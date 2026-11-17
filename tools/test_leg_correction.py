"""Tests for tools/leg_correction.py and tools/blastem_witness.py (v2 B4).

Pure lane only (no artifacts, no emulator): the correction arithmetic, the classify gate, the
witness comparison on synthetic rows, the open-loop replay core against a fake RSP stub, and
the doc/code drift check that reads the "Correcting Oracle's numbers" section of
docs/audits/Hardware limits.md. The live BlastEm smoke is a manual step (task-4 report)."""
import math
import re
from fractions import Fraction
from pathlib import Path

import pytest

import blastem_witness as bw
import leg_correction as lc

AEON = Path(__file__).resolve().parent.parent
DOC = AEON / "docs" / "audits" / "Hardware limits.md"
SECTION = "Correcting Oracle's numbers"


# ---- corrected_margin ---------------------------------------------------------------------

def test_corrected_margin_silent_uses_refresh_only():
    # 16,418 cycles since VInt: 128 whole refresh periods of 128 cycles, 2 cycles each = 256.
    assert lc.corrected_margin(10_000, 16_418, sound_playing=False) == 10_000 - 256


def test_corrected_margin_with_sound_adds_z80():
    elapsed = 16_418
    z80 = math.ceil(elapsed * lc.Z80_STALL_MAX_FRACTION)        # 427: the stall is an upper bound
    assert z80 == 427
    assert lc.corrected_margin(10_000, elapsed, sound_playing=True) == 10_000 - 256 - z80
    # Sound costs more than silence; the sum of the two bounds is rule 3's with-sound term
    # (1.5625 % + 2.6 % = 4.1625 %, pinned against the doc by test_rule3_states_the_exact_terms).
    corr = 10_000 - lc.corrected_margin(10_000, elapsed, sound_playing=True)
    assert corr > 10_000 - lc.corrected_margin(10_000, elapsed, sound_playing=False)
    assert corr == math.floor(elapsed * lc.REFRESH_FRACTION) + z80


def test_corrected_margin_refuses_negative_elapsed():
    with pytest.raises(ValueError):
        lc.corrected_margin(100, -1, sound_playing=False)


# ---- classify -----------------------------------------------------------------------------

def _agree(**kw):
    base = dict(path_agree_ticks=1000, first_divergent_tick=None, lag_oracle=1, lag_blastem=1,
                extra_lag_ticks=(), common_ticks=1000, oracle_ticks=1000)
    base.update(kw)
    return bw.WitnessResult(**base)


def test_under_three_percent_needs_witness():
    assert lc.classify(3800, 128_006, 16_418, sound_playing=False, witness=None) == \
        "NEEDS-WITNESS"


def test_wide_margin_fits_on_oracle_alone():
    assert lc.classify(20_000, 128_006, 16_418, sound_playing=True, witness=None) == "FITS"


def test_correction_can_push_a_fit_under_the_threshold():
    # 3,900 raw is above 3 % of a frame (3,840.18), but not once the refresh is taken off.
    assert 3900 > lc.WITNESS_MARGIN_FRACTION * lc.FRAME_CYCLES
    assert lc.classify(3900, lc.FRAME_CYCLES, 16_418, False, None) == "NEEDS-WITNESS"


def test_negative_corrected_margin_is_over():
    assert lc.classify(100, 128_006, 16_418, sound_playing=False, witness=None) == "OVER"
    assert lc.classify(100, 128_006, 16_418, False, _agree()) == "OVER"


def test_witness_agreement_upgrades_to_fits():
    assert lc.classify(3800, 128_006, 16_418, False, _agree()) == "FITS"


def test_witness_extra_lag_is_disagrees():
    w = _agree(lag_blastem=2, extra_lag_ticks=(512,))
    assert lc.classify(3800, 128_006, 16_418, False, w) == "WITNESS-DISAGREES"


def test_witness_path_divergence_is_disagrees():
    w = _agree(path_agree_ticks=400, first_divergent_tick=700)
    assert lc.classify(3800, 128_006, 16_418, False, w) == "WITNESS-DISAGREES"


def test_witness_that_covered_too_little_is_disagrees():
    # A witness that ran only part of the leg cannot vouch for the rest of it.
    w = _agree(path_agree_ticks=10, common_ticks=10, oracle_ticks=1000)
    assert lc.classify(3800, 128_006, 16_418, False, w) == "WITNESS-DISAGREES"


def test_classify_refuses_nonpositive_budget():
    with pytest.raises(ValueError):
        lc.classify(10, 0, 0, False, None)


# ---- compare ------------------------------------------------------------------------------

def _rows(n, t0=300, fc0=330, lag_at=(), jitter_at=None):
    out, fc = [], fc0
    out.append(bw.WitnessRow(t0 - 1, fc, 96, 400, 256, 500))
    for i in range(n):
        t = t0 + i
        fc += 2 if t in lag_at else 1
        px = 256 + i + (1 if jitter_at is not None and t >= jitter_at else 0)
        out.append(bw.WitnessRow(t, fc & 0xFFFF, 96 + i // 2, 400, px, 500))
    return out


def test_compare_finds_first_divergent_tick():
    o = _rows(50)
    b = _rows(50, jitter_at=320)
    w = bw.compare(o, b)
    assert w.first_divergent_tick == 320
    assert w.path_agree_ticks == 320 - 299          # ticks 299..319 agree
    assert w.lag_oracle == w.lag_blastem == 0
    assert w.extra_lag_ticks == ()


def test_compare_all_agree():
    w = bw.compare(_rows(50, lag_at=(310,)), _rows(50, lag_at=(310,)))
    assert w.first_divergent_tick is None
    assert w.path_agree_ticks == w.common_ticks == 51
    assert w.lag_oracle == w.lag_blastem == 1
    assert w.agrees()


def test_compare_counts_extra_blastem_lag():
    w = bw.compare(_rows(50, lag_at=(310,)), _rows(50, lag_at=(310, 333)))
    assert (w.lag_oracle, w.lag_blastem) == (1, 2)
    assert w.extra_lag_ticks == (333,)
    assert w.first_divergent_tick is None          # positions are tick-keyed, so they agree
    assert not w.agrees()


def test_compare_accepts_leg_run_row_dicts():
    # leg_run rows: the first row's dfc is against the t0-1 hit that is not itself a row.
    b = _rows(5, lag_at=(300,))
    o = [dict(t=r.tick, fc=r.frame_counter, dfc=(2 if r.tick == 300 else 1), dlt=1, cx=r.cx,
              cy=r.cy, px=r.px, py=r.py) for r in b[1:]]
    w = bw.compare(o, b)
    assert (w.lag_oracle, w.lag_blastem) == (1, 1)
    assert w.first_divergent_tick is None and w.oracle_ticks == 5


def test_compare_frame_counter_wraps():
    o = _rows(5, fc0=0xFFFE)
    w = bw.compare(o, o)
    assert w.lag_oracle == 0


def test_compare_no_common_ticks_is_loud():
    with pytest.raises(bw.WitnessError):
        bw.compare(_rows(5, t0=300), _rows(5, t0=900))


# ---- the open-loop replay core, against a fake stub ---------------------------------------

class FakeStub:
    """Input_Tick hits with Logic_Tick 1, 2, ...; a lag frame every `lag_every` ticks. Records
    every pad write as (tick, held, press)."""
    FC, LT, HELD, CX, CY, TGT, IT = 0xFF8002, 0xFF8004, 0xFF8028, 0xFFA6E2, 0xFFA6E6, 0xFFADFE, \
        0x2674

    def __init__(self, lag_every=0, skip_at=None):
        self.tick, self.fc, self.lag_every, self.skip_at = 0, 0, lag_every, skip_at
        self.writes, self.bps, self.closed = [], [], False

    def wait_ready(self):
        return b"S05"

    def bp(self, a):
        self.bps.append(a)
        return b"OK"

    def cont_or_interrupt(self, t=4.0):
        self.tick += 2 if self.skip_at is not None and self.tick + 1 == self.skip_at else 1
        self.fc += 2 if self.lag_every and self.tick % self.lag_every == 0 else 1
        return b"T05", False

    def read_mem(self, addr, n):
        mem = {self.FC: self.fc.to_bytes(2, "big") + self.tick.to_bytes(4, "big"),
               self.LT: self.tick.to_bytes(4, "big"),
               self.CX: (96).to_bytes(2, "big") + b"\0\0" + (400).to_bytes(2, "big"),
               self.CY: (400).to_bytes(2, "big"),
               self.TGT: (0x9000).to_bytes(2, "big"),
               0xFF9000: bytes(64)}
        return mem[addr][:n].ljust(n, b"\0")

    def write_mem(self, addr, data):
        assert addr == self.HELD
        self.writes.append((self.tick, data[0], data[1]))
        return b"OK"

    def close(self):
        self.closed = True


def _syms():
    import leg_drive as ld
    addr = dict(Frame_Counter=0xFF8002, Logic_Tick=0xFF8004, Ctrl_1_Held=0xFF8028,
                Ctrl_1_Press=0xFF8029, Camera_X=0xFFA6E2, Camera_Y=0xFFA6E6,
                Camera_X_Max=0xFFADFA, Camera_Target=0xFFADFE, Input_Tick=0x2674)
    return ld.Syms(addr=addr, equ={}, off=dict(x_pos=2, y_pos=6), buttons=None, debug=False)


def test_replay_writes_held_and_press_keyed_to_tick():
    stub = FakeStub(lag_every=7)
    log = {"t0": 5, "held": [8, 8, 0x28, 0x28, 8]}
    rows = bw.replay(stub, _syms(), log, n_ticks=5)
    assert stub.bps == [0x2674]
    # nothing written before t0; held per tick from the log; press = the edge vs the last write
    assert stub.writes == [(5, 8, 8), (6, 8, 0), (7, 0x28, 0x20), (8, 0x28, 0), (9, 8, 0)]
    assert [r.tick for r in rows] == [4, 5, 6, 7, 8, 9]        # t0-1 baseline + n_ticks
    assert rows[3].frame_counter - rows[2].frame_counter == 2   # tick 7 followed a lag frame


def test_replay_refuses_a_missed_tick():
    with pytest.raises(bw.WitnessError):
        bw.replay(FakeStub(skip_at=6), _syms(), {"t0": 5, "held": [0] * 5}, n_ticks=5)


def test_replay_refuses_more_ticks_than_the_log_holds():
    with pytest.raises(bw.WitnessError):
        bw.replay(FakeStub(), _syms(), {"t0": 5, "held": [0] * 3}, n_ticks=5)


# ---- doc / code drift ---------------------------------------------------------------------

def _section(text: str, title: str) -> str:
    m = re.search(r"^## (?:\d+\. )?" + re.escape(title) + r"\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"{DOC.name}: no '## {title}' section"
    return m.group(1)


def _value(cell: str):
    cell = cell.strip().strip("*`").replace(",", "")
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", cell)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(r"([\d.]+)\s*%", cell)
    if m:
        return Fraction(m.group(1)) / 100
    return Fraction(cell)


def _table(sec: str) -> dict:
    out = {}
    for ln in sec.splitlines():
        m = re.match(r"^\|\s*`([A-Z][A-Z0-9_]+)`\s*\|\s*([^|]+?)\s*\|", ln)
        if m:
            out[m.group(1)] = _value(m.group(2))
    return out


def _code(n):
    # str() first: Fraction(0.026) is the binary float, Fraction("0.026") is 13/500.
    return Fraction(str(getattr(lc, n)))


def test_constants_match_hardware_limits_doc():
    sec = _section(DOC.read_text(), SECTION)
    table = _table(sec)
    names = ("FRAME_CYCLES", "MCLK_PER_LINE", "LINES_PER_FRAME", "BLANK_DMA_LINES",
             "DMA_END_LIMIT_LINE", "REFRESH_FRACTION", "Z80_STALL_MAX_FRACTION",
             "WITNESS_MARGIN_FRACTION")
    assert set(names) <= set(table), f"doc table lacks {set(names) - set(table)}"
    for n in names:
        assert table[n] == _code(n), f"{n}: doc {table[n]} != code {getattr(lc, n)}"
    # The rule's prose states the same numbers; read them too, so neither half can drift.
    prose = {
        "BLANK_DMA_LINES": r"\*\*(\d+) lines\*\*, not 38",
        "DMA_END_LIMIT_LINE": r"no DMA ends after line (\d+) \+ 0",
        "REFRESH_FRACTION": r"\((\d+ cycles in \d+)",
        "WITNESS_MARGIN_FRACTION": r"under (\d+%) of its budget",
        "Z80_STALL_MAX_FRACTION": r"up to about ([\d.]+%) with sound",
    }
    for n, rx in prose.items():
        m = re.search(rx, sec)
        assert m, f"rule prose: no match for {n} ({rx})"
        got = _value(m.group(1).replace(" cycles in ", "/"))
        assert got == _code(n), f"{n}: prose {got} != code {getattr(lc, n)}"


def _rule(sec: str, n: int) -> str:
    m = re.search(rf"^{n}\. (.*?)(?=^\d+\. |^\s*$)", sec, re.M | re.S)
    assert m, f"{DOC.name}: no rule {n} in '{SECTION}'"
    return m.group(1)


def test_frame_cycles_derived_from_lines_and_mclk():
    assert lc.FRAME_CYCLES == round(lc.LINES_PER_FRAME * lc.MCLK_PER_LINE / 7)
    assert lc.FRAME_CYCLES != 127_840          # the retired FRAME_CYC must not come back


# ---- fix round 1, finding 1: a partial witness must never read as agreement --------------

def _leg_result(tmp_path, n=40, t0=300, lag_at=(310,)):
    wrows = _rows(n, t0=t0, lag_at=lag_at)
    rows = [dict(t=r.tick, fc=r.frame_counter, dfc=(r.frame_counter - p.frame_counter) & 0xFFFF,
                 dlt=1, cx=r.cx, cy=r.cy, px=r.px, py=r.py) for p, r in zip(wrows, wrows[1:])]
    res = {"provenance": {"rom": {"crc32": "00000000", "size": 4}}, "leg": "run", "phase": 0,
           "lag": {"frames": len(lag_at), "ticks": n}, "rows": rows,
           "input_log": {"t0": t0, "held": [8] * n}}
    p = tmp_path / "s4_run_p0.json"
    p.write_text(__import__("json").dumps(res))
    return p, wrows


def _stub_main(monkeypatch, wrows):
    """Run blastem_witness.main with BlastEm replaced by `wrows` cut to the asked ticks."""
    monkeypatch.setattr(bw.lp, "rom_provenance", lambda rom, lst: {"crc32": "00000000", "size": 4})
    monkeypatch.setattr(bw.lp, "aeon_provenance", lambda: {"commit": "x", "dirty": False})
    monkeypatch.setattr(bw.lp, "sha256_file", lambda p: "0" * 64)
    monkeypatch.setattr(bw.ld, "resolve_syms", lambda lst: None)
    monkeypatch.setattr(bw, "blastem_binary", lambda: Path("/nonexistent/blastem"))

    def fake_run(rom, lst, log, n, **kw):
        return [r for r in wrows if r.tick < log["t0"] + n]
    monkeypatch.setattr(bw, "run_blastem", fake_run)


def test_short_ticks_witness_does_not_agree(tmp_path, monkeypatch):
    import json
    res, wrows = _leg_result(tmp_path, n=40)
    _stub_main(monkeypatch, wrows)
    rc = bw.main(["--rom", "r.bin", "--lst", "r.lst", "--result", str(res), "--ticks", "10"])
    out = json.loads((tmp_path / "s4_run_p0.json.blastem.json").read_text())
    assert out["status"] == "MEASURED"
    assert out["comparison"]["partial"] is True
    assert out["comparison"]["oracle_ticks"] == 40          # the FULL leg, not the cut window
    assert out["comparison"]["agrees"] is False
    assert rc == 1


def test_full_ticks_witness_agrees_through_main(tmp_path, monkeypatch):
    import json
    res, wrows = _leg_result(tmp_path, n=40)
    _stub_main(monkeypatch, wrows)
    rc = bw.main(["--rom", "r.bin", "--lst", "r.lst", "--result", str(res)])
    out = json.loads((tmp_path / "s4_run_p0.json.blastem.json").read_text())
    assert out["comparison"]["partial"] is False and out["comparison"]["agrees"] is True
    assert rc == 0


def test_partial_flag_alone_refuses_agreement():
    assert not _agree(partial=True).agrees()
    assert lc.classify(3800, 128_006, 16_418, False, _agree(partial=True)) == "WITNESS-DISAGREES"


def test_compare_failure_in_main_is_recorded_could_not_run(tmp_path, monkeypatch):
    import json
    res, wrows = _leg_result(tmp_path, n=40)
    _stub_main(monkeypatch, [bw.WitnessRow(9000 + i, i, 0, 0, 0, 0) for i in range(3)])
    monkeypatch.setattr(bw, "run_blastem", lambda *a, **kw: [bw.WitnessRow(9000, 1, 0, 0, 0, 0)])
    rc = bw.main(["--rom", "r.bin", "--lst", "r.lst", "--result", str(res)])
    out = json.loads((tmp_path / "s4_run_p0.json.blastem.json").read_text())
    assert rc == 2 and out["status"] == "COULD NOT RUN" and "compare" in out["reason"]


def test_doc_states_what_the_code_actually_subtracts():
    """Rule 3 states the code's exact correction terms (fix round 1 finding 2; reworded by
    owner-proxy ruling Q3, 2026-11-17), in order: the refresh alone (silent), then refresh +
    the Z80 stall bound (with sound). Both figures are DERIVED here from leg_correction's
    constants, never copied, so a change to the doc or to the code turns this red."""
    sec = _section(DOC.read_text(), SECTION)
    rule = _rule(sec, 3)
    stated = [_value(x) for x in re.findall(r"\*\*([\d.]+%)\*\*", rule)]
    silent = _code("REFRESH_FRACTION")
    sound = silent + _code("Z80_STALL_MAX_FRACTION")
    assert stated == [silent, sound], (
        f"rule 3 states {[f'{float(x) * 100:g}%' for x in stated]}, code subtracts "
        f"{float(silent) * 100:g}% silent and {float(sound) * 100:g}% with sound")
    assert "2-4%" not in rule, "rule 3 still quotes the retired rounded band"
    assert "Rule 4 is not a second correction" in sec
