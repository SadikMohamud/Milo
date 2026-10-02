"""Download every file in a manifest, verifying SHA-256. Idempotent.

Usage: python scripts/data/download_sample.py [data/manifests/sample-v0.1.yaml ...]
"""
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from asal import download, paths


def main(argv: list[str]) -> int:
    manifests = [Path(a) for a in argv] or [paths.MANIFESTS / "sample-v0.1.yaml", paths.MANIFESTS / "lid-eval-v0.1.yaml"]
    for m in manifests:
        results = download.fetch_manifest(m, log_path=paths.RAW / "access_log.jsonl")
        for r in results:
            state = "downloaded" if r.downloaded else "verified (cached)"
            print(f"{state:18} {r.bytes:>9} B  {r.sha256[:12]}  {r.path.relative_to(paths.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
