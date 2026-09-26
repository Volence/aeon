#!/usr/bin/env python3
"""s2_clip_budget.py — THROWAWAY measurement for the S2-COMPRESSED-ACT design
(docs/research/2026-09-17-s2-compressed-act-design.md).

WHAT THIS IS. A measurement over DONOR DATA pushed through aeon's build-time
page pipeline. It is NOT an observation of the running engine and it bakes
nothing. It exists to put real numbers under the design's budget table instead
of estimates.

It reuses, unmodified and by import:
  tools/s2_donor.py                 THE Sonic 2 donor loader — both donor trees,
                                    nine final-game zones (WFZ included) and the
                                    Simon Wai prototype's ten
  tools/megaact_window_pageset.py   Act placement, run_pipeline (the REAL
                                    dedupe/order/page/pin functions), measure_act
  tools/tile_dedupe.py              canonical-form dedupe, spatial order, paging
  tools/collision_pipeline.py       bake_cell — the REAL donor-word -> attr bake

WHAT CHANGED 2026-09-17 (S2-COMPRESSED-ACT parcel 1). This file used to carry a
monkey patch that bolted a WFZ row onto `megaact_window_pageset.S2_ZONES` and
wrapped its `_load_s2`. Both are gone: WFZ is a registry row in `s2_donor` and
the loader is imported. Two behaviours are worth naming because they are the
only places a number can move:

  * `--profiles` now DEFAULTS TO `vertical`, and that changes three published
    figures. `bake_cell`'s `profiles` argument is the per-column HEIGHT array —
    `collision_pipeline.load_donor_collision` feeds it sonic_hack's `Collision
    array 1.bin`, which is byte-identical to s2disasm's `Collision array -
    Vertical.bin` (MEASURED). This file used to hand it `Collision array -
    Horizontal.bin`, the ROTATED array, so it interned width profiles as
    heights. The design's §3.5 counts were measured that way. Corrected they are
    299 / 130 / 276 instead of 301 / 131 / 278 — no conclusion in §3.5 moves
    (still over by 44, still fits, still over by 21). `--profiles horizontal`
    reproduces the published numbers exactly and is how the promotion was proven
    faithful.
  * There is no other change. The zone grids, the art blobs and every `place`,
    `window`, `act`, `zones`, `clipsweep` and `pallines` figure are byte-for-byte
    what the pre-promotion tool produced.

WHAT CHANGED 2026-09-17 AGAIN (S2-COMPRESSED-ACT parcel 3). `mode_place` handed
`place_pool` the raw `ojz_strip_gen.mark_pinned_pages`, which returns a
list[bool]; `place_pool` wants PAGE INDICES and `generate()` wraps it. See
`pin_rule_fn` below for the full statement and the measurement. The §3.3 table in
the design doc is UNAFFECTED (no page on those acts reaches the pin rule's 75%
threshold, so the candidate set is empty either way — re-measured both ways);
small acts move, and `--pins raw` reproduces the old behaviour.

The ONLY things this file still owns are:
  * Clip(): crop a loaded Zone to a sub-rectangle, which is exactly the
    "marquee a rectangle" operation the owner asked for
  * the reports below

Modes:
  zones           per-zone facts (box, painted extent, sections, tiles, pages)
  clipsweep       every section-aligned NxM-section clip of a zone, tile+page cost
  act             assemble a named clip act and run the real page pipeline
  place           the REAL Pass 4 placement (fg_page_order.place_pool) + its refusal
  window          `act` plus the full camera-window page-set sweep
  collision       attr-set entries a set of zones/clips needs (cap 255)
  collsweep       per-zone attr-set cost of every section-aligned clip
  pallines        which CRAM palette lines each zone's foreground uses

Every mode takes `--donor` (default `s2disasm`, the final game); pass
`--donor s2-simonwai-disasm` to measure the prototype, which is the only tree
carrying Hidden Palace Zone.

Usage: python3 docs/research/s2-compressed-act/s2_clip_budget.py <mode> [args]
"""
import argparse, json, os, sys, time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))

import megaact_window_pageset as mb          # noqa: E402
import s2_donor                              # noqa: E402
import ojz_strip_gen                         # noqa: E402
import tile_dedupe                           # noqa: E402

DONORS = s2_donor.DONORS
S2FINAL_TAG = s2_donor.S2_FINAL


def load_zone(name, donor):
    return s2_donor.load_zone(name, donor)


def clip(zone, col0, row0, cols, rows, name=None):
    """Crop a Zone to [col0:col0+cols, row0:row0+rows] in 8px tiles."""
    w = zone.words[row0:row0 + rows, col0:col0 + cols].copy()
    box = dict(zone.box)
    box["clip_tiles"] = [col0, row0, cols, rows]
    z = s2_donor.Zone(name or f"{zone.name}@{col0},{row0}", w,
                      np.zeros(w.shape, dtype=bool), box, zone.art, zone.n_art_tiles)
    return z


painted_bbox = s2_donor.painted_bbox


def tiles_and_pages(zone, c):
    """Distinct canonical tiles referenced by this zone's words, and the page
    floor at ART_POOL_PAGE_TILES. Uses the REAL canonical_form dedupe."""
    src = np.unique(zone.words & 0x7FF)
    raw = [zone.art[i * 32:(i + 1) * 32] for i in src.tolist()]
    unique, _ = tile_dedupe.dedupe_tiles(raw)
    n = len(unique)
    return int(len(src)), n, -(-n // c["ART_POOL_PAGE_TILES"])


def mode_zones(args):
    c, origin = mb.load_constants()
    st = c["SECTION_SIZE"] >> 3
    print(f"# SECTION_SIZE={c['SECTION_SIZE']} px ({st} tiles) "
          f"MAX_ACT_SECTIONS={c['MAX_ACT_SECTIONS']} "
          f"ART_POOL_PAGE_TILES={c['ART_POOL_PAGE_TILES']} "
          f"PAGE_FRAMES={c['PAGE_FRAMES']} POOL_TILE_CEILING={c['POOL_TILE_CEILING']}")
    rows = []
    for name in args.zones or s2_donor.zone_names(args.donor):
        z = load_zone(name, args.donor)
        h, w = z.words.shape
        pb = painted_bbox(z)
        src, canon, pages = tiles_and_pages(z, c)
        secs_w, secs_h = -(-w // st), -(-h // st)
        r = {"zone": name, "art_tiles_in_blob": z.n_art_tiles,
             "level_size_px": z.box["level_size_px"],
             "box_tiles": [w, h], "box_px": [w * 8, h * 8],
             "painted_bbox_tiles": pb,
             "painted_px": [(pb[1] - pb[0]) * 8, (pb[3] - pb[2]) * 8] if pb else None,
             "sections_box": [secs_w, secs_h, secs_w * secs_h],
             "src_tiles": src, "canonical_tiles": canon, "page_floor": pages}
        rows.append(r)
        print(json.dumps(r))
    tot_secs = sum(r["sections_box"][2] for r in rows)
    tot_canon = sum(r["canonical_tiles"] for r in rows)
    print(f"# donor {args.donor}")
    print(f"# TOTALS over {len(rows)} zones: sections_if_whole={tot_secs} "
          f"(MAX_ACT_SECTIONS={c['MAX_ACT_SECTIONS']}), "
          f"sum_of_per_zone_canonical_tiles={tot_canon} "
          f"(NOT the act pool: cross-zone dedupe not applied here)")
    if args.json:
        json.dump({"constants": {n: {"value": c[n], "source": origin[n]} for n in mb.NEEDED},
                   "zones": rows}, open(args.json, "w"), indent=1)


def mode_clipsweep(args):
    c, _ = mb.load_constants()
    st = c["SECTION_SIZE"] >> 3
    z = load_zone(args.zone, args.donor)
    h, w = z.words.shape
    cw, ch = args.secw * st, args.sech * st
    out = []
    for r0 in range(0, max(1, h - ch + 1), st):
        for c0 in range(0, max(1, w - cw + 1), st):
            cl = clip(z, c0, r0, cw, ch)
            src, canon, pages = tiles_and_pages(cl, c)
            nonblank = int(np.count_nonzero((cl.words & 0x7FF) != 0))
            out.append({"col0": c0, "row0": r0, "px": [c0 * 8, r0 * 8],
                        "src": src, "canonical": canon, "pages": pages,
                        "fill_pct": round(100.0 * nonblank / cl.words.size, 1)})
    vals = [o["canonical"] for o in out]
    pg = [o["pages"] for o in out]
    print(f"# {args.zone}: {len(out)} section-aligned {args.secw}x{args.sech}-section clips "
          f"({cw*8}x{ch*8} px) over a {w}x{h}-tile box")
    print(f"# canonical tiles per clip: min={min(vals)} p50={int(np.percentile(vals,50))} "
          f"max={max(vals)} | pages: min={min(pg)} p50={int(np.percentile(pg,50))} max={max(pg)}")
    for o in sorted(out, key=lambda o: -o["canonical"])[:args.top]:
        print(json.dumps(o))
    if args.json:
        json.dump({"zone": args.zone, "clip_sections": [args.secw, args.sech],
                   "clips": out}, open(args.json, "w"), indent=1)


def split_donor(spec, default):
    """`[<donor>@]REST` -> (donor, REST).

    The showcase act the owner named is FIVE final-game zones plus Hidden Palace,
    and Hidden Palace exists only in the prototype tree — so an act spec has to be
    able to name a donor per clip, not per invocation. `--donor` remains the
    default for every spec that does not carry a prefix.
    """
    if "@" in spec:
        dn, _, rest = spec.partition("@")
        if dn not in DONORS:
            raise SystemExit(f"{spec}: unknown donor {dn!r} (one of {', '.join(DONORS)})")
        return dn, rest
    return default, spec


def parse_spec(spec, st, donor):
    """[<donor>@]ZONE:col0,row0,secw,sech  (col0/row0 in SECTIONS from the box origin)"""
    dn, spec = split_donor(spec, donor)
    zn, rest = spec.split(":")
    c0, r0, sw, sh = (int(x) for x in rest.split(","))
    z = load_zone(zn, dn)
    tag = zn if dn == S2FINAL_TAG else f"{zn}~proto"
    return clip(z, c0 * st, r0 * st, sw * st, sh * st, name=f"{tag}#{c0},{r0}")


def build_act(specs, st, rowlen, donor, align=True):
    """Lay the clips out left to right in section rows of `rowlen` sections.

    align=True starts every clip on a SECTION boundary — the design's premise
    (a clip that straddles a section boundary puts two zones' tiles in one
    section's 11-bit local palette). align=False packs them tight, which is
    what megaact's chain_act does, and is kept as the control.
    """
    clips = [parse_spec(s, st, donor) for s in specs]
    placements, col, row = [], 0, 0
    for cl in clips:
        wsec = -(-cl.words.shape[1] // st)
        if align and col and (col // st) + wsec > rowlen:
            col = 0
            row += max(-(-p[0].words.shape[0] // st) for p in placements)
        placements.append((cl, col, row * st))
        col += wsec * st if align else cl.words.shape[1]
    return mb.Act("clipact " + " ".join(specs), placements, st)


def mode_act(args):
    c, _ = mb.load_constants()
    st = c["SECTION_SIZE"] >> 3
    act = build_act(args.spec, st, args.rowlen, args.donor, align=not args.no_align)
    t0 = time.time()
    pipe = mb.run_pipeline(act, c)
    print(json.dumps({
        "act": act.name,
        "placements": [{"clip": z.name, "col0": c0, "row0": r0,
                        "tiles": list(z.words.shape[::-1])} for z, c0, r0 in act.placements],
        "content_tiles": [act.content_w, act.content_h],
        "grid_sections": pipe["grid"], "sections": pipe["sections"],
        "MAX_ACT_SECTIONS": c["MAX_ACT_SECTIONS"],
        "exceeds_MAX_ACT_SECTIONS": pipe["sections"] > c["MAX_ACT_SECTIONS"],
        "source_tiles_keyed": pipe["source_tiles"],
        "pool_tiles": pipe["pool_tiles"], "pages": pipe["pages"],
        "PAGE_FRAMES": c["PAGE_FRAMES"], "POOL_TILE_CEILING": c["POOL_TILE_CEILING"],
        "pool_fits_fully_resident": pipe["pool_tiles"] <= c["POOL_TILE_CEILING"],
        "pinned_pages": pipe["pinned"],
        "local_palette_max": pipe["local_palette_max"],
        "local_palette_refusals": pipe["local_palette_refusals"],
        "elapsed_s": round(time.time() - t0, 2)}, indent=1))
    if args.json:
        json.dump({k: v for k, v in pipe.items()
                   if k in ("pages", "pool_tiles", "sections", "grid", "pinned",
                            "local_palette_max", "source_tiles")},
                  open(args.json, "w"), indent=1)


# --- collision: how many attr-set entries does a set of zones/clips need? -----
# The donor registry for the collision side is `s2_donor`'s (`coll_p`/`coll_s`,
# cross-read from each donor's own Off_ColP/Off_ColS). It used to be a second
# table here, keyed only to the final game.


class _UncappedAttrSet:
    """collision_pipeline.AttrSet without the 255 refusal, so the REQUIRED size can
    be reported instead of only 'it overflowed'. Same key, same intern order."""

    def __init__(self):
        import collision_pipeline as cp
        self._cp = cp
        self.entries = [(bytes(cp.PROFILE_LEN), 0x00, cp.SOL_NONE)]
        self.lookup = {self.entries[0]: 0}

    def intern(self, heights, angle, solidity):
        k = (heights, angle, solidity)
        i = self.lookup.get(k)
        if i is None:
            i = len(self.entries)
            self.entries.append(k)
            self.lookup[k] = i
        return i


def collision_entries(specs, donor, profiles="vertical"):
    """specs: ["EHZ", ...] or ["EHZ:0,2", ...] meaning zone:first_section,n_sections.
    Returns the attr-set size the whole set needs, through the REAL bake_cell.

    A spec may carry a `<donor>@` prefix; `donor` is the default for those that do
    not. The shape bank comes from `donor` regardless, which is sound only because
    the two donors' banks are byte-identical — `tools/test_s2_donor.py::
    test_the_two_donors_share_one_collision_shape_vocabulary` is what keeps that so.

    `profiles` names WHICH shape bank feeds bake_cell's `profiles` argument.
    "vertical" is the per-column HEIGHT array and the correct one — it is what
    `collision_pipeline.load_donor_collision` reads for the shipping bake.
    "horizontal" is the rotated array and reproduces the design's published
    §3.5 figures, which were measured against it by mistake.
    """
    import collision_pipeline as cp
    prof, ang = s2_donor.collision_arrays(donor, profiles)
    a = _UncappedAttrSet()
    for sp in specs:
        dn, sp = split_donor(sp, donor)
        zn, _, rest = sp.partition(":")
        chunks, grid, P, S = s2_donor.collision_inputs(zn, dn)
        if rest:
            s0, ns = (int(x) for x in rest.split(","))
            grid = grid[:, s0 * 16:(s0 + ns) * 16]     # 16 chunks of 128 px == one 2048 px section
        for ci in sorted(set(np.unique(grid).tolist())):
            if ci < len(chunks):
                for w in chunks[ci]:
                    cp.bake_cell(w, P, S, prof, ang, a)
    return len(a.entries) - 1


def mode_collision(args):
    n = collision_entries(args.spec, args.donor, args.profiles)
    cap = 255
    print(f"{' '.join(args.spec)}: {n} attr-set entries needed "
          f"(cap {cap}, tools/collision_pipeline.py AttrSet.intern) -> "
          f"{'FITS' if n <= cap else 'OVERFLOWS by %d' % (n - cap)}")
    return 0 if n <= cap else 1


def mode_collsweep(args):
    """Per-zone: the attr-set cost of every section-aligned clip of `--secw` sections."""
    for zn in args.zones or s2_donor.zone_names(args.donor):
        _chunks, grid, _P, _S = s2_donor.collision_inputs(zn, args.donor)
        nsec = grid.shape[1] // 16
        vals = []
        for s0 in range(0, max(1, nsec - args.secw + 1)):
            v = collision_entries([f"{zn}:{s0},{args.secw}"], args.donor, args.profiles)
            if v:
                vals.append((s0, v))
        if not vals:
            continue
        v = [x[1] for x in vals]
        print(f"{zn}: {len(vals)} clips of {args.secw} section(s) -> attr entries "
              f"min={min(v)} p50={int(np.percentile(v, 50))} max={max(v)}   "
              f"(whole zone {collision_entries([zn], args.donor, args.profiles)})")


def mode_pallines(args):
    """Which CRAM palette lines does each zone's FOREGROUND actually use?
    Aeon writes lines 1..3 only (engine/effects/palette.emp:48-50)."""
    for zn in args.zones or s2_donor.zone_names(args.donor):
        z = load_zone(zn, args.donor)
        nz = (z.words & 0x7FF) != 0
        line = (z.words >> 13) & 3
        pri = (z.words >> 15) & 1
        u, ct = np.unique(line[nz], return_counts=True)
        tot = int(ct.sum())
        d = {int(a): f"{100 * b / tot:.1f}%" for a, b in zip(u, ct)}
        print(f"{zn}: FG palette lines {d}  priority-bit on {100 * pri[nz].mean():.1f}% of cells")


def pin_rule_fn(mode):
    """`place_pool`'s `rule_pins_fn`, in the shape it actually wants.

    CORRECTED 2026-09-17 (S2-COMPRESSED-ACT parcel 3). `place_pool` calls
    `rule_pins_fn(pages, sets)` and then does `sorted(set(candidates) - {0})`,
    so it needs PAGE INDICES. `ojz_strip_gen.mark_pinned_pages` returns a
    list[bool] parallel to `pages`, and `generate()` wraps it at its Pass 4 call
    (`tools/ojz_strip_gen.py`, `rule_pins_fn=lambda pages, sets: [i for i, f in
    enumerate(mark_pinned_pages(pages, sets)) if f]`). This file passed the raw
    function, so the candidate set became `{False, True} - {0}` = `{True}` = page
    1: every act with any pinned page pinned page 1 instead, and no act could
    pin any other page. MEASURED effect: on the published §3.3 acts, none — no
    page reaches the 75% threshold there, so the candidate set is empty either
    way and the whole table reproduces unchanged. On a SMALL act it moves the
    answer: `place EHZ:1,0,1,1 CPZ:1,0,1,1` prints pins [0, True] worst 11 with
    `--pins raw` and pins [0, 4] worst 10 with the default.

    `--pins raw` keeps the old behaviour reachable, exactly as `--profiles
    horizontal` keeps the pre-parcel-1 collision figures reachable.
    """
    if mode == "raw":
        return ojz_strip_gen.mark_pinned_pages
    return lambda pages, sets: [
        i for i, f in enumerate(ojz_strip_gen.mark_pinned_pages(pages, sets)) if f]


def mode_place(args):
    """The DECISIVE one: run the REAL Pass 4 placement (fg_page_order.place_pool,
    the function ojz_strip_gen.generate() calls at tools/ojz_strip_gen.py:2177)
    and the REAL refusal on a stitched clip act. The shipped bake accepts the act
    iff verdict.ok."""
    import fg_page_order as fpo
    c, _ = mb.load_constants()
    st = c["SECTION_SIZE"] >> 3
    act = build_act(args.spec, st, args.rowlen, args.donor, align=not args.no_align)

    # the shared dedupe, exactly as run_pipeline does it
    key = np.where(act.zone_id < 0, 0,
                   (act.zone_id.astype(np.int64) + 1) * 4096 + act.src).astype(np.int64)
    ref = np.unique(key)
    raw = []
    for k in ref.tolist():
        if k == 0:
            raw.append(tile_dedupe.BLANK_TILE)
        else:
            z = act.zones[k // 4096 - 1]
            raw.append(z.art[(k % 4096) * 32:((k % 4096) + 1) * 32])
    unique, mapping = tile_dedupe.dedupe_tiles(raw)
    k2c = np.array([m[0] for m in mapping], dtype=np.int64)
    canon = k2c[np.searchsorted(ref, key)]

    bc = fpo.load_budget_constants()
    t0 = time.time()
    pl = fpo.place_pool(canon, act.zone_id, unique, st, act.grid_w, act.grid_h, bc,
                        pin_rule_fn(args.pins), log=print)
    v = pl["verdict"]
    print(fpo.verdict_line(v, act.name))
    print(json.dumps({
        "act": act.name, "sections": act.grid_w * act.grid_h,
        "grid": [act.grid_w, act.grid_h],
        "MAX_ACT_SECTIONS": c["MAX_ACT_SECTIONS"],
        "rung": pl["rung"], "stats": pl["stats"],
        "pool_tiles_after_placement": len(pl["unique"]),
        "pages": len(pl["pages"]), "PAGE_TABLE_MAX": c["PAGE_TABLE_MAX"],
        "pins": pl["pins"], "rule_pins": pl["rule_pins"],
        "verdict": v, "place_seconds": round(time.time() - t0, 2)}, indent=1))
    if args.json:
        json.dump({"act": act.name, "rung": pl["rung"], "stats": pl["stats"],
                   "pages": len(pl["pages"]), "pool_tiles": len(pl["unique"]),
                   "pins": pl["pins"], "rule_pins": pl["rule_pins"], "verdict": v,
                   "sections": act.grid_w * act.grid_h, "grid": [act.grid_w, act.grid_h]},
                  open(args.json, "w"), indent=1)
    return 0 if v["ok"] else 1


def mode_window(args):
    c, _ = mb.load_constants()
    st = c["SECTION_SIZE"] >> 3
    act = build_act(args.spec, st, args.rowlen, args.donor, align=not args.no_align)
    frames = [c["PAGE_FRAMES"], mb.OWNER_LEVER_FRAMES]
    res = mb.measure_act(act, c, frames)
    print(json.dumps(mb.strip_arrays(res), indent=1))
    if args.json:
        json.dump(mb.strip_arrays(res), open(args.json, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    subparsers = []
    p = sub.add_parser("zones"); p.add_argument("zones", nargs="*"); p.add_argument("--json")
    p.set_defaults(fn=mode_zones); subparsers.append(p)
    p = sub.add_parser("collision"); p.add_argument("spec", nargs="+")
    p.set_defaults(fn=mode_collision); subparsers.append(p)
    p = sub.add_parser("collsweep"); p.add_argument("zones", nargs="*")
    p.add_argument("--secw", type=int, default=2)
    p.set_defaults(fn=mode_collsweep); subparsers.append(p)
    p = sub.add_parser("pallines"); p.add_argument("zones", nargs="*")
    p.set_defaults(fn=mode_pallines); subparsers.append(p)
    p = sub.add_parser("clipsweep"); p.add_argument("zone")
    p.add_argument("--secw", type=int, default=1); p.add_argument("--sech", type=int, default=1)
    p.add_argument("--top", type=int, default=5); p.add_argument("--json")
    p.set_defaults(fn=mode_clipsweep); subparsers.append(p)
    for nm, fn in (("act", mode_act), ("window", mode_window), ("place", mode_place)):
        p = sub.add_parser(nm); p.add_argument("spec", nargs="+")
        p.add_argument("--rowlen", type=int, default=8); p.add_argument("--json")
        p.add_argument("--no-align", action="store_true")
        p.set_defaults(fn=fn); subparsers.append(p)
    for p in subparsers:
        p.add_argument("--pins", default="wrapped", choices=("wrapped", "raw"),
                       help="how mark_pinned_pages is handed to place_pool (place only). "
                            "wrapped is the shape generate() uses and the correct one; "
                            "raw reproduces this file's pre-2026-09-17 behaviour, which "
                            "pinned page 1 for any act with a pinned page")
        p.add_argument("--donor", default=s2_donor.S2_FINAL, choices=DONORS,
                       help="which Sonic 2 donor tree to measure "
                            "(default: the final game)")
        p.add_argument("--profiles", default="vertical", choices=("vertical", "horizontal"),
                       help="which collision shape bank feeds bake_cell's `profiles` "
                            "(collision/collsweep only). vertical is the per-column "
                            "HEIGHT array and the correct one; horizontal reproduces "
                            "the design doc's published §3.5 figures, which were "
                            "measured against the rotated array by mistake")
    a = ap.parse_args()
    # NOT `return a.fn(a)`. `mode_collision` and `mode_place` compute a verdict and
    # return 0/1, and this call has always DISCARDED it, so both modes exit 0 whether
    # they fit or refuse. That is a real defect — a gate that cannot fail — but fixing
    # it here would move an observable (the exit code of every §13 command) inside a
    # refactor whose whole check is that nothing moved. Booked in DEFERRED_WORK under
    # S2-COMPRESSED-ACT instead; read the printed verdict line, not $?.
    a.fn(a)


if __name__ == "__main__":
    main()
