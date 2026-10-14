# -*- coding: utf-8 -*-
"""E5 ablations (local, 1000-piece corpus):
  E5.4  L (min evidence) sensitivity: 0.75/1.0/1.25/1.5 x base
  E5.5  tolerance scan: (k_pitch, k_bin, k_vel) grid -> recall / time / FP
  E5.7  quantization granularity: tpb 4/8/16 (250/125/62.5 ms grid)

Output: runs/e5/ablation.jsonl
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
from e1_matrix import load_events, span_seconds, apply  # noqa: E402

OUT = ROOT / "runs/e5/ablation.jsonl"


def encode(ev, cfg):
    return events_to_items(sorted(ev, key=lambda e: (e.onset_tick, e.pitch)),
                           1000, cfg)[0]


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ev_corpus = load_events(ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet", 1000)
    cfg = EncodingConfig(use_channel=False)

    # ---- shared plants -------------------------------------------------
    rng = random.Random(1234)
    plants = []
    for _ in range(30):
        donor = rng.randrange(len(ev_corpus))
        L = rng.choice([4, 16])
        span = span_seconds(ev_corpus[donor], rng, L)
        if len(span) < 8:
            continue
        tname = rng.choice(["verbatim", "transcribe", "transpose", "tempo"])
        strength = {"transcribe": (30, 0.08), "transpose": 2,
                    "tempo": 1.10}.get(tname)
        mutated = apply(tname, span, rng, strength)
        plants.append({"donor": donor, "transform": tname,
                       "span": span, "mutated": mutated})
    print(f"plants: {len(plants)}")

    results = []

    # ---- E5.4: L sensitivity -------------------------------------------
    txns = [encode(ev, cfg) for ev in ev_corpus]
    index = CorpusIndex(txns)
    for factor in [0.75, 1.0, 1.25, 1.5]:
        ok = fp = done = 0
        for pl in plants:
            q = encode(pl["mutated"], cfg)
            if len(q) < 8:
                continue
            min_ev = max(8, int(len(q) // 2 * factor))
            done += 1
            r = index.detect_tolerant(q, min_evidence=min_ev, k_pitch=2,
                                      k_bin=1, k_vel=1, cfg=cfg,
                                      pieces_of_interest={pl["donor"]})
            score = r.scores_of_interest.get(pl["donor"], 0)
            ok += score >= min_ev
            fp += max(0, len(r.hits) - (1 if score >= min_ev else 0))
        results.append({"ablation": "E5.4_L", "factor": factor,
                        "recall": f"{ok}/{done}", "false_candidates": fp})
        print(f"E5.4 Lx{factor}: recall {ok}/{done}, FP {fp}", flush=True)

    # ---- E5.5: tolerance scan -------------------------------------------
    grid = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0), (2, 1, 1), (3, 1, 1)]
    for kp, kb, kv in grid:
        ok = fp = done = 0
        wall = []
        for pl in plants:
            q = encode(pl["mutated"], cfg)
            if len(q) < 8:
                continue
            done += 1
            min_ev = max(8, len(q) // 2)
            t0 = time.time()
            r = index.detect_tolerant(q, min_evidence=min_ev, k_pitch=kp,
                                      k_bin=kb, k_vel=kv, cfg=cfg,
                                      pieces_of_interest={pl["donor"]})
            wall.append(time.time() - t0)
            score = r.scores_of_interest.get(pl["donor"], 0)
            ok += score >= min_ev
            fp += max(0, len(r.hits) - (1 if score >= min_ev else 0))
        results.append({"ablation": "E5.5_k", "k_pitch": kp, "k_bin": kb,
                        "k_vel": kv, "recall": f"{ok}/{done}",
                        "false_candidates": fp,
                        "wall_p50_ms": sorted(wall)[len(wall) // 2] * 1000})
        print(f"E5.5 k=({kp},{kb},{kv}): recall {ok}/{done}, FP {fp}, "
              f"p50 {sorted(wall)[len(wall)//2]*1000:.1f}ms", flush=True)

    # ---- E5.7: quantization granularity ---------------------------------
    for tpb in [4, 8, 16]:
        cfg_q = EncodingConfig(tpb=tpb, use_channel=False)
        txns_q = [encode(ev, cfg_q) for ev in ev_corpus]
        index_q = CorpusIndex(txns_q)
        ok = fp = done = 0
        wall = []
        for pl in plants:
            q = encode(pl["mutated"], cfg_q)
            if len(q) < 8:
                continue
            done += 1
            min_ev = max(8, len(q) // 2)
            t0 = time.time()
            r = index_q.detect_tolerant(q, min_evidence=min_ev, k_pitch=2,
                                        k_bin=1, k_vel=1, cfg=cfg_q,
                                        pieces_of_interest={pl["donor"]})
            wall.append(time.time() - t0)
            score = r.scores_of_interest.get(pl["donor"], 0)
            ok += score >= min_ev
            fp += max(0, len(r.hits) - (1 if score >= min_ev else 0))
        results.append({"ablation": "E5.7_grid", "tpb": tpb,
                        "grid_ms": 1000 // tpb, "recall": f"{ok}/{done}",
                        "false_candidates": fp, "postings": len(index_q.postings),
                        "wall_p50_ms": sorted(wall)[len(wall) // 2] * 1000})
        print(f"E5.7 grid={1000//tpb}ms: recall {ok}/{done}, FP {fp}, "
              f"vocab {len(index_q.postings)}", flush=True)

    with open(OUT, "a", encoding="utf-8") as f:
        for rec in results:
            f.write(json.dumps(rec) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
