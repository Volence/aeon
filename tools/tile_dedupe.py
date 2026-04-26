"""Tile canonicalization, global dedupe, and nametable remap for §2 A.1.

A Genesis tile is 32 bytes = 8 rows × 4 bytes/row; each byte holds two
4-bpp pixels (high nibble = left, low nibble = right).

H-flip = reverse the 4 bytes in each row AND swap nibbles within each byte.
V-flip = reverse the 8 rows.

See docs/research/tile-dedupe-canonicalization.md for the rule choice
(lex-smallest of 4 orientations) and source survey.
"""

TILE_SIZE = 32
TILE_ROW_BYTES = 4
TILE_ROWS = 8


def hflip_tile(tile: bytes) -> bytes:
    out = bytearray(TILE_SIZE)
    for r in range(TILE_ROWS):
        for b in range(TILE_ROW_BYTES):
            src = tile[r * TILE_ROW_BYTES + (TILE_ROW_BYTES - 1 - b)]
            # Swap nibbles (left pixel <-> right pixel)
            out[r * TILE_ROW_BYTES + b] = ((src & 0x0F) << 4) | ((src & 0xF0) >> 4)
    return bytes(out)


def vflip_tile(tile: bytes) -> bytes:
    out = bytearray(TILE_SIZE)
    for r in range(TILE_ROWS):
        src_row = TILE_ROWS - 1 - r
        out[r * TILE_ROW_BYTES : (r + 1) * TILE_ROW_BYTES] = (
            tile[src_row * TILE_ROW_BYTES : (src_row + 1) * TILE_ROW_BYTES]
        )
    return bytes(out)


def canonical_form(tile: bytes) -> tuple[bytes, int]:
    """Return (canonical_bytes, flip_bits).

    Canonical form is the lex-smallest of the 4 orientations:
      flip_bits 0 = identity
      flip_bits 1 = hflip (apply H to original to reach canonical)
      flip_bits 2 = vflip
      flip_bits 3 = both

    Two tiles that differ only by an H/V/HV flip share the same canonical form.
    Deterministic regardless of input order — improves on SGDK rescomp's
    first-encountered rule for build reproducibility.
    """
    h  = hflip_tile(tile)
    v  = vflip_tile(tile)
    hv = hflip_tile(v)
    candidates = [(tile, 0), (h, 1), (v, 2), (hv, 3)]
    candidates.sort(key=lambda c: c[0])
    return candidates[0]


def dedupe_tiles(tiles: list[bytes]) -> tuple[list[bytes], list[tuple[int, int]]]:
    """Globally dedupe a list of 32-byte tiles using canonical form.

    Returns (unique_tiles, mapping):
      unique_tiles[k] is the k-th distinct canonical-form tile, in first-seen order.
      mapping[i] = (canonical_index, flip_bits) for the i-th input tile.

    Two input tiles whose canonical forms match collapse to the same index
    with potentially different flip_bits — strip remap uses those flip_bits
    (XORed against the original H/V) to recover the original orientation.
    """
    canonical_to_index: dict[bytes, int] = {}
    unique: list[bytes] = []
    mapping: list[tuple[int, int]] = []
    for t in tiles:
        canon, flip_bits = canonical_form(t)
        idx = canonical_to_index.get(canon)
        if idx is None:
            idx = len(unique)
            canonical_to_index[canon] = idx
            unique.append(canon)
        mapping.append((idx, flip_bits))
    return unique, mapping


# ---------------------------------------------------------------------------
# Nametable strip remap
# ---------------------------------------------------------------------------

# Genesis nametable word: priority[15] | palette[14:13] | V[12] | H[11] | tile_index[10:0]
NAMETABLE_TILE_MASK = 0x07FF
NAMETABLE_H_BIT     = 0x0800
NAMETABLE_V_BIT     = 0x1000


def remap_nametable_word(word: int, vram_tile_slot: int, canon_flip_bits: int) -> int:
    """Rewrite a 16-bit nametable word with a final VRAM tile slot.

    Preserves priority + palette; replaces tile_index with vram_tile_slot;
    XORs the original H/V bits with canon_flip_bits to recover the original
    visual orientation.

    The tile-index field is 11 bits (0-2047), spanning the full VRAM tile
    range. Region 1 tiles get slots 0..REGION1_CAPACITY-1; region 2 tiles
    get slots starting at REGION2_VRAM_BASE/32.
    """
    high = word & ~NAMETABLE_TILE_MASK
    if canon_flip_bits & 1:
        high ^= NAMETABLE_H_BIT
    if canon_flip_bits & 2:
        high ^= NAMETABLE_V_BIT
    return high | (vram_tile_slot & NAMETABLE_TILE_MASK)


# ---------------------------------------------------------------------------
# Multi-region packing (§2 A.2)
# ---------------------------------------------------------------------------

def pack_regions(
    unique_count: int,
    regions: list[tuple[int, int]],
) -> list[int]:
    """Assign each canonical tile to a VRAM tile slot.

    `regions` is a list of (start_tile_slot, capacity) tuples in fill order.
    Returns a list of length `unique_count` where slots[i] is the VRAM
    tile slot assigned to canonical tile i.

    Raises OverflowError if total capacity is insufficient.
    """
    slots: list[int] = []
    region_idx = 0
    region_used = 0
    for canon_idx in range(unique_count):
        # Skip exhausted (or zero-capacity) regions
        while region_idx < len(regions) and region_used >= regions[region_idx][1]:
            region_idx += 1
            region_used = 0
        if region_idx >= len(regions):
            raise OverflowError(
                f"Tile pool exceeds region capacity at canonical tile {canon_idx}"
            )
        slots.append(regions[region_idx][0] + region_used)
        region_used += 1
    return slots
