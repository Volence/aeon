#!/usr/bin/env python3
"""path_b_floor_witness — does a player on collision path B stand where Sonic 2 gives him ground?

WHY IT EXISTS (WOVEN-WFZ-PLANE-B, 2026-09-27). In the woven Sonic 2 act the owner fell through
Wing Fortress: at woven (5133, 1389), grounded on LAYER 1 on the act's fill floor under the ship,
where plane A has decks at y 1152 and 1280 and plane B had none. Sonic 2 never puts the player on
Wing Fortress's path B (its object layout has no plane switcher, and every act starts on path A),
but a clip act can deliver him there on B from a two-path neighbour (Emerald Hill, Chemical
Plant), and nothing in Wing Fortress puts him back. The clip bake now pastes every ONE-PATH zone
(clip_manifest.zone_path_b_switchers == 0: no plane switcher that selects path B in its Sonic 2
object layout) with its plane A on both planes; this checks the ROM against that, on the ROM.

TWO MODES.

  (default) DECKS, a verdict. The population is DERIVED, never typed: for every clip of a
    one-path zone (read off the donor's object layout, clip_manifest.zone_path_b_switchers),
    every LEVEL standing position of the clip's plane A in the baked tree
    (games/sonic4/data/clips/<ID>/baked, read as probe_core reads it, balance_witness._clip_plane):
    both floor sensors (x -/+ PLAYER_X_RADIUS) and every column FLAT_PX past them read 0 at the
    foot, and the body box holds no solid pixel. Positions cluster (same foot, x consecutive on
    the X_STEP grid) into spots; up to --per-clip spots per clip are taken, spread over it.
    --spot x,foot adds a named row (the owner's sighting), graded at the nearest derived
    position on that floor within SPOT_SNAP_PX (the sighting column itself sits within a
    sensor's reach of a deck edge / a wall, so it is not LEVEL ground); none there = could not run.
    Each spot is placed twice through the warp mailbox (DEBUG shape) and pinned PIN_FRAMES:
      CONTROL  layer 0, released, SETTLE_FRAMES: he must still be at the spot. A control that
               moves makes the spot UNMEASURED (counted, printed, never graded).
      SUBJECT  layer 1, the same: he must still be at the spot, on layer 1. Falling is FAIL.
    Exit 0 every graded spot held · 1 one fell · 2 could not run (no ROM / symbol / warp
    mailbox / baked tree, no one-path clip, an empty population, or more than half the spots
    unmeasurable).

  --connectors, a MEASUREMENT (booking item 2: which path does the player carry across each
    connector, and does carrying B produce a wrong-collision case?). For every corridor, run
    RIGHT then LEFT; for every shaft, DROP. Each is driven twice, starting on layer 0 and on
    layer 1 (written after placement, RUN_MARGIN px inside the source zone, so the source's own
    lines on the run-up act as they would), and records the layer at the connector's entry
    mouth, at its exit mouth and at the end of the run-out, and the player's (x, y) at the end.
    The two drives AGREE when they end at the same place: then the path he carried across made
    no collision difference on that crossing. Where the manifest DECLARES a path line at the
    arrival mouth (clip_manifest PATH LINES; WOVEN-CROSSING-PATH), agreeing is not enough: both
    drives must also cross that mouth on the path the named donor Obj03's subtype gives
    (`declared_arrivals`), else WRONG PATH. Exit 0 every connector agreed (and every declared
    arrival was on its path) · 1 one did not (printed with both trajectories' ends) · 2 could
    not run (incl. a declared path line the bake would refuse).

Usage:
    python3 tools/path_b_floor_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --clip s2_woven --spot 5133,1152 --spot 5133,1280
    python3 tools/path_b_floor_witness.py ... --clip s2_woven --connectors
Wired: tools/keepalive_manifest.toml (the decks row on the nightly's woven ROM). RED on the woven
ROM built from master 06185e04 (crc 1bce0476), GREEN after the re-key (see DEFERRED_WORK
WOVEN-WFZ-PLANE-B for the counts).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))
import collision_consistency as cc  # noqa: E402

PIN_FRAMES = 60
SETTLE_FRAMES = 40
FLAT_PX = 8                # level floor this far past each floor sensor
X_STEP = 4                 # the population grid (px)
FALL_PX = 4                # a subject more than this far below its spot fell
SPOT_SNAP_PX = 32          # a --spot is graded at the nearest level position this close
RUN_MARGIN = 400           # --connectors: start this far inside the source zone
RUN_OUT = 160              # ... and end this far past the exit mouth
RUN_MAX = 900
DROP_ABOVE = 64
LAND_FRAMES = 8


class CouldNotRun(Exception):
    pass


# ---------------------------------------------------------------------------
# The population
# ---------------------------------------------------------------------------

def standing(plane, x, foot, lp, top_mask, any_mask):
    xr, yr = lp["PLAYER_X_RADIUS"], lp["PLAYER_Y_RADIUS"]
    for d in range(-xr - FLAT_PX, xr + FLAT_PX + 1):
        if plane.probe_down(x + d, foot, top_mask) != 0:
            return False
    for xx in range(x - xr, x + xr + 1):
        for yy in range(foot - 2 * yr, foot):
            if plane.pixel_solid(xx, yy, any_mask):
                return False
    return True


def column_tops(plane, x, y0, y1, top_mask):
    out, prev = [], True
    for y in range(y0, y1):
        s = plane.pixel_solid(x, y, top_mask)
        if s and not prev:
            out.append(y)
        prev = s
    return out


def population(plane, clip, lp):
    """[(x, foot)] level standing positions inside the clip's destination rectangle."""
    top, lrb = lp["SOLID_TOP"], lp["SOLID_LRB"]
    xr, yr = lp["PLAYER_X_RADIUS"], lp["PLAYER_Y_RADIUS"]
    dx, dy, dw, dh = clip.dst
    out = []
    for x in range(dx + xr + FLAT_PX, dx + dw - xr - FLAT_PX, X_STEP):
        for foot in column_tops(plane, x, dy + 2 * yr, dy + dh, top):
            if standing(plane, x, foot, lp, top, top | lrb):
                out.append((x, foot))
    return out


def spots(rows, per_clip):
    """One spot per cluster (same foot, x consecutive on the X_STEP grid), spread out."""
    clusters = []
    for x, foot in sorted(rows, key=lambda r: (r[1], r[0])):
        c = clusters[-1] if clusters else None
        if c and c[-1][1] == foot and x - c[-1][0] <= X_STEP:
            c.append((x, foot))
        else:
            clusters.append([(x, foot)])
    clusters.sort()
    picked = [c[len(c) // 2] for c in clusters]
    if len(picked) > per_clip:
        step = len(picked) / per_clip
        picked = [picked[int(i * step)] for i in range(per_clip)]
    return picked, len(clusters)


# ---------------------------------------------------------------------------
# The drives
# ---------------------------------------------------------------------------

async def _boot(b, bus, P):
    import loop_step_over_witness as L
    await bus.frames(240)
    await bus.check_alive("boot")
    if (await bus.read(P + L.PLAYERV_DEBUG_FLAG, 1))[0]:
        await b.call("emulator/press", {"buttons": ["b"]})
        await bus.frames(4)
    if (await bus.read(P + L.PLAYERV_DEBUG_FLAG, 1))[0]:
        raise CouldNotRun("the B press did not leave debug free flight")


async def drive_decks(sock, syms, equs, rows):
    from aether import BusClient
    import loop_step_over_witness as L
    import tunnel_run_witness as T
    b = BusClient(socket_path=sock, client_id="pbfw", client_name="path_b_floor_witness")
    await b.connect()
    bus = L.Bus(b)
    P = syms["Player_1"]
    A = {k: P + equs[f"SST_{k}"] for k in ("x_pos", "y_pos", "layer")}
    out = []
    try:
        await _boot(b, bus, P)
        for clip_id, x, foot in rows:
            y = foot - equs["PLAYER_Y_RADIUS"]
            got = {}
            for layer in (0, 1):
                await T.place(b, bus, syms, x, y, frames=PIN_FRAMES)
                await bus.write(A["layer"], layer, 1)
                await bus.write(P + L.PLAYERV_GROUND_SPEED, 0, 2)
                await bus.frames(SETTLE_FRAMES)
                await bus.check_alive(f"spot ({x}, {foot}) layer {layer}")
                got[layer] = (int.from_bytes(await bus.read(A["x_pos"], 2), "big"),
                              int.from_bytes(await bus.read(A["y_pos"], 2), "big"),
                              (await bus.read(A["layer"], 1))[0])
            out.append({"clip": clip_id, "x": x, "foot": foot, "y": y, "l0": got[0], "l1": got[1]})
    finally:
        await b.close()
    return out


def grade_deck(r):
    x, y = r["x"], r["y"]
    if r["l0"] != (x, y, 0):
        return f"UNMEASURED: the layer-0 control did not stay put ({r['l0']})"
    px, py, layer = r["l1"]
    if py > y + FALL_PX:
        return f"FELL on layer 1: ended at ({px}, {py}) layer {layer}"
    if (px, py, layer) != (x, y, 1):
        return f"UNMEASURED: the layer-1 subject moved without falling ({r['l1']})"
    return None


async def drive_connectors(sock, syms, equs, act, legs):
    """legs: [(id, kind, direction)] kind "corridor" (direction "right"/"left") or "shaft"."""
    from aether import BusClient
    import loop_step_over_witness as L
    import tunnel_run_witness as T
    import crossing_witness as X
    b = BusClient(socket_path=sock, client_id="pbfw", client_name="path_b_floor_witness")
    await b.connect()
    bus = L.Bus(b)
    P = syms["Player_1"]
    A = {k: P + equs[f"SST_{k}"] for k in ("x_pos", "y_pos", "layer")}
    A_GSP = P + L.PLAYERV_GROUND_SPEED
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    by_id = {k.id: k for k in list(act.corridors) + list(getattr(act, "shafts", []))}
    out = []

    async def pos():
        return (int.from_bytes(await bus.read(A["x_pos"], 2), "big"),
                int.from_bytes(await bus.read(A["y_pos"], 2), "big"),
                (await bus.read(A["layer"], 1))[0])

    try:
        await _boot(b, bus, P)
        for cid, kind, direction in legs:
            co = by_id[cid]
            for start_layer in (0, 1):
                rec = {"id": cid, "kind": kind, "dir": direction, "start": start_layer,
                       "entry": None, "exit": None, "end": None, "arrived": False}
                x0, y0, x1, y1 = co.dst[0], co.dst[1], co.dst[0] + co.dst[2], co.dst[1] + co.dst[3]
                if kind == "shaft":
                    sx, sy = X.drop_start(act, co)
                    await T.place(b, bus, syms, sx, sy)
                    await bus.write(A["layer"], start_layer, 1)
                    still, last_y = 0, None
                    for _k in range(RUN_MAX):
                        await bus.frames(1)
                        x, y, layer = await pos()
                        if rec["entry"] is None and y >= y0:
                            rec["entry"] = layer
                        if rec["exit"] is None and y >= y1:
                            rec["exit"] = layer
                        still = still + 1 if y == last_y else 0
                        last_y = y
                        if still >= LAND_FRAMES * 3:
                            break
                    rec["arrived"] = rec["exit"] is not None
                else:
                    side = "left" if direction == "right" else "right"
                    sx, feet = T.run_up(act, co, side, RUN_MARGIN)
                    await T.place(b, bus, syms, sx, feet - radius - 2)
                    await bus.write(A["layer"], start_layer, 1)
                    await bus.frames(LAND_FRAMES * 4)
                    await b.call("emulator/hold", {"buttons": [direction], "down": True})
                    sign = 1 if direction == "right" else -1
                    await bus.write(A_GSP, (sign * equs["PHYS_TOP_SPEED"]) & 0xFFFF, 2)
                    enter, leave = (x0, x1) if direction == "right" else (x1 - 1, x0 - 1)
                    end = leave + sign * RUN_OUT
                    try:
                        for _k in range(RUN_MAX):
                            await bus.frames(1)
                            x, y, layer = await pos()
                            if rec["entry"] is None and sign * (x - enter) >= 0:
                                rec["entry"] = layer
                            if rec["exit"] is None and sign * (x - leave) >= 0:
                                rec["exit"] = layer
                            if sign * (x - end) >= 0:
                                rec["arrived"] = True
                                break
                    finally:
                        await b.call("emulator/hold", {"buttons": [direction], "down": False})
                    await bus.frames(SETTLE_FRAMES)
                await bus.check_alive(f"{cid} {direction} from layer {start_layer}")
                rec["end"] = await pos()
                out.append(rec)
    finally:
        await b.close()
    return out


# ---------------------------------------------------------------------------

def _load(a):
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
    for n in ("PLAYER_Y_RADIUS", "SST_layer", "SST_x_pos", "SST_y_pos"):
        if n not in equs:
            raise CouldNotRun(f"{a.lst} carries no EQU {n}")
    return syms, equs


def main_decks(a):
    import balance_witness as BW
    import clip_manifest as CM
    syms, equs = _load(a)
    act = CM.load(str(AEON / "games" / "sonic4" / "data" / "clips" / a.clip / "clips.json"))
    one_path = [cl for cl in act.clips if CM.zone_path_b_switchers(cl) == 0]
    two_path = sorted({cl.zone for cl in act.clips} - {cl.zone for cl in one_path})
    print(f"one-path clips (no path-B plane switcher in the zone's Sonic 2 layout): "
          f"{', '.join(f'{c.id} ({c.zone})' for c in one_path) or 'NONE'}; two-path zones: "
          f"{', '.join(two_path) or 'none'}")
    if not one_path:
        raise CouldNotRun("the act has no one-path clip: nothing to grade")
    try:
        plane, _size = BW._clip_plane(a.clip)
    except BW.CouldNotRun as e:
        raise CouldNotRun(str(e))
    lp = cc.ledge_params()
    rows, pop = [], {}
    for cl in one_path:
        p = population(plane, cl, lp)
        pop[cl.id] = set(p)
        picked, n = spots(p, a.per_clip)
        print(f"  {cl.id}: {len(p)} level standing position(s) in {n} spot(s); grading "
              f"{len(picked)}")
        rows += [(cl.id, x, foot) for x, foot in picked]
    for s in a.spot:
        x, foot = (int(v) for v in s.split(","))
        cl = CM._clip_at(act, x, foot)
        near = sorted((abs(p[0] - x), p[0]) for p in pop.get(cl.id if cl else None, ())
                      if p[1] == foot and abs(p[0] - x) <= SPOT_SNAP_PX)
        if not near:
            raise CouldNotRun(f"--spot {s}: no level standing position of a one-path clip's "
                              f"plane A on that floor within {SPOT_SNAP_PX} px; the derivation "
                              f"and the sighting disagree")
        sx = near[0][1]
        if sx != x:
            print(f"  --spot {s}: the sighting column is not LEVEL ground (a deck edge or a "
                  f"wall is within {FLAT_PX} px of a sensor); graded at the nearest level "
                  f"position of the same floor, x {sx}")
        rows = [r for r in rows if (r[1], r[2]) != (sx, foot)]
        rows.insert(0, (cl.id, sx, foot))
    if not rows:
        raise CouldNotRun("the population is empty")
    from aether_instance import aether_emulator
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        res = asyncio.run(drive_decks(sock, syms, equs, rows))
    fails, unmeasured, ok = 0, 0, 0
    for r in res:
        g = grade_deck(r)
        tag = "ok" if g is None else ("--" if g.startswith("UNMEASURED") else "FAIL")
        print(f"  {tag:4s} {r['clip']:12s} x {r['x']:5d} foot {r['foot']:5d}"
              + (f"  {g}" if g else ""))
        if g is None:
            ok += 1
        elif g.startswith("UNMEASURED"):
            unmeasured += 1
        else:
            fails += 1
    print(f"graded {ok + fails} of {len(res)} spot(s): {ok} held on layer 1, {fails} FELL, "
          f"{unmeasured} unmeasured")
    if fails:
        return 1
    if unmeasured * 2 > len(res):
        raise CouldNotRun("more than half the spots were unmeasurable")
    return 0


def declared_arrivals(act):
    """{(connector id, direction): (layer, why)} — the path each declared corridor path line
    (clip_manifest PATH LINES) must put the player on at the mouth it serves, DERIVED from the
    donor Obj03's own subtype (s2_layer_lines.connector_lines reads it out of the object
    layout): arriving through the EAST mouth is a rightward crossing, so subtype bit 3 (path
    B on a rightward crossing); through the WEST mouth, leftward, bit 4. Read off the raw
    subtype, NOT off the baked flags, so a bake that re-packs the bits wrong is caught."""
    import s2_layer_lines as SLL
    try:
        lines = SLL.connector_lines(act)
    except SLL.LayerLineError as e:
        raise CouldNotRun(f"the act's declared path lines do not bake: {e}")
    out = {}
    for ln in lines:
        d = "right" if ln["mouth"] == "east" else "left"
        bit = 0x08 if d == "right" else 0x10
        out[(ln["connector"], d)] = (1 if ln["subtype"] & bit else 0,
                                     f"{ln['donor_zone']} Obj03 at {ln['src']} subtype "
                                     f"${ln['subtype']:02X}")
    return out


def main_connectors(a):
    import clip_manifest as CM
    syms, equs = _load(a)
    if "PHYS_TOP_SPEED" not in equs:
        raise CouldNotRun(f"{a.lst} carries no EQU PHYS_TOP_SPEED")
    act = CM.load(str(AEON / "games" / "sonic4" / "data" / "clips" / a.clip / "clips.json"))
    legs = []
    for co in act.corridors:
        legs += [(co.id, "corridor", "right"), (co.id, "corridor", "left")]
    for sh in getattr(act, "shafts", []):
        legs.append((sh.id, "shaft", "down"))
    if not legs:
        raise CouldNotRun("the act has no connector")
    zone_of = {}
    for co in list(act.corridors) + list(getattr(act, "shafts", [])):
        x0, y0, w, h = co.dst
        if getattr(co, "axis", "x") == "y":
            ends = (CM._clip_at(act, x0 + w // 2, y0 - 1), CM._clip_at(act, x0 + w // 2, y0 + h))
        else:
            fy = co.floor_y - 1
            ends = (CM._clip_at(act, x0 - 1, fy), CM._clip_at(act, x0 + w, fy))
        zone_of[co.id] = tuple(
            (c.zone, "1-path" if CM.zone_path_b_switchers(c) == 0 else "2-path") if c else ("-", "")
            for c in ends)
    arrivals = declared_arrivals(act)
    for (cid, d), (want, why) in sorted(arrivals.items()):
        print(f"declared arrival path: {cid} {d}: path {'AB'[want]} ({why})")
    print(f"{len(arrivals)} declared arrival path(s) graded (clip_manifest PATH LINES)")
    from aether_instance import aether_emulator
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        res = asyncio.run(drive_connectors(sock, syms, equs, act, legs))
    by = {}
    for r in res:
        by.setdefault((r["id"], r["dir"]), {})[r["start"]] = r
    bad = 0
    print(f"{'connector':14s} {'dir':5s} {'from':14s} {'to':14s} start  entry exit  end(x,y,layer)"
          f"          verdict")
    for (cid, d), pair in by.items():
        src, dst = zone_of[cid] if d in ("right", "down") else zone_of[cid][::-1]
        verdict = "agree"
        e0, e1 = pair[0]["end"], pair[1]["end"]
        if not (pair[0]["arrived"] and pair[1]["arrived"]):
            verdict = "DID NOT ARRIVE"
            bad += 1
        elif e0[:2] != e1[:2]:
            verdict = "DIFFER"
            bad += 1
        elif (cid, d) in arrivals and any(pair[s]["exit"] != arrivals[(cid, d)][0]
                                          for s in (0, 1)):
            verdict = f"WRONG PATH (Sonic 2's is {'AB'[arrivals[(cid, d)][0]]})"
            bad += 1
        for s in (0, 1):
            r = pair[s]
            print(f"{cid:14s} {d:5s} {src[0] + ' ' + src[1]:14s} {dst[0] + ' ' + dst[1]:14s} "
                  f"L{s}     {r['entry']!s:5s} {r['exit']!s:5s} {r['end']!s:22s} "
                  f"{verdict if s else ''}")
    print(f"{len(by)} crossing(s) driven twice: {len(by) - bad} agree, {bad} differ, did not "
          f"arrive, or arrived on a path other than the declared one")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--clip", required=True, help="a clip act id (its baked tree and manifest)")
    ap.add_argument("--spot", action="append", default=[],
                    help="x,foot: a named row (must be a derived level standing position)")
    ap.add_argument("--per-clip", type=int, default=6)
    ap.add_argument("--connectors", action="store_true",
                    help="the path-carry measurement across every connector instead")
    a = ap.parse_args(argv)
    try:
        rc = main_connectors(a) if a.connectors else main_decks(a)
    except (CouldNotRun, SystemExit) as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2
    print("VERDICT: " + ("GREEN" if rc == 0 else "RED"))
    print("finished=1")
    return rc


if __name__ == "__main__":
    sys.exit(main())
