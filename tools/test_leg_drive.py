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


def st(tick, px=100, py=200, xvel=0, yvel=0, gspeed=0, airborne=False, cx=0, cy=0,
       cx_max=5824, fc=None):
    return ld.TickState(tick=tick, frame_counter=tick if fc is None else fc, px=px, py=py,
                        xvel=xvel, yvel=yvel, gspeed=gspeed, airborne=airborne, cx=cx, cy=cy,
                        cx_max=cx_max)


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
    p = ld.POLICIES["run"](B, TOP)
    for t in range(100):
        h = p.held(st(t, xvel=0x300, gspeed=0x300))
        assert h == R, f"tick {t}: C at xvel=$300 (not blocked) -> {h:#x}"
    hs = [p.held(st(100 + k, xvel=0, gspeed=0)) for k in range(8)]
    assert hs[:7] == [R] * 7, hs
    assert hs[7] == R | C, "C must arrive on the 8th consecutive blocked tick"


def test_run_policy_never_jumps_on_a_period_or_in_the_air():
    p = ld.POLICIES["run"](B, TOP)
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
    p = ld.POLICIES["spindash"](B, TOP)
    got = [p.held(st(t, gspeed=0)) for t in range(30)]
    assert got == want
    # sequence over: release down, hold right (a fast roll does not re-trigger)
    assert p.held(st(30, gspeed=0x800)) == R


def test_spindash_triggers_only_below_half_top_speed_on_ground():
    p = ld.POLICIES["spindash"](B, TOP)
    assert p.held(st(0, gspeed=TOP // 2)) == R
    assert p.held(st(1, gspeed=0, airborne=True)) == R
    assert p.held(st(2, gspeed=TOP // 2 - 1)) == D


def test_topspeed_spindashes_after_30_slow_ground_ticks():
    p = ld.POLICIES["topspeed"](B, TOP)
    hs = [p.held(st(t, xvel=0x100, gspeed=0x100)) for t in range(30)]
    assert hs[:29] == [R] * 29
    assert hs[29] == D, "30th slow tick starts the spindash sequence"


def test_diagfall_holds_down_in_the_air():
    p = ld.POLICIES["diagfall"](B, TOP)
    assert p.held(st(0, gspeed=0x800, airborne=True)) == R | D
    assert p.held(st(1, gspeed=0x800)) == R


def test_idle_is_zero():
    p = ld.POLICIES["idle"](B, TOP)
    assert {p.held(st(t)) for t in range(50)} == {0}
    assert set(ld.POLICIES) == {"idle", "run", "topspeed", "diagfall", "spindash"}


def test_press_is_edge_of_held():
    held = [R, R | C, R | C, R]
    assert ld.press_edges(held, prev=0) == [R, C, 0, 0]


# ---- the decision core --------------------------------------------------------------------

def core(policy="run", t0=10, cap=1000, debug=False):
    return ld.LegCore(ld.POLICIES[policy](B, TOP), t0=t0, cap_ticks=cap, debug=debug, buttons=B)


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
    eq = {"PHYS_TOP_SPEED": TOP, "PSTATE_SPINDASH": 4}
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
EQU ST_IN_AIR = $00000003
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
    assert s.equ["PHYS_TOP_SPEED"] == 0x600
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
                pol = ld.POLICIES["run"](syms.buttons, syms.equ["PHYS_TOP_SPEED"])
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
