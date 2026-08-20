#!/usr/bin/env python3
"""engine_baseline_probe — the standing engine cost a scene budget is measured AGAINST.

WHY THIS EXISTS. Design §5's budget for every axis is `pool - engine_reservation`, and the
reservation is standing engine cost at a DEFINED camera state. "Idle" and "max-diagonal" are
not self-defining, and the effects-p3 baseline rows went camera-stale exactly because theirs
were not written down (R1 evidence §7.3, "NO VERDICT"). So the states here are declared as
code, driven through the ENGINE'S OWN camera path, and every run publishes a derived check
that says whether the state it claims to have measured is the state it actually got.

THE INSTRUMENT, AND THE COUNTER THAT IS NOT IT. `get_profiler_frames` returns an
`interrupts.hint` figure and it is NOT HBlank cost in this ROM: oracle buckets an interrupt by
comparing the handler's entry PC against 0x78, and Aeon's VBlank_Handler is a ROM address that
never matches, so BOTH handlers land in the `hint` bucket. Every row this tool prints is a
PER-ROUTINE row keyed by entry address. `interrupts.*` is printed only under --dump, labelled,
and used by nothing. See tools/raster_cost_probe.py's module note for the full derivation.

Addresses are matched on the LOW 24 BITS. Oracle prints a row's key as the raw 68000 PC, which
for anything reached through short-form addressing is sign-extended ($FFFFB452 where the
listing says $FFB452). Comparing printed strings does not agree; comparing 24 bits does.

HOW THE CAMERA STATES ARE REACHED — through Camera_Update, not around it.

    idle       boot, settle, and measure. The player stands where level init put it, the
               camera is stationary, streaming is quiescent. Nothing is poked at all, which
               makes this the most reproducible state available: it is what the ROM does.

    maxdiag    ONE poke: the leader's SST x_pos/y_pos are moved far down-right, and
               Camera_Update then steps the camera at its own per-frame ceiling
               (CAM_MAX_X_STEP = CAM_MAX_Y_STEP = 16 px) in BOTH axes for hundreds of frames.
               The engine's real follow path does the driving, so Camera_Update,
               EntityWindow_Scan, Tile_Cache_Fill and Section_UpdateColumns all run exactly as
               they do in play. No per-frame bus traffic is interleaved with the sample.

WHY NOT Debug_Scene_Freeze + a poked camera. That is the established pattern for a PINNED
scene (tools/scenes/README.md) and it is the right tool there. It is the wrong tool here: the
freeze skips Camera_Update AND EntityWindow_Scan, so a "main loop" total taken under it would
be missing two of the routines a reservation has to reserve for, and moving the camera by hand
each frame would also interleave bus writes with the profiled window.

THE DERIVED CHECK — this tool's `calls`. A max-diagonal claim is checkable, and the check is
per LOGIC TICK rather than per video frame, because measuring it is what found the reason:

    the camera advances by exactly CAM_MAX_STEP on each axis per LOGIC TICK, so
        ticks   = camera_dx / 16   (and dx MUST equal dy, or it is not diagonal)
        frames per tick = profiled video frames / ticks

AND THAT LAST RATIO IS NOT 1. Measured 2026-08-19: idle runs 1.00 video frames per tick, and
sustained max-diagonal runs ~1.9 — the main loop overruns one video frame, VInt_Lag services
the spare VBlanks, and the logic ticks at roughly 30 Hz. It is NOT the art soft-clamp:
Camera_Art_Hold reads 0 throughout and DEBUG's own Dbg_Cam_Clamp_Frames counter stays at 0 for
the whole run, both checked here. So every max-diagonal figure has two honest denominators and
this tool prints both: cycles per VIDEO FRAME (the 128000-cycle budget's denominator) and
cycles per LOGIC TICK (what one invocation of the work actually costs). Reporting only the
first would understate every routine by the lag factor.

Usage:
    python3 tools/engine_baseline_probe.py --rom s4.debug.bin --lst s4.debug.lst --repeat 5
    python3 tools/engine_baseline_probe.py --dump --state idle    # every routine row, once
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
# ONE listing parser and ONE cost model, imported rather than re-transcribed. The wire
# ENCODER in raster_cost_probe is pinned against raster_dsl.emp by tools/test_raster_wire_pin.py;
# reusing its cost terms here means the decoder below is the only new transcription in this
# file, and the self-test at the bottom is what pins that.
from raster_cost_probe import (            # noqa: E402
    parse_lst, op_cost_cycles, program_words, FIXTURES, spin_cyc,
)
from effects_budget_check import emp_constants, eval_int_expr  # noqa: E402


# ---- the routines a reservation is made of ---------------------------------
# The five the plan names, plus the two brackets every axis is a fraction of, plus the two
# the freeze WOULD have excluded (kept here precisely so nobody has to wonder what a frozen
# measurement would have left out).
ROUTINES = [
    # Task 3 — budget axis 4b. The trampoline row IS the per-frame HInt total; the row has no
    # symbol name attached, so it can only be reached by address (see routine_rows).
    "HBlank_Vector_Slot",
    "GameState_OJZScroll_Update",  # the MAIN LOOP bracket — one call per LOGIC TICK
    "VInt_Level",            # the VBlank bracket — Raster_VBlank runs INSIDE it
    "VInt_Lag",              # the spare VBlanks a lagging frame spends here; 0 == not lagging
    "VSync_Wait",            # the idle the frame has left; not a cost, the headroom
    "Parallax_Update",
    "Raster_VBlank",
    "Palette_Compose",
    "Enqueue_Dirty_Buffers",
    "BgAnim_Update",
    "Camera_Update",
    "EntityWindow_Scan",
    "Tile_Cache_Fill",
    "Section_UpdateColumns",
]

# Sst offsets (engine/objects/sst.emp) — both 16.16 Coord.
SST_X_POS = 0x02
SST_Y_POS = 0x06

# The maxdiag poke, in PIXELS ahead of the camera. Large enough that 30 profiled frames at
# 16 px/frame never close the gap (so the step never falls out of its cap) and small enough
# that the act's clamp ceiling is not reached inside the run. Both facts are CHECKED, not
# assumed: the px/frame readback below fails the row if either is wrong.
DIAG_AHEAD_X = 2000
DIAG_AHEAD_Y = 1400
CAM_MAX_STEP = 16        # engine/level/camera.emp CAM_MAX_X_STEP, constants.emp CAM_MAX_Y_STEP


# ---- Task 3: the per-frame HInt TOTAL, and the model it is checked against ----
# Design §5 axis 4 splits into (4a) per-fire spacing, which check_density already owns, and
# (4b) a per-frame HInt TOTAL. The toml's absolute HInt rows have never been measured because
# `interrupts.hint` conflates VBlank -- so the total here is the HBlank trampoline's OWN
# per-routine row, and the model it is compared against is a sum over the LIVE records read
# out of the running buffer rather than over the authored source.
#
# THE DECODER IS THE ONLY NEW TRANSCRIPTION IN THIS FILE, and it is the inverse of
# raster_cost_probe's encoder. It is pinned empirically and hard: `selftest_decoder()` runs the
# nine measured fixture programs (F0..F8) through encode -> decode -> cost-sum and requires
# every one to reproduce the total the hardware reported in Task 1, to the cycle. A decoder
# that mis-parsed an op, dropped a record or mis-costed a class cannot survive nine of those.

OPC_SET_REG, OPC_CRAM, OPC_PAL_REGION = 0, 2, 4
OPC_RUN_GRADIENT, OPC_RUN_RAMP, OPC_PAL_RESTORE = 6, 8, 10
ARM_PARK, OPS_END = 0x8AFF, 0xFFFF

# Read from the shipped .emp, never mirrored here — a second copy of a cost constant is the
# drift this whole parcel is about.
_EFFECTS = Path(__file__).resolve().parent.parent / "engine/effects"
# BOTH files, because the constants this tool needs are split across them by ownership:
# raster_dsl.emp owns the COST model (RASTER_FIRE_BASE_CYC, RASTER_PRIMING_GUARD_CYC) and
# raster.emp owns the RUNTIME shape (RASTER_BUF_SIZE). Merging their tables is what lets a
# name be read from wherever it actually lives instead of being mirrored here.
_CONSTS: dict[str, str] = {}
for _f in ("raster_dsl.emp", "raster.emp"):
    _CONSTS.update(emp_constants(str(_EFFECTS / _f)))


def dsl_const(name: str) -> int:
    return eval_int_expr(name, _CONSTS)


def decode_program(words: list[int]) -> list[dict]:
    """The live wire image -> records, each a list of op dicts raster_cost_probe can price.

    A VSRAM op EMITS OP_CRAM and runs the same `.cram_loop` at the same dispatch rung, so it
    decodes to kind "cram": the two are the same COST even though they are different writes.
    That is not an approximation, it is fixture F7 == F2, measured.
    """
    recs: list[dict] = []
    i = 1                                     # words[0] is the header's pal_dirty_mask
    while i + 1 < len(words):
        arm, cnt = words[i], words[i + 1]
        i += 2
        if cnt == OPS_END:
            break
        ops: list[dict] = []
        for _ in range(cnt):
            opc = words[i]
            if opc == OPC_SET_REG:
                ops.append({"k": "reg", "w": words[i + 1], "spin": 0})
                i += 2
            elif opc == OPC_CRAM:
                n = words[i + 4] + 1
                ops.append({"k": "cram", "v": [0] * n, "spin": words[i + 3]})
                i += 5 + n
            elif opc in (OPC_PAL_REGION, OPC_PAL_RESTORE):
                k = "region" if opc == OPC_PAL_REGION else "restore"
                ops.append({"k": k, "n": words[i + 4] + 1, "spin": words[i + 3]})
                i += 6
            else:
                # RAISE rather than skip. An op this decoder cannot price would otherwise
                # vanish from the model sum and read as "the model under-predicts", which is
                # the exact ambiguity Task 3 step 2 says to investigate before recording.
                raise ValueError(f"decode_program: unpriced opcode {opc} at word {i}"
                                 f" (dense OP_RUN_GRADIENT/OP_RUN_RAMP are not a per-fire cost"
                                 f" — they are RASTER_DENSE_LINE_GRAD_CYC per LINE)")
        recs.append({"arm": arm, "ops": ops})
    return recs


def program_model_cycles(words: list[int]) -> tuple[int, list[int]]:
    """Model cycles for one frame of this program, and the per-record breakdown.

    A record with ops costs RASTER_FIRE_BASE_CYC plus each op's own cost at the spin THE
    PROGRAM CARRIES (substrate item 1a moved the spin into the wire, so the live spin is data,
    not something to re-solve). A record with NO ops is a priming record, and it alone pays
    the frame-rewind interlock: base - 16 + RASTER_PRIMING_GUARD_CYC. The -16 is what a record
    WITH ops pays over a no-op one; both terms are derived in RASTER_FIRE_BASE_CYC's own note
    and both are read from the .emp above.
    """
    base = dsl_const("RASTER_FIRE_BASE_CYC")
    guard = dsl_const("RASTER_PRIMING_GUARD_CYC")
    noop = base - 16 + guard
    per = []
    for r in decode_program(words):
        if not r["ops"]:
            per.append(noop)
        else:
            per.append(base + sum(op_cost_cycles(o, o["spin"]) for o in r["ops"]))
    return sum(per), per


def selftest_decoder() -> list[str]:
    """Nine measured fixtures, encode -> decode -> cost. Every total must match the hardware.

    These are Task 1's rows, re-measured on this very ROM at spread 0 over 3 boots, so they are
    not a copied expectation: they are what the HBlank trampoline reported. A `0` here would
    mean the decoder is not being checked at all, which is why the count is asserted too.
    """
    measured = {"F0": 588, "F1": 2508, "F2": 4332, "F3": 3818, "F4": 4584,
                "F5": 3172, "F6": 3340, "F7": 4332, "F8": 4632}
    fails = []
    for name, want in measured.items():
        got, _ = program_model_cycles(program_words(FIXTURES[name]["fires"]))
        if got != want:
            fails.append(f"{name}: decoder+model {got}, hardware {want}")
    if len(measured) != 9:
        fails.append(f"self-test degenerated to {len(measured)} fixtures")
    return fails


# ---- Task 5: the max-contiguous-DMA-stall AWARENESS row --------------------
# READ THIS BEFORE TRUSTING ANY NUMBER BELOW. The figure design §5 asks for is
# STRUCTURALLY INVISIBLE to this instrument. Oracle's 68000 core adds only `cyclesExecuted` to
# `_currentCycle` (M68000.cpp:1029-1031) while bus/VDP/DMA stall accumulates in
# `additionalTime` and lands in `_currentTime`; the profiler ring stamps `_currentCycle`
# (M68000.h:95). So stall time reaches the wall clock and NEVER reaches a cycle row. Any stall
# figure derived from a cycle row here would be an undercount or a zero regardless of what the
# hardware actually does.
#
# WHAT IS DONE INSTEAD, and it is a DERIVATION, not a measurement of a stall. The 68000 bus is
# held for the whole of a VDP DMA from 68K memory, so the longest contiguous hold in a frame is
# the longest SINGLE DMA the queue carries. That length IS readable: it is `SizeH`/`SizeL` in
# each DMAEntry, in words, and the queue is scanned at the end of active display, after the
# main loop has finished enqueueing and before VBlank drains it.
#
# WHAT THIS IS BLIND TO, stated so the row is not over-read: refresh stalls, Z80 bus contention,
# VDP FIFO stalls on ordinary (non-DMA) port writes, and any DMA the engine issues outside the
# queue. It bounds ONE contributor. It is an awareness row and design §5 says explicitly that
# this phase does not gate on it.
DMA_ENTRY_SIZE = 14                # sizeof(DMAEntry), engine/structs.emp
# H40 VBlank VRAM DMA rate, the standard figure: 205 bytes per scanline, and a scanline is
# 3420 mclk / 7 = 488.57 68000 cycles. Both are documented constants of the hardware, not
# measurements of this ROM -- which is exactly why the row below is labelled derived.
DMA_BYTES_PER_LINE = 205
SCANLINE_CYC = 3420 / 7


def dma_stall_cycles(words: int) -> float:
    return (words * 2 / DMA_BYTES_PER_LINE) * SCANLINE_CYC


def rd_long(b_bytes: str) -> int:
    return int(b_bytes[:8], 16)


async def _read_long(b: BusClient, addr: int) -> int:
    r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": 4})
    return int(r["bytes"][:8], 16)


async def _read_word(b: BusClient, addr: int) -> int:
    r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": 2})
    return int(r["bytes"][:4], 16)


async def _read_byte(b: BusClient, addr: int) -> int:
    # Camera_Art_Hold sits at an ODD address, so this is a byte read and not a word read
    # with a shift — the word form would straddle and read the wrong cell's high half.
    r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": 1})
    return int(r["bytes"][:2], 16)


async def _scan_dma(b: BusClient, sym: dict[str, int], line: int = 220) -> dict:
    """The DMA queue at end-of-active-display: every entry's length, and the largest.

    Scanned at scanline `line` (default 220, inside active display and past every main-loop
    enqueue) rather than at a frame boundary, where VBlank has already drained it and the
    answer would be an empty queue reported as "no stall".
    """
    await b.call("emulator/run_to_scanline", {"line": line})
    lo, hi = sym["DMA_Queue"] & 0xFFFFFF, sym["DMA_Queue_End"] & 0xFFFFFF
    d = await b.call("emulator/read_memory", {"addr": hex(lo), "len": hi - lo})
    raw = d["bytes"]
    slots = []
    for off in range(0, hi - lo, DMA_ENTRY_SIZE):
        e = raw[off * 2:(off + DMA_ENTRY_SIZE) * 2]
        if len(e) < DMA_ENTRY_SIZE * 2:
            break
        words = (int(e[2:4], 16) << 8) | int(e[6:8], 16)     # SizeH @+1, SizeL @+3
        cmd = int(e[20:28], 16)
        if words:
            slots.append({"slot": off // DMA_ENTRY_SIZE, "words": words,
                          "bytes": words * 2, "cmd": f"{cmd:08X}"})
    used = [await _read_word(b, sym[s]) for s in
            ("DMA_Critical_Slot", "DMA_Important_Slot", "DMA_Deferrable_Slot")]
    biggest = max((s["words"] for s in slots), default=0)
    return {"scanline": line, "entries": slots, "slot_cursors": used,
            "max_words": biggest, "max_bytes": biggest * 2,
            "max_stall_cycles_derived": round(dma_stall_cycles(biggest), 1),
            "total_words": sum(s["words"] for s in slots)}


async def _read_program(b: BusClient, sym: dict[str, int]) -> dict:
    """The LIVE raster program, from the buffer the engine is currently running.

    Read through Raster_Active_Buf and never from a fixed buffer address: Raster_BuildSchedule
    re-records into the INACTIVE buffer and swaps every frame, so a fixed read samples the
    stale one on half of all frames and looks stable while measuring nothing (the same trap
    tools/scenes/README.md documents for the gate scenes). The pointer is masked to 24 bits —
    it is stored sign-extended ($FFFF89A2 for $FF89A2) and the bus rejects the raw form.
    """
    act = (await _read_long(b, sym["Raster_Active_Buf"])) & 0xFFFFFF
    prog = (await _read_long(b, sym["Raster_Program"])) & 0xFFFFFF
    size = dsl_const("RASTER_BUF_SIZE")
    d = await b.call("emulator/read_memory", {"addr": hex(act), "len": size})
    words = [int(d["bytes"][i:i + 4], 16) for i in range(0, size * 2, 4)]
    return {"active_buf": act, "program": prog, "words": words}


async def _one(b: BusClient, sym: dict[str, int], state: str,
               settle: int, lead: int, sample: int) -> dict:
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": settle})

    note = {}
    if state == "maxdiag":
        # Camera_Target is a SHORT pointer to the leader's Sst (movea.w in Camera_Update).
        tgt = await _read_word(b, sym["Camera_Target"])
        leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
        cam_x = await _read_long(b, sym["Camera_X"]) >> 16
        cam_y = await _read_long(b, sym["Camera_Y"]) >> 16
        # 16.16 Coord: pixels in the high word.
        await b.call("emulator/write_memory",
                     {"addr": hex(leader + SST_X_POS),
                      "value": (cam_x + DIAG_AHEAD_X) << 16, "width": 4})
        await b.call("emulator/write_memory",
                     {"addr": hex(leader + SST_Y_POS),
                      "value": (cam_y + DIAG_AHEAD_Y) << 16, "width": 4})
        note["leader"] = hex(leader)
        # Let the follow reach its steady per-frame ceiling before the profiler opens.
        await b.call("emulator/run_frames", {"frames": lead})
    elif state != "idle":
        raise ValueError(f"unknown state {state}")

    cam_x0 = await _read_long(b, sym["Camera_X"])
    cam_y0 = await _read_long(b, sym["Camera_Y"])
    art_hold0 = await _read_byte(b, sym["Camera_Art_Hold"])
    # THE TICK-RATE INSTRUMENT, and it is the engine's own. Frame_Counter counts VBlanks;
    # Logic_Tick counts game-loop iterations and is documented in engine/ram.emp as
    # "lag-immune, unlike Frame_Counter". Their ratio over the sample IS frames-per-tick, for
    # BOTH states, with no dependence on the camera moving. Lag_Frame_Count is the engine's
    # own count of lag frames — a third witness to the same fact.
    fc0 = await _read_word(b, sym["Frame_Counter"])
    lt0 = await _read_long(b, sym["Logic_Tick"])
    lag0 = await _read_long(b, sym["Lag_Frame_Count"])
    prog0 = await _read_program(b, sym)

    # THE SLEEPS ARE LOAD-BEARING (raster_cost_probe's note): set_profiler only flips a flag;
    # the GUI's MAIN loop is what starts the CPU recording and what drains the event ring into
    # frame snapshots. Without a tick either side the sample is empty or truncated.
    await b.call("emulator/set_profiler", {"enabled": True})
    await asyncio.sleep(0.4)
    await b.call("emulator/run_frames", {"frames": sample})
    await asyncio.sleep(0.4)
    st = await b.call("emulator/get_profiler", {})
    # `frames: sample`, NOT sample - 1. The counters below bracket exactly the `sample` frames
    # run_frames just executed, so asking the profiler for the same `sample` makes the cycle
    # window and the tick window THE SAME WINDOW — which is what makes cycles-per-logic-tick an
    # exact conversion rather than one carrying a one-frame denominator error (at idle that
    # error was 3%, and it was there because 30 frames of cycles were being divided by a
    # 31-frame tick ratio). Verified 2026-08-19: frames_recorded == sample, and
    # get_profiler_frames answers frame_count == sample. tools/raster_cost_probe.py asks for
    # sample - 1 and is deliberately left alone: it converts nothing, so the extra frame buys it
    # nothing, and it is the pinned instrument behind Task 1's parity row.
    prof = await b.call("emulator/get_profiler_frames", {"frames": sample, "top": 300})
    prof["frames_recorded"] = st.get("frames_recorded")
    await b.call("emulator/set_profiler", {"enabled": False})

    cam_x1 = await _read_long(b, sym["Camera_X"])
    cam_y1 = await _read_long(b, sym["Camera_Y"])
    art_hold1 = await _read_byte(b, sym["Camera_Art_Hold"])
    # DEBUG's own counter for frames the art soft-clamp held an axis (Camera_Update). Read so
    # a degraded max-diagonal row can never be blamed on the clamp without evidence -- it was
    # the first hypothesis for the sub-16 px/frame reading and this is what refuted it.
    clamp = await _read_word(b, sym["Dbg_Cam_Clamp_Frames"]) \
        if "Dbg_Cam_Clamp_Frames" in sym else -1

    fc1 = await _read_word(b, sym["Frame_Counter"])
    lt1 = await _read_long(b, sym["Logic_Tick"])
    lag1 = await _read_long(b, sym["Lag_Frame_Count"])
    prog1 = await _read_program(b, sym)
    # Task 5's awareness scan. AFTER the profiled window, so it cannot perturb it: run_to_scanline
    # leaves the machine mid-frame, which is the whole point and also why it goes last.
    dma = await _scan_dma(b, sym)

    dx = (cam_x1 - cam_x0) / 65536.0
    dy = (cam_y1 - cam_y0) / 65536.0
    d_frames = (fc1 - fc0) & 0xFFFF
    d_ticks = lt1 - lt0
    # The camera derivation, kept as an INDEPENDENT second witness rather than as the primary:
    # at max-diagonal the camera advances CAM_MAX_STEP per logic tick, so dx/16 must equal the
    # engine's own Logic_Tick delta. Two instruments agreeing is the check; either alone is a
    # claim. It says nothing at idle (dx is 0 there), which is exactly why it is not primary.
    cam_ticks = dx / CAM_MAX_STEP
    return {
        "prof": prof,
        "cam": {"x0": cam_x0 >> 16, "y0": cam_y0 >> 16, "x1": cam_x1 >> 16, "y1": cam_y1 >> 16,
                "dx": dx, "dy": dy,
                "dx_per_frame": dx / d_frames if d_frames else 0.0,
                "dy_per_frame": dy / d_frames if d_frames else 0.0,
                "cam_derived_ticks": cam_ticks},
        "tick": {"frames": d_frames, "ticks": d_ticks, "lag_frames": lag1 - lag0,
                 "frames_per_tick": (d_frames / d_ticks) if d_ticks else float("nan"),
                 "cam_agrees": (dx == 0) or abs(cam_ticks - d_ticks) < 0.02},
        "art_hold": [art_hold0, art_hold1],
        "clamp_frames": clamp,
        "dma": dma,
        "prog": {"start": prog0, "end": prog1,
                 # A program that CHANGED mid-sample (a section crossing installing a new
                 # preset) makes the measured total an average of two programs and the model
                 # sum a snapshot of one. Recorded, so the comparison is never made blind.
                 "stable": prog0["words"] == prog1["words"]},
        **note,
    }


def routine_rows(prof: dict, sym: dict[str, int], names: list[str]) -> dict[str, dict]:
    """Per-routine rows keyed by ENTRY ADDRESS, low 24 bits. Never interrupts.hint."""
    by_addr: dict[int, dict] = {}
    for r in prof.get("routines", []):
        try:
            a = int(str(r.get("addr", "$0")).lstrip("$"), 16) & 0xFFFFFF
        except ValueError:
            continue
        by_addr[a] = r
    out = {}
    for n in names:
        if n not in sym:
            continue
        out[n] = by_addr.get(sym[n] & 0xFFFFFF)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=180, help="frames before the state is set")
    ap.add_argument("--lead", type=int, default=24,
                    help="maxdiag only: frames of motion before the profiler opens")
    ap.add_argument("--sample", type=int, default=31, help="frames profiled per state")
    ap.add_argument("--repeat", type=int, default=1, help="independent boots per state")
    ap.add_argument("--state", default="idle,maxdiag")
    ap.add_argument("--dump", action="store_true",
                    help="print every profiler row for the first state and stop")
    ap.add_argument("--out", default="", help="write raw results JSON here")
    args = ap.parse_args()

    # ABSOLUTE, always: headless_emulator launches oracle_gui with `env -C <oracle repo>`, so a
    # relative ROM path resolves against the EMULATOR's cwd and silently loads nothing.
    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    if not Path(args.rom).is_file():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 3

    sym = parse_lst(args.lst)
    need = ["Camera_X", "Camera_Y", "Camera_Target", "Camera_Art_Hold",
            "Frame_Counter", "Logic_Tick", "Lag_Frame_Count",
            "DMA_Queue", "DMA_Queue_End", "DMA_Critical_Slot", "DMA_Important_Slot",
            "DMA_Deferrable_Slot"]
    missing = [s for s in need if s not in sym]
    if missing:
        print(f"symbols missing from {args.lst}: {', '.join(missing)}", file=sys.stderr)
        return 3

    states = [s for s in args.state.split(",") if s]
    results: dict[str, list[dict]] = {s: [] for s in states}

    async def _sweep(sock: str) -> None:
        b = BusClient(socket_path=sock, client_id="ebprobe",
                      client_name="engine_baseline_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for s in states:
            r = await _one(b, sym, s, args.settle, args.lead, args.sample)
            if args.dump:
                print(json.dumps(r["prof"], indent=2))
                print(json.dumps({"cam": r["cam"], "art_hold": r["art_hold"]}, indent=2))
                await b.close()
                return
            results[s].append(r)
        await b.close()

    for _ in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))
        if args.dump:
            return 0

    print(f"ROM {args.rom}   sample {args.sample} frames   repeats {args.repeat}")
    st = selftest_decoder()
    print("decoder self-test (9 measured fixtures, encode -> decode -> cost): "
          + ("PASS" if not st else "FAIL " + "; ".join(st)))
    if st:
        return 4
    print("per-routine rows, matched on the low 24 bits of the entry address.")
    print("interrupts.hint is HBlank + VBlank in this ROM and is NEVER read here.\n")

    table: dict[str, dict] = {}
    for s in states:
        runs = results[s]
        c = runs[0]["cam"]
        cams = [r["cam"] for r in runs]
        ticks = [r["tick"] for r in runs]
        fpt = ticks[0]["frames_per_tick"]
        print(f"== state {s}   camera ({c['x0']},{c['y0']}) -> ({c['x1']},{c['y1']})"
              f"   {c['dx_per_frame']:.2f},{c['dy_per_frame']:.2f} px/video-frame"
              f"   Camera_Art_Hold {runs[0]['art_hold']}  Dbg_Cam_Clamp_Frames "
              f"{runs[0]['clamp_frames']}")
        # The window guard. cycles-per-logic-tick multiplies a per-video-frame average by a
        # frames/ticks ratio, so the two windows have to be the same window. If they are not,
        # the conversion silently carries a denominator error rather than failing.
        fcnt = [r["prof"].get("frame_count") for r in runs]
        if any(f != ticks[0]["frames"] for f in fcnt) or \
                any(x["frames"] != ticks[0]["frames"] for x in ticks):
            print(f"   !! WINDOW MISMATCH: profiler frame_count {fcnt} vs Frame_Counter delta"
                  f" {[x['frames'] for x in ticks]} — cyc/logic-tick is NOT exact")
        print(f"   tick rate (Frame_Counter / Logic_Tick, the ENGINE's own counters):"
              f" {ticks[0]['frames']} video frames / {ticks[0]['ticks']} logic ticks"
              f" = {fpt:.3f} frames per tick;"
              f" Lag_Frame_Count +{ticks[0]['lag_frames']}")
        spread_fpt = (max(x["frames_per_tick"] for x in ticks)
                      - min(x["frames_per_tick"] for x in ticks))
        print(f"   frames/tick across {args.repeat} boots: "
              f"{[round(x['frames_per_tick'], 3) for x in ticks]}  spread {spread_fpt:.3f}")
        if s == "maxdiag":
            # Diagonal means BOTH axes at the per-tick ceiling. dx == dy is the diagonal half;
            # dx/16 agreeing with the engine's own Logic_Tick delta is the at-the-ceiling half
            # AND the two-instrument cross-check. The lag RATIO that falls out is the finding,
            # not a failure -- see the module note.
            diag = all(abs(x["dx"] - x["dy"]) < 0.01 for x in cams)
            agree = all(x["cam_agrees"] for x in ticks)
            print(f"   derived check: dx == dy {'OK' if diag else '!! NOT DIAGONAL'};"
                  f" camera-derived ticks ({c['cam_derived_ticks']:.2f}) vs Logic_Tick"
                  f" ({ticks[0]['ticks']}) {'AGREE' if agree else '!! DISAGREE'}")
        hdr = (f"   {'ROUTINE':24} {'calls':>6} {'cyc/video-frame':>16} {'spread':>7}"
               f" {'%frame':>7} {'cyc/logic-tick':>15}")
        print(hdr)
        print("   " + "-" * (len(hdr) - 3))
        table[s] = {"cam": c, "cams": cams, "tick": ticks[0], "ticks": ticks,
                    "art_hold": runs[0]["art_hold"],
                    "clamp_frames": runs[0]["clamp_frames"],
                    "dma": runs[0]["dma"],
                    "dma_all_boots": [r["dma"]["max_words"] for r in runs],
                    "prog_words": [f"{w:04X}" for w in runs[0]["prog"]["start"]["words"]],
                    "prog_stable": all(r["prog"]["stable"] for r in runs),
                    "routines": {}}
        for name in ROUTINES:
            rows = [routine_rows(r["prof"], sym, [name])[name] for r in runs]
            if not rows or any(x is None for x in rows):
                print(f"   {name:24} {'--':>6} {'ABSENT FROM TOP-300':>16}")
                table[s]["routines"][name] = None
                continue
            cyc = [int(x["cycles"]) for x in rows]
            cal = [int(x["calls"]) for x in rows]
            # HInt has NO per-logic-tick figure and printing one would be a wrong number.
            # The raster schedule is armed in VBlank and the handler fires on every VIDEO
            # frame whether or not the main loop ticked, so its cost does not scale with the
            # lag factor — multiplying it by frames-per-tick would invent 2x the HBlank work.
            display_time = name == "HBlank_Vector_Slot"
            per_tick = float("nan") if display_time else (cyc[0] * fpt)
            table[s]["routines"][name] = {
                "cycles": cyc, "calls": cal,
                "cycles_per_logic_tick": None if display_time else per_tick}
            shown = "n/a (display)" if display_time else f"{per_tick:.0f}"
            print(f"   {name:24} {cal[0]:>6} {cyc[0]:>16} {max(cyc)-min(cyc):>7}"
                  f" {100.0*cyc[0]/128000:>6.1f}% {shown:>15}")

        # ---- Task 3: the per-frame HInt total, measured vs the model over LIVE records ----
        # HInt is a DISPLAY-time cost: the schedule is armed in VBlank and the handler fires
        # every video frame whether or not the main loop ticked. So the denominator here is the
        # VIDEO frame, deliberately, and there is no per-logic-tick column.
        p0 = runs[0]["prog"]
        stable = all(r["prog"]["stable"] for r in runs)
        same = all(r["prog"]["start"]["words"] == p0["start"]["words"] for r in runs)
        model, per_rec = program_model_cycles(p0["start"]["words"])
        hb = table[s]["routines"].get("HBlank_Vector_Slot")
        print(f"   -- axis 4b, the per-frame HInt TOTAL on shipped content --")
        print(f"      live program @ {p0['start']['active_buf']:06X}"
              f"  (Raster_Program {p0['start']['program']:06X})"
              f"  {'stable across the sample' if stable else '!! CHANGED MID-SAMPLE'}"
              f"  {'same across boots' if same else '!! DIFFERS ACROSS BOOTS'}")
        print(f"      records: {len(per_rec)}  per-record model {per_rec}")
        if hb:
            m = hb["cycles"][0]
            print(f"      measured {m} cyc/frame over {hb['calls'][0]} fires"
                  f"   model {model}   gap {m - model}"
                  f"   {'EXACT' if m == model else '<-- INVESTIGATE before recording'}")
            if hb["calls"][0] != len(per_rec):
                print(f"      !! fires {hb['calls'][0]} but {len(per_rec)} live records —"
                      f" dropped fires or an unwalked record")
        else:
            print("      !! HBlank trampoline row ABSENT — no HInt total measured")

        # ---- Task 5: the DMA awareness scan. NOT a measured stall — see the module note.
        dm = runs[0]["dma"]
        allb = [r["dma"]["max_words"] for r in runs]
        print(f"   -- axis: max contiguous DMA, DERIVED (the clock cannot measure a stall) --")
        print(f"      queue at scanline {dm['scanline']}: {len(dm['entries'])} live entries,"
              f" {dm['total_words']} words total; slot cursors {dm['slot_cursors']}")
        print(f"      largest single transfer {dm['max_words']} words = {dm['max_bytes']} B"
              f"   -> {dm['max_stall_cycles_derived']} cyc of bus hold at 205 B/line"
              f"   (max_words across {len(allb)} boots: {allb})")
        for e in dm["entries"]:
            print(f"        slot {e['slot']:>2}  {e['words']:>5} words  {e['bytes']:>6} B"
                  f"  cmd {e['cmd']}")
        print()

    if args.out:
        Path(args.out).write_text(json.dumps(table, indent=2) + "\n")
        print(f"raw: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
