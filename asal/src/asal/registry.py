"""Dataset registry: loading, schema validation and policy rules.

The JSON Schema (data/registry/schema.json) checks structure. The policy rules
below check things a schema cannot express, e.g. "a dataset cannot be approved
for training while its licence is unverified".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

from . import paths

UNRESOLVED = {"unknown", "review_required", "mixed-upstream", "partial"}
ALIASES_FILE = "aliases.yaml"


def load_aliases(registry_dir: Path = paths.REGISTRY_DIR) -> dict[str, str]:
    path = registry_dir / ALIASES_FILE
    if not path.exists():
        return {}
    return {str(k).lower(): v for k, v in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).items()}


def _is_placeholder(upstream: str) -> bool:
    return upstream.startswith("review_required") or upstream == "unknown"


@dataclass
class Finding:
    entry: str
    level: str  # "error" | "warning" | "info"
    rule: str
    message: str


@dataclass
class RegistryReport:
    entries: dict[str, dict] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]


def load_entries(registry_dir: Path = paths.REGISTRY_DIR) -> dict[str, tuple[Path, dict]]:
    out = {}
    for path in sorted(registry_dir.glob("*.yaml")):
        if path.name == ALIASES_FILE:
            continue
        with path.open(encoding="utf-8") as fh:
            out[path.stem] = (path, yaml.safe_load(fh))
    return out


def _all_values(obj) -> list:
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in _all_values(x)]
    if isinstance(obj, list):
        return [v for x in obj for v in _all_values(x)]
    return [obj]


def policy_findings(entry_id: str, e: dict, known_ids: set[str], aliases: dict[str, str]) -> list[Finding]:
    f: list[Finding] = []

    def add(level, rule, msg):
        f.append(Finding(entry_id, level, rule, msg))

    if e.get("id") != entry_id:
        add("error", "id_matches_filename", f"id '{e.get('id')}' differs from filename '{entry_id}'")

    status, lic, prov = e["status"], e["license"], e["provenance"]

    if status["approved_for_training"]:
        problems = []
        for k in ("corpus_license", "commercial_use", "redistribution", "attribution_required"):
            if lic.get(k) in UNRESOLVED:
                problems.append(f"license.{k}={lic.get(k)}")
        if lic.get("license_basis") != "verified_in_source":
            problems.append(f"license.license_basis={lic.get('license_basis')}")
        if not (status["inspected"] and status["sampled"]):
            problems.append("not inspected and sampled")
        if e["evaluation_overlap"]["decontaminated"] is not True:
            problems.append("not decontaminated")
        if prov["machine_translated"] in ("unknown", "review_required"):
            problems.append("machine_translated unresolved")
        if prov["religious_text"] is True and status.get("sensitivity_review") != "done":
            problems.append("religious text without completed sensitivity review")
        if problems:
            add("error", "approval_requires_verification", "approved_for_training but: " + "; ".join(problems))

    if not status["inspected"]:
        size_verified = {k: v for k, v in e["size"]["verified"].items() if k != "measured_by"}
        verified_values = _all_values(size_verified) + _all_values(e["quality"]["verified_by_asal"])
        if any(v != "unknown" for v in verified_values):
            add("error", "verified_requires_inspection", "verified values set on an entry that is not inspected")
        if e["dialects"]["observed"] != "unknown":
            add("error", "verified_requires_inspection", "dialects.observed set on an entry that is not inspected")

    if status["sampled"] and not status["inspected"]:
        add("error", "sampled_implies_inspected", "sampled=true requires inspected=true")

    if prov["aggregation"] is True and not prov["derived_from"]:
        add("error", "aggregation_has_sources", "aggregation=true but derived_from is empty")

    if prov["religious_text"] in (True, "partial"):
        if "religion" not in prov["domains"]:
            add("error", "religious_domain_tracked", "religious text must list 'religion' in provenance.domains")
        if status.get("sensitivity_review") in (None, "not_required"):
            add("error", "religious_sensitivity_review", "religious text requires status.sensitivity_review")

    if prov["machine_translated"] in (True, "partial") and "machine_translated_basis" not in prov:
        add("warning", "mt_basis", "machine_translated set without machine_translated_basis")

    if lic["license_basis"] in ("provider_claim", "secondary_source") and not lic.get("license_claim_source"):
        add("warning", "license_claim_source", "licence claim recorded without license_claim_source")

    for upstream in prov["derived_from"]:
        if _is_placeholder(upstream):
            add("info", "derived_from_unresolved", f"upstream composition not yet known ('{upstream}')")
        elif upstream not in known_ids and upstream.lower() not in aliases:
            add("info", "derived_from_unregistered", f"upstream '{upstream}' has no registry entry yet")

    return f


def validate(registry_dir: Path = paths.REGISTRY_DIR, schema_path: Path = paths.REGISTRY_SCHEMA) -> RegistryReport:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    loaded = load_entries(registry_dir)
    report = RegistryReport()
    aliases = load_aliases(registry_dir)
    for entry_id, (_, e) in loaded.items():
        if isinstance(e, dict):
            aliases[str(e.get("name", "")).lower()] = entry_id
            aliases[entry_id] = entry_id
    for target in aliases.values():
        if target not in loaded:
            report.findings.append(Finding(ALIASES_FILE, "error", "alias_target", f"alias target '{target}' missing"))
    for entry_id, (path, e) in loaded.items():
        errs = sorted(validator.iter_errors(e), key=lambda x: list(x.path))
        for err in errs:
            loc = "/".join(str(p) for p in err.path) or "<root>"
            report.findings.append(Finding(entry_id, "error", "schema", f"{loc}: {err.message}"))
        if errs:
            continue
        report.entries[entry_id] = e
        report.findings.extend(policy_findings(entry_id, e, set(loaded), aliases))
    return report


def aggregation_graph(entries: dict[str, dict]) -> dict[str, list[str]]:
    """entry id -> upstream names, for reporting overlap between aggregated corpora."""
    return {eid: list(e["provenance"]["derived_from"]) for eid, e in entries.items()}


def shared_upstreams(entries: dict[str, dict], aliases: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Canonical upstream -> registry entries containing it (directly or by being it).

    More than one entry means their sizes must not be added: the same text is
    probably present in each.
    """
    aliases = load_aliases() if aliases is None else aliases
    out: dict[str, set[str]] = {}
    for eid, ups in aggregation_graph(entries).items():
        for u in ups:
            if _is_placeholder(u):
                continue
            canonical = aliases.get(u.lower(), u)
            out.setdefault(canonical, set()).add(eid)
            if canonical in entries:
                out[canonical].add(canonical)
    return {u: sorted(v) for u, v in sorted(out.items()) if len(v) > 1}
