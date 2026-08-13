"""Structural integrity of the committed replay fixtures.

This does NOT run the replay net. Running it needs the emulator and a human --
see docs/superpowers/plans/2026-08-13-replay-net-restamp.md. The net has no
automated runner at all, which is how master stayed red from the Knuckles C4
merge until 2026-08-13 with nothing reporting it.

What this DOES catch is a corrupt, truncated, or mis-packed fixture, which is
the failure a re-stamp can introduce -- and, via the length assertion, a change
that would silently move EndOfRom and require a sigil repin.
"""
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
REPLAYS = TOOLS.parent / "games" / "sonic4" / "data" / "replays"

import replay_pack  # noqa: E402


@pytest.mark.parametrize(
    "name,size,ticks,checkpoints",
    [
        ("ojz_fixture.bin", 272, 1721, 27),
        ("ojz_slide_fixture.bin", 336, 2350, 37),
    ],
)
def test_fixture_structure(name, size, ticks, checkpoints):
    path = REPLAYS / name
    blob = path.read_bytes()
    assert len(blob) == size, (
        f"{name} length changed ({len(blob)} != {size}): the fixture sits before the "
        f"fault-handler island, so its size moves EndOfRom and requires a sigil repin"
    )

    raw, checks, core_hash, tick_count, seed, flags = replay_pack.decode_stream(blob)
    assert tick_count == ticks
    assert len(checks) == checkpoints
    assert len(raw) == ticks
    assert seed == 0, "rng_seed must stay 0 until an RNG exists"

    # Checkpoints sit on the 64-tick ring boundary, starting at 0. The recorder
    # fires them at (ring_idx & 63) == 0 BEFORE storing that tick's input, so any
    # drift here means record and playback disagree about what ring index means.
    for i, (ring, _hash) in enumerate(checks):
        assert ring == i * 64, f"{name} checkpoint {i} at ring {ring}, expected {i * 64}"


def test_ojz_fixture_spindash_input_is_preserved():
    """The spindash charge-and-rev at ring 1212-1248 uses BUTTON_C, which the
    oracle driver cannot press. If these runs ever vanish, the fixture was
    RE-RECORDED rather than re-stamped, and its coverage claim no longer holds.

    This is also the input that caused the 2026-08-13 re-stamp: Knuckles C4
    changed spindash dust / line-0 palette / EnsureStanding, so every checkpoint
    after ring 1212 diverged while all 20 at or below ring 1216 passed.
    """
    blob = (REPLAYS / "ojz_fixture.bin").read_bytes()
    raw, _checks, _core, _ticks, _seed, _flags = replay_pack.decode_stream(blob)
    BUTTON_DOWN = 0x02
    BUTTON_C = 0x20
    assert all(b == BUTTON_DOWN for b in raw[1212:1237]), (
        "the 25-tick DOWN hold at ring 1212 (spindash charge) changed"
    )
    assert raw[1237] & BUTTON_C, "spindash rev at ring 1237 lost its C press"
    assert raw[1248] & BUTTON_C, "spindash rev at ring 1248 lost its C press"
