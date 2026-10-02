# Models

## Track 1: Asal-Scratch
Decoder-only Transformers trained from scratch on the approved Asal corpus:
20M → 50M → 125M → 350M. They exist to validate data, tokenizer, architecture, training
and evaluation cheaply, before any expensive scaling.

### Data budget
Rule of thumb: about 20 training tokens per parameter for compute-optimal training.

| Model | ~Compute-optimal tokens | vs ~0.9-1.1B available (provider figures, before cross-source dedup) |
|---|---|---|
| 20M | 0.4B | supported |
| 50M | 1.0B | about 1 epoch; borderline once dedup and decontamination shrink the corpus |
| 125M | 2.5B | data-limited, multiple epochs needed |
| 350M | 7.0B | heavily data-limited |

The usable corpus will be *smaller* than the provider figures (cross-source dedup,
decontamination, licence exclusions). Every run records epochs, and the effect of repetition
on validation loss is measured.

## Track 2: Asal-Adapted
An open multilingual base model with continued pretraining and tuning on Somali.
Candidates: `models/asal_adapted/candidates.yaml` (unmeasured). Selection in Phase 4 by
licence, measured Somali bits per byte, tokenizer fertility and AsalBench before/after.
Asal-Adapted is the baseline every Asal-Scratch model must beat. The winner on measured
Somali performance is carried forward.

## Comparisons
Perplexity is compared only between models that share a tokenizer. Across tokenizers, use
bits per byte. Every evaluation includes at least one strong reference model on the same items.

## Architecture (Phase 3 baseline)
A modern decoder-only Transformer: token embeddings, causal self-attention, feed-forward
network, residual connections, normalisation, tied or untied output head. Candidate techniques
(RoPE, RMSNorm, SwiGLU, grouped-query attention) are adopted only through controlled ablations
at 20M scale, one change at a time, judged on held-out bits per byte at equal compute.
Fused attention kernels (FlashAttention or equivalent) are an implementation-efficiency choice,
not an architectural one.
