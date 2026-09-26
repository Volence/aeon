"""Gate: `tools/import_s2_collision.py` — the Sonic 2 collision base bank.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`),
which `tools/landing_build.sh` runs once per landing. Nothing here reads a build
artifact, so no row carries `needs_build`. Nothing here reads anything under
`docs/`, deliberately: a test that reads `docs/research/s2-compressed-act/` has to be
named in that path's `tools/land_gate.py` rule, and this parcel does not edit that
file.

WHY THIS EXISTS. `docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 4 gives
the bank two falsifiable checks — every shape round-trips through `rotate_profile` with
no raise, and a slope's height and angle match the donor's own `FindFloor` — and a
check run once by hand is not a check. These are the pins that keep them.

WHAT EACH ROW IS A WAY FOR THE BANK TO GO WRONG WITHOUT FAILING

  * `test_the_rotated_table_is_not_the_donors` — the whole reason the importer is not
    a copy of `import_sk_collision.py`. S2 and aeon read the sign of a partial wall row
    the OPPOSITE way round (S2 `+w` = right-anchored, aeon `+w` = left-anchored), so a
    copied rotated array mirrors the solid side of every partial wall row and a wall
    solid on the left of a cell pushes from the right. That failure is silent: the ROM
    builds, the act loads, and Sonic is pushed out of the wrong side of a slope. The
    row asserts BOTH halves — the committed table is not the donor's bytes, AND it is
    what the rule produces.
  * `test_the_two_conventions_decode_to_the_same_geometry` — the constructive form of
    the same claim, and the one that could show the regeneration LOSING something.
    Decoding each row of both arrays to a set of solid columns and comparing each
    against the vertical array's own coverage cannot pass by agreeing with the wrong
    reference, because the vertical array is a third, independent witness.
  * `test_aeon_and_s2_lookups_agree_on_every_chunk_word` — §10 row 4's second check,
    widened from "a hand-picked slope" to every distinct chunk word of all six showcase
    zones, both sensor classes. The reference side is a line-for-line transcription of
    `s2.asm` `FindFloor`/`FindFloor2`, not a restatement of aeon.
  * `test_the_solidity_class_gate_is_exercised` — ANTI-VACUITY for the row above. The
    check's aeon side originally omitted `probe_core`'s `and.b d6,d0` class gate and
    disagreed on 158,442 probes; the danger now is the reverse, a donor with no
    class-asymmetric cells, where the gate would be untested and a future regression
    invisible. This row proves the population contains them.
  * `test_shape_18_ruling_reproduces_the_donors_own_answer` — the ruling, asserted
    against S2's OWN shipped row for `$18` rather than a hand-typed pin: the rule's
    output must equal that row transcribed into aeon's inverted convention.
  * `test_only_shape_18_needs_the_ruling` — the ruling is an exception, not a policy.
    If a second shape starts taking it, the rule is being used to paper over a decoding
    bug and somebody must look.
  * `test_a_multi_run_row_still_raises` — the ruling must not have swallowed the OTHER
    refusal. There is no defensible single byte for a row with two solid runs.
  * `test_the_importer_does_not_write_the_shipping_tables` — the same trap
    `test_import_sk_collision.py` records: an importer that defaults into the repo
    dirties tracked build inputs and makes the ROM diverge from the frozen goldens.
    This one must never touch `collision/` or `collision/base/` at all.
  * `test_defaults_resolve_at_call_time` — parcel 3 shipped two rows that errored on a
    checkout with no converted donor trees because a default was bound at import time.
    This is that class, pinned.
  * `test_the_bank_serves_the_prototype_donor_too` — Hidden Palace comes from the Simon
    Wai tree, and one bank has to serve both. The row re-derives the shared-vocabulary
    claim rather than citing it.

ANTI-VACUITY GENERALLY. Every count below is compared against a population the row
also asserts is non-empty, so an importer that produced nothing cannot pass by having
nothing to check.
"""

import os
import shutil
import subprocess
import sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import collision_pipeline as CP  # noqa: E402
import import_s2_collision as I  # noqa: E402
import s2_donor as S  # noqa: E402
from suite_paths import SuitePathError  # noqa: E402

ROW = I.ROW
REPO = os.path.normpath(os.path.join(TOOLS, ".."))
BANK = os.path.join(REPO, "games", "sonic4", "data", "collision", "base_s2")

#: Re-derived 2026-09-17 by this parcel, from the donor trees and the S&K bank.
#: The design doc's prose says 75 for the second figure; it does not reproduce (see
#: the parcel report). The METHOD is in check_reach() and is re-run by the row that
#: reads these, so they are pins on two fixed donor trees, not copies of prose.
EXPECTED_USED_SHAPES = 151
EXPECTED_UNREACHABLE_FROM_SK = 68

#: 211 of the 255 shapes `rotate_profile` can answer disagree with the donor's shipped
#: rotated array; 212 of 256 once the RULED $18 is counted, which is what check_sign
#: reports because it uses rotate_profile_ruled.
EXPECTED_SIGN_DIFFER = 212
EXPECTED_SIGN_IDENTICAL = 44


def _require(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row "
                    f"was measured: {e}")


def _require_sk():
    try:
        return I._sk_bank()
    except (SystemExit, SuitePathError, OSError) as e:
        pytest.skip(f"the skdisasm donor could not be resolved, so the S&K side of "
                    f"this row was not measured: {e}")


def _require_bank():
    p = os.path.join(BANK, "heightmaps.bin")
    if not os.path.isfile(p):
        pytest.fail(f"the committed S2 base bank is missing at {p} — this row measures "
                    f"the ARTIFACT, and its absence is a failure, not a skip "
                    f"(regenerate: python3 tools/import_s2_collision.py build)")
    return BANK


def _read(name):
    with open(os.path.join(_require_bank(), name), "rb") as f:
        return f.read()


# --- the bank itself -------------------------------------------------------

def test_the_bank_is_the_donors_vertical_array_and_angles():
    _require(S.S2_FINAL)
    vert, ang = S.collision_arrays(S.S2_FINAL, "vertical")
    assert _read("heightmaps.bin") == vert
    assert _read("angles.bin") == ang
    assert len(vert) == I.SHAPES * ROW and len(ang) == I.SHAPES


def test_the_rotated_table_is_not_the_donors():
    """S2's horizontal array must NEVER be copied in — the sign conventions invert."""
    _require(S.S2_FINAL)
    horiz, _ = S.collision_arrays(S.S2_FINAL, "horizontal")
    committed = _read("heightmaps_rot.bin")
    assert committed != horiz, (
        "the committed rotated table IS the donor's horizontal array — every "
        "partial-width wall row now has its solid side mirrored")

    vert, _ = S.collision_arrays(S.S2_FINAL, "vertical")
    rebuilt = bytearray(I.SHAPES * ROW)
    for i in range(I.SHAPES):
        rot, _ruled = I.rotate_profile_ruled(vert[i * ROW:(i + 1) * ROW])
        rebuilt[i * ROW:(i + 1) * ROW] = rot
    assert committed == bytes(rebuilt), (
        "the committed rotated table is not what the rule produces from heightmaps.bin")


def test_solidity_is_all_except_air():
    hm, sol = _read("heightmaps.bin"), _read("solidity.bin")
    assert len(sol) == I.SHAPES
    solid = 0
    for i in range(I.SHAPES):
        air = (i == 0) or not any(hm[i * ROW:(i + 1) * ROW])
        assert sol[i] == (0 if air else I.SOLID_ALL), f"shape {i}: solidity {sol[i]}"
        solid += 0 if air else 1
    assert solid > 200, f"only {solid} solid shapes — the bank did not load"


def test_no_crossover_table_is_written(tmp_path):
    """The fifth table, crossover.bin, is retired with the painted crossover marks
    (LINES-EVERYWHERE, 2026-09-26): the importer writes exactly the four collision tables."""
    _require(S.S2_FINAL)
    I.build(out=str(tmp_path), quiet=True)
    assert sorted(os.listdir(str(tmp_path))) == ["angles.bin", "heightmaps.bin",
                                                 "heightmaps_rot.bin", "solidity.bin"]


# --- §10 row 4, check one: the round trip ----------------------------------

def test_all_256_shapes_round_trip_with_no_raise():
    _require(S.S2_FINAL)
    _require_bank()
    r = I.check_roundtrip()
    assert r["bad"] == [], r["bad"]
    assert r["raised"] == 0
    assert r["ok"] == r["shapes"] == I.SHAPES
    assert r["ruled"] == 1, (
        f"{r['ruled']} shapes took the centred-run ruling, expected exactly 1 ($18)")


def test_only_shape_18_needs_the_ruling():
    _require(S.S2_FINAL)
    r = I.check_sign()
    assert set(r["ruled"]) == {0x18}, (
        f"the centred-run ruling fired for {sorted(hex(k) for k in r['ruled'])}; it is "
        f"an exception for one shape, and a second one means a decoding bug is being "
        f"papered over")
    assert r["ruled"][0x18] == list(range(14)), r["ruled"][0x18]


def test_shape_18_ruling_reproduces_the_donors_own_answer():
    """The ruling, DERIVED: S2's own shipped row for $18, transcribed into aeon's
    inverted sign convention, must be exactly what the rule produces.

    S2's row is [2,2,4,4,...,16,16] — the run's WIDTH at each row, positive, which in
    S2's convention (FindWall2 loc_1EA78) means right-anchored. Aeon spells a
    right-anchored run of width w as (256-w). A full row (16) carries no sign either
    way and transcribes to itself.
    """
    _require(S.S2_FINAL)
    vert, _ = S.collision_arrays(S.S2_FINAL, "vertical")
    horiz, _ = S.collision_arrays(S.S2_FINAL, "horizontal")
    s2_row = horiz[0x18 * ROW:(0x18 + 1) * ROW]
    transcribed = bytes(b if b in (0, 16) else (256 - b) & 0xFF for b in s2_row)

    ruled, rows = I.rotate_profile_ruled(vert[0x18 * ROW:(0x18 + 1) * ROW])
    assert rows, "shape $18 no longer needs the ruling — the fixture has changed"
    assert ruled == transcribed, (
        f"the ruling no longer agrees with the donor's own answer for $18:\n"
        f"  rule       {list(ruled)}\n  S2 (transcribed) {list(transcribed)}")
    assert ruled == _read("heightmaps_rot.bin")[0x18 * ROW:(0x18 + 1) * ROW]


def test_a_multi_run_row_still_raises():
    """The ruling covers a CENTRED single run. A row with two runs has no defensible
    single byte and must still refuse — the S2 bank contains none, so this is the only
    way to keep that refusal alive."""
    # Two solid runs at row 15: columns 0-1 and 14-15 solid to the bottom, a gap between.
    heights = bytes([1, 1] + [0] * 12 + [1, 1])
    with pytest.raises(ValueError, match="solid runs"):
        I.rotate_profile_ruled(heights)


# --- §10 row 4, check two: against the donor's own lookup ------------------

def test_aeon_and_s2_lookups_agree_on_every_chunk_word():
    for _zone, donor in I.SHOWCASE_ZONES:
        _require(donor)
    r = I.check_findfloor()
    assert r["probes"] > 1_000_000, (
        f"only {r['probes']} probes — the sweep did not load the zones")
    assert r["kind_mismatch"] == 0, r["examples"]
    assert r["angle_mismatch"] == 0, r["examples"]
    assert r["dist_mismatch"] == 0, r["examples"]


def test_the_solidity_class_gate_is_exercised():
    """ANTI-VACUITY for the row above: the donor must actually contain cells solid for
    one sensor class and not the other, or the gate that broke the check once is
    untested and a regression in it is invisible."""
    _require(S.S2_FINAL)
    chunks, _g, ia, _ib = S.collision_inputs("EHZ", S.S2_FINAL)
    asym = 0
    for ch in chunks:
        for w in ch:
            if (w & 0x3FF) == 0 or ia[w & 0x3FF] == 0:
                continue
            sol = (w >> CP.PATH_A_SOL_SHIFT) & 3
            if sol in (CP.SOL_TOP, CP.SOL_LRB):
                asym += 1
    assert asym > 0, (
        "no chunk word in EHZ is solid for exactly one sensor class, so the class gate "
        "in check_findfloor is never exercised and its 0 mismatches mean nothing")


def test_every_probe_exit_is_populated():
    """ANTI-VACUITY: all three of S2's exits must occur for both classes, or the sweep
    is agreeing about air."""
    for _zone, donor in I.SHOWCASE_ZONES:
        _require(donor)
    r = I.check_findfloor()
    for label, _bit, _mask in I.SENSOR_CLASSES:
        for kind in (I.AIR_FWD, I.FULL_BACK, I.SURFACE):
            assert r["per_kind"].get((label, kind), 0) > 1000, (
                f"exit {kind!r} for the {label} sensor occurred "
                f"{r['per_kind'].get((label, kind), 0)} times — not a measured result")


# --- the sign finding, pinned ----------------------------------------------

def test_the_sign_disagreement_is_total_and_pure():
    _require(S.S2_FINAL)
    r = I.check_sign()
    assert r["other"] == 0, (
        f"{r['other']} shapes differ from the donor's rotated array in a way that is "
        f"NOT a sign swap — the disagreement is no longer a pure convention "
        f"difference and the regeneration may be losing geometry")
    assert (r["identical"], r["differ"]) == (EXPECTED_SIGN_IDENTICAL,
                                            EXPECTED_SIGN_DIFFER)
    assert r["pure_sign"] == EXPECTED_SIGN_DIFFER
    assert r["s2_pos_aeon_neg"] > 0 and r["s2_neg_aeon_pos"] > 0, (
        "the disagreement runs in only one direction, which would make it a bug in one "
        "bank rather than an inverted convention")


def test_the_two_conventions_decode_to_the_same_geometry():
    """The constructive form: both arrays, decoded to solid-column sets under their own
    conventions, must agree with EACH OTHER and with the vertical array's own coverage.
    The vertical array is a third witness, so this cannot pass by agreeing with the
    wrong reference."""
    _require(S.S2_FINAL)
    r = I.check_sign()
    assert r["rows_disagree"] == 0
    assert r["truth_mismatch"] == [], r["truth_mismatch"][:10]
    assert r["rows_agree"] > 3000, f"only {r['rows_agree']} rows compared"


# --- the reachability finding, pinned --------------------------------------

def test_the_act_needs_shapes_the_sk_bank_cannot_express():
    _require(S.S2_FINAL)
    _require(S.S2_PROTOTYPE)
    _require_sk()
    r = I.check_reach()
    assert r["closure"] > 500, f"S&K flip closure is {r['closure']} — bank not loaded"
    assert r["used"] == EXPECTED_USED_SHAPES
    assert r["unreachable"] == EXPECTED_UNREACHABLE_FROM_SK
    assert r["shape_18_used_by"] == [], (
        "shape $18 is now referenced by a showcase zone, so its ruling has moved from "
        "a completeness question to a gameplay one and needs re-reading")


def test_the_bank_serves_the_prototype_donor_too():
    """Hidden Palace comes from the Simon Wai tree; one bank has to serve both donors.
    Re-derived here rather than cited: the two trees' shape vocabularies must be
    byte-identical, or HPZ's collision indices name shapes this bank does not hold."""
    _require(S.S2_FINAL)
    _require(S.S2_PROTOTYPE)
    for which in ("vertical", "horizontal"):
        a = S.collision_arrays(S.S2_FINAL, which)
        b = S.collision_arrays(S.S2_PROTOTYPE, which)
        assert a == b, f"the donors' {which} arrays or angle tables differ"

    _chunks, _g, ia, ib = S.collision_inputs("HPZ", S.S2_PROTOTYPE)
    hm = _read("heightmaps.bin")
    used = (set(ia) | set(ib)) - {0}
    assert used, "HPZ's collision indices are empty"
    for s in used:
        assert any(hm[s * ROW:(s + 1) * ROW]), (
            f"HPZ references shape ${s:02X}, which is air in this bank")


# --- the traps this file exists to keep shut -------------------------------

def test_the_importer_does_not_write_the_shipping_tables(tmp_path):
    """The trap `test_import_sk_collision.py` records, plus one more: this importer
    must not touch `collision/` OR `collision/base/` even when run with no argument,
    because the shipping act's tables and the S&K bank both live there."""
    _require(S.S2_FINAL)
    coll = os.path.join(REPO, "games", "sonic4", "data", "collision")
    names = ("heightmaps.bin", "heightmaps_rot.bin", "angles.bin", "solidity.bin")
    before = {}
    for sub in ("", "base"):
        for n in names:
            p = os.path.join(coll, sub, n)
            if os.path.isfile(p):
                before[p] = open(p, "rb").read()
    assert len(before) >= 8, f"only found {len(before)} tables to guard under {coll}"

    subprocess.run([sys.executable, os.path.join(TOOLS, "import_s2_collision.py"),
                    "build", str(tmp_path)], check=True,
                   capture_output=True, text=True)
    for p, b in before.items():
        assert open(p, "rb").read() == b, f"the importer overwrote {p}"
    assert os.path.isfile(os.path.join(tmp_path, "heightmaps.bin"))


def test_defaults_resolve_at_call_time():
    """Parcel 3's defect class: a default bound at import time cannot be redirected by
    a caller, and resolves the donor root on a checkout that may not have one."""
    assert callable(I.default_out) and callable(I.default_donor)
    for name in ("default_out", "default_donor"):
        assert not isinstance(getattr(I, name), (str, bytes)), (
            f"{name} became a module-level constant — it is a function so the value is "
            f"resolved per call")
    assert I.default_out().endswith(os.path.join("collision", "base_s2"))
    # and build() honours both overrides without touching the defaults
    import inspect
    sig = inspect.signature(I.build)
    assert sig.parameters["out"].default is None
    assert sig.parameters["donor"].default is None


def test_the_importer_is_deterministic(tmp_path):
    """Two runs, byte-identical, and identical to what is committed."""
    _require(S.S2_FINAL)
    a, b = tmp_path / "a", tmp_path / "b"
    I.build(out=str(a), quiet=True)
    I.build(out=str(b), quiet=True)
    for n in ("heightmaps.bin", "heightmaps_rot.bin", "angles.bin", "solidity.bin"):
        x = open(os.path.join(str(a), n), "rb").read()
        assert x == open(os.path.join(str(b), n), "rb").read(), f"{n} is not stable"
        assert x == _read(n), (
            f"the committed {n} is not what the importer produces today — re-run "
            f"`python3 tools/import_s2_collision.py build` and commit the result")
    shutil.rmtree(str(a))
