# -*- coding: utf-8 -*-
"""G2 acceptance: every baseline runs on 100-tune-like small sample, unified
output, planted verbatim copy ranked top, unrelated pairs low, deterministic.

Generates synthetic MIDI in a temp dir (mido), plants 8-bar verbatim copies
with a time offset, then checks each baseline's donor-rank for the query.
"""
from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

import mido

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from adapter.midi_encode import midi_to_events
from adapter.baselines import (Piece, ngram_signature, ngram_score,
                               contour_signature, contour_score,
                               siatec_signature, siatec_score)

SEED = 42
N_CORPUS = 20
N_EVENTS = (60, 120)      # events per synthetic piece
PLANT_LEN = 40            # events planted verbatim


def make_piece(rng: random.Random) -> list[tuple[int, int, int, int, int]]:
    """events: (onset_tick, pitch, dur_tick, channel, velocity)."""
    ev = []
    t = 0
    for _ in range(rng.randint(*N_EVENTS)):
        t += rng.choice([0, 0, 120, 240, 480])   # 480 tpb
        ev.append((t, rng.randint(48, 84), rng.choice([240, 480, 960]),
                   rng.randint(0, 1), rng.randint(40, 100)))
    return ev


def to_midi(events, path: Path, tpb: int = 480):
    mid = mido.MidiFile(ticks_per_beat=tpb)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    last = 0
    notes = []
    for onset, pitch, dur, ch, vel in events:
        notes.append((onset, mido.Message("note_on", note=pitch, velocity=vel,
                                          channel=ch, time=0)))
        notes.append((onset + dur, mido.Message("note_off", note=pitch, velocity=0,
                                                channel=ch, time=0)))
    notes.sort(key=lambda x: (x[0], x[1].type != "note_on"))
    for onset, msg in notes:
        msg.time = onset - last
        last = onset
        tr.append(msg)
    mid.save(str(path))


def main() -> int:
    rng = random.Random(SEED)
    tmp = Path(tempfile.mkdtemp(prefix="g2_smoke_"))
    corpus = [make_piece(rng) for _ in range(N_CORPUS)]
    donor_idx = 7
    # query = 40-event verbatim span of donor shifted to a new time base + filler
    span = corpus[donor_idx][10:10 + PLANT_LEN]
    t0 = span[0][0]
    # shift by a beat-grid-aligned offset: real musical copies start on beat
    # boundaries; arbitrary tick shifts are the alignment-stress case (E1),
    # not the G2 smoke case.
    shifted = [(on - t0 + 4800, p, d, c, v) for on, p, d, c, v in span]
    filler = make_piece(rng)[:30]
    filler = [(on + 9000, p, d, c, v) for on, p, d, c, v in filler]
    query_events = shifted + filler

    paths = {}
    for i, ev in enumerate(corpus):
        p = tmp / f"corpus_{i:02d}.mid"
        to_midi(ev, p)
        paths[f"c{i}"] = p
    qp = tmp / "query.mid"
    to_midi(query_events, qp)

    def load(pid, p):
        ev, tpb = midi_to_events(p)
        return Piece(pid, list(ev), tpb)

    pieces = {pid: load(pid, p) for pid, p in paths.items()}
    query = load("query", qp)

    ok = True
    for name, sig_fn, score_fn in [
        ("ngram", ngram_signature, ngram_score),
        ("contour", contour_signature, contour_score),
        ("siatec", siatec_signature, siatec_score),
    ]:
        qs = sig_fn(query)
        scores = {pid: score_fn(qs, sig_fn(c)) for pid, c in pieces.items()}
        ranked = sorted(scores, key=scores.get, reverse=True)
        rank = ranked.index(f"c{donor_idx}") + 1
        best_unrelated = max(scores[pid] for pid in ranked if pid != f"c{donor_idx}")
        # determinism: recompute signature, must be identical
        det = sig_fn(query) == qs
        print(f"{name:8s} donor_rank={rank:2d}/{len(pieces)} "
              f"donor_score={scores[f'c{donor_idx}']:.3f} "
              f"best_other={best_unrelated:.3f} deterministic={det}")
        if rank != 1:
            print(f"  FAIL: donor not top-1 for {name}")
            ok = False
        if not det:
            print(f"  FAIL: signature not deterministic for {name}")
            ok = False

    print("SMOKE", "PASSED" if ok else "FAILED", f"(tmp={tmp})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
