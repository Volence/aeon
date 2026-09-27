#!/usr/bin/env python3
"""Write games/sonic4/data/clips/s2_woven/clips.json, the whole woven act (layout v2.1),
from the BAKE's seam rule and the measured floor rows, never from typed positions.

    python3 docs/research/2026-09-27-mega-act-woven/build_woven_act.py [--out PATH]

WHAT IS DERIVED:
  * every connector LENGTH: the bake's own Z2 rule (tools/clip_rom_bake.py
    connector_crossings): half the screen on the connector's axis + CAM_MAX_{X,Y}_STEP x the
    frames the crossing INTO each side takes (crossing_frames: the 3-frame visible-row wipe
    inside a background blob; the blob's 1,824-B overwrite chunks + the wipe across blobs).
    The blob sizes are clip_bg_lower's own tile lists, deduplicated per group, as the bake
    counts them. Controller ruling 1 (2026-09-27): the bake's 3-frame wipe is kept, so a
    same-blob seam is 320 up/down and 416 across, not the report's 288 / 384.
  * every clip POSITION: from those lengths and from the FLOOR ROWS each tunnel joins (a
    tunnel floor must be flush with both neighbours, clip_manifest K6), chosen below from
    the rows each edge accepts (MEASURED with the K6 reading; each choice has its reason).
  * the SHAFT lanes: on spans where both mouths are open (K10), chosen below.
The bake (`tools/clip_rom_bake.py bake`) is the judge of all of it.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import clip_camera            # noqa: E402
import clip_rom_bake as CRB   # noqa: E402

OUT = os.path.join(REPO, "games", "sonic4", "data", "clips", "s2_woven", "clips.json")
S2, SW = "s2disasm", "s2-simonwai-disasm"
ZONES = {"EHZ": S2, "CPZ": S2, "MTZ": S2, "OOZ": S2, "WFZ": S2, "HPZ": SW}
#: the report's three background blobs (§A.2; kept, v2.1 "The background groups, re-checked")
BLOBS = [["EHZ", "HPZ", "WFZ"], ["CPZ", "MTZ"], ["OOZ"]]
GRID = 16                                   # the collision block (R12, K3, K9)


def frames():
    """{(from, into): frames} by the bake's crossing_frames model, per zone pair."""
    chunk, rows_per_frame, screen_rows = CRB.background_constants()
    wipe = -(-screen_rows // rows_per_frame)
    pal = CRB.SNAP_FRAMES
    tiles = {z: set(CRB._lowered_tiles(d, z)) for z, d in ZONES.items()}
    group = {z: i for i, g in enumerate(BLOBS) for z in g}
    nbytes = [len(set().union(*(tiles[z] for z in g))) * 32 for g in BLOBS]
    out = {}
    for a in ZONES:
        for b in ZONES:
            if a != b:
                bg = wipe if group[a] == group[b] else -(-nbytes[group[b]] // chunk) + wipe
                out[(a, b)] = max(pal, bg)
    return out, nbytes


def seam(axis, a, b, fr, c):
    half = c["CAM_SCREEN_HALF_W"] if axis == "x" else c["CAM_SCREEN_HALF_H"]
    step = c["CAM_MAX_X_STEP"] if axis == "x" else c["CAM_MAX_Y_STEP"]
    n = 2 * half + step * (fr[(a, b)] + fr[(b, a)])
    return -(-n // GRID) * GRID


def rect(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def build():
    c = clip_camera.constants()
    fr, blob_bytes = frames()
    L = {k: seam(ax, a, b, fr, c) for k, ax, a, b in (
        ("same_y", "y", "EHZ", "HPZ"), ("same_x", "x", "MTZ", "CPZ"),
        ("AM_y", "y", "WFZ", "MTZ"), ("AM_x", "x", "EHZ", "MTZ"),
        ("MO_y", "y", "CPZ", "OOZ"), ("AO_x", "x", "HPZ", "OOZ"))}

    # ---- the CHOICES (each one MEASURED; the reasons go into the note) -----------------
    # Metropolis | Chemical Plant | Metropolis: s2_mtz_cpz's flown rectangles and floors.
    MTZ_SPLIT = 1520            # both halves stand on Metropolis's walkway at y 640
    CPZ_SRC_X = 7040            # Chemical Plant's middle track y 1088 is flush at 7040 and 9215
    MTZ_DY = 448                # Metropolis lowered 448 below Chemical Plant: 640 + 448 = 1088
    CPZ_FLOOR = 1088
    # C5: Emerald Hill's east edge (donor x 8703) accepts floors 576, 736, 960; Metropolis's
    # west edge (x 0) 256, 384, 672. 672 is Metropolis's own start floor (Sonic 2 starts the
    # player at (96, 652) on it), so the tunnel delivers him where Sonic 2 would; with it,
    # EHZ 960 is the one row that keeps every other seam short (see the note).
    EHZ_FLOOR, MTZ_WEST_FLOOR = 960, 672
    # C11: Hidden Palace's east piece ends at donor x 8336 (its edge column 8335 is flush on
    # the lake bridge at y 1376; 16 px before the W3 pit at 8352), Oil Ocean's west edge
    # (8192) is flush at 576, the ground its piece starts on.
    HPZ_END, HPZ_FLOOR, OOZ_FLOOR = 8336, 1376, 576
    # the east piece's rows: the air band over the lake bridge down to the rock under it
    # (MEASURED: donor y 1280..1343 is air in every column 7248..8351; 1504..2047, v2.1's
    # cut, is solid rock art end to end). Top 1296 puts C10 at exactly its length.
    HPZ_EAST_Y0, HPZ_EAST_Y1 = 1296, 1600
    MTZ_EAST_H = 1600           # Metropolis east's bottom 448 px trimmed: C8 and C9 both 464
    OOZ_X = 5104                # under Chemical Plant, as the report; its top span donor
    #                             10752..11007 then meets Metropolis east's open bottom (C9)

    # ---- positions -----------------------------------------------------------------------
    wfz = dict(id="wfz_deck", zone="WFZ", src=(1024, 256, 6144, 1536), dst=(1536, 0))
    wfz_bot = 1536
    cpz_y = wfz_bot + L["AM_y"]                                   # C3 exact
    mtz_y = cpz_y + MTZ_DY
    ehz_y = mtz_y + MTZ_WEST_FLOOR - EHZ_FLOOR                    # C5's floor
    ehz = dict(id="ehz_double_loop", zone="EHZ", src=(6144, 0, 2560, 1024), dst=(0, ehz_y))
    mtw_x = 2560 + L["AM_x"]
    mtw = dict(id="mtz_west", zone="MTZ", src=(0, 0, MTZ_SPLIT, 2048), dst=(mtw_x, mtz_y))
    cpz_x = mtw_x + MTZ_SPLIT + L["same_x"]
    cpz = dict(id="cpz_loop_cluster", zone="CPZ", src=(CPZ_SRC_X, 0, 9216 - CPZ_SRC_X, 2048),
               dst=(cpz_x, cpz_y), music="SONG_S2_CPZ")
    mte_x = cpz_x + (9216 - CPZ_SRC_X) + L["same_x"]
    mte = dict(id="mtz_east", zone="MTZ", src=(MTZ_SPLIT, 0, 3072 - MTZ_SPLIT, MTZ_EAST_H),
               dst=(mte_x, mtz_y))
    ooz_y = max(cpz_y + 2048, mtz_y + MTZ_EAST_H) + L["MO_y"]
    ooz = dict(id="ooz_east", zone="OOZ", src=(8192, 0, 3072, 1888), dst=(OOZ_X, ooz_y))
    hpz_y = ooz_y + OOZ_FLOOR - HPZ_FLOOR                         # C11's floor
    hpz_e_x1 = OOZ_X - L["AO_x"]                                  # C11 exact
    hpz_sx = HPZ_END - hpz_e_x1                                   # donor x of act x 0
    hpw = dict(id="hpz_west", zone="HPZ", src=(hpz_sx, 0, 2560, 2048), dst=(0, hpz_y))
    hpe = dict(id="hpz_east", zone="HPZ",
               src=(hpz_sx + 2560, HPZ_EAST_Y0, hpz_e_x1 - 2560, HPZ_EAST_Y1 - HPZ_EAST_Y0),
               dst=(2560, hpz_y + HPZ_EAST_Y0))
    ehz["music"] = "SONG_S2_EHZ"
    clips = [wfz, ehz, mtw, cpz, mte, hpw, hpe, ooz]

    def bottom(k):
        return k["dst"][1] + k["src"][3]

    def right(k):
        return k["dst"][0] + k["src"][2]

    lens = {
        "C1": ehz_y - wfz_bot, "C2": mtz_y - wfz_bot, "C3": cpz_y - wfz_bot,
        "C4": hpz_y - bottom(ehz), "C5": mtw_x - right(ehz),
        "C6": cpz_x - right(mtw), "C7": mte_x - right(cpz),
        "C8": ooz_y - bottom(cpz), "C9": ooz_y - bottom(mte),
        "C10": hpe["dst"][1] - bottom(mtw), "C11": OOZ_X - right(hpe)}
    mins = {"C1": L["same_y"], "C2": L["AM_y"], "C3": L["AM_y"], "C4": L["same_y"],
            "C5": L["AM_x"], "C6": L["same_x"], "C7": L["same_x"], "C8": L["MO_y"],
            "C9": L["MO_y"], "C10": L["AM_y"], "C11": L["AO_x"]}
    for k, v in lens.items():
        assert v >= mins[k], (k, v, mins[k])

    # ---- connectors ------------------------------------------------------------------------
    tunnel_art = {"donor": S2, "zone": "CPZ", "wall_src": rect(768, 784, 32, 32),
                  "back_src": rect(512, 896, 32, 32)}
    cloud_art = {"donor": S2, "zone": "EHZ", "wall_src": rect(4096, 512, 64, 64),
                 "back_src": rect(4096, 0, 64, 64)}

    def tunnel(cid, x0, x1, floor, bottom_y=None):
        """A 96-px walkway (s2_mtz_cpz's), painted 256 px above and below its floor, or
        down to `bottom_y`: a tunnel whose near zone names a song must not reach below that
        zone, or the MUSIC walk along its lowest rows starts outside the zone (C5: Emerald
        Hill ends 64 px under the floor)."""
        y1 = floor + 256 if bottom_y is None else min(floor + 256, bottom_y)
        return {"id": cid, "dst_rect": rect(x0, floor - 256, x1 - x0, y1 - (floor - 256)),
                "floor_y": floor, "tunnel": {"ceiling_y": floor - 96, "art": tunnel_art}}

    corridors = [
        tunnel("ehz_to_mtz", right(ehz), mtw_x, ehz_y + EHZ_FLOOR, bottom(ehz)),
        tunnel("mtz_to_cpz", right(mtw), cpz_x, cpz_y + CPZ_FLOOR),
        tunnel("cpz_to_mtz", right(cpz), mte_x, cpz_y + CPZ_FLOOR),
        tunnel("hpz_to_ooz", right(hpe), OOZ_X, hpz_y + HPZ_FLOOR),
    ]

    LEDGES = {"pitch": 64, "w": 64}

    def shaft(cid, x, w, y0, y1, look="rock", ledges=None):
        s = {"id": cid, "dst_rect": rect(x, y0, w, y1 - y0), "look": look}
        if look == "cloud":
            s["art"] = cloud_art
        if ledges:
            s["ledges"] = ledges
        return s

    shafts = [
        shaft("wfz_to_ehz", 2048, 256, wfz_bot, ehz_y, "cloud", LEDGES),
        shaft("wfz_to_mtz", mtw_x + 800, 192, wfz_bot, mtz_y, "cloud", LEDGES),
        shaft("wfz_to_cpz", cpz_x + 1024, 256, wfz_bot, cpz_y, "cloud"),
        shaft("ehz_to_hpz", 704, 256, bottom(ehz), hpz_y, ledges=LEDGES),
        shaft("cpz_to_ooz", cpz_x + 512, 256, bottom(cpz), ooz_y),
        shaft("mtz_to_ooz", mte_x + 16, 96, bottom(mte), ooz_y, ledges={"pitch": 64, "w": 32}),
        shaft("hpz_to_mtz", mtw_x + 32, 256, bottom(mtw), hpe["dst"][1], ledges=LEDGES),
    ]

    W = max(right(k) for k in clips)
    H = max(bottom(k) for k in clips)
    gw, gh = -(-W // 2048), -(-H // 2048)
    return dict(L=L, lens=lens, mins=mins, fr=fr, blob_bytes=blob_bytes, clips=clips,
                corridors=corridors, shafts=shafts, grid=(gw, gh), W=W, H=H,
                hpz_sx=hpz_sx, ehz_y=ehz_y)


def to_manifest(b, note, start):
    def clip_json(k):
        out = {"id": k["id"], "donor": ZONES[k["zone"]], "zone": k["zone"],
               "src_rect": rect(*k["src"]),
               "dst_rect": rect(k["dst"][0], k["dst"][1], k["src"][2], k["src"][3])}
        if k["dst"][0] % 2048 or k["dst"][1] % 2048:
            out["unaligned_dst_reason"] = k.get("why", "woven layout v2.1: placed by the seam "
                                                       "rule (see the note)")
        if k.get("music"):
            out["music"] = k["music"]
        return out
    gw, gh = b["grid"]
    return {
        "schema": 1, "units": "world_px", "id": "s2_woven", "anchor_overlay": True,
        "name": "THE WOVEN SONIC 2 MEGA-ACT (layout v2.1): Wing Fortress over Emerald Hill, "
                "Metropolis and Chemical Plant; Emerald Hill over Hidden Palace; Chemical "
                "Plant a pocket inside Metropolis; Oil Ocean under them",
        "note": note,
        "act": {"grid_w": gw, "grid_h": gh},
        "start": start,
        "clips": [clip_json(k) for k in b["clips"]],
        "corridors": b["corridors"],
        "shafts": b["shafts"],
        "fill": {"rect": rect(0, 0, gw * 2048, gh * 2048),
                 "why": "Everything between the zones is neutral: solid stone on CRAM line 0 "
                        "(the woven report's item 6), so no background shows between zones "
                        "and no Sonic 2 pit falls out of the act."},
        "crossing_overrides": {
            "palette": "snap", "background": "blobs", "bg_blobs": BLOBS,
            "zone_separation": "screen", "parallax": "snap",
            "why": "s2_woven_2d's overrides with the report's three blobs. SNAP palette and "
                   "parallax: every connector is drawn on CRAM line 0 and hides the "
                   "background, so the switch happens while only connector is on screen "
                   "(crossing_witness on s2_ehz_cpz and s2_mtz_cpz). BLOBS: A {EHZ, HPZ, WFZ}, "
                   "M {CPZ, MTZ}, O {OOZ} fit the 376-tile arena one group at a time; a seam "
                   "inside a group only repaints (3 frames), a seam across pays the group's "
                   "overwrite chunks. ZONE_SEPARATION = screen: Z1 counts the screen. "
                   "CROSSING_MARGIN is NOT overridden: every connector is the bake's own Z2 "
                   "length or longer, and Z2 enforces it (controller ruling 1).",
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--baseline", action="store_true",
                    help="write collision_baseline.json from a KEPT bake of --out instead")
    a = ap.parse_args()
    if a.baseline:
        baseline(a.out, os.path.join(os.path.dirname(a.out), "collision_baseline.json"))
        return 0
    b = build()
    print("lengths (derived minimum -> used):")
    for k in b["lens"]:
        print(f"  {k:4s} {b['mins'][k]:5d} -> {b['lens'][k]:5d}")
    for k in b["clips"]:
        print(f"  {k['id']:18s} src {k['src']} dst {k['dst']}")
    print(f"act {b['W']} x {b['H']}, grid {b['grid']}, HPZ donor start {b['hpz_sx']}, "
          f"blob bytes {b['blob_bytes']}")
    if a.print:
        return 0
    note = open(os.path.join(HERE, "s2_woven_note.txt")).read().strip()
    start = json.load(open(os.path.join(HERE, "s2_woven_start.json")))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(to_manifest(b, note, start), fh, indent=2)
        fh.write("\n")
    print(f"wrote {a.out}")
    return 0




def baseline(manifest_path, out_path):
    """Write the clip's collision_baseline.json from collision_consistency.check() run on a
    KEPT bake of it (`clip_rom_bake.py bake <manifest> --keep`), minus the tree's own
    baseline. Every entry is placed in act pixels and REFUSED unless it lies inside a donor
    clip: the file may only declare faithful Sonic 2 data, never a connector or the fill."""
    import collision_consistency as CC
    import clip_manifest as CM
    act = CM.load(manifest_path)
    gw = act.cols * CM.TILE_PX // 2048
    va, vb, _pop = CC.check()
    canon = CC.load_baseline(os.path.join(REPO, "tools", "collision_baseline.json"))
    entries, per = [], {}
    for rule, vs in (("A", va), ("B", vb)):
        for v in vs:
            key = CC.violation_key(v, rule)
            if tuple(map(CC._hashable, key)) in canon:
                continue
            sy, sx = divmod(v["section"], gw)
            x = sx * 2048 + (v["col_start"] * 8 if rule == "A" else v["x_start"])
            y = sy * 2048 + v["row"] * 16
            hit = [c for c in act.clips
                   if c.dst[0] <= x < c.dst[0] + c.dst[2] and c.dst[1] <= y < c.dst[1] + c.dst[3]]
            if len(hit) != 1:
                raise SystemExit(f"RULE {rule} violation at act ({x}, {y}) lies in no donor "
                                 f"clip ({hit}): not faithful donor data, NOT declarable")
            c = hit[0]
            per.setdefault((rule, c.zone), []).append(
                (x - c.dst[0] + c.src[0], y - c.dst[1] + c.src[1]))
            entries.append(key)
    why = ("FAITHFUL SONIC 2 DATA ONLY, every entry placed by build_woven_act.py baseline "
           "inside a donor clip (it refuses one in a connector or the fill): "
           + "; ".join(f"RULE {r} {z}: {len(p)} (donor x {min(q[0] for q in p)}.."
                       f"{max(q[0] for q in p)}, y {min(q[1] for q in p)}..{max(q[1] for q in p)})"
                       for (r, z), p in sorted(per.items()))
           + ". RULE A in Hidden Palace = its flat full-height runs carrying 45-degree angles "
             "(Sonic 2's shapes 251..254, see s2_hpz_solo's baseline); RULE B = 16-px "
             "pinholes in Wing Fortress, Chemical Plant and Oil Ocean floors (s2_wfz_solo, "
             "s2_mtz_cpz, s2_ooz_solo). Kept as Sonic 2 drew them: repainting donor "
             "collision is not a clip bake's call. MEASURED by collision_consistency.check() "
             "on this act's bake.")
    doc = {"_comment": "Read by tools/collision_consistency.py as a second --baseline in "
                       "S2CLIP=s2_woven builds only (build.sh's collision-consistency block). "
                       "Keys are violation_key()'s: section-local, so this file must never "
                       "be passed to a canonical build. GENERATED by "
                       "docs/research/2026-09-27-mega-act-woven/build_woven_act.py baseline.",
           "why": why, "known_violations": entries}
    with open(out_path, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(f"wrote {out_path}: {len(entries)} entries; {why[:400]}")


if __name__ == "__main__":
    sys.exit(main())
