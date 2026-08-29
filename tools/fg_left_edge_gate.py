#!/usr/bin/env python3
"""fg_left_edge_gate — the column-19 borrow, asserted against the running machine.

WHAT IT GATES. With per-column V-scroll on (VDP reg $0B bit 2) and a plane's HScroll off
the 16-px grain, that plane's leading sliver renders at `VSRAM[$4C] & VSRAM[$4E]` — the
bitwise AND of column-pair 19's two words, the same value for both planes, H40 only.
That is Eke-Eke's hardware test (PAL MD2, 2010), and it is what Genesis Plus GX and Oracle
both implement. `Parallax_Step5_Vscroll`'s column-19 borrow exists to make that AND come
out equal to the FOREGROUND's V-scroll. So the gate's question is exactly:

    (VSRAM[$4C] & VSRAM[$4E]) & $7FF  ==  (Camera_Y >> 16) & $7FF

on every scene that raises the mode bit. Both sides are read out of the SAME frame of the
SAME running machine — the expectation is the engine's own camera, never a pinned number,
so it re-derives itself at whatever camera position the run happens to reach.

WHY THIS AND NOT PIXELS. Reading the pixels back would put Oracle's renderer between the
subject and the verdict, and Oracle's model of this quirk carries a KNOWN interim
divergence (its partial-column extent is a flat 16 px where hardware and GPGX say
`hscroll & 15`; oracle's own `plane_vscroll` comment and its divergence ledger P4 both say
so). The VSRAM half of the rule has no such divergence: it is `vsram_word(38) &
vsram_word(39)` in Oracle and `vs[19] & (vs[19] >> 16)` in GPGX, character for character
the same arithmetic. Asserting the value the rule consumes is therefore a stricter test of
OUR code than asserting the pixels the rule produces.

It still reads the machine, not the source: the path it covers is producer -> column
buffer -> `Vscroll_Write` -> VSRAM, end to end. A fix that filled the buffer correctly and
never shipped it would be red here.

WHAT IT CANNOT SEE, stated because a gate that hides its blind spot is worse than none.
If the AND rule is wrong about real silicon, this gate is green while the screen is still
broken. There is exactly one controlled hardware test on that rule in the public record,
it is sixteen years old, and it was run on a PAL Model 2. See
docs/research/2026-08-29-vsram-column19-borrow.md §2. The pixel table this gate prints
alongside its verdict is a MEASUREMENT, not an assertion, for exactly that reason —
terrain makes left-edge occupancy noisy (the 2026-08-27 run found transient one-row
shortfalls at x=24 and x=32 that are terrain, not the defect), so encoding it as pass/fail
would be a tripwire with a false-red every time the camera stops somewhere awkward.

LOUD ON UNMEASURABLE. Every way this run can fail to reach its subject is a FAILURE, never
a zero and never a green: the scene cursor not landing where it was driven, reg $0B bit 2
clear at the sample point, the server serving a different ROM, a symbol that will not
resolve. Two of those manufactured a false negative on 2026-08-27 — the DEBUG warp clears
bit 2, and travelling re-applies the section's own scene while `Debug_Scene_Index` still
reads 10 — so the mode bit is re-read at every sample point and never inferred from the
cursor.

POISON (what must make it red). Delete the one instruction the borrow is:

    engine/level/parallax.emp, Parallax_Step5_Vscroll, end of the Step-5b fill:
        move.w  d1, Parallax_Vscroll_Column_Buf + VSCROLL_COL19_BG_OFF

Rebuild `DEBUG=1 ./build.sh` and re-run. Every sampled scene must fail with

    FAIL scene NN: the leftmost partial column will render at V-scroll $XXX, not $YYY

where `$YYY` is `(Camera_Y >> 16) & $7FF` and `$XXX` is the AND. With the borrow gone,
VSRAM[$4E] carries plane B's own scroll, and on all six shipped per-column scenes plane B
is vertically LOCKED (`v_factor: 15, v_offset: 0`), so that word is 0 or a small deform
sample — which makes the AND collapse to near zero while `expected` is the live camera Y.
Expect `and=$0000..$00xx` against a three-digit `expected`. The gate prints all four
numbers (`vsram4C`, `vsram4E`, `and`, `expected`) on the failing line so the poison's
signature is visible rather than inferred.

USAGE
    python3 tools/fg_left_edge_gate.py                       # all six per-column scenes
    python3 tools/fg_left_edge_gate.py --scenes 12           # one
    python3 tools/fg_left_edge_gate.py --travel 240          # hold RIGHT first (pixel table)
    python3 tools/fg_left_edge_gate.py --rom s4.debug.bin --settle 240

RUN IT FOREGROUND. It boots a headless emulator; oracle from a background agent deadlocks.
"""
import argparse
import asyncio
import os
import sys
import zlib

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The six scenes that attach SceneVDeform.Columns, i.e. the only ones that raise reg $0B
# bit 2 — Rocking_Slow/Rocking/Rocking_Fast and Perspective_Subtle/Perspective/_Dramatic.
# Indices into SCENES[]; the cycle order is the registry's own.
DEFAULT_SCENES = [10, 11, 12, 13, 14, 15]

# VSRAM is 11 bits wide on the write path (the VDP masks $07FF), so the comparison is over
# the bits the chip actually stores. Wider would fail on a value the hardware never kept;
# narrower would pass on a value it did.
VSRAM_MASK = 0x7FF

# VDP reg $0B (Mode Set 3), bit 2 = per-column V-scroll.
VDP_MODE3_OFF = 0x0B
VDP_MODE3_PERCOL = 0x04

# Corroborating pixel table only. Left edge = the fix; right edge = what it costs.
FG_COLS = [0, 8, 16, 24]
BG_COLS = [280, 288, 296, 304, 312]
ROW_RANGE = (96, 216, 8)


def _int(v):
    s = str(v)
    return int(s.removeprefix("0x"), 16) if s.lower().startswith("0x") else int(s, 16)


async def read_bus(client, *, symbol=None, addr=None, length=1):
    p = {"len": length}
    if symbol is not None:
        p["symbol"] = symbol
    else:
        p["addr"] = hex(addr)
    r = await client.call("emulator/read", p)
    return int(str(r["bytes"]).removeprefix("0x"), 16)


async def read_vsram(client, addr, length):
    r = await client.call("emulator/read", {"space": "vsram", "addr": hex(addr), "len": length})
    raw = str(r["bytes"]).removeprefix("0x")
    return bytes.fromhex(raw)


async def lookup(client, name):
    try:
        r = await client.call("emulator/lookup_symbol", {"name": name})
    except Exception as exc:  # noqa: BLE001 — an unresolvable symbol is unmeasurable, not zero
        raise SystemExit(f"UNMEASURABLE: symbol {name!r} did not resolve ({exc}). The gate cannot "
                         f"locate its subject; refusing to report a verdict") from exc
    return _int(r["addr"])


async def step_scene(client):
    """One forward step of the effects-lab cursor: START held, RIGHT pressed on one frame.

    The hotkey is edge-triggered on the direction and gated on START being HELD, so the
    step needs a frame with both and at least one frame with START alone for the next
    edge to exist. Held-only frames on either side keep the chord unambiguous.
    """
    await client.call("emulator/play_input", {
        "rows": [
            {"start": 0, "end": 2, "buttons": ["start"]},
            {"start": 2, "end": 3, "buttons": ["start", "right"]},
            {"start": 3, "end": 8, "buttons": ["start"]},
        ],
        "maxFrames": 8,
    })
    await client.call("emulator/release_all", {})
    await client.call("emulator/run_frames", {"frames": 4})


async def sample_plane(client, layer, cols, rows):
    out = {}
    for y in rows:
        for x in cols:
            r = await client.call("emulator/pixel_attribution", {"x": x, "y": y})
            c = next((c for c in r["candidates"] if c["layer"] == layer), None)
            out[(x, y)] = None if c is None else bool(c["opaque"])
    return out


def render(title, grid, cols, rows):
    print(f"      {title}   (# opaque, . transparent, ? candidate absent)")
    print("        " + "".join(f"x={x:<5}" for x in cols))
    for y in rows:
        cells = "".join(
            f"{('#' if grid[(x, y)] is True else ('.' if grid[(x, y)] is False else '?')):<7}"
            for x in cols
        )
        print(f"        y={y:<4}" + cells)


async def check_scene(client, syms, index, want_pixels):
    """Return (ok, message). Every unmeasurable condition returns ok=False."""
    cursor = await read_bus(client, addr=syms["Debug_Scene_Index"], length=1)
    if cursor != index:
        return False, (f"UNMEASURABLE scene {index}: the effects-lab cursor reads {cursor} after "
                       f"being driven to {index}. The scene was never installed, so nothing here "
                       f"measures the subject")

    mode3 = await read_bus(client, addr=syms["VDP_Shadow_Table"] + VDP_MODE3_OFF, length=1)
    if not mode3 & VDP_MODE3_PERCOL:
        return False, (f"UNMEASURABLE scene {index}: VDP reg $0B reads ${mode3:02X} — bit 2 "
                       f"(per-column V-scroll) is CLEAR at the sample point, so the leftmost "
                       f"partial column quirk cannot occur and this run proves nothing. Never "
                       f"trust the scene cursor: the DEBUG warp clears bit 2 and travelling "
                       f"re-applies the section's own scene")

    cam_y_raw = await read_bus(client, addr=syms["Camera_Y"], length=4)
    cam_y = (cam_y_raw >> 16) & 0xFFFF            # Camera_Y is 16.16; the engine swaps for pixels
    expected = cam_y & VSRAM_MASK

    vs = await read_vsram(client, 0x4C, 4)
    a19 = (vs[0] << 8) | vs[1]                    # VSRAM $4C — column-pair 19, plane A
    b19 = (vs[2] << 8) | vs[3]                    # VSRAM $4E — column-pair 19, plane B
    and_val = (a19 & b19) & VSRAM_MASK

    detail = (f"vsram4C=${a19:04X} vsram4E=${b19:04X} and=${and_val:03X} "
              f"expected=${expected:03X} (Camera_Y={cam_y}, reg$0B=${mode3:02X})")

    if (a19 & VSRAM_MASK) != expected:
        return False, (f"FAIL scene {index}: column-pair 19's PLANE-A word is not the foreground's "
                       f"V-scroll — the column buffer's FG words disagree with Camera_Y, so the "
                       f"borrow has nothing correct to borrow. {detail}")
    if and_val != expected:
        return False, (f"FAIL scene {index}: the leftmost partial column will render at V-scroll "
                       f"${and_val:03X}, not ${expected:03X}. VSRAM[$4C] & VSRAM[$4E] is what the "
                       f"VDP uses there (H40, hardware-tested), and it does not equal the "
                       f"foreground's V-scroll. {detail}")

    msg = f"ok   scene {index}: leftmost partial column renders the foreground's V-scroll. {detail}"
    if want_pixels:
        rows = list(range(ROW_RANGE[0], ROW_RANGE[1] + 1, ROW_RANGE[2]))
        fg = await sample_plane(client, "planeA", FG_COLS, rows)
        bg = await sample_plane(client, "planeB", BG_COLS, rows)
        print(f"  {msg}")
        print("      --- MEASUREMENT ONLY, not asserted (terrain makes edge occupancy noisy) ---")
        render("plane A, LEFT edge — what the borrow fixes", fg, FG_COLS, rows)
        render("plane B, RIGHT edge — what the borrow costs (col 19 now carries the FG's V-scroll)",
               bg, BG_COLS, rows)
        return True, None
    return True, msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--symbols", default=None)
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--travel", type=int, default=0,
                    help="frames to hold RIGHT before sampling (moves the camera off the boot "
                         "position; only affects the pixel table, never the assertion)")
    ap.add_argument("--scenes", default=",".join(str(s) for s in DEFAULT_SCENES))
    ap.add_argument("--pixels", action="store_true",
                    help="also print the plane-A/plane-B edge occupancy tables")
    args = ap.parse_args()

    rom = os.path.abspath(args.rom)
    symbols = args.symbols or (rom[:-4] + ".lst")
    scenes = sorted(int(s) for s in args.scenes.split(",") if s.strip())

    with open(rom, "rb") as fh:
        blob = fh.read()
    print(f"ROM   {rom}")
    print(f"      {len(blob)} bytes, crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")
    print(f"      scenes {scenes}")

    inst = AetherInstance(rom, symbols=symbols)
    sock = inst.start()
    failures = []

    async def body():
        c = BusClient(sock)
        await c.connect()
        st = await c.call("emulator/status", {})
        if st["romBytes"] != len(blob):
            raise SystemExit(f"UNMEASURABLE: server serves {st['romBytes']} bytes, {rom} is "
                             f"{len(blob)} — refusing to gate a different ROM")
        print(f"      server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")

        syms = {}
        for name in ("Debug_Scene_Index", "Camera_Y", "VDP_Shadow_Table"):
            syms[name] = await lookup(c, name)

        await c.call("emulator/run_frames", {"frames": args.settle})
        if args.travel:
            await c.call("emulator/play_input",
                         {"rows": [{"start": 0, "end": args.travel, "buttons": ["right"]}],
                          "maxFrames": args.travel})
            await c.call("emulator/release_all", {})
            await c.call("emulator/run_frames", {"frames": 30})

        at = await read_bus(c, addr=syms["Debug_Scene_Index"], length=1)
        for index in scenes:
            while at != index:
                await step_scene(c)
                nxt = await read_bus(c, addr=syms["Debug_Scene_Index"], length=1)
                if nxt == at:
                    raise SystemExit(
                        f"UNMEASURABLE: the effects-lab cursor did not advance from {at} "
                        f"(START+RIGHT produced no step). The hotkey needs a DEBUG shape and live "
                        f"input (Input_Source == 0); gating on a shape that has no scene cycle "
                        f"would report green having tested nothing")
                at = nxt
            ok, msg = await check_scene(c, syms, index, args.pixels)
            if msg:
                print(f"  {msg}")
            if not ok:
                failures.append(index)

    try:
        asyncio.run(body())
    finally:
        inst.reap()

    print()
    if failures:
        print(f"RED   {len(failures)} of {len(scenes)} scenes failed: {failures}")
        return 1
    print(f"GREEN {len(scenes)} of {len(scenes)} scenes: the leftmost partial column renders the "
          f"foreground's V-scroll")
    return 0


if __name__ == "__main__":
    sys.exit(main())
