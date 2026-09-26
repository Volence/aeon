#!/usr/bin/env python3
"""loop_step_over_witness.py — drive a real player through OJZ act 1's section-0 loop, both
ways and at speed, and record the collision LAYER and the sprite PRIORITY bit every frame.

WHAT IT IS FOR (LINES-EVERYWHERE, 2026-09-26). The loop's layer changes come from the act's
layer-line table (`Act.act_layer_lines`, run by `Player_LayerLines` in
games/sonic4/player/player_common.emp). This witness drives the shipped act in the real ROM,
headless, with nothing injected but one ground speed, and reports what the layer and the
priority bit did on every frame. It was first written for the painted crossover marks those
lines replaced, and it keeps their question: a player going faster than one collision cell a
frame must not step over a layer change.

THE STEP-OVER CLASS, and why it is graded here (docs/LOOP_CROSSOVER_ENCODING.md §12, which is
superseded but keeps the history). A painted mark was one 8 px cell read once per frame, so
above ~8 px/frame a frame could begin on one side of it and end on the other without
occupying it. A line is a CROSSING, not a cell: it fires when the player's position goes from
one side of it to the other between two checks, however far he moved (up to the step bound).
So a line cannot be stepped over. That is the claim, and this witness GRADES it on every
drive: from the ROM's own table (read through `Current_Act_Ptr` -> `Act.act_layer_lines`) and
the drive's own per-frame positions, it derives which rows each frame crossed and what
Obj03's rule says the layer and priority must be afterwards, and it requires the ROM to agree
on every frame. The speeds and the start phases are what make a step-over possible if one
existed; the grade is what would see it.

WHAT IS INJECTED, and nothing else. `PlayerV.ground_speed`, ONCE, after the player has landed
at the start. Everything downstream is the engine's. The three speeds are derived from the
build's own constants, not chosen:

    PHYS_TOP_SPEED  $600  =  6 px/frame   under one collision cell (COLL_CELL_W)
    (the boundary)  $900  =  9 px/frame   just over one cell a frame
    PHYS_GSP_CAP   $1000  = 16 px/frame   two whole cells a frame

`--phase-sweep` shifts the start X over one COLL_CELL_W stride at the cap: the sub-cell phase
is what decided whether a 16 px stride landed on a painted mark or straddled it.

THE PREDICTION, and the lag in it. Player_LayerLines runs in Player_Main's preamble. It
compares the position the previous frame resolved to against the one it saw the frame before,
and the layer it writes is read by this frame's sensors. So the crossing between samples
s[k-1] and s[k] (end-of-frame positions) is acted on at the start of frame k+1, and shows in
sample s[k+1]. "Frame" here is a GAME TICK: the samples are one emulator frame apart, a lag
frame repeats the previous tick, and the grade keeps one sample per Logic_Tick
(engine/ram.emp) so a lag frame cannot shift the prediction by one. The in-air test uses the status at that moment, i.e. s[k]'s. A step longer
than the physics cap (PHYS_GSP_CAP >> 8 px on either axis) crosses nothing, as in the routine.
Rows fire in table order and the last write stands.

THE START POINTS are the two sides of the loop the drives have always used
(docs/witness/loop-leftward-speed-sweep-2026-09-05.json and loop-rolling-circuit-2026-09-05.json:
x 1000 rightward, x 1350 leftward). THE START HEIGHT IS DERIVED from the committed editor
collision (plane A, the words the bake reads, the S&K shape bank), never typed: the old
START_Y = 553 went stale twice as the paint moved and left this tool at a declared setup red
("THE PLAYER NEVER LANDED") from 2026-09-06 to 2026-09-26. The grounded assertion stays.

THE DRIVE ORDER IS LOAD-BEARING (each of these cost an evening):
  * leave debug free flight with a real B PRESS (the DEBUG shape starts in it, and free flight
    skips the whole player preamble), never by writing debug_flag — the write skips
    Player_DebugExit and crashes in RefreshSpritePieceCount;
  * set the CAMERA first and let streaming settle, THEN place the player. The reverse order
    drops him through ground the collision cache does not cover yet;
  * let the camera FOLLOW afterwards.

EXIT: 0 every drive ran to its end and, where the ROM has a line table, every frame agreed
with the prediction and at least one row was crossed; 1 the ROM FAULTED (before or during a
drive), the player never landed, or a frame disagreed; 2 COULD NOT GRADE (the ROM's act binds
no layer-line table, or no drive crossed a row), printed with the traces so a before/after
comparison still reads them.

Usage:
    loop_step_over_witness.py --rom s4.debug.bin --lst s4.debug.lst
    loop_step_over_witness.py --rom A.bin --lst A.lst --compare B.bin B.lst   (A/B, per frame)
    loop_step_over_witness.py ... --dir right --gsp 0x900 -v
    loop_step_over_witness.py ... --phase-sweep
"""

import argparse
import asyncio
import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path, harness_path      # noqa: E402
sys.path.insert(0, str(harness_path()))
add_client_path()
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402

# The SST field offsets and the player slot come from the LISTING, never from here. This is
# the set every importer of parse_lst needs (Bus users elsewhere in tools/); the extra names
# this witness grades with are checked in main().
NEED_SYMS = ("Player_1", "Camera_X", "Camera_Y")
NEED_EQUS = ("SST_x_pos", "SST_y_pos", "SST_layer", "SST_angle",
             "PHYS_TOP_SPEED", "PHYS_GSP_CAP", "COLL_CELL_W")
GRADE_SYMS = ("Current_Act_Ptr", "Logic_Tick")
GRADE_EQUS = ("SST_art_tile", "SST_status", "SST_y_vel", "ST_IN_AIR", "Act_act_layer_lines",
              "LL_ROW", "LL_A_OFF", "LL_B_OFF", "LL_FLAGS_OFF", "LL_KEY_AFTER",
              "LL_KEEP_PATH", "LL_GROUNDED", "LL_HORIZONTAL", "LL_FWD_B", "LL_BACK_B",
              "LL_FWD_HI", "LL_BACK_HI", "LAYER_PATH_A", "LAYER_PATH_B",
              "PSTATE_GROUND", "PSTATE_ROLL", "PLAYER_Y_RADIUS")
# PlayerV overlays Sst.sst_custom = $30; ground_speed is the first field of the overlay,
# player_state the third byte, debug_flag +$C. They are `.emp` struct fields rather than EQU
# lines, so they are the numbers this file states, and it says so.
PLAYERV_GROUND_SPEED = 0x30
PLAYERV_STATE = 0x32
PLAYERV_DEBUG_FLAG = 0x3C
ART_PRIO = 0x8000                     # the VDP sprite attribute word's priority bit

#: The drives: the loop's two sides (see the header), the direction held, and the sign of
#: the injected ground speed.
DRIVES = {"right": {"x": 1000, "button": "right", "sign": 1},
          "left": {"x": 1350, "button": "left", "sign": -1}}
#: The loop's floor: the top of the 16 px floor row its arcs stand on (editor rows 72-73,
#: measured 2026-09-26 from section_0.collattr{,b}.bin, and the "ground_solid_y" of
#: docs/loop-arc-cells-section0.json). A REFERENCE for choosing among a column's surfaces,
#: not the placement: the placement is the surface ground_feet() finds nearest to it.
LOOP_FLOOR_Y = 576
FLOOR_SLACK = 32
EDITOR_ACT = REPO / "games" / "sonic4" / "data" / "editor" / "ojz" / "act1"
SHAPE_BANK = REPO / "games" / "sonic4" / "data" / "collision" / "base" / "heightmaps.bin"
SETTLE_FRAMES = 40                    # camera set -> streaming covers the player
PIN_FRAMES = 8                        # placed and held: y_vel 0, ground speed 0
LAND_FRAMES = 8                       # released -> feet on the ground, before injection


def parse_lst(path, extra_syms=(), extra_equs=()):
    import re
    sym_re = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
    equ_re = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = sym_re.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = equ_re.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    missing = [n for n in NEED_SYMS + tuple(extra_syms) if n not in syms] + \
              [n for n in NEED_EQUS + tuple(extra_equs) if n not in equs]
    if missing:
        raise SystemExit("loop_step_over_witness: %s carries no %s" % (path, ", ".join(missing)))
    return syms, equs


def ground_feet(x, clearance, act_dir=EDITOR_ACT, bank=SHAPE_BANK):
    """The loop's floor under world column x: of the top-solid surfaces in the column on plane A
    with at least `clearance` px of air above them (a standing player fits), the one nearest
    LOOP_FLOOR_Y, from the committed editor collision the bake reads. The column also holds the
    loop's arcs, a canopy left of it and a lower floor 272 px down, so "the first surface" and
    "the lowest surface" both pick the wrong one; the nearest to the loop's floor survives the
    paint moving it by a few pixels, which is how the old typed START_Y broke. A per-plane cell word's low 10 bits index the S&K shape bank,
    bits 11:10 are its flips and bits 13:12 its solidity (tools/collision_pipeline
    bake_plane_cell); the bake samples the TOP tile row of each 16 px collision row
    (tools/ojz_strip_gen.py), so this does too."""
    import collision_pipeline as cp
    sec = 256 * 8                                    # section px: 256 cells of 8 px
    if not (0 <= x < sec):
        raise SystemExit("loop_step_over_witness: x %d is outside section 0" % x)
    raw = (pathlib.Path(act_dir) / "section_0.collattr.bin").read_bytes()
    words = [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw), 2)]
    hm = pathlib.Path(bank).read_bytes()
    n = cp.PROFILE_LEN

    def solid(y):
        w = words[(y // 16 * 2) * 256 + x // 8]
        shape = w & cp.BLOCK_ID_MASK
        if not shape or not ((w >> cp.PLANE_SOL_SHIFT) & cp.SOL_TOP):
            return False
        h = hm[shape * n:(shape + 1) * n]
        if w & cp.CHUNK_XFLIP_BIT:
            h = cp.flip_profile_x(h)
        if w & cp.CHUNK_YFLIP_BIT:
            h = cp.flip_profile_y(h)
        return cp.covers(h[x % 16], y % 16)

    col = [solid(y) for y in range(sec)]
    floors = [y for y in range(clearance, sec)
              if col[y] and not any(col[y - clearance:y])]
    if not floors:
        raise SystemExit("loop_step_over_witness: no plane-A floor with %d px of air above it "
                         "under x=%d" % (clearance, x))
    near = min(floors, key=lambda y: abs(y - LOOP_FLOOR_Y))
    if abs(near - LOOP_FLOOR_Y) > FLOOR_SLACK:
        raise SystemExit("loop_step_over_witness: no plane-A floor within %d px of the loop's "
                         "floor (y %d) under x=%d; its standing surfaces are %s. The paint "
                         "moved: re-derive LOOP_FLOOR_Y." % (FLOOR_SLACK, LOOP_FLOOR_Y, x, floors))
    return near


class Bus:
    """Thin wrapper: 24-bit addresses, and every step checks for a fault handler."""

    def __init__(self, client):
        self.b = client

    async def read(self, addr, n):
        r = await self.b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = r["bytes"]
        s = s[2:] if s[:2].lower() == "0x" else s
        return bytes.fromhex(s)

    async def write(self, addr, value, width):
        return await self.b.call("emulator/write_memory",
                                 {"addr": hex(addr & 0xFFFFFF), "value": value, "width": width})

    async def frames(self, n):
        return await self.b.call("emulator/run_frames", {"frames": n})

    async def status(self):
        return await self.b.call("emulator/status", {})

    async def check_alive(self, where):
        st = await self.status()
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym or "ErrorHandlerBlob" in sym:
            raise SystemExit("loop_step_over_witness: the ROM FAULTED during %s — "
                             "symbolAtPc=%r pc=%s. Every number after this point would "
                             "be from a halted machine." % (where, sym, st.get("pc")))
        return st


def _s16(v):
    return v - 0x10000 if v >= 0x8000 else v


async def drive(sock, syms, equs, gsp, frames, verbose, start_dx=0, direction="right",
                assert_grounded=True):
    """One drive. Returns {"rows": [...], "table": [...] or None, "start": (x, feet)}."""
    d = DRIVES[direction]
    x0 = d["x"] + start_dx
    radius = equs["PLAYER_Y_RADIUS"]
    feet = ground_feet(x0, 2 * radius + 1)
    client = BusClient(socket_path=sock, client_id="lsow", client_name="loop-step-over")
    await client.connect()
    b = Bus(client)
    try:
        P = syms["Player_1"]
        A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
        A_LAYER, A_ANGLE = P + equs["SST_layer"], P + equs["SST_angle"]
        A_YVEL, A_ART = P + equs["SST_y_vel"], P + equs["SST_art_tile"]
        A_STATUS = P + equs["SST_status"]
        A_GSP, A_DBG, A_STATE = (P + PLAYERV_GROUND_SPEED, P + PLAYERV_DEBUG_FLAG,
                                 P + PLAYERV_STATE)
        air_bit = 1 << equs["ST_IN_AIR"]
        grounded = {equs["PSTATE_GROUND"], equs["PSTATE_ROLL"]}

        await client.call("emulator/reset", {})
        await b.frames(240)
        await b.check_alive("boot")

        # 1. leave debug free flight with a REAL press (never by writing debug_flag)
        if (await b.read(A_DBG, 1))[0]:
            await client.call("emulator/press", {"buttons": ["b"]})
            await b.frames(4)
        if (await b.read(A_DBG, 1))[0]:
            raise SystemExit("loop_step_over_witness: still in debug free flight after the "
                             "B press; the player preamble (and the lines) would never run")
        await b.check_alive("debug-fly exit")

        # 2. camera FIRST, then let streaming settle
        await b.write(syms["Camera_X"], (x0 - 160) << 16, 4)
        await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
        await b.frames(SETTLE_FRAMES)
        await b.check_alive("streaming settle")

        # 3. place the player just above the derived ground and hold him there, then let
        #    him land. An injection before the landing is erased by the landing frame.
        for _ in range(PIN_FRAMES):
            await b.write(A_X, x0 << 16, 4)
            await b.write(A_Y, (feet - radius - 2) << 16, 4)
            await b.write(A_YVEL, 0, 2)
            await b.write(A_GSP, 0, 2)
            await b.frames(1)
        await b.frames(LAND_FRAMES)
        await b.check_alive("placement")

        # 3b. THE PRECONDITION, ASSERTED RATHER THAN ASSUMED: a player who never landed is not
        #     riding anything, and his run has the signature of a missed layer change.
        state = (await b.read(A_STATE, 1))[0]
        yv = _s16(int.from_bytes(await b.read(A_YVEL, 2), "big"))
        landed_y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
        if assert_grounded and (state not in grounded or yv != 0):
            raise SystemExit(
                "loop_step_over_witness: THE PLAYER NEVER LANDED, so this run cannot say "
                "anything about the loop.\n  placed at (%d, %d) over plane-A ground at y %d "
                "(derived from %s); after %d landing frames he is at y=%d, y_vel=%d, "
                "player_state=%d (want a grounded state and y_vel 0). This is a SETUP "
                "failure, not a loop result. --no-assert-grounded runs anyway."
                % (x0, feet - radius - 2, feet, EDITOR_ACT.relative_to(REPO), LAND_FRAMES,
                   landed_y, yv, state))

        # 4. the act's layer-line table, out of the RUNNING ROM (the pointer the routine uses)
        act = int.from_bytes(await b.read(syms["Current_Act_Ptr"], 4), "big")
        tptr = int.from_bytes(await b.read(act + equs["Act_act_layer_lines"], 4), "big")
        table = None
        if tptr:
            table, a = [], tptr + equs["LL_ROW"]          # past the leading sentinel
            while True:
                raw = await b.read(a, equs["LL_ROW"])
                key = int.from_bytes(raw[0:2], "big")
                if key == equs["LL_KEY_AFTER"]:
                    break
                table.append({"key": _s16(key),
                              "a": _s16(int.from_bytes(raw[equs["LL_A_OFF"]:][:2], "big")),
                              "b": _s16(int.from_bytes(raw[equs["LL_B_OFF"]:][:2], "big")),
                              "flags": raw[equs["LL_FLAGS_OFF"]]})
                a += equs["LL_ROW"]
                if len(table) > 4096:
                    raise SystemExit("loop_step_over_witness: no trailing sentinel within "
                                     "4096 rows of $%06X" % tptr)

        # 5. hold the direction and inject the ground speed ONCE
        await client.call("emulator/hold", {"buttons": [d["button"]], "down": True})
        await b.write(A_GSP, (d["sign"] * gsp) & 0xFFFF, 2)

        # 6. one frame at a time: at 9 px/frame a player crosses an 8 px cell in under one
        #    frame, so any coarser interval cannot resolve a layer change even in principle.
        rows = []
        A_TICK = syms["Logic_Tick"]

        async def sample(f):
            x = int.from_bytes(await b.read(A_X, 4), "big") >> 16
            y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
            art = int.from_bytes(await b.read(A_ART, 2), "big")
            return {"frame": f, "x": x, "y": y, "layer": (await b.read(A_LAYER, 1))[0],
                    "prio": 1 if art & ART_PRIO else 0,
                    "air": 1 if (await b.read(A_STATUS, 1))[0] & air_bit else 0,
                    "angle": (await b.read(A_ANGLE, 1))[0],
                    "gsp": _s16(int.from_bytes(await b.read(A_GSP, 2), "big")),
                    "tick": int.from_bytes(await b.read(A_TICK, 4), "big")}

        rows.append(await sample(-1))                    # the landed state, before frame 0
        for f in range(frames):
            await b.frames(1)
            st = await b.status()
            sym = st.get("symbolAtPc") or ""
            if "ErrorHandler" in sym:
                rows.append({"frame": f, "fault": sym, "pc": st.get("pc")})
                break
            rows.append(await sample(f))
        await client.call("emulator/hold", {"buttons": [d["button"]], "down": False})
        return {"rows": rows, "table": table, "start": (x0, feet)}
    finally:
        await client.close()


def predict(rows, table, equs):
    """Per frame, what Obj03's rule over `table` says layer and priority must be, from the
    drive's own positions (the header's PREDICTION paragraph). Returns
    (mismatches, fires): mismatches as (frame, want (layer, prio), got (layer, prio), why);
    fires as (frame, row index, direction)."""
    live = []
    for r in rows:
        # One sample per GAME TICK: a lag frame repeats the previous tick's state, and the
        # routine's one-tick lag is a lag in ticks, not in emulator frames.
        if "layer" in r and not (live and r.get("tick") is not None
                                 and r.get("tick") == live[-1].get("tick")):
            live.append(r)
    step = equs["PHYS_GSP_CAP"] >> 8
    bit = {n: 1 << equs[n] for n in ("LL_KEEP_PATH", "LL_GROUNDED", "LL_HORIZONTAL",
                                     "LL_FWD_B", "LL_BACK_B", "LL_FWD_HI", "LL_BACK_HI")}
    bad, fires = [], []
    for k in range(1, len(live) - 1):
        p, c, nxt = live[k - 1], live[k], live[k + 1]
        layer, prio = c["layer"], c["prio"]
        why = []
        if abs(c["x"] - p["x"]) <= step and abs(c["y"] - p["y"]) <= step:
            for i, r in enumerate(table):
                f = r["flags"]
                if f & bit["LL_HORIZONTAL"]:
                    if not (r["key"] <= c["x"] < r["b"]):
                        continue
                    fwd, back = p["y"] < r["a"] <= c["y"], c["y"] < r["a"] <= p["y"]
                else:
                    if not (r["a"] <= c["y"] < r["b"]):
                        continue
                    fwd, back = p["x"] < r["key"] <= c["x"], c["x"] < r["key"] <= p["x"]
                if not (fwd or back):
                    continue
                if f & bit["LL_GROUNDED"] and c["air"]:
                    continue
                if not f & bit["LL_KEEP_PATH"]:
                    to_b = f & (bit["LL_FWD_B"] if fwd else bit["LL_BACK_B"])
                    layer = equs["LAYER_PATH_B"] if to_b else equs["LAYER_PATH_A"]
                prio = 1 if f & (bit["LL_FWD_HI"] if fwd else bit["LL_BACK_HI"]) else 0
                fires.append((nxt["frame"], i, "fwd" if fwd else "back"))
                why.append("row %d (key %d) %s" % (i, r["key"], "fwd" if fwd else "back"))
        if (nxt["layer"], nxt["prio"]) != (layer, prio):
            bad.append((nxt["frame"], (layer, prio), (nxt["layer"], nxt["prio"]),
                        "; ".join(why) or "no row crossed"))
    return bad, fires


def summarise(res, gsp, equs, label, verbose, grade=True):
    rows = res["rows"]
    live = [r for r in rows if "layer" in r]
    faulted = [r for r in rows if "fault" in r]
    lp = [(r["layer"], r["prio"]) for r in live]
    changes = [(r["frame"], r["x"], r["y"], r["layer"], r["prio"])
               for a, r in zip(live, live[1:]) if (a["layer"], a["prio"]) != (r["layer"], r["prio"])]
    xs, ys = [r["x"] for r in live], [r["y"] for r in live]
    print("  %-14s gsp $%04X (%d px/frame), start (%d, feet %d): %d frames, x %d..%d, "
          "min y %d, end (%d, %d) layer %d prio %d"
          % (label, gsp, gsp >> 8, res["start"][0], res["start"][1], len(live), min(xs), max(xs),
             min(ys), xs[-1], ys[-1], lp[-1][0], lp[-1][1]))
    print("                 layer/priority changes (frame, x, y, layer, prio): %s" % changes)
    if faulted:
        print("                 FAULTED at frame %d: %s" % (faulted[0]["frame"], faulted[0]["fault"]))
    if verbose:
        for r in live:
            print("                   f%-4d x=%-5d y=%-5d layer=%d prio=%d air=%d angle=$%02X "
                  "gsp=%d" % (r["frame"], r["x"], r["y"], r["layer"], r["prio"], r["air"],
                              r["angle"], r["gsp"]))
    out = {"faulted": bool(faulted), "changes": changes, "graded": False, "bad": [],
           "fires": 0,
           "trace": [[r["frame"], r["x"], r["y"], r["layer"], r["prio"], r["air"],
                      r.get("tick")] for r in live]}
    if grade and res["table"] is not None and not faulted:
        bad, fires = predict(rows, res["table"], equs)
        out.update(graded=True, bad=bad, fires=len(fires))
        print("                 GRADE over the ROM's %d-row table: %d crossing(s) fired, "
              "%d frame(s) disagree" % (len(res["table"]), len(fires), len(bad)))
        for fr, want, got, why in bad[:8]:
            print("                   DISAGREE f%d: want (layer, prio) %s, ROM has %s  [%s]"
                  % (fr, want, got, why))
    elif grade and res["table"] is None:
        print("                 NOT GRADED: this ROM's act binds no layer-line table")
    return out


def run_one(rom, lst, gsp, frames, verbose, label, start_dx=0, direction="right",
            assert_grounded=True, grade=True):
    syms, equs = parse_lst(lst, GRADE_SYMS, GRADE_EQUS)
    with aether_emulator(rom, symbols=lst) as sock:
        res = asyncio.run(drive(sock, syms, equs, gsp, frames, verbose, start_dx, direction,
                                assert_grounded))
    return summarise(res, gsp, equs, label, verbose, grade), equs


def compare(a, b):
    """Two traces of the same drive on two ROMs, compared per GAME TICK.

    Sampling is one EMULATOR frame apart, but a frame the game loop did not finish (a lag
    frame) repeats the previous tick's state, and two ROMs whose per-frame cost differs lag
    on different frames. So a per-frame comparison reports one-frame position "differences"
    that are only the two machines being a tick apart. The samples are therefore keyed by
    Logic_Tick (engine/ram.emp: the game loop's tick counter, lag-immune) and compared tick
    for tick. Returns {"frames": first per-frame (x, y) difference, "ticks": ticks both
    traces sampled, "pos": first tick whose (x, y) differ, "lp": first tick whose
    (layer, prio) differ, "lp_frames": first per-frame (layer, prio) difference}."""
    frames = next((ra[0] for ra, rb in zip(a["trace"], b["trace"]) if ra[1:3] != rb[1:3]),
                  None)
    lp_frames = next((ra[0] for ra, rb in zip(a["trace"], b["trace"]) if ra[3:5] != rb[3:5]),
                     None)
    ta = {r[6]: r for r in a["trace"]}
    tb = {r[6]: r for r in b["trace"]}
    common = sorted(set(ta) & set(tb))
    pos = next((t for t in common if ta[t][1:3] != tb[t][1:3]), None)
    lp = next((t for t in common if ta[t][3:5] != tb[t][3:5]), None)
    # A position difference confined to a sample or two that the following ticks no longer
    # show is a sample taken while one machine was still inside the tick (the two ROMs'
    # per-frame costs differ, so the emulator frame boundary lands at a different point of
    # the tick); two runs that had DIVERGED would not come back together. So the report is
    # the longest run of consecutive differing ticks and whether the traces end equal.
    differ = {t for t in common if ta[t][1:3] != tb[t][1:3]}
    run = best = 0
    for t in common:
        run = run + 1 if t in differ else 0
        best = max(best, run)
    return {"frames": frames, "lp_frames": lp_frames, "ticks": len(common), "pos": pos,
            "lp": lp, "pos_samples": len(differ), "pos_longest_run": best,
            "end_equal": bool(common) and ta[common[-1]][1:5] == tb[common[-1]][1:5]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--gsp", default=None,
                    help="ground speed to inject (hex ok). Default: the three derived "
                         "speeds PHYS_TOP_SPEED, the one-cell boundary, PHYS_GSP_CAP")
    ap.add_argument("--dir", choices=sorted(DRIVES), action="append", default=None,
                    help="drive direction (repeatable). Default: both")
    ap.add_argument("--compare", nargs=2, metavar=("ROM", "LST"),
                    help="a second build to run the identical drives against, reported per "
                         "frame beside the first (the before/after comparison)")
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--start-dx", type=int, default=0,
                    help="shift the start X by this many pixels")
    ap.add_argument("--no-assert-grounded", action="store_true",
                    help="run even when the player did not land after the placement")
    ap.add_argument("--phase-sweep", action="store_true",
                    help="at the cap (or --gsp), sweep start-dx over one COLL_CELL_W stride "
                         "in each direction: the sub-cell phase decided a painted mark's "
                         "step-over, so it is the variable a line must be indifferent to")
    ap.add_argument("--json", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    syms, equs = parse_lst(args.lst, GRADE_SYMS, GRADE_EQUS)
    speeds = ([int(args.gsp, 0)] if args.gsp else
              [equs["PHYS_TOP_SPEED"], (equs["COLL_CELL_W"] + 1) << 8, equs["PHYS_GSP_CAP"]])
    dirs = args.dir or ["right", "left"]
    runs = []
    if args.phase_sweep:
        cw = equs["COLL_CELL_W"]
        gsp = speeds[-1]
        print("PHASE SWEEP at gsp $%04X (%d px/frame against a %d px cell), start X shifted "
              "0..%d px" % (gsp, gsp >> 8, cw, cw - 1))
        plan = [(dr, gsp, dx) for dr in dirs for dx in range(cw)]
    else:
        plan = [(dr, gsp, args.start_dx) for dr in dirs for gsp in speeds]
    for dr, gsp, dx in plan:
        print("=" * 78)
        lab = "%s dx%+d" % (dr, dx)
        r, _ = run_one(args.rom, args.lst, gsp, args.frames, args.verbose,
                       "%s %s" % (pathlib.Path(args.rom).name, lab), dx, dr,
                       not args.no_assert_grounded)
        entry = {"dir": dr, "gsp": gsp, "dx": dx, "subject": r}
        if args.compare:
            c, _ = run_one(args.compare[0], args.compare[1], gsp, args.frames, args.verbose,
                           "%s %s" % (pathlib.Path(args.compare[0]).name, lab), dx, dr,
                           not args.no_assert_grounded)
            cmp = compare(r, c)
            print("  COMPARE per game tick (%d ticks both sampled): layer/priority first differ "
                  "at tick %s; positions differ on %d sample(s) (first tick %s, longest run "
                  "%d tick(s)); final state %s.  Per emulator frame: positions first differ "
                  "at %s, layer/priority at %s"
                  % (cmp["ticks"], cmp["lp"], cmp["pos_samples"], cmp["pos"],
                     cmp["pos_longest_run"], "EQUAL" if cmp["end_equal"] else "DIFFERENT",
                     cmp["frames"], cmp["lp_frames"]))
            entry["control"] = c
            entry["compare"] = cmp
        runs.append(entry)
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(runs, indent=1) + "\n")
        print("wrote %s" % args.json)
    return verdict([("%s gsp $%04X dx%+d %s" % (e["dir"], e["gsp"], e["dx"], side), e[side])
                    for e in runs for side in ("subject", "control") if side in e])


def verdict(runs):
    """0 / 1 / 2 as the header's EXIT paragraph says. `runs` is [(label, summary dict)].

    A drive that reached ErrorHandler is never a clean exit (KEEPALIVE-IS-BLIND-TO-LOSSY,
    2026-09-25): the same tool treats a fault before the drive as fatal (check_alive)."""
    faulted = [lab for lab, r in runs if r.get("faulted")]
    bad = [lab for lab, r in runs if r.get("bad")]
    if faulted or bad:
        if faulted:
            print("RESULT: the ROM FAULTED during %d drive(s): %s. The traces above are from a "
                  "machine that stopped; this run is not a completed witness."
                  % (len(faulted), ", ".join(faulted)))
        if bad:
            print("RESULT: FAILED — the ROM's layer or priority disagreed with its own line table "
                  "in %d drive(s): %s" % (len(bad), ", ".join(bad)))
        return 1
    graded = [r for _lab, r in runs if r.get("graded")]
    if not graded or not sum(r["fires"] for r in graded):
        print("RESULT: COULD NOT GRADE — %s. The traces above are reported, not graded."
              % ("no drive's ROM binds a layer-line table" if not graded else
                 "no drive crossed a row of the table"))
        return 2
    print("RESULT: PASSED — %d drive(s) graded, %d crossing(s) fired, every frame agreed with "
          "the ROM's own table" % (len(graded), sum(r["fires"] for r in graded)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
