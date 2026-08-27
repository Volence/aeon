#!/usr/bin/env python3
"""sfx_audition — post an SFX id into a RUNNING emulator's sound ring, so you can hear it.

WHY THIS EXISTS. Some sounds cannot be reached by playing. Knuckles' `$7E` ground slide
fires from `Slide_Terrain`, which lives on the glide path — and Knuckles currently ships
with `Ability_None` (glide and climb are unbuilt), so nothing in normal play can make that
sound happen. `$42` insta-shield and `$B6` dash are reachable but fiddly to trigger on
demand and impossible to repeat identically.

The alternative a previous session reached for was a side-built `sfx_test.bin` in a
scratchpad. That has two problems: it is a DIFFERENT ARTIFACT from the ROM we freeze and
ship, and being in a scratchpad it was invisible to every later session — which is exactly
how an owner ended up auditioning a stale copy of the previous build and concluding a fix
had not worked.

This tool avoids both. It posts into the SAME ring the game itself posts into
(`Sound_PlaySFX` -> `Sfx_Ring_Buf`), on the SHIPPED ROM, in an emulator that is already
running with audio. What you hear is the shipping code path, not a harness approximation.

HOW THE RING WORKS (`engine/sound/sound_api.emp`): `Sound_PlaySFX` writes the id at
`Sfx_Ring_Buf[Sfx_Ring_Wr]` and advances `Sfx_Ring_Wr` under `SFX_RING_MASK`. The driver
drains from `Sfx_Ring_Rd`. Posting is therefore two writes, in that order — the id first,
the cursor second, so the consumer never sees a cursor pointing at a byte not yet written.

ADDRESSES ARE DERIVED FROM THE .lst, never hard-coded: a pinned address silently aims at
the wrong RAM the moment the layout moves, and this tool would then post into unrelated
memory and report success.

USAGE
    python3 tools/sfx_audition.py --list
    python3 tools/sfx_audition.py dash
    python3 tools/sfx_audition.py insta-shield ground-slide --gap 1.5
    python3 tools/sfx_audition.py 0x42 --socket /tmp/oracle-aeon-fixed.sock
"""
import argparse
import asyncio
import os
import re
import sys
import time

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
from aether import BusClient  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOCKET = "/tmp/oracle-aeon-fixed.sock"
DEFAULT_LST = os.path.join(REPO, "s4.debug.lst")

# Names are a convenience; the id is the authority. Kept in step with
# games/sonic4/config/sound_ids.emp — `--list` prints both so a drifted name is visible.
NAMED = {
    "dash":         (0xB6, "spindash release — the PSG should sweep DOWNWARD, not sit flat"),
    "insta-shield": (0x42, "Sonic's double-jump attack — two pitches, sweep on the second"),
    "ground-slide": (0x7E, "Knuckles' glide landing — unreachable in play today"),
    "spindash-rev": (0xAB, "the rev charge, for comparison — unchanged by this parcel"),
    "ring":         (0x33, "regression check — unchanged, should sound exactly as before"),
    "jump":         (0x62, "regression check — unchanged"),
    "skid":         (0x36, "regression check — unchanged"),
}

RING_SYMBOLS = ("Sfx_Ring_Buf", "Sfx_Ring_Wr", "Sfx_Ring_Rd")
RING_MASK = 0x07  # SFX_RING_DEPTH-1; see engine/sound/sound_constants.emp


def resolve(lst_path):
    """Map the three ring symbols to 24-bit bus addresses, out of the listing."""
    want = {s: None for s in RING_SYMBOLS}
    pat = re.compile(r"^\s*(\w+)\s*:\s*([0-9A-Fa-f]{6,8})\b")
    with open(lst_path, "r", errors="replace") as fh:
        for line in fh:
            m = pat.match(line)
            if m and m.group(1) in want and want[m.group(1)] is None:
                # The 68k bus is 24 bits on the Rust core: 0xFFFF0000 is refused outright,
                # and 0xFF0000 is the same byte. Mask rather than pass the listing's form.
                want[m.group(1)] = int(m.group(2), 16) & 0xFFFFFF
    missing = [s for s, v in want.items() if v is None]
    if missing:
        raise SystemExit(f"{lst_path}: could not resolve {missing} — wrong listing, or the "
                         f"ring was renamed; refusing to post to a guessed address")
    return want


async def post(client, sym, sfx_id, was_running):
    """One `Sound_PlaySFX`-equivalent post: id byte first, then the cursor.

    The core refuses `write_memory` on a running machine (-32005), so this pauses around
    the two writes and restores the previous run state. The pause is a few milliseconds and
    the ring is drained by the driver afterwards, so the sound still plays normally — but
    it does mean the machine must be RUNNING to hear anything, hence the check in `body`.
    """
    if was_running:
        await client.call("emulator/pause", {})
    r = await client.call("emulator/read_memory", {"addr": hex(sym["Sfx_Ring_Wr"]), "len": 1})
    wr = int(str(r["bytes"]).removeprefix("0x"), 16) & RING_MASK
    await client.call("emulator/write_memory",
                      {"addr": hex(sym["Sfx_Ring_Buf"] + wr), "value": sfx_id, "width": 1})
    await client.call("emulator/write_memory",
                      {"addr": hex(sym["Sfx_Ring_Wr"]), "value": (wr + 1) & RING_MASK, "width": 1})
    if was_running:
        await client.call("emulator/resume", {})
    return wr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sounds", nargs="*", help="names (see --list) or numeric ids like 0x42")
    ap.add_argument("--socket", default=DEFAULT_SOCKET)
    ap.add_argument("--lst", default=DEFAULT_LST)
    ap.add_argument("--gap", type=float, default=1.2, help="seconds between sounds")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.sounds:
        print("name           id     what to listen for")
        for n, (i, why) in NAMED.items():
            print(f"  {n:<13} 0x{i:02X}   {why}")
        return 0

    ids = []
    for s in args.sounds:
        if s in NAMED:
            ids.append((s, NAMED[s][0]))
        else:
            try:
                ids.append((s, int(s, 0)))
            except ValueError:
                raise SystemExit(f"unknown sound {s!r} — try --list")

    sym = resolve(args.lst)
    print("ring: " + "  ".join(f"{k}=0x{v:06X}" for k, v in sym.items()))

    async def body():
        c = BusClient(args.socket)
        await c.connect()
        st = await c.call("emulator/status", {})
        # The stale-ROM trap this tool was written after: an emulator can be serving a
        # completely different build while everything else looks right. Say what is loaded,
        # every time, so the listener can never be auditioning the wrong bytes unknowingly.
        print(f"rom:  {st['romPath']}  ({st['romBytes']} bytes)")
        was_running = bool(st.get("running"))
        if not was_running:
            print("note: the machine is PAUSED — resume it or you will hear nothing")
        for name, i in ids:
            slot = await post(c, sym, i, was_running)
            print(f"  posted 0x{i:02X} ({name}) into ring slot {slot}")
            if len(ids) > 1:
                time.sleep(args.gap)

    asyncio.run(body())
    return 0


if __name__ == "__main__":
    sys.exit(main())
