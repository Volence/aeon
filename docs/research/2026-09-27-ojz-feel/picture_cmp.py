#!/usr/bin/env python3
"""picture_cmp — before/after picture identity from two ojz_feel_probe --dump legs.

usage: picture_cmp.py BEFORE.json AFTER.json
A tick is COMPARED when both legs recorded it (an on-time frame in both) and the camera read
with it agrees. For those ticks it counts how many differ in:
  scroll   Hscroll_Buffer + Parallax_Vscroll_Column_Buf + Vscroll_Factor
  planeA   VRAM Plane A over the camera window (+1 cell each side)
  planeB   VRAM Plane B, all of it
and prints the worst visible-undrawn coverage (right, left, bottom, top) seen in each leg over
ALL its recorded ticks (> 0 is a hole on screen). Exit 0 identical, 1 a difference, 2 nothing
compared (a leg with no matched tick witnesses nothing and must not read as identical).
"""
import json
import sys

a, b = (json.load(open(p)) for p in sys.argv[1:3])
da, db = a["dumps"], b["dumps"]
keys = sorted(set(da) & set(db), key=lambda k: tuple(int(x) for x in k.split(":")))
cmpd = [k for k in keys if da[k][:2] == db[k][:2]]
cam_mismatch = len(keys) - len(cmpd)
diff = {"scroll": [], "planeA": [], "planeB": []}
for k in cmpd:
    for j, nm in ((2, "scroll"), (3, "planeA"), (4, "planeB")):
        if da[k][j] != db[k][j]:
            diff[nm].append(k)


def worst(d):
    return [max(v[5][i] for v in d.values()) for i in range(4)] if d else None


print(f"{a['rom']} {a['crc']} vs {b['rom']} {b['crc']}  script={a['script']}")
print(f"  ticks recorded {len(da)} / {len(db)}; both {len(keys)}; camera-matched {len(cmpd)} "
      f"(camera differs at {cam_mismatch})")
for nm, ks in diff.items():
    print(f"  {nm:<7} differs at {len(ks)} of {len(cmpd)}" + (f"  first {ks[:5]}" if ks else ""))
print(f"  worst visible undrawn (R,L,B,T): before {worst(da)}  after {worst(db)}")
if not cmpd:
    sys.exit(2)
sys.exit(1 if any(diff.values()) else 0)
