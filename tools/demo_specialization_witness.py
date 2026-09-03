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
# five capabilities then gated (CAP_ANCHORS, CAP_PER_COL_VSRAM, CAP_DEFORM, CAP_PER_LINE,
# CAP_TRANSITIONS); CAP_PER_LINE was retired 2026-08-26 (see the last re-derivation log).
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
#
# RE-DERIVATION LOG — 2026-08-22, P3 Task 16 (the parcel-end re-derivation). All eight
# rows re-read head-to-next-head from the P3-tip listings (s4.debug crc 0dbaa80f,
# demo.debug crc dec88cc1) and every one matched the pin — the plan's expectation that
# "P3 changed six of the eight pinned procs" did NOT materialise, and the reason is a
# finding, not a shortfall: only Task 7 (world-Y re-glue, logged above) moved canonical
# bytes. Tasks 9/10's mechanisms are capability-gated behind CAP_MULTI_DEFORM_TABLE
# ($0020) and CAP_FACTOR_CURVE ($0040), NEITHER of which any shipped game raises
# (sonic4 SCANLINE_CAPS stays $001F; adoption is PARK-1, owner-gated), so their code is
# comptime-elided from BOTH fixtures and no pinned row could move.
#
# THE TWO P3 BITS DO ELIDE MEASURABLY — measured on the documented instrument builds
# (recipes in docs/benchmarks/scanline-p3/{DEFORM-OWN,CURVES}.md §3; non-canonical,
# never committed), each three edits off THIS tip, vs the canonical s4.debug listing:
#
#   CAP_MULTI_DEFORM_TABLE  (I1-MDT, crc 01f5eff3, len 715046 — mask $003F, BAND_EXT_N 1)
#     Parallax_Fill_PerLine   686 -> 694   +8   the bracketed span (two movea.l,
#                                               $7B10..$7B18, = the T9 doc's figure)
#     Parallax_Step4_Fill     528 -> 544  +16   record-stride ripple (20 B records widen
#                                               the Step-4a copies; BAND_EXT_N-driven,
#                                               deliberately outside the cap brackets)
#   CAP_FACTOR_CURVE        (I1-FC, crc 7a05bac5, len 715452 — mask $005F, BAND_CURVE_N 1;
#                            byte-identical to CURVES.md §3.7's recorded I1)
#     Parallax_Fill_PerLine   686 -> 788  +102  cap_factor_curve_band ($7BA0..$7C06)
#     Parallax_Step4_Fill     528 -> 688  +160  hoist 138 ($7864..$78EE) + split 6
#                                               ($7A40..$7A46) + 16 stride ripple
#
# Nonzero in every gated site: both bits are really gated, really elided. The
# scanline_spans lane now reports this state in words ("GATED IN SOURCE, RAISED BY
# NEITHER FIXTURE") instead of the old "NOT GATED ANYWHERE" row, which since Task 16
# is reserved for — and FAILS on — a declared bit with no source brackets at all.
# RE-DERIVATION LOG — 2026-08-26, the per-cell HScroll deletion (owner ruling
# d-29-corrected, parcel/delete-percell-hscroll). CAP_PER_LINE is RETIRED: the per-line
# filler, its 896-byte DMA and reg $0B = %11 are unconditional, so the four `cap_per_line_*`
# spans are gone and demo now CARRIES the flat filler it used to elide. Every moved row
# below was traced to its label-span delta in demo.debug.lst (master 32e33ff0's listing
# vs this parcel's), then to the instructions, before the number was touched:
#
#   Enqueue_Dirty_Buffers    514 -> REMOVED  no gated span remains in it (the only one was
#                                            `cap_per_line_dma`); it is still 8 B smaller
#                                            (506) but a proc with no capability gate is not
#                                            this pin's subject — see the "hosts a gated
#                                            span" test in test_demo_specialization_witness
#   Parallax_Fill_PerLine      2 -> 100  (+98) the bare-`rts` else stub is gone and the body
#                                            is unconditional; what demo carries is the
#                                            FLAT filler — prologue 10, .next_band 12,
#                                            .have_end 6, .lp_flat 20, .fl_line 20,
#                                            .fl_tail 6, .fl_rem 6, .band_done 20 — with
#                                            the deform-tables / sampling / multi-table /
#                                            curve spans still elided (CAP mask 0)
#   Parallax_StartTransition  90 -> 78   (-12) `.update_mode` 14 -> 2: the reg $0B HScroll
#                                            arm (moveq 2 + move.l 4 + or.l 4 + beq 2 +
#                                            moveq 2) collapsed to one `moveq #%11`
#   Parallax_Step4_Fill      170 -> 188  (+18) `.bands_ready` 0 -> 24: the two H-deform
#                                            phase accumulators (moveq 2 + move.b 4 +
#                                            add.w abs.w 4 = 10 each) moved out of the
#                                            elided per-line arm and became unconditional,
#                                            plus the `jbra Parallax_Fill_PerLine` tail
#                                            call (bra.w 4); minus the old `.fill_per_cell`
#                                            jbsr (4) and `.fill_done` rts (2)
#   (Parallax_Update 258 -> 246 and BuildStaticDMA 166 -> 142 moved for the same reasons —
#    the reg $0B arm and the 24-byte Static_Hscroll_Cell entry build — but neither hosts a
#    gated span, so neither is pinned here; they are recorded in the parcel's notes.)
#
# RE-DERIVATION LOG — 2026-08-26, the showcase parcel (owner ruling d-15 `depth-curve`,
# parcel/showcase-effects-r2). The pin FAILED and was right to. ONE row moved:
#
#   Parallax_Step4_Fill      188 -> 192  (+4)  `.copy_band` 38 -> 42 (demo.debug.lst:
#                                            $58F0..$5916 on master vs $58F0..$591A here;
#                                            every later local label in the proc is +4
#                                            and nothing else in it moved). The cause is
#                                            the RECORD STRIDE, not a capability span:
#                                            `BAND_CURVE_N` is a pinned ENGINE literal
#                                            (parallax.emp, 0 -> 1 when sonic4 raised
#                                            CAP_FACTOR_CURVE), so `sizeof(band_record)`
#                                            went 10 -> 20 in EVERY game, demo included —
#                                            its own banner says so. `copy_band_entry_fwd`
#                                            is generated from that size:
#                                              10 B: 2 x `move.l (a1)+,(a4)+` + 1 x
#                                                    `move.w (a1)+,(a4)+`   = 3 x 2 = 6 B
#                                              20 B: 5 x `move.l (a1)+,(a4)+` = 5 x 2 = 10 B
#                                            = +4. The neighbouring `mul_const.w d3,
#                                            #sizeof(band_record)` (x10 = <<3 + <<1; x20 =
#                                            <<4 + <<2) and the `-sizeof(band_record)(a4)`
#                                            displacement keep their encodings, so the
#                                            copy is the whole delta. demo's CAP mask is
#                                            still 0 and it still carries NO curve span —
#                                            the span half of this witness stays green;
#                                            this is the "stride ripple" the P3 Task 16
#                                            log predicted (+16 there, on 20 B records
#                                            through the anchored overlay; +4 here, the
#                                            flat copy only).
#
# RE-DERIVATION LOG — 2026-08-29, PARALLAX-SCROLL-CLAMP (`parcel/scroll-and-section-clamps`).
# The pin FAILED and was right to. ONE row moved: Parallax_Step5_Vscroll, demo 62 -> 80
# (+18), sonic4 148 -> 166 (+18). Derived from the source change BEFORE the number was
# touched, and the two derivations agree exactly:
#
#   The BG V-scroll clamp added at `.v_pack` is UNGATED — it sits in the instruction stream
#   outside every `if (Game.SCANLINE_CAPS & CAP_*)` block, so it emits identically in a game
#   with a zero mask. Instruction for instruction:
#       tst.w   d2                       2
#       bge     .v_clamp_hi              2   (bra.s reach)
#       moveq   #0, d2                   2
#       jbra    .v_pack_store            2   (bra.s reach)
#       cmpi.w  #VSCROLL_BG_MAX, d2      4
#       ble     .v_pack_store            2
#       move.w  #VSCROLL_BG_MAX, d2      4
#                                    = 18 B, in BOTH games. Same delta both shapes.
#
# The other six rows are unchanged — measured, not assumed: every pinned proc was diffed
# head-to-next-head between the pre- and post-change plain listings and only this one moved.
# That is the corroboration this banner asks for.
#
# NOTED WHILE HERE, NOT FIXED: the parenthetical `(sonic4 N)` numbers are commentary, not
# asserted by anything. This row's said 144 when the listing said 148 (corrected above with
# the +18), and `Parallax_Fill_PerLine`'s says 792 where the tool prints 782. Left alone
# rather than swept into an unrelated parcel's diff; the tool's own output is authoritative.
# RE-DERIVATION LOG — 2026-08-30, THE SCENE-LEVEL VERTICAL BOB (`parcel/vertical-bob`,
# EFFECTS-W1 item 7). The pin FAILED and was right to. ONE row moved:
# Parallax_Step5_Vscroll, demo 80 -> 120 (+40), sonic4 166 -> 206 (+40). Derived from the
# source change BEFORE the number was touched, and the two derivations agree exactly.
#
# The bob is a term on the BG V-scroll at `.v_pack`, and like the scroll clamp above it, it
# is UNGATED — it sits in the instruction stream outside every
# `if (Game.SCANLINE_CAPS & CAP_*)` block, because the bob is a per-SCENE property (a byte
# in each parallax_config) and not a per-GAME capability. A game with a zero mask emits it
# in full and pays 26 cycles a frame testing a byte that is always 0. That is a stated,
# deliberate cost, argued at the instruction in engine/level/parallax.emp; the CAP_* bit
# that would elide it is named there and rejected.
#
# Instruction for instruction, read off demo.debug.bin $5B94..$5BBB (the `.v_pack` ->
# `.v_bob_none` span), not off the source:
#     moveq   #0, d3                        76 00                    2
#     move.b  pcfg_bob(a0), d3              16 28 00 1D              4
#     beq     .v_bob_none                   67 20                    2   (bra.s reach)
#     move.w  d3, d0                        30 03                    2
#     and.w   #$0F, d0                      C0 7C 00 0F              4   (andi.w)
#     move.w  Logic_Tick+2, d4              38 38 80 06              4   (abs.w)
#     lsr.w   d0, d4                        E0 6C                    2
#     and.w   #BOB_SINE_ENTRIES-1, d4       C8 7C 00 FF              4   (andi.w)
#     add.w   d4, d4                        D8 44                    2
#     lea     Sine_Table, a1                43 F8 12 58              4   (abs.W — see below)
#     move.w  (a1,d4.w), d4                 38 31 40 00              4
#     lsr.w   #4, d3                        E8 4B                    2
#     asr.w   d3, d4                        E6 64                    2
#     add.w   d4, d2                        D4 44                    2
#                                                                 = 40 B, in BOTH games.
#
# RE-DERIVATION LOG — 2026-09-02, the band-drift ADOPTION parcel (EFFECTS-W1 item 3,
# parcel/drift-on). The pin FAILED and was right to. ONE row moved, and it is the 08-26
# entry above one tail over:
#
#   Parallax_Step4_Fill      192 -> 194  (+2)  `.copy_band` 42 -> 44 (demo.debug.lst:
#                                            $5A80..$5AAA on master vs $5A80..$5AAC here;
#                                            every later local label in the proc is +2 and
#                                            nothing else in it moved — `Parallax_Step4_Fill`
#                                            and `.find_k` / `.found_k` / `.copy_band`
#                                            themselves are at IDENTICAL addresses). The
#                                            cause is again the RECORD STRIDE and not a
#                                            capability span: `BAND_DRIFT_N` is a pinned
#                                            ENGINE literal (parallax.emp, 0 -> 1 when
#                                            sonic4 raised CAP_BAND_DRIFT), so
#                                            `sizeof(band_record)` went 20 -> 24 in EVERY
#                                            game, demo included, and `copy_band_entry_fwd`
#                                            is generated from that size: one more
#                                            `move.l (a1)+,(a4)+` = +2 B. demo authors no
#                                            drift and emits NONE of the three
#                                            `cap_band_drift_*` spans — the span half of
#                                            this witness confirms it (demo 0 spans), which
#                                            is exactly why the image half exists.
#
# The other six rows are unchanged — measured, not assumed: this tool's own image
# differential printed 6 / 100 / 78 / 194 / 120 / 8 / 26 against pins of 6 / 100 / 78 /
# 192 / 120 / 8 / 26 on the run that failed this one, so Step4_Fill is the only row that
# disagreed.
#
# ONE OF THOSE FORTY IS RELAXATION-DEPENDENT AND WORTH KNOWING BEFORE THE NEXT REPIN. The
# `lea` lowers to ABSOLUTE SHORT (4 B) because Sine_Table sits at $1258 in demo.debug and
# $2B08 in s4.debug — both inside the sign-extended $0000..$7FFF that `.w` reaches. It
# becomes absolute long (6 B, so 42 here) the day the math section is pushed past $7FFF by
# ROM growth ahead of it. Nothing needs to change when that happens; the row moves by 2 and
# this note is why. It CANNOT go back to `Sine_Table(pc,d4.w)`: PC-relative INDEXED carries
# an 8-bit displacement on the 68000 and the math section is ~20 KB away, which is a hard
# link failure, measured (`(d8,PC,Xn) displacement to `Sine_Table` out of range (-20794)`).
#
# The other six rows are unchanged — measured, not assumed: this tool's own image
# differential printed 6 / 100 / 78 / 192 / 8 / 26 against pins of 6 / 100 / 78 / 192 / 8 /
# 26 on the same run that failed this one. That is the corroboration this banner asks for.
# RE-DERIVATION LOG — 2026-09-03, THE ANCHOR MOVER (`parcel/anchor-mover`, EFFECTS-W1 item 4).
# The pin did NOT fail, and that is the finding: not one of the seven rows moved. Two procs
# JOIN the set, both in engine/effects/raster.emp, and both because CAP_ANCHOR_MOTION ($0100)
# is the first capability whose spans live outside parallax.emp:
#
#   Effects_LatchWorldLines   NEW -> 26   sonic4 126 (-100). The mover — a rate-gated ramp
#                                         plus a sine sweep, evaluated inside the existing
#                                         per-channel loop — is `cap_anchor_motion_latch`.
#                                         DEMO'S 26 IS THE SHIPPED PRE-PARCEL SIZE TO THE
#                                         BYTE: the four prologue instructions were reordered
#                                         (the `lea Effects_Screen_L, a1` moved below the
#                                         `moveq`, so the elided arm can take a1 for the sine
#                                         base) and reordering four instructions of the same
#                                         widths moves no byte.
#   Effects_SetTargetY        NEW ->  2   sonic4 36 (-34). The whole body is gated
#                                         (`cap_anchor_motion_target`), so demo carries the
#                                         `rts` and nothing else. It is a `pub proc` and demo's
#                                         raster.emp is in its use closure, so the alternative
#                                         to gating it was 36 bytes of setter writing a bank
#                                         demo's elided loop never reads.
#
# WHAT DEMO DOES STILL PAY, stated because "the bit elides it" over-reads: 36 code bytes
# (Effects_SetTargetY's `rts` = 2, plus Effects_InstallPreset's 34-byte motion seed, which is
# NOT capability-gated — argued at the instruction in engine/effects/preset.emp) and the 26
# bytes of RAM, which ram.emp has no capability arms to elide. Measured: demo.debug's symbol
# shifts are exactly {+0, +2, +36, +26} and its EndOfRom does NOT move — the 36 bytes land in
# placer fill, so demo's ROM IMAGE is the same length and only the deb2 symbol appendix grows
# (+131 B on demo.debug.bin, +118 on demo.bin, all of it new label names).
#
# RE-DERIVATION LOG — 2026-09-03, tools/scene_spans.py's phased-VMA-symbol fix. Raster_HInt
# is now PINNED, and PROC_SIZE_RIDER_BLIND_PROCS (the exclusion this parcel's own EFFECTS-W1
# item 6 landed minutes earlier, right above where this note now sits) is REMOVED, not just
# emptied — measured, not assumed:
#
# The item-6 note this replaces reasoned correctly about the SYMPTOM (SfxBlobWinTab, 21 B
# after Raster_HInt in sonic4's listing, made `lst_proc_sizes` report 21) but scoped the fix
# to the wrong population: "Z80 sound table" is not what makes a listing address unusable as
# a boundary — `games/sonic4/data/sound/soundbankhead.emp`'s `section soundbankhead (cpu:
# m68000, vma: $8000)` is the actual source of both SfxBlobWinTab AND SoundTablesZ80_Head
# (which had already been silently truncating `Parallax_Step5_Vscroll` the same way, unnoticed
# because nothing pinned it before). `vma_phased_symbol_names()` (scene_spans.py) derives the
# exclusion from every `section ... vma:` declaration in the tree, not by name, so it catches
# both instances from one mechanism and needs no per-proc escape hatch.
#
# With that fix, Raster_HInt measures correctly in BOTH shapes: sonic4 338, demo 316 (+22 —
# exactly item 6's own `.cap_dense_tier_enter` region, corroborating the SPAN half's
# independent proof that the gate raises for sonic4 and elides for demo). The other nine rows
# are unchanged — measured, not assumed: this run printed 26 / 2 / 6 / 100 / 78 / 194 / 120 /
# 8 / 26 against pins of the same nine numbers.
DEMO_SPECIALISED_PROCS = {
    "Effects_LatchWorldLines":   26,   # CAP_ANCHOR_MOTION          (sonic4 126)
    "Effects_SetTargetY":         2,   # CAP_ANCHOR_MOTION          (sonic4  36) — a bare rts
    "Parallax_Active_Config":     6,   # CAP_TRANSITIONS            (sonic4  18)
    "Parallax_Fill_PerLine":    100,   # CAP_DEFORM, CAP_MULTI_DEFORM_TABLE, CAP_FACTOR_CURVE (sonic4 792 with the curve raised) — the flat filler
    "Parallax_StartTransition":  78,   # CAP_PER_COL_VSRAM, CAP_TRANSITIONS  (sonic4 106)
    "Parallax_Step4_Fill":      194,   # CAP_ANCHORS, CAP_FACTOR_CURVE  (sonic4 670; 24 B record stride since CAP_BAND_DRIFT, 2026-09-02)
    "Parallax_Step5_Vscroll":   120,   # CAP_PER_COL_VSRAM, CAP_TRANSITIONS  (sonic4 206)
    "Raster_GetChannelBand":      8,   # CAP_ANCHORS                (sonic4  50)
    "Raster_HInt":              316,   # CAP_DENSE_TIER             (sonic4 338) — see the
                                        # RE-DERIVATION LOG above; unmeasurable before the
                                        # phased-VMA-symbol fix, now pinned like every other row
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
