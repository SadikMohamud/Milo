# Roadmap

Each phase ends at a gate in docs/PHASE_GATES.md. Nothing moves forward on a schedule alone.

| Phase | Name | Output | Gate |
|---|---|---|---|
| 0 | Data intelligence (v0.1) | Registry, pipeline, LID, dedup, decontamination, experiment system | G0 |
| 1 | Corpus v1 | Licence-verified sources, full pipeline at scale, cross-source dedup size, native-speaker sample review | G1 |
| 2 | Tokenizer | 16K/32K/48K/64K candidates vs Goobo 48K vs base-model tokenizers on held-out Somali (incl. Maay) | G2 |
| 3 | Asal-Scratch-20M / 50M | Training infrastructure validated; loss curves, bits per byte, repetition effects | G3 |
| 4 | Asal-Adapted baseline | Base-model selection, continued pretraining, AsalBench before/after | G4 |
| 5 | Asal-Scratch-125M / 350M | Only if Phase 3 trends justify it against the Adapted baseline; multi-epoch measured | G5 |
| 6 | Instruction and reasoning | SFT, then DPO/ORPO/GRPO/distillation only where each measurably helps | G6 |
| 7 | Speech | ASR/TTS on consented, registered speech data | G7 |
| 8 | Runtime | Inference, RAG, tools, agents, decoupled from the model | G8 |

Cross-cutting from Phase 0 onward: dialect annotation (native speakers, inter-annotator
agreement), AsalBench construction (with a private held-out portion), human evaluation.

## Immediate next steps (Phase 0 → 1)
1. Get network access to huggingface.co, dumps.wikimedia.org, opus.nlpl.eu and
   dl.fbaipublicfiles.com (blocked in the v0.1 environment), then pin and download samples of
   SomNLP-Corpus, SomaliWeb, CC100, HPLT, MADLAD, Wikipedia.
2. Verify licences at source for those entries; fill `license_basis: verified_in_source`.
3. Register FLORES-200 devtest, Belebele, XL-Sum test, SomBench, SomaliBench as indexed eval sets.
4. Run GlotLID and fastText lid.176 in the LID comparison (needs the model files); GlotLID
   covers Oromo and Maay, the two gaps found in v0.1.
5. Locate the Goobo 48K tokenizer and SomaliWeb 16K tokenizer; benchmark them.
6. Recruit native-speaker reviewers; review rejected-record samples per stage.
