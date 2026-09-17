"""Gate: `clips.json` means one thing, and the bake that reads it composes the act the
rectangles describe — with each cell keyed to its OWN zone's tileset.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact, so no
row carries `needs_build`.

WHY THIS EXISTS. `docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 3: "the
bake reads a clip manifest and hands `place_pool` a real per-cell zone grid instead of a
uniform one", checked by "a two-clip act bakes; the worst-window count agrees with
`s2_clip_budget.py place` on the same two clips". These are that check's pins, plus the
rules `tools/clip_manifest.py` refuses by.

THE ANTI-VACUITY PROBLEM HERE, AND WHAT IS DONE ABOUT IT. Three separate traps:

  * A WORST-WINDOW AGREEMENT IS EASY TO GET BY ACCIDENT. `PAGE_FRAMES` is 12 and the
    S2 acts the design measured all land at exactly 12, so "both tools said 12" can be
    true of two tools that agree about nothing. `s2_two_clip_pins` exists for that: its
    answer is 10 under the correct pin wiring and 11 under the wiring the design's
    measurement tool shipped with, so agreement there is agreement about something.
    `test_the_pin_wiring_moves_this_fixture` asserts the two wirings really do differ,
    so the discriminating fixture cannot quietly stop discriminating.
  * THE ZONE KEY CAN BE VACUOUS TOO. If the two zones in a fixture never used the same
    tile index, dropping the key would change nothing. `test_the_two_clips_actually_collide`
    counts the indices both zones use, and `test_a_uniform_zone_key_breaks_the_art` is the
    converse control: the same bake with the key flattened must FAIL the art check.
  * A REFUSAL ROW CAN PASS BY RAISING FOR THE WRONG REASON. Every refusal row below
    asserts the rule's own tag (R6, R9, ...) is in the message, so a manifest refused by
    an earlier rule does not count as that rule firing.

Every row that needs a donor SKIPS SAYING SO when the donor cannot be resolved, rather
than passing on an empty set.
"""

import copy
import json
import os
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_act_bake as BAKE                # noqa: E402
import clip_manifest as CM                  # noqa: E402
import ojz_strip_gen                        # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
import tile_dedupe                          # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)

#: The zones the tracked fixtures clip. Two DIFFERENT final-game zones: the per-cell
#: tileset key is a no-op on an act made of one zone.
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ")]

#: The tracked fixtures, and the worst-window count each must produce. The counts are NOT
#: copied from a nearby pin: each is what `place_pool` returns for that act, and each is
#: re-derived twice per run — once by the placement and once by the recount off disk.
#: They are written here so a silent movement fails rather than prints.
FIXTURES = {
    "s2_two_clip": 12,
    "s2_two_clip_pins": 10,
}
FIXTURE_DIR = os.path.join(REPO, "games", "sonic4", "data", "clips")

#: The design's measurement tool, IMPORTED as the independent second implementation two rows
#: below cross-check against. Named as the FILE and the directory taken from its dirname: a
#: bare directory literal is a docs path `tools/land_gate.py` would need its own rule for
#: (test_land_gate_classifier's static scan reads these strings), and the file is the thing
#: this gate actually depends on.
BUDGET_TOOL = os.path.join(REPO, "docs", "research", "s2-compressed-act", "s2_clip_budget.py")


def _need(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")


@pytest.fixture(autouse=True, scope="module")
def no_working_tree_donors():
    """NO row in this file may read the repo's own converted donor trees.

    `games/sonic4/data/donors/` is gitignored by design, so ABSENT is the normal state of a
    checkout and PRESENT means somebody ran the converter. A row that reaches that path
    therefore passes on the author's machine and dies on a fresh clone — which is exactly
    what `r12` did: one `CM.load(p)` with no `donor_root=`, 37 rows green here and 2 ERRORS
    on a tree that had never run the converter.

    Pointing the module-level default at a path that cannot exist turns that class of
    mistake into a failure on EVERY machine instead of only on a clean one. It works because
    every entry point resolves this name at call time rather than binding it as a default
    argument (see clip_manifest.DEFAULT_DONOR_ROOT's note); a default bound at import could
    not be reached from here, and the guard would be decorative.
    """
    real = CM.DEFAULT_DONOR_ROOT
    CM.DEFAULT_DONOR_ROOT = os.path.join(
        REPO, "tools", "__no_donor_root_for_tests__", "this-path-must-not-exist")
    assert not os.path.exists(CM.DEFAULT_DONOR_ROOT)
    yield
    CM.DEFAULT_DONOR_ROOT = real


@pytest.fixture(scope="module")
def donors(tmp_path_factory):
    """A converted donor root holding CASES, in pytest's own tmp tree.

    Never `clip_manifest.DEFAULT_DONOR_ROOT`: a test must not be able to disturb a tree an
    author is working from, and must not pass merely because one happens to be lying there.
    The converter is deterministic and reads only the read-only donor checkouts, so this
    fixture MAKES what the rows need rather than requiring the caller to have made it — which
    is why 37 of the 39 rows already ran on a checkout with no converted trees at all.
    `no_working_tree_donors` above is what stops a row quietly reaching for the repo's copy
    instead of this one.
    """
    root = str(tmp_path_factory.mktemp("s2clipdonors"))
    for donor, zone in CASES:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


@pytest.fixture(scope="module")
def baked(donors, tmp_path_factory):
    """{fixture id: (ClipAct, state, clipact.json, placement verdict, recount verdict)}."""
    for donor, _zone in CASES:
        _need(donor)
    out = {}
    root = tmp_path_factory.mktemp("s2clipbake")
    for name in FIXTURES:
        src = os.path.join(FIXTURE_DIR, name, "clips.json")
        out[name] = BAKE.bake(src, out_dir=str(root / name), donor_root=donors, log=None)
    return out


def _write(tmp_path, doc, name="clips.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return str(p)


@pytest.fixture
def doc():
    """A minimal VALID two-clip manifest — the base every refusal row mutates one field of.

    Read from the tracked fixture rather than retyped, so a rule that starts refusing the
    real fixture cannot be hidden behind a hand-made one that happens to still pass.
    """
    with open(os.path.join(FIXTURE_DIR, "s2_two_clip", "clips.json")) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# The design's row-3 check
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_a_two_clip_act_bakes(baked, name):
    """The tracked fixture composes, places and emits, and the emitted tree re-counts to
    exactly the verdict it was placed at.

    N1 is `place_pool`'s own count over the grid it placed. N2 decodes the emitted
    local-index nametables through the emitted local maps and the emitted page manifest
    and counts again with the SAME functions `fg_page_order.check` calls
    (`window_needed`, `budget_verdict`). A difference is the emission, not the count.
    """
    _act, _st, m, v1, v2 = baked[name]
    assert v1["worst"] == FIXTURES[name], (name, v1)
    assert v2["worst"] == v1["worst"]
    assert (v2["windows"], v2["over"], v2["worst_positions"]) == \
           (v1["windows"], v1["over"], v1["worst_positions"])
    assert v1["over"] == 0, v1
    assert v1["windows"] > 10_000, v1          # not a one-window "sweep"
    assert m["pool"]["tiles"] > 500, m["pool"]
    assert m["act"]["grid_w"] * m["act"]["grid_h"] == len(m["sections"])


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_the_bake_agrees_with_the_designs_own_measurement(baked, donors, name):
    """N3: the same clips reached from the DONOR side, without clips.json or a converted
    tree, through `s2_clip_budget.build_act` + `place_pool`.

    That path is an independent second composition of the same act — it slices
    `s2_donor.load_zone`'s word grid directly, where the bake reassembles a converted
    tree's section files — so an agreement is an agreement about the geometry, not a
    tautology. The pin rule is wired the way `generate()` wires it on both sides; see
    `test_the_pin_wiring_moves_this_fixture` for why that matters.
    """
    sys.path.insert(0, os.path.dirname(BUDGET_TOOL))
    import s2_clip_budget as SB              # noqa: E402
    import fg_page_order as fpo              # noqa: E402
    import megaact_window_pageset as mb      # noqa: E402

    act, _st, _m, v1, _v2 = baked[name]
    assert all(cl.donor == S.S2_FINAL for cl in act.clips), \
        "this row hands build_act one --donor; a mixed-donor fixture needs the donor@ prefix"
    c, _ = mb.load_constants()
    st = c["SECTION_SIZE"] >> 3
    specs = []
    for cl in act.clips:
        # section-indexed spec, derived from the clip's own rectangles
        specs.append(f"{cl.zone}:{cl.src[0] // act.section_px},{cl.src[1] // act.section_px},"
                     f"{-(-cl.src[2] // act.section_px)},{-(-cl.src[3] // act.section_px)}")
    donor_act = SB.build_act(specs, st, 8, S.S2_FINAL, align=True)
    key = np.where(donor_act.zone_id < 0, 0,
                   (donor_act.zone_id.astype(np.int64) + 1) * 4096 + donor_act.src)
    ref = np.unique(key)
    raw = []
    for k in ref.tolist():
        if k == 0:
            raw.append(tile_dedupe.BLANK_TILE)
        else:
            z = donor_act.zones[k // 4096 - 1]
            raw.append(z.art[(k % 4096) * 32:((k % 4096) + 1) * 32])
    unique, mapping = tile_dedupe.dedupe_tiles(raw)
    k2c = np.array([m[0] for m in mapping], dtype=np.int64)
    canon = k2c[np.searchsorted(ref, key)]
    pl = fpo.place_pool(canon, donor_act.zone_id, unique, st,
                        donor_act.grid_w, donor_act.grid_h,
                        fpo.load_budget_constants(), SB.pin_rule_fn("wrapped"))
    v3 = pl["verdict"]
    assert v3["worst"] == v1["worst"], (name, v3, v1)
    assert v3["windows"] == v1["windows"], (name, v3, v1)
    assert v3["worst_positions"] == v1["worst_positions"], (name, v3, v1)
    assert v3["worst_window_tile"] == v1["worst_window_tile"], (name, v3, v1)


# ---------------------------------------------------------------------------
# The per-cell tileset key — the thing row 3 exists to deliver
# ---------------------------------------------------------------------------

def test_the_two_clips_actually_collide(baked):
    """The fixture is CAPABLE of failing the art check.

    Both zones' tile indices start at 0, so a shared index space would silently show one
    zone's art in the other's cells — but only for indices BOTH clips use. If that set
    were empty the key would be decorative and every row below would pass vacuously.
    """
    _act, st, _m, _v1, _v2 = baked["s2_two_clip"]
    zone_id, words = st["zone_id"], st["words"]
    used = []
    for z in range(len(st["sheets"])):
        m = zone_id == z
        used.append(set(np.unique(words[m] & BAKE.TILE_MASK).tolist()) - {0})
    shared = used[0] & used[1]
    assert len(used) == 2
    assert len(shared) > 100, (len(shared), [len(u) for u in used])


def test_two_zones_do_not_share_a_tile_index_space(baked):
    """Every referenced (zone, index) pair resolves to THAT zone's 32 bytes of art."""
    for name in FIXTURES:
        _act, st, _m, _v1, _v2 = baked[name]
        n = BAKE.verify_art_fidelity(st)
        assert n > 500, (name, n)


def test_a_uniform_zone_key_breaks_the_art(baked):
    """THE CONVERSE CONTROL for the row above, and for `fg_page_order.py`'s header.

    Re-run the dedupe with the zone key flattened to 0 everywhere — the uniform grid
    `ojz_strip_gen.generate()` passes, which is what that header said a stitched act's
    loader must replace. Two things must then be true, and if either stops being true the
    key is not reaching the dedupe and every fidelity row above is measuring nothing:
    the pool gets SMALLER (two zones' equal indices collapse into one entry), and at least
    one index that both zones use names 32 different bytes in the two blobs, so whichever
    zone lost the collapse now renders the other's tile.
    """
    _act, st, _m, _v1, _v2 = baked["s2_two_clip"]
    words, zone_id = st["words"], st["zone_id"]
    blobs = [s[2] for s in st["sheets"]]
    uniform = np.where(zone_id < 0, -1, 0).astype(np.int16)
    u2, _canon2, _key2, _s2c2 = BAKE.dedupe_keyed(words, uniform, blobs)
    assert len(u2) < len(st["placement"]["unique"]), (len(u2), len(st["placement"]["unique"]))

    used = []
    for z in range(len(blobs)):
        used.append(set(np.unique(words[zone_id == z] & BAKE.TILE_MASK).tolist()) - {0})
    differing = [i for i in sorted(used[0] & used[1])
                 if blobs[0][i * 32:(i + 1) * 32] != blobs[1][i * 32:(i + 1) * 32]]
    assert len(differing) > 100, (len(differing), len(used[0] & used[1]))


# ---------------------------------------------------------------------------
# The pin-rule defect this parcel found
# ---------------------------------------------------------------------------

def test_the_pin_rule_reaches_place_pool_as_page_indices(baked):
    """`place_pool` does `sorted(set(rule_pins_fn(...)) - {0})` and indexes pages with the
    result, so the callable must return PAGE INDICES.

    `ojz_strip_gen.mark_pinned_pages` returns a list[bool]; handing it over raw makes the
    candidate set `{True}` = page 1 for every act with any pinned page. Derived assertion,
    not a copied pin: every reported candidate must be an int in range(n_pages), and a
    list[bool] fails `type(...) is int`.
    """
    for name in FIXTURES:
        _act, _st, m, _v1, _v2 = baked[name]
        n_pages = m["pool"]["pages"]
        for p in m["placement"]["rule_pins"] + m["placement"]["pins"]:
            assert type(p) is int and not isinstance(p, bool), (name, p)
            assert 0 <= p < n_pages, (name, p, n_pages)


def test_the_pin_wiring_moves_this_fixture(baked):
    """`s2_two_clip_pins` is the fixture that can tell the two wirings apart. If this row
    stops failing to differ, the agreement row above has stopped discriminating and needs
    a new fixture — say so here rather than let it quietly become decorative.
    """
    sys.path.insert(0, os.path.dirname(BUDGET_TOOL))
    import s2_clip_budget as SB              # noqa: E402
    import fg_page_order as fpo              # noqa: E402

    act, st, _m, v1, _v2 = baked["s2_two_clip_pins"]
    budget = fpo.load_budget_constants()
    outs = {}
    for mode in ("wrapped", "raw"):
        pl = fpo.place_pool(st["pre_split_canon"], st["zone_id"], _fresh_unique(st),
                            act.section_tiles, act.grid_w, act.grid_h,
                            budget, SB.pin_rule_fn(mode))
        outs[mode] = pl["verdict"]["worst"]
    assert outs["wrapped"] == v1["worst"] == FIXTURES["s2_two_clip_pins"], outs
    assert outs["raw"] != outs["wrapped"], outs


def _fresh_unique(st):
    """The pre-placement `unique` list. `place_pool` may append to and reorder the list it
    is given (pin_blank_tile_first, zone_split), so a second call needs its own copy."""
    words, zone_id = st["words"], st["zone_id"]
    blobs = [s[2] for s in st["sheets"]]
    u, _c, _k, _m = BAKE.dedupe_keyed(words, zone_id, blobs)
    return u


# ---------------------------------------------------------------------------
# What section alignment buys, asserted rather than believed
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def r12(donors, tmp_path_factory):
    """The three `measure-alignment` placements, run through the bake."""
    for donor, _zone in CASES:
        _need(donor)
    out = {}
    for label, ax, bx in BAKE.ALIGN_ROWS:
        doc = {"schema": 1, "units": "world_px", "id": "r12",
               "act": {"grid_w": 2, "grid_h": 1}, "clips": [
            {"id": "a", "donor": BAKE.ALIGN_CLIPS[0], "zone": BAKE.ALIGN_CLIPS[1],
             "src_rect": {"x": 4096, "y": 0, "w": 1024, "h": 1024},
             "dst_rect": {"x": ax, "y": 0, "w": 1024, "h": 1024},
             "unaligned_dst_reason": "measurement probe"},
            {"id": "b", "donor": BAKE.ALIGN_CLIPS[2], "zone": BAKE.ALIGN_CLIPS[3],
             "src_rect": {"x": 4096, "y": 0, "w": 1024, "h": 1024},
             "dst_rect": {"x": bx, "y": 0, "w": 1024, "h": 1024},
             "unaligned_dst_reason": "measurement probe"}]}
        d = tmp_path_factory.mktemp("r12row")
        p = os.path.join(str(d), "clips.json")
        with open(p, "w") as fh:
            json.dump(doc, fh)
        act = CM.load(p, donor_root=donors, warn=None)
        st = BAKE.place(act, donors, log=None)
        m = BAKE.emit(act, st, os.path.join(str(d), "baked"), donors)
        out[label] = (m, BAKE.recount(os.path.join(str(d), "baked")))
    return out


def test_section_mixing_does_not_change_the_window_budget(r12):
    """The claim `clip_manifest`'s R11 and W3 are written against.

    Rows 2 and 3 of ALIGN_ROWS differ ONLY in whether a section boundary falls between two
    touching clips; the design's §2.2 said a straddling clip hurts the page budget, and it
    does not. Row 1 is kept beside them to show the budget difference in the table is
    adjacency, which is a different argument (§9.1's corridor).
    """
    sep, adj_pure, adj_mixed = (r12[lbl][1]["worst"] for lbl, _a, _b in BAKE.ALIGN_ROWS)
    assert adj_pure == adj_mixed, (adj_pure, adj_mixed)
    assert sep < adj_pure, (sep, adj_pure)


def test_section_mixing_does_change_the_local_map(r12):
    """What alignment DOES buy: one section's local tile map is one 11-bit space.

    Derived, not copied: the mixed act's populated section must need at least as many
    entries as the two split sections need between them, minus the one blank slot both
    carry, and it must stay under the cap the emitter itself enforces.
    """
    maps = {lbl: [s["local_map_entries"] for s in r12[lbl][0]["sections"]]
            for lbl, _a, _b in BAKE.ALIGN_ROWS}
    pure = maps[BAKE.ALIGN_ROWS[1][0]]
    mixed = maps[BAKE.ALIGN_ROWS[2][0]]
    assert max(mixed) >= sum(pure) - 1, (pure, mixed)
    assert min(mixed) == 1, mixed                # the empty section: blank only
    assert max(mixed) <= ojz_strip_gen.SECTION_LOCAL_INDEX_MAX + 1, mixed


# ---------------------------------------------------------------------------
# The manifest's rules
# ---------------------------------------------------------------------------

def test_the_tracked_fixtures_validate(donors):
    """The converse control for every refusal row: unmutated, both fixtures pass clean."""
    for donor, _zone in CASES:
        _need(donor)
    for name in FIXTURES:
        act = CM.load(os.path.join(FIXTURE_DIR, name, "clips.json"), donor_root=donors)
        assert len(act.clips) == 2
        assert len(act.zone_table) == 2, act.zone_table
        assert act.warnings == [], act.warnings
        assert [c.zone_key for c in act.clips] == [0, 1]


@pytest.mark.parametrize("tag,mutate", [
    ("R1", lambda d: d.update(schema=2)),
    ("R1", lambda d: d.update(units="tiles")),
    ("R3", lambda d: d.update(id="S2_Two_Clip")),
    ("R3", lambda d: d["clips"][0].update(id="EHZ")),
    ("R3", lambda d: d["clips"][0].update(region_id="EHZ_s2")),
    ("R3", lambda d: [c.update(region_id="same_region") for c in d["clips"]]),
    ("R3", lambda d: d["clips"][0].update(palette="S2_Palette_EHZ")),
    ("R2", lambda d: d["act"].update(grid_w=0)),
    ("R3", lambda d: d["clips"][1].update(id=d["clips"][0]["id"])),
    ("R4", lambda d: d["clips"][0].update(zone="NOT_A_ZONE")),
    ("R5", lambda d: d["clips"][0]["src_rect"].update(w=0)),
    ("R6", lambda d: (d["clips"][0]["src_rect"].update(x=4100),
                      d["clips"][0]["dst_rect"].update(x=4))),
    ("R7", lambda d: d["clips"][0]["dst_rect"].update(w=1024)),
    ("R8", lambda d: d["clips"][1]["dst_rect"].update(x=4096)),
    ("R9", lambda d: d["clips"][0]["src_rect"].update(x=1372 * 8 - 1024)),
    ("R10", lambda d: (d["clips"][1]["dst_rect"].update(x=1024),
                       d["clips"][1].update(unaligned_dst_reason="so R10 is what fires"))),
    ("R11", lambda d: (d["clips"][1]["dst_rect"].update(x=1024 + 2048),
                       d["act"].update(grid_w=3))),
])
def test_the_manifest_refuses(donors, doc, tmp_path, tag, mutate):
    """One rule at a time, from the tracked fixture, and the refusal must name ITS rule.

    Asserting the tag matters: a mutation can be caught by an earlier rule and the row
    would still be green, which would mean the rule under test is never exercised.
    """
    for donor, _zone in CASES:
        _need(donor)
    d = copy.deepcopy(doc)
    mutate(d)
    with pytest.raises(CM.ClipManifestError) as e:
        CM.load(_write(tmp_path, d), donor_root=donors)
    assert str(e.value).startswith(tag + " "), (tag, str(e.value))


def test_r9_is_about_the_crop_not_the_padded_grid(donors, doc, tmp_path):
    """The converted tree is PADDED up to whole sections, so a rect can be inside the
    files and still outside the level. EHZ's crop ends at tile column 1372 (10,976 px)
    inside a 6-section (12,288 px) grid; a clip in that gap reads as air the donor never
    authored, and `s2_clip_budget.clip` truncates such a rect silently instead.
    """
    for donor, _zone in CASES:
        _need(donor)
    d = copy.deepcopy(doc)
    d["clips"][0]["src_rect"] = {"x": 10240, "y": 0, "w": 2048, "h": 1024}
    with pytest.raises(CM.ClipManifestError) as e:
        CM.load(_write(tmp_path, d), donor_root=donors)
    assert str(e.value).startswith("R9 "), str(e.value)
    assert "crop" in str(e.value)


def test_r11_opt_out_is_honoured_and_recorded(donors, doc, tmp_path):
    """Finer placement stays available, and the argument for it is carried into the bake's
    clipact.json rather than living in someone's shell history."""
    for donor, _zone in CASES:
        _need(donor)
    d = copy.deepcopy(doc)
    d["act"]["grid_w"] = 3
    d["clips"][1]["dst_rect"]["x"] = 1024 + 2048
    d["clips"][1]["unaligned_dst_reason"] = "the corridor needs a half-section offset"
    act = CM.load(_write(tmp_path, d), donor_root=donors)
    assert act.clips[1].unaligned_dst_reason.startswith("the corridor")
    assert act.clips[1].as_json()["unaligned_dst_reason"] == act.clips[1].unaligned_dst_reason
    assert act.warnings == [], act.warnings        # this placement mixes no section


def test_w3_warns_but_does_not_refuse_a_mixed_section(donors, doc, tmp_path):
    """Two zones in one section is a cost, measured, not a format error — so it warns."""
    for donor, _zone in CASES:
        _need(donor)
    d = copy.deepcopy(doc)
    for c, x in zip(d["clips"], (0, 1024)):
        c["src_rect"] = dict(c["src_rect"], w=1024, h=1024)
        c["dst_rect"] = {"x": x, "y": 0, "w": 1024, "h": 1024}
        c["unaligned_dst_reason"] = "mixed-section probe"
    got = []
    act = CM.load(_write(tmp_path, d), donor_root=donors, warn=got.append)
    assert len(got) == 1 and got[0].startswith("W3 "), got
    assert act.warnings == got


def test_w1_warns_on_an_unchunked_src(donors, doc, tmp_path):
    """128-px chunk alignment is a WARNING at row 3: nothing on the art path cares. The
    row exists so that row 5, which does care, finds the hook already wired."""
    for donor, _zone in CASES:
        _need(donor)
    d = copy.deepcopy(doc)
    d["clips"][0]["src_rect"]["x"] = 4096 + 8
    d["clips"][0]["src_rect"]["w"] = 2048 - 8
    d["clips"][0]["dst_rect"]["w"] = 2048 - 8
    got = []
    CM.load(_write(tmp_path, d), donor_root=donors, warn=got.append)
    assert any(w.startswith("W1 ") for w in got), got


def test_the_ids_this_file_carries_are_ids_the_regions_document_could_carry(donors, doc, tmp_path):
    """The cross-tool half of R3, checked against the CONTRACT's pattern rather than a
    pattern retyped here.

    `empyrean:contract/schema/aurora-regions.schema.json` `$defs/region/properties/id` is
    `^[a-z][a-z0-9_]{0,31}$`, and a pasted clip becomes a region. The rule this file enforces
    is that pattern, so every act id, clip id and `region_id` write-back in a clips.json is a
    name aurora can use in the regions document without translating it. The row reads the
    contract when it can and SKIPS SAYING SO when it cannot, rather than passing on a
    hard-coded copy that could drift away from the schema it claims to mirror.
    """
    for donor, _zone in CASES:
        _need(donor)
    schema = os.path.join(os.path.dirname(REPO), "empyrean", "contract", "schema",
                          "aurora-regions.schema.json")
    if not os.path.isfile(schema):
        pytest.skip(f"the suite contract is not checked out beside this repo ({schema}), so "
                    f"the pattern CM.REGION_ID_PATTERN mirrors cannot be re-derived here")
    with open(schema) as fh:
        want = json.load(fh)["$defs"]["region"]["properties"]["id"]["pattern"]
    assert CM.REGION_ID_PATTERN == want, (CM.REGION_ID_PATTERN, want)

    act = CM.load(os.path.join(FIXTURE_DIR, "s2_two_clip", "clips.json"), donor_root=donors)
    import re as _re
    assert _re.match(want, act.id), act.id
    for cl in act.clips:
        assert _re.match(want, cl.id), cl.id
        if cl.region_id:
            assert _re.match(want, cl.region_id), cl.region_id


def test_a_clip_cannot_name_a_preset(donors, doc, tmp_path):
    """A region's palette comes from its REQUIRED `preset`, which names a record in the
    GAME's effects library — a thing no Sonic 2 zone has an opinion about. Schema 1
    therefore has no palette or preset field, and a manifest carrying one is refused rather
    than ignored: a silently-dropped field is how two tools end up disagreeing about which
    of them was supposed to decide.
    """
    for donor, _zone in CASES:
        _need(donor)
    d = copy.deepcopy(doc)
    d["clips"][0]["palette"] = "S2_Palette_EHZ"
    with pytest.raises(CM.ClipManifestError) as e:
        CM.load(_write(tmp_path, d), donor_root=donors)
    assert "preset" in str(e.value) and "palette.bin" in str(e.value), str(e.value)


def test_a_dst_rect_is_a_legal_region_rect(baked):
    """Every clip's dst_rect satisfies the contract's rect: integer world pixels, x/y >= 0,
    w/h >= 1. This file's R6 and R11 are STRICTER, which is fine — a dst_rect is a subset of
    the legal region rects, not a different shape — but it must never be looser, because the
    rectangle aurora writes into the regions document IS this one.
    """
    for name in FIXTURES:
        act, _st, _m, _v1, _v2 = baked[name]
        for cl in act.clips:
            x, y, w, h = cl.dst
            assert all(type(v) is int for v in (x, y, w, h)), cl.dst
            assert x >= 0 and y >= 0 and w >= 1 and h >= 1, cl.dst


def test_a_missing_converted_tree_says_how_to_make_one(doc, tmp_path):
    """A donor tree that is not there must name the converter, not raise FileNotFoundError
    out of a loader three files down."""
    d = copy.deepcopy(doc)
    with pytest.raises(CM.ClipManifestError) as e:
        CM.load(_write(tmp_path, d), donor_root=str(tmp_path / "nothing-here"))
    assert str(e.value).startswith("R4 ")
    assert "s2_zone_convert.py" in str(e.value)


def test_the_zone_key_is_per_zone_not_per_clip(donors, doc, tmp_path):
    """Two clips of the SAME zone share one key: they share a tileset, and two keys would
    put that zone's art in the pool twice."""
    for donor, _zone in CASES:
        _need(donor)
    d = copy.deepcopy(doc)
    d["clips"][1] = dict(d["clips"][0], id="ehz_again", region_id="ehz_again",
                         src_rect={"x": 2048, "y": 0, "w": 2048, "h": 1024},
                         dst_rect={"x": 2048, "y": 0, "w": 2048, "h": 1024})
    act = CM.load(_write(tmp_path, d), donor_root=donors)
    assert [c.zone_key for c in act.clips] == [0, 0]
    assert act.zone_table == [(S.S2_FINAL, "EHZ")]


def test_void_cells_are_not_zone_zero(baked):
    """A cell no clip covers is VOID (-1), not zone 0.

    `fg_page_order.zone_split` and `megaact_window_pageset.Act` both read -1 as "no zone";
    a void cell claiming zone 0 would put blank cells into a real zone's page group. The
    EHZ clip is 1024 px tall in a 2048-px section, so this fixture has 65,536 such cells.
    """
    _act, st, _m, _v1, _v2 = baked["s2_two_clip"]
    void = st["zone_id"] < 0
    assert int(void.sum()) == 256 * 128, int(void.sum())
    assert int((st["key"][void]).max()) == 0
