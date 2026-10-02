# Tokenizer research

Candidates: `tokenizer/configs/candidates.yaml`. Metrics: `src/asal/tokenizer_metrics.py`.
Benchmark: `python scripts/tokenizer/benchmark_tokenizers.py --hf-tokenizer <tokenizer.json>`.

## Plan
Compare Asal-trained byte-level BPE and SentencePiece-unigram (byte fallback) at
16K / 32K / 48K / 64K, the Goobo 48K ByteLevel BPE, the SomaliWeb 16K tokenizer, and the
tokenizers of Asal-Adapted candidates, all on one held-out set never used for training.

Metrics: fertility (tokens per word, Asal word definition), bytes per token, round-trip
fidelity, unknown-token rate (or byte-fallback rate for byte-level tokenizers), tokens per
glottal-stop word, and fertility split by dialect (incl. Maay), English, code, numbers and URLs.

Fertility values from different word definitions are not comparable. Goobo reports 1.3444
tokens/word on its own holdout, while Asal measures 1.2812 on its held-out set with its own
word tokenizer. Always re-measure on Asal's set.

## v0.1 results (experiment ASAL-TOK-20261002-tokenizer-benchmark-8849bc)
| tokenizer | fertility | bytes/token | tokens per apostrophe word | round trip |
|---|---|---|---|---|
| UTF-8 bytes (reference) | 6.476 | 1.000 | 7.99 | 1.0 |
| Goobo somali-bpe v2 48K | 1.281 | 5.055 | 3.10 | 1.0 |

Held-out set: MasakhaNEWS Somali test + SIB-200 som_Latn test (498 texts). It is small,
news-heavy, has no Maay, and may overlap Goobo's training data (both include BBC Somali).

Observation: the GPT-2-style byte-level pre-tokenizer splits on the apostrophe, so no
merge can ever produce `ba'an` as one token. A Somali-aware pre-tokenizer that treats a
word-internal apostrophe as a letter is a Phase 2 experiment, judged by fertility and by
downstream bits per byte, not by intuition.

## For Asal-Adapted
Measure each candidate base model's tokenizer on the same set. If its Somali fertility is
poor, compare vocabulary extension (plus embedding initialisation) against keeping the
original tokenizer. Decide on measured downstream bits per byte.
