# -*- coding: utf-8 -*-
"""E6.4 memorization audit with a REAL trained generator (M5, 2026-10-14):

E6.2 emulated a generative model with an order-m n-gram + copy operator.
This experiment replaces the emulator with an actual neural generator:
a ~1M-parameter decoder-only transformer trained from scratch on 500
Lakh MIDI pieces (the same corpus family the detector indexes) until it
memorizes its training set (train loss -> ~0 while held-out loss stays
high).  Continuations are then sampled exactly like E6.2 (8-event seed
copied from a training piece; seed = context only, NOT part of the
detection query) and screened with the identical production cascade
(tolerant screen -> verbatim top-C=50 -> strict chain confirmation,
k=(1,0,0), rho=0.5).

Question: does a real overfit transformer regurgitate in the same
detection-relevant way as the n-gram/copy spectrum of Table XI?

Runs on CPU (torch); training is chunked via --seconds and resumes
from runs/e21/ckpt.pt.

Output: runs/e21/train_log.jsonl, runs/e21/generated.pkl,
        runs/e21/memorization.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapter.midi_encode import EncodingConfig, Event  # noqa: E402
from adapter.detector import CorpusIndex  # noqa: E402
from e1_matrix import load_events  # noqa: E402
import e13_hard_negatives as e13  # noqa: E402
import e14_structural_confirm as e14  # noqa: E402

OUTDIR = ROOT / "runs/e21"
DATA = OUTDIR / "data.pkl"
CKPT = OUTDIR / "ckpt.pt"
LOG = OUTDIR / "train_log.jsonl"
GEN = OUTDIR / "generated.pkl"
OUT = OUTDIR / "memorization.jsonl"

TRAIN_PIECES = 500
VAL_PIECES = 50
N_TOK_FIELDS = 4           # pitch, dur_bin, ioi_bin, vel_bin
SEED_LEN = 8
GEN_LEN = 120
N_SAMPLES = 60
TEMP = 0.8
TOP_C = 50
RHO = 0.5
KP, KB, KV = 1, 0, 0
GRID_TICKS = 125            # 1000 ms-per-beat / 8 (production grid)

# model
D_MODEL = 128
N_HEADS = 4
N_LAYERS = 4
D_FF = 512
MAX_LEN = 768
LR = 3e-4


# ---------------------------------------------------------------- tokenizer
def tokenize(ev_corpus, cfg: EncodingConfig):
    """piece -> np.int64 array [n_events, 4] of (pitch, dur, ioi, vel)."""
    from adapter.midi_encode import _bin  # same bins as the detector
    seqs = []
    for ev in ev_corpus:
        ordered = sorted(ev, key=lambda e: (e.onset_tick, e.pitch))
        if len(ordered) < SEED_LEN + GEN_LEN + 16:
            seqs.append(None)
            continue
        toks = np.empty((len(ordered), N_TOK_FIELDS), dtype=np.int64)
        for i, e in enumerate(ordered):
            nxt = ordered[i + 1] if i + 1 < len(ordered) else None
            ioi_tick = (nxt.onset_tick - e.onset_tick) if nxt else 0
            toks[i] = (e.pitch,
                       _bin(e.duration_tick, 1000, cfg.tpb, cfg.dur_bins),
                       _bin(ioi_tick, 1000, cfg.tpb, cfg.ioi_bins),
                       min(e.velocity >> 4, cfg.vel_bins - 1))
        seqs.append(toks)
    return seqs


def detokenize(toks: np.ndarray) -> list[Event]:
    # onsets are materialized on the production 125 ms grid with a minimum
    # IOI of one grid step: unconstrained sampling over-produces the chord
    # bin (ioi = 0), whose near-simultaneous 60 ms clusters collapse the
    # item set and inflate structural chains.  The clamp yields monophonic
    # streams, the same materialization family as the E6.2 emulator.
    notes = []
    t = 0
    for pitch, d, g, v in toks:
        dur = max(60, int(d) * GRID_TICKS)
        notes.append(Event(int(t), int(pitch), dur, 0,
                           min(127, int(v) * 16 + 8)))
        t += max(1, int(g)) * GRID_TICKS
    return notes


# ---------------------------------------------------------------- model
def build_model():
    import torch
    import torch.nn as nn

    class TinyGPT(nn.Module):
        def __init__(self):
            super().__init__()
            self.emb_p = nn.Embedding(128, D_MODEL)
            self.emb_d = nn.Embedding(16, D_MODEL)
            self.emb_g = nn.Embedding(16, D_MODEL)
            self.emb_v = nn.Embedding(8, D_MODEL)
            self.pos = nn.Embedding(MAX_LEN, D_MODEL)
            layer = nn.TransformerEncoderLayer(
                d_model=D_MODEL, nhead=N_HEADS, dim_feedforward=D_FF,
                dropout=0.0, batch_first=True, norm_first=True)
            self.tr = nn.TransformerEncoder(layer, num_layers=N_LAYERS)
            self.ln = nn.LayerNorm(D_MODEL)
            self.hp = nn.Linear(D_MODEL, 128)
            self.hd = nn.Linear(D_MODEL, 16)
            self.hg = nn.Linear(D_MODEL, 16)
            self.hv = nn.Linear(D_MODEL, 8)

        def forward(self, x, pad_mask):
            # x: [B, T, 4]
            h = (self.emb_p(x[..., 0]) + self.emb_d(x[..., 1])
                 + self.emb_g(x[..., 2]) + self.emb_v(x[..., 3])
                 + self.pos.weight[:x.shape[1]])
            mask = torch.triu(torch.full((x.shape[1], x.shape[1]),
                                         float("-inf")), diagonal=1) \
                .to(x.device)
            h = self.tr(h, mask=mask, src_key_padding_mask=pad_mask)
            h = self.ln(h)
            return self.hp(h), self.hd(h), self.hg(h), self.hv(h)

    return TinyGPT()


def n_params(m) -> int:
    return sum(p.numel() for p in m.parameters())


# ---------------------------------------------------------------- sampling
def sample_continuation(model, toks, st, gen_len, temp, g):
    """Seed from toks[st:st+SEED_LEN]; sample gen_len events. -> np [G,4]"""
    import torch
    cur = torch.from_numpy(toks[st:st + SEED_LEN]).long().unsqueeze(0)
    gen = []
    with torch.no_grad():
        for _ in range(gen_len):
            pad = torch.zeros(1, cur.shape[1], dtype=torch.bool)
            op, od, og, ov = model(cur, pad)

            def smp(o):
                p = torch.softmax(o[0, -1] / temp, dim=-1)
                return int(torch.multinomial(p, 1, generator=g))
            nxt = torch.tensor(
                [[[smp(op), smp(od), smp(og), smp(ov)]]])
            gen.append(nxt[0, 0].numpy())
            cur = torch.cat([cur, nxt], dim=1)
    return np.array(gen)


def overlap_stats(gen: np.ndarray, ref: np.ndarray) -> dict:
    """Position-wise pitch accuracy + 4/8-gram overlaps vs reference."""
    def ngrams(a, n):
        return {tuple(a[i:i + n, 0]) for i in range(len(a) - n)}
    out = {"pos_pitch_acc": round(float((gen[:, 0] == ref[:, 0]).mean()), 4)}
    for n in (4, 8):
        inter = len(ngrams(gen, n) & ngrams(ref, n))
        out[f"ov{n}"] = round(inter / max(1, len(ngrams(ref, n))), 4)
    return out


def piece_loss(model, toks, bs=16, w=512, stride=256) -> float:
    """Mean 4-field next-event loss of one piece (eval mode)."""
    import torch
    model.eval()
    wins = []
    if len(toks) <= w:
        wins = [toks]
    else:
        for st in range(0, len(toks) - w + 1, stride):
            wins.append(toks[st:st + w])
    tot, cnt = 0.0, 0
    with torch.no_grad():
        for lo in range(0, len(wins), bs):
            batch = wins[lo:lo + bs]
            xs = [torch.from_numpy(b[:-1]) for b in batch]
            ys = [torch.from_numpy(b[1:]) for b in batch]
            T = max(len(x) for x in xs)
            x = torch.zeros(len(batch), T, 4, dtype=torch.long)
            y = torch.zeros(len(batch), T, 4, dtype=torch.long)
            pad = torch.ones(len(batch), T, dtype=torch.bool)
            for j, (xj, yj) in enumerate(zip(xs, ys)):
                x[j, :len(xj)] = xj
                y[j, :len(yj)] = yj
                pad[j, :len(xj)] = False
            op, od, og, ov = model(x, pad)
            loss = (torch.nn.functional.cross_entropy(
                        op.transpose(1, 2), y[..., 0], reduction="none")
                    + torch.nn.functional.cross_entropy(
                        od.transpose(1, 2), y[..., 1], reduction="none")
                    + torch.nn.functional.cross_entropy(
                        og.transpose(1, 2), y[..., 2], reduction="none")
                    + torch.nn.functional.cross_entropy(
                        ov.transpose(1, 2), y[..., 3], reduction="none"))
            m = (~pad).float()
            tot += float((loss * m).sum())
            cnt += int(m.sum())
    return tot / cnt


# ---------------------------------------------------------------- parts
def part_prep(_args) -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cfg = EncodingConfig(use_channel=False)
    ev_corpus = load_events(
        ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet",
        e13.CORPUS_PIECES)
    seqs = tokenize(ev_corpus, cfg)
    usable = [i for i, s in enumerate(seqs) if s is not None]
    rng = random.Random(5)
    rng.shuffle(usable)
    train_ids = usable[:TRAIN_PIECES]
    val_ids = usable[TRAIN_PIECES:TRAIN_PIECES + VAL_PIECES]
    data = {"seqs": seqs, "train_ids": train_ids, "val_ids": val_ids}
    DATA.write_bytes(pickle.dumps(data))
    n_tok = sum(len(seqs[i]) for i in train_ids)
    print(f"usable {len(usable)}/{len(seqs)} pieces; "
          f"train={len(train_ids)} ({n_tok:,} events), "
          f"val={len(val_ids)}", flush=True)
    return 0


def part_train(args) -> int:
    import torch
    data = pickle.loads(DATA.read_bytes())
    seqs, train_ids, val_ids = (data["seqs"], data["train_ids"],
                                data["val_ids"])
    train_ids = train_ids[:args.pieces]
    device = "cpu"
    W = 512  # training window (events)
    model = build_model().to(device)
    start_epoch = 0
    if CKPT.exists():
        ck = torch.load(CKPT, map_location=device, weights_only=False)
        model.load_state_dict(ck["model"])
        start_epoch = ck["epoch"]
        print(f"resumed from epoch {start_epoch}", flush=True)
    print(f"model parameters: {n_params(model):,}", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    rng = random.Random(1000 + start_epoch)

    def windows(ids, bs, train):
        order = ids[:]
        rng.shuffle(order)
        for lo in range(0, len(order), bs):
            batch = order[lo:lo + bs]
            xs, ys = [], []
            for i in batch:
                toks = seqs[i]
                st = rng.randrange(0, len(toks) - W + 1) \
                    if len(toks) > W else 0
                win = toks[st:st + W]
                xs.append(torch.from_numpy(win[:-1]))
                ys.append(torch.from_numpy(win[1:]))
            yield xs, ys

    def loss_on(ids, bs, train):
        model.train() if train else model.eval()
        tot, cnt = 0.0, 0
        with torch.set_grad_enabled(train):
            for xs, ys in windows(ids, bs, train):
                T = max(len(x) for x in xs)
                B = len(xs)
                x = torch.zeros(B, T, 4, dtype=torch.long)
                y = torch.zeros(B, T, 4, dtype=torch.long)
                pad = torch.ones(B, T, dtype=torch.bool)
                for j, (xj, yj) in enumerate(zip(xs, ys)):
                    x[j, :len(xj)] = xj
                    y[j, :len(yj)] = yj
                    pad[j, :len(xj)] = False
                op, od, og, ov = model(x, pad.to(device))
                loss = (torch.nn.functional.cross_entropy(
                            op.transpose(1, 2), y[..., 0], reduction="none")
                        + torch.nn.functional.cross_entropy(
                            od.transpose(1, 2), y[..., 1], reduction="none")
                        + torch.nn.functional.cross_entropy(
                            og.transpose(1, 2), y[..., 2], reduction="none")
                        + torch.nn.functional.cross_entropy(
                            ov.transpose(1, 2), y[..., 3], reduction="none"))
                m = (~pad).float()
                l = (loss * m).sum() / m.sum()
                if train:
                    opt.zero_grad()
                    l.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step()
                tot += float(l) * B
                cnt += B
        return tot / cnt

    t_end = time.time() + args.seconds
    epoch = start_epoch
    while time.time() < t_end:
        epoch += 1
        t0 = time.time()
        tr = loss_on(train_ids, args.bs, True)
        va = loss_on(val_ids, args.bs_val, False)
        dt = time.time() - t0
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"epoch": epoch, "train_loss": round(tr, 4),
                                "val_loss": round(va, 4),
                                "secs": round(dt, 1)}) + "\n")
        torch.save({"model": model.state_dict(), "epoch": epoch}, CKPT)
        print(f"epoch {epoch}: train {tr:.4f} val {va:.4f} "
              f"({dt:.0f}s)", flush=True)
        if args.epochs and epoch >= start_epoch + args.epochs:
            break
    return 0


def part_sample(args) -> int:
    import torch
    data = pickle.loads(DATA.read_bytes())
    seqs, train_ids = data["seqs"], data["train_ids"]
    model = build_model()
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    model.load_state_dict(ck["model"])
    model.eval()
    print(f"model trained for {ck['epoch']} epochs", flush=True)
    g = torch.Generator().manual_seed(args.seed)
    rng = random.Random(args.seed)
    pieces = []
    for _ in range(N_SAMPLES):
        src = rng.choice(train_ids)
        toks = seqs[src]
        st = rng.randrange(0, len(toks) - SEED_LEN - GEN_LEN)
        gen = sample_continuation(model, toks, st, GEN_LEN, TEMP, g)
        pieces.append({"source": src, "seed_start": st, "group": "random",
                       "notes": detokenize(gen)})
    GEN.write_bytes(pickle.dumps(pieces))
    print(f"sampled {len(pieces)} continuations "
          f"(seed={args.seed}, T={TEMP})", flush=True)
    return 0


def part_audit(args) -> int:
    """Likelihood-ranked memorization audit.

    (1) per-piece held likelihood over all 500 split pieces + 50 val
        pieces  -> runs/e21/piece_loss.jsonl
    (2) sampling calibration: position-wise pitch accuracy and 4/8-gram
        overlap of continuations vs the true continuation, across the
        memorization range -> runs/e21/calibration.jsonl
    (3) screen sample: 20 most-memorized trained + 20 untrained controls
        + 20 random trained -> runs/e21/generated.pkl (for --part screen)
    """
    import torch
    data = pickle.loads(DATA.read_bytes())
    seqs = data["seqs"]
    trained = data["train_ids"][:args.pieces]
    untrained = data["train_ids"][args.pieces:]
    val = data["val_ids"]
    model = build_model()
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    model.load_state_dict(ck["model"])
    model.eval()
    print(f"audit at epoch {ck['epoch']}", flush=True)

    # (1) per-piece loss
    PL = OUTDIR / "piece_loss.jsonl"
    if not PL.exists() or args.redo:
        with PL.open("w", encoding="utf-8") as f:
            for split, ids in (("trained", trained),
                               ("untrained", untrained), ("val", val)):
                for i in ids:
                    l = piece_loss(model, seqs[i])
                    f.write(json.dumps({"piece": i, "split": split,
                                        "loss": round(l, 4)}) + "\n")
        print("per-piece loss written", flush=True)
    pl = [json.loads(l) for l in PL.read_text(encoding="utf-8").splitlines()
          if l.strip()]

    # (2) calibration across the memorization range
    CAL = OUTDIR / "calibration.jsonl"
    if not CAL.exists() or args.redo:
        trained_sorted = sorted((r for r in pl if r["split"] == "trained"),
                                key=lambda r: r["loss"])
        ut_sorted = sorted((r for r in pl if r["split"] == "untrained"),
                           key=lambda r: r["loss"])
        picks = ([("trained", r) for r in trained_sorted[:5]] +
                 [("trained", r) for r in trained_sorted[123:128]] +
                 [("trained", r) for r in trained_sorted[-5:]] +
                 [("untrained", r) for r in ut_sorted[:5]] +
                 [("untrained", r) for r in ut_sorted[-5:]])
        g = torch.Generator().manual_seed(args.seed + 1)
        rng = random.Random(args.seed + 1)
        with CAL.open("w", encoding="utf-8") as f:
            for split, r in picks:
                toks = seqs[r["piece"]]
                st = rng.randrange(0, len(toks) - SEED_LEN - GEN_LEN)
                gen = sample_continuation(model, toks, st, GEN_LEN,
                                          TEMP, g)
                ref = toks[st + SEED_LEN:st + SEED_LEN + GEN_LEN]
                f.write(json.dumps({
                    "piece": r["piece"], "split": split,
                    "loss": r["loss"], "seed_start": st,
                    **overlap_stats(gen, ref)}) + "\n")
        print("calibration written", flush=True)

    # (3) screen sample
    trained_sorted = sorted((r for r in pl if r["split"] == "trained"),
                            key=lambda r: r["loss"])
    ut_sorted = sorted((r for r in pl if r["split"] == "untrained"),
                       key=lambda r: r["loss"])
    rng = random.Random(args.seed)
    picks = ([("memorized", r["piece"]) for r in trained_sorted[:20]] +
             [("control", r["piece"]) for r in ut_sorted[:20]] +
             [("random_trained", r["piece"])
              for r in rng.sample(trained_sorted, 20)])
    g = torch.Generator().manual_seed(args.seed)
    pieces = []
    for group, src in picks:
        toks = seqs[src]
        st = rng.randrange(0, len(toks) - SEED_LEN - GEN_LEN)
        gen = sample_continuation(model, toks, st, GEN_LEN, TEMP, g)
        pieces.append({"source": src, "seed_start": st, "group": group,
                       "notes": detokenize(gen)})
    GEN.write_bytes(pickle.dumps(pieces))
    print(f"audit sample: {len(pieces)} pieces "
          f"(20 memorized / 20 control / 20 random trained)", flush=True)
    return 0


def part_screen(_args) -> int:
    cfg = EncodingConfig(use_channel=False)
    ev_corpus = load_events(
        ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet",
        e13.CORPUS_PIECES)
    txns = [e13.encode(ev, cfg) for ev in ev_corpus]
    index = CorpusIndex(txns)
    n_pieces = len(txns)
    all_ids = set(range(n_pieces))
    print("precomputing note matrices + code indexes ...", flush=True)
    t0 = time.time()
    cidxs = []
    for ev in ev_corpus:
        cm = e14.note_matrix(ev, cfg)
        cidxs.append(e14.code_index(cm, cfg) if cm is not None else {})
    print(f"  {n_pieces} pieces in {time.time() - t0:.0f}s", flush=True)

    pieces = pickle.loads(GEN.read_bytes())
    done = 0
    if OUT.exists():
        done = sum(1 for l in OUT.read_text(encoding="utf-8").splitlines()
                   if l.strip())
    todo = pieces[done:]
    print(f"screening: {len(todo)} pieces ({done} done)", flush=True)
    t_all = time.time()
    for pi, gp in enumerate(todo):
        notes = gp["notes"]
        q = e13.encode(notes, cfg)
        nq = len(notes)
        min_ev = max(8, len(q) // 2)
        t0 = time.time()
        rt = index.detect_tolerant(q, min_evidence=min_ev, k_pitch=2,
                                   k_bin=1, k_vel=1, cfg=cfg,
                                   pieces_of_interest=all_ids)
        st = np.zeros(n_pieces, dtype=np.int32)
        for k_, v_ in rt.scores_of_interest.items():
            st[int(k_)] = v_
        rv = index.detect_tolerant(q, min_evidence=1, k_pitch=0,
                                   k_bin=0, k_vel=0, cfg=cfg,
                                   pieces_of_interest=all_ids)
        sv = np.zeros(n_pieces, dtype=np.int32)
        for k_, v_ in rv.scores_of_interest.items():
            sv[int(k_)] = v_
        top_c = [int(j) for j in np.argsort(-sv)[:TOP_C]]
        cands = sorted(set(top_c))
        retained = gp["source"] in cands
        cands = sorted(set(cands) | {gp["source"]})
        qm = e14.note_matrix(notes, cfg)
        qcodes = e14.query_codes(qm, cfg, KP, KB, KV)
        runs = {c: e14.chain_lcs(qcodes, cidxs[c]) for c in cands}
        best_c = max(runs, key=lambda c: runs[c])
        row = {
            "source": gp["source"], "group": gp.get("group", "random"),
            "nq": nq, "lenq": len(q),
            "retained_source": retained,
            "best_run": runs[best_c],
            "best_piece": best_c,
            "source_run": runs[gp["source"]],
            "is_source": best_c == gp["source"],
            "confirmed": runs[best_c] >= RHO * nq,
            "wall_ms": round((time.time() - t0) * 1000, 1),
        }
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        if (pi + 1) % 10 == 0:
            print(f"  {pi + 1}/{len(todo)} "
                  f"({time.time() - t_all:.0f}s)", flush=True)

    rows = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    det = np.mean([r["confirmed"] for r in rows])
    src = np.mean([r["is_source"] for r in rows])
    ret = np.mean([r["retained_source"] for r in rows])
    print(f"\n==== E6.4 SUMMARY ({len(rows)} pieces) ====")
    print(f"detection {det:.3f}  source-attribution {src:.3f}  "
          f"top-C retention {ret:.3f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True,
                    choices=["prep", "train", "sample", "audit",
                             "screen"])
    ap.add_argument("--seconds", type=float, default=270.0)
    ap.add_argument("--epochs", type=int, default=0)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--pieces", type=int, default=250,
                    help="training pieces (first N of the prep split)")
    ap.add_argument("--lr", type=float, default=LR)
    ap.add_argument("--bs-val", type=int, default=25)
    ap.add_argument("--seed", type=int, default=23)
    ap.add_argument("--redo", action="store_true",
                    help="recompute piece loss / calibration even if cached")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    return {"prep": part_prep, "train": part_train,
            "sample": part_sample, "audit": part_audit,
            "screen": part_screen}[args.part](args)


if __name__ == "__main__":
    sys.exit(main())
