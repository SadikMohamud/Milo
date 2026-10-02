"""Document-level quality checks with explicit reason codes.

Every check is a plain heuristic with a documented threshold. Thresholds are
starting points, not tuned values: they must be re-checked against native-speaker
review of rejected samples (docs/DATA_PIPELINE.md, "Manual sampling").
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from .textutil import words

# Reason codes (stable identifiers, used in rejected-record logs).
TOO_SHORT = "too_short"
TOO_LONG = "too_long"
HTML_MARKUP = "html_markup"
URL_HEAVY = "url_heavy"
EXCESSIVE_PUNCTUATION = "excessive_punctuation"
MOJIBAKE = "mojibake"
REPLACEMENT_CHARACTER = "replacement_character"
REPEATED_LINES = "repeated_lines"
LOW_INFORMATION = "low_information"
LOW_ALPHA_RATIO = "low_alpha_ratio"

DEFAULT_THRESHOLDS = {
    "min_words": 5,
    "max_chars": 200_000,
    "max_html_tags": 2,
    "max_url_char_ratio": 0.2,
    "max_punct_ratio": 0.25,
    "max_duplicate_line_ratio": 0.3,
    "min_unique_word_ratio": 0.2,  # applied only to docs with >= 50 words
    "min_alpha_ratio": 0.6,
}

HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^<>]{0,200})?/?>")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# UTF-8 bytes decoded as Latin-1/CP1252: "Ã©", "â€™", "Â " ...
MOJIBAKE_RE = re.compile("\u00c3[\u0080-\u00bf]|\u00e2\u20ac|\u00c2[\u00a0-\u00bf]")


@dataclass
class QualityResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def check(text: str, thresholds: dict | None = None) -> QualityResult:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    reasons: list[str] = []
    toks = words(text)
    non_space = [c for c in text if not c.isspace()]
    n_non_space = max(len(non_space), 1)

    alpha = sum(1 for c in non_space if c.isalpha())
    punct = sum(1 for c in non_space if unicodedata.category(c).startswith("P"))
    url_chars = sum(len(m) for m in URL_RE.findall(text))
    html_tags = len(HTML_TAG_RE.findall(text))
    mojibake = len(MOJIBAKE_RE.findall(text))

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    dup_line_ratio = 0.0
    if len(lines) >= 3:
        counts = Counter(lines)
        dup_line_ratio = sum(c - 1 for c in counts.values()) / len(lines)

    lower = [w.casefold() for w in toks]
    unique_ratio = len(set(lower)) / len(lower) if lower else 0.0

    metrics = {
        "chars": len(text),
        "words": len(toks),
        "alpha_ratio": round(alpha / n_non_space, 4),
        "punct_ratio": round(punct / n_non_space, 4),
        "url_char_ratio": round(url_chars / max(len(text), 1), 4),
        "html_tags": html_tags,
        "mojibake_hits": mojibake,
        "duplicate_line_ratio": round(dup_line_ratio, 4),
        "unique_word_ratio": round(unique_ratio, 4),
    }

    if len(toks) < t["min_words"]:
        reasons.append(TOO_SHORT)
    if len(text) > t["max_chars"]:
        reasons.append(TOO_LONG)
    if html_tags > t["max_html_tags"]:
        reasons.append(HTML_MARKUP)
    if metrics["url_char_ratio"] > t["max_url_char_ratio"]:
        reasons.append(URL_HEAVY)
    if metrics["punct_ratio"] > t["max_punct_ratio"]:
        reasons.append(EXCESSIVE_PUNCTUATION)
    if mojibake:
        reasons.append(MOJIBAKE)
    if "�" in text:
        reasons.append(REPLACEMENT_CHARACTER)
    if dup_line_ratio > t["max_duplicate_line_ratio"]:
        reasons.append(REPEATED_LINES)
    if len(lower) >= 50 and unique_ratio < t["min_unique_word_ratio"]:
        reasons.append(LOW_INFORMATION)
    if metrics["alpha_ratio"] < t["min_alpha_ratio"]:
        reasons.append(LOW_ALPHA_RATIO)

    return QualityResult(passed=not reasons, reasons=reasons, metrics=metrics)
