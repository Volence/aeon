#!/usr/bin/env python3
"""How much of a section's foreground the waterline tint actually reaches.

A MEASUREMENT, NOT A GATE. It has no pass/fail threshold and is wired into no
runner: any threshold here would be invented rather than derived, and the
question it answers ("does this look right?") is the owner's, not a build's.
Run it by hand.

WHY IT EXISTS. Section 7 of OJZ act 1 shows a hard vertical boundary at world
X 2944 with green terrain on one side and blue vertical stripes on the other.
The foreground is loading correctly -- tools/verify_level_bin.py's
verify_editor_bake_fidelity proves the generated tree carries the authored
nametable and art pixel for pixel. The boundary is an AUTHORED chunk-column
edge (sonic_hack level/layout/OJZ_1_sec7.bin, chunk row 2: the hand-built
terrain chunks 3D 3B 3D 3C 3C 3C 3B end at chunk column 7, where the generic
fill chunk 28 begins). What makes an ordinary authored edge read as a defect is
the waterline: `fx_tint_band` recolours THREE of the sixteen entries in one
CRAM line, and the two sides of that edge are painted out of almost disjoint
parts of the line. This tool measures that split so the fix can be chosen
against numbers instead of an impression.

Everything is derived from the tree: the tint band and its variant are parsed
out of games/sonic4/data/effects/ojz_effects.emp, the palette out of the
generated ojz_palette.bin, the geometry out of project.json.

  tools/waterline_tint_coverage.py [--section N] [--rows R0:R1] [--render DIR]

--rows is a nametable ROW range (8 px each) and defaults to the terrain band.
--render writes seam_dry.png / seam_wet.png: the same pixels with the tint off
and on. The renders MODEL the effect from the variant arithmetic offline; they
are not emulator captures.
"""
import argparse
import json
import os
import re
import struct
import sys
import zlib
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GEN = os.path.join(ROOT, "games", "sonic4", "data", "generated", "ojz", "act1")
EFFECTS = os.path.join(ROOT, "games", "sonic4", "data", "effects", "ojz_effects.emp")
PROJECT_JSON = os.path.join(ROOT, "project.json")

TILE_SIZE = 32
TILES_PER_CHUNK = 16        # 128 px chunk / 8 px tile
# engine/effects/palette.emp, Palette_LoadPal: "a1 = palette* (96 bytes = CRAM
# lines 1-3, NEVER line 0 -- the character's)". So ojz_palette.bin's file line L
# is CRAM line L+1, and a nametable word's palette bits index CRAM directly.
PAL_BYTES = 96
CRAM_FIRST_LINE = 1


def die(msg):
    print(f"waterline_tint_coverage: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_tint_band(src):
    """(pal_line, entry, count) of the fx_tint_band inside OJZ_WORLD_WATER_PROG."""
    m = re.search(r"OJZ_WORLD_WATER_PROG\s*=\s*compose\(\[(.*?)\n\]\)", src, re.S)
    if not m:
        die("OJZ_WORLD_WATER_PROG not found in ojz_effects.emp -- the waterline "
            "moved or was renamed; re-derive before trusting any number here")
    body = m.group(1)
    f = re.search(r"fx_tint_band\((.*?)\)", body, re.S)
    if not f:
        die("OJZ_WORLD_WATER_PROG carries no fx_tint_band -- the waterline is no "
            "longer a palette swap; this tool measures the wrong thing")
    args = f.group(1)
    out = {}
    for key in ("pal_line", "entry", "count"):
        k = re.search(rf"\b{key}\s*:\s*(\d+)", args)
        if not k:
            die(f"fx_tint_band has no literal `{key}` -- cannot derive the band")
        out[key] = int(k.group(1))
    return out["pal_line"], out["entry"], out["count"]


def parse_variant(src):
    """The pal_variant bound to slot 0 by OJZ_Preset_Sec7, as (shifts, biases)."""
    p = re.search(r"OJZ_Preset_Sec7:.*?variants:\s*\[\s*(\w+)", src, re.S)
    if not p:
        die("OJZ_Preset_Sec7's variants list not found -- cannot tell which "
            "variant the waterline's slot 0 carries")
    name = p.group(1)
    v = re.search(rf"^pub data {name}:\s*pal_variant\s*=\s*variant\((.*?)\)",
                  src, re.M | re.S)
    if not v:
        die(f"variant {name} is not declared as `variant(...)` in ojz_effects.emp")
    args = v.group(1)
    spec = {}
    for key in ("shift_r", "shift_g", "shift_b", "bias_r", "bias_g", "bias_b"):
        k = re.search(rf"\b{key}\s*:\s*(-?\d+)", args)
        spec[key] = int(k.group(1)) if k else 0
    return name, spec


def apply_variant(word, spec):
    """palette_dsl's variant_word model: clamp07((chan >> shift) + bias)."""
    def chan(v, shift, bias):
        r = (v >> shift) + bias
        return 0 if r < 0 else (7 if r > 7 else r)
    r = chan((word >> 1) & 7, spec["shift_r"], spec["bias_r"])
    g = chan((word >> 5) & 7, spec["shift_g"], spec["bias_g"])
    b = chan((word >> 9) & 7, spec["shift_b"], spec["bias_b"])
    return (b << 9) | (g << 5) | (r << 1)


def rgb(word):
    return (((word >> 1) & 7) * 36, ((word >> 5) & 7) * 36, ((word >> 9) & 7) * 36)


def write_png(path, img):
    h = len(img)
    w = len(img[0])
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in img)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", type=int, default=7)
    ap.add_argument("--rows", default="28:52", help="nametable row range R0:R1")
    ap.add_argument("--render", default=None, help="directory for seam_dry/wet.png")
    a = ap.parse_args()
    r0, r1 = (int(x) for x in a.rows.split(":"))

    src = open(EFFECTS).read()
    pal_line, entry, count = parse_tint_band(src)
    vname, spec = parse_variant(src)
    swapped = set(range(entry, entry + count))

    with open(PROJECT_JSON) as f:
        proj = json.load(f)
    zone = proj["zones"][0]
    act = zone["acts"][0]
    art = open(os.path.join(ROOT, zone["tileset"]), "rb").read()
    if not art or len(art) % TILE_SIZE:
        die(f"editor tileset is {len(art)} bytes -- not whole tiles")
    nt_path = os.path.join(ROOT, act["dataPath"], f"section_{a.section}.tiles.bin")
    if not os.path.isfile(nt_path):
        die(f"{nt_path} missing")
    raw = open(nt_path, "rb").read()
    grid = 256
    if len(raw) != grid * grid * 2:
        die(f"{os.path.basename(nt_path)} is {len(raw)} bytes, expected {grid*grid*2}")
    nt = struct.unpack(f">{grid*grid}H", raw)

    pf = open(os.path.join(GEN, "ojz_palette.bin"), "rb").read()
    if len(pf) != PAL_BYTES:
        die(f"ojz_palette.bin is {len(pf)} bytes, expected {PAL_BYTES} "
            f"(CRAM lines {CRAM_FIRST_LINE}..{CRAM_FIRST_LINE + PAL_BYTES//32 - 1})")
    pw = struct.unpack(f">{PAL_BYTES//2}H", pf)
    cram = [[0] * 16 for _ in range(4)]
    for line in range(PAL_BYTES // 32):
        for i in range(16):
            cram[CRAM_FIRST_LINE + line][i] = pw[line * 16 + i]
    wet = [row[:] for row in cram]
    for e in swapped:
        wet[pal_line][e] = apply_variant(cram[pal_line][e], spec)

    sec_origin_x = (a.section % act["gridWidth"]) * grid * 8
    print(f"section {a.section}  rows {r0}:{r1}  "
          f"tint: CRAM line {pal_line} entries {sorted(swapped)} via {vname} {spec}")
    print(f"  {'chunk col':>9} {'world X':>8} {'tinted px':>10}  top entries on the tinted line")
    for cc in range(grid // TILES_PER_CHUNK):
        hist = Counter()
        total = 0
        for r in range(r0, r1):
            for c in range(cc * TILES_PER_CHUNK, (cc + 1) * TILES_PER_CHUNK):
                word = nt[r * grid + c]
                idx = word & 0x07FF
                line = (word >> 13) & 3
                base = idx * TILE_SIZE
                if base + TILE_SIZE > len(art):
                    continue
                for byte in art[base:base + TILE_SIZE]:
                    for ci in (byte >> 4, byte & 0x0F):
                        total += 1
                        if line == pal_line:
                            hist[ci] += 1
        if not total:
            continue
        tinted = sum(n for ci, n in hist.items() if ci in swapped)
        top = ", ".join(f"{ci}:{100.0*n/total:.0f}%"
                        for ci, n in sorted(hist.items(), key=lambda kv: -kv[1])[:5])
        print(f"  {cc:>9} {sec_origin_x + cc*TILES_PER_CHUNK*8:>8} "
              f"{100.0*tinted/total:>9.1f}%  {top}")

    if a.render:
        os.makedirs(a.render, exist_ok=True)
        for name, pal in (("seam_dry.png", cram), ("seam_wet.png", wet)):
            img = [[(0, 0, 0)] * (grid * 8) for _ in range((r1 - r0) * 8)]
            for r in range(r0, r1):
                for c in range(grid):
                    word = nt[r * grid + c]
                    idx = word & 0x07FF
                    hf = (word >> 11) & 1
                    vf = (word >> 12) & 1
                    line = (word >> 13) & 3
                    base = idx * TILE_SIZE
                    for y in range(8):
                        sy = 7 - y if vf else y
                        for x in range(8):
                            sx = 7 - x if hf else x
                            o = base + sy * 4 + (sx >> 1)
                            ci = 0
                            if o < len(art):
                                ci = (art[o] >> 4) if not (sx & 1) else (art[o] & 0x0F)
                            img[(r - r0) * 8 + y][c * 8 + x] = (
                                (0, 0, 0) if ci == 0 else rgb(pal[line][ci]))
            write_png(os.path.join(a.render, name), img)
            print(f"  wrote {os.path.join(a.render, name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
