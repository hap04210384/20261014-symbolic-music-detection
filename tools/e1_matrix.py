# -*- coding: utf-8 -*-
"""E1.1 production matrix: transform x strength x length x seed -> recall.

Length axis is in SECONDS (2/4/8/16 s): the Lakh parquet export carries no
meter/tempo, so bars cannot be recovered; seconds are the honest unit and
map monotonically to musical length.  min_evidence = min(8, half the planted
span's distinct items) with the distinct-evidence guarantee semantics.

Incremental: appends to runs/e1/matrix.jsonl; existing (transform, strength,
length, seed) cells are skipped.

Corpus: event lists from one parquet shard (N_PIECES pieces).  For the
paper, the same script reruns against the full corpus once all shards are
downloaded (--shard-dir and --pieces args make it automatic).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, Event, events_to_items  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from adapter import transforms as T  # noqa: E402
import duckdb  # noqa: E402

OUT = ROOT / "runs/e1/matrix.jsonl"

GRID = {
    # transform: list of strength values
    "verbatim": [None],
    "transpose": [1, 2, 4, 6],
    "tempo": [1.05, 1.10, 1.20],
    "split_merge": [0.10, 0.20, 0.30],
    "reinstrument": [0.10, 0.25, 0.40],
    "transcribe": [(15, 0.04), (30, 0.08), (60, 0.15)],
}
LENGTHS_S = [2, 4, 8, 16]
SEEDS = [1, 2, 3, 4, 5]


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


def span_seconds(events: list[Event], rng: random.Random,
                 seconds: int) -> list[Event]:
    """Contiguous events inside a seconds-long window of the piece."""
    if not events:
        return []
    t0 = events[0][0] if isinstance(events[0], tuple) else None
    order = sorted(events, key=lambda e: (e.onset_tick, e.pitch))
    start_tick = order[0].onset_tick
    latest = order[-1].onset_tick - seconds * 1000
    if latest <= start_tick:
        return list(order)
    dt = rng.randrange(int(latest - start_tick))
    lo = start_tick + dt
    hi = lo + seconds * 1000
    return [e for e in order if lo <= e.onset_tick < hi]


def apply(name: str, span, rng, strength):
    if name == "verbatim":
        return list(span)
    if name == "transpose":
        return T.transpose(span, rng, semitones=strength if strength else 2)
    if name == "tempo":
        return T.tempo_scale(span, rng, factor=strength)
    if name == "split_merge":
        return T.split_merge(span, rng, p=strength)
    if name == "reinstrument":
        return T.reinstrument(span, rng, p_drop=strength)
    if name == "transcribe":
        q_ms, p_miss = strength
        return T.transcribe_noise(span, rng, q_ms=q_ms, p_miss=p_miss)
    raise ValueError(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces", type=int, default=1000)
    ap.add_argument("--k-pitch", type=int, default=2)
    ap.add_argument("--k-bin", type=int, default=1)
    args = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    done = set()
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            if ln.strip():
                d = json.loads(ln)
                done.add((d["transform"], json.dumps(d["strength"], sort_keys=True),
                          d["length_s"], d["seed"]))

    cfg = EncodingConfig(use_channel=False)
    shard = ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet"
    ev_corpus = load_events(shard, args.pieces)
    txns = [events_to_items(sorted(ev, key=lambda e: (e.onset_tick, e.pitch)),
                            1000, cfg)[0] for ev in ev_corpus]
    index = CorpusIndex(txns)
    print(f"corpus={len(txns)}, vocab={len(index.postings)}")

    for name, strengths in GRID.items():
        for strength in strengths:
            for L in LENGTHS_S:
                for seed in SEEDS:
                    key = (name, json.dumps(strength, sort_keys=True), L, seed)
                    if key in done:
                        continue
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
                    t0 = time.time()
                    r = index.detect_tolerant(
                        q_items, min_evidence=min_ev,
                        k_pitch=args.k_pitch, k_bin=args.k_bin, k_vel=1, cfg=cfg)
                    wall = time.time() - t0
                    hit = any(h.piece == donor for h in r.hits)
                    rec = {
                        "transform": name, "strength": strength, "length_s": L,
                        "seed": seed, "k_pitch": args.k_pitch,
                        "k_bin": args.k_bin,
                        "n_span_events": len(span),
                        "n_span_items": n_span_items,
                        "min_evidence": min_ev,
                        "hit": hit,
                        "top_score": r.hits[0].score if r.hits else 0,
                        "n_hits": len(r.hits),
                        "wall_ms": round(wall * 1000, 1),
                    }
                    with open(OUT, "a", encoding="utf-8") as f:
                        f.write(json.dumps(rec) + "\n")
                    done.add(key)
                print(f"{name} s={strength} L={L}s done "
                      f"(cells={len(done)})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
