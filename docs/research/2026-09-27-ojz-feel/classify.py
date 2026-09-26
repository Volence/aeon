#!/usr/bin/env python3
"""classify — sort the LAG windows of ojz_feel_probe --windows legs into causes.

usage: classify.py WIN.json [...]
Per lag window (Lag_Frame_Count advanced inside it; one overrunning tick, the lagwin rule) it
reads the call counts of the fill's routines and files the tick under the FIRST rule it meets:
  column catch-up   TileCache_FillColumn called >= 4 times (the camera needs <= 2 a tick)
  decode burst      TileCache_DecompressBlock called >= 3 times
  steady over       everything else: the ordinary diagonal fill (2 rows, 1-2 columns, 0-2
                    decodes) on top of the rest of the tick
and prints the counts plus the mean work per class (sample - VSync_Wait, divided by the ticks
the window holds; a lag window spans the overrunning tick's two frames).
"""
import json
import sys
from collections import defaultdict

cls = defaultdict(list)
for p in sys.argv[1:]:
    h = json.load(open(p))
    for w in h["windows"]:
        if not w["lfc"]:
            continue
        d = {r.get("name"): r for r in w["profile"]["items"]}
        t = max(d.get("Parallax_Update", {}).get("callsTotal", 1), 1)
        cols = d.get("TileCache_FillColumn", {}).get("callsTotal", 0) / t
        dec = d.get("TileCache_DecompressBlock", {}).get("callsTotal", 0) / t
        s4 = d.get("S4LZ_DecompressDict", {}).get("callsTotal", 0) / t
        work = (w["profile"]["sampleCycles"] - d.get("VSync_Wait", {}).get("cyclesTotal", 0)) / t
        k = "column catch-up" if cols >= 4 else ("decode burst" if dec >= 3 else "steady over")
        cls[k].append((p.split("/")[-1], w["start"], cols, dec, s4, work))
tot = sum(len(v) for v in cls.values())
for k in ("column catch-up", "decode burst", "steady over"):
    v = cls[k]
    if not v:
        print(f"{k:<16} 0 of {tot}")
        continue
    print(f"{k:<16} {len(v):>3} of {tot}  mean cols {sum(x[2] for x in v) / len(v):.1f}  decodes "
          f"{sum(x[3] for x in v) / len(v):.1f} (S4LZ {sum(x[4] for x in v) / len(v):.1f})  "
          f"work/tick incl. the lag VBlank {sum(x[5] for x in v) / len(v):.0f}")
