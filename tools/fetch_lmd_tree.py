# -*- coding: utf-8 -*-
"""Persistently fetch the roszcz/lakh-lmd-full data/ shard list until success.

Writes data/raw/lmd_data_tree.json. Exit 0 = saved, 2 = give up this round.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hfget import fetch_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/lmd_data_tree.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=270.0)
    args = ap.parse_args()

    t0 = time.time()
    i = 0
    while time.time() - t0 < args.budget:
        i += 1
        try:
            d = fetch_json("https://hf-mirror.com/api/datasets/roszcz/lakh-lmd-full/tree/main/data")
            total = sum((f.get("size") or 0) for f in d)
            OUT.write_text(json.dumps(d, indent=1), encoding="utf-8")
            print(f"[{time.time()-t0:6.1f}s] {len(d)} shards, {total/1e9:.2f} GB total", flush=True)
            for f in d[:100]:
                print(f"  {f['path']:45s} {(f.get('size') or 0)/1e6:10.1f} MB", flush=True)
            return 0
        except Exception as e:
            print(f"[round {i}] {type(e).__name__}: {str(e)[:80]}", flush=True)
            time.sleep(3)
    return 2


if __name__ == "__main__":
    sys.exit(main())
