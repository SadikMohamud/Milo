"""Document-level heuristic flags: suspected machine translation and religious content.

Both are *heuristics for review*, not classifiers. They never reject a record;
they set a flag and a ``basis`` so that the share of affected text is visible
and a native-speaker review can measure their precision.

Machine translation (URL heuristic)
    Many sites publish automatic translations under a language subdomain such
    as ``so.example.com`` or a path such as ``example.com/so/``. A Somali page on
    a non-Somali domain served that way is *suspected* MT. Somali-registered
    domains (.so) and known Somali-language publishers are not flagged by this rule.

Religious content (lexicon heuristic)
    Counts tokens from a small lexicon of Islamic and Christian religious terms
    in Somali. Religious text must be tracked as its own domain (build spec §3),
    and aggregates such as NLLB contain Quran and Bible translations that are
    not labelled as such.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .textutil import words

MT_SUSPECTED = "suspected"

_LANG_SUBDOMAIN_RE = re.compile(r"^(so|som)\.")
_LANG_PATH_RE = re.compile(r"^/(so|som|so-so)(/|$)", re.IGNORECASE)
SOMALI_TLDS = (".so",)


def url_host(url: str | None) -> str | None:
    if not url or "://" not in url:
        return None
    return urlparse(url).hostname


def mt_suspect_from_url(url: str | None) -> str | None:
    """Return a reason string if the URL pattern suggests auto-translation, else None."""
    if not url or "://" not in url:
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host or host.endswith(SOMALI_TLDS):
        return None
    if _LANG_SUBDOMAIN_RE.match(host) and host.count(".") >= 2:
        return "language_subdomain"
    if _LANG_PATH_RE.match(parsed.path or ""):
        return "language_path"
    return None


RELIGION_LEXICON = frozenset(
    """
    allah allaah ilaah ilaahay ilaaha ilaahey eebe eebbe eebbaha rabbi rabbiga rabbigaa rabbigiin rabbigood
    nabi nabiga nebi nebiga nabiyada nebiyada rasuul rasuulka rasuulkii rasuulladii quraan quraanka qur'aan
    qur'aanka aayad aayadda aayadaha suurad suuradda masjid masjidka salaad salaadda sujuud cibaado cibaadada
    jannada janno jahannamo naarta shaydaan shaydaanka malaa'ig malaa'igta malaa'igtii kitaab kitaabka
    injiil injiilka tawreed tawreedka zabuur ciise masiix masiixa ciisaha yeesuus kaniisad kaniisadda
    rumeeyay rumaysan mu'miniin mu'miniinta gaalada xaaraan xalaal sallallaahu calayhi wasallam
    """.split()
)


def religion_score(text: str) -> tuple[float, int]:
    toks = [w.casefold() for w in words(text)]
    if not toks:
        return 0.0, 0
    hits = sum(1 for w in toks if w in RELIGION_LEXICON)
    return hits / len(toks), hits


def is_religious(text: str, min_ratio: float = 0.05, min_hits: int = 1) -> bool:
    ratio, hits = religion_score(text)
    return hits >= min_hits and ratio >= min_ratio
