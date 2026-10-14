# -*- coding: utf-8 -*-
"""FIMI transaction-set IO, statistics, and the G3.5 dense item-ID remapping.

Engine semantics mirrored here (verified against kernel sources 2026-10-11):
  * a transaction is a SET of items (bitmap support counts presence per row);
  * GivenThreshold/TensorFIM survivor rule: freq(x) >= transNum * supportThreshold
    (real comparison, engine compares int freq >= double threshold);
  * AnyFIM-Anytime survivor rule: freq(x) >= freq value at descending-rank
    index UptoStage (0-based), rank order = frequency desc, ties by item id asc
    (C++ stable_sort over ascending-id iteration).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def read_fimi(path: str | Path) -> list[set[int]]:
    """Read a FIMI file: one transaction per line, space-separated item ids."""
    txns: list[set[int]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                txns.append({int(x) for x in line.split()})
            except ValueError as e:
                raise ValueError(f"{path}:{ln}: bad item id in {line[:60]!r}") from e
    return txns


def write_fimi(path: str | Path, txns: list[set[int]]) -> None:
    """Write transactions in deterministic form: ids ascending, one line each.

    Item id 0 is RESERVED: both engines silently mishandle it (AnyFIM drops
    it entirely; TensorFIM emits non-maximal pairs containing it — verified
    2026-10-11, runs/G3.4/debug_item0). The adapter never emits 0.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for t in txns:
            if any(x <= 0 for x in t):
                raise ValueError("item id 0 (and negatives) are reserved; "
                                 "use ids >= 1 (see docs/adapter_design.md)")
            f.write(" ".join(str(x) for x in sorted(t)))
            f.write("\n")


def item_counts(txns: list[set[int]]) -> Counter:
    """Presence-based item frequencies (identical to engine bitmap semantics)."""
    c: Counter = Counter()
    for t in txns:
        c.update(t)
    return c


def _ranked_items(counts: Counter) -> list[tuple[int, int]]:
    """(-freq, id) ascending == frequency desc, ties by id asc (engine order)."""
    return sorted((( -c, i) for i, c in counts.items()))


def survivor_threshold_gt(counts: Counter, n_trans: int, support: float) -> float:
    """GivenThreshold/TensorFIM survivor cutoff = transNum * support (double)."""
    return n_trans * support


def survivor_threshold_anytime(counts: Counter, upto_stage: int) -> int:
    """AnyFIM-Anytime survivor cutoff = freq at descending-rank index upto_stage."""
    ranked = _ranked_items(counts)
    if upto_stage >= len(ranked):
        raise ValueError(
            f"UptoStage {upto_stage} >= distinct items {len(ranked)} "
            "(engine would abort: 'Up to the stage number being greater than the dimension')"
        )
    return -ranked[upto_stage][0]


def survivors(counts: Counter, cutoff: float) -> set[int]:
    return {i for i, c in counts.items() if c >= cutoff}


def dense_remap(txns: list[set[int]], cutoff: float):
    """G3.5: drop sub-cutoff items and renumber survivors densely.

    Dense ids follow the engine's activation order (frequency desc, ties by id
    asc), so traversal behaviour stays close to the engine's native order.
    Behavioural equivalence of the RESULT SET is enforced by tools/g34_sanity.py
    gate 4 (set-identity against the un-remapped run).

    Returns (remapped_txns, orig_of_dense) where orig_of_dense[dense] = orig id.
    """
    counts = item_counts(txns)
    keep = survivors(counts, cutoff)
    # dense ids MUST be order-preserving w.r.t. the original ids (rank by
    # original id ascending). Rationale (engine semantics, verified
    # 2026-10-11 via gate4): the engines extend itemsets only with items of
    # SMALLER id than the current root (little-endian), and roots are the
    # strictly-frequent items; therefore the emitted MFI set depends on the
    # id ORDER. An order-preserving renumbering keeps the engine's logical
    # exploration bit-identical — frequency-ordered renumbering does NOT
    # (it flips which element of a set is id-maximal and can silently drop
    # boundary MFIs). id 0 stays reserved.
    orig_of_dense = [None] + sorted(keep)
    dense_of_orig = {o: d for d, o in enumerate(orig_of_dense) if o is not None}
    # NOTE: empty transactions are KEPT (the engine counts every line towards
    # transNum, and transNum anchors frequencyThreshold = transNum*support;
    # dropping them would silently shift the support base — gate4-found bug)
    remapped = [{dense_of_orig[x] for x in t if x in keep} for t in txns]
    return remapped, orig_of_dense


def save_mapping(path: str | Path, orig_of_dense: list[int]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"orig_of_dense": orig_of_dense}, f)


def load_mapping(path: str | Path) -> list[int]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["orig_of_dense"]
