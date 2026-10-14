# -*- coding: utf-8 -*-
"""Sequentially download all 55 LMD-full parquet shards with resume.

Each shard streams to data/raw/lmd_parquet/<name>.part and is renamed on
completion after size verification against lmd_data_tree.json. The route to
hf-mirror is intermittent, so run this repeatedly:

    python tools/download_all_shards.py --budget 250    # exit 2 = more to do

Exit 0 = all shards complete and verified.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / "data/raw/lmd_data_tree.json"
DEST = ROOT / "data/raw/lmd_parquet"
DEST.mkdir(parents=True, exist_ok=True)

BASE = "https://hf-mirror.com"
REPO = "roszcz/lakh-lmd-full"
CONNECT_TO = 15


def _open(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": "kimi-work-research", **(headers or {})})
    return urllib.request.urlopen(req, timeout=CONNECT_TO)


def fetch_shard(path: str, expected: int, part: Path, deadline: float) -> bool:
    url = f"{BASE}/datasets/{REPO}/resolve/main/{urllib.parse.quote(path)}"
    while time.time() < deadline:
        have = part.stat().st_size if part.exists() else 0
        if have >= expected:
            part.rename(part.with_suffix(""))  # strip .part
            return True
        try:
            with _open(url, {"Range": f"bytes={have}-"}) as r:
                if r.status == 416:
                    if part.exists():
                        part.unlink()
                    have = 0
                    continue
                if have and r.status != 206:
                    part.unlink(missing_ok=True)
                    have = 0
                mode = "ab" if have else "wb"
                got = have
                with open(part, mode) as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if time.time() > deadline:
                            print(f"    budget hit at {got/1e6:.1f}/{expected/1e6:.1f} MB", flush=True)
                            return False
                if got >= expected:
                    part.rename(part.with_suffix(""))
                    return True
        except Exception as e:
            print(f"    [retry] {type(e).__name__} (have {have/1e6:.1f} MB)", flush=True)
            time.sleep(2)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=250.0)
    args = ap.parse_args()

    tree = json.loads(TREE.read_text(encoding="utf-8"))
    shards = [(f["path"], f["size"]) for f in tree if f["type"] == "file"]
    shards.sort()

    done = sum(1 for _, sz in shards if (DEST / Path(_).name).exists()
               and (DEST / Path(_).name).stat().st_size == sz)
    print(f"already complete: {done}/{len(shards)}", flush=True)

    deadline = time.time() + args.budget
    for path, sz in shards:
        name = Path(path).name
        final = DEST / name
        if final.exists() and final.stat().st_size == sz:
            continue
        part = final.with_suffix(final.suffix + ".part")
        t0 = time.time()
        ok = fetch_shard(path, sz, part, deadline)
        if not ok:
            print(f"STOP this round at {name} ({time.time()-t0:.0f}s spent)", flush=True)
            return 2
        print(f"OK {name} {sz/1e6:.1f} MB in {time.time()-t0:.0f}s", flush=True)
    print("ALL SHARDS COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
