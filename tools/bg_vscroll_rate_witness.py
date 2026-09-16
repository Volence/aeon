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
position-clamp change reverted. That is why leg S exists: it POKES a region row's `rg_bg_span`
in the emulator's ROM image to a value that is derived to be distinguishable, and then asserts
the scroll sticks at the poked map's ceiling — a value the pre-step-4 code could not produce.
Leg S is the ONLY leg that tests change (a) at all. If it cannot run (the server refuses a ROM
write; the readback disagrees) this tool exits 2 and says so — never 0.

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
      with (b) reverted. The warp distance is derived from the act's own geometry, never
      picked, and the leg refuses (exit 2) if the derived jump is too small to bind.
  A5  THE POSITION DISCRIMINATOR (leg S, ROM poke). With the row under the camera's
      rg_bg_span poked to SPAN_TEST (derived so SPAN_TEST - SCREEN_HEIGHT is strictly below
      VSCROLL_BG_MAX and strictly reachable), a descent inside that row settles with
      v == SPAN_TEST - SCREEN_HEIGHT and never above it. The pre-step-4 code settles at
      VSCROLL_BG_MAX instead, so this is red with (a) reverted.

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

Usage:
    python3 tools/bg_vscroll_rate_witness.py [--rom s4.debug.bin] [--lst s4.debug.lst]
                                             [--skip-poke] [--json]
Exit: 0 every assertion held · 1 an assertion failed · 2 could not measure (setup error, a
refused ROM poke included — never rendered as a pass).
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient              # noqa: E402
from aether_instance import AetherInstance, SpawnError, WrongServerError, read_bytes  # noqa: E402
from raster_cost_probe import parse_lst   # noqa: E402
import region_table                       # noqa: E402

BOOT_MAX_FRAMES = 600
TICK_MAX_FRAMES = 8          # run_to ceiling for one logic tick (a lag tick spans two frames)
WARP_MAX_FRAMES = 240        # the warp tick alone: a synchronous window refill + plane redraw
LEG_MAX_TICKS = 900          # a ceiling on any one leg; running out is SETUP, never a skip
SETTLE_TICKS = 40            # ticks held after a jump before the value must have settled


class SetupError(Exception):
    """The measurement could not be made. Exit 2 — never a pass and never a verdict."""


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


def step5_shape_check() -> None:
    """Refuse to model a Parallax_Step5_Vscroll whose clamp no longer reads the way clamp_model()
    transcribes it. The model is only as good as this match."""
    txt = (AEON / "engine/level/parallax.emp").read_text()
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
        return {"tag": tag,
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

def check_leg(fails: list[str], K: dict, name: str, samples: list[dict]) -> dict:
    """A1 + A2 + A3 over one leg. Returns the leg's summary row."""
    step_max = K["BG_VSCROLL_MAX_STEP"]
    steps, worst, binds = [], 0, 0
    for i in range(1, len(samples)):
        d = samples[i]["v"] - samples[i - 1]["v"]
        steps.append(d)
        worst = max(worst, abs(d))
        if abs(d) == step_max:
            binds += 1
        if abs(d) > step_max:                                              # A1
            fails.append(f"A1 {name}: tick {i} moved Parallax_Current_Vscroll_BG by {d} px "
                         f"({samples[i-1]['v']} -> {samples[i]['v']}), past BG_VSCROLL_MAX_STEP "
                         f"= {step_max}. Camera Y {samples[i-1]['cam_y']} -> "
                         f"{samples[i]['cam_y']}, region row {samples[i]['row']}")
    for i, s in enumerate(samples):                                        # A2
        if not 0 <= s["v"] <= s["ceiling"]:
            fails.append(f"A2 {name}: sample {i} has Parallax_Current_Vscroll_BG = {s['v']}, "
                         f"outside [0, {s['ceiling']}] — the ceiling derived from region row "
                         f"{s['row']}'s rg_bg_span = {s['span']} "
                         f"({'the act default' if s['span'] == 0 else 'authored'})")
    modelled = mismatched = 0
    for i in range(1, len(samples)):                                       # A3
        a, s = samples[i - 1], samples[i]
        if s["trans"] or a["trans"] or s["cfg"] is None:
            continue           # the lerp arm and a config this witness cannot read: rate only
        if s["cfg"]["bob"]:
            raise SetupError(f"the active parallax_config at {s['cfg']['ptr']:#x} authors a bob "
                             f"(pcfg_bob = {s['cfg']['bob']:#04x}); target_scroll() does not "
                             "model the sine term. Teach it before trusting any verdict here")
        modelled += 1
        want = clamp_model(target_scroll(s["cam_y"], s["cfg"]), a["v"], s["ceiling"], step_max)
        if want != s["v"]:
            mismatched += 1
            if mismatched <= 3:
                fails.append(
                    f"A3 {name}: tick {i}: Parallax_Current_Vscroll_BG is {s['v']}, the clamp "
                    f"model says {want}. camY {s['cam_y']}, config {s['cfg']['ptr']:#x} "
                    f"(v_factor {s['cfg']['v_factor']}, v_center {s16(s['cfg']['v_center'])}, "
                    f"v_offset {s16(s['cfg']['v_offset'])}) -> target "
                    f"{target_scroll(s['cam_y'], s['cfg'])}; previous {a['v']}, ceiling "
                    f"{s['ceiling']} (row {s['row']}, span {s['span']})")
    return {"leg": name, "ticks": len(samples) - 1, "v_first": samples[0]["v"],
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
    step_max = K["BG_VSCROLL_MAX_STEP"]

    sym = parse_lst(args.lst)
    for need in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update",
                 "Camera_X", "Camera_Y", "Camera_Y_Max", "Region_Current",
                 "Parallax_Current_Vscroll_BG", "Parallax_Current_Config",
                 "Parallax_Target_Config", "Parallax_Transition_Frames",
                 "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag",
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

        # ---- leg C: the crossing route, right across the whole region table ---------------
        # The same traversal shape parallax_crossing_gate walks: hold RIGHT from the spawn
        # until the camera centre is past the last row's right edge.
        far = max(r["x1"] for r in rows)
        legC = await leg_until(rig, "C", ["right"], lambda s: s["centre"][0] >= far, 8)
        report["C"] = check_leg(fails, K, "C (crossing route, held RIGHT)", legC)

        # ---- leg D: "the shaft fall" — held DOWN in free flight, the camera's own ceiling --
        cam_y_max = await rd(b, sym["Camera_Y_Max"], 2)
        legD = await leg_until(rig, "D", ["down"],
                               lambda s: s["cam_y"] >= cam_y_max, 8)
        report["D"] = check_leg(fails, K, "D (descent, held DOWN)", legD)
        report["D"]["camera_y_max"] = cam_y_max
        report["D"]["fly_speed_px_per_frame"] = K["PLAYER_DEBUG_FLY_SPEED"]
        findings.append(
            f"D: the descent at PLAYER_DEBUG_FLY_SPEED = {K['PLAYER_DEBUG_FLY_SPEED']} px/frame "
            f"(the camera's own per-frame ceiling — see the header) moved the BG scroll by at "
            f"most {report['D']['worst_step']} px in a tick against a bound of {step_max}. "
            + ("The clamp never bound, which is the expected NEGATIVE CONTROL: it does not fire "
               "in ordinary play." if report['D']['worst_step'] < step_max else
               "The clamp BOUND during an ordinary descent — that is not what the shipped "
               "v_factor predicts and is worth reading before accepting this run."))

        # ---- leg W: the rate DISCRIMINATOR — a DEBUG warp that must ratchet ---------------
        # Derived, not picked: warp from the top of the act to the bottom of the SAME region
        # column, so the target scroll jumps by (dy >> v_factor). Refuse if that jump is too
        # small for the clamp to bind for two consecutive ticks.
        here = await rig.sample("pre_warp")
        if here["cfg"] is None:
            raise SetupError("no parallax_config is active before the warp leg — cannot derive "
                             "the jump the warp has to produce")
        wx = here["cam_x"] + K["HALF_W"]
        row_hi = region_table.region_at(rows, wx, 0) or rows[0]
        y_top, y_bot = row_hi["y0"], min(row_hi["y1"], cam_y_max)
        jump = abs(target_scroll(y_bot, here["cfg"]) - target_scroll(y_top, here["cfg"]))
        report["W_plan"] = {"x": wx, "from_y": y_top, "to_y": y_bot, "derived_target_jump": jump,
                            "needs_more_than": 2 * step_max}
        if jump <= 2 * step_max:
            raise SetupError(
                f"the warp leg cannot discriminate on this act: warping x={wx} from y={y_top} to "
                f"y={y_bot} moves the target BG scroll by only {jump} px, and the rate clamp "
                f"needs a jump over 2 * {step_max} = {2 * step_max} to be forced to the bound "
                "for two consecutive ticks. A4 would be vacuous, so this is COULD NOT RUN, not "
                "a pass. Re-aim the warp or raise the act's height x depth.")
        for nm, v, w in (("Warp_Req_X", wx, 2), ("Warp_Req_Y", y_top, 2), ("Warp_Req_Flag", 1, 1)):
            await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
        await rig.tick(WARP_MAX_FRAMES)
        for _ in range(SETTLE_TICKS):
            await rig.tick()
        for nm, v, w in (("Warp_Req_X", wx, 2), ("Warp_Req_Y", y_bot, 2), ("Warp_Req_Flag", 1, 1)):
            await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
        legW = await leg(rig, "W", None, SETTLE_TICKS, first_tick_frames=WARP_MAX_FRAMES)
        flag = await rd(b, sym["Warp_Req_Flag"], 1)
        if flag:
            raise SetupError(f"Warp_Req_Flag is still {flag} after the warp tick — the warp never "
                             "happened, and a warp that never happened looks exactly like a warp "
                             "that changed nothing")
        report["W"] = check_leg(fails, K, "W (warp ratchet)", legW)
        run_at_bound = longest_run_at(report["W"]["steps"], step_max)
        report["W"]["longest_run_at_the_bound"] = run_at_bound
        if run_at_bound < 2:                                               # A4
            fails.append(
                f"A4: after a warp whose derived target jump is {jump} px (> 2 * {step_max}), the "
                f"longest run of consecutive ticks stepping exactly {step_max} px is "
                f"{run_at_bound}. The rate clamp did not bind, so leg W's green is vacuous and "
                f"A1 is untested. Steps observed: {report['W']['steps'][:12]}")
        else:
            findings.append(f"A4: the warp forced the rate clamp to the bound for {run_at_bound} "
                            f"consecutive ticks at exactly {step_max} px — this is the leg that "
                            "is red with the rate clamp reverted.")

        # ---- leg S: the position DISCRIMINATOR — poke a row's rg_bg_span in ROM -----------
        if args.skip_poke:
            findings.append("S: SKIPPED by --skip-poke. Nothing in this run tested step 4's "
                            "POSITION change; the verdict covers the rate clamp only.")
            report["S"] = {"skipped": True}
        else:
            ro, _ = region_table.region_layout()
            row = row_hi
            span_addr = row["addr"] + ro["rg_bg_span"]
            # DERIVED so the observation is impossible on the pre-step-4 code: a ceiling
            # strictly below VSCROLL_BG_MAX, and strictly above 0, that the act can actually
            # reach (the unclamped target at the act's floor must exceed it).
            span_test = K["SCREEN_HEIGHT"] + K["VSCROLL_BG_MAX"] // 2
            want_ceiling = span_test - K["SCREEN_HEIGHT"]
            reachable = target_scroll(y_bot, here["cfg"])
            if not 0 < want_ceiling < K["VSCROLL_BG_MAX"] or reachable <= want_ceiling:
                raise SetupError(
                    f"leg S cannot discriminate: a poked span of {span_test} gives a ceiling of "
                    f"{want_ceiling}, which must be strictly inside (0, {K['VSCROLL_BG_MAX']}) "
                    f"AND strictly below the target the act's floor produces ({reachable}). "
                    "COULD NOT RUN, not a pass.")
            await _c(b, "emulator/write_memory",
                     {"addr": hex(span_addr), "value": span_test, "width": 2})
            back = await rd(b, span_addr, 2)
            if back != span_test:
                raise SetupError(
                    f"the ROM poke did not stick: wrote {span_test} to region row {row['index']}'s "
                    f"rg_bg_span at {span_addr:#x}, read back {back}. The server will not write "
                    "the ROM image, so the POSITION half of step 4 is UNTESTED by this run. "
                    "COULD NOT RUN — never report this as a pass.")
            rig.span_override[row["addr"]] = span_test
            for nm, v, w in (("Warp_Req_X", wx, 2), ("Warp_Req_Y", y_top, 2),
                             ("Warp_Req_Flag", 1, 1)):
                await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
            await rig.tick(WARP_MAX_FRAMES)
            legS = await leg_until(rig, "S", ["down"], lambda s: s["cam_y"] >= y_bot, 24)
            report["S"] = check_leg(fails, K, "S (poked span, descent)", legS)
            report["S"].update({"row": row["index"], "span_addr": hex(span_addr),
                                "span_test": span_test, "derived_ceiling": want_ceiling,
                                "vscroll_bg_max": K["VSCROLL_BG_MAX"]})
            inside = [s for s in legS if s["region"] == row["addr"]]
            if not inside:
                raise SetupError(f"leg S never had Region_Current on the poked row "
                                 f"{row['index']} — the descent left the row, so nothing here "
                                 "measured the poked span. COULD NOT RUN.")
            settled = inside[-1]["v"]
            over = [s["tag"] for s in inside if s["v"] > want_ceiling]
            if over:                                                        # A5
                fails.append(
                    f"A5: with region row {row['index']}'s rg_bg_span poked to {span_test}, the BG "
                    f"scroll rose above the derived ceiling {want_ceiling} on "
                    f"{len(over)} sample(s) ({over[:5]}). The position clamp is not reading "
                    "rg_bg_span.")
            if settled != want_ceiling:
                fails.append(
                    f"A5: with rg_bg_span poked to {span_test}, the descent settled at "
                    f"{settled}, not at the derived ceiling {want_ceiling}. "
                    + (f"It settled at VSCROLL_BG_MAX = {K['VSCROLL_BG_MAX']}, which is exactly "
                       "what the PRE-step-4 clamp does — the position change is not in this ROM."
                       if settled == K["VSCROLL_BG_MAX"] else
                       "Neither the poked ceiling nor the plane ceiling; read the trace."))
            else:
                findings.append(
                    f"A5: with row {row['index']}'s rg_bg_span poked to {span_test}, the descent "
                    f"settled at {settled} = rg_bg_span - SCREEN_HEIGHT, NOT at VSCROLL_BG_MAX = "
                    f"{K['VSCROLL_BG_MAX']}. This is the leg that is red with the position "
                    "change reverted.")
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
            if not g or g.get("skipped"):
                continue
            print(f"  {g['leg']}: {g['ticks']} ticks, v {g['v_first']} -> {g['v_last']} "
                  f"(min {g['v_min']}, max {g['v_max']}), worst step {g['worst_step']}, "
                  f"{g['ticks_at_the_bound']} tick(s) at the bound, {g['modelled_ticks']} "
                  f"modelled ({g['model_mismatches']} mismatched), rows {g['rows_visited']}")
        for f in findings:
            print(f"FINDING {f}")
    if fails:
        print("FAIL:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("bg_vscroll_rate_witness: PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--skip-poke", action="store_true",
                    help="skip leg S (the ROM poke). The run then tests the RATE clamp only, "
                         "says so in its findings, and is NOT evidence about the position clamp.")
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
