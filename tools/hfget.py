# -*- coding: utf-8 -*-
"""Robust HTTP fetch for the flaky hf-mirror.com route.

TCP connect to hf-mirror succeeds only ~30% of attempts within 10 s, so every
request is retried in a loop until it succeeds. Supports Range resume for
large files.

Usage:
    python tools/hfget.py tree <repo> [--recursive]     # print JSON tree
    python tools/hfget.py get <repo> <path> <out>       # resumable download
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://hf-mirror.com"
CONNECT_TO = 15      # per-attempt TCP+TLS timeout
MAX_TRIES = 40       # total attempts per logical request


def _open(url: str, timeout: int, headers: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": "kimi-work-research", **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_json(url: str):
    for i in range(MAX_TRIES):
        try:
            with _open(url, CONNECT_TO) as r:
                return json.load(r)
        except Exception as e:
            print(f"  [retry {i+1}/{MAX_TRIES}] {type(e).__name__}: {str(e)[:60]}", flush=True)
            time.sleep(min(2 + i, 8))
    raise RuntimeError(f"fetch_json gave up: {url}")


def download(repo: str, path: str, out: Path, budget: float = 1e9) -> int:
    """Resumable download; returns 0 when complete, 2 when budget expired."""
    url = f"{BASE}/datasets/{repo}/resolve/main/{urllib.parse.quote(path)}"
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(out.suffix + ".part")
    t0 = time.time()
    while time.time() - t0 < budget:
        have = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={have}-"}
        try:
            with _open(url, CONNECT_TO, headers) as r:
                if r.status in (301, 302, 307, 308):
                    raise RuntimeError(f"unexpected redirect: {r.status}")
                if r.status == 416:  # range not satisfiable -> already complete
                    part.rename(out)
                    print(f"COMPLETE {out} ({have} bytes)", flush=True)
                    return 0
                if r.status != 206 and have > 0:
                    print(f"  server ignored Range (status {r.status}), restarting file", flush=True)
                    have = 0
                    part.unlink(missing_ok=True)
                mode = "ab" if have else "wb"
                total = r.headers.get("Content-Range", "").split("/")[-1]
                with open(part, mode) as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        if time.time() - t0 > budget:
                            print("  budget expired mid-stream", flush=True)
                            return 2
                if total and total.isdigit() and int(total) == (part.stat().st_size):
                    part.rename(out)
                    print(f"COMPLETE {out} ({total} bytes)", flush=True)
                    return 0
                # fall through: size mismatch -> loop will resume from part size
                print(f"  stream ended at {part.stat().st_size} bytes (total {total}), resuming", flush=True)
        except Exception as e:
            print(f"  [retry] {type(e).__name__}: {str(e)[:60]} (have {have})", flush=True)
            time.sleep(2)
    return 2


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_tree = sub.add_parser("tree")
    p_tree.add_argument("repo")
    p_tree.add_argument("--recursive", action="store_true")
    p_get = sub.add_parser("get")
    p_get.add_argument("repo")
    p_get.add_argument("path")
    p_get.add_argument("out")
    p_get.add_argument("--budget", type=float, default=1e9)
    args = ap.parse_args()

    if args.cmd == "tree":
        rec = "?recursive=true" if args.recursive else ""
        data = fetch_json(f"{BASE}/api/datasets/{args.repo}/tree/main{rec}")
        json.dump(data, sys.stdout, indent=1)
        print()
        return 0
    if args.cmd == "get":
        return download(args.repo, args.path, Path(args.out), args.budget)
    return 1


if __name__ == "__main__":
    sys.exit(main())
