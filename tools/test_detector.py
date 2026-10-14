# -*- coding: utf-8 -*-
"""Detector prototype acceptance: planted verbatim copies in the real
3000-piece Lakh corpus, rare-first anytime, recall + timing.

Plants: for P pieces, copy a 40-item span into a query with random filler
(the copied span is exactly what the guarantee covers).  Also measures the
anytime bound at intermediate stop points.
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from adapter.fimi import read_fimi
from adapter.detector import CorpusIndex


def main() -> int:
    txns = read_fimi(Path(__file__).resolve().parents[1] /
                     "data/processed/lmd/10k.txt")
    n_corpus = len(txns) - 0
    rng = random.Random(11)

    index = CorpusIndex(txns)
    print(f"corpus={n_corpus} pieces, vocab={len(index.postings)} items")

    # ---- planted queries --------------------------------------------
    n_plant, span_len = 20, 40
    t_all0 = time.time()
    ok = 0
    for p in range(n_plant):
        donor = rng.randrange(n_corpus)
        src = sorted(txns[donor])
        if len(src) < span_len + 10:
            continue
        start = rng.randrange(len(src) - span_len)
        span = set(src[start:start + span_len])
        query = span | set(rng.sample(range(1, 300000), 300)) - set()
        r = index.detect(query, min_evidence=span_len)
        hit = any(h.piece == donor for h in r.hits)
        ok += hit
        if p < 5:
            print(f"  plant {p}: donor={donor} hit={hit} "
                  f"hits={len(r.hits)} top_score={r.hits[0].score if r.hits else 0} "
                  f"wall={r.wall_secs*1000:.1f}ms")
    t_build = time.time() - t_all0
    print(f"planted recall: {ok}/{n_plant}, total {t_build:.2f}s")

    # ---- negative control -------------------------------------------
    neg_ok = 0
    for p in range(10):
        q = set(rng.sample(range(1, 300000), 340))
        r = index.detect(q, min_evidence=40)
        neg_ok += (len(r.hits) == 0)
    print(f"negative control (no hits): {neg_ok}/10")

    # ---- anytime profile ---------------------------------------------
    donor = 0
    src = sorted(txns[donor])[40:120]
    query = set(src) | set(rng.sample(range(1, 300000), 300))
    order = sorted([x for x in query if x in index.postings],
                   key=lambda x: (len(index.postings[x]), x))
    for frac in (0.05, 0.1, 0.25, 0.5, 1.0):
        k = max(1, int(len(order) * frac))
        r = index.detect(query, min_evidence=40, max_items=k)
        found = any(h.piece == donor for h in r.hits)
        print(f"  anytime {frac:4.0%}: items={k:4d} donor_found={found} "
              f"hits={len(r.hits)} remaining_bound={r.n_candidates_remaining} "
              f"wall={r.wall_secs*1000:.1f}ms")
    return 0 if ok == n_plant and neg_ok == 10 else 1


if __name__ == "__main__":
    sys.exit(main())
