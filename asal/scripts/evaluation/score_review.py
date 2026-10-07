"""Score the native-speaker answers from the Asal Review page against the hidden strata.

Export the answers first (Claude does this with ArtifactData `list` + `out_dir`), which
writes one JSON file per answer: <dir>/verdicts/<item-id>.json.

  python scripts/evaluation/score_review.py <export-dir> [--key evaluation/human_eval/review-v0.3/key.json]

Writes evaluation/human_eval/review-v0.3/results.json (no sentence text).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401
from asal import paths
from asal.review import wilson

# Population sizes of each LID stratum in ASAL-DATA-20261007-nllb-random-pipeline-45ad3f (51,277 sentences).
LID_POPULATION = {"cld2_only": 6194, "heuristic_only": 616, "both": 42391, "neither": 2076}
SOMALI_ANSWERS = {"somali", "maay", "mixed"}


def load_answers(export_dir: Path) -> dict:
    out = {}
    for p in (export_dir / "verdicts").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[p.stem] = d.get("data", d)
    return out


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "ci95": wilson(k, n) if n else None}


def score(key: dict, answers: dict) -> dict:
    by = defaultdict(list)
    for it in key["items"]:
        a = answers.get(it["item"])
        if a and a.get("answer") and a["answer"] != "unsure":
            by[(it["set"], it["stratum"])].append(a["answer"])
    res = {"answered": sum(1 for it in key["items"] if it["item"] in answers), "total": len(key["items"]),
           "answer_counts": {f"{s}/{st}": dict(Counter(v)) for (s, st), v in sorted(by.items())}}
    lid = {st: rate(sum(a in SOMALI_ANSWERS for a in by[("lid", st)]), len(by[("lid", st)])) for st in LID_POPULATION}
    res["lid_share_somali_by_stratum"] = lid

    def gate(accepts: list[str]) -> dict:
        acc = [s for s in LID_POPULATION if s in accepts]
        rej = [s for s in LID_POPULATION if s not in accepts]
        def weighted(strata, somali: bool):
            num = den = 0.0
            for s in strata:
                r = lid[s]["rate"]
                if r is None:
                    return None
                num += LID_POPULATION[s] * (r if somali else 1 - r)
                den += LID_POPULATION[s]
            return round(num / den, 4) if den else None
        return {"precision_est": weighted(acc, True), "false_reject_share_est": weighted(rej, True)}

    res["lid_gate_estimates"] = {"cld2": gate(["cld2_only", "both"]), "asal-heuristic": gate(["heuristic_only", "both"])}
    res["lid_maay_answers"] = sum(a == "maay" for (s, _), v in by.items() if s == "lid" for a in v)
    res["mt_share_machine_translated"] = {st: rate(sum(a == "machine_translated" for a in by[("mt", st)]),
                                                   len(by[("mt", st)])) for st in ("subdomain", "path", "url_not_flagged")}
    res["religion"] = {st: rate(sum(a == "religious" for a in by[("religion", st)]), len(by[("religion", st)]))
                       for st in ("flagged", "not_flagged")}
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("--key", default=str(paths.ROOT / "evaluation/human_eval/review-v0.3/key.json"))
    args = ap.parse_args()
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    res = score(key, load_answers(Path(args.export_dir)))
    out = Path(args.key).with_name("results.json")
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
