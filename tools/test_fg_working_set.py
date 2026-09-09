"""Unit tests for tools/fg_working_set.py — the FG art-pool working-set model.

RUNNER: build.sh's PRE-BUILD pytest lane (`python3 -m pytest tools -m "not
needs_build"`), which sweeps `tools/test_*.py` at maxdepth 1. Nothing here
reads a build artifact, so nothing carries `needs_build`.

WHAT THESE TESTS PROTECT. The tool's answer is a number the VRAM budget will be
argued from, so the failure that matters is a MODEL that quietly computes
something other than what it claims:

  * the fast rectangle query silently disagreeing with a direct scan
    (`test_page_set_matches_bruteforce`, `test_mask_field_matches_page_mask`)
  * a window dimension having been TYPED IN rather than derived from the
    engine's own constants (`test_windows_are_derived_from_engine_constants`)
  * a constant the model cannot ground being silently defaulted instead of
    refused (`test_missing_constant_is_loud`)
  * an unmeasurable cache configuration rendering as 0 / green
    (`test_unmeasurable_never_renders_as_a_number`,
     `test_window_larger_than_act_is_loud`)
  * the LRU/re-entry simulation drifting from its stated semantics
    (`test_lru_reentry_hand_worked`)

Every one was proven RED by an applied source mutation before being accepted;
the mutations are named in docs/research/2026-09-09-fg-working-set.md.
"""

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fg_working_set as fws


# ---------------------------------------------------------------------------
# Synthetic fixtures — small, deterministic, independent of the baked act
# ---------------------------------------------------------------------------

def synthetic_grid(rows=37, cols=41, pages=6, seed=20260909):
    rng = random.Random(seed)
    return [[rng.choice([-1] + list(range(pages))) for _ in range(cols)]
            for _ in range(rows)]


@pytest.fixture(scope="module")
def field():
    return fws.PageField(synthetic_grid())


@pytest.fixture(scope="module")
def model():
    return fws.Model()


# ---------------------------------------------------------------------------
# 1. The fast rectangle query against a direct scan
# ---------------------------------------------------------------------------

def test_page_set_matches_bruteforce(field):
    """The integral-image answer IS the direct-scan answer, on 400 rectangles.

    These are two independent implementations of one function; if the integral
    arithmetic is wrong the peak, the histogram and the churn are all wrong
    together and nothing else in the tool would notice.
    """
    rng = random.Random(1)
    checked = 0
    for _ in range(400):
        h = rng.randint(1, field.rows)
        w = rng.randint(1, field.cols)
        r0 = rng.randint(0, field.rows - h)
        c0 = rng.randint(0, field.cols - w)
        fast = field.page_set(r0, c0, h, w)
        slow = field.page_set_bruteforce(r0, c0, h, w)
        assert fast == slow, (
            f"rect r0={r0} c0={c0} {w}x{h}: integral {sorted(fast)} != "
            f"scan {sorted(slow)}")
        checked += 1
    assert checked == 400, "the sweep did not run — a vacuous pass"


def test_page_set_covers_the_whole_grid(field):
    """The full-grid rectangle must find exactly the grid's own page set.

    Guards the degenerate direction the random rectangles above can miss: an
    integral that is right on interiors and wrong at the (0,0) corner term.
    """
    whole = field.page_set(0, 0, field.rows, field.cols)
    assert whole == set(field.pages)
    assert whole, "the fixture grid carries no pages — the test proves nothing"


def test_mask_field_matches_page_mask(field):
    """The memoized per-placement field agrees with the single-rectangle query.

    Every consumer (peak, histogram, pinned union, LRU) reads `mask_field`;
    only this test holds it to `page_mask`.
    """
    w, h = 7, 5
    masks = fws.PageField.mask_field(field, w, h)
    assert len(masks) == field.rows - h + 1
    assert len(masks[0]) == field.cols - w + 1
    for r0, row in enumerate(masks):
        for c0, m in enumerate(row):
            assert m == field.page_mask(r0, c0, h, w), (
                f"mask_field disagrees at r0={r0} c0={c0}")


def test_popcount_and_mask_roundtrip():
    for bits in (0, 1, 0b1011, 0b1111111111):
        s = fws.mask_to_set(bits)
        assert fws.popcount(bits) == len(s)
        back = 0
        for p in s:
            back |= 1 << p
        assert back == bits


# ---------------------------------------------------------------------------
# 2. Constants are DERIVED, not typed in
# ---------------------------------------------------------------------------

def test_windows_are_derived_from_engine_constants(model):
    """Each window equals the identity the engine's own constants define.

    Re-derived here from the PRIMITIVE constants (SCREEN_WIDTH/HEIGHT,
    TILE_CACHE_COLS/ROWS) rather than copied from the same derived names the
    model used — otherwise the check and the subject would be one expression
    agreeing with itself.
    """
    c = model.c
    # visible, worst sub-tile alignment: first and last visible pixel columns
    # are camera .. camera+SCREEN_WIDTH-1; the widest tile span is the one a
    # 7-px offset produces.
    expect_cols = ((7 + c["SCREEN_WIDTH"] - 1) >> 3) + 1
    expect_rows = ((7 + c["SCREEN_HEIGHT"] - 1) >> 3) + 1
    assert model.win_visible == (expect_cols, expect_rows)

    # tile-aligned: exactly the screen in tiles
    assert model.win_visible_aligned == (c["SCREEN_WIDTH"] >> 3,
                                         c["SCREEN_HEIGHT"] >> 3)
    # the plane fill must cover at least the visible window, by the engine's
    # own `ensure` pair in constants.emp
    assert model.win_plane_fill[0] >= model.win_visible[0]
    assert model.win_plane_fill[1] >= model.win_visible[1]
    # the residency window IS the tile cache (page_cache.emp's refcount
    # invariant is stated over it), and it must contain the plane fill
    assert model.win_tile_cache == (c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"])
    assert model.win_tile_cache[0] >= model.win_plane_fill[0]
    assert model.win_tile_cache[1] >= model.win_plane_fill[1]


def test_pool_geometry_is_self_consistent(model):
    c = model.c
    assert (1 << c["PAGE_FRAME_TILE_SHIFT"]) == c["ART_POOL_PAGE_TILES"]
    assert c["PAGE_FRAMES"] * c["ART_POOL_PAGE_TILES"] == c["POOL_TILE_CEILING"]
    assert c["PAGE_FRAMES"] <= c["PAGE_FRAMES_MAX"]
    # section tile extent from SECTION_SIZE world px, 8 px per tile
    assert model.section_tiles * 8 == c["SECTION_SIZE"]
    assert model.act_cols == c["GRID_W"] * model.section_tiles


def test_missing_constant_is_loud():
    """A name the tree does not define must RAISE, never resolve to a default.

    A silently-defaulted constant is the single failure this model could not
    survive: every downstream number would still be printed, and printed wrong.
    """
    src = fws.load_constants()
    with pytest.raises(KeyError):
        src.get("NO_SUCH_CONSTANT_IN_THIS_TREE")


def test_constant_sources_are_recorded(model):
    """Every constant the model uses names the file it was read from."""
    for name in fws.NEEDED:
        origin = model.src.origin[name]
        assert origin.endswith(".emp"), f"{name} has no .emp origin"
        assert os.path.isfile(os.path.join(fws.REPO, origin))


# ---------------------------------------------------------------------------
# 3. Unmeasurable is loud, never zero
# ---------------------------------------------------------------------------

def test_unmeasurable_never_renders_as_a_number():
    """A cache too small to hold the pinned set reports UNMEASURABLE.

    It must not report 0 re-entries — which is what "it never evicted" would
    literally compute, and which reads as the BEST possible result.
    """
    grid = synthetic_grid(rows=12, cols=12, pages=4)
    f = fws.PageField(grid)
    out = fws.traverse_reentry(f, 3, 3, frames=2, pinned={0, 1, 2})
    assert "unmeasurable" in out
    assert "re_entries_per_1000px" not in out
    assert "page_ins" not in out


def test_window_larger_than_act_is_loud():
    f = fws.PageField(synthetic_grid(rows=8, cols=8, pages=3))
    with pytest.raises(ValueError):
        f.mask_field(9, 3)
    with pytest.raises(ValueError):
        f.mask_field(3, 9)


# ---------------------------------------------------------------------------
# 4. The LRU / re-entry simulation, hand-worked
# ---------------------------------------------------------------------------

def test_lru_reentry_hand_worked():
    """A 1-row field whose page-in and re-entry counts are worked by hand.

    Grid is one row, one page per cell:  0 1 2 0
    Window 1x1 walks it with a 2-frame cache, no pinning.
      step 0 -> {0}: miss (resident 0)
      step 1 -> {1}: miss (resident 0,1)
      step 2 -> {2}: miss, evicts 0     (resident 1,2)
      step 3 -> {0}: miss AND RE-ENTRY  (0 was evicted at step 2)
    So 4 page-ins, 1 re-entry, 4 steps = 32 px of travel.
    """
    f = fws.PageField([[0, 1, 2, 0]])
    out = fws.traverse_reentry(f, 1, 1, frames=2, pinned=set(),
                               honour_pinning=False)
    assert out["camera_steps"] == 4
    assert out["camera_travel_px"] == 32
    assert out["page_ins"] == 4
    assert out["re_entries"] == 1
    assert out["re_entry_fraction_of_page_ins"] == pytest.approx(0.25)
    assert out["re_entries_per_1000px"] == pytest.approx(1000.0 / 32)


def test_reentry_is_zero_when_the_cache_holds_everything():
    """A cache at least as large as the act's page set never re-enters."""
    f = fws.PageField([[0, 1, 2, 0, 1, 2]])
    out = fws.traverse_reentry(f, 1, 1, frames=3, pinned=set(),
                               honour_pinning=False)
    assert out["page_ins"] == 3
    assert out["re_entries"] == 0


def test_pinned_pages_are_never_evicted():
    """Pinning a page must keep it resident, so it can never be a re-entry.

    Grid 0 1 2 3 0, window 1x1, 3 frames, page 0 pinned:
      start   resident [0]        (pinned pages are pre-resident)
      cell 0  {0} hit
      cell 1  {1} miss            resident [0,1]
      cell 2  {2} miss            resident [0,1,2]
      cell 3  {3} miss, evicts 1  resident [0,2,3]   <- 1, not 0: 0 is pinned
      cell 4  {0} HIT             (an unpinned 0 would have been a re-entry)
    3 page-ins, 0 re-entries. The counterpart without pinning is the
    hand-worked test above, which DOES record a re-entry.
    """
    f = fws.PageField([[0, 1, 2, 3, 0]])
    out = fws.traverse_reentry(f, 1, 1, frames=3, pinned={0})
    assert out["page_ins"] == 3
    assert out["re_entries"] == 0

    loose = fws.traverse_reentry(f, 1, 1, frames=3, pinned={0},
                                 honour_pinning=False)
    assert loose["page_ins"] == 5
    assert loose["re_entries"] == 1


# ---------------------------------------------------------------------------
# 5. The real baked data — shape invariants only (cheap; no full sweep)
# ---------------------------------------------------------------------------

def test_real_page_grid_is_inside_the_manifest(model):
    """Every page id the act's nametables reach exists in the pool manifest.

    A page id past the manifest would mean the local->global maps and the pool
    disagree — the exact drift `PageCache`'s own `cmp.w PageIn_Pool_Pages`
    bounds check exists to survive at runtime.
    """
    grid, per_section, air = fws.load_page_grid(model)
    manifest = fws.load_pool_manifest()
    n_pages = len(manifest["pages"])
    seen = {v for row in grid for v in row if v >= 0}
    assert seen, "no pool page is referenced anywhere — the decode is broken"
    assert max(seen) < n_pages, (
        f"page {max(seen)} referenced but the manifest has {n_pages} pages")
    assert len(grid) == model.act_rows
    assert len(grid[0]) == model.act_cols
    # per-section sets must be exactly the union of what the grid shows there
    st = model.section_tiles
    for sec, pages in per_section.items():
        sx, sy = sec % model.grid_w, sec // model.grid_w
        from_grid = {grid[r][c]
                     for r in range(sy * st, (sy + 1) * st)
                     for c in range(sx * st, (sx + 1) * st)
                     if grid[r][c] >= 0}
        assert from_grid == pages, f"section {sec} page set disagrees"
    assert set(air) == set(range(model.grid_w * model.grid_h))


def test_manifest_page_tiles_match_the_pool_ceiling(model):
    """The manifest's page size is the engine's ART_POOL_PAGE_TILES."""
    manifest = fws.load_pool_manifest()
    assert manifest["page_tiles"] == model.c["ART_POOL_PAGE_TILES"]
    assert sum(p["tiles"] for p in manifest["pages"]) == manifest["pool_tiles"]
    assert manifest["pool_tiles"] <= model.c["POOL_TILE_CEILING"]


def test_vram_map_agrees_with_the_pool_ceiling(model):
    """The GENERATED VRAM map's fg_art_pool row is POOL_TILE_CEILING tiles.

    This is the check that catches a stale hand-copied VRAM table: the tool
    reads docs/generated/vram-map-sonic4.md and refuses to proceed if it
    disagrees with the engine constant.
    """
    v = fws.vram_summary(model)
    assert v["fg_art_pool_tiles"] == model.c["POOL_TILE_CEILING"]
    assert v["window_tiles_total"] == (
        v["window_tiles_shipped_object_art"]
        + v["window_tiles_debug_or_mode_only"]
        + v["window_tiles_bg_owned"])


def test_latency_derivation_names_every_input():
    """No cycle figure enters the lookahead without a cited source."""
    for key, entry in fws.LATENCY_INPUTS.items():
        assert isinstance(entry["value"], int), key
        assert entry["source"].strip(), f"{key} has no source"
        assert len(entry["source"]) > 30, f"{key}'s source is not a citation"
    assert fws.latency_frames() >= 1
