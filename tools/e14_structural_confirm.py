# -*- coding: utf-8 -*-
"""E1.4 structural confirmation v2: anchor-chain LCS, strict tolerance.

v1 lessons (smoke, 10 donors):
  * dense per-row DP is correct but 200 ms/candidate -> too slow;
  * loose confirmation tolerance (k=2,1,1) leaves style-FP at 36% @rho=0.6:
    free-deletion LCS rewards *any* ordered subsequence, and style peers
    share plenty of ordered chord/bass material at loose tolerance.

v2 design:
  * recall comes from the tolerant screen (sound bound, E2) — confirmation
    may therefore afford STRICT tolerance (k_pitch=1, k_bin=0, k_vel=0):
    bin flips under transcribe jitter are absorbed by free deletions
    (a flipped note is simply not aligned; the ordered chain continues);
  * alignment = longest chain of tolerant per-note matches with both query
    index and candidate position strictly increasing (== LCS with free
    deletions), computed over *anchors only* via an exact-code inverted
    index per candidate + Fenwick max-tree: O(A log m), A = #anchors;
  * decision: best chain >= rho * |q|.

Pipeline per query: tolerant screen -> verbatim top-C=10 re-rank ->
verify (top-C ∪ style-pool ∪ {donor}).
Output: runs/e14/confirm.jsonl
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
from adapter.midi_encode import EncodingConfig  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from e1_matrix import load_events, span_seconds, apply  # noqa: E402
import e13_hard_negatives as e13  # noqa: E402

OUT = ROOT / "runs/e14/confirm.jsonl"
TOP_C = 10
RHO_GRID = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
# confirmation tolerances to compare (k_pitch, k_bin, k_vel)
CONF_TOLS = {"strict": (1, 0, 0), "mid": (1, 1, 1), "loose": (2, 1, 1)}


def note_matrix(ev, cfg):
    """Ordered per-note feature arrays (pitch, dur_bin, ioi_bin, vel_bin),
    quantized exactly like midi_encode._bin (round-to-nearest grid)."""
    if not ev:
        return None
    ordered = sorted(ev, key=lambda e: (e.onset_tick, e.pitch))
    n = len(ordered)
    p = np.array([e.pitch for e in ordered], dtype=np.int16)
    d = np.zeros(n, dtype=np.int16)
    g = np.zeros(n, dtype=np.int16)
    v = np.zeros(n, dtype=np.int16)
    grid = max(1, 1000 // cfg.tpb)  # 125 ms at tpb=8, matches _bin
    for i, e in enumerate(ordered):
        d[i] = min(cfg.dur_bins - 1, (e.duration_tick + grid // 2) // grid)
        ioi = (ordered[i + 1].onset_tick - e.onset_tick) if i + 1 < n else 0
        g[i] = min(cfg.ioi_bins - 1, (ioi + grid // 2) // grid)
        v[i] = min(e.velocity >> 4, cfg.vel_bins - 1) if cfg.vel_bins < 128 \
            else e.velocity
    return p, d, g, v


def code_index(cm, cfg):
    """Exact-code -> sorted positions for one candidate piece."""
    p, d, g, v = cm
    idx: dict[int, list[int]] = {}
    for j in range(len(p)):
        c = ((((int(p[j]) * cfg.dur_bins + int(d[j])) * cfg.ioi_bins
               + int(g[j])) * cfg.vel_bins + int(v[j]))) + 1
        idx.setdefault(c, []).append(j)
    return idx


def query_codes(qm, cfg, k_pitch, k_bin, k_vel):
    """Per query note: list of variant codes within tolerance."""
    p, d, g, v = qm
    out = []
    for i in range(len(p)):
        codes = []
        for dp in range(-k_pitch, k_pitch + 1):
            pp = int(p[i]) + dp
            if pp < 0 or pp > 127:
                continue
            for dd in range(-k_bin, k_bin + 1):
                d2 = int(d[i]) + dd
                if not (0 <= d2 < cfg.dur_bins):
                    continue
                for dg in range(-k_bin, k_bin + 1):
                    g2 = int(g[i]) + dg
                    if not (0 <= g2 < cfg.ioi_bins):
                        continue
                    for dv in range(-k_vel, k_vel + 1):
                        v2 = int(v[i]) + dv
                        if not (0 <= v2 < cfg.vel_bins):
                            continue
                        codes.append(
                            (((pp * cfg.dur_bins + d2) * cfg.ioi_bins + g2)
                             * cfg.vel_bins + v2) + 1)
        out.append(codes)
    return out


class Fenwick:
    def __init__(self, n):
        self.t = [0] * (n + 1)

    def query(self, j):
        """max over indices <= j."""
        t, r = self.t, 0
        while j > 0:
            if t[j] > r:
                r = t[j]
            j -= j & (-j)
        return r

    def update(self, j, val):
        t, n = self.t, len(self.t) - 1
        while j <= n:
            if val > t[j]:
                t[j] = val
            j += j & (-j)


def chain_lcs(qcodes, cidx):
    """Longest chain of anchors (query note i, candidate pos j) with i and j
    strictly increasing.  qcodes: per-note variant codes; cidx: candidate
    exact-code -> positions."""
    anchors = []  # (i, j)
    for i, codes in enumerate(qcodes):
        for c in codes:
            js = cidx.get(c)
            if js:
                for j in js:
                    anchors.append((i, j))
    if not anchors:
        return 0
    anchors.sort()
    fw = Fenwick(max(j for _, j in anchors) + 2)
    best = 0
    # group anchors by query note: all values in a group must be computed
    # against the Fenwick state BEFORE the group updates, so one query note
    # can be used at most once in the chain (one-to-one matching)
    k = 0
    A = len(anchors)
    while k < A:
        k2 = k
        while k2 < A and anchors[k2][0] == anchors[k][0]:
            k2 += 1
        upd = []
        for t in range(k, k2):
            j = anchors[t][1]
            v = fw.query(j) + 1  # strictly increasing j: query < j
            if v > best:
                best = v
            upd.append((j, v))
        for j, v in upd:
            fw.update(j + 1, v)
        k = k2
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--donors", type=int, default=80)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--start", type=int, default=0,
                    help="first donor index (chunked runs)")
    args = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    done_donors = set()
    if OUT.exists():
        for ln in OUT.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                done_donors.add(json.loads(ln)["donor"])

    cfg = EncodingConfig(use_channel=False)
    ev_corpus = load_events(
        ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet",
        e13.CORPUS_PIECES)
    txns = [e13.encode(ev, cfg) for ev in ev_corpus]
    index = CorpusIndex(txns)
    feats = e13.piece_features(ev_corpus)
    n_pieces = len(txns)
    all_ids = set(range(n_pieces))
    print("precomputing candidate note matrices + code indexes ...",
          flush=True)
    t0 = time.time()
    cms = [note_matrix(ev, cfg) for ev in ev_corpus]
    cidxs = [code_index(cm, cfg) if cm is not None else {}
             for cm in cms]
    print(f"  {n_pieces} pieces in {time.time() - t0:.0f}s", flush=True)

    rng = random.Random(args.seed)
    donor_ids = [i for i in range(n_pieces) if len(txns[i]) >= 60]
    rng.shuffle(donor_ids)
    donor_ids = donor_ids[args.start:args.start + args.donors]
    donor_ids = [d for d in donor_ids if d not in done_donors]
    print(f"donors to run: {len(donor_ids)} (skip {len(done_donors)} done)",
          flush=True)

    rows = []
    t_all = time.time()
    for di, donor in enumerate(donor_ids):
        sims = feats @ feats[donor]
        sims[donor] = -1.0
        order = np.argsort(-sims)
        pool = []
        for j in order:
            j = int(j)
            if len(txns[donor] & txns[j]) >= e13.DUP_THRESHOLD:
                continue
            pool.append(j)
            if len(pool) >= e13.POOL_K:
                break
        for L in e13.LENGTHS_S:
            span = span_seconds(ev_corpus[donor], rng, L)
            if len(span) < 8:
                continue
            mutated = apply("transcribe", span, rng, (30, 0.08))
            q = e13.encode(mutated, cfg)
            if len(q) < 8:
                continue
            min_ev = max(8, len(q) // 2)

            rt = index.detect_tolerant(q, min_evidence=min_ev, k_pitch=2,
                                       k_bin=1, k_vel=1, cfg=cfg,
                                       pieces_of_interest=all_ids)
            st = np.zeros(n_pieces, dtype=np.int32)
            for k_, v_ in rt.scores_of_interest.items():
                st[int(k_)] = v_
            rv = index.detect_tolerant(q, min_evidence=1, k_pitch=0,
                                       k_bin=0, k_vel=0, cfg=cfg,
                                       pieces_of_interest=all_ids)
            sv = np.zeros(n_pieces, dtype=np.int32)
            for k_, v_ in rv.scores_of_interest.items():
                sv[int(k_)] = v_
            top_c = [int(j) for j in np.argsort(-sv)[:TOP_C]]
            keep = sorted(set(top_c) | set(pool) | {donor})

            qm = note_matrix(sorted(mutated,
                                    key=lambda e: (e.onset_tick, e.pitch)),
                             cfg)
            nq = len(mutated)
            row = {"donor": donor, "len_s": L, "n_query_notes": nq,
                   "n_query_items": len(q), "min_evidence": min_ev,
                   "n_verified": len(keep)}
            tq = time.time()
            for tname, (kp, kb, kv) in CONF_TOLS.items():
                qcodes = query_codes(qm, cfg, kp, kb, kv)
                runs = {}
                for c in keep:
                    runs[c] = chain_lcs(qcodes, cidxs[c])
                donor_run = runs[donor]
                pool_runs = sorted((runs[p] for p in pool), reverse=True)
                row[tname] = {
                    "donor_run": donor_run,
                    "donor_run_frac": round(donor_run / nq, 3),
                    "max_pool_run": pool_runs[0] if pool_runs else 0,
                    "margin": donor_run - (pool_runs[0] if pool_runs else 0),
                    "rho_grid": {str(r): {
                        "donor_confirmed": donor_run >= r * nq,
                        "fp_pool": [s for s in pool_runs if s >= r * nq],
                    } for r in RHO_GRID},
                }
            row["verify_ms"] = round((time.time() - tq) * 1000, 1)
            rows.append(row)
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        if (di + 1) % 10 == 0:
            print(f"  {di + 1}/{len(donor_ids)} donors "
                  f"({time.time() - t_all:.0f}s)", flush=True)

    # ---- summary (always computed from the full jsonl) ------------------
    rows = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    n = len(rows)
    print("\n==== E1.4 v2 SUMMARY ====")
    print(f"fragments: {n}   verify p50: "
          f"{sorted(r['verify_ms'] for r in rows)[n // 2]:.0f} ms/query")
    for tname in CONF_TOLS:
        sub = [r[tname] for r in rows]
        fr = np.array([s["donor_run_frac"] for s in sub])
        mg = sorted(s["margin"] for s in sub)
        print(f"\n[{tname}] donor run frac p5/p50/p95: "
              f"{np.percentile(fr, 5):.2f}/{np.percentile(fr, 50):.2f}/"
              f"{np.percentile(fr, 95):.2f}   margin p50/p10: "
              f"{mg[n // 2]}/{mg[n // 10]}")
        print(f"{'rho':>5} {'donor_recall':>12} {'frag_FP':>8}")
        for r_ in RHO_GRID:
            rec = np.mean([g["donor_confirmed"] for g in
                           (s["rho_grid"][str(r_)] for s in sub)])
            fp = np.mean([len(g["fp_pool"]) > 0 for g in
                          (s["rho_grid"][str(r_)] for s in sub)])
            print(f"{r_:5.1f} {rec:12.3f} {fp:8.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
