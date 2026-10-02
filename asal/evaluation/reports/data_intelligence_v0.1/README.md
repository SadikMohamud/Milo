# ASAL DATA INTELLIGENCE v0.1: results

All numbers are measured in this repository on 2026-10-02 and are reproducible with the
commands in the top-level README. They describe a **small validation sample**: about 1.7K
documents and 0.6M words. They say nothing yet about corpus-scale behaviour.

Machine-readable outputs in this folder:

| File | Experiment |
|---|---|
| `pipeline_summary.json` | ASAL-DATA-20261002-sample-pipeline-915758 |
| `lid_comparison.json`, `lid_comparison.md` | ASAL-LID-20261002-lid-comparison-835374 |
| `tokenizer_benchmark.json` | ASAL-TOK-20261002-tokenizer-benchmark-8849bc |

## 1. Sample

MasakhaNEWS Somali and SIB-200 `som_Latn`, downloaded from GitHub at pinned commits with
SHA-256 verification (`data/manifests/sample-v0.1.yaml`). Hugging Face, Wikimedia, OPUS and
dl.fbaipublicfiles.com were blocked by the network policy of the build environment, so the
large corpora could not be sampled. Train splits run through the pipeline; dev/test splits
are registered evaluation sets. **Neither source is approved for training.** MasakhaNEWS has
no licence file, and SIB-200 text is FLORES-200 evaluation data.

## 2. Pipeline funnel (primary LID: asal-heuristic)

| Stage | In | Kept | Rejected | Reason |
|---|---:|---:|---:|---|
| normalise | 1722 | 1722 | 0 | 464 apostrophe variants and 657 curly double quotes mapped to ASCII |
| format_validation | 1722 | 1722 | 0 | |
| language_identification | 1722 | 1707 | 15 | `lid_not_somali` (all 15 are short Somali SIB sentences; Lingua says Somali) |
| quality_filter | 1707 | 1707 | 0 | |
| pii_filter | 1707 | 1707 | 0 | no e-mail/phone found |
| exact_dedup | 1707 | 1707 | 0 | |
| near_dedup | 1707 | 1706 | 1 | `near_duplicate` (Jaccard 0.95, within MasakhaNEWS train) |
| boilerplate_removal | 1706 | 1706 | 0 | |
| MT flagging / dialect / domain | 1706 | 1706 | 0 | dialect = `unknown` for every record (no labelled set yet) |
| evaluation_decontamination | 1706 | 1604 | 102 | `eval_contamination` (34 at n=13, 68 more at n=8) |
| license_validation | 1604 | 1604 | 0 | validation mode: all marked `not_approved_validation_only` |
| provenance_attachment | 1604 | 1604 | 0 | |

Final: 1,604 documents, 539,078 words. The dataset fingerprint is
`62090746f04df9d1…`, and two runs with the same inputs give the same fingerprint.

## 3. Findings

**F1: MasakhaNEWS Somali train overlaps its own dev/test.** 34 train articles share at
least one 13-word sequence with a dev or test article. 23 of them share 20 or more, which
looks like the same story published twice. 32 test/dev items are affected. Anyone training
on MasakhaNEWS train and reporting on its test split is partly testing on training data. At
n=8, 28 more documents match on exactly one 8-gram; many of these may be stock phrases. The
n=8 single-match rule is deliberately conservative and should be reviewed by a native speaker
before corpus scale.

**F2: LID tools disagree in ways that matter for Somali** (held-out SIB-200 test in 11
languages, plus MasakhaNEWS test):

| backend | precision | recall | F1 | Oromo called Somali | synthetic Somali-English mix called Somali |
|---|---|---|---|---|---|
| asal-heuristic | 0.954 | 0.992 | 0.972 | 10.8% | 3.4% |
| lingua | 0.776 | 1.000 | 0.874 | **67.6%** | 87.8% |

Lingua has no Oromo model and labels most Oromo (`gaz_Latn`) sentences as Somali. Goobo's
SomNLP-Corpus uses Lingua as its LID gate, so Oromo contamination of Somali web corpora is a
risk to measure, not assume. The Asal heuristic is a function-word baseline: it is fast and
precise, but it misses short sentences and cannot name non-Somali languages. Neither tool
covers Maay. GlotLID (which has Oromo and Maay labels) and fastText lid.176 are wired in but
could not be run, because their model files are on blocked hosts. Maay was not evaluated.

**F3: Goobo v2 48K tokenizer** on the same held-out text: 1.28 tokens/word, 5.05
bytes/token, exact round trip. Glottal-stop words cost 3.10 tokens on average because the
byte-level pre-tokenizer always splits at the apostrophe (`ba'an` → `ba ' an`), and `’`
(U+2019) is a separate token, so `ba'an` and `ba’an` differ. Caveat: Goobo trained on XL-Sum
(BBC Somali), and MasakhaNEWS is also BBC Somali, so these figures may be flattered by overlap.

**F4: Registry-level double counting.** `cc100-so` text appears in SomNLP-Corpus and in
SomaliWeb v1. Wikipedia appears in three registered corpora, and HPLT in two. Sizes of these
corpora must never be summed (`data/registry/CATALOGUE.md`).

## 4. Milestone checklist

| # | Criterion | State |
|---|---|---|
| 1 | Repository initialised | done (`asal/`) |
| 2 | Architecture documented | done (docs/ARCHITECTURE.md) |
| 3 | Candidate datasets catalogued | done: 33 entries, `data/registry/CATALOGUE.md` |
| 4 | Registry with provider claims and verified values separate | done, enforced by schema + policy rules |
| 5 | Licences recorded | done, as `unknown` / `review_required` / provider claim with source. **None verified at source except the Unkad list (CC0)** |
| 6 | Provenance and `derived_from` recorded | done, with alias resolution and shared-upstream report |
| 7 | Small sample reproducibly downloaded | done (SHA-256 pinned). Not from the target pretraining corpora (network blocked) |
| 8 | Sample passes validation | done |
| 9 | Dedup within and across sources | done (unit-tested cross-source; the real sample has no cross-source duplicates) |
| 10 | LID works, compared across ≥2 tools | done (Asal heuristic, Lingua). GlotLID/fastText pending model files |
| 11 | Dataset statistics generated | done (`pipeline_summary.json`) |
| 12 | Goobo corpus pipeline studied | done from its repository (RESEARCH_LOG.md); corpus itself not downloaded |
| 13 | SomaliWeb studied | **partial**: only via the Unkad list; dataset and paper hosts blocked |
| 14 | Unkad resources studied | done (awesome-somali-nlp read in full) |
| 15 | Tokenizer candidates identified | done; Goobo v2 measured |
| 16 | Evaluation datasets identified and registered | done: 4 indexed, 6 pending (`eval_sets.yaml`) |
| 17 | Decontamination runs against a sample | done |
| 18 | Asal-Adapted base-model candidates identified | done (`models/asal_adapted/candidates.yaml`, unmeasured) |
| 19 | Experiment ID system | done |
| 20 | PHASE_GATES.md and COMPUTE.md drafted | done |
| 21 | Tests pass | 43 passed |
| 22 | No training without explicit experiment approval | enforced by `training/scripts/train.py` |
