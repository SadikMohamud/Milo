# Phase gates (DRAFT)

A phase starts only when the previous gate is met and the gate review is logged in
RESEARCH_LOG.md, naming who reviewed it.

## G0: Data intelligence v0.1 → Phase 1
- [x] Registry with schema and policy rules; provider claims separate from verified values
- [x] Reproducible, hash-pinned sample download
- [x] Pipeline runs end to end with per-stage outputs and reason codes
- [x] Dedup within and across sources; LID compared across ≥2 tools; decontamination runs
- [x] Experiment ID system; training guard; tests pass
- [ ] Native-speaker review of pipeline samples logged (**in progress**: 140-item review page set up for the project owner, 2026-10-07)
- [ ] Network access to the main data hosts (**open**: environment constraint)

## G1: Corpus v1 → Phase 2
- Licences verified at source for every source in the corpus; `approved_for_training` set by two maintainers
- Corpus size reported after cross-source dedup and decontamination (not summed provider sizes)
- Every indexed eval set (incl. FLORES-200 devtest, Belebele, XL-Sum test, SomBench) decontaminated against the corpus
- LID evaluated incl. GlotLID, with Oromo and code-switched Somali; gate chosen on that evidence
- Native-speaker review per stage, with false-reject / false-keep rates logged
- Domain shares and religious-text share reported

## G2: Tokenizer → Phase 3
- All candidates measured on one held-out set that includes Maay, code-switched text, numbers, URLs and code
- Reuse / adapt / replace decision for the Goobo 48K tokenizer recorded, with its licence resolved

## G3: Asal-Scratch-20M/50M → Phase 4
- Approved compute entries (docs/COMPUTE.md); training stack resumes from a checkpoint bit-exactly on CPU tests
- 20M trains stably; bits per byte on held-out Somali reported, with epochs and repetition effects

## G4: Asal-Adapted baseline → Phase 5
- Base model chosen on licence + measurements; AsalBench before/after continued pretraining
- Scratch vs Adapted comparison on identical items, including a reference model

## G5: Scale Scratch (125M/350M)
- Only if G3/G4 results show Scratch can plausibly beat Adapted at that size given the data budget

## G6-G8: Instruction/reasoning, speech, runtime
Each starts with a written plan, its own data registry entries, and a measured baseline.
