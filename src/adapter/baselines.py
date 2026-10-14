# -*- coding: utf-8 -*-
"""G2 baselines for the copy-detection comparison, unified hit format.

Every baseline exposes:
    signature(piece) -> opaque per-piece representation
    score(query_sig, corpus_sig) -> float in [0,1]  (1 = certain copy)
and a convenience `detect(query, corpus, threshold)` returning Hit|None.

Baselines (experiment_plan.md G2.1-G2.5):
  * SIATEC / COSIATEC  — point-set pattern discovery (Meredith et al. 2002)
  * n-gram piano-roll hash + Jaccard
  * melodic contour edit distance
  * MERT embedding cosine (G2.5) — interface only; weights download is
    network-blocked in this environment, flagged TODO.

Pieces are represented as event lists from midi_encode.Event so all baselines
share the same parsing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from .midi_encode import Event, EncodingConfig

__all__ = ["Hit", "Piece", "ngram_signature", "ngram_score", "contour_signature",
           "contour_score", "siatec", "cosiatec", "siatec_signature",
           "siatec_score", "detect"]


@dataclass
class Hit:
    query_id: str
    corpus_id: str
    score: float
    method: str
    detail: dict = field(default_factory=dict)


@dataclass
class Piece:
    """A parsed musical piece: identity + events + ticks-per-beat."""
    pid: str
    events: list[Event]
    ticks_per_beat: int


def _stable_hash(obj) -> int:
    """Deterministic process-independent hash (built-in hash() is salted)."""
    return int.from_bytes(
        hashlib.blake2b(repr(obj).encode(), digest_size=8).digest(), "big")


# ---------------------------------------------------------------------------
# G2.3  n-gram piano-roll hash + Jaccard
# ---------------------------------------------------------------------------

def _roll_frames(events: list[Event], tpb_file: int, grid_tpb: int = 4):
    """Quantize events onto a 1/grid_tpb-beat grid; return list of frames,
    each frame = frozenset of pitches sounding/starting at that frame."""
    grid = max(1, tpb_file // grid_tpb)
    onsets: dict[int, set[int]] = {}
    for e in events:
        onsets.setdefault(e.onset_tick // grid, set()).add(e.pitch)
    if not onsets:
        return []
    last = max(onsets)
    return [frozenset(onsets.get(t, ())) for t in range(last + 1)]


def ngram_signature(piece: Piece, window: int = 8, hop: int = 2,
                    grid_tpb: int = 4) -> set[int]:
    """Shingle set: hash of each window's (relative onset, pitch) tuple."""
    frames = _roll_frames(piece.events, piece.ticks_per_beat, grid_tpb)
    out: set[int] = set()
    for i in range(0, max(0, len(frames) - window + 1), hop):
        seg = frames[i:i + window]
        shingle = tuple(
            (dt, p) for dt, frame in enumerate(seg) for p in sorted(frame)
        )
        out.add(_stable_hash(shingle))
    return out


def ngram_score(q: set[int], c: set[int]) -> float:
    if not q or not c:
        return 0.0
    inter = len(q & c)
    return inter / (len(q) + len(c) - inter)


# ---------------------------------------------------------------------------
# G2.4  melodic contour edit distance
# ---------------------------------------------------------------------------

_CONTOUR_MIN, _CONTOUR_MAX = -24, 24  # raw semitone intervals; wider than any
# realistic leap so chance matches stay rare (clamped small intervals made
# unrelated random contours align by accident)


def contour_signature(piece: Piece, grid_tpb: int = 4) -> tuple[int, ...]:
    """Melody = highest pitch per grid frame (0 = rest), then per-step
    interval clamped to [-3,3]; returned as a tuple for edit-distance."""
    frames = _roll_frames(piece.events, piece.ticks_per_beat, grid_tpb)
    mel: list[int] = []
    for fr in frames:
        mel.append(max(fr) if fr else 0)
    out: list[int] = []
    last_pitch = 0
    for m in mel:
        if m == 0:
            if out and out[-1] != -100:  # compress rest runs: silence is not melody
                out.append(-100)
            continue
        if last_pitch == 0:
            out.append(0)  # piece-initial note has no reference
        else:
            d = m - last_pitch
            out.append(max(_CONTOUR_MIN, min(_CONTOUR_MAX, d)))
        last_pitch = m
    if not out:
        out.append(-100)
    return tuple(out)


def _smith_waterman(a: tuple[int, ...], b: tuple[int, ...],
                    match: int = 2, mismatch: int = -1, gap: int = -1,
                    band: int | None = None) -> int:
    """Local alignment score (Smith-Waterman) with optional band on |i-j|."""
    la, lb = len(a), len(b)
    if band is None:
        band = max(la, lb)
    prev = [0] * (lb + 1)
    best = 0
    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        lo, hi = max(1, i - band), min(lb, i + band)
        for j in range(lo, hi + 1):
            cur[j] = max(0, prev[j] + gap, cur[j - 1] + gap,
                         prev[j - 1] + (match if a[i - 1] == b[j - 1] else mismatch))
            if cur[j] > best:
                best = cur[j]
        prev = cur
    return best


def contour_score(q: tuple[int, ...], c: tuple[int, ...],
                  band: int | None = None) -> float:
    """Best local alignment normalized by query length: a copied span inside
    a long corpus piece scores ~1 regardless of piece length."""
    if not q or not c:
        return 0.0
    sw = _smith_waterman(q, c, band=band)
    return min(1.0, sw / (2 * len(q)))


# ---------------------------------------------------------------------------
# G2.1/G2.2  SIATEC / COSIATEC (point-set pattern discovery)
# ---------------------------------------------------------------------------

def _mtp_vectors(points: list[tuple[int, int]], max_vec: int | None = None):
    """All translation vectors d with |MTP(d)| >= 2, and the MTPs themselves.

    MTP(d) = {p in P : p + d in P}.  Returns dict d -> frozenset of points.
    """
    P = sorted(set(points))
    pset = set(P)
    out: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for i, a in enumerate(P):
        for b in P[i + 1:]:
            d = (b[0] - a[0], b[1] - a[1])
            if max_vec is not None and (abs(d[0]) > max_vec or abs(d[1]) > max_vec):
                continue
            if d not in out:
                out[d] = {p for p in P if (p[0] + d[0], p[1] + d[1]) in pset}
    return {d: frozenset(s) for d, s in out.items() if len(s) >= 2}


def _normal_form(pattern: frozenset[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    mx = min(p[0] for p in pattern)
    my = min(p[1] for p in pattern)
    return frozenset((x - mx, y - my) for x, y in pattern)


def siatec(points: list[tuple[int, int]], max_vec: int | None = None):
    """SIATEC: group maximal translational patterns into TECs.

    Returns list of TECs; each TEC = (pattern_normal_form, frozenset of
    translators).  This is the normal-form formulation, equivalent to the
    original for translational equivalence classes over MTPs.
    """
    mtps = _mtp_vectors(points, max_vec)
    tecs: dict[frozenset[tuple[int, int]], set[tuple[int, int]]] = {}
    for d, mtp in mtps.items():
        nf = _normal_form(mtp)
        anchor = min(mtp)
        tecs.setdefault(nf, set()).add((anchor[0], anchor[1]))
    return [(nf, frozenset(ts)) for nf, ts in tecs.items()]


def cosiatec(points: list[tuple[int, int]], max_vec: int | None = None,
             min_pattern: int = 3):
    """COSIATEC: greedy set cover by TECs, highest compression first.

    Returns ordered list of (pattern_nf, translators, covered_points).
    """
    remaining = set(points)
    cover = []
    while len(remaining) >= min_pattern:
        best = None
        best_gain = 0.0
        for nf, ts in siatec(list(remaining), max_vec):
            cov = set()
            for t in ts:
                cov |= {(x + t[0], y + t[1]) for x, y in nf}
            gain = len(cov) - len(nf)  # compression = covered - stored
            if gain > best_gain:
                best_gain = gain
                best = (nf, ts, cov)
        if best is None:
            break
        cover.append(best)
        remaining -= best[2]
    return cover


def siatec_signature(piece: Piece, grid_tpb: int = 4, max_vec: int | None = 64):
    """Signature for comparison: set of pattern normal forms (weighted by
    translator count).  Two pieces sharing a copied passage share patterns."""
    grid = max(1, piece.ticks_per_beat // grid_tpb)
    points = [(e.onset_tick // grid, e.pitch) for e in piece.events]
    tecs = siatec(points, max_vec)
    sig: dict[frozenset[tuple[int, int]], int] = {}
    for nf, ts in tecs:
        if len(nf) >= 3:
            sig[nf] = len(ts)
    return sig


def siatec_score(q: dict, c: dict) -> float:
    """Weighted Jaccard over shared pattern normal forms."""
    if not q or not c:
        return 0.0
    shared = sum(min(w, c[k]) for k, w in q.items() if k in c)
    total = sum(q.values()) + sum(c.values())
    return 2 * shared / total if total else 0.0


# ---------------------------------------------------------------------------
# unified detect
# ---------------------------------------------------------------------------

_METHODS = {
    "ngram": (ngram_signature, ngram_score),
    "contour": (contour_signature, contour_score),
    "siatec": (siatec_signature, siatec_score),
}


def detect(query: Piece, corpus: Piece, method: str,
           threshold: float = 0.5, **sig_kwargs) -> Hit | None:
    sig_fn, score_fn = _METHODS[method]
    qs = sig_fn(query, **sig_kwargs)
    cs = sig_fn(corpus, **sig_kwargs)
    s = score_fn(qs, cs)
    if s >= threshold:
        return Hit(query.pid, corpus.pid, s, method,
                   {"q_sig_size": len(qs), "c_sig_size": len(cs)})
    return None


def score_pair(query: Piece, corpus: Piece, method: str, **sig_kwargs) -> float:
    sig_fn, score_fn = _METHODS[method]
    return score_fn(sig_fn(query, **sig_kwargs), sig_fn(corpus, **sig_kwargs))
