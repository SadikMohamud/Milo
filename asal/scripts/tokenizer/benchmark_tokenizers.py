"""Measure tokenizers on the held-out Somali set.

Always measures the UTF-8 byte reference (sanity check for the harness).
Pass --hf-tokenizer PATH/tokenizer.json (repeatable) to measure real candidates
with the `tokenizers` library.

Usage: python scripts/tokenizer/benchmark_tokenizers.py [--hf-tokenizer tokenizer.json ...]
"""
import argparse
import json
import sys

import _bootstrap  # noqa: F401
from asal import experiments, paths, readers, tokenizer_metrics as tm
from asal.download import load_manifest


def held_out_texts():
    m = load_manifest(paths.MANIFESTS / "sample-v0.1.yaml")
    return [r["text"] for f in m["files"] if f["split"] == "test" for r in readers.read(f, paths.RAW)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf-tokenizer", action="append", default=[])
    args = ap.parse_args()
    texts = held_out_texts()
    results = [tm.report("utf8-bytes (reference)", tm.utf8_bytes_encode, texts, tm.utf8_bytes_decode)]
    for path in args.hf_tokenizer:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(path)
        results.append(tm.report(path, lambda t: tok.encode(t, add_special_tokens=False).ids, texts,
                                 lambda ids: tok.decode(ids)))
    exp_id, _ = experiments.register("TOK", "tokenizer-benchmark", config={"tokenizers": [r["tokenizer"] for r in results]},
                                     description="Tokenizer metrics on held-out Somali test splits.",
                                     dataset="sample-v0.1 test splits", track="not_applicable")
    out = paths.REPORTS / "data_intelligence_v0.1" / "tokenizer_benchmark.json"
    out.write_text(json.dumps({"experiment_id": exp_id, "results": results}, indent=2), encoding="utf-8")
    experiments.update(exp_id, status="completed", results=results)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
