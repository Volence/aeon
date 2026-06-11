#!/usr/bin/env python3
"""Synthetic scroll test data generator (§4 Phase 1 visual verification).

Replaces OJZ tile art / palette / strip data with synthetic colored patterns
so the OJZ scroll test visibly proves that section streaming, column streaming,
camera tracking, and section teleport all work — without needing the §2
art pipeline.

Usage: python3 tools/synth_scroll_test_gen.py

Visual layout per column (rows 0-31):
  rows 0-7   sky (tile 0)
  row  8     rainbow band — color = col % 15 (1px-per-col scroll motion)
  rows 9-11  solid blue band
  row  12    chunk band — same color for 16 cols, changes every 16 cols
  rows 13-19 solid yellow band
  row  20    section band — solid color of section index (1-9)
  rows 21-23 solid magenta band
  row  24    fine ruler — every 4th col is white, others black
  rows 25-31 sky (tile 0)
Section parity flips palette line so teleport is unmistakable.
"""

import struct
import os

STRIP_TILE_HEIGHT = 32
NUM_SECTIONS = 9
SECTION_TILE_COLS = 256
NUM_TILES = 16
TILE_BYTES = 32

OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "generated", "ojz", "act1"
)


def solid_color_tile(color_index: int) -> bytes:
    nibble = color_index & 0xF
    byte_val = (nibble << 4) | nibble
    return bytes([byte_val] * TILE_BYTES)


def write_tile_art(path: str, n_tiles: int) -> None:
    with open(path, "wb") as f:
        for i in range(NUM_TILES):
            f.write(solid_color_tile(i))
        # pad to n_tiles so the existing DMA loader doesn't trip
        pad_tile = solid_color_tile(0)
        for _ in range(n_tiles - NUM_TILES):
            f.write(pad_tile)


def write_palette(path: str) -> None:
    pal = bytearray(128)
    base_colors = [
        0x0000,  # 0  transparent / sky
        0x000E,  # 1  red
        0x00E0,  # 2  green
        0x0E00,  # 3  blue
        0x00EE,  # 4  yellow
        0x0E0E,  # 5  magenta
        0x0EE0,  # 6  cyan
        0x0EEE,  # 7  white
        0x0006,  # 8  dark red
        0x0060,  # 9  dark green
        0x0600,  # 10 dark blue
        0x0066,  # 11 dark yellow
        0x0606,  # 12 dark magenta
        0x0660,  # 13 dark cyan
        0x0888,  # 14 mid grey
        0x0AAA,  # 15 light grey
    ]
    # Line 0: base
    for i, c in enumerate(base_colors):
        pal[i * 2 : i * 2 + 2] = struct.pack(">H", c)
    # Line 1: rotate by 8 (so section parity looks dramatically different)
    for i, _ in enumerate(base_colors):
        ci = (i + 8) % 16
        pal[32 + i * 2 : 32 + i * 2 + 2] = struct.pack(">H", base_colors[ci])
    # Lines 2-3: copies of line 0 (unused, but valid)
    for i, c in enumerate(base_colors):
        pal[64 + i * 2 : 64 + i * 2 + 2] = struct.pack(">H", c)
        pal[96 + i * 2 : 96 + i * 2 + 2] = struct.pack(">H", c)
    with open(path, "wb") as f:
        f.write(pal)


def nametable_word(tile_index: int, palette_line: int = 0) -> int:
    return ((palette_line & 3) << 13) | (tile_index & 0x7FF)


def generate_strip(col: int, section_index: int) -> list[int]:
    pal = section_index & 1  # parity → flips palette line
    rainbow = (col % 15) + 1
    chunk = (col // 16 % 15) + 1
    section_color = (section_index % 15) + 1
    ruler = 7 if (col % 4 == 0) else 0  # tile 7 = white marker, tile 0 = black

    rows = []
    for row in range(STRIP_TILE_HEIGHT):
        if row < 8:
            t = 0
        elif row == 8:
            t = rainbow
        elif row < 12:
            t = 3  # blue band
        elif row == 12:
            t = chunk
        elif row < 20:
            t = 4  # yellow band
        elif row == 20:
            t = section_color
        elif row < 24:
            t = 5  # magenta band
        elif row == 24:
            t = ruler
        else:
            t = 0
        rows.append(nametable_word(t, palette_line=pal))
    return rows


def write_strips(path: str, section_index: int) -> None:
    with open(path, "wb") as f:
        for col in range(SECTION_TILE_COLS):
            for word in generate_strip(col, section_index):
                f.write(struct.pack(">H", word))


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    # 322 tiles — historic OJZ raw-export count the test's DMA sizes were built around
    write_tile_art(os.path.join(OUT_DIR, "ojz_tiles.bin"), n_tiles=322)
    write_palette(os.path.join(OUT_DIR, "ojz_palette.bin"))
    for sec in range(NUM_SECTIONS):
        write_strips(os.path.join(OUT_DIR, f"sec{sec}_strips_a.bin"), sec)
        # Plane B placeholder
        zero_size = SECTION_TILE_COLS * STRIP_TILE_HEIGHT * 2
        with open(os.path.join(OUT_DIR, f"sec{sec}_strips_b.bin"), "wb") as f:
            f.write(b"\x00" * zero_size)
    print(f"Synthetic data written to {OUT_DIR}")
    print("  tiles 0-15 used (solid colors); palette line flips per section parity")
    print("  rows 8/12/20/24 carry per-column / per-chunk / per-section / ruler info")


if __name__ == "__main__":
    main()
