# Reproduction Package

Research code and experiment outputs for a two-layer copy detection system
for symbolic music: a provable-recall tolerant screen plus a strict
structural confirmation layer.

This archive contains everything needed to reproduce every number, table, and
figure in the manuscript. Two routes are supported:

| Route | Time | What you do |
|---|---|---|
| **Fast** (verify the paper) | ~5 min | Use the shipped `runs/` results → rebuild `Manuscript.docx` |
| **Full** (reproduce from raw data) | ~1 day (mostly download) | Download Lakh → encode corpus → run all experiments |

---

## 1. Layout

```
Manuscript.docx              the paper (built by src/publish/build_manuscript.py)
src/adapter/                 detection system: encoder, tolerant screen,
                             structural confirmation, cascade, baselines
src/publish/                 manuscript + figure build scripts
tools/                       experiment scripts E1-E6 (e*.py) and data pipeline
scripts/run_all.sh           one-click full reproduction (incremental stages)
runs/                        raw experiment outputs (JSONL) that feed the paper
results/figures/             all figures as EMF/SVG (embedded in the manuscript)
results/refs/                literature-verification worksheets (per-topic CSV)
docs/paper_number_lineage.md every paper number -> {script, result file, commit}
data/README.md               dataset registry (sources, licenses, checksums)
```

## 2. Environment

- Python 3.12, Windows or Linux. No GPU required.
- `pip install -r requirements.txt` (equivalent conda env: `environment.yml`).
- Figures are embedded as EMF: the manuscript build calls Inkscape
  (`inkscape` on PATH) to convert SVG→EMF. Without Inkscape the docx build
  skips EMF embedding; all SVG/PNG sources are in `results/figures/`.
- The two FIM engines reused from our companion paper (under review at EAAI)
  are needed **only** for the G2 FIM-enumeration baseline stage. Their
  provenance and version-locked sources are registered in `src/SOURCES.txt`.
  Every number in the manuscript is reproducible without them except the
  "corpus-side FIM enumeration is infeasible" baseline observation (Section
  V-A), which any frequent-itemset miner can confirm.

## 3. Fast route (verify the paper)

```bash
gunzip runs/e63/pairs.jsonl.gz        # 139 MB, exceeds GitHub's 100 MB/file limit
python -u src/publish/build_manuscript.py     # writes Manuscript.docx
```

`build_manuscript.py` reads `runs/*/*.jsonl` and regenerates every table,
figure caption, and in-text number. The committed `runs/` are the exact
outputs behind the submitted manuscript (see `docs/paper_number_lineage.md`).

## 4. Full route (reproduce from raw data)

```bash
# G1: download Lakh MIDI full (55 parquet shards, ~9 GB) and encode to
# item-set transactions (174,300 pieces). Both steps are resumable; the
# downloader exits 2 while shards remain - re-run until "ALL SHARDS COMPLETE".
python -u tools/download_all_shards.py --budget 250
python -u tools/build_corpus.py --shards data/raw/lmd_parquet \
    --out data/processed/lmd --tiers 10000 100000 0 --seed 42

# G2/G3: sanity gates + baselines, then every experiment (incremental).
bash scripts/run_all.sh

# Rebuild the manuscript from the fresh results.
python -u src/publish/build_manuscript.py
```

Notes:

- **Corpus**: `roszcz/lakh-lmd-full` (HuggingFace mirror of Lakh MIDI v0.1).
  If huggingface.co is unreachable, set `HF_ENDPOINT=https://hf-mirror.com`.
  License: see `data/README.md` (research use).
- **Hard-negative / confirmation / cascade / memorization / case-study
  experiments** (E1.3, E1.4, E7, E6.2, E6.3) run on the first 3,000 pieces of
  shard 0 — same source and fixed seeds as E1/E5, per Section IV of the paper.
- E6.3 screens all 3,000 corpus pieces against each other (1,658,993 candidate
  duplicate pairs, `runs/e63/pairs.jsonl`); this is the longest single stage.
- Every experiment script accepts `--seed`; all reported numbers aggregate the
  fixed seeds baked into the scripts.

## 5. Two-package split (code vs. data)

The release is split into two archives:

| Archive | Goes to | Contents |
|---|---|---|
| `B-paper-code-*.zip` | **GitHub** (public) | All source code, experiment scripts, docs, figure sources (EMF/SVG), experiment result JSONL, `pairs.jsonl.gz`, checksums, this file |
| `B-paper-dataset-*.zip` | **local archive only — do NOT upload** | Raw Lakh parquet shards (8.3 GB), encoded transaction cache, FIMI tier files, per-shard SHA-256 manifest |

**The dataset is publicly downloadable** — reviewers and readers do not need
the dataset archive. Download Lakh MIDI full directly from the public
HuggingFace repository `roszcz/lakh-lmd-full` (mirror of Lakh MIDI v0.1,
174,300 pieces, 55 shards, ~9 GB), then verify against
`docs/SHA256SUMS_lmd_parquet.txt` and encode with `tools/build_corpus.py`:

```bash
python -u tools/download_all_shards.py --budget 250   # resumable; repeat until 55/55
sha256sum -c docs/SHA256SUMS_lmd_parquet.txt          # optional integrity check
python -u tools/build_corpus.py --shards data/raw/lmd_parquet \
    --out data/processed/lmd --tiers 10000 100000 0 --seed 42
```

If huggingface.co is unreachable from your network, set
`HF_ENDPOINT=https://hf-mirror.com` (see `data/README.md`).

### What is NOT in the GitHub archive (and why)

| Excluded | Size | Reason / how to obtain |
|---|---|---|
| `data/raw/lmd_parquet/` | 8.3 GB | Public dataset; download + verify per above |
| `data/processed/lmd/cache/` | 418 MB | Encoded transactions; rebuilt by `build_corpus.py` |
| `data/processed/lmd/*.txt` | 860 MB | FIMI tier files; rebuilt by `build_corpus.py` |
| `src/engine_anyfim/`, `src/engine_tensorfim/` | 1.8 GB | Companion-paper engines; provenance in `src/SOURCES.txt`, needed only for G2 |
| `runs/G3.4/` | 40 MB | Sanity-gate dumps incl. public FIM benchmark datasets; regenerated by `tools/g34_sanity.py` |
| `runs/e63/pairs.jsonl` (raw) | 139 MB | Shipped as `pairs.jsonl.gz` (13.7 MB) in the repo; `gunzip` after clone |

## 6. Pushing to GitHub

- Upload **only the code archive** (or `git push` the repository). No dataset
  files are tracked in git except the registry (`data/README.md`) and the
  checksum manifest (`docs/SHA256SUMS_lmd_parquet.txt`).
- `runs/e63/pairs.jsonl.gz` is force-added to git; after clone, `gunzip` it
  (Section 3). Alternatively register the raw file with Git LFS.
- The repository is self-contained apart from the public dataset above; no
  git submodules are required for the main pipeline.

---

*Generated 2026-10-12. Manuscript build commit: see `git log`.*
