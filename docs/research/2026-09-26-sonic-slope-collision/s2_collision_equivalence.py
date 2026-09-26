#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate): is the clip act's collision Sonic 2's collision, PIXEL FOR PIXEL?

SONIC-SLOPE-COLLISION hypothesis H1 ("the clip's collision import is wrong: heights, angles,
index mapping, the wrong one of S2's two paths, solidity bits, chunk flips"). The converter's
own round trip (tools/s2_zone_convert.py) compares the tree against a second derivation of
the SAME word format, through collision_pipeline's shared definitions. This compares against
Sonic 2's RUNTIME semantics instead, written here from s2.asm and nothing else:

  S2 side (s2.asm Find_Tile :42894, FindFloor :42942, raw donor files):
    chunk entry = chunks[layout[y>>7][x>>7]][((y & $70) >> 4) * 8 + ((x & $70) >> 4)]
    block id = entry & $3FF (0 -> air); solidity: path 0 top = bit 12 ($C), lrb = bit 13,
    path 1 top = bit 14 ($E), lrb = bit 15; shape = ColP[id] (path 0) / ColS[id] (path 1),
    0 -> air; angle = ColCurveMap[shape], X flip (bit 10): neg, Y flip (bit 11):
    +$40 / neg / -$40; column = x & 15, X flip: not; height = ColArrayVertical[shape*16 +
    column], sign-extended, Y flip: neg. A floor-class pixel at row r = y & 15 is solid iff
    h > 0 and r + h >= 16, or h < 0 and r + h < 0 (loc_1E85E's bpl).
  aeon side: the clip act's per-plane cell words from tools/clip_manifest.collision_grids
    (what the bake consumes) for plane A and plane B, both 8-px cells of every 16-px block,
    read through the S2 base bank the manifest names (heightmaps.bin / angles.bin) and
    collision_pipeline's flip helpers, with the same pixel rule.

Every block of both clip rectangles is compared on: per-pixel floor-class solidity (256 px),
LRB class, and the angle byte, for path 0 <-> plane A and path 1 <-> plane B. Prints totals.

    python3 docs/research/2026-09-26-sonic-slope-collision/s2_collision_equivalence.py
"""
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import clip_manifest as CM                                 # noqa: E402
import collision_pipeline as CP                            # noqa: E402
import s2_donor                                            # noqa: E402

MANIFEST = REPO / "games/sonic4/data/clips/s2_ehz_cpz/clips.json"
#: CONTROL mutations of the S2 side, to show the comparison can fail: `noxflip` ignores
#: bit 10, `noyflip` ignores bit 11, `swappath` compares path 0 against plane B and
#: path 1 against plane A. Each must print a nonzero difference.
MUTATE = sys.argv[1] if len(sys.argv) > 1 else ""


def s8(b):
    return b - 256 if b >= 128 else b


def pixels(heights16):
    """16x16 bool: floor-class solid pixels for a 16-column signed height profile."""
    out = np.zeros((16, 16), dtype=bool)
    for c in range(16):
        h = heights16[c]
        for r in range(16):
            out[r, c] = (h > 0 and r + h >= 16) or (h < 0 and r + h < 0)
    return out


def s2_block(zone, x, y, path):
    """Sonic 2's view of the 16-px block holding donor pixel (x, y) on `path`."""
    chunks, grid, ia, ib = s2_donor.collision_inputs(zone, "s2disasm")
    prof, ang = s2_donor.collision_arrays("s2disasm")
    cid = int(grid[y >> 7, x >> 7])
    if cid >= len(chunks):
        return None
    e = chunks[cid][((y & 0x70) >> 4) * 8 + ((x & 0x70) >> 4)]
    if MUTATE == "noxflip":
        e &= ~0x400
    if MUTATE == "noyflip":
        e &= ~0x800
    bid = e & 0x3FF
    if not bid:
        return None
    shape = (ia if path == 0 else ib)[bid]
    if not shape:
        return None
    top = (e >> (12 if path == 0 else 14)) & 1
    lrb = (e >> (13 if path == 0 else 15)) & 1
    a = ang[shape]
    if e & 0x400:
        a = (-a) & 0xFF
    if e & 0x800:
        a = (-((a + 0x40) & 0xFF) - 0x40) & 0xFF
    hs = []
    for col in range(16):
        c = (15 - col) if e & 0x400 else col
        h = s8(prof[shape * 16 + c])
        if e & 0x800:
            h = -h
        hs.append(h)
    return top, lrb, a, pixels(hs)


def aeon_block(word, hm, an):
    shape = word & CP.BLOCK_ID_MASK
    if not shape:
        return None
    sol = (word >> CP.PLANE_SOL_SHIFT) & 3
    h = hm[shape * 16:(shape + 1) * 16]
    a = an[shape]
    if word & CP.CHUNK_XFLIP_BIT:
        h = CP.flip_profile_x(h)
        a = CP.flip_angle_x(a)
    if word & CP.CHUNK_YFLIP_BIT:
        h = CP.flip_profile_y(h)
        a = CP.flip_angle_y(a)
    return sol & 1, (sol >> 1) & 1, a, pixels([s8(v) for v in h])


def main():
    act = CM.load(str(MANIFEST))
    planes = CM.collision_grids(act)
    hm, an = CM._bank(CM.collision_banks(act))
    tot = {"blocks": 0, "solid_blocks": 0, "presence": 0, "top": 0, "lrb": 0,
           "angle": 0, "pixels": 0, "cell_pair": 0}
    examples = []
    for clip in act.clips:
        sx, sy, w, h = clip.src
        dx, dy = clip.dst[0], clip.dst[1]
        zone = clip.zone
        for path in (0, 1):
            grid = planes[path ^ 1] if MUTATE == "swappath" else planes[path]
            for by in range(sy, sy + h, 16):
                for bx in range(sx, sx + w, 16):
                    tot["blocks"] += 1
                    ref = s2_block(zone, bx, by, path)
                    ax, ay = bx - sx + dx, by - sy + dy
                    w0 = int(grid[ay // 8, ax // 8])
                    w1 = int(grid[ay // 8, ax // 8 + 1])
                    if w0 != w1:
                        tot["cell_pair"] += 1
                    ours = aeon_block(w0, hm, an)
                    # S2 treats a block with neither solidity bit as air for every probe
                    if ref is not None and not (ref[0] or ref[1]):
                        ref = None
                    if ours is not None and not (ours[0] or ours[1]):
                        ours = None
                    if (ref is None) != (ours is None):
                        tot["presence"] += 1
                        if len(examples) < 8:
                            examples.append(("presence", zone, path, bx, by, ref and ref[:3],
                                             ours and ours[:3]))
                        continue
                    if ref is None:
                        continue
                    tot["solid_blocks"] += 1
                    bad = False
                    if ref[0] != ours[0]:
                        tot["top"] += 1; bad = True
                    if ref[1] != ours[1]:
                        tot["lrb"] += 1; bad = True
                    if ref[2] != ours[2]:
                        tot["angle"] += 1; bad = True
                    if not np.array_equal(ref[3], ours[3]):
                        tot["pixels"] += 1; bad = True
                    if bad and len(examples) < 8:
                        examples.append(("diff", zone, path, bx, by, ref[:3], ours[:3]))
    print("S2 runtime semantics vs the clip act's cell words, every 16-px block of both clip")
    print("rectangles, path 0 <-> plane A and path 1 <-> plane B:")
    for k, v in tot.items():
        print(f"  {k:13s} {v}")
    for e in examples:
        print("  example:", e)
    bad = sum(v for k, v in tot.items() if k not in ("blocks", "solid_blocks"))
    if tot["solid_blocks"] == 0:
        print("COULD NOT RUN: zero solid blocks compared")
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
