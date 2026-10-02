# Research log

Newest first. Each entry: what was done, what was found, what was decided, and what is
still unknown. Experiment IDs refer to `experiments/runs/<id>/run.yaml`.

---

## 2026-10-02: ASAL DATA INTELLIGENCE v0.1

### Environment constraints (affect every result below)
- Reachable: github.com (git and raw.githubusercontent.com), pypi.org.
- Blocked by the session network policy: huggingface.co, datasets-server.huggingface.co,
  so.wikipedia.org, dumps.wikimedia.org, opus.nlpl.eu, dl.fbaipublicfiles.com, arxiv.org, unkad.com.
- Consequence: no sample of the large Somali pretraining corpora, no licence checks on
  dataset cards, and no GlotLID or fastText LID models. All such registry fields stay
  `unknown` / `review_required`.

### Decision: repository location and layout
The Git repository (`Milo`) already holds an unrelated project, so Asal lives in `asal/`.
The importable code is a `src/asal/` package rather than being spread across the
`tokenizer/src`, `training/src` etc. folders of the specification. This gives one tested
library, with scripts as thin wrappers. The spec folders exist and hold configs, tests and
artifacts.

### Decision: sample sources
MasakhaNEWS Somali and SIB-200 `som_Latn` (GitHub-hosted, pinned to commits 819be052 /
efad32e0). Both are evaluation datasets, so the sample is used only to validate the
pipeline, and their dev/test splits double as registered evaluation sets for decontamination.
Neither is approved for training.

### Study: Unkad Labs, Awesome Somali NLP (unkadlabs/awesome-somali-nlp@de1aaad)
Read in full. CC0-1.0. Gives provider-style descriptions of SomaliWeb v1 (819K docs, ~303M
tokens, HPLT v2 + CC100 + Wikipedia, CC BY-SA 4.0, 16K tokenizer), SomaliBench v0 (200
paired safety prompts), MasakhaNEWS, SIB-200, Belebele, Aya, FLORES-200, OPUS, SomBERTa,
AfroXLMR, AfriBERTa, SERENGETI, AfroBench, IrokoBench. Its "gaps" section matches the
Asal plan: no Somali reasoning/knowledge benchmark, Maay nearly absent, news-heavy web
text, no speech at scale. Every figure was recorded as `secondary_source` in the registry.
SomaliWeb itself could not be inspected (Hugging Face blocked), so it is only partly studied.

### Study: Goobo Labs SomNLP-Corpus pipeline (goobolabs/somnlp-corpus@add401b)
- The repository holds a Rust pipeline and tokenizer, not the corpus text. The latest
  provider build (2026-09-24, 17 sources) reports 7,981,982 docs, 832M words and 1.136B v2
  tokens. The figures in the Asal specification (7.35M / 666M / 912M) are the README's
  *previous* build (2026-09-02, 13 sources). Both are recorded as provider claims.
- Stages: download → merge + exact dedup (first-seen-wins by source order) → clean → LID
  (Lingua, min confidence 0.5) → deep clean (mojibake repair, URL/e-mail masking, boilerplate,
  segment-level LID) → MinHash near dedup (3-shingles, unit not checked; 64 hashes, 16×4 bands,
  τ = 0.8). Each record has a source licence, a content hash and reject sidecars.
- Sentence-class sources (OPUS, MT560, NLLB, Quran) skip the LID gate and near dedup.
- No evaluation-decontamination stage was found (searched for "decontam" and "contamina"),
  and there is no dialect labelling.
- No LICENSE file: the licence of the code and tokenizer is unknown. Asal keeps a local
  copy of the tokenizer for measurement only (`tokenizer/artifacts/`, not committed).
- The apostrophe has no Somali-specific handling; a CLEANING_STRATEGY note says 52% of
  documents contain U+2018/2019/201C/201D and calls this "low priority".
- New upstreams added to the registry: FinePDFs, FineWeb-2, Somali Alpaca, Somali
  TinyStories. The last two may be model-generated; their synthetic status is unknown.
- Lessons adopted: per-stage reject sidecars (already in the Asal design), source-order
  exact dedup, and the class split between document and sentence sources (to adopt in Phase 1).
- Gaps Asal fills: decontamination, Oromo-aware LID, apostrophe normalisation, dialect
  field, and separating provider claims from verified values.

### Experiment ASAL-DATA-20261002-sample-pipeline-915758: pipeline on the sample
See `evaluation/reports/data_intelligence_v0.1/README.md`. The main finding is
MasakhaNEWS train/test overlap: 34 train articles share ≥1 13-gram with dev/test, and 23
share ≥20. The run is deterministic (same fingerprint as the earlier run -ce46c2, which is
marked superseded).

### Experiment ASAL-LID-20261002-lid-comparison-835374: LID comparison
asal-heuristic F1 0.972, Lingua F1 0.874. Lingua calls 67.6% of Oromo sentences Somali.
The heuristic's word lists and threshold (0.5) were written from general knowledge before
any evaluation. The only data examined beforehand was the *train* splits (score check),
never the test splits used in the comparison.
**Decision:** keep asal-heuristic as the v0.1 primary gate and record every backend's
prediction on each record. Revisit when GlotLID can be run. Do not adopt Lingua alone as a gate.

### Experiment ASAL-TOK-20261002-tokenizer-benchmark-8849bc: Goobo v2 48K
1.2812 tokens/word, 5.05 bytes/token, round trip 1.0. Glottal-stop words take 3.10 tokens
(the apostrophe is always split off). ASAL-TOK-…-b75ea0 was a harness smoke run (superseded).
**Open question for Phase 2:** would a pre-tokenizer that keeps word-internal apostrophes
reduce fertility on glottal-stop words without hurting round trip? Measure, don't assume.

### Known limitations of v0.1 code
- PII: e-mail and phone only. Names, addresses and IDs are not detected.
- MT flagging and domain are source-level defaults from the registry, not document classifiers.
- Dialect is always `unknown`: no labelled data exists yet.
- Boilerplate removal is exact-line only.
- Lingua needs about 1 GB RAM; tests marked `slow` load it.
