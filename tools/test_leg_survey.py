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
    pv["rom"]["debug"] = 1 if shape == "debug" else 0    # as leg_provenance writes it (M3)
    if leg in ls.LEG_CLIP:                         # a clip-built cell names its clip (v2 C4)
        pv["rom"]["rebake"] = {"clip": ls.LEG_CLIP[leg]}
    return pv


def _dma(line=230, off=100):
    return {"status": "MEASURED", "unmeasurable": None, "entry_line_expected": 224,
            "overruns": [], "limit": {"line": 260, "off": 0},
            "worst_end": {"status": "MEASURED", "line": line, "off": off, "tick": 1}}


def _sync(out):
    """A manifest as leg_run would have left it: rc 0 for a good cell, 1 for a written-but-not-good
    one, rc None (no file) for a missing one."""
    with open(Path(out) / "manifest.jsonl", "w") as f:
        for c in ls.expected_matrix():
            p = ls.result_path(out, *c)
            rc = None if not p.is_file() else (0 if ls._judge(p, c)[0] == "OK" else 1)
            f.write(json.dumps({"leg": c[0], "shape": c[1], "phase": c[2], "rc": rc}) + "\n")


def write(out, leg, shape, ph, **over):
    r = {"provenance": _good_prov(leg, shape), "leg": ls.LEG_RUN_LEG[leg], "phase": ph, "status": "FINISHED",
         "coverage": {"rule": "r", "got": 1, "need": 1, "met": True}, "lag": {"frames": 3, "ticks": 90},
         "dma": _dma()}
    r.update(over)
    ls.result_path(out, leg, shape, ph).write_text(json.dumps(r))
    _sync(out)


def fill(out, skip=(), companion=True):
    """Every cell of the 48 (bar `skip`) and, with `companion`, the 6 companion cells OK."""
    for c in ls.expected_matrix():
        if c not in skip:
            write(out, *c)
    _sync(out)
    if companion:
        for _l, sh, ph in ls.companion_cells():
            r = {"provenance": _good_prov("stream", sh), "leg": "stream", "phase": ph,
                 "status": "FINISHED", "coverage": {"rule": "r", "got": 1, "need": 1,
                                                    "met": True},
                 "lag": {"frames": 3, "ticks": 90}, "dma": _dma()}
            r["provenance"]["rom"]["rebake"] = {"clip": ls.STREAM_COMPANION_CLIP}
            r["provenance"]["rom"]["crc32"] = "crc-companion-" + sh
            p = ls.companion_path(out, sh, ph)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(r))
        _sync_comp(out)


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


def test_release_and_debug_from_different_commits_is_failed(tmp_path):
    """One aeon + oracle tuple across the WHOLE survey, not per shape."""
    fill(tmp_path)
    for leg in ls.LEGS:
        for ph in (0, 1, 2):
            p = ls.result_path(tmp_path, leg, "debug", ph)
            r = json.loads(p.read_text())
            r["provenance"]["aeon"]["commit"] = "other-commit"
            p.write_text(json.dumps(r))
    summ, rc = ls.write_summary(tmp_path)
    bad = [x for x in summ.rows if x.status == "FAILED"]
    assert len(bad) == 24 and all(x.shape == "debug" for x in bad) and rc == 1
    assert "aeon.commit" in bad[0].detail and "'other-commit'" in bad[0].detail
    assert "'x'" in bad[0].detail                      # both values named


def test_no_manifest_fails_every_present_file(tmp_path):
    fill(tmp_path, skip=[("stream", "debug", 2)])
    (tmp_path / "manifest.jsonl").unlink()
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["FAILED"] == 47 and summ.counts["DID NOT RUN"] == 1 and rc == 2
    assert all("no manifest: cannot confirm this run wrote it" in x.detail
               for x in summ.rows if x.status == "FAILED")


def test_rc1_with_an_ok_file_is_failed(tmp_path):
    fill(tmp_path)
    cell = ("run", "debug", 1)
    _manifest_for(tmp_path, {cell: 1})
    summ, rc = ls.write_summary(tmp_path)
    row = [x for x in summ.rows if (x.leg, x.shape, x.phase) == cell][0]
    assert row.status == "FAILED" and "rc disagrees with file" in row.detail and rc == 1


def test_witness_disagrees_verdict_exits_one(tmp_path, monkeypatch):
    fill(tmp_path)
    monkeypatch.setattr(ls.lc, "classify", lambda *a, **k: "WITNESS-DISAGREES")
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["OK"] == 48 and rc == 1


def test_objheavy_runs_under_its_own_coverage_rule():
    """objheavy drives the run policy, but leg_run is asked for `--leg objheavy` so its result
    is judged by the objheavy rule (v2 C2), and the cell's file is named for it."""
    assert ls.LEG_RUN_LEG["objheavy"] == "objheavy"
    assert ls.LEG_RUN_LEG["run"] == "run" and ls.LEG_RUN_LEG["sidekick"] == "sidekick"
    assert ls.LEG_RUN_LEG["stream"] == "stream"          # v2 C4: its own rule
    assert ls.result_path(Path("/o"), "objheavy", "debug", 1).name == \
        "s4.stressobj.debug_objheavy_p1.json"


# ---- the stream leg (v2 C4, Task 10) -------------------------------------------------------

import leg_drive as ld  # noqa: E402

STREAM_EQ = {"PAGECACHE_DIRECT_BOUNDED": 1}


def _stream_rows(gens, dm=0, t0=300):
    return [{"t": t0 + i, "eg": g, "dm": dm} for i, g in enumerate(gens)]


def _stream_hits(decode=4, landings=6, pick=3):
    return {"ZX0R_Decompress": decode, "PageIn_EnqueueLanding": landings,
            "PageCache_PickVictim": pick}


def _stream_result(out, shape, ph, status, cov, clip=None, sub=None):
    clip = clip or ls.STREAM_CLIP
    r = {"provenance": _good_prov("stream", shape), "leg": "stream", "phase": ph,
         "status": status, "coverage": cov, "lag": {"frames": 3, "ticks": 90}, "dma": _dma(),
         "reason": "progress stalled" if status == "STUCK" else ""}
    r["provenance"]["rom"]["rebake"] = {"clip": clip}
    p = (ls.companion_path(out, shape, ph) if sub else ls.result_path(out, "stream", shape, ph))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(r))
    return p


def test_stream_leg_requires_decode_calls(tmp_path):
    """A run that evicted and finished but never entered the decoder is DID NOT COVER."""
    cov = ld.stream_coverage("FINISHED", _stream_rows([7, 8, 9, 10]), _stream_hits(decode=0))
    assert cov["met"] is False and cov["got"]["decode_calls"] == 0
    assert cov["got"]["evictions"] == 3
    _stream_result(tmp_path, "release", 0, "FINISHED", cov)
    assert ls._judge(ls.result_path(tmp_path, "stream", "release", 0),
                     ("stream", "release", 0))[0] == "DID NOT COVER"


def test_stream_leg_requires_evictions():
    """The companion's shape: it finishes and decodes, but never evicts -> not covered."""
    cov = ld.stream_coverage("FINISHED", _stream_rows([1, 1, 1], dm=1), _stream_hits(pick=0))
    assert cov["met"] is False and cov["got"]["evictions"] == 0
    assert cov["got"]["streamed"] is False and cov["got"]["decode_calls"] == 4


def test_stream_leg_met_needs_finished_decode_and_evictions():
    cov = ld.stream_coverage("FINISHED", _stream_rows([3, 4, 6]), _stream_hits())
    assert cov["met"] is True and cov["got"]["streamed"] is True
    assert cov["got"]["evictions"] == 3 and cov["got"]["no_victim"] == 0
    stuck = ld.stream_coverage("STUCK", _stream_rows([3, 4, 6]), _stream_hits())
    assert stuck["met"] is False and stuck["got"]["streamed"] is True


def test_stream_evict_gen_wraps_mod_16_bits():
    cov = ld.stream_coverage("FINISHED", _stream_rows([0xFFFF, 0, 1]), _stream_hits(pick=2))
    assert cov["got"]["evictions"] == 2 and cov["met"] is True


@pytest.mark.parametrize("rows,hits,why", [
    (_stream_rows([3, 4, 6]), _stream_hits(pick=1), "PickVictim"),
    (_stream_rows([3, 4, 6]), {"ZX0R_Decompress": 4, "PageIn_EnqueueLanding": 6}, "PickVictim"),
    ([{"t": 300, "eg": 3, "dm": 0}, {"t": 301, "dm": 0}], _stream_hits(), "Page_Evict_Gen"),
    ([], _stream_hits(), "no rows"),
])
def test_stream_unmeasurable_is_never_a_count(rows, hits, why):
    cov = ld.stream_coverage("FINISHED", rows, hits)
    assert cov["met"] is False and why in cov["got"]["unmeasurable"]


def test_stream_unmeasurable_cell_is_failed(tmp_path):
    cov = ld.stream_coverage("FINISHED", _stream_rows([3, 4, 6]), _stream_hits(pick=1))
    _stream_result(tmp_path, "debug", 2, "FINISHED", cov)
    s, d, _, _ = ls._judge(ls.result_path(tmp_path, "stream", "debug", 2), ("stream", "debug", 2))
    assert s == "FAILED" and "UNMEASURABLE" in d


def test_stream_stuck_cell_reads_stuck_with_its_counts(tmp_path):
    """s2_woven: evicts, then sticks. The cell is STUCK (never OK) and the detail carries the
    streaming counts as annotations."""
    cov = ld.stream_coverage("STUCK", _stream_rows([3, 4, 5, 6]), _stream_hits())
    _stream_result(tmp_path, "release", 1, "STUCK", cov)
    s, d, _, _ = ls._judge(ls.result_path(tmp_path, "stream", "release", 1),
                           ("stream", "release", 1))
    assert s == "STUCK" and "evictions 3" in d and "decode calls 4" in d


def test_stream_cell_from_the_wrong_clip_is_failed(tmp_path):
    cov = ld.stream_coverage("FINISHED", _stream_rows([3, 4, 6]), _stream_hits())
    _stream_result(tmp_path, "release", 0, "FINISHED", cov, clip=ls.STREAM_COMPANION_CLIP)
    s, d, _, _ = ls._judge(ls.result_path(tmp_path, "stream", "release", 0),
                           ("stream", "release", 0))
    assert s == "FAILED" and ls.STREAM_COMPANION_CLIP in d and ls.STREAM_CLIP in d


def test_stream_clips_are_pinned_and_the_matrix_stays_48():
    assert ls.STREAM_CLIP == "s2_woven" and ls.STREAM_COMPANION_CLIP == "s2_ehz_cpz"
    assert ls.LEG_RUN_LEG["stream"] == "stream" and ls.LEG_POLICY["stream"] == "run"
    assert ld.POLICIES["stream"] is ld.Run
    assert len(ls.expected_matrix()) == 48
    comp = ls.companion_cells()
    assert len(comp) == 6 and not set(comp) & set(ls.expected_matrix())
    cp = {ls.companion_path(Path("/o"), sh, ph) for _l, sh, ph in comp}
    sp = {ls.result_path(Path("/o"), *c) for c in ls.expected_matrix()}
    assert len(cp) == 6 and not cp & sp


def _fill_with_companion(out, comp_status="FINISHED", comp_cov=None, stream_status="STUCK"):
    fill(out, skip=[c for c in ls.expected_matrix() if c[0] == "stream"], companion=False)
    for sh in ls.SHAPES:
        for ph in ls.PHASES:
            cov = ld.stream_coverage(stream_status, _stream_rows([3, 4, 6]), _stream_hits())
            _stream_result(out, sh, ph, stream_status, cov)
            ccov = comp_cov or ld.stream_coverage(comp_status, _stream_rows([1, 1], dm=1),
                                                  _stream_hits(pick=0))
            _stream_result(out, sh, ph, comp_status, ccov, clip=ls.STREAM_COMPANION_CLIP,
                           sub=True)
    _sync(out)
    _sync_comp(out)


def _sync_comp(out):
    """The companion's manifest as `leg_survey run --companion` leaves it."""
    with open(ls.companion_dir(out) / "manifest.jsonl", "w") as f:
        for _l, sh, ph in ls.companion_cells():
            p = ls.companion_path(out, sh, ph)
            rc = None if not p.is_file() else (0 if ls._judge(p)[0] == "OK" else 1)
            f.write(json.dumps({"leg": "stream_companion", "shape": sh, "phase": ph,
                                "rc": rc}) + "\n")


def test_companion_finished_never_makes_the_stream_cell_ok(tmp_path, capsys):
    _fill_with_companion(tmp_path)
    summ, rc = ls.write_summary(tmp_path)
    assert all(r.status == "STUCK" for r in summ.rows if r.leg == "stream")
    assert summ.counts["OK"] == 42 and len(summ.rows) == 48
    assert [r.status for r in summ.companion] == ["DID NOT COVER"] * 6
    assert all(r.drive_status == "FINISHED" for r in summ.companion)
    text = (tmp_path / "summary.md").read_text()
    assert "NO single run both evicts and finishes" in text
    assert "streaming sustained to the end of an act: **DID NOT COVER**" in text
    assert "outside the 48" in text and rc == 1


def test_companion_missing_is_did_not_run_and_loud(tmp_path, capsys):
    fill(tmp_path, companion=False)
    summ, rc = ls.write_summary(tmp_path)
    assert summ.counts["OK"] == 48
    assert [r.status for r in summ.companion] == ["DID NOT RUN"] * 6
    assert rc == 2
    assert "companion" in capsys.readouterr().err


def test_companion_of_the_wrong_clip_is_failed(tmp_path):
    _fill_with_companion(tmp_path)
    cov = ld.stream_coverage("FINISHED", _stream_rows([1, 1], dm=1), _stream_hits(pick=0))
    _stream_result(tmp_path, "debug", 0, "FINISHED", cov, clip=ls.STREAM_CLIP, sub=True)
    summ = ls.summarise(tmp_path)
    bad = [r for r in summ.companion if r.shape == "debug" and r.phase == 0][0]
    assert bad.status == "FAILED" and ls.STREAM_CLIP in bad.detail


def test_run_refuses_a_rom_of_the_wrong_clip(tmp_path, capsys):
    """One s4.s2clip.bin exists per shape at a time (check_pair pins the ROM to the aeon
    root). A stream cell over the companion's ROM is DID NOT RUN, naming both clips."""
    rd = tmp_path / "roms"
    rd.mkdir()
    for n in ("s4.s2clip.bin", "s4.s2clip.lst"):
        (rd / n).write_bytes(b"x")
    (rd / "s4.s2clip.clip_anchors.json").write_text(json.dumps({"clip": "s2_ehz_cpz"}))
    recs = ls.run(tmp_path / "out", only=["stream"], rom_dir=rd)
    rel = [r for r in recs if r["shape"] == "release"]
    assert rel and all(r["rc"] is None and "s2_ehz_cpz" in r["note"] and "s2_woven" in r["note"]
                       for r in rel)


# ---- the "streaming sustained" summary line: all four outcomes (v2 C4 fix 1, I1/I2/M1) -----

def _sus_dir(out, stream="STUCK", comp="FINISHED", skip_stream=(), skip_comp=(),
             stream_clip=None, stream_gens=(3, 4, 6), comp_gens=(1, 1)):
    """Stream + companion cells only (the other 42 cells do not feed the line)."""
    for sh in ls.SHAPES:
        for ph in ls.PHASES:
            if (sh, ph) not in skip_stream:
                cov = ld.stream_coverage(stream, _stream_rows(list(stream_gens)), _stream_hits())
                _stream_result(out, sh, ph, stream, cov, clip=stream_clip)
            if (sh, ph) not in skip_comp:
                ccov = ld.stream_coverage(comp, _stream_rows(list(comp_gens), dm=1),
                                          _stream_hits(pick=0))
                _stream_result(out, sh, ph, comp, ccov, clip=ls.STREAM_COMPANION_CLIP, sub=True)
    _sync(out)
    _sync_comp(out)
    return ls.sustained(ls.summarise(out))


def test_sustained_covered_when_one_run_streams_and_finishes(tmp_path):
    v, why = _sus_dir(tmp_path, stream="FINISHED")
    assert v == "COVERED" and "stream/" in why


def test_sustained_did_not_cover_only_when_every_cell_ran(tmp_path):
    v, why = _sus_dir(tmp_path)
    assert v == "DID NOT COVER"
    assert "NO single run both evicts and finishes" in why
    assert f"evicting runs: stream ({ls.STREAM_CLIP})" in why
    assert f"finishing runs: companion ({ls.STREAM_COMPANION_CLIP})" in why


def test_sustained_is_did_not_run_when_the_stream_half_is_missing(tmp_path):
    """I1: the companion ran, the stream cells did not -> DID NOT RUN, never a negative
    finding about the evicting clip from runs that never happened."""
    allc = {(sh, ph) for sh in ls.SHAPES for ph in ls.PHASES}
    v, why = _sus_dir(tmp_path, skip_stream=allc)
    assert v == "DID NOT RUN"
    assert "NO single run" not in why and "stream/release/p0" in why


def test_sustained_is_did_not_run_on_a_partial_survey(tmp_path):
    v, why = _sus_dir(tmp_path, skip_comp={("debug", 2)})
    assert v == "DID NOT RUN" and "stream_companion/debug/p2" in why
    assert "NO single run" not in why


def test_sustained_is_failed_and_cites_no_refused_evidence(tmp_path):
    """M1: wrong-clip (FAILED) cells are refused evidence: the line is FAILED, names them, and
    never labels their counts as the stream clip's."""
    v, why = _sus_dir(tmp_path, stream="FINISHED", stream_clip=ls.STREAM_COMPANION_CLIP)
    assert v == "FAILED" and "stream/release/p0" in why
    assert "finishing runs" not in why


def test_sustained_covered_outranks_a_missing_cell(tmp_path):
    v, _ = _sus_dir(tmp_path, stream="FINISHED", skip_comp={("release", 0)})
    assert v == "COVERED"


# ---- final review M1-M4 (2026-11-17): the survey trusts a cell's digest, not its file name


def _edit(out, cell, fn):
    p = ls.result_path(out, *cell)
    r = json.loads(p.read_text())
    fn(r)
    p.write_text(json.dumps(r))


def _row(summ, cell):
    return [x for x in summ.rows if (x.leg, x.shape, x.phase) == cell][0]


def test_m1_two_builds_of_one_rom_file_across_legs_is_failed(tmp_path):
    """run/release is internally consistent but its s4.bin is not idle/release's s4.bin."""
    fill(tmp_path)
    for ph in ls.PHASES:
        _edit(tmp_path, ("run", "release", ph),
              lambda r: r["provenance"]["rom"].__setitem__("crc32", "crc-other-s4.bin"))
    summ = ls.summarise(tmp_path)
    row = _row(summ, ("run", "release", 0))
    assert row.status == "FAILED" and "one crc per ROM file" in row.detail and "s4.bin" in row.detail


def test_m1_the_companion_is_its_own_rom_group(tmp_path):
    """The companion bakes another clip into the same s4.s2clip name: not a mismatch."""
    fill(tmp_path)
    summ = ls.summarise(tmp_path)
    assert all(r.status == "OK" for r in summ.rows + summ.companion), \
        [(r.leg, r.shape, r.phase, r.detail) for r in summ.rows + summ.companion if r.status != "OK"]


@pytest.mark.parametrize("block,leaf,field", [
    ("harness", "tool_sha256", "harness.tool_sha256"),
    ("harness", "leg_drive_sha256", "harness.leg_drive_sha256"),
    ("rom", "sigil_revision", "rom.sigil_revision")])
def test_m2_a_harness_or_assembler_change_mid_survey_is_failed(tmp_path, block, leaf, field):
    fill(tmp_path)
    _edit(tmp_path, ("sidekick", "debug", 1),
          lambda r: r["provenance"][block].__setitem__(leaf, "changed"))
    row = _row(ls.summarise(tmp_path), ("sidekick", "debug", 1))
    assert row.status == "FAILED" and field in row.detail


def test_m2_the_printed_tuple_is_unchanged(tmp_path):
    fill(tmp_path)
    summ = ls.summarise(tmp_path)
    assert set(summ.prov["survey"]) == {"aeon.commit", "aeon.dirty", "oracle.server_build_id",
                                        "oracle.source", "oracle.dirty", "oracle.sha256"}


@pytest.mark.parametrize("cell,dbg", [(("objheavy", "debug", 0), 0), (("run", "release", 2), 1),
                                      (("run", "debug", 1), "1"), (("idle", "debug", 0), True)])
def test_m3_a_digest_of_the_other_shape_is_failed(tmp_path, cell, dbg):
    fill(tmp_path)
    _edit(tmp_path, cell, lambda r: r["provenance"]["rom"].__setitem__("debug", dbg))
    row = _row(ls.summarise(tmp_path), cell)
    assert row.status == "FAILED" and "provenance.rom.debug" in row.detail


@pytest.mark.parametrize("cov", [None, {}, {"rule": "r", "got": 1, "need": 1}, "met"])
def test_m4_a_result_without_a_coverage_verdict_is_failed_not_did_not_cover(tmp_path, cov):
    fill(tmp_path)
    _edit(tmp_path, ("topspeed", "release", 0), lambda r: r.__setitem__("coverage", cov))
    row = _row(ls.summarise(tmp_path), ("topspeed", "release", 0))
    assert row.status == "FAILED" and "no coverage verdict" in row.detail
