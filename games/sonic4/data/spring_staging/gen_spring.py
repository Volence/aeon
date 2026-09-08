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

WHAT THIS SCRIPT DOES: repacks 20 donor tiles down to 12 by dropping the 8 that
are entirely blank. S2's mappings declare padded pieces (a 4x2 plate whose top
tile row is empty, a 2x2 base whose bottom row is empty, a 2x4 coil whose bottom
row is empty); re-cutting each piece to its occupied rows costs nothing visually
and hands 8 tiles back to the VRAM map. The 12 that remain are the same 12 S3K's
own mappings reference — the sprite is identical, only the padding differs.

OUTPUT ORDER is VDP column-major within each piece, which is what the engine's
mapping DSL and the SAT both expect (a piece reads consecutive tiles from its
base, down each column then across):

    new  0.. 3   PLATE  4 wide x 1 tall   from donor 1, 3, 5, 7
    new  4.. 5   BASE   2 wide x 1 tall   from donor 8, 10
    new  6..11   COIL   2 wide x 3 tall   from donor 12,13,14, 16,17,18

Deterministic: same donor in, same 384 bytes out. Do not hand-edit the output.

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


def build(art: bytes) -> bytes:
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
    return b"".join(art[t * TILE:(t + 1) * TILE] for t in REPACK)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    blob = build(decompress(DONOR, NEMDEC))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "wb").write(blob)
    print(f"gen_spring: {a.out} — {len(blob)} bytes = {len(blob)//TILE} tiles "
          f"(from {DONOR_TILES} donor tiles, {len(DROPPED)} blank dropped)")


if __name__ == "__main__":
    main()
