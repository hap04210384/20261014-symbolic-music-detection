# -*- coding: utf-8 -*-
"""G3.4 sanity check — four gates between us and G1.

Gate 1  TensorFIM smoke: mushrooms@0.3, both kernels, set-identity vs gold_results.
Gate 2  AnyFIM smoke: (a) GivenThreshold argv mode vs same gold;
        (b) Anytime staged run on accidents.txt vs upstream reference output
            (set-identity per stage).
Gate 3  Planted verbatim copies: recall must be 100% on bmma + anyfim_gt.
Gate 4  G3.5 dense-remap equivalence: >=20 random configs, raw ids vs
        sparse ids + adapter remap, MFI sets identical after unmapping.

Usage: python tools/g34_sanity.py [--gates 1,2,3,4] [--configs N] [--quick]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.adapter.fimi import (  # noqa: E402
    write_fimi, read_fimi, item_counts, dense_remap, save_mapping, load_mapping,
    survivor_threshold_gt,
)
from src.adapter.engines import (  # noqa: E402
    run_tensorfim, run_anyfim_gt, run_anyfim_anytime, parse_results,
)
from src.adapter.synth import random_txns, planted_copy_corpus, recall_verbatim  # noqa: E402

RUNS = ROOT / "runs" / "G3.4"
DATA_DIRS = [ROOT / "src/engine_tensorfim/data",
             ROOT / "src/engine_tensorfim/data/small"]
GOLD = ROOT / "src/engine_tensorfim/data/gold_results"
ANYFIM_TS = ROOT / "src/engine_anyfim/code/AnyFIM-Anytime/TransactionSets"


def find_data(name: str) -> Path | None:
    for base in DATA_DIRS:
        p = base / name
        if p.exists():
            return p
    return None


def mfi_map(parsed: dict) -> dict[frozenset, int]:
    return {s: f for s, f in parsed["mfis"]}


def mfi_map_unmapped(parsed: dict, orig_of_dense) -> dict[frozenset, int]:
    return {frozenset(orig_of_dense[i] for i in s): f for s, f in parsed["mfis"]}


def diff_summary(a: dict, b: dict, label: str) -> list[str]:
    probs = []
    only_a = set(a) - set(b)
    only_b = set(b) - set(a)
    freq_mismatch = {s for s in set(a) & set(b) if a[s] != b[s]}
    if only_a or only_b or freq_mismatch:
        probs.append(f"{label}: only_left={len(only_a)} only_right={len(only_b)} "
                     f"freq_mismatch={len(freq_mismatch)}")
        for s in list(only_a)[:3]:
            probs.append(f"  only_left  {sorted(s)[:12]} freq={a[s]}")
        for s in list(only_b)[:3]:
            probs.append(f"  only_right {sorted(s)[:12]} freq={b[s]}")
        for s in list(freq_mismatch)[:3]:
            probs.append(f"  freq_diff  {sorted(s)[:12]} {a[s]} vs {b[s]}")
    return probs


def gate1(problems: list[str]) -> None:
    print("== Gate 1: TensorFIM smoke (mushrooms @ 0.3, gold set-identity)")
    src = find_data("mushrooms.txt")
    assert src, "mushrooms.txt not found in engine data dirs"
    gold = parse_results(GOLD / "mushrooms.txt-0.300000=Results.txt")
    gold_map = mfi_map(gold)
    work = RUNS / "gate1"
    work.mkdir(parents=True, exist_ok=True)
    local = work / "mushrooms.txt"
    shutil.copyfile(src, local)
    for eng in ("tensorfim_bitmap", "tensorfim_bmma"):
        r = run_tensorfim(eng, local, 0.3, work / eng)
        problems += diff_summary(gold_map, mfi_map(r), f"gate1 {eng} vs gold")
        print(f"   {eng}: {r['n_mfis']} MFIs, total_time={r['total_time']}s")


def gate2(problems: list[str]) -> None:
    print("== Gate 2: AnyFIM smoke")
    work = RUNS / "gate2"
    work.mkdir(parents=True, exist_ok=True)
    # (a) GivenThreshold argv mode
    src = find_data("mushrooms.txt")
    gold = parse_results(GOLD / "mushrooms.txt-0.300000=Results.txt")
    local = work / "mushrooms.txt"
    shutil.copyfile(src, local)
    try:
        r = run_anyfim_gt(local, 0.3, work / "gt_argv")
        problems += diff_summary(mfi_map(gold), mfi_map(r), "gate2a anyfim_gt(argv) vs gold")
        print(f"   gt argv mode: {r['n_mfis']} MFIs, total_time={r['total_time']}s")
    except Exception as e:  # noqa: BLE001
        problems.append(f"gate2a anyfim_gt argv mode failed: {e}")
    # (b) Anytime staged run on accidents vs upstream reference output
    acc = ANYFIM_TS / "accidents.txt"
    ref = ANYFIM_TS / "accidents.txt-20-stages=Results.txt"
    if acc.exists() and ref.exists():
        ref_parsed = parse_results(ref)
        r = run_anyfim_anytime(acc, work / "anytime_accidents", timeout=3600)
        # compare per-stage union (stages descend in threshold; union = stage-20 cutoff)
        for stage, items in sorted(ref_parsed["mfis_by_stage"].items()):
            got = {s: f for s, f in r["mfis_by_stage"].get(stage, [])}
            want = {s: f for s, f in items}
            problems += diff_summary(want, got, f"gate2b stage{stage}")
        print(f"   anytime accidents: {r['n_mfis']} MFIs over "
              f"{len(r['mfis_by_stage'])} stages, wall={r['total_time']}s(pre) "
              f"stages={len(r['runtime_per_stage'])}")
    else:
        problems.append("gate2b: accidents.txt or reference output missing")


def gate3(problems: list[str], seed: int = 0) -> None:
    print("== Gate 3: planted verbatim copies, recall must be 100%")
    txns, meta = planted_copy_corpus(n_corpus=50, n_items=500, span_len=12,
                                     n_planted=10, seed=seed)
    n = len(txns)
    support = 2.0 / n - 1e-9  # avoid float edge: n*(2/n) may be 1.9999...; keep freq-2 alive
    work = RUNS / "gate3"
    work.mkdir(parents=True, exist_ok=True)
    for eng in ("tensorfim_bmma", "anyfim_gt"):
        # per-engine input copy: both engines would otherwise write the same
        # '<dataset>-<support>=Results.txt' next to the input and clobber it
        fimi = work / f"planted_{eng}.fimi"
        write_fimi(fimi, txns)
        if eng == "tensorfim_bmma":
            r = run_tensorfim(eng, fimi, support, work / eng)
        else:
            r = run_anyfim_gt(fimi, support, work / eng)
        rec, per_item = recall_verbatim(r["mfis"], meta)
        print(f"   {eng}: recall={rec:.3f} ({sum(p['found'] for p in per_item)}/{len(per_item)})")
        if rec < 1.0:
            problems.append(f"gate3 {eng}: recall {rec:.3f} < 1.0")


def gate4(problems: list[str], n_configs: int = 20, start: int = 0) -> None:
    print(f"== Gate 4: G3.5 dense-remap equivalence ({n_configs} random configs)")
    work = RUNS / "gate4"
    work.mkdir(parents=True, exist_ok=True)
    for cfg in range(start, start + n_configs):
        seed = 1000 + cfg
        n_trans = 120 + (seed % 5) * 20
        n_items = 600 + (seed % 7) * 100
        support = [0.02, 0.025, 0.03][seed % 3]
        txns = random_txns(n_trans, n_items, seed=seed)
        # raw (native dense ids)
        fimi_raw = work / f"cfg{seed}_raw.fimi"
        write_fimi(fimi_raw, txns)
        # sparse: shift ids into a large sparse space, ORDER-PRESERVING
        # (a non-monotonic scatter would break the raw<->dense equivalence
        # check, since the remap must preserve the original id order)
        offset = 1_000_000 + (seed % 97) * 10_000
        sparse = [{x + offset for x in t} for t in txns]
        fimi_sparse = work / f"cfg{seed}_sparse.fimi"
        write_fimi(fimi_sparse, sparse)
        cutoff = survivor_threshold_gt(item_counts(txns), n_trans, support)
        remapped, orig_of_dense = dense_remap(sparse, cutoff)
        mapping_path = work / f"cfg{seed}_mapping.json"
        save_mapping(mapping_path, orig_of_dense)
        assert load_mapping(mapping_path) == orig_of_dense
        fimi_dense = work / f"cfg{seed}_dense.fimi"
        write_fimi(fimi_dense, remapped)
        for eng, runner in (("tensorfim_bmma", lambda p, w: run_tensorfim("tensorfim_bmma", p, support, w)),
                            ("anyfim_gt", lambda p, w: run_anyfim_gt(p, support, w))):
            r_raw = runner(fimi_raw, work / f"cfg{seed}_{eng}_raw")
            r_dense = runner(fimi_dense, work / f"cfg{seed}_{eng}_dense")
            # unify id spaces before comparing: dense unmaps to the SPARSE
            # id space (its input lineage), sparse = raw + offset
            got = {frozenset(orig_of_dense[i] - offset for i in s): f
                   for s, f in r_dense["mfis"]}
            problems += diff_summary(mfi_map(r_raw), got, f"gate4 cfg{seed} {eng}")
        if (cfg + 1) % 5 == 0:
            print(f"   {cfg + 1}/{n_configs} configs done")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gates", default="1,2,3,4")
    ap.add_argument("--configs", type=int, default=20)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    gates = {int(g) for g in args.gates.split(",")}
    problems: list[str] = []
    if 1 in gates:
        gate1(problems)
    if 2 in gates:
        gate2(problems)
    if 3 in gates:
        gate3(problems, seed=args.seed)
    if 4 in gates:
        gate4(problems, n_configs=args.configs, start=args.start)
    print("=" * 60)
    if problems:
        print(f"FAIL — {len(problems)} problem(s):")
        for p in problems:
            print("  *", p)
        return 1
    print("ALL GATES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
