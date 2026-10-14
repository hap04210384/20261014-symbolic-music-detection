# -*- coding: utf-8 -*-
"""E3: anytime behaviour — rare-first vs hot-first vs random scheduling.

For each planted query, run detect_tolerant at increasing processing
fractions and record: donor found?, #hits, provable remaining bound, wall.
Query cost grows with fraction -> the x-axis doubles as wall-time.

Output: runs/e3/anytime.jsonl
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, events_to_items  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from adapter import transforms as T  # noqa: E402
from e1_matrix import load_events, span_seconds, apply  # noqa: E402

OUT = ROOT / "runs/e3/anytime.jsonl"
FRACTIONS = [0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.70, 1.00]
ORDERS = ["rare", "random", "hot"]
PLANTS = 20
K_PITCH, K_BIN, K_VEL = 2, 1, 1


def main() -> int:
    cfg = EncodingConfig(use_channel=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ev_corpus = load_events(ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet", 1000)
    txns = [events_to_items(sorted(ev, key=lambda e: (e.onset_tick, e.pitch)),
                            1000, cfg)[0] for ev in ev_corpus]
    index = CorpusIndex(txns)

    rng = random.Random(77)
    rows = 0
    for plant in range(PLANTS):
        donor = rng.randrange(len(ev_corpus))
        L = rng.choice([4, 16])
        # distinctive planting: real copied passages are rare-content; resample
        # the span until it carries at least 5 items with support < 20
        span = None
        for _try in range(50):
            cand = span_seconds(ev_corpus[donor], rng, L)
            if len(cand) < 8:
                continue
            items_c, _ = events_to_items(
                sorted(cand, key=lambda e: (e.onset_tick, e.pitch)), 1000, cfg)
            rare_n = sum(1 for x in items_c
                         if len(index.postings.get(x, ())) < 20)
            if rare_n >= 5:
                span = cand
                break
        if span is None:
            span = cand  # fallback: common-content plant (control group)
        tname = rng.choice(["verbatim", "transcribe"])
        strength = (30, 0.08) if tname == "transcribe" else None
        mutated = apply(tname, span, rng, strength)
        q_items, _ = events_to_items(
            sorted(mutated, key=lambda e: (e.onset_tick, e.pitch)), 1000, cfg)
        if len(q_items) < 8:
            continue
        min_ev = max(8, len(q_items) // 2)
        for order in ORDERS:
            for frac in FRACTIONS:
                k = max(1, int(len(q_items) * frac))
                t0 = time.time()
                r = index.detect_tolerant(
                    q_items, min_evidence=min_ev, k_pitch=K_PITCH,
                    k_bin=K_BIN, k_vel=K_VEL, cfg=cfg,
                    max_positions=k, order=order,
                    pieces_of_interest={donor})
                rec = {
                    "plant": plant, "transform": tname, "length_s": L,
                    "order": order, "fraction": frac, "positions": k,
                    "donor_found": donor in {h.piece for h in r.hits},
                    "donor_raw_score": r.scores_of_interest.get(donor, 0),
                    "n_hits": len(r.hits), "remaining_bound": r.n_candidates_remaining,
                    "wall_ms": round((time.time() - t0) * 1000, 1),
                }
                with open(OUT, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")
                rows += 1
        print(f"plant {plant} ({tname} {L}s) done", flush=True)
    print(f"rows={rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
