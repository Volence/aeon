"""Gate: a Sonic 2 clip's COLLISION reaches `collattr.bin` meaning what it meant in the
donor, and the act's attr-set cost is the number the design predicts.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact, so no
row carries `needs_build`, and nothing here touches the shipped act, the S&K bank or
`games/sonic4/data/editor/ojz/act1`.

WHY THIS EXISTS. `docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 5: "run
`bake_cell` over the clip's chunk words, emit both plane files", checked by "the attr-set
entry count for a given clip matches `s2_clip_budget.py`'s prediction for that rectangle,
and the bake refuses a clip that cuts a crossover pair". Both halves are pinned below.

THE ANTI-VACUITY PROBLEM HERE, and it is worse than row 3's, because the interesting data
does not exist:

  * A CONVERTED SONIC 2 TREE HAS NO CROSSOVER MARKS AT ALL. It cannot: the donor's
    chunk-entry word has no crossover field, its bits 15:14 are path-B solidity, so
    `chunk_entry_to_plane_words` emits XOVER_NONE for every cell. A C1 row run against
    the real fixtures would pass while refusing nothing. Every C1 row therefore PAINTS
    marks into a converted tree first — which is exactly what an author does in aurora —
    and `test_a_converted_tree_has_no_marks_to_begin_with` is the control that proves the
    painting is what makes the difference.
  * SO DOES $18. No showcase zone references the one shape `rotate_profile` refuses, so
    C3 is painted in too, and `test_the_showcase_zones_do_not_need_18` records that the
    quiet state is quiet for a reason and will fail if that stops being true.
  * AN ATTR-SET AGREEMENT COULD BE A TAUTOLOGY. It is not: the predictor
    (`s2_clip_budget.collision_entries`) runs `bake_cell` over donor chunk words and never
    opens a clips.json, a converted tree or a plane file, while the bake reads plane words
    off disk through `bake_plane_cell`. `test_the_transcode_is_exactly_bake_cell` is what
    licenses comparing them, and it is proven over every distinct chunk word of the six
    showcase zones rather than a sample.
  * A REFUSAL ROW CAN PASS BY RAISING FOR THE WRONG REASON. Every refusal row asserts the
    rule's own tag (C1, C2, C3, R12) is in the message.

Every row that needs a donor SKIPS SAYING SO when the donor cannot be resolved, rather
than passing on an empty set.
"""

import json
import os
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_act_bake as BAKE                # noqa: E402
import clip_manifest as CM                  # noqa: E402
import collision_pipeline as CP             # noqa: E402
import import_s2_collision as IS2           # noqa: E402
import ojz_strip_gen                        # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)

#: The two zones the tracked fixtures clip.
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ")]

#: The owner's six showcase zones — the population the transcode row sweeps.
THE_SIX = C.THE_SIX

FIXTURE_DIR = os.path.join(REPO, "games", "sonic4", "data", "clips")

#: The design's measurement tool, named as the FILE (a bare directory literal is a docs
#: path `tools/land_gate.py` would need its own CHECKED rule for; see row 3's note).
BUDGET_TOOL = os.path.join(REPO, "docs", "research", "s2-compressed-act", "s2_clip_budget.py")

#: (fixture id, clip id) -> the `s2_clip_budget.py collision` spec naming the SAME
#: rectangle. NOT a copied count: the row runs the tool and compares. The spec is derived
#: from the fixture's own src_rect by `_spec_for` and asserted to match this table, so a
#: fixture whose rectangle moves fails here instead of silently comparing the wrong thing.
CLIP_SPECS = {
    ("s2_two_clip", "ehz_s2"): "EHZ:2,1",
    ("s2_two_clip", "cpz_s2"): "CPZ:2,1",
    ("s2_two_clip_pins", "ehz_s1"): "EHZ:1,1",
    ("s2_two_clip_pins", "cpz_s1"): "CPZ:1,1",
}


def _need(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")


@pytest.fixture(autouse=True, scope="module")
def no_working_tree_donors():
    """NO row here may read the repo's own converted donor trees — see
    `tools/test_clip_manifest.py`'s fixture of the same name for the incident."""
    real = CM.DEFAULT_DONOR_ROOT
    CM.DEFAULT_DONOR_ROOT = os.path.join(
        REPO, "tools", "__no_donor_root_for_tests__", "this-path-must-not-exist")
    assert not os.path.exists(CM.DEFAULT_DONOR_ROOT)
    yield
    CM.DEFAULT_DONOR_ROOT = real


@pytest.fixture(scope="module")
def donors(tmp_path_factory):
    """A converted donor root holding CASES, in pytest's own tmp tree."""
    root = str(tmp_path_factory.mktemp("s2colldonors"))
    for donor, zone in CASES:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


@pytest.fixture(scope="module")
def baked(donors, tmp_path_factory):
    """{fixture id: (ClipAct, state, clipact.json, v1, v2)} for both tracked fixtures."""
    for donor, _zone in CASES:
        _need(donor)
    out = {}
    root = tmp_path_factory.mktemp("s2collbake")
    for name in sorted({n for n, _c in CLIP_SPECS}):
        src = os.path.join(FIXTURE_DIR, name, "clips.json")
        out[name] = BAKE.bake(src, out_dir=str(root / name), donor_root=donors, log=None)
    return out


@pytest.fixture(scope="module")
def bank():
    """(profiles, angles) of the S2 base bank the converted trees name."""
    return ojz_strip_gen.load_base_bank(IS2.default_out())


def _budget():
    sys.path.insert(0, os.path.dirname(BUDGET_TOOL))
    import s2_clip_budget as SB              # noqa: E402
    return SB


def _spec_for(clip):
    """The `ZONE:s0,n` spec naming this clip's source rectangle, DERIVED from the rect.

    Only meaningful for a section-aligned, full-height clip — which is what the tracked
    fixtures are, and what the row asserts before comparing. `s2_clip_budget`'s collision
    spec has no vertical extent, so a clip that does not cover its zone's whole grid
    height is a different rectangle and must not be compared this way.
    """
    sec_px = CM.geometry_constants()["SECTION_SIZE"]
    assert clip.src[0] % sec_px == 0 and clip.src[2] % sec_px == 0, clip.src
    return f"{clip.zone}:{clip.src[0] // sec_px},{clip.src[2] // sec_px}"


# ---------------------------------------------------------------------------
# The transcode — what licenses comparing the two sides at all
# ---------------------------------------------------------------------------

def test_the_transcode_is_exactly_bake_cell(bank):
    """`chunk_entry_to_plane_words` + `bake_plane_cell` == `bake_cell`, every word.

    THE LOAD-BEARING ROW. The whole of row 5 is the claim that a donor chunk word can be
    split into two aurora plane words without changing what the engine sees. If that is
    true then the design's predictor (which runs `bake_cell` from the donor side) and this
    bake (which runs `bake_plane_cell` over bytes on disk) are measuring the same thing,
    and every agreement below means something. If it is false, they are two tools agreeing
    about nothing.

    The population is every distinct (chunk word, index_a, index_b) triple the six
    showcase zones reference — a triple and not a word, because the block-id -> shape
    indirection is per zone and two zones can give one word two meanings.
    """
    profiles, angles = bank
    triples, seen = [], set()
    for donor, zone in THE_SIX:
        _need(donor)
        chunks, grid, ia, ib = S.collision_inputs(zone, donor)
        for ci in sorted(set(np.unique(grid).tolist())):
            if ci < len(chunks):
                for w in chunks[ci]:
                    k = (w, ia, ib)
                    if k not in seen:
                        seen.add(k)
                        triples.append(k)
    assert len(triples) > 1000, len(triples)        # not a two-word "sweep"

    ref = CP.AttrSet(cap=None)
    got = CP.AttrSet(cap=None)
    mismatched = 0
    for w, ia, ib in triples:
        ea, eb = CP.bake_cell(w, ia, ib, profiles, angles, ref)
        pa, pb = CP.chunk_entry_to_plane_words(w, ia, ib)
        ga = CP.bake_plane_cell(pa, profiles, angles, got)
        gb = CP.bake_plane_cell(pb, profiles, angles, got)
        if (ea, eb) != (ga, gb):
            mismatched += 1
    assert mismatched == 0, f"{mismatched} of {len(triples)} triples disagree"
    # not just the same indices — the same SET, in the same intern order
    assert ref.entries == got.entries
    assert len(ref.entries) > 100, len(ref.entries)  # the sweep found real geometry


def test_the_vectorised_expansion_matches_the_scalar_definition():
    """`expand_collision_words`' numpy agrees with the scalar transcode, cell for cell.

    The two are written from the same paragraph and could share a misreading of it, but
    they cannot share a transposition, an off-by-one in the 2x repeat, or a row/column
    swap — which is what this row is for. Sampled over a real zone at a fixed seed.
    """
    donor, zone = CASES[0]
    _need(donor)
    pa, pb = C.rederive_zone_collision(zone, donor)
    rng = np.random.default_rng(0x5CA1AB1E)
    n = 0
    for _ in range(400):
        r = int(rng.integers(0, min(pa.shape[0], 256)))
        c = int(rng.integers(0, pa.shape[1]))
        assert C.reference_collision_cell(zone, donor, r, c) == (int(pa[r, c]), int(pb[r, c])), \
            (r, c)
        n += 1
    assert n == 400
    # and the grids are not trivially all-zero, which would make every comparison pass
    assert np.count_nonzero(pa) > 10_000, int(np.count_nonzero(pa))


# ---------------------------------------------------------------------------
# The converted tree
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c[0]}@{c[1]}")
def test_a_converted_tree_carries_both_planes_crop_masked(donors, case):
    """Both plane files exist at the right size, and the pad outside the crop is air.

    The pad matters: a nonzero collision cell outside the camera-box crop is invisible
    solid ground, and the art converter's own "the pad is zero" claim (verify_tree B)
    would stop covering the tree if collision did not obey it too.
    """
    donor, zone = case
    _need(donor)
    d = os.path.join(donors, donor, zone)
    m = json.load(open(os.path.join(d, "zone.json")))
    n = m["grid"]["sections"]
    want = CM.geometry_constants()["SECTION_SIZE"] // CM.TILE_PX       # 256 cells per section side
    for i in range(n):
        for suffix in ("collattr", "collattrb"):
            p = os.path.join(d, f"section_{i}.{suffix}.bin")
            assert os.path.isfile(p), p
            assert os.path.getsize(p) == want * want * 2, p
    x0, x1, y0, y1 = m["extent"]["crop_tiles"]
    pa = CM.section_plane_grid(d, m, want, "collattr")
    pb = CM.section_plane_grid(d, m, want, "collattrb")
    mask = np.zeros(pa.shape, dtype=bool)
    mask[y0:y1, x0:x1] = True
    assert int(np.count_nonzero(pa[~mask]) + np.count_nonzero(pb[~mask])) == 0
    assert int(np.count_nonzero(pa[mask])) > 1000       # the crop is not empty either


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c[0]}@{c[1]}")
def test_a_converted_tree_names_the_s2_bank_and_pins_it(donors, case):
    """`zone.json` names `base_s2/`, not the S&K bank, and the sha is that bank's.

    The same 10-bit index is a different shape in the two banks (parcel 4: 68 of the 151
    shapes these zones use are unreachable from S&K's under any flip), so a tree that
    named the wrong one would bake plausible-looking wrong ground.
    """
    import hashlib
    donor, zone = case
    _need(donor)
    m = json.load(open(os.path.join(donors, donor, zone, "zone.json")))
    coll = m["collision"]
    assert coll["base_bank"].endswith("base_s2"), coll["base_bank"]
    assert "collision/base" != coll["base_bank"]
    committed = open(os.path.join(REPO, coll["base_bank"], "heightmaps.bin"), "rb").read()
    assert coll["base_bank_heightmaps_sha256"] == hashlib.sha256(committed).hexdigest()
    # and it is genuinely a different bank from the shipped act's
    sk = open(os.path.join(ojz_strip_gen.SK_BANK_DIR, "heightmaps.bin"), "rb").read()
    assert sk != committed


def test_load_base_bank_with_no_argument_is_still_the_shipped_bank():
    """The parameter row 5 added must not have moved the default.

    `ojz_strip_gen.generate()` calls `load_base_bank()` with no argument and writes the
    ROM's collision tables from what it returns, so this is the row that says no ROM byte
    can have moved because of the bank parameter.
    """
    default_hm, default_an = ojz_strip_gen.load_base_bank()
    sk_hm = open(os.path.join(ojz_strip_gen.SK_BANK_DIR, "heightmaps.bin"), "rb").read()
    sk_an = open(os.path.join(ojz_strip_gen.SK_BANK_DIR, "angles.bin"), "rb").read()
    assert default_hm == sk_hm and default_an == sk_an
    s2_hm, _ = ojz_strip_gen.load_base_bank(IS2.default_out())
    assert s2_hm != default_hm          # the parameter reaches a different bank


# ---------------------------------------------------------------------------
# THE ROW-5 CHECK, FIRST HALF: predicted == emitted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(CLIP_SPECS), ids=lambda k: f"{k[0]}:{k[1]}")
def test_a_clips_attr_cost_is_what_the_design_predicts(baked, key):
    """§10 row 5's check, per clip. The bake's count for a clip equals
    `s2_clip_budget.py collision <ZONE>:<s0>,<n>` for the same rectangle.

    The two sides share the shape bank and nothing else: the predictor slices the donor's
    chunk grid and runs `bake_cell`; the bake reassembles a converted tree's plane files
    and runs `bake_plane_cell` over the clip's destination rectangle. The spec is DERIVED
    from the fixture's own rect, so a fixture that moves fails here rather than being
    compared against a stale spec.
    """
    name, clip_id = key
    _need(S.S2_FINAL)
    act, _st, m, _v1, _v2 = baked[name]
    clip = next(c for c in act.clips if c.id == clip_id)
    spec = _spec_for(clip)
    assert spec == CLIP_SPECS[key], (spec, CLIP_SPECS[key])
    # the comparison is only valid for a clip covering its zone's whole grid height
    _chunks, grid, _a, _b = S.collision_inputs(clip.zone, clip.donor)
    assert clip.src[1] == 0 and clip.src[3] >= 0
    predicted = _budget().collision_entries([spec], clip.donor)
    row = next(r for r in m["collision"]["per_clip"] if r["clip"] == clip_id)
    assert row["attr_entries_alone"] == predicted, (clip_id, row, predicted)
    assert predicted > 0
    assert row["solid_cells"] > 1000, row       # the clip has real ground in it


@pytest.mark.parametrize("name", sorted({n for n, _c in CLIP_SPECS}))
def test_the_acts_attr_cost_is_what_the_design_predicts(baked, name):
    """The same check for the ACT: the union of the clips' entries, one attr set.

    This is the number §3.5 caps at 255 and the one that decides whether a set of
    marquees is bakeable, so it is checked as its own claim and not inferred from the
    per-clip rows — the union is not the sum (207 against 95 + 148).
    """
    _need(S.S2_FINAL)
    act, _st, m, _v1, _v2 = baked[name]
    specs = [_spec_for(c) for c in act.clips]
    predicted = _budget().collision_entries(specs, S.S2_FINAL)
    assert m["collision"]["attr_entries"] == predicted, (name, m["collision"], predicted)
    assert predicted < sum(r["attr_entries_alone"] for r in m["collision"]["per_clip"])


@pytest.mark.parametrize("name", sorted({n for n, _c in CLIP_SPECS}))
def test_the_emitted_planes_recount_to_what_was_composed(baked, name):
    """N2 for the collision half: the count decoded back off the emitted files.

    A difference between this and the composed count is the EMISSION — a wrong slice, a
    wrong endianness, a section written twice — because the interning is the same code
    on both sides. `bake` already refuses on a mismatch; this row pins that the manifest
    records both numbers so a future reader can see it was checked.
    """
    _need(S.S2_FINAL)
    _act, _st, m, _v1, _v2 = baked[name]
    assert m["collision"]["attr_entries_at_recount"] == m["collision"]["attr_entries"]
    assert m["collision"]["attr_entries"] <= m["collision"]["cap"] == CP.AttrSet.CAP


@pytest.mark.parametrize("name", sorted({n for n, _c in CLIP_SPECS}))
def test_the_emitted_plane_cells_are_the_donors_own_geometry(baked, donors, name):
    """Spot-check the bytes, not only the count: a cell of the act resolves to the same
    attr as the donor cell it was clipped from.

    A count can be right while the rectangle is transposed or offset — every cell would
    still come from the same zone. This walks the clip's destination cells back to their
    source cells through the manifest's own src/dst and compares the attr byte the engine
    would see, via the scalar `reference_collision_cell` which shares no code with either
    the emitter or the count.
    """
    _need(S.S2_FINAL)
    act, _st, _m, _v1, _v2 = baked[name]
    profiles, angles = ojz_strip_gen.load_base_bank(
        CM.collision_banks(act, donors))
    pa, pb = CM.collision_grids(act, donors)
    rng = np.random.default_rng(0xC11FACE1)
    checked = 0
    for cl in act.clips:
        sx, sy, sw, sh = (v // CM.TILE_PX for v in cl.src)
        dx, dy = cl.dst[0] // CM.TILE_PX, cl.dst[1] // CM.TILE_PX
        for _ in range(120):
            r = int(rng.integers(0, sh))
            c = int(rng.integers(0, sw))
            want = C.reference_collision_cell(cl.zone, cl.donor, sy + r, sx + c)
            got = (int(pa[dy + r, dx + c]), int(pb[dy + r, dx + c]))
            assert got == want, (cl.id, r, c, got, want)
            checked += 1
    assert checked == 120 * len(act.clips)
    # anti-vacuity: the sample is not all air
    assert int(np.count_nonzero((pa >> CP.PLANE_SOL_SHIFT) & 3)) > 1000


# ---------------------------------------------------------------------------
# THE ROW-5 CHECK, SECOND HALF: the crossover refusal (C1)
# ---------------------------------------------------------------------------

def _paint(tree_dir, manifest, section_tiles, suffix, cells):
    """Write cell words into a converted tree's plane file. `cells` = {(row, col): word}.

    This is what an author does in aurora, done from a test: a converted Sonic 2 tree has
    no crossover marks and no $18, so every refusal row below has to make its own subject.
    """
    gw = manifest["grid"]["w"]
    by_section = {}
    for (r, c), w in cells.items():
        n = (r // section_tiles) * gw + (c // section_tiles)
        by_section.setdefault(n, []).append(
            (r % section_tiles, c % section_tiles, w))
    for n, items in by_section.items():
        p = os.path.join(tree_dir, f"section_{n}.{suffix}.bin")
        g = np.frombuffer(open(p, "rb").read(), dtype=">u2").reshape(
            section_tiles, section_tiles).copy()
        for r, c, w in items:
            g[r, c] = w
        open(p, "wb").write(g.astype(">u2").tobytes())


@pytest.fixture
def paintable(donors, tmp_path):
    """A private copy of the EHZ tree a row may paint into, plus its manifest."""
    import shutil
    donor, zone = CASES[0]
    _need(donor)
    root = str(tmp_path / "donors")
    dst = os.path.join(root, donor, zone)
    shutil.copytree(os.path.join(donors, donor, zone), dst)
    m = json.load(open(os.path.join(dst, "zone.json")))
    return root, dst, m, CM.geometry_constants()["SECTION_SIZE"] // CM.TILE_PX


def _one_clip_doc(src, dst=(0, 0), **extra):
    """A one-clip manifest over EHZ with the given source rect."""
    clip = {"id": "ehz_cut", "donor": S.S2_FINAL, "zone": "EHZ",
            "src_rect": dict(zip(("x", "y", "w", "h"), src)),
            "dst_rect": {"x": dst[0], "y": dst[1], "w": src[2], "h": src[3]}}
    clip.update(extra)
    return {"schema": 1, "units": "world_px", "id": "xover_cut",
            "act": {"grid_w": 1, "grid_h": 1}, "clips": [clip]}


def _bake_doc(tmp_path, doc, root, name="clips.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return BAKE.bake(str(p), out_dir=str(tmp_path / "baked"), donor_root=root, log=None)


def test_a_converted_tree_has_no_marks_to_begin_with(donors):
    """THE CONTROL for every C1 row: the subject does not exist until a row paints it.

    If this ever fails, the C1 rows below stopped being about painting and this file's
    anti-vacuity argument stopped holding. The reason it holds is structural: the donor
    chunk word's bits 15:14 are path-B SOLIDITY, so there is no crossover field to
    convert and `chunk_entry_to_plane_words` writes XOVER_NONE unconditionally.
    """
    donor, zone = CASES[0]
    _need(donor)
    d = os.path.join(donors, donor, zone)
    m = json.load(open(os.path.join(d, "zone.json")))
    st = CM.geometry_constants()["SECTION_SIZE"] // CM.TILE_PX
    total = 0
    for suffix in ("collattr", "collattrb"):
        g = CM.section_plane_grid(d, m, st, suffix)
        total += int(BAKE.crossover_marks(g).sum())
        assert g.size > 100_000                  # it did read a real grid
    assert total == 0
    assert m["collision"]["crossover_marks"] == 0


def test_a_clip_that_severs_a_crossover_is_refused(paintable, tmp_path):
    """C1: marks inside the rectangle, marks left outside it -> REFUSED.

    The §2.3 case, painted: the loop's two crossings are two bands of one column (that is
    what the shipped act's eight paired indices are), and the marquee takes the lower band
    and leaves the upper one. The mark that survives sends the player to plane B; nothing
    sends them back.
    """
    root, dst, m, st = paintable
    # bottom-centre band inside the clip, top-centre band outside it. Both inside EHZ's
    # camera-box crop (tile rows 0..128), or R9 would refuse the rect before C1 is reached.
    inside = {(40, 100): 0x8000, (41, 100): 0x8000}
    outside = {(100, 100): 0x8000}
    _paint(dst, m, st, "collattr", {**inside, **outside})
    _paint(dst, m, st, "collattrb", {k: 0x4000 for k in {**inside, **outside}})
    doc = _one_clip_doc((0, 0, 2048, 512))         # covers tile row 40, not row 100
    with pytest.raises(BAKE.ClipCollisionError) as e:
        _bake_doc(tmp_path, doc, root)
    assert "C1" in str(e.value), str(e.value)
    assert "ehz_cut" in str(e.value)


def test_a_clip_that_keeps_every_mark_is_accepted(paintable, tmp_path):
    """The DISCRIMINATING control for C1. Same painted marks, same bake, one rectangle
    that takes ALL of them — and it must pass.

    Without this row C1 could be "refuse any clip of a tree that has marks anywhere", or
    for that matter "refuse everything", and the row above would not notice.
    """
    root, dst, m, st = paintable
    cells = {(40, 100): 0x8000, (41, 100): 0x8000, (100, 100): 0x8000}
    _paint(dst, m, st, "collattr", cells)
    _paint(dst, m, st, "collattrb", {k: 0x4000 for k in cells})
    doc = _one_clip_doc((0, 0, 2048, 1024))        # covers tile rows 40 AND 100
    _act, _s, man, _v1, _v2 = _bake_doc(tmp_path, doc, root)
    row = man["collision"]["per_clip"][0]
    assert row["marks_inside_src"] == 6           # 3 cells x 2 planes
    assert row["marks_outside_src"] == 0


def test_the_c1_opt_out_is_honoured_and_recorded(paintable, tmp_path):
    """An in-file `severed_xover_reason` lets the clip through, and the reason is carried
    into `clipact.json` where the next reader of the bake sees it.

    C1 is conservative on purpose — the encoding says which PLANE a mark points at, never
    which LOOP it belongs to — so refusing a clip that leaves an unrelated loop behind is
    a real false positive and needs an escape hatch in R11's style.
    """
    root, dst, m, st = paintable
    _paint(dst, m, st, "collattr", {(40, 100): 0x8000, (100, 100): 0x8000})
    _paint(dst, m, st, "collattrb", {(40, 100): 0x4000, (100, 100): 0x4000})
    doc = _one_clip_doc((0, 0, 2048, 512),
                        severed_xover_reason="the upper band is a different loop")
    _act, _s, man, _v1, _v2 = _bake_doc(tmp_path, doc, root)
    row = man["collision"]["per_clip"][0]
    assert row["marks_inside_src"] == 2 and row["marks_outside_src"] == 2
    assert row["severed_xover_reason"] == "the upper band is a different loop"
    assert man["clips"][0]["severed_xover_reason"] == row["severed_xover_reason"]


# ---------------------------------------------------------------------------
# C2 — the 255 cap, and C3 — the profile emit_tables cannot rotate
# ---------------------------------------------------------------------------

def test_an_act_over_the_attr_cap_is_refused_with_the_number(paintable, tmp_path):
    """C2: §3.5's cap as a refusal that says HOW FAR over, and by which clip.

    The threshold is read from `AttrSet.CAP` rather than typed, and the subject is
    painted: the tracked fixtures are 207 and 191, and the most expensive pair of real
    zones available here (EHZ + CPZ whole) is 220, so nothing on this gate's data reaches
    255 by itself. Painting CAP + 1 distinct solid shapes into one section is a synthetic
    act that genuinely needs more entries than one byte can address.
    """
    root, dst, m, st = paintable
    cap = CP.AttrSet.CAP
    profiles, _angles = ojz_strip_gen.load_base_bank(IS2.default_out())
    # Only shapes the ROTATION accepts: C3 runs before the cap check, and a row that
    # tripped it instead would be green for the wrong reason. Derived from the bank.
    ok = []
    for shape in range(1, CP.MAX_PROFILES):
        h = profiles[shape * CP.PROFILE_LEN:(shape + 1) * CP.PROFILE_LEN]
        try:
            CP.rotate_profile(h)
        except ValueError:
            continue
        ok.append(shape)
    cells, i = {}, 0
    for sol in (CP.SOL_ALL, CP.SOL_TOP, CP.SOL_LRB):
        for shape in ok:
            cells[(i // 200, i % 200)] = shape | (sol << CP.PLANE_SOL_SHIFT)
            i += 1
    assert i > cap + 8, i
    _paint(dst, m, st, "collattr", cells)
    doc = _one_clip_doc((0, 0, 2048, 1024))
    with pytest.raises(BAKE.ClipCollisionError) as e:
        _bake_doc(tmp_path, doc, root)
    msg = str(e.value)
    assert "C2" in msg, msg
    assert str(cap) in msg and "Over by" in msg


def test_a_profile_emit_tables_cannot_rotate_is_refused_at_the_clip(paintable, tmp_path):
    """C3: the $18 tripwire, fired at the clip instead of four layers down in the bake.

    `emit_tables` rotates every attr-set entry through the UNRULED `rotate_profile` and
    that call is deliberately still there (see `check_rotatable`'s note). This row proves
    the clip-level detection fires on the same condition, and
    `test_the_unruled_rotate_profile_is_still_the_one_emit_tables_calls` proves the
    tripwire it is standing in front of was not quietly disarmed.
    """
    root, dst, m, st = paintable
    _paint(dst, m, st, "collattr", {(10, 10): 0x18 | (CP.SOL_ALL << CP.PLANE_SOL_SHIFT)})
    doc = _one_clip_doc((0, 0, 2048, 1024))
    with pytest.raises(BAKE.ClipCollisionError) as e:
        _bake_doc(tmp_path, doc, root)
    assert "C3" in str(e.value), str(e.value)
    assert "rotate_profile" in str(e.value)


def test_the_unruled_rotate_profile_is_still_the_one_emit_tables_calls(bank):
    """Row 5's DECISION, pinned: `emit_tables` keeps raising, it was not silenced.

    Parcel 4 left `emit_tables` calling the unruled `rotate_profile` as a live tripwire
    for the shipping act and said turning it into a silent value was not its call. Row 5's
    answer is to leave it exactly as it is and move the DETECTION earlier (C3). If someone
    later routes `rotate_profile_ruled` into `emit_tables`, this row fails and the argument
    gets made in the open.
    """
    profiles, _angles = bank
    heights = profiles[0x18 * CP.PROFILE_LEN:0x19 * CP.PROFILE_LEN]
    with pytest.raises(ValueError):
        CP.rotate_profile(heights)
    s = CP.AttrSet()
    s.intern(heights, 0, CP.SOL_ALL, CP.XOVER_NONE)
    with pytest.raises(ValueError):
        CP.emit_tables(s)


def test_a_shape_past_the_end_of_the_bank_is_refused_by_name(bank):
    """`bake_plane_cell` R3, found by row 5 while painting a synthetic over-cap act.

    The cell word gives the shape 10 bits and a bank holds 256 entries, so an authored
    word can name one that is not there. It used to slice past the end and intern a
    ZERO-LENGTH profile, which `emit_tables` met as a bare `IndexError: index out of
    range` from inside `rotate_profile` naming neither the cell nor the shape nor the
    bank. The guard is byte-neutral for the shipping act — measured, not assumed, by the
    control below.
    """
    profiles, angles = bank
    n = len(profiles) // CP.PROFILE_LEN
    word = n | (CP.SOL_ALL << CP.PLANE_SOL_SHIFT)
    with pytest.raises(ValueError) as e:
        CP.bake_plane_cell(word, profiles, angles, CP.AttrSet())
    assert "base_s2" in str(e.value) and str(n) in str(e.value)
    # the last IN-range shape still bakes, so the boundary is the boundary
    CP.bake_plane_cell((n - 1) | (CP.SOL_ALL << CP.PLANE_SOL_SHIFT),
                       profiles, angles, CP.AttrSet())


def test_no_committed_plane_file_names_a_shape_past_its_bank():
    """The CONTROL for the row above: R3 cannot have changed what the shipped act bakes.

    Every committed editor plane file, every SOLID cell, highest shape index. If this ever
    reaches 256 the new refusal would start firing on a real bake, and this is what says
    so before the build does.
    """
    import glob
    highest = -1
    files = sorted(glob.glob(os.path.join(
        REPO, "games", "sonic4", "data", "editor", "*", "*", "section_*.collattr*.bin")))
    assert files, "no committed editor plane files matched — this row measured nothing"
    for p in files:
        g = np.frombuffer(open(p, "rb").read(), dtype=">u2")
        solid = ((g >> CP.PLANE_SOL_SHIFT) & 3) != 0
        if solid.any():
            highest = max(highest, int((g[solid] & CP.BLOCK_ID_MASK).max()))
    assert 0 <= highest < CP.MAX_PROFILES, highest


def test_the_showcase_zones_do_not_need_18(bank):
    """The reason C3 is quiet on real data, recorded so it fails if it stops being true.

    Parcel 4 ruled $18 as a completeness question rather than a gameplay one BECAUSE no
    showcase zone references it. If a zone list change makes that false, the decision to
    leave `emit_tables` raising has to be revisited, and this is what says so.
    """
    profiles, angles = bank
    used = set()
    for donor, zone in THE_SIX:
        _need(donor)
        chunks, grid, ia, ib = S.collision_inputs(zone, donor)
        for ci in sorted(set(np.unique(grid).tolist())):
            if ci < len(chunks):
                for w in chunks[ci]:
                    for pw in CP.chunk_entry_to_plane_words(w, ia, ib):
                        if (pw >> CP.PLANE_SOL_SHIFT) & 3:
                            used.add(pw & CP.BLOCK_ID_MASK)
    assert len(used) > 50, len(used)            # the sweep found real shapes
    assert 0x18 not in used
    # and $18 IS in the bank — the absence is the zones' doing, not a hole in the bank
    assert any(profiles[0x18 * CP.PROFILE_LEN:0x19 * CP.PROFILE_LEN])


# ---------------------------------------------------------------------------
# R12 — W1's ruling
# ---------------------------------------------------------------------------

def test_a_paste_that_shifts_collision_off_the_16px_grid_is_refused(donors, tmp_path):
    """R12: (dst - src) must be a multiple of 16 in both axes.

    DERIVED from `probe_core`'s `andi.w #$F, d0` on the world x, not from either file
    format. The failure it prevents is silent — the art, one word per 8-px cell, moves
    correctly while every collision probe reads the wrong half of a profile.
    """
    _need(S.S2_FINAL)
    for bad_src, axis in (((8, 0, 2048, 1024), "x"), ((0, 8, 2048, 1016), "y")):
        doc = _one_clip_doc(bad_src)
        p = tmp_path / f"bad_{axis}.json"
        p.write_text(json.dumps(doc))
        with pytest.raises(CM.ClipManifestError) as e:
            CM.load(str(p), donor_root=donors)
        assert "R12" in str(e.value), str(e.value)


def test_a_16px_shift_is_accepted_even_when_it_is_not_128px_aligned(donors, tmp_path):
    """W1's premise, falsified as a passing row.

    W1 warned that a src rect off the 128-px chunk grid would bite collision. It does not:
    a chunk is 8x8 independent block placements, so the quantum is the BLOCK. This clip is
    16-px aligned and deliberately NOT 128-px aligned, and it must load clean with no
    warning about chunk alignment.
    """
    _need(S.S2_FINAL)
    doc = _one_clip_doc((16, 16, 2032, 1008), dst=(0, 0))
    doc["clips"][0]["unaligned_dst_reason"] = None
    p = tmp_path / "ok.json"
    p.write_text(json.dumps(doc))
    act = CM.load(str(p), donor_root=donors)
    assert all(v % 128 for v in (act.clips[0].src[0], act.clips[0].src[1]))
    assert not any("W1" in w for w in act.warnings), act.warnings


def test_w1_is_gone_from_the_rule_vocabulary():
    """The retired tag is not silently reused, and its replacement is documented.

    A warning tag that disappears from the code but stays in a reader's head is how two
    people end up meaning different things by "W1". The header keeps the tag reserved with
    its false premise recorded; nothing may raise or warn with it.
    """
    src = open(os.path.join(TOOLS, "clip_manifest.py"), encoding="utf-8").read()
    header, _, body = src.partition('"""\n\nimport json')
    assert body, "the module docstring's end moved; this row is reading the wrong half"
    # the header keeps the retired tag with its false premise recorded...
    assert "W1" in header and "RETIRED" in header
    # ...and no message anywhere may still be tagged with it. The tag form is `W1 clip`
    # / `W1 {path}` — the same shape every other rule's message uses — so this looks for
    # the tag as it would be EMITTED, which prose naming it ("W1's replacement") is not.
    for tag in ('"W1 ', "'W1 ", '"W1:', "W1 clip", "W1 act"):
        assert tag not in body, f"{tag!r} still appears below the header"
    assert "R12 clip" in body, "R12, W1's replacement, does not fire"
    # and it is a REFUSAL, not another warning
    assert "R12" in body.split("def load(")[1].split("raise ClipManifestError")[0] or \
        "R12" in body


# ---------------------------------------------------------------------------
# The tree contract
# ---------------------------------------------------------------------------

def test_a_row2_era_tree_without_collision_is_refused_by_name(donors, tmp_path):
    """A tree converted before row 5 has no plane files, and the bake says so with the
    command that fixes it instead of an IsADirectoryError four frames down."""
    import shutil
    _need(S.S2_FINAL)
    root = str(tmp_path / "old")
    dst = os.path.join(root, S.S2_FINAL, "EHZ")
    shutil.copytree(os.path.join(donors, S.S2_FINAL, "EHZ"), dst)
    for f in os.listdir(dst):
        if "collattr" in f:
            os.remove(os.path.join(dst, f))
    doc = _one_clip_doc((0, 0, 2048, 1024))
    p = tmp_path / "clips.json"
    p.write_text(json.dumps(doc))
    with pytest.raises(CM.ClipManifestError) as e:
        BAKE.bake(str(p), out_dir=str(tmp_path / "baked"), donor_root=root, log=None)
    assert "s2_zone_convert" in str(e.value), str(e.value)


def test_one_act_names_one_collision_bank(baked, donors):
    """`collision_banks` resolves to a single bank, and it is the S2 one.

    An act has ONE attr set and a shape index inside it means one shape, so two banks in
    one act would make the same index mean two. Nothing can produce that today — both S2
    donors share one shape vocabulary byte for byte — which is why this is a row and not
    a paragraph: it is the assertion that would fail first if that stopped being true.
    """
    _need(S.S2_FINAL)
    for name in sorted({n for n, _c in CLIP_SPECS}):
        act, _st, m, _v1, _v2 = baked[name]
        assert CM.collision_banks(act, donors) == os.path.join(REPO, m["collision"]["base_bank"])
        assert m["collision"]["base_bank"].endswith("base_s2")


def test_the_shipped_act_and_the_sk_bank_are_not_touched_by_any_of_this():
    """Row 5 moves no shipping byte, asserted rather than asserted-about.

    Nothing in this parcel writes into `games/sonic4/data/editor/ojz/act1`,
    `games/sonic4/data/collision/base/` or the act's own tables, and the bake writes only
    into the output directory it is given. This row is cheap insurance that a future edit
    to these tools does not quietly gain a second output.
    """
    import hashlib
    for p in ("games/sonic4/data/collision/base/heightmaps.bin",
              "games/sonic4/data/collision/heightmaps.bin",
              "games/sonic4/data/editor/ojz/act1/section_0.collattr.bin"):
        full = os.path.join(REPO, p)
        assert os.path.isfile(full), p
    # the committed S2 bank is what the importer produces (parcel 4's row asserts this
    # too; repeated here because row 5 is the first thing that READS it for a bake)
    hm = open(os.path.join(IS2.default_out(), "heightmaps.bin"), "rb").read()
    assert len(hm) == CP.MAX_PROFILES * CP.PROFILE_LEN
    assert hashlib.sha256(hm).hexdigest() != hashlib.sha256(
        open(os.path.join(ojz_strip_gen.SK_BANK_DIR, "heightmaps.bin"), "rb").read()).hexdigest()
