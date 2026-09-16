#!/usr/bin/env python3
"""gen_tall_bg_test — emit the DEBUG-only background map that is TALLER than the plane.

REGIONS PART 2, STEP 5 (empyrean `docs/superpowers/specs/2026-09-14-regions-part-2-design.md`,
step-table row 5: "Author one: a 96-row test layout for the DEBUG shape only"). NOT the v1
regions design's step 5 — the two step schemes collide and v1's is long done.

WHY THIS FILE EXISTS AT ALL, which is the whole point of the step. Until a background map is
a DIFFERENT HEIGHT from the plane, steps 2 and 4 are machinery nothing can tell apart from the
code they replaced:

  * `Draw_BG_TileRow` (step 2) has no caller, because there is no row to stream.
  * The position clamp (step 4) derives its ceiling from `Region.rg_bg_span`, and every shipped
    row leaves that 0. Authoring the HONEST value would not help: the map IS the plane today, so
    an honest span is PLANE_B_SPAN = 512, whose ceiling is 512 - 224 = 288 — which is exactly
    `VSCROLL_BG_MAX`, the constant it replaced. There is NO authored value that separates the
    two clamps while the map is the plane's height. Step 4's own ledger says so and hands the
    problem here.

So this map is the discriminator, not a decoration: at 96 rows the span is 768 and the ceiling
becomes 768 - 224 = 544, a number the pre-step-4 code could not produce.

SHAPE
  96 rows x 64 cells x 2 B = 12288 B, ROW-MAJOR — blob[(row*64 + col)*2] — which is byte-for-byte
  the Plane B nametable's own VRAM order (regions part 2 step 2, option R). Rows 0..63 are the
  shipped act background verbatim; rows 64..95 repeat shipped rows 32..63, so every cell in the
  map names a tile the act's BG tile blob actually loads and nothing shows as garbage.

THE ROW MARKER, AND WHY A COPY WITHOUT ONE WOULD MAKE THE GATE VACUOUS
  The plane is a 64-row ring: map row m is always shown by plane row m mod 64. So the gate that
  reads the nametable and asks "which map row is plane row p holding" can only answer if map rows
  p and p+64 DIFFER. Rows 64..95 are copies of rows 32..63, and rows 0..31 of a sky-heavy
  background are full of identical blank cells — so without a marker, "the streamer moved the
  window" and "the streamer did nothing" would read IDENTICAL over much of the map. Cell 0 of
  every row therefore carries tile ($400 + row): BG tile index 1024 + row, palette 0, no flip,
  low priority. 1024 is BG_TILE_BASE_VRAM's tile and 1024+95 is inside the 448-tile BG run, so
  every marker is a real tile.

  The generator ASSERTS all 96 rows are pairwise distinct before writing. That assertion is what
  makes the gate's question answerable at every row, and it is checked here rather than assumed
  because it depends on the shipped art, which changes.

Usage:  python3 tools/gen_tall_bg_test.py [--check]
        --check  verify the committed output matches what this script would emit (no write)
"""

import argparse
import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

SRC = REPO / "games/sonic4/data/generated/ojz/act1/zone_bg.bin"
DST = REPO / "games/sonic4/data/generated/ojz/act1/zone_bg_tall_debug.bin"

# Geometry. Every one of these is also spelled in the .emp and pinned there against the engine's
# own constants; they are repeated here because this script runs outside the assembler and the
# two spellings are cross-checked by tools/test_bg_tall_map.py rather than trusted.
PLANE_H_CELLS = 64          # engine/system/constants.emp
PLANE_V_CELLS = 64          # engine/system/constants.emp — the ring's height, in rows
TALL_ROWS = 96              # the test map's height, in rows
ROW_BYTES = PLANE_H_CELLS * 2
BG_TILE_BASE = 1024         # BG_TILE_BASE_VRAM / 32 — the first BG tile index
BG_TILE_CAPACITY = 448      # ($B800 - $8000) / 32, the physical BG tile run


def build() -> bytes:
    src = SRC.read_bytes()
    want = PLANE_V_CELLS * ROW_BYTES
    if len(src) != want:
        sys.exit(f"gen_tall_bg_test: {SRC} is {len(src)} B, expected {want} "
                 f"({PLANE_V_CELLS} rows x {ROW_BYTES} B). The source blob's geometry moved; "
                 f"this generator's TALL_ROWS copy plan is written against 64 rows.")

    rows = [bytearray(src[r * ROW_BYTES:(r + 1) * ROW_BYTES]) for r in range(PLANE_V_CELLS)]

    # rows 64..95 repeat shipped rows 32..63 — real art, real tiles, no new tile budget.
    for r in range(PLANE_V_CELLS, TALL_ROWS):
        rows.append(bytearray(src[(r - 32) * ROW_BYTES:(r - 32 + 1) * ROW_BYTES]))

    # the row marker (see the header): cell 0 of row r becomes tile BG_TILE_BASE + r.
    for r, row in enumerate(rows):
        tile = BG_TILE_BASE + r
        if tile >= BG_TILE_BASE + BG_TILE_CAPACITY:
            sys.exit(f"gen_tall_bg_test: row {r}'s marker tile {tile} is past the BG tile run "
                     f"({BG_TILE_BASE}..{BG_TILE_BASE + BG_TILE_CAPACITY - 1}). A marker must be "
                     f"a tile the act actually loads, or the gate reads a cell that shows as the "
                     f"sprite attribute table.")
        row[0] = (tile >> 8) & 0xFF
        row[1] = tile & 0xFF

    # NON-VACUITY, asserted and not assumed: the gate reads plane row (m mod 64) and asks which
    # map row it holds. That question has an answer only if no two rows of this map are equal.
    seen = {}
    for r, row in enumerate(rows):
        key = bytes(row)
        if key in seen:
            sys.exit(f"gen_tall_bg_test: map rows {seen[key]} and {r} are byte-identical. The "
                     f"BG-TALL gate cannot tell which one a plane row is holding, so a streamer "
                     f"that never ran and one that ran correctly would read the SAME. The marker "
                     f"cell is supposed to make this impossible — check it is still being written.")
        seen[key] = r

    out = b"".join(bytes(r) for r in rows)
    assert len(out) == TALL_ROWS * ROW_BYTES, len(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the committed blob matches; write nothing")
    args = ap.parse_args()

    out = build()
    digest = hashlib.md5(out).hexdigest()

    if args.check:
        if not DST.is_file():
            print(f"MISSING: {DST} does not exist", file=sys.stderr)
            return 2
        have = DST.read_bytes()
        if have != out:
            print(f"STALE: {DST} is {len(have)} B md5 {hashlib.md5(have).hexdigest()}; "
                  f"this generator emits {len(out)} B md5 {digest}. "
                  f"Re-run: python3 tools/gen_tall_bg_test.py", file=sys.stderr)
            return 2
        print(f"gen_tall_bg_test --check: OK — {DST.name} {len(out)} B md5 {digest}, "
              f"{TALL_ROWS} rows, all pairwise distinct")
        return 0

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_bytes(out)
    print(f"gen_tall_bg_test: wrote {DST} — {len(out)} B md5 {digest}, {TALL_ROWS} rows "
          f"({PLANE_V_CELLS} shipped + {TALL_ROWS - PLANE_V_CELLS} repeated), all pairwise distinct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
