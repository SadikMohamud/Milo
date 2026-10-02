"""The Asal data pipeline (docs/DATA_PIPELINE.md).

Stages run in the order of the build specification. Each stage writes, under
``<out_dir>/<NN>_<stage>/``:

  kept.jsonl      records that continue
  rejected.jsonl  records removed here, each with ``reason`` (a stable code)
  stats.json      counts and stage-specific statistics
  log.txt         a human-readable summary

Stages that Asal cannot yet perform properly (dialect classification needs a
human-labelled set that does not exist yet) are present, run, and say so in
their log; they set ``unknown`` rather than guessing.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import PIPELINE_VERSION
from . import dedup, flags, normalize, pii, quality
from .decontam import EvalIndex, scan
from .lid import SOMALI, AsalHeuristicLID, segment_lid
from .stats import corpus_stats
from .textutil import content_hash

LID_NOT_SOMALI = "lid_not_somali"
FORMAT_EMPTY = "format_empty_text"
FORMAT_BAD_FIELDS = "format_missing_fields"
BOILERPLATE_ONLY = "boilerplate_only"
LICENSE_NOT_APPROVED = "license_not_approved"
UNREGISTERED_SOURCE = "unregistered_source"


@dataclass
class StageResult:
    name: str
    kept: list[dict]
    rejected: list[dict]
    stats: dict = field(default_factory=dict)
    log: list[str] = field(default_factory=list)


def _reject(rec: dict, stage: str, reason: str, **extra) -> dict:
    return {**rec, "rejected_at": stage, "reason": reason, **extra}


@dataclass
class PipelineConfig:
    mode: str = "validation"  # "validation" (sample, not for training) | "training"
    primary_lid: str = "asal-heuristic"
    quality_thresholds: dict = field(default_factory=dict)
    near_dup_threshold: float = 0.8
    boilerplate_min_docs: int = 3
    boilerplate_min_fraction: float = 0.01
    boilerplate_min_chars: int = 15
    decontam_n: tuple[int, ...] = (13, 8)


class Pipeline:
    def __init__(self, config: PipelineConfig, registry: dict[str, dict], eval_items: list[dict],
                 lid_backends: list | None = None, experiment_id: str = "unregistered", manifest: dict | None = None):
        self.cfg = config
        self.registry = registry
        self.eval_items = eval_items  # [{"eval_set", "item_id", "text"}]
        self.lid_backends = lid_backends or [AsalHeuristicLID()]
        self.experiment_id = experiment_id
        self.manifest = manifest or {}
        self._file_info = {f["sha256"]: f for f in self.manifest.get("files", [])}
        names = [b.name for b in self.lid_backends]
        if config.primary_lid not in names:
            raise ValueError(f"primary LID backend '{config.primary_lid}' not among {names}")
        if config.mode not in ("validation", "training"):
            raise ValueError("mode must be 'validation' or 'training'")

    # -- stages -------------------------------------------------------------

    def s_normalise(self, recs):
        out, totals = [], Counter()
        for r in recs:
            res = normalize.normalise(r["text"])
            totals.update(res.changes)
            out.append({**r, "text": res.text, "ann": {**r.get("ann", {}), "normalisation": dict(res.changes)}})
        return StageResult("normalise", out, [], {"changes": dict(totals)})

    def s_format_validation(self, recs):
        kept, rej = [], []
        for r in recs:
            if not all(k in r for k in ("id", "source", "source_record_id", "text")):
                rej.append(_reject(r, "format_validation", FORMAT_BAD_FIELDS))
            elif not isinstance(r["text"], str) or not r["text"].strip():
                rej.append(_reject(r, "format_validation", FORMAT_EMPTY))
            elif r["source"] not in self.registry:
                rej.append(_reject(r, "format_validation", UNREGISTERED_SOURCE))
            else:
                kept.append(r)
        return StageResult("format_validation", kept, rej)

    def s_language_identification(self, recs):
        kept, rej = [], []
        agree, switched = Counter(), 0
        seg_backend = AsalHeuristicLID()
        for r in recs:
            preds = {b.name: b.predict(r["text"]) for b in self.lid_backends}
            ann = {name: {"label": p.label, "somali_score": p.somali_score} for name, p in preds.items()}
            seg = segment_lid(r["text"], seg_backend)
            ann["segments"] = seg
            switched += seg["code_switched"]
            primary = preds[self.cfg.primary_lid]
            agree["all_agree" if len({p.label == SOMALI for p in preds.values()}) == 1 else "disagree"] += 1
            r = {**r, "language": SOMALI if primary.label == SOMALI else primary.label,
                 "ann": {**r["ann"], "lid": ann}}
            if primary.label == SOMALI:
                kept.append(r)
            else:
                rej.append(_reject(r, "language_identification", LID_NOT_SOMALI, predicted=primary.label))
        stats = {"primary_backend": self.cfg.primary_lid, "backends": [b.name for b in self.lid_backends],
                 "backend_agreement_on_is_somali": dict(agree),
                 "code_switched_documents (segment-level, asal-heuristic)": switched}
        return StageResult("language_identification", kept, rej, stats)

    def s_quality_filter(self, recs):
        kept, rej = [], []
        for r in recs:
            q = quality.check(r["text"], self.cfg.quality_thresholds)
            r = {**r, "ann": {**r["ann"], "quality": q.metrics}}
            if q.passed:
                kept.append(r)
            else:
                rej.append(_reject(r, "quality_filter", q.reasons[0], all_reasons=q.reasons))
        return StageResult("quality_filter", kept, rej, {"thresholds": {**quality.DEFAULT_THRESHOLDS,
                                                                       **self.cfg.quality_thresholds}})

    def s_pii_filter(self, recs):
        out, totals, docs = [], Counter(), 0
        for r in recs:
            res = pii.redact(r["text"])
            if res.redactions:
                docs += 1
                totals.update(res.redactions)
            out.append({**r, "text": res.text, "ann": {**r["ann"], "pii_redactions": dict(res.redactions)}})
        return StageResult("pii_filter", out, [], {"documents_with_redactions": docs, "redactions": dict(totals)})

    def s_exact_dedup(self, recs):
        res = dedup.exact_dedup(recs)
        return StageResult("exact_dedup", res.kept, [_reject(r, "exact_dedup", r["reason"]) for r in res.removed],
                           res.stats)

    def s_near_dedup(self, recs):
        res = dedup.near_dedup(recs, threshold=self.cfg.near_dup_threshold)
        return StageResult("near_dedup", res.kept, [_reject(r, "near_dedup", r["reason"]) for r in res.removed],
                           res.stats)

    def s_boilerplate_removal(self, recs):
        """Remove lines that recur verbatim across many documents of the same source."""
        by_source: dict[str, Counter] = {}
        n_by_source = Counter(r["source"] for r in recs)
        for r in recs:
            lines = {ln.strip() for ln in r["text"].split("\n") if len(ln.strip()) >= self.cfg.boilerplate_min_chars}
            by_source.setdefault(r["source"], Counter()).update(lines)
        boiler = {}
        for src, counts in by_source.items():
            min_docs = max(self.cfg.boilerplate_min_docs, int(self.cfg.boilerplate_min_fraction * n_by_source[src]))
            boiler[src] = {ln for ln, c in counts.items() if c >= min_docs}
        kept, rej, removed_lines = [], [], Counter()
        for r in recs:
            lines = r["text"].split("\n")
            new = [ln for ln in lines if ln.strip() not in boiler[r["source"]]]
            n_removed = len(lines) - len(new)
            removed_lines[r["source"]] += n_removed
            text = "\n".join(new).strip()
            r = {**r, "text": text, "ann": {**r["ann"], "boilerplate_lines_removed": n_removed}}
            if not text:
                rej.append(_reject(r, "boilerplate_removal", BOILERPLATE_ONLY))
            else:
                kept.append(r)
        stats = {"boilerplate_line_types": {s: len(v) for s, v in boiler.items()},
                 "lines_removed": dict(removed_lines)}
        log = [f"{s}: {len(v)} recurring line type(s) removed" for s, v in boiler.items()]
        return StageResult("boilerplate_removal", kept, rej, stats, log)

    def s_machine_translation_flagging(self, recs):
        out, counts, by_reason, hosts = [], Counter(), Counter(), Counter()
        for r in recs:
            prov = self.registry[r["source"]]["provenance"]
            mt = prov["machine_translated"]
            basis = prov.get("machine_translated_basis", "unknown")
            reason = flags.mt_suspect_from_url((r.get("meta") or {}).get("url"))
            if reason and mt is not True:
                mt, basis = flags.MT_SUSPECTED, f"heuristic:{reason}"
                by_reason[reason] += 1
                hosts[flags.url_host(r["meta"]["url"])] += 1
            counts[str(mt)] += 1
            synthetic = True if mt is True else (False if mt is False else "unknown")
            out.append({**r, "machine_translated": mt, "synthetic": synthetic,
                        "ann": {**r["ann"], "mt_basis": basis}})
        stats = {"machine_translated": dict(counts), "suspected_by_rule": dict(by_reason),
                 "top_suspected_hosts": hosts.most_common(20)}
        return StageResult("machine_translation_flagging", out, [], stats,
                           ["Source-level flag from the registry, overridden to 'suspected' by the URL "
                            "language-subdomain/path heuristic (asal.flags). Suspected records are kept, not removed."])

    def s_dialect_classification(self, recs):
        out = [{**r, "dialect": "unknown", "dialect_confidence": None} for r in recs]
        return StageResult("dialect_classification", out, [], {"dialect": {"unknown": len(out)}},
                           ["No human-labelled dialect set exists yet (docs/ANNOTATION_GUIDELINES.md), so no "
                            "classifier can be trained or evaluated. Every record is 'unknown'."])

    def s_domain_classification(self, recs):
        out, counts = [], Counter()
        for r in recs:
            domains = self.registry[r["source"]]["provenance"]["domains"]
            dom, basis = (domains[0] if domains else "unknown"), "source_default"
            if flags.is_religious(r["text"]):
                dom, basis = "religion", "heuristic:religion-lexicon"
            counts[dom] += 1
            out.append({**r, "domain": dom, "ann": {**r["ann"], "domain_basis": basis}})
        return StageResult("domain_classification", out, [], {"domain": dict(counts)},
                           ["Source default domain from the registry, overridden to 'religion' by the "
                            "religious-lexicon heuristic (asal.flags). No general document classifier yet."])

    def s_evaluation_decontamination(self, recs):
        summaries, clean = {}, recs
        rejected = []
        for n in self.cfg.decontam_n:
            index = EvalIndex(n=n)
            for item in self.eval_items:
                index.add(item["eval_set"], item["item_id"], item["text"])
            clean, contaminated, summary = scan(clean, index)
            summaries[f"n={n}"] = summary
            rejected += [_reject(r, "evaluation_decontamination", r["reason"], ngram_n=n) for r in contaminated]
        return StageResult("evaluation_decontamination", clean, rejected, summaries)

    def s_license_validation(self, recs):
        kept, rej, status = [], [], Counter()
        for r in recs:
            entry = self.registry[r["source"]]
            approved = entry["status"]["approved_for_training"]
            lic_status = "approved_for_training" if approved else "not_approved_validation_only"
            status[lic_status] += 1
            r = {**r, "license": {"corpus_license": entry["license"]["corpus_license"],
                                  "license_basis": entry["license"]["license_basis"], "status": lic_status}}
            if self.cfg.mode == "training" and not approved:
                rej.append(_reject(r, "license_validation", LICENSE_NOT_APPROVED))
            else:
                kept.append(r)
        log = [f"mode={self.cfg.mode}"]
        if self.cfg.mode == "validation":
            log.append("Validation mode: unapproved sources pass but are marked not_approved_validation_only. "
                       "The output must not be used for training.")
        return StageResult("license_validation", kept, rej, {"license_status": dict(status)}, log)

    def s_provenance_attachment(self, recs):
        out = []
        for r in recs:
            entry = self.registry[r["source"]]
            finfo = self._file_info.get(r.get("raw_file_sha256"), {})
            out.append({
                "id": r["id"],
                "text": r["text"],
                "source": r["source"],
                "source_record_id": r["source_record_id"],
                "derived_from": entry["provenance"]["derived_from"],
                "language": r["language"],
                "dialect": r["dialect"],
                "dialect_confidence": r["dialect_confidence"],
                "domain": r["domain"],
                "license": r["license"],
                "machine_translated": r["machine_translated"],
                "synthetic": r["synthetic"],
                "content_hash": content_hash(r["text"]),
                "pipeline_version": PIPELINE_VERSION,
                "quality": {"metrics": r["ann"].get("quality"), "lid": r["ann"].get("lid"),
                            "pii_redactions": r["ann"].get("pii_redactions"),
                            "normalisation": r["ann"].get("normalisation"),
                            "boilerplate_lines_removed": r["ann"].get("boilerplate_lines_removed")},
                "provenance": {
                    "experiment_id": self.experiment_id,
                    "manifest_id": self.manifest.get("manifest_id"),
                    "url": finfo.get("url"),
                    "pinned_revision": finfo.get("pinned_revision"),
                    "raw_file_sha256": r.get("raw_file_sha256"),
                    "split": r.get("split"),
                    "meta": r.get("meta", {}),
                    "domain_basis": r["ann"].get("domain_basis"),
                    "mt_basis": r["ann"].get("mt_basis"),
                },
            })
        return StageResult("provenance_attachment", out, [])

    # -- driver -------------------------------------------------------------

    def stages(self) -> list[Callable]:
        return [self.s_normalise, self.s_format_validation, self.s_language_identification, self.s_quality_filter,
                self.s_pii_filter, self.s_exact_dedup, self.s_near_dedup, self.s_boilerplate_removal,
                self.s_machine_translation_flagging, self.s_dialect_classification, self.s_domain_classification,
                self.s_evaluation_decontamination, self.s_license_validation, self.s_provenance_attachment]

    def run(self, records: list[dict], out_dir: Path | None = None) -> tuple[list[dict], dict]:
        summary = {"experiment_id": self.experiment_id, "pipeline_version": PIPELINE_VERSION,
                   "mode": self.cfg.mode, "input_records": len(records), "stages": []}
        recs = [{**r, "ann": r.get("ann", {})} for r in records]
        for i, stage in enumerate(self.stages(), start=1):
            res = stage(recs)
            reasons = Counter(r["reason"] for r in res.rejected)
            entry = {"stage": res.name, "input": len(recs), "kept": len(res.kept), "rejected": len(res.rejected),
                     "rejected_by_reason": dict(reasons), "stats": res.stats, "log": res.log}
            summary["stages"].append(entry)
            if out_dir is not None:
                _write_stage(out_dir / f"{i:02d}_{res.name}", res, entry)
            recs = res.kept
        summary["final_records"] = len(recs)
        summary["final_stats"] = corpus_stats(recs)
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            _write_jsonl(out_dir / "final_corpus.jsonl", recs)
            (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        return recs, summary


def _write_jsonl(path: Path, recs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def _write_stage(stage_dir: Path, res: StageResult, entry: dict) -> None:
    _write_jsonl(stage_dir / "kept.jsonl", res.kept)
    _write_jsonl(stage_dir / "rejected.jsonl", res.rejected)
    (stage_dir / "stats.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False, default=str),
                                          encoding="utf-8")
    lines = [f"stage: {res.name}", f"input: {entry['input']}", f"kept: {entry['kept']}",
             f"rejected: {entry['rejected']}"]
    lines += [f"  {k}: {v}" for k, v in entry["rejected_by_reason"].items()]
    lines += res.log
    (stage_dir / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
