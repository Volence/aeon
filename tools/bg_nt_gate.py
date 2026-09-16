#!/usr/bin/env python3
"""BG-NT-IDENTICAL — is the Plane B nametable the same picture before and after?

The regions part-2 steps rewrite how Plane B is filled (step 2 flips the blob and
both blits to row-major; steps 3-6 make them region-aware). Every one of those
steps claims THE PICTURE DOES NOT CHANGE, and a green build cannot say that: the
whole risk of a transpose is arithmetic that composes wrong and still assembles.

So this boots both ROMs and reads the live nametable out of the VDP, at two
sample points that exercise the two different blits:

  * BOOT      -- `BG_Init`'s one-shot fill.
  * AFTER WARP-- `Section_RedrawPlanes`' cache-recovery path, which is a
                 DIFFERENT piece of code writing the same region of VRAM.

A verdict names WHICH failure it is, because the two have opposite remedies:
a TRANSPOSE (cell (r,c) holding what belongs at (c,r)) is the arithmetic; a
STREAMING difference (contiguous whole rows, usually at a window edge) is the
frame count or the camera, and calls for a re-run at a second sample point
before anything is concluded.

WHAT A GREEN DOES NOT SAY: that the picture is RIGHT. Identical-to-before is the
whole assertion. If the before-picture is wrong, this gate passes on two wrong
pictures.
"""
import argparse
import asyncio
import sys
from pathlib import Path

import os
AEON = Path(os.environ.get("AEON_DIR", Path(__file__).resolve().parent.parent)).resolve()
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient                                      # noqa: E402
from aether_instance import (AetherInstance, SpawnError,          # noqa: E402
                             WrongServerError, read_bytes, unprefix)
from raster_cost_probe import parse_lst                           # noqa: E402

VRAM_PLANE_B = 0xE000     # engine/system/constants.emp VRAM_PLANE_B_BYTES
PLANE_B_BYTES = 8192      # 64 x 64 cells x 2 B
CELLS = 64
BOOT_FRAMES = 120         # PROCEDURE.md: identical to the frozen control's
WARP_ACK_FRAMES = 120
SETTLE = 30


class GateError(RuntimeError):
    pass


async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def read_plane_b(b) -> bytes:
    out = bytearray()
    for off in range(0, PLANE_B_BYTES, 4096):
        r = await _c(b, "emulator/read_vram",
                     {"addr": hex(VRAM_PLANE_B + off), "len": 4096})
        h = unprefix(r["bytes"])
        if len(h) != 8192:
            raise GateError("short VRAM read at +%d: %d hex chars, wanted 8192"
                            % (off, len(h)))
        out += bytes.fromhex(h)
    if len(out) != PLANE_B_BYTES:
        raise GateError("assembled %d bytes, wanted %d" % (len(out), PLANE_B_BYTES))
    return bytes(out)


async def rd(b, addr, width):
    return int(await read_bytes(b, addr, width), 16)


async def warp(b, sym, x, y):
    """The DEBUG warp mailbox (games/sonic4/config/ram.emp): X, Y, then the FLAG
    last -- the write order IS the protocol. Poll for the ack rather than
    assuming a frame budget covers it: a warp that never happened would leave
    this reading the boot picture twice and calling it a pass."""
    for nm, v, w in (("Warp_Req_X", x, 2), ("Warp_Req_Y", y, 2),
                     ("Warp_Req_Flag", 1, 1)):
        await _c(b, "emulator/write_memory",
                 {"addr": hex(sym[nm]), "value": v, "width": w})
    for _ in range(WARP_ACK_FRAMES):
        await _c(b, "emulator/run_frames", {"frames": 1})
        if await rd(b, sym["Warp_Req_Flag"], 1) == 0:
            return
    raise GateError("Warp_Req_Flag never cleared in %d frames -- the teleport did "
                    "not happen, so the second sample would be the first one again"
                    % WARP_ACK_FRAMES)


async def capture(rom, lst, warp_to):
    """Both samples from ONE boot of one ROM."""
    inst = AetherInstance(rom, symbols=lst)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise GateError(str(e)) from e
    b = BusClient(sock, client_id="bgnt", client_name="bg_nt_gate")
    await b.connect()
    try:
        for m in ("emulator/read_vram", "emulator/run_frames",
                  "emulator/read_memory", "emulator/write_memory"):
            if not b.supports(m):
                raise GateError("the server does not advertise `%s`" % m)
        await _c(b, "emulator/run_frames", {"frames": BOOT_FRAMES})
        boot = await read_plane_b(b)
        sym = parse_lst(lst)
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        cam0 = ((await rd(b, sym["Camera_X"], 4)) >> 16,
                (await rd(b, sym["Camera_Y"], 4)) >> 16)
        await warp(b, sym, *warp_to)
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        cam1 = ((await rd(b, sym["Camera_X"], 4)) >> 16,
                (await rd(b, sym["Camera_Y"], 4)) >> 16)
        # THE WARP LEG'S OWN NON-VACUITY. A warp that did not move the camera
        # leaves this reading the boot picture a second time and calling it a
        # pass -- the acked flag says the mailbox was consumed, not that the
        # machine went anywhere.
        if cam0 == cam1:
            raise GateError("the camera is at %r before AND after the warp -- the "
                            "second sample is the first one again, so this leg "
                            "measured nothing" % (cam0,))
        print("  %s camera %r -> %r across the warp" % (Path(rom).name, cam0, cam1))
        after = await read_plane_b(b)
        return boot, after
    finally:
        await b.close()
        inst.reap()


def cells(buf):
    return [int.from_bytes(buf[i * 2:i * 2 + 2], "big") for i in range(CELLS * CELLS)]


def verdict(a, b, label):
    if a == b:
        print("  %-12s IDENTICAL  (%d bytes)" % (label, len(a)))
        return True
    ca, cb = cells(a), cells(b)
    diff = [i for i in range(len(ca)) if ca[i] != cb[i]]
    mirrored = sum(1 for i in diff
                   if cb[i] == ca[(i % CELLS) * CELLS + (i // CELLS)])
    rows = sorted({i // CELLS for i in diff})
    contiguous = rows == list(range(rows[0], rows[-1] + 1))
    print("  %-12s DIFFERS  %d/%d cells, %d of %d mirrored, rows %d..%d%s"
          % (label, len(diff), len(ca), mirrored, len(diff), rows[0], rows[-1],
             " (contiguous)" if contiguous else ""))
    if mirrored == len(diff):
        print("     -> TRANSPOSE: every differing cell holds its mirror. The "
              "arithmetic, not the timing.")
    elif contiguous and len(diff) % CELLS == 0:
        print("     -> STREAMING: whole contiguous rows. RE-RUN BOTH SIDES at a "
              "second frame count before concluding anything.")
    else:
        print("     -> neither shape. Localise by hand.")
    return False


async def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before-rom", required=True)
    ap.add_argument("--before-lst", required=True)
    ap.add_argument("--after-rom", required=True)
    ap.add_argument("--after-lst", required=True)
    ap.add_argument("--blob", help="the committed zone_bg.bin, checked as a third leg")
    ap.add_argument("--warp-x", type=int, default=2048)
    ap.add_argument("--warp-y", type=int, default=512)
    a = ap.parse_args()

    print("BG-NT-IDENTICAL  (Plane B $E000, %d bytes, frame %d and after one warp)"
          % (PLANE_B_BYTES, BOOT_FRAMES))
    print("  BEFORE %s" % a.before_rom)
    print("  AFTER  %s" % a.after_rom)
    b_boot, b_warp = await capture(a.before_rom, a.before_lst, (a.warp_x, a.warp_y))
    a_boot, a_warp = await capture(a.after_rom, a.after_lst, (a.warp_x, a.warp_y))

    ok = True
    ok &= verdict(b_boot, a_boot, "boot")
    ok &= verdict(b_warp, a_warp, "after warp")

    # NON-VACUITY, stated rather than assumed: if the warp sample equals the boot
    # sample on BOTH sides, the second leg tested nothing the first did not.
    if b_boot == b_warp and a_boot == a_warp:
        print("  note: warp sample == boot sample on both sides. The recovery blit "
              "wrote the same picture, which is the claim -- but this leg adds no "
              "discrimination beyond the boot leg.")
    else:
        print("  note: the warp sample DIFFERS from the boot sample within a ROM, "
              "so the recovery blit is a distinct subject and this leg is not free.")

    if a.blob:
        blob = Path(a.blob).read_bytes()
        same = blob == a_boot
        print("  third leg: AFTER boot picture %s zone_bg.bin"
              % ("== " if same else "!= "))
        if not same and ok:
            print("     (before==after but neither matches the blob: an older "
                  "disagreement, not this parcel's)")
    print("VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
