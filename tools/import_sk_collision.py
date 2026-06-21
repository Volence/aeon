#!/usr/bin/env python3
"""Import Sonic & Knuckles' collision shape set as the s4_engine's collision tables.

Reads S&K's heightmaps + rotated heightmaps + angles from the skdisasm checkout and
writes data/collision/{heightmaps,heightmaps_rot,angles,solidity}.bin — the engine's
fixed 256-slot collision vocabulary. Every non-air shape gets solidity 'all' (3);
classic Sonic heightmaps carry no solidity, so per-shape jump-through variants are a
future feature. Index 0 (and any all-zero slot) stays air (solidity 0).

    python3 tools/import_sk_collision.py
"""
import os

HERE = os.path.dirname(__file__)
SK = os.path.normpath(os.path.join(HERE, "..", "..", "skdisasm", "Levels", "Misc"))
OUT = os.path.normpath(os.path.join(HERE, "..", "data", "collision"))
SHAPES, ROW, SOLID_ALL = 256, 16, 3   # s4 solidity: 0 none, 1 top, 2 sides-bottom, 3 all


def _read(name, expect):
    d = open(os.path.join(SK, name), "rb").read()
    assert len(d) == expect, f"{name}: {len(d)}B, expected {expect}"
    return d


def build():
    hm = _read("Height Maps.bin", SHAPES * ROW)
    hr = _read("Height Maps Rotated.bin", SHAPES * ROW)
    an = _read("angles.bin", SHAPES)
    sol = bytearray(SHAPES)
    for i in range(SHAPES):
        shape = hm[i * ROW:(i + 1) * ROW]
        sol[i] = 0 if (i == 0 or not any(shape)) else SOLID_ALL
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "heightmaps.bin"), "wb").write(hm)
    open(os.path.join(OUT, "heightmaps_rot.bin"), "wb").write(hr)
    open(os.path.join(OUT, "angles.bin"), "wb").write(an)
    open(os.path.join(OUT, "solidity.bin"), "wb").write(bytes(sol))
    n = sum(1 for i in range(SHAPES) if any(hm[i * ROW:(i + 1) * ROW]))
    print(f"Imported {n} S&K collision shapes -> {OUT} (all solidity 'all')")


if __name__ == "__main__":
    build()
