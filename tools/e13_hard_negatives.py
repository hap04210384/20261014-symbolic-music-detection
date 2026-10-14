# -*- coding: utf-8 -*-
"""E1.3 hard negatives v2: style-similar non-copy pairs -> FP characterization.

Rationale: random negative pairs understate FP pressure.  For each planted
query we build a pool of the K most *style-similar* corpus pieces
(12-dim duration-weighted pitch-class histogram + register + dynamics,
cosine similarity) and decontaminate it: any pool piece whose verbatim
evidence against the whole donor piece is high (>= DUP_THRESHOLD shared
items) is an actual duplicate/cover of the same song, i.e. a true positive,
and is dropped from the negative pool (next-nearest refill).

v2 (2026-10-12): v1 found tolerant fragment-level FP = 93% at
min_evidence = |q|/2 — no threshold reaches <5% FP without destroying
recall (FP-recall tradeoff measured in runs/e13/hard_negatives.jsonl v1).
This is a *finding*: tolerant item-set containment is a screening layer,
not a decision layer.  v2 therefore measures screening-quality metrics
for BOTH layers (tolerant k=(2,1,1) and verbatim k=0):
  - donor full-corpus rank and top-K inclusion (the screening metric)
  - fragment-level FP per layer on the style-similar pool
  - donor-vs-pool score margins per layer
Corpus: first CORPUS_PIECES pieces of shard 0.  Output: runs/e13/v2_*.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, events_to_items  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from e1_matrix import load_events, span_seconds, apply  # noqa: E402

OUTDIR = ROOT / "runs/e13"
CORPUS_PIECES = 3000
POOL_K = 20
DUP_THRESHOLD = 30
LENGTHS_S = [4, 8, 16]


def encode(ev, cfg):
    return events_to_items(sorted(ev, key=lambda e: (e.onset_tick, e.pitch)),
                           1000, cfg)[0]


def piece_features(ev_corpus) -> np.ndarray:
    feats = np.zeros((len(ev_corpus), 14), dtype=np.float64)
    for i, ev in enumerate(ev_corpus):
        if not ev:
            continue
        dur = np.array([max(1, e.duration_tick) for e in ev], dtype=np.float64)
        pc = np.array([e.pitch % 12 for e in ev])
        h = np.bincount(pc, weights=dur, minlength=12)
        n = h.sum()
        if n > 0:
            h /= n
        feats[i, :12] = h
        feats[i, 12] = float(np.mean([e.pitch for e in ev])) / 127.0
        feats[i, 13] = float(np.mean([e.velocity for e in ev])) / 127.0
    norms = np.linalg.norm(feats, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return feats / norms


def rank_of(score: int, scores: np.ndarray, donor: int) -> int:
    """1 + #pieces with strictly higher score (ties broken by index)."""
    return int(1 + np.count_nonzero(
        (scores > score) | ((scores == score) &
                            (np.arange(len(scores)) < donor))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--donors", type=int, default=80)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    cfg = EncodingConfig(use_channel=False)
    ev_corpus = load_events(
        ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet",
        CORPUS_PIECES)
    txns = [encode(ev, cfg) for ev in ev_corpus]
    index = CorpusIndex(txns)
    feats = piece_features(ev_corpus)
    n_pieces = len(txns)
    all_ids = set(range(n_pieces))
    print(f"corpus: {n_pieces} pieces", flush=True)

    rng = random.Random(args.seed)
    donor_ids = [i for i in range(n_pieces) if len(txns[i]) >= 60]
    rng.shuffle(donor_ids)
    donor_ids = donor_ids[:args.donors]

    f_v2 = open(OUTDIR / "v2_screening.jsonl", "w", encoding="utf-8")
    rows = []
    t_all = time.time()
    for di, donor in enumerate(donor_ids):
        sims = feats @ feats[donor]
        sims[donor] = -1.0
        order = np.argsort(-sims)
        pool = []
        for j in order:
            j = int(j)
            if len(txns[donor] & txns[j]) >= DUP_THRESHOLD:
                continue
            pool.append(j)
            if len(pool) >= POOL_K:
                break
        for L in LENGTHS_S:
            span = span_seconds(ev_corpus[donor], rng, L)
            if len(span) < 8:
                continue
            mutated = apply("transcribe", span, rng, (30, 0.08))
            q = encode(mutated, cfg)
            if len(q) < 8:
                continue
            min_ev = max(8, len(q) // 2)

            # ---- tolerant layer (recall engine) -------------------------
            rt = index.detect_tolerant(q, min_evidence=min_ev, k_pitch=2,
                                       k_bin=1, k_vel=1, cfg=cfg,
                                       pieces_of_interest=all_ids)
            st = np.zeros(n_pieces, dtype=np.int32)
            for k_, v_ in rt.scores_of_interest.items():
                st[int(k_)] = v_
            donor_rank_t = rank_of(st[donor], st, donor)
            pool_scores_t = sorted((int(st[p]) for p in pool), reverse=True)

            # ---- verbatim layer (precision engine) ----------------------
            rv = index.detect_tolerant(q, min_evidence=max(4, min_ev // 2),
                                       k_pitch=0, k_bin=0, k_vel=0, cfg=cfg,
                                       pieces_of_interest=all_ids)
            sv = np.zeros(n_pieces, dtype=np.int32)
            for k_, v_ in rv.scores_of_interest.items():
                sv[int(k_)] = v_
            donor_rank_v = rank_of(sv[donor], sv, donor)
            vb_threshold = max(4, min_ev // 2)
            pool_scores_v = sorted((int(sv[p]) for p in pool), reverse=True)

            row = {
                "donor": donor, "len_s": L, "n_query_items": len(q),
                "min_evidence": min_ev,
                "tolerant": {
                    "donor_score": int(st[donor]),
                    "donor_rank": donor_rank_t,
                    "top1": donor_rank_t == 1,
                    "top5": donor_rank_t <= 5,
                    "top20": donor_rank_t <= 20,
                    "max_pool_score": pool_scores_t[0],
                    "margin": int(st[donor] - pool_scores_t[0]),
                    "fp_pool": [s for s in pool_scores_t if s >= min_ev],
                },
                "verbatim": {
                    "threshold": vb_threshold,
                    "donor_score": int(sv[donor]),
                    "donor_rank": donor_rank_v,
                    "top1": donor_rank_v == 1,
                    "top5": donor_rank_v <= 5,
                    "top20": donor_rank_v <= 20,
                    "max_pool_score": pool_scores_v[0],
                    "margin": int(sv[donor] - pool_scores_v[0]),
                    "fp_pool": [s for s in pool_scores_v
                                if s >= vb_threshold],
                },
            }
            rows.append(row)
            f_v2.write(json.dumps(row) + "\n")
        if (di + 1) % 20 == 0:
            print(f"  {di + 1}/{len(donor_ids)} donors "
                  f"({time.time() - t_all:.0f}s)", flush=True)
    f_v2.close()

    # ---- summary --------------------------------------------------------
    n = len(rows)
    print("\n==== E1.3 v2 SUMMARY (screening metrics) ====")
    print(f"fragments: {n}")
    for layer in ["tolerant", "verbatim"]:
        sub = [r[layer] for r in rows]
        for k in ["top1", "top5", "top20"]:
            rate = np.mean([s[k] for s in sub])
            print(f"{layer:9s} donor {k:5s}: {rate:.3f}")
        fp = np.mean([len(s["fp_pool"]) > 0 for s in sub])
        mg = sorted(s["margin"] for s in sub)
        print(f"{layer:9s} frag-FP: {fp:.3f}   margin p50/p10: "
              f"{mg[n // 2]:.0f}/{mg[n // 10]:.0f}   "
              f"donor_score p50: {np.median([s['donor_score'] for s in sub]):.0f}")
    for L in LENGTHS_S:
        sub = [r for r in rows if r["len_s"] == L]
        t1 = np.mean([r["tolerant"]["top20"] for r in sub])
        v1 = np.mean([r["verbatim"]["top20"] for r in sub])
        print(f"L={L:2d}s: tolerant top20={t1:.3f}  verbatim top20={v1:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
