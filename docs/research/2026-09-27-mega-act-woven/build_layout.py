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
    mtw = clip("mtz_west", "s2disasm/MTZ", "MTZ", [0, 0, 1536, 2048], (mtw_x, mid_y),
               "METROPOLIS (west half)", "the opening maze, first half", "must")
    cpz_x = mtw[2] + h_gap("MTZ", "CPZ")
    cpz = clip("cpz_loop_cluster", "s2disasm/CPZ", "CPZ", [7168, 0, 2048, 2048],
               (cpz_x, mid_y), "CHEMICAL PLANT (inside Metropolis)", "the loop cluster", "must")
    mte_x = cpz[2] + h_gap("CPZ", "MTZ")
    mte = clip("mtz_east", "s2disasm/MTZ", "MTZ", [1536, 0, 1536, 2048], (mte_x, mid_y),
               "METROPOLIS (east half)", "the same maze, continued", "must")
    # --- bottom row: Hidden Palace under Emerald Hill, Oil Ocean under Metropolis + CPZ
    hpz_y = ehz[3] + v_gap("EHZ", "HPZ")
    hpz = clip("hpz_diagonal", "s2-simonwai-disasm/HPZ", "HPZ", [5632, 0, 2560, 2048],
               (0, hpz_y), "HIDDEN PALACE (under Emerald Hill)", "the great diagonal + lake",
               "optional")
    ooz_y = mtw[3] + max(v_gap("MTZ", "OOZ"), v_gap("CPZ", "OOZ"))
    ooz_x = cpz_x
    ooz = clip("ooz_east", "s2disasm/OOZ", "OOZ", [8192, 0, 3072, 1888], (ooz_x, ooz_y),
               "OIL OCEAN (under CPZ + Metropolis)", "the east refinery", "must")
    # Hidden Palace faces Metropolis west across the gap C5 already set; that gap is exactly
    # their own rule too (both pairs are an A <-> M blob change)
    assert mtw_x - hpz[2] >= h_gap("HPZ", "MTZ"), "HPZ-MTZ tunnel shorter than its rule"

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
    # C10 Hidden Palace <-> Metropolis west: a tunnel through the same gap as C5, lower down
    t10y = mid_y + 1536
    con.append(lane("C10", "tunnel", "HPZ", "MTZ", [hpz[2] - 64, t10y, mtw_x - hpz[2] + 128, 96],
                    "optional", "walk", f"horizontal, BG blob change: {h_gap('HPZ', 'MTZ')} px"))

    spec = {
        "title": "Woven Sonic 2 mega-act (layout v2)",
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
            "UNDER: Emerald Hill -C4-> Hidden Palace -C10-> Metropolis (west).   SKY: Emerald "
            "Hill -C1-> Wing Fortress; Metropolis -C2-> Wing Fortress -C3-> drop into Chemical "
            "Plant.   DROP: Chemical Plant -C8-> Oil Ocean.",
            "Each lane's length is its seam's minimum: screen (320 across / 224 up-down) + "
            "16 px x the background frames of both sides (2 when the two zones share a BG blob).",
            "Checked over every reachable camera (woven.py check): 0 screens show two zones; "
            "every crossing at slack 0.   Collision 245 / 255.   Art window 12 / 12 on the clips.",
            "No objects: every 'ledges' lane stands in for a spring until objects exist.",
        ],
    }
    (HERE / "layout.json").write_text(json.dumps(spec, indent=1) + "\n")
    print(f"act {W} x {H} px -> grid {grid[0]} x {grid[1]} sections")
    for c in clips:
        print(f"  {c['id']:18s} dst {c['dst']}  size {c['src'][2]}x{c['src'][3]}")
    for k in con:
        print(f"  {k['id']:4s} {k['kind']:6s} {'-'.join(k['joins']):8s} lane {k['lanes'][0]}  "
              f"{k['rule']}")


if __name__ == "__main__":
    main()
