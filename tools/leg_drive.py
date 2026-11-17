#!/usr/bin/env python3
"""leg_drive — tick-keyed, closed-loop leg driver (Empyrean v2 step 0, B2).

WHY. The 2026-09-25 perf survey (`docs/research/2026-09-25-perf-survey/leg_probe.py`, frozen)
drove legs open-loop and keyed to FRAMES: it held buttons through `emulator/hold`, jumped on a
45-frame period, stepped `run_frames(1)` and called a leg stalled when the CAMERA stopped. Two
measured defects followed (Oracle fitness findings 2 and 3):

  * the periodic jump broke the x ~ 1046 loop and the leg bounced there until the frame cap,
    while the camera moved every frame — so "camera stalled" never fired and a stuck leg read
    as a run;
  * a lag frame is a frame with no tick, and a frame-keyed drive applied input on it and read
    lag per row.

This module replaces both:

  * ONE breakpoint at `Input_Tick` (engine/system/replay.emp, the replay seam: GameLoop calls it
    right after `addq.l #1, Logic_Tick` and after VInt has latched the pads). On each hit the
    driver reads the state, asks the policy for `held`, derives `press = held & ~prev`, writes
    `Ctrl_1_Held` / `Ctrl_1_Press` BY SYMBOL and continues. Ticks are the only index; a lag
    frame produces no hit, so no input is applied on it and the next row's dFrame_Counter is 2.
  * Policies are CLOSED-LOOP: `run` jumps only when blocked, never on a period.
  * Stuck is PROGRESS-based (max px), never camera-based.
  * Lag over a leg is sum(dFrame_Counter) - sum(dLogic_Tick), never per row.

Every address is resolved by symbol from the build's own listing, every threshold the coverage
rules use is a listing equate, and the SST / PlayerV offsets are parsed from the `.emp` source
(cross-checked against the listing's own `SST_*` / `_pl_state` equates when present).

`LegCore` is the pure decision core (unit-tested with synthetic TickState series); `drive_leg`
is the thin async I/O loop around it.
"""
from __future__ import annotations

import inspect
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
# The driver only ever runs on a client from `leg_provenance.spawn_pinned` (the pinned Rust
# oracle-aether); importing it here also makes this module's seam explicit to
# tools/test_legacy_seam_keys.py (which otherwise reads a library handed a client as
# "ambient", i.e. legacy-server vocabulary). The aeon root is the provenance module's.
import leg_provenance as lp  # noqa: E402

AEON_ROOT = lp.AEON_ROOT

#: Ticks added to T0 for the three phases of a leg (the phase spreads where in the 60 Hz
#: cadence the leg starts relative to whatever periodic work the engine has).
T0 = 300
PHASE_OFFSETS = (0, 7, 19)

# Closed-loop rule constants (task brief B2, "The drive"). These are DRIVER parameters, not
# engine thresholds, so they live here; every engine threshold comes from the listing.
BLOCK_XVEL = 0x80          # run: |xvel| below this on ground counts as blocked
BLOCK_TICKS = 8            # ... for this many consecutive ticks -> press C
JUMP_HOLD = 10             # ticks C is held for a blocked-jump (full height; leg_probe's 10)
SLOW_GSPEED = 0x200        # topspeed: |gspeed| below this on ground ...
SLOW_TICKS = 30            # ... for this many ticks -> spindash
SPIN_PRE = 4               # spindash: ticks of DOWN before the first tap
SPIN_TAPS = 4              # C taps
SPIN_ON, SPIN_OFF = 2, 4   # each tap: ticks on, ticks off
SPIN_POST = 2              # ticks of DOWN after the last tap before release
SPIN_LEN = SPIN_PRE + SPIN_TAPS * (SPIN_ON + SPIN_OFF) + SPIN_POST   # 30
DEBUG_FROZEN_TICKS = 8     # DEBUG: py unchanged this long -> B; still frozen as long -> FAILED
IDLE_NEED_TICKS = 600      # idle coverage
# objheavy (v2 C2, the STRESS_OBJECTS leg; C1 note §1.4). The dispatch threshold is derived
# from the listing's NUM_DYNAMIC (`obj_dispatch_min`), never typed.
OBJ_COVER_TICKS = 60       # ticks with >= obj_dispatch_min dispatched objects: one second at 60 Hz
OBJ_PATH_PCT = 95          # path witness: P1 (x, y) == the canonical run leg's on >= this % of ticks

STATUSES = ("FINISHED", "STUCK", "CAP", "FAILED")


class DriveError(RuntimeError):
    """The drive cannot answer (missing symbol, offset drift, a missed tick). Never a result."""


# ---- types --------------------------------------------------------------------------------

@dataclass(frozen=True)
class TickState:
    tick: int
    frame_counter: int
    px: int
    py: int
    xvel: int
    yvel: int
    gspeed: int
    airborne: bool
    cx: int
    cy: int
    cx_max: int
    #: ST_ROLLING (the engine's "in ball form" status bit, listing equate). Trailing with a
    #: default so the B2 interface fields and their order are unchanged (fix round 2).
    rolling: bool = False


@dataclass(frozen=True)
class Buttons:
    right: int
    left: int
    down: int
    up: int
    a: int
    b: int
    c: int


def buttons_from_equates(equ: dict) -> Buttons:
    try:
        return Buttons(**{k: equ["BUTTON_" + k.upper()] for k in
                          ("right", "left", "down", "up", "a", "b", "c")})
    except KeyError as e:
        raise DriveError(f"the listing publishes no `EQU {e.args[0]}`") from None


#: InputLog = {"t0": int, "held": list[int]} — one held byte per tick from t0 (E1's replay
#: format). A dict alias, not a class, so it round-trips through JSON unchanged.
InputLog = dict


class Policy(Protocol):
    def held(self, s: TickState) -> int: ...


def press_edges(held: list[int], prev: int = 0) -> list[int]:
    out = []
    for h in held:
        out.append(h & ~prev & 0xFF)
        prev = h
    return out


# ---- policies -----------------------------------------------------------------------------

class Idle:
    progress = False

    def __init__(self, b: Buttons, equ: dict):
        pass

    def held(self, s):
        return 0


class Run:
    """Hold right; press C only when on ground and |xvel| < BLOCK_XVEL for BLOCK_TICKS
    consecutive ticks (blocked). Never on a period."""
    progress = True

    def __init__(self, b: Buttons, equ: dict):
        self.b, self.blocked, self.jump_left = b, 0, 0

    def observe(self, s, standing_only: bool = False):
        """Count consecutive blocked ticks (not while a jump is being held). With
        `standing_only` (the moving family, fix round 2 ruling) a ROLLING tick is not blocked:
        a jump from a roll is a roll-jump with no air control, so it waits for the roll to end
        and the count restarts from standing."""
        if not self.jump_left:
            blocked = not s.airborne and abs(s.xvel) < BLOCK_XVEL
            if standing_only and s.rolling:
                blocked = False
            self.blocked = self.blocked + 1 if blocked else 0

    @property
    def jumping(self):
        return bool(self.jump_left) or self.blocked >= BLOCK_TICKS

    def jump(self):
        if self.jump_left:
            self.jump_left -= 1
        else:
            self.blocked, self.jump_left = 0, JUMP_HOLD - 1
        return self.b.right | self.b.c

    def held(self, s):
        self.observe(s)
        return self.jump() if self.jumping else self.b.right


class _SpinSeq:
    """The spindash sequence: release right, hold down, tap C 4 times (2 on, 4 off), release
    down, hold right. `step()` returns the held byte for the next tick of the sequence."""

    def __init__(self, b: Buttons):
        self.b, self.k = b, None

    @property
    def active(self):
        return self.k is not None

    def start(self):
        self.k = 0

    def step(self):
        """SPIN_LEN ticks of down (with the taps), then ONE forced release tick (right, no
        down). The release is part of the sequence, not a fall-through to the trigger: while
        charging the engine holds gspeed at 0, so a trigger re-checked on that tick restarted
        the sequence and down was never released (MEASURED, fix round 1: s4.bin spindash and
        diagfall p0 STUCK at px 256 with 0 releases)."""
        k, D, C = self.k, self.b.down, self.b.c
        if k == SPIN_LEN:
            self.k = None
            return self.b.right
        h = D
        if SPIN_PRE <= k < SPIN_PRE + SPIN_TAPS * (SPIN_ON + SPIN_OFF):
            h = D | C if (k - SPIN_PRE) % (SPIN_ON + SPIN_OFF) < SPIN_ON else D
        self.k = k + 1
        return h


def spindash_gate(equ: dict) -> int:
    """The engine's own spindash gate: PState_Ground (games/sonic4/player/player_ground.emp:
    271-279) spindashes only with down held, a fresh jump-buffer press and |gsp| <
    PHYS_ROLL_START_MIN; at or above it down starts a ROLL and C is a roll-jump. The plan's
    `PHYS_TOP_SPEED/2` ($300) and topspeed's `$200` sit above the gate (fix round 1 ruling:
    a brief defect, booked in docs/DEFERRED_WORK.md, V2-B2-SPINDASH-GATE)."""
    return equ["PHYS_ROLL_START_MIN"]


class _Moving:
    """The shared shape of every MOVING policy that can spindash (controller ruling, B2 round
    1): the run rule's blocked jump, a spindash sequence, and right otherwise.

    Order each tick: the blocked counter is updated, STANDING ticks only (fix round 2: a
    ROLLING tick -- ST_ROLLING set -- is not blocked, because a jump from a roll is a
    roll-jump with no air control; charging a spindash is PSTATE_SPINDASH, not ST_ROLLING,
    games/sonic4/player/player_ground.emp:595-598); a
    sequence in progress runs to its forced release, and no jump is pressed inside it; then a
    due blocked jump; then the policy's own dash trigger (always below the engine gate)."""
    progress = True

    def __init__(self, b: Buttons, equ: dict):
        self.b, self.gate = b, spindash_gate(equ)
        self.run, self.seq = Run(b, equ), _SpinSeq(b)

    def want_dash(self, s) -> bool:
        raise NotImplementedError

    def held(self, s):
        self.run.observe(s, standing_only=True)
        if self.seq.active:
            return self.seq.step()
        if self.run.jumping:
            return self.run.jump()
        if self.want_dash(s):
            self.seq.start()
            return self.seq.step()
        return self.b.right


class Spindash(_Moving):
    """When on ground and |gspeed| < PHYS_ROLL_START_MIN (the engine's spindash gate): the
    spindash sequence; plus the run rule's blocked jump; else hold right."""

    def want_dash(self, s):
        return not s.airborne and abs(s.gspeed) < self.gate


class TopSpeed(_Moving):
    """The run rule, plus a spindash once on ground and |gspeed| < SLOW_GSPEED for SLOW_TICKS
    -- fired only on a tick below the engine's spindash gate (PHYS_ROLL_START_MIN)."""

    def __init__(self, b: Buttons, equ: dict):
        super().__init__(b, equ)
        self.slow = 0

    def want_dash(self, s):
        self.slow = self.slow + 1 if (not s.airborne and abs(s.gspeed) < SLOW_GSPEED) else 0
        if self.slow >= SLOW_TICKS and abs(s.gspeed) < self.gate:
            self.slow = 0
            return True
        return False


class DiagFall(Spindash):
    """The spindash rule (with the blocked jump), plus hold down while airborne."""

    def held(self, s):
        h = super().held(s)
        if s.airborne and not self.seq.active:
            h |= self.b.down
        return h


class Replay:
    """OPEN-LOOP replay of a saved InputLog (E1, tools/v1_reference.py): the held byte for tick
    t is `held[t - t0]`, whatever the state says. `open_loop` tells LegCore to skip the DEBUG
    free-flight exit too -- the recorded log already contains the bytes that exit wrote, so a
    replay re-applies them verbatim instead of re-deciding them. A tick outside the log is a
    loud DriveError (the caller caps the drive at len(held), so it never asks)."""
    progress = False          # a replay ends at the end of its log, never on a stuck verdict
    open_loop = True

    def __init__(self, log: InputLog):
        if not isinstance(log, dict) or not isinstance(log.get("t0"), int) or not isinstance(
                log.get("held"), list):
            raise DriveError(f"not an InputLog {{t0: int, held: list[int]}}: {type(log)}")
        if any(not isinstance(h, int) or not 0 <= h <= 0xFF for h in log["held"]):
            raise DriveError("InputLog.held carries a value that is not a byte")
        self.t0, self.log = log["t0"], list(log["held"])

    def held(self, s):
        k = s.tick - self.t0
        if not 0 <= k < len(self.log):
            raise DriveError(f"replay asked for tick {s.tick}, outside the log "
                             f"[{self.t0}, {self.t0 + len(self.log)})")
        return self.log[k]


#: name -> factory(buttons, equ), `equ` being the listing's equates (`Syms.equ`). The brief's
#: interface was Callable[[Buttons], Policy]; the equates are passed because the spindash
#: family's gate (PHYS_ROLL_START_MIN) must come from the listing, not be typed here.
POLICIES: dict[str, Callable[[Buttons, dict], Policy]] = {
    "idle": Idle, "run": Run, "topspeed": TopSpeed, "diagfall": DiagFall, "spindash": Spindash,
    # The stress legs drive the run policy on their own shape's ROM; the leg NAME selects the
    # coverage rule (and, in leg_run, the per-tick instruments the rule reads).
    "objheavy": Run,
}


# ---- stuck detector -----------------------------------------------------------------------

class ProgressStuck:
    """Progress is the maximum px reached. STUCK when that maximum has not grown by
    `min_progress_px` within `window_ticks`. Camera motion is ignored on purpose: inside a loop
    it moves every tick (Oracle fitness finding 2)."""

    def __init__(self, window_ticks: int = 300, min_progress_px: int = 32):
        self.window, self.min = window_ticks, min_progress_px
        self.anchor_px = self.anchor_tick = None
        self.best = None

    def observe(self, s: TickState) -> bool:
        if self.anchor_px is None:
            self.anchor_px = self.best = s.px
            self.anchor_tick = s.tick
            return False
        self.best = max(self.best, s.px)
        if self.best - self.anchor_px >= self.min:
            self.anchor_px, self.anchor_tick = self.best, s.tick
        return s.tick - self.anchor_tick >= self.window


# ---- the pure decision core ---------------------------------------------------------------

class LegCore:
    """Feed it one TickState per Input_Tick hit; it returns the held byte to write (None before
    t0: no input is written) and sets `status` when the leg ends."""

    def __init__(self, policy, t0: int, cap_ticks: int, debug: bool, buttons: Buttons,
                 stuck: ProgressStuck | None = None):
        self.policy, self.t0, self.cap, self.debug, self.b = policy, t0, cap_ticks, debug, buttons
        self.stuck = stuck if stuck is not None else ProgressStuck()
        self.rows: list[dict] = []
        self.held_log: list[int] = []
        self.status: str | None = None
        self.reason = ""
        self.prev: TickState | None = None
        # An open-loop policy (Replay) owns every tick from t0, DEBUG free-flight exit included.
        open_loop = getattr(policy, "open_loop", False)
        self.policy_from: int | None = None if (debug and not open_loop) else t0
        self._dbg_py0 = self._dbg_py1 = None
        self.notes: list[str] = []

    # -- lag
    @property
    def lag_ticks(self):
        return sum(r["dlt"] for r in self.rows)

    @property
    def lag_frames(self):
        return sum(r["dfc"] for r in self.rows) - self.lag_ticks

    def input_log(self) -> InputLog:
        return {"t0": self.t0, "held": list(self.held_log)}

    def _debug_exit(self, s, k):
        """DEBUG shape: leave free flight. Returns held, or None once the policy owns input."""
        F = DEBUG_FROZEN_TICKS
        if k == 0:
            self._dbg_py0 = s.py
        if k < F:
            return 0
        if k == F:
            if s.py != self._dbg_py0:
                self.notes.append(f"DEBUG: py moved {self._dbg_py0}->{s.py} over {F} ticks; "
                                  "no free flight to leave")
                self.policy_from = s.tick
                return None
            self._dbg_py1 = s.py
            self.notes.append(f"DEBUG: py frozen at {s.py} for {F} ticks; B pressed at tick "
                              f"{s.tick}")
            return self.b.b
        if k < 2 * F:
            return 0
        if s.py == self._dbg_py1:
            self.status, self.reason = "FAILED", "free flight not left"
            return 0
        self.notes.append(f"DEBUG: free flight left (py {self._dbg_py1}->{s.py}); policy from "
                          f"tick {s.tick}")
        self.policy_from = s.tick
        return None

    def step(self, s: TickState, pstate: int, lag_count: int | None = None):
        if self.status:
            raise DriveError("step() after the leg ended")
        prev, self.prev = self.prev, s
        if prev is not None and s.tick != prev.tick + 1:
            raise DriveError(f"tick {prev.tick} -> {s.tick}: an Input_Tick hit was missed or "
                             "repeated (ticks are the only index)")
        if s.tick < self.t0:
            return None
        if prev is None:
            # No baseline hit (only a synthetic series starting AT t0 does this; drive_leg
            # always sees the boot ticks first). The row contributes 0 frames and 0 ticks.
            self.notes.append(f"no baseline hit before t0={self.t0}: first row counts 0/0")
        held = None
        if self.policy_from is None:
            held = self._debug_exit(s, s.tick - self.t0)
        if held is None:
            held = self.policy.held(s) & 0xFF
            if self.policy_from is None:
                self.policy_from = s.tick
        dfc = 0 if prev is None else (s.frame_counter - prev.frame_counter) & 0xFFFF
        dlt = 0 if prev is None else s.tick - prev.tick
        # The press written with this held byte: the edge against the previous ROW's held
        # (0 before the first row -- nothing was written before t0).
        press = press_edges([held], prev=self.held_log[-1] if self.held_log else 0)[0]
        self.last_press = press
        row = dict(t=s.tick, fc=s.frame_counter, dfc=dfc, dlt=dlt, px=s.px, py=s.py, xvel=s.xvel, yvel=s.yvel,
                   gs=s.gspeed, air=int(s.airborne), cx=s.cx, cy=s.cy, cxm=s.cx_max, ps=pstate,
                   roll=int(s.rolling), held=held, press=press)
        if lag_count is not None:
            row["lfc"] = lag_count
        self.rows.append(row)
        self.held_log.append(held)
        if self.status:                      # FAILED inside the debug exit
            return held
        if s.cx_max > 0 and s.cx >= s.cx_max:
            self.status, self.reason = "FINISHED", f"cx {s.cx} >= Camera_X_Max {s.cx_max}"
        elif (self.policy_from is not None and getattr(self.policy, "progress", True)
              and self.stuck.observe(s)):
            self.status = "STUCK"
            self.reason = (f"progress: max px {self.stuck.best} has not grown by "
                           f"{self.stuck.min} px in {self.stuck.window} ticks; at (px, py) = "
                           f"({s.px}, {s.py}), cam ({s.cx}, {s.cy})")
        elif len(self.rows) >= self.cap:
            self.status, self.reason = "CAP", f"{self.cap} ticks driven"
        return held


# ---- coverage -----------------------------------------------------------------------------

def spindash_releases(rows, pstate_spindash: int) -> int:
    return sum(1 for a, b in zip(rows, rows[1:])
               if a["ps"] == pstate_spindash and b["ps"] != pstate_spindash)


def coverage(leg: str, status: str, rows: list, equ: dict, ref: dict | None = None) -> dict:
    """{rule, got, need, met}. Thresholds the engine owns come from listing equates. `ref` is
    the objheavy leg's canonical path, {tick: (px, py)} (ignored by every other leg)."""
    if leg == "idle":
        got, need = len(rows), IDLE_NEED_TICKS
        return dict(rule=f"ticks driven >= {need}", got=got, need=need, met=got >= need)
    if leg == "run":
        return dict(rule="status == FINISHED", got=status, need="FINISHED",
                    met=status == "FINISHED")
    if leg == "topspeed":
        top = equ["PHYS_TOP_SPEED"]
        got = sum(1 for r in rows if abs(r["gs"]) >= top)
        return dict(rule=f"ticks with |gspeed| >= PHYS_TOP_SPEED (${top:X}) >= 60", got=got,
                    need=60, met=got >= 60)
    if leg == "diagfall":
        got = sum(1 for a, b in zip(rows, rows[1:])
                  if b["cx"] != a["cx"] and b["cy"] != a["cy"] and b["yvel"] > 0)
        return dict(rule="ticks with camera moving on both axes and yvel > 0 >= 30", got=got,
                    need=30, met=got >= 30)
    if leg == "spindash":
        n = spindash_releases(rows, equ["PSTATE_SPINDASH"])
        return dict(rule="status == FINISHED and spindash releases (PSTATE_SPINDASH exits) >= 1",
                    got={"status": status, "releases": n}, need={"status": "FINISHED",
                                                                 "releases": 1},
                    met=status == "FINISHED" and n >= 1)
    if leg == "objheavy":
        return _objheavy_coverage(status, rows, equ, ref)
    raise DriveError(f"no coverage rule for leg {leg!r} (sidekick/stream are Tasks 9-10)")


def obj_dispatch_min(equ: dict) -> int:
    """3/4 of the listing's NUM_DYNAMIC: the plan's load level, counted as DISPATCHED objects
    (inside RunObjects' CULL_DISTANCE_X/Y of the camera), not merely live (C1 note §1.4)."""
    return equ["NUM_DYNAMIC"] * 3 // 4


def first_divergence(rows: list, ref: dict):
    """The first tick whose P1 (px, py) differs from the reference (absent counts as
    different), or None."""
    for r in rows:
        if ref.get(r["t"]) != (r["px"], r["py"]):
            return r["t"]
    return None


def _objheavy_coverage(status, rows, equ, ref):
    nd = equ.get("NUM_DYNAMIC")
    rule = (f"status == FINISHED and >= {OBJ_COVER_TICKS} ticks with dispatched >= 3/4 NUM_DYNAMIC"
            f" and live <= NUM_DYNAMIC every tick and P1 (x, y) == canonical run leg on >= "
            f"{OBJ_PATH_PCT}% of ticks")
    need = {"status": "FINISHED", "ticks_dispatched_ge_min": OBJ_COVER_TICKS,
            "ticks_live_over_pool": 0, "path_pct": OBJ_PATH_PCT}
    why = []
    if nd is None:
        why.append("the listing publishes no EQU NUM_DYNAMIC")
    if not rows:
        why.append("no rows")
    lacking = [r.get("t") for r in rows if any(r.get(k) is None for k in ("live", "disp", "pend"))]
    if lacking:
        why.append(f"{len(lacking)} row(s) carry no live/disp/pend reading (first tick "
                   f"{lacking[0]})")
    if ref is None:
        why.append("no canonical run-leg path to compare P1 against (path fixture missing "
                   "this shape/phase)")
    elif not ref:
        why.append("the canonical run-leg path is empty")
    if why:
        return dict(rule=rule, need=need, met=False,
                    got={"status": status, "unmeasurable": "UNMEASURABLE: " + "; ".join(why)})
    dmin = obj_dispatch_min(equ)
    loaded = sum(1 for r in rows if r["disp"] >= dmin)
    over = sum(1 for r in rows if r["live"] > nd)
    same = sum(1 for r in rows if ref.get(r["t"]) == (r["px"], r["py"]))
    pct = round(100.0 * same / len(rows), 2)
    got = {"status": status, "dispatch_min": dmin, "ticks_dispatched_ge_min": loaded,
           "ticks_live_over_pool": over, "path_pct": pct,
           "first_divergence": first_divergence(rows, ref),
           "live_max": max(r["live"] for r in rows), "disp_max": max(r["disp"] for r in rows),
           "ticks_pending": sum(1 for r in rows if r["pend"] > 0),
           "ref_ticks_missing": sum(1 for r in rows if r["t"] not in ref)}
    met = (status == "FINISHED" and loaded >= OBJ_COVER_TICKS and over == 0
           and pct >= OBJ_PATH_PCT)
    return dict(rule=rule, got=got, need=need, met=met)


def obj_cost_fit(rows: list, x_key: str = "live") -> dict:
    """Least-squares fit of main-loop CPU cycles per tick (`cyc`) against `x_key` (live or
    dispatched object count): slope = the cost per object. UNMEASURABLE (never 0) with fewer
    than 3 samples or no spread in x."""
    pts = [(r[x_key], r["cyc"]) for r in rows
           if r.get(x_key) is not None and r.get("cyc") is not None]
    n = len(pts)
    if n < 3:
        return {"status": "UNMEASURABLE", "reason": f"{n} tick(s) with a cycle reading", "n": n}
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx == 0:
        return {"status": "UNMEASURABLE", "reason": f"{x_key} is {pts[0][0]} on every tick",
                "n": n}
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    syy = sum((y - my) ** 2 for _, y in pts)
    slope = sxy / sxx
    intercept = my - slope * mx
    r2 = 1.0 if syy == 0 else (sxy * sxy) / (sxx * syy)
    resid = [y - (intercept + slope * x) for x, y in pts]
    se = math.sqrt(sum(e * e for e in resid) / (n - 2) / sxx) if n > 2 else None
    return {"status": "MEASURED", "x": x_key, "n": n, "slope": slope, "intercept": intercept,
            "r2": r2, "slope_stderr": se, "x_min": min(x for x, _ in pts),
            "x_max": max(x for x, _ in pts)}


# ---- symbol / offset resolution -----------------------------------------------------------

_FIELD = re.compile(r"^\s*(\w+)\s*:\s*[^@,]+?@\s*\$([0-9A-Fa-f]+)\s*,")
_VAR = re.compile(r"^\s*(\w+)\s*:\s*(\[\s*\w+\s*;\s*\d+\s*\]|\w+)\s*,")
_SIZES = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}


def _block(path: Path, header: re.Pattern) -> list[str]:
    lines = Path(path).read_text().splitlines()
    for i, ln in enumerate(lines):
        if header.match(ln):
            out = []
            for body in lines[i + 1:]:
                if body.strip().startswith("}"):
                    return out
                out.append(body)
    raise DriveError(f"{path}: block {header.pattern!r} not found")


def sst_offsets(path: Path) -> dict:
    """Every `name: Type @ $NN` field of `pub struct Sst` (the file's own pinned offsets)."""
    out = {}
    for ln in _block(path, re.compile(r"^\s*pub\s+struct\s+Sst\b")):
        m = _FIELD.match(ln)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    if not out:
        raise DriveError(f"{path}: no `name: Type @ $NN` fields parsed from struct Sst")
    return out


def overlay_offsets(path: Path, name: str) -> dict:
    """Field offsets within a `pub vars <name>: Sst.sst_custom { ... }` overlay, by summing the
    declared widths in order. Stops at the first type it cannot size (fields after it are
    absent, never guessed)."""
    out, off = {}, 0
    for ln in _block(path, re.compile(r"^\s*pub\s+vars\s+" + re.escape(name) + r"\s*:")):
        m = _VAR.match(ln)
        if not m:
            continue
        ty = m.group(2)
        arr = re.match(r"\[\s*(\w+)\s*;\s*(\d+)\s*\]", ty)
        size = (_SIZES.get(arr.group(1), 0) * int(arr.group(2))) if arr else _SIZES.get(ty, 0)
        if not size:
            break
        out[m.group(1)] = off
        off += size
    return out


_SYM = re.compile(r"^\s*([A-Za-z_][\w$.]*)\s*:\s*([0-9A-Fa-f]+)\s+C\s*\|")
_EQU = re.compile(r"^EQU\s+([A-Za-z_]\w*)\s*=\s*\$([0-9A-Fa-f]+)\s*$")
_SHAPE = re.compile(r"^DIGEST-SHAPE\b.*\bdebug=(\d)")

ADDR_SYMS = ("Frame_Counter", "Logic_Tick", "Ctrl_1_Held", "Ctrl_1_Press", "Camera_X",
             "Camera_Y", "Camera_X_Max", "Camera_Target", "Input_Tick")
EQU_NEEDED = ("PHYS_TOP_SPEED", "PHYS_ROLL_START_MIN", "ST_IN_AIR", "ST_ROLLING",
              "PSTATE_SPINDASH")
SST_FIELDS = ("x_pos", "y_pos", "x_vel", "y_vel", "status", "sst_custom")


@dataclass
class Syms:
    addr: dict
    equ: dict
    off: dict
    buttons: Buttons
    debug: bool
    lst: str = ""


def parse_listing(lst: Path):
    addr, equ, debug = {}, {}, None
    for ln in Path(lst).read_text(errors="replace").splitlines():
        m = _EQU.match(ln.strip())
        if m:
            equ[m.group(1)] = int(m.group(2), 16)
            continue
        m = _SYM.match(ln)
        if m:
            addr.setdefault(m.group(1), int(m.group(2), 16) & 0xFFFFFF)
            continue
        m = _SHAPE.match(ln)
        if m:
            debug = m.group(1) == "1"
    return addr, equ, debug


def resolve_syms(lst: Path, aeon: Path = AEON_ROOT) -> Syms:
    addr, equ, debug = parse_listing(lst)
    if debug is None:
        raise DriveError(f"{lst}: no DIGEST-SHAPE line; cannot tell the DEBUG shape")
    miss = [n for n in ADDR_SYMS if n not in addr] + [n for n in EQU_NEEDED if n not in equ]
    if miss:
        raise DriveError(f"{lst}: missing symbol/equate(s) {miss}")
    if debug and "Lag_Frame_Count" not in addr:
        raise DriveError(f"{lst}: DEBUG shape without Lag_Frame_Count (the second lag witness)")
    sst = sst_offsets(aeon / "engine" / "objects" / "sst.emp")
    pv = overlay_offsets(aeon / "games" / "sonic4" / "player" / "player_common.emp", "PlayerV")
    off = {k: sst[k] for k in SST_FIELDS if k in sst}
    for k in ("ground_speed", "player_state"):
        if k not in pv:
            raise DriveError(f"PlayerV.{k} not parsed from player_common.emp")
        off[k] = sst["sst_custom"] + pv[k]
    if len(off) != len(SST_FIELDS) + 2:
        raise DriveError(f"sst.emp: fields missing {set(SST_FIELDS) - set(off)}")
    # Cross-check the source parse against the listing's own harvested offsets, when published.
    checks = {f"SST_{k}": off[k] for k in SST_FIELDS if k != "sst_custom"}
    checks["_pl_state"] = off["player_state"]
    for name, want in checks.items():
        if name in equ and equ[name] != want:
            fld = "player_state" if name == "_pl_state" else name[4:]
            raise DriveError(f"{fld}: source offset ${want:X} != listing `{name}` ${equ[name]:X}")
    return Syms(addr=addr, equ=equ, off=off, buttons=buttons_from_equates(equ), debug=debug,
                lst=str(lst))


# ---- the async I/O loop -------------------------------------------------------------------

@dataclass
class LegTrace:
    rows: list
    input_log: InputLog
    status: str
    lag_frames: int
    lag_ticks: int = 0
    reason: str = ""
    notes: list = field(default_factory=list)
    lag_frame_count_delta: int | None = None
    policy_from: int | None = None
    hits: int = 0
    misses: int = 0
    breaks: int = 0


def _unhex(s: str) -> str:
    return s[2:] if s[:2].lower() == "0x" else (s[1:] if s[:1] == "$" else s)


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


async def _rd(c, addr: int, n: int) -> bytes:
    r = await c.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    return bytes.fromhex(_unhex(r["bytes"])[:n * 2])


def _be(b: bytes, o: int, n: int) -> int:
    return int.from_bytes(b[o:o + n], "big")


async def read_tick_state(c, syms: Syms) -> tuple[TickState, int, int | None]:
    a, o = syms.addr, syms.off
    fl = await _rd(c, a["Frame_Counter"], 2)
    lt = await _rd(c, a["Logic_Tick"], 4)
    cam = await _rd(c, a["Camera_X"], 2)
    camy = await _rd(c, a["Camera_Y"], 2)
    cxm = await _rd(c, a["Camera_X_Max"], 2)
    tgt = _be(await _rd(c, a["Camera_Target"], 2), 0, 2)
    leader = (0xFF0000 | tgt) if tgt & 0x8000 else tgt
    if leader:
        span = max(o["player_state"] + 1, o["status"] + 1, o["ground_speed"] + 2)
        p = await _rd(c, leader, span)
        px, py = _be(p, o["x_pos"], 2), _be(p, o["y_pos"], 2)
        xv, yv = _s16(_be(p, o["x_vel"], 2)), _s16(_be(p, o["y_vel"], 2))
        gs = _s16(_be(p, o["ground_speed"], 2))
        air = bool(p[o["status"]] >> syms.equ["ST_IN_AIR"] & 1)
        rolling = bool(p[o["status"]] >> syms.equ["ST_ROLLING"] & 1)
        ps = p[o["player_state"]]
    else:
        px = py = xv = yv = gs = 0
        air, ps, rolling = False, -1, False
    lag = _be(await _rd(c, a["Lag_Frame_Count"], 4), 0, 4) if syms.debug else None
    s = TickState(tick=_be(lt, 0, 4), frame_counter=_be(fl, 0, 2), px=px, py=py, xvel=xv,
                  yvel=yv, gspeed=gs, airborne=air, rolling=rolling, cx=_be(cam, 0, 2), cy=_be(camy, 0, 2),
                  cx_max=_be(cxm, 0, 2))
    return s, ps, lag


#: objheavy's per-tick instruments (leg_run): the live list, its pending tail, and the
#: main loop's wait (the end of a tick's work). Resolved from the listing, never typed.
OBJ_ADDR_SYMS = ("Dynamic_Live", "Dynamic_Live_Count", "Dynamic_Live_Pending_Count",
                 "VSync_Wait")
OBJ_EQU_NEEDED = ("NUM_DYNAMIC", "CULL_DISTANCE_X", "CULL_DISTANCE_Y")
MCLK_PER_CPU_CYCLE = 7     # the 68000 runs at MCLK / 7 (NTSC 53.693175 MHz / 7)
READ_MAX = 4096            # emulator/read_memory's `len` bound (the server refuses more)


def obj_syms_missing(syms: Syms) -> list:
    return ([n for n in OBJ_ADDR_SYMS if n not in syms.addr]
            + [f"EQU {n}" for n in OBJ_EQU_NEEDED if n not in syms.equ])


async def read_obj_load(c, syms: Syms, cx: int, cy: int) -> dict:
    """Live / pending / dispatched dynamic objects this tick, read by symbol, plus the
    machine's mclk stamp at the read (the machine is paused at the Input_Tick hit).
    `disp` counts Dynamic_Live[] SSTs within CULL_DISTANCE_X/Y of the camera: the objects
    RunObjects will dispatch (C1 note §1.4; needs no emulator/object_list)."""
    a, e, o = syms.addr, syms.equ, syms.off
    live = _be(await _rd(c, a["Dynamic_Live_Count"], 2), 0, 2)
    pend = _be(await _rd(c, a["Dynamic_Live_Pending_Count"], 2), 0, 2)
    n = min(live, e["NUM_DYNAMIC"])
    r = await c.call("emulator/read_memory", {"addr": hex(a["Dynamic_Live"] & 0xFFFFFF),
                                              "len": max(2, 2 * n)})
    mclk = int(r["mclk"])
    raw = bytes.fromhex(_unhex(r["bytes"])[:4 * n])
    words = [_be(raw, 2 * i, 2) for i in range(n)]
    # A zero entry is a slot DeleteObject cleared and the next compaction drops
    # (engine/objects/core.emp, Dynamic_Live compaction): counted in `live`, never dispatched.
    ptrs = sorted(0xFF0000 | w for w in words if w)
    span = max(o["x_pos"], o["y_pos"]) + 2
    disp = 0
    k = 0
    while k < len(ptrs):                       # one read per run of SSTs within READ_MAX
        j = k
        while j + 1 < len(ptrs) and ptrs[j + 1] + span - ptrs[k] <= READ_MAX:
            j += 1
        lo = ptrs[k]
        blk = await _rd(c, lo, ptrs[j] + span - lo)
        for p in ptrs[k:j + 1]:
            x = _be(blk, p - lo + o["x_pos"], 2)
            y = _be(blk, p - lo + o["y_pos"], 2)
            if abs(x - cx) <= e["CULL_DISTANCE_X"] and abs(y - cy) <= e["CULL_DISTANCE_Y"]:
                disp += 1
        k = j + 1
    return {"live": live, "pend": pend, "disp": disp, "zero": len(words) - len(ptrs),
            "mclk": mclk}


async def _write_pad(c, syms: Syms, held: int, press: int):
    a = syms.addr
    if a["Ctrl_1_Press"] == a["Ctrl_1_Held"] + 1:
        await c.call("emulator/write_memory", {"addr": hex(a["Ctrl_1_Held"]),
                                               "bytes": f"0x{held:02x}{press:02x}"})
    else:
        await c.call("emulator/write_memory", {"addr": hex(a["Ctrl_1_Held"]),
                                               "bytes": f"0x{held:02x}"})
        await c.call("emulator/write_memory", {"addr": hex(a["Ctrl_1_Press"]),
                                               "bytes": f"0x{press:02x}"})


MAX_MISS_FRAMES = 1200     # run_frames chunks without an Input_Tick hit before giving up
RUN_CHUNK = 4              # frames per run_frames; a breakpoint halts it early


async def drive_leg(client, syms: Syms, policy, t0: int, cap_ticks: int, on_tick=None,
                    stuck: ProgressStuck | None = None, on_break=None) -> LegTrace:
    """Drive one leg from the machine's current state. `on_tick(state, row)` (sync or async) is
    called on every row (tick >= t0), after the input is written.

    `on_break(client, pc, reply) -> bool` (async) is offered every stop that is NOT
    Input_Tick: other instruments (B3's DMA probe) share this client and its breakpoints. A
    stop it claims (True) is neither a tick nor a miss (`LegTrace.breaks`); one nobody claims
    is a miss, exactly as before."""
    core = LegCore(policy, t0=t0, cap_ticks=cap_ticks, debug=syms.debug, buttons=syms.buttons,
                   stuck=stuck)
    it = syms.addr["Input_Tick"]
    bp = (await client.call("emulator/breakpoint_add", {"symbol": "Input_Tick"}))["breakpoint"]
    hits = misses = breaks = 0
    lag0 = None
    try:
        while core.status is None:
            missed = 0
            while True:
                r = await client.call("emulator/run_frames", {"frames": RUN_CHUNK})
                pc = int(_unhex(r["pc"]), 16) & 0xFFFFFF
                if pc == it:
                    break
                if on_break is not None and await on_break(client, pc, r):
                    breaks += 1
                    continue
                missed += 1
                misses += 1
                if missed * RUN_CHUNK > MAX_MISS_FRAMES:
                    raise DriveError(f"no Input_Tick hit in {missed * RUN_CHUNK} frames "
                                     f"(pc {r['pc']}); the game loop is not running")
            hits += 1
            s, ps, lag = await read_tick_state(client, syms)
            if s.tick == t0 - 1:
                lag0 = lag              # the window's baseline: the same hit the first dFC uses
            held = core.step(s, ps, lag)
            if held is None:
                continue
            await _write_pad(client, syms, held, core.last_press)
            if on_tick is not None:
                res = on_tick(s, core.rows[-1])
                if inspect.isawaitable(res):
                    await res
    finally:
        await client.call("emulator/breakpoint_clear", {"breakpoint": bp})
    lfc = None
    if syms.debug and core.rows and lag0 is not None:
        lfc = core.rows[-1]["lfc"] - lag0
    return LegTrace(rows=core.rows, input_log=core.input_log(), status=core.status,
                    lag_frames=core.lag_frames, lag_ticks=core.lag_ticks, reason=core.reason,
                    notes=core.notes, lag_frame_count_delta=lfc, policy_from=core.policy_from,
                    hits=hits, misses=misses, breaks=breaks)

