#!/usr/bin/env python3
"""decomp.py <parallax.emp> — MEASUREMENT-ONLY rewrite of the parallax pipeline, in place.

The pipeline is one call (Parallax_Update) whose later steps are TAIL BRANCHES (jbra Step5 ->
jbra Step4 -> jbra Fill), and the oracle profiler attributes by call, so on a shipped build
every step's cycles land in Parallax_Update's self column. This rewrite, the same move as the
2026-09-27 study's "decomposition build", turns each tail branch into `jbsr X / rts` and lifts
two regions of Parallax_Step4_Fill into their own procs, so each part gets its own row:

  Parallax_Update self   Step 1-3: config select, reg $0B, the per-band factor/lerp loop
  Decode_Factor_A / _B   the factor decodes (already calls)
  Parallax_Step5_Vscroll Step 5 (+ 5b per-column, if any)
  PxM_Step4a             Step 4a: find k + the whole-record rotate/copy into the shadow view
  PxM_CurveHoist         the per-frame curve hoist (both divides)
  Parallax_Step4_Fill    what is left: 4b's anchored overlay + the phase advance
  Parallax_Fill_PerLine  the fill: per-band dispatch AND the line loops, together

Each added jbsr/rts costs 34 cycles per tick per call (18 + 16), which is a measurement
overhead, not a pipeline cost; the report subtracts nothing and says so. Build with FAST=1:
the ROM is not a shipped ROM, its bytes and timings differ, and it only prices parts.
"""
import re
import sys

p = sys.argv[1]
s = open(p).read()


def once(old, new):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"decomp: expected exactly one {old[:60]!r}, found {n}")
    s = s.replace(old, new)


once("        jbra    Parallax_Step5_Vscroll\n",
     "        jbsr    Parallax_Step5_Vscroll\n        rts\n")
once("        jbra    Parallax_Step4_Fill         // Step 4 runs after Vscroll is final\n",
     "        jbsr    Parallax_Step4_Fill\n        rts\n")
once("        jbra    Parallax_Fill_PerLine               // tail call; it preserves a0/d7 itself\n",
     "        jbsr    Parallax_Fill_PerLine\n        rts\n")

# Step 4a: from the proc's first instruction to the copy loop's dbf.
a0 = s.index("        move.w  Parallax_Current_Vscroll_BG, d0     // (Parallax_Current_Vscroll_BG).w\n"
             "        and.w   #PLANE_B_SPAN-1, d0")
a1 = s.index("        dbf     d6, .copy_band\n", a0) + len("        dbf     d6, .copy_band\n")
body4a = s[a0:a1]
s = s[:a0] + "        jbsr    PxM_Step4a\n" + s[a1:]

h0 = s.index("    .cap_factor_curve_hoist_begin:\n") + len("    .cap_factor_curve_hoist_begin:\n")
h1 = s.index("    .cap_factor_curve_hoist_end:\n")
bodyh = s[h0:h1]
s = s[:h0] + "        jbsr    PxM_CurveHoist\n" + s[h1:]

s += ("\nproc PxM_Step4a () clobbers(d0-d6/a1/a4-a6) {\n" + body4a + "        rts\n}\n"
      "\nproc PxM_CurveHoist () clobbers(d0-d6/a1/a3) {\n    if (Game.SCANLINE_CAPS & CAP_FACTOR_CURVE) != 0 {\n" + bodyh + "    }\n        rts\n}\n")
open(p, "w").write(s)
print("decomp: rewritten", p)
