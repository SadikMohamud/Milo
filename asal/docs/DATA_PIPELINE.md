# Data pipeline

Implementation: `src/asal/pipeline.py`. Run: `python scripts/data/run_sample_pipeline.py`.

## Stages

| # | Stage | v0.1 behaviour | Reason codes |
|---|---|---|---|
| 0 | download | `scripts/data/download_sample.py`: SHA-256-pinned manifest | `ChecksumMismatch` aborts |
| 1 | normalise | NFC; apostrophe variants → `'`; curly double quotes → `"`; zero-width/control removed; whitespace collapsed | n/a (change counts) |
| 2 | format_validation | required fields, non-empty text, registered source | `format_missing_fields`, `format_empty_text`, `unregistered_source` |
| 3 | language_identification | all backends predict; the primary backend gates; segment-level LID adds `segments` and a `code_switched` flag (annotation only) | `lid_not_somali` |
| 4 | quality_filter | see table below | `too_short`, `too_long`, `html_markup`, `url_heavy`, `excessive_punctuation`, `mojibake`, `replacement_character`, `repeated_lines`, `low_information`, `low_alpha_ratio` |
| 5 | pii_filter | redact e-mail and phone (`<EMAIL>`, `<PHONE>`) | n/a (redaction counts) |
| 6 | exact_dedup | casefold + whitespace-collapsed SHA-256; first occurrence wins; `within_source` / `cross_source` | `exact_duplicate` |
| 7 | near_dedup | MinHash (128 perms, word 5-shingles), LSH 32×4, confirmed with exact Jaccard ≥ 0.8 | `near_duplicate` |
| 8 | boilerplate_removal | drop lines (≥15 chars) recurring in ≥ max(3, 1%) of a source's docs | `boilerplate_only` |
| 9 | machine_translation_flagging | from registry (`machine_translated`); overridden to `suspected` by the URL heuristic (Somali language subdomain or `/so/` path on a non-.so domain) | n/a (flag only) |
| 10 | dialect_classification | **`unknown` for all records** (no labelled set yet) | n/a |
| 11 | domain_classification | source default from registry; `religion` when the Somali religious lexicon fires (≥1 hit and ≥5% of tokens) | n/a (flag only) |
| 12 | evaluation_decontamination | word n-gram overlap at n=13 and n=8 against all indexed eval sets | `eval_contamination` |
| 13 | license_validation | validation mode marks; training mode rejects unapproved sources | `license_not_approved` |
| 14 | provenance_attachment | builds the final record (below) | n/a |

Each stage writes `kept.jsonl`, `rejected.jsonl`, `stats.json`, `log.txt` under
`data/interim/<experiment-id>/NN_<stage>/`. The run writes `final_corpus.jsonl` and `summary.json`.

## Normalisation (Somali-specific)
- **Apostrophe = glottal stop** (`ba'an`, `lo'`, `su'aal`, `ta'siis`). It is part of the word.
  It is never stripped. U+2019, U+2018, U+02BC, U+02BB, U+0060, U+00B4, U+2032 and U+FF07 are
  mapped to U+0027 so one word has one spelling. The word tokenizer (`textutil.WORD_RE`) keeps
  apostrophes inside words and at the end of a word (`lo'`).
- **No case folding, no diacritic stripping** in the stored text. Casefolding is used only
  for hashing and matching.
- **Mojibake is detected, not repaired.** Automatic repair can corrupt valid text, so the
  document is rejected and the rejection is reviewable.
- Maay orthography: no Maay-specific rules yet. Maay uses letters and conventions that
  differ from Standard Somali; rules will be written with Maay-speaking annotators, not guessed.

## Quality thresholds (starting points, not tuned)
min 5 words; max 200K chars; >2 HTML tags; URL chars >20%; punctuation >25% of non-space
chars; any mojibake pattern; any U+FFFD; duplicate-line ratio >30% (≥3 lines);
unique-word ratio <0.2 (≥50 words); alphabetic ratio <0.6.

## Final record (provenance)
`id, text, source, source_record_id, derived_from, language, dialect, dialect_confidence,
domain, license{corpus_license, license_basis, status}, machine_translated, synthetic,
content_hash, pipeline_version, quality{metrics, lid (all backends), pii_redactions,
normalisation, boilerplate_lines_removed}, provenance{experiment_id, manifest_id, url,
pinned_revision, raw_file_sha256, split, meta, domain_basis, mt_basis}`

## Manual sampling (required at each major stage)
For every pipeline run on new data: draw ≥50 kept and ≥50 rejected records per stage with
rejections (seeded), have a native Somali speaker review them, and log reviewer, sample size,
seed, and findings (false-reject / false-keep rate) in RESEARCH_LOG.md. Thresholds change only
on such evidence.

Tooling: `python scripts/data/draw_review_sample.py draw <experiment-id> [--n 50 --seed 0]` writes
decision-shuffled sheets (one per stage with rejections, plus one per flag: suspected MT, religion)
to `data/samples/<id>/`. The reviewer fills `verdict` (correct / wrong / unsure) and `note`;
`... summarise <id>` writes wrong-decision rates with Wilson 95% intervals to
`evaluation/reports/reviews/<id>.json`. **Sheets exist for the v0.1 and NLLB runs; no review
has been done yet** (no reviewer available).

## Phase 1 work
Streaming/sharded execution; document vs sentence source classes (as in SomNLP-Corpus);
segment-level LID for code-switched documents; a document-level MT detector; domain
classifier; fuzzy boilerplate; GlotLID backend.
