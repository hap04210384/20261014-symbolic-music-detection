# -*- coding: utf-8 -*-
"""E7 hybrid cascade (architecture v2, 2026-10-12):
cascade = tolerant screen (sound recall, E2 bound)
        -> verbatim re-rank top-C
        -> strict structural confirmation (anchor-chain LCS, E1.4)

E7.1  three systems on the E1.3 style-similar hard-negative suite:
        screen-only  (tolerant count threshold)
        rank-only    (verbatim count threshold, top-1 decision)
        cascade      (screen -> top-C verbatim -> strict chain, rho)
E7.2  candidate-set size C in {5,10,20,50}: donor retention + P-R of cascade
E7.3  dual-threshold sensitivity: min_evidence (screen) x rho (confirm)

Comparability: same corpus / donors / pools / transcribe plants as E1.3/E1.4
(same seed chain).  Output: runs/e17/cascade.jsonl (+ summary)
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
import e14_structural_confirm as e14  # noqa: E402

OUT = ROOT / "runs/e17/cascade.jsonl"
TOP_C_GRID = [5, 10, 20, 50]
MIN_EV_FRACS = [0.25, 0.5, 0.75]
RHO_GRID = [0.4, 0.5, 0.6]
KP, KB, KV = 1, 0, 0  # strict confirmation tolerance (E1.4 winner)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--donors", type=int, default=80)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--start", type=int, default=0)
    args = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    done = set()
    if OUT.exists():
        for ln in OUT.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                done.add(json.loads(ln)["donor"])

    cfg = EncodingConfig(use_channel=False)
    ev_corpus = load_events(
        ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet",
        e13.CORPUS_PIECES)
    txns = [e13.encode(ev, cfg) for ev in ev_corpus]
    index = CorpusIndex(txns)
    feats = e13.piece_features(ev_corpus)
    n_pieces = len(txns)
    all_ids = set(range(n_pieces))
    print("precomputing note matrices + code indexes ...", flush=True)
    t0 = time.time()
    cms = [e14.note_matrix(ev, cfg) for ev in ev_corpus]
    cidxs = [e14.code_index(cm, cfg) if cm is not None else {}
             for cm in cms]
    print(f"  {n_pieces} pieces in {time.time() - t0:.0f}s", flush=True)

    rng = random.Random(args.seed)
    donor_ids = [i for i in range(n_pieces) if len(txns[i]) >= 60]
    rng.shuffle(donor_ids)
    donor_ids = [d for d in donor_ids[args.start:args.start + args.donors]
                 if d not in done]
    print(f"donors to run: {len(donor_ids)}", flush=True)

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
            nq = len(mutated)
            lenq = len(q)

            # ---- full-score screens (both layers, whole corpus) ----------
            rt = index.detect_tolerant(q, min_evidence=1, k_pitch=2,
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

            pool_set = set(pool)
            row = {"donor": donor, "len_s": L, "nq": nq, "lenq": lenq,
                   "donor_st": int(st[donor]), "donor_sv": int(sv[donor]),
                   "pool_st": [int(st[p]) for p in pool],
                   "pool_sv": [int(sv[p]) for p in pool],
                   "donor_sv_rank": e13.rank_of(int(sv[donor]),
                                                sv, donor),
                   "retention": {str(c): int(donor in {
                       int(j) for j in np.argsort(-sv)[:c]})
                       for c in TOP_C_GRID}}

            # ---- cascade: verify (top-C by sv) ∪ pool ∪ {donor} ----------
            qm = e14.note_matrix(sorted(mutated, key=lambda e: (
                e.onset_tick, e.pitch)), cfg)
            qcodes = e14.query_codes(qm, cfg, KP, KB, KV)
            sv_order = [int(j) for j in np.argsort(-sv)]
            tq = time.time()
            for c in TOP_C_GRID:
                cands = sorted(set(sv_order[:c]) | pool_set | {donor})
                runs = {pc: e14.chain_lcs(qcodes, cidxs[pc]) for pc in cands}
                d_run = runs[donor]
                pool_runs = sorted((runs[p] for p in pool), reverse=True)
                row[f"cascade_C{c}"] = {
                    "donor_run": d_run,
                    "max_pool_run": pool_runs[0] if pool_runs else 0,
                    "rho_grid": {str(r): {
                        "donor_confirmed": d_run >= r * nq,
                        "fp": [s for s in pool_runs if s >= r * nq],
                    } for r in RHO_GRID},
                }
            row["verify_ms"] = round((time.time() - tq) * 1000, 1)
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        if (di + 1) % 10 == 0:
            print(f"  {di + 1}/{len(donor_ids)} "
                  f"({time.time() - t_all:.0f}s)", flush=True)

    # ---- summary --------------------------------------------------------
    rows = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    n = len(rows)
    print(f"\n==== E7 SUMMARY ({n} fragments) ====")

    print("\n[E7.1a] screen-only (tolerant count): recall / frag-FP")
    for f_ in MIN_EV_FRACS:
        rec = np.mean([r["donor_st"] >= max(8, int(r["lenq"] * f_))
                       for r in rows])
        fp = np.mean([any(s >= max(8, int(r["lenq"] * f_))
                          for s in r["pool_st"]) for r in rows])
        print(f"  min_ev={f_:.2f}*|q|: recall={rec:.3f} FP={fp:.3f}")

    print("\n[E7.1b] rank-only (verbatim count, top-1 decision):")
    for tau in [8, 12, 16, 20, 25, 30]:
        rec = np.mean([r["donor_sv"] >= tau for r in rows])
        fp = np.mean([any(s >= tau for s in r["pool_sv"]) for r in rows])
        print(f"  tau={tau:2d}: recall={rec:.3f} FP={fp:.3f}")

    print("\n[E7.1c] cascade (C=20):")
    for r_ in RHO_GRID:
        rec = np.mean([r["cascade_C20"]["rho_grid"][str(r_)][
            "donor_confirmed"] for r in rows])
        fp = np.mean([len(r["cascade_C20"]["rho_grid"][str(r_)][
            "fp"]) > 0 for r in rows])
        print(f"  rho={r_:.1f}: recall={rec:.3f} FP={fp:.3f}")

    print("\n[E7.2] donor retention in top-C (verbatim rank):")
    for c in TOP_C_GRID:
        ret = np.mean([r["retention"][str(c)] for r in rows])
        print(f"  C={c:2d}: retention={ret:.3f}")

    print("\n[E7.2/7.3] cascade recall/FP by C x rho "
          "(min_evidence implicit in screens):")
    for c in TOP_C_GRID:
        line = f"  C={c:2d}: "
        for r_ in RHO_GRID:
            rec = np.mean([r[f"cascade_C{c}"]["rho_grid"][str(r_)][
                "donor_confirmed"] for r in rows])
            fp = np.mean([len(r[f"cascade_C{c}"]["rho_grid"][str(r_)][
                "fp"]) > 0 for r in rows])
            line += f"rho{r_}: R={rec:.2f}/FP={fp:.2f}  "
        print(line)
    vm = sorted(r["verify_ms"] for r in rows)
    print(f"\nverify cost p50: {vm[n // 2]:.0f} ms/query "
          f"(4 candidate sets incl. C=50)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
