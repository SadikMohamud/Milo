"""Exact and near deduplication, within and across sources.

Records are processed in a deterministic order (source priority, then source
record id). The first occurrence is kept; later ones are removed with a reason
code and a pointer to the record they duplicate. Every removal is labelled
``within_source`` or ``cross_source`` so aggregation overlap (e.g. a corpus
that re-packages CC100 and mC4) is measured, not assumed.

Near duplicates use MinHash over word 5-shingles with LSH banding; candidate
pairs are confirmed with the exact Jaccard similarity of their shingle sets.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

from .textutil import content_hash, words

EXACT_DUPLICATE = "exact_duplicate"
NEAR_DUPLICATE = "near_duplicate"

_PRIME = (1 << 31) - 1  # a*h < 2**62, so the universal hash never overflows uint64


@dataclass
class DedupResult:
    kept: list[dict]
    removed: list[dict]  # each has "reason", "duplicate_of", "scope" (and "jaccard" for near)
    stats: dict = field(default_factory=dict)


def _scope(a: dict, b: dict) -> str:
    return "within_source" if a["source"] == b["source"] else "cross_source"


def _summarise(kept: list[dict], removed: list[dict], reason: str) -> dict:
    by_scope = Counter(r["scope"] for r in removed)
    pairs = Counter(f'{r["source"]}->{r["duplicate_of_source"]}' for r in removed)
    return {
        "input": len(kept) + len(removed),
        "kept": len(kept),
        "removed": len(removed),
        "reason": reason,
        "removed_within_source": by_scope.get("within_source", 0),
        "removed_cross_source": by_scope.get("cross_source", 0),
        "removed_by_source_pair": dict(sorted(pairs.items())),
    }


def exact_dedup(records: list[dict]) -> DedupResult:
    seen: dict[str, dict] = {}
    kept, removed = [], []
    for rec in records:
        h = rec.get("content_hash") or content_hash(rec["text"])
        rec["content_hash"] = h
        if h in seen:
            first = seen[h]
            removed.append({**rec, "reason": EXACT_DUPLICATE, "duplicate_of": first["id"],
                            "duplicate_of_source": first["source"], "scope": _scope(rec, first)})
        else:
            seen[h] = rec
            kept.append(rec)
    return DedupResult(kept, removed, _summarise(kept, removed, EXACT_DUPLICATE))


def shingles(text: str, k: int = 5) -> set[str]:
    toks = [w.casefold() for w in words(text)]
    if len(toks) < k:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)}


def _hash64(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "little")


class MinHasher:
    def __init__(self, num_perm: int = 128, seed: int = 1):
        rng = np.random.default_rng(seed)
        self.num_perm = num_perm
        self.a = rng.integers(1, _PRIME, size=num_perm, dtype=np.uint64)[:, None]
        self.b = rng.integers(0, _PRIME, size=num_perm, dtype=np.uint64)[:, None]

    def signature(self, shingle_set: set[str]) -> np.ndarray:
        if not shingle_set:
            return np.full(self.num_perm, np.iinfo(np.uint64).max, dtype=np.uint64)
        hs = np.array([_hash64(s) % _PRIME for s in shingle_set], dtype=np.uint64)
        return ((self.a * hs + self.b) % np.uint64(_PRIME)).min(axis=1)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def near_dedup(records: list[dict], threshold: float = 0.8, num_perm: int = 128, bands: int = 32,
               shingle_size: int = 5, seed: int = 1) -> DedupResult:
    """Remove records whose shingle-set Jaccard with an earlier kept record is >= threshold.

    With 32 bands x 4 rows the LSH candidate curve is ~50% at Jaccard 0.42 and
    >99.99% at 0.8, so true pairs above the threshold are almost never missed;
    every candidate is then confirmed with the exact Jaccard.
    """
    assert num_perm % bands == 0
    rows = num_perm // bands
    hasher = MinHasher(num_perm, seed)
    buckets: list[dict] = [defaultdict(list) for _ in range(bands)]
    kept, removed = [], []
    kept_shingles: list[set] = []

    for rec in records:
        sh = shingles(rec["text"], shingle_size)
        sig = hasher.signature(sh)
        keys = [sig[i * rows:(i + 1) * rows].tobytes() for i in range(bands)]
        candidates = {idx for i, key in enumerate(keys) for idx in buckets[i].get(key, ())}
        best, best_j = None, 0.0
        for idx in sorted(candidates):
            j = jaccard(sh, kept_shingles[idx])
            if j >= threshold and j > best_j:
                best, best_j = idx, j
        if best is not None:
            first = kept[best]
            removed.append({**rec, "reason": NEAR_DUPLICATE, "duplicate_of": first["id"],
                            "duplicate_of_source": first["source"], "scope": _scope(rec, first),
                            "jaccard": round(best_j, 4)})
            continue
        idx = len(kept)
        kept.append(rec)
        kept_shingles.append(sh)
        for i, key in enumerate(keys):
            buckets[i][key].append(idx)

    stats = _summarise(kept, removed, NEAR_DUPLICATE)
    stats.update({"threshold": threshold, "num_perm": num_perm, "bands": bands, "shingle_size": shingle_size})
    return DedupResult(kept, removed, stats)
