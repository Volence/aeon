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

INSTRUMENT: the Rust core (`oracle-aether`) via `tools/aether_instance.py`, converted from
the legacy `oracle_gui` harness 2026-08-26. The breakpoint triple became one `run_to` — see
`stop_at` for why the stop RULE is unchanged, which is what lesson 2 rests on.

Usage: python3 tools/snapshot_poison_gate.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit: 0 gate holds · 1 a splice assertion failed · 2 setup/boot/control error
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient                     # noqa: E402
from aether_instance import aether_emulator, read_bytes, write_bytes  # noqa: E402
from raster_cost_probe import parse_lst          # noqa: E402

AEON = Path(__file__).resolve().parent.parent
POISON_WORD = 0xF1F1
POISON = f"{POISON_WORD:04X}" * 64               # 128 bytes


class SetupError(Exception):
    pass


# ⚠ THIS COMMENT'S ORIGINAL PREMISE EXPIRED. It read "the Rust core serves NO breakpoints
# (`capabilities.breakpoints: false`) and no `wait_for_break`", which was true when written
# and is FALSE now: the oracle lane read `capabilities.breakpoints: true` and a served
# `wait_for_break` out of a LIVE `initialize` on 2026-09-03, and this repo's own
# docs/OVERSEER.md has recorded breakpoints as served since 2026-08-27. The stale sentence
# survived because a comment about ANOTHER repo's capabilities has no gate: neither tree can
# tell you its claim about the other has gone stale, and "verified firsthand at a committed
# revision" does not save it — the oracle lane hit the mirror-image of this the same night,
# citing a booking of theirs about OUR call sites that had likewise expired.
#
# `run_to` REMAINS THE RIGHT CALL HERE, now as a choice rather than an inheritance: it is one
# synchronous call instead of an arm/resume/wait triple, and it keeps the semantics lesson 2
# depends on. Reach for a breakpoint only when you need arm -> run -> halt on a hit you did
# not schedule, which `run_to` structurally cannot express.
# ⚠ AND UNDER MACHINE LOAD `wait_for_break` CAN LIE: it has returned
# `{waitedMs: 0, timeoutReached: true}` at frame 2 on a ten-second timeout (oracle,
# 2026-09-03, `WAITFORBREAK-INSTANT-TIMEOUT`) — a plausible-looking wrong NEGATIVE. A reply
# whose `waitedMs` is far below its `timeoutMs` is UNMEASURED, not a missed break: re-run.
#
# The semantics `run_to` preserves: the predicate is
# evaluated at an instruction boundary, so the machine parks WITH pc == addr and that
# instruction NOT yet executed — which is why a stop at `Enqueue_Dirty_Buffers+4` sees d0
# already loaded by the move.b at +0. The captured mask is identical to the legacy run's,
# which is the evidence that the two stop rules agree here.
STOP_MAX_FRAMES = 120        # the handler runs every frame; 120 is ~2 s of game time


async def stop_at(b: BusClient, addr: int, what: str) -> dict:
    r = await b.call("emulator/run_to", {"addr": hex(addr), "maxFrames": STOP_MAX_FRAMES})
    if not r.get("reached"):
        raise SetupError(f"never reached {what} within {STOP_MAX_FRAMES} frames "
                         f"(stopped at pc={r.get('pc')})")
    regs = await b.call("emulator/registers", {})
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
    head = await read_bytes(b, edb, 2)
    if head.upper() != "1038":
        raise SetupError(f"Enqueue_Dirty_Buffers no longer starts with move.b (xxx).w,d0 "
                         f"(read {head}) — the +4 breakpoint offset is stale; re-derive it")
    beq_stop = edb + 4

    # No params: the Rust core refuses undeclared keys (-32602) and resets to a STOPPED
    # machine, which is what the legacy `{wait, run: False}` pair was asking for.
    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": 180})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})

    # Poison check: no fixture palette word may equal the poison.
    buf_now = await read_bytes(b, buf, 128)
    words = [buf_now[i:i + 4].upper() for i in range(0, 256, 4)]
    if f"{POISON_WORD:04X}" in words:
        raise SetupError("the fixture palette contains the poison word $F1F1 — pick another")

    # ---- CONTROL PASS: poison, stop BEFORE the splices, dirty half MUST fail there.
    await write_bytes(b, snap, POISON)
    regs = await stop_at(b, beq_stop, "the pre-enqueue stop (control)")
    mask_c = int(regs["d0"].lstrip("$"), 16) & 0x0F
    snap_c = await read_bytes(b, snap, 128)
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
    buf_at_stop = await read_bytes(b, buf, 128)
    await stop_at(b, no_pal, ".no_pal (after all four splices)")
    snap_after = await read_bytes(b, snap, 128)

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
        # The legacy `deterministic=False` is gone with the legacy server: it bought exact
        # stop PCs by opting out of the C++ threaded scheduler's coarse rollback. The Rust
        # core has no such mode and `run_to` parks on the exact instruction, so the knob has
        # no counterpart and needs none — every stop-PC assertion below still holds.
        with aether_emulator(rom, symbols=lst) as sock:
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
