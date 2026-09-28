#!/usr/bin/env python3
"""woven_route_witness — run a woven clip act's main route through EVERY corridor, left to right.

WHY IT EXISTS (woven first screen s2_mtz_cpz, 2026-09-27). tools/clip_music_witness.py,
tools/crossing_witness.py and tools/tunnel_run_witness.py each drive ONE corridor of a two-clip
act. A woven act strings zones as A | tunnel | B | tunnel | A (Chemical Plant as a pocket inside
Metropolis), and the question the owner asks of it is the route: in at one end, through the
pocket, out into the same zone on the far side. This drives exactly that in ONE boot and reports
what happened at every crossing: the preset (region) change, the palette actually scanned out
(CRAM), the music requests, and the lag frames around each corridor.

THIS IS A WITNESS, NOT A GATE (the status of the three it borrows from): no runner owns a clip
ROM, which is a throwaway S2CLIP shape. Run by hand against `DEBUG=1 S2CLIP=<id> ./build.sh`.

THE DRIVE (DEBUG shape; the plain shape has no warp consumer and is refused):
  boot   BOOT_FRAMES from reset, then a real B press to leave debug free flight (the harness's
         default state IS the condition under test otherwise).
  per corridor, left to right:
    place  the player up to RUN_MARGIN px left of the corridor, on the measured run-up
           (tunnel_run_witness.run_up: the surface he can run along into it), through the
           WARP MAILBOX (tunnel_run_witness.place; never a bare Camera_X write), pinned while
           the window streams, then left to land.
    run    RIGHT held, ground speed PHYS_TOP_SPEED injected once, until RUN_OUT px past the
           corridor's right mouth. The zone BETWEEN two corridors is not run: the player is
           placed again before the next one (the task's "place via the warp mailbox").
  A second, identical boot carries the YM port tap alone (the music-slot watch and the tap
  overflow one hit ring together: clip_music_witness's measurement) for key-ons.

WHAT IS DERIVED, NOT TYPED: the corridors and their flanking clips (the manifest), each zone's
song (the manifest's `music`, ids from games/sonic4/config/sound_ids.emp), each zone's palette
(the converted donor tree), the expected requests (a zone with a song requests it on entry when
it differs from the one playing; a zone with none leaves the music alone, the region rule
S2CLIP-MUSIC-FEEL and Region.rg_song's 0).

VERDICT:
  R1 every run reaches RUN_OUT past its corridor (the route was actually driven), no fault;
  R2 at each corridor the region preset changes from the left zone's to the right zone's
     (read off the ROM's own region table) and the CRAM lines 1-3 hold the right zone's
     palette by the end of the run;
  P1 the music requests, in order, equal the derived expectation; P2 none is made with the
     camera centre inside a connector's RECTANGLE (x and y, the manifest's dst_rect; a
     corridor's x span alone flagged stacked corridors, WOVEN-ROUTE-WITNESS-P2-XSPAN), and each is made with the camera centre inside a zone
     that names the song (the start zone included);
  K1 a note start (an FM key-on or a DAC sample start) within KEYON_WINDOW frames of each
     request; no FM key-on before the first (the driver's boot DAC-enable write is not one).
  LAG: Lag_Frame_Count's advance while the player is within 16 px of each corridor, and over
     each whole run, is PRINTED (a measurement, not a verdict).
  FAULT: the ROM reaching its error handler anywhere on the route is a FAIL (checked every
     30 frames of a run and at the end of each phase).
Exit 0 all held · 1 an assertion failed or the ROM faulted · 2 could not run.

A 2-D ACT (s2_woven, 2026-09-27): `--route id,id,...` names the legs in order, corridors AND
shafts. A corridor leg runs RIGHT as above. A SHAFT leg is a DROP: the player is placed
crossing_witness.DROP_ABOVE px over the shaft's top mouth on its lane (crossing_witness.
drop_start: the fall path is MEASURED clear of collision, or COULD NOT RUN), let go with no
button held, and the leg ends when the camera centre is RUN_OUT_Y px under the shaft's bottom
mouth or he has stood still for LAND_FRAMES (landed, below it or short of it); R1 then asks
that the camera centre got past the bottom mouth. Without --route the legs are every corridor left to right,
exactly as before (the 1-D acts).

Usage:
    python3 tools/woven_route_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --manifest games/sonic4/data/clips/s2_mtz_cpz/clips.json
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator  # noqa: E402
import clip_manifest as CM  # noqa: E402
import clip_rom_bake as CRB  # noqa: E402
import crossing_witness as X  # noqa: E402
import loop_step_over_witness as L  # noqa: E402
import region_music_witness as RMW  # noqa: E402
import region_table as RT  # noqa: E402
import tunnel_run_witness as T  # noqa: E402
from song_load_mid_drum_witness import YmTap  # noqa: E402

BOOT_FRAMES = 240
RUN_MARGIN = T.RUN_MARGIN
#: a run ends this far past the corridor's right mouth: one screen half (T.RUN_MARGIN's
#: reasoning), so the camera centre is past the mouth and every crossing effect has fired.
#: Not further: 262 px past the woven act's first tunnel, Chemical Plant's middle track meets
#: the plane-A back of a loop (MEASURED 2026-09-27, x 2166 held at top speed), and the route
#: through the pocket's interior is placed, not run (see the parcel's DEFERRED_WORK entry).
RUN_OUT = T.RUN_MARGIN
RUN_MAX = 900
#: a DROP leg ends this far past the shaft's bottom mouth (a screen half, RUN_OUT's reason)
RUN_OUT_Y = 112
SETTLE_FRAMES = 60
KEYON_WINDOW = 180


class CouldNotRun(Exception):
    pass


class Faulted(Exception):
    """The ROM reached its error handler: a RESULT (exit 1), not a failure to measure."""


def expected_requests(act, legs, ids):
    """[(corridor id, song id)] the policy expects: entering a zone with a song requests it
    when it differs from the one playing (being PLACED in a leg's left zone counts as
    entering it); a zone with none requests nothing."""
    start = CRB.act_start(act)
    first = legs[0][1]
    playing = ids[first.music] if first.music else None
    if start is not None:
        # the clip whose rectangle holds the start point (either `start` form); a start in
        # a corridor plays nothing (a corridor row names no song)
        holder = next((c for c in act.clips
                       if c.dst[0] <= start["x"] < c.dst[0] + c.dst[2]
                       and c.dst[1] <= start["y"] < c.dst[1] + c.dst[3]), None)
        playing = ids[holder.music] if holder is not None and holder.music else None
    out = [("boot", playing)] if playing is not None else []
    for co, left, right in legs:
        # Every leg PLACES the player in its left zone first (the warp mailbox), so a left
        # zone that names another song requests it there. Until Wing Fortress named its song
        # (song bank 2, 2026-09-28) no leg's left zone did so except the start's: a drop from
        # Wing Fortress (wfz_to_ehz) requests WFZ's song on placement, then EHZ's on landing.
        placed = ids[left.music] if left.music else None
        if placed is not None and placed != playing:
            out.append((co.id, placed))
            playing = placed
        want = ids[right.music] if right.music else None
        if want is not None and want != playing:
            out.append((co.id, want))
            playing = want
    return out


def connectors_holding(legs, c, cy):
    """The route's connectors (corridors AND shafts) whose RECTANGLE (manifest `dst_rect`,
    half-open) holds the camera centre (c, cy): P2's no-music zone.

    WOVEN-ROUTE-WITNESS-P2-XSPAN (2026-09-28): a corridor's zone used to be its x span alone
    (the 1-D rule; only a shaft was tested on both axes). In a 2-D act corridors stack: on
    s2_woven, x 4583 in Metropolis west (y 2859) is inside hpz_to_ooz's span, 4544..5103,
    although that tunnel is y 4624..5135, so the correct song-4 request made there was
    flagged. Still caught (MEASURED on ROM-copy mutants whose corridor far half names the
    far song): s2_woven's hpz_to_ooz request at (4850, 4863) and s2_mtz_cpz's 1-D
    mtz_to_cpz request at (1763, 1067). tools/test_woven_route_witness.py holds both
    cases."""
    return [co for co, _l, _r in legs
            if co.dst[0] <= c < co.dst[0] + co.dst[2]
            and co.dst[1] <= cy < co.dst[1] + co.dst[3]]


async def drive(sock, syms, equs, act, legs, ym=False):
    b = BusClient(socket_path=sock, client_id="wrw", client_name="woven_route_witness")
    await b.connect()
    bus = L.Bus(b)
    P = syms["Player_1"]
    A_X = P + equs["SST_x_pos"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    half_w = CRB.crossing_constants()[2]
    half_h = CRB._cam_constants()["CAM_SCREEN_HALF_H"]
    handle = None
    if not ym:
        w = await b.call("emulator/watchpoint_add", {"addr": hex(equs["MUSIC_SLOT"]), "len": 1,
                                                      "write": True, "read": False,
                                                      "mode": "record", "label": "music_slot",
                                                      "space": "bus"})
        handle = w["watch"]
    tap = YmTap(b) if ym else None
    if tap:
        await tap.arm()
    cursor, dropped = None, 0
    events, keyons, samples, dac_starts = [], {}, [], {}
    frame = 0

    async def poll():
        nonlocal cursor, dropped
        while handle is not None:
            p = {"watch": handle, "limit": 100}
            if cursor is not None:
                p["cursor"] = str(cursor)
            r = await b.call("emulator/watchpoint_hits", p)
            hits = r.get("hits", [])
            for h in hits:
                cursor = h["seq"]
                events.append((frame, h.get("via"),
                               int(str(h["value"]).replace("0x", ""), 16) & 0xFF))
            dropped = r.get("dropped", dropped)
            if len(hits) < 100:
                return

    async def step(leg):
        nonlocal frame
        await bus.frames(1)
        frame += 1
        await poll()
        if tap:
            await tap.poll()
            # A NOTE START: an FM key-on ($28, key bits set) or a DAC sample start ($2B,
            # DAC enable, which Snd_StartSample writes at every sample). The DAC counts
            # because a song can open on drums alone: Sonic 2's Metropolis rests every FM
            # channel for its first bars (s2disasm 85 - MTZ.asm: FM1/FM3 `nRst, $30` x4
            # before a note), so an FM-only count saw 0 in 180 frames on a song that was
            # playing (MEASURED 2026-09-28: 0 FM key-ons in 180 frames, 26 in 300, identical
            # from bank 1 and from bank 2).
            fm = sum(1 for _, _, part, reg, v in tap.events
                     if v is not None and part == 0 and reg == 0x28 and (v & 0xF0))
            dac = sum(1 for _, _, part, reg, v in tap.events
                      if v is not None and part == 0 and reg == 0x2B and (v & 0x80))
            if fm or dac:
                keyons[frame] = fm + dac
                dac_starts[frame] = dac
            del tap.events[:]
        rd = lambda n, w: bus.read(syms[n], w)                           # noqa: E731
        samples.append({
            "frame": frame, "leg": leg,
            "region": int.from_bytes(await rd("Region_Current", 4), "big"),
            "centre": (int.from_bytes(await rd("Camera_X", 4), "big") >> 16) + half_w,
            "cy": (int.from_bytes(await rd("Camera_Y", 4), "big") >> 16) + half_h,
            "px": int.from_bytes(await bus.read(A_X, 4), "big") >> 16,
            "py": int.from_bytes(await bus.read(P + equs["SST_y_pos"], 4), "big") >> 16,
            "layer": (await bus.read(P + equs["SST_layer"], 1))[0],
            "gsp": int.from_bytes(await bus.read(A_GSP, 2), "big", signed=True),
            "lag": int.from_bytes(await rd("Lag_Frame_Count", 4), "big"),
        })

    async def alive(where):
        st = await bus.status()
        if "ErrorHandler" in (st.get("symbolAtPc") or ""):
            raise Faulted(f"the ROM FAULTED during {where}: {st.get('symbolAtPc')!r}")

    for _ in range(BOOT_FRAMES):
        await step("boot")
    await alive("boot")
    if (await bus.read(A_DBG, 1))[0]:
        await b.call("emulator/press", {"buttons": ["b"]})
        for _ in range(4):
            await step("boot")
    if (await bus.read(A_DBG, 1))[0]:
        raise CouldNotRun("the B press did not leave debug free flight")
    cram_end = {}
    for co, left, right in legs:
        if getattr(co, "axis", "x") == "y":
            sx, sy = X.drop_start(act, co)
            await T.place(b, bus, syms, sx, sy)
            await alive(f"placement before {co.id}")
            y_out = co.dst[1] + co.dst[3]
            still = 0
            for k in range(RUN_MAX):
                await step(f"run {co.id}")
                t = samples[-1]
                if t["cy"] >= y_out + RUN_OUT_Y:
                    break
                # STOOD STILL for LAND_FRAMES anywhere ends the leg: under the shaft that is
                # the landing; above its bottom mouth it is a drop that landed SHORT, which
                # R1 then fails (a result, not a failure to run)
                still = still + 1 if t["py"] == samples[-2]["py"] else 0
                if still >= L.LAND_FRAMES:
                    break
                if k % 30 == 29:
                    await alive(f"the drop through {co.id} (y {t['py']})")
            else:
                tail = "; ".join(f"f{t['frame']} x{t['px']} y{t['py']} lag{t['lag']} reg{t['region']:#x}"
                                 for t in samples[-6:])
                raise CouldNotRun(f"the drop through {co.id} never arrived; last frames: {tail}")
            for _ in range(SETTLE_FRAMES):
                await step(f"run {co.id}")
            await alive(f"the drop through {co.id}")
            if not ym:
                cram_end[co.id] = await X.cram_1_3(b)
            continue
        sx, feet = T.run_up(act, co, "left", RUN_MARGIN)
        await T.place(b, bus, syms, sx, feet - radius - 2)
        for _ in range(L.LAND_FRAMES * 4):
            await step(f"place {co.id}")
        await alive(f"placement before {co.id}")
        await b.call("emulator/hold", {"buttons": ["right"], "down": True})
        await bus.write(A_GSP, equs["PHYS_TOP_SPEED"] & 0xFFFF, 2)
        end = co.dst[0] + co.dst[2] + RUN_OUT
        for k in range(RUN_MAX):
            await step(f"run {co.id}")
            if samples[-1]["px"] >= end:
                break
            if k % 30 == 29:
                await alive(f"the run through {co.id} (x {samples[-1]['px']})")
        else:
            await b.call("emulator/hold", {"buttons": ["right"], "down": False})
            tail = "; ".join(f"f{t['frame']} x{t['px']} y{t['py']} gsp{t['gsp']} L{t['layer']} lag{t['lag']} reg{t['region']:#x}"
                             for t in samples[-6:])
            raise CouldNotRun(f"the run through {co.id} never arrived (last x "
                              f"{samples[-1]['px']}, wanted {end}); last frames: {tail}")
        await b.call("emulator/hold", {"buttons": ["right"], "down": False})
        for _ in range(SETTLE_FRAMES):
            await step(f"run {co.id}")
        await alive(f"the run through {co.id}")
        if not ym:
            cram_end[co.id] = await X.cram_1_3(b)
    await b.close()
    if dropped:
        raise CouldNotRun(f"the music-slot watch dropped {dropped} hit(s)")
    return {"events": events, "keyons": keyons, "dac_starts": dac_starts, "samples": samples,
            "cram_end": cram_end,
            "tap_dropped": tap.dropped if tap else 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--route", help="comma list of connector ids (corridors run right, shafts "
                                    "are dropped), in order; default every corridor left to "
                                    "right")
    a = ap.parse_args()
    try:
        syms, equs = L.parse_lst(a.lst)
        _s2, e2 = RMW.parse_lst(a.lst)
        equs.update(e2)
        T._EQUS.update(equs)
        for n in ("Region_Current", "Camera_X", "Lag_Frame_Count", "Warp_Req_Flag",
                  RMW.ACT_SYMBOL):
            if n not in syms:
                raise CouldNotRun(f"{a.lst} carries no {n} (the route needs the DEBUG shape's "
                                  f"warp mailbox)" if n == "Warp_Req_Flag" else
                                  f"{a.lst} carries no {n}")
        rom = Path(a.rom).read_bytes()
        rows = RT.read_regions(rom, syms[RMW.ACT_SYMBOL])
        act = CM.load(a.manifest)
        if a.route:
            by_id = {k.id: k for k in list(act.corridors) + list(getattr(act, "shafts", []))}
            legs = []
            for cid in a.route.split(","):
                if cid not in by_id:
                    raise CouldNotRun(f"--route names {cid!r}, which is no corridor or shaft "
                                      f"of the act ({sorted(by_id)})")
                _ax, bef, aft = CM.connector_ends(act, by_id[cid])
                if bef is None or aft is None:
                    raise CouldNotRun(f"connector {cid!r} does not join two clips")
                legs.append((by_id[cid], bef, aft))
        else:
            cors = sorted(act.corridors, key=lambda c: c.dst[0])
            if len(cors) < 2:
                raise CouldNotRun("the manifest has fewer than two corridors; use the "
                                  "one-corridor witnesses")
            legs = [T.corridor_geometry(act, co.id) for co in cors]
        ids = CRB.song_ids()
        expect = expected_requests(act, legs, ids)
        pals = X.zone_palettes(act)
        print(f"ROM {a.rom}: {len(rom)} B; {len(rows)} region rows: "
              + "; ".join(f"x {r['x0']}..{r['x1']} song {r['song']}" for r in rows))
        print("route: " + " -> ".join([legs[0][1].id] + [f"[{co.id}] {r.id}" for co, _l, r in legs]))
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            w = asyncio.run(drive(sock, syms, equs, act, legs))
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            y = asyncio.run(drive(sock, syms, equs, act, legs, ym=True))
    except Faulted as e:
        print(f"FAIL: {e}")
        print("VERDICT: RED")
        print("finished=1")
        return 1
    except (CouldNotRun, SystemExit) as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2

    by_addr = {r["addr"]: r for r in rows}
    preset_of = {r["addr"]: r["effects"] for r in rows}
    fails = []
    samples = w["samples"]
    at = {s["frame"]: s for s in samples}
    for co, left, right in legs:
        leg = [s for s in samples if s["leg"] == f"run {co.id}"]
        vert = getattr(co, "axis", "x") == "y"
        pk, i0 = ("py", 1) if vert else ("px", 0)
        near = [s for s in leg if co.dst[i0] - 16 <= s[pk] < co.dst[i0] + co.dst[i0 + 2] + 16]
        lag_near = (near[-1]["lag"] - near[0]["lag"]) if near else None
        lag_run = leg[-1]["lag"] - leg[0]["lag"]
        p_first, p_last = preset_of.get(leg[0]["region"]), preset_of.get(leg[-1]["region"])
        cross = next((s for s in leg if preset_of.get(s["region"]) != p_first), None)
        cram = X.classify(w["cram_end"][co.id], [pals[left.zone_key], pals[right.zone_key]],
                          [left.zone, right.zone])
        print(f"{co.id} ({left.zone} -> {right.zone}): {len(leg)} frames; preset "
              f"{p_first:#x} -> {p_last:#x}"
              + (f", changed at frame {cross['frame']} (camera centre {cross['centre']}, "
                 f"player x {cross['px']})" if cross else ", NEVER changed")
              + f"; CRAM lines 1-3 at the end: {cram}; lag frames within 16 px of the corridor "
                f"{lag_near}, over the whole run {lag_run}")
        if cross is None or p_first == p_last:
            fails.append(f"R2 {co.id}: the region preset never changed")
        if cram != right.zone:
            fails.append(f"R2 {co.id}: CRAM lines 1-3 hold {cram} after the run, not {right.zone}")
        if vert:
            if max(t["cy"] for t in leg) < co.dst[1] + co.dst[3]:
                fails.append(f"R1 {co.id}: the drop ended with the camera centre at y "
                             f"{leg[-1]['cy']}, above the shaft's bottom mouth")
        elif leg[-1]["px"] < co.dst[0] + co.dst[2] + RUN_OUT:
            fails.append(f"R1 {co.id}: the run ended at x {leg[-1]['px']}")
    requests = [(f, v) for f, via, v in w["events"] if via != "z80" and v != 0]
    zeros = [(f, v) for f, via, v in w["events"] if via != "z80" and v == 0]
    for f, v in requests:
        s = at.get(f)
        print(f"  REQUEST song {v} at frame {f}, leg {s['leg']}: camera centre x {s['centre']}, "
              f"player x {s['px']}, row {by_addr.get(s['region'], {}).get('index', '?')}")
    got = [v for _f, v in requests]
    print(f"P1 requests {got}; the policy expects {[v for _c, v in expect]} "
          f"({', '.join(f'{v} past {c}' for c, v in expect) or 'none'})")
    if got != [v for _c, v in expect]:
        fails.append(f"P1 requests {got}, not {[v for _c, v in expect]}")
    if zeros:
        fails.append(f"68k wrote 0 to the music slot {len(zeros)} time(s)")
    for f, v in requests:
        c, cy = at[f]["centre"], at[f]["cy"]
        for co in connectors_holding(legs, c, cy):
            fails.append(f"P2 song {v} requested at frame {f} with the camera centre INSIDE "
                         f"connector {co.id} ({c}, {cy})")
        # Made from INSIDE a zone that names this song: any clip whose `music` is it,
        # the act's start zone included. (Until 2026-09-28 only each leg's right-hand zone
        # was a candidate, which was the same thing while no start zone named a song;
        # Metropolis west, the start of s2_mtz_cpz, names SONG_S2_MTZ since song bank 2.)
        named = [cl for cl in act.clips if cl.music and ids[cl.music] == v]
        if named and not any(cl.dst[0] <= c < cl.dst[0] + cl.dst[2]
                             and cl.dst[1] <= cy < cl.dst[1] + cl.dst[3] for cl in named):
            fails.append(f"P2 song {v} requested at frame {f} (centre {c}, {cy}) outside every "
                         f"zone that names it")
    if y["tap_dropped"]:
        print(f"  [the YM tap dropped {y['tap_dropped']} hit(s): key-on counts are LOWER BOUNDS]")
    k = y["keyons"]
    if requests:
        # FM key-ons only: the driver's own boot writes $2B (DAC enable) before any music,
        # which is not a note (MEASURED 2026-09-28: one such write on s2_mtz_cpz DEBUG).
        before = sum(n - y["dac_starts"].get(f, 0) for f, n in k.items() if f < requests[0][0])
        print(f"K1 FM key-ons before the first request: {before}")
        if before:
            fails.append(f"K1 {before} FM key-on(s) before any song was requested")
    for f, v in requests:
        n = sum(c for g, c in k.items() if f <= g < f + KEYON_WINDOW)
        nd = sum(c for g, c in y["dac_starts"].items() if f <= g < f + KEYON_WINDOW)
        print(f"K1 song {v} requested at frame {f}: {n} note start(s) in the next "
              f"{KEYON_WINDOW} frames ({n - nd} FM key-on(s), {nd} DAC sample start(s))")
        if not n:
            fails.append(f"K1 no note start within {KEYON_WINDOW} frames of the request at {f}")
    for m in fails:
        print(f"FAIL: {m}")
    print("VERDICT:", "RED" if fails else "GREEN")
    print("finished=1")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
