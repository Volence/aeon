#!/usr/bin/env python3
"""render_connector.py — draw one connector of a clip manifest with its neighbourhood, the way
plane A composes it: zone cells in their own palette, connector and fill cells from the
corridor sheet on CRAM line 0, transparent pixels (where that zone's BACKGROUND would show)
in flat magenta. Plane B is not drawn. Marks the crossing c and the core / margin / slack split
(cover_measure.py's terms) as coloured ticks along the connector's axis.

    python3 docs/research/2026-09-28-woven-cover/render_connector.py MANIFEST CONNECTOR OUT.png [PAD]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import clip_camera            # noqa: E402
import clip_manifest as CM    # noqa: E402
import clip_rom_bake as CRB   # noqa: E402

MAGENTA = (255, 0, 255)
T = CM.TILE_PX


def rgb(c3):
    return tuple(int(v) * 36 for v in c3)


def main(path, cid, out, pad=320):
    act = CM.load(path)
    root = CM._root(None)
    art = CM.connector_art(act, root)
    sheet = art["sheet"]
    line0 = CM._palette_lines(open(CM.LINE0_PALETTE, "rb").read()[:32])[0]
    conns = list(act.corridors) + list(act.shafts)
    k = next(c for c in conns if c.id == cid)
    ax = "y" if k in act.shafts else "x"
    x0, y0, w, h = k.dst
    if ax == "x":
        X0, X1, Y0, Y1 = x0 - pad, x0 + w + pad, y0, y0 + h
    else:
        X0, X1, Y0, Y1 = x0 - 160, x0 + w + 160, y0 - pad, y0 + h + pad
    X0, Y0 = max(0, X0), max(0, Y0)
    img = np.zeros((Y1 - Y0, X1 - X0, 3), dtype=np.uint8)
    img[:] = MAGENTA

    def put_words(words, ox, oy):
        for ty in range(words.shape[0]):
            for tx in range(words.shape[1]):
                px, py = ox + tx * T, oy + ty * T
                if not (X0 <= px < X1 and Y0 <= py < Y1):
                    continue
                wd = int(words[ty, tx])
                t = sheet[(wd & 0x7FF) * 32:(wd & 0x7FF) * 32 + 32]
                for yy in range(8):
                    for xx in range(8):
                        b = t[yy * 4 + xx // 2]
                        c = (b >> 4) if xx % 2 == 0 else (b & 15)
                        if c:
                            img[py - Y0 + yy, px - X0 + xx] = rgb(line0[c])

    fm = CM.fill_mask(act)
    fw = art["fill_word"]
    if fw is not None:
        for ty in range(Y0 // T, Y1 // T):
            for tx in range(X0 // T, X1 // T):
                if fm[ty, tx]:
                    put_words(np.array([[fw]], dtype=np.uint16), tx * T, ty * T)
    for co, (words, _) in zip(act.corridors, art["corridors"]):
        put_words(words, co.dst[0], co.dst[1])
    for sh, (words, _) in zip(act.shafts, art["shafts"]):
        put_words(words, sh.dst[0], sh.dst[1])
    for cl in act.clips:
        ix0, iy0 = max(X0, cl.dst[0]), max(Y0, cl.dst[1])
        ix1, iy1 = min(X1, cl.dst[0] + cl.dst[2]), min(Y1, cl.dst[1] + cl.dst[3])
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        sx, sy = ix0 - cl.dst[0] + cl.src[0], iy0 - cl.dst[1] + cl.src[1]
        px = CM.donor_pixels(root, cl.tree_key[0], cl.tree_key[1],
                             (sx, sy, ix1 - ix0, iy1 - iy0), act.section_tiles)
        for yy, row in enumerate(px):
            for xx, p in enumerate(row):
                if p is not None:
                    img[iy0 - Y0 + yy, ix0 - X0 + xx] = rgb(p)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    frames = CRB.crossing_frames(act)
    cam = clip_camera.constants()
    for x in CRB.connector_crossings(act, frames):
        if x["id"] != cid:
            continue
        half = cam["CAM_SCREEN_HALF_W"] if ax == "x" else cam["CAM_SCREEN_HALF_H"]
        step = cam["CAM_MAX_X_STEP"] if ax == "x" else cam["CAM_MAX_Y_STEP"]
        core = half + step * CRB.SNAP_FRAMES
        marks = [(x["c"], (255, 255, 255)),
                 (x["c"] - core, (255, 64, 64)), (x["c"] + core, (255, 64, 64)),
                 (x["c"] - x["need_before"], (255, 200, 0)),
                 (x["c"] + x["need_after"], (255, 200, 0))]
        for v, col in marks:
            if ax == "x":
                d.line([(v - X0, 0), (v - X0, 12)], fill=col, width=3)
                d.line([(v - X0, img.shape[0] - 12), (v - X0, img.shape[0])], fill=col, width=3)
            else:
                d.line([(0, v - Y0), (12, v - Y0)], fill=col, width=3)
                d.line([(img.shape[1] - 12, v - Y0), (img.shape[1], v - Y0)], fill=col, width=3)
    im.save(out)
    print(f"{out}: act x {X0}..{X1} y {Y0}..{Y1}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], *(int(a) for a in sys.argv[4:5]))
