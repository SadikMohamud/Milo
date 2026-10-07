# Data v0.3: NLLB English–Somali, uniform random sample + CLD2 language-ID gate

Measured 2026-10-07. Reproduce:

```bash
pip install pycld2
python scripts/evaluation/compare_lid.py
python scripts/data/download_sample.py data/manifests/nllb-random-v0.3.yaml     # streams 1.7 GB once, ~1 min
python scripts/data/run_sample_pipeline.py --manifest data/manifests/nllb-random-v0.3.yaml \
    --no-lingua --slug nllb-random-pipeline --report-dir evaluation/reports/data_v0.3_nllb_random
```

| File | Experiment |
|---|---|
| `lid_comparison.json`, `lid_comparison.md` | ASAL-LID-20261007-lid-comparison-eee8b8 |
| `pipeline_summary.json` | ASAL-DATA-20261007-nllb-random-pipeline-45ad3f |

## 1. A third LID tool: CLD2

`pycld2` (Google CLD2, offline) has Somali, Oromo and Afar classes. On the held-out sets:

| backend | split | precision | recall | F1 | Oromo called Somali |
|---|---|---|---|---|---|
| asal-heuristic | test | 0.954 | 0.992 | 0.972 | 10.8% |
| lingua | test | 0.776 | 1.000 | 0.874 | 67.6% |
| **cld2** | **test** | **1.000** | **1.000** | **1.000** | **0%** |
| asal-heuristic | dev | 0.972 | 0.992 | 0.982 | n/a |
| **cld2** | **dev** | **1.000** | **1.000** | **1.000** | **0%** |

CLD2 also labels 45.6% of the synthetic Somali-English mixes as Somali (Lingua 87.8%,
heuristic 3.4%). Those mixes have no correct single label.

**Decision:** CLD2 is the default primary LID gate from v0.3 (`--primary-lid auto`). The
heuristic and, when run, Lingua still record their predictions on every record.
**Caveats:** the labelled sets are clean FLORES/BBC text. CLD2 is untested on Maay. Short
informal web Somali is still unlabelled; the review sheets exist for exactly that.

## 2. A representative NLLB sample

The v0.2 sample was the top-scored 8 MiB prefix of a score-sorted file. For v0.3 the whole
object was streamed once and every line hashed:

- **MD5 of the stream equals the pinned GCS object MD5** (`gS5eDvCrd26LRP7o8YsB7Q==`).
- **10,229,073 pairs**: the first Asal-verified size of an upstream Somali corpus. It equals
  the figure Goobo Labs reports.
- Line *i* is kept iff `blake2b("20261007:i") < 0.005·2⁶⁴`: **51,277 pairs**, uniform over
  the file. Re-deriving the sample produced a byte-identical file (SHA-256 pinned in the manifest).
- LASER score distribution of the whole file: 66% of pairs score below 1.07, and only 0.9%
  score 1.12 or above. The v0.2 prefix was that top 0.5%.

## 3. Funnel (primary LID: cld2)

| Stage | In | Kept | Rejected | Main reasons |
|---|---:|---:|---:|---|
| language_identification | 51,277 | 48,585 | 2,692 (5.2%) | CLD2 labels: eng 1,333, ind 129, gaz 128, xh 79, … |
| quality_filter | 48,585 | 46,097 | 2,488 | `too_short` 2,360 |
| exact_dedup | 46,097 | 45,731 | 366 | see note below |
| near_dedup | 45,731 | 45,695 | 36 | |
| evaluation_decontamination | 45,695 | 45,659 | 36 | MasakhaNEWS dev/test |

Final: 45,659 sentences, 665,239 words (median 13 words).

Note: a 0.5% sample cannot measure file-level duplication. Two copies of a line are both
sampled with probability ~0.005, so 0.8% here is a large underestimate. Goobo reports that
exact dedup keeps 4.37M of the 10.2M NLLB pairs.

## 4. Representative estimates vs the biased prefix

| Measure | v0.2 prefix (top 0.5%) | **v0.3 uniform sample** (95% CI) |
|---|---|---|
| Rejected by the LID gate | 12.7% (heuristic gate) | 5.2% (CLD2 gate); the heuristic would reject 16.1% |
| Final sentences from suspected-MT URLs | 24.9% | **14.7%** (14.4–15.1%) |
| …among sentences that carry a URL (CC-mined, 31.6% of final) | n/a | **46.5%** |
| Religious (lexicon, lower bound) | 7.5% | **2.9%** (2.8–3.1%) |
| Matching MasakhaNEWS dev/test (n=13 or n=8) | 10 sentences (0.03%) | **36 sentences (0.08%)** |

The prefix overstated religious text (verses align well, so they score high) and suspected
MT. It understated benchmark leakage.

## 5. Findings

**R1: CLD2 removes the Oromo problem on available labels**, and in a 0.1-second run.

**R2: The heuristic gate was wrong for this source.** On the uniform sample, CLD2 and the
heuristic agree on 87% of sentences. CLD2 accepts 6,194 that the heuristic rejects, and the
heuristic accepts 616 that CLD2 rejects. Which one is right on short informal text is a
question for the native-speaker review sheets.

**R3: Benchmark leakage is systematic.** 20 sentences match MasakhaNEWS dev/test at n=13.
They cover 19 distinct eval items: 15 of the 294 test articles and 4 dev articles. Their Somali sides come from ParaCrawl monolingual
crawls, Common Crawl and the AfriBERTa corpus (BBC Somali). At this rate the full file holds
on the order of 4,000 such sentences (20 / 0.005). That is a rough extrapolation, not a
measurement.

**R4: Where NLLB provides a URL, almost half the Somali comes from suspected
auto-translated pages** (`so.lezgka.ru`, `so.rayhaber.com`, `so.eturbonews.com`,
`so.wondershare.com`, …). 68% of final sentences come from ParaCrawl/AfriBERTa without a URL,
so the heuristic cannot judge them. The `/so/` path rule includes human-translation
publishers (e.g. `lawhelpmn.org`, `minnetonkaschools.org`), so precision is unknown until
reviewed.

## 6. Review sheets
```bash
python scripts/data/draw_review_sample.py draw ASAL-DATA-20261007-nllb-random-pipeline-45ad3f
```
