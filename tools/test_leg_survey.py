"""Pre-build lane tests for tools/leg_survey.py (v2 step 0, Task 6). Synthetic results, no emulator."""
import json
from pathlib import Path

import pytest

import leg_survey as ls

PROV = {"aeon": {"commit": "c" * 40, "dirty": False}}


def _good_prov(leg="idle", shape="release"):
    import leg_provenance as lp
    pv = {k: {leaf: "x" for leaf in leaves} for k, leaves in lp.REQUIRED.items()}
    pv["aeon"]["dirty"] = False
    pv["oracle"]["dirty"] = False
    pv["rom"]["rom"] = ls.LEG_ROM[(leg, shape)]
    pv["rom"]["crc32"] = "crc-" + ls.LEG_ROM[(leg, shape)]
    return pv


def _dma(line=230, off=100):
    return {"status": "MEASURED", "unmeasurable": None, "entry_line_expected": 224,
            "overruns": [], "limit": {"line": 260, "off": 0},
            "worst_end": {"status": "MEASURED", "line": line, "off": off, "tick": 1}}


def write(out, leg, shape, ph, **over):
    r = {"provenance": _good_prov(leg, shape), "leg": ls.LEG_POLICY[leg], "phase": ph, "status": "FINISHED",
         "coverage": {"rule": "r", "got": 1, "need": 1, "met": True}, "lag": {"frames": 3, "ticks": 90},
         "dma": _dma()}
    r.update(over)
    ls.result_path(out, leg, shape, ph).write_text(json.dumps(r))


def fill(out, skip=()):
    for c in ls.expected_matrix():
        if c not in skip:
            write(out, *c)


def test_matrix_is_48():
    m = ls.expected_matrix()
    assert len(m) == 48 == len(set(m))
    assert ls.LEGS == ("idle", "run", "topspeed", "diagfall", "spindash", "objheavy", "sidekick",
                       "stream")
    assert ls.LEG_ROM[("idle", "release")] == "s4.bin"
    assert ls.LEG_ROM[("idle", "debug")] == "s4.debug.bin"
    assert ls.LEG_ROM[("objheavy", "debug")] == "s4.stressobj.debug.bin"
    assert ls.LEG_ROM[("sidekick", "release")] == "s4.sidekick.bin"
    assert ls.LEG_ROM[("stream", "release")] == "s4.s2clip.bin"
    assert {ls.LEG_POLICY[x] for x in ("objheavy", "sidekick", "stream")} == {"run"}
    paths = {ls.result_path(Path("o"), *c) for c in m}
    assert len(paths) == 48                       # distinct file per cell


def test_all_ok_exits_zero(tmp_path, capsys):
    fill(tmp_path)
    summ, rc = ls.write_summary(tmp_path)
    assert rc == 0 and summ.counts["OK"] == 48
    assert "ran 48 of 48" in (tmp_path / "summary.md").read_text()


def test_missing_result_is_did_not_run(tmp_path, capsys):
    skip = ("sidekick", "debug", 1)
    fill(tmp_path, skip=[skip])
    summ, rc = ls.write_summary(tmp_path)
    assert rc == 2
    assert summ.counts["DID NOT RUN"] == 1 and summ.counts["OK"] == 47
    text = (tmp_path / "summary.md").read_text()
    assert "ran 47 of 48" in text
    assert "sidekick/debug/p1" in text and "DID NOT RUN" in text
    assert "sidekick/debug/p1" in capsys.readouterr().err
    # a DID NOT RUN cell makes its leg/shape verdict unmeasurable, never FITS
    row = [l for l in text.splitlines() if l.startswith("| sidekick | debug")][0]
    assert "n/a (unmeasurable)" in row and "FITS" not in row


def test_result_without_provenance_is_failed(tmp_path):
    fill(tmp_path)
    r = json.loads(ls.result_path(tmp_path, "run", "release", 0).read_text())
    del r["provenance"]["oracle"]
    ls.result_path(tmp_path, "run", "release", 0).write_text(json.dumps(r))
    summ, rc = ls.write_summary(tmp_path)
    row = [x for x in summ.rows if (x.leg, x.shape, x.phase) == ("run", "release", 0)][0]
    assert row.status == "FAILED" and rc == 1


def test_unreadable_result_is_failed(tmp_path):
    fill(tmp_path)
    ls.result_path(tmp_path, "idle", "debug", 2).write_text("{not json")
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["FAILED"] == 1 and rc == 1


@pytest.mark.parametrize("over,want", [
    ({"status": "STUCK", "reason": "x"}, "STUCK"),
    ({"status": "CAP", "coverage": {"rule": "r", "got": "CAP", "need": "FINISHED", "met": False}},
     "DID NOT COVER"),
    ({"coverage": {"rule": "r", "got": 0, "need": 1, "met": False}}, "DID NOT COVER"),
    ({"dma": {"status": "UNMEASURABLE", "unmeasurable": "no sites", "worst_end": None}}, "FAILED"),
])
def test_stuck_and_uncovered_are_not_ok(tmp_path, over, want):
    fill(tmp_path)
    write(tmp_path, "diagfall", "release", 1, **over)
    summ, rc = ls.write_summary(tmp_path)
    row = [x for x in summ.rows if (x.leg, x.phase, x.shape) == ("diagfall", 1, "release")][0]
    assert row.status == want and rc == 1
    assert summ.counts["OK"] == 47


def test_idle_cap_with_coverage_met_is_ok(tmp_path):
    """idle never FINISHES (it is a fixed-tick leg): CAP + coverage met is its OK."""
    fill(tmp_path)
    write(tmp_path, "idle", "release", 0, status="CAP",
          coverage={"rule": "ticks driven >= 600", "got": 600, "need": 600, "met": True})
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["OK"] == 48 and rc == 0


def test_failed_status_is_failed(tmp_path):
    fill(tmp_path)
    write(tmp_path, "run", "debug", 2, status="FAILED")
    assert ls.summarise(tmp_path).counts["FAILED"] == 1


def _manifest_for(out, rcs=None):
    """A manifest agreeing with the files (rc 0), with per-cell overrides {cell: rc-or-None}."""
    rcs = rcs or {}
    with open(Path(out) / "manifest.jsonl", "w") as f:
        for c in ls.expected_matrix():
            rec = {"leg": c[0], "shape": c[1], "phase": c[2], "rc": rcs.get(c, 0)}
            f.write(json.dumps(rec) + "\n")


def test_topspeed_cap_with_coverage_met_is_ok(tmp_path):
    fill(tmp_path)
    write(tmp_path, "topspeed", "debug", 1, status="CAP",
          coverage={"rule": "topspeed", "got": "CAP", "need": "CAP", "met": True})
    assert ls.summarise(tmp_path).counts["OK"] == 48


def test_dma_overrun_is_failed_and_exits_nonzero(tmp_path):
    fill(tmp_path)
    d = _dma()
    d["overruns"] = [{"end_line": 262}]
    write(tmp_path, "run", "release", 0, dma=d)
    summ, rc = ls.write_summary(tmp_path)
    row = [x for x in summ.rows if (x.leg, x.shape, x.phase) == ("run", "release", 0)][0]
    assert row.status == "FAILED" and "overrun" in row.detail and rc == 1


@pytest.mark.parametrize("line", [259, 261])
def test_non_fits_verdict_exits_one_even_when_all_cells_ok(tmp_path, line):
    """A thin margin (NEEDS-WITNESS) or a negative one (OVER) is not green."""
    fill(tmp_path)
    write(tmp_path, "run", "release", 2, dma=_dma(line, 0))
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["OK"] == 48
    assert summ.groups[("run", "release")][1] in ("NEEDS-WITNESS", "OVER") and rc == 1


def test_na_verdict_on_all_ok_row_exits_one(tmp_path):
    fill(tmp_path)
    d = _dma()
    d["entry_line_expected"] = None            # the probe cannot say where VInt is
    write(tmp_path, "run", "release", 0, dma=d)
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["OK"] == 48
    assert summ.groups[("run", "release")][1] == "n/a (unmeasurable)" and rc == 1


def test_result_for_another_cell_is_failed(tmp_path):
    fill(tmp_path)
    r = json.loads(ls.result_path(tmp_path, "run", "release", 1).read_text())
    r["phase"] = 2
    ls.result_path(tmp_path, "run", "release", 1).write_text(json.dumps(r))
    summ, rc = ls.write_summary(tmp_path)
    row = [x for x in summ.rows if (x.leg, x.shape, x.phase) == ("run", "release", 1)][0]
    assert row.status == "FAILED" and "phase" in row.detail and rc == 1


def test_result_with_other_rom_name_is_failed(tmp_path):
    fill(tmp_path)
    r = json.loads(ls.result_path(tmp_path, "run", "debug", 0).read_text())
    r["provenance"]["rom"]["rom"] = "s4.bin"
    ls.result_path(tmp_path, "run", "debug", 0).write_text(json.dumps(r))
    row = [x for x in ls.summarise(tmp_path).rows if (x.leg, x.shape, x.phase) == ("run", "debug", 0)][0]
    assert row.status == "FAILED" and "provenance.rom.rom" in row.detail


@pytest.mark.parametrize("field,block,leaf", [("aeon.commit", "aeon", "commit"),
                                              ("oracle.server_build_id", "oracle", "server_build_id"),
                                              ("aeon.dirty", "aeon", "dirty")])
def test_mixed_provenance_in_a_shape_is_failed_naming_the_field(tmp_path, field, block, leaf):
    fill(tmp_path)
    p = ls.result_path(tmp_path, "sidekick", "release", 2)
    r = json.loads(p.read_text())
    r["provenance"][block][leaf] = "other" if leaf != "dirty" else True
    p.write_text(json.dumps(r))
    summ, rc = ls.write_summary(tmp_path)
    row = [x for x in summ.rows if (x.leg, x.shape, x.phase) == ("sidekick", "release", 2)][0]
    assert row.status == "FAILED" and field in row.detail and rc == 1


def test_mixed_rom_crc_within_a_leg_is_failed(tmp_path):
    fill(tmp_path)
    p = ls.result_path(tmp_path, "idle", "release", 1)
    r = json.loads(p.read_text())
    r["provenance"]["rom"]["crc32"] = "deadbeef"
    p.write_text(json.dumps(r))
    row = [x for x in ls.summarise(tmp_path).rows if (x.leg, x.shape, x.phase) == ("idle", "release", 1)][0]
    assert row.status == "FAILED" and "rom.crc32" in row.detail


def test_summary_header_prints_provenance_tuples_and_labels(tmp_path):
    fill(tmp_path)
    ls.write_summary(tmp_path)
    t = (tmp_path / "summary.md").read_text()
    assert "aeon.commit=" in t and "oracle.server_build_id=" in t and "rom crc32 idle/release" in t
    assert "MEASURED (Oracle)" in t
    assert "ESTIMATED: classify, sound_playing=True (upper-bound Z80 stall), no witness" in t


def test_no_dma_verdict_is_said_to_be_vacuous(tmp_path):
    fill(tmp_path)
    no = {"status": "MEASURED", "unmeasurable": None, "entry_line_expected": 224, "overruns": [],
          "worst_end": {"status": "NO DMA"}}
    for ph in (0, 1, 2):
        write(tmp_path, "idle", "release", ph, dma=no)
    ls.write_summary(tmp_path)
    row = [l for l in (tmp_path / "summary.md").read_text().splitlines()
           if l.startswith("| idle | release")][0]
    assert "NO DMA" in row and "vacuous" in row


@pytest.mark.parametrize("rc", [None, 2, 7])
def test_rc_disagreeing_with_file_is_failed(tmp_path, rc):
    fill(tmp_path)
    cell = ("run", "release", 0)
    _manifest_for(tmp_path, {cell: rc})
    summ, code = ls.write_summary(tmp_path)
    row = [x for x in summ.rows if (x.leg, x.shape, x.phase) == cell][0]
    assert row.status == "FAILED" and "rc disagrees with file" in row.detail and code == 1


def test_manifest_agreeing_with_files_is_all_ok(tmp_path):
    fill(tmp_path)
    _manifest_for(tmp_path)
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["OK"] == 48 and rc == 0


def test_run_refuses_nonempty_out_dir_without_resume(tmp_path):
    (tmp_path / "stale.json").write_text("{}")
    with pytest.raises(SystemExit, match="not empty"):
        ls.run(tmp_path, only=["objheavy"], rom_dir=tmp_path)
    ls.run(tmp_path, only=["objheavy"], rom_dir=tmp_path, resume=True)    # explicit resume allowed


def test_run_survives_oserror_and_kills_group_on_timeout(tmp_path, monkeypatch, capsys):
    rom_dir = tmp_path / "roms"
    rom_dir.mkdir()
    for n in ("s4.stressobj.bin", "s4.stressobj.lst", "s4.stressobj.debug.bin",
              "s4.stressobj.debug.lst"):
        (rom_dir / n).write_bytes(b"x")
    monkeypatch.setattr(ls.subprocess, "Popen",
                        lambda *a, **k: (_ for _ in ()).throw(PermissionError("nope")))
    done = ls.run(tmp_path / "o", only=["objheavy"], rom_dir=rom_dir)
    assert len(done) == 6 and all(d["rc"] is None and "could not start" in d["note"] for d in done)
    # timeout: a real child that spawns a grandchild; the group kill must take both
    import subprocess as sp, sys, time, os
    monkeypatch.undo()
    pidf = tmp_path / "gc.pid"
    code = ("import subprocess,sys,time;"
            f"g=subprocess.Popen(['sleep','60']);open({str(pidf)!r},'w').write(str(g.pid));time.sleep(60)")
    rc, note = ls._run_cell([sys.executable, "-c", code], timeout=2)
    assert rc is None and "process group killed" in note
    gc = int(pidf.read_text())
    time.sleep(0.3)
    with pytest.raises(ProcessLookupError):
        os.kill(gc, 0)


def test_run_names_missing_rom_and_does_not_crash(tmp_path, capsys):
    done = ls.run(tmp_path / "o", only=["objheavy"], rom_dir=tmp_path)
    assert len(done) == 6 and all(d["rc"] is None for d in done)
    assert "s4.stressobj.bin" in capsys.readouterr().err
    lines = (tmp_path / "o" / "manifest.jsonl").read_text().splitlines()
    assert len(lines) == 6
    assert ls.summarise(tmp_path / "o").counts["OK"] == 0


def test_run_rejects_unknown_leg(tmp_path):
    with pytest.raises(SystemExit):
        ls.run(tmp_path, only=["idel"], rom_dir=tmp_path)


def test_verdict_fits_over_and_unmeasurable():
    def rows(dmas):
        return [ls.Row("run", "release", i, "OK", "", 0, d) for i, d in enumerate(dmas)]
    end, v = ls.dma_verdict(rows([_dma(226, 0)] * 3))
    assert v == "FITS" and "226" in end
    assert ls.dma_verdict(rows([_dma(226, 0), _dma(261, 0), _dma(226, 0)]))[1] == "OVER"
    no = {"status": "MEASURED", "unmeasurable": None, "entry_line_expected": 224, "overruns": [],
          "worst_end": {"status": "NO DMA"}}
    assert ls.dma_verdict(rows([no] * 3))[1] == "FITS"
    bad = {"status": "UNMEASURABLE", "unmeasurable": "x", "worst_end": None}
    assert ls.dma_verdict(rows([_dma(), bad, _dma()])) == ("n/a", "n/a (unmeasurable)")
    assert ls.dma_verdict(rows([_dma(), None, _dma()]))[1] == "n/a (unmeasurable)"


def test_file_with_no_manifest_record_is_failed(tmp_path):
    fill(tmp_path)
    _manifest_for(tmp_path)
    mp = tmp_path / "manifest.jsonl"
    lines = [l for l in mp.read_text().splitlines() if '"leg": "stream"' not in l]
    mp.write_text("\n".join(lines) + "\n")
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["FAILED"] == 6 and rc == 1
