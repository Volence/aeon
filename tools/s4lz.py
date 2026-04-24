#!/usr/bin/env python3
"""
S4LZ — Sonic 4 Engine compression tool.

A word-aligned LZ compressor designed for Sega Genesis (68000) decompression.
Supports tile-delta XOR preprocessing for improved compression of tile art.

Usage:
    s4lz.py compress [--tile-delta] <input> <output>
    s4lz.py decompress <input> <output>
    s4lz.py verify [--tile-delta] <input>
    s4lz.py test
"""

import argparse
import struct
import sys
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TILE_SIZE = 32          # Genesis tile: 8x8 pixels, 4bpp = 32 bytes
MIN_MATCH_WORDS = 2     # Minimum match length in words (4 bytes)
MAX_WINDOW = 65534      # Maximum backwards offset in bytes (16-bit, even)
TOKEN_END = 0x00        # End-of-stream marker
EXTENDED_THRESHOLD = 15 # Nibble value that triggers extension word

# ---------------------------------------------------------------------------
# Tile-delta XOR preprocessing
# ---------------------------------------------------------------------------

def tile_delta_encode(data: bytes) -> bytes:
    """XOR each 32-byte tile against the previous tile. First tile unchanged."""
    if len(data) == 0:
        return data
    result = bytearray(data[:TILE_SIZE])
    for offset in range(TILE_SIZE, len(data), TILE_SIZE):
        chunk_end = min(offset + TILE_SIZE, len(data))
        prev_start = offset - TILE_SIZE
        for i in range(offset, chunk_end):
            result.append(data[i] ^ data[prev_start + (i - offset)])
    return bytes(result)


def tile_delta_decode(data: bytes) -> bytes:
    """Undo tile-delta XOR. First tile unchanged, each subsequent tile
    is XORed with the reconstructed previous tile."""
    if len(data) == 0:
        return data
    result = bytearray(data[:TILE_SIZE])
    for offset in range(TILE_SIZE, len(data), TILE_SIZE):
        chunk_end = min(offset + TILE_SIZE, len(data))
        prev_start = offset - TILE_SIZE
        for i in range(offset, chunk_end):
            result.append(data[i] ^ result[prev_start + (i - offset)])
    return bytes(result)

# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def _build_token(lit_count: int, match_count: int) -> int:
    """Build a token byte from literal and match word counts.
    Each nibble encodes 0-14 directly; 15 means 'read next word for count'."""
    lit_nibble = min(lit_count, 15)
    match_nibble = min(match_count, 15)
    return (lit_nibble << 4) | match_nibble

# ---------------------------------------------------------------------------
# Match finder (brute-force scan within window)
# ---------------------------------------------------------------------------

def _find_best_match(data: bytes, pos: int, data_len: int) -> tuple:
    """Find the longest word-aligned match looking backwards from pos.
    Returns (offset_back, length_in_words) or (0, 0) if no match."""
    best_offset = 0
    best_length = 0  # in words

    # Search window: from max lookback to current position, word-aligned
    min_start = max(0, pos - MAX_WINDOW)
    # We need at least MIN_MATCH_WORDS words to match
    min_bytes = MIN_MATCH_WORDS * 2

    if pos + min_bytes > data_len:
        return (0, 0)

    # Scan backwards through possible match positions (word-aligned)
    scan_pos = min_start
    while scan_pos < pos:
        # Check how many words match
        match_words = 0
        while True:
            src_off = scan_pos + match_words * 2
            dst_off = pos + match_words * 2
            if dst_off + 2 > data_len:
                break
            if src_off + 2 > pos:
                # Allow overlapping matches — copy word by word
                # The source catches up to where we've already written
                pass
            if data[src_off] == data[dst_off] and data[src_off + 1] == data[dst_off + 1]:
                match_words += 1
            else:
                break

        if match_words >= MIN_MATCH_WORDS and match_words > best_length:
            best_length = match_words
            best_offset = pos - scan_pos  # byte distance backwards

        scan_pos += 2  # word-aligned steps

    return (best_offset, best_length)


def _find_best_match_fast(data: bytes, pos: int, data_len: int,
                          hash_table: dict) -> tuple:
    """Hash-chain match finder for better performance on large inputs.
    Returns (offset_back, length_in_words) or (0, 0)."""
    best_offset = 0
    best_length = 0
    min_bytes = MIN_MATCH_WORDS * 2

    if pos + min_bytes > data_len:
        return (0, 0)

    # Hash on first two words (4 bytes)
    key = (data[pos], data[pos + 1], data[pos + 2], data[pos + 3])
    candidates = hash_table.get(key, [])

    # Check candidates in reverse order (most recent first)
    for scan_pos in reversed(candidates):
        dist = pos - scan_pos
        if dist > MAX_WINDOW:
            continue
        if dist <= 0:
            continue

        # Count matching words
        match_words = 0
        while True:
            src_off = scan_pos + match_words * 2
            dst_off = pos + match_words * 2
            if dst_off + 2 > data_len:
                break
            if data[src_off] == data[dst_off] and data[src_off + 1] == data[dst_off + 1]:
                match_words += 1
            else:
                break

        if match_words >= MIN_MATCH_WORDS and match_words > best_length:
            best_length = match_words
            best_offset = dist
            # Good enough heuristic: stop if we found a long match
            if best_length >= 32:
                break

    return (best_offset, best_length)

# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------

def compress(data: bytes, tile_delta: bool = False) -> bytes:
    """Compress data using S4LZ format.
    Returns the complete compressed stream including header."""
    original_data = data

    # Apply tile-delta preprocessing if requested
    if tile_delta:
        data = tile_delta_encode(data)

    data_len = len(data)

    # Build header
    flags = 1 if tile_delta else 0
    header = struct.pack(">HBB", data_len, flags, 0)

    if data_len == 0:
        # Empty data: just header + end token
        return header + bytes([TOKEN_END])

    # Ensure data is word-aligned for processing
    work_data = data
    if data_len % 2 != 0:
        work_data = data + b'\x00'
        data_len = len(work_data)

    # Build hash table for fast matching
    hash_table = {}
    for i in range(0, data_len - 3, 2):
        key = (work_data[i], work_data[i + 1], work_data[i + 2], work_data[i + 3])
        if key not in hash_table:
            hash_table[key] = []
        hash_table[key].append(i)

    # Optimal parser (forward DP with sequence-aware cost model):
    # Each match creates a new sequence boundary (costing 2 bytes for the
    # next token+pad). The DP accounts for this, so matches are only chosen
    # when they genuinely save bytes after all overhead.
    num_words = data_len // 2
    INF = float('inf')

    # Phase 1: find best match at each word position
    match_at = [None] * num_words  # (byte_offset, word_length) or None
    for i in range(num_words):
        offset, length = _find_best_match_fast(work_data, i * 2, data_len, hash_table)
        if length >= MIN_MATCH_WORDS:
            match_at[i] = (offset, length)

    # Phase 2: forward DP — arrival[i] = min compressed bytes for words[0..i)
    # Cost includes token+pad overhead for sequence boundaries.
    arrival = [INF] * (num_words + 1)
    arrival[0] = 2  # first sequence always costs token+pad
    prev = [None] * (num_words + 1)

    for i in range(num_words):
        if arrival[i] == INF:
            continue

        # Option 1: literal word (2 bytes, stays in current sequence)
        new_cost = arrival[i] + 2
        if new_cost < arrival[i + 1]:
            arrival[i + 1] = new_cost
            prev[i + 1] = ('lit', i)

        # Option 2: match — try all sublengths of best match
        if match_at[i] is not None:
            m_offset, max_len = match_at[i]
            for m_len in range(MIN_MATCH_WORDS, max_len + 1):
                dest = i + m_len
                if dest > num_words:
                    break
                # Match cost: offset word (2) + extension if >= 15
                m_cost = 2
                if m_len >= 15:
                    m_cost += 2
                # Match ends current sequence; next sequence needs token+pad
                if dest < num_words:
                    m_cost += 2
                new_cost = arrival[i] + m_cost
                if new_cost < arrival[dest]:
                    arrival[dest] = new_cost
                    prev[dest] = ('match', i, m_offset, m_len)

    # Phase 3: trace back to recover optimal parse
    path = []
    i = num_words
    while i > 0:
        p = prev[i]
        path.append(p)
        i = p[1]  # source position
    path.reverse()

    # Phase 4: build sequences from path
    sequences = []
    literal_words = []
    for entry in path:
        if entry[0] == 'lit':
            pos = entry[1]
            literal_words.append((work_data[pos * 2], work_data[pos * 2 + 1]))
        else:
            _, pos, m_offset, m_length = entry
            sequences.append((list(literal_words), m_offset, m_length))
            literal_words = []

    if literal_words:
        sequences.append((list(literal_words), 0, 0))

    # Encode sequences into the compressed stream
    out = bytearray(header)

    for lits, match_offset, match_words in sequences:
        lit_count = len(lits)
        match_count = match_words

        token = _build_token(lit_count, match_count)
        lit_nibble = (token >> 4) & 0x0F
        match_nibble = token & 0x0F

        # Token + pad byte (word-aligned for 68000)
        out.append(token)
        out.append(0)

        # Literal count extension (word, when nibble == 15)
        if lit_nibble == 15:
            out.extend(struct.pack(">H", lit_count))

        # Literal data words
        for (hi, lo) in lits:
            out.append(hi)
            out.append(lo)

        # Match offset + optional count extension
        if match_count > 0:
            out.extend(struct.pack(">H", match_offset))
            if match_nibble == 15:
                out.extend(struct.pack(">H", match_count))

    # End-of-stream + pad
    out.append(TOKEN_END)
    out.append(0)

    return bytes(out)

# ---------------------------------------------------------------------------
# Decompressor
# ---------------------------------------------------------------------------

def decompress(compressed: bytes) -> bytes:
    """Decompress S4LZ data. Returns the decompressed bytes.
    Automatically applies tile-delta decode if the header flag is set."""
    if len(compressed) < 4:
        raise ValueError("Compressed data too short for header")

    # Parse header
    uncompressed_size = struct.unpack(">H", compressed[0:2])[0]
    flags = compressed[2]
    _reserved = compressed[3]
    tile_delta = bool(flags & 1)

    if uncompressed_size == 0:
        return b""

    output = bytearray()
    pos = 4  # skip header

    while pos < len(compressed):
        token = compressed[pos]
        pos += 2  # token + pad byte (word-aligned)

        # End of stream
        if token == TOKEN_END:
            break

        lit_count = (token >> 4) & 0x0F
        match_raw = token & 0x0F

        # Extended literal count (word)
        if lit_count == 15:
            lit_count = struct.unpack(">H", compressed[pos:pos + 2])[0]
            pos += 2

        # Read literal words
        for _ in range(lit_count):
            output.append(compressed[pos])
            output.append(compressed[pos + 1])
            pos += 2

        # Match: offset + optional extended count
        if match_raw > 0:
            match_offset = struct.unpack(">H", compressed[pos:pos + 2])[0]
            pos += 2
            match_count = match_raw
            if match_raw == 15:
                match_count = struct.unpack(">H", compressed[pos:pos + 2])[0]
                pos += 2
            src_start = len(output) - match_offset
            if src_start < 0:
                raise ValueError(
                    f"Match offset {match_offset} exceeds output size {len(output)}")
            # Copy word by word (supports overlapping matches)
            for i in range(match_count):
                src_pos = src_start + i * 2
                output.append(output[src_pos])
                output.append(output[src_pos + 1])

    # Truncate to declared size (handles odd-length original data via padding)
    result = bytes(output[:uncompressed_size])

    # Undo tile-delta if flag was set
    if tile_delta:
        result = tile_delta_decode(result)

    return result

# ---------------------------------------------------------------------------
# CLI: compress
# ---------------------------------------------------------------------------

def cmd_compress(args):
    with open(args.input, "rb") as f:
        data = f.read()

    compressed = compress(data, tile_delta=args.tile_delta)

    with open(args.output, "wb") as f:
        f.write(compressed)

    ratio = len(compressed) / len(data) if len(data) > 0 else 0.0
    print(f"Compressed: {len(data)} -> {len(compressed)} bytes "
          f"(ratio {ratio:.3f})"
          f"{' [tile-delta]' if args.tile_delta else ''}")

# ---------------------------------------------------------------------------
# CLI: decompress
# ---------------------------------------------------------------------------

def cmd_decompress(args):
    with open(args.input, "rb") as f:
        compressed = f.read()

    data = decompress(compressed)

    with open(args.output, "wb") as f:
        f.write(data)

    print(f"Decompressed: {len(compressed)} -> {len(data)} bytes")

# ---------------------------------------------------------------------------
# CLI: verify
# ---------------------------------------------------------------------------

def cmd_verify(args):
    with open(args.input, "rb") as f:
        original = f.read()

    compressed = compress(original, tile_delta=args.tile_delta)
    decompressed = decompress(compressed)

    if decompressed == original:
        ratio = len(compressed) / len(original) if len(original) > 0 else 0.0
        print(f"PASS: {len(original)} -> {len(compressed)} -> {len(decompressed)} bytes "
              f"(ratio {ratio:.3f})"
              f"{' [tile-delta]' if args.tile_delta else ''}")
    else:
        print(f"FAIL: round-trip mismatch!")
        print(f"  Original:     {len(original)} bytes")
        print(f"  Compressed:   {len(compressed)} bytes")
        print(f"  Decompressed: {len(decompressed)} bytes")
        # Find first difference
        for i in range(min(len(original), len(decompressed))):
            if original[i] != decompressed[i]:
                print(f"  First diff at byte {i}: "
                      f"original=0x{original[i]:02X} got=0x{decompressed[i]:02X}")
                break
        if len(original) != len(decompressed):
            print(f"  Length mismatch: expected {len(original)}, got {len(decompressed)}")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Built-in self-tests
# ---------------------------------------------------------------------------

def _run_test(name: str, data: bytes, tile_delta: bool = False) -> bool:
    """Run a single compress-decompress round-trip test."""
    try:
        compressed = compress(data, tile_delta=tile_delta)
        decompressed = decompress(compressed)

        if decompressed != data:
            # Find first difference
            for i in range(min(len(data), len(decompressed))):
                if data[i] != decompressed[i]:
                    print(f"  FAIL {name}: mismatch at byte {i} "
                          f"(expected 0x{data[i]:02X}, got 0x{decompressed[i]:02X})")
                    return False
            print(f"  FAIL {name}: length mismatch "
                  f"(expected {len(data)}, got {len(decompressed)})")
            return False

        ratio = len(compressed) / len(data) if len(data) > 0 else 0.0
        td_tag = " [tile-delta]" if tile_delta else ""
        print(f"  PASS {name}: {len(data)} -> {len(compressed)} bytes "
              f"(ratio {ratio:.3f}){td_tag}")
        return True

    except Exception as e:
        print(f"  FAIL {name}: exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def cmd_test(_args=None):
    """Run built-in self-tests."""
    print("S4LZ self-tests")
    print("=" * 60)

    passed = 0
    failed = 0
    total = 0

    def check(result):
        nonlocal passed, failed, total
        total += 1
        if result:
            passed += 1
        else:
            failed += 1

    # Test 1: Empty data
    check(_run_test("1. Empty data", b""))

    # Test 2: Single tile (32 bytes of sequential values)
    single_tile = bytes(range(32))
    check(_run_test("2. Single tile (32B sequential)", single_tile))

    # Test 3: Multiple identical tiles (128 bytes = 4 tiles)
    one_tile = bytes([0xAA, 0x55] * 16)  # 32 bytes
    identical_tiles = one_tile * 4  # 128 bytes
    check(_run_test("3. Identical tiles (128B)", identical_tiles))

    # Test 4: Data with known patterns — verify compression ratio < 1.0
    pattern_data = (bytes([0x00, 0x11, 0x22, 0x33]) * 64)  # 256 bytes, highly repetitive
    compressed_pattern = compress(pattern_data)
    ratio = len(compressed_pattern) / len(pattern_data)
    is_compressed = ratio < 1.0
    result4 = _run_test("4. Known pattern (256B)", pattern_data)
    if result4 and not is_compressed:
        print(f"  FAIL 4b. Compression ratio {ratio:.3f} >= 1.0 (not compressing)")
        check(False)
    else:
        check(result4 and is_compressed)
        if is_compressed:
            print(f"       Compression ratio check: {ratio:.3f} < 1.0 OK")

    # Test 5: Tile-delta with identical tiles
    identical_tile_data = bytes([0x12, 0x34, 0x56, 0x78] * 8) * 4  # 4 identical 32-byte tiles
    check(_run_test("5. Tile-delta identical tiles", identical_tile_data, tile_delta=True))

    # Test 6: Tile-delta with dissimilar tiles
    dissimilar = bytearray()
    for t in range(4):
        for i in range(32):
            dissimilar.append((t * 37 + i * 13) & 0xFF)
    check(_run_test("6. Tile-delta dissimilar tiles", bytes(dissimilar), tile_delta=True))

    # Test 7: Large data (1000+ bytes)
    large_data = bytearray()
    for i in range(600):
        large_data.append((i * 7) & 0xFF)
        large_data.append((i * 13) & 0xFF)
    check(_run_test("7. Large data (1200B)", bytes(large_data)))

    # Test 8: Odd-length data (edge case)
    odd_data = bytes(range(33))  # 33 bytes, not word-aligned
    check(_run_test("8. Odd-length data (33B)", odd_data))

    # Test 9: All zeros (maximum compression)
    zeros = bytes(256)
    check(_run_test("9. All zeros (256B)", zeros))

    # Test 10: Random-ish data (worst case)
    # Use a simple PRNG for reproducibility
    rng_data = bytearray()
    state = 0xDEAD
    for _ in range(512):
        state = (state * 1103515245 + 12345) & 0xFFFF
        rng_data.append((state >> 8) & 0xFF)
    check(_run_test("10. Pseudo-random data (512B)", bytes(rng_data)))

    # Test 11: Data requiring extended counts (>14 literal words)
    # 40 unique words followed by a repeated section
    extended_data = bytearray()
    for i in range(40):
        extended_data.extend(struct.pack(">H", 0x1000 + i))
    # Then repeat first 10 words
    for i in range(10):
        extended_data.extend(struct.pack(">H", 0x1000 + i))
    check(_run_test("11. Extended literal counts", bytes(extended_data)))

    # Test 12: Tile-delta + large data
    large_tile_data = bytearray()
    for t in range(40):
        base = t * 3
        for i in range(32):
            large_tile_data.append((base + i) & 0xFF)
    check(_run_test("12. Tile-delta large (1280B)", bytes(large_tile_data), tile_delta=True))

    print("=" * 60)
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed.")

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="S4LZ — Sonic 4 Engine compression tool")
    subparsers = parser.add_subparsers(dest="command")

    # compress
    p_compress = subparsers.add_parser("compress", help="Compress a file")
    p_compress.add_argument("--tile-delta", action="store_true",
                            help="Enable tile-delta XOR preprocessing")
    p_compress.add_argument("input", help="Input file")
    p_compress.add_argument("output", help="Output file")

    # decompress
    p_decompress = subparsers.add_parser("decompress",
                                          help="Decompress a file")
    p_decompress.add_argument("input", help="Input file")
    p_decompress.add_argument("output", help="Output file")

    # verify
    p_verify = subparsers.add_parser("verify",
                                      help="Verify round-trip compression")
    p_verify.add_argument("--tile-delta", action="store_true",
                          help="Enable tile-delta XOR preprocessing")
    p_verify.add_argument("input", help="Input file")

    # test
    subparsers.add_parser("test", help="Run built-in self-tests")

    args = parser.parse_args()

    if args.command == "compress":
        cmd_compress(args)
    elif args.command == "decompress":
        cmd_decompress(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
