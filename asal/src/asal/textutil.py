"""Small text helpers shared by several pipeline stages."""

import hashlib
import re
import unicodedata

# Somali words: letters plus the apostrophe, which marks the glottal stop
# (e.g. "ba'an", "su'aal", "ta'siis"). It is part of the word, never a separator.
WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*'?", re.UNICODE)


def words(text: str) -> list[str]:
    """Word tokens, apostrophes kept inside words. Case preserved."""
    return WORD_RE.findall(text)


def dedup_key(text: str) -> str:
    """Canonical form for exact deduplication: casefolded, whitespace-collapsed."""
    return " ".join(text.casefold().split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(text: str) -> str:
    """Stable hash of the dedup-canonical form of a text."""
    return sha256_text(dedup_key(text))


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
