# -*- coding: utf-8 -*-
"""E6.2 controlled memorization screening (CPU substitute for neural
generator training, approved scope 2026-10-12):

Generative models are emulated by an order-m pitch n-gram model mixed with
a copy operator: after an 8-note seed copied from a random corpus position
(seed = context, NOT part of the detection query), each continuation note
is sampled from the m-gram pitch model with empirical rhythm (lambda=0,
no copying) or copied verbatim from the source continuation (lambda=1,
full memory).  Higher m and higher lambda approach verbatim regurgitation
of training spans -- the same memorization spectrum E6.1 would probe with
a trained neural model.

Every generated piece is screened with the production pipeline:
tolerant screen -> verbatim top-C=50 -> strict structural confirmation
(k=1,0,0, rho=0.5).  Query = continuation only.

Metrics per piece: confirmed?, best chain length, matched corpus piece
(argmax chain), is_source (match == the seed's source piece), latency.
Expectation: monotone detection in (m, lambda).

Output: runs/e62/memorization.jsonl   (generated pieces cached in
runs/e62/generated.pkl, gitignored)
"""
from __future__ import annotations

import argparse
import json
import pickle
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, Event  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from e1_matrix import load_events  # noqa: E402
import e13_hard_negatives as e13  # noqa: E402
import e14_structural_confirm as e14  # noqa: E402

OUTDIR = ROOT / "runs/e62"
OUT = OUTDIR / "memorization.jsonl"
GEN = OUTDIR / "generated.pkl"
ORDERS = [2, 4, 8]
LAMBDAS = [0.0, 0.25, 0.5, 0.75, 1.0]
N_PIECES_PER_CELL = 50
TOP_C = 50
RHO = 0.5
KP, KB, KV = 1, 0, 0
SEED_LEN = 8
GEN_LEN = 120


def gen_pieces(ev_corpus, rng):
    """Build n-gram pitch models + empirical rhythm, emit generated pieces.

    Returns list of dicts: {cell, source, seed_start, notes(list[Event]),
    cont_start_index}.
    """
    # pitch sequences per piece (quantized onsets for n-grams)
    pitch_seqs = []
    dur_pop: Counter[int] = Counter()
    ioi_pop: Counter[int] = Counter()
    for ev in ev_corpus:
        ordered = sorted(ev, key=lambda e: (e.onset_tick, e.pitch))
        if len(ordered) < SEED_LEN + GEN_LEN:
            pitch_seqs.append(None)
            continue
        pitch_seqs.append([e.pitch for e in ordered])
        for i, e in enumerate(ordered):
            dur_pop[min(15, (e.duration_tick + 62) // 125)] += 1
            ioi = (ordered[i + 1].onset_tick - e.onset_tick) \
                if i + 1 < len(ordered) else 0
            ioi_pop[min(15, (ioi + 62) // 125)] += 1
    dur_vals = np.array(sorted(dur_pop))
    dur_probs = np.array([dur_pop[v] for v in dur_vals], dtype=np.float64)
    dur_probs /= dur_probs.sum()
    ioi_vals = np.array(sorted(ioi_pop))
    ioi_probs = np.array([ioi_pop[v] for v in ioi_vals], dtype=np.float64)
    ioi_probs /= ioi_probs.sum()

    pieces = []
    for m in ORDERS:
        # context -> Counter(next pitch), per order, with backoff lookup;
        # built on a random subset to bound memory (8-gram tables are huge)
        usable = [i for i in range(len(pitch_seqs))
                  if pitch_seqs[i] is not None]
        rng.shuffle(usable)
        usable = usable[:1000]
        ctx_map = {o: {} for o in range(1, m + 1)}
        for idx in usable:
            ps = pitch_seqs[idx]
            for o in range(1, m + 1):
                cm = ctx_map[o]
                for i in range(len(ps) - o):
                    d = cm.get(tuple(ps[i:i + o]))
                    if d is None:
                        d = cm[tuple(ps[i:i + o])] = Counter()
                    d[ps[i + o]] += 1

        def sample_pitch(ctx, rng, _m=m, _cm=ctx_map):
            for o in range(min(_m, len(ctx)), 0, -1):
                d = _cm[o].get(tuple(ctx[-o:]))
                if d:
                    keys = list(d.keys())
                    cnts = np.array(list(d.values()), dtype=np.float64)
                    cnts /= cnts.sum()
                    return int(rng.choices(keys, weights=cnts)[0])
            return int(rng.randrange(40, 80))

        for lam in LAMBDAS:
            cell = f"m{m}_l{lam}"
            for g in range(N_PIECES_PER_CELL):
                cand = [i for i in range(len(pitch_seqs))
                        if pitch_seqs[i] is not None]
                src = rng.choice(cand)
                ps = pitch_seqs[src]
                st = rng.randrange(0, len(ps) - SEED_LEN - GEN_LEN + 1)
                seed_p = ps[st:st + SEED_LEN]
                src_p = ps[st + SEED_LEN:st + SEED_LEN + GEN_LEN]
                gen_p = []
                for i in range(GEN_LEN):
                    if rng.random() < lam:
                        gen_p.append(src_p[i])
                    else:
                        gen_p.append(sample_pitch(seed_p + gen_p, rng))
                # materialize Events: rhythm copied from source continuation
                # when lambda-mixed note is a copy; sampled rhythm otherwise
                src_ev = sorted(ev_corpus[src],
                                key=lambda e: (e.onset_tick, e.pitch))
                seg = src_ev[st + SEED_LEN:st + SEED_LEN + GEN_LEN]
                notes = []
                t = 0
                for i in range(GEN_LEN):
                    if rng.random() < lam:  # rhythm copy indicator
                        d_bin = min(15, (seg[i].duration_tick + 62) // 125)
                        ioi_bin = min(15, ((seg[i + 1].onset_tick
                                            - seg[i].onset_tick) + 62) // 125) \
                            if i + 1 < GEN_LEN else 0
                        vel = seg[i].velocity
                    else:
                        d_bin = int(rng.choices(dur_vals, weights=dur_probs)[0])
                        ioi_bin = int(rng.choices(ioi_vals, weights=ioi_probs)[0])
                        vel = seg[i].velocity
                    dur_ms = max(60, d_bin * 125)
                    ioi_ms = max(60, ioi_bin * 125)
                    notes.append(Event(int(t), int(gen_p[i]), int(dur_ms),
                                       0, int(vel)))
                    t += ioi_ms
                pieces.append({"cell": cell, "m": m, "lam": lam,
                               "source": src, "notes": notes})
    return pieces


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    cfg = EncodingConfig(use_channel=False)
    ev_corpus = load_events(
        ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet",
        e13.CORPUS_PIECES)
    txns = [e13.encode(ev, cfg) for ev in ev_corpus]
    index = CorpusIndex(txns)
    n_pieces = len(txns)
    all_ids = set(range(n_pieces))
    print("precomputing note matrices + code indexes ...", flush=True)
    t0 = time.time()
    cms = [e14.note_matrix(ev, cfg) for ev in ev_corpus]
    cidxs = [e14.code_index(cm, cfg) if cm is not None else {}
             for cm in cms]
    print(f"  {n_pieces} pieces in {time.time() - t0:.0f}s", flush=True)

    if GEN.exists():
        pieces = pickle.loads(GEN.read_bytes())
        print(f"loaded {len(pieces)} generated pieces from cache", flush=True)
    else:
        rng = random.Random(args.seed)
        pieces = gen_pieces(ev_corpus, rng)
        GEN.write_bytes(pickle.dumps(pieces))
        print(f"generated {len(pieces)} pieces", flush=True)

    done = 0
    if OUT.exists():
        done = sum(1 for l in OUT.read_text(encoding="utf-8").splitlines()
                   if l.strip())
    todo = pieces[done:]
    print(f"screening: {len(todo)} pieces ({done} done)", flush=True)

    t_all = time.time()
    for pi, gp in enumerate(todo):
        notes = gp["notes"]
        q = e13.encode(notes, cfg)
        nq = len(notes)
        min_ev = max(8, len(q) // 2)
        t0 = time.time()
        # screen (tolerant, whole corpus)
        rt = index.detect_tolerant(q, min_evidence=min_ev, k_pitch=2,
                                   k_bin=1, k_vel=1, cfg=cfg,
                                   pieces_of_interest=all_ids)
        st = np.zeros(n_pieces, dtype=np.int32)
        for k_, v_ in rt.scores_of_interest.items():
            st[int(k_)] = v_
        # verbatim re-rank top-C
        rv = index.detect_tolerant(q, min_evidence=1, k_pitch=0,
                                   k_bin=0, k_vel=0, cfg=cfg,
                                   pieces_of_interest=all_ids)
        sv = np.zeros(n_pieces, dtype=np.int32)
        for k_, v_ in rv.scores_of_interest.items():
            sv[int(k_)] = v_
        top_c = [int(j) for j in np.argsort(-sv)[:TOP_C]]
        # confirm strict chain on top-C ∪ {source} (source added so the
        # true positive is never lost to ranking; its retention is also
        # recorded)
        cands = sorted(set(top_c))
        retained = gp["source"] in cands
        cands = sorted(set(cands) | {gp["source"]})
        qm = e14.note_matrix(notes, cfg)
        qcodes = e14.query_codes(qm, cfg, KP, KB, KV)
        runs = {c: e14.chain_lcs(qcodes, cidxs[c]) for c in cands}
        best_c = max(runs, key=lambda c: runs[c])
        row = {
            "cell": gp["cell"], "m": gp["m"], "lam": gp["lam"],
            "source": gp["source"], "nq": nq, "lenq": len(q),
            "retained_source": retained,
            "best_run": runs[best_c],
            "best_piece": best_c,
            "source_run": runs[gp["source"]],
            "is_source": best_c == gp["source"],
            "confirmed": runs[best_c] >= RHO * nq,
            "wall_ms": round((time.time() - t0) * 1000, 1),
        }
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        if (pi + 1) % 50 == 0:
            print(f"  {pi + 1}/{len(todo)} "
                  f"({time.time() - t_all:.0f}s)", flush=True)

    # ---- summary --------------------------------------------------------
    rows = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"\n==== E6.2 SUMMARY ({len(rows)} generated pieces) ====")
    print(f"{'cell':>12} {'det_rate':>9} {'src_rate':>9} "
          f"{'run/nq p50':>11} {'retain':>7}")
    for m in ORDERS:
        for lam in LAMBDAS:
            cell = f"m{m}_l{lam}"
            sub = [r for r in rows if r["cell"] == cell]
            if not sub:
                continue
            det = np.mean([r["confirmed"] for r in sub])
            src = np.mean([r["is_source"] for r in sub])
            fr = np.median([r["best_run"] / r["nq"] for r in sub])
            ret = np.mean([r["retained_source"] for r in sub])
            print(f"{cell:>12} {det:9.3f} {src:9.3f} "
                  f"{fr:11.2f} {ret:7.3f}")
    wall = sorted(r["wall_ms"] for r in rows)
    print(f"\nlatency p50/p95: {wall[len(wall) // 2]:.0f} / "
          f"{wall[int(len(wall) * .95)]:.0f} ms per generated piece "
          f"(screen + re-rank + confirm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
