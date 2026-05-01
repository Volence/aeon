#!/usr/bin/env python3
"""OJZ nametable strip generator.

Reads OJZ level data from the sonic_hack reference project and outputs
pre-computed nametable word arrays for the s4_engine section streaming system.

Usage:
    python3 tools/ojz_strip_gen.py test      # run self-tests
    python3 tools/ojz_strip_gen.py generate  # generate strip data files

Output: data/generated/ojz/act1/sec{N}_strips_a.bin for each OJZ section.
        data/generated/ojz/act1/sec{N}_tiles.bin (per-section tile blob, §2 A.3).
        data/generated/ojz/act1/zone_bg.bin (zone-wide Plane B nametable, §2 A.5 T1).
        data/generated/ojz/act1/ojz_palette.bin (copied from sonic_hack).

Each file contains ALL columns for section N concatenated sequentially:
col 0 words, then col 1 words, ..., col W-1 words.
Total size per file: num_columns * STRIP_TILE_HEIGHT * 2 bytes.

Each strip covers STRIP_TILE_HEIGHT=32 rows (nametable rows 0-31 only;
the sprite table lives at row 48 in the 64x64 Plane A nametable).
Each strip is a column of STRIP_TILE_HEIGHT big-endian nametable words.
"""

import struct
import sys
import os
import shutil

# Allow running from the s4_engine root (where build.sh lives).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tile_dedupe
import s4lz

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SONIC_HACK = "/home/volence/sonic_hacks/sonic_hack"
LAYOUT_DIR = os.path.join(SONIC_HACK, "level/layout")
CHUNK_MAP_PATH = os.path.join(SONIC_HACK, "mappings/128x128/OJZ.bin")
BLOCK_MAP_PATH = os.path.join(SONIC_HACK, "mappings/16x16/OJZ.bin")
OJZ_ART_PATH = os.path.join(SONIC_HACK, "art/kosinski/OJZ.bin")

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "generated", "ojz", "act1"
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STRIP_TILE_HEIGHT = 48  # nametable rows per strip (rows 0-47; sprite table at row 48)
OJZ_TILES_COUNT = 322   # legacy — pre-A.1 raw export count, kept for old test_generate_tile_art

# (HACK_STRIP_CHUNK_ROW_OFFSET hack reverted — didn't help because the
# upstream chunk/block table parsing is producing mostly-empty data for
# what should be ground chunks. Bug is in load_chunk_map / load_block_map
# / chunk_get_tile_word, not in the strip generator's row sampling.)
HACK_STRIP_CHUNK_ROW_OFFSET = 0

# Multi-region VRAM packing (§2 A.2) — must match constants.asm
# REGION2_VRAM_BASE / 32 == REGION2 starting tile slot
REGION1_TILE_CAPACITY = 1536          # primary art pool $0000-$BFFF
REGION2_VRAM_BASE     = 0xF800        # Plane B off-screen, row 48+ (per A.2 research)
REGION2_TILE_CAPACITY = 64            # ($10000 - $F800) / 32 = 64 tiles
TILES_PER_BLOCK_ROW = 2  # each block is 2 tiles wide × 2 tiles tall
TILES_PER_BLOCK_COL = 2
BLOCKS_PER_CHUNK_ROW = 8  # each chunk is 8×8 blocks
BLOCKS_PER_CHUNK_COL = 8
TILES_PER_CHUNK_ROW = TILES_PER_BLOCK_ROW * BLOCKS_PER_CHUNK_ROW   # 16
TILES_PER_CHUNK_COL = TILES_PER_BLOCK_COL * BLOCKS_PER_CHUNK_COL   # 16
BYTES_PER_CHUNK = BLOCKS_PER_CHUNK_ROW * BLOCKS_PER_CHUNK_COL * 2  # 128
WORDS_PER_BLOCK = TILES_PER_BLOCK_ROW * TILES_PER_BLOCK_COL        # 4

# Genesis nametable word bit masks
TILE_INDEX_MASK = 0x07FF   # bits 10-0: tile index (0-2047)
PALETTE_SHIFT = 13
PRIORITY_BIT = 0x8000

# ---------------------------------------------------------------------------
# Kosinski decompressor — direct port of sonic_hack's KosDec
# (code/engines/kosinski.asm). The earlier homegrown decoder had subtle
# bit-order / displacement bugs that produced ~5x too much output and
# ~50% spurious-empty blocks on real OJZ data. The fix is to mirror the
# asm exactly: LUT bit-reversal of each descriptor byte + add.b reads.
# ---------------------------------------------------------------------------

# Bit-reversal LUT (KosDec_ByteMap) from kosinski.asm
_BYTE_MAP = bytes([
    0x00,0x80,0x40,0xC0,0x20,0xA0,0x60,0xE0,0x10,0x90,0x50,0xD0,0x30,0xB0,0x70,0xF0,
    0x08,0x88,0x48,0xC8,0x28,0xA8,0x68,0xE8,0x18,0x98,0x58,0xD8,0x38,0xB8,0x78,0xF8,
    0x04,0x84,0x44,0xC4,0x24,0xA4,0x64,0xE4,0x14,0x94,0x54,0xD4,0x34,0xB4,0x74,0xF4,
    0x0C,0x8C,0x4C,0xCC,0x2C,0xAC,0x6C,0xEC,0x1C,0x9C,0x5C,0xDC,0x3C,0xBC,0x7C,0xFC,
    0x02,0x82,0x42,0xC2,0x22,0xA2,0x62,0xE2,0x12,0x92,0x52,0xD2,0x32,0xB2,0x72,0xF2,
    0x0A,0x8A,0x4A,0xCA,0x2A,0xAA,0x6A,0xEA,0x1A,0x9A,0x5A,0xDA,0x3A,0xBA,0x7A,0xFA,
    0x06,0x86,0x46,0xC6,0x26,0xA6,0x66,0xE6,0x16,0x96,0x56,0xD6,0x36,0xB6,0x76,0xF6,
    0x0E,0x8E,0x4E,0xCE,0x2E,0xAE,0x6E,0xEE,0x1E,0x9E,0x5E,0xDE,0x3E,0xBE,0x7E,0xFE,
    0x01,0x81,0x41,0xC1,0x21,0xA1,0x61,0xE1,0x11,0x91,0x51,0xD1,0x31,0xB1,0x71,0xF1,
    0x09,0x89,0x49,0xC9,0x29,0xA9,0x69,0xE9,0x19,0x99,0x59,0xD9,0x39,0xB9,0x79,0xF9,
    0x05,0x85,0x45,0xC5,0x25,0xA5,0x65,0xE5,0x15,0x95,0x55,0xD5,0x35,0xB5,0x75,0xF5,
    0x0D,0x8D,0x4D,0xCD,0x2D,0xAD,0x6D,0xED,0x1D,0x9D,0x5D,0xDD,0x3D,0xBD,0x7D,0xFD,
    0x03,0x83,0x43,0xC3,0x23,0xA3,0x63,0xE3,0x13,0x93,0x53,0xD3,0x33,0xB3,0x73,0xF3,
    0x0B,0x8B,0x4B,0xCB,0x2B,0xAB,0x6B,0xEB,0x1B,0x9B,0x5B,0xDB,0x3B,0xBB,0x7B,0xFB,
    0x07,0x87,0x47,0xC7,0x27,0xA7,0x67,0xE7,0x17,0x97,0x57,0xD7,0x37,0xB7,0x77,0xF7,
    0x0F,0x8F,0x4F,0xCF,0x2F,0xAF,0x6F,0xEF,0x1F,0x9F,0x5F,0xDF,0x3F,0xBF,0x7F,0xFF,
])


def kos_decompress(src: bytes, start: int = 0) -> tuple[bytes, int]:
    """Decompress one Kosinski stream from src[start:]. Returns (data, end_pos).

    Direct port of sonic_hack/code/engines/kosinski.asm KosDec.
    Models d0/d1/d2/d3 register state from the asm.
    """
    pos = start
    out = bytearray()

    # Initial descriptor pair read (bit-reversed via LUT)
    d0 = _BYTE_MAP[src[pos]]; pos += 1
    d1 = _BYTE_MAP[src[pos]]; pos += 1
    d2 = 7      # bits remaining in current d0
    d3 = 0      # toggle: 0 = on lo, switch to hi next; -1 = on hi, refill next

    def run_bitstream():
        """`_Kos_RunBitStream` — refill d0 if exhausted."""
        nonlocal d0, d1, d2, d3, pos
        if d2 > 0:
            d2 -= 1
            return
        d2 = 7
        d0 = d1
        d3 = (~d3) & 0xFFFF  # not.w
        if d3 != 0:
            return  # used hi byte; will refill next
        # Refill both bytes
        d0 = _BYTE_MAP[src[pos]] if pos < len(src) else 0
        pos += 1
        d1 = _BYTE_MAP[src[pos]] if pos < len(src) else 0
        pos += 1

    def read_bit() -> int:
        """`_Kos_ReadBit` — `add.b d0, d0` returns the (post-LUT) MSB."""
        nonlocal d0
        carry = (d0 >> 7) & 1
        d0 = (d0 << 1) & 0xFF
        return carry

    while True:
        bit = read_bit()
        if bit:
            # Code 1: uncompressed byte
            run_bitstream()
            out.append(src[pos]); pos += 1
            continue

        # Code 0: dictionary ref
        run_bitstream()
        bit = read_bit()
        if bit:
            # Code 01: long dict ref
            run_bitstream()
            d6 = src[pos]; pos += 1   # LLLLLLLL
            d4 = src[pos]; pos += 1   # HHHHHCCC

            # d5 = displacement word: build from d4<<5 | d6 with sign extension
            d5w = ((0xFF00 | d4) << 5) & 0xFFFF
            d5w = (d5w & 0xFF00) | d6
            d5_signed = d5w - 0x10000 if (d5w & 0x8000) else d5w

            count_bits = d4 & 7
            if count_bits != 0:
                n_bytes = count_bits + 2
            else:
                if pos >= len(src):
                    break
                ext = src[pos]; pos += 1
                if ext == 0:
                    break        # end of stream
                if ext == 1:
                    continue     # skip, fetch new code
                n_bytes = ext + 1

            # Copy n_bytes from (output_end + d5_signed) to output_end
            base = len(out)
            for i in range(n_bytes):
                src_idx = base + d5_signed + i
                out.append(out[src_idx] if 0 <= src_idx < len(out) else 0)
        else:
            # Code 00: short dict ref (2..5 bytes)
            run_bitstream()
            bit_a = read_bit()
            run_bitstream()
            bit_b = read_bit()
            count = (bit_a << 1) | bit_b
            n_bytes = count + 2

            run_bitstream()
            d5_byte = src[pos]; pos += 1
            d5_signed = d5_byte - 0x100  # always negative (one-byte back-ref)

            base = len(out)
            for i in range(n_bytes):
                src_idx = base + d5_signed + i
                out.append(out[src_idx] if 0 <= src_idx < len(out) else 0)

    return bytes(out), pos


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_block_map(path: str) -> list[list[int]]:
    """Load the 16x16 block map (Kosinski compressed).

    Returns a list of blocks, where each block is 4 nametable words
    [top-left, top-right, bottom-left, bottom-right].
    """
    data = open(path, "rb").read()
    decoded, _ = kos_decompress(data, 0)
    # Floor-divide: any trailing partial block (padding bytes) is ignored
    num_blocks = len(decoded) // (WORDS_PER_BLOCK * 2)
    blocks = []
    for i in range(num_blocks):
        base = i * WORDS_PER_BLOCK * 2
        words = [
            struct.unpack_from(">H", decoded, base + j * 2)[0]
            for j in range(WORDS_PER_BLOCK)
        ]
        blocks.append(words)
    return blocks


def load_chunk_map(path: str) -> list[list[int]]:
    """Load the 128x128 chunk map (Kosinski compressed, two concatenated streams).

    Returns a list of chunks, each chunk being 64 big-endian words
    (8×8 grid of block entries).

    Each chunk entry word:
      bits[15:10] = per-chunk flags (xflip/yflip/priority overrides).
                    NOTE: currently not applied — Phase 1 uses tile-level flags only.
      bits[9:0]   = block_id (confirmed by sonic_hack scroll_camera.asm andi.w #$3FF)
    """
    data = open(path, "rb").read()
    all_words = []
    pos = 0
    while pos < len(data):
        try:
            decoded, pos = kos_decompress(data, pos)
        except (IndexError, KeyError):
            break
        if not decoded:
            break
        # Each entry is a 2-byte big-endian word
        n = len(decoded) // 2
        for i in range(n):
            all_words.append(struct.unpack_from(">H", decoded, i * 2)[0])
    # Split into 64-word chunks (8×8 = 64 block entries per chunk)
    chunk_size = BLOCKS_PER_CHUNK_ROW * BLOCKS_PER_CHUNK_COL  # 64
    chunks = []
    for i in range(len(all_words) // chunk_size):
        base = i * chunk_size
        chunks.append(all_words[base:base + chunk_size])
    return chunks


def load_layout(path: str) -> list[list[int]]:
    """Load an OJZ section layout file (Sonic 2 binary layout format).

    Returns fg_rows rows of chunk IDs (list of lists).

    Format:
        0x0000 magic (0x00FE as big-endian word)
        0x0002 width  (in chunks)
        0x0004 fg_rows
        0x0006 bg_rows
        0x0008 pointer table (fg_rows × 4 bytes, row offsets — skip)
        0x0008 + fg_rows*4: FG data (fg_rows × width bytes of chunk IDs)
        ... BG data follows
    """
    data = open(path, "rb").read()
    if len(data) < 8:
        return []
    magic, width, fg_rows, bg_rows = struct.unpack_from(">4H", data, 0)
    if magic != 0xFE:
        raise ValueError(f"Bad layout magic: 0x{magic:04X} in {path}")
    fg_start = 8 + fg_rows * 4  # skip 8-byte header + pointer table
    rows = []
    for r in range(fg_rows):
        row_start = fg_start + r * width
        rows.append(list(data[row_start:row_start + width]))
    return rows


def load_bg_layout(path: str) -> list[list[int]]:
    """Load the BG section of an OJZ layout file (§2 A.5 T1 source).

    Returns bg_rows × width chunk IDs.

    Same file as load_layout(), but reads the BG portion that follows the FG
    data. Sonic 2 layout files store FG and BG separately:
        ... FG data (fg_rows × width bytes) ...
        ... BG data (bg_rows × width bytes) — no separate pointer table ...
    """
    data = open(path, "rb").read()
    if len(data) < 8:
        return []
    magic, width, fg_rows, bg_rows = struct.unpack_from(">4H", data, 0)
    if magic != 0xFE:
        raise ValueError(f"Bad layout magic: 0x{magic:04X} in {path}")
    bg_start = 8 + fg_rows * 4 + fg_rows * width
    rows = []
    for r in range(bg_rows):
        row_start = bg_start + r * width
        rows.append(list(data[row_start:row_start + width]))
    return rows


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
BG_TILE_CAPACITY_PY  = 512    # mirrors constants.asm BG_TILE_CAPACITY


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


def write_strips_to_file(strips: list[list[int]], path: str) -> None:
    """Write all column strips concatenated into a single binary file.

    Format per column (128 bytes):
      - 48 nametable words (96 bytes, big-endian)
      - 24 collision bytes (stub: non-zero tile → solid)
      - 8 bytes padding (zero)
    Total size: len(strips) * 128 bytes.
    """
    with open(path, "wb") as f:
        for strip in strips:
            for word in strip:
                f.write(struct.pack(">H", word))
            f.write(generate_collision_bytes(strip))
            f.write(b'\x00' * STRIP_COLLISION_PAD)


def generate_section_strips(
    layout: list[list[int]],
    chunks: list[list[int]],
    blocks: list[list[int]],
) -> list[list[int]]:
    """Generate one strip (list of ints) per layout tile-column.

    Each strip is STRIP_TILE_HEIGHT words = rows 0-31 of the nametable column.
    A layout row is TILES_PER_CHUNK_COL=16 nametable rows tall, so
    STRIP_TILE_HEIGHT=32 rows covers exactly 2 layout rows (chunks).

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
    # HACK (§2 A.4): apply HACK_STRIP_CHUNK_ROW_OFFSET to skip empty top
    # padding so the test viewport shows actual terrain. Remove when a
    # real start-row mechanism exists.
    nametable = []
    for tile_row in range(strip_rows):
        chunk_row = (tile_row // TILES_PER_CHUNK_COL) + HACK_STRIP_CHUNK_ROW_OFFSET
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
# Tile art extractor
# ---------------------------------------------------------------------------

def generate_tile_art(
    ojz_bin_path: str,
    out_path: str,
    n_tiles: int = OJZ_TILES_COUNT,
) -> None:
    """Decompress stream 0 of OJZ.bin and output the first n_tiles raw tiles.

    Each Genesis tile is 32 bytes (8×8 pixels, 4bpp).
    Stream 0 of OJZ.bin covers the first 891 tiles; tiles 0-321 are all that
    the 32-row strips reference, so only those are included in the output.
    """
    data = open(ojz_bin_path, "rb").read()
    raw, _ = kos_decompress(data, 0)
    tile_bytes = n_tiles * 32
    if len(raw) < tile_bytes:
        raise ValueError(
            f"OJZ.bin stream 0 decompressed to {len(raw)} bytes "
            f"but {tile_bytes} needed for {n_tiles} tiles"
        )
    with open(out_path, "wb") as f:
        f.write(raw[:tile_bytes])


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


def _ojz_grid_dimensions(sec_ids: list[str]) -> tuple[int, int]:
    """Read OJZ act layout grid dimensions.

    OJZ act 1 uses a flat horizontal layout. For now hard-coded to
    (len(sec_ids), 1). Future acts with 2D grids should parse the
    descriptor or pass dims explicitly.
    """
    return (len(sec_ids), 1)


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
    """Test B: strips must be exactly STRIP_TILE_HEIGHT rows (sprite table safety)."""
    tall = [[c for c in range(8)] for r in range(64)]
    tall_strips = build_strips_from_nametable(tall, STRIP_TILE_HEIGHT)
    assert all(len(s) == STRIP_TILE_HEIGHT for s in tall_strips), \
        "Strips must be exactly STRIP_TILE_HEIGHT rows (sprite table safety)"
    print(f"  PASS: strips truncate at {STRIP_TILE_HEIGHT} (sprite table at row 48 safe)")


def test_binary_round_trip():
    """Test C: write strips to temp file, read back, verify first word and total size."""
    import tempfile
    test_strips = [[r + c * 100 for r in range(STRIP_TILE_HEIGHT)] for c in range(3)]
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as tf:
        tmp = tf.name
    write_strips_to_file(test_strips, tmp)
    data = open(tmp, 'rb').read()
    assert len(data) == 3 * STRIP_TILE_HEIGHT * 2, f"Size mismatch: {len(data)}"
    first_word = struct.unpack_from('>H', data, 0)[0]
    assert first_word == test_strips[0][0], \
        f"First word: expected {test_strips[0][0]}, got {first_word}"
    os.unlink(tmp)
    print("  PASS: binary round-trip")


def test_generate_tile_art():
    """Test that generate_tile_art decompresses stream 0 and returns correct tile count."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as tf:
        tmp = tf.name
    generate_tile_art(OJZ_ART_PATH, tmp, OJZ_TILES_COUNT)
    data = open(tmp, 'rb').read()
    expected = OJZ_TILES_COUNT * 32
    assert len(data) == expected, f"Expected {expected} bytes, got {len(data)}"
    # Tile 0 should be all-zero (sky/transparent tile in OJZ)
    assert data[:32] == bytes(32), "Tile 0 expected to be all zeros (sky tile)"
    os.unlink(tmp)
    print(f"  [OK] generate_tile_art: {OJZ_TILES_COUNT} tiles = {expected} bytes "
          f"(Kosinski source: {os.path.getsize(OJZ_ART_PATH)} bytes)")


def test_full_pipeline_runs():
    """Smoke test the whole generate() pipeline produces a deduped pool."""
    import tempfile
    global OUTPUT_DIR
    saved = OUTPUT_DIR
    with tempfile.TemporaryDirectory() as td:
        OUTPUT_DIR = td
        try:
            generate()
            # A.3: per-section blobs (one per OJZ section)
            import glob
            sec_files = sorted(glob.glob(os.path.join(td, "sec*_tiles.bin")))
            assert len(sec_files) > 0, "no per-section tile blobs written"
            for f in sec_files:
                size = os.path.getsize(f)
                assert size % 32 == 0, f"{f} size {size} not a multiple of 32"
                assert size <= REGION1_TILE_CAPACITY * 32
            bases_path = os.path.join(td, "sec_vram_bases.asm")
            assert os.path.exists(bases_path), "sec_vram_bases.asm not written"
        finally:
            OUTPUT_DIR = saved
    print(f"  [OK] test_full_pipeline_runs: deduped pool fits in 1536 tiles")


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
    test_generate_tile_art()
    test_full_pipeline_runs()
    print("All tests passed")


# ---------------------------------------------------------------------------
# Collision byte generation (§4.7 — embedded in wider strips)
# ---------------------------------------------------------------------------

COLLISION_ROWS_PER_STRIP = STRIP_TILE_HEIGHT // 2   # 24 collision cells (16px each)
STRIP_COLLISION_PAD = 8                              # pad to 128 bytes for power-of-2 addressing
WIDE_STRIP_SIZE = STRIP_TILE_HEIGHT * 2 + COLLISION_ROWS_PER_STRIP + STRIP_COLLISION_PAD  # 128


def generate_collision_bytes(strip_words: list[int]) -> bytes:
    """Generate 24 collision bytes for one strip column.

    Stub: mark a cell solid only if its nametable words have the VDP
    priority bit set (bit 15).  In OJZ, sky/cloud tiles use priority 0
    while ground/terrain tiles use priority 1 — this cleanly separates
    walkable ground from background scenery.
    """
    collision = bytearray(COLLISION_ROWS_PER_STRIP)
    for cell in range(COLLISION_ROWS_PER_STRIP):
        top_word = strip_words[cell * 2]
        bot_word = strip_words[cell * 2 + 1] if cell * 2 + 1 < len(strip_words) else 0
        if (top_word & 0x8000) or (bot_word & 0x8000):
            collision[cell] = 1
    return bytes(collision)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(force_region1_cap=None):
    """Generate strip data for all OJZ sections.

    `force_region1_cap` (optional, A.2 stress flag): caps region 1 capacity
    to this value, forcing remaining tiles into region 2. Used for testing
    the spill code path on data that doesn't naturally exceed 1536 tiles.
    """
    out_dir = os.path.normpath(OUTPUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    src_dir = SONIC_HACK

    print(f"Loading block map: {BLOCK_MAP_PATH}")
    blocks = load_block_map(BLOCK_MAP_PATH)
    print(f"  {len(blocks)} blocks loaded")

    print(f"Loading chunk map: {CHUNK_MAP_PATH}")
    chunks = load_chunk_map(CHUNK_MAP_PATH)
    print(f"  {len(chunks)} chunks loaded")

    # Find all OJZ section layout files
    import glob
    import re
    pattern = os.path.join(LAYOUT_DIR, "OJZ_1_sec*.bin")
    def extract_sec_id(path: str) -> int:
        m = re.search(r'sec([0-9A-Fa-f]+)', os.path.basename(path))
        if m:
            try:
                return int(m.group(1), 16)  # Hexadecimal (handles 0-9, A-F)
            except ValueError:
                return int(m.group(1))  # Fallback to decimal
        return -1
    section_files = sorted(glob.glob(pattern), key=extract_sec_id)

    if not section_files:
        print(f"ERROR: No layout files found matching {pattern}")
        sys.exit(1)

    # ---- Pass 1: build per-section strips, hold in memory ----
    per_section_strips: dict[str, list[list[int]]] = {}
    section_meta: dict[str, tuple[int, int]] = {}  # sec_id → (rows, cols)
    for sec_path in section_files:
        sec_name = os.path.basename(sec_path).replace(".bin", "")
        sec_id = sec_name.split("sec")[1]

        layout = load_layout(sec_path)
        if not layout:
            print(f"  WARNING: {sec_name} produced empty layout, skipping")
            continue

        strips = generate_section_strips(layout, chunks, blocks)
        per_section_strips[sec_id] = strips
        section_meta[sec_id] = (len(layout), len(layout[0]))
        print(
            f"  {sec_name}: {len(layout)} rows × {len(layout[0])} chunks "
            f"→ {len(strips)} strips"
        )

    # ---- Pass 2: dedupe across all sections ----
    full_blob = decompress_full_ojz_art(OJZ_ART_PATH)
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

    # ---- Pass 4: section adjacency + coloring + slot assignment ----
    grid_w, grid_h = _ojz_grid_dimensions(sec_ids_in_order)
    edges = tile_dedupe.compute_adjacency(grid_w, grid_h)
    colors = tile_dedupe.color_sections(len(sec_ids_in_order), edges)
    color_bases, section_slots = tile_dedupe.assign_section_slots(
        per_section_canon_tiles, colors, region_start=0
    )

    # ---- Pass 5: rewrite each section's strips using its own slot map ----
    total_strips = 0
    first_strips = None
    for s_idx, sec_id in enumerate(sec_ids_in_order):
        slot_map = section_slots[s_idx]
        remapped_strips = []
        for col in per_section_strips[sec_id]:
            remapped_col = []
            for word in col:
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                canon_idx, flip_bits = src_to_canon.get(src_idx, (0, 0))
                vram_slot = slot_map.get(canon_idx, 0)
                remapped_col.append(
                    tile_dedupe.remap_nametable_word(word, vram_slot, flip_bits)
                )
            remapped_strips.append(remapped_col)

        out_a = os.path.join(out_dir, f"sec{sec_id}_strips_a.bin")
        write_strips_to_file(remapped_strips, out_a)
        # (§2 A.5: per-section strips_b placeholder removed — Plane B is now
        # driven by zone_bg.bin (T1) or per-section secN_bg.bin (T2/T3).)
        if first_strips is None:
            first_strips = remapped_strips
        total_strips += len(remapped_strips)

    # ---- Pass 5b (§4.7): S4LZ compress wide strips + emit checkpoints ----
    STRIPS_PER_CHECKPOINT = 64
    CKPT_INTERVAL = STRIPS_PER_CHECKPOINT * WIDE_STRIP_SIZE

    for sec_id in sec_ids_in_order:
        raw_path = os.path.join(out_dir, f"sec{sec_id}_strips_a.bin")
        with open(raw_path, 'rb') as f:
            raw_data = f.read()

        if len(raw_data) > 0xFFFF:
            print(f"  sec{sec_id} strips: {len(raw_data)} bytes — too large for S4LZ, skipping")
            continue

        compressed, checkpoints = s4lz.compress(
            raw_data, tile_delta=False,
            checkpoint_interval=CKPT_INTERVAL,
            max_match_words=WIDE_STRIP_SIZE // 2)

        s4lz_path = os.path.join(out_dir, f"sec{sec_id}_strips.s4lz")
        with open(s4lz_path, 'wb') as f:
            f.write(compressed)

        ckpt_path = os.path.join(out_dir, f"sec{sec_id}_strip_checkpoints.bin")
        with open(ckpt_path, 'wb') as f:
            while len(checkpoints) < 4:
                checkpoints.append(checkpoints[-1] if checkpoints else 0)
            for offset in checkpoints[:4]:
                f.write(struct.pack(">H", offset))

        ratio = len(compressed) / len(raw_data) * 100 if raw_data else 0
        print(f"  sec{sec_id} strips: {len(raw_data)} -> {len(compressed)} ({ratio:.1f}%) [128B/col, collision embedded]")

    # ---- Pass 6: emit per-section tile-art blobs ----
    for s_idx, sec_id in enumerate(sec_ids_in_order):
        sec_tiles = per_section_canon_tiles[s_idx]
        sec_out = os.path.join(out_dir, f"sec{sec_id}_tiles.bin")
        with open(sec_out, "wb") as f:
            for canon_idx in sec_tiles:
                f.write(unique[canon_idx])

    # ---- Pass 6b (§2 A.5 T1+T2): emit shared-region BG tile blob + per-variant nametables ----
    ojz_master_layout_path = os.path.join(LAYOUT_DIR, "OJZ_1.bin")
    bg_layout = load_bg_layout(ojz_master_layout_path)

    # Zone-wide BG (col_offset=0) — used by act_bg_layout AND any section whose
    # sec_bg_layout is NULL (T1 fallback handled in BG_RedrawForSection).
    bg_nt_zone = build_bg_nametable_words(bg_layout, chunks, blocks, col_offset=0)

    # Shared BG tile blob — references only the zone layout's tiles. When real
    # T2/T3 sections are authored, pass [bg_nt_zone, sec1_nt, sec3_nt, ...] so
    # the deduped blob covers every variant's tiles.
    bg_tiles_path = os.path.join(out_dir, "bg_tiles.bin")
    bg_src_to_canon, bg_tile_count = emit_bg_tile_blob(
        [bg_nt_zone],
        full_blob,
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

    # ---- Pass 7: emit per-section VRAM-base constants for the act descriptor ----
    bases_path = os.path.join(out_dir, "sec_vram_bases.asm")
    with open(bases_path, "w") as f:
        f.write("; Auto-generated by tools/ojz_strip_gen.py — DO NOT EDIT\n")
        f.write("; Per-section VRAM byte destinations (color_base × 32 bytes/tile)\n")
        for s_idx, sec_id in enumerate(sec_ids_in_order):
            base_slot = color_bases[colors[s_idx]]
            f.write(f"OJZ_SEC{sec_id.upper()}_VRAM = {base_slot} * 32\n")

    # ---- A.3 measurement ----
    raw_referenced = len(sorted_indices)
    deduped = len(unique)
    pct = (1.0 - deduped / raw_referenced) * 100 if raw_referenced else 0.0
    src_max = max(sorted_indices) if sorted_indices else 0
    src_min = min(sorted_indices) if sorted_indices else 0
    src_collisions = sum(1 for i in sorted_indices if i >= 1536)
    num_colors = max(colors) + 1 if colors else 0
    max_simultaneous = sum(
        max((len(per_section_canon_tiles[s]) for s in range(len(colors)) if colors[s] == c), default=0)
        for c in range(num_colors)
    )
    print(
        f"\n=== OJZ Act 1 — Phase A.3 measurement ===\n"
        f"  Source tile indices referenced: {raw_referenced} "
        f"(min={src_min}, max={src_max})\n"
        f"  Source indices ≥1536 (nametable collision risk): {src_collisions}\n"
        f"  Deduped (with flip canonicalization): {deduped} "
        f"({pct:.1f}% reduction)\n"
        f"  Section adjacency: {grid_w}×{grid_h} grid, {len(edges)} edges\n"
        f"  Chromatic number: {num_colors} (DSATUR greedy)\n"
        f"  Max simultaneously-resident: {max_simultaneous} tiles\n"
        f"  Color bases: {color_bases}\n"
    )

    # Copy palette file
    pal_src  = os.path.join(src_dir, "art", "palettes", "OJZ.bin")
    pal_dest = os.path.join(out_dir, "ojz_palette.bin")
    shutil.copy(pal_src, pal_dest)
    print(f"Copied palette -> {pal_dest}")

    num_sections_processed = len([1 for f in section_files if os.path.exists(os.path.join(out_dir, f"{os.path.basename(f).replace('OJZ_1_sec', 'sec').replace('.bin', '')}_strips_a.bin"))])
    print(f"Done. {num_sections_processed} sections, {total_strips} total strips written to {out_dir}")

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
    if len(sys.argv) < 2 or sys.argv[1] not in ("test", "generate"):
        print(f"Usage: {sys.argv[0]} test|generate [--force-region1-cap=N]")
        sys.exit(1)

    if sys.argv[1] == "test":
        run_tests()
        return

    # generate
    force_cap = None
    for arg in sys.argv[2:]:
        if arg.startswith("--force-region1-cap="):
            try:
                force_cap = int(arg.split("=", 1)[1])
            except ValueError:
                print(f"Invalid --force-region1-cap value: {arg}")
                sys.exit(1)
        else:
            print(f"Unknown arg: {arg}")
            sys.exit(1)
    generate(force_region1_cap=force_cap)


if __name__ == "__main__":
    main()
