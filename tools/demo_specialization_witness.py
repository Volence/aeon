#!/usr/bin/env python3
"""Scanline P2 Task 8 — the demo witness: span absence AND an image-level backstop.

Design §8.2 requires BOTH halves and states why: "spans alone can be satisfied by an
inlined leak with no boundary symbol — recorded lesson; the image delta is the
backstop." The two halves fail on different things, and that asymmetry is the entire
reason for having both:

  SPAN half   demo declares SCANLINE_CAPS = 0, so no `$cap_*` boundary symbol may
              appear in its listing. Catches a gate that stopped gating WHILE keeping
              its labels. Blind to a block emitted unconditionally with the labels
              stripped — there is nothing left to look for.

  IMAGE half  demo's emitted bytes for a COMMITTED list of specialised procs must
              equal a COMMITTED total. Catches exactly what the span half cannot:
              bytes that are present with no symbol naming them.

  (a third, pin-free check rides along: every proc hosting a gated span must be
   strictly smaller in demo than in sonic4. It catches a gate that stopped gating
   while keeping its labels, and needs no maintenance — but it is NOT the backstop,
   for the reason below.)

WHY THE IMAGE HALF IS A COMMITTED PIN AND NOT A DERIVED DIFFERENTIAL — measured, not
assumed. The differential was written first and the Task-8 poison walked straight
through it: forcing `Raster_GetChannelBand`'s gated block to emit unconditionally
*with its labels stripped* removed the proc from the derived gated set, so the
differential stopped looking at it and reported OK. Any expectation derived from the
same brackets the span half reads shares its blind spot; breaking that shared fate
needs a reference the poison cannot edit. Hence a committed list and a committed
total: the poison cannot delete a row it does not know about.

WHY THE PIN IS PER-PROC BYTES AND NOT `demo_image_len()`. The plan sketched a ROM
length pin. Measured in this parcel: EVERY elision was absorbed by placer fill —
demo's `EndOfRom` sat at 0x1121C before and after the poison, unmoved, while the ROM
LENGTH moved by the deb2 symbol count alone. A ROM-length pin would have caught this
poison for the wrong reason (it was reading the symbol table) and would be blind to a
leak that swaps symbol bytes for code bytes. Proc bytes read out of the listing are
the image measurement the plan wants; fill sits between procs, not inside them.

RE-DERIVE, DO NOT RE-BASELINE. When a pinned proc legitimately changes size, work out
WHY before touching the number — a pin quietly bumped to match a build is the failure
mode this suite exists to prevent.

Usage:
    python3 tools/demo_specialization_witness.py [--sonic4-lst s4.debug.lst]
                                                 [--demo-lst demo.debug.lst]
Exit: 0 both halves pass · 1 a half failed · 2 could not run (missing listing)

POST-BUILD ONLY. It reads listings, so it cannot live in build.sh's pytest lane,
which runs BEFORE sigil. Its runner is tools/effects_gates.py.
"""

import argparse
import os
import sys

from scene_spans import (AEON, capability_bits, expected_spans, game_caps,
                         gated_procs, lst_proc_sizes, lst_spans)

# ---------------------------------------------------------------------------
# THE PIN. Measured on demo.debug.lst at P2 Phase 1 + the CAP_TRANSITIONS parcel — all
# five capabilities now gated (CAP_ANCHORS, CAP_PER_COL_VSRAM, CAP_DEFORM, CAP_PER_LINE,
# CAP_TRANSITIONS).
#
# The NAMES are as load-bearing as the numbers: this list is the reference the derived
# scans cannot edit, which is the whole point (see the module docstring's poison
# note). A proc that stops being specialised is removed here DELIBERATELY, with the
# reason written down — never because a build disagreed.
#
# Sizes are listing head-to-next-head, so they include the inter-proc alignment pad.
# That pad is part of what demo emits, so pinning it is correct; it also means an
# unrelated section moving next door shifts a row by a couple of bytes, and THAT is a
# real event worth looking at rather than smoothing over.
#
# RE-DERIVATION LOG — 2026-08-19, the CAP_TRANSITIONS parcel. The pin FAILED on this
# parcel's build and it was right to: two rows moved and one proc joined the set. Each
# was traced to its cause before the number was touched, which is the discipline the
# failure message demands:
#
#   Parallax_StartTransition  108 -> 90  (-18)  the smooth-staging arm elided
#                                               (cap_transitions_stage)
#   Parallax_Step5_Vscroll     78 -> 62  (-16)  the vscroll lerp elided
#                                               (cap_transitions_lerp)
#   Parallax_Active_Config    NEW  ->  6         joins the set: it hosted no gated span
#                                               before, and cap_transitions_select now
#                                               collapses it to the else arm's
#                                               `move.l Current_Config, d0 / rts`
#                                               (sonic4 18, so -12)
#
# The other five rows are unchanged, which is the corroboration that matters: a parcel
# that moved rows it had no business moving would show up here as an unexplained row,
# not as a total that happens to differ.
#
# RE-DERIVATION LOG — 2026-08-20, P3 Task 7 (world-Y re-glue). The pin FAILED and was
# right to. ONE row moved: Parallax_Step4_Fill, demo 176 -> 170 (-6), sonic4 536 -> 528
# (-8). Derived instruction by instruction from the source change BEFORE the number was
# touched — the shared Step-4a part accounts for demo's -6 and the anchored overlay adds
# sonic4's extra -2:
#
#   Step 4a (both shapes)
#     -2  `lsr.w #3, d0`            deleted — the rotation works in plane LINES now, so
#                                   Vscroll_BG is no longer quantised to cells
#     -2  `moveq #0, d3` (.find_k)  deleted — the top read became `move.w`, which needs no
#                                   zero-extend (the byte read did)
#     -2  `moveq #0, d3` (rebase)   deleted — same reason
#     +2  `moveq #28` -> `move.w #224`   the off-screen clamp is a line count now, and 224
#                                   does not fit a moveq
#     -2  `lsl.w #3, d3`            deleted — no cells->lines conversion left to do
#     ------                        the four field reads/writes that changed width
#                                   (move.b <-> move.w at offset 0 / -10) are the SAME
#                                   size, so they contribute nothing
#     = -6
#   Step 4b, sonic4 only (elided in demo with CAP_ANCHORS)
#     -2  `moveq #0, d2` (.anchor_find_k)  deleted — `move.w band_top_line(a5), d2`
#     = -2, total -8
#
# The two `(sonic4 NNN)` comments below are also corrected against this run: Step4_Fill
# 536 -> 528 (this parcel) and Fill_PerLine 372 -> 686, which went stale at the
# `perf/parallax-unroll` parcel and is recorded here rather than left to mislead. They are
# comments, not pins — the demo number is what this witness enforces.
DEMO_SPECIALISED_PROCS = {
    "Enqueue_Dirty_Buffers":    514,   # CAP_PER_LINE, CAP_ANCHORS  (sonic4 570)
    "Parallax_Active_Config":     6,   # CAP_TRANSITIONS            (sonic4  18)
    "Parallax_Fill_PerLine":      2,   # CAP_PER_LINE, CAP_DEFORM   (sonic4 686) — bare rts
    "Parallax_StartTransition":  90,   # CAP_PER_COL_VSRAM, CAP_TRANSITIONS  (sonic4 118)
    "Parallax_Step4_Fill":      170,   # CAP_ANCHORS, CAP_PER_LINE  (sonic4 528)
    "Parallax_Step5_Vscroll":    62,   # CAP_PER_COL_VSRAM, CAP_TRANSITIONS  (sonic4 144)
    "Raster_GetChannelBand":      8,   # CAP_ANCHORS                (sonic4  50)
    "Vscroll_Write":             26,   # CAP_PER_COL_VSRAM          (sonic4 118)
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sonic4-lst", default=os.path.join(AEON, "s4.debug.lst"))
    ap.add_argument("--demo-lst", default=os.path.join(AEON, "demo.debug.lst"))
    args = ap.parse_args()

    for path in (args.sonic4_lst, args.demo_lst):
        if not os.path.isfile(path):
            print("demo_specialization_witness: listing not found: %s — build both "
                  "fixtures first (`DEBUG=1 ./build.sh` and `DEBUG=1 ./build.sh demo`). "
                  "This is a hard error, not a skip: a witness that quietly does not "
                  "run is the failure mode this suite keeps rediscovering." % path,
                  file=sys.stderr)
            return 2

    bits = capability_bits()
    caps_s4 = game_caps("sonic4")
    caps_demo = game_caps("demo")
    if caps_demo != 0:
        print("demo_specialization_witness: demo declares SCANLINE_CAPS = %#06x, not 0. "
              "The whole witness rests on demo being the zero-capability fixture; with a "
              "nonzero mask these assertions would be checking nothing in particular."
              % caps_demo, file=sys.stderr)
        return 2

    s4_spans = lst_spans(args.sonic4_lst)
    demo_spans_found = lst_spans(args.demo_lst)
    want_s4 = expected_spans(caps_s4)

    fails = []

    # ---- SPAN half ------------------------------------------------------------
    if demo_spans_found:
        fails.append("demo carries capability-gated spans it cannot use: %s"
                     % sorted(demo_spans_found))
    # The positive control, without which the half above passes on an empty universe:
    # a build that emitted NO spans at all would satisfy "demo has none" trivially.
    missing = sorted(want_s4 - s4_spans)
    if missing:
        fails.append("sonic4 (SCANLINE_CAPS = %#06x) is missing spans its mask raises: "
                     "%s — the demo-absence half above cannot mean anything while the "
                     "presence side is unproven" % (caps_s4, missing))
    extra = sorted(s4_spans - want_s4)
    if extra:
        fails.append("sonic4 emits spans its mask does not raise: %s" % extra)

    # ---- IMAGE half: the committed pin, the half a poison cannot edit ----------
    s4_sizes = lst_proc_sizes(args.sonic4_lst)
    demo_sizes = lst_proc_sizes(args.demo_lst)
    for proc, want in sorted(DEMO_SPECIALISED_PROCS.items()):
        got = demo_sizes.get(proc)
        if got is None:
            fails.append(
                "%s is pinned at %d bytes in demo but is not in demo's listing at all. "
                "Either it left the link (say so here and remove the row) or the listing "
                "spelling changed — do not drop the row to make this pass." % (proc, want))
        elif got != want:
            fails.append(
                "%s emits %d bytes in demo, pinned at %d (%+d). This is the IMAGE "
                "backstop: bytes can be present with no boundary symbol naming them, "
                "which the span half above cannot see. RE-DERIVE why it moved before "
                "touching the pin." % (proc, got, want, got - want))

    # ---- pin-free rider: the two-fixture differential --------------------------
    # Not the backstop (it is derived from the same brackets the span half reads, and
    # the Task-8 poison walked through it), but it costs nothing and it catches the
    # other direction: a gate that stopped gating while keeping its labels.
    checked = 0
    for proc, caps in sorted(gated_procs().items()):
        if proc not in s4_sizes or proc not in demo_sizes:
            continue                       # not linked into both fixtures
        if not any(caps_s4 & bits[c] for c in caps):
            continue                       # sonic4 elides it too; no differential
        checked += 1
        if demo_sizes[proc] >= s4_sizes[proc]:
            fails.append(
                "%s is %d bytes in demo and %d in sonic4 — demo raises none of %s, so "
                "the gated region must be GONE, not merely unlabelled. Equal or larger "
                "is the inlined-leak signature the span half is blind to."
                % (proc, demo_sizes[proc], s4_sizes[proc], sorted(caps)))
    if not checked:
        fails.append("no proc hosting a gated span is present in both listings — the "
                     "differential measured nothing and must not report success")

    print("demo_specialization_witness")
    print("  image pin: %d proc(s), %d bytes total"
          % (len(DEMO_SPECIALISED_PROCS), sum(DEMO_SPECIALISED_PROCS.values())))
    print("  sonic4 SCANLINE_CAPS %#06x -> %d spans expected, %d found"
          % (caps_s4, len(want_s4), len(s4_spans)))
    print("  demo   SCANLINE_CAPS %#06x -> %d spans found (must be 0)"
          % (caps_demo, len(demo_spans_found)))
    print("  image differential over %d gated proc(s):" % checked)
    for proc, caps in sorted(gated_procs().items()):
        if proc in s4_sizes and proc in demo_sizes and any(caps_s4 & bits[c] for c in caps):
            print("      %-28s sonic4 %5d  demo %5d  (%+d)"
                  % (proc, s4_sizes[proc], demo_sizes[proc],
                     demo_sizes[proc] - s4_sizes[proc]))
    if fails:
        for f in fails:
            print("  FAIL  " + f)
        print("demo_specialization_witness: FAIL — %d" % len(fails))
        return 1
    print("demo_specialization_witness: OK — span absence + image differential")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
