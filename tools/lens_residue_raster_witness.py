#!/usr/bin/env python3
"""lens_residue_raster_witness.py: three still-owed runtime witnesses, run headless on a debug ROM.

A WITNESS TOOL, NOT A BUILD GATE. Nothing in build.sh or the pytest lanes runs this file,
and nothing should. It boots its own `oracle-aether` through `tools/aether_instance.py`,
one fresh instance per witness, and reaps each one on the way out.

    efx4b   EFX-4b: a static install of a LONGER program followed by a SHORTER one leaves
            Raster_Buf_A holding the short program's ROM image and zeros to RASTER_BUF_SIZE.
    c1b3    C1b-3: Collision_GetType adds Cache_Origin_Row before halving. With physics on,
            the player lands where the committed collision data says, and every
            Collision_GetType call made while he stands there returns the committed cell,
            at a NON-ZERO origin and (control) at origin 0.
    c3b2    C3b-2: the lag-frame residue. Every VInt_Lag in a bounded diagonal flight is
            stopped, and its interrupted PC is classified against Effects_LatchWorldLines'
            two per-channel store loops.
    c3b2s7  C3b-2 in SECTION 7, the one place in OJZ act 1 with two live, moving patch records
            (channels 2 and 3, a sweep on 2, so the .mch loop runs). The flight is warped into
            the section through the warp mailbox and bounces inside the camera band where both
            records are live and unclamped; every VInt_Lag is classified for channel 2 stored,
            channel 3 not. Also measures where the latch runs in its tick, in that section.
    all     efx4b, c1b3 and c3b2, in that order (c3b2s7 is run by name).

Verdicts: WITNESSED / NOT WITNESSED / NOT OBSERVED / COULD NOT RUN. Exit status: 1 if any
witness is NOT WITNESSED; otherwise 2 if any COULD NOT RUN; otherwise 0. C3b-2's NOT
OBSERVED is an allowed result (it prints the rate bound it implies) and does not fail the run.

WHERE EVERY EXPECTED VALUE COMES FROM. Nothing below is copied from a note:
  * addresses are read from the listing's symbol block, and the server refuses a listing that
    does not bind to the ROM;
  * RASTER_BUF_SIZE, RASTER_OPS_END, RASTER_ARM_PARK, RASTER_MAX_PATCH, LAB_ENTRY_SIZE,
    LAB_KIND_RASTER, PLAYER_DEBUG_FLY_SPEED and PlayerV's field layout are read from the
    `.emp` sources in THIS tree, and each source file the build also read is checked against
    the listing's DIGEST-READ crc before it is trusted;
  * a static program's length is walked out of its own ROM image (last non-zero word, which
    must be the RASTER_ARM_PARK + RASTER_OPS_END terminator);
  * floor heights and per-cell collision come from the COMMITTED editor planes
    (games/sonic4/data/editor/ojz/act1/section_0.collattr{,b}.bin) and base bank
    (games/sonic4/data/collision/base/), baked through tools/collision_pipeline.py's own
    bake_plane_cell, the function the level build uses. The files are compared byte for byte
    with the copies in the ROM's own tree when that tree is on disk;
  * the latch loop's store and dbra addresses are decoded out of the ROM's bytes with
    capstone, between the listing's `$...$plain_ch` / `$...$mch` labels and their dbra.

Usage:
    python3 tools/lens_residue_raster_witness.py all --rom s4.debug.bin --lst s4.debug.lst \\
        [--expect-crc 9ce1c2ff] [--lag-budget 3000]
"""
from __future__ import annotations

import argparse
import asyncio
import bisect
import datetime
import re
import sys
import tempfile
import time
import zlib
from pathlib import Path

# A fresh bytecode cache for every run, so no stale .pyc of an imported tool can be served
# (a same-length edit within one second is otherwise read from cache).
sys.pycache_prefix = tempfile.mkdtemp(prefix="lrrw-pyc-")

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from aether_instance import aether_emulator, read_bytes, write_bytes  # noqa: E402
from aether import BusClient  # noqa: E402

WITNESSED = "WITNESSED"
NOT_WITNESSED = "NOT WITNESSED"
NOT_OBSERVED = "NOT OBSERVED"
COULD_NOT_RUN = "COULD NOT RUN"

BOOT_FRAMES = 400            # the controller's and s7's boot point; the scene is settled by then
SETTLE_STILL_FRAMES = 30     # a landing counts as "at rest" after this many unchanged frames
SETTLE_MAX_FRAMES = 400
LOOKUP_CAPTURE_FRAMES = 2    # Collision_GetType calls are captured over this many frames
LOOKUP_CAPTURE_CAP = 240
LATCH_TIMING_SAMPLES = 240   # C3b-2 context: ticks sampled for where the latch runs
MCLK_PER_FRAME = 896040      # NTSC; oracle-aether's handshake timingBasis, checked at run time
LINES_PER_FRAME = 262

_SYM = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
_EQU = re.compile(r"^EQU ([A-Za-z_]\w*) = \$([0-9A-Fa-f]+)\s*$")
_DIGEST = re.compile(r"^DIGEST-READ crc=([0-9a-f]{8}) size=(\d+) origin=\w+ path=(\S+)\s*$")


class CouldNotRun(Exception):
    """A precondition of the experiment failed. Never a verdict about the subject."""


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- the build's facts

class Build:
    def __init__(self, rom: str, lst: str):
        self.rom_path = Path(rom).resolve()
        self.lst_path = Path(lst).resolve()
        self.rom = self.rom_path.read_bytes()
        self.crc = zlib.crc32(self.rom) & 0xFFFFFFFF
        self.sym: dict[str, int] = {}
        self.equ: dict[str, int] = {}
        self.digest: dict[str, tuple[str, int]] = {}
        for line in self.lst_path.read_text(errors="replace").splitlines():
            m = _SYM.match(line)
            if m:
                self.sym.setdefault(m.group(1), int(m.group(2), 16) & 0xFFFFFF)
                continue
            m = _EQU.match(line)
            if m:
                self.equ.setdefault(m.group(1), int(m.group(2), 16))
                continue
            m = _DIGEST.match(line)
            if m:
                self.digest[m.group(3)] = (m.group(1), int(m.group(2)))
        self.checked_sources: list[str] = []

    def s(self, name: str) -> int:
        if name not in self.sym:
            raise CouldNotRun(f"{name} is not in {self.lst_path} (wrong ROM/listing pair?)")
        return self.sym[name]

    def e(self, name: str) -> int:
        if name not in self.equ:
            raise CouldNotRun(f"{name} has no EQU in {self.lst_path}")
        return self.equ[name]

    def rom_u16(self, addr: int) -> int:
        return int.from_bytes(self.rom[addr:addr + 2], "big")

    def rom_u32(self, addr: int) -> int:
        return int.from_bytes(self.rom[addr:addr + 4], "big")

    # ---- source provenance: a file this tool derives from must be the file the build read
    def source(self, rel: str) -> bytes:
        p = ROOT / rel
        data = p.read_bytes()
        if rel in self.digest:
            want_crc, want_size = self.digest[rel]
            got = f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
            if got != want_crc or len(data) != want_size:
                raise CouldNotRun(f"{rel} in this tree (crc {got}, {len(data)} B) is not the file "
                                  f"the build read (DIGEST-READ crc {want_crc}, {want_size} B): "
                                  f"every value derived from it would describe another build")
            note = f"{rel} crc {got} = listing DIGEST-READ"
        else:
            twin = self.rom_path.parent / rel
            if twin.is_file():
                if twin.read_bytes() != data:
                    raise CouldNotRun(f"{rel} differs from the copy in the ROM's tree ({twin})")
                note = f"{rel} byte-identical to the ROM tree's copy"
            else:
                note = f"{rel} (no digest row, no ROM-tree copy to compare: UNVERIFIED)"
        if note not in self.checked_sources:
            self.checked_sources.append(note)
        return data

    def src_const(self, rel: str, name: str) -> int:
        text = self.source(rel).decode("utf-8", "replace")
        m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)\b",
                      text, re.M)
        if not m:
            raise CouldNotRun(f"no `const {name} = <literal>` in {rel}")
        v = m.group(1)
        return int(v[1:], 16) if v.startswith("$") else int(v)


# --------------------------------------------------------------------------- the machine

def _regval(v) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s.startswith("$"):
        s = s[1:]
    elif s[:2].lower() == "0x":
        s = s[2:]
    return int(s, 16)


class Machine:
    def __init__(self, b: BusClient, build: Build):
        self.b = b
        self.k = build

    async def rd(self, addr: int, n: int) -> bytes:
        out = b""
        while n > 0:
            chunk = min(n, 4096)
            out += bytes.fromhex(await read_bytes(self.b, addr, chunk))
            addr += chunk
            n -= chunk
        return out

    async def u8(self, addr): return (await self.rd(addr, 1))[0]
    async def u16(self, addr): return int.from_bytes(await self.rd(addr, 2), "big")
    async def u32(self, addr): return int.from_bytes(await self.rd(addr, 4), "big")

    async def s16(self, addr):
        v = await self.u16(addr)
        return v - 0x10000 if v & 0x8000 else v

    async def wr(self, addr: int, data: bytes):
        await write_bytes(self.b, addr, data.hex())

    async def frames(self, n: int):
        while n > 0:
            step = min(n, 3600)
            await self.b.call("emulator/run_frames", {"frames": step})
            n -= step

    async def buttons(self, *names: str):
        """Make the held set EXACTLY `names` (release everything, then hold the list)."""
        await self.b.call("emulator/release_all", {})
        if names:
            await self.b.call("emulator/hold", {"buttons": list(names), "down": True})

    async def run_to(self, addr: int, max_frames: int) -> bool:
        return bool((await self.run_to_reply(addr, max_frames)).get("reached"))

    async def run_to_reply(self, addr: int, max_frames: int) -> dict:
        return await self.b.call("emulator/run_to", {"addr": hex(addr), "maxFrames": max_frames})

    async def mclk(self, reply: dict | None = None) -> int:
        if reply and "mclk" in reply:
            return int(reply["mclk"])
        st = await self.b.call("emulator/status", {})
        if "mclk" not in st:
            raise CouldNotRun(f"neither run_to nor status reports mclk; status keys {sorted(st)}")
        return int(st["mclk"])

    async def step(self, n: int = 1):
        await self.b.call("emulator/step", {"count": n})

    async def step_out(self):
        await self.b.call("emulator/step_out", {})

    async def regs(self) -> dict:
        raw = await self.b.call("emulator/registers", {})
        out = {}
        for k, v in raw.items():
            if isinstance(v, (int, str)):
                try:
                    out[k.lower()] = _regval(v)
                except ValueError:
                    pass
            elif isinstance(v, list) and k.lower() in ("d", "a"):
                for i, x in enumerate(v):
                    out[f"{k.lower()}{i}"] = _regval(x)
        if "sp" not in out:
            for alt in ("a7", "ssp", "isp"):
                if alt in out:
                    out["sp"] = out[alt]
                    break
        for need in ("pc", "sp", "d0", "d1", "d3"):
            if need not in out:
                raise CouldNotRun(f"emulator/registers carries no {need!r}; keys: {sorted(raw)}")
        return out

    async def frame(self) -> int:
        return int((await self.b.call("emulator/status", {}))["frame"])


def boot_session(build: Build, body):
    """Spawn a fresh oracle-aether on the ROM, run `body(machine)`, reap. Returns body's value."""
    with aether_emulator(str(build.rom_path), symbols=str(build.lst_path)) as sock:
        async def go():
            b = BusClient(socket_path=sock, client_id="lrrw", client_name="lens_residue_raster_witness")
            await b.connect()
            try:
                return await body(Machine(b, build))
            finally:
                await b.close()
        return asyncio.run(go())


# --------------------------------------------------------------------------- player view

class PlayerView:
    """Player_1's fields, located by the listing's SST_* equates and PlayerV's source layout."""

    FIELD_SIZES = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}

    def __init__(self, build: Build):
        self.k = build
        self.base = build.s("Player_1")
        self.off = {n: build.e(f"SST_{n}") for n in
                    ("x_pos", "y_pos", "status", "width_pixels", "height_pixels", "layer",
                     "sst_custom")}
        # PlayerV is a VIEW at Sst.sst_custom (games/sonic4/player/player_common.emp). Its
        # offsets are summed from the declared field types, and the one the listing exports
        # (_pl_flip_angle) is checked against the same sum so a misparse cannot pass silently.
        text = build.source("games/sonic4/player/player_common.emp").decode("utf-8", "replace")
        m = re.search(r"pub vars PlayerV: Sst\.sst_custom \{(.*?)\n\}", text, re.S)
        if not m:
            raise CouldNotRun("PlayerV's declaration was not found in player_common.emp")
        offs, cur = {}, self.off["sst_custom"]
        for fm in re.finditer(r"^\s*(\w+):\s*(u8|i8|u16|i16|u32|i32)\s*,", m.group(1), re.M):
            offs[fm.group(1)] = cur
            cur += self.FIELD_SIZES[fm.group(2)]
        for need in ("player_state", "debug_flag", "flip_angle"):
            if need not in offs:
                raise CouldNotRun(f"PlayerV.{need} not found while summing the layout")
        if offs["flip_angle"] != build.e("_pl_flip_angle"):
            raise CouldNotRun(f"PlayerV layout sum puts flip_angle at ${offs['flip_angle']:02X}, the "
                              f"listing's _pl_flip_angle is ${build.e('_pl_flip_angle'):02X}")
        if offs["player_state"] != build.e("_pl_state"):
            raise CouldNotRun("PlayerV layout sum disagrees with _pl_state")
        self.off["player_state"] = offs["player_state"]
        self.off["debug_flag"] = offs["debug_flag"]

    async def read(self, m: Machine) -> dict:
        k = self.k
        p = self.base
        o = self.off
        return dict(
            frame=await m.frame(),
            x=await m.s16(p + o["x_pos"]), y=await m.s16(p + o["y_pos"]),
            status=await m.u8(p + o["status"]), w=await m.u8(p + o["width_pixels"]),
            h=await m.u8(p + o["height_pixels"]), layer=await m.u8(p + o["layer"]),
            pstate=await m.u8(p + o["player_state"]), fly=await m.u8(p + o["debug_flag"]),
            camx=await m.s16(k.s("Camera_X")), camy=await m.s16(k.s("Camera_Y")),
            top=await m.u16(k.s("Cache_Top_Row")), bottom=await m.u16(k.s("Cache_Bottom_Row")),
            origin=await m.u16(k.s("Cache_Origin_Row")),
        )


def fmt_state(s: dict) -> str:
    return (f"frame {s['frame']} player ({s['x']},{s['y']}) box {s['w']}x{s['h']} layer {s['layer']} "
            f"state {s['pstate']} fly {s['fly']} status ${s['status']:02X} camera ({s['camx']},{s['camy']}) "
            f"Cache_Top_Row {s['top']} Cache_Origin_Row {s['origin']}")


# =========================================================================== EFX-4b

def static_len(build: Build, img: bytes, name: str, ops_end: int, arm_park: int) -> int:
    """A static program's length in BYTES, walked out of its own ROM image: through its
    last non-zero word, which must be the terminator record [RASTER_ARM_PARK][RASTER_OPS_END]."""
    words = [int.from_bytes(img[i:i + 2], "big") for i in range(0, len(img), 2)]
    last = max((i for i, w in enumerate(words) if w), default=-1)
    if last < 1 or words[last] != ops_end or words[last - 1] != arm_park:
        raise CouldNotRun(f"{name}: the last non-zero word of its {len(img)}-byte ROM image is not "
                          f"a [${arm_park:04X}][${ops_end:04X}] terminator (words {words[max(0, last - 2):last + 1]})")
    return (last + 1) * 2


def run_efx4b(build: Build, out: list) -> str:
    k = build
    raster_src = "engine/effects/raster.emp"
    buf_size = k.src_const(raster_src, "RASTER_BUF_SIZE")
    ops_end = k.src_const(raster_src, "RASTER_OPS_END")
    arm_park = k.src_const(raster_src, "RASTER_ARM_PARK")
    buf_a, buf_b = k.s("Raster_Buf_A"), k.s("Raster_Buf_B")
    if buf_b - buf_a != buf_size:
        raise CouldNotRun(f"Raster_Buf_B - Raster_Buf_A = {buf_b - buf_a}, RASTER_BUF_SIZE = {buf_size}")
    lab_src = "games/sonic4/test/ojz_scroll_test.emp"
    entry_size = k.src_const(lab_src, "LAB_ENTRY_SIZE")
    kind_raster = k.src_const(lab_src, "LAB_KIND_RASTER")
    count = k.src_const(lab_src, "LAB_CYCLE_COUNT")

    long_name, short_name = "OJZ_BandDemo", "OJZ_BaseSwap"
    prog = {}
    for n in (long_name, short_name):
        a = k.s(n)
        img = k.rom[a:a + buf_size]
        prog[n] = dict(addr=a, img=img, len=static_len(k, img, n, ops_end, arm_park))
    L, S = prog[long_name], prog[short_name]
    out.append(f"  RASTER_BUF_SIZE {buf_size} (raster.emp; = Raster_Buf_B - Raster_Buf_A). Terminator "
               f"[${arm_park:04X}][${ops_end:04X}] (raster.emp RASTER_ARM_PARK / RASTER_OPS_END)")
    for n in (long_name, short_name):
        p = prog[n]
        out.append(f"  {n} ${p['addr']:06X}: {p['len']} B through its terminator (walked from the ROM "
                   f"image); ROM image bytes [{p['len']}..{buf_size}) non-zero: "
                   f"{sum(1 for x in p['img'][p['len']:] if x)}")
    if not S["len"] < L["len"]:
        raise CouldNotRun(f"{short_name} ({S['len']} B) is not shorter than {long_name} ({L['len']} B)")
    long_tail = L["img"][S["len"]:L["len"]]
    if not any(long_tail):
        raise CouldNotRun(f"{long_name}'s ROM bytes [{S['len']}..{L['len']}) are all zero, so its "
                          f"install could not serve as the control")

    # the lab rows that install them, read out of the ROM's own table, not a comment
    lab = k.s("Debug_LabCycleHotkey.lab_index")
    rtab = k.s("Debug_LabCycleHotkey.raster_table")
    rows = {}
    for r in range(count):
        kind, sub = k.rom[lab + r * entry_size], k.rom[lab + r * entry_size + 1]
        if kind == kind_raster:
            ptr = k.rom_u32(rtab + 4 * sub) & 0xFFFFFF
            for n in (long_name, short_name):
                if ptr == prog[n]["addr"]:
                    rows[n] = r
    if long_name not in rows or short_name not in rows or rows[short_name] != rows[long_name] + 1:
        raise CouldNotRun(f"the ROM's lab table does not put {short_name} one row after {long_name}: {rows}")
    out.append(f"  lab rows (ROM table Debug_LabCycleHotkey.lab_index, {entry_size}-byte rows, kind "
               f"{kind_raster} = raster): {long_name} row {rows[long_name]}, {short_name} row {rows[short_name]}")

    no_install = k.s("$engine.effects.raster$Raster_VBlank$no_install")

    async def body(m: Machine):
        await m.frames(BOOT_FRAMES)
        pre = dict(program=await m.u32(k.s("Raster_Program")),
                   tab=await m.u32(k.s("Raster_Patch_Tab")),
                   active=await m.u32(k.s("Raster_Active_Buf")),
                   lab=await m.u8(k.s("Debug_Lab_Index")))
        out.append(f"  boot+{BOOT_FRAMES}: Raster_Program ${pre['program'] & 0xFFFFFF:06X} "
                   f"Raster_Patch_Tab ${pre['tab']:06X} Raster_Active_Buf ${pre['active'] & 0xFFFFFF:06X} "
                   f"Debug_Lab_Index {pre['lab']} (section 0's own install is "
                   f"{'PATCHED' if pre['tab'] else 'static'})")
        await m.wr(k.s("Debug_Lab_Index"), bytes([rows[long_name] - 1]))

        async def lab_step(target: str) -> dict:
            """START held, RIGHT pressed: the real hotkey, through Raster_Install. Stops at
            Raster_VBlank's .no_install on every VBlank until the one that consumed the
            install, i.e. immediately after its fixed RASTER_BUF_SIZE copy."""
            await m.buttons("start")
            await m.frames(3)
            await m.buttons("start", "right")
            want = prog[target]["addr"]
            for _ in range(10):
                if not await m.run_to(no_install, 3):
                    raise CouldNotRun("Raster_VBlank's .no_install was not reached within 3 frames")
                pend = await m.u32(k.s("Raster_Pending"))
                progv = await m.u32(k.s("Raster_Program")) & 0xFFFFFF
                if pend == 0 and progv == want:
                    snap = dict(program=progv, tab=await m.u32(k.s("Raster_Patch_Tab")),
                                active=await m.u32(k.s("Raster_Active_Buf")) & 0xFFFFFF,
                                lab=await m.u8(k.s("Debug_Lab_Index")),
                                buf=await m.rd(buf_a, buf_size), frame=await m.frame())
                    await m.buttons()
                    return snap
                await m.step(1)
            await m.buttons()
            raise CouldNotRun(f"the lab step never installed {target} (Raster_Program "
                              f"${progv:06X}, Debug_Lab_Index {await m.u8(k.s('Debug_Lab_Index'))})")

        first = await lab_step(long_name)
        second = await lab_step(short_name)
        await m.frames(2)
        later = await m.rd(buf_a, buf_size)
        return first, second, later

    first, second, later = boot_session(build, body)
    fails = []

    def check(snap, name):
        p = prog[name]
        rows_ok = snap["lab"] == rows[name]
        out.append(f"  after the {name} install (stopped at .no_install, frame {snap['frame']}): "
                   f"Debug_Lab_Index {snap['lab']}, Raster_Program ${snap['program']:06X}, "
                   f"Raster_Patch_Tab ${snap['tab']:06X}, Raster_Active_Buf ${snap['active']:06X}")
        if not rows_ok:
            fails.append(f"{name}: Debug_Lab_Index {snap['lab']}, expected {rows[name]}")
        if snap["program"] != p["addr"]:
            fails.append(f"{name}: Raster_Program ${snap['program']:06X}, want ${p['addr']:06X}")
        if snap["tab"] != 0:
            fails.append(f"{name}: Raster_Patch_Tab ${snap['tab']:06X}, want 0")
        if snap["active"] != buf_a:
            fails.append(f"{name}: Raster_Active_Buf ${snap['active']:06X}, want Raster_Buf_A ${buf_a:06X}")

    # ---- CONTROL: the longer install put non-zero bytes where the shorter one must leave zero
    check(first, long_name)
    ctl_nonzero = sum(1 for x in first["buf"][S["len"]:L["len"]] if x)
    ctl_image = first["buf"] == L["img"]
    out.append(f"  CONTROL  Raster_Buf_A[{S['len']}..{L['len']}) after {long_name}: {ctl_nonzero} of "
               f"{L['len'] - S['len']} bytes non-zero; Buf_A[0..{buf_size}) == ROM image: {ctl_image}")
    out.append(f"           Buf_A[{S['len']}..{S['len'] + 16}) = {first['buf'][S['len']:S['len'] + 16].hex()}")
    if not ctl_image:
        fails.append(f"{long_name}: Raster_Buf_A is not its 128-byte ROM image after install")
    if ctl_nonzero == 0:
        return verdict_block(out, "EFX-4b", COULD_NOT_RUN,
                             ["the control failed: the longer install left the tail zero, so a zero "
                              "tail after the shorter one would prove nothing"])

    # ---- the witness
    check(second, short_name)
    head_ok = second["buf"][:S["len"]] == S["img"][:S["len"]]
    tail = second["buf"][S["len"]:]
    tail_nonzero = [i + S["len"] for i, x in enumerate(tail) if x]
    out.append(f"  MEASURED Raster_Buf_A[0..{S['len']}) == {short_name}'s ROM image: {head_ok}; "
               f"Raster_Buf_A[{S['len']}..{buf_size}) non-zero bytes: {len(tail_nonzero)}"
               + (f" at {tail_nonzero[:12]}" if tail_nonzero else " (all zero)"))
    out.append(f"           Buf_A[{S['len']}..{S['len'] + 16}) = {tail[:16].hex()}")
    stable = later == second["buf"]
    out.append(f"  two frames later Raster_Buf_A unchanged: {stable}")
    if not head_ok:
        fails.append(f"{short_name}: Raster_Buf_A[0..{S['len']}) differs from the ROM image")
    if tail_nonzero:
        fails.append(f"{short_name}: {len(tail_nonzero)} non-zero byte(s) past its terminator in "
                     f"Raster_Buf_A: the longer program's residue survived")
    if not stable:
        fails.append("Raster_Buf_A changed in the two frames after the install")
    return verdict_block(out, "EFX-4b", NOT_WITNESSED if fails else WITNESSED, fails)


# =========================================================================== C1b-3

class Committed:
    """Section 0's committed collision, baked through the level build's own bake_plane_cell."""

    def __init__(self, build: Build):
        import collision_pipeline as cp   # tools/, the same module the level build imports
        self.cp = cp
        self.k = build
        rel = "games/sonic4/data/editor/ojz/act1"
        self.plane = {0: build.source(f"{rel}/section_0.collattr.bin"),
                      1: build.source(f"{rel}/section_0.collattrb.bin")}
        self.hm = build.source("games/sonic4/data/collision/base/heightmaps.bin")
        self.an = build.source("games/sonic4/data/collision/base/angles.bin")
        n = len(self.plane[0]) // 2
        self.W = int(round(n ** 0.5))
        if self.W * self.W * 2 != len(self.plane[0]):
            raise CouldNotRun("section_0.collattr.bin is not a square plane of 16-bit words")
        self.cw = build.e("COLL_CELL_W")
        self.ch = build.e("COLL_CELL_H")
        self.sec = build.e("SECTION_SIZE")
        self.solid_top = build.e("SOLID_TOP")
        if self.W * 8 != self.sec:
            raise CouldNotRun(f"editor plane is {self.W} tiles, section is {self.sec} px")
        self._memo = {}

    def cell(self, layer: int, x: int, y: int):
        """(heights, angle, solidity, xover, baked_index, word) of the cell holding world (x, y)
        in section 0 on `layer`, or None outside section 0."""
        if not (0 <= x < self.sec and 0 <= y < self.sec) or layer not in self.plane:
            return None
        col, cr = x // self.cw, y // self.ch
        key = (layer, col, cr)
        if key not in self._memo:
            o = (cr * (self.ch // 8)) * self.W + col      # the TOP tile row of the 16 px cell,
            buf = self.plane[layer]                      # which is the row the bake samples
            word = (buf[2 * o] << 8) | buf[2 * o + 1]
            aset = self.cp.AttrSet()
            idx = self.cp.bake_plane_cell(word, self.hm, self.an, aset)
            heights, angle, sol, xover = aset.entries[idx]
            self._memo[key] = (bytes(heights), angle, sol, xover, idx, word)
        return self._memo[key]

    def surface(self, layer: int, x: int, y0: int):
        """The first floor-class solid pixel row at or below y0 in column x."""
        cr = y0 // self.ch
        while cr * self.ch < self.sec:
            c = self.cell(layer, x, cr * self.ch)
            if c is None:
                return None
            heights, _angle, sol, _xo, idx, _w = c
            if idx and (sol & self.solid_top):
                h = heights[x & 15]
                if h:
                    first = 0 if h >= 0x80 else (self.ch - h)     # hanging runs start at the top
                    y = cr * self.ch + first
                    if y >= y0:
                        return y
            cr += 1
        return None

    def rom_attr(self, attr: int):
        k = self.k
        hm = k.rom[k.s("HeightMaps") + attr * 16: k.s("HeightMaps") + attr * 16 + 16]
        return (hm, k.rom[k.s("AngleTable") + attr], k.rom[k.s("SolidityTable") + attr],
                k.rom[k.s("CrossoverTable") + attr])


async def settle(m: Machine, pv: PlayerView, k: Build):
    """Frame by frame until the player is grounded and nothing (y, camera, origin) has moved
    for SETTLE_STILL_FRAMES frames. Returns (first grounded state, rest state)."""
    ground = k.e("PSTATE_GROUND")
    in_air = k.e("ST_IN_AIR")
    first = None
    prev = None
    still = 0
    for _ in range(SETTLE_MAX_FRAMES):
        await m.frames(1)
        s = await pv.read(m)
        grounded = s["pstate"] == ground and not (s["status"] >> in_air) & 1 and s["fly"] == 0
        if grounded and first is None:
            first = s
        key = (s["y"], s["camy"], s["origin"], grounded)
        still = still + 1 if key == prev else 0
        prev = key
        if first is not None and grounded and still >= SETTLE_STILL_FRAMES:
            return first, s
    raise CouldNotRun(f"the player never came to rest on the ground within {SETTLE_MAX_FRAMES} frames "
                      f"(last: {fmt_state(s)})")


async def capture_lookups(m: Machine, k: Build) -> list:
    """Every Collision_GetType call over LOOKUP_CAPTURE_FRAMES frames: its inputs at entry, the
    cache window and origins it reads, and what it returned."""
    entry = k.s("Collision_GetType")
    win = [k.s(n) for n in ("Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row",
                            "Cache_Bottom_Row", "Cache_Origin_Col", "Cache_Origin_Row")]
    f_end = await m.frame() + LOOKUP_CAPTURE_FRAMES
    calls = []
    while len(calls) < LOOKUP_CAPTURE_CAP:
        if not await m.run_to(entry, LOOKUP_CAPTURE_FRAMES + 1):
            break
        if await m.frame() >= f_end:
            break
        r = await m.regs()
        ret_addr = await m.u32(r["sp"] & 0xFFFFFF) & 0xFFFFFF     # the bus is 24 bits
        w = [await m.u16(a) for a in win]
        await m.step_out()
        r2 = await m.regs()
        if r2["pc"] & 0xFFFFFF != ret_addr:
            raise CouldNotRun(f"step_out from Collision_GetType stopped at ${r2['pc'] & 0xFFFFFF:06X}, "
                              f"not the stacked return ${ret_addr:06X}")
        calls.append(dict(x=r["d0"] & 0xFFFF, y=r["d1"] & 0xFFFF, layer=r["d3"] & 0xFF,
                          ret=r2["d0"] & 0xFF, left=w[0], head=w[1], top=w[2], bottom=w[3],
                          ocol=w[4], orow=w[5], caller=ret_addr))
    return calls


def grade_lookups(calls: list, com: Committed, tag: str, out: list, fails: list) -> dict:
    """Grade every captured call against the committed cell. Also counts how many calls an
    ORIGIN-BLIND lookup (the origin dropped, physical row = row - Cache_Top_Row) would have
    answered with a DIFFERENT cell: that is what makes a match mean something at this origin.
    At origin 0 the count is 0 by construction. The pre-C1b-3 form floor(L/2) + O/2 equals the
    shipped floor((L+O)/2) for every even O, so NO run can tell those two apart; this grades
    the shipped form against the data, not the refactor against its predecessor."""
    rows = com.k.e("TILE_CACHE_ROWS")
    st = dict(n=len(calls), in_win=0, solid=0, air=0, out_win=0, match=0, mismatch=0, nocmp=0,
              origins=set(), layers=set(), discrim=0)
    for c in calls:
        st["origins"].add(c["orow"])
        st["layers"].add(c["layer"])
        col, row = c["x"] >> 3, c["y"] >> 3
        if not (c["left"] <= col <= c["head"] and c["top"] <= row <= c["bottom"]):
            st["out_win"] += 1
            ok = c["ret"] == 0
        else:
            st["in_win"] += 1
            cell = com.cell(c["layer"], c["x"], c["y"])
            if cell is None:
                st["nocmp"] += 1
                continue
            heights, angle, sol, xover, idx, word = cell
            # physical row p holds logical row top + ((p - O) mod ROWS); the blind form reads p = row - top
            blind_row = c["top"] + (((row - c["top"]) - c["orow"]) % rows)
            blind = com.cell(c["layer"], c["x"], blind_row * 8)
            if blind is not None and blind[:4] != cell[:4]:
                st["discrim"] += 1
            if idx == 0:
                st["air"] += 1
                ok = c["ret"] == 0
            else:
                st["solid"] += 1
                ok = c["ret"] != 0 and com.rom_attr(c["ret"]) == (heights, angle, sol, xover)
        if ok:
            st["match"] += 1
        else:
            st["mismatch"] += 1
            if st["mismatch"] <= 6:
                fails.append(f"{tag}: Collision_GetType({c['x']},{c['y']}, layer {c['layer']}) "
                             f"returned attr {c['ret']} at Cache_Origin_Row {c['orow']}, which is "
                             f"not the committed cell")
    out.append(f"  {tag} Collision_GetType calls over {LOOKUP_CAPTURE_FRAMES} frames: {st['n']} "
               f"({st['in_win']} in the cache window: {st['solid']} solid, {st['air']} air, "
               f"{st['nocmp']} outside section 0; {st['out_win']} outside the window), "
               f"{st['match']} match the committed data, {st['mismatch']} do not. "
               f"Cache_Origin_Row during the calls: {sorted(st['origins'])}; layers {sorted(st['layers'])}. "
               f"Calls an origin-blind lookup would have answered with a DIFFERENT cell: {st['discrim']}")
    return st


def run_c1b3(build: Build, out: list, fly_frames: int) -> str:
    k = build
    pv = PlayerView(k)
    com = Committed(k)
    speed = k.src_const("games/sonic4/player/player_common.emp", "PLAYER_DEBUG_FLY_SPEED")
    rows = k.e("TILE_CACHE_ROWS")
    out.append(f"  inputs: fly {fly_frames} frames DOWN at PLAYER_DEBUG_FLY_SPEED {speed} px/frame "
               f"(player_common.emp), then B; TILE_CACHE_ROWS {rows}")

    async def test(m: Machine):
        await m.frames(BOOT_FRAMES)
        s0 = await pv.read(m)
        if not s0["fly"] or s0["y"] == 0:
            raise CouldNotRun(f"boot state is not the debug-fly player: {fmt_state(s0)}")
        await m.buttons("down")
        await m.frames(fly_frames)
        await m.buttons()
        await m.frames(2)
        s1 = await pv.read(m)
        await m.buttons("b")
        drop = None
        for _ in range(6):
            await m.frames(1)
            s = await pv.read(m)
            if not s["fly"]:
                drop = s
                break
        await m.buttons()
        if drop is None:
            raise CouldNotRun("B did not hand the player to physics within 6 frames")
        first, rest = await settle(m, pv, k)
        calls = await capture_lookups(m, k)
        return s0, s1, drop, first, rest, calls

    async def control(m: Machine, at: tuple):
        await m.frames(BOOT_FRAMES)
        await m.buttons("b")
        await m.frames(2)
        await m.buttons()
        pre_first, pre_rest = await settle(m, pv, k)
        # the WARP MAILBOX, whose consumer re-runs Tile_Cache_Init: the one supported path that
        # re-seeds Cache_Origin_Row to 0 at a chosen camera (flight cannot: see the note).
        await m.wr(k.s("Warp_Req_X"), at[0].to_bytes(2, "big") + at[1].to_bytes(2, "big"))
        await m.wr(k.s("Warp_Req_Flag"), b"\x01")
        # 120 frames, as tools/warp_mailbox_gate.py allows: the consumer's synchronous
        # Tile_Cache_Init refill spans several VBlanks, so a 10-frame wait read "no ack".
        for _ in range(120):
            await m.frames(1)
            if await m.u8(k.s("Warp_Req_Flag")) == 0:
                break
        else:
            raise CouldNotRun("the warp mailbox never acknowledged within 120 frames")
        back = (await m.u16(k.s("Warp_Req_X")), await m.u16(k.s("Warp_Req_Y")))
        drop = await pv.read(m)
        first, rest = await settle(m, pv, k)
        calls = await capture_lookups(m, k)
        return pre_rest, back, drop, first, rest, calls

    s0, s1, t_drop, t_first, t_rest, t_calls = boot_session(build, test)
    out.append(f"  TEST     boot+{BOOT_FRAMES}: {fmt_state(s0)}")
    out.append(f"           after the fly: {fmt_state(s1)}")
    out.append(f"           first physics frame: {fmt_state(t_drop)}")
    out.append(f"           first grounded frame: {fmt_state(t_first)}")
    out.append(f"           at rest: {fmt_state(t_rest)}")
    at = (t_drop["x"], t_drop["y"])
    c_pre, c_back, c_drop, c_first, c_rest, c_calls = boot_session(build, lambda m: control(m, at))
    out.append(f"  CONTROL  boot drop at rest (setup only): {fmt_state(c_pre)}")
    out.append(f"           warp to {at}, mailbox read back {c_back}; the frame the warp acked: "
               f"{fmt_state(c_drop)}")
    out.append(f"           first grounded frame: {fmt_state(c_first)}")
    out.append(f"           at rest: {fmt_state(c_rest)}")

    fails = []
    # ---- the expected standing height, from the committed data only
    exp = {}
    for tag, rest, drop in (("TEST", t_rest, t_drop), ("CONTROL", c_rest, c_drop)):
        xr, yr = rest["w"] >> 1, rest["h"] >> 1
        x, lay = rest["x"], rest["layer"]
        y0 = drop["y"] + yr                       # the feet at the drop
        cols = range(x - xr, x + xr + 1)
        surf = {cx: com.surface(lay, cx, y0) for cx in cols}
        if any(v is None for v in surf.values()):
            raise CouldNotRun(f"{tag}: no committed floor below ({x},{y0}) across the sensor span")
        s_a, s_b = surf[x - xr], surf[x + xr]
        flat = len(set(surf.values())) == 1
        exp[tag] = min(s_a, s_b) - yr
        out.append(f"  {tag} DERIVED  layer {lay} committed plane, sensors at x {x - xr} / {x + xr} "
                   f"(x_rad = width {rest['w']} >> 1): floor surfaces y {s_a} / {s_b}"
                   f"{' (flat across the span)' if flat else ' (NOT flat across the span)'}; "
                   f"rest y = {min(s_a, s_b)} - y_rad {yr} (height {rest['h']} >> 1) = {exp[tag]}")
    # ---- measured
    for tag, rest in (("TEST", t_rest), ("CONTROL", c_rest)):
        if rest["y"] != exp[tag]:
            fails.append(f"{tag}: the player rests at y {rest['y']}, the committed floor puts him at {exp[tag]}")
    t_st = grade_lookups(t_calls, com, "TEST", out, fails)
    c_st = grade_lookups(c_calls, com, "CONTROL", out, fails)

    # ---- preconditions that make it the experiment it claims to be
    setup = []
    if t_rest["origin"] == 0 or t_rest["origin"] % 2 or t_first["origin"] == 0:
        setup.append(f"TEST origin at landing/rest is {t_first['origin']}/{t_rest['origin']}: not a "
                     f"non-zero even value, so nothing was exercised past the zero case")
    if c_first["origin"] != 0 or c_rest["origin"] != 0:
        setup.append(f"CONTROL origin at landing/rest is {c_first['origin']}/{c_rest['origin']}, not 0")
    if t_st["solid"] == 0 or c_st["solid"] == 0:
        setup.append("a run captured no in-window SOLID lookup, so no lookup of a real cell was graded")
    if t_st["discrim"] == 0:
        setup.append("no TEST lookup would have read a different cell with the origin dropped, so "
                     "matching the committed data could not have failed at this origin")
    if (t_drop["x"], t_drop["y"]) != (c_drop["x"], c_drop["y"]) and c_back != at:
        setup.append(f"the control did not start from the test's drop point {at} (read back {c_back})")
    out.append(f"  origins: TEST landing {t_first['origin']} rest {t_rest['origin']} | CONTROL landing "
               f"{c_first['origin']} rest {c_rest['origin']}; rest y TEST {t_rest['y']} CONTROL {c_rest['y']}")
    if setup and not fails:
        return verdict_block(out, "C1b-3", COULD_NOT_RUN, setup)
    return verdict_block(out, "C1b-3", NOT_WITNESSED if fails else WITNESSED, fails + setup)


# =========================================================================== C3b-2

_PHASED = None


def phased_names() -> set:
    """scene_spans' one derivation of the phased-section names (a SOURCE fact: the listing
    carries no marker for it). Cached: it walks every .emp in the tree."""
    global _PHASED
    if _PHASED is None:
        from scene_spans import vma_phased_symbol_names
        _PHASED = set(vma_phased_symbol_names())
    return _PHASED


def latch_windows(build: Build, max_patch: int) -> dict:
    """The two per-channel store loops of Effects_LatchWorldLines, decoded out of the ROM."""
    try:
        import capstone
    except ImportError:
        raise CouldNotRun("capstone is not importable; the loop bounds are decoded with it")
    k = build
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    start = k.s("Effects_LatchWorldLines")
    # The extent comes from the tree's ONE head-to-next-head implementation,
    # scene_spans.lst_proc_sizes, which drops phased names before the address sort (see
    # tools/test_routine_extent_phased.py: a sixth opinion on "where a routine ends" is the
    # class that test exists to stop). Its head rows are unmangled top-level labels only.
    from scene_spans import lst_proc_sizes
    size = lst_proc_sizes(str(k.lst_path)).get("Effects_LatchWorldLines")
    if not size:
        raise CouldNotRun("scene_spans.lst_proc_sizes has no size for Effects_LatchWorldLines")
    end = start + size
    insns = list(md.disasm(k.rom[start:end], start))
    if not insns or insns[-1].address + insns[-1].size > end:
        raise CouldNotRun("could not decode Effects_LatchWorldLines")
    moveq = [i for i in insns if i.mnemonic == "moveq" and i.op_str.replace(" ", "") == f"#${max_patch - 1:x},d0"]
    if not moveq:
        raise CouldNotRun(f"no `moveq #{max_patch - 1}, d0` (RASTER_MAX_PATCH-1) in the latch")
    res = {"proc": (start, end)}
    for name, store_ops in (("plain", "d2,(a1)+"), ("mch", "d2,$6(a0)")):
        head = k.s(f"$engine.effects.raster$Effects_LatchWorldLines${'plain_ch' if name == 'plain' else 'mch'}")
        dbra = [i for i in insns if i.mnemonic in ("dbra", "dbf") and i.op_str.endswith(f"${head:x}")]
        store = [i for i in insns if i.mnemonic == "move.w" and i.op_str.replace(" ", "") == store_ops
                 and head <= i.address]
        if len(dbra) != 1 or not store:
            raise CouldNotRun(f"the {name} loop: {len(dbra)} dbra to ${head:X}, {len(store)} stores")
        res[name] = dict(head=head, store=store[0].address, dbra=dbra[0].address)
    return res


def classify(pc: int, d0w: int, w: dict, max_patch: int, lo_ch: int = 0):
    """'plain'/'mch' when a VBlank taken at `pc` sees channel `lo_ch` stored and channel
    `lo_ch + 1` not. The loop counts d0 DOWN from max_patch - 1, so channel c runs with
    d0 = max_patch - 1 - c (section 0's pair 0/1: d0 3 then 2; section 7's pair 2/3: 1 then 0)."""
    for name in ("plain", "mch"):
        L = w[name]
        if pc == L["dbra"] and d0w == max_patch - 1 - lo_ch:
            return name           # channel lo_ch's store retired, its dbra not yet
        if L["head"] <= pc <= L["store"] and d0w == max_patch - 2 - lo_ch:
            return name           # channel lo_ch + 1's iteration, before its store retires
    return None


def band_table(build: Build, tab: int, max_patch: int) -> dict:
    """Raster_BuildSchedule's table, read out of the ROM at `tab`: [count], then per record
    [line_src][lo_fl][hi_fl][rec_off][rec_len]. {channel: (lo_fl, hi_fl)} for the records whose
    line_src has the high (latched) bit set; the band words are in FIRE-LINE space."""
    n = build.rom_u16(tab)
    ents = {}
    for i in range(n):
        e = [build.rom_u16(tab + 2 + 10 * i + 2 * j) for j in range(5)]
        if e[0] & 0x8000:
            ents[e[0] & (max_patch - 1)] = (e[1] - (0x10000 if e[1] & 0x8000 else 0),
                                            e[2] - (0x10000 if e[2] & 0x8000 else 0))
    return ents


def record_state(screen_l: int, band) -> str:
    """Raster_BuildSchedule's rule for one latched record: fire line = screen - 1; past band_hi
    the record is dropped for the frame, below band_lo it is clamped up to band_lo."""
    if band is None:
        return "no record"
    fl = screen_l - 1
    if fl > band[1]:
        return "suppressed"
    return "live (clamped up)" if fl < band[0] else "live"


def run_c3b2(build: Build, out: list, budget: int) -> str:
    k = build
    max_patch = k.src_const("engine/effects/raster_dsl.emp", "RASTER_MAX_PATCH")
    w = latch_windows(k, max_patch)
    out.append(f"  Effects_LatchWorldLines ${w['proc'][0]:06X}..${w['proc'][1]:06X}; RASTER_MAX_PATCH "
               f"{max_patch} (raster_dsl.emp), so channel 0 runs with d0 = {max_patch - 1}")
    for n in ("plain", "mch"):
        L = w[n]
        out.append(f"  {n:5} loop: head ${L['head']:06X}, channel store ${L['store']:06X}, dbra "
                   f"${L['dbra']:06X}. Tear = stacked PC ${L['dbra']:06X} with d0.w {max_patch - 1}, or "
                   f"${L['head']:06X}..${L['store']:06X} with d0.w {max_patch - 2}")
    lag_entry = k.s("VInt_Lag")
    lag_ret = k.s("$engine.vblank$VBlank_Handler$done")
    # Phased (bank-local VMA) names are dropped: their listing value is not a ROM address, and
    # one (DacSampleTable, $85B1) sits inside Parallax_Fill_PerLine by numeric coincidence.
    code_syms = sorted((a, n) for n, a in k.sym.items()
                       if not n.startswith("$") and a < len(k.rom) and n not in phased_names())
    code_addrs = [a for a, _ in code_syms]
    sec = k.e("SECTION_SIZE")

    def nearest(pc):
        i = bisect.bisect_right(code_addrs, pc) - 1
        return code_syms[i][1] if i >= 0 else "?"

    async def body(m: Machine):
        await m.frames(BOOT_FRAMES)
        lag0 = await m.u32(k.s("Lag_Frame_Count"))
        st = dict(stops=0, hits=[], in_proc=0, hist={}, missed=0, frames0=await m.frame(),
                  tabs=set(), motion=set(), ch_status={}, bad_frame=0, legs=0)
        px_off, py_off = k.e("SST_x_pos"), k.e("SST_y_pos")
        p1 = k.s("Player_1")
        leg = ("down", "right")
        await m.buttons(*leg)
        st["legs"] = 1
        ceiling = st["frames0"] + budget * 40
        while st["stops"] < budget:
            if await m.frame() > ceiling:
                raise CouldNotRun(f"{st['stops']} lag frames in {ceiling - st['frames0']} frames: the "
                                  f"flight stopped producing lag frames")
            if not await m.run_to(lag_entry, 240):
                raise CouldNotRun(f"no VInt_Lag in 240 frames after {st['stops']} stops")
            r = await m.regs()
            if r["pc"] & 0xFFFFFF != lag_entry:
                raise CouldNotRun(f"run_to VInt_Lag stopped at ${r['pc'] & 0xFFFFFF:06X}")
            sp = r["sp"] & 0xFFFFFF
            frame = await m.rd(sp, 4 + 60 + 6)
            ret = int.from_bytes(frame[0:4], "big") & 0xFFFFFF
            if ret != lag_ret:
                st["bad_frame"] += 1
                raise CouldNotRun(f"VInt_Lag's return address is ${ret:06X}, not VBlank_Handler.done "
                                  f"${lag_ret:06X}: the stacked-frame layout this reads is wrong")
            d0w = int.from_bytes(frame[4:8], "big") & 0xFFFF          # movem.l d0-a6 slot 0
            pc = int.from_bytes(frame[4 + 60 + 2:4 + 60 + 6], "big") & 0xFFFFFF  # [SR][PC]
            lag_now = await m.u32(k.s("Lag_Frame_Count"))
            if lag_now != lag0 + st["stops"]:
                st["missed"] += 1
            st["stops"] += 1
            name = nearest(pc)
            st["hist"][name] = st["hist"].get(name, 0) + 1
            if w["proc"][0] <= pc < w["proc"][1]:
                st["in_proc"] += 1
            tab = await m.u32(k.s("Raster_Patch_Tab")) & 0xFFFFFF
            st["tabs"].add(tab)
            st["motion"].add(await m.u16(k.s("Effects_Motion_Any")))
            scr = [int.from_bytes(x, "big", signed=True) for x in
                   (lambda b: [b[0:2], b[2:4]])(await m.rd(k.s("Effects_Screen_L"), 4))]
            bands = band_table(k, tab, max_patch) if tab else {}
            key = tuple(record_state(scr[c], bands.get(c)) for c in (0, 1))
            st["ch_status"][key] = st["ch_status"].get(key, 0) + 1
            which = classify(pc, d0w, w, max_patch)
            if which:
                wy = [int.from_bytes(x, "big", signed=True) for x in
                      (lambda b: [b[0:2], b[2:4]])(await m.rd(k.s("Effects_World_Y"), 4))]
                camy = await m.s16(k.s("Camera_Y"))
                st["hits"].append(dict(pc=pc, d0=d0w, loop=which, screen=scr, world=wy, camy=camy,
                                       ch0=key[0], ch1=key[1],
                                       ch1_new=wy[1] - camy, stop=st["stops"]))
            # steer: a diagonal zig-zag that keeps the camera in section 0
            px = await m.s16(p1 + px_off)
            py = await m.s16(p1 + py_off)
            if leg == ("down", "right") and (px > sec - 400 or py > sec - 400):
                leg = ("up", "left")
                await m.buttons(*leg)
                st["legs"] += 1
            elif leg == ("up", "left") and (px < 320 or py < 320):
                leg = ("down", "right")
                await m.buttons(*leg)
                st["legs"] += 1
            await m.step(1)
        st["lag_delta"] = await m.u32(k.s("Lag_Frame_Count")) - lag0
        st["frames"] = await m.frame() - st["frames0"]

        # CONTEXT, not the verdict: WHERE in its tick the latch runs, on the same flight. A tick
        # starts when a VBlank with VBlank_Ready = 1 releases VSync_Wait; a lag VBlank can only
        # tear the latch if it lands between that start and the latch's stores. So: stop at
        # such a VBlank, then at the latch, and measure the gap, and whether Lag_Frame_Count
        # rose inside it (i.e. the pre-latch work of that tick overran a frame).
        vbh, ready = k.s("VBlank_Handler"), k.s("VBlank_Ready")
        gaps, lag_between = [], 0
        while len(gaps) < LATCH_TIMING_SAMPLES:
            rv = await m.run_to_reply(vbh, 3)
            if not rv.get("reached"):
                raise CouldNotRun("no VBlank_Handler entry in 3 frames during the latch timing")
            if await m.u8(ready) == 0:
                await m.step(1)
                continue
            mv = await m.mclk(rv)
            lag_a = await m.u32(k.s("Lag_Frame_Count"))
            await m.step(1)
            rl = await m.run_to_reply(w["proc"][0], 8)
            if not rl.get("reached"):
                raise CouldNotRun("Effects_LatchWorldLines not reached within 8 frames of a tick start")
            gaps.append(await m.mclk(rl) - mv)
            if await m.u32(k.s("Lag_Frame_Count")) != lag_a:
                lag_between += 1
            px = await m.s16(p1 + px_off)
            py = await m.s16(p1 + py_off)
            if leg == ("down", "right") and (px > sec - 400 or py > sec - 400):
                leg = ("up", "left")
                await m.buttons(*leg)
            elif leg == ("up", "left") and (px < 320 or py < 320):
                leg = ("down", "right")
                await m.buttons(*leg)
            await m.step(1)
        st["gaps"], st["lag_between"] = gaps, lag_between
        await m.buttons()
        return st

    t0 = time.monotonic()
    started = utc()
    st = boot_session(build, body)
    secs = time.monotonic() - t0
    out.append(f"  ran {started} .. {utc()} ({secs:.1f} s wall): {st['stops']} VInt_Lag stops over "
               f"{st['frames']} frames, {st['legs']} diagonal legs; Lag_Frame_Count rose by "
               f"{st['lag_delta']} (the last stop's own increment lands after it), stops that found a "
               f"count out of step: {st['missed']}")
    out.append(f"  Raster_Patch_Tab at the stops: {sorted('$%06X' % t for t in st['tabs'])}; "
               f"Effects_Motion_Any at the stops: {sorted(st['motion'])} "
               f"({'the .plain loop runs' if st['motion'] == {0} else 'the .mch loop runs on some'})")
    out.append(f"  channel 0 / channel 1 record state at the stops (Raster_BuildSchedule's rule, "
               f"table read from ROM at Raster_Patch_Tab): " +
               "; ".join(f"{a} / {b}: {n}" for (a, b), n in sorted(st["ch_status"].items(), key=lambda t: -t[1])))
    top = sorted(st["hist"].items(), key=lambda t: -t[1])[:8]
    out.append(f"  interrupted routine (nearest preceding symbol), top 8: " +
               ", ".join(f"{n} {c}" for n, c in top))
    out.append(f"  stops inside Effects_LatchWorldLines at all: {st['in_proc']}")
    line_mclk = MCLK_PER_FRAME / LINES_PER_FRAME
    g = sorted(x / line_mclk for x in st["gaps"])
    if g:
        out.append(f"  CONTEXT latch timing, {len(g)} ticks of the same flight: Effects_LatchWorldLines "
                   f"entered {g[0]:.1f} .. {g[-1]:.1f} scanlines (median {g[len(g) // 2]:.1f}) after "
                   f"the VBlank that started its tick (a frame is {LINES_PER_FRAME} lines); ticks with a "
                   f"lag VBlank between tick start and the latch: {st['lag_between']}")
    out.append(f"  TEAR HITS (channel 0 stored, channel 1 not): {len(st['hits'])}")
    for h in st["hits"][:10]:
        out.append(f"    stop {h['stop']}: PC ${h['pc']:06X} d0.w {h['d0']} ({h['loop']}); Screen_L "
                   f"{h['screen']} world {h['world']} Camera_Y {h['camy']}; channel 1's line this "
                   f"frame would be {h['ch1_new']}; channel 0 {h['ch0']}, channel 1 {h['ch1']}")
    fails = []
    if st["stops"] < budget:
        return verdict_block(out, "C3b-2", COULD_NOT_RUN, [f"only {st['stops']} of {budget} lag frames"])
    if st["missed"]:
        return verdict_block(out, "C3b-2", COULD_NOT_RUN,
                             [f"{st['missed']} stop(s) found Lag_Frame_Count out of step, so a lag "
                              f"frame went unobserved and the count is not the population"])
    if st["hits"]:
        return verdict_block(out, "C3b-2", WITNESSED, [])
    n = st["stops"]
    bound = 1 - 0.05 ** (1 / n)
    out.append(f"  RATE BOUND: 0 hits in {n} lag frames. 95% upper bound on the per-lag-frame tear "
               f"probability: {bound:.5f} (about 1 in {int(1 / bound)}; rule of three 3/n = {3 / n:.5f}). "
               f"This is NOT a clean result: it bounds the rate, it does not show the window closed.")
    return verdict_block(out, "C3b-2", NOT_OBSERVED, fails)


# =========================================================================== C3b-2, section 7

OJZ_EFFECTS = "games/sonic4/data/effects/ojz_effects.emp"
OJZ_ACT1 = "games/sonic4/data/levels/ojz/act1/act_descriptor.emp"
S7_STEER_MARGIN = 8          # px inside the both-live camera band, half a tick of fly motion
S7_NO_LAG_FRAMES = 2400      # a flight this long with no VInt_Lag stopped producing them


def _strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def _top_split(s: str) -> list:
    """Split on the commas that are not inside () or []."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def section_preset(build: Build, sec: int) -> tuple:
    """(GRID_W, the EffectsPreset section `sec` binds), from OJZ act 1's act descriptor."""
    text = _strip_comments(build.source(OJZ_ACT1).decode("utf-8", "replace"))
    gw = re.search(r"^\s*const\s+GRID_W\s*=\s*(\d+)", text, re.M)
    i = text.find(f"ojz_sec(sec: {sec},")
    if not gw or i < 0:
        raise CouldNotRun(f"{OJZ_ACT1}: no GRID_W, or no `ojz_sec(sec: {sec}, ..)` row")
    j = text.find("ojz_sec(sec:", i + 1)
    m = re.search(r"\beffects:\s*(\w+)", text[i:j if j > 0 else len(text)])
    if not m:
        raise CouldNotRun(f"{OJZ_ACT1}: section {sec}'s row binds no `effects:`")
    return int(gw.group(1)), m.group(1)


def preset_fields(build: Build, preset: str) -> dict:
    """The named fields of one `pub data <preset>: EffectsPreset = preset(..)`, as source text."""
    text = _strip_comments(build.source(OJZ_EFFECTS).decode("utf-8", "replace"))
    i = text.find(f"pub data {preset}:")
    if i < 0:
        raise CouldNotRun(f"{OJZ_EFFECTS}: no `pub data {preset}:`")
    k = text.index("preset(", i) + len("preset")
    depth, p = 0, k
    for p in range(k, len(text)):
        if text[p] == "(":
            depth += 1
        elif text[p] == ")":
            depth -= 1
            if depth == 0:
                break
    fields = {}
    for part in _top_split(text[k + 1:p]):
        name, _, val = part.partition(":")
        fields[name.strip()] = val.strip()
    return fields


def run_c3b2s7(build: Build, out: list, budget: int, sec: int = 7) -> str:
    """C3b-2 where it CAN show: two live, moving patch records on adjacent channels.

    Section 0 cannot show the residue (its channel 0 is anchor-NONE and always suppressed, and
    it authors no motion, so the .plain loop runs). Everything section-specific here is derived
    from source, not typed in: which preset the section binds, its patched program, which
    channels carry a world anchor and which a sweep, and the camera-Y band in which BOTH records
    are live and unclamped (from the ROM's own band table and the runtime anchor bank). The
    flight bounces diagonally inside that band and inside the section, and every VInt_Lag is
    stopped and classified exactly as section 0's were, for the channel pair (lo, lo + 1)."""
    k = build
    max_patch = k.src_const("engine/effects/raster_dsl.emp", "RASTER_MAX_PATCH")
    buf_size = k.src_const("engine/effects/raster.emp", "RASTER_BUF_SIZE")
    w = latch_windows(k, max_patch)
    grid_w, preset = section_preset(k, sec)
    fields = preset_fields(k, preset)
    program = fields.get("patched")
    if not program:
        raise CouldNotRun(f"{preset} binds no `patched:` program, so nothing is latched there")
    world = _top_split(fields.get("patch_world_ys", "[]").strip()[1:-1])
    motion = _top_split(fields.get("patch_motion", "[]").strip()[1:-1])
    if len(world) != max_patch or len(motion) != max_patch:
        raise CouldNotRun(f"{preset}: patch_world_ys / patch_motion are not {max_patch} entries")
    anchored = [c for c, v in enumerate(world) if v != "PATCH_ANCHOR_NONE"]
    sweep = {}
    for c, v in enumerate(motion):
        if v == "ANCHOR_MOTION_NONE":
            continue
        mm = re.fullmatch(r"anchor_sweep\(\s*amp_shift:\s*(\d+)\s*,\s*period_shift:\s*(\d+)\s*\)", v)
        if not mm:
            raise CouldNotRun(f"{preset} channel {c}: motion {v!r} is not an anchor_sweep this tool models")
        sweep[c] = int(mm.group(1))
    pair = [c for c in anchored if c + 1 in anchored]
    if len(anchored) != 2 or not pair:
        raise CouldNotRun(f"{preset}: anchored channels {anchored}, not one adjacent pair")
    lo_ch, hi_ch = pair[0], pair[0] + 1
    if not sweep:
        raise CouldNotRun(f"{preset} authors no motion, so the .mch loop would not run here either")
    sine_amp = k.equ.get("SINE_AMPLITUDE") or k.src_const("engine/system/constants.emp", "SINE_AMPLITUDE")
    amp = {c: (sine_amp >> sweep[c]) if c in sweep else 0 for c in (lo_ch, hi_ch)}
    tab_want = k.s(program) + buf_size
    sec_size = k.e("SECTION_SIZE")
    sx0, sy0 = (sec % grid_w) * sec_size, (sec // grid_w) * sec_size
    scr_w = k.e("SCREEN_WIDTH")
    out.append(f"  derived from source: section {sec} is grid ({sec % grid_w},{sec // grid_w}) of GRID_W {grid_w}, "
               f"world x {sx0}..{sx0 + sec_size - 1} y {sy0}..{sy0 + sec_size - 1}; it binds {preset}, "
               f"patched: {program} (patch table expected at ${tab_want:06X} = {program} + RASTER_BUF_SIZE "
               f"{buf_size}); anchored channels {anchored}; sweep channels "
               f"{ {c: f'amp_shift {s}' for c, s in sweep.items()} } (SINE_AMPLITUDE {sine_amp} >> shift = "
               f"+/-{ {c: a for c, a in amp.items()} } px)")
    out.append(f"  channel pair {lo_ch}/{hi_ch}: RASTER_MAX_PATCH {max_patch}, so channel {lo_ch} runs with d0 = "
               f"{max_patch - 1 - lo_ch} and channel {hi_ch} with d0 = {max_patch - 1 - hi_ch}")
    for n in ("plain", "mch"):
        L = w[n]
        out.append(f"  {n:5} loop: head ${L['head']:06X}, store ${L['store']:06X}, dbra ${L['dbra']:06X}. Tear = "
                   f"stacked PC ${L['dbra']:06X} with d0.w {max_patch - 1 - lo_ch}, or ${L['head']:06X}.."
                   f"${L['store']:06X} with d0.w {max_patch - 1 - hi_ch}")
    lag_entry = k.s("VInt_Lag")
    lag_ret = k.s("$engine.vblank$VBlank_Handler$done")
    code_syms = sorted((a, n) for n, a in k.sym.items()
                       if not n.startswith("$") and a < len(k.rom) and n not in phased_names())
    code_addrs = [a for a, _ in code_syms]

    def nearest(pc):
        i = bisect.bisect_right(code_addrs, pc) - 1
        return code_syms[i][1] if i >= 0 else "?"

    bands = band_table(k, tab_want, max_patch)
    if lo_ch not in bands or hi_ch not in bands:
        raise CouldNotRun(f"the ROM's band table at ${tab_want:06X} has records for channels "
                          f"{sorted(bands)}, not {lo_ch} and {hi_ch}")
    cam_x, cam_y = k.s("Camera_X"), k.s("Camera_Y")

    async def words(m, addr):
        raw = await m.rd(addr, 2 * max_patch)
        return [int.from_bytes(raw[i:i + 2], "big", signed=True) for i in range(0, 2 * max_patch, 2)]

    async def body(m: Machine):
        pv = PlayerView(k)
        await m.frames(BOOT_FRAMES)
        s_boot = await pv.read(m)
        if not s_boot["fly"]:
            raise CouldNotRun(f"boot state is not the debug-fly player: {fmt_state(s_boot)}")
        # THE WARP MAILBOX (the c1b3 control's mechanism): its consumer re-seeds every streaming
        # latch and forces a section crossing, so the section's preset installs through the one
        # path a walked crossing takes. It leaves debug fly on (measured below, not assumed).
        wx, wy = sx0 + sec_size // 2, sy0 + 256
        await m.wr(k.s("Warp_Req_X"), wx.to_bytes(2, "big") + wy.to_bytes(2, "big"))
        await m.wr(k.s("Warp_Req_Flag"), b"\x01")
        for _ in range(120):
            await m.frames(1)
            if await m.u8(k.s("Warp_Req_Flag")) == 0:
                break
        else:
            raise CouldNotRun("the warp mailbox never acknowledged within 120 frames")
        await m.frames(4)
        s_warp = await pv.read(m)
        tab0 = await m.u32(k.s("Raster_Patch_Tab")) & 0xFFFFFF
        many0 = await m.u16(k.s("Effects_Motion_Any"))
        wy_rt = await words(m, k.s("Effects_World_Y"))
        out.append(f"  after the warp to ({wx},{wy}): {fmt_state(s_warp)}; Raster_Patch_Tab ${tab0:06X}, "
                   f"Effects_Motion_Any ${many0:04X}, Effects_World_Y {wy_rt}")
        if not s_warp["fly"]:
            raise CouldNotRun("the warp left debug fly, so the flight below cannot be steered")
        if tab0 != tab_want:
            raise CouldNotRun(f"after the warp Raster_Patch_Tab is ${tab0:06X}, not {program}'s ${tab_want:06X}")
        if many0 == 0:
            raise CouldNotRun("Effects_Motion_Any is 0 in the section, so the .mch loop does not run")
        # The camera band in which BOTH records are live and unclamped, for every sweep phase:
        # lo_fl <= W + s - Cy - 1 <= hi_fl for all |s| <= amp.
        span = {}
        for c in (lo_ch, hi_ch):
            lo_fl, hi_fl = bands[c]
            span[c] = (wy_rt[c] + amp[c] - 1 - hi_fl, wy_rt[c] - amp[c] - 1 - lo_fl)
        box = (max(span[lo_ch][0], span[hi_ch][0]), min(span[lo_ch][1], span[hi_ch][1]))
        if box[1] - box[0] < 2 * S7_STEER_MARGIN + 16:
            raise CouldNotRun(f"the both-live camera band {box} is too narrow to steer inside")
        y_lo, y_hi = box[0] + S7_STEER_MARGIN, box[1] - S7_STEER_MARGIN
        x_lo = sx0 - scr_w // 2 + 64                    # camera centre stays inside the section
        x_hi = sx0 + sec_size - scr_w // 2 - 96
        out.append(f"  band table (ROM, fire-line space): channel {lo_ch} {bands[lo_ch]}, channel {hi_ch} "
                   f"{bands[hi_ch]}. Camera_Y ranges with the record live and unclamped at every sweep "
                   f"phase: channel {lo_ch} {span[lo_ch]}, channel {hi_ch} {span[hi_ch]}; both: {box}. "
                   f"Steering: Camera_Y bounces in {y_lo}..{y_hi}, Camera_X in {x_lo}..{x_hi}, diagonally")
        st = dict(stops=0, hits=[], in_proc=0, hist={}, missed=0, frames0=await m.frame(), tabs={},
                  motion=set(), ch_status={}, legs=0, off_section=0, camy_min=1 << 30, camy_max=-(1 << 30))
        steer_st = {"h": None, "v": None}

        async def steer():
            cx, cy = await m.s16(cam_x), await m.s16(cam_y)
            h = steer_st["h"] or "right"
            v = steer_st["v"] or ("down" if cy < y_lo else "up")
            if h == "right" and cx >= x_hi:
                h = "left"
            elif h == "left" and cx <= x_lo:
                h = "right"
            if v == "down" and cy >= y_hi:
                v = "up"
            elif v == "up" and cy <= y_lo:
                v = "down"
            if (h, v) != (steer_st["h"], steer_st["v"]):
                await m.buttons(h, v)
                steer_st.update(h=h, v=v)
                st["legs"] += 1

        # settle into the band before counting anything
        for _ in range(240):
            await steer()
            await m.frames(1)
            if y_lo <= await m.s16(cam_y) <= y_hi:
                break
        else:
            raise CouldNotRun("the camera never reached the both-live band within 240 frames")
        lag0 = await m.u32(k.s("Lag_Frame_Count"))
        st["frames0"] = await m.frame()
        ceiling = st["frames0"] + budget * 60
        last = st["frames0"]
        while st["stops"] < budget:
            fr = await m.frame()
            if fr > ceiling or fr - last > S7_NO_LAG_FRAMES:
                raise CouldNotRun(f"{st['stops']} lag frames by frame {fr}: the flight stopped "
                                  f"producing lag frames")
            r = await m.run_to_reply(lag_entry, 1)
            if r.get("reached"):
                regs = await m.regs()
                if regs["pc"] & 0xFFFFFF != lag_entry:
                    raise CouldNotRun(f"run_to VInt_Lag stopped at ${regs['pc'] & 0xFFFFFF:06X}")
                sp = regs["sp"] & 0xFFFFFF
                frame = await m.rd(sp, 4 + 60 + 6)
                ret = int.from_bytes(frame[0:4], "big") & 0xFFFFFF
                if ret != lag_ret:
                    raise CouldNotRun(f"VInt_Lag's return address is ${ret:06X}, not VBlank_Handler.done "
                                      f"${lag_ret:06X}: the stacked-frame layout this reads is wrong")
                d0w = int.from_bytes(frame[4:8], "big") & 0xFFFF
                pc = int.from_bytes(frame[4 + 60 + 2:4 + 60 + 6], "big") & 0xFFFFFF
                if await m.u32(k.s("Lag_Frame_Count")) != lag0 + st["stops"]:
                    st["missed"] += 1
                st["stops"] += 1
                name = nearest(pc)
                st["hist"][name] = st["hist"].get(name, 0) + 1
                if w["proc"][0] <= pc < w["proc"][1]:
                    st["in_proc"] += 1
                tab = await m.u32(k.s("Raster_Patch_Tab")) & 0xFFFFFF
                st["tabs"][tab] = st["tabs"].get(tab, 0) + 1
                if tab != tab_want:
                    st["off_section"] += 1
                st["motion"].add(await m.u16(k.s("Effects_Motion_Any")))
                scr = await words(m, k.s("Effects_Screen_L"))
                tb = band_table(k, tab, max_patch) if tab else {}
                key = tuple(record_state(scr[c], tb.get(c)) for c in (lo_ch, hi_ch))
                st["ch_status"][key] = st["ch_status"].get(key, 0) + 1
                cy = await m.s16(cam_y)
                st["camy_min"], st["camy_max"] = min(st["camy_min"], cy), max(st["camy_max"], cy)
                which = classify(pc, d0w, w, max_patch, lo_ch)
                if which:
                    wyv = await words(m, k.s("Effects_World_Y"))
                    st["hits"].append(dict(pc=pc, d0=d0w, loop=which, screen=scr, world=wyv, camy=cy,
                                           states=key, hi_bank=scr[hi_ch],
                                           hi_new=(wyv[hi_ch] - cy) if hi_ch not in sweep else None,
                                           stop=st["stops"]))
                last = await m.frame()
                await m.step(1)
            await steer()
        st["lag_delta"] = await m.u32(k.s("Lag_Frame_Count")) - lag0
        st["frames"] = await m.frame() - st["frames0"]

        # CONTEXT: where in its tick the latch runs, IN THIS SECTION, on the same flight (the
        # section-0 method: a tick starts at a VBlank with VBlank_Ready = 1).
        vbh, ready = k.s("VBlank_Handler"), k.s("VBlank_Ready")
        gaps, lag_between = [], 0
        while len(gaps) < LATCH_TIMING_SAMPLES:
            rv = await m.run_to_reply(vbh, 3)
            if not rv.get("reached"):
                raise CouldNotRun("no VBlank_Handler entry in 3 frames during the latch timing")
            if await m.u8(ready) == 0:
                await m.step(1)
                continue
            mv = await m.mclk(rv)
            lag_a = await m.u32(k.s("Lag_Frame_Count"))
            await m.step(1)
            rl = await m.run_to_reply(w["proc"][0], 8)
            if not rl.get("reached"):
                raise CouldNotRun("Effects_LatchWorldLines not reached within 8 frames of a tick start")
            gaps.append(await m.mclk(rl) - mv)
            if await m.u32(k.s("Lag_Frame_Count")) != lag_a:
                lag_between += 1
            if await m.u32(k.s("Raster_Patch_Tab")) & 0xFFFFFF != tab_want:
                st["off_section"] += 1
            await steer()
            await m.step(1)
        st["gaps"], st["lag_between"] = gaps, lag_between
        await m.buttons()
        return st

    t0 = time.monotonic()
    started = utc()
    st = boot_session(build, body)
    secs = time.monotonic() - t0
    out.append(f"  ran {started} .. {utc()} ({secs:.1f} s wall): {st['stops']} VInt_Lag stops over "
               f"{st['frames']} frames, {st['legs']} steering changes; Lag_Frame_Count rose by "
               f"{st['lag_delta']} (the last stop's own increment lands after it), stops that found a "
               f"count out of step: {st['missed']}")
    out.append(f"  Raster_Patch_Tab at the stops: " + ", ".join(f"${t:06X} x{n}" for t, n in sorted(st["tabs"].items()))
               + f"; stops or timing samples outside {program}'s install: {st['off_section']}; "
               f"Effects_Motion_Any at the stops: {sorted('$%04X' % v for v in st['motion'])} "
               f"({'the .mch loop runs' if 0 not in st['motion'] else 'the .plain loop ran on some'}); "
               f"Camera_Y at the stops {st['camy_min']}..{st['camy_max']}")
    out.append(f"  channel {lo_ch} / channel {hi_ch} record state at the stops: " +
               "; ".join(f"{a} / {b}: {n}" for (a, b), n in sorted(st["ch_status"].items(), key=lambda t: -t[1])))
    top = sorted(st["hist"].items(), key=lambda t: -t[1])[:8]
    out.append(f"  interrupted routine (nearest preceding symbol), top 8: " + ", ".join(f"{n} {c}" for n, c in top))
    out.append(f"  stops inside Effects_LatchWorldLines at all: {st['in_proc']}")
    line_mclk = MCLK_PER_FRAME / LINES_PER_FRAME
    g = sorted(x / line_mclk for x in st["gaps"])
    if g:
        out.append(f"  CONTEXT latch timing in section {sec}, {len(g)} ticks of the same flight: "
                   f"Effects_LatchWorldLines entered {g[0]:.1f} .. {g[-1]:.1f} scanlines (median "
                   f"{g[len(g) // 2]:.1f}) after the VBlank that started its tick (a frame is "
                   f"{LINES_PER_FRAME} lines); ticks with a lag VBlank between tick start and the latch: "
                   f"{st['lag_between']}")
    out.append(f"  TEAR HITS (channel {lo_ch} stored, channel {hi_ch} not): {len(st['hits'])}")
    for h in st["hits"][:10]:
        out.append(f"    stop {h['stop']}: PC ${h['pc']:06X} d0.w {h['d0']} ({h['loop']}); Screen_L {h['screen']} "
                   f"world {h['world']} Camera_Y {h['camy']}; channel {hi_ch} holds {h['hi_bank']}, this "
                   f"frame's line would be {h['hi_new']}; states {h['states']}")
    if st["stops"] < budget:
        return verdict_block(out, "C3b-2 s7", COULD_NOT_RUN, [f"only {st['stops']} of {budget} lag frames"])
    if st["missed"]:
        return verdict_block(out, "C3b-2 s7", COULD_NOT_RUN,
                             [f"{st['missed']} stop(s) found Lag_Frame_Count out of step"])
    if st["off_section"]:
        return verdict_block(out, "C3b-2 s7", COULD_NOT_RUN,
                             [f"{st['off_section']} stop(s) or samples were not in {program}'s install"])
    if st["hits"]:
        return verdict_block(out, "C3b-2 s7", WITNESSED, [])
    n = st["stops"]
    bound = 1 - 0.05 ** (1 / n)
    out.append(f"  RATE BOUND: 0 hits in {n} lag frames in section {sec}. 95% upper bound on the per-lag-frame "
               f"tear probability: {bound:.5f} (about 1 in {int(1 / bound)}; rule of three 3/n = {3 / n:.5f}). "
               f"NOT a clean result: it bounds the rate, it does not show the window closed.")
    return verdict_block(out, "C3b-2 s7", NOT_OBSERVED, [])


# =========================================================================== driver

def verdict_block(out: list, name: str, verdict: str, reasons: list) -> str:
    out.append(f"  VERDICT {name}: {verdict}")
    for r in reasons:
        out.append(f"    - {r}")
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("witness", choices=("efx4b", "c1b3", "c3b2", "c3b2s7", "all"))
    ap.add_argument("--rom", default=str(ROOT / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(ROOT / "s4.debug.lst"))
    ap.add_argument("--expect-crc", help="refuse (COULD NOT RUN) unless the ROM's crc32 is this")
    ap.add_argument("--lag-budget", type=int, default=3000)
    # 17, not a guess: the drop point must be one the WARP can also reach with its camera in
    # the rest camera's cache top, or the control's origin slides off 0 as the camera settles.
    # The warp centres the camera at y - CAM_SCREEN_HALF_H (112); the grounded rest camera is
    # 429 for the floor at 573+19, i.e. Cache_Top_Row ((429 >> 3) - 16) & ~1 = 36; top 36 needs
    # a camera in 416..431, so a drop y in 528..543. From the boot marker y 256 at 16 px/frame
    # only 256 + 16*17 = 528 lands there. The run re-measures every one of these numbers.
    ap.add_argument("--c1b3-fly-frames", type=int, default=17,
                    help="frames of downward debug-fly before the B drop (see the note for why 17)")
    a = ap.parse_args()

    build = Build(a.rom, a.lst)
    print(f"lens_residue_raster_witness  {utc()}")
    print(f"ROM {build.rom_path}  {len(build.rom)} B  crc32 {build.crc:08x}")
    print(f"LST {build.lst_path}  (DIGEST-ROM names crc "
          f"{next((l.split()[1][4:] for l in build.lst_path.read_text(errors='replace').splitlines() if l.startswith('DIGEST-ROM')), '?')})")
    print(f"source tree {ROOT}")
    if a.expect_crc and f"{build.crc:08x}" != a.expect_crc.lower():
        print(f"VERDICT all: {COULD_NOT_RUN} (ROM crc32 {build.crc:08x}, expected {a.expect_crc})")
        return 2

    todo = ("efx4b", "c1b3", "c3b2") if a.witness == "all" else (a.witness,)
    verdicts = {}
    for w in todo:
        out = []
        t0 = time.monotonic()
        started = utc()
        print(f"\n== {w}  started {started}")
        try:
            if w == "efx4b":
                v = run_efx4b(build, out)
            elif w == "c1b3":
                v = run_c1b3(build, out, a.c1b3_fly_frames)
            elif w == "c3b2s7":
                v = run_c3b2s7(build, out, a.lag_budget)
            else:
                v = run_c3b2(build, out, a.lag_budget)
        except CouldNotRun as e:
            v = verdict_block(out, w, COULD_NOT_RUN, [str(e)])
        print("\n".join(out))
        print(f"== {w}  finished {utc()} ({time.monotonic() - t0:.1f} s wall)")
        verdicts[w] = v
    print("\nsources checked:")
    for s in build.checked_sources:
        print(f"  {s}")
    print("\nSUMMARY  " + "  ".join(f"{w}={v}" for w, v in verdicts.items()))
    vals = list(verdicts.values())
    if NOT_WITNESSED in vals:
        return 1
    if COULD_NOT_RUN in vals:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
