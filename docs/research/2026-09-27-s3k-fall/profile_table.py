#!/usr/bin/env python3
"""profile_table — per-logic-tick cycles of the named routines in ojz_feel_probe --windows JSONs.

usage: profile_table.py NAME=JSON [NAME=JSON ...]
"""
import json
import sys

NAMES = ['GameState_OJZScroll_Update', 'Tile_Cache_Fill', 'TileCache_FillRow', 'TileCache_FillColumn',
         'TileCache_DecompressBlock', 'Parallax_Update', 'RunObjects', 'Air_Move',
         'Section_UpdateColumns', 'Draw_TileRow_FromCache', 'VBlank_Handler', 'VSync_Wait',
         'Canopy_Probe']
for arg in sys.argv[1:]:
    tag, path = arg.split("=", 1)
    h = json.load(open(path))
    print(f"{tag} crc {h['crc']} script {h['script']}")
    for w in h["windows"]:
        t = w["ticks"]
        d = {it["name"]: it["cyclesTotal"] / t for it in w["profile"]["items"]}
        print(f"  frames {w['start']}+{w['frames']}: {t} ticks, lag {w['lfc']}; " +
              ", ".join(f"{n} {d.get(n, 0) / 1000:.1f}k" for n in NAMES))
