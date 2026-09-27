#!/usr/bin/env python3
"""Draw the woven layout (layout.json) to scale, with each clip's real foreground inside its box.

Called by `woven.py render`. Clip thumbnails come from the v1 proposal's renderer
(docs/research/2026-09-27-mega-act-layout/render_layout.py `ZoneTree.render`: foreground plane
only, colour 0 shows the zone backdrop, CRAM line 0 cells in flat magenta). The neutral fill is
drawn in the two looks the report proposes, both on CRAM line 0 (the character line, which no
region install writes):
  * the CLOUD BAND under and around Wing Fortress: Emerald Hill's own background sky and clouds,
    RECOLOURED to line 0 with the tunnel's rule (`clip_manifest._recolour_to_line0`, nearest
    line-0 colour) and every transparent pixel painted line-0 index 5 ($0E66, a mid blue), so
    no background shows through. It is a LOOK sample, not a bake product;
  * ROCK everywhere else: the tunnel's grey (`CORRIDOR_COLOURS` fill).
The region boundaries drawn in white are the ones `woven.py check` plans (where the palette and
background switch); the lanes are the connectors, coloured by what their length is set by.
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "docs/research/2026-09-27-mega-act-layout"))
import render_layout as RL                 # noqa: E402

SEC = 2048
LINE0 = None


def line0():
    import clip_manifest as CM
    return CM._palette_lines(open(CM.LINE0_PALETTE, "rb").read()[:32])[0]


def cloud_swatch(w_px, h_px):
    """A (h, w, 3) uint8 image: Emerald Hill's background sky and clouds (its lowered plane's
    first 16 tile rows, `clip_bg_lower.lower`), RECOLOURED onto CRAM line 0 by the tunnel's
    rule, transparent pixels painted line-0 index 5, tiled over the band."""
    import clip_bg_lower as L
    import clip_manifest as CM
    words, tiles, _info = L.lower("s2disasm", "EHZ")
    zpal = CM._palette_lines(b"\0" * 32 + (RL.DONORS / "s2disasm/EHZ/palette.bin").read_bytes())
    l0 = line0()                                   # 3-bit channels, as clip_manifest reads it
    hole = 5                                       # $0E66, a mid blue
    rows_n, cols_n = 16, 64
    idx = np.full((rows_n * 8, cols_n * 8), hole, dtype=np.uint8)
    for r in range(rows_n):
        for c in range(cols_n):
            wd = words[r * 64 + c]
            if not wd:
                continue
            px = L._flip(L._unpack(tiles[wd & 0x7FF]), wd)
            ln = (wd >> 13) & 3
            for y in range(8):
                for x in range(8):
                    v = px[y][x]
                    if v and ln:
                        idx[r * 8 + y, c * 8 + x] = CM._nearest_line0(zpal[ln][v], l0)
    lut = np.array([[ch * 36 for ch in col] for col in l0], dtype=np.uint8)
    img = lut[idx]
    out = np.zeros((h_px, w_px, 3), dtype=np.uint8)
    for y in range(0, h_px, img.shape[0]):
        for x in range(0, w_px, img.shape[1]):
            hh = min(img.shape[0], h_px - y)
            ww = min(img.shape[1], w_px - x)
            out[y:y + hh, x:x + ww] = img[:hh, :ww]
    return out


COL = {"same": (80, 220, 120), "change": (240, 170, 40), "sealed": (150, 150, 160)}


def render(spec, out_path):
    import woven
    S = spec["scale"]
    gw, gh = spec["grid"]
    W, H = gw * SEC // S, gh * SEC // S
    bx = max(c["dst"][0] + c["src"][2] for c in spec["clips"])
    by = max(c["dst"][1] + c["src"][3] for c in spec["clips"])
    top, left, right, bottom = 78, 60, 330, 210
    im = Image.new("RGB", (W + left + right, H + top + bottom), (24, 26, 32))
    d = ImageDraw.Draw(im)
    fT, fL, fS = RL.font(22), RL.font(14), RL.font(12)
    d.text((left, 12), spec["title"], fill=(240, 240, 240), font=fT)
    d.text((left, 44), spec["subtitle"], fill=(170, 170, 170), font=fS)
    # neutral fill: clouds in the sky band, rock below it
    sky_bottom = max(c["dst"][1] for c in spec["clips"] if c["zone"] != "WFZ"
                     and c["dst"][1] < 3000)
    rock = tuple(int(v) * 36 for v in line0()[9])
    d.rectangle([left, top, left + bx // S - 1, top + by // S - 1], fill=rock)
    cs = cloud_swatch(bx, sky_bottom)
    cim = Image.fromarray(cs, "RGB").resize((bx // S, sky_bottom // S), Image.BOX)
    im.paste(cim, (left, top))
    # clips
    trees = {}
    for c in spec["clips"]:
        t = trees.setdefault(c["tree"], RL.ZoneTree(c["tree"]))
        sx, sy, w, h = c["src"]
        dx, dy = c["dst"]
        im.paste(t.render(sx, sy, w, h, S), (left + dx // S, top + dy // S))
    # planned region boundaries (where palette + background switch), inside the fill only
    reg = woven.region_all(spec)[3]
    zone_cells = np.zeros(reg.shape, dtype=bool)
    for c in spec["clips"]:
        x0, y0 = c["dst"][0] // 8, c["dst"][1] // 8
        zone_cells[y0:y0 + c["src"][3] // 8, x0:x0 + c["src"][2] // 8] = True
    k = S // 8
    r = reg[::k, ::k]
    zc = zone_cells[::k, ::k]
    edge = np.zeros(r.shape, dtype=bool)
    edge[:, 1:] |= (r[:, 1:] != r[:, :-1]) & (r[:, 1:] >= 0) & (r[:, :-1] >= 0)
    edge[1:, :] |= (r[1:, :] != r[:-1, :]) & (r[1:, :] >= 0) & (r[:-1, :] >= 0)
    edge &= ~zc
    ys, xs = np.nonzero(edge)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if x < bx // S and y < by // S:
            im.putpixel((left + x, top + y), (255, 255, 255))
    # clip frames + labels
    for c in spec["clips"]:
        sx, sy, w, h = c["src"]
        dx, dy = c["dst"]
        X, Y = left + dx // S, top + dy // S
        col = (230, 80, 60) if c["route"] == "must" else (70, 150, 230)
        d.rectangle([X, Y, X + w // S - 1, Y + h // S - 1], outline=col, width=2)
        for i, text in enumerate((c["label"], f"{w}x{h}  {c['what']}")):
            f = fL if i == 0 else fS
            tw = int(d.textlength(text, font=f))
            d.rectangle([X + 3, Y + 3 + i * 19, X + 9 + tw, Y + 20 + i * 19], fill=(0, 0, 0))
            d.text((X + 6, Y + 5 + i * 19), text, fill=(255, 255, 255), font=f)
    # lanes
    for k_ in spec["connectors"]:
        x, y, w, h = k_["lanes"][0]
        kind = "same" if "same" in k_["rule"] else "change"
        col = COL[kind]
        X, Y = left + x // S, top + y // S
        d.rectangle([X, Y, X + max(w // S, 4) - 1, Y + max(h // S, 4) - 1], fill=col,
                    outline=(0, 0, 0))
        length = k_["rule"].split(": ")[-1]
        label = f"{k_['id']} {length}"
        tw = int(d.textlength(label, font=fS))
        if w > h:
            lx, ly = X + (max(w // S, 4) - tw) // 2, Y - 16
        else:
            lx, ly = X + max(w // S, 4) + 3, Y + max(h // S, 4) // 2 - 7
        d.rectangle([lx - 2, ly - 1, lx + tw + 2, ly + 14], fill=(0, 0, 0))
        d.text((lx, ly), label, fill=col, font=fS)
    # section grid + frame
    for sxg in range(gw + 1):
        X = left + sxg * SEC // S
        d.line([(X, top), (X, top + H)], fill=(60, 64, 76), width=1)
        if sxg < gw:
            d.text((X + 3, top + H + 3), f"x{sxg * SEC}", fill=(120, 120, 130), font=fS)
    for syg in range(gh + 1):
        Y = top + syg * SEC // S
        d.line([(left, Y), (left + W, Y)], fill=(60, 64, 76), width=1)
        if syg < gh:
            d.text((4, Y + 3), f"y{syg * SEC}", fill=(120, 120, 130), font=fS)
    sxp, syp = spec["spawn"]
    X, Y = left + sxp // S, top + syp // S
    d.ellipse([X - 6, Y - 6, X + 6, Y + 6], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    d.text((X + 9, Y - 7), "START", fill=(255, 255, 255), font=fL)
    # side legend
    lx = left + W + 16
    ly = top
    d.text((lx, ly), "CONNECTORS (lane = where you cross)", fill=(240, 240, 240), font=fL)
    ly += 22
    for k_ in spec["connectors"]:
        kind = "same" if "same" in k_["rule"] else "change"
        text = f"{k_['id']:3s} {k_['kind']:6s} {'-'.join(k_['joins'])}"
        d.rectangle([lx, ly + 2, lx + 12, ly + 12], fill=COL[kind])
        d.text((lx + 18, ly), text, fill=(230, 230, 230), font=fS)
        d.text((lx + 18, ly + 14), f"   {k_['rule']}", fill=(160, 160, 170), font=fS)
        d.text((lx + 18, ly + 28), f"   {k_['how']}", fill=(160, 160, 170), font=fS)
        ly += 46
    ly += 6
    for text, col in (("green: both zones' backgrounds co-resident", COL["same"]),
                      ("orange: background tiles reloaded in the lane", COL["change"])):
        d.rectangle([lx, ly + 2, lx + 12, ly + 12], fill=col)
        d.text((lx + 18, ly), text, fill=(220, 220, 220), font=fS)
        ly += 18
    d.line([(lx, ly + 8), (lx + 12, ly + 8)], fill=(255, 255, 255), width=1)
    d.text((lx + 18, ly), "white: planned region boundary (palette +", fill=(220, 220, 220),
           font=fS)
    d.text((lx + 18, ly + 14), "background switch), inside the fill", fill=(220, 220, 220),
           font=fS)
    ly += 34
    blobs = spec["blobs"]
    d.text((lx, ly), "BG blobs (376-tile arena):", fill=(220, 220, 220), font=fS)
    ly += 16
    for b, zs in blobs.items():
        n = sum(spec["bg_tiles"][z] for z in zs)
        d.text((lx + 8, ly), f"{b}: {' + '.join(zs)} = {n}", fill=(170, 170, 180), font=fS)
        ly += 15
    # notes under the map
    ny = top + H + 26
    for line in spec.get("notes", []):
        d.text((left, ny), line, fill=(200, 200, 200), font=fS)
        ny += 17
    im.save(out_path)
    print(out_path, im.size)
