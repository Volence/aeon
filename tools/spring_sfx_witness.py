#!/usr/bin/env python3
"""spring_sfx_witness — does hitting a spring actually play sfx $B1?

THE CLAIM UNDER TEST is not "SFXID_SPRING is in the listing" and not "sfx_B1.bin
is in the ROM". It is that a real player meeting a real spring in real level data
causes the sound API to be entered with the spring's id, and that the driver then
CONSUMES that request rather than dropping it on a full ring.

There is no audio instrument to point at this. Oracle's Rust core exposes no
audio method (its bus has none — checked, not assumed), so nothing here renders a
waveform and this file makes no claim about what the spring SOUNDS like. What it
can establish is the whole software path up to the driver's own queue, which is
where the responsibility of this parcel ends: the BYTES of the sound were fixed
by tools/sfx_transcode.py and are gated separately by tools/test_sfx_bank_wiring.py
(the id -> blob -> win-tab-cell chain).

THREE LEGS, and the count is asserted so a leg that silently did not run cannot
read as a leg that passed:

  L1 LAUNCH FIRES IT   drop the player onto the up spring at (160,584); the run
                       stops INSIDE Sound_PlaySFX and d0 holds SFXID_SPRING.

  L2 THE RING TOOK IT  the id really lands in Sfx_Ring_Buf, and the read cursor
                       then catches the write cursor — the driver drained it. A
                       request that is queued and never consumed is a silent
                       no-sound, and L1 alone cannot tell those apart.

  C1 NOT FREE-RUNNING  the CONTROL: from the same boot, WITHOUT going near a
                       spring, Sound_PlaySFX is never entered with SFXID_SPRING
                       across a comparable window. Without this leg L1 would not
                       distinguish "the spring plays it" from "something plays it
                       every frame", which is exactly what an AF_SOUND placed in
                       the IDLE script instead of the fire script would do -- and
                       that mistake builds green and sounds like a stuck buzzer.

RUN:  python3 tools/spring_sfx_witness.py [--rom s4.debug.bin] [--lst s4.debug.lst]
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, unprefix  # noqa: E402

SETTLE_FRAMES = 40
DROP_FRAMES = 240          # generous: the fall plus the contact frame
CONTROL_FRAMES = 240       # the control window, same order as the drive


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


def parse_syms(lst):
    """-> ({label: addr}, {equ_name: value}) — the .lst's two namespaces."""
    syms, equs = {}, {}
    for line in open(lst, errors="replace"):
        m = re.match(r"^EQU (\w+) = \$?([0-9A-Fa-f]+)", line)
        if m:
            equs[m.group(1)] = int(m.group(2), 16)
            continue
        m = re.match(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+(\w+):", line)
        if m:
            syms.setdefault(m.group(2), int(m.group(1), 16))
    return syms, equs


async def rd(b, addr, n):
    """Raw bytes from the 68k bus. The address is masked to 24 bits: the listing
    spells RAM labels as $FFFFxxxx (the 68000's sign-extended short form) and the
    bus rejects anything wider than its 24 real address lines. Reads MEMORY, not `emulator/player_state` —
    that reply's field names are the emulator's, and spring_launch_witness reads
    the SST directly for the same reason: the offsets come from the listing."""
    return bytes.fromhex(unprefix(await read_bytes(b, addr & 0xFFFFFF, n)))


def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


def reg_d0(regs):
    """d0's low byte. `emulator/registers` returns register values as hex STRINGS
    ("0x000000B1"), not ints — reading it as an int silently TypeErrors here and
    would silently compare wrong if it were coerced with str()."""
    v = regs.get("d0", regs.get("D0", 0))
    if isinstance(v, str):
        v = int(v.replace("0x", "").replace("$", ""), 16)
    return v & 0xFF


async def player_y(b, syms, equs):
    """The player's integer Y (the high word of his 16.16 Coord)."""
    return s16(int.from_bytes(await rd(b, syms["Player_1"] + equs["SST_y_pos"], 2), "big"))


async def boot_to_act(b, syms, equs, out):
    """Reach a running act with physics live. Mirrors spring_launch_witness."""
    await b.call("emulator/run_frames", {"frames": 240})
    y0 = await player_y(b, syms, equs)
    await b.call("emulator/run_frames", {"frames": 8})
    if await player_y(b, syms, equs) == y0:
        out.append(f"  player is not falling at y={y0} — pressing B to leave debug-fly")
        await b.call("emulator/press", {"buttons": ["b"]})
        await b.call("emulator/run_frames", {"frames": 8})
        y1 = await player_y(b, syms, equs)
        if y1 == y0:
            raise Unmeasurable(
                f"the player is still frozen at y={y0} after a B press — nothing in "
                "this run would be physics")
        out.append(f"  after B: y {y0} -> {y1}, physics is running")
    await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})


async def main_async(sock, rom, lst, out):
    b = BusClient(socket_path=sock, client_id="springsfx",
                  client_name="spring_sfx_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    syms, equs = parse_syms(lst)

    for need in ("Sound_PlaySFX", "Sfx_Ring_Buf", "Sfx_Ring_Wr", "Sfx_Ring_Rd"):
        if need not in syms:
            raise Unmeasurable(f"{need} is not in {lst} — wrong ROM/listing pair?")
    if "SFXID_SPRING" not in equs:
        raise Unmeasurable(
            f"SFXID_SPRING has no EQU in {lst} — the spring's sound is not wired "
            "into this build at all, so there is nothing here to measure")
    want = equs["SFXID_SPRING"]
    play = syms["Sound_PlaySFX"]
    ring, wr_p, rd_p = syms["Sfx_Ring_Buf"], syms["Sfx_Ring_Wr"], syms["Sfx_Ring_Rd"]
    out.append(f"  SFXID_SPRING = ${want:02X} (from the listing's own EQU, not this file)")
    out.append(f"  Sound_PlaySFX ${play:06X}, Sfx_Ring_Buf ${ring:08X}")

    fails, legs = [], []

    # ---------------- L1 + L2: the launch fires it, the ring takes it -------
    await b.call("emulator/reset", {})
    await boot_to_act(b, syms, equs, out)

    # Seat the player above the UP spring the level already places at (160,584)
    # and let gravity do the rest — no velocity poke, so the contact is the
    # engine's own.
    sx, sy = 160, 584
    await b.call("emulator/write_memory", {
        "addr": hex((syms["Player_1"] + equs["SST_x_pos"]) & 0xFFFFFF),
        "bytes": "0x" + f"{sx << 16:08X}"})
    await b.call("emulator/write_memory", {
        "addr": hex((syms["Player_1"] + equs["SST_y_pos"]) & 0xFFFFFF),
        "bytes": "0x" + f"{(sy - 120) << 16:08X}"})
    await b.call("emulator/write_memory", {
        "addr": hex((syms["Player_1"] + equs["SST_x_vel"]) & 0xFFFFFF), "bytes": "0x00000000"})
    out.append(f"L1 LAUNCH FIRES IT: dropped from y={sy-120} onto the up spring at ({sx},{sy})")

    r = await b.call("emulator/run_to", {"addr": hex(play), "maxFrames": DROP_FRAMES})
    stopped = (r.get("stopped") or r.get("hit") or
               (r.get("pc") is not None and int(str(r["pc"]).replace("0x", ""), 16) == play))
    if not stopped:
        fails.append("L1: Sound_PlaySFX was never entered during the drop — the spring "
                     "fired no sound at all")
        out.append(f"  L1: FAILED — run_to did not stop at Sound_PlaySFX: {r}")
    else:
        regs = await b.call("emulator/registers", {})
        d0 = reg_d0(regs)
        out.append(f"  L1: stopped inside Sound_PlaySFX with d0 = ${d0:02X}")
        if d0 != want:
            fails.append(f"L1: Sound_PlaySFX entered with ${d0:02X}, not SFXID_SPRING "
                         f"${want:02X} — the spring is playing the WRONG sound")
        else:
            out.append(f"  L1: d0 == SFXID_SPRING ${want:02X} — the launch plays the spring")
        legs.append("L1 launch fires it")

        # L2 — let the request land and be drained.
        await b.call("emulator/run_frames", {"frames": 4})
        buf = await rd(b, ring, 8)
        wr = (await rd(b, wr_p, 1))[0]
        rdc = (await rd(b, rd_p, 1))[0]
        out.append(f"L2 THE RING TOOK IT: Sfx_Ring_Buf = {buf.hex(' ')}  Wr={wr} Rd={rdc}")
        if want not in buf:
            fails.append(f"L2: ${want:02X} never appeared in Sfx_Ring_Buf — "
                         f"Sound_PlaySFX was entered but the id was not queued")
        else:
            out.append(f"  L2: ${want:02X} is in the ring at slot {buf.index(want)}")
        if wr != rdc:
            fails.append(f"L2: the ring did not drain (Wr={wr} != Rd={rdc}) — the "
                         f"request is queued but the driver never consumed it, "
                         f"which is a silent no-sound")
        else:
            out.append(f"  L2: Rd caught Wr at {wr} — the driver CONSUMED the request")
        legs.append("L2 the ring took it")

    # ---------------- C1: the control ---------------------------------------
    await b.call("emulator/reset", {})
    await boot_to_act(b, syms, equs, out)
    cy = await player_y(b, syms, equs)
    cx = s16(int.from_bytes(await rd(b, syms["Player_1"] + equs["SST_x_pos"], 2), "big"))
    out.append(f"C1 NOT FREE-RUNNING: the player is where the level put him "
               f"(x={cx}, y={cy}) and is not touched again")
    seen = []
    remaining = CONTROL_FRAMES
    while remaining > 0:
        r = await b.call("emulator/run_to", {"addr": hex(play), "maxFrames": remaining})
        hit = (r.get("stopped") or r.get("hit") or
               (r.get("pc") is not None and
                int(str(r["pc"]).replace("0x", ""), 16) == play))
        if not hit:
            break
        regs = await b.call("emulator/registers", {})
        seen.append(reg_d0(regs))
        used = r.get("frames", 1) or 1
        remaining -= used
        await b.call("emulator/run_frames", {"frames": 1})
        remaining -= 1
    out.append(f"  C1: Sound_PlaySFX entered {len(seen)} time(s) in "
               f"{CONTROL_FRAMES} frames with ids "
               f"{sorted({f'${v:02X}' for v in seen}) or 'none'}")
    if want in seen:
        fails.append(f"C1: SFXID_SPRING ${want:02X} played WITHOUT the player touching a "
                     f"spring — the AF_SOUND is firing off the idle script, not the "
                     f"fire script (a stuck buzzer)")
    else:
        out.append(f"  C1: ${want:02X} never played — the sound belongs to the LAUNCH")
    legs.append("C1 not free-running")

    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 3:
        fails.append(f"only {len(legs)} of 3 legs ran — an unrun leg is not a pass")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    out = []
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            fails = asyncio.run(main_async(sock, a.rom, a.lst, out))
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nUNMEASURABLE: {e}")
        return 2
    print("\n".join(out))
    if fails:
        print("\nRESULT: FAIL")
        for f in fails:
            print(f"  * {f}")
        return 1
    print("\nRESULT: PASS — 3 legs (2 drives + 1 control): a drop onto the up spring "
          f"enters Sound_PlaySFX with SFXID_SPRING, the id reaches Sfx_Ring_Buf and the "
          f"driver drains it, and the same id never plays from an untouched spring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
