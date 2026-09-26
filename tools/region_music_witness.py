#!/usr/bin/env python3
"""region_music_witness — does a region crossing post exactly the music requests the region
table says it should, and no others? (S2CLIP-REGION-MUSIC step 5, 2026-09-25.)

THE SUBJECT. `Region.rg_song` (engine/structs.emp) names a region's song (0 = none: leave the
music alone). `Parallax_CheckBoundary`'s slow path (engine/level/parallax.emp) records a
non-zero one in `Music_Want`; `Music_Service` (engine/sound/sound_api.emp, once a frame from
GameLoop) posts `Sound_PlayMusic` when `Music_Want != Music_Current` and the Z80's music slot
is free, then sets `Music_Current`.

THE INSTRUMENT. A record-mode bus watch on the Z80 RAM byte `MUSIC_SLOT` (the `.lst`'s EQU,
68k address $A0xxxx). Every music request the 68k makes (Sound_PlayMusic's trigger,
Sound_StopMusic's $FF) is a 68000 write of a NON-ZERO byte to that address, `via != "z80"`;
the driver's consume is a Z80 write of 0. So "a music request" here is a measured bus event,
not a code path inferred from a PC. Headless: an oracle-aether subprocess, never MCP.

THE ROUTE (`--route`). `fly` (default): the DEBUG shape boots into debug free flight
(PLAYER_DEBUG_FLY_SPEED px a tick), so a held RIGHT then a held LEFT flies the camera across region
edges out and back. The plain shape has no free flight, and a held RIGHT there never leaves row 0
(measured 2026-09-25: Sonic is stopped inside the first region for all 700 frames), so `pin`
walks the table instead: the player's position is written to each row's centre, in table order
and back again, every frame for PIN_FRAMES frames per row, and the camera follows him across
every edge in between. Either way every frame samples `Region_Current`, so the crossings are
MEASURED, and the verdict is taken over the measured sequence, not the intended one.

THE EXPECTATION IS DERIVED, NOT TYPED. `model_posts()` replays the mechanism over the ROM's own
region table (tools/region_table.py) along the MEASURED sequence of regions: a region with a
non-zero song sets want; a post happens when want != current (then current = want). The slot
probe can only DELAY a post, never add or drop one, so the multiset of posted ids must equal
the model's exactly. On a canonical ROM every row's song is 0 and the model says ZERO posts.

FIXTURE MODE (`--song-row K --song N`): the tool writes a COPY of the ROM with row K's rg_song
byte set to N (the ROM on disk is untouched) and runs the same route on it. That is the
positive control: a row naming an existing song must post it exactly once on first entry and
never again while the song is current, and a 0 row must post nothing. The fixture route's
PREMISES are asserted: row K is entered at least twice, and a song-0 row is entered between
two entries of row K (so the already-playing compare is actually exercised, not assumed).
`--song-row auto` picks the second distinct region the route enters.

Exit 0 every assertion held · 1 an assertion failed · 2 could not measure (no crossing, a
fault, a missing symbol). Prints counts only. NOTHING HERE SAYS HOW ANYTHING SOUNDS.

Usage:
    python3 tools/region_music_witness.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/region_music_witness.py --rom s4.debug.bin --lst s4.debug.lst \\
        --song-row auto --song 1
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator  # noqa: E402
import region_table as rt  # noqa: E402
from song_load_mid_drum_witness import YmTap  # noqa: E402

BOOT_FRAMES = 240
OUT_FRAMES = 700       # held RIGHT
BACK_FRAMES = 700      # then held LEFT
ACT_SYMBOL = "OJZ_Act1_Descriptor"
PIN_FRAMES = 150       # per row on the `pin` route: > a 16 px/frame camera's ~1,400 px trip


class CouldNotRun(Exception):
    pass


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
    need = [n for n in ("Region_Current", ACT_SYMBOL) if n not in syms]
    need += [n for n in ("MUSIC_SLOT", "SST_x_pos", "SST_y_pos") if n not in equs]
    need += [n for n in ("Player_1",) if n not in syms]
    if need:
        raise CouldNotRun(f"{path} carries no {', '.join(need)}")
    return syms, equs


def model_posts(visits, song_of):
    """The mechanism restated: `visits` is the measured sequence of Region* the camera stood
    in (one entry per change, starting with the start region). Returns the ids it must post,
    in order. Music_Want / Music_Current start at 0 (Parallax_Init clears both)."""
    want = cur = 0
    posts = []
    for r in visits:
        s = song_of.get(r, 0)
        if s:
            want = s
        if want != cur:
            posts.append(want)
            cur = want
    return posts


async def drive(sock, syms, equs, valid, ym=False, route="fly", rows=()):
    b = BusClient(socket_path=sock, client_id="rmw", client_name="region_music_witness")
    await b.connect()
    slot = equs["MUSIC_SLOT"]

    async def rd32(addr):
        r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": 4})
        s = r["bytes"]
        s = s[2:] if s[:2].lower() == "0x" else s
        return int(s, 16)

    # ONE WATCH PER RUN. The server's hit ring is shared: with the YM tap armed beside the slot
    # watch, the DAC stream overflowed it (measured: 33,328 dropped) and the slot count could no
    # longer be called complete. So the request count comes from a run with the slot watch
    # alone (drop-gated), and the key-on evidence from a SECOND run of the same route with the
    # YM tap alone (`ym=True`); the headless machine is deterministic, so both runs see the
    # same frames.
    handle = None
    if not ym:
        w = await b.call("emulator/watchpoint_add", {"addr": hex(slot), "len": 1, "write": True,
                                                      "read": False, "mode": "record",
                                                      "label": "music_slot", "space": "bus"})
        handle = w["watch"]
    cursor = None
    events = []          # (frame, via, value)
    dropped = 0

    async def poll(frame):
        nonlocal cursor, dropped
        while handle is not None:
            p = {"watch": handle, "limit": 100}
            if cursor is not None:
                p["cursor"] = str(cursor)
            r = await b.call("emulator/watchpoint_hits", p)
            hits = r.get("hits", [])
            for h in hits:
                cursor = h["seq"]
                val = int(str(h["value"]).replace("0x", ""), 16) & 0xFF
                events.append((frame, h.get("via"), val))
            dropped = r.get("dropped", dropped)
            if len(hits) < 100:
                return

    async def status_ok(where):
        st = await b.call("emulator/status", {})
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            raise CouldNotRun(f"the ROM FAULTED during {where}: symbolAtPc={sym!r} "
                              f"pc={st.get('pc')}")

    # The Z80's consume (it clears the slot from its OWN side) is not a bus event, and this
    # slice cannot read Z80 RAM, so "the request reached the driver" is measured one step
    # further on: the Z80's YM key-ons (register $28, key bits set), through the same port
    # tap tools/song_load_mid_drum_witness.py uses, counted per frame.
    tap = YmTap(b) if ym else None
    if tap:
        await tap.arm()
    keyons = {}          # frame -> key-on count

    visits, trace = [], []
    frame = 0

    async def step(n, leg, pin=None):
        nonlocal frame
        for _ in range(n):
            if pin is not None:
                for off, v in ((equs["SST_x_pos"], pin[0]), (equs["SST_y_pos"], pin[1])):
                    await b.call("emulator/write_memory",
                                 {"addr": hex((syms["Player_1"] + off) & 0xFFFFFF),
                                  "value": v << 16, "width": 4})
            await b.call("emulator/run_frames", {"frames": 1})
            frame += 1
            await poll(frame)
            if tap:
                await tap.poll()
                k = sum(1 for _, _, part, reg, val in tap.events
                        if val is not None and part == 0 and reg == 0x28 and (val & 0xF0))
                if k:
                    keyons[frame] = k
                del tap.events[:]
            reg = await rd32(syms["Region_Current"])
            # Region_Current is uninitialised RAM until the level init's Parallax_Init; only
            # a value that IS a row of this ROM's table counts as a visit.
            if reg in valid and (not visits or visits[-1] != reg):
                visits.append(reg)
                trace.append((frame, leg, reg))

    await step(BOOT_FRAMES, "boot")
    await status_ok("boot")
    if route == "fly":
        await b.call("emulator/hold", {"buttons": ["right"], "down": True})
        await step(OUT_FRAMES, "right")
        await b.call("emulator/hold", {"buttons": ["right"], "down": False})
        await status_ok("the RIGHT leg")
        await b.call("emulator/hold", {"buttons": ["left"], "down": True})
        await step(BACK_FRAMES, "left")
        await b.call("emulator/hold", {"buttons": ["left"], "down": False})
        await status_ok("the LEFT leg")
    else:
        order = list(rows) + list(rows)[-2::-1]
        for r in order:
            await step(PIN_FRAMES, f"pin{r['index']}",
                       pin=((r["x0"] + r["x1"]) // 2, (r["y0"] + r["y1"]) // 2))
            await status_ok(f"the pin at row {r['index']}")
    await step(60, "settle")
    await b.close()
    if dropped:
        raise CouldNotRun(f"the music-slot watch dropped {dropped} hit(s); the count is not "
                          "complete")
    if tap and tap.dropped:
        print(f"  [the YM tap dropped {tap.dropped} hit(s): key-on counts are LOWER BOUNDS]")
    return visits, trace, events, keyons


def run(rom, lst, rows, ym=False, route="fly"):
    syms, equs = parse_lst(lst)
    valid = {r["addr"] for r in rows}
    with aether_emulator(rom, symbols=lst) as sock:
        return asyncio.run(drive(sock, syms, equs, valid, ym, route, rows)), syms


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--song-row", help="fixture: region row index to give a song, or 'auto'")
    ap.add_argument("--song", type=int, default=1, help="fixture: the song id (default 1)")
    ap.add_argument("--route", choices=("fly", "pin"), default="fly")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    try:
        rom_bytes = Path(a.rom).read_bytes()
        syms, _ = parse_lst(a.lst)
        rows = rt.read_regions(rom_bytes, syms[ACT_SYMBOL])
        print(f"ROM {a.rom}: {len(rom_bytes)} B, {len(rows)} region rows, "
              f"songs named: {sorted({r['song'] for r in rows})}")
        subject_rom = a.rom
        tmp = None
        fixture_row = None
        if a.song_row is not None:
            if a.song_row == "auto":
                # a dry run on the unpatched ROM names the route's second distinct region
                (visits0, _, _, _), _ = run(a.rom, a.lst, rows, route=a.route)
                if len(visits0) < 2:
                    raise CouldNotRun("the route entered fewer than two regions; no fixture "
                                      "row to pick")
                fixture_row = next(r for r in rows if r["addr"] == visits0[1])
            else:
                fixture_row = rows[int(a.song_row)]
            if any(r["song"] for r in rows):
                raise CouldNotRun("fixture mode needs a ROM whose rows all name song 0")
            patched = bytearray(rom_bytes)
            off, _ = rt.region_layout()
            patched[fixture_row["addr"] + off["rg_song"]] = a.song
            fd, tmp = tempfile.mkstemp(suffix=".bin", prefix="region_music_fixture_")
            os.write(fd, bytes(patched))
            os.close(fd)
            subject_rom = tmp
            print(f"FIXTURE: row {fixture_row['index']} (x {fixture_row['x0']}..{fixture_row['x1']},"
                  f" y {fixture_row['y0']}..{fixture_row['y1']}) rg_song := {a.song}, written to "
                  f"a copy ({tmp}); the ROM on disk is untouched")
            rows = rt.read_regions(bytes(patched), syms[ACT_SYMBOL])
        try:
            (visits, trace, events, _), _ = run(subject_rom, a.lst, rows, route=a.route)
            keyons, ym_visits = {}, None
            if fixture_row is not None:
                (ym_visits, _, _, keyons), _ = run(subject_rom, a.lst, rows, ym=True,
                                                   route=a.route)
        finally:
            if tmp:
                os.unlink(tmp)
    except CouldNotRun as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2

    by_addr = {r["addr"]: r for r in rows}
    song_of = {r["addr"]: r["song"] for r in rows}
    idx = [by_addr[v]["index"] if v in by_addr else f"?{v:06X}" for v in visits]
    print(f"route: {len(visits)} region visit(s) (row indices, in order): {idx}")
    if a.verbose:
        for f, leg, reg in trace:
            print(f"  frame {f:5d} {leg:6s} -> row {by_addr.get(reg, {}).get('index', '?')}")
    requests = [(f, v) for f, via, v in events if via != "z80" and v != 0]
    other = [(f, via, v) for f, via, v in events if via != "z80" and v == 0]
    print(f"music slot: {len(requests)} 68k request(s) {[v for _, v in requests]} at frames "
          f"{[f for f, _ in requests]}; {len(other)} 68k zero write(s)")
    if fixture_row is not None:
        print(f"YM key-ons (Z80, the second run): {sum(keyons.values())}"
              + (f", first at frame {min(keyons)}" if keyons else "")
              + f"; its route {'MATCHES' if ym_visits == visits else 'DIFFERS FROM'} the first")

    fails = []
    if len(visits) < 2:
        print("COULD NOT RUN: the route crossed no region edge, so it tested nothing")
        print("finished=1")
        return 2
    want = model_posts(visits, song_of)
    print(f"model (derived from the ROM's table along the measured route): posts {want}")
    if [v for _, v in requests] != want:
        fails.append(f"the ROM posted {[v for _, v in requests]}, the table says {want}")
    if other:
        fails.append(f"68k wrote 0 to the music slot {len(other)} time(s): nothing should")
    if fixture_row is not None:
        k = fixture_row["addr"]
        entries = [i for i, v in enumerate(visits) if v == k]
        between = len(entries) >= 2 and any(song_of.get(visits[j], 0) == 0
                                            for j in range(entries[0] + 1, entries[1]))
        print(f"fixture premises: row {fixture_row['index']} entered {len(entries)} time(s); "
              f"a song-0 row between two entries: {between}")
        if len(entries) < 2 or not between:
            print("COULD NOT RUN: the route did not re-enter the fixture row through a song-0 "
                  "row, so the already-playing compare was not exercised")
            print("finished=1")
            return 2
        if want != [a.song]:
            fails.append(f"the model itself expects {want}, not exactly one {a.song}: the "
                         "fixture is not the control it claims to be")
        if requests:
            f0 = requests[0][0]
            before = sum(v for f, v in keyons.items() if f < f0)
            after = sum(v for f, v in keyons.items() if f >= f0)
            print(f"  first request at frame {f0}; Z80 key-ons before it {before}, from it on "
                  f"{after}")
            if ym_visits != visits:
                fails.append("the key-on run took a different route; its frames do not line up")
            if after == 0:
                fails.append("no YM key-on followed the request: the driver never started "
                             "the song")
    for m in fails:
        print(f"FAIL: {m}")
    print("VERDICT:", "RED" if fails else "GREEN")
    print("finished=1")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
