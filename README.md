# Provable-Recall Screening with Structural Confirmation for Symbolic Music

Code and experiments for the paper **"Provable-Recall Screening with Structural
Confirmation: A Two-Layer Copy Detection System for Symbolic Music"**
(submission target: IEEE Transactions on Emerging Topics in Computational
Intelligence).

Given a corpus of symbolic music (MIDI and its derivatives) and a query — a new
submission, a generated sample, or a suspected infringement — the system finds
every piece that shares a substantially copied span with the query, ranks the
candidates, and returns note-level alignment evidence that a human adjudicator
can check against a score. It combines:

- **L1, a tolerant item-set screen** with a *provable* per-query recall
  contract: an evidence lower bound, verified cell by cell on 337 adversarial
  cells with zero violations, plus a rare-first *anytime* schedule with a
  sound open-candidate bound after any budget prefix;
- **L2/L3, a strict structural confirmation layer** that aligns ordered note
  chains and cuts the fragment-level false-positive rate on style-similar
  hard negatives to 2.1% at 83.9% recall under transcription noise.

Measured on the full **174,300-piece** Lakh MIDI corpus: the index builds in
24.75 s, answers queries at 41.9 ms (p50) with 100% planted recall, and scales
to publisher workloads on a single commodity workstation.

## Dataset — download it yourself (not redistributed here)

**We do not provide the dataset in this repository.** The benchmark corpus is
publicly available; please download it yourself:

- **Lakh MIDI full** — HuggingFace dataset `roszcz/lakh-lmd-full`
  (community mirror of Lakh MIDI v0.1, 174,300 pieces, 55 parquet shards,
  ~9 GB). If huggingface.co is unreachable from your network, set
  `HF_ENDPOINT=https://hf-mirror.com`.
- Verify your download against [`docs/SHA256SUMS_lmd_parquet.txt`](docs/SHA256SUMS_lmd_parquet.txt),
  then encode the corpus deterministically:

```bash
python -u tools/download_all_shards.py --budget 250   # resumable; repeat until 55/55
python -u tools/build_corpus.py --shards data/raw/lmd_parquet \
    --out data/processed/lmd --tiers 10000 100000 0 --seed 42
```

Due to its size (~9 GB) and license terms, the raw corpus, the encoded
transaction cache, and the FIMI tier files are **excluded from this
repository by design**. Both steps above are incremental and resumable.

## Reproduce the paper

See [REPRODUCE.md](REPRODUCE.md) for the two supported routes:

- **Fast (~5 min)** — use the shipped experiment outputs in `runs/` and
  rebuild the manuscript:
  `gunzip runs/e63/pairs.jsonl.gz && python -u src/publish/build_manuscript.py`
- **Full (~1 day, mostly download)** — `bash scripts/run_all.sh` from the raw
  corpus.

Every number, table, and figure in the paper traces to
[`docs/paper_number_lineage.md`](docs/paper_number_lineage.md): script →
result file → git commit.

## Layout

| Path | Contents |
|---|---|
| `src/adapter/` | detection system: event encoder, tolerant screen, structural confirmation, cascade, baselines |
| `src/publish/` | manuscript and figure build scripts |
| `tools/` | experiment scripts (E1–E6) and the data pipeline |
| `scripts/run_all.sh` | one-click full reproduction (incremental stages) |
| `runs/` | experiment outputs behind every paper number |
| `results/figures/` | all figures as EMF/SVG, embedded in the manuscript |
| `results/refs/` | literature-verification worksheets |
| `docs/` | experiment protocols, number lineage, dataset checksums |

## Environment

Python 3.12, no GPU required. `pip install -r requirements.txt`
(conda equivalent: `environment.yml`). EMF figure embedding uses Inkscape on
PATH; all SVG/PNG sources are provided, so the pipeline also runs without it.
The two FIM engines reused from our companion paper (under review) are needed
only for the G2 FIM-enumeration baseline; their version-locked sources are
registered in `src/SOURCES.txt`.

## License

MIT for the code in this repository. The datasets (Lakh MIDI, GigaMIDI) retain
their own licenses; see `data/README.md`.
