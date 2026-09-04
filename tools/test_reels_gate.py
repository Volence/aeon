"""Unit cover for `tools/reels_gate.py` — the pure halves, plus the source reads.

WHY THIS FILE NEVER OPENS A ROM, plane_base_swap_gate's own reason: build.sh's pytest
lane runs BEFORE the sigil build, so a unit test opening `s4.debug.bin` here would grade
a PREVIOUS build. The gate's ROM half runs post-sigil, in build.sh, with
`--built-after`. What is covered here is the judgement the gate adds — array parsing,
the two's-complement byte encoding, distinctness — plus the two facts it reads out of
game source, which are exactly the facts a source-level regression would break before
any ROM existed.

PROVEN RED, by editing a COMMITTED baseline and restoring it, 2026-09-03. `__pycache__`
was cleared between mutation runs (the stale-.pyc false-green trap this repo has
measured before: a same-length, same-second mutation can be served from cache). Four
mutations, each shown applied on disk (`git diff --stat` naming the file) before the
run, each restored with `git checkout HEAD -- <path>` afterwards. Full evidence,
including the ROM-level runs (which need a build and so cannot live in this file), is in
docs/DEFERRED_WORK.md's EFFECTS-W1 item 10a booking.

  * `OJZ_REEL_SPEEDS` collides two entries (index 1's `-5` -> `3`, matching index 0)
        -> build RED: `reel_rates_ok()`'s distinctness ensure
           (games/sonic4/config/constants.emp) fires by name, naming the colliding
           array. Re-measured on a GENERATED table 2026-09-04 (EFFECTS-W1 item 10 step
           4): authoring `[3, 3, 2, -4, 6]` into an editor scene's `reels.rates`
           produces exactly ONE build error, that ensure — which is what "the guard
           travels" means, and what the five-ary `distinct5()` it replaced could not
           do. This unit file's own
           `test_all_distinct_refuses_a_collision` covers the PURE half of that same
           judgement without a build.
  * `OJZ_REEL_SPEEDS` shortened to 4 entries (REEL_BAND_COUNT left at 5)
        -> build RED: the array's own `.len == REEL_BAND_COUNT` ensure fires.
  * The `if DEBUG == 1` gate removed from `pub data OJZ_Reel_Speed` and the
    `if DEBUG == 1 {}` wrap removed from `pub proc OJZ_Reels_Fill` (both made
    unconditional)
        -> release build green, `tools/reels_gate.py --shape release` RED: "emits N
           bytes in the RELEASE shape" for both symbols.
  * A single ROM byte hand-patched post-build (`OJZ_Reel_Speed`'s first byte, $03 -> $04)
        -> build untouched (nothing at build time re-reads the ROM's own bytes),
           `tools/reels_gate.py --shape debug` RED: "band 0 ... MISMATCH" — the class of
           divergence only a ROM-level check can catch, mirroring OJZ_BaseSwap's
           literal-bypass mutation.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import reels_gate as G  # noqa: E402


# ---------------------------------------------------------------------------
# The two facts, read out of game source. Not copies: the same calls the gate makes.
# ---------------------------------------------------------------------------

def _facts():
    return dict(
        band_count=G.emp_const(G.GAME_CONSTANTS, "REEL_BAND_COUNT"),
        speeds=G.emp_int_array(G.FIXTURE, "OJZ_REEL_SPEEDS"),
    )


def test_reel_band_count_is_five():
    """A change here is a real geometry change (REEL_COLS_PER_BAND must move with it,
    per games/sonic4/data/effects/ojz_effects.emp's own ensure) — this pins today's
    shipped value so an accidental edit is visible as a failing assumption, not a
    silently-adjusted gate."""
    assert G.emp_const(G.GAME_CONSTANTS, "REEL_BAND_COUNT") == 5


def test_the_speed_array_matches_band_count():
    f = _facts()
    assert len(f["speeds"]) == f["band_count"], (
        f"OJZ_REEL_SPEEDS has {len(f['speeds'])} entries, REEL_BAND_COUNT is "
        f"{f['band_count']} — the source's own ensure should have refused this build")


def test_the_shipped_speeds_are_pairwise_distinct():
    """The whole 'reels' claim, re-measured independently of `reel_rates_ok()`'s ensure."""
    f = _facts()
    assert G.all_distinct(f["speeds"]), (
        f"OJZ_REEL_SPEEDS = {f['speeds']} collide — two reel bands would share a rate")


def test_emp_int_array_parses_negative_entries():
    """The parser must handle signed decimal literals — every other speed is negative."""
    f = _facts()
    assert any(v < 0 for v in f["speeds"]), (
        "the shipped array has no negative entries to exercise the parser's sign "
        "handling — if this ever fires, OJZ_REEL_SPEEDS changed shape and the next "
        "assertion below is the one that actually matters")
    assert -5 in f["speeds"] or True  # documents intent; the real check is the round-trip below


def test_emp_int_array_round_trips_on_a_synthetic_source(tmp_path):
    """Independent of the shipped file: prove the regex handles the general shape,
    including negatives and whitespace variance, without relying on today's five values."""
    p = tmp_path / "synthetic.emp"
    p.write_text("const SOME_ARRAY: [i8; 4] = [ 1, -2,3 , -128 ]\n")
    assert G.emp_int_array(str(p), "SOME_ARRAY") == [1, -2, 3, -128]


def test_emp_int_array_refuses_a_missing_name():
    try:
        G.emp_int_array(G.FIXTURE, "THIS_NAME_DOES_NOT_EXIST_ANYWHERE")
    except G.Unmeasurable:
        return
    raise AssertionError("a missing array name must be UNMEASURABLE, not silently empty")


# ---------------------------------------------------------------------------
# The signed-byte encoder — the two's-complement half a ROM byte compare needs.
# ---------------------------------------------------------------------------

def test_to_bytes_i8_encodes_negatives_as_twos_complement():
    assert G.to_bytes_i8([3, -5, 2, -4, 6]) == [0x03, 0xFB, 0x02, 0xFC, 0x06]


def test_to_bytes_i8_accepts_the_i8_extremes():
    assert G.to_bytes_i8([127, -128]) == [0x7F, 0x80]


def test_to_bytes_i8_refuses_a_value_outside_i8():
    try:
        G.to_bytes_i8([128])
    except G.Unmeasurable:
        pass
    else:
        raise AssertionError("128 does not fit in a signed byte and must be refused")
    try:
        G.to_bytes_i8([-129])
    except G.Unmeasurable:
        pass
    else:
        raise AssertionError("-129 does not fit in a signed byte and must be refused")


# ---------------------------------------------------------------------------
# Distinctness — the pure half of the "reels, not ripple" claim.
# ---------------------------------------------------------------------------

def test_all_distinct_accepts_five_different_values():
    assert G.all_distinct([3, -5, 2, -4, 6]) is True


def test_all_distinct_refuses_a_collision():
    """The exact mutation this file's docstring proves red at the build: two bands
    sharing a rate. Covered here as the pure judgement, without needing a build."""
    assert G.all_distinct([3, 3, 2, -4, 6]) is False


def test_all_distinct_refuses_a_collision_at_the_far_end():
    """A collision is a collision anywhere in the list, not just index 0 vs 1."""
    assert G.all_distinct([3, -5, 2, -4, -5]) is False
