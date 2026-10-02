# AsalBench (planned)

Areas: language, translation, reasoning, knowledge, dialects, conversation, summarisation,
NER, QA, safety, coding.

Each item: `id, source, license, task, expected answer / acceptable variants, difficulty,
dialect, domain, author (human, or synthetic with model name/version/date/prompt),
native_speaker_review_status`.

A held-out portion is kept **private** and never published, so results cannot be contaminated
by models trained on public copies. Every AsalBench set is registered in
`evaluation/decontamination/eval_sets.yaml` before it is used. Per the Unkad Labs gap analysis,
there is no Somali knowledge/reasoning benchmark yet, so that is a priority to build with
native speakers rather than by machine-translating English benchmarks.
