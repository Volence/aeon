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
from suite_paths import add_client_path, harness_path, suite_path  # noqa: E402
add_client_path()
sys.path.insert(0, str(harness_path()))

from contextlib import contextmanager                  # noqa: E402
from aether import BusClient                            # noqa: E402
from launcher import headless_emulator                  # noqa: E402
from aether_instance import aether_emulator, assert_rust_server   # noqa: E402

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
SP_SETTLE, SP_DRIVE = 180, 8

# SP_DRIVE IS 8, NOT vsplit_landing_gate's 2, AND THE REASON IS MEASURED. On the Rust core
# either value gives the identical answer (band 28 rows starting at 113, at drive 2 and at
# drive 8). On the LEGACY core drive 2 gives NO BAND AT ALL -- zero differing rows, which
# reads exactly like "this core cannot show a mid-frame VSRAM split" and is not true: at
# drive 8 the same fixtures band normally. The extra frames are what let the legacy render
# thread get a full frame out with the newly-installed schedule live. 8 is DENSE_AFTER, so
# both tiers now drive the same number of frames after their install.
#
# ⚠ THE NULL AT DRIVE 2 IS THE TRAP THIS CONSTANT EXISTS TO NAME: it is a silent one. Nothing
# errors, the program readback passes, the frame lock passes, and the probe reports "the
# fixtures did not differ" -- a clean, confident, WRONG negative about the very tier the
# published finding says did not move.

# FREEZE_NOTE — THE SCENE IS PINNED IN EVERY ARM, AND THAT IS A MEASURED NECESSITY.
# ramp_boundary_probe does NOT freeze, because on the Rust core it does not have to: that
# core's `emulator/scanlines` reads the per-line raster capture synchronously and its
# control-vs-control ran 224/224. The legacy core cannot do that. MEASURED HERE, 2026-09-03,
# on this ROM and this binary:
#
#   UNFROZEN, two identical boots:  state_hash combined IDENTICAL (0x3B24E54DAB1346B1 both)
#                                   state_hash framebuffer DIFFERENT
#                                   79-83 of 224 screenshot rows differ, and the differing
#                                   BAND MOVES between runs (141..223 one pair, 0..78 another)
#   FROZEN, three identical boots:  state_hash combined identical, and all three screenshots
#                                   224/224 byte-identical to each other
#
# So the machine is perfectly deterministic on the legacy core and only its RENDER is not:
# the framebuffer the GUI copies is not anchored to the ExecuteSystemStep count (oracle-old's
# own ab_runner demotes the screenshot to advisory for exactly this), and on a SCROLLING scene
# a one-render-frame-off capture moves whole bands of rows. Freezing removes the scroll, which
# removes the difference between adjacent frames, which is what makes the capture reproducible.
# It changes nothing about the quantity under test: a landing offset is which screen line a
# VSRAM value displays on, and the camera's position is not an input to it.
#
# THE FREEZE IS THEREFORE APPLIED ON BOTH CORES. Holding it on one side only would put a
# second difference beside the core, and the whole point of this probe is that the core is the
# only one.
POST_FREEZE = 3
CAMERA_Y = 144

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
        tok = _tk(await _c(b, "emulator/status", {}))
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
        self.frames = 0          # frames this arm asked run_frames to execute, in total
        self.attempt = 1

    def token_delta(self):
        """`frame_token` advanced across the whole arm, anchor to capture."""
        pts = [t for _, t in self.track if t is not None]
        return None if len(pts) < 2 else pts[-1] - pts[0]

    def frame_locked(self):
        """Did the RENDER keep up with the MACHINE?

        THE ONE CHECK THAT MAKES A LEGACY SCREENSHOT ADMISSIBLE. `frame_token` is the VDP's
        rendered-frame counter and it advances 1:1 with `run_frames` when nothing is dropped.
        A SHORTFALL means the render thread skipped a frame, so the image on disk is a frame
        the machine has already left -- oracle-old's own ab_runner names exactly this as why
        its screenshot is advisory. MEASURED HERE 2026-09-03: with the scene frozen the
        capture is byte-reproducible across boots WHEN this holds, and the arms where it did
        not hold are precisely the ones that produced impossible pictures (a `top` 40 run
        differing from row 5, a 28-row authored band coming back 146 rows wide and
        non-contiguous). BgAnim and the palette cycle keep ticking under Debug_Scene_Freeze --
        vsplit_landing_gate says so -- so one frame off is dozens of rows off.

        An arm that is not frame-locked is RETRIED, never reported. Reporting it would be
        reporting the instrument."""
        d = self.token_delta()
        return d is not None and d == self.frames

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


# ---------------------------------------------------------------------------
# THE TWO CORES, behind one arm. Everything the arm does is identical; only these
# three things differ, and each difference is MEASURED, not assumed:
#
#   boot      legacy: `launcher.headless_emulator` (xvfb + oracle_gui), then ONE
#                     `emulator/reset {"wait": true, "run": false}` for ab_runner's stopped
#                     anchor -- the legacy server free-runs after boot and this is what
#                     stops it.
#             rust:   `aether_instance.aether_emulator`, which boots PAUSED at frame 0.
#                     `emulator/reset` takes NO params there (undeclared keys are refused),
#                     and none is needed.
#   identity  rust ONLY: `assert_rust_server`, so a gate cannot silently land on the legacy
#             server. The legacy side asserts the MIRROR of it -- serverName "oracle" -- for
#             exactly the same reason in the opposite direction. A probe whose whole claim is
#             "which core answered" must not take the core on faith.
#   capture   legacy: `emulator/screenshot` (there is no `emulator/scanlines`).
#             rust:   `emulator/scanlines` with `source == "raster"` asserted -- the ratified
#                     reading, and the one ramp_boundary_probe's +2 was measured with.
# ---------------------------------------------------------------------------

LEGACY, RUST = "legacy", "rust"

# THE TWO CORES DISAGREE ABOUT THE "0x" PREFIX ON A BYTE STRING, and it is a hard error, not
# a nicety: the legacy `OpWrite`'s HexDecode refuses a prefixed string outright
# ("bytes must be an even-length hex string"), while the Rust core's write_memory takes one.
# Reads come back prefixed on both. Normalising in one place is what keeps every poke below
# core-agnostic -- a per-call `if core ==` would be four chances to send one core the other's
# spelling and read the resulting refusal as a failed install.

def _wr_bytes(core: str, hexstr: str) -> str:
    """A byte string in the spelling THIS core's write_memory accepts."""
    h = hexstr.upper().removeprefix("0X")
    return h if core == LEGACY else "0x" + h


def _rd_bytes(reply) -> bytes:
    """A read_memory reply's payload, prefix or not, as raw bytes."""
    return bytes.fromhex(reply["bytes"].upper().removeprefix("0X"))



def _assert_legacy_server(info: dict) -> None:
    """The mirror of `assert_rust_server`. Measured discriminator, aether_instance's table:
    the legacy C++ server answers serverName "oracle", the Rust one "oracle-next"."""
    name = (info or {}).get("serverName")
    impl = (info or {}).get("implementation")
    if impl is not None and impl != "oracle-cpp":
        raise Unmeasurable("wanted the LEGACY core; server answered implementation=%r" % impl)
    if impl is None and name != "oracle":
        raise Unmeasurable(
            "wanted the LEGACY core; the server answered serverName=%r (the Rust core "
            "answers 'oracle-next'). This probe's entire claim is about WHICH CORE "
            "answered, so it refuses to measure one it cannot identify." % name)


@contextmanager
def _boot(core, rom, lst):
    if core == LEGACY:
        with headless_emulator(rom) as sock:
            yield sock
    else:
        with aether_emulator(rom, symbols=lst) as sock:
            yield sock


async def _connect(core, sock):
    b = BusClient(socket_path=sock, client_id="rlcp", client_name="rlcp")
    info = await b.connect()
    info = info if isinstance(info, dict) else {}
    if core == RUST:
        assert_rust_server(info)
        await _c(b, "emulator/reset", {})
    else:
        _assert_legacy_server(info)
        await _c(b, "emulator/reset", {"wait": True, "run": False})
    return b, info


CAPTURE = ["native"]     # "native" | "screenshot" -- see --capture


async def _capture(core, b, label):
    """The rendered display, 224 rows, as opaque per-row byte strings.

    ⚠ THE CAPTURE API IS A CANDIDATE EXPLANATION IN ITS OWN RIGHT, WHICH IS WHY IT IS A KNOB.
    The legacy core can only be read with `emulator/screenshot` and the Rust core is normally
    read with `emulator/scanlines`, so a one-line difference between the two cores could just
    as well be a one-line difference between the two APIs' row numbering -- and "the ratified
    reading is off by one against its own core's framebuffer" is a completely different
    finding from "the cores render differently". `--capture screenshot` runs the Rust core
    through the SAME api as the legacy one, which separates them: if the Rust screenshot
    agrees with Rust scanlines, the API is exonerated and the core carries the difference."""
    if core == LEGACY or CAPTURE[0] == "screenshot":
        await _settle_token(b)
        r = await _c(b, "emulator/screenshot", {"path": str(SHOTS / ("%s.png" % label))})
        # The Aether client strips the transport's `ok`; the reply's `path` is the witness
        # that the main thread actually wrote a file, and it is re-checked on disk here
        # rather than taken on the reply's word.
        if not r.get("path") or not Path(r["path"]).is_file():
            raise Unmeasurable("screenshot produced no file: %r" % r)
        return _png_rows(Path(r["path"]))
    rows, got = [], 0
    while got < SCREEN_LINES:
        n = min(8, SCREEN_LINES - got)
        r = await _c(b, "emulator/scanlines", {"startLine": got, "count": n})
        if r.get("source") != "raster":
            raise Unmeasurable(
                "emulator/scanlines answered source=%r -- a post-hoc render is rendered from "
                "END-OF-FRAME VDP state and carries ONE VSRAM value for the whole frame, so "
                "every per-line raster effect is erased and the empty diff is "
                "indistinguishable from a real negative." % r.get("source"))
        rows += [ln["rgb"].encode() for ln in r["rows"]]
        got += n
    return rows


async def _freeze(b, sym, a):
    """Pin the scene. MEASURED NECESSITY, not hygiene -- see FREEZE_NOTE."""
    await _c(b, "emulator/write_memory",
             {"addr": "0x%08X" % RBP.bus24(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await _c(b, "emulator/write_memory",
             {"addr": "0x%08X" % RBP.bus24(sym["Camera_Y"]), "value": CAMERA_Y, "width": 2})
    r = await _c(b, "emulator/run_frames", {"frames": POST_FREEZE})
    a.frames += POST_FREEZE
    a.mark("post-freeze", _tk(r))


def _tk(reply):
    """THE ARM'S CLOCK, and the two cores do not spell it the same.

    legacy: `frame_token` -- the VDP's RENDERED-frame counter. That is deliberately the one
            read there: the legacy core's defect is that its RENDER falls behind its MACHINE,
            so the render's own counter is the only thing that can witness it.
    rust:   `frame` -- the absolute machine frame index. That core has no separate render
            thread for `emulator/scanlines` to fall behind, so its lock is satisfied by
            construction and costs nothing. There is no `frame_token` on it at all, and
            reading a missing key as None made every Rust arm fail the lock with `advanced
            None` before this existed.

    They are DIFFERENT QUANTITIES and the difference is the point, not an inconvenience.
    """
    if reply is None:
        return None
    v = reply.get("frame_token")
    return reply.get("frame") if v is None else v


async def _run(b, a, total, tag):
    done = 0
    while done < total:
        n = min(100, total - done)
        r = await _c(b, "emulator/run_frames", {"frames": n})
        done += n
        a.frames += n
        a.mark("%s+%d" % (tag, done), _tk(r))


def _dense_arm_once(core, rom, lst, sym, scratch, record, label):
    """Settle, freeze, install `record` (None = untouched control), run, capture."""
    a = Arm(label)
    with _boot(core, rom, lst) as sock:
        async def go():
            b, info = await _connect(core, sock)
            a.server = info
            a.mark("anchor", _tk(await _c(b, "emulator/status", {})))
            await _run(b, a, DENSE_SETTLE, "settle")
            await _freeze(b, sym, a)
            if record is not None:
                await _c(b, "emulator/write_memory",
                         {"addr": "0x%08X" % RBP.bus24(scratch),
                          "bytes": _wr_bytes(core, record.hex())})
                back = _rd_bytes(await _c(b, "emulator/read_memory",
                                          {"addr": "0x%08X" % RBP.bus24(scratch),
                                           "len": len(record)}))
                if back != record:
                    raise Unmeasurable("record did not stage at $%06X (wrote %s read %s)"
                                       % (RBP.bus24(scratch), record.hex(), back.hex()))
                await _c(b, "emulator/write_memory",
                         {"addr": "0x%08X" % RBP.bus24(sym["Raster_Pending"]),
                          "bytes": _wr_bytes(core, "%08X" % scratch)})
            r = await _c(b, "emulator/run_frames", {"frames": DENSE_AFTER})
            a.frames += DENSE_AFTER
            a.mark("after-install", _tk(r))
            if record is not None:
                back = _rd_bytes(await _c(b, "emulator/read_memory",
                                          {"addr": "0x%08X" % RBP.bus24(scratch),
                                           "len": len(record)}))
                if back != record:
                    raise Unmeasurable(
                        "THE ARM IS VOID: the record at $%06X was CLOBBERED during the %d "
                        "frames it was live. A diff produced by whatever overwrote it is not "
                        "a measurement." % (RBP.bus24(scratch), DENSE_AFTER))
            a.mode3 = _rd_bytes(await _c(
                b, "emulator/read_memory",
                {"addr": "0x%08X" % RBP.bus24(sym["VDP_Shadow_Table"] + 0x0B),
                 "len": 1})).hex().upper()
            a.state = await _c(b, "emulator/state_hash", {})
            a.rows = await _capture(core, b, label)
            a.mark("after-capture", _tk(await _c(b, "emulator/status", {})))
        asyncio.run(go())
    return a


def _sparse_arm_once(core, rom, lst, sym, words, label):
    """vsplit_landing_gate's capture, on either core."""
    a = Arm(label)
    image = "".join("%04X" % w for w in words)
    buf = sym["Raster_Buf_A"]
    with _boot(core, rom, lst) as sock:
        async def go():
            b, info = await _connect(core, sock)
            a.server = info
            a.mark("anchor", _tk(await _c(b, "emulator/status", {})))
            await _run(b, a, SP_SETTLE, "settle")
            # Freeze BEFORE the install: a section crossing would build its own schedule over
            # the fixture and the failure would read as a landing.
            await _freeze(b, sym, a)
            await _c(b, "emulator/write_memory",
                     {"addr": "0x%08X" % RBP.bus24(buf), "bytes": _wr_bytes(core, image)})
            for s, v in (("Raster_Patch_Tab", 0), ("Effects_Offscreen_Entry", 0),
                         ("Raster_Active_Buf", buf), ("Raster_Program", buf)):
                await _c(b, "emulator/write_memory",
                         {"addr": "0x%08X" % RBP.bus24(sym[s]), "value": v, "width": 4})
            r = await _c(b, "emulator/run_frames", {"frames": SP_DRIVE})
            a.frames += SP_DRIVE
            a.mark("after-install", _tk(r))
            got = _rd_bytes(await _c(b, "emulator/read_memory",
                                     {"addr": "0x%08X" % RBP.bus24(buf),
                                      "len": len(words) * 2})).hex().upper()
            if got != image:
                raise Unmeasurable("the sparse program was rewritten during the run\n"
                                   "  poked: %s\n  read : %s" % (image, got))
            a.mode3 = _rd_bytes(await _c(
                b, "emulator/read_memory",
                {"addr": "0x%08X" % RBP.bus24(sym["VDP_Shadow_Table"] + 0x0B),
                 "len": 1})).hex().upper()
            a.state = await _c(b, "emulator/state_hash", {})
            a.rows = await _capture(core, b, label)
            a.mark("after-capture", _tk(await _c(b, "emulator/status", {})))
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

def _provenance(core):
    print("  core        %s" % core.upper())
    if core == LEGACY:
        h = harness_path()
        try:
            rev = subprocess.run(["git", "-C", str(h.parents[1]), "describe", "--always",
                                  "--dirty"], capture_output=True, text=True,
                                 check=True).stdout.strip()
            head = subprocess.run(["git", "-C", str(h.parents[1]), "log", "--oneline", "-1"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        except Exception as e:                                     # noqa: BLE001
            rev, head = "UNKNOWN (%s)" % e, ""
        gui = h.parents[0] / "build" / "oracle_gui"
        st = gui.stat()
        print("  harness     %s" % h)
        print("  oracle-old  %s" % rev)
        print("              %s" % head)
        print("              binary %s" % gui)
        print("              %d bytes, mtime %s"
              % (st.st_size, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))))
        print("  capture     emulator/screenshot -- the legacy core advertises NO")
        print("              emulator/scanlines (its Handlers() table has no such entry).")
        print("              This IS the instrument the 2026-08-14 captures came off.")
    else:
        srv = suite_path("oracle-next", "target", "release", "oracle-aether")
        st = Path(srv).stat()
        try:
            rev = subprocess.run(["git", "-C", str(suite_path("oracle-next")), "describe",
                                  "--always", "--dirty"], capture_output=True, text=True,
                                 check=True).stdout.strip()
        except Exception as e:                                     # noqa: BLE001
            rev = "UNKNOWN (%s)" % e
        print("  server      %s" % srv)
        print("  oracle      %s" % rev)
        print("              %d bytes, mtime %s"
              % (st.st_size, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))))
        if CAPTURE[0] == "screenshot":
            print("  capture     emulator/screenshot -- FORCED, to match the legacy core's "
                  "only option")
            print("              (this core's native reading is emulator/scanlines; forcing "
                  "the")
            print("              screenshot makes the capture API identical across cores)")
        else:
            print("  capture     emulator/scanlines, source == 'raster' asserted per chunk")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", choices=[LEGACY, RUST], default=LEGACY)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--tops", default="40,112,190",
                    help="dense tops to sweep; at least three -- one top cannot distinguish a "
                         "constant offset from a top-dependent one, and the Rust-core result "
                         "under test is constant across 19")
    ap.add_argument("--capture", choices=["native", "screenshot"], default="native",
                    help="native = scanlines on the Rust core, screenshot on the legacy one "
                         "(the legacy core has no scanlines). screenshot = force the "
                         "screenshot path on BOTH, which makes the capture API identical and "
                         "leaves the core as the only difference.")
    ap.add_argument("--skip-sparse", action="store_true")
    a = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    core = a.core
    CAPTURE[0] = a.capture
    t0 = time.time()

    rom = Path(a.rom).read_bytes()
    sym = RBP.lst_symbols(Path(a.lst))
    tops = [int(x) for x in a.tops.split(",") if x.strip()]
    if len(tops) < 3:
        raise SystemExit("--tops needs at least three tops; see its help.")

    print("ramp_legacy_core_probe -- the SAME ROM on EITHER core. ROM or CORE?")
    print("  aeon tree   %s" % AEON)
    print("  rom         %s" % a.rom)
    print("              %d bytes, md5 %s"
          % (len(rom), __import__("hashlib").md5(rom).hexdigest()))
    _provenance(core)
    print("  scene       FROZEN in every arm (Debug_Scene_Freeze=1, Camera_Y=%d) -- see "
          "FREEZE_NOTE" % CAMERA_Y)
    print()

    print("§WIRE  the synthesiser against the constructor")
    RBP.validate_synth(rom, sym)
    scratch = RBP.pick_scratch(rom, sym)
    print()

    VS, VA = "Vsram", 2
    rc = 0

    def show(label, arm):
        print("      %-6s frame_token %s" % (label, arm.track))
        print("             frame lock: token advanced %s over %d frames run (attempt %d)"
              % (arm.token_delta(), arm.frames, arm.attempt))
        print("             reg $0B %s   VDP state combined %s"
              % (arm.mode3, arm.state.get("combined")))
        if arm.rewound():
            print("             *** NON-ADVANCING frame_token: %s" % (arm.rewound(),))

    # ---- §0 control ------------------------------------------------------
    print("§0  CONTROL vs CONTROL on the %s core" % core)
    print("    Two arms per path, two separate boots each. Nothing below is attributable")
    print("    until they are byte-identical on all %d rows." % SCREEN_LINES)
    print("    (a) UNTREATED -- nothing installed")
    cA = dense_arm(core, a.rom, a.lst, sym, scratch, None, "%s_ctlA" % core)
    cB = dense_arm(core, a.rom, a.lst, sym, scratch, None, "%s_ctlB" % core)
    show("A", cA)
    show("B", cB)
    same = sum(1 for x, y in zip(cA.rows, cB.rows) if x == y)
    print("        %d of %d rows identical; VDP state %s"
          % (same, SCREEN_LINES,
             "IDENTICAL" if cA.state.get("combined") == cB.state.get("combined") else "DIFFERS"))
    if same != SCREEN_LINES:
        d = [i for i in range(SCREEN_LINES) if cA.rows[i] != cB.rows[i]]
        print("        -> NOT reproducible (%d rows differ, %d..%d)." % (len(d), d[0], d[-1]))
        print("        THE CAPTURE IS UNUSABLE FOR A ROW DIFF ON THIS CORE. No boundary is")
        print("        reported: a corrupted diff is indistinguishable from a moved landing.")
        print("elapsed %.1f s" % (time.time() - t0))
        return 2

    # §0b -- the TREATED path. §0a installs nothing, so it exercises neither the RAM poke nor
    # the dense run itself; a capture that is stable with the raster program idle says nothing
    # about one taken while .dense_body is re-arming reg $0A on every scanline of the frame.
    print("    (b) TREATED -- two arms with the SAME record (top 112, lines 64)")
    tr = RBP.synth(112, 64, VS, VA, RBP.fp16(0, 0), 0)
    tA = dense_arm(core, a.rom, a.lst, sym, scratch, tr, "%s_trtA" % core)
    tB = dense_arm(core, a.rom, a.lst, sym, scratch, tr, "%s_trtB" % core)
    show("A", tA)
    show("B", tB)
    tsame = sum(1 for x, y in zip(tA.rows, tB.rows) if x == y)
    print("        %d of %d rows identical; VDP state %s"
          % (tsame, SCREEN_LINES,
             "IDENTICAL" if tA.state.get("combined") == tB.state.get("combined") else "DIFFERS"))
    if tsame != SCREEN_LINES:
        d = [i for i in range(SCREEN_LINES) if tA.rows[i] != tB.rows[i]]
        print("        -> two IDENTICAL treated arms disagree on %d rows (%d..%d). The "
              "flat-twin diff cannot be attributed to the record." % (len(d), d[0], d[-1]))
        print("elapsed %.1f s" % (time.time() - t0))
        return 2
    # The treated control must also DIFFER from the untreated one, or the install did nothing
    # and every flat-twin diff below would be measuring two copies of the same picture.
    inst = sum(1 for x, y in zip(cA.rows, tA.rows) if x != y)
    print("        treated vs untreated: %d rows differ -> the install %s"
          % (inst, "REACHES THE PICTURE" if inst else "IS INVISIBLE (nothing is being measured)"))
    if inst == 0:
        print("elapsed %.1f s" % (time.time() - t0))
        return 2
    print("    -> reproducible on both paths, and the install is visible. Diffs licensed.")
    print()

    # ---- §1 dense --------------------------------------------------------
    print("§1  DENSE tier -- flat-twin sweep over `top` (offset %+d px, all layers ON)"
          % PROBE_PX)
    print("    Two records identical but for rrp_start: every line the run REACHES takes a")
    print("    constant offset and no line it misses can move, so the first differing row IS")
    print("    the first reached line.")
    print("    %-5s %-6s %-9s %-9s %-7s %-6s %-5s %s"
          % ("top", "lines", "top+1?", "reached", "delta", "last", "gaps", "reg $0B"))
    dense = []
    for top in tops:
        lines = min(64, 223 - top)
        ra = RBP.synth(top, lines, VS, VA, RBP.fp16(0, 0), 0)
        rb = RBP.synth(top, lines, VS, VA, RBP.fp16(PROBE_PX, 0), 0)
        A = dense_arm(core, a.rom, a.lst, sym, scratch, ra, "%s_d%d_a" % (core, top))
        B = dense_arm(core, a.rom, a.lst, sym, scratch, rb, "%s_d%d_b" % (core, top))
        f, d, g = first_diff(A.rows, B.rows)
        dense.append((top, f))
        print("    %-5d %-6d %-9d %-9s %-7s %-6s %-5d %s/%s   lock %s/%s tries %d/%d"
              % (top, lines, top + 1, f, ("%+d" % (f - top)) if f is not None else "-",
                 d[-1] if d else "-", len(g), A.mode3, B.mode3,
                 A.token_delta(), B.token_delta(), A.attempt, B.attempt))
        rw = A.rewound() + B.rewound()
        if rw:
            print("        *** NON-ADVANCING frame_token: %s" % (rw,))
    deltas = sorted(set(f - t for t, f in dense if f is not None))
    print("    distinct (reached - top) over %d tops (%s): %s"
          % (len(dense), ",".join(str(t) for t in tops), deltas))
    if len(deltas) == 1:
        print("    -> DENSE landing on the %s core: top %+d" % (core.upper(), deltas[0]))
    else:
        print("    -> NOT CONSTANT across tops. Report the table, not a single offset.")
    print()

    # ---- §2 sparse -------------------------------------------------------
    if not a.skip_sparse:
        print("§2  SPARSE tier -- vsplit_landing_gate's differential, on the %s core" % core)
        print("    Two stream_vsram fixtures at lines %d and %d, offset $%04X. Their"
              % (SP_LINE_A, SP_LINE_B, SP_OFFSET))
        print("    disagreement band BEGINS at the landing row and its WIDTH is the authored")
        print("    spacing -- a width that is not %d means the two edges moved differently"
              % (SP_LINE_B - SP_LINE_A))
        print("    and no single landing offset describes the result.")
        try:
            sA = sparse_arm(core, a.rom, a.lst, sym, sparse_words(SP_LINE_A, SP_OFFSET),
                            "%s_sp_a" % core)
            sB = sparse_arm(core, a.rom, a.lst, sym, sparse_words(SP_LINE_B, SP_OFFSET),
                            "%s_sp_b" % core)
            show("A", sA)
            show("B", sB)
            d = [i for i in range(3, SCREEN_LINES) if sA.rows[i] != sB.rows[i]]
            first = d[0] if d else None
            width = len(d)
            contig = bool(d) and d == list(range(d[0], d[0] + width))
            print("        band: %d rows, first %s, last %s, contiguous %s"
                  % (width, first, d[-1] if d else "-", contig))
            print("        authored spacing %d; band width %d -> %s"
                  % (SP_LINE_B - SP_LINE_A, width,
                     "MATCHES" if width == SP_LINE_B - SP_LINE_A else "DOES NOT MATCH"))
            if first is not None:
                print("    -> SPARSE landing on the %s core: split %+d (row %d for a split "
                      "authored at %d)" % (core.upper(), first - SP_LINE_A, first, SP_LINE_A))
            else:
                print("    -> NO BAND AT ALL. The fixtures did not differ; nothing is measured.")
                rc = 2
        except Unmeasurable as e:
            print("    UNMEASURABLE: %s" % e)
            rc = 2
        print()

    print("shots under %s" % SHOTS)
    print("elapsed %.1f s" % (time.time() - t0))
    return rc




# ---------------------------------------------------------------------------
# THE FRAME LOCK. Every arm is taken until the render kept up with the machine.
# ---------------------------------------------------------------------------

LOCK_TRIES = 5


def _locked(fn, label, *args):
    """Take the arm until `frame_locked()`, or refuse to report one.

    The Rust core locks on the first try by construction (`run_frames` is synchronous and
    there is no separate render thread to fall behind), so this costs it nothing; the legacy
    core drops a frame occasionally and this is what keeps a dropped one out of the results
    instead of averaging it in. Every attempt is announced, so a core that needs many is
    visible rather than silently expensive."""
    for i in range(1, LOCK_TRIES + 1):
        a = fn(*args, label if i == 1 else "%s_try%d" % (label, i))
        a.attempt = i
        if a.frame_locked():
            if i > 1:
                print("        (%s: frame-locked on attempt %d)" % (label, i))
            return a
        print("        (%s: attempt %d NOT frame-locked -- frame_token advanced %s over %d "
              "frames run; the render dropped one and the image on disk is a frame the "
              "machine has left. Retrying.)"
              % (label, i, a.token_delta(), a.frames))
    raise Unmeasurable(
        "%s never frame-locked in %d attempts (frame_token advanced %s over %d frames). The "
        "render thread on this core cannot be held to the machine here, so no screenshot "
        "taken in this arm is admissible and NO boundary is reported from it."
        % (label, LOCK_TRIES, a.token_delta(), a.frames))


def dense_arm(core, rom, lst, sym, scratch, record, label):
    return _locked(_dense_arm_once, label, core, rom, lst, sym, scratch, record)


def sparse_arm(core, rom, lst, sym, words, label):
    return _locked(_sparse_arm_once, label, core, rom, lst, sym, words)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Unmeasurable as e:
        print("UNMEASURABLE: %s" % e, file=sys.stderr)
        raise SystemExit(2)
