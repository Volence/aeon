#!/usr/bin/env python3
"""raster_source_gate — assert the address `Raster_HInt` ACTUALLY streams from.

WHY THIS EXISTS. Every gate in this tree that asserts a raster program asserts the PROGRAM'S
WORDS: `effects_scene_assert` checks arm words and opcode presence, the cost fixtures check
cycles, `raster_off_gate` checks three teardown facts. Nothing observes the HANDLER that
interprets those words. A build that encodes a source offset correctly and then reads it from
the wrong base passes every one of them — the program is right, the pixels are wrong, and the
suite is green. That gap was named in the Parcel R adjudication audit (§6, "one gate finding
worth keeping regardless of what happens to R") and this closes it.

It matters most for the op class Parcel R clones. `OP_PAL_REGION` is the only op today whose
source is COMPUTED rather than inline: the program carries a comptime offset and the handler
does `lea Pal_Variant_Stage, a2` + `adda.w <offset>, a2`. Parcel R's `OP_PAL_RESTORE` is the
same body with a different base, so "streams from the wrong base" is precisely R's failure
mode, and it is invisible to word-assertions by construction.

WHERE IT BREAKS, AND WHY THAT EXACT INSTRUCTION.

    .op_region:      move.l (a1)+, (a2)        CRAM write command
                     move.w (a1)+, d1          solved blanking spin, from the program
    .region_delay:   dbf    d1, .region_delay
                     move.w (a1)+, d1          count-1
                     lea    Pal_Variant_Stage, a2
                     adda.w (a1)+, a2          <-- the source pointer is complete HERE
    .region_loop:    move.w (a2)+, VDP_DATA    <-- so we break at this label

`.region_loop` is the first instruction at which a2 holds the finished source address, and it
is a real label in the listing, so the probe point needs no hand-computed offset that could
rot when the body changes.

NON-DETERMINISTIC BY REQUIREMENT, NOT BY ACCIDENT. `headless_emulator` defaults to
deterministic=True, and in that mode oracle answers `breakpoint_add` with "det-mode stop
granularity: PC may precede the breakpoint" — the serial scheduler's rollback stops at commit
granularity. A stop one instruction early lands BEFORE `adda.w` and a2 still holds
`Pal_Variant_Stage` unmodified, which is a plausible-looking value that would make this gate
pass on code that never applied the offset at all. So the launcher is asked for the threaded
path (its own docstring: "required for anything that asserts on exact breakpoint-stop PCs"),
and the stop PC is asserted against the label before a2 is read. A stop anywhere else is
reported as SETUP FAILURE (exit 2), never as a verdict.

TWO FIXTURES, NOT ONE POISON. The anti-vacuity proof here is differential: two programs whose
only difference is the encoded offset must produce two separately-predicted a2 values AND a
measured delta equal to the encoded delta. A gate that read a constant, a stale register, or
the base pointer alone passes NEITHER prediction; a gate that read a2 one instruction early
passes neither delta. One fixture plus one poison would prove less, because a single
prediction can be satisfied by an accident of layout.

Usage:
    python3 tools/raster_source_gate.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit: 0 the handler streams from the predicted address · 1 it does not · 2 setup/boot error
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient                                   # noqa: E402
from launcher import headless_emulator                         # noqa: E402
from raster_cost_probe import parse_lst, program_words, stream_pal_region, pal_restore  # noqa: E402

AEON = Path(__file__).resolve().parent.parent

# The label whose address is the probe point. Local labels reach the sigil listing MANGLED
# (`$module$proc$label`) and `parse_lst` drops every name containing `$`, so this gate carries
# its own resolver rather than weakening a parser three other tools depend on.
REGION_LOOP = "$engine.effects.raster$Raster_HInt$region_loop"
# R1: the restore body's own loop label — same discipline, different base.
RESTORE_LOOP = "$engine.effects.raster$Raster_HInt$restore_loop"

# Two region ops differing ONLY in the encoded offset (slot*128 + line*32 + entry*2).
# Pal_Variant_Stage is [u8; 128*2] (engine/ram.emp:398), so slot 1 is real storage and
# fixture B's highest touched byte, 202 + 2*3 - 1 = 207, is inside it.
FIXTURES = [
    {"name": "A", "slot": 0, "pal_line": 1, "entry": 1, "count": 3},
    {"name": "B", "slot": 1, "pal_line": 2, "entry": 5, "count": 3},
]

# R1: two restore ops differing ONLY in the CRAM address, which IS the snapshot offset
# (claim D-F — no slot term; a naive reuse of offset_of() here would predict wrong, the
# exact [MF-6]/[S4-5] trap the spec records). Line-0 addresses are constructor-refused,
# so both fixtures sit on lines 1-2 like the region pair.
RESTORE_FIXTURES = [
    {"name": "RA", "addr": 0x22, "count": 3},
    {"name": "RB", "addr": 0x4A, "count": 3},
]


def offset_of(f: dict) -> int:
    """The comptime offset the op encodes — the same arithmetic raster.emp documents."""
    return f["slot"] * 128 + f["pal_line"] * 32 + f["entry"] * 2


def restore_offset_of(f: dict) -> int:
    """The restore's offset IS the CRAM byte address — one field, no slot/line/entry terms."""
    return f["addr"]


def parse_lst_locals(path: str) -> dict[str, int]:
    """Symbol -> address INCLUDING mangled local labels, which parse_lst filters out."""
    out: dict[str, int] = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.startswith("(0) "):
            continue
        try:
            addrpart, namepart = line[4:].split(" :", 1)
            addr = int(addrpart.split("/", 1)[1], 16)
        except (ValueError, IndexError):
            continue
        name = namepart.strip().rstrip(":")
        if name and name not in out:
            out[name] = addr & 0xFFFFFF
    return out


class SetupError(Exception):
    """Something made the measurement impossible. Not a verdict — exit 2, never exit 1."""


async def measure(b: BusClient, sym: dict, probe_pc: int, fx: dict, settle: int,
                  op=None) -> int:
    """Install a one-op fixture and return the a2 the handler computed for it."""
    if op is None:
        op = stream_pal_region(0x22, fx["slot"], fx["pal_line"], fx["entry"], fx["count"])
    fires = [(60, [op])]
    image = "".join(f"{w:04X}" for w in program_words(fires))

    await b.call("emulator/breakpoint_clear", {"all": True})
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": settle})
    # Freeze the camera BEFORE installing: a section crossing installs its own program over
    # the poke, and the failure would read as a wrong source rather than a lost fixture.
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})

    buf = sym["Raster_Buf_A"]
    await b.call("emulator/write_memory", {"addr": hex(buf), "bytes": image})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Raster_Patch_Tab"]), "value": 0, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Effects_Offscreen_Entry"]), "value": 0, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Raster_Active_Buf"]), "value": buf, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Raster_Program"]), "value": buf, "width": 4})
    # One frame for Raster_VBlank to rewind the cursor onto the poked image.
    await b.call("emulator/run_frames", {"frames": 2})

    # The poke must still be there. Without this a fixture that was rebuilt underneath us
    # would be measured as a source-address failure.
    back = (await b.call("emulator/read_memory",
                         {"addr": hex(buf), "len": len(image) // 2}))["bytes"].upper()
    if back != image:
        raise SetupError(f"fixture {fx['name']}: program image did not survive install\n"
                         f"        wrote {image}\n        read  {back}")

    await b.call("emulator/breakpoint_add", {"addr": hex(probe_pc)})
    await b.call("emulator/resume", {})
    # 120 s, not 20: this is a WEDGE DETECTOR, not a performance assertion (the
    # lane doctrine: budgets sit 8-35x above honest runtimes). The 20 s budget
    # predated that doctrine and produced four load-induced false SETUP failures
    # on 2026-08-19 alone (parallel agent lanes, load 8+), each passing clean on
    # an unloaded retry. A real wedge hangs forever; 120 s still catches it.
    r = await b.call("emulator/wait_for_break", {"timeout_ms": 120000})
    if r.get("running", False) is not False:
        raise SetupError(f"fixture {fx['name']}: never reached the probe label within 120 s — "
                         f"the handler did not run the op at all")
    regs = await b.call("emulator/registers", {})
    await b.call("emulator/breakpoint_clear", {"all": True})

    pc = int(regs["pc"].lstrip("$"), 16) & 0xFFFFFF
    if pc != probe_pc:
        raise SetupError(
            f"fixture {fx['name']}: stopped at ${pc:06X}, expected ${probe_pc:06X} "
            f"(the op body's stream loop). a2 is only the finished source pointer AT that "
            f"instruction, so reading it here would assert on an address the handler never used.")
    return int(regs["a2"].lstrip("$"), 16) & 0xFFFFFF


async def run(sock: str, sym: dict, probe_pc: int, restore_pc: int, lst: str,
              settle: int) -> list[str]:
    fails: list[str] = []
    b = BusClient(socket_path=sock, client_id="rastsrc", client_name="raster_source_gate")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})

    base = sym["Pal_Variant_Stage"]
    seen: dict[str, int] = {}

    def check(label: str, cond: bool, detail: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {label}: {detail}")
        if not cond:
            fails.append(label)

    for fx in FIXTURES:
        off = offset_of(fx)
        want = base + off
        got = await measure(b, sym, probe_pc, fx, settle)
        seen[fx["name"]] = got
        check(f"fixture {fx['name']} source address",
              got == want,
              f"handler streams from ${got:06X}; predicted ${want:06X} "
              f"(Pal_Variant_Stage ${base:06X} + offset {off})")

    # THE DIFFERENTIAL. This is what makes the two checks above non-vacuous: a probe reading a
    # constant, the bare base, or a stale a2 from before the adda.w cannot move by exactly the
    # encoded delta.
    want_delta = offset_of(FIXTURES[1]) - offset_of(FIXTURES[0])
    got_delta = seen["B"] - seen["A"]
    check("differential (B - A)", got_delta == want_delta,
          f"measured {got_delta}, encoded {want_delta} — a probe reading anything other than "
          f"the computed pointer cannot track this")

    # ---- R1: the restore arm — same two-fixture-plus-differential discipline against the
    # SNAPSHOT base. A build that encodes the restore correctly and streams from
    # Pal_Variant_Stage anyway (R's named failure mode) fails the absolute predictions;
    # a probe that stopped before the adda.w fails the differential.
    snap_base = sym["Palette_Ship_Snap"]
    rseen: dict[str, int] = {}
    for fx in RESTORE_FIXTURES:
        off = restore_offset_of(fx)
        want = snap_base + off
        got = await measure(b, sym, restore_pc, fx, settle,
                            op=pal_restore(fx["addr"], fx["count"]))
        rseen[fx["name"]] = got
        check(f"restore fixture {fx['name']} source address",
              got == want,
              f"handler streams from ${got:06X}; predicted ${want:06X} "
              f"(Palette_Ship_Snap ${snap_base:06X} + addr {off} — the offset IS the CRAM "
              f"address, claim D-F)")
    want_rdelta = restore_offset_of(RESTORE_FIXTURES[1]) - restore_offset_of(RESTORE_FIXTURES[0])
    got_rdelta = rseen["RB"] - rseen["RA"]
    check("restore differential (RB - RA)", got_rdelta == want_rdelta,
          f"measured {got_rdelta}, encoded {want_rdelta}")

    await b.close()
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--settle", type=int, default=180)
    args = ap.parse_args()
    # Absolute: headless_emulator launches oracle with `env -C <oracle repo>`, so a RELATIVE
    # ROM path silently fails to load while every poke and read still answers ok against
    # blank RAM.
    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    if not Path(rom).is_file():
        print(f"raster_source_gate: ROM not found: {rom} — build it first", file=sys.stderr)
        return 2

    sym = parse_lst(lst)
    locals_ = parse_lst_locals(lst)
    for lbl in (REGION_LOOP, RESTORE_LOOP):
        if lbl not in locals_:
            print(f"raster_source_gate: `{lbl}` is not in the listing. The op body was "
                  f"renamed or restructured; re-point the probe at the instruction after the "
                  f"source `adda.w` rather than deleting this gate.", file=sys.stderr)
            return 2
    need = ("Pal_Variant_Stage", "Palette_Ship_Snap", "Raster_Buf_A", "Raster_Program",
            "Raster_Active_Buf", "Raster_Patch_Tab", "Effects_Offscreen_Entry",
            "Debug_Scene_Freeze")
    missing = [s for s in need if s not in sym]
    if missing:
        print(f"raster_source_gate: symbols missing from the listing: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    probe_pc = locals_[REGION_LOOP]
    restore_pc = locals_[RESTORE_LOOP]
    print(f"raster_source_gate  ROM {rom}")
    print(f"  probe: .region_loop ${probe_pc:06X}   base: Pal_Variant_Stage "
          f"${sym['Pal_Variant_Stage']:06X}")
    print(f"  probe: .restore_loop ${restore_pc:06X}  base: Palette_Ship_Snap "
          f"${sym['Palette_Ship_Snap']:06X}")
    print("  fixtures: " + "  ".join(
        f"{f['name']} offset {offset_of(f)}" for f in FIXTURES) + "  " + "  ".join(
        f"{f['name']} addr {restore_offset_of(f)}" for f in RESTORE_FIXTURES) + "\n")

    try:
        # deterministic=False is REQUIRED here — see the module docstring.
        with headless_emulator(rom, deterministic=False) as sock:
            fails = asyncio.run(run(sock, sym, probe_pc, restore_pc, lst, args.settle))
    except SetupError as e:
        print(f"\nraster_source_gate: SETUP — {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\nraster_source_gate: run error: {e}", file=sys.stderr)
        return 2

    if fails:
        print(f"\nraster_source_gate: FAIL — {len(fails)} assertion(s): {', '.join(fails)}")
        return 1
    print("\nraster_source_gate: OK — the handler streams from the address the program encodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
