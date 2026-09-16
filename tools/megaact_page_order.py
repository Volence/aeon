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
    python3 tools/megaact_page_order.py timing [--json PATH]
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


CANDIDATES = {
    "shipped": (None, False),
    "hilbert_first": (order_hilbert_first, False),
    "hilbert_centroid": (order_hilbert_centroid, False),
    "footprint_pack": (order_footprint_pack, False),
    "hilbert_first_zonesplit": (order_hilbert_first, True),
    "footprint_pack_zonesplit": (order_footprint_pack, True),
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

def build_report(game, jobs, cands, log=print):
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
    else:
        specs, mbrep = populations(game, c)
        rep["mb_population_counts"] = {
            "singles": len(mbrep["singles"]), "pairs": len(mbrep["pairs"]),
            "offsets": sum(len(v) for v in mbrep["vertical_offset_sensitivity"].values()),
            "junctions": len(mbrep["junctions"]), "chain": 1}
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
    return rep


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
    python3 tools/megaact_page_order.py report --game {s2,s3k,ojz} [--json PATH] [--jobs N] [--candidates a,b]"""


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
    args = ap.parse_args(rest)
    cands = args.candidates.split(",")
    unknown = [x for x in cands if x not in CANDIDATES]
    if unknown or "shipped" not in cands:
        print(f"ERROR: candidates must include 'shipped' and be among {sorted(CANDIDATES)}; got {unknown}")
        sys.exit(1)
    rep = build_report(args.game, args.jobs, cands, log=lambda m: print(m, flush=True))
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
