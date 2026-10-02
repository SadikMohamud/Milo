# Training

**No training occurs in v0.1.** `training/scripts/train.py` refuses to run unless
`asal.experiments.require_training_approval` passes:

1. a valid experiment ID of kind `TRAIN`, registered under `experiments/runs/<id>/run.yaml`;
2. an approval block with `approved_by`, `approved_on`, `phase_gate`, and `compute_entry`;
3. `compute_entry` present in docs/COMPUTE.md.

## Requirements for the training stack (Phase 3)
Configuration-driven (YAML in `training/configs/`), reproducible (seeded; git commit and
dataset fingerprint recorded), checkpointable and resumable (optimizer, scheduler, RNG and
data-loader state), experiment-tracked.

Tracked: mixed precision, gradient accumulation, gradient clipping, validation loss,
perplexity (same tokenizer only) and bits per byte, throughput, tokens/sec, GPU memory, GPU
hours and cost, seeds, experiment IDs, epochs.

Every run records (`asal.experiments.RUN_FIELDS`): model, track, base_model, parameters,
dataset, dataset_fingerprint, epochs, tokenizer, tokenizer_version, context_length,
batch_size, learning_rate, optimizer, scheduler, precision, steps, seed, hardware, gpu_hours,
estimated_cost, git_commit, results.

## Post-training (Phase 6)
Base → continued pretraining → instruction tuning → reasoning tuning → preference
optimisation. SFT first; DPO / ORPO / GRPO / distillation only where an ablation shows a
measured gain on AsalBench.
