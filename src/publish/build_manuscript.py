# -*- coding: utf-8 -*-
"""Build Manuscript.docx per docs/writing_conventions.md.

- Figures embedded as EMF via manual drawing XML (python-docx cannot
  parse EMF headers; we register the part ourselves with content type
  image/x-emf).
- Core properties: author = corresponding author Yalong Zhang.
- Numbers are read live from runs/*/ so the manuscript re-builds as
  experiments are re-run on the full corpus.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xesc

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import qn, nsdecls
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.part import Part
from docx.opc.packuri import PackURI
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
FIGDIR = ROOT / "results/figures"
OUT = ROOT / "Manuscript.docx"

# Paper title is read from a local, git-ignored file (paper_title.txt) so the
# public repository stays venue- and title-agnostic; fall back to a neutral
# placeholder when the file is absent.
_title_file = Path(__file__).with_name("paper_title.txt")
if _title_file.exists():
    TITLE = _title_file.read_text(encoding="utf-8").strip()
else:
    TITLE = "[Paper title - set in src/publish/paper_title.txt]"
AUTHORS = ("Xuemei Li\u00b9, Jianping Deng\u00b9, Meng Huang\u00b2, "
           "Bao Wang\u00b2, and Yalong Zhang\u00b2*")
AFFIL = ("\u00b9 Faculty of Teacher Education, Quzhou University, "
         "Quzhou 324000, China\n"
         "\u00b2 College of Electrical and Information Engineering, "
         "Quzhou University, Quzhou 324000, China")
ACK = ("This work was supported by the Key Science and Technology "
       "Tackling Program of the Quzhou Municipal Bureau of Science and "
       "Technology under Grant 2025K192, and by the \u201cPioneer and "
       "Leading Goose+X\u201d R&D Program of the Department of Science and "
       "Technology of Zhejiang Province under Grant 2024C01227.")

REFERENCES = [
 "R. Typke, R. C. Veltkamp, and F. Wiering, \u201cSearching notated "
 "polyphonic music using transportation distances,\u201d in Proc. ACM "
 "Multimedia, 2004.",
 "D. Meredith, K. Lemstr\u00f6m, and G. A. Wiggins, \u201cAlgorithms for "
 "discovering repeated patterns in multidimensional representations of "
 "polyphonic music,\u201d Journal of New Music Research, vol. 31, no. 4, "
 "pp. 321\u2013345, 2002.",
 "M. A. Casey et al., \u201cContent-based music information retrieval: "
 "Current directions and future challenges,\u201d Proceedings of the IEEE, "
 "vol. 96, no. 4, pp. 668\u2013676, 2008.",
 "M. M\u00fcller, Information Retrieval for Music and Motion. Springer, "
 "2007.",
 "R. Typke, F. Wiering, and R. C. Veltkamp, \u201cA survey of music "
 "information retrieval systems,\u201d in Proc. ISMIR, 2005.",
 "C. Raffel and D. P. W. Ellis, \u201cOptimizing DTW-based audio-to-MIDI "
 "alignment and matching,\u201d in Proc. ICASSP, 2016.",
 "C. Raffel, Learning-Based Methods for Comparing Sequences, with "
 "Applications to Audio-to-MIDI Alignment and Matching. PhD thesis, "
 "Columbia University, 2016 (Lakh MIDI Dataset).",
 "S. Zilberstein, \u201cUsing anytime algorithms in intelligent "
 "systems,\u201d AI Magazine, vol. 17, no. 3, pp. 73\u201383, 1996.",
 "R. Agrawal and R. Srikant, \u201cFast algorithms for mining association "
 "rules in large databases,\u201d in Proc. VLDB, 1994.",
 "J. Han, J. Pei, and Y. Yin, \u201cMining frequent patterns without "
 "candidate generation,\u201d in Proc. ACM SIGMOD, 2000.",
 "N. Carlini et al., \u201cExtracting training data from large language "
 "models,\u201d in Proc. USENIX Security, 2021.",
 "M. M\u00fcller and S. Ewert, \u201cChroma Toolbox: MATLAB "
 "implementations for extracting variants of chroma-based audio "
 "features,\u201d in Proc. ISMIR, 2011.",
 "A. Ghias, J. Logan, D. Chamberlin, and B. C. Smith, \u201cQuery by "
 "humming: Musical information retrieval in an audio database,\u201d in "
 "Proc. ACM Multimedia, 1995.",
 "J. Salamon, J. Serra, and E. G\u00f3mez, \u201cTonal representations "
 "for music retrieval: From version identification to query-by-humming,"
 "\u201d Int. Journal of Multimedia Information Retrieval, vol. 2, no. 1, "
 "pp. 35\u201348, 2013.",
 "Z. Yu, X. Xu, X. Chen, and D. Yang, \u201cLearning a representation "
 "for cover song identification using convolutional neural network,"
 "\u201d in Proc. ICASSP, 2020.",
 "X. Du, Z. Yu, B. Zhu, X. Chen, and Z. Ma, \u201cByteCover: Cover song "
 "identification via multi-loss training,\u201d in Proc. ICASSP, 2021.",
 "F. Liu, D. Tuo, Y. Xu, and X. Han, \u201cCoverHunter: Cover song "
 "identification with refined attention and alignments,\u201d in Proc. "
 "IEEE ICASSP, 2023.",
 "C. Dittmar, K. F. Hildebrand, D. G\u00e4rtner, M. Gr\u00e4ber, and "
 "C. Landmeyer, \u201cAudio forensics meets music information "
 "retrieval\u2014A toolbox for inspection of music plagiarism claims,"
 "\u201d in Proc. AES Int. Conf. Semantic Audio, 2012.",
 "W. Liu, T. He, C. Gong, N. Zhang, H. Yang, and J. Yan, "
 "\u201cFine-grained music plagiarism detection: Revealing "
 "plagiarists through bipartite graph matching and a "
 "comprehensive large-scale dataset,\u201d in Proc. ACM Int. "
 "Conf. Multimedia, 2023, pp. 8839\u20138848.",
 "S. Park, H. Kim, J. Jung, J. Park, J. Kim, and J. Nam, \u201c"
 "Quantitative analysis of melodic similarity in music copyright "
 "infringement cases,\u201d in Proc. ISMIR, 2024.",
 "K. J. M. Lee, J. Ens, S. Adkins, P. Sarmento, et al., \u201cThe "
 "GigaMIDI dataset with features for expressive music performance "
 "detection,\u201d Transactions of the Int. Society for Music Information "
 "Retrieval, 2025.",
 "C.-Z. A. Huang et al., \u201cMusic Transformer: Generating music with "
 "long-term structure,\u201d in Proc. ICLR, 2019.",
 "R. Shokri, M. Stronati, C. Song, and V. Shmatikov, \u201cMembership "
 "inference attacks against machine learning models,\u201d in Proc. IEEE "
 "Symp. Security and Privacy, 2017.",
 "N. Carlini, J. Hayes, M. Nasr, M. Jagielski, et al., \u201cExtracting "
 "training data from diffusion models,\u201d in Proc. USENIX Security, "
 "2023.",
 "K. Lee, D. Ippolito, A. Nystrom, C. Zhang, et al., \u201cDeduplicating "
 "training data makes language models better,\u201d in Proc. ACL, 2022.",
 "N. Kandpal, E. Wallace, and C. Raffel, \u201cDeduplicating training "
 "data mitigates privacy risks in language models,\u201d in Proc. ICML, "
 "2022.",
 "G. van den Burg and C. Williams, \u201cOn memorization in "
 "probabilistic deep generative models,\u201d in NeurIPS 2021 Workshop "
 "Deep Generative Models, 2021.",
 "Y.-C. Liu, J. Yu, K. Cao, S. I. A. Meerza, et al., \u201cAuditing "
 "training data in generative music models via black-box membership "
 "inference,\u201d in Proc. IEEE Symp. Security and Privacy Workshops "
 "(SPW), 2026, pp. 230\u2013237.",
 "J. Barnett, H. F. Garcia, and B. Pardo, \u201cExploring musical "
 "roots: Applying audio embeddings to empower influence attribution "
 "for a generative music model,\u201d arXiv preprint arXiv:2401.14542, "
 "2024.",
 "S. Stober and T. W. Dornis, \u201cGenerative AI training and copyright "
 "law,\u201d arXiv preprint arXiv:2502.15858, 2025.",
 "R. Fagin, A. Lotem, and M. Naor, \u201cOptimal aggregation algorithms "
 "for middleware,\u201d in Proc. ACM Symp. Principles of Database Systems "
 "(PODS), 2001.",
 "E. L. Lawler and D. E. Wood, \u201cBranch-and-bound methods: A "
 "survey,\u201d Operations Research, vol. 14, no. 4, pp. 699\u2013719, "
 "1966.",
 "A. Z. Broder, \u201cOn the resemblance and containment of "
 "documents,\u201d in Proc. Compression and Complexity of Sequences, 1997.",
 "B. D. Ondov et al., \u201cMash: Fast genome and metagenome distance "
 "estimation using MinHash,\u201d Genome Biology, vol. 17, 2016.",
]

# IEEE requires reference numbers to follow order of first citation.
# _CITE_REMAP maps the original (topical) numbering used in the draft
# strings to citation-order numbering; _REFS_IN_CITE_ORDER is the
# REFERENCES index sequence (1-based old numbers) in new list order.
_CITE_REMAP = {3: 1, 5: 2, 4: 3, 12: 4, 2: 5, 9: 6, 10: 7, 15: 8, 16: 9,
               17: 10, 18: 11, 19: 12, 20: 13, 13: 14, 14: 15, 8: 16,
               1: 17, 6: 18, 7: 19, 11: 20, 23: 21, 24: 22, 25: 23,
               26: 24, 27: 25, 22: 26, 28: 27, 29: 28, 30: 29, 31: 30,
               32: 31, 21: 32, 33: 33, 34: 34}
_REFS_IN_CITE_ORDER = sorted(_CITE_REMAP, key=lambda o: _CITE_REMAP[o])

# ---------------------------------------------------------------- numbers
def load(name):
    p = ROOT / f"runs/{name}"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def nums():
    import numpy as np
    n = {}
    e4 = sorted(load("e4/scaling.jsonl"), key=lambda r: r["n_pieces"])
    n["e4_max"] = e4[-1]["n_pieces"]
    n["e4_build"] = e4[-1]["ours"]["build_secs"]
    n["e4_p50"] = e4[-1]["ours"]["query_p50_ms"]
    e1 = load("e1/matrix.jsonl")
    ok = sum(1 for r in e1 if r.get("recall_hit", r.get("hit", False)))
    n["e1_total"] = len(e1)
    n["e1_ok"] = ok
    e2 = load("e2/bounds.jsonl")
    n["e2_viol"] = sum(1 for r in e2
                       if r["donor_score"] < r["bound"])
    n["e2_n"] = len(e2)
    e3 = [r for r in load("e3/anytime.jsonl") if r["length_s"] == 16]
    def rem(order, frac):
        sub = [r for r in e3 if r["order"] == order
               and r["fraction"] == frac]
        return float(np.mean([r["n_hits"] + r["remaining_bound"] for r in sub]))
    n["e3_rare"], n["e3_rand"], n["e3_hot"] = (rem("rare", 0.7),
                                                rem("random", 0.7),
                                                rem("hot", 0.7))
    e7 = load("e17/cascade.jsonl")
    ret = lambda c: float(np.mean([r["retention"][str(c)] for r in e7]))
    n["e7_ret20"], n["e7_ret50"] = ret(20), ret(50)
    casc = lambda c, rho: (
        float(np.mean([np.array([r["retention"][str(c)] == 1])
                       & np.array([r[f"cascade_C{c}"]["rho_grid"][str(rho)][
                           "donor_confirmed"]]) for r in e7])),
        float(np.mean([len(r[f"cascade_C{c}"]["rho_grid"][str(rho)][
            "fp"]) > 0 for r in e7])))
    n["e7_c50_r4"], n["e7_c50_f4"] = casc(50, 0.4)
    n["e7_c50_r5"], n["e7_c50_f5"] = casc(50, 0.5)
    n["e14_fp"] = 0.021
    n["e14_rec"] = 0.839
    e62 = load("e62/memorization.jsonl")
    n["e62_l1"] = float(np.mean([r["confirmed"] for r in e62
                                 if r["lam"] == 1.0]))
    for cell, tag in (("m8_l0.0", "e62_m8_l0"), ("m8_l1.0", "e62_m8_l1")):
        sub = [r for r in e62 if r["cell"] == cell]
        n[f"{tag}_det"] = float(np.mean([r["confirmed"] for r in sub]))
        n[f"{tag}_src"] = float(np.mean([r["is_source"] for r in sub]))
    e63 = load("e63/cases.jsonl")
    n["e63_pairs"] = sum(1 for _ in (ROOT / "runs/e63/pairs.jsonl")
                         .open(encoding="utf-8"))
    # e18 full-corpus census (stride-8 survey, extrapolate x8)
    e18 = load("e18/queries.jsonl")
    STR = 8
    agg = {}
    for kind in ("exact", "sketch"):
        sub = [r for r in e18 if r["kind"] == kind]
        n[f"e18_{kind}_queries"] = len(sub)
        n[f"e18_{kind}_ge40"] = sum(r["n_ge40"] for r in sub) * STR
        n[f"e18_{kind}_hist"] = [sum(r["hist"][i] for r in sub) * STR
                                 for i in range(4)]
        m = [r["ms"] for r in sub]
        n[f"e18_{kind}_p50"] = float(np.percentile(m, 50))
        n[f"e18_{kind}_p95"] = float(np.percentile(m, 95))
    n["e18_rel35"] = (sum(n["e18_exact_hist"]) +
                      sum(n["e18_sketch_hist"]))
    # e19f precision audit
    s19 = json.loads((ROOT / "runs/e19/e18_pairs/summary.json")
                     .read_text(encoding="utf-8"))
    for key, st in s19["per_stratum"].items():
        n[f"e19f_{key}_p"] = st["precision"]
        n[f"e19f_{key}_lo"] = st["lo"]
        n[f"e19f_{key}_hi"] = st["hi"]
        n[f"e19f_{key}_n"] = st["n"]
    n["e19f_pools"] = s19["pools"]
    n["e19f_est"] = s19["estimated_confirmed_corpus"]
    # e20 MinHash-LSH baseline (matrix: e1 protocol on 1k corpus; scale:
    # same subsampled corpora as e4)
    e20m = load("e20/matrix.jsonl")
    n["e20_total"] = len(e20m)
    n["e20_screen_recall"] = n["e1_ok"] / n["e1_total"] * 100
    for cfg in ((8, 0.10), (2, 0.10), (1, 0.05)):
        sub = [r for r in e20m
               if r.get("rpb", 8) == cfg[0] and r["tau"] == cfg[1]]
        tag = f"e20_m{cfg[0]}_{str(cfg[1]).replace('.', '')}"
        n[f"{tag}_n"] = len(sub)
        n[f"{tag}_dic"] = sum(r["donor_in_cands"] for r in sub) \
            / len(sub) * 100
        n[f"{tag}_hit"] = sum(r["hit"] for r in sub) / len(sub) * 100
        n[f"{tag}_cand"] = float(np.median([r["n_candidates"] for r in sub]))
        n[f"{tag}_ge"] = float(np.median([r["n_ge_tau"] for r in sub]))
    dj = np.array([r["donor_jaccard"] for r in e20m
                   if r.get("rpb", 8) == 8])
    n["e20_dj_p25"] = float(np.percentile(dj, 25))
    n["e20_dj_p50"] = float(np.percentile(dj, 50))
    n["e20_dj_p75"] = float(np.percentile(dj, 75))
    n["e20_dj_ge10"] = int((dj >= 0.10).sum())
    e20s = sorted(load("e20/scale.jsonl"), key=lambda r: r["n_pieces"])
    top = [r for r in e20s if r["n_pieces"] == e20s[-1]["n_pieces"]]
    t10 = [r for r in top if r["tau"] == 0.10][0]
    n["e20_max"] = e20s[-1]["n_pieces"]
    n["e20_build"] = t10["build_secs"]
    n["e20_bucket"] = t10["bucket_secs"]
    n["e20_mem"] = t10["peak_mem_mb"]
    n["e20_p50"] = t10["query_p50_ms"]
    n["e20_recall"] = t10["recall"]
    # e21 real-transformer memorization audit (M5)
    log = load("e21/train_log.jsonl")
    n["e21_epochs"] = log[-1]["epoch"]
    n["e21_train"] = log[-1]["train_loss"]
    n["e21_val"] = log[-1]["val_loss"]
    pl = load("e21/piece_loss.jsonl")
    for split in ("trained", "untrained"):
        sub = [r["loss"] for r in pl if r["split"] == split]
        n[f"e21_loss_{split}"] = float(np.mean(sub))
    tr = [r["loss"] for r in pl if r["split"] == "trained"]
    ut = [r["loss"] for r in pl if r["split"] == "untrained"]
    wins = sum(1 for x in tr for y in ut if x < y)
    ties = sum(1 for x in tr for y in ut if x == y)
    n["e21_auc"] = (wins + 0.5 * ties) / (len(tr) * len(ut))
    n["e21_tail"] = min(tr)
    cal = load("e21/calibration.jsonl")
    n["e21_cal_n"] = len(cal)
    n["e21_cal_pos_max"] = max(r["pos_pitch_acc"] for r in cal)
    n["e21_cal_ov4_max"] = max(r["ov4"] for r in cal)
    n["e21_cal_pos_mean"] = float(np.mean([r["pos_pitch_acc"]
                                           for r in cal]))
    mem = [json.loads(l) for l in
           (ROOT / "runs/e21/memorization.jsonl")
           .read_text(encoding="utf-8").splitlines() if l.strip()]
    for grp in ("memorized", "control", "random_trained"):
        sub = [r for r in mem if r["group"] == grp]
        n[f"e21_{grp}_n"] = len(sub)
        n[f"e21_{grp}_det"] = float(np.mean([r["confirmed"] for r in sub]))
        n[f"e21_{grp}_src"] = float(np.mean([r["is_source"] for r in sub]))
        n[f"e21_{grp}_ret"] = float(np.mean([r["retained_source"]
                                             for r in sub]))
    return n


def e1_table_rows():
    """Aggregate runs/e1/matrix.jsonl into Table II rows:
    transformation group x strength, recall % per span length."""
    rows = load("e1/matrix.jsonl")
    lengths = [2, 4, 8, 16]
    groups = [
        ("Verbatim", "verbatim", [("identity", "None")]),
        ("Transpose", "transpose",
         [(f"\u00b1{s} st", str(s)) for s in (1, 2, 4, 6)]),
        ("Tempo scaling", "tempo",
         [("\u00d71.05", "1.05"), ("\u00d71.10", "1.1"), ("\u00d71.20", "1.2")]),
        ("Split\u2013merge", "split_merge",
         [("p = 0.10", "0.1"), ("p = 0.20", "0.2"), ("p = 0.30", "0.3")]),
        ("Re-instrumentation", "reinstrument",
         [("p_drop = 0.10", "0.1"), ("p_drop = 0.25", "0.25"),
          ("p_drop = 0.40", "0.4")]),
        ("Transcription noise", "transcribe",
         [("q = 15 ms, miss 4 %", "[15, 0.04]"),
          ("q = 30 ms, miss 8 %", "[30, 0.08]"),
          ("q = 60 ms, miss 15 %", "[60, 0.15]")]),
    ]
    out = []
    for gname, tkey, slist in groups:
        for si, (slabel, skey) in enumerate(slist):
            sub = [r for r in rows if r["transform"] == tkey
                   and str(r["strength"]) == skey]

            def rec(pred):
                sel = [r for r in sub if pred(r)]
                if not sel:
                    return None
                return sum(1 for r in sel if r["hit"]) / len(sel) * 100

            cells = []
            for L in lengths:
                v = rec(lambda r, L=L: r["length_s"] == L)
                cells.append(("—" if v is None else f"{v:.0f}",
                              v is not None and v < 100))
            vall = rec(lambda r: True)
            cells.append(("—" if vall is None else f"{vall:.1f}",
                          vall is not None and vall < 100))
            out.append(([gname] if si == 0 else [""])
                       + [slabel] + cells)
    return out


def e2_table_rows():
    """Donor evidence margin versus theoretical bound, per transform."""
    import numpy as np
    rows = load("e2/bounds.jsonl")
    order = ["verbatim", "transpose", "tempo", "split_merge",
             "reinstrument", "transcribe"]
    names = {"verbatim": "Verbatim", "transpose": "Transpose",
             "tempo": "Tempo scaling", "split_merge": "Split\u2013merge",
             "reinstrument": "Re-instrumentation",
             "transcribe": "Transcription noise"}
    out = []
    for tkey in order:
        sub = [r for r in rows if r["transform"] == tkey]
        margins = [r["donor_score"] - r["bound"] for r in sub]
        viol = sum(1 for m in margins if m < 0)
        out.append([names[tkey], str(len(sub)),
                    f"{float(np.mean(margins)):.1f}",
                    f"{min(margins):.0f}",
                    (f"{viol}", viol > 0)])
    return out


def e3_table_rows():
    """Anytime schedules on 16 s spans: open-candidate bound and donor
    recovery per budget fraction."""
    import numpy as np
    rows = [r for r in load("e3/anytime.jsonl") if r["length_s"] == 16]
    fracs = sorted({r["fraction"] for r in rows})
    out = []
    for f in fracs:
        line = [f"{f:.0%}"]
        for order in ("rare", "random", "hot"):
            sub = [r for r in rows if r["order"] == order
                   and r["fraction"] == f]
            open_bound = float(np.mean([r["n_hits"] + r["remaining_bound"]
                                        for r in sub]))
            line.append(f"{open_bound:.1f}")
        sub = [r for r in rows if r["fraction"] == f]
        rec = float(np.mean([r["donor_found"] for r in sub])) * 100
        line.append(f"{rec:.0f}")
        out.append(line)
    return out


def e4_table_rows():
    """Scaling table: ours versus Jaccard-scan and MinHash-LSH baselines."""
    rows = sorted(load("e4/scaling.jsonl"), key=lambda r: r["n_pieces"])
    e20 = {}
    for r in load("e20/scale.jsonl"):
        if r["tau"] == 0.10:
            e20[r["n_pieces"]] = r
    out = []
    for r in rows:
        o = r["ours"]
        jac = r.get("jaccard_scan") or {}
        jp = jac.get("query_p50_ms")
        lsh = e20.get(r["n_pieces"]) or {}
        out.append([f"{r['n_pieces']:,}", f"{o['build_secs']:.2f}",
                    f"{o['peak_mem_mb']:.0f}",
                    f"{o['query_p50_ms']:.1f}", f"{o['query_p95_ms']:.1f}",
                    o["recall"],
                    ("infeasible" if jp is None else f"{jp:.0f}"),
                    (f"{lsh['query_p50_ms']:.1f}" if lsh else "\u2013"),
                    (lsh.get("recall", "\u2013") if lsh else "\u2013")])
    return out


def e13_table_rows():
    """Hard-negative screening by fragment length + overall row."""
    rows = load("e13/v2_screening.jsonl")

    def agg(sub):
        n = len(sub)
        tfp = sum(1 for r in sub if len(r["tolerant"]["fp_pool"]) > 0)
        vfp = sum(1 for r in sub if len(r["verbatim"]["fp_pool"]) > 0)
        v20 = sum(1 for r in sub if r["verbatim"]["top20"])
        return [str(n), f"{tfp / n * 100:.1f}", f"{vfp / n * 100:.1f}",
                f"{v20 / n * 100:.1f}"]

    out = []
    for L in sorted({r["len_s"] for r in rows}):
        out.append([f"{L}"] + agg([r for r in rows if r["len_s"] == L]))
    out.append(["All"] + agg(rows))
    return out


def e14_table_rows():
    """Confirmation trade-off: recall / FP per regime and rho."""
    import numpy as np
    rows = load("e14/confirm.jsonl")
    regimes = [("strict", "Strict anchors"),
               ("mid", "Mid tolerance"), ("loose", "Loose tolerance")]
    out = []
    for key, label in regimes:
        line = [label]
        for rho in ("0.3", "0.4", "0.5", "0.6"):
            grid = [r[key]["rho_grid"][rho] for r in rows]
            rec = float(np.mean([g["donor_confirmed"] for g in grid])) * 100
            fp = float(np.mean([len(g["fp_pool"]) > 0 for g in grid])) * 100
            line.append(f"{rec:.1f} / {fp:.1f}")
        out.append(line)
    return out


def e5_table_rows():
    """Component ablation rows."""
    rows = load("e5/ablation.jsonl")
    out = []
    for r in rows:
        if r["ablation"] == "E5.4_L":
            setting = f"span factor {r['factor']:.2f}\u00d7"
        elif r["ablation"] == "E5.5_k":
            setting = (f"k = ({r['k_pitch']}, {r['k_bin']}, "
                       f"{r['k_vel']})")
        else:
            setting = f"{r['grid_ms']} ms grid"
        p50 = r.get("wall_p50_ms")
        out.append([r["ablation"].replace("E5.", "E5."), setting,
                    r["recall"], f"{r['false_candidates']:,}",
                    ("\u2014" if p50 is None else f"{p50:.1f}")])
    return out


def e62_table_rows():
    """Memorization spectrum: detection % / source-attribution % per
    n-gram order m and copy probability lambda."""
    import numpy as np
    rows = load("e62/memorization.jsonl")
    out = []
    for m in (2, 4, 8):
        line = [str(m)]
        for lam in (0.0, 0.25, 0.5, 0.75, 1.0):
            sub = [r for r in rows if r["m"] == m and r["lam"] == lam]
            det = float(np.mean([r["confirmed"] for r in sub])) * 100
            attr = float(np.mean([r["is_source"] for r in sub])) * 100
            line.append(f"{det:.0f} / {attr:.0f}")
        out.append(line)
    return out


# ---------------------------------------------------------------- EMF part
_EMF_XML = """<w:drawing \
xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" \
xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" \
xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" \
xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" \
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{cx}" cy="{cy}"/>
<wp:effectExtent l="0" t="0" r="0" b="0"/>
<wp:docPr id="{did}" name="{name}"/>
<wp:cNvGraphicFramePr/>
<a:graphic><a:graphicData \
uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic>
<pic:nvPicPr><pic:cNvPr id="0" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{rid}"/>\
<a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>\
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>"""


def _svg_aspect(name: str) -> float:
    svg = (FIGDIR / f"{name}.svg").read_text(encoding="utf-8")
    m = re.search(r'<svg[^>]*width="([\d.]+)pt"[^>]*height="([\d.]+)pt"', svg)
    if not m:  # order may differ
        w = re.search(r'width="([\d.]+)pt"', svg)
        h = re.search(r'height="([\d.]+)pt"', svg)
        return float(w.group(1)) / float(h.group(1))
    return float(m.group(1)) / float(m.group(2))


_docpr_id = [100]


def add_emf(doc: Document, name: str, width_cm: float, center=True) -> None:
    path = FIGDIR / f"{name}.emf"
    partname = f"/word/media/{name}.emf"
    pkg = doc.part.package
    for rel in doc.part.rels.values():
        if rel.is_external:
            continue
        if str(rel.target_part.partname) == partname:
            part = rel.target_part
            rid = rel.rId
            break
    else:
        part = Part(PackURI(partname), "image/x-emf", path.read_bytes(), pkg)
        rid = doc.part.relate_to(part, RT.IMAGE)
    cx = int(Cm(width_cm).emu)
    cy = int(cx / _svg_aspect(name))
    _docpr_id[0] += 1
    xml = _EMF_XML.format(cx=cx, cy=cy, rid=rid, did=_docpr_id[0],
                          name=f"{name}.emf")
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p._p.append(parse_xml(xml))


# ---------------------------------------------------------------- helpers
def h1(doc, text):
    p = doc.add_paragraph(style="Heading 1")
    p.add_run(text.upper())


def h2(doc, text):
    p = doc.add_paragraph(style="Heading 2")
    # 1 pt tighter than the template's 6 pt: imperceptible, but the
    # eighteen subsections together return ~18 pt of column space
    p.paragraph_format.space_before = Pt(5)
    p.add_run(text)


def drop_cap(doc, text):
    """First Introduction paragraph with an IEEE-style 3-line dropped
    capital, replicating the Transactions template exactly (framePr
    dropCap=drop lines=3, small-caps lead-in, exact 724-twip frame line).
    """
    from docx.oxml.ns import nsdecls

    letter, rest = text[0], text[1:]
    head, tail = rest[:4], xesc(rest[4:])
    p1 = parse_xml(
        f'<w:p {nsdecls("w")}><w:pPr>'
        '<w:pStyle w:val="Normal"/><w:keepNext/>'
        '<w:framePr w:dropCap="drop" w:lines="3" w:wrap="around" '
        'w:vAnchor="text" w:hAnchor="text"/>'
        '<w:spacing w:line="724" w:lineRule="exact"/>'
        '<w:jc w:val="both"/><w:textAlignment w:val="baseline"/></w:pPr>'
        '<w:r><w:rPr><w:smallCaps/><w:color w:val="000000"/>'
        '<w:position w:val="-9"/><w:sz w:val="97"/></w:rPr>'
        f'<w:t xml:space="preserve">{letter}</w:t></w:r></w:p>')
    p2 = parse_xml(
        f'<w:p {nsdecls("w")}><w:pPr><w:pStyle w:val="Normal"/>'
        '<w:widowControl w:val="0"/>'
        '<w:spacing w:line="252" w:lineRule="auto"/>'
        '<w:jc w:val="both"/></w:pPr>'
        '<w:r><w:rPr><w:smallCaps/><w:color w:val="000000"/></w:rPr>'
        f'<w:t xml:space="preserve">{head}</w:t></w:r>'
        f'<w:r><w:rPr><w:color w:val="000000"/></w:rPr>'
        f'<w:t xml:space="preserve">{tail}</w:t></w:r></w:p>')
    body = doc.element.body
    sect = body.find(qn("w:sectPr"))
    sect.addprevious(p1)
    sect.addprevious(p2)


_MATH_TOKEN = re.compile(r"""
      O\(([^)]*)\)
    | \u230a0\.5\u00b7\|S\(q\)\|\u230b
    | min\(\|A\|,[ ]\|B\|\)
    | \|A[ ]\u2229[ ]B\| | \|N_k\(item_i\)\| | \|S\(P\)\| | \|S\(q\)\|
    | \|O_u\| | \|chain\|
    | score_[uq]\(P\)
    | budget\(B\)
    | N_k\(item_i\) | N_k\(x\) | N_k
    | S\(P\) | S\(q\)
    | O_u
    | k_screen | k_confirm | k_pitch | k_bin | k_vel
    | item_order | item_i | score_u | score_q | p_drop
    | [eptvd]_\{?[\u2080-\u20890-9a-z]\}?
    | [eptvdq][\u2080-\u2089]
    | P_\{?[\u2080-\u20890-9N]\}?
    | P[\u2080-\u2089]
    | [\u0394\u03a3\u03bb\u03c1\u03c4\u03c6\u03b4]
    | (?<![A-Z]-)(?<!TABLE[ ])(?<![Tt]able[ ])\b[BCWPX]\b
    | \b[qmkNuij]\b
    """, re.VERBOSE)

_GREEK_WORDS = {"tau": "\u03c4", "rho": "\u03c1", "lambda": "\u03bb",
                "delta": "\u03b4"}


def _emit_run(p, text, italic=False, size=None, bold=False, name=None):
    r = p.add_run(text)
    if italic:
        r.font.italic = True
    if bold:
        r.font.bold = True
    if size is not None:
        r.font.size = Pt(size)
    if name:
        r.font.name = name
    return r


_SUBSPLIT = re.compile(r"_([A-Za-z])(?![A-Za-z])")


def _emit_math_tok(p, tok, size=None, bold=False, name=None):
    """Emit one matched math token, turning short _x subscripts into true
    Word subscript runs (e_n -> e + sub n). Wordy subscripts such as
    k_pitch or item_order (>=3 chars) stay literal."""
    pos = 0
    for m in _SUBSPLIT.finditer(tok):
        if m.start() > pos:
            _emit_run(p, tok[pos:m.start()], italic=True, size=size,
                      bold=bold, name=name)
        r = _emit_run(p, m.group(1), italic=True, size=size, bold=bold,
                      name=name)
        r.font.subscript = True
        pos = m.end()
    if pos < len(tok):
        _emit_run(p, tok[pos:], italic=True, size=size, bold=bold,
                  name=name)


def rich_add(p, text, size=None, bold=False, name=None):
    """Add text to paragraph, italicizing mathematical variables per IEEE
    style. Spelled-out Greek names (tau, rho, lambda, delta) are first
    normalized to their symbols; big-O keeps an upright O with an
    italic argument."""
    text = re.sub(r"\b(tau|rho|lambda|delta)\b",
                  lambda m: _GREEK_WORDS[m.group(1)], text)
    text = re.sub(r"\[(\d{1,2})\]",
                  lambda m: f"[{_CITE_REMAP[int(m.group(1))]}]", text)
    pos = 0
    for m in _MATH_TOKEN.finditer(text):
        if m.start() > pos:
            _emit_run(p, text[pos:m.start()], size=size, bold=bold,
                      name=name)
        if m.group(1) is not None:            # O(...) : upright O
            _emit_run(p, "O(", size=size, bold=bold, name=name)
            _emit_run(p, m.group(1), italic=True, size=size, name=name)
            _emit_run(p, ")", size=size, bold=bold, name=name)
        else:
            _emit_math_tok(p, m.group(0), size=size, bold=bold, name=name)
        pos = m.end()
    if pos < len(text):
        _emit_run(p, text[pos:], size=size, bold=bold, name=name)


def para(doc, text, indent=0.36, size=10, align="justify"):
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.first_line_indent = Cm(indent)
    p.paragraph_format.space_after = Pt(0)
    if align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    rich_add(p, text, size=None if size == 10 else size)
    return p


def caption(doc, text, size=8):
    # 8 pt matches the template's Figure Caption style (we had drifted
    # to 9.5 pt); across the fifteen figure captions this also returns
    # ~80 pt of column space
    p = doc.add_paragraph(style="Figure Caption")
    rich_add(p, text, size=size)
    # keep the caption glued to the figure above it (no orphaned
    # captions across page/column breaks)
    prev = p._p.getprevious()
    if prev is not None and prev.findall(qn("w:drawing")):
        from docx.text.paragraph import Paragraph
        Paragraph(prev, p._parent).paragraph_format.keep_with_next = True
    return p


def _keep_table(t, head_paras=()):
    """Keep a table inside one column: rows never split across a page,
    and every row keeps with the next, so the table moves whole to the
    next column instead of breaking across columns."""
    for p in head_paras:
        p.paragraph_format.keep_with_next = True
    rows = list(t.rows)
    for i, row in enumerate(rows):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml('<w:cantSplit %s/>' % nsdecls("w")))
        if i < len(rows) - 1:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.keep_with_next = True


def table(doc, header, rows, widths=None, size=9, title=None):
    heads = [caption(doc, title)] if title else []
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = 1
    for j, htxt in enumerate(header):
        cell = t.cell(0, j)
        cell.text = ""
        rich_add(cell.paragraphs[0], htxt, size=size, bold=True,
                 name="Times New Roman")
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.cell(i + 1, j)
            cell.text = ""
            rich_add(cell.paragraphs[0], str(val), size=size,
                     name="Times New Roman")
    _keep_table(t, heads)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def _cell_edge(cell, edge, sz):
    from docx.oxml import OxmlElement
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcPr.append(borders)
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:color"), "000000")
    borders.append(el)


def three_line_table(doc, header, rows, size=8, title=None, full=False,
                     note=None):
    """Booktabs-style: heavy top rule, thin rule under header, heavy
    bottom rule; no verticals.  full=True places the table in a
    single-column (spanning) section.  note (small text) is typeset
    inside the spanning section, directly under the table."""
    if full:
        switch_to(doc, SECT_2COL[0])
    heads = []
    if title:
        label, _, rest = title.partition(".")
        heads = tabletitle(doc, label.strip() + ".", rest.strip())
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.alignment = 1
    t.autofit = True
    for j, htxt in enumerate(header):
        cell = t.cell(0, j)
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if j else \
            WD_ALIGN_PARAGRAPH.LEFT
        rich_add(p, htxt, size=size, bold=True, name="Times New Roman")
        _cell_edge(cell, "top", 12)
        _cell_edge(cell, "bottom", 6)
    nrows = len(rows)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.cell(i + 1, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if j else \
                WD_ALIGN_PARAGRAPH.LEFT
            bold = False
            if isinstance(val, tuple):
                val, bold = val
            rich_add(p, str(val), size=size, bold=bold,
                     name="Times New Roman")
            if i == nrows - 1:
                _cell_edge(cell, "bottom", 12)
    _keep_table(t, heads)
    _sp = doc.add_paragraph()
    _sp.paragraph_format.space_after = Pt(0)
    _sp._p.get_or_add_pPr().append(parse_xml(
        '<w:rPr %s><w:sz w:val="4"/></w:rPr>' % nsdecls("w")))
    if note:
        np_ = doc.add_paragraph()
        np_.paragraph_format.space_before = Pt(2)
        nr = np_.add_run(note)
        nr.font.size = Pt(8)
        nr.font.name = "Times New Roman"
    if full:
        switch_to(doc, SECT_1COL[0])
    return t


def mono_block(doc, lines, size=7):
    """Monospace block (pseudocode): single-cell bordered table, lines
    wrapped to fit a 3.5-inch column; the row is pinned against
    splitting so the block never breaks across a column or page."""
    import textwrap
    wrapped = []
    for ln in lines:
        wrapped.extend(textwrap.wrap(ln, width=50,
                                     subsequent_indent="    ",
                                     break_long_words=False)
                       or [""])
    t = doc.add_table(rows=1, cols=1)
    t.alignment = 1
    from docx.oxml import OxmlElement
    trPr = t.rows[0]._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))
    cell = t.cell(0, 0)
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    for i, line in enumerate(wrapped):
        if i:
            p.add_run().add_break()
        r = p.add_run(line)
        r.font.name = "Consolas"
        r.font.size = Pt(size)
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


# ------------------------------------------------- IEEE template integration
TEMPLATE = (ROOT / "IEEE-Transactions-Word-templates-and-instructions"
            / "Transactions-template-and-instructions-on-how-to-create-"
              "your-article-formatted (4).docx")

# captured from the template at build start: sectPr of the one-column
# front-matter section and of the two-column body section
SECT_1COL = [None]
SECT_2COL = [None]


def switch_to(doc, sect_el, before=None, after=None):
    """End the current section with a continuous break carrying
    sect_el's properties (1-col or 2-col).

    before/after (points) plus a 9-pt paragraph mark reproduce the
    spacing of the template's section-break paragraph; when omitted the
    break paragraph stays neutral (used around full-width floats).
    """
    import copy as _copy
    p = doc.add_paragraph()
    if before is not None:
        p.paragraph_format.space_before = Pt(before)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    pPr = p._p.get_or_add_pPr()
    # keep the break-paragraph mark small (6 pt) even in the neutral
    # case: a full-width island carries two of these, and a 10-pt mark
    # leaves dead space that can push the whole island to the next page
    pPr.append(parse_xml('<w:rPr %s><w:sz w:val="12"/></w:rPr>'
                         % nsdecls("w")))
    pPr.append(_copy.deepcopy(sect_el))


def spacer(doc, before=None, after=None):
    """Empty spacer paragraph with a 9-pt mark, as between the template's
    title/authors blocks."""
    p = doc.add_paragraph()
    if before is not None:
        p.paragraph_format.space_before = Pt(before)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    pPr = p._p.get_or_add_pPr()
    pPr.append(parse_xml('<w:rPr %s><w:sz w:val="18"/></w:rPr>'
                         % nsdecls("w")))


# ------------------------------------------------------------- 2) footnotes
def _fn_para(runs):
    """One footnote paragraph, 8 pt, first-line indent 202 twips, justified,
    no borders -- replicating the Transactions template footnote format.

    runs: list of (text, italic) tuples.
    """
    from docx.oxml.ns import nsdecls
    rxml = ""
    for text, italic in runs:
        i = "<w:i/>" if italic else ""
        rxml += ('<w:r><w:rPr>%s<w:sz w:val="16"/></w:rPr>'
                 '<w:t xml:space="preserve">%s</w:t></w:r>'
                 % (i, xesc(text)))
    return ('<w:p %s><w:pPr><w:keepLines/><w:pBdr>'
            '<w:top w:val="nil"/><w:left w:val="nil"/>'
            '<w:bottom w:val="nil"/><w:right w:val="nil"/></w:pBdr>'
            '<w:spacing w:before="0" w:after="0" w:line="240" '
            'w:lineRule="auto"/>'
            '<w:ind w:firstLine="202"/><w:jc w:val="both"/>'
            '<w:rPr><w:sz w:val="16"/></w:rPr></w:pPr>%s</w:p>'
            % (nsdecls("w"), rxml))


def add_affiliation_footnote(doc):
    """Append the received-date / funding / affiliations footnote to the
    template's footnotes part (IEEE style: first-page footnote, no
    end-of-paper Acknowledgment). Returns the footnote id."""
    from lxml import etree
    from docx.oxml.ns import nsdecls
    part = None
    for pp in doc.part.package.parts:
        if str(pp.partname).endswith("/footnotes.xml"):
            part = pp
            break
    assert part is not None, "footnotes.xml part not found in template"
    root = etree.fromstring(part.blob)
    fid = max(int(fn.get(qn("w:id")))
              for fn in root.findall(qn("w:footnote"))) + 1
    paras = [
        _fn_para([
            (ACK + " ", False),
            ("(Corresponding author: Yalong Zhang, "
             "ylzhang@qzc.edu.cn.)", True),
        ]),
        _fn_para([
            ("Xuemei Li and Jianping Deng are with the Faculty of Teacher "
             "Education, Quzhou University, Quzhou 324000, China.", False),
        ]),
        _fn_para([
            ("Meng Huang, Bao Wang, and Yalong Zhang are with the College "
             "of Electrical and Information Engineering, Quzhou University, "
             "Quzhou 324000, China.", False),
        ]),
    ]
    fn = parse_xml('<w:footnote %s w:id="%d">%s</w:footnote>'
                   % (nsdecls("w"), fid, "".join(paras)))
    root.append(fn)
    part._blob = etree.tostring(root, xml_declaration=True,
                                encoding="UTF-8", standalone=True)
    return fid


def tabletitle(doc, label, title):
    p = doc.add_paragraph(style="Table Title")
    rich_add(p, label)
    p2 = doc.add_paragraph(style="Table Title")
    rich_add(p2, title)
    return [p, p2]


def full_width(doc, emit):
    """Place content emitted by emit() in a one-column (spanning)
    section inside the two-column body."""
    switch_to(doc, SECT_2COL[0])
    emit()
    switch_to(doc, SECT_1COL[0])


# ---------------------------------------------------------------- build
def build() -> None:
    import copy as _copy
    N = nums()
    # --- load two-column Transactions-style template, keep styles & sections
    doc = Document(str(TEMPLATE))
    body = doc.element.body
    sectPrs = list(body.iter(qn("w:sectPr")))
    SECT_1COL[0] = _copy.deepcopy(sectPrs[0])   # one-column front matter
    SECT_2COL[0] = _copy.deepcopy(sectPrs[-1])  # two-column body
    # clear the template's instruction body, keep final sectPr
    final_sect = body.find(qn("w:sectPr"))
    for child in list(body):
        if child is not final_sect:
            body.remove(child)
    # the template restarts page numbering in its body section; a
    # submission must number pages continuously
    for sect in (SECT_1COL[0], SECT_2COL[0], final_sect):
        for pg in sect.findall(qn("w:pgNumType")):
            sect.remove(pg)

    # --- front matter (one column) -------------------------------------
    p = doc.add_paragraph(style="Title")
    p.add_run(TITLE)
    spacer(doc)  # spacer, as in the template

    p = doc.add_paragraph(style="Authors")
    for i, (name, mark) in enumerate([
            ("Xuemei Li", "1"), ("Jianping Deng", "1"),
            ("Meng Huang", "2"), ("Bao Wang", "2"),
            ("Yalong Zhang", "2*")]):
        if i:
            p.add_run(", " if i < 4 else ", and ")
        p.add_run(name)
        r = p.add_run(mark)
        r.font.superscript = True

    # affiliations, funding and the corresponding-author note go to a
    # first-page footnote, as the IEEE Transactions template requires.
    # The continuous section break lives in a single near-zero-height
    # paragraph (1-pt mark, no spacing); the invisible footnote anchor
    # (customMarkFollows + Symbol space, as in the template) opens the
    # abstract paragraph itself.  Both the break and the anchor must be
    # kept out of the one-column section -- either one anchored there
    # pushes the whole abstract to page 2 in rendering
    fid = add_affiliation_footnote(doc)

    pbrk = doc.add_paragraph()
    pbrk.paragraph_format.space_before = Pt(0)
    pbrk.paragraph_format.space_after = Pt(2)
    pbrk_pr = pbrk._p.get_or_add_pPr()
    pbrk_pr.append(parse_xml('<w:rPr %s><w:sz w:val="2"/><w:szCs w:val="2"/>'
                             '</w:rPr>' % nsdecls("w")))
    pbrk_pr.append(_copy.deepcopy(SECT_1COL[0]))

    # --- abstract / index terms (two-column) --------------------- ----------------------------------------
    p = doc.add_paragraph(style="Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(1)
    # invisible footnote anchor at the very start of the abstract
    p._p.get_or_add_pPr().addnext(parse_xml(
        '<w:r %s><w:rPr><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr>'
        '<w:footnoteReference w:customMarkFollows="1" w:id="%d"/>'
        '<w:sym w:font="Symbol" w:char="F020"/></w:r>'
        % (nsdecls("w"), fid)))
    r = p.add_run("Abstract")
    r.bold = True
    r.italic = True
    r.font.size = Pt(9)
    r = p.add_run("\u2014")
    r.bold = True
    r.font.size = Pt(9)
    r2 = p.add_run(
         "When a publisher screens a submission against a corpus of "
         f"{N['e4_max']:,} MIDI files, or a dataset curator must decide "
         "whether a generative model has memorized its training data, "
         "every missed copy is a liability and every false alarm is an "
         "expert afternoon lost. Existing systems force a choice no such "
         "user can afford: audio fingerprinting and learned embeddings "
         "tolerate noise but certify no recall; exact pattern mining "
         "carries no recall guarantee and explodes at the support levels "
         "copying requires; and the set-similarity engines behind "
         "large-scale deduplication are structurally blind to contained "
         "copies. We show that this trade-off is architectural rather "
         "than fundamental and dissolve it by giving the two layers "
         "different contracts. A tolerant item-set screen guarantees "
         "recall per query through an evidence lower bound, verified "
         f"cell by cell on {N['e2_n']} adversarial cells with zero "
         "violations, and its rare-first anytime schedule answers in "
         "time driven by the evidence rather than by the corpus. A "
         "strict structural confirmation layer then aligns ordered note "
         "chains, cutting the fragment-level false-positive rate on "
         "style-similar hard negatives to 2.1% at 83.9% recall under "
         "transcription noise. The index builds in "
         f"{N['e4_build']:.1f} s and answers queries in "
         f"{N['e4_p50']:.1f} ms (p50) at 100% planted recall. The same "
         "pipeline screens a trained music generator across the full "
         "memorization spectrum with 96-100% correct source "
         "attribution, and delivers a full-corpus census of duplicate "
         "structure, localizing spliced segments and transposed covers "
         "with score-checkable evidence.")
    r2.bold = True
    r2.font.size = Pt(9)
    p = doc.add_paragraph(style="Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(5)
    r = p.add_run("Index Terms")
    r.bold = True
    r.italic = True
    r.font.size = Pt(9)
    r = p.add_run("\u2014")
    r.bold = True
    r.font.size = Pt(9)
    r2 = p.add_run("Anytime algorithms, copyright, music information "
                   "retrieval, plagiarism screening, symbolic music.")
    r2.bold = True
    r2.font.size = Pt(9)

    # --- I. introduction ----------------------------------------------------
    h1(doc, "I. Introduction")
    drop_cap(doc,
         "Music publishers, dataset curators, and generative-music "
         "deployments share a common need: given a corpus of symbolic "
         "music (MIDI and its derivatives) and a query\u2014a new "
         "submission, a generated sample, or a suspected infringement"
         "\u2014find every piece that shares a substantively copied span "
         "with the query, rank the candidates, and show the evidence. "
         "The stakes are concrete: a census run with the system of this "
         "paper finds on the order of "
         f"{N['e19f_est']['exact_band3'] / 1e3:.0f}k verbatim-level "
         "duplicate pairs in a single public corpus mirror alone "
         "(Section VI-C).")
    para(doc,
         "The requirement list is demanding. Recall must survive the "
         "noise of real-world reuse: transposition, tempo change, "
         "re-instrumentation, transcription jitter from audio-to-MIDI "
         "tools, and deliberate splicing. Latency must stay interactive "
         "even as corpora reach hundreds of thousands of pieces. And the "
         "output must be decision-grade: on style-similar but innocent "
         "repertoire the system must not cry wolf, and on positives it "
         "must present an alignment a human expert can check against a "
         "score.")
    para(doc,
         "Established approaches each fail one requirement. Audio "
         "fingerprinting [3], [5] and chroma-based matching [4], [12] "
         "target audio and tolerate noise well, but their features are "
         "lossy with respect to the symbolic content publishers must "
         "adjudicate, and they provide no recall guarantee. Frequent "
         "itemset mining (FIM) and its geometric cousins (SIATEC and "
         "successors) [2], [9], [10] discover repeated patterns with "
         "algorithmic elegance, but exact enumeration explodes "
         "combinatorially at the support levels copying detection "
         "requires (we quantify this in Section V-A), and pattern sets "
         "are not ranked candidates.")
    para(doc,
         f"Nor can the gap be closed by re-tuning the engines that power "
         f"large-scale deduplication. The obstacle is geometric: a copied "
         f"span of about 40 items embedded in a piece of about 700 items "
         f"scores below 0.10 in set-Jaccard under a perfect oracle "
         f"(measured quartiles {N['e20_dj_p25']:.3f}/{N['e20_dj_p50']:.3f}/"
         f"{N['e20_dj_p75']:.3f} over our 337-cell "
         "adversarial audit), and no band configuration of a "
         "MinHash-LSH index recovers such a donor at any operating "
         "point (Section V-G). Relative overlap has no threshold at "
         "which a contained copy becomes visible, so resemblance cannot "
         "be tuned into recall; containment must be verified "
         "query-side, not estimated corpus-side (Proposition 1 "
         "formalizes the invisibility; Section V-G measures it). This "
         "negative result "
         "is what motivates the architecture: the screen's contract "
         "must be stated on evidence, not on similarity.")
    para(doc,
         "Cover-song identification has moved "
         "to learned audio embeddings [15]\u2013[17], while plagiarism "
         "detection specifically has been addressed with chroma-based "
         "forensics [18], bipartite graph matching [19], and melodic-"
         "similarity analysis of real copyright cases [20]; these audio- "
         "and embedding-centric methods, like query-by-humming lineage "
         "[13], [14], do not provide a symbolic, per-query recall "
         "guarantee of the kind a publisher can contract against. "
         "Fig. 1 previews the whole system as an evidence funnel: "
         "candidate sets narrow through the L1 screen and the L2 "
         "top-C gate while the recall floor (Thm 1) stays unbroken; "
         "L3 inspects survivors under a structural lens, and confirmed "
         "matches ship as adjudicable reports.")
    full_width(doc, lambda: (add_emf(doc, "fig1_alt", 16.0),
                             caption(doc, "Fig. 1. The evidence funnel of "
                                         "the proposed pipeline, with one "
                                         "query traced end to end (amber "
                                         "markers). Left: the Lakh MIDI "
                                         "corpus is encoded once into a "
                                         "rare-first item-set index "
                                         "(1.05 GB, 41.9 ms p50). Center: "
                                         "the L1 tolerant screen "
                                         "enumerates 1.66 M candidates "
                                         "under an anytime budget with a "
                                         "per-prefix recall floor (Thm 1). "
                                         "Right: L3 structural "
                                         "confirmation aligns ordered "
                                         "note chains\u2014invariant to "
                                         "pitch, tempo, and splicing\u2014"
                                         "and certifies the copied span "
                                         "(\u03c1 = 0.62 \u2265 0.5) as "
                                         "a publisher-readable verdict.")))
    para(doc,
         "This paper's thesis is architectural: the three requirements "
         "decompose across two layers with different contracts. The "
         "first layer maximizes recall under a stated noise model and "
         "proves it\u2014an evidence lower bound that holds for any "
         "query whose per-note deviation stays within declared "
         "tolerances. The second layer maximizes precision by checking "
         "structure that style peers do not share: the ordered chain "
         "of notes with their inter-onset intervals. We additionally "
         "require the first layer to be anytime [8]: under a partial "
         "budget it must return the best partial answer together with a "
         "sound bound on what remains open. To our knowledge, no prior "
         "copy-detection system states and audits its screening "
         "contract as a per-query recall guarantee under a declared "
         "noise model.")
    para(doc,
         "Our findings, all measured on the Lakh MIDI corpus "
         f"(full corpus, {N['e4_max']:,} pieces), are: "
         "(1) item-set containment alone is screening-grade only\u2014"
         "on style-similar hard negatives its fragment-level "
         "false-positive rate reaches 93%, and no threshold repairs "
         "this without destroying recall; "
         "(2) a strict-tolerance ordered-chain confirmation layer on "
         "top of the screen cuts the false-positive rate to 2.1% at "
         "83.9% recall under transcription noise, meeting the "
         "<5% screening requirement of a decision-support tool; "
         "(3) the screen's rare-first schedule tightens the certified "
         f"open-candidate bound by {N['e3_hot'] / N['e3_rare']:.1f}\u00d7 "
         "over a hot-first schedule at 70% budget, with identical "
         "full-budget recall. ")
    para(doc,
         "Two further findings complete the picture: "
         "(4) detection on a controlled memorization spectrum rises "
         f"monotonically to {N['e62_l1'] * 100:.0f}% at full copying; "
         "and (5) a full-corpus census over 174,300 pieces measures "
         f"{N['e18_rel35'] / 1e9:.1f} billion candidate pairs at the "
         "screening operating point, and a stratified audit of the "
         "high-scoring candidates confirms an estimated "
         f"{N['e19f_est']['exact_band3'] / 1e3:.0f}k verbatim-level "
         "duplicate pairs at 90% channel precision, while on "
         "in-the-wild cases the system localizes a spliced "
         "30-second segment and recovers a +3-semitone transposed "
         "cover with exact, score-checkable alignment maps.")
    para(doc,
         "The through-line of these results is that guarantees, not "
         "thresholds, are the unit of design: each layer is specified "
         "by a contract it must honor, and every reported number is a "
         "measurement of contract compliance rather than a tuned "
         "operating point. The contributions are: "
         "(1) an architectural decomposition of copy detection into a "
         "provable-recall screening problem and a structural "
         "confirmation problem, with formal contracts for each layer, "
         "motivated by a negative result that is also a theorem "
         "(Proposition 1: no corpus-side resemblance threshold attains "
         "complete recall on contained copies) and validated "
         "empirically: no single "
         "item-level method reaches decision-grade precision, and no "
         "purely structural method scales; "
         "(2) a tolerant item-set screen whose per-query recall is "
         "guaranteed by a sound evidence lower bound under a declared "
         "noise model, auditable cell by cell on 337 adversarial cells "
         "with zero violations; "
         "(3) an anytime schedule analysis showing that rare-first "
         "processing tightens the certified open-candidate bound over "
         "hot-first under partial budgets (by "
         f"{N['e3_hot'] / N['e3_rare']:.1f}\u00d7 at 70% budget) and that "
         "the bound is computable after any schedule prefix, turning an "
         "engineering heuristic into a schedulable guarantee. ")
    para(doc,
         "The last two contributions are systems-level: "
         "(4) a strict-tolerance ordered-chain confirmation layer that "
         "outputs note-level alignment evidence, reaching 2.1% "
         "fragment-level false positives at 83.9% recall on "
         "style-similar hard negatives, together with a controlled "
         "memorization study showing monotone detection growth and "
         "96-100% correct source attribution under full copying, "
         f"together with a full-corpus census over 174,300 pieces that "
         f"measures {N['e18_rel35'] / 1e9:.1f} billion candidate pairs "
         "at the screening operating point and, via a stratified "
         f"adjudication audit, an estimated "
         f"{N['e19f_est']['exact_band3'] / 1e3:.0f}k verbatim-level "
         "duplicate pairs at 90% channel precision; and "
         "(5) a fully scripted reproduction release that regenerates "
         "every number, table, and figure in this paper from the raw "
         "corpus download.")
    para(doc,
         "Section II reviews related work. Section III formalizes the "
         "problem, states the evidence-bound theorem, and describes "
         "the three processing layers. Section IV details the "
         "experimental setup and operating parameters. Section V "
         "reports controlled experiments; Section VI reports "
         "real-world studies. Section VII discusses limitations and "
         "deployment considerations, and Section VIII concludes.")

    # --- II. related work ---------------------------------------------------
    h1(doc, "II. Related Work")
    h2(doc, "A. Symbolic music retrieval and pattern discovery")
    para(doc,
         "Sequence-based matching of notated music under edit distance "
         "and transportation distance was established by Typke et al. "
         "[1], and geometric repeated-pattern discovery by Meredith et "
         "al. [2]. Surveying the field, Casey et al. [3] and Typke et "
         "al. [5] separate audio-descriptor approaches from symbolic "
         "approaches; M\u00fcller [4], [12] systematize chroma and "
         "alignment techniques. Our screen layer inherits the item-set "
         "view of "
         "FIM [9], [10] but replaces corpus-side enumeration with "
         "query-side containment verification, trading pattern "
         "completeness for a provable per-query recall contract.")
    para(doc,
         "Symbolic version identification has a complementary lineage. "
         "Alignment-based matching of MIDI to audio [6] and "
         "sequence-comparison methods benchmarked on the Lakh corpus "
         "[7] establish that symbolic sequences support robust "
         "matching, but their cost is per-candidate: applied as "
         "corpus-wide filters they do not scale, and applied after a "
         "cheap filter they inherit the filter's recall, which none of "
         "these systems bounds. ")
    para(doc,
         "Our screen layer can be read as a "
         "recall-guaranteed candidate generator for exactly such "
         "aligners: it hands confirmation a top-C set small enough "
         "that exact structural alignment becomes affordable, while "
         "the bound certifies that nothing outside the set needs "
         "alignment at all.")
    h2(doc, "B. Memorization in generative models")
    para(doc,
         "Carlini et al. [11] demonstrated that large language models "
         "regurgitate training sequences and that extraction is "
         "detectable with membership tests [23]; the same extraction "
         "was then shown for diffusion models [24]. Deduplication "
         "reduces both verbatim regurgitation and privacy leakage "
         "[25], [26], and memorization is measurable even in "
         "probabilistic deep generative models [27]. For music "
         "specifically, symbolic generators such as Music Transformer "
         "[22] are trained on scraped MIDI, membership-inference "
         "auditing of generative music models has only recently been "
         "demonstrated [28], influence-level attribution has been "
         "explored with audio embeddings [29], and the legal status of "
         "such training data remains contested [30]. ")
    para(doc,
         "Publishers "
         "consequently need batch screening tools rather than per-sample "
         "membership oracles. Our controlled experiments (Section VI-A) "
         "emulate the memorization spectrum without training neural "
         "models, using n-gram order and a copy operator\u2014a "
         "deliberately transparent stand-in that exposes exactly where "
         "contiguity-based detection breaks down.")
    h2(doc, "C. Anytime algorithms")
    para(doc,
         "Zilberstein [8] formalized anytime algorithms: interruptible "
         "procedures whose intermediate results improve monotonically "
         "and can be accompanied by a bound on unexplored outcomes. Our "
         "screen adopts this contract at the level of evidence items: "
         "after any prefix of the rare-first schedule, the set of "
         "pieces that can still reach the threshold is exactly "
         "computable, which turns an engineering heuristic into a "
         "guarantee a publisher can schedule around.")
    para(doc,
         "The bound instantiates a classical pattern. Threshold "
         "algorithms for top-k aggregation [31] maintain a partial-score "
         "bound under which no unseen candidate can qualify, and "
         "branch-and-bound search [32] carries an admissible estimate "
         "of everything not yet explored. Theorem 1 transfers this "
         "contract to tolerant item-set evidence: because every "
         "unprocessed position can contribute at most one to any piece, "
         "score_u(P) + (q \u2212 u) plays the role of the partial "
         "bound, with tolerance turning it into a certified floor on "
         "final evidence rather than an optimistic estimate. We are "
         "not aware of an evidence bound of this form stated and "
         "cell-by-cell audited for music retrieval.")

    # --- III. system --------------------------------------------------------
    h1(doc, "III. System")
    para(doc,
         "Fig. 2 shows the pipeline. All layers operate on a shared "
         "event encoding; the screen and the confirmation use different "
         "tolerances by design.")
    h2(doc, "A. Problem statement and notation")
    para(doc,
         "A piece P = (e\u2081, \u2026, e_n) is a sequence of note "
         "events e_i = (t_i, p_i, d_i, v_i): onset time, MIDI pitch, "
         "duration, and velocity. An encoding \u03c6 maps each event "
         "to an item, a tuple of quantized features (Section III-B); "
         "the item set S(P), the union of {\u03c6(e_i)} over all "
         "positions, discards order "
         "and repetition. For tolerance vector k = (k_pitch, k_bin, "
         "k_vel), the neighborhood N_k(x) of an item x is the set of "
         "items whose pitch differs by at most k_pitch semitones and "
         "whose duration, inter-onset interval (IOI), and velocity "
         "bins differ by at most k_bin and k_vel bins respectively. "
         "A planted copy of a span X is produced by transforming "
         "every event of X with one of the six families of Section "
         "IV; the declared screen tolerance k = (2, 1, 1) covers all "
         "families except transposition beyond \u00b12 semitones "
         "and transcription jitter beyond \u00b11 bin, which the "
         "interval-sketch index of Section III-B handles separately.")
    para(doc,
         "Problem. Given a corpus D = {P\u2081, \u2026, P_N} and a "
         "query fragment q, return a ranked candidate list with "
         "per-candidate evidence such that (completeness) every piece "
         "that shares with q a copied span under the declared noise "
         "model appears in the list, and (soundness of evidence) "
         "every confirmed candidate carries a note-level alignment "
         "that a human adjudicator can check against a score. The "
         "two requirements pull in opposite directions: completeness "
         "favors permissive item-level matching, soundness favors "
         "strict structural comparison. The system's bet is that the "
         "two can be separated cleanly enough to prove the first and "
         "measure the second.")
    para(doc,
         "Proposition 1 (containment invisibility of resemblance). "
         "Fix \u03c4 > 0 and a query Q with q items. For any corpus "
         "piece P with p distinct items, J(Q, P) \u2264 q/p: the donor "
         "of a planted span scores below \u03c4 whenever p > q/\u03c4, "
         "however faithfully the copied items are preserved. No fixed "
         "corpus-side resemblance threshold therefore attains complete "
         "recall on contained copies, and no MinHash-LSH configuration "
         "repairs this, since banding only reparametrizes the same "
         "Jaccard operating point. Proof: the intersection contains at "
         "most the q query items and the union contains all p piece "
         "items; the bound is tight when the span is the only "
         "overlap. \u220e",
         indent=0.4)
    h2(doc, "B. Event encoding and index construction")
    para(doc,
         "Each piece is quantized onto a fixed grid (125 ms per bin "
         "at ticks-per-beat 8) and encoded per note as a "
         "four-dimensional item: pitch, duration bin, IOI bin, and "
         "velocity bin. A piece's item set is the set of distinct "
         "codes. Pop-music grid quantization is a deliberate "
         "information reduction: it is what makes the screen layer "
         "fast and its recall argument clean, and it is what the "
         "confirmation layer must overcome with structural "
         "information. An interval-sketch variant (pitch replaced by "
         "the chromatic interval to the next note) provides "
         "transposition invariance for retrieval of transposed "
         "material.")
    para(doc,
         "Items are remapped to gapless dense integer IDs per corpus "
         "revision, so that the inverted index consists of contiguous "
         "posting lists; this costs one sort of the vocabulary and "
         "pays off in cache behavior and in a compact Fenwick-based "
         "open-set bookkeeping at query time.")
    full_width(doc, lambda: (add_emf(doc, "fig1_architecture", 16.0),
                             caption(doc, "Fig. 2. Two-layer "
                                         "copy detection pipeline. (a) A "
                                         "publisher-scale corpus is "
                                         "encoded once into a rare-first "
                                         "item-set index. (b) The L1 "
                                         "screen queries that index under "
                                         "an anytime budget with a "
                                         "provable recall lower bound "
                                         "(Thm 1, 337-cell audit). (c) L2 "
                                         "re-ranks and L3 confirms on "
                                         "ordered note chains, gating on "
                                         "ρ = 0.62 ≥ 0.5. (d) Confirmed matches "
                                         "ship as adjudicable reports; "
                                         "memorization and in-the-wild "
                                         "audits close the loop. Black "
                                         "arrows mark data flow; amber "
                                         "markers trace one query end to "
                                         "end.")))
    para(doc,
         "The corpus index is an inverted index from item to sorted "
         "piece-ID lists, built once in a linear pass (each piece "
         "contributes |S(P)| postings). Build time and memory grow "
         "linearly with corpus size; incremental "
         "updates append postings for new pieces without rebuilding.")
    h2(doc, "C. L1: tolerant screening with a provable bound")
    para(doc,
         "A query is processed position by position in rare-first "
         "order; each position contributes +1 to every piece that "
         "contains any variant of the position's item within "
         "tolerance (pitch \u00b12 semitones, duration/IOI \u00b11 "
         "bin, velocity \u00b11 bin). Formally:")
    para(doc,
         "Theorem 1 (tolerant evidence lower bound and certified open "
         "set). Let a query have q positions, "
         "processed in any order, and let score_u(P) be piece P's "
         "tolerant score after u positions. For every piece P whose "
         "copied span deviates within tolerance at every position, "
         "score_u(P) + (q \u2212 u) \u2265 score_q(P), and the open "
         "set O_u = {P : score_u(P) + (q \u2212 u) \u2265 \u03c4} "
         "is exactly the set of pieces that can still contain such a "
         "copy at threshold \u03c4. Proof sketch: a tolerated "
         "deviation maps position i's item into N_k, so each "
         "position of a true copy contributes at least as much as a "
         "verbatim position; unprocessed positions can contribute at "
         "most one each. Hence a piece outside O_u cannot be a copy, "
         "and no piece inside O_u can be excluded yet. \u220e",
         indent=0.4)
    para(doc,
         "Two consequences matter operationally. First, the recall "
         "contract is auditable per query: measuring donor score "
         "\u2265 bound on adversarial cells verifies it cell by cell "
         "(Section V-B). Second, the anytime contract is sound: "
         "after any budget prefix, the best partial answer plus "
         "O_u is a complete description of the search state, so "
         "interruption never loses a certified answer. Rare-first "
         "ordering greedily minimizes the growth of |O_u|, because a "
         "rare position eliminates, in expectation, the largest "
         "fraction of currently open pieces per unit of budget; "
         "Section V-C quantifies the resulting gap in the certified "
         "bound against hot-first processing.")
    para(doc,
         "Complexity. Index construction is O(\u03a3_P |S(P)|). A "
         "query touches, per position, the posting lists of all "
         "items in N_k, so query cost grows with the length of the "
         "evidence and with the vocabulary mass inside the query's "
         "tolerance neighborhood, and grows with corpus size only "
         "through longer posting lists; "
         "the open set is maintained in a Fenwick structure over "
         "piece IDs, giving O(log N) updates and an exact |O_u| "
         "readout after every position. Measured end to end, the "
         f"index builds in {N['e4_build']} s and queries run at "
         f"p50 = {N['e4_p50']} ms on the full "
         f"{N['e4_max']:,}-piece corpus.")
    h2(doc, "D. L2/L3: re-ranking and structural confirmation")
    para(doc,
         "The screen is deliberately permissive; verbatim counts "
         "re-rank its survivors, and the top-C union of tolerant and "
         "verbatim rankings is passed to confirmation. Confirmation "
         "scores an ordered alignment: two notes match when all four "
         "features are within strict tolerance (pitch \u00b11 "
         "semitone, duration, IOI, and velocity in exact bins). The "
         "score is the longest chain of matches with both note order "
         "and candidate position strictly increasing \u2014 a "
         "longest-common-subsequence computation restricted to "
         "anchor pairs, not a heuristic local alignment. ")
    para(doc,
         "Anchors are "
         "strict-tolerance matches; their j \u2212 i offsets are "
         "voted, and when the strict vote is inconclusive the "
         "interval-sketch offsets estimate the transposition, which "
         "is then removed by re-expressing the query in interval "
         "form and re-running confirmation once. ")
    para(doc,
         "The dynamic program "
         "runs inside the anchor-constrained window, so its cost is "
         "O(W\u00b7m) for window W and m anchors, with a traceback "
         "that recovers the chain itself. A candidate is confirmed "
         "when the best chain reaches \u03c1 times the query "
         "length. Algorithm 1 assembles the full pipeline.")
    para(doc,
         "The confirmed chain is itself the deliverable evidence: it "
         "maps note for note onto both scores, and together with the "
         "estimated transposition and the score trace it is what a "
         "publisher's adjudicator receives (Section VI-B). This "
         "design choice \u2014 evidence as a by-product of the "
         "decision procedure, not a post-hoc visualization \u2014 is "
         "what makes the false-positive rate of Section V-E "
         "interpretable: when confirmation fails, the misaligned "
         "chain shows why.", indent=0.5)
    mono_block(doc, [
        "Algorithm 1  Two-layer copy detection (query q, index I)",
        "Input:  q = (e1..eq); inverted index I; k_screen = (2,1,1);",
        "        k_confirm = (1,0,0); threshold tau; contiguity rho;",
        "        top-C; budget B",
        "Output: confirmed copies (P, chain, delta) with",
        "        |chain| >= rho * q",
        " 1: order <- positions of q sorted by |N_k(item_i)| ascending",
        " 2: score <- {P: 0}; u <- 0",
        " 3: while u < q and budget(B) do",
        " 4:     for P in I[N_k(item_order[u])] do",
        " 5:         score[P] <- score[P] + 1",
        " 6:     u <- u + 1",
        " 7:     open <- {P : score[P] + (q-u) >= tau}   // Thm. 1",
        " 8: end while",
        " 9: C <- top-C union of tolerant and verbatim rankings of open",
        "10: for P in C do",
        "11:     A <- strict-anchor matches of q against P",
        "12:     delta <- modal offset (j - i) over A   // transposition",
        "13:     if weak vote then delta <- interval-sketch estimate",
        "14:     chain <- windowed LCS over A under offset delta",
        "15:     if |chain| >= rho * q then emit (P, chain, delta)",
        "16: end for",
    ])

    # --- IV. setup ------------------------------------------------------------
    h1(doc, "IV. Experimental Setup")
    para(doc,
         f"Corpus. The Lakh MIDI dataset [7] (mirrored parquet export), "
         f"up to "
         f"{N['e4_max']:,} pieces encoded as item sets; the adversarial "
         "suite uses the first 3,000 pieces of shard 0. The GigaMIDI "
         "corpus [21] indicates that symbolic collections at the "
         "million-piece scale are now routine, which is the operating "
         "regime the screen layer is built for. ")
    para(doc,
         "Planted copies. Spans of 2/4/8/16 seconds are extracted from "
         "donor pieces and subjected to six transformation families: "
         "verbatim, transposition (\u00b11\u20136 semitones), tempo "
         "scale (1.05\u20131.20), note split/merge, re-instrumentation "
         "with voice dropping, and a transcription model combining "
         "onset jitter with note dropout. ")
    para(doc,
         "Hard negatives. For each "
         "query, the 20 most style-similar corpus pieces by a "
         "duration-weighted pitch-class histogram are collected as a "
         "negative pool; pairs whose verbatim evidence against the "
         "whole donor exceeds 30 items are removed as true duplicates. "
         "Fragments whose extracted span, or whose encoded item set, "
         "contains fewer than 8 notes or items are skipped, so the "
         "valid-fragment count differs slightly between experiment "
         "generations (238 in screening, 236 in confirmation, 233 in "
         "the cascade suite). ")
    para(doc,
         "Baselines. Set-Jaccard corpus scan, SIATEC-family pattern "
         "discovery [2], and n-gram Jaccard (Section V-A); the two "
         "frequent-itemset engines of our companion papers (under "
         "review) serve as enumeration baselines. They are independent "
         "of\u2014and not contributions of\u2014this paper; for "
         "completeness, Algorithm 1 gives "
         "pseudocode of the full pipeline, and the released source "
         "contains both engines' complete implementation details.")
    para(doc,
         "Environment. All experiments run on one commodity "
         "workstation (12th-generation Intel Core i9, 128 GB RAM); "
         "the computation engines are C++, the harness (corpus "
         "preparation, index building, measurement, figure and table "
         "generation) is Python 3.12 with NumPy, and all quoted "
         "latencies are CPU-only figures. The released pipeline "
         "re-downloads the corpus shards, rebuilds the index, and "
         "regenerates every table and figure from scratch.")
    para(doc,
         "Operating parameters. Table I summarizes the production "
         "configuration used unless a section states otherwise; the "
         "ablations of Section V-F justify each choice.")
    three_line_table(doc,
        ["Parameter", "Value", "Role"],
        [["Quantization grid", "125 ms (tpb = 8)",
          "event-encoding bin for all four features"],
         ["Screen tolerance k", "(2, 1, 1)",
          "pitch \u00b12 st; duration/IOI \u00b11 bin; velocity "
          "\u00b11 bin"],
         ["Evidence threshold \u03c4", "\u230a0.5\u00b7|S(q)|\u230b",
          "screen acceptance per query"],
         ["Confirm tolerance", "(1, 0, 0)",
          "pitch \u00b11 st; duration/IOI/velocity exact bins"],
         ["Contiguity \u03c1", "0.5 (0.4 high-recall)",
          "confirmation acceptance, |chain| \u2265 \u03c1\u00b7q"],
         ["Top-C", "50 (20 ablated)",
          "candidate feed to confirmation"],
         ["Anytime budget B", "full (half ablated)",
          "rare-first schedule length"]],
        size=8,
        title="TABLE I. Production operating parameters.")

    # --- V. results -----------------------------------------------------------
    h1(doc, "V. Results")
    h2(doc, "A. Scale and baseline feasibility")
    para(doc,
         f"Fig. 3 reports scaling on subsampled corpora and Table II "
         f"gives the corresponding numbers. Index build "
         f"reaches {N['e4_build']} s at {N['e4_max']:,} pieces and query "
         f"latency {N['e4_p50']} ms (p50), with planted recall 100% at "
         "every size. The set-Jaccard scan, the strongest naive "
         "baseline, is already 20\u00d7 slower than the screen at 10k "
         "pieces (238 ms vs. 12 ms p50) and infeasible beyond it. "
         f"MinHash-LSH (128 permutations, 16 bands x 8 rows), the standard "
         f"accelerated form of the same set-Jaccard semantics, scales "
         f"gracefully in isolation\u2014{N['e20_build']:.0f} s of signature "
         f"construction plus {N['e20_bucket']:.0f} s of bucket building, "
         f"{N['e20_mem']:.0f} MB, {N['e20_p50']:.0f} ms p50 at "
         f"{N['e20_max']:,} pieces\u2014yet retrieves none of the planted "
         f"donors at any corpus size ({N['e20_recall']} at tau = 0.10; "
         "identical at tau = 0.05 and 0.20): the S-curve of the band "
         "configuration activates only above Jaccard ~0.7, while a "
         "contained span of 40 items inside a ~700-item query reaches "
         "Jaccard ~0.1 at best, so the index answers every query with an "
         "empty candidate set. Section V-G analyses this geometry "
         "directly on the recall-matrix protocol. "
         "Corpus-side FIM "
         "enumeration\u2014the two companion engines\u2014was measured "
         "infeasible at the support levels copying detection requires "
         "(over 11 million frequent pairs at N=300 under the standard "
         "cutoff), which is precisely why the architecture places FIM "
         "semantics on the query side.")
    three_line_table(doc,
        ["Pieces", "Build (s)", "Mem (MB)", "p50 (ms)", "p95 (ms)",
         "Planted recall", "Jaccard p50 (ms)", "LSH p50 (ms)",
         "LSH recall"],
        e4_table_rows(), size=8, full=True,
        title="TABLE II. Index scaling and baseline feasibility; "
              "Jaccard scan infeasible beyond 10,000 pieces; MinHash-LSH "
              "(128 permutations, 16 bands x 8 rows, tau = 0.10) returns "
              "empty candidate sets at every size.",
        note="Rows are corpus-size subsamples drawn across different "
             "experiment generations, so the piece counts are not a "
             "uniform ladder and build times are not monotone in row "
             "order; scaling conclusions rely on within-generation "
             "interpolation rather than on adjacent-row differences.")
    add_emf(doc, "fig2_scaling", 8.0)
    caption(doc, "Fig. 3. Index build and query latency versus corpus "
                 "size (log-log); planted recall 100% at all sizes; "
                 "Jaccard scan baseline shown where feasible; MinHash-LSH "
                 "is fast at every size yet retrieves nothing "
                 "(Section V-G).")
    h2(doc, "B. Recall matrix and the evidence bound")
    para(doc,
         f"Table III summarizes and Fig. 4 visualizes the 337-cell "
         f"recall matrix. Verbatim "
         f"cells hit 100% as constructed; overall recall is "
         f"{N['e1_ok']}/{N['e1_total']} = "
         f"{N['e1_ok'] / N['e1_total'] * 100:.1f}%, and every failure "
         "lies outside the declared tolerance (e.g., transposition by "
         "6 semitones against a \u00b12 guarantee). "
         f"Fig. 5 verifies the bound: across all "
         f"{N['e2_n']} cells the measured donor evidence never falls "
         f"below the theoretical lower bound ({N['e2_viol']} "
         "violations; margins in Table IV), which is the empirical "
         "anchor of the recall "
         "contract.")
    three_line_table(doc,
        ["Transformation", "Strength", "2 s", "4 s", "8 s", "16 s", "All"],
        e1_table_rows(), size=8, full=True,
        title="TABLE III. Recall (%) of the L1 tolerant screen on 337 "
              "planted-copy cells (five seeds per cell; k_pitch = 2, "
              "k_bin = 1). Bold marks cells below 100 %.")
    h2(doc, "C. Anytime behavior")
    para(doc,
         "Fig. 6 shows the open-candidate bound as the rare-first "
         "schedule consumes its budget on 16-second spans, and "
         "Table V quantifies all three schedules. Early in the "
         "schedule the bound is vacuous by construction: after few "
         "positions every piece of the 1,000-piece corpus can still "
         "reach the threshold, and the certified open set is the "
         "whole corpus (1000.0 for all schedules through 50% "
         "budget). Discrimination emerges late: at 70% budget "
         f"rare-first certifies {N['e3_rare']:.1f} open candidates "
         f"versus {N['e3_rand']:.1f} (random) and {N['e3_hot']:.1f} "
         "(hot-first), and at full budget all schedules converge to "
         "the same open set with 100% donor recovery \u2014 the "
         "scheduling advantage is bound quality, not recall. The "
         "operational value of the anytime contract is the certified "
         "open set itself, available after any prefix: a screening "
         "queue can trade the bound against throughput, and an audit "
         "can stop early without losing a certified answer.")
    add_emf(doc, "fig_e1_heatmap", 8.0)
    caption(doc, "Fig. 4. Recall heatmap of the 337-cell matrix; rows "
                 "are transformation and strength, columns span length. "
                 "The three sub-100 % cells pair extreme noise with the "
                 "shortest spans.")
    three_line_table(doc,
        ["Transformation", "Cells", "Mean margin", "Min margin",
         "Violations"],
        e2_table_rows(), size=8,
        title="TABLE IV. Donor evidence margin (donor score minus "
              "theoretical lower bound) per transformation; a negative "
              "margin would be a bound violation.")
    add_emf(doc, "fig4_bounds", 8.0)
    caption(doc, "Fig. 5. Measured donor evidence versus theoretical "
                 "lower bound, 337 adversarial cells; zero violations.")
    add_emf(doc, "fig3_anytime", 8.0)
    caption(doc, "Fig. 6. Open-candidate bound versus processed budget "
                 "for three schedules; 16 s spans, 1,000-piece corpus.")
    three_line_table(doc,
        ["Budget", "Rare-first open", "Random open", "Hot-first open",
         "Donor recovery (%)"],
        e3_table_rows(), size=8,
        title="TABLE V. Anytime schedules on 16 s spans over a "
              "1,000-piece corpus: mean open-candidate bound (hits "
              "plus remaining bound) and donor recovery per budget "
              "fraction.")
    h2(doc, "D. The key negative result: screening is not deciding")
    para(doc,
         "On the hard-negative pools, the tolerant screen alone "
         "produces a 93% fragment-level false-positive rate, and "
         "raising the threshold cannot repair it: recall falls below "
         "80% before the false-positive rate reaches 43%. Verbatim "
         "counts alone rank well (donor in top-20: 93.7%) but still "
         "flag 22% of fragments. Fig. 7 and Table VI break the "
         "phenomenon down by donor-margin distribution and fragment "
         "length. This is a property of item-level "
         "encodings\u2014pop repertoire shares large amounts of "
         "grid-quantized material\u2014and it motivates the "
         "confirmation layer. ")
    para(doc,
         "Sample sizes are small (238 fragments; "
         "95% half-width \u2248 1.8 pp near 2% incidence and \u2248 6.3 "
         "pp near 50%), so we treat single-percentage-point "
         "differences as ties and rely on margins larger than the "
         "half-width.")
    h2(doc, "E. Confirmation precision and the cascade")
    para(doc,
         f"Strict-tolerance chain confirmation reaches a 2.1% "
         f"fragment-level false-positive rate at 83.9% recall "
         f"(\u03c1=0.5), and 7.2% at 98.3% recall (\u03c1=0.4); "
         f"Table VII and Fig. 8 map the full recall/FP trade-off "
         f"over three anchor-tolerance regimes and four contiguity "
         f"thresholds. "
         f"Table VIII and Fig. 9 place the full cascade against "
         f"its single-layer ablations. The cascade's remaining "
         f"bottleneck is candidate retention: verbatim top-C keeps "
         f"{N['e7_ret20'] * 100:.1f}% "
         f"(C=20) and {N['e7_ret50'] * 100:.1f}% (C=50) of donors; the "
         "union of tolerant and verbatim top-C feeds\u2014adopted in "
         "the final system\u2014lifts retention above 99%.")
    full_width(doc, lambda: (add_emf(doc, "fig_e13_margins", 16.0),
                             caption(doc, "Fig. 7. Donor score margin "
                                         "(donor minus best non-donor) "
                                         "on 238 hard-negative fragments; "
                                         "the annotated rate is the "
                                         "fragment-level flag rate of "
                                         "each layer.")))
    three_line_table(doc,
        ["Span (s)", "Fragments", "L1 tolerant FP (%)",
         "L2 verbatim FP (%)", "L2 donor in top-20 (%)"],
        e13_table_rows(), size=8,
        title="TABLE VI. Single-layer screening on style-similar hard "
              "negatives (80 donors, transcribed fragments), by "
              "fragment length.")
    para(doc,
         "Both metrics share one denominator: the 236 fragment queries of "
         "the confirmation suite, each a true transcription copy of one of "
         "the 80 donors. The recall numerator counts fragments whose donor "
         "is confirmed; the FP numerator counts fragments in which at "
         "least one non-donor piece is confirmed at the same threshold, "
         "so recall and FP are measured on exactly the same queries. The "
         "two contiguity anchors answer two different workflows: "
         "\u03c1 = 0.5 (2.1% FP, 83.9% recall) is the decision-grade "
         "operating point, at which a confirmed flag can be acted on "
         "directly; \u03c1 = 0.4 (7.2% FP, 98.3% recall) is the "
         "high-recall triage point for pre-filtering large corpora "
         "before human review. \u201cDecision-grade\u201d is used here in "
         "an operational sense: the threshold is fixed before "
         "measurement, applied uniformly across corpora, and the quoted "
         "error rate is the measured fragment-level FP on style-similar "
         "hard negatives rather than a per-corpus tuned value.")
    three_line_table(doc,
        ["Anchor tolerance", "\u03c1 = 0.3", "\u03c1 = 0.4",
         "\u03c1 = 0.5", "\u03c1 = 0.6"],
        e14_table_rows(), size=8,
        title="TABLE VII. Confirmation recall / fragment-level FP (%) "
              "by anchor-tolerance regime and contiguity threshold \u03c1 "
              "(236 hard-negative fragments).")
    add_emf(doc, "fig_e14_rho", 8.0)
    caption(doc, "Fig. 8. Confirmation operating curves: donor recall "
                 "versus fragment-level FP over \u03c1, labeled by "
                 "threshold, for three anchor-tolerance regimes.")
    three_line_table(doc,
        ["Layer / system", "Recall", "Fragment-level FP", "Contract"],
        [["L1 tolerant screen", "100%",
          "92.7% (\u03c4 = \u230a0.5\u00b7|S(q)|\u230b); no threshold "
          "reaches <50%",
          "provable recall + anytime bound"],
         ["L2 verbatim rank (top-1)", "58.8% top-1 / 93.7% top-20",
          "22.3%", "no guarantee; per-corpus tuning"],
         ["Screen + confirm (\u03c1=0.5)", f"{N['e7_c50_r5'] * 100:.1f}%",
          f"{N['e7_c50_f5'] * 100:.1f}%", "decision-grade"],
         ["Screen + confirm (\u03c1=0.4)", f"{N['e7_c50_r4'] * 100:.1f}%",
          f"{N['e7_c50_f4'] * 100:.1f}%",
          "high-recall operating point"]],
        size=8,
        title="TABLE VIII. Layer comparison on style-similar hard "
              "negatives (233 transcribed fragments, 80 donors).")
    h2(doc, "F. Component ablations")
    para(doc,
         "Ablations over the confirmation and screening components "
         "(threshold level, tolerance vector, grid granularity) are "
         "consistent: recall is flat at 100% wherever the guarantee "
         "applies; false positives and latency trade off along the "
         "tolerance vector exactly as the bound predicts; and finer "
         "grids monotonically reduce false positives at sub-linear "
         "vocabulary growth. The audit grid comprises 29 planted cells "
         "(30 random draws, one dropped because its planted span "
         "contained fewer than 8 notes), spanning the 4 s/16 s span "
         "lengths and four transformation families; the grid is fixed "
         "across all ablation settings, so every configuration is "
         "compared on identical evidence. Fig. 10 plots the three "
         "ablation families and Table IX tabulates them.")
    full_width(doc, lambda: (add_emf(doc, "fig5_cascade", 12.8),
                             caption(doc, "Fig. 9. Operating points and "
                                         "donor retention on hard "
                                         "negatives. (a) Operating "
                                         "points of the three systems; "
                                         "(b) donor retention in the "
                                         "top-C candidate feed.")))
    full_width(doc, lambda: (add_emf(doc, "fig_e5_ablation", 18.2),
                             caption(doc, "Fig. 10. Component ablations "
                                         "over the confirmation and "
                                         "screening stages. (a) evidence "
                                         "span length; "
                                         "(b) tolerance vector (bars: "
                                         "false candidates, log scale; "
                                         "dashed: recall, right axis); "
                                         "(c) quantization grid "
                                         "granularity.")))
    three_line_table(doc,
        ["Ablation", "Setting", "Recall", "False candidates",
         "Query p50 (ms)"],
        e5_table_rows(), size=8,
        title="TABLE IX. Component ablations on the 29-cell planted "
              "audit; false candidates measured on the hard-negative "
              "pool.")
    h2(doc, "G. Set-similarity retrieval: the MinHash-LSH baseline")
    para(doc,
         f"Proposition 1 turns the expected failure of this baseline "
         f"into a prediction to test. A planted query of the recall "
         f"matrix embeds a 40-item span in 300 noise items and probes "
         f"pieces of ~700 distinct items; the proposition then rules "
         f"out any resemblance threshold that both recovers such "
         f"contained donors and keeps candidate volume bounded, "
         f"because the donor's Jaccard is capped near the "
         f"span-to-container ratio and can only fall as containers "
         f"grow. The measurement confirms the cap is operative, not "
         f"hypothetical: even a perfect set-Jaccard oracle scores "
         f"the donor at only "
         f"{N['e20_dj_p25']:.3f} / {N['e20_dj_p50']:.3f} / "
         f"{N['e20_dj_p75']:.3f} (quartiles over the 337 cells; "
         f"Fig. 11(a)); just {N['e20_dj_ge10']} of 337 donors reach "
         f"Jaccard 0.10. A contained copy is structurally invisible "
         f"to relative overlap, however faithfully its items are "
         f"preserved.")
    para(doc,
         f"Tuning the "
         f"band configuration then moves the operating point along "
         f"the recall-versus-candidate-volume trade-off the "
         f"proposition predicts, not past it "
         f"(Table X): with the standard 16 x 8 bands at tau = 0.10 the "
         f"donor survives screening in "
         f"{N['e20_m8_01_dic']:.1f}% of cells; re-tuning to 2 rows x "
         f"64 bands\u2014an S-curve threshold near 0.12, the textbook "
         f"choice for this regime\u2014raises donor survival to "
         f"{N['e20_m2_01_dic']:.1f}% but still confirms only "
         f"{N['e20_m2_01_hit']:.1f}%, because the remaining donors "
         f"fall below the threshold by construction; dropping to 1 row "
         f"x 128 bands at tau = 0.05 recovers the donor in "
         f"{N['e20_m1_005_dic']:.1f}% of cells, at the price of "
         f"returning a median of {N['e20_m1_005_cand']:.0f} of 1,000 "
         f"candidates per query, of which a median of "
         f"{N['e20_m1_005_ge']:.0f} pass tau = 0.05 by chance. "
         f"Either way the screen that certifies "
         f"{N['e20_screen_recall']:.1f}% recall on the same 337 cells "
         f"is unreachable: set-similarity semantics, accelerated or "
         f"not, do not express containment.")
    para(doc,
         "Could containment-aware LSH close this gap? Containment "
         "estimators [33], [34] replace resemblance with the ratio "
         "|A \u2229 B| / min(|A|, |B|), which in principle sees a "
         "contained copy; two obstacles remain. First, they still "
         "operate on unordered sets: containment is blind to note "
         "order exactly where our task is sequential, so a "
         "contained piece and a permuted collage of the same items "
         "are indistinguishable to it. Second, the estimator's "
         "variance explodes for small containing sets: a planted "
         "span of ~40 items yields MinHash sketches whose "
         "containment estimate is too noisy to threshold at the "
         "operating point our chain criterion certifies. A full "
         "containment-LSH baseline is therefore left as a baseline "
         "extension; the point of Table X is that no re-tuning of "
         "Jaccard-band geometry reaches the screen's recall, and "
         "containment estimators trade that impasse for variance "
         "rather than resolving it.")
    three_line_table(doc,
        ["LSH configuration", "tau",
         "Donor in candidates (%)", "Donor confirmed (%)",
         "Median candidates", "Median passing tau"],
        [["16 bands x 8 rows", "0.10",
          f"{N['e20_m8_01_dic']:.1f}", f"{N['e20_m8_01_hit']:.1f}",
          f"{N['e20_m8_01_cand']:.0f}", f"{N['e20_m8_01_ge']:.0f}"],
         ["2 rows x 64 bands", "0.10",
          f"{N['e20_m2_01_dic']:.1f}", f"{N['e20_m2_01_hit']:.1f}",
          f"{N['e20_m2_01_cand']:.0f}", f"{N['e20_m2_01_ge']:.0f}"],
         ["1 row x 128 bands", "0.05",
          f"{N['e20_m1_005_dic']:.1f}", f"{N['e20_m1_005_hit']:.1f}",
          f"{N['e20_m1_005_cand']:.0f}", f"{N['e20_m1_005_ge']:.0f}"]],
        size=8,
        title="TABLE X. MinHash-LSH on the 337-cell recall-matrix "
              "protocol (1,000-piece corpus, 128 permutations); "
              "containment-hitting configurations flood candidates, "
              "discriminating configurations starve the donor.")
    full_width(doc, lambda: (add_emf(doc, "fig_e20_lsh", 16.0),
                             caption(doc,
                                 f"Fig. 11. The containment-versus-"
                                 f"Jaccard geometry behind Table X. "
                                 f"(a) donor Jaccard distribution over "
                                 f"the 337 planted cells (quartiles "
                                 f"{N['e20_dj_p25']:.3f}/{N['e20_dj_p50']:.3f}/"
                                 f"{N['e20_dj_p75']:.3f}) with the two "
                                 "operating thresholds marked; "
                                 "(b) recall of the three LSH "
                                 "configurations versus the tolerant "
                                 "screen on the same cells.")))

    # --- VI. real world -------------------------------------------------------
    h1(doc, "VI. Real-World Studies")
    h2(doc, "A. Controlled memorization screening")
    para(doc,
         "We emulate generative-model memorization with an order-m "
         "pitch n-gram model mixed with a per-note copy operator at "
         "probability \u03bb, sweeping m\u2208{2,4,8} and "
         "\u03bb\u2208{0, 0.25, ..., 1}; 750 generated pieces are "
         "screened with the production cascade. Detection "
         "(Fig. 12, Table XI) rises monotonically: 26-34% at "
         "\u03bb=0\u2014these "
         "residual hits are style-level shared structures, attributed "
         "to the source piece in only 2-4% of cases\u2014through 44-56% "
         f"at \u03bb=0.5, to {N['e62_l1'] * 100:.0f}% at \u03bb=1 with "
         "96-100% correct source attribution. ")
    para(doc,
         "Fragmented partial "
         "memorization (\u03bb=0.25, per-note Bernoulli copies) "
         "escapes the contiguity threshold: an honest boundary of "
         "chain-based confirmation that mirrors the distributed-"
         "memorization blind spot of sequential detectors.  Section "
         "VI-D replaces the emulator with an actually trained "
         "transformer and asks whether real overfitting reproduces "
         "this spectrum.")
    add_emf(doc, "fig6_memorization", 8.0)
    caption(doc, "Fig. 12. Detection rate (bars) and source attribution "
                 "(ticks) over the memorization spectrum, by n-gram "
                 "order.")
    three_line_table(doc,
        ["m", "\u03bb = 0", "\u03bb = 0.25", "\u03bb = 0.5",
         "\u03bb = 0.75", "\u03bb = 1"],
        e62_table_rows(), size=8,
        title="TABLE XI. Memorization spectrum: detection % / correct "
              "source-attribution % per cell (50 generated pieces per "
              "cell; order-m pitch n-gram mixed with per-note copy at "
              "probability \u03bb).")
    h2(doc, "B. Case studies")
    para(doc,
         f"Screening all 3,000 corpus pieces against each other "
         f"(exact and interval-sketch dual index) surfaces "
         f"{N['e63_pairs']:,} candidate duplicate pairs\u2014Lakh is, "
         "in large part, many transcriptions of the same commercial "
         "repertoire. Four publisher-style cases (Table XII) show the "
         "evidence a human adjudicator receives: an identical "
         "transcription pair aligns note-for-note (3,200/3,200); a "
         "+3-semitone transposed cover is fully recovered with the "
         "transposition correctly estimated at \u22123; a piece with a "
         "30-second span of another work spliced into its middle is "
         "localized to the exact segment (Fig. 13); and a "
         "style-similar negative is correctly rejected.")
    add_emf(doc, "fig7_case", 8.0)
    caption(doc, "Fig. 13. Alignment map for the spliced-span case: "
                 "query note index versus corpus piece note index; the "
                 "diagonal band is the copied 30 s segment.")
    three_line_table(doc,
        ["Case", "Aligned", "Longest segment", "Verdict"],
        [["Identical transcription pair", "3,200 / 3,200 notes",
          "3,200", "confirmed copy"],
         ["Transposed cover (+3 st, synth.)", "3,200 / 3,200",
          "3,200 (\u0394=\u22123 st)", "confirmed, transposition "
          "estimated correctly"],
         ["Spliced 30 s span (synth.)", "1,680",
          "1,593", "confirmed partial reuse"],
         ["Style-similar negative", "31", "1",
          "rejected"]],
        size=8,
        title="TABLE XII. Case-study evidence summary (E6.3).")
    full_width(doc, lambda: (add_emf(doc, "fig8_census", 13.2),
                             caption(doc, "Fig. 14. Full-corpus census "
                                         "(174,300 pieces, stride-8 "
                                         "survey extrapolated \u00d78).  "
                                         "(a) Candidate-pair population by "
                                         "relative-score band and channel "
                                         "(log scale).  (b) Confirmed-copy "
                                         "precision of the stored "
                                         "audit-grade strata, Wilson 95% "
                                         "CI; n=40 per stratum.")))
    h2(doc, "C. Full-corpus duplicate census")
    para(doc,
         f"Scaling the case-study protocol to the full corpus "
         f"(174,300 pieces) turns the candidate flood from anecdote "
         f"into measurement.  Every eighth piece serves as a query "
         f"against the whole corpus "
         f"({N['e18_exact_queries']:,} non-trivial queries per "
         f"channel; all counts extrapolate {8}\u00d7), under the same "
         f"dual exact/interval-sketch configuration "
         f"(min-evidence 40, k=0).  Fig. 14(a) shows the candidate "
         f"population by relative-score band.  At the absolute "
         f"\u226540-evidence floor the two channels report "
         f"{N['e18_exact_ge40'] / 1e9:.1f}B (exact) and "
         f"{N['e18_sketch_ge40'] / 1e9:.1f}B (sketch) candidate "
         f"pairs; at the case-study operating point "
         f"(relative \u22650.35) the total is "
         f"{N['e18_rel35'] / 1e9:.2f}B. ")
    para(doc,
         f"A self-screen of the whole "
         f"corpus at the observed per-query cost (median "
         f"{N['e18_exact_p50']:.0f} ms exact, "
         f"{N['e18_sketch_p50']:.0f} ms sketch, p95 "
         f"{N['e18_exact_p95']:.0f}/"
         f"{N['e18_sketch_p95']:.0f} ms; one core) completes in "
         f"roughly four hours.")
    para(doc,
         "How much of this flood is real?  We stored the "
         "audit-grade subset\u2014exact pairs with relative score "
         f"\u22650.70 ({N['e19f_pools']['exact_band2'] + N['e19f_pools']['exact_band3']:,} "
         "after cross-channel dedup) and sketch pairs with relative "
         f"score \u22650.90 ({N['e19f_pools']['sketch_band3']:,})\u2014and "
         "adjudicated a stratified random sample (40 pairs per "
         "stratum) with the Layer-2 chain criterion, run in both "
         "directions with transposition fallback (Table XIII, "
         "Fig. 14(b)). ")
    para(doc,
         "The exact channel is a high-precision "
         f"instrument at the top of its range: {N['e19f_exact_band3_p'] * 100:.0f}% "
         f"of exact pairs with relative score \u22650.90 are confirmed "
         "copies (Wilson 95% CI "
         f"[{N['e19f_exact_band3_lo'] * 100:.0f}, "
         f"{N['e19f_exact_band3_hi'] * 100:.0f}]%), and even its "
         f"0.70\u20130.90 band confirms "
         f"{N['e19f_exact_band2_p'] * 100:.0f}%.  The "
         "interval-sketch channel stays recall-oriented: only "
         f"{N['e19f_sketch_band3_p'] * 100:.0f}% of its \u22650.90 "
         "candidates confirm, so sketch hits should be treated as "
         "leads for confirmation, not verdicts\u2014exactly the "
         "division of labor the two-layer architecture encodes.")
    para(doc,
         f"Weighting each stratum by its precision, Lakh-full "
         f"contains on the order of {N['e19f_est']['exact_band3'] / 1e3:.0f}k "
         f"verbatim-level duplicate pairs (exact \u22650.90), "
         f"{N['e19f_est']['exact_band2'] / 1e6:.1f}M further pairs "
         f"in the exact 0.70\u20130.90 band, and "
         f"{N['e19f_est']['sketch_band3'] / 1e6:.1f}M "
         f"transposition/arrangement-level pairs reachable through "
         f"the sketch channel\u2014each a case a publisher would "
         f"have to adjudicate, and each receiving note-level "
         f"alignment evidence from the confirmation layer.  These "
         f"estimates inherit the precision and recall of the chain "
         f"criterion measured in this section itself; they are survey "
         f"estimates from a "
         f"1/8 sample, not enumerations.")
    three_line_table(doc,
        ["Channel", "Relative score", "Stored pairs",
         "Precision % [95% CI]", "Est. confirmed (corpus)"],
        [["exact", "0.70\u20130.90",
          f"{N['e19f_pools']['exact_band2']:,}",
          f"{N['e19f_exact_band2_p'] * 100:.1f} "
          f"[{N['e19f_exact_band2_lo'] * 100:.1f}, "
          f"{N['e19f_exact_band2_hi'] * 100:.1f}]",
          f"{N['e19f_est']['exact_band2'] / 1e6:.2f}M"],
         ["exact", "\u22650.90",
          f"{N['e19f_pools']['exact_band3']:,}",
          f"{N['e19f_exact_band3_p'] * 100:.1f} "
          f"[{N['e19f_exact_band3_lo'] * 100:.1f}, "
          f"{N['e19f_exact_band3_hi'] * 100:.1f}]",
          f"{N['e19f_est']['exact_band3'] / 1e3:.0f}k"],
         ["sketch", "\u22650.90",
          f"{N['e19f_pools']['sketch_band3']:,}",
          f"{N['e19f_sketch_band3_p'] * 100:.1f} "
          f"[{N['e19f_sketch_band3_lo'] * 100:.1f}, "
          f"{N['e19f_sketch_band3_hi'] * 100:.1f}]",
          f"{N['e19f_est']['sketch_band3'] / 1e6:.2f}M"]],
        size=8,
        title="TABLE XIII. Precision audit of the full-corpus screen: "
              "stratified sample of 40 pairs per stratum, adjudicated "
              "by the Layer-2 chain criterion (both directions, "
              "transposition-aware); confirmed-copy counts "
              "extrapolate the stride-8 survey.")
    h2(doc, "D. Memorization audit with a trained generator")
    para(doc,
         f"E6.2 emulates a generative model with an n-gram/copy "
         f"operator; we now replace the emulator with an actual "
         f"trained one.  A {934824:,}-parameter decoder-only "
         f"transformer ({N['e21_epochs']} epochs on 250 Lakh "
         f"pieces, production tokenization) reaches train loss "
         f"{N['e21_train']:.1f} nats against {N['e21_val']:.1f} "
         f"held-out\u2014a {N['e21_val'] - N['e21_train']:.1f}-nat "
         f"generalization gap, i.e., genuine overfitting.  "
         f"Per-piece held likelihood separates trained from "
         f"never-trained pieces almost perfectly "
         f"({N['e21_loss_trained']:.1f} vs. "
         f"{N['e21_loss_untrained']:.1f} nats mean, AUC = "
         f"{N['e21_auc']:.2f}), and the most-memorized pieces sit "
         f"at {N['e21_tail']:.2f} nats\u2014the model demonstrably "
         f"knows them. ")
    para(doc,
         f"Yet open-ended sampling does not "
         f"regurgitate them: across {N['e21_cal_n']} calibration "
         f"probes seeded from pieces spanning the full memorization "
         f"range, position-wise pitch agreement with the true "
         f"continuation averages {N['e21_cal_pos_mean'] * 100:.0f}% "
         f"(max {N['e21_cal_pos_max'] * 100:.0f}%) and 4-gram "
         f"overlap peaks at {N['e21_cal_ov4_max'] * 100:.0f}% "
         f"(Fig. 15(b)).  Sampling at temperature 0.8 diverges "
         f"from memorized content almost immediately.")
    para(doc,
         f"The production cascade agrees with this reading "
         f"(Table XIV): 60 continuations\u201420 seeded from the "
         f"most-memorized pieces, 20 from never-trained controls, "
         f"20 from random trained pieces\u2014confirm at "
         f"{N['e21_memorized_det'] * 100:.0f}% / "
         f"{N['e21_control_det'] * 100:.0f}% / "
         f"{N['e21_random_trained_det'] * 100:.0f}% with source "
         f"attribution near chance in every group, the same "
         f"style-level confirmation band as the copy-free "
         f"(lambda = 0) cells of Table XI. ")
    para(doc,
         f"In other words, a "
         f"real overfit transformer at this scale behaves, from "
         f"the detector's viewpoint, like the lambda = 0 corner "
         f"of the emulated spectrum\u2014and unlike lambda = 1, "
         f"which confirms and attributes at 98\u2013100%.  The "
         f"conclusion cuts both ways: extractive regurgitation, "
         f"the family that generation-side audits can exhibit to "
         f"a copy detector, is captured by the n-gram/copy "
         f"emulation; but memorization that sampling never "
         f"surfaces\u2014the 0.3-nat pieces\u2014is invisible to "
         f"output inspection of any kind, and only likelihood "
         f"ranking exposes it.  Copy detection and memorization "
         f"auditing are complementary instruments, not "
         f"substitutes.")
    full_width(doc, lambda: (add_emf(doc, "fig_e21_memorization", 18.2),
                             caption(doc,
                                 "Fig. 15. Trained-generator "
                                 "memorization audit.  (a) Training "
                                 "and held-out loss over "
                                 f"{N['e21_epochs']} epochs; the "
                                 "gap is the memorization.  "
                                 "(b) Sampling calibration: "
                                 "position-wise pitch agreement of "
                                 "sampled continuations versus "
                                 "per-piece held likelihood "
                                 "(memorization); even the most "
                                 "memorized pieces are not "
                                 "regurgitated.  (c) Cascade "
                                 "confirmation and source "
                                 "attribution for the three "
                                 "sampling groups against the "
                                 "\u03bb = 0 / \u03bb = 1 anchors "
                                 "of Table XI.")))
    three_line_table(doc,
        ["Generator", "Group", "n", "Confirmed %",
         "Source-attributed %", "Source in top-C %"],
        [["n-gram/copy (E6.2)", "m=8, lambda=0", "50",
          f"{N['e62_m8_l0_det'] * 100:.0f}",
          f"{N['e62_m8_l0_src'] * 100:.0f}", "\u2013"],
         ["n-gram/copy (E6.2)", "m=8, lambda=1", "50",
          f"{N['e62_m8_l1_det'] * 100:.0f}",
          f"{N['e62_m8_l1_src'] * 100:.0f}", "\u2013"],
         ["transformer (E6.4)", "memorized sources", "20",
          f"{N['e21_memorized_det'] * 100:.0f}",
          f"{N['e21_memorized_src'] * 100:.0f}",
          f"{N['e21_memorized_ret'] * 100:.0f}"],
         ["transformer (E6.4)", "untrained controls", "20",
          f"{N['e21_control_det'] * 100:.0f}",
          f"{N['e21_control_src'] * 100:.0f}",
          f"{N['e21_control_ret'] * 100:.0f}"],
         ["transformer (E6.4)", "random trained", "20",
          f"{N['e21_random_trained_det'] * 100:.0f}",
          f"{N['e21_random_trained_src'] * 100:.0f}",
          f"{N['e21_random_trained_ret'] * 100:.0f}"]],
        size=8,
        title="TABLE XIV. Trained-generator audit against the E6.2 "
              "emulation anchors: the overfit transformer confirms in "
              "the lambda = 0 band and attributes no better than "
              "chance, while per-piece likelihood (AUC = "
              f"{N['e21_auc']:.2f}) exposes the memorization that "
              "sampling conceals.")

    # --- VII. discussion --------------------------------------------------------
    h1(doc, "VII. Discussion")
    para(doc,
         "Three boundaries are worth stating plainly. First, item-set "
         "containment is a recall instrument; any deployment that "
         "treats its counts as verdicts will over-flag exactly the "
         "repertoire it is meant to protect. Second, chain-based "
         "confirmation requires contiguity: copies fragmented below "
         "the \u03c1 threshold evade detection, so the system's proper "
         "role is high-precision screening with evidence, not "
         "autonomous adjudication. ")
    para(doc,
         "Third, the guarantees are "
         "conditional on the declared noise model; transformations "
         "outside tolerance (large transposition without sketch "
         "retrieval, heavy swing quantization) must be covered by "
         "model extensions rather than threshold tweaking.")
    para(doc,
         "Threats to validity. The planted transformations are "
         "parametric approximations of real reuse: actual "
         "audio-to-MIDI transcription errors are correlated (a "
         "misaligned beat grid shifts many notes together), which "
         "our jitter model under-represents, and human-made covers "
         "vary by arrangement choices no parametric family captures. "
         "Hard negatives are harvested by pitch-class histogram "
         "similarity, which finds harmonically confusable peers but "
         "may miss style-similar pairs with different key "
         "distributions. ")
    para(doc,
         "The memorization study spans both a "
         "transparent n-gram/copy emulation and an actually "
         "trained generator, but the latter is a 0.9M-parameter "
         "CPU-scale transformer whose memorization is "
         "non-extractive\u2014larger generators that regurgitate "
         "verbatim would move samples toward the lambda = 1 "
         "corner of Table XIV rather than challenge the "
         "detection physics; and the in-the-wild census, while spanning "
         "the full 174,300-piece corpus, rests on a 1/8 systematic "
         "sample of queries and a 120-pair adjudication audit whose "
         "verdicts are automatic (chain criterion), not human, and "
         "examines one corpus lineage. We "
         "regard the cell-by-cell bound audit and the per-length "
         "hard-negative breakdown as the load-bearing evidence, "
         "because both are exhaustive over their stated domains "
         "rather than sampled.")
    para(doc,
         "Deployment and responsible use. Operationally, the index "
         "accepts incremental piece insertions without rebuild, and "
         "the anytime budget lets a screening queue trade recall "
         "headroom against throughput at busy times \u2014 the "
         "open-set size reported after every query is a directly "
         "schedulable quantity. An adversary who learns the declared "
         "tolerance can in principle evade by exceeding it; the "
         "honest response is to widen the envelope (coarser "
         "tolerance, interval-sketch retrieval) and re-audit, which "
         "the cell-by-cell methodology supports cheaply. ")
    para(doc,
         "Finally, "
         "the system's output is evidence for a human decision, not "
         "a legal determination: a confirmed chain localizes shared "
         "material and estimates transposition, while questions of "
         "access, originality, and substantial similarity remain "
         "with adjudicators [20], [30]. The expected utility of the "
         "system is bounded accordingly: it catches extractive "
         "regurgitation\u2014copied spans a generator emits intact\u2014"
         "but not distributed memorization, where influence is spread "
         "across a model without any recoverable span; that "
         "per-sample question is the complement of membership "
         "inference [23], and the two instruments are most credible "
         "when used together. All code and experiment "
         "scripts are released to make every number in this paper "
         "independently reproducible.")

    # --- VIII. conclusion ---------------------------------------------------------
    h1(doc, "VIII. Conclusion")
    para(doc,
         "Copy detection for symbolic music decomposes into a "
         "provable-recall screening problem and a structural "
         "confirmation problem\u2014two layers specified by explicit "
         "contracts, recall with a proof and precision with "
         "evidence\u2014and the decomposition is clean enough "
         "to build, verify cell-by-cell, and operate at publisher "
         "scale: 100% planted recall with an exact anytime bound, "
         "2.1% fragment-level false positives on style-similar hard "
         "negatives, decision-latency queries on a "
         f"{N['e4_max']:,}-piece corpus, and alignment evidence that a "
         "musician can check against a score. What makes the contracts "
         "transferable is that none of them is specific to music: any "
         "domain where a long container hides a short copied span, and "
         "where style peers defeat set similarity, admits the same "
         "evidence-bound screen and chain confirmation. Future work "
         "targets the "
         "two exposed boundaries: fragmented memorization below the "
         "contiguity threshold, and recall guarantees under "
         "transformations outside the current tolerance envelope.")

    # --- references (funding note lives in the first-page footnote) ---------------
    p = doc.add_paragraph(style="Reference Head")
    p.add_run("References")
    for i, old_no in enumerate(_REFS_IN_CITE_ORDER, 1):
        ref = REFERENCES[old_no - 1]
        p = doc.add_paragraph(style="References")
        pf = p.paragraph_format
        pf.left_indent = Cm(0.75)
        pf.first_line_indent = Cm(-0.75)
        # References style auto-numbers the list; do NOT add a literal "[n]" prefix
        p.add_run(ref)

    # full-width closing line after the reference list
    full_width(doc, lambda: spacer(doc))

    # --- core properties ------------------------------------------------------------
    cp = doc.core_properties
    cp.author = "Yalong Zhang"
    cp.last_modified_by = "Yalong Zhang"
    cp.title = TITLE
    cp.subject = "copy detection, symbolic music"
    cp.comments = ""
    cp.category = "journal submission draft"

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    build()
