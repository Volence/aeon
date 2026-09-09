#!/usr/bin/env python3
"""fg_working_set.py — how much of the FG art pool does a SCREEN actually need?

THIS IS A MEASUREMENT OVER BAKED DATA, NOT AN OBSERVATION OF THE RUNNING ENGINE.
=============================================================================
Read this paragraph before quoting any number this tool prints.

OJZ act 1 bakes 10 pool pages against `PAGE_FRAMES` = 12 frames, so
`Level_LoadArt` bulk-loads every page at level init and latches
`PageCache_Direct_Map`. Nothing is ever evicted or paged at runtime in any
shipped build: steady-state streaming has NEVER RUN on a shipped act. So the
peak this tool reports is not "what the engine was seen to hold" — it is what a
SMALLER cache WOULD have to hold, computed from the same bytes the engine
reads. A reader who takes it as a recording of running behaviour is wrong.

It is also a ONE-ACT measurement of a SMALL, MOSTLY-AIR act whose six of nine
sections were cloned from section 0 (see `act_descriptor.emp`'s grid comment).
`--json` reports `limits` with the per-section air fraction and page-set
overlap so the reader can see how uniform the subject is.

WHAT IT COMPUTES
----------------
1. PEAK WORKING SET — over every camera placement the act allows, the maximum
   number of DISTINCT pool pages referenced by the nametable words inside a
   window. Three windows, all derived from engine constants, never typed in:
     * `visible`     the screen itself (worst-case sub-tile alignment)
     * `plane_fill`  what `Section_Update*` writes into the VDP plane
     * `tile_cache`  the 80x60 staging cache — THE ENGINE'S OWN RESIDENCY
                     WINDOW: `pf_refcount` counts nametable words in the TILE
                     CACHE (engine/level/page_cache.emp header), so this, not
                     the screen, is what a frame must survive.
2. LOOKAHEAD SWEEP — the same peak with the window extended by L columns in
   the direction of travel, L swept over a range. Reported as a CURVE; the
   tool does not pick one L for you, it prints the derivation inputs beside it.
2b. TILE-CACHE MARGIN LEVER — the residency window is the tile cache, and the
   cache is margin + reach. `constants.emp` fixes the smallest legal cache at
   each margin, so sweeping the margin down traces the residency requirement
   to its floor (the plane-fill window) and prices the margin in PAGES.
3. RE-ENTRY FREQUENCY — an LRU simulation over every traverse of the act, on
   BOTH axes: for a cache of F frames, how often does an evicted page get
   referenced again, per 1000 px of camera travel. This prices the owner's own
   proposal — keep decompressed pages in work RAM so a re-entry costs a 2 KB
   DMA instead of a second decode. Vertical churn runs ~2x horizontal here, so
   a horizontal-only figure would have understated it.
4. THE BUDGET, per candidate PAGE_FRAMES: the worst single traverse's page-in
   rate scaled by the camera cap, against idle CPU and DMA_BUDGET_NTSC.

Usage:
    python3 tools/fg_working_set.py report            # human-readable
    python3 tools/fg_working_set.py report --json out.json
    python3 tools/fg_working_set.py --help

Every constant is derived from the tree. `--json` carries a `constants` block
naming the file each one came from, so a stale copy in prose can be caught by
diffing against the tool's own output.
"""

import argparse
import json
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")
CAMERA_EMP = os.path.join(REPO, "engine", "level", "camera.emp")
ACT_DESCRIPTOR_EMP = os.path.join(
    REPO, "games", "sonic4", "data", "levels", "ojz", "act1", "act_descriptor.emp")
GEN_DIR = os.path.join(
    REPO, "games", "sonic4", "data", "generated", "ojz", "act1")
VRAM_MAP_DOC = os.path.join(REPO, "docs", "generated", "vram-map-sonic4.md")

BLOCKS_PER_SECTION_AXIS = 16      # cross-checked against constants.emp below
BLOCK_INDEX_SIZE = 1024           # ditto (BLOCKS_PER_SECTION * 4)


# ---------------------------------------------------------------------------
# Constant derivation — parse the engine's own `.emp`, never restate a value
# ---------------------------------------------------------------------------

_CONST_RE = re.compile(r"^\s*(?:pub\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")


def _strip_comment(text):
    # `.emp` line comments are `//`. No string literals appear in the const
    # expressions we parse, so a plain split is sufficient and total.
    return text.split("//", 1)[0].strip()


def _to_python_expr(expr):
    """Rewrite an `.emp` integer expression into Python.

    `$FF` -> `0xFF`, `/` -> `//` (the `.emp` consts we read are integer
    division by construction — every one is asserted exact by an `ensure`
    beside its definition).
    """
    expr = re.sub(r"\$([0-9A-Fa-f]+)", lambda m: str(int(m.group(1), 16)), expr)
    expr = re.sub(r"(?<![/])/(?![/])", "//", expr)
    return expr


class ConstantSource:
    """Every constant the model uses, with the file it was read from.

    A name is resolved ONCE, by evaluating its `.emp` right-hand side against
    the constants already resolved. Anything the expression needs and cannot
    find is a loud failure, never a default.
    """

    def __init__(self):
        self.values = {}
        self.origin = {}
        self._raw = {}

    def load_file(self, path):
        with open(path, "r") as fh:
            for line in fh:
                m = _CONST_RE.match(_strip_comment(line))
                if not m:
                    continue
                name, expr = m.group(1), m.group(2).rstrip(",")
                # first definition wins; a name is defined once per tree
                self._raw.setdefault(name, (expr, path))

    def get(self, name):
        if name in self.values:
            return self.values[name]
        if name not in self._raw:
            raise KeyError(
                f"constant {name!r} not found in any loaded .emp source — the "
                f"model cannot be grounded; do NOT substitute a literal")
        expr, path = self._raw[name]
        py = _to_python_expr(expr)
        env = {}
        for ident in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", py)):
            env[ident] = self.get(ident)
        try:
            val = eval(py, {"__builtins__": {}}, env)  # noqa: S307 - closed env
        except Exception as exc:                        # pragma: no cover
            raise ValueError(
                f"constant {name} = {expr!r} ({path}) did not evaluate: {exc}")
        if not isinstance(val, int):
            raise ValueError(f"constant {name} is not an int: {val!r}")
        self.values[name] = val
        self.origin[name] = os.path.relpath(path, REPO)
        return val


def load_constants():
    src = ConstantSource()
    src.load_file(CONSTANTS_EMP)
    src.load_file(CAMERA_EMP)          # CAM_MAX_X_STEP is file-local there
    src.load_file(ACT_DESCRIPTOR_EMP)  # GRID_W / GRID_H
    return src


NEEDED = [
    # geometry
    "SCREEN_WIDTH", "SCREEN_HEIGHT",
    "SCREEN_LAST_COL_MAX", "SCREEN_LAST_ROW_MAX",
    "SECTION_H_REACH_COLS_MAX", "SECTION_V_REACH_ROWS_MAX",
    "TILE_CACHE_COLS", "TILE_CACHE_ROWS",
    "TILE_CACHE_MARGIN_H", "TILE_CACHE_MARGIN_V",
    "SECTION_SIZE", "SECTION_SIZE_SHIFT",
    "BLOCK_TILE_SIZE", "BLOCK_NT_SIZE",
    "BLOCKS_PER_SECTION_AXIS", "BLOCK_INDEX_ENTRIES",
    # pool / residency
    "ART_POOL_PAGE_TILES", "PAGE_FRAME_TILE_SHIFT",
    "POOL_TILE_CEILING", "PAGE_FRAMES", "PAGE_FRAMES_MAX",
    "PAGE_PREFETCH_MAX", "NT_TILE_MASK",
    # motion
    "CAM_MAX_X_STEP", "CAM_MAX_Y_STEP",
    # act shape
    "GRID_W", "GRID_H",
]


class Model:
    """The derived geometry, all of it traceable to a source file."""

    def __init__(self, src=None):
        self.src = src or load_constants()
        c = {n: self.src.get(n) for n in NEEDED}
        self.c = c

        # The engine asserts `1 << PAGE_FRAME_TILE_SHIFT == ART_POOL_PAGE_TILES`
        # at its definition; re-derive rather than trust either alone.
        if (1 << c["PAGE_FRAME_TILE_SHIFT"]) != c["ART_POOL_PAGE_TILES"]:
            raise ValueError("PAGE_FRAME_TILE_SHIFT disagrees with ART_POOL_PAGE_TILES")
        if c["PAGE_FRAMES"] * c["ART_POOL_PAGE_TILES"] != c["POOL_TILE_CEILING"]:
            raise ValueError("PAGE_FRAMES does not tile POOL_TILE_CEILING")
        if c["BLOCKS_PER_SECTION_AXIS"] != BLOCKS_PER_SECTION_AXIS:
            raise ValueError("blocks-per-section axis moved; the blob parser assumes 16")
        if c["BLOCK_INDEX_ENTRIES"] * 4 != BLOCK_INDEX_SIZE:
            raise ValueError("block index table size moved")

        self.page_tiles = c["ART_POOL_PAGE_TILES"]
        self.page_shift = c["PAGE_FRAME_TILE_SHIFT"]
        self.nt_tile_mask = c["NT_TILE_MASK"]

        # tiles per section axis = SECTION_SIZE world px / 8 px per tile
        self.section_tiles = c["SECTION_SIZE"] >> 3
        self.grid_w, self.grid_h = c["GRID_W"], c["GRID_H"]
        self.act_cols = self.grid_w * self.section_tiles
        self.act_rows = self.grid_h * self.section_tiles

        # ---- windows, every dimension derived ----
        # visible, worst sub-tile alignment: the last visible column index the
        # engine itself computes, +1 to turn an index into a count.
        self.win_visible = (c["SCREEN_LAST_COL_MAX"] + 1,
                            c["SCREEN_LAST_ROW_MAX"] + 1)
        # visible, exact tile alignment (camera_x % 8 == 0)
        self.win_visible_aligned = (c["SCREEN_WIDTH"] >> 3, c["SCREEN_HEIGHT"] >> 3)
        # what the plane fill actually writes (the engine's own reach constants)
        self.win_plane_fill = (c["SECTION_H_REACH_COLS_MAX"] + 1,
                               c["SECTION_V_REACH_ROWS_MAX"] + 1)
        # the residency window the refcount invariant is stated over
        self.win_tile_cache = (c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"])

        # camera step cap, px/frame -> tiles/frame
        self.cam_step_px = max(c["CAM_MAX_X_STEP"], c["CAM_MAX_Y_STEP"])

    def windows(self):
        return {
            "visible": self.win_visible,
            "visible_tile_aligned": self.win_visible_aligned,
            "plane_fill": self.win_plane_fill,
            "tile_cache": self.win_tile_cache,
        }

    def constants_json(self):
        return {n: {"value": self.c[n], "source": self.src.origin[n]}
                for n in sorted(self.c)}


# ---------------------------------------------------------------------------
# Baked data — decode the SHIPPED blobs (sec{N}_blocks.bin), not the strips
# ---------------------------------------------------------------------------
#
# sec{N}_strips_a.bin is an intermediate: nothing embeds it. What the ROM
# carries is sec{N}_blocks.bin (S4LZ block index + dict, per
# generated/.../sec_block_blobs.emp) plus sec{N}_local_map.bin. Measuring the
# strips would measure a file the engine never reads.

_DICT_LEN_RE = re.compile(
    r"^\s*pub\s+const\s+OJZ_SEC(\d+)_BLOCK_DICT_LEN\s*=\s*(\d+)\s*$")


def load_dict_lens():
    lens = {}
    path = os.path.join(GEN_DIR, "sec_block_dicts.emp")
    with open(path, "r") as fh:
        for line in fh:
            m = _DICT_LEN_RE.match(_strip_comment(line))
            if m:
                lens[int(m.group(1))] = int(m.group(2))
    if not lens:
        raise ValueError(f"no OJZ_SEC*_BLOCK_DICT_LEN found in {path}")
    return lens


def load_page_grid(model):
    """Decode every section into one act-wide grid of pool-page ids.

    grid[row][col] = page id, or -1 where the cell references no pool page
    (an air block, or a nametable word whose global slot is 0 — the blank
    tile, which `PageCache` skips before it ever computes a page: see
    page_cache.emp `.sb_loop`, `beq .sb_next // global 0 = blank -> no page`).
    """
    import ojz_block_gen as blockgen

    dict_lens = load_dict_lens()
    n_sections = model.grid_w * model.grid_h
    st = model.section_tiles
    bt = model.c["BLOCK_TILE_SIZE"]
    bpa = model.c["BLOCKS_PER_SECTION_AXIS"]
    words_per_block = model.c["BLOCK_NT_SIZE"] // 2

    grid = [[-1] * model.act_cols for _ in range(model.act_rows)]
    per_section = {}
    air_blocks = {}

    for sec in range(n_sections):
        blob_path = os.path.join(GEN_DIR, f"sec{sec}_blocks.bin")
        lmap_path = os.path.join(GEN_DIR, f"sec{sec}_local_map.bin")
        with open(blob_path, "rb") as fh:
            blob = fh.read()
        with open(lmap_path, "rb") as fh:
            raw = fh.read()
        lmap = struct.unpack(f">{len(raw) // 2}H", raw)
        if lmap[0] != 0:
            raise ValueError(
                f"sec{sec} local map violates the blank-first invariant "
                f"(map[0] == {lmap[0]}, expected 0)")

        sec_x, sec_y = sec % model.grid_w, sec // model.grid_w
        base_col, base_row = sec_x * st, sec_y * st
        pages = set()
        air = 0

        for bi in range(bpa * bpa):
            decoded = blockgen.decode_block(blob, dict_lens[sec], bi)
            if decoded is None:
                air += 1
                continue
            nt = struct.unpack(f">{words_per_block}H", decoded[:words_per_block * 2])
            bx, by = bi % bpa, bi // bpa
            for k, word in enumerate(nt):
                local = word & model.nt_tile_mask
                if local == 0:
                    continue           # local 0 IS global 0 (blank-first)
                if local >= len(lmap):
                    raise ValueError(
                        f"sec{sec} block {bi} word {k}: local index {local} "
                        f"past the {len(lmap)}-entry local map")
                glob = lmap[local]
                if glob == 0:
                    continue
                page = glob >> model.page_shift
                pages.add(page)
                r = base_row + by * bt + k // bt
                cidx = base_col + bx * bt + k % bt
                grid[r][cidx] = page
        per_section[sec] = pages
        air_blocks[sec] = air

    return grid, per_section, air_blocks


def load_pool_manifest():
    with open(os.path.join(GEN_DIR, "ojz_act_pool_manifest.json"), "r") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Rectangle page-set counting
# ---------------------------------------------------------------------------

def _integral(mask, rows, cols):
    """2D prefix sum, (rows+1) x (cols+1), plain Python lists."""
    ii = [[0] * (cols + 1) for _ in range(rows + 1)]
    for r in range(rows):
        row_src = mask[r]
        prev = ii[r]
        cur = ii[r + 1]
        run = 0
        for c in range(cols):
            run += row_src[c]
            cur[c + 1] = prev[c + 1] + run
    return ii


class PageField:
    """Per-page presence, ready for O(1) rectangle queries.

    A window's answer is carried as a BITMASK (bit p set = page p present) so
    the union with the pinned set, the popcount, and the LRU walk all read the
    same object. `page_set` (integral images) and `page_set_bruteforce`
    (direct scan) are two independent implementations of one function; the
    test suite holds them to each other on random rectangles.
    """

    def __init__(self, grid):
        self.rows = len(grid)
        self.cols = len(grid[0])
        self.grid = grid
        self.pages = sorted({v for row in grid for v in row if v >= 0})
        self.integrals = {}
        for p in self.pages:
            mask = [[1 if v == p else 0 for v in row] for row in grid]
            self.integrals[p] = _integral(mask, self.rows, self.cols)
        self._mask_cache = {}

    def page_mask(self, r0, c0, h, w):
        """Bitmask of pages present in the rectangle, by integral image."""
        m = 0
        r1, c1 = r0 + h, c0 + w
        for p, ii in self.integrals.items():
            if ii[r1][c1] - ii[r0][c1] - ii[r1][c0] + ii[r0][c0]:
                m |= 1 << p
        return m

    def page_set(self, r0, c0, h, w):
        return mask_to_set(self.page_mask(r0, c0, h, w))

    def page_set_bruteforce(self, r0, c0, h, w):
        """The same answer by direct scan — the control for `page_set`."""
        out = set()
        for r in range(r0, r0 + h):
            row = self.grid[r]
            for c in range(c0, c0 + w):
                v = row[c]
                if v >= 0:
                    out.add(v)
        return out

    def mask_field(self, w, h):
        """masks[r0][c0] = page bitmask of the w x h window at (r0, c0).

        Computed once per window shape and memoized: every consumer (peak,
        histogram, pinned union, LRU simulation) reads this one field, so they
        cannot disagree about what a placement references.
        """
        key = (w, h)
        got = self._mask_cache.get(key)
        if got is not None:
            return got
        if w > self.cols or h > self.rows:
            raise ValueError(
                f"window {w}x{h} does not fit the {self.cols}x{self.rows} act — "
                f"UNMEASURABLE, not zero")
        n_r = self.rows - h + 1
        n_c = self.cols - w + 1
        flat = [0] * (n_r * n_c)
        for p, ii in self.integrals.items():
            bit = 1 << p
            for r0 in range(n_r):
                top = ii[r0]
                bot = ii[r0 + h]
                i = r0 * n_c
                for t0, t1, b0, b1 in zip(top, top[w:], bot, bot[w:]):
                    if b1 - t1 - b0 + t0:
                        flat[i] |= bit
                    i += 1
        field = [flat[r * n_c:(r + 1) * n_c] for r in range(n_r)]
        self._mask_cache[key] = field
        return field


def mask_to_set(mask):
    out = set()
    p = 0
    while mask:
        if mask & 1:
            out.add(p)
        mask >>= 1
        p += 1
    return out


def popcount(mask):
    return bin(mask).count("1")


def sweep_stats(field, w, h, pinned_mask=0):
    """max / histogram / argmax-positions for a w x h window over the act."""
    masks = field.mask_field(w, h)
    hist = {}
    peak = -1
    peak_at = []
    peak_count = 0
    peak_pinned = 0
    peak_masks = set()
    for r0, row in enumerate(masks):
        for c0, m in enumerate(row):
            n = popcount(m)
            hist[n] = hist.get(n, 0) + 1
            wp = popcount(m | pinned_mask)
            if wp > peak_pinned:
                peak_pinned = wp
            if n > peak:
                peak, peak_at, peak_count = n, [(r0, c0)], 1
                peak_masks = {m}
            elif n == peak:
                peak_count += 1
                peak_masks.add(m)
                if len(peak_at) < 32:
                    peak_at.append((r0, c0))
    # WHERE the peak lives decides how it should be read: a peak confined to
    # one small blob is a single pathological screen (fixable by an art edit);
    # a peak spread over several regions is a broadly high floor.
    all_peak = [(r0, c0) for r0, row in enumerate(masks)
                for c0, m in enumerate(row) if popcount(m) == peak]
    if all_peak:
        rs = [r for r, _ in all_peak]
        cs = [c for _, c in all_peak]
        bbox = {"col_min": min(cs), "col_max": max(cs),
                "row_min": min(rs), "row_max": max(rs),
                "x_min": min(cs) * 8, "x_max": max(cs) * 8,
                "y_min": min(rs) * 8, "y_max": max(rs) * 8}
    else:
        bbox = None
    return {
        "window_cols": w,
        "window_rows": h,
        "placements": sum(hist.values()),
        "peak": peak,
        "peak_including_pinned": peak_pinned,
        "histogram": {str(k): hist[k] for k in sorted(hist)},
        "peak_positions_tile": [{"col": c, "row": r} for r, c in peak_at],
        "peak_positions_px": [{"x": c * 8, "y": r * 8} for r, c in peak_at],
        "peak_position_count": peak_count,
        "peak_position_bbox": bbox,
        "peak_page_sets": [sorted(mask_to_set(m)) for m in sorted(peak_masks)],
    }


# ---------------------------------------------------------------------------
# Re-entry frequency — LRU over horizontal traverses
# ---------------------------------------------------------------------------

def traverse_reentry(field, w, h, frames, pinned, honour_pinning=True,
                     axis="h"):
    """Simulate every traverse of the act along one axis.

    `axis="h"`: every horizontal traverse, one per window row.
    `axis="v"`: every vertical traverse, one per window column. Both are
    reported — a horizontal-only churn number would say nothing about the
    vertical acts this engine is built for, and silence there would read as
    "no churn" rather than "not measured".

    For each row placement the camera walks left-to-right one tile column per
    step (8 px, half the `CAM_MAX_X_STEP` cap — the finest the tile grid
    resolves). Pages the window references are touched (LRU); a page not
    resident is a PAGE-IN. A page-in whose page was evicted earlier in the same
    traverse is a RE-ENTRY — the quantity that decides whether keeping
    decompressed pages in work RAM pays.

    `honour_pinning` keeps the generator's pinned pages permanently resident,
    which is what the shipped cache does; they consume frames whether or not
    they are on screen.

    Returns aggregate counters plus per-1000px rates. A cache that cannot
    admit a page reports `unmeasurable` — never 0, never green.
    """
    masks = field.mask_field(w, h)
    if axis == "v":
        masks = [list(col) for col in zip(*masks)]
    elif axis != "h":
        raise ValueError(f"axis must be 'h' or 'v', not {axis!r}")
    pinned = set(pinned) if honour_pinning else set()
    if len(pinned) > frames:
        return {"frames": frames, "axis": axis, "unmeasurable":
                f"pinned pages ({len(pinned)}) exceed the {frames}-frame cache"}

    total_steps = total_miss = total_reentry = 0
    worst = None

    for r0, row in enumerate(masks):
        resident = list(sorted(pinned))   # LRU order, oldest first
        resident_set = set(resident)
        evicted_before = set()
        miss = reentry = 0
        prev_mask = None
        for m in row:
            total_steps += 1
            # After any column is processed every page it needs is resident, so
            # an identical mask next column is a provable no-op: same reference
            # set, all resident, and touching in the same sorted order leaves
            # the LRU order exactly where it was.
            if m == prev_mask:
                continue
            for p in sorted(mask_to_set(m)):
                if p in resident_set:
                    if p not in pinned:
                        resident.remove(p)
                        resident.append(p)
                    continue
                miss += 1
                if p in evicted_before:
                    reentry += 1
                while len(resident) >= frames:
                    victim = next((q for q in resident if q not in pinned), None)
                    if victim is None:
                        return {"frames": frames, "axis": axis, "unmeasurable":
                                "every resident frame is pinned — no eviction "
                                "candidate; the cache cannot admit the page"}
                    resident.remove(victim)
                    resident_set.discard(victim)
                    evicted_before.add(victim)
                resident.append(p)
                resident_set.add(p)
            prev_mask = m
        total_reentry += reentry
        total_miss += miss
        if worst is None or reentry > worst[1]:
            worst = (r0, reentry, miss)

    px = total_steps * 8
    return {
        "frames": frames,
        "axis": axis,
        "traverses": len(masks),
        "traverse_length_px": (len(masks[0]) * 8) if masks else 0,
        "camera_steps": total_steps,
        "camera_travel_px": px,
        "page_ins": total_miss,
        "re_entries": total_reentry,
        "re_entry_fraction_of_page_ins":
            (total_reentry / total_miss) if total_miss else None,
        "page_ins_per_1000px": 1000.0 * total_miss / px if px else None,
        "re_entries_per_1000px": 1000.0 * total_reentry / px if px else None,
        "worst_traverse": None if worst is None else {
            "traverse_index": worst[0], "re_entries": worst[1],
            "page_ins": worst[2],
            # the number the CPU/DMA budget is argued from: the worst single
            # traverse's page-ins over its own length, not the act average
            "page_ins_per_1000px": (1000.0 * worst[2] / (len(masks[0]) * 8))
                                   if masks and masks[0] else None},
    }


# ---------------------------------------------------------------------------
# Page-in latency — every input named, nothing invented
# ---------------------------------------------------------------------------
#
# The three figures below are the ONLY numbers in this tool that do not come
# out of a `.emp` const or a baked file, so they are declared here with their
# source text and echoed into `--json`. If you cannot verify one, treat the
# lookahead answer as the CURVE and not as a single distance.

LATENCY_INPUTS = {
    "zx0_page_decode_cycles": {
        "value": 45000,
        "source": "docs/ENGINE_ARCHITECTURE.md §9.7 — 'a 2 KB page ~= 45 K cycles "
                  "vs ~42.5 K average idle in a diagonal-fall window, 2026-08-05 "
                  "measurement'",
    },
    "avg_idle_cycles_per_frame": {
        "value": 42500,
        "source": "docs/ENGINE_ARCHITECTURE.md §9.7 — same 2026-08-05 measurement",
    },
    "landing_dma_frames": {
        "value": 1,
        "source": "engine/level/page_in.emp — the completed page lands as ONE "
                  "QueueDMA_Important entry, drained in the next VBlank",
    },
}


def latency_frames():
    d = LATENCY_INPUTS["zx0_page_decode_cycles"]["value"]
    i = LATENCY_INPUTS["avg_idle_cycles_per_frame"]["value"]
    decode = -(-d // i)                     # ceil: whole frames of idle
    return decode + LATENCY_INPUTS["landing_dma_frames"]["value"]


def lookahead_tiles(model):
    """Derived, not chosen: latency frames x camera cap px/frame / 8 px."""
    px = latency_frames() * model.cam_step_px
    return -(-px // 8)


# ---------------------------------------------------------------------------
# VRAM accounting — read the GENERATED map, never a remembered table
# ---------------------------------------------------------------------------

_MAP_ROW = re.compile(r"^\|\s*(\d+)-(\d+)\s*\|\s*([A-Za-z0-9_]+)\s*\|")


def vram_regions():
    rows = []
    with open(VRAM_MAP_DOC, "r") as fh:
        for line in fh:
            m = _MAP_ROW.match(line)
            if m:
                rows.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    if not rows:
        raise ValueError(f"no region rows parsed from {VRAM_MAP_DOC}")
    return rows


def vram_summary(model):
    rows = vram_regions()
    pool = [r for r in rows if r[2] == "fg_art_pool"]
    if len(pool) != 1:
        raise ValueError("expected exactly one fg_art_pool row in the VRAM map")
    lo, hi, _ = pool[0]
    pool_tiles = hi - lo + 1
    if pool_tiles != model.c["POOL_TILE_CEILING"]:
        raise ValueError(
            f"the generated VRAM map gives fg_art_pool {pool_tiles} tiles but "
            f"POOL_TILE_CEILING is {model.c['POOL_TILE_CEILING']}")
    # object/character art = the `window`-kind regions. Reported BROKEN DOWN,
    # not as one number: the kind column alone lumps shipped object art
    # (spring, character_window, ring_placeholder) with debug/test-only windows
    # and with a BG effect (waterline_strips, owner engine.bg_anim), and which
    # of those counts as "space for objects" is the reader's call, not the
    # tool's. Every row carries its owner so the split is auditable.
    windows = []
    with open(VRAM_MAP_DOC, "r") as fh:
        for line in fh:
            m = _MAP_ROW.match(line)
            if not m:
                continue
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) > 4 and parts[2] == "window":
                windows.append({
                    "name": m.group(3),
                    "tiles": int(m.group(2)) - int(m.group(1)) + 1,
                    "lifetime": parts[3],
                    "owner": parts[4],
                })
    debug_ish = [w for w in windows
                 if w["lifetime"] == "mode" or w["name"].startswith("debug_")
                 or w["name"].startswith("test_")]
    bg_owned = [w for w in windows if w["owner"].startswith("engine.bg")]
    shipped = [w for w in windows if w not in debug_ish and w not in bg_owned]
    return {"fg_art_pool_tiles": pool_tiles,
            "window_regions": windows,
            "window_tiles_total": sum(w["tiles"] for w in windows),
            "window_tiles_shipped_object_art": sum(w["tiles"] for w in shipped),
            "window_tiles_debug_or_mode_only": sum(w["tiles"] for w in debug_ish),
            "window_tiles_bg_owned": sum(w["tiles"] for w in bg_owned),
            "total_tiles": 2048,
            "source": os.path.relpath(VRAM_MAP_DOC, REPO)}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(model=None, verbose=False):
    model = model or Model()
    grid, per_section, air_blocks = load_page_grid(model)
    manifest = load_pool_manifest()
    pinned = {p["index"] for p in manifest["pages"] if p["pinned"]}
    field = PageField(grid)

    pinned_mask = 0
    for p in pinned:
        pinned_mask |= 1 << p

    wins = model.windows()
    windows_out = {}
    for name, (w, h) in wins.items():
        if verbose:
            print(f"  sweeping window {name} {w}x{h} ...", file=sys.stderr)
        windows_out[name] = sweep_stats(field, w, h, pinned_mask)

    # --- lookahead sweep, on the VISIBLE window widened in the travel direction
    #
    # Widening on the RIGHT and sweeping every placement gives the same peak
    # as widening on the left, so one sweep covers both travel directions.
    #
    # The sweep deliberately runs WELL PAST the derived lookahead distance and
    # up to the tile-cache width: a curve that only covers the region where it
    # happens to be flat cannot tell a real plateau from a broken model. Where
    # the value does move, the sweep is what shows it.
    vw, vh = model.win_visible
    la_point = lookahead_tiles(model)
    extras = sorted({0, 1, 2, 3, 4, la_point, 2 * la_point, 8, 12, 16, 20,
                     model.c["TILE_CACHE_MARGIN_H"], 24, 32,
                     model.c["TILE_CACHE_COLS"] - vw, 48, 64, 96,
                     2 * model.c["TILE_CACHE_MARGIN_H"] + 1})
    lookahead = []
    for extra in extras:
        w = vw + extra
        if extra < 0 or w > field.cols:
            continue
        if verbose:
            print(f"  lookahead +{extra} cols ...", file=sys.stderr)
        st = sweep_stats(field, w, vh, pinned_mask)
        lookahead.append({
            "lookahead_cols": extra,
            "lookahead_px": extra * 8,
            "lookahead_frames_at_cam_cap":
                round(extra * 8 / model.cam_step_px, 2),
            "window_cols": w,
            "peak": st["peak"],
            "peak_with_pinned": st["peak_including_pinned"],
        })

    # --- the tile-cache margin lever.
    #
    # The residency requirement is the TILE CACHE window, and the tile cache is
    # margin + reach, not screen. constants.emp asserts
    #   TILE_CACHE_COLS >= TILE_CACHE_MARGIN_H + SECTION_H_REACH_COLS_MAX + 1
    #   TILE_CACHE_ROWS >= TILE_CACHE_MARGIN_V + SECTION_V_REACH_ROWS_MAX + 1
    # so the SMALLEST legal cache at margin m is (m + reach + 1). Sweeping the
    # margin down to 0 traces the residency requirement to its floor — the
    # plane-fill window — and prices the margin in pages.
    pf_w, pf_h = model.win_plane_fill
    margin_sweep = []
    mh, mv = model.c["TILE_CACHE_MARGIN_H"], model.c["TILE_CACHE_MARGIN_V"]
    for frac_num in range(0, 5):
        m_h = mh * frac_num // 4
        m_v = mv * frac_num // 4
        w = pf_w + m_h
        h = pf_h + m_v
        if w > field.cols or h > field.rows:
            continue
        if verbose:
            print(f"  cache margin {m_h}/{m_v} -> {w}x{h} ...", file=sys.stderr)
        st = sweep_stats(field, w, h, pinned_mask)
        margin_sweep.append({
            "margin_h": m_h, "margin_v": m_v,
            "cache_cols": w, "cache_rows": h,
            "peak": st["peak"], "peak_with_pinned": st["peak_including_pinned"],
            "note": "smallest cache legal at this margin, per constants.emp's "
                    "TILE_CACHE_COLS/ROWS ensures",
        })
    margin_sweep.append({
        "margin_h": mh, "margin_v": mv,
        "cache_cols": model.win_tile_cache[0],
        "cache_rows": model.win_tile_cache[1],
        "peak": windows_out["tile_cache"]["peak"],
        "peak_with_pinned": windows_out["tile_cache"]["peak_including_pinned"],
        "note": "AS SHIPPED (TILE_CACHE_COLS x TILE_CACHE_ROWS)",
    })

    # --- re-entry, over candidate cache sizes.
    #
    # BOTH pinning regimes. Pinning is a GENERATOR POLICY
    # (tools/ojz_strip_gen.py PIN_SECTION_FRACTION = 0.75), not a property of
    # the art, and on this act it holds half the pool. Reporting only the
    # pinned figure would price the policy and call it the data.
    tw, th = model.win_tile_cache
    reentry = {}
    reentry_unpinned = {}
    reentry_vertical = {}
    for frames in range(2, model.c["PAGE_FRAMES"] + 1):
        if verbose:
            print(f"  re-entry, {frames} frames ...", file=sys.stderr)
        reentry[str(frames)] = traverse_reentry(field, tw, th, frames, pinned)
        reentry_unpinned[str(frames)] = traverse_reentry(
            field, tw, th, frames, pinned, honour_pinning=False)
        reentry_vertical[str(frames)] = traverse_reentry(
            field, tw, th, frames, pinned, honour_pinning=False, axis="v")

    # --- the candidate-PAGE_FRAMES table
    tc_peak = windows_out["tile_cache"]["peak"]
    tc_peak_pin = windows_out["tile_cache"]["peak_including_pinned"]
    vis_peak = windows_out["visible"]["peak"]
    table = []
    for frames in range(2, model.c["PAGE_FRAMES_MAX"] + 1):
        tiles = frames * model.page_tiles
        row = {
            "page_frames": frames,
            "pool_tiles": tiles,
            "tiles_returned_to_objects": model.c["POOL_TILE_CEILING"] - tiles,
            # a frame count below the peak cannot draw the worst screen AT ALL
            # — it is not "more churn", it is a page that must be evicted while
            # a live nametable word still references it, which the refcount
            # invariant forbids.
            "covers_tile_cache_peak_unpinned": frames >= tc_peak,
            "covers_tile_cache_peak_with_pinning": frames >= tc_peak_pin,
            "covers_visible_peak_unpinned": frames >= vis_peak,
            "pinned_pages": len(pinned),
            "free_frames_after_pinning": frames - len(pinned),
        }
        # --- the budget, computed here rather than by hand in a doc.
        #
        # WORST TRAVERSE, not the act average: an average over 709 traverses of
        # a mostly-air act is not what a frame budget is spent against. Taken as
        # the max over the two axes, unpinned (the regime a smaller cache would
        # actually run in).
        worst_rate = None
        for src in (reentry_unpinned, reentry_vertical):
            r = src.get(str(frames))
            if r and "unmeasurable" not in r:
                v = (r["worst_traverse"] or {}).get("page_ins_per_1000px")
                if v is not None:
                    worst_rate = v if worst_rate is None else max(worst_rate, v)
        if worst_rate is None:
            row["budget"] = "UNMEASURABLE at this frame count (see churn rows)"
        else:
            # 1000 px of camera travel at the CAM_MAX_*_STEP cap
            frames_per_1000px = 1000.0 / model.cam_step_px
            pages_per_frame = worst_rate / frames_per_1000px
            decode = LATENCY_INPUTS["zx0_page_decode_cycles"]["value"]
            idle = LATENCY_INPUTS["avg_idle_cycles_per_frame"]["value"]
            dma_budget = model.src.get("DMA_BUDGET_NTSC")
            page_bytes = model.src.get("ART_POOL_PAGE_BYTES")
            row["budget"] = {
                "worst_traverse_page_ins_per_1000px": round(worst_rate, 3),
                "pages_per_frame_at_camera_cap": round(pages_per_frame, 4),
                "decode_cycles_per_frame": round(pages_per_frame * decode),
                "pct_of_idle_cpu": round(100.0 * pages_per_frame * decode / idle, 1),
                "dma_bytes_per_frame": round(pages_per_frame * page_bytes, 1),
                "pct_of_dma_budget_ntsc":
                    round(100.0 * pages_per_frame * page_bytes / dma_budget, 1),
                "pct_of_admission_cap":
                    round(100.0 * pages_per_frame / model.c["PAGE_PREFETCH_MAX"], 1),
            }
        for label, table_src in (("pinned", reentry), ("unpinned", reentry_unpinned)):
            r = table_src.get(str(frames))
            if r is None:
                row[f"churn_{label}"] = "not simulated (above PAGE_FRAMES)"
            elif "unmeasurable" in r:
                row[f"churn_{label}"] = r["unmeasurable"]
            else:
                row[f"re_entries_per_1000px_{label}"] = round(
                    r["re_entries_per_1000px"], 4)
                row[f"page_ins_per_1000px_{label}"] = round(
                    r["page_ins_per_1000px"], 4)
        table.append(row)

    n_sections = model.grid_w * model.grid_h
    limits = {
        "single_act": "OJZ act 1 only",
        "act_grid": f"{model.grid_w}x{model.grid_h} sections of "
                    f"{model.section_tiles}x{model.section_tiles} tiles",
        "air_block_fraction": {
            str(s): round(air_blocks[s] / (BLOCKS_PER_SECTION_AXIS ** 2), 3)
            for s in range(n_sections)},
        "section_page_sets": {str(s): sorted(per_section[s])
                              for s in range(n_sections)},
        "sections_sharing_section0_pages": sum(
            1 for s in range(1, n_sections)
            if per_section[s] <= per_section[0] | pinned),
        "cache_regime": "VACUOUS in every shipped build: 10 pool pages vs "
                        f"PAGE_FRAMES={model.c['PAGE_FRAMES']}, so Level_LoadArt "
                        "bulk-loads all pages and latches PageCache_Direct_Map. "
                        "Nothing is ever evicted at runtime. This measurement is "
                        "over the DATA, not over observed behaviour.",
        "camera_enumeration": "every window placement inside the act rectangle, "
                              "including placements a player cannot reach — an "
                              "UPPER bound on the working set",
    }

    return {
        "subject": "OJZ act 1 foreground art pool working set",
        "constants": model.constants_json(),
        "windows": {k: {"cols": v[0], "rows": v[1]} for k, v in wins.items()},
        "pool": {
            "pages": manifest["pages"],
            "pool_tiles": manifest["pool_tiles"],
            "page_tiles": manifest["page_tiles"],
            "pinned_pages": sorted(pinned),
            "pages_referenced_anywhere": field.pages,
        },
        "vram": vram_summary(model),
        "peak_working_set": windows_out,
        "lookahead_sweep": lookahead,
        "tile_cache_margin_sweep": margin_sweep,
        "lookahead_derivation": {
            "inputs": LATENCY_INPUTS,
            "decode_frames": -(-LATENCY_INPUTS["zx0_page_decode_cycles"]["value"]
                               // LATENCY_INPUTS["avg_idle_cycles_per_frame"]["value"]),
            "total_latency_frames": latency_frames(),
            "camera_cap_px_per_frame": model.cam_step_px,
            "lookahead_tiles": lookahead_tiles(model),
            "lookahead_px": lookahead_tiles(model) * 8,
            "caveat": "the two cycle figures are cited from ARCH §9.7's "
                      "2026-08-05 measurement, not re-measured here; the "
                      "lookahead SWEEP above is the deliverable, this single "
                      "distance is one point on it",
        },
        "re_entry": reentry,
        "re_entry_unpinned": reentry_unpinned,
        "re_entry_vertical_unpinned": reentry_vertical,
        "page_frames_table": table,
        "limits": limits,
    }


def human(report):
    out = []
    a = out.append
    c = report["constants"]
    a("FG ART POOL WORKING SET — OJZ act 1")
    a("=" * 72)
    a("")
    a("!! MEASUREMENT OVER BAKED DATA, NOT AN OBSERVATION OF THE ENGINE.")
    a("   " + report["limits"]["cache_regime"])
    a("")
    a(f"Act: {report['limits']['act_grid']}")
    a(f"Pool: {report['pool']['pool_tiles']} tiles in "
      f"{len(report['pool']['pages'])} pages of {report['pool']['page_tiles']}; "
      f"pinned {report['pool']['pinned_pages']}")
    v = report["vram"]
    a(f"VRAM ({v['source']}): fg_art_pool {v['fg_art_pool_tiles']} tiles "
      f"({100*v['fg_art_pool_tiles']//v['total_tiles']}%)")
    a(f"  window regions: {v['window_tiles_total']} tiles total = "
      f"{v['window_tiles_shipped_object_art']} shipped object/character art + "
      f"{v['window_tiles_debug_or_mode_only']} debug/mode-only + "
      f"{v['window_tiles_bg_owned']} bg-owned")
    a("")
    a("1. PEAK WORKING SET (distinct pool pages a window can reference)")
    a("   'peak' = the data's own requirement. '+pinned' = frames actually")
    a("   needed once the generator's pinned pages are held resident too.")
    a(f"{'window':<22}{'size':>10}{'peak':>7}{'+pinned':>9}{'placements':>13}")
    for name, st in report["peak_working_set"].items():
        a(f"{name:<22}{str(st['window_cols']) + 'x' + str(st['window_rows']):>10}"
          f"{st['peak']:>7}{st['peak_including_pinned']:>9}{st['placements']:>13}")
    a("")
    for name, st in report["peak_working_set"].items():
        a(f"  {name} histogram (pages -> placements): " +
          ", ".join(f"{k}:{vv}" for k, vv in st["histogram"].items()))
        pos = st["peak_positions_px"][:4]
        a(f"    peak at {st['peak_position_count']} placement(s), first: " +
          ", ".join(f"(x={p['x']},y={p['y']})" for p in pos))
    a("")
    a("2. LOOKAHEAD SWEEP (visible window widened in the travel direction)")
    d = report["lookahead_derivation"]
    a(f"   derived point: {d['total_latency_frames']} frames latency x "
      f"{d['camera_cap_px_per_frame']} px/frame = {d['lookahead_px']} px "
      f"= {d['lookahead_tiles']} tiles")
    a(f"{'+cols':>7}{'+px':>7}{'frames':>9}{'peak':>7}{'+pinned':>9}")
    for row in report["lookahead_sweep"]:
        a(f"{row['lookahead_cols']:>7}{row['lookahead_px']:>7}"
          f"{row['lookahead_frames_at_cam_cap']:>9}{row['peak']:>7}"
          f"{row['peak_with_pinned']:>9}")
    a("")
    a("2b. TILE-CACHE MARGIN LEVER — the residency window is the CACHE, not")
    a("    the screen. Smallest legal cache at each margin, per constants.emp.")
    a(f"{'margin h/v':>12}{'cache':>10}{'peak':>7}{'+pinned':>9}  note")
    for row in report["tile_cache_margin_sweep"]:
        a(f"{str(row['margin_h']) + '/' + str(row['margin_v']):>12}"
          f"{str(row['cache_cols']) + 'x' + str(row['cache_rows']):>10}"
          f"{row['peak']:>7}{row['peak_with_pinned']:>9}  {row['note']}")
    a("")
    for label, key in (
            ("horizontal, pinning HONOURED (as shipped)", "re_entry"),
            ("horizontal, pinning OFF (policy lifted)", "re_entry_unpinned"),
            ("VERTICAL, pinning OFF", "re_entry_vertical_unpinned")):
        a(f"3. RE-ENTRY — {label}")
        a("   LRU over the tile-cache window, every traverse along that axis;")
        a("   'worst' is the single worst traverse, which is what a budget")
        a("   argument must use rather than the act average.")
        a(f"{'frames':>7}{'page-ins/1000px':>18}{'re-entries/1000px':>20}"
          f"{'re-entry share':>16}{'worst pi/1000px':>18}")
        for k in sorted(report[key], key=int):
            r = report[key][k]
            if "unmeasurable" in r:
                a(f"{k:>7}  UNMEASURABLE: {r['unmeasurable']}")
                continue
            frac = r["re_entry_fraction_of_page_ins"]
            worst = r["worst_traverse"] or {}
            wpi = worst.get("page_ins_per_1000px")
            a(f"{k:>7}{r['page_ins_per_1000px']:>18.3f}"
              f"{r['re_entries_per_1000px']:>20.3f}"
              f"{('n/a' if frac is None else f'{frac:.1%}'):>16}"
              f"{('n/a' if wpi is None else f'{wpi:.3f}'):>18}")
        a("")
    a("4. CANDIDATE PAGE_FRAMES")
    a("   'fits' False = the worst screen CANNOT be drawn at that frame count")
    a("   (a live nametable word would reference an evicted page), not merely")
    a("   'more churn'.")
    a(f"{'frames':>7}{'tiles':>7}{'->objects':>11}{'fits(unpin)':>13}"
      f"{'fits(pin)':>11}{'pages/frame':>13}{'%idle CPU':>11}{'%DMA':>7}")
    for row in report["page_frames_table"]:
        b = row.get("budget")
        if isinstance(b, dict):
            cells = (f"{b['pages_per_frame_at_camera_cap']:>13.4f}"
                     f"{b['pct_of_idle_cpu']:>11.1f}"
                     f"{b['pct_of_dma_budget_ntsc']:>7.1f}")
        else:
            cells = "  " + f"{str(b)[:29]:>29}"
        a(f"{row['page_frames']:>7}{row['pool_tiles']:>7}"
          f"{row['tiles_returned_to_objects']:>11}"
          f"{str(row['covers_tile_cache_peak_unpinned']):>13}"
          f"{str(row['covers_tile_cache_peak_with_pinning']):>11}"
          f"{cells}")
    a("")
    a("   pages/frame = worst-traverse page-ins per 1000 px (max over both axes,")
    a("   unpinned) scaled by the CAM_MAX_*_STEP camera cap. %idle CPU is against")
    a("   ARCH 9.7's ~42.5 K idle cycles; %DMA against DMA_BUDGET_NTSC.")
    a("")
    a("LIMITS")
    for k, val in report["limits"].items():
        a(f"  {k}: {val}")
    a("")
    a(f"PAGE_FRAMES today = {c['PAGE_FRAMES']['value']} "
      f"({c['PAGE_FRAMES']['source']}), max {c['PAGE_FRAMES_MAX']['value']}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", nargs="?", default="report", choices=["report"])
    ap.add_argument("--json", metavar="PATH",
                    help="write the full report as JSON to PATH ('-' for stdout)")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress the human-readable report")
    ap.add_argument("--verbose", action="store_true",
                    help="progress to stderr")
    args = ap.parse_args(argv)

    report = build_report(verbose=args.verbose)
    if args.json:
        text = json.dumps(report, indent=2, sort_keys=False)
        if args.json == "-":
            print(text)
        else:
            with open(args.json, "w") as fh:
                fh.write(text + "\n")
    if not args.quiet:
        print(human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
