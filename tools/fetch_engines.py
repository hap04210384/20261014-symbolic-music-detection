# -*- coding: utf-8 -*-
"""按文件清单从 raw.githubusercontent.com 逐文件拉取引擎仓库（git 协议被网络封锁的替代方案）。
断点续传：已存在且非空的文件跳过。provenance 写入 SOURCES.txt。"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = "https://raw.githubusercontent.com/hap04210384/{repo}/main/{path}"
HEADERS = {"TensorFIM": "706701795c2b6768f37837de3a85465662075252",
           "Anytime-Frequent-Itemset-Mining": "f2fbd69f1524f0226a0d645fdd8ba4963b09fb87"}

TENSORFIM = [
 "MANIFEST.md5","README.md",
 "code/batch_proto/PROTO_RESULTS.md","code/batch_proto/batch_proto.cu","code/batch_proto/build.bat",
 "code/batch_proto/run_bitmap_only.txt","code/batch_proto/run_dispatch.txt","code/batch_proto/batch_proto.exe",
 "code/engine/ablate.py","code/engine/build.bat","code/engine/build_bmma.bat","code/engine/compare_mfis.py",
 "code/engine/set_dataset.py","code/engine/src/kernel_bitmap.cu","code/engine/src/kernel_bmma.cu",
 "code/engine/run/CoParaCG_baseline.exe","code/engine/run/CoParaCG_bmma.exe","code/engine/run/vcomp140.dll",
 "code/microbench/RESULTS.md","code/microbench/bmma_bench.cu","code/microbench/build.bat",
 "code/microbench/sweep_results.txt","code/microbench/sweep_results_v2.txt","code/microbench/bmma_bench.exe",
 "data/DOWNLOAD.md","data/make_replica.py","data/strip_tcga.py",
 "data/gold_results/T10I4D100K.txt-0.005000=Results.txt",
 "data/gold_results/TCGA_BRCA_stripped.txt-0.650000=Results.txt",
 "data/gold_results/TCGA_BRCA_stripped.txt-0.700000=Results.txt",
 "data/gold_results/accidents.txt-0.500000=Results.txt",
 "data/gold_results/accidents_x4.txt-0.400000=Results.txt",
 "data/gold_results/accidents_x8.txt-0.400000=Results.txt",
 "data/gold_results/chainstore.txt-0.002000=Results.txt",
 "data/gold_results/chess.txt-0.800000=Results.txt",
 "data/gold_results/connect.txt-0.850000=Results.txt",
 "data/gold_results/connect.txt-0.900000=Results.txt",
 "data/gold_results/kosarak.dat-0.020000=Results.txt",
 "data/gold_results/mushrooms.txt-0.300000=Results.txt",
 "data/gold_results/pumsb_x256.txt-0.800000=Results.txt",
 "data/gold_results/retail.txt-0.010000=Results.txt",
 "data/gold_results/webdocs.dat-0.080000=Results.txt",
 "data/TCGA_BRCA_stripped.txt.gz",
 "data/small/T10I4D100K.txt","data/small/accidents.txt","data/small/chainstore.txt",
 "data/small/chess.txt","data/small/connect.txt","data/small/kosarak.dat",
 "data/small/mushrooms.txt","data/small/retail.txt",
 "portable/README.md","portable/RUN_ME.bat",
 "portable/anyfim_bmma/src/kernel_bitmap.cu","portable/anyfim_bmma/src/kernel_bmma.cu",
 "portable/prebuilt/CoParaCG_baseline.exe","portable/prebuilt/CoParaCG_baseline.exp",
 "portable/prebuilt/CoParaCG_baseline.lib","portable/prebuilt/CoParaCG_bmma.exe",
 "portable/prebuilt/CoParaCG_bmma.exp","portable/prebuilt/CoParaCG_bmma.lib",
 "portable/prebuilt/bmma_bench.exe","portable/prebuilt/bmma_bench.exp","portable/prebuilt/bmma_bench.lib",
 "portable/prebuilt/smcheck.exe","portable/prebuilt/smcheck.exp","portable/prebuilt/smcheck.lib",
 "portable/prebuilt/vcomp140.dll",
 "portable/scripts/bmma_bench.cu","portable/scripts/compare.ps1","portable/scripts/configs.txt",
 "portable/scripts/configs_quick.txt","portable/scripts/configs_selftest.txt",
 "portable/scripts/set_dataset.ps1","portable/scripts/smcheck.cu",
 "scripts/download_chainstore.py","scripts/download_webdocs.py","scripts/run_ablation.py",
 "scripts/run_all_configs.py","scripts/run_threshold_sweep.py","scripts/verify_all.py",
]

ANYFIM = [
 ".gitignore","LICENSE","README.md",
 "code/AnyFIM-Anytime/AnytimeMining.sln","code/AnyFIM-Anytime/AnytimeMining/AnytimeMining.vcxproj",
 "code/AnyFIM-Anytime/AnytimeMining/kernel.cu",
 "code/AnyFIM-GivenThreshold/CoParaCG.sln","code/AnyFIM-GivenThreshold/CoParaCG/CoParaCG.vcxproj",
 "code/AnyFIM-GivenThreshold/CoParaCG/kernel.cu",
 "code/baselines/CD/build.bat","code/baselines/CD/cd.cpp",
 "code/baselines/DMM/build.bat","code/baselines/DMM/dmm.cpp",
 "code/baselines/FPmax-LIB/.gitignore","code/baselines/FPmax-LIB/CMakeLists.txt",
 "code/baselines/FPmax-LIB/LICENSE","code/baselines/FPmax-LIB/README.md",
 "code/baselines/FPmax-LIB/build_cli.bat","code/baselines/FPmax-LIB/run_fpmax.cpp",
 "code/baselines/FPmax-LIB/src/buffer.cpp","code/baselines/FPmax-LIB/src/buffer.h",
 "code/baselines/FPmax-LIB/src/common.h","code/baselines/FPmax-LIB/src/data.cpp",
 "code/baselines/FPmax-LIB/src/data.h","code/baselines/FPmax-LIB/src/fitemset.cpp",
 "code/baselines/FPmax-LIB/src/fitemset.h","code/baselines/FPmax-LIB/src/fp_node.cpp",
 "code/baselines/FPmax-LIB/src/fp_node.h","code/baselines/FPmax-LIB/src/fp_tree.cpp",
 "code/baselines/FPmax-LIB/src/fp_tree.h","code/baselines/FPmax-LIB/src/fpmax.cpp",
 "code/baselines/FPmax-LIB/src/fpmax.h","code/baselines/FPmax-LIB/src/fsout.cpp",
 "code/baselines/FPmax-LIB/src/fsout.h",
 "code/baselines/FPmax-LIB/test/test-data/transactions.txt",
 "code/baselines/FPmax-LIB/test/test-src/CMakeLists.txt",
 "code/baselines/FPmax-LIB/test/test-src/test.cpp",
 "code/baselines/GMiner/BlockPage.h","code/baselines/GMiner/DeviceBuf.cuh",
 "code/baselines/GMiner/Framework.cuh","code/baselines/GMiner/Global.h",
 "code/baselines/GMiner/Kernel.cuh","code/baselines/GMiner/Materialization.cuh",
 "code/baselines/GMiner/PORTING_NOTES.md","code/baselines/GMiner/PageTmp.h",
 "code/baselines/GMiner/PagesetTmp.h","code/baselines/GMiner/README.md",
 "code/baselines/GMiner/SAUnit.h","code/baselines/GMiner/VerticalDatabase.h",
 "code/baselines/GMiner/build_win.bat","code/baselines/GMiner/data.cpp",
 "code/baselines/GMiner/data.h","code/baselines/GMiner/item.h",
 "code/baselines/GMiner/itemsetUnit.h","code/baselines/GMiner/main.cu",
 "code/baselines/RHSE/OWE.sln","code/baselines/RHSE/OWE/OWE.cpp",
 "code/baselines/RHSE/OWE/OWE.vcxproj",
 "datasets/accidents.txt","datasets/chess.txt","datasets/mushroom.txt","datasets/pumsb.txt",
 "results/expected/abl4_summary.csv",
 "results/expected/accidents.txt-0.400000=Results.txt",
 "results/expected/chess.txt-0.950000=Results.txt",
 "results/expected/mushroom.txt-0.520000=Results.txt",
 "results/expected/pumsb.txt-0.800000=Results.txt",
 "tools/replicate.py",
]

REPOS = [("TensorFIM", "engine_tensorfim", TENSORFIM),
         ("Anytime-Frequent-Itemset-Mining", "engine_anyfim", ANYFIM)]

def main():
    only_small = "--large" not in sys.argv  # 默认先跳过大文件(>8MB)，--large 才下载
    for repo, dest, paths in REPOS:
        base = os.path.join(ROOT, "src", dest)
        os.makedirs(base, exist_ok=True)
        ok = fail = skip = 0
        for p in paths:
            # 大文件（数据集）默认跳过，--large 时再拉
            if only_small and any(p.endswith(ext) for ext in ("/accidents.txt","/pumsb.txt","/chainstore.txt","/kosarak.dat",".txt.gz","/T10I4D100K.txt","/connect.txt","/retail.txt")):
                skip += 1
                continue
            target = os.path.join(base, p)
            if os.path.exists(target) and os.path.getsize(target) > 0:
                ok += 1
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            url = RAW.format(repo=repo, path=p)
            r = subprocess.run(["curl", "-sSL", "--retry", "3", "--max-time", "240", "-o", target, url])
            if r.returncode == 0 and os.path.getsize(target) > 0:
                ok += 1
            else:
                fail += 1
                print("FAIL:", p, flush=True)
        print(f"[{repo}] ok={ok} fail={fail} large-deferred={skip}", flush=True)
    # provenance
    with open(os.path.join(ROOT, "src", "SOURCES.txt"), "w", encoding="utf-8") as f:
        f.write("Files fetched per-file from raw.githubusercontent.com (git protocol blocked on this network)\n")
        for repo, dest, _ in REPOS:
            f.write(f"{dest}: https://github.com/hap04210384/{repo} @ main commit {HEADERS[repo]}\n")
    print("done.")

if __name__ == "__main__":
    main()
