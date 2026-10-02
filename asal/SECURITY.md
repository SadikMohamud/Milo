# Security and data protection

## Reporting
Report vulnerabilities or data-protection concerns privately to the project maintainers
(contact to be set by the project owner). Do not open a public issue for personal data
found in a dataset.

## Scope
- **Personal data.** Web text and speech contain personal data. The pipeline redacts
  e-mail addresses and phone numbers (docs/DATA_POLICY.md lists what is not yet covered).
  Speech recordings require informed consent and a retention policy (docs/DATA_POLICY.md).
- **Secrets.** Never commit tokens (e.g. `HF_TOKEN`). Use environment variables.
- **Data in Git.** Dataset text is never committed. `.gitignore` excludes `data/raw`,
  `interim`, `processed`, `rejected` and `samples`.
- **Model safety.** Safety evaluation sets (e.g. SomaliBench) are evaluation-only and must
  never be used as training data.
- **Downloads.** Every download is pinned by SHA-256 in a manifest; a mismatch aborts.
