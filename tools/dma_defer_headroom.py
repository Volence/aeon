#!/usr/bin/env python3
"""dma_defer_headroom -- the frame's Important-queue headroom, and what wants it.

WHAT THIS MEASURES, AND WHY IT IS NOT THE STRADDLE QUESTION
===========================================================

`tools/dplc_straddle.py` asks whether the Important queue has enough SLOTS.
This asks whether the frame has enough BYTES, which is a different wall with a
different failure mode, and until 2026-09-05 nothing computed it.

The two walls behave differently on being hit:

  SLOTS   -- `QueueDMA_Important` returns carry SET. `perform_dplc` sees the
             carry, takes `bcs .done`, and leaves `prev_frame` STALE so the
             next frame retries. Counted by DMA_Overflow_Count /
             Dbg_DMA_Enq_Capped. LOUD.

  BYTES   -- `Drain_Budgeted_Queue` (engine/system/dma_queue.emp) reaches
             `.out_of_budget`, COMPACTS the survivors to the queue base and
             leaves them for next frame's fresh budget. The enqueue already
             returned carry CLEAR, so `perform_dplc` has ALREADY committed
             `prev_frame`. No counter moves. SILENT.

The silent one is the interesting one, because of what happens on the OTHER
queue in the same VBlank. Order in `VInt_Level` (engine/system/vblank.emp):

    seed DMA_Budget_Remaining = DMA_Budget_Default      :136
    Enqueue_Dirty_Buffers   -- palette + SAT + HScroll -> CRITICAL   :161
    charge Plane_Buffer_Ptr against the budget                       :169
    charge the whole Critical queue against the budget               :190
    Process_DMA_Critical    -- UNBUDGETED, always fully drains       :200
    Process_DMA_Important   -- BUDGETED, may defer                   :264
    Process_DMA_Deferrable  -- BUDGETED, may defer                   :276

The sprite attribute table ships on Critical. The art its mappings index ships
on Important. Nothing interlocks them. So on a frame where the residual budget
runs out mid-Important-drain, the VDP is handed the NEW frame's mappings over
the OLD frame's tiles -- and because the drain stops at the FIRST entry that
does not fit rather than skipping it, a player whose DPLC was cut in half shows
some pieces from the new frame and some from the old. That is a jumble, it
lasts exactly one frame, and every existing drop instrument reads zero through
it.

Queue ORDER decides who loses. One `GameLoop` iteration
(engine/system/game_loop.emp:29) runs `VSync_Wait` -- where `PageIn_Process`
enqueues a 2048-byte page landing on Important -- BEFORE the state dispatch,
where `perform_dplc` enqueues the player's art on Important. The queue is FIFO
and `Drain_Budgeted_Queue` walks from the base, so the page landing is ahead of
the player and spends the budget first. The player's art is what gets deferred.

WHAT THIS TOOL PRINTS
=====================

  residual  = DMA_BUDGET_* - (plane drain charge + Critical charge)
  demand    = page landing + the resident cast's peak per-frame DPLC bytes
  deficit   = demand - residual        (positive means the drain WILL defer)

Every input is derived from source, never typed in -- and then read a SECOND
time out of the ASSEMBLED tree, by different machinery, and refused if the two
disagree. That second route is LS-15b-resid (2026-09-08) and the reason for it
is in the block below.

  quantity                     route 1 (DECLARED)          route 2 (ASSEMBLED)
  ---------------------------  --------------------------  --------------------
  DMA_BUDGET_NTSC / _PAL,      engine/system/constants.emp  the `EQU <name> = $x`
  PLANE_BUFFER_SIZE,           text, via `_const`'s regex   rows sigil emits into
  MAX_VDP_SPRITES,             + `eval` -- this tool's own  the listing, i.e. what
  ART_STAGING_BUFFER_SIZE,     re-implementation of the     SIGIL'S evaluator made
  TILE_SIZE                    .emp constant evaluator      of the same file
  the four static Critical     engine/system/buffers.emp    the `move.w #imm, d3`
  entry lengths                text, out of `move.w         immediates sigil
                               #dma_length(N), d3` in       ENCODED inside
                               BuildStaticDMA               BuildStaticDMA, x2
  per-frame DPLC byte totals   the shipped blobs, via       `DPLC_PEAK_TILES_*`,
                               tools/dplc_straddle.py's     engine.objects.dplc
                               `parse_dplc` (Python,        `dplc_peak_tiles`
                               struct.unpack over the       (.emp) evaluated by
                               embed FILE) x TILE_SIZE      SIGIL, x TILE_SIZE

WHY THE SECOND ROUTE EXISTS -- THE FLAW IT CLOSES
=================================================

The pin in tools/dma_defer_headroom_baseline.json is an EXTERNALISED committed
expectation, which is why this tool never had `dplc_straddle`'s LS-15b flaw (a
proof RELATIVE to a number the harness also computed). But it had a milder one
in the same family, and the LS-15b row named it:

    the pin is written by the harness ITSELF. `--write-baseline` serialises
    `measure()`'s own output. So `--gate` catches DRIFT and can never say the
    pinned numbers were RIGHT -- a re-cut LAUNDERS any error already present.

A wrong-but-self-consistent reader passed. If `_const` resolved a constant chain
wrongly, or the `dma_length` argument was not the byte count this tool assumes,
or `parse_dplc` mis-modelled the blob, the number went into the pin and stayed
there, and every later build agreed with it.

The fix is the same shape LS-15b used: a SECOND and DIFFERENT statement of every
pinned quantity, and disagreement is `Unmeasurable` NAMING BOTH SIDES -- never a
silent preference for one. Route 2 is the ASSEMBLED tree, so it is not this
tool's opinion of the source at all: it is what sigil evaluated, and (for the
Critical lengths) what sigil ENCODED into bytes the 68000 will execute.

MEASURED 2026-09-08, all fourteen pinned quantities: route 2 AGREES with route 1
and with the pin. That is the statement the pre-fix tool could not make.

WHAT THIS STILL CANNOT SAY, stated here rather than left to be inferred:

  * Both routes read the SAME FILES. A wrong VALUE authored in constants.emp is
    invisible to both -- they would agree on it. What is now impossible is the
    narrower and likelier failure: one reader drifting from the other while each
    stays consistent with itself, which is the LS-15b shape exactly.
  * The DPLC pair reads the same blob and implements the same format spec
    (engine/objects/dplc.emp's header). A wrong SPEC defeats both.
  * The ROM decode is a linear 2-byte scan for the `move.w #imm, d3` opcode
    inside one proc's extent; an immediate word that happened to equal $363C
    would be misread as an opcode. Here the scan finds exactly the six the
    source declares, in the order the source declares them, and both facts are
    asserted -- but the scan is not a disassembler and does not claim to be.
  * NOTHING HERE EXECUTES THE ENGINE. Every route is a static reading of the
    build. The `regions` arithmetic is an ENVELOPE (see `report`'s tail), and no
    route above turns it into a frame anybody observed.

A deficit today is NOT a build failure -- the engine ships with one and the
frames it needs to bite are rare. `--gate` pins the arithmetic instead: it
fails when any derived input MOVES without the baseline being re-cut, so the
next person to change a budget, a buffer size or the cast's art volume is told
what it did to this margin.

USAGE
    python3 tools/dma_defer_headroom.py                     # report
    python3 tools/dma_defer_headroom.py --gate              # pin check
    python3 tools/dma_defer_headroom.py --write-baseline    # re-cut the pin
    python3 tools/dma_defer_headroom.py --selftest          # red-first proof

`--rom` defaults to `--lst` with its suffix swapped, so the ROM read alongside a
listing is always that listing's own build. Both are REQUIRED: route 2 lives in
them, and a missing one is exit 3, never a quiet fall-back to route 1 alone.

EXIT CODES
    0  measured (and, under --gate, matched the baseline)
    1  --gate mismatch: an input moved
    3  UNMEASURABLE -- an input could not be read at all. Never silent, never 0.
"""

import argparse
import io
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import dplc_straddle as DS  # noqa: E402  -- parser + subject table, single-sourced

BASELINE = HERE / "dma_defer_headroom_baseline.json"

CONSTANTS_EMP = REPO / "engine" / "system" / "constants.emp"
BUFFERS_EMP = REPO / "engine" / "system" / "buffers.emp"
VBLANK_EMP = REPO / "engine" / "system" / "vblank.emp"
DMA_QUEUE_EMP = REPO / "engine" / "system" / "dma_queue.emp"


class Unmeasurable(Exception):
    """An input could not be read. Exit 3, never a zero and never a number."""


# --------------------------------------------------------------- source reads

#: `pub const NAME = <expr>`, where expr is integers, other constant names, and
#: `* + - ( )`. Several of the sizes this tool needs are DERIVED in
#: constants.emp (`ART_STAGING_BUFFER_SIZE = ART_POOL_PAGE_BYTES`, itself
#: `ART_POOL_PAGE_TILES * TILE_SIZE`), and resolving the chain is the whole
#: point -- retyping the leaf value here would put a second, rottable copy of
#: the number in the tree, which is the failure this tool exists to catch.
_CONST_RE = re.compile(
    r"^\s*pub\s+const\s+([A-Za-z_]\w*)\s*=\s*([^/\n]+?)\s*(?://.*)?$", re.M)
_TOKEN_OK = re.compile(r"^[\w\s$*+\-()]+$")


def _const(name, _seen=None):
    text = CONSTANTS_EMP.read_text()
    hits = [m for m in _CONST_RE.finditer(text) if m.group(1) == name]
    if len(hits) != 1:
        raise Unmeasurable(
            f"`pub const {name}` appears {len(hits)} times in "
            f"{CONSTANTS_EMP.relative_to(REPO)}, expected exactly 1")
    expr = hits[0].group(2).strip()
    _seen = (_seen or set()) | {name}
    if not _TOKEN_OK.match(expr):
        raise Unmeasurable(f"{name} = {expr!r} uses syntax this reader does not model")
    # $hex -> 0xhex, then substitute any bare names recursively.
    py = re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", expr)
    for ident in sorted(set(re.findall(r"[A-Za-z_]\w*", py)), key=len, reverse=True):
        if ident in _seen:
            raise Unmeasurable(f"constant cycle resolving {name} at {ident}")
        py = re.sub(rf"\b{ident}\b", str(_const(ident, _seen)), py)
    try:
        v = eval(py, {"__builtins__": {}}, {})       # noqa: S307 -- token-gated above
    except Exception as exc:                          # noqa: BLE001
        raise Unmeasurable(f"{name} = {expr!r} did not evaluate: {exc}") from exc
    if not isinstance(v, int):
        raise Unmeasurable(f"{name} evaluated to {v!r}, not an integer")
    return v


def static_critical_lengths():
    """The Critical queue's per-frame byte cost, out of BuildStaticDMA.

    Read from the `move.w #dma_length(N), d3` lines rather than retyped, so a
    length change lands here instead of rotting a comment. The SAT entry's 640
    is the boot default -- Render_Sprites re-patches it every frame to
    Sprites_Rendered*8 -- so 640 IS the worst case (MAX_VDP_SPRITES*8) and is
    checked against that below.
    """
    text = BUFFERS_EMP.read_text()
    lens = [int(m) for m in re.findall(r"move\.w\s+#dma_length\((\d+)\),\s*d3", text)]
    if len(lens) != 6:
        raise Unmeasurable(
            f"expected 6 `move.w #dma_length(N), d3` lines in "
            f"{BUFFERS_EMP.relative_to(REPO)}, found {len(lens)}: {lens}. "
            "BuildStaticDMA changed shape -- re-derive this reader "
            "before trusting any number below it."
        )
    pal = lens[0:4]
    if len(set(pal)) != 1:
        raise Unmeasurable(f"the four palette-line entries differ: {pal}")
    sat, hscroll = lens[4], lens[5]
    sprites_max = _const("MAX_VDP_SPRITES")
    if sat != sprites_max * 8:
        raise Unmeasurable(
            f"the SAT static entry is {sat} B but MAX_VDP_SPRITES*8 is "
            f"{sprites_max * 8} -- one of the two moved; the worst-case SAT "
            "charge below is derived from the pair agreeing."
        )
    return {"palette_line": pal[0], "palette_lines": 4, "sat": sat, "hscroll": hscroll}


# ------------------------------------------------ route 2: the ASSEMBLED tree
#
# Everything above this line reads `.emp` TEXT with this tool's own readers.
# Everything below reads the BUILD -- the listing sigil emitted and the ROM it
# encoded -- and `_cross_check` refuses to report when the two disagree. See the
# module header for why (LS-15b-resid: the pin is self-written, so drift is all
# it could ever catch).
#
# THE INDEPENDENCE CLAIM, PRECISELY. These are not the same reader run twice.
# Route 1 is Python regex + `eval` over source; route 2 is sigil's own `.emp`
# evaluator, its own layout, and (for the Critical lengths) its instruction
# encoder. For the DPLC peaks route 2 is `dplc_peak_tiles`, a parser written in
# `.emp` in engine/objects/dplc.emp, whose Python counterpart `parse_dplc` says
# in its own docstring that it was "written fresh from the format spec ... not
# shared with dplc_layout.py, so a bug in one does not silently agree with the
# other" -- the same deliberate non-sharing, one layer out.

#: `EQU <name> = $<hex>` -- the listing's Equate Table (sigil-link
#: `resolved_equates`). ONLY a link-level equate (`pub equ`) lands here; a
#: `pub const` in a data module is comptime-only and emits no row at all, which
#: is why games/sonic4/data/*/`DPLC_PEAK_TILES_*` are `pub equ`.
_EQU_RE = re.compile(r"^EQU (\w+) = \$([0-9A-Fa-f]+)\s*$", re.M)


def equ_table(lst_path):
    """name -> value, out of the listing's Equate Table."""
    p = Path(lst_path)
    if not p.exists():
        raise Unmeasurable(f"listing {lst_path} does not exist -- build the shape first")
    out = {m.group(1): int(m.group(2), 16) for m in _EQU_RE.finditer(p.read_text())}
    if not out:
        raise Unmeasurable(
            f"{lst_path} carries NO `EQU name = $x` rows. sigil omits the Equate "
            "Table entirely when a link has no equates, so this is either the "
            "wrong file or a listing-format change -- either way route 2 is gone "
            "and this tool will not report on route 1 alone.")
    return out


#: `move.w #<imm>, d3` -- the instruction BuildStaticDMA uses for every entry
#: length. 68000 encoding: MOVE.W with source = immediate (mode 7 reg 4) and
#: destination = D3 (mode 0 reg 3) is 0011 011 000 111 100 = $363C, followed by
#: the 16-bit immediate.
_MOVE_W_IMM_D3 = b"\x36\x3c"

#: The routine whose six entry builds ARE the Critical queue's static content.
#: Named here rather than in a comment because the extent is taken from it.
_STATIC_DMA_PROC = "BuildStaticDMA"


def rom_static_critical_lengths(lst_path, rom_path):
    """The static Critical entry lengths as sigil ENCODED them, in BYTES.

    Route 2 for `static_critical_lengths`. `dma_length(N)` is
    `(N >> 1) & $FFFF` (engine/vdp.emp) and the VDP's length register counts
    WORDS, so the encoded immediate is halved and this doubles it back. That
    round trip is the point: route 1 reads the ARGUMENT `N` and calls it bytes,
    which is only true if `dma_length` halves. Route 2 never assumes that -- it
    reads what the halving PRODUCED and doubles, so a `dma_length` that stopped
    halving lands here as a disagreement instead of passing unnoticed.

    NOT A DISASSEMBLER. The scan steps two bytes at a time looking for one
    opcode inside one proc's extent, so an immediate word equal to $363C would
    be misread. The caller cross-checks the count and the values against the
    source's six, which is what makes that safe here and is stated in the module
    header as a limit rather than hidden.
    """
    rom = Path(rom_path)
    if not rom.exists():
        raise Unmeasurable(f"ROM {rom_path} does not exist -- build the shape first")
    data = rom.read_bytes()
    # Local (`$mod$proc$label`) rows included on purpose: the tightest extent is
    # the next row of ANY kind, which keeps the scan inside this proc.
    rows = {}
    for line in Path(lst_path).read_text().splitlines():
        m = re.match(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w.$]*):", line)
        if m:
            rows.setdefault(m.group(2), int(m.group(1), 16))
    if _STATIC_DMA_PROC not in rows:
        raise Unmeasurable(
            f"{_STATIC_DMA_PROC} is not in {lst_path} -- the routine that builds "
            "the static Critical entries was renamed or dropped; route 2 for the "
            "entry lengths cannot be read.")
    base = rows[_STATIC_DMA_PROC]
    above = [v for v in rows.values() if v > base]
    if not above:
        raise Unmeasurable(f"{_STATIC_DMA_PROC} at 0x{base:X} is the last symbol in "
                           "the listing -- its extent cannot be bounded")
    end = min(above)
    if end > len(data):
        raise Unmeasurable(
            f"{_STATIC_DMA_PROC}'s extent [0x{base:X}, 0x{end:X}) runs past the "
            f"{len(data)}-byte ROM {rom_path} -- listing and ROM are not the same build")
    blk = data[base:end]
    words, i = [], 0
    while i + 4 <= len(blk):
        if blk[i:i + 2] == _MOVE_W_IMM_D3:
            words.append(struct.unpack_from(">H", blk, i + 2)[0])
            i += 4
        else:
            i += 2
    if len(words) != 6:
        raise Unmeasurable(
            f"expected 6 `move.w #imm, d3` encodings in {_STATIC_DMA_PROC} "
            f"[0x{base:X}, 0x{end:X}) of {rom_path}, decoded {len(words)}: {words}. "
            "Either the routine changed shape or the scan misaligned -- re-derive "
            "this reader before trusting any number below it.")
    b = [w * 2 for w in words]                        # words -> bytes (dma_length halved)
    if len(set(b[0:4])) != 1:
        raise Unmeasurable(f"the four encoded palette-line lengths differ: {b[0:4]}")
    return {"palette_line": b[0], "palette_lines": 4, "sat": b[4], "hscroll": b[5]}


def _cross_check(what, declared, assembled, how):
    """Route 1 vs route 2. Disagreement names BOTH SIDES and is never resolved.

    Deliberately not `assert declared == assembled`: which side is right is a
    question this tool cannot answer, and picking one silently is the failure
    mode the whole parcel exists to remove. `Unmeasurable` -> exit 3, loud.
    """
    if declared != assembled:
        raise Unmeasurable(
            f"{what}: this tool DECLARES {declared} reading .emp source, but the "
            f"BUILD says {assembled} ({how}). One of the two readers is wrong and "
            "nothing here can say which -- do not re-cut the baseline until you "
            "know. The pin is written by this harness, so a re-cut would launder "
            "the error rather than fix it.")


def assert_ship_asymmetry():
    """The claim the whole report rests on: Critical is unbudgeted, Important is not.

    Spelling-pinned rather than assumed. If either side ever grows or loses a
    budget test this raises, because the arithmetic below would then be about a
    machine that no longer exists.
    """
    vb = VBLANK_EMP.read_text()
    dq = DMA_QUEUE_EMP.read_text()
    checks = [
        (vb, r"jbsr\s+Process_DMA_Critical",
         "VInt_Level no longer calls Process_DMA_Critical"),
        (vb, r"jbsr\s+Process_DMA_Important",
         "VInt_Level no longer calls Process_DMA_Important"),
        (vb, r"move\.w\s+\(DMA_Budget_Default\)\.w,\s*\(DMA_Budget_Remaining\)\.w",
         "VInt_Level no longer seeds the frame budget from DMA_Budget_Default"),
        (dq, r"jbra\s+Drain_Budgeted_Queue",
         "Process_DMA_Important no longer tail-calls Drain_Budgeted_Queue"),
        (dq, r"bmi\s+\.out_of_budget",
         "Drain_Budgeted_Queue no longer has the out-of-budget branch"),
        # The Critical charge this tool computes in BYTES is charged by the
        # engine as `2 * sum(entry SizeH)`, and every byte figure below rests on
        # that doubling. Anchored as the CONTIGUOUS accumulate/double/subtract
        # block rather than as three separate searches: `add.w d1, d1` alone is a
        # two-token pattern that could match an unrelated double anywhere in the
        # file, and matching it there would pin nothing.
        (vb, r"movep\.w\s+DMAEntry\.SizeH\(a0\),\s*d0[^\n]*\n"
             r"(?:[^\n]*\n)*?\s*add\.w\s+d1,\s*d1[^\n]*\n"
             r"\s*sub\.w\s+d1,\s*DMA_Budget_Remaining",
         "VInt_Level no longer accumulates the Critical queue's SizeH words, "
         "doubles them to bytes and subtracts -- the words->bytes conversion "
         "every byte figure in this tool rests on is gone or has moved apart"),
    ]
    for text, pat, why in checks:
        if not re.search(pat, text):
            raise Unmeasurable(f"{why} (pattern {pat!r} not found)")
    # Process_DMA_Critical must NOT consult the budget -- that asymmetry is the defect.
    crit = re.search(
        r"pub proc Process_DMA_Critical.*?\n\}", dq, re.S)
    if crit is None:
        raise Unmeasurable("Process_DMA_Critical's body could not be delimited")
    if "DMA_Budget_Remaining" in crit.group(0):
        raise Unmeasurable(
            "Process_DMA_Critical now reads DMA_Budget_Remaining -- the "
            "unbudgeted-Critical premise of this report is DEAD; re-derive it."
        )
    return True


# ------------------------------------------------------------------- the model

#: pinned quantity -> the equate name sigil publishes for it. The constants are
#: their own names; the DPLC peaks are published by games/sonic4/data/*.emp as
#: `pub equ DPLC_PEAK_TILES_<SUBJECT>` in TILES, and are scaled by TILE_SIZE here.
_CONSTS = ("DMA_BUDGET_NTSC", "DMA_BUDGET_PAL", "PLANE_BUFFER_SIZE",
           "ART_STAGING_BUFFER_SIZE", "TILE_SIZE", "MAX_VDP_SPRITES")


def measure(lst_path, rom_path, equs=None, rom_crit=None):
    """The model, with every pinned input stated TWICE and refused on disagreement.

    `equs` / `rom_crit` override route 2 IN MEMORY and exist for the selftest's
    arm [E], which perturbs the assembled side without touching disk. Passing
    them is how the cross-check is shown CALIBRATED rather than merely live: a
    lookup that never disagrees is indistinguishable from no lookup at all.
    """
    assert_ship_asymmetry()

    if equs is None:
        equs = equ_table(lst_path)
    if rom_crit is None:
        rom_crit = rom_static_critical_lengths(lst_path, rom_path)

    for name in _CONSTS:
        if name not in equs:
            raise Unmeasurable(
                f"`{name}` has no `EQU` row in {lst_path}. sigil publishes an "
                "equate for every constant in engine/system/constants.emp, so its "
                "absence means the constant moved, was renamed, or stopped being "
                "reachable from this shape -- route 2 for it is gone, and route 1 "
                "alone is exactly the self-confirming reading this tool no longer "
                "makes.")
        _cross_check(name, _const(name), equs[name],
                     f"`EQU {name}` in {lst_path}, i.e. sigil's own evaluation of "
                     "engine/system/constants.emp")

    budget_ntsc = _const("DMA_BUDGET_NTSC")
    budget_pal = _const("DMA_BUDGET_PAL")
    plane = _const("PLANE_BUFFER_SIZE")
    staging = _const("ART_STAGING_BUFFER_SIZE")
    tile = _const("TILE_SIZE")

    crit = static_critical_lengths()
    for k in ("palette_line", "sat", "hscroll"):
        _cross_check(f"the static Critical `{k}` entry length", crit[k], rom_crit[k],
                     f"the `move.w #imm, d3` sigil encoded in {_STATIC_DMA_PROC}, "
                     f"doubled from words -- read out of {rom_path}")
    critical_bytes = crit["palette_line"] * crit["palette_lines"] + crit["sat"] + crit["hscroll"]

    labels = DS.lst_labels(lst_path)
    subs = DS.load_subjects(labels)
    peaks = {}
    peak_frames = {}
    for s in subs:
        by_frame = [sum(c for _, c in ents) * tile for ents in s["frames"]]
        if not by_frame:
            raise Unmeasurable(f"{s['name']}: DPLC parsed to zero frames")
        peaks[s["name"]] = max(by_frame)
        peak_frames[s["name"]] = [i for i, b in enumerate(by_frame) if b == max(by_frame)]
        # Route 2: engine.objects.dplc `dplc_peak_tiles`, an independently-written
        # .emp parser sigil runs over the same blob at build time and publishes as
        # an equate. This is the number the ENGINE'S OWN VRAM window guards are
        # written against, so a disagreement here is not a tooling curiosity --
        # it means this report and those `ensure`s describe different art.
        eq = "DPLC_PEAK_TILES_" + s["name"].upper()
        if eq not in equs:
            raise Unmeasurable(
                f"{s['name']}: no `EQU {eq}` row in {lst_path}. It is published by "
                f"`pub equ {eq} = dplc_peak_tiles({s['dplc_const']})` in {s['emp']} "
                "-- a `pub const` there would be comptime-only and emit NO row, "
                "which is how this was first written and why it says `equ`. Without "
                "it the peak has only this tool's own parse behind it.")
        _cross_check(f"{s['name']}'s peak per-frame DPLC bytes",
                     max(by_frame), equs[eq] * tile,
                     f"`EQU {eq}` ({equs[eq]} tiles) x TILE_SIZE {tile}, i.e. sigil "
                     f"evaluating engine.objects.dplc `dplc_peak_tiles` over the "
                     f"same blob")

    # The resident cast in the shipped game is ONE player. The two-player and
    # Tails-appendage rows are reported because dplc_straddle's own reserve model
    # counts them, and because they are the direction this margin gets worse in.
    solo = max(peaks["sonic"], peaks["knuckles"])
    duo = peaks["sonic"] + peaks["tails"] + peaks["tails_tail"]

    out = {}
    for region, budget in (("NTSC", budget_ntsc), ("PAL", budget_pal)):
        residual = budget - plane - critical_bytes
        out[region] = {
            "budget": budget,
            "charge_plane_max": plane,
            "charge_critical_max": critical_bytes,
            "residual": residual,
            "demand_solo": staging + solo,
            "demand_duo": staging + duo,
            "deficit_solo": staging + solo - residual,
            "deficit_duo": staging + duo - residual,
        }
    return {
        "constants": {
            "DMA_BUDGET_NTSC": budget_ntsc, "DMA_BUDGET_PAL": budget_pal,
            "PLANE_BUFFER_SIZE": plane, "ART_STAGING_BUFFER_SIZE": staging,
            "TILE_SIZE": tile, "MAX_VDP_SPRITES": _const("MAX_VDP_SPRITES"),
        },
        "critical_entry_bytes": crit,
        "critical_bytes_total": critical_bytes,
        "dplc_peak_bytes": peaks,
        "dplc_peak_frames": {k: [hex(i) for i in v] for k, v in peak_frames.items()},
        "regions": out,
    }


# -------------------------------------------------------------------- printing

def report(m, out=sys.stdout):
    p = lambda *a: print(*a, file=out)                                  # noqa: E731
    p("dma_defer_headroom -- Important-queue BYTE headroom per frame")
    p("")
    p("  charged before the Important drain (worst case):")
    p(f"    plane drain (Plane_Buffer_Ptr max)   {m['constants']['PLANE_BUFFER_SIZE']:6d} B")
    c = m["critical_entry_bytes"]
    p(f"    palette {c['palette_lines']} x {c['palette_line']} B"
      f"{'':<21}{c['palette_line'] * c['palette_lines']:6d} B")
    p(f"    SAT (MAX_VDP_SPRITES x 8){'':<12}{c['sat']:6d} B")
    p(f"    HScroll (always, parallax active){'':<4}{c['hscroll']:6d} B")
    p(f"    {'':<36}------")
    p(f"    Critical total{'':<23}{m['critical_bytes_total']:6d} B  (UNBUDGETED -- always ships)")
    p("")
    p("  wants the residual (Important, FIFO, page landing FIRST):")
    p(f"    PageIn staging landing{'':<15}{m['constants']['ART_STAGING_BUFFER_SIZE']:6d} B")
    for name, v in sorted(m["dplc_peak_bytes"].items()):
        frames = ",".join(m["dplc_peak_frames"][name][:4])
        p(f"    {name + ' peak DPLC frame':<37}{v:6d} B  (frames {frames})")
    p("")
    for region, r in m["regions"].items():
        p(f"  {region}: budget {r['budget']} - plane {r['charge_plane_max']} "
          f"- critical {r['charge_critical_max']} = residual {r['residual']} B")
        for tag in ("solo", "duo"):
            d = r[f"deficit_{tag}"]
            verdict = "DEFERS" if d > 0 else "fits"
            p(f"      {tag:4s}: demand {r['demand_' + tag]:6d} B  "
              f"deficit {d:+6d} B  -> {verdict}")
    p("")
    p("  A positive deficit means Drain_Budgeted_Queue reaches .out_of_budget")
    p("  while the SAT for the same frame has ALREADY shipped on Critical:")
    p("  one frame of new mappings over partly-old art, with every drop")
    p("  counter reading zero. See this file's header for the full chain.")
    p("")
    p("  WHAT THIS IS NOT. Every charge above is that rider's MAXIMUM, so the")
    p("  numbers describe an ENVELOPE, not a frame anybody observed. A frame")
    p("  reaches the deficit only when several riders peak together: the plane")
    p("  drain full, a page landing queued, the player on a peak DPLC frame.")
    p("  Whether that conjunction occurs in play is a RUNTIME question and this")
    p("  tool cannot answer it -- it can only say the window is open, and how")
    p("  wide. A negative deficit, by contrast, IS conclusive: the drain cannot")
    p("  defer, and this mechanism is ruled out for that region.")


# ----------------------------------------------------------------------- gate

def pinned(m):
    """The subset of a measurement the baseline pins -- one definition, two users
    (`gate` compares it, `--write-baseline` serialises it). They used to be two
    literal copies of the same dict, which is a second place for the pin's SHAPE
    to drift from itself."""
    return {"constants": m["constants"],
            "critical_entry_bytes": m["critical_entry_bytes"],
            "dplc_peak_bytes": m["dplc_peak_bytes"],
            "regions": m["regions"]}


def gate(m, out=sys.stdout, want=None):
    """`want=None` reads the committed pin; an injected `want` is the selftest's
    arm [D], which perturbs the EXPECTATION rather than the tree and so needs no
    file write at all."""
    if want is None:
        if not BASELINE.exists():
            raise Unmeasurable(
                f"no baseline at {BASELINE.relative_to(REPO)} -- run --write-baseline")
        want = json.loads(BASELINE.read_text())
    got = pinned(m)
    if got == want:
        print("dma_defer_headroom --gate: OK, every derived input matches the pin",
              file=out)
        return 0
    print("dma_defer_headroom --gate: FAILED -- a derived input moved.", file=out)
    _diff(want, got, out)
    print("", file=out)
    print("  If the move is intended, re-read this file's header (the deficit is "
          "the F7 mechanism), then re-cut with --write-baseline.", file=out)
    return 1


def _diff(want, got, out, path=""):
    for k in sorted(set(want) | set(got)):
        w, g = want.get(k, "<absent>"), got.get(k, "<absent>")
        here = f"{path}.{k}" if path else k
        if isinstance(w, dict) and isinstance(g, dict):
            _diff(w, g, out, here)
        elif w != g:
            print(f"    {here}: baseline {w} -> now {g}", file=out)


# ------------------------------------------------------------------- selftest

def selftest(lst_path, rom_path, out=sys.stdout):
    """Red-first proof, run against THIS tree, restoring what it mutated.

    FIVE arms. Three mutate a DIFFERENT class of input ON DISK; two perturb a
    reader's expectation IN MEMORY and touch no tracked file at all.

      [A] a constant           (DMA_BUDGET_NTSC in constants.emp)      DISK
      [B] a static DMA length  (the HScroll entry in buffers.emp)      DISK
      [C] the premise pin      (Process_DMA_Critical gains a budget read)  DISK
      [D] the committed pin    (one pinned value, perturbed in memory)  memory
      [E] the ASSEMBLED side   (one equate, perturbed in memory)       memory

    WHAT CHANGED HERE IN LS-15b-resid, AND WHY -- the LS-15b row's defect (ii):

      A and B used to assert `rc == 1` and DISCARD `_diff`'s output
      (`gate(measure(lst), io.StringIO())`), so neither could tell "the gate
      noticed WHAT I MUTATED" from "the gate noticed SOMETHING". That is an
      existence search: it establishes the predicate is live, never that it is
      calibrated. Both now assert on CONTENT.

      A and B also changed VERDICT, and the change is the evidence that route 2
      is live. A source-only mutation now makes the DECLARED and ASSEMBLED
      readings disagree -- the listing and ROM are from the unmutated build --
      so both raise `Unmeasurable` naming BOTH numbers, rather than reaching the
      gate at all. Each asserts the mutated value AND the assembled value appear
      in the message, so it is red for its OWN reason and not an unrelated one.

      [D] is the arm that keeps a genuine `gate rc == 1` under test, with a diff
      line derived from the LIVE MEASUREMENT and the perturbation -- never read
      out of the baseline file, which is the very artifact under suspicion. It
      requires that line to be the ONLY line, so a gate that reported everything
      as moved would fail it.

      [E] perturbs the INDEPENDENT source in memory (LS-15b's arm [7] shape) and
      is what makes the cross-check a calibration check rather than a lookup
      that happens to be present: it must refuse, naming both sides.

    Expectations are derived from the mutation and from the live measurement.
    Nothing here reads dma_defer_headroom_baseline.json to decide what to expect.
    """
    ok = True

    def note(name, verdict, why):
        nonlocal ok
        if verdict:
            print(f"  {name}: RED as required -- {why}", file=out)
        else:
            print(f"  {name}: GREEN when it must be RED -- {why}", file=out)
            ok = False

    # ---- route 2 must actually be readable before any arm means anything ----
    try:
        base = measure(lst_path, rom_path)
    except Unmeasurable as exc:
        print(f"  PRECONDITION: the unmutated tree is already UNMEASURABLE -- {exc}",
              file=out)
        print("  No arm below can be interpreted; every one of them would be red "
              "for this reason and not for its own.", file=out)
        return 1
    equs = equ_table(lst_path)

    # ---------------------------------------------------------- disk arms -----
    # `expect` is the substring set the raised message MUST contain. Each is
    # derived from the mutation (the new value) and from the live build (the old
    # one), so an arm that went red for an unrelated reason fails here.
    arms = [
        ("[A] a constant", CONSTANTS_EMP,
         "pub const DMA_BUDGET_NTSC = 6144",
         "pub const DMA_BUDGET_NTSC = 6145",
         ["DMA_BUDGET_NTSC", "6145", str(equs["DMA_BUDGET_NTSC"])]),
        ("[B] a static DMA length", BUFFERS_EMP,
         "move.w  #dma_length(896), d3",
         "move.w  #dma_length(892), d3",
         ["hscroll", "892", str(base["critical_entry_bytes"]["hscroll"])]),
        ("[C] the premise pin", DMA_QUEUE_EMP,
         "        movea.w DMA_Critical_Slot, a1           // (DMA_Critical_Slot).w",
         "        move.w  DMA_Budget_Remaining, d0        // premise-pin mutation\n"
         "        movea.w DMA_Critical_Slot, a1           // (DMA_Critical_Slot).w",
         ["Process_DMA_Critical now reads DMA_Budget_Remaining"]),
    ]
    for name, path, old, new, expect in arms:
        text = path.read_text()
        if text.count(old) != 1:
            print(f"  {name}: UNMEASURABLE -- anchor appears "
                  f"{text.count(old)} times in {path.name}, not once", file=out)
            ok = False
            continue
        path.write_text(text.replace(old, new, 1))
        try:
            # An unapplied mutation and a correctly restored baseline both look
            # green, so quote the mutated line back OFF DISK before judging.
            on_disk = new.splitlines()[0].strip()
            if on_disk not in path.read_text():
                print(f"  {name}: UNMEASURABLE -- the mutation did not reach "
                      f"{path.name} on disk", file=out)
                ok = False
                continue
            try:
                measure(lst_path, rom_path)
            except Unmeasurable as exc:
                missing = [e for e in expect if e not in str(exc)]
                note(name, not missing,
                     str(exc) if not missing
                     else f"but for the WRONG reason: {missing} absent from {exc!r}")
            else:
                note(name, False, "the reader agreed with the build after the "
                                  "source moved under it")
        finally:
            path.write_text(text)

    # --------------------------------------------------------- memory arms ----
    # [D] the gate's DIFF, against a perturbed expectation. PLANE_BUFFER_SIZE is
    # chosen because it appears in `constants` and in both regions' charge, so a
    # gate reporting a whole subtree as moved would break the "only line" check.
    want = json.loads(json.dumps(pinned(base)))            # deep copy
    live = base["constants"]["PLANE_BUFFER_SIZE"]
    want["constants"]["PLANE_BUFFER_SIZE"] = live + 64
    buf = io.StringIO()
    rc = gate(base, buf, want=want)
    lines = [l.strip() for l in buf.getvalue().splitlines() if " -> now " in l]
    expect_line = f"constants.PLANE_BUFFER_SIZE: baseline {live + 64} -> now {live}"
    note("[D] the committed pin (in memory)",
         rc == 1 and lines == [expect_line],
         f"gate rc={rc}, diff lines {lines!r} (wanted exactly [{expect_line!r}])")

    # [E] the ASSEMBLED side, perturbed in memory. Two shots: one constant, one
    # DPLC peak, because they cross-check through different code paths.
    for key, why in ((("DMA_BUDGET_NTSC"), "a constant equate"),
                     (("DPLC_PEAK_TILES_SONIC"), "a DPLC peak equate")):
        bad = dict(equs)
        bad[key] = equs[key] + 1
        try:
            measure(lst_path, rom_path, equs=bad)
        except Unmeasurable as exc:
            note(f"[E] the assembled side ({why})",
                 str(equs[key] + 1) in str(exc) and key.split("_")[-1].lower() in
                 str(exc).lower(),
                 str(exc))
        else:
            note(f"[E] the assembled side ({why})", False,
                 f"the cross-check accepted an equate one off from the build's own "
                 f"({key} {equs[key]} -> {equs[key] + 1}) -- it is a LOOKUP, not a "
                 f"comparison")

    # And green again on the restored tree -- a selftest that leaves the tree
    # red is indistinguishable from one that never restored it.
    rc = gate(measure(lst_path, rom_path), io.StringIO())
    if rc != 0:
        print(f"  restore check: tree did NOT come back green (rc={rc})", file=out)
        ok = False
    else:
        print("  restore check: tree green again", file=out)

    print("", file=out)
    print("  COVERAGE, and its edge. Arms A/B/C move the tree and require this "
          "tool to refuse; D and E move an EXPECTATION and require it to refuse "
          "the same way, without touching a tracked file. Together they say the "
          "cross-check is calibrated, not merely present. WHAT THEY DO NOT SAY: "
          "both routes read the same files and the same format spec, so a value "
          "wrong in constants.emp, or a wrong DPLC spec, passes every arm above. "
          "Nothing here executes the engine.", file=out)
    return 0 if ok else 1


# --------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lst", default=str(REPO / "s4.debug.lst"))
    # Defaulted from --lst rather than given its own default so the ROM is always
    # the listing's OWN build: a stale pairing would cross-check route 1 against
    # a different tree and call the disagreement a defect.
    ap.add_argument("--rom", default=None,
                    help="ROM for route 2 (default: --lst with .bin for .lst)")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    rom = a.rom if a.rom else re.sub(r"\.lst$", ".bin", a.lst)
    try:
        if a.selftest:
            return selftest(a.lst, rom)
        m = measure(a.lst, rom)
        if a.write_baseline:
            BASELINE.write_text(
                json.dumps(pinned(m), indent=2, sort_keys=True) + "\n")
            print(f"baseline written to {BASELINE.relative_to(REPO)}")
            return 0
        report(m)
        if a.gate:
            return gate(m)
        return 0
    except (Unmeasurable, DS.Unmeasurable) as exc:
        print(f"dma_defer_headroom: UNMEASURABLE -- {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
