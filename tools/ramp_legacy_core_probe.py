#!/usr/bin/env python3
"""ramp_legacy_core_probe — RUN TODAY'S ROM ON THE LEGACY CORE. Is the shift ROM or CORE?

THE QUESTION. `tools/ramp_boundary_probe.py` measured, over 19 tops and 9 run lengths on the
RUST core, that a dense VSRAM ramp's first value lands on screen line `top + 2`. The ORIGINAL
2026-08-14 captures fit `top + 1` on 37 of 37 discriminating rows. engine/effects/raster.emp
concluded from that pair that the ENGINE's write landing moved, fire+1 -> fire+2, and
bracketed it to the perf(raster) batch of 2026-08-19.

THAT CONCLUSION HAS AN UNTESTED ALTERNATIVE, AND raster.emp SAYS SO ITSELF: the 2026-08-14
captures came off the LEGACY Exodus-derived C++ core, and the Rust core became the ratified
default on 2026-08-26. Two candidates — the ROM changed, or the INSTRUMENT changed — and no
pixel taken on one core can separate them. raster.emp also records that the cycle story
PREDICTS THE WRONG DIRECTION: today's path to the write is if anything shorter, and an
earlier write cannot land a line later.

THE DISCRIMINATOR NEEDS NO NEW BUILD: run TODAY's ROM on the LEGACY core.

    today's ROM reads top + 2 on the legacy core  -> the difference is in the ROM.
                                                     The published conclusion stands.
    today's ROM reads top + 1 on the legacy core  -> the difference is in the CORE.
                                                     The 2026-08-19 bracket is a coincidence
                                                     and the conclusion is wrong.

BOTH ARMS ARE PUBLISHABLE. Nothing here prefers either.

THE INSTRUMENT IS NOT THE SAME INSTRUMENT, AND THAT IS STATED RATHER THAN HIDDEN. The legacy
core advertises NO `emulator/scanlines` — its method table (oracle-old ControlSocket.cpp
`Handlers()`) has no such entry, so the per-scanline raster capture the Rust probe asserts
`source == "raster"` on DOES NOT EXIST here. What the legacy core has is `emulator/screenshot`,
which writes the VDP's own rendered image buffer (main_gui.cpp `SaveScreenshotPng`, from
`CopyLatestFrame`'s snapshot of `GetImageBufferData`) — and that is EXACTLY the instrument the
2026-08-14 captures came off, at exactly their 320x224. So this probe is era-matched to the
captures under test, which is the point, and it is a DIFFERENT instrument from the Rust
probe's, which is the caveat.

⚠ THE LEGACY SCREENSHOT IS DOCUMENTED NON-DETERMINISTIC AND IS THEREFORE CONTROLLED, NOT
TRUSTED. oracle-old's own `ab_runner.py` demotes the screenshot to ADVISORY: "the VDP renders
on a dedicated worker thread draining an async operation queue; the rendered framebuffer the
GUI copies is not anchored to the deterministic ExecuteSystemStep count, so two identical runs
can occasionally capture a one-render-frame-off image (~0.4% of pixels)". A one-render-frame-off
capture would corrupt every row diff below. So §0 runs CONTROL vs CONTROL — two identical arms,
two separate boots — and this probe REFUSES to report any boundary unless they are
byte-identical on all 224 rows. That is the same discipline the Rust probe's §1a carries, and
here it is load-bearing rather than ceremonial.

⚠ REWIND. Each arm gets its own freshly-booted isolated instance and takes exactly ONE
`emulator/reset` — ab_runner's stopped anchor — BEFORE any frame is counted. After that anchor
nothing calls reset, restore, a checkpoint, or run_to; every frame is advanced by `run_frames`
alone. The legacy core exposes no absolute frame index (only `frame_token`, the VDP render
token), so `frame_token` is read and printed at every step and a NON-ADVANCING one across the
measurement window is reported. A rewind reads as "no change observed", which is
indistinguishable from a real negative.

⚠ NO `wait_for_break` ANYWHERE IN THIS FILE. Oracle's WAITFORBREAK-INSTANT-TIMEOUT defect
returns `timeoutReached` with `waitedMs` near zero under machine load — a WRONG answer that
presents as "the breakpoint never fired", which on this task would read as "the ramp did
nothing" and could manufacture either verdict. Every stop here is SCHEDULED (`run_frames`),
so the defect cannot reach this measurement.

BOTH TIERS ARE MEASURED, because the published finding has two halves. The claim is that the
DENSE tier moved to fire+2 while the SPARSE tier is still fire+1. If both tiers read the SAME
landing on the legacy core while they disagree by one on the Rust core, that is close to
decisive for the core hypothesis.

    §1  DENSE   — the flat-twin sweep, `ramp_boundary_probe.synth`'s own records, over several
                  tops. Two records identical but for `rrp_start`: every line the run reaches
                  takes a constant offset and no line it misses can move, so the first
                  differing row IS the first reached line.
    §2  SPARSE  — `vsplit_landing_gate`'s own differential, unchanged in substance: two
                  `stream_vsram` fixtures at two split lines, whose disagreement band begins at
                  the landing row.

Both synthesisers are the shipped ones, imported rather than restated: `synth` is validated
byte-for-byte against `raster_ramp_program`'s ROM emission by `ramp_boundary_probe.validate_synth`,
and `program_words`/`stream_vsram` are the transcription `tools/test_raster_wire_pin.py` pins to
raster_dsl.emp.

Usage:
    python3 tools/ramp_legacy_core_probe.py [--rom s4.debug.bin] [--lst s4.debug.lst]
                                            [--tops 40,112,190] [--skip-sparse]
Exit: 0 measured · 2 could not measure (control failed, harness absent, capture unusable)
"""
import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path, harness_path   # noqa: E402
add_client_path()
sys.path.insert(0, str(harness_path()))

from aether import BusClient                            # noqa: E402
from launcher import headless_emulator                  # noqa: E402

# The shipped synthesisers. Imported, never restated — see the header.
import ramp_boundary_probe as RBP                       # noqa: E402
from raster_cost_probe import program_words, stream_vsram   # noqa: E402

SCREEN_LINES = 224
SCREEN_W = 320

# §1 dense — the Rust probe's own constants, so the two runs are comparable arm for arm.
DENSE_SETTLE, DENSE_AFTER = RBP.SETTLE, RBP.AFTER
PROBE_PX = -37          # ramp_boundary_probe's: odd on purpose, a multiple of the 8-px tile
                        # height could alias

# §2 sparse — vsplit_landing_gate's own constants, so its Rust-core reading transfers.
SP_LINE_A, SP_LINE_B, SP_OFFSET = 112, 140, 0x0043
SP_VSRAM_BYTE = 2
SP_SETTLE, SP_POST_FREEZE, SP_DRIVE = 180, 3, 2
SP_CAMERA_Y = 144

SHOTS = Path(os.environ.get("RAMP_LEGACY_SHOTDIR", "/tmp/ramp_legacy_shots"))


class Unmeasurable(Exception):
    """The measurement could not be made. Exit 2 — never a verdict."""


# ---------------------------------------------------------------------------
# One legacy instance, one arm
# ---------------------------------------------------------------------------

async def _c(b, method, params=None, timeout=300.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def _settle_token(b, stable_reads=3, tries=60, delay=0.05):
    """ab_runner's best-effort render settle: wait until status.frame_token stops advancing.

    The system is PAUSED here (run_frames returns with it stopped), so the render thread is
    draining a finite queue and this converges. It is best-effort by construction; §0's
    control-vs-control is what actually licenses the capture."""
    last, stable = None, 0
    for _ in range(tries):
        tok = (await _c(b, "emulator/status", {})).get("frame_token")
        if tok == last:
            stable += 1
            if stable >= stable_reads:
                return tok
        else:
            stable, last = 0, tok
        time.sleep(delay)
    return last


def _png_rows(path: Path) -> list:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.size != (SCREEN_W, SCREEN_LINES):
        raise Unmeasurable(
            "the legacy screenshot is %dx%d, not %dx%d. Every row index below is a SCREEN "
            "LINE; a scaled or letterboxed capture would silently renumber them and the "
            "boundary reported would be a property of the scaler."
            % (im.size[0], im.size[1], SCREEN_W, SCREEN_LINES))
    px = im.tobytes()
    stride = SCREEN_W * 3
    return [px[y * stride:(y + 1) * stride] for y in range(SCREEN_LINES)]


class Arm:
    """One boot, one capture. `track` is the frame_token trail, printed with every result."""

    def __init__(self, label):
        self.label = label
        self.track = []
        self.rows = None

    def mark(self, what, tok):
        self.track.append((what, tok))
        return tok

    def rewound(self):
        """Any DECREASING frame_token step after the anchor. Reported, never swallowed.

        The legacy core exposes no absolute frame index, so this is the only monotone clock
        available. `frame_token` is the VDP's RENDER token, not a frame counter, so it is a
        weaker witness than the Rust core's index — it is printed in full rather than
        summarised, and a decrease is called out rather than trusted to be impossible."""
        pts = [(w, t) for w, t in self.track if t is not None]
        return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)
                if pts[i + 1][1] < pts[i][1]]


def _dense_arm(rom, lst, sym, scratch, record, label):
    """Settle, install `record` (None = untouched control), run, capture."""
    a = Arm(label)
    with headless_emulator(rom) as sock:
        async def go():
            b = BusClient(socket_path=sock, client_id="rlcp", client_name="rlcp")
            info = await b.connect()
            a.server = (info or {}).get("server", {}) if isinstance(info, dict) else {}
            # THE ONE ANCHOR. ab_runner's deterministic stopped anchor, taken BEFORE any
            # frame is counted, so run_frames is the sole clock from here on.
            await _c(b, "emulator/reset", {"wait": True, "run": False})
            a.mark("anchor", (await _c(b, "emulator/status", {})).get("frame_token"))
            done = 0
            while done < DENSE_SETTLE:
                n = min(100, DENSE_SETTLE - done)
                r = await _c(b, "emulator/run_frames", {"frames": n})
                done += n
                a.mark("settle+%d" % done, r.get("frame_token"))
            if record is not None:
                await _c(b, "emulator/write_memory",
                         {"addr": "0x%08X" % RBP.bus24(scratch), "bytes": "0x" + record.hex()})
                back = (await _c(b, "emulator/read_memory",
                                 {"addr": "0x%08X" % RBP.bus24(scratch),
                                  "len": len(record)}))["bytes"]
                if bytes.fromhex(back[2:]) != record:
                    raise Unmeasurable("record did not stage at $%06X" % RBP.bus24(scratch))
                await _c(b, "emulator/write_memory",
                         {"addr": "0x%08X" % RBP.bus24(sym["Raster_Pending"]),
                          "bytes": "0x%08X" % scratch})
            r = await _c(b, "emulator/run_frames", {"frames": DENSE_AFTER})
            a.mark("after-install", r.get("frame_token"))
            if record is not None:
                back = (await _c(b, "emulator/read_memory",
                                 {"addr": "0x%08X" % RBP.bus24(scratch),
                                  "len": len(record)}))["bytes"]
                if bytes.fromhex(back[2:]) != record:
                    raise Unmeasurable(
                        "THE ARM IS VOID: the record at $%06X was CLOBBERED during the %d "
                        "frames it was live." % (RBP.bus24(scratch), DENSE_AFTER))
            a.mode3 = (await _c(b, "emulator/read_memory",
                                {"addr": "0x%08X" % RBP.bus24(sym["VDP_Shadow_Table"] + 0x0B),
                                 "len": 1}))["bytes"]
            a.mark("settled", await _settle_token(b))
            shot = SHOTS / ("%s.png" % label)
            r = await _c(b, "emulator/screenshot", {"path": str(shot)})
            # The Aether client strips the transport's `ok`; the reply's `path` is the
            # witness that the main thread actually wrote a file, and it is re-checked on
            # disk below rather than taken on the reply's word.
            if not r.get("path") or not Path(r["path"]).is_file():
                raise Unmeasurable("screenshot produced no file: %r" % r)
            a.mark("after-capture", (await _c(b, "emulator/status", {})).get("frame_token"))
            a.rows = _png_rows(Path(r["path"]))
        asyncio.run(go())
    return a


def _sparse_arm(rom, lst, sym, words, label):
    """vsplit_landing_gate's capture, on the legacy core, ending in a screenshot."""
    a = Arm(label)
    image = "".join("%04X" % w for w in words)
    buf = sym["Raster_Buf_A"]
    with headless_emulator(rom) as sock:
        async def go():
            b = BusClient(socket_path=sock, client_id="rlcp", client_name="rlcp")
            info = await b.connect()
            a.server = (info or {}).get("server", {}) if isinstance(info, dict) else {}
            await _c(b, "emulator/reset", {"wait": True, "run": False})
            a.mark("anchor", (await _c(b, "emulator/status", {})).get("frame_token"))
            done = 0
            while done < SP_SETTLE:
                n = min(100, SP_SETTLE - done)
                r = await _c(b, "emulator/run_frames", {"frames": n})
                done += n
                a.mark("settle+%d" % done, r.get("frame_token"))
            # Freeze BEFORE the camera poke and the install: a section crossing would build
            # its own schedule over the fixture and the failure would read as a landing.
            await _c(b, "emulator/write_memory",
                     {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
            await _c(b, "emulator/write_memory",
                     {"addr": hex(sym["Camera_Y"]), "value": SP_CAMERA_Y, "width": 2})
            r = await _c(b, "emulator/run_frames", {"frames": SP_POST_FREEZE})
            a.mark("post-freeze", r.get("frame_token"))
            await _c(b, "emulator/write_memory", {"addr": hex(buf), "bytes": "0x" + image})
            for s, v in (("Raster_Patch_Tab", 0), ("Effects_Offscreen_Entry", 0),
                         ("Raster_Active_Buf", buf), ("Raster_Program", buf)):
                await _c(b, "emulator/write_memory",
                         {"addr": hex(sym[s]), "value": v, "width": 4})
            r = await _c(b, "emulator/run_frames", {"frames": SP_DRIVE})
            a.mark("after-install", r.get("frame_token"))
            back = (await _c(b, "emulator/read_memory",
                             {"addr": hex(buf), "len": len(words) * 2}))["bytes"]
            got = back.upper().removeprefix("0X")
            if got != image:
                raise Unmeasurable("the sparse program was rewritten during the run\n"
                                   "  poked: %s\n  read : %s" % (image, got))
            a.mark("settled", await _settle_token(b))
            shot = SHOTS / ("%s.png" % label)
            r = await _c(b, "emulator/screenshot", {"path": str(shot)})
            # The Aether client strips the transport's `ok`; the reply's `path` is the
            # witness that the main thread actually wrote a file, and it is re-checked on
            # disk below rather than taken on the reply's word.
            if not r.get("path") or not Path(r["path"]).is_file():
                raise Unmeasurable("screenshot produced no file: %r" % r)
            a.mark("after-capture", (await _c(b, "emulator/status", {})).get("frame_token"))
            a.rows = _png_rows(Path(r["path"]))
        asyncio.run(go())
    return a


def first_diff(a, b):
    d = [i for i in range(SCREEN_LINES) if a[i] != b[i]]
    if not d:
        return None, [], []
    gaps = [l for l in range(d[0], d[-1] + 1) if a[l] == b[l]]
    return d[0], d, gaps


def sparse_words(line, offset):
    """vsplit_landing_gate.fixture_words, verbatim including its word-0 override and reason."""
    w = program_words([(line, [stream_vsram(SP_VSRAM_BYTE, [offset])])])
    w[0] = 0
    return w


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--tops", default="40,112,190",
                    help="dense tops to sweep; at least three — one cannot distinguish a "
                         "constant offset from a top-dependent one")
    ap.add_argument("--skip-sparse", action="store_true")
    a = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    rom = Path(a.rom).read_bytes()
    sym = RBP.lst_symbols(Path(a.lst))
    tops = [int(x) for x in a.tops.split(",") if x.strip()]
    if len(tops) < 3:
        raise SystemExit("--tops needs at least three tops; see its help.")

    print("ramp_legacy_core_probe — TODAY'S ROM on the LEGACY C++ core")
    print("  aeon tree   %s" % AEON)
    print("  rom         %s  (%d bytes)" % (a.rom, len(rom)))
    print("  harness     %s" % harness_path())
    try:
        rev = subprocess.run(["git", "-C", str(harness_path().parents[1]),
                              "describe", "--always", "--dirty"],
                             capture_output=True, text=True, check=True).stdout.strip()
        head = subprocess.run(["git", "-C", str(harness_path().parents[1]),
                               "log", "--oneline", "-1"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception as e:                                    # noqa: BLE001
        rev, head = "UNKNOWN (%s)" % e, ""
    gui = harness_path().parents[0] / "build" / "oracle_gui"
    print("  oracle-old  %s" % rev)
    print("              %s" % head)
    print("              binary %s  %d bytes  mtime %s"
          % (gui, gui.stat().st_size,
             time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(gui.stat().st_mtime))))
    print("  ⚠ the legacy core advertises NO emulator/scanlines; captures below are")
    print("    emulator/screenshot — the VDP image buffer, the SAME instrument the")
    print("    2026-08-14 captures came off, and DOCUMENTED non-deterministic (see header).")
    print()

    print("§WIRE  the synthesiser against the constructor")
    RBP.validate_synth(rom, sym)
    scratch = RBP.pick_scratch(rom, sym)
    print()

    VS, VA = "Vsram", 2
    rc = 0

    # ---- §0 control vs control -------------------------------------------
    print("§0  CONTROL vs CONTROL on the legacy core")
    print("    two identical untouched arms, two separate boots. Nothing below is")
    print("    attributable until these are byte-identical on all %d rows — the legacy"
          % SCREEN_LINES)
    print("    screenshot is documented advisory-only, so this is load-bearing.")
    cA = _dense_arm(a.rom, a.lst, sym, scratch, None, "ctlA")
    cB = _dense_arm(a.rom, a.lst, sym, scratch, None, "ctlB")
    same = sum(1 for x, y in zip(cA.rows, cB.rows) if x == y)
    print("    %d of %d rows identical   reg $0B %s / %s" % (same, SCREEN_LINES,
                                                             cA.mode3, cB.mode3))
    print("    frame_token trail A: %s" % (cA.track,))
    print("    frame_token trail B: %s" % (cB.track,))
    print("    non-advancing frame_token steps: A %s  B %s" % (cA.rewound(), cB.rewound()))
    if same != SCREEN_LINES:
        d = [i for i in range(SCREEN_LINES) if cA.rows[i] != cB.rows[i]]
        print("    -> the two instances do NOT reproduce each other (%d rows differ, "
              "first %d, last %d)." % (len(d), d[0], d[-1]))
        print("    THE CAPTURE IS UNUSABLE FOR A ROW DIFF ON THIS CORE. No boundary is")
        print("    reported: a one-render-frame-off screenshot would corrupt every diff")
        print("    below, and a corrupted diff is indistinguishable from a moved landing.")
        print("elapsed %.1f s" % (time.time() - t0))
        return 2
    print("    -> the UNTREATED path reproduces.")

    # §0b — the TREATED path. §0a installs nothing, so it exercises neither the RAM poke nor
    # the dense run itself; a capture that is stable with the raster program idle says
    # nothing about one taken while .dense_body is re-arming reg $0A on every scanline of the
    # frame. Two arms with the SAME record must also be byte-identical, or the flat-twin
    # diffs below are reading render jitter.
    tr = RBP.synth(112, 64, VS, VA, RBP.fp16(0, 0), 0)
    tA = _dense_arm(a.rom, a.lst, sym, scratch, tr, "trtA")
    tB = _dense_arm(a.rom, a.lst, sym, scratch, tr, "trtB")
    tsame = sum(1 for x, y in zip(tA.rows, tB.rows) if x == y)
    print("    TREATED control (identical records, top 112, lines 64): %d of %d rows "
          "identical" % (tsame, SCREEN_LINES))
    print("    frame_token trail A: %s" % (tA.track,))
    print("    non-advancing frame_token steps: A %s  B %s" % (tA.rewound(), tB.rewound()))
    if tsame != SCREEN_LINES:
        d = [i for i in range(SCREEN_LINES) if tA.rows[i] != tB.rows[i]]
        print("    -> two IDENTICAL treated arms disagree on %d rows (first %d, last %d). "
              "The flat-twin diff cannot be attributed to the record." % (len(d), d[0], d[-1]))
        print("elapsed %.1f s" % (time.time() - t0))
        return 2
    print("    -> reproducible on both paths. The row diff is licensed.")
    print()

    # ---- §1 dense ---------------------------------------------------------
    print("§1  DENSE tier — flat-twin sweep over `top`  (offset %+d px, ALL LAYERS ON)"
          % PROBE_PX)
    print("    two records identical but for rrp_start; the first differing row IS the")
    print("    first line the run reaches")
    print("    %-5s %-6s %-9s %-9s %-7s %-6s %-5s %s"
          % ("top", "lines", "top+1?", "reached", "delta", "last", "gaps", "reg $0B"))
    dense = []
    for top in tops:
        lines = min(64, 223 - top)
        ra = RBP.synth(top, lines, VS, VA, RBP.fp16(0, 0), 0)
        rb = RBP.synth(top, lines, VS, VA, RBP.fp16(PROBE_PX, 0), 0)
        A = _dense_arm(a.rom, a.lst, sym, scratch, ra, "dense%d_a" % top)
        B = _dense_arm(a.rom, a.lst, sym, scratch, rb, "dense%d_b" % top)
        f, d, g = first_diff(A.rows, B.rows)
        dense.append((top, f))
        print("    %-5d %-6d %-9d %-9s %-7s %-6s %-5d %s/%s"
              % (top, lines, top + 1, f, ("%+d" % (f - top)) if f is not None else "-",
                 d[-1] if d else "-", len(g), A.mode3, B.mode3))
        rw = A.rewound() + B.rewound()
        if rw:
            print("        ⚠ NON-ADVANCING frame_token: %s" % (rw,))
    deltas = sorted(set(f - t for t, f in dense if f is not None))
    print("    distinct (reached - top) over %d tops: %s" % (len(dense), deltas))
    if len(deltas) == 1:
        print("    -> the DENSE landing on the LEGACY core is top %+d" % deltas[0])
    else:
        print("    -> NOT CONSTANT across tops. Report the table, not a single offset.")
    print()

    # ---- §2 sparse --------------------------------------------------------
    if not a.skip_sparse:
        print("§2  SPARSE tier — vsplit_landing_gate's differential, on the legacy core")
        print("    two stream_vsram fixtures at lines %d and %d, offset $%04X; the"
              % (SP_LINE_A, SP_LINE_B, SP_OFFSET))
        print("    disagreement band BEGINS at the landing row")
        try:
            sA = _sparse_arm(a.rom, a.lst, sym, sparse_words(SP_LINE_A, SP_OFFSET), "sp_a")
            sB = _sparse_arm(a.rom, a.lst, sym, sparse_words(SP_LINE_B, SP_OFFSET), "sp_b")
            d = [i for i in range(3, SCREEN_LINES) if sA.rows[i] != sB.rows[i]]
            first = d[0] if d else None
            width = len(d)
            contig = (d == list(range(d[0], d[0] + width))) if d else False
            print("    band: %d rows, first %s, last %s, contiguous %s"
                  % (width, first, d[-1] if d else "-", contig))
            print("    authored spacing %d rows (%d..%d); band width %d -> %s"
                  % (SP_LINE_B - SP_LINE_A, SP_LINE_A, SP_LINE_B, width,
                     "MATCHES" if width == SP_LINE_B - SP_LINE_A else "DOES NOT MATCH"))
            if first is not None:
                print("    -> the SPARSE landing on the LEGACY core is line %+d from the "
                      "authored split (%d - %d)" % (first - SP_LINE_A, first, SP_LINE_A))
            rw = sA.rewound() + sB.rewound()
            if rw:
                print("        ⚠ NON-ADVANCING frame_token: %s" % (rw,))
        except Unmeasurable as e:
            print("    UNMEASURABLE: %s" % e)
            rc = 2
        print()

    print("shots under %s" % SHOTS)
    print("elapsed %.1f s" % (time.time() - t0))
    return rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Unmeasurable as e:
        print("UNMEASURABLE: %s" % e, file=sys.stderr)
        raise SystemExit(2)
