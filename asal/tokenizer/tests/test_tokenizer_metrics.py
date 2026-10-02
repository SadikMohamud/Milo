import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from asal import tokenizer_metrics as tm  # noqa: E402

TEXTS = ["Waa maxay su'aashu?", "Lo' badan ayaa jira."]


def test_byte_reference():
    r = tm.report("bytes", tm.utf8_bytes_encode, TEXTS, tm.utf8_bytes_decode)
    assert r["bytes_per_token"] == 1.0
    assert r["roundtrip_fidelity"] == 1.0


def test_fertility_whitespace():
    assert tm.fertility(str.split, ["waa haa", "ba'an"]) == 1.0


def test_unknown_and_fallback_rates():
    enc = lambda t: ["<unk>" if w == "x" else w for w in t.split()]  # noqa: E731
    assert tm.unknown_rate(enc, ["a x b x"], "<unk>") == 0.5
    assert tm.byte_fallback_rate(lambda t: ["<0xE2>", "waa"], ["."], lambda tok: tok.startswith("<0x")) == 0.5
