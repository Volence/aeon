#!/usr/bin/env python3
"""megaact_fg_cache10.py — FG-CACHE-10-RESEARCH: can M-B's stitched S2/S3K
populations fit a foreground art cache of 10 x 64-tile frames (640 tiles)?

THIS IS A MEASUREMENT OVER DONOR DATA PUSHED THROUGH A REPLAY OF AEON'S BUILD-TIME
PAGE PIPELINE, WITH SOME ENGINE CONSTANTS SET TO HYPOTHETICAL VALUES. IT CHANGES NO
SHIPPED ORDER, NO CONSTANT AND NO ROM BYTE. Read this before quoting a number.

The count is M-B's and report 09's (docs/research/megaact-bg-streaming/08-*, 09-*):

    needed(window) = | pinned pages UNION pages referenced by the window's non-blank words |

and a window is OVER at budget F when needed > F. Report 09 found the best order
(`refined_zonesplit`) fits every population at 12 frames but leaves 3.76% of the S3K
row's windows over 10. This tool measures the levers 09 named but did not build, and
their combinations, on exactly the same acts:

  LEVER 1  PIN POLICY    rule75 (shipped: page 0 + pages >= 75% of sections reference),
                         pin0 (page 0 only), frameaware (rule75's candidates, each kept
                         only if it pushes no window from <= F to > F).
  LEVER 2  WINDOW        the tile-cache geometry: TILE_CACHE_MARGIN_H/V and COLS/ROWS set
                         to hypothetical values. Every geometry is checked against the
                         engine's own ensures (constants.emp) AND against a parity-exact
                         coverage check (every camera sub-tile offset, both row parities):
                         the held window must contain the plane fill's near and far edges.
  LEVER 3  PAGE SIZE     32-tile pages: the same 640 tiles = 20 frames.
  LEVER 4  POOLS         per-zone pages (no page mixes two zones; the last page of a zone
                         is short, which the manifest's per-page `tiles.w` allows), and
                         a shared pinned page 0 (blank + the 63 tiles with the widest
                         act-wide window footprint, deduped ACROSS zones; everything else
                         zone-split).
  ORDER                  `rzs12` = report 09's refined_zonesplit, exactly (its search
                         targets 12). `rzsF` = the same search targeting the lever's F.

WHAT IS REAL AND WHAT IS NEW
  REAL, called unmodified: megaact_window_pageset (donor loading, acts, window sweep,
  presence counts, reachability, OJZ glue control), megaact_page_order (populations,
  hilbert_first order, page_presence_sums, refine_order, control_presence),
  tile_dedupe, ojz_strip_gen.mark_pinned_pages / build_section_local_map.
  NEW here, each with a control that ties it to the real code before it is used:
  * `run_pipeline_ext` generalises megaact_window_pageset.run_pipeline with a split
    policy and explicit page sizes. CONTROL: under split none/zone and contiguous
    pages it must reproduce run_pipeline's page grid, pool order and pins exactly.
  * `refine_pages` generalises megaact_page_order.refine_order to explicit page
    member lists and a same-zone move constraint. CONTROL: with contiguous pages and
    no constraint it must return refine_order's order exactly.
  * `rederive`: report 09's per-act numbers for `shipped` and `refined_zonesplit`
    must come back out of THIS tool's measurement path (shipped geometry, 64-tile
    pages, rule75) with 0 mismatches before any lever number is trusted.

ALSO MEASURED per window step (the timing cost of lever 2): how many pages ENTER the
window when it moves one column or one row pair, and the lead (in columns/rows and in
frames at the 16 px/frame camera cap) between the window's edge and the plane fill's
edge. The latency those leads must cover is DERIVED from cited numbers (ARCH §9.7:
~45 K cycles per ZX0 page against ~42.5 K idle per frame), never measured here.

NOT COVERED (as M-B and 09): object/sprite art, the BG plane, animated tiles, transient
frame demand (in-flight decode, published-but-unreferenced pages, stalled columns
holding old references), eviction order in motion, runtime. Collision range for
objects outside a smaller window is a COST named in the report, not simulated.

Usage (numpy required; donors as megaact_window_pageset; salvador for `rom`):
    python3 tools/megaact_fg_cache10.py control
    python3 tools/megaact_fg_cache10.py rederive --game {s2,s3k,ojz} [--jobs N] [--json PATH]
    python3 tools/megaact_fg_cache10.py sweep --game {s2,s3k,ojz} --configs a,b [--jobs N]
                                        [--only groups] [--acts name,name] [--bursts] [--json PATH]
    python3 tools/megaact_fg_cache10.py rom --game {s2,s3k,ojz} --configs a,b [--json PATH]
    python3 tools/megaact_fg_cache10.py configs
"""

import argparse
import re
import json
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import megaact_window_pageset as mb              # noqa: E402
import megaact_page_order as mpo                 # noqa: E402
import ojz_strip_gen                             # noqa: E402
import tile_dedupe                               # noqa: E402

P09_JSON = {g: os.path.join(REPO, f"docs/research/megaact-bg-streaming/09-page-order-results-{g}.json")
            for g in ("s2", "s3k", "ojz")}

# The owner's lever: POOL_TILE_CEILING 768 -> 640 (constants.emp:856-871 names the 640 /
# 10-frame floor). Held as FRAMES x the shipped page size so it is derived, not typed.
LEVER_FRAMES_64 = mb.OWNER_LEVER_FRAMES


def lever_pool_tiles(c):
    return LEVER_FRAMES_64 * c["ART_POOL_PAGE_TILES"]


# ---------------------------------------------------------------------------
# Configurations
# ---------------------------------------------------------------------------

# geometry name -> (margin_h, margin_v, cols, rows); None cols/rows = screen + 2*margin
GEOMETRIES = {
    "g80x60": (20, 16, 80, 60),         # shipped (checked against constants at use)
    "g72x52": (16, 12, None, None),
    "g64x48": (12, 10, None, None),
    "g60x44": (10, 8, None, None),
    "g56x40": (8, 6, None, None),
    "g52x36": (6, 4, None, None),
    "g48x36": (4, 4, None, None),
    "g44x34": (2, 3, None, None),
}


def config(name):
    """name = <geometry>/<page tiles>/<split>/<order>/<pin>, e.g. g80x60/64/zone/rzs12/rule75.
    split: none | zone | perzone | page0shared.  order: shipped | rzs12 | rzsF.
    pin: rule75 | pin0 | frameaware."""
    parts = name.split("/")
    if len(parts) != 5:
        raise SystemExit(f"config {name!r}: want geometry/page/split/order/pin")
    g, p, s, o, pin = parts
    if g not in GEOMETRIES:
        raise SystemExit(f"config {name!r}: unknown geometry {g!r} (have {sorted(GEOMETRIES)})")
    if p not in ("64", "32"):
        raise SystemExit(f"config {name!r}: page tiles must be 64 or 32")
    if s not in ("none", "zone", "perzone", "page0shared"):
        raise SystemExit(f"config {name!r}: unknown split {s!r}")
    if o not in ("shipped", "rzs12") and not re.fullmatch(r"rzs(12)?F(t[0-9]+)?(s[0-9]+)?(w)?(d[0-9]+)?", o):
        raise SystemExit(f"config {name!r}: unknown order {o!r}")
    if pin not in ("rule75", "pin0", "frameaware"):
        raise SystemExit(f"config {name!r}: unknown pin policy {pin!r}")
    if o == "shipped" and s != "none":
        raise SystemExit(f"config {name!r}: the shipped order is only defined with split none")
    if o == "rzs12" and (s != "zone" or p != "64" or pin != "rule75"):
        raise SystemExit(f"config {name!r}: rzs12 is report 09's exact candidate: split zone, 64, rule75")
    dm = re.search(r"d([0-9]+)$", o)
    spare = int(dm.group(1)) if dm else 0
    if spare and (pin == "rule75" or spare >= int(p) // 2):
        raise SystemExit(f"config {name!r}: duplication fixup needs pin0/frameaware and spare < page/2")
    return {"name": name, "geometry": g, "page_tiles": int(p), "split": s, "order": o, "pin": pin,
            "spare": spare}


def geometry_constants(c, gname):
    """A copy of the engine constants with the tile-cache geometry replaced; refuses a
    geometry the engine's ensures would refuse, or whose held window can miss the plane
    fill's edges at any camera sub-tile offset or row parity. Returns (c2, facts)."""
    mh, mv, cols, rows = GEOMETRIES[gname]
    sw, sh = c["SCREEN_WIDTH"] >> 3, c["SCREEN_HEIGHT"] >> 3
    cols = sw + 2 * mh if cols is None else cols
    rows = sh + 2 * mv if rows is None else rows
    if gname == "g80x60" and (mh, mv, cols, rows) != (c["TILE_CACHE_MARGIN_H"], c["TILE_CACHE_MARGIN_V"],
                                                      c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]):
        raise SystemExit("g80x60 no longer matches the shipped TILE_CACHE_* constants: re-derive")
    c2 = dict(c)
    c2.update({"TILE_CACHE_MARGIN_H": mh, "TILE_CACHE_MARGIN_V": mv,
               "TILE_CACHE_COLS": cols, "TILE_CACHE_ROWS": rows})
    reach_c = (7 + c["SECTION_H_REACH_PX"]) >> 3
    reach_r = (7 + c["SECTION_V_REACH_PX"]) >> 3
    problems = []
    # the engine's own ensures (constants.emp:899-900, :969-972)
    if rows % 2:
        problems.append("TILE_CACHE_ROWS odd")
    if cols < mh + reach_c + 1:
        problems.append("COLS < MARGIN_H + reach + 1 (engine ensure)")
    if rows < mv + reach_r + 1:
        problems.append("ROWS < MARGIN_V + reach + 1 (engine ensure)")
    # parity-exact coverage + lead, at every sub-tile offset and both tile parities
    lead_right = lead_left = lead_down = lead_up = 1 << 30
    binds = True
    for base in (8 * 1000, 8 * 1001):
        for f in range(8):
            cam = base + f
            l, r, t, b = mb.window_for_camera(c2, cam, cam)
            if r - l + 1 != cols or b - t + 1 != rows:
                binds = False
            held_r, held_b = l + cols - 1, t + rows - 1
            plane_l, plane_t = cam >> 3, cam >> 3
            plane_r = (cam + c["SECTION_H_REACH_PX"]) >> 3
            plane_b = (cam + c["SECTION_V_REACH_PX"]) >> 3
            if l > plane_l or held_r < plane_r:
                problems.append(f"columns miss the plane fill at cam {cam}")
            if t > plane_t or held_b < plane_b:
                problems.append(f"rows miss the plane fill at cam {cam} (parity {(cam >> 3) & 1})")
            lead_right = min(lead_right, held_r - plane_r)
            lead_left = min(lead_left, plane_l - l)
            lead_down = min(lead_down, held_b - plane_b)
            lead_up = min(lead_up, plane_t - t)
    if not binds:
        problems.append("far-edge clamp does not bind: held window would depend on travel direction")
    if problems:
        raise SystemExit(f"geometry {gname} {cols}x{rows} refused: {sorted(set(problems))}")
    facts = {"geometry": gname, "cols": cols, "rows": rows, "margin_h": mh, "margin_v": mv,
             "lead_cols_right": lead_right, "lead_cols_left": lead_left,
             "lead_rows_down": lead_down, "lead_rows_up": lead_up,
             "nametable_bytes": cols * rows * 2, "collision_bytes": cols * (rows // 2) * 2}
    return c2, facts


def page_constants(c, page_tiles):
    c2 = dict(c)
    shift = page_tiles.bit_length() - 1
    if (1 << shift) != page_tiles:
        raise SystemExit("page tiles must be a power of two")
    c2["ART_POOL_PAGE_TILES"] = page_tiles
    c2["PAGE_FRAME_TILE_SHIFT"] = shift
    return c2


# ---------------------------------------------------------------------------
# Pipeline, generalised (controlled against megaact_window_pageset.run_pipeline)
# ---------------------------------------------------------------------------

def _dedupe(act):
    key = np.where(act.zone_id < 0, 0,
                   (act.zone_id.astype(np.int64) + 1) * 4096 + act.src).astype(np.int64)
    ref = np.unique(key)
    raw = []
    for k in ref.tolist():
        if k == 0:
            raw.append(tile_dedupe.BLANK_TILE)
        else:
            z = act.zones[k // 4096 - 1]
            i = k % 4096
            raw.append(z.art[i * 32:(i + 1) * 32])
    unique, mapping = tile_dedupe.dedupe_tiles(raw)
    key_to_canon = np.array([m[0] for m in mapping], dtype=np.int64)
    return unique, key_to_canon[np.searchsorted(ref, key)], int(len(ref))


def _split(act, unique, canon, keep_shared=frozenset()):
    """one canonical per (zone, canonical), except the blank and `keep_shared`."""
    blank_c = unique.index(tile_dedupe.BLANK_TILE) if tile_dedupe.BLANK_TILE in unique else -1
    nz = len(act.zones) + 1
    zk = canon * nz + (act.zone_id.astype(np.int64) + 1)
    collapse = canon == blank_c
    if keep_shared:
        collapse |= np.isin(canon, np.array(sorted(keep_shared), dtype=np.int64))
    zk = np.where(collapse, canon * nz, zk)
    zref, zinv = np.unique(zk, return_inverse=True)
    return [unique[int(k) // nz] for k in zref.tolist()], zinv.reshape(canon.shape).astype(np.int64), zref // nz


def run_pipeline_ext(act, c, order_fn=None, split="none", keep_shared_fn=None):
    """megaact_window_pageset.run_pipeline with (a) a split policy and (b) page sizes the
    order function may set explicitly (ctx['stats']['page_sizes']). Everything else is
    the same sequence of the same real functions."""
    st = c["SECTION_SIZE"] >> 3
    unique, canon, n_src = _dedupe(act)
    shared = []
    if split in ("zone", "perzone", "page0shared"):
        keep = frozenset()
        if split == "page0shared":
            keep = frozenset(keep_shared_fn(act, c, unique, canon))
            shared = sorted(keep)
        unique, canon, _ = _split(act, unique, canon, keep)
    per_section = []
    for sy in range(act.grid_h):
        for sx in range(act.grid_w):
            sub = canon[sy * st:(sy + 1) * st, sx * st:(sx + 1) * st]
            flat = sub.T.ravel()
            u, idx = np.unique(flat, return_index=True)
            per_section.append(u[np.argsort(idx, kind="stable")].tolist())
    t0 = time.perf_counter()
    stats = {}
    if order_fn is None:
        pool_order = tile_dedupe.order_pool_spatially(per_section)
        pool_order = tile_dedupe.pin_blank_tile_first(pool_order, unique)
    else:
        if tile_dedupe.BLANK_TILE not in unique:
            unique.append(tile_dedupe.BLANK_TILE)
        ctx = {"canon": canon, "zone_id": act.zone_id, "unique": unique, "per_section": per_section,
               "act": act, "c": c, "stats": stats, "shared_canon_before_split": shared}
        pool_order = list(order_fn(ctx))
        if sorted(pool_order) != sorted({x for s in per_section for x in s}
                                        | {unique.index(tile_dedupe.BLANK_TILE)}):
            raise SystemExit(f"{act.name}: order is not a permutation of referenced canonicals + blank")
    order_s = time.perf_counter() - t0
    assert unique[pool_order[0]] == tile_dedupe.BLANK_TILE
    canon_to_pool = np.full(len(unique), -1, dtype=np.int64)
    canon_to_pool[np.array(pool_order, dtype=np.int64)] = np.arange(len(pool_order))
    sizes = stats.get("page_sizes")
    if sizes is None:
        pages = tile_dedupe.split_pool_into_pages(pool_order, c["ART_POOL_PAGE_TILES"])
    else:
        if sum(sizes) != len(pool_order) or any(s < 1 or s > c["ART_POOL_PAGE_TILES"] for s in sizes):
            raise SystemExit(f"{act.name}: explicit page sizes do not tile the pool")
        pages, o = [], 0
        for s in sizes:
            pages.append(pool_order[o:o + s])
            o += s
    slot_page = np.concatenate([np.full(len(p), i, dtype=np.int64) for i, p in enumerate(pages)])
    sets = [set(canon_to_pool[np.array(s, dtype=np.int64)].tolist()) for s in per_section]
    pinned_flags = ojz_strip_gen.mark_pinned_pages(pages, sets)
    pal_max, refusals = 0, 0
    for gs in sets:
        try:
            pal_max = max(pal_max, len(ojz_strip_gen.build_section_local_map(gs)))
        except ValueError:
            refusals += 1
    glob = canon_to_pool[canon]
    page_grid = np.where(glob == 0, -1, slot_page[glob]).astype(np.int16)
    return {"page_grid": page_grid, "pinned": [i for i, f in enumerate(pinned_flags) if f],
            "pages": len(pages), "page_sizes": [len(p) for p in pages], "pool_tiles": len(pool_order),
            "source_tiles": n_src, "sections": act.grid_w * act.grid_h,
            "local_palette_max": pal_max, "local_palette_refusals": refusals,
            "per_section_global_sets": sets, "glob_grid": glob, "order_seconds": order_s,
            "order_stats": stats, "pool_order": pool_order, "unique": unique, "canon": canon,
            "shared_kept": len(shared)}


# ---------------------------------------------------------------------------
# Refinement over explicit pages (controlled against megaact_page_order.refine_order)
# ---------------------------------------------------------------------------

def refine_pages(ctx, pages, target, max_tries=None, pinned=frozenset({0}), group=None, max_move=None,
                 stride=None, light_n=None, heavy_n=None):
    """megaact_page_order.refine_order over explicit page member lists (canonical ids,
    page 0 includes the blank) with an optional same-group move constraint (`group[p]`:
    moves only between pages of one group). Same samples, cost, move, loop and
    determinism; the only additions are the page lists and the constraint. Returns
    the new page lists (sizes unchanged)."""
    max_tries = mpo.REFINE_MAX_TRIES if max_tries is None else max_tries
    max_move = mpo.REFINE_MAX_MOVE if max_move is None else max_move
    t0 = time.perf_counter()
    light_n = mpo.REFINE_LIGHT if light_n is None else light_n
    heavy_n = mpo.REFINE_HEAVY if heavy_n is None else heavy_n
    sx, sy = (mpo.REFINE_SX, mpo.REFINE_SY) if stride is None else stride
    tiles, inc, nwin, blank = mpo.refine_incidences(ctx, sx, sy)
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
            outq = [u for u in members[q] if not mpo._has(inc[u], wstar)]
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
            S = [k for k in members[P] if mpo._has(inc[k], wstar)]
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


def _pages_from_order(order, size):
    return [list(order[i:i + size]) for i in range(0, len(order), size)]


def _pinned_rule75(ctx, pages):
    pos, o = {}, 0
    for p in pages:
        for t in p:
            pos[t] = o
            o += 1
    sets = [{pos[t] for t in sec} for sec in ctx["per_section"]]
    return frozenset(i for i, f in enumerate(ojz_strip_gen.mark_pinned_pages(pages, sets)) if f)


def _zone_of_canon(ctx):
    tile, r, cc, blank = mpo._tile_cells(ctx)
    z = ctx["zone_id"][r, cc].astype(np.int64)
    pairs = np.unique(tile * 256 + z)
    t, zz = pairs // 256, pairs % 256
    multi = np.flatnonzero(np.r_[False, t[1:] == t[:-1]])
    return dict(zip(t.tolist(), zz.tolist())), set(t[multi].tolist())


def make_order(cfg, target):
    """Order function for a config (None for the shipped order)."""
    if cfg["order"] == "shipped":
        return None
    # rzs12: 09's search (target 12). rzsF: target F. rzs12F: 09's search, then a second
    # search at F starting from its result. A trailing t<k> multiplies the try budget by k.
    m = re.fullmatch(r"rzs(12)?(F)?(?:t([0-9]+))?(?:s([0-9]+))?(w)?(?:d[0-9]+)?", cfg["order"])
    stages = [12] if m.group(1) else []
    if m.group(2):
        stages.append(target)
    tries = mpo.REFINE_MAX_TRIES * int(m.group(3) or 1)
    # s<k>: sample stride k lefts x k tops (tops even, so k >= 2); w: wider move search
    knobs = {}
    if m.group(4):
        k = int(m.group(4))
        knobs["stride"] = (k, max(2, k if k % 2 == 0 else k + 1))
    if m.group(5):
        knobs["light_n"], knobs["heavy_n"] = 2 * mpo.REFINE_LIGHT, 2 * mpo.REFINE_HEAVY
    if cfg["pin"] == "rule75" and len(stages) > 1:
        raise SystemExit("two-stage orders are measured with pin0/frameaware only")
    rounds = mpo.REFINE_PIN_ROUNDS if cfg["pin"] == "rule75" else 1

    spare = cfg.get("spare", 0)

    def fn(ctx):
        # d<k>: every page is built k slots short, the room the duplication fixup fills
        page = ctx["c"]["ART_POOL_PAGE_TILES"] - spare
        base = mpo.order_hilbert_first(ctx)
        group = None
        if cfg["split"] == "perzone":
            zone_of, multi = _zone_of_canon(ctx)
            if multi:
                raise SystemExit(f"perzone: {len(multi)} canonicals occur in more than one zone after the split")
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
        elif cfg["split"] == "page0shared":
            # the kept-shared canonicals (one each after the split) fill page 0 behind the
            # blank, in base order; every other tile follows in base order
            if "_shared_ids" not in ctx:
                raise SystemExit("page0shared: ctx lacks _shared_ids")
            ids = set(ctx["_shared_ids"])
            if len(ids) > ctx["c"]["ART_POOL_PAGE_TILES"] - 1:
                raise SystemExit("page0shared: more kept tiles than page 0 holds")
            p0 = [base[0]] + [t for t in base[1:] if t in ids][:page - 1]
            ids = set(p0[1:])
            rest = [t for t in base[1:] if t not in ids]
            pages = [p0] + _pages_from_order(rest, page)
        else:
            pages = _pages_from_order(base, page)
        pinned = frozenset({0})
        for _ in range(rounds):
            if len(stages) == 1:
                pages = refine_pages(ctx, pages, stages[0], max_tries=tries, pinned=pinned, group=group,
                                     max_move=page // 2, **knobs)
            else:
                for tgt in stages:
                    pages = refine_pages(ctx, pages, tgt, max_tries=tries, pinned=pinned, group=group,
                                         max_move=page // 2, **knobs)
            if cfg["pin"] != "rule75":
                break
            new = _pinned_rule75(ctx, pages)
            ctx["stats"]["refine_rounds"][-1]["pinned_after"] = sorted(new)
            if new <= pinned:
                break
            pinned = pinned | new
        order = [t for p in pages for t in p]
        if cfg["split"] in ("perzone", "page0shared") or spare:
            ctx["stats"]["page_sizes"] = [len(p) for p in pages]
        return order
    return fn


def widest_shared_tiles(act, c, unique, canon, n=None):
    """page0shared's keep set: the canonicals (deduped across zones) whose presence covers
    the most window samples act-wide (megaact_page_order.footprints, stride 20x16),
    blank excluded, ties on id; n = page tiles - 1."""
    n = c["ART_POOL_PAGE_TILES"] - 1 if n is None else n
    ctx = {"canon": canon, "unique": unique, "c": c}
    tiles, _mat, size, blank = mpo.footprints(ctx)
    keep = [int(tiles[i]) for i in np.lexsort((tiles, -size)) if int(tiles[i]) != blank][:n]
    return keep


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

class Fixed:
    """Per (act, geometry): windows, zone classes, reachability."""

    def __init__(self, act, c2):
        cols, rows = c2["TILE_CACHE_COLS"], c2["TILE_CACHE_ROWS"]
        self.lefts, self.tops, _, _ = mb.camera_windows(c2, act.content_w, act.content_h)
        self.zp = mb.presence_counts(act.zone_id, list(range(len(act.zones))), cols, rows, self.lefts, self.tops)
        self.reach = mb.reachable_mask(act, c2, self.lefts, self.tops)

    def classes(self):
        return {"all": None, "interior_one_zone": self.zp <= 1,
                "seam_two_plus_zones": self.zp >= 2, "junction_three_plus_zones": self.zp >= 3}


def page_presence(pg, lefts, tops, cols, rows, p):
    """bool (tops x lefts): page p present in the window (megaact_page_order bbox method)."""
    return mpo.page_presence_sums(pg, lefts, tops, cols, rows, {"x": {p}})["x"] > 0


def entering_pages(pg, lefts, tops, cols, rows, pages):
    """Max pages that ENTER a window on a one-step move, per direction: right (left+1),
    left (left-1), down (top+2), up (top-2). Also the count of steps with >= 2 entering."""
    out = {}
    acc = {d: None for d in ("right", "left", "down", "up")}
    for p in range(pages):
        pr = page_presence(pg, lefts, tops, cols, rows, p)
        if not pr.any():
            continue
        steps = {"right": pr[:, 1:] & ~pr[:, :-1], "left": pr[:, :-1] & ~pr[:, 1:],
                 "down": pr[1:, :] & ~pr[:-1, :], "up": pr[:-1, :] & ~pr[1:, :]}
        for d, m in steps.items():
            m = m.astype(np.int8)
            acc[d] = m if acc[d] is None else acc[d] + m
    for d, a in acc.items():
        if a is None or a.size == 0:
            out[d] = {"max": 0, "steps": 0, "steps_ge2": 0}
            continue
        out[d] = {"max": int(a.max()), "steps": int(a.size), "steps_ge2": int(np.count_nonzero(a >= 2)),
                  "steps_ge3": int(np.count_nonzero(a >= 3))}
    return out


def _local_presence(pg, p, ts, ls, cols, rows):
    """bool (len ts x len ls): page p present in each window, from a local integral image."""
    H, W = pg.shape
    r0, c0 = int(ts[0]), int(ls[0])
    r1, c1 = min(H, int(ts[-1]) + rows), min(W, int(ls[-1]) + cols)
    if r0 >= r1 or c0 >= c1:
        return np.zeros((len(ts), len(ls)), dtype=bool)
    ind = (pg[r0:r1, c0:c1] == p).astype(np.int32)
    h, w = ind.shape
    ii = np.zeros((h + 1, w + 1), dtype=np.int32)
    np.cumsum(np.cumsum(ind, axis=0), axis=1, out=ii[1:, 1:])
    ya = np.clip(ts - r0, 0, h)[:, None]
    yb = np.clip(ts + rows - r0, 0, h)[:, None]
    xa = np.clip(ls - c0, 0, w)[None, :]
    xb = np.clip(ls + cols - c0, 0, w)[None, :]
    return (ii[yb, xb] - ii[ya, xb] - ii[yb, xa] + ii[ya, xa]) > 0


def dup_fixup(pg, glob, page_sizes, cap, F, lefts, tops, cols, rows, max_dup=16, max_passes=6):
    """Duplication fixup, pinned = {page 0}. For a window over F, take its unpinned page
    P with the fewest distinct tiles present in it and copy those tiles into a page Q the
    window already references (or page 0) that has spare slots (a copy already in Q is
    reused), then re-point that window's cells of those tiles (first try: the window's
    own cells; second: the window grown by half a window each side). Kept only if the
    window loses a page, no window crosses from <= F to > F, and the summed excess over
    F falls, all judged EXACTLY on every window the change can touch. Returns the new
    page grid, the new slot grid, per-page fill and counters; the caller re-measures
    from scratch and compares."""
    pg = pg.copy()
    glob = glob.copy()
    fill = list(page_sizes)
    npages = len(fill)
    slot_page = np.concatenate([np.full(n, i, dtype=np.int64) for i, n in enumerate(page_sizes)]).tolist()
    root = list(range(len(slot_page)))
    copies = {}
    sums = mpo.page_presence_sums(pg, lefts, tops, cols, rows, {"u": set(range(1, npages))})["u"]
    needed = sums.astype(np.int32) + 1
    lefts = np.asarray(lefts)
    tops = np.asarray(tops)
    H, W = pg.shape
    added = accepted = attempts = passes = 0
    for passes in range(1, max_passes + 1):
        over = np.flatnonzero(needed.ravel() > F)
        if over.size == 0:
            break
        order = over[np.argsort(-needed.ravel()[over], kind="stable")]
        kept_this_pass = 0
        for flat in order.tolist():
            ti, li = divmod(flat, needed.shape[1])
            if needed[ti, li] <= F:
                continue
            top, left = int(tops[ti]), int(lefts[li])
            wpg = pg[top:top + rows, left:left + cols]
            wgl = glob[top:top + rows, left:left + cols]
            live = wpg >= 0
            pages_here, cells_here = np.unique(wpg[live], return_counts=True)
            roots_by_page = {}
            for sl in np.unique(wgl[live]).tolist():
                roots_by_page.setdefault(slot_page[sl], set()).add(root[sl])
            cand_p = sorted((len(roots_by_page[p]), p) for p in pages_here.tolist() if p != 0)
            q_order = [0] + [int(p) for p in pages_here[np.argsort(-cells_here, kind="stable")].tolist() if p != 0]
            done = False
            for nroots, P in cand_p:
                if nroots > max_dup:
                    break
                S = roots_by_page[P]
                s_arr = np.array(sorted(S), dtype=np.int64)
                for Q in q_order:
                    if Q == P:
                        continue
                    cost = sum(1 for r in S if (r, Q) not in copies)
                    if fill[Q] + cost > cap:
                        continue
                    for grow in (0, 1):
                        attempts += 1
                        gr, gc = (rows // 2, cols // 2) if grow else (0, 0)
                        R0, R1 = max(0, top - gr), min(H, top + rows + gr)
                        C0, C1 = max(0, left - gc), min(W, left + cols + gc)
                        sub_pg = pg[R0:R1, C0:C1]
                        sub_gl = glob[R0:R1, C0:C1]
                        roots_arr = np.array(root, dtype=np.int64)
                        mask = (sub_pg == P) & np.isin(roots_arr[np.maximum(sub_gl, 0)], s_arr)
                        if not mask.any():
                            continue
                        rr, cc = np.nonzero(mask)
                        br0, br1 = R0 + int(rr.min()), R0 + int(rr.max())
                        bc0, bc1 = C0 + int(cc.min()), C0 + int(cc.max())
                        ta = int(np.searchsorted(tops, br0 - rows + 1))
                        tb = int(np.searchsorted(tops, br1, side="right"))
                        la = int(np.searchsorted(lefts, bc0 - cols + 1))
                        lb = int(np.searchsorted(lefts, bc1, side="right"))
                        ts, ls = tops[ta:tb], lefts[la:lb]
                        beforeP = _local_presence(pg, P, ts, ls, cols, rows)
                        beforeQ = _local_presence(pg, Q, ts, ls, cols, rows) if Q != 0 else None
                        saved = sub_pg[mask].copy()
                        sub_pg[mask] = Q
                        delta = _local_presence(pg, P, ts, ls, cols, rows).astype(np.int32) - beforeP
                        if Q != 0:
                            delta += _local_presence(pg, Q, ts, ls, cols, rows).astype(np.int32) - beforeQ
                        old = needed[ta:tb, la:lb]
                        new = old + delta
                        ok = (new[ti - ta, li - la] < old[ti - ta, li - la]
                              and not np.any((old <= F) & (new > F))
                              and np.maximum(new - F, 0).sum() < np.maximum(old - F, 0).sum())
                        if not ok:
                            sub_pg[mask] = saved
                            continue
                        for r in sorted(S):
                            if (r, Q) not in copies:
                                copies[(r, Q)] = len(slot_page)
                                slot_page.append(Q)
                                root.append(r)
                                fill[Q] += 1
                                added += 1
                        gl_old = sub_gl[mask]
                        sub_gl[mask] = np.array([copies[(root[x], Q)] for x in gl_old.tolist()], dtype=sub_gl.dtype)
                        needed[ta:tb, la:lb] = new
                        accepted += 1
                        kept_this_pass += 1
                        done = True
                        break
                    if done:
                        break
                if done:
                    break
        if kept_this_pass == 0:
            break
    return pg, glob, fill, {"tiles_added": added, "accepted": accepted, "attempts": attempts,
                            "passes": passes, "cap": cap,
                            "over_after_incremental": int(np.count_nonzero(needed > F)), "_needed": needed}


def measure(act, c, cfg, fixed_cache, frames_ref, bursts=False):
    cg, geo = geometry_constants(c, cfg["geometry"])
    c2 = page_constants(cg, cfg["page_tiles"])
    F = lever_pool_tiles(c) // cfg["page_tiles"]
    F_ship = c["POOL_TILE_CEILING"] // cfg["page_tiles"]
    gkey = cfg["geometry"]
    if gkey not in fixed_cache:
        fixed_cache[gkey] = Fixed(act, cg)
    fixed = fixed_cache[gkey]
    split = cfg["split"]
    order_fn = make_order(cfg, F)

    t0 = time.perf_counter()
    if split == "page0shared":
        # the order function needs to know which post-split canonicals are the kept ones
        unique0, canon0, _ = _dedupe(act)
        keep = frozenset(widest_shared_tiles(act, c2, unique0, canon0))
        base_unique = [unique0[k] for k in sorted(keep)]

        def order_wrap(ctx, _inner=order_fn):
            ids = [ctx["unique"].index(b) for b in base_unique]
            ctx["_shared_ids"] = sorted(set(ids))
            return _inner(ctx)
        pipe = run_pipeline_ext(act, c2, order_wrap, split, keep_shared_fn=lambda *a: keep)
    else:
        pipe = run_pipeline_ext(act, c2, order_fn, split)
    t_pipe = time.perf_counter() - t0
    cols, rows = cg["TILE_CACHE_COLS"], cg["TILE_CACHE_ROWS"]
    pg = pipe["page_grid"]
    dup = None
    if cfg.get("spare"):
        t1 = time.perf_counter()
        pg, glob2, fill, dup = dup_fixup(pg, pipe["glob_grid"], pipe["page_sizes"], cfg["page_tiles"], F,
                                         fixed.lefts, fixed.tops, cols, rows)
        dup["seconds"] = round(time.perf_counter() - t1, 3)
        inc_needed = dup.pop("_needed")
        pipe["glob_grid"] = glob2
        pipe["page_sizes"] = fill
        pipe["pool_tiles"] = sum(fill)
    allp = set(range(pipe["pages"]))
    rule = set(pipe["pinned"])
    sums = mpo.page_presence_sums(pg, fixed.lefts, fixed.tops, cols, rows,
                                  {"unpinned": allp - rule, "pinned_nonzero": rule - {0}})
    needed_rule = sums["unpinned"] + len(rule)
    needed_pin0 = sums["unpinned"] + sums["pinned_nonzero"] + 1
    if dup is not None:
        # CONTROL: the fixup's incremental counts must equal a from-scratch re-measure
        diff = int(np.count_nonzero(inc_needed != needed_pin0))
        dup["incremental_vs_remeasure_windows_differing"] = diff
        if diff:
            raise SystemExit(f"{act.name} {cfg['name']}: dup fixup incremental count differs on {diff} windows")
    pins_kept = [0]
    if cfg["pin"] == "rule75":
        needed = needed_rule
        pinned_used = sorted(rule)
    elif cfg["pin"] == "pin0":
        needed = needed_pin0
        pinned_used = [0]
    else:
        needed = needed_pin0.copy()
        for p in sorted(rule - {0}):
            pres = page_presence(pg, fixed.lefts, fixed.tops, cols, rows, p)
            bump = needed + (~pres).astype(np.int16)
            if np.count_nonzero((needed <= F) & (bump > F)) == 0:
                needed = bump
                pins_kept.append(p)
        pinned_used = pins_kept
    res = {"config": cfg["name"], "frames": F, "frames_at_768": F_ship, "geometry": geo,
           "pool_tiles": pipe["pool_tiles"], "pages": pipe["pages"], "rule75_pinned": sorted(rule),
           "pinned_used": pinned_used, "page_sizes_min": min(pipe["page_sizes"]),
           "pages_short": sum(1 for s in pipe["page_sizes"][:-1] if s < cfg["page_tiles"]),
           "sections": pipe["sections"], "exceeds_PAGE_TABLE_MAX": pipe["pages"] > c["PAGE_TABLE_MAX"],
           "local_palette_max": pipe["local_palette_max"], "local_palette_refusals": pipe["local_palette_refusals"],
           "shared_kept": pipe["shared_kept"], "order_seconds": round(pipe["order_seconds"], 3),
           "pipeline_seconds": round(t_pipe, 3), "order_stats": pipe["order_stats"],
           "dup_fixup": dup,
           "needed": {}, "needed_rule75": {}, "needed_pin0": {}, "needed_reachable": {}}
    for cname, m in fixed.classes().items():
        if m is not None and not m.any():
            continue
        res["needed"][cname] = mb.summarise(needed, [F, F_ship], m)
        res["needed_rule75"][cname] = mb.summarise(needed_rule, [F, F_ship], m)
        res["needed_pin0"][cname] = mb.summarise(needed_pin0, [F, F_ship], m)
        rm = fixed.reach if m is None else (fixed.reach & m)
        res["needed_reachable"][cname] = mb.summarise(needed, [F], rm)
    tiles = mb.distinct_tiles_per_window(pipe["glob_grid"], fixed.lefts, fixed.tops, cols, rows)
    floor = -(-tiles // cfg["page_tiles"])
    res["any_order_floor_max"] = int(floor.max()) if floor.size else 0
    res["any_order_floor_over_F"] = int(np.count_nonzero(floor > F))
    if bursts:
        res["entering"] = entering_pages(pg, fixed.lefts, fixed.tops, cols, rows, pipe["pages"])
    res["_arrays"] = (pg, needed, pipe)
    return res


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def control_ext(c, log=print):
    """run_pipeline_ext == run_pipeline (split none/zone), refine_pages == refine_order,
    rzs12 == megaact_page_order's refined_zonesplit pool order, and the geometry model
    reproduces the shipped window. Acts: LRZ1|CNZ1 (S3K) and OJZ act 1."""
    problems = []
    st = c["SECTION_SIZE"] >> 3
    acts = [mb.pair_act("LRZ1", "CNZ1", st), mpo.ojz_act(c)]
    compared = 0
    for act in acts:
        for split, zs in (("none", False), ("zone", True)):
            for name, fn in (("shipped", None), ("hilbert_first", mpo.order_hilbert_first)):
                ref = mb.run_pipeline(act, c, order_fn=fn, zone_split_dedupe=zs)
                mine = run_pipeline_ext(act, c, fn, split)
                compared += 1
                if not np.array_equal(ref["page_grid"], mine["page_grid"]):
                    problems.append(f"{act.name} {split} {name}: page grid differs")
                if ref["pinned"] != mine["pinned"] or ref["pool_order"] != mine["pool_order"]:
                    problems.append(f"{act.name} {split} {name}: pins or pool order differ")
                if ref["local_palette_max"] != mine["local_palette_max"]:
                    problems.append(f"{act.name} {split} {name}: local palette max differs")
        # refine_pages vs refine_order, and the whole rzs12 order vs refined_zonesplit
        ref = mb.run_pipeline(act, c, order_fn=mpo.order_refined, zone_split_dedupe=True)
        mine = run_pipeline_ext(act, c, make_order(config("g80x60/64/zone/rzs12/rule75"), 12), "zone")
        compared += 1
        if ref["pool_order"] != mine["pool_order"]:
            problems.append(f"{act.name}: rzs12 pool order differs from megaact_page_order refined_zonesplit")
        if ref["pinned"] != mine["pinned"]:
            problems.append(f"{act.name}: rzs12 pins differ")
        # the explicit-page path with contiguous sizes must equal the implicit one
        cfgp = dict(config("g80x60/64/zone/rzsF/pin0"))
        a = run_pipeline_ext(act, c, make_order(cfgp, 12), "zone")
        page = c["ART_POOL_PAGE_TILES"]

        def with_sizes(ctx, _f=make_order(cfgp, 12)):
            o = _f(ctx)
            ctx["stats"]["page_sizes"] = [len(p) for p in _pages_from_order(o, page)]
            return o
        b = run_pipeline_ext(act, c, with_sizes, "zone")
        compared += 1
        if not np.array_equal(a["page_grid"], b["page_grid"]) or a["pinned"] != b["pinned"]:
            problems.append(f"{act.name}: explicit contiguous page sizes differ from the implicit split")
    # geometry: g80x60 window == megaact_window_pageset's shipped window at many cameras
    cg, geo = geometry_constants(c, "g80x60")
    for x in list(range(0, 400, 3)) + [4096 + 5, 8191]:
        if mb.window_for_camera(cg, x, x) != mb.window_for_camera(c, x, x):
            problems.append(f"g80x60 window differs at cam {x}")
    # POISON: the geometry check must refuse a window that misses the plane at odd rows
    poisoned = False
    # (2/2 margins, 44x32: passes the engine's two ensures and binds, but at an odd
    # camera row the even-rounded top leaves the held bottom one row short of the fill)
    GEOMETRIES["_poison"] = (2, 2, 44, 32)
    why = ""
    try:
        geometry_constants(c, "_poison")
    except SystemExit as e:
        why = str(e)
        poisoned = "rows miss the plane fill" in why and "engine ensure" not in why and "bind" not in why
    finally:
        del GEOMETRIES["_poison"]
    if not poisoned:
        problems.append(f"geometry check did not refuse 44x32 for the odd-row reason alone: {why!r}")
    log(f"  control_ext: {compared} comparisons, problems={problems[:4]}")
    return {"comparisons": compared, "shipped_geometry": geo, "poison_44x32_refused": poisoned,
            "problems": problems, "ok": not problems}


def rederive_vs_09(acts_out, game):
    """This tool's shipped + rzs12 numbers against report 09's committed per-act values."""
    ref = json.load(open(P09_JSON[game]))
    by = {(a["group"], a["act"]): a for a in ref["acts"]}
    mism, n_vals, n_acts = [], 0, 0
    pairs = (("g80x60/64/none/shipped/rule75", "shipped"), ("g80x60/64/zone/rzs12/rule75", "refined_zonesplit"))
    for a in acts_out:
        r = by.get((a["group"], a["act"]))
        if r is None:
            mism.append(f"{a['act']}: not in report 09")
            continue
        n_acts += 1
        for mine_name, theirs in pairs:
            m, t = a["configs"][mine_name], r["candidates"][theirs]
            for k in ("pool_tiles", "pages"):
                n_vals += 1
                if m[k] != t[k]:
                    mism.append(f"{a['act']} {theirs}: {k} {m[k]} != {t[k]}")
            n_vals += 1
            if m["rule75_pinned"] != t["pinned_pages"]:
                mism.append(f"{a['act']} {theirs}: pinned {m['rule75_pinned']} != {t['pinned_pages']}")
            for field, tfield in (("needed_rule75", "needed"), ("needed_pin0", "needed_pin0")):
                for cls, tv in t[tfield].items():
                    mv = m[field].get(cls, {})
                    for k in ("positions", "max", "p50", "p99", "over_12", "over_10"):
                        n_vals += 1
                        if mv.get(k) != tv.get(k):
                            mism.append(f"{a['act']} {theirs} {tfield}.{cls}.{k}: {mv.get(k)} != {tv.get(k)}")
    return {"acts_compared": n_acts, "acts_in_09": len(ref["acts"]), "values_compared": n_vals,
            "mismatches": mism, "ok": not mism and n_acts == len(ref["acts"])}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

_W = {}


def _work(args):
    spec, group, cfgs, bursts = args
    c = _W.get("c")
    if c is None:
        c, _ = mb.load_constants()
        _W["c"] = c
    t0 = time.perf_counter()
    act = mpo.build_act(spec, c)
    fixed_cache = {}
    out = {"act": act.name, "group": group, "sections": act.grid_w * act.grid_h, "configs": {}}
    for name in cfgs:
        r = measure(act, c, config(name), fixed_cache, None, bursts)
        r.pop("_arrays")
        # evidence size: histograms are kept for the headline count only
        for field in ("needed_rule75", "needed_pin0", "needed_reachable"):
            for v in r[field].values():
                v.pop("histogram", None)
        out["configs"][name] = r
    out["elapsed_s"] = round(time.perf_counter() - t0, 2)
    return out


def specs_for(game, c, only=None, acts=None):
    if game == "ojz":
        specs = [("ojz", ("ojz",))]
    else:
        specs, _ = mpo.populations(game, c)
    if only:
        specs = [(g, s) for g, s in specs if g in only]
    return specs


def run(game, cfgs, jobs, log, only=None, act_names=None, bursts=False):
    c, _ = mb.load_constants()
    specs = specs_for(game, c, only)
    work = [(s, g, cfgs, bursts) for g, s in specs]
    work.sort(key=lambda w: 0 if w[1] == "chain" else (1 if w[1] == "junction" else 2))
    out = []
    t0 = time.time()

    def keep(r):
        return act_names is None or r["act"] in act_names

    if act_names is not None:
        # names are only known after building; filter cheaply by the spec label
        def label(spec):
            k = spec[0]
            if k == "single":
                return spec[1]
            if k == "pair":
                return spec[1]
            if k == "offset":
                return f"{spec[1]} dy={spec[2]}"
            if k == "junction":
                return spec[5]
            if k == "chain":
                return "chain " + "|".join(spec[1])
            return "OJZ act 1"
        work = [w for w in work if label(w[0]) in act_names]
    if jobs > 1:
        with mp.get_context("fork").Pool(jobs) as pool:
            for i, r in enumerate(pool.imap_unordered(_work, work)):
                out.append(r)
                log(f"  [{i + 1}/{len(work)}] {r['group']:8} {r['act']} {r['elapsed_s']}s " + " ".join(
                    f"{n.split('/')[0]}/{n.split('/')[1]}/{n.split('/')[2][:2]}/{n.split('/')[3]}/{n.split('/')[4][:2]}"
                    f"={v['needed']['all']['max']}:{v['needed']['all']['over_' + str(v['frames'])]}"
                    for n, v in r["configs"].items()))
    else:
        for i, w in enumerate(work):
            r = _work(w)
            out.append(r)
            log(f"  [{i + 1}/{len(work)}] {r['group']:8} {r['act']} {r['elapsed_s']}s " + " ".join(
                f"{n}={v['needed']['all']['max']}:{v['needed']['all']['over_' + str(v['frames'])]}"
                for n, v in r["configs"].items()))
    out = [r for r in out if keep(r)]
    return c, sorted(out, key=lambda r: (r["group"], r["act"])), round(time.time() - t0, 1)


SUBJECT = {"single": ["all"], "pair": ["seam_two_plus_zones", "interior_one_zone"],
           "offset": ["seam_two_plus_zones"], "junction": ["junction_three_plus_zones"],
           "chain": ["all", "interior_one_zone", "seam_two_plus_zones"], "ojz": ["all"]}


def summarise(acts, cfgs):
    out = {}
    for group in sorted({a["group"] for a in acts}):
        for cls in SUBJECT[group]:
            for name in cfgs:
                row = {"acts": 0, "windows": 0, "worst": 0, "windows_over_F": 0, "acts_over_F": 0,
                       "reachable_windows_over_F": 0, "rule75_windows_over_F": 0, "pin0_windows_over_F": 0,
                       "frames": None, "pinned_used_max": 0, "floor_max": 0, "floor_windows_over_F": 0,
                       "pool_tiles_max": 0, "pages_max": 0, "order_seconds_max": 0.0,
                       "try_cap_hits": 0, "entering_max": {}}
                for a in acts:
                    if a["group"] != group:
                        continue
                    r = a["configs"][name]
                    n = r["needed"].get(cls)
                    if not n or not n.get("positions"):
                        continue
                    F = r["frames"]
                    row["frames"] = F
                    row["acts"] += 1
                    row["windows"] += n["positions"]
                    row["worst"] = max(row["worst"], n["max"])
                    row["windows_over_F"] += n[f"over_{F}"]
                    row["acts_over_F"] += 1 if n[f"over_{F}"] else 0
                    row["reachable_windows_over_F"] += r["needed_reachable"][cls].get(f"over_{F}", 0)
                    row["rule75_windows_over_F"] += r["needed_rule75"][cls][f"over_{F}"]
                    row["pin0_windows_over_F"] += r["needed_pin0"][cls][f"over_{F}"]
                    row["pinned_used_max"] = max(row["pinned_used_max"], len(r["pinned_used"]))
                    row["floor_max"] = max(row["floor_max"], r["any_order_floor_max"])
                    row["floor_windows_over_F"] += r["any_order_floor_over_F"] if cls == "all" else 0
                    row["pool_tiles_max"] = max(row["pool_tiles_max"], r["pool_tiles"])
                    row["pages_max"] = max(row["pages_max"], r["pages"])
                    row["order_seconds_max"] = max(row["order_seconds_max"], r["order_seconds"])
                    row["try_cap_hits"] += sum(1 for x in r["order_stats"].get("refine_rounds", []) if x["try_cap_hit"])
                    for d, e in r.get("entering", {}).items():
                        row["entering_max"][d] = max(row["entering_max"].get(d, 0), e["max"])
                out[f"{group}/{cls}/{name}"] = row
    return out


# ---------------------------------------------------------------------------
# ROM (page payload bytes under salvador, regenerate-level.sh's ZX0/raw election)
# ---------------------------------------------------------------------------

def rom_bytes(act, c, cfg, sal):
    cg, _ = geometry_constants(c, cfg["geometry"])
    c2 = page_constants(cg, cfg["page_tiles"])
    F = lever_pool_tiles(c) // cfg["page_tiles"]
    if cfg["split"] == "page0shared":
        unique0, canon0, _ = _dedupe(act)
        keep = frozenset(widest_shared_tiles(act, c2, unique0, canon0))
        base_unique = [unique0[k] for k in sorted(keep)]
        inner = make_order(cfg, F)

        def order_wrap(ctx):
            ctx["_shared_ids"] = sorted({ctx["unique"].index(b) for b in base_unique})
            return inner(ctx)
        pipe = run_pipeline_ext(act, c2, order_wrap, "page0shared", keep_shared_fn=lambda *a: keep)
    else:
        pipe = run_pipeline_ext(act, c2, make_order(cfg, F), cfg["split"])
    order, unique = pipe["pool_order"], pipe["unique"]
    sizes, o, total, forms = pipe["page_sizes"], 0, 0, {"zx0": 0, "raw": 0}
    with tempfile.TemporaryDirectory() as td:
        for k, s in enumerate(sizes):
            payload = b"".join(unique[t] for t in order[o:o + s])
            o += s
            src, dst = os.path.join(td, f"p{k}.bin"), os.path.join(td, f"p{k}.zx0")
            with open(src, "wb") as fh:
                fh.write(payload)
            subprocess.run([sal, src, dst], check=True, stdout=subprocess.DEVNULL)
            z = os.path.getsize(dst) + 4
            if z * 10 <= len(payload) * 9:
                total += z + (z & 1)
                forms["zx0"] += 1
            else:
                total += len(payload)
                forms["raw"] += 1
    # manifest: one PageManifest (8 B, engine/structs.emp) per page
    return {"config": cfg["name"], "pages": len(sizes), "pool_tiles": pipe["pool_tiles"],
            "page_bytes": total, "manifest_bytes": 8 * len(sizes), "forms": forms}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

USAGE = """Usage:
    python3 tools/megaact_fg_cache10.py control
    python3 tools/megaact_fg_cache10.py rederive --game {s2,s3k,ojz} [--jobs N] [--json PATH]
    python3 tools/megaact_fg_cache10.py sweep --game {s2,s3k,ojz} --configs a,b [--jobs N] [--only groups] [--acts names] [--bursts] [--json PATH]
    python3 tools/megaact_fg_cache10.py rom --game {s2,s3k,ojz} --configs a,b [--only groups] [--json PATH]
    python3 tools/megaact_fg_cache10.py configs"""

REDERIVE_CFGS = ["g80x60/64/none/shipped/rule75", "g80x60/64/zone/rzs12/rule75"]


def _log(m):
    print(m, flush=True)


def _write(path, rep):
    if path:
        with open(path, "w") as fh:
            json.dump(rep, fh, separators=(",", ":"))
            fh.write("\n")


def _mode_control(rest):
    if rest:
        print(f"ERROR: unknown argument {rest[0]!r}")
        print(USAGE)
        sys.exit(1)
    c, _ = mb.load_constants()
    ojz = mb.control_ojz(c)
    pres = mpo.control_presence(c)
    ext = control_ext(c, _log)
    out = {"control_ojz_ok": ojz["ok"], "control_presence_ok": pres["ok"], "control_ext": ext,
           "ok": ojz["ok"] and pres["ok"] and ext["ok"]}
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


def _controls_or_refuse(c, rep):
    ojz = mb.control_ojz(c)
    rep["control_ojz"] = {k: ojz[k] for k in ("ok", "problems", "cells_compared", "cells_differing", "pinned")}
    ext = control_ext(c, _log)
    rep["control_ext"] = ext
    if not ojz["ok"] or not ext["ok"]:
        rep["refused"] = "a control failed"
        return False
    return True


def _mode_rederive(rest):
    ap = argparse.ArgumentParser(prog="megaact_fg_cache10.py rederive")
    ap.add_argument("--game", choices=["s2", "s3k", "ojz"], required=True)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args(rest)
    c, _ = mb.load_constants()
    rep = {"tool": "tools/megaact_fg_cache10.py", "mode": "rederive", "game": args.game, "configs": REDERIVE_CFGS}
    if _controls_or_refuse(c, rep):
        _, acts, wall = run(args.game, REDERIVE_CFGS, args.jobs, _log)
        rep["wall_seconds"] = wall
        rep["rederive_vs_09"] = rederive_vs_09(acts, args.game)
        rv = rep["rederive_vs_09"]
        _log(f"rederive vs 09: {rv['acts_compared']}/{rv['acts_in_09']} acts, {rv['values_compared']} values, "
             f"{len(rv['mismatches'])} mismatches {rv['mismatches'][:5]}")
        rep["summary"] = summarise(acts, REDERIVE_CFGS)
        if not rv["ok"]:
            rep["refused"] = "this tool does not re-derive report 09"
    _write(args.json, rep)
    if "refused" in rep:
        print("REFUSED:", rep["refused"])
        return 2
    print("finished=ok")
    return 0


def _mode_sweep(rest):
    ap = argparse.ArgumentParser(prog="megaact_fg_cache10.py sweep")
    ap.add_argument("--game", choices=["s2", "s3k", "ojz"], required=True)
    ap.add_argument("--configs", required=True)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--only", default=None)
    ap.add_argument("--acts", default=None, help="semicolon-separated act labels")
    ap.add_argument("--bursts", action="store_true")
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args(rest)
    cfgs = args.configs.split(",")
    for n in cfgs:
        config(n)
    c, _ = mb.load_constants()
    rep = {"tool": "tools/megaact_fg_cache10.py", "mode": "sweep", "game": args.game, "configs": cfgs,
           "only": args.only, "acts_filter": args.acts, "bursts": args.bursts}
    if _controls_or_refuse(c, rep):
        only = args.only.split(",") if args.only else None
        names = set(args.acts.split(";")) if args.acts else None
        _, acts, wall = run(args.game, cfgs, args.jobs, _log, only=only, act_names=names, bursts=args.bursts)
        rep["wall_seconds"] = wall
        rep["population_counts_measured"] = {g: sum(1 for a in acts if a["group"] == g)
                                             for g in sorted({a["group"] for a in acts})}
        rep["summary"] = summarise(acts, cfgs)
        rep["acts"] = acts
        if names is not None and len(acts) != len(names):
            rep["refused"] = f"--acts named {len(names)} acts, measured {len(acts)}"
    _write(args.json, rep)
    if "refused" in rep:
        print("REFUSED:", rep["refused"])
        return 2
    print("finished=ok")
    return 0


def _mode_rom(rest):
    ap = argparse.ArgumentParser(prog="megaact_fg_cache10.py rom")
    ap.add_argument("--game", choices=["s2", "s3k", "ojz"], required=True)
    ap.add_argument("--configs", required=True)
    ap.add_argument("--only", default="chain")
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args(rest)
    cfgs = [config(n) for n in args.configs.split(",")]
    sal = mpo._salvador()
    if sal is None:
        print(f"COULD NOT RUN: no salvador ({mpo.SALVADOR_ENV} or tools/bin/salvador)")
        return 2
    c, _ = mb.load_constants()
    specs = specs_for(args.game, c, args.only.split(","))
    rep = {"tool": "tools/megaact_fg_cache10.py", "mode": "rom", "game": args.game, "salvador": sal, "acts": []}
    for g, spec in specs:
        act = mpo.build_act(spec, c)
        row = {"act": act.name, "group": g, "configs": {}}
        for cfg in cfgs:
            row["configs"][cfg["name"]] = rom_bytes(act, c, cfg, sal)
            _log(f"  {act.name} {cfg['name']}: {row['configs'][cfg['name']]}")
        rep["acts"].append(row)
    _write(args.json, rep)
    print("finished=ok")
    return 0


def _mode_configs(rest):
    if rest:
        print(f"ERROR: unknown argument {rest[0]!r}")
        print(USAGE)
        sys.exit(1)
    c, _ = mb.load_constants()
    for g in GEOMETRIES:
        try:
            print(json.dumps(geometry_constants(c, g)[1]))
        except SystemExit as e:
            print(g, "REFUSED", e)
    return 0


# ONE list of legal modes, and it is the dispatch table (LS-15d shape,
# tools/test_cli_dispatch_refuses.py). An unknown or missing mode prints usage and
# exits 1 BEFORE any handler; nothing is a default.
MODES = {
    "control": _mode_control,
    "rederive": _mode_rederive,
    "sweep": _mode_sweep,
    "rom": _mode_rom,
    "configs": _mode_configs,
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
