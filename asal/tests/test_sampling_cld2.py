import base64
import gzip
import hashlib

import pytest

from asal import readers, sampling


def _nllb_lines(n):
    return [f"eng {i}\tWaa jumlad {i} oo Soomaali ah.\t{1.05 + (i % 20) / 100:.4f}\t1.0\t1.0\tcc\t_\tcc\t_" for i in range(n)]


def test_selection_is_deterministic_and_near_rate():
    picks = [i for i in range(20000) if sampling.selected(i, seed=7, rate=0.05)]
    assert picks == [i for i in range(20000) if sampling.selected(i, seed=7, rate=0.05)]
    assert 800 < len(picks) < 1200
    assert picks != [i for i in range(20000) if sampling.selected(i, seed=8, rate=0.05)]


def test_hash_line_sample_end_to_end(tmp_path):
    payload = gzip.compress(("\n".join(_nllb_lines(3000)) + "\n").encode())
    md5 = base64.b64encode(hashlib.md5(payload).digest()).decode()
    chunks = [payload[i:i + 997] for i in range(0, len(payload), 997)]  # odd chunk size splits lines
    out = tmp_path / "s.tsv.gz"
    stats = sampling.hash_line_sample("mem://x", out, seed=1, rate=0.1, expected_md5_b64=md5, score_column=2,
                                      chunks=chunks)
    assert stats["lines"] == 3000 and 200 < stats["kept"] < 400
    assert sum(stats["score_histogram"].values()) == 3000
    first = out.read_bytes()
    sampling.hash_line_sample("mem://x", out, seed=1, rate=0.1, expected_md5_b64=md5, chunks=chunks)
    assert out.read_bytes() == first  # byte-identical: gzip mtime is pinned
    entry = {"path": "s.tsv.gz", "source_id": "nllb-en-so", "split": "r", "sha256": "x"}
    recs = readers.read_nllb_line_sample(entry, tmp_path)
    assert len(recs) == stats["kept"]
    i = int(recs[0]["source_record_id"].split("-")[1])
    assert recs[0]["text"] == f"Waa jumlad {i} oo Soomaali ah."
    with pytest.raises(sampling.SourceChecksumMismatch):
        sampling.hash_line_sample("mem://x", tmp_path / "bad.tsv.gz", seed=1, rate=0.1,
                                  expected_md5_b64="AAAA", chunks=chunks)
    assert not (tmp_path / "bad.tsv.gz").exists()


def test_cld2_backend():
    pytest.importorskip("pycld2")
    from asal.lid import Cld2LID

    c = Cld2LID()
    assert c.predict("Wasiirka ayaa sheegay in dowladdu ay ka shaqeyn doonto horumarinta waxbarashada.").label == "som"
    assert c.predict("The minister said that the government would improve education.").label == "eng"
    assert c.predict("").label in ("und", "eng")  # empty input never raises
