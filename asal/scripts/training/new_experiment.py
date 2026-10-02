"""Register a new experiment and print its ID.

Usage: python scripts/training/new_experiment.py KIND SLUG [--description TEXT] [--config CONFIG.yaml]
KIND is one of DATA, LID, TOK, EVAL, TRAIN. TRAIN experiments are created
unapproved; a maintainer fills in the approval block by hand after reviewing
docs/COMPUTE.md and docs/PHASE_GATES.md.
"""
import argparse
import sys

import yaml

import _bootstrap  # noqa: F401
from asal import experiments


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=experiments.KINDS)
    ap.add_argument("slug")
    ap.add_argument("--description", default="")
    ap.add_argument("--config")
    args = ap.parse_args()
    config = yaml.safe_load(open(args.config, encoding="utf-8")) if args.config else {}
    exp_id, path = experiments.register(args.kind, args.slug, config=config, description=args.description)
    print(exp_id)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
