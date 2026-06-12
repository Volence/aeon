#!/usr/bin/env python3
"""Shared OJZ data loaders + path constants.

Home of the sonic_hack source paths and the Kosinski/layout/map loaders
used by BOTH ojz_strip_gen.py and collision_pipeline.py. Lives in its own
module so the two can share code without a circular import:

    ojz_common          (no project imports)
      ^         ^
      |         |
  collision   ojz_strip_gen  (imports collision_pipeline + re-exports
  _pipeline                   ojz_common names for existing importers)

Editor-specific paths (EDITOR_DIR, PROJECT_JSON, OJZ_ART_PATH, ...) stay in
ojz_strip_gen — only what both sides need is here.
"""

import os
import struct

# ---------------------------------------------------------------------------
# Paths (sonic_hack reference project — shared by strip gen + collision)
# ---------------------------------------------------------------------------
SONIC_HACK = "/home/volence/sonic_hacks/sonic_hack"
LAYOUT_DIR = os.path.join(SONIC_HACK, "level/layout")
CHUNK_MAP_PATH = os.path.join(SONIC_HACK, "mappings/128x128/OJZ.bin")
BLOCK_MAP_PATH = os.path.join(SONIC_HACK, "mappings/16x16/OJZ.bin")

# ---------------------------------------------------------------------------
# Block / chunk geometry (needed by the loaders below)
# ---------------------------------------------------------------------------
TILES_PER_BLOCK_ROW = 2  # each block is 2 tiles wide × 2 tiles tall
TILES_PER_BLOCK_COL = 2
BLOCKS_PER_CHUNK_ROW = 8  # each chunk is 8×8 blocks
BLOCKS_PER_CHUNK_COL = 8
WORDS_PER_BLOCK = TILES_PER_BLOCK_ROW * TILES_PER_BLOCK_COL        # 4

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
