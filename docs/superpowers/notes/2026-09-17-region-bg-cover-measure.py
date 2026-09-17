#!/usr/bin/env python3
"""REGION-BG-COVER-WARNING phase 1: what would each reading of "opaque cover" warn on,
for OJZ act 1 as committed today?

MEASUREMENT ONLY. It is not the warning and not a build lane. It exists so the numbers in
docs/superpowers/notes/2026-09-17-region-bg-cover-warning.md can be re-run.

Inputs (all committed, donor-free):
  * project.json                      -> tileset path, act dataPath, grid
  * <dataPath>/section_N.tiles.bin    -> Plane A nametable, 256x256 BE words, flat id row*W+col
  * games/sonic4/data/editor/ojz_tiles.bin -> raw 4bpp tiles, 32 B each (colour 0 = transparent)
  * engine constants, READ FROM SOURCE (never retyped): SCREEN_WIDTH/HEIGHT, CAM_SCREEN_HALF_W/H,
    CAM_MAX_Y_STEP (engine/system/constants.emp), CAM_MAX_X_STEP (engine/level/camera.emp,
    file-local), BG_WIPE_ROWS_PER_FRAME (engine/level/bg.emp), BG_OVERWRITE_CHUNK_BYTES
    (engine/level/bg.emp), BG_TILE_CAPACITY (engine/system/constants.emp)
  * blob byte lengths from the 2-byte headers of the committed tile blobs

The crossings are the DEBUG showcase row's four edges, both directions: the only region in the
act with its own rg_bg_tiles (act_descriptor.emp OJZ_SHOWCASE_BG_ROWS). The release table
has none (every regions.json row takes the act's tiles; REGION-BG-TILES-AUTHORING).

Usage: python3 docs/superpowers/notes/2026-09-17-region-bg-cover-measure.py
"""
import json
import math
import os
import re
import struct
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def const(path, name):
    text = open(os.path.join(REPO, path)).read()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{name}\s*=\s*(\d+)\b", text, re.M)
    if not m:
        sys.exit(f"cannot read {name} as an integer literal from {path}")
    return int(m.group(1))


SCREEN_W = const("engine/system/constants.emp", "SCREEN_WIDTH")
SCREEN_H = const("engine/system/constants.emp", "SCREEN_HEIGHT")
HALF_W = const("engine/system/constants.emp", "CAM_SCREEN_HALF_W")
HALF_H = const("engine/system/constants.emp", "CAM_SCREEN_HALF_H")
CAP_Y = const("engine/system/constants.emp", "CAM_MAX_Y_STEP")
CAP_X = const("engine/level/camera.emp", "CAM_MAX_X_STEP")
WIPE_ROWS = const("engine/level/bg.emp", "BG_WIPE_ROWS_PER_FRAME")
CHUNK = const("engine/level/bg.emp", "BG_OVERWRITE_CHUNK_BYTES")
CAPACITY_BYTES = const("engine/system/constants.emp", "BG_TILE_CAPACITY") * 32
PLANE_V_CELLS = const("engine/system/constants.emp", "PLANE_V_CELLS")
# BG_SCREEN_ROWS = SCREEN_HEIGHT / BG_STREAM_ROW_PX + 1 (bg.emp); BG_STREAM_ROW_PX = 8
# (BG_VSCROLL_ROW_PX, pinned to 8 by parallax.emp's ensure).
BG_SCREEN_ROWS = SCREEN_H // 8 + 1
BG_WIPE_FRAMES = math.ceil(PLANE_V_CELLS / WIPE_ROWS)


def blob_len(path):
    hdr = struct.unpack(">H", open(os.path.join(REPO, path), "rb").read(2))[0]
    return min(hdr, CAPACITY_BYTES) & 0xFFFC   # BG_Stream_Update's clamp and andi #$FFFC


ACT_BLOB = blob_len("games/sonic4/data/generated/ojz/act1/bg_tiles.bin")
SHOWCASE_BLOB = blob_len("games/sonic4/data/generated/ojz/act1/bg_tiles_showcase_debug.bin")


def durations(target_bytes):
    n = math.ceil(target_bytes / CHUNK)                    # ticks crossing -> arena settled
    visible = n + math.ceil(BG_SCREEN_ROWS / WIPE_ROWS) - 1  # -> last visible row sent (BG window still)
    sweep = n + BG_WIPE_FRAMES - 1                          # -> every plane row sent (any motion)
    return n, visible, sweep


def load_plane_a():
    proj = json.load(open(os.path.join(REPO, "project.json")))
    zone = proj["zones"][0]
    act = zone["acts"][0]
    gw, gh = act["gridWidth"], act["gridHeight"]
    tiles = np.frombuffer(open(os.path.join(REPO, zone["tileset"]), "rb").read(), dtype=np.uint8)
    ntiles = len(tiles) // 32
    nib = np.empty((ntiles, 64), dtype=np.uint8)
    t = tiles[: ntiles * 32].reshape(ntiles, 32)
    nib[:, 0::2] = t >> 4
    nib[:, 1::2] = t & 15
    opaque_px = (nib != 0).reshape(ntiles, 8, 8)            # [tile, y, x]
    S = 256
    words = np.zeros((gh * S, gw * S), dtype=np.uint16)
    for sy in range(gh):
        for sx in range(gw):
            p = os.path.join(REPO, act["dataPath"], f"section_{sy * gw + sx}.tiles.bin")
            w = np.array(struct.unpack(f">{S * S}H", open(p, "rb").read()), dtype=np.uint16)
            words[sy * S:(sy + 1) * S, sx * S:(sx + 1) * S] = w.reshape(S, S)
    idx = (words & 0x7FF).astype(np.int32)
    hflip = (words & 0x800) != 0
    vflip = (words & 0x1000) != 0
    tile_any = opaque_px.any(axis=(1, 2))[idx]              # tile-granular: any pixel opaque
    tile_full = opaque_px.all(axis=(1, 2))[idx]             # tile-granular: every pixel opaque
    H, W = words.shape
    px = np.zeros((H * 8, W * 8), dtype=bool)
    variants = {
        (False, False): opaque_px,
        (True, False): opaque_px[:, :, ::-1],
        (False, True): opaque_px[:, ::-1, :],
        (True, True): opaque_px[:, ::-1, ::-1],
    }
    for (hf, vf), arr in variants.items():
        sel = (hflip == hf) & (vflip == vf)
        ys, xs = np.nonzero(sel)
        for y, x in zip(ys, xs):
            px[y * 8:y * 8 + 8, x * 8:x * 8 + 8] = arr[idx[y, x]]
    upscale = lambda m: np.repeat(np.repeat(m, 8, axis=0), 8, axis=1)
    return {"pixel": px, "tile_full": upscale(tile_full), "tile_any": upscale(tile_any)}, words


def run_length(ok_1d, start, step):
    """Consecutive True cells from `start` walking by `step` (+1/-1)."""
    n = 0
    i = start
    while 0 <= i < len(ok_1d) and ok_1d[i]:
        n += 1
        i += step
    return n


def measure(mask, axis, edge, direction, perp_lo, perp_hi, centre_lo, centre_hi, full_band):
    """Authored cover per perpendicular camera centre, in px along the entry axis.

    axis 'x': a vertical edge at world x = edge (the first column of the right-hand region),
    crossed moving +x (direction +1) or -x (-1). At the crossing tick the camera centre is
    at the edge (moving +x: centre = edge, screen [edge-HALF_W, edge+HALF_W-1]) or one pixel
    before it (moving -x: centre = edge-1, screen [edge-HALF_W-1, edge+HALF_W-2]); cover is
    measured from the screen's TRAILING column forward. full_band: the column must be opaque
    over the whole screen height; else only on the centre scanline.
    """
    out = []
    step = 8
    for c in range(max(perp_lo, centre_lo), min(perp_hi, centre_hi) + 1, step):
        if axis == "x":
            band = mask[c - HALF_H:c - HALF_H + SCREEN_H, :] if full_band else mask[c:c + 1, :]
            ok = band.all(axis=0)
            start = edge - HALF_W if direction > 0 else edge + HALF_W - 2
        else:
            band = mask[:, c - HALF_W:c - HALF_W + SCREEN_W] if full_band else mask[:, c:c + 1]
            ok = band.all(axis=1)
            start = edge - HALF_H if direction > 0 else edge + HALF_H - 2
        out.append(run_length(ok, start, direction))
    return out


def main():
    masks, words = load_plane_a()
    act_h, act_w = words.shape[0] * 8, words.shape[1] * 8
    cx_lo, cx_hi = HALF_W, act_w - SCREEN_W + HALF_W
    cy_lo, cy_hi = HALF_H, act_h - SCREEN_H + HALF_H
    print(f"constants: SCREEN {SCREEN_W}x{SCREEN_H}, caps X {CAP_X} Y {CAP_Y} px/tick, "
          f"chunk {CHUNK} B, wipe {WIPE_ROWS} rows/tick, BG_SCREEN_ROWS {BG_SCREEN_ROWS}, "
          f"BG_WIPE_FRAMES {BG_WIPE_FRAMES}")
    print(f"blobs: act default {ACT_BLOB} B, showcase {SHOWCASE_BLOB} B")
    # the showcase rectangle, act_descriptor.emp OJZ_SHOWCASE_X0 .. x1 2047, y 2048..4095
    sx0, sx1, sy0, sy1 = 1024, 2047, 2048, 4095
    crossings = [
        # name, axis, edge (first coordinate of the far side), direction, perp span, target blob
        ("sec3 -> showcase (right, x=1024)", "x", sx0, +1, (sy0, sy1), SHOWCASE_BLOB),
        ("showcase -> sec3 (left,  x=1024)", "x", sx0, -1, (sy0, sy1), ACT_BLOB),
        ("showcase -> sec4 (right, x=2048)", "x", sx1 + 1, +1, (sy0, sy1), ACT_BLOB),
        ("sec4 -> showcase (left,  x=2048)", "x", sx1 + 1, -1, (sy0, sy1), SHOWCASE_BLOB),
        ("sec0 -> showcase (down,  y=2048)", "y", sy0, +1, (sx0, sx1), SHOWCASE_BLOB),
        ("showcase -> sec0 (up,    y=2048)", "y", sy0, -1, (sx0, sx1), ACT_BLOB),
        ("showcase -> sec6 (down,  y=4096)", "y", sy1 + 1, +1, (sx0, sx1), ACT_BLOB),
        ("sec6 -> showcase (up,    y=4096)", "y", sy1 + 1, -1, (sx0, sx1), SHOWCASE_BLOB),
    ]
    readings = [
        ("A pixel, whole screen", "pixel", True),
        ("B tile-full, whole screen", "tile_full", True),
        ("C tile-any, whole screen", "tile_any", True),
        ("D pixel, centre line", "pixel", False),
        ("E tile-any, centre line", "tile_any", False),
    ]
    for name, axis, edge, direction, (plo, phi), blob in crossings:
        n, vis, sweep = durations(blob)
        if axis == "x":
            screen, cap, clo, chi = SCREEN_W, CAP_X, cy_lo, cy_hi
            req_lo = screen + vis * cap
            req_hi = req_lo
        else:
            screen, cap, clo, chi = SCREEN_H, CAP_Y, cx_lo, cx_hi
            req_lo = screen + vis * cap
            req_hi = screen + sweep * cap
        print(f"\n{name}: n={n} visible={vis} sweep={sweep} ticks; required "
              f"{req_lo}" + (f"..{req_hi}" if req_hi != req_lo else "") + " px")
        # F: partial cover. The opaque-pixel FRACTION of the rectangle the screen sweeps over the
        # required length (screen-perpendicular x required, from the trailing edge at crossing).
        px = masks["pixel"]
        fracs = []
        for c in range(max(plo, clo), min(phi, chi) + 1, 8):
            if axis == "x":
                a0 = edge - HALF_W if direction > 0 else edge + HALF_W - 1 - req_lo
                rect = px[c - HALF_H:c - HALF_H + SCREEN_H, a0:a0 + req_lo]
            else:
                a0 = edge - HALF_H if direction > 0 else edge + HALF_H - 1 - req_lo
                rect = px[a0:a0 + req_lo, c - HALF_W:c - HALF_W + SCREEN_W]
            fracs.append(float(rect.mean()))
        print(f"  {'F opaque fraction of sweep':28s} min {min(fracs):.1%} max {max(fracs):.1%}; "
              f"centres >= 90%: {sum(f >= 0.9 for f in fracs)}, >= 75%: {sum(f >= 0.75 for f in fracs)}, "
              f">= 50%: {sum(f >= 0.5 for f in fracs)} of {len(fracs)}")
        for rname, key, full in readings:
            vals = measure(masks[key], axis, edge, direction, plo, phi, clo, chi, full)
            mn, mx = min(vals), max(vals)
            share_ok = sum(1 for v in vals if v >= req_lo) / len(vals)
            print(f"  {rname:28s} authored min {mn:5d} max {mx:5d} px over {len(vals)} "
                  f"perpendicular centres; >= required(lo) at {share_ok:.0%}; "
                  f"warn(worst)={'Y' if mn < req_lo else 'n'} warn(best)={'Y' if mx < req_lo else 'n'}")


if __name__ == "__main__":
    main()
