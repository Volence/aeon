#!/usr/bin/env python3
"""s2_clip_budget.py — THROWAWAY measurement for the S2-COMPRESSED-ACT design
(docs/research/2026-09-17-s2-compressed-act-design.md).

WHAT THIS IS. A measurement over DONOR DATA pushed through aeon's build-time
page pipeline. It is NOT an observation of the running engine and it bakes
nothing. It exists to put real numbers under the design's budget table instead
of estimates.

It reuses, unmodified and by import:
  tools/megaact_window_pageset.py   S2 donor loading (Zone/_load_s2/_crop),
                                    Act placement, run_pipeline (the REAL
                                    dedupe/order/page/pin functions), measure_act
  tools/ojz_common.py               Kosinski decode, block/chunk maps
  tools/tile_dedupe.py              canonical-form dedupe, spatial order, paging
The ONLY new things here are:
  * a WFZ donor registry row (megaact's S2_ZONES has 8 zones and no WFZ), built
    the same way HTZ's is: base art WFZ_SCZ.kos with WFZ_Supp.kos overlaid at
    ArtTile_ArtKos_NumTiles_WFZ_Main (s2disasm/s2.asm:6492-6495,
    s2.constants.asm:2305)
  * Clip(): crop a loaded Zone to a sub-rectangle, which is exactly the
    "marquee a rectangle" operation the owner asked for
  * the reports below

Modes:
  zones           per-zone facts (box, painted extent, sections, tiles, pages)
  clipsweep       every section-aligned NxM-section clip of a zone, tile+page cost
  act             assemble a named clip act and run the real page pipeline
  window          `act` plus the full camera-window page-set sweep (slow)

Usage: python3 docs/research/s2-compressed-act/s2_clip_budget.py <mode> [args]
"""
import argparse, json, os, sys, time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))

import megaact_window_pageset as mb          # noqa: E402
import ojz_common                            # noqa: E402
import ojz_strip_gen                         # noqa: E402
import tile_dedupe                           # noqa: E402


# --- WFZ registry row (not in mb.S2_ZONES) ---------------------------------
mb.S2_ZONES["WFZ"] = ("WFZ_SCZ", "WFZ_SCZ", "WFZ_SCZ", "WFZ", "WFZ")
_orig_load_s2 = mb._load_s2


def _load_s2_wfz(name):
    """WFZ = SCZ art with WFZ_Supp overlaid, exactly as s2.asm:6492 does."""
    if name != "WFZ":
        return _orig_load_s2(name)
    root = mb.s2disasm_root()
    s2asm = open(os.path.join(root, "s2.asm"), errors="replace").read()
    s2const = open(os.path.join(root, "s2.constants.asm"), errors="replace").read()
    for spelled in ('"art/kosinski/WFZ_SCZ.kos"', '"art/kosinski/WFZ_Supp.kos"',
                    '"mappings/16x16/WFZ_SCZ.kos"', '"mappings/128x128/WFZ_SCZ.kos"'):
        if spelled not in s2asm:
            raise SystemExit(f"s2.asm no longer BINCLUDEs {spelled}")
    art, _ = ojz_common.kos_decompress(mb._read(os.path.join(root, "art/kosinski/WFZ_SCZ.kos")))
    art = bytearray(art)
    main = mb.parse_s2_constant(s2const, "ArtTile_ArtKos_NumTiles_WFZ_Main")
    supp, _ = ojz_common.kos_decompress(mb._read(os.path.join(root, "art/kosinski/WFZ_Supp.kos")))
    off = main * 32
    if len(art) < off + len(supp):
        art.extend(bytes(off + len(supp) - len(art)))
    art[off:off + len(supp)] = supp
    blocks = ojz_common.load_block_map(os.path.join(root, "mappings/16x16/WFZ_SCZ.kos"))
    chunks = ojz_common.load_chunk_map(os.path.join(root, "mappings/128x128/WFZ_SCZ.kos"))
    layout, _ = ojz_common.kos_decompress(mb._read(os.path.join(root, "level/layout/WFZ.kos")))
    if len(layout) != 0x1000:
        raise SystemExit(f"WFZ layout decoded to {len(layout)} bytes, expected $1000")
    tpc = ojz_strip_gen.TILES_PER_CHUNK_ROW
    lay = np.frombuffer(bytes(layout), dtype=np.uint8).reshape(32, 128)[0::2]
    full = mb._chunk_tiles(chunks, blocks)[lay]
    full = full.transpose(0, 2, 1, 3).reshape(16 * tpc, 128 * tpc)
    xs, xe, ys, ye = mb.parse_level_sizes(s2asm)[("WFZ", 1)]
    return mb._crop("WFZ", full, art, xs, xe, ys, ye, {"game": "Sonic 2", "layout": "WFZ"})


mb._load_s2 = _load_s2_wfz


# --- a clip ----------------------------------------------------------------
def clip(zone, col0, row0, cols, rows, name=None):
    """Crop a Zone to [col0:col0+cols, row0:row0+rows] in 8px tiles."""
    w = zone.words[row0:row0 + rows, col0:col0 + cols].copy()
    box = dict(zone.box)
    box["clip_tiles"] = [col0, row0, cols, rows]
    z = mb.Zone(name or f"{zone.name}@{col0},{row0}", w,
                np.zeros(w.shape, dtype=bool), box, zone.art, zone.n_art_tiles)
    return z


def painted_bbox(zone):
    """Bounding box of cells whose nametable tile field is non-zero."""
    nz = (zone.words & 0x7FF) != 0
    if not nz.any():
        return None
    rows = np.nonzero(nz.any(axis=1))[0]
    cols = np.nonzero(nz.any(axis=0))[0]
    return int(cols[0]), int(cols[-1]) + 1, int(rows[0]), int(rows[-1]) + 1


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
    for name in args.zones or sorted(mb.S2_ZONES):
        z = mb.load_zone(name)
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
    z = mb.load_zone(args.zone)
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


def parse_spec(spec, st):
    """ZONE:col0,row0,secw,sech   (col0/row0 in SECTIONS from the zone box origin)"""
    zn, rest = spec.split(":")
    c0, r0, sw, sh = (int(x) for x in rest.split(","))
    z = mb.load_zone(zn)
    return clip(z, c0 * st, r0 * st, sw * st, sh * st, name=f"{zn}#{c0},{r0}")


def build_act(specs, st, rowlen, align=True):
    """Lay the clips out left to right in section rows of `rowlen` sections.

    align=True starts every clip on a SECTION boundary — the design's premise
    (a clip that straddles a section boundary puts two zones' tiles in one
    section's 11-bit local palette). align=False packs them tight, which is
    what megaact's chain_act does, and is kept as the control.
    """
    clips = [parse_spec(s, st) for s in specs]
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
    act = build_act(args.spec, st, args.rowlen, align=not args.no_align)
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


def mode_place(args):
    """The DECISIVE one: run the REAL Pass 4 placement (fg_page_order.place_pool,
    the function ojz_strip_gen.generate() calls at tools/ojz_strip_gen.py:2177)
    and the REAL refusal on a stitched clip act. The shipped bake accepts the act
    iff verdict.ok."""
    import fg_page_order as fpo
    c, _ = mb.load_constants()
    st = c["SECTION_SIZE"] >> 3
    act = build_act(args.spec, st, args.rowlen, align=not args.no_align)

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
                        ojz_strip_gen.mark_pinned_pages, log=print)
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
    act = build_act(args.spec, st, args.rowlen, align=not args.no_align)
    frames = [c["PAGE_FRAMES"], mb.OWNER_LEVER_FRAMES]
    res = mb.measure_act(act, c, frames)
    print(json.dumps(mb.strip_arrays(res), indent=1))
    if args.json:
        json.dump(mb.strip_arrays(res), open(args.json, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("zones"); p.add_argument("zones", nargs="*"); p.add_argument("--json")
    p.set_defaults(fn=mode_zones)
    p = sub.add_parser("clipsweep"); p.add_argument("zone")
    p.add_argument("--secw", type=int, default=1); p.add_argument("--sech", type=int, default=1)
    p.add_argument("--top", type=int, default=5); p.add_argument("--json")
    p.set_defaults(fn=mode_clipsweep)
    for nm, fn in (("act", mode_act), ("window", mode_window), ("place", mode_place)):
        p = sub.add_parser(nm); p.add_argument("spec", nargs="+")
        p.add_argument("--rowlen", type=int, default=8); p.add_argument("--json")
        p.add_argument("--no-align", action="store_true")
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
