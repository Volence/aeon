#!/usr/bin/env python3
"""Draw the mega-act layout proposal, and look at the converted zones to pick clips from.

A DRAWING TOOL for a proposal, not a bake and not a gate. It reads the converted donor trees
(`games/sonic4/data/donors/<donor>/<ZONE>/`, written by `tools/s2_zone_convert.py`, gitignored)
and renders nametable words through each zone's own tileset and palette. It never writes into
the repo tree except where told (`--out`).

    python3 render_layout.py zone  s2disasm/EHZ --out DIR          # whole zone, 1/8 scale, 1024-px grid
    python3 render_layout.py map   layout.json --out map.png       # the proposal picture

Rendering rules (a thumbnail, stated so nobody mistakes it for the engine's picture):
  * colour index 0 of any line is transparent and shows the zone's backdrop (CRAM line 2
    entry 0 of the zone palette, which is what Sonic 2's `$8720` backdrop register selects);
  * CRAM line 0 is the CHARACTER's line in aeon and no zone install writes it; cells on it are
    drawn in a flat magenta so the §5.3 defect is visible rather than hidden;
  * foreground plane only. No background plane, no objects, no priority compositing.
"""
import argparse
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = pathlib.Path(__file__).resolve().parents[3]
DONORS = REPO / "games/sonic4/data/donors"
SEC = 256  # tiles per section edge


def md_colour(w):
    """Genesis CRAM word 0000BBB0GGG0RRR0 -> (r, g, b)."""
    r = (w >> 1) & 7
    g = (w >> 5) & 7
    b = (w >> 9) & 7
    return (r * 36, g * 36, b * 36)


class ZoneTree:
    def __init__(self, rel):
        self.dir = DONORS / rel
        self.zm = json.loads((self.dir / "zone.json").read_text())
        ts = np.frombuffer((self.dir / "tileset.bin").read_bytes(), dtype=np.uint8)
        n = len(ts) // 32
        ts = ts.reshape(n, 8, 4)
        px = np.empty((n, 8, 8), dtype=np.uint8)
        px[:, :, 0::2] = ts >> 4
        px[:, :, 1::2] = ts & 15
        self.tiles = px
        pal = np.frombuffer((self.dir / "palette.bin").read_bytes(), dtype=">u2")
        lut = np.zeros((4, 16, 3), dtype=np.uint8)
        lut[0, :] = (255, 0, 255)
        for line in range(3):
            for i in range(16):
                lut[line + 1, i] = md_colour(int(pal[line * 16 + i]))
        self.lut = lut
        self.backdrop = tuple(int(v) for v in lut[2, 0])
        gw, gh = self.zm["grid"]["w"], self.zm["grid"]["h"]
        words = np.zeros((gh * SEC, gw * SEC), dtype=np.uint16)
        for s in self.zm["sections"]:
            raw = (self.dir / f"section_{s['n']}.tiles.bin").read_bytes()
            words[s["sy"] * SEC:(s["sy"] + 1) * SEC, s["sx"] * SEC:(s["sx"] + 1) * SEC] = \
                np.frombuffer(raw, dtype=">u2").reshape(SEC, SEC)
        self.words = words
        self.crop_tiles = self.zm["extent"]["crop_tiles"]
        self.painted_tiles = self.zm["extent"]["painted_bbox_tiles"]

    def render(self, x, y, w, h, scale):
        """Render donor px rect (multiples of 8) and downscale by integer `scale`."""
        c0, r0, cw, ch = x // 8, y // 8, w // 8, h // 8
        wd = self.words[r0:r0 + ch, c0:c0 + cw].astype(np.int32)
        idx = wd & 0x7FF
        hf = (wd >> 11) & 1
        vf = (wd >> 12) & 1
        line = (wd >> 13) & 3
        t = self.tiles[np.minimum(idx, len(self.tiles) - 1)]            # ch,cw,8,8
        t = np.where(hf[:, :, None, None].astype(bool), t[:, :, :, ::-1], t)
        t = np.where(vf[:, :, None, None].astype(bool), t[:, :, ::-1, :], t)
        img = self.lut[line[:, :, None, None], t]                         # ch,cw,8,8,3
        img[t == 0] = self.backdrop
        img = img.transpose(0, 2, 1, 3, 4).reshape(ch * 8, cw * 8, 3)
        im = Image.fromarray(img, "RGB")
        if scale > 1:
            im = im.resize((im.width // scale, im.height // scale), Image.BOX)
        return im


def font(size):
    for p in ("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if pathlib.Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def mode_zone(a):
    z = ZoneTree(a.tree)
    x0, x1, y0, y1 = z.painted_tiles
    x0, y0 = 0, 0
    im = z.render(x0 * 8, y0 * 8, (x1 - x0) * 8, (y1 - y0) * 8, a.scale)
    d = ImageDraw.Draw(im)
    f = font(11)
    step = 1024
    for gx in range(0, (x1 - x0) * 8 + 1, step):
        d.line([(gx // a.scale, 0), (gx // a.scale, im.height)], fill=(255, 255, 255), width=1)
        d.text((gx // a.scale + 2, 2), str(gx), fill=(255, 255, 0), font=f)
    for gy in range(0, (y1 - y0) * 8 + 1, 512):
        d.line([(0, gy // a.scale), (im.width, gy // a.scale)], fill=(255, 255, 255), width=1)
        d.text((2, gy // a.scale + 2), str(gy), fill=(255, 255, 0), font=f)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    p = out / (a.tree.replace("/", "_") + ".png")
    im.save(p)
    print(p, im.size)


PALETTE = {
    "must": (230, 80, 60), "optional": (70, 150, 230), "shaft": (230, 170, 40),
}


def mode_map(a):
    spec = json.loads(pathlib.Path(a.layout).read_text())
    S = spec["scale"]                      # world px per image px
    gw, gh = spec["grid"]                  # sections
    W, H = gw * 2048 // S, gh * 2048 // S
    top, left, right, bottom = 70, 50, 20, 250
    im = Image.new("RGB", (W + left + right, H + top + bottom), (24, 26, 32))
    d = ImageDraw.Draw(im)
    fT, fL, fS = font(22), font(15), font(12)
    d.text((left, 12), spec["title"], fill=(240, 240, 240), font=fT)
    d.text((left, 42), spec["subtitle"], fill=(170, 170, 170), font=fS)
    # section grid
    for sx in range(gw + 1):
        X = left + sx * 2048 // S
        d.line([(X, top), (X, top + H)], fill=(52, 56, 66), width=1)
        if sx < gw:
            d.text((X + 3, top + H + 3), f"{sx * 2048}", fill=(110, 110, 120), font=fS)
    for sy in range(gh + 1):
        Y = top + sy * 2048 // S
        d.line([(left, Y), (left + W, Y)], fill=(52, 56, 66), width=1)
        if sy < gh:
            d.text((4, Y + 3), f"y{sy * 2048}", fill=(110, 110, 120), font=fS)
    trees = {}
    # clips
    for c in spec["clips"]:
        t = trees.setdefault(c["tree"], ZoneTree(c["tree"]))
        sx, sy, w, h = c["src"]
        dx, dy = c["dst"]
        thumb = t.render(sx, sy, w, h, S)
        X, Y = left + dx // S, top + dy // S
        im.paste(thumb, (X, Y))
        col = PALETTE["must"] if c["route"] == "must" else PALETTE["optional"]
        d.rectangle([X, Y, X + w // S - 1, Y + h // S - 1], outline=col, width=3)
        label = f"{c['label']}"
        d.rectangle([X + 3, Y + 3, X + 9 + int(d.textlength(label, font=fL)), Y + 23],
                    fill=(0, 0, 0))
        d.text((X + 6, Y + 5), label, fill=(255, 255, 255), font=fL)
        sub = f"{w}x{h} px  |  {c['what']}"
        d.rectangle([X + 3, Y + 25, X + 9 + int(d.textlength(sub, font=fS)), Y + 41],
                    fill=(0, 0, 0))
        d.text((X + 6, Y + 27), sub, fill=(220, 220, 220), font=fS)
    # connectors
    for k in spec["connectors"]:
        x, y, w, h = k["rect"]
        X, Y = left + x // S, top + y // S
        col = PALETTE["shaft"] if k["kind"] == "shaft" else (
            PALETTE["must"] if k["route"] == "must" else PALETTE["optional"])
        d.rectangle([X, Y, X + max(w // S, 3) - 1, Y + max(h // S, 3) - 1], fill=col)
        if k["kind"] == "shaft":
            rc = PALETTE["must"] if k["route"] == "must" else PALETTE["optional"]
            d.rectangle([X, Y, X + max(w // S, 3) - 1, Y + max(h // S, 3) - 1], outline=rc,
                        width=3)
        tx, ty = X + max(w // S, 3) + 3, Y
        if k.get("label_at") == "below":
            tx, ty = X, Y + max(h // S, 3) + 2
        if k.get("label_at") == "above":
            tx, ty = X, Y - 16
        d.text((tx, ty), k["id"], fill=col, font=fS)
    # seals: a clip edge that must be walled off because it faces void, not a connector
    for x, y, w, h in spec.get("seals", []):
        X, Y = left + x // S, top + y // S
        d.rectangle([X, Y, X + max(w // S, 3) - 1, Y + h // S - 1], fill=(150, 150, 160))
    # spawn
    sxp, syp = spec["spawn"]
    X, Y = left + sxp // S, top + syp // S
    d.ellipse([X - 7, Y - 7, X + 7, Y + 7], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    d.text((X + 10, Y - 8), "START", fill=(255, 255, 255), font=fL)
    # legend + notes
    ly = top + H + 24
    items = [("must-pass region / connector", PALETTE["must"]),
             ("optional (side area / second route)", PALETTE["optional"]),
             ("vertical shaft (outline = must / optional)", PALETTE["shaft"]),
             ("sealed edge (a wall, no way through)", (150, 150, 160))]
    lx = left
    for text, col in items:
        d.rectangle([lx, ly + 2, lx + 16, ly + 14], fill=col)
        d.text((lx + 22, ly), text, fill=(220, 220, 220), font=fS)
        lx += 40 + int(d.textlength(text, font=fS))
    for i, line in enumerate(spec.get("notes", [])):
        d.text((left, ly + 24 + i * 17), line, fill=(190, 190, 190), font=fS)
    im.save(a.out)
    print(a.out, im.size)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("zone")
    p.add_argument("tree")
    p.add_argument("--out", required=True)
    p.add_argument("--scale", type=int, default=8)
    p = sub.add_parser("map")
    p.add_argument("layout")
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    {"zone": mode_zone, "map": mode_map}[a.mode](a)


if __name__ == "__main__":
    sys.exit(main())
