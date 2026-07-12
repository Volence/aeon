#!/usr/bin/env python3
"""Compose aeon's 4-frame 2x2 ring art from the decompressed S3K Ring.bin.

S3K spin (Ani_Ring frames 0,1,2,3):
  F0 full ring  = tiles 0-3 (2x2)
  F1 narrower   = tiles 4-7 (2x2)
  F2 thin edge  = tiles 8-9 (1x2, 8px wide, centred X-4) -> centre in a 2x2
  F3 narrower'  = tiles 4-7 H-FLIPPED (2x2)
Output: 16 tiles = 4 frames x 4 tiles, VDP 2x2 column-major order (TL,BL,TR,BR),
so aeon's DrawRings can pick a frame with base_tile + frame*4.
Input: the DONOR ring art (sonic_hack/art/nemesis/Ring.bin), decompressed via
nemdec/clownnemesis — already coloured for act-palette line-1 indices
{5=outline, 6=white highlight, C=bright gold, D=dark gold}, matching aeon's
OJZ_Palette line 1. So NO palette remap: identity (rings are drawn on CRAM
line 1 via vram_art(...,1,1); see DrawRings). (Do NOT feed skdisasm's Ring.bin
here — its raw indices {1,5,6,F} would need a lossy remap onto the wrong line.)
"""
import sys

REMAP = {}  # identity — donor art indices already match OJZ_Palette line 1

def load_tiles(path):
    d = open(path, 'rb').read()
    tiles = []
    for t in range(len(d)//32):
        px = [[0]*8 for _ in range(8)]           # px[row][col]
        for row in range(8):
            for bcol in range(4):
                b = d[t*32 + row*4 + bcol]
                px[row][bcol*2]   = REMAP.get(b>>4,  b>>4)
                px[row][bcol*2+1] = REMAP.get(b&0xF, b&0xF)
        tiles.append(px)
    return tiles

def emit(px):
    out = bytearray()
    for row in range(8):
        for bcol in range(4):
            out.append((px[row][bcol*2] << 4) | px[row][bcol*2+1])
    return bytes(out)

def hflip(px):
    return [list(reversed(r)) for r in px]

def blank():
    return [[0]*8 for _ in range(8)]

def frame_thin(t_top, t_bot):
    """Place the 8px-wide thin sprite (t_top over t_bot) centred in a 16x16
    frame (cols 4..11), then slice into TL,BL,TR,BR (col-major)."""
    canvas = [[0]*16 for _ in range(16)]
    for row in range(8):
        for col in range(8):
            canvas[row][4+col]   = t_top[row][col]   # top half, rows 0-7
            canvas[8+row][4+col] = t_bot[row][col]   # bottom half, rows 8-15
    def slc(r0, c0):
        return [canvas[r0+r][c0:c0+8] for r in range(8)]
    TL = slc(0,0); BL = slc(8,0); TR = slc(0,8); BR = slc(8,8)
    return [TL, BL, TR, BR]

def main():
    t = load_tiles(sys.argv[1])
    assert len(t) >= 14, f"expected >=14 tiles, got {len(t)}"
    frames = []
    frames.append([t[0], t[1], t[2], t[3]])                          # F0 full
    frames.append([t[4], t[5], t[6], t[7]])                          # F1 narrower
    frames.append(frame_thin(t[8], t[9]))                            # F2 thin, centred
    frames.append([hflip(t[6]), hflip(t[7]), hflip(t[4]), hflip(t[5])])  # F3 F1 h-flipped
    out = bytearray()
    for f in frames:
        for tile in f:
            out += emit(tile)
    open(sys.argv[2], 'wb').write(out)
    print(f"wrote {len(out)} bytes = {len(out)//32} tiles to {sys.argv[2]}")
    # ASCII preview: reconstruct each 16x16 frame (col-major TL,BL,TR,BR)
    GLYPH = {0:'.', 5:'o', 6:'*', 0xC:'#', 0xD:'+'}  # outline / white / bright gold / dark gold
    for fi, f in enumerate(frames):
        TL,BL,TR,BR = f
        print(f"\n-- frame {fi} --")
        top = [TL, TR]; bot = [BL, BR]
        for band,(L,R) in enumerate([(TL,TR),(BL,BR)]):
            for row in range(8):
                line = ''.join(GLYPH.get(v,'?') for v in L[row]) + ''.join(GLYPH.get(v,'?') for v in R[row])
                print(line)

main()
