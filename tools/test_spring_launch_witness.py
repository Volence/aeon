#!/usr/bin/env python3
"""tools/spring_launch_witness.py: a measured failure outranks a later refusal.

KEEPALIVE-IS-BLIND-TO-LOSSY (docs/research/2026-09-25-keepalive-lossy.md). The witness runs
eleven legs in sequence, and any of them can raise Unmeasurable. Until 2026-09-25 the list of
findings was a local inside run(), so a raise in a later leg threw away what the earlier legs
had MEASURED and the run exited 2 ("could not measure") with failures in hand and unprinted.
That is the dma_straddle_exercise shape: a "nothing measured" verdict that consulted less
than the tool had measured.

These rows drive the SHIPPED main() and the shipped C1 leg with the machine replaced by fakes,
so they boot no emulator and read no build artifact.
"""

import asyncio
import contextlib

import pytest

import spring_launch_witness as W


def _stub_reference_chain(monkeypatch, run_fake):
    """Make main()'s hop 1/hop 2 agree trivially and hand the machine to `run_fake`."""
    want = -2560
    monkeypatch.setattr(W, "s3k_spring_magnitudes", lambda: (want, -4096))
    monkeypatch.setattr(W, "parse_lst", lambda lst: {})
    monkeypatch.setattr(W, "parse_equs", lambda lst: {})
    monkeypatch.setattr(W, "objdef_y_vel_from_rom", lambda rom, sym, equ: want)
    table = {(d, s): (0, want) for d in W.SPRING_DIRS for s in W.SPRING_STRENGTHS}
    dirs = {d: i for i, d in enumerate(W.SPRING_DIRS)}
    monkeypatch.setattr(W, "spring_launch_table",
                        lambda rom, sym, equ, mags: (table, dirs, {}, [], (0x10, 0x20, 0x1000)))

    @contextlib.contextmanager
    def fake_emulator(rom, symbols=None):
        yield "fake.sock"

    monkeypatch.setattr(W, "aether_emulator", fake_emulator)
    monkeypatch.setattr(W, "run", run_fake)
    monkeypatch.setattr(W.sys, "argv", ["spring_launch_witness.py"])


def test_a_later_refusal_does_not_discard_an_earlier_measured_failure(monkeypatch, capsys):
    async def run_fake(sock, rom, lst, want, table, subtypes, out, fails):
        fails.append("L1: MEASURED FINDING THAT MUST SURVIVE")
        raise W.Unmeasurable("L5: entered the face, the hook never fired")

    _stub_reference_chain(monkeypatch, run_fake)
    rc = W.main()
    text = capsys.readouterr().out
    assert rc == 1, f"a measured failure followed by a refusal exited {rc}, not 1:\n{text}"
    assert "MEASURED FINDING THAT MUST SURVIVE" in text
    assert "RESULT: FAIL" in text
    assert "L5: entered the face" in text, "the refusal that stopped the run must still be named"


def test_a_refusal_with_nothing_measured_is_still_unmeasurable(monkeypatch, capsys):
    """The control: the change must not turn an honest refusal into a failure."""
    async def run_fake(sock, rom, lst, want, table, subtypes, out, fails):
        raise W.Unmeasurable("no spawned spring carries subtype 0")

    _stub_reference_chain(monkeypatch, run_fake)
    assert W.main() == 2
    assert "RESULT: UNMEASURABLE" in capsys.readouterr().out


class _FakeProbe:
    """Just enough of Probe for test_back_face: a scripted x track, a fired animation."""

    def __init__(self, xs, anim):
        self.equ = {"PHYS_TOP_SPEED": 0x600}
        self.xs, self.anim_id, self.i = list(xs), anim, -1

    async def put_player(self, **kw):
        self.put = kw

    async def frames(self, n):
        self.i += 1

    async def player_state(self):
        if self.i < 0:
            return {"x": self.put["x"], "y": self.put["y"], "xv": 0, "yv": 0, "gsp": 0}
        return {"x": self.xs[self.i], "y": self.put["y"], "xv": 0, "yv": 0, "gsp": 64}

    async def anim(self, sst):
        return self.anim_id


def test_c1_returns_a_measured_hook_firing_even_when_the_push_frame_was_not_seen(monkeypatch):
    """C1 in-leg: the launch hook fired (a finding) and he entered on the LAST sampled frame,
    so the push frame was never observed. That guard voids the push checks, not the finding."""
    monkeypatch.setitem(W._TOUCH, "w", 20)
    monkeypatch.setitem(W._ANIM, "Idle", 0)
    monkeypatch.setitem(W._ANIM, "IdleH", 1)
    spring = {"x": 1000, "y": 600, "w": 16, "xv": -0x1000, "sst": 0xFFB000}
    # launch_side_of -> -1, so the back face is on the +x side at BACK_DX. Hold him outside
    # the 18px face until the last sampled frame, then put him inside it.
    xs = [spring["x"] + W.BACK_DX] * (W.BACK_FRAMES - 1) + [spring["x"] + 10]
    pr = _FakeProbe(xs, anim=7)                       # 7 != the idle id: the hook ran
    out = []
    fails = asyncio.run(W.test_back_face(pr, spring, -2560, out, "C1"))
    assert any("the launch hook RAN" in f for f in fails), fails
    assert any("push frame itself was not observed" in f for f in fails), fails


def test_c1_with_no_finding_and_no_push_frame_still_refuses(monkeypatch):
    """The control: nothing measured wrong and the push unobserved is still Unmeasurable."""
    monkeypatch.setitem(W._TOUCH, "w", 20)
    monkeypatch.setitem(W._ANIM, "Idle", 0)
    monkeypatch.setitem(W._ANIM, "IdleH", 1)
    spring = {"x": 1000, "y": 600, "w": 16, "xv": -0x1000, "sst": 0xFFB000}
    xs = [spring["x"] + W.BACK_DX] * (W.BACK_FRAMES - 1) + [spring["x"] + 10]
    pr = _FakeProbe(xs, anim=1)                       # idle for a horizontal spring
    with pytest.raises(W.Unmeasurable, match="last sampled frame"):
        asyncio.run(W.test_back_face(pr, spring, -2560, [], "C1"))
