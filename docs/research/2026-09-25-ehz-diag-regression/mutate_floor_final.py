#!/usr/bin/env python3
"""mutate_floor_final.py <in.bin> <out.bin>: the red control for the LANDED curve loop.

In the hoist, the landed sequence `swap d2 / clr.w d2 / add.w d4,d2 / subq.w #1,d2 /
divu.w d4,d2` is `4842 4242 D444 5342 84C4`. Replacing the ceil adjust (`D444 5342`) with two
NOPs makes the fraction floor(rem*65536/span), which is NOT exact. The pattern must occur exactly
once in the image. The .lst is copied alongside (same addresses; only 4 bytes change)."""
import shutil
import sys
import zlib

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, "rb").read())
pat = bytes.fromhex("48424242D444534284C4")
i = d.find(pat)
assert i >= 0 and d.count(pat) == 1, "pattern not unique"
d[i + 4:i + 8] = bytes.fromhex("4E714E71")
open(dst, "wb").write(d)
shutil.copy(src[:-4] + ".lst", dst[:-4] + ".lst")
print(f"patched at {i:#x}; {dst.split('/')[-1]} crc={zlib.crc32(d):08x} size={len(d)}")
