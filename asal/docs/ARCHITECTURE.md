# Architecture

```text
asal/
├── src/asal/             importable library (all logic lives here, all of it tested)
│   ├── registry.py       dataset registry: schema + policy rules + aggregation graph
│   ├── download.py       manifest-driven, SHA-256-verified downloads
│   ├── readers.py        raw files -> records
│   ├── normalize.py      Somali-aware normalisation
│   ├── quality.py        quality checks with reason codes
│   ├── pii.py            e-mail / phone redaction
│   ├── lid.py            LID backends: asal-heuristic, lingua, fastText lid.176, GlotLID
│   ├── dedup.py          exact + MinHash/LSH near dedup, within and across sources
│   ├── decontam.py       n-gram evaluation decontamination
│   ├── evalsets.py       registered evaluation sets -> items
│   ├── pipeline.py       14-stage pipeline orchestrator
│   ├── stats.py          corpus statistics
│   ├── tokenizer_metrics.py
│   └── experiments.py    experiment IDs, run records, training guard
├── scripts/<area>/       command-line wrappers (no logic of their own)
├── data/registry/        one YAML per dataset + schema.json + aliases.yaml + CATALOGUE.md
├── data/manifests/       pinned download manifests
├── data/{raw,interim,processed,rejected,samples}/   never committed
├── evaluation/decontamination/eval_sets.yaml        evaluation-set registry
├── evaluation/reports/   text-free result reports
├── experiments/runs/     one run.yaml per experiment
├── tokenizer/  models/  training/  speech/  runtime/   per-track folders (spec layout)
└── tests/                pytest suite (plus tokenizer/tests, training/tests)
```

## Data flow

```text
manifest ──download──> data/raw ──readers──> records ──pipeline──> data/interim/<exp-id>/NN_stage/
                                                         │                  kept / rejected / stats / log
registry ────────────────────────────────────────────────┤
eval_sets.yaml ──evalsets──> EvalIndex ──────────────────┘──> final_corpus.jsonl + summary.json
                                                               └─> evaluation/reports (no text)
```

## Design decisions
- **One library, thin scripts.** Avoids duplicated logic between tokenizer/, training/ and
  data/ code, and makes everything unit-testable.
- **Registry as data, rules as code.** JSON Schema checks structure; `registry.policy_findings`
  checks things a schema cannot express (approval requires verified licence, verified values
  require inspection, religious text needs domain + sensitivity review).
- **Stages are pure functions over record lists.** v0.1 holds the sample in memory. Phase 1
  will need streaming/sharded execution at corpus scale (about 8M documents). The stage
  interface was kept simple so it can be wrapped, not rewritten.
- **Backends behind protocols.** LID and tokenizers are pluggable so tools are compared on
  identical items.
- **Model and runtime are separate** (runtime/): inference, RAG, tools and agents depend on
  a model interface, not on a specific checkpoint.

## Known scale limits (to fix in Phase 1)
In-memory stages; pure-Python shingling; Lingua's ~1 GB memory footprint; exact-line boilerplate.
