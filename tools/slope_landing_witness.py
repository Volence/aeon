#!/usr/bin/env python3
"""slope_landing_witness — does a player who FALLS onto a steep slope take the slope's angle?

SONIC-SLOPE-COLLISION (owner, 2026-09-26: "I can stand on random things or don't just start
rolling when I try to", on the Sonic 2 clip act). The cause was measured, not guessed: the
two air landings (`Air_FloorLandBanded` / `Air_FloorLandFlat`) read the floor through the
GROUNDED sensor wrapper, whose angle policy (S2 `Sonic_Angle`, S3K `Player_Angle`) rejects a
surface angle more than $20 from the player's current angle. In the air that angle has
decayed to 0, so a landing on any surface of $20 or steeper was converted as a landing on
FLAT ground (angle 0, flat band, gsp = x_vel) and the player stood still on the slope, for
good. Both classics land through `Sonic_CheckFloor` instead (nearer sensor's angle raw, odd
flag -> 0 only). docs/research/2026-09-26-sonic-slope-collision.md has the measurements.

THE SUBJECTS ARE DERIVED FROM THE COMMITTED LEVEL, never typed here. The committed act's
plane-A collision (the same `sec*_strips_a.bin` + interned attr tables the ROM embeds, read
through tools/collision_consistency.py's loaders) is scanned for EXPOSED top-surface blocks
(top-solid, nothing top-solid in the block above) whose floor angle is in the landing code's
STEEP band -- `(angle + $20) & $40` nonzero, the exact test `Air_FloorLandBanded` makes --
with open air above both foot sensors for the whole drop. On the shipped OJZ act that is ONE
block (measured 2026-09-26: x 1072..1087, row y 528, angle $20; the Sonic 2 clip act has 58).

TWO LEGS, and the second is what makes the first a measurement:

  L1 STEEP  drop the standing player, x_vel 0, from DROP_PX above each subject's surface.
            On the first grounded frame his angle must be in the steep band with the
            SUBJECT'S SIGN, his ground speed non-zero and DOWNHILL (a positive angle
            descends rightward, so gsp > 0), and SETTLE_FRAMES later he must have moved
            downhill. The defect this was built for reads angle $00, gsp 0, x unchanged.
  C1 FLAT   the same drop onto a derived FLAT exposed block (angle $00 or the odd
            sentinel under both sensors). He must land with angle $00, gsp 0, and stay
            put. Without it L1 cannot tell "the landing reads the slope" from "this
            harness never sees an angle of 0", and a drive that always reported motion
            would pass L1 vacuously.

Exit: 0 every leg passed; 1 a leg FAILED (a measured wrong landing); 2 COULD NOT RUN (no
subject in the level, the player never landed, the ROM faulted, free flight would not
release, the landing happened on the wrong layer). Never 0 on an empty population.

RED-FIRST, measured 2026-09-26: with `Air_FloorLandBanded` pointed back at
`Player_SensorFloor` (the pre-fix code, committed baseline 91d4119c) L1 FAILS on the one OJZ
subject (landed angle $00, gsp 0) and C1 passes; on the fix both pass.

    python3 tools/slope_landing_witness.py --rom s4.debug.bin --lst s4.debug.lst
"""
import argparse
import asyncio
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import collision_consistency as CC                         # noqa: E402
import ojz_block_gen                                       # noqa: E402
import loop_step_over_witness as L                         # noqa: E402
from emp_consts import emp_consts                          # noqa: E402
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402

ACT_GRID = REPO / "games/sonic4/data/generated/ojz/act1/act_grid.emp"
PL_STATE_OFF = 0x32          # PlayerV.player_state (engine/level/camera.emp PL_STATE_OFF)
DROP_PX = 48                 # feet this far above the surface when released
PIN_FRAMES = 240             # camera + player held while streaming settles
LAND_WITHIN = 90             # a 48-px fall from rest lands in ~24 frames at 60 Hz
SETTLE_FRAMES = 12           # frames after landing over which "moved downhill" is read


class Unmeasurable(Exception):
    pass


def steep(a):
    """Air_FloorLandBanded's steep band: (a + $20) & $40, on a usable (even) angle."""
    return (a & 1) == 0 and (((a + 0x20) & 0xFF) & 0x40) != 0


def flat(a):
    return a == 0 or (a & 1) == 1


def load_act(solid_top):
    grid_w = emp_consts(ACT_GRID).get("OJZ_ACT_GRID_W")
    if not grid_w:
        raise Unmeasurable(f"no OJZ_ACT_GRID_W in {ACT_GRID}")
    heights, angles, solidity = CC.load_attr_tables()
    secs = CC.enumerate_sections()
    if not secs:
        raise Unmeasurable("no committed sec*_strips_a.bin: zero collision cells to scan")
    planes = []
    for sec, path in secs:
        _nt, ca, _cb = ojz_block_gen.parse_strips(open(path, "rb").read())
        ox = (sec % grid_w) * len(ca[0]) * CC.CELL_PX_W
        oy = (sec // grid_w) * len(ca) * CC.CELL_PX_H
        planes.append((ox, oy, ca, CC.CollisionPlane(ca, heights, solidity)))
    return planes, angles, solidity


def surface_y(plane, lx, ly_from, solid_top):
    for y in range(ly_from, ly_from + 64):
        if plane.pixel_solid(lx, y, solid_top):
            return y
    return None


def subjects(planes, angles, solidity, solid_top, x_rad):
    """(steep, flat): exposed top blocks as (world_x_centre, world_surface_y, angle)."""
    steep_out, flat_out = [], []
    for ox, oy, ca, pl in planes:
        for row in range(1, len(ca)):
            for col in range(0, len(ca[0]) - 1, 2):          # a 16-px block = 2 cells
                a = ca[row][col]
                if not a or not (solidity[a] & solid_top):
                    continue
                up = ca[row - 1][col]
                if up and (solidity[up] & solid_top):
                    continue
                ang = angles[a]
                lx = col * CC.CELL_PX_W + 8
                ly0 = row * CC.CELL_PX_H
                sy = surface_y(pl, lx, ly0, solid_top)
                if sy is None:
                    continue
                # both foot columns must be open for the whole drop
                clear = all(not pl.pixel_solid(fx, y, solid_top) and
                            not pl.pixel_solid(fx, y, 0xFF)
                            for fx in (lx - x_rad, lx, lx + x_rad)
                            for y in range(max(0, sy - DROP_PX - 40), sy - 16))
                if not clear:
                    continue
                if steep(ang):
                    steep_out.append((ox + lx, oy + sy, ang))
                elif flat(ang):
                    # flat control: the neighbours under both sensors must be flat too
                    nb = [ca[row][c] for c in (col - 2, col + 2) if 0 <= c < len(ca[0])]
                    open_to_surface = all(not pl.pixel_solid(fx, y, 0xFF)
                                          for fx in (lx - x_rad, lx, lx + x_rad)
                                          for y in range(max(0, sy - DROP_PX - 40), sy))
                    if len(nb) == 2 and open_to_surface and all(
                            n and flat(angles[n]) and (solidity[n] & solid_top)
                            for n in nb):
                        flat_out.append((ox + lx, oy + sy, ang))
    return steep_out, flat_out


async def drop(sock, syms, equs, x, surface, grounded):
    client = BusClient(socket_path=sock, client_id="slw", client_name="slope-landing")
    await client.connect()
    b = L.Bus(client)
    try:
        P = syms["Player_1"]
        A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
        A_XV, A_YV = P + equs["SST_x_vel"], P + equs["SST_y_vel"]
        A_ANG, A_LAY = P + equs["SST_angle"], P + equs["SST_layer"]
        A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
        A_ST = P + PL_STATE_OFF
        radius = equs["PLAYER_Y_RADIUS"]
        await client.call("emulator/reset", {})
        await b.frames(240)
        await b.check_alive("boot")
        if (await b.read(A_DBG, 1))[0]:
            await client.call("emulator/press", {"buttons": ["b"]})
            await b.frames(4)
        if (await b.read(A_DBG, 1))[0]:
            raise Unmeasurable("debug free-flight did not release on a B press")
        start_y = surface - DROP_PX - radius
        await b.write(syms["Camera_X"], max(0, x - 160) << 16, 4)
        await b.write(syms["Camera_Y"], max(0, start_y - 112) << 16, 4)
        for _ in range(PIN_FRAMES):
            await b.write(A_X, x << 16, 4)
            await b.write(A_Y, start_y << 16, 4)
            await b.write(A_XV, 0, 2)
            await b.write(A_YV, 0, 2)
            await b.write(A_GSP, 0, 2)
            await b.frames(1)

        async def row():
            st = await b.status()
            if "ErrorHandler" in (st.get("symbolAtPc") or ""):
                raise Unmeasurable(f"the ROM FAULTED ({st.get('symbolAtPc')})")
            g = int.from_bytes(await b.read(A_GSP, 2), "big")
            return {"x": int.from_bytes(await b.read(A_X, 4), "big") >> 16,
                    "y": int.from_bytes(await b.read(A_Y, 4), "big") >> 16,
                    "gsp": g - 0x10000 if g >= 0x8000 else g,
                    "ang": (await b.read(A_ANG, 1))[0],
                    "layer": (await b.read(A_LAY, 1))[0],
                    "state": (await b.read(A_ST, 1))[0]}
        land = None
        for f in range(LAND_WITHIN):
            await b.frames(1)
            r = await row()
            if r["state"] in grounded:
                land = dict(r, frame=f)
                break
        if land is None:
            raise Unmeasurable(f"the player dropped at x={x} never landed within "
                               f"{LAND_WITHIN} frames (surface y {surface})")
        await b.frames(SETTLE_FRAMES)
        after = await row()
        return land, after
    finally:
        await client.close()


def grade_steep(subj, land, after):
    x, sy, ang = subj
    fails = []
    down = 1 if ang < 0x80 else -1          # positive angle descends rightward
    if not steep(land["ang"]) or (land["ang"] < 0x80) != (ang < 0x80):
        fails.append(f"landed with angle ${land['ang']:02X}; the surface is ${ang:02X} "
                     f"(steep band, sign {'+' if down > 0 else '-'})")
    if land["gsp"] * down <= 0:
        fails.append(f"ground speed on landing {land['gsp']} is not downhill "
                     f"({'+' if down > 0 else '-'})")
    if (after["x"] - land["x"]) * down <= 0:
        fails.append(f"{SETTLE_FRAMES} frames after landing x went {land['x']} -> "
                     f"{after['x']}: not downhill")
    return fails


def grade_flat(subj, land, after):
    fails = []
    if land["ang"] != 0:
        fails.append(f"landed on flat ground with angle ${land['ang']:02X}")
    if land["gsp"] != 0 or after["x"] != land["x"]:
        fails.append(f"a vertical drop onto flat ground moved: gsp {land['gsp']}, x "
                     f"{land['x']} -> {after['x']}")
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--max-subjects", type=int, default=4,
                    help="steep subjects driven (each is one emulator boot)")
    args = ap.parse_args(argv)
    try:
        syms, equs = L.parse_lst(args.lst)
        for n in ("PLAYER_Y_RADIUS", "PLAYER_X_RADIUS", "PSTATE_GROUND", "PSTATE_ROLL",
                  "SST_x_vel"):
            if n not in equs:
                raise Unmeasurable(f"{args.lst} carries no EQU {n}")
        c = emp_consts(REPO / "engine/system/constants.emp")
        solid_top = c.get("SOLID_TOP")
        if solid_top is None:
            raise Unmeasurable("SOLID_TOP not readable from engine/system/constants.emp")
        planes, angles, solidity = load_act(solid_top)
        st, fl = subjects(planes, angles, solidity, solid_top, equs["PLAYER_X_RADIUS"])
        print(f"slope_landing_witness: {len(st)} steep and {len(fl)} flat exposed "
              f"top blocks with a clear drop (plane A, committed act)")
        if not st:
            raise Unmeasurable("NO STEEP SUBJECT: the committed act has no exposed "
                               "steep top block with a clear drop, so L1 has nothing to "
                               "measure. Do not read this as a pass.")
        if not fl:
            raise Unmeasurable("NO FLAT CONTROL subject")
        grounded = {equs["PSTATE_GROUND"], equs["PSTATE_ROLL"]}
        legs = [("L1 STEEP", s, grade_steep) for s in st[:args.max_subjects]]
        # the flat control nearest the first steep subject: same neighbourhood, same
        # streaming, so the two legs differ in the surface under the feet
        # (ranked by distance, the vertical weighted x4 so a floor under the subject --
        # which the drop would have to fall through the slope to reach -- loses to one
        # beside it at the same height)
        legs.append(("C1 FLAT", min(fl, key=lambda f: abs(f[0] - st[0][0]) +
                                    4 * abs(f[1] - st[0][1])), grade_flat))
        failed = 0
        for name, subj, grade in legs:
            try:
                with aether_emulator(args.rom, symbols=args.lst) as sock:
                    land, after = asyncio.run(drop(sock, syms, equs, subj[0], subj[1],
                                                   grounded))
            except Unmeasurable:
                raise
            except Exception as e:          # a bus refusal is not a measurement
                raise Unmeasurable(f"{name}: the drive raised {type(e).__name__}: {e}")
            if land["layer"] != 0:
                raise Unmeasurable(f"{name}: landed on layer {land['layer']}, but the "
                                   f"subject was derived from plane A")
            fails = grade(subj, land, after)
            head = (f"  {name} x={subj[0]} surface y={subj[1]} angle ${subj[2]:02X}: "
                    f"landed f{land['frame']} angle ${land['ang']:02X} gsp {land['gsp']}, "
                    f"x {land['x']} -> {after['x']}")
            print(("FAILED" if fails else "passed") + head)
            for f_ in fails:
                print("         " + f_)
            failed += bool(fails)
        print(f"slope_landing_witness: {len(legs) - failed} of {len(legs)} legs passed")
        return 1 if failed else 0
    except Unmeasurable as e:
        print(f"slope_landing_witness: COULD NOT RUN: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
