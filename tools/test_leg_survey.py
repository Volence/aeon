"""Pre-build lane tests for tools/leg_survey.py (v2 step 0, Task 6). Synthetic results, no emulator."""
import json
from pathlib import Path

import pytest

import leg_survey as ls

PROV = {"aeon": {"commit": "c" * 40, "dirty": False}}


def _good_prov():
    import leg_provenance as lp
    return {k: {leaf: "x" for leaf in leaves} for k, leaves in lp.REQUIRED.items()}


def _dma(line=230, off=100):
    return {"status": "MEASURED", "unmeasurable": None, "entry_line_expected": 224,
            "worst_end": {"status": "MEASURED", "line": line, "off": off, "tick": 1}}


def write(out, leg, shape, ph, **over):
    r = {"provenance": _good_prov(), "leg": ls.LEG_POLICY[leg], "phase": ph, "status": "FINISHED",
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
    no = {"status": "MEASURED", "unmeasurable": None, "entry_line_expected": 224,
          "worst_end": {"status": "NO DMA"}}
    assert ls.dma_verdict(rows([no] * 3))[1] == "FITS"
    bad = {"status": "UNMEASURABLE", "unmeasurable": "x", "worst_end": None}
    assert ls.dma_verdict(rows([_dma(), bad, _dma()])) == ("n/a", "n/a (unmeasurable)")
    assert ls.dma_verdict(rows([_dma(), None, _dma()]))[1] == "n/a (unmeasurable)"
