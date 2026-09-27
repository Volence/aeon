#!/usr/bin/env python3
"""trace_table — per-frame y_vel / camera y / player y / screen line of one leg across builds.

usage: trace_table.py LEG NAME=DIR [NAME=DIR ...] [--every N]

The rows are ojz_feel_probe's. `line` is py - cy against the PREVIOUS tick's camera (the
probe's snapshot sits between RunObjects and Camera_Update, ojz-feel.md method notes), which is
the line Player_FallLimit's screen hold tests; the drawn line is that minus the tick's step.
"""
import json
import sys
from pathlib import Path

a = sys.argv[1:]
every = 10
if "--every" in a:
    k = a.index("--every")
    every = int(a[k + 1])
    del a[k:k + 2]
leg, sets = a[0], [x.split("=", 1) for x in a[1:]]
data = {n: json.loads((Path(d) / f"{leg}.json").read_text()) for n, d in sets}
print(f"leg {leg}; " + "; ".join(f"{n} crc {h['crc']}" for n, h in data.items()))
print("frame | " + " | ".join(f"{n:^29}" for n in data))
print("      | " + " | ".join(f"{'yv':>6} {'cy':>6} {'py':>6} {'line':>5}   " for _ in data))
n = max(len(h["rows"]) for h in data.values())
for i in range(0, n, every):
    cells = []
    for h in data.values():
        r = h["rows"]
        if i < len(r):
            _, _, _, _, cx, cy, px, py, xv, yv, st, si = r[i]
            cells.append(f"{yv / 256:6.1f} {cy:6d} {py:6d} {py - cy:5d}   ")
        else:
            cells.append(" " * 29)
    print(f"{i:5d} | " + " | ".join(cells))
