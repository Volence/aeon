#!/usr/bin/env python3
"""raster_cost_probe — measure what one raster fire actually costs, per op class.

WHAT IT MEASURES, AND WHY NOT THE OBVIOUS COUNTER. `get_profiler_frames` returns an
`interrupts.hint` figure, and it is NOT HBlank cost in this ROM. Oracle classifies an
interrupt by the handler address the vector points at:

    if (vec == 0x78 || (vec >= 0x70078 && vec <= 0x7FFFF)) vint += dur; else hint += dur;
                                        -- oracle linux-port/gui/ControlSocket.cpp, OpGetProfilerFrames

Aeon's VBlank_Handler sits at $2310 and its HBlank trampoline at $FFB452, so BOTH fall
into the `else` and `interrupts.hint` is (HBlank + VBlank). That is the whole explanation
for the 2026-08-18 session's "the hint counter includes VBlank work" caveat and for the
~380-cycle jump it saw when the off-screen ship turned on: the ship is VBlank work being
counted as HInt. The counter is not subtly contaminated, it is measuring both handlers.

So this probe reads the PER-ROUTINE row instead. `routines[]` is keyed by that same entry
address, so the HBlank trampoline gets its own row with its own `cycles` and `calls`, with
VBlank's cycles in a different row entirely. `cycles` and `calls` are both divided by the
frame count inside the emulator, so a multi-frame sample is exact to within 1 cycle rather
than averaged-with-noise. `calls` is a free correctness check: it says how many fires
actually happened, so a fixture that failed to install cannot be silently measured.

HOW A FIXTURE IS INSTALLED — no ROM bytes, no map.toml entry, no rebuild per fixture. A
raster program is a flat [u16] image that lives in RAM at Raster_Buf_A once installed, so
a fixture is written STRAIGHT INTO THE BUFFER and the three pointers that make it live are
poked beside it:

    Raster_Patch_Tab       = 0    stops Raster_BuildSchedule re-recording over the poke
    Effects_Offscreen_Entry= 0    stops the previous program's frame-top ship
    Raster_Active_Buf      = &Raster_Buf_A
    Raster_Program         = &Raster_Buf_A   (nonzero -> Raster_VBlank walks it)

Raster_VBlank then does the rest every frame: rewinds Raster_Cursor to the priming record
and arms reg $0A = 0. Nothing in the engine changes for this to work, which is the point —
a measurement rig that needed engine code would be measuring the rig.

THE PALETTE MASK IS FORCED CONSTANT across every fixture (PIN_MASK below) rather than
derived from the ops. Raster_VBlank ORs the header mask into Palette_Dirty every frame, so
a mask that varied by fixture would vary the VBlank palette DMA between fixtures — bus
traffic that competes with the very handler being measured. Holding it fixed removes the
confound; it costs nothing, because the mask is not an input to any cost being measured.

Usage:
    python3 tools/raster_cost_probe.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/raster_cost_probe.py --dump          # every profiler routine row, once
    python3 tools/raster_cost_probe.py --repeat 5      # noise floor over 5 boots
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

HARNESS = "/home/volence/sonic_hacks/oracle/linux-port/harness"
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, HARNESS)
from aether import BusClient          # noqa: E402
from launcher import headless_emulator  # noqa: E402


# ---- the wire encoder -------------------------------------------------------
# A transcription of engine/effects/raster_dsl.emp's op_words / raster_program. It is a
# SECOND implementation of that format on purpose: the probe has to build programs the
# .emp authoring layer refuses (F0 has no fires at all, which raster_program rejects), and
# a fixture that had to be a ROM `data` declaration would drag map.toml and the frozen
# tables into a measurement. The cross-check that it is transcribed correctly is empirical
# and strong — `calls` reports the fires the hardware actually took, so a mis-encoded
# program shows up as the wrong fire count before any cycle figure is read.

CRAM_WRITE  = 0xC0000000     # (type & rwd) = 3 -> 3 << 30, no high bits
VSRAM_WRITE = 0x40000010     # (type & rwd) = 5 -> 1 << 30 | 4 << 2


def _delta(addr: int) -> int:
    return ((addr & 0x3FFF) << 16) | ((addr & 0xC000) >> 14)


def reg_set(word: int) -> dict:
    return {"k": "reg", "w": word}


def stream_cram(addr: int, cols: list[int]) -> dict:
    return {"k": "cram", "a": addr, "v": cols}


def stream_vsram(addr: int, vals: list[int]) -> dict:
    return {"k": "vsram", "a": addr, "v": vals}


def stream_pal_region(addr: int, slot: int, pal_line: int, entry: int, count: int) -> dict:
    return {"k": "region", "a": addr, "slot": slot, "pl": pal_line, "e": entry, "n": count}


def pal_restore(addr: int, count: int) -> dict:
    return {"k": "restore", "a": addr, "n": count}


def op_words(o: dict) -> list[int]:
    k = o["k"]
    if k == "reg":
        return [0, o["w"]]
    if k == "cram":
        c = CRAM_WRITE | _delta(o["a"])
        return [2, (c >> 16) & 0xFFFF, c & 0xFFFF, len(o["v"]) - 1] + list(o["v"])
    if k == "vsram":
        c = VSRAM_WRITE | _delta(o["a"])
        return [2, (c >> 16) & 0xFFFF, c & 0xFFFF, len(o["v"]) - 1] + list(o["v"])
    if k == "region":
        c = CRAM_WRITE | _delta(o["a"])
        return [4, (c >> 16) & 0xFFFF, c & 0xFFFF, o["n"] - 1,
                o["slot"] * 128 + o["pl"] * 32 + o["e"] * 2]
    if k == "restore":
        # R1: OP_PAL_RESTORE — the snapshot offset IS the CRAM byte address (claim D-F),
        # so word 5 is the same `a` the command longword was derived from.
        c = CRAM_WRITE | _delta(o["a"])
        return [10, (c >> 16) & 0xFFFF, c & 0xFFFF, o["n"] - 1, o["a"]]
    raise ValueError(f"unknown op {k}")


PIN_MASK = 0x0002            # see the module note: constant across every fixture


def program_words(fires: list[tuple[int, list[dict]]]) -> list[int]:
    """fires = [(screen_line, [op, ...]), ...] in ascending screen-line order."""
    L = [0, 1] + [line - 1 for line, _ in fires]
    for i in range(1, len(L)):
        if L[i] <= L[i - 1]:
            raise ValueError(f"fire lines not strictly ascending: {L}")

    def arm(i: int) -> int:
        if i + 2 >= len(L):
            return 0x8AFF
        gap = L[i + 2] - L[i + 1] - 1
        if not (0 <= gap <= 255):
            raise ValueError(f"arm gap {gap} out of range at record {i}")
        return 0x8A00 | gap

    out = [PIN_MASK, arm(0), 0, arm(1), 0]
    for i, (_, ops) in enumerate(fires):
        out += [arm(i + 2), len(ops)]
        for o in ops:
            out += op_words(o)
    out += [0x8AFF, 0xFFFF]
    if len(out) * 2 > 128:
        raise ValueError(f"program is {len(out) * 2} bytes, over RASTER_BUF_SIZE (128)")
    return out


# ---- the fixtures -----------------------------------------------------------
# Each varies ONE thing from a neighbour. Fires REPEAT within a fixture so the measured
# quantity is a marginal cost divided by the repeat count: the per-fire figure is
# (fixture - F0) / n, which divides any instrument error by n as well. The repeat count is
# capped by RASTER_BUF_SIZE (128 bytes), not by choice — a 3-word cram fire is 9 words, so
# six of them plus the 7-word frame is the whole buffer.
#
# Fire lines are spaced 20 apart, far wider than any plausible cost, so no fixture is near
# the density boundary and spacing cannot be a hidden variable. Fire POSITION was measured
# to have no effect (2026-08-18: line 2 vs line 99 read 10,309 vs 10,307).
#
# CRAM writes target line 1 entry 1 ($22 = 34). Never line 0 — that is the character's.

def _spread(n: int, ops_for) -> list[tuple[int, list[dict]]]:
    return [(3 + 20 * i, ops_for(i)) for i in range(n)]


COLS3 = [0x0EEE, 0x0E0E, 0x00EE]
COLS1 = [0x0EEE]
REGW  = 0x8C81               # reg $0C, the H40 base boot already holds: a no-op write

FIXTURES: dict[str, dict] = {
    "F0": {
        "what": "no fires — priming records and terminator only: the schedule's floor",
        "n": 0,
        "fires": [],
    },
    "F1": {
        "what": "one reg_set per fire — the op charged ZERO by the old model",
        "n": 6,
        "fires": _spread(6, lambda i: [reg_set(REGW)]),
    },
    "F2": {
        "what": "stream_cram, 1 word — stream base + one word",
        "n": 6,
        "fires": _spread(6, lambda i: [stream_cram(34, COLS1)]),
    },
    "F3": {
        "what": "stream_cram, 3 words — the per-word slope against F2",
        "n": 6,
        "fires": _spread(6, lambda i: [stream_cram(34, COLS3)]),
    },
    "F4": {
        "what": "stream_pal_region, 3 words — the region premium against F3",
        "n": 6,
        "fires": _spread(6, lambda i: [stream_pal_region(34, 0, 1, 1, 3)]),
    },
    "F5": {
        "what": "reg_set + stream_cram 3 — is a mixed fire additive?",
        "n": 5,
        "fires": _spread(5, lambda i: [reg_set(REGW), stream_cram(34, COLS3)]),
    },
    "F6": {
        "what": "two stream_cram 1-word ops in ONE fire — per-op cost without per-fire overhead",
        "n": 4,
        "fires": _spread(4, lambda i: [stream_cram(34, COLS1), stream_cram(38, COLS1)]),
    },
    "F7": {
        "what": "stream_vsram, 1 word — does a VSRAM word cost what a colour word costs?",
        "n": 6,
        "fires": _spread(6, lambda i: [stream_vsram(2, [0x0043])]),
    },
    # R1 (claim 9): the restore op's work constant is DERIVED (region 122 minus the 58-cyc
    # delay site) and this fixture is what turns it into a measurement — BEFORE band()'s
    # minima freeze. Model expectation at work=64: dispatch 82 (depth 4) + fetch 8 +
    # work 64 + 3*30 + tail 10 = 254 marginal + the 302 fire base = 556/fire.
    "F8": {
        "what": "pal_restore, 3 words — claim 9 (work=212 calibrated: spinless 64 + EFX_RESTORE_DELAY 148)",
        "n": 6,
        "fires": _spread(6, lambda i: [pal_restore(34, 3)]),
    },
}


# ---- the run ----------------------------------------------------------------

SYMS = ("Raster_Buf_A", "Raster_Program", "Raster_Active_Buf", "Raster_Patch_Tab",
        "Effects_Offscreen_Entry", "Debug_Scene_Freeze", "HBlank_Vector_Slot")


def parse_lst(path: str) -> dict[str, int]:
    """Symbol -> address from a sigil listing (`(0) <idx>/<hex> :        Name:`)."""
    out: dict[str, int] = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.startswith("(0) "):
            continue
        try:
            body = line[4:]
            addrpart, namepart = body.split(" :", 1)
            addr = int(addrpart.split("/", 1)[1], 16)
        except (ValueError, IndexError):
            continue
        name = namepart.strip().rstrip(":")
        if name and "$" not in name and name not in out:
            out[name] = addr & 0xFFFFFF
    return out


async def _one(b: BusClient, sym: dict[str, int], fixture: dict,
               settle: int, sample: int) -> dict:
    words = program_words(fixture["fires"])
    image = "".join(f"{w:04X}" for w in words)

    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": settle})
    # Freeze the camera BEFORE installing: a section crossing would install its own
    # program over the fixture, and the failure would look like a cost measurement.
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

    # One frame for Raster_VBlank to rewind the cursor onto the poked image, THEN start
    # the profiler, so no partially-installed frame is inside the sample.
    await b.call("emulator/run_frames", {"frames": 2})
    # THE SLEEPS ARE LOad-BEARING, not politeness. `run_frames` executes synchronously on the
    # socket thread, but the profiler is driven entirely by the GUI's MAIN loop: that loop is
    # what calls m68k->SetProfilingEnabled(true), what services the reset request, and what
    # drains the CPU's event ring into frame snapshots (main_gui.cpp, "Profiler: drain ring
    # buffer"). set_profiler only flips a flag. Without a main-loop tick between the flag and
    # the run, the CPU never starts recording and get_profiler_frames answers "no profiler
    # frames recorded"; without one after, the tail of the run is still in the ring.
    await b.call("emulator/set_profiler", {"enabled": True})
    await asyncio.sleep(0.4)
    await b.call("emulator/run_frames", {"frames": sample})
    await asyncio.sleep(0.4)
    st = await b.call("emulator/get_profiler", {})
    prof = await b.call("emulator/get_profiler_frames", {"frames": sample - 1, "top": 200})
    prof["frames_recorded"] = st.get("frames_recorded")
    await b.call("emulator/set_profiler", {"enabled": False})

    # Read the image back: proof the poke survived to the end of the sample rather than
    # being rebuilt underneath it (the Patch_Tab poke is what prevents that, and this is
    # what checks the poke worked).
    back = await b.call("emulator/read_memory", {"addr": hex(buf), "len": len(words) * 2})
    return {"prof": prof, "image": image, "readback": back["bytes"].upper(),
            "words": words}


def hint_row(prof: dict, hb_addr: int) -> dict | None:
    """The HBlank trampoline's routine row, matched by ADDRESS not name.

    Oracle prints the row's key as `$FFFFB452` (the raw 68000 PC, sign-extended by the
    short-form addressing the vector slot is reached through) while the listing spells the
    same location `$FFB452`. Comparing the low 24 bits is what makes the two agree; comparing
    the printed strings does not, and the row also has no symbol name attached, so matching on
    "HBlank_Vector_Slot" would find nothing either.
    """
    for r in prof.get("routines", []):
        try:
            a = int(r.get("addr", "$0").lstrip("$"), 16)
        except ValueError:
            continue
        if (a & 0xFFFFFF) == (hb_addr & 0xFFFFFF):
            return r
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=180, help="frames before install")
    ap.add_argument("--sample", type=int, default=31, help="frames profiled per fixture")
    ap.add_argument("--repeat", type=int, default=1, help="independent boots per fixture")
    ap.add_argument("--only", default="", help="comma-separated fixture names")
    ap.add_argument("--dump", action="store_true",
                    help="print every profiler routine row for the first fixture and stop")
    ap.add_argument("--out", default="", help="write raw results JSON here")
    args = ap.parse_args()

    # ABSOLUTE, always. headless_emulator launches oracle_gui with `env -C <oracle repo>`, so a
    # relative ROM path resolves against the EMULATOR's cwd, not this tool's — the ROM then fails
    # to load and every read/write/poke still answers ok against blank RAM. The only symptom is
    # `get_profiler_frames` reporting no frames, which reads like a profiler problem and is not.
    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    if not Path(args.rom).is_file():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 3

    sym = parse_lst(args.lst)
    missing = [s for s in SYMS if s not in sym]
    if missing:
        print(f"symbols missing from {args.lst}: {', '.join(missing)}", file=sys.stderr)
        return 3

    names = [n for n in FIXTURES if not args.only or n in args.only.split(",")]
    results: dict[str, list[dict]] = {n: [] for n in names}

    async def _sweep(sock: str) -> None:
        b = BusClient(socket_path=sock, client_id="rcprobe", client_name="raster_cost_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": str(Path(args.lst).resolve())})
        for name in names:
            r = await _one(b, sym, FIXTURES[name], args.settle, args.sample)
            if args.dump:
                print(json.dumps(r["prof"], indent=2))
                await b.close()
                return
            results[name].append(r)
        await b.close()

    for rep in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))
        if args.dump:
            return 0

    hb = sym["HBlank_Vector_Slot"]
    print(f"ROM {args.rom}   sample {args.sample - 1} frames   repeats {args.repeat}")
    print(f"HBlank trampoline $%06X  (routine key; VBlank_Handler is a separate row)\n" % hb)
    hdr = f"{'FIXTURE':8} {'n':>2} {'calls':>6} {'cycles/frame':>13} {'per call':>9}  what"
    print(hdr)
    print("-" * len(hdr))
    table: dict[str, dict] = {}
    for name in names:
        runs = results[name]
        rows = [hint_row(r["prof"], hb) for r in runs]
        if any(x is None for x in rows):
            print(f"{name:8} -- NO HInt ROUTINE ROW (fixture did not install?)")
            continue
        bad = [r for r in runs if r["readback"] != r["image"]]
        flag = "  !! buffer was rewritten during the sample" if bad else ""
        cyc = [int(x["cycles"]) for x in rows]
        cal = [int(x["calls"]) for x in rows]
        n = FIXTURES[name]["n"]
        per = (cyc[0] / cal[0]) if cal[0] else 0
        spread = f"{min(cyc)}..{max(cyc)}" if len(set(cyc)) > 1 else str(cyc[0])
        table[name] = {"cycles": cyc, "calls": cal, "n": n}
        print(f"{name:8} {n:>2} {cal[0]:>6} {spread:>13} {per:>9.1f}  "
              f"{FIXTURES[name]['what']}{flag}")
        if len(set(cal)) > 1:
            print(f"         call count VARIED across repeats: {cal}")

    if "F0" in table:
        f0 = table["F0"]["cycles"][0]
        print(f"\nmarginal cost of ONE fire, (fixture - F0) / n, with F0 = {f0}:")
        for name in names:
            if name == "F0" or name not in table:
                continue
            t = table[name]
            print(f"  {name:4} ({t['n']} fires)  {(t['cycles'][0] - f0) / t['n']:8.1f} cyc"
                  f"   {FIXTURES[name]['what']}")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {k: {"cycles": v["cycles"], "calls": v["calls"], "n": v["n"],
                 "what": FIXTURES[k]["what"]} for k, v in table.items()}, indent=2) + "\n")
        print(f"\nraw: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
