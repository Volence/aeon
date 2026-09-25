#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate, not wired into any build): what Sonic 2 puts at the
34 RULE-B floor pinholes of S2CLIP-CPZ-LONGER. Reads the STOCK s2disasm files
directly; the only aeon code it borrows is the Kosinski decoder.

    python3 docs/research/2026-09-25-cpz-floor-gaps/cpz_gap_probe.py [--s2 DIR]

Prints: the pinhole list from the stock data (independent of the converter), the
same list via the converted donor tree + collision_pipeline + the gate's own
find_pinhole_violations (needs `python3 tools/s2_zone_convert.py convert
s2disasm@CPZ` first), whether the two agree, and a per-site row: sealed-pocket
flood, standing-position search, nearest object in CPZ_1.bin.
Report: docs/research/2026-09-25-cpz-floor-gaps.md.
"""
import argparse
import os
import re
import struct
import sys
from collections import deque

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))
import ojz_common  # noqa: E402  (Kosinski decoder only)

ap = argparse.ArgumentParser()
ap.add_argument("--s2", default=None, help="s2disasm root (default: s2_donor's resolver)")
args = ap.parse_args()
if args.s2 is None:
    import s2_donor
    args.s2 = s2_donor.donor_root("s2disasm")
S2 = os.path.abspath(args.s2)

# CPZ -> act placement in the s2_ehz_cpz clip (clips.json cpz_act1 dst_rect) AT THE TIME OF THIS
# REPORT (832-px tunnel). Kept so the report's act coordinates reproduce; since the 384-px tunnel
# was adopted (2026-09-25) the act pastes CPZ at x 11360, so subtract 448 for today's act x.
ACT_DX, ACT_DY = 11808, 256
# act sections 7 and 8 of the 6624-px variant, in CPZ coordinates
SECTIONS = ((2528, 4576), (4576, 6624))
MIN_GAP = 2 * 9        # 2 * PLAYER_X_RADIUS, the gate's threshold
XR, YR, REACH = 9, 19, 9 + 2   # PLAYER_X_RADIUS, PLAYER_Y_RADIUS, LEDGE_PROBE_REACH


def rd(p):
    return open(os.path.join(S2, p), "rb").read()


def kos(p):
    return bytes(ojz_common.kos_decompress(rd(p))[0])


layout = kos("level/layout/CPZ_1.kos")                      # s2.asm:89709
chunks = kos("mappings/128x128/CPZ_DEZ.kos")                # s2.asm:90311
colP = kos("collision/CPZ and DEZ primary 16x16 collision index.kos")    # s2.asm:89601
colS = kos("collision/CPZ and DEZ secondary 16x16 collision index.kos")  # s2.asm:89603
HV = rd("collision/Collision array - Vertical.bin")         # s2.asm:89576


def block_entry(x, y):
    # layout rows alternate FG/BG, 128 bytes each; chunk = 8x8 words of 16x16 blocks
    c = layout[(y >> 7) * 256 + (x >> 7)]
    off = c * 128 + ((y & 0x7F) >> 4) * 16 + ((x & 0x7F) >> 4) * 2
    return struct.unpack(">H", chunks[off:off + 2])[0]


def chunk_id(x, y):
    return layout[(y >> 7) * 256 + (x >> 7)]


def _shape(x, y, plane):
    w = block_entry(x, y)
    bid = w & 0x3FF
    if not bid:
        return w, 0
    idx = (colP if plane == "A" else colS)[bid]
    return w, idx


def floor_px(x, y, plane):
    """FindFloor (s2.asm:42941-42990): block id != 0, top-solid bit set, collision id != 0,
    height at (x, flipped if X-flip) & 15 != 0. Exactly what the gate's RULE B reads."""
    w, idx = _shape(x, y, plane)
    if not idx or not (w >> (12 if plane == "A" else 14)) & 1:
        return False
    col = (~x if w & 0x400 else x) & 15
    return HV[idx * 16 + col] != 0


def solid_px(x, y, plane):
    """2D pixel solidity (top OR lrb), signed heights, Y-flip negates (s2.asm:42979-42990)."""
    w, idx = _shape(x, y, plane)
    if not idx or not (w >> (12 if plane == "A" else 14)) & 3:
        return False
    h = HV[idx * 16 + ((~x if w & 0x400 else x) & 15)]
    h = h - 256 if h >= 128 else h
    if w & 0x800:
        h = -h
    r = y & 15
    if h == 0:
        return False
    if abs(h) >= 16:
        return True
    return r >= 16 - h if h > 0 else r < -h


def block_passable(x, y, plane):
    """Conservative for the SEALED claim: anything not a fully solid block is passable."""
    if x < 0 or y < 0 or x >= 16384 or y >= 2048:
        return False
    w, idx = _shape(x, y, plane)
    if not idx or not (w >> (12 if plane == "A" else 14)) & 3:
        return True
    return not all(h in (16, 0xF0) for h in HV[idx * 16: idx * 16 + 16])


def flood(x, y, plane, cap=600):
    seen = {(x, y)}
    q = deque([(x, y)])
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((16, 0), (-16, 0), (0, 16), (0, -16)):
            n = (cx + dx, cy + dy)
            if n not in seen and block_passable(n[0], n[1], plane):
                seen.add(n)
                q.append(n)
                if len(seen) > cap:
                    return None
    return seen


def standable(plane, gx, gy, glen):
    """A standing player whose single ledge probe (x +/- REACH) lands in the gap: body box
    (2*XR+1) x (2*YR) all air, a foot sensor on a solid pixel at the gap row's top."""
    for px in range(gx - REACH - XR - 2, gx + glen + REACH + XR + 2):
        if not any(gx <= p < gx + glen for p in (px + REACH, px - REACH)):
            continue
        if not (solid_px(px - XR, gy, plane) or solid_px(px + XR, gy, plane)):
            continue
        if all(not solid_px(xx, yy, plane)
               for yy in range(gy - 2 * YR, gy) for xx in range(px - XR, px + XR + 1)):
            return px
    return None


def stock_pinholes():
    out = []
    for plane in "AB":
        for x0, x1 in SECTIONS:
            for y in range(0, 1792, 16):
                line = [floor_px(x, y, plane) for x in range(x0, x1)]
                i, n = 0, len(line)
                while i < n:
                    if line[i]:
                        i += 1
                        continue
                    s = i
                    while i < n and not line[i]:
                        i += 1
                    if s and i < n and i - s < MIN_GAP:
                        out.append((plane, x0 + s, y, i - s))
    return sorted(out, key=lambda r: (r[1], r[2], r[0]))


def tree_pinholes():
    import collision_pipeline as cp
    import collision_consistency as cc
    tree = os.path.join(REPO, "games/sonic4/data/donors/s2disasm/CPZ")
    bank = os.path.join(REPO, "games/sonic4/data/collision/base_s2")
    if not os.path.isdir(tree):
        return None
    prof = open(os.path.join(bank, "heightmaps.bin"), "rb").read()
    ang = open(os.path.join(bank, "angles.bin"), "rb").read()
    aset = cp.AttrSet(cap=None)
    cache = {}

    def word(x, y, plane):
        key = (x // 2048, plane)
        if key not in cache:
            fn = "section_%d.%s.bin" % (key[0], "collattr" if plane == "A" else "collattrb")
            d = open(os.path.join(tree, fn), "rb").read()
            cache[key] = struct.unpack(">%dH" % (len(d) // 2), d)
        return cache[key][(y // 16) * 2 * 256 + (x % 2048) // 8]

    out = []
    for plane in "AB":
        for x0, x1 in SECTIONS:
            rows = [[cp.bake_plane_cell(word(x0 + c * 8, r * 16, plane), prof, ang, aset)
                     for c in range((x1 - x0) // 8)] for r in range(1792 // 16)]
            pad = 300 - len(aset.entries)
            heights = [list(e[0]) for e in aset.entries] + [[0] * 16] * pad
            solidity = [e[2] for e in aset.entries] + [0] * pad
            v, _ = cc.find_pinhole_violations(rows, heights, solidity, 1, MIN_GAP)
            out += [(plane, x0 + e["x_start"], e["world_y"], e["gap_px"]) for e in v]
    return sorted(out, key=lambda r: (r[1], r[2], r[0]))


def load_objects():
    lines = open(os.path.join(S2, "s2.asm")).read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("Obj_Index:"))
    names, oid, i = {}, 1, start + 1
    while oid <= 0xDC:
        m = re.search(r"dc\.l\s+(\w+)\s*(;.*)?", lines[i])
        i += 1
        if m:
            names[oid] = (m.group(1), (m.group(2) or "").strip("; ").strip(), i)
            oid += 1
    data = rd("level/objects/CPZ_1.bin")                    # s2.asm:90685
    objs = []
    for k in range(0, len(data) - 5, 6):
        x, yw, oid_, st = struct.unpack(">HHBB", data[k:k + 6])
        if x == 0xFFFF:
            break
        # y word: bits 0-11 y, 13 x-flip, 14 y-flip, 15 respawn (ChkLoadObj, s2.asm:33376-33404)
        objs.append(dict(idx=k // 6, x=x, y=yw & 0xFFF, xf=(yw >> 13) & 1, st=st,
                         name=names.get(oid_, ("?", "", 0))))
    return objs


if __name__ == "__main__":
    stock = stock_pinholes()
    print("stock pinholes:", len(stock))
    tree = tree_pinholes()
    if tree is None:
        print("donor tree absent: run tools/s2_zone_convert.py convert s2disasm@CPZ")
    else:
        print("tree pinholes:", len(tree), "IDENTICAL" if tree == stock else "DIFFER")
    objs = load_objects()
    for (pl, x, y, g) in stock:
        f = flood(x, y, pl)
        s = standable(pl, x, y, g)
        near = min(objs, key=lambda o: abs(o["x"] - (x + 8)) + abs(o["y"] - (y + 8)))
        d = abs(near["x"] - (x + 8)) + abs(near["y"] - (y + 8))
        fs = "open" if f is None else "sealed %d blk x%d..%d y%d..%d" % (
            len(f), min(c[0] for c in f), max(c[0] for c in f) + 15,
            min(c[1] for c in f), max(c[1] for c in f) + 15)
        print("%s cpz(%d,%d) act(%d,%d) gap %dpx chunk $%02X word $%04X | %s | stand %s | "
              "nearest #%d %s st $%02X (%d,%d) %dpx" % (
                  pl, x, y, x + ACT_DX, y + ACT_DY, g, chunk_id(x, y), block_entry(x, y), fs,
                  "none" if s is None else "px%d" % s, near["idx"], near["name"][0],
                  near["st"], near["x"], near["y"], d))
    print("cavity beside cpz(2672,1632) plane B:", len(flood(2656, 1600, "B") or []), "blocks, sealed")
