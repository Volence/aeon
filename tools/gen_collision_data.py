#!/usr/bin/env python3
"""Generate stub collision data: height maps and angle table.

Usage: python3 tools/gen_collision_data.py [output_dir]
Default output_dir: data/collision
"""

import sys
import os


def generate_heightmaps(path: str) -> None:
    """256 profiles × 16 bytes each = 4096 bytes.
    Type 0 = air (all $00). Type 1 = flat solid (all $10 = height 16).
    Types 2-255 = placeholder (all $00).
    """
    data = bytearray(256 * 16)
    for i in range(16):
        data[1 * 16 + i] = 0x10
    with open(path, 'wb') as f:
        f.write(data)


def generate_angles(path: str) -> None:
    """256 bytes — one angle per collision type. All flat ($00) for stub."""
    data = bytearray(256)
    with open(path, 'wb') as f:
        f.write(data)


if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/collision'
    os.makedirs(out_dir, exist_ok=True)
    generate_heightmaps(os.path.join(out_dir, 'heightmaps.bin'))
    generate_heightmaps(os.path.join(out_dir, 'heightmaps_rot.bin'))
    generate_angles(os.path.join(out_dir, 'angles.bin'))
    print(f"Generated collision data in {out_dir}")
