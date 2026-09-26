#!/usr/bin/env python3
"""STRESS_ART flight witness: the stress fixture's two DEBUG free-flight legs, run to a halt.

WHY IT EXISTS (STRESSART-HALTS, 2026-09-26). `STRESS_ART=1 ./build.sh` builds the
uniquified-pool fixture that forces continuous page eviction (s4.stressart.{bin,lst}), and
the nightly built it every night from 2026-09-17 on. Nothing booted it. When a design parcel
finally flew it, both legs HALTED on origin/master and had been doing so since at least the
first commit the shape builds at (b9a6bf6d):
  GPL-1  fly right     "PageCache_AllocFrame: no free/evictable frame (thrash bug)"
  GPL-2  fly diagonal  "PageCache_Audit: assigned frame in no reclaim list (leaked/orphan)"
A green build line about a ROM nobody runs is the defect this file closes. It grades the
artifact the way the design parcel measured it: each leg boots a FRESH private headless
`oracle-aether` (tools/aether_instance.py, which also proves the cart is the file on disk),
lets the machine settle for BOOT_FRAMES, holds the leg's directions in DEBUG free flight, and
steps ONE EMULATED FRAME at a time for LEG_FRAMES frames.

A HALT is the game loop stopping: `Logic_Tick` (+1 per completed tick) unchanged for
HALT_FRAMES consecutive frames. A camera parked at the level edge still ticks, a lag frame
misses one tick, and nothing in a working build stops the loop for a whole second. On a halt
the witness prints the leg, the frame, the camera, whether the PC sits in the MD Debugger's
fault island (at or past `ErrorHandlerBlob`, which the build places last), and the
raise_error message recovered from RAM (a `jsr <handler>` return address pointing at the
message bytes; best effort, printed as found or as not found).

A LEG THAT CANNOT FAIL IS NOT A LEG. Two preconditions are measured per leg, and either one
missing is UNMEASURABLE, never a pass:
  * the camera moved at least MIN_TRAVEL_PX on each held axis (the leg flew; a ROM that
    boots out of free flight would sit still and never stress anything);
  * at least one page EVICTION was observed (a page resident in one frame's Page_Table and
    absent in the next). The fixture exists to force evictions; a leg that forced none
    did not exercise what this witness is for.

Exit: 0 both legs ran LEG_FRAMES frames without a halt and met both preconditions;
      1 a leg HALTED;
      2 UNMEASURABLE / COULD NOT RUN (artifact missing, symbol missing, cart mismatch, a
        precondition above not met). "Could not ask" is not "the answer is no".

Usage (spawns its own emulator; nothing needs to be running):
  STRESS_ART=1 ./build.sh
  python3 tools/stressart_legs_witness.py [--rom s4.stressart.bin] [--lst s4.stressart.lst]
Wired: tools/nightly_effects_gates.sh runs it right after its STRESS_ART build, gated on that
build's exit, with its own log and rc in the worst-wins fold (tools/test_landing_lane_shapes.py
grades the wiring). Not in tools/landing_build.sh: the STRESS_ART build re-bakes the act in
place (~4 min) and the legs boot two emulators, on every landing.
"""
import argparse
import asyncio
import bisect
import os
import re
import sys
import zlib
from pathlib import Path

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance, SpawnError, read_bytes  # noqa: E402
from cart_identity import CartMismatch  # noqa: E402

# The two legs the design parcel found halting (docs/research/2026-09-27-general-patch-loop,
# halt_probe.py): DEBUG free flight, directions held from the end of the boot settle.
LEGS = (("fly right", ["right"]), ("fly diagonal", ["right", "down"]))
# Boot settle before the directions go down: halt_probe's 300 (the act is loaded and the
# level state ticking well before then on this shape; the leg re-checks that the loop ticks).
BOOT_FRAMES = 300
# Per-leg budget in emulated frames. The measured halts were at leg frames 42 (right) and 125
# (diagonal) past the settle; the fixed diagonal reaches the act's far corner (5824,5920) by
# about frame 1150 and then sits there, still ticking. 1500 covers both with room, at ~4-5 ms
# of wall per stepped frame on this bus.
LEG_FRAMES = 1500
# One second of video with no completed logic tick. Lag frames cost single ticks, never 60.
HALT_FRAMES = 60
# The leg must actually fly: 16 px per tick in DEBUG free flight, so any leg that ran for
# more than a few ticks has travelled far past this.
MIN_TRAVEL_PX = 256

SYMS = ("Logic_Tick", "Camera_X", "Camera_Y", "Page_Table", "PageIn_Pool_Pages",
        "ErrorHandlerBlob")


class Unmeasurable(Exception):
    pass


async def sym(b, name):
    try:
        r = await b.call("emulator/lookup_symbol", {"name": name})
    except Exception as e:  # noqa: BLE001 - the bus raises its own error type
        raise Unmeasurable(f"symbol {name} not found in the listing ({e})") from e
    return int(r["addr"], 16) & 0xFFFFFF


async def rd(b, addr, n):
    h = await read_bytes(b, addr & 0xFFFFFF, n)
    if len(h) != 2 * n:
        raise Unmeasurable(f"read_memory ${addr:06X} len {n} returned {len(h) // 2} byte(s)")
    return bytes.fromhex(h)


_LST_LABEL = re.compile(r"^\(\d+\)\s+\d+/([0-9A-F]+)\s*:\s+([^\s:]+):\s*$")


def listing_labels(lst_path):
    """(sorted addresses, names) of every label line in a sigil listing. Used only to NAME
    the raise site in a halt report ("assert.w d1,eq" says nothing about WHERE)."""
    pairs = {}
    for line in Path(lst_path).read_text(errors="replace").splitlines():
        m = _LST_LABEL.match(line)
        if m:
            pairs.setdefault(int(m.group(1), 16), m.group(2))
    addrs = sorted(pairs)
    return addrs, [pairs[a] for a in addrs]


def nearest_label(labels, addr):
    addrs, names = labels
    i = bisect.bisect_right(addrs, addr) - 1
    return f"{names[i]}+${addr - addrs[i]:X}" if i >= 0 else "?"


async def raise_message(b, rom_image):
    """(site, text) of the raise_error, recovered the way halt_probe.py does: a long in RAM
    that points into ROM just past a `jsr abs.l` (4EB9, the site) whose target is printable
    text (the message). The message bytes follow the jsr, so the site is v - 6."""
    ram = b""
    for off in range(0, 0x10000, 1024):
        ram += await rd(b, 0xFF0000 + off, 1024)
    found = []
    for off in range(0, len(ram) - 3, 2):
        v = int.from_bytes(ram[off:off + 4], "big")
        if 6 <= v < len(rom_image) - 4 and rom_image[v - 6:v - 4] == b"\x4e\xb9":
            txt = rom_image[v:v + 110].split(b"\0")[0]
            if len(txt) >= 12 and all(32 <= c < 127 for c in txt[:12]):
                hit = (v - 6, txt.decode("latin1"))
                if hit not in found:
                    found.append(hit)
    return found


async def run_leg(sock, rom_image, labels, name, buttons):
    b = BusClient(socket_path=sock, client_id="sartw", client_name="stressart-legs-witness")
    await b.connect()
    try:
        s = {n: await sym(b, n) for n in SYMS}

        async def tick():
            return int.from_bytes(await rd(b, s["Logic_Tick"], 4), "big")

        async def cam():
            return (int.from_bytes(await rd(b, s["Camera_X"], 4), "big") >> 16,
                    int.from_bytes(await rd(b, s["Camera_Y"], 4), "big") >> 16)

        async def halted_report(frame, where):
            st = await b.call("emulator/status", {})
            pc = int(str(st.get("pc", "0")), 16) & 0xFFFFFF
            island = pc >= s["ErrorHandlerBlob"]
            msgs = await raise_message(b, rom_image)
            cx, cy = await cam()
            print(f"  HALT: {name}, {where} frame {frame}: Logic_Tick unchanged for "
                  f"{HALT_FRAMES} frames, camera ({cx},{cy}), pc ${pc:06X} "
                  f"({'in' if island else 'NOT in'} the fault island at "
                  f"${s['ErrorHandlerBlob']:06X})")
            if msgs:
                for site, m in msgs:
                    print(f"    raise_error at ${site:06X} ({nearest_label(labels, site)}): {m!r}")
            else:
                print("    raise_error message: none recovered from RAM")

        # ---- boot settle ----
        # NOT halt-checked: Logic_Tick legitimately stands still for longer than HALT_FRAMES
        # while the act loads (measured: 63+ frames on s4.stressart.bin 41401ef1). A boot
        # that never reaches a ticking level state shows up as a halt at the leg's frame 60.
        await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})
        prev = await tick()
        pool = int.from_bytes(await rd(b, s["PageIn_Pool_Pages"], 2), "big")
        if not 0 < pool <= 256:
            raise Unmeasurable(f"PageIn_Pool_Pages reads {pool} after the boot settle")
        x0, y0 = await cam()

        # ---- the leg ----
        await b.call("emulator/hold", {"buttons": buttons, "down": True})
        prev_res, evictions, still = None, 0, 0
        for f in range(1, LEG_FRAMES + 1):
            await b.call("emulator/run_frames", {"frames": 1})
            t = await tick()
            still = still + 1 if t == prev else 0
            prev = t
            table = await rd(b, s["Page_Table"], pool)
            res = {p for p in range(pool) if table[p] != 0xFF}
            if prev_res is not None:
                evictions += len(prev_res - res)
            prev_res = res
            if still >= HALT_FRAMES:
                await halted_report(f - HALT_FRAMES, "leg")
                return 1
        x1, y1 = await cam()
        print(f"  {name}: {LEG_FRAMES} frames, no halt; camera ({x0},{y0}) -> ({x1},{y1}); "
              f"{evictions} page eviction(s) observed; pool {pool} pages")
        if "right" in buttons and x1 - x0 < MIN_TRAVEL_PX:
            raise Unmeasurable(f"{name}: the camera moved {x1 - x0} px right (< {MIN_TRAVEL_PX}); "
                               f"the leg did not fly, so it stressed nothing")
        if "down" in buttons and y1 - y0 < MIN_TRAVEL_PX:
            raise Unmeasurable(f"{name}: the camera moved {y1 - y0} px down (< {MIN_TRAVEL_PX}); "
                               f"the leg did not fly, so it stressed nothing")
        if evictions == 0:
            raise Unmeasurable(f"{name}: no page eviction observed in {LEG_FRAMES} frames; this "
                               f"ROM is not forcing the fixture's churn (is it s4.stressart.bin?)")
        return 0
    finally:
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.stressart.bin"))
    ap.add_argument("--lst", default=os.path.join(AEON, "s4.stressart.lst"))
    a = ap.parse_args()
    rom, lst = Path(a.rom).resolve(), Path(a.lst).resolve()
    for label, q in (("ROM", rom), ("listing", lst)):
        if not q.is_file():
            print(f"UNMEASURABLE: no {label} at {q}. Build the fixture with "
                  f"`STRESS_ART=1 ./build.sh` (writes s4.stressart.bin / s4.stressart.lst).")
            return 2
    rom_image = rom.read_bytes()
    labels = listing_labels(lst)
    print(f"stressart_legs_witness: {rom.name} crc32 {zlib.crc32(rom_image):08x}, "
          f"{LEG_FRAMES} frames per leg after a {BOOT_FRAMES}-frame settle")
    worst = 0
    for name, buttons in LEGS:
        inst = AetherInstance(str(rom), symbols=str(lst))
        try:
            sock = inst.start()
            rc = asyncio.run(run_leg(sock, rom_image, labels, name, buttons))
        except (Unmeasurable, SpawnError, CartMismatch) as e:
            print(f"  UNMEASURABLE: {name}: {e}")
            rc = 2
        finally:
            inst.reap()
        if rc == 2 or (rc == 1 and worst != 2):
            worst = rc
    verdict = {0: "PASS: both legs flew without a halt",
               1: "FAIL: a leg halted",
               2: "UNMEASURABLE: a leg could not be measured"}[worst]
    print(verdict)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
