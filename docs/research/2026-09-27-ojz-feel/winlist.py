#!/usr/bin/env python3
"""winlist — one line per profiled window of an ojz_feel_probe --windows leg: which routines
carried the overrunning tick. Columns are inclusive cycles (calls) per window for NAMES.

usage: winlist.py WIN.json [--lag-only] [names...]
"""
import json
import sys

args = [x for x in sys.argv[1:] if x != "--lag-only"]
lag_only = "--lag-only" in sys.argv
h = json.load(open(args[0]))
names = args[1:] or ["Tile_Cache_Fill", "TileCache_FillRow", "TileCache_FillColumn",
                     "TileCache_DecompressBlock", "S4LZ_DecompressDict", "Section_UpdateColumns",
                     "Parallax_Update", "RunObjects"]
print("start lfc ticks  cam        work   " + "  ".join(n[:14] for n in names))
for w in h["windows"]:
    if lag_only and not w["lfc"]:
        continue
    d = {r.get("name"): r for r in w["profile"]["items"]}
    vs = d.get("VSync_Wait", {}).get("cyclesTotal", 0)
    t = max(d.get("Parallax_Update", {}).get("callsTotal", 1), 1)
    work = (w["profile"]["sampleCycles"] - vs) / t
    cells = []
    for n in names:
        r = d.get(n)
        cells.append(f"{(r['cyclesTotal'] / t if r else 0):>7.0f}({(r['callsTotal'] / t if r else 0):.1f})")
    print(f"{w['start']:>5} {w['lfc']:>3} {w['ticks']:>3} {str(w['cam']):<12} {work:>7.0f} " + " ".join(cells))
