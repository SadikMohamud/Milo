"""Run the full data pipeline on the v0.1 validation sample.

  1. registers a DATA experiment (experiments/runs/<id>/run.yaml)
  2. reads the pipeline_validation_sample files from the manifest
  3. loads registered evaluation sets for decontamination
  4. runs every pipeline stage, writing per-stage outputs to data/interim/<id>/
  5. writes a text-free summary to evaluation/reports/data_intelligence_v0.1/

Usage: python scripts/data/run_sample_pipeline.py [--primary-lid asal-heuristic|lingua] [--no-lingua]
"""
import argparse
import hashlib
import json
import sys

import _bootstrap  # noqa: F401
from asal import evalsets, experiments, lid, paths, readers, registry
from asal.download import load_manifest
from asal.pipeline import Pipeline, PipelineConfig
from asal.stats import by_key, corpus_stats

REPORT_DIR = paths.REPORTS / "data_intelligence_v0.1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(paths.MANIFESTS / "sample-v0.1.yaml"))
    ap.add_argument("--primary-lid", default="asal-heuristic")
    ap.add_argument("--no-lingua", action="store_true", help="skip the Lingua backend (saves ~1 GB RAM)")
    args = ap.parse_args()

    manifest = load_manifest(paths.Path(args.manifest))
    reg = registry.validate()
    if reg.errors:
        print("registry has errors; run scripts/data/validate_registry.py", file=sys.stderr)
        return 1

    config = PipelineConfig(mode="validation", primary_lid=args.primary_lid)
    exp_id, run_path = experiments.register(
        "DATA", "sample-pipeline", config=dict(vars(config), manifest=manifest["manifest_id"]),
        description="Data pipeline on the v0.1 validation sample (not for training).",
        dataset=manifest["manifest_id"], track="not_applicable", model="not_applicable")
    print(f"experiment {exp_id}")

    records = []
    for f in manifest["files"]:
        if f["role"] == "pipeline_validation_sample":
            records += readers.read(f, paths.RAW)
    eval_items, pending = evalsets.load_items({manifest["manifest_id"]: manifest})

    backends = [lid.AsalHeuristicLID()]
    if not args.no_lingua:
        try:
            backends.append(lid.LinguaLID())
        except ImportError:
            print("lingua not installed; running with the Asal heuristic only")

    raw_stats = {"per_source": by_key(records, lambda r: r["source"]), "all": corpus_stats(records)}
    pipe = Pipeline(config, reg.entries, eval_items, backends, experiment_id=exp_id, manifest=manifest)
    out_dir = paths.INTERIM / exp_id
    final, summary = pipe.run(records, out_dir)

    fingerprint = hashlib.sha256("\n".join(sorted(r["content_hash"] for r in final)).encode()).hexdigest()
    summary["dataset_fingerprint"] = fingerprint
    summary["raw_stats"] = raw_stats
    summary["final_stats_per_source"] = by_key(final, lambda r: r["source"])
    summary["eval_sets_indexed"] = sorted({i["eval_set"] for i in eval_items})
    summary["eval_sets_pending"] = [p["id"] for p in pending]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "pipeline_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    experiments.update(exp_id, status="completed", dataset_fingerprint=fingerprint,
                       results={"input_records": summary["input_records"], "final_records": summary["final_records"],
                                "report": str((REPORT_DIR / "pipeline_summary.json").relative_to(paths.ROOT)),
                                "outputs": str(out_dir.relative_to(paths.ROOT))})

    print(f"{'stage':32} {'in':>6} {'kept':>6} {'rej':>5}  reasons")
    for s in summary["stages"]:
        print(f"{s['stage']:32} {s['input']:>6} {s['kept']:>6} {s['rejected']:>5}  {s['rejected_by_reason']}")
    print(f"final records: {summary['final_records']}  fingerprint {fingerprint[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
