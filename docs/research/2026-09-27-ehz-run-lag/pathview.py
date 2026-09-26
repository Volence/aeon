#!/usr/bin/env python3
"""pathview — print a run_probe leg's player path every N frames, and where its lag frames fall.

usage: pathview.py LEG.json [every=100]
Lag per 256-px bucket of PLAYER x = sum(dFrame_Counter) - sum(dLogic_Tick) over the rows in it.
"""
import json
import sys

h = json.load(open(sys.argv[1]))
every = int(sys.argv[2]) if len(sys.argv) > 2 else 100
rows = h["rows"]
print(h["rom"], h["crc"], h["mode"], h["notes"])
print("path (frame, px, py):", [(r[0], r[6], r[7]) for r in rows[::every]])
b = {}
for r in rows:
    e = b.setdefault(r[6] // 256 * 256, [0, 0, 0, 0])
    e[0] += r[1]
    e[1] += r[2]
    e[2] = max(e[2], r[7])
print("lag by player-x/256 (x: frames/lag, max py):")
print("  " + " ".join(f"{k}:{v[0]}/{v[0] - v[1]}" + (f"(y{v[2]})" if v[2] > 1024 else "")
                      for k, v in sorted(b.items())))
