#!/usr/bin/env python3
"""Did the V-7 release-shape ZX0R nets FIRE on a real boot? A witness, not a gate.

WHY THIS EXISTS. The four checks landed by V-7 (`.fault_ver`, `.fault_size`,
`.fault_extent` in `PageIn_Process`, `.fault_bank` in `PageIn_BankRegs`) are
RELEASE-SHAPE: they are in the ROM the owner plays. A release check that
false-fires does not report a bug, it BRICKS the game on a crash screen. The
build-time half (`tools/test_zx0r_resume_net.py`) re-derives each predicate over
the baked corpus and so covers a false fire on the SHIPPED BYTES. It cannot cover
the runtime path, because the runtime path involves the suspend/resume round trip
and nothing in a build sees that. Only a running machine can answer it.

⚠ WHAT MAKES THIS NON-VACUOUS, and it is the whole design. "The ROM did not crash"
is worthless on its own: if no ZX0 page-in happens in the boot window, none of the
four checks ever EXECUTES and a clean run proves only that unreached code cannot
fire. So this asserts POSITIVE EVIDENCE THAT THE CHECKS RAN, from state the
engine keeps for its own reasons:

  * `Page_Table` entries != PAGE_NOT_RESIDENT  -> that many pages completed a
    page-in. Nets 1, 2 and 4 execute once per ZX0 page-in / completion, so a
    resident count of N is N executions of each that did not fault.
  * `Dbg_PageIn_Preempts` (DEBUG shape only) -> bookmark redirects, i.e. decodes
    sliced by a VBlank. Net 3 lives in `PageIn_BankRegs`, which is reached ONLY by
    that redirect, so this counter IS net 3's execution count.

A run where both are zero is reported UNMEASURABLE and exits 2. It is never green.

This is a witness rather than a build gate because it needs a headless emulator,
which `build.sh` deliberately does not have. Run it by hand at a landing, the same
way the effects gates lane is run.

Usage:  python3 tools/zx0r_net_boot_witness.py --rom s4.debug.bin --lst s4.debug.lst
Exit:   0 witnessed clean · 1 a net fired (or the machine died) · 2 unmeasurable
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path                     # noqa: E402
add_client_path()
from aether import BusClient                                # noqa: E402
from aether_instance import aether_emulator, read_bytes     # noqa: E402

# DERIVED, never copied: both constants are read out of engine/system/constants.emp
# below rather than typed here, so a change to either fails loudly instead of
# silently measuring the wrong table.
CONSTANTS = "engine/system/constants.emp"
BOOT_FRAMES = 600          # ~10 s at 60 Hz: past the title path and well into streaming


class Unmeasurable(RuntimeError):
    pass


def const_from_source(name: str) -> int:
    """Read `pub const NAME = <value>` out of the engine's own constants file."""
    import re
    text = Path(CONSTANTS).read_text()
    m = re.search(rf"^pub const\s+{re.escape(name)}\s*=\s*(\$?[0-9A-Fa-f]+)", text, re.M)
    if not m:
        raise Unmeasurable(f"{name} is not in {CONSTANTS} - the expectation cannot be "
                           f"derived, so this witness has nothing to compare against")
    raw = m.group(1)
    return int(raw[1:], 16) if raw.startswith("$") else int(raw)


def symbols(lst: str) -> dict:
    from raster_cost_probe import parse_lst
    return parse_lst(lst)


async def run(sock: str, lst: str, want_debug_counter: bool) -> int:
    page_table_max = const_from_source("PAGE_TABLE_MAX")
    not_resident = const_from_source("PAGE_NOT_RESIDENT")

    b = BusClient(socket_path=sock, client_id="zx0rnet", client_name="zx0r_net_boot_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym = symbols(lst)

    needed = ["Page_Table"]
    if want_debug_counter:
        needed.append("Dbg_PageIn_Preempts")
    missing = [n for n in needed if n not in sym]
    if missing:
        raise Unmeasurable(f"symbol(s) {missing} absent from {lst} - the witness cannot "
                           f"establish that any check RAN, and a clean boot without that "
                           f"is not evidence")

    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})

    # --- did the machine survive? ---
    st = await b.call("emulator/status", {})
    regs = await b.call("emulator/registers", {})
    pc = regs.get("pc")
    pc_i = int(str(pc), 16) if isinstance(pc, str) else pc

    # The crash path is the MD Debugger island. If we are inside it, a net fired
    # (or something else did) - either way this is not a clean boot.
    #
    # ⚠ THIS ARM MUST NEVER FAIL QUIET, and the first version of it did. It tried
    # the names `MDDBG__ErrorHandler` and `ErrorHandler`, found NEITHER, and set
    # `in_handler = False` -- which reads as "the machine is fine". Measured
    # 2026-09-10 against a deliberately poisoned ROM (one flipped wrapper version
    # byte): the machine really was halted at ErrorHandlerBlob+$E2E and this
    # witness said it was not. The cause is the two-namespaces trap this suite
    # already carries: `MDDBG__ErrorHandler` exists in the listing only as an
    # `EQU` line, which the symbol parser does not return, while the LABEL is
    # spelled `ErrorHandlerBlob`. So: try the label names, and if none resolves,
    # this is UNMEASURABLE rather than clean.
    island = next((sym[n] for n in ("ErrorHandlerBlob", "MDDBG__ErrorHandler",
                                    "ErrorHandler") if n in sym), None)
    if island is None:
        raise Unmeasurable(
            "no crash-island label in the listing (tried ErrorHandlerBlob, "
            "MDDBG__ErrorHandler, ErrorHandler) - this witness cannot tell a clean "
            "boot from a halted one, and reporting 'clean' would be manufacturing "
            "the absence")
    if pc_i is None:
        raise Unmeasurable("emulator/registers returned no pc - nothing to compare")
    # Island extent DERIVED from the listing: the island is the last emission, so
    # its end is the highest symbol address in the file, never a magic window.
    top = max(sym.values())
    in_handler = island <= pc_i <= max(top, island)

    # --- did the checks RUN? ---
    raw = await read_bytes(b, sym["Page_Table"], page_table_max)
    entries = [int(raw[i * 2:i * 2 + 2], 16) for i in range(page_table_max)]
    resident = sum(1 for e in entries if e != not_resident)

    preempts = None
    if want_debug_counter:
        preempts = int(await read_bytes(b, sym["Dbg_PageIn_Preempts"], 2), 16)

    print(f"  frames run                 : {BOOT_FRAMES}")
    print(f"  emulator frame             : {st.get('frame')}")
    print(f"  pc                         : {pc}")
    print(f"  inside the crash island    : {in_handler}")
    print(f"  Page_Table resident entries: {resident} of {page_table_max} "
          f"(sentinel ${not_resident:02X}) -> nets 1/2/4 executed this many times")
    if preempts is not None:
        print(f"  Dbg_PageIn_Preempts        : {preempts} -> net 3 (PageIn_BankRegs) "
              f"executed this many times")

    if in_handler:
        print("VERDICT: FIRED - the machine is in the crash island after a clean boot")
        return 1
    if resident == 0 and not preempts:
        print("VERDICT: UNMEASURABLE - no page-in completed and no decode was sliced, so "
              "not one of the four checks executed. A clean run here rules out nothing.")
        return 2
    print(f"VERDICT: WITNESSED CLEAN - the checks ran and none fired "
          f"({resident} page-in completions"
          + (f", {preempts} slices" if preempts is not None else "") + ")")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    args = ap.parse_args()
    # Whether the DEBUG counter exists is a property of the LISTING, never of the
    # rom's filename -- a poisoned or renamed copy of a debug ROM would otherwise
    # silently drop net 3's execution count and weaken the witness with no notice.
    want_debug = "Dbg_PageIn_Preempts" in Path(args.lst).read_text()
    try:
        with aether_emulator(args.rom, symbols=args.lst) as sock:
            return asyncio.run(run(sock, args.lst, want_debug))
    except Unmeasurable as e:
        print(f"VERDICT: UNMEASURABLE - {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
