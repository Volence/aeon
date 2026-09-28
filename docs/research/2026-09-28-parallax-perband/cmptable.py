#!/usr/bin/env python3
"""cmptable — before/after table for two legs.sh output dirs (the 2026-09-27 final_table's rules,
plus the parallax cycles per tick from the profile).

usage: cmptable.py BEFORE_DIR AFTER_DIR [LEG ...]
Per leg:
  * lag / video frames over the SAME tick span (both cut at the smaller tick count);
  * the player path compared tick by tick (ticks off, max dx/dy);
  * Parallax_Update cycles per tick, INCLUSIVE (the whole pipeline: Step 1-5, the fill, the
    decodes), whole leg, before -> after;
  * the parallax OUTPUT (Hscroll_Buffer 896 B + Parallax_Vscroll_Column_Buf 80 B +
    Vscroll_Factor 4 B) compared at every tick both legs recorded with an agreeing camera.
    Camera-mismatch ticks are counted, never compared.
For `debug_diag` it also prints Emerald Hill's band (camera y < 1024) lag and the parallax
cycles of profile segment 0 (camera x 0..1023, the same band on a 16/16 diagonal).
Exit 1 if any compared tick differs, 2 if a leg is missing or compared nothing, else 0.
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


def pxcyc(h, segs=None):
    segs = [g for g in h["segs"] if "profile" in g] if segs is None else segs
    t = sum(g["profile"]["ticks"] for g in segs)
    c = sum(r["cyclesTotal"] for g in segs for r in g["profile"]["items"]
            if r.get("name") == "Parallax_Update")
    return c / t if t else float("nan")


def main():
    B, A = sys.argv[1:3]
    legs = sys.argv[3:] or LEGS
    bad = miss = 0
    print(f"{'leg':<13} {'lag/frames before':>18} {'after':>13} {'ticks':>6}  {'parallax cyc/tick':>22}  "
          f"path                        output identity")
    for leg in legs:
        pb, pa = os.path.join(B, leg + ".json"), os.path.join(A, leg + ".json")
        if not (os.path.exists(pb) and os.path.exists(pa)):
            print(f"{leg:<13} DID NOT RUN")
            miss += 1
            continue
        b, a = json.load(open(pb)), json.load(open(pa))
        n = min(sum(r[2] for r in b["rows"]), sum(r[2] for r in a["rows"]))
        (fb, lb), (fa, la) = cut(b, n), cut(a, n)
        P, Q = b["path"], a["path"]
        com = [t for t in set(P) & set(Q) if int(t) <= n]
        pd = [t for t in com if P[t][:2] != Q[t][:2]]
        mdy = max((abs(P[t][1] - Q[t][1]) for t in pd), default=0)
        mdx = max((abs(P[t][0] - Q[t][0]) for t in pd), default=0)
        D, E = b["dumps"], a["dumps"]
        dc = [t for t in set(D) & set(E) if D[t][:2] == E[t][:2]]
        cam_bad = len(set(D) & set(E)) - len(dc)
        dd = sum(1 for t in dc if D[t][2] != E[t][2])
        if not dc:
            miss += 1
        bad += dd
        print(f"{leg:<13} {fb - lb:>7} / {fb:<9} {fa - la:>4} / {fa:<6} {n:>6}  "
              f"{pxcyc(b):>9.0f} -> {pxcyc(a):>8.0f}  "
              f"{len(pd):>3} ticks off (dx {mdx}, dy {mdy})  "
              f"{dd} of {len(dc)} ticks differ ({cam_bad} cam-mismatch skipped)")
        if leg == "debug_diag":
            (lb2, fb2), (la2, fa2) = band(b), band(a)
            s0b = [g for g in b["segs"] if "profile" in g][:1]
            s0a = [g for g in a["segs"] if "profile" in g][:1]
            print(f"{'':<13} Emerald Hill band (cam y < 1024): {lb2}/{fb2} -> {la2}/{fa2}; "
                  f"parallax seg0 {pxcyc(b, s0b):.0f} -> {pxcyc(a, s0a):.0f}")
    print(f"finished=1 differing_ticks={bad} legs_missing_or_empty={miss}")
    sys.exit(1 if bad else (2 if miss else 0))


if __name__ == "__main__":
    main()
