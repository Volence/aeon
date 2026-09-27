#!/usr/bin/env python3
"""first_screen_fg_witness — is the FOREGROUND a clip act draws on its first screen the baked one?

WHY IT EXISTS (WOVEN-BOOT-FG-GARBAGE, 2026-09-27). The owner booted the woven Sonic 2 act
(`S2CLIP=s2_woven`) and its first screen had a shredded foreground: Emerald Hill's grass and
dirt with holes cut through it, the background showing through where ground belongs; flying
away and back repaired it. MEASURED on the woven DEBUG ROM (crc 2a0f1df3): 191 of the 1,120
visible Plane A cells that the bake paints were the blank word $0000 at frame 180, every one
of them a tile of pool page 12, and the tile cache held the same $0000 there. The act has 49
pages; a streaming act bulk-loads only pages [0, PAGE_FRAMES_CLAMP) (engine/level/
load_art.emp), and the woven start (Emerald Hill, section 5) needs pages 12 and 13 as well.
TileCache_FillAll met them non-resident, took the patch run's miss arm (demand the page,
leave the cell untouched, set Cache_Art_Stall) and returned; nothing ever resumed those
cells, because FillAll ignored the stall and the per-frame fill only extends the window's
edges. The pages landed a few frames later, into cells nobody rewrote.

WHAT IT MEASURES. For every cell it grades, the cell's EXPECTED content is derived from the
bake the ROM was built from (games/sonic4/data/clips/<clip>/baked: section_N.local.bin, the
section's local nametable word; secN_local_map.bin, local -> global pool slot; pool.bin, the
pool's 8x8 patterns at slot * 32), and the ACTUAL content is the cell's nametable word
RESOLVED through the VRAM it names: (word & $F800, the 32 pattern bytes at (word & $7FF) * 32).
Physical page frames differ from global pages whenever the act streams, so raw words are not
comparable; resolved cells are (docs/research/2026-09-27-general-patch-loop/pic_witness.py).
  * an art cell (global slot != 0) must carry the baked attribute bits and the baked pattern;
  * a blank cell (global slot 0) must resolve to an all-zero (transparent) pattern.
Two surfaces are graded at each stop:
  PLANE  the visible Plane A cells, world tile cols floor(cx/8) .. floor((cx+319)/8) and rows
         floor(cy/8) .. floor((cy+223)/8), read at plane cell (col mod 64, row mod 64);
  CACHE  every cell of the 80x60 Tile_Cache_Nametable window (Cache_Left_Col/Top_Row and the
         circular origins), less a pending partial column/row (the DECLARED != FILLED rule,
         ARCH §4.7) — a hole off screen becomes a hole on screen the moment the streamer
         draws it.
Stops: BOOT, `--boot` frames after reset with no input (the owner's view); then one WARP per
clip rectangle in the manifest (to its centre, through the DEBUG warp mailbox, which runs the
same Tile_Cache_Init as the boot), `--settle` frames after the mailbox is acknowledged.

Exit 0 every graded cell matched; 1 a cell did not (the first few printed, and the totals);
2 could not run (symbol missing, the baked tree absent or not this ROM's: its page count must
equal the ROM's PageIn_Pool_Pages, and the warp mailbox must acknowledge).

Usage (DEBUG clip shape; spawns its own headless emulator):
    S2CLIP=s2_woven DEBUG=1 ./build.sh
    python3 tools/first_screen_fg_witness.py --rom s4.s2clip.debug.bin \\
        --lst s4.s2clip.debug.lst --clip s2_woven
Wired: tools/keepalive_manifest.toml (the nightly builds DEBUG S2CLIP=s2_woven and keeps it as
s4.s2clip_woven.debug.*). Not in tools/landing_build.sh, which builds no clip shape.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import struct
import sys
import zlib
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance, SpawnError  # noqa: E402
from aether_bytes import unprefix  # noqa: E402
from cart_identity import CartMismatch  # noqa: E402

BOOT_FRAMES = 180          # the owner's measured frame
SETTLE_FRAMES = 30
PLANE_A = 0xC000           # engine.constants VRAM_PLANE_A
PLANE_CELLS = 64           # PLANE_H_CELLS = PLANE_V_CELLS (engine.constants)
CACHE_COLS, CACHE_ROWS = 80, 60   # TILE_CACHE_COLS / TILE_CACHE_ROWS
SCREEN_W, SCREEN_H = 320, 224
TILE = 8
SYMS = ("Camera_X", "Camera_Y", "Tile_Cache_Nametable", "Cache_Left_Col", "Cache_Top_Row",
        "Cache_Origin_Col", "Cache_Origin_Row", "Cache_Fill_Resume_Col",
        "Cache_Fill_RowResume_Row", "PageIn_Pool_Pages", "Warp_Req_X", "Warp_Req_Y",
        "Warp_Req_Flag")
SHOW = 8


class CouldNotRun(Exception):
    pass


class Bake:
    """The expected foreground, straight off the baked tree."""

    def __init__(self, baked: Path):
        if not (baked / "clipact.json").is_file():
            raise CouldNotRun(f"no baked tree at {baked} (build the clip shape first)")
        meta = json.loads((baked / "clipact.json").read_text())
        self.gw, self.gh = meta["act"]["grid_w"], meta["act"]["grid_h"]
        self.sect = meta["act"]["section_px"] // TILE
        self.pages = meta["pool"]["pages"]
        self.pool = (baked / "pool.bin").read_bytes()
        self.baked = baked
        self._sec = {}
        self.clips = json.loads((baked / "clips.json").read_text())["clips"]

    def _section(self, n):
        if n not in self._sec:
            loc = (self.baked / f"section_{n}.local.bin").read_bytes()
            raw = (self.baked / f"sec{n}_local_map.bin").read_bytes()
            self._sec[n] = (loc, struct.unpack(f">{len(raw) // 2}H", raw))
        return self._sec[n]

    def cell(self, col, row):
        """(attr bits, global slot) the bake puts at world tile (col, row); off the act: blank."""
        sx, sy = col // self.sect, row // self.sect
        if col < 0 or row < 0 or sx >= self.gw or sy >= self.gh:
            return 0, 0
        loc, lmap = self._section(sy * self.gw + sx)
        i = ((row % self.sect) * self.sect + (col % self.sect)) * 2
        w = (loc[i] << 8) | loc[i + 1]
        return w & 0xF800, lmap[w & 0x7FF]

    def pattern(self, g):
        return self.pool[g * 32:g * 32 + 32]


def grade(bake, vram, word, col, row):
    """None when the resolved cell is the baked one, else a short reason."""
    attr, g = bake.cell(col, row)
    t = word & 0x7FF
    pat = vram[t * 32:t * 32 + 32]
    if g == 0:
        return None if not any(pat) else f"baked blank, drawn opaque (word ${word:04X})"
    if word == 0:
        return f"baked slot {g} (page {g >> 6}), drawn BLANK ($0000)"
    if (word & 0xF800) != attr:
        return f"baked attr ${attr:04X} slot {g}, drawn word ${word:04X}"
    if pat != bake.pattern(g):
        return f"baked slot {g} (page {g >> 6}), word ${word:04X} names other art"
    return None


async def snapshot(b, s):
    async def rm(addr, n):
        out = b""
        while len(out) < n:
            k = min(1024, n - len(out))
            r = await b.call("emulator/read_memory", {"addr": hex((addr + len(out)) & 0xFFFFFF), "len": k})
            out += bytes.fromhex(unprefix(r["bytes"]))[:k]
        if len(out) != n:
            raise CouldNotRun(f"read_memory ${addr:06X} returned {len(out)} of {n} B")
        return out

    async def rv(addr, n):
        out = b""
        while len(out) < n:
            k = min(4096, n - len(out))
            r = await b.call("emulator/read_vram", {"addr": hex(addr + len(out)), "len": k})
            out += bytes.fromhex(unprefix(r["bytes"]))[:k]
        if len(out) != n:
            raise CouldNotRun(f"read_vram ${addr:04X} returned {len(out)} of {n} B")
        return out

    snap = {}
    for n in ("Camera_X", "Camera_Y", "Cache_Left_Col", "Cache_Top_Row", "Cache_Origin_Col",
              "Cache_Origin_Row", "Cache_Fill_Resume_Col", "Cache_Fill_RowResume_Row"):
        snap[n] = int.from_bytes(await rm(s[n], 2), "big")
    snap["tc"] = await rm(s["Tile_Cache_Nametable"], CACHE_COLS * CACHE_ROWS * 2)
    snap["vram"] = await rv(0, 0x10000)
    return snap


def grade_stop(bake, snap, label):
    vram, tc = snap["vram"], snap["tc"]
    cx, cy = snap["Camera_X"], snap["Camera_Y"]
    bad = []
    n_plane = n_cache = art = 0
    for row in range(cy // TILE, (cy + SCREEN_H - 1) // TILE + 1):
        for col in range(cx // TILE, (cx + SCREEN_W - 1) // TILE + 1):
            a = PLANE_A + ((row % PLANE_CELLS) * PLANE_CELLS + (col % PLANE_CELLS)) * 2
            w = (vram[a] << 8) | vram[a + 1]
            n_plane += 1
            art += bake.cell(col, row)[1] != 0
            why = grade(bake, vram, w, col, row)
            if why:
                bad.append(("PLANE", col, row, why))
    left, top = snap["Cache_Left_Col"], snap["Cache_Top_Row"]
    oc, orow = snap["Cache_Origin_Col"], snap["Cache_Origin_Row"]
    skip_col, skip_row = snap["Cache_Fill_Resume_Col"], snap["Cache_Fill_RowResume_Row"]
    skipped = cache_art = 0
    for lr in range(CACHE_ROWS):
        row = top + lr
        for lc in range(CACHE_COLS):
            col = left + lc
            if col == skip_col or row == skip_row:
                skipped += 1
                continue
            i = (((lr + orow) % CACHE_ROWS) * CACHE_COLS + (lc + oc) % CACHE_COLS) * 2
            n_cache += 1
            cache_art += bake.cell(col, row)[1] != 0
            why = grade(bake, vram, (tc[i] << 8) | tc[i + 1], col, row)
            if why:
                bad.append(("CACHE", col, row, why))
    nb_p = sum(1 for x in bad if x[0] == "PLANE")
    nb_c = len(bad) - nb_p
    print(f"  {label}: camera ({cx},{cy}); PLANE {n_plane - nb_p}/{n_plane} cells right "
          f"({art} painted); CACHE window cols {left}.. rows {top}..: {n_cache - nb_c}/{n_cache} "
          f"right ({cache_art} painted; {skipped} in a pending partial, not graded)")
    for x in bad[:SHOW]:
        print(f"      {x[0]} world tile ({x[1]},{x[2]}): {x[3]}")
    if len(bad) > SHOW:
        print(f"      ... and {len(bad) - SHOW} more")
    if cache_art == 0:
        raise CouldNotRun(f"{label}: the bake paints nothing in the whole cache window; nothing to grade")
    return len(bad)


async def drive(sock, bake, boot, settle, warps):
    b = BusClient(socket_path=sock, client_id="fsfg", client_name="first-screen-fg")
    await b.connect()
    try:
        s = {}
        for n in SYMS:
            try:
                s[n] = int((await b.call("emulator/lookup_symbol", {"name": n}))["addr"], 16) & 0xFFFFFF
            except Exception as ex:  # noqa: BLE001 - the bus raises its own type
                raise CouldNotRun(f"symbol {n} not in the listing ({ex}); a DEBUG clip ROM is required")
        await b.call("emulator/run_frames", {"frames": boot})
        r = await b.call("emulator/read_memory", {"addr": hex(s["PageIn_Pool_Pages"]), "len": 2})
        pages = int(unprefix(r["bytes"]), 16)
        if pages != bake.pages:
            raise CouldNotRun(f"the ROM's pool has {pages} pages, the baked tree {bake.pages}: "
                              "the bake is not this ROM's")
        fails = {}
        fails["boot"] = grade_stop(bake, await snapshot(b, s), f"BOOT (frame {boot})")
        for name, x, y in warps:
            await b.call("emulator/write_memory", {"addr": hex(s["Warp_Req_X"]), "bytes": f"0x{x:04x}"})
            await b.call("emulator/write_memory", {"addr": hex(s["Warp_Req_Y"]), "bytes": f"0x{y:04x}"})
            await b.call("emulator/write_memory", {"addr": hex(s["Warp_Req_Flag"]), "bytes": "0x01"})
            for _ in range(240):
                await b.call("emulator/run_frames", {"frames": 1})
                r = await b.call("emulator/read_memory", {"addr": hex(s["Warp_Req_Flag"]), "len": 1})
                if int(unprefix(r["bytes"]), 16) == 0:
                    break
            else:
                raise CouldNotRun(f"the warp mailbox never acknowledged the warp to {name}")
            await b.call("emulator/run_frames", {"frames": settle})
            fails[name] = grade_stop(bake, await snapshot(b, s), f"WARP {name} ({x},{y})")
        return fails
    finally:
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--clip", required=True, help="clip act id (games/sonic4/data/clips/<id>)")
    ap.add_argument("--boot", type=int, default=BOOT_FRAMES)
    ap.add_argument("--settle", type=int, default=SETTLE_FRAMES)
    ap.add_argument("--no-warps", action="store_true", help="grade the boot screen only")
    a = ap.parse_args()
    rom = Path(a.rom).resolve()
    try:
        if not rom.is_file() or not Path(a.lst).is_file():
            raise CouldNotRun(f"{rom} or {a.lst} does not exist")
        bake = Bake(AEON / "games/sonic4/data/clips" / a.clip / "baked")
        warps = [] if a.no_warps else [
            (c["id"], c["dst_rect"]["x"] + c["dst_rect"]["w"] // 2,
             c["dst_rect"]["y"] + c["dst_rect"]["h"] // 2) for c in bake.clips]
        print(f"first_screen_fg_witness: {rom.name} crc {zlib.crc32(rom.read_bytes()):08x}, "
              f"clip {a.clip} ({bake.gw}x{bake.gh} sections, {bake.pages} pages), "
              f"boot {a.boot} frames, {len(warps)} warp(s)")
        inst = AetherInstance(str(rom), symbols=str(Path(a.lst).resolve()))
        try:
            sock = inst.start()
            fails = asyncio.run(drive(sock, bake, a.boot, a.settle, warps))
        finally:
            inst.reap()
    except (CouldNotRun, SpawnError, CartMismatch, OSError) as ex:
        print(f"COULD NOT RUN: {ex}")
        print("finished=1")
        return 2
    bad = {k: v for k, v in fails.items() if v}
    total = sum(fails.values())
    if bad:
        print(f"FAIL: {total} cell(s) differ from the bake at {len(bad)} of {len(fails)} stop(s): "
              + ", ".join(f"{k} {v}" for k, v in bad.items()))
        print("finished=1")
        return 1
    print(f"PASS: every graded cell matches the bake at all {len(fails)} stop(s)")
    print("finished=1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
