# Data v0.2: NLLB English–Somali mined bitext (top-scored prefix)

Measured 2026-10-02. Reproduce:

```bash
python scripts/data/download_sample.py data/manifests/nllb-sample-v0.2.yaml
python scripts/data/run_sample_pipeline.py --manifest data/manifests/nllb-sample-v0.2.yaml \
    --no-lingua --slug nllb-head-pipeline --report-dir evaluation/reports/data_v0.2_nllb
python scripts/evaluation/compare_lid.py
```

| File | Experiment |
|---|---|
| `pipeline_summary.json` | ASAL-DATA-20261002-nllb-head-pipeline-961d5c |
| `lid_comparison.json`, `lid_comparison.md` | ASAL-LID-20261002-lid-comparison-349e98 |

## What was sampled, and the bias
NLLB's `eng_Latn-som_Latn.gz` (1.70 GB, about 10.2M pairs according to Goobo Labs) is
one gzip stream sorted by LASER alignment score, highest first. Asal fetched the first 8 MiB,
pinned by GCS generation and SHA-256. That prefix decodes to **51,806 pairs, all with LASER
score ≥ 1.12**. It is the best-aligned slice of the file, **not a random sample**, so the
shares below must not be extrapolated to the whole file. Only the Somali side was processed.

This source matters because, per Goobo Labs, NLLB supplies 4.1M of SomNLP-Corpus's 8.0M final
documents (62M of its 832M words). Goobo treats it as sentence-class, so it is not LID-gated
there.

## Funnel (primary LID: asal-heuristic)

| Stage | In | Kept | Rejected | Main reasons |
|---|---:|---:|---:|---|
| language_identification | 51,806 | 45,214 | 6,592 | `lid_not_somali` |
| quality_filter | 45,214 | 44,122 | 1,092 | `too_short` 1,040 |
| exact_dedup | 44,122 | 32,195 | 11,927 | 27% of the remaining sentences are exact repeats |
| near_dedup | 32,195 | 31,813 | 382 | |
| evaluation_decontamination | 31,813 | 31,803 | 10 | MasakhaNEWS dev/test sentences |

Final: 31,803 sentences, 479,385 words (median 14 words per sentence).

## Findings

**N1: Web-mined bitext contains benchmark text.** At n=13, four Somali sentences are
verbatim from MasakhaNEWS Somali dev/test (BBC Somali) articles. Six more match at n=8.
Any corpus that includes NLLB, such as SomNLP-Corpus, needs decontamination against
MasakhaNEWS (and XL-Sum) before results on those benchmarks mean anything.

**N2: About a quarter of the slice comes from suspected machine-translated pages.** 7,904 of
31,803 final sentences (24.9%) come from URLs on a Somali language subdomain of a foreign
site (`so.rayhaber.com`, `so.eturbonews.com`, `so.lezgka.ru`, `so.urdolls.com`, …; 3,660) or a
`/so/` path (4,244). They are flagged `machine_translated: suspected`, not removed. **The
heuristic's precision is unknown and certainly below 100%.** The `/so/` rule also catches
sites that publish human translations for Somali communities, such as `www.jw.org` and
Minnesota public institutions. A review sheet per flag is ready; see the end of this report.

**N3: Religious text is a large share.** The religion lexicon flags 2,387 sentences (7.5%), and
the slice opens with Quran and Bible verses. The lexicon covers Bible narrative poorly (for
example, "He shall be head over all the people of Gilead" is not flagged), so this is a lower
bound.

**N4: The v0.1 LID gate is too strict for short web sentences.** The heuristic rejected 6,592
sentences (12.7%). On a random 400 of those, Lingua labels 307 Somali (76.8%, 95% CI
72.4–80.6%). Some of these are clearly Somali to a reader (e.g. *"Aragtidaada hoos noogu reeb,
mahadsanid."*), and others are clearly not (English song lyrics, romanised Urdu). On 400 kept
sentences, Lingua agrees 396 times. NLLB's own Somali LID score is ≥ 0.98 for most of the
rejected lines, including English ones, so that score is not a usable filter either.

**N5: Combining the tools does not fix it on available labels.** An ensemble gate (Somali if the
heuristic is confident, *or* Lingua says Somali and the heuristic score ≥ t) was tuned on
SIB-200 *dev*. Every t below 0.5 lets Oromo through (dev precision falls from 0.97 to
0.79–0.95), so tuning chose t = 0.5, which is the heuristic alone. On FLORES-style text,
Oromo and short informal Somali cannot be separated with these two tools. Resolving this
needs (a) native-speaker labels on web sentences (the review sheets) and (b) GlotLID, which
has an Oromo class, once its host is reachable.

**N6: Exact duplication is heavy.** 27% of the sentences that passed LID and quality are verbatim
repeats within the slice, mostly religious verses and boilerplate phrases mined from many pages.

## Review sheets (for a native Somali speaker)
`python scripts/data/draw_review_sample.py draw ASAL-DATA-20261002-nllb-head-pipeline-961d5c`
writes seeded sheets to `data/samples/<id>/` (not committed): 50 rejected + 50 kept per stage
with rejections, plus 50 MT-suspected and 50 religion-flagged records. After the `verdict`
column is filled in, `... summarise <id>` writes error rates with 95% CIs to
`evaluation/reports/reviews/`.
