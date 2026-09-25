#!/usr/bin/env python3
"""mutate_floor.py: red control for the curve prototype. In runs/P.bin, replace the hoist's
ceil adjust (add.w d4,d2 ; subq.w #1,d2 = D444 5342) with two NOPs, so the fraction becomes
floor(rem*65536/span) - which the exhaustive check says is NOT exact. Writes runs/Pfloor.bin."""
import shutil, zlib
d = bytearray(open("runs/P.bin", "rb").read())
pat = bytes.fromhex("4842 4242 D444 5342 84C4".replace(" ", ""))
i = d.find(pat)
assert i >= 0 and d.count(pat) == 1, "pattern not unique"
d[i + 4:i + 8] = bytes.fromhex("4E714E71")
open("runs/Pfloor.bin", "wb").write(d)
shutil.copy("runs/P.lst", "runs/Pfloor.lst")
print(f"patched at {i:#x}; Pfloor crc={zlib.crc32(d):08x} size={len(d)}")
