#!/usr/bin/env python3
"""tools/loop_step_over_witness.py: its verdict, its crossing prediction, and its start height.

These rows run the SHIPPED main() -> run_one() -> summarise() -> verdict() with only drive()
and the emulator faked, so no emulator boots and no build artifact is read.

KEEPALIVE-IS-BLIND-TO-LOSSY (docs/research/2026-09-25-keepalive-lossy.md): a drive that
reached ErrorHandler is never a clean exit. LINES-EVERYWHERE (2026-09-26): the witness now
GRADES every frame against the ROM's own layer-line table, so a frame whose layer or priority
disagrees with Obj03's rule over the drive's own positions is exit 1, a ROM with no table is
exit 2 (COULD NOT GRADE), and a graded run that crossed nothing is exit 2 as well.
"""

import contextlib

import pytest

import loop_step_over_witness as L

EQUS = {"PHYS_TOP_SPEED": 0x600, "COLL_CELL_W": 8, "PHYS_GSP_CAP": 0x1000,
        "LL_KEEP_PATH": 0, "LL_GROUNDED": 1, "LL_HORIZONTAL": 2, "LL_FWD_B": 3,
        "LL_BACK_B": 4, "LL_FWD_HI": 5, "LL_BACK_HI": 6, "LAYER_PATH_A": 0, "LAYER_PATH_B": 1}
#: One vertical line at x 1144, y 544..576: right -> B high, left -> A low (OJZ's shape).
TABLE = [{"key": 1144, "a": 544, "b": 576, "flags": (1 << 3) | (1 << 5)}]


def _rows(xs, lp):
    """A trace from end-of-frame X positions and the (layer, prio) the ROM reported."""
    return [{"frame": f - 1, "x": x, "y": 556, "layer": l, "prio": p, "air": 0, "angle": 0,
             "gsp": 0x600} for f, (x, (l, p)) in enumerate(zip(xs, lp))]


def _honest(step, n=40, x0=1100):
    """A rightward run at `step` px/frame whose layer follows the one-line table with the
    routine's one-frame lag: the crossing between samples k-1 and k shows at sample k+1."""
    xs = [x0 + step * k for k in range(n)]
    cross = next(k for k in range(1, n) if xs[k - 1] < 1144 <= xs[k])
    lp = [(1, 1) if j >= cross + 1 else (0, 0) for j in range(n)]
    return xs, lp


def _stub(monkeypatch, res, extra_argv):
    monkeypatch.setattr(L, "parse_lst", lambda lst, *a, **k: ({}, dict(EQUS)))

    @contextlib.contextmanager
    def fake_emulator(rom, symbols=None):
        yield "fake.sock"

    async def fake_drive(*a, **k):
        return {"rows": list(res["rows"]), "table": res["table"], "start": (1000, 576)}

    monkeypatch.setattr(L, "aether_emulator", fake_emulator)
    monkeypatch.setattr(L, "drive", fake_drive)
    monkeypatch.setattr(L.sys, "argv", ["loop_step_over_witness.py", "--rom", "x.bin",
                                        "--lst", "x.lst"] + extra_argv)


FAULT = {"frame": 5, "fault": "ErrorHandler", "pc": "0x000200"}
ARGVS = [["--no-assert-grounded"], ["--phase-sweep"], []]


@pytest.mark.parametrize("argv", ARGVS)
def test_a_drive_that_faulted_exits_1(monkeypatch, capsys, argv):
    xs, lp = _honest(6, 12)
    _stub(monkeypatch, {"rows": _rows(xs, lp) + [FAULT], "table": TABLE}, argv)
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 1, f"a drive that reached ErrorHandler exited {rc} under {argv}:\n{text}"
    assert "the ROM FAULTED" in text


@pytest.mark.parametrize("argv", ARGVS)
def test_an_honest_drive_over_a_table_passes(monkeypatch, capsys, argv):
    """The control for the two rows below: the same drive, agreeing with the table."""
    xs, lp = _honest(6)
    _stub(monkeypatch, {"rows": _rows(xs, lp), "table": TABLE}, argv)
    rc = L.main()
    assert rc == 0, capsys.readouterr().out


@pytest.mark.parametrize("argv", ARGVS)
def test_a_rom_without_a_table_could_not_grade(monkeypatch, capsys, argv):
    xs, lp = _honest(6)
    _stub(monkeypatch, {"rows": _rows(xs, lp), "table": None}, argv)
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 2, text
    assert "COULD NOT GRADE" in text


def test_a_graded_drive_that_crossed_nothing_could_not_grade(monkeypatch, capsys):
    xs = [900 + 2 * k for k in range(20)]                   # never reaches x 1144
    _stub(monkeypatch, {"rows": _rows(xs, [(0, 0)] * 20), "table": TABLE}, [])
    assert L.main() == 2


@pytest.mark.parametrize("step", [6, 9, 16])
def test_a_stepped_over_line_is_a_disagreement(monkeypatch, capsys, step):
    """THE STEP-OVER CLASS, red. A ROM that failed to fire the line (the layer stays 0 while
    the drive crossed x 1144) must fail at every speed, including the ones above one cell a
    frame where a painted mark was skipped."""
    xs, _lp = _honest(step)
    _stub(monkeypatch, {"rows": _rows(xs, [(0, 0)] * len(xs)), "table": TABLE}, ["--gsp", "0x600"])
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 1, text
    assert "DISAGREE" in text


def test_the_priority_bit_is_graded_on_its_own():
    """A ROM that moved the layer but not the priority bit disagrees: the lines set priority
    from their own bits, and the grade reads both."""
    xs, lp = _honest(6)
    bad, fires = L.predict(_rows(xs, [(l, 0) for l, _p in lp]), TABLE, EQUS)
    assert fires and bad and all(want == (1, 1) and got == (1, 0) for _f, want, got, _w in bad[:1])


def test_a_discontinuity_crosses_nothing():
    """A step longer than the physics cap (a teleport) crosses no line, as in the routine."""
    xs = [1100, 1100, 1200, 1200, 1200]
    bad, fires = L.predict(_rows(xs, [(0, 0)] * 5), TABLE, EQUS)
    assert not fires and not bad


def test_a_grounded_only_line_is_skipped_airborne():
    table = [dict(TABLE[0], flags=TABLE[0]["flags"] | (1 << 1))]
    xs, lp = _honest(6)
    rows = _rows(xs, [(0, 0)] * len(xs))
    for r in rows:
        r["air"] = 1
    bad, fires = L.predict(rows, table, EQUS)
    assert not fires and not bad


def test_the_start_height_is_derived_from_the_editor_collision():
    """Both starts stand on the loop's floor, found in the committed plane-A collision, not
    typed: the old START_Y went stale twice as the paint moved."""
    for x in (L.DRIVES["right"]["x"], L.DRIVES["left"]["x"]):
        assert abs(L.ground_feet(x, 39) - L.LOOP_FLOOR_Y) <= L.FLOOR_SLACK


def test_a_lag_frame_does_not_shift_the_prediction():
    """A lag frame repeats the previous GAME TICK's sample. The routine's lag is one tick,
    so the layer change shows one TICK after the crossing, which here is two emulator
    frames. The grade keeps one sample per Logic_Tick; without that it expects the change
    on the repeated (lagged) sample and reports a disagreement that is not there."""
    xs, lp = _honest(6)
    rows = _rows(xs, lp)
    for k, r in enumerate(rows):
        r["tick"] = 1000 + k
    cross = next(k for k in range(1, len(xs)) if xs[k - 1] < 1144 <= xs[k])
    lagged = dict(rows[cross], frame=rows[cross]["frame"] + 0.5)   # same tick, same state
    rows = rows[:cross + 1] + [lagged] + rows[cross + 1:]
    bad, fires = L.predict(rows, TABLE, EQUS)
    assert fires and not bad, bad
