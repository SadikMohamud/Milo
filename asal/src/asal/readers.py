"""Turn raw downloaded files into records: {id, source, source_record_id, text, meta}.

Readers know the file layout of each upstream format. They do no cleaning;
that is the pipeline's job.
"""

from __future__ import annotations

import csv
from pathlib import Path

csv.field_size_limit(1 << 30)


def read_tsv(entry: dict, raw_dir: Path) -> list[dict]:
    """Read a TSV file described by a manifest entry.

    Manifest keys used: path, source_id, split, text_fields, id_field (optional),
    meta_fields (optional).
    """
    path = raw_dir / entry["path"]
    text_fields = entry["text_fields"]
    id_field = entry.get("id_field")
    meta_fields = entry.get("meta_fields", [])
    records = []
    with path.open(encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh, delimiter="\t")):
            parts = [row[f].strip() for f in text_fields if row.get(f) and row[f].strip()]
            rid = f"{entry['split']}-{row[id_field] if id_field else i}"
            records.append({
                "id": f"{entry['source_id']}:{rid}",
                "source": entry["source_id"],
                "source_record_id": rid,
                "split": entry["split"],
                "text": "\n\n".join(parts),
                "meta": {f: row.get(f) for f in meta_fields},
                "raw_file_sha256": entry.get("sha256"),
            })
    return records


READERS = {"tsv": read_tsv}


def read(entry: dict, raw_dir: Path) -> list[dict]:
    return READERS[entry["format"]](entry, raw_dir)
