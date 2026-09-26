#!/usr/bin/env python3
"""tools/loop_step_over_witness.py: its verdict, its crossing prediction, and its start height.

These rows run the SHIPPED main() -> run_one() -> summarise() -> verdict() with only drive()
and the emulator faked, so no emulator boots and no build artifact is read.

KEEPALIVE-IS-BLIND-TO-LOSSY (docs/research/2026-09-25-keepalive-lossy.md): a drive that
reached ErrorHandler is never a clean exit. LINES-EVERYWHERE (2026-09-26): the witness now
GRADES every frame against the ROM's own layer-line table, so a frame whose layer or priority
disagrees with Obj03's rule over the drive's own positions is exit 1, a ROM with no table is
exit 2 (COULD NOT GRADE), and a graded run that crossed nothing is exit 2 as well. LOOP-EXIT
(2026-09-26): every drive is also held to one lap, then leaving on plane A (the LAP CHECK
rows at the end); the double lap the old floor lines produced is exit 1.
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
        r = res(a[7]) if callable(res) else res          # a[7] is drive()'s `direction`
        return {"rows": list(r["rows"]), "table": r["table"], "start": (1000, 576)}

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
    """The control for the rows below: one lap each way over LOOP-EXIT's line layout, every
    tick agreeing with the table, leaving on plane A."""
    _stub(monkeypatch, lambda d: {"rows": _lap(d), "table": LAP_TABLE}, argv)
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 0, text
    assert text.count("LAP CHECK (right): OK") and text.count("LAP CHECK (left): OK")


@pytest.mark.parametrize("argv", ARGVS)
def test_a_rom_without_a_table_could_not_grade(monkeypatch, capsys, argv):
    xs, lp = _honest(6)
    _stub(monkeypatch, {"rows": _rows(xs, lp), "table": None}, argv)
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 2, text
    assert "COULD NOT GRADE" in text


def test_a_graded_drive_that_crossed_nothing_could_not_grade(monkeypatch, capsys):
    xs = [1100 + 2 * k for k in range(20)]    # never reaches x 1144, nor either far side
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


# ---------------------------------------------------------------------------------------
# THE LAP CHECK (LOOP-EXIT, 2026-09-26): one lap, then leave on plane A.
# ---------------------------------------------------------------------------------------

_TO_B = (1 << 3) | (1 << 5)                   # LL_FWD_B | LL_FWD_HI, EQUS's bit numbers
#: LOOP-EXIT's layout: entry west (right -> B high, left -> A low), the two crown lines
#: (same, grounded-only, y 384..447), exit east (A low both ways). The table the witness reads
#: out of the ROM.
LAP_TABLE = [{"key": 1024, "a": 512, "b": 576, "flags": _TO_B},
             {"key": 1144, "a": 384, "b": 448, "flags": _TO_B | (1 << 1)},
             {"key": 1152, "a": 384, "b": 448, "flags": _TO_B | (1 << 1)},
             {"key": 1280, "a": 384, "b": 576, "flags": 0}]
#: The table that was shipped until LOOP-EXIT: crown and floor lines at x 1144/1152.
OLD_TABLE = [{"key": k, "a": a, "b": a + 32, "flags": _TO_B}
             for k in (1144, 1152) for a in (416, 544)]
FLOOR, TOP, LEFT_ARC, RIGHT_ARC = 557, 430, 1082, 1222


def _path(direction, laps=1, step=6):
    """End-of-tick positions of a rider going round the loop `laps` times: along the floor,
    up the far arc, across the crown against the drive, down the near arc, and on."""
    def seg(a, b, fixed, axis):
        d = step if b > a else -step
        return [((v, fixed) if axis == "x" else (fixed, v)) for v in range(a, b, d)]
    if direction == "right":
        pts = seg(1000, RIGHT_ARC, FLOOR, "x")
        for _ in range(laps):
            pts += (seg(FLOOR, TOP, RIGHT_ARC, "y") + seg(RIGHT_ARC, LEFT_ARC, TOP, "x")
                    + seg(TOP, FLOOR, LEFT_ARC, "y"))
            pts += seg(LEFT_ARC, RIGHT_ARC if _ < laps - 1 else 1420, FLOOR, "x")
    else:
        pts = seg(1350, LEFT_ARC, FLOOR, "x")
        for _ in range(laps):
            pts += (seg(FLOOR, TOP, LEFT_ARC, "y") + seg(LEFT_ARC, RIGHT_ARC, TOP, "x")
                    + seg(TOP, FLOOR, RIGHT_ARC, "y"))
            pts += seg(RIGHT_ARC, LEFT_ARC if _ < laps - 1 else 930, FLOOR, "x")
    return pts


def _lap(direction, laps=1, table=None, gsp=0x600):
    """A trace along _path() whose (layer, prio) is what Obj03's rule over `table` makes it,
    one tick late, exactly as predict() expects: an honest ROM."""
    table = LAP_TABLE if table is None else table
    sign = 1 if direction == "right" else -1
    rows = [{"frame": f - 1, "x": x, "y": y, "layer": 0, "prio": 0, "air": 0, "angle": 0,
             "gsp": sign * gsp} for f, (x, y) in enumerate(_path(direction, laps))]
    for _ in range(64):
        bad, _fires = L.predict(rows, table, EQUS)
        if not bad:
            return rows
        frame, want = bad[0][0], bad[0][1]
        for r in rows:
            if r["frame"] >= frame:
                r["layer"], r["prio"] = want
    raise AssertionError("the synthetic trace did not settle")


def test_the_loop_geometry_is_derived():
    """The crown test's numbers come from the drives and the committed collision: the
    midpoint of the two drive starts, half way between the floor and the loop's ceiling, and
    the air above the crown (a riding centre stays between the last two), and which plane each
    arc is on (the left arc is plane A's, the right arc plane B's)."""
    assert L.LOOP_MID_X == (L.DRIVES["right"]["x"] + L.DRIVES["left"]["x"]) // 2
    g = L.loop_geometry()
    assert g["top"] < TOP < g["half"] < FLOOR, g
    assert g["arc"] == {"left": 0, "right": 1}, g
    # the synthetic riders below stay inside both arcs' inner faces, as real riders do
    assert L.LOOP_SIDES[0] < g["face"]["left"] < LEFT_ARC < RIGHT_ARC < g["face"]["right"], g


def test_an_airborne_pass_over_the_interior_is_not_a_lap():
    """Measured at 11 px/frame from some phases: the rider comes off the far arc and flies
    across the loop's interior, below the crown. Not a lap (the crown lines are grounded-only
    for the same reason): the drive is NOT MEASURED, never a lap or a wrong-plane descent."""
    rows = _lap("right")
    for r in rows:
        if r["y"] == TOP:
            r["air"] = 1
    lap = L.lap_check(rows, "right", EQUS)
    assert lap["laps"] == 0 and lap["verdict"] == "unmeasured", lap


def test_falling_through_the_floor_or_leaving_over_the_top_is_named_not_passed():
    """One lap on the right planes, then the collision loses him: measured 2026-09-26 at
    3..10 px/frame rightward from some phases (angle $24 held past the left arc's foot,
    through the floor) and at 10 px/frame (thrown right along the crown's underside). NOT
    MEASURED with the fault named; a wrong LAYER at the same exit still fails."""
    rows = _lap("right")
    ex = next(r for r in rows if r["x"] >= L.LOOP_SIDES[1])
    for mutate, needle in ((dict(air=1, y=ex["y"] + 380), "FELL THROUGH THE FLOOR"),
                           (dict(air=1, y=414), "LEFT OVER THE TOP")):
        rs = [dict(r, **mutate) if r is ex else r for r in rows]
        lap = L.lap_check(rs, "right", EQUS)
        assert lap["verdict"] == "unmeasured" and needle in lap["why"], (mutate, lap)
        rs = [dict(r, layer=1, **mutate) if r is ex else r for r in rows]
        assert L.lap_check(rs, "right", EQUS)["verdict"] == "fail"


@pytest.mark.parametrize("direction", ["right", "left"])
def test_coming_down_on_the_wrong_plane_fails(direction):
    """Red for the crown-extent defect measured on the old lines: a leftward rider at 9 and
    16 px/frame crossed the crown ABOVE its lines, stayed on A, and came down the right arc's
    side on the wrong plane. Here: the crown lines are removed, so the rider crosses the top
    on the plane he climbed with."""
    table = [r for r in LAP_TABLE if r["key"] not in (1144, 1152)]
    lap = L.lap_check(_lap(direction, table=table), direction, EQUS)
    assert lap["verdict"] == "fail" and "WRONG PLANE" in lap["why"], lap


def test_going_out_through_the_crown_is_not_a_lap():
    """Measured at PHYS_GSP_CAP leftward from some phases, before and after LOOP-EXIT alike:
    the rider climbs the left arc and passes UP through the crown, crossing LOOP_MID_X above
    it, and ends standing on top of the loop. That crossing is not a lap, and the drive is
    NOT MEASURED with the crown named, not failed: it is a collision fault, not a layer one."""
    top = L.loop_geometry()["top"]
    rows = [r for r in _lap("left") if r["y"] == FLOOR and r["x"] >= LEFT_ARC]
    f = rows[-1]["frame"]
    rows += [dict(rows[-1], frame=f + k, x=LEFT_ARC + 4 * k, y=FLOOR - 12 * k) for k in range(1, 40)
             if FLOOR - 12 * k > top - 60]
    rows += [dict(rows[-1], frame=rows[-1]["frame"] + k, x=rows[-1]["x"] + 6 * k)
             for k in range(1, 10)]                              # across the mid, over the top
    lap = L.lap_check(rows, "left", EQUS)
    assert lap["laps"] == 0 and lap["verdict"] == "unmeasured", lap
    assert "THROUGH THE CROWN" in lap["why"]


@pytest.mark.parametrize("direction", ["right", "left"])
def test_one_lap_leaving_on_a_is_ok(direction):
    lap = L.lap_check(_lap(direction), direction, EQUS)
    assert lap["verdict"] == "ok" and lap["laps"] == 1, lap
    assert lap["exit"]["layer"] == 0 and lap["exit"]["prio"] == 0


@pytest.mark.parametrize("direction", ["right", "left"])
def test_the_old_floor_lines_are_a_double_lap(monkeypatch, capsys, direction):
    """THE DEFECT, red. Over the pre-LOOP-EXIT table the floor lines put a rider leaving a
    lap back on the plane of the arc ahead, so he goes round again. The line grade alone
    PASSES this trace (every tick agrees with the table); the lap check is what fails it."""
    rows = _lap(direction, laps=2, table=OLD_TABLE)
    bad, fires = L.predict(rows, OLD_TABLE, EQUS)
    assert fires and not bad                         # the grade is blind to it
    _stub(monkeypatch, {"rows": rows, "table": OLD_TABLE}, ["--dir", direction])
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 1, text
    assert "DOUBLE LAP: 2 laps" in text


def test_leaving_on_plane_b_fails():
    """One lap, but a table whose exit line puts the rider on B: the exit state is graded."""
    table = [dict(r, flags=_TO_B) for r in LAP_TABLE]          # exit line now "right: B"
    lap = L.lap_check(_lap("right", table=table), "right", EQUS)
    assert lap["verdict"] == "fail" and "not plane A" in lap["why"] and "high priority" in lap["why"]


def test_leaving_airborne_or_fallen_or_reversed_fails():
    rows = _lap("right")
    ex = next(r for r in rows if r["x"] >= L.LOOP_SIDES[1])
    for mutate, needle in ((dict(air=1), "airborne"), (dict(y=ex["y"] + 200), "landed height"),
                           (dict(gsp=-5), "not moving right")):
        rs = [dict(r, **mutate) if r is ex else r for r in rows]
        lap = L.lap_check(rs, "right", EQUS)
        assert lap["verdict"] == "fail" and needle in lap["why"], (mutate, lap)


def test_a_lap_with_no_exit_fails_and_no_lap_is_not_measured():
    rows = _lap("right")
    ex = next(i for i, r in enumerate(rows) if r["x"] >= L.LOOP_SIDES[1])
    lap = L.lap_check(rows[:ex], "right", EQUS)
    assert lap["verdict"] == "fail" and "never reached" in lap["why"]
    stop = next(i for i, r in enumerate(rows) if r["y"] < 480)       # climbed, fell back
    lap = L.lap_check(rows[:stop], "right", EQUS)
    assert lap["verdict"] == "unmeasured"


def test_passing_the_loop_without_riding_it_fails():
    rows = [r for r in _lap("right") if r["y"] == FLOOR and r["x"] <= RIGHT_ARC]
    rows += [dict(rows[-1], frame=rows[-1]["frame"] + k, x=RIGHT_ARC + 6 * k)
             for k in range(1, 40)]
    lap = L.lap_check(rows, "right", EQUS)
    assert lap["verdict"] == "fail" and "WITHOUT riding" in lap["why"]


def test_a_run_where_no_drive_completed_could_not_grade(monkeypatch, capsys):
    rows = _lap("right")
    stop = next(i for i, r in enumerate(rows) if r["y"] < 480)
    _stub(monkeypatch, {"rows": rows[:stop], "table": LAP_TABLE}, ["--dir", "right"])
    rc = L.main()
    text = capsys.readouterr().out
    assert rc == 2, text
    assert "no drive completed the loop" in text and "NOT MEASURED" in text


def test_thrown_out_backwards_then_a_clean_retry_is_not_a_double_lap():
    """Measured at 13 and 15 px/frame rightward from some phases after LOOP-EXIT: over the
    crown, then out THROUGH the left arc (grounded on plane A, its own plane), back past the
    near side, and a clean second attempt. The second crown crossing belongs to a new
    attempt, so the drive is NOT MEASURED with the fault named, never a DOUBLE LAP; two laps
    before any such exit still are (the old floor lines' defect, above)."""
    one = _lap("right")
    crown = next(i for i, r in enumerate(one) if r["y"] == TOP and r["x"] < 1130)  # on A now
    out = [dict(one[crown], frame=one[crown]["frame"] + k, x=LEFT_ARC - 8 * k, y=FLOOR)
           for k in range(1, 20)]                            # out through the left arc
    retry = [dict(r, frame=out[-1]["frame"] + 1 + i) for i, r in enumerate(_lap("right"))]
    rows = one[:crown + 1] + out + retry
    lap = L.lap_check(rows, "right", EQUS)
    assert lap["verdict"] == "unmeasured" and "THROWN OUT THROUGH THE LEFT ARC" in lap["why"], lap
    lap2 = L.lap_check(_lap("right", laps=2, table=OLD_TABLE) + out, "right", EQUS)
    assert lap2["verdict"] == "fail" and "DOUBLE LAP" in lap2["why"]


# ---------------------------------------------------------------------------------------
# THE STAND-REVERSE ARM (LOOP-EXIT): standing and turning at the two floor lines.
# ---------------------------------------------------------------------------------------

def test_the_stand_reverse_lines_come_from_the_committed_file():
    assert L.floor_lines() == {"entry": 1024, "exit": 1280}


def _walk(xs, table):
    """A walk along the floor through end-of-tick xs, layered honestly by `table`."""
    rows = [{"frame": f - 1, "x": x, "y": FLOOR, "layer": 0, "prio": 0, "air": 0, "angle": 0,
             "gsp": 0} for f, x in enumerate(xs)]
    for _ in range(16):
        bad, _fires = L.predict(rows, table, EQUS)
        if not bad:
            return rows
        for r in rows:
            if r["frame"] >= bad[0][0]:
                r["layer"], r["prio"] = bad[0][1]
    raise AssertionError("did not settle")


def _stub_sr(monkeypatch, table, walk_for):
    monkeypatch.setattr(L, "parse_lst", lambda lst, *a, **k: ({}, dict(EQUS)))

    @contextlib.contextmanager
    def fake_emulator(rom, symbols=None):
        yield "fake.sock"

    async def fake_drive(*a, script=None, x_start=None, **k):
        return {"rows": walk_for(x_start, a[6]), "table": table, "start": (x_start, 576)}

    monkeypatch.setattr(L, "aether_emulator", fake_emulator)
    monkeypatch.setattr(L, "drive", fake_drive)


def _there_and_back(key, dx, table):
    """From key + dx: over the line and back again (standing still when dx is 0)."""
    x0 = key + dx
    if dx == 0:
        return _walk([x0] * 20, table)
    toward = 1 if dx < 0 else -1
    xs = [x0 + toward * 2 * k for k in range(12)]
    xs += [xs[-1] - toward * 2 * k for k in range(1, 12)]
    return _walk(xs, table)


def test_stand_reverse_passes_on_the_committed_layout(monkeypatch, capsys):
    _stub_sr(monkeypatch, LAP_TABLE, lambda key, dx: _there_and_back(key, dx, LAP_TABLE))
    rc, _ = L.stand_reverse("x.bin", "x.lst", False)
    assert rc == 0, capsys.readouterr().out


def test_stand_reverse_fails_on_plane_b_at_the_exit(monkeypatch, capsys):
    """Red: an exit line that puts a rightward walker on B (the mutation also run on a real
    ROM, 2026-09-26) fails even though every tick agrees with that table."""
    table = [dict(r, flags=_TO_B) if r["key"] == 1280 else r for r in LAP_TABLE]
    _stub_sr(monkeypatch, table, lambda key, dx: _there_and_back(key, dx, table))
    rc, _ = L.stand_reverse("x.bin", "x.lst", False)
    text = capsys.readouterr().out
    assert rc == 1 and "on plane B beside the exit line" in text, text


def test_stand_reverse_that_never_crossed_could_not_grade(monkeypatch, capsys):
    _stub_sr(monkeypatch, LAP_TABLE, lambda key, dx: _walk([key + dx] * 20, LAP_TABLE))
    rc, _ = L.stand_reverse("x.bin", "x.lst", False)
    assert rc == 2, capsys.readouterr().out
