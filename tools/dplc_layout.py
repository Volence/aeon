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


if __name__ == '__main__':
    main()
