#!/usr/bin/env python3
"""glide_ceiling_witness — does Knuckles' glide push his head back out of a ceiling? (CHAR-4)

THE CLAIM UNDER TEST (`docs/lens-findings.jsonl` CHAR-4). The glide family had no ceiling
probe, so a glide carried Knuckles' head into the underside of the OJZ act 1 box's 16 px
slab and left it there: the controller measured 7 frames at 4 px deep, every frame's y
change equal to y_vel exactly (docs/superpowers/notes/2026-09-13-char46-repro-recipe.md
§10). The fix runs the air states' own ceiling machinery (`Air_CeilingBump` ->
`Player_SensorCeiling`) inside `Glide_Collide` whenever the motion is NOT mostly down —
`Air_Collide`'s classifier, S3K's `Knux_DoLevelCollision_CheckRet` classes.

THE ASSERTION, DERIVED FROM WHAT THE FIX GUARANTEES rather than from a remembered count.
Inside `Glide_Collide` the ceiling probe runs after the move and before the frame's
state decision, and an embedded head (dist < 0) is moved down by exactly -dist, which is
dist 0 at the new position. Nothing later in a frame that STAYS in PSTATE_GLIDE moves y
up (the floor snap only moves y up onto a floor the feet are inside, and there is no
floor within reach here). So:

    every frame that starts AND ends in PSTATE_GLIDE, in a motion class that is not
    mostly down, ends with the head's ceiling distance >= 0.

Frames that change state are excluded on purpose: the release runs PHook_EnsureStanding's
9 px lift AFTER Glide_Collide, which is CHAR-6 and a separate parcel. Leg B measures it.

THE CEILING DISTANCE IS THE ENGINE'S OWN CRITERION, re-derived here and not typed in:
`Player_SensorCeiling`'s pair at (x_int -/+ (width >> 1), y_int - (height >> 1)), each run
through a Python mirror of `probe_core`'s `Collision_ProbeUp` stamp (player_sensors.emp:
heights negated, sub-coordinate flipped, one cell forward on empty, one cell back on
full, the hanging-run rule), over cells baked with `collision_pipeline.bake_plane_cell`
from the SAME editor collision the build bakes (section 0 plane A/B, the S&K base bank),
on the layer the player is actually on. The closer sensor wins. dist < 0 is embedded.
The last solid row of the slab (511) is therefore an OUTPUT of this file — it is printed,
never assumed. build.sh's level-staleness gate is what binds the editor tree to the ROM.

TWO CONTROLS ON THE MODEL, because a mis-modelled probe would read as a result:
  * every frame the ENGINE ejected (dy != y_vel * 256 on a glide frame) must read
    exactly 0 in the model afterwards — the engine moved by its own probe's -dist, so
    a model that disagrees is caught against the engine itself;
  * the run must contain at least one frame where the MOVE carried the head into the
    ceiling (the model's distance at the pre-collision position, y_prev + y_vel, is
    < 0). Without one the assertion has no subject and the run is UNMEASURABLE, not a
    pass.

LEGS (both boot fresh, both select Knuckles the same way):
  A  CHAR-4 (a), ASSERTED. The note's §7 recipe: glide right in open air, and when the
     integer x first reaches INJECT_X write y_pos = 514.0; hold A; step one frame at a
     time to STOP_X. RED on the unfixed ROM (the head sits in the slab), GREEN on the fix.
  B  CHAR-6 release, INFORMATIONAL. Pass under the slab at y 532 and release A once x
     reaches RELEASE_X: count the frames that END embedded from the release on. The
     release frame itself stays embedded until CHAR-6's lift is fixed; with the ceiling
     probe the next GLIDEFALL frame should eject.

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
the model control and the contact requirement are what turn a moved slab into a loud
UNMEASURABLE instead of a quiet pass.

RUNNER: none. This repo runs player-physics runtime witnesses BY HAND; the only runtime
witness any runner executes is `preset_lab_witness.py`, in the effects nightly. Wiring
this one somewhere is booked, not done here.

    python3 tools/glide_ceiling_witness.py --rom s4.debug.bin --lst s4.debug.lst [-v]

Exit 0 the guarantee held (leg A) · 1 it did NOT hold · 2 UNMEASURABLE · 3 BLOCKED.
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
             "GameState_OJZScroll_Init", "Player_SetState", "Player_DebugExit")
NEED_EQUS = ("SST_x_pos", "SST_y_pos", "SST_x_vel", "SST_y_vel", "SST_width_pixels",
             "SST_height_pixels", "SST_status", "SST_layer", "CHAR_KNUCKLES",
             "PSTATE_AIR", "PSTATE_GLIDE", "PSTATE_GLIDEFALL", "SOLID_LRB")

# Drive coordinates (world px). Content coordinates — see the docstring.
BOOT_X, BOOT_Y = 760, 470   # open air left of the box: nothing solid within reach
INJECT_X = 850              # leg A: first integer x at which y_pos is written
INJECT_Y_A = 514            # leg A: the note's §7 recipe (inside its 512..520 band)
UNDER_Y_B = 532             # leg B: under the slab, glide head clear by the model
RELEASE_X = 925             # leg B: both standing head sensors under the flat underside
STOP_X = 960                # leg A: stop recording once past the embed run
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

class CeilingModel:
    """`Collision_ProbeUp` + `Player_SensorCeiling`'s pair, over section 0's baked cells."""

    def __init__(self, lrb_mask):
        self.lrb = lrb_mask
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

    def _cell(self, layer, x, y):
        """probe_core's `.cell` for the UP stamp: 0 air, 1..15 partial, 16 full."""
        if not (0 <= x < SECTION_PX and 0 <= y < SECTION_PX):
            raise Unmeasurable(f"the model was asked about ({x}, {y}), outside section 0 — "
                               f"the drive left the area whose collision it reads")
        plane = self.planes[layer & 1]
        i = (((y >> 4) * 2) * EDITOR_W + (x >> 3)) * 2
        word = int.from_bytes(plane[i:i + 2], "big")
        key = word
        if key not in self.cache:
            idx = cp.bake_plane_cell(word, self.hm, self.an, self.attrs)
            heights, _angle, sol, _xo = self.attrs.entries[idx]
            self.cache[key] = (heights, sol)
        heights, sol = self.cache[key]
        if not (sol & self.lrb):
            return 0
        h = heights[x & 15]
        h = h - 256 if h >= 128 else h
        h = -h                                  # probe_neg: Up negates
        if h == 0:
            return 0
        if h < 0:                               # hanging run (near-edge anchored)
            sub = (y & 15) ^ 15
            return 0 if sub + h >= 0 else 16
        return h

    def probe_up(self, layer, x, y):
        sub = (y & 15) ^ 15                     # psubflip: Up mirrors the axis
        h = self._cell(layer, x, y)
        if h == 0:
            h2 = self._cell(layer, x, y - 16)   # one cell forward (up)
            return 32 if h2 == 0 else 32 - (h2 + sub)
        if h == 16:
            h3 = self._cell(layer, x, y + 16)   # one cell back (down)
            return -(h3 + sub)
        return 16 - (h + sub)

    def head_dist(self, layer, x, y, w, h):
        rw, rh = w >> 1, h >> 1
        p = y - rh
        return min(self.probe_up(layer, x - rw, p), self.probe_up(layer, x + rw, p))


# --------------------------------------------------------------------------- the drive

def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


class Drive:
    def __init__(self, client, syms, equs, state_off, dbg_off):
        self.b, self.s, self.e = client, syms, equs
        self.P = syms["Player_1"] & 0xFFFFFF
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

    async def boot_knuckles(self, out):
        s, e = self.s, self.e
        await self.b.call("emulator/reset", {})
        await run_to_addr(self.b, s["GameState_OJZScroll_Init"] & 0xFFFFFF,
                          "GameState_OJZScroll_Init", max_frames=600)
        await self.write(s["Character_ID"], e["CHAR_KNUCKLES"], 2)
        await self.write(s["Boot_At_X"], BOOT_X, 2)
        await self.write(s["Boot_At_Y"], BOOT_Y, 2)
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

    async def start_glide(self):
        await self.hold_a(True)
        for _ in range(3):
            await self.frames(1)
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
            await self.frames(1)
        raise Unmeasurable(f"x never reached {x_px} in {MAX_FRAMES} frames")

    async def set_y(self, y_px):
        await self.write(self.P + self.e["SST_y_pos"], y_px << 16, 4)
        got = int.from_bytes(await self.read(self.P + self.e["SST_y_pos"], 4), "big")
        if got != y_px << 16:
            raise Unmeasurable(f"the y_pos write did not read back ({got:08X})")

    async def record(self, n, stop):
        rows = [await self.player()]
        for _ in range(n):
            await self.frames(1)
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
    """One row per stepped frame. THE INTEGRATOR, per state (the note's §8): a GLIDE frame
    writes y_vel in Glide_Move BEFORE ObjectMove, so its move is the END y_vel; a GLIDEFALL
    frame moves by the PREVIOUS y_vel and adds gravity after. Any other y change on a frame
    that stays in its state is a correction — an ejection. A state-change frame runs other
    code (the release lift) and is marked, never graded."""
    g, gf = e["PSTATE_GLIDE"], e["PSTATE_GLIDEFALL"]
    out = []
    for prev, cur in zip(rows, rows[1:]):
        x, y = cur["x"] >> 16, cur["y"] >> 16
        # A STALLED frame — the player code did not run (a lag frame; measured on the
        # first step after the injection). Every GLIDE frame changes x_vel (gsp accel)
        # or y_vel (the parachute alternates), and every GLIDEFALL frame changes y_vel
        # (gravity) or y (at the cap), so "all four unchanged" cannot be a frame that
        # ran. It is marked and never graded; reading it as dy != move would call it
        # an ejection, which is what the first run of this file did.
        stall = all(prev[k] == cur[k] for k in ("x", "y", "xv", "yv"))
        stay = not stall and prev["state"] == cur["state"] and cur["state"] in (g, gf)
        move = (cur["yv"] if cur["state"] == g else prev["yv"]) * 256
        d_end = model.head_dist(cur["layer"], x, y, cur["w"], cur["h"])
        pre_y = (prev["y"] + move) >> 16                      # where the MOVE put the head
        d_pre = model.head_dist(cur["layer"], x, pre_y, cur["w"], cur["h"])
        out.append({"x": cur["x"] / 65536, "y": cur["y"] / 65536, "yv": cur["yv"],
                    "xv": cur["xv"], "state_in": prev["state"], "state": cur["state"],
                    "box": f"{cur['w']}x{cur['h']}", "dist": d_end, "dist_pre": d_pre,
                    "stall": stall, "stay": stay,
                    "ejected": stay and cur["y"] - prev["y"] != move,
                    "down": mostly_down(cur["xv"], cur["yv"])})
    return out


def model_control(rows):
    """Every frame the ENGINE ejected must read 0 in the model afterwards."""
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
            f"head dist={r['dist']:+3d} (move put it at {r['dist_pre']:+3d})"
            f"{tag}{'  [down class]' if r['down'] else ''}")


async def leg_a(drv, model, out, verbose):
    e = drv.e
    out.append("LEG A — CHAR-4 (a): glide right into the slab from integer y "
               f"{INJECT_Y_A} (ASSERTED)")
    await drv.boot_knuckles(out)
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
    return {"frames": len(ann), "subject": len(subject), "contact": len(contact),
            "ejected": len(ejected), "embedded": len(embedded),
            "embedded_depths": [r["dist"] for r in embedded]}


async def leg_b(drv, model, out, verbose):
    e = drv.e
    out.append(f"LEG B — CHAR-6 release under the slab at y {UNDER_Y_B}, x >= {RELEASE_X} "
               f"(INFORMATIONAL)")
    await drv.boot_knuckles(out)
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
    fall = [r for r in ann if r["state"] == e["PSTATE_GLIDEFALL"]]
    if not fall:
        raise Unmeasurable("leg B never reached PSTATE_GLIDEFALL — the release did not happen")
    first = ann.index(fall[0])
    tail = ann[first:first + 12]
    for i, r in enumerate(tail):
        out.append(fmt(first + i + 1, r))
    emb = [r for r in fall if r["dist"] < 0]
    run = 0
    for r in ann[first:]:
        if r["state"] != e["PSTATE_GLIDEFALL"] or r["dist"] >= 0:
            break
        run += 1
    ej = [r for r in fall if r["ejected"]]
    out.append(f"  frames ENDING embedded from the release on: {run} consecutive "
               f"({len(emb)} in all GLIDEFALL frames); release-frame depth "
               f"{fall[0]['dist']:+d}; GLIDEFALL ejections {len(ej)}")
    return {"release_run": run, "glidefall_embedded": len(emb),
            "release_depth": fall[0]["dist"], "glidefall_ejections": len(ej)}


async def main_async(sock, rom, syms, equs, out, verbose):
    client = BusClient(socket_path=sock, client_id="glideceil", client_name="glide_ceiling")
    await client.connect()
    try:
        state_off, dbg_off = decode_playerv(Path(rom).read_bytes(), syms)
        out.append(f"  PlayerV.player_state +${state_off:02X}, debug_flag +${dbg_off:02X} "
                   f"(decoded from the ROM's Player_SetState / Player_DebugExit bytes)")
        model = CeilingModel(equs["SOLID_LRB"])
        # dist = p - u for a sensor under a solid run, so u = p - dist: the model reports
        # the slab's last solid row rather than this file assuming it.
        rows = sorted({520 - model.probe_up(0, x, 520) for x in range(912, 1008)})
        out.append(f"  model: last solid LRB row above y 520, plane A, x 912..1007 = {rows} "
                   f"(derived from the editor collision, not typed in)")
        drv = Drive(client, syms, equs, state_off, dbg_off)
        a = await leg_a(drv, model, out, verbose)
        b = await leg_b(drv, model, out, verbose)
        return a, b
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
            a, b = asyncio.run(main_async(sock, args.rom, syms, equs, out, args.verbose))
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
        Path(args.json).write_text(json.dumps({"leg_a": a, "leg_b": b}, indent=2) + "\n")
    print(f"\nLEG B (informational): {b['release_run']} frame(s) end embedded from the "
          f"release on.")
    if a["embedded"]:
        print(f"RESULT: FAIL — {a['embedded']} glide frame(s) in a probing class END with the "
              f"head in the ceiling (depths {a['embedded_depths']}); the move put it there "
              f"on {a['contact']} frame(s) and the engine ejected {a['ejected']} time(s).")
        return 1
    print(f"RESULT: PASS — the move put the head in the ceiling on {a['contact']} frame(s); "
          f"the engine ejected {a['ejected']} time(s); no probing-class glide frame ends "
          f"embedded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
