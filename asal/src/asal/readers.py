"""Turn raw downloaded files into records: {id, source, source_record_id, text, meta}.

Readers know the file layout of each upstream format. They do no cleaning;
that is the pipeline's job.
"""

from __future__ import annotations

import csv
import zlib
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


NLLB_COLUMNS = ["eng", "som", "laser_score", "eng_lid_score", "som_lid_score",
                "eng_source", "eng_url", "som_source", "som_url"]


def read_nllb_gz_prefix(entry: dict, raw_dir: Path) -> list[dict]:
    """Read the Somali side of an NLLB mined-bitext file from a gzip *prefix*.

    The file is a single gzip stream, so a byte-range prefix decompresses to a
    prefix of the text; the last (truncated) line is dropped. Columns follow
    NLLB_COLUMNS. Record ids are 0-based line numbers in the upstream file.
    """
    raw = (raw_dir / entry["path"]).read_bytes()
    text = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw).decode("utf-8", errors="replace")
    lines = text.split("\n")[:-1]  # last line may be truncated
    records = []
    for i, line in enumerate(lines):
        cols = line.split("\t")
        if len(cols) < 5:
            continue
        row = dict(zip(NLLB_COLUMNS, cols))
        rid = f"{entry['split']}-{i}"
        url = row.get("som_url", "_")
        records.append({
            "id": f"{entry['source_id']}:{rid}",
            "source": entry["source_id"],
            "source_record_id": rid,
            "split": entry["split"],
            "text": row["som"].strip(),
            "meta": {"laser_score": float(row["laser_score"]), "som_lid_score": float(row["som_lid_score"]),
                     "som_source": row.get("som_source"), "url": None if url in ("_", "") else url},
            "raw_file_sha256": entry.get("sha256"),
        })
    return records


def _nllb_record(entry: dict, rid: str, cols: list[str]) -> dict | None:
    if len(cols) < 5:
        return None
    row = dict(zip(NLLB_COLUMNS, cols))
    url = row.get("som_url", "_")
    return {
        "id": f"{entry['source_id']}:{rid}",
        "source": entry["source_id"],
        "source_record_id": rid,
        "split": entry["split"],
        "text": row["som"].strip(),
        "meta": {"laser_score": float(row["laser_score"]), "som_lid_score": float(row["som_lid_score"]),
                 "som_source": row.get("som_source"), "url": None if url in ("_", "") else url},
        "raw_file_sha256": entry.get("sha256"),
    }


def read_nllb_line_sample(entry: dict, raw_dir: Path) -> list[dict]:
    """Read a hash_line_sample of NLLB: gzip TSV of ``<upstream line number>\t<NLLB line>``."""
    import gzip

    records = []
    with gzip.open(raw_dir / entry["path"], "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            lineno, _, rest = line.rstrip("\n").partition("\t")
            rec = _nllb_record(entry, f"line-{lineno}", rest.split("\t"))
            if rec:
                records.append(rec)
    return records


READERS = {"tsv": read_tsv, "nllb_gz_prefix": read_nllb_gz_prefix, "nllb_line_sample": read_nllb_line_sample}


def read(entry: dict, raw_dir: Path) -> list[dict]:
    return READERS[entry["format"]](entry, raw_dir)
