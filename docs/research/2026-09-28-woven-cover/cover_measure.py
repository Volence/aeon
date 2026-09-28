#!/usr/bin/env python3
"""cover_measure.py — how much of the screen the woven act's line-0 COVER takes, per connector,
and how small the crossing model lets it get.

    python3 docs/research/2026-09-28-woven-cover/cover_measure.py <clips.json>

Research instrument for docs/research/2026-09-28-woven-cover.md. Reads only the manifest, the
donor trees and the engine constants (through the bake's own functions); writes nothing.

"COVER" = every act cell drawn from the corridor sheet on CRAM line 0: tunnel art, shaft art
and the neutral fill. It is opaque by construction (clip_manifest: TUNNEL_HOLE_COLOUR, the
shaft's "every pixel painted", the fill's stone tile), so while it fills a screen no background
pixel is visible.

Per connector it prints:
  * the geometry and Z2's two needs (clip_rom_bake.connector_crossings, the bake's own call);
  * THE SPLIT of the connector along its axis, from the crossing c outwards:
      core    = HALF + STEP x SNAP_FRAMES each side: no zone cell of EITHER zone may be here
                (the palette is snapped at c and may land one frame late);
      margin  = need - core each side: a cell of the zone on THAT side may be here only if it
                is OPAQUE (its palette is up, its background is not settled yet);
      slack   = connector - need each side: anything of the zone on that side, transparent
                included (its background has settled before the camera can show it);
  * over the REACHABLE camera centres inside the connector (clip_camera.CameraModel, the
    SCREEN check's own model): how many px of camera travel along the axis show a screen that
    is 100% cover, and the mean share of the screen that is cover;
  * for each ZONE MOUTH: the share of that zone's 8x8 cells that are fully opaque, in the
    first `margin` px past the mouth over the connector's open band +-HALF_H (the cells an
    "opaque zone art" margin would have to be made of).
The whole act: the share of every reachable screen that is cover (fill included).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import clip_camera            # noqa: E402
import clip_manifest          # noqa: E402
import clip_rom_bake as CRB   # noqa: E402
import s2_donor as sd         # noqa: E402

C = clip_manifest.TILE_PX


def opaque_tiles(donor, zone):
    """bool per art tile: every one of its 64 pixels is non-zero."""
    art = sd.load_zone(zone, donor).art
    n = len(art) // 32
    a = np.frombuffer(art, dtype=np.uint8).reshape(n, 32)
    hi, lo = a >> 4, a & 15
    return ((hi != 0) & (lo != 0)).all(axis=1)


def zone_cell_opaque(clip, x0, y0, x1, y1):
    """(opaque cells, cells) of `clip`'s donor plane A over act px [x0,x1) x [y0,y1)."""
    z = sd.load_zone(clip.tree_key[1], clip.tree_key[0])
    op = opaque_tiles(clip.tree_key[0], clip.tree_key[1])
    cx0, cy0 = z.box["crop_tiles"][0], z.box["crop_tiles"][2]
    x0, x1 = max(x0, clip.dst[0]), min(x1, clip.dst[0] + clip.dst[2])
    y0, y1 = max(y0, clip.dst[1]), min(y1, clip.dst[1] + clip.dst[3])
    if x1 <= x0 or y1 <= y0:
        return 0, 0
    sx = (x0 - clip.dst[0] + clip.src[0]) // C - cx0
    sy = (y0 - clip.dst[1] + clip.src[1]) // C - cy0
    w, h = (x1 - x0) // C, (y1 - y0) // C
    words = z.words[sy:sy + h, sx:sx + w]
    idx = (words & 0x7FF).astype(np.int64)
    good = op[np.clip(idx, 0, len(op) - 1)] & (idx > 0)
    return int(good.sum()), int(good.size)


def main(path):
    act = clip_manifest.load(path)
    model = clip_camera.CameraModel.for_act(act)
    cam = model.c
    frames = CRB.crossing_frames(act)
    cross = CRB.connector_crossings(act, frames)
    R, K = model.centres.shape
    cover = np.zeros((R, K), dtype=bool)
    for k in list(act.corridors) + list(act.shafts):
        x, y, w, h = (v // C for v in k.dst)
        cover[y:y + h, x:x + w] = True
    cover |= clip_manifest.fill_mask(act)
    ii = np.zeros((R + 1, K + 1), dtype=np.int64)
    np.cumsum(np.cumsum(cover.astype(np.int64), axis=0), axis=1, out=ii[1:, 1:])
    hw, hh = cam["CAM_SCREEN_HALF_W"] // C, cam["CAM_SCREEN_HALF_H"] // C

    def cover_share(ys, xs):
        y0, y1 = np.clip(ys - hh, 0, R), np.clip(ys + hh, 0, R)
        x0, x1 = np.clip(xs - hw, 0, K), np.clip(xs + hw, 0, K)
        n = ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]
        return n / float((2 * hh) * (2 * hw))

    snap = CRB.SNAP_FRAMES
    print(f"constants: HALF_W {cam['CAM_SCREEN_HALF_W']} HALF_H {cam['CAM_SCREEN_HALF_H']} "
          f"X_STEP {cam['CAM_MAX_X_STEP']} Y_STEP {cam['CAM_MAX_Y_STEP']} SNAP_FRAMES {snap} "
          f"wipe {frames['wipe']} frames; blob bytes {frames['blob_bytes']}")
    print("connector            ax  len  a..b          c     need(b/a)  core/side  "
          "margin(b/a)  slack(b/a)  full-cover travel  mean cover  opaque at mouth (before/after)")
    for x in cross:
        k, ax = x["connector"], x["axis"]
        i = 0 if ax == "x" else 1
        half = cam["CAM_SCREEN_HALF_W"] if ax == "x" else cam["CAM_SCREEN_HALF_H"]
        step = cam["CAM_MAX_X_STEP"] if ax == "x" else cam["CAM_MAX_Y_STEP"]
        core = half + step * snap
        L = x["b"] - x["a"]
        nb, na = x["need_before"], x["need_after"]
        sb, sa = (x["c"] - x["a"]) - nb, (x["b"] - x["c"]) - na
        mb, ma = nb - core, na - core
        # reachable centres inside the connector
        kx, ky, kw, kh = (v // C for v in k.dst)
        m = np.zeros((R, K), dtype=bool)
        m[ky:ky + kh, kx:kx + kw] = True
        m &= model.centres
        ys, xs = np.nonzero(m)
        if len(ys):
            sh = cover_share(ys, xs)
            along = (xs if ax == "x" else ys)
            full_pos = np.unique(along[sh >= 1.0])
            trav = len(full_pos) * C
            mean = float(sh.mean())
        else:
            trav, mean = 0, float("nan")
        # opacity of each zone's first `margin` px past its mouth, over the band the screen
        # can show around the connector's open lane
        if ax == "x":
            fy = k.floor_y
            band = (fy - 96 - cam["CAM_SCREEN_HALF_H"], fy + cam["CAM_SCREEN_HALF_H"])
            ob = zone_cell_opaque(x["before"], x["a"] - max(mb, C), band[0], x["a"], band[1])
            oa = zone_cell_opaque(x["after"], x["b"], band[0], x["b"] + max(ma, C), band[1])
        else:
            band = (k.dst[0] - cam["CAM_SCREEN_HALF_W"] + k.dst[2] // 2,
                    k.dst[0] + k.dst[2] // 2 + cam["CAM_SCREEN_HALF_W"])
            ob = zone_cell_opaque(x["before"], band[0], x["a"] - max(mb, C), band[1], x["a"])
            oa = zone_cell_opaque(x["after"], band[0], x["b"], band[1], x["b"] + max(ma, C))
        pct = lambda t: f"{100.0 * t[0] / t[1]:.0f}%" if t[1] else "n/a"
        print(f"{k.id:20s} {ax}  {L:4d}  {x['a']:5d}..{x['b']:<5d} {x['c']:5d}  "
              f"{nb:3d}/{na:<3d}    {core:3d}        {mb:3d}/{ma:<3d}      {sb:3d}/{sa:<3d}     "
              f"{trav:4d} px of {L}       {mean:5.1%}      {pct(ob)} / {pct(oa)}")
    ys, xs = np.nonzero(model.centres)
    sh = cover_share(ys, xs)
    print(f"whole act: {len(ys)} reachable centres; mean screen share that is cover "
          f"{sh.mean():.1%}; screens with >= 25% cover {np.mean(sh >= .25):.1%}, "
          f"100% cover {np.mean(sh >= 1.0):.1%}")
    # the same, excluding centres inside a connector: what the FILL alone hides in the zones
    inside = np.zeros((R, K), dtype=bool)
    for k in list(act.corridors) + list(act.shafts):
        x0, y0, w, h = (v // C for v in k.dst)
        inside[y0:y0 + h, x0:x0 + w] = True
    zc = model.centres & ~inside
    ys, xs = np.nonzero(zc)
    sh = cover_share(ys, xs)
    print(f"zone centres only (camera outside every connector): {len(ys)}; mean cover share "
          f"{sh.mean():.1%}; >= 25% cover {np.mean(sh >= .25):.1%}; >= 50% {np.mean(sh >= .5):.1%}")
    for cl in act.clips:
        x0, y0, w, h = (v // C for v in cl.dst)
        mm = np.zeros((R, K), dtype=bool)
        mm[y0:y0 + h, x0:x0 + w] = True
        mm &= zc
        ys, xs = np.nonzero(mm)
        if len(ys):
            sh = cover_share(ys, xs)
            # an example screen at about half cover, to point the owner at
            i = int(np.argmin(np.abs(sh - 0.5)))
            print(f"   {cl.id:18s} centres {len(ys):6d}  mean cover {sh.mean():5.1%}  "
                  f">=25% {np.mean(sh >= .25):5.1%}  e.g. camera centre "
                  f"({xs[i] * C + 4}, {ys[i] * C + 4}) shows {sh[i]:.0%} fill")


if __name__ == "__main__":
    main(sys.argv[1])
