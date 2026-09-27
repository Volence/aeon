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
     camera centre inside a corridor, and each is made past the mouth of the zone it names;
  K1 a key-on within KEYON_WINDOW frames of each request, none before the first.
  LAG: Lag_Frame_Count's advance while the player is within 16 px of each corridor, and over
     each whole run, is PRINTED (a measurement, not a verdict).
  FAULT: the ROM reaching its error handler anywhere on the route is a FAIL (checked every
     30 frames of a run and at the end of each phase).
Exit 0 all held · 1 an assertion failed or the ROM faulted · 2 could not run.

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
SETTLE_FRAMES = 60
KEYON_WINDOW = 180


class CouldNotRun(Exception):
    pass


class Faulted(Exception):
    """The ROM reached its error handler: a RESULT (exit 1), not a failure to measure."""


def expected_requests(act, legs, ids):
    """[(corridor id, song id)] the policy expects: entering a zone with a song requests it
    when it differs from the one playing; a zone with none requests nothing."""
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
    for co, _left, right in legs:
        want = ids[right.music] if right.music else None
        if want is not None and want != playing:
            out.append((co.id, want))
            playing = want
    return out


async def drive(sock, syms, equs, act, legs, ym=False):
    b = BusClient(socket_path=sock, client_id="wrw", client_name="woven_route_witness")
    await b.connect()
    bus = L.Bus(b)
    P = syms["Player_1"]
    A_X = P + equs["SST_x_pos"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    half_w = CRB.crossing_constants()[2]
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
    events, keyons, samples = [], {}, []
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
            n = sum(1 for _, _, part, reg, v in tap.events
                    if v is not None and part == 0 and reg == 0x28 and (v & 0xF0))
            if n:
                keyons[frame] = n
            del tap.events[:]
        rd = lambda n, w: bus.read(syms[n], w)                           # noqa: E731
        samples.append({
            "frame": frame, "leg": leg,
            "region": int.from_bytes(await rd("Region_Current", 4), "big"),
            "centre": (int.from_bytes(await rd("Camera_X", 4), "big") >> 16) + half_w,
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
    return {"events": events, "keyons": keyons, "samples": samples, "cram_end": cram_end,
            "tap_dropped": tap.dropped if tap else 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", required=True)
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
        cors = sorted(act.corridors, key=lambda c: c.dst[0])
        if len(cors) < 2:
            raise CouldNotRun("the manifest has fewer than two corridors; use the one-corridor "
                              "witnesses")
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
        near = [s for s in leg if co.dst[0] - 16 <= s["px"] < co.dst[0] + co.dst[2] + 16]
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
        if leg[-1]["px"] < co.dst[0] + co.dst[2] + RUN_OUT:
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
        c = at[f]["centre"]
        for co, _l, right in legs:
            if co.dst[0] <= c < co.dst[0] + co.dst[2]:
                fails.append(f"P2 song {v} requested at frame {f} with the camera centre INSIDE "
                             f"corridor {co.id} (x {c})")
        named = [(co, r) for co, _l, r in legs if r.music and ids[r.music] == v]
        if named and not any(c >= r.dst[0] for _co, r in named):
            fails.append(f"P2 song {v} requested at frame {f} (centre {c}) before the camera "
                         f"reached the zone that names it")
    if y["tap_dropped"]:
        print(f"  [the YM tap dropped {y['tap_dropped']} hit(s): key-on counts are LOWER BOUNDS]")
    k = y["keyons"]
    if requests:
        before = sum(n for f, n in k.items() if f < requests[0][0])
        print(f"K1 key-ons before the first request: {before}")
        if before:
            fails.append(f"K1 {before} key-on(s) before any song was requested")
    for f, v in requests:
        n = sum(c for g, c in k.items() if f <= g < f + KEYON_WINDOW)
        print(f"K1 song {v} requested at frame {f}: {n} key-on(s) in the next {KEYON_WINDOW} "
              f"frames")
        if not n:
            fails.append(f"K1 no key-on within {KEYON_WINDOW} frames of the request at {f}")
    for m in fails:
        print(f"FAIL: {m}")
    print("VERDICT:", "RED" if fails else "GREEN")
    print("finished=1")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
