#!/usr/bin/env python3
"""blank_priority_probe — does a blank plane-A cell's PRIORITY bit change what S/H shows? (sweep F4)

THE QUESTION. `engine/level/page_cache.emp`, `.pw_new_blank`, writes `$0000` for every
nametable word whose tile index is 0, so the attribute bits the baker wrote on a blank word
(priority, palette, flips) never reach VRAM. `secN_strips_a.bin` keeps them. Gap-lens sweep
F4 (2026-09-12) claimed that under Shadow/Highlight a blank cell's PRIORITY bit still decides
whether the pixels beneath it are shadowed. It flagged that claim as a reading of the hardware,
not a measurement. This probe measures it on the Rust core (oracle-aether), spawned through
tools/aether_instance.py.

⚠ THIS IS A PROBE, NOT A GATE. Nothing runs it; it is not wired into build.sh, pytest or
tools/effects_gates.py and must not be counted as standing coverage.

WHAT IT DOES, in order:
  1. OFFLINE. Re-derives the blank-priority population from sec{N}_strips_a.bin. The masks come
     from engine/system/constants.emp (NT_TILE_MASK) and the strip layout from ojz_strip_gen.py.
     Priority is bit 15, the top bit of NT_ATTR_MASK.
  2. S/H EXTENT, MEASURED. For every section, warps the player to the section centre (warp
     mailbox), confirms the section the engine installed (Parallax_Prev_Sec_X/Y), then walks
     one frame with `run_to_scanline` 0..223 and reads VDP reg $0C at each line. The lines with
     bit 3 set are that section's S/H extent at that camera.
  3. PREMISE (section 1). Picks a blank plane-A cell ($0000 in VRAM) whose 64 pixels are all
     inside the S/H band. Plane B beneath it must be low-priority and opaque, and no sprite may
     win any of its dots. Captures two frames from one checkpoint: as shipped, and with only
     the priority bit set on that VRAM word. Diffs the raster rows.
  4. CONTROLS. (a) The same toggle on a blank cell ABOVE the S/H line in the same frame.
     (b) Determinism: the unmodified capture taken twice from the same checkpoint must match
     byte for byte, or nothing here is a verdict. (c) After each poke, pixel_attribution must
     report plane A priority=true at the cell, proving the toggle landed on the dot we diff.
  5. CONSEQUENCE. Counts how many of the re-derived words could be displayed inside a MEASURED
     S/H band while that band's section is installed (camera-centre rule of
     Parallax_CheckBoundary, camera bounds 0..Camera_X_Max / 0..Camera_Y_Max read from RAM).
     Then, in place, writes the AUTHORED word back into VRAM for every re-derived word on
     screen in sections 1, 0 and 7, one at a time and all together, and diffs.
     Before any poke, a 7x7 neighbourhood check confirms the world-cell -> VRAM-address mapping:
     blank cells agree and non-blank cells' attribute bits match strips_a.

INSTRUMENT FACTS it relies on (read from oracle's source, 2026-09-12):
  * `emulator/write_vram` is `Vdp::poke_vram`, a direct store into the VRAM array (plus the SAT
    cache when the address is inside the SAT). It does NOT go through the VDP data port: no
    FIFO, no auto-increment, no command latch. The renderer reads VRAM directly each line.
  * oracle-core's `sh_state` rule: the default S/H state is Shadow iff BOTH the plane-A-slot
    and plane-B priority bits are 0, and "transparent planes still contribute their tile's
    priority". So the instrument IMPLEMENTS F4's premise. This probe measures whether the
    as-built engine's pixels change under that model. It cannot testify for real hardware.

RECORDED RUN, 2026-09-12 14:28:15-14:28:24 UTC (8.6 s, load avg 13.85), ROM the landing
tree's s4.debug.bin, crc32 9ce1c2ff (tree 9fe9ee91), exit 0.
Full notes: docs/superpowers/notes/2026-09-12-blank-priority-measurement.md.
  population      116 blank-priority words, 20/19/10/15/10/11/14/7/10 over sections 0-8
  S/H measured    ONLY section 1, lines 121..223 (reg $0C $89). Sections 0, 2-8: never on,
                  including section 7's water band and section 0 at three cameras.
  premise (sec 1) blank cell VRAM $C394, screen (8..15, 128..135): $0000 -> $8000 changes
                  25 px, all 25 exact shadow->normal; the other 39 are black (shadowed
                  black is black). Same cell -> $7800 (palette + flips, no priority): 0 px.
  control         blank cell $C118 above the line (24..31, 88..95): $0000 -> $8000, 0 px
  determinism     two unmodified captures from one checkpoint: 0 px differ, every scene
  consequence     19 of 116 (all of section 1's) can be shown inside the measured band;
                  in place at camera (2120,440), six words at world y 576/592 restored to
                  their authored $C000: 14/11/14/11/14/11 px, 75 together, all shadow->normal.
                  Sections 0 and 7 in place: 0 px (S/H is off there).

Exit: 0 = measured (whatever the verdict), 2 = COULD NOT RUN (named on stderr).

Usage:
    python3 tools/blank_priority_probe.py --rom <s4.debug.bin> --lst <s4.debug.lst> [--json out.json]
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import datetime
import json
import os
import re
import struct
import sys
import time
import zlib
from pathlib import Path

AEON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AEON / "tools"))
from aether_instance import AetherInstance, unprefix  # noqa: E402  (also puts the client on sys.path)
from aether import BusClient                             # noqa: E402
from raster_cost_probe import parse_lst                  # noqa: E402

GEN = AEON / "games" / "sonic4" / "data" / "generated" / "ojz" / "act1"
EXPECT_CRC = 0x9CE1C2FF
SETTLE = 180          # boot frames before the first warp
POST_WARP = 90        # settle after a warp ack (page cache + streaming quiesce)
FRAMES_PER_CAPTURE = 2  # capture the SECOND frame after a poke: fully rendered after it
ACTIVE_LINES = 224
WIDTH = 320


class CouldNotRun(Exception):
    pass


# --------------------------------------------------------------------------- derived constants

def _emp_const(rel: str, name: str) -> int:
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*pub\s+const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)", txt, re.M)
    if not m:
        raise CouldNotRun(f"cannot find `pub const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def _py_const(rel: str, name: str) -> int:
    m = re.search(rf"^{re.escape(name)}\s*=\s*(\d+)", (AEON / rel).read_text(), re.M)
    if not m:
        raise CouldNotRun(f"cannot find `{name} = <int>` in {rel}")
    return int(m.group(1))


def derive_constants() -> dict:
    k = {
        "NT_TILE_MASK": _emp_const("engine/system/constants.emp", "NT_TILE_MASK"),
        "NT_ATTR_MASK": _emp_const("engine/system/constants.emp", "NT_ATTR_MASK"),
        "SECTION_SIZE_SHIFT": _emp_const("engine/system/constants.emp", "SECTION_SIZE_SHIFT"),
        "STRIP_TILE_HEIGHT": _py_const("tools/ojz_strip_gen.py", "STRIP_TILE_HEIGHT"),
        "STRIP_COLLISION_PAD": _py_const("tools/ojz_strip_gen.py", "STRIP_COLLISION_PAD"),
    }
    if k["NT_TILE_MASK"] | k["NT_ATTR_MASK"] != 0xFFFF or k["NT_TILE_MASK"] & k["NT_ATTR_MASK"]:
        raise CouldNotRun(f"NT_TILE_MASK {k['NT_TILE_MASK']:#06x} / NT_ATTR_MASK "
                          f"{k['NT_ATTR_MASK']:#06x} do not partition the word")
    # Priority is the TOP bit of the attribute mask (VDP nametable layout: bit 15).
    k["PRI"] = 1 << (k["NT_ATTR_MASK"].bit_length() - 1)
    if k["PRI"] != 0x8000:
        raise CouldNotRun(f"top attribute bit is {k['PRI']:#06x}, not bit 15")
    n = k["STRIP_TILE_HEIGHT"]
    # ojz_strip_gen's formula: WIDE_STRIP_SIZE = H*2 + 2*(H//2) + PAD
    k["STRIDE"] = n * 2 + 2 * (n // 2) + k["STRIP_COLLISION_PAD"]
    proj = json.loads((AEON / "project.json").read_text())
    act = proj["zones"][0]["acts"][0]
    k["GRID_W"], k["GRID_H"] = act["gridWidth"], act["gridHeight"]
    k["SEC_PX"] = 1 << k["SECTION_SIZE_SHIFT"]
    if k["SEC_PX"] != n * 8:
        raise CouldNotRun(f"section is {k['SEC_PX']} px but a strip is {n} tiles ({n * 8} px)")
    return k


def load_strips(k: dict) -> dict[int, list[list[int]]]:
    """sec -> [col][row] -> word."""
    out = {}
    n = k["STRIP_TILE_HEIGHT"]
    for s in range(k["GRID_W"] * k["GRID_H"]):
        p = GEN / f"sec{s}_strips_a.bin"
        b = p.read_bytes()
        if len(b) != n * k["STRIDE"]:
            raise CouldNotRun(f"{p} is {len(b)} bytes, expected {n} x {k['STRIDE']}")
        out[s] = [list(struct.unpack(f">{n}H", b[c * k["STRIDE"]: c * k["STRIDE"] + n * 2]))
                  for c in range(n)]
    return out


def population(k: dict, strips: dict) -> list[dict]:
    rows = []
    for s, cols in strips.items():
        gx, gy = s % k["GRID_W"], s // k["GRID_W"]
        for c, col in enumerate(cols):
            for r, w in enumerate(col):
                if (w & k["NT_TILE_MASK"]) == 0 and (w & k["PRI"]):
                    rows.append({"sec": s, "col": c, "row": r, "word": w,
                                 "wx": gx * k["SEC_PX"] + c * 8, "wy": gy * k["SEC_PX"] + r * 8})
    return rows


def strips_word(k, strips, wcx: int, wcy: int) -> int | None:
    """Authored word at WORLD cell (wcx, wcy), or None outside the grid."""
    n = k["STRIP_TILE_HEIGHT"]
    gx, gy = wcx // n, wcy // n
    if not (0 <= gx < k["GRID_W"] and 0 <= gy < k["GRID_H"]):
        return None
    return strips[gy * k["GRID_W"] + gx][wcx % n][wcy % n]


# --------------------------------------------------------------------------- bus helpers

async def c(b, m, p=None, t=120.0):
    return await asyncio.wait_for(b.call(m, p or {}), timeout=t)


async def rmem(b, a: int, n: int) -> bytes:
    return bytes.fromhex(unprefix((await c(b, "emulator/read_memory",
                                           {"addr": hex(a), "len": n}))["bytes"]))


async def rvram(b, a: int, n: int) -> bytes:
    out = b""
    while n:
        k = min(n, 4096)
        out += bytes.fromhex(unprefix((await c(b, "emulator/read_vram",
                                               {"addr": hex(a), "len": k}))["bytes"]))
        a += k
        n -= k
    return out


async def wvram_word(b, a: int, w: int) -> None:
    await c(b, "emulator/write_vram", {"addr": hex(a), "bytes": f"0x{w:04X}"})


async def vregs(b) -> list[int]:
    return [int(unprefix(x), 16) for x in (await c(b, "emulator/read_vdp_registers", {}))["raw"]]


async def drop(b, cp) -> None:
    """Release a checkpoint slot (the server caps them at 8)."""
    await c(b, "emulator/checkpoint_drop", {"id": cp})


async def capture(b) -> list[bytes]:
    """All 224 raster rows as raw RGB bytes. `source` MUST be 'raster'."""
    rows = []
    for s in range(0, ACTIVE_LINES, 16):
        r = await c(b, "emulator/scanlines", {"startLine": s, "count": 16})
        if r.get("source") != "raster":
            raise CouldNotRun(f"emulator/scanlines answered source={r.get('source')!r} "
                              f"caveat={r.get('caveat')!r}: a post-hoc render cannot testify")
        if r.get("mode") != "h40":
            raise CouldNotRun(f"scanlines mode {r.get('mode')!r}, expected h40")
        for row in r["rows"]:
            rows.append(bytes.fromhex(unprefix(row["rgb"])))
    return rows


def px(rows, x, y):
    o = x * 3
    return tuple(rows[y][o:o + 3])


def diff(a: list[bytes], bb: list[bytes]) -> list[tuple[int, int]]:
    out = []
    for y in range(ACTIVE_LINES):
        if a[y] != bb[y]:
            for x in range(WIDTH):
                if a[y][x * 3:x * 3 + 3] != bb[y][x * 3:x * 3 + 3]:
                    out.append((x, y))
    return out


# 8-bit levels of the core's 15-step intensity ramp (normal = even steps, shadow = step/2).
# Derived from the measured pair (0,72,36)->(0,36,18) on line 118->121 and oracle-core
# render.rs `sh_level`: step*255//14. Used only to CLASSIFY changed pixels.
RAMP = [s * 255 // 14 for s in range(15)]
SHADE_OF_NORMAL = {RAMP[2 * n]: RAMP[n] for n in range(8)}


def is_shadow_to_normal(before, after) -> bool:
    return all(ch_a in SHADE_OF_NORMAL and SHADE_OF_NORMAL[ch_a] == ch_b
               for ch_b, ch_a in zip(before, after))


# --------------------------------------------------------------------------- VDP mapping

class Frame:
    """Plane geometry at the paused instant: registers, hscroll, VSRAM, and all of VRAM."""

    def __init__(self, regs, vram, vsram):
        self.regs, self.vram, self.vsram = regs, vram, vsram
        self.a_base = (regs[0x02] & 0x38) << 10
        self.b_base = (regs[0x04] & 0x07) << 13
        self.hs_base = (regs[0x0D] & 0x3F) << 10
        self.hs_mode = regs[0x0B] & 3
        self.vs_mode = (regs[0x0B] >> 2) & 1
        size = {0: 32, 1: 64, 3: 128}
        self.pw, self.ph = size[regs[0x10] & 3], size[(regs[0x10] >> 4) & 3]
        if self.vs_mode != 0:
            raise CouldNotRun("VSRAM is in 2-cell column mode here; this probe maps full-screen "
                              "vscroll only")
        # One pass over the screen per plane: dot -> (addr, tx, ty), and addr -> its dots.
        self.map = {}
        self.dots = {}
        for plane in ("A", "B"):
            m = []
            inv = collections.defaultdict(list)
            for y in range(ACTIVE_LINES):
                row = []
                for x in range(WIDTH):
                    a, tx, ty = self.cell(plane, x, y)
                    row.append((a, tx, ty))
                    inv[a].append((x, y, tx, ty))
                m.append(row)
            self.map[plane], self.dots[plane] = m, inv

    def word(self, a):
        return (self.vram[a] << 8) | self.vram[a + 1]

    def hscroll(self, line, plane):
        off = {0: 0, 1: (line & 7) * 4, 2: (line & ~7) * 4, 3: line * 4}[self.hs_mode]
        return self.word(self.hs_base + off + (2 if plane == "B" else 0)) & 0x3FF

    def vscroll(self, plane):
        o = 0 if plane == "A" else 2
        return ((self.vsram[o] << 8) | self.vsram[o + 1]) & 0x3FF

    def cell(self, plane, x, line):
        """(nametable byte address, tile-local x, tile-local y) for screen dot (x, line)."""
        base = self.a_base if plane == "A" else self.b_base
        pxx = (x - self.hscroll(line, plane)) % (self.pw * 8)
        pyy = (line + self.vscroll(plane)) % (self.ph * 8)
        return base + ((pyy >> 3) * self.pw + (pxx >> 3)) * 2, pxx & 7, pyy & 7

    def pixel_index(self, w, tx, ty):
        t = w & 0x7FF
        if w & 0x1000:
            ty = 7 - ty
        if w & 0x0800:
            tx = 7 - tx
        byte = self.vram[t * 32 + ty * 4 + (tx >> 1)]
        return (byte >> 4) if (tx & 1) == 0 else (byte & 0xF)


async def read_frame(b) -> Frame:
    regs = await vregs(b)
    vram = await rvram(b, 0, 0x10000)
    vs = bytes.fromhex(unprefix((await c(b, "emulator/read", {"space": "vsram", "addr": "0x0",
                                                              "len": 80}))["bytes"]))
    return Frame(regs, vram, vs)


# --------------------------------------------------------------------------- the machine

class Probe:
    def __init__(self, b, sym, k, strips):
        self.b, self.sym, self.k, self.strips = b, sym, k, strips

    async def rword(self, name, n=2):
        return int.from_bytes(await rmem(self.b, self.sym[name], n), "big")

    async def camera(self):
        return (await self.rword("Camera_X", 4)) >> 16, (await self.rword("Camera_Y", 4)) >> 16

    async def warp(self, px_, py_) -> dict:
        b, s = self.b, self.sym
        for a, v, w in ((s["Warp_Req_X"], px_, 2), (s["Warp_Req_Y"], py_, 2), (s["Warp_Req_Flag"], 1, 1)):
            await c(b, "emulator/write_memory", {"addr": hex(a), "value": v, "width": w})
        ack = None
        for i in range(1, 121):
            await c(b, "emulator/run_frames", {"frames": 1})
            if (await rmem(b, s["Warp_Req_Flag"], 1))[0] == 0:
                ack = i
                break
        if ack is None:
            raise CouldNotRun("Warp_Req_Flag never cleared in 120 frames (not in the level state?)")
        clamped = (await self.rword("Warp_Req_X"), await self.rword("Warp_Req_Y"))
        await c(b, "emulator/run_frames", {"frames": POST_WARP})
        cam = await self.camera()
        await c(b, "emulator/run_frames", {"frames": 10})
        cam2 = await self.camera()
        if cam != cam2:
            raise CouldNotRun(f"camera still moving after the warp settle: {cam} -> {cam2}")
        sec = tuple(await rmem(b, s["Parallax_Prev_Sec_X"], 2))
        rp = await self.rword("Raster_Program", 4)
        return {"ack_frames": ack, "requested": (px_, py_), "clamped": clamped, "camera": cam,
                "installed_section": sec[1] * self.k["GRID_W"] + sec[0], "section_xy": sec,
                "raster_program": rp, "raster_program_name": self.name_of(rp)}

    async def screen_l(self):
        """Effects_Screen_L, the four patch channels' latched screen lines, as raw hex words."""
        if "Effects_Screen_L" not in self.sym:
            return None
        raw = await rmem(self.b, self.sym["Effects_Screen_L"], 8)
        return [f"{int.from_bytes(raw[i:i + 2], 'big'):04X}" for i in range(0, 8, 2)]

    def name_of(self, addr):
        best = None
        for n, a in self.sym.items():
            if a == addr and (best is None or len(n) < len(best)):
                best = n
        return best

    async def sh_sweep(self, cp) -> list[int]:
        """reg $0C per line over one frame from checkpoint `cp` (run_to_scanline 0..223)."""
        await c(self.b, "emulator/restore", {"id": cp})
        out = []
        for line in range(ACTIVE_LINES):
            r = await c(self.b, "emulator/run_to_scanline", {"line": line, "maxFrames": 2})
            if not r.get("reached"):
                raise CouldNotRun(f"run_to_scanline {line} not reached: {r}")
            out.append((await vregs(self.b))[0x0C])
        return out

    async def frame_from(self, cp, pokes=()) -> list[bytes]:
        await c(self.b, "emulator/restore", {"id": cp})
        for a, w in pokes:
            await wvram_word(self.b, a, w)
        await c(self.b, "emulator/run_frames", {"frames": FRAMES_PER_CAPTURE})
        rows = await capture(self.b)
        for a, w in pokes:
            got = int.from_bytes(await rvram(self.b, a, 2), "big")
            if got != w:
                raise CouldNotRun(f"VRAM ${a:04X} read back {got:04X} after the capture, poked "
                                  f"{w:04X}: the engine rewrote it inside the capture window")
        return rows

    async def attr(self, x, y):
        return await c(self.b, "emulator/pixel_attribution", {"x": x, "y": y})


def sh_band(sweep: list[int]) -> list[int]:
    return [i for i, v in enumerate(sweep) if v & 0x08]


def band_str(lines: list[int]) -> str:
    if not lines:
        return "none"
    runs, start, prev = [], lines[0], lines[0]
    for x in lines[1:]:
        if x != prev + 1:
            runs.append((start, prev))
            start = x
        prev = x
    runs.append((start, prev))
    return ", ".join(f"{a}..{z}" for a, z in runs)


def cell_pixels(fr: Frame, plane, addr):
    """Screen dots whose plane-`plane` cell is `addr` (per-line hscroll aware)."""
    return list(fr.dots[plane].get(addr, []))


def summarise_change(before, after, pts):
    pairs = collections.Counter((px(before, x, y), px(after, x, y)) for x, y in pts)
    s2n = sum(n for (bf, af), n in pairs.items() if is_shadow_to_normal(bf, af))
    return pairs, s2n


def fmt_pairs(pairs, limit=8):
    return "; ".join(f"{bf}->{af} x{n}" for (bf, af), n in pairs.most_common(limit))


async def choose_blank_cell(p: Probe, fr: Frame, lines_ok: set, sprite_free=True):
    """Best blank plane-A cell whose every dot lies on `lines_ok`, over low-priority opaque B."""
    cands = set()
    for y in sorted(lines_ok):
        for x in range(WIDTH):
            a = fr.map["A"][y][x][0]
            if fr.word(a) == 0x0000:
                cands.add(a)
    scored = []
    for a in sorted(cands):
        full = cell_pixels(fr, "A", a)
        if len(full) != 64 or any(y not in lines_ok for _, y, _, _ in full):
            continue
        if any(x < 8 or x > WIDTH - 9 for x, _, _, _ in full):
            continue
        opaque = 0
        ok = True
        for x, y, _, _ in full:
            ba, tx, ty = fr.map["B"][y][x]
            bw = fr.word(ba)
            if bw & 0x8000:
                ok = False
                break
            if fr.pixel_index(bw, tx, ty):
                opaque += 1
        if ok:
            scored.append((-opaque, a, full))
    scored.sort()
    for neg, a, full in scored[:40]:
        if sprite_free:
            clean = True
            for x, y, _, _ in full:
                if (await p.attr(x, y))["winner"]["layer"] == "sprite":
                    clean = False
                    break
            if not clean:
                continue
        return a, full, -neg, len(scored)
    return None, None, 0, len(scored)


async def verify_neighbourhood(p: Probe, fr: Frame, cam, wx, wy) -> tuple[int, int, int]:
    """Visible 7x7 world cells around (wx,wy): VRAM blank/attrs vs strips_a. (agree, disagree, n)."""
    k = p.k
    agree = dis = 0
    for dr in range(-3, 4):
        for dc in range(-3, 4):
            cx, cy = (wx >> 3) + dc, (wy >> 3) + dr
            sx, sy = cx * 8 - cam[0], cy * 8 - cam[1]
            if not (0 <= sx <= WIDTH - 8 and 0 <= sy <= ACTIVE_LINES - 8):
                continue
            want = strips_word(k, p.strips, cx, cy)
            if want is None:
                continue
            a, _, _ = fr.cell("A", sx + 4, sy + 4)
            got = fr.word(a)
            wb, gb = (want & k["NT_TILE_MASK"]) == 0, (got & k["NT_TILE_MASK"]) == 0
            if wb != gb:
                dis += 1
            elif gb:
                agree += 1 if got == 0 else 0
                dis += 0 if got == 0 else 1
            elif (want & k["NT_ATTR_MASK"]) == (got & k["NT_ATTR_MASK"]):
                agree += 1
            else:
                dis += 1
    return agree, dis, agree + dis


# --------------------------------------------------------------------------- scenes

def section_rect(k, s):
    gx, gy = s % k["GRID_W"], s // k["GRID_W"]
    return gx * k["SEC_PX"], gy * k["SEC_PX"]


def reachable(k, w, band: list[int], sec: int, cam_max):
    """Is there a camera, with its centre in `sec` and inside 0..cam_max, that shows word `w`'s
    whole cell on lines inside `band` (the band measured for `sec`)? Returns the camera or None."""
    if not band:
        return None
    x0, y0 = section_rect(k, sec)
    # centre rule (Parallax_CheckBoundary): camX + 160 in [x0, x0+SEC-1], camY + 112 likewise
    cx_lo, cx_hi = max(0, x0 - WIDTH // 2), min(cam_max[0], x0 + k["SEC_PX"] - 1 - WIDTH // 2)
    cy_lo, cy_hi = max(0, y0 - ACTIVE_LINES // 2), min(cam_max[1], y0 + k["SEC_PX"] - 1 - ACTIVE_LINES // 2)
    # cell fully on screen horizontally
    cx_lo2, cx_hi2 = max(cx_lo, w["wx"] + 8 - WIDTH), min(cx_hi, w["wx"])
    if cx_lo2 > cx_hi2:
        return None
    bandset = set(band)
    for cy in range(max(cy_lo, w["wy"] + 8 - ACTIVE_LINES), min(cy_hi, w["wy"]) + 1):
        top = w["wy"] - cy
        if all((top + i) in bandset for i in range(8)):
            return (cx_lo2, cy)
    return None


async def inplace(p: Probe, cp, fr: Frame, cam, words, base_rows, label, out):
    """Write each on-screen authored word back into VRAM, one at a time, then all together."""
    k = p.k
    rows = []
    pokes_all = []
    for w in words:
        sx, sy = w["wx"] - cam[0], w["wy"] - cam[1]
        if not (0 <= sx <= WIDTH - 8 and 0 <= sy <= ACTIVE_LINES - 8):
            continue
        a, tx, ty = fr.cell("A", sx + 4, sy + 4)
        if (tx, ty) != (4, 4):
            rows.append({**w, "status": f"plane A not tile-aligned to world (tile-local {tx},{ty})"})
            continue
        cur = fr.word(a)
        ag, dis, n = await verify_neighbourhood(p, fr, cam, w["wx"], w["wy"])
        rec = {**w, "screen": (sx, sy), "vram_addr": a, "vram_word": cur,
               "neigh_agree": ag, "neigh_disagree": dis, "neigh_n": n}
        if cur != 0x0000 or dis:
            rec["status"] = "MAPPING NOT CONFIRMED, not poked"
            rows.append(rec)
            continue
        after = await p.frame_from(cp, [(a, w["word"])])
        d = diff(base_rows, after)
        cellpts = [(x, y) for x, y, _, _ in cell_pixels(fr, "A", a)]
        cellset = set(cellpts)
        inside = [q for q in d if q in cellset]
        pairs, s2n = summarise_change(base_rows, after, inside)
        dset = set(d)
        unchanged = collections.Counter(px(base_rows, x, y) for x, y in cellpts if (x, y) not in dset)
        rec["unchanged_colours"] = {str(k_): v for k_, v in unchanged.items()}
        at = await p.attr(sx + 4, sy + 4)
        pa = next((cd for cd in at["candidates"] if cd["layer"] == "planeA"), {})
        b_pri = sum(1 for x, y in cellpts if fr.word(fr.cell("B", x, y)[0]) & 0x8000)
        rec.update({"changed": len(d), "changed_inside_cell": len(inside),
                    "changed_outside_cell": len(d) - len(inside), "cell_dots": len(cellpts),
                    "shadow_to_normal": s2n, "pairs": fmt_pairs(pairs),
                    "planeB_high_priority_dots": b_pri,
                    "attr_planeA_priority_after": pa.get("priority"),
                    "sh_lines_in_cell": None, "status": "measured"})
        rows.append(rec)
        pokes_all.append((a, w["word"]))
    together = None
    if pokes_all:
        after = await p.frame_from(cp, pokes_all)
        d = diff(base_rows, after)
        pairs, s2n = summarise_change(base_rows, after, d)
        together = {"words": len(pokes_all), "changed": len(d), "shadow_to_normal": s2n,
                    "pairs": fmt_pairs(pairs)}
    out[label] = {"words": rows, "together": together}
    return rows, together


# --------------------------------------------------------------------------- main

async def run(rom, lst, sock, k, strips, pop, report):
    sym = parse_lst(lst)
    for n in ("Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Camera_X", "Camera_Y", "Raster_Program",
              "Parallax_Prev_Sec_X", "Camera_X_Max", "Camera_Y_Max"):
        if n not in sym:
            raise CouldNotRun(f"{lst}: symbol {n} absent")
    b = BusClient(socket_path=sock, client_id="blank-priority", client_name="blank_priority_probe")
    await b.connect()
    for m in ("emulator/write_vram", "emulator/scanlines", "emulator/run_to_scanline",
              "emulator/checkpoint", "emulator/restore", "emulator/pixel_attribution"):
        if not b.supports(m):
            raise CouldNotRun(f"server does not advertise {m}")
    p = Probe(b, sym, k, strips)
    await c(b, "emulator/load_symbols", {"path": lst})
    await c(b, "emulator/reset", {})
    await c(b, "emulator/run_frames", {"frames": SETTLE})

    # ---- 2. S/H extent, measured, per section -------------------------------------------
    # First at the BOOT camera, before any warp: the one position no warp chose.
    cam0 = await p.camera()
    sec0 = tuple(await rmem(b, sym["Parallax_Prev_Sec_X"], 2))
    rp0 = await p.rword("Raster_Program", 4)
    cp = (await c(b, "emulator/checkpoint", {}))["id"]
    sw0 = await p.sh_sweep(cp)
    await drop(b, cp)
    esl0 = await p.screen_l()
    report["boot_sweep"] = {"camera": cam0, "section_xy": sec0, "raster": p.name_of(rp0) or hex(rp0),
                            "band": band_str(sh_band(sw0)), "effects_screen_l": esl0}
    print(f"  boot: camera {cam0} installed sec{sec0[1] * k['GRID_W'] + sec0[0]} raster "
          f"{p.name_of(rp0) or hex(rp0)}  reg$0C values {[f'{v:02X}' for v in sorted(set(sw0))]}  "
          f"S/H lines: {band_str(sh_band(sw0))}  Effects_Screen_L {esl0}")
    sweeps = {}
    unmeasured = []
    cam_max = None
    for s in range(k["GRID_W"] * k["GRID_H"]):
        x0, y0 = section_rect(k, s)
        sp = k["SEC_PX"]
        got = None
        # The centre first; if the warp's clamp lands the camera centre in another section,
        # try the other points before giving up on this section.
        for fx, fy in ((2, 2), (1, 1), (3, 3), (1, 3), (3, 1)):
            w = await p.warp(x0 + sp * fx // 4, y0 + sp * fy // 4)
            if w["installed_section"] == s:
                got = w
                break
        if cam_max is None:
            cam_max = (await p.rword("Camera_X_Max"), await p.rword("Camera_Y_Max"))
        if got is None:
            unmeasured.append(s)
            print(f"  sec{s}: UNMEASURED — no warp point installed this section (last camera "
                  f"{w['camera']} installed sec{w['installed_section']})")
            continue
        w = got
        cp = (await c(b, "emulator/checkpoint", {}))["id"]
        sw = await p.sh_sweep(cp)
        await drop(b, cp)
        band = sh_band(sw)
        esl = await p.screen_l()
        sweeps[s] = {"warp": w, "band": band, "reg0C_values": sorted(set(sw)), "esl": esl}
        print(f"  sec{s}: camera {w['camera']} installed sec{w['installed_section']} "
              f"raster {w['raster_program_name'] or hex(w['raster_program'])}  "
              f"reg$0C values {[f'{v:02X}' for v in sorted(set(sw))]}  S/H lines: {band_str(band)}"
              f"  Effects_Screen_L {esl}")
    report["sh_extent"] = {s: {"band": band_str(v["band"]), "camera": v["warp"]["camera"],
                               "raster": v["warp"]["raster_program_name"],
                               "reg0C": [f"{x:02X}" for x in v["reg0C_values"]],
                               "effects_screen_l": v["esl"]}
                           for s, v in sweeps.items()}
    report["sh_unmeasured_sections"] = unmeasured
    report["camera_max"] = cam_max
    print(f"  camera bounds: 0..{cam_max[0]} x 0..{cam_max[1]} (Camera_X_Max / Camera_Y_Max)")

    # ---- 5a. reachability of the population into a MEASURED band --------------------------
    # A band measured at the section centre is taken as the section's band at every camera.
    # That holds for a static-line program (sec 1) and a PATCH_ANCHOR_NONE record (sec 0);
    # a world-anchored S/H record would need its own sweep, and the output says which applies.
    sh_secs = [s for s, v in sweeps.items() if v["band"]]
    reach = []
    for w in pop:
        hits = []
        for s in sh_secs:
            cam = reachable(k, w, sweeps[s]["band"], s, cam_max)
            if cam is not None:
                hits.append((s, cam))
        reach.append(hits)
    n_reach = sum(1 for h in reach if h)
    per_sec = collections.Counter(w["sec"] for w, h in zip(pop, reach) if h)
    report["consequence_count"] = {"population": len(pop), "reachable_into_sh": n_reach,
                                   "per_section": dict(sorted(per_sec.items())),
                                   "sh_sections": sh_secs, "unmeasured_sections": unmeasured}
    print(f"\n  CONSEQUENCE COUNT: {n_reach} of {len(pop)} blank-priority words can be shown inside a "
          f"measured S/H band (S/H sections: {sh_secs}); per section {dict(sorted(per_sec.items()))}"
          + (f"; sections NOT measured (not counted): {unmeasured}" if unmeasured else ""))

    # ---- 3/4. premise + controls in section 1 ----------------------------------------------
    scenes = {
        # section-1 cluster, world y 576..599, lands on lines ~136..159 (below the line-120 fire)
        "sec1": (2280, 552),
        # section-0 cluster, cols 7/23/39 rows 66..72, world y 528..583, below sec 0's line
        "sec0": (200, 520),
        # section 7, row 32 (world y 4352) below the water surface, camera centre in sec 7
        "sec7": (2240, 4314),
    }
    for label, (tx, ty) in scenes.items():
        w = await p.warp(tx, ty)
        cam = w["camera"]
        cp = (await c(b, "emulator/checkpoint", {}))["id"]
        sw = await p.sh_sweep(cp)
        band = sh_band(sw)
        base = await p.frame_from(cp)
        base2 = await p.frame_from(cp)
        dd = diff(base, base2)
        await c(b, "emulator/restore", {"id": cp})
        await c(b, "emulator/run_frames", {"frames": FRAMES_PER_CAPTURE})
        fr = await read_frame(b)
        hsA = fr.hscroll(150, "A")
        sc = {"warp": w, "sh_band": band_str(band), "reg0C": [f"{x:02X}" for x in sorted(set(sw))],
              "determinism_diff": len(dd), "hscrollA_line150": hsA, "vscrollA": fr.vscroll("A"),
              "planeA_base": fr.a_base, "planeB_base": fr.b_base, "hs_mode": fr.hs_mode,
              "vs_mode": fr.vs_mode, "plane_cells": (fr.pw, fr.ph)}
        report.setdefault("scenes", {})[label] = sc
        print(f"\n== {label}: warp {w['requested']} -> camera {cam}, installed sec{w['installed_section']}, "
              f"raster {w['raster_program_name'] or hex(w['raster_program'])}")
        sc["effects_screen_l"] = await p.screen_l()
        print(f"   reg $0C values over the frame {sc['reg0C']}; S/H ON on lines {band_str(band)}; "
              f"Effects_Screen_L (ch0..3) {sc['effects_screen_l']}")
        print(f"   determinism control: two unmodified captures from one checkpoint differ in "
              f"{len(dd)} px")
        print(f"   plane A ${fr.a_base:04X}, plane B ${fr.b_base:04X}, {fr.pw}x{fr.ph} cells, hscroll mode "
              f"{fr.hs_mode}, vscroll A {fr.vscroll('A')} (camY {cam[1]}), hscroll A @150 = {hsA} "
              f"(-camX mod 1024 = {(-cam[0]) % 1024})")
        if dd:
            raise CouldNotRun(f"{label}: the determinism control failed ({len(dd)} px differ "
                              f"between two unmodified captures) — no diff here is a verdict")

        if label == "sec1":
            if not band:
                raise CouldNotRun("sec1: no S/H line measured — the premise has no subject")
            lo = band[0]
            in_band = {y for y in band if y >= lo + 4}
            a, full, opaque, ncand = await choose_blank_cell(p, fr, in_band)
            if a is None:
                raise CouldNotRun(f"BLOCKED: no blank plane-A cell fully inside the S/H band over "
                                  f"low-priority plane B without a sprite ({ncand} candidates)")
            pts = [(x, y) for x, y, _, _ in full]
            after = await p.frame_from(cp, [(a, 0x8000)])
            d = diff(base, after)
            inside = [q for q in d if q in set(pts)]
            pairs, s2n = summarise_change(base, after, inside)
            unchanged = collections.Counter(px(base, x, y) for x, y in pts if (x, y) not in set(d))
            at = await p.attr(pts[0][0], pts[0][1])
            pa = next((cd for cd in at["candidates"] if cd["layer"] == "planeA"), {})
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            prem = {"vram_addr": a, "screen_rect": (min(xs), min(ys), max(xs), max(ys)),
                    "opaque_B_dots": opaque, "candidates": ncand, "changed": len(d),
                    "changed_inside_cell": len(inside), "changed_outside_cell": len(d) - len(inside),
                    "shadow_to_normal": s2n, "pairs": fmt_pairs(pairs),
                    "unchanged_colours": {str(k_): v for k_, v in unchanged.items()},
                    "attr_planeA_priority_after": pa.get("priority")}
            report["premise"] = prem
            print(f"\n   PREMISE: blank plane-A cell VRAM ${a:04X} at screen {prem['screen_rect']} "
                  f"(inside S/H lines {lo + 4}..; {opaque}/64 plane-B dots opaque, all B low-priority; "
                  f"chosen of {ncand} candidates)")
            print(f"     $0000 -> $8000: {len(d)} px changed ({len(inside)} inside the cell, "
                  f"{len(d) - len(inside)} outside); shadow->normal exact: {s2n}")
            print(f"     before->after: {prem['pairs']}")
            print(f"     unchanged dots in the cell: {dict(unchanged)}")
            print(f"     pixel_attribution after the poke: plane A priority={pa.get('priority')} "
                  f"opaque={pa.get('opaque')}")
            # Every attribute bit EXCEPT priority (palette 3, both flips) on the same cell:
            # a transparent tile's palette/flips cannot change a dot, so the prediction is 0.
            non_pri = k["NT_ATTR_MASK"] & ~k["PRI"]
            after_np = await p.frame_from(cp, [(a, non_pri)])
            d_np = diff(base, after_np)
            prem["non_priority_attrs"] = {"word": f"{non_pri:04X}", "changed": len(d_np)}
            print(f"     same cell, $0000 -> ${non_pri:04X} (palette + flips, NO priority): "
                  f"{len(d_np)} px changed")

            above = {y for y in range(ACTIVE_LINES) if y not in set(band) and y <= lo - 4}
            a2, full2, opaque2, ncand2 = await choose_blank_cell(p, fr, above)
            if a2 is None:
                raise CouldNotRun("BLOCKED: no blank control cell above the S/H line")
            pts2 = [(x, y) for x, y, _, _ in full2]
            after2 = await p.frame_from(cp, [(a2, 0x8000)])
            d2 = diff(base, after2)
            at2 = await p.attr(pts2[0][0], pts2[0][1])
            pa2 = next((cd for cd in at2["candidates"] if cd["layer"] == "planeA"), {})
            xs, ys = [q[0] for q in pts2], [q[1] for q in pts2]
            ctl = {"vram_addr": a2, "screen_rect": (min(xs), min(ys), max(xs), max(ys)),
                   "opaque_B_dots": opaque2, "changed": len(d2),
                   "attr_planeA_priority_after": pa2.get("priority")}
            report["control_outside_sh"] = ctl
            print(f"   CONTROL (same frame, above the S/H line): VRAM ${a2:04X} at screen "
                  f"{ctl['screen_rect']} ({opaque2}/64 B dots opaque): $0000 -> $8000 changed "
                  f"{len(d2)} px; pixel_attribution plane A priority={pa2.get('priority')}")

        words = [w_ for w_ in pop]
        rows, together = await inplace(p, cp, fr, cam, words, base, label, report.setdefault("inplace", {}))
        print(f"   IN PLACE ({label}): {len(rows)} re-derived blank-priority word(s) on screen")
        for r in rows:
            if r["status"] != "measured":
                print(f"     sec{r['sec']} col {r['col']} row {r['row']} word {r['word']:04X}: {r['status']}"
                      f" (VRAM {r.get('vram_word', 0):04X}, neighbourhood {r.get('neigh_agree')}/"
                      f"{r.get('neigh_n')})")
                continue
            print(f"     sec{r['sec']} col {r['col']:3d} row {r['row']:3d} world ({r['wx']},{r['wy']}) "
                  f"screen {r['screen']} VRAM ${r['vram_addr']:04X}={r['vram_word']:04X} "
                  f"[mapping {r['neigh_agree']}/{r['neigh_n']}]  -> {r['word']:04X}: changed "
                  f"{r['changed']} ({r['changed_inside_cell']} in cell, {r['changed_outside_cell']} "
                  f"outside), shadow->normal {r['shadow_to_normal']}, B high-pri dots "
                  f"{r['planeB_high_priority_dots']}, attr A pri {r['attr_planeA_priority_after']}")
            if r["pairs"]:
                print(f"         {r['pairs']}")
            print(f"         unchanged dots: {r['unchanged_colours']}")
        if together:
            print(f"     all {together['words']} together: changed {together['changed']} px, "
                  f"shadow->normal {together['shadow_to_normal']}")
        await drop(b, cp)
    await b.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--json")
    ap.add_argument("--any-rom", action="store_true",
                    help=f"run on a ROM whose crc32 is not {EXPECT_CRC:08x}")
    a = ap.parse_args()
    t0 = time.monotonic()
    print(f"blank_priority_probe  started {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    report: dict = {}
    inst = None
    try:
        for pth in (a.rom, a.lst):
            if not os.path.isfile(pth):
                raise CouldNotRun(f"missing {pth}")
        data = Path(a.rom).read_bytes()
        crc = zlib.crc32(data)
        print(f"  ROM {a.rom}: {len(data)} bytes, crc32 {crc:08x}")
        report["rom"] = {"path": a.rom, "size": len(data), "crc32": f"{crc:08x}"}
        if crc != EXPECT_CRC and not a.any_rom:
            raise CouldNotRun(f"ROM crc32 {crc:08x} is not the measured {EXPECT_CRC:08x}; pass --any-rom")
        k = derive_constants()
        strips = load_strips(k)
        pop = population(k, strips)
        per = collections.Counter(w["sec"] for w in pop)
        print(f"  masks: NT_TILE_MASK ${k['NT_TILE_MASK']:04X}, NT_ATTR_MASK ${k['NT_ATTR_MASK']:04X}, "
              f"priority ${k['PRI']:04X}; strip stride {k['STRIDE']} B; grid {k['GRID_W']}x{k['GRID_H']}")
        print(f"  POPULATION: {len(pop)} blank words (tile index 0) carrying the priority bit; per section "
              f"{[per.get(s, 0) for s in range(k['GRID_W'] * k['GRID_H'])]}")
        report["population"] = {"total": len(pop),
                                "per_section": [per.get(s, 0) for s in range(k["GRID_W"] * k["GRID_H"])],
                                "words": pop}
        inst = AetherInstance(a.rom, symbols=a.lst)
        sock = inst.start()
        print(f"  oracle-aether pid {inst.pid} (spawned via aether_instance), implementation "
              f"{inst.handshake.get('implementation')!r}")
        report["server_pid"] = inst.pid
        asyncio.run(run(a.rom, a.lst, sock, k, strips, pop, report))
    except CouldNotRun as e:
        print(f"blank_priority_probe: COULD NOT RUN — {e}", file=sys.stderr)
        return 2
    except Exception as e:  # a wedge, a refused RPC: never a verdict
        print(f"blank_priority_probe: COULD NOT RUN — {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        if inst is not None:
            pid = inst.pid
            inst.reap()
            if pid:
                print(f"  reaped pid {pid}: {'STILL ALIVE' if os.path.exists(f'/proc/{pid}') else 'gone'}")
        if a.json:
            Path(a.json).write_text(json.dumps(report, indent=1, default=str))
    print(f"blank_priority_probe  finished in {time.monotonic() - t0:.1f}s at "
          f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    return 0


if __name__ == "__main__":
    sys.exit(main())
