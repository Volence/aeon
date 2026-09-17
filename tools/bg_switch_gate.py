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
         The same, with DMA_Budget_Default poked below the subject's smallest chunk (Fixture.STARVE) for STARVE_TICKS ticks once two
         chunks have gone, so a chunk is HELD in the queue. The only leg that can see the
         one-outstanding rule: on a calm frame every chunk drains in its own VBlank.
  TRAFFIC  the_overwrite_completes_while_another_producer_enqueues_a_deferrable_entry_every_frame
         A synthetic 32 B Deferrable entry to the map's free tile, appended every tick (positive
         control first). Red against a global queue-empty completion test (the draft's C2).

  ORDER  no_plane_b_row_shows_the_new_layout_before_vram_holds_the_new_tiles
         Every tick: no Plane B row holding a (discriminating) row of the subject's layout while
         the arena does not hold its tiles; the wipe cursor arms strictly after the tracker names
         the tiles; the settled plane and arena are the subject's.
  ORDER_STARVED  ...even_when_the_last_chunk_is_held_in_the_queue
         The window is starved from the tick that enqueues the LAST chunk, for a whole sweep's
         worth of ticks: while it is queued, BG_Tiles_Current and the cursor must stay 0. The leg
         that sees the Icecap inversion (completion taken without waiting for the last chunk).
  ORDER_VERTICAL  a_vertical_crossing_paints_no_new_layout_row_before_its_tiles_land
         ORDER on a DOWNWARD entry. It does NOT grade the streamer's suspension: the subject's
         layout is one plane tall, so the streamer's window is fixed at 0 and it paints nothing.
  REENTRANT  reversing_across_the_edge_mid_overwrite_retargets_and_settles_on_the_act_tiles
         Enter with the window starved (a chunk held), fly back out; the target names the act's
         tiles on the reverse crossing, and the run settles on the act's full tile blob and
         layout (no stale subject chunk lands after them). A timeout is FAIL, not COULD NOT RUN.
  CONTROL  a_crossing_between_two_act_default_rows_arms_no_overwrite
  POISON  an_overwrite_that_cancels_a_sweep_still_ends_with_the_whole_plane_repainted
         On a COPY of the ROM whose left neighbour is patched to show the subject's layout over
         the act's tiles: cancel the subject's sweep mid-flight by flying into that neighbour; the
         settled plane must be the subject's layout on every row. The only case where zeroing
         BG_Plane_Layout at the arm (plan C6) is what repaints the plane.

WHAT A GREEN HERE DOES NOT SAY: nothing about how the switch LOOKS, and nothing about the
steady-state streamer's suspension on a TALL map (no tiles-owning row in the DEBUG table has a
span; booked in docs/DEFERRED_WORK.md, REGION-BG-STREAMER-SUSPENSION-UNGRADED).

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
        # THE STARVATION BUDGET, DERIVED FROM THE SUBJECT BLOB (parcel/showcase-classic-bg).
        # Every starved leg pokes DMA_Budget_Default below a chunk so a chunk is HELD in the
        # queue. It used to poke CHUNK - 2, which holds a chunk only if that chunk is longer than
        # CHUNK - 2. The colonnade blob (6912 B = 3 x 1824 + 1440) still had a full chunk to send
        # past the two-chunk triggers; the Oil Ocean blob (3776 B = 2 x 1824 + 128) has only a
        # 128 B one, which CHUNK - 2 lets straight through, and WARP_MID went COULD NOT RUN
        # ("no subject chunk is held in the queue before the warp"). The chunk
        # lengths are the engine's own rule (BG_Stream_Update: min(CHUNK, bytes left)), so the
        # value that holds ANY chunk this subject sends is the smallest of them, minus 2.
        L = len(self.S_tiles)
        self.chunk_sizes = [min(K.CHUNK, L - o) for o in range(0, L, K.CHUNK)]
        self.STARVE = min(self.chunk_sizes) - 2
        if self.STARVE <= 0:
            raise GateError(f"the subject's smallest overwrite chunk is {min(self.chunk_sizes)} B; "
                            f"no DMA budget below it can still be a budget")
        # AND WHEN TO POKE IT, from the same list. A leg that pokes from the PREVIOUS tick's
        # sample (TRANSPORT_STARVED's Starver) lands its poke after the update that sample
        # preceded has already enqueued and drained a chunk, so to hold the LAST chunk it must
        # fire on the sample taken before the SECOND-TO-LAST one went: offset >= the start of
        # the second-to-last chunk. For a 4-chunk blob that is 2 x CHUNK, the value this leg
        # used to type; for the 3-chunk Oil Ocean blob it is 1 x CHUNK, and 2 x CHUNK fired one
        # chunk late and held nothing (measured: COULD NOT RUN, "no arena write stayed queued").
        if len(self.chunk_sizes) < 2:
            raise GateError(f"the subject's overwrite is {len(self.chunk_sizes)} chunk; the "
                            f"starved legs need a chunk still to send after one has gone")
        self.STARVE_AT = sum(self.chunk_sizes[:-2])
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


async def synthetic_cmd_base(rig, K, tag):
    """The VRAM-DMA command with its address bits cleared, derived from the booted machine's own
    static SAT entry. READ AFTER A BOOT: before one, that RAM holds whatever the previous run left
    (measured: $BDC96A93 read before a boot, $78000082 after), which once produced synthetic
    entries addressed to the wrong tile."""
    cmd_sat = await rd(rig.b, rig.sym["Static_Sprite_DMA"] + K.DMA_ENTRY["Command"], 4)
    sat = _const("engine/system/constants.emp", "VRAM_SPRITE_TABLE")
    if vdp_addr(cmd_sat) != sat:
        raise GateError(f"{tag}: Static_Sprite_DMA's command decodes to "
                        f"${vdp_addr(cmd_sat):04X}, not VRAM_SPRITE_TABLE ${sat:04X}; the "
                        f"synthetic entry's command cannot be derived from it")
    return cmd_sat ^ vdp_delta(sat)


async def leg_traffic(rig, F, K, fails):
    dest = K.FREE_TILE * 32
    src = F.S["bg_tiles"] + 2 + 32                   # an even ROM address with real art
    want = F.S_tiles[32:64]

    # POSITIVE CONTROL: the synthetic entry drains and lands, with no crossing in play.
    await rig.boot((F.left_centre[0], F.left_centre[1]))
    for _ in range(4):
        await rig.tick()
    cmd_base = await synthetic_cmd_base(rig, K, "TRAFFIC")
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
    # THE PEER SLIP (controller ruling 2026-09-16: the chunk is sized for liveness, and a
    # Deferrable peer may slip behind it). Measured: at each sample (taken after that tick's
    # append, before its VBlank) the number of synthetic entries queued is how many VBlanks the
    # OLDEST one will have waited if it is sent in this frame's VBlank, so its maximum over the
    # run is the peer wait W in frames (1 = sent in the VBlank of the frame it was enqueued).
    # Derived bound: the drain is FIFO and stops at the first entry that does not fit, and one
    # chunk is outstanding at a time. The chunk enqueued THIS frame sits BEHIND this frame's
    # peer (BG_Stream_Update runs after the top-of-Update append), so only a chunk left over
    # from an earlier VBlank can be ahead of a peer. With H = the longest run of consecutive
    # samples showing a leftover arena write, a peer waits at most H + 1 frames. A peer can
    # also fail to fit on its own (window exhausted by other riders); the traffic entry is 32 B
    # on calm free-flight frames, where that is not the case, so a W above H + 1 is red.
    wait = max((sum(1 for e in s["queue"] if e[0] == dest) for s in samples), default=0)
    runs, cur = [], 0
    for s in samples:
        cur = cur + 1 if s["arena_entries"] else 0
        runs.append(cur)
    held = max(runs, default=0)
    if wait > held + 1:
        fails.append(f"TRAFFIC peer slip: a synthetic Deferrable entry waited {wait} frames from "
                     f"enqueue to send; the longest leftover chunk run was {held} frame(s), so "
                     f"the FIFO-behind-one-chunk mechanism allows at most {held + 1}")
    print(f"  TRAFFIC peer slip: measured max wait {wait} frame(s) from enqueue to send; longest "
          f"run of a chunk left over at the queue head {held}; derived bound {held + 1}")
    # Slack: the synthetic entry is 32 B per frame against a window thousands of bytes wide.
    check_transport(samples, i_in, F, K, "TRAFFIC", fails, slack=2)


STARVE_TICKS = 6


class Starver:
    """Holds the DMA window below the subject's smallest chunk for STARVE_TICKS ticks, once, starting at the first
    tick `when(sample)` is true: the budget poke of plan call C13. DMA_Budget_Default seeds
    DMA_Budget_Remaining at the top of every VInt_Level, so a value below the chunk keeps an
    enqueued chunk in the Deferrable queue for as long as it is held."""

    def __init__(self, rig, F, K, when):
        self.rig, self.F, self.K, self.when = rig, F, K, when
        self.addr = rig.sym["DMA_Budget_Default"]
        self.saved = None
        self.start = None
        self.ticks = 0

    async def step(self, i, last_sample):
        b = self.rig.b
        if self.start is None and last_sample is not None and self.when(last_sample):
            self.saved = await rd(b, self.addr, 2)
            await _c(b, "emulator/write_memory", {"addr": hex(self.addr),
                                                  "value": self.F.STARVE, "width": 2})
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
    st = Starver(rig, F, K, lambda s: s["offset"] >= F.STARVE_AT)

    async def per_tick(i):
        await st.step(i, holder["last"])


    samples, i_in = await cross_into_subject(rig, F, K, per_tick=per_tick,
                                             tag="TRANSPORT-STARVED", on_sample=holder)
    if st.start is None:
        raise GateError(f"TRANSPORT-STARVED: the offset never reached {F.STARVE_AT} B, so the window "
                        "was never starved and the leg measured nothing")
    held = samples[st.start + 1:st.start + STARVE_TICKS]
    if not any(s["arena_entries"] for s in held):
        raise GateError("TRANSPORT-STARVED: no arena write stayed queued during the starved "
                        "window; the poke did not hold a chunk and the leg is not discriminating")
    print(f"  TRANSPORT-STARVED: window starved for {STARVE_TICKS} ticks from sample {st.start}; "
          f"arena entries queued at {sum(1 for s in held if s['arena_entries'])} of "
          f"{len(held)} held samples")
    check_transport(samples, i_in, F, K, "TRANSPORT-STARVED", fails, slack=STARVE_TICKS + 2)


# ---------------------------------------------------------------------------
# TASK 4 — the ORDERING legs. Each samples Plane B and the arena every tick.
# ---------------------------------------------------------------------------
ROW = None   # set from K in the helpers below


async def drive(rig, F, K, start, script, max_ticks, tag):
    """Boot at `start`, settle, then one tick at a time: `await script(i, samples)` returns
    (button-or-None, done). Every sample carries the plane, the arena and the trackers."""
    await rig.boot(start)
    for _ in range(4):
        await rig.tick()
    samples, held = [], "unset"
    try:
        for i in range(max_ticks):
            s = await sample_ow(rig, F, K)
            s["plane"] = await read_vram(rig.b, K.VRAM_PLANE_B, K.PLANE_BYTES)
            s["region_row"] = next((r["index"] for r in F.rows if r["addr"] == s["region"]), None)
            samples.append(s)
            button, done = await script(i, samples)
            if done:
                return samples
            if button != held:
                await rig.hold(button)
                held = button
            await rig.tick()
    finally:
        await rig.hold(None)
    raise GateError(f"{tag}: the route did not finish in {max_ticks} ticks (last region row "
                    f"{samples[-1]['region_row']}, target ${samples[-1]['target']:06X}, current "
                    f"${samples[-1]['current']:06X}, cursor {samples[-1]['cursor']})")


def rows_of(blob, K):
    n = K.PLANE_H_CELLS * 2
    return [blob[p * n:(p + 1) * n] for p in range(K.PLANE_V_CELLS)]


def check_order(samples, F, K, label, fails, new_layout, new_tiles, old_layout):
    """THE ORDERING INVARIANT: on no sampled tick may a Plane B row hold a row of the NEW
    layout (one that differs from the OLD layout's same row) while the arena does not hold the
    NEW tiles; and the sweep may not arm before the tiles are named current."""
    new_rows, old_rows = rows_of(new_layout, K), rows_of(old_layout, K)
    discriminating = [p for p in range(K.PLANE_V_CELLS) if new_rows[p] != old_rows[p]]
    if not discriminating:
        raise GateError(f"{label}: the new and old layouts agree on every plane row")
    first_bad = None
    for k, s in enumerate(samples):
        prow = rows_of(s["plane"], K)
        shown = [p for p in discriminating if prow[p] == new_rows[p]]
        if shown and s["arena"][:len(new_tiles)] != new_tiles:
            if first_bad is None:
                first_bad = (k, shown)
    if first_bad:
        k, shown = first_bad
        fails.append(f"{label}: at tick {k} Plane B shows {len(shown)} row(s) of the new layout "
                     f"(first plane row {shown[0]}) while the BG arena does not hold the new "
                     f"tiles — the repaint ran ahead of the overwrite")
    done = next((k for k, s in enumerate(samples) if s["current"] == F.S["bg_tiles"]), None)
    armed = next((k for k, s in enumerate(samples) if s["cursor"]), None)
    if armed is not None and (done is None or armed < done):
        fails.append(f"{label}: the wipe cursor armed at tick {armed}, "
                     f"{'before' if done is not None else 'and'} the tile tracker named the new "
                     f"blob{' at tick %d' % done if done is not None else ' never'}")
    return done, armed


async def leg_order(rig, F, K, fails):
    """no_plane_b_row_shows_the_new_layout_before_vram_holds_the_new_tiles"""
    run_up = 8 * K.FLY
    start = (F.S["x0"] - run_up, F.centre[1])
    state = {"in": None, "done": None}

    async def script(i, S):
        s = S[-1]
        if state["in"] is None and s["region"] == F.S["addr"]:
            state["in"] = i
        if s["current"] == F.S["bg_tiles"] and state["done"] is None:
            state["done"] = i
        if state["done"] is not None and s["cursor"] == 0 and i > state["done"] + 1:
            return None, True
        button = "right" if state["in"] is None or i - state["in"] < 8 else None
        return button, False

    samples = await drive(rig, F, K, start, script, 200, "ORDER")
    check_order(samples, F, K, "ORDER", fails, F.S_layout, F.S_tiles, F.A_layout)
    end = samples[-1]
    if end["plane"] != F.S_layout or end["arena"] != F.S_tiles:
        fails.append("ORDER: after the sweep retired, Plane B / the arena do not hold the subject's "
                     "layout / tiles")
    print(f"  ORDER: entered at tick {state['in']}, tiles settled at {state['done']}, sweep "
          f"retired by {len(samples) - 1}")


async def leg_order_starved(rig, F, K, fails):
    """no_plane_b_row_shows_the_new_layout_even_when_the_last_chunk_is_held_in_the_queue"""
    run_up = 8 * K.FLY
    start = (F.S["x0"] - run_up, F.centre[1])
    state = {"in": None, "done": None, "hold_from": None, "saved": None}
    addr = rig.sym["DMA_Budget_Default"]
    HOLD = K.WIPE_FRAMES

    async def script(i, S):
        s = S[-1]
        if state["in"] is None and s["region"] == F.S["addr"]:
            state["in"] = i
        # Starve from the tick whose update will enqueue the LAST chunk (at most one chunk left,
        # nothing queued): the poke is read at the top of THIS frame's VBlank, so the last chunk
        # is held in the queue — the exact window the Icecap inversion needs. Sampled at the top
        # of Update, "every byte already enqueued" would be one VBlank too late: that chunk has
        # already drained.
        if (state["hold_from"] is None and state["in"] is not None
                and s["target"] == F.S["bg_tiles"] and s["current"] == 0
                and 0 < len(F.S_tiles) - s["offset"] <= K.CHUNK and not s["arena_entries"]):
            state["saved"] = await rd(rig.b, addr, 2)
            await _c(rig.b, "emulator/write_memory", {"addr": hex(addr), "value": F.STARVE,
                                                      "width": 2})
            state["hold_from"] = i
        if state["hold_from"] is not None and state["saved"] is not None \
                and i - state["hold_from"] >= HOLD:
            await _c(rig.b, "emulator/write_memory", {"addr": hex(addr), "value": state["saved"],
                                                      "width": 2})
            state["saved"] = None
        if s["current"] == F.S["bg_tiles"] and state["done"] is None:
            state["done"] = i
        if state["done"] is not None and s["cursor"] == 0 and i > state["done"] + 1:
            return None, True
        return ("right" if state["in"] is None or i - state["in"] < 8 else None), False

    samples = await drive(rig, F, K, start, script, 260, "ORDER_STARVED")
    if state["hold_from"] is None:
        raise GateError("ORDER_STARVED: the last chunk was never observed in flight, so nothing "
                        "was starved")
    h = state["hold_from"]
    held = samples[h + 1:h + HOLD]
    if not any(s["arena_entries"] for s in held):
        raise GateError("ORDER_STARVED: no arena write stayed queued while starved; the leg "
                        "did not hold the last chunk and cannot discriminate")
    for k, s in enumerate(held, start=h + 1):
        if s["arena_entries"] and (s["current"] or s["cursor"]):
            fails.append(f"ORDER_STARVED tick {k}: the last chunk is still queued but "
                         f"BG_Tiles_Current=${s['current']:06X}, BG_Wipe_Cursor={s['cursor']}")
            break
    check_order(samples, F, K, "ORDER_STARVED", fails, F.S_layout, F.S_tiles, F.A_layout)
    print(f"  ORDER_STARVED: last chunk held from tick {h} for {HOLD} ticks; arena write queued at "
          f"{sum(1 for s in held if s['arena_entries'])} of {len(held)} held samples; settled "
          f"at {state['done']}")


async def leg_order_vertical(rig, F, K, fails):
    """a_vertical_crossing_paints_no_new_layout_row_before_its_tiles_land"""
    run_up = 8 * K.FLY
    start = (F.centre[0], F.S["y0"] - run_up)
    state = {"in": None, "done": None}

    async def script(i, S):
        s = S[-1]
        if state["in"] is None and s["region"] == F.S["addr"]:
            state["in"] = i
        if s["current"] == F.S["bg_tiles"] and state["done"] is None:
            state["done"] = i
        if state["done"] is not None and s["cursor"] == 0 and i > state["done"] + 1:
            return None, True
        return ("down" if state["in"] is None or i - state["in"] < 8 else None), False

    samples = await drive(rig, F, K, start, script, 200, "ORDER_VERTICAL")
    vs = {s.get("vscroll") for s in samples}
    check_order(samples, F, K, "ORDER_VERTICAL", fails, F.S_layout, F.S_tiles, F.A_layout)
    # WHAT THIS LEG CANNOT GRADE, measured rather than assumed: the steady-state streamer only
    # paints when want_top moves, and want_top is clamped to [0, map_rows - PLANE_V_CELLS]. The
    # subject's layout is one plane tall (rg_bg_span 0), so want_top is 0 on every frame and the
    # streamer paints nothing on this route whether or not the overwrite suspends it.
    print(f"  ORDER_VERTICAL: entered at {state['in']}, settled at {state['done']} (subject span "
          f"{F.S['bg_span']}: the streamer's window is fixed at 0 here, so this leg grades the "
          f"wipe's ordering on a vertical entry, NOT the streamer's suspension)")


async def leg_reentrant(rig, F, K, fails):
    """reversing_across_the_edge_mid_overwrite_retargets_and_settles_on_the_act_tiles"""
    run_up = 8 * K.FLY
    start = (F.S["x0"] - run_up, F.centre[1])
    st = {"in": None, "back": None, "retarget": None, "saved": None, "settled": None}
    addr = rig.sym["DMA_Budget_Default"]

    async def script(i, S):
        s = S[-1]
        if st["in"] is None and s["region"] == F.S["addr"]:
            st["in"] = i
            st["saved"] = await rd(rig.b, addr, 2)             # starve: hold a chunk queued
            await _c(rig.b, "emulator/write_memory", {"addr": hex(addr), "value": F.STARVE,
                                                      "width": 2})
        if st["in"] is not None and st["back"] is None and s["region"] == F.left["addr"]:
            st["back"] = i
        if st["back"] is not None and st["retarget"] is None and s["target"] == F.act_tiles_ptr:
            st["retarget"] = i
        if st["back"] is not None and st["saved"] is not None and i - st["back"] >= 2:
            await _c(rig.b, "emulator/write_memory", {"addr": hex(addr), "value": st["saved"],
                                                      "width": 2})
            st["saved"] = None
        if (st["back"] is not None and s["current"] == F.act_tiles_ptr and s["cursor"] == 0
                and s["target"] == 0):
            st["settled"] = i
            return None, True
        if st["in"] is None:
            return "right", False
        if st["back"] is None:
            return ("right" if i - st["in"] < 4 else "left"), False
        return None, False

    bound = 40 + 2 * (-(-len(F.S_tiles) // K.CHUNK)) + K.WIPE_FRAMES
    samples = await drive(rig, F, K, start, script, bound + 80, "REENTRANT")
    if st["back"] is None:
        raise GateError("REENTRANT: the route never came back out of the subject row")
    mid = samples[st["back"]]
    if mid["current"] == F.S["bg_tiles"]:
        raise GateError("REENTRANT: the forward overwrite had already completed when the camera "
                        "came back out; the reversal was not mid-overwrite")
    if st["retarget"] is None or st["retarget"] > st["back"]:
        fails.append(f"REENTRANT: the reverse crossing was sampled at tick {st['back']} but the "
                     f"target named the act's tiles only at {st['retarget']}")
    end = samples[-1]
    if end["arena"][:len(F.S_tiles)] != F.A_tiles[:len(F.S_tiles)] or \
            end["plane"] != F.A_layout:
        fails.append("REENTRANT: after settling, the arena does not hold the act's tiles or Plane "
                     "B does not hold the act's layout")
    full = await read_vram(rig.b, K.BG_TILE_BASE_VRAM, len(F.A_tiles))
    if full != F.A_tiles:
        fails.append("REENTRANT: after settling, the full act tile blob is not in the arena (a "
                     "stale showcase chunk landed after the act's)")
    print(f"  REENTRANT: in at {st['in']}, back out at {st['back']} (offset "
          f"{mid['offset']} of {len(F.S_tiles)}), retarget seen at {st['retarget']}, settled at "
          f"{st['settled']}")


async def leg_control(rig, F, K, fails):
    """a_crossing_between_two_act_default_rows_arms_no_overwrite"""
    run_up = 8 * K.FLY
    x = (F.left["x0"] + F.left["x1"]) // 2
    start = (x, F.left["y0"] + run_up)
    above = region_table.region_at(F.rows, x, F.left["y0"] - 1)
    if above is None or above["bg_tiles"] or above["bg_layout"]:
        raise GateError("CONTROL: the row above the left neighbour is not act-default")
    st = {"out": None}

    async def script(i, S):
        s = S[-1]
        if st["out"] is None and s["region"] == above["addr"]:
            st["out"] = i
        if st["out"] is not None and i - st["out"] >= 8:
            return None, True
        return "up", False

    samples = await drive(rig, F, K, start, script, 200, "CONTROL")
    bad = [k for k, s in enumerate(samples) if s["target"] or s["offset"] or not s["current"]]
    if bad:
        fails.append(f"CONTROL: crossing row {F.left['index']} -> row {above['index']} (both act "
                     f"default) touched the tile tracker at ticks {bad[:4]}")
    print(f"  CONTROL: row {F.left['index']} -> row {above['index']}, {len(samples)} ticks, tracker "
          f"untouched: {not bad}")


async def leg_poison(rig, F, K, fails):
    """an_overwrite_that_cancels_a_sweep_still_ends_with_the_whole_plane_repainted

    The one case where C6 (zero BG_Plane_Layout at arm) is the only thing that repaints the plane:
    a sweep for layout L is cancelled by an overwrite for a region whose layout pointer IS L. It
    needs a second row showing the subject's layout with DIFFERENT tiles, which the shipped DEBUG
    table does not have, so this leg patches a COPY of the ROM on disk: the left neighbour's
    rg_bg_layout := the subject's layout (its tiles stay the act's). Route: fly DOWN from the row
    above into the subject near its left edge, let the tiles settle and the sweep start, then fly
    LEFT into the patched neighbour mid-sweep."""
    import tempfile
    ro, _ = region_table.region_layout()
    L = F.left
    off = L["addr"] + ro["rg_bg_layout"]
    image = bytearray(rig.rom)
    image[off:off + 4] = F.S["bg_layout"].to_bytes(4, "big")
    tmp = tempfile.mkdtemp(prefix="bgswitch-poison-")
    patched = Path(tmp) / Path(rig.rom_path).name
    patched.write_bytes(bytes(image))
    x = F.S["x0"] + 3 * K.FLY
    above = region_table.region_at(F.rows, x, F.S["y0"] - 1)
    start = (x, F.S["y0"] - 8 * K.FLY)
    st = {"in": None, "sweep": None, "left": None, "settled": None}
    async with open_rig(str(patched), rig.lst_path, rig.sym, K) as r2:
        live = bytes.fromhex(await read_bytes(r2.b, off, 4))
        if int.from_bytes(live, "big") != F.S["bg_layout"]:
            raise GateError(f"POISON: the emulator's cart holds ${live.hex()} at {off:#x}, not the "
                            f"patched layout pointer")

        async def script(i, S):
            s = S[-1]
            if st["in"] is None and s["region"] == F.S["addr"]:
                st["in"] = i
            if st["in"] is not None and st["sweep"] is None and s["cursor"] and \
                    s["current"] == F.S["bg_tiles"]:
                st["sweep"] = i
            if st["sweep"] is not None and st["left"] is None and s["region"] == L["addr"]:
                st["left"] = i
            if (st["left"] is not None and s["current"] == F.act_tiles_ptr and s["cursor"] == 0
                    and i > st["left"] + 2):
                st["settled"] = i
                return None, True
            if st["in"] is None:
                return "down", False
            if st["sweep"] is None:
                return None, False
            if st["left"] is None:
                return "left", False
            return None, False

        samples = await drive(r2, F, K, start, script, 300, "POISON")
    if st["left"] is None or samples[st["left"] - 1]["cursor"] == 0:  # the tick BEFORE: the arm clears the cursor in the crossing frame
        raise GateError(f"POISON: the camera entered the patched neighbour at tick {st['left']} "
                        f"with no sweep in flight; the leg did not cancel a sweep")
    end = samples[-1]
    if end["plane"] != F.S_layout:
        bad = sum(1 for a, b in zip(rows_of(end["plane"], K), rows_of(F.S_layout, K)) if a != b)
        fails.append(f"POISON: after the overwrite back to the act's tiles settled, {bad} of "
                     f"{K.PLANE_V_CELLS} Plane B rows do not hold the patched neighbour's layout "
                     f"(the subject's) — the cancelled sweep was never re-armed")
    print(f"  POISON: in at {st['in']}, sweep at {st['sweep']}, into patched neighbour at "
          f"{st['left']} (cursor the tick before: {samples[st['left'] - 1]['cursor']}), settled at {st['settled']}")


async def leg_warp_mid(rig, F, K, fails):
    """a_warp_during_an_overwrite_leaves_vram_holding_the_warp_targets_tiles_and_keeps_other_entries

    Cross into the subject with the window starved (a subject chunk held in the queue), append one
    synthetic NON-arena Deferrable entry (TRAFFIC's producer), warp to the act-default neighbour,
    then release the window. After the warp: the synthetic entry is still queued; after release it
    lands on the free tile; the arena ends holding the act's FULL tile blob (a held subject chunk
    landing after the synchronous copy would break it) and the trackers agree."""
    sym = rig.sym
    dest = K.FREE_TILE * 32
    src = F.S["bg_tiles"] + 2 + 64                   # a different 32 B than TRAFFIC's control
    want = F.S_tiles[64:96]
    addr = sym["DMA_Budget_Default"]
    run_up = 8 * K.FLY
    await rig.boot((F.S["x0"] - run_up, F.centre[1]))
    for _ in range(4):
        await rig.tick()
    cmd_base = await synthetic_cmd_base(rig, K, "WARP_MID")
    if await read_vram(rig.b, dest, 32) == want:
        raise GateError("WARP_MID: the free tile already holds the synthetic source bytes")
    saved = await rd(rig.b, addr, 2)
    await rig.hold("right")
    inside = False
    for i in range(80):
        s = await sample_ow(rig, F, K, with_arena=False)
        if s["region"] == F.S["addr"] and s["offset"] >= 2 * K.CHUNK and not inside:
            inside = True
            await rig.hold(None)
            await _c(rig.b, "emulator/write_memory", {"addr": hex(addr), "value": F.STARVE,
                                                      "width": 2})
            await rig.tick()
            await rig.tick()
            break
        await rig.tick()
    await rig.hold(None)
    if not inside:
        raise GateError("WARP_MID: never reached two chunks inside the subject row")
    s = await sample_ow(rig, F, K, with_arena=False)
    if not s["arena_entries"]:
        raise GateError("WARP_MID: no subject chunk is held in the queue before the warp; the leg "
                        "cannot tell a cancelled overwrite from a finished one")
    if not await rig.append_synthetic(src, dest, cmd_base):
        raise GateError("WARP_MID: the Deferrable queue was full")
    before = await rig.queue()
    await rig.warp(F.left_centre)
    after = await sample_ow(rig, F, K, with_arena=False)
    # Kept = still queued, OR already SENT (it landed on the free tile). With the liveness-sized
    # chunk the starved window (CHUNK - 2 B) still admits a 32 B entry, so it can legitimately
    # drain in the warp frame's VBlank; a DROPPED entry is neither queued nor ever lands.
    kept = [e for e in after["queue"] if e[0] == dest]
    if not kept and await read_vram(rig.b, dest, 32) == want:
        kept = ["sent"]
    if not kept:
        fails.append(f"WARP_MID: the synthetic non-arena entry (dest ${dest:04X}) is gone from the "
                     f"queue after the warp; the cancel dropped an entry that does not write the "
                     f"BG arena (queue before {[hex(e[0]) for e in before]}, after "
                     f"{[hex(e[0]) for e in after['queue']]})")
    if after["arena_entries"]:
        fails.append(f"WARP_MID: {len(after['arena_entries'])} arena write(s) still queued after "
                     f"the warp's synchronous copy")
    if after["target"] or after["current"] != F.act_tiles_ptr:
        fails.append(f"WARP_MID: after the warp target=${after['target']:06X} "
                     f"current=${after['current']:06X}; want 0 and the act's blob")
    await _c(rig.b, "emulator/write_memory", {"addr": hex(addr), "value": saved, "width": 2})
    for _ in range(-(-len(F.S_tiles) // K.CHUNK) + 4):
        await rig.tick()
    arena = await read_vram(rig.b, K.BG_TILE_BASE_VRAM, len(F.A_tiles))
    if arena != F.A_tiles:
        bad = sum(1 for i in range(0, len(F.A_tiles), 32) if arena[i:i + 32] != F.A_tiles[i:i + 32])
        fails.append(f"WARP_MID: after the window was released {bad} of {len(F.A_tiles) // 32} arena "
                     f"tiles differ from the act's blob — a held subject chunk landed after the "
                     f"warp's synchronous copy")
    landed = await read_vram(rig.b, dest, 32)
    if kept and landed != want:
        fails.append("WARP_MID: the kept synthetic entry never landed on the free tile")
    print(f"  WARP_MID: {len(s['arena_entries'])} subject chunk(s) held at the warp; after it "
          f"{len(after['arena_entries'])} arena write(s) and {len(kept)} synthetic entry kept; "
          f"arena {'==' if arena == F.A_tiles else '!='} act tiles after release")


async def band_record(rig, name):
    """A DEBUG band-table view out of the ROM: count word, then the first 44-byte bganim_band
    record (driver, rate_shift, step_mask, col_shift, tile_count, vram_dest, 8 bank pointers)."""
    at = rig.sym[name]
    rom = rig.rom
    n = int.from_bytes(rom[at:at + 2], "big")
    if n < 1:
        raise GateError(f"{name} holds {n} bands")
    w = [int.from_bytes(rom[at + 2 + 2 * i:at + 4 + 2 * i], "big") for i in range(6)]
    banks = [int.from_bytes(rom[at + 14 + 4 * i:at + 18 + 4 * i], "big") for i in range(8)]
    return {"addr": at, "driver": w[0], "rate_shift": w[1], "step_mask": w[2], "col_shift": w[3],
            "tiles": w[4], "dest": w[5], "banks": banks}


async def set_band_table(rig, name):
    await _c(rig.b, "emulator/write_memory", {"addr": hex(rig.sym["BgAnim_Table_Ptr"]),
                                              "value": rig.sym[name], "width": 4})
    for off in (0, 4):
        await _c(rig.b, "emulator/write_memory", {"addr": hex(rig.sym["BgAnim_LastStep"] + off),
                                                  "value": 0xFFFFFFFF, "width": 4})


def band_phase_art(rig, rec, step):
    """What bg_anim.emp's two DMAs leave in the band's slots for `step` (header's rule)."""
    total = rec["tiles"] * 32
    fine = step & 7
    shift = (step >> 3) << rec["col_shift"]
    bank = rig.rom[rec["banks"][fine]:rec["banks"][fine] + total]
    return bank[shift:] + bank[:shift]


async def leg_bands(rig, F, K, fails):
    """no_band_write_lands_in_the_arena_while_a_region_with_its_own_tiles_is_resident_and_bands_resync

    Two band views from the DEBUG lab's own tables (BgAnim_View_T, timer-driven; BgAnim_View_H,
    camera-X-driven), pointed at through BgAnim_Table_Ptr as the lab does. (1) With View_T bands
    write every few ticks: positive control first. Cross into the subject; once its tiles and
    sweep settle, the arena must equal the subject's blob on every tick of a band period, twice.
    (2) Switch to View_H while inside, fly back out and STOP. At the tick the last act chunk is
    about to be enqueued, set BgAnim_LastStep[0] to the step the still camera selects (so a band
    that is NOT invalidated at completion has no step change to re-send on). After settling, the
    band slots must hold that step's phase art."""
    sym = rig.sym
    T = await band_record(rig, "BgAnim_View_T")
    H = await band_record(rig, "BgAnim_View_H")
    if T["dest"] != K.BG_TILE_BASE_VRAM or H["dest"] != K.BG_TILE_BASE_VRAM:
        raise GateError("BANDS: the lab's band views do not start at the BG arena")
    nb = T["tiles"] * 32
    run_up = 8 * K.FLY
    await rig.boot((F.S["x0"] - run_up, F.centre[1]))
    for _ in range(4):
        await rig.tick()
    await set_band_table(rig, "BgAnim_View_T")
    seen = set()
    for _ in range(4 * (1 << T["rate_shift"])):
        await rig.tick()
        seen.add(await read_vram(rig.b, K.BG_TILE_BASE_VRAM, nb))
    if len(seen) < 2:
        raise GateError("BANDS control: with View_T selected the band slots never changed; the "
                        "bands are not running and the leg cannot see them")
    print(f"  BANDS control: View_T wrote {len(seen)} distinct band images in "
          f"{4 << T['rate_shift']} ticks")
    # (1) cross in, settle, watch.
    await rig.hold("right")
    inside, settled_at = None, None
    for i in range(200):
        s = await sample_ow(rig, F, K, with_arena=False)
        if inside is None and s["region"] == F.S["addr"]:
            inside = i
        if inside is not None and i - inside == 8:
            await rig.hold(None)
        if s["current"] == F.S["bg_tiles"] and s["cursor"] == 0 and i > (inside or 0) + 8:
            settled_at = i
            break
        await rig.tick()
    await rig.hold(None)
    if settled_at is None:
        raise GateError("BANDS: the subject never settled")
    period = 2 << T["rate_shift"]
    for k in range(2 * period):
        arena = await read_vram(rig.b, K.BG_TILE_BASE_VRAM, len(F.S_tiles))
        if arena != F.S_tiles:
            bad = sum(1 for i in range(0, nb, 32) if arena[i:i + 32] != F.S_tiles[i:i + 32])
            fails.append(f"BANDS: {k} ticks after the subject settled, {bad} of {T['tiles']} band "
                         f"slots no longer hold the subject's tiles — a band DMA wrote the arena "
                         f"while it held a region's own art")
            break
        await rig.tick()
    else:
        print(f"  BANDS hold: arena == subject tiles for {2 * period} ticks with View_T running")
    # (2) resync.
    await set_band_table(rig, "BgAnim_View_H")
    await rig.hold("left")
    out, poked, done = None, False, None
    for i in range(300):
        s = await sample_ow(rig, F, K, with_arena=False)
        if out is None and s["region"] == F.left["addr"]:
            out = i
        if out is not None and i - out == 1:
            await rig.hold(None)
        if (out is not None and i - out >= 3 and not poked and s["current"] == 0
                and s["target"] == F.act_tiles_ptr
                and 0 < len(F.A_tiles) - s["offset"] <= K.CHUNK and not s["arena_entries"]):
            camx = (await rd(rig.b, sym["Camera_X"], 4)) >> 16
            step = (camx >> H["rate_shift"]) & H["step_mask"]
            await _c(rig.b, "emulator/write_memory", {"addr": hex(sym["BgAnim_LastStep"]),
                                                      "value": step, "width": 2})
            poked = step
        if poked is not False and s["current"] == F.act_tiles_ptr:
            done = i
            break
        await rig.tick()
    await rig.hold(None)
    if poked is False or done is None:
        raise GateError(f"BANDS resync: never reached the act's last chunk with the camera still "
                        f"(out {out}, poked {poked}, done {done})")
    for _ in range(3):
        await rig.tick()
    camx = (await rd(rig.b, sym["Camera_X"], 4)) >> 16
    step = (camx >> H["rate_shift"]) & H["step_mask"]
    want = band_phase_art(rig, H, step)
    static = F.A_tiles[:nb]
    if want == static:
        raise GateError(f"BANDS resync: step {step}'s phase art equals the act's static front "
                        f"tiles, so a band that never re-sent reads the same")
    got = await read_vram(rig.b, K.BG_TILE_BASE_VRAM, nb)
    if step != poked:
        raise GateError(f"BANDS resync: the camera moved after the poke (step {poked} -> {step})")
    if got != want:
        what = "the act's static (phase-0) art" if got == static else "neither"
        fails.append(f"BANDS resync: back on the act's tiles with the camera still at step {step}, "
                     f"the band slots hold {what}, not step {step}'s phase art — the bands were "
                     f"not made to re-send when the hold released")
    print(f"  BANDS resync: step {step}, band slots {'==' if got == want else '!='} phase art")


LEGS = {"boot": leg_boot, "warp": leg_warp, "warp_mid": leg_warp_mid, "transport": leg_transport,
        "transport_starved": leg_transport_starved, "traffic": leg_traffic,
        "order": leg_order, "order_starved": leg_order_starved,
        "order_vertical": leg_order_vertical, "reentrant": leg_reentrant,
        "control": leg_control, "poison": leg_poison, "bands": leg_bands}


async def _measure_route(rig, F, K, start, button, axis, tag):
    """M-A on one route: ticks from the crossing to (a) the arena settled, (b) every VISIBLE plane
    row holding the subject's layout, (c) the sweep retired. Also counts VBlanks (Frame_Counter)
    across the same span so lag is reported, not assumed away."""
    sym = rig.sym
    C = "engine/system/constants.emp"
    screen_h = _const(C, "SCREEN_HEIGHT")
    row_px = 8
    vis_rows = screen_h // row_px + 1                 # engine/level/bg.emp BG_SCREEN_ROWS
    st = {"in": None, "settled": None, "visible": None, "retired": None, "f0": None}
    new_rows = rows_of(F.S_layout, K)
    cam_path = []

    async def script(i, S):
        s = S[-1]
        cam = ((await rd(rig.b, sym["Camera_X"], 4)) >> 16, (await rd(rig.b, sym["Camera_Y"], 4)) >> 16)
        cam_path.append(cam)
        if st["in"] is None and s["region"] == F.S["addr"]:
            st["in"] = i
            st["f0"] = await rd(rig.b, sym["Frame_Counter"], 2)
        if st["in"] is not None:
            if st["settled"] is None and s["current"] == F.S["bg_tiles"]:
                st["settled"] = i
            if st["settled"] is not None and st["visible"] is None:
                vs = await rd(rig.b, sym["Parallax_Current_Vscroll_BG"], 2)
                top = (vs >> 3) & (K.PLANE_V_CELLS - 1)
                prow = rows_of(s["plane"], K)
                if all(prow[(top + k) % K.PLANE_V_CELLS] == new_rows[(top + k) % K.PLANE_V_CELLS]
                       for k in range(vis_rows)):
                    st["visible"] = i
            if st["settled"] is not None and st["retired"] is None and s["cursor"] == 0 \
                    and i > st["settled"]:
                st["retired"] = i
                st["f1"] = await rd(rig.b, sym["Frame_Counter"], 2)
                return None, True
        return (button if st["in"] is None or i - st["in"] < 8 else None), False

    await drive(rig, F, K, start, script, 300, tag)
    vblanks = (st["f1"] - st["f0"]) & 0xFFFF
    ticks = st["retired"] - st["in"]
    moved = cam_path[st["in"] + 8][axis] - cam_path[st["in"]][axis] if len(cam_path) > st["in"] + 8 else None
    print(f"  {tag}: crossing at tick {st['in']}; arena settled +{st['settled'] - st['in']} ticks; "
          f"all {vis_rows} visible rows repainted +{st['visible'] - st['in']} ticks; sweep retired "
          f"+{ticks} ticks ({vblanks} VBlanks over the same span, lag frames = {vblanks - ticks}); "
          f"camera moved {moved} px on its axis in the first 8 ticks inside")
    return st


async def leg_measure(rig, F, K, fails):
    """M-A, measurement only (no assertions): run with --legs measure."""
    run_up = 8 * K.FLY
    await _measure_route(rig, F, K, (F.S["x0"] - run_up, F.centre[1]), "right", 0, "M-A HORIZONTAL")
    await _measure_route(rig, F, K, (F.centre[0], F.S["y0"] - run_up), "down", 1, "M-A VERTICAL")


MEASURE = {"measure": leg_measure}


class open_rig:
    """One headless oracle-aether instance on `rom_path`, as a Rig. Reaped on exit."""

    def __init__(self, rom_path, lst_path, sym, K):
        self.args = (rom_path, lst_path, sym, K)
        self.inst = self.b = None

    async def __aenter__(self):
        rom_path, lst_path, sym, K = self.args
        self.inst = AetherInstance(rom_path, symbols=lst_path)
        try:
            sock = await asyncio.to_thread(self.inst.start)
        except (SpawnError, WrongServerError) as e:
            raise GateError(str(e)) from e
        self.b = BusClient(socket_path=sock, client_id="bgswitch", client_name="bg_switch_gate")
        await self.b.connect()
        for m in ("emulator/step", "emulator/run_to", "emulator/hold", "emulator/release_all",
                  "emulator/read_vram", "emulator/read_memory", "emulator/write_memory",
                  "emulator/reset"):
            if not self.b.supports(m):
                raise GateError(f"the server does not advertise `{m}`")
        await _c(self.b, "emulator/load_symbols", {"path": lst_path})
        return Rig(self.b, sym, K)

    async def __aexit__(self, *exc):
        try:
            if self.b is not None:
                await self.b.close()
        finally:
            if self.inst is not None:
                self.inst.reap()
        return False


async def run(rom_path, lst_path, only):
    rom = Path(rom_path).read_bytes()
    K = Consts()
    sym = parse_lst(lst_path)
    need = ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update", "Boot_At_X", "Boot_At_Y",
            "Boot_At_Flag", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Camera_X",
            "Camera_Y", "BG_Tiles_Current", "BG_Tiles_Target", "BG_Tiles_Offset",
            "BG_Plane_Layout", "BG_Wipe_Cursor", "OJZ_Act1_Descriptor", "Region_Current",
            "DMA_Deferrable", "DMA_Deferrable_Slot", "DMA_Deferrable_End",
            "Static_Sprite_DMA", "DMA_Budget_Default", "BgAnim_Table_Ptr", "BgAnim_LastStep",
            "BgAnim_View_T", "BgAnim_View_H", "Frame_Counter", "Parallax_Current_Vscroll_BG")
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

    fails = []
    ran = []
    try:
        async with open_rig(rom_path, lst_path, sym, K) as rig:
            rig.rom_path, rig.lst_path, rig.rom = rom_path, lst_path, rom
            for name, fn in {**LEGS, **MEASURE}.items():
                if (only and name not in only) or (not only and name in MEASURE):
                    continue
                print(f"  -- leg {name.upper()}")
                await fn(rig, F, K, fails)
                ran.append(name)
    except GateError as e:
        if not fails:
            raise
        print(f"\n  REFUSED after reds were already collected:\n    {e}")

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
