#!/usr/bin/env python3
"""Convert Sonic 2 sprite mappings to S4 engine VDP-order format.

S2 piece format (8 bytes):
  byte  Y offset (signed)
  byte  size code (bits 3-2=width-1, bits 1-0=height-1)
  word  tile attributes (priority|palette|vflip|hflip|tile)
  word  padding (skipped by S2's DrawSprite)
  word  X offset (signed)

S4 piece format (8 bytes):
  word  Y offset (signed)
  byte  size code
  byte  padding (0)
  word  tile attributes
  word  X offset (signed)

Both formats use: word offset table, then per-frame word piece_count + pieces.
"""

import struct
import sys
from pathlib import Path


def convert_mappings(data):
    """Convert S2 mapping binary to S4 VDP-order format."""
    first_offset = struct.unpack_from('>H', data, 0)[0]
    frame_count = first_offset // 2

    offsets = []
    for i in range(frame_count):
        offsets.append(struct.unpack_from('>H', data, i * 2)[0])

    s4_frames = []
    for fi in range(frame_count):
        off = offsets[fi]
        piece_count = struct.unpack_from('>H', data, off)[0]

        pieces = []
        pos = off + 2
        for p in range(piece_count):
            y_byte = struct.unpack_from('>b', data, pos)[0]
            size = data[pos + 1] & 0x0F
            tile_attrs = struct.unpack_from('>H', data, pos + 2)[0]
            x_word = struct.unpack_from('>h', data, pos + 6)[0]

            piece = struct.pack('>h', y_byte)        # Y as signed word
            piece += struct.pack('BB', size, 0)       # size + pad
            piece += struct.pack('>H', tile_attrs)    # tile attrs
            piece += struct.pack('>h', x_word)        # X as signed word

            pieces.append(piece)
            pos += 8

        s4_frames.append(pieces)

    pointer_table_size = frame_count * 2
    frame_data_parts = []
    new_offsets = []

    data_offset = pointer_table_size
    for pieces in s4_frames:
        new_offsets.append(data_offset)
        frame_bytes = struct.pack('>H', len(pieces))
        for piece in pieces:
            frame_bytes += piece
        frame_data_parts.append(frame_bytes)
        data_offset += len(frame_bytes)

    output = bytearray()
    for off in new_offsets:
        output.extend(struct.pack('>H', off))
    for part in frame_data_parts:
        output.extend(part)

    return bytes(output), frame_count


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.bin [output.bin]")
        print("Converts S2 sprite mappings to S4 VDP-order format.")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else in_path.with_suffix('.s4.bin')

    data = in_path.read_bytes()
    result, frame_count = convert_mappings(data)

    out_path.write_bytes(result)
    print(f"Converted {frame_count} frames: {len(data)} → {len(result)} bytes")
    print(f"Written: {out_path}")

    # Verify a few frames
    for fi in [1, 2, 3]:
        off = struct.unpack_from('>H', result, fi * 2)[0]
        pc = struct.unpack_from('>H', result, off)[0]
        pos = off + 2
        print(f"\n  Frame {fi}: {pc} pieces")
        for p in range(pc):
            y = struct.unpack_from('>h', result, pos)[0]
            size = result[pos + 2]
            tile = struct.unpack_from('>H', result, pos + 4)[0]
            x = struct.unpack_from('>h', result, pos + 6)[0]
            w = ((size >> 2) & 3) + 1
            h = (size & 3) + 1
            print(f"    [{p}] Y={y:+4d} {w}x{h} tile={tile & 0x7FF:3d} X={x:+4d}")
            pos += 8


if __name__ == '__main__':
    main()
