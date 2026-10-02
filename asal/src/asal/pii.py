"""PII detection and redaction.

v0.1 covers e-mail addresses and phone numbers (international format and
Somali mobile numbers). PII is redacted with a typed placeholder rather than the
document being rejected, and the number of redactions is recorded on the record.

Known gaps (logged in docs/DATA_POLICY.md): personal names, street addresses,
national ID numbers and account numbers are not detected. Somali personal names
are also common words and place names, so name redaction needs a dedicated,
evaluated approach rather than a regex.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# +252 61 234 5678, 00252612345678, +44 20 7946 0000 ... (9+ digits)
INTL_PHONE_RE = re.compile(r"(?<![\w+])(?:\+|00)\d(?:[\s\-().]?\d){8,14}\b")
# Somali mobile numbers written locally: 061 234 5678, 0612345678, 61-234-5678
SO_LOCAL_PHONE_RE = re.compile(r"(?<![\w+])0?6[1-9](?:[\s\-]?\d){7}\b")

PLACEHOLDERS = {"email": "<EMAIL>", "phone": "<PHONE>"}


@dataclass
class PIIResult:
    text: str
    redactions: Counter = field(default_factory=Counter)


def redact(text: str) -> PIIResult:
    counts: Counter = Counter()

    def sub(pattern: re.Pattern, kind: str, s: str) -> str:
        def repl(_m):
            counts[kind] += 1
            return PLACEHOLDERS[kind]

        return pattern.sub(repl, s)

    text = sub(EMAIL_RE, "email", text)
    text = sub(INTL_PHONE_RE, "phone", text)
    text = sub(SO_LOCAL_PHONE_RE, "phone", text)
    return PIIResult(text=text, redactions=counts)
