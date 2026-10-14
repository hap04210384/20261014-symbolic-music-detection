# -*- coding: utf-8 -*-
"""E6.3 case studies (substitute design, approved fallback 2026-10-12):
the Lakh corpus itself mixes multiple user transcriptions of the same
commercial songs -- exactly the real-world duplication a publisher must
adjudicate.  We discover such pairs in the wild (tolerant screen, one full
piece as query), then produce publisher-grade evidence for 4 cases:

  (a) near-verbatim duplicate   (b) transposed cover
  (c) partial reuse (one section copied into a longer piece)
  (d) style-similar NEGATIVE (no confirmed copy; honest contrast)

Evidence per case: greedy ordered alignment (strict tolerance), shared-run
stats, modal pitch offset (transposition interval), and an alignment map
saved for the EMF figure pipeline at manuscript time.

Output: runs/e63/cases.jsonl, runs/e63/alignments.pkl (figure input)
"""
from __future__ import annotations

import argparse
import json
import pickle
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

OUTDIR = ROOT / "runs/e63"
OUT = OUTDIR / "cases.jsonl"
ALIGN = OUTDIR / "alignments.pkl"
KP, KB, KV = 1, 0, 0
RHO = 0.5


def greedy_align(qm, cm, k_pitch=KP, k_bin=KB, k_vel=KV):
    """Leftmost ordered alignment of query notes into candidate notes.
    Returns list of (i, j) and modal pitch offset."""
    qp, qd, qg, qv = qm
    cp, cd, cg, cv = cm
    m = len(cp)
    pairs = []
    j_prev = -1
    for i in range(len(qp)):
        pi, di, gi, vi = int(qp[i]), int(qd[i]), int(qg[i]), int(qv[i])
        found = -1
        for j in range(j_prev + 1, m):
            if abs(int(cp[j]) - pi) <= k_pitch and \
                    abs(int(cd[j]) - di) <= k_bin and \
                    abs(int(cg[j]) - gi) <= k_bin and \
                    abs(int(cv[j]) - vi) <= k_vel:
                found = j
                break
        if found >= 0:
            pairs.append((i, found))
            j_prev = found
    deltas = [int(cp[j]) - int(qp[i]) for i, j in pairs]
    modal = int(np.bincount(np.array(deltas) - min(deltas)).argmax()) + \
        min(deltas) if deltas else 0
    return pairs, modal


def _sketch_codes_pair(p0, p1, d, g, v, cfg):
    iv = (int(p1) - int(p0)) % 12
    return ((((iv * cfg.dur_bins + int(d)) * cfg.ioi_bins + int(g))
             * cfg.vel_bins + int(v)) + 1)


def windowed_greedy_align(qm, cm, cidx, cfg, k_pitch=KP, k_bin=KB,
                          k_vel=KV, margin=100):
    """Region-aware, transposition-tolerant evidence alignment.
    Phase 1: vote for the dominant index offset j-i among STRICT-variant
    anchors (roughly constant in a copied region with preserved rhythm;
    wide codes would drown the signal).
    Phase 1b: if strict support is weak, estimate the transposition from
    interval-sketch anchors (transposition-invariant), transpose the query
    pitch axis, and redo Phase 1.
    Phase 2: within the candidate window, run an exact LCS DP restricted to
    query notes that have strict anchors there (leftmost-greedy fails:
    style matches early in the candidate consume positions and the true
    segment gets skipped).  Returns (pairs, modal_delta, window)."""
    transposition = 0
    svotes = e14.query_codes(qm, cfg, 1, 0, 0)
    votes: dict[int, int] = {}
    for i, codes in enumerate(svotes):
        for c in codes:
            for j in cidx.get(c, ()):
                d = j - i
                votes[d] = votes.get(d, 0) + 1
    support = votes.get(max(votes, key=votes.get), 0) if votes else 0
    if support < 0.2 * len(qm[0]):
        # weak direct overlap -> estimate transposition via sketch anchors
        sk_cidx: dict[int, list[int]] = {}
        for j in range(len(cm[0]) - 1):
            c = _sketch_codes_pair(cm[0][j], cm[0][j + 1], cm[1][j],
                                   cm[2][j], cm[3][j], cfg)
            sk_cidx.setdefault(c, []).append(j)
        dvotes: dict[int, int] = {}
        for i in range(len(qm[0]) - 1):
            c = _sketch_codes_pair(qm[0][i], qm[0][i + 1], qm[1][i],
                                   qm[2][i], qm[3][i], cfg)
            for j in sk_cidx.get(c, ()):
                delta = int(cm[0][j]) - int(qm[0][i])
                dvotes[delta] = dvotes.get(delta, 0) + 1
        if dvotes:
            mdelta = max(dvotes, key=dvotes.get)
            if dvotes[mdelta] >= 0.15 * len(qm[0]):
                transposition = mdelta
                # correct the query toward the candidate: qm + (c - q)
                qp = np.clip(qm[0].astype(np.int32) + mdelta, 0, 127) \
                    .astype(np.int16)
                qm = (qp, qm[1], qm[2], qm[3])
                svotes = e14.query_codes(qm, cfg, 1, 0, 0)
                votes = {}
                for i, codes in enumerate(svotes):
                    for c in codes:
                        for j in cidx.get(c, ()):
                            d = j - i
                            votes[d] = votes.get(d, 0) + 1
    if not votes:
        return [], transposition, (0, 0)
    mode = max(votes, key=votes.get)
    m = len(cm[0])
    j_lo = max(0, mode - margin)
    j_hi = min(m, mode + len(qm[0]) + margin)

    # rows: query notes with >=1 strict anchor inside the window
    rows = []
    row_anchor_sets = []
    for i, codes in enumerate(svotes):
        js = set()
        for c in codes:
            for j in cidx.get(c, ()):
                if j_lo <= j < j_hi:
                    js.add(j)
        if js:
            rows.append(i)
            row_anchor_sets.append(js)
    if not rows:
        return [], 0, (j_lo, j_hi)
    w = j_hi - j_lo
    # exact LCS DP over rows x window with match test in wide tolerance;
    # match predicate restricted to strict anchors (cheap and sufficient:
    # a wide-tolerant match that is not strict-anchored cannot be trusted)
    table = np.zeros((len(rows), w), dtype=np.int32)
    for ri in range(len(rows)):
        i = rows[ri]
        pi = int(qm[0][i])
        anch = row_anchor_sets[ri]
        prev = table[ri - 1] if ri > 0 else None
        row = table[ri]
        run = 0
        if prev is None:
            for jj in range(w):
                v = 1 if (jj + j_lo) in anch else 0
                row[jj] = v
                if v > run:
                    run = v
        else:
            for jj in range(w):
                v = 0
                if (jj + j_lo) in anch:
                    cand = int(prev[jj - 1]) + 1 if jj > 0 else 1
                    if cand > v:
                        v = cand
                if int(prev[jj]) > v:
                    v = int(prev[jj])
                if run > v:
                    v = run
                row[jj] = v
                run = v
    # traceback from the max cell
    ri, jj = np.unravel_index(int(table.argmax()), table.shape)
    pairs = []
    while ri >= 0 and jj >= 0 and table[ri, jj] > 0:
        cur = int(table[ri, jj])
        i = rows[ri]
        if (jj + j_lo) in row_anchor_sets[ri] and cur == 1:
            pairs.append((i, jj + j_lo))
            break  # chain start
        if jj > 0 and (jj + j_lo) in row_anchor_sets[ri] and \
                int(table[ri - 1, jj - 1]) == cur - 1:
            pairs.append((i, jj + j_lo))
            ri -= 1
            jj -= 1
        elif ri > 0 and int(table[ri - 1, jj]) == cur:
            ri -= 1
        else:
            jj -= 1
    pairs.reverse()
    deltas = [int(cm[0][j]) - int(qm[0][i]) for i, j in pairs]
    modal = int(np.bincount(np.array(deltas) - min(deltas)).argmax()) + \
        min(deltas) if deltas else 0
    return pairs, modal + transposition, (j_lo, j_hi)


def sketch_txn(ev, cfg):
    """Transposition-invariant item set: interval-from-previous-note
    (mod 12) replaces pitch.  Same binning as midi_encode._bin."""
    ordered = sorted(ev, key=lambda e: (e.onset_tick, e.pitch))
    if len(ordered) < 2:
        return set()
    grid = max(1, 1000 // cfg.tpb)
    items = set()
    for i in range(len(ordered) - 1):
        iv = (ordered[i + 1].pitch - ordered[i].pitch) % 12
        d = min(cfg.dur_bins - 1,
                (ordered[i].duration_tick + grid // 2) // grid)
        ioi = ordered[i + 1].onset_tick - ordered[i].onset_tick
        g = min(cfg.ioi_bins - 1, (ioi + grid // 2) // grid)
        v = min(ordered[i].velocity >> 4, cfg.vel_bins - 1) \
            if cfg.vel_bins < 128 else ordered[i].velocity
        items.add((((iv * cfg.dur_bins + d) * cfg.ioi_bins + g)
                   * cfg.vel_bins + v) + 1)
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=100000)
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    cfg = EncodingConfig(use_channel=False)
    ev_corpus = load_events(
        ROOT / "data/raw/lmd_parquet/train-00000-of-00055.parquet",
        e13.CORPUS_PIECES)
    txns = [e13.encode(ev, cfg) for ev in ev_corpus]
    n_pieces = len(txns)

    # ---- stage 1: dual-index discovery (incremental) ---------------------
    pair_out = OUTDIR / "pairs.jsonl"
    done_rows = set()
    if pair_out.exists():
        for l in pair_out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                done_rows.add((r["a"], r["kind"]))
    print("stage 1: building exact + sketch indexes ...", flush=True)
    t0 = time.time()
    index = CorpusIndex(txns)
    sk_txns = [sketch_txn(ev, cfg) for ev in ev_corpus]
    sk_index = CorpusIndex(sk_txns)
    print(f"indexes in {time.time() - t0:.0f}s", flush=True)

    all_ids = set(range(n_pieces))
    hi = min(args.start + args.limit, n_pieces)
    t0 = time.time()
    with open(pair_out, "a", encoding="utf-8") as f:
        for pi in range(args.start, hi):
            if len(txns[pi]) < 30:
                continue
            for kind, idx, tt in (("exact", index, txns),
                                  ("sketch", sk_index, sk_txns)):
                if (pi, kind) in done_rows:
                    continue
                r = idx.detect_tolerant(tt[pi], min_evidence=40, k_pitch=0,
                                        k_bin=0, k_vel=0, cfg=cfg,
                                        pieces_of_interest=all_ids)
                for k_, v_ in r.scores_of_interest.items():
                    k_ = int(k_)
                    if k_ <= pi:
                        continue
                    if v_ >= 40 and v_ >= 0.35 * min(len(tt[pi]),
                                                     len(tt[k_])):
                        f.write(json.dumps({"a": pi, "b": k_, "kind": kind,
                                            "shared": int(v_),
                                            "len_a": len(tt[pi]),
                                            "len_b": len(tt[k_])}) + "\n")
            if (pi + 1) % 200 == 0:
                print(f"  {pi + 1}/{hi} ({time.time() - t0:.0f}s)",
                      flush=True)
    if hi < n_pieces:
        print(f"chunk done through piece {hi}; re-run with --start {hi}")
        return 0
    pairs = [json.loads(l) for l in pair_out.read_text(encoding="utf-8")
             .splitlines() if l.strip()]
    seen = set()
    pairs = [p for p in pairs
             if not ((p["a"], p["b"]) in seen or seen.add((p["a"], p["b"])))]
    print(f"discovered {len(pairs)} candidate pairs (deduped)", flush=True)

    print("building note matrices + code indexes ...", flush=True)
    t0 = time.time()
    cms = [e14.note_matrix(ev, cfg) for ev in ev_corpus]
    cidxs = [e14.code_index(cm, cfg) if cm is not None else {}
             for cm in cms]
    print(f"  in {time.time() - t0:.0f}s", flush=True)
    # wide tolerance for transposition-tolerant publisher evidence
    W_P, W_B, W_V = 6, 1, 1

    # cluster pairs into groups (same underlying song)
    parent = list(range(n_pieces))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairs:
        ra, rb = find(p["a"]), find(p["b"])
        if ra != rb:
            parent[ra] = rb
    groups: dict[int, list[int]] = {}
    for p in pairs:
        groups.setdefault(find(p["a"]), []).append(p)
    clusters = sorted(groups.values(), key=len, reverse=True)
    print(f"clusters: {len(clusters)}, top sizes: "
          f"{[len(c) for c in clusters[:8]]}", flush=True)

    # ---- stage 2: pick 4 diverse cases + 1 negative ----------------------
    # clean-case filters: single-song-sized files (by NOTE count — medley
    # MIDI files have few distinct items but thousands of notes), comparable
    # lengths
    note_len = [len(cm[0]) if cm is not None else 0 for cm in cms]

    def clean(p, max_notes=4000, ratio=2.0):
        na, nb = note_len[p["a"]], note_len[p["b"]]
        return (0 < na <= max_notes and 0 < nb <= max_notes
                and max(na, nb) <= ratio * min(na, nb))

    cases = []
    # (a) near-verbatim: highest shared fraction among clean pairs
    pool_a = [p for p in pairs if clean(p)]
    best = max(pool_a, key=lambda p: p["shared"] / min(p["len_a"],
                                                       p["len_b"]))
    cases.append(("near_verbatim_dup", best["a"], best["b"]))
    # (b) arrangement variant: same-song pair, wide-chain coverage >= 0.75
    # of the shorter piece but not identical (if the modal pitch offset is
    # >= 2 semitones the case is reported as a transposed cover)
    used = {best["a"], best["b"]}
    wide_qc_cache: dict[int, list] = {}

    def wide_cov(a, b):
        # strict codes for speed; final evidence uses wide greedy align
        key = a
        if key not in wide_qc_cache:
            wide_qc_cache[key] = e14.query_codes(cms[a], cfg, KP, KB, KV)
        return e14.chain_lcs(wide_qc_cache[key], cidxs[b])

    variant = None
    cands_b = sorted((p for p in pool_a if p["kind"] == "sketch"),
                     key=lambda p: -p["shared"])[:150]
    for p in cands_b:
        if p["a"] in used or p["b"] in used:
            continue
        na, nb = note_len[p["a"]], note_len[p["b"]]
        cov = wide_cov(p["a"], p["b"])
        if 0.4 * min(na, nb) <= cov < 0.97 * min(na, nb):
            variant = p
            break
    if variant:
        qm, cm = cms[variant["a"]], cms[variant["b"]]
        pairs_al, modal, _ = windowed_greedy_align(qm, cm, cidxs[p["b"]], cfg, W_P, W_B, W_V)
        tag = "transposed_cover" if abs(modal) >= 2 else "arrangement_variant"
        cases.append((tag, variant["a"], variant["b"]))
        used |= {variant["a"], variant["b"]}

    # (c) partial reuse: shorter piece largely contained in a longer one
    partial = None
    for p in sorted(pool_a, key=lambda p: -p["shared"])[:200]:
        if p["a"] in used or p["b"] in used:
            continue
        na, nb = note_len[p["a"]], note_len[p["b"]]
        if max(na, nb) < 1.4 * min(na, nb):
            continue
        if wide_cov(p["a"], p["b"]) >= 0.35 * min(na, nb):
            partial = p
            break
    if partial:
        cases.append(("partial_reuse", partial["a"], partial["b"]))
        used |= {partial["a"], partial["b"]}

    # ---- (b)/(c) synthesized fallbacks from the real identical pair ------
    # shard 0's natural duplicates are overwhelmingly verbatim copies of the
    # same transcription; arrangement/partial variants are absent.  When not
    # found in the wild we synthesize them FROM the real pair (honest tag):
    #   transposed_cover_synth: piece 1947 transposed +3 semitones
    #   partial_reuse_synth: piece 511 with a 30 s span of another real
    #     piece (574) spliced into its middle
    synth_queries = {}
    if not any(t[0].startswith("transposed_cover") or
               t[0] == "arrangement_variant" for t in cases):
        src_ev = sorted(ev_corpus[best["b"]],
                        key=lambda e: (e.onset_tick, e.pitch))
        t_ev = [Event(e.onset_tick, min(127, e.pitch + 3), e.duration_tick,
                      e.channel, e.velocity) for e in src_ev]
        synth_queries["transposed_cover_synth"] = (t_ev, best["b"])
    if not any(t[0] == "partial_reuse" for t in cases):
        base = sorted(ev_corpus[best["a"]],
                      key=lambda e: (e.onset_tick, e.pitch))
        donor_ev = sorted(ev_corpus[574],
                          key=lambda e: (e.onset_tick, e.pitch))
        mid = base[len(base) // 2].onset_tick
        head = [e for e in base if e.onset_tick < mid]
        tail = [e for e in base if e.onset_tick >= mid]
        d0, d1 = donor_ev[0].onset_tick, donor_ev[-1].onset_tick
        take = [e for e in donor_ev if e.onset_tick <= d0 + 30000]
        shift_take = [Event(e.onset_tick - d0 + mid, e.pitch,
                            e.duration_tick, e.channel, e.velocity)
                      for e in take]
        shift_tail = [Event(e.onset_tick - mid + mid + 30000, e.pitch,
                            e.duration_tick, e.channel, e.velocity)
                      for e in tail]
        splice = head + shift_take + shift_tail
        synth_queries["partial_reuse_synth"] = (splice, 574)

    # (d) negative: style-similar pair with NO confirmed copy
    feats = e13.piece_features(ev_corpus)
    neg = None
    rng = np.random.RandomState(3)
    for _ in range(400):
        a = int(rng.randint(0, n_pieces))
        sims = feats @ feats[a]
        sims[a] = -1
        b = int(np.argsort(-sims)[0])
        if len(txns[a] & txns[b]) >= 30:
            continue  # actual duplicate, not a negative
        qm, cm = cms[a], cms[b]
        if qm is None or cm is None:
            continue
        qcodes = e14.query_codes(qm, cfg, KP, KB, KV)
        run = e14.chain_lcs(qcodes, cidxs[b])
        if run < RHO * len(qm[0]):
            neg = (a, b, run)
            break
    if neg:
        cases.append(("negative_style_pair", neg[0], neg[1]))

    # ---- stage 3: evidence per case --------------------------------------
    align_store = {}
    with open(OUT, "w", encoding="utf-8") as f:
        for name, a, b in cases:
            qm, cm = cms[a], cms[b]
            pairs_al, modal, _ = windowed_greedy_align(qm, cm, cidxs[b], cfg, W_P, W_B, W_V)
            nq = len(qm[0])
            run_len = 0
            best_seg = (0, 0)
            # longest contiguous-ish segment of the alignment
            cur = 0
            prev_i = -2
            for (i, j) in pairs_al:
                cur = cur + 1 if i == prev_i + 1 else 1
                if cur > run_len:
                    run_len = cur
                prev_i = i
            row = {
                "case": name, "piece_a": a, "piece_b": b,
                "notes_a": nq, "notes_b": len(cm[0]),
                "aligned_pairs": len(pairs_al),
                "aligned_frac_a": round(len(pairs_al) / nq, 3),
                "longest_segment": run_len,
                "modal_delta_pitch": modal,
                "transposed_semitones": modal,
                "confirmed_copy": run_len >= max(50, 0.25 * min(nq, len(cm[0]))),
            }
            f.write(json.dumps(row) + "\n")
            align_store[name] = {"a": a, "b": b, "pairs": pairs_al,
                                 "modal": modal,
                                 "notes_a": [x.tolist() for x in qm],
                                 "notes_b": [x.tolist() for x in cm]}
            print(json.dumps(row), flush=True)

        # synthesized fallback cases: retrieve via the transposition-
        # invariant sketch index (top-5), report origin rank; evidence =
        # greedy alignment vs the origin piece (the copied span shows up as
        # the longest aligned segment)
        for name, (sev, origin) in synth_queries.items():
            qset = sketch_txn(sev, cfg)
            r = sk_index.detect_tolerant(qset, min_evidence=40, k_pitch=0,
                                         k_bin=0, k_vel=0, cfg=cfg,
                                         pieces_of_interest=all_ids)
            sk2 = np.zeros(n_pieces, dtype=np.int32)
            for k_, v_ in r.scores_of_interest.items():
                sk2[int(k_)] = v_
            top5 = [int(j) for j in np.argsort(-sk2)[:5]]
            qm = e14.note_matrix(sev, cfg)
            cm = cms[origin]
            pairs_al, modal, _ = windowed_greedy_align(qm, cm, cidxs[origin], cfg, W_P, W_B, W_V)
            run_len = 0
            cur = 0
            prev_i = -2
            for (i, j) in pairs_al:
                cur = cur + 1 if i == prev_i + 1 else 1
                if cur > run_len:
                    run_len = cur
                prev_i = i
            nq = len(qm[0])
            row = {
                "case": name, "piece_a": -1, "piece_b": origin,
                "origin_in_sketch_top5": origin in top5,
                "sketch_top5": top5,
                "notes_a": nq, "notes_b": len(cm[0]),
                "aligned_pairs": len(pairs_al),
                "aligned_frac_a": round(len(pairs_al) / nq, 3),
                "longest_segment": run_len,
                "modal_delta_pitch": modal,
                "transposed_semitones": modal,
                "confirmed_copy": run_len >= max(50, 0.25 * min(nq, len(cm[0]))),
                "synthesized_from_real_pair": True,
            }
            f.write(json.dumps(row) + "\n")
            align_store[name] = {"a": "synth", "b": origin,
                                 "pairs": pairs_al, "modal": modal,
                                 "notes_a": [x.tolist() for x in qm],
                                 "notes_b": [x.tolist() for x in cm]}
            print(json.dumps(row), flush=True)
    ALIGN.write_bytes(pickle.dumps(align_store))
    print(f"\nwrote {OUT} and {ALIGN}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
