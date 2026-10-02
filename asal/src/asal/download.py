"""Reproducible, manifest-driven downloads.

A manifest (data/manifests/*.yaml) pins every file by URL (including an
immutable upstream revision where the host supports one), byte size and
SHA-256. ``fetch`` refuses to accept a file whose hash differs from the
manifest, so a changed upstream is detected instead of silently ingested.
An entry may set ``byte_range: [start, end]`` (inclusive) to pin a prefix of a
large object; the hash then covers exactly those bytes.
Downloads land under data/raw/, which is never committed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import paths


class ChecksumMismatch(RuntimeError):
    pass


@dataclass
class FetchResult:
    path: Path
    sha256: str
    bytes: int
    downloaded: bool  # False when an already-present file was verified and reused


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def fetch(entry: dict, raw_dir: Path = paths.RAW, timeout: int = 60) -> FetchResult:
    dest = raw_dir / entry["path"]
    expected = entry.get("sha256")
    if dest.exists() and expected and sha256_file(dest) == expected:
        return FetchResult(dest, expected, dest.stat().st_size, downloaded=False)

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": "asal-data/0.1"}
    if entry.get("byte_range"):
        start, end = entry["byte_range"]
        headers["Range"] = f"bytes={start}-{end}"
    req = urllib.request.Request(entry["url"], headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as out:
        if entry.get("byte_range") and getattr(resp, "status", None) != 206:
            # Server (or file:// URL) ignored the Range header: cut the range out locally.
            start, end = entry["byte_range"]
            resp.read(start)
            out.write(resp.read(end - start + 1))
        else:
            shutil.copyfileobj(resp, out)
    digest = sha256_file(tmp)
    if expected and digest != expected:
        tmp.unlink()
        raise ChecksumMismatch(f"{entry['url']}: expected sha256 {expected}, got {digest}")
    tmp.replace(dest)
    return FetchResult(dest, digest, dest.stat().st_size, downloaded=True)


def fetch_manifest(manifest_path: Path, raw_dir: Path = paths.RAW, log_path: Path | None = None) -> list[FetchResult]:
    manifest = load_manifest(manifest_path)
    results = []
    for entry in manifest["files"]:
        res = fetch(entry, raw_dir)
        results.append(res)
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "manifest": manifest["manifest_id"], "source_id": entry["source_id"],
                    "url": entry["url"], "sha256": res.sha256, "bytes": res.bytes,
                    "downloaded": res.downloaded,
                }) + "\n")
    return results
