import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "train.py"


def test_train_refuses_without_experiment():
    res = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert res.returncode == 2 and "refusing to train" in res.stderr


def test_train_refuses_unknown_experiment():
    res = subprocess.run([sys.executable, str(SCRIPT), "--experiment-id", "ASAL-TRAIN-20260101-nope-abcdef"],
                         capture_output=True, text=True)
    assert res.returncode == 2
