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


def _need_donor(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row is "
                    f"checked: {e}")


@pytest.mark.parametrize("donor,zone", [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ"),
                                        (S.S2_FINAL, "OOZ"), (S.S2_FINAL, "WFZ"),
                                        (S.S2_PROTOTYPE, "HPZ")])
def test_every_lowered_cell_is_the_donors_own_cell(donor, zone):
    _need_donor(donor)
    words, tiles, info = L.lower(donor, zone)
    bg, ct, art = L._load(donor, zone)
    tpc = ct.shape[1]
    period = info["period_cells"] // tpc
    start = info["crop_start_chunk"]
    r0c = info["window_top_px"] // (tpc * 8)
    assert len(words) == L.PLANE_COLS * L.PLANE_ROWS
    for r in range(L.PLANE_ROWS):
        for c in range(L.PLANE_COLS):
            gc = start * tpc + c
            chunk = int(bg[r0c + r // tpc, (gc // tpc) % period])
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


def _whole_map_period(bg, ct):
    """The pre-2026-09-27 rule, restated: the period over EVERY painted row of the map."""
    painted = [r for r in range(bg.shape[0])
               if any((ct[c] & 0x7FF).any() for c in set(bg[r].tolist()))]
    width = max(c for c in range(bg.shape[1]) if bg[:max(painted) + 1, c].any()) + 1
    return next((p for p in range(1, width)
                 if all((bg[r, :width - p] == bg[r, p:width]).all()
                        for r in range(max(painted) + 1))), None)


@pytest.mark.parametrize("zone", ["EHZ", "CPZ", "MTZ", "OOZ"])
def test_the_window_rule_changes_nothing_for_the_zones_lowered_before_it(zone):
    """The period is now measured over the rows the plane holds. For every zone clipped before
    the change (and OOZ, lowered by the old rule too) the window is rows 0..511 and the period
    is the whole-map period, so the crop, and every byte, is what it was."""
    _need()
    _w, _t, info = L.lower(S.S2_FINAL, zone)
    bg, ct, _art = L._load(S.S2_FINAL, zone)
    assert info["window_top_px"] == 0
    assert info["period_cells"] == _whole_map_period(bg, ct) * ct.shape[1]


def test_wing_fortress_window_holds_its_start_view_and_repeats():
    """WFZ was refused (no period over the whole map: the fortress's far-right rows 0-1 and
    the rows 11-12 feature never repeat). Its plane window is the lowest chunk-aligned one that
    holds Sonic 2's start view, DERIVED here from StartLocations and the 1:1 BG, and inside it
    the clouds repeat every 4 chunks, one plane exactly, so the wrap invents no seam."""
    _need()
    bg, ct, _art = L._load(S.S2_FINAL, "WFZ")
    assert _whole_map_period(bg, ct) is None                 # the old refusal, still true
    _x, y = S.start_position("WFZ", S.S2_FINAL)
    view = (y - 0x60, y - 0x60 + L.SCREEN_PX)                # BG Y = camera Y (1:1)
    r0 = L.window_top(S.S2_FINAL, "WFZ")
    assert r0 % L.CHUNK_PX == 0 and r0 <= view[0] and view[1] <= r0 + L.PLANE_ROWS * 8
    assert r0 - L.CHUNK_PX < 0 or view[1] > r0 - L.CHUNK_PX + L.PLANE_ROWS * 8
    _w, _t, info = L.lower(S.S2_FINAL, "WFZ")
    assert info["window_top_px"] == r0
    assert info["period_cells"] == L.PLANE_COLS and info["seam_cost_pixels"] == 0


def test_hidden_palace_background_comes_from_off_level():
    """HPZ's background is Off_Level's act-1 BG row (HPZ_BG.bin, 8 x 9 chunks), repeated
    across the RAM row the way Interleave_Level_Layout does it."""
    _need_donor(S.S2_PROTOTYPE)
    fg, bgp = S.proto_layout_paths("HPZ", S.S2_PROTOTYPE)
    assert os.path.basename(bgp) == "HPZ_BG.bin" and os.path.basename(fg) == "HPZ_1.bin"
    raw = S.read_bytes(bgp)
    w, h = raw[0] + 1, raw[1] + 1
    grid = S.load_bg_grid("HPZ", S.S2_PROTOTYPE)
    assert grid.shape == (h, 128)
    assert all(int(grid[r, c]) == raw[2 + r * w + c % w] for r in range(h) for c in range(128))
    _w, tiles, info = L.lower(S.S2_PROTOTYPE, "HPZ")
    assert info["window_top_px"] == 0 and info["period_cells"] == w * 16


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


@pytest.mark.parametrize("donor,top", [(S.S2_FINAL, "s2.asm"), (S.S2_PROTOTYPE, "main.asm")])
def test_backdrop_register_is_read_from_each_donors_own_top_file(donor, top):
    """The clip bake reads the backdrop colour (VDP register 7) off the START zone's donor.
    Hidden Palace's only donor is the prototype, whose top file is main.asm, not s2.asm: the
    reader used to open s2.asm for every donor, so an act starting in HPZ could not bake.
    Expected value re-read here from the named file by line, not through s2_donor."""
    root = _need_donor(donor)
    lines = open(os.path.join(root, top), errors="replace").read().split("\n")
    s = next(i for i, ln in enumerate(lines) if ln.rstrip() == "Level:")
    e = next(i for i in range(s + 1, len(lines)) if lines[i].rstrip() == "Level_LoadPal:")
    writes = [ln.split("#$87", 1)[1][:2] for ln in lines[s:e]
              if "move.w" in ln and "#$87" in ln and "(a6)" in ln]
    assert len(writes) == 1
    assert L.s2_backdrop_register(donor) == int(writes[0], 16)
