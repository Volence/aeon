#!/usr/bin/env python3
"""snapshot_poison_gate — the R1 E-B gate: the splices copy WHAT the mask says, WHEN it says.

WHAT IT PROVES (and honestly, what it cannot). Poison `Palette_Ship_Snap`, capture the REAL
pre-enqueue `Palette_Dirty` from d0 at the instruction after the handler loads it, let the
four splices run, then assert per line: a line IN the mask now equals the `Palette_Buffer`
span the accepted DMA delivered; a line OUTSIDE it still holds poison. Equality is causally
meaningful because the poison broke it first: a no-copy build leaves poison on dirty lines,
an unconditional-128-byte copy clears poison on clean lines. CLAIM SCOPE (spec §10.3): this
tests dirty-gating and copy extent. The `bcs` drop arm is untestable without the synthetic
8th Critical enqueuer spec §2.4 rules out — that half rests on code review plus the
"enqueue and bit-clear are the same event" grounding, and this docstring says so.

THE THREE LESSONS THIS GATE'S LINEAGE PAID FOR (sweeps 3-5 killed three predecessor forms):
  1. The mask is CAPTURED, never assumed — the fixture's "authored" mask was wrong twice
     (the T15 sky-marker dirties line 0 every frame; the pre-enqueue value is bclr-destroyed
     before any post-frame read). d0 at the stop is the only honest source.
  2. The breakpoint is at the instruction AFTER `move.b Palette_Dirty, d0` — oracle checks
     breakpoints BEFORE the stopped instruction executes, so a stop ON the move.b reads
     pre-entry garbage (sweep 5 K1). The stop address is Enqueue_Dirty_Buffers+4, and the
     gate BYTE-VERIFIES the move.b opcode (0x1038, move.b (xxx).w,d0) at +0 before trusting
     the offset, so a prologue change fails as SETUP, not as a wrong verdict.
  3. The payload comparison reads `Palette_Buffer` AT THE FIRST STOP — the buffer is frozen
     for the whole IRQ (CLAIM 1) — never at end-of-frame, where a T15-idempotent fixture
     made a wrong read accidentally pass (sweep 5's fixture-coincidence kill).

THE SELF-CONTROL (poison the subject, not the expectation): a "control" pass reads the
snapshot at the FIRST stop — before the splices ran — where the dirty-line assertion MUST
fail (poison still present). A control that passes means the gate is not observing the
splices at all, and the run aborts as SETUP FAILURE. This simulates the no-copy build every
run; the unconditional-copy direction is live in the real pass via the retain-poison half
(OJZ steady state leaves lines 1 and 3 clean).

POISON VALUE: $F1F1 — bits set outside the CRAM $0EEE format, and asserted absent from the
fixture's `Palette_Buffer` before use.

Usage: python3 tools/snapshot_poison_gate.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit: 0 gate holds · 1 a splice assertion failed · 2 setup/boot/control error
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle-old/linux-port/harness")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient                     # noqa: E402
from launcher import headless_emulator           # noqa: E402
from raster_cost_probe import parse_lst          # noqa: E402

AEON = Path(__file__).resolve().parent.parent
POISON_WORD = 0xF1F1
POISON = f"{POISON_WORD:04X}" * 64               # 128 bytes


class SetupError(Exception):
    pass


async def stop_at(b: BusClient, addr: int, what: str) -> dict:
    await b.call("emulator/breakpoint_add", {"addr": hex(addr)})
    await b.call("emulator/resume", {})
    r = await b.call("emulator/wait_for_break", {"timeout_ms": 20000})
    if r.get("running", False) is not False:
        raise SetupError(f"never reached {what} within 20 s")
    regs = await b.call("emulator/registers", {})
    await b.call("emulator/breakpoint_clear", {"all": True})
    pc = int(regs["pc"].lstrip("$"), 16) & 0xFFFFFF
    if pc != addr:
        raise SetupError(f"stopped at ${pc:06X}, expected ${addr:06X} ({what})")
    return regs


async def run(sock: str, sym: dict, locals_: dict, lst: str) -> list[str]:
    fails: list[str] = []
    b = BusClient(socket_path=sock, client_id="snappoison", client_name="snapshot_poison_gate")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})

    edb = sym["Enqueue_Dirty_Buffers"]
    no_pal = locals_["$engine.buffers$Enqueue_Dirty_Buffers$no_pal"]
    snap = sym["Palette_Ship_Snap"]
    buf = sym["Palette_Buffer"]

    # Lesson 2: byte-verify the prologue before trusting the +4 offset.
    head = (await b.call("emulator/read_memory", {"addr": hex(edb), "len": 2}))["bytes"]
    if head.upper() != "1038":
        raise SetupError(f"Enqueue_Dirty_Buffers no longer starts with move.b (xxx).w,d0 "
                         f"(read {head}) — the +4 breakpoint offset is stale; re-derive it")
    beq_stop = edb + 4

    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 180})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})

    # Poison check: no fixture palette word may equal the poison.
    buf_now = (await b.call("emulator/read_memory", {"addr": hex(buf), "len": 128}))["bytes"]
    words = [buf_now[i:i + 4].upper() for i in range(0, 256, 4)]
    if f"{POISON_WORD:04X}" in words:
        raise SetupError("the fixture palette contains the poison word $F1F1 — pick another")

    # ---- CONTROL PASS: poison, stop BEFORE the splices, dirty half MUST fail there.
    await b.call("emulator/write_memory", {"addr": hex(snap), "bytes": POISON})
    regs = await stop_at(b, beq_stop, "the pre-enqueue stop (control)")
    mask_c = int(regs["d0"].lstrip("$"), 16) & 0x0F
    snap_c = (await b.call("emulator/read_memory", {"addr": hex(snap), "len": 128}))["bytes"]
    if mask_c == 0:
        raise SetupError("control: pre-enqueue mask is 0 — no dirty line to observe; the "
                         "fixture scene no longer dirties any line per frame")
    dirty_equal_before = all(
        snap_c[ln * 64:(ln + 1) * 64].upper() != POISON[:64]
        for ln in range(4) if mask_c & (1 << ln))
    if dirty_equal_before:
        raise SetupError("CONTROL FAILED: the poison was already gone BEFORE the splices ran "
                         "— the gate is not observing the splices (wrong stop, or something "
                         "else writes the snapshot)")

    # ---- REAL PASS: buffer read at the SAME stop (lesson 3), then run to .no_pal.
    buf_at_stop = (await b.call("emulator/read_memory", {"addr": hex(buf), "len": 128}))["bytes"]
    await stop_at(b, no_pal, ".no_pal (after all four splices)")
    snap_after = (await b.call("emulator/read_memory", {"addr": hex(snap), "len": 128}))["bytes"]

    def check(label: str, cond: bool, detail: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {label}: {detail}")
        if not cond:
            fails.append(label)

    print(f"  captured pre-enqueue mask: %{mask_c:04b} (from d0 at ${beq_stop:06X})")
    for ln in range(4):
        s = snap_after[ln * 64:(ln + 1) * 64].upper()
        p = buf_at_stop[ln * 64:(ln + 1) * 64].upper()
        if mask_c & (1 << ln):
            check(f"line {ln} (dirty): snapshot == payload", s == p,
                  "copied span matches the buffer the DMA shipped" if s == p
                  else f"snapshot {s[:16]}... != payload {p[:16]}...")
        else:
            check(f"line {ln} (clean): poison retained", s == POISON[:64].upper() * 1,
                  "untouched, as the dirty-gating requires" if s == POISON[:64].upper()
                  else f"poison overwritten: {s[:16]}... — the copy is not dirty-gated")

    await b.close()
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    args = ap.parse_args()
    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    if not Path(rom).is_file():
        print(f"snapshot_poison_gate: ROM not found: {rom}", file=sys.stderr)
        return 2

    sym = parse_lst(lst)
    locals_ = {}
    for line in Path(lst).read_text(errors="replace").splitlines():
        if not line.startswith("(0) "):
            continue
        try:
            addrpart, namepart = line[4:].split(" :", 1)
            addr = int(addrpart.split("/", 1)[1], 16)
        except (ValueError, IndexError):
            continue
        name = namepart.strip().rstrip(":")
        if name and name not in locals_:
            locals_[name] = addr & 0xFFFFFF

    need = ("Enqueue_Dirty_Buffers", "Palette_Ship_Snap", "Palette_Buffer",
            "Debug_Scene_Freeze")
    missing = [s for s in need if s not in sym]
    if "$engine.buffers$Enqueue_Dirty_Buffers$no_pal" not in locals_:
        missing.append(".no_pal (mangled local)")
    if missing:
        print(f"snapshot_poison_gate: missing from listing: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    try:
        # deterministic=False: exact stop-PC assertions (the raster_source_gate precedent).
        with headless_emulator(rom, deterministic=False) as sock:
            fails = asyncio.run(run(sock, sym, locals_, lst))
    except SetupError as e:
        print(f"\nsnapshot_poison_gate: SETUP — {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\nsnapshot_poison_gate: run error: {e}", file=sys.stderr)
        return 2

    if fails:
        print(f"\nsnapshot_poison_gate: FAIL — {len(fails)}: {', '.join(fails)}")
        return 1
    print("\nsnapshot_poison_gate: OK — the splices copy what the mask says, when it says")
    return 0


if __name__ == "__main__":
    sys.exit(main())
