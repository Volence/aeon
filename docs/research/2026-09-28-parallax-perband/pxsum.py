#!/usr/bin/env python3
"""pxsum — parallax cycles per logic tick, by routine, from legs.sh output (profiled legs).

usage: pxsum.py LEGDIR [LEG ...]
For each leg: the ROM (crc, bytes), the tick span, lag / video frames in motion, and for every
Parallax-pipeline routine the INCLUSIVE and SELF cycles per tick summed over all the leg's
profile segments (the probe re-arms the profiler per 1024 px of camera x, so the segments
partition the leg). `*_diag` legs also print segment 0 alone (camera x 0..1023, which on a
16 px/16 px diagonal is camera y ~0..1023: Emerald Hill's band on the clip).
Routine rows not present (e.g. PxM_* on a shipped ROM, where the steps are tail branches and
land in Parallax_Update's self) print as '-'.
"""
import json
import os
import sys

ROUT = ["Parallax_Update", "Decode_Factor_A", "Decode_Factor_B", "Parallax_Step5_Vscroll",
        "PxM_Step4a", "PxM_CurveHoist", "Parallax_Step4_Fill", "Parallax_Fill_PerLine",
        "Parallax_Set_Roles_Swapped", "Parallax_CheckBoundary"]
LEGS = ["plain_run", "plain_spin", "debug_run", "debug_spin", "debug_diag", "debug_right",
        "debug_down", "cdebug_diag", "cdebug_right", "cdebug_down", "cplain_run", "cdebug_run"]


def agg(segs):
    t = sum(g["profile"]["ticks"] for g in segs)
    tot = {}
    for g in segs:
        for r in g["profile"]["items"]:
            nm = r.get("name")
            if nm in ROUT:
                a = tot.setdefault(nm, [0, 0, 0])
                a[0] += r["cyclesTotal"]
                a[1] += r["cyclesSelfTotal"]
                a[2] += r["callsTotal"]
    return t, tot


def line(tag, t, tot):
    cells = []
    for nm in ROUT:
        if nm in tot:
            cells.append(f"{nm}={tot[nm][0] / t:.0f}/{tot[nm][1] / t:.0f}")
    return f"  {tag} ticks={t}: " + "  ".join(cells)


def main():
    d = sys.argv[1]
    legs = sys.argv[2:] or LEGS
    for leg in legs:
        p = os.path.join(d, leg + ".json")
        if not os.path.exists(p):
            print(f"{leg}: DID NOT RUN")
            continue
        h = json.load(open(p))
        m = h["summary"]["motion"]
        segs = [g for g in h["segs"] if "profile" in g]
        print(f"{leg}: {h['rom']} crc={h['crc']} bytes={h['size']} motion lag {m['lag']}/"
              f"{m['video_frames']} ticks {m['ticks']}  (inclusive/self cycles per tick)")
        if not segs:
            print("  NO PROFILE")
            continue
        t, tot = agg(segs)
        print(line("whole", t, tot))
        if leg.endswith("_diag"):
            t0, tot0 = agg(segs[:1])
            print(line(f"seg0 cx {segs[0]['cx_lo']}", t0, tot0))


if __name__ == "__main__":
    main()
