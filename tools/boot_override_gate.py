#!/usr/bin/env python3
"""boot_override_gate — does the DEBUG boot-position override put the FIRST
displayed frame at the editor cursor, with the same streaming the warp produces?

WHAT IS BEING ASSERTED, AND WHY IT IS A DIFFERENT QUESTION FROM THE WARP'S.

`warp_mailbox_gate` asks "does a mid-play teleport land a coherent frame?". This
asks "does a BOOT land a coherent frame somewhere other than the authored start?",
which is a different mechanism with a different failure mode. The override does not
re-seed anything: it substitutes for the authored start at the point the level init
consumes it, so every streaming step below the hook (Section_Init, Player_BoundsInit,
Tile_Cache_Init, the synchronous plane fill, the parallax config select) runs once,
in its authored order, already aimed at the destination. The failure this gate exists
to catch is therefore NOT tearing-over-time but a HOOK IN THE WRONG PLACE: a consumer
that reads the authored start after the override wrote, or an override applied after
a consumer already latched the authored one. Both show up as "the boot streams the
wrong place", and both are visible in the very first displayed frame.

THE REFERENCE IS NOT DECLARED — IT IS THE WARP. There is no authored "correct
nametable" for an arbitrary cursor, and deriving one by walking (what warp_mailbox_gate
does) would re-litigate a question that gate already settled. The warp is proven
coherent AT THE SAME DESTINATION by that gate, so this one uses it directly: boot
normally, warp to (X,Y), settle — that is the reference. Then boot WITH the override
at the same (X,Y), settle the same budget, and the visible plane-A window must be
IDENTICAL. If the boot override streams somewhere else, or streams the right place
badly, it cannot match a warp that streamed it well.

THE VISIBLE WINDOW, NOT THE WHOLE PLANE, and for warp_mailbox_gate's reason: the
nametable is a 512x512 px ring behind a 320x224 view, so three quarters of it holds
whatever was last written there and is legitimately path-dependent. 41x29 cells covers
the view including both partial edge cells.

THE TIMING TRUTH THIS GATE ENCODES. Boot clears ALL 64KB of Work RAM
(engine/system/boot.emp `.clear_ram`), so the mailbox CANNOT be written at the
reset-paused machine — a pre-resume write is zeroed before the init can see it. The
supported client window is after that clear and before the init: `emulator/run_to`
GameState_OJZScroll_Init, write X/Y/flag, then continue. Every run below uses exactly
that sequence, so the gate is also the executable spec of the client procedure. (A
pre-resume write is not merely unsupported — run PRE proves it is silently ignored.)

THE RUNS (each a fresh oracle-aether process, each from reset):

    control   no write at all                -> the authored start, byte-for-byte today
    override  write at the init breakpoint   -> the destination, from the first frame
    warp      boot + mailbox warp there      -> the REFERENCE plane for `override`
    clamp     a request past the act edge    -> clamped AND published back
    poisonA   flag set, garbage X/Y          -> clamped, machine still alive
    poisonB   cells written, flag NOT set    -> boots authored (the flag is the gate)
    pre       cells written BEFORE resume    -> boots authored (the RAM clear ate them)

EXPECTATIONS ARE DERIVED, NEVER COPIED. The authored start comes out of the ROM's own
act descriptor; the clamp edges out of `grid_w/grid_h` and the two constants
Player_BoundsInit uses; the tile-cache window out of Tile_Cache_Init's arithmetic
against engine/system/constants.emp. Nothing here is a number lifted from a pin.

Exit 0 pass · 1 fail · 2 setup error (the measurement could not be made).
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, str(AEON / "tools"))

from aether import BusClient            # noqa: E402
from aether_instance import assert_rust_server  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

SERVER = "/home/volence/sonic_hacks/oracle-next/target/release/oracle-aether"
SOCK = f"/tmp/aeon_bootovr_{os.getpid()}.sock"   # short + per-process: AF_UNIX caps at 108

BOOT_MAX_FRAMES = 600        # ceiling for run_to(Init) / run_to(Update); the DEBUG shape
                             # boots straight into the OJZ scroll test, no buttons pressed
SETTLE = 30                  # the sample budget, identical for override and warp
PAINT_LAG = 2                # frames between the init's RETURN and the first fully painted
                             # frame. MEASURED, not assumed: the init enables the display
                             # through the VDP shadow, which the next VBlank flushes, so the
                             # frame in progress is still blanked and the one after it is the
                             # first the beam draws whole. Sampling earlier reads a black
                             # raster (probe: 1 colour at +0f and +1f, 5-9 from +2f on) and
                             # would make the colour control a lie either way.
ACK_MAX_FRAMES = 120         # the warp reference's ack poll ceiling

# THE DESTINATION. Diagonal and multi-section on both axes so a hook that only fixed one
# axis (or only the camera, or only the player) cannot pass: OJZ act 1 is a 3x3 grid of
# 2048 px sections and the authored start is in section (0,0), so this lands in (1,1) —
# a different section, hence a different parallax config, which is the second consumer.
DEST_X, DEST_Y = 2560, 2400

SCANLINE_START, SCANLINE_COUNT = 100, 8

# Sst field offsets — the listing's own equates would do, but parse_lst reads addresses
# only, and these two are the whole of what a placement check needs.
SST_X_POS, SST_Y_POS = 0x02, 0x06

# Sec record (engine/structs.emp `struct Sec`, sizeof 66 — pinned by an `ensure` in
# engine/level/section.emp because the generated grid data assumes it).
SEC_SIZE = 66
SEC_PARALLAX_CONFIG = 0x14
ACT_SEC_GRID_PTR = 0x00

# Act descriptor field offsets (engine/structs.emp `struct Act`).
ACT_GRID_W, ACT_GRID_H = 0x04, 0x06
ACT_START_LX, ACT_START_LY = 0x08, 0x0A
ACT_START_SX, ACT_START_SY = 0x0C, 0x0D


class SetupError(Exception):
    """Something made the measurement impossible. Not a verdict — exit 2, never exit 1."""


def emp_const(rel: str, name: str) -> int:
    """A `const NAME = $HEX` / `= 123` out of an .emp source, so the gate cannot drift."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        raise SetupError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


class Server:
    """One oracle-aether process. A fresh one per run — every run starts from reset."""

    def __init__(self, rom: str, sock: str = SOCK):
        self.rom, self.sock, self.proc, self.client = rom, sock, None, None

    async def __aenter__(self) -> "Server":
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        self.proc = subprocess.Popen(
            [SERVER, self.rom, "--socket", self.sock, "--no-pace"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)
        else:
            raise SetupError(f"oracle-aether never created {self.sock}")
        self.client = BusClient(self.sock, client_id="bootovr",
                                client_name="boot_override_gate")
        info = await self.client.connect()
        # The identity assertion, shared with every other gate in this lane
        # (`tools/aether_instance.py`): this gate has ALWAYS spawned oracle-aether,
        # but nothing checked that the thing which answered was it. A gate silently
        # talking to the legacy server reports a verdict measured on the wrong
        # emulator and nothing goes red.
        assert_rust_server(info)
        for m in ("emulator/scanlines", "emulator/read_vram", "emulator/write_memory",
                  "emulator/run_to"):
            if not self.client.supports(m):
                raise SetupError(f"the server does not advertise `{m}`")
        return self

    async def __aexit__(self, *exc) -> None:
        try:
            if self.client:
                await self.client.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


async def _c(b, method, params=None, timeout=180.0):
    """Every RPC gets a deadline — a run that never breaks otherwise blocks the next
    call, which has no timeout of its own."""
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


# ---- readback ---------------------------------------------------------------

def _hexint(r) -> int:
    return int(r["bytes"].removeprefix("0x").removeprefix("0X"), 16)


async def read_at(b, addr: int, n: int) -> int:
    return _hexint(await _c(b, "emulator/read_memory", {"addr": hex(addr), "len": n}))


async def read_word(b, sym, name: str) -> int:
    return await read_at(b, sym[name], 2)


async def read_long(b, sym, name: str) -> int:
    return await read_at(b, sym[name], 4)


async def frame_token(b) -> int:
    """The emulated frame index — the only honest clock here. `run_to`'s own `frames`
    counts frames advanced INSIDE that call, and a boot that completes mid-frame reports
    0, which is a measurement artefact rather than a boot that took no time."""
    return int((await _c(b, "emulator/status", {}))["frameToken"])


async def read_plane_a(b, base: int) -> list[int]:
    """Plane A's 4096 nametable WORDS, read as two 4096-byte chunks (maxReadLen = 4096)."""
    raw = ""
    for off in (0, 4096):
        r = await _c(b, "emulator/read_vram", {"addr": hex(base + off), "len": 4096})
        chunk = r["bytes"].upper().removeprefix("0X")
        if len(chunk) != 8192:
            raise SetupError(f"read_vram returned {len(chunk)//2} bytes, wanted 4096")
        raw += chunk
    return [int(raw[i:i + 4], 16) for i in range(0, len(raw), 4)]


STATE_WORDS = ["Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row", "Cache_Bottom_Row",
               "Cache_Prev_Cam_X", "Cache_Prev_Cam_Row"]


async def read_state(b, sym) -> dict:
    st = {n: await read_word(b, sym, n) for n in STATE_WORDS}
    st["Camera_X"] = (await read_long(b, sym, "Camera_X")) >> 16
    st["Camera_Y"] = (await read_long(b, sym, "Camera_Y")) >> 16
    st["Player_X"] = (await read_at(b, sym["Player_1"] + SST_X_POS, 4)) >> 16
    st["Player_Y"] = (await read_at(b, sym["Player_1"] + SST_Y_POS, 4)) >> 16
    return st


async def snapshot(b, sym, plane_base: int) -> dict:
    st = await read_state(b, sym)
    r = await _c(b, "emulator/scanlines",
                 {"startLine": SCANLINE_START, "count": SCANLINE_COUNT})
    if r.get("source") != "raster":
        raise SetupError(f"emulator/scanlines answered source={r.get('source')!r} "
                         f"(caveat {r.get('caveat')!r}) — a post-hoc render is blind here")
    colours = set()
    for row in r["rows"]:
        h = row["rgb"].removeprefix("0x").removeprefix("0X")
        b3 = bytes.fromhex(h)
        colours |= {b3[i:i + 3] for i in range(0, len(b3), 3)}
    return {"state": st, "plane": await read_plane_a(b, plane_base),
            "colours": len(colours), "mode": r.get("mode"),
            "rows": [row["rgb"].upper().removeprefix("0X") for row in r["rows"]]}


def visible_words(snap: dict) -> list[int]:
    """The plane cells the camera is actually SHOWING, in a fixed order.

    41x29 cells covers 320x224 px including both partial edge cells. Cell (col,row)
    lives at (row & 63)*64 + (col & 63) — continuous scroll wraps the world through
    the 64x64 ring. The whole plane is NOT a valid metric (warp_mailbox_gate proved
    two correct walks disagree on it by 26 words)."""
    c0, r0 = snap["state"]["Camera_X"] >> 3, snap["state"]["Camera_Y"] >> 3
    return [snap["plane"][(r & 63) * 64 + (c & 63)]
            for r in range(r0, r0 + 29) for c in range(c0, c0 + 41)]


def word_diff(a: list[int], b: list[int]) -> int:
    if len(a) != len(b):
        raise SetupError(f"plane captures differ in length ({len(a)} vs {len(b)})")
    return sum(1 for x, y in zip(a, b) if x != y)


# ---- derived expectations ---------------------------------------------------

def derived_cache(cam_x: int, cam_y: int, k: dict) -> dict:
    """Tile_Cache_Init IS the authority; this restates its arithmetic against the
    constants read out of engine/system/constants.emp."""
    left = max(0, (cam_x >> 3) - k["MH"])
    top = max(0, (cam_y >> 3) - k["MV"]) & 0xFFFE
    return {"Cache_Left_Col": left, "Cache_Head_Col": left + k["COLS"] - 1,
            "Cache_Top_Row": top, "Cache_Bottom_Row": top + k["ROWS"] - 1,
            "Cache_Prev_Cam_X": cam_x, "Cache_Prev_Cam_Row": cam_y >> 3}


def check_cache(snap: dict, k: dict) -> list[str]:
    exp = derived_cache(snap["state"]["Camera_X"], snap["state"]["Camera_Y"], k)
    return [f"{n}={snap['state'][n]} wanted {w}" for n, w in exp.items()
            if snap["state"][n] != w]


def clamp_expect(x: int, y: int, act: dict) -> tuple[int, int]:
    """Player_BoundsInit's own formula, re-derived from the descriptor + the two
    constants it reads. Signed: bit 15 set is out of range by definition."""
    def s16(v):
        return v - 0x10000 if v & 0x8000 else v
    cx, cy = s16(x), s16(y)
    return (min(max(cx, 0), act["bound_right"]), min(max(cy, 0), act["bound_bottom"]))


def camera_expect(px: int, py: int, act: dict, k: dict) -> tuple[int, int]:
    """center_camera_on's own clamp, against Camera_Init's precomputed ceilings."""
    return (min(max(px - k["HALF_W"], 0), act["cam_x_max"]),
            min(max(py - k["HALF_H"], 0), act["cam_y_max"]))


# ---- the runs ---------------------------------------------------------------

async def _boot_to_init(b, sym, lst: str) -> int:
    """Reset, then stop at the level init's first instruction — i.e. AFTER boot's 64KB
    Work-RAM clear and BEFORE any consumer of the mailbox. THE client window."""
    await _c(b, "emulator/load_symbols", {"path": lst})
    await _c(b, "emulator/reset", {})
    r = await _c(b, "emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Init"]),
                                        "maxFrames": BOOT_MAX_FRAMES})
    if not r.get("fired", True):
        raise SetupError("never reached GameState_OJZScroll_Init — wrong ROM shape?")
    return int(r.get("frames", 0))


async def _init_to_update(b, sym) -> int:
    """Run the init out. Stopping at the UPDATE state's first instruction is the first
    frame the display is on with the init's synchronous plane fill complete — 'the first
    visible frame' made operable."""
    r = await _c(b, "emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Update"]),
                                        "maxFrames": BOOT_MAX_FRAMES})
    if not r.get("fired", True):
        raise SetupError("never reached GameState_OJZScroll_Update")
    return int(r.get("frames", 0))


async def _write_mailbox(b, sym, prefix: str, x: int, y: int, flag: int = 1) -> None:
    """X, then Y, then the FLAG last — the write order IS the protocol."""
    await _c(b, "emulator/write_memory", {"addr": hex(sym[f"{prefix}_X"]), "value": x,
                                          "width": 2})
    await _c(b, "emulator/write_memory", {"addr": hex(sym[f"{prefix}_Y"]), "value": y,
                                          "width": 2})
    if flag:
        await _c(b, "emulator/write_memory", {"addr": hex(sym[f"{prefix}_Flag"]),
                                              "value": flag, "width": 1})


async def run_control(rom, sym, lst, k, plane_base: int) -> dict:
    """No write at all: today's boot, unchanged."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _init_to_update(b, sym)
        # Past the init to the first FULLY PAINTED frame — see PAINT_LAG.
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        t_playable = await frame_token(b)
        first = await snapshot(b, sym, plane_base)
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        return {"t_playable": t_playable,
                "first": first, "final": await snapshot(b, sym, plane_base),
                "boot_flag": await read_at(b, sym["Boot_At_Flag"], 1)}


async def run_override(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """The subject: write at the init breakpoint, then let the init consume it."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _write_mailbox(b, sym, "Boot_At", x, y)
        await _init_to_update(b, sym)
        # The state AT the init's exit — before a single Update tick has run. This is
        # where "the init aimed ITSELF at the override" is either true or not.
        at_exit = await read_state(b, sym)
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        t_playable = await frame_token(b)
        first = await snapshot(b, sym, plane_base)
        published = (await read_word(b, sym, "Boot_At_X"),
                     await read_word(b, sym, "Boot_At_Y"))
        flags = {"Boot_At_Flag": await read_at(b, sym["Boot_At_Flag"], 1),
                 "Warp_Req_Flag": await read_at(b, sym["Warp_Req_Flag"], 1)}
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        final = await snapshot(b, sym, plane_base)
        # STILL ALIVE? Tile_Cache_Init's DEBUG tail runs PageCache_Audit, and a bad
        # residency reset raises and parks the 68000 in the error handler. A Logic_Tick
        # that still advances is the proof the audit passed.
        t0 = await read_long(b, sym, "Logic_Tick")
        await _c(b, "emulator/run_frames", {"frames": 2})
        t1 = await read_long(b, sym, "Logic_Tick")
        return {"t_playable": t_playable, "at_exit": at_exit, "first": first,
                "final": final, "published": published, "flags": flags,
                "ticks": (t0, t1)}


async def run_warp_reference(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """The REFERENCE: today's supported route to the same place — boot, then warp."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _init_to_update(b, sym)
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})   # the same first-painted-
                                                                    # frame baseline the
                                                                    # override run uses
        await _write_mailbox(b, sym, "Warp_Req", x, y)
        acked = None
        for i in range(1, ACK_MAX_FRAMES + 1):
            await _c(b, "emulator/run_frames", {"frames": 1})
            if await read_at(b, sym["Warp_Req_Flag"], 1) == 0:
                acked = i
                break
        if acked is None:
            raise SetupError(f"Warp_Req_Flag never cleared in {ACK_MAX_FRAMES} frames")
        t_playable = await frame_token(b)
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        return {"t_playable": t_playable, "ack_frames": acked,
                "final": await snapshot(b, sym, plane_base),
                "published": (await read_word(b, sym, "Warp_Req_X"),
                              await read_word(b, sym, "Warp_Req_Y"))}


async def run_flag_clear(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """POISON: cells written, FLAG NOT SET. Must boot authored, and must NOT publish —
    an override that ran anyway, or a clamp that ran anyway, both show here."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _write_mailbox(b, sym, "Boot_At", x, y, flag=0)
        await _init_to_update(b, sym)
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        first = await snapshot(b, sym, plane_base)
        return {"first": first, "cells": (await read_word(b, sym, "Boot_At_X"),
                                          await read_word(b, sym, "Boot_At_Y"))}


async def run_pre_resume(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """THE TIMING TRUTH, made a measurement: write the mailbox at the RESET-PAUSED
    machine, the way the warp mailbox's prose would suggest. Boot's 64KB Work-RAM clear
    eats it, so the boot must be the AUTHORED one and the cells must read back zero.
    This is why the client procedure is a breakpoint and not a pre-resume poke."""
    async with Server(rom) as s:
        b = s.client
        await _c(b, "emulator/load_symbols", {"path": lst})
        await _c(b, "emulator/reset", {})
        await _write_mailbox(b, sym, "Boot_At", x, y)
        await _c(b, "emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Init"]),
                                        "maxFrames": BOOT_MAX_FRAMES})
        at_init = (await read_word(b, sym, "Boot_At_X"),
                   await read_word(b, sym, "Boot_At_Y"),
                   await read_at(b, sym["Boot_At_Flag"], 1))
        await _init_to_update(b, sym)
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        return {"at_init": at_init, "first": await snapshot(b, sym, plane_base)}


# ---- main -------------------------------------------------------------------

def _fail(msgs: list[str], cond: bool, text: str) -> None:
    if not cond:
        msgs.append(text)


async def main_async(args) -> int:
    k = {
        "COLS": emp_const("engine/system/constants.emp", "TILE_CACHE_COLS"),
        "ROWS": emp_const("engine/system/constants.emp", "TILE_CACHE_ROWS"),
        "MH": emp_const("engine/system/constants.emp", "TILE_CACHE_MARGIN_H"),
        "MV": emp_const("engine/system/constants.emp", "TILE_CACHE_MARGIN_V"),
        "HALF_W": emp_const("engine/system/constants.emp", "CAM_SCREEN_HALF_W"),
        "HALF_H": emp_const("engine/system/constants.emp", "CAM_SCREEN_HALF_H"),
        "SHIFT": emp_const("engine/system/constants.emp", "SECTION_SIZE_SHIFT"),
        "SCREEN_W": emp_const("engine/system/constants.emp", "SCREEN_WIDTH"),
        "SCREEN_H": emp_const("engine/system/constants.emp", "SCREEN_HEIGHT"),
        "PBOUND": emp_const("games/sonic4/player/player_common.emp", "PBOUND_RIGHT_MARGIN"),
    }
    plane_base = emp_const("engine/system/constants.emp", "VRAM_PLANE_A")
    sym = parse_lst(args.lst)
    for need in ("Boot_At_X", "Boot_At_Y", "Boot_At_Flag", "Warp_Req_X", "Warp_Req_Y",
                 "Warp_Req_Flag", "GameState_OJZScroll_Init", "GameState_OJZScroll_Update",
                 "Camera_X", "Camera_Y", "Logic_Tick", "Player_1",
                 "OJZ_Act1_Descriptor", *STATE_WORDS):
        if need not in sym:
            raise SetupError(f"symbol {need} is not in {args.lst} — wrong ROM shape? "
                             "(this gate needs the sonic4 DEBUG listing)")

    # The act descriptor, read out of the ROM image itself — the authored start and the
    # clamp edges are DERIVED from it, never typed here.
    rom_img = Path(args.rom).read_bytes()
    d = sym["OJZ_Act1_Descriptor"]
    if d >= len(rom_img):
        raise SetupError(f"OJZ_Act1_Descriptor {d:#x} is past the end of {args.rom}")

    def rw(off):
        return int.from_bytes(rom_img[d + off:d + off + 2], "big")

    act = {
        "grid_w": rw(ACT_GRID_W), "grid_h": rw(ACT_GRID_H),
        "start_lx": rw(ACT_START_LX), "start_ly": rw(ACT_START_LY),
        "start_sx": rom_img[d + ACT_START_SX], "start_sy": rom_img[d + ACT_START_SY],
    }
    act["level_w"] = act["grid_w"] << k["SHIFT"]
    act["level_h"] = act["grid_h"] << k["SHIFT"]
    act["bound_right"] = act["level_w"] - k["PBOUND"]
    act["bound_bottom"] = act["level_h"] - k["SCREEN_H"]
    act["cam_x_max"] = act["level_w"] - k["SCREEN_W"]
    act["cam_y_max"] = act["level_h"] - k["SCREEN_H"]
    # The authored start as the init ladder actually produces it: Camera_Init clamps the
    # seed, and the spawn is camera + half-screen. Near a world edge those disagree with
    # the raw start point, which is exactly why this is computed and not assumed.
    a_start_x = (act["start_sx"] << k["SHIFT"]) + act["start_lx"]
    a_start_y = (act["start_sy"] << k["SHIFT"]) + act["start_ly"]
    a_cam_x = min(max(a_start_x - k["HALF_W"], 0), act["cam_x_max"])
    a_cam_y = min(max(a_start_y - k["HALF_H"], 0), act["cam_y_max"])
    authored = (a_cam_x + k["HALF_W"], a_cam_y + k["HALF_H"])

    dest = (args.x, args.y)
    dest_clamped = clamp_expect(*dest, act)
    dest_cam = camera_expect(*dest_clamped, act, k)
    # A destination that clamps is not testing what this gate is about.
    if dest_clamped != dest:
        raise SetupError(f"destination {dest} clamps to {dest_clamped} in this act — "
                         "pick one inside the bounds for the main runs")

    # THE GATE'S OWN BLIND SPOT, MADE A TRIPWIRE. The override has a SECOND consumer —
    # the init's parallax config select, which must read the destination's section rather
    # than the authored one. In OJZ act 1 that is currently unobservable: every section
    # binds `sec_parallax_config: default` (NULL = inherit the act default), so the select
    # returns the same pointer whatever section index it is handed, and poisoning that half
    # of the hook leaves every measurement below unchanged (verified: poison p2 passes).
    # Rather than let a green gate imply coverage it does not have, assert the PREMISE: the
    # day any section binds its own config, this fails and names the work.
    grid = int.from_bytes(rom_img[d + ACT_SEC_GRID_PTR:d + ACT_SEC_GRID_PTR + 4], "big")
    bound = 0
    for i in range(act["grid_w"] * act["grid_h"]):
        off = grid + i * SEC_SIZE + SEC_PARALLAX_CONFIG
        if off + 4 <= len(rom_img) and int.from_bytes(rom_img[off:off + 4], "big"):
            bound += 1
    if bound:
        raise SetupError(
            f"{bound} of {act['grid_w'] * act['grid_h']} sections now bind their own "
            "sec_parallax_config. The boot override's parallax select becomes observable "
            "at that point and this gate does not yet witness it — extend it (compare the "
            "override's rendered scanlines against a walked arrival, not against a warp "
            "that snaps) before trusting a green run.")

    ctl = await run_control(args.rom, sym, args.lst, k, plane_base)
    ovr = await run_override(args.rom, sym, args.lst, k, plane_base, *dest)
    wrp = await run_warp_reference(args.rom, sym, args.lst, k, plane_base, *dest)
    # The clamp run: one axis past the act edge, one axis negative — both directions of
    # the clamp in a single boot.
    clamp_req = (act["level_w"] + 4096, 0xFFF0)
    clamp_exp = clamp_expect(*clamp_req, act)
    clm = await run_override(args.rom, sym, args.lst, k, plane_base, *clamp_req)
    # POISON: the maximum-garbage request. $7FFF/$7FFF is the largest positive word, far
    # past any act edge, and $8000-set values are covered by the clamp run's negative axis.
    psn = await run_override(args.rom, sym, args.lst, k, plane_base, 0x7FFF, 0x7FFF)
    psn_exp = clamp_expect(0x7FFF, 0x7FFF, act)
    flg = await run_flag_clear(args.rom, sym, args.lst, k, plane_base, *dest)
    pre = await run_pre_resume(args.rom, sym, args.lst, k, plane_base, *dest)

    fails: list[str] = []

    # 1. CONTROL — an unwritten mailbox boots exactly where the act says.
    _fail(fails, (ctl["first"]["state"]["Player_X"], ctl["first"]["state"]["Player_Y"])
          == authored,
          f"control: player at ({ctl['first']['state']['Player_X']},"
          f"{ctl['first']['state']['Player_Y']}), authored start is {authored}")
    _fail(fails, ctl["boot_flag"] == 0,
          f"control: Boot_At_Flag reads {ctl['boot_flag']} on a boot nothing wrote")

    # 2. THE OVERRIDE, AT THE INIT'S OWN EXIT — before a single Update tick has run.
    #    Player, camera and the tile-cache window all already at the destination is the
    #    difference between "the init aimed itself" and "something corrected it after".
    xs = ovr["at_exit"]
    _fail(fails, (xs["Player_X"], xs["Player_Y"]) == dest_clamped,
          f"override: at the init's exit the player is ({xs['Player_X']},{xs['Player_Y']}), "
          f"wanted {dest_clamped}")
    _fail(fails, (xs["Camera_X"], xs["Camera_Y"]) == dest_cam,
          f"override: at the init's exit the camera is ({xs['Camera_X']},{xs['Camera_Y']}), "
          f"wanted {dest_cam}")
    bad_exit = check_cache({"state": xs}, k)
    _fail(fails, not bad_exit,
          f"override: the init did not seed the tile-cache window at the destination: {bad_exit}")

    # 2b. AND STILL THERE ON THE FIRST PAINTED FRAME.
    fs = ovr["first"]["state"]
    _fail(fails, (fs["Player_X"], fs["Player_Y"]) == dest_clamped,
          f"override: first-frame player ({fs['Player_X']},{fs['Player_Y']}) "
          f"wanted {dest_clamped}")
    _fail(fails, (fs["Camera_X"], fs["Camera_Y"]) == dest_cam,
          f"override: first-frame camera ({fs['Camera_X']},{fs['Camera_Y']}) "
          f"wanted {dest_cam}")
    bad = check_cache(ovr["first"], k)
    _fail(fails, not bad, f"override: tile-cache window not seeded at the destination: {bad}")
    _fail(fails, ovr["published"] == dest_clamped,
          f"override: published {ovr['published']}, wanted {dest_clamped}")
    _fail(fails, ovr["flags"]["Boot_At_Flag"] == 0,
          "override: Boot_At_Flag not cleared — the ack never landed")
    _fail(fails, ovr["flags"]["Warp_Req_Flag"] == 0,
          "override: Warp_Req_Flag is set — a warp was involved, which is the whole "
          "thing this replaces")
    _fail(fails, ovr["ticks"][1] > ovr["ticks"][0],
          f"override: Logic_Tick stuck at {ovr['ticks']} — the 68000 is parked "
          "(PageCache_Audit raised?)")
    _fail(fails, ovr["first"]["colours"] > 1,
          f"override: first frame shows {ovr['first']['colours']} colour(s) — a flat "
          "screen is not level content")

    # 3. NO DRAW-THEN-JUMP. The first displayed frame's visible plane must already equal
    #    the settled one: the init's synchronous fill did the whole job, nothing crawls in.
    d_first_final = word_diff(visible_words(ovr["first"]), visible_words(ovr["final"]))
    _fail(fails, d_first_final == 0,
          f"override: {d_first_final} visible words changed between the first painted "
          f"frame and +{SETTLE}f — the destination was NOT complete on frame 1")

    # 3b. A NEGATIVE CONTROL THAT IS NOT FREE. Every assertion above would still pass if
    #     the destination happened to look like the authored start, so require the two
    #     first frames to differ by most of the LEGITIMATE content delta between the two
    #     places — measured in-run (control settled vs warp settled), never typed.
    content_delta = word_diff(visible_words(ctl["final"]), visible_words(wrp["final"]))
    d_ctl_ovr = word_diff(visible_words(ctl["first"]), visible_words(ovr["first"]))
    _fail(fails, content_delta > 0,
          "negative control: the authored start and the destination render the SAME visible "
          "plane, so nothing below distinguishes them — pick a different destination")
    _fail(fails, d_ctl_ovr >= content_delta // 2,
          f"negative control: the override's first frame differs from the authored boot's by "
          f"only {d_ctl_ovr} words against a legitimate content delta of {content_delta} — "
          "the override did not move the screen")

    # 3c. THE PIXELS, not just the nametable. The plane-A comparison is blind to the
    #     parallax config — palette, band offsets and Plane B all live outside it, and the
    #     init's parallax select is the SECOND consumer of the override. `emulator/scanlines`
    #     is the only pixel-truthful instrument on this bus (source=="raster", asserted in
    #     `snapshot`), so the same 8 scanlines rendered by the two routes must agree.
    px_diff = sum(1 for a, bb in zip(ovr["final"]["rows"], wrp["final"]["rows"]) if a != bb)
    _fail(fails, px_diff == 0,
          f"override vs warp reference: {px_diff} of {len(ovr['final']['rows'])} rendered "
          "scanlines differ — the two routes agree on the nametable but not on what is "
          "actually drawn (parallax config / palette)")

    # 4. THE REFERENCE. The boot override must reproduce the warp's settled plane exactly.
    d_vs_warp = word_diff(visible_words(ovr["final"]), visible_words(wrp["final"]))
    _fail(fails, d_vs_warp == 0,
          f"override vs warp reference: {d_vs_warp} of "
          f"{len(visible_words(ovr['final']))} visible plane-A words differ")
    _fail(fails, (ovr["final"]["state"]["Camera_X"], ovr["final"]["state"]["Camera_Y"])
          == (wrp["final"]["state"]["Camera_X"], wrp["final"]["state"]["Camera_Y"]),
          "override vs warp reference: the two runs settled on different cameras, so the "
          "plane comparison above is not like-for-like")

    # 5. THE CLAMP, both directions, published back.
    _fail(fails, clm["published"] == clamp_exp,
          f"clamp: requested {clamp_req}, published {clm['published']}, wanted {clamp_exp}")
    cs = clm["first"]["state"]
    _fail(fails, (cs["Player_X"], cs["Player_Y"]) == clamp_exp,
          f"clamp: player at ({cs['Player_X']},{cs['Player_Y']}), wanted {clamp_exp}")

    # 6. POISON — garbage past every edge is clamped and the machine survives it.
    _fail(fails, psn["published"] == psn_exp,
          f"poison: $7FFF/$7FFF published {psn['published']}, wanted {psn_exp}")
    ps = psn["first"]["state"]
    _fail(fails, (ps["Player_X"], ps["Player_Y"]) == psn_exp,
          f"poison: player at ({ps['Player_X']},{ps['Player_Y']}), wanted {psn_exp}")
    _fail(fails, psn["ticks"][1] > psn["ticks"][0],
          f"poison: Logic_Tick stuck at {psn['ticks']} — a garbage request faulted the machine")
    _fail(fails, not check_cache(psn["first"], k),
          f"poison: tile-cache window incoherent at the clamped destination: "
          f"{check_cache(psn['first'], k)}")

    # 7. POISON — the FLAG is the gate. Cells written, flag left clear: authored boot,
    #    and the cells come back untouched (no clamp, no publish).
    gs = flg["first"]["state"]
    _fail(fails, (gs["Player_X"], gs["Player_Y"]) == authored,
          f"flag-clear: player at ({gs['Player_X']},{gs['Player_Y']}), wanted the "
          f"authored {authored} — the override ran without its flag")
    _fail(fails, flg["cells"] == dest,
          f"flag-clear: cells read back {flg['cells']}, wanted the untouched {dest} — "
          "the clamp ran without the flag")

    # 8. THE RAM-CLEAR TRUTH. A pre-resume write is zeroed, so the boot is authored.
    _fail(fails, pre["at_init"] == (0, 0, 0),
          f"pre-resume: the mailbox read {pre['at_init']} at the init — boot's Work-RAM "
          "clear was expected to zero it, so the client procedure's premise moved")
    prs = pre["first"]["state"]
    _fail(fails, (prs["Player_X"], prs["Player_Y"]) == authored,
          f"pre-resume: player at ({prs['Player_X']},{prs['Player_Y']}), wanted the "
          f"authored {authored}")

    # ---- the saving, measured engine-side --------------------------------------
    # Absolute emulated frame indices (`frameToken`), so the two routes are compared on
    # one clock. `run_to`'s own `frames` counts frames advanced inside that call and a
    # boot that finishes mid-frame reports 0 — an artefact, not a boot that took no time.
    boot_frames = ctl["t_playable"]
    ovr_frames = ovr["t_playable"]
    warp_frames = wrp["t_playable"]
    saving = warp_frames - ovr_frames

    report = {
        "destination": dest, "clamped": dest_clamped, "camera": dest_cam,
        "authored_start": authored,
        "act": {kk: act[kk] for kk in ("grid_w", "grid_h", "bound_right", "bound_bottom")},
        "frames": {
            "boot_to_first_painted_frame": boot_frames,
            "override_boot_to_destination": ovr_frames,
            "warp_boot_to_destination": warp_frames,
            "warp_ack_frames": wrp["ack_frames"],
            "saving_frames": saving,
            "saving_seconds_ntsc": round(saving / 60.0, 3),
        },
        "parallax_sections_binding_own_config": bound,
        "planes": {
            "visible_words": len(visible_words(ovr["final"])),
            "authored_vs_destination_content_delta": content_delta,
            "control_first_vs_override_first": d_ctl_ovr,
            "override_vs_warp_scanline_rows": px_diff,
            "override_first_vs_settled": d_first_final,
            "override_vs_warp_reference": d_vs_warp,
        },
        "published": {"override": ovr["published"], "warp": wrp["published"],
                      "clamp": clm["published"], "poison": psn["published"]},
        "fails": fails,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"boot_override_gate: destination {dest} -> clamped {dest_clamped}, "
              f"camera {dest_cam}")
        print(f"  authored start (derived from the act descriptor): {authored}")
        print(f"  boot -> first painted frame:          {boot_frames} frames")
        print(f"  override: boot -> AT the destination: {ovr_frames} frames")
        print(f"  warp:     boot -> AT the destination: {warp_frames} frames "
              f"({wrp['ack_frames']} of them the ack)")
        print(f"  SAVING: {saving} frames = {saving / 60.0:.2f} s at 60 Hz, and the "
              f"override shows the destination on frame 1 rather than the authored start")
        print(f"  visible plane-A words: {len(visible_words(ovr['final']))}; "
              f"first-vs-settled {d_first_final}; vs warp reference {d_vs_warp}")
        print(f"  negative control: authored-vs-destination content delta {content_delta}, "
              f"control-first vs override-first {d_ctl_ovr}")
        print(f"  rendered scanlines differing from the warp reference: {px_diff} of "
              f"{len(ovr['final']['rows'])}")
        print(f"  published — override {ovr['published']}, clamp {clm['published']}, "
              f"poison {psn['published']}")
    if fails:
        print("FAIL:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("boot_override_gate: PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--x", type=int, default=DEST_X)
    ap.add_argument("--y", type=int, default=DEST_Y)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        return asyncio.run(main_async(args))
    except SetupError as e:
        print(f"SETUP ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
