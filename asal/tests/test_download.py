import hashlib

import pytest

from asal import download


def test_fetch_verifies_checksum(tmp_path):
    src = tmp_path / "src.tsv"
    src.write_text("index_id\ttext\n1\tWaa tijaabo.\n", encoding="utf-8")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    entry = {"url": src.as_uri(), "sha256": sha, "path": "x/src.tsv"}
    raw = tmp_path / "raw"
    first = download.fetch(entry, raw)
    assert first.downloaded and first.sha256 == sha
    again = download.fetch(entry, raw)
    assert not again.downloaded
    with pytest.raises(download.ChecksumMismatch):
        download.fetch({**entry, "sha256": "0" * 64, "path": "y/src.tsv"}, raw)
    assert not (raw / "y" / "src.tsv").exists()
