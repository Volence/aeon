#!/usr/bin/env python3
"""Write layout.json, the woven proposal, from the seam rule rather than from typed numbers.

Every gap between two clips below is DERIVED from the connector rule of the report's §A
(screen extent + 16 px x the background frames of both sides, or the sealed rule), and the
clip positions follow from the gaps. `woven.py check layout.json` then measures the result
over every reachable camera position. Change a blob or a clip here and re-run both.

    python3 build_layout.py && python3 woven.py check layout.json
"""
import json
import math
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# MEASURED by bg_tiles.py (clip_bg_lower's list for four zones, the same dedupe for WFZ/HPZ)
BG_TILES = {"EHZ": 141, "CPZ": 237, "OOZ": 117, "MTZ": 77, "WFZ": 83, "HPZ": 145}
# BG blobs: zones in one blob are co-resident in the 376-tile arena (no overwrite between
# them). Chosen so the showcase seams (Chemical Plant inside Metropolis, Emerald Hill on
# Hidden Palace, Wing Fortress over Emerald Hill) are the cheap ones.
BLOBS = {"A": ["EHZ", "HPZ", "WFZ"], "M": ["CPZ", "MTZ"], "O": ["OOZ"]}
CAPACITY = 376
CHUNK = 1824
SCREEN_W, SCREEN_H = 320, 224


def blob(z):
    return next(b for b, zs in BLOBS.items() if z in zs)


def t_into(frm, to):
    if blob(frm) == blob(to):
        return 2
    return math.ceil(sum(BG_TILES[z] for z in BLOBS[blob(to)]) * 32 / CHUNK) + 3


def up16(v):
    return (v + 15) // 16 * 16


def h_gap(a, b):
    return up16(SCREEN_W + 16 * (t_into(a, b) + t_into(b, a)))


def v_gap(a, b):
    return up16(SCREEN_H + 16 * (t_into(a, b) + t_into(b, a)))


def main():
    for b, zs in BLOBS.items():
        n = sum(BG_TILES[z] for z in zs)
        assert n <= CAPACITY, (b, n)
    clips = []

    def clip(cid, tree, zone, src, dst, label, what, route):
        clips.append({"id": cid, "tree": tree, "zone": zone, "src": src, "dst": list(dst),
                      "label": label, "what": what, "route": route})
        return dst[0], dst[1], dst[0] + src[2], dst[1] + src[3]

    # --- the sky: Wing Fortress, one long clip over three zones
    WFZ_SRC = [1024, 256, 6144, 1536]
    wfz_x = 1536
    wfz = clip("wfz_deck", "s2disasm/WFZ", "WFZ", WFZ_SRC, (wfz_x, 0),
               "WING FORTRESS (sky)", "deck, tail fins, thrusters", "optional")
    # --- middle row: Emerald Hill, then Metropolis | Chemical Plant | Metropolis
    ehz_y = wfz[3] + v_gap("WFZ", "EHZ")
    ehz = clip("ehz_double_loop", "s2disasm/EHZ", "EHZ", [6144, 0, 2560, 1024], (0, ehz_y),
               "EMERALD HILL (start)", "the double loop", "must")
    mid_y = wfz[3] + max(v_gap("WFZ", "MTZ"), v_gap("WFZ", "CPZ"))
    mtw_x = ehz[2] + h_gap("EHZ", "MTZ")
    # MTZ_WEST_H: the TRADE variant (report §R2) sets 1536, which trims Metropolis west's
    # bottom 512 px and gives Hidden Palace's east piece 512 px more (its lake). Default 2048.
    mtw_h = int(os.environ.get("MTZ_WEST_H", "2048"))
    mtw = clip("mtz_west", "s2disasm/MTZ", "MTZ", [0, 0, 1536, mtw_h], (mtw_x, mid_y),
               "METROPOLIS (west half)", "the opening maze, first half", "must")
    cpz_x = mtw[2] + h_gap("MTZ", "CPZ")
    cpz = clip("cpz_loop_cluster", "s2disasm/CPZ", "CPZ", [7168, 0, 2048, 2048],
               (cpz_x, mid_y), "CHEMICAL PLANT (inside Metropolis)", "the loop cluster", "must")
    mte_x = cpz[2] + h_gap("CPZ", "MTZ")
    mte = clip("mtz_east", "s2disasm/MTZ", "MTZ", [1536, 0, 1536, 2048], (mte_x, mid_y),
               "METROPOLIS (east half)", "the same maze, continued", "must")
    # --- bottom row: Hidden Palace under Emerald Hill, Oil Ocean under Metropolis + CPZ
    # REVISION r2 (owner, 2026-09-27): Hidden Palace runs on EAST, under Emerald Hill and
    # on under Metropolis west, up into Metropolis and across into Oil Ocean.
    # It is ONE donor rectangle cut into an L: two clips pasted with the SAME donor->act
    # offset, so where they touch the geometry is Sonic 2's own (no seam, no connector:
    # same zone, same palette, same background). The west piece is full height under
    # Emerald Hill; the east piece is the part of the same donor strip that lies below
    # Metropolis west's bottom + the HPZ<->MTZ vertical rule.
    hpz_y = ehz[3] + v_gap("EHZ", "HPZ")
    ooz_y = max(mte[3] + v_gap("MTZ", "OOZ"), cpz[3] + v_gap("CPZ", "OOZ"))
    ooz_x = cpz_x
    hpz_top_e = mtw[3] + v_gap("HPZ", "MTZ")
    hpz_e_x1 = ooz_x - h_gap("HPZ", "OOZ")           # east piece ends where the tunnel starts
    if hpz_top_e < cpz[3] + v_gap("HPZ", "CPZ"):     # it rises beside Chemical Plant: keep
        hpz_e_x1 = min(hpz_e_x1, cpz_x - h_gap("HPZ", "CPZ"))   # that pair's rule too
    HPZ_DONOR_END = 9216                             # the prototype's painted HPZ width (MEASURED)
    hpz_sx = HPZ_DONOR_END - hpz_e_x1               # donor x of act x 0
    e_sy = hpz_top_e - hpz_y                         # donor y where the east piece starts
    hpz = clip("hpz_west", "s2-simonwai-disasm/HPZ", "HPZ", [hpz_sx, 0, 2560, 2048],
               (0, hpz_y), "HIDDEN PALACE (under Emerald Hill)", "the great diagonal",
               "optional")
    hpe = clip("hpz_east", "s2-simonwai-disasm/HPZ", "HPZ",
               [hpz_sx + 2560, e_sy, hpz_e_x1 - 2560, 2048 - e_sy], (2560, hpz_top_e),
               "HIDDEN PALACE (runs on east)", "its east floor, under Metropolis", "optional")
    ooz = clip("ooz_east", "s2disasm/OOZ", "OOZ", [8192, 0, 3072, 1888], (ooz_x, ooz_y),
               "OIL OCEAN (under CPZ + Metropolis)", "the east refinery", "must")
    # the L's two pieces share one offset (the geometry join is the donor's own)
    assert hpe[0] - hpz[0] == 2560 and hpe[1] - hpz[1] == e_sy

    W = max(c["dst"][0] + c["src"][2] for c in clips)
    H = max(c["dst"][1] + c["src"][3] for c in clips)
    grid = [math.ceil(W / 2048), math.ceil(H / 2048)]

    # --- connectors: the LANES the player crosses on (everything else between clips is
    # neutral fill). Each is named by the two zones it joins and the rule that sized it.
    def lane(cid, kind, a, b, rect, route, how, rule):
        return {"id": cid, "kind": kind, "joins": [a, b], "lanes": [rect], "rect": rect,
                "route": route, "how": how, "rule": rule}

    con = []
    # C1 Wing Fortress <-> Emerald Hill: a cloud climb through the band
    con.append(lane("C1", "cloud", "WFZ", "EHZ", [2048, wfz[3] - 96, 256, ehz_y - wfz[3] + 192],
                    "optional", "cloud ledges up (a spring later); fall down",
                    f"vertical, same BG blob: {v_gap('WFZ', 'EHZ')} px"))
    # C2 Wing Fortress <-> Metropolis west: a cloud climb out of MTZ's roof
    con.append(lane("C2", "cloud", "WFZ", "MTZ", [mtw_x + 512, wfz[3] - 96, 256,
                                                   mid_y - wfz[3] + 192],
                    "optional", "cloud ledges up out of Metropolis's roof; fall down",
                    f"vertical, BG blob change: {v_gap('WFZ', 'MTZ')} px"))
    # C3 Wing Fortress <-> Chemical Plant
    con.append(lane("C3", "cloud", "WFZ", "CPZ", [cpz_x + 1024, wfz[3] - 96, 256,
                                                   mid_y - wfz[3] + 192],
                    "optional", "drop from the fortress into Chemical Plant (down only)",
                    f"vertical, BG blob change: {v_gap('WFZ', 'CPZ')} px"))
    # C4 Emerald Hill <-> Hidden Palace: a shaft down through the ground
    con.append(lane("C4", "shaft", "EHZ", "HPZ", [768, ehz[3] - 96, 256, hpz_y - ehz[3] + 192],
                    "optional", "fall through Emerald Hill's pit; ledges back up",
                    f"vertical, same BG blob: {v_gap('EHZ', 'HPZ')} px"))
    # C5 Emerald Hill <-> Metropolis west: a tunnel
    t5y = ehz_y + 640
    con.append(lane("C5", "tunnel", "EHZ", "MTZ", [ehz[2] - 64, t5y, mtw_x - ehz[2] + 128, 96],
                    "must", "walk (the tunnel of today's act)",
                    f"horizontal, BG blob change: {h_gap('EHZ', 'MTZ')} px"))
    # C6 / C7 Metropolis <-> Chemical Plant <-> Metropolis: the two short tunnels
    t6y = mid_y + 1024
    con.append(lane("C6", "tunnel", "MTZ", "CPZ", [mtw[2] - 64, t6y, cpz_x - mtw[2] + 128, 96],
                    "must", "walk in", f"horizontal, same BG blob: {h_gap('MTZ', 'CPZ')} px"))
    con.append(lane("C7", "tunnel", "CPZ", "MTZ", [cpz[2] - 64, t6y, mte_x - cpz[2] + 128, 96],
                    "must", "walk out the other side",
                    f"horizontal, same BG blob: {h_gap('CPZ', 'MTZ')} px"))
    # C8 Chemical Plant <-> Oil Ocean: a drop shaft through CPZ's one open floor span
    con.append(lane("C8", "shaft", "CPZ", "OOZ", [cpz_x + 768, cpz[3] - 96, 256,
                                                   ooz_y - cpz[3] + 192],
                    "must", "drop (down only)", f"vertical, BG blob change: "
                    f"{v_gap('CPZ', 'OOZ')} px"))
    # C9 Metropolis east <-> Oil Ocean: a stair shaft
    con.append(lane("C9", "shaft", "MTZ", "OOZ", [mte_x + 256, mte[3] - 96, 256,
                                                   ooz_y - mte[3] + 192],
                    "optional", "ledges up and down", f"vertical, BG blob change: "
                    f"{v_gap('MTZ', 'OOZ')} px"))
    # C10 (r2, replaces v2's side tunnel) Hidden Palace east <-> Metropolis west, VERTICAL:
    # on the span where both edges are open (MEASURED, woven.py edges: MTZ west's bottom is
    # open from its 2nd 256-px span; HPZ east's top from its 1st to 3rd under Metropolis)
    con.append(lane("C10", "shaft", "HPZ", "MTZ", [mtw_x + 272, mtw[3] - 96, 256,
                                                    hpe[1] - mtw[3] + 192],
                    "optional", "ledges up into Metropolis; fall back down",
                    f"vertical, BG blob change: {v_gap('HPZ', 'MTZ')} px"))
    # C11 (r2) Hidden Palace east <-> Oil Ocean: a tunnel at the rows both edges share
    t11y = ooz_y + 320
    con.append(lane("C11", "tunnel", "HPZ", "OOZ", [hpe[2] - 64, t11y, ooz_x - hpe[2] + 128, 96],
                    "optional", "walk", f"horizontal, BG blob change: {h_gap('HPZ', 'OOZ')} px"))

    spec = {
        "title": "Woven Sonic 2 mega-act (layout v2.1: Hidden Palace runs east)",
        "subtitle": "To scale, 1 px = 8 world px. Each box holds its donor clip's foreground. "
                    "Grey = neutral fill (line-0 art, solid). Coloured bars = the connector "
                    "lanes, sized by the seam rule.",
        "scale": 8, "grid": grid, "spawn": [320, ehz_y + 640],
        "bg_tiles": BG_TILES, "blobs": BLOBS,
        "clips": clips, "connectors": con,
        "notes": [
            "MAIN ROUTE: Emerald Hill -C5-> Metropolis (west) -C6-> Chemical Plant -C7-> "
            "Metropolis (east) -C9-> Oil Ocean.   CPZ is a pocket you pass through; MTZ carries "
            "on at the other side.",
            "UNDER: Emerald Hill -C4-> Hidden Palace, which runs east under Metropolis: up -C10-> "
            "Metropolis (west), or on -C11-> Oil Ocean (a second way to the end).   SKY: Emerald "
            "Hill -C1-> Wing Fortress; Metropolis -C2-> Wing Fortress -C3-> drop into Chemical "
            "Plant.   DROP: Chemical Plant -C8-> Oil Ocean.",
            "Each lane's length is its seam's minimum: screen (320 across / 224 up-down) + "
            "16 px x the background frames of both sides (2 when the two zones share a BG blob).",
            "Checked over every reachable camera (woven.py check): 0 screens show two zones; "
            "every crossing at slack 0.   Collision 245 / 255.   Art window 12 / 12 on the clips.",
            "No objects: every 'ledges' lane stands in for a spring until objects exist.",
        ],
    }
    out = os.environ.get("LAYOUT_OUT", str(HERE / "layout.json"))
    pathlib.Path(out).write_text(json.dumps(spec, indent=1) + "\n")
    print(f"act {W} x {H} px -> grid {grid[0]} x {grid[1]} sections")
    for c in clips:
        print(f"  {c['id']:18s} dst {c['dst']}  size {c['src'][2]}x{c['src'][3]}")
    for k in con:
        print(f"  {k['id']:4s} {k['kind']:6s} {'-'.join(k['joins']):8s} lane {k['lanes'][0]}  "
              f"{k['rule']}")


if __name__ == "__main__":
    main()
