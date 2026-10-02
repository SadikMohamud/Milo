# Compute plan (DRAFT)

Status: draft. **No entry is approved.** Training needs an approved entry here, referenced by
ID from a TRAIN experiment's `approval.compute_entry`.

## Spending limit
Any single run or phase above **USD [to be set by the project owner]** needs explicit written
approval from the project owner before it starts. Until the owner sets a limit, the effective
limit is **USD 0**: nothing runs.

## Entries

| ID | Phase | Model | Where | Est. GPU-hours | Est. cost | Status |
|---|---|---|---|---|---|---|
| C-DRAFT-01 | 3 | Asal-Scratch-20M, ~0.4B tokens | to decide (single consumer/cloud GPU is sufficient) | to estimate after a throughput benchmark | to estimate | draft, not approved |
| C-DRAFT-02 | 3 | Asal-Scratch-50M, ~1B tokens | to decide | to estimate | to estimate | draft, not approved |
| C-DRAFT-03 | 4 | Asal-Adapted continued pretraining (0.5B-3B base) | named cloud provider, to decide | to estimate | to estimate | draft, not approved |
| C-DRAFT-04 | 5 | Asal-Scratch-125M / 350M | to decide | to estimate | to estimate | gated on Phase 3/4 results |

## How to estimate (fill in before approval)
Training FLOPs ≈ 6 × parameters × tokens. GPU-hours = FLOPs / (peak FLOP/s × measured MFU × 3600).
Measure MFU with a short (≤1 GPU-hour) throughput benchmark on the target hardware. Do not use
vendor peak figures alone. Add 30% for evaluation, restarts and checkpoints. Record the provider
and price per GPU-hour with the date.
