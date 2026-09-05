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

So this script refuses to report a verdict unless a control has FIRED. It runs two, and
that distinction turned out to be the whole result:

  CONTROL A, natural -- did Dbg_DMA_Straddle_All move during ordinary play?
  CONTROL B, forced  -- write a straddling DPLC frame into the player's mapping_frame, run
      ONE frame, and watch the counter. This uses the ROM's own data and no source change,
      It runs on its OWN emulator instance with a fresh boot per attempt, because a force
      -- whether or not it fires -- leaves the machine in the MD Debugger island, and on a
      single machine that gives the control exactly one roll of an intra-frame phase race.
      Three full campaigns reported UNMEASURABLE that way while the instrument was fine.
      See control_body().

Control A failing is not the same as a broken instrument, and the difference is decidable:
static_straddle_survey() reads the act's page manifest out of the ROM and asks whether any
page-in landing -- a DIRECT ROM->VRAM DMA on the RAW form -- can cross a 128 KB boundary at
all. If none can, and tools/dplc_straddle.py already says every straddling DPLC frame in the
cast is unreachable through its anim table, then the straddle population in ordinary play is
EMPTY BY CONSTRUCTION and a zero from control A is the correct answer. Only both controls
failing is exit 2 (could-not-measure).

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
to completion and a control FIRED -- the numbers in the report are readable; 2 setup, or
NEITHER control fired, or the run was capped/reaped short. This script never returns 1:
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
        self.campaign_frames = 0          # frames driven before the post-campaign control
        self.campaign_final: dict = {}    # the cells as the CAMPAIGN left them
        self.control: dict = {}           # control_body()'s record
        self.recover_after = 2            # consecutive airborne polls before a rescue warp
        # The straddling frame per character, from tools/dplc_straddle.py's per-build report.
        self.control_ladder = (0x65, 0x9F, 0x85)
        self.control_tries = 12           # attempts per frame: the force is a PHASE RACE
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
                # N consecutive airborne polls (>= N*chunk frames) is not a jump -- it is
                # the free fall that made the prior 600-frame attempt uninformative. The
                # act's built ground is SMALL (the survey finds floor over a fraction of
                # the 6144px width), so a held direction sails off it within a couple of
                # seconds and the recovery is what keeps the grounded fraction meaningful.
                if airborne_streak >= self.recover_after and self.ground_anchors:
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


# 68000 word-write opcodes onto an absolute-short destination, i.e. the forms these six
# cells are actually written with. Derived by reading the two writers, NOT guessed:
# dma_queue.emp uses `addq.w #1,(xxx).w`; vblank.emp's VInt_Level fold uses
# `move.w d0,(xxx).w` for the peak and `clr.w (xxx).w` for the per-frame cell. Getting
# this set wrong is not a silent failure -- an unmatched cell is reported as NONE, which
# is exactly what happened on the first run of this check when it only knew ADDQ and
# declared the Peak cell dead.
WRITE_OPCODES = {
    0x5278: "addq.w #1,(xxx).w",
    0x4278: "clr.w (xxx).w",
    **{0x31C0 | n: f"move.w d{n},(xxx).w" for n in range(8)},
}


def counters_present_in_rom(blob: bytes, sym: dict) -> dict[str, list[dict]]:
    """Find each counter's WRITE sites in the ROM image. This proves the `if DEBUG == 1`
    blocks were COMPILED IN -- a shape that silently dropped them would read zero from a
    cell nothing writes, which is indistinguishable at the bus from a real zero. It does
    NOT prove reachability; only the positive control does that, and only for the straddle
    path.

    A match is an opcode word from WRITE_OPCODES immediately followed by the cell's
    absolute-short address, so a bare occurrence of the address bytes inside data does not
    count as a write."""
    out: dict[str, list[dict]] = {}
    for name in ALL_CELLS:
        short = sym[name] & 0xFFFF
        sites = []
        for i in range(0, len(blob) - 4, 2):
            op = (blob[i] << 8) | blob[i + 1]
            if op in WRITE_OPCODES and ((blob[i + 2] << 8) | blob[i + 3]) == short:
                sites.append({"addr": i, "form": WRITE_OPCODES[op]})
        out[name] = sites
    return out


def static_straddle_survey(blob: bytes, sym: dict) -> dict:
    """Read the act's page manifest out of the ROM and ask whether ANY page-in landing --
    the largest non-player Important consumer, and a DIRECT ROM->VRAM DMA on the RAW form
    (page_in.emp:272-287) -- can cross a 128 KB DMA-source boundary in this act.

    This is what makes a zero control readable. If no page can straddle and no REACHABLE
    DPLC frame straddles (tools/dplc_straddle.py, run on every build, says the ROM's three
    straddling frames -- Sonic $65, Tails $9F, Knuckles $85 -- are all unreachable through
    their anim tables), then the straddle population in ordinary play is EMPTY BY
    CONSTRUCTION, and Dbg_DMA_Straddle_All = 0 is the correct answer rather than a broken
    instrument. The ZX0 form cannot straddle at all: it DMAs from Art_Staging_Buffer in
    work RAM, and $FF0000-$FFFFFF lies wholly inside one 128 KB block."""
    name = next((k for k in sym if k.endswith("_Act_Pool_PageTable")), None)
    if name is None:
        return {"error": "no *_Act_Pool_PageTable symbol in the listing"}
    tbl = sym[name] & 0xFFFFFF
    pages = []
    for i in range(64):                      # bounded; stops on the first implausible row
        o = tbl + i * 8
        if o + 8 > len(blob):
            break
        src = int.from_bytes(blob[o:o + 4], "big")
        tiles = int.from_bytes(blob[o + 4:o + 6], "big")
        if src == 0 or src >= len(blob) or tiles == 0 or tiles > 0x100:
            break
        ln = tiles * 32
        end = src + ln - 1
        pages.append({"i": i, "src": src, "tiles": tiles, "len": ln, "end": end,
                      "form": blob[o + 6], "flags": blob[o + 7],
                      "crosses": (src >> 17) != (end >> 17)})
    return {"table": name, "table_addr": tbl, "pages": pages,
            "any_crosses": any(p["crosses"] for p in pages)}


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
    d.recover_after = max(1, args.recover_after)
    d.control_ladder = tuple(f & 0xFF for f in args.control_frame)
    d.control_tries = max(1, args.control_tries)

    st = await d.call("emulator/status", {})
    if st["romBytes"] != len(blob):
        raise SetupError(f"server serves {st['romBytes']} bytes, {rom} is {len(blob)} -- "
                         f"refusing to drive a different ROM")
    print(f"ROM {rom}  {len(blob)} bytes crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")
    print(f"server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")
    print(f"Sst offsets from sst.emp: {off};  ST_IN_AIR mask ${air_bit:02X}")
    print(f"cells: " + ", ".join(f"{n}=${sym[n] & 0xFFFFFF:06X}" for n in ALL_CELLS))

    # ---- STATIC CHECK 1: are the DEBUG counter writes actually in this ROM image? ----
    d.counters_in_rom = counters_present_in_rom(blob, sym)
    dead = [n for n, sites in d.counters_in_rom.items() if not sites]
    for n, sites in d.counters_in_rom.items():
        print(f"  ROM write site(s) for {n:24s}: "
              + (", ".join(f"0x{x['addr']:X} {x['form']}" for x in sites)
                 if sites else "NONE"))
    if dead:
        raise SetupError(f"no `addq.w #1,(cell).w` write site in the ROM for {dead} -- the "
                         f"`if DEBUG == 1` block did not compile into this shape, so those "
                         f"cells read zero because NOTHING writes them")

    # ---- STATIC CHECK 2: can any page-in landing straddle in this act at all? ----
    d.static_survey = static_straddle_survey(blob, sym)
    ss = d.static_survey
    if "error" in ss:
        print(f"  static page-manifest survey: {ss['error']}")
    else:
        print(f"  static page-manifest survey ({ss['table']} @ 0x{ss['table_addr']:X}, "
              f"{len(ss['pages'])} page(s)):")
        for pg in ss["pages"]:
            print(f"    page{pg['i']:<2d} src=0x{pg['src']:06X} tiles={pg['tiles']:<3d} "
                  f"len={pg['len']:<5d} end=0x{pg['end']:06X} form={pg['form']} "
                  f"crosses128K={pg['crosses']}")
        print(f"    ANY page-in landing in this act can straddle a 128 KB boundary: "
              f"{ss['any_crosses']}")

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

    # ---- P4b: SHUTTLE. The act's built floor is a narrow strip (the survey finds it over
    #      roughly x 200-2100 of a 6144px act), so any held direction runs off it within a
    #      couple of seconds and the rest of the leg is free fall. Flipping direction every
    #      `--shuttle-leg` frames keeps the player ON the floor, which is the only way this
    #      campaign gets a grounded fraction worth quoting -- and grounded, animating play
    #      is exactly the condition the F7 report describes. ----
    for (ax, ay) in d.ground_anchors:
        await d.warp(ax, ay)
        for i in range(args.shuttle_reps):
            direction = "right" if i % 2 == 0 else "left"
            await d.chunk("P4b-shuttle",
                          hold_with_pulses(args.shuttle_leg, [direction], JUMP_BUTTON,
                                           args.shuttle_leg + 1, 8),
                          args.shuttle_leg)
    d.report_phase("P4b-shuttle")

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

    # ---- THE CAMPAIGN ENDS HERE. ----
    d.campaign_frames = d.frames_driven
    d.campaign_final = await d.read_cells()

    await b.close()
    return d


async def control_body(sock: str, lst: str, blob: bytes, args, d: Driver) -> dict:
    """CONTROL B on its OWN MACHINE. Measured reason, not tidiness: a force that works
    ends the run -- the enqueue completes and then the out-of-range frame is guarded
    downstream, leaving the machine in the MD Debugger island with Logic_Tick frozen. A
    force the DPLC never sees ALSO ends the run the same way, without having enqueued
    anything. So on a single machine the control gets exactly ONE attempt, and a miss is
    indistinguishable from a dead instrument -- which is how three full campaigns in a row
    reported UNMEASURABLE while the instrument was fine.

    And a miss is not bad luck. Whether Perform_DPLC sees the forced value is DETERMINISTIC
    in the frame the machine is stopped on: the base staging below fired on six resets out
    of six, and the same staging with two extra frames in it missed on six out of six. So
    each attempt here gets a fresh boot AND a settle one frame longer than the last, which
    sweeps that offset instead of re-rolling it. It also removes the last contamination worry:
    the campaign's numbers were read on a machine this never touched.

    WHY A FORCED CONTROL AT ALL. ram.emp's reading rule says an Important zero means
    "Important never straddled" only while Dbg_DMA_Straddle_All is non-zero -- otherwise it
    means "nothing straddled at all", which is also what a broken instrument reads like.
    That rule assumes ordinary play can move the control. In this act it structurally
    cannot (see static_straddle_survey), so waiting for the control to move is waiting
    forever, and calling the wait a failure throws away a real answer. The force uses the
    ROM's own data and no source change: Perform_DPLC sees mapping_frame != prev_frame,
    walks that frame's entries, and the straddling one takes `.split` -- the exact
    instruction path the four cells sit on.

    THE TWO WAYS AN EARLIER VERSION OF THIS GOT A CONFIDENT WRONG ANSWER, both measured:
      * It ran at the END of the campaign, where the player had fallen out of the world at
        y65469. Perform_DPLC is reached through the object's display path, which an object
        that far out does not take, so the force did nothing and read as "instrument dead".
        A fresh boot puts the player at spawn, grounded and animating, by construction.
      * It SWEPT all 256 mapping frames looking for the straddling set. The sweep started
        at $00, that first force stopped the machine, and it then reported that NOTHING
        straddles -- an answer manufactured entirely by the control's own side effect.

    WHY THE INCREMENT IS A REAL STRADDLE AND NOT A CRASH ARTIFACT: prev_frame is committed
    only after every entry enqueued (dplc.emp:214-262) and the commit is observed, and the
    Important-only counter Dbg_DMA_Straddle_Frame moves alongside the all-queue one. The
    guard that stops the machine is downstream of the queue.

    THE LADDER IS PER CHARACTER: the DPLC walks only the ACTIVE character's table, and
    Debug_CharacterHotkey can cycle the roster off a campaign's own A presses, so a control
    pinned to Sonic's frame could read "did not fire" for a reason with nothing to do with
    the subject. Character_ID is reported beside the result."""
    b = BusClient(sock, client_id="dma_straddle_ctl", client_name="dma_straddle_control")
    await b.connect()
    c = Driver(b, d.sym, d.off, d.air_bit)
    c.control_ladder = d.control_ladder
    c.control_tries = d.control_tries
    hits: list[int] = []
    important: list[int] = []
    attempts = 0
    commits = 0
    before = after = {}
    char = -1
    for f in c.control_ladder:
        if hits:
            break
        for extra in range(c.control_tries):
            # THE STAGING IS EXACT, and the offset sweep is why. Whether the force is seen
            # by Perform_DPLC that frame is DETERMINISTIC in the frame the machine is
            # stopped on, not random: measured, `reset -> 180f -> B(2f) -> release ->
            # 120f -> force` FIRES every run, and the same sequence with two extra frames
            # in it FAILS every run -- six resets each way, no exceptions. So this does not
            # retry the same thing hoping for luck; it steps the settle by one frame per
            # attempt, on a fresh boot each time, and sweeps the phase.
            await c.call("emulator/reset", {})
            await c.call("emulator/run_frames", {"frames": args.settle})
            await c.call("emulator/play_input",
                         {"rows": [{"start": 0, "end": 2, "buttons": ["b"]}], "maxFrames": 2})
            await c.call("emulator/release_all", {})
            await c.call("emulator/run_frames", {"frames": 120 + extra})
            if "Character_ID" in c.sym:
                char = (await c.read_bytes(c.sym["Character_ID"], 2))[1]
            pre = await c.read_cells()
            before = before or pre
            await c.call("emulator/write_memory",
                         {"addr": hex(c.player + c.off["prev_frame"]),
                          "value": (f ^ 0xFF) & 0xFF, "width": 1})
            await c.call("emulator/write_memory",
                         {"addr": hex(c.player + c.off["mapping_frame"]),
                          "value": f, "width": 1})
            await c.call("emulator/run_frames", {"frames": 1})
            attempts += 1
            post = await c.read_cells()
            after = post
            if (await c.read_bytes(c.player + c.off["prev_frame"], 1))[0] == f:
                commits += 1
            if post["Dbg_DMA_Straddle_All"] > pre["Dbg_DMA_Straddle_All"]:
                hits.append(f)
                if post["Dbg_DMA_Straddle_Frame"] > pre["Dbg_DMA_Straddle_Frame"]:
                    important.append(f)
                break
    tick = await c.read_long("Logic_Tick")
    await b.close()
    return {"before": before, "after": after, "frames_that_straddled": hits,
            "of_which_important": important,
            "forced_frames_tried": list(c.control_ladder),
            "character_id": char, "attempts": attempts, "dplc_commits": commits,
            "prev_frame_committed_to": (hits[0] if hits else -1),
            "logic_tick_after": tick, "own_machine": True}


def report_control(d: Driver) -> None:
    print()
    print("  --- POSITIVE CONTROL (its own machine, fresh boot per attempt) ---")
    print(f"  Character_ID at the control: {d.control['character_id']} "
          f"({ {0: 'sonic', 1: 'tails', 2: 'knuckles'}.get(d.control['character_id'], '?') })")
    hits = d.control["frames_that_straddled"]
    if hits:
        print(f"  the instrument FIRES: forcing mapping_frame ${hits[0]:02X} moved "
              f"Dbg_DMA_Straddle_All {d.control['before']['Dbg_DMA_Straddle_All']} -> "
              f"{d.control['after']['Dbg_DMA_Straddle_All']} in ONE frame; the "
              f"Important-only cell Dbg_DMA_Straddle_Frame moved "
              f"{d.control['before']['Dbg_DMA_Straddle_Frame']} -> "
              f"{d.control['after']['Dbg_DMA_Straddle_Frame']}"
              + ("" if d.control['of_which_important'] else " (NOT counted as Important)"))
        print(f"  the DPLC committed prev_frame to "
              f"${d.control['prev_frame_committed_to']:02X}, i.e. EVERY entry of that frame "
              f"enqueued -- the straddling one included. "
              f"({d.control['dplc_commits']} DPLC commit(s) over "
              f"{d.control['attempts']} attempt(s) at stepped settle offsets.)")
    else:
        print(f"  the instrument did NOT fire on any forced mapping frame of "
              f"{', '.join(f'${f:02X}' for f in d.control['forced_frames_tried'])}.")
    print(f"  ({d.control['attempts']} attempt(s), each on a fresh boot; "
          f"{d.control['dplc_commits']} of them got the DPLC to commit prev_frame. "
          f"Logic_Tick on the control machine afterwards: {d.control['logic_tick_after']} "
          f"-- an out-of-range mapping frame is guarded downstream of the queue, so a "
          f"fired control leaves its own machine in the MD Debugger island. The campaign "
          f"machine was never touched by any of this.)")


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

    # ---- THE READING RULE (ram.emp:1444-1448), and the two ways to satisfy it ----
    # ram.emp: an Important zero means "Important never straddled" only while
    # Dbg_DMA_Straddle_All is non-zero; otherwise it means "nothing straddled at all,
    # which is also what a broken instrument reads like". The rule's job is to rule OUT
    # a dead instrument. Ordinary play moving the control is ONE way to do that. A
    # deliberately forced straddle is another, and it is the only one available when the
    # act's straddle population is empty by construction -- which is a fact about the ROM,
    # not a failure of the run, and is established here rather than assumed.
    control_moved = peak_all > boot["Dbg_DMA_Straddle_All"]
    forced = d.control.get("frames_that_straddled") or []
    print()
    print(f"  CONTROL A (natural): Dbg_DMA_Straddle_All {boot['Dbg_DMA_Straddle_All']} at "
          f"boot -> {d.campaign_final.get('Dbg_DMA_Straddle_All', final['Dbg_DMA_Straddle_All'])}"
          f" at the end of the campaign, max {peak_all}.  MOVED DURING PLAY: {control_moved}")
    print(f"  CONTROL B (forced):  {'FIRED' if forced else 'DID NOT FIRE'}"
          + (f" -- forcing mapping_frame ${forced[0]:02X} moved the counter in ONE frame; "
             f"straddling frames seen live: {', '.join(f'${f:02X}' for f in forced)}"
             if forced else ""))
    if not forced:
        print()
        print("  VERDICT: UNMEASURABLE. Neither control fired: the counters did not move in")
        print("  play AND did not move when a straddling DPLC frame was forced. By ram.emp's")
        print("  own reading rule the Important zeros above are indistinguishable from a")
        print("  broken instrument, and they are reported as unmeasurable, not as zeros.")
        return 2
    if not control_moved:
        print()
        print("  NOTE: the control never moved in PLAY, only when forced. Read the zeros as")
        print("  'the straddle population reachable by this act is empty', NOT as 'straddles")
        print("  were possible and none happened' -- see the static survey printed above.")

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
        print(f"  VERDICT: across {d.campaign_frames} frames of campaign play the Important "
              f"straddle cells stayed at Peak={peak_peak} (<= reserve {args.reserve}) and "
              f"Reject=0, with the instrument PROVEN live by the forced control. No enqueue "
              f"was dropped by any of the three drop paths either: DMA_Split_Reject_Count="
              f"{peak_rej}, DMA_Overflow_Count={peak_ovf}, Dbg_DMA_Enq_Capped={peak_cap}. "
              f"Since a dropped Important enqueue is the NECESSARY first step of the F7 "
              f"stale-prev_frame mechanism, and no drop of any kind occurred, that mechanism "
              f"did not fire in this campaign.")
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
                   "campaign_frames": d.campaign_frames,
                   "campaign_final": d.campaign_final,
                   "control": d.control,
                   "static_survey": getattr(d, "static_survey", {}),
                   "counters_in_rom": getattr(d, "counters_in_rom", {}),
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
    ap.add_argument("--chunk", type=int, default=30,
                    help="frames between polls in the held-direction phases (default 60 = "
                         "one poll per half-second of game time; a transient Peak is a "
                         "high-water mark so it survives, but Frame and the groundedness "
                         "sample do not)")
    ap.add_argument("--reserve", type=int, default=2, help="DPLC_ENTRY_RESERVE")
    ap.add_argument("--shuttle-leg", type=int, default=45,
                    help="frames per direction in the P4b shuttle (short enough that the "
                         "player does not reach the edge of the act's narrow built floor)")
    ap.add_argument("--shuttle-reps", type=int, default=24,
                    help="direction flips per ground anchor in the P4b shuttle")
    ap.add_argument("--recover-after", type=int, default=2,
                    help="consecutive airborne polls before warping back to a ground anchor")
    ap.add_argument("--control-tries", type=int, default=12,
                    help="attempts per control frame, each a fresh boot with the settle one "
                         "frame longer than the last. Whether Perform_DPLC sees the forced "
                         "value is DETERMINISTIC in the stop frame, not random -- measured "
                         "as fire-every-time at the base offset and fail-every-time two "
                         "frames off it -- so this sweeps the phase rather than retrying.")
    ap.add_argument("--control-frame", type=lambda v: int(v, 0), nargs="+",
                    default=[0x65, 0x9F, 0x85],
                    help="mapping frames the post-campaign positive control tries, in order, "
                         "stopping at the first that fires. Defaults are the ONE straddling "
                         "frame per character that tools/dplc_straddle.py names on every "
                         "build: sonic $65, tails $9F, knuckles $85. The ladder exists "
                         "because the campaign's own A presses can cycle the active "
                         "character, and the DPLC only walks the active one's table.")
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
    ap.add_argument("--p1-frames", type=int, default=1800)
    ap.add_argument("--p2-frames", type=int, default=1800)
    ap.add_argument("--p3-reversals", type=int, default=32)
    ap.add_argument("--p3-leg", type=int, default=30)
    ap.add_argument("--p4-leg", type=int, default=300)
    ap.add_argument("--p5-frames", type=int, default=6000)
    ap.add_argument("--p5-leg", type=int, default=300)
    ap.add_argument("--p6-frames", type=int, default=1800)
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

    # ---- CONTROL B on a second, untouched machine. The campaign's numbers are already
    #      read; this only has to answer "does the counter increment on a real straddling
    #      enqueue". A fresh boot per attempt is what makes the intra-frame phase race
    #      survivable instead of fatal -- see control_body's docstring. ----
    cinst = AetherInstance(rom, symbols=lst)
    try:
        csock = cinst.start()
        d.control = asyncio.run(control_body(csock, lst, blob, args, d))
    except (SetupError, asyncio.TimeoutError, Exception) as e:   # noqa: BLE001
        print(f"dma_straddle_exercise: the positive control could not be run ({e!r}) -- "
              f"the campaign numbers below are therefore UNREADABLE, not zero",
              file=sys.stderr)
        d.control = {"before": {}, "after": {}, "frames_that_straddled": [],
                     "of_which_important": [], "forced_frames_tried": list(d.control_ladder),
                     "character_id": -1, "attempts": 0, "dplc_commits": 0,
                     "prev_frame_committed_to": -1, "logic_tick_after": -1,
                     "own_machine": True, "error": repr(e)}
    finally:
        cinst.reap()
    report_control(d)
    return summarise(d, args, time.monotonic() - t0)


if __name__ == "__main__":
    sys.exit(main())
