"""Tests for tools/leg_drive.py (v2 B2: tick-keyed closed-loop leg driver).

The pure lane (no artifacts, no emulator) drives the decision core with synthetic TickState
series. The one emulator-backed test is `@pytest.mark.needs_build` and runs in the post-sigil
lane (tools/needs_build_lane.py)."""
import asyncio
from pathlib import Path

import pytest

import leg_drive as ld

AEON = Path(__file__).resolve().parent.parent
# Button bits as the listing publishes them (BUTTON_* equates); the tests that need the
# listing-resolution path itself use `ld.buttons_from_equates` on a synthetic listing.
B = ld.Buttons(right=0x08, left=0x04, down=0x02, up=0x01, a=0x40, b=0x10, c=0x20)
R, L, D, C, BB = B.right, B.left, B.down, B.c, B.b
TOP = 0x600
GATE = 0x100      # PHYS_ROLL_START_MIN, the engine's spindash gate
EQ = {"PHYS_TOP_SPEED": TOP, "PHYS_ROLL_START_MIN": GATE, "PSTATE_SPINDASH": 4}


def st(tick, px=100, py=200, xvel=0, yvel=0, gspeed=0, airborne=False, cx=0, cy=0,
       cx_max=5824, fc=None, rolling=False):
    return ld.TickState(tick=tick, frame_counter=tick if fc is None else fc, px=px, py=py,
                        xvel=xvel, yvel=yvel, gspeed=gspeed, airborne=airborne, cx=cx, cy=cy,
                        cx_max=cx_max, rolling=rolling)


# ---- stuck detector -----------------------------------------------------------------------

def test_loop_bounce_is_stuck_although_camera_moves():
    """The x ~ 1046 loop: px bounces inside 1040..1075 (a 35 px band, triangle wave starting
    at the top of the band) while the camera moves EVERY tick. Progress (max px) never grows
    by 32, so the leg is STUCK at the window's end, and not one tick before it."""
    det = ld.ProgressStuck(window_ticks=300, min_progress_px=32)
    seen = {}
    for t in range(400):
        ph = t % 70
        px = 1075 - ph if ph < 35 else 1040 + (ph - 35)
        s = st(t, px=px, cx=900 + t, cy=300 + (t % 3))      # camera changes every tick
        seen[t] = det.observe(s)
    assert not any(seen[t] for t in range(300)), "stuck before the window elapsed"
    assert seen[300], "a 35 px bounce for 300 ticks with a moving camera must read STUCK"


def test_steady_progress_is_not_stuck():
    det = ld.ProgressStuck(window_ticks=300, min_progress_px=32)
    assert not any(det.observe(st(t, px=100 + 2 * t, cx=0)) for t in range(1000))


# ---- policies -----------------------------------------------------------------------------

def test_run_policy_jumps_only_when_blocked():
    p = ld.POLICIES["run"](B, EQ)
    for t in range(100):
        h = p.held(st(t, xvel=0x300, gspeed=0x300))
        assert h == R, f"tick {t}: C at xvel=$300 (not blocked) -> {h:#x}"
    hs = [p.held(st(100 + k, xvel=0, gspeed=0)) for k in range(8)]
    assert hs[:7] == [R] * 7, hs
    assert hs[7] == R | C, "C must arrive on the 8th consecutive blocked tick"


def test_run_policy_never_jumps_on_a_period_or_in_the_air():
    p = ld.POLICIES["run"](B, EQ)
    hs = [p.held(st(t, xvel=0, airborne=True)) for t in range(200)]
    assert all(h == R for h in hs), "blocked counter must only count ON-GROUND ticks"


def spin_seq():
    out = [D] * 4
    for _ in range(4):
        out += [D | C] * 2 + [D] * 4
    out += [D] * 2
    return out


def test_spindash_sequence_shape():
    want = spin_seq()
    assert len(want) == 30
    p = ld.POLICIES["spindash"](B, EQ)
    got = [p.held(st(t, gspeed=0)) for t in range(30)]
    assert got == want
    # sequence over: release down, hold right (a fast roll does not re-trigger)
    assert p.held(st(30, gspeed=0x800)) == R


@pytest.mark.parametrize("name", ["spindash", "diagfall", "topspeed"])
def test_blocked_spindash_family_jumps_on_the_8th_blocked_tick(name):
    """Controller ruling (B2 round 1, finding 1): every moving policy inherits the run rule's
    blocked jump. MEASURED reason: spindash/diagfall p0 were STUCK at px 1143 (the obstacle the
    run leg clears with its blocked jump). Blocked = on ground, |xvel| < $80, 8 ticks running;
    gspeed $200 is above the spindash gate, so no dash competes here."""
    p = ld.POLICIES[name](B, EQ)
    hs = [p.held(st(t, xvel=0, gspeed=0x200)) for t in range(8)]
    assert [h & C for h in hs[:7]] == [0] * 7, f"{name}: C before the 8th blocked tick"
    assert hs[7] & C and hs[7] & R, f"{name}: no blocked jump on the 8th tick"


@pytest.mark.parametrize("name", ["spindash", "diagfall", "topspeed"])
def test_no_blocked_jump_while_rolling_then_jump_from_standing(name):
    """Fix round 2 ruling: the blocked jump fires only on ground, blocked AND not rolling
    (ST_ROLLING clear). MEASURED reason: after a dash at px 1142 the blocked jump fired from
    PSTATE_ROLL, became a roll-jump with no air control (xvel 0 all airtime) and landed back.
    Rolling and blocked: hold right and wait. Standing: C on the 8th blocked tick. gspeed $200
    sits above the dash gate so no dash competes."""
    p = ld.POLICIES[name](B, EQ)
    rolling = [p.held(st(t, xvel=0, gspeed=0x200, rolling=True)) for t in range(40)]
    assert all(h == R for h in rolling), f"{name}: C (or a dash) while rolling and blocked"
    standing = [p.held(st(40 + t, xvel=0, gspeed=0x200)) for t in range(8)]
    assert [h & C for h in standing[:7]] == [0] * 7
    assert standing[7] == R | C, f"{name}: no standing blocked jump on the 8th tick"


def test_run_unaffected_by_the_rolling_rule():
    p = ld.POLICIES["run"](B, EQ)
    hs = [p.held(st(t, xvel=0, gspeed=0, rolling=True)) for t in range(8)]
    assert hs[7] == R | C


def test_rolling_flag_read_from_the_listing_status_bit(tmp_path):
    p = tmp_path / "x.lst"
    p.write_text(LST)
    s = ld.resolve_syms(p, aeon=AEON)
    assert s.equ["ST_ROLLING"] == 4


def test_blocked_at_a_wall_after_a_dash_jumps_not_dashes_again():
    """The px-1143 shape itself: gspeed 0 against a wall. The dash fires first (below the
    gate), its charge ticks are stationary and count as blocked, and on the first tick after
    the release, still blocked, the policy jumps instead of dashing into the wall again. C is
    never pressed as a jump while the sequence runs (its taps are the sequence's own)."""
    for name in ("spindash", "diagfall"):
        p = ld.POLICIES[name](B, EQ)
        got = [p.held(st(t, xvel=0, gspeed=0)) for t in range(31)]
        assert got[:30] == spin_seq() and got[30] == R, name
        assert p.held(st(31, xvel=0, gspeed=0)) == R | C, f"{name}: still blocked -> jump"


def test_spindash_release_tick_is_never_skipped():
    """MEASURED defect (fix round 1 real legs, s4.bin spindash/diagfall p0 STUCK at px 256):
    while charging, the engine reads gspeed 0, so a trigger re-checked on the tick the sequence
    ends restarted it and DOWN was never released -- 0 spindash releases. The release tick
    (right, no down) is part of the sequence and is emitted whatever the state says."""
    for name in ("spindash", "diagfall"):
        p = ld.POLICIES[name](B, EQ)
        got = [p.held(st(t, gspeed=0)) for t in range(31)]
        assert got[:30] == spin_seq() and got[30] == R, name
        # not blocked (moving) and below the gate: a NEW sequence may start after it
        assert p.held(st(31, xvel=0x300, gspeed=0)) == D, name
    p = ld.POLICIES["topspeed"](B, EQ)
    hs = [p.held(st(t, xvel=0x300, gspeed=0x50)) for t in range(30 + 31)]
    assert hs[29:59] == spin_seq() and hs[59] == R, "topspeed: release tick emitted"


def test_spindash_triggers_only_below_the_engine_gate_on_ground():
    """The engine spindashes only below PHYS_ROLL_START_MIN (player_ground.emp:271-279); at or
    above it down rolls. So the family triggers below the gate -- not the plan's TOP/2."""
    for name in ("spindash", "diagfall"):
        p = ld.POLICIES[name](B, EQ)
        assert p.held(st(0, gspeed=TOP // 2 - 1)) == R, f"{name}: $2FF would roll, not dash"
        assert p.held(st(1, gspeed=GATE)) == R
        assert p.held(st(2, gspeed=0, airborne=True)) & D == D or name == "spindash"
        assert p.held(st(3, gspeed=-(GATE - 1))) == D, f"{name}: below the gate -> sequence"


def test_spindash_gate_comes_from_the_listing_equate():
    p = ld.POLICIES["spindash"](B, dict(EQ, PHYS_ROLL_START_MIN=0x40))
    assert p.held(st(0, gspeed=0x40)) == R
    assert p.held(st(1, gspeed=0x3F)) == D
    with pytest.raises(KeyError):
        ld.POLICIES["spindash"](B, {"PHYS_TOP_SPEED": TOP})


def test_topspeed_spindashes_after_30_slow_ground_ticks_below_the_gate():
    p = ld.POLICIES["topspeed"](B, EQ)
    hs = [p.held(st(t, xvel=0x100, gspeed=0x80)) for t in range(30)]
    assert hs[:29] == [R] * 29
    assert hs[29] == D, "30th slow tick (below the gate) starts the spindash sequence"


def test_topspeed_slow_but_above_the_gate_waits():
    """Slow for 30+ ticks at $180 (below $200, above the $100 gate): no dash yet -- it would
    roll. It fires on the first slow tick below the gate."""
    p = ld.POLICIES["topspeed"](B, EQ)
    hs = [p.held(st(t, xvel=0x180, gspeed=0x180)) for t in range(40)]
    assert all(h & D == 0 for h in hs)
    assert p.held(st(40, xvel=0xF0, gspeed=0xF0)) == D


def test_diagfall_holds_down_in_the_air():
    p = ld.POLICIES["diagfall"](B, EQ)
    assert p.held(st(0, gspeed=0x800, airborne=True)) == R | D
    assert p.held(st(1, gspeed=0x800)) == R


def test_idle_is_zero():
    p = ld.POLICIES["idle"](B, EQ)
    assert {p.held(st(t)) for t in range(50)} == {0}
    assert set(ld.POLICIES) == {"idle", "run", "topspeed", "diagfall", "spindash", "objheavy"}


class _Script:
    progress = False

    def __init__(self, seq):
        self.seq = list(seq)

    def held(self, s):
        return self.seq.pop(0)


def test_press_is_edge_of_held():
    held = [R, R | C, R | C, R]
    assert ld.press_edges(held, prev=0) == [R, C, 0, 0]
    # ... and the press the DRIVE writes is that same edge (LegCore is the real path)
    c = ld.LegCore(_Script(held), t0=1, cap_ticks=4, debug=False, buttons=B)
    c.step(st(0), pstate=0)
    got = []
    for t in range(1, 5):
        c.step(st(t), pstate=0)
        got.append(c.last_press)
    assert got == [R, C, 0, 0] and [r["press"] for r in c.rows] == [R, C, 0, 0]


# ---- the decision core --------------------------------------------------------------------

def core(policy="run", t0=10, cap=1000, debug=False):
    return ld.LegCore(ld.POLICIES[policy](B, EQ), t0=t0, cap_ticks=cap, debug=debug, buttons=B)


def test_lag_counted_from_frame_counter_delta():
    """Rows with dFrame_Counter [1,2,1,3] over 4 ticks: 7 frames, 4 ticks, lag 3 — counted as
    sum(dFC) - sum(dTick) over the leg, never per row."""
    c = core(t0=1, cap=4)
    fc = 50
    c.step(st(0, fc=fc), pstate=0)            # pre-t0 baseline: no row, no input
    for t, d in zip(range(1, 5), [1, 2, 1, 3]):
        fc += d
        c.step(st(t, fc=fc, px=100 + 40 * t), pstate=0)
    assert [r["dfc"] for r in c.rows] == [1, 2, 1, 3]
    assert c.lag_frames == 3 and c.lag_ticks == 4
    assert c.status == "CAP"


def test_lag_frame_counter_wraps_at_16_bits():
    c = core(t0=1, cap=2)
    c.step(st(0, fc=0xFFFF), pstate=0)
    c.step(st(1, fc=0x0001), pstate=0)        # +2 across the wrap
    assert c.rows[0]["dfc"] == 2


def test_no_input_before_t0():
    c = core(t0=5, cap=10)
    for t in range(5):
        assert c.step(st(t), pstate=0) is None
    assert c.step(st(5), pstate=0) == R
    assert c.input_log() == {"t0": 5, "held": [R]}


def test_finished_at_camera_max():
    c = core(t0=0, cap=10_000)
    for t in range(100):
        c.step(st(t, px=100 + 10 * t, cx=min(5824, 60 * t), cx_max=5824), pstate=0)
        if c.status:
            break
    assert c.status == "FINISHED"
    assert c.rows[-1]["cx"] == 5824
    assert len(c.input_log()["held"]) == len(c.rows)


def test_finished_needs_a_live_camera_max():
    """Camera_X_Max == 0 (not set up yet) never reads FINISHED."""
    c = core(t0=0, cap=5)
    for t in range(5):
        c.step(st(t, px=100 + 40 * t, cx=0, cx_max=0), pstate=0)
    assert c.status == "CAP"


def test_stuck_ends_the_leg():
    c = core(t0=0, cap=10_000)
    for t in range(1000):
        c.step(st(t, px=1040 + (t % 30), cx=900 + t, xvel=0x300), pstate=0)
        if c.status:
            break
    assert c.status == "STUCK" and c.reason.startswith("progress")


def test_idle_is_never_stuck():
    c = core("idle", t0=0, cap=700)
    for t in range(700):
        c.step(st(t), pstate=0)
    assert c.status == "CAP" and len(c.rows) == 700


def test_debug_free_flight_not_left_refuses():
    """DEBUG: py frozen 8 ticks after t0 -> B pressed once; still frozen 8 ticks after the
    press -> FAILED, reason `free flight not left`."""
    c = core(t0=0, cap=1000, debug=True)
    held = []
    for t in range(40):
        held.append(c.step(st(t, py=300), pstate=0))
        if c.status:
            break
    assert held[:8] == [0] * 8
    assert held[8] == BB, "B pressed on the 8th frozen tick"
    assert held[9:17] == [0] * 8
    assert c.status == "FAILED" and c.reason == "free flight not left"


def test_debug_free_flight_left_then_policy_drives():
    c = core(t0=0, cap=1000, debug=True)
    held = [c.step(st(t, py=300 if t <= 8 else 300 + t), pstate=0) for t in range(18)]
    assert held[8] == BB and c.status is None
    assert held[16] == R, "the policy drives from the tick the exit is confirmed"


def test_release_shape_never_presses_b():
    c = core(t0=0, cap=1000, debug=False)
    held = [c.step(st(t, py=300, px=100 + 3 * t, xvel=0x300), pstate=0) for t in range(30)]
    assert all(h == R for h in held), "release shape: py frozen on ground is normal, no B"


def test_tick_gap_is_loud():
    """Ticks are the only index: a missed Input_Tick hit is a driver defect, never a row."""
    c = core(t0=0, cap=100)
    c.step(st(0), pstate=0)
    with pytest.raises(ld.DriveError, match="tick"):
        c.step(st(2), pstate=0)


# ---- coverage -----------------------------------------------------------------------------

def rows_of(**over):
    base = dict(t=0, fc=0, dfc=1, dlt=1, px=0, py=0, xvel=0, yvel=0, gs=0, air=0, cx=0, cy=0,
                cxm=5824, ps=0, held=0)
    base.update(over)
    return base


def test_coverage_rules():
    eq = EQ
    cov = ld.coverage("idle", "CAP", [rows_of()] * 600, eq)
    assert cov["met"] and cov["need"] == 600
    assert not ld.coverage("idle", "CAP", [rows_of()] * 599, eq)["met"]
    assert ld.coverage("run", "FINISHED", [], eq)["met"]
    assert not ld.coverage("run", "STUCK", [], eq)["met"]
    fast = [rows_of(gs=-TOP)] * 60
    assert ld.coverage("topspeed", "CAP", fast, eq)["met"]
    assert not ld.coverage("topspeed", "CAP", fast[:59], eq)["met"]
    fall = [rows_of(t=i, cx=i, cy=i, yvel=0x100) for i in range(31)]
    assert ld.coverage("diagfall", "CAP", fall, eq)["got"] == 30
    sd = [rows_of(ps=4), rows_of(ps=2)]
    assert ld.coverage("spindash", "FINISHED", sd, eq)["met"]
    assert not ld.coverage("spindash", "FINISHED", [rows_of(ps=4)], eq)["met"]
    assert not ld.coverage("spindash", "STUCK", sd, eq)["met"]


# ---- symbol / offset resolution -----------------------------------------------------------

def test_sst_offsets_parsed_from_source():
    o = ld.sst_offsets(AEON / "engine" / "objects" / "sst.emp")
    assert o["x_pos"] == 0x02 and o["y_pos"] == 0x06
    assert o["x_vel"] == 0x0A and o["y_vel"] == 0x0C
    assert o["status"] == 0x1E and o["sst_custom"] == 0x30


def test_player_overlay_offsets_parsed_from_source():
    o = ld.overlay_offsets(AEON / "games" / "sonic4" / "player" / "player_common.emp",
                           "PlayerV")
    assert o["ground_speed"] == 0 and o["player_state"] == 2


LST = """\
DIGEST-SHAPE target=sonic4 game=sonic4 debug=1 extra-entries=none
 Frame_Counter : FFFF8002 C |
 Logic_Tick : FFFF8004 C |
 Ctrl_1_Held : FFFF8028 C |
 Ctrl_1_Press : FFFF8029 C |
 Camera_X : FFFFA6E2 C |
 Camera_Y : FFFFA6E6 C |
 Camera_X_Max : FFFFADFA C |
 Camera_Target : FFFFADFE C |
 Lag_Frame_Count : FFFFF000 C |
 Input_Tick : 2674 C |
 $engine.replay$Input_Tick$live : 2680 C |
EQU BUTTON_A = $00000040
EQU BUTTON_B = $00000010
EQU BUTTON_C = $00000020
EQU BUTTON_DOWN = $00000002
EQU BUTTON_LEFT = $00000004
EQU BUTTON_RIGHT = $00000008
EQU BUTTON_UP = $00000001
EQU PHYS_TOP_SPEED = $00000600
EQU PHYS_ROLL_START_MIN = $00000100
EQU ST_IN_AIR = $00000003
EQU ST_ROLLING = $00000004
EQU PSTATE_SPINDASH = $00000004
EQU _pl_state = $00000032
EQU SST_x_pos = $00000002
"""


def test_resolve_syms_from_listing(tmp_path):
    p = tmp_path / "x.lst"
    p.write_text(LST)
    s = ld.resolve_syms(p, aeon=AEON)
    assert s.addr["Frame_Counter"] == 0xFF8002 and s.addr["Input_Tick"] == 0x2674
    assert s.addr["Lag_Frame_Count"] == 0xFFF000 and s.debug
    assert s.buttons == B
    assert s.equ["PHYS_TOP_SPEED"] == 0x600 and s.equ["PHYS_ROLL_START_MIN"] == 0x100
    assert s.off["ground_speed"] == 0x30 and s.off["player_state"] == 0x32


def test_resolve_syms_refuses_missing_symbol(tmp_path):
    p = tmp_path / "x.lst"
    p.write_text(LST.replace(" Input_Tick : 2674 C |\n", ""))
    with pytest.raises(ld.DriveError, match="Input_Tick"):
        ld.resolve_syms(p, aeon=AEON)


def test_resolve_syms_refuses_source_listing_offset_drift(tmp_path):
    p = tmp_path / "x.lst"
    p.write_text(LST.replace("EQU _pl_state = $00000032", "EQU _pl_state = $00000034"))
    with pytest.raises(ld.DriveError, match="player_state"):
        ld.resolve_syms(p, aeon=AEON)


# ---- leg_run: a failed drive is COULD NOT RUN ----------------------------------------------

@pytest.mark.parametrize("exc", ["drive", "bus", "conn"])
def test_failed_drive_is_could_not_run_and_writes_nothing(tmp_path, monkeypatch, capsys, exc):
    """Exit contract: 1 = written but not met, 2 = could not run. A drive that dies (driver
    refusal, a bus error reply, a dropped connection) is 2 with NO result file."""
    import leg_run
    import leg_provenance as lp
    lst = tmp_path / "x.lst"
    lst.write_text(LST)

    class Inst:
        handshake = {}
        socket_path = "/nonexistent"

        def reap(self):
            Inst.reaped = True

    errs = {"drive": ld.DriveError("no Input_Tick hit in 1204 frames"),
            "bus": leg_run.BusError(-32004, "bad address"),
            "conn": ConnectionResetError("bus connection closed")}

    async def boom(a, inst, syms, probe=None, obj=None):
        raise errs[exc]
    monkeypatch.setattr(lp, "spawn_pinned", lambda rom, l: Inst())
    monkeypatch.setattr(lp, "provenance", lambda *a: {"harness": {}})
    monkeypatch.setattr(lp, "sha256_file", lambda p: "0" * 64)
    monkeypatch.setattr(leg_run, "run_leg", boom)
    out = tmp_path / "out"
    rc = leg_run.main(["--rom", str(tmp_path / "x.bin"), "--lst", str(lst), "--leg", "run",
                       "--phase", "0", "--out", str(out)])
    assert rc == 2
    assert "COULD NOT RUN" in capsys.readouterr().err
    assert not out.exists() or not any(out.iterdir())
    assert Inst.reaped


# ---- emulator-backed (post-sigil lane) ----------------------------------------------------

@pytest.mark.needs_build("s4.bin", "s4.lst")
def test_real_drive_is_tick_keyed():
    """A short real leg on the pinned oracle: every row is exactly one Logic_Tick after the
    last (the breakpoint loop misses no tick), the input log is one byte per row, and the
    lag identity holds over the rows."""
    import leg_provenance as lp
    from suite_paths import add_client_path
    add_client_path()
    from aether import BusClient
    rom, lst = AEON / "s4.bin", AEON / "s4.lst"
    syms = ld.resolve_syms(lst, aeon=AEON)
    inst = lp.spawn_pinned(rom, lst)
    try:
        async def go():
            c = BusClient(socket_path=inst.socket_path, client_id="test-leg-drive",
                          client_name="test_leg_drive")
            await c.connect()
            try:
                await c.call("emulator/reset", {})
                pol = ld.POLICIES["run"](syms.buttons, syms.equ)
                return await ld.drive_leg(c, syms, pol, t0=300, cap_ticks=120)
            finally:
                await c.close()
        tr = asyncio.run(go())
    finally:
        inst.reap()
    assert tr.status == "CAP" and len(tr.rows) == 120
    assert [r["dlt"] for r in tr.rows] == [1] * 120
    assert [r["t"] for r in tr.rows] == list(range(300, 420))
    assert tr.input_log["t0"] == 300 and len(tr.input_log["held"]) == 120
    assert tr.lag_frames == sum(r["dfc"] for r in tr.rows) - 120
    assert any(r["px"] != tr.rows[0]["px"] for r in tr.rows), "holding right moved nothing"


# ---- drive_leg: other breakpoints on the same client (B3) ---------------------------------

class _Bus:
    """A fake bus for drive_leg's I/O loop: `run_frames` replays a pc script; an Input_Tick
    stop advances Logic_Tick and Frame_Counter; everything else in RAM reads as zero."""

    def __init__(self, syms, pcs):
        self.a, self.pcs = syms.addr, list(pcs)
        self.tick, self.fc = 0, 0
        self.bp_added = self.bp_cleared = 0

    async def call(self, method, params):
        if method == "emulator/breakpoint_add":
            self.bp_added += 1
            return {"breakpoint": "b0"}
        if method == "emulator/breakpoint_clear":
            self.bp_cleared += 1
            return {}
        if method == "emulator/run_frames":
            pc = self.pcs.pop(0)
            if pc == self.a["Input_Tick"]:
                self.tick += 1
                self.fc += 1
            return {"pc": hex(pc), "mclk": 0}
        if method == "emulator/read_memory":
            addr, n = int(params["addr"], 16), params["len"]
            val = {self.a["Logic_Tick"]: self.tick, self.a["Frame_Counter"]: self.fc}.get(addr, 0)
            return {"bytes": "0x" + val.to_bytes(n, "big").hex()}
        if method == "emulator/write_memory":
            return {}
        raise AssertionError(method)


def _fake_syms():
    addr = {n: 0xFF8000 + 0x10 * i for i, n in enumerate(ld.ADDR_SYMS)}
    addr["Input_Tick"] = 0x2674
    return ld.Syms(addr=addr, equ=EQ, off={}, buttons=B, debug=False)


def test_drive_routes_other_breaks_to_on_break():
    """A DMA-site stop on the shared client goes to `on_break` and is neither a tick nor a
    miss; a stop nobody claims is still a miss (never silently a tick)."""
    syms = _fake_syms()
    IT, SITE, OTHER = 0x2674, 0x202E, 0x5000
    bus = _Bus(syms, [IT, SITE, SITE, IT, OTHER, IT, SITE, IT])
    seen = []

    async def on_break(client, pc, reply):
        seen.append(pc)
        return pc == SITE

    tr = asyncio.run(ld.drive_leg(bus, syms, ld.Idle(B, EQ), t0=2, cap_ticks=3,
                                  on_break=on_break))
    assert [r["t"] for r in tr.rows] == [2, 3, 4]
    assert seen == [SITE, SITE, OTHER, SITE]
    assert tr.misses == 1 and tr.hits == 4 and tr.breaks == 3
    assert bus.bp_added == bus.bp_cleared == 1


# ---- objheavy (v2 C2: the STRESS_OBJECTS leg) ----------------------------------------------

OEQ = dict(EQ, NUM_DYNAMIC=0x28)


def _oh_rows(n=100, disp=30, live=32, t0=300, px0=256, cyc=None):
    return [rows_of(t=t0 + i, px=px0 + i, py=500, disp=disp, live=live, pend=0,
                    cyc=cyc(i) if cyc else None) for i in range(n)]


def _ref(rows, shift_from=None):
    """The canonical path for the same ticks; positions differ from tick `shift_from` on."""
    return {r["t"]: (r["px"] + (1 if shift_from is not None and r["t"] >= shift_from else 0),
                     r["py"]) for r in rows}


def test_objheavy_drives_the_run_policy():
    assert ld.POLICIES["objheavy"] is ld.POLICIES["run"]


def test_objheavy_dispatch_threshold_is_three_quarters_of_num_dynamic():
    assert ld.obj_dispatch_min(OEQ) == 30
    assert ld.obj_dispatch_min(dict(OEQ, NUM_DYNAMIC=0x20)) == 24


def test_objheavy_coverage_met():
    rows = _oh_rows(100)
    cov = ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows))
    assert cov["met"], cov
    assert cov["got"]["ticks_dispatched_ge_min"] == 100
    assert cov["got"]["first_divergence"] is None


def test_objheavy_coverage_needs_sixty_loaded_ticks():
    rows = _oh_rows(100, disp=29)
    for r in rows[:ld.OBJ_COVER_TICKS]:
        r["disp"] = 30
    assert ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows))["met"]
    rows[0]["disp"] = 29
    cov = ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows))
    assert not cov["met"] and cov["got"]["ticks_dispatched_ge_min"] == ld.OBJ_COVER_TICKS - 1


def test_objheavy_coverage_refuses_live_over_pool_and_not_finished():
    rows = _oh_rows(100)
    rows[5]["live"] = 41
    assert not ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows))["met"]
    rows = _oh_rows(100)
    assert not ld.coverage("objheavy", "STUCK", rows, OEQ, ref=_ref(rows))["met"]


def test_objheavy_path_witness_and_first_touch():
    rows = _oh_rows(100)
    cov = ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows, shift_from=396))
    assert cov["met"] and cov["got"]["path_pct"] == 96.0          # 4 of 100 ticks differ
    assert cov["got"]["first_divergence"] == 396
    cov = ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows, shift_from=394))
    assert not cov["met"] and cov["got"]["path_pct"] == 94.0


def test_objheavy_without_reference_or_fields_is_unmeasurable():
    rows = _oh_rows(100)
    cov = ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=None)
    assert not cov["met"] and "UNMEASURABLE" in cov["got"]["unmeasurable"]
    bad = _oh_rows(100)
    del bad[3]["disp"]
    cov = ld.coverage("objheavy", "FINISHED", bad, OEQ, ref=_ref(bad))
    assert not cov["met"] and "UNMEASURABLE" in cov["got"]["unmeasurable"]
    cov = ld.coverage("objheavy", "FINISHED", [], OEQ, ref={})
    assert not cov["met"] and "UNMEASURABLE" in cov["got"]["unmeasurable"]


def test_obj_cost_fit_recovers_a_linear_cost():
    rows = _oh_rows(50)
    for i, r in enumerate(rows):
        r["live"] = 10 + i % 25
        r["cyc"] = 20000 + 700 * r["live"]
    fit = ld.obj_cost_fit(rows, "live")
    assert fit["status"] == "MEASURED" and fit["slope"] == pytest.approx(700.0)
    assert fit["intercept"] == pytest.approx(20000.0) and fit["r2"] == pytest.approx(1.0)
    assert fit["n"] == 50


def test_obj_cost_fit_is_unmeasurable_without_spread_or_samples():
    rows = _oh_rows(50, cyc=lambda i: 1000)
    assert ld.obj_cost_fit(rows, "live")["status"] == "UNMEASURABLE"     # live constant
    rows = _oh_rows(50)                                                  # cyc None
    assert ld.obj_cost_fit(rows, "live")["status"] == "UNMEASURABLE"


class _FakeRam:
    """The read_memory method over a dict of RAM bytes; refuses len > READ_MAX like the server."""

    def __init__(self, mem):
        self.mem, self.calls = mem, []

    async def call(self, method, params):
        assert method == "emulator/read_memory"
        a, n = int(params["addr"], 16), params["len"]
        assert 1 <= n <= ld.READ_MAX, n
        self.calls.append((a, n))
        return {"bytes": bytes(self.mem.get(a + i, 0) for i in range(n)).hex(), "mclk": 777}


def test_read_obj_load_counts_dispatched_skips_zero_entries_and_bounds_reads():
    off = {"x_pos": 2, "y_pos": 6}
    syms = ld.Syms(addr={"Dynamic_Live": 0xFFB5E2, "Dynamic_Live_Count": 0xFFB632,
                         "Dynamic_Live_Pending_Count": 0xFFB646},
                   equ={"NUM_DYNAMIC": 40, "CULL_DISTANCE_X": 0x300, "CULL_DISTANCE_Y": 0x200},
                   off=off, buttons=B, debug=False)
    mem = {}

    def w16(a, v):
        mem[a], mem[a + 1] = v >> 8, v & 0xFF
    ssts = [(0x8000, 1000, 500), (0x8040, 5000, 500), (0x9F00, 1100, 600)]   # 2nd is culled
    entries = [s[0] for s in ssts] + [0]                                       # + a zero slot
    w16(0xFFB632, len(entries))
    w16(0xFFB646, 1)
    for i, e in enumerate(entries):
        w16(0xFFB5E2 + 2 * i, e)
    for p, x, y in ssts:
        w16(0xFF0000 | p + 2, x)
        w16(0xFF0000 | p + 6, y)
    c = _FakeRam(mem)
    got = asyncio.run(ld.read_obj_load(c, syms, cx=900, cy=400))
    assert got == {"live": 4, "pend": 1, "disp": 2, "zero": 1, "mclk": 777}
    assert all(n <= ld.READ_MAX for _a, n in c.calls)


# ---- fix round 1: the paired per-object cost, the unpaired label, the re-record note -------

def _paired_rows(n=60, slope=1100, route=lambda i: 40000 + (i * 7919) % 30000):
    """Stress and canonical rows on the same ticks and route: the canonical run carries the
    route's own work (`route`, wildly varying); the stress run adds `slope` per extra object."""
    canon, stress = [], []
    for i in range(n):
        t = 300 + i
        cl = i % 4
        sl = cl + 5 + (i * 13) % 30
        canon.append(dict(t=t, px=100 + i, py=50, live=cl, disp=cl, cyc=route(i)))
        stress.append(dict(t=t, px=100 + i, py=50, live=sl, disp=sl,
                           cyc=route(i) + slope * (sl - cl) + 250))
    return stress, canon


def test_obj_cost_paired_recovers_a_known_slope_despite_route_work():
    stress, canon = _paired_rows()
    un = ld.obj_cost_fit(stress, "live")
    assert un["r2"] < 0.9                          # the route work confounds the unpaired fit
    f = ld.obj_cost_paired(stress, canon, "live")
    assert f["status"] == "MEASURED" and f["label"] == "MEASURED (Oracle)"
    assert f["slope"] == pytest.approx(1100.0) and f["intercept"] == pytest.approx(250.0)
    assert f["r2"] == pytest.approx(1.0) and f["n"] == 60 and f["slope_stderr"] is not None
    assert "paired" in f["method"] and "same tick" in f["method"]


def test_obj_cost_paired_uses_only_ticks_on_the_same_route():
    stress, canon = _paired_rows()
    for r in stress[:10]:
        r["px"] += 1                               # off the canonical route: not paired
    f = ld.obj_cost_paired(stress, canon, "live")
    assert f["n"] == 50 and f["ticks_off_route"] == 10


def test_obj_cost_paired_without_shared_ticks_is_unmeasurable():
    stress, canon = _paired_rows()
    for r in canon:
        r["t"] += 10000
    assert ld.obj_cost_paired(stress, canon, "live")["status"] == "UNMEASURABLE"


def test_obj_cost_block_without_a_reference_says_unpaired_and_confounded():
    stress, _canon = _paired_rows()
    blk = ld.obj_cost_block(stress, None)
    assert blk["per_object"]["status"] == "DID NOT RUN"
    assert "UNPAIRED" in blk["unpaired"]["what"] and "confounded" in blk["unpaired"]["what"]
    assert "NOT the per-object cost" in blk["unpaired"]["what"]
    assert "cost per object" not in blk["unpaired"]["what"].lower().replace("not the per-object cost", "")


def test_obj_cost_block_with_a_reference_reports_the_paired_cost():
    stress, canon = _paired_rows()
    blk = ld.obj_cost_block(stress, {"rows": canon, "source": "x.json"})
    assert blk["per_object"]["live"]["slope"] == pytest.approx(1100.0)
    assert blk["per_object"]["ref"] == "x.json"
    assert "UNPAIRED" in blk["unpaired"]["what"]


def test_objheavy_path_shortfall_names_the_fixture_commit_and_the_recipe():
    rows = _oh_rows(100)
    cov = ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows, shift_from=310),
                      ref_source="aeon d60c5ee6 (s4.bin 193507d9)")
    assert not cov["met"]
    note = cov["got"]["note"]
    assert "d60c5ee6" in note and "V2-C2-STRESS-OBJECTS" in note and "re-record" in note
    ok = ld.coverage("objheavy", "FINISHED", rows, OEQ, ref=_ref(rows), ref_source="x")
    assert "note" not in ok["got"]
