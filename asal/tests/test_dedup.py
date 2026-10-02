import random
import string

from asal import dedup

random.seed(7)
VOCAB = ["".join(random.choices(string.ascii_lowercase, k=6)) for _ in range(2000)]


def doc(n=120, start=0):
    return " ".join(VOCAB[start:start + n])


def rec(i, source, text):
    return {"id": f"{source}:{i}", "source": source, "text": text}


def test_exact_within_and_across_sources():
    recs = [rec(1, "a", doc()), rec(2, "a", "  " + doc().upper()), rec(3, "b", doc()), rec(4, "b", doc(start=500))]
    res = dedup.exact_dedup(recs)
    assert [r["id"] for r in res.kept] == ["a:1", "b:4"]
    assert res.stats["removed_within_source"] == 1
    assert res.stats["removed_cross_source"] == 1
    assert res.stats["removed_by_source_pair"] == {"a->a": 1, "b->a": 1}


def test_near_duplicate_across_sources():
    base = doc(200)
    edited = base.replace(VOCAB[50], "kalemadan", 1) + " dhammaad"
    recs = [rec(1, "cc100", base), rec(2, "somnlp", edited), rec(3, "somnlp", doc(200, start=1000))]
    res = dedup.near_dedup(recs, threshold=0.8)
    assert [r["id"] for r in res.kept] == ["cc100:1", "somnlp:3"]
    assert res.removed[0]["scope"] == "cross_source"
    assert res.removed[0]["jaccard"] >= 0.8


def test_near_dedup_keeps_different_docs():
    recs = [rec(i, "a", doc(150, start=i * 150)) for i in range(8)]
    assert len(dedup.near_dedup(recs).kept) == 8


def test_minhash_estimates_jaccard():
    a = dedup.shingles(doc(300))
    b = dedup.shingles(doc(300, start=60))
    true_j = dedup.jaccard(a, b)
    est = (dedup.MinHasher(256, seed=3).signature(a) == dedup.MinHasher(256, seed=3).signature(b)).mean()
    assert abs(est - true_j) < 0.1
