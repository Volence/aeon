"""tools/fg_page_order.py — the Pass 4 page order and the FG window-budget refusal.

STITCHED-ACT-PAGE-ORDER wiring (2026-09-17). What these rows hold:

  * The budget is PARAMETERS, not literals. Every placement/refusal row runs twice: under
    the constants read from engine/system/constants.emp today, and under the other option
    on the owner's open card FG-CACHE-10-HOW (640 tiles as 20 x 32-tile pages, tile-cache
    margins 8/10, so a 56x48 window). The expected numbers are derived from whichever set
    the row runs, never typed.
  * The ladder: the shipped order is kept when it fits; otherwise the per-zone, budget-
    aimed search runs, and its pages never mix zones and keep page-aligned slots.
  * The count is right: the vectorised window count equals a direct scan.
  * The refusal fires, names the worst window and its count, and cannot be passed by an
    unmeasurable input.
  * `check`, the build lane, passes the committed tree and refuses it once the budget is
    one frame under its measured worst.

Fixtures are synthetic stitched acts: two 256x256-tile "zones" side by side, tiled in
square blocks each drawing on its own tile set. Block size and tiles per block set how
many distinct tiles a camera window meets.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fg_page_order as fpo     # noqa: E402
import ojz_strip_gen            # noqa: E402
import tile_dedupe              # noqa: E402

SECTION_TILES = 256


def _source():
    return fpo.load_budget_constants()


def _card_option_20x32(c):
    """FG-CACHE-10-HOW's second option as a parameter set: 640 tiles in 32-tile pages
    (20 frames) and margins 8 columns / 10 rows, the window being screen + 2 x margin."""
    alt = dict(c)
    alt["ART_POOL_PAGE_TILES"] = 32
    alt["PAGE_FRAME_TILE_SHIFT"] = 5
    alt["POOL_TILE_CEILING"] = 640
    alt["PAGE_FRAMES"] = alt["POOL_TILE_CEILING"] // alt["ART_POOL_PAGE_TILES"]
    alt["TILE_CACHE_MARGIN_H"], alt["TILE_CACHE_MARGIN_V"] = 8, 10
    alt["TILE_CACHE_COLS"] = (c["SCREEN_WIDTH"] >> 3) + 2 * alt["TILE_CACHE_MARGIN_H"]
    alt["TILE_CACHE_ROWS"] = (c["SCREEN_HEIGHT"] >> 3) + 2 * alt["TILE_CACHE_MARGIN_V"]
    fpo.validate_budget_constants(alt)
    return alt


PARAM_SETS = ["source", "card_20x32"]


def _params(name):
    c = _source()
    return c if name == "source" else _card_option_20x32(c)


def _rule(pages, sets):
    return [i for i, f in enumerate(ojz_strip_gen.mark_pinned_pages(pages, sets)) if f]


def _tile(i):
    return bytes([(i >> 16) & 255, (i >> 8) & 255, i & 255, 1] + [(i * 7 + k) & 255 for k in range(28)])


def _blocks(block, per_block, gw=2, gh=1, seed=1):
    H, W = gh * SECTION_TILES, gw * SECTION_TILES
    canon = np.zeros((H, W), dtype=np.int64)
    zone = np.zeros((H, W), dtype=np.int16)
    rng = np.random.default_rng(seed)
    nid = 1
    for by in range(0, H, block):
        for bx in range(0, W, block):
            ids = np.arange(nid, nid + per_block)
            nid += per_block
            canon[by:by + block, bx:bx + block] = rng.choice(
                ids, size=(min(block, H - by), min(block, W - bx)))
    for sx in range(gw):
        zone[:, sx * SECTION_TILES:(sx + 1) * SECTION_TILES] = sx
    unique = [tile_dedupe.BLANK_TILE] + [_tile(i) for i in range(1, nid)]
    return canon, zone, unique, gw, gh


def _place(c, fixture):
    canon, zone, unique, gw, gh = fixture
    return fpo.place_pool(canon, zone, unique, SECTION_TILES, gw, gh, c, _rule)


# ---------------------------------------------------------------------------

def test_budget_constants_are_read_from_engine_source():
    c = _source()
    import fg_working_set
    src = fg_working_set.ConstantSource()
    src.load_file(fpo.CONSTANTS_EMP)
    for name in fpo.BUDGET_CONSTANTS:
        assert c[name] == src.get(name), name
    assert c["PAGE_FRAMES"] == c["POOL_TILE_CEILING"] // c["ART_POOL_PAGE_TILES"]
    # the generator's page size is the same source value, not its own literal
    assert ojz_strip_gen.ART_POOL_PAGE_TILES == c["ART_POOL_PAGE_TILES"]


def test_incoherent_parameter_set_is_refused():
    c = dict(_source())
    c["PAGE_FRAMES"] += 1                       # no longer tiles POOL_TILE_CEILING
    with pytest.raises(fpo.BudgetError):
        fpo.validate_budget_constants(c)


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_shipped_order_kept_when_it_fits(pset):
    c = _params(pset)
    fx = _blocks(block=64, per_block=40)
    pl = _place(c, fx)
    assert pl["rung"] == "shipped"
    assert pl["verdict"]["ok"] and pl["verdict"]["frames"] == c["PAGE_FRAMES"]
    canon, _zone, unique, gw, gh = fx
    unique = list(unique)
    per_section = fpo.per_section_lists(canon, SECTION_TILES, gw, gh)
    order = tile_dedupe.pin_blank_tile_first(tile_dedupe.order_pool_spatially(per_section), unique)
    assert pl["pages"] == tile_dedupe.split_pool_into_pages(order, c["ART_POOL_PAGE_TILES"])


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_search_rung_fits_an_act_the_shipped_order_overflows(pset):
    c = _params(pset)
    F, page = c["PAGE_FRAMES"], c["ART_POOL_PAGE_TILES"]
    pl = _place(c, _blocks(block=32, per_block=32))
    assert pl["stats"]["shipped_worst_pin0"] > F, "fixture no longer overflows the shipped order"
    assert pl["rung"] == "searched"
    v = pl["verdict"]
    assert v["ok"] and v["worst"] <= F and v["over"] == 0
    assert v["page_tiles"] == page and v["window"] == [c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]]
    # per-zone pages: no page mixes zones; slots are page-aligned (a short page keeps a gap)
    canon, zone = pl["canon"], _blocks(block=32, per_block=32)[1]
    zone_of = {}
    for t, z in zip(canon.ravel().tolist(), zone.ravel().tolist()):
        zone_of.setdefault(t, set()).add(z)
    blank = pl["unique"].index(tile_dedupe.BLANK_TILE)
    for p, lst in enumerate(pl["pages"]):
        assert len(lst) <= page
        zs = set().union(*(zone_of[t] for t in lst if t != blank)) if any(t != blank for t in lst) else set()
        assert len(zs) <= 1, f"page {p} mixes zones {zs}"
        for i, t in enumerate(lst):
            assert pl["slot_of"][t] == p * page + i


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_window_count_equals_a_direct_scan(pset):
    c = _params(pset)
    pl = _place(c, _blocks(block=32, per_block=32))
    pg, pins, needed = pl["page_grid"], set(pl["pins"]) | {0}, pl["needed"]
    lefts, tops = pl["lefts"], pl["tops"]
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    rng = np.random.default_rng(3)
    picks = [(int(rng.integers(len(tops))), int(rng.integers(len(lefts)))) for _ in range(60)]
    ti, li = np.nonzero(needed == needed.max())
    picks.append((int(ti[0]), int(li[0])))
    for t, l in picks:
        top, left = int(tops[t]), int(lefts[l])
        sub = pg[top:top + rows, left:left + cols]
        direct = set(np.unique(sub[sub >= 0]).tolist()) | pins
        assert len(direct) == int(needed[t, l]), (top, left)
    # and the camera -> window map holds the parameter set's window size
    l_, r_, t_, b_ = fpo.window_for_camera(c, 8 * 300 + 5, 8 * 300 + 3)
    assert (r_ - l_ + 1, b_ - t_ + 1) == (cols, rows)


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_refusal_is_keyed_to_the_budget_parameter(pset):
    """One frame under the placed act's measured worst refuses, naming that window; at the
    worst it passes. Nothing here is a literal frame count."""
    c = _params(pset)
    pl = _place(c, _blocks(block=32, per_block=32))
    worst = pl["verdict"]["worst"]
    at = dict(c)
    at["PAGE_FRAMES"] = worst
    at["POOL_TILE_CEILING"] = worst * c["ART_POOL_PAGE_TILES"]
    fpo.validate_budget_constants(at)
    fpo.refuse_over_budget(fpo.budget_verdict(pl["needed"], pl["lefts"], pl["tops"], at), "fixture")
    under = dict(at)
    under["PAGE_FRAMES"] = worst - 1
    under["POOL_TILE_CEILING"] = (worst - 1) * c["ART_POOL_PAGE_TILES"]
    v = fpo.budget_verdict(pl["needed"], pl["lefts"], pl["tops"], under)
    assert not v["ok"] and v["over"] > 0 and v["worst"] == worst
    with pytest.raises(SystemExit) as exc:
        fpo.refuse_over_budget(v, "fixture")
    msg = str(exc.value)
    w = v["worst_window_tile"]
    assert f"worst window needs {worst}" in msg
    assert f"tile left {w['left']} top {w['top']}" in msg
    assert f"budget {worst - 1} frames x {c['ART_POOL_PAGE_TILES']}-tile pages" in msg


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_act_no_order_can_fit_is_refused_end_to_end(pset, monkeypatch):
    """Every window of a noise act holds more distinct tiles than PAGE_FRAMES pages can,
    so NO order fits (the any-order floor), and place_pool's verdict must refuse. The try
    budget is cut to keep the row fast: the refusal is guaranteed by the floor, not by
    how hard the search tried."""
    c = _params(pset)
    monkeypatch.setattr(fpo, "REFINE_MAX_TRIES", 25)
    fx = _blocks(block=SECTION_TILES, per_block=2000, gw=1, gh=1)
    pl = _place(c, fx)
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    glob = pl["slot_of"][pl["canon"]]
    floor_min = min(
        -(-np.unique(glob[t:t + rows, l:l + cols][glob[t:t + rows, l:l + cols] != 0]).size
          // c["ART_POOL_PAGE_TILES"])
        for t in pl["tops"][:3].tolist() for l in pl["lefts"][:3].tolist())
    assert floor_min > c["PAGE_FRAMES"], "fixture no longer exceeds the any-order floor"
    with pytest.raises(SystemExit) as exc:
        fpo.refuse_over_budget(pl["verdict"], "noise fixture")
    assert "REFUSED" in str(exc.value)


def test_check_passes_the_committed_tree_and_refuses_one_frame_under_its_worst(monkeypatch, capsys):
    c = _source()
    assert fpo.check() == 0
    out = capsys.readouterr().out
    assert "FG page budget OK" in out
    pg, pins, n_pages = fpo.committed_placement(c)
    lefts, tops, _, _ = fpo.camera_windows(c, pg.shape[1], pg.shape[0])
    needed, _ = fpo.window_needed(pg, n_pages, pins, c, lefts, tops)
    worst = int(needed.max())
    assert worst <= c["PAGE_FRAMES"]
    under = dict(c)
    under["PAGE_FRAMES"] = worst - 1
    under["POOL_TILE_CEILING"] = (worst - 1) * c["ART_POOL_PAGE_TILES"]
    monkeypatch.setattr(fpo, "load_budget_constants", lambda path=None: under)
    assert fpo.check() == 1
    out = capsys.readouterr().out
    assert "FG page budget REFUSED" in out and f"worst window needs {worst}" in out


def test_check_has_no_report_only_mode(capsys):
    """stressart-budget (2026-09-26): the STRESS_ART fixture's report-only pass is how a
    13-page window over 12 frames shipped with nothing refusing (GPL-1). The flag is gone;
    passing it is an unknown argument (usage, exit 1), not a quiet pass."""
    with pytest.raises(SystemExit) as exc:
        fpo.main(["check", "--report-only"])
    assert exc.value.code == 1
    assert "unknown argument '--report-only'" in capsys.readouterr().out


def test_check_unmeasurable_exits_2_not_0(monkeypatch, capsys):
    def boom(c):
        raise fpo.BudgetError("planted: the committed tree could not be read")
    monkeypatch.setattr(fpo, "committed_placement", boom)
    assert fpo.main(["check"]) == 2
    assert "UNMEASURABLE" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The stress fixture's pin pass and refusal (ojz_strip_gen Pass 4c, stressart-budget)
# ---------------------------------------------------------------------------

def _shared_band_act(c, per_block=20, shared_pages=4):
    """A two-section act whose sections both carry the same `shared_pages` pages of tiles in
    their top rows (so the 75% rule pins them), laid out in the SHIPPED contiguous order the
    stress arm requires (slot == pool position). Returns (canon, slot_of_canon, pool order,
    per_section_slot_sets, n_canon, grid_w, (zone, unique, grid_h) for place_pool)."""
    page = c["ART_POOL_PAGE_TILES"]
    canon, zone, unique, gw, gh = _blocks(block=64, per_block=per_block)
    nid = len(unique)
    shared = np.arange(nid, nid + shared_pages * page)
    unique = list(unique) + [_tile(i) for i in shared.tolist()]
    band = 8
    for sx in range(gw):
        for k in range(shared_pages):
            canon[k * band:(k + 1) * band, sx * SECTION_TILES:sx * SECTION_TILES + page] = \
                shared[k * page:(k + 1) * page][None, :]
    per_section = fpo.per_section_lists(canon, SECTION_TILES, gw, gh)
    order = tile_dedupe.pin_blank_tile_first(tile_dedupe.order_pool_spatially(per_section), unique)
    slot_of = {t: i for i, t in enumerate(order)}
    sets = [{slot_of[t] for t in sec} for sec in per_section]
    return canon, slot_of, order, sets, len(unique), gw, (zone, unique, gh)


def _stressed(c, clones=None):
    """_shared_band_act plus stress clones exactly as stress_uniquify_pool shapes them:
    appended pool slots, each re-pointing one cell (strided over section 0), folded into
    that section's slot set. Returns the stress_pin_pass arguments and the ROM's glob grid."""
    page = c["ART_POOL_PAGE_TILES"]
    canon, slot_of, order, sets, n_canon, gw, _extra = _shared_band_act(c)
    clones = 2 * page if clones is None else clones
    base = len(order)
    redirect = {}
    for j in range(clones):
        col, row = (j * 37) % SECTION_TILES, (j * 53) % SECTION_TILES
        redirect[(0, col, row)] = base + j
    pool = list(order) + [f"clone{j}" for j in range(clones)]
    pages = tile_dedupe.split_pool_into_pages(pool, page)
    sets[0] |= set(redirect.values())
    glob = np.vectorize(slot_of.get)(canon).astype(np.int64)
    for (s_idx, col, row), slot in redirect.items():
        sy, sx = divmod(s_idx, gw)
        glob[sy * SECTION_TILES + row, sx * SECTION_TILES + col] = slot
    args = dict(canon_grid=canon, canon_to_pool=slot_of, n_canon=n_canon, redirect=redirect,
                pages=pages, per_section_global_sets=sets, grid_w=gw, section_tiles=SECTION_TILES)
    return args, glob, pages


def _budget(c, frames):
    b = dict(c)
    b["PAGE_FRAMES"] = frames
    b["POOL_TILE_CEILING"] = frames * c["ART_POOL_PAGE_TILES"]
    fpo.validate_budget_constants(b)
    return b


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_fixed_pool_placement_is_place_pools_own_pin_rule(pset):
    """place_fixed_pool (the stress arm's pass) over a placed act's own slot grid returns
    exactly place_pool's pins, count and verdict: one pin rule, one code path. The budget is
    the act's page-0-only worst (derived), where the frame-aware rule must trim the plain
    rule's pins, so an arm that shipped the plain rule could not pass."""
    c = _params(pset)
    canon, _slot, _order, _sets, _n, gw, (zone, unique, gh) = \
        _shared_band_act(c, per_block=16, shared_pages=3)
    w0 = int(fpo.place_pool(canon, zone, unique, SECTION_TILES, gw, gh, c, _rule)["needed_pin0"].max())
    b = _budget(c, w0)
    pl = fpo.place_pool(canon, zone, unique, SECTION_TILES, gw, gh, b, _rule)
    assert pl["rung"] == "shipped" and set(pl["pins"]) < set(pl["rule_pins"]), \
        "fixture: the frame-aware rule no longer trims the plain rule here"
    glob = pl["slot_of"][pl["canon"]]
    fx = fpo.place_fixed_pool(glob, len(pl["pages"]), pl["rule_pins"], b)
    assert fx["pins"] == pl["pins"]
    assert np.array_equal(fx["needed"], pl["needed"])
    assert fx["verdict"] == pl["verdict"]


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_stress_pin_pass_keeps_only_frame_aware_pins(pset):
    """GPL-1's shape: the plain 75% rule's pins push the stress act's worst window over
    PAGE_FRAMES, while the window alone (page 0 pinned) fits. The stress arm must ship the
    frame-aware subset, which fits. The budget is DERIVED from the fixture (its page-0-only
    worst), never typed."""
    c = _params(pset)
    args, glob, pages = _stressed(c)
    H, W = glob.shape
    lefts, tops, _, _ = fpo.camera_windows(c, W, H)
    pg = fpo.page_grid_of(glob, c)
    rule = [i for i, f in enumerate(ojz_strip_gen.mark_pinned_pages(pages, args["per_section_global_sets"])) if f]
    _n, pin0 = fpo.window_needed(pg, len(pages), {0}, c, lefts, tops)
    b = _budget(c, int(pin0.max()))
    plain, _ = fpo.window_needed(pg, len(pages), rule, c, lefts, tops)
    assert int(plain.max()) > b["PAGE_FRAMES"], "fixture: the plain rule no longer overflows"
    place = ojz_strip_gen.stress_pin_pass(budget=b, stress_n=len(pages) * 64, **args)
    expect, needed = fpo.frame_aware_pins(pg, rule, b["PAGE_FRAMES"], pin0, b, lefts, tops)
    assert place["pins"] == expect and set(expect) < set(rule)
    assert place["verdict"]["ok"] and int(needed.max()) == place["verdict"]["worst"] <= b["PAGE_FRAMES"]
    manifest_pins = [i for i in range(len(pages)) if i in set(place["pins"])]
    assert manifest_pins == sorted(place["pins"])


@pytest.mark.parametrize("pset", PARAM_SETS)
def test_stress_pin_pass_refuses_a_window_over_budget(pset):
    """One frame under the stress act's frame-aware worst, the pass REFUSES, naming the
    window, its camera, its page count and the frame count (the report-only pass it replaces
    printed this and exited 0)."""
    c = _params(pset)
    args, glob, _pages = _stressed(c)
    at = _budget(c, _pin0_worst(c, args, glob))
    worst = ojz_strip_gen.stress_pin_pass(budget=at, stress_n=2600, **args)["verdict"]["worst"]
    assert worst == at["PAGE_FRAMES"]
    under = _budget(c, worst - 1)
    with pytest.raises(SystemExit) as exc:
        ojz_strip_gen.stress_pin_pass(budget=under, stress_n=2600, **args)
    msg = str(exc.value)
    assert msg.startswith("REFUSED — FG page budget: OJZ act 1 STRESS bake (--stress-uniquify 2600")
    assert f"worst window needs {worst}" in msg
    assert f"budget {worst - 1} frames x {c['ART_POOL_PAGE_TILES']}-tile pages" in msg
    assert "camera x=" in msg and "tile left" in msg
    assert "lower STRESS_ART_N" in msg


def _pin0_worst(c, args, glob):
    """The stress act's page-0-only worst window: the smallest budget its frame-aware pins
    can fit (a pin is kept only if it pushes no window over the budget)."""
    return int(fpo.place_fixed_pool(glob, len(args["pages"]), [0], c)["needed_pin0"].max())
