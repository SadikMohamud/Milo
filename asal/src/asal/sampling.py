"""Single-pass, reproducible sampling of large gzip line files.

Used when an upstream file is too large to keep but a representative sample is
needed (e.g. NLLB eng-som, 1.7 GB compressed, sorted by alignment score, so a
prefix is biased). The whole object is streamed once:

* the MD5 of the compressed bytes is checked against the value pinned in the
  manifest (the object's own MD5 as reported by the host), so the sample is
  provably drawn from that exact file;
* line ``i`` (0-based) is kept iff  blake2b(f"{seed}:{i}") / 2**64 < rate.
  Selection depends only on (seed, line number), so anyone with the same file
  gets the same sample, and the sample is uniform over lines;
* every line, kept or not, contributes to file-level statistics (line count,
  score histogram) that are written next to the sample.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import urllib.request
import zlib
from collections import Counter
from pathlib import Path


class SourceChecksumMismatch(RuntimeError):
    pass


def selected(lineno: int, seed: int, rate: float) -> bool:
    h = hashlib.blake2b(f"{seed}:{lineno}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") < rate * 2.0 ** 64


def _chunks(url: str, chunk_size: int = 1 << 22):
    req = urllib.request.Request(url, headers={"User-Agent": "asal-data/0.2"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        while True:
            block = resp.read(chunk_size)
            if not block:
                return
            yield block


def hash_line_sample(url: str, out_path: Path, seed: int, rate: float, expected_md5_b64: str | None = None,
                     score_column: int | None = None, chunks=None) -> dict:
    """Stream ``url`` (gzip), write kept lines as gzip TSV ``<lineno>\\t<line>``; return stats."""
    md5 = hashlib.md5()
    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buf = b""
    lineno = kept = 0
    score_hist: Counter = Counter()
    tmp = out_path.with_suffix(out_path.suffix + ".part")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def handle(line: bytes, out) -> None:
        nonlocal lineno, kept
        if score_column is not None:
            parts = line.split(b"\t", score_column + 1)
            try:
                score_hist[f"{float(parts[score_column]):.2f}"] += 1
            except (IndexError, ValueError):
                score_hist["unparsable"] += 1
        if selected(lineno, seed, rate):
            out.write(str(lineno).encode() + b"\t" + line + b"\n")
            kept += 1
        lineno += 1

    # mtime=0 keeps the gzip header, and so the output's SHA-256, deterministic.
    with tmp.open("wb") as raw_out, gzip.GzipFile(fileobj=raw_out, mode="wb", mtime=0) as out:
        for block in (chunks if chunks is not None else _chunks(url)):
            md5.update(block)
            buf += dec.decompress(block)
            *lines, buf = buf.split(b"\n")
            for line in lines:
                handle(line, out)
        buf += dec.flush()
        if buf:
            handle(buf, out)

    md5_b64 = base64.b64encode(md5.digest()).decode()
    if expected_md5_b64 and md5_b64 != expected_md5_b64:
        tmp.unlink()
        raise SourceChecksumMismatch(f"{url}: expected md5 {expected_md5_b64}, got {md5_b64}")
    tmp.replace(out_path)
    stats = {"source_url": url, "source_md5_base64": md5_b64, "lines": lineno, "kept": kept, "seed": seed,
             "rate": rate, "score_histogram": dict(sorted(score_hist.items()))}
    out_path.with_name(out_path.name + ".stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    return stats
