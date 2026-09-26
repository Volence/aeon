#!/usr/bin/env python3
"""RESEARCH (not a gate): Sonic 2's own two collision paths, per 8-px column, read straight
from the donor (chunk words + both collision indices + the vertical height array), with no
aeon conversion in between. For each column and each path it prints the solid cells from the
top: `y:<T|W|TW><height>` where T = top-solid bit, W = LRB bit (s2.asm chunk word bits 12/13
for path A, 14/15 for path B), height = the vertical profile at this column.

    python3 docs/research/2026-09-27-clip-planeb-hole/s2_paths.py EHZ 1280 1760
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools"))
import s2_donor as D  # noqa: E402

zone, x0, x1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ymax = int(sys.argv[4]) if len(sys.argv) > 4 else 1024
chunks, grid, ia, ib = D.collision_inputs(zone, "s2disasm")
prof, _ = D.collision_arrays("s2disasm")


def cell(x, y, path):
    ch = grid[y // 128][x // 128]
    w = chunks[ch][((y % 128) // 16) * 8 + (x % 128) // 16]
    blk, xf, yf = w & 0x3FF, (w >> 10) & 1, (w >> 11) & 1
    sol = (w >> (12 if path == 0 else 14)) & 3
    idx = (ia if path == 0 else ib)[blk]
    col = 15 - (x % 16) if xf else x % 16
    h = prof[idx * 16 + col]
    h = h - 256 if h > 127 else h
    return sol, idx, (-h if yf else h)


def floor(x, path):
    """Topmost top-solid cell with a positive height (probe_core's floor, S2's too)."""
    for y in range(0, ymax, 16):
        sol, idx, h = cell(x, y, path)
        if sol & 1 and idx and h > 0:
            return y + 16 - h
    return None


for x in range(x0, x1, 8):
    out = []
    for p in (0, 1):
        s = []
        for y in range(0, ymax, 16):
            sol, idx, h = cell(x, y, p)
            if sol and idx:
                s.append(f"{y}:{'T' if sol & 1 else ''}{'W' if sol & 2 else ''}{h}")
        out.append(f"floor {floor(x, p)!s:>4}  " + " ".join(s[:int(os.environ.get("NCELLS", "5"))]))
    print(f"{x:5d} | A {out[0]:<52} | B {out[1]}")
