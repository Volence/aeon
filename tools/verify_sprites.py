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


# (dplc, art) PAIRS, named explicitly rather than discovered by globbing two
# directories and hoping the stems match.
#
# The old form globbed `data/dplc` — a path that has not existed since the
# engine/game restructure moved the tables to games/sonic4/data/dplc. The glob
# therefore matched nothing, the whole DPLC section was skipped, `all_ok` stayed
# True and test.sh printed "PASS: Sprite & DPLC verification" while verifying
# zero tables. Knuckles was never covered at all (there is no
# art/uncompressed/characters/knuckles.bin), and the one check that matters most
# — every DPLC tile index inside its art blob — was the check being skipped.
#
# SHIPPED pairs are exactly what the .emp modules embed(), so this list is
# checkable against them by grep. Note knuckles ships a RAW dplc while the other
# three ship optimized ones — precisely the asymmetry a stem-matching glob hides.
SHIPPED_PAIRS = [
    ('sonic',       'games/sonic4/data/dplc/optimized/sonic.bin',
                    'art/optimized/characters/sonic.bin'),
    ('tails',       'games/sonic4/data/dplc/optimized/tails.bin',
                    'art/optimized/characters/tails.bin'),
    ('tails_tail',  'games/sonic4/data/dplc/optimized/tails_tail.bin',
                    'art/optimized/characters/tails_tail.bin'),
    ('knuckles',    'games/sonic4/data/dplc/knuckles.bin',
                    'art/optimized/characters/knuckles.bin'),
    ('dust',        'games/sonic4/data/generated/dust/dplc_dust.bin',
                    'games/sonic4/data/generated/dust/art_dust.bin'),
]

# On disk and verifiable, but not embedded in the ROM today. Still checked — a
# broken pending asset should fail here, not on the day someone wires it up.
PENDING_PAIRS = [
    ('sonic_src',      'games/sonic4/data/dplc/sonic.bin',
                       'art/uncompressed/characters/sonic.bin'),
    ('tails_src',      'games/sonic4/data/dplc/tails.bin',
                       'art/uncompressed/characters/tails.bin'),
    ('tails_tail_src', 'games/sonic4/data/dplc/tails_tail.bin',
                       'art/uncompressed/characters/tails_tail.bin'),
    ('bubble_shield',    'games/sonic4/data/dplc/bubble_shield.bin',
                         'art/uncompressed/shields/bubble_shield.bin'),
    ('fire_shield',      'games/sonic4/data/dplc/fire_shield.bin',
                         'art/uncompressed/shields/fire_shield.bin'),
    ('insta_shield',     'games/sonic4/data/dplc/insta_shield.bin',
                         'art/uncompressed/shields/insta_shield.bin'),
    ('lightning_shield', 'games/sonic4/data/dplc/lightning_shield.bin',
                         'art/uncompressed/shields/lightning_shield.bin'),
    # wind shares the lightning art (same animation, recoloured)
    ('wind_shield',      'games/sonic4/data/dplc/wind_shield.bin',
                         'art/uncompressed/shields/lightning_shield.bin'),
]


def verify_pairs(base, pairs, heading):
    """Check each (dplc, art) pair. A missing file is a FAILURE, not a skip:
    a named gate whose input is absent is a red gate."""
    ok_all = True

    print("\n" + "=" * 70)
    print(heading)
    print("=" * 70)

    for name, dplc_rel, art_rel in pairs:
        dplc_path = base / dplc_rel
        art_path = base / art_rel

        missing = [p for p in (dplc_path, art_path) if not p.is_file()]
        if missing:
            print(f"\n  [FAIL] {name}")
            for p in missing:
                print(f"       missing input: {p.relative_to(base)}")
            ok_all = False
            continue

        art_ok, art_tiles, art_issues = check_art_file(art_path)
        if not art_ok:
            print(f"\n  [FAIL] {art_path.relative_to(base)}")
            for issue in art_issues:
                print(f"       {issue}")
            ok_all = False

        # art_tiles is the real bound — there is no 65536 escape hatch. The old
        # code substituted 65536 when it could not find the art, which disabled
        # the tile-index bounds check that is this tool's whole reason to exist.
        dplc_ok, frame_count, stats, issues = check_dplc_file(dplc_path, art_tiles)
        status = "OK" if dplc_ok else "FAIL"
        print(f"\n  [{status}] {name}: {dplc_path.relative_to(base)}")
        print(f"       art: {art_path.relative_to(base)} ({art_tiles} tiles)")

        if stats:
            print(f"       {stats['frame_count']} frames, "
                  f"{stats['avg_entries']:.1f} avg entries/frame (max {stats['max_entries']})")
            print(f"       {stats['avg_tiles']:.1f} avg tiles/frame (max {stats['max_tiles']}), "
                  f"highest tile index: {stats['max_tile_index']}")
            print(f"       Avg DMA per frame change: {stats['avg_dma_bytes']:.0f} bytes, "
                  f"max: {stats['max_dma_bytes']} bytes")
            print(f"       Art utilization: {stats['art_utilization']:.1f}% "
                  f"({stats['max_tile_index'] + 1}/{art_tiles} tiles referenced)")

        for issue in issues:
            prefix = "FAIL:" if "exceed" in issue or "out of bounds" in issue else "     "
            print(f"       {prefix} {issue}")

        if not dplc_ok:
            ok_all = False

    return ok_all


def main():
    base = Path(__file__).parent.parent

    art_dir = base / 'art' / 'uncompressed' / 'characters'
    shield_dir = base / 'art' / 'uncompressed' / 'shields'

    ART_ALIASES = {
        'wind_shield': 'lightning_shield',
    }

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

    if not verify_pairs(base, SHIPPED_PAIRS, "DPLC TABLE VERIFICATION — SHIPPED (embedded in the ROM)"):
        all_ok = False

    if not verify_pairs(base, PENDING_PAIRS, "DPLC TABLE VERIFICATION — PENDING (on disk, not yet embedded)"):
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
