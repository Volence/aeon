#!/usr/bin/env python3
"""OJZ nametable strip generator.

Reads OJZ level data from the sonic_hack reference project and outputs
pre-computed nametable word arrays for the s4_engine section streaming system.

Usage:
    python3 tools/ojz_strip_gen.py test      # run self-tests
    python3 tools/ojz_strip_gen.py generate  # generate strip data files

Output: data/generated/ojz/act1/sec{N}_strips_a.bin for each OJZ section.
        data/generated/ojz/act1/sec{N}_strips_b.bin (all-zeros plane B placeholder)
        data/generated/ojz/act1/ojz_palette.bin (copied from sonic_hack)

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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SONIC_HACK = "/home/volence/sonic_hacks/sonic_hack"
LAYOUT_DIR = os.path.join(SONIC_HACK, "level/layout")
CHUNK_MAP_PATH = os.path.join(SONIC_HACK, "mappings/128x128/OJZ.bin")
BLOCK_MAP_PATH = os.path.join(SONIC_HACK, "mappings/16x16/OJZ.bin")

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "generated", "ojz", "act1"
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STRIP_TILE_HEIGHT = 32  # nametable rows per strip (rows 0-31 of 64-row plane)
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
HFLIP_BIT = 0x0800
VFLIP_BIT = 0x1000

# ---------------------------------------------------------------------------
# Kosinski decompressor (standard Sega Genesis variant)
#
# Descriptor word: 16-bit little-endian, read LSB-first (PopWhere::Low).
# Bit=1  → literal byte
# Bit=0, Bit=1 → long back-reference
#   offset = 0x2000 - ((hi & 0xF8)<<5 | lo)
#   count  = (hi & 7) + 2   if count >= 2 else read extended byte:
#            ext+1; if 1 → end; if 2 → skip (no copy)
# Bit=0, Bit=0 → short back-reference
#   count  = 2 + 2*b3 + b4
#   offset = 0x100 - next_byte
# ---------------------------------------------------------------------------
KOSINSKI_WINDOW = 0x2000  # 8192-byte ring buffer


def kos_decompress(src: bytes, start: int = 0) -> tuple[bytes, int]:
    """Decompress one Kosinski stream from src[start:]. Returns (data, end_pos)."""
    ring = bytearray(KOSINSKI_WINDOW)
    ring_pos = 0
    result = bytearray()
    pos = start

    desc_val = 0
    desc_bits = 0

    def read_descriptor():
        nonlocal pos, desc_val, desc_bits
        lo = src[pos];  pos += 1
        hi = src[pos];  pos += 1
        desc_val = lo | (hi << 8)
        desc_bits = 16

    def pop_bit() -> int:
        nonlocal desc_val, desc_bits
        if desc_bits == 0:
            read_descriptor()
        b = desc_val & 1
        desc_val >>= 1
        desc_bits -= 1
        return b

    def write_byte(b: int):
        nonlocal ring_pos
        ring[ring_pos & (KOSINSKI_WINDOW - 1)] = b
        ring_pos += 1
        result.append(b)

    read_descriptor()

    while True:
        if pos >= len(src):
            break
        try:
            if pop_bit():
                # Literal byte
                write_byte(src[pos]);  pos += 1
            else:
                if pop_bit():
                    # Long back-reference
                    if pos + 1 >= len(src):
                        break
                    lo = src[pos];  pos += 1
                    hi = src[pos];  pos += 1
                    offset = 0x2000 - (((hi & 0xF8) << 5) | lo)
                    count  = hi & 7
                    if count:
                        count += 2
                    else:
                        if pos >= len(src):
                            break
                        ext = src[pos];  pos += 1
                        count = ext + 1
                        if count == 1:
                            break           # end-of-stream
                        if count == 2:
                            continue        # skip, no copy
                else:
                    # Short back-reference
                    b3 = pop_bit()
                    b4 = pop_bit()
                    count  = 2 + b3 * 2 + b4
                    if pos >= len(src):
                        break
                    offset = 0x100 - src[pos];  pos += 1

                cp = ring_pos - offset
                for _ in range(count):
                    write_byte(ring[cp & (KOSINSKI_WINDOW - 1)])
                    cp += 1
        except IndexError:
            break

    return bytes(result), pos


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
    (8×8 grid of block entries).  Each word: bits15-10 flags, bits9-0 block_id.
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


# ---------------------------------------------------------------------------
# Strip generation
# ---------------------------------------------------------------------------

def chunk_get_tile_word(
    chunk: list[int],
    blocks: list[list[int]],
    tile_col: int,
    tile_row: int,
) -> int:
    """Return the nametable word for tile (tile_col, tile_row) within a chunk.

    tile_col and tile_row are in [0, TILES_PER_CHUNK_ROW).
    Within a chunk: 8×8 block grid, each block 2×2 tiles.
    """
    block_col = tile_col // TILES_PER_BLOCK_ROW   # 0-7
    block_row = tile_row // TILES_PER_BLOCK_COL   # 0-7
    block_entry = chunk[block_row * BLOCKS_PER_CHUNK_ROW + block_col]
    block_id = block_entry & 0x3FF                # 10-bit mask (confirmed by scroll_camera.asm)
    if block_id >= len(blocks):
        return 0  # out-of-range → transparent tile
    sub_col = tile_col & 1  # 0 or 1 within block
    sub_row = tile_row & 1  # 0 or 1 within block
    word_idx = sub_row * TILES_PER_BLOCK_ROW + sub_col
    return blocks[block_id][word_idx]


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

    Format: col 0 words (STRIP_TILE_HEIGHT big-endian uint16s), then col 1, ...
    Total size: len(strips) * STRIP_TILE_HEIGHT * 2 bytes.
    """
    with open(path, "wb") as f:
        for strip in strips:
            for word in strip:
                f.write(struct.pack(">H", word))


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
# Self-tests
# ---------------------------------------------------------------------------

def test_kos_decompress():
    """Smoke test: decompress 16x16 OJZ.bin and check basic properties."""
    data = open(BLOCK_MAP_PATH, "rb").read()
    decoded, end_pos = kos_decompress(data, 0)
    assert len(decoded) > 0, "Block map decompressed to empty"
    # Decompressed data is floor-aligned to whole blocks
    num_blocks = len(decoded) // (WORDS_PER_BLOCK * 2)
    assert num_blocks >= 1000, f"Expected >=1000 blocks, got {num_blocks}"
    print(f"  [OK] kos_decompress: {len(data)} bytes -> {len(decoded)} bytes, "
          f"{num_blocks} blocks")


def test_load_block_map():
    """Load block map and validate structure."""
    blocks = load_block_map(BLOCK_MAP_PATH)
    assert len(blocks) > 1000, f"Expected >1000 blocks, got {len(blocks)}"
    for i, blk in enumerate(blocks[:10]):
        assert len(blk) == WORDS_PER_BLOCK, (
            f"Block {i} has {len(blk)} words, expected {WORDS_PER_BLOCK}"
        )
    print(f"  [OK] load_block_map: {len(blocks)} blocks loaded")


def test_load_chunk_map():
    """Load chunk map and validate structure."""
    chunks = load_chunk_map(CHUNK_MAP_PATH)
    assert len(chunks) >= 92, f"Expected >=92 chunks, got {len(chunks)}"
    for i, ch in enumerate(chunks[:5]):
        assert len(ch) == 64, f"Chunk {i} has {len(ch)} words, expected 64"
    # All block IDs in stream 1 must fit in the block table (verified: 2002 blocks)
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


def run_tests():
    """Run all self-tests."""
    print("Running ojz_strip_gen tests...")
    test_kos_decompress()
    test_load_block_map()
    test_load_chunk_map()
    test_load_layout()
    test_generate_strips_sec0()
    test_column_layout_correctness()
    test_explicit_truncation()
    test_binary_round_trip()
    print("All tests passed")


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate():
    """Generate strip data for all OJZ sections."""
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
    pattern = os.path.join(LAYOUT_DIR, "OJZ_1_sec*.bin")
    section_files = sorted(glob.glob(pattern))

    if not section_files:
        print(f"ERROR: No layout files found matching {pattern}")
        sys.exit(1)

    total_strips = 0
    first_strips = None
    for sec_path in section_files:
        sec_name = os.path.basename(sec_path).replace(".bin", "")
        sec_id = sec_name.split("sec")[1]

        layout = load_layout(sec_path)
        if not layout:
            print(f"  WARNING: {sec_name} produced empty layout, skipping")
            continue

        strips = generate_section_strips(layout, chunks, blocks)
        n_cols = len(strips)

        # Write all columns concatenated into a single plane A file
        out_a = os.path.join(out_dir, f"sec{sec_id}_strips_a.bin")
        write_strips_to_file(strips, out_a)

        # Write plane B placeholder (all zeros, same size)
        out_b = os.path.join(out_dir, f"sec{sec_id}_strips_b.bin")
        with open(out_b, "wb") as f:
            f.write(bytes(n_cols * STRIP_TILE_HEIGHT * 2))
        print(f"  sec{sec_id}: plane B placeholder -> {out_b}")

        if first_strips is None:
            first_strips = strips

        total_strips += n_cols
        print(
            f"  {sec_name}: {len(layout)} rows × {len(layout[0])} chunks "
            f"→ {n_cols} strips → {out_a}"
        )

    # Copy palette file
    pal_src  = os.path.join(src_dir, "art", "palettes", "OJZ.bin")
    pal_dest = os.path.join(out_dir, "ojz_palette.bin")
    shutil.copy(pal_src, pal_dest)
    print(f"Copied palette -> {pal_dest}")

    print(f"Done. {total_strips} total strips written to {out_dir}")

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
        print(f"Usage: {sys.argv[0]} test|generate")
        sys.exit(1)

    if sys.argv[1] == "test":
        run_tests()
    else:
        generate()


if __name__ == "__main__":
    main()
