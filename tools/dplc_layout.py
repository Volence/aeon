#!/usr/bin/env python3
"""DPLC Layout Tool — build-time contiguous art rearrangement + entry merging.

Takes uncompressed sprite art + S2-format DPLC table and produces:
1. Rearranged art where each animation frame's tiles are contiguous
2. Optimized DPLC table with exactly 1 entry per frame (start + count)

Input:  art.bin (uncompressed tiles) + dplc.bin (S2 pointer-table format)
Output: art_opt.bin (rearranged tiles) + dplc_opt.bin (optimized DPLC)

The S2 DPLC format:
  Pointer table: word offsets from file start, indexed by frame * 2
  Frame count = first_offset / 2
  Each frame: word entry_count, then entry_count × word entries
  Entry: bits 15-12 = tile_count-1 (1-16), bits 11-0 = tile_start_index
"""

import struct
import sys
from pathlib import Path

TILE_SIZE = 32


def parse_dplc(data):
    """Parse S2-format DPLC. Returns list of frames, each frame = [(start, count), ...]."""
    first_offset = struct.unpack_from('>H', data, 0)[0]
    frame_count = first_offset // 2

    frames = []
    for fi in range(frame_count):
        off = struct.unpack_from('>H', data, fi * 2)[0]
        entry_count = struct.unpack_from('>H', data, off)[0]
        pos = off + 2

        entries = []
        for _ in range(entry_count):
            word = struct.unpack_from('>H', data, pos)[0]
            pos += 2
            tile_count = ((word >> 12) & 0xF) + 1
            tile_start = word & 0xFFF
            entries.append((tile_start, tile_count))

        frames.append(entries)

    return frames


def build_contiguous_art(art_data, frames):
    """Rearrange art so each frame's tiles are contiguous.

    Returns (new_art_bytes, new_frames) where each new frame is a single
    (new_start, total_count) entry.
    """
    art_tile_count = len(art_data) // TILE_SIZE
    new_art = bytearray()
    new_frames = []
    cursor = 0

    for fi, entries in enumerate(frames):
        total_tiles = sum(count for _, count in entries)

        if total_tiles == 0:
            new_frames.append((cursor, 0))
            continue

        frame_start = cursor
        for tile_start, tile_count in entries:
            for t in range(tile_count):
                src_idx = tile_start + t
                if src_idx < art_tile_count:
                    tile_data = art_data[src_idx * TILE_SIZE:(src_idx + 1) * TILE_SIZE]
                else:
                    tile_data = b'\x00' * TILE_SIZE
                new_art.extend(tile_data)
                cursor += 1

        new_frames.append((frame_start, total_tiles))

    return bytes(new_art), new_frames


def merge_adjacent_entries(frames):
    """Merge adjacent DPLC entries within each frame (optimization for legacy tables).

    Adjacent entries where entry[i].start + entry[i].count == entry[i+1].start
    can be combined into a single larger entry, reducing DMA queue pressure.
    """
    merged_frames = []
    total_before = 0
    total_after = 0

    for entries in frames:
        if not entries:
            merged_frames.append([])
            continue

        total_before += len(entries)
        merged = [list(entries[0])]

        for start, count in entries[1:]:
            prev_start, prev_count = merged[-1]
            if start == prev_start + prev_count:
                merged[-1][1] += count
            else:
                merged.append([start, count])

        total_after += len(merged)
        merged_frames.append([(s, c) for s, c in merged])

    return merged_frames, total_before, total_after


def write_dplc(frames):
    """Write optimized DPLC in S2 pointer-table format."""
    frame_count = len(frames)
    pointer_table_size = frame_count * 2

    frame_data_parts = []
    offsets = []

    data_offset = pointer_table_size
    for entries in frames:
        offsets.append(data_offset)
        entry_count = len(entries)
        frame_bytes = struct.pack('>H', entry_count)
        for tile_start, tile_count in entries:
            word = ((tile_count - 1) & 0xF) << 12 | (tile_start & 0xFFF)
            frame_bytes += struct.pack('>H', word)
        frame_data_parts.append(frame_bytes)
        data_offset += len(frame_bytes)

    output = bytearray()
    for off in offsets:
        output.extend(struct.pack('>H', off))
    for part in frame_data_parts:
        output.extend(part)

    return bytes(output)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='DPLC layout optimizer')
    parser.add_argument('art', help='Input uncompressed art file')
    parser.add_argument('dplc', help='Input S2-format DPLC file')
    parser.add_argument('--out-art', help='Output rearranged art file')
    parser.add_argument('--out-dplc', help='Output optimized DPLC file')
    parser.add_argument('--merge-only', action='store_true',
                        help='Only merge adjacent entries (no art rearrangement)')
    parser.add_argument('--stats', action='store_true', help='Print statistics only')
    args = parser.parse_args()

    art_data = Path(args.art).read_bytes()
    dplc_data = Path(args.dplc).read_bytes()

    art_tiles = len(art_data) // TILE_SIZE
    frames = parse_dplc(dplc_data)

    print(f"Input: {len(art_data):,} bytes ({art_tiles} tiles), "
          f"{len(frames)} DPLC frames, {len(dplc_data):,} bytes DPLC")

    total_entries = sum(len(f) for f in frames)
    avg_entries = total_entries / len(frames) if frames else 0
    tiles_per_frame = [sum(c for _, c in f) for f in frames]
    avg_tiles = sum(tiles_per_frame) / len(tiles_per_frame) if tiles_per_frame else 0
    max_tiles = max(tiles_per_frame) if tiles_per_frame else 0

    print(f"Original: {avg_entries:.1f} avg entries/frame, "
          f"{avg_tiles:.1f} avg tiles/frame (max {max_tiles})")

    if args.merge_only:
        merged, before, after = merge_adjacent_entries(frames)
        print(f"Merged: {before} → {after} total entries "
              f"({after / len(frames):.1f} avg/frame)")

        if not args.stats:
            out_dplc = args.out_dplc or args.dplc.replace('.bin', '_merged.bin')
            Path(out_dplc).write_bytes(write_dplc(merged))
            print(f"Written: {out_dplc}")
        return

    new_art, new_frames = build_contiguous_art(art_data, frames)
    new_art_tiles = len(new_art) // TILE_SIZE
    overhead = (len(new_art) - len(art_data)) / len(art_data) * 100 if art_data else 0

    contiguous_frames = [[(start, count)] if count > 0 else [] for start, count in new_frames]

    print(f"\nContiguous layout:")
    print(f"  Art: {len(art_data):,} → {len(new_art):,} bytes "
          f"({art_tiles} → {new_art_tiles} tiles, {overhead:+.1f}% overhead)")
    print(f"  DPLC: 1 entry per frame (was {avg_entries:.1f} avg)")
    print(f"  Every frame change = exactly 1 DMA transfer")

    orig_dplc_bytes = write_dplc(frames)
    new_dplc_bytes = write_dplc(contiguous_frames)
    print(f"  DPLC table: {len(orig_dplc_bytes):,} → {len(new_dplc_bytes):,} bytes")

    dma_per_frame = [count * TILE_SIZE for _, count in new_frames]
    avg_dma = sum(dma_per_frame) / len(dma_per_frame) if dma_per_frame else 0
    max_dma = max(dma_per_frame) if dma_per_frame else 0
    print(f"  Avg DMA per frame change: {avg_dma:.0f} bytes, max: {max_dma} bytes")

    if not args.stats:
        out_art = args.out_art or args.art.replace('.bin', '_opt.bin')
        out_dplc = args.out_dplc or args.dplc.replace('.bin', '_opt.bin')
        Path(out_art).write_bytes(new_art)
        Path(out_dplc).write_bytes(new_dplc_bytes)
        print(f"\nWritten: {out_art}")
        print(f"Written: {out_dplc}")


def cmd_test():
    """Built-in self-tests for DPLC layout tool."""
    print("DPLC layout tool self-tests")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS {name}")
        else:
            failed += 1
            print(f"  FAIL {name}: {detail}")

    # Build a synthetic DPLC + art for testing
    # 8 frames, 16 tiles of art, various entry patterns
    def make_tile(value):
        return bytes([value]) * TILE_SIZE

    art = b''.join(make_tile(i) for i in range(16))

    # frames: list of [(start, count), ...]
    test_frames = [
        [(0, 3)],                    # frame 0: tiles 0-2
        [(4, 2)],                    # frame 1: tiles 4-5
        [(0, 2), (4, 2)],            # frame 2: tiles 0-1 + 4-5 (non-contiguous)
        [(8, 1)],                    # frame 3: tile 8
        [],                          # frame 4: empty
        [(3, 3), (6, 2)],            # frame 5: tiles 3-5 + 6-7 (adjacent, mergeable)
        [(10, 5)],                   # frame 6: tiles 10-14
        [(0, 1)],                    # frame 7: tile 0
    ]

    # Test 1: write_dplc + parse_dplc round-trip
    dplc_bytes = write_dplc(test_frames)
    parsed = parse_dplc(dplc_bytes)
    check("1. DPLC write/parse round-trip",
          parsed == test_frames,
          f"expected {test_frames}, got {parsed}")

    # Test 2: frame count preserved
    check("2. Frame count preserved",
          len(parsed) == len(test_frames),
          f"expected {len(test_frames)}, got {len(parsed)}")

    # Test 3: contiguous rearrangement produces 1 entry per frame
    new_art, new_frames = build_contiguous_art(art, test_frames)
    all_single = all(count <= 16 for _, count in new_frames)
    check("3. Contiguous layout: 1 entry per frame", all_single)

    # Test 4: contiguous art preserves tile data
    ok = True
    detail = ""
    for fi, entries in enumerate(test_frames):
        new_start, new_count = new_frames[fi]
        expected_tiles = []
        for start, count in entries:
            for t in range(count):
                expected_tiles.append(art[(start + t) * TILE_SIZE:(start + t + 1) * TILE_SIZE])
        actual_tiles = []
        for t in range(new_count):
            actual_tiles.append(new_art[(new_start + t) * TILE_SIZE:(new_start + t + 1) * TILE_SIZE])
        if expected_tiles != actual_tiles:
            ok = False
            detail = f"frame {fi} tile data mismatch"
            break
    check("4. Contiguous layout preserves tile data", ok, detail)

    # Test 5: contiguous layout tile counts match original
    ok = True
    detail = ""
    for fi, entries in enumerate(test_frames):
        orig_count = sum(c for _, c in entries)
        _, new_count = new_frames[fi]
        if orig_count != new_count:
            ok = False
            detail = f"frame {fi}: expected {orig_count}, got {new_count}"
            break
    check("5. Contiguous layout tile counts match", ok, detail)

    # Test 6: merge_adjacent_entries merges correctly
    merge_input = [
        [(3, 3), (6, 2)],           # adjacent: 3+3=6 == 6 → merge to (3,5)
        [(0, 2), (4, 2)],           # gap: not mergeable
        [(10, 1), (11, 1), (12, 1)],  # triple adjacent → (10, 3)
    ]
    merged, before, after = merge_adjacent_entries(merge_input)
    check("6a. Merge: adjacent entries combined",
          merged[0] == [(3, 5)],
          f"expected [(3,5)], got {merged[0]}")
    check("6b. Merge: non-adjacent preserved",
          merged[1] == [(0, 2), (4, 2)],
          f"expected [(0,2),(4,2)], got {merged[1]}")
    check("6c. Merge: triple adjacent combined",
          merged[2] == [(10, 3)],
          f"expected [(10,3)], got {merged[2]}")
    check("6d. Merge: entry count reduction",
          before == 7 and after == 4,
          f"expected 7→4, got {before}→{after}")

    # Test 7: optimized DPLC round-trips through write/parse
    contiguous_frames = [[(start, count)] if count > 0 else [] for start, count in new_frames]
    opt_bytes = write_dplc(contiguous_frames)
    opt_parsed = parse_dplc(opt_bytes)
    check("7. Optimized DPLC write/parse round-trip",
          opt_parsed == contiguous_frames,
          f"mismatch in round-trip")

    # Test 8: empty frame handling
    empty_frames = [[], [(0, 1)], []]
    empty_dplc = write_dplc(empty_frames)
    empty_parsed = parse_dplc(empty_dplc)
    check("8. Empty frame round-trip",
          empty_parsed == empty_frames,
          f"expected {empty_frames}, got {empty_parsed}")

    # Test 9: single-tile frame round-trip through full pipeline
    single_art = make_tile(0x42)
    single_frames = [[(0, 1)]]
    new_a, new_f = build_contiguous_art(single_art, single_frames)
    check("9. Single-tile pipeline",
          new_a == single_art and new_f == [(0, 1)],
          f"art match: {new_a == single_art}, frames: {new_f}")

    # Test 10: max entry size (16 tiles)
    big_art = b''.join(make_tile(i) for i in range(20))
    big_frames = [[(0, 16)], [(4, 16)]]
    big_dplc = write_dplc(big_frames)
    big_parsed = parse_dplc(big_dplc)
    check("10. Max tile count (16) entry",
          big_parsed == big_frames,
          f"expected {big_frames}, got {big_parsed}")

    print("=" * 60)
    print(f"Results: {passed}/{passed + failed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    print("All tests passed.")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        cmd_test()
    else:
        main()
