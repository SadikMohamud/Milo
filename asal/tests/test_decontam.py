from asal.decontam import EvalIndex, scan

EVAL_LONG = ("Kooxda Manchester United ayaa la hadli doonta difaacooda kaddib markii la shaaciyay "
             "inuu ku xadgudbay shuruucda xayiraadaha dalkiisa")
EVAL_SHORT = "Zayat kuma dhaawacmin shilka xalay magaalada."


def build(n=13):
    idx = EvalIndex(n=n)
    idx.add("news-test", "1", EVAL_LONG)
    idx.add("sib-test", "7", EVAL_SHORT)
    idx.add("sib-test", "8", "Haa waa.")  # too short to index
    return idx


def test_detects_long_overlap():
    res = build().check("War cusub: " + EVAL_LONG + " Taasi waa warka.")
    assert res.contaminated and res.eval_hits == ["news-test:1"]


def test_detects_short_item_verbatim():
    res = build().check("Warbixin: zayat kuma dhaawacmin shilka xalay magaalada, ayay tiri booliska.")
    assert res.contaminated and "sib-test:7" in res.eval_hits


def test_clean_text_passes():
    assert not build().check("Roobab culus ayaa ka da'ay gobollada koonfureed toddobaadkan.").contaminated


def test_scan_summary_counts():
    recs = [{"id": "a", "text": EVAL_LONG}, {"id": "b", "text": "Wax kale oo aan xiriir la lahayn."}]
    clean, bad, summary = scan(recs, build())
    assert [r["id"] for r in clean] == ["b"] and [r["id"] for r in bad] == ["a"]
    assert summary["per_eval_set"]["news-test"]["training_records_overlapping"] == 1
    assert summary["per_eval_set"]["sib-test"]["eval_items_skipped_too_short"] == 1
