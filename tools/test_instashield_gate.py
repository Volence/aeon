"""Unit tests for the insta-shield's `jumping` precondition (Ability_InstaShield).

Three layers, and the split matters:

1. THE MODEL. S3K's rule is transcribed once, in instashield_gate.py, from
   sonic3k.asm:23368-23486. These tests do NOT re-transcribe it — they assert
   INVARIANTS the transcription must satisfy if it is right (the allowed set is exactly
   the two from-a-jump states; the not-from-a-jump air states are refused; the one-shot
   outranks everything past the state test; a suppressed press still lifts the roll-jump
   lockout). A copy of the allowed set would prove nothing about a mis-copied branch.

2. THE ROUTINE, executed. Over a COMMITTED CUT of a real ROM
   (tools/fixtures/instashield_cut.json), because build.sh's pytest lane runs BEFORE
   sigil and a test opening s4.debug.bin here would measure a previous build —
   documented at build.sh:61-72, where that happened twice. The same sweep runs against
   the FRESH artifact in build.sh's post-sigil block, which also fails loudly if this
   cut has gone stale.

3. THE CONSTANTS. The cut carries the PSTATE_*/INSTASHIELD_* values the ROM was built
   with; these re-read them from games/sonic4/config/constants.emp so a renumbered
   state fails as a named mismatch rather than as a quietly weaker gate.
"""

import json
import pathlib
import re
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import instashield_gate as isg  # noqa: E402

FIXTURE = TOOLS / "fixtures" / "instashield_cut.json"


def _shapes():
    if not FIXTURE.exists():
        return []
    return isg.cut_shapes(FIXTURE)


@pytest.fixture(scope="module", params=_shapes() or [None])
def cut(request):
    """One cut per committed BUILD SHAPE. Both canonical shapes place
    Ability_InstaShield at different addresses, and both must satisfy the model — a
    green on `s4.debug.lst` alone would leave the shipped release ROM ungraded."""
    if request.param is None:
        pytest.fail("%s is missing or carries no shapes — regenerate with "
                    "tools/instashield_gate.py --write-fixture" % FIXTURE)
    return isg.load_cut(FIXTURE, request.param)


@pytest.fixture(scope="module")
def K(cut):
    return cut[5]         # the constants the ROM in this cut was built with


def test_both_canonical_shapes_are_committed():
    """A cut for one shape only would silently leave the other ROM ungraded — which is
    exactly how a release-only regression gets shipped behind a green DEBUG lane."""
    assert set(_shapes()) == {"s4.lst", "s4.debug.lst"}, \
        "instashield_cut.json holds %s; both canonical shapes must be stamped " \
        "(./build.sh and DEBUG=1 ./build.sh, then --write-fixture on each)" % _shapes()


# ---------------------------------------------------------------- 1. the model

def test_model_allows_exactly_the_two_from_a_jump_states(K):
    """S3K's `tst.b jumping(a0) / beq Sonic_UpVelCap` (sonic3k.asm:23369-23370) makes
    the insta-shield unreachable for any airborne frame that did not come from a jump.
    In this engine that set is {PSTATE_JUMP, PSTATE_ROLLJUMP} — assert it over EVERY
    byte value, not just the declared states, so an illegal state byte cannot slip in
    either."""
    allowed = set()
    for state in range(256):
        fires, _, _, _ = isg.model(state, K["INSTASHIELD_READY"], 0, K)
        if fires:
            allowed.add(state)
    assert allowed == {K["PSTATE_JUMP"], K["PSTATE_ROLLJUMP"]}


def test_model_refuses_the_two_not_from_a_jump_air_states(K):
    """The owner's report — insta-shield out of an uncurled fall — is PSTATE_AIR, and
    PSTATE_AIRBALL is its curled twin (rolled off a ledge / the spindash floor-vanish).
    Both are airborne and neither came from a jump."""
    for state in (K["PSTATE_AIR"], K["PSTATE_AIRBALL"]):
        fires, cancels, new_state, new_insta = isg.model(
            state, K["INSTASHIELD_READY"], 0, K)
        assert not fires
        assert not cancels
        assert new_state == state, "a refused press must not change the state"
        assert new_insta == K["INSTASHIELD_READY"], \
            "a refused press must leave the one-shot armed — otherwise a state with " \
            "no re-arm path could strand it"


def test_model_one_shot_outranks_everything_past_the_state_test(K):
    """S3K's `tst.b double_jump_flag / bne` (:23402) sits between the `jumping` test
    and the roll-jump cancel, so a second press in the same airborne stretch does
    nothing at all — not even the cancel."""
    for state in (K["PSTATE_JUMP"], K["PSTATE_ROLLJUMP"]):
        for insta in (K["INSTASHIELD_ATTACKING"], K["INSTASHIELD_SPENT"]):
            fires, cancels, new_state, new_insta = isg.model(state, insta, 0, K)
            assert not fires and not cancels
            assert new_state == state and new_insta == insta


def test_model_suppressed_press_still_lifts_the_rolljump_lockout(K):
    """S3K's `bclr #Status_RollJump` (:23408) is ahead of the barrier tests, so a
    suppressed insta-shield still cancels the roll-jump. That ordering is the whole
    reason the cancel is a separate observable in the sweep."""
    fires, cancels, new_state, new_insta = isg.model(
        K["PSTATE_ROLLJUMP"], K["INSTASHIELD_READY"],
        K["INSTASHIELD_SUPPRESS_MASK"], K)
    assert not fires
    assert cancels and new_state == K["PSTATE_JUMP"]
    assert new_insta == K["INSTASHIELD_READY"]


def test_model_every_suppression_bit_suppresses_and_nothing_else_does(K):
    mask = K["INSTASHIELD_SUPPRESS_MASK"]
    for bit in range(8):
        fires, _, _, _ = isg.model(K["PSTATE_JUMP"], K["INSTASHIELD_READY"],
                                   1 << bit, K)
        assert fires == (not (mask & (1 << bit))), \
            "status_secondary bit %d disagrees with INSTASHIELD_SUPPRESS_MASK" % bit


# ------------------------------------------------- 2. the routine, executed

def _sweep(cut):
    rom, start, end, stubs, offs, k, _ = cut
    prog, _ = isg.decode(rom, start, end)
    return isg.sweep(rom, prog, start, end, stubs, offs, k)


def test_routine_matches_the_model_over_the_full_cross_product(cut):
    total, fails, fired = _sweep(cut)
    assert total > 0
    assert fails == [], "%d of %d executions disagree: %s" % (
        len(fails), total, fails[:5])


def test_routine_fires_from_exactly_the_two_jump_states(cut, K):
    _, _, fired = _sweep(cut)
    assert fired == {K["PSTATE_JUMP"], K["PSTATE_ROLLJUMP"]}


def test_routine_reads_only_the_three_playerv_bytes_the_model_knows_about(cut):
    """A guard against the model and the routine drifting apart SILENTLY. S3K has one
    more gate we have not built — `cmp.w y_vel(a0),#-$400 / ble` in Sonic_JumpHeight,
    booked in docs/DEFERRED_WORK.md — and if it ever lands here without
    instashield_gate.model growing with it, the sweep would keep passing while the two
    described different routines. It cannot land without reading a fourth SST byte."""
    rom, start, end, stubs, offs, k, _ = cut
    prog, _ = isg.decode(rom, start, end)
    seen = set()
    for state in (k["PSTATE_JUMP"], k["PSTATE_ROLLJUMP"], k["PSTATE_AIR"],
                  k["PSTATE_AIRBALL"]):
        for insta in (k["INSTASHIELD_READY"], k["INSTASHIELD_SPENT"]):
            got = isg.run_case(rom, prog, start, end, stubs, offs, state, insta, 0)
            seen |= got["sst_reads"]
    expected = {offs["player_state"], offs["status_secondary"], offs["instashield"]}
    assert seen <= expected, (
        "Ability_InstaShield reads SST byte(s) %s that instashield_gate's model does "
        "not know about — grow the model before the gate can be trusted again"
        % sorted("$%02X" % o for o in (seen - expected)))


# ------------------------------------------------------------- 3. constants

_CONST = re.compile(r"^pub const (\w+)\s*=\s*(.+?)\s*(?://.*)?$", re.M)


def _source_constants():
    text = (ROOT / "games" / "sonic4" / "config" / "constants.emp").read_text()
    out = {}
    for name, expr in _CONST.findall(text):
        expr = expr.strip()
        if re.fullmatch(r"\d+", expr):
            out[name] = int(expr)
        elif re.fullmatch(r"\$[0-9A-Fa-f]+", expr):
            out[name] = int(expr[1:], 16)
    return out


def test_cut_constants_still_match_the_source(K):
    """The cut was stamped from a build's own equates. These are the same names read
    back out of the file that DECLARES them, so a renumbered state or a re-derived
    suppression mask fails here by name."""
    src = _source_constants()
    for name in ("PSTATE_JUMP", "PSTATE_ROLLJUMP", "PSTATE_AIR", "PSTATE_AIRBALL",
                 "INSTASHIELD_READY", "INSTASHIELD_ATTACKING", "INSTASHIELD_SPENT"):
        assert name in src, "%s is no longer a plain `pub const` in constants.emp" % name
        assert src[name] == K[name], (
            "%s is %d in games/sonic4/config/constants.emp but %d in the committed "
            "cut — regenerate tools/fixtures/instashield_cut.json"
            % (name, src[name], K[name]))


def test_playerv_offsets_parse_to_the_cut(K, cut):
    """The overlay parser, re-run against today's player_common.emp. A reordered
    PlayerV moves the probes; a cut stamped before the reorder is then stale, and this
    is what says so."""
    _, _, _, _, offs, _, sst_custom = cut
    fresh, _ = isg.playerv_offsets(sst_custom)
    for field in ("player_state", "status_secondary", "instashield"):
        assert fresh[field] == offs[field], (
            "PlayerV.%s parses to $%02X today but the cut holds $%02X — the overlay "
            "moved; regenerate tools/fixtures/instashield_cut.json"
            % (field, fresh[field], offs[field]))
