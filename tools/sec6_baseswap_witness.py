#!/usr/bin/env python3
"""sec6_baseswap_witness — does a RUNNING MACHINE obey the GENERATED base-swap program?

EFFECTS-W1 DoD item 11a's certification, and the precise gap its two landings left open.

WHAT WAS ALREADY PROVEN, so this is not a duplicate:
  * `tools/plane_base_swap_gate.py` reads `OJZ_BaseSwap` — the HAND-AUTHORED, DEBUG-ONLY
    demo — out of the ROM image and checks its 11 words against an independently derived
    expectation. Its own docstring states the limit: "it does NOT prove the VDP draws Plane
    B's map in the Plane-A layer at scanline 160."
  * item 11a's authorable half made the swap a preset-document key and bound it to OJZ act 1
    section 6. Nothing watched a machine obey THAT program. `tools/ramp_authored_witness.py`
    is the closest precedent (item 6, "an authored document moved the picture"), and it
    installs its subject by poking `Raster_Pending`; the subject here is a SECTION BINDING,
    so the debug arm below never pokes to install.

THE SUBJECT is `EditorRaster_OJZ_Act1_ojz_sec6_baseswap`, lowered by `tools/effects_gen.py`
from `games/sonic4/data/editor/effects/presets/ojz_sec6_baseswap.json`
(`base_swap = {line, target}`) and bound to section 6 by that section's `rasterRef` sidecar.
It is NOT `OJZ_BaseSwap`, and telling the two apart is this instrument's whole job.

================================================================================
HOW IT DISTINGUISHES THE GENERATED PROGRAM FROM THE HAND-WRITTEN DEMO — three ways,
and each one alone would be enough:

  1. BY ADDRESS. `Raster_Program` is read out of work RAM after the crossing and must equal
     the address of `EditorRaster_OJZ_Act1_<preset id>` and MUST NOT equal `OJZ_BaseSwap`'s.
     Both are resolved from the listing, never typed. The demo's only installer is
     `Debug_BandDemoHotkey`; no arm here presses a key or writes `Debug_Scene_Index` (which
     would be VACUOUS anyway — it is a counter the hotkey installs FROM).
  2. BY THE PATH. The debug arm reaches section 6 through the engine's own crossing
     (`Debug_Warp_Consume` -> `Parallax_CheckBoundary` -> `Effects_InstallPreset` ->
     `Raster_Install`), and the picture arm proves the poke it later uses is a NO-OP against
     that already-installed program (arm D4 below): treated-with-poke and treated-without-poke
     are byte-identical frames.
  3. BY CONSTRUCTION, IN THE RELEASE SHAPE. `OJZ_BaseSwap` emits ZERO bytes in `s4.bin` —
     its label collapses onto its neighbour's address, which this file ASSERTS rather than
     assumes — while the generated program is unconditional there. A base swap observed in
     the release shape cannot be the demo, because the demo is not in the ROM.

THE CONTROL TRAP THIS INSTRUMENT IS BUILT AROUND. `OJZ_BaseSwap` re-points Plane A below its
own line. A predecessor lane held it installed as a "constant" control on an unrelated
measurement and contaminated every sample below line 160; the rule looked like it failed on
"some" lines, and the contiguous failure region was really the control's own boundary. So:
NO ARM HERE INSTALLS THE DEMO, in any shape, ever. The control is the SAME scene with the
program REMOVED (`Raster_Program_None`, the engine's own uninstall sentinel), which cannot
manufacture the treatment result — a removal has no line of its own.

================================================================================
THE TWO INSTRUMENTS. Neither is a screenshot for a human to squint at.

  I. PLANE-BASE READBACK (which nametable is Plane A actually on, right now?)
     The bus exposes no VDP register space — `emulator/read` serves bus/vram/cram/vsram and
     there is no register method (measured against oracle's `MethodSpec` table). But
     `emulator/pixel_attribution` resolves the winning layer's nametable CELL through
     `render.rs::plane_a_base()`, which reads the LIVE `regs()[0x02]`. So: mask every layer
     but Plane A (a display mask; the machine is untouched), stop at a scanline, sample a run
     of 32 dots 8 px apart — one per cell — and search BOTH decoded nametables (read out of
     VRAM at `VRAM_PLANE_A` and at the preset's `target`) for that run. A run found in
     exactly one map names the base the register currently holds. Found in both, or neither,
     or too few dots resolved: UNMEASURABLE, never a verdict.

 II. PICTURE DIFFERENTIAL (does the frame change, and exactly where?)
     From ONE checkpoint, restore and run the same frame count twice: once with the program
     installed, once with it removed. Everything else — camera, VRAM, sprite phase, lag — is
     bit-identical by construction, so a per-line diff of the two frames is the program's
     footprint and nothing else.

     ⚠ MEASURED TRAP, and it silently deletes the entire subject: `emulator/scanlines`
     returns the raster-latched frame ONLY when no layer is masked. oracle's `framebuffer()`
     says so in as many words — "a masked read cannot use the latched frame" — and falls back
     to a post-hoc state render, which is blind to every mid-frame effect. The first draft of
     this file masked sprites for a cleaner diff and got `source: "stateRender"` back. So the
     picture arm runs UNMASKED and asserts it (`grab` refuses on any other source), and the
     masks used by instrument I are applied only after every capture is taken.

     ⚠ SECOND TRAP, the one the checkpoint itself creates: THE ABSOLUTE FRAME INDEX REWINDS
     at every restore (oracle 91b21a8, 2026-09-03). Logic gated on a strictly ADVANCING frame
     index silently does nothing across a rewind instead of failing — and "no change observed"
     then reads exactly like a real negative. Nothing here is gated on one: every arm measures
     a `run_frames` DELTA inside a single uninterrupted window, `Shape.rebaseline` re-reads the
     index after each restore and REFUSES if the machine did not land back on the checkpoint's
     own frame, and the run asserts that every arm it compares advanced the SAME number of
     frames. So a negative from this instrument is a negative, not a rewind.

================================================================================
EXPECTATIONS ARE DERIVED, NEVER TYPED:
  * the authored line L and target T          the preset JSON the sidecar names
  * that the sidecar and the generated chooser agree, and that the chooser's arm is the
    label `effects_gen` emits for that preset id
  * `VRAM_PLANE_A`                            engine/system/constants.emp
  * `SECTION_SIZE_SHIFT`, `SCREEN_WIDTH/HEIGHT`, `GRID_W/H`   constants + act descriptor
  * `EffectsPreset.ep_raster`'s offset        engine/effects/preset.emp's struct
  * THE ONE-LINE WINDOW. The first line the swap can affect is L or L+1, and that window is
    the tree's own, not this file's: item 11a's DEFERRED_WORK block states it ("the boundary
    may land on line 160 or 161") from `raster.emp`'s row-119 note — the blanking spin guards
    the CRAM paths only, so a bare `OP_SET_REG` switches its register partway across the
    fire+1 line. This instrument REPORTS which of the two it measured and fails outside the
    window; it does not fit to the value it saw.

WHAT IT DOES NOT PROVE, stated so a green is not over-read:
  * The RELEASE arm cannot reach section 6 — the warp mailbox (`Warp_Req_*`) is DEBUG-only,
    and it is absent from `s4.lst`. So release installs the generated program by poking
    `Raster_Pending`. The release BINDING is instead proved statically, by reading
    `OJZ_Preset_Sec6.ep_raster` out of the running release ROM and requiring it to be the
    generated label — the same record the debug arm watches the crossing install.
  * It samples ONE act, ONE section, ONE warp point.
  * `run_to_scanline` stops when the raster reaches a line; the base readback is therefore a
    statement about the register at that stop, and the PICTURE arm is what pins the first
    line actually drawn differently. The two must agree, and that agreement is asserted.

USAGE
    python3 tools/sec6_baseswap_witness.py --rom s4.debug.bin --lst s4.debug.lst \
        [--release-rom s4.bin --release-lst s4.lst] [--json OUT.json]
    --shapes debug|release|both   (default: both)

EXIT 0 = measured and every derived expectation met.  1 = measured, something did not match.
2 = REFUSED (unmeasurable) — nothing about the base swap follows either way.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402
from fg_left_edge_capture import grab  # noqa: E402  (refuses unless source == "raster")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT_DIR = os.path.join("games", "sonic4", "data", "editor", "ojz", "act1")
PRESETS_DIR = os.path.join("games", "sonic4", "data", "editor", "effects", "presets")
GENERATED = os.path.join("games", "sonic4", "data", "generated", "ojz", "act1", "effects_scenes.emp")
DESCRIPTOR = os.path.join("games", "sonic4", "data", "levels", "ojz", "act1", "act_descriptor.emp")
CONSTANTS = os.path.join("engine", "system", "constants.emp")
PRESET_STRUCT = os.path.join("engine", "effects", "preset.emp")
CHOOSER = "ojz_act1_sec_raster"
RASTER_REF_KEY = "rasterRef"
SECTION = 6
PRESET_SYM = "OJZ_Preset_Sec6"
DEMO_SYM = "OJZ_BaseSwap"
DEMO_NEIGHBOUR = "OJZ_TestPal"      # the label OJZ_BaseSwap collapses onto when it emits nothing
ACTIVE_H = 224
NAMETABLE_BYTES = 0x2000            # 64x64 cells x 2 bytes — the plane size this engine uses
PLANE_COLS = PLANE_ROWS = 64
DOTS = 32                           # cells sampled per scanline; 32 x 8 px = 256 of 320
# Below this many resolved dots a row is UNMEASURABLE, not a verdict. 16 rather than 32
# because a foreground line is rarely opaque all the way across (measured: 22 of 32 at the
# boundary line of the debug arm's warp point) — and 16 is not a weak fingerprint: each
# resolved dot must match at its own exact wrapped offset in a candidate row, and a run that
# matches BOTH nametables, or neither, is refused as ambiguous rather than resolved.
MIN_RESOLVED = 16
MAX_WALK_UP = 24                    # how far above the boundary to look for a measurable line

EXIT_OK, EXIT_MISMATCH, EXIT_REFUSED = 0, 1, 2


class Refused(SystemExit):
    def __init__(self, why: str):
        super().__init__(EXIT_REFUSED)
        self.why = why


def refuse(why: str) -> "Refused":
    print(f"REFUSED: {why}")
    return Refused(why)


# ------------------------------------------------------------------ derivations (pure)

def parse_const(text: str, name: str, where: str) -> int:
    m = re.search(r"^\s*(?:pub\s+)?const\s+" + re.escape(name) + r"\s*=\s*(\$?[0-9A-Fa-f]+)", text, re.M)
    if not m:
        raise refuse(f"could not parse `{name}` out of {where}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def struct_field_offset(text: str, struct: str, field: str, where: str) -> int:
    """`field: <type> @ $NN` inside `struct <struct> (...) { ... }`.

    Read from the DECLARATION rather than typed, for `plane_base_swap_gate`'s reason: the
    release arm reads a pointer at this offset out of the shipped ROM, and an offset that
    silently drifted would read a neighbouring field and compare it against a label address
    — a mismatch that is really a parse failure.
    """
    m = re.search(r"struct\s+" + re.escape(struct) + r"\s*\([^)]*\)\s*\{(.*?)\n\}", text, re.S)
    if not m:
        raise refuse(f"could not find `struct {struct}` in {where}")
    f = re.search(r"^\s*" + re.escape(field) + r"\s*:[^@\n]*@\s*\$([0-9A-Fa-f]+)", m.group(1), re.M)
    if not f:
        raise refuse(f"`struct {struct}` in {where} has no `{field}: ... @ $NN` field")
    return int(f.group(1), 16)


def geometry(repo: str) -> dict:
    consts = open(os.path.join(repo, CONSTANTS), encoding="utf-8").read()
    desc = open(os.path.join(repo, DESCRIPTOR), encoding="utf-8").read()
    shift = parse_const(consts, "SECTION_SIZE_SHIFT", CONSTANTS)
    return {"shift": shift, "size": 1 << shift,
            "screen_w": parse_const(consts, "SCREEN_WIDTH", CONSTANTS),
            "screen_h": parse_const(consts, "SCREEN_HEIGHT", CONSTANTS),
            "grid_w": parse_const(desc, "GRID_W", DESCRIPTOR),
            "grid_h": parse_const(desc, "GRID_H", DESCRIPTOR),
            "plane_a": parse_const(consts, "VRAM_PLANE_A", CONSTANTS)}


def sidecar_ref(repo: str, sec: int):
    path = os.path.join(repo, ACT_DIR, f"section_{sec}.meta.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get(RASTER_REF_KEY), path


def load_preset(repo: str, pid: str):
    d = os.path.join(repo, PRESETS_DIR)
    for name in sorted(os.listdir(d)):
        if name.endswith(".json"):
            p = os.path.join(d, name)
            with open(p, encoding="utf-8") as fh:
                doc = json.load(fh)
            if doc.get("id") == pid:
                return doc, p
    raise refuse(f"{RASTER_REF_KEY} {pid!r} names no preset document under {PRESETS_DIR}")


def base_swap_expectation(preset: dict, where: str, plane_a: int) -> dict:
    bs = preset.get("base_swap")
    if not isinstance(bs, dict):
        raise refuse(f"{where}: this instrument measures a `base_swap` preset; that document "
                     f"carries {sorted(preset)} — extend it, do not guess")
    line, target = bs.get("line"), bs.get("target")
    if not isinstance(line, int) or not isinstance(target, int):
        raise refuse(f"{where}: base_swap.line/target must be integers, got {line!r}/{target!r}")
    if target == plane_a:
        raise refuse(f"{where}: base_swap.target ${target:04X} IS Plane A's own nametable "
                     f"(VRAM_PLANE_A) — re-pointing Plane A at itself is invisible on screen, so "
                     f"there is nothing for this instrument to see. The generator's own ensure "
                     f"refuses this too; seeing it here means that check is no longer running")
    if not 0 < line < ACTIVE_H:
        raise refuse(f"{where}: base_swap.line {line} is not inside the {ACTIVE_H}-line display")
    return {"preset_id": preset["id"], "line": line, "target": target,
            # THE WINDOW, and its provenance is the tree's, not this file's: item 11a's
            # DEFERRED_WORK block reads "the boundary may land on line 160 or 161", from
            # raster.emp's row-119 note that the blanking spin guards the CRAM paths only.
            "first_window": (line, line + 1)}


def chooser_binding(repo: str, sec: int):
    text = open(os.path.join(repo, GENERATED), encoding="utf-8").read()
    m = re.search(r"pub comptime fn " + CHOOSER + r"\(.*?\)\s*->\s*Label\s*\{(.*?)\n\}", text, re.S)
    if not m:
        raise refuse(f"could not find `{CHOOSER}` in {GENERATED}")
    arms = dict((int(a), b) for a, b in re.findall(r"if sec == (\d+) \{ out = (\w+) \}", m.group(1)))
    return arms.get(sec), arms


def cells_of(blob: bytes) -> list[int]:
    return [int.from_bytes(blob[i:i + 2], "big") for i in range(0, len(blob), 2)]


def find_run(mapcells: list[int], run: list, cols: int = PLANE_COLS, rows: int = PLANE_ROWS) -> list:
    """(row, col) starts where `run` matches with horizontal wrap; None entries are wildcards.

    Pure, so the classifier can be exercised without a ROM (tools/test_sec6_baseswap_witness.py).
    A scanline's consecutive 8-px dots are consecutive cells of one nametable row, so a match
    is a contiguous wrapped run — which is what makes 32 cells a fingerprint rather than a
    coincidence.
    """
    hits = []
    for r in range(rows):
        base = r * cols
        for c0 in range(cols):
            if all(want is None or mapcells[base + ((c0 + i) % cols)] == want
                   for i, want in enumerate(run)):
                hits.append((r, c0))
    return hits


def classify(run: list, map_a: list[int], map_t: list[int]) -> str:
    """'A' / 'T' / 'sparse' / 'ambiguous' — which nametable Plane A is reading, or nothing.

    `ambiguous` covers both "found in both maps" and "found in neither"; both mean the
    fingerprint cannot name a base, and the caller must report UNMEASURABLE rather than pick.
    """
    if sum(1 for v in run if v is not None) < MIN_RESOLVED:
        return "sparse"
    ha, ht = bool(find_run(map_a, run)), bool(find_run(map_t, run))
    if ha and not ht:
        return "A"
    if ht and not ha:
        return "T"
    return "ambiguous"


def contiguous(lines: list[int]) -> bool:
    return bool(lines) and lines == list(range(lines[0], lines[-1] + 1))


# ------------------------------------------------------------------------- bus helpers

def _hex(s) -> int:
    s = str(s)
    return int(s[2:] if s[:2].lower() == "0x" else (s[1:] if s[:1] == "$" else s), 16)


async def lookup(c: BusClient, name: str) -> int:
    try:
        r = await c.call("emulator/lookup_symbol", {"name": name})
    except Exception as e:
        raise refuse(f"symbol {name!r} does not resolve against the loaded listing: {e}")
    return _hex(r["addr"])


async def rd(c: BusClient, addr: int, length: int) -> int:
    return _hex((await c.call("emulator/read_memory", {"addr": hex(addr), "len": length}))["bytes"])


async def wr(c: BusClient, addr: int, value: int, width: int) -> None:
    await c.call("emulator/write_memory", {"addr": hex(addr), "value": value, "width": width})


async def read_space(c: BusClient, space: str, addr: int, n: int, chunk: int = 2048) -> bytes:
    out = b""
    while n > 0:
        k = min(chunk, n)
        r = await c.call("emulator/read", {"space": space, "addr": hex(addr), "len": k})
        out += bytes.fromhex(str(r["bytes"]).removeprefix("0x"))
        addr += k
        n -= k
    return out


async def sample_row(c: BusClient, y: int) -> list:
    """One 32-cell fingerprint of whatever Plane A is fetching, at the CURRENT stop."""
    out = []
    for i in range(DOTS):
        r = await c.call("emulator/pixel_attribution", {"x": 4 + 8 * i, "y": y})
        cell = r.get("cell")
        if r["winner"].get("layer") == "planeA" and cell:
            out.append(((1 if cell["priority"] else 0) << 15) | (cell["palette"] << 13) |
                       ((1 if cell["vflip"] else 0) << 12) | ((1 if cell["hflip"] else 0) << 11) |
                       cell["tile"])
        else:
            out.append(None)
    return out


async def frame_hashes(c: BusClient) -> list[str]:
    w, rows = await grab(c, 0, ACTIVE_H - 1)   # refuses on source != "raster"
    return [hashlib.md5(r).hexdigest()[:12] for r in rows]


async def assert_unmasked(c: BusClient) -> None:
    st = await c.call("emulator/get_layer_states", {})
    # Keyed to the LAYER names only: the reply carries transport/run-state fields beside them
    # (`running` was measured in it), and reading those as layers refuses a clean instrument.
    hidden = [k for k in ("planeA", "planeB", "window", "sprites") if st.get(k) is False]
    if not any(k in st for k in ("planeA", "planeB", "window", "sprites")):
        raise refuse(f"emulator/get_layer_states named no known layer (keys {sorted(st)}) — this "
                     f"instrument cannot confirm the capture is unmasked, and an unconfirmed "
                     f"unmasked read is exactly the state-render trap it exists to catch")
    if hidden:
        raise refuse(f"layers {hidden} are masked, and a MASKED scanline read is a post-hoc state "
                     f"render (oracle's framebuffer(): 'a masked read cannot use the latched "
                     f"frame') — blind to every mid-frame effect, which is the entire subject")


async def warp(c: BusClient, syms: dict, px: int, py: int) -> int:
    await wr(c, syms["Warp_Req_X"], px, 2)
    await wr(c, syms["Warp_Req_Y"], py, 2)
    await wr(c, syms["Warp_Req_Flag"], 1, 1)
    for i in range(1, 121):
        await c.call("emulator/run_frames", {"frames": 1})
        if await rd(c, syms["Warp_Req_Flag"], 1) == 0:
            bx, by = await rd(c, syms["Warp_Req_X"], 2), await rd(c, syms["Warp_Req_Y"], 2)
            if (bx, by) != (px, py):
                raise refuse(f"the engine CLAMPED the warp: asked ({px}, {py}), landed ({bx}, {by})")
            return i
    raise refuse("Warp_Req_Flag never cleared in 120 frames — the warp consumer did not run")


# ------------------------------------------------------------------------------- arms

class Shape:
    """One shape's run. `bound` = reach section 6 through the engine's own crossing."""

    def __init__(self, name, rom, lst, exp, geo, a, bound):
        self.name, self.rom, self.lst = name, rom, lst
        self.exp, self.geo, self.a, self.bound = exp, geo, a, bound
        self.out = {"shape": name, "rom": rom, "lst": lst, "bound": bound}
        self.fail: list[str] = []

    def check(self, ok: bool, what: str, detail: str) -> bool:
        print(f"    [{'OK  ' if ok else 'FAIL'}] {what}: {detail}")
        if not ok:
            self.fail.append(f"{self.name}/{what}: {detail}")
        return ok

    async def rebaseline(self, c, cp) -> int:
        """Restore, then RE-READ the frame index and prove the rewind landed on the checkpoint.

        THE REWIND HAZARD (oracle 91b21a8, 2026-09-03): the absolute frame index is not
        monotonic — `reset`, `restore` and a backwards `run_to` all move it backwards, and any
        logic gated on a strictly ADVANCING index silently does nothing instead of failing.
        That is the worst possible shape for a witness: "no change observed" and a real
        negative become indistinguishable.

        This instrument rewinds DELIBERATELY, once per arm, because a checkpoint is what makes
        the treated and removed frames comparable at all. So it does what `tools/reels_witness.py`
        does: it never carries a frame number across a rewind, it measures in `run_frames`
        DELTAS inside one uninterrupted window, and it re-baselines here — refusing if the
        restore did not put the machine back on the checkpoint's own frame, which is the one
        way a rewind could corrupt a sample without anything going red.
        """
        await c.call("emulator/restore", {"id": cp["id"]})
        f = int((await c.call("emulator/status", {}))["frame"])
        if f != cp["frame"]:
            raise refuse(f"restore of checkpoint {cp['id']} left the machine at frame {f}, not the "
                         f"checkpoint's own frame {cp['frame']} — every arm below would be sampling "
                         f"a different scene, and the differential would be measuring the rewind")
        return f

    async def install_arm(self, c, syms, cp, poke, frames):
        """restore -> re-baseline -> (poke Raster_Pending) -> run N -> (program, hashes, N).

        Returns the MEASURED frame advance, not the requested one: the caller asserts that
        every arm it intends to compare ended on the same absolute frame, which is what makes
        a per-line diff attributable to the program rather than to a scene that moved.
        """
        f0 = await self.rebaseline(c, cp)
        if poke is not None:
            await wr(c, syms["Raster_Pending"], poke, 4)
        await c.call("emulator/run_frames", {"frames": frames})
        f1 = int((await c.call("emulator/status", {}))["frame"])
        return await rd(c, syms["Raster_Program"], 4), await frame_hashes(c), f1 - f0

    async def run(self, sock, blob):
        a, exp, geo = self.a, self.exp, self.geo
        c = BusClient(socket_path=sock, client_id="sec6bs", client_name="sec6_baseswap_witness")
        await c.connect()
        st = await c.call("emulator/status", {})
        if st["romBytes"] != len(blob):
            raise refuse(f"server serves {st['romBytes']} bytes, {self.rom} is {len(blob)} — a "
                         f"different ROM (the stale-shim classic)")
        print(f"    server romPath={st['romPath']} romBytes={st['romBytes']} (matches disk)")

        names = ["Raster_Program", "Raster_Pending", "Raster_Program_None", DEMO_SYM,
                 DEMO_NEIGHBOUR, PRESET_SYM, exp["label"], "Parallax_Prev_Sec_X",
                 "Parallax_Prev_Sec_Y", "Camera_X", "Camera_Y"]
        if self.bound:
            names += ["Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag"]
        syms = {n: await lookup(c, n) for n in names}
        gen, demo, none = syms[exp["label"]], syms[DEMO_SYM], syms["Raster_Program_None"]
        self.out["symbols"] = {k: f"${v:06X}" for k, v in syms.items()}

        # ---- the demo's footprint in THIS shape -------------------------------------
        collapsed = demo == syms[DEMO_NEIGHBOUR]
        self.out["demo_zero_bytes"] = collapsed
        if self.name == "release":
            self.check(collapsed, "demo absent by construction",
                       f"{DEMO_SYM} ${demo:06X} == {DEMO_NEIGHBOUR} ${syms[DEMO_NEIGHBOUR]:06X} "
                       f"— the hand-written demo emits ZERO bytes here, so nothing measured "
                       f"below can be it")
        else:
            self.check(not collapsed, "demo present (so telling them apart is real work)",
                       f"{DEMO_SYM} ${demo:06X} != {exp['label']} ${gen:06X}")

        # ---- the release binding, read out of the shipped ROM ------------------------
        ep = await rd(c, syms[PRESET_SYM] + exp["ep_raster_off"], 4)
        self.out["preset_ep_raster"] = f"${ep:06X}"
        self.check(ep == gen, f"{PRESET_SYM}.ep_raster (offset ${exp['ep_raster_off']:02X})",
                   f"${ep:06X} == {exp['label']} ${gen:06X}" if ep == gen else
                   f"${ep:06X} is NOT {exp['label']} ${gen:06X} — section 6's preset record "
                   f"does not point at the generated program in this shape")

        await c.call("emulator/run_frames", {"frames": a.settle})

        if self.bound:
            col, row = SECTION % geo["grid_w"], SECTION // geo["grid_w"]
            px = col * geo["size"] + geo["size"] // 2
            py = row * geo["size"] + geo["size"] // 2 + a.warp_dy
            acked = await warp(c, syms, px, py)
            await c.call("emulator/run_frames", {"frames": a.post_warp})
            cam_x = (await rd(c, syms["Camera_X"], 4)) >> 16
            cam_y = (await rd(c, syms["Camera_Y"], 4)) >> 16
            cam_sec = ((cam_x + geo["screen_w"] // 2) >> geo["shift"],
                       (cam_y + geo["screen_h"] // 2) >> geo["shift"])
            prev = (await rd(c, syms["Parallax_Prev_Sec_X"], 1),
                    await rd(c, syms["Parallax_Prev_Sec_Y"], 1))
            self.out.update({"player": [px, py], "camera": [cam_x, cam_y],
                             "camera_section": list(cam_sec), "engine_prev_sec": list(prev),
                             "warp_ack_frames": acked})
            if cam_sec != (col, row) or prev != (col, row):
                raise refuse(f"section mismatch: asked ({col}, {row}), camera-centre {cam_sec}, "
                             f"engine Parallax_Prev_Sec {prev}")
            pend = await rd(c, syms["Raster_Pending"], 4)
            if pend != 0:
                raise refuse(f"Raster_Pending is still ${pend:08X} {a.post_warp} frames after the "
                             f"warp ack — VBlank never consumed the install")
            prog = await rd(c, syms["Raster_Program"], 4)
            self.out["raster_program_after_crossing"] = f"${prog:06X}"
            # ---- D1: THE DISCRIMINATOR -----------------------------------------------
            self.check(prog == gen, "the section's own crossing installed the GENERATED program",
                       f"Raster_Program=${prog:06X} == {exp['label']} ${gen:06X} "
                       f"(demo {DEMO_SYM} is ${demo:06X}, none is ${none:06X})"
                       if prog == gen else
                       f"Raster_Program=${prog:06X}, wanted {exp['label']} ${gen:06X} "
                       f"(it is {'THE DEMO' if prog == demo else 'not the demo either'})")
            if prog == demo:
                raise refuse(f"Raster_Program holds {DEMO_SYM} — the hand-written demo is "
                             f"installed and NOTHING below could distinguish it from the subject")
        else:
            print(f"    (unbound arm: the warp mailbox is DEBUG-only and absent from this "
                  f"listing, so section 6 cannot be reached here — the generated program is "
                  f"installed by poking Raster_Pending, and the BINDING is what "
                  f"{PRESET_SYM}.ep_raster above proves)")

        # ================= INSTRUMENT II — the picture differential ===================
        await assert_unmasked(c)
        r = await c.call("emulator/checkpoint", {})
        cp = {"id": r["id"], "frame": int(r["frame"])}
        n = a.frames
        p_t1, t1, a_t1 = await self.install_arm(c, syms, cp, gen, n)
        p_t2, t2, a_t2 = await self.install_arm(c, syms, cp, gen, n)
        p_c1, c1, a_c1 = await self.install_arm(c, syms, cp, none, n)
        p_c2, c2, a_c2 = await self.install_arm(c, syms, cp, none, n)
        p_n1, n1, a_n1 = ((await self.install_arm(c, syms, cp, None, n)) if self.bound
                          else (None, None, None))
        # The no-accumulation pair is a PAIR, at the longer frame count: diffing a 12-frame
        # treated frame against a 4-frame control would report every line as changed and read
        # as drift, which is what the first draft of this arm did.
        p_t3, t3, a_t3 = await self.install_arm(c, syms, cp, gen, n + a.persist)
        p_c3, c3, a_c3 = await self.install_arm(c, syms, cp, none, n + a.persist)

        # ---- P0: the rewind is accounted for, not assumed away ------------------------
        short = [x for x in (a_t1, a_t2, a_c1, a_c2, a_n1) if x is not None]
        adv = {"checkpoint_frame": cp["frame"], "short_arms": short, "long_arms": [a_t3, a_c3],
               "requested": [n, n + a.persist]}
        self.out["frame_advance"] = adv
        self.check(set(short) == {n} and set([a_t3, a_c3]) == {n + a.persist},
                   "every compared arm advanced the SAME number of frames from the checkpoint",
                   f"restores all re-baselined on frame {cp['frame']}; short arms advanced "
                   f"{short} (want all {n}), long arms {[a_t3, a_c3]} (want both {n + a.persist}) "
                   f"— the absolute frame index REWINDS at every restore, so this is measured "
                   f"as a delta inside each window and never carried across one")

        def diff(x, y):
            return [i for i in range(ACTIVE_H) if x[i] != y[i]]

        self.out["programs"] = {"treat": f"${p_t1:06X}", "treat2": f"${p_t2:06X}",
                                "control": f"${p_c1:06X}", "control2": f"${p_c2:06X}",
                                "nopoke": (f"${p_n1:06X}" if p_n1 is not None else None)}
        # ---- P1: CONTROL vs CONTROL, run BEFORE control-vs-treatment is read ---------
        # Both pairs, because a differential is attributable only once the instrument has
        # been shown to reproduce itself. Ordered first deliberately.
        cc_t, cc_c = diff(t1, t2), diff(c1, c2)
        ok1 = self.check(not cc_t and not cc_c, "control-vs-control (both pairs)",
                         f"treated pair {len(cc_t)} differing lines, removed pair {len(cc_c)} "
                         f"— both must be 0 for anything below to be attributable")
        if not ok1:
            raise refuse("the two instances of an arm do not reproduce each other; a "
                         "control/treatment difference cannot be attributed to anything")
        # ---- P2: the poke is a NO-OP against what the section already installed ------
        if self.bound:
            d_np = diff(t1, n1)
            self.check(not d_np and p_n1 == gen, "the treated arm's poke changes nothing",
                       f"treated-with-poke vs treated-with-NO-poke: {len(d_np)} differing lines, "
                       f"Raster_Program=${p_n1:06X} — so the frame measured is the one the "
                       f"SECTION BINDING installed, not one this instrument installed")
        # ---- P3: the footprint --------------------------------------------------------
        self.check(p_t1 == gen and p_c1 == 0,
                   "the two arms hold what they should",
                   f"treated Raster_Program=${p_t1:06X} (generated ${gen:06X}), removed "
                   f"${p_c1:06X} (an empty program uninstalls to 0)")
        d = diff(t1, c1)
        self.out["picture_diff"] = {"count": len(d), "first": d[0] if d else None,
                                    "last": d[-1] if d else None, "contiguous": contiguous(d)}
        if not d:
            self.check(False, "the program changes the picture at all",
                       "ZERO lines differ between program-installed and program-removed — the "
                       "op did not execute, or it re-points Plane A at the base it already has")
            first = None
        else:
            first = d[0]
            lo, hi = exp["first_window"]
            self.check(lo <= first <= hi, "the first affected line is the authored one",
                       f"first differing line {first}, authored line {exp['line']} — the derived "
                       f"window is [{lo}, {hi}] (item 11a's own note: the boundary may land on "
                       f"{lo} or {hi}, because the blanking spin guards the CRAM paths only)")
            self.check(contiguous(d) and d[-1] == ACTIVE_H - 1,
                       "the change runs unbroken to the bottom of the display",
                       f"lines {first}..{d[-1]}, {len(d)} of them, contiguous={contiguous(d)} "
                       f"— the swap is restored by the VBlank shadow flush, not mid-screen")
            self.check(all(t1[i] == c1[i] for i in range(first)),
                       "nothing above the boundary moves",
                       f"lines 0..{first - 1} are byte-identical between the two arms")
            # ---- P4: no accumulation across frames (item 11a's failure mode 3) --------
            d3 = diff(t3, c3)
            same_span = bool(d3) and d3[0] == first and d3[-1] == ACTIVE_H - 1 and contiguous(d3)
            self.out["picture_diff_long"] = {"count": len(d3), "first": d3[0] if d3 else None,
                                             "last": d3[-1] if d3 else None}
            self.check(same_span, "no accumulation or drift over more frames",
                       f"after {n + a.persist} frames instead of {n} the footprint is still "
                       f"{d3[0] if d3 else None}..{d3[-1] if d3 else None} ({len(d3)} lines) — the "
                       f"shadow flush restores reg $02 at every frame top, so the swap neither "
                       f"creeps up the screen nor survives into the next frame")

        # ================= INSTRUMENT I — the plane-base readback =====================
        # Masks LAST: every capture above is taken unmasked, because a masked scanline read
        # is a state render. pixel_attribution is a live-state query and is unaffected.
        await self.rebaseline(c, cp)
        await wr(c, syms["Raster_Pending"], gen, 4)
        await c.call("emulator/run_frames", {"frames": n})
        for lay in ("planeB", "sprites", "window"):
            await c.call("emulator/set_layer_enabled", {"layer": lay, "enabled": False})
        map_a = cells_of(await read_space(c, "vram", geo["plane_a"], NAMETABLE_BYTES))
        map_t = cells_of(await read_space(c, "vram", exp["target"], NAMETABLE_BYTES))
        if map_a == map_t:
            raise refuse(f"the nametables at ${geo['plane_a']:04X} and ${exp['target']:04X} hold "
                         f"IDENTICAL bytes right now, so no fingerprint can tell them apart — "
                         f"UNMEASURABLE, not a pass")
        self.out["maps"] = {"a_distinct": len(set(map_a)), "t_distinct": len(set(map_t))}

        async def at(y):
            # Re-baselined, never carried: run_to_scanline can land in a LATER frame than the
            # one this arm ran to, and the next probe's restore rewinds the index under it.
            await self.rebaseline(c, cp)
            await wr(c, syms["Raster_Pending"], gen, 4)
            await c.call("emulator/run_frames", {"frames": n})
            r = await c.call("emulator/run_to_scanline", {"line": y})
            if not r.get("reached"):
                raise refuse(f"run_to_scanline({y}) reported reached=false: {r.get('caveat', r)}")
            return classify(await sample_row(c, y), map_a, map_t)

        probes, above_line = {}, None
        if first is not None:
            # ABOVE the boundary: the line immediately above it if the foreground resolves
            # there, else the nearest one that does. A screen row where Plane A is transparent
            # cannot fingerprint a nametable at all, and walking up to a row that can is not a
            # weaker claim — every line walked is still above the boundary. The line actually
            # used is reported, and running out of them is a FAILURE, never a skip.
            for y in range(first - 1, max(-1, first - 1 - MAX_WALK_UP), -1):
                probes[y] = await at(y)
                if probes[y] in ("A", "T"):
                    above_line = y
                    break
            for y in (first, min(ACTIVE_H - 1, first + a.deep)):
                probes[y] = await at(y)
        self.out["base_probes"] = probes
        self.out["base_probe_above_line"] = above_line
        print(f"    plane-base readback (A = ${geo['plane_a']:04X} Plane A's own, "
              f"T = ${exp['target']:04X} the authored target):")
        for y, v in sorted(probes.items()):
            print(f"      stop line {y:3d} -> {v}")
        if first is not None:
            deep_line = min(ACTIVE_H - 1, first + a.deep)
            above = probes.get(above_line) if above_line is not None else None
            below, deep = probes.get(first), probes.get(deep_line)
            if above_line is None or below in ("sparse", "ambiguous") or deep in ("sparse", "ambiguous"):
                self.check(False, "the base readback is measurable at the boundary",
                           f"above-the-boundary probes {[(y, probes[y]) for y in sorted(probes) if y < first]} "
                           f"and line {first} reads {below!r}, line {deep_line} reads {deep!r} — the "
                           f"foreground does not resolve enough cells to fingerprint a nametable. "
                           f"UNMEASURABLE at this point in the level, not a pass; move --warp-dy to a "
                           f"screen where Plane A is opaque on both sides of the boundary")
            else:
                ok = above == "A" and below == "T" and deep == "T"
                self.check(ok, "the VDP's Plane A base actually moves at the boundary",
                           f"stop {above_line} reads Plane A's own nametable (${geo['plane_a']:04X}), "
                           f"stop {first} and stop {deep_line} read the authored target "
                           f"(${exp['target']:04X}) — the register readback and the picture "
                           f"differential name the SAME boundary line" if ok else
                           f"above={above} at {above_line}, below={below} at {first}, "
                           f"deep={deep} at {deep_line} — wanted A then T then T")
        await c.close()
        return EXIT_MISMATCH if self.fail else EXIT_OK


# -------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--lst", default=None, help="listing; default = ROM path with .lst")
    ap.add_argument("--release-rom", default=os.path.join(REPO, "s4.bin"))
    ap.add_argument("--release-lst", default=None)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--shapes", default="both", choices=("debug", "release", "both"))
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--post-warp", type=int, default=8)
    ap.add_argument("--frames", type=int, default=4, help="frames run from the checkpoint in each arm")
    ap.add_argument("--persist", type=int, default=8, help="extra frames for the no-accumulation arm")
    ap.add_argument("--deep", type=int, default=40, help="how far below the boundary the third probe sits")
    ap.add_argument("--warp-dy", type=int, default=-700,
                    help="offset from the section centre. The DEFAULT IS NOT COSMETIC: at the "
                         "bare centre of section 6 the foreground is empty sky above the swap "
                         "line, every dot resolves to the backdrop, and the base readback is "
                         "UNMEASURABLE above the boundary (measured). -700 puts opaque "
                         "foreground on both sides of it.")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    repo = a.repo
    geo = geometry(repo)
    ref, sidecar = sidecar_ref(repo, SECTION)
    label, arms = chooser_binding(repo, SECTION)
    if ref is None or label is None:
        raise refuse(f"section {SECTION} is not bound: sidecar {RASTER_REF_KEY}={ref!r}, chooser "
                     f"arm={label!r} (arms {arms}). There is no generated program to witness")
    preset, ppath = load_preset(repo, ref)
    exp = base_swap_expectation(preset, os.path.relpath(ppath, repo), geo["plane_a"])
    if label != f"EditorRaster_OJZ_Act1_{exp['preset_id']}":
        raise refuse(f"the chooser binds {label}, not the label effects_gen emits for preset "
                     f"{exp['preset_id']!r}")
    exp["label"] = label
    exp["ep_raster_off"] = struct_field_offset(
        open(os.path.join(repo, PRESET_STRUCT), encoding="utf-8").read(),
        "EffectsPreset", "ep_raster", PRESET_STRUCT)

    print(f"DERIVED (nothing below is typed)")
    print(f"  {os.path.relpath(sidecar, repo)} {RASTER_REF_KEY}={ref!r}; chooser arms {arms}")
    print(f"  {os.path.relpath(ppath, repo)}: base_swap line {exp['line']}, target "
          f"${exp['target']:04X}; VRAM_PLANE_A ${geo['plane_a']:04X}")
    print(f"  first-affected-line window {exp['first_window']}; {label}; "
          f"EffectsPreset.ep_raster @ ${exp['ep_raster_off']:02X}")
    print(f"  act grid {geo['grid_w']}x{geo['grid_h']}, section {geo['size']} px, "
          f"section {SECTION} = col {SECTION % geo['grid_w']} row {SECTION // geo['grid_w']}")

    shapes = []
    if a.shapes in ("debug", "both"):
        rom = os.path.abspath(a.rom)
        shapes.append(("debug", rom, os.path.abspath(a.lst) if a.lst else rom[:-4] + ".lst", True))
    if a.shapes in ("release", "both"):
        rom = os.path.abspath(a.release_rom)
        shapes.append(("release", rom,
                       os.path.abspath(a.release_lst) if a.release_lst else rom[:-4] + ".lst", False))

    report, rc = [], EXIT_OK
    for name, rom, lst, bound in shapes:
        for p in (rom, lst):
            if not os.path.isfile(p):
                raise refuse(f"{p} does not exist")
        blob = open(rom, "rb").read()
        print(f"\n=== {name.upper()} SHAPE — {rom}\n    {len(blob)} bytes, crc32 "
              f"{zlib.crc32(blob) & 0xFFFFFFFF:08x}, lst {lst}")
        sh = Shape(name, rom, lst, exp, geo, a, bound)
        inst = AetherInstance(rom, symbols=lst)
        sock = inst.start()
        try:
            r = asyncio.run(sh.run(sock, blob))
        except Refused as e:
            sh.out["refused"] = e.why
            report.append(sh.out)
            if a.json:
                with open(a.json, "w", encoding="utf-8") as fh:
                    json.dump(report, fh, indent=1, sort_keys=True)
            return EXIT_REFUSED
        finally:
            inst.reap()
        sh.out["failures"] = sh.fail
        report.append(sh.out)
        rc = max(rc, r)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
        print(f"\nwrote {a.json}")
    fails = [f for s in report for f in s.get("failures", [])]
    print(f"\nsec6_baseswap_witness: {len(shapes)} shape(s), {len(fails)} failed check(s)")
    for f in fails:
        print(f"  FAIL {f}")
    print("RESULT: " + ("MEASURED — a running machine obeys the GENERATED base-swap program"
                        if rc == EXIT_OK else "MEASURED — at least one derived expectation was not met"))
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refused as e:
        sys.exit(EXIT_REFUSED)
