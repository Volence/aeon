"""Render S2 zone collision, plane A vs plane B, with Obj03 lines, to PNG.

red = solid on A only, blue = B only, grey = both. Top-only solidity drawn lighter.
Green line = Obj03 (label = fwd/back path).
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s2_zone_convert as C  # noqa
import s2_donor  # noqa
import obj03  # noqa

prof = open(os.path.join(REPO, "games/sonic4/data/collision/base_s2/heightmaps.bin"), "rb").read()


def covers(h, row):
    if h == 0:
        return False
    if h == 16:
        return True
    if h < 0x80:
        return row >= 16 - h
    return row < (256 - h)


_cache = {}


def block_mask(word):
    """16x16 bool mask and solidity for one per-plane cell word."""
    shape = word & 0x3FF
    sol = (word >> 12) & 3
    key = (shape, word & 0xC00)
    if key not in _cache:
        hts = list(prof[shape * 16:shape * 16 + 16])
        if word & 0x400:
            hts = hts[::-1]
        if word & 0x800:
            hts = [h if h in (0, 16) else (256 - h) & 0xFF for h in hts]
        m = np.zeros((16, 16), bool)
        for c in range(16):
            for r in range(16):
                m[r, c] = covers(hts[c], r)
        _cache[key] = m
    return _cache[key], sol


def masks(zone):
    a, b = C.rederive_zone_collision(zone, s2_donor.S2_FINAL)
    out = []
    for g in (a, b):
        H, W = g.shape[0] // 2, g.shape[1] // 2
        full = np.zeros((H * 16, W * 16), np.uint8)  # 0 air, 1 top-only, 3 all/lrb
        for by in range(H):
            for bx in range(W):
                w = int(g[by * 2, bx * 2])
                if (w >> 12) & 3 == 0:
                    continue
                m, sol = block_mask(w)
                full[by * 16:by * 16 + 16, bx * 16:bx * 16 + 16] = np.where(m, sol, 0)
        out.append(full)
    return out


def render(zone, x0, y0, x1, y1, path, scale=1, zone_w=10**6, zone_h=10**6):
    A, B = masks(zone)
    a = A[y0:y1, x0:x1]
    b = B[y0:y1, x0:x1]
    img = np.full(a.shape + (3,), 255, np.uint8)
    both = (a > 0) & (b > 0)
    img[(a > 0) & ~both] = (220, 40, 40)
    img[(b > 0) & ~both] = (40, 80, 230)
    img[both] = (110, 110, 110)
    # top-only lighter
    img[(a == 1) & ~both] = (250, 160, 160)
    img[(b == 1) & ~both] = (160, 180, 250)
    im = Image.fromarray(img).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for r in obj03.rows(zone, zone_w, zone_h)[1]:
        x, y, h = r["x"], r["y"], r["half"]
        if r["horiz"]:
            p = [(x - h - x0) * scale, (y - y0) * scale, (x + h - x0) * scale, (y - y0) * scale]
            lab = f"v{r['fwd']} ^{r['back']}"
        else:
            p = [(x - x0) * scale, (y - h - y0) * scale, (x - x0) * scale, (y + h - y0) * scale]
            lab = f">{r['fwd']} <{r['back']}{' g' if r['grounded'] else ''}"
        d.line(p, fill=(0, 170, 0), width=2)
        d.text((p[0] + 3, p[1] + 2), lab, fill=(0, 120, 0))
    im.save(path)


if __name__ == "__main__":
    zone = sys.argv[1]
    x0, y0, x1, y1 = map(int, sys.argv[2:6])
    scale = int(sys.argv[7]) if len(sys.argv) > 7 else 1
    render(zone, x0, y0, x1, y1, sys.argv[6], scale=scale)
