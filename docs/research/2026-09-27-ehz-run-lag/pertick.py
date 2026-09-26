#!/usr/bin/env python3
"""pertick — the cost of ONE overrunning tick, from a ehz_run_probe --windows leg.

usage: pertick.py WIN.json [names...]
lagwin.py divides by the ticks the snapshot span counted; a 3-frame window around a lag frame
profiles 2 whole frames that hold exactly ONE main-loop tick (checked: Parallax_Update, called
once per tick, is counted per window and printed). This divides by that call count instead, so
the figures are cycles per tick that ran inside the profiled frames: the overrunning tick in a
lag window, ordinary ticks in a control window. Also prints the distribution of block decodes
(TileCache_DecompressBlock calls) per lag window.
"""
import json
import sys
from collections import Counter, defaultdict

h = json.load(open(sys.argv[1]))
names = sys.argv[2:] or ["Tile_Cache_Fill", "TileCache_DecompressBlock", "S4LZ_DecompressDict",
                         "TileCache_FillRow", "TileCache_FillColumn", "PageCache_PatchRun_Seq",
                         "PageCache_PatchRun_Col", "Parallax_Update", "RunObjects", "Render_Sprites",
                         "Section_UpdateColumns", "Canopy_Probe", "PageCache_Audit", "VBlank_Handler"]
for kind in ("lag", "ctl"):
    ws = [w for w in h["windows"] if ((w["lfc"] or 0) > 0) == (kind == "lag")]
    ticks = 0
    inc, calls = defaultdict(float), defaultdict(float)
    dec = Counter()
    work = 0
    for w in ws:
        d = {r.get("name"): r for r in w["profile"]["items"]}
        t = d.get("Parallax_Update", {}).get("callsTotal", 0)
        ticks += t
        dec[d.get("TileCache_DecompressBlock", {}).get("callsTotal", 0)] += 1
        vs = d.get("VSync_Wait", {}).get("cyclesTotal", 0)
        work += w["profile"]["sampleCycles"] - vs
        for n in names:
            if n in d:
                inc[n] += d[n]["cyclesTotal"]
                calls[n] += d[n]["callsTotal"]
    print(f"{kind}: {len(ws)} windows, {ticks:.0f} ticks inside the profiled frames "
          f"(Parallax_Update calls), work (sample - VSync_Wait) {work / max(ticks, 1):.0f} cyc/tick; "
          f"decodes per window {dict(sorted(dec.items()))}")
    for n in names:
        print(f"   {n:<28} {inc[n] / max(ticks, 1):>8.0f} cyc/tick  {calls[n] / max(ticks, 1):>5.2f} calls/tick")
