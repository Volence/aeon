#!/usr/bin/env python3
"""Verify extracted sprite art and DPLC tables for the S4 engine.

Checks:
- Art file sizes are multiples of 32 (one 8x8 tile = 32 bytes)
- DPLC table structure is valid (entry counts, tile indices within art bounds)
- No all-zero art files (placeholder detection)
- Reports tile counts, frame counts, DMA statistics
"""

import struct
import sys
from pathlib import Path

TILE_SIZE = 32

def check_art_file(path):
    """Validate an uncompressed art file. Returns (ok, tile_count, issues)."""
    data = path.read_bytes()
    size = len(data)
    issues = []

    if size == 0:
        return False, 0, ["Empty file"]

    if size % TILE_SIZE != 0:
        issues.append(f"Size {size} not a multiple of {TILE_SIZE}")

    tile_count = size // TILE_SIZE

    if all(b == 0 for b in data):
        issues.append("All zeros — placeholder file, not real art")

    nonzero_tiles = 0
    for i in range(tile_count):
        tile = data[i * TILE_SIZE:(i + 1) * TILE_SIZE]
        if any(b != 0 for b in tile):
            nonzero_tiles += 1

    blank_pct = ((tile_count - nonzero_tiles) / tile_count * 100) if tile_count else 0

    return len(issues) == 0, tile_count, issues + [
        f"{tile_count} tiles ({size:,} bytes), {nonzero_tiles} non-blank ({blank_pct:.1f}% blank)"
    ]


def check_dplc_file(path, art_tile_count):
    """Validate a DPLC table in S2/S3K format. Returns (ok, frame_count, stats, issues).

    S2 DPLC format:
      Pointer table: word offsets from start of file (indexed by frame * 2)
      Frame count = first_offset / 2 (pointer table ends where frame 0 data starts)
      Each frame: word entry_count, then entry_count words
      Entry word: bits 15-12 = tile_count-1, bits 11-0 = tile_start_index
    """
    data = path.read_bytes()
    size = len(data)
    issues = []

    if size < 2:
        return False, 0, {}, ["File too small for DPLC data"]

    first_offset = struct.unpack_from('>H', data, 0)[0]
    if first_offset == 0 or first_offset % 2 != 0:
        issues.append(f"Invalid first offset: 0x{first_offset:04X}")
        return False, 0, {}, issues

    frame_count = first_offset // 2
    if first_offset > size:
        issues.append(f"First offset 0x{first_offset:04X} exceeds file size {size}")
        return False, frame_count, {}, issues

    offsets = []
    for i in range(frame_count):
        off = struct.unpack_from('>H', data, i * 2)[0]
        offsets.append(off)

    total_entries = 0
    max_tile_end = 0
    total_tiles_per_frame = []
    entries_per_frame = []

    for frame_idx, off in enumerate(offsets):
        if off + 2 > size:
            issues.append(f"Frame {frame_idx}: offset 0x{off:04X} out of bounds")
            continue

        entry_count = struct.unpack_from('>H', data, off)[0]
        pos = off + 2

        frame_tiles = 0
        for e in range(entry_count):
            if pos + 2 > size:
                issues.append(f"Frame {frame_idx} entry {e}: read past end of file")
                break
            word = struct.unpack_from('>H', data, pos)[0]
            pos += 2

            tile_count_minus1 = (word >> 12) & 0xF
            tile_start = word & 0xFFF
            tile_count = tile_count_minus1 + 1

            tile_end = tile_start + tile_count
            if tile_end > art_tile_count:
                issues.append(
                    f"Frame {frame_idx} entry {e}: tiles {tile_start}-{tile_end - 1} "
                    f"exceed art bounds ({art_tile_count} tiles)"
                )

            max_tile_end = max(max_tile_end, tile_end)
            frame_tiles += tile_count

        total_entries += entry_count
        total_tiles_per_frame.append(frame_tiles)
        entries_per_frame.append(entry_count)

    stats = {
        'frame_count': frame_count,
        'total_entries': total_entries,
        'avg_entries': total_entries / frame_count if frame_count else 0,
        'max_entries': max(entries_per_frame) if entries_per_frame else 0,
        'avg_tiles': sum(total_tiles_per_frame) / len(total_tiles_per_frame) if total_tiles_per_frame else 0,
        'max_tiles': max(total_tiles_per_frame) if total_tiles_per_frame else 0,
        'max_tile_index': max_tile_end - 1 if max_tile_end > 0 else 0,
        'art_utilization': max_tile_end / art_tile_count * 100 if art_tile_count else 0,
        'avg_dma_bytes': sum(total_tiles_per_frame) / len(total_tiles_per_frame) * TILE_SIZE if total_tiles_per_frame else 0,
        'max_dma_bytes': max(total_tiles_per_frame) * TILE_SIZE if total_tiles_per_frame else 0,
    }

    return len(issues) == 0, frame_count, stats, issues


def main():
    base = Path(__file__).parent.parent

    art_dir = base / 'art' / 'uncompressed' / 'characters'
    shield_dir = base / 'art' / 'uncompressed' / 'shields'
    dplc_dir = base / 'data' / 'dplc'

    all_ok = True

    print("=" * 70)
    print("SPRITE ART VERIFICATION")
    print("=" * 70)

    art_files = {}
    for d in [art_dir, shield_dir]:
        if d.exists():
            for f in sorted(d.glob('*.bin')):
                ok, tile_count, issues = check_art_file(f)
                name = f.stem
                art_files[name] = tile_count
                status = "OK" if ok else "FAIL"
                print(f"\n  [{status}] {f.relative_to(base)}")
                for issue in issues:
                    print(f"       {issue}")
                if not ok:
                    all_ok = False

    print("\n" + "=" * 70)
    print("DPLC TABLE VERIFICATION")
    print("=" * 70)

    if dplc_dir.exists():
        for f in sorted(dplc_dir.glob('*.bin')):
            name = f.stem
            art_count = art_files.get(name, 0)

            if art_count == 0:
                print(f"\n  [WARN] {f.relative_to(base)}")
                print(f"       No matching art file for '{name}' — validating structure only")
                art_count = 65536

            ok, frame_count, stats, issues = check_dplc_file(f, art_count)
            status = "OK" if ok else "FAIL"
            print(f"\n  [{status}] {f.relative_to(base)}")

            if stats:
                print(f"       {stats['frame_count']} frames, "
                      f"{stats['avg_entries']:.1f} avg entries/frame (max {stats['max_entries']})")
                print(f"       {stats['avg_tiles']:.1f} avg tiles/frame (max {stats['max_tiles']}), "
                      f"highest tile index: {stats['max_tile_index']}")
                print(f"       Avg DMA per frame change: {stats['avg_dma_bytes']:.0f} bytes, "
                      f"max: {stats['max_dma_bytes']} bytes")
                if art_count < 65536:
                    print(f"       Art utilization: {stats['art_utilization']:.1f}% "
                          f"({stats['max_tile_index'] + 1}/{art_count} tiles referenced)")

            for issue in issues:
                prefix = "FAIL:" if "exceed" in issue or "out of bounds" in issue else "     "
                print(f"       {prefix} {issue}")

            if not ok:
                all_ok = False

    print("\n" + "=" * 70)
    if all_ok:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED — see above")
    print("=" * 70)

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
