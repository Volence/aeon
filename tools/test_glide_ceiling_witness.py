#!/usr/bin/env python3
"""tools/glide_ceiling_witness.py: a measured failure outranks a later leg's refusal.

KEEPALIVE-IS-BLIND-TO-LOSSY (docs/research/2026-09-25-keepalive-lossy.md). Legs A, B and C
each boot Knuckles afresh and run their own model control before grading, so a finding leg
A returns is valid whatever B or C later says. Until 2026-09-25 the three results were only
combined after all three returned, so B or C raising Unmeasurable threw A's measured
failure away and the run exited 2. These rows run the SHIPPED main() and main_async() with
the machine and the three legs replaced by fakes: no emulator, no build artifact.
"""

import contextlib

import glide_ceiling_witness as G


class _FakeClient:
    def __init__(self, **kw):
        pass

    async def connect(self):
        pass

    async def close(self):
        pass


class _FakeModel:
    def __init__(self, lrb, top):
        pass

    def probe_up(self, layer, x, y):
        return 8


def _stub_machine(monkeypatch, tmp_path, leg_b):
    rom, lst = tmp_path / "x.bin", tmp_path / "x.lst"
    rom.write_bytes(b"\0" * 16)
    lst.write_text("")
    monkeypatch.setattr(G.sys, "argv", ["glide_ceiling_witness.py", "--rom", str(rom),
                                        "--lst", str(lst)])
    monkeypatch.setattr(G, "parse_lst", lambda path: ({}, {"SOLID_LRB": 1, "SOLID_TOP": 2}))

    @contextlib.contextmanager
    def fake_emulator(rom, symbols=None):
        yield "fake.sock"

    monkeypatch.setattr(G, "aether_emulator", fake_emulator)
    monkeypatch.setattr(G, "BusClient", _FakeClient)
    monkeypatch.setattr(G, "decode_playerv", lambda rom, syms: (0x20, 0x21))
    monkeypatch.setattr(G, "TerrainModel", _FakeModel)
    monkeypatch.setattr(G, "Drive", lambda *a, **k: object())

    async def leg_a(drv, model, out, verbose):
        return {"fails": ["A: MEASURED HEAD-IN-CEILING THAT MUST SURVIVE"]}

    async def leg_c(drv, model, out, verbose):
        raise AssertionError("leg C must not run after leg B raised")

    monkeypatch.setattr(G, "leg_a", leg_a)
    monkeypatch.setattr(G, "leg_b", leg_b)
    monkeypatch.setattr(G, "leg_c", leg_c)


def test_leg_b_refusing_does_not_discard_leg_a_measured_failure(monkeypatch, tmp_path, capsys):
    async def leg_b(drv, model, out, verbose):
        raise G.Unmeasurable("NO SUBJECT: the two designs do not disagree here")

    _stub_machine(monkeypatch, tmp_path, leg_b)
    rc = G.main()
    text = capsys.readouterr().out
    assert rc == 1, f"leg A's measured failure followed by leg B's refusal exited {rc}:\n{text}"
    assert "MEASURED HEAD-IN-CEILING THAT MUST SURVIVE" in text
    assert "NO SUBJECT" in text, "the refusal that stopped the run must still be named"


def test_a_refusal_with_nothing_failed_is_still_unmeasurable(monkeypatch, tmp_path, capsys):
    """The control: with no measured failure, a refusal is still exit 2."""
    async def leg_b(drv, model, out, verbose):
        raise G.Unmeasurable("MODEL CONTROL: the model is not the engine's probe")

    _stub_machine(monkeypatch, tmp_path, leg_b)

    async def leg_a(drv, model, out, verbose):
        return {"fails": []}

    monkeypatch.setattr(G, "leg_a", leg_a)
    assert G.main() == 2
    assert "UNMEASURABLE: MODEL CONTROL" in capsys.readouterr().out


def test_three_clean_legs_still_pass(monkeypatch, tmp_path, capsys):
    """The refactor's own control: the ordinary path still reaches PASS and exit 0."""
    async def leg_b(drv, model, out, verbose):
        return {"fails": [], "release_head_dist": 2}

    _stub_machine(monkeypatch, tmp_path, leg_b)

    async def leg_a(drv, model, out, verbose):
        return {"fails": [], "contact": 1, "ejected": 1}

    async def leg_c(drv, model, out, verbose):
        return {"fails": [], "release_feet": -5}

    monkeypatch.setattr(G, "leg_a", leg_a)
    monkeypatch.setattr(G, "leg_c", leg_c)
    assert G.main() == 0
    assert "RESULT: PASS" in capsys.readouterr().out
