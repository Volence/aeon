#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate): is a CONVERTED ZONE TREE's collision Sonic 2's, pixel for pixel?

The whole-zone generalisation of the slope parcel's
`docs/research/2026-09-26-sonic-slope-collision/s2_collision_equivalence.py`. That probe
compares the EHZ/CPZ clip act's cell words (through clips.json) against Sonic 2's runtime
semantics; this one compares a converted zone tree
(`games/sonic4/data/donors/<donor>/<ZONE>/section_N.collattr{,b}.bin`, written by
`tools/s2_zone_convert.py`) against the same semantics, over EVERY 16-px block of the zone's
camera-box crop, for either donor (the prototype is the only HPZ source).

The S2 side is written from s2.asm (Find_Tile / FindFloor), exactly as the slope parcel's:
    entry = chunks[layout[y>>7][x>>7]][((y & $70) >> 4) * 8 + ((x & $70) >> 4)]
    block id = entry & $3FF; path 0 solidity bits 12/13, path 1 bits 14/15;
    shape = ColP[id] / ColS[id]; angle = ColCurveMap[shape] with X/Y flip rules;
    height = ColArrayVertical[shape*16 + col] with X flip (col = 15-col) and Y flip (negate).
The aeon side reads the tree's plane-A word for path 0 and plane-B word for path 1 at the
block's top-left 8-px cell, through the base bank zone.json names, with collision_pipeline's
flip helpers. Both 8-px columns of a block must carry the same word (`cell_pair`).

Outside the crop the tree is air by rule 7 of the converter and S2's layout is not; the
comparison is restricted to the crop, which is the converter's own contract.

    python3 docs/research/2026-09-27-mega-act-layout/s2_zone_collision_equivalence.py \
        [--mutate noxflip|noyflip|swappath] DIR [DIR ...]

CONTROLS: `--mutate` corrupts the S2 side (ignore bit 10, ignore bit 11, or compare path 0
with plane B). Each must report a nonzero difference; a probe that cannot fail proves nothing.
Exit 0 = all zero differences, 1 = differences, 2 = could not run (zero solid blocks).
"""
import argparse
import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import collision_pipeline as CP                            # noqa: E402
import s2_donor                                            # noqa: E402


def s8(b):
    return b - 256 if b >= 128 else b


_pix_cache = {}


def pixels(heights16):
    """16x16 bool: floor-class solid pixels for a 16-column signed height profile."""
    key = tuple(heights16)
    got = _pix_cache.get(key)
    if got is not None:
        return got
    out = np.zeros((16, 16), dtype=bool)
    for c in range(16):
        h = heights16[c]
        for r in range(16):
            out[r, c] = (h > 0 and r + h >= 16) or (h < 0 and r + h < 0)
    _pix_cache[key] = out
    return out


def s2_entry_view(e, path, ia, ib, prof, ang, mutate):
    """Sonic 2's view of one chunk entry word on one path (None = air)."""
    if mutate == "noxflip":
        e &= ~0x400
    if mutate == "noyflip":
        e &= ~0x800
    bid = e & 0x3FF
    if not bid:
        return None
    shape = (ia if path == 0 else ib)[bid]
    if not shape:
        return None
    top = (e >> (12 if path == 0 else 14)) & 1
    lrb = (e >> (13 if path == 0 else 15)) & 1
    if not (top or lrb):
        return None
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


def aeon_word_view(word, hm, an):
    shape = word & CP.BLOCK_ID_MASK
    if not shape:
        return None
    sol = (word >> CP.PLANE_SOL_SHIFT) & 3
    if not sol:
        return None
    h = hm[shape * 16:(shape + 1) * 16]
    a = an[shape]
    if word & CP.CHUNK_XFLIP_BIT:
        h = CP.flip_profile_x(h)
        a = CP.flip_angle_x(a)
    if word & CP.CHUNK_YFLIP_BIT:
        h = CP.flip_profile_y(h)
        a = CP.flip_angle_y(a)
    return sol & 1, (sol >> 1) & 1, a, pixels([s8(v) for v in h])


def load_plane(tree, zm, suffix):
    gw, gh = zm["grid"]["w"], zm["grid"]["h"]
    n = 256
    out = np.zeros((gh * n, gw * n), dtype=np.uint16)
    for s in zm["sections"]:
        raw = (tree / f"section_{s['n']}.{suffix}.bin").read_bytes()
        arr = np.frombuffer(raw, dtype=">u2").reshape(n, n)
        out[s["sy"] * n:(s["sy"] + 1) * n, s["sx"] * n:(s["sx"] + 1) * n] = arr
    return out


def compare(tree, mutate):
    tree = pathlib.Path(tree)
    zm = json.loads((tree / "zone.json").read_text())
    zone, donor = zm["zone"], zm["donor"]
    chunks, grid, ia, ib = s2_donor.collision_inputs(zone, donor)
    prof, ang = s2_donor.collision_arrays(donor)
    bank = REPO / zm["collision"]["base_bank"]
    hm = (bank / "heightmaps.bin").read_bytes()
    an = (bank / "angles.bin").read_bytes()
    planes = (load_plane(tree, zm, "collattr"), load_plane(tree, zm, "collattrb"))
    x0t, x1t, y0t, y1t = zm["extent"]["crop_tiles"]
    tot = {"blocks": 0, "solid_blocks": 0, "presence": 0, "top": 0, "lrb": 0,
           "angle": 0, "pixels": 0, "cell_pair": 0}
    examples = []
    s2c, aec = {}, {}
    for path in (0, 1):
        g = planes[path ^ 1] if mutate == "swappath" else planes[path]
        for by in range(y0t * 8, y1t * 8, 16):
            for bx in range(x0t * 8, x1t * 8, 16):
                tot["blocks"] += 1
                cy, cx = by >> 7, bx >> 7
                ref = None
                if cy < grid.shape[0] and cx < grid.shape[1]:
                    cid = int(grid[cy, cx])
                    if cid < len(chunks):
                        e = chunks[cid][((by & 0x70) >> 4) * 8 + ((bx & 0x70) >> 4)]
                        k = (e, path)
                        if k not in s2c:
                            s2c[k] = s2_entry_view(e, path, ia, ib, prof, ang, mutate)
                        ref = s2c[k]
                w0 = int(g[by // 8, bx // 8])
                w1 = int(g[by // 8, bx // 8 + 1])
                if w0 != w1:
                    tot["cell_pair"] += 1
                if w0 not in aec:
                    aec[w0] = aeon_word_view(w0, hm, an)
                ours = aec[w0]
                if (ref is None) != (ours is None):
                    tot["presence"] += 1
                    if len(examples) < 4:
                        examples.append(("presence", path, bx, by))
                    continue
                if ref is None:
                    continue
                tot["solid_blocks"] += 1
                bad = False
                for i, k in ((0, "top"), (1, "lrb"), (2, "angle")):
                    if ref[i] != ours[i]:
                        tot[k] += 1
                        bad = True
                if not np.array_equal(ref[3], ours[3]):
                    tot["pixels"] += 1
                    bad = True
                if bad and len(examples) < 4:
                    examples.append(("diff", path, bx, by, ref[:3], ours[:3]))
    return f"{donor}@{zone}", tot, examples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", choices=("noxflip", "noyflip", "swappath"), default="")
    ap.add_argument("dirs", nargs="+")
    a = ap.parse_args()
    worst = 0
    for d in a.dirs:
        name, tot, ex = compare(d, a.mutate)
        diffs = sum(v for k, v in tot.items() if k not in ("blocks", "solid_blocks"))
        print(f"{name:24s} " + " ".join(f"{k}={v}" for k, v in tot.items())
              + f"  -> differences={diffs}" + (f"  [mutate={a.mutate}]" if a.mutate else ""))
        for e in ex:
            print("   example:", e)
        if tot["solid_blocks"] == 0:
            print(f"COULD NOT RUN: {name}: zero solid blocks compared")
            worst = max(worst, 2)
        elif diffs:
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    sys.exit(main())
