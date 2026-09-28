#!/usr/bin/env python3
"""donor_rows.py — what a candidate zone extension into a connector would show: per 64-px
band of donor rows over a donor x range, the share of 8x8 cells that are empty (tile 0: the
zone's background shows), fully opaque, or partly transparent.

    python3 docs/research/2026-09-28-woven-cover/donor_rows.py DONOR ZONE X0 X1 Y0 Y1
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "tools"))
import s2_donor as sd  # noqa: E402
from cover_measure import opaque_tiles  # noqa: E402

donor, zone, x0, x1, y0, y1 = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
z = sd.load_zone(zone, donor)
op = opaque_tiles(donor, zone)
cx0, cx1, cy0, cy1 = z.box["crop_tiles"]
print(f"{donor}/{zone}: crop tiles x {cx0}..{cx1} y {cy0}..{cy1} (px y {cy0 * 8}..{cy1 * 8})")
for by in range(y0, y1, 64):
    w = z.words[(by // 8) - cy0:(by + 64) // 8 - cy0, x0 // 8 - cx0:x1 // 8 - cx0]
    idx = (w & 0x7FF).astype(np.int64)
    empty = idx == 0
    opq = op[np.clip(idx, 0, len(op) - 1)] & ~empty
    n = idx.size
    print(f"  donor y {by:4d}..{by + 63:4d}: cells {n:4d}  empty {empty.sum() / n:5.1%}  "
          f"opaque {opq.sum() / n:5.1%}  partial {(n - empty.sum() - opq.sum()) / n:5.1%}")
