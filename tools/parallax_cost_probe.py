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
                "cfg": build(base, bands=4, tab_bg=zero_tab, anchor=0,
                             dsa=NO_DEFORM, dsb=2,
                             shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
    }


SYMS = ("Parallax_Update", "Parallax_Fill_PerLine", "Parallax_Fill_PerCell",
        "Parallax_Current_Config", "Parallax_Target_Config", "Parallax_Transition_Frames",
        "Debug_Scene_Freeze", "Replay_Record_Buf", "Replay_Record_Idx",
        "DeformTable_Zero", "ParallaxConfig_OJZ_Default", "Effects_Screen_L")


async def _one(b: BusClient, sym: dict[str, int], cfg: bytes,
               settle: int, sample: int) -> dict:
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

    idx0 = await b.call("emulator/read_memory",
                        {"addr": hex(sym["Replay_Record_Idx"]), "len": 2})
    # THE SLEEPS ARE LOAD-BEARING — see raster_cost_probe's note. set_profiler only flips a
    # flag; the GUI main loop starts the recording and drains the ring.
    await b.call("emulator/set_profiler", {"enabled": True})
    await asyncio.sleep(0.4)
    await b.call("emulator/run_frames", {"frames": sample})
    await asyncio.sleep(0.4)
    prof = await b.call("emulator/get_profiler_frames", {"frames": sample, "top": 300})
    await b.call("emulator/set_profiler", {"enabled": False})

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
    return {"prof": prof, "shadow_tops": tops, "screen_l": screen_l,
            "ptr_ok": (int(ptr["bytes"][:8], 16) & 0xFFFFFF) == (scratch & 0xFFFFFF),
            "bytes_ok": back["bytes"].upper() == cfg.hex().upper(),
            "replay_idle": idx0["bytes"] == idx1["bytes"] == "0000"}


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
PARAMS = ["base", "band_percell", "line_mode", "band_perline", "multiband",
          "line_fg_only", "line_bg_only", "line_both", "vdeform", "anchor"]


def sampled_lines(c: bytes, split: int | None = None) -> tuple[int, int, int]:
    """Screen LINES that sample, split three ways: FG only, BG only, BOTH.

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

    only_f = only_b = both = 0
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
            f = tf and dsa != NO_DEFORM
            b = tb and dsb != NO_DEFORM
            if f and b:
                both += span
            elif f:
                only_f += span
            elif b:
                only_b += span
    return only_f, only_b, both


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
            1.0 if vd else 0.0,
            1.0 if an else 0.0]


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

    async def _sweep(sock: str) -> None:
        b = BusClient(socket_path=sock, client_id="pxprobe",
                      client_name="parallax_cost_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for k, fx in FX.items():
            results[k].append(await _one(b, sym, fx["cfg"], args.settle, args.sample))
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
    for k, fx in FX.items():
        runs = results[k]
        rows = [row(r["prof"], sym["Parallax_Update"]) for r in runs]
        if any(x is None for x in rows):
            print(f"{k:4} -- NO Parallax_Update ROW (fixture did not install?)")
            continue
        bad = [r for r in runs if not (r["ptr_ok"] and r["bytes_ok"] and r["replay_idle"])]
        flag = ""
        if bad:
            flag = ("  !! " + ("pointer moved " if not bad[0]["ptr_ok"] else "")
                    + ("fixture bytes changed " if not bad[0]["bytes_ok"] else "")
                    + ("replay recorder ACTIVE" if not bad[0]["replay_idle"] else ""))
        cyc = [int(x["cycles"]) for x in rows]
        pl = row(runs[0]["prof"], sym["Parallax_Fill_PerLine"])
        pc = row(runs[0]["prof"], sym["Parallax_Fill_PerCell"])
        n = fx["cfg"][CFG_BAND_COUNT]
        split = runs[0]["screen_l"][fx["cfg"][CFG_ANCHOR_CH]] \
            if fx["cfg"][CFG_ANCHOR_CH] != ANCHOR_NONE else None
        mode = "per-line" if design_row(k, fx, split)[2] else "per-cell"
        lf, lb, lboth = sampled_lines(fx["cfg"], split)
        print(f"{k:4} {n:>5} {mode:>8} {lf:>3}/{lb:<3}/{lboth:<3} {cyc[0]:>10} {max(cyc)-min(cyc):>7}"
              f" {(pl['cycles'] if pl else 0):>8} {(pc['cycles'] if pc else 0):>8}"
              f"  {fx['vary']}{flag}")
        table[k] = {"cycles": cyc, "bands": n, "mode": mode, "what": fx["what"],
                    "vary": fx["vary"],
                    "fill_per_line": pl["cycles"] if pl else 0,
                    "fill_per_cell": pc["cycles"] if pc else 0,
                    "sampled_lines_fg_bg_both": [lf, lb, lboth],
                    "shadow_tops": runs[0]["shadow_tops"],
                    "split_line": split,
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
            if p != "anchor":
                print(f"  {p:14} {c:>10.2f}")
        print("\nTHE ANCHORED OVERLAY IS NOT A CONSTANT. Each anchored fixture's cost over the"
              "\nun-anchored model, which is what a single `anchor` coefficient has to be:")
        for i in anch:
            a = list(A[i])
            a[PARAMS.index("anchor")] = 0.0
            pred = sum(x * c for x, c in zip(a, cp))
            print(f"  {names[i]:4} bands={table[names[i]]['bands']}"
                  f" sampled(fg/bg/both)={table[names[i]]['sampled_lines_fg_bg_both']}"
                  f" split={table[names[i]]['split_line']}"
                  f"   measured {y[i]:.0f} - model {pred:.1f} = {y[i] - pred:+.1f}")

    # The split witness, printed as a DIFFERENTIAL: an anchored fixture whose shadow tops match
    # its un-anchored neighbour's took the overlay's early-out and measured nothing.
    print("\nshadow band tops (screen lines) — the anchored fixtures must DIFFER from their"
          " un-anchored neighbours, or the overlay took an early-out")
    for k in table:
        print(f"  {k:4} {table[k]['shadow_tops']}   {table[k]['vary']}")
    for anch, plain in (("W10", "W5"), ("W12", "W6")):
        if anch in table and plain in table:
            same = table[anch]["shadow_tops"] == table[plain]["shadow_tops"]
            print(f"  {anch} vs {plain}: "
                  + ("!! IDENTICAL — the split did NOT happen, the anchor coefficient is"
                     " measuring an early-out" if same else "differ — the split happened"))
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"fixtures": table, "params": dict(zip(PARAMS, coef)),
             "residuals": res, "max_abs_residual": worst}, indent=2) + "\n")
        print(f"\nraw: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
