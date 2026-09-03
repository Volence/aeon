#!/usr/bin/env python3
"""canopy_gap_exercise — drive OJZ act 1 hard, headlessly, with the canopy-gap capture
instrument armed, and try to make it fire.

WHY THIS EXISTS. DoD item 17 (docs/DEFERRED_WORK.md, "CANOPY GAP") requires a found cause
and a fix. Two derived (code-read) explanations for the canopy gap were already refuted by
measurement, so a third derivation is not the deliverable. The instrument
(`Canopy_Probe`/`Canopy_Fire`/`Canopy_Persist` in `engine/level/section.emp`, the shadow
writes in `engine/level/plane_buffer.emp`, `tools/canopy_record.py`) exists precisely
because nobody could settle this from a post-hoc read — but as of 2026-09-02 it had never
been run against a live machine (`tools/canopy_record.py`'s `read_live` used
`async with AetherInstance(...)`, which does not exist; fixed in the same parcel as this
script — see the note at the top of `canopy_record.py`'s `read_live`). This script is the
FIRST thing that actually exercises the instrument end-to-end: it plays the level for real
(held direction + real jumps, not just camera pokes) for a long, continuous session, adds
warps and a debug-fly vertical sweep, and polls the latch throughout so a fire is caught
with the whole shadow still fresh, whether or not the run was watched.

WHAT IT DOES NOT DO: diagnose. If the instrument fires, this script decodes and archives
the record and stops — the cause is for a human (or the next pass of this task) to read out
of `Canopy_Rec_*` per `tools/canopy_record.py`'s own documentation. If it does not fire,
this script's OUTPUT IS THE COVERAGE, not a verdict: exactly what was driven, for how long,
through which sections, so the next attempt can vary something real instead of re-deriving.

PHASES (default sizes are the `--p*` argparse defaults below), each logged with camera
position, frame count and wall clock, each checked for a latch before moving to the next:

  1. long RIGHT run with periodic real jumps, start to the act's right edge
  2. long LEFT run back to the start, crossing every section boundary in reverse
  3. rapid direction reversals straddling BOTH internal section boundaries (a streamer
     whiplash)
  4. debug-fly sweep of both axes over the WHOLE grid (avoids the unrelated no-wall-at-
     the-edge freefall real physics has at the act's right edge -- see the module's
     `classify_and_maybe_clear` docstring)
  5. warp-mailbox hops to distant sections and back, each followed by ordinary
     held-direction play (not a static settle) so the post-warp redraw is exercised by
     a moving camera, not just a resting one
  6. a final long RIGHT run to end on fresh ground

USAGE
    python3 tools/canopy_gap_exercise.py                          # full campaign
    python3 tools/canopy_gap_exercise.py --save capture.json       # archive the end-state
                                                                    # canopy record either way
    python3 tools/canopy_gap_exercise.py --p1-frames 6000 ...      # every phase's frame
                                                                    # budget is a --p<N>-*
                                                                    # flag; see `main()`'s
                                                                    # argparse block

To test the CANOPY_PERSIST_FRAMES caveat this instrument's own docs warn about (an empty
record does not distinguish "no defect" from "the latch is too strict to see it"): lower
`pub const CANOPY_PERSIST_FRAMES` in engine/system/constants.emp, rebuild DEBUG, and re-run
this same script -- it reads the constant live via canopy_record.geometry(), so nothing here
needs to change. Revert the constant and rebuild before calling the tree clean again.

Exit codes (the house contract): 0 the campaign ran to completion (fired or not — this is
a driver with a coverage report, not a gate with a verdict), 2 setup / could-not-measure.

RUN IT FOREGROUND. It boots a headless emulator through `tools/aether_instance.py`; oracle
from a background agent deadlocks, and this never touches the owner's window.
"""
from __future__ import annotations

import argparse
import asyncio
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
import canopy_record as cr                                      # noqa: E402


class SetupError(Exception):
    """The campaign could not be run. Exit 2 -- never a verdict."""


SETTLE_FRAMES = 180          # boot -> gameplay, the tree-wide constant (see warp_mailbox_gate)
MAX_CHUNK = 3600             # server's limits.maxRunFrames
JUMP_BUTTON = "a"            # A|B|C all jump normally; B is excluded from the mask while
                             # CHEAT_DEBUG_FLY is armed (games/sonic4/player/player_common.emp),
                             # and the DEBUG shape arms that cheat at boot (ojz_scroll_test.emp
                             # GameState_OJZScroll_Init) -- so A/C are the reliable jump buttons
                             # for the WHOLE session, fly or not.


def cheat_debug_fly_bit() -> int:
    src = os.path.join(AEON, "games/sonic4/config/constants.emp")
    with open(src) as fh:
        for line in fh:
            m = re.match(r"\s*pub const CHEAT_DEBUG_FLY\s*=\s*1\s*<<\s*(\d+)", line)
            if m:
                return 1 << int(m.group(1))
    raise SetupError(f"CHEAT_DEBUG_FLY is not declared as `1 << N` in {src}")


def hold_with_pulses(total: int, hold: list[str], pulse: str, period: int, pulse_len: int) -> list[dict]:
    """`rows` for `play_input`: hold `hold` buttons for `total` frames, tapping `pulse`
    for `pulse_len` frames every `period` frames. Rows are a UNION on the wire (oracle-aether
    `pad_at`), so this is simply the base hold row plus one short row per pulse -- no need to
    split the base row around the pulses.
    """
    rows = [{"start": 0, "end": total, "buttons": list(hold)}]
    t = period // 2
    while t < total:
        rows.append({"start": t, "end": min(t + pulse_len, total), "buttons": [pulse]})
        t += period
    return rows


class Driver:
    def __init__(self, b: BusClient, sym: dict, k: dict, geom: dict):
        self.b = b
        self.sym = sym
        self.k = k
        self.geom = geom
        self.t0 = time.monotonic()
        self.frames_driven = 0
        self.min_x = self.max_x = self.min_y = self.max_y = None
        self.sections_visited: set[tuple[int, int]] = set()
        self.log: list[str] = []
        self.benign_edge_fires = 0

    async def call(self, method: str, params: dict, timeout: float = 60.0):
        return await asyncio.wait_for(self.b.call(method, params), timeout=timeout)

    async def read_word(self, name: str) -> int:
        r = await self.call("emulator/read_memory", {"addr": hex(self.sym[name]), "len": 2})
        return int(str(r["bytes"]).removeprefix("0x").removeprefix("0X"), 16)

    async def read_long(self, name: str) -> int:
        r = await self.call("emulator/read_memory", {"addr": hex(self.sym[name]), "len": 4})
        return int(str(r["bytes"]).removeprefix("0x").removeprefix("0X"), 16)

    async def write_word(self, name: str, value: int) -> None:
        await self.call("emulator/write_memory",
                         {"addr": hex(self.sym[name]), "value": value, "width": 2})

    async def write_byte(self, name: str, value: int) -> None:
        await self.call("emulator/write_memory",
                         {"addr": hex(self.sym[name]), "value": value, "width": 1})

    async def camera(self) -> tuple[int, int]:
        cx = (await self.read_long("Camera_X")) >> 16
        cy = (await self.read_long("Camera_Y")) >> 16
        return cx, cy

    async def fired(self) -> int:
        return await self.read_word("Canopy_Rec_Code")

    async def classify_and_maybe_clear(self, geom: dict) -> str | None:
        """None: not fired. 'benign_edge_column': the KNOWN, CONFIRMED-INVISIBLE act-edge
        artifact (see the module's derivation below) -- cleared so the campaign can keep
        looking for anything else. 'interesting': a fire that does NOT match that shape;
        left latched (with its whole shadow snapshot intact) for the caller to report.

        THE ARTIFACT, derived (not assumed) from the engine's own geometry, and confirmed
        by screenshot (`/tmp/oracle-frame-800.png` in this session's own repro): at the
        RIGHT-edge camera clamp, `Camera_X_Max = grid_w<<SECTION_SIZE_SHIFT - SCREEN_WIDTH`
        is ALWAYS a multiple of 8 (both operands are), so the clamp always lands with ZERO
        fine-scroll. The engine tracks `SCREEN_LAST_COL_MAX` (=40) columns as potentially
        visible to cover the general case where fine-scroll exposes a 41st partial column --
        correct in general, but AT THE EXACT CLAMP there is no fine-scroll, so only 40 whole
        columns are ever actually painted (cam_col..cam_col+39). The 41st tracked column
        (cam_col+40) sits exactly one tile past the act's last valid column whenever the grid
        width in tiles equals cam_col_max+40 -- i.e. it is OUTSIDE every section, never gets a
        legitimate write, and C1 fires on it FOREVER once the camera rests at the wall. Real,
        reproducible, permanent -- and INVISIBLE, because it is never one of the 40 columns the
        VDP actually reads at that exact scroll phase. This is checked GENERICALLY below (off
        the live Camera_X/Camera_X_Max and the parsed SCREEN_LAST_COL_MAX), not pinned to OJZ's
        particular numbers.
        """
        code = await self.fired()
        if code == 0:
            return None
        if code not in (1, 4):
            return "interesting"
        want = await self.read_word("Canopy_Rec_Want")
        got = await self.read_word("Canopy_Rec_Got")
        cam_x = (await self.read_long("Camera_X")) >> 16
        cam_x_max = await self.read_word("Camera_X_Max")
        # The phantom column: cam_col_max + SCREEN_LAST_COL_MAX. Derived from the LIVE
        # Camera_X_Max, never pinned to OJZ's numbers -- it happens to equal grid_w<<8
        # (the act's own tile width) but is computed the same way for any act.
        edge_col = (cam_x_max >> 3) + geom["SCREEN_LAST_COL_MAX"]
        benign = False
        if code == 1:
            idx = await self.read_word("Canopy_Rec_Idx")
            # C1: the tracked column IS the phantom one, and the camera is pinned at the
            # exact clamp (so fine-scroll is 0 and that column is never actually painted;
            # proven by screenshot in this session -- see the module docstring).
            benign = (cam_x == cam_x_max and want == edge_col
                      and idx == (edge_col % geom["PLANE_H_CELLS"]))
        else:
            # C4: a row write's anchor R fell exactly one short of the phantom column,
            # i.e. it correctly stopped at the act's last VALID tile (edge_col - 1)
            # instead of reaching for a column that does not exist. Same root cause,
            # the row-anchor predicate's mirror of C1's column-identity check.
            benign = (cam_x == cam_x_max and got == edge_col - 1)
        if benign:
            print(f"      (classified: KNOWN benign act-edge artifact, code {code} -- camera "
                  f"pinned at Camera_X_Max={cam_x_max}, the tracked/required column {edge_col} "
                  f"is one past the act's last valid tile and is structurally never painted at "
                  f"zero fine-scroll (screenshot-confirmed in this session). Clearing the latch "
                  f"and warping back to mid-level to continue the search -- real physics has no "
                  f"wall at this edge and Sonic sails past it into a long freefall drift, which "
                  f"would otherwise burn the whole run's budget recovering from a spot already "
                  f"fully characterised.)")
            await self.write_word("Canopy_Rec_Code", 0)
            await self.write_word("Canopy_Pend_Code", 0)
            await self.write_word("Canopy_Pend_Idx", 0)
            await self.write_word("Canopy_Pend_Age", 0)
            self.benign_edge_fires += 1
            await self.warp(3000, 300)
            return "benign_edge_column"
        return "interesting"

    def note_position(self, cx: int, cy: int) -> None:
        self.min_x = cx if self.min_x is None else min(self.min_x, cx)
        self.max_x = cx if self.max_x is None else max(self.max_x, cx)
        self.min_y = cy if self.min_y is None else min(self.min_y, cy)
        self.max_y = cy if self.max_y is None else max(self.max_y, cy)
        self.sections_visited.add((cx >> 11, cy >> 11))  # SECTION_SIZE_SHIFT = 11 (2048 px)

    async def chunk(self, phase: str, rows: list[dict], frames: int) -> bool:
        """Run one play_input chunk (<= MAX_CHUNK), release, check the latch. Returns
        True if the machine has fired (caller should stop immediately)."""
        assert frames <= MAX_CHUNK, f"{frames} exceeds one server call's ceiling"
        await self.call("emulator/play_input", {"rows": rows, "maxFrames": frames}, timeout=120.0)
        await self.call("emulator/release_all", {})
        self.frames_driven += frames
        cx, cy = await self.camera()
        self.note_position(cx, cy)
        code = await self.fired()
        elapsed = time.monotonic() - self.t0
        line = (f"  [{phase}] +{frames}f (total {self.frames_driven}f, {elapsed:6.1f}s wall)  "
                f"cam=({cx},{cy}) sec=({cx >> 11},{cy >> 11})  canopy_code={code}")
        print(line)
        self.log.append(line)
        if code == 0:
            return False
        verdict = await self.classify_and_maybe_clear(self.geom)
        return verdict == "interesting"

    async def run_phase(self, name: str, total: int, rows_fn, chunk_size: int = MAX_CHUNK) -> bool:
        """Split `total` frames into <= chunk_size pieces, calling `rows_fn(chunk_len)` for
        each piece's rows. Returns True on a fire (caller must stop)."""
        remaining = total
        while remaining > 0:
            n = min(chunk_size, remaining)
            if await self.chunk(name, rows_fn(n), n):
                return True
            remaining -= n
        return False

    async def warp(self, x: int, y: int) -> None:
        await self.write_word("Warp_Req_X", x)
        await self.write_word("Warp_Req_Y", y)
        await self.write_byte("Warp_Req_Flag", 1)
        for _ in range(120):
            await self.call("emulator/run_frames", {"frames": 1})
            r = await self.call("emulator/read_memory",
                                {"addr": hex(self.sym["Warp_Req_Flag"]), "len": 1})
            v = int(str(r["bytes"]).removeprefix("0x").removeprefix("0X"), 16)
            if v == 0:
                self.frames_driven += 1
                return
            self.frames_driven += 1
        raise SetupError(f"Warp_Req_Flag never cleared warping to ({x},{y})")

    async def enter_fly(self) -> None:
        cur = await self.call("emulator/read_memory", {"addr": hex(self.sym["Cheat_Flags"]), "len": 1})
        bit = cheat_debug_fly_bit()
        cur_v = int(str(cur["bytes"]).removeprefix("0x").removeprefix("0X"), 16)
        await self.call("emulator/write_memory",
                         {"addr": hex(self.sym["Cheat_Flags"]), "value": cur_v | bit, "width": 1})
        # B is excluded from the jump mask while the cheat is armed (see module docstring),
        # so B here is unambiguously the fly toggle, not a jump. Edge-triggered: press+release.
        await self.call("emulator/play_input", {"rows": [{"start": 0, "end": 2, "buttons": ["b"]}],
                                                 "maxFrames": 2})
        await self.call("emulator/release_all", {})
        await self.call("emulator/run_frames", {"frames": 2})
        self.frames_driven += 4

    async def exit_fly(self) -> None:
        await self.call("emulator/play_input", {"rows": [{"start": 0, "end": 2, "buttons": ["b"]}],
                                                 "maxFrames": 2})
        await self.call("emulator/release_all", {})
        await self.call("emulator/run_frames", {"frames": 2})
        self.frames_driven += 4


async def body(sock: str, rom: str, lst: str, blob: bytes, args) -> tuple[bool, Driver, dict]:
    sym = parse_lst(lst)
    needed = ["Camera_X", "Camera_Y", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag",
              "Cheat_Flags", "Canopy_Rec_Code", "Canopy_Hits", "Canopy_Cost", "Canopy_Cost_Peak",
              "Canopy_Pend_Code", "Canopy_Pend_Idx", "Canopy_Pend_Age", "Logic_Tick",
              "Canopy_Halt"] + cr.SCALARS + cr.LONGS + cr.ARRAYS + cr.SNAPS + cr.LIVE
    missing = sorted(set(n for n in needed if n not in sym))
    if missing:
        raise SetupError(f"symbols did not resolve in {lst}: {missing[:5]}"
                         f"{' ...' if len(missing) > 5 else ''}")

    b = BusClient(sock, client_id="canopy_exercise", client_name="canopy_gap_exercise")
    await b.connect()
    geom = cr.geometry()
    d = Driver(b, sym, {}, geom)

    st = await d.call("emulator/status", {})
    if st["romBytes"] != len(blob):
        raise SetupError(f"server serves {st['romBytes']} bytes, {rom} is {len(blob)} -- "
                         f"refusing to drive a different ROM")
    print(f"ROM {rom}  {len(blob)} bytes crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")
    print(f"server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")

    if args.arm:
        await d.write_word("Canopy_Halt", 1)
        print("  Canopy_Halt ARMED (informational only -- this driver polls Canopy_Rec_Code "
              "itself every chunk and does not rely on the CPU halting)")

    await d.call("emulator/run_frames", {"frames": args.settle})
    d.frames_driven += args.settle
    cx0, cy0 = await d.camera()
    d.note_position(cx0, cy0)
    print(f"  settled {args.settle}f -> camera ({cx0},{cy0})  Logic_Tick pre-check...")
    t0 = await d.read_long("Logic_Tick")
    await d.call("emulator/run_frames", {"frames": 2})
    t1 = await d.read_long("Logic_Tick")
    if t1 <= t0:
        raise SetupError(f"Logic_Tick did not advance across a settle ({t0} -> {t1}) -- "
                         f"the machine is not running the level")
    d.frames_driven += 2
    print(f"  Logic_Tick {t0} -> {t1}: alive")

    fired = False

    # ---- Phase 1: long RIGHT run with real jumps ----
    # SMALL chunk_size deliberately: the KNOWN benign edge artifact (see
    # classify_and_maybe_clear) re-latches within a handful of frames of being cleared
    # whenever the camera is STILL sitting at the wall (e.g. the player has not yet
    # built up speed away from it), and a coarse chunk boundary would leave that stale
    # re-latch sitting unexamined -- and misread as fresh -- until the chunk ends.
    if not fired:
        fired = await d.run_phase(
            "P1-right", args.p1_frames,
            lambda n: hold_with_pulses(n, ["right"], JUMP_BUTTON, period=97, pulse_len=8),
            chunk_size=150)

    # ---- Phase 2: long LEFT run back, crossing every boundary in reverse ----
    if not fired:
        fired = await d.run_phase(
            "P2-left", args.p2_frames,
            lambda n: hold_with_pulses(n, ["left"], JUMP_BUTTON, period=113, pulse_len=8),
            chunk_size=150)

    # ---- Phase 3: rapid reversals straddling EVERY internal section boundary ----
    # OJZ act 1 is a 3x3 grid of 2048px sections: internal seams sit at world 2048 and
    # 4096 on both axes. Only the X seams are reachable by ground play without fly (the Y
    # seams need vertical fly, covered by phase 4); flip across both X seams here.
    if not fired:
        for seam in (2048, 4096):
            if fired:
                break
            await d.warp(seam - 96, cy0)
            for i in range(args.p3_reversals):
                direction = "right" if i % 2 == 0 else "left"
                if await d.chunk(f"P3-flip@{seam}",
                                  [{"start": 0, "end": args.p3_leg, "buttons": [direction]}],
                                  args.p3_leg):
                    fired = True
                    break

    # ---- Phase 4: debug-fly sweep, BOTH axes, over the WHOLE map -- fly avoids the
    # falling-into-the-void behaviour real physics has past the right/bottom edges (see
    # this parcel's notes: Sonic sails past Camera_X_Max into freefall with no wall there,
    # which is a separate, unrelated defect from the canopy gap and is not chased here),
    # so this is the only phase that can cleanly visit every corner of the grid.
    if not fired:
        await d.enter_fly()
        remaining = args.p4_frames
        leg = min(args.p4_leg, MAX_CHUNK)
        i = 0
        while remaining > 0 and not fired:
            n = min(leg, remaining)
            vert = "down" if (i % 2 == 0) else "up"
            horiz = "right" if (i // 3) % 2 == 0 else "left"   # slower horizontal flip
                                                                # than vertical, so both
                                                                # axes sweep independently
            fired = await d.chunk("P4-fly", [{"start": 0, "end": n, "buttons": [vert, horiz]}], n)
            remaining -= n
            i += 1
        await d.exit_fly()

    # ---- Phase 5: warp-mailbox hops, each followed by MOVING play, not a static settle ----
    if not fired:
        cx, cy = await d.camera()
        # Sections span 0..3*2048=6144 on each axis (3x3 grid). Hop the diagonal and the
        # anti-diagonal, plus a couple of pure-axis hops, then return to spawn.
        targets = [(5800, 5800), (300, 5800), (5800, 300), (3000, 3000), (256, 256)]
        for (tx, ty) in targets:
            if fired:
                break
            await d.warp(tx, ty)
            afterX, afterY = await d.camera()
            d.note_position(afterX, afterY)
            code_now = await d.fired()
            print(f"  [P5-warp] requested ({tx},{ty}) -> camera ({afterX},{afterY})  "
                  f"canopy_code={code_now}")
            if code_now:
                verdict = await d.classify_and_maybe_clear(geom)
                if verdict == "interesting":
                    fired = True
                    break
            # Move for real immediately after landing -- the post-warp redraw meeting a
            # moving camera is the untested combination the ladder's own comments flag.
            fired = await d.run_phase(
                "P5-postwarp", args.p5_leg,
                lambda n: hold_with_pulses(n, ["right"], JUMP_BUTTON, period=97, pulse_len=8),
                chunk_size=150)

    # ---- Phase 6: one more long RIGHT run to end on fresh ground ----
    if not fired:
        fired = await d.run_phase(
            "P6-right", args.p6_frames,
            lambda n: hold_with_pulses(n, ["right"], JUMP_BUTTON, period=89, pulse_len=8),
            chunk_size=150)

    rec = await cr.read_from_bus(b, sym, None)
    await b.close()
    return fired, d, rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.debug.bin"))
    ap.add_argument("--lst", default=None)
    ap.add_argument("--settle", type=int, default=SETTLE_FRAMES)
    ap.add_argument("--save", help="write the full canopy record (fired or not) to this JSON")
    ap.add_argument("--arm", action="store_true",
                    help="also set Canopy_Halt (informational; this driver polls regardless)")
    ap.add_argument("--p1-frames", type=int, default=2400)   # OJZ act1's playable width is
    ap.add_argument("--p2-frames", type=int, default=2400)   # short (~550f spawn->right wall
                                                             # at full speed) -- these budgets
                                                             # cross it several times over with
                                                             # room to spare, without burning
                                                             # wall-clock sitting at a clamp
    ap.add_argument("--p3-reversals", type=int, default=24)
    ap.add_argument("--p3-leg", type=int, default=30)
    ap.add_argument("--p4-frames", type=int, default=9000)   # vertical sweep gets the most
                                                             # budget: it is the axis the
                                                             # d-45/08-30 entries flagged as
                                                             # under-exercised historically
    ap.add_argument("--p4-leg", type=int, default=450)
    ap.add_argument("--p5-leg", type=int, default=600)
    ap.add_argument("--p6-frames", type=int, default=2400)
    args = ap.parse_args()

    rom = os.path.abspath(args.rom)
    lst = os.path.abspath(args.lst) if args.lst else rom[:-4] + ".lst"
    try:
        blob = open(rom, "rb").read()
    except OSError as e:
        print(f"canopy_gap_exercise: SETUP -- {e}", file=sys.stderr)
        return 2
    if not os.path.exists(lst):
        print(f"canopy_gap_exercise: SETUP -- no listing at {lst}", file=sys.stderr)
        return 2

    inst = AetherInstance(rom, symbols=lst)
    try:
        sock = inst.start()
    except Exception as e:                       # noqa: BLE001 -- spawn failure is setup
        print(f"canopy_gap_exercise: SETUP -- {e}", file=sys.stderr)
        return 2
    try:
        fired, d, rec = asyncio.run(body(sock, rom, lst, blob, args))
    except SetupError as e:
        print(f"canopy_gap_exercise: SETUP -- {e}", file=sys.stderr)
        return 2
    except asyncio.TimeoutError:
        print("canopy_gap_exercise: SETUP -- an RPC exceeded its deadline (emulator wedge)",
              file=sys.stderr)
        return 2
    finally:
        inst.reap()

    elapsed = time.monotonic() - d.t0
    print()
    print(f"COVERAGE: {d.frames_driven} frames driven ({d.frames_driven / 60:.1f}s of game "
          f"time at 60fps) in {elapsed:.1f}s wall clock")
    print(f"  camera X range {d.min_x}..{d.max_x} px, Y range {d.min_y}..{d.max_y} px")
    print(f"  world sections (col,row) visited: {sorted(d.sections_visited)}")
    print(f"  (OJZ act 1 is a 3x3 grid of 2048px sections, cols/rows 0..2, spawn at (256,256))")
    print(f"  KNOWN benign act-edge artifact fired and was cleared {d.benign_edge_fires} time(s) "
          f"during this run (see classify_and_maybe_clear's docstring) -- not counted below")

    g = cr.geometry()
    if args.save:
        import json
        json.dump({**rec, "_geometry": g}, open(args.save, "w"), indent=1)
        print(f"  wrote {args.save}")

    print()
    for line in cr.decode(rec, g["PLANE_H_CELLS"], g["PLANE_V_CELLS"],
                          g["SCREEN_LAST_COL_MAX"], g["SCREEN_LAST_ROW_MAX"],
                          g["CANOPY_PERSIST_FRAMES"]):
        print(line)

    if fired:
        print()
        print("RESULT: the instrument FIRED during this campaign. See the decoded record above.")
    else:
        print()
        print("RESULT: the instrument did NOT fire during this campaign. This is coverage, not "
              "a clean bill -- see canopy_record.py's own caveat about CANOPY_PERSIST_FRAMES.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
