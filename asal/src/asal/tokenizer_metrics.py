"""Tokenizer evaluation metrics (docs/TOKENIZER.md).

A tokenizer is evaluated through two callables, so any implementation
(HF tokenizers, SentencePiece, a base model's tokenizer) can be plugged in:

  encode(text) -> list[int | str]   token sequence
  decode(tokens) -> str             inverse (optional; needed for round trip)

Metrics are computed on a held-out Somali set that the tokenizer never saw.
"""

from __future__ import annotations

from typing import Callable, Sequence

from .textutil import words


def fertility(encode: Callable, texts: Sequence[str]) -> float:
    """Tokens per word (word = Asal word tokenizer, apostrophes kept inside words)."""
    n_tok = sum(len(encode(t)) for t in texts)
    n_words = sum(len(words(t)) for t in texts)
    return n_tok / n_words if n_words else float("nan")


def bytes_per_token(encode: Callable, texts: Sequence[str]) -> float:
    n_tok = sum(len(encode(t)) for t in texts)
    n_bytes = sum(len(t.encode("utf-8")) for t in texts)
    return n_bytes / n_tok if n_tok else float("nan")


def roundtrip_fidelity(encode: Callable, decode: Callable, texts: Sequence[str]) -> float:
    """Share of texts reproduced exactly by decode(encode(text))."""
    if not texts:
        return float("nan")
    return sum(1 for t in texts if decode(encode(t)) == t) / len(texts)


def unknown_rate(encode: Callable, texts: Sequence[str], unk) -> float:
    toks = [tok for t in texts for tok in encode(t)]
    return sum(1 for tok in toks if tok == unk) / len(toks) if toks else float("nan")


def byte_fallback_rate(encode: Callable, texts: Sequence[str], is_byte_token: Callable) -> float:
    toks = [tok for t in texts for tok in encode(t)]
    return sum(1 for tok in toks if is_byte_token(tok)) / len(toks) if toks else float("nan")


def apostrophe_word_split_rate(encode: Callable, texts: Sequence[str]) -> float:
    """Average tokens per glottal-stop word (e.g. "ba'an") — a Somali-specific check."""
    target = [w for t in texts for w in words(t) if "'" in w]
    if not target:
        return float("nan")
    return sum(len(encode(w)) for w in target) / len(target)


def report(name: str, encode: Callable, texts: Sequence[str], decode: Callable | None = None) -> dict:
    out = {
        "tokenizer": name,
        "texts": len(texts),
        "fertility": round(fertility(encode, texts), 4),
        "bytes_per_token": round(bytes_per_token(encode, texts), 4),
        "tokens_per_apostrophe_word": round(apostrophe_word_split_rate(encode, texts), 4),
    }
    if decode is not None:
        out["roundtrip_fidelity"] = round(roundtrip_fidelity(encode, decode, texts), 4)
    return out


# Reference tokenizers for sanity checks; not candidates.
def utf8_bytes_encode(text: str) -> list[int]:
    return list(text.encode("utf-8"))


def utf8_bytes_decode(tokens: list[int]) -> str:
    return bytes(tokens).decode("utf-8", errors="replace")
