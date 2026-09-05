#!/usr/bin/env python3
"""fg_hscroll_witness — is the FOREGROUND still one plane, in every section of an act?

WHAT IT MEASURES, AND WHY THAT NUMBER. `Hscroll_Buffer` holds 224 line entries of
(FG word, BG word). Plane A — the foreground the player collides with — must carry
EXACTLY `-Camera_X` on all 224 lines, so `max(FG) - min(FG)` must be 0. That is not a
style preference, it is the engine's own standing rule, written at the two places that
enforce it:

  * engine/level/parallax.emp, Parallax_Update's band loop: *"Plane A (factor_a) is
    HARD-LOCKED to its factor-derived target — never lerped. The FG streaming engine
    draws columns in a camera-anchored 64-col window, so any FG scroll offset from the
    camera drags the plane-wrap seam into view at the screen edge."*
  * engine/level/scene_dsl.emp, SceneDrift's banner: *"BG ONLY, AND THAT IS A REFUSAL BY
    REPRESENTATION RATHER THAN A GUARD ... There is no plane-A field, so the mistake is
    unspellable instead of diagnosed."*

SceneDrift closed that door by having no plane-A field. `layer(fa: ...)` is the OTHER
door to the same offset and it has no guard, so this witness is the only thing in the
tree that can see through it. A nonzero FG span is the foreground torn into horizontal
bands sliding past each other and past the collision map.

THE BG SPAN IS REPORTED BESIDE IT AND IS *NOT* A FAULT. A background curve is exactly
what a per-band `fb` with `curve:` is for; the number is here so a reader can tell a
sheared background (legal, authored, several shipped sections have one) apart from a
torn foreground (not legal anywhere).

THIS IS A WITNESS, NOT A GATE. It always exits 0 when it could measure and 2 when it
could not; it prints numbers and never a verdict. It is deliberately not wired into
tools/effects_gates.py: as of 2026-09-05 it is RED on master (section 7 of OJZ act 1,
FG span 2485) and the fix is content, not code, so wiring it now would only paint the
gate lane red for something no engine change closes. Wire it — with the derived
expectation `fg_span == 0`, which needs no pinned number — once the content is fixed.

HOW IT GETS THERE. Every destination is reached through the WARP MAILBOX
(`Warp_Req_X`/`Warp_Req_Y`/`Warp_Req_Flag`), never by writing `Camera_X`/`Camera_Y`.
A direct camera write of section size trips EntityWindow's DEBUG single-axis slide
invariant (`assert.w d1, eq` in EntityWindow_Slide, engine/objects/entity_window.emp)
and halts into the debugger — that assert holds because the camera moves at most 16 px
per frame in play, which a placement does not.

`--drive` additionally crosses one seam ON A MOVING CAMERA rather than arriving by
placement, so a defect that only exists in the placed state can be told from one that
is a property of the section.

USAGE
    python3 tools/fg_hscroll_witness.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/fg_hscroll_witness.py --rom R --lst L --drive 3000,3800,down,300

RUN IT FOREGROUND. It boots a headless emulator through tools/aether_instance.py;
oracle from a background agent deadlocks, and this never touches the owner's window.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient                 # noqa: E402
from aether_instance import aether_emulator  # noqa: E402
from raster_cost_probe import parse_lst      # noqa: E402

SETTLE_FRAMES = 180      # boot -> gameplay, the tree-wide constant (warp_mailbox_gate's)
HSCROLL_LINES = 224      # engine/ram.emp: Hscroll_Buffer is 224 lines x 4 bytes


class SetupError(Exception):
    """Could not measure. Exit 2 — never a verdict."""


def _hexb(s) -> bytes:
    s = str(s)
    return bytes.fromhex(s[2:] if s.startswith(("0x", "0X")) else s)


def _s16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


class Probe:
    def __init__(self, bus: BusClient, sym: dict):
        self.b, self.sym = bus, sym

    async def call(self, method: str, params: dict, timeout: float = 120.0):
        return await asyncio.wait_for(self.b.call(method, params), timeout=timeout)

    async def read(self, addr: int, n: int) -> bytes:
        out = b""
        while len(out) < n:
            k = min(n - len(out), 4096)
            r = await self.call("emulator/read_memory", {"addr": hex(addr + len(out)), "len": k})
            out += _hexb(r["bytes"])
        return out

    async def long(self, name: str) -> int:
        return int.from_bytes(await self.read(self.sym[name], 4), "big")

    async def word(self, name: str) -> int:
        return int.from_bytes(await self.read(self.sym[name], 2), "big")

    async def write_word(self, name: str, value: int) -> None:
        await self.call("emulator/write_memory",
                        {"addr": hex(self.sym[name]), "value": value, "width": 2})

    async def write_byte(self, name: str, value: int) -> None:
        await self.call("emulator/write_memory",
                        {"addr": hex(self.sym[name]), "value": value, "width": 1})

    async def warp(self, x: int, y: int) -> None:
        """The sanctioned reposition. See the module docstring for why not Camera_X."""
        await self.write_word("Warp_Req_X", x)
        await self.write_word("Warp_Req_Y", y)
        await self.write_byte("Warp_Req_Flag", 1)
        for _ in range(120):
            await self.call("emulator/run_frames", {"frames": 1})
            if int.from_bytes(await self.read(self.sym["Warp_Req_Flag"], 1), "big") == 0:
                return
        raise SetupError(f"Warp_Req_Flag never cleared warping to ({x},{y})")

    async def sample(self) -> dict:
        cx = (await self.long("Camera_X")) >> 16
        cy = (await self.long("Camera_Y")) >> 16
        hs = await self.read(self.sym["Hscroll_Buffer"], HSCROLL_LINES * 4)
        fg = [_s16(int.from_bytes(hs[i * 4:i * 4 + 2], "big")) for i in range(HSCROLL_LINES)]
        bg = [_s16(int.from_bytes(hs[i * 4 + 2:i * 4 + 4], "big")) for i in range(HSCROLL_LINES)]
        return {
            "cam": (cx, cy),
            "sec": (cx >> 11, cy >> 11),          # SECTION_SIZE_SHIFT = 11
            "fg": fg, "bg": bg,
            "fg_span": max(fg) - min(fg),
            "bg_span": max(bg) - min(bg),
            "fg_want": -cx,                        # the value every line must carry
            "fg_bands": _bands(fg),
            "vscroll_bg": await self.word("Parallax_Current_Vscroll_BG"),
        }


def _bands(vals: list[int]) -> list[tuple[int, int, int]]:
    """Collapse a per-line list into (first_line, last_line, value) runs."""
    out, start = [], 0
    for i in range(1, len(vals) + 1):
        if i == len(vals) or vals[i] != vals[start]:
            out.append((start, i - 1, vals[start]))
            start = i
    return out


async def body(sock: str, rom: str, lst: str, args) -> int:
    sym = parse_lst(lst)
    needed = ["Camera_X", "Camera_Y", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag",
              "Hscroll_Buffer", "Parallax_Current_Vscroll_BG"]
    missing = sorted(n for n in needed if n not in sym)
    if missing:
        raise SetupError(f"symbols did not resolve in {lst}: {missing}")

    b = BusClient(socket_path=sock, client_id="fghsw", client_name="fg_hscroll_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    p = Probe(b, sym)

    blob = Path(rom).read_bytes()
    st = await p.call("emulator/status", {})
    if st["romBytes"] != len(blob):
        raise SetupError(f"server serves {st['romBytes']} bytes, {rom} is {len(blob)} — "
                         f"refusing to measure a different ROM")
    print(f"ROM {rom}  {len(blob)} bytes  sha256 {hashlib.sha256(blob).hexdigest()[:12]}")
    print(f"server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")

    await p.call("emulator/run_frames", {"frames": SETTLE_FRAMES})

    print("\n  dest        camera         sec    Vscroll_BG   FG span   BG span   FG line0 / -camX")
    torn = []
    for spec in args.dest:
        name, x, y = spec.split(",")
        await p.warp(int(x), int(y))
        await p.call("emulator/run_frames", {"frames": args.settle})
        s = await p.sample()
        flag = "  <-- FG TORN" if s["fg_span"] else ""
        print(f"  {name:10s} ({s['cam'][0]:5d},{s['cam'][1]:5d})  {s['sec']}   "
              f"{s['vscroll_bg']:6d}    {s['fg_span']:6d}    {s['bg_span']:6d}   "
              f"{s['fg'][0]:7d} / {s['fg_want']:6d}{flag}")
        if s["fg_span"]:
            torn.append((name, s))

    for (name, s) in torn:
        print(f"\n  {name}: plane A is in {len(s['fg_bands'])} horizontal bands "
              f"(every line should read {s['fg_want']}):")
        for (lo, hi, v) in s["fg_bands"]:
            print(f"      lines {lo:3d}..{hi:3d}  FG hscroll {v:6d}   "
                  f"offset from camera {v - s['fg_want']:+6d} px")

    if args.drive:
        x, y, hold, frames = args.drive.split(",")
        print(f"\n--- seam crossing on a MOVING camera: start ({x},{y}), hold {hold}, "
              f"{frames} frames ---")
        await p.warp(int(x), int(y))
        await p.call("emulator/run_frames", {"frames": args.settle})
        s = await p.sample()
        print(f"  start camera={s['cam']} sec={s['sec']}  FG span {s['fg_span']}  "
              f"BG span {s['bg_span']}")
        print("\n  frame   camera         sec    FG span   BG span")
        stride = args.stride
        for step in range(int(frames) // stride):
            await p.call("emulator/play_input",
                         {"rows": [{"start": 0, "end": stride, "buttons": [hold]}],
                          "maxFrames": stride})
            await p.call("emulator/release_all", {})
            s = await p.sample()
            print(f"  {(step + 1) * stride:5d}   ({s['cam'][0]:5d},{s['cam'][1]:5d})  "
                  f"{s['sec']}   {s['fg_span']:6d}    {s['bg_span']:6d}")

    print(f"\nsections measured: {len(args.dest)}; foreground torn in {len(torn)} of them"
          f"{': ' + ', '.join(n for n, _ in torn) if torn else ''}")
    return 0


# OJZ act 1 is a 3x3 grid of 2048-px sections; these land the camera inside each of the
# five that bind a scene or a raster document, plus two plain ones for contrast. They are
# WARP TARGETS (player position), and the camera settles ~112 px above the request.
DEFAULT_DESTS = ["sec0,256,256", "sec4,3000,3000", "sec5,5100,3000",
                 "sec6,900,5100", "sec7,3000,5100", "sec8,5100,5100"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=60,
                    help="frames to let the section settle after each warp")
    ap.add_argument("--stride", type=int, default=10, help="--drive sample interval, frames")
    ap.add_argument("--dest", action="append", metavar="NAME,X,Y",
                    help="warp destination; repeatable. Defaults to OJZ act 1's grid.")
    ap.add_argument("--drive", metavar="X,Y,BUTTON,FRAMES",
                    help="after the sweep, warp to X,Y and hold BUTTON for FRAMES, "
                         "sampling the span every --stride frames")
    args = ap.parse_args()
    if not args.dest:
        args.dest = DEFAULT_DESTS
    for f in (args.rom, args.lst):
        if not os.path.isfile(f):
            print(f"SETUP: {f} does not exist", file=sys.stderr)
            return 2
    try:
        with aether_emulator(args.rom, symbols=args.lst) as sock:
            return asyncio.run(body(sock, args.rom, args.lst, args))
    except SetupError as e:
        print(f"SETUP: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
