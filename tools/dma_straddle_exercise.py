#!/usr/bin/env python3
"""dma_straddle_exercise — READ the four DEBUG straddle cells across long, varied,
GROUNDED play. A measurement driver, not a gate and not a fix.

WHY THIS EXISTS. `engine/ram.emp:1424-1476` documents four DEBUG cells built for the d-47
booking "DMA SPLIT-REJECT NEEDS TWO FREE IMPORTANT SLOTS, AND NOTHING COUNTS PER-FRAME
STRADDLES". `ram.emp` states in its own words that `DPLC_ENTRY_RESERVE = 2` was sized from
total art VOLUME, which "bounds how many straddling entries EXIST IN THE ROM and says
nothing about how many can want slots in ONE FRAME ... NOTHING measured it. These four
cells are that measurement." As of this script they had never been read against a live
machine across representative play.

THE QUESTION (docs/witness/f7-sprite-jumble-diagnosis-2026-09-05.md, after its own
correction): the player's DPLC peaks at 10 Important entries, the reserve holds 2 free,
DMA_IMPORTANT_SLOTS is 12. A drop -- which leaves `prev_frame` stale and draws the sprite
against tiles that never loaded, i.e. the owner's jumble -- requires non-player Important
consumers to want MORE THAN 2 slots in one frame. These cells count exactly that.

THE READING RULE, which is the whole reason this needs care and is quoted from ram.emp:

    Dbg_DMA_Straddle_All   free-running, EVERY queue. The positive control. A zero in the
                           Important cells means "Important never straddled" only if this
                           one is non-zero; otherwise it means "nothing straddled at all",
                           which is also what a broken instrument reads like.

So this script REFUSES to report a verdict unless the control both is non-zero AND MOVED
during the campaign. A stationary control is exit 2 (could-not-measure), never a green zero.

AND THE SECOND REASON: the prior attempt (RIGHT held 600 frames) ended at y5587 -- the
player had run off the built ground in the first seconds and spent the window in FREE FALL,
which streams nothing and animates almost nothing. So this script measures its own
groundedness at every poll, recovers by warping when the player falls out of the world, and
prints the grounded fraction beside every number. A run whose grounded fraction is low is
the prior attempt's defect wearing a longer frame count.

WHAT IS POLLED (six cells, four subject + two adjacent):

    Dbg_DMA_Straddle_All    $FFE912  free-running, all queues -- THE POSITIVE CONTROL
    Dbg_DMA_Straddle_Frame  $FFE914  this VBlank window's straddling IMPORTANT enqueues
                                     (folded and cleared every VInt_Level, so a poll sees
                                     only the current window -- Peak is what accumulates)
    Dbg_DMA_Straddle_Peak   $FFE916  high-water mark of the above -- THE BOOKING'S NUMBER
    DMA_Split_Reject_Count  $FFE918  transfers dropped whole by `.split_reject`
                                     -- "any non-zero value here is the defect, observed
                                     directly" (ram.emp)
    DMA_Overflow_Count      $FFF8F78 ADJACENT, not the subject: enqueues dropped by `.full`
                                     (an ordinary full queue). Included because the DPLC
                                     starvation path in the F7 diagnosis is carry-set from
                                     EITHER `.full` OR `.split_reject`, and measuring only
                                     one of the two drop paths would answer a narrower
                                     question than the one asked. Split out of each other
                                     when the straddle instrument landed (dma_queue.emp:170).
    Dbg_DMA_Enq_Capped      $FFF8F7A ADJACENT: enqueues rejected by DMA_ENQ_BYTE_CAP, the
                                     third drop path, "0 in normal play" per ram.emp:720.

Plus, per poll: player x/y, the in-air bit (ST_IN_AIR, engine/system/constants.emp:125),
and mapping_frame -- so the report can say which animation frames the campaign actually
reached, and in particular whether the walk/run tilt block $01-$30 (the owner's "rotated
slightly" frames, player_common.emp:224-244) was exercised at all.

THE THING THAT MAKES OR BREAKS THIS RUN, measured here on 2026-09-05 and not documented
anywhere before: **the canonical DEBUG shape boots ALREADY IN DEBUG FLY.**
GameState_OJZScroll_Init arms CHEAT_DEBUG_FLY *and* engages free flight, so out of the box
Player_1 is a camera puck -- moved by Player_DebugMove at a flat ~15.6 px/frame with
x_vel/y_vel both ZERO, status pinned at $08, and **mapping_frame pinned at $00 with
prev_frame $FF, i.e. the player never animates**. Perform_DPLC's `mapping_frame ==
prev_frame` early-out then fires every single frame and the player enqueues NOTHING. A
campaign driven from boot without leaving fly measures a machine in which the subject
system is switched off, and its zeros mean nothing whatsoever. One B press (edge-triggered)
hands the player to real physics; `leave_fly_and_prove_physics` presses it and then PROVES
it took, by requiring mapping_frame off $00 and prev_frame off $FF. That assertion is not
decoration -- it is the difference between this run and a longer version of the last one.
(This also means tools/canopy_gap_exercise.py's phases 1-3 and 5-6, which never press B,
drove a NON-ANIMATING player. Fine for its own subject, the canopy shadow; noted here
because the next person to copy that harness for a player-side question will inherit it.)

PHASES, all GROUNDED except P5 which is labelled:
  P0  ground survey -- warp a ladder of X positions and find where the act has real floor,
      measured live, so every later recovery warps somewhere the player can actually stand
  P1  long RIGHT run with real jumps
  P2  long LEFT run back
  P3  reversal whiplash straddling both internal X section seams (streamer whiplash)
  P4  grounded play anchored in EVERY surveyed ground spot, so the streamer is driven in
      each section rather than only the spawn one
  P5  debug-fly sweep of the whole grid -- NOT grounded, and reported separately. It is
      here because the page-in streamer (`PageIn_EnqueueLanding`) is the largest non-player
      Important consumer and a fly sweep is the hardest way to make it work; a straddle
      seen only here is still a straddle, but it is not "representative play".
  P6  a final long grounded RIGHT run

EXIT CODES (the house contract, same as tools/canopy_gap_exercise.py): 0 the campaign ran
to completion and the control moved -- the numbers in the report are readable; 2 setup, or
the control did not move, or the run was capped/reaped short. This script never returns 1:
a non-zero DMA_Split_Reject_Count is a FINDING to be reported, not a gate failure, and
turning it into an exit code would invite someone to "fix the red" instead of reading it.

RUN IT FOREGROUND. It boots a headless emulator through tools/aether_instance.py; oracle
from a background agent deadlocks, and this never touches the owner's window.

    python3 tools/dma_straddle_exercise.py [--rom s4.debug.bin] [--save out.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import zlib

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()
sys.path.insert(0, os.path.join(AEON, "tools"))

from aether import BusClient                                    # noqa: E402
from aether_instance import AetherInstance                      # noqa: E402
from raster_cost_probe import parse_lst                         # noqa: E402


class SetupError(Exception):
    """The campaign could not be run, or could not be READ. Exit 2 -- never a verdict."""


SETTLE_FRAMES = 180
MAX_CHUNK = 3600            # server's limits.maxRunFrames
JUMP_BUTTON = "a"           # B is stolen by the fly toggle while CHEAT_DEBUG_FLY is armed,
                            # and the DEBUG shape arms that at boot -- so A is the jump
                            # button for the whole session (canopy_gap_exercise.py's finding)
SECTION_SHIFT = 11          # SECTION_SIZE_SHIFT: 2048px sections

# Sst field offsets are NOT pinned here -- sst_offsets_from_source() re-derives all five
# from engine/objects/sst.emp on every run, so a struct move is a loud setup error rather
# than five confident numbers read off the wrong bytes. There is deliberately no second
# copy of them in this file to disagree with.

# The counters, in the two contiguous runs they actually occupy.
SUBJECT = ["Dbg_DMA_Straddle_All", "Dbg_DMA_Straddle_Frame",
           "Dbg_DMA_Straddle_Peak", "DMA_Split_Reject_Count"]
ADJACENT = ["DMA_Overflow_Count", "Dbg_DMA_Enq_Capped"]
ALL_CELLS = SUBJECT + ADJACENT

TILT_FRAMES = range(0x01, 0x31)   # walk $01-$20 + run $21-$30 (player_common.emp:224-244)


def sst_offsets_from_source() -> dict[str, int]:
    """Re-derive the five Sst offsets from sst.emp rather than trusting the constants
    above. A silent struct move is exactly the way this script would report confident
    nonsense about groundedness."""
    src = os.path.join(AEON, "engine/objects/sst.emp")
    want = {"y_pos": None, "x_pos": None, "status": None,
            "mapping_frame": None, "prev_frame": None}
    # SCOPED to `pub struct Sst` and nothing else. sst.emp also defines ObjDef, the spawn
    # TEMPLATE, which carries its own `status` at a DIFFERENT offset ($16 vs $1E) -- an
    # unscoped scan takes ObjDef's (it comes later in the file) and this script then reads
    # width_pixels and calls it the airborne bit. Measured: it did exactly that on the
    # first smoke run.
    in_sst = False
    with open(src) as fh:
        for line in fh:
            if re.match(r"\s*pub struct Sst\b", line):
                in_sst = True
                continue
            if in_sst and line.startswith("}"):
                break
            if not in_sst:
                continue
            m = re.match(r"\s*(\w+):\s*[^@]*@\s*\$([0-9A-Fa-f]+)", line)
            if m and m.group(1) in want:
                want[m.group(1)] = int(m.group(2), 16)
    missing = [k for k, v in want.items() if v is None]
    if missing:
        raise SetupError(f"could not read Sst offsets {missing} out of {src}")
    order = ["x_pos", "y_pos", "status", "mapping_frame", "prev_frame"]
    vals = [want[k] for k in order]
    if vals != sorted(vals) or len(set(vals)) != len(vals) or vals[-1] >= 0x50:
        raise SetupError(f"Sst offsets are not in the expected ascending order inside a "
                         f"$50-byte record: {want} -- refusing to guess")
    if want["mapping_frame"] - want["status"] >= 8:
        raise SetupError(f"mapping_frame (${want['mapping_frame']:02X}) is more than 8 bytes "
                         f"past status (${want['status']:02X}); player_state's single block "
                         f"read no longer covers it")
    return want


def st_in_air_bit() -> int:
    src = os.path.join(AEON, "engine/system/constants.emp")
    with open(src) as fh:
        for line in fh:
            m = re.match(r"\s*pub const ST_IN_AIR\s*=\s*(\d+)", line)
            if m:
                return 1 << int(m.group(1))
    raise SetupError(f"ST_IN_AIR is not declared in {src}")


def cheat_debug_fly_bit() -> int:
    src = os.path.join(AEON, "games/sonic4/config/constants.emp")
    with open(src) as fh:
        for line in fh:
            m = re.match(r"\s*pub const CHEAT_DEBUG_FLY\s*=\s*1\s*<<\s*(\d+)", line)
            if m:
                return 1 << int(m.group(1))
    raise SetupError(f"CHEAT_DEBUG_FLY is not declared as `1 << N` in {src}")


def hold_with_pulses(total: int, hold: list[str], pulse: str,
                     period: int, pulse_len: int) -> list[dict]:
    """`rows` for play_input: hold `hold` for `total` frames, tapping `pulse` for
    `pulse_len` every `period`. Rows union on the wire (oracle-aether `pad_at`)."""
    rows = [{"start": 0, "end": total, "buttons": list(hold)}]
    t = period // 2
    while t < total:
        rows.append({"start": t, "end": min(t + pulse_len, total), "buttons": [pulse]})
        t += period
    return rows


class Sample:
    __slots__ = ("frame", "phase", "cells", "x", "y", "in_air", "map_frame")

    def __init__(self, frame, phase, cells, x, y, in_air, map_frame):
        self.frame, self.phase, self.cells = frame, phase, cells
        self.x, self.y, self.in_air, self.map_frame = x, y, in_air, map_frame

    def as_dict(self):
        return {"frame": self.frame, "phase": self.phase, "cells": self.cells,
                "x": self.x, "y": self.y, "in_air": self.in_air,
                "map_frame": self.map_frame}


class Driver:
    def __init__(self, b: BusClient, sym: dict, off: dict, air_bit: int):
        self.b = b
        self.sym = sym
        self.off = off
        self.air_bit = air_bit
        self.player = sym["Player_1"] & 0xFFFFFF
        self.t0 = time.monotonic()
        self.frames_driven = 0
        self.samples: list[Sample] = []
        self.log: list[str] = []
        self.recoveries = 0
        self.sections_visited: set[tuple[int, int]] = set()
        self.map_frames_seen: set[int] = set()
        self.ground_anchors: list[tuple[int, int]] = []
        # first non-zero sighting of each subject cell: (frame, phase, value, x, y, in_air)
        self.first_hit: dict[str, dict] = {}

    # ---- plumbing ----------------------------------------------------------
    async def call(self, method: str, params: dict, timeout: float = 120.0):
        return await asyncio.wait_for(self.b.call(method, params), timeout=timeout)

    async def read_bytes(self, addr: int, n: int) -> bytes:
        r = await self.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = str(r["bytes"]).removeprefix("0x").removeprefix("0X")
        if len(s) != n * 2:
            # NEVER left-pad a short answer: a server that returned fewer bytes than asked
            # would silently shift every field in the block decode below.
            raise SetupError(f"read_memory at {addr:06X} len {n} returned {len(s) // 2} "
                             f"byte(s) ({s!r})")
        return bytes.fromhex(s)

    async def read_word(self, name: str) -> int:
        return int.from_bytes(await self.read_bytes(self.sym[name], 2), "big")

    async def read_long(self, name: str) -> int:
        return int.from_bytes(await self.read_bytes(self.sym[name], 4), "big")

    async def write_word(self, name: str, value: int) -> None:
        await self.call("emulator/write_memory",
                        {"addr": hex(self.sym[name] & 0xFFFFFF), "value": value, "width": 2})

    async def write_byte(self, name: str, value: int) -> None:
        await self.call("emulator/write_memory",
                        {"addr": hex(self.sym[name] & 0xFFFFFF), "value": value, "width": 1})

    # ---- the measurement ---------------------------------------------------
    async def read_cells(self) -> dict[str, int]:
        """One 8-byte read for the four tail cells (contiguous $FFE912-$FFE919) and one
        4-byte read for the two adjacent ones ($FFF8F78-$FFF8F7B). Contiguity is ASSERTED
        against the .lst at startup, so a RAM move turns into a loud setup error rather
        than into four numbers read off the wrong addresses."""
        tail = await self.read_bytes(self.sym["Dbg_DMA_Straddle_All"], 8)
        adj = await self.read_bytes(self.sym["DMA_Overflow_Count"], 4)
        return {
            "Dbg_DMA_Straddle_All":   int.from_bytes(tail[0:2], "big"),
            "Dbg_DMA_Straddle_Frame": int.from_bytes(tail[2:4], "big"),
            "Dbg_DMA_Straddle_Peak":  int.from_bytes(tail[4:6], "big"),
            "DMA_Split_Reject_Count": int.from_bytes(tail[6:8], "big"),
            "DMA_Overflow_Count":     int.from_bytes(adj[0:2], "big"),
            "Dbg_DMA_Enq_Capped":     int.from_bytes(adj[2:4], "big"),
        }

    async def player_state(self) -> tuple[int, int, bool, int]:
        pos = await self.read_bytes(self.player + self.off["x_pos"], 8)  # x 16.16, y 16.16
        x = int.from_bytes(pos[0:2], "big")
        y = int.from_bytes(pos[4:6], "big")
        blk = await self.read_bytes(self.player + self.off["status"], 8)  # $1E..$25
        status = blk[0]
        map_frame = blk[self.off["mapping_frame"] - self.off["status"]]
        return x, y, bool(status & self.air_bit), map_frame

    async def poll(self, phase: str) -> dict[str, int]:
        cells = await self.read_cells()
        x, y, in_air, mf = await self.player_state()
        s = Sample(self.frames_driven, phase, cells, x, y, in_air, mf)
        self.samples.append(s)
        self.map_frames_seen.add(mf)
        self.sections_visited.add((x >> SECTION_SHIFT, y >> SECTION_SHIFT))
        for name in SUBJECT[1:] + ADJACENT:      # All is expected non-zero; the rest are the news
            if cells[name] and name not in self.first_hit:
                self.first_hit[name] = {"frame": self.frames_driven, "phase": phase,
                                        "value": cells[name], "x": x, "y": y,
                                        "in_air": in_air, "map_frame": mf}
                print(f"      *** FIRST NON-ZERO {name}={cells[name]} at frame "
                      f"{self.frames_driven} ({phase}) player=({x},{y}) "
                      f"in_air={in_air} mapping_frame=${mf:02X}")
        return cells

    # ---- driving -----------------------------------------------------------
    async def chunk(self, phase: str, rows: list[dict], frames: int) -> None:
        assert frames <= MAX_CHUNK
        await self.call("emulator/play_input", {"rows": rows, "maxFrames": frames})
        await self.call("emulator/release_all", {})
        self.frames_driven += frames
        await self.poll(phase)

    async def run_phase(self, name: str, total: int, rows_fn, chunk_size: int,
                        keep_grounded: bool = True) -> None:
        remaining = total
        airborne_streak = 0
        while remaining > 0:
            n = min(chunk_size, remaining)
            await self.chunk(name, rows_fn(n), n)
            remaining -= n
            s = self.samples[-1]
            if keep_grounded:
                airborne_streak = airborne_streak + 1 if s.in_air else 0
                # Three consecutive airborne polls (>= 3*chunk frames) is not a jump --
                # it is the free fall that made the prior 600-frame attempt uninformative.
                if airborne_streak >= 3 and self.ground_anchors:
                    ax, ay = self.ground_anchors[self.recoveries % len(self.ground_anchors)]
                    print(f"      (recovering: airborne for >= {3 * chunk_size} frames at "
                          f"({s.x},{s.y}) -- warping to ground anchor ({ax},{ay}))")
                    await self.warp(ax, ay)
                    self.recoveries += 1
                    airborne_streak = 0
        self.report_phase(name)

    def report_phase(self, name: str) -> None:
        ss = [s for s in self.samples if s.phase == name]
        if not ss:
            return
        grounded = sum(1 for s in ss if not s.in_air)
        c = ss[-1].cells
        line = (f"  [{name}] {len(ss)} polls, ends frame {ss[-1].frame}, "
                f"grounded {grounded}/{len(ss)} ({100.0 * grounded / len(ss):.0f}%)  "
                f"All={c['Dbg_DMA_Straddle_All']} Peak={c['Dbg_DMA_Straddle_Peak']} "
                f"Reject={c['DMA_Split_Reject_Count']} Overflow={c['DMA_Overflow_Count']} "
                f"Capped={c['Dbg_DMA_Enq_Capped']}  "
                f"[{time.monotonic() - self.t0:6.1f}s wall]")
        print(line)
        self.log.append(line)

    async def warp(self, x: int, y: int) -> None:
        await self.write_word("Warp_Req_X", x)
        await self.write_word("Warp_Req_Y", y)
        await self.write_byte("Warp_Req_Flag", 1)
        for _ in range(120):
            await self.call("emulator/run_frames", {"frames": 1})
            self.frames_driven += 1
            v = int.from_bytes(await self.read_bytes(self.sym["Warp_Req_Flag"], 1), "big")
            if v == 0:
                return
        raise SetupError(f"Warp_Req_Flag never cleared warping to ({x},{y})")

    async def enter_fly(self) -> None:
        bit = cheat_debug_fly_bit()
        cur = int.from_bytes(await self.read_bytes(self.sym["Cheat_Flags"], 1), "big")
        await self.call("emulator/write_memory",
                        {"addr": hex(self.sym["Cheat_Flags"] & 0xFFFFFF),
                         "value": cur | bit, "width": 1})
        await self.toggle_fly()

    async def leave_fly_and_prove_physics(self, probe_frames: int) -> None:
        """Press B once to drop out of debug fly, then PROVE real physics is running:
        mapping_frame must move off $00 (the never-animated spawn value) and prev_frame off
        $FF within `probe_frames`. Without this proof the whole campaign can run green while
        the player is a camera puck that never touches Perform_DPLC."""
        before = await self.player_state()
        await self.toggle_fly()
        for _ in range(max(1, probe_frames // 30)):
            await self.call("emulator/run_frames", {"frames": 30})
            self.frames_driven += 30
            x, y, in_air, mf = await self.player_state()
            prev = (await self.read_bytes(self.player + self.off["prev_frame"], 1))[0]
            if mf != 0x00 and prev != 0xFF:
                print(f"  LEFT DEBUG FLY: player {before[0], before[1]} -> ({x},{y}), "
                      f"mapping_frame $00 -> ${mf:02X}, prev_frame $FF -> ${prev:02X}, "
                      f"in_air={in_air}. Real physics and the DPLC path are LIVE.")
                await self.poll("leave-fly")
                return
        raise SetupError(
            "after the B press the player still never animated (mapping_frame stayed $00 / "
            "prev_frame $FF) -- the machine is still in debug fly, Perform_DPLC's early-out "
            "fires every frame, and every number this campaign would print is about a "
            "player that enqueues nothing")

    async def toggle_fly(self) -> None:
        await self.call("emulator/play_input",
                        {"rows": [{"start": 0, "end": 2, "buttons": ["b"]}], "maxFrames": 2})
        await self.call("emulator/release_all", {})
        await self.call("emulator/run_frames", {"frames": 2})
        self.frames_driven += 4


# ---------------------------------------------------------------------------


async def ground_survey(d: Driver, xs: list[int], y: int, settle: int) -> None:
    """P0. Warp each candidate X at height `y`, let physics settle with NO input, and
    record the spots where the player ends up standing. This is measured, not assumed:
    the prior attempt's whole defect was believing the player was on ground when he was
    in free fall, and every recovery warp later in the campaign uses this list."""
    print("  [P0-survey] probing for real floor (warp, settle, read ST_IN_AIR)")
    for x in xs:
        try:
            await d.warp(x, y)
        except SetupError as e:
            print(f"      x={x}: warp refused ({e})")
            continue
        await d.call("emulator/run_frames", {"frames": settle})
        d.frames_driven += settle
        px, py, in_air, mf = await d.player_state()
        await d.poll("P0-survey")
        ok = not in_air
        if ok:
            d.ground_anchors.append((px, max(py - 32, 0)))
        print(f"      x={x:5d} -> player ({px},{py}) in_air={in_air} "
              f"{'GROUND' if ok else 'no floor'}")
    print(f"  [P0-survey] {len(d.ground_anchors)} ground anchor(s): {d.ground_anchors}")


async def body(sock: str, rom: str, lst: str, blob: bytes, args) -> Driver:
    sym = parse_lst(lst)
    off = sst_offsets_from_source()
    air_bit = st_in_air_bit()

    needed = ALL_CELLS + ["Player_1", "Camera_X", "Camera_Y", "Warp_Req_X", "Warp_Req_Y",
                          "Warp_Req_Flag", "Cheat_Flags", "Logic_Tick"]
    missing = sorted(n for n in needed if n not in sym)
    if missing:
        raise SetupError(f"symbols did not resolve in {lst}: {missing}")

    # Contiguity, asserted -- read_cells does two block reads and would otherwise decode
    # four numbers off whatever happens to sit at those addresses after a RAM move.
    base = sym["Dbg_DMA_Straddle_All"]
    for i, name in enumerate(SUBJECT):
        if sym[name] != base + 2 * i:
            raise SetupError(f"{name} is at {sym[name]:06X}, not {base + 2 * i:06X} -- "
                             f"the four straddle cells are no longer contiguous; "
                             f"read_cells' block read would decode garbage")
    if sym["Dbg_DMA_Enq_Capped"] != sym["DMA_Overflow_Count"] + 2:
        raise SetupError("DMA_Overflow_Count / Dbg_DMA_Enq_Capped are no longer adjacent")

    b = BusClient(sock, client_id="dma_straddle", client_name="dma_straddle_exercise")
    await b.connect()
    d = Driver(b, sym, off, air_bit)

    st = await d.call("emulator/status", {})
    if st["romBytes"] != len(blob):
        raise SetupError(f"server serves {st['romBytes']} bytes, {rom} is {len(blob)} -- "
                         f"refusing to drive a different ROM")
    print(f"ROM {rom}  {len(blob)} bytes crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")
    print(f"server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")
    print(f"Sst offsets from sst.emp: {off};  ST_IN_AIR mask ${air_bit:02X}")
    print(f"cells: " + ", ".join(f"{n}=${sym[n] & 0xFFFFFF:06X}" for n in ALL_CELLS))

    await d.call("emulator/run_frames", {"frames": args.settle})
    d.frames_driven += args.settle
    t0 = await d.read_long("Logic_Tick")
    await d.call("emulator/run_frames", {"frames": 2})
    d.frames_driven += 2
    t1 = await d.read_long("Logic_Tick")
    if t1 <= t0:
        raise SetupError(f"Logic_Tick did not advance across the settle ({t0} -> {t1}) -- "
                         f"the machine is not running the level")
    boot = await d.poll("boot")
    print(f"  settled {args.settle}f, Logic_Tick {t0} -> {t1}: alive")
    print(f"  AT BOOT: " + "  ".join(f"{k}={v}" for k, v in boot.items()))

    # ---- LEAVE DEBUG FLY. This is the single most important line in the script. ----
    # MEASURED, not read: the canonical DEBUG shape boots ALREADY IN free flight
    # (CHEAT_DEBUG_FLY armed AND engaged by GameState_OJZScroll_Init). In that state
    # Player_1 is moved by Player_DebugMove at a flat ~15.6 px/frame with x_vel/y_vel
    # both ZERO, status stuck at $08, and mapping_frame pinned at $00 with prev_frame
    # $FF -- i.e. THE PLAYER NEVER ANIMATES, so Perform_DPLC's `mapping_frame ==
    # prev_frame` early-out fires every single frame and the player enqueues NOTHING.
    # A campaign driven in that state cannot exercise the DPLC path at all and its
    # zeros would be worthless. One B press (edge-triggered) leaves fly and hands the
    # player to real physics; the assertion below is what proves it took.
    await d.leave_fly_and_prove_physics(args.physics_probe)

    # ---- P0: where is the floor? ----
    xs = list(range(args.survey_x0, args.survey_x1 + 1, args.survey_step))
    await ground_survey(d, xs, args.survey_y, args.survey_settle)
    if not d.ground_anchors:
        raise SetupError("the ground survey found NO spot where the player stands -- "
                         "every later phase would measure free fall, which is the exact "
                         "defect this run exists to avoid")
    spawn = d.ground_anchors[0]

    # ---- P1: long RIGHT with jumps ----
    await d.warp(*spawn)
    await d.run_phase("P1-right", args.p1_frames,
                      lambda n: hold_with_pulses(n, ["right"], JUMP_BUTTON, 97, 8),
                      chunk_size=args.chunk)

    # ---- P2: long LEFT back ----
    await d.run_phase("P2-left", args.p2_frames,
                      lambda n: hold_with_pulses(n, ["left"], JUMP_BUTTON, 113, 8),
                      chunk_size=args.chunk)

    # ---- P3: reversal whiplash at both internal X seams ----
    for seam in (2048, 4096):
        near = min(d.ground_anchors, key=lambda a: abs(a[0] - seam))
        await d.warp(seam - 96 if abs(near[0] - seam) > 400 else near[0], near[1])
        for i in range(args.p3_reversals):
            direction = "right" if i % 2 == 0 else "left"
            await d.chunk(f"P3-flip", [{"start": 0, "end": args.p3_leg,
                                        "buttons": [direction]}], args.p3_leg)
    d.report_phase("P3-flip")

    # ---- P4: grounded play anchored in EVERY surveyed ground spot ----
    for (ax, ay) in d.ground_anchors:
        await d.warp(ax, ay)
        for direction, period in (("right", 79), ("left", 91)):
            await d.run_phase("P4-anchored", args.p4_leg,
                              lambda n, _d=direction, _p=period:
                                  hold_with_pulses(n, [_d], JUMP_BUTTON, _p, 8),
                              chunk_size=args.chunk)
    d.report_phase("P4-anchored")

    # ---- P5: debug-fly sweep, NOT grounded, reported separately ----
    await d.enter_fly()
    remaining = args.p5_frames
    leg = min(args.p5_leg, MAX_CHUNK)
    i = 0
    while remaining > 0:
        n = min(leg, remaining)
        vert = "down" if (i % 2 == 0) else "up"
        horiz = "right" if (i // 3) % 2 == 0 else "left"
        await d.chunk("P5-fly", [{"start": 0, "end": n, "buttons": [vert, horiz]}], n)
        remaining -= n
        i += 1
    await d.toggle_fly()          # leave fly
    d.report_phase("P5-fly")

    # ---- P6: one more long grounded RIGHT run ----
    await d.warp(*spawn)
    await d.run_phase("P6-right", args.p6_frames,
                      lambda n: hold_with_pulses(n, ["right"], JUMP_BUTTON, 89, 8),
                      chunk_size=args.chunk)

    await b.close()
    return d


def summarise(d: Driver, args, elapsed: float) -> int:
    print()
    print("=" * 78)
    grounded_phases = [s for s in d.samples if s.phase.startswith(("P1", "P2", "P3", "P4", "P6"))]
    grounded = sum(1 for s in grounded_phases if not s.in_air)
    print(f"COVERAGE: {d.frames_driven} frames driven "
          f"({d.frames_driven / 60:.0f}s of game time at 60fps) in {elapsed:.1f}s wall clock")
    print(f"  polls: {len(d.samples)} total, {len(grounded_phases)} in GROUNDED phases")
    if grounded_phases:
        print(f"  GROUNDED FRACTION over the grounded phases: {grounded}/{len(grounded_phases)}"
              f" = {100.0 * grounded / len(grounded_phases):.1f}%"
              f"   ({d.recoveries} free-fall recovery warp(s))")
    xs = [s.x for s in d.samples]
    ys = [s.y for s in d.samples]
    print(f"  player X {min(xs)}..{max(xs)}, Y {min(ys)}..{max(ys)}")
    print(f"  world sections (col,row) visited: {sorted(d.sections_visited)}")
    tilt = sorted(f for f in d.map_frames_seen if f in TILT_FRAMES)
    print(f"  distinct mapping frames observed at poll boundaries: {len(d.map_frames_seen)}"
          f"  ({', '.join(f'${f:02X}' for f in sorted(d.map_frames_seen))})")
    print(f"  of those, walk/run TILT frames $01-$30 (the owner's 'rotated slightly'): "
          f"{len(tilt)}  ({', '.join(f'${f:02X}' for f in tilt) if tilt else 'NONE'})")

    final = d.samples[-1].cells
    peak_all = max(s.cells["Dbg_DMA_Straddle_All"] for s in d.samples)
    peak_peak = max(s.cells["Dbg_DMA_Straddle_Peak"] for s in d.samples)
    peak_frame = max(s.cells["Dbg_DMA_Straddle_Frame"] for s in d.samples)
    peak_rej = max(s.cells["DMA_Split_Reject_Count"] for s in d.samples)
    peak_ovf = max(s.cells["DMA_Overflow_Count"] for s in d.samples)
    peak_cap = max(s.cells["Dbg_DMA_Enq_Capped"] for s in d.samples)
    boot = d.samples[0].cells

    print()
    print("  cell                      at boot   final   max over all polls")
    for name, mx in (("Dbg_DMA_Straddle_All", peak_all),
                     ("Dbg_DMA_Straddle_Frame", peak_frame),
                     ("Dbg_DMA_Straddle_Peak", peak_peak),
                     ("DMA_Split_Reject_Count", peak_rej),
                     ("DMA_Overflow_Count", peak_ovf),
                     ("Dbg_DMA_Enq_Capped", peak_cap)):
        print(f"  {name:24s} {boot[name]:7d} {final[name]:7d} {mx:20d}")

    # THE READING RULE (ram.emp:1444-1448): the Important zeros mean nothing unless the
    # free-running control both is non-zero AND moved during this campaign.
    control_moved = peak_all > boot["Dbg_DMA_Straddle_All"]
    print()
    print(f"  CONTROL (Dbg_DMA_Straddle_All): {boot['Dbg_DMA_Straddle_All']} at boot -> "
          f"{final['Dbg_DMA_Straddle_All']} at end, max {peak_all}.  "
          f"MOVED: {control_moved}")
    if not control_moved:
        print()
        print("  VERDICT: UNMEASURABLE. The positive control did not move across the whole")
        print("  campaign, so by ram.emp's own reading rule a zero in the Important cells")
        print("  means 'nothing straddled at all' -- which is also what a broken instrument")
        print("  reads like. This is EXACTLY the defect that made the 600-frame RIGHT-hold")
        print("  attempt uninterpretable, and it is reported as such rather than as a zero.")
        return 2

    print()
    if peak_rej > 0:
        fh = d.first_hit.get("DMA_Split_Reject_Count", {})
        print(f"  VERDICT: DMA_Split_Reject_Count went NON-ZERO ({peak_rej}). Per ram.emp, "
              f"'any non-zero value here is the defect, observed directly'. First seen at "
              f"frame {fh.get('frame')} in phase {fh.get('phase')}, player "
              f"({fh.get('x')},{fh.get('y')}) in_air={fh.get('in_air')} "
              f"mapping_frame=${fh.get('map_frame', 0):02X}.")
    elif peak_peak > args.reserve:
        print(f"  VERDICT: NEAR MISS. Dbg_DMA_Straddle_Peak reached {peak_peak}, above the "
              f"{args.reserve}-slot DPLC_ENTRY_RESERVE, without a reject being observed.")
    else:
        print(f"  VERDICT: the Important straddle cells stayed at Peak={peak_peak} "
              f"(<= reserve {args.reserve}) and Reject=0 across this campaign, WITH a moving "
              f"control ({boot['Dbg_DMA_Straddle_All']} -> {peak_all}). On this evidence the "
              f"split-reject starvation path did not fire in representative play.")
    print("=" * 78)

    if args.save:
        json.dump({"rom": args.rom, "frames": d.frames_driven,
                   "elapsed_s": elapsed,
                   "grounded_polls": grounded, "grounded_phase_polls": len(grounded_phases),
                   "recoveries": d.recoveries,
                   "ground_anchors": d.ground_anchors,
                   "sections": sorted(d.sections_visited),
                   "map_frames": sorted(d.map_frames_seen),
                   "first_hit": d.first_hit,
                   "boot": boot, "final": final,
                   "max": {"Dbg_DMA_Straddle_All": peak_all,
                           "Dbg_DMA_Straddle_Frame": peak_frame,
                           "Dbg_DMA_Straddle_Peak": peak_peak,
                           "DMA_Split_Reject_Count": peak_rej,
                           "DMA_Overflow_Count": peak_ovf,
                           "Dbg_DMA_Enq_Capped": peak_cap},
                   "samples": [s.as_dict() for s in d.samples]},
                  open(args.save, "w"), indent=1)
        print(f"  wrote {args.save}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.debug.bin"))
    ap.add_argument("--lst", default=None)
    ap.add_argument("--save", help="archive every poll to this JSON")
    ap.add_argument("--settle", type=int, default=SETTLE_FRAMES)
    ap.add_argument("--chunk", type=int, default=60,
                    help="frames between polls in the held-direction phases (default 60 = "
                         "one poll per second of game time; a transient Peak is a "
                         "high-water mark so it survives, but Frame and the groundedness "
                         "sample do not)")
    ap.add_argument("--reserve", type=int, default=2, help="DPLC_ENTRY_RESERVE")
    ap.add_argument("--physics-probe", type=int, default=180,
                    help="frames to wait for the player to start animating after the B "
                         "press that leaves debug fly, before declaring the run unmeasurable")
    ap.add_argument("--survey-x0", type=int, default=200)
    ap.add_argument("--survey-x1", type=int, default=5900)
    ap.add_argument("--survey-step", type=int, default=200)
    ap.add_argument("--survey-y", type=int, default=300)
    ap.add_argument("--survey-settle", type=int, default=180,
                    help="frames of no-input settling after each survey warp. MEASURED: a "
                         "drop from y=300 to the spawn floor at y=573 takes about 60 frames "
                         "and the act has deeper pockets, so a short settle reports floor as "
                         "void")
    ap.add_argument("--p1-frames", type=int, default=3000)
    ap.add_argument("--p2-frames", type=int, default=3000)
    ap.add_argument("--p3-reversals", type=int, default=32)
    ap.add_argument("--p3-leg", type=int, default=30)
    ap.add_argument("--p4-leg", type=int, default=600)
    ap.add_argument("--p5-frames", type=int, default=6000)
    ap.add_argument("--p5-leg", type=int, default=300)
    ap.add_argument("--p6-frames", type=int, default=3000)
    args = ap.parse_args()

    rom = os.path.abspath(args.rom)
    args.rom = rom
    lst = os.path.abspath(args.lst) if args.lst else rom[:-4] + ".lst"
    try:
        blob = open(rom, "rb").read()
    except OSError as e:
        print(f"dma_straddle_exercise: SETUP -- {e}", file=sys.stderr)
        return 2
    if not os.path.exists(lst):
        print(f"dma_straddle_exercise: SETUP -- no listing at {lst}", file=sys.stderr)
        return 2

    inst = AetherInstance(rom, symbols=lst)
    try:
        sock = inst.start()
    except Exception as e:                       # noqa: BLE001 -- spawn failure is setup
        print(f"dma_straddle_exercise: SETUP -- {e}", file=sys.stderr)
        return 2
    t0 = time.monotonic()
    try:
        d = asyncio.run(body(sock, rom, lst, blob, args))
    except SetupError as e:
        print(f"dma_straddle_exercise: SETUP -- {e}", file=sys.stderr)
        return 2
    except asyncio.TimeoutError:
        print("dma_straddle_exercise: SETUP -- an RPC exceeded its deadline (emulator wedge); "
              "the campaign did NOT complete and its partial numbers are NOT a result",
              file=sys.stderr)
        return 2
    finally:
        inst.reap()
    return summarise(d, args, time.monotonic() - t0)


if __name__ == "__main__":
    sys.exit(main())
