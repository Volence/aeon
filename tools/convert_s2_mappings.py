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

S4 frame format:
  +0  dc.b x_min, x_max, y_min, y_max   ; signed bbox extents relative to origin
  +4  dc.w piece_count
  +6  pieces (8 bytes each)

x_max/y_max are the far edge (x_off + width_px, y_off + height_px).
Bbox extents are FLIP-INVARIANT: after computing raw extents the generator
symmetrizes them (union of unflipped and flipped extents).  Exact for symmetric
frames; conservative by the asymmetry amount for asymmetric frames — always
correct under any RF_XFLIP/RF_YFLIP combination, still far tighter than the old
±32 margin.  See _compute_bbox for details.
The generator hard-fails if any extent exceeds the signed byte range [-128,127].
"""

import struct
import sys
from pathlib import Path


def _cell_px(size_byte):
    """Return (width_px, height_px) for a VDP size code byte."""
    w = (((size_byte >> 2) & 3) + 1) * 8
    h = ((size_byte & 3) + 1) * 8
    return w, h


def _compute_bbox(pieces, frame_index=None):
    """Compute flip-invariant (x_min, x_max, y_min, y_max) over all pieces.

    Each piece is (y, size, tile_attrs, x).
    x_max / y_max are far edges (origin + dimension).

    After computing raw extents the result is symmetrized so the stored bbox
    covers the union of the unflipped and flipped extents:
        x_min, x_max = min(x_min, -x_max), max(x_max, -x_min)
        y_min, y_max = min(y_min, -y_max), max(y_max, -y_min)
    This means Draw_Sprite's unflipped bbox test is always correct regardless of
    the RF_XFLIP / RF_YFLIP state used by Emit_ObjectPieces at render time.
    Exact for symmetric frames; conservative by the asymmetry amount otherwise.

    Returns (0,0,0,0) for empty frames.
    Raises ValueError (naming the offending frame) if any extent exceeds the
    signed byte range [-128,127] after symmetrization.
    """
    if not pieces:
        return 0, 0, 0, 0

    x_min = 127
    x_max = -128
    y_min = 127
    y_max = -128

    for y, size, _tile, x in pieces:
        w, h = _cell_px(size)
        if x < x_min:
            x_min = x
        if x + w > x_max:
            x_max = x + w
        if y < y_min:
            y_min = y
        if y + h > y_max:
            y_max = y + h

    # Symmetrize for flip-invariance: stored box is union of flipped/unflipped.
    x_min, x_max = min(x_min, -x_max), max(x_max, -x_min)
    y_min, y_max = min(y_min, -y_max), max(y_max, -y_min)

    frame_tag = f" (frame {frame_index})" if frame_index is not None else ""
    for name, val in (('x_min', x_min), ('x_max', x_max),
                      ('y_min', y_min), ('y_max', y_max)):
        if val < -128 or val > 127:
            raise ValueError(
                f"Bbox {name}={val}{frame_tag} exceeds signed byte range [-128,127]; "
                "split the frame or shrink piece extents."
            )
    return x_min, x_max, y_min, y_max


def convert_mappings(data):
    """Convert S2 mapping binary to S4 VDP-order format with bbox headers."""
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
            pieces.append((y_byte, size, tile_attrs, x_word))
            pos += 8

        s4_frames.append(pieces)

    pointer_table_size = frame_count * 2
    frame_data_parts = []
    new_offsets = []

    data_offset = pointer_table_size
    for fi, pieces in enumerate(s4_frames):
        new_offsets.append(data_offset)

        x_min, x_max, y_min, y_max = _compute_bbox(pieces, fi)

        # Frame header: 4 signed bbox bytes + piece count word
        frame_bytes = struct.pack('bbbb', x_min, x_max, y_min, y_max)
        frame_bytes += struct.pack('>H', len(pieces))

        for y, size, tile_attrs, x in pieces:
            piece = struct.pack('>h', y)             # Y as signed word
            piece += struct.pack('BB', size, 0)       # size + pad
            piece += struct.pack('>H', tile_attrs)    # tile attrs
            piece += struct.pack('>h', x)             # X as signed word
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

    # Verify a few frames (now with bbox header at +0, piece count at +4)
    for fi in [1, 2, 3]:
        off = struct.unpack_from('>H', result, fi * 2)[0]
        x_min, x_max, y_min, y_max = struct.unpack_from('bbbb', result, off)
        pc = struct.unpack_from('>H', result, off + 4)[0]
        pos = off + 6
        print(f"\n  Frame {fi}: bbox=({x_min},{x_max},{y_min},{y_max}) {pc} pieces")
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
