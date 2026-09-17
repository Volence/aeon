#!/usr/bin/env python3
"""megaact_page_order.py — STITCHED-ACT-PAGE-ORDER: candidate foreground tile-page
ORDERS measured against M-B's window page-set populations.

THIS IS A MEASUREMENT OVER DONOR DATA PUSHED THROUGH A REPLAY OF AEON'S BUILD-TIME
PAGE PIPELINE. IT CHANGES NO SHIPPED ORDER AND NO ROM BYTE. Read this before quoting.

What it answers. M-B (docs/research/megaact-bg-streaming/08-m-b-window-page-set.md)
counted, for every distinct 80x60 tile-cache window a camera can hold,

    needed = | pinned pages UNION pages referenced by the window's non-blank words |

under the SHIPPED order (tile_dedupe.order_pool_spatially: first occurrence in flat
section order). This tool re-runs the same act populations with alternative orders
plugged into megaact_window_pageset.run_pipeline(order_fn=...), so the dedupe, the
64-tile page split, the 75%-of-sections pin rule (ojz_strip_gen.mark_pinned_pages) and
the per-section local palette refusal are the unmodified pipeline functions. Only the
order differs.

THE CANDIDATES (all put the blank canonical at pool slot 0, as the engine requires):
  shipped            order_pool_spatially + pin_blank_tile_first (the M-B baseline;
                     `report` re-derives M-B's committed numbers from it as a control)
  hilbert_first      tiles sorted by the first 4x4-tile block they occur in along a
                     Hilbert curve over the act (min curve index over the tile's cells)
  hilbert_centroid   tiles sorted by the Hilbert index of their mean cell position
  footprint_pack     co-occurrence packing: each tile's footprint is the set of
                     window-sized sample windows (stride 20 cols x 16 rows) it occurs
                     in; page 0 = blank + the 63 widest-footprint tiles (page 0 is
                     always pinned, so its references are already paid); every later
                     page is seeded with the earliest unassigned tile along the Hilbert
                     curve and grown one tile at a time by the candidate that adds the
                     FEWEST new sample windows to the page's footprint (ties: the wider
                     tile first), from the next FOOTPRINT_CANDIDATES unassigned tiles in
                     curve order. sum over windows of pages referenced == sum over pages
                     of windows its footprint touches, so this is a greedy on that sum.
  refined            hilbert_first, then refine_order: a deterministic group-swap local
                     search that attacks the windows over PAGE_FRAMES directly (move a
                     light page's few present tiles into a heavy page, swap back tiles
                     absent from that window), judged on superset-sampled windows whose
                     counts upper-bound the real ones; capped by a count of tries
  *_zonesplit        the same order after keying dedupe by (zone, canonical): a tile two
                     zones share gets one pool slot PER ZONE, so no zone's window can
                     reference another zone's page. Costs pool slots (reported).

MEASURED PER ACT, PER CANDIDATE: `needed` (shipped pin rule re-applied to the candidate's
pages), `needed_pin0` (page 0 only pinned: what the window alone forces), the
any-order floor ceil(distinct non-blank tiles / 64) and the per-window gap
needed - floor. Populations are READ from M-B's committed JSON (pair list, the worst and
calm pair it ranked for the offset sweep, the junction acts and alignments, the chain),
so every candidate is measured on exactly M-B's acts, not a re-ranked set.

The per-page presence count uses the page's bounding box (a page's cells outside it do
not exist), and `control` checks it against megaact_window_pageset.presence_counts and a
pure-Python direct scan.

Usage (numpy required; donors as megaact_window_pageset):
    python3 tools/megaact_page_order.py control
    python3 tools/megaact_page_order.py report --game {s2,s3k,ojz} [--json PATH] [--jobs N]
                                               [--candidates a,b] [--only chain,junction]
"""

import argparse
import json
import multiprocessing as mp
import os
import random
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import megaact_window_pageset as mb              # noqa: E402
import tile_dedupe                               # noqa: E402

MB_JSON = {
    "s2": os.path.join(REPO, "docs/research/megaact-bg-streaming/08-m-b-results-s2.json"),
    "s3k": os.path.join(REPO, "docs/research/megaact-bg-streaming/08-m-b-results-s3k.json"),
}

HILBERT_BLOCK = 4               # tiles per Hilbert cell edge (order keys)
FOOT_COLS, FOOT_ROWS = 20, 16   # footprint sample-window stride (a quarter window)
FOOTPRINT_CANDIDATES = 512      # unassigned tiles scanned per growth step


# ---------------------------------------------------------------------------
# Hilbert curve
# ---------------------------------------------------------------------------

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


def order_hilbert_centroid(ctx):
    tile, r, cc, blank = _tile_cells(ctx)
    H, W = ctx["canon"].shape
    ntile = int(tile.max()) + 1 if tile.size else 1
    n = np.bincount(tile, minlength=ntile)
    mr = np.bincount(tile, weights=r, minlength=ntile)
    mc = np.bincount(tile, weights=cc, minlength=ntile)
    present = np.flatnonzero(n)
    cr = (mr[present] / n[present]).astype(np.int64) // HILBERT_BLOCK
    ccol = (mc[present] / n[present]).astype(np.int64) // HILBERT_BLOCK
    bh, bw = -(-H // HILBERT_BLOCK), -(-W // HILBERT_BLOCK)
    d = hilbert_d(ccol, cr, _order_for(bh, bw))
    return _finish(dict(zip(present.tolist(), d.tolist())), blank)


def footprints(ctx):
    """tile ids, packed uint64 footprint matrix (tiles x words), bit counts."""
    tile, r, cc, blank = _tile_cells(ctx)
    H, W = ctx["canon"].shape
    c = ctx["c"]
    fc, fr = FOOT_COLS, FOOT_ROWS
    span_c = -(-c["TILE_CACHE_COLS"] // fc)        # blocks a window covers
    span_r = -(-c["TILE_CACHE_ROWS"] // fr)
    nbx, nby = -(-W // fc), -(-H // fr)
    blk = (r // fr) * nbx + (cc // fc)
    pairs = np.unique(tile * (nbx * nby) + blk)
    pt, pb = pairs // (nbx * nby), pairs % (nbx * nby)
    bx, by = pb % nbx, pb // nbx
    ts, bits = [], []
    for dj in range(span_r):
        for di in range(span_c):
            i, j = bx - di, by - dj
            ok = (i >= 0) & (j >= 0)
            ts.append(pt[ok])
            bits.append(j[ok] * nbx + i[ok])
    ts = np.concatenate(ts)
    bits = np.concatenate(bits)
    tiles, t_idx = np.unique(ts, return_inverse=True)
    nwords = -(-(nbx * nby) // 64)
    mat = np.zeros((len(tiles), nwords), dtype=np.uint64)
    np.bitwise_or.at(mat, (t_idx, bits // 64), np.left_shift(np.uint64(1), (bits % 64).astype(np.uint64)))
    size = np.bitwise_count(mat).sum(axis=1).astype(np.int64)
    return tiles, mat, size, blank


def order_footprint_pack(ctx):
    page = ctx["c"]["ART_POOL_PAGE_TILES"]
    tiles, mat, size, blank = footprints(ctx)
    keys, _ = _hilbert_first_keys(ctx)
    n = len(tiles)
    curve = np.array([keys[int(t)] for t in tiles.tolist()], dtype=np.int64)
    by_curve = np.lexsort((tiles, curve))            # tile rows in curve order
    assigned = np.zeros(n, dtype=bool)
    out = [blank]
    # page 0: blank + the widest footprints (page 0 is pinned by rule)
    widest = np.lexsort((tiles, -size))[:page - 1]
    assigned[widest] = True
    out += [int(tiles[i]) for i in sorted(widest.tolist(), key=lambda i: (curve[i], tiles[i]))]
    ptr = 0
    while True:
        while ptr < n and assigned[by_curve[ptr]]:
            ptr += 1
        if ptr >= n:
            break
        seed = by_curve[ptr]
        assigned[seed] = True
        members = [seed]
        psig = mat[seed].copy()
        cands = []
        q = ptr + 1
        while q < n and len(cands) < FOOTPRINT_CANDIDATES:
            if not assigned[by_curve[q]]:
                cands.append(by_curve[q])
            q += 1
        cands = np.array(cands, dtype=np.int64)
        if cands.size:
            sub = mat[cands]
            live = np.ones(len(cands), dtype=bool)
            wide = size[cands]
            while len(members) < page and live.any():
                added = np.bitwise_count(sub & ~psig).sum(axis=1).astype(np.int64)
                score = np.where(live, added * (1 << 20) - wide, np.iinfo(np.int64).max)
                k = int(np.argmin(score))
                live[k] = False
                t = cands[k]
                assigned[t] = True
                members.append(t)
                psig |= sub[k]
        out += [int(tiles[i]) for i in members]
    return out


# ---------------------------------------------------------------------------
# Targeted swap refinement (on superset-sampled windows)
# ---------------------------------------------------------------------------

REFINE_SX, REFINE_SY = 8, 4     # sample stride: one sample per 8 lefts x 2 even tops
REFINE_TARGET = 12              # the shipped PAGE_FRAMES; checked against constants at use
REFINE_MAX_TRIES = 6000         # per round; a TRY cap, not a time cap: the result must not depend on machine speed
REFINE_LIGHT, REFINE_HEAVY = 5, 6
REFINE_MAX_MOVE = 32            # tiles moved out of a light page in one group swap
REFINE_PIN_ROUNDS = 3           # re-run with the pin rule's pages counted until the pinned set is stable


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


def refine_order(ctx, base_order, target=REFINE_TARGET, max_tries=None, pinned=frozenset({0})):
    """Targeted group-swap local search on sample windows.

    State: page_of[tile], cnt[sample, page] = tiles of that page present, and
    pw[sample] = pages present OR pinned (`pinned` always includes page 0).
    Loop: take the sample with the most pages that is over `target` and not marked
    stuck; for its LIGHTEST pages P (fewest of their tiles present) and HEAVIEST pages
    Q, move P's present tiles S into Q and swap back the |S| tiles of Q that are absent
    from the sample and most often co-present with P elsewhere (page sizes unchanged,
    so the pool stays contiguous 64-tile pages). Accept iff the sample loses a page AND
    sum phi(pw) over every touched sample falls, phi(k) = 4^(k-target+2) - 1 above
    target-2 (steep: trading one window at 13 for many at 11 is refused). Otherwise
    undo and try the next (P, Q), then the group split round-robin across the heavy
    pages. Each over-target sample gets one attempt per pass; a new pass starts only if
    the last one accepted a move. Deterministic: ties break on index, and the budget is
    a count of tries, never wall time."""
    max_tries = REFINE_MAX_TRIES if max_tries is None else max_tries
    page = ctx["c"]["ART_POOL_PAGE_TILES"]
    t0 = time.perf_counter()
    tiles, inc, nwin, blank = refine_incidences(ctx)
    row = {int(t): i for i, t in enumerate(tiles.tolist())}
    npages = -(-len(base_order) // page)
    page_of = np.zeros(len(tiles), dtype=np.int32)
    members = [[] for _ in range(npages)]
    for slot, t in enumerate(base_order):
        if t == blank:
            continue
        k = row[int(t)]
        page_of[k] = slot // page
        members[slot // page].append(k)
    cnt = np.zeros((nwin, npages), dtype=np.int16)
    for k, w in enumerate(inc):
        cnt[w, page_of[k]] += 1
    pinmask = np.zeros(npages, dtype=bool)
    pinmask[sorted(pinned | {0})] = True
    pw = ((cnt > 0) | pinmask).sum(axis=1).astype(np.int32)
    start_max = int(pw.max()) if nwin else 0
    start_over = int(np.count_nonzero(pw > target))
    phi = np.array([0.0 if k <= target - 2 else float(4 ** (k - target + 2) - 1) for k in range(128)])
    t_init = time.perf_counter() - t0
    tries = accepted = 0
    stuck = set()

    def apply(moves):
        touched = np.unique(np.concatenate([inc[k] for k, _ in moves]))
        old = pw[touched].copy()
        for k, q in moves:
            cnt[inc[k], page_of[k]] -= 1
            cnt[inc[k], q] += 1
            page_of[k] = q
        sub = cnt[touched]
        pw[touched] = ((sub > 0) | pinmask).sum(axis=1)
        return touched, old

    def attempt(P, S, targets, wstar, pref):
        """Move each tile S[i] to page targets[i]; from each receiving page Q swap back
        as many of its tiles absent from wstar (best co-presence with P first). Keep
        iff wstar loses a page and phi over the touched samples falls."""
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
            # every over-target sample has been tried since the last reset: another
            # pass only if something changed during this one
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
        for P in [x for x in light.tolist() if not pinmask[x]][:REFINE_LIGHT]:
            S = [k for k in members[P] if _has(inc[k], wstar)]
            if not S or len(S) > REFINE_MAX_MOVE:
                continue
            pref = cnt[:, P] > 0
            qs = [q for q in heavy if q != P][:REFINE_HEAVY]
            for Q in qs:                                   # whole group into one page
                tries += 1
                if attempt(P, S, [Q] * len(S), wstar, pref):
                    improved = True
                    break
            if not improved and len(S) > 1 and len(qs) > 1:  # split the group across them
                tries += 1
                improved = attempt(P, S, [qs[i % len(qs)] for i in range(len(S))], wstar, pref)
            if improved:
                break
        if improved:
            accepted += 1
            accepted_this_pass += 1
        stuck.add(wstar)
    out = []
    base_pos = {int(t): i for i, t in enumerate(base_order)}
    for p in range(npages):
        # within a page keep the base order's sequence (no refinement move = base order)
        ids = sorted((int(tiles[k]) for k in members[p]), key=lambda t: base_pos[t])
        out += ([blank] + ids) if p == 0 else ids
    ctx["stats"]["refine"] = {
        "target": target, "stride": [REFINE_SX, REFINE_SY], "sample_windows": int(nwin), "incidences": int(sum(len(w) for w in inc)),
        "tries": tries, "accepted": accepted, "passes": passes, "try_cap_hit": tries >= max_tries,
        "sample_max_before": start_max, "sample_over_target_before": start_over,
        "sample_max_after": int(pw.max()) if nwin else 0,
        "sample_over_target_after": int(np.count_nonzero(pw > target)),
        "init_seconds": round(t_init, 3), "seconds": round(time.perf_counter() - t0, 3)}
    return out


def pinned_for_order(ctx, order):
    """The shipped pin rule (ojz_strip_gen.mark_pinned_pages) applied to `order`."""
    import ojz_strip_gen
    page = ctx["c"]["ART_POOL_PAGE_TILES"]
    pos = {t: i for i, t in enumerate(order)}
    pages = tile_dedupe.split_pool_into_pages(order, page)
    sets = [{pos[t] for t in sec} for sec in ctx["per_section"]]
    return frozenset(i for i, f in enumerate(ojz_strip_gen.mark_pinned_pages(pages, sets)) if f)


def order_refined(ctx):
    """hilbert_first, then refine_order; repeated with the pin rule's pinned pages
    counted as always present until the pinned set stops changing (at most
    REFINE_PIN_ROUNDS rounds)."""
    if ctx["c"]["PAGE_FRAMES"] != REFINE_TARGET:
        raise SystemExit(f"REFINE_TARGET {REFINE_TARGET} != PAGE_FRAMES {ctx['c']['PAGE_FRAMES']}: re-derive")
    t0 = time.perf_counter()
    order = order_hilbert_first(ctx)
    ctx["stats"]["base_seconds"] = round(time.perf_counter() - t0, 3)
    pinned = frozenset({0})
    rounds = []
    for _ in range(REFINE_PIN_ROUNDS):
        order = refine_order(ctx, order, pinned=pinned)
        st = ctx["stats"].pop("refine")
        new_pinned = pinned_for_order(ctx, order)
        st["pinned_counted"] = sorted(pinned)
        st["pinned_after"] = sorted(new_pinned)
        rounds.append(st)
        if new_pinned <= pinned:
            break
        pinned = pinned | new_pinned
    ctx["stats"]["refine_rounds"] = rounds
    return order


CANDIDATES = {
    "shipped": (None, False),
    "hilbert_first": (order_hilbert_first, False),
    "hilbert_centroid": (order_hilbert_centroid, False),
    "footprint_pack": (order_footprint_pack, False),
    "refined": (order_refined, False),
    "hilbert_first_zonesplit": (order_hilbert_first, True),
    "footprint_pack_zonesplit": (order_footprint_pack, True),
    "refined_zonesplit": (order_refined, True),
}


# ---------------------------------------------------------------------------
# Measurement (bbox-restricted per-page presence)
# ---------------------------------------------------------------------------

def page_presence_sums(pg, lefts, tops, cols, rows, groups):
    """groups: {name: set(page ids)}. Returns {name: int16 (tops x lefts) count of
    pages of that group present in each window}. A page's presence is computed on
    its bounding box only."""
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


class ActFixed:
    """Order-independent per-act arrays, computed once (per dedupe policy for tiles)."""

    def __init__(self, act, c):
        cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
        self.lefts, self.tops, _, _ = mb.camera_windows(c, act.content_w, act.content_h)
        self.zones_present = mb.presence_counts(act.zone_id, list(range(len(act.zones))),
                                                cols, rows, self.lefts, self.tops)
        self.reach = mb.reachable_mask(act, c, self.lefts, self.tops)
        self.floor = {}

    def classes(self):
        zp = self.zones_present
        return {"all": None, "interior_one_zone": zp <= 1,
                "seam_two_plus_zones": zp >= 2, "junction_three_plus_zones": zp >= 3}


def measure_candidate(act, c, fixed, name, frames):
    order_fn, zsplit = CANDIDATES[name]
    t0 = time.perf_counter()
    pipe = mb.run_pipeline(act, c, order_fn=order_fn, zone_split_dedupe=zsplit)
    t_pipe = time.perf_counter() - t0
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    pg = pipe["page_grid"]
    pinned = set(pipe["pinned"])
    allp = set(range(pipe["pages"]))
    sums = page_presence_sums(pg, fixed.lefts, fixed.tops, cols, rows, {
        "unpinned": allp - pinned,
        "pinned_nonzero": pinned - {0},
    })
    needed = sums["unpinned"] + len(pinned)
    needed_pin0 = sums["unpinned"] + sums["pinned_nonzero"] + 1
    fkey = "zonesplit" if zsplit else "shared"
    if fkey not in fixed.floor:
        tiles = mb.distinct_tiles_per_window(pipe["glob_grid"], fixed.lefts, fixed.tops, cols, rows)
        fixed.floor[fkey] = (tiles, -(-tiles // c["ART_POOL_PAGE_TILES"]))
    tiles, floor = fixed.floor[fkey]
    gap = needed.astype(np.int32) - floor
    res = {
        "candidate": name, "pool_tiles": pipe["pool_tiles"], "pages": pipe["pages"],
        "pinned_pages": sorted(pinned), "order_seconds": round(pipe["order_seconds"], 3),
        "order_stats": pipe["order_stats"],
        "pipeline_seconds": round(t_pipe, 3),
        "local_palette_max": pipe["local_palette_max"],
        "local_palette_refusals": len(pipe["local_palette_refusals"]),
        "needed": {}, "needed_pin0": {}, "needed_reachable": {}, "gap_to_floor": {},
        "any_order_page_floor": {},
    }
    for cname, m in fixed.classes().items():
        if m is not None and not m.any():
            continue
        res["needed"][cname] = mb.summarise(needed, frames, m)
        res["needed_pin0"][cname] = mb.summarise(needed_pin0, frames, m)
        rm = fixed.reach if m is None else (fixed.reach & m)
        res["needed_reachable"][cname] = mb.summarise(needed, frames, rm)
        g = gap if m is None else gap[m]
        res["gap_to_floor"][cname] = {"max": int(g.max()), "p50": float(np.percentile(g, 50)),
                                      "p99": float(np.percentile(g, 99))}
        res["any_order_page_floor"][cname] = {"max": int((floor if m is None else floor[m]).max())}
    res["_arrays"] = (pg, needed, pinned)
    return res


# ---------------------------------------------------------------------------
# Populations (read from M-B's committed evidence)
# ---------------------------------------------------------------------------

def populations(game, c):
    """[(group, act_builder_args)] exactly as M-B measured them."""
    st = c["SECTION_SIZE"] >> 3
    rep = json.load(open(MB_JSON[game]))
    acts = []
    for zn in rep["singles"]:
        acts.append(("single", ("single", zn)))
    for label in rep["pairs"]:
        acts.append(("pair", ("pair", label)))
    for label, rows_ in rep["vertical_offset_sensitivity"].items():
        for row in rows_:
            acts.append(("offset", ("offset", label, row["b_row_offset_tiles"])))
    for label, j in rep["junctions"].items():
        zs = [p["zone"] for p in j["placements"]]
        acts.append(("junction", ("junction", zs[0], zs[1], zs[2],
                                  j["junction_geometry"]["section_aligned"], label)))
    acts.append(("chain", ("chain", [p["zone"] for p in rep["chain"]["placements"]])))
    return acts, rep


def build_act(spec, c):
    st = c["SECTION_SIZE"] >> 3
    kind = spec[0]
    if kind == "single":
        return mb.Act(spec[1], [(mb.load_zone(spec[1]), 0, 0)], st)
    if kind == "pair":
        a, b = spec[1].split("|")
        return mb.pair_act(a, b, st)
    if kind == "offset":
        a, b = spec[1].split("|")
        za, zb = mb.load_zone(a), mb.load_zone(b)
        off = spec[2]
        base = max(0, -off)
        return mb.Act(f"{a}|{b} dy={off}", [(za, 0, base), (zb, za.words.shape[1], base + off)], st)
    if kind == "junction":
        act, _geo = mb.junction_act(spec[1], spec[2], spec[3], st, section_align=spec[4])
        if act.name != spec[5]:
            raise SystemExit(f"junction rebuild named {act.name!r}, M-B has {spec[5]!r}")
        return act
    if kind == "chain":
        return mb.chain_act(spec[1], st)
    if kind == "ojz":
        return ojz_act(c)
    raise SystemExit(f"unknown act spec {spec!r}")


def ojz_act(c):
    import act_grid
    import ojz_strip_gen
    _zone, act1 = act_grid.project_act(ojz_strip_gen.PROJECT_JSON)
    gw, gh = act_grid.section_grid(ojz_strip_gen.PROJECT_JSON)
    paths = ojz_strip_gen.require_editor_sections(os.path.join(REPO, act1["dataPath"]), gw * gh)
    blob = ojz_strip_gen.load_editor_tile_art(ojz_strip_gen.ZONE_TILESET_PATH)
    st = c["SECTION_SIZE"] >> 3
    words = np.zeros((gh * st, gw * st), dtype=np.uint16)
    for i, p in enumerate(paths):
        nt = np.array(ojz_strip_gen.load_editor_section_nametable(p), dtype=np.uint16)
        sy, sx = divmod(i, gw)
        words[sy * st:(sy + 1) * st, sx * st:(sx + 1) * st] = nt
    z = mb.Zone("OJZ", words, np.zeros(words.shape, bool), {}, blob, len(blob) // 32)
    return mb.Act("OJZ act 1", [(z, 0, 0)], st)


SALVADOR_ENV = "AEON_SALVADOR"


def _salvador():
    env = os.environ.get(SALVADOR_ENV)
    for p in ([env] if env else []) + [os.path.join(REPO, "tools", "bin", "salvador")]:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def ojz_page_rom(c, cands, log=print):
    """OJZ act 1's art-pool ROM under each candidate: page payloads (pass 6 of
    ojz_strip_gen.generate: 32 raw bytes per canonical, pool order) compressed with
    salvador and elected ZX0/raw by regenerate-level.sh's rule (keep ZX0 iff
    (stream+4)*10 <= raw*9; ZX0 padded to even). CONTROL: the shipped candidate's
    payloads must equal the committed act_pool_page<k>.bin byte for byte, and its
    elected sizes the committed .zx0/.raw files. Only the page blobs are measured; the
    per-section block streams also change under a new order and are NOT measured."""
    import subprocess
    import tempfile
    import fg_working_set as fws
    sal = _salvador()
    if sal is None:
        return {"ran": False, "why": f"no salvador at tools/bin/salvador or ${SALVADOR_ENV}"}
    act = ojz_act(c)
    out = {"ran": True, "salvador": sal, "candidates": {}}

    def elect(payload, td, k):
        src = os.path.join(td, f"p{k}.bin")
        dst = os.path.join(td, f"p{k}.zx0")
        with open(src, "wb") as fh:
            fh.write(payload)
        subprocess.run([sal, src, dst], check=True, stdout=subprocess.DEVNULL)
        z = os.path.getsize(dst) + 4
        if z * 10 <= len(payload) * 9:
            return z + (z & 1), "zx0"
        return len(payload), "raw"

    for name in cands:
        order_fn, zsplit = CANDIDATES[name]
        pipe = mb.run_pipeline(act, c, order_fn=order_fn, zone_split_dedupe=zsplit)
        order, unique = pipe["pool_order"], pipe["unique"]
        page = c["ART_POOL_PAGE_TILES"]
        payloads = [b"".join(unique[t] for t in order[i:i + page]) for i in range(0, len(order), page)]
        with tempfile.TemporaryDirectory() as td:
            sizes = [elect(p, td, k) for k, p in enumerate(payloads)]
        row = {"pages": len(payloads), "stored_bytes": sum(s for s, _ in sizes),
               "forms": [f for _, f in sizes], "pinned": pipe["pinned"]}
        if name == "shipped":
            ctl = []
            for k, p in enumerate(payloads):
                committed = open(os.path.join(fws.GEN_DIR, f"act_pool_page{k}.bin"), "rb").read()
                if committed != p:
                    ctl.append(f"page {k} payload differs from committed act_pool_page{k}.bin")
                form = sizes[k][1]
                cpath = os.path.join(fws.GEN_DIR, f"act_pool_page{k}.{form}")
                if not os.path.isfile(cpath):
                    ctl.append(f"page {k} elected {form} but committed has no act_pool_page{k}.{form}")
                elif os.path.getsize(cpath) != sizes[k][0]:
                    ctl.append(f"page {k} {form} {sizes[k][0]} B != committed {os.path.getsize(cpath)} B")
            row["control_vs_committed"] = {"problems": ctl, "ok": not ctl}
        out["candidates"][name] = row
        log(f"  ojz rom {name}: {row['stored_bytes']} B over {row['pages']} pages {row['forms']}")
    base = out["candidates"]["shipped"]["stored_bytes"]
    for name, row in out["candidates"].items():
        row["delta_vs_shipped_bytes"] = row["stored_bytes"] - base
    return out


_WORKER = {}


def _measure_spec(args):
    spec, group, cands = args
    c = _WORKER.get("c")
    if c is None:
        c, _ = mb.load_constants()
        _WORKER["c"] = c
    frames = [c["PAGE_FRAMES"], mb.OWNER_LEVER_FRAMES]
    t0 = time.perf_counter()
    act = build_act(spec, c)
    fixed = ActFixed(act, c)
    out = {"act": act.name, "group": group, "sections": act.grid_w * act.grid_h,
           "windows": int(len(fixed.lefts) * len(fixed.tops)), "candidates": {}}
    for name in cands:
        r = measure_candidate(act, c, fixed, name, frames)
        r.pop("_arrays")
        out["candidates"][name] = r
    out["elapsed_s"] = round(time.perf_counter() - t0, 2)
    return out


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def control_presence(c, samples=150, seed=7):
    """bbox presence vs megaact_window_pageset.presence_counts (full-grid integral
    images) on every window, and vs a pure-Python direct scan on sampled windows,
    for a real S3K pair under a non-shipped order. Also checks the Hilbert curve is a
    bijection with unit steps on a 64x64 square."""
    problems = []
    xs, ys = np.meshgrid(np.arange(64), np.arange(64))
    d = hilbert_d(xs.ravel(), ys.ravel(), 6)
    if sorted(d.tolist()) != list(range(64 * 64)):
        problems.append("hilbert_d is not a bijection on 64x64")
    inv = np.empty(64 * 64, dtype=np.int64)
    inv[d] = np.arange(64 * 64)
    px, py = xs.ravel()[inv], ys.ravel()[inv]
    steps = np.abs(np.diff(px)) + np.abs(np.diff(py))
    if not np.all(steps == 1):
        problems.append(f"hilbert_d has {int(np.count_nonzero(steps != 1))} non-unit steps")
    st = c["SECTION_SIZE"] >> 3
    act = mb.pair_act("LRZ1", "CNZ1", st)
    fixed = ActFixed(act, c)
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    checked = 0
    for name in ("shipped", "footprint_pack"):
        r = measure_candidate(act, c, fixed, name, [12, 10])
        pg, needed, pinned = r["_arrays"]
        labels = sorted(set(np.unique(pg).tolist()) - {-1})
        ref = mb.presence_counts(pg, labels, cols, rows, fixed.lefts, fixed.tops, weight_mask=pinned)
        full = int(np.count_nonzero(ref + len(pinned) != needed))
        if full:
            problems.append(f"{name}: {full} windows differ from megaact_window_pageset.presence_counts")
        rnd = random.Random(seed)
        for _ in range(samples):
            ti, li = rnd.randrange(len(fixed.tops)), rnd.randrange(len(fixed.lefts))
            brute = mb.window_page_set_bruteforce(pg, int(fixed.lefts[li]), int(fixed.tops[ti]), cols, rows)
            checked += 1
            if len(brute | pinned) != int(needed[ti, li]):
                problems.append(f"{name}: direct scan differs at top {fixed.tops[ti]} left {fixed.lefts[li]}")
        if name == "shipped":
            mbres = json.load(open(MB_JSON["s3k"]))["pairs"]["LRZ1|CNZ1"]
            for cls in ("all", "seam_two_plus_zones"):
                a, b = r["needed"][cls], mbres["needed"][cls]
                for k in ("positions", "max", "over_12", "over_10", "p50"):
                    if a[k] != b[k]:
                        problems.append(f"shipped {cls}.{k} {a[k]} != M-B committed {b[k]}")
    return {"windows_direct_scanned": checked, "windows_full_compared": int(needed.size) * 2,
            "problems": problems, "ok": not problems}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(game, jobs, cands, log=print, only=None):
    c, _ = mb.load_constants()
    rep = {"tool": "tools/megaact_page_order.py", "game": game, "candidates": cands,
           "frames_compared": [c["PAGE_FRAMES"], mb.OWNER_LEVER_FRAMES],
           "footprint_params": {"stride_cols": FOOT_COLS, "stride_rows": FOOT_ROWS,
                                "candidates_per_step": FOOTPRINT_CANDIDATES,
                                "hilbert_block": HILBERT_BLOCK}}
    log("control: OJZ glue replay ...")
    ctl = mb.control_ojz(c)
    rep["control_ojz"] = {k: v for k, v in ctl.items()}
    if not ctl["ok"]:
        rep["refused"] = "OJZ glue control failed"
        return rep
    log("control: presence counting + hilbert + shipped vs M-B ...")
    cp = control_presence(c)
    rep["control_presence"] = cp
    log(f"  ok={cp['ok']} problems={cp['problems'][:3]}")
    if not cp["ok"]:
        rep["refused"] = "presence control failed"
        return rep
    if game == "ojz":
        specs = [("ojz", ("ojz",))]
        rep["ojz_rom"] = ojz_page_rom(c, cands, log)
    else:
        specs, mbrep = populations(game, c)
        rep["mb_population_counts"] = {
            "singles": len(mbrep["singles"]), "pairs": len(mbrep["pairs"]),
            "offsets": sum(len(v) for v in mbrep["vertical_offset_sensitivity"].values()),
            "junctions": len(mbrep["junctions"]), "chain": 1}
    if only:
        specs = [(g, sp) for g, sp in specs if g in only]
        rep["only_groups"] = only
    work = [(spec, group, cands) for group, spec in specs]
    # biggest first so the chain does not start last
    work.sort(key=lambda w: 0 if w[1] == "chain" else 1)
    acts = []
    t0 = time.time()
    if jobs > 1:
        ctx = mp.get_context("fork")
        with ctx.Pool(jobs) as pool:
            for i, r in enumerate(pool.imap_unordered(_measure_spec, work)):
                acts.append(r)
                log(f"  [{i + 1}/{len(work)}] {r['group']:8} {r['act']}  {r['elapsed_s']}s  "
                    + " ".join(f"{n}={v['needed']['all']['max']}" for n, v in r["candidates"].items()))
    else:
        for i, w in enumerate(work):
            r = _measure_spec(w)
            acts.append(r)
            log(f"  [{i + 1}/{len(work)}] {r['group']:8} {r['act']}  {r['elapsed_s']}s  "
                + " ".join(f"{n}={v['needed']['all']['max']}" for n, v in r["candidates"].items()))
    rep["wall_seconds"] = round(time.time() - t0, 1)
    rep["acts"] = sorted(acts, key=lambda r: (r["group"], r["act"]))
    rep["population_counts_measured"] = {g: sum(1 for a in acts if a["group"] == g)
                                         for g in sorted({a["group"] for a in acts})}
    rep["summary"] = summarise_groups(rep["acts"], cands, rep["frames_compared"])
    if game != "ojz":
        rep["control_shipped_vs_mb"] = shipped_vs_mb(rep["acts"], mbrep, rep["frames_compared"])
        cm = rep["control_shipped_vs_mb"]
        log(f"control: shipped vs M-B committed: {cm['acts_compared']} acts, "
            f"{cm['values_compared']} values, {len(cm['mismatches'])} mismatches")
        if cm["mismatches"] or cm["acts_compared"] != len(acts):
            rep["refused"] = "the shipped candidate does not re-derive M-B's committed numbers"
    return rep


def shipped_vs_mb(acts, mbrep, frames):
    """Every act's shipped-candidate numbers against the value M-B committed for it."""
    F, L = frames
    offs = {}
    for label, rows_ in mbrep["vertical_offset_sensitivity"].items():
        a, b = label.split("|")
        for row in rows_:
            offs[f"{a}|{b} dy={row['b_row_offset_tiles']}"] = row
    by_name = {}
    for zn, v in mbrep["singles"].items():
        by_name[v["act"]] = v
    for v in list(mbrep["pairs"].values()) + list(mbrep["junctions"].values()) + [mbrep["chain"]]:
        by_name[v["act"]] = v
    mism, n_vals, n_acts = [], 0, 0
    for a in acts:
        mine = a["candidates"]["shipped"]
        if a["group"] == "offset":
            ref = offs.get(a["act"])
            if ref is None:
                mism.append(f"{a['act']}: not in M-B")
                continue
            s = mine["needed"].get("seam_two_plus_zones", {})
            pairs_ = [("seam_max", s.get("max")), ("seam_p50", s.get("p50")),
                      ("seam_positions", s.get("positions")), ("seam_over_frames", s.get(f"over_{F}")),
                      ("seam_over_lever", s.get(f"over_{L}")), ("pages", mine["pages"])]
            for k, v in pairs_:
                n_vals += 1
                if ref[k] != v:
                    mism.append(f"{a['act']}: {k} {v} != M-B {ref[k]}")
            n_acts += 1
            continue
        ref = by_name.get(a["act"])
        if ref is None:
            mism.append(f"{a['act']}: not in M-B")
            continue
        n_acts += 1
        for k in ("pages", "pool_tiles"):
            n_vals += 1
            if ref[k] != mine[k]:
                mism.append(f"{a['act']}: {k} {mine[k]} != M-B {ref[k]}")
        n_vals += 1
        if ref["pinned_pages"] != mine["pinned_pages"]:
            mism.append(f"{a['act']}: pinned {mine['pinned_pages']} != M-B {ref['pinned_pages']}")
        for cls, s in mine["needed"].items():
            rs = ref["needed"].get(cls, {})
            for k in ("positions", "max", "p50", "p99", f"over_{F}", f"over_{L}"):
                n_vals += 1
                if rs.get(k) != s.get(k):
                    mism.append(f"{a['act']}: needed.{cls}.{k} {s.get(k)} != M-B {rs.get(k)}")
    return {"acts_compared": n_acts, "values_compared": n_vals, "mismatches": mism}


def summarise_groups(acts, cands, frames):
    """Per (group, class, candidate): acts measured, windows, worst, acts over F,
    windows over F; plus pin0 and the worst gap. Classes: the group's own subject
    (single/pair-interior -> all, pair/offset -> seam, junction -> junction, chain -> all)."""
    F, L = frames
    subject = {"single": ["all"], "pair": ["seam_two_plus_zones", "interior_one_zone"],
               "offset": ["seam_two_plus_zones"], "junction": ["junction_three_plus_zones"],
               "chain": ["all", "interior_one_zone", "seam_two_plus_zones"], "ojz": ["all"]}
    out = {}
    for group in sorted({a["group"] for a in acts}):
        for cls in subject[group]:
            for name in cands:
                row = {"acts": 0, "windows": 0, "worst": 0, f"acts_over_{F}": 0, f"acts_over_{L}": 0,
                       f"windows_over_{F}": 0, f"windows_over_{L}": 0,
                       f"pin0_windows_over_{F}": 0, f"pin0_windows_over_{L}": 0, "pin0_worst": 0,
                       "worst_gap_to_floor": 0, "worst_floor": 0, "pinned_max": 0,
                       "order_seconds_max": 0.0, "pool_tiles_delta_vs_shipped_max": 0}
                for a in acts:
                    if a["group"] != group:
                        continue
                    r = a["candidates"][name]
                    n = r["needed"].get(cls)
                    if not n or not n.get("positions"):
                        continue
                    p0 = r["needed_pin0"][cls]
                    row["acts"] += 1
                    row["windows"] += n["positions"]
                    row["worst"] = max(row["worst"], n["max"])
                    row["pin0_worst"] = max(row["pin0_worst"], p0["max"])
                    for f in (F, L):
                        row[f"windows_over_{f}"] += n[f"over_{f}"]
                        row[f"acts_over_{f}"] += 1 if n[f"over_{f}"] else 0
                        row[f"pin0_windows_over_{f}"] += p0[f"over_{f}"]
                    row["worst_gap_to_floor"] = max(row["worst_gap_to_floor"], r["gap_to_floor"][cls]["max"])
                    row["worst_floor"] = max(row["worst_floor"], r["any_order_page_floor"][cls]["max"])
                    row["pinned_max"] = max(row["pinned_max"], len(r["pinned_pages"]))
                    row["order_seconds_max"] = max(row["order_seconds_max"], r["order_seconds"])
                    row["pool_tiles_delta_vs_shipped_max"] = max(
                        row["pool_tiles_delta_vs_shipped_max"],
                        r["pool_tiles"] - a["candidates"]["shipped"]["pool_tiles"]
                        if "shipped" in a["candidates"] else 0)
                out[f"{group}/{cls}/{name}"] = row
    return out


USAGE = """Usage:
    python3 tools/megaact_page_order.py control
    python3 tools/megaact_page_order.py report --game {s2,s3k,ojz} [--json PATH] [--jobs N] [--candidates a,b] [--only groups]"""


def _mode_control(rest):
    if rest:
        print(f"ERROR: unknown argument {rest[0]!r}")
        print(USAGE)
        sys.exit(1)
    c, _ = mb.load_constants()
    out = control_presence(c)
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


def _mode_report(rest):
    # the one WRITING mode: --json PATH writes the evidence file
    ap = argparse.ArgumentParser(prog="megaact_page_order.py report")
    ap.add_argument("--game", choices=["s2", "s3k", "ojz"], required=True)
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--candidates", default=",".join(CANDIDATES))
    ap.add_argument("--only", default=None,
                    help="comma list of groups (single,pair,offset,junction,chain) to measure")
    args = ap.parse_args(rest)
    cands = args.candidates.split(",")
    unknown = [x for x in cands if x not in CANDIDATES]
    if unknown or "shipped" not in cands:
        print(f"ERROR: candidates must include 'shipped' and be among {sorted(CANDIDATES)}; got {unknown}")
        sys.exit(1)
    only = args.only.split(",") if args.only else None
    rep = build_report(args.game, args.jobs, cands, log=lambda m: print(m, flush=True), only=only)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rep, fh, separators=(",", ":"))
            fh.write("\n")
    if "refused" in rep:
        print("REFUSED:", rep["refused"])
        return 2
    print("finished=ok")
    return 0


# ONE list of legal modes, and it is the dispatch table (LS-15d shape,
# tools/test_cli_dispatch_refuses.py). An unknown or missing mode prints usage and
# exits 1 BEFORE any handler; nothing is a default.
MODES = {
    "control": _mode_control,
    "report": _mode_report,
}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    mode = args[0] if args else None
    handler = MODES.get(mode)
    if handler is None:
        print(USAGE)
        sys.exit(1)
    return handler(args[1:])


if __name__ == "__main__":
    sys.exit(main())
