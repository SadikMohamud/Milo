import json

from asal import registry
from asal.lid import AsalHeuristicLID
from asal.pipeline import Pipeline, PipelineConfig

S1 = ("Dowladda Soomaaliya ayaa sheegtay in ay qorsheyneyso dib u habeyn lagu sameynayo nidaamka "
      "waxbarashada dalka, iyadoo la xoojinayo tayada macallimiinta iyo dugsiyada.")
S2 = ("Roobab culus oo ka da'ay gobollada koonfureed ayaa sababay fatahaado, waxaana barakacay "
      "kumanaan qoys oo ku noolaa tuulooyinka ku teedsan wabiga.")
EVAL = ("Kooxda Manchester United ayaa la hadli doonta difaacooda kaddib markii la shaaciyay inuu ku "
        "xadgudbay shuruucda xayiraadaha dalkiisa")


def test_pipeline_end_to_end(tmp_path):
    reg = registry.validate().entries
    recs = [
        {"id": "masakhanews-som:1", "source": "masakhanews-som", "source_record_id": "1", "text": S1},
        {"id": "sib200-som:1", "source": "sib200-som", "source_record_id": "1", "text": S1},  # cross-source dup
        {"id": "masakhanews-som:2", "source": "masakhanews-som", "source_record_id": "2",
         "text": S2.replace("da'ay", "da’ay") + " Wac +252 61 234 5678."},
        {"id": "masakhanews-som:3", "source": "masakhanews-som", "source_record_id": "3",
         "text": "The government said it plans to reform the national education system this year."},
        {"id": "masakhanews-som:4", "source": "masakhanews-som", "source_record_id": "4", "text": "Warka: " + EVAL},
        {"id": "unknown:1", "source": "not-registered", "source_record_id": "1", "text": S2},
    ]
    eval_items = [{"eval_set": "news-test", "item_id": "9", "text": EVAL}]
    pipe = Pipeline(PipelineConfig(), reg, eval_items, [AsalHeuristicLID()], experiment_id="ASAL-DATA-test")
    final, summary = pipe.run(recs, tmp_path)

    assert [r["id"] for r in final] == ["masakhanews-som:1", "masakhanews-som:2"]
    by_stage = {s["stage"]: s for s in summary["stages"]}
    assert by_stage["format_validation"]["rejected_by_reason"] == {"unregistered_source": 1}
    assert by_stage["language_identification"]["rejected_by_reason"] == {"lid_not_somali": 1}
    assert by_stage["exact_dedup"]["stats"]["removed_cross_source"] == 1
    assert by_stage["evaluation_decontamination"]["rejected_by_reason"] == {"eval_contamination": 1}

    r2 = final[1]
    assert "da'ay" in r2["text"] and "<PHONE>" in r2["text"]
    assert r2["dialect"] == "unknown" and r2["dialect_confidence"] is None
    assert r2["license"]["status"] == "not_approved_validation_only"
    assert r2["derived_from"] == ["BBC News Somali"]
    for key in ("id", "text", "source", "source_record_id", "derived_from", "language", "dialect",
                "dialect_confidence", "domain", "license", "machine_translated", "synthetic", "content_hash",
                "pipeline_version", "quality", "provenance"):
        assert key in r2

    for d in tmp_path.iterdir():
        if d.is_dir():
            assert {p.name for p in d.iterdir()} == {"kept.jsonl", "rejected.jsonl", "stats.json", "log.txt"}
    assert json.loads((tmp_path / "summary.json").read_text())["final_records"] == 2


def test_training_mode_rejects_unapproved_sources():
    reg = registry.validate().entries
    recs = [{"id": "masakhanews-som:1", "source": "masakhanews-som", "source_record_id": "1", "text": S1}]
    final, summary = Pipeline(PipelineConfig(mode="training"), reg, [], [AsalHeuristicLID()]).run(recs)
    assert final == []
    assert summary["stages"][-2]["rejected_by_reason"] == {"license_not_approved": 1}
