"""Load registered evaluation sets (evaluation/decontamination/eval_sets.yaml) as items."""

from __future__ import annotations

from pathlib import Path

import yaml

from . import paths, readers


def load_registry(path: Path = paths.EVAL_SETS) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["eval_sets"]


def load_items(manifests: dict[str, dict], raw_dir: Path = paths.RAW, path: Path = paths.EVAL_SETS) -> tuple[list[dict], list[dict]]:
    """Return (items, pending_sets). Items: {"eval_set", "item_id", "text"}."""
    items, pending = [], []
    for es in load_registry(path):
        if es["status"] != "indexed":
            pending.append(es)
            continue
        manifest = manifests[es["manifest"]]
        entries = [f for f in manifest["files"] if f["source_id"] == es["registry_id"] and f["split"] == es["split"]]
        if len(entries) != 1:
            raise ValueError(f"eval set {es['id']}: expected one manifest file, found {len(entries)}")
        for rec in readers.read(entries[0], raw_dir):
            items.append({"eval_set": es["id"], "item_id": rec["source_record_id"], "text": rec["text"]})
    return items, pending
