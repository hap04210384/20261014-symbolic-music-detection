# -*- coding: utf-8 -*-
"""Query-side exact-subset detector (rare-first anytime).

Rationale (docs/feasibility_cutoff2.md): enumerating all MFIs of the
corpus+query DB at cutoff 2 is combinatorially infeasible on real music
(11.3M frequent pairs at N=300).  Detection is fundamentally SET CONTAINMENT:

    hit  <=>  span S, |S| >= min_evidence,  S ⊆ Q  and  S ⊆ C_i for some i.

The corpus is stored as an inverted index (item -> sorted piece-id array).
A query is answered by accumulating, over its items, piece counters; the
completeness argument is exact and threshold-free:

  * recall guarantee: any verbatim span of >= min_evidence items makes
    every one of its items shared with the donor piece, so the donor's
    counter reaches min_evidence no matter the processing order;
  * anytime: items are processed rarest-first (ascending corpus frequency),
    so evidence-bearing pieces surface early; at any stop point the set of
    pieces that can still become hits is exactly
        { i : cnt[i] + U >= min_evidence },  U = #unprocessed query items,
    which is reported as the provable incompleteness bound.

This replaces the "mine corpus+query at sigma=2/(N+1)" protocol of
docs/adapter_design.md §2 (measured infeasible 2026-10-12); the FIM engines
remain as experimental baselines (GivenThreshold at feasible thresholds).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .midi_encode import EncodingConfig

__all__ = ["CorpusIndex", "DetectionResult", "Hit", "item_decode", "item_encode"]


DEFAULT_CFG = EncodingConfig(use_channel=False)


def item_decode(code: int, cfg: EncodingConfig = DEFAULT_CFG):
    """Inverse of midi_encode.events_to_items (use_channel=False)."""
    x = code - 1
    v = x % cfg.vel_bins
    x //= cfg.vel_bins
    g = x % cfg.ioi_bins
    x //= cfg.ioi_bins
    d = x % cfg.dur_bins
    pitch = x // cfg.dur_bins
    return pitch, d, g, v


def item_encode(pitch: int, d: int, g: int, v: int,
                cfg: EncodingConfig = DEFAULT_CFG) -> int:
    return ((((pitch * cfg.dur_bins + d) * cfg.ioi_bins + g)
             * cfg.vel_bins + v)) + 1


@dataclass
class Hit:
    piece: int            # corpus piece id
    score: int            # |Q ∩ C_i|
    span: list[int]       # the shared items (Q ∩ C_i), ascending


@dataclass
class DetectionResult:
    hits: list[Hit]
    n_candidates_remaining: int   # provable bound: pieces that can still hit
    items_processed: int
    items_total: int
    wall_secs: float
    per_item_secs: list[float] = field(default_factory=list)
    scores_of_interest: dict[int, int] = field(default_factory=dict)


class CorpusIndex:
    """Inverted index over a corpus of item-set transactions."""

    def __init__(self, txns: list[set[int]] | None = None):
        self.n_pieces = 0
        self.postings: dict[int, np.ndarray] = {}
        self.txns: list[set[int]] | None = None
        if txns is not None:
            self.build(txns)

    def build(self, txns: list[set[int]]) -> None:
        self.n_pieces = len(txns)
        self.txns = txns
        lists: dict[int, list[int]] = {}
        for i, t in enumerate(txns):
            for x in t:
                lists.setdefault(x, []).append(i)
        self.postings = {x: np.asarray(v, dtype=np.int32)
                         for x, v in lists.items()}

    # -- persistence ----------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        meta = {"n_pieces": self.n_pieces}
        (path / "meta.json").write_text(json.dumps(meta))
        with open(path / "postings.npz", "wb") as f:
            np.savez(f, **{str(k): v for k, v in self.postings.items()})

    @classmethod
    def load(cls, path: str | Path) -> "CorpusIndex":
        path = Path(path)
        obj = cls()
        obj.n_pieces = json.loads((path / "meta.json").read_text())["n_pieces"]
        with open(path / "postings.npz", "rb") as f:
            z = np.load(f)
            obj.postings = {int(k): z[k] for k in z.files}
        obj.txns = None  # corpus txns not persisted (rebuild from FIMI if needed)
        return obj

    # -- detection -------------------------------------------------------
    def detect(self, query: set[int], min_evidence: int = 8,
               max_items: int | None = None,
               order: str = "rare") -> DetectionResult:
        """Rare-first anytime detection. max_items = process only the
        max_items rarest query items (anytime budget in items).
        order: 'rare' (ascending corpus freq), 'hot' (descending), 'random'."""
        import time
        t0 = time.time()
        # rarest-first order
        present = [x for x in query if x in self.postings]
        if order == "rare":
            present.sort(key=lambda x: (len(self.postings[x]), x))
        elif order == "hot":
            present.sort(key=lambda x: (-len(self.postings[x]), x))
        elif order == "random":
            import random as _r
            _r.Random(0).shuffle(present)
        else:
            raise ValueError(order)
        if max_items is not None:
            present = present[:max_items]

        n = self.n_pieces
        cnt = np.zeros(n, dtype=np.int32)
        processed = 0
        per_item: list[float] = []
        for x in present:
            ta = time.time()
            np.add.at(cnt, self.postings[x], 1)
            per_item.append(time.time() - ta)
            processed += 1
        hits = [Hit(int(i), int(cnt[i]), sorted(query & self.txns[i]))
                for i in np.nonzero(cnt >= min_evidence)[0]]
        hits.sort(key=lambda h: -h.score)
        u = len(query) - processed  # upper bound of unprocessed query items
        remaining = int(np.count_nonzero(cnt + u >= min_evidence)) - len(hits)
        return DetectionResult(hits=hits,
                               n_candidates_remaining=max(0, remaining),
                               items_processed=processed,
                               items_total=len(query),
                               wall_secs=time.time() - t0,
                               per_item_secs=per_item)

    # ------------------------------------------------------------------
    # k-tolerant detection (SP3): per-position bounded deviation
    # ------------------------------------------------------------------
    def detect_tolerant(self, query: set[int], min_evidence: int = 8,
                        k_pitch: int = 2, k_bin: int = 1, k_vel: int = 1,
                        cfg: EncodingConfig = DEFAULT_CFG,
                        max_positions: int | None = None,
                        order: str = "rare",
                        pieces_of_interest: set[int] | None = None) -> DetectionResult:
        """Per-position counting: a corpus piece scores +1 for each query
        position for which it contains ANY variant of that position's item,
        where variants vary pitch by <=k_pitch semitones, dur/ioi by <=k_bin
        bins, and velocity by <=k_vel bins.  Velocity is tolerated because
        it is the least stable feature under transcription (2026-10-12 E2:
        without it the bound is mathematically unsound).
        Recall guarantee: a copy whose per-position deviation stays within
        (k_pitch, k_bin, k_vel) scores the full span length, exactly like
        verbatim.  Anytime bound identical to detect().
        order: 'rare' (ascending min-variant support), 'hot', 'random'."""
        import time
        t0 = time.time()
        # positions = query items, rarest-first (by rarest variant support)
        def rarest_support(x: int) -> int:
            p, d, g, v = item_decode(x, cfg)
            best = None
            for dp in range(-k_pitch, k_pitch + 1):
                for dd in range(-k_bin, k_bin + 1):
                    for dg in range(-k_bin, k_bin + 1):
                        for dv in range(-k_vel, k_vel + 1):
                            pp = p + dp
                            vv = v + dv
                            dd2, gg2 = d + dd, g + dg
                            if pp < 0 or vv < 0 or vv >= cfg.vel_bins \
                                    or not (0 <= dd2 < cfg.dur_bins) \
                                    or not (0 <= gg2 < cfg.ioi_bins):
                                continue
                            code = item_encode(pp, dd2, gg2, vv, cfg)
                            n = len(self.postings.get(code, ()))
                            best = n if best is None else min(best, n)
            return best if best is not None else 0

        # positions = ALL query items; a query item absent from the corpus can
        # still be matched by its variants (2026-10-12 E2: filtering here
        # silently dropped ~10% of positions and broke the bound)
        present = list(query)
        if order == "rare":
            present.sort(key=lambda x: (rarest_support(x), x))
        elif order == "hot":
            present.sort(key=lambda x: (-rarest_support(x), x))
        elif order == "random":
            import random as _r
            _r.Random(0).shuffle(present)
        else:
            raise ValueError(order)
        if max_positions is not None:
            present = present[:max_positions]

        cnt = np.zeros(self.n_pieces, dtype=np.int32)
        processed = 0
        per_item: list[float] = []
        for x in present:
            ta = time.time()
            p, d, g, v = item_decode(x, cfg)
            lists = []
            for dp in range(-k_pitch, k_pitch + 1):
                for dd in range(-k_bin, k_bin + 1):
                    for dg in range(-k_bin, k_bin + 1):
                        for dv in range(-k_vel, k_vel + 1):
                            pp = p + dp
                            vv = v + dv
                            dd2, gg2 = d + dd, g + dg
                            if pp < 0 or vv < 0 or vv >= cfg.vel_bins \
                                    or not (0 <= dd2 < cfg.dur_bins) \
                                    or not (0 <= gg2 < cfg.ioi_bins):
                                continue
                            code = item_encode(pp, dd2, gg2, vv, cfg)
                            arr = self.postings.get(code)
                            if arr is not None:
                                lists.append(arr)
            if lists:
                union = np.unique(np.concatenate(lists))
                np.add.at(cnt, union, 1)
            per_item.append(time.time() - ta)
            processed += 1

        hits = []
        if self.txns is not None:
            hits = [Hit(int(i), int(cnt[i]),
                        sorted(query & self.txns[i]))
                    for i in np.nonzero(cnt >= min_evidence)[0]]
        else:
            hits = [Hit(int(i), int(cnt[i]), [])
                    for i in np.nonzero(cnt >= min_evidence)[0]]
        hits.sort(key=lambda h: -h.score)
        u = len(query) - processed
        remaining = int(np.count_nonzero(cnt + u >= min_evidence)) - len(hits)
        result = DetectionResult(hits=hits,
                                 n_candidates_remaining=max(0, remaining),
                                 items_processed=processed,
                                 items_total=len(query),
                                 wall_secs=time.time() - t0,
                                 per_item_secs=per_item)
        if pieces_of_interest:
            result.scores_of_interest = {
                int(i): int(cnt[i]) for i in pieces_of_interest}
        return result
