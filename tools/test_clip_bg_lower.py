"""tools/clip_bg_lower.py — a Sonic 2 zone's own background, lowered for a clip act.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`). Nothing
here reads a build artifact. Rows that read the Sonic 2 donor SKIP SAYING SO when the donor
checkout cannot be resolved.

WHAT IS PINNED, every expectation read from the DONOR or from the lowering's own contract,
never from a measured count:
  * FIDELITY: every cell of the lowered plane, decoded back through its word (tile, line,
    flip, priority), is the donor's own cell at the crop position, pixel for pixel — so the
    flip-aware dedupe, the native palette bits and the crop cannot drift silently;
  * EMERALD HILL'S wrap is the donor's own join (its period is exactly the plane), so its
    invented-seam cost is 0;
  * the refusals, on synthetic donors: over the static tile budget, and an opaque cell that
    would lower to the transparent word $0000.
"""

import os
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_bg_lower as L                   # noqa: E402
import s2_donor as S                        # noqa: E402
from suite_paths import SuitePathError      # noqa: E402
from vram_map import BG_STATIC_TILE_BUDGET  # noqa: E402


def _need():
    try:
        return S.donor_root(S.S2_FINAL)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {S.S2_FINAL} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")


@pytest.mark.parametrize("zone", ["EHZ", "CPZ"])
def test_every_lowered_cell_is_the_donors_own_cell(zone):
    _need()
    words, tiles, info = L.lower(S.S2_FINAL, zone)
    bg, ct, art = L._load(S.S2_FINAL, zone)
    tpc = ct.shape[1]
    period = info["period_cells"] // tpc
    start = info["crop_start_chunk"]
    assert len(words) == L.PLANE_COLS * L.PLANE_ROWS
    for r in range(L.PLANE_ROWS):
        for c in range(L.PLANE_COLS):
            gc = start * tpc + c
            chunk = int(bg[r // tpc, (gc // tpc) % period])
            dw = int(ct[chunk, r % tpc, gc % tpc])
            t = dw & 0x7FF
            want = L._flip(L._unpack(art[t * 32:(t + 1) * 32]), dw)
            w = words[r * L.PLANE_COLS + c]
            if w == 0:
                assert not any(v for row in want for v in row), (
                    f"{zone} cell ({c}, {r}) lowered to the transparent word but the donor "
                    f"draws opaque pixels there")
                continue
            got = L._flip(L._unpack(tiles[w & 0x7FF]), w)
            assert got == want, f"{zone} cell ({c}, {r}): pixels differ from the donor's"
            assert (w >> 13) & 3 == (dw >> 13) & 3, f"{zone} cell ({c}, {r}): palette line"
            assert w & L.PRIO == dw & L.PRIO, f"{zone} cell ({c}, {r}): priority bit"
    assert len(tiles) == info["tiles"] <= BG_STATIC_TILE_BUDGET


def test_emerald_hills_wrap_is_the_donors_own_join():
    """EHZ repeats every 4 chunks = 64 cells = exactly one plane, so wrapping the plane IS
    the donor's next column and no join is invented. DERIVED from the donor's own period."""
    _need()
    _w, _t, info = L.lower(S.S2_FINAL, "EHZ")
    assert info["period_cells"] == L.PLANE_COLS
    assert info["seam_cost_pixels"] == 0


def _tile(i):
    """A 4bpp tile that is DISTINCT from every other _tile(j) under all four flips: a 15
    marker in one corner only, and i's bits in the interior."""
    px = [[0] * 8 for _ in range(8)]
    px[0][0] = 15
    for b in range(36):
        px[1 + b // 6][1 + b % 6] = 1 + ((i >> b) & 1)
    return L._pack(px)


def _synthetic(n_tiles, line=2):
    """A donor whose background period is 4 x 4 chunks (one plane), every cell a real tile,
    cycling through n_tiles distinct ones in row-major order."""
    tpc = 16
    # tile 1 (the first cell's) is flip-SYMMETRIC, so its canonical form needs no flip bit
    # and its word carries only what the donor gave it: the case the $0000 refusal is about
    art = bytes(32) + bytes([0x11] * 32) + b"".join(_tile(i) for i in range(1, n_tiles))
    ct = np.zeros((17, tpc, tpc), dtype="int64")
    for cr in range(4):
        for cc in range(4):
            for r in range(tpc):
                for c in range(tpc):
                    k = (cr * tpc + r) * 64 + cc * tpc + c
                    ct[1 + cr * 4 + cc, r, c] = (line << 13) | (1 + k % n_tiles)
    bg = np.array([[1 + (r % 4) * 4 + (c % 4) for c in range(8)] for r in range(16)],
                  dtype="int64")
    return lambda _d, _z: (bg, ct, art)


def test_refuses_more_tiles_than_the_static_budget():
    L.lower("synthetic", "Z", loader=_synthetic(BG_STATIC_TILE_BUDGET - 64))   # control
    with pytest.raises(L.ClipBgError) as exc:
        L.lower("synthetic", "Z", loader=_synthetic(BG_STATIC_TILE_BUDGET + 1))
    assert "BG_STATIC_TILE_BUDGET" in str(exc.value)


def test_refuses_an_opaque_cell_that_would_lower_to_the_transparent_word():
    L.lower("synthetic", "Z", loader=_synthetic(8, line=2))          # control
    with pytest.raises(L.ClipBgError) as exc:
        L.lower("synthetic", "Z", loader=_synthetic(8, line=0))
    assert "$0000" in str(exc.value)
