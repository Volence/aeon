#!/usr/bin/env python3
"""SCRATCH: write a variant of the woven manifest with one tunnel partly replaced by a rect of
map. Never committed.

    variant.py BASE OUT CORRIDOR SIDE EXT Y0 H [SHIFT]
SIDE west: the rect continues the corridor's WEST clip eastward (donor x = that clip's src right
edge); east: continues the EAST clip westward. Y0/H: the rect's rows in ACT px. SHIFT=1 moves
every clip and connector whose x >= the corridor's east mouth right by EXT (the tunnel keeps its
length); SHIFT=0 shortens the tunnel.
"""
import json, sys

base, out, cid, side, ext, y0, h = sys.argv[1:8]
ext, y0, h = int(ext), int(y0), int(h)
shift = len(sys.argv) > 8 and sys.argv[8] == "1"
m = json.load(open(base))
co = next(c for c in m["corridors"] if c["id"] == cid)
x0, w = co["dst_rect"]["x"], co["dst_rect"]["w"]
east_mouth = x0 + w


def clip_at_x(x):
    return next(c for c in m["clips"] if (c["dst_rect"]["x"] == x if side == "east"
                                          else c["dst_rect"]["x"] + c["dst_rect"]["w"] == x)
                and c["dst_rect"]["y"] <= co["floor_y"] < c["dst_rect"]["y"] + c["dst_rect"]["h"])


if side == "west":
    k = clip_at_x(x0)
    sx = k["src_rect"]["x"] + k["src_rect"]["w"]
    dx = x0
else:
    k = clip_at_x(east_mouth)
    sx = k["src_rect"]["x"] - ext
    dx = east_mouth if shift else east_mouth - ext
sy = k["src_rect"]["y"] + (y0 - k["dst_rect"]["y"])
new = {"id": f"{k['id'][:20]}_ext", "donor": k["donor"], "zone": k["zone"],
       "src_rect": {"x": sx, "y": sy, "w": ext, "h": h},
       "dst_rect": {"x": dx, "y": y0, "w": ext, "h": h},
       "unaligned_dst_reason": "SCRATCH variant (woven touch-ups sizing), never committed"}
if "music" in k:
    new["music"] = k["music"]
if shift:
    for group in ("clips", "corridors", "shafts"):
        for c in m.get(group, []):
            if c is co:
                continue
            if c["dst_rect"]["x"] >= east_mouth:
                c["dst_rect"]["x"] += ext
                for pl in c.get("path_lines", []):
                    pass
    if side == "west":
        co["dst_rect"]["x"] += ext
    # a corridor whose EAST end moved but whose west end did not: lengthen it
    for c in m["corridors"]:
        if c is co:
            continue
        cx, cw = c["dst_rect"]["x"], c["dst_rect"]["w"]
        if cx < east_mouth <= cx + cw + ext and any(
                k2["dst_rect"]["x"] == cx + cw + ext for k2 in m["clips"]):
            c["dst_rect"]["w"] += ext
else:
    if side == "west":
        co["dst_rect"]["x"] += ext
    co["dst_rect"]["w"] -= ext
m["clips"].insert(m["clips"].index(k) + 1, new)
json.dump(m, open(out, "w"), indent=2)
print("variant:", cid, side, "rect", new["src_rect"], "->", new["dst_rect"], "shift" if shift else "shorten",
      "corridor now", co["dst_rect"])
