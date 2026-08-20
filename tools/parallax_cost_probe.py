#!/usr/bin/env python3
"""parallax_cost_probe — the walker's cost as a FITTED ADDITIVE MODEL, not per-variant rows.

WHY A FITTED MODEL. Design §5 axis 1 requires the walker's cost to come from a small parameter
set pinned to oracle fixtures with a 0-residual target, explicitly NOT per-variant
re-measurement. This is the raster F1-F8 precedent applied to the parallax walker: one fixture
per parameter, each varying ONE thing from a neighbour, and the RESIDUAL is the deliverable.

HOW A FIXTURE IS INSTALLED — no ROM bytes, no rebuild, no engine hook. A parallax config is a
28-byte header plus a `band_entry` array, reached through ONE RAM pointer
(`Parallax_Current_Config`). So a fixture is a config BUILT IN RAM with the pointer aimed at
it, which is `raster_cost_probe`'s trick in a different module:

    Debug_Scene_Freeze         = 1     camera pinned, so Parallax_CheckBoundary (edge-triggered
                                       on the section under the camera) never fires and cannot
                                       install a real config over the fixture
    Parallax_Transition_Frames = 0     forces Parallax_Update's `.use_current` arm; a live
                                       transition would drive from Target_Config instead
    Parallax_Target_Config     = 0
    Parallax_Current_Config    = &scratch

THE SCRATCH IS `Replay_Record_Buf` — 8 KB, DEBUG-shape only, and inert unless the replay
recorder is recording. `Replay_Record_Idx` is read before and after every sample and must stay
0; if the recorder ever woke up it would be writing through the fixture, and the run says so
rather than measuring the wreckage.

THE FIXTURE IS A MUTATION OF THE SHIPPED CONFIG, not a config invented here. The bytes of
`ParallaxConfig_OJZ_Default` are copied out of ROM and then ONE field is changed per fixture.
Inventing a header from scratch would risk measuring a config the engine never sees; starting
from the shipped one means every fixture is one edit away from something real.

WHAT IS MEASURED. `Parallax_Update`'s per-routine row, which is INCLUSIVE of its callees --
verified on this ROM: Parallax_Update 19511 contains Parallax_Fill_PerLine 14866 plus
Decode_Factor_A/B 766, and GameState_OJZScroll_Update 35125 contains all of it. So one row is
the whole walker, which is the quantity axis 1 budgets. `interrupts.hint` is never read (it is
HBlank + VBlank in this ROM); addresses match on the low 24 bits.

THE WINDOW MUST BE PREEMPTION-FREE, AND THIS IS CHECKED, NOT ASSUMED (P3 Task 1). The row is a
per-VIDEO-FRAME average, so it equals one call only while the main loop completes one logic tick
per video frame. `Frame_Counter` and `Logic_Tick` bracket the profiled window and must agree; the
window is re-taken until they do. The P2 sweep did not check this and every one of its rows was
diluted by 30/31 (some by 29/31), which is why its coefficients are ~3.3% low and why its
`line_both` — a column excited by one fixture, and that fixture lagged twice — is ~7% low.

THE CAMERA IS FROZEN AND THAT IS LOAD-BEARING FOR THE ARITHMETIC, not just for reproducibility.
Sustained motion makes the main loop overrun a video frame (ENGINE-BASELINE.md §2), and under
lag one logic tick spans two frames, so a per-frame average stops being one call of the walker.
Frozen, every frame carries exactly one complete call and the row is directly comparable
between fixtures.

Usage:
    python3 tools/parallax_cost_probe.py --rom s4.debug.bin --lst s4.debug.lst --repeat 3
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

HARNESS = "/home/volence/sonic_hacks/oracle-old/linux-port/harness"
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient           # noqa: E402
from launcher import headless_emulator  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402


# ---- the config's wire layout (engine/structs.emp, parallax_config; 28 bytes) ----
# Offsets, not a re-declaration: the probe edits fields of a config it COPIED, so it only needs
# to know where they sit. sizeof is pinned below against the shipped header the copy came from.
CFG_BAND_COUNT      = 0    # u8
CFG_V_FACTOR_BG     = 1    # u8   (15 = locked: Step 5 skips the lerp)
CFG_LAYER_MASK      = 3    # u8
CFG_TRANSITION      = 8    # u8
CFG_DEFORM_SPEED_FG = 9    # u8
CFG_DEFORM_SPEED_BG = 10   # u8
CFG_ANCHOR_CH       = 11   # u8   ($FF = PARALLAX_ANCHOR_NONE)
CFG_DEFORM_TAB_FG   = 12   # u32
CFG_DEFORM_TAB_BG   = 16   # u32
CFG_V_DEFORM_TAB_BG = 20   # u32
CFG_V_DEFORM_SHIFT  = 25   # u8
CFG_ANCHOR_DSA      = 26   # u8
CFG_ANCHOR_DSB      = 27   # u8
CFG_SIZE            = 28

# band_entry (engine/level/parallax.emp), 10 bytes
BE_TOP_CELL   = 0
BE_A_S1       = 1
BE_A_S2       = 2
BE_B_S1       = 4
BE_B_S2       = 5
BE_DSHIFT_A   = 7
BE_DSHIFT_B   = 8
BE_SIZE       = 10

ANCHOR_NONE = 0xFF
NO_DEFORM   = 15          # the shift sentinel: 15 = this plane takes no deform


def band(top: int, dsa: int = NO_DEFORM, dsb: int = NO_DEFORM) -> bytes:
    b = bytearray(BE_SIZE)
    b[BE_TOP_CELL] = top
    b[BE_A_S1] = 1;  b[BE_A_S2] = NO_DEFORM      # single-term factor, plane A
    b[BE_B_S1] = 2;  b[BE_B_S2] = NO_DEFORM      # single-term factor, plane B
    b[BE_DSHIFT_A] = dsa
    b[BE_DSHIFT_B] = dsb
    return bytes(b)


def band_tops(bands: int) -> list[int]:
    """Band tops in CELL rows, spread evenly over the 28 visible rows.

    Screen lines are these x 8, and `Parallax_Shadow_Bands` confirms it: with v_factor_bg = 15
    (locked) Vscroll_BG is pinned, so Step 4a's rotation is the identity and the shadow tops
    read back as exactly 0/112 for 2 bands and 0/72/144 for 3. Measured, not assumed -- the
    probe prints them.
    """
    return [i * (28 // bands) for i in range(bands)]


def build(base: bytes, *, bands: int = 1, tab_fg: int = 0, tab_bg: int = 0,
          v_tab_bg: int = 0, anchor: int = ANCHOR_NONE, dsa: int = NO_DEFORM,
          dsb: int = NO_DEFORM, speed_fg: int = 0, speed_bg: int = 0,
          shifts: list[tuple[int, int]] | None = None) -> bytes:
    """The shipped header with ONE thing changed, plus `bands` synthetic band entries.

    Band tops are spread evenly over the 28 visible cell rows so a multi-band fixture really
    does give the filler several bands to walk rather than several zero-length ones -- a
    per-band slope measured on empty bands would be measuring the loop and not the work.
    """
    h = bytearray(base[:CFG_SIZE])
    h[CFG_BAND_COUNT] = bands
    h[CFG_V_FACTOR_BG] = NO_DEFORM       # locked: Step 5 pins BG and skips the lerp, so the
                                         # vscroll half is constant across every fixture
    h[CFG_LAYER_MASK] = 0xFF
    h[CFG_TRANSITION] = 0
    h[CFG_DEFORM_SPEED_FG] = speed_fg
    h[CFG_DEFORM_SPEED_BG] = speed_bg
    h[CFG_ANCHOR_CH] = anchor
    h[CFG_ANCHOR_DSA] = dsa if anchor != ANCHOR_NONE else NO_DEFORM
    h[CFG_ANCHOR_DSB] = dsb if anchor != ANCHOR_NONE else NO_DEFORM
    h[CFG_V_DEFORM_SHIFT] = 3
    for off, val in ((CFG_DEFORM_TAB_FG, tab_fg), (CFG_DEFORM_TAB_BG, tab_bg),
                     (CFG_V_DEFORM_TAB_BG, v_tab_bg)):
        h[off:off + 4] = val.to_bytes(4, "big")
    tops = band_tops(bands)
    sh = shifts if shifts is not None else [(dsa, dsb)] * bands
    body = b"".join(band(t, s[0], s[1]) for t, s in zip(tops, sh))
    return bytes(h) + body


# ---- the fixture matrix -----------------------------------------------------
# One thing changes between a fixture and its named neighbour. The `vary` field names it, and
# nothing is fitted that no pair isolates.
#
# MAPPING TO THE PLAN'S PARAMETER NAMES. The plan asks for per-layer, per-line-mode, per-curve,
# per-deform-ref and re-glue. Those are the DESIGN doc's scene vocabulary; the walker that
# exists today has these cost axes, and they correspond:
#   per-layer      -> band count            (W1/W2/W3 per-cell, W5/W6 per-line)
#   per-line-mode  -> an H-deform table is attached at all (this is what selects
#                     Parallax_Fill_PerLine over Parallax_Fill_PerCell AND flips reg $0B)
#   per-curve      -> the deform SAMPLING actually running, i.e. band_deform_shift != 15
#                     with a table attached (W7 FG, W8 FG+BG)
#   per-deform-ref -> the V-deform table reference: per-column VSRAM instead of whole-plane (W9)
#   re-glue        -> the Step-4b anchored overlay, which SPLITS a band and re-glues the
#                     shadow list one entry longer (W10)
# A name with no fixture would be a fitted parameter nothing measured, which is the defect this
# whole phase exists to avoid.

def fixtures(base: bytes, zero_tab: int) -> dict:
    return {
        "W0": {"what": "1 band, per-cell, no deform, no anchor — the floor",
               "vary": "-", "cfg": build(base, bands=1)},
        "W1": {"what": "2 bands, per-cell", "vary": "band count vs W0",
               "cfg": build(base, bands=2)},
        "W2": {"what": "3 bands, per-cell", "vary": "band count vs W1",
               "cfg": build(base, bands=3)},
        "W3": {"what": "4 bands, per-cell", "vary": "band count vs W2",
               "cfg": build(base, bands=4)},
        "W4": {"what": "1 band, PER-LINE (FG table attached, shifts still 15 = no sampling)",
               "vary": "line mode vs W0", "cfg": build(base, bands=1, tab_fg=zero_tab)},
        "W5": {"what": "2 bands, per-line, no sampling", "vary": "band count vs W4",
               "cfg": build(base, bands=2, tab_fg=zero_tab)},
        "W6": {"what": "3 bands, per-line, no sampling", "vary": "band count vs W5",
               "cfg": build(base, bands=3, tab_fg=zero_tab)},
        "W7": {"what": "1 band, per-line, FG SAMPLING live (shift_a = 3)",
               "vary": "FG curve sampling vs W4",
               "cfg": build(base, bands=1, tab_fg=zero_tab, dsa=3)},
        "W8": {"what": "1 band, per-line, FG+BG sampling live",
               "vary": "BG curve sampling vs W7",
               "cfg": build(base, bands=1, tab_fg=zero_tab, tab_bg=zero_tab, dsa=3, dsb=3)},
        "W9": {"what": "1 band, per-cell, V-DEFORM table attached (per-column VSRAM)",
               "vary": "deform-ref vs W0", "cfg": build(base, bands=1, v_tab_bg=zero_tab)},
        "W10": {"what": "2 bands, per-line, ANCHORED overlay (Step 4b split + re-glue)",
                "vary": "re-glue vs W5",
                "cfg": build(base, bands=2, tab_fg=zero_tab, anchor=0, dsa=3, dsb=3)},
        "W11": {"what": "1 band, per-line, deform speed non-zero — the CONTROL",
                "vary": "phase advance vs W4",
                "cfg": build(base, bands=1, tab_fg=zero_tab, speed_fg=4, speed_bg=4)},
        # W12 exists so `anchor` is not fitted from a SINGLE fixture. With only W10 the
        # coefficient is exactly identified, its residual is 0 by construction, and a wrong
        # value would be invisible. Two anchored fixtures at different band counts make the
        # parameter over-determined like every other one here.
        "W12": {"what": "3 bands, per-line, ANCHORED — the second anchor point",
                "vary": "band count vs W10",
                "cfg": build(base, bands=3, tab_fg=zero_tab, anchor=0, dsa=3, dsb=3)},
        # W13 disambiguates `sample_fg`. With only W4 -> W7 -> W8 the model cannot tell
        # "the FG channel costs more than the BG channel" from "the FIRST sampled channel
        # pays the flat -> sampling transition and the second is incremental" -- the two
        # explanations fit the same three points identically. A BG-ONLY fixture separates
        # them: if the channels are symmetric, W13's marginal cost over W4 equals W7's.
        "W13": {"what": "1 band, per-line, BG SAMPLING ONLY (shift_b = 3, FG stays 15)",
                "vary": "BG-only sampling vs W4 — disambiguates sample_fg",
                "cfg": build(base, bands=1, tab_bg=zero_tab, dsb=3)},
        # W14/W15 are what put the sampling cost in LINES rather than in channels. Every
        # fixture above samples all 224 lines or none, so "the channel is on" and "224 lines
        # sample" are the same column and no fit can separate them. These two sample only their
        # LOWEST band -- 112 lines and 80 lines -- which is also the shape real content takes:
        # the shipped underwater config samples only below its anchored split.
        "W14": {"what": "2 bands, per-line, only the LOWER band samples FG (112 lines)",
                "vary": "sampled LINES vs W7 (224) — puts the cost in lines, not channels",
                "cfg": build(base, bands=2, tab_fg=zero_tab,
                             shifts=[(NO_DEFORM, NO_DEFORM), (3, NO_DEFORM)])},
        "W15": {"what": "3 bands, per-line, only the LOWEST band samples FG (80 lines)",
                "vary": "sampled LINES vs W14 (112)",
                "cfg": build(base, bands=3, tab_fg=zero_tab,
                             shifts=[(NO_DEFORM, NO_DEFORM), (NO_DEFORM, NO_DEFORM),
                                     (3, NO_DEFORM)])},
        # W16 IS THE SHIPPED SHAPE, and it is the fixture that makes this model's out-of-sample
        # claim testable rather than asserted. `ParallaxConfig_OJZ_Underwater` -- the config
        # actually live at the idle baseline -- has four bands whose ROM entries ALL say 15, a
        # BG deform table, and an anchor whose `pcfg_anchor_dsb` is what switches BG sampling on
        # below the split. So the anchor is not a small additive extra there, it is the thing
        # that turns the expensive term on, for a runtime number of lines. No fixture above has
        # that shape: W10/W12 sample everywhere with or without their anchor.
        "W16": {"what": "4 bands, per-line, ANCHORED, sampling turned on BY the anchor "
                        "(bands 15/15, anchor_dsb = 2) — the shipped underwater shape",
                "vary": "anchor-driven sampling vs W12",
                # POISON, run red-first 2026-08-20: setting this `anchor=` to ANCHOR_NONE makes
                # the run exit 5 with "W16 vs W24: shadow tops IDENTICAL — no split", and W16's
                # row collapses 19932 -> 7322 (it becomes the un-anchored 4-band config). The
                # instructive half: the SLOT witness does not catch it — with anchor_ch = $FF the
                # fixture is legitimately un-anchored, so "slot still $FF" is the correct verdict
                # for what the config now says. Only the NEIGHBOUR DIFFERENTIAL sees that the
                # fixture stopped being the thing it claims to measure. Neither witness is
                # sufficient alone, which is why both are kept and why W24 exists.
                "cfg": build(base, bands=4, tab_bg=zero_tab, anchor=0,
                             dsa=NO_DEFORM, dsb=2,
                             shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},

        # ---- P3 Task 1: the 2x2 that resolves the anchored overlay's two regimes ----
        # W10/W12 (+456) and W16 (+1205) differ in FOUR ways at once -- band count, channel,
        # sampled-line count, and whether the overlay TURNS SAMPLING ON versus merely rewriting
        # shifts on bands that already sample. Four differences and two data regimes is not a
        # measurement, it is a coincidence with a story. These fixtures take the differences
        # apart one at a time.
        #
        # THE AXIS UNDER TEST is the last one: does the overlay CHANGE THE FILLER'S LOOP TYPE at
        # the split (bands above take `.lp_flat`, bands below take a sampling loop) or not?
        # W10/W12 change nothing -- every band sampled before the overlay and samples after.
        # The 2x2 crosses that axis with band count:
        #
        #                       | 2 bands | 4 bands
        #   ----------------------+---------+--------
        #   overlay CHANGES type  |   W17   |   W16
        #   overlay changes none  |   W21   |   W18
        #
        # W21 is the fourth cell and it is NOT in the plan's table: the plan pairs W17/W18
        # against W10/W16, but W10 is the "already sampling everywhere" shape, which is a
        # different no-change cell from "nothing samples at all". Crossing band count against
        # the type-change axis needs both no-change cells at both band counts, so W21 is added
        # to make the 2x2 an actual 2x2 rather than three cells and a near neighbour.
        #
        # W17 holds the SAMPLED-LINE COUNT constant against W16 by construction, not by luck:
        # 2 bands top at 0/112 and 4 bands at 0/56/112/168, and with the split at L = 80 both
        # sample every line from 80 to 224 = 144 lines. So W17 vs W16 varies band count ALONE.
        "W17": {"what": "2 bands, per-line, ANCHORED, sampling turned on BY the anchor "
                        "(bands 15/15, anchor_dsb = 2) — W16's regime at W10's band count",
                "vary": "band count vs W16 (sampled lines identical: 144)",
                "cfg": build(base, bands=2, tab_bg=zero_tab, anchor=0,
                             dsa=NO_DEFORM, dsb=2,
                             shifts=[(NO_DEFORM, NO_DEFORM)] * 2)},
        "W18": {"what": "4 bands, per-line, ANCHORED, overlay writes FLAT shifts — the pure "
                        "re-glue at W16's band count (nothing samples)",
                "vary": "overlay turns sampling ON vs W16 (anchor_dsb 2 -> 15)",
                "cfg": build(base, bands=4, tab_bg=zero_tab, anchor=0,
                             dsa=NO_DEFORM, dsb=NO_DEFORM,
                             shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
        "W21": {"what": "2 bands, per-line, ANCHORED, overlay writes FLAT shifts — the pure "
                        "re-glue at W17's band count (nothing samples)",
                "vary": "band count vs W18 — the 2x2's fourth cell",
                "cfg": build(base, bands=2, tab_bg=zero_tab, anchor=0,
                             dsa=NO_DEFORM, dsb=NO_DEFORM,
                             shifts=[(NO_DEFORM, NO_DEFORM)] * 2)},
        # Channel. W16 turns the BG loop on; W19 turns the FG loop on, same band count, same
        # split, same 144 lines, same shift. If the regimes are a property of the overlay rather
        # than of which plane it happens to drive, these two agree.
        "W19": {"what": "4 bands, per-line, ANCHORED, sampling turned on BY the anchor on the "
                        "FG channel (anchor_dsa = 2)",
                "vary": "channel vs W16 (BG -> FG)",
                "cfg": build(base, bands=4, tab_fg=zero_tab, anchor=0,
                             dsa=2, dsb=NO_DEFORM,
                             shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
        # Split position. The split line is NOT a config field -- it is Effects_Screen_L[ch],
        # latched every frame from Effects_World_Y[ch] - Camera_Y. So this fixture is W16 with
        # the WORLD ANCHOR moved (+16 px), never the camera: moving the camera would change the
        # scroll factors, the section under it and the whole `Decode_Factor` half, which is four
        # more differences. The realized split is read back from the shadow view rather than
        # assumed, because Raster_GetChannelBand clamps L into the channel's authored band.
        "W20": {"what": "4 bands, per-line, ANCHORED, W16 with the world anchor moved +16 px "
                        "(split 80 -> 96, sampled lines 144 -> 128)",
                "vary": "split POSITION vs W16 — and it re-checks sampled_lines(split)",
                "world_y_delta": 16,
                "cfg": build(base, bands=4, tab_bg=zero_tab, anchor=0,
                             dsa=NO_DEFORM, dsb=2,
                             shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
        # ---- the deform SHIFT VALUE, a confound the P2 fixture set could not see ----
        # Every sampling fixture W7..W15 uses shift 3; W16 uses 2, because 2 is what the shipped
        # underwater config's `pcfg_anchor_dsb` says. The sampled line loops end in
        # `asr.w d3, d1`, and a REGISTER-count shift on the 68000 is 6 + 2n cycles, so the shift
        # VALUE is a per-line cost term and the fitted 76.2x is the shift-3 value, not a
        # constant. Two fixtures, not one: a column excited by a single fixture is exactly what
        # this file refuses to fit. Un-anchored, so the column is identified inside the clean
        # subset and does not lean on the anchored rows.
        "W22": {"what": "1 band, per-line, FG sampling at shift 2 (W7 is shift 3)",
                "vary": "deform SHIFT VALUE vs W7 (3 -> 2)",
                "cfg": build(base, bands=1, tab_fg=zero_tab, dsa=2)},
        "W23": {"what": "1 band, per-line, FG sampling at shift 5",
                "vary": "deform SHIFT VALUE vs W22 (2 -> 5)",
                "cfg": build(base, bands=1, tab_fg=zero_tab, dsa=5)},
        # The un-anchored 4-band per-line point. Two jobs, both structural: it extends
        # `band_perline` from three points (W4/W5/W6 at 1/2/3 bands) to four, and it is the
        # same-shaped neighbour the 4-band ANCHORED fixtures (W16/W18/W19/W20) need for the
        # shadow-tops differential — without it those four have only the slot poison as a
        # witness, and a check with one form is a check with one failure mode.
        "W24": {"what": "4 bands, per-line, no sampling", "vary": "band count vs W6",
                "cfg": build(base, bands=4, tab_fg=zero_tab)},
        # The S = 2 row for `band_sampling`. W14 is 2 bands with only the LOWER one sampling
        # (112 lines, S = 1); W25 turns the upper band on too (224 lines, S = 2). Un-anchored,
        # so the column is identified in the clean subset and at more than the 0-vs-1 contrast.
        "W25": {"what": "2 bands, per-line, BOTH bands sample FG (224 lines, 2 sampling bands)",
                "vary": "sampling BANDS vs W14 (1 -> 2) — identifies band_sampling",
                "cfg": build(base, bands=2, tab_fg=zero_tab, dsa=3)},
    }


SYMS = ("Parallax_Update", "Parallax_Fill_PerLine", "Parallax_Fill_PerCell",
        "Parallax_Current_Config", "Parallax_Target_Config", "Parallax_Transition_Frames",
        "Debug_Scene_Freeze", "Replay_Record_Buf", "Replay_Record_Idx",
        "DeformTable_Zero", "ParallaxConfig_OJZ_Default", "Effects_Screen_L",
        # These two were READ by _one and absent from the missing-symbol guard, so a build
        # that dropped either would have raised KeyError mid-sweep instead of failing the
        # precondition. Listed, not just used.
        "Parallax_Shadow_Bands", "Effects_World_Y",
        # The preemption check's three counters — see the FRAMES PER TICK block in _one.
        "Frame_Counter", "Logic_Tick", "Lag_Frame_Count")

SLOT_POISON = 0xFF        # the un-written shadow slot's arm value — see _one


async def _one(b: BusClient, sym: dict[str, int], cfg: bytes,
               settle: int, sample: int, world_y_delta: int = 0) -> dict:
    # `reset: timeout waiting for main-thread drain` is an INSTRUMENT flake, not a ROM one:
    # oracle's reset is serviced by the GUI main loop, and under machine load (other lanes'
    # headless emulators running) that loop can miss its drain window. Observed three times
    # across this parcel's runs, always on `reset`, never on anything else, and always fine on
    # the next attempt. Retried rather than left to abort a 17-fixture sweep at fixture 12 --
    # and bounded, so a genuinely wedged emulator still fails instead of spinning.
    for attempt in range(4):
        try:
            await b.call("emulator/reset", {"wait": True, "run": False})
            break
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(1.5)
    await b.call("emulator/run_frames", {"frames": settle})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})

    scratch = sym["Replay_Record_Buf"]
    await b.call("emulator/write_memory",
                 {"addr": hex(scratch), "bytes": cfg.hex().upper()})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Transition_Frames"]), "value": 0, "width": 1})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Target_Config"]), "value": 0, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Current_Config"]), "value": scratch, "width": 4})
    await b.call("emulator/run_frames", {"frames": 3})

    # THE SPLIT LINE IS NOT A CONFIG FIELD. It is Effects_Screen_L[ch], re-derived every frame
    # by Effects_LatchWorldLines as Effects_World_Y[ch] - Camera_Y. A fixture that wants a
    # DIFFERENT split therefore moves the world anchor, never the camera: the camera also
    # selects the section, the scroll factors and the whole Decode_Factor half, so moving it
    # would vary four things instead of one. Read-modify-write, and the value is read back
    # after the sample so "the preset re-installed its own anchors over the poke" is a check
    # rather than an assumption.
    ch = cfg[CFG_ANCHOR_CH]
    wy_addr = wy_want = None
    if world_y_delta and ch != ANCHOR_NONE:
        wy_addr = sym["Effects_World_Y"] + 2 * ch
        wy0 = await b.call("emulator/read_memory", {"addr": hex(wy_addr), "len": 2})
        wy_want = (int(wy0["bytes"], 16) + world_y_delta) & 0xFFFF
        await b.call("emulator/write_memory",
                     {"addr": hex(wy_addr), "value": wy_want, "width": 2})
        await b.call("emulator/run_frames", {"frames": 2})

    idx0 = await b.call("emulator/read_memory",
                        {"addr": hex(sym["Replay_Record_Idx"]), "len": 2})

    # POISON THE SHADOW SLOT THE OVERLAY IS THE ONLY WRITER OF. Step 4a writes exactly
    # `band_count` shadow entries every frame (`.copy_band`, dbf over d7); slot `band_count` is
    # written by Step 4b's split and by nothing else. So filling that slot with $FF and reading
    # it back is a TWO-SIDED witness rather than a differential that needs a neighbour:
    #   anchored fixture   -> the slot must hold a real top (the overlay ran and split)
    #   un-anchored fixture-> the slot must still read $FF (nothing writes there)
    # The neighbour-pair differential below stays as well, but it cannot cover a fixture with
    # no same-shaped neighbour, and it reads a stale slot as evidence when the shapes differ.
    # Poisoning is safe: an un-written slot is never READ either, because the filler's band
    # countdown is d7 = band_count unless the overlay bumped it.
    n_cfg = cfg[CFG_BAND_COUNT]
    poison_hex = (bytes([SLOT_POISON]) * BE_SIZE).hex().upper()
    poison_addr = hex(sym["Parallax_Shadow_Bands"] + n_cfg * BE_SIZE)

    # ---- FRAMES PER TICK: the condition under which the response variable means what it says --
    # The per-routine row is a per-VIDEO-FRAME average (`get_profiler_frames` divides the window
    # total by `frame_count`), so it is "the cost of one Parallax_Update call" ONLY while the main
    # loop completes one logic tick per video frame. One lag frame in the window and VInt_Lag
    # services the spare VBlank, one tick spans two frames, and EVERY row in the profile — the
    # walker's included — scales by ticks/frames.
    #
    # THIS IS NOT HYPOTHETICAL, IT BIT THIS FILE. Sweeping the deform shift 0..14 on an otherwise
    # identical 1-band fixture produced a per-line cost that went NEGATIVE from shift 3 to shift 4
    # (-1.25 cyc/line) and positive again after. The full per-routine diff showed every unrelated
    # row — RunObjects, TouchResponse, Tile_Cache_Fill — down by exactly 30/31 and VInt_Lag up
    # from 167 to 423: the machine had started lagging, the loop had not got cheaper. Measured
    # clean, the same fixture reads 22332 where the P2 sweep recorded 21611 = 22332 x 30/31.
    #
    # RETRIED, NOT NORMALISED. Scaling a diluted row by frames/ticks recovers the right number to
    # within the row's own integer rounding, but it makes every fixture's precision depend on how
    # many lag frames it happened to catch. Re-taking the window until it is preemption-free
    # measures the quantity directly instead. The lag here is a startup transient plus a rare
    # periodic frame (one in ~120 at idle), so a clean window is cheap to find; bounded, so a
    # fixture that genuinely cannot run preemption-free FAILS the check rather than spinning.
    # WARM-UP, UNPROFILED. Measured (8 consecutive windows per fixture): the window immediately
    # after the install ALWAYS lags — installing the fixture costs the frame that follows it —
    # and thereafter one window in four lags, a periodic engine frame at ~124-frame spacing.
    # Burning one window up front turns the retry loop from the common path into the exception.
    await b.call("emulator/run_frames", {"frames": sample})
    d_frames = d_ticks = d_lag = -1
    prof = None
    for _ in range(4):
        await b.call("emulator/write_memory", {"addr": poison_addr, "bytes": poison_hex})
        # THE SLEEPS ARE LOAD-BEARING — see raster_cost_probe's note. set_profiler only flips a
        # flag; the GUI main loop starts the recording and drains the ring.
        await b.call("emulator/set_profiler", {"enabled": True})
        await asyncio.sleep(0.4)
        fc0 = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Frame_Counter"]), "len": 2})
        lt0 = await b.call("emulator/read_memory", {"addr": hex(sym["Logic_Tick"]), "len": 4})
        lg0 = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Lag_Frame_Count"]), "len": 4})
        await b.call("emulator/run_frames", {"frames": sample})
        fc1 = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Frame_Counter"]), "len": 2})
        lt1 = await b.call("emulator/read_memory", {"addr": hex(sym["Logic_Tick"]), "len": 4})
        lg1 = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Lag_Frame_Count"]), "len": 4})
        d_frames = (int(fc1["bytes"], 16) - int(fc0["bytes"], 16)) & 0xFFFF
        d_ticks = int(lt1["bytes"], 16) - int(lt0["bytes"], 16)
        d_lag = int(lg1["bytes"], 16) - int(lg0["bytes"], 16)
        await asyncio.sleep(0.4)
        prof = await b.call("emulator/get_profiler_frames", {"frames": sample, "top": 300})
        await b.call("emulator/set_profiler", {"enabled": False})
        if d_frames == d_ticks and d_lag == 0:
            break

    # Two readbacks, both derived checks rather than decoration:
    #  - the config pointer must still aim at the fixture (nothing re-installed over it)
    #  - the fixture bytes must be unchanged (the replay recorder never woke up)
    ptr = await b.call("emulator/read_memory",
                       {"addr": hex(sym["Parallax_Current_Config"]), "len": 4})
    back = await b.call("emulator/read_memory",
                        {"addr": hex(scratch), "len": len(cfg)})
    idx1 = await b.call("emulator/read_memory",
                        {"addr": hex(sym["Replay_Record_Idx"]), "len": 2})
    # THE SPLIT WITNESS. An anchored fixture can reach `.bands_ready` through the overlay's
    # OWN early-outs (L past the channel's band_hi, or no band declared), in which case it
    # measures the early-out and not the split -- a gate asserting only "something ran". The
    # shadow view is where a split is visible: Step 4b copies band k down one slot, retops the
    # copy at L, and bumps the band count. So the shadow band TOPS are read back and the
    # anchored fixtures must show a different sequence from their un-anchored neighbours.
    scr = await b.call("emulator/read_memory",
                       {"addr": hex(sym["Effects_Screen_L"]), "len": 8})
    screen_l = [int(scr["bytes"][i:i + 4], 16) for i in range(0, 16, 4)]
    screen_l = [v - 0x10000 if v > 0x7FFF else v for v in screen_l]
    shadow = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Shadow_Bands"]), "len": BE_SIZE * 6})
    tops = [int(shadow["bytes"][i * BE_SIZE * 2:i * BE_SIZE * 2 + 2], 16) for i in range(6)]
    wy_ok = True
    if wy_addr is not None:
        wy1 = await b.call("emulator/read_memory", {"addr": hex(wy_addr), "len": 2})
        wy_ok = int(wy1["bytes"], 16) == wy_want
    return {"prof": prof, "shadow_tops": tops, "screen_l": screen_l,
            "slot_n": tops[n_cfg] if n_cfg < len(tops) else None,
            "frames": d_frames, "ticks": d_ticks, "lag_frames": d_lag,
            "preempt_free": d_frames == d_ticks and d_lag == 0,
            "ptr_ok": (int(ptr["bytes"][:8], 16) & 0xFFFFFF) == (scratch & 0xFFFFFF),
            "bytes_ok": back["bytes"].upper() == cfg.hex().upper(),
            "world_y_ok": wy_ok,
            "replay_idle": idx0["bytes"] == idx1["bytes"] == "0000"}


async def _live(b: BusClient, sym: dict[str, int], settle: int, sample: int) -> dict:
    """OUT OF SAMPLE: the config the game actually installs, measured with NOTHING poked but the
    camera freeze.

    The fixtures are all mutations of `ParallaxConfig_OJZ_Default`; the config live at the idle
    baseline is `ParallaxConfig_OJZ_Underwater`, four anchored bands whose ROM entries all say 15
    with the anchor turning BG sampling on below the split. So this row is the only test of the
    model that the fixture set could not have been tuned to pass, and P2's version of it is where
    the per-channel parameterization was caught mis-predicting by 12411 cycles.

    It reads the config OUT OF THE RUNNING MACHINE rather than naming a symbol: whichever config
    the section under the frozen camera installed is the one scored, and a build that changes it
    changes this check instead of silently invalidating it.
    """
    for attempt in range(4):
        try:
            await b.call("emulator/reset", {"wait": True, "run": False})
            break
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(1.5)
    await b.call("emulator/run_frames", {"frames": settle})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 5})

    ptr = await b.call("emulator/read_memory",
                       {"addr": hex(sym["Parallax_Current_Config"]), "len": 4})
    cfg_addr = int(ptr["bytes"][:8], 16) & 0xFFFFFF
    hdr = await b.call("emulator/read_memory", {"addr": hex(cfg_addr), "len": CFG_SIZE})
    n = int(hdr["bytes"][0:2], 16)
    full = await b.call("emulator/read_memory",
                        {"addr": hex(cfg_addr), "len": CFG_SIZE + n * BE_SIZE})
    cfg = bytes.fromhex(full["bytes"])
    tf = await b.call("emulator/read_memory",
                      {"addr": hex(sym["Parallax_Transition_Frames"]), "len": 1})

    await b.call("emulator/run_frames", {"frames": sample})          # burn the transient window
    poison_hex = (bytes([SLOT_POISON]) * BE_SIZE).hex().upper()
    poison_addr = hex(sym["Parallax_Shadow_Bands"] + n * BE_SIZE)
    d_frames = d_ticks = -1
    prof = None
    for _ in range(4):
        await b.call("emulator/write_memory", {"addr": poison_addr, "bytes": poison_hex})
        await b.call("emulator/set_profiler", {"enabled": True})
        await asyncio.sleep(0.4)
        fc0 = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Frame_Counter"]), "len": 2})
        lt0 = await b.call("emulator/read_memory", {"addr": hex(sym["Logic_Tick"]), "len": 4})
        await b.call("emulator/run_frames", {"frames": sample})
        fc1 = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Frame_Counter"]), "len": 2})
        lt1 = await b.call("emulator/read_memory", {"addr": hex(sym["Logic_Tick"]), "len": 4})
        d_frames = (int(fc1["bytes"], 16) - int(fc0["bytes"], 16)) & 0xFFFF
        d_ticks = int(lt1["bytes"], 16) - int(lt0["bytes"], 16)
        await asyncio.sleep(0.4)
        prof = await b.call("emulator/get_profiler_frames", {"frames": sample, "top": 300})
        await b.call("emulator/set_profiler", {"enabled": False})
        if d_frames == d_ticks:
            break
    scr = await b.call("emulator/read_memory",
                       {"addr": hex(sym["Effects_Screen_L"]), "len": 8})
    screen_l = [int(scr["bytes"][i:i + 4], 16) for i in range(0, 16, 4)]
    screen_l = [v - 0x10000 if v > 0x7FFF else v for v in screen_l]
    shadow = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Shadow_Bands"]), "len": BE_SIZE * 6})
    raw = bytes.fromhex(shadow["bytes"])
    ents = [(raw[i * BE_SIZE + BE_TOP_CELL], raw[i * BE_SIZE + BE_DSHIFT_A],
             raw[i * BE_SIZE + BE_DSHIFT_B]) for i in range(6)]
    return {"prof": prof, "cfg": cfg, "addr": cfg_addr,
            "shadow_tops": [e[0] for e in ents], "shadow_entries": ents,
            "split_happened": ents[n][0] != SLOT_POISON,
            "screen_l": screen_l, "transition": int(tf["bytes"], 16),
            "frames": d_frames, "ticks": d_ticks}


def live_terms(cfg: bytes, ents: list[tuple[int, int, int]], n_shadow: int) -> dict:
    """The model's inputs for the LIVE config, read from the SHADOW VIEW rather than re-derived.

    The fixtures pin `v_factor_bg` to 15, so Step 4a's rotation is the identity and a fixture's
    ROM tops ARE its shadow tops. The shipped config does not pin it: its tops are rotated by
    `Vscroll_BG >> 3` and clamped at 28 cells, so reading its ROM entries scores a band layout the
    filler never walks. (Measured: the ROM-entry derivation put the split at line 48 when the
    latch says 80 and the shadow view says 80.)

    So the out-of-sample row takes the filler's ACTUAL inputs — post-rotation, post-overlay tops
    and deform shifts, straight out of `Parallax_Shadow_Bands`. That is strictly better evidence
    than re-deriving both steps in Python and hoping the two agree.
    """
    tf = int.from_bytes(cfg[CFG_DEFORM_TAB_FG:CFG_DEFORM_TAB_FG + 4], "big") != 0
    tb = int.from_bytes(cfg[CFG_DEFORM_TAB_BG:CFG_DEFORM_TAB_BG + 4], "big") != 0
    only_f = only_b = both = shifts = bands_s = 0
    for i in range(n_shadow):
        lo = min(ents[i][0], 224)
        hi = min(ents[i + 1][0] if i + 1 < n_shadow else 224, 224)
        if hi <= lo:
            continue
        span = hi - lo
        f = ents[i][1] if (tf and ents[i][1] != NO_DEFORM) else None
        b = ents[i][2] if (tb and ents[i][2] != NO_DEFORM) else None
        if f is not None and b is not None:
            both += span
        elif f is not None:
            only_f += span
        elif b is not None:
            only_b += span
        if f is not None or b is not None:
            bands_s += 1
        shifts += span * ((f or 0) + (b or 0))
    return {"fg": only_f, "bg": only_b, "both": both,
            "shift_lines": shifts, "sampling_bands": bands_s}


def row(prof: dict, addr: int) -> dict | None:
    for r in prof.get("routines", []):
        try:
            a = int(str(r.get("addr", "$0")).lstrip("$"), 16) & 0xFFFFFF
        except ValueError:
            continue
        if a == (addr & 0xFFFFFF):
            return r
    return None


# ---- the fit ----------------------------------------------------------------
# Design matrix, one column per parameter. Solved by exact least squares (normal equations,
# Gaussian elimination) -- no numpy dependency, and with 12 fixtures over 7 parameters the
# system is well over-determined, which is the point: an over-determined fit is what makes a
# non-zero residual MEAN something instead of being absorbed.
# `multiband` is NOT a fudge column and it was not in the first fit. The first fit left a
# max |residual| of 9.2 cycles whose SIGN PATTERN named it: the 1 -> 2 band step measured 770
# (per-cell) and 869 (per-line) while every later step measured 747 and 846, i.e. a constant
# +23 paid once, on the first extra band, in BOTH modes. That is Step 4a's `.find_k` probe
# loop: at band_count 1 the `cmp.w d7, d2` with d2 = d7 = 1 branches straight to `.found_k`
# and the loop body never runs, so the cost appears the moment a second band exists and does
# not scale after. An indicator column is the honest shape for a cost like that; a per-band
# slope forced to absorb it is what produced the residual.
#
# THE SAMPLING COLUMNS TOOK THREE PASSES TO GET RIGHT, and each pass was forced by a residual
# rather than chosen. Recorded in order, because the sequence is the evidence:
#
#  1. PER-CHANNEL INDICATORS (`sample_fg`, `sample_bg`). Fitted W0..W12 to a max |residual| of
#     0.3 cycles and said the FG channel costs 17071 while the BG channel costs 11190 -- a 53%
#     asymmetry between two channels doing the same work. Nothing in the fixture set contradicted
#     it, so the fit was perfect and the model was wrong.
#  2. W13 (BG-ONLY sampling) contradicted it: 21625 against W7's 21611, i.e. the channels are
#     within 14 cycles of each other. |residual| blew up 0.3 -> 1702.7 the moment that point
#     entered, which is the model failing usefully.
#  3. PER-SAMPLED-LINE, three columns. W14/W15 sample only their LOWER band (112 and 80 lines),
#     which separates "the channel is on" from "224 lines sample" -- collinear until then,
#     because every earlier fixture sampled all bands or none. The marginal cost over the
#     matching no-sampling fixture is 17071/224, 8536/112 and 6097/80: 76.21, 76.21, 76.21.
#     Linear in lines, with NO fixed transition term at all. `sample_any` was an artifact of
#     step 1's parameterization and is gone.
#
# And the third column, `line_both`, is why two are not enough: one FG line is 76.21 and one BG
# line 76.27, but a line sampling BOTH is 126.17 rather than 152.5. The per-line loop shares its
# index and phase work across the planes, so the second channel on the same line costs 50.
#
# THE UNIT MATTERS FOR REAL CONTENT, which is how the collinearity was caught at all: the shipped
# ParallaxConfig_OJZ_Underwater samples only BELOW its anchored split, so a per-channel constant
# over-charges it by every line above that split. The per-channel model predicted 7100 for it
# against a measured 19511.
#
# AND A FOURTH PASS, P3 Task 1: `shift_lines`. Every sampling fixture W7..W15 uses deform shift
# 3, so the three per-line coefficients above are the shift-3 values and NOT constants -- the
# sampled loops end in `asr.w d3, d1`, a REGISTER-count shift, which is 6 + 2n cycles on the
# 68000. The shipped underwater config samples at shift 2, so the P2 model charged the shipped
# shape a shift it does not pay, and that error sat inside the `anchor` regime it could not be
# separated from. W22/W23 (shift 2 and 5, un-anchored, otherwise W7) excite the column inside
# the clean subset; the three line columns become the shift-0 intercepts.
#
# AND A FIFTH, same parcel: `band_sampling` — §5(c)'s named-but-never-fitted parameter, the
# per-band cost difference between a flat band and a sampling one. P2 called it collinear with
# `band_perline` "in every un-anchored fixture"; that is false for W14/W15, which are mixed, and
# the (LINES, S) pairs (224,1)/(112,1)/(80,1) identify it by differencing. W25 adds an S = 2 row.
# On this walker it is ~1 cycle — REPORTED, not omitted, because the parallax fill-unroll parcel
# measures the SAME column at a ~149-cycle class once the sampled loops are unrolled. A column
# that reads zero on one loop shape and 149 on another is a real parameter with two regimes, and
# leaving it out of the model is what made it look like it did not exist.
PARAMS = ["base", "band_percell", "line_mode", "band_perline", "multiband",
          "line_fg_only", "line_bg_only", "line_both", "shift_lines", "band_sampling",
          "vdeform", "anchor", "anchor_ops"]


def _segments(c: bytes, split: int | None = None):
    """Yield (span_lines, fg_shift_or_None, bg_shift_or_None) for every sampling SEGMENT.

    The one walk of the config both `sampled_lines` and `shift_lines` read, so the two can
    never disagree about which lines sample -- they are the same accounting, summed differently.

    A band's span is its own top to the next band's top (or 224 for the last), tops x 8 because
    the entries are authored in cells and Step 4a's rotation is the identity here. A band with
    `band_deform_shift_* == 15` takes `.lp_flat` and samples nothing, so its lines do not count.

    THREE COLUMNS AND NOT TWO, because the channels are not independent and the measurement says
    so. One FG line costs 76.21, one BG line 76.27 -- symmetric, as expected -- but a line
    sampling BOTH costs 126.17, not 152.5. The per-line loop shares its index and phase work
    between the two planes, so the second channel on the same line is 50 cycles rather than 76.
    Two columns cannot express that and a two-column fit was left with a 5895-cycle residual
    sitting entirely on the one fixture where both channels are live.

    THE OVERLAY IS APPLIED HERE, not ignored, and that is what lets this model describe SHIPPED
    content. Step 4b rewrites `band_deform_shift_a/b` to `pcfg_anchor_dsa/dsb` for every band
    at or below the anchored screen line L, so an anchored config's ROM band entries are NOT
    what the filler sees. `ParallaxConfig_OJZ_Underwater` is exactly this case: its four ROM
    bands all say 15 (no deform), and the anchor is what turns BG sampling on, for the 144
    lines below L = 80. Reading the ROM entries alone scores it at zero sampled lines and
    under-predicts it by 11k cycles.

    `split` is the LATCHED value of Effects_Screen_L[anchor_ch], read from the running machine
    -- a camera-dependent quantity, so it is measured per run and never assumed.
    """
    n = c[CFG_BAND_COUNT]
    tf = int.from_bytes(c[CFG_DEFORM_TAB_FG:CFG_DEFORM_TAB_FG + 4], "big") != 0
    tb = int.from_bytes(c[CFG_DEFORM_TAB_BG:CFG_DEFORM_TAB_BG + 4], "big") != 0
    tops = [c[CFG_SIZE + i * BE_SIZE + BE_TOP_CELL] * 8 for i in range(n)]
    anchored = c[CFG_ANCHOR_CH] != ANCHOR_NONE and split is not None
    L = max(0, min(224, split)) if anchored else 224

    for i in range(n):
        lo, hi = tops[i], (tops[i + 1] if i + 1 < n else 224)
        lo, hi = min(lo, 224), min(hi, 224)
        # Two segments per band: above the split it keeps its own shifts, at/below it takes
        # the config's anchored ones.
        for a, z, dsa, dsb in ((lo, min(hi, L),
                                c[CFG_SIZE + i * BE_SIZE + BE_DSHIFT_A],
                                c[CFG_SIZE + i * BE_SIZE + BE_DSHIFT_B]),
                               (max(lo, L), hi,
                                c[CFG_ANCHOR_DSA] if anchored
                                else c[CFG_SIZE + i * BE_SIZE + BE_DSHIFT_A],
                                c[CFG_ANCHOR_DSB] if anchored
                                else c[CFG_SIZE + i * BE_SIZE + BE_DSHIFT_B])):
            span = z - a
            if span <= 0:
                continue
            yield (span,
                   dsa if (tf and dsa != NO_DEFORM) else None,
                   dsb if (tb and dsb != NO_DEFORM) else None)


def sampled_lines(c: bytes, split: int | None = None) -> tuple[int, int, int]:
    """Screen LINES that sample, split three ways: FG only, BG only, BOTH."""
    only_f = only_b = both = 0
    for span, f, b in _segments(c, split):
        if f is not None and b is not None:
            both += span
        elif f is not None:
            only_f += span
        elif b is not None:
            only_b += span
    return only_f, only_b, both


def shift_lines(c: bytes, split: int | None = None) -> int:
    """Sum of the deform SHIFT over every sampled (line, channel) pair.

    The sampled loops end in `asr.w d3, d1` — a register-count shift, 6 + 2n cycles — so a line
    sampling at shift 5 costs more than the same line at shift 2, and a line sampling BOTH pays
    two of them. This column carries that; the three per-line columns become the shift-0
    intercepts. Excited by W22/W23 (shift 2 and 5 against W7's 3), un-anchored, so the slope is
    identified without leaning on an anchored row.
    """
    return sum(span * ((f or 0) + (b or 0)) for span, f, b in _segments(c, split))


def sampling_bands(c: bytes, split: int | None = None) -> int:
    """How many of the bands the filler walks take a SAMPLING loop rather than `.lp_flat`.

    §5(c)'s named parameter, given a column. A band's segments are what the filler walks — for an
    anchored config the overlay's split makes two of them out of one band — so counting segments
    with a live channel counts exactly the `.lp_fg`/`.lp_bg`/`.lp_both` entries.

    IT IS IDENTIFIED, and the P2 note that called it collinear was reading its own fixture set
    wrong. W7/W14/W15 all have ONE sampling band at 224/112/80 lines, so `(LINES, S)` pairs of
    (224,1), (112,1), (80,1) separate the per-line slope from the per-band constant by
    differencing; W25 adds an S = 2 row so the axis is not carried by the 0-vs-1 contrast alone.

    ITS VALUE IS A PROPERTY OF THE LOOP SHAPE, NOT A CONSTANT OF THE WALKER. On the un-unrolled
    per-line filler in this tree it is ~1 cycle — the sampling hoist and the flat path's own
    unroll-and-tail setup very nearly cancel. The parallax fill-unroll parcel measures it at a
    ~149-cycle class on ITS shape, because unrolling the sampled loops moves work out of the
    per-line body and into the per-band prologue. Same named parameter, two regimes, and the
    regime is the loop shape.
    """
    return sum(1 for span, f, b in _segments(c, split)
               if span > 0 and (f is not None or b is not None))


def anchor_ops(c: bytes, split: int | None = None) -> int:
    """Total iterations the Step-4b overlay's four loops run — the anchor's measured driver.

    P2 recorded `anchor` as TWO LABELLED REGIMES (456 / 1205) because W10 and W12 agreed to one
    cycle while W16 was 749 dearer, and named the regime "the overlay switches the filler's loop
    type at the split". Measured preemption-free, that is not what the anchor does: switching the
    loop type costs **27 cycles at 2 bands and 45 at 4**, and what actually moves the term is
    BAND COUNT — +222 (flat overlay) to +240 (turn-on) going from 2 bands to 4.

    The mechanism is the overlay's own loop trip counts, and they are a function of the band
    count `n` and the index `k` of the band the split lands in, nothing else
    (`engine/level/parallax.emp:889-987`):

        .anchor_find_k     min(k+1, n-1)   probes for the band containing L
        .anchor_shift_band n-1-k           entries shifted down one slot (skipped when 0)
        .anchor_shift_scroll n-1-k         the matching scroll words
        .anchor_shift_write  n-k           the deform-shift override walk, k+1 .. n

    ONE LUMPED COUNT, NOT FOUR COLUMNS, AND THAT IS DELIBERATE. Four columns would need four
    independent (n, k) classes and this fixture set has three — (2,0), (3,1), (4,1) — so a
    four-column fit would be exactly identified and its residual zero by construction, the defect
    §5(b) is a postmortem for. Lumping asserts the weaker, testable claim that the four loops cost
    about the same per iteration; the fit says ~59 cycles each, against a hand count of 62 for the
    `.anchor_find_k` body, and leaves a residual that is REPORTED rather than absorbed.
    """
    n = c[CFG_BAND_COUNT]
    if c[CFG_ANCHOR_CH] == ANCHOR_NONE or split is None:
        return 0
    L = max(0, min(224, split))
    tops = authored_tops(c)
    k = max((i for i in range(n) if tops[i] <= L), default=0)
    below = n - 1 - k
    return min(k + 1, n - 1) + (2 * below if below >= 1 else 0) + (n - k)


def design_row(name: str, fx: dict, split: int | None = None) -> list[float]:
    c = fx["cfg"]
    n = c[CFG_BAND_COUNT]
    per_line = (int.from_bytes(c[CFG_DEFORM_TAB_FG:CFG_DEFORM_TAB_FG + 4], "big") != 0
                or int.from_bytes(c[CFG_DEFORM_TAB_BG:CFG_DEFORM_TAB_BG + 4], "big") != 0
                or c[CFG_ANCHOR_CH] != ANCHOR_NONE)
    lf, lb, lboth = sampled_lines(c, split)
    vd = int.from_bytes(c[CFG_V_DEFORM_TAB_BG:CFG_V_DEFORM_TAB_BG + 4], "big") != 0
    an = c[CFG_ANCHOR_CH] != ANCHOR_NONE
    return [1.0,
            0.0 if per_line else float(n - 1),
            1.0 if per_line else 0.0,
            float(n - 1) if per_line else 0.0,
            1.0 if n >= 2 else 0.0,
            float(lf),
            float(lb),
            float(lboth),
            float(shift_lines(c, split)),
            float(sampling_bands(c, split)),
            1.0 if vd else 0.0,
            1.0 if an else 0.0,
            float(anchor_ops(c, split))]


def authored_tops(c: bytes) -> list[int]:
    """The band tops Step 4a writes into the shadow view, in SCREEN LINES.

    With v_factor_bg locked (every fixture) the rotation is the identity, so these are the
    config's own tops x 8 — which is what makes the shadow readback a witness of the OVERLAY
    rather than of Step 4a.
    """
    n = c[CFG_BAND_COUNT]
    return [c[CFG_SIZE + i * BE_SIZE + BE_TOP_CELL] * 8 for i in range(n)]


def realized_split(c: bytes, tops: list[int]) -> int | None:
    """The split line the overlay ACTUALLY produced, read out of the shadow view.

    Step 4b inserts one entry — a copy of band k retopped to L — at index k+1, so the live
    shadow tops are the authored tops with exactly one extra value spliced in at its sorted
    position. The extra value IS the realized split, and reading it here rather than trusting
    `Effects_Screen_L` is what makes the split-position fixture honest: `Raster_GetChannelBand`
    clamps L into the channel's authored raster band, so the latched L and the split the filler
    walks are not the same number in general.
    """
    n = c[CFG_BAND_COUNT]
    live, auth = tops[:n + 1], authored_tops(c)
    if len(live) < n + 1:
        return None
    for i in range(n):
        if live[i] != auth[i]:
            return live[i]     # the splice landed here; everything before it matched
    return live[n]             # split appended past the last authored band


def lstsq(A: list[list[float]], y: list[float]) -> list[float]:
    n = len(A[0])
    M = [[sum(A[k][i] * A[k][j] for k in range(len(A))) for j in range(n)]
         + [sum(A[k][i] * y[k] for k in range(len(A)))] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[p][i]) < 1e-9:
            M[i][i] = 1.0                       # unexcited column -> coefficient pinned to 0
            continue
        M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r == i:
                continue
            f = M[r][i] / M[i][i]
            for c in range(i, n + 1):
                M[r][c] -= f * M[i][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--sample", type=int, default=31)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    if not Path(args.rom).is_file():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 3
    sym = parse_lst(args.lst)
    missing = [s for s in SYMS if s not in sym]
    if missing:
        print(f"symbols missing: {', '.join(missing)}", file=sys.stderr)
        return 3

    rom = Path(args.rom).read_bytes()
    base = rom[sym["ParallaxConfig_OJZ_Default"]:
               sym["ParallaxConfig_OJZ_Default"] + CFG_SIZE]
    FX = fixtures(base, sym["DeformTable_Zero"])
    results: dict[str, list[dict]] = {k: [] for k in FX}
    live: list[dict] = []

    async def _sweep(sock: str) -> None:
        b = BusClient(socket_path=sock, client_id="pxprobe",
                      client_name="parallax_cost_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for k, fx in FX.items():
            results[k].append(await _one(b, sym, fx["cfg"], args.settle, args.sample,
                                         fx.get("world_y_delta", 0)))
        live.append(await _live(b, sym, args.settle, args.sample))
        await b.close()

    for _ in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))

    print(f"ROM {args.rom}   sample {args.sample} frames   repeats {args.repeat}")
    print("response = Parallax_Update's per-routine row, INCLUSIVE of its callees.")
    print("interrupts.hint is HBlank + VBlank in this ROM and is never read.\n")
    hdr = (f"{'FIX':4} {'bands':>5} {'mode':>8} {'FG/BG/both':>11} {'Px_Update':>10} {'spread':>7}"
           f" {'PerLine':>8} {'PerCell':>8}  varies")
    print(hdr)
    print("-" * len(hdr))
    y, A, names, table = [], [], [], {}
    failures: list[str] = []
    for k, fx in FX.items():
        runs = results[k]
        rows = [row(r["prof"], sym["Parallax_Update"]) for r in runs]
        if any(x is None for x in rows):
            print(f"{k:4} -- NO Parallax_Update ROW (fixture did not install?)")
            continue
        bad = [r for r in runs if not (r["ptr_ok"] and r["bytes_ok"] and r["replay_idle"]
                                       and r["world_y_ok"] and r["preempt_free"])]
        flag = ""
        if bad:
            flag = ("  !! " + ("pointer moved " if not bad[0]["ptr_ok"] else "")
                    + ("fixture bytes changed " if not bad[0]["bytes_ok"] else "")
                    + ("world anchor re-installed " if not bad[0]["world_y_ok"] else "")
                    + (f"LAGGING f/t={bad[0]['frames']}/{bad[0]['ticks']} "
                       f"lag={bad[0]['lag_frames']} " if not bad[0]["preempt_free"] else "")
                    + ("replay recorder ACTIVE" if not bad[0]["replay_idle"] else ""))
            for reason, key in (("config pointer moved off the fixture", "ptr_ok"),
                                ("fixture bytes were overwritten", "bytes_ok"),
                                ("the world anchor was re-installed over the poke", "world_y_ok"),
                                ("the replay recorder woke up", "replay_idle")):
                if not bad[0][key]:
                    failures.append(f"{k}: {reason}")
        cyc = [int(x["cycles"]) for x in rows]
        pl = row(runs[0]["prof"], sym["Parallax_Fill_PerLine"])
        pc = row(runs[0]["prof"], sym["Parallax_Fill_PerCell"])
        n = fx["cfg"][CFG_BAND_COUNT]
        anchored = fx["cfg"][CFG_ANCHOR_CH] != ANCHOR_NONE
        latched = runs[0]["screen_l"][fx["cfg"][CFG_ANCHOR_CH]] if anchored else None
        # THE SPLIT USED BY THE MODEL IS THE REALIZED ONE, read out of the shadow view, not the
        # latched L. The two differ whenever Raster_GetChannelBand clamps, and scoring a fixture
        # against a split the filler did not walk is the same class of defect as scoring an
        # anchored config off its ROM band entries. `split_latched` is kept beside it so a clamp
        # is visible rather than silently absorbed.
        split = realized_split(fx["cfg"], runs[0]["shadow_tops"]) if anchored else None
        mode = "per-line" if design_row(k, fx, split)[2] else "per-cell"
        lf, lb, lboth = sampled_lines(fx["cfg"], split)
        clamp = ""
        if anchored and split is not None and split != latched:
            clamp = f"  [L latched {latched} -> split {split}]"
        print(f"{k:4} {n:>5} {mode:>8} {lf:>3}/{lb:<3}/{lboth:<3} {cyc[0]:>10} {max(cyc)-min(cyc):>7}"
              f" {(pl['cycles'] if pl else 0):>8} {(pc['cycles'] if pc else 0):>8}"
              f"  {fx['vary']}{clamp}{flag}")
        table[k] = {"cycles": cyc, "bands": n, "mode": mode, "what": fx["what"],
                    "vary": fx["vary"],
                    "fill_per_line": pl["cycles"] if pl else 0,
                    "fill_per_cell": pc["cycles"] if pc else 0,
                    "sampled_lines_fg_bg_both": [lf, lb, lboth],
                    "shift_lines": shift_lines(fx["cfg"], split),
                    "sampling_bands": sampling_bands(fx["cfg"], split),
                    "anchor_ops": anchor_ops(fx["cfg"], split),
                    "shadow_tops": runs[0]["shadow_tops"],
                    "slot_n": [r["slot_n"] for r in runs],
                    "authored_tops": authored_tops(fx["cfg"]),
                    "anchored": anchored,
                    "split_line": split,
                    "split_latched": latched,
                    "frames_ticks": [[r["frames"], r["ticks"], r["lag_frames"]] for r in runs],
                    "checks_ok": not bad}
        y.append(float(cyc[0]))
        A.append(design_row(k, fx, split))
        names.append(k)

    if len(y) < len(PARAMS):
        print("\nnot enough fixtures measured to fit")
        return 4
    coef = lstsq(A, y)
    print("\nFITTED ADDITIVE MODEL — cycles for one Parallax_Update call")
    for p, c in zip(PARAMS, coef):
        print(f"  {p:14} {c:>10.1f}")
    print("\nRESIDUAL PER FIXTURE (measured - model). THIS IS THE DELIVERABLE.")
    worst = 0.0
    res = {}
    for k, a, m in zip(names, A, y):
        pred = sum(ai * ci for ai, ci in zip(a, coef))
        r = m - pred
        res[k] = r
        worst = max(worst, abs(r))
        print(f"  {k:4} measured {m:>8.0f}  model {pred:>8.1f}  residual {r:>+8.1f}")
    print(f"\nmax |residual| = {worst:.1f} cycles"
          f"  ({100.0 * worst / max(y):.2f}% of the largest fixture)")

    # ---- WHERE THE RESIDUAL LIVES, and it does not live everywhere -------------------
    # The full-set residual above is dominated by the three ANCHORED fixtures. Re-fitting
    # without them separates a model that IS zero-residual from an overlay term that is not
    # constant -- which is a far more useful statement than one averaged number, and it is what
    # the plan means by naming the missing parameter rather than smoothing it.
    plain = [i for i, k in enumerate(names) if table[k]["split_line"] is None]
    anch = [i for i, k in enumerate(names) if table[k]["split_line"] is not None]
    if plain and anch:
        cp = lstsq([A[i] for i in plain], [y[i] for i in plain])
        wp = max(abs(y[i] - sum(a * c for a, c in zip(A[i], cp))) for i in plain)
        print(f"\nUN-ANCHORED SUBSET ({len(plain)} fixtures): max |residual| = {wp:.2f} cycles")
        for p, c in zip(PARAMS, cp):
            if p not in ("anchor", "anchor_ops"):
                print(f"  {p:14} {c:>10.2f}")
        print("\nTHE ANCHORED OVERLAY IS NOT A CONSTANT — but it is not two regimes either. Each"
              "\nanchored fixture's cost over the un-anchored model, with the overlay's own loop"
              "\ntrip count beside it:")
        ov = {}
        for i in anch:
            a = list(A[i])
            a[PARAMS.index("anchor")] = 0.0
            a[PARAMS.index("anchor_ops")] = 0.0
            pred = sum(x * c for x, c in zip(a, cp))
            ov[names[i]] = y[i] - pred
            tk = table[names[i]]
            print(f"  {names[i]:4} bands={tk['bands']} ops={tk['anchor_ops']}"
                  f" sampling_bands={tk['sampling_bands']}"
                  f" sampled(fg/bg/both)={tk['sampled_lines_fg_bg_both']}"
                  f" split={tk['split_line']}"
                  f"   measured {y[i]:.0f} - model {pred:.1f} = {y[i] - pred:+.1f}")
        # The overlay term, fitted over those costs as `anchor + anchor_ops x trips`. Two
        # parameters over eight fixtures at three trip counts -- over-determined, unlike the
        # four-column mechanistic form the (n, k) classes cannot identify.
        Aa = [[1.0, float(table[names[i]]["anchor_ops"])] for i in anch]
        ya = [ov[names[i]] for i in anch]
        ca = lstsq(Aa, ya)
        print(f"\n  OVERLAY TERM FITTED: anchor = {ca[0]:.1f} + {ca[1]:.2f} x overlay_loop_trips")
        wa = 0.0
        for i in anch:
            p = ca[0] + ca[1] * table[names[i]]["anchor_ops"]
            wa = max(wa, abs(ov[names[i]] - p))
            print(f"    {names[i]:4} trips={table[names[i]]['anchor_ops']}"
                  f"  measured {ov[names[i]]:+8.1f}  model {p:+8.1f}"
                  f"  residual {ov[names[i]] - p:+7.1f}")
        print(f"  max |residual| on the overlay term = {wa:.1f} cycles")
        print("  What is LEFT in that residual is the loop-type change the P2 note called the"
              "\n  regime: turn-on costs +27 (2 bands) / +45 (4 bands) over a flat overlay, and the"
              "\n  BG channel ~25 over FG. Recorded, not fitted — one fixture pair per cell.")

    # ---- CHECK 3: the split witness, and it REFUSES rather than reporting -------------
    # An anchored fixture can reach `.bands_ready` through the overlay's own early-outs (L past
    # the channel's band_hi, no band declared, PARALLAX_ANCHOR_NONE) and measure the early-out
    # instead of the split — a gate asserting only "something ran".
    #
    # TWO-SIDED, ARM-WORD FORM. `_one` poisons shadow slot `band_count` with $FF before the
    # sample. Step 4a writes exactly `band_count` entries; slot `band_count` is written by the
    # overlay's split and by nothing else. So:
    #     anchored   -> the slot must hold a REAL top (0..224) and the tops must stay ordered
    #     un-anchored-> the slot must still read $FF
    # The second half is what makes this non-vacuous: it proves the poison reaches the machine
    # and is not being overwritten by some other writer, which a one-sided "it changed" check
    # cannot distinguish from a stale buffer.
    #
    # The P2-era neighbour differential is kept below as well. It is weaker (it cannot cover a
    # fixture with no same-shaped neighbour, and it reads stale slots as evidence), but it is
    # the check the published model was taken under and dropping it silently would remove a
    # witness rather than replace one.
    print("\nPREEMPTION CHECK — the per-routine row is a per-VIDEO-FRAME average, so it is one"
          "\nParallax_Update call ONLY at frames/tick = 1.000 (see _one).")
    for k in table:
        ft = table[k]["frames_ticks"]
        ok = all(f == t and lg == 0 for f, t, lg in ft)
        print(f"  {k:4} " + "  ".join(f"{f}/{t} lag {lg}" for f, t, lg in ft)
              + ("" if ok else "   !! DILUTED — this row is not one call"))
        if not ok:
            failures.append(f"{k}: frames != ticks {ft} — the row is a diluted average")
    print("\nshadow band tops (screen lines). Slot band_count is poisoned with $FF before the"
          "\nsample: an ANCHORED fixture must overwrite it, an un-anchored one must not.")
    for k in table:
        t = table[k]
        slot = t["slot_n"][0]
        if t["anchored"]:
            ok = (all(s != SLOT_POISON for s in t["slot_n"])
                  and t["split_line"] is not None
                  and 0 <= t["split_line"] <= 224
                  and t["shadow_tops"][:t["bands"] + 1]
                  == sorted(t["shadow_tops"][:t["bands"] + 1]))
            verdict = (f"split at {t['split_line']}" if ok
                       else "!! NO SPLIT — slot still poisoned or tops out of order")
        else:
            ok = all(s == SLOT_POISON for s in t["slot_n"])
            verdict = ("un-anchored, slot untouched" if ok
                       else "!! slot band_count was WRITTEN by an un-anchored fixture")
        if not ok:
            failures.append(f"{k}: split witness — {verdict}")
        print(f"  {k:4} {t['shadow_tops']}  slot[{t['bands']}]="
              f"{'$FF' if slot == SLOT_POISON else slot:>4}  {verdict}")
    # Pairs must share a band count or the differential answers "the shapes differ", not
    # "the split happened" — the vacuous-gate failure mode this tree has a postmortem for.
    for a_k, p_k in (("W10", "W5"), ("W12", "W6"), ("W17", "W5"), ("W21", "W5"),
                     ("W18", "W24"), ("W16", "W24"), ("W19", "W24"), ("W20", "W24")):
        if a_k in table and p_k in table:
            same = (table[a_k]["shadow_tops"][:table[a_k]["bands"]]
                    == table[p_k]["shadow_tops"][:table[p_k]["bands"]]
                    and table[a_k]["bands"] == table[p_k]["bands"])
            if same:
                failures.append(f"{a_k} vs {p_k}: shadow tops IDENTICAL — no split")
            print(f"  {a_k} vs {p_k}: "
                  + ("!! IDENTICAL — the split did NOT happen, the anchor coefficient is"
                     " measuring an early-out" if same else "differ — the split happened"))

    # ---- OUT OF SAMPLE: the shipped config, scored by the fitted model --------------
    live_out = {}
    if live:
        lv = live[0]
        lcfg = lv["cfg"]
        lch = lcfg[CFG_ANCHOR_CH]
        ln = lcfg[CFG_BAND_COUNT]
        split_ran = lv["split_happened"]
        n_shadow = ln + 1 if split_ran else ln
        ents = lv["shadow_entries"]
        L = lv["screen_l"][lch] if lch != ANCHOR_NONE else None
        # k = the split entry's index minus one. The split entry is the first slot at or below
        # index 1 whose top equals the latched L; the overlay puts it at k+1 and tops it at L.
        k = next((i - 1 for i in range(1, n_shadow) if ents[i][0] == L), 0) if split_ran else 0
        ops = (min(k + 1, ln - 1) + (2 * (ln - 1 - k) if ln - 1 - k >= 1 else 0)
               + (ln - k)) if split_ran else 0
        lt = live_terms(lcfg, ents, n_shadow)
        lrow = row(lv["prof"], sym["Parallax_Update"])
        lmeas = [int(row(x["prof"], sym["Parallax_Update"])["cycles"]) for x in live]
        vd = int.from_bytes(lcfg[CFG_V_DEFORM_TAB_BG:CFG_V_DEFORM_TAB_BG + 4], "big") != 0
        per_line = (int.from_bytes(lcfg[CFG_DEFORM_TAB_FG:CFG_DEFORM_TAB_FG + 4], "big") != 0
                    or int.from_bytes(lcfg[CFG_DEFORM_TAB_BG:CFG_DEFORM_TAB_BG + 4], "big") != 0
                    or lch != ANCHOR_NONE)
        a = [1.0,
             0.0 if per_line else float(ln - 1),
             1.0 if per_line else 0.0,
             float(ln - 1) if per_line else 0.0,
             1.0 if ln >= 2 else 0.0,
             float(lt["fg"]), float(lt["bg"]), float(lt["both"]),
             float(lt["shift_lines"]), float(lt["sampling_bands"]),
             1.0 if vd else 0.0,
             1.0 if split_ran else 0.0,
             float(ops)]
        pred = sum(x * c for x, c in zip(a, coef))
        print(f"\nOUT OF SAMPLE — the config the game installs at the idle baseline, NOTHING poked"
              f"\nbut the camera freeze. addr ${lv['addr']:06X}, {ln} authored bands,"
              f" anchor ch {lch}, transition frames {lv['transition']}")
        print(f"  shadow view (top,dsa,dsb) x{n_shadow}: {ents[:n_shadow]}"
              f"   split slot poison overwritten: {split_ran}")
        print(f"  latched L {lv['screen_l'][:2]}   split band k={k}   overlay trips {ops}")
        print(f"  sampled lines fg/bg/both = {lt['fg']}/{lt['bg']}/{lt['both']}"
              f"   shift_lines {lt['shift_lines']}   sampling_bands {lt['sampling_bands']}")
        print(f"  frames/ticks {lv['frames']}/{lv['ticks']}   measured {lmeas}"
              f"   spread {max(lmeas) - min(lmeas)}")
        gap = int(lrow["cycles"]) - pred
        print(f"  model {pred:.1f}   measured {int(lrow['cycles'])}   gap {gap:+.1f}"
              f"  ({100.0 * gap / int(lrow['cycles']):+.2f}%)")
        live_out = {"addr": lv["addr"], "bands": ln, "split_band_k": k, "overlay_trips": ops,
                    "latched_L": L, "terms": lt,
                    "measured": lmeas, "model": pred, "gap": gap,
                    "frames_ticks": [[x["frames"], x["ticks"]] for x in live],
                    "shadow_entries": ents[:n_shadow], "config": lcfg.hex().upper()}
        if any(x["frames"] != x["ticks"] for x in live):
            failures.append("LIVE: frames != ticks — the out-of-sample row is a diluted average")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"fixtures": table, "params": dict(zip(PARAMS, coef)),
             "residuals": res, "max_abs_residual": worst,
             "out_of_sample": live_out,
             "failures": failures}, indent=2) + "\n")
        print(f"\nraw: {args.out}")
    if failures:
        print("\nDERIVED CHECKS FAILED — the cycle rows above are NOT evidence:")
        for f in failures:
            print(f"  {f}")
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
