# -*- coding: utf-8 -*-
"""MIDI -> event set -> FIM item encoding (translation-invariant).

Design (docs/adapter_design.md §2, extended 2026-10-11):
  * event = (onset_tick, pitch, duration_tick, channel, velocity), absolute
    ticks via mido.
  * item = mixed-radix code of (pitch, dur_bin, ioi_bin, vel_bin, channel),
    where ioi = onset gap to the NEXT event in onset-sorted order.
    Because no absolute onset is encoded, a segment copied to a different
    time offset yields the SAME item set — that is what makes verbatim-copy
    recall a set-inclusion property (engine-verifiable, G3.4 gate 3).
  * Grid quantization granularity (tpb = ticks-per-beat of the grid, i.e.
    1/tpb beat resolution) is an E5.7 sweep parameter; dur/ioi overflow
    collapses into the last bin.
  * item id 0 is reserved (engines mishandle it): mixed-radix codes start
    at 1 by construction (pitch term >= 1).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mido


@dataclass(frozen=True)
class Event:
    onset_tick: int
    pitch: int
    duration_tick: int
    channel: int
    velocity: int


@dataclass(frozen=True)
class EncodingConfig:
    tpb: int = 8            # grid resolution: 1/tpb beat
    dur_bins: int = 16      # duration bins (last bin = overflow)
    ioi_bins: int = 16      # inter-onset interval bins (last bin = overflow)
    vel_bins: int = 8       # velocity bins (last bin = overflow)
    use_channel: bool = True

    def param_hash(self) -> str:
        return (f"tpb{self.tpb}-dur{self.dur_bins}-ioi{self.ioi_bins}"
                f"-vel{self.vel_bins}-ch{int(self.use_channel)}")


def midi_to_events(path: str | Path) -> tuple[list[Event], int]:
    """Parse a MIDI file into events. Returns (events, ticks_per_beat)."""
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat
    events: list[Event] = []
    # per-track absolute tick accumulation; pair note_on with note_off
    for track in mid.tracks:
        now = 0
        open_notes: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for msg in track:
            now += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                open_notes.setdefault((msg.channel, msg.note), []).append((now, msg.velocity))
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                stack = open_notes.get((msg.channel, msg.note))
                if stack:
                    start, vel = stack.pop(0)
                    events.append(Event(start, msg.note, now - start, msg.channel, vel))
    events.sort(key=lambda e: (e.onset_tick, e.pitch))
    return events, tpb


def _bin(value_tick: int, ticks_per_beat: int, grid_tpb: int, n_bins: int) -> int:
    """Quantize a tick length onto a 1/grid_tpb-beat grid; overflow -> last bin."""
    grid = max(1, ticks_per_beat // grid_tpb) if ticks_per_beat >= grid_tpb else 1
    g = (value_tick + grid // 2) // grid
    return min(g, n_bins - 1)


def events_to_items(events: list[Event], file_tpb: int,
                    cfg: EncodingConfig = EncodingConfig()) -> tuple[set[int], dict]:
    """Encode events into FIM items.

    Returns (item_set, meta) where meta maps item -> component tuple
    (pitch, dur_bin, ioi_bin, vel_bin, channel) for unmapping/locating.
    """
    if not events:
        return set(), {}
    n_ch = 16 if cfg.use_channel else 1
    items: set[int] = set()
    meta: dict[int, tuple] = {}
    ordered = sorted(events, key=lambda e: (e.onset_tick, e.pitch))
    for idx, e in enumerate(ordered):
        nxt = ordered[idx + 1] if idx + 1 < len(ordered) else None
        ioi_tick = (nxt.onset_tick - e.onset_tick) if nxt else 0
        d = _bin(e.duration_tick, file_tpb, cfg.tpb, cfg.dur_bins)
        g = _bin(ioi_tick, file_tpb, cfg.tpb, cfg.ioi_bins)
        v = min(e.velocity >> (7 - (cfg.vel_bins - 1).bit_length()), cfg.vel_bins - 1) \
            if cfg.vel_bins < 128 else e.velocity
        ch = e.channel if cfg.use_channel else 0
        code = ((((e.pitch * cfg.dur_bins + d) * cfg.ioi_bins + g)
                 * cfg.vel_bins + v) * n_ch + ch) + 1  # +1: reserve id 0
        items.add(code)
        meta[code] = (e.pitch, d, g, v, ch)
    return items, meta
