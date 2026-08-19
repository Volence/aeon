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
import os, sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ojz_common import skdisasm_root  # noqa: E402

# skdisasm is an out-of-repo DONOR only this manual re-bake reads (the build
# consumes the committed collision tables). Override with AEON_SKDISASM_DIR
# (pointing at the skdisasm checkout root); absence fails loudly below.
# The resolution lives in ojz_common so this tool, ojz_strip_gen.preflight() (which
# must refuse a run BEFORE this file's destructive write — tools lens sweep D1) and
# tools/donor_provenance.py all name the same checkout.
_SK_ROOT = skdisasm_root()
SK = os.path.join(_SK_ROOT, "Levels", "Misc")
if not os.path.isdir(SK):
    raise SystemExit(
        f"import_sk_collision: skdisasm donor not found at {SK}. This is a MANUAL "
        f"re-bake tool (tools/regenerate-level.sh); set AEON_SKDISASM_DIR to your "
        f"skdisasm checkout. The build does NOT run this — it uses the committed "
        f"collision tables under games/sonic4/data/collision/.")
OUT = os.path.normpath(os.path.join(HERE, "..", "games", "sonic4", "data", "collision"))
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


def build(out=None):
    """Import the S&K collision tables.

    `out` defaults to the in-repo collision dir. It is a PARAMETER because the
    runtime tables this writes are only DEFAULTS — gen_collision_data.generate()
    overwrites them with the per-section bake, and the committed bytes are the
    baked ones. So any caller that just wants to CHECK the importer (the test)
    must redirect it, or it silently reverts the bake and leaves four tracked
    build inputs dirty. That is exactly what test_import_sk_collision.py used to
    do; a dirty tree there makes the ROM diverge from the frozen goldens.
    """
    out = OUT if out is None else out
    hm = _read("Height Maps.bin", SHAPES * ROW)
    hr = _read("Height Maps Rotated.bin", SHAPES * ROW)
    an = _read("angles.bin", SHAPES)
    sol = bytearray(SHAPES)
    for i in range(SHAPES):
        shape = hm[i * ROW:(i + 1) * ROW]
        sol[i] = 0 if (i == 0 or not any(shape)) else SOLID_ALL
    base_dir = os.path.join(out, "base")
    _write_tables(base_dir, hm, hr, an, sol)     # authoritative base bank (Aurora palette + bake source)
    _write_tables(out, hm, hr, an, sol)          # default runtime tables (overwritten by generate())
    n = sum(1 for i in range(SHAPES) if any(hm[i * ROW:(i + 1) * ROW]))
    print(f"Imported {n} S&K collision shapes -> {base_dir} (base bank) + {out} (default; all solidity 'all')")


if __name__ == "__main__":
    # Optional output dir, mirroring gen_collision_data.py's argv[1] convention.
    build(sys.argv[1] if len(sys.argv) > 1 else None)
