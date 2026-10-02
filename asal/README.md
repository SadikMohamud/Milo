# Asal

**Building Somali-native AI from the ground up.**

Asal is a Somali-first foundation-model research project. It is not an API wrapper: the
goal is to build, understand, evaluate and progressively train a Somali-native AI system
covering Standard Somali, Benaadir, Waqooyi/Northern Somali, Maay (as its own variety),
Somali-English code-switching, speech, reasoning, translation, coding, retrieval and agents.

> **Status: Phase 0, milestone ASAL DATA INTELLIGENCE v0.1.** No model has been trained.
> No dataset is approved for training. Every number below was measured in this repository,
> on a small validation sample, and is reproducible with the commands shown.

## Two model tracks

| Track | What it is | Role |
|---|---|---|
| **Asal-Scratch** | 20M → 50M → 125M → 350M decoder-only models trained from scratch on Somali | Validates data, tokenizer, training and evaluation |
| **Asal-Adapted** | An open multilingual base model with continued pretraining and tuning on Somali | The baseline every Scratch model must beat |

About 0.9B Somali tokens exist in the largest known corpus (provider figure, before
cross-source deduplication). That supports small from-scratch models but is well below a
compute-optimal budget for models in the hundreds of millions of parameters, so whichever
track wins on measured Somali performance is carried forward (docs/MODEL.md).

## What v0.1 contains

| Component | Where | State |
|---|---|---|
| Dataset registry (29 entries), schema, policy rules, catalogue | `data/registry/` | Provider claims and Asal-verified values kept apart; overlap between aggregated corpora detected |
| Reproducible sample download (SHA-256 pinned) | `data/manifests/`, `scripts/data/download_sample.py` | 16 files, GitHub-hosted, pinned to commit SHAs |
| 14-stage data pipeline with per-stage outputs, stats, logs, rejected records and reason codes | `src/asal/pipeline.py` | Runs end to end on the sample |
| Somali normalisation (apostrophe = glottal stop, never stripped) | `src/asal/normalize.py` | Tested |
| Exact + MinHash near deduplication, within and across sources | `src/asal/dedup.py` | Tested |
| Language ID with 2 working backends (+ fastText lid.176 / GlotLID adapters) | `src/asal/lid.py` | Compared on held-out data |
| Evaluation-set registry and n-gram decontamination | `evaluation/decontamination/`, `src/asal/decontam.py` | Runs on the sample |
| Tokenizer metric harness and candidate list | `src/asal/tokenizer_metrics.py`, `tokenizer/configs/candidates.yaml` | Harness tested; candidates not yet measured |
| Asal-Adapted base-model candidates | `models/asal_adapted/candidates.yaml` | Listed, not measured |
| Experiment ID system and training guard | `src/asal/experiments.py`, `training/scripts/train.py` | Training refuses to start without an approved TRAIN experiment |

Results: [`evaluation/reports/data_intelligence_v0.1/README.md`](evaluation/reports/data_intelligence_v0.1/README.md).

## Quick start

```bash
cd asal
pip install -r requirements.txt          # PyYAML, jsonschema, numpy, pytest, lingua (optional)
python -m pytest -q                       # 43 tests (add -m "not slow" to skip loading Lingua)

python scripts/data/validate_registry.py  # validate registry, regenerate CATALOGUE.md
python scripts/data/download_sample.py    # fetch + verify the pinned sample (~6 MB)
python scripts/data/run_sample_pipeline.py      # full pipeline on the sample (needs ~1 GB RAM with Lingua)
python scripts/evaluation/compare_lid.py        # LID comparison
python scripts/tokenizer/benchmark_tokenizers.py
```

Each run registers an experiment under `experiments/runs/<id>/run.yaml`.
Downloaded and processed text is never committed (`.gitignore`), because the upstream
redistribution terms are not yet verified.

## Principles

Research before training. "Open" does not mean unrestricted. Unknown facts are `unknown`
or `review_required`, never guessed. Provider claims stay provider claims until Asal
verifies them. No benchmark result or SOTA claim without evidence. Native Somali speakers
are part of the pipeline. See [CLAUDE.md](CLAUDE.md) and [docs/](docs/).

## Layout

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The importable package lives in
`src/asal/`; scripts in `scripts/` are thin command-line wrappers around it.

## Licence

Code: Apache-2.0 (see [LICENSE](LICENSE); the project owner should confirm this choice).
Data listed in the registry keeps its own upstream licence.
