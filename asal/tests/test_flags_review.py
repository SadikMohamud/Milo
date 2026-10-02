import csv
import gzip
import hashlib
import json

from asal import download, flags, readers, review
from asal.lid import segment_lid


def test_mt_url_heuristic():
    assert flags.mt_suspect_from_url("https://so.eturbonews.com/123/x") == "language_subdomain"
    assert flags.mt_suspect_from_url("https://www.example.org/so/page") == "language_path"
    assert flags.mt_suspect_from_url("https://www.bbc.com/somali/articles/x") is None
    assert flags.mt_suspect_from_url("https://so.example.so/x") is None  # Somali TLD
    assert flags.mt_suspect_from_url(None) is None and flags.mt_suspect_from_url("_") is None


def test_religion_lexicon():
    assert flags.is_religious("Waxaad dhahdaa: Ilaahay baa og waxa ay qabtaan.")
    assert not flags.is_religious("Dowladda ayaa sheegtay in ay dhisi doonto waddooyin cusub.")


def test_segment_lid_code_switch():
    mixed = ("Wasiirka ayaa sheegay in dowladdu ay ka shaqeyn doonto horumarinta waxbarashada. "
             "The minister said that the government would work on it and the plan is ready.")
    assert segment_lid(mixed)["code_switched"]
    assert not segment_lid("Wasiirka ayaa sheegay in dowladdu ay ka shaqeyn doonto horumarinta.")["code_switched"]


def test_byte_range_and_nllb_reader(tmp_path):
    import random
    rng = random.Random(0)
    lines = ["eng one\tWaa jumlad koowaad oo Soomaali ah.\t1.2\t1.0\t1.0\tcc\thttps://a.com/x\tcc\thttps://so.a.com/x",
             "eng two\tTan waa tan labaad oo aad u dheer.\t1.1\t1.0\t0.9\tparacrawl\t_\tparacrawl\t_"]
    lines += [f"e{i}\t{' '.join(rng.choice(['waa', 'iyo', 'ka', 'dal', 'magaalo']) for _ in range(8))} {i}\t1.0\t1\t1\tx\t_\tx\t_"
              for i in range(400)]
    full = gzip.compress(("\n".join(lines) + "\n").encode())
    src = tmp_path / "nllb.gz"
    src.write_bytes(full)
    prefix = full[:len(full) // 2]
    entry = {"url": src.as_uri(), "byte_range": [0, len(prefix) - 1], "sha256": hashlib.sha256(prefix).hexdigest(),
             "path": "n/head.gz", "source_id": "nllb-en-so", "split": "head", "format": "nllb_gz_prefix"}
    res = download.fetch(entry, tmp_path / "raw")
    assert res.bytes == len(prefix)
    recs = readers.read(entry, tmp_path / "raw")
    assert 2 < len(recs) < 402
    assert recs[0]["text"] == "Waa jumlad koowaad oo Soomaali ah."
    assert recs[0]["meta"]["url"] == "https://so.a.com/x" and recs[1]["meta"]["url"] is None


def _write_jsonl(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")


def test_review_draw_and_summarise(tmp_path):
    run = tmp_path / "run"
    kept = [{"id": f"s:{i}", "source": "s", "text": f"waa qoraal {i}"} for i in range(30)]
    rej = [{"id": f"s:r{i}", "source": "s", "text": f"text {i}", "reason": "lid_not_somali"} for i in range(30)]
    _write_jsonl(run / "03_language_identification" / "kept.jsonl", kept)
    _write_jsonl(run / "03_language_identification" / "rejected.jsonl", rej)
    _write_jsonl(run / "01_normalise" / "rejected.jsonl", [])
    _write_jsonl(run / "final_corpus.jsonl", [{**k, "domain": "religion"} for k in kept[:5]])
    out = tmp_path / "sheets"
    written = review.draw(run, out, n=10, seed=1, flag_fields={"religion": ("domain", "religion")})
    assert written == {"03_language_identification": 20, "flag_religion": 5}
    path = out / "review_03_language_identification.tsv"
    rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))
    for r in rows:
        r["verdict"] = "wrong" if r["decision"] == "rejected" and int(r["sample_id"]) % 2 else "correct"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=review.FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    s = review.summarise(out)["review_03_language_identification"]["by_decision"]
    assert s["kept"]["wrong_rate"] == 0.0
    assert 0 < s["rejected"]["wrong_rate"] < 1
    lo, hi = s["rejected"]["wrong_rate_95ci"]
    assert lo <= s["rejected"]["wrong_rate"] <= hi


def test_wilson_bounds():
    assert review.wilson(0, 0) == (0.0, 1.0)
    lo, hi = review.wilson(5, 50)
    assert 0.03 < lo < 0.1 < hi < 0.22
