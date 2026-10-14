# -*- coding: utf-8 -*-
"""E20 MinHash-LSH baseline (reviewer M3).

Two paired comparisons against the screen, identical corpora/protocols:

Part 1 (scale feasibility, extends Table II): MinHash-LSH over the same
item sets at E4's corpus scales, E4's planted protocol (donor + 40-item
sorted-set span + 300 distractor items).  Reports build time, memory,
query latency, donor recall as a function of the Jaccard threshold tau,
and the candidate volume each tau implies.

Part 2 (recall quality, extends Table III): regenerate the exact 337
planted queries of the e1 recall matrix from their stored seeds (the
reconstruction is verified against the stored n_span_events /
n_span_items), and measure whether the LSH candidate set contains the
donor at Jaccard >= tau, per cell.

Usage:
  python tools/e20_minhash_lsh.py --part scale [--n-queries 50]
  python tools/e20_minhash_lsh.py --part matrix [--tau 0.10]

Output: runs/e20/scale.jsonl, runs/e20/matrix.jsonl
"""
from __future__ import annotations

import argparse
import json
import pickle
import random
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, events_to_items  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from e1_matrix import load_events, span_seconds, apply, GRID, LENGTHS_S  # noqa: E402

OUTDIR = ROOT / "runs/e20"
E4_CACHE = ROOT / "data/processed/lmd/cache"
SEEDS = [7, 42, 99, 123, 2024]

# MinHash parameters: 128 permutations.  The band split is configurable:
# fewer rows per band lowers the S-curve threshold at the cost of candidate
# volume.  We report every configuration we try, including the floods.
NUM_PERM = 128
PRIME = (1 << 61) - 1
_ROWS_PER_BAND = 8  # default: 16 bands x 8 rows


def set_rows_per_band(r: int):
    global _ROWS_PER_BAND
    _ROWS_PER_BAND = r


class MinHashLSH:
    def __init__(self, sets: list[set[int]], seed: int = 13,
                 sig: np.ndarray | None = None):
        n_bands = NUM_PERM // _ROWS_PER_BAND
        rng = np.random.RandomState(seed)
        self.a = rng.randint(1, PRIME, size=NUM_PERM, dtype=np.int64) \
            .astype(np.uint64)
        self.b = rng.randint(0, PRIME, size=NUM_PERM, dtype=np.int64) \
            .astype(np.uint64)
        self.sets = sets
        self.n = len(sets)
        t0 = time.time()
        if sig is not None:
            # signatures precomputed (and cached on disk) for the full
            # corpus; only the prefix of length n belongs to this index
            self.sig = sig[:self.n]
            self.build_secs = 0.0
        else:
            self.sig = np.empty((self.n, NUM_PERM), dtype=np.int64)
            nonempty = [i for i, s in enumerate(sets) if s]
            for i in nonempty:
                items = np.fromiter(sets[i], dtype=np.int64)
                h = (items[None, :] * self.a[:, None] +
                     self.b[:, None]) % np.uint64(PRIME)
                self.sig[i] = h.min(axis=1).astype(np.int64)
            for i in range(self.n):
                if not sets[i]:
                    self.sig[i] = PRIME
            self.build_secs = time.time() - t0
        # band buckets
        self.buckets: list[dict[bytes, list[int]]] = []
        t0 = time.time()
        for bi in range(n_bands):
            d: dict[bytes, list[int]] = {}
            sl = self.sig[:, bi * _ROWS_PER_BAND:(bi + 1) * _ROWS_PER_BAND]
            for i in range(self.n):
                key = sl[i].tobytes()
                d.setdefault(key, []).append(i)
            self.buckets.append(d)
        self.bucket_secs = time.time() - t0

    def signature(self, qset: set[int]) -> np.ndarray:
        if not qset:
            return np.full(NUM_PERM, PRIME)
        items = np.fromiter(qset, dtype=np.int64)
        h = (items[None, :] * self.a[:, None] +
             self.b[:, None]) % np.uint64(PRIME)
        return h.min(axis=1).astype(np.int64)

    def query(self, qset: set[int]):
        """-> (candidates int array, ms)."""
        t0 = time.time()
        sig = self.signature(qset)
        cands: set[int] = set()
        n_bands = NUM_PERM // _ROWS_PER_BAND
        for bi in range(n_bands):
            key = sig[bi * _ROWS_PER_BAND:(bi + 1) * _ROWS_PER_BAND].tobytes()
            hit = self.buckets[bi].get(key)
            if hit:
                cands.update(hit)
        return np.fromiter(cands, dtype=np.int64), (time.time() - t0) * 1000

    def jaccard(self, qset: set[int], idx: np.ndarray) -> np.ndarray:
        out = np.zeros(len(idx))
        for j, i in enumerate(idx):
            s = self.sets[int(i)]
            if s:
                inter = len(qset & s)
                out[j] = inter / (len(qset) + len(s) - inter)
        return out


def load_cached(n=None):
    txns = []
    for cp in sorted(E4_CACHE.glob("*.pkl")):
        items_c, _ = pickle.loads(cp.read_bytes())
        txns.extend(items_c)
        if n and len(txns) >= n:
            break
    return txns[:n] if n else txns


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


def part_scale(args) -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / "scale.jsonl"
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            if ln.strip():
                done.add((json.loads(ln)["n_pieces"],
                          json.loads(ln)["tau"]))
    all_txns = load_cached()
    rng_perm = random.Random(42)
    perm = rng_perm.sample(range(len(all_txns)), len(all_txns))
    txns_full = [all_txns[i] for i in perm]
    # signatures depend only on the corpus, not on the prefix size: compute
    # once for the full permuted corpus and cache on disk so reruns only pay
    # the O(n) bucket construction per size
    sig_cache = OUTDIR / "sig.npy"
    if sig_cache.exists():
        sig_full = np.load(sig_cache)
        if len(sig_full) == len(txns_full):
            sig_secs = None
        else:  # partial cache from an interrupted run: resume
            sig_full = None
            sig_secs = None
    else:
        sig_full = None
        sig_secs = None
    if sig_full is None:
        # compute in chunks of 20k, saving after each chunk so an
        # interrupted run resumes instead of restarting
        start = 0
        if sig_cache.exists():
            prev = np.load(sig_cache)
            if len(prev) < len(txns_full):
                sig_part = prev
                start = len(prev)
        else:
            sig_part = np.empty((0, NUM_PERM), dtype=np.int64)
        probe = MinHashLSH.__new__(MinHashLSH)
        rng = np.random.RandomState(13)
        probe.a = rng.randint(1, PRIME, size=NUM_PERM,
                              dtype=np.int64).astype(np.uint64)
        probe.b = rng.randint(0, PRIME, size=NUM_PERM,
                              dtype=np.int64).astype(np.uint64)
        t0 = time.time()
        CH = 20000
        for lo in range(start, len(txns_full), CH):
            hi = min(lo + CH, len(txns_full))
            blk = np.empty((hi - lo, NUM_PERM), dtype=np.int64)
            for j, i in enumerate(range(lo, hi)):
                s = txns_full[i]
                if s:
                    items = np.fromiter(s, dtype=np.int64)
                    h = (items[None, :] * probe.a[:, None] +
                         probe.b[:, None]) % np.uint64(PRIME)
                    blk[j] = h.min(axis=1).astype(np.int64)
                else:
                    blk[j] = PRIME
            sig_part = np.vstack([sig_part, blk])
            np.save(sig_cache, sig_part)
            print(f"signatures {len(sig_part)}/{len(txns_full)} "
                  f"({time.time() - t0:.0f}s)", flush=True)
        sig_full = sig_part
        sig_secs = time.time() - t0
        print(f"signatures computed in {sig_secs:.0f}s and cached",
              flush=True)
    taus = [0.05, 0.10, 0.20]
    # sizes mirror Table II (e4 scaling) exactly
    for n in [1000, 3000, 10000, 25357, 30000, 44371, 50000, 50709,
              69723, 100000, len(txns_full)]:
        if all((n, t) in done for t in taus):
            print(f"N={n}: already done, skipped", flush=True)
            continue
        txns = txns_full[:n]
        tracemalloc.start()
        lsh = MinHashLSH(txns, sig=sig_full)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rng = random.Random(99)
        lat = []
        stats = {t: {"ok": 0, "cand": []} for t in taus}
        nq = 0
        for _ in range(args.n_queries):
            pq = planted_query(txns, rng)
            if pq is None:
                continue
            donor, q = pq
            nq += 1
            cands, ms = lsh.query(q)
            lat.append(ms)
            jac = lsh.jaccard(q, cands)
            for t in taus:
                stats[t]["ok"] += int(jac[donor] >= t) if len(jac) else 0
                stats[t]["cand"].append(int((jac >= t).sum()))
        lat.sort()
        for t in taus:
            if (n, t) in done:
                continue
            row = {
                "n_pieces": n, "tau": t,
                "build_secs": round(sig_secs
                                    if sig_secs is not None
                                    else lsh.build_secs, 2),
                "bucket_secs": round(lsh.bucket_secs, 2),
                "sig_mem_mb": round(lsh.sig.nbytes / 1e6, 1),
                "peak_mem_mb": round(peak / 1e6, 1),
                "query_p50_ms": round(lat[len(lat) // 2], 2) if lat else None,
                "query_p95_ms": round(lat[int(len(lat) * .95)], 2)
                if lat else None,
                "recall": f"{stats[t]['ok']}/{nq}",
                "cand_p50": int(np.median(stats[t]["cand"])) if nq else 0,
            }
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        p50 = lat[len(lat) // 2] if lat else float("nan")
        bs = sig_secs if sig_secs is not None else lsh.build_secs
        print(f"N={n}: build {bs:.0f}s "
              f"query p50 {p50:.2f}ms "
              f"recall@0.1 {stats[0.10]['ok']}/{nq}", flush=True)
    return 0


def part_matrix(args) -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / "matrix.jsonl"
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            if ln.strip():
                d = json.loads(ln)
                done.add((d["transform"], json.dumps(
                    d["strength"], sort_keys=True),
                    d["length_s"], d["seed"], d["tau"],
                    d.get("rpb", 8)))
    set_rows_per_band(args.rows_per_band)
    cfg = EncodingConfig(use_channel=False)
    shard = ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet"
    ev_corpus = load_events(shard, 1000)  # e1 matrix was built with the
    # default 1,000-piece corpus; reconstruction verified below
    txns = [events_to_items(sorted(ev, key=lambda e: (e.onset_tick,
                                                      e.pitch)),
                            1000, cfg)[0] for ev in ev_corpus]
    lsh = MinHashLSH(txns)
    print(f"corpus={len(txns)} lsh build {lsh.build_secs:.0f}s",
          flush=True)
    rows = [json.loads(l) for l in (ROOT / "runs/e1/matrix.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    mismatches = 0
    for r in rows:
        key = (r["transform"], json.dumps(r["strength"], sort_keys=True),
               r["length_s"], r["seed"], args.tau, args.rows_per_band)
        if key in done:
            continue
        rng = random.Random(r["seed"] * 1000 + r["length_s"])
        donor = rng.randrange(len(ev_corpus))
        span = span_seconds(ev_corpus[donor], rng, r["length_s"])
        mutated = apply(r["transform"], span, rng, r["strength"])
        q_items, _ = events_to_items(
            sorted(mutated, key=lambda e: (e.onset_tick, e.pitch)),
            1000, cfg)
        if len(span) != r["n_span_events"] or len(q_items) != \
                r["n_span_items"]:
            mismatches += 1
            continue
        cands, ms = lsh.query(set(q_items))
        candset = set(int(c) for c in cands)
        jac = lsh.jaccard(set(q_items), cands)
        n_ge = int((jac >= args.tau).sum())
        ds = txns[donor]
        inter = len(set(q_items) & ds)
        dj = inter / (len(q_items) + len(ds) - inter) if ds else 0.0
        hit = (donor in candset) and dj >= args.tau
        rec = {"transform": r["transform"], "strength": r["strength"],
               "length_s": r["length_s"], "seed": r["seed"],
               "tau": args.tau, "rpb": args.rows_per_band, "hit": hit,
               "donor_jaccard": round(dj, 4),
               "donor_in_cands": donor in candset,
               "n_candidates": int(len(cands)),
               "n_ge_tau": n_ge,
               "screen_hit": r["hit"], "n_span_items": len(q_items)}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    print(f"done; reconstruction mismatches: {mismatches}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["scale", "matrix"], required=True)
    ap.add_argument("--n-queries", type=int, default=50)
    ap.add_argument("--tau", type=float, default=0.10)
    ap.add_argument("--rows-per-band", type=int, default=8,
                    help="rows per LSH band (128/rows bands)")
    args = ap.parse_args()
    if args.part == "scale":
        return part_scale(args)
    return part_matrix(args)


if __name__ == "__main__":
    sys.exit(main())
