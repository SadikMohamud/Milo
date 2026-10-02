"""Experiment ID system and the training guard.

Every run (data pipeline, LID comparison, tokenizer benchmark, evaluation,
training) gets a unique ID and a ``run.yaml`` under experiments/runs/<id>/.
Training additionally requires an approval block that names the approver and
the costed entry in docs/COMPUTE.md; ``require_training_approval`` enforces
this and every training entry point must call it first.

ID format: ASAL-<KIND>-<YYYYMMDD>-<slug>-<hash6>
  KIND  one of DATA, LID, TOK, EVAL, TRAIN
  hash6 first 6 hex chars of sha256(kind, slug, config, created timestamp)
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import paths

KINDS = ("DATA", "LID", "TOK", "EVAL", "TRAIN")
ID_RE = re.compile(r"^ASAL-(DATA|LID|TOK|EVAL|TRAIN)-\d{8}-[a-z0-9][a-z0-9-]{0,40}-[0-9a-f]{6}$")

# Fields every run records (docs/EXPERIMENTS.md). Unknown until filled.
RUN_FIELDS = (
    "model", "track", "base_model", "parameters", "dataset", "dataset_fingerprint", "epochs",
    "tokenizer", "tokenizer_version", "context_length", "batch_size", "learning_rate", "optimizer",
    "scheduler", "precision", "steps", "seed", "hardware", "gpu_hours", "estimated_cost",
    "git_commit", "results",
)


class TrainingNotApproved(RuntimeError):
    pass


def git_commit(cwd: Path = paths.ROOT) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True).stdout
        return out.stdout.strip() + ("-dirty" if dirty.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def make_id(kind: str, slug: str, config: dict | None = None, created: datetime | None = None) -> str:
    kind = kind.upper()
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")[:40] or "run"
    created = created or datetime.now(timezone.utc)
    payload = json.dumps({"kind": kind, "slug": slug, "config": config or {}, "t": created.isoformat()},
                         sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:6]
    return f"ASAL-{kind}-{created:%Y%m%d}-{slug}-{digest}"


def is_valid_id(exp_id: str) -> bool:
    return bool(ID_RE.match(exp_id))


def register(kind: str, slug: str, config: dict | None = None, description: str = "",
             runs_dir: Path = paths.EXPERIMENT_RUNS, **fields) -> tuple[str, Path]:
    """Create experiments/runs/<id>/run.yaml and return (id, path). Never overwrites."""
    created = datetime.now(timezone.utc)
    exp_id = make_id(kind, slug, config, created)
    run_dir = runs_dir / exp_id
    run_dir.mkdir(parents=True, exist_ok=False)
    record = {
        "id": exp_id,
        "kind": kind.upper(),
        "description": description,
        "created": created.isoformat(timespec="seconds"),
        "status": "registered",
        "config": config or {},
        **{k: fields.get(k, "unknown") for k in RUN_FIELDS},
    }
    record["git_commit"] = fields.get("git_commit") or git_commit()
    if kind.upper() == "TRAIN":
        record["approval"] = {"approved_by": None, "approved_on": None, "compute_entry": None, "phase_gate": None}
    path = run_dir / "run.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return exp_id, path


def load(exp_id: str, runs_dir: Path = paths.EXPERIMENT_RUNS) -> dict:
    path = runs_dir / exp_id / "run.yaml"
    if not path.exists():
        raise FileNotFoundError(f"experiment {exp_id} is not registered ({path} missing)")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def update(exp_id: str, runs_dir: Path = paths.EXPERIMENT_RUNS, **changes) -> dict:
    record = load(exp_id, runs_dir)
    record.update(changes)
    (runs_dir / exp_id / "run.yaml").write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
                                                encoding="utf-8")
    return record


def require_training_approval(exp_id: str | None, runs_dir: Path = paths.EXPERIMENT_RUNS,
                              compute_doc: Path = paths.ROOT / "docs" / "COMPUTE.md") -> dict:
    """Raise TrainingNotApproved unless exp_id is a registered, approved TRAIN experiment."""
    if not exp_id:
        raise TrainingNotApproved("no experiment ID given: every training run needs a registered experiment")
    if not is_valid_id(exp_id):
        raise TrainingNotApproved(f"'{exp_id}' is not a valid Asal experiment ID")
    try:
        record = load(exp_id, runs_dir)
    except FileNotFoundError as err:
        raise TrainingNotApproved(str(err)) from err
    if record.get("kind") != "TRAIN":
        raise TrainingNotApproved(f"{exp_id} is a {record.get('kind')} experiment, not TRAIN")
    approval = record.get("approval") or {}
    missing = [k for k in ("approved_by", "approved_on", "compute_entry", "phase_gate") if not approval.get(k)]
    if missing:
        raise TrainingNotApproved(f"{exp_id}: approval incomplete, missing {missing}")
    if not compute_doc.exists():
        raise TrainingNotApproved(f"{compute_doc} does not exist: training needs a costed compute plan")
    if approval["compute_entry"] not in compute_doc.read_text(encoding="utf-8"):
        raise TrainingNotApproved(f"{exp_id}: compute entry '{approval['compute_entry']}' not found in {compute_doc.name}")
    return record
