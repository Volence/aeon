#!/usr/bin/env python3
"""raster_frame_epoch_probe — does a fire on the last active line survive the frame rewind?

THE HAZARD THIS EXISTS TO OBSERVE (docs/DEFERRED_WORK.md, raster substrate sweep item 3).
`Raster_VBlank` rewinds the frame unconditionally: it clears the dense mode, points
`Raster_Cursor` at the priming record and re-arms reg $0A = 0. `Raster_HInt` carries no
frame or line test at all. So if an IRQ4 raised near the end of active display is still
PENDING when IRQ6 (VBlank) is taken -- IRQ6 masks level 4 -- that IRQ4 runs AFTER the
rewind. It then consumes priming record 0, overwrites the reg $0A = 0 the rewind just
flushed, and the whole next frame walks the schedule one record out of step.

That reasoning was SOURCE-ONLY. This probe is the measurement, and it is deliberately
built so that a null result is as informative as a positive one: if the fire on the last
line retires in-frame like every other fire, the ordering the source argument assumes is
not what the hardware does, and the fix must not be shipped on the argument alone.

WHAT IS OBSERVED, AND WHY IT NEEDS NO PIXELS. Two execution breakpoints -- `Raster_HInt`
and `Raster_VBlank` -- turn one frame into an ORDERED EVENT LIST, which is exactly the
quantity in dispute:

    healthy   H H H V | H H H V | ...      the fire retires before the rewind
    hazard    H H V H | ...                the third fire runs AFTER the rewind

and every event carries `Raster_Cursor` read at the breakpoint, i.e. BEFORE that fire
consumes its record. A cursor offset is a record index in bytes from the buffer base, so
the healthy walk reads 2, 6, 10 (priming 0, priming 1, the event) and a fire that lands
after the rewind reads 2 again -- the rewind put it back. The shift into the NEXT frame is
then visible as the same list starting from the wrong offset.

TWO INSTRUMENT FACTS, both found the hard way and both load-bearing:

  * `emulator/status`'s `frame_token` is the VDP's LAST-RENDERED-IMAGE token and it does
    NOT advance in a headless instance -- it read a constant 492/496 across six confirmed
    VBlank breakpoint hits. Frames are therefore grouped by the game's own
    `Frame_Counter` ($FF8002), which is RAM and advances whatever the renderer does.
  * RESUMING FROM A BREAKPOINT'S OWN ADDRESS RE-BREAKS WITHOUT EXECUTING. A plain
    resume/wait_for_break loop reports a rising `hits` count and a stopped CPU every
    time while nothing runs at all -- 24 "hits" with `Frame_Counter` and `Raster_Cursor`
    frozen at their initial values. It is the persistent-breakpoint face of oracle's
    defect 1 (`linux-port/harness/breakpoint_regression_test.py`, bar [1]). One
    `emulator/step` before each resume steps off the address and the trace becomes real;
    without it this probe would confidently report "no hazard" on a machine that never
    ran a single instruction, which is why the step is here and not an optimisation.

THE FIXTURE IS POKED, NOT AUTHORED. `raster_gradient_program` / `raster_ramp_program`
refuse `top + lines > 223` precisely to make this unauthorable, so the hazardous program is
written straight into `Raster_Buf_A` and the four pointers that make it live are poked
beside it -- the discipline `tools/raster_cost_probe.py` established and documents. The
wire encoder is imported from that probe rather than re-transcribed (a third copy of the
format is the drift its wire pin exists to prevent).

ONE FIRE, ONE REGISTER WRITE, ON A SWEPT LINE. The op is a `reg_set` of $8C81 -- the H40
base reg $0C already holds -- so the fire does real dispatch work but changes nothing
observable, and any difference between sweep points is the LINE and nothing else. The
sweep runs a control far from the boundary alongside the candidates, so "the instrument
sees a healthy frame" is proven in the same run as any claimed defect.

Usage:
    python3 tools/raster_frame_epoch_probe.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/raster_frame_epoch_probe.py --lines 199,222,223 --json out.json
Exit: 0 the sweep ran (read the verdicts) - 1 an assertion/control failed - 3 setup problem
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, str(AEON / "tools"))
HARNESS = "/home/volence/sonic_hacks/oracle/linux-port/harness"
sys.path.insert(0, HARNESS)

from aether import BusClient            # noqa: E402
from launcher import headless_emulator  # noqa: E402
from raster_cost_probe import (  # noqa: E402
    ARM_EVERY_LINE, ARM_PARK, CRAM_WRITE, OPS_END, OP_RUN_GRADIENT, _delta,
    parse_lst, program_words, reg_set, stream_cram,
)

REGW = 0x8C81            # reg $0C H40 base — a write that changes nothing
DEFAULT_LINES = "199,220,221,222,223,224,225"

SYMS = ("Raster_Buf_A", "Raster_Cursor", "Raster_Program", "Raster_Active_Buf",
        "Raster_Patch_Tab", "Effects_Offscreen_Entry", "Debug_Scene_Freeze",
        "Raster_HInt", "Raster_VBlank", "Frame_Counter", "OJZ_GradientStream")


def dense_words(top: int, lines: int, cram_addr: int, stream: int) -> list[int]:
    """`raster_gradient_program`'s wire image, WITHOUT its `top + lines <= 223` refusal.

    raster_cost_probe.dense_program_words raises on the barred range, which is correct for
    a cost fixture and useless here: the whole point of this probe is to run the program
    the constructors exist to forbid. Everything else is the same schedule — two priming
    records, a setup record at T-1 carrying OP_RUN_GRADIENT, then the terminator.
    """
    cmd = CRAM_WRITE | _delta(cram_addr)
    return [1 << (cram_addr >> 5),
            ARM_EVERY_LINE | ((top - 1) - 1 - 1), 0,     # record 0 — priming
            ARM_EVERY_LINE, 0,                           # record 1 — priming, every-line
            ARM_EVERY_LINE, 1,                           # record 2 — setup
            OP_RUN_GRADIENT,
            (cmd >> 16) & 0xFFFF, cmd & 0xFFFF,
            lines,
            (stream >> 16) & 0xFFFF, stream & 0xFFFF,
            ARM_PARK, OPS_END]


def stall_words(first: int, second: int, spin: int) -> list[int]:
    """Two fires, the FIRST holding IPL 7 across the VINT instant. THE FORCING FIXTURE.

    The sparse and dense sweeps both found every fire retiring before the rewind, which
    leaves the booked mechanism untested rather than disproved: the source argument needs
    the CPU to be masked at level >= 4 at the moment IRQ6 arrives, and nothing in a normal
    schedule puts it there. This fixture puts it there on purpose, with no engine change and
    no emulator feature — only the authoring surface plus one poked word.

    HOW. `Raster_HInt` runs its whole body inside `ints_off` (IPL 7 — it must, or a nested
    VBlank would retarget the VDP address latch mid-CRAM-burst). Since substrate item 1a a
    stream op's blanking delay is a `dbf` count carried IN THE PROGRAM, one word the fixture
    owns. A large count therefore holds IPL 7 for as long as we like:

      fire 1 @ `first`   OP_CRAM with `spin` dbf iterations = 10 cycles each. At 400 that is
                         ~4,000 cycles, about eight scanlines — the handler is still running,
                         masked, when the VDP raises VINT at line 224.
      fire 2 @ `second`  its IRQ4 is raised DURING that spin, so it too is pending and masked.

    At fire 1's `rte` both IRQ4 and IRQ6 are pending and the 68000 takes the higher first:
    IRQ6 runs VInt, `Raster_VBlank` rewinds the cursor and re-arms reg $0A = 0, and only then
    is the deferred IRQ4 serviced — the exact ordering item 3 is booked on. The one place a
    real schedule reaches the same state is a main-loop `ints_off` bracket straddling the
    boundary, which this engine has many of; a long fire is simply the version a probe can
    author.

    Run it against the SAME program with the solved (small) spin and the only variable is the
    mask window.
    """
    words = program_words([(first + 1, [stream_cram(34, [0x0EEE])]),
                           (second + 1, [reg_set(REGW)])])
    # Program layout: [mask][arm0][ops0][arm1][ops1][arm2][ops2] then fire 1's body. An
    # OP_CRAM body is [op][cmd hi][cmd lo][spin][count-1][colour...], so the spin word is
    # index 7 + 3. Asserted rather than assumed — a wire-format change must fail here loudly
    # rather than poke a colour word and produce a confidently wrong null result.
    assert words[7] == 2, f"fire 1's first op is {words[7]}, not OP_CRAM — layout drifted"
    words[10] = spin
    return words


class Wedged(Exception):
    """An RPC did not answer inside its deadline — the instance is unusable."""


async def _c(b, method, params=None, timeout=45.0):
    """Every call goes through here, and every call has a deadline.

    A resume that never breaks leaves the emulator running free, and the NEXT call on the
    socket then blocks with no timeout of its own: the first version of this probe sat for
    thirty minutes that way, emulator at 150% CPU and driver at 0%, and had to be killed
    with no partial results at all. A per-call deadline plus a per-fixture instance (see
    main) turns that into one lost fixture, reported.
    """
    try:
        return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise Wedged(f"{method} did not answer in {timeout}s") from e


async def _install(b, sym, fixture, settle):
    """Boot -> settle -> freeze the camera -> poke the fixture into Raster_Buf_A."""
    if fixture["kind"] == "stall":
        words = stall_words(fixture["first"], fixture["second"], fixture["spin"])
    elif fixture["kind"] == "dense":
        # The shipped ROM stream, so nothing about the memory the run reads is a probe
        # artifact. CRAM $48 = palette line 2, the address the dense cost fixtures use.
        words = dense_words(fixture["top"], fixture["lines"], 0x48,
                            sym["OJZ_GradientStream"])
    else:
        # program_words authors in SCREEN lines and applies the tier's own -1, so a fire on
        # line F is authored as screen line F+1. Everything below talks in FIRE lines,
        # which is the quantity the hazard is about.
        words = program_words([(fixture["fire"] + 1, [reg_set(REGW)])])
    image = "".join(f"{w:04X}" for w in words)

    await _c(b, "emulator/reset", {"wait": True, "run": False}, 60.0)
    await _c(b, "emulator/run_frames", {"frames": settle}, 120.0)
    await _c(b, "emulator/write_memory",
             {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await _c(b, "emulator/run_frames", {"frames": 2})

    buf = sym["Raster_Buf_A"]
    await _c(b, "emulator/write_memory", {"addr": hex(buf), "bytes": image})
    for name, val in (("Raster_Patch_Tab", 0), ("Effects_Offscreen_Entry", 0),
                      ("Raster_Active_Buf", buf), ("Raster_Program", buf)):
        await _c(b, "emulator/write_memory",
                 {"addr": hex(sym[name]), "value": val, "width": 4})
    await _c(b, "emulator/run_frames", {"frames": 2})
    return words, image


async def _trace(b, sym, events):
    """Collect `events` (handler, frame_token, cursor offset) triples."""
    buf = sym["Raster_Buf_A"]
    hint, vbl = sym["Raster_HInt"], sym["Raster_VBlank"]
    await _c(b, "emulator/pause")
    await _c(b, "emulator/breakpoint_clear", {"all": True})
    await _c(b, "emulator/breakpoint_add", {"addr": hex(hint)})
    await _c(b, "emulator/breakpoint_add", {"addr": hex(vbl)})
    out, dropped = [], []
    for _ in range(events):
        # Step OFF the breakpoint address first — see the module note; without this the
        # resume re-breaks on the same instruction and the CPU never advances.
        await _c(b, "emulator/step", {"count": 1})
        await _c(b, "emulator/resume")
        r = await _c(b, "emulator/wait_for_break", {"timeout_ms": 6000}, 20.0)
        if r.get("running") is not False:
            out.append({"kind": "TIMEOUT"})
            break
        st = await _c(b, "emulator/status")
        pc = int(st["pc"], 16) & 0xFFFFFF
        cur = await _c(b, "emulator/read_memory",
                       {"addr": hex(sym["Raster_Cursor"]), "len": 4})
        c = int(cur["bytes"], 16) & 0xFFFFFF
        fc = await _c(b, "emulator/read_memory",
                      {"addr": hex(sym["Frame_Counter"]), "len": 2})
        # A stop on neither breakpoint is a PREFIX of the next one, not an event. The common
        # case is $FFB452, HBlank_Vector_Slot: the `step` above lands on the IRQ4 vector's
        # target and the following resume breaks at Raster_HInt one `jmp` later — the SAME
        # fire, seen twice. Counting it split one fire into two and made a healthy frame read
        # as a different shape from its neighbours. Dropped rather than merged, and counted,
        # so "the instrument saw something it did not classify" stays visible.
        kind = ("H" if pc == (hint & 0xFFFFFF)
                else "V" if pc == (vbl & 0xFFFFFF) else None)
        if kind is None:
            dropped.append(f"${pc:06X}")
            continue
        out.append({
            "kind": kind,
            "pc": f"${pc:06X}",
            "ft": int(fc["bytes"], 16),
            "cur": (c - buf) if buf <= c < buf + 128 else None,
            "cur_raw": f"${c:06X}",
        })
    await _c(b, "emulator/pause")
    await _c(b, "emulator/breakpoint_clear", {"all": True})
    return out, dropped


def _frames(trace):
    """Group the event list into per-frame strings, keyed by frame_token."""
    frames, cur_ft, acc = [], None, []
    for e in trace:
        if e["kind"] == "TIMEOUT":
            continue
        if e["ft"] != cur_ft:
            if acc:
                frames.append((cur_ft, acc))
            cur_ft, acc = e["ft"], []
        acc.append(e)
    if acc:
        frames.append((cur_ft, acc))
    return frames


def _verdict(frames):
    """HEALTHY iff every complete frame walks the identical schedule.

    A frame is COMPLETE if it contains a V event; the leading and trailing partial groups
    are dropped because the trace can start and stop anywhere. Two independent signatures
    are read off each complete frame and BOTH must be uniform across the sample:

      shape   the event kinds in order, e.g. "HHHV" — a fire deferred past the rewind
              leaves its own frame one H short and lands in the next one, so the hazard
              shows up as two different shapes alternating rather than as one repeated.
      cursor  the record offsets those fires READ, e.g. "2,6,10" — the walk itself. A
              post-rewind fire reads 2 (the rewind put the cursor back on priming record
              0), so a shifted schedule is visible even where the shape alone is not.

    Grouping is by the game's Frame_Counter, so a fire that runs after Raster_VBlank is
    attributed to the frame the counter had already advanced to — which is exactly why the
    verdict tests UNIFORMITY over the sample rather than looking for an H after a V.
    """
    shapes, cursors, order, complete = {}, {}, [], 0
    # The FIRST and LAST groups are partial by construction — the trace starts and stops
    # wherever the event budget lands, so the first group is missing however many fires
    # happened before the breakpoints were armed and the last is missing its rewind. Only
    # the tail was dropped at first, and the head then reported a lone "V" as a frame whose
    # every fire had vanished. Both ends go.
    frames = frames[1:-1] if len(frames) > 2 else []
    for ft, evs in frames:
        seq = "".join(e["kind"] for e in evs)
        cur = ",".join("-" if e["cur"] is None else str(e["cur"])
                       for e in evs if e["kind"] == "H")
        order.append(f"{ft}:{seq}")
        if "V" not in seq:
            continue
        complete += 1
        shapes[seq] = shapes.get(seq, 0) + 1
        cursors[cur] = cursors.get(cur, 0) + 1
    return {"complete_frames": complete, "shapes": shapes, "cursors": cursors,
            "uniform": complete > 0 and len(shapes) == 1 and len(cursors) == 1,
            "order": order}


async def _sweep_one(b, sym, fixture, settle, events):
    words, image = await _install(b, sym, fixture, settle)
    trace, dropped = await _trace(b, sym, events)
    back = await _c(b, "emulator/read_memory",
                    {"addr": hex(sym["Raster_Buf_A"]), "len": len(words) * 2})
    v = _verdict(_frames(trace))
    v["name"] = fixture["name"]
    v["image_intact"] = (back["bytes"].upper() == image)
    v["timed_out"] = any(e["kind"] == "TIMEOUT" for e in trace)
    v["dropped"] = dropped
    v["trace"] = trace
    return v


def _row(r: dict) -> str:
    sh = "  ".join(f"{k}x{v}" for k, v in sorted(r["shapes"].items()))
    cu = "  ".join(f"[{k}]x{v}" for k, v in sorted(r["cursors"].items()))
    verdict = ("WEDGED" if r.get("wedged") else "STALLED" if r["timed_out"]
               else "UNIFORM" if r["uniform"] else "VARIES")
    drop = f"  (+{len(r['dropped'])} unclassified stops)" if r.get("dropped") else ""
    return (f"{r['name']:22} {r['complete_frames']:6} "
            f"{'yes' if r['image_intact'] else 'NO':>6} {verdict:>8}  {sh} | {cu}{drop}")


def _fixtures(lines_arg: str, dense_arg: str, stall_arg: str) -> list[dict]:
    """`--lines` one-fire sparse · `--dense` top:lines · `--stall` first:second:spin."""
    out = []
    for x in (t.strip() for t in lines_arg.split(",")):
        if x:
            out.append({"kind": "sparse", "fire": int(x), "name": f"sparse@{x}"})
    for x in (t.strip() for t in dense_arg.split(",")):
        if not x:
            continue
        top, lines = (int(v) for v in x.split(":"))
        out.append({"kind": "dense", "top": top, "lines": lines,
                    "name": f"dense {top}+{lines}->{top + lines - 1}"})
    for x in (t.strip() for t in stall_arg.split(",")):
        if not x:
            continue
        first, second, spin = (int(v) for v in x.split(":"))
        out.append({"kind": "stall", "first": first, "second": second, "spin": spin,
                    "name": f"stall {first}(spin {spin})+{second}"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--lines", default=DEFAULT_LINES, help="sparse fire lines to sweep")
    ap.add_argument("--dense", default="",
                    help="dense gradient fixtures as top:lines pairs, e.g. 216:7,216:8")
    ap.add_argument("--stall", default="",
                    help="forcing fixtures as first:second:spin, e.g. 222:224:400")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--events", type=int, default=16, help="breakpoint stops per fixture")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

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

    fixtures = _fixtures(args.lines, args.dense, args.stall)
    results = []

    print(f"ROM {args.rom}")
    print(f"{'FIXTURE':22} {'frames':>6} {'intact':>6} {'verdict':>8}  "
          f"shapes (H = Raster_HInt, V = Raster_VBlank) | cursor offsets read per fire",
          flush=True)

    async def _run(sock, fx):
        # deterministic=False: the threaded path is the only one whose breakpoints stop on
        # the exact PC (the serial scheduler rolls back to commit granularity), and this
        # probe classifies every stop BY its PC.
        b = BusClient(socket_path=sock, client_id="rfep", client_name="raster_frame_epoch")
        await b.connect()
        await _c(b, "emulator/load_symbols", {"path": args.lst})
        try:
            r = await _sweep_one(b, sym, fx, args.settle, args.events)
        except Wedged as e:
            r = {"name": fx["name"], "complete_frames": 0, "shapes": {}, "cursors": {},
                 "uniform": False, "order": [], "image_intact": True, "timed_out": True,
                 "wedged": str(e), "dropped": [], "trace": []}
        results.append(r)
        try:
            await b.close()
        except Exception:                                  # noqa: BLE001
            pass

    # ONE INSTANCE PER FIXTURE. A fixture whose program stops firing leaves the emulator
    # running free and the socket unusable for everything after it; a shared instance turned
    # that into a whole lost sweep twice. A fresh instance also removes any question of one
    # fixture's poked state surviving into the next.
    for fx in fixtures:
        with headless_emulator(args.rom, deterministic=False) as sock:
            asyncio.run(_run(sock, fx))
        print(_row(results[-1]), flush=True)

    bad = sum(0 if r["image_intact"] else 1 for r in results)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"\nwrote {args.json}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
