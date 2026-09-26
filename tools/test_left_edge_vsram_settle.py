#!/usr/bin/env python3
"""test_left_edge_vsram_settle — left_edge_vsram_probe settles on the SHARED, DERIVED bound.

SETTLE-IMPL-COLLAPSE (2026-09-26). The probe carried its own copy of the parallax-transition
settle with a magic `limit=300`: the only copy in tools/ whose give-up threshold did not move
with PARALLAX_TRANS_DEFAULT. It now delegates to `fg_left_edge_gate.settle_transition`, whose
bound is 2 x PARALLAX_TRANS_DEFAULT read out of engine/system/constants.emp, and keeps its
own +30-frame rest after the counter reaches 0.

No emulator: a fake bus client plays `Parallax_Transition_Frames` and counts the frames the
settle asks for. Two things are pinned, because each alone could pass on a wrong settle:

  * a counter that NEVER reaches 0 is refused (SystemExit, UNMEASURABLE) after exactly the
    derived budget of single-frame steps -- 2 x PARALLAX_TRANS_DEFAULT + 1, the gate's own
    loop shape -- and not after 300. This is the row's subject;
  * a counter that DOES reach 0 costs exactly its remaining frames in single steps, then one
    30-frame rest, which is what the probe did before the collapse. This is the "sampled
    values unchanged" half: the frame schedule the probe runs is the same one.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fg_left_edge_gate as G          # noqa: E402
import left_edge_vsram_probe as P      # noqa: E402

ADDR = 0xFF88F4
SYMS = {"Parallax_Transition_Frames": ADDR}


class FakeBus:
    """`remaining` is the counter; None means it never reaches 0."""

    def __init__(self, remaining):
        self.remaining = remaining
        self.steps = []                 # the `frames` argument of every run_frames call

    async def call(self, method, params):
        if method == "emulator/read":
            assert params["addr"] == hex(ADDR), params
            v = 5 if self.remaining is None else self.remaining
            return {"bytes": "0x%02X" % v}
        if method == "emulator/run_frames":
            n = params["frames"]
            self.steps.append(n)
            if self.remaining is not None:
                self.remaining = max(0, self.remaining - n)
            return {}
        raise AssertionError(f"unexpected call {method}")


def test_the_bound_is_derived_not_magic():
    trans = G._trans_default()
    budget = 2 * trans
    assert budget < 300, "the derived bound should be the tighter one; re-read this test"
    bus = FakeBus(None)
    with pytest.raises(SystemExit) as ei:
        asyncio.run(P.settle_transition(bus, SYMS))
    assert "UNMEASURABLE" in str(ei.value)
    assert "PARALLAX_TRANS_DEFAULT" in str(ei.value), (
        "the refusal must name the derivation, not a bare frame count: " + str(ei.value))
    assert bus.steps == [1] * (budget + 1), (
        f"gave up after {len(bus.steps)} single-frame steps; the derived budget is "
        f"2 x PARALLAX_TRANS_DEFAULT ({trans}) = {budget}, in the gate's loop shape "
        f"({budget + 1} steps)")


@pytest.mark.parametrize("remaining", [0, 1, 11, 16])
def test_a_settling_counter_runs_the_same_frame_schedule_as_before(remaining):
    bus = FakeBus(remaining)
    asyncio.run(P.settle_transition(bus, SYMS))
    assert bus.steps == [1] * remaining + [30], bus.steps
