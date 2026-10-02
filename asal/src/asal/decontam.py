"""Evaluation decontamination by word n-gram overlap.

Every registered evaluation item is indexed as word n-grams (casefolded,
punctuation-free word tokens). A training record is *contaminated* when it
shares at least ``min_matches`` n-grams with any evaluation item. Evaluation
items shorter than n words are indexed as a single n-gram of their full length,
so short items (e.g. single FLORES / SIB-200 sentences) are still caught when a
training document contains them verbatim. Items with fewer than
``min_item_words`` words are not indexed (they would match ordinary phrases);
they are counted in ``skipped_items`` and reported.

n = 13 follows common practice for long documents; Asal also reports n = 8
because Somali evaluation items are often single sentences.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .textutil import words

CONTAMINATED = "eval_contamination"


def _tokens(text: str) -> list[str]:
    return [w.casefold() for w in words(text)]


def _ngrams(toks: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


@dataclass
class OverlapResult:
    contaminated: bool
    matched_ngrams: int
    ngram_overlap_ratio: float
    eval_hits: list[str] = field(default_factory=list)  # "eval_set:item_id"


class EvalIndex:
    def __init__(self, n: int = 13, min_matches: int = 1, min_item_words: int = 6):
        self.n = n
        self.min_matches = min_matches
        self.min_item_words = min_item_words
        self.skipped_items: Counter = Counter()
        self._index: dict[tuple[str, ...], set[str]] = defaultdict(set)
        self._short_lengths: set[int] = set()
        self.items_by_set: Counter = Counter()

    def add(self, eval_set: str, item_id: str, text: str) -> None:
        toks = _tokens(text)
        if len(toks) < self.min_item_words:
            self.skipped_items[eval_set] += 1
            return
        key = f"{eval_set}:{item_id}"
        self.items_by_set[eval_set] += 1
        if len(toks) < self.n:
            self._short_lengths.add(len(toks))
            self._index[tuple(toks)].add(key)
        else:
            for g in _ngrams(toks, self.n):
                self._index[g].add(key)

    def check(self, text: str) -> OverlapResult:
        toks = _tokens(text)
        grams = _ngrams(toks, self.n)
        matched = [g for g in grams if g in self._index]
        hits: set[str] = set()
        for g in matched:
            hits |= self._index[g]
        short_matches = 0
        for length in self._short_lengths:
            for g in _ngrams(toks, length):
                if g in self._index:
                    short_matches += 1
                    hits |= self._index[g]
        total = len(matched) + short_matches
        return OverlapResult(
            contaminated=total >= self.min_matches,
            matched_ngrams=total,
            ngram_overlap_ratio=round(len(matched) / len(grams), 4) if grams else 0.0,
            eval_hits=sorted(hits),
        )


def scan(records: list[dict], index: EvalIndex) -> tuple[list[dict], list[dict], dict]:
    """Split records into (clean, contaminated) and summarise per evaluation set."""
    clean, contaminated = [], []
    per_set_docs: Counter = Counter()
    per_set_items: dict[str, set] = defaultdict(set)
    for rec in records:
        res = index.check(rec["text"])
        if res.contaminated:
            sets = {h.split(":", 1)[0] for h in res.eval_hits}
            for s in sets:
                per_set_docs[s] += 1
            for h in res.eval_hits:
                per_set_items[h.split(":", 1)[0]].add(h)
            contaminated.append({**rec, "reason": CONTAMINATED, "matched_ngrams": res.matched_ngrams,
                                 "eval_hits": res.eval_hits[:50]})
        else:
            clean.append(rec)
    hist: Counter = Counter()
    for r in contaminated:
        m = r["matched_ngrams"]
        hist["1" if m == 1 else "2-4" if m < 5 else "5-19" if m < 20 else "20+"] += 1
    summary = {
        "n": index.n,
        "contaminated_by_matched_ngrams": {k: hist.get(k, 0) for k in ("1", "2-4", "5-19", "20+")},
        "min_matches": index.min_matches,
        "training_records_checked": len(records),
        "training_records_contaminated": len(contaminated),
        "per_eval_set": {
            s: {
                "eval_items_indexed": index.items_by_set[s],
                "eval_items_skipped_too_short": index.skipped_items.get(s, 0),
                "training_records_overlapping": per_set_docs.get(s, 0),
                "eval_items_found_in_training": len(per_set_items.get(s, ())),
            }
            for s in sorted(set(index.items_by_set) | set(index.skipped_items))
        },
    }
    return clean, contaminated, summary
