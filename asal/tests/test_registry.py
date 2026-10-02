import copy

from asal import paths, registry


def test_all_registry_entries_valid():
    report = registry.validate()
    assert not report.errors, report.errors
    assert len(report.entries) >= 25


def test_somnlp_entry_matches_policy():
    e = registry.validate().entries["goobolabs-somnlp-corpus"]
    assert e["size"]["provider_reported"]["tokens"] == 1136027958
    assert e["size"]["provider_reported"]["previous_build_2026_09_02_tokens"] == 911824557
    assert e["size"]["verified"]["tokens"] == "unknown"
    assert e["provenance"]["aggregation"] is True
    assert {"CC100", "mC4", "MADLAD", "HPLT"} <= set(e["provenance"]["derived_from"])
    assert e["provenance"]["religious_text"] is True and "religion" in e["provenance"]["domains"]
    assert e["status"]["approved_for_training"] is False


def test_nothing_is_approved_for_training_in_v01():
    assert not any(e["status"]["approved_for_training"] for e in registry.validate().entries.values())


def _entry(eid):
    _, e = registry.load_entries()[eid]
    return copy.deepcopy(e)


def test_approval_without_verified_licence_is_an_error():
    e = _entry("masakhanews-som")
    e["status"]["approved_for_training"] = True
    findings = registry.policy_findings("masakhanews-som", e, set(), {})
    assert any(f.rule == "approval_requires_verification" for f in findings)


def test_verified_values_require_inspection():
    e = _entry("cc100-so")
    e["size"]["verified"]["tokens"] = 123
    findings = registry.policy_findings("cc100-so", e, set(), {})
    assert any(f.rule == "verified_requires_inspection" for f in findings)


def test_religious_text_needs_domain_and_review():
    e = _entry("cc100-so")
    e["provenance"]["religious_text"] = True
    rules = {f.rule for f in registry.policy_findings("cc100-so", e, set(), {})}
    assert {"religious_domain_tracked", "religious_sensitivity_review"} <= rules


def test_shared_upstreams_detect_double_counting():
    shared = registry.shared_upstreams(registry.validate().entries)
    assert {"goobolabs-somnlp-corpus", "unkadlabs-somaliweb-v1", "cc100-so"} <= set(shared["cc100-so"])


def test_schema_file_exists():
    assert paths.REGISTRY_SCHEMA.exists()
