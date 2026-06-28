#!/usr/bin/env python3
"""Import Sonic & Knuckles' collision shape set as the aeon's collision tables.

Reads S&K's heightmaps + rotated heightmaps + angles from the skdisasm checkout and
writes the engine's fixed 256-slot collision vocabulary to TWO places:

  data/collision/base/{heightmaps,heightmaps_rot,angles,solidity}.bin
      The BASE BANK — the stable S&K shape vocabulary Aurora's palette shows and
      the bake (ojz_strip_gen) draws flipped/solidity variants from. Authoritative.

  data/collision/{heightmaps,heightmaps_rot,angles,solidity}.bin
      A default copy so the ROM tables exist even without a generate pass.
      ojz_strip_gen.generate() OVERWRITES these with the sparse INTERNED runtime
      set (only the shape/flip/solidity combos actually painted reach the ROM).

Every non-air base shape gets solidity 'all' (3); the editor picks per-cell
solidity (jump-through etc.) and the bake resolves it. Index 0 (and any all-zero
slot) stays air (solidity 0).

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


def _write_tables(out_dir, hm, hr, an, sol):
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "heightmaps.bin"), "wb").write(hm)
    open(os.path.join(out_dir, "heightmaps_rot.bin"), "wb").write(hr)
    open(os.path.join(out_dir, "angles.bin"), "wb").write(an)
    open(os.path.join(out_dir, "solidity.bin"), "wb").write(bytes(sol))


def build():
    hm = _read("Height Maps.bin", SHAPES * ROW)
    hr = _read("Height Maps Rotated.bin", SHAPES * ROW)
    an = _read("angles.bin", SHAPES)
    sol = bytearray(SHAPES)
    for i in range(SHAPES):
        shape = hm[i * ROW:(i + 1) * ROW]
        sol[i] = 0 if (i == 0 or not any(shape)) else SOLID_ALL
    base_dir = os.path.join(OUT, "base")
    _write_tables(base_dir, hm, hr, an, sol)     # authoritative base bank (Aurora palette + bake source)
    _write_tables(OUT, hm, hr, an, sol)          # default runtime tables (overwritten by generate())
    n = sum(1 for i in range(SHAPES) if any(hm[i * ROW:(i + 1) * ROW]))
    print(f"Imported {n} S&K collision shapes -> {base_dir} (base bank) + {OUT} (default; all solidity 'all')")


if __name__ == "__main__":
    build()
