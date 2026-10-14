# -*- coding: utf-8 -*-
"""E4 feasibility probe: full detection protocol at small scale (N=1000).

Protocol (docs/adapter_design.md): corpus = N real Lakh pieces (one
transaction each); query = one extra transaction sharing a verbatim span with
corpus piece #k; G3.5 dense remap at cutoff=2; mine corpus+query with
support = 2/(N+1) so any shared item must surface (freq >= 2 <=> shared);
hit = MFI that is a subset of the query's items.

Measures: wall time, MFI count, peak memory, recall. If MFI explosion makes
cutoff-2 mining infeasible even at N=1000, the headline claim needs
rethinking NOW, before the full download finishes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.fimi import read_fimi, dense_remap, save_mapping  # noqa: E402
from adapter.engines import run_tensorfim  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "data/processed/lmd/10k.txt"))
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--engine", default="tensorfim_bitmap",
                    choices=["tensorfim_bitmap", "tensorfim_bmma"])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    import random
    rng = random.Random(args.seed)
    txns = read_fimi(args.corpus)[: args.n]

    # plant: query = 60% item-span of corpus piece #k, verbatim
    k = rng.randrange(len(txns))
    donor = sorted(txns[k])
    span = set(donor[: max(10, int(0.6 * len(donor)))])
    filler = set(rng.sample(range(1, 262145), 200))
    query = span | (filler - span)
    db = txns + [query]
    n = len(db)
    support = 2.0 / n

    t0 = time.time()
    remapped, orig_of_dense = dense_remap(db, cutoff=2.0)
    remap_t = time.time() - t0
    kept = sum(1 for t in remapped if t)
    print(f"N={n} (incl. query), remap cutoff=2: "
          f"{kept} non-empty txns, dense vocab={len(orig_of_dense)-1}, "
          f"{remap_t:.1f}s", flush=True)

    work = ROOT / "runs/e4_probe"
    work.mkdir(parents=True, exist_ok=True)
    local = work / "probe.txt"
    with open(local, "w", encoding="utf-8") as f:
        for t in remapped:
            f.write(" ".join(str(x) for x in sorted(t)))
            f.write("\n")
    save_mapping(work / "mapping.json", orig_of_dense)

    import subprocess
    r = run_tensorfim(args.engine, local, support, work / args.engine,
                      timeout=1200)
    q_items = remapped[-1]
    hits = [sorted(s) for s, freq in r["mfis"] if set(s) <= q_items and freq >= 2]
    print(f"engine={args.engine} support={support:.6f}")
    print(f"  wall={r['manifest'] and json.load(open(r['manifest']))['wall_time_secs']}s "
          f"pre={r['preprocessing_time']}s comp={r['computation_time']}s")
    print(f"  total MFIs={r['n_mfis']}, MFIs subset-of-query={len(hits)}")
    if hits:
        best = max(hits, key=len)
        print(f"  best hit size={len(best)} (planted span dense size={len(span & set()) or 'n/a'})")
    # ground truth: planted span survived remap?
    span_dense = {x for x in remapped[-1] if orig_of_dense[x] in span}
    print(f"  planted span in query after remap: {len(span_dense)} items")
    hit_union = set().union(*hits) if hits else set()
    print(f"  planted span covered by hit union: "
          f"{len(span_dense & hit_union)}/{len(span_dense)}")
    print(f"  VERDICT: {'PASS' if hits else 'FAIL'} (hit found)")
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
