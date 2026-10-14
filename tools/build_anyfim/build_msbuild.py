# -*- coding: utf-8 -*-
"""Rebuild AnyFIM exes via the upstream-proven route: MSBuild + CUDA 12.5
VS integration (the same recipe the prebuilt exes were built with).
Sources are copied project trees under tools/build_anyfim/; upstream repos
stay read-only. Outputs land in bin/anyfim/ with a build manifest."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MSBUILD = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe")
CUDA = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5")
OUT = ROOT / "bin/anyfim"
SLNS = {
    "anyfim_gt.exe": (ROOT / "tools/build_anyfim/vs_gt/CoParaCG.sln",
                      ROOT / "src/engine_anyfim/code/AnyFIM-GivenThreshold/CoParaCG/kernel.cu"),
    "anytime_mining.exe": (ROOT / "tools/build_anyfim/vs_at/AnytimeMining.sln",
                           ROOT / "src/engine_anyfim/code/AnyFIM-Anytime/AnytimeMining/kernel.cu"),
}


def sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "builder": "tools/build_anyfim/build_msbuild.py",
                "method": "MSBuild + CUDA 12.5 VS BuildCustomizations (upstream recipe)",
                "msbuild": str(MSBUILD), "cuda_toolkit": str(CUDA),
                "targets": {}}
    ok = True
    for exe_name, (sln, upstream_kernel) in SLNS.items():
        projdir = sln.parent
        proj_name = projdir.name
        # refresh the build copy of kernel.cu from upstream (kept out of git;
        # the committed .sln/.vcxproj copies reference it)
        local_kernel = projdir / "kernel.cu"
        if sha256(local_kernel) != sha256(upstream_kernel):
            shutil.copyfile(upstream_kernel, local_kernel)
        r = subprocess.run(
            [str(MSBUILD), str(sln), "/p:Configuration=Release", "/p:Platform=x64",
             f"/p:CudaToolkitDir={CUDA}\\", "/v:m", "/nologo"],
            capture_output=True, text=True, encoding="gbk", errors="replace",
            timeout=2400)
        built = list(projdir.rglob("*.exe"))
        if r.returncode != 0 or not built:
            ok = False
            print(f"BUILD FAILED {exe_name} rc={r.returncode}")
            print(r.stdout[-2500:])
            print(r.stderr[-800:])
            continue
        exe = built[0]
        dst = OUT / exe_name
        shutil.copyfile(exe, dst)
        src_kernel = next(projdir.rglob("kernel.cu"))
        manifest["targets"][exe_name] = {
            "solution": str(sln),
            "build_copy_kernel_sha256": sha256(src_kernel),
            "exe_sha256": sha256(dst),
            "exe_bytes": dst.stat().st_size,
        }
        print(f"built {exe_name} <- {exe}")
    manifest_path = OUT / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    print("manifest:", manifest_path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
