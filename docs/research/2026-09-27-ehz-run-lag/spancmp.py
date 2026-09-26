#!/usr/bin/env python3
"""spancmp — lag of two legs over the SAME span of logic ticks, and whether their paths agree.

usage: spancmp.py A.json B.json
A leg capped by video frames ends at a different tick on a ROM with less lag, so its whole-leg
lag is not comparable. This cuts both legs at N = the smaller tick count and reports, over ticks
1..N: the video frames each needed (= N + lag), and the player path compared tick by tick
(differing ticks counted and the first printed; the path is what makes the span the same work).
"""
import json
import sys


def cut(h, n):
    fr = lt = 0
    for r in h["rows"]:
        if lt >= n:
            break
        fr += r[1]
        lt += r[2]
    return fr, lt


a, b = (json.load(open(p)) for p in sys.argv[1:3])
ta = sum(r[2] for r in a["rows"])
tb = sum(r[2] for r in b["rows"])
n = min(ta, tb)
(fa, la), (fb, lb) = cut(a, n), cut(b, n)
pa, pb = a["path"], b["path"]
common = [t for t in sorted(set(pa) & set(pb), key=int) if int(t) <= n]
diff = [t for t in common if pa[t][:2] != pb[t][:2]]
print(f"span: ticks 1..{n}  A {a['crc']}: {fa - la} lag / {fa} frames   B {b['crc']}: {fb - lb} lag / {fb} frames")
print(f"path: {len(common)} common ticks, {len(diff)} differ"
      + (f" (first {diff[0]}: {pa[diff[0]][:2]} vs {pb[diff[0]][:2]}; max |dy| "
         f"{max(abs(pa[t][1] - pb[t][1]) for t in diff)}, max |dx| {max(abs(pa[t][0] - pb[t][0]) for t in diff)})"
         if diff else ""))
