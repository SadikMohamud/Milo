"""Canonical repository paths. Everything is resolved relative to the repo root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
REGISTRY_DIR = DATA / "registry"
REGISTRY_SCHEMA = REGISTRY_DIR / "schema.json"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
REJECTED = DATA / "rejected"
MANIFESTS = DATA / "manifests"

EVALUATION = ROOT / "evaluation"
EVAL_SETS = EVALUATION / "decontamination" / "eval_sets.yaml"
REPORTS = EVALUATION / "reports"

EXPERIMENTS = ROOT / "experiments"
EXPERIMENT_RUNS = EXPERIMENTS / "runs"
EXPERIMENT_SCHEMA = EXPERIMENTS / "run_schema.json"
