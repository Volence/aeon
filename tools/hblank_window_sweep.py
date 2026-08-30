#!/usr/bin/env python3
"""hblank_window_sweep — locate the horizontal-blanking window in cycle space.

Substrate item 1b. The spec is `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-SPEC.md`;
this file is its driver, and every number it prints is measured here rather than restated
from that document. §7 of the spec governs: a disagreement with the §3 prediction
(N in [15,19], centre 17) is the FINDING, never a cue to adjust the fixture.

THIS DRIVER HAS TWO ANALYSIS MODES AND PICKS BETWEEN THEM BY MEASUREMENT, because the
instrument changed underneath it on 2026-08-19 and the old server is still reachable.
`summarize` calls `subline_detect`, which asks the only question that separates them: does
the landing PIXEL move with the spin?

  * LINE-ATOMIC (`atomic_summarize` -> `boundary_analysis` -> `solver_fit`) -- the original
    path, and still the correct one for oracle classic and any conformant server that samples
    a row once at its line start. There `flipX` is the constant `{0}`, §6's verdicts bucket
    rather than measure, and the window has to be recovered from where the PICTURE changes.
    Measured that way: 30.0 cyc per burst word, 490.0 cyc per sampling period, late edge
    N=21.5, early edge DERIVED because nothing in the picture marks it. NOT DELETED, and not
    to be run on a sub-line server: it folds split rows into one nonsense group and prints a
    spurious NO-GO.
  * SUB-LINE (`subline_analysis`) -- oracle-next since F-SCANLINE-SUBLINE (their 87c8e99 /
    ff9e784; empyrean contract §11.15). A CRAM write landing `d` mclk into a line's 2560-mclk
    active window recolours that row FROM pixel floor(d/8) at H40, so the landing row splits
    and the landing pixel IS the measurement. `flipX` marches ~8.7 px per spin iteration. The
    first WHOLLY recoloured row is still authored+1, which is what lets the anchors' edge-row
    calibration carry across the change unaltered.

WHAT THE SUB-LINE MODE MADE MEASURABLE FOR THE FIRST TIME. The blanking window's EARLY edge --
the spin at which a burst's first write leaves active display and enters blanking. Nothing in
a line-atomic picture changes when that happens, so every earlier reading of it was derived
from the arithmetic width (3420/7 - 2560/7 = 122.9), and the guard margins are asymmetric
(early 20, late 10) for precisely that reason. Here the landing simply walks off the right
edge of the active window, and both edges come out of one fit with a standard error each.
`HBLANK-WINDOW-SWEEP-RESULTS.md` beside the spec carries both regimes, the older one intact.

MEASURE THE WINDOW AT `--words 1`. Every sensitive column samples exactly ONE of the written
entries, so on a multi-word burst `flipX` is the first column sampling the FIRST entry and its
bracket cannot be taken over the whole sensitive set. Width and period survive that (a
constant offset cancels); the absolute edges do not. The wider bursts are still worth sweeping
-- their CLEAN plateaus are a falsifiable prediction from the one-word window plus the cycle
table -- but the edges come from `--words 1`.

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

HOW MANY WORDS THE BURST CARRIES IS AN INPUT (`--words`, default 3). The sweep was written
for the shape the DSL shipped at the time — a single ceiling of 3 — but the ceiling is a
CYCLE budget, and the only honest way to move it is to author the wider burst and measure
where it lands. The driver pokes the wire image directly, so the constructors' `ensure` never
sees the fixture; that is the same latitude the 1b fixture already takes (it pokes a spin the
lowering would never solve). `--words 4` is the fixture the ceiling raise was ASKED on and
REFUSED on -- `RASTER_BURST_MAX_CRAM` is 3, and the sub-line re-measurement of 2026-08-19
refuses it again on a directly measured early edge -- and `--words 5` is available to watch
the refusal's arithmetic be right. `--words 1` is the window fixture: see the note above.

Usage:
    python3 tools/hblank_window_sweep.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/hblank_window_sweep.py --only anchors
    python3 tools/hblank_window_sweep.py --only sweep --words 4 --lo 0 --hi 200 --rows 12
    python3 tools/hblank_window_sweep.py --json out.json
Exit: 0 sweep completed · 1 a control or assertion failed (BLOCKED) · 3 setup problem
"""
import argparse
import asyncio
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path, suite_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
sys.path.insert(0, str(AEON / "tools"))

from aether import BusClient  # noqa: E402
# The encoder, verbatim -- see the module note. `parse_lst` too: symbol addresses come from
# the same listing parser the cost probe uses, so a listing-format change breaks both
# together rather than silently mis-addressing one.
from raster_cost_probe import (  # noqa: E402
    fire_spins, pal_restore, parse_lst, program_words, reg_set, spin_cyc, stream_cram,
)

# oracle-next's aether server. The OLD oracle harness launcher is deliberately NOT used:
# that build predates `emulator/scanlines` and would fail on the method, not on the physics.
SERVER = str(suite_path("oracle-next", "target", "release", "oracle-aether"))
# AF_UNIX paths cap at 108 bytes and the scratchpad path is longer than that (the trap
# recorded in tools/sh_probe.py). Short, and unlinked before each launch.
# PER-PROCESS, because this tree runs parallel lanes in parallel worktrees and a shared path
# would have two drivers unlinking each other's socket -- each then silently measuring the
# OTHER lane's ROM, which is a wrong number rather than an error.
SOCK = f"/tmp/aeon_hblank_sweep_{os.getpid()}.sock"

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

TINT_COLOUR = 0x0E0E                 # $0E0E = R7 G0 B7, the magenta R1 measured with
TINT = [TINT_COLOUR] * 3             # the 3-word default; --words rebuilds it
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


def fx_sweep(addr: int = CRAM_LINE2_E5, words: int = 3) -> dict:
    """§4: ONE fire, ONE leading OP_CRAM, authored at line 100. The defective shape.

    `addr` is the CRAM byte address of the burst. §4 fixes it at $4A and warns, in
    the same breath, that the address must be one "the art at those rows actually references"
    or the sweep reads a null that looks like a result. At the frozen spawn this ROM boots to,
    $4A is NOT such an address -- the `--only map` measurement puts it at 7 sensitive columns
    summed over six rows, with rows 98, 99 and 101 at exactly zero, i.e. the boundary row and
    both §6 controls are blind. The address is therefore a measured input to this sweep rather
    than a constant, chosen by that map and reported with it.

    `words` is the burst width, and it is an INPUT because the ceiling it feeds
    (`RASTER_BURST_MAX_CRAM` for this op class) is a per-fire cycle budget rather than a
    hardware limit -- the only way to know whether a wider burst still lands inside blanking
    is to author one and read the picture back. Nothing in the DSL is bypassed dishonestly
    here: the constructors' `ensure` refuses a burst above the ceiling and this driver never
    calls them, it pokes the wire image exactly as it already pokes a spin the lowering would
    never solve. Widening the
    burst only ADDS CRAM entries ($50, $52, $54, $56 at four words), so an address the map
    found adequate at three stays adequate -- and `run_sweep` prints the reference sensitivity
    per row before any verdict, which is that claim measured rather than assumed.
    """
    ops = [stream_cram(addr, [TINT_COLOUR] * words)]
    return {
        "name": f"sweep_{addr:02X}_w{words}",
        "what": f"single leading OP_CRAM, {words} words at ${addr:02X}, authored line 100 (§4)",
        "boundary": 100,
        "words": words,
        "ops": ops,
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
           "flip_at_left": None, "flip_x_prev": None, "notes": [], "edge": edges[0],
           "verdicts": {e: {"verdict": None, "notes": []} for e in edges},
           "verdicts_subline": {e: {"verdict": None, "notes": []} for e in edges}}
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
            out["verdicts_subline"][e] = {"verdict": "VACUOUS", "notes": []}
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
            # THE BRACKET, and it is what makes the sub-line fit unbiased rather than merely
            # precise. `flip_x` is not the landing pixel: it is the first column the ART lets
            # report, so the true landing lies in (previous sensitive column, flip_x]. Reading
            # flip_x as the landing biases every observation UP by about half the local gap --
            # ~0.8 px here, i.e. ~0.1 N, i.e. ~1 cycle, against a 4-word early margin this
            # parcel measures at 1.3. Recording the bracket lets `subline_fit` use the midpoint
            # and lets a later reader re-derive the correction instead of trusting it.
            s = sens[line]
            below_flip = [x for x in s if x < out["flip_x"]]
            out["flip_x_prev"] = below_flip[-1] if below_flip else -1
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
    # The same landing, read under the sub-line convention. Computed unconditionally and
    # stored beside the atomic verdict; which of the two the driver PRINTS is decided by
    # `subline_detect` once the sweep has enough observations to say what server it is on.
    for e in edges:
        v, notes = _verdict_subline(out, e)
        out["verdicts_subline"][e] = {"verdict": v, "notes": notes}
    return out


def _verdict_subline(out: dict, edge: int) -> tuple[str, list[str]]:
    """§6's three verdicts under the F-SCANLINE-SUBLINE row convention (empyrean §11.15).

    The convention the atomic classifier was written against is gone: a row is no longer one
    sample taken at its line start. A CRAM write landing `d` mclk into line N's 2560-mclk
    active window now recolours row N FROM pixel floor(d/8) (H40) -- the landing row SPLITS --
    and only a write that has reached the blanking leaves the following row wholly recoloured.
    The first WHOLLY recoloured row is still authored+1, which is why `edge` keeps its meaning
    and why the anchors' calibration carries forward unchanged.

    That makes the three verdicts sharper than §6 could make them, and it makes them mean
    what §6 always wanted them to mean:

      * TOO EARLY -- the burst's first word landed inside the AUTHORED line's active display.
        Under the old convention this was invisible (the row was sampled before the write, so
        it read clean); it is now the split row itself, and `flip_x` is where the dot starts.
        This is the defect class the whole substrate item exists to see.
      * CLEAN -- the WHOLE burst landed in blanking: the edge row is recoloured from its
        leftmost observable column AND every sensitive column on it reads new (no column left
        holding a base colour, which is what a trailing word landing past the active start
        would leave behind), and the authored row is untouched.
      * TOO LATE -- the first word cleared blanking but the burst did not finish inside it
        (the edge row is split, or partially new), or the landing is a whole row further on.

    A column reading NEITHER reference is counted against CLEAN too: on a multi-word burst
    each column samples exactly one of the written entries, so a partially-landed burst shows
    up as a mixture, and calling that clean would be the same error the old classifier made
    one line higher up.
    """
    notes: list[str] = []
    rows, fr, fx = out["rows"], out["flip_row"], out["flip_x"]
    if edge not in rows:
        return "FIXTURE BROKEN", [f"edge row {edge} is outside the read window"]
    if rows[edge]["sens"] == 0:
        return "VACUOUS", [f"edge row {edge} has no sensitive columns"]
    if fr is None:
        return "TOO LATE", ["no row in the read window ever turns new"]
    if fr < edge:
        notes.append(f"row {fr} is SPLIT at x={fx} -- the write landed in that row's active "
                     f"display, {rows[fr]['old']} of {rows[fr]['sens']} columns still base")
        return "TOO EARLY", notes
    if fr > edge:
        notes.append(f"first new pixel is on row {fr}, a whole row past the edge row {edge}")
        return "TOO LATE", notes
    e = rows[edge]
    if not out["flip_at_left"]:
        notes.append(f"edge row {edge} is SPLIT at x={fx} (leftmost observable column is "
                     f"x={e['sens_first']}) -- the burst's first word landed in active display")
        return "TOO LATE", notes
    if e["old"] or e["neither"]:
        notes.append(f"edge row {edge} starts new at its leftmost column but {e['old']} "
                     f"columns still read base and {e['neither']} read neither reference -- a "
                     f"trailing burst word landed past the active start")
        return "TOO LATE", notes
    return "CLEAN", notes


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
    # BOTH readings, side by side and labelled. An anchor's job is to calibrate the edge row,
    # and the two conventions agree about that (authored+1) while disagreeing about what a
    # landing inside a row looks like -- so printing both is how the anchors carry forward
    # across the instrument change instead of being re-run on faith.
    for e, v in res["verdicts"].items():
        print(f"   verdict with edge row {e}: line-atomic {v['verdict']:<14} "
              f"sub-line {res['verdicts_subline'][e]['verdict']}"
              + ("   " + "; ".join(res["verdicts_subline"][e]["notes"])
                 if res["verdicts_subline"][e]["notes"] else ""))
    for line in sorted(res["rows"]):
        print(row_line(line, res["rows"][line]))
    for n in res["notes"]:
        print(f"      note: {n}")
    report["anchors"][fx["name"]] = {
        "what": fx["what"], "boundary": b,
        "flip_row": res["flip_row"], "flip_x": res["flip_x"],
        "flip_at_left": res["flip_at_left"], "flip_x_prev": res["flip_x_prev"],
        "verdicts": {str(k): v for k, v in res["verdicts"].items()},
        "verdicts_subline": {str(k): v for k, v in res["verdicts_subline"].items()},
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
    # The row a correctly-landed burst first shows on WHOLLY. Under both conventions it is
    # authored+1: the anchors measured it that way on the atomic server, and §11.15's
    # amendment kept it ("the first WHOLLY recoloured row is still N+1") while making the
    # authored row itself splittable. That continuity is why the anchors carry forward.
    report["edge_row"] = b + 1
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
    # THE STREAMED TABLE IS OBSERVATIONS ONLY, and that is a deliberate change from the
    # atomic-era driver, which printed its verdicts inline. A verdict depends on which row
    # convention the server implements, and that is something this sweep MEASURES (see
    # `subline_detect`) rather than knows in advance -- on a sub-line server the atomic
    # verdicts read FIXTURE BROKEN at nearly every N, which is the classifier being asked a
    # question about a picture it cannot parse, not a broken fixture. So the landing is
    # reported as it is observed, and the verdict table is printed once, below, in whichever
    # convention the data says is in force. Both verdicts are recorded in the JSON either way.
    print("\n   " + f"{'N':>3} {'flipRow':>7} {'flipX':>5} {'atLeft':>6}  "
          + " ".join(f"{'r' + str(ln):>6}" for ln in lines) + "   (new columns)")
    for n in range(lo, hi + 1):
        cap = await capture(c, sym, fx["prog"](b), b, n, fx["spin_off"])
        res = classify(cap, below, above, edges)
        r = res["rows"]
        print(f"   {n:>3} {str(res['flip_row']):>7} {str(res['flip_x']):>5} "
              f"{str(res['flip_at_left']):>6}  "
              + " ".join(f"{r[ln]['new']:>6}" for ln in lines))
        report["sweep"].append({
            "n": n, "flip_row": res["flip_row"], "flip_x": res["flip_x"],
            "flip_at_left": res["flip_at_left"], "flip_x_prev": res["flip_x_prev"],
            "notes": res["notes"],
            "verdicts": {str(k): v["verdict"] for k, v in res["verdicts"].items()},
            "verdicts_subline": {str(k): v["verdict"]
                                 for k, v in res["verdicts_subline"].items()},
            "verdict_notes": {str(k): v["notes"] for k, v in res["verdicts"].items()},
            "rows": {str(k): v for k, v in r.items()}})


def emp_int(rel: str, name: str) -> int:
    """A `const NAME = <int>` out of an .emp source, so no number here is hand-copied.

    Same three lines as `tools/effects_gates.py`'s helper and for the same reason: the
    go/no-go below compares a MEASURED band against the guard margins the compiler actually
    enforces, and a margin transcribed into this file would let the two drift apart silently
    -- which is the failure mode "derive gate expectations" exists to prevent.
    """
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)",
                  txt, re.M)
    if not m:
        raise Blocked(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def solver_fit(report: dict, fx: dict) -> None:
    """THE GO/NO-GO: does the lowering's own answer for this fixture sit inside the band the
    sweep just measured, with the guard's margins to spare?

    The sweep measures where a burst LANDS as a function of the spin it is given. The DSL
    solver, which has never seen a boundary, computes one spin for this fixture from the cost
    model alone. Those are two independent answers to the same question, and a ceiling raise
    is only defensible if the second lands inside the first:

      * the LATE edge is `n_hi`, MEASURED -- the N at which the burst's last word stops
        beating the line-start sampling instant. The guard demands the landing clear it by
        `RASTER_HBLANK_MARGIN_LATE_CYC`.
      * the EARLY edge is `n_lo`, DERIVED -- the first word crossing the start of blanking,
        which no instrument here can watch (the RESULTS doc's standing caveat). The guard
        demands `RASTER_HBLANK_MARGIN_EARLY_CYC`, a full extra iteration over the late side
        for exactly that reason.

    Both edges carry the instrument's own +-0.5 N localization, so the verdict is printed with
    the worst-case edges beside the nominal ones: a fit that survives BOTH is a fit, a fit that
    only survives the nominal one is reported as marginal and is not a go.

    THE FOLDED WINDOW IS USED WHERE IT EXISTS, and which one was used is printed. See
    `boundary_analysis`: both edges of the single-group headline descend from ONE integer
    boundary, so its whole band can sit up to half an N off, and half an N is 5 cycles against
    margins of 10 and 20. A run wide enough to hold several sampling periods measures the same
    crossing several times over, and the fold is what turns a +-5-cycle headline into an
    estimate this verdict can actually rest on. A narrow run still gets a verdict -- it is just
    labelled as resting on the single-group edges, which is a reason to widen the run rather
    than to trust the number.
    """
    w = report.get("window_folded") or report.get("window")
    if not w:
        return
    folded = "window_folded" in report
    spin = fire_spins(fx["ops"])[0]
    early = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_MARGIN_EARLY_CYC")
    late = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_MARGIN_LATE_CYC")
    n_lo, n_hi = w["n_lo_derived"], w["n_hi_measured"]
    need_lo, need_hi = n_lo + early / 10, n_hi - late / 10
    # HOW MUCH TO DISTRUST THE EDGES. A single boundary is localized to +-0.5 N, and that is
    # the right figure for the single-group window. The folded window has an INTERCEPT whose
    # uncertainty the fit measured for itself (the residual spread over sqrt(groups)), and
    # using the single-boundary 0.5 there would be double-counting the very noise the fold
    # removed -- it would call a landing marginal that is nothing of the kind. Take the
    # measured one where the fit produced it.
    unc = w.get("intercept_se_n", 0.5) if folded else 0.5
    pess_lo, pess_hi = need_lo + unc, need_hi - unc
    ok = need_lo <= spin <= need_hi
    ok_pess = pess_lo <= spin <= pess_hi
    print(f"\n== solver fit ({fx['words']}-word burst)")
    print(f"   the DSL solver's spin for this fixture, from the cost model alone: N = {spin}")
    print(f"   edges from the {'FOLDED' if folded else 'single-group'} window"
          + ("" if folded else "   (only one sampling period in view -- widen with "
                              "--hi 200 --rows 12)"))
    print(f"   measured clean band                : N in [{n_lo:.2f}, {n_hi:.2f}]")
    print(f"   guard margins (read from raster_dsl.emp): early {early} cyc, late {late} cyc")
    print(f"   band that satisfies both margins   : N in [{need_lo:.2f}, {need_hi:.2f}]"
          f"   -> solved N={spin} {'FITS' if ok else 'DOES NOT FIT'}")
    print(f"   same, less the edge uncertainty {unc:.2f} N: N in [{pess_lo:.2f}, {pess_hi:.2f}]"
          f"   -> solved N={spin} {'FITS' if ok_pess else 'DOES NOT FIT'}")
    print(f"   slack at the landing: {10 * (spin - n_lo) - early:.1f} cyc early side, "
          f"{10 * (n_hi - spin) - late:.1f} cyc late side")
    verdict = "GO" if ok and ok_pess else ("MARGINAL" if ok else "NO-GO")
    print(f"   => {verdict}")
    report["solver_fit"] = {
        "words": fx["words"], "solved_spin": spin, "edges_from_folded_window": folded,
        "margin_early_cyc": early, "margin_late_cyc": late,
        "n_lo_derived": n_lo, "n_hi_measured": n_hi,
        "need": [need_lo, need_hi], "need_pessimistic": [pess_lo, pess_hi],
        "fits": ok, "fits_pessimistic": ok_pess, "edge_uncertainty_n": unc,
        "slack_early_cyc": 10 * (spin - n_lo) - early,
        "slack_late_cyc": 10 * (n_hi - spin) - late,
        "verdict": verdict}


def summarize(report: dict, fx: dict) -> None:
    """Decide which row convention the server implements, then interpret in that one.

    The two paths below are not two opinions about the same data; they are two different
    instruments, and the sweep can tell them apart from the data itself. See `subline_detect`.
    The atomic path is kept whole and is NOT dead code: oracle classic (the GUI build) and any
    line-atomic conformant server still land there, and the results this document's early
    sections rest on were taken through it.
    """
    sw = report["sweep"]
    if not sw:
        return
    det = subline_detect(report)
    print(f"\n== instrument mode: {'SUB-LINE' if det['subline'] else 'LINE-ATOMIC'}")
    print(f"   {det['why']}")
    if det["subline"]:
        subline_analysis(report, fx)
    else:
        atomic_summarize(report, fx)


def subline_detect(report: dict) -> dict:
    """SUB-LINE iff the landing pixel moves with N. Measured, never configured.

    A line-atomic server renders each row once, from the CRAM state at that row's line start,
    so a write landing anywhere inside a row is invisible until the next one: the first column
    to read new is always the row's leftmost observable one, and `flipX` is the constant `{0}`
    at every N (that is precisely what the 2026-08-19 acceptance sweep measured, 201 captures,
    and what F-SCANLINE-SUBLINE was registered to fix). A sub-line server splits the landing
    row at the landing pixel, so `flipX` marches.

    The test is therefore the one bit of the picture the two conventions cannot both produce,
    and it needs no version string, no capability flag and no agreement with the server about
    what it is: if the landing pixel is a function of the spin, the instrument resolves it.
    """
    xs = [e["flip_x"] for e in report["sweep"] if e["flip_x"] is not None]
    distinct = sorted(set(xs))
    sub = len(distinct) > 1
    why = (f"flipX takes {len(distinct)} distinct values over {len(xs)} captures "
           f"({distinct[0]}..{distinct[-1]}) -- the landing pixel is a function of the spin, "
           "so the row splits where the write lands"
           if sub else
           f"flipX is the constant {set(distinct)} over {len(xs)} captures -- a row is one "
           "sample at its line start and a landing inside it is not expressible")
    report["instrument_mode"] = "subline" if sub else "atomic"
    report["instrument_detect"] = {"subline": sub, "distinct_flip_x": len(distinct),
                                   "flip_x_min": distinct[0] if distinct else None,
                                   "flip_x_max": distinct[-1] if distinct else None,
                                   "why": why}
    return {"subline": sub, "why": why}


# ---- sub-line analysis ------------------------------------------------------
# H40 geometry as the amendment states it (empyrean contract §11.15): a CRAM write landing d
# master clocks into a line's 2560-mclk active window shows from pixel floor(d / 8) of that
# row; at or past d = 2560 it first appears in the next row. The 68000 runs at master/7, so a
# pixel is 8/7 of a CPU cycle and a spin iteration (10 cycles) walks the landing 8.75 pixels.
PX_MCLK_H40 = 8
CPU_MCLK = 7
PX_PER_SPIN_ARITH = 10 * CPU_MCLK / PX_MCLK_H40
ACTIVE_PX = 320
# The threshold the CRAM parcel refused the DEEP class on (2.9 cycles, "smaller than the
# +-5-cycle resolution of the instrument that would have to confirm it" --
# raster_dsl.emp's stream_pal_region ensure, and the RESULTS doc's closing section). It is a
# DECISION RULE rather than a model constant, so it lives here with its citation rather than
# being read out of an .emp that does not hold it.
DECISION_MIN_SLACK_CYC = 2.9
DECISION_MIN_SE = 2.0


def _lstsq(A: list[list[float]], Y: list[float]) -> tuple[list, list, list, float]:
    """Ordinary least squares by normal equations, returning the parameter COVARIANCE too.

    The covariance is the point. The estimator this replaces reported a spread and halved it;
    a fit that is going to decide a ceiling raise on a 1.3-cycle margin has to say how much
    its own intercept is worth, and the residual variance times (A'A)^-1 is that statement.
    """
    m = len(A[0])
    n = len(A)
    M = [[sum(A[i][a] * A[i][b] for i in range(n)) for b in range(m)] for a in range(m)]
    B = [sum(A[i][a] * Y[i] for i in range(n)) for a in range(m)]
    inv = [[float(a == b) for b in range(m)] for a in range(m)]
    for c in range(m):
        p = max(range(c, m), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        inv[c], inv[p] = inv[p], inv[c]
        if abs(M[c][c]) < 1e-12:
            raise Blocked("the sub-line fit is singular -- the sweep does not span enough "
                          "distinct landings to estimate slope, phase and period")
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        inv[c] = [v / pv for v in inv[c]]
        for r in range(m):
            if r != c:
                f = M[r][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(m)]
                inv[r] = [inv[r][j] - f * inv[c][j] for j in range(m)]
    th = [sum(inv[a][b] * B[b] for b in range(m)) for a in range(m)]
    resid = [Y[i] - sum(A[i][j] * th[j] for j in range(m)) for i in range(n)]
    s2 = sum(r * r for r in resid) / (n - m) if n > m else float("inf")
    cov = [[inv[a][b] * s2 for b in range(m)] for a in range(m)]
    return th, cov, resid, s2


def _se(J: list[float], cov: list[list[float]]) -> float:
    m = len(J)
    return math.sqrt(max(0.0, sum(J[a] * cov[a][b] * J[b]
                                  for a in range(m) for b in range(m))))


def subline_segments(report: dict) -> list[dict]:
    """The marching runs, one per row the landing walked across, with each landing BRACKETED.

    Two kinds of capture come back from a sub-line sweep and only one of them locates a
    landing. A capture whose flip sits at the row's leftmost observable column is CENSORED: it
    says the write landed at or before pixel 0 of that row, which is every spin in the whole
    blanking window plus the first pixel of active, and reading it as "x = 0" would drag the
    fit toward the plateau and flatten the slope. Those are excluded from the fit and kept as
    the plateau evidence instead. The rest are bracketed: the landing lies in
    (previous observable column, flipX], and the midpoint is the estimate.
    """
    segs: dict[int, list[dict]] = {}
    for e in report["sweep"]:
        if e["flip_row"] is None or e["flip_at_left"] or e["flip_x"] is None:
            continue
        lo = e.get("flip_x_prev")
        lo = -1 if lo is None else lo
        segs.setdefault(e["flip_row"], []).append({
            "n": e["n"], "x_obs": e["flip_x"], "x_lo": lo + 1, "x_hi": e["flip_x"],
            "x_mid": (lo + 1 + e["flip_x"]) / 2.0})
    return [{"row": r, "pts": segs[r]} for r in sorted(segs)]


def subline_plateaus(report: dict) -> list[dict]:
    """The censored captures, grouped: one run per blanking window the sweep crossed.

    A plateau is the set of spins for which the WHOLE burst landed in blanking, so the edge
    row came back recoloured from its first observable column with nothing left holding a base
    colour. It is a direct observable needing no fit and no bracket, which makes it the
    control on the fit rather than a second version of it -- and it is coarse for two reasons
    that are both named rather than absorbed: it is integer-quantized to +-0.5 N, and its
    lower edge is biased EARLY by however many pixels of the previous row the art leaves
    unobservable at its right end (a landing past that row's last sensitive column cannot be
    seen there and reads as though it had already reached blanking).
    """
    runs: list[dict] = []
    cur: list[int] = []
    row = None
    for e in report["sweep"]:
        clean = (e["flip_row"] is not None and e["flip_at_left"]
                 and e["rows"][str(e["flip_row"])]["old"] == 0
                 and e["rows"][str(e["flip_row"])]["neither"] == 0)
        if clean and (row is None or e["flip_row"] == row) and (not cur or e["n"] == cur[-1] + 1):
            cur.append(e["n"])
            row = e["flip_row"]
        else:
            if cur:
                runs.append({"row": row, "lo": cur[0], "hi": cur[-1], "len": len(cur)})
            cur = [e["n"]] if clean else []
            row = e["flip_row"] if clean else None
    if cur:
        runs.append({"row": row, "lo": cur[0], "hi": cur[-1], "len": len(cur)})
    return runs


def subline_fit(report: dict, words: int) -> dict | None:
    """The window, from the landing's own march. Both edges MEASURED, for the first time.

    Until this instrument existed the early edge -- the spin at which a burst's first write
    crosses OUT of active display and INTO blanking -- could not be watched, because nothing
    in a line-atomic picture changes when it happens. It was derived from the arithmetic
    blanking width instead, and the asymmetric guard margins (early 20, late 10) exist because
    of exactly that asymmetry of evidence. A sub-line server makes it an observation: the
    landing pixel marches to the right edge of the active window and off it.

    The model is one straight line per row with a SHARED slope and a SHARED period, fitted
    together:

        x(N)  =  b * (N - N0 - k*P)          k = which row the landing is walking across

    from which three quantities the sweep never fitted for fall out as functions of the
    parameters, each with a standard error propagated from the fit's covariance:

        active span   = 320 / b            (cross-check: 2560/7 = 365.7 cyc)
        period        = P                  (cross-check: 3420/7 = 488.6 cyc)
        BLANKING      = P - 320 / b        (cross-check: 860/7 = 122.9 cyc -- and if the
                                            measurement disagrees with that arithmetic, the
                                            disagreement is the finding, not a tuning knob)

    Fitting slope and period TOGETHER rather than taking either from the H40 constants is what
    makes those three cross-checks real: none of the arithmetic values is an input anywhere in
    this function, so their agreement with the fit is evidence and not a tautology.

    A CONSTANT bias in the observations -- and the art's sampling supplies one, since the
    landing is only visible at a column the art draws from the written entry -- moves the
    intercept and leaves b and P alone, so the width and the period are insensitive to it and
    the absolute edges are not. That is why the observations are bracket-corrected before they
    reach here: it is the only one of the three numbers that needs it.
    """
    segs = subline_segments(report)
    segs = [s for s in segs if len(s["pts"]) >= 3]
    if len(segs) < 2:
        print("   sub-line fit: not enough marching rows in the swept range (need 2+ with 3+ "
              "points each) -- widen with --lo/--hi and --rows")
        return None
    A: list[list[float]] = []
    Y: list[float] = []
    for k, s in enumerate(segs):
        for p in s["pts"]:
            A.append([float(p["n"]), -1.0, -float(k)])
            Y.append(p["x_mid"])
    (u, v, w), cov, resid, s2 = _lstsq(A, Y)
    b, N0, P = u, v / u, w / u
    active_n = ACTIVE_PX / b
    width_n = (w - ACTIVE_PX) / u
    se_b = math.sqrt(cov[0][0])
    se_P = _se([-w / u ** 2, 0.0, 1.0 / u], cov)
    se_width = _se([-(w - ACTIVE_PX) / u ** 2, 0.0, 1.0 / u], cov)
    print(f"\n== the window, from the landing's march ({len(A)} bracketed landings across "
          f"{len(segs)} rows)")
    print(f"   rows the landing walked: " + ", ".join(
        f"{s['row']} ({len(s['pts'])} pts, x {s['pts'][0]['x_obs']}..{s['pts'][-1]['x_obs']})"
        for s in segs))
    print(f"   residual rms {math.sqrt(s2):.2f} px, max |r| {max(abs(r) for r in resid):.1f} px"
          f"   (the art's own column spacing is the floor here)")
    print(f"   slope   b = {b:.4f} +- {se_b:.4f} px per spin iteration "
          f"= {b / 10:.4f} px/cyc      [H40 arithmetic {PX_PER_SPIN_ARITH / 10:.4f}]")
    print(f"   period  P = {P:.4f} +- {se_P:.4f} N = {10 * P:.2f} +- {10 * se_P:.2f} cyc"
          f"        [3420/7 = {LINE_CYC:.2f} cyc]")
    print(f"   active    = 320/b = {active_n:.4f} N = {10 * active_n:.2f} cyc"
          f"                 [2560/7 = {ACTIVE_CYC:.2f} cyc]")
    out = {"points": len(A), "rows": [s["row"] for s in segs],
           "px_per_spin": b, "px_per_spin_se": se_b, "px_per_cyc": b / 10,
           "px_per_cyc_arith": PX_PER_SPIN_ARITH / 10,
           "period_n": P, "period_n_se": se_P, "period_cyc": 10 * P,
           "period_cyc_arith": LINE_CYC,
           "active_n": active_n, "active_cyc": 10 * active_n, "active_cyc_arith": ACTIVE_CYC,
           "width_n": width_n, "width_cyc": 10 * width_n, "width_cyc_se": 10 * se_width,
           "width_cyc_arith": BLANK_CYC,
           "resid_rms_px": math.sqrt(s2), "resid_max_px": max(abs(r) for r in resid),
           "bracket_confounded": words > 1}
    # THE COMPARISON THE BOOKING ASKS FOR, and it is reported as a comparison rather than
    # reconciled: 122.9 is arithmetic (3420/7 - 2560/7) and has never been measured.
    dev = 10 * width_n - BLANK_CYC
    sigmas = abs(dev) / (10 * se_width) if se_width > 0 else float("inf")
    print(f"\n   BLANKING WIDTH = P - 320/b = {width_n:.4f} N = "
          f"{10 * width_n:.2f} +- {10 * se_width:.2f} cyc   MEASURED, both edges")
    print(f"      against the arithmetic {BLANK_CYC:.2f} cyc: {dev:+.2f} cyc = {sigmas:.2f} "
          f"standard errors  -> {'AGREES' if sigmas < 2 else 'DISAGREES -- this is a FINDING'}")
    out["width_dev_cyc"] = dev
    out["width_dev_sigmas"] = sigmas
    out["width_agrees_with_arithmetic"] = sigmas < 2

    # The two edges, in the spin coordinate of THIS fixture. The close edge is the blanking
    # that ends at the edge row's active start; the open edge is that same window's start.
    edge_row = report["edge_row"]
    rows_used = [s["row"] for s in segs]
    if edge_row not in rows_used:
        print(f"   (edge row {edge_row} is not among the marching rows -- no edge in spin "
              "coordinates; the width above still stands)")
        report["subline_window"] = out
        return out
    k_e = rows_used.index(edge_row)
    n_close = (v + k_e * w) / u
    n_open = n_close - width_n
    se_close = _se([-(v + k_e * w) / u ** 2, 1.0 / u, float(k_e) / u], cov)
    se_open = _se([-(v + (k_e - 1) * w + ACTIVE_PX) / u ** 2, 1.0 / u,
                   float(k_e - 1) / u], cov)
    print(f"\n   the window in this fixture's spin coordinate (edge row {edge_row}):")
    print(f"      EARLY edge  N = {n_open:.3f} +- {se_open:.3f}  "
          f"({10 * se_open:.2f} cyc)   MEASURED -- the first write leaves row "
          f"{edge_row - 1}'s active display")
    print(f"      LATE  edge  N = {n_close:.3f} +- {se_close:.3f}  "
          f"({10 * se_close:.2f} cyc)   MEASURED -- the write reaches row {edge_row}'s "
          "active display")
    out.update({"edge_row": edge_row, "n_open": n_open, "n_open_se": se_open,
                "n_close": n_close, "n_close_se": se_close})
    if words > 1:
        print(f"\n   !! CAVEAT: this run's burst is {words} words wide. Every sensitive column "
              "samples\n      exactly ONE of the written entries, so `flipX` is the first "
              "column sampling the\n      FIRST entry -- the bracket above is taken over ALL "
              "sensitive columns and is\n      therefore too tight. The width and period are "
              "insensitive to that (a constant\n      offset cancels), the ABSOLUTE edges are "
              "not. Take the edges from a --words 1 run.")
    report["subline_window"] = out
    return out


def subline_verdicts(report: dict) -> None:
    """§6's three verdicts, per N, in the convention the instrument actually implements.

    This is the table §6 was written to produce and could never produce here: on a line-atomic
    server TOO EARLY is inexpressible (the landing row is sampled before the write, so it
    reads clean) and the "CLEAN range" is the sampling quantum. Every verdict below is a
    direct reading of where the write landed.
    """
    sw = report["sweep"]
    edge = report["edge_row"]
    print(f"\n== §6 verdicts under the sub-line convention (edge row {edge} = authored+1)")
    runs, cur, last = [], [], None
    for e in sw:
        v = e["verdicts_subline"][str(edge)]
        if v == "CLEAN" and (not cur or e["n"] == cur[-1] + 1):
            cur.append(e["n"])
        else:
            if cur:
                runs.append(cur)
            cur = [e["n"]] if v == "CLEAN" else []
        last = v
    if cur:
        runs.append(cur)
    tally: dict[str, int] = {}
    for e in sw:
        v = e["verdicts_subline"][str(edge)]
        tally[v] = tally.get(v, 0) + 1
    print("   " + "  ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    if runs:
        best = max(runs, key=len)
        centre = (best[0] + best[-1]) / 2
        print(f"   contiguous CLEAN runs: {[(r[0], r[-1]) for r in runs]}")
        print(f"   widest: N in [{best[0]}, {best[-1]}] ({len(best)} values)   "
              f"CENTRE N = {centre:.1f}")
        report["clean_subline"] = {"runs": [[r[0], r[-1]] for r in runs],
                                   "range": [best[0], best[-1]], "width": len(best),
                                   "centre": centre, "tally": tally}
    else:
        print("   NO CLEAN N in the swept range")
        report["clean_subline"] = {"runs": [], "range": None, "tally": tally}
    _ = last


def subline_rederive_anchor(report: dict, win: dict, fx: dict) -> None:
    """`RASTER_HBLANK_END_CYC`, from a DIRECTLY measured edge instead of a derived one.

    The constant locates the blanking window's close -- the instant a write can no longer
    reach the row it was authored for -- in the cost model's own cycle space, measured from
    the record's op-walk origin. Its whole provenance has been indirect: 351, then 371 (a
    single-group boundary plus a mis-folded centre), then 366 (pooled least squares over
    twelve groups, still on an instrument that could only see the LATE edge and had to derive
    the early one). This is the first measurement that watches the write cross both edges.

    The conversion is arithmetic on the model's own decomposition, and every term is read out
    of `raster_dsl.emp` rather than transcribed, so a term that moves in the engine moves here
    too instead of leaving this number quietly stale:

        write instant(N)  =  op fetch + dispatch + pre-burst + spin_cyc(N)

    with `spin_cyc` taken from `raster_cost_probe`, the transcription the wire pin keeps equal
    to the engine's.
    """
    pro = (emp_int("engine/effects/raster_dsl.emp", "RASTER_OP_FETCH_CYC")
           + emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_ZERO_MISS_CYC")
           + emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_RUNG_CYC")
           * emp_int("engine/effects/raster_dsl.emp", "RASTER_DEPTH_CRAM")
           + emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_HIT_CYC")
           + emp_int("engine/effects/raster_dsl.emp", "RASTER_PRE_CRAM_CYC"))
    base = pro + spin_cyc(0)
    shipped = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_END_CYC")
    width_x10 = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_WIDTH_X10")
    early = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_MARGIN_EARLY_CYC")
    late = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_MARGIN_LATE_CYC")
    meas = base + 10 * win["n_close"]
    se = 10 * win["n_close_se"]
    open_meas = base + 10 * win["n_open"]
    open_model = shipped - width_x10 / 10
    print(f"\n== RASTER_HBLANK_END_CYC, re-derived from the measured LATE edge")
    print(f"   fixture prologue (op fetch + dispatch + pre-burst, read from raster_dsl.emp): "
          f"{pro} cyc;  spin_cyc(0) = {spin_cyc(0)}")
    print(f"   END = {base} + 10 x {win['n_close']:.3f} = {meas:.2f} +- {se:.2f} cyc"
          f"      [shipped {shipped}]")
    print(f"   window OPEN = {base} + 10 x {win['n_open']:.3f} = {open_meas:.2f} +- "
          f"{10 * win['n_open_se']:.2f} cyc   [model {open_model:.1f} = "
          f"{shipped} - {width_x10 / 10:.1f}]")
    d_close, d_open = meas - shipped, open_meas - open_model
    print(f"   disagreement: close {d_close:+.2f} cyc ({abs(d_close) / se:.2f} s.e.), "
          f"open {d_open:+.2f} cyc")
    # THE STOP CONDITION, stated as a comparison rather than as a tuning opportunity. Every
    # shipped spin is solved against the shipped anchor; if the anchor is wrong by more than a
    # guard margin, the fires it placed are mis-centred against the better instrument and that
    # is a finding for the controller, not something this driver may quietly correct.
    worst = min(early, late)
    breach = abs(d_close) > worst
    print(f"   guard margins are early {early} / late {late} cyc; the anchor is off by "
          f"{abs(d_close):.2f} -> {'OUTSIDE' if breach else 'INSIDE'} the tighter margin "
          f"({worst})")
    if breach:
        print("   !! STOP AND REPORT: shipped spins are solved against an anchor this "
              "measurement puts outside a guard margin.")
    report["hblank_end_rederived"] = {
        "prologue_cyc": pro, "spin_cyc_0": spin_cyc(0),
        "measured": meas, "measured_se": se, "shipped": shipped, "delta": d_close,
        "delta_se": abs(d_close) / se if se else None,
        "open_measured": open_meas, "open_measured_se": 10 * win["n_open_se"],
        "open_model": open_model, "open_delta": d_open,
        "margin_early_cyc": early, "margin_late_cyc": late,
        "outside_margin": breach}
    _ = fx


def subline_placement(report: dict, win: dict, fx: dict) -> None:
    """The burst-width question, against a window whose EARLY edge is measured for once.

    The parked 4-word raise failed on a derived early edge: the arithmetic admitted it (78
    cycles of burst plus 30 of margins against 122.9) and the pooled atomic-era estimator put
    the solved landing 0.9 cycles inside the early margin, against its own 2.0-cycle standard
    error. Both halves of that verdict were indirect -- the edge was derived from the
    arithmetic width, and the estimator's error was the quantization of a LATE-edge crossing.
    This re-asks it with the early edge watched directly.

    THE DECISION RULE IS THE ONE FIXED BEFORE THE NUMBER WAS KNOWN, and it is not restated
    here to be softened: the binding margin must clear BOTH two standard errors AND the
    2.9-cycle threshold the DEEP class was refused on. Nothing below changes a constant; the
    verdict is a recommendation for the controller and is booked as one.
    """
    early = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_MARGIN_EARLY_CYC")
    late = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_MARGIN_LATE_CYC")
    word = emp_int("engine/effects/raster_dsl.emp", "RASTER_STREAM_WORD_CRAM_CYC")
    ceil_cram = emp_int("engine/effects/raster.emp", "RASTER_BURST_MAX_CRAM")
    n_open, n_close = win["n_open"], win["n_close"]
    se_open, se_close = 10 * win["n_open_se"], 10 * win["n_close_se"]
    print(f"\n== burst placement against the MEASURED window "
          f"(N in [{n_open:.3f}, {n_close:.3f}])")
    print(f"   cram word {word} cyc, margins early {early} / late {late}, shipped "
          f"RASTER_BURST_MAX_CRAM = {ceil_cram}")
    print(f"   decision rule (fixed before the numbers): the BINDING margin must clear both "
          f"2 s.e. AND {DECISION_MIN_SLACK_CYC} cyc")
    print(f"\n   {'W':>2} {'spin':>4} {'early slack':>12} {'late slack':>11} "
          f"{'binding':>9} {'2 s.e.':>7}  verdict")
    rows = []
    for w in range(1, 6):
        spin = fire_spins([stream_cram(report["cram_addr"], [TINT_COLOUR] * w)])[0]
        e_slack = 10 * (spin - n_open) - early
        l_slack = 10 * (n_close - spin) - word * (w - 1) - late
        binding, se = ((e_slack, se_open) if e_slack <= l_slack else (l_slack, se_close))
        ok = binding >= 2 * se and binding >= DECISION_MIN_SLACK_CYC
        v = "GO" if ok else "NO-GO"
        print(f"   {w:>2} {spin:>4} {e_slack:>+11.2f} {l_slack:>+10.2f} "
              f"{binding:>+8.2f} {2 * se:>7.2f}  {v}"
              + ("   <- shipped ceiling" if w == ceil_cram else "")
              + ("   <- the parked question" if w == ceil_cram + 1 else ""))
        rows.append({"words": w, "solved_spin": spin, "early_slack_cyc": e_slack,
                     "late_slack_cyc": l_slack, "binding_cyc": binding,
                     "binding_edge": "early" if e_slack <= l_slack else "late",
                     "two_se_cyc": 2 * se, "clears_2se": binding >= 2 * se,
                     "clears_threshold": binding >= DECISION_MIN_SLACK_CYC, "verdict": v})
    raise_w = ceil_cram + 1
    r = next(x for x in rows if x["words"] == raise_w)
    print(f"\n   RECOMMENDATION on RASTER_BURST_MAX_CRAM {ceil_cram} -> {raise_w}: "
          f"{'RAISE' if r['verdict'] == 'GO' else 'HOLD AT ' + str(ceil_cram)}")
    print(f"      binding margin {r['binding_cyc']:+.2f} cyc on the {r['binding_edge']} side; "
          f"needs >= {r['two_se_cyc']:.2f} (2 s.e.) and >= {DECISION_MIN_SLACK_CYC}; "
          f"clears 2 s.e.: {r['clears_2se']}, clears threshold: {r['clears_threshold']}")
    print("      NO CONSTANT IS CHANGED BY THIS RUN -- this is the number, booked for the "
          "controller.")
    report["subline_placement"] = {"rows": rows, "shipped_ceiling": ceil_cram,
                                   "recommendation": r["verdict"],
                                   "word_cyc": word, "margin_early_cyc": early,
                                   "margin_late_cyc": late}
    _ = fx


def subline_plateau_control(report: dict, win: dict, words: int) -> None:
    """The plateau as a CONTROL on the fit -- and a check that the control can still see.

    A plateau is a direct observable: the run of spins for which the edge row came back wholly
    recoloured, i.e. the whole burst landed in blanking. Its two ends are predictions the fit
    makes and has no say over:

        start  =  the first word crossing OUT of active   ->  ceil(n_open)
        end    =  the LAST word crossing INTO active      ->  floor(n_close - 2.6*(words-1))

    Both are compared here, and the second one is the one that can go quietly vacuous. `flipX`
    is measured at the FIRST burst word's entry, which the content map picked for being the
    best-sampled address on these rows; the LAST word's entry gets no such guarantee, and on
    this art the fourth and fifth entries add only ~2 observable columns each to the edge row.
    A trailing word landing a few pixels into active then changes nothing any column can
    report, the plateau does not shrink, and a reader comparing plateaus across widths would
    conclude the burst span had stopped growing. It has not; the instrument has stopped
    watching. §4's content trap, one entry further along than §4 looks.

    So the disagreement is reported as a defect OF THE CONTROL, never folded into the window:
    nothing downstream of here consumes a plateau. The window's own edges come from the first
    word's march, and the burst span comes from the cycle table, which three independent runs
    have already confirmed to within a cycle and a half.
    """
    pl = subline_plateaus(report)
    report["subline_plateaus"] = pl
    if not pl:
        print("\n== blanking plateaus: NONE in the swept range")
        return
    word_cyc = emp_int("engine/effects/raster_dsl.emp", "RASTER_STREAM_WORD_CRAM_CYC")
    span_n = word_cyc * (words - 1) / 10.0
    print("\n== blanking plateaus (the CONTROL: whole-burst-in-blanking runs, no fit)")
    for p in pl:
        print(f"   row {p['row']}: N {p['lo']}..{p['hi']}  ({p['len']} values)")
    lens = [p["len"] for p in pl]
    mean = sum(lens) / len(lens)
    rec = {"lens": lens, "mean_n": mean, "burst_span_cyc": 10 * span_n}
    if win and "n_open" in win:
        want_lo = math.ceil(win["n_open"])
        want_hi = math.floor(win["n_close"] - span_n)
        # FOLD BEFORE AVERAGING. Each plateau sits one sampling period further along than the
        # last, so the raw mean of four absolute N is a number about the middle of the sweep
        # and not about a window at all. Subtracting the FITTED period puts all four on the
        # first window's coordinate, which is the same fold the crossings get and the only
        # form in which the comparison against the fit means anything.
        per = win["period_n"]
        got_lo = sum(p["lo"] - k * per for k, p in enumerate(pl)) / len(pl)
        got_hi = sum(p["hi"] - k * per for k, p in enumerate(pl)) / len(pl)
        print(f"   predicted from the fit: start ceil({win['n_open']:.2f}) = {want_lo}, "
              f"end floor({win['n_close']:.2f} - {span_n:.2f}) = {want_hi}")
        print(f"   observed, folded over {len(pl)} windows by the fitted period "
              f"{per:.2f} N: start {got_lo:.2f}, end {got_hi:.2f}")
        # The start is expected to run EARLY by however much of the previous row the art
        # leaves unobservable at its right end: a landing past that row's last sensitive
        # column cannot be seen there and reads as though blanking had already begun.
        prev = report["sensitivity"].get(str(report["edge_row"] - 1))
        blind_px = (319 - prev["last"]) if prev and prev["last"] is not None else 0
        blind_n = blind_px / win["px_per_spin"]
        print(f"      start bias: row {report['edge_row'] - 1} is unobservable over its last "
              f"{blind_px} px = {blind_n:.2f} N, so the plateau must begin that much early")
        end_err = got_hi - want_hi
        ok = end_err <= 1.0
        print(f"      end agreement: {end_err:+.2f} N  -> "
              + ("within the +-0.5 N quantization" if ok else
                 f"NOT EXPLAINED BY QUANTIZATION -- the trailing word of a {words}-word "
                 "burst is\n         effectively UNOBSERVABLE at this address, so this "
                 "width's plateau end is VACUOUS\n         as a control (the window and the "
                 "verdicts above do not rest on it)"))
        rec.update({"predicted_lo": want_lo, "predicted_hi": want_hi,
                    "observed_lo": got_lo, "observed_hi": got_hi,
                    "start_blind_px": blind_px, "start_blind_n": blind_n,
                    "end_error_n": end_err, "end_control_valid": ok})
    report["subline_plateau_summary"] = rec


def subline_analysis(report: dict, fx: dict) -> None:
    """Everything the sub-line instrument can say, in the order the evidence supports it."""
    subline_verdicts(report)
    win = subline_fit(report, fx["words"])
    subline_plateau_control(report, win or {}, fx["words"])
    if win and "n_close" in win:
        subline_rederive_anchor(report, win, fx)
        subline_placement(report, win, fx)


def atomic_summarize(report: dict, fx: dict) -> None:
    """§6's answer under the LINE-ATOMIC row convention -- the driver's original path.

    KEPT, and kept whole, because it is still the correct reading for a line-atomic server:
    oracle classic and any conformant server that samples a row once at its line start land
    here, and every result in `HBLANK-WINDOW-SWEEP-RESULTS.md` above the sub-line section was
    taken through this code. On such a server the flip x cannot move, the "CLEAN range" it
    prints is the instrument's quantum rather than the window, and the window has to be
    recovered from where the picture changes (`boundary_analysis`) -- all of which this path
    says out loud, as it always did.

    Do NOT run this on a sub-line server. It folds a split row and its neighbours into one
    signature, reads the resulting per-pixel changes as ~170 "boundaries", derives a nonsense
    span and prints a spurious NO-GO. `summarize` is what keeps the two apart, and it decides
    from the data rather than from a flag.
    """
    sw = report["sweep"]
    print("\n== result (line-atomic reading)")
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
    solver_fit(report, fx)


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

    # ---- the same window, with the quantization averaged out ------------------
    # THE HEADLINE ABOVE RESTS ON ONE INTEGER. Both its edges descend from `n_first_word`,
    # which is group 0's last boundary less a half -- and a boundary is the CEILING of a
    # crossing, so that half-step correction is right on average and wrong by up to +-0.5 N
    # on any single reading. A whole band shifted by up to 5 cycles is fine for a headline
    # ("the centre is 18") and is NOT fine for a go/no-go on a 5.9-cycle margin, which is
    # what a ceiling raise comes down to.
    #
    # When the sweep is wide enough to hold several sampling periods, the same crossing is
    # observed once per group, each with an INDEPENDENT rounding. Folding them onto one
    # estimate divides the quantization noise by sqrt(groups). That is the arithmetic the
    # RESULTS doc does by hand when it averages twelve boundary deltas to -0.833.
    #
    # THE PERIOD COMES FROM THE CROSSINGS' OWN SPACING, by least squares, and NOT from
    # `measured_cycles_per_sampling_period` -- which is the same quantity measured on a
    # DIFFERENT statistic (the group FIRST boundaries, i.e. the last word). The two can
    # disagree: post-SR the 3-word run read 486.7 there against 490.0 in the 4- and 5-word
    # runs, and subtracting a period that is 0.33 N wrong accumulates 1 N of error by the
    # fourth group -- which is exactly the scatter that made that run's fold disagree with
    # its neighbours. Fitting a line through (group index, crossing) estimates the intercept
    # and the period TOGETHER from one set of observations, and the residuals then say how
    # much to trust the intercept instead of leaving that to be assumed.
    if len(groups) > 1:
        obs = [g[-1] - 0.5 for g in groups]
        xs = list(range(len(obs)))
        n = len(obs)
        mx, my = sum(xs) / n, sum(obs) / n
        den = sum((x - mx) ** 2 for x in xs)
        period = sum((x - mx) * (y - my) for x, y in zip(xs, obs)) / den
        fw = my - period * mx
        resid = [y - (fw + period * x) for x, y in zip(xs, obs)]
        folded = [y - period * x for x, y in zip(xs, obs)]
        # the burst span, likewise averaged over every group that saw the whole burst
        widths = [g[-1] - g[0] for g in groups if len(g) == max(len(x) for x in groups)]
        span_n = sum(widths) / len(widths)
        hi = fw - span_n
        lo = fw - BLANK_CYC / 10
        # The residual spread is the instrument's own answer to "how much is this intercept
        # worth?", and it is PRINTED rather than assumed, because every margin verdict below
        # is a comparison against it. Half the spread over sqrt(n) is the usable figure.
        spread = max(resid) - min(resid)
        se = spread / 2 / len(obs) ** 0.5
        print(f"\n   folded over {len(groups)} sampling periods, least-squares:")
        print("      first-word crossing per group: "
              + ", ".join(f"{v:.2f}" for v in folded) + f"   -> intercept {fw:.2f} N")
        print(f"      fitted period {period:.2f} N = {10 * period:.1f} cyc   "
              f"(H40 NTSC arithmetic {LINE_CYC / 10:.2f} N)")
        print(f"      residuals {[round(v, 2) for v in resid]}  spread {spread:.2f} N "
              f"= {10 * spread:.1f} cyc  -> s.e. on the intercept ~{se:.2f} N "
              f"= {10 * se:.1f} cyc")
        print(f"      burst span {span_n:.2f} N = {10 * span_n:.1f} cyc over "
              f"{len(widths)} full groups")
        print(f"      => clean N in [{lo:.2f}, {hi:.2f}]   width {hi - lo:.2f} N")
        report["window_folded"] = {
            "groups": len(groups), "period_n": period, "per_group_crossing": folded,
            "residuals": resid, "residual_spread_n": spread, "intercept_se_n": se,
            "first_word_crossing": fw, "burst_span_n": span_n,
            "burst_span_cyc": 10 * span_n, "n_lo_derived": lo, "n_hi_measured": hi}


def replay(args) -> int:
    """Re-run the ANALYSIS over a saved sweep, with no emulator anywhere.

    The captures are the expensive, slow, physical half of this tool; the interpretation is
    the half that gets revised, and revising it by re-measuring is how a change to the
    arithmetic gets silently confounded with a change in the machine. `--replay` separates
    them: the observations are frozen in the JSON the run already wrote, and every number in
    this file's analysis can be re-derived from them by anyone, on any machine, with no server
    and no ROM. It is also what makes the analysis unit-testable -- see
    tools/test_hblank_subline.py, which feeds it landings it constructed and checks the
    window that comes back.
    """
    report = json.loads(Path(args.replay).read_text())
    if not report.get("sweep"):
        print(f"{args.replay} holds no sweep to replay", file=sys.stderr)
        return 3
    if "flip_x_prev" not in report["sweep"][0]:
        print(f"{args.replay} predates the bracket record (flip_x_prev) -- the sub-line fit "
              "needs it; re-run the sweep", file=sys.stderr)
        return 3
    fx = fx_sweep(report.get("cram_addr", 0x50), report.get("burst_words", 1))
    report.setdefault("edge_row", fx["boundary"] + 1)
    print(f"== replay of {args.replay}")
    print(f"   rom {report.get('rom')}   burst {report.get('burst_words')} words at "
          f"${report.get('cram_addr', 0):02X}   {len(report['sweep'])} captures")
    try:
        summarize(report, fx)
    except Blocked as e:
        print(f"\nBLOCKED: {e}", file=sys.stderr)
        return 1
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1) + "\n")
        print(f"\nraw: {args.json}")
    return 0


async def amain(args) -> int:
    sym = parse_lst(args.lst)
    missing = [s for s in SYMS if s not in sym]
    if missing:
        print(f"symbols missing from {args.lst}: {', '.join(missing)}", file=sys.stderr)
        return 3

    report = {"rom": args.rom, "lst": args.lst, "server": SERVER,
              "pal_dirty_mask": MASK,
              "settle_frames": SETTLE_FRAMES, "drive_frames": DRIVE_FRAMES,
              "cram_addr": args.addr, "burst_words": args.words,
              "anchors": {}, "sweep": [], "sensitivity": {}}
    sweep_fx = fx_sweep(args.addr, args.words)
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
            summarize(report, sweep_fx)
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
    # Analysis without an emulator: see `replay`. Reproduces every number in the sub-line
    # sections of HBLANK-WINDOW-SWEEP-RESULTS.md from that run's own saved observations.
    ap.add_argument("--replay", default="", help="re-run the analysis over a saved --json "
                                                 "record; no server, no ROM, no captures")
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
    # The swept burst's width. The DEFAULT STAYS 3 so every earlier section of the RESULTS
    # doc reproduces with no flag, even though the cram ceiling is now 4; 5 is the width the
    # arithmetic refuses and the instrument agrees with. See fx_sweep's note on why poking a
    # width the DSL would refuse is the point rather than a cheat.
    ap.add_argument("--words", type=int, default=3,
                    help="CRAM words in the swept burst (default 3, which reproduces the "
                         "earlier runs; 4 is the ceiling-raise fixture)")
    args = ap.parse_args()
    if args.words < 1:
        print("--words must be at least 1", file=sys.stderr)
        return 3
    if args.mask:
        MASK = int(args.mask, 0)
    ROWS_READ = args.rows
    if args.replay:
        if not Path(args.replay).is_file():
            print(f"not found: {args.replay}", file=sys.stderr)
            return 3
        return replay(args)
    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    for p in (args.rom, args.lst, SERVER):
        if not Path(p).is_file():
            print(f"not found: {p}", file=sys.stderr)
            return 3
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
