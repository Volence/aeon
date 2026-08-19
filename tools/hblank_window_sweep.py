#!/usr/bin/env python3
"""hblank_window_sweep — locate the horizontal-blanking window in cycle space.

Substrate item 1b. The spec is `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-SPEC.md`;
this file is its driver, and every number it prints is measured here rather than restated
from that document. §7 of the spec governs: a disagreement with the §3 prediction
(N in [15,19], centre 17) is the FINDING, never a cue to adjust the fixture.

WHAT THE FIRST RUN FOUND, so a reader starts where the 2026-08-19 session ended --
`HBLANK-WINDOW-SWEEP-RESULTS.md` beside the spec has the evidence:
  * `emulator/scanlines` resolves a landing to ONE SCANLINE, not to a pixel: the row is
    rendered once per line at the line-start event (oracle-core's Limitation L1). §6's
    verdicts therefore bucket rather than measure, and the driver says so out loud.
  * The window comes instead from WHERE THE PICTURE CHANGES -- see `boundary_analysis`.
    Measured: 30.0 cyc per burst word, 490.0 cyc per sampling period, upper edge N=21.5.
  * The spec's §4 fixture is vacuous on this ROM for two independent reasons, both fixed
    here with measurements rather than guesses: see PAL_MASK and `fx_sweep`'s `addr`.

WHAT IS BEING MEASURED. Since substrate item 1a the blanking spin is a WORD IN THE RASTER
PROGRAM (`move.w (a1)+, d1` ahead of `.cram_delay`), not a constant, so the pre-burst delay
of one op is authorable per op and pokeable per capture. One fire, one leading OP_CRAM,
authored at screen line 100 -- the defective shape -- and the only thing that varies across
the sweep is the single word at `Raster_Buf_A + 20`. Where the resulting CRAM write LANDS is
read out of the rendered picture: a write inside active display recolours the pixels drawn
after it and leaves the ones before it alone, so the first column that changed is the
landing point, to within the art's own sampling of the CRAM entries being written.

THE ENCODER IS NOT RE-IMPLEMENTED HERE. `raster_cost_probe.program_words` builds the image;
it is pinned against `engine/effects/raster_dsl.emp` by `tools/test_raster_wire_pin.py`, and
a third transcription of the wire format is exactly the drift the pin exists to prevent.

THE INSTRUMENT, AND THE ONE ASSERTION THAT MATTERS. oracle-next's `emulator/scanlines`
returns `source`, which is `"raster"` when the reply comes from a retained per-line frame and
`"stateRender"` when it is rendered post-hoc from current VDP state. A post-hoc render shows
N=0 and N=17 as IDENTICAL -- by end of frame the CRAM value is the same either way, and the
whole question is *when* it changed. Every capture below therefore hard-fails on
`source != "raster"`; an unchecked reply is how this sweep would produce a confident wrong
answer. (Acceptance criterion A2 in the spec is the same claim as a poison: perturb the spin
and require the instrument to notice.)

HOW A LANDING IS CLASSIFIED WITHOUT ASSUMING WHAT THE PICTURE LOOKS LIKE. Two REFERENCE
captures bracket every fixture: the identical program with its fire authored far BELOW the
read window (so the rows are in their pre-boundary state) and far ABOVE it (post-boundary).
Those give, per row, the set of SENSITIVE columns -- the ones whose colour the op actually
changes. Everything else follows from that set and needs no knowledge of the art, no
hard-coded tint RGB, and no assumption that x=0 is even observable:

  * a row is "old" iff every sensitive column matches the below-fire reference,
  * "new" iff every one matches the above-fire reference,
  * the flip is the first sensitive column that reads new,
  * CLEAN is a flip on the authored line at that line's LEFTMOST sensitive column --
    derived from the reference, not assumed to be x=0, because the art decides which
    columns can report anything at all.

The sampling granularity is therefore a property of the art and is reported beside every
verdict (`sens` counts, and the leftmost/rightmost sensitive column per row) so a reader can
see how sharp the measurement is instead of trusting it. This is the §4 "content trap" made
visible rather than assumed away: CRAM $4A is line 2, which R1 verified the trunk art uses at
these rows, and if it did not, the sensitive-column counts here would be zero and every
verdict below would be marked vacuous.

DETERMINISM COMES FROM A FIXED SCHEDULE, NOT FROM HOPE. Every capture -- references, anchors,
and all 31 sweep points -- is a fresh `emulator/reset` followed by the identical frame
schedule, so BgAnim/HUD phase is the same in all of them and cross-capture pixel comparison
is meaningful. Three prior Aeon capture protocols failed exactly this control, so A1 (three
independent SERVER processes, same N, byte-identical rows) runs before the sweep and its
result is recorded either way.

Usage:
    python3 tools/hblank_window_sweep.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/hblank_window_sweep.py --only anchors
    python3 tools/hblank_window_sweep.py --json out.json
Exit: 0 sweep completed · 1 a control or assertion failed (BLOCKED) · 3 setup problem
"""
import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, str(AEON / "tools"))

from aether import BusClient  # noqa: E402
# The encoder, verbatim -- see the module note. `parse_lst` too: symbol addresses come from
# the same listing parser the cost probe uses, so a listing-format change breaks both
# together rather than silently mis-addressing one.
from raster_cost_probe import (  # noqa: E402
    pal_restore, parse_lst, program_words, reg_set, stream_cram,
)

# oracle-next's aether server. The OLD oracle harness launcher is deliberately NOT used:
# that build predates `emulator/scanlines` and would fail on the method, not on the physics.
SERVER = "/home/volence/sonic_hacks/oracle-next/target/release/oracle-aether"
# AF_UNIX paths cap at 108 bytes and the scratchpad path is longer than that (the trap
# recorded in tools/sh_probe.py). Short, and unlinked before each launch.
SOCK = "/tmp/aeon_hblank_sweep.sock"

# The scene preamble, identical to tools/scenes/effects_raster_*.json: boot, freeze, and put
# the camera where R1 measured the trunk art's CRAM usage. Camera_Y is poked AFTER the freeze
# so nothing moves it back.
SETTLE_FRAMES = 180
POST_FREEZE_FRAMES = 3
# Two frames after the install, not one: the first is where Raster_VBlank rewinds the cursor
# onto the poked image and arms reg $0A, the second is the frame the retained framebuffer
# comes from. One frame would work if the rewind always preceded the first fire of the same
# frame; two removes the question from the measurement at the cost of 16 ms of emulated time.
DRIVE_FRAMES = 2
SPIN_WORD_OFF = 20          # Raster_Buf_A + 20 -- spec §4's table, verified by readback
ROWS_READ = 6               # boundary-3 .. boundary+2; see `capture`

SYMS = ("Raster_Buf_A", "Raster_Program", "Raster_Active_Buf", "Raster_Patch_Tab",
        "Effects_Offscreen_Entry", "Debug_Scene_Freeze", "Camera_Y")

Row = list  # list[tuple[int, int, int]], one per active column


# ---- fixtures ---------------------------------------------------------------
# Each fixture is (ops-at-a-line) builder + the authored boundary line + the two reference
# lines that bracket it. A reference is THE SAME PROGRAM fired somewhere else, so the only
# difference between a reference and a capture is where the write happens -- never what is
# written, never how many ops, never the dispatch depth.

TINT = [0x0E0E, 0x0E0E, 0x0E0E]     # $0E0E = R7 G0 B7, the magenta R1 measured with
CRAM_LINE2_E5 = 0x4A                 # palette line 2, entry 5 -- $40-$5E is line 2
CRAM_LINE2_E4 = 0x48                 # the entry R1 §7.3 used

# THE HEADER MASK IS PART OF THE FIXTURE, and the spec's value makes the fixture vacuous.
#
# Word 0 of a raster program is `pal_dirty_mask`; Raster_VBlank ORs it into `Palette_Dirty`,
# and bit N there means "re-ship palette line N from Palette_Buffer to CRAM this VBlank"
# (engine/system/buffers.emp, the bclr #0/#1/#2/#3 ladder). `raster_cost_probe.PIN_MASK` is
# $0002 -- line 1 only -- for a good reason on ITS measurement (constant DMA traffic across
# cost fixtures, where nothing is ever read out of the picture).
#
# On THIS measurement that value is fatal, and measurably so. The fixture tints palette line
# 2; with only line 1 re-shipped, nothing ever puts line 2 back, so the tint written at line
# 99 of frame K is still in CRAM at line 0 of frame K+1. Every frame after the first is
# uniformly tinted from the top, the landing position is not expressed in the picture at all,
# and the sweep reads a flat null at every N -- which is precisely the "looks like a null
# result" failure §4 warns about, arrived at through the header rather than the address. It
# was reproduced here before being fixed: with $0002, all 42 three-entry windows of palette
# lines 1-3 measured ZERO sensitive columns on all six rows (the `--only map` run recorded in
# the results doc), and A2 failed on every row.
#
# $000E = lines 1-3, which is what `palette.emp` itself ORs in (`ori.b #%1110`) when a global
# operator moves the level palette. It restores the base before every frame, so the write's
# position is what the picture shows. Held constant across references, anchors and every N.
PAL_MASK = 0x000E
MASK = PAL_MASK             # what this run uses; --mask overrides, to reproduce the above


def with_mask(words: list[int], mask: int = PAL_MASK) -> list[int]:
    """The encoder's image with word 0 (`pal_dirty_mask`) set. See PAL_MASK."""
    out = list(words)
    out[0] = mask
    return out


def fx_sweep(addr: int = CRAM_LINE2_E5) -> dict:
    """§4: ONE fire, ONE leading OP_CRAM, authored at line 100. The defective shape.

    `addr` is the CRAM byte address of the 3-colour burst. §4 fixes it at $4A and warns, in
    the same breath, that the address must be one "the art at those rows actually references"
    or the sweep reads a null that looks like a result. At the frozen spawn this ROM boots to,
    $4A is NOT such an address -- the `--only map` measurement puts it at 7 sensitive columns
    summed over six rows, with rows 98, 99 and 101 at exactly zero, i.e. the boundary row and
    both §6 controls are blind. The address is therefore a measured input to this sweep rather
    than a constant, chosen by that map and reported with it.
    """
    ops = [stream_cram(addr, TINT)]
    return {
        "name": f"sweep_{addr:02X}",
        "what": f"single leading OP_CRAM, 3 words at ${addr:02X}, authored line 100 (§4)",
        "boundary": 100,
        "prog": lambda line: program_words([(line, ops)]),
        "ref_below": 160,   # fire after the read window -> rows read pre-boundary
        "ref_above": 50,    # fire before it              -> rows read post-boundary
        "spin_off": SPIN_WORD_OFF,
    }


def fx_anchor_row119(addr: int = CRAM_LINE2_E5) -> dict:
    """§6b anchor 1: the row-119 fixture -- CRAM op SECOND, behind an OP_SET_REG.

    Note what the observable is at the spec's $4A: the OP_SET_REG turns shadow/highlight on
    ($8C89 = reg $0C, H40 + S/H), which moves most of the row, while the 1-word CRAM burst at
    $4A moves ~2 columns. The reg op also runs FIRST. So at $4A this anchor measures the REG
    write's landing; run it again at a well-sampled address to see the CRAM burst's own.
    """
    ops = [reg_set(0x8C89), stream_cram(addr, [0x000E])]
    return {
        "name": f"anchor_row119_{addr:02X}",
        "what": f"reg_set($8C89) + stream_cram(${addr:02X},[$000E]), authored line 120 (§6b)",
        "boundary": 120,
        "prog": lambda line: program_words([(line, ops)]),
        "ref_below": 180,
        "ref_above": 60,
        "spin_off": None,
    }


def fx_anchor_r1_bare() -> dict:
    """§6b anchor 2 AS WRITTEN: a lone pal_restore at 140.

    Kept because §6b spells it this way, and run first so the record shows what the literal
    fixture does. OP_PAL_RESTORE streams from `Palette_Ship_Snap`, i.e. THIS frame's base DMA
    payload (engine/effects/raster.emp, `.op_pal_restore`), so with nothing having tinted CRAM
    earlier in the frame it writes the colours that are already there. Expect zero sensitive
    columns -- a vacuous fixture, reported as such rather than as a verdict.
    """
    ops = [pal_restore(CRAM_LINE2_E4, 3)]
    return {
        "name": "anchor_r1_bare",
        "what": "lone pal_restore($48,3), authored line 140 (spec §6b as written)",
        "boundary": 140,
        "prog": lambda line: program_words([(line, ops)]),
        "ref_below": 200,
        "ref_above": 60,
        "spin_off": None,
    }


def fx_anchor_r1_band(addr: int = CRAM_LINE2_E4) -> dict:
    """§6b anchor 2 AS MEASURED: R1's band -- a tint ON above, the restore as the OFF edge.

    GATE-EVIDENCE.md §7.3 describes the capture as a "`band`-shaped program ... tint $0E0E x3
    on line 2 entries 4-6 ($48)", and its verdict ("row 139 fully tinted, rows 140+ fully
    base") is only expressible if something tinted CRAM above the restore. The ON fire is the
    minimum needed to reproduce the shape R1 actually measured; the restore op itself -- its
    dispatch depth, its spin word, its burst -- is untouched, which is what makes this an
    anchor rather than a new fixture.
    """
    on = [stream_cram(addr, TINT)]
    off = [pal_restore(addr, 3)]
    return {
        "name": f"anchor_r1_band_{addr:02X}",
        "what": f"stream_cram(${addr:02X},tint) at 100 + pal_restore(${addr:02X},3) at 140 "
                "(R1 §7.3 shape)",
        "boundary": 140,
        "prog": lambda line: program_words([(100, on), (line, off)]),
        "ref_below": 200,
        "ref_above": 130,
        "spin_off": None,
    }


# ---- the bus session --------------------------------------------------------

class Server:
    """One oracle-aether process. A fresh one per A1 repeat; shared across a sweep."""

    def __init__(self, rom: str, sock: str = SOCK):
        self.rom, self.sock, self.proc, self.client = rom, sock, None, None

    async def __aenter__(self) -> "Server":
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        self.proc = subprocess.Popen(
            [SERVER, self.rom, "--socket", self.sock, "--no-pace"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)
        else:
            raise SystemExit(f"oracle-aether never created {self.sock}")
        self.client = BusClient(self.sock, client_id="hbsweep",
                                client_name="hblank_window_sweep")
        await self.client.connect()
        if not self.client.supports("emulator/scanlines"):
            raise SystemExit(
                "the server does not advertise `emulator/scanlines` -- it predates "
                "oracle-next fdb6903; rebuild `cargo build --release -p oracle-aether`")
        return self

    async def __aexit__(self, *exc) -> None:
        try:
            if self.client:
                await self.client.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


class Blocked(Exception):
    """A condition under which no number may be recorded. Carries its own evidence."""


def _rgb(hexstr: str) -> Row:
    h = hexstr[2:] if hexstr[:2].lower() == "0x" else hexstr
    b = bytes.fromhex(h)
    return [(b[i], b[i + 1], b[i + 2]) for i in range(0, len(b), 3)]


async def capture(c: BusClient, sym: dict, words: list[int], boundary: int,
                  spin: int | None = None, spin_off: int | None = None) -> dict:
    """Install `words`, drive to a completed frame, read the four rows around `boundary`."""
    words = with_mask(words, MASK)      # see PAL_MASK -- the spec's $0002 is vacuous here
    if spin is not None:
        if spin_off is None:
            raise Blocked("spin requested for a fixture with no spin word offset")
        words[spin_off // 2] = spin
    image = "".join(f"{w:04X}" for w in words)
    buf = sym["Raster_Buf_A"]

    await c.call("emulator/reset", {})
    await c.call("emulator/run_frames", {"frames": SETTLE_FRAMES})
    # Freeze BEFORE the camera poke and before the install: a section crossing would build
    # its own schedule over the fixture and the failure would look like a landing.
    await c.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await c.call("emulator/write_memory",
                 {"addr": hex(sym["Camera_Y"]), "value": 144, "width": 2})
    await c.call("emulator/run_frames", {"frames": POST_FREEZE_FRAMES})

    # No `pause` call anywhere: this server only enters free-run on an explicit
    # `emulator/resume`, so a driver built out of `run_frames` is never running when it pokes
    # and `write_memory`'s `-32005 machineRunning` refusal is structurally unreachable. That
    # is spec §5 step 2's discipline satisfied by construction rather than by remembering it.
    await c.call("emulator/write_memory", {"addr": hex(buf), "bytes": "0x" + image})
    for s, v in (("Raster_Patch_Tab", 0), ("Effects_Offscreen_Entry", 0),
                 ("Raster_Active_Buf", buf), ("Raster_Program", buf)):
        await c.call("emulator/write_memory", {"addr": hex(sym[s]), "value": v, "width": 4})
    await c.call("emulator/run_frames", {"frames": DRIVE_FRAMES})

    # The poke has to have SURVIVED the frames it was measured over. Raster_Patch_Tab = 0 is
    # what stops Raster_BuildSchedule re-recording over it; this is the check that it worked.
    back = await c.call("emulator/read_memory", {"addr": hex(buf), "len": len(words) * 2})
    got = back["bytes"].upper().removeprefix("0X")
    if got != image:
        raise Blocked(f"program was rewritten during the run\n  poked: {image}\n  read : {got}")

    # SIX rows, not §6's four. §6 asks for boundary-1..boundary+1 plus controls either side;
    # the extra row above and below is a superset of that and is what makes an edge landing
    # one row off the authored line VISIBLE WITH ITS OWN CONTROLS rather than showing up as
    # a failed control on a four-row window. Nothing is classified from the extra rows that
    # §6 would classify differently -- see `classify`, which takes the edge row explicitly.
    start = boundary - 3
    if start < 0 or start + ROWS_READ > 224:
        raise Blocked(f"read window {start}..{start + ROWS_READ - 1} is outside the display")
    r = await c.call("emulator/scanlines", {"startLine": start, "count": ROWS_READ})
    # THE assertion. See the module note; a stateRender reply is a legitimate answer to the
    # method and a structurally invalid one to this measurement.
    if r.get("source") != "raster":
        raise Blocked("emulator/scanlines answered source=%r (caveat: %r) -- a post-hoc "
                      "render cannot see WHEN the write landed" % (r.get("source"),
                                                                   r.get("caveat")))
    if r.get("mode") != "h40":
        raise Blocked(f"mode is {r.get('mode')!r}, not h40 -- 320 active columns assumed")
    rows = {row["line"]: _rgb(row["rgb"]) for row in r["rows"]}
    if sorted(rows) != list(range(start, start + ROWS_READ)):
        raise Blocked(f"rows returned {sorted(rows)}, wanted "
                      f"{list(range(start, start + ROWS_READ))}")
    return {"rows": rows, "frame": r.get("frame"), "image": image, "start": start}


# ---- classification ---------------------------------------------------------

def sensitive(below: Row, above: Row) -> list[int]:
    """Columns whose colour the op actually changes -- the only ones that can report."""
    return [x for x in range(len(below)) if below[x] != above[x]]


def classify(cap: dict, ref_below: dict, ref_above: dict, edge: int) -> dict:
    """§6, with two substitutions, both of them measurements rather than conveniences.

    `edge` is the row on which a correctly-landed write is expected to first show, passed in
    rather than assumed to be the authored line: the anchors calibrate it, which is one of the
    two jobs §6b gives them. Passing the authored line reproduces §6 literally.

    'x = 0' is read as 'the leftmost SENSITIVE column' -- the leftmost column the art lets the
    op change at all. A write landing in blanking recolours the row from its very first pixel,
    but only columns drawn from the CRAM entries being written can say so, and which those are
    is the art's business. The two figures are reported side by side so the substitution is
    auditable per row.
    """
    edges = [edge] if isinstance(edge, int) else list(edge)
    out = {"rows": {}, "verdict": None, "flip_row": None, "flip_x": None,
           "flip_at_left": None, "notes": [], "edge": edges[0],
           "verdicts": {e: {"verdict": None, "notes": []} for e in edges}}
    sens = {}
    for line in sorted(cap["rows"]):
        b, a, g = ref_below["rows"][line], ref_above["rows"][line], cap["rows"][line]
        s = sensitive(b, a)
        sens[line] = s
        new = [x for x in s if g[x] == a[x] and g[x] != b[x]]
        old = [x for x in s if g[x] == b[x] and g[x] != a[x]]
        odd = [x for x in s if g[x] != a[x] and g[x] != b[x]]
        out["rows"][line] = {
            "sens": len(s),
            "sens_first": s[0] if s else None,
            "sens_last": s[-1] if s else None,
            "new": len(new),
            "old": len(old),
            "neither": len(odd),
            "first_new_x": new[0] if new else None,
        }
    out["sens"] = {k: v for k, v in sens.items()}

    if all(not v for v in sens.values()):
        out["verdict"] = "VACUOUS"
        for e in edges:
            out["verdicts"][e] = {"verdict": "VACUOUS", "notes": []}
        out["notes"].append(
            "no sensitive columns on any row: the two reference captures are identical, so "
            "this fixture changes nothing the art samples (spec §4's content trap)")
        return out

    for line in sorted(out["rows"]):
        r = out["rows"][line]
        if r["neither"]:
            out["notes"].append(
                f"row {line}: {r['neither']} sensitive columns match NEITHER reference")

    # THE OBSERVATION, edge-independent: the first (row, column) in raster order that reads
    # new. This is the landing point, up to the art's sampling; every verdict below is a
    # comparison of it against a candidate edge row, and the raw pair is what the results doc
    # tabulates so a later reader can re-derive any verdict without re-running the sweep.
    for line in sorted(out["rows"]):
        if out["rows"][line]["first_new_x"] is not None:
            out["flip_row"] = line
            out["flip_x"] = out["rows"][line]["first_new_x"]
            out["flip_at_left"] = (out["flip_x"] == out["rows"][line]["sens_first"])
            break
    else:
        out["flip_at_left"] = None

    # Monotonicity: a landing is one instant, so within the flip row every sensitive column
    # right of it must read new. A violation means something other than this write moved the
    # picture, and the flip x is not a landing point.
    if out["flip_row"] is not None:
        line = out["flip_row"]
        a, g = ref_above["rows"][line], cap["rows"][line]
        bad = [x for x in sens[line] if x > out["flip_x"] and g[x] != a[x]]
        if bad:
            out["notes"].append(f"row {line}: {len(bad)} non-monotone sensitive columns "
                                f"(first {bad[0]}) -- flip x is not a clean boundary")

    # §6's verdict, evaluated against the candidate edge row(s) the caller names.
    for e in edges:
        v, notes = _verdict(out, e)
        out["verdicts"][e] = {"verdict": v, "notes": notes}
    out["verdict"] = out["verdicts"][out["edge"]]["verdict"]
    out["notes"] += out["verdicts"][out["edge"]]["notes"]
    return out


def _verdict(out: dict, edge: int) -> tuple[str, list[str]]:
    """§6's table, against one candidate edge row. Controls first -- they can veto."""
    notes: list[str] = []
    rows = out["rows"]
    for ctrl, want, other in ((edge - 2, "new", "old"), (edge + 1, "old", "new")):
        if ctrl not in rows:
            notes.append(f"row {ctrl} control is OUTSIDE the read window")
            continue
        r = rows[ctrl]
        if r["sens"] == 0:
            notes.append(f"row {ctrl} control is VACUOUS (0 sensitive columns)")
        elif r[want]:
            notes.append(f"row {ctrl} is not uniformly {other}: "
                         f"{r[want]}/{r['sens']} columns {want}")
            return "FIXTURE BROKEN", notes
    fr, fxx = out["flip_row"], out["flip_x"]
    if fr is None:
        notes.append("no row in the read window ever turns new")
        return "TOO LATE", notes
    if fr < edge:
        return "TOO EARLY", notes
    if fr > edge:
        notes.append(f"first new pixel is on row {fr}, past the edge row {edge}")
        return "TOO LATE", notes
    if out["flip_at_left"]:
        return "CLEAN", notes
    notes.append(f"flip at x={fxx}, leftmost observable column on row {fr} is "
                 f"x={rows[fr]['sens_first']}")
    return "TOO LATE", notes


# ---- runners ----------------------------------------------------------------

async def refs(c: BusClient, sym: dict, fx: dict) -> tuple[dict, dict]:
    below = await capture(c, sym, fx["prog"](fx["ref_below"]), fx["boundary"])
    above = await capture(c, sym, fx["prog"](fx["ref_above"]), fx["boundary"])
    return below, above


def row_line(line: int, r: dict) -> str:
    return (f"      row {line}: sens {r['sens']:3d} [{r['sens_first']}..{r['sens_last']}]"
            f"  new {r['new']:3d}  old {r['old']:3d}  neither {r['neither']:3d}"
            f"  first_new_x {r['first_new_x']}")


async def run_anchor(c: BusClient, sym: dict, fx: dict, report: dict) -> None:
    print(f"\n== anchor {fx['name']}: {fx['what']}")
    below, above = await refs(c, sym, fx)
    cap = await capture(c, sym, fx["prog"](fx["boundary"]), fx["boundary"])
    b = fx["boundary"]
    res = classify(cap, below, above, [b, b + 1])
    print(f"   first new pixel: row {res['flip_row']} x {res['flip_x']}  "
          f"(at that row's leftmost observable column: {res['flip_at_left']})")
    for e, v in res["verdicts"].items():
        print(f"   verdict with edge row {e}: {v['verdict']}"
              + ("   " + "; ".join(v["notes"]) if v["notes"] else ""))
    for line in sorted(res["rows"]):
        print(row_line(line, res["rows"][line]))
    for n in res["notes"]:
        print(f"      note: {n}")
    report["anchors"][fx["name"]] = {
        "what": fx["what"], "boundary": b,
        "flip_row": res["flip_row"], "flip_x": res["flip_x"],
        "flip_at_left": res["flip_at_left"],
        "verdicts": {str(k): v for k, v in res["verdicts"].items()},
        "rows": {str(k): v for k, v in res["rows"].items()}, "notes": res["notes"],
    }


async def run_a2(c: BusClient, sym: dict, fx: dict, report: dict) -> None:
    """A2 liveness poison: N=0 and N=17 MUST render differently.

    The spec names row 99 specifically, on the model that the authored line is where a clean
    write shows. It is evaluated over the WHOLE read window instead -- every row, reported
    individually -- because which row a landing shows on is a thing this sweep MEASURES (both
    anchors put it one past the authored line) and A2's claim is about the instrument, not
    about that row index: an instrument that reports post-frame state renders N=0 and N=17
    identically EVERYWHERE, and one that sees the raster differs SOMEWHERE. Naming one row in
    advance can only make the poison weaker, never stronger -- it would fail on a correct
    instrument whose landing row is off by one, which is exactly what happened on first run.
    """
    print("\n== A2 liveness poison (spec §8): N=0 vs N=17 must render differently")
    a = await capture(c, sym, fx["prog"](fx["boundary"]), fx["boundary"], 0, fx["spin_off"])
    b = await capture(c, sym, fx["prog"](fx["boundary"]), fx["boundary"], 17, fx["spin_off"])
    per_row, total = {}, 0
    for line in sorted(a["rows"]):
        r0, r17 = a["rows"][line], b["rows"][line]
        diff = [x for x in range(len(r0)) if r0[x] != r17[x]]
        total += len(diff)
        per_row[line] = {"differing_columns": len(diff),
                         "first": diff[0] if diff else None,
                         "last": diff[-1] if diff else None}
        print(f"      row {line}: {len(diff):>3} differing columns"
              + (f", x {diff[0]}..{diff[-1]}" if diff else ""))
    literal_ok = total > 0
    print(f"   total differing columns across the window: {total}  -> "
          f"{'PASS' if literal_ok else 'FAIL'}   (the spec's literal N=0 vs N=17 pair)")

    # PART 2, and it is the part that decides BLOCKED. A2's real claim is that the surface is
    # not a post-hoc render -- such a surface answers IDENTICALLY at every N, because by end of
    # frame the CRAM value is the same whatever the spin was. Part 1 tests that with one
    # hand-picked pair. If that pair happens to sit inside a single quantum of whatever
    # resolution the instrument does have, part 1 fails on an instrument that is merely COARSE
    # rather than blind -- and the difference between those two IS the finding this sweep is
    # for. So: scan N and count DISTINCT pictures. Blind => exactly 1, over any range at all.
    # More than 1 is a resolution to be characterised by the sweep, not a blindness to stop on.
    seen: dict[str, list[int]] = {}
    scan = list(range(0, 60, 3))
    for n in scan:
        cap = await capture(c, sym, fx["prog"](fx["boundary"]), fx["boundary"], n,
                            fx["spin_off"])
        key = "|".join("".join("%02X%02X%02X" % p for p in cap["rows"][k])
                       for k in sorted(cap["rows"]))
        seen.setdefault(key, []).append(n)
    distinct = len(seen)
    groups = sorted(seen.values())
    print(f"   distinct pictures over N in {scan[0]}..{scan[-1]} step 3: {distinct}"
          f"   -> {'PASS' if distinct > 1 else 'FAIL (blind)'}")
    for g in groups:
        print(f"      identical at N {g}")
    report["A2"] = {"literal_pass": literal_ok, "pass": distinct > 1,
                    "total_differing_columns": total, "per_row": per_row,
                    "spec_named_row": fx["boundary"] - 1,
                    "spec_named_row_differs":
                        per_row[fx["boundary"] - 1]["differing_columns"] > 0,
                    "distinct_pictures": distinct, "distinct_groups": groups, "scan": scan,
                    "rows_N0": {str(k): "".join("%02X%02X%02X" % p for p in v)
                                for k, v in a["rows"].items()},
                    "rows_N17": {str(k): "".join("%02X%02X%02X" % p for p in v)
                                 for k, v in b["rows"].items()}}
    if distinct <= 1:
        raise Blocked(
            "A2 FAILED: every N in the scan renders identically. The instrument is blind to "
            "this defect class in exactly the way a post-hoc frame dump is. The N=0 and N=17 "
            "captures are recorded verbatim in the JSON.")
    if not literal_ok:
        print("   NOTE: the spec's literal pair does NOT differ, while the scan shows the "
              "instrument is not blind -- N=0 and N=17 sit inside ONE quantum of its "
              "resolution. Measuring that quantum is what the sweep below does.")


async def run_a1(rom: str, sym: dict, fx: dict, report: dict, n: int = 17,
                 repeats: int = 3) -> None:
    """A1 determinism: `repeats` independent server processes, same N, identical rows."""
    print(f"\n== A1 determinism (spec §8): {repeats} fresh server processes, N={n}")
    digests = []
    for i in range(repeats):
        async with Server(rom, SOCK) as s:
            cap = await capture(s.client, sym, fx["prog"](fx["boundary"]), fx["boundary"],
                                n, fx["spin_off"])
        blob = "|".join("%d:%s" % (line, "".join("%02X%02X%02X" % p for p in cap["rows"][line]))
                        for line in sorted(cap["rows"]))
        digests.append(blob)
        print(f"   boot {i + 1}: frame {cap['frame']}  rows {sorted(cap['rows'])}  "
              f"len {len(blob)}")
    ok = len(set(digests)) == 1
    print(f"   -> {'PASS (byte-identical)' if ok else 'FAIL (captures differ)'}")
    report["A1"] = {"n": n, "repeats": repeats, "pass": ok,
                    "distinct": len(set(digests))}
    if not ok:
        for i, d in enumerate(digests):
            for j in range(i + 1, len(digests)):
                if digests[i] != digests[j]:
                    report["A1"].setdefault("first_disagreement", f"boot {i+1} vs boot {j+1}")
        raise Blocked("A1 FAILED: repeated boots at the same N do not render identically; "
                      "no per-N verdict below would be attributable to N.")


async def run_map(c: BusClient, sym: dict, fx: dict, report: dict) -> None:
    """Which CRAM entries does the art at these rows actually sample? -- §4's content trap.

    NOT a diagnostic bolted on after the fact: §4 states the trap ("the CRAM address must be
    an entry the art at those rows actually references, or the sweep shows nothing and looks
    like a null result") and R1 hit it in the flesh. The only way to know an address is
    ADEQUATE rather than to hope it is, is to measure the art's usage at the rows being read,
    which is what this does: the identical 3-word burst at every 3-entry window of palette
    lines 1-3, fired above and below the read window, counting the columns that move.

    Palette line 0 is not probed: it is the character's, and the cost probe's standing rule
    ("Never line 0") applies to anything that writes CRAM under a frozen camera.
    """
    print("\n== content-trap map (spec §4): sensitive columns per CRAM window, "
          f"rows {fx['boundary'] - 3}..{fx['boundary'] + 2}")
    rows_of_interest = list(range(fx["boundary"] - 3, fx["boundary"] + 3))
    table = []
    for line in (1, 2, 3):
        for e in range(0, 14):
            addr = line * 32 + e * 2
            ops = [stream_cram(addr, TINT)]
            below = await capture(c, sym, program_words([(fx["ref_below"], ops)]),
                                  fx["boundary"])
            above = await capture(c, sym, program_words([(fx["ref_above"], ops)]),
                                  fx["boundary"])
            counts = {r: len(sensitive(below["rows"][r], above["rows"][r]))
                      for r in rows_of_interest}
            table.append({"addr": addr, "pal_line": line, "entry": e,
                          "counts": {str(k): v for k, v in counts.items()},
                          "total": sum(counts.values()),
                          "min_row": min(counts.values())})
            print(f"   ${addr:02X}  line {line} entries {e}-{e + 2}:  "
                  + " ".join(f"r{r}={counts[r]:>3}" for r in rows_of_interest)
                  + f"   total {sum(counts.values()):>4}  min {min(counts.values()):>3}")
    report["content_map"] = table
    usable = [t for t in table if t["min_row"] > 0]
    usable.sort(key=lambda t: (t["min_row"], t["total"]), reverse=True)
    print("\n   windows with EVERY row of the read window sensitive (best first):")
    for t in usable[:8]:
        print(f"      ${t['addr']:02X}  line {t['pal_line']} entries {t['entry']}-"
              f"{t['entry'] + 2}   min/row {t['min_row']:>3}   total {t['total']:>4}")
    if not usable:
        print("      NONE -- no 3-entry window of palette lines 1-3 is sampled on every row")


async def run_sweep(c: BusClient, sym: dict, fx: dict, report: dict,
                    lo: int, hi: int) -> None:
    print(f"\n== sweep: {fx['what']}, N = {lo}..{hi}")
    below, above = await refs(c, sym, fx)
    b = fx["boundary"]
    for line in sorted(below["rows"]):
        s = sensitive(below["rows"][line], above["rows"][line])
        gaps = [s[i + 1] - s[i] for i in range(len(s) - 1)]
        print(f"   sensitivity row {line}: {len(s)} columns"
              + (f", x {s[0]}..{s[-1]}, max gap {max(gaps) if gaps else 0}" if s else ""))
        report["sensitivity"][line] = {
            "count": len(s), "first": s[0] if s else None, "last": s[-1] if s else None,
            "max_gap": max(gaps) if gaps else None}
    edges = [b, b + 1]
    lines = sorted(below["rows"])
    print("\n   " + f"{'N':>3} {'flipRow':>7} {'flipX':>5} {'atLeft':>6}  "
          + "  ".join(f"{'edge ' + str(e):<12}" for e in edges)
          + "  " + " ".join(f"{'r' + str(ln):>6}" for ln in lines) + "   (new columns)")
    for n in range(lo, hi + 1):
        cap = await capture(c, sym, fx["prog"](b), b, n, fx["spin_off"])
        res = classify(cap, below, above, edges)
        r = res["rows"]
        vs = "  ".join(f"{res['verdicts'][e]['verdict']:<12}" for e in edges)
        print(f"   {n:>3} {str(res['flip_row']):>7} {str(res['flip_x']):>5} "
              f"{str(res['flip_at_left']):>6}  {vs}  "
              + " ".join(f"{r[ln]['new']:>6}" for ln in lines))
        report["sweep"].append({
            "n": n, "flip_row": res["flip_row"], "flip_x": res["flip_x"],
            "flip_at_left": res["flip_at_left"], "notes": res["notes"],
            "verdicts": {str(k): v["verdict"] for k, v in res["verdicts"].items()},
            "verdict_notes": {str(k): v["notes"] for k, v in res["verdicts"].items()},
            "rows": {str(k): v for k, v in r.items()}})


def summarize(report: dict) -> None:
    sw = report["sweep"]
    if not sw:
        return
    print("\n== result")
    report["clean"] = {}
    for edge in sorted(sw[0]["verdicts"], key=int):
        runs, cur = [], []
        for e in sw:
            if e["verdicts"][edge] == "CLEAN":
                cur.append(e["n"])
            else:
                if cur:
                    runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        if not runs:
            print(f"   edge row {edge}: NO CLEAN N in the swept range")
            report["clean"][edge] = {"runs": [], "range": None, "centre": None}
            continue
        runs.sort(key=len, reverse=True)
        best = runs[0]
        centre = (best[0] + best[-1]) // 2
        report["clean"][edge] = {"runs": [[r[0], r[-1]] for r in runs],
                                 "range": [best[0], best[-1]], "centre": centre,
                                 "width": len(best)}
        print(f"   edge row {edge}: contiguous CLEAN {[(r[0], r[-1]) for r in runs]}"
              f"   widest N in [{best[0]}, {best[-1]}] ({len(best)} values)  CENTRE N = {centre}")

    # px/cyc cross-check (§6): the flip x as a function of 10*N. Reported only if the flip x
    # ever moves -- see the note printed when it does not, which is itself the finding.
    moved = {e["flip_x"] for e in sw if e["flip_x"] is not None}
    if len(moved) > 1:
        for row in sorted({e["flip_row"] for e in sw if e["flip_row"] is not None}):
            pts = [(e["n"] * 10, e["flip_x"]) for e in sw
                   if e["flip_row"] == row and e["flip_x"] is not None]
            if len(pts) < 3:
                continue
            mx = sum(p[0] for p in pts) / len(pts)
            my = sum(p[1] for p in pts) / len(pts)
            den = sum((p[0] - mx) ** 2 for p in pts)
            if den == 0:
                continue
            slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / den
            print(f"   px/cyc from row {row}'s flips ({len(pts)} points): {slope:.3f}")
            report.setdefault("px_per_cyc", {})[str(row)] = {"points": len(pts),
                                                             "slope": slope}
    else:
        print("   px/cyc cross-check: UNOBTAINABLE -- the flip x never moves off a row's "
              "leftmost sampled column at any N.")
        print("   !! THE §6 CLEAN RANGE ABOVE IS NOT THE BLANKING WINDOW. A flip x that\n"
              "      never moves means the instrument cannot place a landing WITHIN a row,\n"
              "      so every N whose write lands anywhere before a sampling instant reads\n"
              "      identically -- CLEAN included. That range is the instrument's quantum.\n"
              "      The window is derived from the boundaries instead; see below.")
        report["px_per_cyc"] = None
        report["clean_range_is_quantum"] = True
    boundary_analysis(report)


# H40 NTSC line geometry, from the hardware constants rather than from any document's table:
# a line is 3420 master clocks; active display is 320 pixels clocked at master/8, i.e. 2560
# master; the 68000 runs at master/7. Everything below is in 68000 cycles.
LINE_CYC = 3420 / 7
ACTIVE_CYC = 320 * 8 / 7
BLANK_CYC = LINE_CYC - ACTIVE_CYC


def boundary_analysis(report: dict) -> None:
    """What the sweep can and cannot conclude, from where the PICTURE changes.

    The classifier answers §6's question. This answers the one the data actually turned out to
    pose: the picture changes only at discrete N, in tight groups, with wide flat stretches
    between -- so the instrument resolves the landing to something coarser than a pixel, and
    the whole measurement rests on what that something is. Both scales are read straight out
    of the boundaries:

      * WITHIN a group, consecutive boundaries are one colour word of the burst apart. The
        burst is three `move.w (a1)+, VDP_DATA`, and each crosses the instrument's sampling
        instant at its own N, so the spacing IS the per-word cost.
      * BETWEEN groups, the gap is the sampling period -- one scanline if the instrument
        samples once per line. Cross-checked against LINE_CYC, which nothing here fitted.

    The window then follows from the group's own two edges plus BLANK_CYC. The LAST word to
    be written crosses first (smallest N), the FIRST word last; a burst is clean exactly when
    the last word still precedes the sampling instant and the first word has not yet preceded
    the start of blanking. Only the first of those two is measured -- the start of blanking is
    not a sampling instant, so it cannot be, and the derived edge is labelled as derived.
    """
    sw = report["sweep"]
    sig = [(e["n"], tuple(sorted((k, v["new"]) for k, v in e["rows"].items()))) for e in sw]
    bounds = [sig[i][0] for i in range(1, len(sig)) if sig[i][1] != sig[i - 1][1]]
    if not bounds:
        print("\n== boundary analysis: the picture never changes across the swept range")
        report["boundaries"] = []
        return
    groups: list[list[int]] = [[bounds[0]]]
    for b in bounds[1:]:
        if b - groups[-1][-1] <= 10:      # same sampling instant, a later burst word
            groups[-1].append(b)
        else:                             # a whole sampling period later
            groups.append([b])
    print("\n== boundary analysis (where the picture changes)")
    print(f"   boundaries at N = {bounds}")
    print(f"   groups: {groups}")
    report["boundaries"] = bounds
    report["boundary_groups"] = groups

    steps = [g[i + 1] - g[i] for g in groups for i in range(len(g) - 1)]
    if steps:
        per_word = 10 * sum(steps) / len(steps)
        print(f"   within-group step: {steps}  ->  {per_word:.1f} cycles per burst word "
              f"({len(steps)} intervals)")
        report["measured_cycles_per_burst_word"] = per_word
    if len(groups) > 1:
        firsts = [g[0] for g in groups]
        per_line = 10 * (firsts[-1] - firsts[0]) / (len(firsts) - 1)
        print(f"   between-group step: first-boundary N = {firsts}  ->  {per_line:.1f} "
              f"cycles per sampling period   (one H40 NTSC scanline = {LINE_CYC:.1f}, "
              f"ratio {per_line / LINE_CYC:.4f})")
        report["measured_cycles_per_sampling_period"] = per_line
        report["line_cyc_arith"] = LINE_CYC

    g = groups[0]
    n_hi = g[0] - 0.5              # last word still lands before the sampling instant
    n_first_word = g[-1] - 0.5     # first word crosses it here
    span = 10 * (g[-1] - g[0])     # first->last write, in cycles
    n_lo = n_first_word - BLANK_CYC / 10
    lo_i, hi_i = math.ceil(n_lo), math.floor(n_hi)
    centre = round((n_lo + n_hi) / 2)
    print(f"\n   burst span (first write -> last write): {span:.0f} cycles")
    print(f"   blanking window: {BLANK_CYC:.1f} cycles  (line {LINE_CYC:.1f} - active "
          f"{ACTIVE_CYC:.1f}, from the H40 NTSC constants)")
    print(f"   upper edge  N = {n_hi}   MEASURED (the group's first boundary, +-0.5)")
    print(f"   lower edge  N = {n_lo:.2f}   DERIVED (upper-word crossing {n_first_word} "
          f"minus blanking/10) -- NOT measured: the start of blanking is not a sampling "
          f"instant of this instrument")
    print(f"   => clean N in [{n_lo:.2f}, {n_hi}]  = integers {lo_i}..{hi_i}   "
          f"CENTRE N = {centre}")
    report["window"] = {"n_hi_measured": n_hi, "n_lo_derived": n_lo,
                        "first_word_crossing": n_first_word, "burst_span_cyc": span,
                        "blank_cyc": BLANK_CYC, "integers": [lo_i, hi_i], "centre": centre}


async def amain(args) -> int:
    sym = parse_lst(args.lst)
    missing = [s for s in SYMS if s not in sym]
    if missing:
        print(f"symbols missing from {args.lst}: {', '.join(missing)}", file=sys.stderr)
        return 3

    report = {"rom": args.rom, "lst": args.lst, "server": SERVER,
              "pal_dirty_mask": MASK,
              "settle_frames": SETTLE_FRAMES, "drive_frames": DRIVE_FRAMES,
              "cram_addr": args.addr,
              "anchors": {}, "sweep": [], "sensitivity": {}}
    sweep_fx = fx_sweep(args.addr)
    want = set(args.only.split(",")) if args.only else None

    def on(name: str) -> bool:
        return want is None or name in want

    t0 = time.time()
    try:
        if on("anchors"):
            # Each anchor twice where the address matters: once at the address the spec/R1
            # names, and once at a well-sampled one. The pair is the evidence that a null at
            # the named address is the art's doing and not the landing's.
            async with Server(args.rom, SOCK) as s:
                for fx in (fx_anchor_row119(CRAM_LINE2_E5), fx_anchor_row119(args.addr),
                           fx_anchor_r1_bare(),
                           fx_anchor_r1_band(CRAM_LINE2_E4), fx_anchor_r1_band(args.addr)):
                    await run_anchor(s.client, sym, fx, report)
        if on("map"):
            async with Server(args.rom, SOCK) as s:
                await run_map(s.client, sym, sweep_fx, report)
        if on("a1"):
            await run_a1(args.rom, sym, sweep_fx, report)
        if on("a2"):
            async with Server(args.rom, SOCK) as s:
                await run_a2(s.client, sym, sweep_fx, report)
        if on("sweep"):
            async with Server(args.rom, SOCK) as s:
                await run_sweep(s.client, sym, sweep_fx, report, args.lo, args.hi)
            summarize(report)
    except Blocked as e:
        print(f"\nBLOCKED: {e}", file=sys.stderr)
        report["blocked"] = str(e)
        if args.json:
            Path(args.json).write_text(json.dumps(report, indent=1) + "\n")
        return 1
    report["wall_clock_s"] = round(time.time() - t0, 1)
    print(f"\nwall clock: {report['wall_clock_s']} s")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1) + "\n")
        print(f"raw: {args.json}")
    return 0


def main() -> int:
    global MASK, ROWS_READ
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--lo", type=int, default=0)
    ap.add_argument("--hi", type=int, default=30)
    ap.add_argument("--only", default="", help="anchors,map,a1,a2,sweep")
    ap.add_argument("--mask", default="", help="header pal_dirty_mask override, e.g. 0x0002 "
                                              "to reproduce the vacuous spec fixture")
    ap.add_argument("--json", default="", help="write the raw record here")
    # $50 is not a preference: `--only map` measures every 3-entry window of palette lines
    # 1-3 at the rows being read, and $50 (line 2 entries 8-10) is the one the art samples on
    # every row of the window. The spec's $4A is blind on three of the six.
    ap.add_argument("--addr", default="0x50", type=lambda s: int(s, 0),
                    help="CRAM byte address of the sweep burst (default $50, per --only map)")
    # Widening the read window is how a sweep long enough to cross SEVERAL line boundaries
    # keeps every crossing in view. Four crossings turn "the landing steps by a line" from an
    # observation into a fit: their spacing is a measurement of cycles per scanline.
    ap.add_argument("--rows", type=int, default=6,
                    help=f"rows read per capture, from boundary-3 (default {ROWS_READ})")
    args = ap.parse_args()
    if args.mask:
        MASK = int(args.mask, 0)
    ROWS_READ = args.rows
    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    for p in (args.rom, args.lst, SERVER):
        if not Path(p).is_file():
            print(f"not found: {p}", file=sys.stderr)
            return 3
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
