# Research log

Newest first. Each entry: what was done, what was found, what was decided, and what is
still unknown. Experiment IDs refer to `experiments/runs/<id>/run.yaml`.

---

## 2026-10-07 (later): native-speaker review set up

The project owner is a native Somali speaker and will do the review. They chose to keep
Apache-2.0 for the code and the USD 0 compute limit as they are.
- Review page: a private claude.ai artifact ("Asal Review", source in
  `evaluation/human_eval/review-v0.3/asal-review.html`). It holds 140 sentences from
  ASAL-DATA-20261007-nllb-random-pipeline-45ad3f: 60 language-ID items (stratified by
  CLD2/heuristic agreement: 30 CLD2-only, 15 heuristic-only, 8 both, 7 neither), 50 MT items
  (20 language-subdomain, 20 `/so/` path, 10 URL-bearing unflagged controls) and 30 religion
  items (20 flagged, 10 unflagged). Strata and tool labels are hidden from the reviewer; the key
  is in `evaluation/human_eval/review-v0.3/key.json`.
- Answers save to the artifact's database. `scripts/evaluation/score_review.py` turns an export
  into per-stratum rates (Wilson 95% CIs) and population-weighted precision / false-reject
  estimates for each LID gate.
- Chrome control and WebFetch are unavailable in this cloud session: WebFetch is blocked by the
  same egress policy as curl. The blocked hosts still need to be allowed in the environment's
  network settings.

---

## 2026-10-07: v0.3, CLD2, and a uniform NLLB sample

### CLD2 as a third LID backend (ASAL-LID-20261007-lid-comparison-eee8b8)
`pycld2` installs from PyPI and has Somali, Oromo and Afar classes. On test it scored
P = R = F1 = 1.000 with 0/204 Oromo false positives. On dev, which Asal also checked before
adopting it, it scored 1.000 too (the heuristic got 0.982).
**Decision:** CLD2 becomes the primary LID gate for new runs (`--primary-lid auto`). Old runs
keep their recorded gate. This is a backend choice informed by test *and* dev results; no
threshold was tuned. The open risks are short informal web text and Maay, neither of which is
labelled yet. The compare_lid run briefly overwrote the v0.2 report files; they were restored
from git, and v0.3 results live in `evaluation/reports/data_v0.3_nllb_random/`.

### Uniform sample of NLLB (ASAL-DATA-20261007-nllb-random-pipeline-45ad3f)
New `asal.sampling.hash_line_sample`: it streams the whole object once, verifies its MD5
against the pinned GCS object, keeps line i iff blake2b(seed:i) < rate, and writes a
deterministic gzip (mtime 0). A re-derivation was byte-identical.
- **Verified: NLLB eng-som has 10,229,073 pairs**, equal to Goobo's figure. This is the first
  Asal-verified upstream size. LASER scores: 66% below 1.07, 0.9% at 1.12 or above (the v0.2
  prefix was the top 0.5%).
- Representative estimates are in the v0.3 report: suspected-MT URLs 14.7% of sentences
  (46.5% of the URL-bearing ones), religious ≥2.9%, MasakhaNEWS leakage 0.08% (15 of 294
  test articles hit at n=13 in a 0.5% sample).
- Leaked benchmark sentences come from ParaCrawl monolingual, Common Crawl and the AfriBERTa
  corpus.
- Duplication cannot be estimated from a 0.5% line sample (pairs of copies are rarely both
  sampled), so the 0.8% figure is not a duplication estimate.

### Housekeeping
Registry YAMLs are edited directly from now on. The one-off generator script used for v0.1/v0.2
was a scratch file and has been retired.

---

## 2026-10-02 (later): v0.2, real web-mined Somali, review tooling, MT/religion flags

### Access
Still blocked: Hugging Face, Wikimedia, OPUS, arXiv, statmt.org, quranenc.com, tanzil.net.
**Reachable:** `storage.googleapis.com`, which hosts NLLB's mined bitext (the location is
documented in Goobo's SOURCES.md).

### Registry enriched from Goobo SOURCES.md (somnlp-corpus@add401b)
Upstream URLs, provider licences and sizes were added as `secondary_source` claims for 17
upstream entries, including each source's contribution to SomNLP-Corpus's final build
(`goobo_final_documents`/`_words`). Notable claims: NLLB is 4.1M of 8.0M final documents;
20,900 of 42,000 Somali TinyStories rows are verbatim duplicates upstream; TinyStories has no
licence on its dataset card. None of this is verified by Asal.

### Experiment ASAL-DATA-20261002-nllb-head-pipeline-961d5c
The pipeline ran on the top-scored 8 MiB prefix of NLLB eng-som (51,806 pairs, a biased
sample). The full report is `evaluation/reports/data_v0.2_nllb/README.md`. Summary: verbatim
MasakhaNEWS dev/test sentences appear in the mined bitext; 24.9% of the final sentences come
from suspected-MT URLs; at least 7.5% is religious text; 27% exact duplicates; the heuristic LID
gate falsely rejects many short Somali sentences (Lingua calls 76.8% of a 400-sample of
rejections Somali). ASAL-DATA-…-ca4c88 crashed while writing its run record after the
pipeline had finished (relative path bug, now fixed); it is marked failed.

### Experiment ASAL-LID-20261002-lid-comparison-349e98: ensemble gate
Added `EnsembleLID` and tuned its low threshold on SIB-200 dev only (dev splits for 10
non-Somali languages added to the lid-eval manifest). Dev F1 rises monotonically with t up
to 0.5, i.e. the heuristic alone, because Oromo sentences get heuristic scores of 0.2–0.5
exactly where Lingua says Somali. Test results are therefore identical to the heuristic.
**Decision:** keep the heuristic as the primary gate. Do not build an ensemble on FLORES-style
labels alone. Get native labels on web sentences and GlotLID. Every backend's prediction stays
on each record so the gate can be re-decided later without re-running LID.

### New pipeline behaviour (applies to runs after v0.1)
- `machine_translated: suspected` from a URL heuristic (language subdomain or `/so/` path; `.so`
  domains exempt). Flag only, never a removal. Precision unknown: `/so/` paths include human
  translations (jw.org, Minnesota public institutions).
- `domain: religion` from a Somali religious lexicon (Islamic and Christian terms). Flag only.
  Recall on Bible narrative is poor.
- Segment-level LID annotation with a `code_switched` flag (sentence-level; intra-sentence
  switching is not detected). 68 NLLB sentences were flagged.
- Manifests support `byte_range` (pinned prefixes of large objects).

### Review tooling
`scripts/data/draw_review_sample.py` draws seeded, decision-shuffled sheets per stage and per
flag, and summarises filled sheets with Wilson 95% intervals. This is what gate G0 needs. It is
waiting on a native-speaker reviewer.

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
