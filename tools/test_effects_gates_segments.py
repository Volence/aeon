"""The gate lane's SEGMENTATION — the partition, the ownership matcher, the wedge path.

None of this tests a gate. It tests the scheduler that runs them, which is the part that broke:
one wedged emulator used to take all 22 results down with it and print nothing.

The wedge test is the load-bearing one and it is red-first by construction — it drives a real
child process into a real hang and asserts the lane retries once and then reports a NAMED
failure. A lane that went silent on a wedge would fail it.
"""
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import effects_gates as eg  # noqa: E402

TOOL = Path(__file__).resolve().parent / "effects_gates.py"


# --------------------------------------------------------------------------- the partition
def test_segments_cover_the_registry_exactly_and_in_order():
    """Every registered gate is scheduled exactly once, in the body's own run order.

    This is the anti-drift assertion at the partition layer: a gate that no segment names is a
    gate no default run executes, and the totals line cannot tell that from a pass.
    """
    reg = [n for n, _, _ in eg.gate_registry()]
    scheduled = [n for _, names, _ in eg.segments() for n in names]
    assert scheduled == reg


def test_every_emulator_gate_is_its_own_segment():
    """The emulator gate is the unit that wedges, so isolation is the whole mechanism."""
    emu = {n for n, is_emu, _ in eg.gate_registry() if is_emu}
    solo = {names[0] for _, names, _ in eg.segments() if len(names) == 1}
    assert emu <= solo, f"emulator gates sharing a segment: {sorted(emu - solo)}"


def test_listing_only_gates_share_one_segment():
    """They boot nothing and cannot wedge; a process spawn each would be pure waste."""
    listing = {n for n, is_emu, _ in eg.gate_registry() if not is_emu}
    segs = [names for _, names, _ in eg.segments() if set(names) & listing]
    assert len(segs) == 1 and set(segs[0]) == listing


def test_every_segment_has_a_positive_timeout():
    """A zero/absent budget would make the segment wedge-detect instantly and retry forever."""
    assert all(t > 0 for _, _, t in eg.segments())


# --------------------------------------------------------------------------- drift detection
def test_drift_check_is_silent_when_registry_and_body_agree():
    assert eg.check_registry_drift({n for n, _, _ in eg.gate_registry()}) == ""


def test_drift_check_names_a_gate_the_registry_would_never_schedule():
    queried = {n for n, _, _ in eg.gate_registry()} | {"brand_new_gate"}
    assert "brand_new_gate" in eg.check_registry_drift(queried)


def test_drift_check_names_a_registry_entry_the_body_dropped():
    reg = [n for n, _, _ in eg.gate_registry()]
    assert reg[0] in eg.check_registry_drift(set(reg[1:]))


# --------------------------------------------------------- oracle ownership (the pkill trap)
# The real pair of paths this tree runs concurrently. A bare `pkill oracle_gui` kills both, and
# so does any substring test on the shorter one — which is how another session's measurement
# got killed twice on 2026-08-19.
MAIN_ROM = b"/home/volence/sonic_hacks/aeon/s4.debug.bin"
TREE_ROM = b"/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-x/s4.debug.bin"
GUI = b"/home/volence/sonic_hacks/oracle-old/linux-port/build/oracle_gui"


def _argv(rom: bytes) -> list[bytes]:
    """Exactly how launcher.headless_emulator spells it."""
    return [GUI, b"/tmp/oracle-harness-abc/settings.xml", rom]


def test_ownership_matches_our_own_rom():
    assert eg.owns_rom(_argv(TREE_ROM), TREE_ROM)


def test_ownership_does_not_match_another_worktrees_rom():
    """The whole point: our reaper must never touch a parallel session's emulator."""
    assert not eg.owns_rom(_argv(MAIN_ROM), TREE_ROM)
    assert not eg.owns_rom(_argv(TREE_ROM), MAIN_ROM)


def test_ownership_is_token_equality_not_substring():
    """A substring test would match, because one ROM path contains the other's directory."""
    assert MAIN_ROM.rsplit(b"/", 1)[0] in TREE_ROM      # the trap is real...
    assert not eg.owns_rom(_argv(TREE_ROM), MAIN_ROM)   # ...and the matcher does not fall in


def test_ownership_ignores_non_oracle_processes_carrying_the_rom_path():
    """The gate tool and xvfb-run both carry the ROM path in argv; neither is the emulator."""
    assert not eg.owns_rom([b"/usr/bin/python3", b"snapshot_poison_gate.py",
                            b"--rom", TREE_ROM], TREE_ROM)
    assert not eg.owns_rom([b"/bin/sh", b"/usr/bin/xvfb-run", b"-a", GUI, TREE_ROM], TREE_ROM)


# --------------------------------------------------------------------------- output contract
def test_report_final_line_on_success(capsys):
    """`tools/nightly_effects_gates.sh` consumes the exit code and this line. Do not drift it."""
    rc = eg.report([["a", True, "m"], ["b", True, "m"]])
    assert rc == 0 and "effects_gates: OK — 2 gates" in capsys.readouterr().out


def test_report_final_line_on_failure(capsys):
    rc = eg.report([["a", True, "m"], ["b", False, "why"]])
    out = capsys.readouterr().out
    assert rc == 1 and "effects_gates: FAIL — 1 of 2 gate(s)" in out
    assert "FAIL  b" in out and "why" in out


# --------------------------------------------------------------------------- the wedge path
def test_unknown_only_name_is_rejected_rather_than_silently_running_nothing():
    """A typo'd/renamed gate used to run zero gates and exit 0 — a vacuous pass."""
    p = subprocess.run([sys.executable, str(TOOL), "--only", "no_such_gate",
                        "--rom", "/nonexistent/s4.debug.bin"],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "no_such_gate" in p.stderr


def test_wedged_segment_retries_once_then_reports_a_named_failure(tmp_path, monkeypatch, capsys):
    """RED-FIRST EVIDENCE for the whole parcel.

    A poisoned segment hangs exactly as an oracle stop-race hangs it. The lane must: time it
    out, retry it ONCE, and then emit its own named row — never silence, and never a pass.
    """
    seg = ("listing", ["scanline_spans", "demo_witness"], 3)
    monkeypatch.setattr(eg, "segments", lambda: [seg])
    monkeypatch.setenv("EFFECTS_GATES_POISON_WEDGE", "listing")
    monkeypatch.setenv("EFFECTS_GATES_POISON_TIMEOUT", "3")
    rc = eg.run_segmented(Namespace(rom=str(tmp_path / "s4.debug.bin"),
                                    lst=str(tmp_path / "s4.debug.lst"),
                                    demo_lst=str(tmp_path / "demo.debug.lst")))
    out = capsys.readouterr().out
    assert rc == 1, "a wedge must FAIL the lane, never pass it"
    assert "WEDGED after retry" in out, "the wedge must be its own named failure row"
    assert "scanline_spans" in out, "the row must name the gates left unmeasured"
    assert out.count("retrying once") == 1, "exactly one retry, not zero and not a loop"
    assert "effects_gates: FAIL — 1 of 1 gate(s)" in out


def test_poison_is_inert_without_the_env_var(tmp_path, monkeypatch):
    """The test-only hook must not be reachable on a normal run."""
    monkeypatch.delenv("EFFECTS_GATES_POISON_HANG", raising=False)
    p = subprocess.run([sys.executable, str(TOOL), "--only", "scanline_spans",
                        "--rom", "/nonexistent/s4.debug.bin"],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 2 and "ROM not found" in p.stderr


def test_parent_never_leaks_the_poison_selector_into_a_child(tmp_path, monkeypatch, capsys):
    """Only the NAMED segment may hang; the selector must not be inherited wholesale."""
    calls = []

    def fake_popen(cmd, **kw):
        calls.append(kw["env"])
        raise RuntimeError("stop here")

    monkeypatch.setenv("EFFECTS_GATES_POISON_WEDGE", "listing")
    monkeypatch.setattr(eg.subprocess, "Popen", fake_popen)
    with pytest.raises(RuntimeError):
        eg.run_one_segment(["scanline_spans"], 5,
                           Namespace(rom="r", lst="l", demo_lst="d"), poison=False)
    assert "EFFECTS_GATES_POISON_WEDGE" not in calls[0]
    assert "EFFECTS_GATES_POISON_HANG" not in calls[0]


def test_segment_child_writes_its_rows_as_json(tmp_path):
    """The aggregation transport: rows travel as data, not as scraped stdout."""
    jf = tmp_path / "rows.json"
    rom = Path(eg.AEON / "s4.debug.bin")
    if not rom.is_file():
        pytest.skip("needs a DEBUG build (s4.debug.bin)")
    p = subprocess.run([sys.executable, str(TOOL), "--rom", str(rom),
                        "--lst", str(eg.AEON / "s4.debug.lst"),
                        "--only", "demo_witness", "--emit-results", str(jf)],
                       capture_output=True, text=True, timeout=300)
    assert jf.is_file(), p.stdout + p.stderr
    rows = json.loads(jf.read_text())
    assert len(rows) == 1 and isinstance(rows[0][1], bool)
