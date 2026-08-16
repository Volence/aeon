#!/usr/bin/env python3
"""raster_off_gate — installing an EMPTY raster program must UNINSTALL the HInt handler.

This is EFX-7's gate. The defect it guards against is not a wrong pixel, it is a handler that
stays armed doing nothing: before the fix, `Raster_Program_None` cost 512 cycles per frame across
two HInt entries, forever, in every section with no raster effect. Nothing on screen changes when
that regresses, so no image-based gate can see it — which is exactly why it survived from P1 to
2026-08-16 with a booking against it the whole time.

THREE FACTS, and all three matter separately:

  Raster_Program == 0        the per-frame tail of Raster_VBlank short-circuits. Without this the
                             proc still re-arms reg $0A and calls HBlank_Install every frame.
  HBlank_Vector_Slot == rte  the trampoline is idle, so an HInt already in flight when IE1 is
                             cleared lands on a bare `rte` instead of walking a dead program.
  reg $00 IE1 clear          the interrupt itself is off. This is the one that buys the cycles.

A regression could satisfy any two and fail the third, so the gate asserts each by name.

EXPECTATIONS ARE DERIVED, NEVER COPIED. `HBLANK_SLOT_RTE` and `HBLANK_IE1_BIT` are read out of
engine/system/hblank.emp at run time, and every address comes from the listing of the ROM under
test. A gate that hard-coded $4E73 and $10 would keep passing after someone changed the constant,
which is the failure mode two gates in this tree have already had.

The ROUND TRIP is half the gate: uninstall, re-install a real program, uninstall again. A one-way
check passes on an engine that can turn the handler off and never bring it back.

Usage:
    python3 tools/raster_off_gate.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit: 0 all assertions hold · 1 an assertion failed · 3 setup/boot error
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient            # noqa: E402
from launcher import headless_emulator  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

AEON = Path(__file__).resolve().parent.parent


def emp_const(rel: str, name: str) -> int:
    """A `const NAME = $HEX` / `= 123` out of an .emp source, so the gate cannot drift from it."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        raise SystemExit(f"raster_off_gate: cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


async def read_state(b, sym, slot_bytes) -> dict:
    prog = int((await b.call("emulator/read_memory",
                             {"addr": hex(sym["Raster_Program"]), "len": 4}))["bytes"], 16)
    slot = int((await b.call("emulator/read_memory",
                             {"addr": hex(sym["HBlank_Vector_Slot"]), "len": slot_bytes}))["bytes"], 16)
    mode1 = int((await b.call("emulator/read_memory",
                              {"addr": hex(sym["VDP_Shadow_Table"]), "len": 1}))["bytes"], 16)
    return {"prog": prog, "slot": slot, "mode1": mode1}


async def run(sock, sym, rte_word, ie1_bit, lst) -> list[str]:
    fails: list[str] = []
    b = BusClient(socket_path=sock, client_id="rastoff", client_name="raster_off_gate")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 180})
    # Freeze the camera: a section crossing would install its own program over the poke and the
    # failure would read as a teardown bug.
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})

    async def install(addr: int) -> None:
        await b.call("emulator/write_memory",
                     {"addr": hex(sym["Raster_Pending"]), "value": addr, "width": 4})
        await b.call("emulator/run_frames", {"frames": 3})

    def check(label: str, cond: bool, detail: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {label}: {detail}")
        if not cond:
            fails.append(label)

    none_addr = sym["Raster_Program_None"]
    real_addr = sym["OJZ_TestVsram"]

    # --- ARMED, before anything is poked: the gate must be able to see the ON state too, or
    # "uninstalled" is indistinguishable from "was never installed".
    print("armed (the section's own program):")
    s = await read_state(b, sym, 2)
    check("armed/program-nonzero", s["prog"] != 0, f"Raster_Program=${s['prog']:08X}")
    check("armed/slot-is-jmp", s["slot"] != rte_word,
          f"slot=${s['slot']:04X} (idle rte would be ${rte_word:04X})")
    check("armed/ie1-set", (s["mode1"] & ie1_bit) != 0,
          f"reg $00=${s['mode1']:02X}, IE1 bit ${ie1_bit:02X}")

    for pass_no in (1, 2):
        print(f"empty program installed (pass {pass_no}):")
        await install(none_addr)
        s = await read_state(b, sym, 2)
        check(f"off{pass_no}/program-cleared", s["prog"] == 0,
              f"Raster_Program=${s['prog']:08X}, want 0")
        check(f"off{pass_no}/slot-idled", s["slot"] == rte_word,
              f"slot=${s['slot']:04X}, want ${rte_word:04X} (rte)")
        check(f"off{pass_no}/ie1-cleared", (s["mode1"] & ie1_bit) == 0,
              f"reg $00=${s['mode1']:02X}, IE1 bit ${ie1_bit:02X} must be clear")

        if pass_no == 1:
            print("real program re-installed:")
            await install(real_addr)
            s = await read_state(b, sym, 2)
            check("back/program-set", s["prog"] == real_addr,
                  f"Raster_Program=${s['prog']:08X}, want ${real_addr:08X}")
            check("back/slot-rearmed", s["slot"] != rte_word,
                  f"slot=${s['slot']:04X} (must not be the idle rte)")
            check("back/ie1-set", (s["mode1"] & ie1_bit) != 0,
                  f"reg $00=${s['mode1']:02X}, IE1 bit ${ie1_bit:02X} must be set again")

    await b.close()
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    args = ap.parse_args()
    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    if not Path(rom).is_file():
        print(f"raster_off_gate: ROM not found: {rom}", file=sys.stderr)
        return 3

    rte_word = emp_const("engine/system/hblank.emp", "HBLANK_SLOT_RTE")
    ie1_bit = emp_const("engine/system/hblank.emp", "HBLANK_IE1_BIT")
    sym = parse_lst(lst)
    need = ("Raster_Program", "Raster_Pending", "HBlank_Vector_Slot", "VDP_Shadow_Table",
            "Debug_Scene_Freeze", "Raster_Program_None", "OJZ_TestVsram")
    missing = [s for s in need if s not in sym]
    if missing:
        print(f"raster_off_gate: symbols missing from the listing: {', '.join(missing)}",
              file=sys.stderr)
        return 3

    print(f"raster_off_gate  ROM {rom}")
    print(f"  derived: HBLANK_SLOT_RTE=${rte_word:04X}  HBLANK_IE1_BIT=${ie1_bit:02X}  "
          f"Raster_Program_None=${sym['Raster_Program_None']:06X}\n")
    try:
        with headless_emulator(rom) as sock:
            fails = asyncio.run(run(sock, sym, rte_word, ie1_bit, lst))
    except Exception as e:                       # boot / bus failure is a setup error, not a verdict
        print(f"raster_off_gate: run error: {e}", file=sys.stderr)
        return 3

    if fails:
        print(f"\nraster_off_gate: FAIL — {len(fails)} assertion(s): {', '.join(fails)}")
        return 1
    print("\nraster_off_gate: OK — an empty program uninstalls the handler, and a real one re-arms it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
