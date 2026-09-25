#!/usr/bin/env python3
"""clip_act_bake.py — compose an act from a `clips.json` and run the REAL art-pool
placement over it with a REAL per-cell tileset key.

S2-COMPRESSED-ACT staged plan row 3, second half, plus row 5's collision half
(`docs/research/2026-09-17-s2-compressed-act-design.md` §2, §3.5, §8). No objects, no
rings, no regions, no background, no `.emp`, no ROM.

~~ART AND LAYOUT ONLY~~ — **ROW 5, 2026-09-17: collision too.** Both plane files are
emitted beside the art, the act's attr-set size is counted and capped, and the §8 per-clip
readout is complete. See "COLLISION" below and the C1-C3 block further down.

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

WHAT SECTION-ALIGNED PLACEMENT ACTUALLY BUYS (`measure-alignment`, and it is less than the
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

COLLISION (row 5), and the number it exists to produce. The clip's collision planes come
from the SAME rectangles as its art — `clip_manifest.collision_grids` shares
`cell_grids`' loop, so a rectangle cannot mean one thing to the tiles and another to the
ground — and they are emitted in the same per-plane cell-word format an authored act uses,
against the S2 base bank the donor tree names (`base_s2/`, NOT the S&K bank the shipped
OJZ act uses; the same index is a different shape in the two).

  THE NUMBER is the act's attr-set size against `AttrSet.CAP` = 255, the design's §3.5
  cap and the one budget of this act that a bigger ROM cannot buy out of. It is counted
  twice, the same way the window budget is: once over the composed grids and once decoded
  back OFF DISK (`recount_collision`), so a disagreement is the emission rather than the
  arithmetic. The §8 readout the author needs is per clip and printed per clip: entries
  the clip needs ALONE, entries it ADDS to the clips before it, solid cells, and crossover
  marks taken.

  MEASURED AGAINST THE DESIGN'S OWN PREDICTOR, which reaches `bake_cell` from the donor
  side without going through clips.json, a converted tree or a plane file at all — six
  numbers, six exact matches:

    fixture            clip     alone  s2_clip_budget collision   act   act predicted
    s2_two_clip        ehz_s2      95  EHZ:2,1 -> 95              207   EHZ:2,1 CPZ:2,1 -> 207
    s2_two_clip        cpz_s2     148  CPZ:2,1 -> 148
    s2_two_clip_pins   ehz_s1      62  EHZ:1,1 -> 62              191   EHZ:1,1 CPZ:1,1 -> 191
    s2_two_clip_pins   cpz_s1     148  CPZ:1,1 -> 148

  The two agree only because these clips are full-height and section-aligned: that tool's
  `ZONE:s0,n` spec has no vertical extent and counts every chunk its COLUMN range
  references, over every row. A clip taller or shorter than its zone's grid is a different
  rectangle and the numbers are allowed to differ; this tool's is the one about the bytes.

PER-CLIP POOL ROWS (2026-09-25, aurora's row-8 ask; design §8 RULED block). `clipact.json`
`pool` carries, beside the act-level `tiles` / `pages`:

    "per_clip":    [ {"id", "index", "tiles", "tiles_added",
                      "pages_touched", "pages_exclusive"}, ... ]   // one per clips[i]
    "per_corridor": [ same row shape ]                              // one per corridors[i]
    "per_clip_fields": { field -> its meaning }   // PER_CLIP_POOL_FIELDS, verbatim

  tiles            distinct pool tiles the rectangle's cells reference, blank (slot 0) excluded
  tiles_added      of those, the ones no earlier row references (clips in manifest order,
                   then corridors); sum over all rows + 1 == pool.tiles
  pages_touched    pages holding any of its tiles: what must be resident to draw all of it.
                   Shared pages count for every row, so the sum can exceed pool.pages
  pages_exclusive  touched pages no other row touches; sum over rows <= pool.pages
  There is NO field called "pages" — see "Per-clip pool readout" below for why. Every row
  is sliced out of the same placement dict `pool.tiles`/`pool.pages` come from;
  `tools/test_clip_pool_per_clip.py` re-derives each one off the emitted tree.

`bake --json` (added 2026-09-25 for aurora's Sonic 2 donor page, aurora ROADMAP row 213 open
item (a); aeon row CLIP-BAKE-JSON). Same bake, same output tree, same exit codes (0 baked, 1
refused), and the human mode's output is unchanged byte for byte. Instead of the progress
lines it prints ONE JSON document on stdout, in `clip_manifest.py validate --json`'s shape
(built by the same `clip_manifest.refusal_record` / `json_text`), so one reader reads both:

    { "schema": 1,              // BAKE_JSON_SCHEMA; bumped on its own, on any change a
                                //   reader of this document could see
      "ok": false,              // true iff exit code 0
      "refusals": [             // [] when ok. At most ONE entry: the bake stops at the first
        {                       //   refusal. A list so that never changes the shape.
          "rule": "C1",         // the message's leading tag: R1-R12 / K1-K3 (the manifest,
                                //   as validate --json gives them), C1-C3 (this file's
                                //   collision refusals); "FG_PAGE_BUDGET" for the page
                                //   budget; null for an untagged refusal (--expect-worst
                                //   not met, an emitted tree that does not re-count as it
                                //   was placed, a tileset shorter than a clip's indices)
          "subjects": [         // WHICH clip(s)/corridor(s), validate --json's subject
            { "kind": "clip",   //   dicts. [] = about the act as a whole: C2 (the act's
              "index": 0,       //   attr-set cap), C3 (a profile in the act's merged set),
              "id": "ehz_cut" } //   the page budget (a camera window, not a clip), and
          ],                    //   every untagged one. C1 names its clip.
          "message": "C1 clip 'ehz_cut': its source rectangle takes ..." } ],
                                // the human sentence: what the human mode prints after
                                //   "clip act REFUSED — ", or for the page budget, the
                                //   stderr sentence after its leading "REFUSED — "
      "warnings": [ ... ] }     // W2/W3 from the manifest loader, validate --json's shape

A refusal is EXACTLY what the human mode reports as REFUSED, and nothing else:
  * a `clip_manifest.ClipManifestError`. It does reach `bake`: `load()` is the first call,
    and `place()`/`collision()` reach the loader's tree readers, which raise it too;
  * a `ClipBakeError` or subclass (`ClipCollisionError`);
  * the FG page budget. That one is `fg_page_order.refuse_over_budget`'s SystemExit, shared
    with the OJZ generator; the human mode lets it print "REFUSED — FG page budget: ..." on
    stderr. `--json` asks that same function itself (`budget_refusal`, `bake(...,
    refuse_budget=False)`), catching its SystemExit around that ONE call only.
Anything else is a crash and is not wrapped: a manifest that is not JSON, a path that does
not exist, a non-integer --expect-worst, a BudgetError. Traceback, exit code 1, and NO JSON on
stdout, in either mode. A caller must read "exit 1 and stdout that is not JSON" as a crash,
never as a refusal. A usage error prints USAGE (unchanged, still human) and exits 1.
`--json` goes after the manifest path, anywhere among the other options.

A refusal can come AFTER the tree is written: --expect-worst and the page budget are decided
on the emitted tree, so `--out` then holds a complete tree, `clipact.json` included, exactly
as the human mode leaves it. An ok of false means: do not use that tree.

Usage:
    python3 tools/clip_act_bake.py bake <clips.json> [--out DIR] [--expect-worst N] [--json]
    python3 tools/clip_act_bake.py recount <baked DIR>
    python3 tools/clip_act_bake.py measure-alignment
"""

import hashlib
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
import collision_pipeline                         # noqa: E402
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
    """The clip act cannot be composed, placed or re-counted.

    `subjects` names the clip(s)/corridor(s) the refusal is about (`clip_manifest.subject()`
    dicts; empty for an act-level refusal) and `rule` is the message's leading tag, read by
    the same reader `clip_manifest` uses. Neither changes the message: str(exc) is exactly
    what it always was, so the human mode cannot move."""

    def __init__(self, message, subjects=()):
        super().__init__(message)
        self.subjects = [dict(s) for s in subjects]

    @property
    def rule(self):
        return clip_manifest.rule_of(str(self))


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


def place(act, donor_root=None, log=None):
    """Compose the act and run Pass 4. Returns everything the emitter and the checks need.

    `donor_root=None` resolves through clip_manifest at CALL TIME — see the note at
    clip_manifest.DEFAULT_DONOR_ROOT for why none of these is a default bound at import."""
    donor_root = clip_manifest._root(donor_root)
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


def zone_separation(act, zone_id, constants=None):
    """Z1 — does any camera position hold cells of two DONOR zones at once?

    S2-COMPRESSED-ACT row 7's first static check, in the design's own words (§10 row 7):
    "no camera position holds cells from both clips". WHY IT MATTERS: two Sonic 2 zones
    disagree about which CRAM line their ground is (§5.3), and a region crossing installs
    ONE palette for all three lines — so a screen showing two zones shows one of them in
    the other's colours. The corridor (clip_manifest CORRIDORS) is what prevents it, and
    this is what says whether it does.

    THE WINDOW IS THE TILE CACHE'S, not the 320-px screen, and it is read rather than
    typed: `fg_page_order.camera_windows` enumerates every window a camera in the act can
    produce and each is TILE_CACHE_COLS x TILE_CACHE_ROWS cells from its (left, top) —
    `require_clamp_binds` proves the held window is exactly that at every sub-tile offset.
    It is the stronger statement of the two: the cache is what the page budget counts and
    what streams, and it is wider than the screen (the screen is inside it), so a cache
    window holding one zone is a screen holding one zone.

    CORRIDOR and VOID cells are not zones and do not count: the corridor sheet is drawn on
    the one CRAM line no install writes, and a void cell is the blank tile.

    Returns a dict — `mixed` is the number of windows holding two zones (0 is the pass),
    with the first such window and the narrowest gap between two zones' cells in the act,
    against the window's width, so a near miss is visible before it is a failure.
    """
    c = constants or fpo.load_budget_constants()
    H, W = zone_id.shape
    lefts, tops, _mx, _my = fpo.camera_windows(c, W, H)
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    donors = list(range(len(act.zone_table)))
    present = []
    for k in donors:
        m = (zone_id == k).astype(np.int32)
        ii = np.zeros((H + 1, W + 1), dtype=np.int64)
        np.cumsum(np.cumsum(m, axis=0), axis=1, out=ii[1:, 1:])
        t0 = np.clip(tops, 0, H)[:, None]
        t1 = np.clip(tops + rows, 0, H)[:, None]
        l0 = np.clip(lefts, 0, W)[None, :]
        l1 = np.clip(lefts + cols, 0, W)[None, :]
        cnt = ii[t1, l1] - ii[t0, l1] - ii[t1, l0] + ii[t0, l0]
        present.append(cnt > 0)
    n_present = (np.sum(present, axis=0) if present
                 else np.zeros((len(tops), len(lefts)), dtype=np.int64))
    mixed = int(np.count_nonzero(n_present > 1))
    first = None
    if mixed:
        ti, li = np.argwhere(n_present > 1)[0]
        first = {"left_tile": int(lefts[li]), "top_tile": int(tops[ti]),
                 "camera_x_px_approx": int(lefts[li]) * clip_manifest.TILE_PX}
    # The narrowest horizontal gap between the column spans of two different zones, per
    # tile row, in cells — reported against the window width so a near miss shows.
    gap = None
    col_has = [np.any(zone_id == k, axis=0) for k in donors]
    for a in donors:
        for b in donors:
            if a >= b:
                continue
            ca, cb = np.flatnonzero(col_has[a]), np.flatnonzero(col_has[b])
            if len(ca) and len(cb):
                g = max(int(cb.min()) - int(ca.max()) - 1, int(ca.min()) - int(cb.max()) - 1)
                gap = g if gap is None else min(gap, g)
    return {"windows": int(len(lefts) * len(tops)), "mixed": mixed, "first_mixed": first,
            "donor_zones": len(donors), "window_cells": [cols, rows],
            "min_column_gap_cells": gap}


# ---------------------------------------------------------------------------
# Per-clip pool readout — design §8, "unique tiles and pages this clip adds"
# ---------------------------------------------------------------------------
#
# ADDED 2026-09-25 for aurora's Sonic 2 donor page (row-8 ask, design §8 RULED block).
# Written into clipact.json as `pool.per_clip` (index-aligned with `clips`) and
# `pool.per_corridor` (index-aligned with `corridors`), one row shape for both, with the
# meaning of every field carried beside them in `pool.per_clip_fields` so a reader never
# has to find this comment to know what a number means.
#
# SAME CODE PATH AS THE ACT-LEVEL FIGURES. `pool.tiles` is len(placement["unique"]) and
# `pool.pages` is len(placement["pages"]); the rows below read the same placement dict —
# `canon` (the post-split canonical id of every cell) and `page_grid` (the per-cell page
# index `_evaluate` builds and the window budget counts, global slot 0 = -1 = no page) —
# sliced by each rectangle. Nothing is re-deduped or re-placed.
#
# WHY "PAGES TOUCHED" AND "PAGES EXCLUSIVE", and not a single "pages" number. A page is
# 64 tiles of ONE placement of the WHOLE act, so when two clips share a page (two clips of
# one zone always can; page 0 is everyone's) there is no true per-clip share of it. The two
# numbers an author choosing what to paste can act on are:
#   * pages_touched — how many pages must be resident to draw ALL of this clip. It is the
#     clip's own streaming footprint, it is what the camera-window budget is made of, and
#     it OVER-COUNTS across clips by design: the sum over clips can exceed pool.pages.
#   * pages_exclusive — the touched pages no OTHER clip or corridor touches: the pages that
#     exist in this pool only because of this clip. The sum over rows never exceeds
#     pool.pages. (It is not a promise of what deleting the clip would save — a re-bake
#     re-places the pool.)
# A single "pages" field would be read as one of these by one reader and the other by the
# next, so there is no field called "pages".

#: Field meanings, copied VERBATIM into clipact.json `pool.per_clip_fields`.
PER_CLIP_POOL_FIELDS = {
    "id": "the clip's (or corridor's) id from clips.json",
    "index": "its position in clips.json's `clips` (per_clip) or `corridors` (per_corridor) list",
    "tiles": "distinct pool tiles (post-dedupe canonical tiles, flips folded) this rectangle's "
             "cells reference, EXCLUDING the blank tile at pool slot 0, which the act always "
             "carries whatever is pasted",
    "tiles_added": "of `tiles`, those no EARLIER row references; rows are ordered clips (in "
                   "manifest order) then corridors. sum(tiles_added over per_clip and "
                   "per_corridor) + 1 (the blank) == pool.tiles",
    "pages_touched": "pool pages holding at least one of this rectangle's `tiles` (the pages "
                     "that must be resident to draw ALL of it). Shared pages count for every "
                     "row that touches them, so the sum over rows can exceed pool.pages",
    "pages_exclusive": "of pages_touched, the pages NO other clip or corridor touches (the "
                       "pages in this pool only because of this rectangle). Sum over rows "
                       "<= pool.pages. Not a prediction of what removing it saves: a re-bake "
                       "re-places the whole pool",
}


def pool_contributions(act, pl):
    """(per_clip rows, per_corridor rows) — see PER_CLIP_POOL_FIELDS for each field.

    Reads the placement `place_pool` returned (`canon`, `page_grid`, `slot_of`) and slices
    it by each rectangle's dst cells; the blank is identified by its SLOT (0), the same
    rule `_evaluate`'s page grid uses to give it no page."""
    canon, pg, slot_of = pl["canon"], pl["page_grid"], pl["slot_of"]
    blank = {int(c) for c in np.flatnonzero(slot_of == 0)}
    rects = ([("clip", r) for r in act.clips] + [("corridor", r) for r in act.corridors])
    sets = []
    for _kind, r in rects:
        dx, dy, w, h = (v // clip_manifest.TILE_PX for v in r.dst)
        tiles = {int(c) for c in np.unique(canon[dy:dy + h, dx:dx + w])} - blank
        sub_pg = pg[dy:dy + h, dx:dx + w]
        pages = {int(p) for p in np.unique(sub_pg[sub_pg >= 0])}
        sets.append((tiles, pages))
    touch = {}
    for _t, pages in sets:
        for p in pages:
            touch[p] = touch.get(p, 0) + 1
    seen, clips, corridors = set(), [], []
    for (kind, r), (tiles, pages) in zip(rects, sets):
        row = {"id": r.id, "index": r.index,
               "tiles": len(tiles), "tiles_added": len(tiles - seen),
               "pages_touched": len(pages),
               "pages_exclusive": sum(1 for p in pages if touch[p] == 1)}
        seen |= tiles
        (clips if kind == "clip" else corridors).append(row)
    return clips, corridors


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------

def emit(act, st, out_dir, donor_root=None):
    """Write the composed act tree + the placed pool artifacts. Returns the summary dict."""
    donor_root = clip_manifest._root(donor_root)
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

    # THE PER-CELL TILESET KEY, ON DISK (row 7). One signed byte per cell, row-major like
    # section_N.tiles.bin, -1 = VOID. This is what lets the ROM bake
    # (ojz_strip_gen.generate(), pointed at this tree by clip_rom_bake's staged project)
    # resolve a cell against ITS OWN zone's tileset instead of project.json's one. Written
    # for every clip act, one zone or many, so there is one path and no special case.
    zone_id = st["zone_id"]
    for s_idx in range(n_sections):
        sy, sx = divmod(s_idx, act.grid_w)
        r0, c0 = sy * sect, sx * sect
        with open(os.path.join(out_dir, f"section_{s_idx}.zonekey.bin"), "wb") as fh:
            fh.write(zone_id[r0:r0 + sect, c0:c0 + sect].astype(np.int8).tobytes())
    per_clip, per_corridor = pool_contributions(act, pl)
    sheet_files = []
    for i, (d, z, b, zm) in enumerate(st["sheets"]):
        if (d, z) == clip_manifest.CORRIDOR_SHEET:
            p = os.path.join(out_dir, "corridor_sheet.bin")
            with open(p, "wb") as fh:
                fh.write(b)
        else:
            p = os.path.join(donor_root, d, z, "tileset.bin")
        sheet_files.append(p)

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
        "corridors": [c.as_json() for c in act.corridors],
        "zone_table": [
            {"key": i, "donor": d, "zone": z, "tiles": len(b) // tile_dedupe.TILE_SIZE,
             "tileset_sha256": zm["tileset"]["sha256"],
             "palette_sha256": (zm.get("palette") or {}).get("sha256"),
             "synthesised": zm.get("synthesised"),
             "tileset_file": os.path.relpath(sheet_files[i], REPO),
             "tree": (None if zm.get("synthesised") else
                      os.path.relpath(os.path.join(donor_root, d, z), REPO))}
            for i, (d, z, b, zm) in enumerate(st["sheets"])],
        "zone_separation": zone_separation(act, zone_id),
        "pool": {"tiles": len(unique), "pages": len(pages),
                 "page_tiles": page_tiles,
                 "page_lengths": [len(p) for p in pages],
                 "pool_bin": "pool.bin (pages padded to page_tiles; slot = page*page_tiles + i)",
                 "per_clip": per_clip, "per_corridor": per_corridor,
                 "per_clip_fields": dict(PER_CLIP_POOL_FIELDS)},
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
# Collision — S2-COMPRESSED-ACT staged plan row 5
# ---------------------------------------------------------------------------
#
# The clip's collision planes come from the SAME rectangles as its art
# (`clip_manifest.collision_grids`, which shares `cell_grids`' loop), and are
# emitted in the same per-plane cell-word format an authored act uses. The three
# refusals below are tagged C1-C3 rather than continuing `clip_manifest`'s R/W
# namespace, because they are BAKE-time facts: each needs the collision bytes and
# the base bank, neither of which the manifest loader reads.
#
#   C1  the clip severs a crossover. A rectangle that takes SOME of a zone's
#       crossover marks and leaves others may have cut a loop in half — the encoding
#       records which plane a mark points at (docs/LOOP_CROSSOVER_ENCODING.md §3.3)
#       but NOT which loop it belongs to, so nothing can tell a severed loop from
#       two unrelated ones. CONSERVATIVE by necessity and it says so; opt out with
#       "severed_xover_reason" on the clip.
#       ⚠ WHAT THE DESIGN GOT WRONG HERE, corrected in §2.3 in place: it said a
#       marquee that cuts a loop "will fail the bake" via
#       `apply_editor_collision_overlay`'s R2. R2 refuses a SELF-MARK (plane A
#       carrying TO_A). Cutting a loop in half produces a perfectly well-formed
#       mark whose partner is simply absent, which R2 cannot see and neither can
#       anything else that existed before this function.
#   C2  the act's attr set is over `AttrSet.CAP`. This is §3.5's cap arriving as a
#       refusal instead of a paragraph, and it is the number the design says decides
#       whether a set of marquees is bakeable at all.
#   C3  the act interns a height profile `rotate_profile` will not rotate. LEFT
#       RAISING ON PURPOSE — see the note at `check_rotatable`.

class ClipCollisionError(ClipBakeError):
    """A clip act whose COLLISION this bake will not emit."""


def crossover_marks(plane_words):
    """Cell indices carrying a crossover, per the encoding's own field position."""
    x = (plane_words >> collision_pipeline.XOVER_SHIFT) & collision_pipeline.XOVER_MASK
    return x != 0


def check_severed_crossovers(act, donor_root, log=None):
    """C1. Returns the per-clip mark census whether or not it refuses.

    A clip is refused when its SOURCE RECTANGLE contains at least one crossover
    mark and its source ZONE contains at least one outside that rectangle.

    WHY THAT RULE AND NOT A SHARPER ONE. A crossover is a per-plane pair at ONE
    cell (`tools/collision_xover_census.py`'s pairing is "same cell index, marked on
    both planes" — 8 paired indices in the shipped act), and a rectangle cut can
    never split THAT: both planes are clipped by the same rectangle. What a cut
    really breaks is the loop's OTHER crossing — act 1's marks sit in two bands of
    one column, the §3.3 bottom-centre and top-centre — and nothing in the encoding
    says those two bands belong to one loop. So the only sound rule is the
    conservative one, and its false positive (a clip that leaves an UNRELATED loop
    behind) is exactly what the opt-out is for.

    STRUCTURALLY VACUOUS ON TODAY'S DATA, and that is stated rather than discovered:
    a converted Sonic 2 tree carries XOVER_NONE in every cell, because the donor
    chunk word has no crossover field at all (its bits 15:14 are path-B solidity).
    This guards the path that opens the moment an author paints a mark onto a donor
    tree in aurora. `tools/test_s2_clip_collision.py` proves it fires by painting
    one.
    """
    rows = []
    for cl in act.clips:
        zm = clip_manifest._zone_manifest(cl, donor_root)
        d = cl.tree_dir(donor_root)
        st = act.section_tiles
        inside = outside = 0
        for suffix in ("collattr", "collattrb"):
            g = clip_manifest.section_plane_grid(d, zm, st, suffix)
            marked = crossover_marks(g)
            sx, sy, sw, sh = (v // clip_manifest.TILE_PX for v in cl.src)
            sub = marked[sy:sy + sh, sx:sx + sw]
            inside += int(sub.sum())
            outside += int(marked.sum()) - int(sub.sum())
        rows.append({"clip": cl.id, "zone": "/".join(cl.tree_key),
                     "marks_inside_src": inside, "marks_outside_src": outside,
                     "severed_xover_reason": cl.severed_xover_reason})
        if inside and outside and not cl.severed_xover_reason:
            raise ClipCollisionError(
                f"C1 clip {cl.id!r}: its source rectangle takes {inside} crossover "
                f"mark(s) from {'/'.join(cl.tree_key)} and leaves {outside} behind. A "
                f"crossover sends the player to the other collision plane and something "
                f"else has to send them back (docs/LOOP_CROSSOVER_ENCODING.md §3.3); a "
                f"marquee that keeps one end of a loop and drops the other produces a "
                f"one-way trip onto a plane whose geometry is not there. The encoding "
                f"does NOT record which marks belong to one loop, so this refusal cannot "
                f"tell a severed loop from two unrelated ones and errs toward refusing. "
                f"If you know the ones left behind are a different loop, say so in "
                f"\"severed_xover_reason\" on this clip and it will be carried into "
                f"clipact.json.", [clip_manifest.subject("clip", cl.index, cl.id)])
        if inside and outside and log:
            log(f"  C1 OPT-OUT clip {cl.id!r}: {inside} mark(s) taken, {outside} left "
                f"behind — {cl.severed_xover_reason}")
    return rows


def check_rotatable(attrset):
    """C3. Every interned profile must survive `collision_pipeline.rotate_profile`.

    THE DECISION ROW 4 HANDED ROW 5, and it is to keep the refusal. `emit_tables`
    rotates every attr-set entry to build `heightmaps_rot.bin`, and it calls the
    UNRULED `rotate_profile`, which RAISES on a row whose solid span touches neither
    edge — S2 shape `$18` and its flips are the only such shapes in either bank.
    Row 4 ruled `$18` for the BANK (keep the run's width, anchor it RIGHT) inside
    `tools/import_s2_collision.py`, and that ruling deliberately does not reach
    `emit_tables`.

    IT STILL DOES NOT, and this function does not change that. What it changes is
    WHEN the author hears about it. Turning the raise into a value on the shipping
    act's path is a change to how every act in the repo is baked, made to serve one
    clip act that does not exist yet, and `$18` is referenced by NO showcase zone —
    so the cost of leaving it raising is zero today and the cost of silencing it is
    every future act. What was actually wrong was the DISTANCE: the author marquees
    a rectangle in aurora and finds out at the ROM bake, in a traceback from a
    function four layers down that names a height profile and no clip. So the same
    condition is now detected here, by name, against the clip that caused it, before
    a single byte is emitted — and when row 6 or later genuinely needs `$18` in a
    shipping act, the argument for `rotate_profile_ruled` will be made against a
    real clip instead of a hypothetical one.
    """
    bad = []
    for idx, (heights, _angle, _sol, _xover) in enumerate(attrset.entries):
        try:
            collision_pipeline.rotate_profile(heights)
        except ValueError as exc:
            bad.append((idx, list(heights), str(exc)))
    if bad:
        detail = "; ".join(f"attr {i} heights={h} ({m})" for i, h, m in bad[:4])
        raise ClipCollisionError(
            f"C3 this act interns {len(bad)} height profile(s) that "
            f"collision_pipeline.rotate_profile REFUSES, so the ROM's wall-probe table "
            f"(heightmaps_rot.bin, emit_tables) cannot be built for it: {detail}. In the "
            f"S2 bank the only shape like this is $18, a symmetric 45-degree peak whose "
            f"upper rows have a solid run touching neither edge — one signed byte per row "
            f"cannot say that. tools/import_s2_collision.py RULED it for the bank (keep "
            f"the run's width, anchor RIGHT) but that ruling deliberately does not reach "
            f"emit_tables, because turning a build refusal into a silent value on every "
            f"act's path is not a change to make for a clip. Marquee around the shape, or "
            f"make the case for rotate_profile_ruled in emit_tables with this clip as the "
            f"evidence.")


def collision(act, st, donor_root=None, log=None):
    """Compose both collision planes, count the attr set, and run C1-C3.

    Returns everything `emit` and the readout need. The count is taken with the cap
    LIFTED (`AttrSet(cap=None)`) so an act that does not fit can be told how far
    over it is — the §8 readout the author needs is "you need 278", not "it
    overflowed" — and C2 then compares against `AttrSet.CAP`.
    """
    donor_root = clip_manifest._root(donor_root)
    marks = check_severed_crossovers(act, donor_root, log=log)
    bank_dir = clip_manifest.collision_banks(act, donor_root)
    profiles, angles = ojz_strip_gen.load_base_bank(bank_dir)
    plane_a, plane_b = clip_manifest.collision_grids(act, donor_root)

    attrset = collision_pipeline.AttrSet(cap=None)
    per_clip = []
    for cl, mrow in zip(act.clips, marks):
        before = len(attrset.entries)
        dx, dy = (v // clip_manifest.TILE_PX for v in cl.dst[:2])
        sw, sh = (v // clip_manifest.TILE_PX for v in cl.src[2:])
        alone = collision_pipeline.AttrSet(cap=None)
        for plane in (plane_a, plane_b):
            sub = plane[dy:dy + sh, dx:dx + sw]
            for w in np.unique(sub).tolist():
                collision_pipeline.bake_plane_cell(int(w), profiles, angles, attrset)
                collision_pipeline.bake_plane_cell(int(w), profiles, angles, alone)
        per_clip.append(dict(
            mrow,
            attr_entries_alone=len(alone.entries) - 1,
            attr_entries_added=len(attrset.entries) - before,
            solid_cells=int(sum(
                np.count_nonzero((plane[dy:dy + sh, dx:dx + sw]
                                  >> collision_pipeline.PLANE_SOL_SHIFT) & 3)
                for plane in (plane_a, plane_b))),
        ))

    # cells no clip covers are word 0 = air on both planes and intern to nothing,
    # but bake them anyway so the count is over the ACT and not over the clips
    for plane in (plane_a, plane_b):
        for w in np.unique(plane).tolist():
            collision_pipeline.bake_plane_cell(int(w), profiles, angles, attrset)

    check_rotatable(attrset)
    n = len(attrset.entries) - 1
    cap = collision_pipeline.AttrSet.CAP
    if n > cap:
        worst = max(per_clip, key=lambda r: r["attr_entries_alone"])
        raise ClipCollisionError(
            f"C2 this act needs {n} collision attr-set entries and the cap is {cap} "
            f"(collision_pipeline.AttrSet.CAP — one byte per cell, index 0 reserved for "
            f"air). Over by {n - cap}. Per clip, standing alone: "
            + ", ".join(f"{r['clip']} {r['attr_entries_alone']}" for r in per_clip)
            + f". The most expensive is {worst['clip']!r} at "
            f"{worst['attr_entries_alone']}. This is the design's §3.5 cap, the one "
            f"budget of this act that a bigger ROM cannot buy out of: clip harder, or "
            f"take the ruling §9.3 asks for (merge near-identical shapes, widen the attr "
            f"field to a word, or give each region its own bank).")
    if log:
        log(f"  collision: {n} attr-set entries of {cap} "
            f"({100 * n / cap:.0f}% of the act-wide cap), bank "
            f"{os.path.relpath(bank_dir, REPO)}")
        for r in per_clip:
            log(f"    {r['clip']}: {r['attr_entries_alone']} entries alone, "
                f"{r['attr_entries_added']} added here, {r['solid_cells']} solid cells, "
                f"{r['marks_inside_src']} crossover mark(s)")
    return {"plane_a": plane_a, "plane_b": plane_b, "attrset": attrset,
            "entries": n, "cap": cap, "bank_dir": bank_dir, "per_clip": per_clip}


def emit_collision(act, coll, out_dir):
    """Write both plane files per section and return the manifest block."""
    sect = act.section_tiles
    rows = []
    for s_idx in range(act.grid_w * act.grid_h):
        sy, sx = divmod(s_idx, act.grid_w)
        r0, c0 = sy * sect, sx * sect
        row = {"n": s_idx}
        for plane, suffix in ((coll["plane_a"], "collattr"), (coll["plane_b"], "collattrb")):
            sub = plane[r0:r0 + sect, c0:c0 + sect].astype(">u2")
            data = sub.tobytes()
            with open(os.path.join(out_dir, f"section_{s_idx}.{suffix}.bin"), "wb") as fh:
                fh.write(data)
            row[f"{suffix}_sha256"] = hashlib.sha256(data).hexdigest()
            row[f"{suffix}_solid_cells"] = int(np.count_nonzero(
                (np.asarray(sub, dtype=np.uint16)
                 >> collision_pipeline.PLANE_SOL_SHIFT) & 3))
        rows.append(row)
    return {
        "attr_entries": coll["entries"],
        "cap": coll["cap"],
        "base_bank": os.path.relpath(coll["bank_dir"], REPO),
        "format": "aurora per-plane cell word, big-endian u16 (see "
                  "tools/collision_pipeline.chunk_entry_to_plane_words)",
        "per_clip": coll["per_clip"],
        "sections": rows,
    }


def recount_collision(act, out_dir, bank_dir):
    """The act's attr-set size, decoded back OFF DISK. The N2 of the collision half.

    Deliberately not `collision()`'s number: that one counts the in-memory grids, this
    one re-reads the emitted plane files, so a disagreement is the emission.
    """
    profiles, angles = ojz_strip_gen.load_base_bank(bank_dir)
    attrset = collision_pipeline.AttrSet(cap=None)
    sect = act.section_tiles
    for s_idx in range(act.grid_w * act.grid_h):
        for suffix in ("collattr", "collattrb"):
            p = os.path.join(out_dir, f"section_{s_idx}.{suffix}.bin")
            with open(p, "rb") as fh:
                data = fh.read()
            want = sect * sect * 2
            if len(data) != want:
                raise ClipCollisionError(f"{p}: {len(data)} bytes, expected {want}")
            g = np.frombuffer(data, dtype=">u2")
            for w in np.unique(g).tolist():
                collision_pipeline.bake_plane_cell(int(w), profiles, angles, attrset)
    return len(attrset.entries) - 1


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def bake(manifest_path, out_dir=None, expect_worst=None,
         donor_root=None, log=print, warning_records=None, refuse_budget=True):
    """Bake the act. Raises ClipManifestError / ClipBakeError on a refusal.

    `warning_records` is handed to `clip_manifest.load` (the `--json` warnings list).
    `refuse_budget=False` skips ONLY the final `fpo.refuse_over_budget` call, which refuses
    by raising SystemExit (it is fg_page_order's, shared with the OJZ generator). The
    `--json` mode takes that one decision itself, from the verdict this returns, so it can
    report it as a refusal without catching SystemExit around the whole bake. It is the
    last statement, so skipping it changes nothing that runs before it."""
    donor_root = clip_manifest._root(donor_root)
    act = clip_manifest.load(manifest_path, donor_root=donor_root,
                             warn=(lambda m: log(f"  WARNING: {m}")) if log else None,
                             warning_records=warning_records)
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), "baked")
    if log:
        log(f"clip act: {act.summary()}")
    st = place(act, donor_root, log=log)
    pl = st["placement"]
    n_checked = verify_art_fidelity(st)
    if log:
        log(f"  art fidelity: {n_checked} (zone, tile) pair(s) resolve to their own zone's art")
    coll = collision(act, st, donor_root, log=log)
    manifest = emit(act, st, out_dir, donor_root)
    if log:
        z = manifest["zone_separation"]
        log(f"  Z1 zone separation: {z['mixed']} of {z['windows']} camera windows "
            f"({z['window_cells'][0]}x{z['window_cells'][1]} cells) hold two donor zones; "
            f"{z['donor_zones']} donor zone(s), narrowest column gap between two zones "
            f"{z['min_column_gap_cells']} cell(s)"
            + (f" — FIRST MIXED window at tile ({z['first_mixed']['left_tile']}, "
               f"{z['first_mixed']['top_tile']})" if z["mixed"] else ""))
    manifest["collision"] = emit_collision(act, coll, out_dir)
    n2_coll = recount_collision(act, out_dir, coll["bank_dir"])
    if n2_coll != coll["entries"]:
        raise ClipCollisionError(
            f"the emitted collision planes do not re-count as they were composed: "
            f"{coll['entries']} attr-set entries in memory, {n2_coll} decoded back off "
            f"disk. The interning is the same code either way, so this is the emission.")
    manifest["collision"]["attr_entries_at_recount"] = n2_coll
    if log:
        log(f"  collision recount off disk: {n2_coll} attr-set entries")
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
    if refuse_budget:
        fpo.refuse_over_budget(v1, f"clip act {act.id}")
    return act, st, manifest, v1, v2


#: `bake --json` document schema. The SHAPE is `clip_manifest.py validate --json`'s
#: (VALIDATE_JSON_SCHEMA 1); this number is bumped on its own, on any change a vendored
#: reader of THIS document could notice.
BAKE_JSON_SCHEMA = 1

#: The rule tag of the FG page-budget refusal. Every other tag is read back from its
#: message's leading token; this one cannot be, because the sentence is
#: `fg_page_order.refuse_over_budget`'s (shared with the OJZ generator) and the human mode
#: prints it unchanged. So the tag is named here, once.
BUDGET_RULE = "FG_PAGE_BUDGET"
#: What `refuse_over_budget`'s sentence starts with. The human mode prints it whole on
#: stderr; the `--json` message is the rest of it, as validate's message is the rest of
#: "clips.json REFUSED — ".
_BUDGET_PREFIX = "REFUSED — "


def budget_refusal(v, act):
    """The FG page-budget refusal as a `--json` refusal entry, or None when the act fits.

    Asks `fpo.refuse_over_budget` itself, the call the human mode makes, so the verdict and
    the sentence are that function's and nothing is restated. Only its own SystemExit is
    caught, and only around that one call."""
    try:
        fpo.refuse_over_budget(v, f"clip act {act.id}")
    except SystemExit as exc:
        msg = str(exc.code)
        if msg.startswith(_BUDGET_PREFIX):
            msg = msg[len(_BUDGET_PREFIX):]
        return {"rule": BUDGET_RULE, "subjects": [], "message": msg}
    return None


def bake_json(manifest_path, out_dir=None, expect_worst=None, donor_root=None):
    """(the `bake --json` document, exit code). See "--json" in the module header.

    A refusal is exactly what the human mode reports as REFUSED: a ClipManifestError or a
    ClipBakeError (stdout "clip act REFUSED — ..."), or the FG page budget (stderr
    "REFUSED — FG page budget: ..."). Anything else propagates, as it does in the human
    mode, and is a crash."""
    warnings = []
    doc = {"schema": BAKE_JSON_SCHEMA, "ok": False, "refusals": [], "warnings": warnings}
    try:
        act, _st, _m, v1, _v2 = bake(manifest_path, out_dir, expect_worst,
                                     donor_root=donor_root, log=None,
                                     warning_records=warnings, refuse_budget=False)
    except (clip_manifest.ClipManifestError, ClipBakeError) as exc:
        doc["refusals"].append(clip_manifest.refusal_record(exc))
        return doc, 1
    over = budget_refusal(v1, act)
    if over is not None:
        doc["refusals"].append(over)
        return doc, 1
    doc["ok"] = True
    return doc, 0


def _mode_bake(rest):
    if not rest:
        print(USAGE)
        return 1
    path, out_dir, expect, as_json = rest[0], None, None, False
    extra = rest[1:]
    while extra:
        if extra[0] == "--out" and len(extra) > 1:
            out_dir, extra = extra[1], extra[2:]
        elif extra[0] == "--expect-worst" and len(extra) > 1:
            expect, extra = int(extra[1]), extra[2:]
        elif extra[0] == "--json":
            as_json, extra = True, extra[1:]
        else:
            print(f"ERROR: unknown argument {extra[0]!r}")
            print(USAGE)
            return 1
    if as_json:
        doc, rc = bake_json(path, out_dir, expect)
        print(clip_manifest.json_text(doc))
        return rc
    t0 = time.time()
    try:
        _act, _st, m, v1, _v2 = bake(path, out_dir, expect)
    except (clip_manifest.ClipManifestError, ClipBakeError) as exc:
        print(f"clip act REFUSED — {exc}")
        return 1
    print(f"clip act baked: {m['pool']['tiles']} pool tiles in {m['pool']['pages']} pages, "
          f"rung {m['placement']['rung']}, worst window {v1['worst']} of {v1['frames']}, "
          f"{v1['over']} over budget; {m['collision']['attr_entries']} collision attr-set "
          f"entries of {m['collision']['cap']}; {time.time() - t0:.2f} s")
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


ALIGN_CLIPS = ("s2disasm", "EHZ", "s2disasm", "CPZ")


#: (label, clip A dst x, clip B dst x) for measure-alignment, in a 2x1-section act with two
#: 1024x1024 clips of two different zones. Row 2 is the CONTROL for row 3: the two clips
#: touch in both, so "a camera window can hold both zones" is held fixed and the only
#: thing that varies is whether the section boundary falls between them. Row 1 is the
#: separated case, kept to show how much of row 3's cost is adjacency rather than mixing.
ALIGN_ROWS = (
    ("separated, one zone per section", 0, 2048),
    ("adjacent,  one zone per section", 1024, 2048),
    ("adjacent,  both in section 0", 0, 1024),
)


def _mode_measure_alignment(rest):
    """The measurement behind clip_manifest's R11 and W3, from the code the bake uses."""
    if rest:
        print(USAGE)
        return 1
    import tempfile
    rows = []
    for label, ax, bx in ALIGN_ROWS:
        doc = {"schema": 1, "units": "world_px", "id": "align_probe",
               "act": {"grid_w": 2, "grid_h": 1},
               "clips": [
                   {"id": "a", "donor": ALIGN_CLIPS[0], "zone": ALIGN_CLIPS[1],
                    "src_rect": {"x": 4096, "y": 0, "w": 1024, "h": 1024},
                    "dst_rect": {"x": ax, "y": 0, "w": 1024, "h": 1024},
                    "unaligned_dst_reason": "alignment measurement probe"},
                   {"id": "b", "donor": ALIGN_CLIPS[2], "zone": ALIGN_CLIPS[3],
                    "src_rect": {"x": 4096, "y": 0, "w": 1024, "h": 1024},
                    "dst_rect": {"x": bx, "y": 0, "w": 1024, "h": 1024},
                    "unaligned_dst_reason": "alignment measurement probe"}]}
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "clips.json")
            with open(p, "w") as fh:
                json.dump(doc, fh)
            try:
                act = _load_probe(p)
            except clip_manifest.ClipManifestError as exc:
                print(f"measure-alignment UNMEASURABLE — {exc}")
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


def _load_probe(path):
    """`clip_manifest.load` for the alignment probe.

    The mixed placement it measures is a WARNING (W3), not a refusal, and the offset
    placements carry the in-file `unaligned_dst_reason` R11 asks for, so this is the
    ordinary loader. It exists as its own name because the probe manifests are built here
    rather than tracked, and the tests share it.
    """
    return clip_manifest.load(path, warn=None)


USAGE = """Usage:
    python3 tools/clip_act_bake.py bake <clips.json> [--out DIR] [--expect-worst N]
    python3 tools/clip_act_bake.py recount <baked DIR>
    python3 tools/clip_act_bake.py measure-alignment"""

MODES = {"bake": _mode_bake, "recount": _mode_recount, "measure-alignment": _mode_measure_alignment}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(USAGE)
        sys.exit(1)
    return handler(args[1:])


if __name__ == "__main__":
    sys.exit(main())
