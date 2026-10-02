"""Training entry point (placeholder).

v0.1 performs no training. This script exists so that the guard is the first
thing any future training code runs: without a registered, approved TRAIN
experiment (experiments/runs/<id>/run.yaml with an approval block that names a
costed entry in docs/COMPUTE.md) it refuses to start.

Usage: python training/scripts/train.py --experiment-id ASAL-TRAIN-...
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from asal.experiments import TrainingNotApproved, require_training_approval  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment-id")
    args = ap.parse_args(argv)
    try:
        record = require_training_approval(args.experiment_id)
    except TrainingNotApproved as err:
        print(f"refusing to train: {err}", file=sys.stderr)
        return 2
    print(f"{record['id']} is approved, but no training code exists in v0.1 (Phase 0).", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
