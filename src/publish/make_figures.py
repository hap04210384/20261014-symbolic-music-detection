# -*- coding: utf-8 -*-
"""Generate all manuscript figures from runs/*/ results.
Pipeline per writing_conventions.md: matplotlib -> SVG (fonts as paths)
-> Inkscape -> EMF in results/figures/.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FIGDIR = ROOT / "results/figures"
FIGDIR.mkdir(parents=True, exist_ok=True)
INKSCAPE = r"C:\Program Files\Inkscape\bin\inkscape.exe"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "svg.fonttype": "path",   # text -> curves: zero font risk in Word
    "figure.dpi": 150,
})


def load(name: str) -> list[dict]:
    p = ROOT / f"runs/{name}"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def save(fig, name: str) -> None:
    svg = FIGDIR / f"{name}.svg"
    emf = FIGDIR / f"{name}.emf"
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)
    subprocess.run([INKSCAPE, str(svg), "--export-type=emf",
                    f"--export-filename={emf}"], check=True,
                   capture_output=True)
    print(f"  {emf.name}", flush=True)


# ---------------------------------------------------------------- fig 1
def fig1_architecture() -> None:
    """Full system framework: offline indexing band, online screening band,
    guarantees band.  Information-dense first figure."""
    fig, ax = plt.subplots(figsize=(9.6, 5.9))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62)

    C_PROC, E_PROC = "#e8eef7", "#4a6fa5"   # processing boxes
    C_LAY, E_LAY = "#fdeedd", "#c96f2a"     # L1/L2/L3 layer boxes
    C_OUT, E_OUT = "#e5f3e5", "#3d8b3d"     # output / accept
    C_GAR, E_GAR = "#f2ecf9", "#7a5aa8"     # guarantee boxes
    C_BAND, E_BAND = "#f7f7f7", "#cccccc"
    INK = "#333333"

    def band(x, y, w, h, label):
        ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8",
            fc=C_BAND, ec=E_BAND, lw=0.8, zorder=1))
        ax.text(x + 2.0, y + h / 2, label, rotation=90, ha="center",
                va="center", fontsize=7, color="#666666", weight="bold",
                zorder=2)

    def stage(x, y, w, h, header, body, fc, ec, dashed=False, hfs=7):
        ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.5",
            fc=fc, ec=ec, lw=1.0, ls="--" if dashed else "-", zorder=3))
        ax.text(x + w / 2, y + h - 1.8, header, ha="center", va="center",
                fontsize=hfs, weight="bold", color=INK, zorder=4)
        ax.text(x + w / 2, y + (h - 3.2) / 2 - 0.3, body, ha="center",
                va="center", fontsize=6.3, color=INK, zorder=4,
                linespacing=1.4)

    def arrow(p0, p1, dashed=False, lw=1.1):
        ax.annotate("", xy=p1, xytext=p0, zorder=5,
                    arrowprops=dict(arrowstyle="-|>", lw=lw, color=INK,
                                    ls="--" if dashed else "-"))

    def elbow(pts, dashed=False):
        for a, b in zip(pts[:-2], pts[1:-1]):
            ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=1.0,
                    ls="--" if dashed else "-", zorder=5,
                    solid_capstyle="round")
        arrow(pts[-2], pts[-1], dashed=dashed)

    # ---- band A: offline index construction --------------------------
    band(2, 44, 96, 17, "OFFLINE · INDEX CONSTRUCTION")
    ya, ha = 47.5, 9.0
    stage(8.0, ya, 13.5, ha, "CORPUS",
          "symbolic music\n69,723 MIDI pieces", C_PROC, E_PROC)
    stage(24.5, ya, 16.5, ha, "EVENT ENCODING",
          "pitch class · IOI bin\n125 ms grid · velocity", C_PROC, E_PROC)
    stage(44.5, ya, 14.0, ha, "DENSE ID REMAP",
          "gapless item IDs\ncompression (§III-B)", C_PROC, E_PROC)
    stage(61.5, ya, 21.0, ha, "L1 ITEM-SET INDEX",
          "FP-growth · rare-first order\nbuild 9.7 s · query p50 15.2 ms",
          C_PROC, E_PROC)
    for x0, x1 in [(21.5, 24.5), (41.0, 44.5), (58.5, 61.5)]:
        arrow((x0, ya + ha / 2), (x1, ya + ha / 2))

    # ---- band B: online screening ------------------------------------
    band(2, 12, 96, 28, "ONLINE · COPY SCREENING")
    yb, hb = 17.5, 13.0
    stage(7.5, yb, 10.0, hb, "QUERY",
          "new MIDI\npiece", C_PROC, E_PROC)
    stage(19.5, yb, 11.5, hb, "ENCODER",
          "shared event\nencoding", C_PROC, E_PROC, dashed=True)
    stage(33.5, yb, 16.0, hb, "L1 · TOLERANT SCREEN",
          "rare-first anytime\ntwo-sided rare itemset\nrecall lower bound",
          C_LAY, E_LAY)
    stage(51.5, yb, 13.0, hb, "L2 · VERBATIM RE-RANK",
          "tolerant + verbatim\ntop-C union feed", C_LAY, E_LAY, hfs=6.3)
    stage(66.5, 15.5, 15.0, 15.0, "L3 · STRUCTURAL CONFIRM",
          "strict-anchor offset vote\ntransposition estimate\n"
          "anchored LCS · tolerance ρ", C_LAY, E_LAY, hfs=6.3)
    stage(87.5, yb, 10.0, hb, "REPORT",
          "verdict + evidence:\nnote alignment\n· offset map", C_OUT, E_OUT)

    ym = 24.0  # mid arrow line
    for x0, x1 in [(17.5, 19.5), (31.0, 33.5), (49.5, 51.5),
                   (64.5, 66.5), (81.5, 82.6), (86.9, 87.5)]:
        arrow((x0, ym), (x1, ym))
    # candidate-pair count on L1 -> L2 arrow
    ax.text(50.5, 26.2, "1.66 M pairs", ha="center", fontsize=6,
            style="italic", color=INK, zorder=6,
            bbox=dict(fc="white", ec="none", pad=0.15))
    ax.text(58.0, 15.3, "top-C retention 96.6 % (C50)", ha="center",
            fontsize=6, style="italic", color=INK, zorder=6)

    # decision diamond
    dc = (84.75, ym)
    ax.add_patch(plt.Polygon([(dc[0], dc[1] + 2.2), (dc[0] + 2.25, dc[1]),
                              (dc[0], dc[1] - 2.2), (dc[0] - 2.25, dc[1])],
                             closed=True, fc="#fff2cc", ec="#b58900",
                             lw=1.0, zorder=4))
    ax.text(dc[0], dc[1], "ρ ≥ θ ?", ha="center", va="center",
            fontsize=5.2, color=INK, zorder=5)
    ax.text(86.6, 25.6, "yes", ha="center", fontsize=5.8, color=INK,
            style="italic", zorder=6)
    ax.text(dc[0] + 0.2, dc[1] - 3.1, "no", ha="center", fontsize=5.8,
            color=INK, style="italic", zorder=6)
    arrow((dc[0], dc[1] - 2.3), (dc[0], 14.0), dashed=True)
    ax.text(dc[0], 13.3, "rejected\n(FP-controlled)", ha="center",
            va="top", fontsize=5.8, color="#777777", zorder=6,
            linespacing=1.2)

    # anytime budget knob
    knob = (41.0, 35.5)
    ax.add_patch(plt.Circle(knob, 2.6, fc="white", ec=INK, lw=1.0,
                            zorder=4))
    ax.text(knob[0], knob[1], "B", ha="center", va="center", fontsize=8,
            weight="bold", color=INK, zorder=5)
    ax.text(knob[0] + 3.6, knob[1] + 0.2, "anytime budget", ha="left",
            va="center", fontsize=6, style="italic", color=INK, zorder=5)
    arrow((knob[0] + 1.2, knob[1] - 2.4), (knob[0] + 0.4, 30.9))

    # cross-band links
    elbow([(72.0, 47.5), (72.0, 41.0), (41.0, 41.0), (41.0, 30.9)])
    elbow([(32.75, 47.5), (32.75, 42.0), (25.25, 42.0), (25.25, 30.9)],
          dashed=True)
    ax.text(29.2, 43.0, "shared encoding", ha="center", fontsize=6,
            style="italic", color="#555555", zorder=6)

    # ---- band C: guarantees -------------------------------------------
    band(2, 1.5, 96, 9.0, "GUARANTEES")
    yg, hg = 3.0, 6.0
    stage(7.5, yg, 28.0, hg, "THM 1 · RECALL LOWER BOUND",
          "L1 never drops a true copy —\n337-cell audit: 0 violations",
          C_GAR, E_GAR)
    stage(38.5, yg, 28.0, hg, "ANYTIME EFFICIENCY",
          "rare-first converges fastest —\n16× cleaner candidates (E3)",
          C_GAR, E_GAR)
    stage(69.5, yg, 28.0, hg, "DECISION-GRADE PRECISION",
          "L3 structural confirm —\nFP 2.1 %, R 83.9 % @ ρ = 0.5 (E1.4)",
          C_GAR, E_GAR)
    elbow([(37.0, 17.5), (37.0, 13.0), (21.5, 13.0), (21.5, 9.4)],
          dashed=True)
    elbow([(46.0, 17.5), (46.0, 11.0), (52.5, 11.0), (52.5, 9.4)],
          dashed=True)
    elbow([(74.0, 15.5), (74.0, 11.0), (83.5, 11.0), (83.5, 9.4)],
          dashed=True)

    save(fig, "fig1_architecture")


# ---------------------------------------------------------------- fig 2
def fig2_scaling() -> None:
    rows = sorted(load("e4/scaling.jsonl"), key=lambda r: r["n_pieces"])
    n = [r["n_pieces"] for r in rows]
    build = [r["ours"]["build_secs"] for r in rows]
    p50 = [r["ours"]["query_p50_ms"] for r in rows]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.plot(n, build, "o-", ms=3.5, lw=1, color="#1f5fb4",
            label="index build (s)")
    ax.plot(n, p50, "s--", ms=3.5, lw=1, color="#c0392b",
            label="query p50 (ms)")
    jn = [r["n_pieces"] for r in rows if "jaccard_scan" in r]
    jp = [r["jaccard_scan"]["query_p50_ms"] for r in rows
          if "jaccard_scan" in r]
    ax.plot(jn, jp, "^:", ms=4, lw=1, color="#7f8c8d",
            label="Jaccard scan p50 (ms), infeasible beyond 10k")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("corpus size (pieces)")
    ax.set_ylabel("time (s / ms, log)")
    ax.grid(True, which="both", lw=0.3, alpha=0.4)
    ax.legend(loc="lower right")
    recall = [r["ours"]["recall"] for r in rows]
    ok = all(r.split("/")[0] == r.split("/")[1] for r in recall)
    ax.set_title(f"planted recall = 100% at all sizes (n={len(rows)})"
                 if ok else "planted recall varies")
    save(fig, "fig2_scaling")


# ---------------------------------------------------------------- fig 3
def fig3_anytime() -> None:
    rows = [r for r in load("e3/anytime.jsonl") if r["length_s"] == 16]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    style = {"rare": ("o-", "#1f5fb4"), "random": ("s--", "#27ae60"),
             "hot": ("^:", "#c0392b")}
    for order, (st, c) in style.items():
        sub = [r for r in rows if r["order"] == order]
        fr = sorted({r["fraction"] for r in sub})
        mean_rem, found = [], []
        for f in fr:
            cell = [r for r in sub if r["fraction"] == f]
            mean_rem.append(float(np.mean([r["n_hits"] + r["remaining_bound"]
                                           for r in cell])))
            found.append(np.mean([r["donor_found"] for r in cell]))
        ax.plot(fr, mean_rem, st, ms=3.5, lw=1, color=c,
                label=f"{order}-first")
    ax.set_yscale("log")
    ax.set_xlabel("budget (fraction of positions processed)")
    ax.set_ylabel("open candidates (bound)")
    ax.grid(True, which="both", lw=0.3, alpha=0.4)
    ax.legend(loc="upper right")
    ax.set_title("anytime behaviour, 16 s spans")
    save(fig, "fig3_anytime")


# ---------------------------------------------------------------- fig 4
def fig4_bounds() -> None:
    rows = load("e2/bounds.jsonl")
    b = np.array([r["bound"] for r in rows])
    s = np.array([r["donor_score"] for r in rows])
    g = np.array([r["guaranteed"] for r in rows])
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.scatter(b[~g], s[~g], s=8, c="#bdc3c7", label="not guaranteed")
    ax.scatter(b[g], s[g], s=8, c="#1f5fb4", label="guaranteed cells")
    lim = max(b.max(), s.max()) * 1.05
    ax.plot([0, lim], [0, lim], "k--", lw=0.8)
    ax.text(lim * 0.62, lim * 0.80, "measured = bound", fontsize=7,
            rotation=24)
    ax.set_xlabel("theoretical evidence lower bound")
    ax.set_ylabel("measured donor evidence")
    ax.legend(loc="lower right")
    viol = int(np.sum(s < b))
    ax.set_title(f"337 cells, {viol} bound violations")
    save(fig, "fig4_bounds")


# ---------------------------------------------------------------- fig 5
def fig5_cascade() -> None:
    rows = load("e17/cascade.jsonl")
    n = len(rows)
    # three families of operating points
    pts = []
    for f_ in (0.25, 0.5, 0.75):
        rec = np.mean([r["donor_st"] >= max(8, int(r["lenq"] * f_))
                       for r in rows])
        fp = np.mean([any(s >= max(8, int(r["lenq"] * f_)) for s in r["pool_st"])
                      for r in rows])
        pts.append((fp, rec, f"L1 screen t={f_}"))
    for tau in (16, 20, 25, 30):
        rec = np.mean([r["donor_sv"] >= tau for r in rows])
        fp = np.mean([any(s >= tau for s in r["pool_sv"]) for r in rows])
        pts.append((fp, rec, "L2 rank"))
    for c in (20, 50):
        for rho in (0.4, 0.5):
            ret = np.array([r["retention"][str(c)] == 1 for r in rows])
            conf = np.array([r[f"cascade_C{c}"]["rho_grid"][str(rho)][
                "donor_confirmed"] for r in rows])
            rec = float((ret & conf).mean())
            fp = float(np.mean([len(r[f"cascade_C{c}"]["rho_grid"][str(rho)][
                "fp"]) > 0 for r in rows]))
            pts.append((fp, rec, f"cascade C={c}"))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(6.8, 2.6))
    seen = set()
    for fp, rec, lab in pts:
        fam = lab.split()[0]
        mk = {"L1": "o", "L2": "s", "cascade": "^"}[fam]
        c = {"L1": "#c0392b", "L2": "#27ae60", "cascade": "#1f5fb4"}[fam]
        if fam not in seen:
            ax.plot(fp, rec, mk, ms=6, color=c, label=fam, ls="None")
            seen.add(fam)
        else:
            ax.plot(fp, rec, mk, ms=6, color=c, ls="None")
        if fam == "cascade":
            ax.annotate(lab.split()[1], (fp, rec), textcoords="offset points",
                        xytext=(4, -9), fontsize=6)
    ax.set_xlabel("fragment-level false-positive rate")
    ax.set_ylabel("donor recall")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(0.3, 1.03)
    ax.grid(True, lw=0.3, alpha=0.4)
    ax.legend(loc="lower left")
    ax.set_title("(a) operating points, hard negatives")
    cs = [5, 10, 20, 50]
    ret = [np.mean([r["retention"][str(c)] for r in rows]) for c in cs]
    ax2.bar([str(c) for c in cs], ret, color="#1f5fb4", width=0.55)
    ax2.axhline(0.99, ls="--", lw=0.8, c="#c0392b")
    ax2.text(1.6, 0.9835, "union feed target 99%", fontsize=6.5,
             color="#c0392b")
    ax2.set_ylim(0.75, 1.01)
    ax2.set_xlabel("candidate set size C")
    ax2.set_ylabel("donor retention (top-C)")
    ax2.set_title("(b) candidate retention")
    fig.tight_layout()
    save(fig, "fig5_cascade")


# ---------------------------------------------------------------- fig 6
def fig6_memorization() -> None:
    rows = load("e62/memorization.jsonl")
    lambdas = [0.0, 0.25, 0.5, 0.75, 1.0]
    orders = [2, 4, 8]
    det = {m: [] for m in orders}
    src = {m: [] for m in orders}
    for m in orders:
        for lam in lambdas:
            cell = [r for r in rows if r["m"] == m and r["lam"] == lam]
            det[m].append(np.mean([r["confirmed"] for r in cell]))
            src[m].append(np.mean([r["is_source"] for r in cell]))
    x = np.arange(len(lambdas))
    w = 0.26
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    for i, m in enumerate(orders):
        ax.bar(x + (i - 1) * w, det[m], w, label=f"m={m}",
               color=["#9db8d9", "#4a7ebb", "#1f3f73"][i])
        ax.plot(x + (i - 1) * w, src[m], "k_", ms=5)
    ax.plot([], [], "k_", ms=5, label="source attribution")
    ax.set_xticks(x, [str(l) for l in lambdas])
    ax.set_xlabel("copy probability lambda")
    ax.set_ylabel("detection rate")
    ax.set_ylim(0, 1.09)
    ax.grid(True, axis="y", lw=0.3, alpha=0.4)
    ax.legend(loc="upper left")
    ax.set_title("memorization spectrum, 750 generated pieces")
    save(fig, "fig6_memorization")


# ---------------------------------------------------------------- fig 7
def fig7_case() -> None:
    import pickle
    store = pickle.loads((ROOT / "runs/e63/alignments.pkl").read_bytes())
    case = store["partial_reuse_synth"]
    na, nb = case["notes_a"], case["notes_b"]
    ia = np.arange(len(na[0]))
    ib = np.arange(len(nb[0]))
    pairs = case["pairs"]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.plot(ia, ia * 0 + 1, "|", ms=3, color="#bdc3c7")
    ax.plot(ib * 0 + 1, ib, "|", ms=3, color="#bdc3c7")
    if pairs:
        pi = [p[0] for p in pairs]
        pj = [p[1] for p in pairs]
        ax.plot(pi, pj, ".", ms=1.2, color="#c0392b")
    ax.set_xlabel("query piece note index")
    ax.set_ylabel("corpus piece 574 note index")
    ax.set_title("spliced-span localization (30 s segment)")
    ax.grid(True, lw=0.3, alpha=0.4)
    save(fig, "fig7_case")


# ---------------------------------------------------------------- new figs
def _e1_groups():
    """Shared group order for the recall matrix (Table I / heatmap)."""
    return [
        ("Verbatim", "verbatim", [("identity", "None")]),
        ("Transpose", "transpose",
         [(f"\u00b1{s} st", str(s)) for s in (1, 2, 4, 6)]),
        ("Tempo", "tempo",
         [("\u00d71.05", "1.05"), ("\u00d71.10", "1.1"), ("\u00d71.20", "1.2")]),
        ("Split\u2013merge", "split_merge",
         [("p=0.10", "0.1"), ("p=0.20", "0.2"), ("p=0.30", "0.3")]),
        ("Re-instrument", "reinstrument",
         [("p=0.10", "0.1"), ("p=0.25", "0.25"), ("p=0.40", "0.4")]),
        ("Transcribe", "transcribe",
         [("15 ms/4 %", "[15, 0.04]"), ("30 ms/8 %", "[30, 0.08]"),
          ("60 ms/15 %", "[60, 0.15]")]),
    ]


def fig_e1_heatmap() -> None:
    """Recall (%) heatmap over the 337-cell matrix: 17 transform x
    strength rows x 4 span lengths."""
    rows = load("e1/matrix.jsonl")
    lengths = [2, 4, 8, 16]
    labels, mat = [], []
    for gname, tkey, slist in _e1_groups():
        for si, (slabel, skey) in enumerate(slist):
            sub = [r for r in rows if r["transform"] == tkey
                   and str(r["strength"]) == skey]
            labels.append(gname if si == 0 else "" )
            mat.append([
                100.0 * sum(1 for r in sub if r["length_s"] == L and r["hit"])
                / max(1, sum(1 for r in sub if r["length_s"] == L))
                for L in lengths])
    M = np.array(mat)
    fig, ax = plt.subplots(figsize=(3.3, 5.0))
    im = ax.imshow(M, cmap="RdYlGn", vmin=75, vmax=100, aspect="auto")
    ax.set_xticks(range(4), [f"{L} s" for L in lengths])
    ax.set_yticks(range(len(labels)),
                  [f"{g}  {s}" if g else s
                   for (g, s) in zip(labels,
                                     [sl for _, _, slist in _e1_groups()
                                      for sl, _ in slist])])
    ax.xaxis.set_ticks_position("top")
    ax.tick_params(length=0, labelsize=6.5)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            miss = M[i, j] < 100
            ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center",
                    fontsize=6, weight="bold" if miss else "normal",
                    color="#7f0000" if miss else "white")
    for e in ["top", "right", "bottom", "left"]:
        ax.spines[e].set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.5, pad=0.02)
    cb.ax.tick_params(labelsize=6)
    cb.set_label("recall (%)", fontsize=6.5)
    save(fig, "fig_e1_heatmap")


def fig_e13_margins() -> None:
    """Why screening is not deciding: score margins of the true donor
    versus the rest of the pool on hard negatives."""
    rows = load("e13/v2_screening.jsonl")
    tol_margins = [r["tolerant"]["margin"] for r in rows]
    verb_margins = [r["verbatim"]["margin"] for r in rows]
    tol_flag = [len(r["tolerant"]["fp_pool"]) > 0 for r in rows]
    verb_flag = [len(r["verbatim"]["fp_pool"]) > 0 for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.4))
    for ax, margins, flag, title in [
            (axes[0], tol_margins, tol_flag,
             "(a) L1 tolerant screen: donor margin"),
            (axes[1], verb_margins, verb_flag,
             "(b) L2 verbatim: donor margin")]:
        ax.hist(margins, bins=np.arange(-1.5, 42, 1.5) - 0.75,
                color="#7f9ec9", ec="#4a6fa5", lw=0.4)
        ax.axvline(0, color="#c0392b", lw=1.2, ls="--")
        ax.text(0.97, 0.96, f"{np.mean(flag) * 100:.0f}% of fragments\n"
                "flagged", transform=ax.transAxes, ha="right", va="top",
                fontsize=7)
        ax.set_xlabel("donor score minus best non-donor", fontsize=7.5)
        ax.set_ylabel("fragments", fontsize=7.5)
        ax.set_title(title, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.set_xlim(-2, 41)
    save(fig, "fig_e13_margins")


def fig_e14_rho() -> None:
    """Confirmation recall / FP trade-off over the tolerance regimes
    and contiguity thresholds rho."""
    rows = load("e14/confirm.jsonl")
    regimes = [("strict", "#1f5fb4", "s", "strict"),
               ("mid", "#c0392b", "o", "mid"),
               ("loose", "#27ae60", "^", "loose")]
    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    for key, color, marker, label in regimes:
        rec, fp = [], []
        for rho in ("0.3", "0.4", "0.5", "0.6"):
            grid = [r[key]["rho_grid"][rho] for r in rows]
            rec.append(100.0 * np.mean([g["donor_confirmed"] for g in grid]))
            fp.append(100.0 * np.mean([len(g["fp_pool"]) > 0 for g in grid]))
        ax.plot(fp, rec, marker=marker, ms=3.5, lw=1, color=color,
                label=label)
        for rho, x, y in zip(("0.3", "0.4", "0.5", "0.6"), fp, rec):
            ax.annotate(rho, (x, y), textcoords="offset points",
                        xytext=(4, 3), fontsize=5.5, color=color)
    ax.set_xlabel("fragment-level FP (%)", fontsize=7.5)
    ax.set_ylabel("donor recall (%)", fontsize=7.5)
    ax.set_title("contiguity threshold \u03c1 by anchor tolerance",
                 fontsize=8)
    ax.legend(fontsize=6.5, frameon=False)
    ax.grid(True, lw=0.3, alpha=0.4)
    ax.tick_params(labelsize=7)
    save(fig, "fig_e14_rho")


def fig_e5_ablation() -> None:
    """Component ablations: (a) span length, (b) tolerance vector,
    (c) grid granularity."""
    rows = load("e5/ablation.jsonl")
    L = [r for r in rows if r["ablation"] == "E5.4_L"]
    K = [r for r in rows if r["ablation"] == "E5.5_k"]
    G = [r for r in rows if r["ablation"] == "E5.7_grid"]
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.2))

    ax = axes[0]
    x = [r["factor"] for r in L]
    y = [r["false_candidates"] for r in L]
    ax.plot(x, y, "o-", ms=3.5, lw=1, color="#1f5fb4")
    ax.set_xlabel("span length factor L", fontsize=7.5)
    ax.set_ylabel("false candidates", fontsize=7.5)
    ax.set_title("(a) evidence span E5.4", fontsize=8)

    ax = axes[1]
    labels = [f"({r['k_pitch']},{r['k_bin']},{r['k_vel']})" for r in K]
    y = [r["false_candidates"] for r in K]
    recall = [int(r["recall"].split("/")[0]) / int(r["recall"].split("/")[1])
              for r in K]
    ax.bar(range(len(K)), y, color="#7f9ec9", ec="#4a6fa5", lw=0.5)
    ax.set_yscale("log")
    ax.set_xticks(range(len(K)))
    ax.set_xticklabels(labels, fontsize=6, rotation=45)
    ax2 = ax.twinx()
    ax2.plot(range(len(K)), [v * 100 for v in recall], "s--", ms=3,
             lw=1, color="#c0392b")
    ax2.set_ylim(60, 110)
    ax2.set_ylabel("recall (%)", fontsize=7, color="#c0392b")
    ax2.tick_params(labelsize=6.5, colors="#c0392b")
    ax.set_ylabel("false candidates (log)", fontsize=7.5)
    ax.set_title("(b) tolerance vector (kp,kb,kv) E5.5", fontsize=8)

    ax = axes[2]
    labels = [f"{r['grid_ms']} ms" for r in G]
    y = [r["false_candidates"] for r in G]
    ax.plot(range(len(G)), y, "o-", ms=3.5, lw=1, color="#1f5fb4",
            label="false candidates")
    ax.set_xticks(range(len(G)))
    ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_xlabel("quantization grid", fontsize=7.5)
    ax.set_ylabel("false candidates", fontsize=7.5)
    ax.set_title("(c) grid granularity E5.7", fontsize=8)

    for ax in axes:
        ax.tick_params(labelsize=7)
        ax.grid(True, lw=0.3, alpha=0.4)
    save(fig, "fig_e5_ablation")


ALL = {n: f for n, f in list(globals().items()) if n.startswith("fig")}
if __name__ == "__main__":
    which = sys.argv[1:] or list(ALL)
    for name in which:
        print(f"[{name}]", flush=True)
        ALL[name]()
    print("done ->", FIGDIR)
