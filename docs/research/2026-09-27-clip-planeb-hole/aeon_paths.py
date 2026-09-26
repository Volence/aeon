#!/usr/bin/env python3
"""RESEARCH (not a gate): the clip act's OWN converted collision planes (clip_manifest.
collision_grids, the words the clip bake writes into the ROM), per 8-px column, printed the way
s2_paths.py prints the donor's so the two can be diffed line for line.

    python3 docs/research/2026-09-27-clip-planeb-hole/aeon_paths.py 1280 1760 [ymax]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools"))
import clip_manifest as CM  # noqa: E402
import collision_pipeline as CP  # noqa: E402

MAN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "../../../games/sonic4/data/clips/s2_ehz_cpz/clips.json")
x0, x1 = int(sys.argv[1]), int(sys.argv[2])
ymax = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
act = CM.load(MAN)
planes = CM.collision_grids(act)
hm, _ = CM._bank(CM.collision_banks(act))
n = int(os.environ.get("NCELLS", "5"))


def cellinfo(x, y, p):
    w = int(planes[p][y // 16 * 2, x // 8])
    sol = (w >> CP.PLANE_SOL_SHIFT) & 3
    shape = w & CP.BLOCK_ID_MASK
    if not sol or not shape:
        return None
    h = hm[shape * CP.PROFILE_LEN:(shape + 1) * CP.PROFILE_LEN]
    if w & CP.CHUNK_XFLIP_BIT:
        h = CP.flip_profile_x(h)
    hv = h[x % 16]
    hv = hv - 256 if hv > 127 else hv
    if w & CP.CHUNK_YFLIP_BIT:
        hv = -hv
    return f"{y}:{'T' if sol & CP.SOL_TOP else ''}{'W' if sol & ~CP.SOL_TOP & 3 else ''}{hv}"


def floor(x, p):
    for y in range(0, ymax, 16):
        w = int(planes[p][y // 16 * 2, x // 8])
        h = CM._word_heights(w, hm)
        if h is not None:
            hv = h[x % 16]
            hv = hv - 256 if hv > 127 else hv
            if hv > 0:
                return y + 16 - hv
    return None


for x in range(x0, x1, 8):
    out = []
    for p in (0, 1):
        cells = [c for c in (cellinfo(x, y, p) for y in range(0, ymax, 16)) if c]
        out.append(f"floor {floor(x, p)!s:>4}  " + " ".join(cells[:n]))
    print(f"{x:5d} | A {out[0]:<52} | B {out[1]}")
