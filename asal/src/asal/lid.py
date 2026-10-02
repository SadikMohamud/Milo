"""Language identification (LID) with interchangeable backends.

Labels are ISO 639-3 codes: "som" (Somali), "ymm" (Maay), "eng", ... and
"und" when a backend cannot decide.

Backends
--------
* ``asal-heuristic``: Asal's own transparent baseline. Scores the share of
  tokens that are high-frequency Somali function words against high-frequency
  English function words, plus a Somali orthography signal (long vowels and
  the letters c/x/q/dh/kh). It is a *binary* Somali detector (som / eng / und);
  it cannot tell Swahili from Hausa. Its word lists were written from general
  knowledge of Somali, not fitted to any evaluation set.
* ``lingua``: lingua-language-detector (offline, 75 languages incl. Somali; no
  Maay, no Oromo, no Amharic).
* ``fasttext-lid176``: fastText lid.176 (label ``__label__so``). Needs the model
  file; not bundled.
* ``glotlid``: GlotLID fastText model (labels like ``__label__som_Latn``,
  ``__label__ymm_Latn``). Needs the model file; not bundled.

Every backend returns an ``LIDPrediction`` so results can be compared on the
same items (scripts/evaluation/compare_lid.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .textutil import words

SOMALI = "som"
MAAY = "ymm"
UNDETERMINED = "und"


@dataclass
class LIDPrediction:
    label: str
    somali_score: float  # backend-specific confidence that the text is Somali, in [0, 1]
    backend: str


class LIDBackend(Protocol):
    name: str

    def predict(self, text: str) -> LIDPrediction: ...


# --- Asal heuristic baseline -------------------------------------------------

SOMALI_FUNCTION_WORDS = frozenset(
    """
    waa iyo ayaa ka ku u la oo ah ee uu ay aan aad ayuu ayay ayaan waxaa waxay wuxuu
    waxaan waxa wax si sida soo laga lagu loo kala kaga kula kaso kusoo ugu iska isku
    kale kasta dhan badan haddii hadda markii kadib kaddib laakiin balse sidoo weli
    mid qof dadka dalka ama mise inuu inay inaan inaad yahay tahay yihiin ahaa ahayd
    ahaayeen jira jiray jirta jiro ilaa illaa xitaa sababtoo sababta tan kan kuwa kuwaas
    taas kaas halkaas halkan intii inta ayey waxuu iyada isaga iyaga anaga idinka adiga
    aniga wuxuuna waxayna ayaana iyadoo isagoo iyagoo hase haseyeeshee
    """.split()
)

ENGLISH_FUNCTION_WORDS = frozenset(
    """
    the of and to is in that it for was on are with as by this be at from have or an
    which were has had not but they their his her he she its been will would can there
    what when who all also more one into than other some these then them may such
    """.split()
)

SOMALI_ORTHOGRAPHY_MARKERS = ("aa", "ee", "ii", "oo", "uu", "dh", "kh", "sh", "x", "c", "q")


class AsalHeuristicLID:
    name = "asal-heuristic"

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def score(self, text: str) -> float:
        toks = [w.casefold() for w in words(text)]
        if not toks:
            return 0.0
        so = sum(1 for w in toks if w in SOMALI_FUNCTION_WORDS) / len(toks)
        en = sum(1 for w in toks if w in ENGLISH_FUNCTION_WORDS) / len(toks)
        letters = "".join(toks)
        ortho = sum(letters.count(b) for b in SOMALI_ORTHOGRAPHY_MARKERS) / max(len(letters), 1)
        # Typical Somali prose: function-word share ~0.25-0.45, orthography signal ~0.15-0.3.
        raw = 2.0 * so + 1.0 * min(ortho, 0.3) - 2.5 * en
        return max(0.0, min(1.0, raw / 0.8))

    def predict(self, text: str) -> LIDPrediction:
        s = self.score(text)
        toks = [w.casefold() for w in words(text)]
        en = sum(1 for w in toks if w in ENGLISH_FUNCTION_WORDS) / max(len(toks), 1)
        if s >= self.threshold:
            label = SOMALI
        elif en >= 0.15:
            label = "eng"
        else:
            label = UNDETERMINED
        return LIDPrediction(label=label, somali_score=round(s, 4), backend=self.name)


# --- Lingua ------------------------------------------------------------------

class LinguaLID:
    name = "lingua"

    def __init__(self):
        from lingua import IsoCode639_3, Language, LanguageDetectorBuilder  # optional dependency

        self._Language = Language
        self._iso3 = IsoCode639_3
        self._detector = LanguageDetectorBuilder.from_all_languages().build()

    def predict(self, text: str) -> LIDPrediction:
        lang = self._detector.detect_language_of(text)
        score = self._detector.compute_language_confidence(text, self._Language.SOMALI)
        label = lang.iso_code_639_3.name.lower() if lang is not None else UNDETERMINED
        return LIDPrediction(label=label, somali_score=round(float(score), 4), backend=self.name)


# --- Ensemble ------------------------------------------------------------------

class EnsembleLID:
    """Somali if the heuristic is confident, or if Lingua says Somali and the
    heuristic gives at least weak Somali evidence (``low_threshold``).

    Motivation (v0.2): the heuristic alone rejects many short Somali web
    sentences; Lingua alone labels most Oromo as Somali. ``low_threshold`` is
    tuned on SIB-200 *dev* splits (scripts/evaluation/compare_lid.py --tune)
    and reported on test splits.
    """

    name = "asal-ensemble"

    def __init__(self, heuristic: AsalHeuristicLID | None = None, lingua: "LinguaLID | None" = None,
                 low_threshold: float = 0.2):
        self.heuristic = heuristic or AsalHeuristicLID()
        self.lingua = lingua or LinguaLID()
        self.low_threshold = low_threshold

    def predict(self, text: str) -> LIDPrediction:
        h = self.heuristic.score(text)
        lp = self.lingua.predict(text)
        if h >= self.heuristic.threshold or (lp.label == SOMALI and h >= self.low_threshold):
            label = SOMALI
        else:
            label = lp.label if lp.label != SOMALI else UNDETERMINED
        return LIDPrediction(label=label, somali_score=round(max(h, lp.somali_score if label == SOMALI else h), 4),
                             backend=self.name)


# --- fastText-format models (lid.176, GlotLID) --------------------------------

class FastTextLID:
    """Wraps a fastText LID model. ``label_map`` maps raw labels to ISO 639-3."""

    def __init__(self, name: str, model_path: str | Path, label_map: dict[str, str], somali_labels: set[str]):
        import fasttext  # optional dependency

        if not Path(model_path).exists():
            raise FileNotFoundError(f"{name}: model file not found at {model_path}")
        self.name = name
        self._model = fasttext.load_model(str(model_path))
        self._label_map = label_map
        self._somali_labels = somali_labels

    def _map(self, raw: str) -> str:
        raw = raw.replace("__label__", "")
        if raw in self._label_map:
            return self._label_map[raw]
        return raw.split("_")[0]  # GlotLID: "som_Latn" -> "som"

    def predict(self, text: str) -> LIDPrediction:
        labels, probs = self._model.predict(text.replace("\n", " "), k=5)
        top = self._map(labels[0])
        som = sum(float(p) for lab, p in zip(labels, probs) if lab.replace("__label__", "") in self._somali_labels)
        return LIDPrediction(label=top, somali_score=round(som, 4), backend=self.name)


def fasttext_lid176(model_path: str | Path) -> FastTextLID:
    # lid.176 uses ISO 639-1 codes; map the ones relevant to Somali evaluation.
    label_map = {"so": SOMALI, "en": "eng", "sw": "swh", "ar": "arb", "am": "amh", "om": "gaz",
                 "ha": "hau", "yo": "yor", "af": "afr", "id": "ind", "ti": "tir"}
    return FastTextLID("fasttext-lid176", model_path, label_map, somali_labels={"so"})


def glotlid(model_path: str | Path) -> FastTextLID:
    return FastTextLID("glotlid", model_path, label_map={}, somali_labels={"som_Latn"})


# --- segment-level LID (code-switching) ----------------------------------------

import re as _re

_SEGMENT_RE = _re.compile(r"(?<=[.!?\n])\s+")


def segment_lid(text: str, backend=None, min_words: int = 4) -> dict:
    """Label each sentence-like segment and summarise.

    Segments shorter than ``min_words`` are not labelled (LID is unreliable on
    them). ``code_switched`` is True when at least one segment is Somali and at
    least one is labelled a different, determined language. Intra-sentence
    switching is not detected by this function.
    """
    backend = backend or AsalHeuristicLID()
    counts: dict[str, int] = {}
    for seg in _SEGMENT_RE.split(text):
        if len(words(seg)) < min_words:
            continue
        label = backend.predict(seg).label
        counts[label] = counts.get(label, 0) + 1
    other = {k for k in counts if k not in (SOMALI, UNDETERMINED)}
    return {"segments": counts, "code_switched": SOMALI in counts and bool(other)}


def available_backends(fasttext_model: str | None = None, glotlid_model: str | None = None) -> list:
    """Instantiate every backend that can run in this environment."""
    backends: list = [AsalHeuristicLID()]
    try:
        backends.append(LinguaLID())
    except ImportError:
        pass
    for factory, path in ((fasttext_lid176, fasttext_model), (glotlid, glotlid_model)):
        if path:
            try:
                backends.append(factory(path))
            except (ImportError, FileNotFoundError):
                pass
    return backends
