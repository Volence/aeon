#!/usr/bin/env python3
"""clip_act_bake.py — compose an act from a `clips.json` and run the REAL art-pool
placement over it with a REAL per-cell tileset key.

S2-COMPRESSED-ACT staged plan row 3, second half
(`docs/research/2026-09-17-s2-compressed-act-design.md` §2, §8). ART AND LAYOUT ONLY: no
collision, no objects, no rings, no regions, no background, no `.emp`, no ROM.

WHAT THIS CLOSES. `tools/fg_page_order.py`'s header said:

    Every act this generator can build today reads ONE tileset (project.json
    zones[0].tileset), so the generator passes a uniform zone grid; a stitched act's
    loader must supply the per-cell tileset key.

This is that loader. `clip_manifest.cell_grids` turns the manifest's destination
rectangles into the (rows, cols) `zone_id` grid, and this file hands it to
`fg_page_order.place_pool` in the same call shape `ojz_strip_gen.generate()` Pass 4 uses.
The key is load-bearing in TWO places, and only one of them is the placer:

  * the DEDUPE. A cell is keyed by (zone, source index), so Emerald Hill's tile 5 and
    Chemical Plant's tile 5 are two pool entries. Without the key they collapse and half
    the act renders the other zone's art. `verify_art_fidelity` below is the check.
  * the PLACER's searched rung (`fg_page_order.perzone_pages`), which builds pages that
    never mix two zones. The shipped rung does not read the key at all, so an act that
    fits without the search exercises only the first use.

WHY THE OUTPUT IS A SEPARATE TREE. `ojz_strip_gen.generate()` bakes one hard-wired act
(`OUTPUT_DIR`, `PROJECT_JSON`, `COLLISION_DIR`) and writes the ROM's collision tables on
the way past. A clip act is a second act, and a second act needs a `project.json` entry,
an `act_descriptor.emp` with matching `GRID_W`/`GRID_H` (`tools/act_grid.py` refuses
otherwise) and collision — staged-plan rows 4-6. So this tool bakes the ART half into its
own directory and leaves the committed OJZ tree untouched. Consequences, stated rather
than hidden:

  * `fg_page_order.check` cannot be pointed at this tree. It reads exactly one act
    (`_known_acts` raises on any other, `fg_working_set.GEN_DIR` and `Model`'s
    GRID_W/GRID_H are the OJZ act's), and teaching it a second one is a ROM change. The
    design's row-3 check is therefore executed here, against the same COUNT — this file
    imports `fg_page_order.window_needed` and `budget_verdict`, the two functions `check`
    itself calls, so the arithmetic is shared and only the decoding differs.
  * the decoding differs in one way and one way only: `check` recovers each cell's local
    index by S4LZ-decoding `sec{N}_blocks.bin`, this recovers it from `section_N.local.bin`.
    Blocks are staged-plan row 6's job because a block file carries the collision planes
    (`tools/ojz_block_gen.py` BLOCK_RAW_SIZE), and inventing collision bytes to reach a
    count is exactly the sort of filler this parcel is not allowed to take.

THE THREE NUMBERS this tool makes agree, and what each would catch:

  N1  the placement verdict — `place_pool`'s own count over the grid it just placed.
  N2  the recount, decoded back off disk from the emitted local maps, local-index
      nametables and page manifest. N2 != N1 means the emission lost or mangled the
      placement; the count itself is the same code.
  N3  `docs/research/s2-compressed-act/s2_clip_budget.py place` on the same clips, which
      reaches the same `place_pool` from the donor side without going through clips.json
      or a converted tree at all. N3 != N1 means the manifest path composed a different
      act than the rectangles describe.

  `bake --expect-worst N` fails unless N1 == N2 == N, so the pair is a gate and not a
  printout. N3 is a separate command by design: it is an INDEPENDENT second implementation
  and folding it in here would make it this tool's own opinion.

WHAT SECTION-ALIGNED PLACEMENT ACTUALLY BUYS (`measure-r12`, and it is less than the
design's §2.2 claimed). Two 1024x1024 clips of two different zones, EHZ and CPZ, in a
2x1-section act — same cells, same tilesets, three placements:

    placement                          sections used   local maps   pool  pages  worst
    separated, one zone per section          2          394 / 224    617    10    7 of 12
    adjacent,  one zone per section          2          394 / 224    617    10    9 of 12
    adjacent,  both in section 0             1          617 /   1    617    10    9 of 12

  Row 2 is the CONTROL for row 3: the clips touch in both, so "a camera window can hold
  both zones" is held fixed and the only thing that varies is whether a section boundary
  falls between them. The worst window is 9 in both. So the §2.2 sentence that a
  straddling clip hurts the page budget is NOT SUPPORTED: every page-budget difference in
  the table is adjacency (row 1 vs row 2), which is the §9.1 corridor argument, not the
  §2.2 alignment argument. What alignment does buy is the row-3 column: a section's local
  tile map is one 11-bit space capped at 2047 entries, and a mixed section needs the sum
  of both zones' tiles (617) where split sections need 394 and 224. That is why
  `clip_manifest` keeps R11 (section-aligned placement is the default, with an in-file
  opt-out) but demoted "two zones in one section" to a warning, W3: the exact limit is
  downstream and precise (`ojz_strip_gen.build_section_local_map` raises past 2047).

Usage:
    python3 tools/clip_act_bake.py bake <clips.json> [--out DIR] [--expect-worst N]
    python3 tools/clip_act_bake.py recount <baked DIR>
    python3 tools/clip_act_bake.py measure-r12
"""

import json
import os
import shutil
import struct
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import clip_manifest                              # noqa: E402
import fg_page_order as fpo                       # noqa: E402
import ojz_strip_gen                              # noqa: E402
import tile_dedupe                                # noqa: E402

TILE_MASK = tile_dedupe.NAMETABLE_TILE_MASK       # 0x07FF
#: dedupe key stride: one slot per representable tile index, so (zone, index) is unique.
KEY_STRIDE = TILE_MASK + 1

#: The pin rule, in the shape `place_pool` wants. ojz_strip_gen.mark_pinned_pages returns a
#: list[bool] parallel to `pages`; `place_pool`'s rule_pins_fn must return page INDICES.
#: generate() wraps it at tools/ojz_strip_gen.py Pass 4 and so does this — the design's
#: measurement tool did NOT, which is the defect the row-3 report names.
def rule_pins(pages, sets):
    return [i for i, f in enumerate(ojz_strip_gen.mark_pinned_pages(pages, sets)) if f]


class ClipBakeError(RuntimeError):
    """The clip act cannot be composed, placed or re-counted."""


# ---------------------------------------------------------------------------
# Compose + place
# ---------------------------------------------------------------------------

def dedupe_keyed(words, zone_id, blobs):
    """The shared cross-zone dedupe, keyed by (zone, source index).

    Returns (unique, canon, key, src_to_canon) where
      unique      list[bytes]  canonical 32-byte tiles, first-seen order
      canon       (rows, cols) int64 canonical id per cell
      key         (rows, cols) int64 the dedupe key (0 = VOID)
      src_to_canon dict key -> (canonical id, flip bits)

    VOID cells key to 0 and take the all-zero tile, matching
    `megaact_window_pageset.run_pipeline` and `fg_page_order`'s "global slot 0 is the
    blank tile" rule. A cell INSIDE a clip whose index is 0 is NOT void: it means tile 0
    of that zone's blob, which is what the donor renders there (both S2 donors load level
    art to VRAM tile 0, verified by tools/s2_zone_convert.py's vram_base_tile).
    """
    key = np.where(zone_id < 0, 0,
                   (zone_id.astype(np.int64) + 1) * KEY_STRIDE
                   + (words & TILE_MASK).astype(np.int64)).astype(np.int64)
    ref = np.unique(key)
    raw = []
    for k in ref.tolist():
        if k == 0:
            raw.append(tile_dedupe.BLANK_TILE)
            continue
        z, idx = k // KEY_STRIDE - 1, k % KEY_STRIDE
        blob = blobs[z]
        if (idx + 1) * tile_dedupe.TILE_SIZE > len(blob):
            raise ClipBakeError(
                f"zone key {z} is referenced at tile index {idx}, past the end of its "
                f"{len(blob) // tile_dedupe.TILE_SIZE}-tile blob. The converted tree and "
                f"the clip disagree about the tileset; re-run tools/s2_zone_convert.py.")
        raw.append(blob[idx * tile_dedupe.TILE_SIZE:(idx + 1) * tile_dedupe.TILE_SIZE])
    unique, mapping = tile_dedupe.dedupe_tiles(raw)
    canon_of_ref = np.array([m[0] for m in mapping], dtype=np.int64)
    canon = canon_of_ref[np.searchsorted(ref, key)]
    src_to_canon = {int(k): mapping[i] for i, k in enumerate(ref.tolist())}
    return unique, canon, key, src_to_canon


def place(act, donor_root=clip_manifest.DEFAULT_DONOR_ROOT, log=None):
    """Compose the act and run Pass 4. Returns everything the emitter and the checks need."""
    words, zone_id = clip_manifest.cell_grids(act, donor_root)
    sheets = clip_manifest.tilesets(act, donor_root)
    blobs = [s[2] for s in sheets]
    unique, canon, key, src_to_canon = dedupe_keyed(words, zone_id, blobs)
    budget = fpo.load_budget_constants()
    if budget["SECTION_SIZE"] != act.section_px:
        raise ClipBakeError("the budget constants and the manifest disagree about SECTION_SIZE")
    pl = fpo.place_pool(canon, zone_id, unique, act.section_tiles,
                        act.grid_w, act.grid_h, budget, rule_pins, log=log)
    return {"words": words, "zone_id": zone_id, "sheets": sheets, "key": key,
            "src_to_canon": src_to_canon, "budget": budget, "placement": pl,
            "pre_split_canon": canon}


# ---------------------------------------------------------------------------
# Checks that do not depend on the count
# ---------------------------------------------------------------------------

def verify_art_fidelity(st):
    """Every referenced (zone, index) pair resolves to THAT zone's art.

    This is the check the per-cell tileset key exists for. Without the key two zones'
    equal indices share one pool entry and one of them renders the other's tile; the
    window count would not notice, because a smaller pool needs no more pages.

    Method: the dedupe stores (canonical, flip) per key, and `canonical_form` returns the
    flip that takes the ORIGINAL to the canonical. Flips are involutions, so applying it
    to the canonical returns the original bytes. Compare those to the donor blob.
    Separately, assert every cell of a key carries one canonical after the placer's
    optional zone split, so the per-key result covers every cell.
    """
    pl = st["placement"]
    unique, canon = pl["unique"], pl["canon"]
    key = st["key"]
    blobs = [s[2] for s in st["sheets"]]

    pairs = np.unique(key * (len(unique) + 1) + canon)
    per_key = {}
    for p in pairs.tolist():
        k, c = divmod(p, len(unique) + 1)
        if k in per_key:
            raise ClipBakeError(
                f"key {k} maps to canonicals {per_key[k]} and {c} — a cell's art is not "
                f"a function of its (zone, index) pair")
        per_key[k] = c

    checked = 0
    for k, c in per_key.items():
        if k == 0:
            if unique[c] != tile_dedupe.BLANK_TILE:
                raise ClipBakeError("VOID cells do not resolve to the blank tile")
            continue
        z, idx = k // KEY_STRIDE - 1, k % KEY_STRIDE
        want = blobs[z][idx * tile_dedupe.TILE_SIZE:(idx + 1) * tile_dedupe.TILE_SIZE]
        _c0, flip = st["src_to_canon"][k]
        got = unique[c]
        if flip & 1:
            got = tile_dedupe.hflip_tile(got)
        if flip & 2:
            got = tile_dedupe.vflip_tile(got)
        if got != want:
            raise ClipBakeError(
                f"zone key {z} tile {idx}: the placed pool entry is not this zone's art. "
                f"This is what happens when two zones share one tile-index space — the "
                f"per-cell tileset key (tools/clip_manifest.py cell_grids) is not reaching "
                f"the dedupe.")
        checked += 1
    return checked


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------

def emit(act, st, out_dir, donor_root=clip_manifest.DEFAULT_DONOR_ROOT):
    """Write the composed act tree + the placed pool artifacts. Returns the summary dict."""
    pl = st["placement"]
    budget = st["budget"]
    page_tiles = budget["ART_POOL_PAGE_TILES"]
    sect = act.section_tiles
    unique, canon = pl["unique"], pl["canon"]
    slot_of = pl["slot_of"]
    pages = pl["pages"]

    os.makedirs(out_dir, exist_ok=True)

    # per-section global slot sets -> local maps (ojz_strip_gen owns the rule)
    local_maps = []
    for s_idx, sec_canons in enumerate(pl["per_section"]):
        globals_ = {int(slot_of[c]) for c in sec_canons}
        local_maps.append(ojz_strip_gen.build_section_local_map(globals_))

    words = st["words"]
    n_sections = act.grid_w * act.grid_h
    sec_rows = []
    for s_idx in range(n_sections):
        sy, sx = divmod(s_idx, act.grid_w)
        r0, c0 = sy * sect, sx * sect
        sub_words = words[r0:r0 + sect, c0:c0 + sect]
        sub_canon = canon[r0:r0 + sect, c0:c0 + sect]
        sub_key = st["key"][r0:r0 + sect, c0:c0 + sect]
        lmap = local_maps[s_idx]
        g2l = {g: i for i, g in enumerate(lmap)}

        out = np.zeros((sect, sect), dtype=np.uint16)
        for (r, cc), w in np.ndenumerate(sub_words):
            k = int(sub_key[r, cc])
            flip = st["src_to_canon"][k][1] if k else 0
            out[r, cc] = tile_dedupe.remap_nametable_word(
                int(w), g2l[int(slot_of[int(sub_canon[r, cc])])], flip)

        # the composed act, in each clip's own indices — what aurora edits
        with open(os.path.join(out_dir, f"section_{s_idx}.tiles.bin"), "wb") as fh:
            fh.write(sub_words.astype(">u2").tobytes())
        # the same cells with SECTION-LOCAL pool indices — what the recount decodes.
        # Same shape as .tiles.bin on purpose: no new format is invented here.
        with open(os.path.join(out_dir, f"section_{s_idx}.local.bin"), "wb") as fh:
            fh.write(out.astype(">u2").tobytes())
        with open(os.path.join(out_dir, f"sec{s_idx}_local_map.bin"), "wb") as fh:
            fh.write(struct.pack(f">{len(lmap)}H", *lmap))
        sec_rows.append({
            "n": s_idx, "sx": sx, "sy": sy,
            "local_map_entries": len(lmap),
            "zone_keys": sorted({int(v) for v in np.unique(st["zone_id"][r0:r0 + sect, c0:c0 + sect])
                                 if int(v) >= 0}),
            "painted_cells": int(np.count_nonzero((sub_words & TILE_MASK) != 0)),
        })

    # the placed pool, in pool order: page p's tiles start at global slot p * page_tiles
    with open(os.path.join(out_dir, "pool.bin"), "wb") as fh:
        for p, page in enumerate(pages):
            for cid in page:
                fh.write(unique[cid])
            fh.write(bytes(tile_dedupe.TILE_SIZE * (page_tiles - len(page))))

    manifest = {
        "schema": 1,
        "produced_by": "tools/clip_act_bake.py",
        "content": "foreground art + layout only (no collision, objects, rings, regions, "
                   "background) — S2-COMPRESSED-ACT staged plan row 3",
        "act": {"id": act.id, "name": act.name,
                "grid_w": act.grid_w, "grid_h": act.grid_h,
                "section_px": act.section_px, "cells": [act.cols, act.rows]},
        "source_manifest": os.path.relpath(act.path, REPO),
        "clips": [c.as_json() for c in act.clips],
        "zone_table": [
            {"key": i, "donor": d, "zone": z, "tiles": len(b) // tile_dedupe.TILE_SIZE,
             "tileset_sha256": zm["tileset"]["sha256"],
             "palette_sha256": zm["palette"]["sha256"],
             "tree": os.path.relpath(os.path.join(donor_root, d, z), REPO)}
            for i, (d, z, b, zm) in enumerate(st["sheets"])],
        "pool": {"tiles": len(unique), "pages": len(pages),
                 "page_tiles": page_tiles,
                 "page_lengths": [len(p) for p in pages],
                 "pool_bin": "pool.bin (pages padded to page_tiles; slot = page*page_tiles + i)"},
        "placement": {"rung": pl["rung"], "pins": [int(p) for p in pl["pins"]],
                      "rule_pins": [int(p) for p in pl["rule_pins"]],
                      "stats": pl["stats"], "seconds": pl["seconds"]},
        "verdict_at_placement": pl["verdict"],
        "sections": sec_rows,
        "warnings": act.warnings,
    }
    with open(os.path.join(out_dir, "clipact.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    shutil.copyfile(act.path, os.path.join(out_dir, "clips.json"))
    return manifest


# ---------------------------------------------------------------------------
# The recount — off disk, through the SAME count `fg_page_order.check` runs
# ---------------------------------------------------------------------------

def page_grid_from_tree(out_dir):
    """(page grid, pins, n_pages) decoded from an emitted clip-act tree.

    The per-cell arithmetic is `fg_working_set.load_page_grid`'s, restated over the
    local-index nametable instead of the S4LZ block blob: local 0 is blank, a local index
    past the map is a hard error, global 0 references no page, otherwise the page is
    `global >> PAGE_FRAME_TILE_SHIFT`.
    """
    with open(os.path.join(out_dir, "clipact.json")) as fh:
        cm = json.load(fh)
    c = fpo.load_budget_constants()
    if cm["pool"]["page_tiles"] != c["ART_POOL_PAGE_TILES"]:
        raise ClipBakeError(
            f"{out_dir} was baked at {cm['pool']['page_tiles']}-tile pages but the engine "
            f"now says {c['ART_POOL_PAGE_TILES']} — UNMEASURABLE, re-bake it")
    gw, gh = cm["act"]["grid_w"], cm["act"]["grid_h"]
    sect = cm["act"]["section_px"] // clip_manifest.TILE_PX
    n_pages = cm["pool"]["pages"]
    pins = sorted({0} | set(cm["placement"]["pins"]))
    grid = np.full((gh * sect, gw * sect), -1, dtype=np.int16)
    for s_idx in range(gw * gh):
        with open(os.path.join(out_dir, f"section_{s_idx}.local.bin"), "rb") as fh:
            data = fh.read()
        want = sect * sect * 2
        if len(data) != want:
            raise ClipBakeError(f"section_{s_idx}.local.bin is {len(data)} bytes, expected {want}")
        nt = np.frombuffer(data, dtype=">u2").reshape(sect, sect).astype(np.int64)
        with open(os.path.join(out_dir, f"sec{s_idx}_local_map.bin"), "rb") as fh:
            raw = fh.read()
        lmap = np.array(struct.unpack(f">{len(raw) // 2}H", raw), dtype=np.int64)
        if lmap[0] != 0:
            raise ClipBakeError(
                f"sec{s_idx} local map violates the blank-first invariant (map[0] == {lmap[0]})")
        local = nt & TILE_MASK
        if int(local.max()) >= len(lmap):
            raise ClipBakeError(
                f"sec{s_idx}: a cell names local index {int(local.max())} past the "
                f"{len(lmap)}-entry local map")
        glob = lmap[local]
        page = np.where(glob == 0, -1, glob >> c["PAGE_FRAME_TILE_SHIFT"])
        sy, sx = divmod(s_idx, gw)
        grid[sy * sect:(sy + 1) * sect, sx * sect:(sx + 1) * sect] = page.astype(np.int16)
    if int(grid.max()) >= n_pages:
        raise ClipBakeError(
            f"a cell references page {int(grid.max())} past the {n_pages}-page manifest")
    return grid, pins, n_pages


def recount(out_dir):
    """The window-budget verdict of an emitted tree, through fg_page_order's own count."""
    pg, pins, n_pages = page_grid_from_tree(out_dir)
    c = fpo.load_budget_constants()
    H, W = pg.shape
    lefts, tops, _, _ = fpo.camera_windows(c, W, H)
    needed, _pin0 = fpo.window_needed(pg, n_pages, pins, c, lefts, tops)
    return fpo.budget_verdict(needed, lefts, tops, c)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def bake(manifest_path, out_dir=None, expect_worst=None,
         donor_root=clip_manifest.DEFAULT_DONOR_ROOT, log=print):
    act = clip_manifest.load(manifest_path, donor_root=donor_root,
                             warn=(lambda m: log(f"  WARNING: {m}")) if log else None)
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), "baked")
    if log:
        log(f"clip act: {act.summary()}")
    st = place(act, donor_root, log=log)
    pl = st["placement"]
    n_checked = verify_art_fidelity(st)
    if log:
        log(f"  art fidelity: {n_checked} (zone, tile) pair(s) resolve to their own zone's art")
    manifest = emit(act, st, out_dir, donor_root)
    v1 = pl["verdict"]
    v2 = recount(out_dir)
    if log:
        log("  N1 " + fpo.verdict_line(v1, "placement"))
        log("  N2 " + fpo.verdict_line(v2, "recount off disk"))
    if v1["worst"] != v2["worst"] or v1["over"] != v2["over"] or v1["windows"] != v2["windows"]:
        raise ClipBakeError(
            f"the emitted tree does not re-count as it was placed: placement "
            f"worst={v1['worst']} over={v1['over']} windows={v1['windows']}, recount "
            f"worst={v2['worst']} over={v2['over']} windows={v2['windows']}. The count is "
            f"the same code either way, so this is the emission.")
    manifest["verdict_at_recount"] = v2
    with open(os.path.join(out_dir, "clipact.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    if expect_worst is not None and v1["worst"] != expect_worst:
        raise ClipBakeError(
            f"--expect-worst {expect_worst} but the act's worst camera window needs "
            f"{v1['worst']} page frame(s)")
    fpo.refuse_over_budget(v1, f"clip act {act.id}")
    return act, st, manifest, v1, v2


def _mode_bake(rest):
    if not rest:
        print(USAGE)
        return 1
    path, out_dir, expect = rest[0], None, None
    extra = rest[1:]
    while extra:
        if extra[0] == "--out" and len(extra) > 1:
            out_dir, extra = extra[1], extra[2:]
        elif extra[0] == "--expect-worst" and len(extra) > 1:
            expect, extra = int(extra[1]), extra[2:]
        else:
            print(f"ERROR: unknown argument {extra[0]!r}")
            print(USAGE)
            return 1
    t0 = time.time()
    try:
        _act, _st, m, v1, _v2 = bake(path, out_dir, expect)
    except (clip_manifest.ClipManifestError, ClipBakeError) as exc:
        print(f"clip act REFUSED — {exc}")
        return 1
    print(f"clip act baked: {m['pool']['tiles']} pool tiles in {m['pool']['pages']} pages, "
          f"rung {m['placement']['rung']}, worst window {v1['worst']} of {v1['frames']}, "
          f"{v1['over']} over budget; {time.time() - t0:.2f} s")
    return 0


def _mode_recount(rest):
    if len(rest) != 1:
        print(USAGE)
        return 1
    try:
        v = recount(rest[0])
    except (ClipBakeError, fpo.BudgetError) as exc:
        print(f"clip act recount UNMEASURABLE — {exc}")
        return 2
    print(fpo.verdict_line(v, f"{rest[0]} (recount)"))
    return 0 if v["ok"] else 1


R12_CLIPS = ("s2disasm", "EHZ", "s2disasm", "CPZ")


#: (label, clip A dst x, clip B dst x) for measure-r12, in a 2x1-section act with two
#: 1024x1024 clips of two different zones. Row 2 is the CONTROL for row 3: the two clips
#: touch in both, so "a camera window can hold both zones" is held fixed and the only
#: thing that varies is whether the section boundary falls between them. Row 1 is the
#: separated case, kept to show how much of row 3's cost is adjacency rather than mixing.
R12_ROWS = (
    ("separated, one zone per section", 0, 2048),
    ("adjacent,  one zone per section", 1024, 2048),
    ("adjacent,  both in section 0", 0, 1024),
)


def _mode_measure_r12(rest):
    """The measurement behind clip_manifest's R12, run from the same code the bake uses."""
    if rest:
        print(USAGE)
        return 1
    import tempfile
    rows = []
    for label, ax, bx in R12_ROWS:
        doc = {"schema": 1, "id": "r12_probe", "act": {"grid_w": 2, "grid_h": 1},
               "clips": [
                   {"id": "a", "donor": R12_CLIPS[0], "zone": R12_CLIPS[1],
                    "src_rect": {"x": 4096, "y": 0, "w": 1024, "h": 1024},
                    "dst_rect": {"x": ax, "y": 0, "w": 1024, "h": 1024},
                    "unaligned_dst_reason": "R12 measurement probe"},
                   {"id": "b", "donor": R12_CLIPS[2], "zone": R12_CLIPS[3],
                    "src_rect": {"x": 4096, "y": 0, "w": 1024, "h": 1024},
                    "dst_rect": {"x": bx, "y": 0, "w": 1024, "h": 1024},
                    "unaligned_dst_reason": "R12 measurement probe"}]}
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "clips.json")
            with open(p, "w") as fh:
                json.dump(doc, fh)
            try:
                act = _load_ignoring_r12(p)
            except clip_manifest.ClipManifestError as exc:
                print(f"measure-r12 UNMEASURABLE — {exc}")
                return 2
            st = place(act, log=None)
            m = emit(act, st, os.path.join(td, "baked"))
            v = recount(os.path.join(td, "baked"))
            rows.append((label, m, v))
    print(f"{'placement':34s} {'sections used':>13s} {'local maps':>18s} {'pool':>6s} "
          f"{'pages':>6s} {'worst':>6s}")
    for label, m, v in rows:
        used = sum(1 for s in m["sections"] if s["zone_keys"])
        lm = " / ".join(str(s["local_map_entries"]) for s in m["sections"])
        print(f"{label:34s} {used:>13d} {lm:>18s} {m['pool']['tiles']:>6d} "
              f"{m['pool']['pages']:>6d} {v['worst']:>4d} of {v['frames']}")
    return 0


def _load_ignoring_r12(path):
    """Load a manifest with R12 suppressed — ONLY for measure-r12, which measures R12.

    R12 is the LAST rule `clip_manifest.load` runs, so a manifest that reaches it has
    already passed every other rule; the ClipAct is then rebuilt from those validated
    pieces rather than by giving the validator a bypass flag that a caller could reach.
    """
    seen = []
    try:
        return clip_manifest.load(path, warn=None)
    except clip_manifest.ClipManifestError as exc:
        if not str(exc).startswith("R12"):
            raise
        seen.append(str(exc))
    with open(path) as fh:
        raw = json.load(fh)
    clips = [clip_manifest.Clip(cr, i) for i, cr in enumerate(raw["clips"])]
    keys = {}
    for cl in clips:
        cl.zone_key = keys.setdefault(cl.tree_key, len(keys))
    return clip_manifest.ClipAct(path, raw, clips, raw["act"]["grid_w"],
                                 raw["act"]["grid_h"],
                                 clip_manifest.geometry_constants(), seen)


USAGE = """Usage:
    python3 tools/clip_act_bake.py bake <clips.json> [--out DIR] [--expect-worst N]
    python3 tools/clip_act_bake.py recount <baked DIR>
    python3 tools/clip_act_bake.py measure-r12"""

MODES = {"bake": _mode_bake, "recount": _mode_recount, "measure-r12": _mode_measure_r12}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(USAGE)
        sys.exit(1)
    return handler(args[1:])


if __name__ == "__main__":
    sys.exit(main())
