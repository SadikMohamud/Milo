# Contributing to Asal

1. Read [CLAUDE.md](CLAUDE.md). Its rules apply to humans too.
2. Run `python -m pytest -q` and `python scripts/data/validate_registry.py` before a PR.
3. **Adding a dataset:** add `data/registry/<id>.yaml` (see `schema.json`). Put provider
   figures under `size.provider_reported` with a `claim_source`. Leave every `verified`
   value `unknown` until you have inspected the data. Record `derived_from` and add an alias
   in `aliases.yaml` if other corpora name it differently.
4. **Adding an evaluation set:** register it in `evaluation/decontamination/eval_sets.yaml`
   before anyone trains on anything.
5. **Running anything that produces results:** register an experiment
   (`scripts/training/new_experiment.py`) and log the outcome in RESEARCH_LOG.md.
6. **Native-speaker contributions** (annotation, dialect labels, review of rejected samples,
   human evaluation) are the most valuable kind. Follow docs/ANNOTATION_GUIDELINES.md.
7. Never commit dataset text, model weights, tokens or credentials.
