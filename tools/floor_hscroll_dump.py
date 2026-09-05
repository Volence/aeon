#!/usr/bin/env python3
"""floor_hscroll_dump -- read the LIVE per-line HScroll table at the floor scene.

WHY. The explain-only parcel (docs/witness/floor-still-wrong-2026-09-05.md)
refuted four hypotheses including the one nobody thought to doubt: the owner's
picture is NOT our art under our MODELLED ramp. Best fit 6.67 px over 200,859
combinations, against a positive control through identical code that recovers a
synthetic case at 1.08 px. Its conclusion was that the cross seams, which are
scroll-invariant, match ours, while the lattice, which is scroll-dependent,
matches nothing: the art is ours and THE APPLIED SCROLL IS NOT WHAT WE MODEL.

It could not name the applied scroll because that needs the live table and a
background agent may not touch an emulator. This reads it. That is the whole
purpose: turn "not what we model" into "here is what it actually is".

It reports the table as DIFFERENCES between adjacent lines as well as absolute
values, because the shear is what matters and the absolute value carries a whole
frame offset that says nothing about the fan.

WHY A SINGLE READ OF THIS TABLE IS VALID, WHICH IS NOT TRUE OF EVERY VDP READ.
Oracle found (2026-09-05) that every instrument resolving against ONE VDP state
is blind to mid-frame writes by construction: constant phase down the screen,
identical columns per row and "no shearing table found" are all exactly what a
mid-frame fan produces through such an instrument, so three independent-looking
results shared one blind spot and their agreement read as corroboration.

This tool is safe from that, but by a property of OUR engine rather than of the
method, and the distinction is the point. The hscroll table is DMA'd from
Hscroll_Buffer in VBlank (engine/system/buffers.emp, "the ONE table"), and the
raster interpreter never touches it: engine/effects/raster_dsl.emp writes only
CRAM (7 sites) and VSRAM (2). So the table the VDP fetches for every line of a
frame is the table one read returns.

THE SAME CANNOT BE SAID OF A CRAM OR VSRAM READ HERE. `OP_PAL_REGION` streams
CRAM mid-frame and `fx_vscroll_split` writes VSRAM mid-frame, so a single-state
read of either shows the last write and not what the frame drew. Anything asking
what the SCREEN showed must read the drawn raster and require source == "raster";
a reply of source == "stateRender" is a post-hoc render that cannot witness a
per-line effect at all, and it fails by showing a clean picture.

VRAM_HSCROLL_TABLE is $BC00 (engine/system/constants.emp:403) and the buffer is
896 bytes = 224 lines x 4 (plane A word then plane B word, per the VDP's
per-line format). The floor is Plane B, so plane B is the column to read; plane A
is dumped beside it because a mismatch between them is itself diagnostic.
"""
import argparse
import asyncio
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))

import perspective_floor_witness as w  # noqa: E402
from aether import BusClient           # noqa: E402
from aether_instance import (          # noqa: E402
    AetherInstance, SpawnError, WrongServerError, read_bytes, unprefix)

HSCROLL = 0xBC00            # engine/system/constants.emp:403
LINES = 224


async def run(rom, lst, extra):
    inst = AetherInstance(rom)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise w.WitnessError(str(e)) from e
    client = BusClient(sock, client_id="hsdump", client_name="floor_hscroll_dump")
    await client.connect()
    try:
        await w._c(client, "emulator/run_frames", {"frames": w.BOOT_FRAMES})
        lab = w.lst_symbol(lst, "Debug_Lab_Index")
        cam = w.lst_symbol(lst, "Camera_X")
        if lab is None:
            raise w.WitnessError("Debug_Lab_Index not in %s; refusing to walk blind" % lst)
        w.LAB_ROW  # noqa: B018
        await w.walk_to_floor_row(client, lab)
        await w._c(client, "emulator/run_frames", {"frames": 30})
        if extra:
            await w._c(client, "emulator/play_input",
                       {"rows": [{"start": 0, "end": extra,
                                  "buttons": ["right"], "port": 0}]})
            await w._c(client, "emulator/run_frames", {"frames": 4})
        again = int((await read_bytes(client, lab, 1))[:2], 16)
        if again != w.LAB_ROW:
            raise w.WitnessError("cursor moved to %d before the read" % again)
        camx = int(await read_bytes(client, cam, 2), 16) if cam else None

        r = await w._c(client, "emulator/read_vram",
                       {"addr": hex(HSCROLL), "len": LINES * 4})
        h = unprefix(r["bytes"])
        a, b = [], []
        for i in range(LINES):
            wa = int(h[i * 8:i * 8 + 4], 16)
            wb = int(h[i * 8 + 4:i * 8 + 8], 16)
            a.append(wa - 0x10000 if wa > 0x7FFF else wa)
            b.append(wb - 0x10000 if wb > 0x7FFF else wb)
        print("  camera x %s, lab row %d verified at read time" % (camx, again))
        print("  line : planeA planeB   dB(adjacent)")
        for ln in range(140, LINES, 4):
            db = b[ln] - b[ln - 1] if ln else 0
            print("   %3d : %6d %6d   %+d" % (ln, a[ln], b[ln], db))
        floor = [b[i] - b[i - 1] for i in range(153, LINES)]
        uniq = sorted(set(floor))
        print("  plane B adjacent differences over floor lines 153..223:")
        print("    distinct values: %s" % uniq)
        print("    sum %d over %d rows, mean %.3f px/row"
              % (sum(floor), len(floor), sum(floor) / len(floor)))
        nz = sum(1 for d in floor if d)
        print("    rows with a nonzero step: %d of %d" % (nz, len(floor)))
        return True
    finally:
        try:
            await client.close()
        except Exception:
            pass
        try:
            inst.stop()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--extra-right-frames", type=int, default=0)
    a = ap.parse_args()
    try:
        ok = asyncio.run(run(a.rom, a.lst, a.extra_right_frames))
    except w.WitnessError as e:
        print("  NOT MEASURED: %s" % e)
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
