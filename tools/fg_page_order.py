#!/usr/bin/env python3
"""fg_page_order.py — the foreground act art pool's page ORDER, and the build-time
refusal of any camera window that needs more pages than the cache has frames.

STITCHED-ACT-PAGE-ORDER wiring (2026-09-17). Reports 09 and 10
(docs/research/megaact-bg-streaming/09-page-order-candidates.md, 10-fg-cache-10-frames.md)
measured that the pool's tile ORDER, not its capacity, decides whether every window of a
stitched act fits the page cache. This module is where that result lives in the REAL
pipeline: `ojz_strip_gen.generate()` Pass 4 calls `place_pool`, and `check` is the lane
build.sh runs on the committed, placed act on every canonical build.

THE COUNT (M-B's, reports 08-10):

    needed(window) = | pinned pages  UNION  pages referenced by the window's non-blank words |

over every distinct tile-cache window a camera in the act can hold, and a window is OVER
when needed > PAGE_FRAMES. Global slot 0 (the blank tile) references no page, exactly as
`PageCache` skips it.

EVERY BUDGET NUMBER IS A PARAMETER READ FROM SOURCE. `load_budget_constants` reads
PAGE_FRAMES, ART_POOL_PAGE_TILES, POOL_TILE_CEILING, PAGE_FRAME_TILE_SHIFT and the
TILE_CACHE_COLS/ROWS/MARGIN_H/MARGIN_V window out of engine/system/constants.emp through
fg_working_set.ConstantSource (the mechanism the M-B tools already use). Nothing below
types 12, 64 or 80x60. The owner's open card FG-CACHE-10-HOW (12 x 64-tile frames at the
80x60 window, or 20 x 32-tile frames at a 56x48 window) is therefore a constant change
here, and tools/test_fg_page_order.py runs the placement and the refusal under both sets.

THE ORDER (`place_pool`), a two-rung ladder keyed on the property the refusal checks:

  rung "shipped"   tile_dedupe.order_pool_spatially + pin_blank_tile_first, contiguous
                   pages. Kept when no window needs more than PAGE_FRAMES pages with only
                   page 0 pinned. This is the order every act was baked with before this
                   parcel, so an act that already fits keeps its bytes.
  rung "searched"  report 10's recommended policy, parameterised: dedupe keyed per zone
                   (no two zones share a pool slot), per-zone pages (no page mixes two
                   zones; a zone's last page may be short), Hilbert first-use order, then
                   the swap search (`refine_pages`) aimed at PAGE_FRAMES with a 4x try
                   budget and the wider move set (10's config `rzsFt4w`).

  Pins on either rung are FRAME-AWARE: the 75%-of-sections rule's candidates
  (ojz_strip_gen.mark_pinned_pages, passed in by the caller), each kept only if it pushes
  no window from at or under PAGE_FRAMES to over it.

  WHY A LADDER AND NOT ONE PATH (measured, see the parcel's DEFERRED_WORK entry): the
  searched rung starts from a Hilbert order, and on OJZ act 1 that alone moves every page
  (09: pins [0,1,7,8,9] -> [0,2,7,8,9], windows needing 6+ pages 25,231 -> 40,092) while
  fixing nothing, because OJZ already fits. The zone split is a no-op on a one-zone act;
  the order is what moves it. The rung is chosen by the measured property, not by a zone
  count: M-B measured S2 seams that fit under the shipped order, and those keep it too.

WHAT A "ZONE" IS HERE: the tileset a cell's art comes from. It is NOT an effects region.
OJZ act 1 has 10 regions (regions.json) over one tileset; keying the split on them would
duplicate one zone's shared art per region. Every act `ojz_strip_gen.generate()` can build
reads ONE tileset (project.json zones[0].tileset), so that generator passes a uniform zone
grid. THE STITCHED-ACT LOADER NOW EXISTS (2026-09-17, S2-COMPRESSED-ACT staged plan row 3):
`tools/clip_manifest.py` turns a `clips.json`'s destination rectangles into the per-cell
tileset key and `tools/clip_act_bake.py` hands it to `place_pool` in this same call shape.
It bakes into its own directory rather than through `generate()`, because a second act needs
a project.json entry, a matching `act_descriptor.emp` and collision — see that file's header.

THE REFUSAL (`budget_verdict` + `refuse_over_budget`): the search is a heuristic (09
verdict item 3; 10 "the search is a heuristic"), so the placed act is COUNTED, and a
window over budget fails the bake, naming the worst window and its count. `check` repeats
the count on the committed tree the ROM embeds (sec*_blocks.bin through each section's
local map, pins from the manifest table's pm_flags), because the bake runs only when the
editor tree changes and the build must not trust a stale verdict.

NOT COVERED (as M-B, 09, 10): object/sprite art, the BG plane, animated tiles, transient
frame demand (in-flight decodes, stalled columns), eviction order in motion. A static count
at the budget is NECESSARY for no camera hold, not sufficient.

Usage:
    python3 tools/fg_page_order.py check [--report-only]
      exit 0 every window of every act fits; 1 a window is over budget;
      2 UNMEASURABLE (a constant, an input or an act the decoder does not know).
      --report-only prints the verdict and exits 0 on over-budget (the STRESS_ART fixture,
      which inflates the pool to overwhelm the cache on purpose); unmeasurable still exits 2.
"""

import json
import os
import re
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import tile_dedupe                              # noqa: E402
from fg_working_set import ConstantSource       # noqa: E402  (stdlib-only at import)

CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")

BUDGET_CONSTANTS = [
    "PAGE_FRAMES", "ART_POOL_PAGE_TILES", "POOL_TILE_CEILING", "PAGE_FRAME_TILE_SHIFT",
    "TILE_CACHE_COLS", "TILE_CACHE_ROWS", "TILE_CACHE_MARGIN_H", "TILE_CACHE_MARGIN_V",
    "SECTION_H_REACH_PX", "SECTION_V_REACH_PX", "SCREEN_WIDTH", "SCREEN_HEIGHT",
    "SECTION_SIZE",
]


class BudgetError(Exception):
    """The budget cannot be measured: a constant, input or act the count cannot ground."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def load_budget_constants(path=CONSTANTS_EMP):
    """The budget parameters, read from engine source. Returns a dict name -> int."""
    src = ConstantSource()
    src.load_file(path)
    try:
        c = {n: src.get(n) for n in BUDGET_CONSTANTS}
    except (KeyError, ValueError) as exc:
        raise BudgetError(f"budget constant unreadable from {path}: {exc}")
    validate_budget_constants(c)
    return c


def validate_budget_constants(c):
    """The ties the engine ensures beside each definition, re-stated so a caller that
    builds a hypothetical parameter set (the FG-CACHE-10-HOW options) cannot pass an
    incoherent one; and the window clamp that makes the camera -> window map exact."""
    if c["PAGE_FRAMES"] * c["ART_POOL_PAGE_TILES"] != c["POOL_TILE_CEILING"]:
        raise BudgetError("PAGE_FRAMES * ART_POOL_PAGE_TILES != POOL_TILE_CEILING")
    if (1 << c["PAGE_FRAME_TILE_SHIFT"]) != c["ART_POOL_PAGE_TILES"]:
        raise BudgetError("PAGE_FRAME_TILE_SHIFT is not log2(ART_POOL_PAGE_TILES)")
    if c["TILE_CACHE_ROWS"] % 2:
        raise BudgetError("TILE_CACHE_ROWS is odd (the cache top is even-rounded)")
    require_clamp_binds(c)


def require_clamp_binds(c):
    """The held window is exactly COLS x ROWS from (left, top) at every sub-tile offset,
    so it does not depend on the direction of travel (megaact_window_pageset.derive_window's
    proof, re-stated for a parameter set that is not the shipped one)."""
    for base in (8 * 64, 8 * 1000, 8 * 1001):
        for f in range(8):
            l, r, t, b = window_for_camera(c, base + f, base + f)
            if r - l + 1 != c["TILE_CACHE_COLS"] or b - t + 1 != c["TILE_CACHE_ROWS"]:
                raise BudgetError(
                    f"window clamp does NOT bind at sub-tile offset {f}: {l}..{r} x {t}..{b}. "
                    f"The held window then depends on travel direction and the camera->window "
                    f"map is unsound — UNMEASURABLE, re-derive.")


# ---------------------------------------------------------------------------
# Window model (moved from megaact_window_pageset, which re-exports it)
# ---------------------------------------------------------------------------

def window_for_camera(c, cam_x, cam_y):
    """Tile_Cache_Fill's desired window at steady state, straight from its code
    (engine/level/tile_cache.emp .h_* / .v_* arms). Returns (left, right, top,
    bottom) INCLUSIVE, after the COLS/ROWS clamp."""
    ct, rt = cam_x >> 3, cam_y >> 3
    left = max(0, ct - c["TILE_CACHE_MARGIN_H"])
    right = ((cam_x + c["SECTION_H_REACH_PX"]) >> 3) + c["TILE_CACHE_MARGIN_H"]
    right = min(right, left + c["TILE_CACHE_COLS"] - 1)
    top = max(0, rt - c["TILE_CACHE_MARGIN_V"]) & ~1
    bottom = ((cam_y + c["SECTION_V_REACH_PX"]) >> 3) + c["TILE_CACHE_MARGIN_V"]
    bottom = min(bottom, top + c["TILE_CACHE_ROWS"] - 1)
    return left, right, top, bottom


def camera_windows(c, content_w, content_h):
    """Every distinct window (left, top) a camera in [0, W*8-320] x [0, H*8-224]
    produces, as index arrays + the camera tile ranges that map to each."""
    max_cx = max(0, content_w * 8 - c["SCREEN_WIDTH"])
    max_cy = max(0, content_h * 8 - c["SCREEN_HEIGHT"])
    lefts = sorted({window_for_camera(c, x * 8, 0)[0] for x in range(max_cx // 8 + 1)})
    tops = sorted({window_for_camera(c, 0, y * 8)[2] for y in range(max_cy // 8 + 1)})
    return np.array(lefts), np.array(tops), max_cx, max_cy


def page_presence_sums(pg, lefts, tops, cols, rows, groups):
    """groups: {name: set(page ids)}. Returns {name: int16 (tops x lefts) count of
    pages of that group present in each window}. A page's presence is computed on
    its bounding box only. (Moved from megaact_page_order, which re-exports it; its
    `control_presence` holds it to full-grid integral images and a direct scan.)"""
    H, W = pg.shape
    flat = pg.ravel()
    idx = np.flatnonzero(flat >= 0)
    vals = flat[idx]
    srt = np.argsort(vals, kind="stable")
    idx, vals = idx[srt], vals[srt]
    uniq, starts = np.unique(vals, return_index=True)
    ends = list(starts[1:]) + [len(vals)]
    out = {g: np.zeros((len(tops), len(lefts)), dtype=np.int16) for g in groups}
    for p, a, b in zip(uniq.tolist(), starts.tolist(), ends):
        gs = [g for g, members in groups.items() if p in members]
        if not gs:
            continue
        cells = idx[a:b]
        r, cc = cells // W, cells % W
        r0, r1, c0, c1 = int(r.min()), int(r.max()), int(cc.min()), int(cc.max())
        h, w = r1 - r0 + 1, c1 - c0 + 1
        ind = np.zeros((h, w), dtype=np.int32)
        ind[r - r0, cc - c0] = 1
        ii = np.zeros((h + 1, w + 1), dtype=np.int32)
        np.cumsum(np.cumsum(ind, axis=0), axis=1, out=ii[1:, 1:])
        ta, tb = np.searchsorted(tops, r0 - rows + 1), np.searchsorted(tops, r1, side="right")
        la, lb = np.searchsorted(lefts, c0 - cols + 1), np.searchsorted(lefts, c1, side="right")
        if ta >= tb or la >= lb:
            continue
        t = tops[ta:tb]
        l = lefts[la:lb]
        ya = np.clip(t - r0, 0, h)[:, None]
        yb = np.clip(t + rows - r0, 0, h)[:, None]
        xa = np.clip(l - c0, 0, w)[None, :]
        xb = np.clip(l + cols - c0, 0, w)[None, :]
        s = ii[yb, xb] - ii[ya, xb] - ii[yb, xa] + ii[ya, xa]
        present = (s > 0).astype(np.int16)
        for g in gs:
            out[g][ta:tb, la:lb] += present
    return out


def page_presence(pg, lefts, tops, cols, rows, p):
    """bool (tops x lefts): page p present in the window."""
    return page_presence_sums(pg, lefts, tops, cols, rows, {"x": {p}})["x"] > 0


# ---------------------------------------------------------------------------
# Hilbert first-use order (moved from megaact_page_order, which re-exports it)
# ---------------------------------------------------------------------------

HILBERT_BLOCK = 4               # tiles per Hilbert cell edge (order keys)


def hilbert_d(x, y, order):
    """Vectorised xy -> d on a 2^order square (Wikipedia xy2d)."""
    n = 1 << order
    x = np.asarray(x, dtype=np.int64).copy()
    y = np.asarray(y, dtype=np.int64).copy()
    d = np.zeros_like(x)
    s = n >> 1
    while s > 0:
        rx = ((x & s) > 0).astype(np.int64)
        ry = ((y & s) > 0).astype(np.int64)
        d += s * s * ((3 * rx) ^ ry)
        flip = (ry == 0) & (rx == 1)
        x = np.where(flip, n - 1 - x, x)
        y = np.where(flip, n - 1 - y, y)
        swap = ry == 0
        x, y = np.where(swap, y, x), np.where(swap, x, y)
        s >>= 1
    return d


def _order_for(h, w):
    return max(1, int(np.ceil(np.log2(max(h, w, 2)))))


def _blank_canon(unique):
    return unique.index(tile_dedupe.BLANK_TILE)


def _tile_cells(ctx):
    """(canon ids of non-blank cells, their rows, their cols)."""
    canon = ctx["canon"]
    blank = _blank_canon(ctx["unique"])
    flat = canon.ravel()
    idx = np.flatnonzero(flat != blank)
    W = canon.shape[1]
    return flat[idx], idx // W, idx % W, blank


def _finish(keys_by_tile, blank):
    """pool order = blank, then referenced tiles by ascending key (stable on id)."""
    tiles = np.array(sorted(keys_by_tile), dtype=np.int64)
    k = np.array([keys_by_tile[t] for t in tiles.tolist()], dtype=np.float64)
    order = tiles[np.lexsort((tiles, k))]
    return [blank] + [int(t) for t in order.tolist() if t != blank]


def _hilbert_first_keys(ctx):
    tile, r, cc, blank = _tile_cells(ctx)
    H, W = ctx["canon"].shape
    bh, bw = -(-H // HILBERT_BLOCK), -(-W // HILBERT_BLOCK)
    blk = (r // HILBERT_BLOCK) * bw + (cc // HILBERT_BLOCK)
    pairs = np.unique(tile * (bh * bw) + blk)
    pt, pb = pairs // (bh * bw), pairs % (bh * bw)
    d = hilbert_d(pb % bw, pb // bw, _order_for(bh, bw))
    ntile = int(tile.max()) + 1 if tile.size else 1
    best = np.full(ntile, np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(best, pt, d)
    present = np.unique(pt)
    return {int(t): int(best[t]) for t in present.tolist()}, blank


def order_hilbert_first(ctx):
    keys, blank = _hilbert_first_keys(ctx)
    return _finish(keys, blank)


# ---------------------------------------------------------------------------
# The swap search (moved: samples from megaact_page_order, explicit pages from
# megaact_fg_cache10; both re-export. megaact_fg_cache10's control_ext holds
# refine_pages to megaact_page_order.refine_order.)
# ---------------------------------------------------------------------------

REFINE_SX, REFINE_SY = 8, 4     # sample stride: one sample per 8 lefts x 2 even tops
REFINE_MAX_TRIES = 6000         # per round; a TRY cap, not a time cap: the result must not depend on machine speed
REFINE_LIGHT, REFINE_HEAVY = 5, 6
REFINE_MAX_MOVE = 32            # tiles moved out of a light page in one group swap

# The wired policy: report 10's `rzsFt4w` (aimed at the budget, 4x the try budget, twice
# the light/heavy pages per move, a move of at most half a page). Held as multipliers of
# the search constants above, so a page-size change moves them with it.
PLACE_TRY_MULTIPLIER = 4
PLACE_WIDE_MOVES = 2


def refine_incidences(ctx, sx=None, sy=None):
    """Per referenced non-blank tile, the sorted indices of the SAMPLE windows it
    occurs in. Sample (i, j) is the union of every real window with left in
    [sx*i, sx*i+sx-1] and even top in [sy*j, sy*j+sy-1], so a tile counted present in
    a sample is present in at least one real window of that cell, and a real window's
    page count is <= its sample's count (UPPER BOUND; the final numbers are always
    re-measured on the exact windows)."""
    sx = REFINE_SX if sx is None else sx
    sy = REFINE_SY if sy is None else sy
    tile, r, cc, blank = _tile_cells(ctx)
    H, W = ctx["canon"].shape
    c = ctx["c"]
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    kx = -(-(cols + sx - 1) // sx)                    # blocks the superset spans
    ky = -(-(rows + (sy - 2)) // sy)                  # tops are even: last top is sy*j+sy-2
    nbx, nby = -(-W // sx), -(-H // sy)
    blk = (r // sy) * nbx + (cc // sx)
    pairs = np.unique(tile * (nbx * nby) + blk)
    pt, pb = pairs // (nbx * nby), pairs % (nbx * nby)
    starts = np.flatnonzero(np.r_[True, pt[1:] != pt[:-1]])
    ends = np.r_[starts[1:], len(pt)]
    tiles = pt[starts]
    inc = []
    for a, b in zip(starts.tolist(), ends.tolist()):
        bx, by = pb[a:b] % nbx, pb[a:b] // nbx
        x0, x1, y0, y1 = int(bx.min()), int(bx.max()), int(by.min()), int(by.max())
        img = np.zeros((y1 - y0 + 1, x1 - x0 + 1), dtype=np.int32)
        img[by - y0, bx - x0] = 1
        ii = np.zeros((img.shape[0] + 1, img.shape[1] + 1), dtype=np.int32)
        np.cumsum(np.cumsum(img, 0), 1, out=ii[1:, 1:])
        js = np.arange(max(0, y0 - ky + 1), y1 + 1)
        is_ = np.arange(max(0, x0 - kx + 1), x1 + 1)
        ya = np.clip(js - y0, 0, img.shape[0])[:, None]
        yb = np.clip(js + ky - y0, 0, img.shape[0])[:, None]
        xa = np.clip(is_ - x0, 0, img.shape[1])[None, :]
        xb = np.clip(is_ + kx - x0, 0, img.shape[1])[None, :]
        s = ii[yb, xb] - ii[ya, xb] - ii[yb, xa] + ii[ya, xa]
        yy, xx = np.nonzero(s > 0)
        inc.append((js[yy] * nbx + is_[xx]).astype(np.int32))
    return tiles, inc, nbx * nby, blank


def _has(arr, w):
    i = np.searchsorted(arr, w)
    return i < len(arr) and arr[i] == w


def refine_pages(ctx, pages, target, max_tries=None, pinned=frozenset({0}), group=None, max_move=None,
                 stride=None, light_n=None, heavy_n=None):
    """megaact_page_order.refine_order over explicit page member lists (canonical ids,
    page 0 includes the blank) with an optional same-group move constraint (`group[p]`:
    moves only between pages of one group). Same samples, cost, move, loop and
    determinism; the only additions are the page lists and the constraint. Returns
    the new page lists (sizes unchanged)."""
    max_tries = REFINE_MAX_TRIES if max_tries is None else max_tries
    max_move = REFINE_MAX_MOVE if max_move is None else max_move
    t0 = time.perf_counter()
    light_n = REFINE_LIGHT if light_n is None else light_n
    heavy_n = REFINE_HEAVY if heavy_n is None else heavy_n
    sx, sy = (REFINE_SX, REFINE_SY) if stride is None else stride
    tiles, inc, nwin, blank = refine_incidences(ctx, sx, sy)
    row = {int(t): i for i, t in enumerate(tiles.tolist())}
    npages = len(pages)
    page_of = np.zeros(len(tiles), dtype=np.int32)
    members = [[] for _ in range(npages)]
    base_pos = {}
    pos = 0
    for p, lst in enumerate(pages):
        for t in lst:
            base_pos[int(t)] = pos
            pos += 1
            if t == blank:
                continue
            k = row[int(t)]
            page_of[k] = p
            members[p].append(k)
    cnt = np.zeros((nwin, npages), dtype=np.int16)
    for k, w in enumerate(inc):
        cnt[w, page_of[k]] += 1
    pinmask = np.zeros(npages, dtype=bool)
    pinmask[sorted(pinned | {0})] = True
    pw = ((cnt > 0) | pinmask).sum(axis=1).astype(np.int32)
    start_max = int(pw.max()) if nwin else 0
    start_over = int(np.count_nonzero(pw > target))
    phi = np.array([0.0 if k <= target - 2 else float(4 ** (k - target + 2) - 1) for k in range(128)])
    tries = accepted = 0
    stuck = set()

    def apply(moves):
        touched = np.unique(np.concatenate([inc[k] for k, _ in moves]))
        old = pw[touched].copy()
        for k, q in moves:
            cnt[inc[k], page_of[k]] -= 1
            cnt[inc[k], q] += 1
            page_of[k] = q
        pw[touched] = ((cnt[touched] > 0) | pinmask).sum(axis=1)
        return touched, old

    def attempt(P, S, targets, wstar, pref):
        need = {}
        for q in targets:
            need[q] = need.get(q, 0) + 1
        back = []
        for q, n in need.items():
            outq = [u for u in members[q] if not _has(inc[u], wstar)]
            if len(outq) < n:
                return False
            score = np.array([np.count_nonzero(pref[inc[u]]) / max(1, len(inc[u])) for u in outq])
            back += [(outq[i], q) for i in np.argsort(-score, kind="stable")[:n]]
        fwd = list(zip(S, targets))
        touched, old = apply(fwd + [(u, P) for u, _ in back])
        d = phi[np.minimum(pw[touched], 127)].sum() - phi[np.minimum(old, 127)].sum()
        if d < 0 and pw[wstar] < old[np.searchsorted(touched, wstar)]:
            for k, q in fwd:
                members[P].remove(k)
                members[q].append(k)
            for u, q in back:
                members[q].remove(u)
                members[P].append(u)
            return True
        apply([(k, P) for k, _ in fwd] + [(u, q) for u, q in back])
        return False

    passes = 1
    accepted_this_pass = 0
    while tries < max_tries:
        over = np.flatnonzero(pw > target)
        if over.size == 0:
            break
        wstar = None
        for w in over[np.argsort(-pw[over], kind="stable")].tolist():
            if w not in stuck:
                wstar = w
                break
        if wstar is None:
            if accepted_this_pass == 0:
                break
            stuck.clear()
            accepted_this_pass = 0
            passes += 1
            continue
        improved = False
        ref = np.flatnonzero(cnt[wstar] > 0)
        light = ref[np.argsort(cnt[wstar, ref], kind="stable")]
        heavy = [q for q in ref[np.argsort(-cnt[wstar, ref], kind="stable")].tolist()]
        for P in [x for x in light.tolist() if not pinmask[x]][:light_n]:
            S = [k for k in members[P] if _has(inc[k], wstar)]
            if not S or len(S) > max_move:
                continue
            pref = cnt[:, P] > 0
            qs = [q for q in heavy if q != P and (group is None or group[q] == group[P])][:heavy_n]
            for Q in qs:
                tries += 1
                if attempt(P, S, [Q] * len(S), wstar, pref):
                    improved = True
                    break
            if not improved and len(S) > 1 and len(qs) > 1:
                tries += 1
                improved = attempt(P, S, [qs[i % len(qs)] for i in range(len(S))], wstar, pref)
            if improved:
                break
        if improved:
            accepted += 1
            accepted_this_pass += 1
        stuck.add(wstar)
    out = []
    for p in range(npages):
        ids = sorted((int(tiles[k]) for k in members[p]), key=lambda t: base_pos[t])
        out.append(([blank] + ids) if p == 0 else ids)
    ctx["stats"].setdefault("refine_rounds", []).append({
        "target": target, "stride": [sx, sy], "light": light_n, "heavy": heavy_n, "sample_windows": int(nwin), "tries": tries, "accepted": accepted,
        "passes": passes, "try_cap_hit": tries >= max_tries, "sample_max_before": start_max,
        "sample_over_target_before": start_over, "sample_max_after": int(pw.max()) if nwin else 0,
        "sample_over_target_after": int(np.count_nonzero(pw > target)),
        "pinned_counted": sorted(pinned | {0}), "seconds": round(time.perf_counter() - t0, 3)})
    return out


# ---------------------------------------------------------------------------
# Zones: split dedupe and per-zone pages (moved from megaact_fg_cache10, which re-exports)
# ---------------------------------------------------------------------------

def pages_from_order(order, size):
    return [list(order[i:i + size]) for i in range(0, len(order), size)]


def zone_split(zone_id, unique, canon, keep_shared=frozenset(), n_zones=None):
    """one canonical per (zone, canonical), except the blank and `keep_shared`.
    `zone_id` is (H, W), -1 = VOID. Returns (unique', canon', original canonical of each
    new id)."""
    blank_c = unique.index(tile_dedupe.BLANK_TILE) if tile_dedupe.BLANK_TILE in unique else -1
    nz = (int(zone_id.max()) + 1 if n_zones is None else n_zones) + 1
    zk = canon * nz + (zone_id.astype(np.int64) + 1)
    collapse = canon == blank_c
    if keep_shared:
        collapse |= np.isin(canon, np.array(sorted(keep_shared), dtype=np.int64))
    zk = np.where(collapse, canon * nz, zk)
    zref, zinv = np.unique(zk, return_inverse=True)
    return [unique[int(k) // nz] for k in zref.tolist()], zinv.reshape(canon.shape).astype(np.int64), zref // nz


def zone_of_canon(ctx):
    tile, r, cc, blank = _tile_cells(ctx)
    z = ctx["zone_id"][r, cc].astype(np.int64)
    pairs = np.unique(tile * 256 + z)
    t, zz = pairs // 256, pairs % 256
    multi = np.flatnonzero(np.r_[False, t[1:] == t[:-1]])
    return dict(zip(t.tolist(), zz.tolist())), set(t[multi].tolist())


def perzone_pages(ctx, base, page):
    """Pages that never mix two zones: the base order regrouped by zone (stable), a new
    page at every zone change or when a page is full. Page 0 = blank + the first zone's
    tiles. Returns (pages, group) with group[p] = the zone of page p."""
    zone_of, multi = zone_of_canon(ctx)
    if multi:
        raise BudgetError(f"perzone: {len(multi)} canonicals occur in more than one zone after the split")
    blank = base[0]
    keys = {t: i for i, t in enumerate(base)}
    rest = sorted(base[1:], key=lambda t: (zone_of[t], keys[t]))
    pages, group = [], []
    zfirst = zone_of[rest[0]] if rest else 0
    cur = [blank]
    curz = zfirst
    for t in rest:
        z = zone_of[t]
        if z != curz or len(cur) == page:
            pages.append(cur)
            group.append(curz)
            cur, curz = [], z
        cur.append(t)
    pages.append(cur)
    group.append(curz)
    return pages, group


# ---------------------------------------------------------------------------
# Counting, pins, verdict
# ---------------------------------------------------------------------------

def per_section_lists(canon, section_tiles, grid_w, grid_h):
    """Each section's canonical ids in first-occurrence order, COLUMN-major inside the
    section (generate()'s strips[col][row] walk), sections in flat row-major grid order."""
    st = section_tiles
    out = []
    for sy in range(grid_h):
        for sx in range(grid_w):
            sub = canon[sy * st:(sy + 1) * st, sx * st:(sx + 1) * st]
            flat = sub.T.ravel()
            u, idx = np.unique(flat, return_index=True)
            out.append(u[np.argsort(idx, kind="stable")].tolist())
    return out


def window_needed(pg, n_pages, pinned, c, lefts, tops):
    """needed[ti, li] = |pinned UNION pages present| for every window. Also returns the
    page-0-only count (what the window alone forces)."""
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    pinned = set(pinned) | {0}
    allp = set(range(n_pages))
    sums = page_presence_sums(pg, lefts, tops, cols, rows,
                              {"unpinned": allp - pinned, "pinned_nonzero": pinned - {0}})
    needed = sums["unpinned"].astype(np.int32) + len(pinned)
    needed_pin0 = sums["unpinned"].astype(np.int32) + sums["pinned_nonzero"] + 1
    return needed, needed_pin0


def frame_aware_pins(pg, candidates, F, needed_pin0, c, lefts, tops):
    """Report 10's lever 1: take the pin rule's candidates in page order and keep each only
    if it pushes no window from <= F to > F. Page 0 is always pinned. Returns
    (pins, needed with those pins)."""
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    needed = needed_pin0.copy()
    kept = [0]
    for p in sorted(set(candidates) - {0}):
        pres = page_presence(pg, lefts, tops, cols, rows, p)
        bump = needed + (~pres).astype(np.int32)
        if np.count_nonzero((needed <= F) & (bump > F)) == 0:
            needed = bump
            kept.append(p)
    return kept, needed


def budget_verdict(needed, lefts, tops, c):
    """The refusal's facts: the worst window (first in row-major order at the peak), its
    count, and how many windows are over PAGE_FRAMES. Refuses an empty population."""
    F = c["PAGE_FRAMES"]
    if needed.size == 0:
        raise BudgetError("no camera window to count: the act has no content — UNMEASURABLE, not a pass")
    peak = int(needed.max())
    ti, li = np.nonzero(needed == peak)
    left, top = int(lefts[li[0]]), int(tops[ti[0]])
    return {
        "frames": F,
        "page_tiles": c["ART_POOL_PAGE_TILES"],
        "window": [c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]],
        "windows": int(needed.size),
        "worst": peak,
        "worst_positions": int(len(ti)),
        "worst_window_tile": {"left": left, "top": top},
        "worst_camera_px": {"x": (left + c["TILE_CACHE_MARGIN_H"]) * 8 if left else 0,
                            "y": (top + c["TILE_CACHE_MARGIN_V"]) * 8 if top else 0},
        "over": int(np.count_nonzero(needed > F)),
        "ok": peak <= F,
    }


def verdict_line(v, subject):
    w, cam = v["worst_window_tile"], v["worst_camera_px"]
    return (f"{subject}: {v['windows']} camera windows ({v['window'][0]}x{v['window'][1]} tiles), "
            f"budget {v['frames']} frames x {v['page_tiles']}-tile pages; worst window needs "
            f"{v['worst']} (tile left {w['left']} top {w['top']}, e.g. camera x={cam['x']} "
            f"y={cam['y']} px; {v['worst_positions']} window(s) at that count); "
            f"{v['over']} window(s) over budget")


def refuse_over_budget(v, subject):
    if not v["ok"]:
        raise SystemExit(
            f"REFUSED — FG page budget: {verdict_line(v, subject)}.\n"
            f"  A camera holding that window would need more art pages resident than the cache "
            f"has frames (PAGE_FRAMES = POOL_TILE_CEILING / ART_POOL_PAGE_TILES, "
            f"engine/system/constants.emp), and the release engine holds the camera until a "
            f"frame frees, which it never does. The page-order search could not fit this "
            f"placement: move art so fewer distinct tiles meet in that window, or change the "
            f"budget constants.")


# ---------------------------------------------------------------------------
# Placement (generate() Pass 4)
# ---------------------------------------------------------------------------

def _evaluate(canon, unique, pages, c, lefts, tops, rule_pins_fn, per_section):
    """page grid, rule candidates, frame-aware pins and the count for explicit pages whose
    page p starts at global slot p * ART_POOL_PAGE_TILES."""
    page = c["ART_POOL_PAGE_TILES"]
    F = c["PAGE_FRAMES"]
    slot_of = np.full(len(unique), -1, dtype=np.int64)
    for p, lst in enumerate(pages):
        if len(lst) > page:
            raise BudgetError(f"page {p} holds {len(lst)} tiles > ART_POOL_PAGE_TILES {page}")
        for i, t in enumerate(lst):
            if slot_of[t] >= 0:
                raise BudgetError(f"canonical {t} placed twice")
            slot_of[t] = p * page + i
    glob = slot_of[canon]
    if np.any(glob < 0):
        raise BudgetError("a referenced canonical has no page slot")
    pg = np.where(glob == 0, -1, glob >> c["PAGE_FRAME_TILE_SHIFT"]).astype(np.int16)
    # the pin rule sees CONTIGUOUS pool positions (its page-slot walk is a running sum)
    pos, o = {}, 0
    for lst in pages:
        for t in lst:
            pos[t] = o
            o += 1
    sets = [{pos[t] for t in sec} for sec in per_section]
    rule = sorted(rule_pins_fn(pages, sets))
    _needed, needed_pin0 = window_needed(pg, len(pages), {0}, c, lefts, tops)
    pins, needed = frame_aware_pins(pg, rule, F, needed_pin0, c, lefts, tops)
    return {"pages": pages, "slot_of": slot_of, "page_grid": pg, "rule_pins": rule,
            "pins": pins, "needed": needed, "needed_pin0": needed_pin0}


def place_pool(canon, zone_id, unique, section_tiles, grid_w, grid_h, c, rule_pins_fn, log=None):
    """generate() Pass 4. `canon` (H, W) canonical ids from the shared dedupe, `zone_id`
    (H, W) >= 0 the tileset key per cell, `unique` the canonical tile bytes (the blank may
    be appended). `rule_pins_fn(pages, per_section_position_sets)` -> the 75% rule's pinned
    page indices (ojz_strip_gen.mark_pinned_pages). Returns the placement dict; the caller
    refuses on `verdict`."""
    t0 = time.perf_counter()
    page = c["ART_POOL_PAGE_TILES"]
    F = c["PAGE_FRAMES"]
    H, W = canon.shape
    lefts, tops, _, _ = camera_windows(c, W, H)
    unique = list(unique)

    # ---- rung 1: the shipped order ----
    per_section = per_section_lists(canon, section_tiles, grid_w, grid_h)
    order = tile_dedupe.order_pool_spatially(per_section)
    order = tile_dedupe.pin_blank_tile_first(order, unique)
    ev = _evaluate(canon, unique, tile_dedupe.split_pool_into_pages(order, page), c, lefts, tops,
                   rule_pins_fn, per_section)
    rung = "shipped"
    shipped_worst = int(ev["needed_pin0"].max()) if ev["needed_pin0"].size else 0
    stats = {"shipped_worst_pin0": shipped_worst}
    if shipped_worst > F:
        # ---- rung 2: per-zone dedupe + per-zone pages + Hilbert order + aimed search ----
        rung = "searched"
        if tile_dedupe.BLANK_TILE not in unique:
            unique.append(tile_dedupe.BLANK_TILE)
        unique, canon, _ = zone_split(zone_id, unique, canon)
        if tile_dedupe.BLANK_TILE not in unique:
            unique.append(tile_dedupe.BLANK_TILE)
        per_section = per_section_lists(canon, section_tiles, grid_w, grid_h)
        ctx = {"canon": canon, "zone_id": zone_id, "unique": unique, "per_section": per_section,
               "c": c, "stats": stats}
        base = order_hilbert_first(ctx)
        pages, group = perzone_pages(ctx, base, page)
        pages = refine_pages(ctx, pages, F, max_tries=REFINE_MAX_TRIES * PLACE_TRY_MULTIPLIER,
                             pinned=frozenset({0}), group=group, max_move=page // 2,
                             light_n=REFINE_LIGHT * PLACE_WIDE_MOVES,
                             heavy_n=REFINE_HEAVY * PLACE_WIDE_MOVES)
        ev = _evaluate(canon, unique, pages, c, lefts, tops, rule_pins_fn, per_section)
    verdict = budget_verdict(ev["needed"], lefts, tops, c)
    out = dict(ev)
    out.update({"rung": rung, "unique": unique, "canon": canon, "per_section": per_section,
                "verdict": verdict, "stats": stats, "lefts": lefts, "tops": tops,
                "seconds": round(time.perf_counter() - t0, 3)})
    if log:
        log(f"  Pass 4 page order: rung {rung} (shipped order's worst window with page 0 pinned: "
            f"{shipped_worst} of {F} frames); pins {out['pins']} (rule {out['rule_pins']}); "
            f"{time.perf_counter() - t0:.2f} s")
    return out


# ---------------------------------------------------------------------------
# `check`: the count on the committed, placed act (what the ROM embeds)
# ---------------------------------------------------------------------------

def _known_acts():
    """(act label, generated dir) for every act project.json declares, refusing any the
    decoder below cannot read. Today one act; a second one must fail here loudly rather
    than be skipped."""
    import act_grid
    import fg_working_set as fws
    proj = json.load(open(act_grid.PROJECT_JSON))
    acts = []
    for zone in proj.get("zones", []):
        for act in zone.get("acts", []):
            gen = os.path.normpath(os.path.join(REPO, act.get("stripPath", "")))
            label = f"{zone.get('id')}/{act.get('id')}"
            if gen != os.path.normpath(fws.GEN_DIR):
                raise BudgetError(
                    f"act {label} ({gen}) is not the one act the committed-tree decoder "
                    f"(fg_working_set.load_page_grid, {fws.GEN_DIR}) reads — UNMEASURABLE. "
                    f"Teach the decoder this act; do not skip it.")
            acts.append((label, gen))
    if not acts:
        raise BudgetError("project.json declares no act — UNMEASURABLE, not a pass")
    return acts


def committed_placement(c):
    """Page grid (from sec*_blocks.bin through each section's local map) and pins (the
    manifest table's pm_flags bit 0) of the committed OJZ act 1 tree."""
    import fg_working_set as fws
    model = fws.Model()
    if model.page_tiles != c["ART_POOL_PAGE_TILES"] or model.page_shift != c["PAGE_FRAME_TILE_SHIFT"]:
        raise BudgetError("fg_working_set's page geometry disagrees with the budget constants")
    grid, _per, _air = fws.load_page_grid(model)
    pg = np.array(grid, dtype=np.int16)
    pool = os.path.join(fws.GEN_DIR, "ojz_act_pool.emp")
    if not os.path.isfile(pool):
        raise BudgetError(f"{pool} missing — UNMEASURABLE")
    entries = re.findall(r"pm_tiles:\s*(\d+)\s*,\s*pm_form:\s*(\d+)\s*,\s*pm_flags:\s*(\d+)",
                         open(pool).read())
    if not entries:
        raise BudgetError(f"no PageManifest entries in {pool} — UNMEASURABLE")
    pins = sorted({0} | {i for i, (_t, _f, fl) in enumerate(entries) if int(fl) & 1})
    n_pages = len(entries)
    if pg.size and int(pg.max()) >= n_pages:
        raise BudgetError(f"a cell references page {int(pg.max())} past the {n_pages}-page manifest")
    return pg, pins, n_pages


def check(report_only=False, out=print):
    c = load_budget_constants()
    status = 0
    for label, _gen in _known_acts():
        pg, pins, n_pages = committed_placement(c)
        H, W = pg.shape
        lefts, tops, _, _ = camera_windows(c, W, H)
        needed, _pin0 = window_needed(pg, n_pages, pins, c, lefts, tops)
        v = budget_verdict(needed, lefts, tops, c)
        line = verdict_line(v, f"{label} (committed tree; {n_pages} pages, pins {pins})")
        if v["ok"]:
            out(f"FG page budget OK — {line}")
        elif report_only:
            out(f"FG page budget OVER (report-only, not failing) — {line}")
        else:
            out(f"FG page budget REFUSED — {line}")
            status = 1
    return status


USAGE = """Usage:
    python3 tools/fg_page_order.py check [--report-only]"""


def _mode_check(rest):
    report_only = False
    for a in rest:
        if a == "--report-only":
            report_only = True
        else:
            print(f"ERROR: unknown argument {a!r}")
            print(USAGE)
            sys.exit(1)
    try:
        return check(report_only=report_only)
    except BudgetError as exc:
        print(f"FG page budget UNMEASURABLE — {exc}")
        return 2


# ONE list of legal modes, and it is the dispatch table (LS-15d shape,
# tools/test_cli_dispatch_refuses.py). An unknown or missing mode prints usage and
# exits 1 BEFORE any handler; nothing is a default.
MODES = {
    "check": _mode_check,
}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(USAGE)
        sys.exit(1)
    return handler(args[1:])


if __name__ == "__main__":
    sys.exit(main())
