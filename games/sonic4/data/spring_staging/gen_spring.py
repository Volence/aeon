#!/usr/bin/env python3
"""Generate the vertical spring's art blob from the sonic_hack donor.

DONOR: sonic_hack/art/nemesis/Vertical spring.bin — Nemesis-compressed, 20 tiles
after decompression. Decompressed with sonic_hack/tools/nemdec (clownnemesis).

WHY THIS DONOR AND NOT skdisasm's. The blob's pixel indices are {0,1,6,7,8,9,C,D},
which against CRAM line 0 (art/palettes/SonicAndTails.bin, the line this game
already loads for the player and the backdrop) read as:

    0 transparent   1 near-black outline   6 white        7 light grey
    8 grey-blue     9 grey                 C bright red   D dark red

i.e. a correct red spring at ZERO palette cost. That is not luck: the donor object
declares `vram_art(VRAM_VrtclSprng,0,0)` — palette line 0 — in Spring__UpData
(sonic_hack/code/objects/Spring.asm), so S2 draws its spring on the player line
too. skdisasm's Vertical Spring.bin uses {0,1,5,6,7,8,9,C,D,E,F}; against OUR line
0 the extra indices are blue ($5) and orange ($E/$F), so it would need a lossy
re-index. Same reasoning as compose_ring.py's donor choice.

THE OUTPUT DRAWS {0,1,6,7,8,C,D} — the donor's index 9 is moved onto 8 (INDEX_REMAP
below). Line 0 is the PER-CHARACTER line, and 9 is one of its four character-specific
slots: $0444 grey under Sonic and Tails, $0080 green under Knuckles. So the donor's
index-9 coil mid-tone recoloured on a character swap. The owner ruled the spring gives
that grey up (docs/decisions.jsonl SPRING-PAL-IDX9, `drop-grey`) and picked the
LIGHTER neighbour, index 8 ($0866, identical under every character), over the darker
index 1 ($0222). The coil therefore reads a little lighter and flatter than S2's.

WHAT THIS SCRIPT DOES: repacks 20 donor tiles down to 12 by dropping the 8 that
are entirely blank, then applies INDEX_REMAP to every pixel of both sheets. S2's mappings declare padded pieces (a 4x2 plate whose top
tile row is empty, a 2x2 base whose bottom row is empty, a 2x4 coil whose bottom
row is empty); re-cutting each piece to its occupied rows costs nothing visually
and hands 8 tiles back to the VRAM map. The 12 that remain are the same 12 S3K's
own mappings reference — the shape is identical, only the padding differs (and the
coil's one grey, per INDEX_REMAP).

OUTPUT ORDER is VDP column-major within each piece, which is what the engine's
mapping DSL and the SAT both expect (a piece reads consecutive tiles from its
base, down each column then across):

    new  0.. 3   PLATE  4 wide x 1 tall   from Vertical donor 1, 3, 5, 7
    new  4.. 5   BASE   2 wide x 1 tall   from Vertical donor 8, 10
    new  6..11   COIL   2 wide x 3 tall   from Vertical donor 12,13,14, 16,17,18
    new 12..15   HPLATE 1 wide x 4 tall   Horizontal donor 0..3   (verbatim)
    new 16..17   HBASE  1 wide x 2 tall   Horizontal donor 4..5
    new 18..23   HCOIL  3 wide x 2 tall   Horizontal donor 6..11

Deterministic: same donor in, same 768 bytes out. Do not hand-edit the output.

Usage:  python3 games/sonic4/data/spring_staging/gen_spring.py [--out PATH]
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(AEON, "tools"))
from suite_paths import suite_path  # noqa: E402

SONIC_HACK = os.environ.get("AEON_SONIC_HACK_DIR", str(suite_path("sonic_hack")))
DONOR = os.path.join(SONIC_HACK, "art", "nemesis", "Vertical spring.bin")
DONOR_H = os.path.join(SONIC_HACK, "art", "nemesis", "Horizontal spring.bin")
NEMDEC = os.path.join(SONIC_HACK, "tools", "nemdec")
DEFAULT_OUT = os.path.join(AEON, "games", "sonic4", "data", "generated",
                           "spring", "art_spring.bin")

TILE = 32
DONOR_TILES = 20
# The repack, in output order. Each entry is a donor tile index.
PLATE = [1, 3, 5, 7]            # 4 wide x 1 tall
BASE  = [8, 10]                 # 2 wide x 1 tall
COIL  = [12, 13, 14, 16, 17, 18]  # 2 wide x 3 tall (column-major)
REPACK = PLATE + BASE + COIL
# The donor tiles the repack drops, asserted blank below rather than assumed.
DROPPED = [0, 2, 4, 6, 9, 11, 15, 19]

# --- the HORIZONTAL sheet, appended after the vertical one ------------------
# A SEPARATE DONOR FILE AND A SEPARATE SHEET, not a rotation of the vertical one.
# The side spring's plate is a VERTICAL BAR (1 cell wide, 4 tall) with its coil
# running sideways; nothing about the flat 4x1 plate can be turned into it. The
# donor keeps them apart too — VRAM_VrtclSprng = $460 and VRAM_HrzntlSprng = $474
# are different blocks, and Spring__UpData / Spring__SideData name different art
# (sonic_hack/VRAM_Layout.asm:77-78, code/objects/Spring.asm:127/139).
#
# NO REPACK HERE: all 12 donor tiles are non-blank and all 12 are referenced by
# mapping frames 3/4/5, so the sheet is copied verbatim and the frames address it
# by the donor's own tile numbers (offset by the vertical sheet's 12).
HORIZ_TILES = 12
# LEFT vs RIGHT is the renderer's X-flip of these same 12 tiles, and DOWN is the
# renderer's Y-flip of the vertical ones — engine/objects/sprites.emp mirrors a
# piece's OFFSETS as well as its tiles (y_term/x_term `neg` then subtract the
# piece's own extent), so a flipped multi-piece frame lands where it should.

# --- the owner's look ruling: the coil mid-tone leaves line-0 index 9 -------
# Donor index -> output index, applied to every pixel of BOTH sheets (the side
# spring's coil uses the same grey). 9 is character-specific on line 0 ($0444 as
# Sonic/Tails, $0080 as Knuckles — games/sonic4/data/characters/knuckles_data.emp
# rules the set 2/3/5/9), so drawing through it recoloured the coil on a swap.
# docs/decisions.jsonl SPRING-PAL-IDX9: `drop-grey`, and the shade is the LIGHTER
# neighbour, 8 ($0866), chosen by the owner over the darker 1 ($0222). Changing the
# 8 is changing how the spring looks for every character — an eye call, not ours.
# games/sonic4/objects/test_solid.emp refuses at build time any spring pixel on a
# slot the character palettes disagree about, so this cannot drift back onto 9.
INDEX_REMAP = {9: 8}


def remap_indices(blob: bytes, remap: dict) -> bytes:
    """Relabel 4bpp pixel indices (2 px/byte, both nibbles) through `remap`."""
    if set(remap) & set(remap.values()):
        sys.exit(f"gen_spring: INDEX_REMAP {remap} maps onto an index it also moves — "
                 f"the result would depend on application order")
    lut = [remap.get(i, i) for i in range(16)]
    return bytes((lut[b >> 4] << 4) | lut[b & 0x0F] for b in blob)


def decompress(donor: str, nemdec: str) -> bytes:
    for p, what in ((donor, "donor art"), (nemdec, "nemdec decompressor")):
        if not os.path.exists(p):
            sys.exit(f"gen_spring: {what} not found: {p}\n"
                     f"  set AEON_SONIC_HACK_DIR, or install the donor tree beside this checkout")
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "vspring.bin")
        r = subprocess.run([nemdec, "-d", donor, out],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"gen_spring: nemdec failed ({r.returncode}): {r.stderr.strip()}")
        return open(out, "rb").read()


def build(art: bytes, art_h: bytes) -> bytes:
    if len(art) != DONOR_TILES * TILE:
        sys.exit(f"gen_spring: donor decompressed to {len(art)} bytes, "
                 f"expected {DONOR_TILES * TILE} ({DONOR_TILES} tiles)")
    # The 8 dropped tiles must be EMPTY. If a donor revision put pixels in one,
    # this repack would silently delete part of the sprite — refuse instead.
    for t in DROPPED:
        if art[t * TILE:(t + 1) * TILE] != b"\0" * TILE:
            sys.exit(f"gen_spring: donor tile {t} is NOT blank, but the repack drops it. "
                     f"The donor's piece padding changed — re-derive PLATE/BASE/COIL "
                     f"from mappings/sprite/Spring 1.asm frames 0/1/2 before regenerating.")
    if sorted(REPACK + DROPPED) != list(range(DONOR_TILES)):
        sys.exit("gen_spring: REPACK + DROPPED must partition the donor's tiles exactly")
    if len(art_h) != HORIZ_TILES * TILE:
        sys.exit(f"gen_spring: the horizontal donor decompressed to {len(art_h)} bytes, "
                 f"expected {HORIZ_TILES * TILE} ({HORIZ_TILES} tiles)")
    for t in range(HORIZ_TILES):
        if art_h[t * TILE:(t + 1) * TILE] == b"\0" * TILE:
            sys.exit(f"gen_spring: horizontal donor tile {t} is blank; frames 3/4/5 "
                     f"reference all {HORIZ_TILES}, so a blank one means the donor changed")
    blob = remap_indices(b"".join(art[t * TILE:(t + 1) * TILE] for t in REPACK) + art_h,
                         INDEX_REMAP)
    left = sorted({n for b in blob for n in (b >> 4, b & 0x0F)} & set(INDEX_REMAP))
    if left:
        sys.exit(f"gen_spring: output still draws remapped-away index(es) {left}")
    return blob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    blob = build(decompress(DONOR, NEMDEC), decompress(DONOR_H, NEMDEC))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "wb").write(blob)
    print(f"gen_spring: {a.out} — {len(blob)} bytes = {len(blob)//TILE} tiles "
          f"= {len(REPACK)} vertical (from {DONOR_TILES}, {len(DROPPED)} blank dropped) "
          f"+ {HORIZ_TILES} horizontal (verbatim), indices remapped {INDEX_REMAP}")


if __name__ == "__main__":
    main()
