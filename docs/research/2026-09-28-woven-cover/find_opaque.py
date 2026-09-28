#!/usr/bin/env python3
"""find_opaque.py — 32x32 donor squares whose 16 cells are all fully opaque (a tunnel wall_src
candidate): prints the first few, with how many DISTINCT tiles each holds.

    python3 docs/research/2026-09-28-woven-cover/find_opaque.py DONOR ZONE X0 X1 Y0 Y1 [N]
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "tools"))
import s2_donor as sd  # noqa: E402
from cover_measure import opaque_tiles  # noqa: E402

donor, zone, x0, x1, y0, y1 = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
n_want = int(sys.argv[7]) if len(sys.argv) > 7 else 8
z = sd.load_zone(zone, donor)
op = opaque_tiles(donor, zone)
cx0, _, cy0, _ = z.box["crop_tiles"]
idx = (z.words & 0x7FF).astype(np.int64)
good = op[np.clip(idx, 0, len(op) - 1)] & (idx > 0)
found = 0
for y in range(y0, y1 - 31, 32):
    for x in range(x0, x1 - 31, 32):
        ty, tx = y // 8 - cy0, x // 8 - cx0
        if good[ty:ty + 4, tx:tx + 4].all():
            print(f"({x}, {y}) distinct tiles {len(set(idx[ty:ty + 4, tx:tx + 4].ravel()))}")
            found += 1
            if found >= n_want:
                raise SystemExit(0)
print("found", found)
