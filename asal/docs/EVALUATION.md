# Evaluation

## Principles
- Compare Asal-Scratch, Asal-Adapted and at least one strong commercial or open reference model
  on identical items.
- Report only measured numbers, with the experiment ID. No SOTA claims without evidence.
- Generation, translation and dialect tasks need native-speaker human evaluation: blind, ≥2 raters
  per item where possible, agreement reported with scores.

## Areas
Somali perplexity / bits per byte; generation; grammar; spelling; vocabulary; classification;
NER; QA; summarisation; Somali↔English translation; mathematics; logical reasoning;
instruction following; dialect identification, understanding and generation; safety.

## Evaluation-set registry
`evaluation/decontamination/eval_sets.yaml`. v0.1: 4 indexed sets (MasakhaNEWS Somali dev/test,
SIB-200 som_Latn dev/test) and 6 pending (FLORES-200 devtest, Belebele, XL-Sum test, SomBench,
SomaliBench v0, FLEURS transcripts). Pending sets are blocked by network access or location.

## Decontamination (enforced)
`src/asal/decontam.py`, pipeline stage 12.
1. Every evaluation set is registered with its source.
2. Before any training run: n-gram overlap (casefolded word tokens) between the training corpus and
   every indexed set, at n=13 and n=8. Items shorter than n are matched in full. Items under 6 words
   are not indexed and are counted as skipped.
3. Overlapping training records are removed. The removal is logged (rejected.jsonl with eval hits)
   and summarised per eval set.
4. Same-provider pairs need special care: SomNLP-Corpus vs SomBench; shared sources such as
   Wikipedia, XL-Sum and BBC Somali (MasakhaNEWS); FLORES-200 derivatives (SIB-200, Belebele, FLEURS).

v0.1 finding: MasakhaNEWS Somali train overlaps its own dev/test (34 train docs at n=13; see
the v0.1 report). Results on MasakhaNEWS test from models trained on its train split are
partly contaminated.

## Language-ID evaluation
`scripts/evaluation/compare_lid.py`: held-out SIB-200 test in 11 languages, MasakhaNEWS Somali
test, and a synthetic Somali-English mix. Thresholds (e.g. the ensemble's) are tuned on the dev
splits only. Maay, natural code-switched text and short informal web sentences are still missing
from the labelled data. The v0.2 NLLB run shows the last of these is where the tools disagree most.

v0.3 (ASAL-LID-20261007-lid-comparison-eee8b8): CLD2 scores F1 1.000 on test and dev, with no
Oromo false positives, and is now the default gate. Heuristic 0.972, Lingua 0.874 (Lingua labels
67.6% of Oromo as Somali).
