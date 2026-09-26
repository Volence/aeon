#!/usr/bin/env python3
"""General-regime witness: fly the S2 clip's Chemical Plant legs past the bounded regime, to a halt.

WHY IT EXISTS (GPL-A3, 2026-09-27; stage 2 of docs/research/2026-09-27-general-patch-loop.md).
Every shipped act latches a direct patch regime, so the page cache's GENERAL regime (the
liveness-mask barrier, the idle sweep, PageCache_PickVictim's eviction and the sliced
general-regime audit) runs on no canonical shape: neither tools/landing_build.sh nor a
canonical nightly lane executes it. The two-zone S2 clip act (`S2CLIP=s2_ehz_cpz`) is the one
built shape that streams past its bulk-loaded block: it leaves the bounded regime when the
camera nears Chemical Plant's own pages and stays general for the rest of the act. This
witness flies it there, in the DEBUG shape, where the audit checks the liveness invariant
per word, and fails on any halt.

WHAT IT RUNS. Two legs, each on a FRESH private headless `oracle-aether`
(tools/aether_instance.py, which also proves the cart is the file on disk): settle for
BOOT_FRAMES, hold RIGHT in DEBUG free flight, and at camera x >= SWITCH_X turn to the leg's
second heading (DOWN, or RIGHT+DOWN), stepping ONE EMULATED FRAME at a time for LEG_FRAMES
frames. SWITCH_X is the design parcel's turn (x 14400, inside Chemical Plant's first 4576 px,
x 11360..15935 in the clip manifest); the painted rows it flies down through are where the
general loop's cost was measured.

A HALT is the game loop stopping: `Logic_Tick` unchanged for HALT_FRAMES consecutive frames
(a lag frame misses one tick, never 60). On a halt the witness prints the leg, the frame, the
camera and the raise_error message recovered from RAM (tools/stressart_legs_witness.py's
recovery, imported), and exits 1.

A LEG THAT CANNOT FAIL IS NOT A LEG. Measured per leg, and any one missing is UNMEASURABLE,
never a pass:
  * the leg turned (the camera reached SWITCH_X; a ROM that is not the clip never does);
  * the GENERAL regime was reached (PageCache_Direct_Map read 0) and the leg flew at least
    MIN_GENERAL_FRAMES frames in it — the regime under test;
  * at least one page EVICTION was observed (a page resident in one frame's Page_Table and
    absent in the next): PageCache_PickVictim ran.

NOT A LAG GATE. It carries no lag ceiling: the clip's lag is a research measurement
(docs/research/2026-09-27-general-patch-loop/, the GPL-A3 build notes), and a ceiling copied
from one run would be a number, not a derivation. It gates correctness only.

Exit: 0 both legs flew without a halt and met every precondition; 1 a leg HALTED;
      2 UNMEASURABLE / COULD NOT RUN.
Usage (spawns its own emulators):
  DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh
  python3 tools/general_regime_witness.py [--rom s4.s2clip.debug.bin] [--lst s4.s2clip.debug.lst]
Wired: tools/keepalive_manifest.toml (the clip ROM rows; tools/nightly_instrument_keepalive.sh
builds DEBUG S2CLIP=s2_ehz_cpz nightly). Not in tools/landing_build.sh, which builds no clip
shape.
"""
import argparse
import asyncio
import os
import sys
import zlib
from pathlib import Path

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance, SpawnError  # noqa: E402
from cart_identity import CartMismatch  # noqa: E402
from stressart_legs_witness import (Unmeasurable, sym, rd, listing_labels,  # noqa: E402
                                    nearest_label, raise_message)

# (name, first heading, heading after the turn). The design parcel's CPZ legs.
LEGS = (("CPZ fly down", ["right"], ["down"]),
        ("CPZ fly diagonal", ["right"], ["right", "down"]))
SWITCH_X = 14400
# The settle before the directions go down (stressart_legs_witness's; the act is loaded and
# ticking well before it).
BOOT_FRAMES = 300
# Per-leg budget in emulated frames. The design parcel's legs ran 2000; the turn comes at
# about frame 900 of free flight at 16 px a tick, and the general regime starts near it.
LEG_FRAMES = 2000
HALT_FRAMES = 60
MIN_GENERAL_FRAMES = 300

SYMS = ("Logic_Tick", "Camera_X", "Camera_Y", "Page_Table", "PageIn_Pool_Pages",
        "PageCache_Direct_Map", "ErrorHandlerBlob")


async def run_leg(sock, rom_image, labels, name, first, second):
    b = BusClient(socket_path=sock, client_id="genrw", client_name="general-regime-witness")
    await b.connect()
    try:
        s = {n: await sym(b, n) for n in SYMS}

        async def tick():
            return int.from_bytes(await rd(b, s["Logic_Tick"], 4), "big")

        async def cam():
            return (int.from_bytes(await rd(b, s["Camera_X"], 4), "big") >> 16,
                    int.from_bytes(await rd(b, s["Camera_Y"], 4), "big") >> 16)

        await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})
        prev = await tick()
        pool = int.from_bytes(await rd(b, s["PageIn_Pool_Pages"], 2), "big")
        if not 0 < pool <= 256:
            raise Unmeasurable(f"PageIn_Pool_Pages reads {pool} after the boot settle")

        await b.call("emulator/hold", {"buttons": first, "down": True})
        turned_at, general_frames, prev_res, evictions, still = None, 0, None, 0, 0
        for f in range(1, LEG_FRAMES + 1):
            await b.call("emulator/run_frames", {"frames": 1})
            t = await tick()
            still = still + 1 if t == prev else 0
            prev = t
            cx, cy = await cam()
            if turned_at is None and cx >= SWITCH_X:
                await b.call("emulator/hold", {"buttons": first, "down": False})
                await b.call("emulator/hold", {"buttons": second, "down": True})
                turned_at = (f, cx, cy)
            if (await rd(b, s["PageCache_Direct_Map"], 1))[0] == 0:
                general_frames += 1
            table = await rd(b, s["Page_Table"], pool)
            res = {p for p in range(pool) if table[p] != 0xFF}
            if prev_res is not None:
                evictions += len(prev_res - res)
            prev_res = res
            if still >= HALT_FRAMES:
                st = await b.call("emulator/status", {})
                pc = int(str(st.get("pc", "0")), 16) & 0xFFFFFF
                print(f"  HALT: {name}, frame {f - HALT_FRAMES}: Logic_Tick unchanged for "
                      f"{HALT_FRAMES} frames, camera ({cx},{cy}), pc ${pc:06X} "
                      f"({'in' if pc >= s['ErrorHandlerBlob'] else 'NOT in'} the fault island), "
                      f"{general_frames} frame(s) in the general regime, {evictions} eviction(s)")
                msgs = await raise_message(b, rom_image)
                for site, m in msgs:
                    print(f"    raise_error at ${site:06X} ({nearest_label(labels, site)}): {m!r}")
                if not msgs:
                    print("    raise_error message: none recovered from RAM")
                return 1
        cx, cy = await cam()
        print(f"  {name}: {LEG_FRAMES} frames, no halt; turned at {turned_at}; camera now "
              f"({cx},{cy}); {general_frames} frame(s) in the general regime; {evictions} "
              f"page eviction(s); pool {pool} pages")
        if turned_at is None:
            raise Unmeasurable(f"{name}: the camera never reached x {SWITCH_X}; is this the "
                               f"S2 clip ROM (S2CLIP=s2_ehz_cpz)?")
        if general_frames < MIN_GENERAL_FRAMES:
            raise Unmeasurable(f"{name}: {general_frames} frame(s) in the general regime "
                               f"(< {MIN_GENERAL_FRAMES}); the regime under test barely ran")
        if evictions == 0:
            raise Unmeasurable(f"{name}: no page eviction observed; PageCache_PickVictim never ran")
        return 0
    finally:
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.s2clip.debug.bin"))
    ap.add_argument("--lst", default=os.path.join(AEON, "s4.s2clip.debug.lst"))
    a = ap.parse_args()
    rom, lst = Path(a.rom).resolve(), Path(a.lst).resolve()
    for label, q in (("ROM", rom), ("listing", lst)):
        if not q.is_file():
            print(f"UNMEASURABLE: no {label} at {q}. Build the clip with "
                  f"`DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh` (writes s4.s2clip.debug.bin/.lst).")
            return 2
    rom_image = rom.read_bytes()
    labels = listing_labels(lst)
    print(f"general_regime_witness: {rom.name} crc32 {zlib.crc32(rom_image):08x}, "
          f"{LEG_FRAMES} frames per leg after a {BOOT_FRAMES}-frame settle, turn at x {SWITCH_X}")
    rcs = []
    for name, first, second in LEGS:
        inst = AetherInstance(str(rom), symbols=str(lst))
        try:
            sock = inst.start()
            rc = asyncio.run(run_leg(sock, rom_image, labels, name, first, second))
        except (Unmeasurable, SpawnError, CartMismatch) as e:
            print(f"  UNMEASURABLE: {name}: {e}")
            rc = 2
        finally:
            inst.reap()
        rcs.append(rc)
    # A halt is the verdict this lane exists for; it outranks an unmeasurable sibling leg.
    worst = 1 if 1 in rcs else (2 if 2 in rcs else 0)
    print({0: "PASS: both legs flew the general regime without a halt",
           1: "FAIL: a leg halted",
           2: "UNMEASURABLE: a leg could not be measured"}[worst])
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
