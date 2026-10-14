# -*- coding: utf-8 -*-
"""Resumable torrent download for the Lakh MIDI (LMD-full) community mirror.

Source: hyper.ai dataset page 9406 (Lakh MIDI v0.1, ~176k files, ~1.65 GB),
.torrent fetched from orion.hyper.ai/tracker/download?torrent=9409,
also announces to academictorrents.com.

No background tasks are available in this environment, so the downloader is
budgeted: run it repeatedly (each run continues where the last stopped):

    python tools/download_lmd.py --budget 250

Resume state lives in data/raw/lmd_resume/ (git-ignored).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import libtorrent as lt

ROOT = Path(__file__).resolve().parents[1]
TORRENT = ROOT / "data/raw/lmd9409.torrent"
DEST = ROOT / "data/raw/lmd"
RESUME_DIR = ROOT / "data/raw/lmd_resume"
RESUME_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=250, help="seconds per run")
    ap.add_argument("--limit", type=int, default=0, help="rate limit KB/s (0=unlimited)")
    args = ap.parse_args()

    ses = lt.session({
        "listen_interfaces": "0.0.0.0:6881",
        "enable_dht": True,
        "announce_to_all_trackers": True,
        "announce_to_all_tiers": True,
        "user_agent": "kimi-work-research",
    })
    if args.limit:
        ses.set_download_limit(args.limit * 1024)

    info = lt.torrent_info(str(TORRENT))
    fastresume = RESUME_DIR / "lmd.fastresume"
    params = {
        "ti": info,
        "save_path": str(DEST),
        "storage_mode": lt.storage_mode_t.storage_mode_sparse,
    }
    if fastresume.exists():
        params["resume_data"] = fastresume.read_bytes()
    h = ses.add_torrent(params)

    # Magnet (orion.hyper.ai/tracker/magnet?torrent=9409) carries extra trackers
    # the .torrent file may lack; add them all so any live swarm can find us.
    extra_trackers = [
        "https://academictorrents.com/announce.php?passkey=9e7acf0084240b3b09d4225139889952",
        "http://pubt.net:2710/announce",
        "http://tracker.tfile.me/announce",
        "udp://tracker.coppersurfer.tk:6969",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.publicbt.com:80/announce",
        "udp://tracker.openbittorrent.com:80/announce",
    ]
    for tr in extra_trackers:
        h.add_tracker({"url": tr})

    t0 = time.time()
    seen_trackers = set()
    last = 0.0
    done = False
    while time.time() - t0 < args.budget:
        s = h.status()
        if s.state == lt.torrent_status.seeding:
            done = True
            break
        if s.progress != last:
            print(f"[{time.time()-t0:6.1f}s] {s.progress*100:6.2f}% "
                  f"({s.total_done>>20} MiB) down {s.download_rate/1024:8.1f} KiB/s "
                  f"peers={s.num_peers} seeds={s.num_seeds} state={s.state}",
                  flush=True)
            last = s.progress
        # surface each tracker announce result exactly once, for diagnosis
        for a in ses.pop_alerts():
            if isinstance(a, (lt.tracker_reply_alert, lt.tracker_error_alert,
                              lt.announce_entry)):
                key = (type(a).__name__, getattr(a, "url", ""))
                if key not in seen_trackers:
                    seen_trackers.add(key)
                    msg = getattr(a, "message", lambda: str(a))()
                    print(f"  TRACKER {type(a).__name__}: {msg}", flush=True)
        time.sleep(5)

    s = h.status()
    print(f"END OF BUDGET: {s.progress*100:.2f}% ({s.total_done>>20} MiB), "
          f"peers={s.num_peers}, seeds={s.num_seeds}")

    # persist resume data
    h.save_resume_data()
    got = False
    for _ in range(50):
        a = ses.wait_for_alert(1000)
        if a is None:
            continue
        if isinstance(a, lt.save_resume_data_alert):
            (RESUME_DIR / "lmd.fastresume").write_bytes(lt.write_resume_data_buf(a.params))
            got = True
            break
    ses.pause()
    if not got:
        print("WARN: resume data not saved this run")
    return 0 if (done or s.progress >= 0.9999) else 2


if __name__ == "__main__":
    sys.exit(main())
