# Research method

1. **Question first.** Each experiment starts with a written question and the measurement that
   would answer it (in the run record's `description`).
2. **Register, then run.** Experiment ID before execution. Configs are committed.
3. **Held-out discipline.** Evaluation data is registered and decontaminated before any training.
   Thresholds and word lists are fixed before looking at the test split. If a test split is
   looked at, say so in the log.
4. **Baselines.** Every new method is compared against the simplest reasonable baseline and the
   current best, on identical items.
5. **Ablate one thing at a time.** Architecture choices (RoPE, RMSNorm, SwiGLU, GQA) and
   post-training methods (DPO, ORPO, GRPO, distillation) are adopted only on measured gains.
6. **Report honestly.** Report negative results, caveats (overlap, sample size, missing
   varieties) and failed runs. Small samples are labelled as small.
7. **Humans in the loop.** Native speakers review samples, label dialects and rate outputs.
   Automated metrics never stand in for them on generation, translation or dialect.
8. **Log decisions.** RESEARCH_LOG.md records each decision, the evidence behind it and what is
   still unknown. Architectural decisions are never changed silently.
