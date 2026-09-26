#!/usr/bin/env python3
"""legtable — lag frames per leg across build sets, over the SAME span of logic ticks.

usage: legtable.py NAME=DIR [NAME=DIR ...]
Each DIR holds one JSON per leg (ojz_feel_probe output). For each leg present in every DIR,
all sets are cut at the smallest tick count any of them reached (a lag frame never changes a
tick-keyed path, but a leg that ends on a tick budget ends at the same tick everywhere; the cut
is a guard, and it is printed). Lag = sum(dFrame_Counter) - sum(dLogic_Tick) over the cut.
Also reports whether the player path agrees tick by tick with the first set (px,py,cx,cy per
completed tick), as a count of ticks that differ.
"""
import json
import sys
from pathlib import Path

sets = [a.split("=", 1) for a in sys.argv[1:]]
legs = sorted(set.intersection(*[{p.stem for p in Path(d).glob("*.json") if not p.stem.endswith(("_win", "_cache"))} for _, d in sets]))


def cut(rows, T):
    out, t = [], 0
    for r in rows:
        if t >= T:
            break
        out.append(r)
        t += r[2]
    return out


def path(rows):
    p, t = {}, 0
    for r in rows:
        if r[2]:
            t += r[2]
            p[(r[11], t)] = tuple(r[4:8])
    return p


hdr = f"{'leg':<15}" + "".join(f"{n:>16}" for n, _ in sets) + "   ticks  path-diff vs first"
print(hdr)
tot = [0] * len(sets)
for leg in legs:
    hs = [json.load(open(Path(d) / f"{leg}.json")) for _, d in sets]
    T = min(sum(r[2] for r in h["rows"]) for h in hs)
    cells, diffs = [], []
    p0 = path(cut(hs[0]["rows"], T))
    for k, h in enumerate(hs):
        rows = cut(h["rows"], T)
        lag = sum(r[1] for r in rows) - sum(r[2] for r in rows)
        tot[k] += lag
        cells.append(f"{lag:>5} / {sum(r[1] for r in rows):<6}")
        if k:
            p = path(rows)
            diffs.append(sum(1 for key in p0 if key in p and p[key] != p0[key]))
    print(f"{leg:<15}" + "".join(f"{c:>16}" for c in cells) + f"   {T:>5}  {diffs}")
print(f"{'TOTAL':<15}" + "".join(f"{t:>16}" for t in tot))
