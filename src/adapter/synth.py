# -*- coding: utf-8 -*-
"""Seeded synthetic transaction-set generators for sanity checks and
planted-copy experiments (transaction level; MIDI-level generators come with
the G1 data pipeline)."""
from __future__ import annotations

import random


def random_txns(n_trans: int, n_items: int, min_len: int = 5, max_len: int = 30,
                seed: int = 0) -> list[set[int]]:
    """Uniform random transactions over ids 1..n_items (id 0 is reserved)."""
    rng = random.Random(seed)
    out = []
    for _ in range(n_trans):
        k = rng.randint(min_len, max_len)
        out.append(set(rng.sample(range(1, n_items + 1), min(k, n_items))))
    return out


def planted_copy_corpus(n_corpus: int = 50, n_items: int = 500,
                        span_len: int = 12, n_planted: int = 10,
                        extra_per_txn: int = 10, seed: int = 0):
    """Corpus of `n_corpus` tunes plus `n_planted` queries, each query sharing a
    verbatim `span_len`-item span with exactly one distinct corpus tune.

    Returns (txns, meta) where txns = corpus tunes followed by queries and
    meta = list of dicts {query_idx, corpus_idx, span} for recall checks.
    """
    rng = random.Random(seed)
    corpus = [set(rng.sample(range(1, n_items + 1), rng.randint(15, 40)))
              for _ in range(n_corpus)]
    queries: list[set[int]] = []
    meta = []
    donor_order = rng.sample(range(n_corpus), n_planted)
    for q, c_idx in enumerate(donor_order):
        donor = corpus[c_idx]
        pool = list(donor)
        k = min(span_len, len(pool))
        span = set(rng.sample(pool, k))
        q_txn = set(span)
        while len(q_txn) < k + extra_per_txn:
            q_txn.add(rng.randrange(1, n_items + 1))
        queries.append(q_txn)
        meta.append({"query_idx": n_corpus + q, "corpus_idx": c_idx, "span": span})
    return corpus + queries, meta


def recall_verbatim(parsed_mfis, meta) -> tuple[float, list[dict]]:
    """Fraction of planted spans covered by some MFI (span ⊆ MFI ⊆ its pair).

    Every frequent itemset is a subset of some MFI, and a superset of a span
    can only occur in transactions containing that span — hence MFI ⊆ q ∩ c,
    which is exactly the 'verified hit' we count.
    """
    mfis = [frozenset(s) for s, _ in parsed_mfis]
    per_item = []
    hits = 0
    for m in meta:
        ok = any(m["span"] <= s for s in mfis)
        hits += ok
        per_item.append({**{k: v for k, v in m.items() if k != "span"},
                         "found": ok, "span_size": len(m["span"])})
    return hits / max(1, len(meta)), per_item
