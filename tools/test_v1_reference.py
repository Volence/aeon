"""Tests for tools/v1_reference.py (v2 E1: the v1 behaviour reference).

Pure and synthetic: frame files are written by the module's own writer into tmp dirs and
diffed. The recordings themselves are made by the CLI against the pinned oracle (MANIFEST.json
under docs/benchmarks/v1-reference/ carries their provenance); nothing here boots an emulator.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import leg_drive as ld
import v1_reference as v1


def _rows(n=120, t0=300):
    out = []
    for k in range(n):
        t = t0 + k
        out.append(dict(tick=t, held=0x08 if k % 50 else 0x28, fb=f"{t * 7919:016x}",
                        vdp=f"{t * 104729:016x}", obj_ram=f"{t * 31:016x}",
                        game_ram=f"{t * 37:016x}", px=96 + k * 3, py=700 - (k % 9),
                        xvel=k * 12, yvel=-(k % 5), status=k & 0x06, cx=k * 3, cy=600,
                        lag_before=1 if k == 77 else 0))
    return out


def _put(root: Path, shape: str, leg: str, rows):
    d = root / shape
    d.mkdir(parents=True, exist_ok=True)
    v1.write_frames(d / f"{leg}.frames.jsonl.gz", rows)


def _pair(tmp_path, legs=("idle", "run"), shapes=("s4", "s4.debug")):
    ref, run = tmp_path / "ref", tmp_path / "run"
    for sh in shapes:
        for leg in legs:
            _put(ref, sh, leg, _rows())
            _put(run, sh, leg, _rows())
    return ref, run


# ---- the brief's four -----------------------------------------------------------------------

def test_diff_identical_is_none(tmp_path):
    ref, run = _pair(tmp_path)
    rep = v1.diff(ref, run)
    assert set(rep.results) == {(s, l) for s in ("s4", "s4.debug") for l in ("idle", "run")}
    assert all(v is None for v in rep.results.values()), rep.results
    assert rep.ok


def test_diff_reports_first_divergent_tick_and_field(tmp_path):
    """Mutating px at tick 40 (of the leg; t0 + 40 here as Logic_Tick) gives (tick, "px").
    Later divergences in other fields do not move the answer: it is the FIRST tick."""
    ref, run = _pair(tmp_path)
    rows = _rows(t0=0)
    _put(ref, "s4", "run", rows)
    bad = [dict(r) for r in rows]
    bad[40]["px"] += 1
    bad[41]["obj_ram"] = "f" * 16           # a later, different divergence
    bad[90]["cx"] = -1
    _put(run, "s4", "run", bad)
    rep = v1.diff(ref, run)
    assert rep.results[("s4", "run")] == (40, "px")
    assert rep.results[("s4", "idle")] is None
    assert not rep.ok


def test_diff_semantic_only_ignores_ram_hashes(tmp_path):
    """A rebuilt engine with a different RAM layout differs on every raw hash and on none of
    the semantic fields: the semantic diff is None, the full diff is not."""
    ref, run = _pair(tmp_path, legs=("run",), shapes=("s4",))
    moved = [dict(r, fb="0" * 16, vdp="1" * 16, obj_ram="2" * 16, game_ram="3" * 16)
             for r in _rows()]
    _put(run, "s4", "run", moved)
    assert v1.diff(ref, run, fields=v1.SEMANTIC).results[("s4", "run")] is None
    assert v1.diff(ref, run).results[("s4", "run")] == (300, "fb")
    for h in v1.RAW_HASHES:
        assert h not in v1.SEMANTIC


def test_diff_missing_leg_is_did_not_run(tmp_path):
    ref, run = _pair(tmp_path)
    (run / "s4.debug" / "run.frames.jsonl.gz").unlink()
    rep = v1.diff(ref, run)
    assert rep.results[("s4.debug", "run")] == v1.DID_NOT_RUN
    assert not rep.ok, "a missing leg is never equal"
    # ... in either direction: a leg the reference lacks has nothing to be equal to
    _put(run, "s4", "spindash", _rows())
    rep = v1.diff(ref, run)
    assert rep.results[("s4", "spindash")] == v1.DID_NOT_RUN and not rep.ok


# ---- the rest of the gate's edges -----------------------------------------------------------

def test_diff_empty_frames_is_did_not_run(tmp_path):
    ref, run = _pair(tmp_path, legs=("idle",), shapes=("s4",))
    _put(run, "s4", "idle", [])
    _put(ref, "s4", "idle", [])
    assert v1.diff(ref, run).results[("s4", "idle")] == v1.DID_NOT_RUN


def test_diff_manifest_declared_leg_absent_from_both_is_did_not_run(tmp_path):
    ref, run = _pair(tmp_path, legs=("idle",), shapes=("s4",))
    (ref / "MANIFEST.json").write_text(json.dumps(
        {"recordings": {"s4/idle": {}, "s4/topspeed": {}}}))
    rep = v1.diff(ref, run)
    assert rep.results[("s4", "topspeed")] == v1.DID_NOT_RUN
    assert rep.results[("s4", "idle")] is None


def test_diff_shorter_run_diverges_at_its_first_missing_tick(tmp_path):
    ref, run = _pair(tmp_path, legs=("run",), shapes=("s4",))
    _put(run, "s4", "run", _rows()[:70])
    assert v1.diff(ref, run).results[("s4", "run")] == (370, v1.ROW_MISSING)
    _put(run, "s4", "run", _rows() + [dict(_rows()[-1], tick=420)])
    assert v1.diff(ref, run).results[("s4", "run")] == (420, v1.ROW_MISSING)


def test_diff_refuses_unknown_field(tmp_path):
    ref, run = _pair(tmp_path, legs=("run",), shapes=("s4",))
    with pytest.raises(ValueError, match="nope"):
        v1.diff(ref, run, fields=("px", "nope"))


def test_diff_cli_exit_codes(tmp_path, capsys):
    ref, run = _pair(tmp_path, legs=("run",), shapes=("s4",))
    assert v1.main(["diff", "--ref", str(ref), "--run", str(run)]) == 0
    bad = _rows()
    bad[5]["held"] ^= 0x20
    _put(run, "s4", "run", bad)
    assert v1.main(["diff", "--ref", str(ref), "--run", str(run)]) == 1
    assert "s4/run: DIVERGES at tick 305 on held" in capsys.readouterr().out
    (run / "s4" / "run.frames.jsonl.gz").unlink()
    assert v1.main(["diff", "--ref", str(ref), "--run", str(run)]) == 1
    assert "DID NOT RUN" in capsys.readouterr().out


def test_frames_roundtrip_and_deterministic_bytes(tmp_path):
    a, b = tmp_path / "a.jsonl.gz", tmp_path / "b.jsonl.gz"
    v1.write_frames(a, _rows())
    v1.write_frames(b, _rows())
    assert a.read_bytes() == b.read_bytes(), "gzip header must not carry a timestamp"
    assert v1.read_frames(a) == _rows()


def test_frame_row_has_exactly_the_brief_fields():
    assert v1.ROW_FIELDS == ("tick", "held", "fb", "vdp", "obj_ram", "game_ram", "px", "py",
                             "xvel", "yvel", "status", "cx", "cy", "lag_before")
    assert set(v1.ALL) == set(v1.ROW_FIELDS) - {"tick"}
    s = ld.TickState(tick=301, frame_counter=9, px=10, py=20, xvel=-3, yvel=4, gspeed=0,
                     airborne=False, cx=1, cy=2, cx_max=5824)
    drow = dict(t=301, dfc=2, dlt=1, held=0x08)
    row = v1.frame_row(s, drow, status_byte=0x02,
                       hashes=dict(fb="a", vdp="b", obj_ram="c", game_ram="d"))
    assert tuple(row) == v1.ROW_FIELDS
    assert row["lag_before"] == 1 and row["status"] == 2 and row["held"] == 8


# ---- recording refusals ---------------------------------------------------------------------

def test_record_refuses_a_dirty_tree_and_names_the_paths(tmp_path, monkeypatch):
    """Task 2 review carry-over: a reference is never written from a dirty aeon tree. The
    refusal names the dirty paths and nothing is written."""
    reaped = []

    class Inst:
        handshake = {}
        socket_path = "/nonexistent"

        def reap(self):
            reaped.append(1)

    monkeypatch.setattr(v1.ld, "resolve_syms", lambda lst: SimpleNamespace(buttons=B, equ={}))
    monkeypatch.setattr(v1, "_ram_spans", lambda syms: {})
    monkeypatch.setattr(v1.lp, "rom_sha256", lambda rom, *a, **k: "9" * 64)   # the sidecar gate has its own test
    monkeypatch.setattr(v1.lp, "spawn_pinned", lambda rom, lst: Inst())
    monkeypatch.setattr(v1.lp, "load_pin", lambda: None)
    monkeypatch.setattr(v1.lp, "provenance", lambda *a: {
        "aeon": {"commit": "c0ffee", "dirty": True, "dirty_count": 2, "branch": "b",
                 "dirty_paths": [" M engine/foo.emp", "?? stray.emp"]}})
    out = tmp_path / "out"
    with pytest.raises(v1.DirtyTree) as e:
        v1.record(tmp_path / "s4.bin", tmp_path / "s4.lst", "run", out)
    assert "engine/foo.emp" in str(e.value) and "stray.emp" in str(e.value)
    assert reaped == [1]
    assert not out.exists() or not any(out.rglob("*"))


def test_record_refuses_an_unknown_leg(tmp_path):
    with pytest.raises(ValueError, match="objheavy"):
        v1.record(tmp_path / "s4.bin", tmp_path / "s4.lst", "objheavy", tmp_path / "o")


# ---- the replay policy (leg_drive.Replay) ---------------------------------------------------

def _st(t):
    return ld.TickState(tick=t, frame_counter=t, px=0, py=0, xvel=0, yvel=0, gspeed=0,
                        airborne=False, cx=0, cy=0, cx_max=5824)


B = ld.Buttons(right=0x08, left=0x04, down=0x02, up=0x01, a=0x40, b=0x10, c=0x20)


def test_replay_policy_returns_the_logged_byte_for_each_tick():
    log = {"t0": 300, "held": [0, 0x08, 0x28, 0x10]}
    core = ld.LegCore(ld.Replay(log), t0=300, cap_ticks=4, debug=False, buttons=B)
    core.step(_st(299), 0)
    got = [core.step(_st(t), 0) for t in range(300, 304)]
    assert got == log["held"] and core.status == "CAP"
    assert core.input_log() == log


def test_replay_skips_the_debug_free_flight_exit():
    """In DEBUG, LegCore normally decides the first ticks itself (frozen-py watch, then B).
    A replay is open-loop: the log's bytes are applied from t0, the exit logic never runs."""
    log = {"t0": 300, "held": [0x08] * 20}
    core = ld.LegCore(ld.Replay(log), t0=300, cap_ticks=20, debug=True, buttons=B)
    core.step(_st(299), 0)
    got = [core.step(_st(t), 0) for t in range(300, 320)]
    assert got == [0x08] * 20 and core.policy_from == 300 and core.status == "CAP"


def test_replay_outside_the_log_is_loud():
    pol = ld.Replay({"t0": 300, "held": [1, 2]})
    with pytest.raises(ld.DriveError, match="outside the log"):
        pol.held(_st(302))
    with pytest.raises(ld.DriveError):
        ld.Replay({"t0": 300, "held": [256]})
    with pytest.raises(ld.DriveError):
        ld.Replay({"held": []})


# ---- the MANIFEST entry: coverage verdict + computed duplicate marking (fix round 1) -------

EQU = {"PHYS_TOP_SPEED": 0x600, "PHYS_ROLL_START_MIN": 0x100, "PSTATE_SPINDASH": 4,
       "ST_IN_AIR": 3, "ST_ROLLING": 4, "BUTTON_C": 0x20}


def _clean_prov():
    return {"oracle": {"commit": "dd09", "server_build_id": "dd09+profile=release",
                       "source": "vcs", "dirty": False, "sha256": "ab"},
            "aeon": {"commit": "c0ffee", "dirty": False, "dirty_count": 0, "branch": "b",
                     "dirty_paths": []},
            "rom": {"rom": "s4.bin", "romSha256": "9" * 64, "size": 1, "game": "sonic4",
                    "debug": 0, "target": "x", "sigil_revision": "7630"},
            "harness": {"tool_sha256": "cd"}}


def _fake_record(monkeypatch, drives):
    """record() with the emulator replaced: `drives[leg]` is (status, gs list, held list)."""
    class Inst:
        handshake = {}

        def reap(self):
            pass

    monkeypatch.setattr(v1.ld, "resolve_syms",
                        lambda lst: SimpleNamespace(buttons=B, equ=EQU, debug=False))
    monkeypatch.setattr(v1, "_ram_spans", lambda syms: {})
    monkeypatch.setattr(v1.lp, "rom_sha256", lambda rom, *a, **k: "9" * 64)   # the sidecar gate has its own test
    monkeypatch.setattr(v1.lp, "spawn_pinned", lambda rom, lst: Inst())
    monkeypatch.setattr(v1.lp, "load_pin", lambda: None)
    monkeypatch.setattr(v1.lp, "provenance", lambda *a: _clean_prov())
    leg_now = {}

    async def drive(inst, syms, spans, policy, t0, cap):
        status, gs, held = drives[leg_now["leg"]]
        trows, frows = [], []
        for k, (g, h) in enumerate(zip(gs, held)):
            t = t0 + k
            trows.append(dict(t=t, dfc=1, dlt=1, gs=g, cx=k, cy=0, yvel=0, ps=0, held=h))
            s = ld.TickState(tick=t, frame_counter=t, px=k, py=0, xvel=g, yvel=0, gspeed=g,
                             airborne=False, cx=k, cy=0, cx_max=5824)
            frows.append(v1.frame_row(s, trows[-1], 0, dict(fb="f", vdp="v", obj_ram="o",
                                                            game_ram="g")))
        tr = SimpleNamespace(rows=trows, input_log={"t0": t0, "held": list(held)},
                             status=status, reason="r", notes=[], lag_frames=0)
        return tr, frows

    monkeypatch.setattr(v1, "_drive", drive)
    return leg_now


def test_recorded_entry_carries_coverage_and_identical_inputs_get_identical_to(tmp_path,
                                                                               monkeypatch):
    fast = ([0x700] * 80, [0x08] * 80)
    leg_now = _fake_record(monkeypatch, {"run": ("FINISHED",) + fast,
                                         "topspeed": ("FINISHED",) + fast,
                                         "spindash": ("STUCK", [0] * 80, [0x02] * 80)})
    out = tmp_path / "ref"
    for leg in ("topspeed", "run", "spindash"):     # topspeed FIRST: the mark is order-free
        leg_now["leg"] = leg
        v1.record(tmp_path / "s4.bin", tmp_path / "s4.lst", leg, out)
    recs = json.loads((out / "MANIFEST.json").read_text())["recordings"]
    assert recs["s4/run"]["coverage"]["met"] is True and recs["s4/run"]["covered"] == "COVERED"
    assert recs["s4/topspeed"]["coverage"]["got"] == 80          # |gspeed| >= PHYS_TOP_SPEED
    assert recs["s4/spindash"]["coverage"]["met"] is False
    assert recs["s4/spindash"]["covered"] == "DID NOT COVER"
    assert recs["s4/topspeed"]["identical_to"] == "s4/run"
    assert "identical_to" not in recs["s4/run"] and "identical_to" not in recs["s4/spindash"]
    schema = json.loads((out / "MANIFEST.json").read_text())["schema"]
    assert schema["status_bits"] == {"ST_IN_AIR": 3, "ST_ROLLING": 4}
    assert "fb" in schema["v2_comparable"]


def test_mark_identical_needs_both_shas_and_the_same_shape():
    recs = {"s4/run": dict(inputs_sha256="a", frames_sha256="b"),
            "s4/topspeed": dict(inputs_sha256="a", frames_sha256="c", identical_to="stale"),
            "s4.debug/topspeed": dict(inputs_sha256="a", frames_sha256="b")}
    v1.mark_identical(recs)
    assert "identical_to" not in recs["s4/topspeed"], "frames differ: not identical"
    assert "identical_to" not in recs["s4.debug/topspeed"], "another shape is not a duplicate"


def test_allow_dirty_refuses_an_out_holding_reference_entries(tmp_path):
    out = tmp_path / "ref"
    out.mkdir()
    (out / "MANIFEST.json").write_text(json.dumps(
        {"recordings": {"s4/run": {"reference_grade": True}}}))
    with pytest.raises(v1.DirtyTree, match="reference-grade"):
        v1.record(tmp_path / "s4.bin", tmp_path / "s4.lst", "run", out, allow_dirty=True)


def test_diff_refuses_duplicate_tick_rows(tmp_path):
    ref, run = _pair(tmp_path, legs=("run",), shapes=("s4",))
    rows = _rows()
    _put(run, "s4", "run", rows + [rows[3]])
    with pytest.raises(ValueError, match="duplicate tick"):
        v1.diff(ref, run)


# ---- policy versions (owner-proxy ruling Q1, 2026-11-17) ------------------------------------

def _versions(d: Path, **v):
    d.mkdir(parents=True, exist_ok=True)
    (d / "MANIFEST.json").write_text(json.dumps(
        {"recordings": {k.replace("_", "/", 1): {"policy_version": n} for k, n in v.items()}}))


def test_diff_refuses_across_policy_versions(tmp_path, capsys):
    """Identical frames recorded under different policy versions are NOT a same-behaviour
    verdict: the diff says plainly that the versions differ and fails."""
    ref, run = _pair(tmp_path, legs=("spindash",), shapes=("s4",))
    _versions(ref, s4_spindash=1)
    _versions(run, s4_spindash=2)
    rep = v1.diff(ref, run)
    assert rep.results[("s4", "spindash")] == (v1.POLICY_DIFFERS, 1, 2)
    assert not rep.ok
    assert v1.main(["diff", "--ref", str(ref), "--run", str(run)]) == 1
    assert "s4/spindash: POLICY VERSIONS DIFFER (reference v1, run v2)" in capsys.readouterr().out


def test_diff_refuses_a_version_declared_on_one_side_only(tmp_path):
    ref, run = _pair(tmp_path, legs=("spindash",), shapes=("s4",))
    _versions(ref, s4_spindash=2)
    rep = v1.diff(ref, run)
    assert rep.results[("s4", "spindash")] == (v1.POLICY_DIFFERS, 2, None)
    assert not rep.ok


def test_diff_same_policy_version_compares_frames(tmp_path):
    ref, run = _pair(tmp_path, legs=("spindash",), shapes=("s4",))
    _versions(ref, s4_spindash=2)
    _versions(run, s4_spindash=2)
    assert v1.diff(ref, run).ok


def test_recorded_entry_carries_the_policy_version(tmp_path, monkeypatch):
    """Closed-loop: the leg's current policy version. Replay: the version of the log it
    replays (passed from the reference's own entry), never the current policy's."""
    leg_now = _fake_record(monkeypatch, {"run": ("FINISHED", [0x700] * 80, [0x08] * 80),
                                         "spindash": ("STUCK", [0] * 80, [0x02] * 80)})
    out = tmp_path / "ref"
    for leg in ("run", "spindash"):
        leg_now["leg"] = leg
        v1.record(tmp_path / "s4.bin", tmp_path / "s4.lst", leg, out)
    recs = json.loads((out / "MANIFEST.json").read_text())["recordings"]
    assert recs["s4/run"]["policy_version"] == ld.policy_version("run") == 1
    assert recs["s4/spindash"]["policy_version"] == ld.policy_version("spindash") == 2
    leg_now["leg"] = "spindash"
    log = {"t0": 300, "held": [0x02] * 80}
    v1.record(tmp_path / "s4.bin", tmp_path / "s4.lst", "spindash", tmp_path / "rp",
              inputs=log, policy_version=1)
    rp = json.loads((tmp_path / "rp" / "MANIFEST.json").read_text())["recordings"]
    assert rp["s4/spindash"]["policy_version"] == 1 and rp["s4/spindash"]["mode"] == "replay"
    with pytest.raises(ld.DriveError, match="policy_version"):
        v1.record(tmp_path / "s4.bin", tmp_path / "s4.lst", "spindash", tmp_path / "rp2",
                  inputs=log)


def test_replay_cli_refuses_a_reference_without_a_policy_version(tmp_path, capsys):
    ref = tmp_path / "ref"
    (ref / "s4").mkdir(parents=True)
    (ref / "s4" / "spindash.inputs.json").write_text(json.dumps({"t0": 300, "held": [2]}))
    (ref / "MANIFEST.json").write_text(json.dumps({"recordings": {"s4/spindash": {}}}))
    rc = v1.main(["replay", "--rom", str(tmp_path / "s4.bin"), "--lst", str(tmp_path / "s4.lst"),
                  "--leg", "spindash", "--ref", str(ref), "--out", str(tmp_path / "o")])
    assert rc == 2 and "policy_version" in capsys.readouterr().err


def test_record_without_a_build_export_could_not_run_before_spawning(tmp_path, monkeypatch, capsys):
    """No `<stem>.build.json` beside the ROM: COULD NOT RUN, rc 2, and nothing spawned."""
    spawned = []
    monkeypatch.setattr(v1.lp, "spawn_pinned", lambda rom, lst: spawned.append(1))
    monkeypatch.setattr(v1.ld, "resolve_syms", lambda lst: SimpleNamespace(buttons={}, equ={}))
    monkeypatch.setattr(v1, "_ram_spans", lambda syms: {})
    (tmp_path / "s4.bin").write_bytes(b"R")
    (tmp_path / "s4.lst").write_text("L")
    rc = v1.main(["record", "--rom", str(tmp_path / "s4.bin"), "--lst", str(tmp_path / "s4.lst"),
                  "--leg", "run", "--out", str(tmp_path / "out")])
    assert rc == 2 and spawned == []
    err = capsys.readouterr().err
    assert "COULD NOT RUN" in err and "UnboundRom" in err and "s4.build.json" in err
