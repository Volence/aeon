#!/usr/bin/env python3
"""The art-window budget of the woven layout WITH its connector art, off the real bake.

`tools/clip_act_bake.py bake draft_clips.json --out DIR` measures the clips (N1/N2). The
manifest cannot carry this layout's connectors (no shaft or cloud-band kind; K6 refuses any
tunnel into Metropolis, Hidden Palace or Oil Ocean, which have no plane-B floor), so their art
is ADDED here to the bake's own per-cell page grid (`clip_act_bake.page_grid_from_tree`) and
the windows are re-counted by the bake's own counter (`fg_page_order.window_needed` /
`budget_verdict`, the calls `clip_act_bake.recount` makes):
  * ROCK FILL (every non-clip cell of the layout's bounding box below the sky band): the
    tunnel sheet, MEASURED at 28 tiles in today's s2_ehz_cpz bake (pool.per_corridor), counted
    as ONE page of its own (it shares a page there, so this over-counts by up to one);
  * CLOUD BAND (non-clip cells above the middle row's top): the sample look of
    render_woven.cloud_swatch, its canonical tiles counted here, as that many pages of its
    own, ALL of them charged to every window that touches the band (an over-count).

    python3 art_window.py layout.json <baked dir>
"""
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))
import clip_act_bake as B                # noqa: E402
import fg_page_order as fpo              # noqa: E402
import render_woven as RW                # noqa: E402
import woven                             # noqa: E402

TUNNEL_SHEET_TILES = 28                  # MEASURED: s2_ehz_cpz bake, pool.per_corridor


def cloud_tiles():
    img = RW.cloud_swatch(512, 128)                     # one period of the sample
    seen = set()
    for r in range(0, img.shape[0], 8):
        for c in range(0, img.shape[1], 8):
            t = img[r:r + 8, c:c + 8]
            forms = [t, t[:, ::-1], t[::-1, :], t[::-1, ::-1]]
            seen.add(min(f.tobytes() for f in forms))
    return len(seen)


def present(mask, lefts, tops, c):
    """(tops x lefts) 0/1: does the window hold any cell of `mask`."""
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    H, W = mask.shape
    ii = np.zeros((H + 1, W + 1), dtype=np.int64)
    np.cumsum(np.cumsum(mask.astype(np.int64), axis=0), axis=1, out=ii[1:, 1:])
    t0 = np.clip(tops, 0, H)[:, None]
    t1 = np.clip(tops + rows, 0, H)[:, None]
    l0 = np.clip(lefts, 0, W)[None, :]
    l1 = np.clip(lefts + cols, 0, W)[None, :]
    return ((ii[t1, l1] - ii[t0, l1] - ii[t1, l0] + ii[t0, l0]) > 0).astype(np.int32)


def main():
    spec = woven.load(sys.argv[1])
    pg, pins, n_pages = B.page_grid_from_tree(sys.argv[2])
    c = fpo.load_budget_constants()
    H, W = pg.shape
    lefts, tops, _, _ = fpo.camera_windows(c, W, H)
    base = fpo.budget_verdict(fpo.window_needed(pg, n_pages, pins, c, lefts, tops)[0],
                              lefts, tops, c)
    clipm = np.zeros((H, W), dtype=bool)
    for cl in spec["clips"]:
        x0, y0 = cl["dst"][0] // 8, cl["dst"][1] // 8
        clipm[y0:y0 + cl["src"][3] // 8, x0:x0 + cl["src"][2] // 8] = True
    bx = max(cl["dst"][0] + cl["src"][2] for cl in spec["clips"]) // 8
    by = max(cl["dst"][1] + cl["src"][3] for cl in spec["clips"]) // 8
    sky = max(cl["dst"][1] for cl in spec["clips"] if cl["zone"] != "WFZ"
              and cl["dst"][1] < 3000) // 8
    fill = np.zeros((H, W), dtype=bool)
    fill[:by, :bx] = True
    fill &= ~clipm
    band = fill.copy()
    band[sky:] = False
    rock = fill & ~band
    n_cloud = cloud_tiles()
    k = math.ceil(n_cloud / c["ART_POOL_PAGE_TILES"])
    needed = fpo.window_needed(pg, n_pages, pins, c, lefts, tops)[0].copy()
    needed += present(rock, lefts, tops, c)                  # one rock page
    needed += k * present(band, lefts, tops, c)              # all k cloud pages
    v = fpo.budget_verdict(needed, lefts, tops, c)
    print(f"clips only (the bake's own N1): worst {base['worst']} of {base['frames']}, "
          f"{base['over']} of {base['windows']} windows over")
    print(f"connector art: rock/tunnel sheet {TUNNEL_SHEET_TILES} tiles = 1 page; cloud band "
          f"sample {n_cloud} canonical tiles = {k} page(s)")
    print(f"clips + connectors: worst {v['worst']} of {v['frames']}, {v['over']} of "
          f"{v['windows']} windows over")
    if v["over"]:
        over = needed > v["frames"]
        ti, li = np.argwhere(over)[0]
        print(f"  first over-budget window: camera x={int(lefts[li]) * 8} y={int(tops[ti]) * 8}"
              f" px needs {int(needed[ti, li])}")
        hist = {int(n): int((needed == n).sum()) for n in np.unique(needed) if n > v["frames"]}
        print(f"  over-budget windows by frames needed: {hist}")
        ti, li = np.nonzero(over)
        print(f"  over-budget camera span: x {int(lefts[li].min()) * 8}..{int(lefts[li].max()) * 8}"
              f", y {int(tops[ti].min()) * 8}..{int(tops[ti].max()) * 8} (cache-window left/top)")
    for name, m in (("rock", rock), ("cloud band", band)):
        pr = present(m, lefts, tops, c).astype(bool)
        base_n = fpo.window_needed(pg, n_pages, pins, c, lefts, tops)[0]
        print(f"  windows touching the {name}: clips-only worst there {int(base_n[pr].max())}, "
              f"with connector art {int(needed[pr].max())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
