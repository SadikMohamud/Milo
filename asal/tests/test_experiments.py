import pytest
import yaml

from asal import experiments
from asal.experiments import TrainingNotApproved, require_training_approval


def test_id_format():
    exp_id = experiments.make_id("data", "Sample Pipeline!")
    assert experiments.is_valid_id(exp_id)
    assert exp_id.startswith("ASAL-DATA-") and "-sample-pipeline-" in exp_id


def test_register_creates_unique_runs(tmp_path):
    a, pa = experiments.register("EVAL", "x", runs_dir=tmp_path, git_commit="abc")
    b, _ = experiments.register("EVAL", "x", runs_dir=tmp_path, git_commit="abc")
    assert a != b
    rec = yaml.safe_load(pa.read_text())
    assert rec["status"] == "registered" and rec["seed"] == "unknown" and rec["git_commit"] == "abc"


def test_training_guard(tmp_path):
    compute = tmp_path / "COMPUTE.md"
    compute.write_text("## C-001 Asal-Scratch-20M\n")
    with pytest.raises(TrainingNotApproved):
        require_training_approval(None, tmp_path, compute)
    with pytest.raises(TrainingNotApproved):
        require_training_approval("ASAL-TRAIN-20260101-x-abcdef", tmp_path, compute)
    data_id, _ = experiments.register("DATA", "d", runs_dir=tmp_path, git_commit="abc")
    with pytest.raises(TrainingNotApproved, match="not TRAIN"):
        require_training_approval(data_id, tmp_path, compute)
    train_id, _ = experiments.register("TRAIN", "scratch-20m", runs_dir=tmp_path, git_commit="abc")
    with pytest.raises(TrainingNotApproved, match="approval incomplete"):
        require_training_approval(train_id, tmp_path, compute)
    approval = {"approved_by": "maintainer", "approved_on": "2026-10-02", "compute_entry": "C-999", "phase_gate": "G3"}
    experiments.update(train_id, runs_dir=tmp_path, approval=approval)
    with pytest.raises(TrainingNotApproved, match="not found"):
        require_training_approval(train_id, tmp_path, compute)
    experiments.update(train_id, runs_dir=tmp_path, approval={**approval, "compute_entry": "C-001"})
    assert require_training_approval(train_id, tmp_path, compute)["id"] == train_id
    with pytest.raises(TrainingNotApproved, match="does not exist"):
        require_training_approval(train_id, tmp_path, tmp_path / "missing.md")
