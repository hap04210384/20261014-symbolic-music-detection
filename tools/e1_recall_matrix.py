# -*- coding: utf-8 -*-
"""E1.1 precursor: tolerant-detector recall on six transforms (real corpus
pieces, event-level planting).

Builds an Event-list corpus from one parquet shard, plants a span of a real
piece into a query, applies each transform at event level, encodes the query
and runs detect_tolerant.  Reports recall per transform x k.

This is the precursor of the full E1.1 matrix (4 lengths x 3-5 strengths x
5 seeds); it answers "does the k-tolerant layer recover each transform at
all" before the full matrix is run.
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, Event, events_to_items  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from adapter import transforms as T  # noqa: E402
import duckdb  # noqa: E402

N_PIECES = 1000
SPAN = 40
PLANTS = 10
K_PITCH = 2
K_BIN = 1


def load_events(shard: Path, limit: int) -> list[list[Event]]:
    con = duckdb.connect()
    ev_corpus: list[list[Event]] = []
    off = 0
    while len(ev_corpus) < limit:
        df = con.execute(
            f"SELECT notes.start AS s, notes.\"end\" AS e, notes.pitch AS p, "
            f"notes.velocity AS v FROM read_parquet('{shard}') "
            f"LIMIT 500 OFFSET {off}").df()
        if len(df) == 0:
            break
        for _, row in df.iterrows():
            ev = [Event(int(round(float(s) * 1000)), int(p),
                        max(1, int(round((float(e) - float(s)) * 1000))), 0,
                        int(v))
                  for s, e, p, v in zip(row["s"], row["e"], row["p"], row["v"])]
            ev_corpus.append(ev)
        off += 500
    return ev_corpus[:limit]


def main() -> int:
    cfg = EncodingConfig(use_channel=False)
    shard = ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet"
    ev_corpus = load_events(shard, N_PIECES)
    txns = [events_to_items(sorted(ev, key=lambda e: (e.onset_tick, e.pitch)),
                            1000, cfg)[0] for ev in ev_corpus]
    index = CorpusIndex(txns)
    print(f"corpus={len(txns)} pieces, vocab={len(index.postings)}")

    rng = random.Random(23)
    print(f"\n{'transform':14s} {'recall':>8s} {'avg_top':>8s} {'ms/q':>7s}")
    for name, fn in T.TRANSFORMS.items():
        ok = 0
        done = 0
        scores = []
        lat = []
        for p in range(PLANTS):
            donor = rng.randrange(len(ev_corpus))
            span = T.copy_span(ev_corpus[donor], rng, SPAN)
            if len(span) < SPAN:
                continue
            mutated = fn(span, rng)
            q_items, _ = events_to_items(
                sorted(mutated, key=lambda e: (e.onset_tick, e.pitch)),
                1000, cfg)
            # guarantee is about DISTINCT evidence items: a 40-event span of a
            # 4-note loop carries < 20 distinct items; such spans cannot meet
            # min_evidence=20 by construction.  Resample donors until the
            # planted span carries enough distinct evidence.
            if len(q_items) < 25:
                continue
            done += 1
            # evidence: fraction of planted span still present after transform,
            # capped by span length; min_evidence = SPAN//2 to allow loss
            t0 = time.time()
            r = index.detect_tolerant(q_items, min_evidence=max(8, SPAN // 2),
                                      k_pitch=K_PITCH, k_bin=K_BIN, cfg=cfg)
            lat.append((time.time() - t0) * 1000)
            hit = any(h.piece == donor for h in r.hits)
            ok += hit
            scores.append(r.hits[0].score if r.hits else 0)
        print(f"{name:14s} {ok}/{done:<5d}  {np.mean(scores) if scores else 0:8.1f} "
              f"{np.mean(lat) if lat else 0:7.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
