#!/usr/bin/env python3
"""tools/dplc_coherence_witness.py: a drive that FAULTED part-way is not a clean exit.

KEEPALIVE-IS-BLIND-TO-LOSSY (docs/research/2026-09-25-keepalive-lossy.md). drive() records a
fault row and stops, report() prints "FAULTED", and main() returned 0 regardless, so the
keepalive row (declared `expect = 0`) stayed PASSED over a ROM that crashed mid-drive.

These rows run the SHIPPED main() with the models, the machine and the report faked: no
emulator boots and no build artifact is read. Only the fault is graded -- see
drive_verdict's SCOPE note for what is still printed and not graded.
"""

import contextlib
from types import SimpleNamespace

import pytest

import dplc_coherence_witness as D


def _stub(monkeypatch, tmp_path, rows):
    rom = tmp_path / "x.bin"
    rom.write_bytes(b"\0" * 64)
    monkeypatch.setattr(D.sys, "argv", ["dplc_coherence_witness.py", "--rom", str(rom),
                                        "--lst", str(tmp_path / "x.lst")])
    monkeypatch.setattr(D, "parse_lst", lambda path: (
        {"DPLC_Sonic": 0, "Art_Sonic": 0, "Map_Sonic": 0}, {}))
    monkeypatch.setattr(D, "DplcModel", lambda rom, dplc, art: SimpleNamespace(
        frames=1, entries=lambda f: 3))
    monkeypatch.setattr(D, "MapModel", lambda rom, m: SimpleNamespace())
    monkeypatch.setattr(D, "TiltPopulation", lambda rom, lst: SimpleNamespace(
        error="faked in the test"))
    monkeypatch.setattr(D, "TileAttribution", lambda model: SimpleNamespace(
        by_slot=[0], discriminating=lambda f: (1,)))

    @contextlib.contextmanager
    def fake_emulator(rom, symbols=None):
        yield "fake.sock"

    async def fake_drive(*a, **k):
        return list(rows), []

    monkeypatch.setattr(D, "aether_emulator", fake_emulator)
    monkeypatch.setattr(D, "drive", fake_drive)
    monkeypatch.setattr(D, "report", lambda *a, **k: None)


LIVE = [{"frame": f} for f in range(10)]


@pytest.mark.parametrize("fault", [
    {"frame": 10, "fault": "ErrorHandler", "pc": "0x000200"},
    {"frame": 10, "fault": "run_to never reached the sample pc", "pc": "0x000400"},
])
def test_a_drive_that_faulted_exits_1(monkeypatch, tmp_path, capsys, fault):
    _stub(monkeypatch, tmp_path, LIVE + [fault])
    rc = D.main()
    text = capsys.readouterr().out
    assert rc == 1, f"a drive that recorded {fault['fault']!r} exited {rc}:\n{text}"
    assert "FAULTED at frame 10" in text


def test_a_drive_that_ran_to_its_end_still_exits_0(monkeypatch, tmp_path):
    """The control: the witness still reports rather than grades when nothing faulted."""
    _stub(monkeypatch, tmp_path, LIVE)
    assert D.main() == 0
