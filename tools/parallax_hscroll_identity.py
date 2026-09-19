#!/usr/bin/env python3
"""parallax_hscroll_identity — the walker's OUTPUT, byte for byte, across ROMs.

WHY THIS EXISTS. `parallax_cost_probe.py` measures what the walker COSTS. Nothing measured
what it PRODUCES, so a cheaper fill that computed slightly different scroll words would have
passed every lane in the tree: the replay net is pixel-blind, `ab_runner` freezes the scene,
and no golden covers `Hscroll_Buffer`. This probe closes that hole for any parcel that
rewrites the fill: it captures the 896-byte buffer for a fixture matrix on a reference ROM and
re-captures it on the candidate, and the two must be EQUAL. The cost may move; the values may
not.

HOW A FIXTURE IS INSTALLED. Identical to `parallax_cost_probe` and deliberately so -- the same
`build()` builds the config, the same four pokes aim `Parallax_Current_Config` at
`Replay_Record_Buf`, and the same three derived checks (pointer still aimed, fixture bytes
unchanged, replay recorder idle) run every time. A fixture that failed to install would
otherwise "match" trivially, because both ROMs would be filling from the same shipped config.
⚠ ONE THING IS NO LONGER IDENTICAL, as of 2026-09-19: an ANCHORED fixture also installs its
own `Effects_World_Y[0]`, absolutely, where `parallax_cost_probe` only PERTURBS the live one
by a delta. The reasoning is in the banner above `split_line`; the short version is that the
overlay takes two inputs and a fixture that synthesizes one of them is half a fixture.

WHAT MAKES THE MATRIX NON-VACUOUS -- the two coverage witnesses, ASSERTED not assumed.
A fill rewritten around a walking table pointer has exactly two new failure surfaces, and a
matrix that misses either is a gate that cannot fail:

  * THE 256-BYTE WRAP. The curve index is (phase + line) & $FF, so a walking pointer must be
    reset when it runs off the end. The deform phase advances every frame, so sampling MANY
    consecutive frames sweeps the wrap across the screen -- but only if the phase actually
    moves and only if some frame's band really does straddle it. `wrap_frames` counts the
    frames whose sampled run crosses a multiple of 256, read from the live phase registers,
    and the run FAILS if the matrix never produced one.
  * SPANS THAT ARE NOT MULTIPLES OF 8. An unrolled fill needs a remainder tail, and every
    cell-aligned fixture hides a broken one: config band tops are CELL rows, so their screen
    lines are all multiples of 8. Fixture ID8 unlocks `v_factor_bg`, which lets Step 4a's
    vscroll rotation land shadow tops on arbitrary scanlines. `ragged_spans` counts spans with
    span % 8 != 0 across the matrix, read back from `Parallax_Shadow_Bands`, and the run FAILS
    if there were none.

Both witnesses are printed on every run, pass or fail, so a future change that quietly makes
the matrix cell-aligned again is visible rather than silently green.

STATUS 2026-09-19: GREEN, AND THE THREE REDS WERE CLOSED BY GIVING THE FIXTURE THE STATE IT
WAS MISSING -- NOT BY RELAXING A WITNESS. The witnesses got STRICTER in the same change.

WHAT WAS WRONG, and it was the fixture. From 2026-09-18 this file reported three failures on
s4.debug.bin (crc32 62238a15): ID7 and ID8 sampled a buffer identical to the flat fixture ID1,
and COVERAGE found no non-multiple-of-8 span anywhere in the matrix. All three were ONE cause.
A split line is not a config field: it is `Effects_Screen_L[ch]`, re-latched every frame from
`Effects_World_Y[ch] - Camera_Y`. The anchored fixtures set `anchor=0` in their CONFIG and
inherited the ANCHOR BANK from whatever section the boot had loaded -- and the boot region
leaves channel 0 at PATCH_ANCHOR_NONE ($7FFF), so L came out ~32623, past every band, and the
overlay correctly did nothing. The engine was right the whole time; the fixture asked for a
split while supplying one of the two inputs a split takes. The tell was in the printed spans,
ID7/ID8 [56, 56, 56, -8, 64]: a NEGATIVE span, i.e. `nshadow = bands + 1` reading a slot
nothing had written that frame.

WHAT CHANGED: the anchored fixtures now install their own channel-0 world anchor, at a split
line DERIVED from the matrix's own band tops (see `split_line`), and four checks were added
that did not exist while the split never fired --

  * the installed anchor is read back after the sample (a preset re-install or the anchor
    mover would otherwise change what was measured, silently);
  * the whole realized shadow view must equal the fixture's own config tops with
    `anchor_wy - Camera_Y` inserted -- so a split in the wrong place, or no split, is named;
  * no span may be non-positive, which turns the old [.., -8, ..] artifact into a failure;
  * `shipped_precedent()` MEASURES, every run, that the loaded act still pairs a parallax
    config consuming channel 0 with a preset seeding a real world anchor on it. That is the
    original diagnosis -- "the fixture picks its anchor channel by NUMBER, and which channel
    carries a world anchor is a property of the scene" -- made mechanical instead of left as
    a rot the fixture cannot feel.

MEASURED 2026-09-19, s4.debug.bin crc32 62238a15 / 848,075 B, 20.6 s at load average 2.20:
exit 0. ID6 spans [104, 8, 112]; ID7 [56, 48, 8, 56, 56]; ID8 (camera 147) [56, 45, 11, 56, 56];
ID9 [101, 11, 112]. RAGGED SPANS 4 (was 0), WRAPPING FRAMES 240. ID7/ID8 now carry digests of
their own rather than ID1's. THE CONTROL: ID0-ID5, the un-anchored fixtures, are byte-identical
to the pre-change run -- digests 4ef90c32e72c / 4ef90c32e72c / 108caaa4b699 / c7aaecfd9e6a /
e1ccd44faa9b / 96a227f98067 before and after -- so the change reached only the fixtures it was
aimed at.

AND THE STATE IS ONE THE GAME REACHES, measured rather than argued. The loaded act's own region
table (13 regions) has exactly one row pairing a consuming `anchor_ch` with a real world anchor
on that channel: region 5, x 4096..5119 y 2048..4095, `OJZ_Preset_Sec5` ->
`ParallaxConfig_OJZ_Underwater`, `anchor_ch` 0, `ep_patch_world_ys[0]` = 2272. That is what the
player walks into, and it is the shape these fixtures build. The boot region (region 0) declares
`anchor_ch` 0 as well and leaves channel 0 at the sentinel -- deliberately, by a dated owner
ruling of 2026-09-09 recorded verbatim in games/sonic4/data/effects/ojz_effects.emp, reversible
in two tokens (`224` back into `ep_patch_world_ys[0]`). The field is not dead data; its producer
is switched off in that one region.

Usage:
    python3 tools/parallax_hscroll_identity.py --rom s4.debug.bin --lst s4.debug.lst \
        --out ref.json                       # capture a reference
    python3 tools/parallax_hscroll_identity.py --rom s4.debug.bin --lst s4.debug.lst \
        --ref ref.json                       # compare against it (exit 1 on any diff)
"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path, harness_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
HARNESS = str(harness_path())  # legacy oracle_gui launcher; loud if absent
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient            # noqa: E402
from launcher import headless_emulator   # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402
import parallax_cost_probe as pcp        # noqa: E402
import region_table                      # noqa: E402  -- the one out-of-assembler Act/Region reader
from parallax_cost_probe import (        # noqa: E402
    ANCHOR_NONE, CFG_ANCHOR_CH, CFG_BAND_COUNT, CFG_SIZE, CFG_V_FACTOR_BG,
    NO_DEFORM, build,
)

# `BE_SIZE` IS NOT IMPORTED BY VALUE, AND THAT IS THE WHOLE REPAIR (2026-09-18).
#
# It used to be, on the line above. On 2026-08-29 08:56 (57bd877c) parallax_cost_probe stopped
# carrying `BE_SIZE = 10` and made it `BE_SIZE = None`, to be installed from the .lst under
# measure by `set_stride()` — deliberately None so that a caller who forgets gets an immediate
# TypeError instead of a plausible number. Every sibling took the call: curve_probe's main(),
# deform_own_cost_probe's derive_stride(), parallax_cost_probe's own main(). This module did
# not, and `from parallax_cost_probe import BE_SIZE` binds the VALUE at import time, so even a
# later `pcp.set_stride()` by somebody else could not have reached it.
#
# The result, every run since 2026-08-29:
#     File "tools/parallax_cost_probe.py", line 240, in band
#       b = bytearray(BE_SIZE)
#   TypeError: cannot convert 'NoneType' object to bytearray
# — raised out of the first `build()` in `matrix()`, before a single emulator boot.
#
# IT FAILED THE SAFE WAY AND THAT IS WORTH SAYING. A stale 10 would have laid every fixture
# out at half the walker's stride and captured a reference that looked like a clean 896-byte
# buffer; this refused to start instead. Loud beats plausible. The two reads below now name
# `pcp.BE_SIZE` through the module so they cannot go stale again the same way, and main()
# calls `pcp.set_stride(sym)` from the .lst being measured.

HSCROLL_BYTES = 224 * 4          # the whole buffer: 224 lines x (FG word + BG word)
FRAMES = 24                      # consecutive frames per fixture; the phase sweeps the wrap

SYMS = ("Parallax_Current_Config", "Parallax_Target_Config", "Parallax_Transition_Frames",
        "Debug_Scene_Freeze", "Replay_Record_Buf", "Replay_Record_Idx",
        "DeformTable_OJZ_Calm", "DeformTable_Shimmer", "ParallaxConfig_OJZ_Default",
        "Parallax_Shadow_Bands", "Hscroll_Buffer", "Camera_Y",
        "Parallax_Deform_Phase_FG", "Parallax_Deform_Phase_BG",
        # The anchored fixtures' OTHER input, and the act the precedent check walks.
        "Effects_World_Y", "Current_Act_Ptr")

# THE CURVES MUST DEFLECT. `parallax_cost_probe` attaches `DeformTable_Zero` because a cost
# probe only needs the sampling path to RUN. An identity probe attaching it would be vacuous
# in the worst way: sampling a table of zeros writes base + 0, which is byte-for-byte what the
# flat path writes, so every sampled fixture would "match" a fill that never sampled at all.
# Measured on the first draft of this file -- seven of nine fixtures shared one digest with
# the all-flat fixture. Two DIFFERENT non-zero curves are used so FG and BG are distinguishable
# from each other as well as from flat, and `--ref` comparison is preceded by a vacuity check
# that every sampled fixture differs from ID1.
CURVE_FG = "DeformTable_OJZ_Calm"    # amplitude 96, period 64
CURVE_BG = "DeformTable_Shimmer"     # amplitude 8,  period 32

# The camera Y each fixture is pinned at, AFTER Debug_Scene_Freeze. 144 is the idle baseline.
# A camera that is not a multiple of 8 is what makes an anchored split land on a ragged
# scanline: L is a world anchor minus the camera, and the filler reads shadow tops in SCREEN
# LINES, so an odd camera gives an odd span. Config band tops are CELL rows and can never do
# it, which is why every cell-aligned fixture hides a broken remainder tail.
CAM_Y_IDLE = 144
CAM_Y_RAGGED = 147

SCREEN_LINES = 224               # the visible height the filler walks, and spans_of's end

# =====================================================================================
#  THE ANCHORED FIXTURES INSTALL THEIR OWN CHANNEL-0 WORLD ANCHOR (2026-09-19)
# =====================================================================================
# THE THREE REDS THIS CLOSES, and what was actually wrong. ID7 and ID8 sampled a buffer
# identical to the flat fixture ID1, and the whole matrix produced no span off the 8-pixel
# grid. Both were ONE cause: the anchored split never fired, because a split line is not a
# config field. It is `Effects_Screen_L[ch]`, re-latched every frame from
# `Effects_World_Y[ch] - Camera_Y`, and these fixtures set `anchor=0` in their config while
# leaving the ANCHOR BANK at whatever the live section had put there. On the shipping ROM the
# boot region leaves channel 0 at PATCH_ANCHOR_NONE ($7FFF), so L came out ~32623, past every
# band, and the overlay correctly did nothing. The engine was right; the fixture asked for a
# split with only half the state a split needs.
#
# SO THE FIXTURE INSTALLS THE OTHER HALF. THREE REASONS, AND THE THIRD IS MEASURED:
#
#  1. IT IS THE SAME CLASS OF REACH THIS FILE ALREADY MAKES. A fixture here already writes
#     `Debug_Scene_Freeze`, pins `Camera_Y`, and aims the LIVE `Parallax_Current_Config` at a
#     scratch buffer it filled itself. The overlay takes exactly two inputs -- the config and
#     the anchor -- and synthesizing one while inheriting the other from whatever section
#     happens to be loaded is not a principle, it is half a fixture. The thing a fixture must
#     not do is poke the RESPONSE, and `Hscroll_Buffer` is untouched.
#  2. THE SIBLING THAT SHARES `build()` ALREADY WRITES THIS BANK. `parallax_cost_probe`'s W20
#     moves `Effects_World_Y[ch]` to move the split, with a comment saying why the camera is
#     the wrong knob. (It PERTURBS by a delta rather than installing an absolute, which is why
#     W20's own split is stale on this ROM today: $7FFF + 16 is still off-screen. Stated here
#     because the precedent is "this bank is a fixture input", not "the sibling is correct".)
#  3. THE STATE IS SHIPPED CONTENT, and `shipped_precedent()` below MEASURES it on every run
#     rather than this comment asserting it. Measured 2026-09-19 on s4.debug.bin crc32
#     62238a15: OJZ act 1 region 5 (x 4096..5119, y 2048..4095) binds `OJZ_Preset_Sec5`, whose
#     `ep_patch_world_ys[0]` is 2272 -- a real world anchor on channel 0 -- and resolves its
#     parallax to `ParallaxConfig_OJZ_Underwater`, whose `anchor_ch` is 0. An anchored channel
#     0 with a config that consumes it is what the player walks into, not a state invented
#     here. If NO region pairs them any more, the check below says so and fails: a fixture
#     exercising a shape the game cannot reach is a different defect, not a green one.
#
# THE SPLIT LINE IS DERIVED, NOT TYPED. It must (a) be a multiple of 8 at the idle camera, so
# the cell-aligned fixtures stay cell-aligned and the RAGGED ones earn their raggedness from
# the camera alone -- which is this file's own stated mechanism -- and (b) not coincide with a
# band top of ANY anchored fixture, because a split exactly on a boundary produces a
# zero-length band and tests the boundary rather than the remainder. `split_line()` picks it
# off `band_tops()`; nothing here is a literal but the tie-break.
ANCHOR_CH = 0                    # the channel the anchored fixtures name in their config


# `split_line` MOVED to `parallax_cost_probe` on 2026-09-19 — `pcp.band_tops`, its only
# input, lives there, and both files need it now that the cost probe's anchored fixtures
# install a world anchor too. One derivation, in the module that owns the geometry.
split_line = pcp.split_line


def matrix(base: bytes, fg: int, bg: int) -> dict:
    """One fixture per fill PATH, plus the coverage fixtures.

    The paths are what the filler branches to per band: `.lp_flat`, `.band_fg_only`, `.lp_bg`
    and `.lp_both`. Every one is covered, including the ones this parcel did NOT touch -- an
    unchanged path that silently changed is exactly what an identity gate is for. (ID0 used
    to exercise `Parallax_Fill_PerCell`; that filler was deleted 2026-08-26 and a bare config
    now runs the per-line filler on `.lp_flat`, which ID0 still witnesses.)
    """
    return {
        "ID0": {"what": "no table, no deform — the bare config, per-line `.lp_flat` throughout",
                "cfg": build(base, bands=1)},
        "ID1": {"what": "per-line, all 224 lines flat (`.lp_flat`) — the vacuity reference",
                "cfg": build(base, bands=1, tab_fg=fg)},
        "ID2": {"what": "BG-only sampling, 224 lines, phase advancing (`.lp_bg`)",
                "cfg": build(base, bands=1, tab_bg=bg, dsb=2, speed_bg=3)},
        "ID3": {"what": "FG-only sampling, 224 lines, phase advancing (`.band_fg_only`)",
                "cfg": build(base, bands=1, tab_fg=fg, dsa=3, speed_fg=3)},
        "ID4": {"what": "BOTH channels sampling, different curves, phases advancing at "
                        "different rates (`.lp_both` — UNCHANGED path, so this is a control)",
                "cfg": build(base, bands=1, tab_fg=fg, tab_bg=bg, dsa=3, dsb=1,
                             speed_fg=5, speed_bg=2)},
        "ID5": {"what": "3 bands, only the lowest samples FG — flat and sampled bands mixed",
                "cfg": build(base, bands=3, tab_fg=fg, speed_fg=3,
                             shifts=[(NO_DEFORM, NO_DEFORM), (NO_DEFORM, NO_DEFORM),
                                     (3, NO_DEFORM)])},
        "ID6": {"what": "anchored overlay, 2 bands, FG+BG sampling below an arbitrary split",
                "cfg": build(base, bands=2, tab_fg=fg, tab_bg=bg, anchor=0, dsa=3, dsb=3,
                             speed_fg=3, speed_bg=3)},
        "ID7": {"what": "anchored, sampling turned ON BY the anchor (the shipped "
                        "underwater shape: ROM bands all 15, anchor_dsb = 2)",
                "cfg": build(base, bands=4, tab_bg=bg, anchor=0, dsa=NO_DEFORM, dsb=2,
                             speed_bg=1, shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
        # ID8/ID9 ARE THE RAGGED-SPAN WITNESSES — same shapes as ID7/ID6 but with the camera
        # off the 8-pixel grid, so the anchored split lands on a scanline that is not a cell
        # edge and the unrolled run has a real remainder to finish.
        "ID8": {"what": "ID7's shipped shape at a RAGGED camera (Y=147) — anchored split on "
                        "a non-cell scanline, so spans are not multiples of 8",
                "cam_y": CAM_Y_RAGGED,
                "cfg": build(base, bands=4, tab_bg=bg, anchor=0, dsa=NO_DEFORM, dsb=2,
                             speed_bg=1, shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
        "ID9": {"what": "FG+BG sampling at a RAGGED camera (Y=147) — ragged spans through "
                        "both the single-channel and the both-channel loop",
                "cam_y": CAM_Y_RAGGED,
                "cfg": build(base, bands=2, tab_fg=fg, tab_bg=bg, anchor=0, dsa=3, dsb=3,
                             speed_fg=3, speed_bg=3)},
    }


async def _one(b: BusClient, sym: dict[str, int], cfg: bytes, settle: int,
               cam_y: int, anchor_wy: int | None = None) -> dict:
    for attempt in range(4):     # `reset: timeout waiting for main-thread drain` is an
        try:                     # instrument flake under load — see parallax_cost_probe's note
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
    # Camera_Y is 16.16 with the whole pixels in the HIGH word (the walker reads it as
    # `move.l Camera_Y,d1 / swap d1`). Written AFTER the freeze so nothing drives it back.
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Camera_Y"]), "value": cam_y << 16, "width": 4})
    await b.call("emulator/run_frames", {"frames": 2})

    scratch = sym["Replay_Record_Buf"]
    await b.call("emulator/write_memory", {"addr": hex(scratch), "bytes": cfg.hex().upper()})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Transition_Frames"]), "value": 0, "width": 1})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Target_Config"]), "value": 0, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Current_Config"]), "value": scratch, "width": 4})
    await b.call("emulator/run_frames", {"frames": 3})

    # THE ANCHORED FIXTURES' SECOND INPUT. Written AFTER the config so the install order is
    # the same one a section crossing uses (Effects_InstallPreset seeds the bank and the
    # config together), and ABSOLUTE rather than a delta: the live bank holds
    # PATCH_ANCHOR_NONE for this channel on the shipping ROM, and $7FFF plus anything is
    # still $7FFF-ish, i.e. still off screen. See the banner above CAM_Y_IDLE.
    wy_addr = None
    if anchor_wy is not None:
        wy_addr = sym["Effects_World_Y"] + 2 * ANCHOR_CH
        await b.call("emulator/write_memory",
                     {"addr": hex(wy_addr), "value": anchor_wy & 0xFFFF, "width": 2})
        await b.call("emulator/run_frames", {"frames": 2})

    idx0 = await b.call("emulator/read_memory",
                        {"addr": hex(sym["Replay_Record_Idx"]), "len": 2})

    frames, tops_seen, phases = [], [], []
    for _ in range(FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        buf = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Hscroll_Buffer"]), "len": HSCROLL_BYTES})
        frames.append(buf["bytes"].upper())
        sh = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Shadow_Bands"]), "len": pcp.BE_SIZE * 6})
        # FOUR hex chars: `band_top_plane` is a u16 since P3 Task 7. A two-char read returns
        # the always-zero HIGH byte of every shadow top in 0..224 and this list silently
        # becomes [0,0,0,...].
        tops_seen.append([int(sh["bytes"][i * pcp.BE_SIZE * 2:i * pcp.BE_SIZE * 2 + 4], 16)
                          for i in range(6)])
        ph = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Deform_Phase_FG"]), "len": 2})
        pb = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Deform_Phase_BG"]), "len": 2})
        phases.append((int(ph["bytes"], 16), int(pb["bytes"], 16)))

    ptr = await b.call("emulator/read_memory",
                       {"addr": hex(sym["Parallax_Current_Config"]), "len": 4})
    back = await b.call("emulator/read_memory", {"addr": hex(scratch), "len": len(cfg)})
    idx1 = await b.call("emulator/read_memory",
                        {"addr": hex(sym["Replay_Record_Idx"]), "len": 2})
    cam = await b.call("emulator/read_memory", {"addr": hex(sym["Camera_Y"]), "len": 4})
    # READ THE ANCHOR BACK. "The preset re-installed its own anchors over the poke" and "the
    # anchor mover walked it" are both things that would silently change what was measured,
    # so this is a check rather than an assumption -- the same reason the config bytes and
    # the config pointer are read back two lines up.
    wy_back = None
    if wy_addr is not None:
        r = await b.call("emulator/read_memory", {"addr": hex(wy_addr), "len": 2})
        wy_back = int(r["bytes"], 16)
    return {"frames": frames, "tops": tops_seen, "phases": phases,
            "cam_y": int(cam["bytes"][:4], 16),
            "anchor_wy": wy_back,
            "ptr_ok": (int(ptr["bytes"][:8], 16) & 0xFFFFFF) == (scratch & 0xFFFFFF),
            "bytes_ok": back["bytes"].upper() == cfg.hex().upper(),
            "replay_idle": idx0["bytes"] == idx1["bytes"] == "0000"}


# =====================================================================================
#  DOES THE GAME REACH THE STATE THE ANCHORED FIXTURES BUILD?  MEASURED, NOT ASSERTED.
# =====================================================================================
# A fixture that installs state by hand owes an answer to "and does anything reach this?",
# and the honest place for that answer is a measurement that re-runs, not a paragraph that
# ages. This walks the LOADED act's own region table out of the ROM image and reports every
# region that pairs a parallax config consuming channel `ch` with a preset seeding a REAL
# world anchor on that same channel -- which is exactly the pair the anchored fixtures build.
#
# THE OFFSETS ARE READ OFF THE DECLARATIONS. Act/Region come from `region_table`, the one
# out-of-assembler reader for them (it cross-checks every `// $HH` against the accumulated
# field types). EffectsPreset's two fields are read from their own `@ $HH` annotations in
# engine/effects/preset.emp -- the annotation IS the declaration there, not a comment -- and
# PATCH_ANCHOR_NONE from engine/effects/raster_dsl.emp through parallax_cost_probe's
# `_emp_const`, which refuses rather than guessing. Nothing below is a typed offset.
PRESET_SRC = "engine/effects/preset.emp"
PATCH_ANCHOR_NONE = pcp._emp_const("engine/effects/raster_dsl.emp", "PATCH_ANCHOR_NONE")


def _preset_field(name: str) -> int:
    txt = (Path(__file__).resolve().parent.parent / PRESET_SRC).read_text()
    m = re.search(rf"^\s*{re.escape(name)}\s*:[^@\n]*@\s*\$([0-9A-Fa-f]+)", txt, re.M)
    if not m:
        raise SystemExit(f"parallax_hscroll_identity: `struct EffectsPreset` in {PRESET_SRC} "
                         f"no longer declares `{name}` with an `@ $HH` offset — the shipped "
                         f"precedent check reads that field and will not guess where it went")
    return int(m.group(1), 16)


def shipped_precedent(rom: bytes, act_base: int) -> tuple[list[dict], list[dict]]:
    """(regions pairing an anchor_ch with a real world anchor, all regions) for this act.

    A region "pairs" when its RESOLVED parallax config names channel `c` in `anchor_ch` and
    the preset bound to that region seeds `ep_patch_world_ys[c]` with something other than
    PATCH_ANCHOR_NONE. The resolve is the engine's three rungs -- Region.rg_parallax, then
    EffectsPreset.ep_parallax, then Act.act_parallax_config.
    """
    act_off, _ = region_table.struct_layout("Act")
    ep_par = _preset_field("ep_parallax")
    ep_wy = _preset_field("ep_patch_world_ys")
    o = act_off["act_parallax_config"]
    act_default = int.from_bytes(rom[act_base + o:act_base + o + 4], "big")
    rows, paired = [], []
    for r in region_table.read_regions(rom, act_base):
        ep = r["effects"]
        cfg = r["parallax"] or int.from_bytes(rom[ep + ep_par:ep + ep_par + 4], "big") \
            or act_default
        anchor_ch = rom[cfg + CFG_ANCHOR_CH]
        wys = [int.from_bytes(rom[ep + ep_wy + 2 * i:ep + ep_wy + 2 * i + 2], "big")
               for i in range(pcp.RASTER_MAX_PATCH)]
        row = {"index": r["index"], "rect": (r["x0"], r["x1"], r["y0"], r["y1"]),
               "preset": ep, "cfg": cfg, "anchor_ch": anchor_ch, "world_ys": wys}
        rows.append(row)
        if anchor_ch != ANCHOR_NONE and anchor_ch < len(wys) \
                and wys[anchor_ch] != PATCH_ANCHOR_NONE:
            paired.append(row)
    return paired, rows


def spans_of(tops: list[int], nbands: int) -> list[int]:
    """Screen-line spans of the shadow bands, in the order the filler walks them."""
    t = [x for x in tops[:nbands]]
    return [(t[i + 1] if i + 1 < len(t) else 224) - t[i] for i in range(len(t))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="")
    ap.add_argument("--ref", default="")
    args = ap.parse_args()

    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    sym = parse_lst(args.lst)
    missing = [s for s in SYMS if s not in sym]
    if missing:
        print(f"symbols missing: {', '.join(missing)}", file=sys.stderr)
        return 3

    # INSTALL THE RECORD STRIDE BEFORE THE FIRST `build()`. See the banner at the import.
    # Derived from THIS .lst's own symbol span, never typed: `set_stride` refuses if
    # `Parallax_Shadow_Scroll_A - Parallax_Shadow_Bands` is not a whole number of records.
    stride = pcp.set_stride(sym)

    rom = Path(args.rom).read_bytes()
    off = sym["ParallaxConfig_OJZ_Default"]
    FX = matrix(rom[off:off + CFG_SIZE], sym[CURVE_FG], sym[CURVE_BG])
    got: dict[str, list[dict]] = {k: [] for k in FX}

    # The split line every anchored fixture lands on at the idle camera, and the ONE world
    # anchor that produces it. One value for all four, because the RAGGED fixtures earn
    # their raggedness by moving the camera under a fixed world anchor -- moving the anchor
    # with the camera would hold L constant and there would be no ragged span anywhere.
    anchored_counts = sorted({fx["cfg"][CFG_BAND_COUNT] for fx in FX.values()
                              if fx["cfg"][CFG_ANCHOR_CH] != ANCHOR_NONE})
    split_l = split_line(anchored_counts)
    anchor_wy = CAM_Y_IDLE + split_l

    act_ptr: list[int] = []

    async def _sweep(sock: str) -> None:
        b = BusClient(socket_path=sock, client_id="pxident",
                      client_name="parallax_hscroll_identity")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        r = await b.call("emulator/read_memory",
                         {"addr": hex(sym["Current_Act_Ptr"]), "len": 4})
        act_ptr.append(int(r["bytes"][:8], 16) & 0xFFFFFF)
        for k, fx in FX.items():
            anchored = fx["cfg"][CFG_ANCHOR_CH] != ANCHOR_NONE
            got[k].append(await _one(b, sym, fx["cfg"], args.settle,
                                     fx.get("cam_y", CAM_Y_IDLE),
                                     anchor_wy=anchor_wy if anchored else None))
        await b.close()

    for _ in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))

    ref = json.loads(Path(args.ref).read_text()) if args.ref else None
    print(f"ROM {args.rom}   {FRAMES} frames/fixture   repeats {args.repeat}")
    print(f"response = Hscroll_Buffer, all {HSCROLL_BYTES} bytes, after each frame")
    print(f"anchored fixtures: channel {ANCHOR_CH} world anchor {anchor_wy} installed by this "
          f"fixture -> split line {split_l} at camera {CAM_Y_IDLE}, "
          f"{anchor_wy - CAM_Y_RAGGED} at camera {CAM_Y_RAGGED} "
          f"(band tops of the anchored counts {anchored_counts}: "
          f"{sorted({t for n in anchored_counts for t in pcp.band_tops(n)})})")

    # ---- the precedent, MEASURED, before anything is graded ----
    setup_bad = []
    if not act_ptr or not act_ptr[0]:
        setup_bad.append("PRECEDENT UNMEASURABLE: Current_Act_Ptr read back 0, so there is no "
                         "act whose regions could be walked — this run cannot say whether the "
                         "state these fixtures install is one the game reaches")
        paired, allrows = [], []
    else:
        paired, allrows = shipped_precedent(rom, act_ptr[0])
    if allrows:
        inv = {v: k for k, v in sym.items()}
        print(f"\nSHIPPED PRECEDENT — the act at ${act_ptr[0]:06X} has {len(allrows)} region(s); "
              f"{len(paired)} pair a consuming `anchor_ch` with a real world anchor on it "
              f"({sum(1 for r in paired if r['anchor_ch'] == ANCHOR_CH)} on the fixtures' own "
              f"channel {ANCHOR_CH}):")
        for r in paired:
            ys = ["NONE" if y == PATCH_ANCHOR_NONE else y for y in r["world_ys"]]
            print(f"  region {r['index']:2d} x{r['rect'][0]}..{r['rect'][1]} "
                  f"y{r['rect'][2]}..{r['rect'][3]}  "
                  f"{inv.get(r['preset'], hex(r['preset']))} -> "
                  f"{inv.get(r['cfg'], hex(r['cfg']))}  anchor_ch {r['anchor_ch']}  "
                  f"world_ys {ys}")
        # THE CHECK IS ON THE FIXTURE'S OWN CHANNEL, and that is the point rather than
        # pedantry. The original diagnosis of this file's three reds was that "the fixture
        # picks its anchor channel by NUMBER, and which channel carries a world anchor is a
        # property of the scene, which changed under it". That sentence describes a rot the
        # fixture could not feel. This is the same sentence made mechanical: the fixture
        # still picks channel 0 by number, and the run FAILS if the content stops pairing
        # that number, naming the channel the content moved to.
        on_ch = [r for r in paired if r["anchor_ch"] == ANCHOR_CH]
        if not on_ch:
            elsewhere = sorted({r["anchor_ch"] for r in paired})
            setup_bad.append(
                f"PRECEDENT: no region of the loaded act pairs a parallax config consuming "
                f"channel {ANCHOR_CH} with a preset seeding a real world anchor on it"
                + (f" — the content anchors channel(s) {elsewhere} instead, so ANCHOR_CH "
                   f"here is now the stale number"
                   if elsewhere else
                   ", and no channel is paired anywhere in this act at all")
                + ". The anchored fixtures below build a state the shipped content does not "
                  "reach, so what they certify is an engine path with no consumer — re-read "
                  "them before trusting a green, and do not silence this by deleting the "
                  "check")
    print()
    hdr = (f"{'FIX':4} {'camY':>4} {'bands':>5} {'spans (screen lines)':<30} {'ragged':>6}"
           f" {'wrapF':>6} {'digest':<12} {'vs ref':>8}")
    print(hdr)
    print("-" * len(hdr))

    out, bad, ragged_total, wrap_total = {}, list(setup_bad), 0, 0
    flat_digest = None
    for k, fx in FX.items():
        runs = got[k]
        nb = fx["cfg"][CFG_BAND_COUNT]
        anchored = fx["cfg"][CFG_ANCHOR_CH] != ANCHOR_NONE
        digests = [hashlib.sha256("".join(r["frames"]).encode()).hexdigest() for r in runs]
        stable = len(set(digests)) == 1
        checks = all(r["ptr_ok"] and r["bytes_ok"] and r["replay_idle"] for r in runs)
        r0 = runs[0]
        nshadow = nb + (1 if anchored else 0)
        sp = spans_of(r0["tops"][-1], nshadow)
        ragged = sum(1 for s in sp if s % 8 != 0 and s > 0)
        # a frame WRAPS if the sampled walk crosses a 256 boundary: index0 + 224 >= 256,
        # i.e. the phase's low byte is past 32. Read from the live phase, not assumed.
        wrapf = sum(1 for (pf, pb) in r0["phases"] if ((pf & 0xFF) + 224) > 256
                    or ((pb & 0xFF) + 224) > 256)
        ragged_total += ragged
        wrap_total += wrapf
        note = ""
        if not checks:
            note = "INSTALL!"
            bad.append(f"{k}: fixture did not install cleanly")
        # ---- THE ANCHORED FIXTURES' OWN TWO CHECKS ----
        # Neither of these existed while the split never fired, which is how [56,56,56,-8,64]
        # -- a NEGATIVE span, i.e. a slot holding the previous frame's leftover -- printed
        # every run without being a failure. A fixture that asks for a split and does not get
        # one tests the flat path under an anchored name, and that is worse than a red.
        if anchored:
            if r0.get("anchor_wy") != anchor_wy:
                note = "ANCHOR!"
                bad.append(f"{k}: the installed channel-{ANCHOR_CH} world anchor read back as "
                           f"{r0.get('anchor_wy')}, not the {anchor_wy} this fixture wrote — "
                           f"something re-seeded the bank under the sample (a preset install, "
                           f"or the anchor mover), so the split this fixture measured is not "
                           f"the one it asked for")
            # THE WHOLE REALIZED SHADOW VIEW, against an expectation derived two ways that
            # do not share the parser: the UNSPLIT tops are read back out of the config
            # bytes this fixture installed (and `bytes_ok` above has already confirmed the
            # emulator holds those bytes), and the SPLIT line is `anchor_wy - cam_y` with
            # BOTH terms read back off the machine. An overlay that wrote the split in the
            # wrong place, or did not write it, cannot produce this list.
            # ⚠ Stated narrowly: the unsplit half is a fixture-to-fixture identity (the
            # fixture authored those tops), so what this check is a WITNESS for is the
            # split's position and the insert, not the band layout.
            cfgb = fx["cfg"]
            want_l = anchor_wy - r0["cam_y"]
            want_tops = sorted([pcp.be_top(cfgb, i, CFG_SIZE) for i in range(nb)] + [want_l])
            got_tops = r0["tops"][-1][:nshadow]
            if got_tops != want_tops:
                note = "SPLIT!"
                bad.append(f"{k}: the anchored split did not land where the world anchor puts "
                           f"it — the shadow view reads {got_tops} and the config's own tops "
                           f"with Effects_World_Y[{ANCHOR_CH}] {anchor_wy} - Camera_Y "
                           f"{r0['cam_y']} = {want_l} inserted are {want_tops}. Either no "
                           f"split was written (a slot is the previous frame's leftover) or "
                           f"Raster_GetChannelBand clamped L into channel {ANCHOR_CH}'s "
                           f"authored band")
            if any(x <= 0 for x in sp):
                note = "SPANS!"
                bad.append(f"{k}: spans {sp} contain a non-positive entry, so the "
                           f"nshadow = bands + 1 reading of the shadow view is not what the "
                           f"engine wrote — a slot is being read that nothing filled")
        if not stable:
            note = "UNSTABLE"
            bad.append(f"{k}: not reproducible across {args.repeat} boots")
        cmp_s = "-"
        if ref is not None:
            want = ref.get(k, {}).get("digest")
            if want is None:
                cmp_s = "NO-REF"
                bad.append(f"{k}: absent from the reference")
            elif want == digests[0]:
                cmp_s = "match"
            else:
                cmp_s = "DIFFER"
                nf = next((i for i, f in enumerate(runs[0]["frames"])
                           if f != ref[k]["per_frame"][i]), None) \
                    if "per_frame" in ref.get(k, {}) else None
                bad.append(f"{k}: Hscroll_Buffer DIFFERS from the reference"
                           + (f" (first at frame {nf})" if nf is not None else ""))
        # VACUITY: a sampled fixture whose buffer equals the all-flat fixture's is a fixture
        # whose curve never deflected — it would match any fill, including one that dropped
        # the sampling entirely. ID1 IS the flat reference; ID0 is the other filler.
        if k == "ID1":
            flat_digest = digests[0]
        elif k != "ID0" and flat_digest is not None and digests[0] == flat_digest:
            note = "VACUOUS"
            bad.append(f"{k}: sampled buffer is identical to the flat fixture ID1 — the "
                       f"curve did not deflect, so this fixture tests nothing")
        print(f"{k:4} {r0['cam_y']:>4} {nshadow:>5} {str(sp):<30} {ragged:>6} {wrapf:>6}"
              f" {digests[0][:12]:<12} {cmp_s:>8}  {note}")
        out[k] = {"digest": digests[0], "what": fx["what"], "spans": sp, "cam_y": r0["cam_y"],
                  "ragged": ragged, "wrap_frames": wrapf, "checks_ok": checks,
                  "anchor_wy": r0.get("anchor_wy"),
                  "per_frame": runs[0]["frames"]}

    print(f"\nCOVERAGE WITNESSES — ragged spans {ragged_total}   wrapping frames {wrap_total}")
    if ragged_total == 0:
        bad.append("COVERAGE: no non-multiple-of-8 span in the whole matrix — the remainder "
                   "tail is untested and this gate cannot fail on it")
    if wrap_total == 0:
        bad.append("COVERAGE: no frame's sampled run crossed the 256-byte curve wrap — the "
                   "pointer reset is untested and this gate cannot fail on it")

    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1))
        print(f"\nwrote {args.out}")
    if bad:
        print("\nFAIL")
        for m in bad:
            print(f"  - {m}")
        return 1
    print("\nOK — every fixture's Hscroll_Buffer is byte-identical to the reference"
          if ref is not None else "\nOK — captured (no reference to compare against)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
