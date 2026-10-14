# -*- coding: utf-8 -*-
"""G1.2/G1.3: LMD-full parquet shards -> per-piece FIMI transactions.

Source: roszcz/lakh-lmd-full (HF mirror of Lakh MIDI v0.1, 174,300 pieces,
55 parquet shards). Schema per row: notes = struct of parallel arrays
(duration[], end[], pitch[], start[], velocity[]) + source (lakh midi path).

Timing: LMD-full rows carry seconds, not ticks. We set file_tpb = 1000 and
treat 1 tick = 1 ms; EncodingConfig then quantizes onto a 125 ms grid
(tpb=8). Channel is absent from the schema -> use_channel=False.

Outputs under data/processed/lmd/:
  <tier>.txt          FIMI file, one transaction per piece (original ids)
  <tier>.pieces.json  ordered list of {idx, source}
  <tier>.meta.json    config, sha256, counts
Tiers: fixed-seed samples of 10k / 100k / full.

Usage:
  python tools/build_corpus.py --shards data/raw/lmd_parquet \
      --out data/processed/lmd --tiers 10000 100000 0 --seed 42 [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from adapter.midi_encode import EncodingConfig, Event, events_to_items  # noqa: E402
from adapter.engines import sha256_file  # noqa: E402

import duckdb  # noqa: E402
import numpy as np  # noqa: E402


def row_to_items(starts, ends, pitches, vels, cfg: EncodingConfig) -> set[int]:
    """numpy arrays per piece -> item set. 1 tick = 1 ms, file_tpb = 1000.

    Vectorized; bit-identical to adapter.midi_encode.events_to_items for
    (use_channel=False, file_tpb=1000) — verified by tools/test_encoding.py
    equivalence gate."""
    if starts is None or len(starts) == 0:
        return set()
    s_raw = np.asarray(starts, dtype=np.float64)
    # duration rounds the raw (end-start) delta — NOT round(end)-round(start);
    # the two differ by ±1 ms at half-ms boundaries (2026-10-12 equivalence test)
    dur = np.rint((np.asarray(ends, dtype=np.float64) - s_raw) * 1000).astype(np.int64)
    s_ms = np.rint(s_raw * 1000).astype(np.int64)
    p = np.asarray(pitches, dtype=np.int64)
    v = np.asarray(vels, dtype=np.int64)
    order = np.lexsort((p, s_ms))          # (onset_tick, pitch) ascending
    s_ms = s_ms[order]
    dur = np.maximum(dur[order], 1)
    ioi = np.empty_like(s_ms)
    ioi[:-1] = np.diff(s_ms)               # onset gaps of rounded ms (engine path)
    ioi[-1] = 0
    ioi = np.maximum(ioi, 0)
    grid = max(1, 1000 // cfg.tpb)

    def q(x):  # _bin semantics: round-half-up to grid, overflow -> last bin
        return np.minimum((x + grid // 2) // grid, cfg.dur_bins - 1)

    d = q(dur)
    g = q(ioi)
    if cfg.vel_bins < 128:
        vv = np.minimum(v[order] >> (7 - (cfg.vel_bins - 1).bit_length()),
                        cfg.vel_bins - 1)
    else:
        vv = v[order]
    code = ((((p[order] * cfg.dur_bins + d) * cfg.ioi_bins + g)
             * cfg.vel_bins + vv) * 1 + 0) + 1
    return set(code.tolist())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", default="data/raw/lmd_parquet")
    ap.add_argument("--out", default="data/processed/lmd")
    ap.add_argument("--tiers", type=int, nargs="+", default=[10000, 100000, 0])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="debug: cap pieces")
    ap.add_argument("--cache", default="data/processed/lmd/cache",
                    help="per-shard encoded cache (resume across runs)")
    ap.add_argument("--allow-partial", action="store_true",
                    help="write tiers from whatever shards are cached now")
    ap.add_argument("--tpb", type=int, default=8)
    ap.add_argument("--dur-bins", type=int, default=16)
    ap.add_argument("--ioi-bins", type=int, default=16)
    ap.add_argument("--vel-bins", type=int, default=8)
    args = ap.parse_args()

    shards = sorted(Path(args.shards).glob("*.parquet"))
    if not shards:
        print(f"no parquet shards in {args.shards}")
        return 2
    cfg = EncodingConfig(tpb=args.tpb, dur_bins=args.dur_bins,
                         ioi_bins=args.ioi_bins, vel_bins=args.vel_bins,
                         use_channel=False)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    all_items: list[set[int]] = []
    all_src: list[str] = []
    t0 = time.time()
    CHUNK = 500
    for si, sh in enumerate(shards):
        cp = cache / (sh.stem + ".pkl")
        if cp.exists():
            items_c, src_c = pickle.loads(cp.read_bytes())
            all_items.extend(items_c)
            all_src.extend(src_c)
            print(f"[{time.time()-t0:6.1f}s] shard {si}: cached {len(items_c)} pieces",
                  flush=True)
            continue
        items_c, src_c = [], []
        n_done = 0
        while True:
            df = con.execute(
                f"SELECT source, notes.start AS s, notes.\"end\" AS e, "
                f"notes.pitch AS p, notes.velocity AS v "
                f"FROM read_parquet('{str(sh).replace(chr(39), chr(39)*2)}') "
                f"LIMIT {CHUNK} OFFSET {n_done}"
            ).df()
            if len(df) == 0:
                break
            for _, row in df.iterrows():
                src = row["source"]
                items_c.append(row_to_items(row["s"], row["e"], row["p"],
                                            row["v"], cfg))
                src_c.append(src["filenames"][0] if isinstance(src, dict)
                             else str(src))
            n_done += len(df)
            if args.limit and (len(all_items) + len(items_c)) >= args.limit:
                break
        cp.write_bytes(pickle.dumps((items_c, src_c)))
        all_items.extend(items_c)
        all_src.extend(src_c)
        print(f"[{time.time()-t0:6.1f}s] shard {si}: encoded {len(items_c)} pieces "
              f"(cumulative {len(all_items)})", flush=True)
        if args.limit and len(all_items) >= args.limit:
            break
    all_cached = all((cache / (sh.stem + ".pkl")).exists() for sh in shards)
    if not all_cached and not args.allow_partial and not args.limit:
        print("partial shards only; re-run with --allow-partial to assemble tiers")
        return 2
    if args.limit:
        all_items = all_items[:args.limit]
        all_src = all_src[:args.limit]
    n = len(all_items)
    print(f"encoded {n} pieces in {time.time()-t0:.0f}s", flush=True)

    rng = random.Random(args.seed)
    for tier in args.tiers:
        size = n if tier == 0 else min(tier, n)
        idx = sorted(rng.sample(range(n), size)) if size < n else list(range(n))
        name = "full" if tier == 0 else f"{tier//1000}k"
        fimi = out / f"{name}.txt"
        with open(fimi, "w", encoding="utf-8") as f:
            for i in idx:
                f.write(" ".join(str(x) for x in sorted(all_items[i])))
                f.write("\n")
        pieces = out / f"{name}.pieces.json"
        pieces.write_text(json.dumps(
            [{"idx": i, "source": all_src[i]} for i in idx], indent=0))
        meta = {
            "dataset": "roszcz/lakh-lmd-full (Lakh MIDI v0.1)",
            "encoding": cfg.param_hash(),
            "seed": args.seed,
            "n_pieces": size,
            "shards_available": sum(1 for sh in shards
                                    if (cache / (sh.stem + ".pkl")).exists()),
            "shards_total": len(shards),
            "partial": not all_cached,
            "sha256_fimi": sha256_file(fimi),
            "sha256_pieces": sha256_file(pieces),
        }
        (out / f"{name}.meta.json").write_text(json.dumps(meta, indent=2))
        print(f"tier {name}: {size} pieces -> {fimi}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
