#!/usr/bin/env python3
"""floor_capture -- put the perspective floor on screen and SAVE THE PICTURE.

WHY THIS EXISTS SEPARATELY FROM perspective_floor_witness. The witness proves
the ROM carries the fan by exact byte comparison against plane B and VRAM, which
is the stronger evidence and is what a gate should assert. It does not produce
anything the OWNER can look at, and the owner's question about this floor has
always been a look question ("the first few are good then a few after get weird
and point away"). This walks the same lab and screenshots.

IT REUSES THE WITNESS'S WALK RATHER THAN REIMPLEMENTING IT, and that is the
whole point of the file. Hand-driving the chord over MCP does not work and fails
in a way that looks like success: consecutive presses with no released frames
between them do not re-trigger the edge, so the cursor silently STOPS ADVANCING
while every press call returns OK. Measured 2026-09-05: eight consecutive presses
moved the cursor zero rows and reported success eight times. The witness already
solved this (2-frame hold, 2-frame release, retry, and verify Debug_Lab_Index
after every single step), so this imports that function instead of guessing at
hold lengths.

It also refuses to shoot a frame it cannot vouch for: the lab cursor is READ BACK
and compared before the screenshot, because a picture of the wrong row is exactly
the artifact that would be mistaken for evidence.
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
    AetherInstance, SpawnError, WrongServerError, read_bytes)


async def run(rom, lst, out, extra_frames):
    inst = AetherInstance(rom)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise w.WitnessError(str(e)) from e
    client = BusClient(sock, client_id="fcap", client_name="floor_capture")
    await client.connect()
    try:
        if not client.supports("emulator/screenshot"):
            raise w.WitnessError("the server does not advertise "
                                 "`emulator/screenshot`; nothing to capture")
        await w._c(client, "emulator/run_frames", {"frames": w.BOOT_FRAMES})

        lab_sym = w.lst_symbol(lst, "Debug_Lab_Index")
        cam_sym = w.lst_symbol(lst, "Camera_X")
        if lab_sym is None:
            raise w.WitnessError("Debug_Lab_Index is not in %s; refusing to "
                                 "walk blind" % lst)
        row = await w.walk_to_floor_row(client, lab_sym)
        await w._c(client, "emulator/run_frames", {"frames": 30})

        if extra_frames:
            # Optional extra travel so a second shot sits at a different camera
            # x. Held RIGHT only -- no START, so the lab cursor cannot move.
            await w._c(client, "emulator/play_input",
                       {"rows": [{"start": 0, "end": extra_frames,
                                  "buttons": ["right"], "port": 0}]})
            await w._c(client, "emulator/run_frames", {"frames": 4})

        # VOUCH FOR THE FRAME BEFORE SHOOTING IT.
        again = int((await read_bytes(client, lab_sym, 1))[:2], 16)
        if again != w.LAB_ROW:
            raise w.WitnessError("cursor moved to %d before the capture" % again)
        cam = (int(await read_bytes(client, cam_sym, 2), 16)
               if cam_sym else None)

        r = await w._c(client, "emulator/screenshot", {"path": str(out)})
        print("  lab row %d verified at shoot time" % again)
        print("  camera x %s" % ("unknown" if cam is None else cam))
        print("  saved %s" % (r.get("path") or out))
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
    ap.add_argument("--out", required=True)
    ap.add_argument("--extra-right-frames", type=int, default=0,
                    help="hold RIGHT this many frames after selecting the row, "
                         "to move the camera for a second viewpoint")
    a = ap.parse_args()
    try:
        ok = asyncio.run(run(a.rom, a.lst, a.out, a.extra_right_frames))
    except w.WitnessError as e:
        print("  NOT CAPTURED: %s" % e)
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
