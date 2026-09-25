#!/usr/bin/env python3
"""patch_ehz.py <runs/X.bin> : write X{nc,nr,nb,np}.bin + .lst beside it.
EHZ scroll record = the .lst label OJZ_Clip_Parallax_0 (30-byte parallax_config header, then
7 band records of 32 bytes: band_entry 10, band_curve 10, band_drift 4, band_remap 8).
  nc: band 6 (plane line 144, the curve) bc_flags 02 -> 00  (curve off: flat camX/8)
  nr: band 2 (plane line 80, the ripple) band_deform_shift_b 00 -> 0F  (no deform)
  nb: both
  np: OJZ_Clip_Preset_0's parallax pointer -> 0 (EHZ scrolls with the act default, pre-B-2)
Every patched byte is asserted to hold its expected old value first."""
import re, sys, shutil, zlib
src = sys.argv[1]; stem = src[:-4]
d = bytearray(open(src, "rb").read())
lst = open(stem + ".lst", errors="replace").read()
par = int(re.search(r"OJZ_Clip_Parallax_0 : ([0-9A-F]+)", lst).group(1), 16)
pre = int(re.search(r"OJZ_Clip_Preset_0 : ([0-9A-F]+)", lst).group(1), 16)
base = par + 30
curve = base + 6 * 32 + 10 + 2
rip = base + 2 * 32 + 8
assert d[base + 6 * 32:base + 6 * 32 + 2] == b"\x00\x90" and d[curve] == 0x02
assert d[base + 2 * 32:base + 2 * 32 + 2] == b"\x00\x50" and d[rip] == 0x00
ref = par.to_bytes(4, "big")
assert d[pre + 4:pre + 8] == ref and bytes(d).count(ref) == 1
for tag, mods in (("nc", [(curve, b"\x00")]), ("nr", [(rip, b"\x0f")]),
                  ("nb", [(curve, b"\x00"), (rip, b"\x0f")]), ("np", [(pre + 4, b"\0\0\0\0")])):
    e = bytearray(d)
    for a, v in mods:
        e[a:a + len(v)] = v
    open(f"{stem}{tag}.bin", "wb").write(e)
    shutil.copy(stem + ".lst", f"{stem}{tag}.lst")
    print(f"{stem}{tag}.bin crc={zlib.crc32(e):08x} size={len(e)} "
          + " ".join(f"{a:#x}<-{v.hex()}" for a, v in mods))
