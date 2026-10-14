# -*- coding: utf-8 -*-
"""E2: theoretical lower bound vs measured recall.

For each planted cell (same deterministic replay as e1_matrix), compute the
guaranteed evidence count:

    bound = |{ x in S : ball(x; k) intersects ball(T(x); k) }|

where S = distinct planted span items, T(x) = the transformed item at the
event carrying x, and balls are boxes of (+-k_pitch semitones, +-k_bin dur
bins, +-k_bin ioi bins).  Box intersection is exact via the decoded
components (triangle inequality is tight for boxes).

Checks (E2 hard acceptance):
  1. measured donor tolerant-score >= bound for every cell (bound validity);
  2. NO cell with bound >= min_evidence is missed (guarantee holds);
  3. per-transform recall-vs-strength curve data for paper fig 4.

Output: runs/e2/bounds.jsonl (per cell) + console summary.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, _bin  # noqa: E402
from adapter.detector import CorpusIndex, item_decode, item_encode  # noqa: E402
from adapter import transforms as T  # noqa: E402
from e1_matrix import GRID, LENGTHS_S, SEEDS, apply, load_events, span_seconds  # noqa: E402

OUT = ROOT / "runs/e2/bounds.jsonl"
K_PITCH, K_BIN, K_VEL = 2, 1, 1


def event_code(e, cfg) -> int:
    d = _bin(e.duration_tick, 1000, cfg.tpb, cfg.dur_bins)
    g = 0  # ioi filled by caller per position
    v = min(e.velocity >> (7 - (cfg.vel_bins - 1).bit_length()),
            cfg.vel_bins - 1) if cfg.vel_bins < 128 else e.velocity
    return d, v


def bound_for_span(span, mutated, q_items, cfg):
    """Exact guaranteed evidence count under (K_PITCH, K_BIN) tolerance.

    Detector semantics: the donor contains the planted set S (distinct span
    items); it scores a query item y iff it contains a variant of y, i.e. an
    item within radius (K_PITCH, K_BIN) of y.  Since S is a subset of the
    donor's items,
        donor_score >= |{ y in Q : dist(y, S) <= K }|      (exact bound)
    where dist is the box distance on decoded components.  The guarantee
    premise is that the transform keeps every item within K of its original
    (deviation <= k per component); such copies score the full span.
    """
    s_items = set()
    s_span = sorted(span, key=lambda e: (e.onset_tick, e.pitch))
    for i, e in enumerate(s_span):
        d, v = event_code(e, cfg)
        nxt = s_span[i + 1] if i + 1 < len(s_span) else None
        ioi = (nxt.onset_tick - e.onset_tick) if nxt else 0
        g = _bin(max(ioi, 0), 1000, cfg.tpb, cfg.ioi_bins)
        s_items.add(item_encode(e.pitch, d, g, v, cfg))
    s_dec = [item_decode(x, cfg) for x in s_items]
    bound = 0
    for y in q_items:
        py, dy, gy, vy = item_decode(y, cfg)
        if any(abs(px - py) <= K_PITCH and abs(dx - dy) <= K_BIN
               and abs(gx - gy) <= K_BIN and abs(vx - vy) <= K_VEL
               for px, dx, gx, vx in s_dec):
            bound += 1
    return bound, len(s_items)


def main() -> int:
    cfg = EncodingConfig(use_channel=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            if ln.strip():
                d = json.loads(ln)
                done.add((d["transform"], json.dumps(d["strength"],
                          sort_keys=True), d["length_s"], d["seed"]))

    ev_corpus = load_events(ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet", 1000)
    txns = []
    from adapter.midi_encode import events_to_items
    for ev in ev_corpus:
        txns.append(events_to_items(sorted(ev, key=lambda e: (e.onset_tick, e.pitch)),
                                    1000, cfg)[0])
    index = CorpusIndex(txns)

    violations = 0
    cells = 0
    for name, strengths in GRID.items():
        for strength in strengths:
            for L in LENGTHS_S:
                agg = [0, 0, 0]   # hit, guaranteed-hit, total
                for seed in SEEDS:
                    key = (name, json.dumps(strength, sort_keys=True), L, seed)
                    if key in done:
                        continue
                    import random
                    rng = random.Random(seed * 1000 + L)
                    donor = rng.randrange(len(ev_corpus))
                    span = span_seconds(ev_corpus[donor], rng, L)
                    if len(span) < 6:
                        continue
                    mutated = apply(name, span, rng, strength)
                    q_items, _ = events_to_items(
                        sorted(mutated, key=lambda e: (e.onset_tick, e.pitch)),
                        1000, cfg)
                    n_span_items = len(q_items)
                    if n_span_items < 8:
                        continue
                    min_ev = max(8, n_span_items // 2)
                    bound, n_distinct = bound_for_span(span, mutated, q_items, cfg)
                    t0 = time.time()
                    r = index.detect_tolerant(q_items, min_evidence=min_ev,
                                              k_pitch=K_PITCH, k_bin=K_BIN,
                                              k_vel=K_VEL, cfg=cfg,
                                              pieces_of_interest={donor})
                    donor_score = r.scores_of_interest.get(donor, 0)
                    hit = donor_score >= min_ev
                    guaranteed = bound >= min_ev
                    if donor_score < bound:
                        violations += 1
                        print(f"  BOUND VIOLATION {key}: score={donor_score} "
                              f"bound={bound}")
                    if guaranteed and not hit:
                        violations += 1
                        print(f"  GUARANTEE MISS {key}: bound={bound} "
                              f"min_ev={min_ev} score={donor_score}")
                    rec = {"transform": name, "strength": strength,
                           "length_s": L, "seed": seed, "min_evidence": min_ev,
                           "bound": bound, "n_distinct_span_items": n_distinct,
                           "donor_score": donor_score, "hit": hit,
                           "guaranteed": guaranteed,
                           "wall_ms": round((time.time() - t0) * 1000, 1)}
                    with open(OUT, "a", encoding="utf-8") as f:
                        f.write(json.dumps(rec) + "\n")
                    agg[0] += hit; agg[1] += guaranteed and hit; agg[2] += 1
                    cells += 1
                    done.add(key)
                if agg[2]:
                    print(f"{name} s={strength} L={L}s: recall {agg[0]}/{agg[2]}, "
                          f"guaranteed-hits {agg[1]}/{agg[2]}", flush=True)
    print(f"\nE2 cells={cells}, violations={violations}")
    print("VERDICT:", "PASS" if violations == 0 else "FAIL")
    return 0 if violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
