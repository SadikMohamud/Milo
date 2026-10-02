"""Somali-aware text normalisation.

Design rules (see docs/DATA_PIPELINE.md, "Normalisation"):

* Unicode is normalised to NFC.
* The apostrophe marks the glottal stop in Somali orthography ("ba'an", "lo'",
  "su'aal"). It is never stripped. Its typographic variants (U+2019, U+02BC, ...)
  are mapped to the ASCII apostrophe U+0027, which is what most Somali text
  already uses, so that "ba'an" and "ba’an" become the same word.
* Curly double quotes are mapped to ASCII double quotes.
* Zero-width characters, soft hyphens and control characters (except newline
  and tab) are removed.
* Whitespace is collapsed per line; runs of 3+ newlines become 2 (paragraphs
  are kept).
* Case, diacritics and punctuation other than the above are left untouched.

Normalisation does not repair mojibake. Mojibake is detected by the quality
filter and rejected with a reason code, because "repairs" can silently
corrupt text.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

# Typographic apostrophes and look-alikes seen in Somali web text.
APOSTROPHE_VARIANTS = {
    "\u2019": "right single quotation mark",
    "\u2018": "left single quotation mark",
    "\u02bc": "modifier letter apostrophe",
    "\u02bb": "modifier letter turned comma",
    "`": "grave accent",
    "\u00b4": "acute accent",
    "\u2032": "prime",
    "\uff07": "fullwidth apostrophe",
}
DOUBLE_QUOTE_VARIANTS = {"\u201c", "\u201d", "\u201e", "\u201f", "\u00ab", "\u00bb"}
ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad"}

_SPACES_RE = re.compile(r"[ \t\u00a0\u2000-\u200a\u202f\u205f\u3000]+")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")


@dataclass
class NormalisationResult:
    text: str
    changes: Counter = field(default_factory=Counter)


def _is_removable_control(ch: str) -> bool:
    if ch in ("\n", "\t"):
        return False
    return unicodedata.category(ch) in ("Cc", "Cf") or ch in ZERO_WIDTH


def normalise(text: str) -> NormalisationResult:
    changes: Counter = Counter()

    nfc = unicodedata.normalize("NFC", text)
    if nfc != text:
        changes["nfc"] += 1
    text = nfc.replace("\r\n", "\n").replace("\r", "\n")

    out = []
    for ch in text:
        if ch in APOSTROPHE_VARIANTS:
            out.append("'")
            changes["apostrophe_variant"] += 1
        elif ch in DOUBLE_QUOTE_VARIANTS:
            out.append('"')
            changes["double_quote_variant"] += 1
        elif _is_removable_control(ch):
            changes["control_or_zero_width"] += 1
        else:
            out.append(ch)
    text = "".join(out)

    lines = []
    for line in text.split("\n"):
        collapsed = _SPACES_RE.sub(" ", line).strip()
        if collapsed != line:
            changes["whitespace"] += 1
        lines.append(collapsed)
    text = "\n".join(lines)
    text = _MANY_NEWLINES_RE.sub("\n\n", text).strip()

    return NormalisationResult(text=text, changes=changes)
