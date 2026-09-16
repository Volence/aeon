#!/usr/bin/env python3
"""capture_settle — the SETTLE PREDICATE and the NAME DERIVATION, in one place, with no
emulator anywhere near it.

WHY THIS FILE EXISTS, and it is one incident rather than a tidiness argument.

`docs/captures/2026-09-13-regions-p2-night/t5-f272-settled.png` was used as the evidence
base for a colour ruling. It is not settled: a decode found 45.9% of its pixels in neither
the day nor the night palette (docs/superpowers/notes/2026-09-16-night-palette-mechanism.md).
A human wrote the word into the name because the CRAM *tracer* entry had reached its night
value. **The refutation was already in that README's own table, one column over: the same row
records `Pal_Fade_Frames` = 11, and `engine/ram.emp` spells that field "cross-fade frames
remaining (0 = stable)".** Nothing compared the name against the state recorded beside it,
because nothing was ever going to: the name was typed and the state was tabulated, by hand,
minutes apart.

THE FIX IS NOT A CHECKER. A checker is a thing somebody must remember to run, on the right
files, before believing a name. The fix is that the name is DERIVED from the state at the
moment of capture, so it cannot disagree with it. This module is that derivation, and the
only place the string "settled" is allowed to enter a filename.

WHAT `Pal_Fade_Frames == 0` DOES AND DOES NOT GUARANTEE
------------------------------------------------------
It is NECESSARY and it is not SUFFICIENT. Read out of engine/effects/palette.emp:

  GUARANTEED. The cross-fade layer is finished. `Palette_DoFade` leaves the count 0 by
  exactly two paths and both end at `.close`, which copies `Pal_Target` over
  `Palette_Buffer` lines 1-3 (and over `Pal_Base`): `.arrived` (every channel is on its
  target, the early close) and the backstop (`subq.b #1` reached 0). So a count of 0 that
  the fade itself wrote does imply `Palette_Buffer` lines 1-3 == `Pal_Target`.

  NOT GUARANTEED, four separate ways:

  1. THE FADE IS ONE LAYER OF FIVE. `Palette_Compose` runs base -> cycling -> cross-fade ->
     operators -> variants. `Palette_DoCycle` (a `Pal_Cycle_Script`) and `Palette_DoOperator`
     (a `Pal_Op`) move lines 1-3 and neither looks at `Pal_Fade_Frames`. A count of 0 says
     nothing whatever about them.
  2. A COUNT OF 0 CAN MEAN "NEVER STARTED", AND IT CAN MEAN "CANCELLED". `Palette_LoadPal`'s
     snap arm does `clr.b Pal_Fade_Frames` (palette.emp:296) — a snap install cancels a fade
     in flight. A frame sampled one tick after such a cancel reads 0 with the buffer NOT on
     the palette the cancelled fade was heading for. Hence the separate buffer-vs-target
     clause below: it distinguishes "arrived" from "stopped".
  3. THE BUFFER IS NOT CRAM. `Palette_Compose` runs in the MAIN LOOP (engine/system/
     game_loop.emp, after the state dispatch); `Enqueue_Dirty_Buffers` runs in the NEXT
     VBlank (engine/system/vblank.emp) and only then does a DMA carry lines 1-3 to CRAM. A
     settled buffer is one tick ahead of settled CRAM.
  4. CRAM IS NOT THE PICTURE. The screenshot a paused emulator hands back is the previously
     completed video frame, one tick behind the state read beside it (this is
     `tools/e2_snap_capture.py`'s header finding, and it is load-bearing here).

  And the thing that actually produced the bad name: ONE ENTRY OF CRAM IS NOT THE PALETTE.
  The 2026-09-13 set watched CRAM line 1 entry 2 as a tracer. `Palette_DoFade` steps every
  channel of all 48 words by +/-1, so a word whose channels are close to their targets
  ARRIVES EARLY and sits there while the rest of the palette is still moving. A tracer
  reaching its night value is evidence about one colour and no evidence at all about the
  other 47.

THE PREDICATE, therefore, is seven clauses over a LIVE read, in this order. The first one
that fails NAMES THE FRAME, so a filename says not only that it is unsettled but why:

  fading  `Pal_Fade_Frames == 0`
  armed   `Pal_Fade_Request == 0`         (a fade armed to start on the next load)
  layer   no other palette layer is live  (`Pal_Active` base/cycle/op bits, `Pal_Op`,
                                           `Pal_Cycle_Script`)
  buf     `Palette_Buffer` lines 1-3 == `Pal_Target`, under `Palette_DoFade`'s own
          `$0EEE` channel mask  (arrived, not merely stopped)
  cram    CRAM lines 1-3 == `Palette_Buffer` lines 1-3  (the DMA has landed)
  lag     the last N samples each advanced Logic_Tick by exactly 1 and took no lag frame
  hold    CRAM lines 1-3 identical across the last N samples

All seven -> `settled`. A clause whose inputs are absent from the row is UNDECIDABLE and the
frame is named `unknown`: never `settled`, and never quietly treated as a pass.

N IS DERIVED, NOT CHOSEN
------------------------
N = COMPOSE_TO_CRAM_TICKS + CRAM_TO_CAPTURED_FRAME_TICKS + 1 = 3.

  COMPOSE_TO_CRAM_TICKS = 1. `GameLoop` is `VSync_Wait` -> `Logic_Tick++` -> ... -> state
  dispatch -> `Palette_Compose` -> loop. So tick T's compose is followed by the VBlank that
  tick T+1's `VSync_Wait` returns from, and that VBlank's `Enqueue_Dirty_Buffers` is what
  moves lines 1-3 into CRAM. A CRAM read at tick T+1's sample point shows tick T's compose.

  CRAM_TO_CAPTURED_FRAME_TICKS = 1. The paused screenshot is the previously completed video
  frame. The CRAM installed in the VBlank opening tick T+1 is scanned out during tick T+1,
  and that frame is only *completed* at tick T+2's sample point.

  + 1 because N samples span N-1 tick intervals, and a run must span the depth (2) to cover
  it. At N = 3 the compose the captured PNG actually shows lies strictly inside the stable
  run, with a settled neighbour on each side.

`derive_engine_facts()` re-reads those three orderings out of the engine source on every
run and REFUSES if any has moved, so N cannot outlive its derivation. Changing the game
loop makes this module loud, not wrong.

WHAT THIS MODULE STILL CANNOT DO. It cannot see a mid-frame CRAM write: a raster program
with an `OP_PAL_REGION` writes CRAM during the scan, so a read at one point in the frame is
a mixture and can be perfectly stable frame to frame while the PICTURE is not the palette.
That is a PREMISE for the caller to refuse on (the subject region must bind
`Raster_Program_None`), not a clause here — a per-frame clause could not tell the two apart.
`tools/night_settle_capture.py` refuses on exactly that premise.

No emulator, no I/O except reading engine source for the derivation. Exercised offline by
tools/test_capture_settle.py, including against the 2026-09-13 set's own recorded rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent

#: The ONE place this word may be produced. Nothing else in this module or its callers may
#: spell it into a filename; tools/test_capture_settle.py pins that.
SETTLED_WORD = "settled"

#: The word used when a clause could not be evaluated. Deliberately not a substring of, and
#: not containing, SETTLED_WORD — "unsettled" would have been, and a glob for `*settled*`
#: would then have swept up the frames that are anything but.
UNKNOWN_WORD = "unknown"


class DerivationError(Exception):
    """The engine source no longer reads the way this module's N is derived from. Callers
    must refuse to run — exit 2, never a pass and never a quietly stale N."""


# ---------------------------------------------------------------------------------------
# The derivation
# ---------------------------------------------------------------------------------------

#: Ticks between a `Palette_Compose` writing Palette_Buffer and CRAM holding it.
COMPOSE_TO_CRAM_TICKS = 1
#: Ticks between CRAM holding a palette and a paused screenshot showing a frame drawn with it.
CRAM_TO_CAPTURED_FRAME_TICKS = 1


@dataclass(frozen=True)
class EngineFacts:
    """Everything the predicate needs that comes from the engine rather than from a read."""
    stable_ticks: int            # N
    moving_bits: int             # Pal_Active bits meaning "a layer that moves lines 1-3"
    chan_mask: int               # Palette_DoFade's own comparison mask
    fade_frames_const: int       # PAL_FADE_FRAMES, for the report's model cross-check
    citations: tuple             # (claim, where) pairs, printed into every report


def _src(aeon: Path, rel: str) -> str:
    p = aeon / rel
    if not p.is_file():
        raise DerivationError(f"{rel} is not in this tree — N cannot be derived from it")
    return p.read_text()


def _const(aeon: Path, rel: str, name: str) -> int:
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|%[01]+|\d+)",
                  _src(aeon, rel), re.M)
    if not m:
        raise DerivationError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v[0] == "$" else int(v[1:], 2) if v[0] == "%" else int(v)


def derive_engine_facts(aeon: Path = AEON) -> EngineFacts:
    """N and the predicate's constants, RE-READ out of the engine on every run.

    Each check below is the source of one term of N or of one clause. If the engine stops
    reading this way the answer is a refusal, not an N that used to be right."""
    cites = []

    loop = _src(aeon, "engine/system/game_loop.emp")
    m = re.search(r"pub proc GameLoop\s*\(\)[^{]*\{(.*?)^\}", loop, re.M | re.S)
    if not m:
        raise DerivationError("cannot find `pub proc GameLoop` in engine/system/game_loop.emp")
    body = re.sub(r"//[^\n]*", "", m.group(1))
    order = [tok for tok in re.findall(
        r"jbsr\s+VSync_Wait|addq\.l\s+#1,\s*Logic_Tick|jsr\s+\(a0\)\s+as\s+GameState|"
        r"jbsr\s+Palette_Compose\b", body)]
    kinds = ["vsync" if "VSync" in t else
             "tick" if "Logic_Tick" in t else
             "state" if "GameState" in t else "compose" for t in order]
    if kinds[:4] != ["vsync", "tick", "state", "compose"]:
        raise DerivationError(
            "GameLoop no longer runs VSync_Wait -> Logic_Tick++ -> the state dispatch -> "
            f"Palette_Compose in that order (found {kinds}). COMPOSE_TO_CRAM_TICKS = "
            f"{COMPOSE_TO_CRAM_TICKS} is derived from exactly that ordering; re-derive it "
            "before this module names another frame `%s`." % SETTLED_WORD)
    cites.append(("Palette_Compose runs in the main loop AFTER the state dispatch, so a "
                  "compose is followed by the VBlank the next tick's VSync_Wait returns from",
                  "engine/system/game_loop.emp, proc GameLoop"))

    vb = _src(aeon, "engine/system/vblank.emp")
    if not re.search(r"jbsr\s+Enqueue_Dirty_Buffers\b", vb):
        raise DerivationError(
            "engine/system/vblank.emp no longer calls Enqueue_Dirty_Buffers — the "
            "compose -> CRAM latency N is derived from is gone")
    cites.append(("Enqueue_Dirty_Buffers, which queues the palette DMA, runs in VBlank",
                  "engine/system/vblank.emp"))

    pal = _src(aeon, "engine/effects/palette.emp")
    comp = re.search(r"pub proc Palette_Compose\s*\(\)[^{]*\{(.*?)^\}", pal, re.M | re.S)
    if not comp:
        raise DerivationError("cannot find `pub proc Palette_Compose` in engine/effects/palette.emp")
    cbody = re.sub(r"//[^\n]*", "", comp.group(1))
    for what, pat in (("the base one-shot copy", r"tst\.b\s+Pal_Base_Dirty"),
                      ("the cycling layer", r"jbsr\s+Palette_DoCycle\b"),
                      ("the cross-fade layer", r"tst\.b\s+Pal_Fade_Frames"),
                      ("the operator layer", r"tst\.b\s+Pal_Op")):
        if not re.search(pat, cbody):
            raise DerivationError(
                f"Palette_Compose no longer runs {what} (/{pat}/ is gone). The `layer` clause "
                "enumerates the layers that can move lines 1-3 from this body; re-read it.")
    cites.append(("Palette_Compose composes base, cycling, cross-fade and operators over "
                  "lines 1-3, so Pal_Fade_Frames == 0 settles ONE of four",
                  "engine/effects/palette.emp, proc Palette_Compose"))

    fade = re.search(r"proc Palette_DoFade\s*\(\)[^{]*\{(.*?)^\}", pal, re.M | re.S)
    if not fade:
        raise DerivationError("cannot find `proc Palette_DoFade` in engine/effects/palette.emp")
    fbody = re.sub(r"//[^\n]*", "", fade.group(1))
    mask = re.search(r"andi\.w\s+#\$([0-9A-Fa-f]+),\s*d6\s+beq\s+\.arrived", fbody)
    if not mask:
        raise DerivationError(
            "Palette_DoFade's arrival test (`andi.w #$..., d6 ; beq .arrived`) is gone. The "
            "`buf` and `cram` clauses compare under THAT mask rather than a mask typed here.")
    chan_mask = int(mask.group(1), 16)
    if not re.search(r"clr\.b\s+Pal_Fade_Frames", fbody):
        raise DerivationError("Palette_DoFade no longer closes with `clr.b Pal_Fade_Frames`")
    cites.append((f"the arrival comparison is masked with ${chan_mask:04X}, so `buf` and "
                  "`cram` compare exactly the bits the engine compares",
                  "engine/effects/palette.emp, proc Palette_DoFade `.arrived` test"))

    load = re.search(r"pub proc Palette_LoadPal\s*\([^)]*\)[^{]*\{(.*?)^\}", pal, re.M | re.S)
    if not load or not re.search(r"clr\.b\s+Pal_Fade_Frames",
                                 re.sub(r"//[^\n]*", "", load.group(1))):
        raise DerivationError(
            "Palette_LoadPal's snap arm no longer clears Pal_Fade_Frames. The `buf` clause "
            "exists because a 0 count can mean CANCELLED as well as ARRIVED; re-derive it.")
    cites.append(("a snap install CANCELS a fade in flight with `clr.b Pal_Fade_Frames`, so "
                  "a 0 count alone cannot tell `arrived` from `stopped`",
                  "engine/effects/palette.emp, proc Palette_LoadPal snap arm"))

    moving = (_const(aeon, "engine/effects/palette.emp", "PAL_ACT_BASE") |
              _const(aeon, "engine/effects/palette.emp", "PAL_ACT_CYCLE") |
              _const(aeon, "engine/effects/palette.emp", "PAL_ACT_OP"))
    n = COMPOSE_TO_CRAM_TICKS + CRAM_TO_CAPTURED_FRAME_TICKS + 1
    cites.append((f"N = {COMPOSE_TO_CRAM_TICKS} (compose -> CRAM) + "
                  f"{CRAM_TO_CAPTURED_FRAME_TICKS} (CRAM -> the completed frame a paused "
                  f"screenshot returns) + 1 (N samples span N-1 intervals) = {n}",
                  "this module's header"))
    return EngineFacts(stable_ticks=n, moving_bits=moving, chan_mask=chan_mask,
                       fade_frames_const=_const(aeon, "engine/effects/palette.emp",
                                                "PAL_FADE_FRAMES"),
                       citations=tuple(cites))


# ---------------------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Verdict:
    word: str                    # the state word that goes in the filename
    settled: bool                # every clause held, from a live read
    decided: bool                # every clause could be evaluated at all
    reasons: tuple = field(default_factory=tuple)
    stable_run: int = 0          # consecutive samples, ending here, with identical CRAM


def _masked(words, mask):
    return None if words is None else tuple(w & mask for w in words)


def _missing(row, *keys):
    return [k for k in keys if row.get(k) is None]


def assess(series, facts: EngineFacts) -> Verdict:
    """The verdict for `series[-1]`, given every sample before it in `series`.

    `series` is a list of state rows, oldest first, each a dict with any of:
      tick, dtick, lag, fade_frames, fade_request, pal_active, pal_op, pal_cycle_script,
      buffer (48 ints), target (48 ints), cram (48 ints).
    A key that is absent or None makes its clause UNDECIDABLE rather than false: the caller
    did not measure it, and a predicate must not answer a question it was not given.
    """
    if not series:
        raise ValueError("assess() needs at least the row being assessed")
    row = series[-1]
    mask = facts.chan_mask
    undecided: list[str] = []

    def undec(clause, keys):
        undecided.append(f"`{clause}`: the row carries no " + ", ".join(keys))
        return Verdict(UNKNOWN_WORD, False, False, tuple(undecided), _stable_run(series, mask))

    # 1 -- fading
    if (miss := _missing(row, "fade_frames")):
        return undec("fading", miss)
    if row["fade_frames"] != 0:
        return Verdict("fading", False, True,
                       (f"Pal_Fade_Frames = {row['fade_frames']}; engine/ram.emp spells this "
                        "field \"cross-fade frames remaining (0 = stable)\", so a non-zero "
                        "count is the cross-fade still running",), _stable_run(series, mask))

    # 2 -- armed
    if (miss := _missing(row, "fade_request")):
        return undec("armed", miss)
    if row["fade_request"] != 0:
        return Verdict("armed", False, True,
                       ("Pal_Fade_Request is set: the next Palette_LoadPal will start a "
                        "cross-fade rather than snap",), _stable_run(series, mask))

    # 3 -- layer
    if (miss := _missing(row, "pal_active", "pal_op", "pal_cycle_script")):
        return undec("layer", miss)
    live = []
    if row["pal_active"] & facts.moving_bits:
        live.append(f"Pal_Active = {row['pal_active']:#07b} has a base/cycle/operator bit set "
                    f"(mask {facts.moving_bits:#07b})")
    if row["pal_op"]:
        live.append(f"Pal_Op = {row['pal_op']} (a global operator is running)")
    if row["pal_cycle_script"]:
        live.append(f"Pal_Cycle_Script = {row['pal_cycle_script']:#010x} (a cycling script "
                    "is installed)")
    if live:
        return Verdict("layer", False, True, tuple(live), _stable_run(series, mask))

    # 4 -- buf
    if (miss := _missing(row, "buffer", "target")):
        return undec("buf", miss)
    if _masked(row["buffer"], mask) != _masked(row["target"], mask):
        bad = [i for i in range(len(row["buffer"]))
               if (row["buffer"][i] ^ row["target"][i]) & mask]
        return Verdict("buf", False, True,
                       (f"{len(bad)} of {len(row['buffer'])} words of Palette_Buffer lines "
                        f"1-3 differ from Pal_Target under ${mask:04X}, first at line "
                        f"{bad[0] // 16 + 1} entry {bad[0] % 16}: ${row['buffer'][bad[0]]:04X} "
                        f"vs ${row['target'][bad[0]]:04X}. The fade STOPPED rather than "
                        "arrived (Palette_LoadPal's snap arm clears the count)",),
                       _stable_run(series, mask))

    # 5 -- cram
    if (miss := _missing(row, "cram")):
        return undec("cram", miss)
    if _masked(row["cram"], mask) != _masked(row["buffer"], mask):
        bad = [i for i in range(len(row["cram"]))
               if (row["cram"][i] ^ row["buffer"][i]) & mask]
        return Verdict("cram", False, True,
                       (f"{len(bad)} of {len(row['cram'])} words of CRAM lines 1-3 differ "
                        f"from Palette_Buffer, first at line {bad[0] // 16 + 1} entry "
                        f"{bad[0] % 16}: ${row['cram'][bad[0]]:04X} vs "
                        f"${row['buffer'][bad[0]]:04X}. The compose has not reached CRAM "
                        "yet (Enqueue_Dirty_Buffers runs in the next VBlank)",),
                       _stable_run(series, mask))

    # 6 -- lag
    window = series[-facts.stable_ticks:]
    if len(window) < facts.stable_ticks:
        return Verdict("hold", False, True,
                       (f"only {len(window)} sample(s) taken; {facts.stable_ticks} consecutive "
                        "are required before a frame may be called settled",),
                       _stable_run(series, mask))
    for s in window[1:]:
        if s.get("dtick") is None or s.get("lag") is None:
            return undec("lag", ["dtick/lag over the stability window"])
    dirty = [s for s in window[1:] if s["dtick"] != 1]
    lagged = [(a, b) for a, b in zip(window, window[1:]) if b["lag"] != a["lag"]]
    if dirty or lagged:
        why = []
        if dirty:
            why.append("Logic_Tick advanced by " +
                       ", ".join(str(s["dtick"]) for s in dirty) + " rather than 1")
        if lagged:
            why.append(f"Lag_Frame_Count moved {len(lagged)} time(s) inside the window, so a "
                       "logic tick spanned more than one video frame and the compose-to-frame "
                       "mapping N is derived from does not hold across it")
        return Verdict("lag", False, True, tuple(why), _stable_run(series, mask))

    # 7 -- hold
    run = _stable_run(series, mask)
    if run < facts.stable_ticks:
        return Verdict("hold", False, True,
                       (f"CRAM lines 1-3 have been identical for {run} consecutive sample(s); "
                        f"{facts.stable_ticks} are required (see this module's derivation of "
                        "N)",), run)

    return Verdict(SETTLED_WORD, True, True,
                   (f"all seven clauses held from a live read, with CRAM identical across "
                    f"the last {run} samples",), run)


def _stable_run(series, mask) -> int:
    """How many consecutive samples ending at series[-1] carry identical CRAM lines 1-3.
    0 when the last row carries no CRAM at all: not measured is not stable."""
    last = _masked(series[-1].get("cram"), mask)
    if last is None:
        return 0
    n = 1
    for s in reversed(series[:-1]):
        if _masked(s.get("cram"), mask) != last:
            break
        n += 1
    return n


# ---------------------------------------------------------------------------------------
# The name
# ---------------------------------------------------------------------------------------

def frame_name(leg: str, row: dict, verdict: Verdict, ext: str = "png") -> str:
    """The filename for a captured frame, derived ENTIRELY from the state read beside it.

    `<leg>-k<+NNN>-t<NNNNN>-cx<NNNN>-r<NN>-pf<NN>-<state>.<ext>`

      k     ticks from the crossing tick (the first tick the new region is current)
      t     Logic_Tick, the engine's deterministic timebase
      cx    the camera CENTRE x -- the point Region_Resolve tests, not Camera_X
      r     the region row the ROM's own table puts that centre in (`XX` = no row)
      pf    Pal_Fade_Frames as read on this tick
      state SETTLED_WORD, or the name of the FIRST clause that refused, or `unknown`

    The only way to get `settled` into a name is for `assess()` to have returned it from a
    live read. This function will not take the word from a caller."""
    if verdict.word == SETTLED_WORD and not verdict.settled:
        raise ValueError("refusing to name a frame `%s` from a verdict that is not settled — "
                         "this is the bug this module exists to make impossible" % SETTLED_WORD)
    for need in ("k", "tick", "centre_x", "fade_frames"):
        if row.get(need) is None:
            raise ValueError(f"refusing to name a frame with no `{need}`: a name that omits "
                             "the state it is derived from is the defect, not a shortcut")
    r = row.get("row")
    return (f"{leg}-k{row['k']:+04d}-t{row['tick']:05d}-cx{row['centre_x']:04d}"
            f"-r{'XX' if r is None else f'{r:02d}'}-pf{row['fade_frames']:02d}"
            f"-{verdict.word}.{ext}")
