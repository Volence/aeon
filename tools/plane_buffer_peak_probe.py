#!/usr/bin/env python3
"""Plane_Buffer high-water mark across REGION CROSSINGS and at the camera's speed cap.

WHY THIS EXISTS BESIDE tools/plane_buffer_headroom_probe.py, AND DOES NOT REPLACE IT.

`plane_buffer_headroom_probe.py` (d2c3dff0, 2026-09-08) sampled `Plane_Buffer_Ptr` by
STOPPING at `VInt_DrawLevel`'s entry once per iteration. Its own commit message names what
it did not cover: "only horizontal motion was driven. Vertical and diagonal motion, BG
column entries, section transitions and teleports are unmeasured."  Two defects follow from
the METHOD, not from the input script, and they are why this is a second instrument:

  * A SAMPLED PEAK IS A LOWER BOUND.  The loop is `play_input(1 frame)` then
    `run_to(VInt_DrawLevel, maxFrames: 3)`.  Each `run_to` consumes real frames, so the pad
    is NOT held on the frames it skips past and those frames' occupancy is never read.  The
    instrument therefore samples roughly every other frame of a walk that is not actually
    continuous.
  * `run_to` MISSES ARE COUNTED AND DISCARDED.  A frame whose stop was not reached is
    tallied as a miss; a peak that occurred in that frame is simply lost.

This probe reads a LATCH instead: `Plane_Buffer_Peak` (engine/ram.emp, DEBUG shape only) is
written by `VInt_DrawLevel` itself, at its own entry, on EVERY frame — including frames this
script never stops on.  The walk is then a continuous frame-by-frame hold (the
`parallax_crossing_gate` form, `{"rows": [{"start": 0, "end": 1, ...}]}`, verified to advance
exactly one frame), and the peak is read out of RAM afterwards.  Nothing is sampled, so
nothing can be missed.

WHAT IS DRIVEN, and why these routes.

  rest        control.  A non-zero peak at rest would mean the streamer runs with a still
              camera, and every moving figure below would need re-reading against it.
  right       the section-0 | section-1 edge at x = 2048 (region rows 0 -> 1).
  night_in    the night region's LEFT edge at x = OJZ_NIGHT_X0 = 3400 (rows 1 -> 9) — OFF
              the section grid.
  night_out   the night region's RIGHT edge at x = OJZ_NIGHT_X1 + 1 = 4800 (rows 9 -> 2).
  left        the same x = 2048 edge walked BACKWARDS, over ground already drawn.
  down        the fastest vertical traversal the engine allows.  In the DEBUG shape the
              player boots into free flight (Player_Init tail-calls Player_DebugEnter when
              CHEAT_DEBUG_FLY is armed), and `Player_DebugMove` steps PLAYER_DEBUG_FLY_SPEED
              = 16 px/frame — which is CAM_MAX_Y_STEP, the camera's own per-frame ceiling.
              A physics fall cannot beat that: the camera clamps at 16 px/frame however fast
              the player falls, so free flight IS the worst case and a shaft would be a
              slower rehearsal of it.  Crosses the y = 2048 section line.
  diag        down + right together, each axis at the same 16 px/frame cap.  THIS IS THE
              CONSTRUCTED WORST CASE, and the reason the brief's "a fall through a shaft"
              framing is not the ceiling: a fall streams rows only, while this streams the
              right column edge and the bottom row edge in the SAME frame, which is the one
              geometry where `Section_UpdateStreaming`'s four loops all have work.
  diag_cross  the same diagonal aimed so that it crosses the x = 2048 and y = 2048 section
              lines in the same walk.

THE THREE STRESS ROUTES, and why steady-state motion is not on its own a ceiling.

The four streaming loops in `Section_UpdateStreaming` advance from `Section_*_Written`
towards what the camera needs, so in steady state a 16 px/frame camera adds two tile
columns and two tile rows per frame and nothing else.  That is a DERIVED figure, and the
diagonals above should hit it exactly.  What it does not cover is a BACKLOG: each loop also
stops when the tile-cache fill left the next column half-written (`Cache_Fill_Resume_Col` /
`Cache_Fill_RowResume_Row`), and a loop that has been blocked for k frames can advance k + 2
columns in the frame the fill completes — up to the reservation guard, which is far above
the steady-state figure.  Three routes aim at that:

  shake       reverses the diagonal every few frames.  A reversal is what invalidates the
              tile-cache fill direction, so this is the cheapest way to keep a fill
              perpetually incomplete while the camera keeps demanding columns.
  diag_long   the plain diagonal held three times as long, so a backlog that needs many
              frames to build has them.
  warp_diag   teleports through the DEBUG warp mailbox and then holds the diagonal.
              `Section_RedrawPlanes` — the full 64-column repaint a teleport triggers —
              writes STRAIGHT to VDP_CTRL/VDP_DATA and never touches Plane_Buffer, so the
              repaint itself cannot show up here; what this route tests is the frames
              AFTER it, where the written-markers and the cache have both just been reset.

Every scenario zeroes the latch first (a poke), holds for its frames, then reads it back.

Exit 0 measured · 2 setup error (nothing was measured).  There is no exit 1: this is an
INSTRUMENT, not a gate — it reports a number and does not know what number is acceptable.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path  # noqa: E402
add_client_path()

from aether import BusClient                                        # noqa: E402
from aether_instance import (AetherInstance, SpawnError,            # noqa: E402
                             WrongServerError, read_bytes)
from raster_cost_probe import parse_lst                             # noqa: E402

BOOT_MAX_FRAMES = 600
ALIGN_MAX_FRAMES = 8
WARP_ACK_FRAMES = 120   # the budget tools/warp_mailbox_gate.py uses against the same mailbox


class SetupError(Exception):
    """The measurement could not be made. Exit 2 — never a number."""


def emp_const(rel: str, name: str) -> int:
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        raise SetupError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def rd(b, addr: int, n: int) -> int:
    return int(await read_bytes(b, addr, n), 16)


async def run_to_sym(b, sym, name: str, max_frames: int) -> None:
    r = await _c(b, "emulator/run_to", {"addr": hex(sym[name]), "maxFrames": max_frames})
    if not r.get("reached"):
        raise SetupError(f"run_to {name} (${sym[name]:06X}) never reached it within "
                         f"{max_frames} frames; stopped at pc={r.get('pc')} — no reading "
                         "below would be of the state this probe names")


async def boot_at(b, sym, lst: str, x: int, y: int) -> None:
    """The DEBUG boot-position mailbox. X, then Y, then the FLAG last — the write order IS
    the protocol (games/sonic4/test/ojz_scroll_test.emp). The mailbox is written at the
    init's first instruction because boot's 64 KB Work-RAM clear would zero an earlier poke."""
    await _c(b, "emulator/load_symbols", {"path": lst})
    await _c(b, "emulator/reset", {})
    await run_to_sym(b, sym, "GameState_OJZScroll_Init", BOOT_MAX_FRAMES)
    for nm, v, w in (("Boot_At_X", x, 2), ("Boot_At_Y", y, 2), ("Boot_At_Flag", 1, 1)):
        await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
    await run_to_sym(b, sym, "GameState_OJZScroll_Update", BOOT_MAX_FRAMES)


async def cam(b, sym) -> tuple[int, int]:
    return ((await rd(b, sym["Camera_X"], 4)) >> 16,
            (await rd(b, sym["Camera_Y"], 4)) >> 16)


async def warp(b, sym, x: int, y: int) -> None:
    """The DEBUG warp mailbox (games/sonic4/config/ram.emp). X, Y, then the FLAG last — the
    same write order the boot mailbox uses, and for the same reason."""
    for nm, v, w in (("Warp_Req_X", x, 2), ("Warp_Req_Y", y, 2), ("Warp_Req_Flag", 1, 1)):
        await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
    # POLL for the ack, do not assume a fixed number of frames covers it — the same 120-frame
    # budget tools/warp_mailbox_gate.py uses against the same mailbox.
    for _ in range(WARP_ACK_FRAMES):
        await _c(b, "emulator/run_frames", {"frames": 1})
        if await rd(b, sym["Warp_Req_Flag"], 1) == 0:
            return
    raise SetupError(f"Warp_Req_Flag never cleared in {WARP_ACK_FRAMES} frames — the "
                     "teleport did not happen and this route would be the plain diagonal "
                     "under another name")


async def scenario(b, sym, lst, size, name, boot, buttons, frames, settle,
                   flip=0, warp_to=None) -> dict:
    """One walk. Boot fresh, let the level settle, ZERO the latch, hold, read it back.

    The latch is zeroed AFTER the settle on purpose: the boot itself does a full
    `Section_RedrawPlanes` (64 columns), which is a one-off that no in-play frame repeats,
    and folding it into a walk's peak would report the boot's cost as the walk's.  The boot
    peak is measured separately, in its own row, so it is reported rather than hidden.
    """
    await boot_at(b, sym, lst, *boot)
    await _c(b, "emulator/run_frames", {"frames": settle})
    if warp_to:
        await warp(b, sym, *warp_to)
    await run_to_sym(b, sym, "GameState_OJZScroll_Update", ALIGN_MAX_FRAMES)
    boot_peak = await rd(b, sym["Plane_Buffer_Peak"], 2)

    await _c(b, "emulator/write_memory",
             {"addr": hex(sym["Plane_Buffer_Peak"]), "value": 0, "width": 2})
    if await rd(b, sym["Plane_Buffer_Peak"], 2) != 0:
        raise SetupError(f"{name}: the latch did not read back as 0 after the poke — this "
                         "shape has no writable Plane_Buffer_Peak and every figure below "
                         "would be the previous scenario's")

    cam0 = await cam(b, sym)
    trace, peak = [], 0
    t0 = await rd(b, sym["Logic_Tick"], 4)
    # `flip` reverses the held direction every `flip` frames. OPPOSITE, not orthogonal: the
    # tile-cache fill is directional, so left+up is what invalidates a right+down fill.
    opposite = {"right": "left", "left": "right", "down": "up", "up": "down"}
    for i in range(1, frames + 1):
        held = buttons
        if flip and (i - 1) // flip % 2:
            held = [opposite[x] for x in buttons]
        r = await _c(b, "emulator/play_input",
                     {"rows": [{"start": 0, "end": 1, "buttons": held, "port": 0}]}) \
            if held else await _c(b, "emulator/run_frames", {"frames": 1})
        if buttons and int(r.get("frames", -1)) != 1:
            raise SetupError(f"{name}: play_input advanced {r.get('frames')} frames, wanted "
                             "1 — the hold is not frame-by-frame and the walk's geometry is "
                             "not what this scenario claims")
        v = await rd(b, sym["Plane_Buffer_Peak"], 2)
        if v > peak:
            peak = v
            trace.append({"frame": i, "peak": v, "cam": list(await cam(b, sym))})
        if i == frames // 2:
            cam_mid = await cam(b, sym)
    cam1 = await cam(b, sym)
    t1 = await rd(b, sym["Logic_Tick"], 4)
    await _c(b, "emulator/release_all", {})

    # STILL ALIVE?  RAM that stopped changing because the 68000 parked in the error handler
    # reads exactly like a walk that simply never got busier.  A dead machine's peak is not
    # a measurement of anything, and the one thing it must never be rendered as is a low
    # number.
    if t1 <= t0:
        raise SetupError(f"{name}: Logic_Tick did not advance ({t0} -> {t1}) across "
                         f"{frames} frames — the 68000 is parked (the error handler?) and "
                         "the peak read above is of a machine that stopped running")
    # A REVERSING route can legitimately end where it started, so "did the camera move" is
    # asked of the MIDPOINT as well as the end. Asking it only of the endpoints would make
    # `shake` unfalsifiable — a route that never moved at all would look identical.
    if buttons and cam0 == cam1 and cam0 == cam_mid:
        raise SetupError(f"{name}: the camera never moved from {cam0} while holding "
                         f"{buttons} for {frames} frames (checked at the midpoint too) — "
                         "nothing was traversed, so the peak is the at-rest peak under "
                         "another name")
    return {"name": name, "boot": list(boot), "buttons": buttons, "frames": frames,
            "flip": flip, "warp_to": list(warp_to) if warp_to else None,
            "boot_peak": boot_peak, "peak": peak, "cam0": list(cam0),
            "cam_mid": list(cam_mid), "cam1": list(cam1),
            "ticks": [t0, t1], "trace": trace}


async def main_async(args) -> int:
    size = 1 << emp_const("engine/system/constants.emp", "SECTION_SIZE_SHIFT")
    pbs = emp_const("engine/system/constants.emp", "PLANE_BUFFER_SIZE")
    ph = emp_const("engine/system/constants.emp", "PLANE_H_CELLS")
    pv = emp_const("engine/system/constants.emp", "PLANE_V_CELLS")
    fly = emp_const("games/sonic4/player/player_common.emp", "PLAYER_DEBUG_FLY_SPEED")
    cap = emp_const("engine/system/constants.emp", "CAM_MAX_Y_STEP")

    act = (AEON / "games/sonic4/data/levels/ojz/act1/act_descriptor.emp").read_text()
    nx0 = int(re.search(r"const OJZ_NIGHT_X0\s*=\s*(\d+)", act).group(1))
    nx1 = int(re.search(r"const OJZ_NIGHT_X1\s*=\s*(\d+)", act).group(1))

    sym = parse_lst(args.lst)
    for need in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update", "Boot_At_X",
                 "Boot_At_Y", "Boot_At_Flag", "Camera_X", "Camera_Y", "Logic_Tick",
                 "Plane_Buffer_Ptr", "Plane_Buffer"):
        if need not in sym:
            raise SetupError(f"symbol {need} is not in {args.lst} — wrong ROM shape? "
                             "(this probe needs the sonic4 DEBUG listing)")
    if "Plane_Buffer_Peak" not in sym:
        raise SetupError(
            f"Plane_Buffer_Peak is not in {args.lst}. The latch is DEBUG-only by design; a "
            "release listing legitimately lacks it, and so does a tree the latch has not "
            "landed in. Either way NOTHING was measured — this is not a zero peak.")
    if sym["Plane_Buffer_Ptr"] - sym["Plane_Buffer"] != pbs:
        raise SetupError(
            f"the listing puts Plane_Buffer_Ptr {sym['Plane_Buffer_Ptr'] - sym['Plane_Buffer']} "
            f"bytes above Plane_Buffer, but PLANE_BUFFER_SIZE is {pbs} — the source and the "
            "ROM disagree about the buffer, so no headroom figure derived below is sound")

    # The streamer's OWN self-caps, restated from engine/level/section.emp's four loops.  A
    # column entry is 2 headers (8 B) + PLANE_V_CELLS words; a row entry is 1 header (4 B) +
    # PLANE_H_CELLS words.  Each loop stops when Plane_Buffer_Ptr EXCEEDS
    # PLANE_BUFFER_SIZE - 2 - <its own entry size>, so the last admitted entry can still
    # carry the pointer to one byte short of the buffer.
    col_entry, row_entry = 8 + pv * 2, 4 + ph * 2
    caps = {"col_guard": pbs - 2 - col_entry, "row_guard": pbs - 2 - row_entry,
            "col_entry": col_entry, "row_entry": row_entry,
            "analytic_max": max(pbs - 2 - col_entry + col_entry,
                                pbs - 2 - row_entry + row_entry)}

    # THE ROUTES.  Every boot point is derived from the act's own numbers, never typed:
    # start an eighth of a section short of each edge so the walk is short and unambiguous.
    eighth = size // 8
    y_mid = size // 2
    #  name, boot, buttons, frames, flip period (0 = hold), warp destination
    routes = [
        ("rest",       (size - eighth, y_mid),      [],                args.frames // 2, 0, None),
        ("right",      (size - eighth, y_mid),      ["right"],         args.frames, 0, None),
        ("left",       (size + eighth, y_mid),      ["left"],          args.frames, 0, None),
        ("night_in",   (nx0 - eighth, y_mid),       ["right"],         args.frames, 0, None),
        ("night_out",  (nx1 + 1 - eighth, y_mid),   ["right"],         args.frames, 0, None),
        ("down",       (size // 2, size - eighth),  ["down"],          args.frames, 0, None),
        ("up",         (size // 2, size + eighth),  ["up"],            args.frames, 0, None),
        ("diag",       (size // 2, size // 2),      ["down", "right"], args.frames, 0, None),
        ("diag_cross", (size - eighth, size - eighth), ["down", "right"], args.frames, 0, None),
        # -- the three stress routes (see the header) --
        ("shake2",     (size, size),                ["down", "right"], args.frames, 2, None),
        ("shake5",     (size, size),                ["down", "right"], args.frames, 5, None),
        ("shake17",    (size, size),                ["down", "right"], args.frames, 17, None),
        ("diag_long",  (size // 2, size // 2),      ["down", "right"], args.frames * 3, 0, None),
        ("warp_diag",  (size // 2, size // 2),      ["down", "right"], args.frames, 0,
                       (size * 2 + eighth, size * 2 + eighth)),
    ]

    inst = AetherInstance(args.rom)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise SetupError(str(e)) from e
    b = BusClient(sock, client_id="pbpeak", client_name="plane_buffer_peak_probe")
    try:
        await b.connect()
        for m in ("emulator/run_to", "emulator/play_input", "emulator/run_frames",
                  "emulator/read_memory", "emulator/write_memory", "emulator/release_all"):
            if not b.supports(m):
                raise SetupError(f"the server does not advertise `{m}`")
        for need in ("Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag"):
            if need not in sym:
                raise SetupError(f"symbol {need} is not in {args.lst} — the warp route "
                                 "cannot be driven and would silently become a second "
                                 "plain diagonal")
        rows = []
        for name, boot, buttons, frames, flip, warp_to in routes:
            # A route that could not be driven is recorded as an ERROR ROW and excluded from
            # the worst-case pick. It is NEVER rendered as a peak of 0: "the walk did not
            # happen" and "the walk was quiet" are opposite findings and a 0 would read as
            # the second. The other routes still measured what they measured, so the run
            # continues rather than throwing thirteen good walks away with one bad one.
            try:
                rows.append(await scenario(b, sym, args.lst, size, name, boot, buttons,
                                           frames, args.settle, flip, warp_to))
            except SetupError as e:
                rows.append({"name": name, "boot": list(boot), "buttons": buttons,
                             "frames": frames, "flip": flip,
                             "warp_to": list(warp_to) if warp_to else None,
                             "error": str(e), "peak": None})
    finally:
        await b.close()
        inst.reap()

    errs = [r for r in rows if r.get("error")]
    good = [r for r in rows if r.get("peak") is not None]
    if not good:
        raise SetupError("every route failed to drive — nothing was measured:\n  "
                         + "\n  ".join(f"{r['name']}: {r['error']}" for r in errs))
    worst = max(good, key=lambda r: r["peak"])
    report = {
        "rom": args.rom, "lst": args.lst,
        "constants": {"PLANE_BUFFER_SIZE": pbs, "PLANE_H_CELLS": ph, "PLANE_V_CELLS": pv,
                      "SECTION_PX": size, "PLAYER_DEBUG_FLY_SPEED": fly,
                      "CAM_MAX_Y_STEP": cap,
                      "OJZ_NIGHT_X0": nx0, "OJZ_NIGHT_X1": nx1},
        "caps": caps, "scenarios": rows,
        "routes_measured": len(good), "routes_total": len(rows),
        "could_not_run": [{"name": r["name"], "error": r["error"]} for r in errs],
        "worst": {"name": worst["name"], "peak": worst["peak"],
                  "headroom": pbs - worst["peak"]},
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"plane_buffer_peak_probe: {args.rom}")
        print(f"  PLANE_BUFFER_SIZE {pbs} B; a column entry is {col_entry} B and its loop "
              f"stops above {caps['col_guard']} B;")
        print(f"  a row entry is {row_entry} B and its loop stops above "
              f"{caps['row_guard']} B. Free flight is {fly} px/frame on each axis, "
              f"= CAM_MAX_Y_STEP {cap}.")
        print(f"  {'scenario':<11} {'boot':>13} {'buttons':<14} {'f':>4} {'flip':>4} "
              f"{'bootpk':>7} {'PEAK':>6} {'headroom':>9}  camera")
        for r in rows:
            if r.get("error"):
                print(f"  {r['name']:<11} {str(tuple(r['boot'])):>13} "
                      f"{'+'.join(r['buttons']) or '-':<14} {r['frames']:>4} "
                      f"{r['flip'] or '-':>4} {'COULD NOT RUN — NOT a peak of 0':>40}")
                continue
            print(f"  {r['name']:<11} {str(tuple(r['boot'])):>13} "
                  f"{'+'.join(r['buttons']) or '-':<14} {r['frames']:>4} "
                  f"{r['flip'] or '-':>4} {r['boot_peak']:>7} "
                  f"{r['peak']:>6} {pbs - r['peak']:>9}  "
                  f"{tuple(r['cam0'])} -> {tuple(r['cam1'])}")
        for r in errs:
            print(f"  !! {r['name']} COULD NOT RUN: {r['error']}")
        print(f"  {len(good)} of {len(rows)} routes measured"
              + (f"; {len(errs)} COULD NOT RUN (see above) — the worst below is the worst "
                 "of what RAN, not of what was asked for" if errs else ""))
        print(f"  WORST: {worst['name']} at {worst['peak']} B of {pbs} B "
              f"({100.0 * worst['peak'] / pbs:.1f}%), headroom {pbs - worst['peak']} B")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--frames", type=int, default=200, help="frames held per scenario")
    ap.add_argument("--settle", type=int, default=30, help="frames after boot before the latch is zeroed")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        return asyncio.run(main_async(args))
    except SetupError as e:
        print(f"SETUP ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
