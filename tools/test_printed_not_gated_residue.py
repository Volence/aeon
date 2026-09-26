"""PRINTED-NOT-GATED residue (2026-09-26): the hand-run probes whose failure or "nothing was
tested" path printed a verdict and exited 0. The rows here are the ones that can be graded
without an emulator; the emulator-bound ones (parallax_cost_probe, poke_storm, the engine
baseline probe, crossing_witness, perspective_floor_witness, ramp_boundary_probe) were proved
red-first by a mutated run against a built ROM, recorded in docs/DEFERRED_WORK.md.

Nothing here boots an emulator: sec5's main() is stopped at the point it would start one.
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))


# ---------------------------------------------------------------- sec5_band_witness ----
class _WouldBoot(Exception):
    pass


def _run_sec5(monkeypatch, tmp_path, lines, band=(96, 112)):
    import sec5_band_witness as W

    rom = tmp_path / "s4.debug.bin"
    rom.write_bytes(b"\0" * 64)
    top, bot = band
    exp = {"top": top, "bot": bot, "cram_line": 2, "cram_entry": 5, "cram_addr": 0x4A,
           "colour": 0x0EE, "preset_id": "p"}
    monkeypatch.setattr(W, "geometry", lambda repo: {"size": 2048, "shift": 11, "grid_w": 4,
                                                     "grid_h": 2, "screen_w": 320,
                                                     "screen_h": 224})
    monkeypatch.setattr(W, "sidecar_ref", lambda repo, sec: ("p", str(tmp_path / "s.json")))
    monkeypatch.setattr(W, "chooser_binding",
                        lambda repo, sec: ("EditorRaster_OJZ_Act1_p", ["arm"]))
    monkeypatch.setattr(W, "load_preset", lambda repo, pid: ({}, str(tmp_path / "p.json")))
    monkeypatch.setattr(W, "expectation", lambda preset, where: dict(exp))

    def boot(*a, **k):
        raise _WouldBoot()
    monkeypatch.setattr(W, "AetherInstance", boot)
    monkeypatch.setattr(sys, "argv", ["sec5_band_witness", "--rom", str(rom), "--repo",
                                      str(tmp_path), "--label", "t", "--out-dir",
                                      str(tmp_path / "out"), "--lines",
                                      ",".join(str(v) for v in lines)])
    return W.main


def test_sec5_plan_with_no_in_band_line_is_refused_before_boot(monkeypatch, tmp_path):
    # The band is 96..111 and every line is outside it: the run used to sample only the
    # base, match every expectation and exit 0.
    main = _run_sec5(monkeypatch, tmp_path, [8, 20, 40, 150])
    with pytest.raises(SystemExit) as ei:
        main()
    assert ei.value.code == 2


def test_sec5_plan_with_no_out_of_band_line_is_refused(monkeypatch, tmp_path):
    main = _run_sec5(monkeypatch, tmp_path, [96, 100])
    with pytest.raises(SystemExit) as ei:
        main()
    assert ei.value.code == 2


def test_sec5_a_plan_that_straddles_the_band_reaches_the_emulator(monkeypatch, tmp_path):
    # The control: the default-shaped plan passes the plan check and goes on to boot.
    main = _run_sec5(monkeypatch, tmp_path, [8, 100, 150])
    with pytest.raises(_WouldBoot):
        main()


# ------------------------------------------------------------- hblank_window_sweep ----
def test_hblank_anchor_breach_exits_1_and_inside_exits_0():
    import hblank_window_sweep as H

    def rep(outside):
        return {"hblank_end_rederived": {"measured": 380.0, "delta": 14.0, "shipped": 366,
                                         "margin_early_cyc": 6, "margin_late_cyc": 9,
                                         "outside_margin": outside}}
    assert H.anchor_breach(rep(True)) == 1
    assert H.anchor_breach(rep(False)) == 0
    assert H.anchor_breach({}) == 0


def test_hblank_replay_returns_the_breach(monkeypatch, tmp_path):
    """End to end through --replay: summarize() is stubbed to record a breach, as the
    sub-line re-derivation does, and the exit must carry it (it was `return 0`)."""
    import hblank_window_sweep as H

    rec = tmp_path / "w.json"
    rec.write_text(json.dumps({"sweep": [{"n": 0, "flip_x_prev": -1}], "cram_addr": 0x50,
                               "burst_words": 1}))

    def summarize(report, fx):
        report["hblank_end_rederived"] = {"measured": 380.0, "delta": 14.0, "shipped": 366,
                                          "margin_early_cyc": 6, "margin_late_cyc": 9,
                                          "outside_margin": True}
    monkeypatch.setattr(H, "summarize", summarize)
    monkeypatch.setattr(sys, "argv", ["hblank_window_sweep", "--replay", str(rec)])
    assert H.main() == 1


# ---------------------------------------------------------------------- vgm_onsets ----
def _vgm(tmp_path, body: bytes) -> Path:
    hdr = bytearray(0x40)
    hdr[0:4] = b"Vgm "
    struct.pack_into("<I", hdr, 0x08, 0x150)
    struct.pack_into("<I", hdr, 0x2C, 7670453)
    struct.pack_into("<I", hdr, 0x34, 0x40 - 0x34)
    p = tmp_path / "cap.vgm"
    p.write_bytes(bytes(hdr) + body + b"\x66")
    return p


def test_vgm_onsets_silent_capture_is_could_not_run(tmp_path):
    p = _vgm(tmp_path, b"\x62\x62")                       # two waits, no key-on
    r = subprocess.run([sys.executable, str(TOOLS / "vgm_onsets.py"), str(p)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "COULD NOT RUN" in r.stdout, r.stdout


def test_vgm_onsets_a_key_on_is_parsed_and_exits_0(tmp_path):
    body = b"\x52\xa4\x22" + b"\x52\xa0\x69" + b"\x52\x28\xf0" + b"\x62"
    p = _vgm(tmp_path, body)
    r = subprocess.run([sys.executable, str(TOOLS / "vgm_onsets.py"), str(p)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "total key-on events: 1" in r.stdout, r.stdout
