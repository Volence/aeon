#!/usr/bin/env python3
"""GATE BG-SWITCH — a region whose background names its OWN TILES must show those tiles, and the
Plane B layout that indexes them must never reach the screen before they have landed.

Region bg switch (plan docs/superpowers/plans/2026-09-16-region-bg-switch.md). The owner's
ruling: a switch is a FULL OVERWRITE of the BG tile arena, then a repaint, and the repaint must
not start until the overwrite completes, enforced by the sequence and not by timing. S3K's
Icecap Zone is the failure shape this gate exists to refuse: a layout switch gated on the
layout being ready rather than on the tiles it references being resident.

THE SUBJECT, DERIVED: the one region row in the ROM's own table whose `rg_bg_tiles` is
nonzero (the DEBUG showcase row, games/sonic4/data/levels/ojz/act1/act_descriptor.emp). Its
tile blob and layout blob are READ OUT OF THE ROM at the row's pointers, the act default's out
of `Act.act_bg_tiles` / `Act.act_bg_layout`, and every VRAM comparison is against those bytes.
Constants are parsed out of the engine sources. Nothing is typed from a table.

LEGS (each names what it asserts):

  BOOT   boot_inside_a_region_with_its_own_tiles_shows_those_tiles
         Boot with the camera centre in the subject row. At the first Update: the BG tile
         arena holds the subject's tile blob, BG_Tiles_Current names it, and Plane B holds
         the subject's layout.
  WARP   warp_into_a_region_with_its_own_tiles_uploads_them_before_the_first_update
         Boot in an act-default neighbour, warp into the subject row, and at the first Update
         after the ack assert the same three; then warp back OUT and assert the act default's
         tiles and layout are back.

  TRANSPORT  crossing_into_a_region_with_its_own_tiles_uploads_its_whole_blob_in_bounded_frames
         Fly RIGHT across the subject's left edge. The overwrite arms on the first sample inside;
         at most one chunk (2 entries if split) is ever queued; no chunk is enqueued while an
         arena write was still queued the tick before; BG_Tiles_Current names the blob only when
         VRAM holds it; completion within ceil(len/CHUNK)+2 ticks.
  TRANSPORT_STARVED  transport_under_a_starved_window_keeps_one_chunk_outstanding_and_completes
         The same, with DMA_Budget_Default poked below one chunk for STARVE_TICKS ticks once two
         chunks have gone, so a chunk is HELD in the queue. The only leg that can see the
         one-outstanding rule: on a calm frame every chunk drains in its own VBlank.
  TRAFFIC  the_overwrite_completes_while_another_producer_enqueues_a_deferrable_entry_every_frame
         A synthetic 32 B Deferrable entry to the map's free tile, appended every tick (positive
         control first). Red against a global queue-empty completion test (the draft's C2).

WHAT A GREEN HERE DOES NOT SAY: nothing about how the switch LOOKS, and (until the ORDER legs)
nothing about whether Plane B is painted before the tiles land.

Exit: 0 PASS · 1 FAIL · 2 COULD NOT RUN (a premise the gate refuses to measure past).
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

AEON = Path(os.environ.get("AEON_DIR",
                           Path(__file__).resolve().parent.parent)).resolve()
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path                            # noqa: E402
add_client_path()
from aether import BusClient                                       # noqa: E402
from aether_instance import (AetherInstance, SpawnError,           # noqa: E402
                             WrongServerError, read_bytes, unprefix)
from raster_cost_probe import parse_lst                            # noqa: E402
import region_table                                                # noqa: E402

BOOT_MAX_FRAMES = 1200
TICK_MAX_FRAMES = 30
ACK_MAX_TICKS = 240


class GateError(RuntimeError):
    """A premise this gate refuses to measure past — exit 2, never a pass."""


class Failure(RuntimeError):
    """A real red — exit 1."""


# ---------------------------------------------------------------------------
# Constants, each re-derived from the source that declares it.
# ---------------------------------------------------------------------------
def _const(rel, name):
    text = (AEON / rel).read_text(errors="replace")
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*(?::\s*\w+\s*)?=\s*"
                  rf"(\$[0-9A-Fa-f]+|\d+)\s*(?://|$)", text, re.M)
    if not m:
        raise GateError(f"{rel} no longer declares `const {name} = <int>`; every expectation "
                        f"in tools/bg_switch_gate.py is derived from it")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


class Consts:
    def __init__(self):
        C = "engine/system/constants.emp"
        self.PLANE_H_CELLS = _const(C, "PLANE_H_CELLS")
        self.PLANE_V_CELLS = _const(C, "PLANE_V_CELLS")
        self.VRAM_PLANE_B = _const(C, "VRAM_PLANE_B_BYTES")
        self.BG_TILE_BASE_VRAM = _const(C, "BG_TILE_BASE_VRAM")
        self.BG_TILE_CAPACITY = _const(C, "BG_TILE_CAPACITY")
        self.HALF_W = _const(C, "CAM_SCREEN_HALF_W")
        self.HALF_H = _const(C, "CAM_SCREEN_HALF_H")
        self.FLY = _const("games/sonic4/player/player_common.emp", "PLAYER_DEBUG_FLY_SPEED")
        self.PLANE_BYTES = self.PLANE_H_CELLS * self.PLANE_V_CELLS * 2
        if self.VRAM_PLANE_B is None:
            raise GateError("engine/system/constants.emp declares no VRAM_PLANE_B_BYTES")
        self.CHUNK = _const("engine/level/bg.emp", "BG_OVERWRITE_CHUNK_BYTES")
        self.ARENA_END = self.BG_TILE_BASE_VRAM + self.BG_TILE_CAPACITY * 32
        self.WIPE_ROWS = _const("engine/level/bg.emp", "BG_WIPE_ROWS_PER_FRAME")
        self.WIPE_FRAMES = -(-self.PLANE_V_CELLS // self.WIPE_ROWS)
        self.DMA_ENTRY, self.DMA_ENTRY_SIZE = dma_entry_layout()
        # The one free tile in the VRAM map (vram.toml: "THE MAP HAS ONE FREE TILE LEFT"),
        # derived from the generated map rather than typed: the tile no region covers.
        from vram_map import REGIONS
        covered = set()
        for r in REGIONS.values():
            covered.update(range(r["base"], r["base"] + r["tiles"]))
        free = [t for t in range(0, 2048) if t not in covered]
        if not free:
            raise GateError("the VRAM map has no free tile; the TRAFFIC leg's synthetic "
                            "Deferrable producer has nowhere harmless to write")
        self.FREE_TILE = free[0]


def dma_entry_layout():
    """`struct DMAEntry` field offsets, parsed from engine/structs.emp by type width (its
    comments carry VDP register numbers like `$14`, so region_table's comment check cannot be
    used on it)."""
    text = (AEON / "engine/structs.emp").read_text()
    m = re.search(r"pub struct DMAEntry\s*\{(.*?)^\}", text, re.M | re.S)
    if not m:
        raise GateError("engine/structs.emp declares no `pub struct DMAEntry`")
    widths = {"u8": 1, "u16": 2, "u32": 4}
    off, out = 0, {}
    for ln in m.group(1).splitlines():
        fm = re.match(r"\s*(\w+)\s*:\s*(u8|u16|u32)\s*,", ln.split("//")[0])
        if fm:
            out[fm.group(1)] = off
            off += widths[fm.group(2)]
    if off != 14 or "Command" not in out:
        raise GateError(f"DMAEntry parsed to {off} B with fields {list(out)}; the queue "
                        f"readers below assume the 14-byte interleaved layout")
    return out, off


def vdp_delta(addr):
    """engine/vdp.emp vdp_comm_delta, restated."""
    return ((addr & 0x3FFF) << 16) | ((addr & 0xC000) >> 14)


def vdp_addr(cmd):
    """engine/vdp.emp vdp_comm_addr, restated."""
    return ((cmd >> 16) & 0x3FFF) | ((cmd & 3) << 14)


# ---------------------------------------------------------------------------
async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def rd(b, addr, width):
    return int(await read_bytes(b, addr, width), 16)


async def read_vram(b, addr, n):
    out = bytearray()
    for off in range(0, n, 4096):
        k = min(4096, n - off)
        r = await _c(b, "emulator/read_vram", {"addr": hex(addr + off), "len": k})
        h = unprefix(r["bytes"])
        if len(h) != k * 2:
            raise GateError(f"short VRAM read at ${addr + off:04X}: {len(h)} hex chars, "
                            f"wanted {k * 2}")
        out += bytes.fromhex(h)
    return bytes(out)


def blob_at(rom, ptr, what):
    if ptr == 0 or ptr + 2 > len(rom):
        raise GateError(f"{what} pointer ${ptr:06X} is not inside the {len(rom)}-byte ROM")
    n = int.from_bytes(rom[ptr:ptr + 2], "big")
    if ptr + 2 + n > len(rom):
        raise GateError(f"{what} at ${ptr:06X} declares {n} B, past the end of the ROM")
    return rom[ptr + 2:ptr + 2 + n]


class Rig:
    """One logic tick at a time, sampled at the top of the game state's Update."""

    def __init__(self, b, sym, K):
        self.b, self.sym, self.K = b, sym, K
        self.upd = sym["GameState_OJZScroll_Update"]

    async def boot(self, at):
        b, sym = self.b, self.sym
        await _c(b, "emulator/reset", {})
        r = await _c(b, "emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Init"]),
                                            "maxFrames": BOOT_MAX_FRAMES})
        if not r.get("reached"):
            raise GateError(f"run_to GameState_OJZScroll_Init never reached it: {r}")
        for nm, v, w in (("Boot_At_X", at[0], 2), ("Boot_At_Y", at[1], 2),
                         ("Boot_At_Flag", 1, 1)):
            await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
        r = await _c(b, "emulator/run_to", {"addr": hex(self.upd), "maxFrames": BOOT_MAX_FRAMES})
        if not r.get("reached"):
            raise GateError(f"run_to GameState_OJZScroll_Update never reached it: {r}")

    async def tick(self):
        await _c(self.b, "emulator/step", {})
        r = await _c(self.b, "emulator/run_to", {"addr": hex(self.upd),
                                                 "maxFrames": TICK_MAX_FRAMES})
        if not r.get("reached"):
            raise GateError(f"the game state's Update did not come round within "
                            f"{TICK_MAX_FRAMES} frames: {r}")

    async def warp(self, at):
        b, sym = self.b, self.sym
        for nm, v, w in (("Warp_Req_X", at[0], 2), ("Warp_Req_Y", at[1], 2),
                         ("Warp_Req_Flag", 1, 1)):
            await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
        for i in range(ACK_MAX_TICKS):
            await self.tick()
            if await rd(b, sym["Warp_Req_Flag"], 1) == 0:
                return i + 1
        raise GateError(f"Warp_Req_Flag never cleared in {ACK_MAX_TICKS} ticks — the warp did "
                        f"not happen, so every sample after it would be the sample before it")

    async def hold(self, button):
        await _c(self.b, "emulator/release_all", {})
        if button:
            await _c(self.b, "emulator/hold", {"buttons": [button], "down": True})

    async def queue(self):
        """The Deferrable queue's live entries: [(dest, length_bytes, source_bytes)]."""
        K, sym = self.K, self.sym
        base, slot = sym["DMA_Deferrable"], await rd(self.b, sym["DMA_Deferrable_Slot"], 2)
        slot |= 0xFF0000
        n = (slot - base) // K.DMA_ENTRY_SIZE
        if slot < base or (slot - base) % K.DMA_ENTRY_SIZE or n > 64:
            raise GateError(f"DMA_Deferrable_Slot ${slot:06X} is not a whole number of "
                            f"entries past DMA_Deferrable ${base:06X}")
        out = []
        if n:
            raw = bytes.fromhex(await read_bytes(self.b, base, n * K.DMA_ENTRY_SIZE))
            E = K.DMA_ENTRY
            for i in range(n):
                e = raw[i * K.DMA_ENTRY_SIZE:(i + 1) * K.DMA_ENTRY_SIZE]
                cmd = int.from_bytes(e[E["Command"]:E["Command"] + 4], "big")
                ln = ((e[E["SizeH"]] << 8) | e[E["SizeL"]]) * 2
                src = ((e[E["SrcH"]] << 16) | (e[E["SrcM"]] << 8) | e[E["SrcL"]]) * 2
                out.append((vdp_addr(cmd), ln, src))
        return out

    async def append_synthetic(self, src, dest, cmd_base):
        """TRAFFIC's producer: append ONE well-formed 32-byte ROM->VRAM entry at the slot, the
        way QueueDMA_Deferrable's core lays it, from the main loop (no VBlank mid-write:
        sampled at the top of Update)."""
        K, sym, E = self.K, self.sym, self.K.DMA_ENTRY
        slot = (await rd(self.b, sym["DMA_Deferrable_Slot"], 2)) | 0xFF0000
        if slot + K.DMA_ENTRY_SIZE > sym["DMA_Deferrable_End"]:
            return False
        e = bytearray(K.DMA_ENTRY_SIZE)
        words = 16
        w = src >> 1
        e[E["Reg94"]], e[E["SizeH"]] = 0x94, (words >> 8) & 0xFF
        e[E["Reg93"]], e[E["SizeL"]] = 0x93, words & 0xFF
        e[E["Reg97"]], e[E["SrcH"]] = 0x97, (w >> 16) & 0x7F
        e[E["Reg96"]], e[E["SrcM"]] = 0x96, (w >> 8) & 0xFF
        e[E["Reg95"]], e[E["SrcL"]] = 0x95, w & 0xFF
        e[E["Command"]:E["Command"] + 4] = (cmd_base | vdp_delta(dest)).to_bytes(4, "big")
        for i, v in enumerate(e):
            await _c(self.b, "emulator/write_memory", {"addr": hex(slot + i), "value": v,
                                                       "width": 1})
        await _c(self.b, "emulator/write_memory", {"addr": hex(sym["DMA_Deferrable_Slot"]),
                                                   "value": (slot + K.DMA_ENTRY_SIZE) & 0xFFFF,
                                                   "width": 2})
        return True

    async def centre_region(self, rows):
        K = self.K
        cx = (await rd(self.b, self.sym["Camera_X"], 4)) >> 16
        cy = (await rd(self.b, self.sym["Camera_Y"], 4)) >> 16
        return region_table.region_at(rows, cx + K.HALF_W, cy + K.HALF_H), (cx, cy)


# ---------------------------------------------------------------------------
class Fixture:
    def __init__(self, rom, sym, K):
        self.rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])
        act_off, _ = region_table.struct_layout("Act")
        d = sym["OJZ_Act1_Descriptor"]
        u32 = lambda a: int.from_bytes(rom[a:a + 4], "big")     # noqa: E731
        self.act_layout_ptr = u32(d + act_off["act_bg_layout"])
        self.act_tiles_ptr = u32(d + act_off["act_bg_tiles"])
        subj = [r for r in self.rows if r["bg_tiles"]]
        if len(subj) != 1:
            raise GateError(
                f"this ROM has {len(subj)} region rows naming their own rg_bg_tiles "
                f"({[r['index'] for r in subj]}); this gate's routes assume exactly one (the "
                f"DEBUG showcase row). The RELEASE listing has none, and there is nothing to "
                f"measure there.")
        S = self.S = subj[0]
        if not S["bg_layout"]:
            raise GateError(f"the subject row {S['index']} names tiles but no layout, so its "
                            f"picture is the act layout over different art — not this "
                            f"gate's fixture")
        self.S_tiles = blob_at(rom, S["bg_tiles"], "the subject's rg_bg_tiles")
        self.A_tiles = blob_at(rom, self.act_tiles_ptr, "Act.act_bg_tiles")
        self.S_layout = rom[S["bg_layout"]:S["bg_layout"] + K.PLANE_BYTES]
        self.A_layout = rom[self.act_layout_ptr:self.act_layout_ptr + K.PLANE_BYTES]
        if S["bg_span"] and S["bg_span"] != K.PLANE_V_CELLS * 8:
            raise GateError("the subject row authors a span; this gate's plane comparison "
                            "assumes a one-plane layout (window top 0)")
        if self.S_tiles[:len(self.A_tiles)] == self.A_tiles[:len(self.S_tiles)]:
            raise GateError("the subject's tiles and the act's agree over their common "
                            "length, so a VRAM read cannot tell them apart")
        if self.S_layout == self.A_layout:
            raise GateError("the subject's layout equals the act's")
        # Routes, derived from the row's own rectangle and its act-default neighbours.
        self.centre = ((S["x0"] + S["x1"]) // 2, (S["y0"] + S["y1"]) // 2)
        left = region_table.region_at(self.rows, S["x0"] - 1, self.centre[1])
        above = region_table.region_at(self.rows, self.centre[0], S["y0"] - 1)
        for nm, r in (("left of", left), ("above", above)):
            if r is None or r["bg_tiles"] or r["bg_layout"]:
                raise GateError(f"the row {nm} the subject is not an act-default row "
                                f"({None if r is None else r['index']}), so the crossing "
                                f"routes this gate derives have no default side")
        self.left, self.above = left, above
        self.left_centre = ((left["x0"] + left["x1"]) // 2, self.centre[1])


async def assert_holds(rig, F, K, which, label, fails):
    """The three facts a settled switch owes: arena tiles, the tile tracker, Plane B."""
    b, sym = rig.b, rig.sym
    tiles, layout, ptr = ((F.S_tiles, F.S_layout, F.S["bg_tiles"]) if which == "subject"
                          else (F.A_tiles, F.A_layout, F.act_tiles_ptr))
    arena = await read_vram(b, K.BG_TILE_BASE_VRAM, len(tiles))
    if arena != tiles:
        bad = sum(1 for i in range(0, len(tiles), 32) if arena[i:i + 32] != tiles[i:i + 32])
        fails.append(f"{label}: the BG tile arena does not hold the {which}'s tile blob — "
                     f"{bad} of {len(tiles) // 32} tiles differ")
    cur = await rd(b, sym["BG_Tiles_Current"], 4)
    if cur != ptr:
        fails.append(f"{label}: BG_Tiles_Current is ${cur:06X}, not the {which}'s blob "
                     f"${ptr:06X}")
    plane = await read_vram(b, K.VRAM_PLANE_B, K.PLANE_BYTES)
    if plane != layout:
        row = K.PLANE_H_CELLS * 2
        bad = sum(1 for p in range(K.PLANE_V_CELLS)
                  if plane[p * row:(p + 1) * row] != layout[p * row:(p + 1) * row])
        fails.append(f"{label}: Plane B does not hold the {which}'s layout — {bad} of "
                     f"{K.PLANE_V_CELLS} rows differ")
    print(f"  {label}: arena {'==' if arena == tiles else '!='} {which} tiles, "
          f"Current ${cur:06X}, plane {'==' if plane == layout else '!='} {which} layout")


async def leg_boot(rig, F, K, fails):
    await rig.boot(F.centre)
    reg, cam = await rig.centre_region(F.rows)
    if reg is None or reg["index"] != F.S["index"]:
        raise GateError(f"BOOT: booted at {F.centre}, camera {cam}, but the camera centre "
                        f"resolves to row {None if reg is None else reg['index']}, not the "
                        f"subject row {F.S['index']}")
    await assert_holds(rig, F, K, "subject", "BOOT", fails)


async def leg_warp(rig, F, K, fails):
    await rig.boot(F.left_centre)
    for _ in range(4):
        await rig.tick()
    await assert_holds(rig, F, K, "act", "WARP (control, before)", fails)
    n = await rig.warp(F.centre)
    reg, cam = await rig.centre_region(F.rows)
    if reg is None or reg["index"] != F.S["index"]:
        raise GateError(f"WARP: warped to {F.centre} (ack after {n} ticks), camera {cam}, "
                        f"but the centre resolves to row {None if reg is None else reg['index']}")
    await assert_holds(rig, F, K, "subject", "WARP in", fails)
    await rig.warp(F.left_centre)
    await assert_holds(rig, F, K, "act", "WARP out", fails)


WALK_MAX_TICKS = 400


async def sample_ow(rig, F, K, with_arena=True):
    b, sym = rig.b, rig.sym
    s = {"region": await rd(b, sym["Region_Current"], 4),
         "target": await rd(b, sym["BG_Tiles_Target"], 4),
         "offset": await rd(b, sym["BG_Tiles_Offset"], 2),
         "current": await rd(b, sym["BG_Tiles_Current"], 4),
         "cursor": await rd(b, sym["BG_Wipe_Cursor"], 1),
         "queue": await rig.queue()}
    s["arena_entries"] = [q for q in s["queue"]
                          if K.BG_TILE_BASE_VRAM <= q[0] < K.ARENA_END]
    if with_arena:
        s["arena"] = await read_vram(b, K.BG_TILE_BASE_VRAM, len(F.S_tiles))
    return s


async def cross_into_subject(rig, F, K, per_tick=None, tag="CROSS", on_sample=None):
    """Boot in the left neighbour, hold RIGHT until the camera centre's region is the subject
    row, then keep holding while `per_tick` samples, until the overwrite completes or the walk
    budget runs out. Returns (samples, index of the first sample inside the subject)."""
    run_up = 8 * K.FLY
    start = (F.S["x0"] - run_up, F.centre[1])
    await rig.boot(start)
    for _ in range(4):
        await rig.tick()
    base = await sample_ow(rig, F, K)
    if base["region"] == F.S["addr"]:
        raise GateError(f"{tag}: booted at {start} but the camera centre is already inside "
                        f"the subject row; the route has no outside")
    await rig.hold("right")
    samples, i_in = [], None
    # Stop flying a few ticks after the crossing so the camera stays inside the subject row
    # for as long as the overwrite takes; the row is 1024 px wide, 64 ticks at fly speed.
    STOP_AFTER = 8
    budget = None
    try:
        for i in range(WALK_MAX_TICKS):
            if per_tick:
                await per_tick(i)
            s = await sample_ow(rig, F, K)
            samples.append(s)
            if on_sample is not None:
                on_sample["last"] = s
            if i_in is None and s["region"] == F.S["addr"]:
                i_in = i
                budget = i + STOP_AFTER + 4 * (-(-len(F.S_tiles) // K.CHUNK)) + 16
            if i_in is not None and i - i_in == STOP_AFTER:
                await rig.hold(None)
            if i_in is not None and s["current"] == F.S["bg_tiles"]:
                return samples, i_in
            if i_in is not None and s["region"] != F.S["addr"]:
                raise GateError(f"{tag}: the camera left the subject row {i - i_in} ticks after "
                                f"entering, before the overwrite completed; the route no "
                                f"longer keeps the camera inside")
            if budget is not None and i >= budget:
                return samples, i_in       # never completed: check_transport reports it red
            await rig.tick()
    finally:
        await rig.hold(None)
    return samples, i_in


def check_transport(samples, i_in, F, K, label, fails, slack):
    if i_in is None:
        raise GateError(f"{label}: the walk never entered the subject row")
    n_chunks = -(-len(F.S_tiles) // K.CHUNK)
    # The crossing is published by Parallax_CheckBoundary BEFORE BG_Stream_Update in the same
    # frame, so the first sample showing Region_Current == subject also shows the arm.
    s0 = samples[i_in]
    if s0["target"] != F.S["bg_tiles"] and s0["current"] != F.S["bg_tiles"]:
        fails.append(f"{label} ARM: on the first sample inside the subject row the target is "
                     f"${s0['target']:06X} and Current ${s0['current']:06X}; neither names the "
                     f"subject's blob ${F.S['bg_tiles']:06X}")
    prev = None
    for k, s in enumerate(samples[i_in:], start=i_in):
        if len(s["arena_entries"]) > 2:
            fails.append(f"{label} tick {k}: {len(s['arena_entries'])} queued Deferrable entries "
                         f"write the BG arena; one outstanding chunk allows at most 2 (a "
                         f"128 KB split pair)")
        if prev is not None and s["offset"] > prev["offset"] and s["target"] == prev["target"]:
            step = s["offset"] - prev["offset"]
            if step > K.CHUNK:
                fails.append(f"{label} tick {k}: the offset advanced {step} B in one tick; one "
                             f"chunk is {K.CHUNK} B")
            if prev["arena_entries"]:
                fails.append(f"{label} tick {k}: a chunk was enqueued while an arena write was "
                             f"still queued at the tick before ({prev['arena_entries']})")
        prev = s
    done = [k for k, s in enumerate(samples) if s["current"] == F.S["bg_tiles"]]
    if not done:
        fails.append(f"{label}: the overwrite never completed in {len(samples) - i_in} ticks "
                     f"inside the subject row (last offset {samples[-1]['offset']} of "
                     f"{len(F.S_tiles)} B, {len(samples[-1]['arena_entries'])} arena entries "
                     f"queued)")
        return None
    k = done[0]
    if samples[k]["arena"] != F.S_tiles:
        bad = sum(1 for i in range(0, len(F.S_tiles), 32)
                  if samples[k]["arena"][i:i + 32] != F.S_tiles[i:i + 32])
        fails.append(f"{label}: BG_Tiles_Current named the subject's blob at tick {k} while "
                     f"{bad} of {len(F.S_tiles) // 32} arena tiles still differed")
    bound = n_chunks + 2 + slack
    took = k - i_in
    if took > bound:
        fails.append(f"{label}: the overwrite took {took} ticks; {n_chunks} chunks of "
                     f"{K.CHUNK} B allow {bound}")
    print(f"  {label}: {n_chunks} chunks of {K.CHUNK} B, completed {took} ticks after the "
          f"crossing (bound {bound})")
    return k


async def leg_transport(rig, F, K, fails):
    samples, i_in = await cross_into_subject(rig, F, K, tag="TRANSPORT")
    check_transport(samples, i_in, F, K, "TRANSPORT", fails, slack=0)


async def leg_traffic(rig, F, K, fails):
    sym = rig.sym
    cmd_sat = await rd(rig.b, sym["Static_Sprite_DMA"] + K.DMA_ENTRY["Command"], 4)
    sat = _const("engine/system/constants.emp", "VRAM_SPRITE_TABLE")
    if vdp_addr(cmd_sat) != sat:
        raise GateError(f"TRAFFIC: Static_Sprite_DMA's command decodes to "
                        f"${vdp_addr(cmd_sat):04X}, not VRAM_SPRITE_TABLE ${sat:04X}; the "
                        f"synthetic entry's command cannot be derived from it")
    cmd_base = cmd_sat ^ vdp_delta(sat)
    dest = K.FREE_TILE * 32
    src = F.S["bg_tiles"] + 2 + 32                   # an even ROM address with real art
    want = F.S_tiles[32:64]

    # POSITIVE CONTROL: the synthetic entry drains and lands, with no crossing in play.
    await rig.boot((F.left_centre[0], F.left_centre[1]))
    for _ in range(4):
        await rig.tick()
    before = await read_vram(rig.b, dest, 32)
    if before == want:
        raise GateError(f"TRAFFIC: free tile {K.FREE_TILE} already holds the synthetic "
                        f"source bytes, so a landing cannot be observed")
    if not await rig.append_synthetic(src, dest, cmd_base):
        raise GateError("TRAFFIC: the Deferrable queue was full at the control")
    await rig.tick()
    await rig.tick()
    q = await rig.queue()
    landed = await read_vram(rig.b, dest, 32)
    if any(e[0] == dest for e in q) or landed != want:
        raise GateError(f"TRAFFIC control: the synthetic entry did not drain and land within "
                        f"2 ticks (queued {[hex(e[0]) for e in q]}, tile {K.FREE_TILE} "
                        f"{'==' if landed == want else '!='} source) — the producer is not a "
                        f"real Deferrable entry and the leg would measure nothing")
    print(f"  TRAFFIC control: a synthetic 32 B entry to tile {K.FREE_TILE} drained and landed")

    appended = []

    async def per_tick(i):
        appended.append(await rig.append_synthetic(src, dest, cmd_base))

    samples, i_in = await cross_into_subject(rig, F, K, per_tick=per_tick, tag="TRAFFIC")
    busy = sum(1 for s in samples if s["queue"])
    if i_in is not None and not all(bool(s["queue"]) for s in samples[i_in:]):
        raise GateError("TRAFFIC: some sample after the crossing saw an EMPTY Deferrable queue; "
                        "the synthetic producer is not keeping the queue busy, so a global "
                        "queue-empty completion test would not be discriminated")
    print(f"  TRAFFIC: queue non-empty at {busy} of {len(samples)} samples; "
          f"{sum(appended)} synthetic entries appended")
    # Slack: the synthetic entry is 32 B per frame against a window thousands of bytes wide.
    check_transport(samples, i_in, F, K, "TRAFFIC", fails, slack=2)


STARVE_TICKS = 6


class Starver:
    """Holds the DMA window below one chunk for STARVE_TICKS ticks, once, starting at the first
    tick `when(sample)` is true: the budget poke of plan call C13. DMA_Budget_Default seeds
    DMA_Budget_Remaining at the top of every VInt_Level, so a value below the chunk keeps an
    enqueued chunk in the Deferrable queue for as long as it is held."""

    def __init__(self, rig, K, when):
        self.rig, self.K, self.when = rig, K, when
        self.addr = rig.sym["DMA_Budget_Default"]
        self.saved = None
        self.start = None
        self.ticks = 0

    async def step(self, i, last_sample):
        b = self.rig.b
        if self.start is None and last_sample is not None and self.when(last_sample):
            self.saved = await rd(b, self.addr, 2)
            await _c(b, "emulator/write_memory", {"addr": hex(self.addr),
                                                  "value": self.K.CHUNK - 2, "width": 2})
            self.start = i
        elif self.start is not None and self.saved is not None:
            self.ticks += 1
            if self.ticks >= STARVE_TICKS:
                await _c(b, "emulator/write_memory", {"addr": hex(self.addr),
                                                      "value": self.saved, "width": 2})
                self.saved = None


async def leg_transport_starved(rig, F, K, fails):
    """transport_under_a_starved_window_keeps_one_chunk_outstanding_and_completes_after_release"""
    holder = {"last": None}
    st = Starver(rig, K, lambda s: s["offset"] >= 2 * K.CHUNK)

    async def per_tick(i):
        await st.step(i, holder["last"])


    samples, i_in = await cross_into_subject(rig, F, K, per_tick=per_tick,
                                             tag="TRANSPORT-STARVED", on_sample=holder)
    if st.start is None:
        raise GateError("TRANSPORT-STARVED: the offset never reached two chunks, so the window "
                        "was never starved and the leg measured nothing")
    held = samples[st.start + 1:st.start + STARVE_TICKS]
    if not any(s["arena_entries"] for s in held):
        raise GateError("TRANSPORT-STARVED: no arena write stayed queued during the starved "
                        "window; the poke did not hold a chunk and the leg is not discriminating")
    print(f"  TRANSPORT-STARVED: window starved for {STARVE_TICKS} ticks from sample {st.start}; "
          f"arena entries queued at {sum(1 for s in held if s['arena_entries'])} of "
          f"{len(held)} held samples")
    check_transport(samples, i_in, F, K, "TRANSPORT-STARVED", fails, slack=STARVE_TICKS + 2)


LEGS = {"boot": leg_boot, "warp": leg_warp, "transport": leg_transport,
        "transport_starved": leg_transport_starved, "traffic": leg_traffic}


async def run(rom_path, lst_path, only):
    rom = Path(rom_path).read_bytes()
    K = Consts()
    sym = parse_lst(lst_path)
    need = ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update", "Boot_At_X", "Boot_At_Y",
            "Boot_At_Flag", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Camera_X",
            "Camera_Y", "BG_Tiles_Current", "BG_Tiles_Target", "BG_Tiles_Offset",
            "BG_Plane_Layout", "BG_Wipe_Cursor", "OJZ_Act1_Descriptor", "Region_Current",
            "DMA_Deferrable", "DMA_Deferrable_Slot", "DMA_Deferrable_End",
            "Static_Sprite_DMA", "DMA_Budget_Default")
    for nm in need:
        if nm not in sym:
            raise GateError(f"`{nm}` is not in {lst_path} — not the sonic4 DEBUG listing this "
                            f"gate reads")
    F = Fixture(rom, sym, K)
    print("GATE BG-SWITCH — a region's own tiles must be resident before its layout is shown")
    print(f"  ROM {rom_path} ({len(rom)} bytes)")
    print(f"  subject row {F.S['index']} [x {F.S['x0']}..{F.S['x1']}, y {F.S['y0']}..{F.S['y1']}]"
          f" tiles ${F.S['bg_tiles']:06X} ({len(F.S_tiles) // 32} tiles) layout "
          f"${F.S['bg_layout']:06X}; act tiles ${F.act_tiles_ptr:06X} "
          f"({len(F.A_tiles) // 32} tiles)")
    print(f"  neighbours: left row {F.left['index']}, above row {F.above['index']}")

    inst = AetherInstance(rom_path, symbols=lst_path)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise GateError(str(e)) from e
    b = BusClient(socket_path=sock, client_id="bgswitch", client_name="bg_switch_gate")
    fails = []
    ran = []
    try:
        await b.connect()
        for m in ("emulator/step", "emulator/run_to", "emulator/hold", "emulator/release_all",
                  "emulator/read_vram", "emulator/read_memory", "emulator/write_memory",
                  "emulator/reset"):
            if not b.supports(m):
                raise GateError(f"the server does not advertise `{m}`")
        await _c(b, "emulator/load_symbols", {"path": lst_path})
        rig = Rig(b, sym, K)
        for name, fn in LEGS.items():
            if only and name not in only:
                continue
            print(f"  -- leg {name.upper()}")
            await fn(rig, F, K, fails)
            ran.append(name)
    except GateError as e:
        if not fails:
            raise
        print(f"\n  REFUSED after reds were already collected:\n    {e}")
    finally:
        await b.close()
        inst.reap()

    print()
    for f in fails:
        print(f"  FAIL  {f}")
    print(f"legs run: {len(ran)} ({', '.join(ran)})")
    print(f"VERDICT: {'PASS' if not fails else 'FAIL'} ({len(fails)} failing assertions)")
    if fails:
        raise Failure(f"{len(fails)} assertions red")
    if only and set(only) - set(ran):
        raise GateError(f"asked for legs {sorted(set(only) - set(ran))}, which do not exist")


async def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--legs", default="", help="comma-separated subset of legs")
    a = ap.parse_args()
    only = [x.strip() for x in a.legs.split(",") if x.strip()]
    try:
        await run(a.rom, a.lst, only)
    except GateError as e:
        print(f"COULD NOT RUN: {e}")
        return 2
    except Failure:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
