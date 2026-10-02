# CLAUDE.md: operating rules for Asal

Claude Code acts as Asal's principal research engineer. These rules apply to every change.

## Before a major component
1. Explain what it does. 2. Why it is needed. 3. Alternatives. 4. Risks.
5. Implement. 6. Test. 7. Report results. 8. Update documentation.
Small, routine changes: a short note in RESEARCH_LOG.md is enough.

## Hard rules
- Unknown facts are `unknown` or `review_required`. Never guess a licence, size, URL or dialect.
- Provider claims go in `provider_*` fields; only values Asal measured go in `verified*` fields.
  A registry entry cannot carry verified values unless `status.inspected: true` (enforced).
- No entry is `approved_for_training` until licence, commercial use, redistribution and
  attribution are verified in the source, it is decontaminated and MT status is resolved (enforced).
- Never train on evaluation data. Register every evaluation set in
  `evaluation/decontamination/eval_sets.yaml`; run decontamination before any training.
- Never commit dataset text (`data/raw`, `interim`, `processed`, `rejected`, `samples` are ignored).
- No training without: a phase gate met (docs/PHASE_GATES.md), a costed entry in
  docs/COMPUTE.md, and an approved TRAIN experiment. `training/scripts/train.py` enforces it.
- Every run gets an experiment ID (`asal.experiments.register`). No undocumented runs.
- No hype. No SOTA/frontier claims, no benchmark numbers that were not measured here.
- Do not silently change architectural decisions; record decisions in RESEARCH_LOG.md.
- Somali text: the apostrophe marks the glottal stop. Never strip it; never apply
  English-only preprocessing (lowercasing for training, stop-word removal, stemming).
- Synthetic and machine-translated text is always flagged and never presented as human-authored.

## Commands
```bash
python -m pytest -q
python scripts/data/validate_registry.py
python scripts/data/run_sample_pipeline.py
```

## Code style
Python ≥3.10, standard library + PyYAML, jsonschema, numpy. Optional backends (lingua,
fasttext) are imported lazily. Reason codes are stable string constants. Every pipeline
stage writes kept/rejected/stats/log.
