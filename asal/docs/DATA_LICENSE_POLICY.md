# Data licence policy

## The licence ledger
The registry *is* the licence ledger. For every dataset it records `corpus_license`,
`license_basis` (`verified_in_source` | `provider_claim` | `secondary_source` | `unknown`),
`license_claim_source`, `per_source_licenses` for aggregates, `commercial_use`,
`redistribution`, `attribution_required` and free-text `terms_notes`.
`data/registry/CATALOGUE.md` renders it as a table.

## Rules
- "Open" does not mean unrestricted. Check each of: use for training, commercial use,
  redistribution of the data, redistribution of derived models, attribution, share-alike.
- Aggregated corpora inherit *all* upstream terms. A record keeps its upstream licence.
- Conflicting claims are recorded, not resolved by preference. For example, XL-Sum is listed
  as CC-BY-4.0 by Goobo Labs, while Asal maintainers recalled a non-commercial licence. It
  stays `review_required` until checked at source.
- Web crawls (Common Crawl derivatives): the packaging licence (e.g. CC0, ODC-BY) does not
  transfer rights in the underlying page content. Record this in `terms_notes`.
- Model outputs: do not assume proprietary model outputs may be used to train a competing
  model or be redistributed. Check the provider's terms per model and record them with the
  synthetic data's metadata.
- Religious translations: copyright usually sits with the translator or publisher, so
  check each translation separately.

## Verification procedure (per dataset)
1. Open the licence at its primary location (dataset card, LICENSE file, publisher terms).
2. Record the URL and access date in `license_claim_source`, and set
   `license_basis: verified_in_source`.
3. Fill commercial use / redistribution / attribution from the text, not from memory.
4. A second maintainer reviews the change before `approved_for_training` can be set.

## v0.1 state
Only one entry has a licence verified at source: the Unkad awesome list (CC0-1.0), which is
not a corpus. SIB-200's repository licence (Apache-2.0) was read, but the sentences are
FLORES-200 text with their own licence, so the data licence is `review_required`.
