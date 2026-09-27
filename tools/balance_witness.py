#!/usr/bin/env python3
"""balance_witness — does a standing player teeter exactly where Sonic 3K's balance rule says?

WHY IT EXISTS (WOVEN-FALSE-BALANCE, 2026-09-27). In the woven Sonic 2 act the owner stood on
flat grass in Emerald Hill, facing a 32-px step, and Sonic played the BALANCE animation (woven
(1609, 2829), anim 6, status $02). Player_AtLedgeEdge then probed ONE point at x - 11 (facing
left) and called anything more than 8 px down a ledge; x - 11 is inside the step's own column,
under the step, where Sonic 2 leaves no collision, so the probe read 32 ("nothing") while the
centre and both floor sensors stood on the floor. Sonic 2 (s2.asm:36322 Sonic_Balance /
:43674 ChkFloorEdge) and Sonic 3K (sonic3k.asm:22535) ask the CENTRE instead: balance when the
floor under x_pos is at least $C below the foot AND one floor sensor (x -/+ x_radius) found no
surface at all, then turn to face that side. The engine now runs that rule; this checks the
ROM against it.

WHAT IT DERIVES (never typed): the standing positions, from the collision the ROM was built
from, read as probe_core reads it (collision_consistency.CollisionPlane):
  * a clip act (--clip ID): its baked editor tree, games/sonic4/data/clips/<ID>/baked/
    section_N.collattr.bin (plane A cell words; a 16-px row samples the even tile row), resolved
    through the bank the clip's zones name (clip_manifest.collision_banks);
  * the canonical act (no --clip): the committed generated strips and interned attr tables
    (games/sonic4/data/generated/ojz/act1, games/sonic4/data/collision).
A position is STANDING when the floor pair (x -/+ PLAYER_X_RADIUS) reads 0 at the foot and the
body box holds no wall-class pixel. Two classes are graded, on plane A (the player is put on
layer 0):
  WALL   supported by S3K's rule (centre < BALANCE_DROP_MIN), facing a solid face whose column
         one foot-width + 2 ahead (x -/+ (PLAYER_X_RADIUS + 2)) is solid above the foot and holds
         nothing within 8 px below it: exactly where the old probe teetered. EXPECT: not ANIM_BALANCE.
  LEDGE  S3K's rule balances (collision_consistency.balances): EXPECT ANIM_BALANCE, and the
         player facing the side it names (placed facing AWAY, so the turn is observed).
Clusters of neighbouring positions are one spot; up to --per-class spots per class are taken,
spread over the act. --spot x,foot,face adds a named WALL row (the owner's sighting).

THE DRIVE (DEBUG shape: the warp mailbox): boot, a real B press to leave debug free flight
(the harness's default state IS the condition under test otherwise), then per spot: warp to
(x, foot - PLAYER_Y_RADIUS), pin there PIN frames, put him on layer 0 with the row's facing and
no ground speed, release, SETTLE frames, read anim / status / x / y. A spot where he did not
stay put (x or y moved) is UNMEASURED, counted and printed, never graded.

Exit 0 every graded spot matched; 1 one did not; 2 could not run (no ROM / symbol / warp
mailbox, the population empty, or fewer than half the spots measurable).

Usage:
    python3 tools/balance_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --clip s2_woven --spot 1609,2848,left
    python3 tools/balance_witness.py --rom s4.debug.bin --lst s4.debug.lst
Wired: tools/keepalive_manifest.toml (both). RED on the woven ROM before the fix (crc
65eac6c3): the owner's spot and the WALL rows teeter. GREEN after.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import struct
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))
import collision_consistency as cc  # noqa: E402

OLD_PROBE_EXTRA = 2        # the retired probe's reach past the foot (PLAYER_X_RADIUS + 2)
OLD_NO_GROUND = 8          # ... and its threshold: the WALL class is where THAT probe lied
PIN_FRAMES = 60
FLAT_PX = 8                # level floor this far past the supporting sensor (see classify)
SETTLE_FRAMES = 40
SECTION_PX = 2048


class CouldNotRun(Exception):
    pass


# ---------------------------------------------------------------------------
# The collision model: one plane-A CollisionPlane over the whole act
# ---------------------------------------------------------------------------

def _clip_plane(clip):
    import clip_manifest as CM
    import collision_pipeline as CP
    baked = AEON / "games" / "sonic4" / "data" / "clips" / clip / "baked"
    import json
    try:
        proj = json.loads((baked / "project.json").read_text())
        act = proj["zones"][0]["acts"][0]
        gw, gh = act["gridWidth"], act["gridHeight"]
    except (OSError, KeyError, ValueError) as e:
        raise CouldNotRun(f"no baked tree for clip {clip!r} at {baked} ({e}); build "
                          f"DEBUG=1 S2CLIP={clip} ./build.sh first")
    man = CM.load(str(AEON / "games" / "sonic4" / "data" / "clips" / clip / "clips.json"))
    hm, _an = CM._bank(CM.collision_banks(man))
    ncol, nrow = SECTION_PX // 8, SECTION_PX // 16
    intern, heights, solidity = {0: 0}, [[0] * 16], [0]
    rows = [[0] * (ncol * gw) for _ in range(nrow * gh)]
    for n in range(gw * gh):
        p = baked / f"section_{n}.collattr.bin"
        try:
            raw = p.read_bytes()
        except OSError as e:
            raise CouldNotRun(f"{p}: {e}")
        if len(raw) != ncol * ncol * 2:
            raise CouldNotRun(f"{p} is {len(raw)} B, not a {ncol}x{ncol} word grid")
        sx, sy = n % gw, n // gw
        for r in range(nrow):
            base = (2 * r) * ncol * 2            # the EVEN tile row carries the 16-px row
            out = rows[sy * nrow + r]
            for c in range(ncol):
                w = struct.unpack_from(">H", raw, base + c * 2)[0]
                a = intern.get(w)
                if a is None:
                    shape = w & CP.BLOCK_ID_MASK
                    sol = (w >> CP.PLANE_SOL_SHIFT) & 3
                    h = hm[shape * 16:(shape + 1) * 16] if shape and sol else bytes(16)
                    if w & CP.CHUNK_XFLIP_BIT:
                        h = CP.flip_profile_x(h)
                    if w & CP.CHUNK_YFLIP_BIT:
                        h = CP.flip_profile_y(h)
                    a = intern[w] = len(heights)
                    heights.append(list(h))
                    solidity.append(sol if shape else 0)
                out[sx * ncol + c] = a
    return cc.CollisionPlane(rows, heights, solidity), (gw * SECTION_PX, gh * SECTION_PX)


def _canonical_plane():
    import act_grid
    import ojz_block_gen as g
    gen = cc.gen_dir_for()
    try:
        heights, _angles, solidity = cc.load_attr_tables(cc.coll_dir_for())
        gw, gh = act_grid.descriptor_grid(os.path.join(gen, "act_grid.emp"))
    except Exception as e:  # noqa: BLE001 — every failure here is "could not measure"
        raise CouldNotRun(f"canonical collision unreadable: {e}")
    ncol, nrow = SECTION_PX // 8, SECTION_PX // 16
    rows = [[0] * (ncol * gw) for _ in range(nrow * gh)]
    for n in range(gw * gh):
        p = os.path.join(gen, f"sec{n}_strips_a.bin")
        if not os.path.isfile(p):
            continue
        _nt, a, _b = g.parse_strips(open(p, "rb").read())
        sx, sy = n % gw, n // gw
        for r in range(len(a)):
            rows[sy * nrow + r][sx * ncol:sx * ncol + len(a[r])] = a[r]
    return cc.CollisionPlane(rows, heights, solidity), (gw * SECTION_PX, gh * SECTION_PX)


# ---------------------------------------------------------------------------
# The population
# ---------------------------------------------------------------------------

def classify(plane, size, lp):
    """{"WALL": [(x, foot, face)], "LEDGE": [(x, foot, side)]} over every standing position."""
    top, lrb = lp["SOLID_TOP"], lp["SOLID_LRB"]
    xr, yr, drop = lp["PLAYER_X_RADIUS"], lp["PLAYER_Y_RADIUS"], lp["BALANCE_DROP_MIN"]
    reach = xr + OLD_PROBE_EXTRA
    w, h = size
    out = {"WALL": [], "LEDGE": []}
    tops = {}

    def column_tops(cx):
        """Every floor surface in column cx: a TOP-solid pixel with air above it."""
        if cx not in tops:
            t, prev = [], True
            for y in range(h):
                s = plane.pixel_solid(cx, y, top)
                if s and not prev:
                    t.append(y)
                prev = s
            tops[cx] = t
            tops.pop(cx - 2 * xr - 2, None)
        return tops[cx]

    def level(sx, foot, away):
        """Level floor under sensor column sx and FLAT_PX past it, away from the edge."""
        return all(plane.probe_down(sx + away * d, foot, top) == 0 for d in range(FLAT_PX + 1))

    for x in range(reach + FLAT_PX + 1, w - reach - FLAT_PX - 1):
        feet = set(column_tops(x - xr)) | set(column_tops(x + xr))
        for foot in sorted(feet):
            def flat(sx, away, foot=foot):
                return level(sx, foot, away)

            if min(plane.probe_down(x - xr, foot, top), plane.probe_down(x + xr, foot, top)) != 0:
                continue
            if any(plane.pixel_solid(xx, yy, lrb) for xx in (x - xr, x, x + xr)
                   for yy in range(foot - 2 * yr, foot)):
                continue
            side = cc.balances(plane, x, foot, top, xr, drop)
            if side:
                # the supporting sensor is the other one; FLAT under it, or a placed
                # player slides off before anything can be read (measured: 5 of 8)
                if flat(x + (-xr if side == "right" else xr), -1 if side == "right" else 1):
                    out["LEDGE"].append((x, foot, side))
                continue
            for face, dx in (("right", reach), ("left", -reach)):
                px = x + dx
                if plane.probe_down(px, foot, top) <= OLD_NO_GROUND:
                    continue
                if not flat(x - xr if face == "right" else x + xr,
                            -1 if face == "right" else 1):
                    continue
                if any(plane.pixel_solid(px, yy, top) or plane.pixel_solid(px, yy, lrb)
                       for yy in range(foot - 2 * yr, foot)):
                    out["WALL"].append((x, foot, face))
    return out


def spots(rows, per_class):
    """One spot per cluster (same foot and face, x consecutive), spread over the act."""
    clusters = []
    for x, foot, face in sorted(rows, key=lambda r: (r[1], r[2], r[0])):
        c = clusters[-1] if clusters else None
        if c and c[1] == foot and c[2] == face and x - c[3] <= 1:
            c[3] = x
        else:
            clusters.append([x, foot, face, x])
    clusters.sort(key=lambda c: (c[0], c[1]))
    picked = [((c[0] + c[3]) // 2, c[1], c[2]) for c in clusters]
    if len(picked) > per_class:
        step = len(picked) / per_class
        picked = [picked[int(i * step)] for i in range(per_class)]
    return picked, len(clusters)


# ---------------------------------------------------------------------------
# The drive
# ---------------------------------------------------------------------------

async def drive(sock, syms, equs, rows):
    from aether import BusClient
    import loop_step_over_witness as L
    import tunnel_run_witness as T
    b = BusClient(socket_path=sock, client_id="balw", client_name="balance_witness")
    await b.connect()
    bus = L.Bus(b)
    P = syms["Player_1"]
    A = {k: P + equs[f"SST_{k}"] for k in ("x_pos", "y_pos", "anim", "status", "layer")}
    flip = 1 << equs["ST_XFLIP"]
    out = []
    try:
        await bus.frames(240)
        await bus.check_alive("boot")
        if (await bus.read(P + L.PLAYERV_DEBUG_FLAG, 1))[0]:
            await b.call("emulator/press", {"buttons": ["b"]})
            await bus.frames(4)
        if (await bus.read(P + L.PLAYERV_DEBUG_FLAG, 1))[0]:
            raise CouldNotRun("the B press did not leave debug free flight")
        for cls, x, foot, face in rows:
            y = foot - equs["PLAYER_Y_RADIUS"]
            await T.place(b, bus, syms, x, y, frames=PIN_FRAMES)
            await bus.write(A["layer"], 0, 1)
            # LEDGE rows are placed facing AWAY from the edge the rule names, so the
            # turn to face it is observed; WALL rows face the wall (where the old probe lied)
            want_face = face if cls == "WALL" else ("left" if face == "right" else "right")
            st = (await bus.read(A["status"], 1))[0]
            st = (st | flip) if want_face == "left" else (st & ~flip)
            await bus.write(A["status"], st & 0xFF, 1)
            await bus.write(P + L.PLAYERV_GROUND_SPEED, 0, 2)
            await bus.frames(SETTLE_FRAMES)
            await bus.check_alive(f"spot ({x}, {foot})")
            px = int.from_bytes(await bus.read(A["x_pos"], 2), "big")
            py = int.from_bytes(await bus.read(A["y_pos"], 2), "big")
            anim = (await bus.read(A["anim"], 1))[0]
            st = (await bus.read(A["status"], 1))[0]
            out.append({"cls": cls, "x": x, "foot": foot, "face": face, "px": px, "py": py,
                        "anim": anim, "facing": "left" if st & flip else "right",
                        "layer": (await bus.read(A["layer"], 1))[0]})
    finally:
        await b.close()
    return out


def grade(r, equs):
    """None = matched, "UNMEASURED ..." = not graded, else the failure."""
    if (r["px"], r["py"]) != (r["x"], r["foot"] - equs["PLAYER_Y_RADIUS"]) or r["layer"] != 0:
        return f"UNMEASURED: did not stay put (at {r['px']},{r['py']} layer {r['layer']})"
    bal = r["anim"] == equs["ANIM_BALANCE"]
    if r["cls"] == "WALL":
        return f"TEETERED (anim {r['anim']}) with the centre supported" if bal else None
    if not bal:
        return f"did NOT teeter (anim {r['anim']}) over a {r['face']} edge S3K balances on"
    if r["facing"] != r["face"]:
        return f"teetered facing {r['facing']}, not the {r['face']} edge (S3K turns to face it)"
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--clip", help="a clip act id (its baked tree); default the canonical act")
    ap.add_argument("--spot", action="append", default=[],
                    help="x,foot,face: an extra named WALL row (must classify as WALL)")
    ap.add_argument("--per-class", type=int, default=8)
    a = ap.parse_args(argv)
    try:
        import loop_step_over_witness as L
        import region_music_witness as RMW
        import tunnel_run_witness as T
        if not os.path.isfile(a.rom) or not os.path.isfile(a.lst):
            raise CouldNotRun(f"{a.rom} / {a.lst} missing")
        syms, equs = L.parse_lst(a.lst)
        equs.update(RMW.parse_lst(a.lst)[1])
        T._EQUS.update(equs)
        for n in ("Warp_Req_Flag", "Player_1"):
            if n not in syms:
                raise CouldNotRun(f"{a.lst} carries no {n} (the DEBUG shape's warp mailbox)")
        for n in ("ANIM_BALANCE", "ST_XFLIP", "PLAYER_Y_RADIUS", "SST_anim", "SST_layer"):
            if n not in equs:
                raise CouldNotRun(f"{a.lst} carries no EQU {n}")
        lp = cc.ledge_params()
        plane, size = _clip_plane(a.clip) if a.clip else _canonical_plane()
        pop = classify(plane, size, lp)
        rows = []
        for cls in ("WALL", "LEDGE"):
            picked, n = spots(pop[cls], a.per_class)
            print(f"{cls}: {len(pop[cls])} standing position(s) in {n} spot(s); grading "
                  f"{len(picked)}")
            rows += [(cls, *p) for p in picked]
        for s in a.spot:
            x, foot, face = s.split(",")
            key = (int(x), int(foot), face)
            if key not in set(pop["WALL"]):
                raise CouldNotRun(f"--spot {s} is not a WALL position of this collision; "
                                  f"the derivation and the sighting disagree")
            if ("WALL", *key) in rows:
                rows.remove(("WALL", *key))
            rows.insert(0, ("WALL", *key))
        if not pop["LEDGE"]:
            raise CouldNotRun("no LEDGE position at all: the population is empty")
        from aether_instance import aether_emulator
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            res = asyncio.run(drive(sock, syms, equs, rows))
    except (CouldNotRun, SystemExit) as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2
    fails, unmeasured, ok = [], 0, 0
    for r in res:
        g = grade(r, equs)
        tag = "ok" if g is None else ("--" if g.startswith("UNMEASURED") else "FAIL")
        print(f"  {tag:4s} {r['cls']:5s} x {r['x']:5d} foot {r['foot']:5d} {r['face']:5s} -> "
              f"anim {r['anim']} facing {r['facing']}" + (f"  {g}" if g else ""))
        if g is None:
            ok += 1
        elif g.startswith("UNMEASURED"):
            unmeasured += 1
        else:
            fails.append(r)
    print(f"graded {ok + len(fails)} of {len(res)} spot(s): {ok} matched, {len(fails)} FAILED, "
          f"{unmeasured} unmeasured")
    if fails:
        print("VERDICT: RED")
        print("finished=1")
        return 1
    if unmeasured * 2 > len(res):
        print("COULD NOT RUN: more than half the spots were unmeasurable")
        print("finished=1")
        return 2
    print("VERDICT: GREEN")
    print("finished=1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
