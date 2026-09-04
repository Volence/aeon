#!/usr/bin/env python3
"""dma_straddle_reading — the reading DoD item 15's last live row has been waiting for.

`parcel/dma-straddle-counter` (2026-09-03) BUILT the instrument and said so plainly: "THE
MEASUREMENT IS NOT [done] — this entry stays OPEN, and the reserve is UNCHANGED at 2. No
emulator was used in that parcel; the reading is owed by a foreground session and only that
reading closes this." This is that session.

THE QUESTION. `.split_reject` refuses BOTH halves of a 128 KB-straddling transfer when only
one Important slot is free, so a straddling Important landing costs two slots or is dropped
whole. `DPLC_ENTRY_RESERVE = 2` is what holds those two open. That reserve was sized from
total art VOLUME, which bounds how many straddling entries exist in the ROM and says nothing
about how many can want slots in ONE FRAME. `Dbg_DMA_Straddle_Peak` is the per-frame
high-water mark, and the booking calls it "THE number this booking asks for".

    The reserve is adequate iff the measured peak never exceeds it.

THE POSITIVE CONTROL IS NOT OPTIONAL AND IT IS THE WHOLE DESIGN. A zero in the Important
cells is the expected-and-desirable outcome, and it is also exactly what a probe that never
reached gameplay, never loaded art, or read the wrong addresses would report. Those are
indistinguishable without a witness that the instrument fires at all — bar 16(d)'s absence
surface, on a result whose GOOD value is the empty one. `Dbg_DMA_Straddle_All` counts
straddling enqueues on EVERY queue, free-running, and is that witness: if it is zero, this
run says nothing whatever and the tool refuses rather than reporting a reassuring zero.

WHAT IS DERIVED: `DPLC_ENTRY_RESERVE` (engine/objects/dplc.emp) and `DMA_IMPORTANT_SLOTS`
(engine/system/constants.emp) are read from source; every cell address comes from the
listing. Nothing about the verdict is typed in.

WHAT THIS CANNOT SAY. A peak is a fact about the play this drives, not about all possible
play. The drive below is deliberately art-heavy — long runs both ways across section
boundaries with jumps and look-ups, which is what forces page-ins and animation DPLC churn —
but a peak of N means "N was reached", never "N is the maximum". Read a pass as "no frame in
this exercise wanted more than the reserve holds", and say so in those words.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

SETTLE = 180          # boot -> gameplay, the tree-wide constant
MAX_CHUNK = 3600      # the server's limits.maxRunFrames
NEED = ("Character_ID",)
CELLS = ("Dbg_DMA_Straddle_All", "Dbg_DMA_Straddle_Frame", "Dbg_DMA_Straddle_Peak",
         "DMA_Split_Reject_Count", "DMA_Peak_Important", "DMA_Overflow_Count")


def read_const(path, name):
    src = Path(path).read_text()
    hits = re.findall(r"^\s*(?:pub\s+)?const\s+%s\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$" % name,
                      src, re.M)
    if len(hits) != 1:
        raise SystemExit("%s: expected one `const %s`, found %d" % (path, name, len(hits)))
    v = hits[0]
    return int(v[1:], 16) if v.startswith("$") else int(v)


def legs(total, hold, pulse, period, pulse_len):
    """One play_input program: hold a direction for the whole leg, pulsing a button."""
    rows = [{"start": 0, "end": total, "buttons": list(hold)}]
    t = 0
    while t < total:
        rows.append({"start": t, "end": min(t + pulse_len, total), "buttons": [pulse]})
        t += period
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--leg", type=int, default=3600, help="frames per leg")
    ap.add_argument("--legs", type=int, default=4, help="how many legs to drive")
    ap.add_argument("--character", type=int, default=0,
                    help="A-presses to cycle Character_ID before driving (0 sonic, 1 tails, "
                         "2 knuckles). Only Knuckles' art straddles a 128 KB boundary, so 2 "
                         "is the only value that can move the straddle cells at all.")
    a = ap.parse_args()

    rom, lst, root = Path(a.rom), Path(a.lst), Path(a.root)
    for p in (rom, lst):
        if not p.is_file():
            raise SystemExit("missing %s — DEBUG=1 ./build.sh first (the cells are DEBUG-only)" % p)
    if a.leg > MAX_CHUNK:
        raise SystemExit("--leg %d exceeds one server call's ceiling of %d" % (a.leg, MAX_CHUNK))

    reserve = read_const(root / "engine/objects/dplc.emp", "DPLC_ENTRY_RESERVE")
    slots = read_const(root / "engine/system/constants.emp", "DMA_IMPORTANT_SLOTS")
    sym = parse_lst(str(lst))
    missing = [c for c in CELLS + NEED if c not in sym]
    if missing:
        raise SystemExit(
            "%s carries no %s. These cells are DEBUG-only; a release listing cannot answer this "
            "question and a run against one would report zeros that mean nothing."
            % (lst.name, ", ".join(missing)))

    print("DERIVED FROM SOURCE")
    print("  DPLC_ENTRY_RESERVE   %d   (engine/objects/dplc.emp)" % reserve)
    print("  DMA_IMPORTANT_SLOTS  %d   (engine/system/constants.emp)" % slots)
    print("  cells                %s" % ", ".join("%s=$%06X" % (c, sym[c] & 0xFFFFFF)
                                                  for c in ("Dbg_DMA_Straddle_Peak",
                                                            "Dbg_DMA_Straddle_All")))
    print()

    with aether_emulator(rom, symbols=lst) as sock:
        async def go():
            b = BusClient(socket_path=sock, client_id="strd", client_name="dma_straddle")
            await b.connect()

            async def cells():
                out = {}
                for c in CELLS:
                    v = (await b.call("emulator/read_memory",
                                      {"addr": "0x%08X" % (sym[c] & 0xFFFFFF), "len": 2}))["bytes"]
                    out[c] = int(v, 16)
                return out

            await b.call("emulator/run_frames", {"frames": SETTLE})
            print("  settled %d frames" % SETTLE)

            # WHICH CHARACTER IS IN PLAY IS THE WHOLE EXPERIMENT, and it took a wasted run to
            # learn it. `tools/dplc_straddle.py --gate` reports that of every sprite set in
            # the ROM, only KNUCKLES' art crosses a 128 KB boundary (at 0x60000), on exactly
            # ONE animation frame ($88). Sonic's crosses none, Tails' crosses none. So a
            # session that drives the default player can never move these cells, however long
            # it plays — its zero is structural, not evidence about the reserve.
            # Debug_CharacterHotkey cycles on a bare A press (vetoed by B, by START held, and
            # by a live replay); a hand poke of Character_ID alone would desync it from
            # Player_Chardef, which characters.emp refuses by name, so the hotkey is the only
            # correct route.
            for i in range(a.character):
                await b.call("emulator/play_input",
                             {"rows": [{"start": 0, "end": 2, "buttons": ["a"]}], "maxFrames": 2})
                await b.call("emulator/release_all", {})
                await b.call("emulator/run_frames", {"frames": 10})
            cid = (await b.call("emulator/read_memory",
                                {"addr": "0x%08X" % (sym["Character_ID"] & 0xFFFFFF),
                                 "len": 2}))["bytes"]
            cid = int(cid, 16)
            print("  Character_ID = %d after %d A-press(es)" % (cid, a.character))
            if cid != a.character:
                raise SystemExit(
                    "THE CHARACTER DID NOT CYCLE: Character_ID is %d after %d A-press(es). "
                    "Debug_CharacterHotkey stands down while Input_Source is non-zero "
                    "(replaying or recording) and vetoes on B or on START held. Without the "
                    "intended character in play this run measures the wrong subject, and for "
                    "the straddle cells specifically it would report a structural zero."
                    % (cid, a.character))
            snaps = [("settle", await cells())]
            for i in range(a.legs):
                # Alternate direction so the camera crosses every section boundary both ways;
                # pulse C (jump) to force the airborne/roll animation DPLC churn, and hold up
                # on the last leg because LookUp is the state the reserve booking names.
                hold = ["right"] if i % 2 == 0 else ["left"]
                pulse = "c" if i < a.legs - 1 else "up"
                await b.call("emulator/play_input",
                             {"rows": legs(a.leg, hold, pulse, 90, 12), "maxFrames": a.leg})
                await b.call("emulator/release_all", {})
                s = await cells()
                snaps.append(("leg%d %s+%s" % (i + 1, hold[0], pulse), s))
                print("  leg %d (%s, pulsing %s, %d frames): all=%d peak=%d reject=%d"
                      % (i + 1, hold[0], pulse, a.leg, s["Dbg_DMA_Straddle_All"],
                         s["Dbg_DMA_Straddle_Peak"], s["DMA_Split_Reject_Count"]))
            return snaps

        snaps = asyncio.run(go())

    final = snaps[-1][1]
    print()
    print("FINAL CELLS after %d frames of driven play" % (SETTLE + a.leg * a.legs))
    for c in CELLS:
        print("  %-24s %d" % (c, final[c]))
    print()

    if final["Dbg_DMA_Straddle_All"] == 0:
        print("THIS RUN SAYS NOTHING — REFUSING TO REPORT IT AS A PASS")
        print("  Dbg_DMA_Straddle_All is 0, so NOT ONE straddling transfer was enqueued on ANY")
        print("  queue in the whole exercise. That is the positive control, and without it a")
        print("  zero in the Important cells is indistinguishable from a probe that never")
        print("  reached gameplay, never loaded art, or read the wrong addresses. The good")
        print("  answer here is a zero, which is exactly why it cannot be accepted un-witnessed.")
        print()
        print("  BEFORE DRIVING LONGER, CHECK WHICH SUBJECT IS IN PLAY. Run")
        print("  `python3 tools/dplc_straddle.py --gate`: it reports, per sprite set, how many")
        print("  128 KB boundaries that art spans. If the character you drove spans none, this")
        print("  cell CANNOT fire however long you play and its zero is structural. As measured")
        print("  2026-09-04, only KNUCKLES straddles (one boundary at 0x60000, one frame $88);")
        print("  Sonic and Tails span none. Re-run with --character 2.")
        return 1

    peak = final["Dbg_DMA_Straddle_Peak"]
    print("THE READING")
    print("  straddling enqueues, all queues   %d   (the positive control — the instrument fires)"
          % final["Dbg_DMA_Straddle_All"])
    print("  per-frame Important peak          %d   against a reserve of %d" % (peak, reserve))
    print("  transfers dropped by .split_reject %d" % final["DMA_Split_Reject_Count"])
    print("  peak Important occupancy          %d bytes = %.1f of %d slots"
          % (final["DMA_Peak_Important"], final["DMA_Peak_Important"] / 14.0, slots))
    print("  queue-full overflows              %d" % final["DMA_Overflow_Count"])
    print()

    fails = []
    if peak > reserve:
        fails.append(
            "THE RESERVE IS TOO SMALL: a frame wanted %d straddling Important slots and "
            "DPLC_ENTRY_RESERVE holds %d open. This is the exact failure the booking predicted "
            "could not be seen before the counter existed — the reserve was sized from art "
            "VOLUME, which cannot bound per-frame demand." % (peak, reserve))
    if final["DMA_Split_Reject_Count"]:
        fails.append(
            "%d transfer(s) were DROPPED WHOLE by .split_reject during ordinary driven play. "
            "Whole-rejection is deliberate, but a drop in play means a landing did not happen "
            "and page_in will not have marked those pages resident."
            % final["DMA_Split_Reject_Count"])

    if fails:
        print("FINDING")
        for f in fails:
            print("  * %s" % f)
        return 1
    print("NO FRAME IN THIS EXERCISE WANTED MORE THAN THE RESERVE HOLDS.")
    print("  Peak %d <= reserve %d, and nothing was dropped by .split_reject. Stated as a fact")
    print("  about this play and not about all play: a peak says a value was REACHED, never")
    print("  that it is the maximum. What closes the booking is that the number now exists and")
    print("  was taken with its positive control lit, which is what it asked for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
