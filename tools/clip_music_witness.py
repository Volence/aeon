#!/usr/bin/env python3
"""clip_music_witness — does a Sonic 2 clip act request each zone's song exactly where the owner
ruled, and nowhere else? (S2CLIP-REGION-MUSIC step 7, the headless half, 2026-09-25.)

THE RULING (docs/decisions.jsonl S2CLIP-MUSIC-FEEL = cut-at-exit): Emerald Hill's song plays from
act load; Chemical Plant's starts as the player comes OUT of the tunnel into Chemical Plant;
going back left, Emerald Hill's starts as he comes out on the Emerald Hill side; nothing is
requested inside the tunnel, and standing on a line and wiggling requests nothing.

THE SUBJECT. The clip bake's region rows (tools/clip_rom_bake.py MUSIC: each zone's strip split
at the corridor mouth, the corridor naming song 0) and the engine's step-5 mechanism
(Parallax_CheckBoundary records a row's non-zero rg_song in Music_Want; Music_Service posts it
when it differs from Music_Current).

THE INSTRUMENTS (headless oracle-aether subprocesses, never MCP):
  * a record-mode bus watch on the Z80 RAM byte MUSIC_SLOT (region_music_witness's instrument:
    every 68k music request is a non-zero 68000 write there), with Region_Current, Camera_X and
    the player's x sampled every frame;
  * a SECOND run of the identical drive with the YM port tap alone (the two watches overflow one
    shared hit ring together, measured in region_music_witness), counting Z80 key-ons (register
    $28, key bits set) per frame. The machine is deterministic; the two runs' region sequences
    are compared, and a mismatch fails.

THE ROUTE, all in one boot (`drive`):
  boot   BOOT_FRAMES from reset: the act-load rescan requests the start row's song.
  place  debug free flight left with a real B press (DEBUG shape); camera + pinned player at
         RUN_MARGIN px left of the corridor, PIN_FRAMES while the window streams
         (tunnel_run_witness's measured drive order).
  right  RIGHT held, ground speed PHYS_TOP_SPEED injected once, until the player is
         RUN_OUT px past the right mouth.
  wig_r  the player pinned alternately WIGGLE_DX px either side of the RIGHT mouth, WIGGLE_HOLD
         frames each, 2 * WIGGLES pins (WIGGLES round trips): the camera centre crosses the
         song line back and forth.
  left   placed RUN_MARGIN px right of the corridor, LEFT held at top speed, until RUN_OUT px
         past the left mouth.
  wig_l  the same wiggle on the LEFT mouth.
  settle SETTLE_FRAMES.

WHAT IS DERIVED, NOT TYPED: the corridor mouths (the manifest's clip rectangles), each zone's
song NAME (the manifest's `music`) and its id (games/sonic4/config/sound_ids.emp, via
clip_rom_bake.song_ids), the model's expected posts (region_music_witness.model_posts over the
ROM's own region table along the MEASURED region sequence).

VERDICT — every assertion, and which are POLICY (from the manifest, independent of the ROM's
table, so a ROM whose rows are wrong fails them) and which are MECHANISM (from the ROM's table):
  P1 the requests, in order, are exactly [start zone's song, right zone's song, left zone's song]
     (for s2_ehz_cpz: [EHZ, CPZ, EHZ]), one per leg: boot, right, left; none on either wiggle
     leg and none while settling;
  P2 on the frame each request is observed, the camera centre (Camera_X + CAM_SCREEN_HALF_W) is
     OUTSIDE the corridor, on the side of the zone whose song it is (right: centre >= the right
     mouth; left: centre < the left mouth). A request made inside the tunnel fails here;
  P3 the wiggle legs really crossed the song line: the camera centre crossed the mouth's x at
     least 2 * WIGGLES - 1 times on each (a premise; unmet = COULD NOT RUN, never a pass);
  M1 the requests equal model_posts over the measured region sequence (the ROM's own table);
  K1 Z80 key-ons: none before the first request, and at least one within KEYON_WINDOW frames
     from each request.
Exit 0 all held · 1 an assertion failed · 2 could not measure. Prints counts. NOTHING HERE SAYS
HOW ANYTHING SOUNDS: which song the key-ons belong to, and how the cut feels, are the owner's
listening test.

Usage:
    python3 tools/clip_music_witness.py --rom s4.s2clip.bin --lst s4.s2clip.lst \\
        --manifest games/sonic4/data/clips/s2_ehz_cpz/clips.json
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
import loop_step_over_witness as L  # noqa: E402
import region_music_witness as RMW  # noqa: E402
import region_table as RT  # noqa: E402
import tunnel_run_witness as T  # noqa: E402
from song_load_mid_drum_witness import YmTap  # noqa: E402

BOOT_FRAMES = 240
PIN_FRAMES = T.PIN_FRAMES       # tunnel_run_witness's measured streaming settle
RUN_MARGIN = T.RUN_MARGIN       # start this far outside the corridor
RUN_OUT = 320                   # a run ends this far past the far mouth
RUN_MAX = 900                   # frames; a run that has not arrived by then is COULD NOT RUN
WIGGLE_DX = 48
WIGGLE_HOLD = 40                # > 2 * WIGGLE_DX / 16 px a frame: the camera catches up
WIGGLES = 4
SETTLE_FRAMES = 60
KEYON_WINDOW = 180
CH = {0: "FM1", 1: "FM2", 2: "FM3", 4: "FM4", 5: "FM5", 6: "FM6"}


class CouldNotRun(Exception):
    pass


async def drive(sock, syms, equs, act, valid, ym=False):
    b = BusClient(socket_path=sock, client_id="cmw", client_name="clip_music_witness")
    await b.connect()
    bus = L.Bus(b)
    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_YVEL, A_GSP = P + equs["SST_y_vel"], P + L.PLAYERV_GROUND_SPEED
    A_DBG = P + L.PLAYERV_DEBUG_FLAG
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    half_w = CRB.crossing_constants()[2]
    co = act.corridors[0]
    top = co.tunnel.ceiling_y if co.tunnel else 0
    clips = sorted(act.clips, key=lambda c: c.dst[0])
    a_right, b_left = clips[0].dst[0] + clips[0].dst[2], clips[1].dst[0]

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
    visits = []
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

    async def step(n, leg, pin=None):
        nonlocal frame
        for _ in range(n):
            if pin is not None:
                await bus.write(A_X, pin[0] << 16, 4)
                await bus.write(A_Y, pin[1] << 16, 4)
                await bus.write(A_YVEL, 0, 2)
            await bus.frames(1)
            frame += 1
            await poll()
            if tap:
                await tap.poll()
                ch = collections.Counter(CH.get(v & 7, "?") for _, _, part, reg, v in tap.events
                                         if v is not None and part == 0 and reg == 0x28
                                         and (v & 0xF0))
                if ch:
                    keyons[frame] = ch
                del tap.events[:]
            reg = int.from_bytes(await bus.read(syms["Region_Current"], 4), "big")
            cam = int.from_bytes(await bus.read(syms["Camera_X"], 4), "big") >> 16
            px = int.from_bytes(await bus.read(A_X, 4), "big") >> 16
            samples.append((frame, leg, reg, cam + half_w, px))
            if reg in valid and (not visits or visits[-1][1] != reg):
                visits.append((frame, reg, leg))

    async def alive(where):
        st = await bus.status()
        if "ErrorHandler" in (st.get("symbolAtPc") or ""):
            raise CouldNotRun(f"the ROM FAULTED during {where}: {st.get('symbolAtPc')!r}")

    def feet_at(x):
        return T.ground_y(act, x, top) - radius - 2

    async def run(button, gsp, until):
        await b.call("emulator/hold", {"buttons": [button], "down": True})
        await bus.write(A_GSP, gsp & 0xFFFF, 2)
        for _ in range(RUN_MAX):
            await step(1, button)
            px = samples[-1][4]
            if until(px):
                break
        else:
            raise CouldNotRun(f"the {button} run never arrived (last x {samples[-1][4]})")
        await b.call("emulator/hold", {"buttons": [button], "down": False})
        await alive(f"the {button} run")

    async def wiggle(x_line, leg):
        # strictly alternating: 2 * WIGGLES pins, each on the other side of the line
        for i in range(2 * WIGGLES):
            x = x_line - WIGGLE_DX if i % 2 == 0 else x_line + WIGGLE_DX
            await step(WIGGLE_HOLD, leg, pin=(x, feet_at(x)))
        await alive(leg)

    await step(BOOT_FRAMES, "boot")
    await alive("boot")
    if (await bus.read(A_DBG, 1))[0]:
        await b.call("emulator/press", {"buttons": ["b"]})
        await step(4, "boot")
    # place (tunnel_run_witness's order: camera and pinned player together)
    sx = a_right - RUN_MARGIN
    await bus.write(syms["Camera_X"], (sx - half_w) << 16, 4)
    await bus.write(syms["Camera_Y"], (feet_at(sx) - 112) << 16, 4)
    await step(PIN_FRAMES, "place", pin=(sx, feet_at(sx)))
    await step(L.LAND_FRAMES * 4, "place")
    await alive("placement")
    await run("right", equs["PHYS_TOP_SPEED"], lambda x: x >= b_left + RUN_OUT)
    await step(SETTLE_FRAMES, "right")
    await wiggle(b_left, "wig_r")
    sx = b_left + RUN_MARGIN
    await step(SETTLE_FRAMES, "place2", pin=(sx, feet_at(sx)))
    await step(L.LAND_FRAMES * 4, "place2")
    await run("left", -equs["PHYS_TOP_SPEED"], lambda x: x <= a_right - RUN_OUT)
    await step(SETTLE_FRAMES, "left")
    await wiggle(a_right, "wig_l")
    await step(SETTLE_FRAMES, "settle")
    await b.close()
    if dropped:
        raise CouldNotRun(f"the music-slot watch dropped {dropped} hit(s)")
    return {"events": events, "keyons": keyons, "samples": samples, "visits": visits,
            "tap_dropped": tap.dropped if tap else 0, "a_right": a_right, "b_left": b_left}


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
        for n in ("Region_Current", "Camera_X", "Camera_Y", RMW.ACT_SYMBOL):
            if n not in syms:
                raise CouldNotRun(f"{a.lst} carries no {n}")
        rom = Path(a.rom).read_bytes()
        rows = RT.read_regions(rom, syms[RMW.ACT_SYMBOL])
        act = CM.load(a.manifest)
        clips = sorted(act.clips, key=lambda c: c.dst[0])
        if len(clips) != 2 or not act.corridors:
            raise CouldNotRun("this reads a two-clip act with one corridor")
        ids = CRB.song_ids()
        want_song = [ids[c.music] for c in clips] if all(c.music for c in clips) else None
        if want_song is None:
            raise CouldNotRun("the manifest's clips name no music; nothing to witness")
        print(f"ROM {a.rom}: {len(rom)} B; {len(rows)} region rows: "
              + "; ".join(f"x {r['x0']}..{r['x1']} song {r['song']}" for r in rows))
        print(f"manifest: {clips[0].zone} plays {clips[0].music} ({want_song[0]}), "
              f"{clips[1].zone} plays {clips[1].music} ({want_song[1]})")
        valid = {r["addr"] for r in rows}
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            w = asyncio.run(drive(sock, syms, equs, act, valid))
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            y = asyncio.run(drive(sock, syms, equs, act, valid, ym=True))
    except CouldNotRun as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2

    by_addr = {r["addr"]: r for r in rows}
    a_right, b_left = w["a_right"], w["b_left"]
    sample_at = {s[0]: s for s in w["samples"]}
    requests = [(f, v) for f, via, v in w["events"] if via != "z80" and v != 0]
    zeros = [(f, v) for f, via, v in w["events"] if via != "z80" and v == 0]
    legs = collections.OrderedDict()
    for s in w["samples"]:
        legs.setdefault(s[1], [s[0], s[0]])[1] = s[0]
    print(f"corridor mouths: left x {a_right} (first corridor px), right x {b_left} "
          f"(first {clips[1].zone} px); legs (frames): "
          + ", ".join(f"{k} {v[0]}..{v[1]}" for k, v in legs.items()))
    leg_of = {s[0]: s[1] for s in w["samples"]}
    print("region visits (frame, row, leg): "
          + " ".join(f"{f}:{by_addr[r]['index']}:{lg}" for f, r, lg in w["visits"]))
    for f, v in requests:
        s = sample_at.get(f)
        print(f"  REQUEST song {v} at frame {f}, leg {leg_of.get(f)}: camera centre x {s[3]}, "
              f"player x {s[4]}, row {by_addr.get(s[2], {}).get('index', '?')}")
    fails = []
    # P1
    expect = [want_song[0], want_song[1], want_song[0]]
    got = [v for _, v in requests]
    per_leg = collections.Counter(leg_of.get(f) for f, _ in requests)
    print(f"P1 requests {got}, by leg {dict(per_leg)}; the ruling expects {expect} on legs "
          f"boot, right, left")
    if got != expect or [leg_of.get(f) for f, _ in requests] != ["boot", "right", "left"]:
        fails.append(f"P1 requests {got} on legs {[leg_of.get(f) for f, _ in requests]}, "
                     f"not {expect} on boot/right/left")
    if zeros:
        fails.append(f"68k wrote 0 to the music slot {len(zeros)} time(s)")
    # P2
    for f, v in requests:
        c = sample_at[f][3]
        if v == want_song[1] and not c >= b_left:
            fails.append(f"P2 song {v} requested at frame {f} with the camera centre at x {c}, "
                         f"not yet out of the corridor into {clips[1].zone} (x >= {b_left})")
        if v == want_song[0] and leg_of.get(f) != "boot" and not c < a_right:
            fails.append(f"P2 song {v} requested at frame {f} with the camera centre at x {c}, "
                         f"not yet out of the corridor into {clips[0].zone} (x < {a_right})")
        if a_right <= c < b_left:
            fails.append(f"P2 a request (song {v}, frame {f}) with the camera centre INSIDE "
                         f"the corridor (x {c})")
    # P3 — the premise, measured on the CAMERA (policy geometry), not on the ROM's rows: a ROM
    # whose rows put no edge at the mouth must still be wiggled across the mouth, so its
    # verdict comes from P1/P2 instead of hiding behind a premise
    for leg, line in (("wig_r", b_left), ("wig_l", a_right)):
        cs = [s[3] for s in w["samples"] if s[1] == leg]
        n = sum(1 for c0, c1 in zip(cs, cs[1:]) if (c0 < line) != (c1 < line))
        rc = sum(1 for f, _r, lg in w["visits"] if lg == leg)
        print(f"P3 {leg}: the camera centre crossed x {line} {n} time(s) while wiggling "
              f"({rc} region change(s))")
        if n < 2 * WIGGLES - 1:
            print(f"COULD NOT RUN: the {leg} wiggle crossed the song line only {n} time(s); "
                  f"it tested nothing")
            print("finished=1")
            return 2
    # M1
    model = RMW.model_posts([r for _f, r, _lg in w["visits"]],
                            {r["addr"]: r["song"] for r in rows})
    print(f"M1 model (the ROM's own table along the measured route) posts {model}")
    if got != model:
        fails.append(f"M1 the ROM posted {got}, its own table says {model}")
    # K1
    if [r for _f, r, _lg in w["visits"]] != [r for _f, r, _lg in y["visits"]]:
        fails.append("K1 the key-on run took a different region route; frames do not line up")
    if y["tap_dropped"]:
        print(f"  [the YM tap dropped {y['tap_dropped']} hit(s): key-on counts are LOWER BOUNDS]")
    k = y["keyons"]
    if requests:
        before = sum(sum(c.values()) for f, c in k.items() if f < requests[0][0])
        print(f"K1 key-ons before the first request: {before}")
        if before:
            fails.append(f"K1 {before} key-on(s) before any song was requested")
    for f, v in requests:
        win = collections.Counter()
        for g, c in k.items():
            if f <= g < f + KEYON_WINDOW:
                win.update(c)
        print(f"K1 song {v} requested at frame {f}: key-ons in the next {KEYON_WINDOW} "
              f"frames {sum(win.values())} {dict(sorted(win.items()))}")
        if not win:
            fails.append(f"K1 no key-on within {KEYON_WINDOW} frames of the request at {f}")
    for m in fails:
        print(f"FAIL: {m}")
    print("VERDICT:", "RED" if fails else "GREEN")
    print("finished=1")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
