"""Slope-standstill mirror symmetry — the half the comptime gate cannot reach.

`games/sonic4/player/player_ground.emp` carries a comptime gate (search the file
for "SLOPE STANDSTILL MIRROR-SYMMETRY GATE") that walks all 256 angles and proves
the standing gate's DECISION is mirror-symmetric. What comptime cannot do is read
the instructions it guards: the ensures would stay green if someone put the shift
back in front of the abs, because they compute their own arithmetic. That is this
file's job, plus an independent re-derivation of the same numeric property so the
two do not share a bug.

THE DIVERGENCE THIS PROTECTS (owner ruling 2026-08-27, "mirrored slopes must
behave the same"). S3K's Player_SlopeResist takes `|sin asr 3|` as the magnitude
its standing threshold compares. `asr` floors toward -inf, so a negative sine
comes back one magnitude larger than its positive mirror, and the same physical
slope slides in one orientation and holds in the other. We take the magnitude
BEFORE the shift. Registered in docs/ENGINE_ARCHITECTURE.md.

NOTHING BELOW IS A COPIED NUMBER. The threshold, the shift amount, the ceiling
band and the fixtures are all parsed out of the sources or derived from the
threshold, so a change to any of them moves the expectations with it.
"""

import os
import re
import struct

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

GROUND_EMP = os.path.join(ROOT, "games", "sonic4", "player", "player_ground.emp")
CONSTANTS_EMP = os.path.join(ROOT, "engine", "system", "constants.emp")
SINE_BIN = os.path.join(ROOT, "engine", "data", "sine.bin")

# Honor the same donor override the importers honor — a worktree checkout sits
# under .claude/worktrees/, where the ../../skdisasm default resolves wrong.
_SK_ROOT = os.environ.get(
    "AEON_SKDISASM_DIR",
    os.path.normpath(os.path.join(ROOT, "..", "skdisasm")))
SK_SINE = os.path.join(_SK_ROOT, "Levels", "Misc", "sine.bin")


# --------------------------------------------------------------------------
# Source extraction — everything the derivation needs, read from the tree.
# --------------------------------------------------------------------------

def _int(text):
    """`$1F` / `31` -> int."""
    text = text.strip()
    return int(text[1:], 16) if text.startswith("$") else int(text, 10)


def _strip_comment(line):
    return line.split("//", 1)[0]


@pytest.fixture(scope="module")
def slope_block():
    """The walking slope-factor block of PState_Ground, code lines only.

    Bounded by its own header comment and its own `.no_slope:` label, so it
    cannot accidentally swallow PState_Roll's slope block further down the file
    (which has the same shape and a DIFFERENT shift form).
    """
    src = open(GROUND_EMP, encoding="utf-8").read().splitlines()
    starts = [i for i, ln in enumerate(src) if "--- slope factor on gsp" in ln]
    assert len(starts) == 1, (
        "player_ground.emp: expected exactly one '--- slope factor on gsp' header "
        f"marking PState_Ground's walking slope block, found {len(starts)}. The "
        "block moved or was duplicated; this test can no longer say which one it "
        "is reading.")
    ends = [i for i, ln in enumerate(src) if i > starts[0] and ln.strip() == ".no_slope:"]
    assert ends, "player_ground.emp: no '.no_slope:' label after the slope-factor header"
    body = src[starts[0]:ends[0] + 1]
    code = [c.strip() for c in (_strip_comment(ln) for ln in body) if c.strip()]
    assert code, "player_ground.emp: the slope-factor block has no code lines"
    return code


def _find_one(code, pattern, what):
    hits = [(i, m) for i, m in ((i, re.match(pattern, ln)) for i, ln in enumerate(code)) if m]
    assert len(hits) == 1, (
        f"player_ground.emp slope block: expected exactly one {what} "
        f"(/{pattern}/), found {len(hits)}: {[code[i] for i, _ in hits]}")
    return hits[0]


@pytest.fixture(scope="module")
def shape(slope_block):
    """Every parameter of the slope block, parsed from the block itself."""
    code = slope_block
    i_band_add, m_band_add = _find_one(code, r"addi\.b\s+#(\$?[0-9A-Fa-f]+),\s*d1$", "ceiling-band bias")
    i_band_cmp, m_band_cmp = _find_one(code, r"cmpi\.b\s+#(\$?[0-9A-Fa-f]+),\s*d1$", "ceiling-band compare")
    i_abs, _ = _find_one(code, r"abs_w\(d1\)$", "gate magnitude abs")
    i_gate_shift, m_gate_shift = _find_one(code, r"asr\.w\s+#(\d+),\s*d1$", "gate magnitude shift")
    i_fac_shift, m_fac_shift = _find_one(code, r"asr\.w\s+#(\d+),\s*d0$", "applied slope-factor shift")
    i_thresh, m_thresh = _find_one(code, r"cmpi\.w\s+#(\w+),\s*d1$", "standing-gate threshold compare")
    i_flat, _ = _find_one(code, r"beq\s+\.no_slope$", "flat-angle fast path")

    consts = open(CONSTANTS_EMP, encoding="utf-8").read()
    out = {}
    for name in ("PHYS_SLOPE_STAND_MIN", "PHYS_SLOPE_WALK"):
        m = re.search(r"^pub const\s+%s\s*=\s*(\$?[0-9A-Fa-f]+)" % name, consts, re.M)
        assert m, f"engine/system/constants.emp: {name} not found"
        out[name] = _int(m.group(1))

    assert m_thresh.group(1) == "PHYS_SLOPE_STAND_MIN", (
        "player_ground.emp slope block: the standing gate compares against "
        f"'{m_thresh.group(1)}' rather than PHYS_SLOPE_STAND_MIN — this test can no "
        "longer derive the threshold from engine/system/constants.emp")

    out.update(
        band_add=_int(m_band_add.group(1)),
        band_cmp=_int(m_band_cmp.group(1)),
        gate_shift=int(m_gate_shift.group(1)),
        factor_shift=int(m_fac_shift.group(1)),
        i_band_add=i_band_add, i_band_cmp=i_band_cmp, i_abs=i_abs,
        i_gate_shift=i_gate_shift, i_factor_shift=i_fac_shift,
        i_thresh=i_thresh, i_flat=i_flat,
    )
    # WHICH RULE THE CODE ACTUALLY IMPLEMENTS, read off the instruction order
    # rather than assumed. This is what keeps the symmetry test below from being
    # a statement about arithmetic the test itself invented: revert the order in
    # player_ground.emp and the symmetry test starts asking about |sin asr n|,
    # finds the asymmetry, and goes red naming the angles.
    out["mag"] = _mag_shipped if i_abs < i_gate_shift else _mag_s3k
    return out


# --------------------------------------------------------------------------
# The structural half — the order of the two operations IS the divergence.
# --------------------------------------------------------------------------

def test_gate_takes_the_magnitude_before_the_shift(shape):
    assert shape["i_abs"] < shape["i_gate_shift"], (
        "player_ground.emp: the standing gate shifts before it takes the magnitude "
        "— that is S3K's |sin asr 3| and it makes mirrored slopes behave "
        "differently (owner ruling 2026-08-27 says they must not). The gate path "
        "must run abs_w(d1) FIRST, then asr.w. See the divergence register in "
        "docs/ENGINE_ARCHITECTURE.md before changing this back.")


def test_applied_factor_shift_is_not_hoisted_above_the_gate(shape):
    """The gate must consume the raw sine, not an already-shifted value.

    Hoisting `asr.w #3, d0` back above the gate does not by itself reintroduce
    the asymmetry, but it removes the only reason the gate's own shift exists,
    and the obvious follow-up cleanup ("d0 is already shifted, just abs it") is
    exactly the regression. Fail here, at the cheap step.
    """
    assert shape["i_factor_shift"] > shape["i_thresh"], (
        "player_ground.emp: the applied slope-factor shift (asr.w #N, d0) sits "
        "ABOVE the standing-gate compare again. The gate must see the unshifted "
        "sine so it can take the magnitude first.")


def test_shift_amount_is_the_one_phys_slope_walk_implies(shape):
    """asr N is only 'exact, no muls' if PHYS_SLOPE_WALK == 1 << (8 - N)."""
    n = shape["factor_shift"]
    assert shape["gate_shift"] == n, (
        f"player_ground.emp: the gate shifts by {shape['gate_shift']} but the applied "
        f"factor shifts by {n}. The gate would be testing a different slope.")
    assert shape["PHYS_SLOPE_WALK"] == 1 << (8 - n), (
        f"player_ground.emp: asr #{n} implements (${1 << (8 - n):X}*sin)>>8, but "
        f"PHYS_SLOPE_WALK is ${shape['PHYS_SLOPE_WALK']:X}. The shift form and the "
        "constant have diverged.")


# --------------------------------------------------------------------------
# The numeric half — re-derived here, independently of the comptime gate.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sine():
    blob = open(SINE_BIN, "rb").read()
    assert len(blob) == 0x280, f"engine/data/sine.bin is {len(blob)} bytes, not $280"
    return [struct.unpack(">h", blob[i * 2:i * 2 + 2])[0] for i in range(256)]


def _mirror(a):
    """Mirroring a slope left-to-right negates its angle."""
    return (256 - a) & 0xFF


def _reaches(a, shape):
    """Does the block reach its standing gate at this angle? Its own two skips."""
    if a == 0:
        return False                                        # beq .no_slope
    return ((a + shape["band_add"]) & 0xFF) < shape["band_cmp"]


def _mag_shipped(s, n):
    """(|sin|) >> n — the magnitude taken before the shift."""
    return (-s if s < 0 else s) >> n


def _mag_s3k(s, n):
    """|sin asr n| — asr floors, so a negative sine rounds AWAY from zero."""
    return -(s >> n) if s < 0 else s >> n


def _band_edges(shape):
    """Angles the ceiling band treats differently from their mirrors.

    Derived from the parsed band, never written down: the skip is a half-open
    interval, and the mirror of a half-open interval is the other one, so its
    two endpoints necessarily disagree with their mirrors.
    """
    return {a for a in range(256) if _reaches(a, shape) != _reaches(_mirror(a), shape)}


def _slides(a, sine, shape, mag):
    if not _reaches(a, shape):
        return False
    return mag(sine[a], shape["gate_shift"]) >= shape["PHYS_SLOPE_STAND_MIN"]


def _asymmetric(sine, shape, mag):
    edges = _band_edges(shape)
    return sorted(a for a in range(256)
                  if a not in edges
                  and _slides(a, sine, shape, mag) != _slides(_mirror(a), sine, shape, mag))


def test_band_edges_are_the_two_endpoints(shape):
    """The one asymmetry we knowingly do NOT fix — pinned so it cannot widen."""
    edges = _band_edges(shape)
    assert len(edges) == 2, (
        f"the ceiling-band skip now disagrees with its own mirror at {len(edges)} "
        f"angles ({sorted(hex(a) for a in edges)}), not the 2 endpoints a half-open "
        "interval must have. The band changed shape — the exclusion below is no "
        "longer the small authentic S3K artifact it was scoped to be.")


def test_shipped_rule_is_mirror_symmetric(sine, shape):
    """Asked of the rule the CODE implements — see shape()'s `mag`."""
    bad = _asymmetric(sine, shape, shape["mag"])
    assert bad == [], (
        "a player standing at rest behaves differently from one on the mirrored "
        f"slope at angle(s) {[hex(a) for a in bad]}. The owner ruled mirrored slopes "
        "behave alike (2026-08-27, docs/ENGINE_ARCHITECTURE.md divergence register).")


def test_s3k_rule_is_not_symmetric_so_the_divergence_still_buys_something(sine, shape):
    bad = _asymmetric(sine, shape, _mag_s3k)
    assert bad, (
        "S3K's own |sin asr N| is now mirror-symmetric too, which makes "
        "player_ground.emp's abs-before-shift a divergence that buys nothing. "
        "Restore the reference form and retire the register entry.")


def test_the_two_rules_differ_exactly_where_they_straddle_the_threshold(sine, shape):
    """Two independent derivations of the moved set must agree.

    Naive: run both rules and diff the decisions. Analytic: the rules can only
    disagree where `asr` rounded a negative sine up ACROSS the threshold, i.e.
    where the S3K magnitude is exactly the threshold and the shipped one is one
    below it. If these two sets ever disagree, one of the derivations is wrong.
    """
    n, thresh = shape["gate_shift"], shape["PHYS_SLOPE_STAND_MIN"]
    naive = sorted(a for a in range(256)
                   if _slides(a, sine, shape, _mag_shipped) != _slides(a, sine, shape, _mag_s3k))
    analytic = sorted(a for a in range(256)
                      if _reaches(a, shape)
                      and _mag_s3k(sine[a], n) == thresh
                      and _mag_shipped(sine[a], n) == thresh - 1)
    assert naive == analytic, (
        f"the moved-angle set disagrees between derivations: decision-diff "
        f"{[hex(a) for a in naive]} vs straddle-the-threshold {[hex(a) for a in analytic]}")
    assert naive, (
        "no angle's behaviour moves at all — the change is a no-op against this "
        "table and threshold, so it is an unjustified S3K divergence.")
    # Every moved angle's mirror must be one that already held: that is what
    # "the pair now agrees" means, and it is why nothing symmetric moved.
    for a in naive:
        assert not _slides(_mirror(a), sine, shape, _mag_s3k), (
            f"angle {hex(a)} moved but its mirror {hex(_mirror(a))} was already "
            "sliding — the change did not converge a mirror pair, it broke one.")


def test_only_the_decision_moves_never_the_applied_factor(sine, shape):
    """The applied factor stays S3K's signed `sin asr n` at every angle.

    The parcel's safety claim is that the standstill DECISION is the only thing
    that moves. The applied value is read straight off d0, which the gate never
    writes, so this is a claim about the block's register discipline: `abs_w`
    and the gate shift both target d1.
    """
    assert shape["i_abs"] != shape["i_factor_shift"]
    n = shape["gate_shift"]
    for a in range(256):
        assert _mag_s3k(sine[a], n) == abs(sine[a] >> n), (
            f"the S3K magnitude model disagrees with a real arithmetic shift at "
            f"angle {hex(a)}")


# --------------------------------------------------------------------------
# Fixtures derived from the threshold, not from today's table.
# --------------------------------------------------------------------------

def test_threshold_boundary_cases_derived_from_the_constant(shape):
    n, thresh = shape["gate_shift"], shape["PHYS_SLOPE_STAND_MIN"]
    step = 1 << n

    exact = thresh * step          # the smallest sine that is EXACTLY at the bound
    over = exact + 1               # one raw unit over the bound
    under = exact - 1              # one raw unit under it

    # An exact multiple of the shift has no rounding to disagree about, in
    # either sign or either rule.
    for s in (exact, -exact):
        assert _mag_shipped(s, n) == thresh
        assert _mag_s3k(s, n) == thresh

    # Just over the bound. The shipped rule is exactly symmetric; S3K's rounds
    # the negative side up by one, but both signs still clear the bound, so the
    # DECISION agrees. Above the bound the artifact is invisible — that is why
    # it only ever showed up at one specific pair of angles.
    assert _mag_shipped(over, n) == thresh
    assert _mag_shipped(-over, n) == thresh
    assert _mag_s3k(over, n) == thresh
    assert _mag_s3k(-over, n) == thresh + 1
    assert _mag_s3k(-over, n) >= thresh

    # Just under it is where the two rules part company, and only on the
    # negative side. This is the whole bug, in two lines.
    assert _mag_shipped(under, n) == thresh - 1
    assert _mag_s3k(under, n) == thresh - 1
    assert _mag_shipped(-under, n) == thresh - 1, "abs-before-shift must hold below the bound"
    assert _mag_s3k(-under, n) == thresh, "asr must round -|under| up across the bound"


# --------------------------------------------------------------------------
# Provenance — the four antisymmetric rows are S3K's, not ours.
# --------------------------------------------------------------------------

def test_sine_table_is_byte_identical_to_the_s3k_donor(sine):
    if not os.path.exists(SK_SINE):
        pytest.skip(
            f"skdisasm donor not present at {SK_SINE} — set AEON_SKDISASM_DIR. "
            "The sine-table provenance claim in player_ground.emp's gate header "
            "is UNVERIFIED in this run.")
    assert open(SINE_BIN, "rb").read() == open(SK_SINE, "rb").read(), (
        "engine/data/sine.bin has diverged from skdisasm's Levels/Misc/sine.bin. "
        "The gate header in player_ground.emp claims the table's four "
        "non-antisymmetric rows are authentic S3K; that claim is now false.")


def test_table_antisymmetry_breaks_are_all_on_one_side_of_the_threshold(sine, shape):
    """Why the four authentic quirk rows cannot flip a standstill decision."""
    n, thresh = shape["gate_shift"], shape["PHYS_SLOPE_STAND_MIN"]
    broken = [a for a in range(256) if sine[a] != -sine[_mirror(a)]]
    assert broken, (
        "engine/data/sine.bin is now perfectly antisymmetric — the exclusion "
        "reasoning in player_ground.emp's gate header is stale and should be cut.")
    for a in broken:
        here = _mag_shipped(sine[a], n) >= thresh
        there = _mag_shipped(sine[_mirror(a)], n) >= thresh
        assert here == there, (
            f"sine table row {hex(a)} ({sine[a]}) and its mirror {hex(_mirror(a))} "
            f"({sine[_mirror(a)]}) now land on OPPOSITE sides of "
            f"PHYS_SLOPE_STAND_MIN. The table's own rounding is now a feel "
            "asymmetry in its own right, which no amount of abs-before-shift fixes.")
