#!/usr/bin/env python3
"""megaact_window_pageset.py — M-B: how many FG pages does the 80x60 tile-cache
window reference at a stitched seam / junction between REAL classic zones?

THIS IS A MEASUREMENT OVER DONOR DATA PUSHED THROUGH AEON'S BUILD-TIME PAGE
PIPELINE. IT IS NOT AN OBSERVATION OF THE RUNNING ENGINE. Read this before
quoting a number.

The question (docs/research/megaact-bg-streaming/07-fable-design-review.md,
finding 1): the release engine soft-locks (camera held forever) when the
tile-cache window references more distinct pages than there are frames. So for
every camera position along a seam between two zones, and around a three-zone
junction, count

    needed(camera) = | pinned_pages  UNION  pages referenced by every non-blank
                       nametable word in the 80x60 Tile_Cache_Nametable window |

and compare it against PAGE_FRAMES (and against 10, the owner's future lever).

WHAT IS REAL AND WHAT IS ADAPTER
--------------------------------
REAL (imported, called unmodified):
  tile_dedupe.dedupe_tiles           canonical-form global dedupe
  tile_dedupe.order_pool_spatially   first-occurrence traversal order
  tile_dedupe.pin_blank_tile_first   blank tile at global slot 0
  tile_dedupe.split_pool_into_pages  64-tile pages
  ojz_strip_gen.mark_pinned_pages    PIN_SECTION_FRACTION pin rule
  ojz_strip_gen.build_section_local_map  (the 2048-entry per-section refusal)
  ojz_strip_gen.chunk_get_tile_word  chunk -> tile word (flip handling)
  ojz_common.kos_decompress / load_block_map / load_chunk_map
ADAPTER (this file):
  * Sonic 2 donor loading: layout ($1000 bytes, FG row r at r*$100, 128 chunks
    wide x 16 tall), per-zone art/blocks/chunks, the HTZ supplement overlays
    (art at ArtTile_ArtKos_NumTiles_HTZ_Main, blocks at the `Block_Table+$980`
    patch), each read out of s2disasm, never typed in.
  * Each zone is CROPPED to its camera-reachable box from s2.asm `LevelSize`
    (x: xstart .. xend+320, y: max(0,ystart) .. yend+224). Everything outside
    the box is VOID (blank). MTZ's negative ystart (vertical wrap) is clamped
    to 0; the wrap is not modelled.
  * Stitching: boxes are placed into one world nametable; each source tile is
    keyed (zone, source tile index) so two zones' tile index spaces never
    collide, and a VOID cell is keyed to an all-zero tile (which dedupe merges
    with any real all-zero tile, exactly as a painted-air cell would be).
  * The generate() GLUE is replicated, not called (generate() is hard-wired
    to OJZ's editor tree and writes the committed tree): sections are 256x256
    tiles in flat row-major grid order, each section's canonical tiles listed
    in column-major first-occurrence order (generate()'s Pass 3 walks
    `for col in strips: for word in col`). The glue is PROVEN against the
    shipped OJZ bake by `control` (it must reproduce the manifest's pool size,
    page count and pinned flags, every section's committed local map, and the
    page of every cell decoded from the shipped block blobs) before any
    donor number is trusted. `report` refuses to run if the control fails.
  * The source tile index is NOT squeezed into the nametable's 11-bit field
    (collect_referenced_tiles masks to it): three dense S2 zones carry more
    than 2048 source tiles between them. The dedupe/order/page functions take
    canonical ids and have no such limit; the 11-bit limit that the engine
    DOES have is the per-section LOCAL palette, which build_section_local_map
    enforces and this tool reports.

WINDOW GEOMETRY (derived from engine source; `derive_window` re-proves it):
  left = max(0, floor(camX/8) - TILE_CACHE_MARGIN_H), cols left..left+COLS-1
  top  = max(0, floor(camY/8) - TILE_CACHE_MARGIN_V) & ~1, rows top..top+ROWS-1
because Tile_Cache_Fill's desired far edge ((cam + SECTION_*_REACH_PX)>>3 +
MARGIN) always exceeds near + COLS-1 / ROWS-1, so the clamp binds at every
sub-tile offset and the window does not depend on direction of travel.
The sweep enumerates every distinct window a camera in the act's bounding
rectangle can produce (all camera X/Y, which is tile granularity by
construction: the window depends only on floor(cam/8)).

  * Sonic 3 & Knuckles donor loading (`--game s3k`): LevelLoadBlock rows and
    label bincludes from skdisasm (the S3 half through `Lockon S3/LockOn
    Data.asm`), 8x8 art as KosM primary + secondary appended at the primary's
    size, blocks/chunks as Kosinski primary + secondary concatenated, the FG
    rows of the uncompressed layout via its row-pointer table, LevelSizes for
    the box; xend $6000 placeholders fall back to the layout width, and
    trailing all-tile-0 columns beyond one screen are trimmed.

ALSO REPORTED per window: distinct non-blank tiles and ceil(tiles/64), a lower
bound on frames for ANY 64-tile paging of that one window. It is a per-window
bound, not a proof that one global order meets it everywhere.

NOT COVERED: object/sprite art, the BG plane, animated tiles as separate
art, transient frame demand (a published-but-unreferenced demand page, an
in-flight decode, a stalled column whose old words still hold references),
and eviction ORDER under motion. The static page-set count is a NECESSARY
condition for no soft-lock, not a sufficient one.

Usage (numpy required; donors resolved through suite_paths, or
AEON_S2DISASM_DIR / AEON_SKDISASM_DIR):
    python3 tools/megaact_window_pageset.py control
    python3 tools/megaact_window_pageset.py report --game s2  [--json PATH] [--quick]
    python3 tools/megaact_window_pageset.py report --game s3k [--json PATH] [--quick]
Measured wall time on the dev box (2026-09-16): s2 ~1.7 min, s3k ~9.4 min.
"""

import argparse
import json
import os
import random
import re
import struct
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
sys.path.insert(0, TOOLS)

import tile_dedupe                              # noqa: E402
import ojz_common                               # noqa: E402
import ojz_strip_gen                            # noqa: E402
import act_grid                                 # noqa: E402
from fg_working_set import ConstantSource       # noqa: E402
from suite_paths import require_suite_path      # noqa: E402

CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")

S2_DIR_ENV = "AEON_S2DISASM_DIR"


def s2disasm_root():
    env = os.environ.get(S2_DIR_ENV)
    if env:
        if not os.path.isdir(env):
            raise SystemExit(f"{S2_DIR_ENV}={env} is not a directory")
        return env
    return str(require_suite_path("s2disasm", what="Sonic 2 donor disassembly"))


# ---------------------------------------------------------------------------
# Engine constants + window derivation
# ---------------------------------------------------------------------------

NEEDED = [
    "TILE_CACHE_COLS", "TILE_CACHE_ROWS", "TILE_CACHE_MARGIN_H", "TILE_CACHE_MARGIN_V",
    "SECTION_H_REACH_PX", "SECTION_V_REACH_PX", "SCREEN_WIDTH", "SCREEN_HEIGHT",
    "ART_POOL_PAGE_TILES", "PAGE_FRAME_TILE_SHIFT", "POOL_TILE_CEILING",
    "PAGE_FRAMES", "PAGE_FRAMES_MAX", "SECTION_SIZE", "MAX_ACT_SECTIONS",
    "PAGE_TABLE_MAX", "NT_TILE_MASK",
]

OWNER_LEVER_FRAMES = 10   # owner ruling: a future lever shrinks the FG cache 12 -> 10 pages


def load_constants():
    src = ConstantSource()
    src.load_file(CONSTANTS_EMP)
    c = {n: src.get(n) for n in NEEDED}
    origin = {n: src.origin[n] for n in NEEDED}
    if c["PAGE_FRAMES"] * c["ART_POOL_PAGE_TILES"] != c["POOL_TILE_CEILING"]:
        raise SystemExit("PAGE_FRAMES does not tile POOL_TILE_CEILING")
    if (1 << c["PAGE_FRAME_TILE_SHIFT"]) != c["ART_POOL_PAGE_TILES"]:
        raise SystemExit("PAGE_FRAME_TILE_SHIFT disagrees with ART_POOL_PAGE_TILES")
    if ojz_strip_gen.ART_POOL_PAGE_TILES != c["ART_POOL_PAGE_TILES"]:
        raise SystemExit("ojz_strip_gen.ART_POOL_PAGE_TILES disagrees with the engine")
    if ojz_strip_gen.STRIP_TILE_HEIGHT != c["SECTION_SIZE"] >> 3:
        raise SystemExit("ojz_strip_gen section height disagrees with SECTION_SIZE")
    return c, origin


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


def derive_window(c):
    """Prove the clamp binds at every sub-tile offset (so the held window is
    exactly COLS x ROWS from left/top, independent of travel direction)."""
    # Away from the zero clamp. AT the zero clamp (left == 0 / top == 0) the fill's
    # desired far edge is short of left+COLS-1, but the HELD window is still
    # COLS x ROWS: Tile_Cache_Init commits Cache_Head_Col = left+COLS-1 and
    # Cache_Bottom_Row = top+ROWS-1 and fills all of it, and the far edge only
    # ever retreats through the evict-at-capacity arms, which keep span == COLS/ROWS.
    for base in (8 * 64, 8 * 1000):
        for f in range(8):
            l, r, t, b = window_for_camera(c, base + f, base + f)
            if r - l + 1 != c["TILE_CACHE_COLS"] or b - t + 1 != c["TILE_CACHE_ROWS"]:
                raise SystemExit(
                    f"window clamp does NOT bind at sub-tile offset {f}: {l}..{r} x {t}..{b}. "
                    f"The held window then depends on travel direction; this tool's "
                    f"camera->window map is unsound — UNMEASURABLE, re-derive.")
    return {
        "cols": c["TILE_CACHE_COLS"], "rows": c["TILE_CACHE_ROWS"],
        "left": "max(0, floor(camX/8) - TILE_CACHE_MARGIN_H)",
        "top": "max(0, floor(camY/8) - TILE_CACHE_MARGIN_V) & ~1",
        "note": "far-edge clamp binds at all 8 sub-tile offsets on both axes (checked)",
    }


# ---------------------------------------------------------------------------
# Sonic 2 donor loading
# ---------------------------------------------------------------------------

# Donor file registry: which art/16x16/128x128/layout each zone's act 1 uses.
# Cross-read from s2.asm `LevelArtPointers` (levartptrs rows) and the
# `BM16_*:/ArtKos_*:/BM128_*: BINCLUDE` block; `zone_files()` re-checks each
# BINCLUDE spelling against s2.asm so a renamed donor file fails loudly.
S2_ZONES = {
    #        art          blocks16     chunks128    layout   LevelSize key
    "EHZ": ("EHZ_HTZ",  "EHZ",       "EHZ_HTZ",   "EHZ_1", "EHZ"),
    "HTZ": ("EHZ_HTZ",  "EHZ",       "EHZ_HTZ",   "HTZ_1", "HTZ"),   # + HTZ overlays
    "CPZ": ("CPZ_DEZ",  "CPZ_DEZ",   "CPZ_DEZ",   "CPZ_1", "CPZ"),
    "ARZ": ("ARZ",      "ARZ",       "ARZ",       "ARZ_1", "ARZ"),
    "CNZ": ("CNZ",      "CNZ",       "CNZ",       "CNZ_1", "CNZ"),
    "MCZ": ("MCZ",      "MCZ",       "MCZ",       "MCZ_1", "MCZ"),
    "OOZ": ("OOZ",      "OOZ",       "OOZ",       "OOZ_1", "OOZ"),
    "MTZ": ("MTZ",      "MTZ",       "MTZ",       "MTZ_1", "MTZ"),
}


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def parse_level_sizes(s2asm_text):
    """{(zone, act): (xstart, xend, ystart, yend)} from s2.asm `LevelSize:`."""
    start = s2asm_text.index("\nLevelSize:")
    end = s2asm_text.index("zoneTableEnd", start)
    zone = None
    acts = {}
    for line in s2asm_text[start:end].splitlines()[1:]:
        m = re.match(r"^\s*;\s*([A-Za-z0-9 ]+?)\s*$", line)
        if m:
            zone = m.group(1).strip()
            continue
        m = re.match(r"^\s*zoneTableEntry\.w\s+(.+?);\s*Act\s+(\d+)", line)
        if m:
            vals = [int(v.strip().replace("$", "0x").replace("-0x", "-0x"), 0)
                    for v in m.group(1).split(",")]
            acts[(zone, int(m.group(2)))] = tuple(vals)
    if ("EHZ", 1) not in acts:
        raise SystemExit("could not parse s2.asm LevelSize table")
    return acts


def parse_s2_constant(text, name):
    m = re.search(rf"^{name}\s*=\s*\$([0-9A-Fa-f]+)", text, re.M)
    if not m:
        raise SystemExit(f"s2.constants.asm no longer defines {name}")
    return int(m.group(1), 16)


class Zone:
    """One S2 zone act, cropped to its camera-reachable box.

    words: (box_h, box_w) uint16 nametable words; void: same shape, bool.
    """

    def __init__(self, name, words, void, box, art_tiles, n_art_tiles):
        self.name = name
        self.words = words
        self.void = void
        self.box = box
        self.art = art_tiles          # bytes, 32 per tile
        self.n_art_tiles = n_art_tiles


_zone_cache = {}


def _chunk_tiles(chunks, blocks):
    """chunk id -> 16x16 tile words, through the REAL chunk_get_tile_word."""
    tpc = ojz_strip_gen.TILES_PER_CHUNK_ROW
    out = np.zeros((len(chunks), tpc, tpc), dtype=np.uint16)
    for ci, ch in enumerate(chunks):
        for tr in range(tpc):
            for tc in range(tpc):
                out[ci, tr, tc] = ojz_strip_gen.chunk_get_tile_word(ch, blocks, tc, tr)
    return out


def _crop(name, full, art, xs, xe, ys, ye, extra=None):
    """Crop a zone's full FG nametable to its camera-reachable LevelSize box."""
    tile = 8
    x0 = max(0, xs) // tile
    x1 = min(full.shape[1], -(-(xe + 320) // tile))
    y0 = max(0, ys) // tile
    y1 = min(full.shape[0], -(-(ye + 224) // tile))
    words = full[y0:y1, x0:x1].copy()
    n_art = len(art) // 32
    oob = int(np.count_nonzero((words & 0x7FF) >= n_art))
    if oob:
        raise SystemExit(f"{name}: {oob} words reference tiles past the {n_art}-tile art blob")
    box = {"level_size_px": [xs, xe, ys, ye], "crop_tiles": [x0, x1, y0, y1],
           "ystart_clamped": ys < 0}
    if extra:
        box.update(extra)
    return Zone(name, words, np.zeros(words.shape, dtype=bool), box, bytes(art), n_art)


def load_zone(name):
    if name in _zone_cache:
        return _zone_cache[name]
    if name in S2_ZONES:
        z = _load_s2(name)
    elif name in S3K_ZONES:
        z = _load_s3k(name)
    else:
        raise SystemExit(f"unknown zone {name!r}")
    _zone_cache[name] = z
    return z


def _load_s2(name):
    root = s2disasm_root()
    s2asm = open(os.path.join(root, "s2.asm"), "r", errors="replace").read()
    s2const = open(os.path.join(root, "s2.constants.asm"), "r", errors="replace").read()
    art_n, b16_n, b128_n, lay_n, size_key = S2_ZONES[name]
    for spelled in (f'"art/kosinski/{art_n}.kos"', f'"mappings/16x16/{b16_n}.kos"',
                    f'"mappings/128x128/{b128_n}.kos"'):
        if spelled not in s2asm:
            raise SystemExit(f"s2.asm no longer BINCLUDEs {spelled} — donor registry is stale")

    art, _ = ojz_common.kos_decompress(_read(os.path.join(root, "art/kosinski", art_n + ".kos")))
    art = bytearray(art)
    blocks = ojz_common.load_block_map(os.path.join(root, "mappings/16x16", b16_n + ".kos"))
    if name == "HTZ":
        # s2.asm: KosDec ArtKos_HTZ to Chunk_Table+tiles_to_bytes(..._HTZ_Main)
        main = parse_s2_constant(s2const, "ArtTile_ArtKos_NumTiles_HTZ_Main")
        supp, _ = ojz_common.kos_decompress(_read(os.path.join(root, "art/kosinski/HTZ_Supp.kos")))
        off = main * 32
        if len(art) < off + len(supp):
            art.extend(bytes(off + len(supp) - len(art)))
        art[off:off + len(supp)] = supp
        # s2.asm: `lea (Block_Table+$980).w,a1` / `lea (BM16_HTZ).l,a0` / KosDec
        m = re.search(r"lea\s+\(Block_Table\+\$([0-9A-Fa-f]+)\)\.w,a1\s*\n\s*lea\s+\(BM16_HTZ\)", s2asm)
        if not m:
            raise SystemExit("s2.asm HTZ block-map patch offset not found")
        boff = int(m.group(1), 16) // 8
        htz_blocks = ojz_common.load_block_map(os.path.join(root, "mappings/16x16/HTZ.kos"))
        need = boff + len(htz_blocks)
        while len(blocks) < need:
            blocks.append([0, 0, 0, 0])
        blocks[boff:boff + len(htz_blocks)] = htz_blocks
    chunks = ojz_common.load_chunk_map(os.path.join(root, "mappings/128x128", b128_n + ".kos"))
    layout, _ = ojz_common.kos_decompress(_read(os.path.join(root, "level/layout", lay_n + ".kos")))
    if len(layout) != 0x1000:
        raise SystemExit(f"{lay_n}: layout decoded to {len(layout)} bytes, expected $1000")

    tpc = ojz_strip_gen.TILES_PER_CHUNK_ROW
    lay = np.frombuffer(bytes(layout), dtype=np.uint8).reshape(32, 128)[0::2]   # FG rows
    full = _chunk_tiles(chunks, blocks)[lay]       # (16, 128, 16, 16)
    full = full.transpose(0, 2, 1, 3).reshape(16 * tpc, 128 * tpc)
    xs, xe, ys, ye = parse_level_sizes(s2asm)[(size_key, 1)]
    return _crop(name, full, art, xs, xe, ys, ye, {"game": "Sonic 2", "layout": lay_n})


# ---------------------------------------------------------------------------
# Sonic 3 & Knuckles donor loading
# ---------------------------------------------------------------------------

# name -> (LevelLoadBlock row comment, LevelSizes comment, LevelPtrs layout label).
# Every file is resolved from sonic3k.asm by label (`Label:` then `binclude`).
S3K_ZONES = {
    "AIZ2": ("ANGEL ISLAND ZONE ACT 2", "AIZ2", "Layout_AIZ2"),
    "HCZ1": ("HYDROCITY ZONE ACT 1", "HCZ1", "Layout_HCZ1"),
    "MGZ1": ("MARBLE GARDEN ZONE ACT 1", "MGZ1", "Layout_MGZ1"),
    "CNZ1": ("CARNIVAL NIGHT ZONE ACT 1", "CNZ1", "Layout_CNZ1"),
    "FBZ1": ("FLYING BATTERY ZONE ACT 1", "FBZ1", "Layout_FBZ1"),
    "ICZ1": ("ICECAP ZONE ACT 1", "ICZ1", "Layout_ICZ1"),
    "LBZ1": ("LAUNCH BASE ZONE ACT 1", "LBZ1", "Layout_LBZ1"),
    "MHZ1": ("MUSHROOM HILL ZONE ACT 1", "MHZ1", "Layout_MHZ1"),
    "SOZ1": ("SANDOPOLIS ZONE ACT 1", "SOZ1", "Layout_SOZ1"),
    "LRZ1": ("LAVA REEF ZONE ACT 1", "LRZ1", "Layout_LRZ1"),
}


def skdisasm_dir():
    root = ojz_common.skdisasm_root()
    if not os.path.isfile(os.path.join(root, "sonic3k.asm")):
        raise SystemExit(f"skdisasm donor not found at {root} (set AEON_SKDISASM_DIR)")
    return root


def kosm_decompress(data):
    """Kosinski-moduled, per sonic3k.asm Process_Kos_Module_Queue(_Init): a u16
    uncompressed size ($A000 means $8000), then Kosinski modules, each next module
    starting at the previous one's end rounded up to a $10 boundary FROM ITS START."""
    size = struct.unpack(">H", data[:2])[0]
    if size == 0xA000:
        size = 0x8000
    pos = 2
    out = bytearray()
    while len(out) < size:
        start = pos
        dec, end = ojz_common.kos_decompress(data, pos)
        if not dec:
            raise SystemExit("KosM module decoded empty before the header size was reached")
        out += dec
        pos = end + ((start - end) & 0xF)
    if len(out) != size:
        raise SystemExit(f"KosM decoded {len(out)} bytes, header says {size}")
    return bytes(out)


def _load_s3k(name):
    root = skdisasm_dir()
    asm = open(os.path.join(root, "sonic3k.asm"), "r", errors="replace").read()
    row_comment, size_tag, layout_label = S3K_ZONES[name]

    # The S3 half's data lives in `Lockon S3/LockOn Data.asm` (sonic3k.asm only
    # carries `ds.b` placeholders for it via LockOn Pointers.asm).
    lockon = open(os.path.join(root, "Lockon S3", "LockOn Data.asm"), "r", errors="replace").read()

    def binclude(label):
        for text in (asm, lockon):
            m = re.search(r"^" + re.escape(label) + r':\s*binclude\s+"([^"]+)"', text, re.M)
            if m:
                return os.path.join(root, m.group(1))
        raise SystemExit(f"skdisasm: no `{label}:` binclude in sonic3k.asm or LockOn Data.asm")

    row = re.search(r"^\s*levartptrs\s+(.+?);\s*" + re.escape(row_comment) + r"\s*$", asm, re.M)
    if not row:
        raise SystemExit(f"sonic3k.asm LevelLoadBlock: no row `{row_comment}`")
    f = [x.strip() for x in row.group(1).split(",")]
    tiles_p, tiles_s, b16_p, b16_s, b128_p, b128_s = f[3:9]

    # LoadLevelLoadBlock: primary 8x8 at VRAM 0, secondary at (primary size), unless same label
    art = bytearray(kosm_decompress(_read(binclude(tiles_p))))
    if tiles_s != tiles_p:
        art += kosm_decompress(_read(binclude(tiles_s)))
    # LoadLevelLoadBlock2: Kos_Decomp primary then secondary into one buffer (a1 continues)
    raw16, _ = ojz_common.kos_decompress(_read(binclude(b16_p)))
    if b16_s != b16_p:
        raw16 += ojz_common.kos_decompress(_read(binclude(b16_s)))[0]
    raw128, _ = ojz_common.kos_decompress(_read(binclude(b128_p)))
    if b128_s != b128_p:
        raw128 += ojz_common.kos_decompress(_read(binclude(b128_s)))[0]
    blocks = [list(struct.unpack_from(">4H", raw16, i)) for i in range(0, len(raw16) // 8 * 8, 8)]
    words128 = struct.unpack(f">{len(raw128) // 2}H", raw128[:len(raw128) // 2 * 2])
    chunks = [list(words128[i:i + 64]) for i in range(0, len(words128) // 64 * 64, 64)]

    lay = _read(binclude(layout_label))
    fg_w, _bg_w, fg_h, _bg_h = struct.unpack(">4H", lay[:8])
    rows = []
    for r in range(fg_h):
        ptr = struct.unpack(">H", lay[8 + 4 * r:10 + 4 * r])[0] - 0x8000
        rows.append(list(lay[ptr:ptr + fg_w]))
    lay_arr = np.array(rows, dtype=np.int64)
    if lay_arr.max() >= len(chunks):
        raise SystemExit(f"{name}: layout names chunk {lay_arr.max()} of {len(chunks)}")
    tpc = ojz_strip_gen.TILES_PER_CHUNK_ROW
    full = _chunk_tiles(chunks, blocks)[lay_arr]
    full = full.transpose(0, 2, 1, 3).reshape(fg_h * tpc, fg_w * tpc)

    m = re.search(r"^\s*dc\.w\s+(.+?);\s*" + re.escape(size_tag) + r"\s*$", asm, re.M)
    if not m:
        raise SystemExit(f"sonic3k.asm LevelSizes: no row `{size_tag}`")
    xs, xe, ys, ye = [int(v.strip().replace("$", "0x"), 0) for v in m.group(1).split(",")]
    z = _crop(name, full, art, xs, xe, ys, ye,
              {"game": "Sonic 3 & Knuckles", "layout_chunks_wh": [fg_w, fg_h],
               "xend_is_placeholder_6000": xe >= 0x6000})
    # xend $6000 is a placeholder the resize events narrow at runtime; the layout's
    # own painted extent bounds the box. Trim trailing all-tile-0 columns, keeping
    # one screen width of the empty edge.
    nz = np.nonzero((z.words & 0x7FF).any(axis=0))[0]
    keep_extra = 320 // 8
    if nz.size and nz[-1] + 1 + keep_extra < z.words.shape[1]:
        keep = int(nz[-1] + 1 + keep_extra)
        z.box["trimmed_empty_cols_to"] = keep
        z.words = z.words[:, :keep].copy()
        z.void = z.void[:, :keep].copy()
    return z


# ---------------------------------------------------------------------------
# Act assembly + the page pipeline
# ---------------------------------------------------------------------------

class Act:
    """A world nametable made of placed zone boxes.

    zone_id: (H, W) int16, -1 = VOID.   src: (H, W) int32 source tile index.
    flip: (H, W) uint16 — the original word (only the tile field is keyed).
    """

    def __init__(self, name, placements, section_tiles):
        self.name = name
        self.placements = placements     # [(Zone, col0, row0)]
        h = max(r0 + z.words.shape[0] for z, _, r0 in placements)
        w = max(c0 + z.words.shape[1] for z, c0, _ in placements)
        self.content_h, self.content_w = h, w
        st = section_tiles
        self.grid_w = -(-w // st)
        self.grid_h = -(-h // st)
        H, W = self.grid_h * st, self.grid_w * st
        self.zone_id = np.full((H, W), -1, dtype=np.int16)
        self.src = np.zeros((H, W), dtype=np.int32)
        self.zones = []
        for zi, (z, c0, r0) in enumerate(placements):
            zh, zw = z.words.shape
            region = self.zone_id[r0:r0 + zh, c0:c0 + zw]
            if np.any(region >= 0):
                raise SystemExit(f"{name}: placement of {z.name} overlaps another zone")
            region[:] = zi
            self.src[r0:r0 + zh, c0:c0 + zw] = z.words & 0x7FF
            self.zones.append(z)


def run_pipeline(act, c, order_fn=None, zone_split_dedupe=False):
    """Aeon's build-time page pipeline over the stitched act. Returns a dict with
    page_grid ((H, W) int16, -1 = blank/no page), pinned list, pool facts.

    order_fn=None is the SHIPPED Pass 4 (order_pool_spatially + pin_blank_tile_first),
    the path `control` proves against the committed OJZ bake. A candidate order
    (tools/megaact_page_order.py, STITCHED-ACT-PAGE-ORDER) is a callable
    order_fn(ctx) -> pool_order over canonical ids that must put the blank canonical
    at slot 0 and list every referenced canonical exactly once; this function
    refuses otherwise. Everything after the order (split, pin rule, local maps) is
    the same code either way.

    zone_split_dedupe=True keys the dedupe result by (zone, canonical), so two
    zones never share a pool slot (VOID cells stay on the one blank). It is a
    candidate POLICY for cross-zone shared tiles, not the shipped behaviour."""
    st = c["SECTION_SIZE"] >> 3
    H, W = act.zone_id.shape
    # ---- key every cell: (zone, source tile), VOID -> key 0 (an all-zero tile) ----
    key = np.where(act.zone_id < 0, 0,
                   (act.zone_id.astype(np.int64) + 1) * 4096 + act.src).astype(np.int64)
    ref = np.unique(key)
    raw_tiles = []
    for k in ref.tolist():
        if k == 0:
            raw_tiles.append(tile_dedupe.BLANK_TILE)
        else:
            z = act.zones[k // 4096 - 1]
            i = k % 4096
            raw_tiles.append(z.art[i * 32:(i + 1) * 32])
    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)
    key_to_canon = np.array([m[0] for m in mapping], dtype=np.int64)
    canon = key_to_canon[np.searchsorted(ref, key)]
    if zone_split_dedupe:
        # one canonical per (zone, canonical); every blank cell keeps the one blank canonical
        blank_c = unique.index(tile_dedupe.BLANK_TILE) if tile_dedupe.BLANK_TILE in unique else -1
        nz = len(act.zones) + 1
        zk = canon * nz + (act.zone_id.astype(np.int64) + 1)
        zk = np.where(canon == blank_c, blank_c * nz, zk)
        zref, zinv = np.unique(zk, return_inverse=True)
        unique = [unique[int(k) // nz] for k in zref.tolist()]
        canon = zinv.reshape(canon.shape).astype(np.int64)

    # ---- Pass 3: per-section canonical lists, column-major first occurrence ----
    per_section = []
    for sy in range(act.grid_h):
        for sx in range(act.grid_w):
            sub = canon[sy * st:(sy + 1) * st, sx * st:(sx + 1) * st]
            flat = sub.T.ravel()                   # strips[col][row] walk order
            u, idx = np.unique(flat, return_index=True)
            per_section.append(u[np.argsort(idx, kind="stable")].tolist())

    # ---- Pass 4 ----
    order_s = time.perf_counter()
    order_stats = {}
    if order_fn is None:
        pool_order = tile_dedupe.order_pool_spatially(per_section)
        pool_order = tile_dedupe.pin_blank_tile_first(pool_order, unique)
    else:
        if tile_dedupe.BLANK_TILE not in unique:      # as pin_blank_tile_first would
            unique.append(tile_dedupe.BLANK_TILE)
        order_ctx = {"canon": canon, "zone_id": act.zone_id, "unique": unique,
                     "per_section": per_section, "act": act, "c": c, "stats": {}}
        pool_order = list(order_fn(order_ctx))
        order_stats = order_ctx["stats"]
        if sorted(pool_order) != sorted({x for s in per_section for x in s}
                                        | {unique.index(tile_dedupe.BLANK_TILE)}):
            raise SystemExit(f"{act.name}: candidate order is not a permutation of the "
                             f"referenced canonicals plus blank")
    order_s = time.perf_counter() - order_s
    assert unique[pool_order[0]] == tile_dedupe.BLANK_TILE
    canon_to_pool = np.full(len(unique), -1, dtype=np.int64)
    canon_to_pool[np.array(pool_order, dtype=np.int64)] = np.arange(len(pool_order))
    pages = tile_dedupe.split_pool_into_pages(pool_order, c["ART_POOL_PAGE_TILES"])

    per_section_global_sets = [set(canon_to_pool[np.array(s, dtype=np.int64)].tolist())
                               for s in per_section]
    pinned_flags = ojz_strip_gen.mark_pinned_pages(pages, per_section_global_sets)
    pinned = [i for i, p in enumerate(pinned_flags) if p]

    local_palette_max = 0
    local_palette_refusals = []
    for s_idx, gs in enumerate(per_section_global_sets):
        try:
            lm = ojz_strip_gen.build_section_local_map(gs)
            local_palette_max = max(local_palette_max, len(lm))
        except ValueError as exc:
            local_palette_refusals.append({"section": s_idx, "error": str(exc)})

    glob = canon_to_pool[canon]
    page_grid = np.where(glob == 0, -1, glob >> c["PAGE_FRAME_TILE_SHIFT"]).astype(np.int16)
    return {
        "page_grid": page_grid,
        "pinned": pinned,
        "pages": len(pages),
        "pool_tiles": len(pool_order),
        "source_tiles": int(len(ref)),
        "sections": act.grid_w * act.grid_h,
        "grid": [act.grid_w, act.grid_h],
        "local_palette_max": local_palette_max,
        "local_palette_refusals": local_palette_refusals,
        "per_section_global_sets": per_section_global_sets,
        "glob_grid": glob,
        "order_seconds": order_s,
        "order_stats": order_stats,
        "pool_order": pool_order,
        "unique": unique,
    }


# ---------------------------------------------------------------------------
# Window sweep
# ---------------------------------------------------------------------------

def camera_windows(c, content_w, content_h):
    """Every distinct window (left, top) a camera in [0, W*8-320] x [0, H*8-224]
    produces, as index arrays + the camera tile ranges that map to each."""
    max_cx = max(0, content_w * 8 - c["SCREEN_WIDTH"])
    max_cy = max(0, content_h * 8 - c["SCREEN_HEIGHT"])
    lefts = sorted({window_for_camera(c, x * 8, 0)[0] for x in range(max_cx // 8 + 1)})
    tops = sorted({window_for_camera(c, 0, y * 8)[2] for y in range(max_cy // 8 + 1)})
    return np.array(lefts), np.array(tops), max_cx, max_cy


def presence_counts(grid, labels, cols, rows, lefts, tops, weight_mask=None):
    """counts[ti, li] = number of distinct label values (>=0) present in the
    cols x rows window at (tops[ti], lefts[li]). Labels in `weight_mask`
    (a set) are skipped. Out-of-grid cells count as absent."""
    H, W = grid.shape
    padded = np.full((H + rows, W + cols), -1, dtype=grid.dtype)
    padded[:H, :W] = grid
    counts = np.zeros((len(tops), len(lefts)), dtype=np.int16)
    for p in labels:
        if weight_mask is not None and p in weight_mask:
            continue
        ind = (padded == p).astype(np.int32)
        ii = np.zeros((H + rows + 1, W + cols + 1), dtype=np.int32)
        np.cumsum(np.cumsum(ind, axis=0), axis=1, out=ii[1:, 1:])
        t = tops[:, None]
        l = lefts[None, :]
        s = ii[t + rows, l + cols] - ii[t, l + cols] - ii[t + rows, l] + ii[t, l]
        counts += (s > 0)
    return counts


def distinct_tiles_per_window(glob, lefts, tops, cols, rows):
    """out[ti, li] = number of distinct NON-BLANK global tiles in the window.

    Per top band: each (tile, column) occurrence, de-duplicated per column,
    counts +1 for every window left l in [max(prev_col(tile)+1, col-cols+1), col],
    where prev_col is the previous column in the band holding the same tile.
    A difference array + cumsum turns that into per-left counts. The independent
    control is `window_tiles_bruteforce`."""
    H, W = glob.shape
    padded = np.zeros((H + rows, W + cols), dtype=np.int64)
    padded[:H, :W] = glob
    Wp = W + cols
    out = np.zeros((len(tops), len(lefts)), dtype=np.int32)
    for ti, t in enumerate(tops.tolist()):
        band = padded[t:t + rows, :]
        col_idx = np.broadcast_to(np.arange(Wp), band.shape)
        tile = band.ravel()
        col = col_idx.ravel()
        keep = tile != 0
        key = np.unique(tile[keep] * Wp + col[keep])          # sorted by (tile, col), deduped
        if key.size == 0:                                     # an all-blank band
            continue                                          # out[ti, :] stays 0
        tk, ck = key // Wp, key % Wp
        prev = np.empty_like(ck)
        prev[0] = -1
        prev[1:] = np.where(tk[1:] == tk[:-1], ck[:-1], -1)
        lo = np.maximum(prev + 1, ck - cols + 1)
        lo = np.maximum(lo, 0)
        hi = ck
        diff = np.zeros(Wp + 1, dtype=np.int64)
        valid = lo <= hi
        np.add.at(diff, lo[valid], 1)
        np.add.at(diff, hi[valid] + 1, -1)
        per_left = np.cumsum(diff)[:Wp]
        out[ti, :] = per_left[lefts]
    return out


def window_tiles_bruteforce(glob, left, top, cols, rows):
    v = glob[top:top + rows, left:left + cols].ravel()
    return int(np.unique(v[v != 0]).size)


def window_page_set_bruteforce(page_grid, left, top, cols, rows):
    """Independent direct scan (pure Python) — the control for presence_counts."""
    H, W = page_grid.shape
    out = set()
    for r in range(top, min(top + rows, H)):
        row = page_grid[r].tolist()
        for cc in range(left, min(left + cols, W)):
            v = row[cc]
            if v >= 0:
                out.add(v)
    return out


def reachable_mask(act, c, lefts, tops):
    """reach[ti, li] = some camera tile position mapping to this window has its
    whole visible screen (40x28 tiles) inside non-VOID cells."""
    sw, sh = c["SCREEN_WIDTH"] >> 3, c["SCREEN_HEIGHT"] >> 3
    H, W = act.zone_id.shape
    solid = (act.zone_id >= 0).astype(np.int32)
    ii = np.zeros((H + sh + 1, W + sw + 1), dtype=np.int32)
    ii[1:H + 1, 1:W + 1] = np.cumsum(np.cumsum(solid, axis=0), axis=1)
    ii[H + 1:, :] = ii[H, :]
    ii[:, W + 1:] = ii[:, W:W + 1]
    li_of = {int(v): i for i, v in enumerate(lefts)}
    ti_of = {int(v): i for i, v in enumerate(tops)}
    reach = np.zeros((len(tops), len(lefts)), dtype=bool)
    max_ct = max(0, (act.content_w * 8 - c["SCREEN_WIDTH"]) // 8)
    max_rt = max(0, (act.content_h * 8 - c["SCREEN_HEIGHT"]) // 8)
    cts = np.arange(max_ct + 1)
    rts = np.arange(max_rt + 1)
    inside = (ii[rts[:, None] + sh, cts[None, :] + sw] - ii[rts[:, None], cts[None, :] + sw]
              - ii[rts[:, None] + sh, cts[None, :]] + ii[rts[:, None], cts[None, :]]) == sw * sh
    col_li = np.array([li_of[window_for_camera(c, int(x) * 8, 0)[0]] for x in cts])
    row_ti = np.array([ti_of[window_for_camera(c, 0, int(y) * 8)[2]] for y in rts])
    rr, cc = np.nonzero(inside)
    reach[row_ti[rr], col_li[cc]] = True
    return reach


def summarise(values, frames_list, mask=None):
    v = values if mask is None else values[mask]
    v = v.ravel()
    if v.size == 0:
        return {"positions": 0}
    hist = np.bincount(v.astype(np.int64))
    out = {
        "positions": int(v.size),
        "max": int(v.max()),
        "p50": float(np.percentile(v, 50)),
        "p90": float(np.percentile(v, 90)),
        "p99": float(np.percentile(v, 99)),
        "min": int(v.min()),
        "histogram": {str(k): int(n) for k, n in enumerate(hist) if n},
    }
    for f in frames_list:
        over = int(np.count_nonzero(v > f))
        out[f"over_{f}"] = over
        out[f"over_{f}_pct"] = round(100.0 * over / v.size, 2)
    return out


def measure_act(act, c, frames_list, want_positions=True):
    t0 = time.time()
    pipe = run_pipeline(act, c)
    pg = pipe["page_grid"]
    glob = pipe["glob_grid"]
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    lefts, tops, max_cx, max_cy = camera_windows(c, act.content_w, act.content_h)
    pinned = set(pipe["pinned"])
    labels = sorted(set(np.unique(pg).tolist()) - {-1})
    referenced = presence_counts(pg, labels, cols, rows, lefts, tops)
    unpinned_ref = presence_counts(pg, labels, cols, rows, lefts, tops, weight_mask=pinned)
    needed = unpinned_ref + len(pinned)
    zones_present = presence_counts(act.zone_id, list(range(len(act.zones))), cols, rows, lefts, tops)
    reach = reachable_mask(act, c, lefts, tops)
    tiles = distinct_tiles_per_window(glob, lefts, tops, cols, rows)
    page_floor = -(-tiles // c["ART_POOL_PAGE_TILES"])

    classes = {
        "all": None,
        "interior_one_zone": zones_present <= 1,
        "seam_two_plus_zones": zones_present >= 2,
        "junction_three_plus_zones": zones_present >= 3,
    }
    res = {
        "act": act.name,
        "placements": [{"zone": z.name, "col0": c0, "row0": r0,
                        "box_tiles": list(z.words.shape[::-1]), **z.box}
                       for z, c0, r0 in act.placements],
        "content_tiles": [act.content_w, act.content_h],
        "grid_sections": pipe["grid"],
        "sections": pipe["sections"],
        "exceeds_MAX_ACT_SECTIONS": pipe["sections"] > c["MAX_ACT_SECTIONS"],
        "pool_tiles": pipe["pool_tiles"],
        "source_tiles_keyed": pipe["source_tiles"],
        "pages": pipe["pages"],
        "exceeds_PAGE_TABLE_MAX": pipe["pages"] > c["PAGE_TABLE_MAX"],
        "pinned_pages": sorted(pinned),
        "local_palette_max": pipe["local_palette_max"],
        "local_palette_refusals": pipe["local_palette_refusals"],
        "camera_range_px": [max_cx, max_cy],
        "windows": int(len(lefts) * len(tops)),
        "needed": {}, "needed_reachable": {}, "referenced_only": {},
        "distinct_tiles": {}, "any_order_page_floor": {},
    }
    for cname, m in classes.items():
        res["needed"][cname] = summarise(needed, frames_list, m)
        rm = reach if m is None else (reach & m)
        res["needed_reachable"][cname] = summarise(needed, frames_list, rm)
        res["referenced_only"][cname] = summarise(referenced, frames_list, m)
        res["distinct_tiles"][cname] = summarise(tiles, [], m)
        res["any_order_page_floor"][cname] = summarise(page_floor, frames_list, m)
    if want_positions:
        worst = {}
        for cname, m in classes.items():
            mm = np.ones_like(needed, dtype=bool) if m is None else m
            if not mm.any():
                continue
            val = np.where(mm, needed, -1)
            peak = int(val.max())
            ti, li = np.nonzero(val == peak)
            k = 0
            left, top = int(lefts[li[k]]), int(tops[ti[k]])
            pset = window_page_set_bruteforce(pg, left, top, cols, rows)
            worst[cname] = {
                "needed": peak,
                "positions_at_peak": int(len(ti)),
                "first_window_tile": {"left": left, "top": top},
                "camera_px_example": {"x": (left + c["TILE_CACHE_MARGIN_H"]) * 8 if left else 0,
                                      "y": (top + c["TILE_CACHE_MARGIN_V"]) * 8 if top else 0},
                "peak_bbox_window_tile": {"left_min": int(lefts[li].min()), "left_max": int(lefts[li].max()),
                                          "top_min": int(tops[ti].min()), "top_max": int(tops[ti].max())},
                "referenced_pages": sorted(pset),
                "zones_in_window": int(zones_present[ti[k], li[k]]),
            }
        res["worst"] = worst
    res["elapsed_s"] = round(time.time() - t0, 2)
    res["_arrays"] = (pg, lefts, tops, needed, pinned, glob, tiles)
    return res


def strip_arrays(res):
    return {k: v for k, v in res.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def control_counting(c, res, samples=200, seed=1):
    """presence_counts (integral images, numpy) vs a pure-Python direct scan, on
    random windows AND on every class's peak window."""
    pg, lefts, tops, needed, pinned, glob, tiles = res["_arrays"]
    rnd = random.Random(seed)
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    picks = [(rnd.randrange(len(tops)), rnd.randrange(len(lefts))) for _ in range(samples)]
    for w in res.get("worst", {}).values():
        ti = int(np.nonzero(tops == w["first_window_tile"]["top"])[0][0])
        li = int(np.nonzero(lefts == w["first_window_tile"]["left"])[0][0])
        picks.append((ti, li))
    bad = []
    for ti, li in picks:
        brute = window_page_set_bruteforce(pg, int(lefts[li]), int(tops[ti]), cols, rows)
        want = len(brute | pinned)
        if want != int(needed[ti, li]):
            bad.append({"top": int(tops[ti]), "left": int(lefts[li]),
                        "integral": int(needed[ti, li]), "bruteforce": want})
        wt = window_tiles_bruteforce(glob, int(lefts[li]), int(tops[ti]), cols, rows)
        if wt != int(tiles[ti, li]):
            bad.append({"top": int(tops[ti]), "left": int(lefts[li]),
                        "tiles_sweep": int(tiles[ti, li]), "tiles_bruteforce": wt})
    return {"windows_checked": len(picks), "mismatches": bad}


def control_ojz(c):
    """Replay the pipeline glue on the shipped OJZ act-1 inputs and require it to
    reproduce the committed bake exactly."""
    import fg_working_set as fws
    _zone, act1 = act_grid.project_act(ojz_strip_gen.PROJECT_JSON)
    gw, gh = act_grid.section_grid(ojz_strip_gen.PROJECT_JSON)
    data_path = os.path.join(REPO, act1["dataPath"])
    paths = ojz_strip_gen.require_editor_sections(data_path, gw * gh)
    blob = ojz_strip_gen.load_editor_tile_art(ojz_strip_gen.ZONE_TILESET_PATH)
    st = c["SECTION_SIZE"] >> 3
    words = np.zeros((gh * st, gw * st), dtype=np.uint16)
    for i, p in enumerate(paths):
        nt = np.array(ojz_strip_gen.load_editor_section_nametable(p), dtype=np.uint16)
        sy, sx = divmod(i, gw)
        words[sy * st:(sy + 1) * st, sx * st:(sx + 1) * st] = nt
    z = Zone("OJZ", words, np.zeros(words.shape, bool), {}, blob, len(blob) // 32)

    class _OjzAct(Act):
        pass
    act = _OjzAct("OJZ-control", [(z, 0, 0)], st)
    # OJZ keys: the editor's source index space is the only one; the VOID key is
    # unused (no cell is void), so the keyed pipeline sees exactly the editor tiles.
    pipe = run_pipeline(act, c)

    problems = []
    manifest = json.load(open(os.path.join(fws.GEN_DIR, "ojz_act_pool_manifest.json")))
    if pipe["pool_tiles"] != manifest["pool_tiles"]:
        problems.append(f"pool_tiles {pipe['pool_tiles']} != manifest {manifest['pool_tiles']}")
    if pipe["pages"] != len(manifest["pages"]):
        problems.append(f"pages {pipe['pages']} != manifest {len(manifest['pages'])}")
    man_pinned = [p["index"] for p in manifest["pages"] if p["pinned"]]
    if pipe["pinned"] != man_pinned:
        problems.append(f"pinned {pipe['pinned']} != manifest {man_pinned}")
    sections_ok = 0
    for s_idx, gs in enumerate(pipe["per_section_global_sets"]):
        raw = open(os.path.join(fws.GEN_DIR, f"sec{s_idx}_local_map.bin"), "rb").read()
        shipped = list(struct.unpack(f">{len(raw) // 2}H", raw))
        mine = ojz_strip_gen.build_section_local_map(gs)
        if mine != shipped:
            problems.append(f"sec{s_idx} local map differs ({len(mine)} vs {len(shipped)} entries)")
        else:
            sections_ok += 1
    # page of every cell, decoded from the SHIPPED block blobs by fg_working_set
    model = fws.Model()
    grid, _per, _air = fws.load_page_grid(model)
    shipped_grid = np.array(grid, dtype=np.int16)
    mine_grid = pipe["page_grid"][:shipped_grid.shape[0], :shipped_grid.shape[1]]
    diff = int(np.count_nonzero(shipped_grid != mine_grid))
    if diff:
        problems.append(f"{diff} cells map to a different page than the shipped block blobs")
    return {
        "subject": "OJZ act 1 (editor tree) -> replayed glue vs committed bake",
        "pool_tiles": pipe["pool_tiles"], "pages": pipe["pages"], "pinned": pipe["pinned"],
        "sections_local_map_identical": sections_ok, "sections": len(pipe["per_section_global_sets"]),
        "cells_compared": int(shipped_grid.size), "cells_differing": diff,
        "problems": problems, "ok": not problems,
    }


def control_window_model(c):
    """The camera->window map, checked against a direct re-statement of the fill's
    far-edge clamp at a spread of camera positions (including the zero clamp)."""
    out = []
    for x in (0, 7, 8, 159, 160, 161, 163, 999, 4096 + 3):
        l, r, t, b = window_for_camera(c, x, x)
        out.append({"cam": x, "cols": [l, r], "rows": [t, b],
                    "width": r - l + 1, "height": b - t + 1})
    return out


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

def pair_act(a, b, st, b_row_offset=0):
    za, zb = load_zone(a), load_zone(b)
    return Act(f"{a}|{b}", [(za, 0, 0), (zb, za.words.shape[1], b_row_offset)], st)


def junction_act(a, b, cz, st, section_align=False):
    """T-junction: A top-left, B top-right, bottoms aligned; C directly below,
    horizontally centred on the A|B seam. `section_align` pushes the junction
    row down to the next section boundary (256 tiles), so C starts its own
    section row instead of sharing one with A and B."""
    za, zb, zc = load_zone(a), load_zone(b), load_zone(cz)
    h0 = max(za.words.shape[0], zb.words.shape[0])
    if section_align:
        h0 = -(-h0 // st) * st
    seam = za.words.shape[1]
    c_col = seam - zc.words.shape[1] // 2
    shift = max(0, -c_col)               # keep every placement at a non-negative column
    return Act(f"{a}|{b} over {cz}" + (" [section-aligned]" if section_align else ""), [
        (za, shift, h0 - za.words.shape[0]),
        (zb, shift + seam, h0 - zb.words.shape[0]),
        (zc, c_col + shift, h0),
    ], st), {"seam_col": seam + shift, "junction_row": h0, "section_aligned": section_align}


def chain_act(names, st):
    placements = []
    col = 0
    for n in names:
        z = load_zone(n)
        placements.append((z, col, 0))
        col += z.words.shape[1]
    return Act("chain " + "|".join(names), placements, st)


def headline(res, frames_list, cls):
    n = res["needed"][cls]
    if not n.get("positions"):
        return None
    return {"act": res["act"], "class": cls, "positions": n["positions"], "max": n["max"],
            "p50": n["p50"], "p90": n["p90"],
            **{f"over_{f}": n[f"over_{f}"] for f in frames_list},
            **{f"over_{f}_pct": n[f"over_{f}_pct"] for f in frames_list},
            "pages": res["pages"], "pinned": len(res["pinned_pages"]),
            "distinct_tiles_max": res["distinct_tiles"][cls]["max"],
            "any_order_page_floor_max": res["any_order_page_floor"][cls]["max"]}


GAMES = {
    "s2": {"zones": lambda: list(S2_ZONES), "quick": ["EHZ", "ARZ", "MCZ", "HTZ"],
           "chain": ["EHZ", "CPZ", "ARZ", "CNZ", "HTZ", "MCZ", "OOZ", "MTZ"]},
    "s3k": {"zones": lambda: list(S3K_ZONES), "quick": ["MHZ1", "LBZ1", "CNZ1", "ICZ1"],
            "chain": ["AIZ2", "HCZ1", "MGZ1", "CNZ1", "FBZ1", "ICZ1", "LBZ1", "MHZ1", "SOZ1", "LRZ1"]},
}


def build_report(game="s2", quick=False, log=print):
    c, origin = load_constants()
    frames_list = [c["PAGE_FRAMES"], OWNER_LEVER_FRAMES]
    F, L = frames_list
    st = c["SECTION_SIZE"] >> 3
    report = {
        "tool": "tools/megaact_window_pageset.py",
        "constants": {n: {"value": c[n], "source": origin[n]} for n in NEEDED},
        "frames_compared": frames_list,
        "window": derive_window(c),
        "window_model_samples": control_window_model(c),
    }
    log("control: replaying the page pipeline glue on OJZ act 1 ...")
    ctl = control_ojz(c)
    report["control_ojz"] = ctl
    log(f"  ok={ctl['ok']} pool={ctl['pool_tiles']} pages={ctl['pages']} pinned={ctl['pinned']} "
        f"local maps identical {ctl['sections_local_map_identical']}/{ctl['sections']} "
        f"cells differing {ctl['cells_differing']}/{ctl['cells_compared']}")
    if not ctl["ok"]:
        report["refused"] = "OJZ glue control failed — no donor number is trustworthy"
        return report

    g = GAMES[game]
    zones = g["quick"] if quick else g["zones"]()
    report["game"] = game
    donor = {"root": s2disasm_root() if game == "s2" else skdisasm_dir(), "zones": {}}
    for zn in zones:
        z = load_zone(zn)
        donor["zones"][zn] = {"box_tiles_wh": list(z.words.shape[::-1]), **z.box,
                              "art_tiles": z.n_art_tiles}
    report["donor"] = donor

    # ---- singles ----
    log("singles ...")
    singles = {}
    for zn in zones:
        r = measure_act(Act(zn, [(load_zone(zn), 0, 0)], st), c, frames_list)
        singles[zn] = strip_arrays(r)
        n = r["needed"]["all"]
        log(f"  {zn:4} pages={r['pages']:3} pinned={len(r['pinned_pages'])} max={n['max']:3} "
            f"p50={n['p50']:5.1f} over{F}={n[f'over_{F}_pct']:6.2f}% over{L}={n[f'over_{L}_pct']:6.2f}%")
    report["singles"] = singles

    # ---- ordered pair matrix ----
    log("pair matrix ...")
    pairs = {}
    ctl_count = None
    for a in zones:
        for b in zones:
            if a == b:
                continue
            r = measure_act(pair_act(a, b, st), c, frames_list)
            if ctl_count is None:
                ctl_count = control_counting(c, r)
                report["control_counting"] = ctl_count
                log(f"  counting control: {ctl_count['windows_checked']} windows, "
                    f"{len(ctl_count['mismatches'])} mismatches")
                if ctl_count["mismatches"]:
                    report["refused"] = "counting control failed"
                    return report
            pairs[f"{a}|{b}"] = strip_arrays(r)
            s = r["needed"]["seam_two_plus_zones"]
            log(f"  {a}|{b}: pages={r['pages']:3} pinned={len(r['pinned_pages'])} seam max={s['max']:3} "
                f"p50={s['p50']:5.1f} over{F}={s[f'over_{F}']}/{s['positions']} over{L}={s[f'over_{L}']} "
                f"| tiles max={r['distinct_tiles']['seam_two_plus_zones']['max']} "
                f"any-order floor max={r['any_order_page_floor']['seam_two_plus_zones']['max']}")
    report["pairs"] = pairs

    ranked = sorted(pairs.values(), key=lambda r: (r["needed"]["seam_two_plus_zones"]["max"],
                                                   r["needed"]["seam_two_plus_zones"]["p50"]))
    worst_pair, calm_pair = ranked[-1], ranked[0]
    report["worst_pair"] = worst_pair["act"]
    report["calm_pair"] = calm_pair["act"]

    # ---- vertical alignment sensitivity for worst + calm pair ----
    log("vertical offset sensitivity ...")
    offsets = {}
    for label in (worst_pair["act"], calm_pair["act"]):
        a, b = label.split("|")
        za, zb = load_zone(a), load_zone(b)
        rows = []
        lo = -(zb.words.shape[0] - 30)
        hi = za.words.shape[0] - 30
        step = 16 if not quick else 64
        for off in range(lo, hi + 1, step):
            base = max(0, -off)
            act = Act(f"{a}|{b} dy={off}", [(za, 0, base), (zb, za.words.shape[1], base + off)], st)
            r = measure_act(act, c, frames_list, want_positions=False)
            s = r["needed"]["seam_two_plus_zones"]
            rows.append({"b_row_offset_tiles": off, "seam_max": s.get("max"), "seam_p50": s.get("p50"),
                         "seam_positions": s.get("positions"),
                         "seam_over_frames": s.get(f"over_{F}"), "seam_over_lever": s.get(f"over_{L}"),
                         "pages": r["pages"]})
        offsets[label] = rows
        log(f"  {label}: offsets {lo}..{hi} step {step}: seam max range "
            f"{min(x['seam_max'] for x in rows if x['seam_max'] is not None)}.."
            f"{max(x['seam_max'] for x in rows if x['seam_max'] is not None)}")
    report["vertical_offset_sensitivity"] = offsets

    # ---- junctions ----
    log("junctions ...")
    junctions = {}
    top_pairs = [r["act"] for r in ranked[::-1][:3]]
    triples = []
    for tp in top_pairs:
        a, b = tp.split("|")
        for cz in zones:
            if cz not in (a, b):
                triples.append((a, b, cz))
    ca, cb = calm_pair["act"].split("|")
    for cz in zones:
        if cz not in (ca, cb):
            triples.append((ca, cb, cz))
    seen = set()
    for a, b, cz in triples:
      for align in (False, True):
        if (a, b, cz, align) in seen:
            continue
        seen.add((a, b, cz, align))
        act, geo = junction_act(a, b, cz, st, section_align=align)
        r = measure_act(act, c, frames_list)
        rr = strip_arrays(r)
        rr["junction_geometry"] = geo
        junctions[act.name] = rr
        j = r["needed"]["junction_three_plus_zones"]
        s = r["needed"]["seam_two_plus_zones"]
        log(f"  {act.name}: pages={r['pages']} pinned={len(r['pinned_pages'])} "
            f"junction max={j.get('max')} over{F}={j.get(f'over_{F}')}/{j.get('positions')} "
            f"| seam max={s.get('max')} | junction tiles max={r['distinct_tiles']['junction_three_plus_zones'].get('max')} "
            f"floor max={r['any_order_page_floor']['junction_three_plus_zones'].get('max')}")
    report["junctions"] = junctions

    # ---- whole-game chain (the owner's real shape, one row) ----
    if not quick:
        log("chain of all zones ...")
        order = g["chain"]
        r = measure_act(chain_act(order, st), c, frames_list)
        report["chain"] = strip_arrays(r)
        s = r["needed"]["seam_two_plus_zones"]
        i = r["needed"]["interior_one_zone"]
        log(f"  chain: sections={r['sections']} pages={r['pages']} pinned={len(r['pinned_pages'])} "
            f"seam max={s['max']} interior max={i['max']} over{F} all={r['needed']['all'][f'over_{F}_pct']}% "
            f"over{L} all={r['needed']['all'][f'over_{L}_pct']}% | tiles max={r['distinct_tiles']['all']['max']} "
            f"floor max={r['any_order_page_floor']['all']['max']}")

    report["headlines"] = {
        "worst_pair_seam": headline(worst_pair, frames_list, "seam_two_plus_zones"),
        "calm_pair_seam": headline(calm_pair, frames_list, "seam_two_plus_zones"),
        "junctions": [headline(v, frames_list, "junction_three_plus_zones") for v in junctions.values()],
    }
    return report


USAGE = """Usage:
    python3 tools/megaact_window_pageset.py control
    python3 tools/megaact_window_pageset.py report --game {s2,s3k} [--json PATH] [--quick]"""


def _mode_control(rest):
    if rest:
        print(f"ERROR: unknown argument {rest[0]!r}")
        print(USAGE)
        sys.exit(1)
    c, _ = load_constants()
    derive_window(c)
    ctl = control_ojz(c)
    print(json.dumps(ctl, indent=2))
    return 0 if ctl["ok"] else 1


def _mode_report(rest):
    # the one WRITING mode: --json PATH writes the evidence file
    ap = argparse.ArgumentParser(prog="megaact_window_pageset.py report")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--quick", action="store_true", help="4 zones, coarse offsets (smoke run)")
    ap.add_argument("--game", choices=sorted(GAMES), default="s2")
    args = ap.parse_args(rest)
    rep = build_report(game=args.game, quick=args.quick, log=lambda m: print(m, flush=True))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rep, fh, separators=(",", ":"))   # compact: the committed evidence files are large
            fh.write("\n")
    if "refused" in rep:
        print("REFUSED:", rep["refused"])
        return 2
    print("finished=ok")
    return 0


# ONE list of legal modes, and it is the dispatch table (LS-15d shape,
# tools/test_cli_dispatch_refuses.py). An unknown or missing mode prints usage
# and exits 1 BEFORE any handler; nothing is a default.
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
