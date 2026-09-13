#!/usr/bin/env python3
"""glide_ceiling_witness — Knuckles' glide family against ceilings and floors (CHAR-4, CHAR-6)

THE CLAIMS UNDER TEST (`docs/lens-findings.jsonl` CHAR-4 and CHAR-6).

CHAR-4. The glide family had no ceiling probe, so a glide carried Knuckles' head into the
underside of the OJZ act 1 box's 16 px slab and left it there: the controller measured 7
frames at 4 px deep, every frame's y change equal to y_vel exactly
(docs/superpowers/notes/2026-09-13-char46-repro-recipe.md §10). The fix runs the air
states' own ceiling machinery (`Air_CeilingBump` -> `Player_SensorCeiling`) inside
`Glide_Collide` whenever the motion is NOT mostly down — `Air_Collide`'s classifier, S3K's
`Knux_DoLevelCollision_CheckRet` classes.

CHAR-6. Leaving the 21-high ability box for PSTATE_GLIDEFALL used to run
PHook_EnsureStanding's feet-planted lift: y_pos -= 9 px, so the head rose 18 px with no
clearance check. The fix gives GLIDEFALL its own enter hook, PHook_GlideFallEnter, which
restores the standing box about a FIXED CENTRE, as S3K does at all four of its mid-air
restore sites (skdisasm sonic3k.asm :30730, :30893, :31031, :31461 write the radii and
never y_pos). The head now rises Δr and the feet drop Δr, where

    Δr = (standing height >> 1) - (ability height >> 1)       (19 - 10 = 9 for Knuckles)

with both heights READ from the running player, never typed in. The feet can therefore
end the release frame up to Δr px inside a floor, which S3K accepts too; the next
GLIDEFALL update's floor probe (Glide_Collide's centre sensor) snaps them out and the
fall dead-stops into PSTATE_GROUND.

THE ASSERTIONS, DERIVED FROM WHAT EACH FIX GUARANTEES rather than from a remembered count.

  A (CHAR-4). Inside `Glide_Collide` the ceiling probe runs after the move and before the
    frame's state decision, and an embedded head (dist < 0) is moved down by exactly
    -dist, which is dist 0 at the new position. Nothing later in a frame that STAYS in
    PSTATE_GLIDE moves y up. So every frame that starts AND ends in PSTATE_GLIDE, in a
    motion class that is not mostly down, ends with the head's ceiling distance >= 0.
  B (CHAR-6, the head). The release update's only y writers are the glide's own move
    (Glide_Move sets y_vel before ObjectMove) and, before the fix, the lift. So the
    release update must change y_pos by EXACTLY y_vel * 256, and the box must become the
    standing box. The head then sits Δr above where the glide head was, so a release
    whose glide head had >= Δr of clearance ends clear, and the fall only moves away:
    no frame from the release on ends with the head embedded.
  C (CHAR-6, the feet). A release whose glide feet were FEET_GAP_C (< Δr) px above a
    floor must again move y_pos by exactly y_vel * 256, leave the standing feet at
    FEET_GAP_C - Δr (< 0: the one frame S3K accepts), and the very next update must land
    (PSTATE_GROUND, the dead stop's zero velocities) with the feet at floor distance
    exactly 0, having moved by exactly the model's floor distance.

Frames that change state are excluded from leg A on purpose; legs B and C grade exactly
those frames.

THE TERRAIN DISTANCES ARE THE ENGINE'S OWN CRITERIA, re-derived here and not typed in:
`Player_SensorCeiling`'s pair at (x_int -/+ (width >> 1), y_int - (height >> 1)), and
`Glide_Collide`'s single centre floor sensor at (x_int, y_int + (height >> 1)), each run
through a Python mirror of `probe_core` (player_sensors.emp): the Up stamp negates heights
and flips the sub-coordinate, the Down stamp does neither; one cell forward on empty, one
cell back on full, the hanging-run rule. Cells are baked with
`collision_pipeline.bake_plane_cell` from the SAME editor collision the build bakes (section
0 plane A/B, the S&K base bank), on the layer the player is actually on. For the ceiling
the closer sensor wins. dist < 0 is embedded. The slab's last solid row (511) and the leg-C
floor's top row are OUTPUTS of this file — printed, never assumed. build.sh's
level-staleness gate is what binds the editor tree to the ROM.

CONTROLS ON THE MODEL, because a mis-modelled probe would read as a result:
  * every frame the ENGINE ejected from a ceiling (dy != y_vel * 256 on a frame that stays
    in its state) must read exactly 0 in the model afterwards;
  * leg C's landing is the floor twin: the engine's correction must equal the model's
    floor distance at the post-move position, and read 0 in the model afterwards;
  * each leg has a SUBJECT requirement. A: at least one frame where the MOVE carried the
    head into the ceiling. B: the lifted alternative (the release position minus Δr)
    must be embedded in the model while the unlifted one is clear, so the leg can tell
    the two designs apart. C: the standing feet must be inside the floor at the release.
    A run without its subject is UNMEASURABLE, never a pass.

SAMPLING IS PER PLAYER UPDATE, NOT PER VIDEO FRAME, and the first version of this file got
that wrong. It stepped with `run_frames(1)` and read RAM at the VBlank boundary. The level
logic sometimes overruns a VBlank (a lag frame), so a boundary can fall INSIDE a player
update. Measured on the CHAR-4 fix: leg B's first GLIDEFALL update read the class gate at
frame 147 and the ceiling probe (-6, then ejected) at frame 148, and the frame-147 sample,
taken after gravity and before the eject, reported a head that was never left embedded. The
same straddle shows up the other way as a boundary with no update in it at all. So
`Drive.step` stops at each Player_1 entry into Player_Main, where the previous update is
complete, and a stall under that stepping is UNMEASURABLE.

LEGS (each boots fresh, each selects Knuckles the same way):
  A  CHAR-4 (a). The note's §7 recipe: glide right in open air, and when the integer x
     first reaches INJECT_X write y_pos = 514.0; hold A; step one update at a time to
     STOP_X. RED on 96a98abd (the head sits in the slab), GREEN on the CHAR-4 fix.
  B  CHAR-6, the head. Pass under the slab at y 532 and release A once x reaches
     RELEASE_X. RED before the CHAR-6 fix (the release lifts 9 px and ends the head 7 px
     inside the slab), GREEN on it.
  C  CHAR-6, the feet. Boot over the open floor right of the boxes, glide to
     RELEASE_X_C, place the glide feet FEET_GAP_C px above the floor and release. RED
     before the CHAR-6 fix (the lift), GREEN on it.

HOW KNUCKLES IS SELECTED, and why this way (the note's §2, option B). Boot clears all of
Work RAM, so the only window that can write `Character_ID` is after the clear and before
`Player_Init`: `run_to GameState_OJZScroll_Init`. The same stop writes the DEBUG
boot-override mailbox (Boot_At_X, Boot_At_Y, then Boot_At_Flag LAST), so the level starts
where the drive needs it with no warp and nothing to re-seed. The player boots in
debug-fly (the DEBUG shape arms CHEAT_DEBUG_FLY); a real B press leaves it.

WHERE THE NUMBERS COME FROM. Every RAM address and SST offset is read from the listing
this run is handed. The two PlayerV offsets (player_state, debug_flag) are overlay struct
fields with no EQU line, so they are DECODED from the built ROM's own bytes: the
`move.b d16(a0),d1` at Player_SetState+6 and the `sf d16(a0)` at Player_DebugExit+0. An
opcode that does not match is UNMEASURABLE, never a guess. The drive coordinates below
are coordinates into CONTENT, the class of number that moves when the level is edited;
the model controls and the subject requirements are what turn moved terrain into a loud
UNMEASURABLE instead of a quiet pass.

RUNNER: none. This repo runs player-physics runtime witnesses BY HAND; the only runtime
witness any runner executes is `preset_lab_witness.py`, in the effects nightly. Wiring
this one somewhere is booked (docs/DEFERRED_WORK.md, "CHAR-4 LEFT TWO THINGS OPEN").

    python3 tools/glide_ceiling_witness.py --rom s4.debug.bin --lst s4.debug.lst [-v]

Exit 0 every asserted leg held · 1 one did NOT hold · 2 UNMEASURABLE · 3 BLOCKED.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, run_to_addr  # noqa: E402
from cart_identity import CartMismatch  # noqa: E402
import collision_pipeline as cp  # noqa: E402

EDITOR = AEON / "games/sonic4/data/editor/ojz/act1"
BASE_BANK = AEON / "games/sonic4/data/collision/base"

NEED_SYMS = ("Player_1", "Character_ID", "Boot_At_X", "Boot_At_Y", "Boot_At_Flag",
             "GameState_OJZScroll_Init", "Player_SetState", "Player_DebugExit", "Player_Main")
NEED_EQUS = ("SST_x_pos", "SST_y_pos", "SST_x_vel", "SST_y_vel", "SST_width_pixels",
             "SST_height_pixels", "SST_status", "SST_layer", "CHAR_KNUCKLES",
             "PSTATE_AIR", "PSTATE_GLIDE", "PSTATE_GLIDEFALL", "PSTATE_GROUND",
             "SOLID_LRB", "SOLID_TOP")

# Drive coordinates (world px). Content coordinates — see the docstring.
BOOT_X, BOOT_Y = 760, 470   # legs A, B: open air left of the box: nothing solid within reach
INJECT_X = 850              # legs A, B: first integer x at which y_pos is written
INJECT_Y_A = 514            # leg A: the note's §7 recipe (inside its 512..520 band)
UNDER_Y_B = 532             # leg B: under the slab, glide head clear by the model
RELEASE_X = 925             # leg B: both standing head sensors under the flat underside
STOP_X = 960                # leg A: stop recording once past the embed run
BOOT_C_X, BOOT_C_Y = 1200, 470  # leg C: open air right of the second box, over the y 576 floor
RELEASE_X_C = 1300          # leg C: the release column, over the flat top-only floor
FEET_GAP_C = 4              # leg C: glide feet this far above the floor at the release
FLOOR_SEEK_Y = 560          # leg C: a row above the floor to measure its top from. probe_core
                            #   reaches the primary cell and ONE cell forward, so the row must
                            #   sit in the cell directly above the floor's (540 read "nothing")
MAX_FRAMES = 240

# One section is 2048 px square (Section = (x >> 11, y >> 11)); the drive stays in section
# 0, and the model refuses a coordinate outside it rather than reading air there.
SECTION_PX = 1 << 11
EDITOR_W = 256              # editor words per row (8 px tiles), rows sampled every 16 px


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


class Blocked(RuntimeError):
    """A precondition stopped the run before it started."""


def parse_lst(path):
    sym_re = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
    equ_re = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")
    syms, equs = {}, {}
    for line in Path(path).read_text(errors="replace").splitlines():
        m = sym_re.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = equ_re.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    missing = [n for n in NEED_SYMS if n not in syms] + [n for n in NEED_EQUS if n not in equs]
    if missing:
        raise Unmeasurable(f"{path} carries no {', '.join(missing)} — a DEBUG sonic4 "
                           f"listing is required (Boot_At_* exist only in that shape)")
    return syms, equs


def decode_playerv(rom, syms):
    """player_state and debug_flag offsets out of the ROM's own instruction bytes."""
    a = syms["Player_SetState"]
    w = [int.from_bytes(rom[a + i:a + i + 2], "big") for i in range(0, 10, 2)]
    # lea d16(pc),a1 / moveq #0,d1 / move.b d16(a0),d1
    if w[0] != 0x43FA or w[2] != 0x7200 or w[3] != 0x1228:
        raise Unmeasurable(f"Player_SetState at ${a:06X} no longer opens "
                           f"`lea (pc),a1 / moveq #0,d1 / move.b d16(a0),d1` "
                           f"(words {' '.join(f'{x:04X}' for x in w)}); the player_state "
                           f"offset cannot be decoded, and this file will not guess it")
    state_off = w[4]
    b = syms["Player_DebugExit"]
    op, disp = (int.from_bytes(rom[b + i:b + i + 2], "big") for i in (0, 2))
    if op != 0x51E8:
        raise Unmeasurable(f"Player_DebugExit at ${b:06X} no longer opens `sf d16(a0)` "
                           f"(word {op:04X}); the debug_flag offset cannot be decoded")
    return state_off, disp


# --------------------------------------------------------------------------- the model

class TerrainModel:
    """`probe_core`'s Up and Down stamps + the glide family's sensors, over section 0's
    baked cells: `Player_SensorCeiling`'s pair and `Glide_Collide`'s centre floor sensor."""

    def __init__(self, lrb_mask, top_mask):
        self.lrb, self.top = lrb_mask, top_mask
        self.hm = (BASE_BANK / "heightmaps.bin").read_bytes()
        self.an = (BASE_BANK / "angles.bin").read_bytes()
        self.planes = []
        a = EDITOR / "section_0.collattr.bin"
        if not a.is_file():
            raise Unmeasurable(f"no editor collision at {a}")
        pa = a.read_bytes()
        bpath = EDITOR / "section_0.collattrb.bin"
        pb = bpath.read_bytes() if bpath.is_file() else pa   # absent B mirrors A (ojz_strip_gen)
        for p in (pa, pb):
            if len(p) != EDITOR_W * EDITOR_W * 2:
                raise Unmeasurable(f"editor collision plane is {len(p)} bytes, "
                                   f"expected {EDITOR_W * EDITOR_W * 2}")
        self.planes = [pa, pb]
        self.attrs = cp.AttrSet()
        self.cache = {}

    def _cell(self, layer, x, y, mask, up):
        """probe_core's `.cell`: 0 air, 1..15 partial, 16 full. `up` is the Up stamp
        (heights negated, sub-coordinate flipped); otherwise the Down stamp."""
        if not (0 <= x < SECTION_PX and 0 <= y < SECTION_PX):
            raise Unmeasurable(f"the model was asked about ({x}, {y}), outside section 0 — "
                               f"the drive left the area whose collision it reads")
        plane = self.planes[layer & 1]
        i = (((y >> 4) * 2) * EDITOR_W + (x >> 3)) * 2
        word = int.from_bytes(plane[i:i + 2], "big")
        if word not in self.cache:
            idx = cp.bake_plane_cell(word, self.hm, self.an, self.attrs)
            heights, _angle, sol, _xo = self.attrs.entries[idx]
            self.cache[word] = (heights, sol)
        heights, sol = self.cache[word]
        if not (sol & mask):
            return 0
        h = heights[x & 15]
        h = h - 256 if h >= 128 else h
        if up:
            h = -h                              # probe_neg: Up negates
        if h == 0:
            return 0
        if h < 0:                               # hanging run (near-edge anchored)
            sub = ((y & 15) ^ 15) if up else (y & 15)
            return 0 if sub + h >= 0 else 16
        return h

    def probe_up(self, layer, x, y):
        sub = (y & 15) ^ 15                     # psubflip: Up mirrors the axis
        h = self._cell(layer, x, y, self.lrb, True)
        if h == 0:
            h2 = self._cell(layer, x, y - 16, self.lrb, True)   # one cell forward (up)
            return 32 if h2 == 0 else 32 - (h2 + sub)
        if h == 16:
            h3 = self._cell(layer, x, y + 16, self.lrb, True)   # one cell back (down)
            return -(h3 + sub)
        return 16 - (h + sub)

    def probe_down(self, layer, x, y):
        sub = y & 15                            # Down: no flip
        h = self._cell(layer, x, y, self.top, False)
        if h == 0:
            h2 = self._cell(layer, x, y + 16, self.top, False)  # one cell forward (down)
            return 32 if h2 == 0 else 32 - (h2 + sub)
        if h == 16:
            h3 = self._cell(layer, x, y - 16, self.top, False)  # one cell back (up)
            return -(h3 + sub)
        return 16 - (h + sub)

    def head_dist(self, layer, x, y, w, h):
        rw, rh = w >> 1, h >> 1
        p = y - rh
        return min(self.probe_up(layer, x - rw, p), self.probe_up(layer, x + rw, p))

    def feet_dist(self, layer, x, y, h):
        """Glide_Collide's floor probe: ONE centre sensor at (x, y + (h >> 1)), SOLID_TOP."""
        return self.probe_down(layer, x, y + (h >> 1))


# --------------------------------------------------------------------------- the drive

def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


class Drive:
    def __init__(self, client, syms, equs, state_off, dbg_off):
        self.b, self.s, self.e = client, syms, equs
        self.P = syms["Player_1"] & 0xFFFFFF
        self.pm = syms["Player_Main"] & 0xFFFFFF
        self.state_off, self.dbg_off = state_off, dbg_off

    async def read(self, addr, n):
        r = await self.b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = r["bytes"]
        return bytes.fromhex(s[2:] if s[:2].lower() == "0x" else s)

    async def write(self, addr, value, width):
        await self.b.call("emulator/write_memory",
                          {"addr": hex(addr & 0xFFFFFF), "value": value, "width": width})

    async def frames(self, n):
        await self.b.call("emulator/run_frames", {"frames": n})
        st = await self.b.call("emulator/status", {})
        if "ErrorHandler" in (st.get("symbolAtPc") or ""):
            raise Unmeasurable(f"the ROM FAULTED (symbolAtPc={st.get('symbolAtPc')!r}, "
                               f"pc={st.get('pc')}) — every number after this is a halted machine")

    async def step(self):
        """Advance exactly one PLAYER UPDATE: stop at the next Player_Main entry for
        Player_1. At that PC the previous update (dispatch, Player_LevelBound, touch) is
        complete, so every sample is a whole update however the logic straddles a VBlank.
        `run_to` returns at once when the PC is already the target (measured: six calls,
        same pc, same frame), so one instruction step leaves it first. NUM_PLAYERS is 2
        and Player_Main is an object routine, so a stop on another slot is run past."""
        for _ in range(4):
            await self.b.call("emulator/step", {"count": 1})
            r = await self.b.call("emulator/run_to", {"addr": hex(self.pm), "maxFrames": 3})
            if not r.get("reached"):
                raise Unmeasurable(f"Player_Main (${self.pm:06X}) was not reached within 3 "
                                   f"frames (pc={r.get('pc')}) — the player is not being updated")
            regs = await self.b.call("emulator/registers", {})
            a0 = next(v for k, v in regs.items() if k.lower() == "a0")
            a0 = int(a0, 16) if isinstance(a0, str) else int(a0)
            if a0 & 0xFFFFFF == self.P:
                return
        raise Unmeasurable("four Player_Main stops in a row were not Player_1's")

    async def player(self):
        e = self.e
        blk = await self.read(self.P, 0x50)
        g = lambda o, n: int.from_bytes(blk[o:o + n], "big")  # noqa: E731
        return {"x": g(e["SST_x_pos"], 4), "y": g(e["SST_y_pos"], 4),
                "xv": s16(g(e["SST_x_vel"], 2)), "yv": s16(g(e["SST_y_vel"], 2)),
                "w": blk[e["SST_width_pixels"]], "h": blk[e["SST_height_pixels"]],
                "status": blk[e["SST_status"]], "layer": blk[e["SST_layer"]],
                "state": blk[self.state_off], "dbg": blk[self.dbg_off]}

    async def hold_a(self, down):
        await self.b.call("emulator/hold", {"buttons": ["a"], "down": bool(down)})

    async def boot_knuckles(self, out, x, y):
        """Boot Knuckles at (x, y) and leave debug-fly. Returns the STANDING box (w, h)
        as the running player reports it: Player_DebugExit installs it."""
        s, e = self.s, self.e
        await self.b.call("emulator/reset", {})
        await run_to_addr(self.b, s["GameState_OJZScroll_Init"] & 0xFFFFFF,
                          "GameState_OJZScroll_Init", max_frames=600)
        await self.write(s["Character_ID"], e["CHAR_KNUCKLES"], 2)
        await self.write(s["Boot_At_X"], x, 2)
        await self.write(s["Boot_At_Y"], y, 2)
        await self.write(s["Boot_At_Flag"], 1, 1)            # LAST, per the protocol
        for _ in range(600):
            await self.frames(1)
            if (await self.read(s["Boot_At_Flag"], 1))[0] == 0:
                break
        else:
            raise Unmeasurable("Boot_At_Flag was never consumed — the boot override did not run")
        await self.frames(30)
        cid = int.from_bytes(await self.read(s["Character_ID"], 2), "big")
        p = await self.player()
        if cid != e["CHAR_KNUCKLES"]:
            raise Unmeasurable(f"Character_ID reads {cid}, not CHAR_KNUCKLES "
                               f"({e['CHAR_KNUCKLES']}) — Knuckles was not selected")
        if not p["dbg"]:
            raise Unmeasurable("the player did not boot in debug-fly, so the B press below "
                               "would not be the exit this drive depends on")
        await self.b.call("emulator/press", {"buttons": ["b"]})
        for _ in range(8):
            await self.frames(1)
            p = await self.player()
            if not p["dbg"]:
                break
        if p["dbg"] or p["state"] != e["PSTATE_AIR"]:
            raise Unmeasurable(f"leaving debug-fly did not reach PSTATE_AIR "
                               f"(debug_flag={p['dbg']}, state=${p['state']:02X})")
        out.append(f"  booted Knuckles at ({p['x'] >> 16}, {p['y'] >> 16}), AIR, "
                   f"box {p['w']}x{p['h']}")
        return p["w"], p["h"]

    async def start_glide(self):
        await self.hold_a(True)
        for _ in range(3):
            await self.step()
            if (await self.player())["state"] == self.e["PSTATE_GLIDE"]:
                return
        raise Unmeasurable("holding A from AIR did not enter PSTATE_GLIDE within 3 frames")

    async def glide_until_x(self, x_px):
        for _ in range(MAX_FRAMES):
            p = await self.player()
            if p["state"] != self.e["PSTATE_GLIDE"]:
                raise Unmeasurable(f"the glide ended (state ${p['state']:02X}) at "
                                   f"({p['x'] >> 16}, {p['y'] >> 16}) before x reached {x_px}")
            if (p["x"] >> 16) >= x_px:
                return p
            await self.step()
        raise Unmeasurable(f"x never reached {x_px} in {MAX_FRAMES} frames")

    async def set_y(self, y_px):
        await self.write(self.P + self.e["SST_y_pos"], y_px << 16, 4)
        got = int.from_bytes(await self.read(self.P + self.e["SST_y_pos"], 4), "big")
        if got != y_px << 16:
            raise Unmeasurable(f"the y_pos write did not read back ({got:08X})")

    async def record(self, n, stop):
        rows = [await self.player()]
        for _ in range(n):
            await self.step()
            rows.append(await self.player())
            if stop(rows[-1]):
                break
        return rows


# --------------------------------------------------------------------------- analysis

def mostly_down(xv, yv):
    """Air_Collide's class boundary: |x_vel| <= |y_vel| is vertical (ties vertical), and
    the vertical class is DOWN when y_vel >= 0. The glide probes the ceiling otherwise."""
    return abs(xv) <= abs(yv) and yv >= 0


def annotate(rows, model, e):
    """One row per stepped update. THE INTEGRATOR, per state (the note's §8): a GLIDE update
    writes y_vel in Glide_Move BEFORE ObjectMove, so its move is the END y_vel; a GLIDEFALL
    update moves by the PREVIOUS y_vel and adds gravity after. Any other y change on an
    update that stays in its state is a correction — an ejection. A state-change update runs
    other code (the release hook, the landing) and is marked, never graded here; legs B and
    C grade those updates themselves."""
    g, gf = e["PSTATE_GLIDE"], e["PSTATE_GLIDEFALL"]
    out = []
    for prev, cur in zip(rows, rows[1:]):
        x, y = cur["x"] >> 16, cur["y"] >> 16
        # A STALLED update — the player code did not run. Every GLIDE update changes x_vel
        # (gsp accel) or y_vel (the parachute alternates), and every GLIDEFALL update
        # changes y_vel (gravity) or y (at the cap), so "all four unchanged" cannot be an
        # update that ran. model_control refuses it outright.
        stall = all(prev[k] == cur[k] for k in ("x", "y", "xv", "yv"))
        stay = not stall and prev["state"] == cur["state"] and cur["state"] in (g, gf)
        move = (cur["yv"] if cur["state"] == g else prev["yv"]) * 256
        d_end = model.head_dist(cur["layer"], x, y, cur["w"], cur["h"])
        pre_y = (prev["y"] + move) >> 16                      # where the MOVE put the head
        d_pre = model.head_dist(cur["layer"], x, pre_y, cur["w"], cur["h"])
        out.append({"x": cur["x"] / 65536, "y": cur["y"] / 65536, "yv": cur["yv"],
                    "xv": cur["xv"], "state_in": prev["state"], "state": cur["state"],
                    "box": f"{cur['w']}x{cur['h']}", "dist": d_end, "dist_pre": d_pre,
                    "feet": model.feet_dist(cur["layer"], x, y, cur["h"]),
                    "stall": stall, "stay": stay,
                    "ejected": stay and cur["y"] - prev["y"] != move,
                    "down": mostly_down(cur["xv"], cur["yv"])})
    return out


def model_control(rows):
    """Every update the ENGINE ejected must read 0 in the model afterwards, and no sample
    may be a stall: stepping by player updates makes one impossible, so a stall means the
    stepping is not doing what `Drive.step` says it does."""
    stalls = sum(r["stall"] for r in rows)
    if stalls:
        raise Unmeasurable(f"STEPPING CONTROL: {stalls} sample(s) show no player update at "
                           f"all, which stepping by Player_Main entries cannot produce")
    bad = [r for r in rows if r["ejected"] and r["dist"] != 0]
    if bad:
        raise Unmeasurable(f"MODEL CONTROL: the engine ejected on {len(bad)} frame(s) and the "
                           f"model does not read 0 after them ({[r['dist'] for r in bad]}) — "
                           f"the model is not the engine's probe, so no distance it prints "
                           f"can be trusted")


def fmt(i, r):
    tag = ("  EJECTED" if r["ejected"] else "  (stalled: player code did not run)"
           if r["stall"] else "" if r["stay"] else "  (state change)")
    return (f"    f+{i:<3d} x={r['x']:8.2f} y={r['y']:8.3f} xv={r['xv']:+6d} yv={r['yv']:+5d} "
            f"state=${r['state_in']:02X}->${r['state']:02X} box={r['box']:5s} "
            f"head dist={r['dist']:+3d} (move put it at {r['dist_pre']:+3d}) "
            f"feet dist={r['feet']:+3d}"
            f"{tag}{'  [down class]' if r['down'] else ''}")


def release_update(rows, model, stand, e, out):
    """Find the release update (GLIDE -> GLIDEFALL) and derive, from design-independent
    quantities only, where it SHOULD leave the player. The release update runs Glide_Move
    (y_vel), ObjectMove (y += y_vel * 256), Glide_Collide, and then the GLIDEFALL enter
    hook; the hook touches no velocity, so the unlifted end position is the previous
    sample plus the END y_vel — valid on both designs. Glide_Collide may not have moved y
    in that update (no ceiling eject, no floor landing), or the derivation is void."""
    g, gf = e["PSTATE_GLIDE"], e["PSTATE_GLIDEFALL"]
    for i in range(1, len(rows)):
        if rows[i - 1]["state"] == g and rows[i]["state"] == gf:
            break
    else:
        raise Unmeasurable("no GLIDE -> GLIDEFALL update was recorded — the release did not happen")
    prev, cur = rows[i - 1], rows[i]
    x = cur["x"] >> 16
    aw, ah = prev["w"], prev["h"]
    sw, sh = stand
    dr = (sh >> 1) - (ah >> 1)
    out.append(f"  Δr = (standing h {sh} >> 1) - (ability h {ah} >> 1) = {sh >> 1} - "
               f"{ah >> 1} = {dr}  (both heights read from the running player)")
    y_nolift = prev["y"] + cur["yv"] * 256
    yn = y_nolift >> 16
    if model.head_dist(prev["layer"], x, yn, aw, ah) < 0:
        raise Unmeasurable("the glide head was in the ceiling at the release update's "
                           "post-move position, so Glide_Collide ejected it and the release "
                           "update has a third y writer — the derivation does not apply")
    if cur["yv"] >= 0 and model.feet_dist(prev["layer"], x, yn, ah) < 0:
        raise Unmeasurable("the glide feet were in the floor at the release update's "
                           "post-move position, so the glide should have LANDED there")
    return {"i": i, "prev": prev, "cur": cur, "x": x, "dr": dr, "stand": stand,
            "abil": (aw, ah), "y_nolift": y_nolift, "yn": yn, "y_end": cur["y"],
            "lift": cur["y"] - y_nolift, "layer": prev["layer"]}


def grade_release_mechanism(rel, fails, leg):
    """The two engine facts both CHAR-6 legs rest on: the release moves y by the glide's own
    move and nothing else, and it leaves the standing box."""
    cur = rel["cur"]
    if rel["lift"] != 0:
        fails.append(f"{leg}: the release update moved y_pos by {rel['lift'] / 65536:+.4f} px "
                     f"beyond the glide's own move (y_vel {cur['yv']:+d}); a centre-preserving "
                     f"restore moves it by 0, the feet-planted lift by -Δr = -{rel['dr']}")
    if (cur["w"], cur["h"]) != rel["stand"]:
        fails.append(f"{leg}: the release left box {cur['w']}x{cur['h']}, not the standing "
                     f"box {rel['stand'][0]}x{rel['stand'][1]}")


async def leg_a(drv, model, out, verbose):
    e = drv.e
    out.append("LEG A — CHAR-4 (a): glide right into the slab from integer y "
               f"{INJECT_Y_A} (ASSERTED)")
    await drv.boot_knuckles(out, BOOT_X, BOOT_Y)
    await drv.start_glide()
    p = await drv.glide_until_x(INJECT_X)
    out.append(f"  injecting y_pos = {INJECT_Y_A}.0 at x={p['x'] / 65536:.2f} "
               f"(state ${p['state']:02X})")
    await drv.set_y(INJECT_Y_A)
    rows = await drv.record(MAX_FRAMES, lambda r: (r["x"] >> 16) >= STOP_X
                            or r["state"] != e["PSTATE_GLIDE"])
    await drv.hold_a(False)
    ann = annotate(rows, model, e)
    for i, r in enumerate(ann):
        if verbose or r["dist"] < 0 or r["dist_pre"] < 0 or r["ejected"]:
            out.append(fmt(i + 1, r))
    g = e["PSTATE_GLIDE"]
    subject = [r for r in ann if r["stay"] and r["state"] == g and not r["down"]]
    contact = [r for r in subject if r["dist_pre"] < 0]
    embedded = [r for r in subject if r["dist"] < 0]
    ejected = [r for r in ann if r["ejected"]]
    out.append(f"  frames recorded {len(ann)} ({sum(r['stall'] for r in ann)} stalled, "
               f"not graded); glide frames in a probing class {len(subject)}; "
               f"frames where the MOVE put the head in the ceiling {len(contact)}; "
               f"engine ejections {len(ejected)}; frames ENDING embedded {len(embedded)}")
    model_control(ann)
    if not contact:
        raise Unmeasurable("NO SUBJECT: the move never carried the head into a ceiling, so "
                           "'no frame ends embedded' is true of this run for free. The "
                           "content under the drive coordinates has probably moved")
    fails = []
    if embedded:
        fails.append(f"A: {len(embedded)} glide frame(s) in a probing class END with the head "
                     f"in the ceiling (depths {[r['dist'] for r in embedded]}); the move put it "
                     f"there on {len(contact)} frame(s) and the engine ejected "
                     f"{len(ejected)} time(s)")
    return {"frames": len(ann), "subject": len(subject), "contact": len(contact),
            "ejected": len(ejected), "embedded": len(embedded),
            "embedded_depths": [r["dist"] for r in embedded], "fails": fails}


async def leg_b(drv, model, out, verbose):
    e = drv.e
    out.append(f"LEG B — CHAR-6, the head: release under the slab at y {UNDER_Y_B}, "
               f"x >= {RELEASE_X} (ASSERTED)")
    stand = await drv.boot_knuckles(out, BOOT_X, BOOT_Y)
    await drv.start_glide()
    await drv.glide_until_x(INJECT_X)
    await drv.set_y(UNDER_Y_B)
    p = await drv.glide_until_x(RELEASE_X)
    await drv.set_y(UNDER_Y_B)
    out.append(f"  releasing A at x={p['x'] / 65536:.2f}, y={UNDER_Y_B}.0")
    await drv.hold_a(False)
    rows = await drv.record(40, lambda r: r["state"] not in (e["PSTATE_GLIDE"],
                                                             e["PSTATE_GLIDEFALL"]))
    ann = annotate(rows, model, e)
    model_control(ann)
    rel = release_update(rows, model, stand, e, out)
    first = rel["i"] - 1
    for i, r in enumerate(ann[first:first + 12]):
        out.append(fmt(first + i + 1, r))
    sw, sh = stand
    aw, ah = rel["abil"]
    L, x, yn, dr = rel["layer"], rel["x"], rel["yn"], rel["dr"]
    # THE DERIVATION. The unlifted release leaves the head at the glide head's clearance
    # minus Δr; the lifted one at minus 2Δr. The leg discriminates only if the first is
    # clear and the second is not.
    d_glide = model.head_dist(L, x, yn, aw, ah)
    d_keep = model.head_dist(L, x, yn, sw, sh)
    d_lift = model.head_dist(L, x, yn - dr, sw, sh)
    out.append(f"  derived at the release column x={x}: glide head clearance {d_glide:+d}; "
               f"standing head, centre kept (y {yn}) {d_keep:+d} = {d_glide:+d} - Δr; "
               f"feet-planted lift (y {yn - dr}) {d_lift:+d} = {d_glide:+d} - 2Δr")
    if d_keep != d_glide - dr or d_lift != d_glide - 2 * dr:
        raise Unmeasurable(f"the release column is not under a flat underside for both sensor "
                           f"pairs ({d_keep} vs {d_glide - dr}, {d_lift} vs {d_glide - 2 * dr}), "
                           f"so the head's rise is not Δr there and the derivation does not apply")
    if not (d_keep >= 0 > d_lift):
        raise Unmeasurable(f"NO SUBJECT: the two designs do not disagree here (centre kept "
                           f"{d_keep:+d}, lifted {d_lift:+d}); the leg cannot tell them apart")
    fails = []
    grade_release_mechanism(rel, fails, "B")
    tail = ann[rel["i"] - 1:]
    emb = [r for r in tail if r["state"] in (e["PSTATE_GLIDEFALL"],) and r["dist"] < 0]
    ej = [r for r in tail if r["ejected"]]
    out.append(f"  release update: dy = {(rel['y_end'] - rel['prev']['y']) / 65536:+.4f} px, "
               f"the glide's own move {rel['cur']['yv'] * 256 / 65536:+.4f} px, excess "
               f"{rel['lift'] / 65536:+.4f} px; box {rel['cur']['w']}x{rel['cur']['h']}; head "
               f"dist {ann[rel['i'] - 1]['dist']:+d} (expected {d_keep:+d})")
    out.append(f"  GLIDEFALL updates ENDING with the head embedded: {len(emb)} (expected 0); "
               f"ceiling ejections {len(ej)}")
    if emb:
        fails.append(f"B: {len(emb)} update(s) from the release on END with the head in the "
                     f"slab (depths {[r['dist'] for r in emb]}); a centre-preserving restore "
                     f"leaves {d_keep:+d} here")
    return {"release_excess_px": rel["lift"] / 65536, "release_head_dist": ann[rel["i"] - 1]["dist"],
            "expected_head_dist": d_keep, "embedded": len(emb), "ejections": len(ej),
            "fails": fails}


async def leg_c(drv, model, out, verbose):
    e = drv.e
    out.append(f"LEG C — CHAR-6, the feet: release {FEET_GAP_C} px above the floor at "
               f"x >= {RELEASE_X_C} (ASSERTED)")
    stand = await drv.boot_knuckles(out, BOOT_C_X, BOOT_C_Y)
    await drv.start_glide()
    p = await drv.glide_until_x(RELEASE_X_C)
    x, L, ah = p["x"] >> 16, p["layer"], p["h"]
    seek = model.probe_down(L, x, FLOOR_SEEK_Y)
    if not 0 <= seek < 32:
        raise Unmeasurable(f"no floor within reach below ({x}, {FLOOR_SEEK_Y}) (dist {seek}) — "
                           f"the content under leg C's coordinates has moved")
    top = FLOOR_SEEK_Y + seek
    dr = (stand[1] >> 1) - (ah >> 1)
    if not 0 <= FEET_GAP_C < dr:
        raise Unmeasurable(f"FEET_GAP_C {FEET_GAP_C} is not in 0..Δr-1 = 0..{dr - 1}, so the "
                           f"standing feet would not reach the floor and the leg has no subject")
    y_c = top - (ah >> 1) - FEET_GAP_C
    out.append(f"  model: the floor's top row under x={x} is {top} (probed from y "
               f"{FLOOR_SEEK_Y}, not typed in); releasing A at y={y_c}.0 puts the glide "
               f"feet {FEET_GAP_C} px above it")
    await drv.set_y(y_c)
    await drv.hold_a(False)
    rows = await drv.record(40, lambda r: r["state"] not in (e["PSTATE_GLIDE"],
                                                             e["PSTATE_GLIDEFALL"]))
    ann = annotate(rows, model, e)
    model_control(ann)
    rel = release_update(rows, model, stand, e, out)
    first = rel["i"] - 1
    for i, r in enumerate(ann[first:first + 6]):
        out.append(fmt(first + i + 1, r))
    sw, sh = stand
    aw, ah = rel["abil"]
    L, x, yn, dr = rel["layer"], rel["x"], rel["yn"], rel["dr"]
    f_glide = model.feet_dist(L, x, yn, ah)
    f_keep = model.feet_dist(L, x, yn, sh)
    out.append(f"  derived at the release column x={x}: glide feet gap {f_glide:+d}; standing "
               f"feet, centre kept (y {yn}) {f_keep:+d} = {f_glide:+d} - Δr")
    if f_keep != f_glide - dr:
        raise Unmeasurable(f"the release column is not over a flat floor ({f_keep} vs "
                           f"{f_glide - dr}), so the feet's drop is not Δr there")
    if f_keep >= 0:
        raise Unmeasurable(f"NO SUBJECT: the standing feet end the release {f_keep:+d} from the "
                           f"floor, so there is no embedded frame for the next update to correct")
    fails = []
    grade_release_mechanism(rel, fails, "C")
    i = rel["i"]
    if i + 1 >= len(rows):
        raise Unmeasurable("the recording ended at the release update; the landing was not sampled")
    after, land = rows[i], rows[i + 1]
    moved = after["y"] + after["yv"] * 256                  # GLIDEFALL: move by the previous y_vel
    f_pre = model.feet_dist(L, land["x"] >> 16, moved >> 16, sh)
    f_land = model.feet_dist(L, land["x"] >> 16, land["y"] >> 16, sh)
    corr = land["y"] - moved
    out.append(f"  release update ends with the feet at {ann[i - 1]['feet']:+d} (expected "
               f"{f_keep:+d}: the one frame S3K accepts)")
    out.append(f"  next update: state ${after['state']:02X}->${land['state']:02X}, "
               f"xv={land['xv']:+d} yv={land['yv']:+d}; its move put the feet at {f_pre:+d}, the "
               f"engine corrected y by {corr / 65536:+.4f} px, feet now {f_land:+d}")
    if land["state"] != e["PSTATE_GROUND"]:
        fails.append(f"C: the update after the release did not land (state ${land['state']:02X}, "
                     f"feet at floor distance {ann[i]['feet']:+d})")
    else:
        if land["xv"] or land["yv"]:
            fails.append(f"C: the landing is not GLIDEFALL's dead stop (xv {land['xv']:+d}, "
                         f"yv {land['yv']:+d})")
        if corr != f_pre << 16:
            raise Unmeasurable(f"MODEL CONTROL (floor): the engine corrected y by "
                               f"{corr / 65536:+.4f} px where the model's floor distance is "
                               f"{f_pre:+d} — the floor model is not the engine's probe")
        if f_land != 0:
            fails.append(f"C: the landing left the feet at floor distance {f_land:+d}, not 0")
    emb = [r for r in ann[i - 1:] if r["feet"] < 0]
    out.append(f"  updates ENDING with the feet in the floor from the release on: {len(emb)} "
               f"(expected 1, the release update)")
    if len(emb) != 1:
        fails.append(f"C: {len(emb)} update(s) end with the feet in the floor (expected exactly "
                     f"the release update)")
    return {"release_excess_px": rel["lift"] / 65536, "release_feet": ann[i - 1]["feet"],
            "expected_feet": f_keep, "landing_state": land["state"], "landed_feet": f_land,
            "feet_embedded_updates": len(emb), "fails": fails}


async def main_async(sock, rom, syms, equs, out, verbose):
    client = BusClient(socket_path=sock, client_id="glideceil", client_name="glide_ceiling")
    await client.connect()
    try:
        state_off, dbg_off = decode_playerv(Path(rom).read_bytes(), syms)
        out.append(f"  PlayerV.player_state +${state_off:02X}, debug_flag +${dbg_off:02X} "
                   f"(decoded from the ROM's Player_SetState / Player_DebugExit bytes)")
        model = TerrainModel(equs["SOLID_LRB"], equs["SOLID_TOP"])
        # dist = p - u for a sensor under a solid run, so u = p - dist: the model reports
        # the slab's last solid row rather than this file assuming it.
        rows = sorted({520 - model.probe_up(0, x, 520) for x in range(912, 1008)})
        out.append(f"  model: last solid LRB row above y 520, plane A, x 912..1007 = {rows} "
                   f"(derived from the editor collision, not typed in)")
        drv = Drive(client, syms, equs, state_off, dbg_off)
        a = await leg_a(drv, model, out, verbose)
        b = await leg_b(drv, model, out, verbose)
        c = await leg_c(drv, model, out, verbose)
        return a, b, c
    finally:
        await client.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--json", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    out = [f"glide_ceiling_witness  ROM {args.rom}"]
    try:
        for f in (args.rom, args.lst):
            if not os.path.isfile(f):
                raise Blocked(f"{f} does not exist — build the DEBUG sonic4 shape first")
        syms, equs = parse_lst(args.lst)
        with aether_emulator(args.rom, symbols=args.lst) as sock:
            a, b, c = asyncio.run(main_async(sock, args.rom, syms, equs, out, args.verbose))
    except Blocked as e:
        print("\n".join(out))
        print(f"\nBLOCKED: {e}")
        return 3
    except (Unmeasurable, CartMismatch) as e:
        print("\n".join(out))
        print(f"\nUNMEASURABLE: {e}")
        return 2
    print("\n".join(out))
    if args.json:
        Path(args.json).write_text(json.dumps({"leg_a": a, "leg_b": b, "leg_c": c},
                                              indent=2) + "\n")
    fails = a["fails"] + b["fails"] + c["fails"]
    if fails:
        print("\nRESULT: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"\nRESULT: PASS — A: the move put the head in the ceiling on {a['contact']} frame(s), "
          f"the engine ejected {a['ejected']} time(s), no probing-class glide frame ends "
          f"embedded. B: the release kept the centre and the head ended at "
          f"{b['release_head_dist']:+d}; 0 updates end embedded. C: the release left the feet "
          f"at {c['release_feet']:+d} and the next update landed them at 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
