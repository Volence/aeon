#!/usr/bin/env python3
"""OJZ nametable strip generator.

Reads OJZ level data from the sonic_hack reference project and outputs
pre-computed nametable word arrays for the s4_engine section streaming system.

Usage:
    python3 tools/ojz_strip_gen.py test      # run self-tests
    python3 tools/ojz_strip_gen.py generate  # generate strip data files

Output: data/generated/ojz/act1/sec{N}_strips_a.bin for each OJZ section.
        data/generated/ojz/act1/act_pool_page{N}.bin (global deduped act art pool, paged).
        data/generated/ojz/act1/ojz_act_pool_manifest.emp (page count + per-page VRAM slot base).
        data/generated/ojz/act1/zone_bg.bin (zone-wide Plane B nametable, §2 A.5 T1).
        data/generated/ojz/act1/ojz_palette.bin (copied from sonic_hack).

Each file contains ALL columns for section N concatenated sequentially:
col 0 words, then col 1 words, ..., col W-1 words.
Total size per file: num_columns * STRIP_TILE_HEIGHT * 2 bytes.

Each strip covers STRIP_TILE_HEIGHT rows of the section nametable.
Each strip is a column of STRIP_TILE_HEIGHT big-endian nametable words.

Strip binary layout (WIDE_STRIP_SIZE bytes per column):
  Bytes 0 .. STRIP_NT_BYTES-1         : STRIP_TILE_HEIGHT × 2 nametable words (big-endian)
  Bytes STRIP_NT_BYTES .. +COLL_ROWS-1: COLLISION_ROWS_PER_STRIP collision bytes (path A)
  Bytes +COLL_ROWS .. +2*COLL_ROWS-1 : COLLISION_ROWS_PER_STRIP collision bytes (path B)
  Bytes +2*COLL_ROWS .. end           : STRIP_COLLISION_PAD padding bytes (0)
Total: WIDE_STRIP_SIZE = STRIP_TILE_HEIGHT*2 + 2*COLLISION_ROWS_PER_STRIP + STRIP_COLLISION_PAD

Dual-layer collision (Task 7 + §5 Task 2): each strip carries TWO collision
planes, path A followed by path B. Both are REAL attr-set indices baked from
sonic_hack's per-placement collision data (build_section_collision /
tools/collision_pipeline.py); the matching ROM tables are emitted to
data/collision/. The old priority-bit placeholder survives only as a fallback
when the sonic_hack collision sources are missing.
"""

import glob
import struct
import sys
import os
import json
import re
import shutil

# Allow running from the s4_engine root (where build.sh lives).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tile_dedupe

# Shared paths + loaders live in ojz_common (re-exported here so existing
# importers like test_bg_emit keep working). collision_pipeline also imports
# ojz_common directly, which is what breaks the old import cycle and lets us
# import it at module level below.
from ojz_common import (
    SONIC_HACK,
    LAYOUT_DIR,
    CHUNK_MAP_PATH,
    BLOCK_MAP_PATH,
    TILES_PER_BLOCK_ROW,
    TILES_PER_BLOCK_COL,
    BLOCKS_PER_CHUNK_ROW,
    BLOCKS_PER_CHUNK_COL,
    WORDS_PER_BLOCK,
    kos_decompress,
    load_block_map,
    load_chunk_map,
    load_layout,
    load_bg_layout,
)
import collision_pipeline

# ---------------------------------------------------------------------------
# Paths (editor / strip-gen specific — shared ones come from ojz_common)
# ---------------------------------------------------------------------------
OJZ_ART_PATH = os.path.join(SONIC_HACK, "art/kosinski/OJZ.bin")

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "games", "sonic4", "data", "generated", "ojz", "act1"
)

# ROM collision tables (§4.7 BINCLUDEs in main.asm) — emitted by generate()
# from the §5 collision attr-set so the table indices always match the
# collision bytes baked into the strips.
COLLISION_DIR = os.path.join(
    os.path.dirname(__file__), "..", "games", "sonic4", "data", "collision"
)

EDITOR_DIR = os.path.join(
    os.path.dirname(__file__), "..", "games", "sonic4", "data", "editor"
)
PROJECT_JSON = os.path.join(
    os.path.dirname(__file__), "..", "project.json"
)


def _project_tileset_path() -> str:
    """Resolve the zone tile-art blob path from project.json (source of truth).

    project.json's zones[0].tileset points at the editor chunk-library tile
    blob (data/editor/<zone>/chunks_tiles.bin), relative to the repo root.
    """
    with open(PROJECT_JSON, "r") as f:
        proj = json.load(f)
    return os.path.join(
        os.path.dirname(PROJECT_JSON), proj["zones"][0]["tileset"]
    )


CHUNKS_TILES_PATH = _project_tileset_path()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STRIP_TILE_HEIGHT = 256  # nametable rows per strip (full section height)

# Act art pool VRAM ceiling — the PHASE-1 shipped layout, not the end-state.
# The pool loads to tiles 0..N-1; the character DPLC region sits at tile 960
# (VRAM_TEST_SONIC) and the BG region at 1024 (BG_TILE_BASE_VRAM), so a pool
# past 960 would pass a 1472-tile check and silently DMA over live art at
# runtime. 1472 ($0000-$B7FF, SAT excluded) becomes the ceiling only when the
# spec's Phase 3 unifies BG/characters into the residency pool. Mirrors
# POOL_TILE_CEILING in constants.asm — keep in sync.
POOL_TILE_CEILING = 960
ART_POOL_PAGE_TILES = 64              # tiles per independently-decodable act art page (P2b cutover: 256->64)
PAGE_TABLE_MAX = 256                  # residency page-table ceiling (replaces POOL_TILE_CEILING as the hard cap)
SECTION_LOCAL_INDEX_MAX = 2047        # 11-bit nametable field: a section's local palette must fit
PIN_SECTION_FRACTION = 0.75           # a page is pinned if >= this fraction of sections reference it (page 0 always)
# --stress-uniquify N default (Art-streaming P2c Task 11 stress fixture): crosses
# the 2048 index line (>32 pages) AND exceeds 15 PAGE_FRAMES by ~4x (>40 pages),
# so the residency cache is forced into continuous evict/reload traffic on OJZ.
STRESS_UNIQUIFY_DEFAULT = 2600
STRESS_XOR_FALLBACK = 0xA5            # nonzero perturbation when the per-clone counter byte is 0
# (block/chunk geometry constants imported from ojz_common above)
TILES_PER_CHUNK_ROW = TILES_PER_BLOCK_ROW * BLOCKS_PER_CHUNK_ROW   # 16
TILES_PER_CHUNK_COL = TILES_PER_BLOCK_COL * BLOCKS_PER_CHUNK_COL   # 16
BYTES_PER_CHUNK = BLOCKS_PER_CHUNK_ROW * BLOCKS_PER_CHUNK_COL * 2  # 128

# Genesis nametable word bit masks
TILE_INDEX_MASK = 0x07FF   # bits 10-0: tile index (0-2047)
PALETTE_SHIFT = 13
PRIORITY_BIT = 0x8000

def extract_sec_id(path: str) -> int:
    """Sort key for OJZ_1_sec*.bin layout filenames (sec digits parse as hex)."""
    m = re.search(r'sec([0-9A-Fa-f]+)', os.path.basename(path))
    if m:
        return int(m.group(1), 16)
    return -1


def enumerate_collision_layouts() -> list[tuple[str, str]]:
    """The ONE enumeration of (sec_id, layout_path) pairs the collision walk
    bakes — used by BOTH generate() Pass 1b and gen_collision_data.real_tables
    so a standalone gen_collision_data.py run can never produce differently-
    ordered attr-set indices than the strips carry.

    Editor mode (editor_data_available()): editor section indices
    0..gridWidth*gridHeight-1 from project.json, skipping sections without a
    section_{N}.tiles.bin (generate() skips those entirely) and sections
    without a sonic_hack layout file (they bake to air anyway).

    Mapping (verified 2026-06-12): editor section index N ↔
    LAYOUT_DIR/OJZ_1_sec{N}.bin with N in DECIMAL. The editor grid is
    gridWidth×gridHeight from project.json (currently 3×3 = 9 sections,
    indices 0-8); its 256×256-tile section nametables match the
    16-chunk-wide × 16-row layout files OJZ_1_sec0..11 (header: width=16,
    fg_rows=16). The OJZ_1_secA..secD files are LEGACY 32-chunk-wide ×
    18-row layouts from an earlier section scheme and never correspond to
    editor sections. For indices 0-9 the hex-vs-decimal filename question
    is moot (identical); the editor grid would need to exceed 10 sections
    AND use decimal sec10/sec11 names before it matters — those two files
    are also 16×16 and decimal-named, so decimal is correct there too.

    Fallback mode (no editor data): the same decimal-named OJZ_1_sec{N}.bin
    files, sorted by section number. Legacy hex-named secA-D are excluded
    in BOTH modes.
    """
    pairs: list[tuple[str, str]] = []
    if editor_data_available():
        with open(PROJECT_JSON, "r") as pf:
            proj = json.load(pf)
        ojz_act1 = proj["zones"][0]["acts"][0]
        num_sections = ojz_act1["gridWidth"] * ojz_act1["gridHeight"]
        data_path = os.path.join(
            os.path.dirname(PROJECT_JSON), ojz_act1["dataPath"]
        )
        for sec_idx in range(num_sections):
            tiles_path = os.path.join(data_path, f"section_{sec_idx}.tiles.bin")
            if not os.path.isfile(tiles_path):
                continue   # generate() skips sections without editor tiles
            layout_path = os.path.join(LAYOUT_DIR, f"OJZ_1_sec{sec_idx}.bin")
            if os.path.isfile(layout_path):
                pairs.append((str(sec_idx), layout_path))
    else:
        pattern = os.path.join(LAYOUT_DIR, "OJZ_1_sec*.bin")
        for path in sorted(glob.glob(pattern), key=extract_sec_id):
            m = re.search(r'sec([0-9A-Fa-f]+)\.bin$', os.path.basename(path))
            if not m or not m.group(1).isdigit():
                continue   # legacy hex-named secA-D
            pairs.append((m.group(1), path))
    return pairs


# ---------------------------------------------------------------------------
# Strip generation
# ---------------------------------------------------------------------------

CHUNK_YFLIP_BIT = 0x0800   # bit 11 of chunk entry word — Y-flip whole block
CHUNK_XFLIP_BIT = 0x0400   # bit 10 of chunk entry word — X-flip whole block


def chunk_get_tile_word(
    chunk: list[int],
    blocks: list[list[int]],
    tile_col: int,
    tile_row: int,
) -> int:
    """Return the nametable word for tile (tile_col, tile_row) within a chunk.

    tile_col and tile_row are in [0, TILES_PER_CHUNK_ROW).
    Within a chunk: 8×8 block grid, each block 2×2 tiles.

    Chunk-level X/Y-flip flags (bits 10/11 of the chunk entry word) are
    honoured — they swap the sub-tile within the block AND toggle the H/V
    bits in the returned tile word. This matches sonic_hack's
    ProcessAndWriteBlock (`btst #3,(a0)` for Y-flip, `btst #2,(a0)` for X-flip
    in code/engines/scroll_camera.asm); without applying these, BG layouts
    that rely on flipped chunks render with the wrong orientation.
    """
    block_col = tile_col // TILES_PER_BLOCK_ROW   # 0-7
    block_row = tile_row // TILES_PER_BLOCK_COL   # 0-7
    block_entry = chunk[block_row * BLOCKS_PER_CHUNK_ROW + block_col]
    block_id = block_entry & 0x3FF                # 10-bit mask (confirmed by scroll_camera.asm)
    if block_id >= len(blocks):
        return 0  # out-of-range → transparent tile

    sub_col = tile_col & 1  # 0 or 1 within block
    sub_row = tile_row & 1  # 0 or 1 within block

    # Apply chunk-level X-flip: swap left/right tiles and toggle H-bit later
    if block_entry & CHUNK_XFLIP_BIT:
        sub_col ^= 1
    # Apply chunk-level Y-flip: swap top/bottom tiles and toggle V-bit later
    if block_entry & CHUNK_YFLIP_BIT:
        sub_row ^= 1

    word_idx = sub_row * TILES_PER_BLOCK_ROW + sub_col
    word = blocks[block_id][word_idx]

    # Toggle the tile's H/V bits to flip pixels within the tile
    if block_entry & CHUNK_XFLIP_BIT:
        word ^= tile_dedupe.NAMETABLE_H_BIT
    if block_entry & CHUNK_YFLIP_BIT:
        word ^= tile_dedupe.NAMETABLE_V_BIT

    return word


PLANE_B_W = 64       # Plane B cells horizontally
PLANE_B_H = 32       # Plane B cells vertically (= 4 chunk-rows-worth, but we only show 2)
BG_TILE_BASE_SLOT_PY = 1024   # mirrors constants.asm BG_TILE_BASE_SLOT
BG_TILE_CAPACITY_PY  = 448    # mirrors constants.asm BG_TILE_CAPACITY (usable $8000..$B7FF, SAT at $B800)


def build_bg_nametable_words(
    bg_layout: list[list[int]],
    chunks: list[list[int]],
    blocks: list[list[int]],
    col_offset: int = 0,
) -> list[int]:
    """Build a 64×32 list of raw chunk-source nametable words for Plane B.

    Samples 4 chunks of BG rows 0-1 starting at `col_offset` (= 64 tiles wide
    × 32 tiles tall = full Plane B). Different col_offsets produce visually
    distinct per-section variants for T2 fixtures.

    Returns words with original tile_index in sonic_hack's source space — the
    caller dedupes + remaps to the shared BG VRAM region.
    """
    if not bg_layout:
        raise ValueError("BG layout is empty — load_bg_layout returned no rows")

    out: list[int] = []
    for plane_row in range(PLANE_B_H):
        chunk_row = plane_row // TILES_PER_CHUNK_COL
        tile_row_in_chunk = plane_row % TILES_PER_CHUNK_COL
        if chunk_row >= len(bg_layout):
            out.extend([0] * PLANE_B_W)
            continue
        for plane_col in range(PLANE_B_W):
            chunk_col = col_offset + (plane_col // TILES_PER_CHUNK_ROW)
            tile_col_in_chunk = plane_col % TILES_PER_CHUNK_ROW
            if chunk_col >= len(bg_layout[chunk_row]):
                out.append(0)
                continue
            chunk_id = bg_layout[chunk_row][chunk_col]
            if chunk_id >= len(chunks):
                out.append(0)
                continue
            word = chunk_get_tile_word(
                chunks[chunk_id], blocks, tile_col_in_chunk, tile_row_in_chunk
            )
            out.append(word)
    return out


def emit_bg_tile_blob(
    bg_nametable_words_list,
    full_blob: bytes,
    out_path: str,
) -> tuple[dict[int, tuple[int, int]], int]:
    """Dedupe BG-referenced tiles across ONE OR MORE nametables and emit shared VRAM blob.

    Accepts a list of nametables OR a single nametable (back-compat). Walks
    every cell of every nametable, gathers unique source tiles, dedupes via
    tile_dedupe canonicalization, writes a 2-byte length header + raw deduped
    bytes (mirrors S4LZ blob shape).

    For T2 fixtures, pass [zone_nametable, sec1_variant, sec3_variant, ...] —
    the union covers tiles needed by every variant so Plane B has correct
    tile data regardless of which variant is currently drawn.

    Returns (src_to_canon, unique_tile_count).
    """
    # Normalize: accept either a flat list of words or a list-of-lists
    if bg_nametable_words_list and isinstance(bg_nametable_words_list[0], int):
        nametables = [bg_nametable_words_list]
    else:
        nametables = list(bg_nametable_words_list)

    referenced: set[int] = set()
    for nt in nametables:
        for word in nt:
            referenced.add(word & tile_dedupe.NAMETABLE_TILE_MASK)
    sorted_indices = sorted(referenced)

    raw_tiles: list[bytes] = []
    for idx in sorted_indices:
        base = idx * tile_dedupe.TILE_SIZE
        if base + tile_dedupe.TILE_SIZE <= len(full_blob):
            raw_tiles.append(full_blob[base : base + tile_dedupe.TILE_SIZE])
        else:
            raw_tiles.append(bytes(tile_dedupe.TILE_SIZE))

    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)
    src_to_canon: dict[int, tuple[int, int]] = {
        src_idx: mapping[i] for i, src_idx in enumerate(sorted_indices)
    }

    body = b"".join(unique)
    # Tier-1 move.l blit contract (BG_Init .tile_copy, engine/level/bg.emp):
    # the runtime copies longwords and SILENTLY DROPS a sub-longword tail (the
    # in-engine assert was deliberately omitted — DEBUG expansion would push
    # .skip_tiles past short-branch reach). 32-byte tiles guarantee granularity
    # by construction; assert so a format change can't feed the blit a dropped
    # tail (mirrors inject_editor_bg.py:158 — but THIS emitter is the
    # unconditional producer; the injector only runs when an editor override
    # exists).
    assert len(body) % 4 == 0, (
        f"BG tile blob must be 4-byte granular for move.l, got {len(body)}"
    )
    header = struct.pack(">H", len(body))
    with open(out_path, "wb") as f:
        f.write(header)
        f.write(body)

    return src_to_canon, len(unique)


def emit_zone_bg_layout(
    bg_nametable_words: list[int],
    src_to_canon: dict[int, tuple[int, int]],
    out_path: str,
    palette_override: int | None = None,
) -> None:
    """Emit a 64×32 nametable with tile_index fields remapped into the shared BG region.

    Each input word's tile_index is rewritten via tile_dedupe.remap_nametable_word
    to (BG_TILE_BASE_SLOT + canon_idx). The original H/V bits XOR canonicalization-
    flip-bits so visual orientation is preserved. Priority bit forced low.

    palette_override: if set (0..3), force every cell to that CRAM line. Used by
    T2 fixtures so each per-section variant tints the BG distinctively. None
    leaves chunk-derived palette bits untouched.
    """
    if len(bg_nametable_words) != PLANE_B_W * PLANE_B_H:
        raise ValueError(
            f"BG nametable has {len(bg_nametable_words)} words; expected {PLANE_B_W * PLANE_B_H}"
        )

    out = bytearray(PLANE_B_W * PLANE_B_H * 2)
    for i, word in enumerate(bg_nametable_words):
        src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
        canon_idx, flip_bits = src_to_canon.get(src_idx, (0, 0))
        slot = BG_TILE_BASE_SLOT_PY + canon_idx
        remapped = tile_dedupe.remap_nametable_word(word, slot, flip_bits)
        remapped &= ~PRIORITY_BIT          # BG always low-priority
        if palette_override is not None:
            remapped = (remapped & ~0x6000) | ((palette_override & 0x3) << 13)
        struct.pack_into(">H", out, i * 2, remapped)

    with open(out_path, "wb") as f:
        f.write(out)


def build_strips_from_nametable(
    nametable: list[list[int]],
    strip_height: int,
) -> list[list[int]]:
    """Build column strips from a 2D nametable (list of rows, each row a list of ints).

    Returns list[list[int]] — one list per column, each containing exactly
    strip_height word values (rows 0..strip_height-1).  Rows beyond strip_height
    are ignored; missing rows are filled with 0.
    """
    if not nametable:
        return []
    n_cols = len(nametable[0])
    strips = []
    for col in range(n_cols):
        words = []
        for row in range(strip_height):
            if row < len(nametable) and col < len(nametable[row]):
                words.append(nametable[row][col])
            else:
                words.append(0)
        strips.append(words)
    return strips


def load_editor_section_nametable(path: str) -> list[list[int]]:
    """Load a section_*.tiles.bin from the level editor.

    The file is a 256×256 grid of big-endian 16-bit VDP nametable words.
    Tile indices reference entries in chunks_tiles.bin.
    Returns all rows as a list-of-rows nametable.
    """
    data = open(path, "rb").read()
    GRID = 256
    expected = GRID * GRID * 2
    if len(data) != expected:
        raise ValueError(
            f"Expected {expected} bytes for {GRID}×{GRID} nametable, got {len(data)}"
        )
    words = struct.unpack(f">{GRID * GRID}H", data)
    nametable = []
    for row in range(min(STRIP_TILE_HEIGHT, GRID)):
        nametable.append(list(words[row * GRID : (row + 1) * GRID]))
    return nametable


def load_editor_tile_art(path: str) -> bytes:
    """Load raw tile art from the editor's chunks_tiles.bin."""
    return open(path, "rb").read()


def editor_data_available() -> bool:
    """Check if editor section data exists for OJZ act1."""
    sec0 = os.path.join(EDITOR_DIR, "ojz", "act1", "section_0.tiles.bin")
    return os.path.isfile(sec0) and os.path.isfile(CHUNKS_TILES_PATH)


def write_strips_to_file(
    strips: list[list[int]],
    path: str,
    coll_a: list[bytes] | None = None,
    coll_b: list[bytes] | None = None,
) -> None:
    """Write all column strips concatenated into a single binary file.

    Format per column (WIDE_STRIP_SIZE bytes):
      - STRIP_TILE_HEIGHT nametable words (big-endian)
      - COLLISION_ROWS_PER_STRIP collision bytes (path A)
      - COLLISION_ROWS_PER_STRIP collision bytes (path B)
      - STRIP_COLLISION_PAD bytes padding
    Total size: len(strips) * WIDE_STRIP_SIZE bytes.

    coll_a/coll_b: real attr-set collision grids from build_section_collision
    (one COLLISION_ROWS_PER_STRIP-byte entry per column). When omitted, fall
    back to generate_collision_bytes — the legacy priority-bit placeholder,
    kept ONLY for the no-sonic_hack-collision-sources case.
    """
    if coll_a is not None:
        if coll_b is None or len(coll_a) != len(strips) or len(coll_b) != len(strips):
            raise ValueError(
                f"collision grid columns ({len(coll_a)}/"
                f"{len(coll_b) if coll_b is not None else 'None'}) "
                f"must match strip count ({len(strips)}) for {path}"
            )
        for i in range(len(strips)):
            if (len(coll_a[i]) != COLLISION_ROWS_PER_STRIP
                    or len(coll_b[i]) != COLLISION_ROWS_PER_STRIP):
                raise ValueError(
                    f"collision column {i} has {len(coll_a[i])}/{len(coll_b[i])} "
                    f"bytes; expected {COLLISION_ROWS_PER_STRIP} for {path}"
                )
    with open(path, "wb") as f:
        for i, strip in enumerate(strips):
            for word in strip:
                f.write(struct.pack(">H", word))
            if coll_a is not None:
                f.write(coll_a[i])
                f.write(coll_b[i])
            else:
                f.write(generate_collision_bytes(strip))
            f.write(b'\x00' * STRIP_COLLISION_PAD)


def generate_section_strips(
    layout: list[list[int]],
    chunks: list[list[int]],
    blocks: list[list[int]],
) -> list[list[int]]:
    """Generate one strip (list of ints) per layout tile-column.

    Each strip is STRIP_TILE_HEIGHT words covering the full section height.

    Returns list[list[int]] — one list per column, each STRIP_TILE_HEIGHT long.
    """
    if not layout:
        return []

    width_chunks = len(layout[0])    # section width in chunks
    height_chunks = len(layout)      # section height in chunks

    # Total nametable rows from layout (each chunk = 16 tile rows)
    total_tile_rows = height_chunks * TILES_PER_CHUNK_COL
    # We clamp to STRIP_TILE_HEIGHT
    strip_rows = min(STRIP_TILE_HEIGHT, total_tile_rows)

    # One strip per *tile column* (nametable column)
    total_tile_cols = width_chunks * TILES_PER_CHUNK_ROW

    # Build a flat 2D nametable: nametable[tile_row][tile_col] = word
    nametable = []
    for tile_row in range(strip_rows):
        chunk_row = tile_row // TILES_PER_CHUNK_COL
        sub_tile_row = tile_row % TILES_PER_CHUNK_COL
        row_words = []
        for tile_col in range(total_tile_cols):
            chunk_col = tile_col // TILES_PER_CHUNK_ROW
            sub_tile_col = tile_col % TILES_PER_CHUNK_ROW

            if chunk_col >= width_chunks or chunk_row >= height_chunks:
                word = 0
            else:
                chunk_id = layout[chunk_row][chunk_col]
                if chunk_id >= len(chunks):
                    word = 0
                else:
                    word = chunk_get_tile_word(
                        chunks[chunk_id], blocks, sub_tile_col, sub_tile_row
                    )
            row_words.append(word)
        nametable.append(row_words)

    return build_strips_from_nametable(nametable, STRIP_TILE_HEIGHT)


# ---------------------------------------------------------------------------
# Tile dedupe + remap helpers (§2 A.1)
# ---------------------------------------------------------------------------

def decompress_full_ojz_art(path: str) -> bytes:
    """Decompress every Kosinski stream in OJZ.bin and concatenate.

    The source file holds multiple back-to-back streams; the original 322-tile
    helper only used stream 0. A.1 needs the full tile space because nametable
    references can land anywhere in the source's flat tile-index range.
    """
    src = open(path, "rb").read()
    out = bytearray()
    pos = 0
    while pos < len(src):
        try:
            decoded, pos = kos_decompress(src, pos)
        except (IndexError, KeyError):
            break
        if not decoded:
            break
        out.extend(decoded)
    return bytes(out)


def collect_referenced_tiles(
    all_section_strips: dict,  # sec_id → list[list[int]]
    full_tile_blob: bytes,
) -> tuple[list[int], list[bytes]]:
    """Walk every nametable word across all sections.

    Returns (sorted_indices, raw_tiles):
      sorted_indices = sorted list of unique source tile indices referenced
      raw_tiles[i]   = the 32 bytes of source tile sorted_indices[i]
                       (zero-tile if the source blob doesn't reach that index)
    """
    referenced: set[int] = set()
    for strips in all_section_strips.values():
        for col in strips:
            for word in col:
                referenced.add(word & tile_dedupe.NAMETABLE_TILE_MASK)
    sorted_indices = sorted(referenced)
    raw_tiles: list[bytes] = []
    for idx in sorted_indices:
        base = idx * tile_dedupe.TILE_SIZE
        if base + tile_dedupe.TILE_SIZE <= len(full_tile_blob):
            raw_tiles.append(full_tile_blob[base : base + tile_dedupe.TILE_SIZE])
        else:
            raw_tiles.append(bytes(tile_dedupe.TILE_SIZE))  # missing → zero tile
    return sorted_indices, raw_tiles


# ---------------------------------------------------------------------------
# Per-section local→global tables + page pinning (§4/§5 — P2b format cutover)
# ---------------------------------------------------------------------------

def build_section_local_map(section_globals) -> list[int]:
    """Build a section's local→global palette from the set of global pool slots
    it references.

    Returns local_to_global: a list where local_to_global[local_index] = global
    VRAM slot. Globals are sorted ascending for determinism (build-reproducible).
    The engine maps each block nametable word's 11-bit LOCAL index through this
    table per word at the patch/scan consumers (F-3 merge-translation) — the
    full-width global lives only in a register, so the pool is unbounded.

    INVARIANT map[0] == 0: global slot 0 (the blank tile) is force-included in
    every section's palette, so local index 0 always means blank — this is what
    lets the engine's shared all-zero staged block (its words are $0000 = local
    0) read as blank through ANY section's map. Cost: at most one map slot.

    Raises ValueError if the palette exceeds the 11-bit nametable field
    (SECTION_LOCAL_INDEX_MAX + 1 = 2048 distinct tiles). The GLOBAL pool may
    exceed 2047 tiles; only the section-LOCAL palette must fit the field.
    """
    ordered = sorted(set(section_globals) | {0})
    if len(ordered) > SECTION_LOCAL_INDEX_MAX + 1:
        raise ValueError(
            f"section references {len(ordered)} distinct tiles > "
            f"{SECTION_LOCAL_INDEX_MAX + 1}: exceeds the 11-bit local index field"
        )
    assert ordered[0] == 0, "blank-first invariant: map[0] must be global 0"
    return ordered


def mark_pinned_pages(pages, per_section_global_sets) -> list[bool]:
    """Return a list[bool] parallel to `pages`.

    A page is PINNED (never evicted) if at least PIN_SECTION_FRACTION of sections
    reference at least one of the page's global slots (act-common art). Page 0 is
    ALWAYS pinned — it holds the blank tile at global slot 0, which every air cell
    renders. Global slot of a page's first tile is the running sum of prior page
    lengths (== page_idx * ART_POOL_PAGE_TILES, since every page but the last is
    full).
    """
    n_sections = len(per_section_global_sets)
    threshold = PIN_SECTION_FRACTION * n_sections
    pinned: list[bool] = []
    base = 0
    for page_idx, page in enumerate(pages):
        page_slots = range(base, base + len(page))
        base += len(page)
        if page_idx == 0:
            pinned.append(True)
            continue
        refs = sum(1 for gs in per_section_global_sets
                   if any(slot in gs for slot in page_slots))
        pinned.append(refs >= threshold)
    return pinned


def stress_uniquify_pool(target_tiles, unique, pool_order, canon_to_pool,
                         per_section_strips, sec_ids_in_order, src_to_canon):
    """Art-streaming P2c Task 11 stress fixture (post-dedup pool inflation).

    Clone existing pool tiles with a DETERMINISTIC per-clone pixel perturbation
    and re-point a spread of block references at the clones, until the pool holds
    exactly `target_tiles` distinct tiles. NO RNG — every choice is seeded by an
    integer index, so two runs are byte-identical.

    PARENT-MATCHED (the visual-fidelity contract): a reference is only ever
    re-pointed at a clone of ITS OWN parent tile. Each chosen position's clone is a
    single-row perturbation of the exact tile that position currently renders, so
    the fixture looks like clean OJZ with a faint scratch — a bark cell stays bark,
    a vine-swag cell stays swag. (The earlier unconstrained version handed a
    position an arbitrary clone, baking full texture swaps that made "wrong-looking"
    indistinguishable from actually-wrong — defeating the zero-wrong-tiles gate.)
    Popular tiles (referenced at many chosen positions) get many clones; the pool
    still reaches N because one clone is minted per re-pointed position.

    Mutates `unique`/`pool_order`/`canon_to_pool` in place (clones are APPENDED —
    the real pool + blank tile 0 are untouched, so page 0 stays pinned/blank).
    Returns `(redirect, clone_parent)`:
      redirect      {(section_index, col, row): clone_pool_slot} — applied in Pass 5
                    (the local-index word rewrite; the original canon-flip is KEPT so
                    the clone renders in the source orientation) and folded into
                    per_section_global_sets so each section's local map covers its clones.
      clone_parent  {clone_pool_slot: parent_pool_slot} — the parent each clone was
                    minted from (the redirected position's own referenced tile); the
                    parent-match invariant / pytest reads this.

    The fixture exists to overwhelm the residency cache: `target_tiles` well above
    PAGE_FRAMES*ART_POOL_PAGE_TILES forces continuous eviction/reload.
    """
    base_pool_len = len(pool_order)
    if target_tiles <= base_pool_len:
        raise ValueError(
            f"--stress-uniquify {target_tiles} <= deduped pool size {base_pool_len}: "
            f"nothing to stress (pick N well above the real pool, e.g. "
            f"{STRESS_UNIQUIFY_DEFAULT})")
    n_clones = target_tiles - base_pool_len
    rows_per_tile = tile_dedupe.TILE_SIZE // 4          # 8 rows of 4 bytes (4bpp, 8px)

    # 1. Enumerate every re-pointable non-blank word position WITH the global pool
    #    slot it currently renders (its PARENT). A word resolving to the blank canon
    #    (pool slot 0) is skipped — the blank tile is pinned and never cloned.
    positions = []          # (s_idx, col_i, row_i, parent_slot)
    for s_idx, sec_id in enumerate(sec_ids_in_order):
        for col_i, col in enumerate(per_section_strips[sec_id]):
            for row_i, word in enumerate(col):
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                if src_idx == 0:                         # blank source tile
                    continue
                canon_idx, _flip = src_to_canon.get(src_idx, (0, 0))
                parent_slot = canon_to_pool[canon_idx]
                if parent_slot == 0:                     # resolves to the blank canon
                    continue
                positions.append((s_idx, col_i, row_i, parent_slot))
    if len(positions) < n_clones:
        raise ValueError(
            f"stress-uniquify: {len(positions)} re-pointable block references < "
            f"{n_clones} clones — pool target {target_tiles} too high for this act")

    # 2. Choose n_clones positions, evenly strided (deterministic, spreads across
    #    sections). Each chosen position mints a PARENT-MATCHED clone — a single-row
    #    perturbation of ITS OWN parent tile — and is re-pointed at it.
    step = len(positions) // n_clones                  # >= 1 (checked above)
    redirect = {}
    clone_parent = {}
    for j in range(n_clones):
        s_idx, col_i, row_i, parent_slot = positions[j * step]   # strided => distinct
        parent_canon = pool_order[parent_slot]
        tile = bytearray(unique[parent_canon])
        row = j % rows_per_tile
        xor = (j & 0xFF) or STRESS_XOR_FALLBACK
        tile[row * 4] ^= xor                           # faint scratch, same tile
        new_canon = len(unique)
        unique.append(bytes(tile))
        pool_order.append(new_canon)
        clone_slot = len(pool_order) - 1
        canon_to_pool[new_canon] = clone_slot
        redirect[(s_idx, col_i, row_i)] = clone_slot
        clone_parent[clone_slot] = parent_slot
    return redirect, clone_parent


# Repo-relative path the generated `.emp` embed()s reference (matches
# ojz_block_gen's sec_block_blobs.emp convention). OUTPUT_DIR == this in
# production; tests point OUTPUT_DIR at a tempdir and don't build the .emp.
GEN_REL_DIR = "games/sonic4/data/generated/ojz/act1"


def emit_section_local_maps(section_local_maps, out_dir) -> None:
    """Emit each section's local→global table as a u16-BE binary + a generated
    `.emp` section (Parcel-K3 style): per-section `embed()`s + OJZ_Sec_LocalMaps,
    a [*u8; N] pointer table indexed by FLAT section id (sec_y*grid_w + sec_x —
    the index TileCache_DecompressBlock computes). Consumed by act_descriptor.emp
    (Act.act_sec_local_maps). Each u16 entry = map[local_index] -> global VRAM slot.
    """
    by_id: dict[int, str] = {}
    for sec_id, local_to_global in section_local_maps:
        with open(os.path.join(out_dir, f"sec{sec_id}_local_map.bin"), "wb") as f:
            for g in local_to_global:
                f.write(struct.pack(">H", g))
        by_id[int(sec_id)] = sec_id
    n = (max(by_id) + 1) if by_id else 0
    missing = [i for i in range(n) if i not in by_id]
    if missing:
        raise RuntimeError(
            f"sec_local_maps: non-contiguous section ids {sorted(by_id)}; the "
            f"flat-id table needs 0..{n-1} (missing {missing})")
    with open(os.path.join(out_dir, "sec_local_maps.emp"), "w") as f:
        f.write("// AUTO-GENERATED by tools/ojz_strip_gen.py — DO NOT EDIT.\n")
        f.write("// OJZ Act 1 per-section local->global tile-index tables. Each u16-BE entry\n")
        f.write("// maps a block nametable word's 11-bit LOCAL index -> the GLOBAL VRAM slot;\n")
        f.write("// the engine translates local->global at block decode\n")
        f.write("// (TileCache_DecompressBlock via Act.act_sec_local_maps). OJZ_Sec_LocalMaps\n")
        f.write("// is indexed by FLAT section id (sec_y*grid_w + sec_x). Natively placed at\n")
        f.write("// the sec_local_maps section; consumed by act_descriptor.emp.\n")
        f.write("module games.sonic4.ojz_sec_local_maps_act1 in sec_local_maps\n\n")
        for i in range(n):
            sid = by_id[i]
            f.write(f'pub data OJZ_Sec{sid}_LocalMap = embed("{GEN_REL_DIR}/sec{sid}_local_map.bin")\n')
        ptrs = ", ".join(f'extern("OJZ_Sec{by_id[i]}_LocalMap")' for i in range(n))
        f.write(f"\npub data OJZ_Sec_LocalMaps: [*u8; {n}] = [{ptrs}]\n")


# ---------------------------------------------------------------------------
# Ring expansion — §4.9 camera-driven entity window
# ---------------------------------------------------------------------------

def expand_rings(ring_defs):
    """Expand pattern ring definitions to flat X-sorted list.

    Each ring_def is a tuple:
      ('individual', x, y)
      ('hline', x, y, count, spacing)
      ('vline', x, y, count, spacing)

    Returns: list of (x, y) tuples, sorted ascending by (x, y).
    """
    rings = []
    for entry in ring_defs:
        rtype = entry[0]
        x, y = entry[1], entry[2]
        if rtype == 'individual':
            rings.append((x, y))
        elif rtype == 'hline':
            count, spacing = entry[3], entry[4]
            for i in range(count):
                rings.append((x + i * spacing, y))
        elif rtype == 'vline':
            count, spacing = entry[3], entry[4]
            for i in range(count):
                rings.append((x, y + i * spacing))
    rings.sort(key=lambda r: (r[0], r[1]))
    return rings


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def test_expand_rings():
    """Test ring pattern expansion and X-sorting."""
    # H-line of 5 at spacing 0x10
    result = expand_rings([('hline', 0x80, 0x60, 5, 0x10)])
    assert result == [(0x80, 0x60), (0x90, 0x60), (0xA0, 0x60),
                      (0xB0, 0x60), (0xC0, 0x60)]

    # V-line of 3 at spacing 0x10 (same X, ascending Y)
    result = expand_rings([('vline', 0x100, 0x40, 3, 0x10)])
    assert result == [(0x100, 0x40), (0x100, 0x50), (0x100, 0x60)]

    # Mixed — sorted by X then Y
    result = expand_rings([
        ('individual', 0x200, 0x80),
        ('individual', 0x100, 0x80),
    ])
    assert result == [(0x100, 0x80), (0x200, 0x80)]

    # OJZ Sec2 full expansion
    result = expand_rings([
        ('hline', 0xC0, 0x50, 4, 0x14),
        ('vline', 0x300, 0x30, 3, 0x10),
        ('individual', 0x200, 0x70),
    ])
    assert result == [
        (0xC0, 0x50), (0xD4, 0x50), (0xE8, 0x50), (0xFC, 0x50),
        (0x200, 0x70),
        (0x300, 0x30), (0x300, 0x40), (0x300, 0x50),
    ]
    print("  test_expand_rings OK")


def test_kos_decompress():
    """Smoke test: decompress 16x16 OJZ.bin and check basic properties."""
    data = open(BLOCK_MAP_PATH, "rb").read()
    decoded, end_pos = kos_decompress(data, 0)
    assert len(decoded) > 0, "Block map decompressed to empty"
    # Decompressed data is floor-aligned to whole blocks
    num_blocks = len(decoded) // (WORDS_PER_BLOCK * 2)
    # Expect ~374 blocks for OJZ post-bugfix; old buggy decoder produced 2002.
    assert 200 < num_blocks < 800, f"Expected 200-800 blocks, got {num_blocks}"
    # Most blocks should be non-empty (correct decoder gives ~99% non-empty;
    # buggy decoder gave ~50% non-empty due to garbage bytes).
    nonempty = sum(1 for i in range(num_blocks)
                   if any(decoded[i*8 + j] for j in range(8)))
    assert nonempty / num_blocks > 0.9, (
        f"Expected >90% non-empty blocks (correct Kosinski), got {nonempty}/{num_blocks}"
    )
    print(f"  [OK] kos_decompress: {len(data)} bytes -> {len(decoded)} bytes, "
          f"{num_blocks} blocks ({nonempty} non-empty)")


def test_load_block_map():
    """Load block map and validate structure."""
    blocks = load_block_map(BLOCK_MAP_PATH)
    assert 200 < len(blocks) < 800, f"Expected 200-800 blocks, got {len(blocks)}"
    for i, blk in enumerate(blocks[:10]):
        assert len(blk) == WORDS_PER_BLOCK, (
            f"Block {i} has {len(blk)} words, expected {WORDS_PER_BLOCK}"
        )
    print(f"  [OK] load_block_map: {len(blocks)} blocks loaded")


def test_load_chunk_map():
    """Load chunk map and validate structure."""
    chunks = load_chunk_map(CHUNK_MAP_PATH)
    # Expect ~71 chunks post-bugfix; old buggy decoder gave 179.
    assert 32 < len(chunks) < 128, f"Expected 32-128 chunks, got {len(chunks)}"
    for i, ch in enumerate(chunks[:5]):
        assert len(ch) == 64, f"Chunk {i} has {len(ch)} words, expected 64"
    # All block IDs must fit in the block table.
    blocks = load_block_map(BLOCK_MAP_PATH)
    num_blocks = len(blocks)
    for ci, ch in enumerate(chunks):
        for wi, w in enumerate(ch):
            bid = w & 0x3FF
            assert bid < num_blocks, (
                f"Chunk {ci} word {wi}: block_id {bid} >= {num_blocks}"
            )
    print(f"  [OK] load_chunk_map: {len(chunks)} chunks loaded, "
          f"all block IDs valid against {num_blocks}-block table")


def test_load_layout():
    """Load sec0 layout and validate structure."""
    path = os.path.join(LAYOUT_DIR, "OJZ_1_sec0.bin")
    rows = load_layout(path)
    assert len(rows) > 0, "sec0 layout loaded 0 rows"
    width = len(rows[0])
    assert width > 0, "sec0 layout row 0 is empty"
    for r in rows:
        assert len(r) == width, f"Inconsistent row width"
    print(f"  [OK] load_layout: sec0 = {len(rows)} rows × {width} chunks")


def test_generate_strips_sec0():
    """Generate strips for sec0 and validate dimensions and word count."""
    layout = load_layout(os.path.join(LAYOUT_DIR, "OJZ_1_sec0.bin"))
    chunks = load_chunk_map(CHUNK_MAP_PATH)
    blocks = load_block_map(BLOCK_MAP_PATH)
    strips = generate_section_strips(layout, chunks, blocks)

    width_chunks = len(layout[0])
    expected_strips = width_chunks * TILES_PER_CHUNK_ROW
    assert len(strips) == expected_strips, (
        f"Expected {expected_strips} strips, got {len(strips)}"
    )
    for i, s in enumerate(strips):
        assert len(s) == STRIP_TILE_HEIGHT, (
            f"Strip {i}: {len(s)} words, expected {STRIP_TILE_HEIGHT}"
        )
    print(
        f"  [OK] generate_strips_sec0: {len(strips)} strips × "
        f"{STRIP_TILE_HEIGHT} words each"
    )


def test_column_layout_correctness():
    """Test A: column layout with synthetic data where cell = row*10 + col."""
    nametable = [[r * 10 + c for c in range(4)] for r in range(STRIP_TILE_HEIGHT + 4)]
    strips = build_strips_from_nametable(nametable, STRIP_TILE_HEIGHT)
    assert len(strips) == 4, f"Expected 4 strips, got {len(strips)}"
    assert strips[2][0] == 2,  f"col 2 row 0: expected 2, got {strips[2][0]}"
    assert strips[2][3] == 32, f"col 2 row 3: expected 32, got {strips[2][3]}"
    assert strips[0][STRIP_TILE_HEIGHT - 1] == (STRIP_TILE_HEIGHT - 1) * 10, \
        "Last row of strip 0 wrong"
    print("  PASS: column layout correctness")


def test_explicit_truncation():
    """Test B: strips must be exactly STRIP_TILE_HEIGHT rows."""
    tall = [[c for c in range(8)] for r in range(STRIP_TILE_HEIGHT + 10)]
    tall_strips = build_strips_from_nametable(tall, STRIP_TILE_HEIGHT)
    assert all(len(s) == STRIP_TILE_HEIGHT for s in tall_strips), \
        "Strips must be exactly STRIP_TILE_HEIGHT rows"
    print(f"  PASS: strips are exactly {STRIP_TILE_HEIGHT} rows")


def test_binary_round_trip():
    """Test C: write strips to temp file, read back, verify first word and total size."""
    import tempfile
    test_strips = [[r + c * 100 for r in range(STRIP_TILE_HEIGHT)] for c in range(3)]
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as tf:
        tmp = tf.name
    write_strips_to_file(test_strips, tmp)
    data = open(tmp, 'rb').read()
    assert len(data) == 3 * WIDE_STRIP_SIZE, f"Size mismatch: {len(data)}"
    first_word = struct.unpack_from('>H', data, 0)[0]
    assert first_word == test_strips[0][0], \
        f"First word: expected {test_strips[0][0]}, got {first_word}"
    os.unlink(tmp)
    print("  PASS: binary round-trip")


def test_section_collision_sec0():
    """Bake sec0 (fallback-mode data) and validate the real collision grids."""
    index_a, index_b, profiles, angles = \
        collision_pipeline.load_collision_sources(SONIC_HACK)
    layout = load_layout(os.path.join(LAYOUT_DIR, "OJZ_1_sec0.bin"))
    chunks = load_chunk_map(CHUNK_MAP_PATH)

    attrset = collision_pipeline.AttrSet()
    coll_a, coll_b = build_section_collision(
        layout, chunks, index_a, index_b, profiles, angles, attrset
    )

    n_cols = len(layout[0]) * TILES_PER_CHUNK_ROW
    assert len(coll_a) == n_cols and len(coll_b) == n_cols, (
        f"expected {n_cols} columns, got {len(coll_a)}/{len(coll_b)}"
    )
    assert all(len(c) == COLLISION_ROWS_PER_STRIP for c in coll_a + coll_b), \
        "every column must carry COLLISION_ROWS_PER_STRIP bytes"

    # (2) every baked byte indexes into the attr-set
    n_entries = len(attrset.entries)
    for col_a, col_b in zip(coll_a, coll_b):
        assert all(byte < n_entries for byte in col_a), \
            f"plane A byte >= attr-set size {n_entries}"
        assert all(byte < n_entries for byte in col_b), \
            f"plane B byte >= attr-set size {n_entries}"

    # Sanity: sec0 must contain SOME solid collision
    assert any(any(col) for col in coll_a), "sec0 baked to all-air plane A"

    # (1) plane A ≠ plane B somewhere iff the source data diverges for a
    # block actually placed within sec0's baked area (computed from the
    # source, not hardcoded).
    src_diverges = False
    scratch = collision_pipeline.AttrSet()
    covered_rows = COLLISION_ROWS_PER_STRIP // BLOCKS_PER_CHUNK_COL  # 16 chunk rows
    for chunk_row in range(min(len(layout), covered_rows)):
        for chunk_col in range(len(layout[chunk_row])):
            chunk_id = layout[chunk_row][chunk_col]
            if chunk_id >= len(chunks):
                continue
            for word in chunks[chunk_id]:
                a, b = collision_pipeline.bake_cell(
                    word, index_a, index_b, profiles, angles, scratch
                )
                if a != b:
                    src_diverges = True
    grids_diverge = any(ca != cb for ca, cb in zip(coll_a, coll_b))
    assert grids_diverge == src_diverges, (
        f"plane divergence mismatch: grids {grids_diverge}, source {src_diverges}"
    )

    # (3) both 8px tile columns of any block carry identical bytes — pairs
    # (2i, 2i+1) never straddle a block (or chunk) boundary.
    for col in range(0, n_cols, 2):
        assert coll_a[col] == coll_a[col + 1], f"plane A cols {col}/{col+1} differ"
        assert coll_b[col] == coll_b[col + 1], f"plane B cols {col}/{col+1} differ"

    print(f"  [OK] test_section_collision_sec0: {n_cols} cols, "
          f"{n_entries} attr-set entries, planes diverge={grids_diverge} "
          f"(matches source)")


def test_collision_emit_identity():
    """gen_collision_data.real_tables() == a generate()-equivalent walk.

    Pins the §5 invariant: BOTH emit paths enumerate sections via
    enumerate_collision_layouts(), so a standalone gen_collision_data.py run
    can never rewrite data/collision/ with differently-ordered attr-set
    indices than the strips carry.
    """
    import gen_collision_data

    pairs = enumerate_collision_layouts()
    assert pairs, "enumerate_collision_layouts returned no sections"
    for sec_id, layout_path in pairs:
        assert sec_id.isdigit(), f"legacy hex section leaked in: {sec_id}"
        assert os.path.basename(layout_path) == f"OJZ_1_sec{sec_id}.bin", \
            f"sec_id/path mismatch: {sec_id} vs {layout_path}"

    tables, n_entries = gen_collision_data.real_tables()

    # Generate-equivalent walk: same enumeration, same shared attr-set.
    index_a, index_b, profiles, angles = \
        collision_pipeline.load_collision_sources(SONIC_HACK)
    chunks = load_chunk_map(CHUNK_MAP_PATH)
    attrset = collision_pipeline.AttrSet()
    for _sec_id, layout_path in pairs:
        layout = load_layout(layout_path)
        if not layout:
            continue
        build_section_collision(
            layout, chunks, index_a, index_b, profiles, angles, attrset
        )
    expected = collision_pipeline.emit_tables(attrset)

    assert n_entries == len(attrset.entries), (
        f"attr-set size diverged: real_tables {n_entries} vs "
        f"generate-equivalent walk {len(attrset.entries)}"
    )
    assert tables == expected, \
        "real_tables() tables diverge from the generate-equivalent walk"
    print(f"  [OK] test_collision_emit_identity: {len(pairs)} sections, "
          f"{n_entries} attr-set entries, all four tables identical")


def test_full_pipeline_runs():
    """Smoke test the whole generate() pipeline produces a deduped pool."""
    import tempfile
    global OUTPUT_DIR, COLLISION_DIR
    saved = OUTPUT_DIR
    saved_coll = COLLISION_DIR
    with tempfile.TemporaryDirectory() as td:
        OUTPUT_DIR = td
        COLLISION_DIR = os.path.join(td, "collision")
        try:
            generate()
            # Global act art pool: one set of independently-decodable pages.
            import glob
            page_files = sorted(glob.glob(os.path.join(td, "act_pool_page*.bin")))
            assert len(page_files) > 0, "no act art pool pages written"
            for f in page_files:
                size = os.path.getsize(f)
                assert size % 32 == 0, f"{f} size {size} not a multiple of 32"
                assert size <= ART_POOL_PAGE_TILES * 32, \
                    f"{f} exceeds one page ({ART_POOL_PAGE_TILES} tiles)"
            manifest_path = os.path.join(td, "ojz_act_pool_manifest.emp")
            assert os.path.exists(manifest_path), "ojz_act_pool_manifest.emp not written"
            assert os.path.exists(os.path.join(td, "ojz_act_pool_manifest.json")), \
                "manifest v2 JSON sidecar not written"
            assert os.path.exists(os.path.join(td, "sec_local_maps.emp")), \
                "sec_local_maps.emp not written"
            # sidecar shape + pinned page 0
            with open(os.path.join(td, "ojz_act_pool_manifest.json")) as jf:
                side = json.load(jf)
            assert side["version"] == 2 and side["page_tiles"] == ART_POOL_PAGE_TILES
            assert len(side["pages"]) == len(page_files)
            assert side["pages"][0]["pinned"] is True, "page 0 must always be pinned"
            # (Collision tables are no longer emitted by generate() — they're the
            # fixed imported S&K set written by tools/import_sk_collision.py.)
        finally:
            OUTPUT_DIR = saved
            COLLISION_DIR = saved_coll
    print("  [OK] test_full_pipeline_runs: all act art pool pages fit one page each")


def test_section_local_map_round_trip():
    """word -> local -> global == original global; palette/priority/flip preserved."""
    section_globals = [0, 5, 900, 42, 42]         # dupes + unsorted
    l2g = build_section_local_map(section_globals)
    assert l2g == [0, 5, 42, 900], f"expected sorted-unique, got {l2g}"
    g2l = {g: i for i, g in enumerate(l2g)}
    high = 0x8000 | (2 << 13) | tile_dedupe.NAMETABLE_V_BIT   # pri=1, pal=2, V=1
    for g in (0, 5, 42, 900):
        word_local = tile_dedupe.remap_nametable_word(high, g2l[g], 0)
        local = word_local & tile_dedupe.NAMETABLE_TILE_MASK
        assert l2g[local] == g, f"round-trip broke for global {g}"
        assert (word_local & ~tile_dedupe.NAMETABLE_TILE_MASK) == high, \
            "high bits (pal/pri/flip) not preserved"
    print("  PASS: section local map round-trip")


def test_page_split_covers_pool_exactly():
    """Pages partition the pool with no gaps/overlaps; all but the last are full."""
    pool = list(range(200))
    pages = tile_dedupe.split_pool_into_pages(pool, ART_POOL_PAGE_TILES)
    assert [x for p in pages for x in p] == pool, "pages do not cover the pool exactly"
    assert all(len(p) == ART_POOL_PAGE_TILES for p in pages[:-1]), "non-final page not full"
    assert 0 < len(pages[-1]) <= ART_POOL_PAGE_TILES
    print("  PASS: page split covers pool exactly")


def test_unbounded_pool_over_2048_tiles():
    """A >2048-tile GLOBAL pool splits into >32 pages (unbounded index proof); a
    section's LOCAL palette still fits the 11-bit nametable field."""
    pool = list(range(2600))
    pages = tile_dedupe.split_pool_into_pages(pool, ART_POOL_PAGE_TILES)
    assert len(pages) > 32, f"expected >32 pages for a 2600-tile pool, got {len(pages)}"
    assert len(pages) <= PAGE_TABLE_MAX
    # a section referencing 2000 distinct globals scattered across the whole pool
    section_globals = list(range(1000)) + list(range(1600, 2600))   # 2000 distinct, spans 0..2599
    l2g = build_section_local_map(section_globals)
    assert len(l2g) == 2000
    assert len(l2g) - 1 <= SECTION_LOCAL_INDEX_MAX, "local indices must fit 11 bits"
    print("  PASS: unbounded >2048-tile pool, >32 pages, local palette fits")


def test_section_over_2047_tiles_fails():
    """A section referencing >2048 distinct tiles overflows the local index and
    must fail LOUDLY at generation (the unbounded-index guard)."""
    build_section_local_map(list(range(2048)))    # exactly 2048 is fine (0..2047)
    try:
        build_section_local_map(list(range(2049)))
    except ValueError:
        print("  PASS: >2047-distinct-tile section fails loudly")
        return
    raise AssertionError("expected ValueError for a 2049-distinct-tile section")


def test_mark_pinned_pages():
    """Page 0 always pinned; a page most sections use is pinned; a rare page is not."""
    # 4 pages of 64 slots each; slots 0..255
    pages = [list(range(0, 64)), list(range(64, 128)),
             list(range(128, 192)), list(range(192, 256))]
    # 4 sections: all use page 1 (>=75%); only 1 uses page 3 (<75%)
    sections = [
        {0, 70},          # page0, page1
        {80},             # page1
        {90},             # page1
        {100, 200},       # page1, page3
    ]
    pinned = mark_pinned_pages(pages, sections)
    assert pinned[0] is True, "page 0 must always be pinned"
    assert pinned[1] is True, "page 1 used by 100% of sections must be pinned"
    assert pinned[2] is False, "page 2 used by 0 sections must not be pinned"
    assert pinned[3] is False, "page 3 used by 25% of sections must not be pinned"
    print("  PASS: page pin heuristic")


def _fabricate_stress_inputs(base_pool=600, cols=48, rows=64, n_sections=9):
    """Fabricate deduped-pool + per-section strips shaped like generate()'s
    Pass-4 outputs, donor-free, for the stress-uniquify unit tests. Words carry
    a tile index in 1..base_pool-1 (blank slot 0 never referenced) with the high
    pal/pri/flip bits zero; src == canon == pool slot for the fabricated data, so
    src_to_canon is the identity {i: (i, 0)}."""
    unique = [bytes([i & 0xFF, (i >> 8) & 0xFF]) + bytes(tile_dedupe.TILE_SIZE - 2)
              for i in range(base_pool)]
    unique[0] = tile_dedupe.BLANK_TILE                     # slot 0 = blank
    pool_order = list(range(base_pool))
    canon_to_pool = {c: i for i, c in enumerate(pool_order)}
    src_to_canon = {i: (i, 0) for i in range(base_pool)}   # identity (no flip)
    sec_ids = [str(s) for s in range(n_sections)]
    per_section_strips = {}
    for s in range(n_sections):
        cols_list = []
        for c in range(cols):
            col = [1 + ((s * 131 + c * 17 + r * 7) % (base_pool - 1))
                   for r in range(rows)]
            cols_list.append(col)
        per_section_strips[str(s)] = cols_list
    return unique, pool_order, canon_to_pool, per_section_strips, sec_ids, src_to_canon


def _ref_slot(strips, sec_ids, canon_to_pool, src_to_canon, s_idx, col_i, row_i):
    """The pool slot a strip word actually renders (its parent), resolved the way
    generate() Pass 5 does: word -> src -> canon -> global slot."""
    word = strips[sec_ids[s_idx]][col_i][row_i]
    canon_idx, _flip = src_to_canon[word & tile_dedupe.NAMETABLE_TILE_MASK]
    return canon_to_pool[canon_idx]


def test_stress_uniquify_generation_and_pages():
    """N=2600 stress inflation succeeds, produces >40 pages, and every clone is
    referenced by exactly one re-pointed block position (byte-distinct from parent)."""
    N = STRESS_UNIQUIFY_DEFAULT
    unique, pool_order, canon_to_pool, strips, sec_ids, s2c = _fabricate_stress_inputs()
    base_len = len(pool_order)
    redirect, clone_parent = stress_uniquify_pool(
        N, unique, pool_order, canon_to_pool, strips, sec_ids, s2c)

    assert len(pool_order) == N, f"pool inflated to {len(pool_order)}, expected {N}"
    assert unique[pool_order[0]] == tile_dedupe.BLANK_TILE, "blank slot 0 must be untouched"
    pages = tile_dedupe.split_pool_into_pages(pool_order, ART_POOL_PAGE_TILES)
    assert len(pages) > 40, f"expected >40 pages for N={N}, got {len(pages)}"
    assert len(pages) <= PAGE_TABLE_MAX

    n_clones = N - base_len
    clone_slots = set(range(base_len, N))                 # clones appended contiguously
    assert set(redirect.values()) == clone_slots, "every clone must be referenced once"
    assert len(redirect) == n_clones, "one re-pointed position per clone (no collisions)"
    # perturbation actually changed bytes: each clone differs from its OWN parent tile
    for clone_slot in range(base_len, N, 137):            # sample
        parent_slot = clone_parent[clone_slot]
        assert unique[pool_order[clone_slot]] != unique[pool_order[parent_slot]], \
            f"clone {clone_slot} not perturbed from parent {parent_slot}"
    print(f"  PASS: stress-uniquify N={N} -> {len(pages)} pages, {n_clones} clones")


def test_stress_uniquify_parent_matched():
    """VISUAL-FIDELITY CONTRACT: every re-pointed reference is re-pointed at a clone
    of ITS OWN parent tile — a single-row scratch perturbation of the exact tile that
    position originally rendered. No cross-texture swaps (a bark cell never lands on a
    swag-clone)."""
    N = STRESS_UNIQUIFY_DEFAULT
    unique, pool_order, canon_to_pool, strips, sec_ids, s2c = _fabricate_stress_inputs()
    redirect, clone_parent = stress_uniquify_pool(
        N, unique, pool_order, canon_to_pool, strips, sec_ids, s2c)
    tsz = tile_dedupe.TILE_SIZE
    for (s_idx, col_i, row_i), clone_slot in redirect.items():
        parent_slot = clone_parent[clone_slot]
        ref_slot = _ref_slot(strips, sec_ids, canon_to_pool, s2c, s_idx, col_i, row_i)
        assert parent_slot == ref_slot, (
            f"clone {clone_slot} minted from parent {parent_slot} but the re-pointed "
            f"position renders {ref_slot} — CROSS-TEXTURE SWAP")
        parent_tile = unique[pool_order[parent_slot]]
        clone_tile = unique[pool_order[clone_slot]]
        assert clone_tile != parent_tile, "clone must be perturbed from its parent"
        diff_rows = sum(1 for k in range(0, tsz, 4)
                        if clone_tile[k:k + 4] != parent_tile[k:k + 4])
        assert diff_rows == 1, \
            f"clone {clone_slot} differs from parent in {diff_rows} rows, expected 1 (faint scratch)"
    print("  PASS: stress-uniquify parent-matched (no cross-texture swaps)")


def test_stress_uniquify_local_tables_valid():
    """After inflation + redirect fold-in, every section's local→global map fits
    the 11-bit field and each re-pointed clone slot round-trips local→global."""
    N = STRESS_UNIQUIFY_DEFAULT
    unique, pool_order, canon_to_pool, strips, sec_ids, s2c = _fabricate_stress_inputs()
    redirect, _clone_parent = stress_uniquify_pool(
        N, unique, pool_order, canon_to_pool, strips, sec_ids, s2c)

    # Rebuild per-section global sets the way generate() Pass 4/5 does, folding in
    # the redirect clones, then build + validate each section's local map.
    per_section_globals = []
    for s_idx, sec_id in enumerate(sec_ids):
        gs = set()
        for col in strips[sec_id]:
            for word in col:
                gs.add(canon_to_pool[word & tile_dedupe.NAMETABLE_TILE_MASK])
        per_section_globals.append(gs)
    for (s_idx, _c, _r), slot in redirect.items():
        per_section_globals[s_idx].add(slot)

    for s_idx, gs in enumerate(per_section_globals):
        l2g = build_section_local_map(gs)                 # raises if > 2047 distinct
        g2l = {g: i for i, g in enumerate(l2g)}
        assert len(l2g) - 1 <= SECTION_LOCAL_INDEX_MAX
        # each clone re-pointed into this section must resolve local->global
        for (rs, _c, _r), slot in redirect.items():
            if rs == s_idx:
                assert g2l[slot] < len(l2g) and l2g[g2l[slot]] == slot
    print("  PASS: stress-uniquify local tables valid")


def test_stress_uniquify_deterministic():
    """Two independent runs are byte-identical (seeded by index, no RNG)."""
    N = STRESS_UNIQUIFY_DEFAULT
    u1, p1, c1, s1, ids1, s2c1 = _fabricate_stress_inputs()
    r1, cp1 = stress_uniquify_pool(N, u1, p1, c1, s1, ids1, s2c1)
    u2, p2, c2, s2, ids2, s2c2 = _fabricate_stress_inputs()
    r2, cp2 = stress_uniquify_pool(N, u2, p2, c2, s2, ids2, s2c2)
    assert r1 == r2, "redirect map differs between runs"
    assert cp1 == cp2, "clone-parent map differs between runs"
    assert u1 == u2, "cloned tile bytes differ between runs"
    assert p1 == p2, "pool order differs between runs"
    print("  PASS: stress-uniquify deterministic across runs")


def test_stress_uniquify_rejects_small_target():
    """N below the deduped pool size fails loudly (nothing to stress)."""
    unique, pool_order, canon_to_pool, strips, sec_ids, s2c = _fabricate_stress_inputs(base_pool=600)
    try:
        stress_uniquify_pool(500, unique, pool_order, canon_to_pool, strips, sec_ids, s2c)
    except ValueError:
        print("  PASS: stress-uniquify rejects N <= pool size")
        return
    raise AssertionError("expected ValueError for N <= deduped pool size")


def run_tests():
    """Run all self-tests."""
    print("Running ojz_strip_gen tests...")
    test_expand_rings()
    test_kos_decompress()
    test_load_block_map()
    test_load_chunk_map()
    test_load_layout()
    test_generate_strips_sec0()
    test_column_layout_correctness()
    test_explicit_truncation()
    test_binary_round_trip()
    test_full_pipeline_runs()
    # This list is the ONLY automated invocation of these tests: the file is
    # not collectible by pytest (not test_*.py, no conftest anywhere), so a
    # test function not listed here runs NOWHERE. The stress-uniquify family
    # guards the parent-match re-pointing fix (no cross-texture swaps); the
    # pool/section tests guard the unbounded-pool -> 2047-local contract.
    test_section_collision_sec0()
    test_collision_emit_identity()
    test_section_local_map_round_trip()
    test_page_split_covers_pool_exactly()
    test_unbounded_pool_over_2048_tiles()
    test_section_over_2047_tiles_fails()
    test_mark_pinned_pages()
    test_stress_uniquify_generation_and_pages()
    test_stress_uniquify_parent_matched()
    test_stress_uniquify_local_tables_valid()
    test_stress_uniquify_deterministic()
    test_stress_uniquify_rejects_small_target()
    print("All tests passed")


# ---------------------------------------------------------------------------
# Collision byte generation (§4.7 — embedded in wider strips)
# ---------------------------------------------------------------------------

COLLISION_ROWS_PER_STRIP = STRIP_TILE_HEIGHT // 2   # 128 collision cells (16px each)
# Two collision planes (path A + path B) per strip; path B = copy of path A for OJZ.
STRIP_COLLISION_PAD = 8                              # pad to even power-of-2 alignment
WIDE_STRIP_SIZE = (STRIP_TILE_HEIGHT * 2
                   + 2 * COLLISION_ROWS_PER_STRIP
                   + STRIP_COLLISION_PAD)            # 776 bytes (512 NT + 2x128 collision planes + 8 pad)


def generate_collision_bytes(strip_words: list[int]) -> bytes:
    """LEGACY placeholder collision for one strip column (path A + path B).

    Only used when the sonic_hack collision sources are missing (see
    _try_load_collision_sources). The real path is build_section_collision,
    which bakes per-placement attr-set indices.

    Path A: mark a cell solid (type 1) if its nametable words have the VDP
    priority bit set (bit 15). In OJZ, sky/cloud tiles use priority 0 while
    ground/terrain tiles use priority 1. Path B: copy of path A.

    Returns: path_A_bytes (COLLISION_ROWS_PER_STRIP) + path_B_bytes (COLLISION_ROWS_PER_STRIP)
    """
    collision_a = bytearray(COLLISION_ROWS_PER_STRIP)
    for cell in range(COLLISION_ROWS_PER_STRIP):
        top_word = strip_words[cell * 2]
        bot_word = strip_words[cell * 2 + 1] if cell * 2 + 1 < len(strip_words) else 0
        if (top_word & 0x8000) or (bot_word & 0x8000):
            collision_a[cell] = 1
    # Path B = copy of path A (placeholder has no per-path source data)
    collision_b = bytes(collision_a)
    return bytes(collision_a) + collision_b


def _try_load_collision_sources():
    """Load the sonic_hack collision sources, or None with a LOUD warning.

    Returns (index_a, index_b, profiles, angles) on success. On failure the
    strip generator falls back to the priority-bit placeholder
    (generate_collision_bytes) and rewrites data/collision/ with the
    matching STUB tables (collision_pipeline.emit_stub_tables, type 1 =
    flat full block) so placeholder strip bytes (0/1) are never paired
    with stale real attr-set tables.
    """
    try:
        return collision_pipeline.load_collision_sources(SONIC_HACK)
    except (OSError, ValueError) as exc:
        print("!" * 72)
        print(f"WARNING: sonic_hack collision sources unavailable: {exc}")
        print("WARNING: strips get PRIORITY-BIT PLACEHOLDER collision (0/1),")
        print("WARNING: and data/collision/ ROM tables are rewritten as STUBS.")
        print("!" * 72)
        return None


def build_section_collision(
    layout: list[list[int]],
    chunks: list[list[int]],
    index_a: bytes,
    index_b: bytes,
    profiles: bytes,
    angles: bytes,
    attrset,
) -> tuple[list[bytes], list[bytes]]:
    """Bake one section's real collision grids from sonic_hack data (§5 Task 2).

    Per tile column (8px) × collision row (16px): bake the covering 16×16
    block placement to (a_byte, b_byte) attr-set indices via
    collision_pipeline.bake_cell. Section = 16×16 chunks = 256 tile cols ×
    128 collision rows (columns derived from layout width; rows fixed at
    COLLISION_ROWS_PER_STRIP — layout rows beyond that are clamped, exactly
    like the strip nametable clamps at STRIP_TILE_HEIGHT).

    For cell (tile_col, coll_row):
      chunk_col = tile_col // 16, chunk_row = coll_row // 8,
      block_col = (tile_col % 16) // 2, block_row = coll_row % 8,
      word = chunks[chunk_id][block_row*8 + block_col]
      where chunk_id = layout[chunk_row][chunk_col]
    (guards: chunk_row/col beyond layout bounds, or chunk_id >= len(chunks)
    → air, byte 0). BOTH 8px tile columns of one block share the block's
    baked bytes.

    Returns (coll_a, coll_b), oriented per-COLUMN to match the strips
    structure write_strips_to_file consumes: coll_a[tile_col] is a bytes
    object of COLLISION_ROWS_PER_STRIP path-A bytes (collision rows top to
    bottom), written verbatim after the column's nametable words.
    """
    n_cols = (len(layout[0]) if layout else 0) * TILES_PER_CHUNK_ROW
    cache: dict[int, tuple[int, int]] = {}   # chunk-entry word → (a, b)
    coll_a: list[bytes] = []
    coll_b: list[bytes] = []
    for tile_col in range(n_cols):
        col_a = bytearray(COLLISION_ROWS_PER_STRIP)
        col_b = bytearray(COLLISION_ROWS_PER_STRIP)
        chunk_col = tile_col // TILES_PER_CHUNK_ROW
        block_col = (tile_col % TILES_PER_CHUNK_ROW) // TILES_PER_BLOCK_ROW
        for coll_row in range(COLLISION_ROWS_PER_STRIP):
            chunk_row = coll_row // BLOCKS_PER_CHUNK_COL
            block_row = coll_row % BLOCKS_PER_CHUNK_COL
            if chunk_row >= len(layout) or chunk_col >= len(layout[chunk_row]):
                continue                     # beyond layout → air
            chunk_id = layout[chunk_row][chunk_col]
            if chunk_id >= len(chunks):
                continue                     # out-of-range chunk → air
            word = chunks[chunk_id][block_row * BLOCKS_PER_CHUNK_ROW + block_col]
            baked = cache.get(word)
            if baked is None:
                baked = collision_pipeline.bake_cell(
                    word, index_a, index_b, profiles, angles, attrset
                )
                cache[word] = baked
            col_a[coll_row], col_b[coll_row] = baked
        coll_a.append(bytes(col_a))
        coll_b.append(bytes(col_b))
    return coll_a, coll_b


def load_base_bank():
    """Load the imported S&K base bank (heightmaps + angles) the bake draws shapes
    from. Written by tools/import_sk_collision.py to data/collision/base/."""
    base = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "games", "sonic4", "data", "collision", "base"))
    hm = open(os.path.join(base, "heightmaps.bin"), "rb").read()
    an = open(os.path.join(base, "angles.bin"), "rb").read()
    return hm, an


def apply_editor_collision_overlay(grids, sec_id, base_profiles, base_angles, attrset):
    """Bake Aurora's editor collision into the section's collision grids when the
    section has been authored (AUTHORITATIVE / WYSIWYG). Each 16px cell of the
    `.collattr.bin` is a 16-bit BIG-ENDIAN packed cell word (shape | X/Y-flip |
    per-plane solidity, see collision-cell-word.ts). bake_plane_cell resolves the
    flip + solidity against the base bank and INTERNS the result into the shared
    `attrset`, returning the runtime 1-byte attr index — so the in-game collision
    matches the editor (painted = solid, erased/air = 0) and only the combos
    actually painted reach the ROM tables. A section with NO editor file keeps its
    (air) baseline unchanged.

    `grids` = (coll_a, coll_b), each a list of per-column bytes(COLLISION_ROWS_
    PER_STRIP). Editor data is 256×256 cells (one 16-bit word per 8px tile); a
    16px collision row samples the top tile row (even rows). Returns the new
    grids, or the originals unchanged when no editor file exists for the section."""
    coll_a, coll_b = grids
    base = os.path.join(EDITOR_DIR, "ojz", "act1")
    path_a = os.path.join(base, f"section_{sec_id}.collattr.bin")
    if not os.path.isfile(path_a):
        return grids
    W = STRIP_TILE_HEIGHT                       # 256 tiles wide / tall
    expect = W * W * 2                          # 16-bit words: 2 bytes per cell
    a = open(path_a, "rb").read()
    if len(a) != expect:
        print(f"  WARNING: {path_a} is {len(a)}B, expected {expect}; "
              f"ignoring editor collision for sec {sec_id}")
        return grids
    path_b = os.path.join(base, f"section_{sec_id}.collattrb.bin")
    b = open(path_b, "rb").read() if os.path.isfile(path_b) else None
    if b is not None and len(b) != expect:
        b = None                                # malformed path B → mirror A

    def word(buf, o):                           # big-endian (Aurora serializeCollAttr)
        return (buf[2 * o] << 8) | buf[2 * o + 1]

    out_a, out_b = [], []
    nonair = 0
    for col in range(len(coll_a)):
        if col < W:
            ea = bytearray(COLLISION_ROWS_PER_STRIP)   # authoritative: start from air
            eb = bytearray(COLLISION_ROWS_PER_STRIP)
            for cr in range(COLLISION_ROWS_PER_STRIP):
                o = (cr * 2) * W + col           # top tile row of the 16px cell
                wa = word(a, o)
                wb = word(b, o) if b is not None else wa
                ea[cr] = collision_pipeline.bake_plane_cell(wa, base_profiles, base_angles, attrset)
                eb[cr] = collision_pipeline.bake_plane_cell(wb, base_profiles, base_angles, attrset)
                if ea[cr]:
                    nonair += 1
            out_a.append(bytes(ea))
            out_b.append(bytes(eb))
        else:                                    # beyond editor width → keep engine
            out_a.append(coll_a[col])
            out_b.append(coll_b[col])
    print(f"  sec {sec_id}: editor collision baked ({nonair} non-air cells)")
    return out_a, out_b


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def require_donor():
    """Fail LOUDLY if a re-bake is asked for without the inputs that make it
    reproducible. The old silent fallback (no editor data → bake the legacy
    sonic_hack layout glob with air-placeholder collision) produced a ~131 KB
    WRONG level tree with no error — the row-178 hole. A manual re-bake MUST use
    the editor data + the sonic_hack donor; if either is absent, stop."""
    if not os.path.isdir(SONIC_HACK):
        raise SystemExit(
            f"ojz_strip_gen: sonic_hack donor not found at {SONIC_HACK}. This is a "
            f"MANUAL re-bake (tools/regenerate-level.sh); set AEON_SONIC_HACK_DIR. "
            f"The build does NOT run this — it uses the committed level tree under "
            f"games/sonic4/data/generated/.")
    if not editor_data_available():
        raise SystemExit(
            "ojz_strip_gen: editor section data absent (need editor/ojz/act1/"
            "section_0.tiles.bin + editor/ojz/chunks_tiles.bin). Refusing the "
            "silent legacy-air fallback — a re-bake without editor data would "
            "emit a ~131 KB wrong level tree. Restore the editor working data "
            "(committed for the shipped act) or point the editor at real data.")


def generate(stress_uniquify=0):
    """Generate strip data for all OJZ sections.

    stress_uniquify > 0 activates the P2c Task 11 stress fixture: post-dedup, the
    act art pool is inflated to that many distinct tiles via deterministic tile
    clones with re-pointed block references (see stress_uniquify_pool). Used only
    by the STRESS_ART build shape; the real committed tree is generated with 0.
    """
    require_donor()
    out_dir = os.path.normpath(OUTPUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    src_dir = SONIC_HACK
    use_editor = editor_data_available()

    if use_editor:
        print("=== Using level editor data ===")
        # Read grid dimensions from project.json
        with open(PROJECT_JSON, "r") as pf:
            proj = json.load(pf)
        ojz_act1 = proj["zones"][0]["acts"][0]
        editor_grid_w = ojz_act1["gridWidth"]
        editor_grid_h = ojz_act1["gridHeight"]
        editor_num_sections = editor_grid_w * editor_grid_h
        editor_data_path = os.path.join(
            os.path.dirname(__file__), "..", ojz_act1["dataPath"]
        )

        full_blob = load_editor_tile_art(CHUNKS_TILES_PATH)
        print(f"  Tile art: {CHUNKS_TILES_PATH} ({len(full_blob)} bytes, {len(full_blob)//32} tiles)")

        per_section_strips: dict[str, list[list[int]]] = {}
        for sec_idx in range(editor_num_sections):
            sec_path = os.path.join(editor_data_path, f"section_{sec_idx}.tiles.bin")
            if not os.path.isfile(sec_path):
                print(f"  WARNING: {sec_path} not found, skipping")
                continue
            nametable = load_editor_section_nametable(sec_path)
            strips = build_strips_from_nametable(nametable, STRIP_TILE_HEIGHT)
            per_section_strips[str(sec_idx)] = strips
            n_cols = len(strips)
            print(f"  section_{sec_idx}: {len(nametable)} rows × {n_cols} cols → {n_cols} strips")
    else:
        print("=== Using sonic_hack reference data (no editor data found) ===")
        print(f"Loading block map: {BLOCK_MAP_PATH}")
        blocks = load_block_map(BLOCK_MAP_PATH)
        print(f"  {len(blocks)} blocks loaded")

        print(f"Loading chunk map: {CHUNK_MAP_PATH}")
        chunks = load_chunk_map(CHUNK_MAP_PATH)
        print(f"  {len(chunks)} chunks loaded")

        # Same enumeration as the collision walk — decimal-named sections
        # only (legacy hex secA-D layouts are never generated).
        section_pairs = enumerate_collision_layouts()
        if not section_pairs:
            print(f"ERROR: No OJZ_1_sec*.bin layout files found in {LAYOUT_DIR}")
            sys.exit(1)

        per_section_strips = {}
        for sec_id, sec_path in section_pairs:
            sec_name = os.path.basename(sec_path).replace(".bin", "")
            layout = load_layout(sec_path)
            if not layout:
                print(f"  WARNING: {sec_name} produced empty layout, skipping")
                continue

            strips = generate_section_strips(layout, chunks, blocks)
            per_section_strips[sec_id] = strips
            print(
                f"  {sec_name}: {len(layout)} rows × {len(layout[0])} chunks "
                f"→ {len(strips)} strips"
            )

        full_blob = decompress_full_ojz_art(OJZ_ART_PATH)

    # ---- Pass 1b (§5 Task 2): bake real collision grids from sonic_hack ----
    # Collision ALWAYS derives from sonic_hack layout data, even in editor
    # mode (precedent: Pass 6b "BG layout always uses sonic_hack data").
    # NOTE: editor FG tile edits therefore do NOT update collision — editor
    # collision authoring is future work (deferred per design spec §1).
    #
    # ONE shared AttrSet across all sections — the strips' collision bytes
    # are indices into the attr-set tables emitted below, so every section
    # must intern into the same set. The section list comes from
    # enumerate_collision_layouts(), the SAME enumeration
    # gen_collision_data.real_tables() walks, so a standalone
    # gen_collision_data.py run always reproduces these tables.
    # ---- Collision: FRESH START + flag-based authoring (S&K base bank) ----
    # The collision VOCABULARY is the imported S&K base bank (data/collision/base/,
    # written by import_sk_collision.py). Level collision is all AIR except what the
    # editor authored. Each authored cell is a 16-bit word (shape | flip | solidity)
    # that the bake RESOLVES against the base bank and INTERNS into a shared attr-set
    # (bake_plane_cell). The runtime ROM tables (data/collision/*.bin) are then
    # emitted from that attr-set — only the combos actually painted reach the ROM.
    air_col = bytes(COLLISION_ROWS_PER_STRIP)
    per_section_coll: dict[str, tuple[list[bytes], list[bytes]]] = {
        sec_id: ([air_col] * len(strips), [air_col] * len(strips))
        for sec_id, strips in per_section_strips.items()
    }
    # ROM strips carry the authoritative editor override; source strips (the
    # editor's read-only baseline, sec*_strips_source.bin) stay air.
    per_section_coll_rom = per_section_coll
    if use_editor:
        base_profiles, base_angles = load_base_bank()
        attrset = collision_pipeline.AttrSet()      # ONE shared set across all sections
        per_section_coll_rom = {
            sec_id: apply_editor_collision_overlay(grids, sec_id, base_profiles, base_angles, attrset)
            for sec_id, grids in per_section_coll.items()
        }
        # Emit the sparse INTERNED runtime tables the ROM uses (overwrites the
        # default full-bank tables import_sk_collision.py wrote).
        coll_out = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "games", "sonic4", "data", "collision"))
        for name, data in collision_pipeline.emit_tables(attrset).items():
            with open(os.path.join(coll_out, name), "wb") as f:
                f.write(data)
        peak = len(attrset.entries) - 1             # minus air at index 0
        print(f"Collision: {len(per_section_coll)} sections; editor cells baked → "
              f"interned {peak}/255 solid attr-set combos; runtime tables → {coll_out}")
    else:
        print(f"Collision: {len(per_section_coll)} sections (air baseline, no editor data)")

    # ---- Pass 2: dedupe across all sections ----
    sorted_indices, raw_tiles = collect_referenced_tiles(per_section_strips, full_blob)
    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)

    # src_idx → canonical_idx + flip_bits
    src_to_canon: dict[int, tuple[int, int]] = {
        src_idx: mapping[i]
        for i, src_idx in enumerate(sorted_indices)
    }

    # ---- Pass 3: per-section unique canonical-tile lists ----
    sec_ids_in_order = list(per_section_strips.keys())
    per_section_canon_tiles: list[list[int]] = []
    for sec_id in sec_ids_in_order:
        seen: set[int] = set()
        ordered: list[int] = []
        for col in per_section_strips[sec_id]:
            for word in col:
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                canon_idx, _ = src_to_canon.get(src_idx, (0, 0))
                if canon_idx not in seen:
                    seen.add(canon_idx)
                    ordered.append(canon_idx)
        per_section_canon_tiles.append(ordered)

    # ---- Pass 4: global act art pool — spatially ordered, no per-section partition ----
    pool_order = tile_dedupe.order_pool_spatially(per_section_canon_tiles)   # canon IDs in pool order
    # Pool slot 0 == VRAM tile 0 must be the blank tile — empty blocks and
    # sparse plane rows render nametable word $0000. May append to `unique`.
    pool_order = tile_dedupe.pin_blank_tile_first(pool_order, unique)
    assert unique[pool_order[0]] == tile_dedupe.BLANK_TILE
    canon_to_pool = {cid: idx for idx, cid in enumerate(pool_order)}  # canon ID -> pool index (== VRAM global slot)

    # ---- Pass 4b (P2c Task 11): optional stress-uniquify pool inflation ----
    # Clones are APPENDED to pool_order (after the blank-pinned slot 0), so the
    # split/pin/manifest passes below see the inflated pool transparently. The
    # returned redirect re-points a spread of block references at the clones; it
    # is applied in Pass 5 and folded into per_section_global_sets.
    stress_redirect = None
    if stress_uniquify:
        stress_redirect, _stress_clone_parent = stress_uniquify_pool(
            stress_uniquify, unique, pool_order, canon_to_pool,
            per_section_strips, sec_ids_in_order, src_to_canon)
        print(f"STRESS-UNIQUIFY: inflated act pool to {len(pool_order)} tiles "
              f"({len(stress_redirect)} parent-matched clone references re-pointed)")

    # F-3 merge-translation LANDED: staged nametable words stay section-LOCAL and
    # the engine maps local->global per word at full u16 width, so there is NO
    # 2048-tile pool ceiling — the pool is bounded only by PAGE_TABLE_MAX pages
    # (asserted below) and the ROM budget gate.

    pages = tile_dedupe.split_pool_into_pages(pool_order, ART_POOL_PAGE_TILES)
    # P2b cutover: the pool ceiling is now the RESIDENCY page-table cap, not a
    # VRAM-tile ceiling — pages land in ALLOCATED frames (dest = frame base, not
    # page_id*64), so there is no per-act VRAM fit to guard. act_descriptor.emp
    # guards only OJZ_ACT_POOL_PAGES <= PAGE_TABLE_MAX at comptime; the old
    # identity-residency guard (OJZ_ACT_POOL_TILES <= POOL_TILE_CEILING) is retired.
    assert len(pages) <= PAGE_TABLE_MAX, (
        f"act art pool split into {len(pages)} pages > PAGE_TABLE_MAX {PAGE_TABLE_MAX} "
        f"(residency page table is a byte per page)")

    # Per-section global-slot sets (parallel to sec_ids_in_order) — drive both the
    # per-section local→global tables (Pass 5) and the page-pin heuristic (Pass 7).
    per_section_global_sets = [
        set(canon_to_pool[c] for c in sec_canons)
        for sec_canons in per_section_canon_tiles
    ]
    # Fold stress clones into each section's global set so its local→global map
    # (Pass 5) and the pin heuristic (Pass 7) cover the re-pointed references.
    if stress_redirect is not None:
        for (s_idx, _col, _row), slot in stress_redirect.items():
            per_section_global_sets[s_idx].add(slot)

    # ---- Pass 5: rewrite each section's strips to LOCAL indices + emit local→global tables ----
    # The block nametable words the engine bakes carry per-section LOCAL indices
    # (bits 0-10); palette/priority/flip (bits 11-15) are untouched. Each section
    # emits a local→global table (u16 per local index -> global VRAM slot); the
    # engine maps local→global PER WORD at the patch/scan consumers (F-3
    # merge-translation — staged words stay LOCAL; the full-width global lives
    # only in a register). The residency cache (engine page_cache) writes the
    # PHYSICAL index (allocated frame) into the tile cache, so a global index
    # is a cache key, not a fixed VRAM slot.
    total_strips = 0
    first_strips = None
    section_local_maps: list[tuple[str, list[int]]] = []   # (sec_id, local_to_global)
    for s_idx, sec_id in enumerate(sec_ids_in_order):
        local_to_global = build_section_local_map(per_section_global_sets[s_idx])
        global_to_local = {g: i for i, g in enumerate(local_to_global)}
        section_local_maps.append((sec_id, local_to_global))

        remapped_strips = []
        for col_i, col in enumerate(per_section_strips[sec_id]):
            remapped_col = []
            for row_i, word in enumerate(col):
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                canon_idx, flip_bits = src_to_canon.get(src_idx, (0, 0))
                vram_slot = canon_to_pool[canon_idx]         # global pool slot
                if stress_redirect is not None:
                    r = stress_redirect.get((s_idx, col_i, row_i))
                    if r is not None:
                        # Re-point at a PARENT-MATCHED clone (a scratch-perturbed copy of
                        # THIS word's own parent tile). KEEP the resolved canon-flip so the
                        # clone renders in the source orientation — same tile, faint scratch.
                        vram_slot = r
                local_idx = global_to_local[vram_slot]       # section-local index
                remapped_col.append(
                    tile_dedupe.remap_nametable_word(word, local_idx, flip_bits)
                )
            remapped_strips.append(remapped_col)

        # ROM strips carry the AUTHORITATIVE editor collision (per_section_coll_rom).
        rom_grids = per_section_coll_rom.get(sec_id)
        rom_a, rom_b = rom_grids if rom_grids else (None, None)

        out_a = os.path.join(out_dir, f"sec{sec_id}_strips_a.bin")
        write_strips_to_file(remapped_strips, out_a, rom_a, rom_b)

        # Source-space strips for the level editor (OJZ.bin tile indices, same
        # per-col format). The editor loads these instead of strips_a.bin so it
        # never sees VRAM slot assignments — and Aurora reads their collision
        # bytes as its read-only engine baseline (engineCollision), so these get
        # the PURE engine collision (per_section_coll), NOT the editor override.
        src_grids = per_section_coll.get(sec_id)
        src_a, src_b = src_grids if src_grids else (None, None)
        out_src = os.path.join(out_dir, f"sec{sec_id}_strips_source.bin")
        write_strips_to_file(
            per_section_strips[sec_id], out_src, src_a, src_b
        )

        if first_strips is None:
            first_strips = remapped_strips
        total_strips += len(remapped_strips)

    # ---- Pass 5b: emit per-section local→global tables (.bin + generated .emp) ----
    emit_section_local_maps(section_local_maps, out_dir)

    # ---- Pass 6: emit the single act art pool as independently-decodable pages ----
    for page_idx, page in enumerate(pages):
        page_out = os.path.join(out_dir, f"act_pool_page{page_idx}.bin")
        with open(page_out, "wb") as f:
            for canon_idx in page:
                f.write(unique[canon_idx])          # 32 raw bytes per tile
    pool_pages = len(pages)

    # ---- Pass 6b (§2 A.5 T1+T2): emit shared-region BG tile blob + per-variant nametables ----
    # BG layout always uses sonic_hack data (editor doesn't modify BG yet)
    bg_blocks = load_block_map(BLOCK_MAP_PATH) if use_editor else blocks
    bg_chunks = load_chunk_map(CHUNK_MAP_PATH) if use_editor else chunks
    bg_art_blob = decompress_full_ojz_art(OJZ_ART_PATH) if use_editor else full_blob

    ojz_master_layout_path = os.path.join(LAYOUT_DIR, "OJZ_1.bin")
    bg_layout = load_bg_layout(ojz_master_layout_path)

    # Zone-wide BG (col_offset=0) — used by act_bg_layout AND any section whose
    # sec_bg_layout is NULL (T1 fallback handled in BG_RedrawForSection).
    bg_nt_zone = build_bg_nametable_words(bg_layout, bg_chunks, bg_blocks, col_offset=0)

    # Shared BG tile blob — references only the zone layout's tiles. When real
    # T2/T3 sections are authored, pass [bg_nt_zone, sec1_nt, sec3_nt, ...] so
    # the deduped blob covers every variant's tiles.
    bg_tiles_path = os.path.join(out_dir, "bg_tiles.bin")
    bg_src_to_canon, bg_tile_count = emit_bg_tile_blob(
        [bg_nt_zone],
        bg_art_blob,
        bg_tiles_path,
    )

    zone_bg_path = os.path.join(out_dir, "zone_bg.bin")
    emit_zone_bg_layout(bg_nt_zone, bg_src_to_canon, zone_bg_path)

    print(
        f"Emitted BG tile blob: {bg_tiles_path} "
        f"({bg_tile_count} unique tiles, {os.path.getsize(bg_tiles_path)} bytes)"
    )
    print(f"Emitted zone BG layout (T1).")
    if bg_tile_count > BG_TILE_CAPACITY_PY:
        raise RuntimeError(
            f"BG tile count {bg_tile_count} exceeds shared region capacity {BG_TILE_CAPACITY_PY}"
        )

    # ---- Pass 7: act art pool manifest (page count + per-page tile count -> VRAM slot base) ----
    # A generated `.emp` const module (Parcel K3): comptime ints, zero ROM bytes,
    # consumed by act_descriptor.emp (its act_art_pool_pages field + the
    # OJZ_ACT_POOL_PAGES <= PAGE_TABLE_MAX guard).
    # See docs/superpowers/notes/2026-08-01-k3-islands.md.
    manifest_path = os.path.join(out_dir, "ojz_act_pool_manifest.emp")
    with open(manifest_path, "w") as f:
        f.write("// AUTO-GENERATED by tools/ojz_strip_gen.py — DO NOT EDIT.\n")
        f.write("// OJZ Act 1 act-wide paged art pool manifest: page count, total pool\n")
        f.write("// tiles, and each page's VRAM slot base + tile count. Consumed at\n")
        f.write("// comptime by act_descriptor.emp; emits ZERO ROM bytes.\n")
        f.write("module games.sonic4.ojz_act_pool_manifest_act1\n\n")
        f.write(f"pub const OJZ_ACT_POOL_PAGES = {len(pages)}\n")
        f.write(f"pub const OJZ_ACT_POOL_TILES = {len(pool_order)}\n\n")
        for page_idx, page in enumerate(pages):
            base = page_idx * ART_POOL_PAGE_TILES
            f.write(f"pub const OJZ_ACT_POOL_PAGE{page_idx}_SLOT  = {base}\n")
            f.write(f"pub const OJZ_ACT_POOL_PAGE{page_idx}_TILES = {len(page)}\n")

    # ---- Pass 7b: manifest v2 sidecar (JSON, deterministic) ----
    # Per-page {tiles, pinned}. regenerate-level.sh consumes this at compression
    # time, adds {source, form} (form = its ratio election), and emits the final
    # byte-emitting v2 manifest table {source.l, tiles.w, form.b, flags.b} in
    # ojz_act_pool.emp (replacing the old longword OJZ_Act_Pool_PageTable). The
    # generator owns tiles+pinned (data knowledge); the packer owns source+form
    # (compression knowledge).
    pinned_flags = mark_pinned_pages(pages, per_section_global_sets)
    sidecar = {
        "version": 2,
        "page_tiles": ART_POOL_PAGE_TILES,
        "page_bytes": ART_POOL_PAGE_TILES * tile_dedupe.TILE_SIZE,
        "pool_tiles": len(pool_order),
        "pages": [
            {"index": i, "tiles": len(page), "pinned": bool(pinned_flags[i])}
            for i, page in enumerate(pages)
        ],
    }
    with open(os.path.join(out_dir, "ojz_act_pool_manifest.json"), "w") as f:
        json.dump(sidecar, f, indent=2, sort_keys=True)
        f.write("\n")

    # ---- A.3 measurement ----
    raw_referenced = len(sorted_indices)
    deduped = len(unique)
    pct = (1.0 - deduped / raw_referenced) * 100 if raw_referenced else 0.0
    src_max = max(sorted_indices) if sorted_indices else 0
    src_min = min(sorted_indices) if sorted_indices else 0
    pool_tiles = len(pool_order)
    print(
        f"\n=== OJZ Act 1 — global art pool measurement ===\n"
        f"  Source tile indices referenced: {raw_referenced} "
        f"(min={src_min}, max={src_max})\n"
        f"  Deduped (with flip canonicalization): {deduped} "
        f"({pct:.1f}% reduction)\n"
        f"  Act art pool: {pool_tiles} distinct tiles "
        f"(ceiling {POOL_TILE_CEILING})\n"
        f"  Pages: {pool_pages} × {ART_POOL_PAGE_TILES} tiles "
        f"({', '.join(str(len(p)) for p in pages)} tiles each)\n"
    )

    # Copy palette file
    pal_src  = os.path.join(src_dir, "art", "palettes", "OJZ.bin")
    pal_dest = os.path.join(out_dir, "ojz_palette.bin")
    shutil.copy(pal_src, pal_dest)
    print(f"Copied palette -> {pal_dest}")

    print(f"Done. {len(sec_ids_in_order)} sections, {total_strips} total strips written to {out_dir}")

    # ---- Pass 8: entity data (rings/objects) from editor JSONs ----
    # TODO: promote to its own build.sh line once the in-flight build.sh changes land.
    import ojz_entity_gen
    ojz_entity_gen.generate()

    # Print a brief sanity summary for the first section's first strip
    if first_strips:
        first_strip = first_strips[0]
        print("\nFirst strip (section 0, column 0) — first 8 nametable words:")
        for row in range(min(8, STRIP_TILE_HEIGHT)):
            w = first_strip[row]
            tile = w & TILE_INDEX_MASK
            pal  = (w >> PALETTE_SHIFT) & 3
            pri  = bool(w & PRIORITY_BIT)
            print(
                f"    row {row:2d}: 0x{w:04X}  "
                f"tile={tile:4d}  pal={pal}  pri={pri}"
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    mode = args[0] if args else None
    if mode not in ("test", "generate"):
        print(f"Usage: {sys.argv[0]} test | generate [--stress-uniquify N]")
        sys.exit(1)

    if mode == "test":
        run_tests()
        return

    stress_uniquify = 0
    rest = args[1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--stress-uniquify":
            if i + 1 >= len(rest):
                print("ERROR: --stress-uniquify needs an integer N")
                sys.exit(1)
            try:
                stress_uniquify = int(rest[i + 1])
            except ValueError:
                print(f"ERROR: --stress-uniquify N must be an integer, got {rest[i + 1]!r}")
                sys.exit(1)
            i += 2
        else:
            print(f"ERROR: unknown argument {rest[i]!r}")
            sys.exit(1)

    generate(stress_uniquify=stress_uniquify)


if __name__ == "__main__":
    main()
