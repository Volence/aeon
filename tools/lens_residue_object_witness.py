#!/usr/bin/env python3
"""lens_residue_object_witness — five still-owed runtime witnesses from the lens residue.

A WITNESS TOOL, NOT A BUILD GATE. It is wired into nothing (not build.sh, not a pytest lane)
and it never builds. It boots its OWN headless emulator through tools/aether_instance.py,
drives the DEBUG ROM, and prints one verdict per witness:

    WITNESSED       the path ran, AND its control came out the other way
    NOT WITNESSED   the machine ran but did not show the path (the reason is printed)
    COULD NOT RUN   setup failed: wrong ROM, a symbol or source fact missing, instrument refusal

Exit status: 0 when every requested witness is WITNESSED; 1 when any is NOT WITNESSED;
2 when none is NOT WITNESSED but at least one COULD NOT RUN.

THE FIVE (recipes: docs/superpowers/notes/2026-09-12-physics-scene-survey.md on branch
survey/physics-scene-0912, sections 3a/3b/3e/3f/3g; results and derivations:
docs/superpowers/notes/2026-09-12-object-witnesses.md):

  c2a6         Render_Sprites' DEBUG staleness net (the C2a-6 move ahead of the overflow
               pre-check). Piece count $FF plus a wrong cached frame_off on Player_1 must reach
               the net's raise rail (a0 = Player_1) and then MDDBG__ErrorHandler.
               CONTROL A: the piece count alone -> no raise, and Player_1 owns no SAT entry
               that frame (the pre-check skipped it). CONTROL B: the same two pokes plus
               mappings = 0 on a slot already registered in a band -> no raise.
  multisprite  Draw_Sprite's batching-parent exit, and Render_Sprites' .multi_sprite walk.
               ObjDef_Parent is spawned through the live-object mailbox (Obj_Req_*). Each child's
               Draw_Sprite must reach .offscreen without visiting .no_parent and leave
               RF_ONSCREEN clear; Render_Sprites must reach .multi_sprite with a0 = the parent,
               and the children must own SAT entries. CONTROL: clear the parent's
               RF_MULTISPRITE; the children then go through .no_parent and set RF_ONSCREEN,
               and .multi_sprite is not reached.
  nullmap      Draw_Sprite on a zeroed slot, by the NATURAL path: collect a ring, then catch the
               ring sparkle's last Draw_Sprite (AnimateSprite's AF_DELETE -> DeleteObject ->
               back into RingSparkle_Main's tail `jbra Draw_Sprite`). At .no_parent with the
               sparkle's slot, mappings 0 must branch to .offscreen. CONTROL: the sparkle's
               live frames arrive at .no_parent with mappings set and fall through.
  c4a2         The collected half of C4a-2: collect section-0 ring list index 0, fly right far
               enough that section 0 is evicted into the respawn park, fly back, and require
               index 0 absent, its collected bit set, indices 1..6 present. CONTROL: the same
               route with no ring collected -> index 0 present, and section 0 never parked.
  c4a3         EntityWindow_DespawnRings profiled at a FULL ring buffer (MAX_RING_BUFFER
               entries seeded at the proc's entry), keep-all and remove-all. Cycles are the
               mclk delta from the proc's first instruction to the instruction after its rts,
               divided by 7 (the 68000 runs at MCLK/7). Every instruction is single-stepped so
               an interrupt inside the window is SEEN rather than billed to the proc; a
               contaminated window is discarded and the next frame's call is used. The machine
               is restored after each variant (a full buffer reaching RingBuffer_Add is a
               DEBUG-fatal assert).

HOW THE BOOT WORKS (cited, not re-derived): the DEBUG shape boots in debug fly
(GameState_OJZScroll_Init arms CHEAT_DEBUG_FLY; Player_Init enters fly). One B press hands
Player_1 to real physics (tools/spring_launch_witness.py `boot_and_settle`,
tools/dma_straddle_exercise.py header). Every witness starts from one checkpoint taken at
boot + BOOT_FRAMES with the player still in fly.

Usage:
    python3 tools/lens_residue_object_witness.py all
    python3 tools/lens_residue_object_witness.py c2a6 [--rom R --lst L]
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
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance, read_bytes, write_bytes  # noqa: E402

DEFAULT_ROM = "/home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.bin"
EXPECT_CRC = 0x9CE1C2FF          # master 9fe9ee91, s4.debug.bin
EXPECT_LEN = 847533

BOOT_FRAMES = 400                # the controller's premise: fly at boot + 400
MCLK_PER_68K_CYCLE = 7           # Mega Drive: the 68000 is clocked at MCLK / 7

WITNESSES = ("c2a6", "multisprite", "nullmap", "c4a2", "c4a3")


class CouldNotRun(Exception):
    """Setup or instrument failure. Never a verdict about the engine."""


# --------------------------------------------------------------------------- listing + source

def parse_listing(path: str) -> tuple[dict, dict]:
    """(labels, equs). Labels keep sigil's `$module$Proc$local` names, which parse_lst drops."""
    labels: dict[str, int] = {}
    equs: dict[str, int] = {}
    lab = re.compile(r"^\(0\) \d+/([0-9A-F]+) :\s+(\S+):\s*$")
    equ = re.compile(r"^EQU (\S+) = \$([0-9A-F]+)\s*$")
    for line in Path(path).read_text(errors="replace").splitlines():
        m = lab.match(line)
        if m:
            labels.setdefault(m.group(2), int(m.group(1), 16) & 0xFFFFFF)
            continue
        m = equ.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    return labels, equs


def struct_offsets(path: Path, header_re: str) -> dict[str, int]:
    """`name: type @ $OFF` fields inside one struct block."""
    out, inside = {}, False
    for line in path.read_text().splitlines():
        if not inside:
            inside = bool(re.match(header_re, line))
            continue
        if line.startswith("}"):
            break
        m = re.match(r"\s*(\w+):\s*[^@/]*@\s*\$([0-9A-Fa-f]+)", line)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    return out


def vars_offsets(path: Path, header_re: str, base: int) -> dict[str, int]:
    """Sequential `name: type,` fields of a `vars X: Sst.sst_custom {` overlay, packed from base."""
    size = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}
    out, inside, off = {}, False, base
    for line in path.read_text().splitlines():
        if not inside:
            inside = bool(re.match(header_re, line))
            continue
        if line.startswith("}"):
            break
        m = re.match(r"\s*(\w+):\s*(\w+)\s*,", line)
        if m:
            if m.group(2) not in size:
                break                 # a typed field we cannot size: stop, offsets past it unknown
            out[m.group(1)] = off
            off += size[m.group(2)]
    return out


def emp_const(path: Path, name: str) -> int:
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  path.read_text(), re.M)
    if not m:
        raise CouldNotRun(f"cannot read const {name} out of {path}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


class Facts:
    """Every address, offset and constant, from THIS ROM's listing and the source tree."""

    def __init__(self, rom: str, lst: str):
        data = Path(rom).read_bytes()
        self.rom_bytes = data
        self.crc = zlib.crc32(data) & 0xFFFFFFFF
        self.rom_len = len(data)
        if (self.crc, self.rom_len) != (EXPECT_CRC, EXPECT_LEN):
            raise CouldNotRun(f"ROM {rom} is crc32 {self.crc:08x} / {self.rom_len} B; this tool's "
                              f"runs are booked against {EXPECT_CRC:08x} / {EXPECT_LEN} (master "
                              f"9fe9ee91). Refusing to report on a different ROM.")
        self.lab, self.equ = parse_listing(lst)
        L = self.lab

        def need(name, table=None):
            t = L if table is None else table
            if name not in t:
                raise CouldNotRun(f"symbol {name} is not in {lst}")
            return t[name]
        self.need = need

        # Sst field offsets, from engine/objects/sst.emp (the struct is the layout's author).
        sst = struct_offsets(AEON / "engine/objects/sst.emp", r"\s*pub struct Sst\b")
        want = ["code_addr", "x_pos", "y_pos", "render_flags", "mappings", "width_pixels",
                "height_pixels", "mapping_frame", "sprite_piece_count", "parent_ptr",
                "sibling_ptr", "frame_off"]
        sst.setdefault("code_addr", 0)           # first field, no @ spelled
        miss = [k for k in want if k not in sst]
        if miss:
            raise CouldNotRun(f"Sst offsets {miss} not readable from engine/objects/sst.emp")
        self.sst = sst
        m = re.search(r"pub struct Sst \(size: \$([0-9A-Fa-f]+)\)",
                      (AEON / "engine/objects/sst.emp").read_text())
        self.sst_size = int(m.group(1), 16)

        # PlayerV.debug_flag: the overlay is packed from sst_custom; cross-checked against the
        # three offsets the game exports for witnesses (_pl_gsp / _pl_state / _pl_flip_angle).
        pv = vars_offsets(AEON / "games/sonic4/player/player_common.emp",
                          r"pub vars PlayerV: Sst\.sst_custom \{", sst["sst_custom"])
        for field, eq in (("ground_speed", "_pl_gsp"), ("player_state", "_pl_state"),
                          ("flip_angle", "_pl_flip_angle")):
            if pv.get(field) != self.equ.get(eq):
                raise CouldNotRun(f"PlayerV.{field} packs to {pv.get(field)} but the listing's {eq} "
                                  f"is {self.equ.get(eq)}: the overlay parse is wrong, refusing")
        if "debug_flag" not in pv:
            raise CouldNotRun("PlayerV.debug_flag not found in the overlay parse")
        self.debug_flag = pv["debug_flag"]

        ess = struct_offsets(AEON / "engine/objects/entity_window.emp",
                             r"\s*struct EntityScanState\b")
        m = re.search(r"struct EntityScanState \(size: \$([0-9A-Fa-f]+)\)",
                      (AEON / "engine/objects/entity_window.emp").read_text())
        self.ess_size = int(m.group(1), 16)
        self.ess_section_id = ess["ess_section_id"]

        # Constants: the build's own values from the listing's EQU table.
        for k in ("MAX_RING_BUFFER", "MAX_VDP_SPRITES", "SCREEN_WIDTH", "SCREEN_HEIGHT",
                  "SECTION_SIZE", "ENTITY_DESPAWN_BUFFER", "MAX_TRACKED_SECTIONS", "SEC_VOID",
                  "COLLECTED_WINDOW_SLOTS", "COLLECTED_SLOT_SIZE", "COLLECTED_BITMASK_OFFSET",
                  "COLLECTED_EMPTY_TAG", "COLLECTED_PARK_SLOTS", "COLLECTED_PARK_ENTRY_SIZE",
                  "NUM_EFFECTS", "RING_WIDTH", "RING_HEIGHT", "PLAYER_X_RADIUS",
                  "PLAYER_Y_RADIUS"):
            setattr(self, k, need(k, self.equ))
        const = AEON / "engine/system/constants.emp"
        self.SECTION_SIZE_SHIFT = emp_const(const, "SECTION_SIZE_SHIFT")
        self.ENTITY_DESPAWN_BUFFER_Y = emp_const(const, "ENTITY_DESPAWN_BUFFER_Y")
        self.RF_ONSCREEN = emp_const(const, "RF_ONSCREEN")
        self.RF_MULTISPRITE = emp_const(const, "RF_MULTISPRITE")
        self.RING_BUFFER_ENTRY_SIZE = emp_const(const, "RING_ENTRY_LIST_INDEX_OFFSET") + 1
        if 1 << self.SECTION_SIZE_SHIFT != self.SECTION_SIZE:
            raise CouldNotRun("SECTION_SIZE_SHIFT disagrees with the listing's SECTION_SIZE")
        if emp_const(const, "ENTITY_DESPAWN_BUFFER") != self.ENTITY_DESPAWN_BUFFER:
            raise CouldNotRun("ENTITY_DESPAWN_BUFFER: source and listing disagree")

        # The act's section-0 ring list, from the editor source the ROM was baked from.
        self.sec0_rings = [(r["x"], r["y"]) for r in json.loads(
            (AEON / "games/sonic4/data/editor/ojz/act1/section_0.rings.json").read_text())]

        # The sparkle's lifetime, from the ROM's own build-time ensure in ring_sparkle.emp:
        # S3K_SPARKLE_FRAMES frames x (S3K_SPARKLE_DURATION + 1) display ticks each.
        rs = AEON / "games/sonic4/objects/ring_sparkle.emp"
        self.sparkle_live_draws = (emp_const(rs, "S3K_SPARKLE_FRAMES")
                                   * (emp_const(rs, "S3K_SPARKLE_DURATION") + 1))
        # TestParent's children: the rows of child_desc in test_parent.emp.
        tp = (AEON / "games/sonic4/objects/test_parent.emp").read_text()
        m = re.search(r"data child_desc: \[SpawnDesc; (\d+)\]", tp)
        self.parent_children = int(m.group(1))

        # Addresses.
        for k in ("Player_1", "ObjCodeBase", "Player_Main", "Render_Sprites", "Draw_Sprite",
                  "Sprite_Owner", "Sprite_Bands", "Sprite_Band_Counts", "Obj_Req_Def",
                  "Obj_Req_X", "Obj_Req_Y", "Obj_Req_Slot", "Obj_Req_Place", "Obj_Req_Op",
                  "Obj_Req_Status", "Obj_Req_Flag", "ObjDef_Parent", "TestParent",
                  "TestParent_Main", "TestChildPart_Main", "Effect_Slots", "RingSparkle_Main",
                  "Ring_Buffer", "Ring_Count", "Ring_Counter", "Ring_Collected_Window",
                  "Ring_Collected_Park", "Entity_Scan_State", "Entity_Window_Center_ID",
                  "Entity_Window_Anchor", "Camera_X", "Camera_Y", "Camera_X_Max",
                  "EntityWindow_DespawnRings", "EntityWindow_DespawnObjects",
                  "EntityWindow_EntryForSection", "RingBuffer_Remove", "EntityLoaded_Clear",
                  "Debug_Scene_Freeze"):
            setattr(self, k, need(k))
        self.MDDBG__ErrorHandler = need("MDDBG__ErrorHandler", self.equ) & 0xFFFFFF
        S = "$engine.objects.sprites$"
        self.ds_offscreen = need(S + "Draw_Sprite$offscreen")
        self.ds_no_parent = need(S + "Draw_Sprite$no_parent")
        self.rs_object_loop = need(S + "Render_Sprites$object_loop")
        self.rs_stale_done = need(S + "Render_Sprites$stale_net_done")
        self.rs_multi = need(S + "Render_Sprites$multi_sprite")
        E = "$engine.objects.entity_window$EntityWindow_DespawnRings$"
        self.dr_loop = need(E + "loop")
        self.dr_done = need(E + "done")

        # The staleness net's raise rail: the ONE sprites-module diag raise label between the
        # object loop and .stale_net_done (sigil numbers diags per build, so find it by place).
        raises = [a for n, a in L.items()
                  if re.fullmatch(r"\$diag\d+\$engine\.objects\.sprites\$raise", n)
                  and self.rs_object_loop < a < self.rs_stale_done]
        if len(raises) != 1:
            raise CouldNotRun(f"expected exactly one sprites diag raise inside Render_Sprites' "
                              f"staleness net, found {len(raises)}")
        self.net_raise = raises[0]
        # ... and prove it is a raise rail that calls the MD Debugger: `jsr (xxx).l` = 4EB9.
        blob = data[self.net_raise:self.rs_stale_done]
        if (b"\x4e\xb9" + self.MDDBG__ErrorHandler.to_bytes(4, "big")) not in blob:
            raise CouldNotRun(f"the rail at ${self.net_raise:X} does not jsr MDDBG__ErrorHandler")

        # Code ranges for the DespawnRings trace: a label's range runs to the next top-level
        # (non-local) ROM label.
        tops = sorted(a for n, a in L.items() if not n.startswith("$") and a < 0x400000)

        def end_of(a):
            nxt = [t for t in tops if t > a]
            return nxt[0] if nxt else a + 0x100
        self.dr_range = (self.EntityWindow_DespawnRings, self.EntityWindow_DespawnObjects)
        self.callee_ranges = {
            "EntityWindow_EntryForSection": (self.EntityWindow_EntryForSection,
                                             end_of(self.EntityWindow_EntryForSection)),
            "RingBuffer_Remove": (self.RingBuffer_Remove, end_of(self.RingBuffer_Remove)),
            "EntityLoaded_Clear": (self.EntityLoaded_Clear, end_of(self.EntityLoaded_Clear)),
        }

    def rom_word(self, addr: int) -> int:
        return int.from_bytes(self.rom_bytes[addr:addr + 2], "big")


# --------------------------------------------------------------------------- the machine

class Rig:
    def __init__(self, bus: BusClient, f: Facts):
        self.b, self.f = bus, f

    async def call(self, m, p=None):
        return await self.b.call(m, p or {})

    async def rd(self, addr, n) -> bytes:
        addr &= 0xFFFFFF                  # the bus is 24 bits; a7 reads back as $FFFFxxxx
        out = b""
        while n > 0:
            k = min(n, 4096)
            out += bytes.fromhex(await read_bytes(self.b, addr, k))
            addr, n = addr + k, n - k
        return out

    async def rb(self, a):
        return (await self.rd(a, 1))[0]

    async def rw(self, a):
        return int.from_bytes(await self.rd(a, 2), "big")

    async def rl(self, a):
        return int.from_bytes(await self.rd(a, 4), "big")

    async def wr(self, a, data: bytes):
        for i in range(0, len(data), 4096):
            await write_bytes(self.b, a + i, data[i:i + 4096].hex())

    async def wb(self, a, v):
        await self.wr(a, bytes([v & 0xFF]))

    async def ww(self, a, v):
        await self.wr(a, (v & 0xFFFF).to_bytes(2, "big"))

    async def wl(self, a, v):
        await self.wr(a, (v & 0xFFFFFFFF).to_bytes(4, "big"))

    async def frames(self, n):
        return await self.call("emulator/run_frames", {"frames": n})

    async def run_to(self, addr, max_frames):
        return await self.call("emulator/run_to", {"addr": hex(addr), "maxFrames": max_frames})

    async def step(self, n=1):
        return await self.call("emulator/step", {"count": n})

    async def regs(self):
        r = await self.call("emulator/registers")
        return {k: int(v, 16) for k, v in r.items() if isinstance(v, str) and v.startswith("0x")}

    async def status(self):
        return await self.call("emulator/status")

    async def checkpoint(self):
        return (await self.call("emulator/checkpoint"))["id"]

    async def restore(self, cid):
        await self.call("emulator/release_all")
        await self.call("emulator/restore", {"id": cid})

    async def drop(self, cid):
        await self.call("emulator/checkpoint_drop", {"id": cid})

    async def press(self, button, frames=1):
        return await self.call("emulator/press", {"buttons": [button], "frames": frames})

    async def hold(self, button, down):
        await self.call("emulator/hold", {"buttons": [button], "down": bool(down)})

    # ---- typed reads
    async def fly(self):
        return await self.rb(self.f.Player_1 + self.f.debug_flag)

    async def pos(self, sst):
        o = self.f.sst
        x = await self.rw(sst + o["x_pos"])
        y = await self.rw(sst + o["y_pos"])
        return x, y

    async def camera(self):
        return await self.rw(self.f.Camera_X), await self.rw(self.f.Camera_Y)

    async def sprite_owner(self):
        raw = await self.rd(self.f.Sprite_Owner, 2 * self.f.MAX_VDP_SPRITES)
        return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw), 2)]

    async def ring_buffer(self):
        n = await self.rb(self.f.Ring_Count)
        es = self.f.RING_BUFFER_ENTRY_SIZE
        raw = await self.rd(self.f.Ring_Buffer, max(n, 1) * es)
        out = []
        for i in range(n):
            e = raw[i * es:(i + 1) * es]
            out.append(dict(x=int.from_bytes(e[0:2], "big"), y=int.from_bytes(e[2:4], "big"),
                            sec=e[4], idx=e[5]))
        return out

    async def collected_window(self):
        f = self.f
        raw = await self.rd(f.Ring_Collected_Window, f.COLLECTED_WINDOW_SLOTS * f.COLLECTED_SLOT_SIZE)
        slots = []
        for i in range(f.COLLECTED_WINDOW_SLOTS):
            s = raw[i * f.COLLECTED_SLOT_SIZE:(i + 1) * f.COLLECTED_SLOT_SIZE]
            mask = s[f.COLLECTED_BITMASK_OFFSET:f.COLLECTED_BITMASK_OFFSET + 16]
            slots.append((s[0], mask))
        return slots

    async def park(self):
        f = self.f
        raw = await self.rd(f.Ring_Collected_Park, f.COLLECTED_PARK_SLOTS * f.COLLECTED_PARK_ENTRY_SIZE)
        out = []
        for i in range(f.COLLECTED_PARK_SLOTS):
            e = raw[i * f.COLLECTED_PARK_ENTRY_SIZE:(i + 1) * f.COLLECTED_PARK_ENTRY_SIZE]
            out.append((e[0], e[1:17]))
        return out

    async def tracked_ids(self):
        f = self.f
        return [await self.rb(f.Entity_Scan_State + k * f.ess_size + f.ess_section_id)
                for k in range(f.MAX_TRACKED_SECTIONS)]


def bit(mask: bytes, idx: int) -> bool:
    return bool(mask[idx >> 3] & (1 << (idx & 7)))


# --------------------------------------------------------------------------- shared steps

async def boot_checkpoint(rig: Rig, out: list) -> str:
    """Reset, run BOOT_FRAMES, prove the player is in debug fly, checkpoint."""
    f = rig.f
    await rig.call("emulator/reset")
    await rig.frames(BOOT_FRAMES)
    code = await rig.rw(f.Player_1)
    if code != f.Player_Main - f.ObjCodeBase:
        raise CouldNotRun(f"Player_1.code_addr is ${code:04X}, not Player_Main's "
                          f"${f.Player_Main - f.ObjCodeBase:04X}, at frame {BOOT_FRAMES}")
    if not await rig.fly():
        raise CouldNotRun("Player_1 is not in debug fly at boot; the recipes assume it is")
    if await rig.rb(f.Debug_Scene_Freeze):
        raise CouldNotRun("Debug_Scene_Freeze is set at boot; EntityWindow_Scan would not run")
    st = await rig.status()
    if st.get("romBytes") != f.rom_len:
        raise CouldNotRun(f"the server has {st.get('romBytes')} ROM bytes loaded, not {f.rom_len}")
    cam = await rig.camera()
    out.append(f"  boot: frame {st['frame']}, Player_1 in fly at {await rig.pos(f.Player_1)}, "
               f"camera {cam}")
    return await rig.checkpoint()


async def stop_at_entry(rig: Rig, addr: int, max_frames: int, what: str):
    r = await rig.run_to(addr, max_frames)
    if not r.get("reached"):
        raise CouldNotRun(f"run_to {what} (${addr:X}) not reached in {max_frames} frames")
    return r


async def reaches(rig: Rig, addr: int, max_frames: int) -> dict:
    return await rig.run_to(addr, max_frames)


async def render_pass(rig: Rig, watch: list, before=None) -> dict:
    """Run exactly ONE Render_Sprites call with execution breakpoints armed at `watch`.

    WHY A COUNTED PASS and not "not reached within N frames": this scene lags once the player
    is in physics (one logic tick can span two frames; measured), so a frame budget does not
    say how many renders it contained, and a "not reached" over a budget that held no render
    is vacuous. Here the pass is bracketed by the proc's own entry and its own return
    address (read off the stack at entry), so a pass that completes is one whole render.

    The detector is a breakpoint, and oracle halts any run on an armed breakpoint before the
    target (oracle crates/oracle-aether/src/breakpoints.rs). Every witness that uses this has
    a SUBJECT that must trip the same breakpoint its control must not, in the same process,
    so a detector that does not fire cannot pass a witness.
    `before(rig)` runs at the entry, before arming (a mid-frame poke)."""
    f = rig.f
    r = await rig.run_to(f.Render_Sprites, 6)
    if not r.get("reached"):
        raise CouldNotRun("Render_Sprites was not entered within 6 frames")
    entry_frame = r.get("frame")
    ret = await rig.rl((await rig.regs())["a7"])
    if before is not None:
        await before(rig)
    handles = []
    try:
        for a in watch:
            handles.append((await rig.call("emulator/breakpoint_add", {"addr": hex(a)}))["breakpoint"])
        r2 = await rig.run_to(ret, 6)
    finally:
        for h in handles:
            await rig.call("emulator/breakpoint_clear", {"breakpoint": h})
    pc = int(r2["pc"], 16)
    return dict(entry_frame=entry_frame, ret=ret, returned=bool(r2.get("reached")),
                hit=pc if pc in watch else None, stop_frame=r2.get("frame"), pc=pc)


async def collect_ring0(rig: Rig, out: list, collect: bool = True) -> dict:
    """From the fly checkpoint: place Player_1 on section-0 ring list index 0 (or, for the
    control, 40 px below it), press B once. Returns the before/after record.

    x = ring0.x - 8: AABB overlap on an axis is 2|d| < wa + wb (engine/objects/aabb.emp), so
    ring 0 (d = 8) overlaps for any player width 1..31 and ring 1 (d = 24, 16 px on) does
    not overlap for any width <= 32. The control's y is 40 px below: 2*40 = 80 is past
    38 + 16 for the standing height 2*PLAYER_Y_RADIUS."""
    f = rig.f
    rx, ry = f.sec0_rings[0]
    px, py = rx - 8, ry + (0 if collect else 40)
    o = f.sst
    await rig.wl(f.Player_1 + o["x_pos"], px << 16)
    await rig.wl(f.Player_1 + o["y_pos"], py << 16)
    before = dict(count=await rig.rb(f.Ring_Count), counter=await rig.rw(f.Ring_Counter),
                  buf=await rig.ring_buffer())
    sec0 = sorted((e["idx"], e["x"], e["y"]) for e in before["buf"] if e["sec"] == 0)
    want = [(i, x, y) for i, (x, y) in enumerate(f.sec0_rings)]
    if sec0 != want:
        raise CouldNotRun(f"section 0's rings in the buffer before the collect are {sec0}, not "
                          f"the editor list {want}")
    # B is HELD (not tapped) and released at a known instruction. A frame boundary falls
    # mid-tick in this scene (boot+400 stops inside Tile_Cache_Fill), so a tap returns with the
    # B tick half-run. For the collect, hold B until RingCollision calls the game's
    # ring_collected hook (RingSparkle_Spawn), release, then finish that tick at
    # Render_Sprites: the sparkle exists and its Main has not run yet.
    await rig.hold("b", True)
    spawn = None
    try:
        if collect:
            spawn = await rig.run_to(f.need("RingSparkle_Spawn"), 4)
        else:
            for _ in range(4):
                await rig.frames(1)
                if not await rig.fly():
                    break
    finally:
        await rig.hold("b", False)
    r = await rig.run_to(f.Render_Sprites, 2)
    after = dict(count=await rig.rb(f.Ring_Count), counter=await rig.rw(f.Ring_Counter),
                 buf=await rig.ring_buffer(), fly=await rig.fly(),
                 w=await rig.rb(f.Player_1 + o["width_pixels"]),
                 h=await rig.rb(f.Player_1 + o["height_pixels"]), frame=r.get("frame"),
                 spawn=bool(spawn and spawn.get("reached")))
    if after["fly"]:
        raise CouldNotRun("holding B did not leave debug fly")
    after["sec0_idx"] = sorted(e["idx"] for e in after["buf"] if e["sec"] == 0)
    out.append(f"  placed Player_1 at ({px},{py}), ring 0 at ({rx},{ry}); B held -> physics on"
               f"{', RingSparkle_Spawn reached' if after['spawn'] else ''}, B released; at "
               f"Render_Sprites, frame {after['frame']}: standing box {after['w']}x{after['h']}; "
               f"Ring_Count {before['count']} -> {after['count']}, Ring_Counter "
               f"{before['counter']} -> {after['counter']}, section-0 indices now {after['sec0_idx']}")
    return dict(before=before, after=after)


async def reenter_fly(rig: Rig):
    """B released for two polls, then held until debug_flag is set again (the edge the game
    needs), then released."""
    await rig.frames(2)
    await rig.hold("b", True)
    try:
        for _ in range(4):
            await rig.frames(1)
            if await rig.fly():
                break
    finally:
        await rig.hold("b", False)
    await rig.frames(2)
    if not await rig.fly():
        raise CouldNotRun("holding B again did not re-enter debug fly")


async def find_sparkle(rig: Rig):
    f = rig.f
    want = f.RingSparkle_Main - f.ObjCodeBase
    for k in range(f.NUM_EFFECTS):
        s = f.Effect_Slots + k * f.sst_size
        if await rig.rw(s) == want:
            return s
    return None


# --------------------------------------------------------------------------- witness: C2a-6

async def w_c2a6(rig: Rig, boot: str, out: list) -> tuple[str, str]:
    f = rig.f
    P = f.Player_1
    o = f.sst
    await rig.restore(boot)
    F = await rig.rw(P + o["frame_off"])
    M = await rig.rb(P + o["mapping_frame"])
    MP = await rig.rl(P + o["mappings"])
    cnt = await rig.rb(P + o["sprite_piece_count"])
    live = f.rom_word(MP + 2 * M)
    rf = await rig.rb(P + o["render_flags"])
    out.append(f"  Player_1 at boot+{BOOT_FRAMES}: mappings ${MP:06X}, mapping_frame {M}, cached "
               f"frame_off ${F:04X}, live-resolved ${live:04X}, piece count {cnt}, "
               f"render_flags ${rf:02X}")
    if live != F:
        raise CouldNotRun("the cache is already inconsistent at boot; a 'wrong' value means nothing")
    W = (F + 2) & 0xFFFF
    p1w = P & 0xFFFF
    watch = [f.net_raise, f.MDDBG__ErrorHandler]
    PASSES = 2                        # counted Render_Sprites calls per control

    def fmt(p):
        return (f"entry f{p['entry_frame']} -> {'returned' if p['returned'] else 'STOPPED'} "
                f"f{p['stop_frame']} at ${p['pc']:X}")

    # baseline: no poke -> both passes return, and Player_1 owns SAT entries
    await rig.restore(boot)
    base = [await render_pass(rig, watch) for _ in range(PASSES)]
    base_own = (await rig.sprite_owner()).count(p1w)
    out.append(f"  baseline (no poke), {PASSES} passes: " + "; ".join(fmt(p) for p in base)
               + f"; Player_1 owns {base_own} SAT entries")

    # SUBJECT: count $FF + wrong frame_off, poked at the boot checkpoint (mid-tick, before
    # this tick's Render_Sprites; in fly nothing refreshes the cache in between)
    async def subject_poke(rig):
        await rig.wb(P + o["sprite_piece_count"], 0xFF)
        await rig.ww(P + o["frame_off"], W)
    await rig.restore(boot)
    await subject_poke(rig)
    sp = await render_pass(rig, watch)
    subj = dict(hit=sp["hit"], frame=sp["stop_frame"])
    if sp["hit"] == f.net_raise:
        rg = await rig.regs()
        subj.update(a0=rg["a0"] & 0xFFFFFF, d0=rg["d0"] & 0xFFFF, d1=rg["d1"] & 0xFFFF)
        r2 = await reaches(rig, f.MDDBG__ErrorHandler, 1)
        subj["handler"] = bool(r2.get("reached"))
    out.append(f"  SUBJECT (count $FF, frame_off ${F:04X} -> ${W:04X}): {fmt(sp)}; raise rail "
               f"${f.net_raise:X} hit={sp['hit'] == f.net_raise}; a0=${subj.get('a0', 0):06X} "
               f"d1(cached)=${subj.get('d1', 0):04X} d0(live)=${subj.get('d0', 0):04X}; "
               f"then MDDBG__ErrorHandler ${f.MDDBG__ErrorHandler:X} entered={subj.get('handler')}")

    # CONTROL A: count $FF only
    await rig.restore(boot)
    await rig.wb(P + o["sprite_piece_count"], 0xFF)
    ca = [await render_pass(rig, watch)]
    a_own = (await rig.sprite_owner()).count(p1w)       # stamps of the first poked pass
    ca.append(await render_pass(rig, watch))
    out.append(f"  CONTROL A (count $FF only), {PASSES} passes: " + "; ".join(fmt(p) for p in ca)
               + f"; Player_1 owns {a_own} SAT entries in the first (baseline {base_own})")

    # CONTROL B: the subject's two pokes plus mappings = 0, on a slot already in a band
    b_band = []

    async def control_b_poke(rig):
        counts = await rig.rd(f.Sprite_Band_Counts, 8)
        bands = await rig.rd(f.Sprite_Bands, 8 * 64)
        b_band.extend((bd, i) for bd in range(8) for i in range(counts[bd])
                      if int.from_bytes(bands[bd * 64 + 2 * i:bd * 64 + 2 * i + 2], "big") == p1w)
        await rig.wl(P + o["mappings"], 0)
        await subject_poke(rig)
    await rig.restore(boot)
    cb = [await render_pass(rig, watch, before=control_b_poke)]
    cb.append(await render_pass(rig, watch))
    out.append(f"  CONTROL B (at Render_Sprites entry Player_1 is in band list at {b_band}; "
               f"mappings=0 + count $FF + frame_off ${W:04X}), {PASSES} passes: "
               + "; ".join(fmt(p) for p in cb))

    def clean(ps):
        return all(p["returned"] and p["hit"] is None for p in ps)
    ok_subject = (subj["hit"] == f.net_raise and subj.get("a0") == P and subj.get("d1") == W
                  and subj.get("d0") == F and subj.get("handler"))
    ok_a = clean(ca) and a_own == 0 and base_own > 0
    ok_b = bool(b_band) and clean(cb)
    ok_base = clean(base)
    if ok_subject and ok_a and ok_b and ok_base:
        return "WITNESSED", (f"raise at ${f.net_raise:X} with a0=Player_1, cached ${W:04X} vs live "
                             f"${F:04X}, handler entered; A: no raise, 0 SAT entries (baseline "
                             f"{base_own}); B: no raise")
    why = []
    if not ok_base:
        why.append("the unpoked baseline raised")
    if not ok_subject:
        why.append("subject did not raise on Player_1 with the poked values")
    if not ok_a:
        why.append("control A raised or Player_1 was not skipped")
    if not ok_b:
        why.append("control B raised or Player_1 was not in a band")
    return "NOT WITNESSED", "; ".join(why)


# --------------------------------------------------------------------------- witness: multisprite

async def trace_draw(rig: Rig, max_steps=40):
    """From Draw_Sprite's entry: step to its return, return (pcs, ret)."""
    ret = await rig.rl((await rig.regs())["a7"])
    pcs = []
    for _ in range(max_steps):
        st = await rig.step(1)
        pc = int(st["pc"], 16)
        if pc == ret:
            return pcs, ret
        pcs.append(pc)
    return pcs, None


async def draw_paths(rig: Rig, slots: set, max_arrivals=200):
    """Catch each slot's next Draw_Sprite call; for each, (visited .no_parent, visited
    .offscreen, RF_ONSCREEN after)."""
    f = rig.f
    res = {}
    for _ in range(max_arrivals):
        r = await rig.run_to(f.Draw_Sprite, 6)       # 6: a lag tick can span two frames
        if not r.get("reached"):
            break
        a0 = (await rig.regs())["a0"] & 0xFFFFFF
        if a0 in slots and a0 not in res:
            pcs, ret = await trace_draw(rig)
            rf = await rig.rb(a0 + f.sst["render_flags"])
            res[a0] = dict(no_parent=f.ds_no_parent in pcs, offscreen=f.ds_offscreen in pcs,
                           onscreen=bool(rf & (1 << f.RF_ONSCREEN)), returned=ret is not None)
            if len(res) == len(slots):
                break
        else:
            await rig.step(1)
    return res


async def w_multisprite(rig: Rig, boot: str, out: list) -> tuple[str, str]:
    f = rig.f
    o = f.sst
    await rig.restore(boot)
    cam0 = await rig.camera()
    await rig.wl(f.Obj_Req_Def, f.ObjDef_Parent)
    await rig.ww(f.Obj_Req_X, 160)
    await rig.ww(f.Obj_Req_Y, 112)
    await rig.ww(f.Obj_Req_Place, 0)
    await rig.wb(f.Obj_Req_Op, 1)
    await rig.wb(f.Obj_Req_Flag, 1)              # last
    for _ in range(3):
        await rig.frames(1)
        if await rig.rb(f.Obj_Req_Flag) == 0:
            break
    status = await rig.rb(f.Obj_Req_Status)
    slot = await rig.rw(f.Obj_Req_Slot)
    if await rig.rb(f.Obj_Req_Flag) != 0 or status != 0:
        raise CouldNotRun(f"the objreq spawn was not acked OK (flag "
                          f"{await rig.rb(f.Obj_Req_Flag)}, status {status})")
    parent = 0xFF0000 | slot
    await rig.frames(2)                           # children run their init, then Main
    pcode = await rig.rw(parent)
    prf = await rig.rb(parent + o["render_flags"])
    kids = []
    c = await rig.rw(parent + o["sibling_ptr"])
    while c and len(kids) < 16:
        kids.append(0xFF0000 | c)
        c = await rig.rw((0xFF0000 | c) + o["sibling_ptr"])
    kid_ok = all([await rig.rw(k + o["parent_ptr"]) == slot and
                  await rig.rw(k) == f.TestChildPart_Main - f.ObjCodeBase for k in kids])
    out.append(f"  spawned ObjDef_Parent ${f.ObjDef_Parent:X} via Obj_Req_*: status {status}, slot "
               f"${slot:04X}, code ${pcode:04X} (TestParent_Main ${f.TestParent_Main - f.ObjCodeBase:04X}), "
               f"render_flags ${prf:02X}; {len(kids)} children "
               f"{[f'${k & 0xFFFF:04X}' for k in kids]} (expected {f.parent_children}), each "
               f"parent_ptr=slot and code=TestChildPart_Main: {kid_ok}")
    if (pcode != f.TestParent_Main - f.ObjCodeBase or not prf & (1 << f.RF_MULTISPRITE)
            or len(kids) != f.parent_children or not kid_ok):
        raise CouldNotRun("the spawned parent/children are not in the shape the witness needs")
    settled = await rig.checkpoint()
    try:
        # A: each child's Draw_Sprite
        paths = await draw_paths(rig, set(kids))
        # B: one counted Render_Sprites pass with a breakpoint at .multi_sprite
        bp = await render_pass(rig, [f.rs_multi])
        multi_a0 = ((await rig.regs())["a0"] & 0xFFFFFF) if bp["hit"] == f.rs_multi else None
        if bp["hit"] == f.rs_multi:
            await stop_at_entry(rig, bp["ret"], 2, "Render_Sprites' return")   # finish the pass
        owners = await rig.sprite_owner()                    # this pass's SAT ownership stamps
        own = {k: owners.count(k & 0xFFFF) for k in [parent] + kids}
        kids_rf = [await rig.rb(k + o["render_flags"]) for k in kids]
        cam1 = await rig.camera()
        alive = await rig.rw(parent)
        out.append(f"  children's Draw_Sprite: " + "; ".join(
            f"${k & 0xFFFF:04X} no_parent={p['no_parent']} offscreen={p['offscreen']} "
            f"RF_ONSCREEN={p['onscreen']}" for k, p in paths.items()))
        out.append(f"  Render_Sprites .multi_sprite (${f.rs_multi:X}) a0="
                   f"{'$%06X' % multi_a0 if multi_a0 is not None else 'NOT REACHED'}; SAT entries "
                   f"owned: " + ", ".join(f"${k & 0xFFFF:04X}={n}" for k, n in own.items())
                   + f"; children render_flags {[f'${v:02X}' for v in kids_rf]}; camera {cam0} -> "
                   f"{cam1}; parent alive (code ${alive:04X})")
        # CONTROL: parent without RF_MULTISPRITE
        await rig.restore(settled)
        await rig.wb(parent + o["render_flags"], prf & ~(1 << f.RF_MULTISPRITE))
        cpaths = await draw_paths(rig, set(kids))
        cps = [await render_pass(rig, [f.rs_multi]) for _ in range(2)]
        cowners = await rig.sprite_owner()
        cown = {k: cowners.count(k & 0xFFFF) for k in [parent] + kids}
        out.append(f"  CONTROL (parent RF_MULTISPRITE cleared): " + "; ".join(
            f"${k & 0xFFFF:04X} no_parent={p['no_parent']} offscreen={p['offscreen']} "
            f"RF_ONSCREEN={p['onscreen']}" for k, p in cpaths.items())
            + "; 2 counted Render_Sprites passes: " + "; ".join(
                f"{'returned' if p['returned'] else 'STOPPED'} at ${p['pc']:X}"
                f"{' (.multi_sprite HIT)' if p['hit'] else ''}" for p in cps)
            + f"; SAT entries owned: " + ", ".join(f"${k & 0xFFFF:04X}={n}" for k, n in cown.items()))
    finally:
        await rig.drop(settled)

    ok_a = (len(paths) == len(kids) and all(p["offscreen"] and not p["no_parent"]
                                            and not p["onscreen"] and p["returned"]
                                            for p in paths.values()))
    ok_b = multi_a0 == parent and all(own[k] > 0 for k in [parent] + kids)
    ok_c = (len(cpaths) == len(kids) and all(p["no_parent"] and p["onscreen"]
                                             for p in cpaths.values())
            and all(p["returned"] and p["hit"] is None for p in cps))
    still = cam0 == cam1 and alive != 0
    if ok_a and ok_b and ok_c and still:
        return "WITNESSED", (f"{len(kids)}/{len(kids)} children took the batching exit "
                             f"(RF_ONSCREEN clear); .multi_sprite a0=parent, children own SAT "
                             f"entries; control: all children via .no_parent, RF_ONSCREEN set, "
                             f"no .multi_sprite")
    return "NOT WITNESSED", (f"children path ok={ok_a}, multi_sprite ok={ok_b}, control "
                             f"differs={ok_c}, camera still + parent alive={still}")


# --------------------------------------------------------------------------- witness: null mappings

async def w_nullmap(rig: Rig, boot: str, out: list) -> tuple[str, str]:
    f = rig.f
    o = f.sst
    await rig.restore(boot)
    rec = await collect_ring0(rig, out)
    spark = await find_sparkle(rig)
    if spark is None or rec["after"]["counter"] != rec["before"]["counter"] + 1:
        return "NOT WITNESSED", "the ring was not collected / no sparkle spawned (natural path unavailable)"
    st = await rig.status()
    out.append(f"  sparkle in effect slot ${spark & 0xFFFF:04X} at frame {st['frame']}")
    live_visits, live_fell_through, final = 0, 0, None
    f0 = st["frame"]
    for _ in range(4000):
        # 6 frames, not 2: this scene lags (one logic tick can span two frames), so from
        # Render_Sprites the next Draw_Sprite can be more than two frame boundaries away.
        # Measured: from the collect tick's Render_Sprites at frame 401 the next Draw_Sprite
        # of any object ran in frame 403.
        r = await rig.run_to(f.ds_no_parent, 6)
        if not r.get("reached"):
            break
        if r.get("frame", 0) - f0 > 3 * f.sparkle_live_draws:
            break
        a0 = (await rig.regs())["a0"] & 0xFFFFFF
        if a0 != spark:
            await rig.step(1)
            continue
        mp = await rig.rl(spark + o["mappings"])
        code = await rig.rw(spark)
        s = None
        for _ in range(3):                 # movea.l mappings / move.l / beq .offscreen
            s = await rig.step(1)
        pc = int(s["pc"], 16)
        if mp != 0:
            live_visits += 1
            live_fell_through += pc != f.ds_offscreen
            continue
        s2 = await rig.step(1)            # bclr RF_ONSCREEN
        rf = await rig.rb(spark + o["render_flags"])
        final = dict(frame=r.get("frame"), code=code, mappings=mp, next_pc=pc,
                     onscreen=bool(rf & (1 << f.RF_ONSCREEN)))
        break
    out.append(f"  sparkle's live Draw_Sprite visits at .no_parent: {live_visits} (derived "
               f"{f.sparkle_live_draws} = S3K_SPARKLE_FRAMES x (S3K_SPARKLE_DURATION+1)), "
               f"{live_fell_through} fell through the null test")
    if final is None:
        return "NOT WITNESSED", "no Draw_Sprite call on the sparkle's slot with null mappings was seen"
    out.append(f"  final visit, frame {final['frame']}: slot code_addr ${final['code']:04X}, "
               f"mappings ${final['mappings']:08X} -> next pc ${final['next_pc']:X} "
               f"(.offscreen ${f.ds_offscreen:X}); RF_ONSCREEN after bclr={final['onscreen']}")
    ok = (final["code"] == 0 and final["next_pc"] == f.ds_offscreen and not final["onscreen"]
          and live_visits > 0 and live_fell_through == live_visits)
    if ok:
        return "WITNESSED", (f"NATURAL path: zeroed sparkle slot .no_parent -> .offscreen; control "
                             f"{live_visits} live visits fell through (derived "
                             f"{f.sparkle_live_draws})")
    return "NOT WITNESSED", "the zeroed slot did not branch to .offscreen, or the control did not fall through"


# --------------------------------------------------------------------------- witness: C4a-2

async def c4a2_route(rig: Rig, boot: str, collect: bool, out: list) -> dict:
    """Collect (or not), back to fly, RIGHT until the slide that evicts section 0, LEFT home."""
    f = rig.f
    tag = "SUBJECT" if collect else "CONTROL"
    await rig.restore(boot)
    lines: list = []
    rec = await collect_ring0(rig, lines, collect=collect)
    out.extend(f"  [{tag}] {x.strip()}" for x in lines)
    await reenter_fly(rig)
    cam_home = await rig.camera()
    out.append(f"  [{tag}] back in fly at {await rig.pos(f.Player_1)}, camera {cam_home}")
    # Derived: a window slide fires only when DeriveWindow's anchor changes,
    # sec_x0 = (Camera_X - ENTITY_DESPAWN_BUFFER) >> SECTION_SIZE_SHIFT. The recenter at a slide
    # uses the camera centre, (Camera_X + SCREEN_WIDTH/2) >> SECTION_SIZE_SHIFT, and evicts
    # |slot_x - centre_x| > 1. The sec_x0 0->1 slide fires at Camera_X = 2560, centre col 1,
    # so section 0 is KEPT; the 1->2 slide fires at Camera_X = 2*SECTION_SIZE +
    # ENTITY_DESPAWN_BUFFER = 4608, centre col (4608+160)>>11 = 2, which evicts col 0.
    x_evict = 2 * f.SECTION_SIZE + f.ENTITY_DESPAWN_BUFFER
    far = None
    await rig.hold("right", True)
    t = 0
    try:
        while t < 1200:
            await rig.frames(4)
            t += 4
            cx, cy = await rig.camera()
            tags = [s[0] for s in await rig.collected_window()]
            if cx >= x_evict and 0 not in tags:
                park = await rig.park()
                far = dict(frames=t, cam=(cx, cy), center=await rig.rb(f.Entity_Window_Center_ID),
                           tags=tags, park=[(i, m.hex()) for i, m in park if i != f.COLLECTED_EMPTY_TAG],
                           park0=[m for i, m in park if i == 0])
                break
    finally:
        await rig.hold("right", False)
    if far is None:
        raise CouldNotRun(f"section 0 was never evicted within {t} frames of RIGHT "
                          f"(camera {await rig.camera()})")
    far["park0_bit0"] = bool(far["park0"]) and bit(far["park0"][0], 0)
    out.append(f"  [{tag}] RIGHT {far['frames']} frames: camera {far['cam']} (evicting slide derived "
               f"at Camera_X >= {x_evict}), centre id {far['center']}, window tags {far['tags']}, "
               f"park {far['park']}")
    await rig.hold("left", True)
    t = 0
    try:
        while t < 1200:
            await rig.frames(4)
            t += 4
            cx, _ = await rig.camera()
            if cx <= cam_home[0]:
                break
    finally:
        await rig.hold("left", False)
    await rig.frames(8)
    buf = await rig.ring_buffer()
    sec0 = sorted(e["idx"] for e in buf if e["sec"] == 0)
    pos_ok = all((e["x"], e["y"]) == f.sec0_rings[e["idx"]] for e in buf if e["sec"] == 0)
    win = await rig.collected_window()
    slot0 = [m for tg, m in win if tg == 0]
    park = await rig.park()
    res = dict(rec=rec, far=far, back_frames=t, cam=await rig.camera(), sec0=sec0, pos_ok=pos_ok,
               slot0_bit0=bool(slot0) and bit(slot0[0], 0),
               slot0_mask=slot0[0].hex() if slot0 else None,
               park_has0=any(i == 0 for i, _ in park))
    out.append(f"  [{tag}] LEFT {t}+8 frames: camera {res['cam']}; section-0 indices in the buffer "
               f"{sec0} (positions match the editor list: {pos_ok}); section 0's window slot mask "
               f"{res['slot0_mask']}; park still holds section 0: {res['park_has0']}")
    return res


async def w_c4a2(rig: Rig, boot: str, out: list) -> tuple[str, str]:
    f = rig.f
    s = await c4a2_route(rig, boot, True, out)
    c = await c4a2_route(rig, boot, False, out)
    rest = list(range(1, len(f.sec0_rings)))
    collected = (s["rec"]["after"]["counter"] == s["rec"]["before"]["counter"] + 1
                 and s["rec"]["after"]["sec0_idx"] == rest)
    ok_s = (collected and s["far"]["park0_bit0"] and s["sec0"] == rest and s["pos_ok"]
            and s["slot0_bit0"] and not s["park_has0"])
    ok_c = (c["rec"]["after"]["counter"] == c["rec"]["before"]["counter"]
            and not c["far"]["park0"] and c["sec0"] == list(range(len(f.sec0_rings)))
            and not c["slot0_bit0"])
    if ok_s and ok_c:
        return "WITNESSED", (f"after eviction into the park (bit 0 parked) and return: indices "
                             f"{s['sec0']}, bit 0 set, park entry freed; control: indices "
                             f"{c['sec0']}, section 0 never parked")
    return "NOT WITNESSED", f"subject ok={ok_s} (collected={collected}), control differs={ok_c}"


# --------------------------------------------------------------------------- witness: C4a-3

def cost_model(n: int, remove: bool) -> int:
    """68000 cycles for EntityWindow_DespawnRings over n entries, entry to after the rts.

    Hand-derived from the ROM's disassembly with the MC68000 timing tables (no wait states);
    the derivation, instruction by instruction, is in the results note. The loop tail's dbf
    costs 10 taken and 14 on expiry, hence the +4.
      prologue (moveq .. addi.w d7)                                             100
      keep-all iteration: X inside the window, Y inside the band               118
      remove-all iteration: X right of the window, section untracked:
        X tests 32 + four section compares 94 + remove setup 46
        + EntryForSection (untracked, four probes) 214 + tst/bmi 14
        + move.w/bsr.w 22 + RingBuffer_Remove (removing the last entry) 70
        + subq/dbf 18                                                          510
      rts                                                                        16
    """
    per = 510 if remove else 118
    return 100 + n * per + 4 + 16


async def profile_once(rig: Rig, variant: str, out: list, tries: int = 6) -> dict:
    f = rig.f
    N = f.MAX_RING_BUFFER
    es = f.RING_BUFFER_ENTRY_SIZE
    for attempt in range(tries):
        await stop_at_entry(rig, f.EntityWindow_DespawnRings, 2, "EntityWindow_DespawnRings")
        entry_state = await rig.checkpoint()
        try:
            cx, cy = await rig.camera()
            tracked = await rig.tracked_ids()
            ret = await rig.rl((await rig.regs())["a7"])
            natural = await rig.rb(f.Ring_Count)
            if variant == "keep":
                x = cx + f.SCREEN_WIDTH // 2          # inside [cx - $200, cx + 320 + $200]
                sec = tracked[0]
            else:
                x = cx + f.SCREEN_WIDTH + f.ENTITY_DESPAWN_BUFFER + 16   # right of the window
                sec = next(s for s in range(0, 64) if s not in tracked and s != f.SEC_VOID)
            y = cy + f.SCREEN_HEIGHT // 2             # inside the Y band
            buf = b"".join(x.to_bytes(2, "big") + y.to_bytes(2, "big") + bytes([sec, i])
                           for i in range(N))
            assert len(buf) == N * es
            await rig.wr(f.Ring_Buffer, buf)
            await rig.wb(f.Ring_Count, N)
            if await rig.rb(f.Ring_Count) != N or await rig.rd(f.Ring_Buffer, N * es) != buf:
                raise CouldNotRun("the ring-buffer seed did not read back")
            st0 = await rig.status()
            m0 = st0["mclk"]
            loops = efs = rem = clr = 0
            foreign = []
            ranges = [f.dr_range] + list(f.callee_ranges.values())
            n_steps = 0
            while True:
                st = await rig.step(1)
                n_steps += 1
                pc = int(st["pc"], 16)
                if pc == ret:
                    m1 = st["mclk"]
                    break
                if pc == f.dr_loop:
                    loops += 1
                elif pc == f.EntityWindow_EntryForSection:
                    efs += 1
                elif pc == f.RingBuffer_Remove:
                    rem += 1
                elif pc == f.EntityLoaded_Clear:
                    clr += 1
                if not any(a <= pc < b for a, b in ranges):
                    foreign.append(pc)
                if n_steps > 200000:
                    raise CouldNotRun("the DespawnRings trace did not return in 200000 steps")
            after = await rig.rb(f.Ring_Count)
            # the same window with no stepping, from the same entry state
            await rig.restore(entry_state)
            await rig.wr(f.Ring_Buffer, buf)
            await rig.wb(f.Ring_Count, N)
            mA = (await rig.status())["mclk"]
            r = await stop_at_entry(rig, ret, 1, "DespawnRings' return")
            mB = r["mclk"]
        finally:
            await rig.restore(entry_state)
            await rig.drop(entry_state)
        rec = dict(variant=variant, attempt=attempt, frame=st0["frame"], cam=(cx, cy),
                   tracked=tracked, natural=natural, sec=sec, x=x, y=y, steps=n_steps,
                   loops=loops, efs=efs, rem=rem, clr=clr, foreign=len(foreign),
                   mclk=m1 - m0, mclk_run=mB - mA, after=after)
        rec["cycles"] = rec["mclk"] / MCLK_PER_68K_CYCLE
        rec["model"] = cost_model(N, variant == "remove")
        out.append(f"  [{variant}] attempt {attempt}, frame {rec['frame']}: camera {rec['cam']}, "
                   f"tracked ids {tracked}, natural Ring_Count {natural}; seeded {N} x "
                   f"(x={x}, y={y}, sec={sec}); {n_steps} instructions stepped, {loops} loop "
                   f"passes, EntryForSection x{efs}, RingBuffer_Remove x{rem}, EntityLoaded_Clear "
                   f"x{clr}, {len(foreign)} steps outside the proc and its callees; mclk "
                   f"{rec['mclk']} stepped / {rec['mclk_run']} run_to -> "
                   f"{rec['cycles']:.2f} cycles (model {rec['model']}); Ring_Count after {after}")
        if not foreign:
            return rec
        out.append(f"  [{variant}] attempt {attempt} had an interrupt inside the window; discarded, "
                   f"using the next frame's call")
        await rig.frames(1)
    raise CouldNotRun(f"no interrupt-free DespawnRings window in {tries} frames")


async def w_c4a3(rig: Rig, boot: str, out: list) -> tuple[str, str]:
    f = rig.f
    N = f.MAX_RING_BUFFER
    await rig.restore(boot)
    k = await profile_once(rig, "keep", out)
    await rig.restore(boot)
    r = await profile_once(rig, "remove", out)
    ok_k = (k["loops"] == N and k["rem"] == 0 and k["efs"] == 0 and k["after"] == N
            and k["mclk"] == k["mclk_run"] and k["mclk"] % MCLK_PER_68K_CYCLE == 0)
    ok_r = (r["loops"] == N and r["rem"] == N and r["efs"] == N and r["clr"] == 0
            and r["after"] == 0 and r["mclk"] == r["mclk_run"]
            and r["mclk"] % MCLK_PER_68K_CYCLE == 0)
    model = k["cycles"] == k["model"] and r["cycles"] == r["model"]
    out.append(f"  hand-derived model agreement: keep {k['cycles']:.0f} vs {k['model']}, remove "
               f"{r['cycles']:.0f} vs {r['model']} -> {model}")
    if ok_k and ok_r and model:
        return "WITNESSED", (f"full buffer ({N}): keep-all {k['cycles']:.0f} cycles "
                             f"({k['mclk']} mclk), remove-all {r['cycles']:.0f} cycles "
                             f"({r['mclk']} mclk); both equal the hand-derived model")
    return "NOT WITNESSED", (f"keep ok={ok_k}, remove ok={ok_r}, model agreement={model} "
                             f"(keep {k['cycles']:.2f}/{k['model']}, remove "
                             f"{r['cycles']:.2f}/{r['model']})")


# --------------------------------------------------------------------------- driver

RUNNERS = {"c2a6": w_c2a6, "multisprite": w_multisprite, "nullmap": w_nullmap,
           "c4a2": w_c4a2, "c4a3": w_c4a3}


async def drive(sock: str, f: Facts, which: list) -> list:
    b = BusClient(socket_path=sock, client_id="lens-residue-witness",
                  client_name="lens_residue_object_witness")
    await b.connect()
    rig = Rig(b, f)
    results = []
    try:
        await rig.call("emulator/checkpoint_drop", {"all": True})
        boot_out: list = []
        boot = await boot_checkpoint(rig, boot_out)
        for line in boot_out:
            print(line)
        for w in which:
            out: list = []
            t0 = time.monotonic()
            try:
                verdict, why = await RUNNERS[w](rig, boot, out)
            except CouldNotRun as e:
                verdict, why = "COULD NOT RUN", str(e)
            dt = time.monotonic() - t0
            print(f"\n== {w}")
            for line in out:
                print(line)
            print(f"  -> {verdict}: {why}  [{dt:.1f} s]")
            results.append((w, verdict, why))
            await rig.call("emulator/release_all")
    finally:
        await b.close()
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("witness", choices=WITNESSES + ("all",))
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--lst", default=None, help="default: the .lst beside the ROM")
    a = ap.parse_args()
    lst = a.lst or str(Path(a.rom).with_suffix(".lst"))
    which = list(WITNESSES) if a.witness == "all" else [a.witness]
    print(f"lens_residue_object_witness  {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    try:
        f = Facts(a.rom, lst)
    except CouldNotRun as e:
        print(f"COULD NOT RUN (setup): {e}")
        return 2
    print(f"ROM {a.rom} crc32 {f.crc:08x} / {f.rom_len} B (verified); listing {lst}")
    inst = AetherInstance(a.rom, symbols=lst)
    pid = None
    try:
        sock = inst.start()
        pid = inst.pid
        print(f"own oracle-aether pid {pid}, socket {sock}, serverName "
              f"{inst.handshake.get('serverName')!r} implementation "
              f"{inst.handshake.get('implementation')!r}")
        results = asyncio.run(drive(sock, f, which))
    except CouldNotRun as e:
        print(f"COULD NOT RUN: {e}")
        results = [(w, "COULD NOT RUN", str(e)) for w in which]
    finally:
        inst.reap()
        if pid is not None:
            try:
                os.kill(pid, 0)
                print(f"WARNING: server pid {pid} still exists after reap")
            except ProcessLookupError:
                print(f"server pid {pid} reaped: gone")
    print("\nVERDICTS")
    for w, v, why in results:
        print(f"  {w:<12} {v:<14} {why}")
    vs = [v for _, v, _ in results]
    if "NOT WITNESSED" in vs:
        return 1
    if "COULD NOT RUN" in vs:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
