#!/usr/bin/env python3
"""
S4LZ — Sonic 4 Engine compression tool.

A word-aligned LZ compressor designed for Sega Genesis (68000) decompression.
Supports tile-delta XOR preprocessing for improved compression of tile art.

Stream format v3 (version byte = 1):
    Header (4 bytes): [u16 BE uncompressed_size][u8 flags: bit0=tile_delta][u8 version=1]
    Per sequence, token word = [token.b][offmark.b]:
        token.b hi nibble = literal word count (15 = u16 BE extension word)
        token.b lo nibble = match word count   (15 = u16 BE extension word)
        token.b $00 = end of stream (offmark.b is $00; full word consumed)
        offmark.b = match_offset/2 for offsets 2..510 (short form, no offset
                    word); $00 = long form (u16 BE offset word after literals)
                    or no match at all (match nibble 0)
    Stream order: token word, [lit ext word], literals,
                  [offset word — long form only], [match ext word]

v1 streams (version byte = 0) used a $00 pad byte where offmark.b now lives
and always emitted a u16 offset word. decompress() decodes both versions;
compress() emits v3 only.

Usage:
    s4lz.py compress [--tile-delta] <input> <output>
    s4lz.py decompress <input> <output>
    s4lz.py verify [--tile-delta] <input>
    s4lz.py test
"""

import argparse
import struct
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TILE_SIZE = 32          # Genesis tile: 8x8 pixels, 4bpp = 32 bytes
MIN_MATCH_WORDS = 2     # Minimum match length in words (4 bytes)
MAX_WINDOW = 32766      # Maximum backwards offset in bytes.
                        # 68000 decoder uses suba.w (sign-extends); offsets must stay < $8000.
                        # Zero ratio cost — all dest buffers are <= 32 KB.
MAX_SHORT_OFFSET = 510  # Maximum byte offset encodable in offmark (255 * 2)
TOKEN_END = 0x00        # End-of-stream marker
EXTENDED_THRESHOLD = 15 # Nibble value that triggers extension word
VERSION_V1 = 0          # Legacy: pad byte + always-emitted offset word
VERSION_V3 = 1          # Token word with offmark short-offset slot

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
# Match finder (hash-chain, two candidates per position)
# ---------------------------------------------------------------------------

def _find_best_matches(data: bytes, pos: int, data_len: int,
                       hash_table: dict, dict_len: int = 0) -> tuple:
    """Hash-chain match finder returning two candidates:
        ((offset_any, length_any), (offset_short, length_short))
    where the second candidate is the longest match with byte offset
    <= MAX_SHORT_OFFSET (encodable in offmark, costing 0 extra bytes).
    Either candidate is (0, 0) when no match of MIN_MATCH_WORDS exists.

    When compressing with a prepended dictionary (`data` = dict + payload,
    dict_len > 0), matches whose source starts inside the dictionary must
    NOT extend past the dict/payload boundary: the 68000 decoder copies the
    dict portion from ROM with an ascending pointer, so a straddling match
    would read past the dictionary into unrelated ROM bytes."""
    best_offset = 0
    best_length = 0
    best_short_offset = 0
    best_short_length = 0
    min_bytes = MIN_MATCH_WORDS * 2

    if pos + min_bytes > data_len:
        return ((0, 0), (0, 0))

    # Hash on first two words (4 bytes)
    key = (data[pos], data[pos + 1], data[pos + 2], data[pos + 3])
    candidates = hash_table.get(key, [])

    # Check candidates in reverse order (most recent = smallest offset first).
    # Because offsets only grow as we iterate, every short-offset candidate
    # is examined before the early-exit below can trigger.
    for scan_pos in reversed(candidates):
        dist = pos - scan_pos
        if dist > MAX_WINDOW:
            continue
        if dist <= 0:
            continue

        # Count matching words (capped at the dict boundary for dict sources)
        max_words = (data_len - pos) // 2
        if scan_pos < dict_len:
            max_words = min(max_words, (dict_len - scan_pos) // 2)
        match_words = 0
        while match_words < max_words:
            src_off = scan_pos + match_words * 2
            dst_off = pos + match_words * 2
            if data[src_off] == data[dst_off] and data[src_off + 1] == data[dst_off + 1]:
                match_words += 1
            else:
                break

        if match_words >= MIN_MATCH_WORDS:
            if match_words > best_length:
                best_length = match_words
                best_offset = dist
            if dist <= MAX_SHORT_OFFSET and match_words > best_short_length:
                best_short_length = match_words
                best_short_offset = dist
            # Good enough heuristic: stop if we found a long match.
            # All nearer (short-offset) candidates were already seen.
            if best_length >= 32:
                break

    return ((best_offset, best_length), (best_short_offset, best_short_length))

# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------

def _match_cost(offset: int, m_len: int, at_end: bool) -> int:
    """Extra bytes a match adds beyond the words it replaces:
    long offsets need a u16 offset word, counts >= 15 need an extension
    word, and any match ends the sequence (next token word, unless at end)."""
    cost = 0 if offset <= MAX_SHORT_OFFSET else 2
    if m_len >= EXTENDED_THRESHOLD:
        cost += 2
    if not at_end:
        cost += 2
    return cost


def compress(data: bytes, tile_delta: bool = False,
             dictionary: bytes = b'') -> bytes:
    """Compress data into an S4LZ v3 stream. Returns the compressed bytes.

    `dictionary` pre-seeds the LZ window: matches may reach back into it,
    with offsets measured as distances in the dict+data concatenation. The
    emitted stream encodes ONLY the data (header size = len(data)); the
    decoder must be given the same dictionary. Matches never straddle the
    dict/data boundary (see _find_best_matches)."""
    original_data = data

    # Apply tile-delta preprocessing if requested
    if tile_delta:
        if dictionary:
            raise ValueError("dictionary is not supported with tile_delta")
        data = tile_delta_encode(data)

    dict_len = len(dictionary)
    if dict_len % 2 != 0:
        raise ValueError(f"dictionary length {dict_len} must be word-even")

    data_len = len(data)
    if dict_len + data_len > MAX_WINDOW:
        raise ValueError(
            f"dict+data {dict_len + data_len} exceeds window {MAX_WINDOW}")

    # Build header
    flags = 1 if tile_delta else 0
    header = struct.pack(">HBB", data_len, flags, VERSION_V3)

    if data_len == 0:
        return header + bytes([TOKEN_END, 0])

    # Ensure data is word-aligned for processing
    work_data = data
    if data_len % 2 != 0:
        work_data = data + b'\x00'
        data_len = len(work_data)

    # The match window is the dictionary prepended to the data; offsets
    # are distances within this concatenation.
    work_data = dictionary + work_data
    concat_len = dict_len + data_len

    # Build hash table for fast matching (dict + data positions)
    hash_table = {}
    for i in range(0, concat_len - 3, 2):
        key = (work_data[i], work_data[i + 1], work_data[i + 2], work_data[i + 3])
        if key not in hash_table:
            hash_table[key] = []
        hash_table[key].append(i)

    # Optimal parser (forward DP with sequence-aware cost model):
    # Each match creates a sequence boundary (costing 2 bytes for the next
    # token word). Short offsets (<= 510) cost 0 extra bytes; long offsets
    # cost a 2-byte offset word — so a NEARER, possibly shorter match can
    # beat the longest one. Both candidates feed the DP.
    num_words = data_len // 2
    INF = float('inf')

    # Phase 1: best matches at each DATA word position (concat position
    # dict_len + i*2) — (any, short) candidates
    match_at = [None] * num_words
    for i in range(num_words):
        best_any, best_short = _find_best_matches(work_data,
                                                  dict_len + i * 2,
                                                  concat_len,
                                                  hash_table, dict_len)
        cands = []
        if best_any[1] >= MIN_MATCH_WORDS:
            cands.append(best_any)
        if best_short[1] >= MIN_MATCH_WORDS and best_short != best_any:
            cands.append(best_short)
        if cands:
            match_at[i] = cands

    # Phase 2: forward DP — arrival[i] = min compressed bytes for words[0..i)
    arrival = [INF] * (num_words + 1)
    arrival[0] = 2  # first sequence always costs a token word
    prev = [None] * (num_words + 1)

    for i in range(num_words):
        if arrival[i] == INF:
            continue

        # Option 1: literal word (2 bytes, stays in current sequence)
        new_cost = arrival[i] + 2
        if new_cost < arrival[i + 1]:
            arrival[i + 1] = new_cost
            prev[i + 1] = ('lit', i)

        # Option 2: match — try all sublengths of each candidate
        if match_at[i] is not None:
            for m_offset, max_len in match_at[i]:
                for m_len in range(MIN_MATCH_WORDS, max_len + 1):
                    dest = i + m_len
                    if dest > num_words:
                        break
                    m_cost = _match_cost(m_offset, m_len, dest >= num_words)
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
            pos = dict_len + entry[1] * 2          # data word -> concat byte pos
            literal_words.append((work_data[pos], work_data[pos + 1]))
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

        # Token word: token byte + offmark byte
        short_form = (match_count > 0 and
                      2 <= match_offset <= MAX_SHORT_OFFSET)
        offmark = (match_offset >> 1) if short_form else 0
        out.append(token)
        out.append(offmark)

        # Literal count extension (word, when nibble == 15)
        if lit_nibble == 15:
            out.extend(struct.pack(">H", lit_count))

        # Literal data words
        for (hi, lo) in lits:
            out.append(hi)
            out.append(lo)

        # Long-form match offset (after literals), then count extension
        if match_count > 0:
            if not short_form:
                out.extend(struct.pack(">H", match_offset))
            if match_nibble == 15:
                out.extend(struct.pack(">H", match_count))

    # End-of-stream word
    out.append(TOKEN_END)
    out.append(0)

    return bytes(out)

# ---------------------------------------------------------------------------
# Decompressor
# ---------------------------------------------------------------------------

def _decompress_v1(compressed: bytes) -> bytearray:
    """Decode a v1 token stream (pad byte, always-emitted offset word)."""
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

    return output


def _decompress_v3(compressed: bytes, dictionary: bytes = b'') -> bytearray:
    """Decode a v3 token stream (offmark short-offset slot).

    `dictionary` mirrors the 68000 dict decoder: match sources reaching
    below the output start are read from the dictionary tail. A match must
    lie entirely in the dictionary or entirely in the output — straddling
    is rejected (the ROM decoder would read garbage past the dict end)."""
    dict_len = len(dictionary)
    output = bytearray()
    pos = 4  # skip header

    while pos + 1 < len(compressed):
        token = compressed[pos]
        offmark = compressed[pos + 1]
        pos += 2  # token word

        # End of stream
        if token == TOKEN_END:
            if offmark != 0:
                raise ValueError(
                    f"EOS token at stream pos {pos - 2} has non-zero offmark 0x{offmark:02X} "
                    f"(EOS word must be $0000)")
            break

        lit_count = (token >> 4) & 0x0F
        match_raw = token & 0x0F

        if match_raw == 0 and offmark != 0:
            raise ValueError(
                f"Nonzero offmark 0x{offmark:02X} with no match at stream pos {pos - 2}")

        # Extended literal count (word)
        if lit_count == 15:
            lit_count = struct.unpack(">H", compressed[pos:pos + 2])[0]
            pos += 2

        # Read literal words
        for _ in range(lit_count):
            output.append(compressed[pos])
            output.append(compressed[pos + 1])
            pos += 2

        # Match: short offset from offmark, or long offset word after literals
        if match_raw > 0:
            if offmark != 0:
                match_offset = offmark * 2
            else:
                match_offset = struct.unpack(">H", compressed[pos:pos + 2])[0]
                pos += 2
            match_count = match_raw
            if match_raw == 15:
                match_count = struct.unpack(">H", compressed[pos:pos + 2])[0]
                pos += 2
            src_start = len(output) - match_offset
            if src_start < 0:
                # Dictionary hit: rebase into the dict tail (the same
                # arithmetic the 68000 decoder applies via its rebase
                # constant: src = dict_end - (output_start - src)).
                dict_pos = dict_len + src_start
                if dict_pos < 0:
                    raise ValueError(
                        f"Match offset {match_offset} reaches below dict "
                        f"(output {len(output)}B, dict {dict_len}B)")
                if src_start + match_count * 2 > 0:
                    raise ValueError(
                        f"Match at output {len(output)} straddles the "
                        f"dict/data boundary (offset {match_offset}, "
                        f"count {match_count})")
                output.extend(dictionary[dict_pos:dict_pos + match_count * 2])
                continue
            # Copy word by word (supports overlapping matches)
            for i in range(match_count):
                src_pos = src_start + i * 2
                output.append(output[src_pos])
                output.append(output[src_pos + 1])

    return output


def decompress(compressed: bytes, dictionary: bytes = b'') -> bytes:
    """Decompress S4LZ data (v1 or v3, dispatched on the version byte).
    Automatically applies tile-delta decode if the header flag is set.
    `dictionary` must match the one used at compression time (v3 only)."""
    if len(compressed) < 4:
        raise ValueError("Compressed data too short for header")

    # Parse header
    uncompressed_size = struct.unpack(">H", compressed[0:2])[0]
    flags = compressed[2]
    version = compressed[3]
    tile_delta = bool(flags & 1)

    if uncompressed_size == 0:
        return b""

    if version == VERSION_V1:
        if dictionary:
            raise ValueError("dictionary is not supported for v1 streams")
        output = _decompress_v1(compressed)
    elif version == VERSION_V3:
        output = _decompress_v3(compressed, dictionary)
    else:
        raise ValueError(f"Unknown S4LZ version byte {version}")

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


def _run_decode_test(name: str, stream: bytes, expected: bytes) -> bool:
    """Decode a hand-constructed stream and compare against expected output."""
    try:
        decoded = decompress(stream)
        if decoded != expected:
            print(f"  FAIL {name}: decoded {len(decoded)}B != expected {len(expected)}B")
            for i in range(min(len(decoded), len(expected))):
                if decoded[i] != expected[i]:
                    print(f"    First diff at byte {i}: "
                          f"expected 0x{expected[i]:02X} got 0x{decoded[i]:02X}")
                    break
            return False
        print(f"  PASS {name}: {len(stream)}B stream -> {len(decoded)}B")
        return True
    except Exception as e:
        print(f"  FAIL {name}: exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def _v3_header(size: int, flags: int = 0) -> bytes:
    return struct.pack(">HBB", size, flags, VERSION_V3)


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

    # Test 13: v1-decode regression — hand-constructed v1 stream
    # (version byte 0, pad byte after token, offset word always emitted)
    v1_stream = bytes([
        0x00, 0x08,             # uncompressed size = 8
        0x00, VERSION_V1,       # flags, version
        0x22, 0x00,             # token: 2 lits, 2-word match + pad byte
        0xAA, 0xBB, 0xCC, 0xDD, # literal words
        0x00, 0x04,             # offset word = 4 (always present in v1)
        0x00, 0x00,             # EOS + pad
    ])
    check(_run_decode_test("13. v1-decode regression",
                           v1_stream, bytes([0xAA, 0xBB, 0xCC, 0xDD,
                                             0xAA, 0xBB, 0xCC, 0xDD])))

    # Test 14: v3 short offset 2 with overlap (offmark = 1, length > 1 word)
    v3_overlap = (_v3_header(10) +
                  bytes([0x14, 0x01,        # 1 lit, 4-word match, offmark 1
                         0xAB, 0xCD]) +     # literal word
                  bytes([0x00, 0x00]))      # EOS word
    check(_run_decode_test("14. v3 short offset 2 (overlap)",
                           v3_overlap, bytes([0xAB, 0xCD] * 5)))

    # Test 15: v3 short offset boundary 510 (offmark = 255)
    lits_255 = bytes((i & 0xFF) for i in range(510))   # 255 unique-ish words
    v3_short_max = (_v3_header(514) +
                    bytes([0xF2, 0xFF]) +              # lit ext, 2-word match, offmark 255
                    struct.pack(">H", 255) +           # literal count extension
                    lits_255 +
                    bytes([0x00, 0x00]))               # EOS word
    check(_run_decode_test("15. v3 short offset 510 (offmark 255)",
                           v3_short_max, lits_255 + lits_255[:4]))

    # Test 16: v3 long offset 512 (offmark = 0, offset word after literals)
    lits_256 = bytes((i * 3) & 0xFF for i in range(512))  # 256 words
    v3_long = (_v3_header(516) +
               bytes([0xF2, 0x00]) +                   # lit ext, 2-word match, long form
               struct.pack(">H", 256) +                # literal count extension
               lits_256 +
               struct.pack(">H", 512) +                # offset word (after literals)
               bytes([0x00, 0x00]))                    # EOS word
    check(_run_decode_test("16. v3 long offset 512",
                           v3_long, lits_256 + lits_256[:4]))

    # Test 17: v3 token with BOTH nibbles extended, short offset
    # (match ext follows literals directly — no offset word in short form)
    lits_16 = bytes((0x40 + i) & 0xFF for i in range(32))  # 16 words
    v3_both_ext = (_v3_header(32 + 40) +
                   bytes([0xFF, 0x01]) +               # both ext, offmark 1
                   struct.pack(">H", 16) +             # literal count extension
                   lits_16 +
                   struct.pack(">H", 20) +             # match count extension
                   bytes([0x00, 0x00]))                # EOS word
    check(_run_decode_test("17. v3 both nibbles extended (short form)",
                           v3_both_ext, lits_16 + lits_16[-2:] * 20))

    # Test 18: encoder picks short form for near matches — exact stream check
    # b'\xAA\x55' * 100: optimal parse = 1 lit + 99-word match at offset 2.
    rep = bytes([0xAA, 0x55]) * 100
    rep_compressed = compress(rep)
    expected_rep = (_v3_header(200) +
                    bytes([0x1F, 0x01,                  # 1 lit, ext match, offmark 1
                           0xAA, 0x55]) +               # literal word
                    struct.pack(">H", 99) +             # match count extension
                    bytes([0x00, 0x00]))                # EOS word
    if rep_compressed == expected_rep:
        print(f"  PASS 18. Encoder short-form stream: {len(rep)} -> {len(rep_compressed)}B exact")
        check(True)
    else:
        print(f"  FAIL 18. Encoder short-form stream mismatch:")
        print(f"    expected {expected_rep.hex()}")
        print(f"    got      {rep_compressed.hex()}")
        check(False)

    # Test 19: encoder round-trip on data engineered for boundary offsets
    # Pattern at 0, unique filler, repeat at distance 510 then 512.
    def boundary_data(gap_bytes: int) -> bytes:
        pattern = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE])
        filler = bytearray()
        i = 0
        while len(filler) < gap_bytes - len(pattern):
            filler.extend(struct.pack(">H", 0x8000 + i))
            i += 1
        return pattern + bytes(filler[:gap_bytes - len(pattern)]) + pattern

    check(_run_test("19a. Boundary offset 510 round-trip", boundary_data(510)))
    check(_run_test("19b. Boundary offset 512 round-trip", boundary_data(512)))

    # Test 20: dictionary round-trip — data shares word runs with the dict
    def _run_dict_test(name, payload, dictionary):
        try:
            comp = compress(payload, dictionary=dictionary)
            out = decompress(comp, dictionary=dictionary)
            if out != payload:
                print(f"  FAIL {name}: round-trip mismatch")
                return False
            print(f"  PASS {name}: {len(payload)} -> {len(comp)} bytes "
                  f"(dict {len(dictionary)}B)")
            return True
        except Exception as e:
            print(f"  FAIL {name}: exception: {e}")
            import traceback
            traceback.print_exc()
            return False

    dict_block = bytes([0x21, 0x43, 0x65, 0x87] * 64)        # 256B of word runs
    payload_like_dict = bytes([0x21, 0x43, 0x65, 0x87] * 32) # entirely dict content
    check(_run_dict_test("20. Dict round-trip (payload in dict)",
                         payload_like_dict, dict_block))
    comp_with = compress(payload_like_dict, dictionary=dict_block)
    comp_without = compress(payload_like_dict)
    if len(comp_with) <= len(comp_without):
        print(f"  PASS 20b. Dict helps: {len(comp_with)} <= {len(comp_without)}B")
        check(True)
    else:
        print(f"  FAIL 20b. Dict made it bigger: {len(comp_with)} > {len(comp_without)}B")
        check(False)

    # Test 21: no-dict regression — empty dictionary is byte-identical
    nodict_data = bytes(rng_data) + identical_tiles
    if compress(nodict_data) == compress(nodict_data, dictionary=b''):
        print("  PASS 21. Empty dict is byte-identical to no dict")
        check(True)
    else:
        print("  FAIL 21. Empty dict changed the stream")
        check(False)

    # Test 22: no-straddle — the tempting match spans the dict/data boundary.
    # dict ends with P1, data starts with P2, and data later repeats P1+P2.
    # A straddling source would be illegal; round-trip success proves the
    # compressor split or avoided it (the dict decoder raises on straddle).
    p1 = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
    p2 = bytes([0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC])
    straddle_dict = bytes([0x0F, 0xF0] * 16) + p1                    # dict tail = P1
    straddle_data = p2 + bytes([0xDE, 0xAD] * 8) + p1 + p2
    check(_run_dict_test("22. Dict no-straddle boundary", straddle_data,
                         straddle_dict))

    # Test 23: dict + real-shaped data — multi-block dict, long offsets
    big_dict = bytes((i * 7) & 0xFF for i in range(1536))            # 2 "blocks"
    big_payload = big_dict[700:1200] + bytes([0xEE] * 64) + big_dict[:96]
    check(_run_dict_test("23. Dict long-offset round-trip", big_payload,
                         big_dict))

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
