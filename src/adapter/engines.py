# -*- coding: utf-8 -*-
"""Subprocess wrappers around the four prebuilt engine executables.

Upstream repos are read-only. Exes are referenced in place (AnytimeMining.exe
is the sole exception: it is COPIED into the run directory because it has a
compile-time hardcoded relative input path, see docs/adapter_design.md §1).
Every run writes a manifest.json with sha256 of inputs and executable.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXE = {
    "tensorfim_bitmap": ROOT / "src/engine_tensorfim/code/engine/run/CoParaCG_baseline.exe",
    "tensorfim_bmma": ROOT / "src/engine_tensorfim/code/engine/run/CoParaCG_bmma.exe",
    # our MSBuild rebuilds (upstream recipe, see bin/anyfim/BUILD_MANIFEST.json):
    # the upstream PREBUILT exes are an older generation with a compile-time
    # hardcoded input and no argv support — usable only via the staged-dir
    # trick with unknown thresholds, hence replaced by these builds.
    "anyfim_gt": ROOT / "bin/anyfim/anyfim_gt.exe",
    "anyfim_anytime": ROOT / "bin/anyfim/anytime_mining.exe",
}
ANYTIME_UPTO_STAGE = 20  # compile-time constant of AnytimeMining.exe
ANYTIME_INPUT_NAME = "accidents.txt"  # compile-time hardcoded filename


class EngineError(RuntimeError):
    pass


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


LINE = re.compile(r"^\d+th:\s+(\d+)\s+\{\s*([^}]*)\}\s+support:\s+\S+\s+frequency:\s+(\d+)")
STAGE = re.compile(r"=+\s*(\d+)th stage MFIs Number:\s*(\d+)\s*=+")
PRE = re.compile(r"preprocessing_time\(s\):\s*([\d.eE+-]+)")
COMP = re.compile(r"computation_time\(s\):\s*([\d.eE+-]+)")
TOT = re.compile(r"total_time\(s\):\s*([\d.eE+-]+)")
RPS = re.compile(r"runtimePerStage\(s\):\s*([[\d.,eE+-]*\d)")


def parse_results(path: str | Path) -> dict:
    """Parse an engine Results.txt into MFIs (flat and per-stage) and timings."""
    mfis: list[tuple[frozenset, int]] = []
    by_stage: dict[int, list[tuple[frozenset, int]]] = {}
    stage = 0
    pre = comp = tot = None
    rps: list[float] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = STAGE.search(ln)
            if m:
                stage = int(m.group(1))
                continue
            m = LINE.match(ln.strip())
            if m:
                items = frozenset(int(x) for x in m.group(2).split())
                rec = (items, int(m.group(3)))
                mfis.append(rec)
                if stage:
                    by_stage.setdefault(stage, []).append(rec)
                continue
            m = PRE.search(ln)
            if m:
                pre = float(m.group(1))
                continue
            m = COMP.search(ln)
            if m:
                comp = float(m.group(1))
                continue
            m = TOT.search(ln)
            if m:
                tot = float(m.group(1))
                continue
            m = RPS.search(ln)
            if m:
                rps = [float(x) for x in m.group(1).split(",") if x.strip()]
    return {
        "mfis": mfis,
        "mfis_by_stage": by_stage,
        "preprocessing_time": pre,
        "computation_time": comp,
        "total_time": tot,
        "runtime_per_stage": rps,
        "n_mfis": len(mfis),
    }


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _write_manifest(workdir: Path, **kw) -> Path:
    kw["adapter_commit"] = _git_commit()
    kw["created"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    p = workdir / "manifest.json"
    p.write_text(json.dumps(kw, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def _spawn(cmd: list[str], cwd: Path, log_path: Path, timeout: int) -> None:
    with open(log_path, "wb") as lf:
        try:
            subprocess.run(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT,
                           timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise EngineError(f"engine timeout after {timeout}s: {cmd}") from e


def _require_result(result_path: Path, log_path: Path, cmd: list[str]) -> None:
    if not result_path.exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise EngineError(
            f"no result file {result_path}\ncmd: {cmd}\n--- stdout tail ---\n{tail}"
        )


def result_name(dataset: str | Path, support: float) -> str:
    """Engine writes '<dataset>-<support>=Results.txt' with %f (6 decimals)."""
    return f"{dataset}-{support:.6f}=Results.txt"


def run_tensorfim(engine: str, dataset: Path, support: float,
                  workdir: Path, timeout: int = 1800) -> dict:
    """engine in {'tensorfim_bitmap','tensorfim_bmma'}; argv: <dataset> <support>."""
    exe = EXE[engine]
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    result_path = Path(result_name(str(dataset), support))
    log = workdir / "stdout.log"
    t0 = time.time()
    _spawn([str(exe), str(dataset), str(support)], workdir, log, timeout)
    wall = time.time() - t0
    _require_result(result_path, log, [str(exe), str(dataset), str(support)])
    parsed = parse_results(result_path)
    manifest = _write_manifest(
        workdir, engine=engine, exe=str(exe), exe_sha256=sha256_file(exe),
        dataset=str(dataset), dataset_sha256=sha256_file(dataset),
        support=support, wall_time_secs=round(wall, 4),
        result_file=str(result_path), stdout_log=str(log),
    )
    parsed["manifest"] = str(manifest)
    return parsed


def run_anyfim_gt(dataset: Path, support: float, workdir: Path,
                  run_mode: int = 1, cpu_cores: int | None = None,
                  timeout: int = 1800) -> dict:
    """argv: <RUN_MODE> <CPU_CORES> <dataset> <support> (source-verified)."""
    exe = EXE["anyfim_gt"]
    cpu_cores = cpu_cores or (os.cpu_count() or 8)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    result_path = Path(result_name(str(dataset), support))
    cmd = [str(exe), str(run_mode), str(cpu_cores), str(dataset), str(support)]
    log = workdir / "stdout.log"
    t0 = time.time()
    _spawn(cmd, workdir, log, timeout)
    wall = time.time() - t0
    _require_result(result_path, log, cmd)
    parsed = parse_results(result_path)
    manifest = _write_manifest(
        workdir, engine="anyfim_gt", exe=str(exe), exe_sha256=sha256_file(exe),
        dataset=str(dataset), dataset_sha256=sha256_file(dataset),
        support=support, run_mode=run_mode, cpu_cores=cpu_cores,
        wall_time_secs=round(wall, 4),
        result_file=str(result_path), stdout_log=str(log),
    )
    parsed["manifest"] = str(manifest)
    return parsed


def run_anyfim_anytime(dataset: Path, workdir: Path,
                       timeout: int = 3600) -> dict:
    """AnytimeMining.exe has no argv: input is compile-time hardcoded to
    '..\\TransactionSets\\accidents.txt' with UptoStage=20. We stage a
    private copy of the exe plus our data under that exact filename."""
    exe = EXE["anyfim_anytime"]
    workdir = Path(workdir)
    bindir = workdir / "bin"
    tsdir = workdir / "TransactionSets"
    bindir.mkdir(parents=True, exist_ok=True)
    tsdir.mkdir(parents=True, exist_ok=True)
    staged_exe = bindir / exe.name
    if not staged_exe.exists() or sha256_file(staged_exe) != sha256_file(exe):
        shutil.copyfile(exe, staged_exe)
    staged_input = tsdir / ANYTIME_INPUT_NAME
    shutil.copyfile(dataset, staged_input)
    result_path = tsdir / f"{ANYTIME_INPUT_NAME}-{ANYTIME_UPTO_STAGE}-stages=Results.txt"
    if result_path.exists():
        result_path.unlink()
    log = workdir / "stdout.log"
    t0 = time.time()
    _spawn([str(staged_exe)], bindir, log, timeout)
    wall = time.time() - t0
    _require_result(result_path, log, [str(staged_exe)])
    parsed = parse_results(result_path)
    parsed["upto_stage"] = ANYTIME_UPTO_STAGE
    manifest = _write_manifest(
        workdir, engine="anyfim_anytime", exe=str(exe), exe_sha256=sha256_file(exe),
        staged_exe=str(staged_exe), dataset=str(dataset),
        dataset_sha256=sha256_file(dataset), upto_stage=ANYTIME_UPTO_STAGE,
        wall_time_secs=round(wall, 4),
        result_file=str(result_path), stdout_log=str(log),
    )
    parsed["manifest"] = str(manifest)
    return parsed
