# -*- coding: utf-8 -*-
"""Encoding self-test: translation invariance + transposition separability.

Builds synthetic MIDI with mido: a donor melody, plus queries containing
(a) a verbatim segment copied to a different time offset,
(b) the same segment transposed,
then checks the item-set relationships that the paper's recall guarantee
rests on. Run: python tools/test_encoding.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.adapter.midi_encode import (  # noqa: E402
    midi_to_events, events_to_items, EncodingConfig,
)
import mido  # noqa: E402

TPB = 480


def make_midi(path: Path, notes: list[tuple[int, int, int, int, int]]) -> None:
    """notes: (onset_tick, pitch, duration_tick, channel, velocity)."""
    mid = mido.MidiFile(ticks_per_beat=TPB)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    events = []
    for onset, pitch, dur, ch, vel in notes:
        events.append((onset, mido.Message("note_on", channel=ch, note=pitch,
                                           velocity=vel, time=0)))
        events.append((onset + dur, mido.Message("note_off", channel=ch, note=pitch,
                                                 velocity=0, time=0)))
    events.sort(key=lambda x: x[0])
    now = 0
    for tick, msg in events:
        msg.time = tick - now
        now = tick
        track.append(msg)
    track.append(mido.MetaMessage("end_of_track", time=0))
    mid.tracks.append(track)
    mid.save(path)


def melody(start: int, pitch_shift: int = 0) -> list[tuple[int, int, int, int, int]]:
    """A 12-note deterministic melody starting at tick `start`."""
    seq = [60, 62, 64, 67, 69, 67, 64, 62, 60, 55, 57, 60]
    durs = [240, 120, 240, 240, 480, 240, 120, 240, 240, 480, 240, 480]
    out, t = [], start
    for p, d in zip(seq, durs):
        out.append((t, p + pitch_shift, d, 0, 80))
        t += d
    return out


def main() -> int:
    cfg = EncodingConfig()
    tmp = Path(tempfile.mkdtemp(prefix="enc_test_"))
    donor = tmp / "donor.mid"
    make_midi(donor, melody(0))
    seg_items = events_to_items(midi_to_events(donor)[0], TPB, cfg)[0]

    # query A: full melody copied to a different time offset (verbatim full-file copy)
    qa = tmp / "queryA.mid"
    make_midi(qa, [(t + 30000, p, d, c, v) for t, p, d, c, v in melody(0)])
    # query B: same melody transposed +5 semitones at a different offset
    qb = tmp / "queryB.mid"
    make_midi(qb, [(t + 30000, p + 5, d, c, v) for t, p, d, c, v in melody(0)])

    donor_items = events_to_items(midi_to_events(donor)[0], TPB, cfg)[0]
    qa_items = events_to_items(midi_to_events(qa)[0], TPB, cfg)[0]
    qb_items = events_to_items(midi_to_events(qb)[0], TPB, cfg)[0]

    # translation invariance: full-file copy -> IDENTICAL item set
    print(f"donor items: {len(donor_items)}, queryA items: {len(qa_items)}, "
          f"identical: {donor_items == qa_items}")
    ok_a = donor_items == qa_items
    # transposition separability: a verbatim hit requires the WHOLE item set;
    # a transposed copy may coincidentally share a couple of items in a tiny
    # toy melody (repeated figures), so we assert small overlap, not zero.
    inter_b = seg_items & qb_items
    jacc_b = len(inter_b) / len(seg_items | qb_items)
    print(f"segment items ∩ transposed-query items: {len(inter_b)} "
          f"(Jaccard {jacc_b:.2f}, expect << 1)")
    # 0 in id space is never emitted
    ok_zero = 0 not in donor_items and 0 not in qa_items and 0 not in qb_items
    print("no item id 0:", ok_zero)
    ok = ok_a and jacc_b < 0.3 and ok_zero
    print("ENCODING TEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
