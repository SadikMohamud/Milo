"""Draw native-speaker review sheets from a pipeline run, or summarise filled sheets.

  python scripts/data/draw_review_sample.py draw ASAL-DATA-...  [--n 50] [--seed 0]
  python scripts/data/draw_review_sample.py summarise ASAL-DATA-...

Sheets: data/samples/<experiment-id>/review_*.tsv (not committed).
Summary: evaluation/reports/reviews/<experiment-id>.json (committed, no text).
Log every completed review (reviewer, varieties spoken, sheets, findings) in RESEARCH_LOG.md.
"""
import argparse
import json
import sys

import _bootstrap  # noqa: F401
from asal import paths, review


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["draw", "summarise"])
    ap.add_argument("experiment_id")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sheet_dir = paths.DATA / "samples" / args.experiment_id
    if args.action == "draw":
        run_dir = paths.INTERIM / args.experiment_id
        if not run_dir.exists():
            print(f"no pipeline outputs at {run_dir}", file=sys.stderr)
            return 1
        written = review.draw(run_dir, sheet_dir, n=args.n, seed=args.seed, flag_fields={
            "mt_suspected": ("machine_translated", "suspected"),
            "religion": ("domain", "religion"),
        })
        for name, rows in written.items():
            print(f"{rows:>4} rows  {sheet_dir.relative_to(paths.ROOT)}/review_{name}.tsv")
        return 0
    summary = review.summarise(sheet_dir)
    out = paths.REPORTS / "reviews" / f"{args.experiment_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
