#!/usr/bin/env python3
"""waterline_stamp_witness — is the waterline stamp ACTUALLY IN THE SPRITE TABLE, and does
it stay there?

EFFECTS-W1 item 9d, the on-screen half. tools/waterline_art_witness.py answers "are the
right BYTES at VRAM_WATERLINE_STRIPS"; this answers the question that one cannot: "is
anything on screen POINTING AT THEM". They are different questions and the first was
answered POSITIVE 12/12 for a day while the second's answer was NO.

WHY THIS EXISTS, WHICH IS A DEFECT AND NOT A HYPOTHETICAL
=========================================================
The stamp's first shape built the object in the effects lab's hotkey and retired it from
the per-frame poller whenever `Waterline_Art_Row` read 0. Both run inside one proc, in
this order:

    Debug_LabCycleHotkey      the press: installed the scene AND built the object
    Debug_TierTags_Update     the honesty arm: retired it if the row read 0
    Parallax_Update           <- THIS is what publishes Waterline_Art_Row
    Waterline_Art_Update

so the arm read the PREVIOUS scene's cell and cleared the slot on the same frame the press
built it, every press, forever. All four shapes built green, 2,476 tests passed, the art
witness passed, and the lint arm that checks the row names the right scene passed. Not one
of them can see whether the object SURVIVES THE FRAME IT IS BUILT IN. That is what this
measures, and it measures it in the only place the answer is visible from outside the
engine: the VDP's sprite attribute table.

WHAT IT READS, AND WHY THE SAT RATHER THAN PIXELS
=================================================
A screenshot is not available to this lane and would not be better if it were: the strips
are drawn through palette line 1, so their PIXELS depend on whatever that line holds, and a
pixel test would fail for a palette reason and be reported as a stamp failure. The SAT is
the machine's own statement of what it is drawing: an entry naming tile
VRAM_WATERLINE_STRIPS/32 at a 4x2 size, on screen, IS the stamp. Nothing else in either
game names that tile.

THREE ARMS, AND ALL THREE ARE REQUIRED
======================================
  1. POSITIVE / PERSISTS — with the lab cursor on the WLINE row and the remapping scene
     installed, an SAT entry names the run at the derived size, on screen, on EVERY one of
     N consecutive sampled frames. The persistence is the arm, not the first hit: the
     defect above produced a slot that was written and cleared inside one frame, so a
     single sample taken at the right moment could have said yes.
  2. CONTROL / RETIRES ON THE CURSOR — move the cursor to a non-WLINE row and the entry is
     gone within a few frames. Without this arm an object built once and never retired
     satisfies arm 1, and "the stamp works" would be reported for a stamp that can never
     be turned off — which is the staleness failure the whole readout family exists to
     remove.
  3. HONESTY / RETIRES ON THE ENGINE — put the cursor back on WLINE but install a scene
     with no ladder, so `Waterline_Art_Row` goes 0 and the eight tiles freeze. The entry
     must go. That is the section-crossing case, and it is the half no press can reach.

EVERY EXPECTATION IS DERIVED. The tile index comes from games/sonic4/vram.toml's
`waterline_strips` base; the sprite size nibble from WATERLINE_H (read out of
engine/level/parallax_dsl.emp) through the same geometry the engine derives it from
(cells_h = H/8, cells_w = tiles/cells_h, packed (w-1)<<2 | (h-1)); the WLINE row index from
`.lab_index`'s own rows; the on-screen bound from the VDP's +128 sprite offset and the
screen size. No number in this file is copied from the subject.

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every failure to resolve a symbol, parse a
constant or match the served ROM against the file on disk REFUSES with exit 2 rather than
reporting a verdict.

HOW TO RUN IT

    DEBUG=1 ./build.sh                        # s4.debug.bin + s4.debug.lst
    python3 tools/waterline_stamp_witness.py  # defaults to s4.debug.bin

It drives NO input. The cursor and the arming latch are written directly, the way
tools/waterline_art_witness.py writes the parallax config — a held-chord fixture would
have to survive the replay gate and would desync anything downstream.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import waterline_art_gen as model                          # noqa: E402
from suite_paths import add_client_path                    # noqa: E402

add_client_path()
from aether import BusClient                               # noqa: E402
from aether_instance import AetherInstance                 # noqa: E402

LAB = "games/sonic4/test/ojz_scroll_test.emp"
DSL = "engine/level/parallax_dsl.emp"
TOML = "games/sonic4/vram.toml"

SAT_ENTRIES = 80            # the VDP's H40 sprite limit; the table is 80 x 8 bytes
SAT_ENTRY = 8
VDP_SPRITE_OFFSET = 128     # both axes; engine/objects/sprites.emp's `.screen_pos` arm
SCREEN_W, SCREEN_H = 320, 224


class Refused(RuntimeError):
    pass


def refuse(msg: str) -> Refused:
    return Refused(msg)


def _hex(s) -> int:
    s = str(s)
    return int(s[2:] if s[:2].lower() == "0x" else (s[1:] if s[:1] == "$" else s), 16)


async def lookup(c: BusClient, name: str) -> int:
    try:
        r = await c.call("emulator/lookup_symbol", {"name": name})
    except Exception as e:
        raise refuse(f"symbol {name!r} does not resolve against the loaded listing: {e}")
    return _hex(r["addr"])


async def write(c: BusClient, addr: int, value: int, width: int) -> None:
    await c.call("emulator/write_memory",
                 {"addr": hex(addr), "value": value, "width": width})


async def read_vram(c: BusClient, addr: int, n: int) -> bytes:
    r = await c.call("emulator/read_vram", {"addr": hex(addr), "len": n})
    raw = str(r["bytes"])
    raw = raw[2:] if raw[:2].lower() == "0x" else raw
    got = bytes.fromhex(raw)
    if len(got) != n:
        raise refuse(f"read_vram(${addr:04X}, {n}) returned {len(got)} B")
    return got


# ------------------------------------------------------------------ derivations


def _read(rel: str) -> str:
    p = os.path.join(REPO, rel)
    if not os.path.isfile(p):
        raise refuse(f"{rel} does not exist — every expectation below is derived from the "
                     f"sources, so a missing one must refuse rather than pass")
    return open(p, encoding="utf-8").read()


def region_base_tile(name: str) -> int:
    import tomllib
    with open(os.path.join(REPO, TOML), "rb") as fh:
        doc = tomllib.load(fh)
    for r in doc.get("region", []):
        if r.get("name") == name:
            return int(r["base"])
    raise refuse(f"{TOML} declares no region {name!r}")


def dsl_H() -> int:
    """WATERLINE_H through its alias, out of the engine source. Never typed."""
    text = _read(DSL)
    m = re.search(r"^pub const WATERLINE_H\s*=\s*([A-Za-z0-9_]+)", text, re.M)
    if not m:
        raise refuse(f"WATERLINE_H is not declared in {DSL}")
    tok = m.group(1)
    if tok.isdigit():
        return int(tok)
    m2 = re.search(r"^pub const " + tok + r"\s*=\s*(\d+)", text, re.M)
    if not m2:
        raise refuse(f"WATERLINE_H = {tok}, which is not a literal const in {DSL}")
    return int(m2.group(1))


def stamp_geometry(H: int) -> tuple[int, int, int]:
    """(cells_w, cells_h, VDP size nibble) — the SAME derivation the engine makes.

    A tile column is 8 px tall, so the strip is H/8 cells tall; the run holds
    `tiles_for_height(H)` tiles in all, so it is that many cells wide. The VDP packs
    (w-1) in bits 3:2 and (h-1) in bits 1:0.
    """
    tiles = model.tiles_for_height(H)
    cells_h = H // 8
    if cells_h <= 0 or tiles % cells_h:
        raise refuse(f"H = {H} gives {tiles} tiles over {cells_h} rows, which is not a "
                     f"rectangle — this witness cannot say what shape to look for")
    cells_w = tiles // cells_h
    if not (1 <= cells_w <= 4 and 1 <= cells_h <= 4):
        raise refuse(f"the stamp would be {cells_w} x {cells_h} cells and a VDP piece is "
                     f"at most 4 x 4 — at H = {H} it is no longer ONE piece and this "
                     f"witness's one-entry search is the wrong question")
    return cells_w, cells_h, ((cells_w - 1) << 2) | (cells_h - 1)


def lab_rows() -> list[list[str]]:
    src = _read(LAB)
    m = re.search(r"^\s*(?:export\s+)?\.lab_index:\s*$", src, re.M)
    if m is None:
        raise refuse(f"{LAB}: no `.lab_index:` label — the WLINE row's index is derived "
                     "from that table and cannot be guessed")
    rest = src[m.end():]
    stop = re.search(r"(?=^\s*(?:export\s+)?[.\w]+:\s*$|^\s*\}\s*$)", rest, re.M)
    body = rest[:stop.start()] if stop else rest
    rows = []
    for line in re.findall(r"^\s*dc\.b\s+([^/\n]+?)\s*(?://.*)?$", body, re.M):
        rows.append([t.strip() for t in line.split(",") if t.strip()])
    if not rows:
        raise refuse(f"{LAB}: `.lab_index:` holds no rows")
    return rows


def wline_row_index() -> int:
    rows = lab_rows()
    hits = [i for i, r in enumerate(rows) if r and r[0] == "LAB_KIND_WLINE"]
    if len(hits) != 1:
        raise refuse(f"{LAB}: expected exactly one LAB_KIND_WLINE row in `.lab_index`, "
                     f"found {hits or 'none'} — tools/test_lab_index_lint.py owns that "
                     "failure; this witness cannot pick one")
    return hits[0]


def a_non_wline_row_index(wline: int) -> int:
    """Any SCENE row — the control moves the cursor to one and nothing else changes."""
    rows = lab_rows()
    for i, r in enumerate(rows):
        if i != wline and r and r[0] == "LAB_KIND_SCENE":
            return i
    raise refuse(f"{LAB}: found no LAB_KIND_SCENE row to use as the control cursor")


# ------------------------------------------------------------------ the search


def find_stamp(sat: bytes, tile: int, size: int) -> dict | None:
    """The SAT entry drawing the waterline run, or None.

    Matched on BOTH the base tile and the size nibble, because either alone is weak: the
    tile field alone would match a hypothetical one-cell debug object based there, and the
    size alone matches every 4x2 sprite in the game.
    """
    for i in range(SAT_ENTRIES):
        e = sat[i * SAT_ENTRY:(i + 1) * SAT_ENTRY]
        y = int.from_bytes(e[0:2], "big") & 0x03FF
        sz = e[2] & 0x0F
        attrs = int.from_bytes(e[4:6], "big")
        x = int.from_bytes(e[6:8], "big") & 0x01FF
        if (attrs & 0x07FF) == tile and sz == size:
            return {"slot": i, "x": x, "y": y, "size": f"${sz:02X}",
                    "attrs": f"${attrs:04X}",
                    "screen_x": x - VDP_SPRITE_OFFSET, "screen_y": y - VDP_SPRITE_OFFSET,
                    "palette": (attrs >> 13) & 3, "priority": (attrs >> 15) & 1}
    return None


async def sample(c: BusClient, sat_at: int, tile: int, size: int) -> dict | None:
    sat = await read_vram(c, sat_at, SAT_ENTRIES * SAT_ENTRY)
    return find_stamp(sat, tile, size)


async def run(a) -> int:
    rom_path = os.path.abspath(a.rom)
    lst = os.path.abspath(a.lst) if a.lst else rom_path[:-4] + ".lst"
    rom = open(rom_path, "rb").read()

    H = dsl_H()
    cells_w, cells_h, size = stamp_geometry(H)
    tile = region_base_tile("waterline_strips")
    wline = wline_row_index()
    control = a_non_wline_row_index(wline)
    print(f"  H = {H}; the run is {model.tiles_for_height(H)} tiles = {cells_w} x "
          f"{cells_h} cells, VDP size nibble ${size:02X}, base tile {tile} (${tile:03X})")
    print(f"  the WLINE row is lab index {wline}; the control cursor is {control}")

    inst = AetherInstance(rom=rom_path, symbols=lst)
    sock = await asyncio.to_thread(inst.start)
    out = {"rom": rom_path, "rom_bytes": len(rom), "H": H, "tile": tile,
           "size": size, "wline_row": wline, "control_row": control}
    try:
        c = BusClient(socket_path=sock, client_id="wlstampw",
                      client_name="waterline_stamp_witness")
        await c.connect()
        st = await c.call("emulator/status", {})
        # ⚠ ROM IDENTITY FIRST. A stale shim serves a previous freeze behind a
        # correct-looking romPath, and every arm below would then describe another build.
        if int(st["romBytes"]) != len(rom):
            raise refuse(f"server serves {st['romBytes']} bytes, {rom_path} is {len(rom)} "
                         f"— a different ROM")
        print(f"  server romPath={st['romPath']} romBytes={st['romBytes']} (matches disk)")
        out["server_rom_path"] = st["romPath"]

        sym = {n: await lookup(c, n) for n in
               ("Debug_Lab_Index", "Debug_Tags_Armed", "Waterline_Art_Row",
                "Parallax_Current_Config", "Parallax_Target_Config",
                "Parallax_Transition_Frames")}
        sat_at = region_base_tile("sprite_table") * 32
        print(f"  sprite table at ${sat_at:04X}, derived from {TOML}")
        out["symbols"] = {k: f"${v:06X}" for k, v in sym.items()}
        out["sat"] = f"${sat_at:04X}"

        await c.call("emulator/run_frames", {"frames": a.settle})

        async def install(config_name: str) -> None:
            cfg = await lookup(c, config_name)
            for s in ("Parallax_Current_Config", "Parallax_Target_Config"):
                await write(c, sym[s], cfg, 4)
            await write(c, sym["Parallax_Transition_Frames"], 0, 1)

        async def put_cursor(row: int) -> None:
            await write(c, sym["Debug_Lab_Index"], row, 1)
            await write(c, sym["Debug_Tags_Armed"], 1, 1)

        # ---- ARM 1: POSITIVE / PERSISTS ------------------------------------
        await install(a.config)
        await put_cursor(wline)
        await c.call("emulator/run_frames", {"frames": a.install_settle})
        hits, misses, first = [], [], None
        for _ in range(a.samples):
            got = await sample(c, sat_at, tile, size)
            if got is None:
                misses.append(int((await c.call("emulator/status", {}))["frame"]))
            else:
                hits.append(got)
                first = first or got
            await c.call("emulator/run_frames", {"frames": a.stride})
        out["positive"] = {"samples": a.samples, "hits": len(hits),
                           "miss_frames": misses, "entry": first}
        print(f"  POSITIVE  {len(hits)}/{a.samples} sampled frames carry an SAT entry "
              f"naming tile {tile} at ${size:02X}")
        if first:
            print(f"            slot {first['slot']}, screen ({first['screen_x']}, "
                  f"{first['screen_y']}), palette {first['palette']}, "
                  f"priority {first['priority']}, attrs {first['attrs']}")

        onscreen = None
        if first:
            onscreen = (0 <= first["screen_x"] <= SCREEN_W - cells_w * 8
                        and 0 <= first["screen_y"] <= SCREEN_H - cells_h * 8)
            out["positive"]["on_screen"] = onscreen
            if not onscreen:
                print(f"  ⚠ THE ENTRY IS OFF SCREEN: ({first['screen_x']}, "
                      f"{first['screen_y']}) with a {cells_w * 8} x {cells_h * 8} px "
                      f"piece does not fit inside {SCREEN_W} x {SCREEN_H}. An SAT entry "
                      "nobody can see is the same defect as no entry at all")

        # ---- ARM 2: CONTROL / RETIRES ON THE CURSOR ------------------------
        await put_cursor(control)
        await c.call("emulator/run_frames", {"frames": a.retire_frames})
        after_cursor = await sample(c, sat_at, tile, size)
        out["control_cursor"] = {"row": control, "entry": after_cursor}
        print(f"  CONTROL   cursor -> row {control}: entry is "
              f"{'STILL THERE' if after_cursor else 'gone'} after {a.retire_frames} frames")

        # ---- ARM 3: HONESTY / RETIRES ON THE ENGINE ------------------------
        await put_cursor(wline)
        await c.call("emulator/run_frames", {"frames": a.retire_frames})
        back = await sample(c, sat_at, tile, size)
        await install(a.plain_config)
        await c.call("emulator/run_frames", {"frames": a.retire_frames})
        row_now = int.from_bytes(
            bytes.fromhex(str((await c.call("emulator/read_memory",
                                            {"addr": hex(sym["Waterline_Art_Row"]),
                                             "len": 4}))["bytes"]).replace("0x", "")),
            "big")
        after_engine = await sample(c, sat_at, tile, size)
        out["honesty"] = {"rebuilt_on_return": bool(back),
                          "plain_config": a.plain_config,
                          "waterline_art_row": f"${row_now:08X}",
                          "entry": after_engine}
        print(f"  HONESTY   cursor back on WLINE: entry "
              f"{'rebuilt' if back else 'DID NOT COME BACK'}; then {a.plain_config} "
              f"installed -> Waterline_Art_Row = ${row_now:08X}, entry is "
              f"{'STILL THERE' if after_engine else 'gone'}")

        ok = (len(hits) == a.samples and onscreen and after_cursor is None
              and back is not None and row_now == 0 and after_engine is None)
        if row_now != 0:
            print("  ⚠ THE HONESTY ARM DID NOT SEPARATE: installing "
                  f"{a.plain_config} left Waterline_Art_Row non-zero, so the arm never "
                  "tested what it exists to test. Name a scene with no `rowRemap:`")
        out["verdict"] = "PASS" if ok else "FAIL"
        print(f"  VERDICT {out['verdict']}")
        json.dump(out, open(a.out, "w"), indent=1)
        print(f"  wrote {a.out}")
        return 0 if ok else 1
    finally:
        await asyncio.to_thread(inst.reap)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--lst", default=None)
    ap.add_argument("--config", default="ParallaxConfig_OJZ_Underwater",
                    help="the scene whose layer carries the rowRemap ladder")
    ap.add_argument("--plain-config", default="ParallaxConfig_OJZ_Default",
                    help="a scene with NO ladder — the honesty arm's contaminant")
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--install-settle", type=int, default=30)
    ap.add_argument("--retire-frames", type=int, default=10)
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--stride", type=int, default=6)
    ap.add_argument("--out", default=os.path.join(REPO, "waterline_stamp_witness.json"))
    a = ap.parse_args()
    try:
        return asyncio.run(run(a))
    except Refused as e:
        print(f"REFUSED: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
