#!/usr/bin/env python3
"""bg_vscroll_rate_witness — GATE BG-RATE. Does the BG V-scroll ever move more than
BG_VSCROLL_MAX_STEP in one logic tick, and is it ever bounded by the CURRENT REGION's map
height rather than by the plane's?

THE SUBJECT (regions part 2, step 4; empyrean docs/superpowers/specs/2026-09-14-regions-part-2-design.md
§4.4). `Parallax_Step5_Vscroll` (engine/level/parallax.emp) ends in one clamp site, and step 4
changed both halves of it:

  (a) POSITION. The ceiling was `VSCROLL_BG_MAX = PLANE_B_SPAN - SCREEN_HEIGHT` — a fact about
      the 512-line PLANE. It is now `rg_bg_span - SCREEN_HEIGHT` read from the region the
      crossing cached in `Region_Current`, falling back to VSCROLL_BG_MAX when the row leaves
      `rg_bg_span` at 0. Map space, not plane space.
  (b) RATE. `|new - Parallax_Current_Vscroll_BG| <= BG_VSCROLL_MAX_STEP`, applied after the
      snap-or-lerp and the bob and the position clamp, immediately before the store. This is
      the bound on the row streamer's per-frame work (steps 5 and 6), and the engine-side
      replacement for a level-design door rule.

⚠ READ THIS BEFORE READING A GREEN FROM HERE — WHAT THIS WITNESS CANNOT DISTINGUISH.
Every region row shipped in OJZ act 1 leaves `rg_bg_span` at 0 (ten rows in release, eleven in
DEBUG). So on this tree the position clamp takes its FALLBACK on every frame and behaves
EXACTLY as it did before step 4. Legs C/D/W below would pass byte for byte with the whole
position-clamp change reverted, and so would A3, which models the clamp but is only exercised
where the clamp would act. **Leg S is the ONLY thing anywhere in this tree that tests change
(a) at all**, so a run in which leg S did not run is no evidence about the position clamp — the
tool exits 2 and says that in those words, never 0.

HOW LEG S GETS ITS SUBJECT, and the route it does NOT take. It patches `rg_bg_span` in a COPY
OF THE ROM ON DISK and boots that in its own instance. A live `emulator/write_memory` poke was
tried first and is REFUSED BY THE CORE, measured 2026-09-16: `[-32004] only the work-RAM window
($E00000-$FFFFFF) is writable; ROM and I/O writes are refused`. The on-disk route turned out to
be better evidence anyway — `AetherInstance` byte-compares the WHOLE 4 MB cart against the file
on every spawn, so the patched word is proven present by a full-image comparison rather than by
a single-word readback.

WHAT IS ASSERTED (exit 1 on any failure):
  R0  the premise, reported not assumed: every region row's rg_bg_span, and how many are
      non-zero. Zero non-zero rows is a loud FINDING, not a failure — it is the tree's truth —
      but it is what makes legs C/D/W blind to change (a).
  A1  THE GATE. On every consecutive pair of samples in every leg,
      |v[n] - v[n-1]| <= BG_VSCROLL_MAX_STEP, where v is `Parallax_Current_Vscroll_BG` sampled
      once per logic tick at the `GameState_OJZScroll_Update` entry.
  A2  0 <= v[n] <= ceiling[n] on every sample, where ceiling[n] is DERIVED from the region
      `Region_Current` names at that sample: rg_bg_span - SCREEN_HEIGHT, or VSCROLL_BG_MAX when
      the span is 0 or no region is resolved.
  A3  the whole clamp, modelled: on every tick where the config is not mid-transition,
      v[n] == clamp_model(target(camY[n]), v[n-1], ceiling[n]) exactly, with target computed
      from the ACTIVE parallax_config's own pcfg_v_factor_bg / v_center_y / v_offset read out
      of the ROM. This is the assertion that would catch a clamp applied in the wrong order.
  A4  THE RATE DISCRIMINATOR (leg W). After a DEBUG warp that jumps the camera far enough for
      the unclamped target to move more than 2 * BG_VSCROLL_MAX_STEP, there is a run of at
      least two consecutive ticks whose |step| is EXACTLY BG_VSCROLL_MAX_STEP. Without the
      rate clamp the jump completes in one tick and no such run exists, so A4 is red on a tree
      with (b) reverted. BOTH THE COLUMN AND THE ENDPOINTS ARE CHOSEN FROM THE ACT'S OWN REGION
      TABLE by `plan_vertical_leg()`, which probes rows in order, asks the ENGINE which config
      is live in each, and takes the first whose derived jump qualifies — see that function's
      header for why it exists and for the vertical-lock rows it correctly rejects.
  A5  THE POSITION DISCRIMINATOR (leg S, a PATCHED ROM COPY). With the chosen row's
      rg_bg_span patched to SPAN_TEST (derived from THAT region's own reach, so
      SPAN_TEST - SCREEN_HEIGHT is strictly below VSCROLL_BG_MAX and at least one
      BG_VSCROLL_MAX_STEP below what the act can actually drive the scroll to), a descent
      inside that row settles with v == SPAN_TEST - SCREEN_HEIGHT and never above it. The
      pre-step-4 code settles at VSCROLL_BG_MAX instead, so this is red with (a) reverted.

WHY "THE SHAFT FALL" IS LEG D, AND WHY IT IS A NEGATIVE CONTROL RATHER THAN A DISCRIMINATOR.
The step-4 gate line asks for "the shaft fall". `tools/plane_buffer_peak_probe.py`'s route
catalogue already settled what that means for a CAMERA-rate question, and its answer is
transcribed rather than re-argued: in the DEBUG shape the player boots into free flight at
PLAYER_DEBUG_FLY_SPEED = 16 px/frame, which IS CAM_MAX_Y_STEP, the camera's own per-frame
ceiling — so a physics fall cannot beat a held DOWN, and free flight is the worst case for
camera Y rate. With the shipped configs' v_factor the BG scroll moves camY >> v_factor per
frame, which is FAR under BG_VSCROLL_MAX_STEP, so leg D is expected to show the clamp never
binding. That is its value: it says the rate clamp does not fire in ordinary play. It is not
evidence that the clamp exists. A4 is.

EXPECTATIONS ARE DERIVED FROM SOURCE, never copied: BG_VSCROLL_MAX_STEP, VSCROLL_BG_MAX,
SCREEN_HEIGHT, PLANE_B_SPAN, PARALLAX_LERP_SHIFT and the camera halves are resolved out of the
.emp `const` declarations by `emp_consts()` below, which evaluates the declaration EXPRESSIONS
(BG_VSCROLL_MAX_STEP is `BG_VSCROLL_MAX_STEP_ROWS * BG_VSCROLL_ROW_PX`, and that is
`PLANE_B_SPAN / PLANE_B_CELL_ROWS`) rather than matching a literal. The parallax_config field
offsets come from the struct's own `// $XX` comments, cross-checked against the field order.

RUNNER: tools/effects_gates.py, gate `bg_vscroll_rate`.

⚠ NOT YET RUN. This witness was written by a session under a no-emulator invariant (background
agents deadlock the emulator MCP). It has never been executed. Its first run is the controller's
foreground job, and so is its red-first proof — see the MUTATIONS block at the foot of this file
for the two one-line reverts that must make it red, and which leg each one must break.

LEGS ARE INDEPENDENTLY BLOCKABLE (coordinator ruling, 2026-09-16). A SetupError means the
INSTRUMENT is wrong and aborts everything. A LegBlocked stops ONE leg: the others still run and
still report, the blocked leg is named with its reason, and the run exits 2 — because a leg that
could not run is not a leg that passed. C and D need nothing from W or S; W and S share one
precondition (a region whose config responds to the camera vertically) and are genuinely coupled
to each other, which the first live run demonstrated the hard way.

Usage:
    python3 tools/bg_vscroll_rate_witness.py [--rom s4.debug.bin] [--lst s4.debug.lst]
                                             [--skip-poke] [--json]
Exit: 0 every assertion held, every leg ran, AND every bound step is attributable · 1 an
assertion failed · 2 the instrument could not measure, one or more legs could not run (a refused
ROM poke, an act with no vertically responsive region, --skip-poke), OR a bound step has no
attributable cause — never rendered as a pass.

⚠ THE EXIT CODE AND THE PROSE MUST AGREE, and they did not once. A run printed "read the trace
before accepting this run" and exited 0. An exit code is what gets pasted into merge evidence, so
that combination tells a tired reader the opposite of what the words say. Anything this tool
believes must be read before acceptance now exits 2 AND prints the trace itself, and the word
PASS is not printed at all in that case.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient, BusError    # noqa: E402
from aether_instance import (AetherInstance, CartMismatch, SpawnError,  # noqa: E402
                             WrongServerError, read_bytes)
from raster_cost_probe import parse_lst   # noqa: E402
import region_table                       # noqa: E402

BOOT_MAX_FRAMES = 600
TICK_MAX_FRAMES = 8          # run_to ceiling for one logic tick (a lag tick spans two frames)
WARP_MAX_FRAMES = 240        # the warp tick alone: a synchronous window refill + plane redraw
LEG_MAX_TICKS = 900          # a ceiling on any one leg; running out is SETUP, never a skip
SETTLE_TICKS = 40            # ticks held after a jump before the value must have settled


class SetupError(Exception):
    """The INSTRUMENT is wrong — a missing symbol, a server that will not answer, a proc whose
    shape no longer matches the model. Nothing measured under it is worth reading, so it aborts
    the whole run. Exit 2 — never a pass and never a verdict."""


class LegBlocked(Exception):
    """ONE leg could not be run. Every other leg still runs and still reports; the blocked leg is
    named with its reason; the run still exits 2. A leg that could not run is not a leg that
    passed, and rendering it as one is the failure this whole tool exists to avoid."""


# ---- source-derived constants -------------------------------------------------------------

CONST_FILES = ("engine/level/parallax.emp", "engine/system/constants.emp",
               "games/sonic4/player/player_common.emp")
_CONST_RE = re.compile(r"^\s*(?:pub\s+)?const\s+([A-Za-z_]\w*)\s*=\s*([^\n]+)$", re.M)
# The expression may itself contain `/` (BG_VSCROLL_ROW_PX is PLANE_B_SPAN / PLANE_B_CELL_ROWS),
# so the trailing comment is stripped by the `//` pair, never by excluding the character.
_TRAILING_COMMENT = re.compile(r"\s*//.*$")


def _num(tok: str) -> str:
    """`$1F` -> `0x1F`, `%1010` -> `0b1010`, everything else untouched."""
    tok = re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", tok)
    return re.sub(r"%([01]+)", r"0b\1", tok)


def emp_consts(names: list[str]) -> dict[str, int]:
    """Resolve `const NAME = <expr>` across CONST_FILES, EVALUATING the expression so a derived
    constant (BG_VSCROLL_MAX_STEP = ROWS * ROW_PX) resolves the way the assembler folds it.

    Deliberately NOT a literal match: every number this witness asserts against has to move when
    the source moves it, and three of the four are derived in source today.
    """
    decls: dict[str, str] = {}
    dupes: dict[str, int] = {}
    for rel in CONST_FILES:
        txt = (AEON / rel).read_text()
        for m in _CONST_RE.finditer(txt):
            nm = m.group(1)
            expr = _TRAILING_COMMENT.sub("", m.group(2)).strip()
            if not expr:
                continue
            if nm in decls and decls[nm] != expr:
                dupes[nm] = dupes.get(nm, 1) + 1
            decls.setdefault(nm, expr)

    resolving: set[str] = set()

    def val(nm: str) -> int:
        if nm in dupes:
            raise SetupError(f"`const {nm}` is declared {dupes[nm]} different ways across "
                             f"{CONST_FILES} — this witness cannot tell which the build folded")
        if nm not in decls:
            raise SetupError(f"cannot find `const {nm}` in any of {CONST_FILES}")
        if nm in resolving:
            raise SetupError(f"`const {nm}` resolves through itself")
        resolving.add(nm)
        try:
            return _eval(decls[nm], val, nm)
        finally:
            resolving.discard(nm)

    return {n: val(n) for n in names}


def _eval(expr: str, val, who: str) -> int:
    try:
        tree = ast.parse(_num(expr), mode="eval")
    except SyntaxError as e:
        raise SetupError(f"`const {who} = {expr}` is not an expression this witness can "
                         f"evaluate ({e}) — teach emp_consts() or read it another way") from e

    def go(n):
        if isinstance(n, ast.Expression):
            return go(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return n.value
        if isinstance(n, ast.Name):
            return val(n.id)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = go(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = go(n.left), go(n.right)
            for t, f in ((ast.Add, lambda: a + b), (ast.Sub, lambda: a - b),
                         (ast.Mult, lambda: a * b), (ast.FloorDiv, lambda: a // b),
                         (ast.Div, lambda: a // b), (ast.LShift, lambda: a << b),
                         (ast.RShift, lambda: a >> b)):
                if isinstance(n.op, t):
                    return f()
        raise SetupError(f"`const {who} = {expr}` uses a form emp_consts() does not evaluate "
                         f"({ast.dump(n)[:60]}) — extend _eval or read the value another way")
    return go(tree)


def pcfg_offsets() -> dict[str, int]:
    """parallax_config's field offsets, from the struct's own trailing `// $XX` comments, with
    the comments cross-checked against the declared field ORDER (strictly increasing, and each
    gap at least the previous field's width). The comments are the only offsets this struct
    states; a witness that trusted them blindly would read a renamed field's bytes."""
    txt = (AEON / "engine/structs.emp").read_text()
    m = re.search(r"pub struct parallax_config\s*\{(.*?)^\}", txt, re.M | re.S)
    if not m:
        raise SetupError("cannot find `pub struct parallax_config` in engine/structs.emp")
    width = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}
    out: dict[str, int] = {}
    prev_off, prev_w = -1, 0
    for fm in re.finditer(r"^\s*(pcfg_\w+)\s*:\s*(\*?\w+)[^\n]*?//\s*\$([0-9A-Fa-f]+)",
                          m.group(1), re.M):
        nm, ty, off = fm.group(1), fm.group(2), int(fm.group(3), 16)
        w = 4 if ty.startswith("*") else width.get(ty)
        if w is None:
            raise SetupError(f"parallax_config.{nm} has type `{ty}`, which pcfg_offsets() does "
                             "not size — teach it before trusting any offset here")
        if off < prev_off + prev_w:
            raise SetupError(f"parallax_config's `// $XX` offsets are not consistent with its "
                             f"field order: {nm} is marked ${off:02X} but the field before it "
                             f"ends at ${prev_off + prev_w:02X}")
        out[nm] = off
        prev_off, prev_w = off, w
    for need in ("pcfg_v_factor_bg", "pcfg_v_center_y", "pcfg_v_offset", "pcfg_bob"):
        if need not in out:
            raise SetupError(f"parallax_config declares no `{need} ... // $XX` — the model "
                             "below would be reading guessed bytes")
    return out


def warp_consumer_shape_check(text: str | None = None) -> None:
    """Refuse to run if `Debug_Warp_Consume` no longer contains the second `Parallax_Update`.

    Leg W samples per INVOCATION precisely because a warp tick contains two of them — the
    consumer's own priming call plus the frame body's. That is a structural fact about the game's
    init ladder, and the moment it stops being true this witness's explanation of its own
    sampling choice becomes wrong. Cheap to pin, and the failure it prevents is a comment that
    confidently describes a mechanism that has gone.
    """
    rel = "games/sonic4/test/ojz_scroll_test.emp"
    # `text` exists so a test can feed DOCTORED source and prove this check is LIVE. Without it
    # the only assertion possible is "it does not raise on a good tree", which a check gutted to
    # look at nothing also satisfies — measured: a mutation emptying the loop below left the test
    # GREEN, which is a runner defect and not a pass (invariant 8c).
    txt = (AEON / rel).read_text() if text is None else text
    m = re.search(r"proc Debug_Warp_Consume\s*\(\)[^{]*\{(.*?)^\}", txt, re.M | re.S)
    if not m:
        raise SetupError(f"cannot find `proc Debug_Warp_Consume` in {rel}")
    body = re.sub(r"//[^\n]*", "", m.group(1))
    for want in (r"jbsr\s+Parallax_CheckBoundary", r"jbsr\s+Parallax_Update"):
        if not re.search(want, body):
            raise SetupError(
                f"Debug_Warp_Consume no longer contains /{want}/. Leg W samples per "
                "Parallax_Update invocation BECAUSE a warp tick runs two of them; if the "
                "consumer has stopped priming, re-read the path and update leg_step5's header "
                "before trusting leg W's granularity.")
    if not re.search(r"if DEBUG == 1 \{\s*jbsr\s+Debug_Warp_Consume", txt):
        raise SetupError(
            "GameState_OJZScroll_Update no longer calls Debug_Warp_Consume at its frame top, so "
            "a warp is no longer inside the same logic tick as the frame body — leg W's "
            "granularity argument rests on that and must be re-read.")


def step5_shape_check(text: str | None = None) -> None:
    """Refuse to model a Parallax_Step5_Vscroll whose clamp no longer reads the way clamp_model()
    transcribes it. The model is only as good as this match."""
    txt = (AEON / "engine/level/parallax.emp").read_text() if text is None else text
    m = re.search(r"proc Parallax_Step5_Vscroll\s*\(\)[^{]*\{(.*?)^\}", txt, re.M | re.S)
    if not m:
        raise SetupError("cannot find `proc Parallax_Step5_Vscroll` in engine/level/parallax.emp")
    body = re.sub(r"//[^\n]*", "", m.group(1))
    want = {
        "the region-derived ceiling":
            r"move\.w\s+#VSCROLL_BG_MAX,\s*d3\s+move\.l\s+Region_Current,\s*d0\s+beq",
        "the span read":
            r"move\.w\s+Region\.rg_bg_span\(a1\),\s*d0\s+beq",
        "the span-to-ceiling subtraction":
            r"subi\.w\s+#SCREEN_HEIGHT,\s*d3",
        "the low clamp":
            r"tst\.w\s+d2\s+bge\s+\.v_clamp_hi\s+moveq\s+#0,\s*d2",
        "the high clamp against the derived ceiling":
            r"cmp\.w\s+d3,\s*d2\s+ble\s+\.v_rate\s+move\.w\s+d3,\s*d2",
        "the rate clamp, on the STEP":
            r"move\.w\s+Parallax_Current_Vscroll_BG,\s*d0\s+sub\.w\s+d0,\s*d2\s+"
            r"cmp\.w\s+#BG_VSCROLL_MAX_STEP,\s*d2",
        "the rate clamp's low arm":
            r"cmp\.w\s+#-BG_VSCROLL_MAX_STEP,\s*d2\s+bge",
        "the re-add and the store":
            r"add\.w\s+d0,\s*d2\s+move\.w\s+d2,\s*Parallax_Current_Vscroll_BG",
    }
    for what, rx in want.items():
        if not re.search(rx, body):
            raise SetupError(f"Parallax_Step5_Vscroll no longer matches {what} as clamp_model() "
                             f"transcribes it (missing /{rx}/). Re-read the proc and update "
                             "clamp_model() before trusting any verdict here")


# ---- the model ----------------------------------------------------------------------------

def s16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def target_scroll(cam_y: int, cfg: dict) -> int:
    """`Parallax_Step5_Vscroll`'s target_b, transcribed:
         v_factor == 15 (the lock sentinel) -> v_offset
         else                                -> ((camY - v_center_y) >>a v_factor) + v_offset
    `asr` is an ARITHMETIC shift and Python's `>>` on a negative int floors the same way."""
    if cfg["v_factor"] == 15:
        return s16(cfg["v_offset"])
    d = s16(cam_y - cfg["v_center"])
    d = d >> cfg["v_factor"]
    return s16(d + cfg["v_offset"])


def clamp_pos(target: int, ceiling: int) -> int:
    """The POSITION half of the clamp alone — `clamp_model` without the rate arm."""
    return 0 if target < 0 else (ceiling if target > ceiling else target)


def why_it_bound(prev_src, src, v_prev, step_max):
    """WHY did the clamp bind on this step? Decomposed EXACTLY, not guessed.

    The gap the clamp had to close is `clamped_target_now - v_prev`, and it decomposes into three
    terms with no remainder:

        d_cfg      the target moved because the CONFIG changed  (same camera, new config)
        d_cam      the target moved because the CAMERA moved    (new camera, new config)
        backlog    the stored value was ALREADY behind the target before this step

        gap = d_cfg + d_cam + backlog          (identically)

    THIS EXISTS BECAUSE A GUESS WAS REFUTED. Leg D reported one bound step, classified by the
    first version of this code as "steady state" purely because the region/config pointers were
    equal ACROSS that one step. The coordinator's hypothesis was that a ratchet's later ticks get
    that label while the jump that caused them sits ticks earlier — which the old classifier
    could not tell apart, because comparing two adjacent samples cannot see a backlog. This can:
    a ratchet shows up as `backlog`, a crossing as `d_cfg`, and a camera that genuinely moved the
    target a long way as `d_cam`.

    THE TWO SURPRISING ANSWERS, and only these two block:
      * `camera` with the config UNCHANGED — at the shipped v_factor 3 a 16 px camera step is
        2 px of BG scroll, so a camera term over the bound contradicts the derivation;
      * `contradiction` — the value moved exactly the bound while the model says the target was
        already within reach. Impossible while A3 is green, which is why it deserves a name.
    `config`, `backlog` and `combined` are the clamp doing its job: a target that jumped at a
    crossing, the ratchet that follows one, and two ordinary terms adding up.
    """
    t_prev = clamp_pos(target_scroll(prev_src["cam_y"], prev_src["cfg"]), prev_src["ceiling"])
    t_mixed = clamp_pos(target_scroll(prev_src["cam_y"], src["cfg"]), src["ceiling"])
    t_now = clamp_pos(target_scroll(src["cam_y"], src["cfg"]), src["ceiling"])
    d_cfg, d_cam, backlog = t_mixed - t_prev, t_now - t_mixed, t_prev - v_prev
    cfg_same = (prev_src["cfg"] or {}).get("ptr") == (src["cfg"] or {}).get("ptr")
    terms = {"d_cfg": d_cfg, "d_cam": d_cam, "backlog": backlog}
    gap = t_now - v_prev
    big = [k for k, v in terms.items() if abs(v) > step_max]
    # THE DECOMPOSITION IS EXACT, so "no single term is big" is not a mystery — it is a SUM, and
    # calling it unexplained (as my first draft did) would have flagged ordinary arithmetic and
    # taught a reader to ignore the flag. The real contradiction is the other one: the value moved
    # exactly the bound while the model says the target was already within reach. That cannot
    # happen while A3 is green, which is precisely why it is worth a name and a blocker.
    if abs(gap) <= step_max:
        why = "contradiction"
    elif not big:
        why = "combined"
    else:
        why = {"d_cfg": "config", "d_cam": "camera",
               "backlog": "backlog"}[max(big, key=lambda k: abs(terms[k]))]
    return {"why": why, "cfg_unchanged": cfg_same, "gap": gap, **terms,
            "target_now": t_now, "target_prev": t_prev, "v_prev": v_prev,
            "cam": [prev_src["cam_y"], src["cam_y"]],
            "cfg": [hex((prev_src["cfg"] or {}).get("ptr", 0)),
                    hex((src["cfg"] or {}).get("ptr", 0))],
            "row": [prev_src["row"], src["row"]],
            # The two answers nobody may wave through: a bind the model says was unnecessary,
            # and a camera term over the bound with the config unchanged.
            "blocking": why == "contradiction" or (why == "camera" and cfg_same)}


def clamp_model(target: int, prev: int, ceiling: int, max_step: int) -> int:
    """The step-4 clamp, in order: position first (low then high), then the RATE on the step."""
    v = 0 if target < 0 else (ceiling if target > ceiling else target)
    d = v - prev
    d = max_step if d > max_step else (-max_step if d < -max_step else d)
    return prev + d


def ceiling_for(span: int, screen_h: int, vscroll_bg_max: int) -> int:
    """`rg_bg_span - SCREEN_HEIGHT`, or the act default when the row leaves the span at 0."""
    return vscroll_bg_max if span == 0 else s16(span - screen_h)


# ---- the emulator --------------------------------------------------------------------------

async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def rd(b, addr: int, n: int) -> int:
    return int(await read_bytes(b, addr, n), 16)


class Rig:
    def __init__(self, b, sym, rows, rom, K):
        self.b, self.sym, self.rows, self.rom, self.K = b, sym, rows, rom, K
        self.upd = sym["GameState_OJZScroll_Update"]
        self.tick_prev = None
        self.index = {r["addr"]: r["index"] for r in rows}
        self.by_addr = {r["addr"]: r for r in rows}
        self.span_override: dict[int, int] = {}   # row addr -> poked rg_bg_span (leg S)

    async def boot(self) -> None:
        await _c(self.b, "emulator/reset", {})
        for name in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update"):
            r = await _c(self.b, "emulator/run_to", {"addr": hex(self.sym[name]),
                                                     "maxFrames": BOOT_MAX_FRAMES})
            if not r.get("reached"):
                raise SetupError(f"run_to {name} never reached it: {r}")

    async def tick(self, max_frames: int = TICK_MAX_FRAMES) -> None:
        await _c(self.b, "emulator/step", {})
        r = await _c(self.b, "emulator/run_to", {"addr": hex(self.upd), "maxFrames": max_frames})
        if not r.get("reached"):
            raise SetupError(f"run_to GameState_OJZScroll_Update did not come round within "
                             f"{max_frames} frames: {r}")

    async def hold(self, buttons) -> None:
        await _c(self.b, "emulator/release_all", {})
        if buttons:
            await _c(self.b, "emulator/hold", {"buttons": list(buttons), "down": True})

    def config_at(self, ptr: int) -> dict | None:
        """The parallax_config at a ROM pointer, read out of the ROM IMAGE (configs are ROM)."""
        if not ptr or ptr + 0x20 > len(self.rom):
            return None
        o = self.K["pcfg"]
        g = lambda off, n: int.from_bytes(self.rom[ptr + off:ptr + off + n], "big")  # noqa: E731
        return {"ptr": ptr,
                "v_factor": g(o["pcfg_v_factor_bg"], 1),
                "v_center": g(o["pcfg_v_center_y"], 2),
                "v_offset": g(o["pcfg_v_offset"], 2),
                "bob": g(o["pcfg_bob"], 1)}

    async def sample(self, tag: str) -> dict:
        b, sym = self.b, self.sym
        cam_x = (await rd(b, sym["Camera_X"], 4)) >> 16
        cam_y = (await rd(b, sym["Camera_Y"], 4)) >> 16
        region = await rd(b, sym["Region_Current"], 4)
        frames = await rd(b, sym["Parallax_Transition_Frames"], 1)
        cur = await rd(b, sym["Parallax_Current_Config"], 4)
        tgt = await rd(b, sym["Parallax_Target_Config"], 4)
        row = self.by_addr.get(region)
        span = self.span_override.get(region, row["bg_span"] if row else 0)
        lt = await rd(b, sym["Logic_Tick"], 4)
        dtick = None if self.tick_prev is None else lt - self.tick_prev
        self.tick_prev = lt
        return {"tag": tag, "logic_tick": lt, "dtick": dtick,
                "cam_x": cam_x, "cam_y": cam_y,
                "centre": (cam_x + self.K["HALF_W"], cam_y + self.K["HALF_H"]),
                "v": s16(await rd(b, sym["Parallax_Current_Vscroll_BG"], 2)),
                "region": region, "row": self.index.get(region),
                "span": span,
                "ceiling": ceiling_for(span, self.K["SCREEN_HEIGHT"], self.K["VSCROLL_BG_MAX"]),
                "trans": frames,
                # Parallax_Active_Config's rule: mid-transition the TARGET config is active for
                # every structural decision; outside one it is Current.
                "cfg": self.config_at(tgt if frames else cur),
                "lag": await rd(b, sym["Lag_Frame_Count"], 4)}


def candidate_window(r, K, cam_x_max, cam_y_max):
    """The geometry half of `plan_vertical_leg`'s per-row decision, PURE so it can be tested
    without an emulator (tools/test_bg_vscroll_rate_aim.py does, against the real act table).

    Returns (record, probe_camera_x, cam_y_lo, cam_y_hi). The record carries a "verdict" key ONLY
    when the row is rejected on geometry alone; a row that survives has no verdict yet and still
    has to be probed for its live config.

    THE WINDOW IS THE CAMERA'S, NOT THE ROW'S. `Region_Resolve` tests the camera CENTRE, so the
    camera Ys whose centre lies inside the row are [y0 - HALF_H, y1 - HALF_H] — intersected with
    the engine's own clamp [0, Camera_Y_Max], which is why a row at the act's floor can have a
    legal rectangle and no travel at all.
    """
    half_w, half_h = K["HALF_W"], K["HALF_H"]
    cy_lo = max(0, r["y0"] - half_h)
    cy_hi = min(cam_y_max, r["y1"] - half_h)
    cx = min(max((r["x0"] + r["x1"]) // 2 - half_w, 0), cam_x_max)
    rec = {"row": r["index"], "x": [r["x0"], r["x1"]], "y": [r["y0"], r["y1"]],
           "probe_x": cx + half_w, "cam_y": [cy_lo, cy_hi]}
    if cy_hi - cy_lo < 1:
        rec["verdict"] = ("REJECTED: no camera-Y travel with the centre inside this row "
                          f"(window {cy_lo}..{cy_hi} against Camera_Y_Max {cam_y_max})")
    elif not r["x0"] <= cx + half_w <= r["x1"]:
        rec["verdict"] = ("REJECTED: the camera cannot centre inside this row's X span "
                          f"(best centre {cx + half_w} against Camera_X_Max {cam_x_max})")
    return rec, cx, cy_lo, cy_hi


def jump_verdict(rec, cfg, cy_lo, cy_hi, step_max):
    """The arithmetic half of the same decision, PURE for the same reason. Writes rec["verdict"]
    and returns the derived jump.

    THE LOCK ARM IS NAMED, NOT LUMPED IN WITH "too small". A config at pcfg_v_factor_bg == 15 has
    a jump of exactly 0 however far the camera travels, and that is `Parallax_Step5_Vscroll`'s
    documented lock sentinel behaving correctly — not a modelling failure and not a marginal
    region. A reader who sees "0 px over 2047 px of camera" needs to be told which of those two
    it is, because the fixes are opposite: re-aim, or fix the model.
    """
    jump = abs(target_scroll(cy_hi, cfg) - target_scroll(cy_lo, cfg))
    rec["derived_jump"] = jump
    if cfg["v_factor"] == 15:
        rec["verdict"] = (
            "REJECTED: this region's config is the VERTICAL LOCK sentinel "
            f"(pcfg_v_factor_bg == 15), so its BG scroll is pinned to v_offset "
            f"{s16(cfg['v_offset'])} and does not respond to the camera at all. The jump of "
            f"{jump} here is CORRECT, not a modelling failure.")
    elif jump <= 2 * step_max:
        rec["verdict"] = (f"REJECTED: derived jump {jump} px over camera Y {cy_lo}..{cy_hi} "
                          f"does not exceed 2 * {step_max} = {2 * step_max}, so the rate clamp "
                          "could not be forced to the bound for two consecutive ticks")
    else:
        rec["verdict"] = "CHOSEN"
    return jump


async def warp_to(b, sym, rig: "Rig", x: int, y: int, tick: bool = True) -> None:
    """Fill the DEBUG warp mailbox and (by default) spend the one long tick that consumes it.
    `tick=False` leaves the mailbox armed for a caller that wants to sample the pre-warp frame
    first — leg W does, because the step ACROSS the warp is the one A1 is about."""
    for nm, v, w in (("Warp_Req_X", x, 2), ("Warp_Req_Y", y, 2), ("Warp_Req_Flag", 1, 1)):
        await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
    if tick:
        await rig.tick(WARP_MAX_FRAMES)


async def plan_vertical_leg(rig: "Rig", b, sym, rows, K, cam_x_max, cam_y_max, step_max, report):
    """Choose the region legs W and S run in, FROM THE ACT'S OWN TABLE.

    WHY THIS EXISTS, and it is a defect this tool shipped with (found on its first live run,
    2026-09-16). Leg W used to take its column from `Camera_X` as the earlier legs happened to
    leave it — `wx = here["cam_x"] + HALF_W` — under a comment that said "derived, not picked".
    That was true of the y endpoints and FALSE of the x. Worse, it read the ACTIVE CONFIG at that
    inherited position while taking the y endpoints from `region_at(rows, wx, 0)`, a DIFFERENT
    row. On OJZ act 1 the earlier legs end at the bottom-right, in a region whose config is the
    vertical LOCK (`pcfg_v_factor_bg == 15`), so the derived jump came out 0 px over 2047 px of
    camera travel and the leg refused. The refusal was right; the aim was not, and neither was
    the mixture of two rows' facts in one calculation.

    ⚠ THE 0 WAS NOT A MODELLING BUG, and that had to be settled before re-aiming — re-aiming
    first would have hidden one behind a passing leg. `target_scroll` transcribes
    `Parallax_Step5_Vscroll`'s `cmpi.b #15 / beq .v_locked` arm: at v_factor 15 the BG scroll IS
    `v_offset`, camera-independent, by design. A jump of 0 there is the correct answer about a
    correctly-modelled region. Verified against the act's own table at this pin: four rows author
    v_factor 15, every other row resolves to a config with v_factor 3, and
    tools/test_bg_vscroll_rate_aim.py pins that the population contains both kinds.

    WHAT THIS DOES INSTEAD. Walk the act's rows in table order. For each, compute the camera-Y
    window whose CENTRE lies inside the row (intersected with the engine's own `Camera_Y_Max`
    clamp) and a probe column at the row's middle (clamped to `Camera_X_Max`), warp there, and
    then ASK THE ENGINE which parallax config is live — `Parallax_Current_Config` /
    `Parallax_Target_Config`, read out of RAM. `Effects_ResolveParallax`'s three rungs are NOT
    restated here; a second private answer to that question is the defect the regions work exists
    to delete, and a witness that restated it could disagree with the engine and call that a pass.

    Returns the first row whose derived jump exceeds `2 * step_max`, with the scan recorded. If
    none does, raises LegBlocked naming EVERY candidate and why it was rejected — because "this
    act has no vertically responsive region wide enough to force the clamp" is a real finding
    about the act, and it should read as one rather than as a tool that gave up.
    """
    scan: list[dict] = []
    for r in rows:
        rec, cx, cy_lo, cy_hi = candidate_window(r, K, cam_x_max, cam_y_max)
        scan.append(rec)
        if "verdict" in rec:
            continue
        await warp_to(b, sym, rig, rec["probe_x"], cy_lo + K["HALF_H"])
        flag = await rd(b, sym["Warp_Req_Flag"], 1)
        s = await rig.sample(f"probe{r['index']}")
        if flag:
            rec["verdict"] = f"REJECTED: Warp_Req_Flag still {flag} — the warp was not consumed"
            continue
        if s["region"] != r["addr"]:
            rec["verdict"] = (f"REJECTED: the warp landed with Region_Current on row {s['row']}, "
                              f"not this one (camera centre {s['centre']})")
            continue
        if s["cfg"] is None:
            rec["verdict"] = "REJECTED: no parallax_config is live after the warp"
            continue
        cfg = s["cfg"]
        rec.update({"cfg": hex(cfg["ptr"]), "v_factor": cfg["v_factor"],
                    "v_center": s16(cfg["v_center"]), "v_offset": s16(cfg["v_offset"]),
                    "landed_cam_y": s["cam_y"]})
        jump = jump_verdict(rec, cfg, cy_lo, cy_hi, step_max)
        if rec["verdict"] != "CHOSEN":
            continue
        report["W_scan"] = scan
        report["W_scan_unprobed"] = [x["index"] for x in rows[r["index"] + 1:]]
        return {"row": r, "x": rec["probe_x"], "cam_y_lo": cy_lo, "cam_y_hi": cy_hi,
                "cfg": cfg, "jump": jump}
    report["W_scan"] = scan
    report["W_scan_unprobed"] = []
    raise LegBlocked(
        "NO REGION IN THIS ACT CAN FORCE THE RATE CLAMP, and that is a finding about the act, "
        f"not a tool failure. All {len(rows)} rows were probed and every one was rejected:\n  "
        + "\n  ".join(f"row {x['row']} {x['x']}x{x['y']}: {x['verdict']}" for x in scan)
        + f"\nA qualifying row needs a config with pcfg_v_factor_bg != 15 and a derived target "
          f"jump over 2 * {step_max} = {2 * step_max} px across the camera-Y travel available "
          "inside its own rectangle.")


async def leg_step5(rig: Rig, tag: str, n: int, max_frames: int):
    """Sample at PARALLAX_STEP5 granularity instead of per logic tick — i.e. once per invocation
    of the routine that owns the clamp.

    WHY THIS EXISTS (measured 2026-09-16, the third live run). Leg W reported a 32 px step on its
    warp tick and A1/A3 went red. 32 is exactly 2 x BG_VSCROLL_MAX_STEP, and the unclamped target
    was 177 — so a bypassed clamp would have landed on 177, not on precisely double the bound.
    The cause is in the ENGINE'S SHAPE, not in the clamp: `Debug_Warp_Consume` runs at the TOP of
    `GameState_OJZScroll_Update` and ends with `jbsr Parallax_CheckBoundary` + `jbsr
    Parallax_Update` ("the final Parallax_Update primes HScroll/VSRAM"), and then the SAME frame's
    normal body runs both again. So a warp tick contains TWO Parallax_Update calls, two correctly
    clamped 16 px stores, and a rig that samples once per tick attributes both to one tick.

    THE ARITHMETIC CONSERVES, which is the decisive check and it uses the failing run's own
    numbers: target 177, observed 0 -> 32, then NINE consecutive ticks at exactly 16 = 144.
    32 + 144 = 176, and the last tick takes the remaining 1. Every pixel is accounted for and
    none is skipped. A bypass does not produce a run of nine.

    SO THE FIX IS IN THE SAMPLING, AND IT TIGHTENS RATHER THAN LOOSENS. The clamp's guarantee is
    per INVOCATION, not per tick; a per-tick bound follows from it but is weaker. This samples the
    thing the clamp actually bounds. A1 was NOT relaxed to admit 32 on the first tick — that is
    the shape that produces a gate which passes because it was taught to.

    HOW IT READS THE STORES. It stops at `Parallax_Step5_Vscroll`'s ENTRY, where
    `Parallax_Current_Vscroll_BG` still holds what the PREVIOUS invocation stored. So consecutive
    entries are consecutive STORES, and the delta between two of them is exactly one clamped step.
    The camera read at entry k is the one invocation k is about to use, which is why the model
    arm pairs `v[k+1]` with `cam[k]` — see `check_leg(granularity="step5")`.
    """
    addr = hex(rig.sym["Parallax_Step5_Vscroll"])
    out = []
    for i in range(n):
        r = await _c(rig.b, "emulator/run_to", {"addr": addr, "maxFrames": max_frames})
        if not r.get("reached"):
            raise LegBlocked(f"leg `{tag}` did not reach Parallax_Step5_Vscroll within "
                             f"{max_frames} frames on sample {i}: {r}")
        out.append(await rig.sample(f"{tag}{i}"))
        await _c(rig.b, "emulator/step", {})       # off the entry so the next run_to advances
    return out


async def leg(rig: Rig, tag: str, buttons, ticks: int, first_tick_frames: int | None = None):
    await rig.hold(buttons)
    out = [await rig.sample(f"{tag}0")]
    for i in range(1, ticks + 1):
        await rig.tick(first_tick_frames if (i == 1 and first_tick_frames) else TICK_MAX_FRAMES)
        out.append(await rig.sample(f"{tag}{i}"))
    await rig.hold(None)
    return out


async def leg_until(rig: Rig, tag: str, buttons, done, margin: int):
    """Hold until done(sample) has held for `margin` more ticks. Running out is SETUP."""
    await rig.hold(buttons)
    out, since = [await rig.sample(f"{tag}0")], None
    for i in range(1, LEG_MAX_TICKS):
        await rig.tick()
        s = await rig.sample(f"{tag}{i}")
        out.append(s)
        if done(s):
            since = i if since is None else since
            if i - since >= margin:
                await rig.hold(None)
                return out
    await rig.hold(None)
    raise SetupError(f"leg `{tag}` ran {LEG_MAX_TICKS} ticks without arriving (last centre "
                     f"{out[-1]['centre']}, v={out[-1]['v']}) — the route has gone stale")


# ---- the verdict ---------------------------------------------------------------------------

def check_leg(fails: list[str], K: dict, name: str, samples: list[dict],
              granularity: str = "tick") -> dict:
    """A1 + A2 + A3 over one leg. Returns the leg's summary row.

    GRANULARITY is not cosmetic. "tick" samples once per logic tick at the game-state Update
    entry; "step5" samples once per `Parallax_Step5_Vscroll` invocation, which is what the clamp
    actually bounds. They differ on exactly one path and it is a real one: a DEBUG warp tick runs
    Parallax_Update TWICE (Debug_Warp_Consume's own call at the frame top, then the frame body's),
    so a per-tick sample sees two clamped stores as one step. See `leg_step5`.

    In "tick" mode every interval MUST be exactly one logic tick, and the leg is blocked if not —
    every per-tick assertion here assumes it, and a lag tick or a missed Update entry would make
    A1 read a multi-tick move as a single step. That guard is why the two cases above can be told
    apart by data rather than by argument.
    """
    step_max = K["BG_VSCROLL_MAX_STEP"]
    unit = "tick" if granularity == "tick" else "invocation"
    if granularity == "tick":
        bad = [(i, s["dtick"]) for i, s in enumerate(samples)
               if i and s["dtick"] is not None and s["dtick"] != 1]
        if bad:
            raise LegBlocked(
                f"{len(bad)} sample interval(s) in this leg are not exactly one logic tick "
                f"({bad[:6]}), so every per-tick assertion here would be measuring something "
                "other than a tick. Blocked rather than reported: a multi-tick interval read as "
                "one step is precisely how a working clamp looks broken.")
    steps, worst, binds, bound_at = [], 0, 0, []
    blocking: list[dict] = []
    for i in range(1, len(samples)):
        d = samples[i]["v"] - samples[i - 1]["v"]
        steps.append(d)
        worst = max(worst, abs(d))
        if abs(d) == step_max:
            binds += 1
            # WHY IT BOUND, DECOMPOSED EXACTLY rather than inferred from two adjacent pointers.
            # The first version of this compared samples[i-1] and samples[i] for a region/config
            # change and called everything else "steady state"; that cannot see a BACKLOG, so a
            # ratchet's later steps were labelled steady-state and the label was off by the
            # length of the ratchet. See why_it_bound().
            src_i = samples[i] if granularity == "tick" else samples[i - 1]
            src_h = samples[i - 1] if granularity == "tick" else (
                samples[i - 2] if i >= 2 else None)
            if src_h is None or src_i["cfg"] is None or src_h["cfg"] is None:
                bound_at.append({"i": i, "why": "unmodelled",
                                 "note": "no config or no earlier sample to decompose against",
                                 "blocking": False})
            else:
                w = why_it_bound(src_h, src_i, samples[i - 1]["v"], step_max)
                w["i"] = i
                bound_at.append(w)
                if w["blocking"]:
                    lo, hi = max(0, i - 3), min(len(samples), i + 4)
                    blocking.append({
                        "leg": name, "i": i, "why": w["why"], "decomposition": w,
                        # THE TRACE, DUMPED. The old code printed "read the trace before
                        # accepting this run" and exited 0 — telling a tired reader the opposite
                        # of what the exit code said. It now carries the trace itself.
                        "trace": [{k: s[k] for k in ("tag", "v", "cam_y", "row", "region",
                                                     "trans", "ceiling", "dtick")}
                                  for s in samples[lo:hi]]})
        if abs(d) > step_max:                                              # A1
            fails.append(f"A1 {name}: {unit} {i} moved Parallax_Current_Vscroll_BG by {d} px "
                         f"({samples[i-1]['v']} -> {samples[i]['v']}), past BG_VSCROLL_MAX_STEP "
                         f"= {step_max}. Camera Y {samples[i-1]['cam_y']} -> "
                         f"{samples[i]['cam_y']}, region row {samples[i]['row']}"
                         + (f", dtick {samples[i]['dtick']}" if granularity == "tick" else ""))
    for i, s in enumerate(samples):                                        # A2
        if not 0 <= s["v"] <= s["ceiling"]:
            fails.append(f"A2 {name}: sample {i} has Parallax_Current_Vscroll_BG = {s['v']}, "
                         f"outside [0, {s['ceiling']}] — the ceiling derived from region row "
                         f"{s['row']}'s rg_bg_span = {s['span']} "
                         f"({'the act default' if s['span'] == 0 else 'authored'})")
    modelled = mismatched = 0
    for i in range(1, len(samples)):                                       # A3
        a, s = samples[i - 1], samples[i]
        # WHICH CAMERA PRODUCED THIS STORE depends on the granularity, and getting it backwards
        # would model the wrong frame. Per TICK: the value at tick i was computed from the camera
        # as it stood at the end of tick i-1, which is the camera sampled at tick i's entry — so
        # pair v[i] with cam[i]. Per INVOCATION: the entry sample reads the PREVIOUS invocation's
        # store, and the camera it reads is the one THIS invocation is about to use — so v[i]
        # pairs with cam[i-1].
        src = s if granularity == "tick" else a
        if s["trans"] or a["trans"] or src["cfg"] is None:
            continue           # the lerp arm and a config this witness cannot read: rate only
        if src["cfg"]["bob"]:
            raise SetupError(f"the active parallax_config at {src['cfg']['ptr']:#x} authors a "
                             f"bob (pcfg_bob = {src['cfg']['bob']:#04x}); target_scroll() does "
                             "not model the sine term. Teach it before trusting any verdict here")
        modelled += 1
        want = clamp_model(target_scroll(src["cam_y"], src["cfg"]), a["v"], src["ceiling"],
                           step_max)
        if want != s["v"]:
            mismatched += 1
            if mismatched <= 3:
                fails.append(
                    f"A3 {name}: {unit} {i}: Parallax_Current_Vscroll_BG is {s['v']}, the clamp "
                    f"model says {want}. camY {src['cam_y']}, config {src['cfg']['ptr']:#x} "
                    f"(v_factor {src['cfg']['v_factor']}, v_center {s16(src['cfg']['v_center'])},"
                    f" v_offset {s16(src['cfg']['v_offset'])}) -> target "
                    f"{target_scroll(src['cam_y'], src['cfg'])}; previous {a['v']}, ceiling "
                    f"{src['ceiling']} (row {src['row']}, span {src['span']})")
    return {"leg": name, "granularity": granularity, "bound_at": bound_at,
            "blocking_observations": blocking,
            "bound_by": {k: sum(1 for x in bound_at if x.get("why") == k)
                         for k in ("config", "camera", "backlog", "combined",
                                   "contradiction", "unmodelled")},
            "ticks": len(samples) - 1, "v_first": samples[0]["v"],
            "v_last": samples[-1]["v"], "v_min": min(s["v"] for s in samples),
            "v_max": max(s["v"] for s in samples), "worst_step": worst,
            "ticks_at_the_bound": binds, "modelled_ticks": modelled,
            "model_mismatches": mismatched,
            "rows_visited": sorted({s["row"] for s in samples}, key=lambda r: (r is None, r)),
            "steps": steps}


def longest_run_at(steps: list[int], mag: int) -> int:
    best = run = 0
    for d in steps:
        run = run + 1 if abs(d) == mag else 0
        best = max(best, run)
    return best


async def run(args) -> int:
    K = emp_consts(["BG_VSCROLL_MAX_STEP", "BG_VSCROLL_ROW_PX", "BG_VSCROLL_MAX_STEP_ROWS",
                    "VSCROLL_BG_MAX", "SCREEN_HEIGHT", "PLANE_B_SPAN", "PLANE_B_CELL_ROWS",
                    "PARALLAX_LERP_SHIFT", "CAM_SCREEN_HALF_W", "CAM_SCREEN_HALF_H",
                    "PLAYER_DEBUG_FLY_SPEED"])
    K["HALF_W"], K["HALF_H"] = K["CAM_SCREEN_HALF_W"], K["CAM_SCREEN_HALF_H"]
    K["pcfg"] = pcfg_offsets()
    step5_shape_check()
    warp_consumer_shape_check()
    step_max = K["BG_VSCROLL_MAX_STEP"]

    sym = parse_lst(args.lst)
    for need in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update",
                 "Camera_X", "Camera_Y", "Camera_X_Max", "Camera_Y_Max", "Region_Current",
                 "Parallax_Current_Vscroll_BG", "Parallax_Current_Config",
                 "Parallax_Target_Config", "Parallax_Transition_Frames",
                 "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Logic_Tick",
                 "Lag_Frame_Count", "OJZ_Act1_Descriptor", "Parallax_Step5_Vscroll"):
        if need not in sym:
            raise SetupError(f"symbol {need} is not in {args.lst} — this witness needs the "
                             "sonic4 DEBUG listing")
    rom = Path(args.rom).read_bytes()
    try:
        rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])
    except region_table.LayoutError as e:
        raise SetupError(str(e)) from e

    report: dict = {"constants": {k: v for k, v in K.items() if isinstance(v, int)},
                    "rows": [{k: (hex(v) if k in ("addr", "effects", "parallax", "bg_layout")
                                  else v) for k, v in r.items()} for r in rows]}
    fails: list[str] = []
    findings: list[str] = []

    # ---- R0: the premise, and the vacuity warning -----------------------------------------
    authored = [r for r in rows if r["bg_span"]]
    report["rows_with_authored_span"] = [r["index"] for r in authored]
    if not authored:
        findings.append(
            f"R0: all {len(rows)} region rows in this ROM leave rg_bg_span at 0, so the position "
            f"clamp takes its VSCROLL_BG_MAX = {K['VSCROLL_BG_MAX']} fallback on EVERY frame. "
            "Legs C/D/W below would pass identically with step 4's position change reverted — "
            "leg S (the ROM poke) is the only thing here that tests it.")
    else:
        findings.append(f"R0: {len(authored)} of {len(rows)} region rows author an rg_bg_span "
                        f"({[(r['index'], r['bg_span']) for r in authored]}), so legs C/D/W do "
                        "exercise the region path where the camera is inside those rows.")

    inst = AetherInstance(args.rom, symbols=args.lst)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise SetupError(str(e)) from e
    b = BusClient(socket_path=sock, client_id="bgvscrollrate", client_name="bg_vscroll_rate_witness")
    try:
        await b.connect()
        for m in ("emulator/step", "emulator/run_to", "emulator/hold", "emulator/release_all",
                  "emulator/write_memory", "emulator/read_memory"):
            if not b.supports(m):
                raise SetupError(f"the server does not advertise `{m}`")
        await _c(b, "emulator/load_symbols", {"path": args.lst})
        rig = Rig(b, sym, rows, rom, K)
        await rig.boot()
        for _ in range(3):
            await rig.tick()
        s0 = await rig.sample("spawn")
        report["spawn"] = {"centre": s0["centre"], "v": s0["v"], "row": s0["row"],
                           "cfg": None if s0["cfg"] is None else hex(s0["cfg"]["ptr"])}

        # ---- the legs, each INDEPENDENTLY BLOCKABLE (coordinator ruling 2026-09-16) ----
        #
        # A `SetupError` still aborts the whole run: it means the INSTRUMENT is wrong, and nothing
        # measured under it is worth reading. A `LegBlocked` aborts ONE leg. The leg is reported
        # by name with its reason, every other leg still runs and still reports, and the run still
        # exits 2 — a leg that could not run is not a leg that passed.
        #
        # WHY THAT IS THE RIGHT SPLIT AND NOT SIMPLY MORE OUTPUT: C and D measure A1/A2/A3 over
        # ordinary motion and need nothing from W or S. W and S share ONE precondition — a region
        # whose parallax config actually responds to the camera vertically — so they are genuinely
        # coupled to each other and to nothing else. The first live run proved that coupling
        # matters: the bottom-right region is vertically LOCKED, and a leg planned from wherever
        # the camera happened to stop inherits that.
        cam_x_max = await rd(b, sym["Camera_X_Max"], 2)
        cam_y_max = await rd(b, sym["Camera_Y_Max"], 2)
        report["camera_max"] = {"x": cam_x_max, "y": cam_y_max}
        blocked: list[tuple[str, str]] = []

        async def run_leg(name, body):
            # A `BusError` is classified here and NOT allowed to escape as a traceback. Measured
            # 2026-09-16: the Rust core refuses every write outside $E00000-$FFFFFF, so leg S's
            # ROM poke raised `[-32004] only the work-RAM window is writable` BEFORE its readback
            # guard could run, and a designed-for refusal arrived as a Python stack. That is the
            # one shape this tool's whole vocabulary exists to prevent: a reader could not tell
            # whether the instrument had broken or the subject had.
            try:
                await body()
            except LegBlocked as e:
                blocked.append((name, str(e)))
                report[name] = {"could_not_run": str(e)}
            except BusError as e:
                why = (f"the bus refused a call this leg needs: {e}. Classified rather than "
                       "raised, so the run still reports every other leg — but it is COULD NOT "
                       "RUN, never a pass.")
                blocked.append((name, why))
                report[name] = {"could_not_run": why}

        # ---- leg C: the crossing route, right across the whole region table ---------------
        # Hold RIGHT from the spawn until the camera stops moving. The stop test is
        # `Camera_X >= Camera_X_Max` and NOT "the centre passed the last row's x1": the camera is
        # clamped to act_width - SCREEN_WIDTH, so its centre tops out SCREEN_WIDTH/2 px SHORT of
        # the act's right edge and an x1 test would spin for LEG_MAX_TICKS.
        async def _legC():
            legC = await leg_until(rig, "C", ["right"], lambda s: s["cam_x"] >= cam_x_max, 8)
            report["C"] = check_leg(fails, K, "C (crossing route, held RIGHT)", legC)
            report["C"]["camera_x_max"] = cam_x_max
            if len(report["C"]["rows_visited"]) < 2:
                raise LegBlocked(
                    f"it crossed no region boundary: it stayed in row(s) "
                    f"{report['C']['rows_visited']} for its whole traversal to Camera_X_Max = "
                    f"{cam_x_max}. A green over one region says nothing about a crossing.")
        await run_leg("C", _legC)

        # ---- leg D: "the shaft fall" — held DOWN in free flight, the camera's own ceiling --
        async def _legD():
            legD = await leg_until(rig, "D", ["down"], lambda s: s["cam_y"] >= cam_y_max, 8)
            report["D"] = check_leg(fails, K, "D (descent, held DOWN)", legD)
            report["D"]["camera_y_max"] = cam_y_max
            report["D"]["fly_speed_px_per_frame"] = K["PLAYER_DEBUG_FLY_SPEED"]
            findings.append(
                f"D: the descent at PLAYER_DEBUG_FLY_SPEED = {K['PLAYER_DEBUG_FLY_SPEED']} "
                f"px/frame (the camera's own per-frame ceiling — see the header) moved the BG "
                f"scroll by at most {report['D']['worst_step']} px in a tick against a bound of "
                f"{step_max}. "
                + (f"The clamp never bound, which is the expected NEGATIVE CONTROL: it does "
                   "not fire in ordinary play."
                   if not report["D"]["bound_at"] else
                   f"It bound {len(report['D']['bound_at'])} time(s), attributed by exact "
                   f"decomposition (see why_it_bound): {report['D']['bound_by']}. `config` and "
                   "`backlog` are the clamp doing its job — a target that jumped at a crossing, "
                   "and the ratchet that follows it. `camera` with the config unchanged and "
                   "`unexplained` are the two that contradict the derivation, because the "
                   f"shipped v_factor turns a {K['PLAYER_DEBUG_FLY_SPEED']} px/frame camera "
                   "into a few px of BG scroll — and either of those makes this run exit 2 with "
                   "the surrounding trace PRINTED, not exit 0 with advice to go and read it."))
        await run_leg("D", _legD)

        # ---- the shared precondition for W and S: a vertically RESPONSIVE region ----------
        plan = None

        async def _plan():
            nonlocal plan
            plan = await plan_vertical_leg(rig, b, sym, rows, K, cam_x_max, cam_y_max,
                                           step_max, report)
            findings.append(
                f"W/S aim: region row {plan['row']['index']} "
                f"[{plan['row']['x0']}..{plan['row']['x1']}]x[{plan['row']['y0']}.."
                f"{plan['row']['y1']}] at x={plan['x']}, camera Y {plan['cam_y_lo']}.."
                f"{plan['cam_y_hi']}, config {plan['cfg']['ptr']:#x} "
                f"(v_factor {plan['cfg']['v_factor']}, v_center {s16(plan['cfg']['v_center'])}, "
                f"v_offset {s16(plan['cfg']['v_offset'])}) -> derived target jump "
                f"{plan['jump']} px, needs > {2 * step_max}. Chosen from the act's own table, "
                "not inherited from wherever the earlier legs left the camera.")
        await run_leg("W_plan", _plan)

        # ---- leg W: the rate DISCRIMINATOR — a DEBUG warp that must ratchet ---------------
        async def _legW():
            if plan is None:
                raise LegBlocked("no region qualified for the vertical legs — see W_plan.")
            half_h = K["HALF_H"]
            wx, y_top, y_bot = plan["x"], plan["cam_y_lo"] + half_h, plan["cam_y_hi"] + half_h
            await warp_to(b, sym, rig, wx, y_top)
            for _ in range(SETTLE_TICKS):
                await rig.tick()
            await warp_to(b, sym, rig, wx, y_bot, tick=False)
            # PER INVOCATION, NOT PER TICK — see leg_step5's header. The warp tick runs
            # Parallax_Update twice, so per-tick sampling reports two clamped stores as one
            # 32 px step and A1 goes red on a clamp that is working. Enough samples to cover
            # the whole ratchet with margin: one store per BG_VSCROLL_MAX_STEP of the jump.
            n = plan["jump"] // step_max + 8
            legW = await leg_step5(rig, "W", n, WARP_MAX_FRAMES)
            flag = await rd(b, sym["Warp_Req_Flag"], 1)
            if flag:
                raise LegBlocked(
                    f"Warp_Req_Flag is still {flag} after the warp tick — the warp never "
                    "happened, and a warp that never happened looks exactly like a warp that "
                    "changed nothing.")
            report["W"] = check_leg(fails, K, "W (warp ratchet, per Parallax_Update)", legW,
                                    granularity="step5")
            report["W"].update({"x": wx, "from_player_y": y_top, "to_player_y": y_bot,
                                "samples_requested": n,
                                "logic_ticks_spanned": legW[-1]["logic_tick"]
                                                       - legW[0]["logic_tick"],
                                "derived_target_jump": plan["jump"],
                                "needs_more_than": 2 * step_max})
            run_at_bound = longest_run_at(report["W"]["steps"], step_max)
            report["W"]["longest_run_at_the_bound"] = run_at_bound
            if run_at_bound < 2:                                               # A4
                fails.append(
                    f"A4: after a warp whose derived target jump is {plan['jump']} px "
                    f"(> 2 * {step_max}), the longest run of consecutive INVOCATIONS stepping "
                    f"exactly {step_max} px is {run_at_bound}. The rate clamp did not bind, so "
                    f"leg W's green is vacuous and A1 is untested. Steps: "
                    f"{report['W']['steps'][:12]}")
            else:
                # THE CONSERVATION CHECK, reported beside the run because it is what separates
                # "the clamp bound" from "the clamp was skipped and the numbers happen to look
                # tidy": the ratchet's total travel must equal the derived jump, give or take the
                # final partial step. A bypass reaches the target in one store and has no run.
                travel = legW[-1]["v"] - legW[0]["v"]
                findings.append(
                    f"A4: the warp forced the rate clamp to the bound for {run_at_bound} "
                    f"consecutive Parallax_Update invocations at exactly {step_max} px — this is "
                    "the leg that is red with the rate clamp reverted. Conservation: the ratchet "
                    f"travelled {travel} px over {len(legW) - 1} invocations "
                    f"({report['W']['logic_ticks_spanned']} logic ticks) against a derived jump "
                    f"of {plan['jump']}; every pixel is accounted for and none skipped.")
        await run_leg("W", _legW)

        # ---- leg S: the position DISCRIMINATOR — a PATCHED ROM, not a live poke ----------
        #
        # ⚠ THE LIVE POKE IS DEAD, MEASURED. The Rust core refuses every write outside the
        # work-RAM window: `[-32004] 0x00018AC8: only the work-RAM window ($E00000-$FFFFFF) is
        # writable; ROM and I/O writes are refused`. $18AC8 is inside OJZ act 1's region table,
        # which is ROM. So this leg patches `rg_bg_span` in a COPY OF THE ROM ON DISK and boots
        # that, in its own emulator instance.
        #
        # WHY THAT IS BETTER EVIDENCE AND NOT MERELY A WORKAROUND. `AetherInstance.start()` runs
        # `assert_cart_matches_disk` on every spawn with `CART_WINDOW = 0x400000`, i.e. it reads
        # the WHOLE cart back off the bus and byte-compares it against the file. So the patched
        # word is proven to be in the emulator's cart by a full-image comparison, for free —
        # strictly stronger than the single-word readback the live poke would have got.
        #
        # THE PATCH SITE IS A FILE OFFSET, and that identity is proven rather than assumed: the
        # region table is read out of this same file with `rom[addr:...]` using the ROM addresses
        # from `Act.act_regions`, and it yields the act's real rows — so address == offset here.
        #
        # WHAT IS NOT PATCHED, deliberately: nothing else. The header checksum at $18E is data
        # (`games/sonic4/config/header.emp`) and NO engine code reads it — sigil folds it
        # post-pipeline and the ROM never verifies it at boot, so a two-byte data patch boots
        # exactly as the pristine image does. The deb2 appendix sits past EndOfRom and is
        # untouched; the `.lst` is untouched, so every symbol still resolves.
        #
        # A SECOND INSTANCE, NOT A RE-USE, because leg S's subject is a DIFFERENT ACT. Running
        # C/D/W against the patched cart would move the ceilings A2 and A3 assert against.
        async def _legS():
            if args.skip_poke:
                raise LegBlocked(
                    "SKIPPED by --skip-poke. Nothing in this run tested step 4's POSITION "
                    "change; the verdict covers the rate clamp only.")
            if plan is None:
                raise LegBlocked("no region qualified for the vertical legs — see W_plan.")
            half_h = K["HALF_H"]
            row, cfg = plan["row"], plan["cfg"]
            ro, _ = region_table.region_layout()
            span_off = row["addr"] + ro["rg_bg_span"]
            # DERIVED from THIS region's own reach, not from a fraction of VSCROLL_BG_MAX: the
            # ceiling has to be strictly below what the act can actually drive the scroll to, or
            # the scroll never presses against it and a pass would mean nothing. One clear
            # BG_VSCROLL_MAX_STEP of margin, and the span rounded DOWN to the 8-px grid because
            # `ojz_region()` refuses a span off it (a partial row nothing can draw).
            reachable = target_scroll(plan["cam_y_hi"], cfg)
            span_test = ((K["SCREEN_HEIGHT"] + max(0, reachable - 2 * step_max)) // 8) * 8
            want_ceiling = span_test - K["SCREEN_HEIGHT"]
            if not 0 < want_ceiling < K["VSCROLL_BG_MAX"] or reachable - step_max <= want_ceiling:
                raise LegBlocked(
                    f"it cannot discriminate in row {row['index']}: the scroll reaches "
                    f"{reachable} there, so a patched span of {span_test} gives a ceiling of "
                    f"{want_ceiling}, which must be strictly inside (0, {K['VSCROLL_BG_MAX']}) "
                    f"AND at least {step_max} below the reach.")
            if span_off + 2 > len(rom):
                raise LegBlocked(f"region row {row['index']}'s rg_bg_span is at {span_off:#x}, "
                                 f"past the end of the {len(rom)}-byte ROM image")
            tmp = tempfile.mkdtemp(prefix="bgrate-patched-")
            try:
                patched = Path(tmp) / Path(args.rom).name
                image = bytearray(rom)
                was = int.from_bytes(image[span_off:span_off + 2], "big")
                image[span_off:span_off + 2] = span_test.to_bytes(2, "big")
                patched.write_bytes(bytes(image))
                back = int.from_bytes(patched.read_bytes()[span_off:span_off + 2], "big")
                if back != span_test:
                    raise LegBlocked(f"the on-disk patch did not take: wrote {span_test} at "
                                     f"{span_off:#x}, read back {back} from {patched}")
                report["S_patch"] = {"rom": str(patched), "offset": hex(span_off),
                                     "row": row["index"], "was": was, "now": span_test,
                                     "bytes_changed": 2}
                inst2 = AetherInstance(str(patched), symbols=args.lst)
                try:
                    sock2 = await asyncio.to_thread(inst2.start)
                except (SpawnError, WrongServerError, CartMismatch) as e:
                    raise LegBlocked(f"the patched cart would not boot or would not verify: {e}")
                b2 = BusClient(socket_path=sock2, client_id="bgvscrollrateS",
                               client_name="bg_vscroll_rate_witness (patched cart)")
                try:
                    await b2.connect()
                    await _c(b2, "emulator/load_symbols", {"path": args.lst})
                    rig2 = Rig(b2, sym, rows, bytes(image), K)
                    rig2.span_override[row["addr"]] = span_test
                    await rig2.boot()
                    for _ in range(3):
                        await rig2.tick()
                    # Confirm the patched word is in the EMULATOR's cart, not merely on disk.
                    # (assert_cart_matches_disk already byte-compared the whole image on spawn;
                    # this reads the one word back by its own address so the verdict names it.)
                    live = await rd(b2, span_off, 2)
                    if live != span_test:
                        raise LegBlocked(
                            f"the emulator's cart holds {live} at {span_off:#x}, not the patched "
                            f"{span_test} — the patched file is not what booted.")
                    await warp_to(b2, sym, rig2, plan["x"], plan["cam_y_lo"] + half_h)
                    legS = await leg_until(rig2, "S", ["down"],
                                           lambda s: s["cam_y"] >= plan["cam_y_hi"], 24)
                finally:
                    try:
                        await b2.close()
                    finally:
                        inst2.reap()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            report["S"] = check_leg(fails, K, "S (patched span, descent)", legS)
            report["S"].update({"row": row["index"], "span_offset": hex(span_off),
                                "span_test": span_test, "derived_ceiling": want_ceiling,
                                "reach_without_the_patch": reachable,
                                "vscroll_bg_max": K["VSCROLL_BG_MAX"]})
            inside = [s for s in legS if s["region"] == row["addr"]]
            if not inside:
                raise LegBlocked(
                    f"Region_Current was never on the patched row {row['index']} during the "
                    "descent, so nothing here measured the patched span.")
            settled = inside[-1]["v"]
            over = [s["tag"] for s in inside if s["v"] > want_ceiling]
            if over:                                                        # A5
                fails.append(
                    f"A5: with region row {row['index']}'s rg_bg_span patched to {span_test}, "
                    f"the BG scroll rose above the derived ceiling {want_ceiling} on "
                    f"{len(over)} sample(s) ({over[:5]}). The position clamp is not reading "
                    "rg_bg_span.")
            if settled != want_ceiling:
                fails.append(
                    f"A5: with rg_bg_span patched to {span_test}, the descent settled at "
                    f"{settled}, not at the derived ceiling {want_ceiling}. "
                    + (f"It settled at VSCROLL_BG_MAX = {K['VSCROLL_BG_MAX']}, which is exactly "
                       "what the PRE-step-4 clamp does — the position change is not in this ROM."
                       if settled == K["VSCROLL_BG_MAX"] else
                       "Neither the patched ceiling nor the plane ceiling; read the trace."))
            else:
                findings.append(
                    f"A5: with row {row['index']}'s rg_bg_span patched to {span_test} in a COPY "
                    f"OF THE ROM (2 bytes at {span_off:#x}), the descent settled at {settled} = "
                    f"rg_bg_span - SCREEN_HEIGHT, NOT at VSCROLL_BG_MAX = {K['VSCROLL_BG_MAX']} "
                    f"(which it reaches at {reachable} unpatched). This is the leg that is red "
                    "with the position change reverted.")
        await run_leg("S", _legS)
        report["blocked"] = [{"leg": n, "why": w} for n, w in blocked]
        report["unexplained"] = [o for k in ("C", "D", "W", "S")
                                 for o in report.get(k, {}).get("blocking_observations", [])]
    finally:
        try:
            await b.close()
        finally:
            inst.reap()
    return finish(args, report, fails, findings)


def finish(args, report, fails, findings) -> int:
    report["fails"] = fails
    report["findings"] = findings
    if args.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        c = report["constants"]
        print(f"bg_vscroll_rate_witness: BG_VSCROLL_MAX_STEP = {c['BG_VSCROLL_MAX_STEP']} px "
              f"({c['BG_VSCROLL_MAX_STEP_ROWS']} rows x {c['BG_VSCROLL_ROW_PX']} px), "
              f"VSCROLL_BG_MAX = {c['VSCROLL_BG_MAX']}, SCREEN_HEIGHT = {c['SCREEN_HEIGHT']}")
        print(f"  region rows authoring an rg_bg_span: {report['rows_with_authored_span']} "
              f"of {len(report['rows'])}")
        for key in ("C", "D", "W", "S"):
            g = report.get(key)
            if not g:
                continue
            if "could_not_run" in g:
                print(f"  {key}: COULD NOT RUN — {g['could_not_run'].splitlines()[0]}")
                continue
            print(f"  {g['leg']}: {g['ticks']} ticks, v {g['v_first']} -> {g['v_last']} "
                  f"(min {g['v_min']}, max {g['v_max']}), worst step {g['worst_step']}, "
                  f"{g['ticks_at_the_bound']} tick(s) at the bound, {g['modelled_ticks']} "
                  f"modelled ({g['model_mismatches']} mismatched), rows {g['rows_visited']}")
        for r in report.get("W_scan", []):
            print(f"  scan row {r['row']} {r['x']}x{r['y']} "
                  + (f"cfg {r['cfg']} v_factor {r['v_factor']} jump {r.get('derived_jump')}: "
                     if "cfg" in r else "")
                  + r.get("verdict", "(not probed)"))
        if report.get("W_scan_unprobed"):
            print(f"  scan stopped at the first qualifying row; rows "
                  f"{report['W_scan_unprobed']} were not probed")
        for f in findings:
            print(f"FINDING {f}")
    blocked = report.get("blocked", [])
    unexplained = report.get("unexplained", [])
    if unexplained and not args.json:
        print("UNEXPLAINED OBSERVATION(S) — the trace, not advice to go and find it:",
              file=sys.stderr)
        for o in unexplained:
            d = o["decomposition"]
            print(f"  - leg {o['leg']} step {o['i']}: the clamp bound and the cause is "
                  f"`{o['why']}`. gap {d['gap']} = d_cfg {d['d_cfg']} + d_cam {d['d_cam']} + "
                  f"backlog {d['backlog']}; camera {d['cam']}, config {d['cfg']} "
                  f"({'unchanged' if d['cfg_unchanged'] else 'CHANGED'}), rows {d['row']}, "
                  f"target {d['target_prev']} -> {d['target_now']}, previous value {d['v_prev']}",
                  file=sys.stderr)
            for s in o["trace"]:
                print(f"      {s['tag']}: v={s['v']:<5} camY={s['cam_y']:<5} row={s['row']} "
                      f"region={s['region']:#x} trans={s['trans']} ceiling={s['ceiling']} "
                      f"dtick={s['dtick']}", file=sys.stderr)
    if fails:
        print("FAIL:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        if blocked:
            print(f"  (and {len(blocked)} leg(s) could not run: "
                  f"{', '.join(n['leg'] for n in blocked)})", file=sys.stderr)
        if unexplained:
            print(f"  (and {len(unexplained)} unattributable bound step(s), above)",
                  file=sys.stderr)
        return 1
    if blocked:
        # NEVER 0 HERE. The legs that can be blocked include both DISCRIMINATORS, and A1/A2/A3
        # over ordinary motion cannot stand in for either: in ordinary play the target never
        # moves more than the bound, so a tree with the rate clamp REMOVED produces identical
        # numbers on legs C and D — including under A3, which models the clamp but is only
        # exercised where the clamp would act.
        print("COULD NOT RUN:", file=sys.stderr)
        for n in blocked:
            print(f"  - leg {n['leg']}: {n['why']}", file=sys.stderr)
        ran = [k for k in ("C", "D", "W", "S")
               if k in report and "could_not_run" not in report[k]]
        print(f"\n  {len(ran)} leg(s) DID run and their assertions held "
              f"({', '.join(ran) or 'none'}), and that is reported above rather than thrown "
              "away.", file=sys.stderr)
        if "W" not in ran:
            print("  WITHOUT LEG W NOTHING HERE TESTED THE RATE CLAMP. In ordinary play the "
                  "target never moves more than the bound, so C and D produce identical "
                  "numbers on a tree with the rate clamp removed.", file=sys.stderr)
        if "S" not in ran:
            print("  WITHOUT LEG S NOTHING HERE TESTED THE POSITION CLAMP, AND NOTHING ELSE IN "
                  "THIS TREE CAN. Every shipped region row leaves rg_bg_span at 0, so every "
                  "other leg takes the act-default fallback and would pass unchanged with step "
                  "4's position change reverted. This is not a partial pass; it is no evidence "
                  "about change (a) at all.", file=sys.stderr)
        return 2
    if unexplained:
        # NOT A PASS, AND THE WORD IS NOT PRINTED. A run whose own prose says "read this before
        # accepting it" while exiting 0 tells a tired reader the opposite of what the exit code
        # says — and the exit code is what gets pasted into merge evidence. Every assertion held
        # AND something happened the model cannot attribute to a named cause. Those are two
        # different facts and this says both.
        print(f"bg_vscroll_rate_witness: NOT ACCEPTED — every assertion held, but "
              f"{len(unexplained)} bound step(s) have no attributable cause (see above). "
              "This is not a failure of the clamp and it is not green.", file=sys.stderr)
        return 2
    print("bg_vscroll_rate_witness: PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--skip-poke", action="store_true",
                    help="skip leg S (the ROM poke). The other legs still run and still report, "
                         "but the run exits 2, not 0: without leg S nothing has tested step 4's "
                         "POSITION change and a green would be a lie about it.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        return asyncio.run(run(args))
    except SetupError as e:
        print(f"SETUP ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())


# ---- MUTATIONS — the red-first proof this witness has NOT yet been given --------------------
#
# ⚠ NEVER RUN. Written by a session that could not touch an emulator. These are the two reverts
# that must make it red; until somebody has watched each one fail, a green here is an untested
# instrument. Restore from the COMMITTED baseline afterwards (`git checkout <sha> -- <file>`),
# never with `git checkout --` on a dirty tree.
#
#   (b) THE RATE CLAMP. In engine/level/parallax.emp, Parallax_Step5_Vscroll, replace the whole
#       `.v_rate` block (from `move.w Parallax_Current_Vscroll_BG, d0` to `add.w d0, d2`) with
#       nothing, so `.v_rate:` falls straight into the store. Rebuild. EXPECT: A4 red (no run at
#       the bound) AND A1 red on leg W (a single tick moving the whole jump) AND A3 red (the
#       model still clamps the step). If only A4 goes red, leg W's jump is not actually landing
#       and the leg needs re-aiming before anything here is trusted.
#
#   (a) THE POSITION CLAMP. In the same proc, delete the five instructions from
#       `move.l Region_Current, d0` through `subi.w #SCREEN_HEIGHT, d3`, leaving
#       `move.w #VSCROLL_BG_MAX, d3` as the only ceiling. Rebuild. EXPECT: leg S's A5 red with
#       the message naming VSCROLL_BG_MAX explicitly ("the position change is not in this ROM"),
#       and legs C/D/W UNCHANGED AND GREEN — which is the point being demonstrated: on a tree
#       where no row authors a span, C/D/W cannot see this change at all.
#
# A mutation that leaves the tool green is a runner defect, not a pass: check that the rebuilt
# ROM is the one the witness loaded (`--rom`) before concluding anything about the instrument.
