# -*- coding: utf-8 -*-
"""E1 transformation suite: six realistic mutation types applied to event
lists (MIDI level), used to plant near-verbatim copies of corpus pieces.

Each transform takes (events, rng, strength) and returns a new event list.
Deterministic given the seeded rng.  Semantics follow experiment_plan.md
E1.1: verbatim / transposition / tempo / note split-merge / instrumentation /
transcription round-trip.

The transcription round-trip is approximated at the symbol level (onset &
duration quantization noise, missed notes, spurious notes); the audio-stage
version (MIDI->audio->MT3/BasicPitch->detect) is E2.3 and reuses the same
planting code with a real transcriber plugged in.
"""
from __future__ import annotations

import random

from .midi_encode import Event

__all__ = ["copy_span", "transpose", "tempo_scale", "split_merge",
           "reinstrument", "transcribe_noise", "TRANSFORMS"]


def copy_span(events: list[Event], rng: random.Random,
              n_events: int) -> list[Event]:
    """Extract a contiguous (in onset order) span of n_events events."""
    if not events:
        return []
    order = sorted(events, key=lambda e: (e.onset_tick, e.pitch))
    if len(order) <= n_events:
        return list(order)
    start = rng.randrange(len(order) - n_events + 1)
    return list(order[start:start + n_events])


def _shift(events: list[Event], dt: int) -> list[Event]:
    t0 = min(e.onset_tick for e in events)
    return [Event(e.onset_tick - t0 + dt, e.pitch, e.duration_tick,
                  e.channel, e.velocity) for e in events]


def transpose(events: list[Event], rng: random.Random,
              semitones: int | None = None) -> list[Event]:
    """Global transposition within [-st, st] (default ±2), pitch clipped to
    [21, 108]."""
    st = semitones if semitones is not None else rng.choice([-2, -1, 1, 2])
    return [Event(e.onset_tick, min(108, max(21, e.pitch + st)),
                  e.duration_tick, e.channel, e.velocity) for e in events]


def tempo_scale(events: list[Event], rng: random.Random,
                factor: float | None = None) -> list[Event]:
    """Uniformly scale onsets and durations (default 0.9 / 1.1)."""
    f = factor or rng.choice([0.9, 1.1])
    return [Event(int(round(e.onset_tick * f)), e.pitch,
                  max(1, int(round(e.duration_tick * f))),
                  e.channel, e.velocity) for e in events]


def split_merge(events: list[Event], rng: random.Random,
                p: float = 0.15) -> list[Event]:
    """With probability p per event: split one note into two halves, or merge
    a note with its onset-neighbour ( deleting the neighbour)."""
    out: list[Event] = []
    order = sorted(events, key=lambda e: (e.onset_tick, e.pitch))
    i = 0
    while i < len(order):
        e = order[i]
        if rng.random() < p:
            if rng.random() < 0.5 and e.duration_tick >= 4:
                h = e.duration_tick // 2
                out.append(Event(e.onset_tick, e.pitch, h, e.channel,
                                 e.velocity))
                out.append(Event(e.onset_tick + h, e.pitch,
                                 e.duration_tick - h, e.channel, e.velocity))
                i += 1
                continue
            if i + 1 < len(order):
                nxt = order[i + 1]
                dur = (nxt.onset_tick + nxt.duration_tick) - e.onset_tick
                out.append(Event(e.onset_tick, e.pitch, max(1, dur),
                                 e.channel,
                                 max(e.velocity, nxt.velocity)))
                i += 2
                continue
        out.append(e)
        i += 1
    return out


def reinstrument(events: list[Event], rng: random.Random,
                 p_drop: float = 0.2) -> list[Event]:
    """Randomly reassign channels and drop p_drop of the events (parts)."""
    out = []
    remap = {}
    for e in events:
        if rng.random() < p_drop:
            continue
        if e.channel not in remap:
            remap[e.channel] = rng.randrange(16)
        out.append(Event(e.onset_tick, e.pitch, e.duration_tick,
                         remap[e.channel], e.velocity))
    return out


def transcribe_noise(events: list[Event], rng: random.Random,
                     q_ms: int = 30, p_miss: float = 0.08,
                     p_extra: float = 0.05) -> list[Event]:
    """Symbol-level transcription round-trip approximation: onsets/durations
    jittered by up to q_ms, p_miss of notes lost, p_extra spurious notes."""
    out = []
    for e in events:
        if rng.random() < p_miss:
            continue
        j = lambda v: v + rng.randint(-q_ms, q_ms)  # noqa: E731
        out.append(Event(max(0, j(e.onset_tick)), e.pitch,
                         max(1, j(e.duration_tick)), 0, e.velocity))
    for _ in range(int(len(events) * p_extra)):
        base = rng.choice(events)
        out.append(Event(max(0, base.onset_tick + rng.randint(-60, 60)),
                         min(108, max(21, base.pitch + rng.choice([-2, -1, 1, 2]))),
                         max(1, base.duration_tick), 0,
                         rng.randint(30, 110)))
    return out


TRANSFORMS = {
    "verbatim": lambda ev, rng, s=1.0: list(ev),
    "transpose": transpose,
    "tempo": tempo_scale,
    "split_merge": split_merge,
    "reinstrument": reinstrument,
    "transcribe": transcribe_noise,
}
