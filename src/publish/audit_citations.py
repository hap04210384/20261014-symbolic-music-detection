# -*- coding: utf-8 -*-
"""Audit figure/table first-citation order vs. physical appearance, and
table physical order, in the rendered PDF."""
import re
import fitz

doc = fitz.open("results/figures/_check/Manuscript.pdf")
pages = [p.get_text() for p in doc]

# --- collect caption locations ------------------------------------------------
fig_caps, tab_caps = {}, {}
for i, t in enumerate(pages):
    for m in re.finditer(r"Fig\. (\d+)\.\s", t):
        fig_caps.setdefault(int(m.group(1)), []).append(i + 1)
    for m in re.finditer(r"TABLE ([IVX]+)\.\s*", t):
        tab_caps.setdefault(m.group(1), []).append(i + 1)

# --- first textual citation (exclude the caption line itself) -----------------
def citations(pattern):
    first = {}
    for i, t in enumerate(pages):
        for m in re.finditer(pattern, t):
            key = m.group(1)
            if key not in first:
                first[key] = i + 1
    return first

fig_cites = citations(r"Fig\. (\d+)[\s,.():]")
tab_cites = citations(r"Table ([IVX]+)[\s,.():]")

def roman(n):
    vals = [("X", 10), ("IX", 9), ("V", 5), ("IV", 4), ("I", 1)]
    out = ""
    for s, v in vals:
        while n >= v:
            out += s
            n -= v
    return out

print("== figures ==")
problems = []
for n in range(1, 16):
    c = fig_cites.get(str(n))
    a = fig_caps.get(n, [None])[0]
    flag = ""
    if c is None:
        flag = "NO CITATION"
    elif a is not None and a > c + 1:
        flag = f"VIOLATION cite p{c} appears p{a}"
    print(f"Fig {n}: cited p{c}  caption p{a}  {flag}")
    if flag:
        problems.append(("fig", n, flag))

print("== tables ==")
for n in range(1, 15):
    r = roman(n)
    c = tab_cites.get(r)
    a = tab_caps.get(r, [None])[0]
    flag = ""
    if c is None:
        flag = "NO CITATION"
    elif a is not None and a > c + 1:
        flag = f"VIOLATION cite p{c} appears p{a}"
    print(f"Table {r}: cited p{c}  title p{a}  {flag}")
    if flag:
        problems.append(("tab", r, flag))

# --- physical order of tables -------------------------------------------------
order = []
for i, t in enumerate(pages):
    for m in re.finditer(r"TABLE ([IVX]+)\.\s", t):
        order.append((i + 1, m.group(1)))
print("== table physical order ==")
print(order)
expected = [roman(k) for k in range(1, 15)]
actual = [r for _, r in order]
print("order ok:", actual == expected)

print("== pages:", len(pages))
print("PROBLEMS:", problems if problems else "none")
