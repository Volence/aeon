#!/usr/bin/env python3
"""Render OJZ act 1 plane-A solidity (1 px per 8x8 cell) with objects/springs, 3x3 sections."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
WT = Path(__file__).resolve().parents[3]
ED = WT / "games/sonic4/data/editor/ojz/act1"
S = 256
img = Image.new("RGB", (S * 3, S * 3), (20, 20, 40))
px = img.load()
for sec in range(9):
    sx, sy = (sec % 3) * S, (sec // 3) * S
    f = ED / f"section_{sec}.collattr.bin"
    t = ED / f"section_{sec}.tiles.bin"
    if not f.exists():
        continue
    raw = f.read_bytes()
    tr = t.read_bytes() if t.exists() else b""
    cr = (ED / f"section_{sec}.coll.bin").read_bytes()
    any_attr = any(raw)
    for cy in range(S):
        for cx in range(S):
            i = (cy * S + cx) * 2
            w = int.from_bytes(raw[i:i + 2], "big")
            sol = (w >> 12) & 3
            cb = cr[cy * S + cx] if cr else 0
            if cb and not any_attr:
                px[sx + cx, sy + cy] = (230, 230, 230) if cb >= 0x80 else (200, 160, 255)
            elif w & 0x3FF and sol:
                px[sx + cx, sy + cy] = (230, 230, 230) if sol == 3 else ((120, 200, 255) if sol == 1 else (255, 150, 90))
            elif tr and int.from_bytes(tr[i:i + 2], "big") & 0x7FF:
                px[sx + cx, sy + cy] = (50, 70, 50)
d = ImageDraw.Draw(img)
for sec in range(9):
    sx, sy = (sec % 3) * S, (sec // 3) * S
    d.rectangle([sx, sy, sx + S - 1, sy + S - 1], outline=(255, 255, 0))
    d.text((sx + 3, sy + 3), str(sec), fill=(255, 255, 0))
    o = ED / f"section_{sec}.objects.json"
    if o.exists():
        for ob in json.loads(o.read_text()):
            x = ob.get("x", 0); y = ob.get("y", 0)
            d.ellipse([sx + x // 8 - 2, sy + y // 8 - 2, sx + x // 8 + 2, sy + y // 8 + 2], outline=(255, 0, 255))
# gridlines every 512 px (64 cells)
for k in range(0, S * 3, 64):
    for j in range(0, S * 3, 4):
        px[k, j] = (90, 90, 0); px[j, k] = (90, 90, 0)
img = img.resize((S * 3 * 2, S * 3 * 2), Image.NEAREST)
img.save(sys.argv[1])  # usage: render_ojz.py OUT.png
print("ok")
