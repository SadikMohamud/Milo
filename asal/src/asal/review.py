"""Native-speaker review of pipeline decisions.

``draw`` writes seeded review sheets (TSV) from a pipeline run: for every stage
that rejected anything, ``n`` rejected and ``n`` kept records; plus optional
per-flag sheets (e.g. records flagged as suspected MT or religion). Sheets go
to data/samples/<experiment-id>/ (not committed: they contain text).

A reviewer fills two columns per row:
  verdict  correct | wrong | unsure   (was the pipeline's decision right?)
  note     free text (why; Somali-specific problems, dialect, MT feel, ...)

``summarise`` reads filled sheets and reports, per sheet, the share of wrong
decisions with a 95% Wilson interval. Only the summary (no text) is committed.
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter
from pathlib import Path

FIELDS = ["sample_id", "record_id", "source", "stage", "decision", "reason", "flag", "text", "verdict", "note"]
VERDICTS = ("correct", "wrong", "unsure")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def _row(i: int, rec: dict, stage: str, decision: str, flag: str = "") -> dict:
    return {"sample_id": i, "record_id": rec["id"], "source": rec["source"], "stage": stage,
            "decision": decision, "reason": rec.get("reason", ""), "flag": flag,
            "text": " ".join(rec["text"].split())[:2000], "verdict": "", "note": ""}


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def draw(run_dir: Path, out_dir: Path, n: int = 50, seed: int = 0,
         flag_fields: dict[str, tuple[str, object]] | None = None) -> dict[str, int]:
    """Write review sheets; return {sheet name: rows}.

    flag_fields maps a sheet name to (final-record field, value), e.g.
    {"mt_suspected": ("machine_translated", "suspected")}; it samples n records of
    the final corpus with that value.
    """
    rng = random.Random(seed)
    written: dict[str, int] = {}
    for stage_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name[:2].isdigit()):
        rejected = _read_jsonl(stage_dir / "rejected.jsonl")
        if not rejected:
            continue
        kept = _read_jsonl(stage_dir / "kept.jsonl")
        stage = stage_dir.name[3:]
        rows = [_row(0, r, stage, "rejected") for r in rng.sample(rejected, min(n, len(rejected)))]
        rows += [_row(0, r, stage, "kept") for r in rng.sample(kept, min(n, len(kept)))]
        rng.shuffle(rows)  # reviewers should not see decisions in blocks
        for i, row in enumerate(rows):
            row["sample_id"] = i
        _write(out_dir / f"review_{stage_dir.name}.tsv", rows)
        written[stage_dir.name] = len(rows)
    final = _read_jsonl(run_dir / "final_corpus.jsonl")
    for sheet, (fieldname, value) in (flag_fields or {}).items():
        pool = [r for r in final if r.get(fieldname) == value]
        if not pool:
            continue
        rows = [_row(i, r, "final", "flagged", f"{fieldname}={value}")
                for i, r in enumerate(rng.sample(pool, min(n, len(pool))))]
        _write(out_dir / f"review_flag_{sheet}.tsv", rows)
        written[f"flag_{sheet}"] = len(rows)
    return written


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def summarise(sheet_dir: Path) -> dict:
    out = {}
    for path in sorted(sheet_dir.glob("review_*.tsv")):
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        by_decision: dict[str, Counter] = {}
        invalid = 0
        for r in rows:
            v = (r.get("verdict") or "").strip().lower()
            if v and v not in VERDICTS:
                invalid += 1
                continue
            by_decision.setdefault(r["decision"], Counter())[v or "unreviewed"] += 1
        summary = {}
        for decision, c in by_decision.items():
            judged = c["correct"] + c["wrong"]
            summary[decision] = {**dict(c), "wrong_rate": round(c["wrong"] / judged, 4) if judged else None,
                                 "wrong_rate_95ci": wilson(c["wrong"], judged) if judged else None}
        out[path.stem] = {"rows": len(rows), "invalid_verdicts": invalid, "by_decision": summary}
    return out
