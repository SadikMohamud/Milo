"""Dataset statistics. Pure counts; no text content is written except word frequencies."""

from __future__ import annotations

import statistics
from collections import Counter

from .textutil import words


def _pct(values: list[int], q: float) -> float:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def corpus_stats(records: list[dict], top_k: int = 30) -> dict:
    word_counts = []
    char_counts = []
    byte_counts = []
    vocab: Counter = Counter()
    chars: Counter = Counter()
    apostrophe_words = 0
    total_words = 0
    for r in records:
        toks = words(r["text"])
        word_counts.append(len(toks))
        char_counts.append(len(r["text"]))
        byte_counts.append(len(r["text"].encode("utf-8")))
        total_words += len(toks)
        apostrophe_words += sum(1 for w in toks if "'" in w)
        vocab.update(w.casefold() for w in toks)
        chars.update(r["text"])
    non_ascii = {c: n for c, n in chars.items() if ord(c) > 127}
    return {
        "documents": len(records),
        "words": total_words,
        "characters": sum(char_counts),
        "bytes_utf8": sum(byte_counts),
        "words_per_doc": {
            "mean": round(statistics.mean(word_counts), 1) if word_counts else 0,
            "median": statistics.median(word_counts) if word_counts else 0,
            "p05": _pct(word_counts, 0.05),
            "p95": _pct(word_counts, 0.95),
            "max": max(word_counts, default=0),
        },
        "vocabulary_size_casefolded": len(vocab),
        "type_token_ratio": round(len(vocab) / total_words, 4) if total_words else 0,
        "words_with_apostrophe_per_1k": round(1000 * apostrophe_words / total_words, 2) if total_words else 0,
        "distinct_characters": len(chars),
        "non_ascii_characters": dict(sorted(non_ascii.items(), key=lambda kv: -kv[1])[:40]),
        "top_words": vocab.most_common(top_k),
    }


def by_key(records: list[dict], key) -> dict[str, dict]:
    groups: dict[str, list] = {}
    for r in records:
        groups.setdefault(key(r), []).append(r)
    return {k: corpus_stats(v, top_k=10) for k, v in sorted(groups.items())}
