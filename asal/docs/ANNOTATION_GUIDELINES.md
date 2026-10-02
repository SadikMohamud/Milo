# Annotation guidelines (draft v0.1)

Status: draft for discussion with native-speaker annotators. Not yet used.

## Dialect / variety labelling
Labels: `standard`, `benaadir`, `waqooyi` (Northern), `maay`, `mixed`, `unknown`.
- Label what the text *shows*, not where the author is thought to come from.
- Use `unknown` whenever you are not confident. `unknown` is a valid, useful answer.
- `mixed`: clear features of more than one variety in one text.
- Record the evidence: the words or forms that drove the decision (free text). This becomes
  the basis for the classifier's feature analysis and for disagreement review.
- Record confidence: 1 (guess) to 3 (certain).
- Maay is treated as its own language variety with its own orthography. Do not "correct" Maay
  spelling toward Standard Somali.

## Annotators
- Native speakers of the variety they label. Each annotator records which varieties they
  speak natively and fluently (stored separately from the data).
- At least two annotators per item for the dialect set; disagreements go to adjudication by
  a third annotator.
- Report Cohen's / Krippendorff's alpha per label before the set is used for training or evaluation.

## Code-switching
Mark Somali-English (or Somali-Arabic) switching at the span level: `[en]...[/en]`. Named
entities and loanwords that are established in Somali are not switches.

## Review of pipeline samples
For rejected/kept samples (docs/DATA_PIPELINE.md): mark each record `correct_decision`,
`wrong_decision`, or `unsure`, with a reason. Note Somali-specific problems (apostrophe damage,
broken orthography, machine-translated feel).

## Human evaluation of model output
Blind (model identity hidden, order randomised), at least two raters per item, rubric per task
(fluency, adequacy, dialect appropriateness, safety), agreement reported with scores.

## Ethics
Annotators are paid fairly, can withdraw, and are credited if they wish. No annotator is asked
to label content that identifies private individuals.
