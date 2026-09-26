#!/usr/bin/env python3
"""legview — summarise one or more ojz_feel_probe legs: lag by camera region, lag events, path.

  legview.py LEG.json [...] [--png OUT.png --map MAP.png]
Prints per leg: totals; lag by camera 512x512 bucket; each lag frame with camera, player,
velocities and player state; a coarse path (every 60 frames). With --png, draws each leg's
player path on the act map (1 map px = 4 world px; the map is render_ojz.py's) and marks the
player at each lag frame in red.
"""
import json
import sys
from collections import defaultdict

args = sys.argv[1:]
png = mapf = None
if "--png" in args:
    png = args[args.index("--png") + 1]
    mapf = args[args.index("--map") + 1]
    args = [x for i, x in enumerate(args) if x not in ("--png", "--map") and
            (i == 0 or args[i - 1] not in ("--png", "--map"))]
STATES = {0: "GRD", 2: "ROLL", 4: "SDASH", 6: "AIR", 8: "JUMP", 10: "RJMP", 12: "ABALL", 14: "FLY"}
legs = []
for p in args:
    h = json.load(open(p))
    rows = h["rows"]
    legs.append((p, rows))
    fc = sum(r[1] for r in rows)
    lt = sum(r[2] for r in rows)
    print(f"== {p}: {h['crc']} script={h['script']}\n   frames {fc} ticks {lt} lag {fc - lt} "
          f"(LFC {sum(r[3] for r in rows)})  notes={h['notes']}")
    b = defaultdict(lambda: [0, 0])
    for r in rows:
        k = (r[4] // 512 * 512, r[5] // 512 * 512)
        b[k][0] += r[1]
        b[k][1] += r[1] - r[2]
    print("   lag by camera (x,y) 512 bucket: " + "  ".join(
        f"{k[0]},{k[1]}:{v[1]}/{v[0]}" for k, v in sorted(b.items()) if v[1]))
    for r in rows:
        if r[3]:
            print(f"   LAG f{r[0]:>5} step{r[11]} cam ({r[4]},{r[5]}) pl ({r[6]},{r[7]}) "
                  f"v ({r[8]},{r[9]}) {STATES.get(r[10], r[10])}")
if png:
    from PIL import Image, ImageDraw
    im = Image.open(mapf).convert("RGB")
    sc = im.size[0] / 6144
    d = ImageDraw.Draw(im)
    cols = [(0, 255, 0), (0, 200, 255), (255, 200, 0), (255, 255, 255), (255, 120, 255)]
    for li, (p, rows) in enumerate(legs):
        pts = [(r[6] * sc, r[7] * sc) for r in rows]
        if len(pts) > 1:
            d.line(pts, fill=cols[li % len(cols)], width=1)
        for r in rows:
            if r[3]:
                x, y = r[6] * sc, r[7] * sc
                d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=(255, 0, 0))
    im.save(png)
    print("png", png)
