# Experiments

Every run that produces a result has an experiment ID and a run record:
`experiments/runs/<ID>/run.yaml`. No undocumented runs.

## ID format
`ASAL-<KIND>-<YYYYMMDD>-<slug>-<hash6>`, where KIND ∈ {DATA, LID, TOK, EVAL, TRAIN} and hash6
is derived from kind, slug, config and creation time (`asal.experiments.make_id`).

## Creating one
- From code: `asal.experiments.register(kind, slug, config=..., description=...)` (all v0.1
  scripts do this).
- From the shell: `python scripts/training/new_experiment.py TRAIN scratch-20m --config training/configs/x.yaml`.

## Run record
id, kind, description, created, status (registered → completed | failed | superseded), config,
the RUN_FIELDS listed in docs/TRAINING.md (unknown until filled), git_commit (with `-dirty`
if the tree had changes), results. TRAIN runs also have an `approval` block.

A superseded run is kept and gets a `superseded_reason`. Run records are never deleted.

## Folders
`experiments/configs/` (inputs), `runs/` (records, committed), `results/` (small result files),
`artifacts/` (large outputs, not committed).

## v0.1 runs
| ID | Status |
|---|---|
| ASAL-DATA-20261002-sample-pipeline-ce46c2 | superseded |
| ASAL-DATA-20261002-sample-pipeline-915758 | completed |
| ASAL-LID-20261002-lid-comparison-835374 | completed |
| ASAL-TOK-20261002-tokenizer-benchmark-b75ea0 | superseded |
| ASAL-TOK-20261002-tokenizer-benchmark-8849bc | completed |
| ASAL-DATA-20261002-nllb-head-pipeline-ca4c88 | failed (crash while writing its run record) |
| ASAL-DATA-20261002-nllb-head-pipeline-961d5c | completed |
| ASAL-LID-20261002-lid-comparison-349e98 | completed (adds the ensemble, tuned on dev) |
| ASAL-LID-20261007-lid-comparison-eee8b8 | completed (adds CLD2) |
| ASAL-DATA-20261007-nllb-random-pipeline-45ad3f | completed (uniform NLLB sample, CLD2 gate) |
