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


# ------------------------------------------------------- the row SET (GATES-EXPECTED-ROWSET)
#
# The parcel: `OK — N gates` printed `len(results)`, which is neither a gate count nor a
# population. Rows now carry the gate that produced them and the run asserts a SET derived
# from `wanted()`. Everything below drives `check_row_coverage` / `report` directly — no
# emulator, no lane. See the ROW SET block in effects_gates.py for R1/R2/R3.
REG = {n for n, _, _ in eg.gate_registry()}


def _rows(final_for=REG, skip=()):
    """One complete, passing row per registry gate — the shape a fully green lane emits."""
    return [eg.row(g, f"{g} row", True, "m", final=(g in final_for))
            for g in sorted(REG) if g not in skip]


def test_coverage_is_silent_when_every_scheduled_gate_produced_a_final_row():
    assert eg.check_row_coverage(REG, _rows()) == []


def test_coverage_names_the_GATE_that_produced_no_row():
    """THE PARCEL. This is the state `OK — N gates` rendered as a smaller green."""
    victim = "raster_source"
    probs = eg.check_row_coverage(REG, _rows(skip={victim}))
    assert [g for g, _ in probs] == [victim]
    assert f"`{victim}`" in probs[0][1] and "PRODUCED NO ROW" in probs[0][1]


def test_coverage_stays_silent_when_a_gate_emits_FEWER_rows_BECAUSE_IT_FAILED():
    """The distinguishing case, and the one a weak version cannot get right.

    A scene that fails determinism `continue`s past its shape row, so it legitimately emits 1
    row where a passing scene emits 2. That must NOT read as a gate that went missing.
    """
    rows = _rows(skip={"scene:mid_band"})
    rows.append(eg.row("scene:mid_band", "scene:mid_band determinism", False, "runs differed"))
    assert eg.check_row_coverage(REG, rows) == []


def test_coverage_catches_an_all_PASS_gate_that_never_reached_its_terminal_row():
    """The other half of that pair: fewer rows with NOTHING failing is a gate gone dark."""
    rows = _rows(skip={"scene:mid_band"})
    rows.append(eg.row("scene:mid_band", "scene:mid_band determinism", True, "identical"))
    probs = eg.check_row_coverage(REG, rows)
    assert [g for g, _ in probs] == ["scene:mid_band"]
    assert "EVERY ONE PASS" in probs[0][1] and "final=True" in probs[0][1]


def test_coverage_expectation_is_exactly_what_ONLY_selected():
    """An `--only` run legitimately emits a subset; the expectation must shrink with it."""
    assert eg.check_row_coverage({"demo_witness"},
                                 [eg.row("demo_witness", "x", True, "m", final=True)]) == []


def test_coverage_rejects_a_row_from_a_gate_the_run_did_not_schedule():
    probs = eg.check_row_coverage({"demo_witness"},
                                  [eg.row("demo_witness", "x", True, "m", final=True),
                                   eg.row("raster_off", "y", True, "m", final=True)])
    assert [g for g, _ in probs] == ["raster_off"]
    assert "did not schedule" in probs[0][1]


def test_a_gate_that_FAILS_its_terminal_row_is_still_complete():
    """`final` marks the terminal EMIT SITE, not a verdict; a red gate is not an absent one."""
    rows = _rows(skip={"raster_off"})
    rows.append(eg.row("raster_off", "raster_off", False, "teardown left the handler armed",
                       final=True))
    assert eg.check_row_coverage(REG, rows) == []


# --------------------------------------------------------------------------- output contract
def test_report_final_line_names_the_GATE_SET_not_the_row_count(capsys):
    """`tools/nightly_effects_gates.sh` consumes the exit code; humans read this line.

    It must not report a row count as a gate count — that is the whole defect. An extra row
    beyond one-per-gate must not change the gate accounting.
    """
    rows = _rows() + [eg.row("demo_witness", "demo_witness second row", True, "m")]
    rc = eg.report(rows, REG)
    out = capsys.readouterr().out
    assert rc == 0
    assert f"OK — all {len(REG)} scheduled gate(s) produced a complete row set" in out
    assert f"({len(rows)} result rows" in out and "NOT the witness" in out
    assert "OK — %d gates" % len(rows) not in out


def test_report_refuses_to_print_OK_when_a_scheduled_gate_produced_no_row(capsys):
    """`report` runs the coverage check itself, so no path can print a verdict without it."""
    rc = eg.report(_rows(skip={"cost_model"}), REG)
    out = capsys.readouterr().out
    assert rc == 1
    assert "ROW-SET COVERAGE — cost_model" in out and "PRODUCED NO ROW" in out
    assert "effects_gates: OK" not in out


def test_report_final_line_on_failure(capsys):
    rc = eg.report([eg.row("raster_off", "a", True, "m", final=True),
                    eg.row("raster_source", "b", False, "why", final=True)],
                   {"raster_off", "raster_source"})
    out = capsys.readouterr().out
    assert rc == 1 and "effects_gates: FAIL — 1 of 2 row(s), over 2 of 2 scheduled gate(s)" in out
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
    # ONE ROW PER GATE the segment left unmeasured, each tagged with that gate. This is what
    # keeps a wedge from reading as a missing gate under R1: the gate does produce a row, and
    # that row fails, so the reader is told WHICH state they are in rather than shown a
    # smaller total. A "ROW-SET COVERAGE" row here would mean the two had been conflated.
    assert "effects_gates: FAIL — 2 of 2 row(s), over 2 of 2 scheduled gate(s)" in out
    assert "ROW-SET COVERAGE" not in out, "a wedge is a named failure, NOT a missing gate"
    assert "`demo_witness`" in out and "`scanline_spans`" in out


def test_segmented_parent_checks_the_row_set_it_aggregated(monkeypatch, capsys):
    """The PARENT half of the row-set check, end to end and with no emulator.

    Drives the real `listing` segment as a real `--only` child, aggregates its rows across the
    JSON seam, and asserts the parent's own coverage check passes over the partition it
    scheduled. The twelve emulator segments cannot be exercised from pytest (each boots a
    headless emulator); this shares every line of the aggregation path with them.
    """
    rom, lst = eg.AEON / "s4.debug.bin", eg.AEON / "s4.debug.lst"
    dlst = eg.AEON / "demo.debug.lst"
    if not (rom.is_file() and lst.is_file() and dlst.is_file()):
        pytest.skip("needs DEBUG builds of BOTH fixtures (s4.debug.* and demo.debug.lst)")
    listing = [s for s in eg.segments() if s[0] == "listing"]
    assert len(listing) == 1 and len(listing[0][1]) > 1, "the listing segment moved"
    monkeypatch.setattr(eg, "segments", lambda: listing)
    rc = eg.run_segmented(Namespace(rom=str(rom), lst=str(lst), demo_lst=str(dlst)))
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "ROW-SET COVERAGE" not in out, out
    assert f"OK — all {len(listing[0][1])} scheduled gate(s) produced a complete row set" in out
    # The row count is REPORTED but no longer sold as the witness.
    assert "NOT the witness" in out


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
    # `[gate, label, ok, msg, final]` — the gate tag has to survive the JSON seam or the
    # parent's aggregate row-set check has nothing to attribute a segment's rows to.
    assert len(rows) == 1
    assert rows[0][eg.ROW_GATE] == "demo_witness"
    assert isinstance(rows[0][eg.ROW_OK], bool) and rows[0][eg.ROW_FINAL] is True


# --------------------------------------------------------------------------- scene resolution
# The committed scenes name SYMBOLS and carry a placeholder for the listing; the listing under
# test is substituted at run time. Until 2026-08-26 every scene hardcoded the MAIN tree's
# `s4.debug.lst`, so a worktree's gates resolved master's RAM addresses (the showcase parcel
# moved Raster_Buf_A/_B by +84 B and all four scene:* shape gates failed on a stale capture).

def _all_scene_names():
    return list(eg.SCENES) + [eg.DENSE_SCENE]


def test_every_committed_scene_carries_the_placeholder_not_a_listing():
    for name in _all_scene_names():
        sc = json.loads(eg.scene_path(name).read_text())
        assert sc.get("symbols") == eg.SCENE_SYMBOLS_PLACEHOLDER, (
            f"{eg.scene_path(name)}: symbols = {sc.get('symbols')!r} — a committed scene must "
            f"not name a listing; the gate resolves it against --lst")
        # And every poke / capture is by NAME, so the placeholder is load-bearing.
        for step in sc["steps"]:
            if "poke" in step:
                assert "symbol" in step["poke"] and "addr" not in step["poke"], step
        for region in sc["capture"].get("memory_read", []) + sc["capture"].get("memory_hash", []):
            assert "symbol" in region and "addr" not in region, region


def test_resolve_scene_substitutes_the_listing_under_test(tmp_path):
    lst = tmp_path / "some.debug.lst"
    lst.write_text("(0) 1/FFFF0000 :        Whatever:\n")
    out = tmp_path / "run"
    for name in _all_scene_names():
        resolved = eg.resolve_scene(name, str(lst), out / name)
        sc = json.loads(resolved.read_text())
        assert sc["symbols"] == str(lst.resolve())
        committed = json.loads(eg.scene_path(name).read_text())
        committed["symbols"] = sc["symbols"]
        assert sc == committed, "resolution changed something other than `symbols`"


def test_resolve_scene_refuses_a_hardcoded_listing_and_a_missing_one(tmp_path, monkeypatch):
    """RED-FIRST for the defect: a scene spelling the main tree's listing is refused, not
    silently run against another tree's addresses; a listing that does not exist is refused
    because ab_runner would then poke nothing and still report ALL EQUAL."""
    stale = tmp_path / "effects_raster_stale.json"
    sc = json.loads(eg.scene_path("mid_band").read_text())
    sc["symbols"] = "/home/volence/sonic_hacks/aeon/s4.debug.lst"
    stale.write_text(json.dumps(sc))
    monkeypatch.setattr(eg, "scene_path", lambda name: stale)
    lst = tmp_path / "x.lst"
    lst.write_text("")
    with pytest.raises(ValueError, match="must not name a listing"):
        eg.resolve_scene("stale", str(lst), tmp_path / "o")
    sc["symbols"] = eg.SCENE_SYMBOLS_PLACEHOLDER
    stale.write_text(json.dumps(sc))
    with pytest.raises(FileNotFoundError, match="listing under test not found"):
        eg.resolve_scene("stale", str(tmp_path / "absent.lst"), tmp_path / "o")
    assert eg.resolve_scene("stale", str(lst), tmp_path / "o").is_file()
