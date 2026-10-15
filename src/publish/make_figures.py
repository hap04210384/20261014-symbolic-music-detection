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
    """Full system framework, four-panel card layout in the style of the
    companion anytime-mining figure: lettered column badges, cards with
    inline mini-visualizations, evidence arrows, bottom claims band.
    Numbers are the paper's authoritative values (174,300-piece corpus)."""
    # sans-serif, as in the reference figure (fonts are exported as paths)
    old = {k: plt.rcParams[k] for k in ("font.family", "font.serif",
                                        "font.sans-serif")}
    plt.rcParams.update({"font.family": "sans-serif",
                         "font.sans-serif": ["Arial", "Helvetica",
                                             "DejaVu Sans"]})
    try:
        _fig1_draw()
    finally:
        plt.rcParams.update(old)


def _fig1_draw() -> None:
    fig, ax = plt.subplots(figsize=(10.2, 5.9))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(1.4, 58)

    # --- palette: deep slate-blue primary, soft ochre accent, cool gray
    # vs warm sand card tints, ink-dark report card ----------------------
    GREEN, GREEN_DK = "#33566e", "#23404f"   # primary slate blue
    GOOD = "#57836a"                          # muted sage (positive)
    AMBER, AMBER_DK = "#bf8830", "#96691c"   # soft ochre accent
    BG, EC = "#ffffff", "#d9ddde"            # neutral white cards
    ABG, AEC = "#faf5ea", "#e6d7b8"          # warm sand cards (column c)
    DARK, DARK_TX = "#232b30", "#d3dee2"     # report card
    INK, GRAY = "#22292e", "#5c6569"
    MINT, MINT_E = "#eaf0ee", "#b4c6c0"      # audit-grid cells
    AXGR = "#a8b2b6"                          # mini-plot axes

    def mix(c1, c2, t):
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{round(x + (y - x) * t):02x}"
                             for x, y in zip(a, b))

    def badge(x, y, letter, title_lines):
        ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
            (x, y), 3.1, 3.1, boxstyle="round,pad=0,rounding_size=0.45",
            fc=GREEN, ec="none", zorder=6))
        ax.text(x + 1.55, y + 1.55, letter, ha="center", va="center",
                fontsize=11, weight="bold", color="white", zorder=7)
        ax.text(x + 4.0, y + 1.55, title_lines, ha="left", va="center",
                fontsize=8.6, weight="bold", color=INK, zorder=7,
                linespacing=1.15)

    def card(x, y, w, h, title, fc=BG, ec=EC, title_c=None, dashed=False):
        ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.55",
            fc=fc, ec=ec, lw=1.0, ls="--" if dashed else "-", zorder=3))
        ax.text(x + 1.2, y + h - 1.5, title, ha="left", va="center",
                fontsize=7.2, weight="bold",
                color=title_c or INK, zorder=5)

    def tag(x, y, text, fc=GREEN):
        w = 1.35 + 0.62 * len(text) * 0.72
        ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
            (x, y), w, 2.0, boxstyle="round,pad=0,rounding_size=0.9",
            fc=fc, ec="none", zorder=6))
        ax.text(x + w / 2, y + 1.0, text, ha="center", va="center",
                fontsize=5.6, weight="bold", color="white", zorder=7)

    def arrow(p0, p1, color=INK, lw=1.4, ls="-"):
        ax.annotate("", xy=p1, xytext=p0, zorder=8,
                    arrowprops=dict(arrowstyle="-|>", lw=lw, color=color,
                                    ls=ls, shrinkA=1, shrinkB=1))

    def elbow(pts, color=INK, lw=1.3, ls="-"):
        for a, b in zip(pts[:-2], pts[1:-1]):
            ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw,
                    ls=ls, zorder=7, solid_capstyle="round")
        arrow(pts[-2], pts[-1], color=color, lw=lw, ls=ls)

    def txt(x, y, s, fs=6.0, c=INK, w="normal", st="normal", ha="left"):
        ax.text(x, y, s, fontsize=fs, color=c, weight=w, style=st,
                ha=ha, va="center", zorder=6, linespacing=1.35)

    def piano_roll(x, y, w, h, seed, n=46):
        rng = np.random.default_rng(seed)
        for _ in range(n):
            t0 = rng.uniform(0, w - 1.6)
            d = rng.uniform(0.5, 1.7)
            p = rng.uniform(0.12 * h, 0.88 * h)
            ax.add_patch(plt.Rectangle(
                (x + t0, y + p - 0.28), d, 0.56,
                fc=mix("#d8e4ea", GREEN_DK, 0.1 + 0.8 * p / h),
                ec="none", alpha=0.9, zorder=4))
        ax.add_patch(plt.Rectangle((x, y), w, h, fc="none", ec=AXGR,
                                   lw=0.6, zorder=5))

    # ================= column headers =====================================
    HX = [2.0, 26.5, 51.0, 75.5]
    badge(HX[0], 54.2, "a", "Ingestion — publisher-scale\ncorpus")
    badge(HX[1], 54.2, "b", "Screening — provable-recall\nitem sets")
    badge(HX[2], 54.2, "c", "Confirmation — ordered\nnote chains")
    badge(HX[3], 54.2, "d", "Verdict — evidence-grounded\nreport")

    XA, XB, XC, XD = 2.0, 26.5, 51.0, 75.5
    WA, WB, WC, WD = 21.5, 21.5, 20.0, 22.5
    YT, YM, YB_ = 40.0, 24.5, 9.0   # card bottoms
    HH = 12.2                        # card height

    # ================= column a: ingestion ================================
    card(XA, YT, WA, HH, "LAKH MIDI CORPUS", title_c=GREEN_DK)
    piano_roll(XA + 1.4, YT + 2.6, WA - 2.8, 5.4, seed=7)
    txt(XA + 1.4, YT + 1.3, "174,300 pieces", fs=6.4, w="bold",
        c=GREEN_DK)
    tag(XA + WA - 9.6, YT + 0.6, "symbolic · MIDI")

    card(XA, YM, WA, HH, "EVENT ENCODING", title_c=GREEN_DK)
    rng = np.random.default_rng(11)
    for i in range(14):
        for j in range(5):
            if rng.random() < 0.42:
                ax.add_patch(plt.Rectangle(
                    (XA + 1.4 + i * 0.95, YM + 5.2 + j * 0.8), 0.8, 0.66,
                    fc=mix("#dbe6ec", GREEN_DK,
                           0.15 + 0.7 * rng.random()),
                    ec="none", zorder=4))
    ax.add_patch(plt.Rectangle((XA + 1.4, YM + 5.2), 13.3, 4.0,
                               fc="none", ec=AXGR, lw=0.6, zorder=5))
    txt(XA + 15.4, YM + 9.0, "pitch class", fs=5.6)
    txt(XA + 15.4, YM + 7.6, "IOI bin", fs=5.6)
    txt(XA + 15.4, YM + 6.2, "125 ms grid", fs=5.6)
    txt(XA + 15.4, YM + 4.6, "velocity", fs=5.6)
    txt(XA + 1.4, YM + 3.4, "items = quantized event tuples,", fs=6.0)
    txt(XA + 1.4, YM + 2.1, "dense gapless IDs (§III-B)", fs=6.0)
    txt(XA + 1.4, YM + 0.8, "order discarded at this layer", fs=5.6,
        c=GRAY, st="italic")

    card(XA, YB_, WA, HH, "L1 ITEM-SET INDEX", title_c=GREEN_DK)
    txt(XA + 1.4, YB_ + 8.6, "FP-growth · rare-first order", fs=6.2)
    txt(XA + 1.4, YB_ + 6.2, "build 24.7 s", fs=9.2, w="bold", c=GREEN_DK)
    txt(XA + 1.4, YB_ + 4.2, "query p50 41.9 ms", fs=9.2, w="bold",
        c=GREEN_DK)
    txt(XA + 1.4, YB_ + 2.4, "peak mem 1.05 GB · recall 47/47 planted",
        fs=5.6, c=GRAY)
    tag(XA + 1.4, YB_ + 0.5, "offline · once")

    # ================= column b: screening ================================
    card(XB, YT, WB, HH, "QUERY — NEW MIDI PIECE", title_c=GREEN_DK,
         dashed=True)
    piano_roll(XB + 1.4, YT + 4.6, WB - 2.8, 3.6, seed=23)
    txt(XB + 1.4, YT + 3.2, "a submission, a generated sample,", fs=6.0)
    txt(XB + 1.4, YT + 1.9, "or a suspected infringement", fs=6.0)
    tag(XB + 1.4, YT + 0.4, "same shared encoding", fc=GRAY)

    card(XB, YM, WB, HH, "L1 · TOLERANT SCREEN", title_c=GREEN_DK)
    xs = np.linspace(0, 10, 60)
    ys = 8.4 * (1 - np.exp(-xs / 3.1))
    ax.plot(XB + 3.4 + xs * 1.55, YM + 2.4 + ys * 0.62, color=GREEN,
            lw=1.6, zorder=4)
    ax.plot([XB + 3.4, XB + 19.0], [YM + 2.4, YM + 2.4], color=AXGR,
            lw=0.6, zorder=4)
    ax.plot([XB + 3.4, XB + 3.4], [YM + 2.4, YM + 7.9], color=AXGR,
            lw=0.6, zorder=4)
    ax.plot([XB + 16.8, XB + 16.8], [YM + 2.4, YM + 8.9], color=AMBER,
            lw=1.0, ls=":", zorder=4)
    txt(XB + 17.6, YM + 8.4, "budget B", fs=5.4, c=AMBER_DK, w="bold")
    txt(XB + 4.0, YM + 8.6, "cumulative evidence", fs=5.4, c=GRAY)
    txt(XB + 1.4, YM + 1.9, "rare-first anytime schedule —", fs=6.0)
    txt(XB + 1.4, YM + 0.6, "two-sided rare itemsets", fs=6.0)
    tag(XB + WB - 5.7, YM + HH - 2.5, "anytime")

    card(XB, YB_, WB, HH, "RECALL LOWER BOUND — THM 1", title_c=GREEN_DK)
    rng = np.random.default_rng(5)
    for i in range(8):
        for j in range(3):
            ax.add_patch(plt.Rectangle(
                (XB + 1.6 + i * 1.15, YB_ + 4.4 + j * 1.05), 0.95, 0.85,
                fc=MINT, ec=MINT_E, lw=0.5, zorder=4))
            ax.text(XB + 2.075 + i * 1.15, YB_ + 4.825 + j * 1.05, "0",
                    ha="center", va="center", fontsize=5.4, color=GREEN_DK,
                    zorder=5)
    txt(XB + 12.6, YB_ + 6.6, "337 adversarial cells", fs=6.2, w="bold")
    txt(XB + 12.6, YB_ + 5.2, "(8 transformations ×", fs=5.8, c=GRAY)
    txt(XB + 12.6, YB_ + 4.0, " noise levels)", fs=5.8, c=GRAY)
    txt(XB + 1.4, YB_ + 2.4, "donor evidence ≥ bound on every cell —",
        fs=6.0)
    txt(XB + 1.4, YB_ + 1.1, "L1 never drops a true copy", fs=6.0)
    tag(XB + WB - 6.4, YB_ + 0.5, "provable")

    # ================= column c: confirmation =============================
    card(XC, YT, WC, HH, "L2 · VERBATIM RE-RANK", fc=ABG, ec=AEC,
         title_c=AMBER_DK)
    txt(XC + 1.4, YT + 8.8, "tolerant + verbatim signatures,", fs=6.2)
    txt(XC + 1.4, YT + 7.5, "top-C union feed", fs=6.2)
    txt(XC + 1.4, YT + 5.4, "1.66 M pairs screened", fs=7.6, w="bold",
        c=AMBER_DK)
    txt(XC + 1.4, YT + 3.2, "top-C retention 96.6 % (C50)", fs=6.4)
    txt(XC + 1.4, YT + 1.6, "candidates only — no verdicts", fs=5.6,
        c=GRAY, st="italic")

    card(XC, YM, WC, HH, "L3 · STRUCTURAL CONFIRM", fc=ABG, ec=AEC,
         title_c=AMBER_DK)
    for row in range(2):
        yy = YM + 6.3 - row * 2.0
        for i in range(16):
            hit = (4 <= i <= 11) if row == 0 else (5 <= i <= 12)
            ax.add_patch(plt.Rectangle(
                (XC + 1.6 + i * 1.05, yy), 0.8, 0.9,
                fc=AMBER if hit else "#d9ccba", ec="none", zorder=4))
    ax.plot([XC + 5.8, XC + 14.0], [YM + 8.3, YM + 8.3], color=AMBER_DK,
            lw=0.9, zorder=4)
    ax.text(XC + 9.9, YM + 8.9, "matched span", ha="center", fontsize=5.4,
            color=AMBER_DK, zorder=5)
    txt(XC + 1.4, YM + 3.6, "strict-anchor offset vote", fs=6.2)
    txt(XC + 1.4, YM + 2.3, "transposition estimate · anchored LCS",
        fs=6.0)
    txt(XC + 1.4, YM + 0.9, "ordered chains, tolerance ρ", fs=5.6,
        c=GRAY, st="italic")

    card(XC, YB_, WC, HH, "VERDICT", fc=ABG, ec=AEC, title_c=AMBER_DK)
    dc = (XC + 4.6, YB_ + 5.2)
    ax.add_patch(plt.Polygon(
        [(dc[0], dc[1] + 2.6), (dc[0] + 2.7, dc[1]),
         (dc[0], dc[1] - 2.6), (dc[0] - 2.7, dc[1])],
        closed=True, fc="white", ec=AMBER_DK, lw=1.1, zorder=5))
    ax.text(dc[0], dc[1], "ρ ≥ θ ?", ha="center", va="center",
            fontsize=6.0, color=INK, zorder=6)
    txt(XC + 9.2, YB_ + 6.9, "FP  2.1 %", fs=6.6, w="bold", c=AMBER_DK)
    ax.add_patch(plt.Rectangle((XC + 9.2, YB_ + 5.6), 8.6, 0.75,
                               fc="#f2e3c8", ec="none", zorder=4))
    ax.add_patch(plt.Rectangle((XC + 9.2, YB_ + 5.6), 0.9, 0.75,
                               fc=AMBER, ec="none", zorder=5))
    txt(XC + 9.2, YB_ + 4.3, "R  83.9 %", fs=6.6, w="bold", c=GREEN_DK)
    ax.add_patch(plt.Rectangle((XC + 9.2, YB_ + 3.0), 8.6, 0.75,
                               fc="#deeee3", ec="none", zorder=4))
    ax.add_patch(plt.Rectangle((XC + 9.2, YB_ + 3.0), 7.2, 0.75,
                               fc=GOOD, ec="none", zorder=5))
    txt(XC + 9.2, YB_ + 1.6, "@ ρ = 0.5, transcription noise (E1.4)",
        fs=5.4, c=GRAY)
    # yes: exits upward between the bars, toward the report (column d)
    elbow([(dc[0] + 2.75, dc[1] + 0.2), (58.9, dc[1] + 0.2),
           (58.9, YB_ + 7.9), (XC + WC - 0.7, YB_ + 7.9)], color=GREEN_DK,
          lw=1.2)
    txt(60.4, YB_ + 8.7, "yes → report", fs=5.4, c=GREEN_DK, st="italic")
    arrow((dc[0], dc[1] - 2.7), (dc[0], YB_ + 0.6), color=GRAY, lw=1.0,
          ls="--")
    txt(dc[0] + 0.5, YB_ + 1.0, "no → rejected (FP-controlled)", fs=5.4,
        c=GRAY, st="italic")

    # ================= column d: verdict ==================================
    card(XD, YT, WD, HH, "REPORT", fc=DARK, ec=DARK, title_c="#9cc4d8")
    mono = [
        ("donor", "piece_0421.mid"),
        ("span",  "bars 33–48 · spliced"),
        ("offset", "+2 semitones · ×1.05"),
        ("score", "ρ = 0.62 ≥ θ  ✓"),
    ]
    for i, (k, v) in enumerate(mono):
        yy = YT + 8.6 - i * 2.1
        ax.text(XD + 1.5, yy, k, fontsize=6.0, color="#7f9dab",
                family="monospace", zorder=5)
        ax.text(XD + 5.6, yy, v, fontsize=6.0, color=DARK_TX,
                family="monospace", zorder=5)
    txt(XD + 1.4, YT + 1.2, "verdict + publisher-readable evidence",
        fs=5.6, c="#9cc4d8", st="italic")

    card(XD, YM, WD, HH, "MEMORIZATION AUDIT", title_c=GREEN_DK)
    lx = np.array([0, 0.25, 0.5, 0.75, 1.0])
    det = np.array([30, 52, 71, 88, 100])
    px = XD + 3.0 + lx * 15.5
    py = YM + 2.2 + det / 100 * 6.6
    ax.plot(px, py, color=GREEN, lw=1.6, marker="o", ms=2.6, zorder=4)
    ax.plot([XD + 3.0, XD + 19.0], [YM + 2.2, YM + 2.2], color=AXGR,
            lw=0.6, zorder=4)
    ax.plot([XD + 3.0, XD + 3.0], [YM + 2.2, YM + 9.0], color=AXGR,
            lw=0.6, zorder=4)
    for xx, lab in ((XD + 3.0, "0"), (XD + 18.75, "1")):
        ax.text(xx, YM + 1.2, lab, ha="center", fontsize=5.2, color=GRAY,
                zorder=5)
    ax.text(XD + 11.0, YM + 0.2, "copying level λ", ha="center",
            fontsize=5.2, color=GRAY, zorder=5)
    ax.text(XD + 2.5, YM + 8.6, "detection %", fontsize=5.2, color=GRAY,
            ha="right", zorder=5)
    txt(XD + 1.4, YM + 9.9, "26–34 % at λ = 0 → 100 % at λ = 1", fs=6.2,
        w="bold", c=GREEN_DK)
    txt(XD + 1.4, YM + 0.9, "attribution to source 96–100 %", fs=5.6,
        c=GRAY)

    card(XD, YB_, WD, HH, "IN-THE-WILD CASES", title_c=GREEN_DK)
    txt(XD + 1.4, YB_ + 8.6, "1,658,993 duplicate pairs", fs=7.6,
        w="bold", c=GREEN_DK)
    txt(XD + 1.4, YB_ + 6.6, "census over the full corpus (E6.3):", fs=6.0)
    txt(XD + 1.4, YB_ + 5.2, "spliced segments and transposed covers", fs=6.0)
    txt(XD + 1.4, YB_ + 3.9, "localized with offset maps", fs=6.0)
    tag(XD + 1.4, YB_ + 0.5, "human-adjudicable")

    # ================= flow arrows ========================================
    # vertical arrows inside columns
    for xc in (XA + WA / 2, XB + WB / 2, XC + WC / 2, XD + WD / 2):
        arrow((xc, YT - 0.2), (xc, YM + HH + 0.2), lw=1.2)
        arrow((xc, YM - 0.2), (xc, YB_ + HH + 0.2), lw=1.2)
    # shared encoding / index into screening (labels run along the elbow)
    elbow([(XA + WA, YM + 7.0), (24.9, YM + 7.0), (24.9, YT + 6.0),
           (XB, YT + 6.0)])
    ax.text(24.25, YM + 13.5, "shared encoding", fontsize=5.2, color=GRAY,
            style="italic", ha="center", va="center", rotation=90, zorder=6)
    elbow([(XA + WA, YB_ + 9.0), (25.7, YB_ + 9.0), (25.7, YM + 4.4),
           (XB, YM + 4.4)])
    ax.text(26.05, YB_ + 6.4, "index", fontsize=5.2, color=GRAY,
            style="italic", ha="center", va="center", rotation=90, zorder=6)
    # screen -> re-rank
    arrow((XB + WB, YM + 5.4), (XC, YT + 6.0))
    # confirm -> report
    arrow((XC + WC, YM + 5.6), (XD, YT + 5.6))
    ax.text(73.6, YM + 7.6, "evidence", fontsize=5.2, c=GRAY,
            style="italic", ha="center", va="center", zorder=6)

    # ================= claims band ========================================
    ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
        (2.0, 2.6), 96.0, 4.4, boxstyle="round,pad=0,rounding_size=0.5",
        fc=GREEN, ec="none", zorder=3))
    claims = [
        ("Provable recall", "Thm 1 · 337-cell audit, zero violations"),
        ("Anytime by construction", "budget B · rare-first schedule"),
        ("Decision-grade precision", "FP 2.1 % at R 83.9 % (ρ = 0.5)"),
        ("Publisher scale", "174,300 pieces · query p50 41.9 ms"),
    ]
    for i, (t, s) in enumerate(claims):
        cx = 4.5 + i * 24.5
        ax.text(cx, 5.7, t, fontsize=7.4, weight="bold", color="white",
                zorder=5)
        ax.text(cx, 3.9, s, fontsize=5.8, color="#d3dee2", zorder=5)
        if i:
            ax.plot([cx - 2.3, cx - 2.3], [3.3, 6.2], color="#5a7d92",
                    lw=0.8, zorder=4)
    # evidence arrows into the claims band
    arrow((XB + WB / 2, YB_ - 0.2), (XB + WB / 2, 7.2), color=AMBER,
          lw=1.5)
    arrow((XC + WC / 2, YB_ - 0.2), (XC + WC / 2, 7.2), color=AMBER,
          lw=1.5)

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
    e20 = {}
    for r in load("e20/scale.jsonl"):
        if r["tau"] == 0.10:
            e20[r["n_pieces"]] = r["query_p50_ms"]
    ln = [n_ for n_ in n if n_ in e20]
    lp = [e20[n_] for n_ in ln]
    ax.plot(ln, lp, "d-.", ms=4, lw=1, color="#8e44ad",
            label="MinHash-LSH p50 (ms), recall 0")
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


# ---------------------------------------------------------------- fig 8
def fig8_census() -> None:
    """Full-corpus census (e18) + stratified precision audit (e19f)."""
    STRIDE = 8
    rows = load("e18/queries.jsonl")
    bands = [(0.35, 0.50), (0.50, 0.70), (0.70, 0.90), (0.90, 1.01)]
    hist = {"exact": [0] * 4, "sketch": [0] * 4}
    ms = {"exact": [], "sketch": []}
    for r in rows:
        a = hist[r["kind"]]
        for i in range(4):
            a[i] += r["hist"][i]
        ms[r["kind"]].append(r["ms"])
    p50 = {k: float(np.percentile(v, 50)) for k, v in ms.items()}

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(6.8, 2.7))
    x = np.arange(4)
    w = 0.38
    for i, (kind, c, lab) in enumerate(
            [("exact", "#1f5fb4", "exact channel"),
             ("sketch", "#c0392b", "interval-sketch channel")]):
        y = [h * STRIDE for h in hist[kind]]
        ax.bar(x + (i - 0.5) * w, y, w, color=c, label=lab)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"[{lo:.2f},{hi:.2f})" for lo, hi in bands],
                       fontsize=6.5)
    ax.set_xlabel("relative containment score")
    ax.set_ylabel("candidate pairs (log)")
    ax.set_title("(a) all-pairs census, 174,300 pieces", fontsize=8)
    ax.legend(fontsize=7)
    ax.grid(True, axis="y", lw=0.3, alpha=0.4)

    summ = json.loads(
        (ROOT / "runs/e19/e18_pairs/summary.json").read_text())
    strata = [("exact_band2", "exact, rel 0.70-0.90"),
              ("exact_band3", "exact, rel >= 0.90"),
              ("sketch_band3", "sketch, rel >= 0.90")]
    y = [summ["per_stratum"][k]["precision"] * 100 for k, _ in strata]
    lo = [summ["per_stratum"][k]["lo"] * 100 for k, _ in strata]
    hi = [summ["per_stratum"][k]["hi"] * 100 for k, _ in strata]
    ax2.bar(range(3), y, 0.5,
            color=["#4a7ebb", "#1f3f73", "#b04a3a"],
            yerr=[np.array(y) - np.array(lo),
                  np.array(hi) - np.array(y)],
            capsize=3, error_kw=dict(lw=0.9))
    for i, (k, _) in enumerate(strata):
        n = summ["per_stratum"][k]["n"]
        ax2.text(i, hi[i] + 2, f"n={n}", ha="center", fontsize=6.5)
    ax2.set_xticks(range(3))
    ax2.set_xticklabels([s[1] for s in strata], fontsize=6.5, rotation=12)
    ax2.set_ylabel("precision of channel (%)")
    ax2.set_ylim(0, 108)
    ax2.set_title("(b) confirmed-copy precision, stratified audit",
                  fontsize=8)
    ax2.grid(True, axis="y", lw=0.3, alpha=0.4)
    for ax_ in (ax, ax2):
        ax_.tick_params(labelsize=7)
    fig.tight_layout()
    save(fig, "fig8_census")


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
    # scale to the data so variation is visible (previous fixed 75-100
    # window rendered the whole matrix green); perfect cells stay green,
    # degrading cells shift through yellow to red
    vmin = max(0.0, float(np.floor(M.min() / 5.0) * 5.0) - 5.0)
    im = ax.imshow(M, cmap="RdYlGn", vmin=vmin, vmax=100, aspect="auto")
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
            if M[i, j] < 95:  # box the materially-degraded cells
                ax.add_patch(plt.Rectangle(
                    (j - 0.5, i - 0.5), 1, 1, fill=False,
                    edgecolor="#7f0000", lw=1.2))
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


# ---------------------------------------------------------------- fig 10
def fig_e20_lsh() -> None:
    """Containment-versus-Jaccard geometry: (a) donor Jaccard histogram
    with the LSH operating thresholds; (b) recall of the three band
    configurations versus the tolerant screen on the same 337 cells."""
    rows = load("e20/matrix.jsonl")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.1))

    dj = [r["donor_jaccard"] for r in rows if r.get("rpb", 8) == 8]
    ax = axes[0]
    ax.hist(dj, bins=np.linspace(0, 1, 51), color="#1f5fb4", alpha=0.75,
            edgecolor="white", lw=0.3)
    ax.axvline(0.10, color="#c0392b", ls="--", lw=1.2)
    ax.text(0.105, ax.get_ylim()[1] * 0.93, "tau = 0.10",
            fontsize=7.5, color="#c0392b")
    ax.axvline(0.05, color="#e67e22", ls=":", lw=1.2)
    ax.text(0.055, ax.get_ylim()[1] * 0.80, "tau = 0.05",
            fontsize=7.5, color="#e67e22")
    ax.set_xlabel("donor set-Jaccard (337 planted cells)", fontsize=8)
    ax.set_ylabel("cells", fontsize=8)
    ax.set_title("(a) a contained span scores Jaccard ~0.1 at best",
                 fontsize=8.5)
    ax.grid(True, lw=0.3, alpha=0.4)

    ax = axes[1]
    cfgs = [("16x8 bands, tau=0.10", 8, 0.10),
            ("2x64 bands, tau=0.10", 2, 0.10),
            ("1x128 bands, tau=0.05", 1, 0.05)]
    labels, hits, dics = [], [], []
    for lab, rpb, tau in cfgs:
        sub = [r for r in rows
               if r.get("rpb", 8) == rpb and r["tau"] == tau]
        labels.append(lab)
        hits.append(sum(r["hit"] for r in sub) / len(sub) * 100)
        dics.append(sum(r["donor_in_cands"] for r in sub)
                    / len(sub) * 100)
    x = np.arange(len(labels))
    ax.bar(x - 0.2, dics, width=0.38, color="#7f8c8d",
           label="donor in candidate set")
    ax.bar(x + 0.2, hits, width=0.38, color="#8e44ad",
           label="donor confirmed (Jaccard >= tau)")
    ax.axhline(99.1, color="#1f5fb4", ls="--", lw=1.2)
    ax.text(2.45, 96, "tolerant screen:\n334/337 = 99.1%",
            fontsize=7, color="#1f5fb4", ha="right", va="top")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("% of 337 cells", fontsize=8)
    ax.set_ylim(0, 112)
    ax.set_title("(b) band tuning trades starvation for flooding",
                 fontsize=8.5)
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(True, lw=0.3, alpha=0.4)
    ax.tick_params(labelsize=7)
    save(fig, "fig_e20_lsh")


# ---------------------------------------------------------------- fig 14
def fig_e21_memorization() -> None:
    """Trained-generator memorization audit (E6.4): (a) loss curves;
    (b) sampling calibration vs per-piece likelihood; (c) cascade
    confirmation/attribution vs E6.2 anchors."""
    log = load("e21/train_log.jsonl")
    cal = load("e21/calibration.jsonl")
    mem = load("e21/memorization.jsonl")
    e62 = load("e62/memorization.jsonl")
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.1))

    ax = axes[0]
    ep = [r["epoch"] for r in log]
    ax.plot(ep, [r["train_loss"] for r in log], "-", lw=1,
            color="#1f5fb4", label="train (250 pieces)")
    ax.plot(ep, [r["val_loss"] for r in log], "-", lw=1,
            color="#c0392b", label="held-out (50 pieces)")
    ax.set_xlabel("epoch", fontsize=8)
    ax.set_ylabel("4-field next-event loss (nats)", fontsize=8)
    ax.set_title("(a) overfitting is real: the gap is memorization",
                 fontsize=8.5)
    ax.legend(fontsize=7)
    ax.grid(True, lw=0.3, alpha=0.4)

    ax = axes[1]
    style = {"trained": ("o", "#1f5fb4"), "untrained": ("x", "#c0392b")}
    for split, (mk, c) in style.items():
        sub = [r for r in cal if r["split"] == split]
        ax.plot([r["loss"] for r in sub],
                [r["pos_pitch_acc"] * 100 for r in sub], mk, ms=4,
                color=c, label=f"{split} source")
    ax.set_xlabel("per-piece held likelihood (nats)", fontsize=8)
    ax.set_ylabel("position-wise pitch agreement (%)", fontsize=8)
    ax.set_title("(b) memorized is not regurgitated", fontsize=8.5)
    ax.legend(fontsize=7)
    ax.grid(True, lw=0.3, alpha=0.4)

    ax = axes[2]
    l0 = [r for r in e62 if r["cell"] == "m8_l0.0"]
    l1 = [r for r in e62 if r["cell"] == "m8_l1.0"]
    labels = ["E6.2\nlambda=0", "E6.2\nlambda=1", "E6.4\nmemorized",
              "E6.4\ncontrol", "E6.4\nrandom"]
    det = [np.mean([r["confirmed"] for r in l0]) * 100,
           np.mean([r["confirmed"] for r in l1]) * 100]
    src = [np.mean([r["is_source"] for r in l0]) * 100,
           np.mean([r["is_source"] for r in l1]) * 100]
    for grp in ("memorized", "control", "random_trained"):
        sub = [r for r in mem if r["group"] == grp]
        det.append(np.mean([r["confirmed"] for r in sub]) * 100)
        src.append(np.mean([r["is_source"] for r in sub]) * 100)
    x = np.arange(len(labels))
    ax.bar(x - 0.2, det, width=0.38, color="#7f8c8d", label="confirmed")
    ax.bar(x + 0.2, src, width=0.38, color="#8e44ad",
           label="source-attributed")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_ylabel("% of samples", fontsize=8)
    ax.set_title("(c) detector view: the lambda = 0 band", fontsize=8.5)
    ax.legend(fontsize=7)
    ax.grid(True, lw=0.3, alpha=0.4)

    for ax in axes:
        ax.tick_params(labelsize=7)
    save(fig, "fig_e21_memorization")


ALL = {n: f for n, f in list(globals().items()) if n.startswith("fig")}
if __name__ == "__main__":
    which = sys.argv[1:] or list(ALL)
    for name in which:
        print(f"[{name}]", flush=True)
        ALL[name]()
    print("done ->", FIGDIR)
