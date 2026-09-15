#!/usr/bin/env python3
"""E3 measurement: unique BG tile counts for one picture, and for two deduped together.

Reuses tools/png_to_bg_override.py's OWN quantise + flip-canonical dedup
(`load_lock_palettes`, `quantise_tile`, `canonical`) so the numbers are the
shipped importer's numbers and not a re-implementation. The only thing NOT
reused is `check_tile_budget`, which is a POLICY REFUSAL (it exits non-zero
above BG_STATIC_TILE_BUDGET) and not part of the count — the count is taken
before it would fire, exactly where the importer itself takes it.

Usage:
  python3 docs/superpowers/notes/2026-09-15-regions-p2-e3-measure.py \
      --lines 2,3 a.png [b.png ...]

Prints per-image unique counts, the union count when >1 image is given, the
cross-picture saving, and (with --emit-json DIR) writes an override JSON per
image plus a union JSON whose `tiles` is the shared blob, so the real
tools/inject_editor_bg.py can be run over them and the 2-byte big-endian
BYTE-length header of bg_tiles.bin read back (tiles = header / 32).
"""
import argparse, json, os, sys

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))

from png_to_bg_override import (load_lock_palettes, quantise_tile, canonical,
                                flip_variants, PLANE_W, PLANE_H)
from vram_map import BG_TILE_CAPACITY, BG_BAND_RESERVE, BG_STATIC_TILE_BUDGET


def quantise_image(path, palettes):
    """[(idx8x8, cram_line)] in row-major tile order, plus (tw, th)."""
    img = np.array(Image.open(path).convert("RGB"))
    h, w, _ = img.shape
    assert w % 8 == 0 and h % 8 == 0, f"{path}: {w}x{h} not tile-aligned"
    tw, th = w // 8, h // 8
    art = [quantise_tile(img[r * 8:r * 8 + 8, c * 8:c * 8 + 8], palettes)
           for r in range(th) for c in range(tw)]
    return art, tw, th


def intern(art, blob, key_to_local):
    """Fold `art` into the SHARED (blob, key_to_local); return its layout words.

    One dict across every image is what makes a union a union: the second
    picture's tiles are looked up in the first picture's keys.
    """
    words = []
    for idx, line in art:
        key = canonical(idx)
        if key not in key_to_local:
            key_to_local[key] = len(blob)
            blob.append(np.frombuffer(key, np.uint8).reshape(8, 8))
        local = key_to_local[key]
        for flag, var in flip_variants(blob[local]).items():
            if var.tobytes() == idx.tobytes():
                break
        words.append((line & 3) << 13 | (1 if "V" in flag else 0) << 12 |
                     (1 if "H" in flag else 0) << 11 | (local & 0x7FF))
    return words


def plane_layout(words, tw, th):
    """Tile the image over the 64x64 plane the way png_to_bg_override does
    (voffset 0, full-height art wraps)."""
    full_height = (th == PLANE_H)
    out = []
    for r in range(PLANE_H):
        ar = r % th if full_height else min(max(r, 0), th - 1)
        for c in range(PLANE_W):
            out.append(int(words[ar * tw + (c % tw)]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--lines", default="2,3")
    ap.add_argument("--emit-json", default=None)
    a = ap.parse_args()

    palettes = load_lock_palettes([int(x) for x in a.lines.split(",")])
    print(f"capacity {BG_TILE_CAPACITY}  band_reserve {BG_BAND_RESERVE}  "
          f"static budget {BG_STATIC_TILE_BUDGET}  lines {a.lines}")

    singles, arts = [], []
    for p in a.images:
        art, tw, th = quantise_image(p, palettes)
        arts.append((p, art, tw, th))
        blob, k2l = [], {}
        intern(art, blob, k2l)
        singles.append(len(blob))
        print(f"single {os.path.basename(p)}: {len(blob)} unique tiles "
              f"({tw}x{th} cells)")
        del blob, k2l

    if len(a.images) > 1:
        ublob, uk2l = [], {}
        ulayouts = []
        for i, (p, art, tw, th) in enumerate(arts):
            before = len(ublob)
            words = intern(art, ublob, uk2l)
            ulayouts.append((p, words, tw, th))
            added = len(ublob) - before
            print(f"  after {os.path.basename(p)}: union {len(ublob)} "
                  f"(+{added} new, {singles[i] - added} shared with earlier)")
        union = len(ublob)
        naive = sum(singles)
        print(f"union {union}  naive sum {naive}  shared saving {naive - union}")
        if union == naive:
            print("  !! union == naive sum: NO cross-picture sharing at all — "
                  "investigate before reporting")
        if a.emit_json:
            os.makedirs(a.emit_json, exist_ok=True)
            tiles = [t.reshape(-1).astype(int).tolist() for t in ublob]
            for p, words, tw, th in ulayouts:
                name = os.path.splitext(os.path.basename(p))[0]
                with open(os.path.join(a.emit_json, f"union_{name}.json"), "w") as f:
                    json.dump({"layout": plane_layout(words, tw, th),
                               "tiles": tiles}, f)
                print(f"  wrote union_{name}.json (union blob, {len(tiles)} tiles)")

    if a.emit_json:
        os.makedirs(a.emit_json, exist_ok=True)
        for p, art, tw, th in arts:
            blob, k2l = [], {}
            words = intern(art, blob, k2l)
            name = os.path.splitext(os.path.basename(p))[0]
            with open(os.path.join(a.emit_json, f"single_{name}.json"), "w") as f:
                json.dump({"layout": plane_layout(words, tw, th),
                           "tiles": [t.reshape(-1).astype(int).tolist() for t in blob]}, f)
            print(f"  wrote single_{name}.json ({len(blob)} tiles)")


if __name__ == "__main__":
    main()
