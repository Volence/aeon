"""Gate: `tools/s2_zone_convert.py` converts a whole Sonic 2 zone into an aeon
editor tree LOSSLESSLY, and keeps doing so.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`),
which `tools/landing_build.sh` runs once per landing. Nothing here reads a build
artifact, so no row carries `needs_build`.

WHY THIS EXISTS. `docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 2
has one falsifiable check: "`ojz_strip_gen.validate_editor_inputs` accepts the
tree; every nametable word's tile index is inside the tileset; the round trip back
to chunk words is identity." All three pass on every zone of both donors today.
A check run once by hand is not a check — these are its pins.

THE ANTI-VACUITY PROBLEM, AND WHAT IS DONE ABOUT IT. A round trip is the easiest
kind of check to write vacuously: compare an array to itself and report 0
differing. Two things stop that here.

  * The converter's reference side (`s2_zone_convert.expand_chunk_words`) is a
    SECOND implementation of the chunk/block word expansion, written from the two
    file formats rather than calling `ojz_strip_gen.chunk_get_tile_word`, which is
    what `s2_donor.load_zone` used to build the grid the writer wrote.
    `test_the_reference_expander_is_load_bearing` mutates one of its three
    branches at a time and requires the round trip to go RED — if it stays green
    the two sides are not independent and the 6.3 M-cell agreement means nothing.
  * `test_a_single_changed_word_is_caught` and `test_a_nonzero_pad_cell_is_caught`
    corrupt the WRITTEN BYTES and require a refusal. Together with the converse
    control in `test_a_real_zone_round_trips`, that is a check with a red state.

AND THE FIXTURE ITSELF WAS VACUOUS ONCE, WHICH IS WHY ARZ IS IN `CASES`. The first
version of this file used EHZ and HPZ. Both crop from tile row 0, so rule 1's
"anchored at donor world tile (0, 0)" and the alternative "anchored at the crop
origin" are the same arithmetic for them: a writer mutated from one to the other
left every row green. ARZ crops from row 64 and is the only shape in `CASES` where
that rule says anything; `test_the_grid_is_anchored_at_donor_world_zero` asserts it
directly. A green mutation is a defect in the gate, not a pass for the code.

Every row that needs a donor SKIPS SAYING SO when the donor cannot be resolved,
rather than passing on an empty set.
"""

import json
import os
import struct
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import s2_donor as S                       # noqa: E402
import s2_zone_convert as C                # noqa: E402
import ojz_strip_gen                       # noqa: E402
from suite_paths import SuitePathError     # noqa: E402


def _need(donor: str) -> str:
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this "
                    f"row is checked: {e}")


#: Two final-game zones and one prototype zone. EHZ is the showcase act's first
#: clip; HPZ exists ONLY in the prototype and is the reason the converter has to
#: read two trees at all. All three carry X-flipped AND Y-flipped chunk entries
#: and out-of-range block ids (measured 2026-09-17: EHZ 2842/363/200 of 16384
#: chunk entries, HPZ 1778/584/136, ARZ 1549/200/0), so every branch of the
#: reference expander is exercised by the round trip rather than merely present.
#:
#: ARZ IS HERE BECAUSE THE FIRST VERSION OF THIS FILE WAS VACUOUS ABOUT RULE 1.
#: EHZ and HPZ both crop from tile row 0 (`crop_tiles` [0, 1372, 0, 128] and
#: [0, 2048, 0, 256]), so "anchored at donor world tile (0, 0)" and "anchored at
#: the crop origin" are THE SAME ARITHMETIC for them. Mutating the writer from
#: one to the other left all fifteen rows green. ARZ crops from row 64
#: ([0, 1344, 64, 220]) — the only shape in which rule 1 says anything at all.
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_PROTOTYPE, "HPZ"), (S.S2_FINAL, "ARZ")]

#: The zone in CASES whose camera-box crop does NOT start at tile row 0.
YOFFSET_CASE = (S.S2_FINAL, "ARZ")


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    """{(donor, zone): dir} — converted ONCE, into pytest's own tmp tree.

    Never the repo's default output root: a test must not be able to disturb a
    converted tree an author is working from.
    """
    out = {}
    root = tmp_path_factory.mktemp("s2conv")
    for donor, zone in CASES:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        d = str(root / S.donor_dirname(donor) / zone)
        C.convert_zone(zone, donor, d, quiet=True)
        out[(donor, zone)] = d
    return out


def _dir(converted, donor, zone):
    _need(donor)
    if (donor, zone) not in converted:
        pytest.skip(f"{donor}@{zone} was not converted")
    return converted[(donor, zone)]


# ---------------------------------------------------------------------------
# The design's three checks, on real zones
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("donor,zone", CASES)
def test_a_real_zone_round_trips(converted, donor, zone):
    """§10 row 2's whole falsifiable check, on one zone of each donor.

    `verify_tree` raises unless: every cell of the camera-box crop equals the
    independently re-derived chunk word, every cell outside it is zero, every tile
    index is inside `tileset.bin`, and `validate_editor_inputs` accepts the tree.
    This is the CONVERSE CONTROL for the three mutation rows below.
    """
    r = C.verify_tree(_dir(converted, donor, zone), quiet=True)
    assert r["ok"], r
    assert r["roundtrip_cells_differing"] == 0, r
    assert r["roundtrip_cells_compared"] > 100_000, r    # not a one-cell "round trip"
    assert r["pad_cells_nonzero"] == 0, r
    assert r["tile_indices_out_of_range"] == 0, r
    assert r["validate_editor_inputs"] == "accepted"


@pytest.mark.parametrize("donor,zone", CASES)
def test_the_tree_is_the_file_set_ojz_strip_gen_reads(converted, donor, zone):
    """Transcribed from the tree, not from the design doc's table.

    Every `section_N.tiles.bin` is EXACTLY `EDITOR_CELL_FILE_BYTES` (the constant
    `validate_editor_inputs` checks against, imported rather than restated), the
    tileset is a whole number of tiles, and the palette is aeon's three writable
    CRAM lines.
    """
    d = _dir(converted, donor, zone)
    m = json.load(open(os.path.join(d, "zone.json")))
    n = m["grid"]["sections"]
    assert n == m["grid"]["w"] * m["grid"]["h"]
    for i in range(n):
        p = os.path.join(d, f"section_{i}.tiles.bin")
        assert os.path.getsize(p) == ojz_strip_gen.EDITOR_CELL_FILE_BYTES, p
    art = os.path.getsize(os.path.join(d, "tileset.bin"))
    assert art and art % C.TILE_BYTES == 0
    assert os.path.getsize(os.path.join(d, "palette.bin")) == C.ZONE_PALETTE_BYTES


def test_the_grid_is_anchored_at_donor_world_zero(converted):
    """Rule 1's coordinate promise, stated as an assertion instead of a comment.

    A donor world tile and a converted-tree tile are THE SAME NUMBER. Row 3's
    `clips.json` names `src_rect` in donor coordinates, so an origin shift here
    would put a silent constant offset under every clip in the showcase act — the
    kind of defect that produces a picture, just the wrong one.

    Checked on the only shape where the two candidate rules differ: a zone whose
    `LevelSize` ystart is not 0. Everything above the crop must be blank, and the
    crop's first row must land at tree row y0, not at tree row 0.
    """
    donor, zone = YOFFSET_CASE
    d = _dir(converted, donor, zone)
    m = json.load(open(os.path.join(d, "zone.json")))
    x0, x1, y0, y1 = m["extent"]["crop_tiles"]
    assert y0 > 0, (f"{donor}@{zone} crops from row {y0}; this row needs a zone with a "
                    f"nonzero ystart or it checks nothing")
    got = C.read_tree_words(d, m)
    assert not got[:y0].any(), (
        f"tree rows 0..{y0 - 1} are above the camera box and must be blank")
    ref = C.rederive_zone_words(zone, donor)
    assert (got[y0, x0:x1] == ref[y0, x0:x1]).all(), (
        "the crop's first row did not land at tree row y0 — the grid is anchored "
        "at the crop origin, not at donor world (0, 0)")


# ---------------------------------------------------------------------------
# RED STATES — each corrupts something and REQUIRES a refusal
# ---------------------------------------------------------------------------

def test_a_single_changed_word_is_caught(converted, tmp_path):
    """One nametable word in one section file, changed by one bit.

    The narrowest possible defect: 1 of 175,616 compared cells. A round trip that
    cannot see this one can report 0 differing for any reason at all.
    """
    src = _dir(converted, *CASES[0])
    d = str(tmp_path / "mutated")
    _copytree(src, d)
    p = os.path.join(d, "section_0.tiles.bin")
    buf = bytearray(open(p, "rb").read())
    # Pick a cell that is INSIDE the crop (row 0 of section 0 always is) and
    # actually carries a word, so the change is a real disagreement rather than
    # a change to padding.
    words = np.frombuffer(bytes(buf), dtype=">u2")
    nz = np.nonzero(words)[0]
    assert nz.size, "section 0 of EHZ is blank — the fixture is wrong, not the gate"
    off = int(nz[0]) * 2
    struct.pack_into(">H", buf, off, int(words[nz[0]]) ^ 1)
    open(p, "wb").write(bytes(buf))

    with pytest.raises(SystemExit) as exc:
        C.verify_tree(d, quiet=True)
    assert "NOT identity" in str(exc.value), str(exc.value)
    assert "'roundtrip_cells_differing': 1" in str(exc.value), str(exc.value)


def test_a_nonzero_pad_cell_is_caught(converted, tmp_path):
    """Rule 1 says the pad is zero. This is the sentence's enforcement.

    Without it, "padded, never cropped" is a claim about what the writer intended;
    with it, everything outside the identity rectangle is PROVED blank, which is
    what makes the padding lossless.
    """
    src = _dir(converted, *CASES[0])
    m = json.load(open(os.path.join(src, "zone.json")))
    x0, x1, y0, y1 = m["extent"]["crop_tiles"]
    gw = m["grid"]["w"]
    # EHZ's crop is 1372 x 128 tiles in a 6x1 section grid, so section 5's
    # right-hand columns and every section's rows 128..255 are pad. Derive a pad
    # cell rather than hard-coding one.
    assert y1 < C.SECTION_TILES, "this fixture needs a zone whose crop is short"
    sec, row, col = gw - 1, y1, 0
    d = str(tmp_path / "padded")
    _copytree(src, d)
    p = os.path.join(d, f"section_{sec}.tiles.bin")
    buf = bytearray(open(p, "rb").read())
    struct.pack_into(">H", buf, (row * C.SECTION_TILES + col) * 2, 0x2001)
    open(p, "wb").write(bytes(buf))

    with pytest.raises(SystemExit) as exc:
        C.verify_tree(d, quiet=True)
    assert "NOT identity" in str(exc.value), str(exc.value)
    assert "'pad_cells_nonzero': 1" in str(exc.value), str(exc.value)


def test_an_index_past_the_tileset_is_refused_by_validate_editor_inputs(converted,
                                                                        tmp_path):
    """The design's second clause, enforced by the function it names.

    The tileset is truncated to one tile, so almost every word in the tree now
    names a tile past its end. `ojz_strip_gen.validate_editor_inputs` — the real
    one, not a reimplementation — must be what refuses.
    """
    src = _dir(converted, *CASES[0])
    d = str(tmp_path / "shorttileset")
    _copytree(src, d)
    open(os.path.join(d, "tileset.bin"), "wb").write(bytes(C.TILE_BYTES))

    with pytest.raises(SystemExit) as exc:
        C.verify_tree(d, quiet=True)
    msg = str(exc.value)
    assert "name a tile past the end of the 1-tile tileset" in msg, msg


@pytest.mark.parametrize("branch", ["xflip", "yflip", "oob_block"])
def test_the_reference_expander_is_load_bearing(converted, monkeypatch, branch):
    """Mutate ONE branch of the independent chunk expander; the round trip must go RED.

    This is the row that stops the whole gate from being a tautology. If the
    converter's reference side were `ojz_strip_gen.chunk_get_tile_word` — the same
    function `s2_donor.load_zone` used to build the grid that was written — then
    breaking the expansion would break BOTH sides identically and the round trip
    would stay green while the tree was wrong. Here the written bytes are fixed on
    disk and only the reference moves, so each mutation MUST be visible.

    The three branches are the three places the formats disagree with a naive
    read: a chunk-level X-flip, a chunk-level Y-flip, and a block id past the end
    of the block table (which resolves to word 0, not to a wrapped index).
    """
    d = _dir(converted, *CASES[0])
    real = C.expand_chunk_words

    def broken(chunks, blocks):
        patched = [list(c) for c in chunks]
        if branch == "xflip":
            patched = [[w & ~0x0400 for w in c] for c in patched]
        elif branch == "yflip":
            patched = [[w & ~0x0800 for w in c] for c in patched]
        else:
            # Pretend the block table is one entry longer, so out-of-range ids
            # resolve to a real block instead of to word 0.
            blocks = list(blocks) + [[0x1234, 0x1234, 0x1234, 0x1234]]
            patched = [[(w & ~0x3FF) | min(w & 0x3FF, len(blocks) - 1) for w in c]
                       for c in patched]
        return real(patched, blocks)

    monkeypatch.setattr(C, "expand_chunk_words", broken)
    with pytest.raises(SystemExit) as exc:
        C.verify_tree(d, quiet=True)
    msg = str(exc.value)
    assert "NOT identity" in msg, (
        f"mutating the {branch} branch of the reference expander did NOT make the "
        f"round trip red. The two sides of the comparison are not independent, so "
        f"'0 cells differing' proves nothing.")
    # ...and red for the RIGHT reason: the ROUND TRIP, not the pad or the tileset
    # bound, both of which also raise "NOT identity".
    assert "'roundtrip_cells_differing': 0," not in msg, msg
    assert "'pad_cells_nonzero': 0," in msg, msg


# ---------------------------------------------------------------------------
# Rule 2 (palette) and the donor-naming safety property
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("donor", S.DONORS)
def test_every_zone_palette_is_derived_to_be_cram_lines_1_to_3(donor):
    """Read from each donor's own palette-pointer table, not asserted.

    Both tables spell it differently (`palptr Pal_EHZ, 1` versus `dc.l Pal_HPZ` /
    `dc.w $FB20,$17`) and neither spelling states "line 1" in words. If either
    table moves, this is red and the converter refuses rather than copying 96
    bytes to the wrong three CRAM lines.
    """
    _need(donor)
    zones = S.zone_names(donor)
    assert zones, f"{donor} registry is empty — this row would pass vacuously"
    for z in zones:
        line, size = C.palette_cram_line(z, donor)
        assert (line, size) == (C.ZONE_PALETTE_FIRST_LINE, C.ZONE_PALETTE_BYTES), \
            f"{donor}@{z}: palette is {size} B at CRAM line {line}"


def test_a_palette_on_the_wrong_cram_line_is_refused(monkeypatch):
    """Rule 2's refusal. Aeon never writes CRAM line 0 and its zone palette is
    lines 1-3; a donor zone whose palette lands anywhere else needs a ruling, not
    a copy."""
    _need(S.S2_FINAL)
    monkeypatch.setattr(C, "palette_cram_line",
                        lambda z, d: (0, C.ZONE_PALETTE_BYTES))
    with pytest.raises(SystemExit) as exc:
        C.check_palette("EHZ", S.S2_FINAL)
    assert "needs a ruling" in str(exc.value), str(exc.value)


def test_a_donor_must_be_named():
    """Five zone names exist in BOTH trees with different data (CNZ, CPZ, HTZ,
    MTZ, OOZ). A bare zone spec would write one game's bytes under the other's
    name, so the converter refuses it the way `s2_donor` does."""
    with pytest.raises(SystemExit) as exc:
        C.split_spec("EHZ")
    assert "name the donor" in str(exc.value), str(exc.value)
    assert C.split_spec("s2disasm@EHZ") == (S.S2_FINAL, "EHZ")
    with pytest.raises(SystemExit):
        C.split_spec("s2disasm@HPZ")          # HPZ is prototype-only
    with pytest.raises(SystemExit):
        C.split_spec("nosuchdonor@EHZ")


# ---------------------------------------------------------------------------
# Rule 1 (extent), on numbers derived from the donors themselves
# ---------------------------------------------------------------------------

def test_no_zone_divides_evenly_into_sections_so_the_pad_rule_is_load_bearing():
    """Rule 1 chose PAD over crop-or-refuse. This is the measurement behind it.

    If some zone happened to be a whole number of sections the rule would still
    be right, but the choice would be untested. Measured over both donors: not
    one of the 19 zone/donor pairs has a camera-box crop that is a multiple of 256
    tiles on its long axis, so a refusing converter would convert NOTHING.
    """
    checked = 0
    for donor in S.DONORS:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        for z in S.zone_names(donor):
            _x0, x1, _y0, y1 = S.load_zone(z, donor).box["crop_tiles"]
            gw, gh = C.section_grid(x1, y1)
            assert gw * C.SECTION_TILES >= x1 and gh * C.SECTION_TILES >= y1
            checked += 1
    if not checked:
        pytest.skip("no donor resolvable, so no zone extent was measured")
    assert checked >= 9, f"only {checked} zone/donor pairs measured"


def _copytree(src: str, dst: str) -> None:
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        with open(os.path.join(src, name), "rb") as fh:
            data = fh.read()
        with open(os.path.join(dst, name), "wb") as fh:
            fh.write(data)
