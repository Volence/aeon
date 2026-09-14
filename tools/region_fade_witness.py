#!/usr/bin/env python3
"""region_fade_witness — does a palette cross-fade arm at an authored REGION edge that is NOT on
the 2048-px section grid, reach its target on the frame the fade's own step rule predicts, and do
nothing at a section line the region spans?

THE SUBJECT (painted-regions v1, step 5; docs/superpowers/notes/2026-09-13-regions-p2.md). OJZ act
1's region table carries a region whose preset arms the cross-fade (`preset(..., transition: N)`,
N != 0) and whose left edge is off the section grid. This is the first time the fade path has run
in the game at all, so its behaviour is the thing measured, not assumed:

  Parallax_CheckBoundary (engine/level/parallax.emp) -> Effects_InstallPreset
  (engine/effects/preset.emp): `tst.w ep_transition; beq` -> Palette_ArmFade (Pal_Fade_Request = 1)
  -> Palette_LoadPal: request set -> copy ep_pal into Pal_Target, Pal_Fade_Frames = PAL_FADE_FRAMES,
  clear the request; request clear -> copy into Pal_Base and snap on the next compose.
  Palette_Compose (engine/system/game_loop.emp calls it AFTER the game state, so the same tick)
  -> Palette_DoFade (engine/effects/palette.emp).

THE STEP RULE, READ OUT OF Palette_DoFade'S INSTRUCTIONS AND NOT ITS COMMENTS (they disagree):

      subq.b #1, Pal_Fade_Frames ; bne .step_frame        -> 0 after the decrement: SNAP
      .step_frame: btst #0, Pal_Fade_Frames ; bne .noskip ; rts
                                                        -> STEP when the decremented count is ODD
      .noskip: every channel of every word of lines 1-3 moves +/-1 toward Pal_Target
               (step_d3_toward_d4), the word rebuilt from the three 3-bit channels alone

  The inline comments say "step only on even frame parity" / "odd frame: nothing moved"; the
  branch does the opposite (`bne` after `btst` is taken when the bit is SET). So with
  PAL_FADE_FRAMES = F, the k-th compose after the arm (k = 1 is the arming tick's own compose)
  leaves Pal_Fade_Frames = F - k, steps when F - k is odd, and snaps to Pal_Target at k = F. A
  channel that is d steps from its target therefore arrives at k = 2d - 1, and the whole palette
  arrives at k = 2 * max(d) - 1. PAL_FADE_FRAMES is parsed out of the source; the parity and the
  +/-1 are transcribed from the instructions above, and `fade_model()` below is the only copy.

WHAT IS ASSERTED (exit 1 on any failure):
  E0  the premise: exactly one region row binds a preset with ep_transition != 0 (the FADE
      region), its left edge is off the section grid, the region to its left binds a DIFFERENT
      ep_pal, and a section line lies strictly inside it. On a ROM with no such row (the base,
      before step 5) this is the red, with the reason printed.
  E1  no fade before the edge: every sample before the crossing reads Pal_Fade_Frames == 0,
      Pal_Fade_Request == 0 and the palette buffer equal to the left region's ep_pal.
  E2  the fade arms AT the edge: the first tick whose camera centre is >= the edge is the tick
      Region_Current becomes the fade region, and that tick's compose leaves
      Pal_Fade_Frames == F - 1 with Pal_Target == the fade region's ep_pal.
  E3  it reaches the target after the derived number of composes, and follows fade_model()
      word for word on EVERY compose in between; Pal_Fade_Frames reaches 0 at k = F and the
      PAL_ACT_FADE bit is clear after it; CRAM lines 1-3 read the target once settled.
  E4  the section line INSIDE the fade region is crossed with nothing happening: Region_Current
      unchanged, no request, no frames, palette unchanged.
  E5  crossing OUT of the fade region into a region whose preset does not arm the fade SNAPS:
      the first compose in the new region shows that region's ep_pal exactly, no frames.
  E6  a crossing between two regions that share an ep_pal (the section line at the left
      region's own left edge) changes no colour and arms nothing.
  Every sample: Region_Current is the row the ROM's own table (tools/region_table.py) places
  under the camera centre, and Logic_Tick advanced by exactly one (a lag-free sample stream,
  so "k composes" and "k samples" are the same count — checked, not assumed).

WHAT IS MEASURED AND PRINTED BUT NOT ASSERTED (open questions; see the parcel note):
  R   REVERSAL mid-fade: cross into the fade region, turn back after a few ticks, and read what
      the palette settles to in the region you returned to. `--strict-reversal` asserts that it
      settles to THAT region's own ep_pal (region-exact); without the flag the reading is
      printed as a finding.
  W   a DEBUG warp that lands INSIDE the already-cached fade region: does the forced
      re-install arm a fade, and does any colour move?
  B   a boot (the DEBUG boot-position mailbox) straight into the fade region: the palette buffer
      and CRAM on the first displayed frames (design Q3 / T6).
  C   the cost, in 68000 cycles (master clock / 7), of Parallax_CheckBoundary and
      Palette_Compose on the crossing tick, the fade's step and skip ticks, and a quiet tick.
      Entry-to-return windows, so any interrupt taken inside one is included — stated beside
      the figures.

THE ROUTE. The DEBUG shape boots into debug free-flight (measured: holding RIGHT from the spawn
moves the player exactly PLAYER_DEBUG_FLY_SPEED px a tick at a constant Y), and the camera's own
step cap is the same 16 px, so a held RIGHT crosses every edge at the camera's maximum speed. The
walk is a HOLD (emulator/hold) sampled once per logic tick at the first instruction of
GameState_OJZScroll_Update — `step` one instruction off it, `run_to` back — where the previous
tick's crossing and compose have both completed.

RUNNER: none. Like tools/preset_lab_witness.py this is a hand-run witness for the parcel that
authored the edge; tools/effects_gates.py does not run it. Booked in docs/DEFERRED_WORK.md.

Exit 0 every assertion held · 1 an assertion failed (or the premise is absent) · 2 could not
measure (setup error). `--json` prints the per-tick record.
"""
from __future__ import annotations

import argparse
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
WALK_MAX_TICKS = 900         # a ceiling on any one leg; running out is a SETUP error, never a skip
MARGIN_TICKS = 24            # samples kept past a crossing before a leg may stop (> PAL_FADE_FRAMES)
REVERSAL_AFTER = 4           # ticks spent inside the fade region before turning back (< F/2)
SETTLE_TICKS = 24
WARP_MAX_FRAMES = 240        # the warp tick only: a synchronous window refill + plane redraw


class SetupError(Exception):
    """The measurement could not be made. Exit 2 — never a pass and never a verdict."""


# ---- source-derived constants ------------------------------------------------------------

def src_const(rel: str, name: str) -> int:
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|%[01]+|\d+)",
                  txt, re.M)
    if not m:
        raise SetupError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v[0] == "$" else int(v[1:], 2) if v[0] == "%" else int(v)


def preset_offsets() -> dict[str, int]:
    """EffectsPreset's explicit `@ $XX` displacements, read out of its declaration."""
    txt = (AEON / "engine/effects/preset.emp").read_text()
    m = re.search(r"pub struct EffectsPreset\s*\(size:\s*(\d+)\)\s*\{(.*?)^\}", txt, re.M | re.S)
    if not m:
        raise SetupError("cannot find `pub struct EffectsPreset (size: N)` in engine/effects/preset.emp")
    out = {}
    for fm in re.finditer(r"^\s*(ep_\w+)\s*:[^@\n]*@\s*\$([0-9A-Fa-f]+)", m.group(2), re.M):
        out[fm.group(1)] = int(fm.group(2), 16)
    for need in ("ep_pal", "ep_raster", "ep_patched", "ep_transition"):
        if need not in out:
            raise SetupError(f"EffectsPreset declares no `{need} ... @ $XX` — the ROM reads below "
                             "would be guesses")
    return out


def dofade_rule_check() -> None:
    """Refuse to model a Palette_DoFade whose instructions no longer read the way fade_model()
    transcribes them. The model is only as good as this match; a changed body must be re-read,
    not silently mis-modelled."""
    txt = (AEON / "engine/effects/palette.emp").read_text()
    m = re.search(r"proc Palette_DoFade\s*\(\)[^{]*\{(.*?)^\}", txt, re.M | re.S)
    if not m:
        raise SetupError("cannot find `proc Palette_DoFade` in engine/effects/palette.emp")
    body = re.sub(r"//[^\n]*", "", m.group(1))
    want = [r"subq\.b\s+#1,\s*Pal_Fade_Frames\s+bne\s+\.step_frame",
            r"\.step_frame:\s+btst\s+#0,\s*Pal_Fade_Frames\s+bne\s+\.noskip\s+rts",
            r"cmp\.w\s+d4,\s*d3|step_d3_toward_d4\(\)"]
    for w in want:
        if not re.search(w, body):
            raise SetupError(f"Palette_DoFade no longer matches the step rule this witness "
                             f"transcribes (missing /{w}/). Re-read the proc and update "
                             "fade_model() before trusting any verdict here")
    step = re.search(r"comptime fn step_d3_toward_d4\(\)[^{]*\{(.*?)^\}", txt, re.M | re.S)
    if not step or not re.search(r"cmp\.w\s+d4,\s*d3\s+beq\s+\.st_end\s+bcs\s+\.st_up\s+"
                                 r"subq\.w\s+#1,\s*d3", re.sub(r"//[^\n]*", "", step.group(1))):
        raise SetupError("step_d3_toward_d4 is not the +/-1-toward-target step fade_model() "
                         "transcribes")


def step_word(cur: int, tgt: int) -> int:
    """One Palette_DoFade `.word` iteration: each 3-bit channel (bits 1-3, 5-7, 9-11) one step
    toward the target's, the word REBUILT from the three channels (every other bit is 0)."""
    out = 0
    for sh in (1, 5, 9):
        c, t = (cur >> sh) & 7, (tgt >> sh) & 7
        c += 1 if c < t else -1 if c > t else 0
        out |= c << sh
    return out


def fade_model(start: list[int], target: list[int], k: int, frames: int) -> tuple[list[int], int]:
    """(lines 1-3 after the k-th compose since the arm, Pal_Fade_Frames after it). k >= 1."""
    cur = list(start)
    left = frames
    for _ in range(k):
        if left == 0:
            break
        left -= 1
        if left == 0:
            cur = list(target)                  # the snap copies Pal_Target verbatim
        elif left & 1:
            cur = [step_word(c, t) for c, t in zip(cur, target)]
    return cur, left


def channel_distance(a: list[int], b: list[int]) -> int:
    return max(max(abs(((x >> s) & 7) - ((y >> s) & 7)) for s in (1, 5, 9))
               for x, y in zip(a, b))


# ---- the emulator ------------------------------------------------------------------------

async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def rd(b, addr: int, n: int) -> int:
    return int(await read_bytes(b, addr, n), 16)


async def rd_words(b, addr: int, n: int) -> list[int]:
    raw = await read_bytes(b, addr, n * 2)
    if len(raw) != n * 4:
        raise SetupError(f"read_memory({addr:#x}) returned {len(raw) // 2} bytes, wanted {n * 2}")
    return [int(raw[i:i + 4], 16) for i in range(0, len(raw), 4)]


async def cram_lines_1_3(b) -> list[int]:
    out = []
    for line in (1, 2, 3):
        c = await _c(b, "emulator/read_cram", {"line": line})
        ents = next((v for v in c.values()
                     if isinstance(v, list) and v and isinstance(v[0], dict) and "raw" in v[0]),
                    None)
        if ents is None or len(ents) != 16:
            raise SetupError(f"read_cram line {line} returned no 16-entry list: {str(c)[:200]}")
        out += [int(e["raw"], 16) for e in ents]
    return out


class Rig:
    def __init__(self, b, sym, rows, half_w: int, half_h: int):
        self.b, self.sym, self.rows = b, sym, rows
        self.half_w, self.half_h = half_w, half_h
        self.upd = sym["GameState_OJZScroll_Update"]
        self.index = {r["addr"]: r["index"] for r in rows}
        self.tick_prev = None
        self.samples: list[dict] = []

    async def boot(self, boot_at: tuple[int, int] | None = None) -> None:
        b, sym = self.b, self.sym
        await _c(b, "emulator/reset", {})
        r = await _c(b, "emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Init"]),
                                             "maxFrames": BOOT_MAX_FRAMES})
        if not r.get("reached"):
            raise SetupError(f"run_to GameState_OJZScroll_Init never reached it: {r}")
        if boot_at:
            for nm, v, w in (("Boot_At_X", boot_at[0], 2), ("Boot_At_Y", boot_at[1], 2),
                             ("Boot_At_Flag", 1, 1)):
                await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
        r = await _c(b, "emulator/run_to", {"addr": hex(self.upd), "maxFrames": BOOT_MAX_FRAMES})
        if not r.get("reached"):
            raise SetupError(f"run_to GameState_OJZScroll_Update never reached it: {r}")
        self.tick_prev = await rd(b, sym["Logic_Tick"], 4)

    async def tick(self, max_frames: int = TICK_MAX_FRAMES) -> None:
        """Exactly one logic tick: one instruction off the Update entry, then back to it."""
        await _c(self.b, "emulator/step", {})
        r = await _c(self.b, "emulator/run_to", {"addr": hex(self.upd), "maxFrames": max_frames})
        if not r.get("reached"):
            raise SetupError(f"run_to GameState_OJZScroll_Update did not come round within "
                             f"{max_frames} frames: {r}")

    async def sample(self, tag: str, cram: bool = False) -> dict:
        b, sym = self.b, self.sym
        cx = (await rd(b, sym["Camera_X"], 4)) >> 16
        cy = (await rd(b, sym["Camera_Y"], 4)) >> 16
        tick = await rd(b, sym["Logic_Tick"], 4)
        s = {
            "tag": tag, "tick": tick, "frame": await rd(b, sym["Frame_Counter"], 2),
            "lag": await rd(b, sym["Lag_Frame_Count"], 4),
            "centre": (cx + self.half_w, cy + self.half_h),
            "region": await rd(b, sym["Region_Current"], 4),
            "frames": await rd(b, sym["Pal_Fade_Frames"], 1),
            "request": await rd(b, sym["Pal_Fade_Request"], 1),
            "active": await rd(b, sym["Pal_Active"], 1),
            "pal": await rd_words(b, sym["Palette_Buffer"] + 0x20, 48),
            "target": await rd_words(b, sym["Pal_Target"], 48),
        }
        if cram:
            s["cram"] = await cram_lines_1_3(b)
        s["dtick"] = None if self.tick_prev is None else tick - self.tick_prev
        self.tick_prev = tick
        s["row"] = self.index.get(s["region"])
        self.samples.append(s)
        return s

    async def hold(self, button: str | None) -> None:
        await _c(self.b, "emulator/release_all", {})
        if button:
            await _c(self.b, "emulator/hold", {"buttons": [button], "down": True})


def row_name(rows, addr) -> str:
    for r in rows:
        if r["addr"] == addr:
            return f"row {r['index']} [{r['x0']}..{r['x1']}]x[{r['y0']}..{r['y1']}]"
    return f"{addr:#x} (no row)"


async def walk(rig: Rig, button: str, done, tag: str) -> list[dict]:
    """Hold `button`, one sample per tick, until done(sample) has held for MARGIN_TICKS."""
    print(f"  leg `{tag}`: holding {button}", file=sys.stderr)
    await rig.hold(button)
    out, since = [], None
    for i in range(WALK_MAX_TICKS):
        await rig.tick()
        s = await rig.sample(f"{tag}{i}")
        out.append(s)
        if done(s):
            since = i if since is None else since
            if i - since >= MARGIN_TICKS:
                await rig.hold(None)
                return out
    await rig.hold(None)
    raise SetupError(f"leg `{tag}` held {button} for {WALK_MAX_TICKS} ticks without arriving "
                     f"(last centre {out[-1]['centre']}) — the route has gone stale")


# ---- the verdict -------------------------------------------------------------------------

def first(seq, pred, start=0):
    for i in range(start, len(seq)):
        if pred(seq[i]):
            return i
    return None


def check_fade_in(fails, leg, samples, i_arm, fade, start_pal, F, cram_after, who):
    """E2 + E3 for one crossing INTO the fade region at samples[i_arm]."""
    tgt = fade["pal"]
    s = samples[i_arm]
    if s["frames"] != F - 1 or s["target"] != tgt or s["request"] != 0:
        fails.append(f"{who}: on the arming tick Pal_Fade_Frames={s['frames']} (want F-1={F-1}), "
                     f"Pal_Fade_Request={s['request']} (want 0, consumed by the load), Pal_Target "
                     f"{'==' if s['target'] == tgt else '!='} the fade region's ep_pal")
    d = channel_distance(start_pal, tgt)
    k_vis = 2 * d - 1 if d else 0
    arrived = None
    for k in range(1, F + 3):
        j = i_arm + k - 1
        if j >= len(samples):
            fails.append(f"{who}: the leg ended {k - 1} composes after the arm, before k = F + 2")
            break
        want_pal, want_frames = fade_model(start_pal, tgt, k, F)
        got = samples[j]
        if got["row"] != fade["index"]:
            fails.append(f"{who}: the camera left the fade region {k - 1} composes after the "
                         "arm, so the fade was not observed whole — lengthen the route")
            break
        if got["pal"] != want_pal or got["frames"] != want_frames:
            bad = [n for n in range(48) if got["pal"][n] != want_pal[n]]
            fails.append(f"{who}: compose k={k} after the arm: Pal_Fade_Frames {got['frames']} "
                         f"(model {want_frames}); {len(bad)} word(s) differ from fade_model(), "
                         f"first at line {bad[0] // 16 + 1} entry {bad[0] % 16}: "
                         f"${got['pal'][bad[0]]:04X} vs ${want_pal[bad[0]]:04X}" if bad else
                         f"{who}: compose k={k}: Pal_Fade_Frames {got['frames']}, model {want_frames}")
            break
        if arrived is None and got["pal"] == tgt:
            arrived = k
    if arrived != k_vis:
        fails.append(f"{who}: the palette first equalled the target at compose k={arrived}; the "
                     f"step rule predicts k = 2*{d}-1 = {k_vis} for a max channel distance of {d}")
    j_end = i_arm + F - 1
    if j_end < len(samples):
        e = samples[j_end]
        if e["frames"] != 0 or (e["active"] & cram_after["PAL_ACT_FADE"]):
            fails.append(f"{who}: at k=F={F} Pal_Fade_Frames={e['frames']} and Pal_Active="
                         f"{e['active']:#04x} — the fade did not close at PAL_FADE_FRAMES")
    lo, hi = max(0, i_arm - 1), min(len(samples) - 1, i_arm + F)
    return {"distance": d, "k_visible_derived": k_vis, "k_visible_measured": arrived,
            # REPORTED, NOT ASSERTED: a lag frame here could be streaming's, not the fade's.
            "lag_frames_over_window": samples[hi]["lag"] - samples[lo]["lag"],
            "video_frames_over_window": (samples[hi]["frame"] - samples[lo]["frame"]) & 0xFFFF,
            "ticks_over_window": hi - lo}


async def run(args) -> int:
    F = src_const("engine/effects/palette.emp", "PAL_FADE_FRAMES")
    PAL_ACT_FADE = src_const("engine/effects/palette.emp", "PAL_ACT_FADE")
    SHIFT = src_const("engine/system/constants.emp", "SECTION_SIZE_SHIFT")
    HALF_W = src_const("engine/system/constants.emp", "CAM_SCREEN_HALF_W")
    HALF_H = src_const("engine/system/constants.emp", "CAM_SCREEN_HALF_H")
    FLY = src_const("games/sonic4/player/player_common.emp", "PLAYER_DEBUG_FLY_SPEED")
    SEC = 1 << SHIFT
    ep = preset_offsets()
    dofade_rule_check()

    sym = parse_lst(args.lst)
    for need in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update", "Boot_At_X",
                 "Boot_At_Y", "Boot_At_Flag", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag",
                 "Camera_X", "Camera_Y", "Region_Current", "Pal_Fade_Frames", "Pal_Fade_Request",
                 "Pal_Active", "Pal_Target", "Palette_Buffer", "Logic_Tick", "Frame_Counter",
                 "Lag_Frame_Count", "OJZ_Act1_Descriptor", "Parallax_CheckBoundary",
                 "Palette_Compose"):
        if need not in sym:
            raise SetupError(f"symbol {need} is not in {args.lst} — this witness needs the sonic4 "
                             "DEBUG listing")
    rom = Path(args.rom).read_bytes()
    try:
        rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])
    except region_table.LayoutError as e:
        raise SetupError(str(e)) from e

    def u16(a): return int.from_bytes(rom[a:a + 2], "big")
    def u32(a): return int.from_bytes(rom[a:a + 4], "big")
    for r in rows:
        p = r["effects"]
        r["transition"] = u16(p + ep["ep_transition"])
        r["pal_ptr"] = u32(p + ep["ep_pal"])
        r["pal"] = [u16(r["pal_ptr"] + 2 * n) for n in range(48)]

    report: dict = {"PAL_FADE_FRAMES": F, "rows": [
        {k: (hex(v) if k in ("addr", "effects", "parallax", "pal_ptr") else v)
         for k, v in r.items() if k != "pal"} for r in rows]}
    fails: list[str] = []
    findings: list[str] = []

    # ---- E0: the premise ------------------------------------------------------------------
    fading = [r for r in rows if r["transition"]]
    if not fading:
        fails.append("E0: no region row in OJZ act 1's table binds a preset with ep_transition != 0 "
                     "— there is no fade edge in this ROM, so nothing below can be measured. "
                     f"({len(rows)} rows, every ep_transition 0.)")
        return finish(args, report, fails, findings)
    if len(fading) != 1:
        raise SetupError(f"{len(fading)} rows arm the fade ({[r['index'] for r in fading]}); this "
                         "witness walks exactly one fade region — teach it which")
    fade = fading[0]
    y_c = 256                                # the DEBUG spawn's flight line (measured, re-checked below)
    if not fade["y0"] <= y_c <= fade["y1"]:
        raise SetupError(f"the fade region {row_name(rows, fade['addr'])} does not span the spawn's "
                         f"flight line y={y_c}, so a held RIGHT from the spawn never enters it")
    edge = fade["x0"]
    left = region_table.region_at(rows, edge - 1, y_c)
    right = region_table.region_at(rows, fade["x1"] + 1, y_c)
    if edge % SEC == 0:
        fails.append(f"E0: the fade region's left edge x={edge} lies ON the {SEC}-px section grid — "
                     "this witness exists to prove an edge that does not")
    if left is None or left["pal"] == fade["pal"]:
        fails.append(f"E0: the region left of x={edge} "
                     f"{'does not exist' if left is None else 'binds the SAME ep_pal'}, so the fade "
                     "cannot change a colour and nothing below would be visible")
    inside = [k * SEC for k in range(1, 64) if edge < k * SEC <= fade["x1"]]
    if not inside:
        fails.append(f"E0: no section line lies inside the fade region [{edge}..{fade['x1']}], so "
                     "`nothing arms at a section line the split did not cut` cannot be measured")
    shared = region_table.region_at(rows, left["x0"] - 1, y_c) if left and left["x0"] else None
    if shared is None or shared["pal"] != left["pal"]:
        fails.append("E0: the region left of the left region does not share its ep_pal, so the "
                     "shared-palette crossing (E6) has no subject on this route")
    if fails:
        return finish(args, report, fails, findings)
    report["route"] = {"fade_row": fade["index"], "edge_x": edge, "fade_x1": fade["x1"],
                       "section_lines_inside": inside, "left_row": left["index"],
                       "right_row": None if right is None else right["index"],
                       "shared_row": shared["index"], "y": y_c,
                       "fade_distance_from_left": channel_distance(left["pal"], fade["pal"])}

    inst = AetherInstance(args.rom, symbols=args.lst)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise SetupError(str(e)) from e
    b = BusClient(socket_path=sock, client_id="regionfade", client_name="region_fade_witness")
    try:
        await b.connect()
        for m in ("emulator/step", "emulator/run_to", "emulator/hold", "emulator/release_all",
                  "emulator/read_cram", "emulator/write_memory", "emulator/registers",
                  "emulator/read_vdp_registers"):
            if not b.supports(m):
                raise SetupError(f"the server does not advertise `{m}`")
        await _c(b, "emulator/load_symbols", {"path": args.lst})
        rig = Rig(b, sym, rows, HALF_W, HALF_H)
        await rig.boot()
        for _ in range(3):
            await rig.tick()
        s0 = await rig.sample("spawn", cram=True)
        if s0["centre"][1] != y_c:
            raise SetupError(f"the spawn's camera centre is {s0['centre']}, not on y={y_c} — the "
                             "route's flight line has moved")

        # ---- leg OUT: right from the spawn, past the fade region's right edge ----------------
        stop_x = (fade["x1"] + 1 if right else fade["x1"]) + 1
        out = await walk(rig, "right", lambda s: s["centre"][0] >= stop_x, "out")
        # the flight check: the camera moves FLY px a tick once it is tracking
        steps = [b_["centre"][0] - a_["centre"][0] for a_, b_ in zip(out, out[1:])]
        if max(steps) != FLY:
            raise SetupError(f"the held RIGHT moved the camera centre at most {max(steps)} px a tick, "
                             f"not PLAYER_DEBUG_FLY_SPEED = {FLY} — this is not debug flight")
        # ---- leg BACK: left, past the shared-palette line --------------------------------------
        back = await walk(rig, "left", lambda s: s["centre"][0] < left["x0"] - 1, "back")
        settle = []
        for i in range(4):
            await rig.tick()
            settle.append(await rig.sample(f"home{i}", cram=True))

        walk_all = [s0] + out + back
        # every sample: one tick, and the engine's region is the table's region at the centre
        for s in walk_all[1:]:
            if s["dtick"] != 1:
                fails.append(f"sample {s['tag']}: Logic_Tick advanced {s['dtick']} since the last "
                             "sample, not 1 — k composes and k samples are no longer the same count")
                break
        for s in walk_all:
            phys = region_table.region_at(rows, *s["centre"])
            if phys is None or phys["addr"] != s["region"]:
                fails.append(f"sample {s['tag']}: Region_Current {row_name(rows, s['region'])} but "
                             f"the table puts centre {s['centre']} in "
                             f"{'no row' if phys is None else row_name(rows, phys['addr'])}")
                break

        # ---- E6 (outbound): the shared-palette line at left['x0'] ------------------------------
        i6 = first(walk_all, lambda s: s["row"] == left["index"])
        if i6 is None:
            raise SetupError("the walk never entered the left region")
        before, after = walk_all[i6 - 1], walk_all[i6]
        if before["row"] != shared["index"]:
            raise SetupError(f"the tick before the left region was {before['tag']} in row "
                             f"{before['row']}, not the shared row {shared['index']}")
        for s in walk_all[max(0, i6 - 3):i6 + 4]:
            if s["pal"] != shared["pal"] or s["frames"] or s["request"]:
                fails.append(f"E6: around the shared-palette crossing at x={left['x0']} sample "
                             f"{s['tag']} reads frames={s['frames']} request={s['request']} and a "
                             f"palette {'equal to' if s['pal'] == shared['pal'] else 'DIFFERENT from'} "
                             "the shared ep_pal")
                break

        # ---- E1 + E2 + E3 (outbound): the fade edge ------------------------------------------
        ia = first(walk_all, lambda s: s["row"] == fade["index"])
        if ia is None:
            raise SetupError("the walk never entered the fade region")
        pre = walk_all[ia - 1]
        for s in walk_all[:ia]:
            if s["frames"] or s["request"] or s["pal"] != (shared["pal"] if s["row"] == shared["index"]
                                                           else left["pal"]):
                fails.append(f"E1: before the edge, sample {s['tag']} (centre {s['centre']}) reads "
                             f"frames={s['frames']} request={s['request']} or a palette that is not "
                             "its region's ep_pal — something armed before the edge")
                break
        if not (pre["centre"][0] < edge <= walk_all[ia]["centre"][0]):
            fails.append(f"E2: the fade region became current at centre x={walk_all[ia]['centre'][0]} "
                         f"with the previous tick at x={pre['centre'][0]}; the authored edge is "
                         f"x={edge}, so the switch did not happen AT the edge")
        report["fade_in_out"] = check_fade_in(fails, "out", walk_all, ia, fade, pre["pal"], F,
                                              {"PAL_ACT_FADE": PAL_ACT_FADE}, "E3 outbound")
        report["fade_in_out"]["arm_centre_x"] = walk_all[ia]["centre"][0]
        report["fade_in_out"]["frames_by_k"] = [walk_all[ia + k]["frames"] for k in range(F + 1)]
        report["fade_in_out"]["distance_by_k"] = [channel_distance(walk_all[ia + k]["pal"], fade["pal"])
                                                  for k in range(F + 1)]

        # ---- E4: the section line(s) inside the fade region ---------------------------------
        for line_x in inside:
            j = first(walk_all, lambda s: s["centre"][0] >= line_x, ia)
            win = walk_all[j - 3:j + 4]
            for s in win:
                if s["row"] != fade["index"] or s["request"] or s["frames"] or s["pal"] != fade["pal"]:
                    fails.append(f"E4: crossing the section line x={line_x} inside the fade region, "
                                 f"sample {s['tag']} reads row {s['row']}, request {s['request']}, "
                                 f"frames {s['frames']}, palette "
                                 f"{'== ' if s['pal'] == fade['pal'] else '!= '}the fade ep_pal")
                    break
            report.setdefault("section_lines", []).append(
                {"x": line_x, "samples": [(s["centre"][0], s["row"], s["frames"]) for s in win]})

        # ---- E5 (outbound): out of the fade region at its right edge ------------------------
        if right is not None:
            ir = first(walk_all, lambda s: s["row"] == right["index"], ia)
            s = walk_all[ir]
            if right["transition"] == 0:
                if s["pal"] != right["pal"] or s["frames"]:
                    fails.append(f"E5: into row {right['index']} (ep_transition 0) at x={fade['x1'] + 1}: "
                                 f"frames {s['frames']}, palette "
                                 f"{'==' if s['pal'] == right['pal'] else '!='} its ep_pal on the "
                                 "first compose — it did not SNAP")
            report["exit_right"] = {"centre_x": s["centre"][0], "frames": s["frames"],
                                    "snapped": s["pal"] == right["pal"]}

        # ---- the return leg: into the fade region from the right, out through the edge -------
        nb = len([s0] + out)
        if right is not None:
            ib = first(walk_all, lambda s: s["row"] == fade["index"], nb)
            report["fade_in_back"] = check_fade_in(
                fails, "back", walk_all, ib, fade, walk_all[ib - 1]["pal"], F,
                {"PAL_ACT_FADE": PAL_ACT_FADE}, "E3 inbound (from the right)")
            report["fade_in_back"]["arm_centre_x"] = walk_all[ib]["centre"][0]
        il = first(walk_all, lambda s: s["row"] == left["index"], nb)
        s = walk_all[il]
        if not (walk_all[il - 1]["centre"][0] >= edge > s["centre"][0]):
            fails.append(f"E5: the left region became current at x={s['centre'][0]} with the "
                         f"previous tick at x={walk_all[il - 1]['centre'][0]} — not at the edge x={edge}")
        if left["transition"] == 0 and (s["pal"] != left["pal"] or s["frames"]):
            fails.append(f"E5: back across x={edge} into row {left['index']}: frames {s['frames']}, "
                         "palette not its ep_pal on the first compose — it did not SNAP back")
        report["exit_left"] = {"centre_x": s["centre"][0], "frames": s["frames"],
                               "snapped": s["pal"] == left["pal"]}
        i6b = first(walk_all, lambda s: s["row"] == shared["index"], il)
        for s in walk_all[max(il, i6b - 3):i6b + 4]:
            if s["pal"] != shared["pal"] or s["frames"] or s["request"]:
                fails.append(f"E6: inbound shared-palette crossing, sample {s['tag']} changed colour "
                             "or armed")
                break

        # ---- CRAM, settled: real output, not only the buffer -----------------------------
        if s0["cram"] != shared["pal"]:
            fails.append("E1/CRAM: at the spawn CRAM lines 1-3 are not the spawn region's ep_pal")
        if settle[-1]["cram"] != shared["pal"]:
            fails.append("E6/CRAM: home again, CRAM lines 1-3 are not the home region's ep_pal")

        # ---- the settled CRAM inside the fade region: fly back in and stop -----------------
        await walk(rig, "right", lambda s: s["centre"][0] >= edge + FLY * (F + 4), "in")
        for _ in range(4):
            await rig.tick()
        sin = await rig.sample("in-settled", cram=True)
        if sin["cram"] != fade["pal"] or sin["pal"] != fade["pal"]:
            fails.append("E3/CRAM: settled inside the fade region, CRAM lines 1-3 "
                         f"{'==' if sin['cram'] == fade['pal'] else '!='} its ep_pal and the buffer "
                         f"{'==' if sin['pal'] == fade['pal'] else '!='} it")

        # ---- W: a warp INSIDE the already-cached fade region -----------------------------
        wx = edge + (fade["x1"] - edge) // 2
        await _c(b, "emulator/write_memory", {"addr": hex(sym["Warp_Req_X"]), "value": wx, "width": 2})
        await _c(b, "emulator/write_memory", {"addr": hex(sym["Warp_Req_Y"]), "value": y_c, "width": 2})
        await _c(b, "emulator/write_memory", {"addr": hex(sym["Warp_Req_Flag"]), "value": 1, "width": 1})
        wtrace = []
        for i in range(F + 4):
            # The warp tick refills the whole tile-cache window and redraws both planes
            # synchronously (Debug_Warp_Consume), which takes many video frames; only that
            # tick gets the long ceiling.
            await rig.tick(WARP_MAX_FRAMES if i == 0 else TICK_MAX_FRAMES)
            wtrace.append(await rig.sample(f"warp{i}"))
        flag = await rd(b, sym["Warp_Req_Flag"], 1)
        moved = any(s["pal"] != fade["pal"] for s in wtrace)
        armed = [s["frames"] for s in wtrace]
        report["warp_inside_cached"] = {"to": [wx, y_c], "flag_after": flag,
                                        "frames_by_tick": armed, "colour_moved": moved,
                                        "region_rows": [s["row"] for s in wtrace]}
        findings.append(f"W: a DEBUG warp to ({wx},{y_c}), inside the fade region the crossing had "
                        f"already cached: Pal_Fade_Frames by tick {armed[:6]}...; "
                        f"{'a fade ARMED (the sentinel forced a re-install)' if any(armed) else 'nothing armed'}; "
                        f"colour {'MOVED' if moved else 'did not move'}; Warp_Req_Flag {flag} after")

        # ---- C: cost of the crossing, by master clock -----------------------------------
        cost = await measure_costs(rig, b, sym, rows, fade, left, edge, FLY, F)
        report["cost"] = cost

        # ---- R: reversal mid-fade --------------------------------------------------------
        rev = await reversal(rig, b, sym, rows, fade, left, edge, FLY, F)
        report["reversal"] = rev
        exact = rev["settled_pal_is"] == "left"
        findings.append(
            f"R: crossed into the fade region, turned back after {REVERSAL_AFTER} ticks "
            f"(Pal_Fade_Frames {rev['frames_at_turn']}), re-entered row {left['index']} at tick "
            f"{rev['reentry_k']} after the arm; {SETTLE_TICKS} ticks later the palette buffer is "
            f"{rev['settled_pal_is'].upper()}'s ep_pal and CRAM is {rev['settled_cram_is'].upper()}'s"
            f"{'' if exact else ' — the fade in flight survived the crossing back and finished on the region the camera LEFT'}")
        if args.strict_reversal and not exact:
            fails.append(f"R (--strict-reversal): after a mid-fade reversal into row {left['index']} "
                         f"the palette settled to {rev['settled_pal_is']}'s ep_pal, not the region's own")

        # ---- B: boot straight into the fade region ---------------------------------------
        report["boot_into_fade"] = await boot_into(rig, b, sym, rows, fade, left, wx, y_c, F)
        bi = report["boot_into_fade"]
        findings.append(f"B: booted at ({wx},{y_c}) inside the fade region: " + bi["summary"])
    finally:
        try:
            await b.close()
        finally:
            inst.reap()
    report["walk"] = [{k: v for k, v in s.items() if k not in ("pal", "target", "cram")}
                      for s in rig.samples]
    return finish(args, report, fails, findings)


async def mclk_window(b, sym, entry: str, max_frames: int = 4) -> int:
    """68000 cycles from `entry` to its return (master clock / 7). The return address is read
    off the stack at entry; any interrupt taken inside the window is included."""
    r = await _c(b, "emulator/run_to", {"addr": hex(sym[entry]), "maxFrames": max_frames})
    if not r.get("reached"):
        raise SetupError(f"run_to {entry} never reached it: {r}")
    m0 = r["mclk"]
    sp = int((await _c(b, "emulator/registers", {}))["a7"], 16) & 0xFFFFFF
    ret = await rd(b, sp, 4) & 0xFFFFFF
    r = await _c(b, "emulator/run_to", {"addr": hex(ret), "maxFrames": max_frames})
    if not r.get("reached"):
        raise SetupError(f"{entry} did not return to ${ret:06X}: {r}")
    return (r["mclk"] - m0) // 7


async def measure_costs(rig, b, sym, rows, fade, left, edge, FLY, F) -> dict:
    """Fly to a few ticks short of the edge, then measure CheckBoundary + Compose per tick
    across the crossing and the fade, then a quiet tick. Each tick is: CheckBoundary's window,
    then Compose's window, then back to the Update entry."""
    await rig.boot()
    await walk(rig, "right", lambda s: s["centre"][0] >= edge - FLY * 4 - MARGIN_TICKS * FLY,
               "costpre")
    await rig.hold("right")
    rowsout = []
    for i in range(F + 10):
        cb = await mclk_window(b, sym, "Parallax_CheckBoundary")
        pc = await mclk_window(b, sym, "Palette_Compose")
        r = await _c(b, "emulator/run_to", {"addr": hex(rig.upd), "maxFrames": TICK_MAX_FRAMES})
        if not r.get("reached"):
            raise SetupError("cost walk lost the Update entry")
        cx = ((await rd(b, sym["Camera_X"], 4)) >> 16) + rig.half_w
        rowsout.append({"centre_x": cx, "region": rig.index.get(await rd(b, sym["Region_Current"], 4)),
                        "frames": await rd(b, sym["Pal_Fade_Frames"], 1),
                        "checkboundary": cb, "compose": pc,
                        "lag": await rd(b, sym["Lag_Frame_Count"], 4)})
    await rig.hold(None)
    return {"ticks": rowsout,
            "note": "68000 cycles = master clock / 7, entry to return, interrupts inside the "
                    "window included; one row per logic tick"}


async def reversal(rig, b, sym, rows, fade, left, edge, FLY, F) -> dict:
    await rig.boot()
    await walk(rig, "right", lambda s: s["row"] == fade["index"], "revpre")
    # walk() stops MARGIN_TICKS after arriving; that is past the fade. Go back out and set up.
    await walk(rig, "left", lambda s: s["centre"][0] < edge - FLY * 3, "revout")
    await rig.hold("right")
    arm = None
    turn = None
    trace = []
    for i in range(80):
        await rig.tick()
        s = await rig.sample(f"rev{i}")
        trace.append(s)
        if arm is None and s["row"] == fade["index"]:
            arm = i
        if arm is not None and turn is None and i - arm >= REVERSAL_AFTER - 1:
            turn = i
            await rig.hold("left")
        if turn is not None and s["row"] == left["index"] and i > turn:
            reentry = i
            break
    else:
        raise SetupError("the reversal never re-entered the left region")
    await rig.hold(None)
    for i in range(SETTLE_TICKS):
        await rig.tick()
        trace.append(await rig.sample(f"revset{i}"))
    fin = await rig.sample("rev-final", cram=True)

    def who(p):
        return "left" if p == left["pal"] else "fade" if p == fade["pal"] else "neither"
    return {"frames_at_turn": trace[turn]["frames"], "reentry_k": reentry - arm + 1,
            "frames_at_reentry": trace[reentry]["frames"],
            "settled_pal_is": who(fin["pal"]), "settled_cram_is": who(fin["cram"]),
            "row_after": fin["row"],
            "frames_trace": [(s["row"], s["frames"], channel_distance(s["pal"], left["pal"]))
                             for s in trace[arm:reentry + 20]]}


async def boot_into(rig, b, sym, rows, fade, left, bx, by, F) -> dict:
    """Boot with the mailbox aimed inside the fade region; read the palette buffer, the
    fade state and CRAM at the init's exit (before any Parallax_CheckBoundary) and on the next
    ticks, each labelled with the video frame it was read on."""
    await rig.boot((bx, by))
    rig.tick_prev = None
    out = []
    async def display_on() -> bool:
        """VDP register $01 bit 6 (DISP), read off the VDP itself — not the RAM shadow, and not
        the server's `status.display`, which is about the emulator's window."""
        v = await _c(b, "emulator/read_vdp_registers", {})
        return bool(int(v["raw"][1], 16) & 0x40)
    s = await rig.sample("boot-exit", cram=True)
    s["display"] = await display_on()
    out.append(s)
    for i in range(F + 2):
        await rig.tick()
        s = await rig.sample(f"boot{i}", cram=True)
        s["display"] = await display_on()
        out.append(s)

    def who(p):
        return "OJZ-left" if p == left["pal"] else "fade" if p == fade["pal"] else "between"
    rowsout = [{"tag": s["tag"], "frame": s["frame"], "display": s["display"], "row": s["row"],
                "fade_frames": s["frames"],
                "buffer": who(s["pal"]), "cram": who(s["cram"]),
                "cram_distance_to_fade": channel_distance(s["cram"], fade["pal"])} for s in out]
    first_fade_cram = next((r["tag"] for r in rowsout if r["cram"] == "fade"), None)
    summary = (f"at the init's exit (the first Update entry, before any Parallax_CheckBoundary) "
               f"the buffer is {rowsout[0]['buffer']} and CRAM {rowsout[0]['cram']} with the VDP's "
               f"display {'ON' if rowsout[0]['display'] else 'OFF'}; next ticks CRAM = "
               + ", ".join(f"{r['tag']}@f{r['frame']}:{r['cram']}/{r['fade_frames']}" for r in rowsout[1:6])
               + f"; CRAM first equals the fade ep_pal at {first_fade_cram}")
    return {"rows": rowsout, "summary": summary}


def finish(args, report, fails, findings) -> int:
    report["fails"] = fails
    report["findings"] = findings
    if args.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        r = report.get("route")
        if r:
            print(f"region_fade_witness: fade row {r['fade_row']} [{r['edge_x']}..{r['fade_x1']}] at "
                  f"y={r['y']}; left row {r['left_row']}, right row {r['right_row']}, shared-palette "
                  f"row {r['shared_row']}; section line(s) inside: {r['section_lines_inside']}")
            print(f"  PAL_FADE_FRAMES = {report['PAL_FADE_FRAMES']}; max channel distance "
                  f"left->fade = {r['fade_distance_from_left']}")
        for key in ("fade_in_out", "fade_in_back"):
            f = report.get(key)
            if f:
                print(f"  {key}: armed at centre x={f['arm_centre_x']}; target reached at compose "
                      f"k={f['k_visible_measured']} (derived 2*{f['distance']}-1 = "
                      f"{f['k_visible_derived']}); over the window {f['ticks_over_window']} ticks "
                      f"took {f['video_frames_over_window']} video frames, "
                      f"{f['lag_frames_over_window']} lag frame(s)"
                      + (f"; Pal_Fade_Frames by k: {f['frames_by_k']}" if "frames_by_k" in f else "")
                      + (f"; distance to target by k: {f['distance_by_k']}" if "distance_by_k" in f else ""))
        for key in ("exit_right", "exit_left"):
            if key in report:
                print(f"  {key}: {report[key]}")
        for sl in report.get("section_lines", []):
            print(f"  section line x={sl['x']} inside the fade region: (centre_x, row, fade_frames) "
                  f"{sl['samples']}")
        c = report.get("cost")
        if c:
            print("  cost (68000 cycles; entry->return, interrupts included):")
            for t in c["ticks"]:
                print(f"    centre x={t['centre_x']:5d} row {t['region']} fade {t['frames']:2d}  "
                      f"CheckBoundary {t['checkboundary']:6d}  Compose {t['compose']:6d}  lag {t['lag']}")
        rv = report.get("reversal")
        if rv:
            print(f"  reversal trace (row, fade_frames, distance-to-left): {rv['frames_trace']}")
        bi = report.get("boot_into_fade")
        if bi:
            for row in bi["rows"]:
                print(f"  boot: {row}")
        for f in findings:
            print(f"FINDING {f}")
    if fails:
        print("FAIL:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("region_fade_witness: PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict-reversal", action="store_true",
                    help="assert that a mid-fade reversal settles to the returned-to region's own palette")
    args = ap.parse_args()
    try:
        return asyncio.run(run(args))
    except SetupError as e:
        print(f"SETUP ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
