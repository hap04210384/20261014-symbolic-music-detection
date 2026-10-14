# -*- coding: utf-8 -*-
"""并行版 v2：Python 线程池 + curl 子进程。"""
import os, sys, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_engines import REPOS, RAW, ROOT

def fetch(job):
    url, target = job
    if os.path.exists(target) and os.path.getsize(target) > 0:
        return (target, True, "cached")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    r = subprocess.run(["curl", "-sSL", "--retry", "2", "--max-time", "120", "-o", target, url],
                       capture_output=True)
    ok = r.returncode == 0 and os.path.exists(target) and os.path.getsize(target) > 0
    return (target, ok, r.returncode if not ok else "ok")

def main():
    only_small = "--large" not in sys.argv
    jobs = []
    for repo, dest, paths in REPOS:
        base = os.path.join(ROOT, "src", dest)
        for p in paths:
            if only_small and any(p.endswith(ext) for ext in ("/accidents.txt","/pumsb.txt","/chainstore.txt","/kosarak.dat",".txt.gz","/T10I4D100K.txt","/connect.txt","/retail.txt")):
                continue
            target = os.path.join(base, p)
            jobs.append((RAW.format(repo=repo, path=p), target))
    todo = [j for j in jobs if not (os.path.exists(j[1]) and os.path.getsize(j[1]) > 0)]
    print("total:", len(jobs), "pending:", len(todo))
    okc = failc = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(fetch, j) for j in todo]
        for fut in as_completed(futs):
            target, ok, info = fut.result()
            if ok: okc += 1
            else:
                failc += 1
                print("FAIL", info, os.path.relpath(target, ROOT), flush=True)
    print(f"done ok={okc} fail={failc}")

if __name__ == "__main__":
    main()
