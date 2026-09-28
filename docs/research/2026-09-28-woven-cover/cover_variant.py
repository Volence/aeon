#!/usr/bin/env python3
"""cover_variant.py — write a SCRATCH variant of the woven manifest for the cover research.
Never committed as an act change: the note's §8 restores the tree after every bake.

    python3 docs/research/2026-09-28-woven-cover/cover_variant.py BASE.json OUT.json VARIANT...

VARIANTS (any combination):
  wfz_c1:N   a new Wing Fortress clip under the deck over shaft wfz_to_ehz, N px of donor rows
             1792.. (the empty sky Sonic 2 has under its hull there), the shaft shortened by N
  wfz_c2:N   the same over shaft wfz_to_mtz
  wide:W     the new clips W px wide, centred on their shaft (default: the shaft's own width)
  art:CID:ZONE:WX,WY:BX,BY   corridor CID's tunnel art from ZONE (32x32 wall_src at WX,WY and
             back_src at BX,BY, donor px), everything else unchanged
"""
import json
import sys

WFZ_DONOR_DX = 1024 - 1536          # act x -> WFZ donor x (wfz_deck: src x 1024 at dst 1536)
WFZ_BOTTOM_DONOR = 1792             # wfz_deck's src bottom
WFZ_DECK_BOTTOM_ACT = 1408


def main(base, out, variants):
    m = json.load(open(base))
    wide = None
    for v in variants:
        if v.startswith("wide:"):
            wide = int(v.split(":")[1])
    for v in variants:
        kind, _, arg = v.partition(":")
        if kind in ("wfz_c1", "wfz_c2"):
            sid = {"wfz_c1": "wfz_to_ehz", "wfz_c2": "wfz_to_mtz"}[kind]
            n = int(arg)
            sh = next(s for s in m["shafts"] if s["id"] == sid)
            r = sh["dst_rect"]
            assert r["y"] == WFZ_DECK_BOTTOM_ACT, r
            w = wide or r["w"]
            x = r["x"] + r["w"] // 2 - w // 2
            m["clips"].append({
                "id": f"wfz_over_{sid}", "donor": "s2disasm", "zone": "WFZ",
                "src_rect": {"x": x + WFZ_DONOR_DX, "y": WFZ_BOTTOM_DONOR, "w": w, "h": n},
                "dst_rect": {"x": x, "y": WFZ_DECK_BOTTOM_ACT, "w": w, "h": n},
                "unaligned_dst_reason": "SCRATCH (research/woven-cover): Wing Fortress's own "
                                        "sky under its hull, in the shaft's slack"})
            r["y"] += n
            r["h"] -= n
        elif kind == "cpz_c3":
            # Chemical Plant's own rows ABOVE its clip (donor y src.y - N .. src.y) over shaft
            # wfz_to_cpz, the shaft shortened from the bottom by N. Same paste offset (SC0).
            n = int(arg)
            sh = next(s for s in m["shafts"] if s["id"] == "wfz_to_cpz")
            r = sh["dst_rect"]
            cpz = next(c for c in m["clips"] if c["id"] == "cpz_loop_cluster")
            assert r["y"] + r["h"] == cpz["dst_rect"]["y"], (r, cpz["dst_rect"])
            assert cpz["src_rect"]["y"] >= n, cpz["src_rect"]
            w = wide or r["w"]
            x = r["x"] + r["w"] // 2 - w // 2
            sx = x - cpz["dst_rect"]["x"] + cpz["src_rect"]["x"]
            m["clips"].append({
                "id": "cpz_over_wfz_to_cpz", "donor": "s2disasm", "zone": "CPZ",
                "src_rect": {"x": sx, "y": cpz["src_rect"]["y"] - n, "w": w, "h": n},
                "dst_rect": {"x": x, "y": cpz["dst_rect"]["y"] - n, "w": w, "h": n},
                "unaligned_dst_reason": "SCRATCH (research/woven-cover): Chemical Plant's own "
                                        "sky above its clip, in the shaft's slack"})
            if cpz.get("music"):
                m["clips"][-1]["music"] = cpz["music"]     # R3: one song per zone
            r["h"] -= n
        elif kind == "art":
            cid, zone, wxy, bxy = arg.split(":")
            wx, wy = map(int, wxy.split(","))
            bx, by = map(int, bxy.split(","))
            co = next(c for c in m["corridors"] if c["id"] == cid)
            co["tunnel"]["art"] = {"donor": "s2disasm", "zone": zone,
                                   "wall_src": {"x": wx, "y": wy, "w": 32, "h": 32},
                                   "back_src": {"x": bx, "y": by, "w": 32, "h": 32}}
        elif kind == "wide":
            pass
        elif kind == "report":
            # SCRATCH ONLY: Z2's margin reported instead of enforced, so a connector cut
            # below the model can be BUILT and flown (the witness is then the judge)
            m["crossing_overrides"]["crossing_margin"] = "report"
        else:
            raise SystemExit(f"unknown variant {v!r}")
    with open(out, "w") as fh:
        json.dump(m, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
