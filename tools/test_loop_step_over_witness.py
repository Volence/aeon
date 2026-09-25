#!/usr/bin/env python3
"""tools/loop_step_over_witness.py: a drive that reached ErrorHandler is not a clean exit.

KEEPALIVE-IS-BLIND-TO-LOSSY (docs/research/2026-09-25-keepalive-lossy.md). drive() records
a fault row and stops, summarise() prints "FAULTED at frame N", and main() returned 0 anyway,
so the `#no-assert-grounded` keepalive row (declared `expect = 0`) stayed PASSED over a ROM
that crashed mid-drive. In --phase-sweep the quiet path dropped fault rows altogether.

These rows run the SHIPPED main() -> run_one() -> summarise() with only drive() and the
emulator faked, so no emulator boots and no build artifact is read.
"""

import contextlib

import pytest

import loop_step_over_witness as L

EQUS = {"PHYS_TOP_SPEED": 0x600, "COLL_CELL_W": 8, "PHYS_GSP_CAP": 0x1000}


def _live(n):
    return [{"frame": f, "x": 1097 + 4 * f, "y": 585, "layer": 0, "angle": 0, "gsp": 0x600}
            for f in range(n)]


def _stub(monkeypatch, rows, extra_argv):
    monkeypatch.setattr(L, "parse_lst", lambda lst: ({}, dict(EQUS)))

    @contextlib.contextmanager
    def fake_emulator(rom, symbols=None):
        yield "fake.sock"

    async def fake_drive(*a, **k):
        return list(rows)

    monkeypatch.setattr(L, "aether_emulator", fake_emulator)
    monkeypatch.setattr(L, "drive", fake_drive)
    monkeypatch.setattr(L.sys, "argv", ["loop_step_over_witness.py", "--rom", "x.bin",
                                        "--lst", "x.lst"] + extra_argv)


FAULT = {"frame": 5, "fault": "ErrorHandler", "pc": "0x000200"}


@pytest.mark.parametrize("argv", [["--no-assert-grounded"], ["--phase-sweep"], []])
def test_a_drive_that_faulted_exits_1(monkeypatch, capsys, argv):
    _stub(monkeypatch, _live(5) + [FAULT], argv)
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 1, f"a drive that reached ErrorHandler exited {rc} under {argv}:\n{text}"
    assert "the ROM FAULTED" in text


@pytest.mark.parametrize("argv", [["--no-assert-grounded"], ["--phase-sweep"], []])
def test_a_drive_that_ran_to_its_end_still_exits_0(monkeypatch, capsys, argv):
    """The control: the witness still reports rather than grades when nothing faulted."""
    _stub(monkeypatch, _live(90), argv)
    assert L.main() == 0
