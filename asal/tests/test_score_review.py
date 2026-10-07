import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "evaluation"))

import score_review  # noqa: E402


def test_score_strata_and_gate_estimates():
    key = {"items": [
        {"item": "lid-001", "set": "lid", "stratum": "cld2_only"},
        {"item": "lid-002", "set": "lid", "stratum": "cld2_only"},
        {"item": "lid-003", "set": "lid", "stratum": "heuristic_only"},
        {"item": "lid-004", "set": "lid", "stratum": "both"},
        {"item": "lid-005", "set": "lid", "stratum": "neither"},
        {"item": "mt-001", "set": "mt", "stratum": "subdomain"},
        {"item": "religion-001", "set": "religion", "stratum": "flagged"},
    ]}
    answers = {"lid-001": {"answer": "somali"}, "lid-002": {"answer": "not_somali"},
               "lid-003": {"answer": "not_somali"}, "lid-004": {"answer": "maay"},
               "lid-005": {"answer": "not_somali"}, "mt-001": {"answer": "machine_translated"},
               "religion-001": {"answer": "unsure"}}
    r = score_review.score(key, answers)
    assert r["lid_share_somali_by_stratum"]["cld2_only"]["rate"] == 0.5
    assert r["lid_maay_answers"] == 1
    g = r["lid_gate_estimates"]["cld2"]
    assert 0.9 < g["precision_est"] < 1.0 and g["false_reject_share_est"] == 0.0
    assert r["mt_share_machine_translated"]["subdomain"]["rate"] == 1.0
    assert r["religion"]["flagged"]["n"] == 0  # "unsure" is not counted
