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
