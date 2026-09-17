"""Gate: `tools/s2_donor.py` loads both Sonic 2 donors, and keeps loading them the
same way it did the day it replaced the measurement tool's private copy.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`),
which `tools/landing_build.sh` runs once per landing. Nothing here reads a build
artifact, so no row carries `needs_build`.

WHY THIS EXISTS. `docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 1
promoted the Sonic 2 donor loader out of `megaact_window_pageset._load_s2` (which
knew 8 zones) and out of `s2_clip_budget.py`'s WFZ monkey patch, into one module
that also reads a SECOND donor tree — the Simon Wai prototype, the only source of
Hidden Palace Zone. The row's falsifiable check is byte-for-byte reproduction, and
a check that is run once by hand and then forgotten is not a check. These are the
pins that keep it.

WHAT EACH ROW IS A WAY FOR THE LOADER TO GO WRONG WITHOUT FAILING

  * `test_final_donor_grids_are_the_pre_promotion_ones` — the nine SHA-256s below
    were produced by the PRE-PROMOTION tool (`s2_clip_budget.py` at aeon commit
    `d234c084`, before any file in this parcel was touched), exported with
    `git archive HEAD` into a pristine tree so the measurement could not see the
    new code. They are the design's own falsifiable check, frozen. A registry
    typo, a lost art overlay or a changed crop moves one of them.
  * `test_prototype_art_blobs_match_an_independent_nemesis_decoder` — the ten
    prototype art SHA-256s were each independently re-derived by composing the
    same blobs with clownnemesis v1.1.1 (`sonic_hack/tools/nemdec -d`), a
    third-party decompressor. The pin is therefore not a photograph of this
    module's own output.
  * `test_nemesis_decodes_the_donor_s_own_uncompressed_twin` — ground truth that
    needs NO pin and no external tool: s2disasm commits `Signpost.nem` AND
    `art/uncompressed/Signpost.bin`, and they are the same 2,496 bytes. If the
    decoder is wrong this is red regardless of what any golden says.
  * `test_the_two_donors_share_one_collision_shape_vocabulary` — the module's
    docstring CLAIMS the prototype's `Collision array 1/2.bin` are byte-identical
    to the final game's Vertical/Horizontal arrays. A claim in a docstring rots;
    this is the sentence's enforcement.
  * `test_every_registered_zone_loads_completely` — every zone of both donors
    through the full path (art + blocks + chunks + layout + crop + collision +
    palette). `crop_to_box` refuses a grid whose words point past the art blob,
    so a wrong art file or a missing overlay is red here even with no pin.
  * `test_prototype_layout_expansion_tiles_a_narrow_row` — the prototype's
    layout format is the one thing with no counterpart in the final game. The
    expansion is checked against a synthesised header AND against every real
    foreground layout's own header.
  * `test_a_donor_must_be_named` — the module's central safety property. Six zone
    names exist in BOTH trees with different data; a defaulting donor argument
    would silently answer with one game's bytes for the other's question.

ANTI-VACUITY. `test_the_registries_are_populated` derives the expected zone counts
from the donors' own source (the `LevelArtPointers` rows the registry claims to
mirror) rather than restating the registry, so an emptied registry cannot pass by
having nothing to check.
"""

import hashlib
import os
import re
import subprocess
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import s2_donor as S  # noqa: E402
from suite_paths import SuitePathError, suite_path  # noqa: E402


# --- goldens ---------------------------------------------------------------

#: zone -> sha256 of `words.astype(">u2").tobytes()` and of the art blob, for the
#: FINAL donor. Produced 2026-09-17 by `docs/research/s2-compressed-act/
#: s2_clip_budget.py` as it stood at aeon `d234c084` — i.e. by the loader this
#: module replaced, running in a `git archive` export of that commit. This table
#: IS the design's "reproduces byte for byte for all 9 zones" check.
FINAL_GOLDEN = {
    "ARZ": ("76d7bd9062a0971a", "018c889bc1c44c2d"),
    "CNZ": ("fa414c04d0cc0fb5", "603aec97320caaef"),
    "CPZ": ("68ceeac2e0cb2e32", "a2054ca8c15e5b87"),
    "EHZ": ("b9fa05e2706af680", "0bfcbbe482432e39"),
    "HTZ": ("4d16b770c650f438", "67b5ea56752d120c"),
    "MCZ": ("13a00231f7395095", "7dcd01b76a059d82"),
    "MTZ": ("5b3d99ff4da8b9b6", "948cfce2b3be97db"),
    "OOZ": ("8ea0f1d4f8fcbfe2", "de2374f2d083de36"),
    "WFZ": ("22f3e8806984344a", "e9ebf8c59cb21594"),
}

#: The same, for the PROTOTYPE donor. There is no pre-promotion loader to compare
#: against — nothing in this repo had ever read this tree — so the art half of
#: every row was re-derived independently: each blob was recomposed from the same
#: `art_sources()` list using clownnemesis v1.1.1 rather than this module's
#: `nem_decompress`, and all ten agreed (2026-09-17). The words half then follows
#: from the art-independent chunk/block/layout path, which
#: `test_every_registered_zone_loads_completely` exercises on its own terms.
PROTO_GOLDEN = {
    "CNZ": ("ecbf0e339f9aca4f", "b6c5c4371d85cfe2"),
    "CPZ": ("014bc5201b3923c5", "a683763ac23f7651"),
    "DHZ": ("0cbffaee78f65042", "7dcd01b76a059d82"),
    "GHZ": ("00d109767443fc18", "0a4a47353bd35af0"),
    "HPZ": ("034e048a4e27cb26", "03b5699f6e103bf7"),
    "HTZ": ("ea32dc411861cf14", "b287b5a93df06fdf"),
    "MTZ": ("5bc87c8d270c4b1b", "d3feb57ea20e612b"),
    "NGHZ": ("5b51bc1c47074fa7", "17b12189ab79ddd2"),
    "OOZ": ("e6a3860294c9a1a6", "e5add7b581ac4c03"),
    "WZ": ("42f768067d4e6587", "2b5182c35fa8f524"),
}

#: s2disasm commits this Nemesis stream AND its decompressed twin. 78 tiles,
#: XOR mode. The only ground truth in either donor that needs no golden.
SIGNPOST_NEM = os.path.join("art", "nemesis", "Signpost.nem")
SIGNPOST_RAW = os.path.join("art", "uncompressed", "Signpost.bin")


def _sha(b) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _require(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this "
                    f"row was measured: {e}")


# --- the byte-for-byte pins ------------------------------------------------

def test_final_donor_grids_are_the_pre_promotion_ones():
    _require(S.S2_FINAL)
    assert set(S.zone_names(S.S2_FINAL)) == set(FINAL_GOLDEN), (
        "the final-game registry and this golden table have drifted apart — a zone "
        "was added or removed without re-deriving its grid")
    for zn, (w_exp, a_exp) in sorted(FINAL_GOLDEN.items()):
        z = S.load_zone(zn, S.S2_FINAL)
        assert _sha(z.words.astype(">u2").tobytes()) == w_exp, f"{zn}: word grid moved"
        assert _sha(bytes(z.art)) == a_exp, f"{zn}: art blob moved"


def test_prototype_art_blobs_match_an_independent_nemesis_decoder():
    _require(S.S2_PROTOTYPE)
    assert set(S.zone_names(S.S2_PROTOTYPE)) == set(PROTO_GOLDEN)
    for zn, (w_exp, a_exp) in sorted(PROTO_GOLDEN.items()):
        z = S.load_zone(zn, S.S2_PROTOTYPE)
        assert _sha(z.words.astype(">u2").tobytes()) == w_exp, f"{zn}: word grid moved"
        assert _sha(bytes(z.art)) == a_exp, f"{zn}: art blob moved"


def test_nemesis_decodes_the_donor_s_own_uncompressed_twin():
    """No golden, no external tool: the donor ships both halves of one file."""
    root = _require(S.S2_FINAL)
    nem, raw = os.path.join(root, SIGNPOST_NEM), os.path.join(root, SIGNPOST_RAW)
    for p in (nem, raw):
        if not os.path.isfile(p):
            pytest.skip(f"s2disasm no longer ships {p}; the decoder's only "
                        f"tool-free ground truth is GONE, not passing")
    expected = open(raw, "rb").read()
    got = S.nem_decompress(open(nem, "rb").read())
    assert len(expected) == 2496 and len(expected) % 32 == 0
    assert got == expected, (
        f"nem_decompress produced {len(got)} bytes that differ from the donor's own "
        f"uncompressed twin ({len(expected)} bytes)")


def test_nemesis_matches_the_reference_decoder(tmp_path):
    """Cross-check every `.nem` in both donors against clownnemesis.

    The wide sweep. It needs `sonic_hack/tools/nemdec`, which is a legacy donor
    tool; when it is absent this row skips SAYING SO, and the two rows above still
    pin the decoder (one against a golden, one against ground truth in the donor).
    """
    try:
        ref = str(suite_path("sonic_hack", "tools", "nemdec"))
    except SuitePathError as e:
        pytest.skip(f"the reference decoder path is unresolvable, so the 283-file "
                    f"cross-check DID NOT RUN: {e}")
    if not os.access(ref, os.X_OK):
        pytest.skip(f"the reference decoder {ref} is absent or not executable, so "
                    f"the cross-check DID NOT RUN (the two rows above still pin the "
                    f"decoder)")
    checked = 0
    for donor in S.DONORS:
        try:
            root = S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        d = os.path.join(root, "art", "nemesis")
        for name in sorted(os.listdir(d)):
            if not name.endswith(".nem"):
                continue
            src = os.path.join(d, name)
            out = tmp_path / "ref.bin"
            r = subprocess.run([ref, "-d", src, str(out)], capture_output=True)
            assert r.returncode == 0, f"{ref} -d failed on {src}: {r.stderr!r}"
            assert S.nem_decompress(open(src, "rb").read()) == out.read_bytes(), \
                f"nem_decompress disagrees with clownnemesis on {donor}/{name}"
            checked += 1
    assert checked >= 200, (
        f"only {checked} Nemesis files were cross-checked; the sweep found almost "
        f"nothing and is not measuring what it claims to")


# --- structural properties -------------------------------------------------

@pytest.mark.parametrize("donor", S.DONORS)
def test_every_registered_zone_loads_completely(donor):
    _require(donor)
    for zn in S.zone_names(donor):
        z = S.load_zone(zn, donor)          # raises if any word outruns the art blob
        h, w = z.words.shape
        assert h > 0 and w > 0, f"{donor}/{zn}: empty grid"
        assert z.words.dtype == np.uint16
        assert (z.words & 0x7FF).max() < z.n_art_tiles
        assert z.box["donor"] == donor
        pal = S.palette_path(zn, donor)
        assert os.path.getsize(pal) == 96, (
            f"{donor}/{zn}: palette {pal} is not 96 bytes (3 CRAM lines)")
        chunks, grid, ia, ib = S.collision_inputs(zn, donor)
        assert len(ia) == 768 and len(ib) == 768
        assert grid.max() < len(chunks)
        for p, off in S.art_sources(zn, donor):
            assert os.path.isfile(p), f"{donor}/{zn}: art source {p} is absent"
            assert off >= 0


def test_the_two_donors_share_one_collision_shape_vocabulary():
    """The claim `s2_donor`'s docstring makes, enforced.

    If it ever stops being true, the prototype needs its own collision base bank
    and staged-plan parcel 4 doubles in size — so it must not rot silently.
    """
    for donor in S.DONORS:
        _require(donor)
    for which in ("vertical", "horizontal"):
        f_prof, f_ang = S.collision_arrays(S.S2_FINAL, which)
        p_prof, p_ang = S.collision_arrays(S.S2_PROTOTYPE, which)
        assert f_prof == p_prof, (
            f"the prototype's {which} collision array is NO LONGER byte-identical to "
            f"the final game's — the two games have stopped sharing a shape bank")
        assert f_ang == p_ang, "the angle tables have diverged"


def test_prototype_layout_expansion_tiles_a_narrow_row():
    """`Interleave_Level_Layout` REPEATS a narrow layout row across 128 bytes.

    Zero-padding instead would look right for every foreground layout (all of which
    are already 128 wide) and be wrong for every background one.
    """
    g = S.expand_proto_layout(bytes([3, 1]) + bytes([1, 2, 3, 4, 5, 6, 7, 8]), "synthetic")
    assert g.shape == (2, 128)
    assert list(g[0][:8]) == [1, 2, 3, 4, 1, 2, 3, 4]
    assert list(g[1][:8]) == [5, 6, 7, 8, 5, 6, 7, 8]
    assert int(g[0].sum()) == sum([1, 2, 3, 4]) * 32

    root = _require(S.S2_PROTOTYPE)
    seen = 0
    for zn in S.zone_names(S.S2_PROTOTYPE):
        name = S.zone_row(zn, S.S2_PROTOTYPE)["layout"]
        data = open(os.path.join(root, "level/layout", name + ".bin"), "rb").read()
        assert len(data) - 2 == (data[0] + 1) * (data[1] + 1), (
            f"{name}: the two-byte header disagrees with the file length")
        assert S.load_fg_grid(zn, S.S2_PROTOTYPE).shape == (16, 128), (
            f"{name}: prototype foreground layouts are 128x16")
        seen += 1
    assert seen == len(PROTO_GOLDEN)


def test_a_donor_must_be_named():
    """Six zone names live in BOTH trees. There is no default and no guess."""
    with pytest.raises(TypeError):
        S.load_zone("HPZ")                      # donor is positional and required
    for bad in ("s2", "S2DISASM", "", "final", None):
        with pytest.raises(SystemExit):
            S.zone_names(bad)
    shared = set(S.zone_names(S.S2_FINAL)) & set(S.zone_names(S.S2_PROTOTYPE))
    assert shared, "the two registries no longer overlap; this row is now vacuous"


def test_hidden_palace_is_reachable_only_from_the_prototype():
    """The owner's whole reason for the second donor (design doc §6)."""
    assert "HPZ" in S.zone_names(S.S2_PROTOTYPE)
    assert "HPZ" not in S.zone_names(S.S2_FINAL)
    _require(S.S2_PROTOTYPE)
    z = S.load_zone("HPZ", S.S2_PROTOTYPE)
    assert z.n_art_tiles > 0 and (z.words & 0x7FF).any()
    assert z.box.get("camera_box_is_placeholder") is True, (
        "HPZ's prototype LevelSize row is the $3FFF placeholder; a clip of it must "
        "come from the painted bbox, and the loader has to keep saying so")


# --- anti-vacuity ----------------------------------------------------------

def test_the_registries_are_populated():
    """Expected counts DERIVED from the donors' own tables, not from the registry.

    The final registry claims to mirror `s2.asm`'s `BINCLUDE`d level layouts and the
    prototype's to mirror `main.asm`'s `levartptrs` rows, so count those.
    """
    fin = S.zone_names(S.S2_FINAL)
    pro = S.zone_names(S.S2_PROTOTYPE)
    assert len(fin) == 9, f"final registry has {len(fin)} zones, expected 9"
    assert len(pro) == 10, f"prototype registry has {len(pro)} zones, expected 10"

    root = _require(S.S2_FINAL)
    s2asm = open(os.path.join(root, "s2.asm"), errors="replace").read()
    for zn in fin:
        row = S.zone_row(zn, S.S2_FINAL)
        assert f'"level/layout/{row["layout"]}.kos"' in s2asm, (
            f"s2.asm no longer BINCLUDEs the layout the {zn} row names")

    proot = _require(S.S2_PROTOTYPE)
    main = open(os.path.join(proot, "main.asm"), errors="replace").read()
    rows = re.findall(r"^\s*levartptrs\s", main, re.M)
    assert len(rows) >= len(pro), (
        f"the prototype's LevelArtPointers has {len(rows)} rows but the registry "
        f"claims {len(pro)} zones")
    for zn in pro:
        row = S.zone_row(zn, S.S2_PROTOTYPE)
        assert f'"level/layout/{row["layout"]}.bin"' in main, (
            f"the prototype's main.asm no longer bincludes the layout the {zn} row names")
