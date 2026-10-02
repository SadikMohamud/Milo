# Data policy

1. **Register before use.** No data enters any pipeline without a registry entry.
2. **Provider claims ≠ facts.** Figures and quality statements from providers or secondary
   sources go in `provider_*` fields with a `claim_source`. Only Asal measurements go in
   `verified*` fields, and only for inspected entries (enforced).
3. **Unknown means unknown.** Use `unknown` or `review_required`; never fill a gap with an assumption.
4. **Approval for training** requires: licence, commercial use, redistribution and
   attribution verified *at source* (`license_basis: verified_in_source`); inspection and
   sampling; decontamination; resolved machine-translation status; a completed sensitivity
   review for religious text. Enforced by `asal.registry`.
5. **No dataset text in Git.** Only registry metadata, manifests (URLs + hashes) and
   text-free reports are committed.
6. **Personal data.** v0.1 redacts e-mail addresses and phone numbers (`<EMAIL>`, `<PHONE>`).
   Not yet covered: personal names, street addresses, ID and account numbers. Somali names
   overlap heavily with common words and place names, so name handling needs an evaluated
   method (the Goobo *Somali Names* resource is a candidate input).
7. **Speech is personal data.** New recordings need informed consent, recorded speaker
   metadata (dialect, age band, gender only where volunteered) and a retention policy before
   collection starts.
8. **Synthetic and machine-translated text** is flagged (`machine_translated`, `synthetic`)
   and never presented as human-authored (see docs/DATA_LICENSE_POLICY.md for model-output terms).
9. **Religious text** (e.g. QuranEnc, Tanzil, Bible translations in aggregates) is tracked
   as the `religion` domain so its corpus share is visible, and needs licence and sensitivity review.
10. **Community data** (e.g. dialect collection with universities, radio, community
    organisations) only under written, consented partnerships.
