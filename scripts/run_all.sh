#!/usr/bin/env bash
# run_all.sh - one-click reproduction of all B-paper experiments.
# Every stage is incremental (existing results are skipped), so the script
# is safe to re-run; network stages (G1) resume from partial downloads.
#
# Usage:  bash run_all.sh [stage ...]     # default: all stages
# Stages: g1 g3 g2 e4 e1 e2 e3 e5 e13 e14 e17 e62 e63
set -uo pipefail
cd "$(dirname "$0")/.."
PY=python

run() { echo "== $* =="; $PY "$@" || echo "!! stage failed: $* (continuing)"; }

for stage in "${@:-g1 g3 g2 e4 e1 e2 e3 e5 e13 e14 e17 e62 e63}"; do
  case $stage in
    g1)  run -u tools/download_all_shards.py --budget 250   # exit 2 = more to fetch
         run -u tools/build_corpus.py --tiers 10000 --allow-partial ;;
    g3)  run -u tools/g34_sanity.py ;;
    g2)  run -u tools/test_baselines.py ;;
    e4)  run -u tools/e4_scaling.py --n-queries 50 ;;
    e1)  run -u tools/e1_matrix.py ;;
    e2)  run -u tools/e2_bounds.py ;;
    e3)  run -u tools/e3_anytime.py ;;
    e5)  run -u tools/e5_ablation.py ;;
    e13) run -u tools/e13_hard_negatives.py ;;
    e14) run -u tools/e14_structural_confirm.py --start 0 --donors 80 ;;
    e17) run -u tools/e17_cascade.py --start 0 --donors 80 ;;
    e62) run -u tools/e62_memorization.py ;;
    e63) run -u tools/e63_cases.py --start 0 --limit 100000 ;;
    *) echo "unknown stage: $stage" ;;
  esac
done
echo "run_all done. Results in runs/; see docs/paper_number_lineage.md"
