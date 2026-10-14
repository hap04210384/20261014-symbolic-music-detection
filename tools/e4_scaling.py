# -*- coding: utf-8 -*-
"""E4 scaling curve: corpus size vs {index build time, memory, query latency,
planted recall} for the containment detector, plus set-Jaccard scan baseline.

Incremental: results appended to runs/e4/scaling.jsonl; N values already
present are skipped (safe to re-run after adding shards).

Scales: fixed-seed subsample of whatever is cached in
data/processed/lmd/cache (sorted shard order -> cumulative).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.detector import CorpusIndex  # noqa: E402

CACHE = ROOT / "data/processed/lmd/cache"
OUT = ROOT / "runs/e4/scaling.jsonl"

SCALES = [1000, 3000, 10000, 30000, 50000, 100000, 174300]


def load_cached() -> list[set[int]]:
    import pickle
    txns: list[set[int]] = []
    for cp in sorted(CACHE.glob("*.pkl")):
        items_c, _ = pickle.loads(cp.read_bytes())
        txns.extend(items_c)
    return txns


def planted_query(txns, rng, L=40):
    donor = rng.randrange(len(txns))
    src = sorted(txns[donor])
    if len(src) < L + 25:
        return None
    st = rng.randrange(len(src) - L)
    span = set(src[st:st + L])
    if len(span) < 25:
        return None
    return donor, span | set(rng.sample(range(1, 300000), 300))


def run_ours(txns, n_queries=50):
    tracemalloc.start()
    t0 = time.time()
    index = CorpusIndex(txns)
    build_t = time.time() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rng = random.Random(99)
    lat, ok, done = [], 0, 0
    for _ in range(n_queries):
        pq = planted_query(txns, rng)
        if pq is None:
            continue
        donor, q = pq
        done += 1
        t0 = time.time()
        r = index.detect(q, min_evidence=25)
        lat.append(time.time() - t0)
        ok += any(h.piece == donor for h in r.hits)
    lat.sort()
    return {
        "build_secs": round(build_t, 3),
        "peak_mem_mb": round(peak / 1e6, 1),
        "postings": len(index.postings),
        "query_p50_ms": round(lat[len(lat) // 2] * 1000, 2) if lat else None,
        "query_p95_ms": round(lat[int(len(lat) * .95)] * 1000, 2) if lat else None,
        "recall": f"{ok}/{done}",
    }


def run_jaccard_scan(txns, n_queries=20):
    """Baseline: per-query scan of the whole corpus with set Jaccard."""
    rng = random.Random(98)
    lat, ok, done = [], 0, 0
    for _ in range(n_queries):
        pq = planted_query(txns, rng)
        if pq is None:
            continue
        donor, q = pq
        done += 1
        t0 = time.time()
        best, best_i = -1.0, -1
        for i, c in enumerate(txns):
            inter = len(q & c)
            j = inter / (len(q) + len(c) - inter)
            if j > best:
                best, best_i = j, i
        lat.append(time.time() - t0)
        ok += (best_i == donor)
    lat.sort()
    return {
        "query_p50_ms": round(lat[len(lat) // 2] * 1000, 1) if lat else None,
        "top1_acc": f"{ok}/{done}",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-queries", type=int, default=50)
    args = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    done_scales = set()
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            if ln.strip():
                done_scales.add(json.loads(ln)["n_pieces"])

    all_txns = load_cached()
    print(f"cached corpus: {len(all_txns)} pieces")
    scales = list(SCALES)
    if len(all_txns) not in scales:
        scales.append(len(all_txns))
        scales.sort()
    rng = random.Random(42)
    perm = rng.sample(range(len(all_txns)), len(all_txns))  # fixed subsample order

    for n in scales:
        if n > len(all_txns) or n in done_scales:
            continue
        txns = [all_txns[i] for i in perm[:n]]
        row = {"n_pieces": n}
        t0 = time.time()
        row["ours"] = run_ours(txns, args.n_queries)
        row["ours_total_secs"] = round(time.time() - t0, 1)
        if n <= 10000:
            t0 = time.time()
            row["jaccard_scan"] = run_jaccard_scan(txns, 20)
            row["jaccard_total_secs"] = round(time.time() - t0, 1)
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(f"N={n}: ours build {row['ours']['build_secs']}s "
              f"p50 {row['ours']['query_p50_ms']}ms "
              f"recall {row['ours']['recall']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
