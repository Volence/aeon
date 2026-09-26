#!/usr/bin/env python3
"""final_table — before/after table for two final_legs.sh output dirs.

usage: final_table.py BEFORE_DIR AFTER_DIR
Per leg: lag / video frames over the SAME tick span (spancmp's rule: both cut at the smaller
tick count), the player path compared tick by tick, the worst undrawn visible cells (coverage:
right/left/bottom/top, > 0 = a hole on screen) on each side, and the parallax output compared
at every tick both recorded with an agreeing camera (dumpcmp's rule). For the S2 clip's fly
diag it also prints the Emerald Hill band (camera y < 1024) lag.
"""
import json
import os
import sys

LEGS = ["plain_run", "plain_spin", "debug_run", "debug_spin", "debug_diag", "debug_right",
        "debug_down", "cdebug_diag", "cdebug_right", "cdebug_down", "cplain_run", "cdebug_run"]


def cut(h, n):
    fr = lt = 0
    for r in h["rows"]:
        if lt >= n:
            break
        fr += r[1]
        lt += r[2]
    return fr, lt


def band(h):
    b = [x for x in h["rows"] if x[5] < 1024]
    return sum(x[1] for x in b) - sum(x[2] for x in b), sum(x[1] for x in b)


def main():
    B, A = sys.argv[1:3]
    print(f"{'leg':<13} {'before lag/frames':>18} {'after lag/frames':>17} {'ticks':>6}  path          "
          f"coverage max before -> after            parallax output")
    for leg in LEGS:
        pb, pa = os.path.join(B, leg + ".json"), os.path.join(A, leg + ".json")
        if not (os.path.exists(pb) and os.path.exists(pa)):
            print(f"{leg:<13} DID NOT RUN")
            continue
        b, a = json.load(open(pb)), json.load(open(pa))
        n = min(sum(r[2] for r in b["rows"]), sum(r[2] for r in a["rows"]))
        (fb, lb), (fa, la) = cut(b, n), cut(a, n)
        P, Q = b["path"], a["path"]
        com = [t for t in set(P) & set(Q) if int(t) <= n]
        pd = [t for t in com if P[t][:2] != Q[t][:2]]
        mdy = max((abs(P[t][1] - Q[t][1]) for t in pd), default=0)
        mdx = max((abs(P[t][0] - Q[t][0]) for t in pd), default=0)
        cvb = [max(r[k] for r in b["coverage"]) for k in (1, 2, 3, 4)]
        cva = [max(r[k] for r in a["coverage"]) for k in (1, 2, 3, 4)]
        D, E = b["dumps"], a["dumps"]
        dc = [t for t in set(D) & set(E) if D[t][:2] == E[t][:2]]
        cam_bad = len(set(D) & set(E)) - len(dc)
        dd = sum(1 for t in dc if D[t][2] != E[t][2])
        print(f"{leg:<13} {fb - lb:>7} / {fb:<8} {fa - la:>6} / {fa:<8} {n:>6}  "
              f"{len(pd):>3} ticks off (max dx {mdx}, dy {mdy})  {cvb} -> {cva}  "
              f"{dd} of {len(dc)} ticks differ ({cam_bad} camera-mismatch ticks skipped)")
        if leg == "debug_diag":
            (lb2, fb2), (la2, fa2) = band(b), band(a)
            print(f"{'':<13} Emerald Hill band (cam y < 1024): {lb2}/{fb2} -> {la2}/{fa2}")


if __name__ == "__main__":
    main()
