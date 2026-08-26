#!/usr/bin/env python3
"""parallax_crossing_gate — does a WALKED section crossing install the parallax config
`Effects_ResolveParallax` names for the section actually entered?

WHY THIS IS A SEPARATE GATE FROM `boot_override_gate`, AND NOT A BLOCK INSIDE IT.

`boot_override_gate` witnesses the OTHER caller of the same resolver: the level init's
boot select. It samples `Parallax_Current_Config` at the init's exit and its own docstring
makes that timing load-bearing — the sample is taken deliberately BEFORE the first
`Parallax_CheckBoundary`, because the update loop's first crossing re-selects from the
camera and would launder a wrong boot choice into a right one. That timing rule and this
gate's are exact opposites: here the crossing IS the subject, so every sample must be taken
AFTER one. Two mutually contradictory sampling rules in one file would make a red ambiguous
about which mechanism broke, and the runner already gives every emulator-backed gate its own
segment with its own wedge budget — the unit of isolation is one subject per segment. So:
sibling, not extension. (The two gates are still each other's other half; a change to
`Effects_ResolveParallax` should turn BOTH red, and that is the design, not a duplication.)

THE SUBJECT, spelled as the source reads today (2026-08-26):

  `Parallax_CheckBoundary` (engine/level/parallax.emp) watches the section under the camera
  CENTRE (camX + SCREEN_WIDTH/2, camY + SCREEN_HEIGHT/2, each >> SECTION_SIZE_SHIFT). On a
  change it commits the new coords to `Parallax_Prev_Sec_X/Y`, calls `Effects_InstallPreset`,
  whose tail is `Effects_ResolveParallax`, and tail-jumps into `Parallax_StartTransition`
  with the resolved pointer in a0. It is the ONLY caller of `Parallax_StartTransition`.

  `Effects_ResolveParallax` (engine/effects/preset.emp) — THE three-way resolution, and the
  whole of what this gate asserts, restated here rung for rung:

      1. Sec.sec_parallax_config      non-zero wins outright
      2. EffectsPreset.ep_parallax    read through Sec.sec_effects, if a preset is bound
      3. Act.act_parallax_config      the act default

  A 0 at rung 1 or 2 means DEFER, never "keep": nothing a previous section chose survives
  into a section that did not bind it.

  `Parallax_StartTransition` then either SNAPS (`pcfg_transition != 0`: Current_Config = a0,
  Target = 0, Transition_Frames = 0) or STAGES (`pcfg_transition == 0`: Target = a0,
  Transition_Frames = PARALLAX_TRANS_DEFAULT, Current_Config left alone until the counter
  reaches 0). That fork is why "read Parallax_Current_Config right after the crossing" is
  not by itself a correct test — for a smooth config it is still the OUTGOING pointer, and a
  gate that asserted equality there would be red on correct code. Both shapes are checked
  here, each against the entered config's own `pcfg_transition` byte read out of the ROM.

WHAT THE BOOKING ASKED FOR. docs/DEFERRED_WORK.md, "PARALLAX CONFIG PRECEDENCE" left open
item (a): "runtime confirmation that Parallax_Current_Config equals the editor record after
a crossing once the aurora binding lands". That binding has landed — OJZ act 1 section (0,0)
carries `sec_parallax_config = EditorSceneBinding_OJZ_Act1_Sec0` — and it is what makes this
measurable at all, because section (0,0) is the ONE section in the act where all three rungs
hold different pointers:

      rung 1  Sec.sec_parallax_config   EditorSceneBinding_OJZ_Act1_Sec0   <- must win
      rung 2  ep_parallax of OJZ_Preset_Sec0   ParallaxConfig_OJZ_Underwater
      rung 3  Act.act_parallax_config   ParallaxConfig_OJZ_Default

The defect the precedence closure fixed was precisely rung 2 beating rung 1 at the crossing
(the boot select got rung 1 right and the crossing took it back on the first boundary), so a
crossing INTO (0,0) is the exact experiment the booking names. The gate refuses to run — as a
setup error, never a pass — if content ever makes those three coincide, because then a
resolver with the old precedence would be indistinguishable from the correct one.

THE ROUTE, and why it is a walk and not a warp. `Debug_Warp_Consume` reaches the crossing by
forcing `Parallax_Prev_Sec_X/Y` to the $FF sentinel and calling `Parallax_CheckBoundary`
itself — the same code, but with `Parallax_Snap_Pending` set and the camera teleported, so a
gate built on it would be measuring the warp's staging as much as the crossing's. This gate
instead uses the DEBUG boot-position mailbox to START an eighth of a section short of the
(0,0)|(1,0) boundary and then WALKS the pad across it and back. The boot override is used only
to shorten the walk (it is `boot_override_gate`'s subject, proven there); every crossing here
is edge-triggered by `Camera_Update` moving the camera, which is the shipped mechanism.

  crossing A   (0,0) -> (1,0)   expect Act.act_parallax_config      [rung 3, SMOOTH: staged]
  crossing B   (1,0) -> (0,0)   expect Sec.sec_parallax_config      [rung 1, INSTANT: snapped]

B is the one that carries the booking. A exists because a gate that only ever entered the
authored section could be satisfied by a resolver that returned that one pointer always.

OBSERVABLES, all three DERIVED from the ROM's own section grid and struct declarations:

  * `Parallax_Current_Config` / `Parallax_Target_Config` / `Parallax_Transition_Frames` —
    the pointer, read both at the crossing and after the transition window has closed.
  * the VDP reg $0B (Mode Set 3) shadow, re-derived from the entered config's own deform
    table fields exactly as `Parallax_StartTransition` derives it. A crossing that stored the
    right pointer where nothing read it passes the first check and fails this one. It
    discriminates here: the editor record attaches no deform table (%10) and both other
    candidates attach a BG one (%11).
  * the band-scroll tail — at least one live entry non-zero, i.e. the band pipeline ran
    against the selected config. NOT the "entries above the count are zero" form
    `boot_override_gate` uses: that one is only sound straight out of `Parallax_Init`, which
    zeroes the whole span. Across a crossing from a 5-band config to a 4-band one, entry [4]
    legitimately holds the previous config's value and nothing re-zeroes it.

STRUCT OFFSETS ARE PARSED, NOT TYPED. `struct_offsets()` accumulates field sizes out of the
`.emp` declaration AND cross-checks every `// $HH` offset comment on the way, so a field
inserted into `Sec` or `Act` fails this gate at setup rather than silently sliding every read
by four bytes. `EffectsPreset`'s explicit `@ $XX` displacements are read the same way.

Exit 0 pass · 1 fail · 2 setup error (the measurement could not be made).
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, str(AEON / "tools"))

from aether import BusClient            # noqa: E402
from aether_instance import (            # noqa: E402
    AetherInstance, SpawnError, WrongServerError, read_bytes)
from raster_cost_probe import parse_lst  # noqa: E402

BOOT_MAX_FRAMES = 600     # ceiling for run_to(Init)/run_to(Update); the DEBUG shape boots
                          # straight into the OJZ scroll test with no buttons pressed
WALK_MAX_FRAMES = 400     # per crossing. A ceiling, not an expectation: the walk polls for
                          # the crossing every frame and this only bounds a walk that never
                          # arrives, which is a FAILURE (see `walk_to_section`), never a skip.
ALIGN_MAX_FRAMES = 8      # run_to(Update) after a walk, to sample at a fixed point in the
                          # game loop. `play_input` stops wherever the frame ended, which can
                          # be between Camera_Update and Parallax_CheckBoundary — so a sample
                          # taken there can show a camera whose crossing has not run yet.
                          # At the TOP of Update both have run for the same camera. MEASURED:
                          # a camera-derived section disagreed with Parallax_Prev_Sec by one
                          # section at an unaligned sample, which is what this exists for.


class SetupError(Exception):
    """Something made the measurement impossible. Not a verdict — exit 2, never exit 1."""


# ---- source-derived constants and struct layouts -----------------------------

def emp_const(rel: str, name: str) -> int:
    """A `const NAME = $HEX` / `= 123` out of an .emp source, so the gate cannot drift."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        raise SetupError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


_SCALAR = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}


def emp_const_anywhere(name: str) -> int:
    """A `const NAME = <int>` from wherever in `engine/` it is declared.

    Array fields are spelt with named lengths (`[u16; RASTER_MAX_PATCH]`), so the layout
    parser needs the constant, and the constant's OWNING module is not something this gate
    should hard-code — it would be one more copied fact. A name declared twice with different
    values is a setup error rather than a silent first-match.
    """
    found: dict[int, list[str]] = {}
    for p in sorted((AEON / "engine").rglob("*.emp")):
        m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                      p.read_text(), re.M)
        if m:
            v = m.group(1)
            found.setdefault(int(v[1:], 16) if v.startswith("$") else int(v), []).append(
                str(p.relative_to(AEON)))
    if not found:
        raise SetupError(f"cannot find `const {name}` anywhere under engine/ — a struct "
                         "field's array length is unresolvable, so no offset below is safe")
    if len(found) > 1:
        raise SetupError(f"`const {name}` is declared with {len(found)} different values "
                         f"under engine/: {found} — the layout parser cannot choose")
    return next(iter(found))


def _field_size(ty: str) -> int:
    ty = ty.strip()
    if ty.startswith("*"):
        return 4
    m = re.fullmatch(r"\[\s*([^;\]]+)\s*;\s*([\w]+)\s*\]", ty)
    if m:
        n = m.group(2)
        count = int(n) if n.isdigit() else emp_const_anywhere(n)
        return _field_size(m.group(1)) * count
    if ty in _SCALAR:
        return _SCALAR[ty]
    raise SetupError(f"unknown field type `{ty}` — teach struct_offsets() about it rather "
                     "than guessing an offset")


def struct_offsets(rel: str, name: str) -> tuple[dict[str, int], int]:
    """Field name -> byte offset, and the struct's total size, out of the `.emp` declaration.

    TWO INDEPENDENT STATEMENTS, CHECKED AGAINST EACH OTHER. The offset is accumulated from
    the field TYPES; where a field also carries an explicit `@ $HH` displacement or a
    trailing `// $HH` offset comment, that is compared against the accumulation and a
    disagreement is a setup error. A struct whose comments have gone stale, or a field
    inserted without renumbering, stops this gate instead of sliding every read.
    """
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?struct\s+{re.escape(name)}\b[^{{]*\{{(.*?)^\}}",
                  txt, re.M | re.S)
    if not m:
        raise SetupError(f"cannot find `struct {name}` in {rel}")
    off, out = 0, {}
    for raw in m.group(1).splitlines():
        line = raw.split("//")[0]
        fm = re.match(r"\s*(\w+)\s*:\s*([^=@,]+?)\s*(?:@\s*\$([0-9A-Fa-f]+))?\s*(?:=\s*[^,]+)?,",
                      line)
        if not fm:
            continue
        fname, ty, at = fm.group(1), fm.group(2), fm.group(3)
        declared = int(at, 16) if at else None
        cm = re.search(r"//.*?\$([0-9A-Fa-f]+)", raw)
        if declared is None and cm:
            declared = int(cm.group(1), 16)
        if declared is not None and declared != off:
            raise SetupError(f"{rel} `struct {name}`: field `{fname}` is declared/commented "
                             f"at ${declared:02X} but the fields before it total ${off:02X} "
                             "— the declaration and its offsets disagree")
        out[fname] = off
        off += _field_size(ty)
    if not out:
        raise SetupError(f"parsed no fields out of `struct {name}` in {rel}")
    return out, off


# ---- the emulator ------------------------------------------------------------

class Server:
    """One oracle-aether process, spawned through `tools/aether_instance` — the ONE spawn
    seam (private mkdtemp socket, readiness by socket ACCEPT, PR_SET_PDEATHSIG, the identity
    assertion that refuses the legacy C++ server, and a reap in a finally).

    `AetherInstance.start()` runs its own `asyncio.run` for the handshake, so it cannot be
    called from inside a running loop — hence `asyncio.to_thread`.
    """

    def __init__(self, rom: str):
        self.rom, self.inst, self.client = rom, None, None

    async def __aenter__(self) -> "Server":
        self.inst = AetherInstance(self.rom)
        try:
            sock = await asyncio.to_thread(self.inst.start)
        except (SpawnError, WrongServerError) as e:
            raise SetupError(str(e)) from e
        self.client = BusClient(sock, client_id="parxing",
                                client_name="parallax_crossing_gate")
        await self.client.connect()
        for m in ("emulator/run_to", "emulator/play_input", "emulator/run_frames",
                  "emulator/read_memory", "emulator/write_memory"):
            if not self.client.supports(m):
                raise SetupError(f"the server does not advertise `{m}`")
        return self

    async def __aexit__(self, *exc) -> None:
        try:
            if self.client:
                await self.client.close()
        finally:
            self.inst.reap()


async def _c(b, method, params=None, timeout=180.0):
    """Every RPC gets a deadline — a run that never returns otherwise blocks the next call,
    which has no timeout of its own."""
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def rd(b, addr: int, n: int) -> int:
    """`read_memory` through `aether_instance.read_bytes`, which strips the Rust core's `0x`.

    The prefix is the quiet trap of the aether cutover: the legacy server answered bare hex,
    this one prefixes, and anything that slices positionally reads two characters off and
    returns a plausible wrong answer with nothing raised.
    """
    return int(await read_bytes(b, addr, n), 16)


async def run_to_sym(b, sym, name: str, max_frames: int) -> None:
    """`run_to` and INSIST it fired. `reached: false` is a failure of the measurement, never
    a skip — a caller that ignored it would read state from wherever the machine happened to
    stop and report it as the subject's."""
    r = await _c(b, "emulator/run_to", {"addr": hex(sym[name]), "maxFrames": max_frames})
    if not r.get("reached"):
        raise SetupError(f"run_to {name} (${sym[name]:06X}) never reached it within "
                         f"{max_frames} frames; stopped at pc={r.get('pc')} "
                         f"(caveat {r.get('caveat')!r}) — nothing about the machine's state "
                         "follows from where it stopped, so no verdict is available")


# ---- the ROM's own section grid ---------------------------------------------

class RomAct:
    """The act's section grid read out of the ROM image, and `Effects_ResolveParallax`
    restated against it. One object so every ROM walk here shares a base."""

    def __init__(self, rom_img: bytes, act_base: int, off: dict):
        self.rom, self.act_base, self.o = rom_img, act_base, off
        self.grid_w = self.u16(act_base + off["act"]["grid_w"])
        self.grid_h = self.u16(act_base + off["act"]["grid_h"])
        self.grid = self.u32(act_base + off["act"]["sec_grid_ptr"])
        self.act_default = self.u32(act_base + off["act"]["act_parallax_config"])

    def _at(self, o: int, n: int) -> bytes:
        if o + n > len(self.rom) or o < 0:
            raise SetupError(f"ROM read at {o:#x} is outside the image")
        return self.rom[o:o + n]

    def u32(self, o: int) -> int:
        return int.from_bytes(self._at(o, 4), "big")

    def u16(self, o: int) -> int:
        return int.from_bytes(self._at(o, 2), "big")

    def u8(self, o: int) -> int:
        return self._at(o, 1)[0]

    def sec_ptr(self, gx: int, gy: int) -> int | None:
        """`Section_GetSecPtrXY`: flat = sec_y * grid_w + sec_x, stride sizeof(Sec). None is
        that routine's "Z set = no such section", which every caller answers with the act
        default."""
        if not (0 <= gx < self.grid_w and 0 <= gy < self.grid_h):
            return None
        return self.grid + (gy * self.grid_w + gx) * self.o["sec_size"]

    def rungs(self, gx: int, gy: int) -> dict:
        """All three rungs' values for a section, whether or not they win. The gate needs the
        losers by name: a failure message that says only "wanted X, got Y" leaves the reader
        to work out that Y is the rung that used to win."""
        sec = self.sec_ptr(gx, gy)
        if sec is None:
            return {"sec": 0, "preset": 0, "act": self.act_default, "sec_ptr": None}
        preset = self.u32(sec + self.o["sec"]["sec_effects"])
        return {
            "sec": self.u32(sec + self.o["sec"]["sec_parallax_config"]),
            "preset": self.u32(preset + self.o["ep"]["ep_parallax"]) if preset else 0,
            "act": self.act_default,
            "sec_ptr": sec,
        }

    def resolve_parallax(self, gx: int, gy: int) -> tuple[int, str]:
        """`Effects_ResolveParallax` (engine/effects/preset.emp) restated: rung 1
        Sec.sec_parallax_config, rung 2 EffectsPreset.ep_parallax through Sec.sec_effects,
        rung 3 Act.act_parallax_config; a 0 at rung 1 or 2 defers, never keeps."""
        r = self.rungs(gx, gy)
        if r["sec_ptr"] is None:
            return r["act"], "act default (no section at that grid coord)"
        if r["sec"]:
            return r["sec"], "Sec.sec_parallax_config"
        if r["preset"]:
            return r["preset"], "EffectsPreset.ep_parallax"
        return r["act"], "Act.act_parallax_config"

    def cfg(self, base: int, field: str) -> int:
        o = self.o["pcfg"][field]
        n = 4 if field.endswith("_table_fg") or field.endswith("_table_bg") else 1
        return self.u32(base + o) if n == 4 else self.u8(base + o)

    def band_count(self, c: int) -> int:
        return self.u8(c + self.o["pcfg"]["pcfg_band_count"])

    def transition(self, c: int) -> int:
        return self.u8(c + self.o["pcfg"]["pcfg_transition"])

    def mode3(self, c: int) -> int:
        """`Parallax_StartTransition`'s own reg $0B (Mode Set 3) derivation from the config
        it installs: bits 1:0 = %11 if either H-deform table is attached else %10, bit 2 set
        if a V-column table is attached. (That last arm sits behind the CAP_PER_COL_VSRAM
        span and no shipped config attaches a column table, so it is inert either way —
        restated rather than dropped so the derivation stays the source's.)"""
        m = 0b11 if (self.u32(c + self.o["pcfg"]["pcfg_deform_table_fg"])
                     or self.u32(c + self.o["pcfg"]["pcfg_deform_table_bg"])) else 0b10
        if self.u32(c + self.o["pcfg"]["pcfg_v_deform_table_bg"]):
            m |= 0b100
        return m


def sym_name(addr: int, inv: dict) -> str:
    """`0x12c38 (ParallaxConfig_OJZ_Default)` — a red gate someone can act on names both
    pointers, not just the one that was wrong."""
    if addr == 0:
        return "NULL"
    names = inv.get(addr)
    return f"{addr:#x} ({'/'.join(sorted(names))})" if names else f"{addr:#x} (unnamed)"


# ---- sampling ----------------------------------------------------------------

async def sample(b, sym, k) -> dict:
    """Everything the verdict reads, from one stop point."""
    cam_x = (await rd(b, sym["Camera_X"], 4)) >> 16
    cam_y = (await rd(b, sym["Camera_Y"], 4)) >> 16
    return {
        "cam": (cam_x, cam_y),
        # Parallax_CheckBoundary's own rule: the section under the camera CENTRE.
        "cam_sec": ((cam_x + k["SCREEN_W"] // 2) >> k["SHIFT"],
                    (cam_y + k["SCREEN_H"] // 2) >> k["SHIFT"]),
        "prev_sec": (await rd(b, sym["Parallax_Prev_Sec_X"], 1),
                     await rd(b, sym["Parallax_Prev_Sec_Y"], 1)),
        "current": await rd(b, sym["Parallax_Current_Config"], 4),
        "target": await rd(b, sym["Parallax_Target_Config"], 4),
        "frames": await rd(b, sym["Parallax_Transition_Frames"], 1),
        "mode3": await rd(b, sym["VDP_Shadow_Table"] + k["MODE3_OFF"], 1),
        "scroll_a": await read_words(b, sym["Parallax_Current_Scroll_A"], k["BANDS"]),
        "scroll_b": await read_words(b, sym["Parallax_Current_Scroll_B"], k["BANDS"]),
        "tick": await rd(b, sym["Logic_Tick"], 4),
    }


async def read_words(b, addr: int, n: int) -> list[int]:
    raw = await read_bytes(b, addr, n * 2)
    if len(raw) != n * 4:
        raise SetupError(f"read_memory returned {len(raw) // 2} bytes, wanted {n * 2}")
    return [int(raw[i:i + 4], 16) for i in range(0, len(raw), 4)]


def installed(s: dict) -> tuple[int, str]:
    """WHAT THE CROSSING INSTALLED, given `Parallax_StartTransition`'s two shapes.

    An instant config (`pcfg_transition != 0`) lands in Current_Config with Target cleared;
    a smooth one is STAGED in Target_Config with Current_Config left holding the OUTGOING
    pointer until the counter reaches 0. Reading Current_Config alone at the crossing would
    therefore be red on correct code for every smooth config, which is why this fork exists
    rather than a single read.
    """
    return (s["target"], "staged (Parallax_Target_Config)") if s["frames"] else \
           (s["current"], "snapped (Parallax_Current_Config)")


# ---- the run -----------------------------------------------------------------

async def boot_at(b, sym, lst: str, x: int, y: int) -> None:
    """Boot with the DEBUG boot-position mailbox aimed at (x, y).

    The write window is fixed by boot's own 64 KB Work-RAM clear: a pre-resume poke is zeroed
    before the init can see it (proven by `boot_override_gate`'s `pre` run), so the mailbox is
    written at the init's first instruction and consumed by the init below it. X, then Y, then
    the FLAG last — the write order is the protocol.
    """
    await _c(b, "emulator/load_symbols", {"path": lst})
    await _c(b, "emulator/reset", {})
    await run_to_sym(b, sym, "GameState_OJZScroll_Init", BOOT_MAX_FRAMES)
    for nm, v, w in (("Boot_At_X", x, 2), ("Boot_At_Y", y, 2), ("Boot_At_Flag", 1, 1)):
        await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
    await run_to_sym(b, sym, "GameState_OJZScroll_Update", BOOT_MAX_FRAMES)


async def walk_to_section(b, sym, k, button: str, want: tuple[int, int]) -> tuple[dict, int]:
    """Hold `button` a frame at a time until `Parallax_Prev_Sec_X/Y` reads `want`.

    ONE FRAME PER CALL is deliberate. `play_input` REPLACES the pad for the frames it covers
    and releases it afterwards, so consecutive single-frame calls are a continuous hold; and
    polling every frame means the crossing is caught in the frame it happens rather than
    somewhere inside a block of held input, which is what makes the "at the crossing" sample
    meaningful.

    Returns the sample taken in the crossing frame, and how many frames the walk took.
    A walk that never arrives raises — an unreachable crossing is an unmeasurable gate, and
    the one thing it must never render as is a pass.
    """
    for i in range(1, WALK_MAX_FRAMES + 1):
        r = await _c(b, "emulator/play_input",
                     {"rows": [{"start": 0, "end": 1, "buttons": [button], "port": 0}]})
        if int(r.get("frames", -1)) != 1:
            raise SetupError(f"play_input advanced {r.get('frames')} frames, wanted 1 — the "
                             "walk is not frame-by-frame and the crossing sample would be "
                             "taken at an unknown time")
        got = (await rd(b, sym["Parallax_Prev_Sec_X"], 1),
               await rd(b, sym["Parallax_Prev_Sec_Y"], 1))
        if got == want:
            return await sample(b, sym, k), i
    raise SetupError(
        f"held `{button}` for {WALK_MAX_FRAMES} frames and Parallax_Prev_Sec_X/Y never "
        f"reached {want} — the walk never crossed the boundary, so NOTHING about the "
        "crossing was measured. This is not a skip: either the pad no longer moves the "
        "player in this shape, or the boot position/route below has gone stale.")


async def settle(b, sym, k, frames: int) -> dict:
    """Run the transition window out with the pad RELEASED, then align on the top of Update.

    The alignment matters: `play_input`/`run_frames` stop wherever the frame ended, which can
    be between `Camera_Update` and `Parallax_CheckBoundary`; at `GameState_OJZScroll_Update`'s
    first instruction both have run against the same camera, so a camera-derived section and
    `Parallax_Prev_Sec_X/Y` are comparable.
    """
    await _c(b, "emulator/run_frames", {"frames": frames})
    await run_to_sym(b, sym, "GameState_OJZScroll_Update", ALIGN_MAX_FRAMES)
    return await sample(b, sym, k)


# ---- verdict helpers ---------------------------------------------------------

def _fail(msgs: list[str], cond: bool, text: str) -> None:
    if not cond:
        msgs.append(text)


def rung_story(got: int, rungs: dict, inv: dict) -> str:
    """Name the rung the observed pointer belongs to, so a red says WHICH precedence the
    engine appears to be using rather than only that it is wrong."""
    for key, label in (("sec", "rung 1 Sec.sec_parallax_config"),
                       ("preset", "rung 2 EffectsPreset.ep_parallax"),
                       ("act", "rung 3 Act.act_parallax_config")):
        if got and got == rungs[key]:
            return f"that pointer is this section's {label}"
    return "that pointer is none of this section's three rungs"


def check_crossing(fails: list, who: str, sec: tuple, cross: dict, final: dict,
                   ra: RomAct, inv: dict, k: dict) -> None:
    """Every assertion about one crossing. `cross` is the sample from the frame the crossing
    happened in; `final` is after the transition window closed."""
    want, rung = ra.resolve_parallax(*sec)
    rungs = ra.rungs(*sec)
    trans = ra.transition(want)
    got, how = installed(cross)

    # 1. THE CROSSING ITSELF — the resolver's answer for the section entered, in whichever
    #    cell Parallax_StartTransition's fork put it.
    _fail(fails, got == want,
          f"{who}: crossing into section {sec} installed {sym_name(got, inv)} ({how}), but "
          f"Effects_ResolveParallax resolves that section to {sym_name(want, inv)} [{rung}]. "
          f"{rung_story(got, rungs, inv)}. This section's three rungs are: "
          f"1 Sec.sec_parallax_config {sym_name(rungs['sec'], inv)}; "
          f"2 EffectsPreset.ep_parallax {sym_name(rungs['preset'], inv)}; "
          f"3 Act.act_parallax_config {sym_name(rungs['act'], inv)}")

    # 2. THE FORK ITSELF, against the entered config's own pcfg_transition byte. A config
    #    that snapped when its byte says lerp (or the reverse) is installing by a path other
    #    than the one the data asks for, even when the pointer happens to be right.
    if trans:
        _fail(fails, cross["frames"] == 0 and cross["target"] == 0,
              f"{who}: {sym_name(want, inv)} declares pcfg_transition = {trans} (instant), so "
              f"Parallax_StartTransition must swap Current_Config and clear the stage — but "
              f"at the crossing Target_Config = {sym_name(cross['target'], inv)} with "
              f"{cross['frames']} transition frames left")
    else:
        _fail(fails, 0 < cross["frames"] <= k["TRANS"],
              f"{who}: {sym_name(want, inv)} declares pcfg_transition = 0 (smooth), so the "
              f"crossing must stage it for up to PARALLAX_TRANS_DEFAULT = {k['TRANS']} "
              f"frames — but Parallax_Transition_Frames reads {cross['frames']}")

    # 3. AFTER THE WINDOW — Parallax_Current_Config itself, which is what the booking asked
    #    for in those words. Staged or snapped, this is where both shapes must agree.
    _fail(fails, final["current"] == want,
          f"{who}: {k['SETTLE']} frames after the crossing (PARALLAX_TRANS_DEFAULT is "
          f"{k['TRANS']}) Parallax_Current_Config reads {sym_name(final['current'], inv)}, "
          f"but section {sec} resolves to {sym_name(want, inv)} [{rung}]. "
          f"{rung_story(final['current'], rungs, inv)}")
    _fail(fails, final["target"] == 0 and final["frames"] == 0,
          f"{who}: the transition never closed — {k['SETTLE']} frames after the crossing "
          f"Parallax_Target_Config = {sym_name(final['target'], inv)} with "
          f"{final['frames']} frames left, against PARALLAX_TRANS_DEFAULT = {k['TRANS']}")

    # 4. THE SECTION IS THE ONE THE CAMERA IS IN — not merely the one the engine wrote down.
    #    Parallax_Prev_Sec_X/Y is Parallax_CheckBoundary's own bookkeeping, so testing the
    #    resolve against it alone would be circular: a crossing that computed the wrong
    #    section would commit that wrong section and then resolve it "correctly". The camera
    #    is the physical fact, and this restates CheckBoundary's centre rule against it.
    _fail(fails, final["cam_sec"] == sec,
          f"{who}: after the crossing the camera centre {final['cam']} + "
          f"({k['SCREEN_W'] // 2},{k['SCREEN_H'] // 2}) >> {k['SHIFT']} is in section "
          f"{final['cam_sec']}, not the {sec} the crossing committed to "
          f"Parallax_Prev_Sec_X/Y — the two disagree about where the camera is")
    _fail(fails, final["prev_sec"] == sec,
          f"{who}: Parallax_Prev_Sec_X/Y drifted to {final['prev_sec']} during the settle, "
          f"so the sample above is not this crossing's ({sec})")

    # 5. THE CONFIG WAS CONSUMED, not merely stored. Reg $0B is re-derived by
    #    Parallax_StartTransition from the config it installs; a crossing that parked the
    #    right pointer where nothing read it passes 1-3 and fails here.
    want_m3 = ra.mode3(want)
    _fail(fails, final["mode3"] == want_m3,
          f"{who}: the VDP reg $0B (Mode Set 3) shadow reads {final['mode3']:#05b}, but "
          f"{sym_name(want, inv)} derives {want_m3:#05b} from its deform-table fields — "
          "Parallax_StartTransition wrote the register from a different config than the one "
          "the crossing resolved")

    # 6. THE BAND PIPELINE RAN. Deliberately NOT boot_override_gate's "entries above the
    #    count are zero" form: that is sound only straight out of Parallax_Init, which zeroes
    #    the whole span. Across a crossing from a 5-band config to a 4-band one, entry [4]
    #    legitimately still holds the previous config's value.
    n = ra.band_count(want)
    for axis in ("a", "b"):
        live = final[f"scroll_{axis}"][:n]
        _fail(fails, any(live),
              f"{who}: all {n} live entries of Parallax_Current_Scroll_{axis.upper()} are 0 "
              f"after the crossing — the band pipeline never ran against "
              f"{sym_name(want, inv)} (pcfg_band_count = {n})")


# ---- main --------------------------------------------------------------------

async def main_async(args) -> int:
    k = {
        "SHIFT": emp_const("engine/system/constants.emp", "SECTION_SIZE_SHIFT"),
        "SCREEN_W": emp_const("engine/system/constants.emp", "SCREEN_WIDTH"),
        "SCREEN_H": emp_const("engine/system/constants.emp", "SCREEN_HEIGHT"),
        "BANDS": emp_const("engine/system/constants.emp", "MAX_PARALLAX_BANDS"),
        "TRANS": emp_const("engine/system/constants.emp", "PARALLAX_TRANS_DEFAULT"),
        "MODE3_OFF": emp_const("engine/vdp.emp", "VDP_MODE3_OFF"),
    }
    # The settle budget: the transition window plus a frame of slack on each side. DERIVED
    # from PARALLAX_TRANS_DEFAULT, so raising that constant cannot leave this gate sampling
    # mid-lerp and calling it a regression.
    k["SETTLE"] = k["TRANS"] + 2

    sec_off, sec_size = struct_offsets("engine/structs.emp", "Sec")
    act_off, _ = struct_offsets("engine/structs.emp", "Act")
    ep_off, _ = struct_offsets("engine/effects/preset.emp", "EffectsPreset")
    pcfg_off, pcfg_size = struct_offsets("engine/structs.emp", "parallax_config")
    if pcfg_size % 2:
        raise SetupError(f"sizeof(parallax_config) parsed as {pcfg_size}, which is ODD — "
                         "parallax.emp requires it EVEN (copy_band_entry's move.l would "
                         "address-error), so this parse disagrees with the engine")
    off = {"sec": sec_off, "act": act_off, "ep": ep_off, "pcfg": pcfg_off,
           "sec_size": sec_size}

    sym = parse_lst(args.lst)
    inv: dict[int, list[str]] = {}
    for nm, addr in sym.items():
        inv.setdefault(addr, []).append(nm)
    for need in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update",
                 "Boot_At_X", "Boot_At_Y", "Boot_At_Flag", "Camera_X", "Camera_Y",
                 "Parallax_Prev_Sec_X", "Parallax_Prev_Sec_Y", "Parallax_Current_Config",
                 "Parallax_Target_Config", "Parallax_Transition_Frames",
                 "Parallax_Current_Scroll_A", "Parallax_Current_Scroll_B",
                 "VDP_Shadow_Table", "Logic_Tick", "OJZ_Act1_Descriptor"):
        if need not in sym:
            raise SetupError(f"symbol {need} is not in {args.lst} — wrong ROM shape? "
                             "(this gate needs the sonic4 DEBUG listing)")

    rom_img = Path(args.rom).read_bytes()
    d = sym["OJZ_Act1_Descriptor"]
    if d >= len(rom_img):
        raise SetupError(f"OJZ_Act1_Descriptor {d:#x} is past the end of {args.rom}")
    ra = RomAct(rom_img, d, off)

    # THE ROUTE, derived. The authored start section is (0,0) and the act is a grid of
    # 1<<SECTION_SIZE_SHIFT px sections, so the first vertical boundary sits at that width.
    # Start an eighth of a section short of it (a short walk, unambiguously inside (0,0)) at
    # half a section down (so the walk cannot touch a horizontal boundary).
    size = 1 << k["SHIFT"]
    home, away = (0, 0), (1, 0)
    boot_x, boot_y = size - size // 8, size // 2
    if not (0 <= boot_x < size and 0 <= boot_y < size):
        raise SetupError(f"the derived boot point ({boot_x},{boot_y}) is not inside section "
                         f"{home} of a {size}px grid")
    if away[0] >= ra.grid_w or away[1] >= ra.grid_h:
        raise SetupError(f"this act's grid is {ra.grid_w}x{ra.grid_h}, so there is no section "
                         f"{away} to cross into — the route has gone stale")

    # THE PREMISE, and it is a setup error rather than a pass when it fails. Section (0,0) is
    # the only section that binds its own config, and the whole content of the booking is
    # that rung 1 must beat rungs 2 and 3 there. If any two of its three rungs ever hold the
    # SAME pointer, a resolver with the old (preset-first) precedence would be
    # indistinguishable from the correct one and every assertion below would be vacuous.
    hr = ra.rungs(*home)
    home_cfg, home_rung = ra.resolve_parallax(*home)
    away_cfg, away_rung = ra.resolve_parallax(*away)
    if not hr["sec"]:
        raise SetupError(
            f"section {home} no longer binds Sec.sec_parallax_config, so a crossing into it "
            "cannot witness rung 1 at all. That binding (the aurora editor scene) is the "
            "entire reason DEFERRED_WORK item (a) became measurable; if content dropped it, "
            "say so in DEFERRED_WORK rather than letting this gate go green on rung 3.")
    if not hr["preset"]:
        raise SetupError(
            f"section {home}'s preset no longer binds ep_parallax, so rung 1 beating rung 2 "
            "— the exact defect the precedence closure fixed — is unwitnessable here: a "
            "resolver that skipped rung 1 would fall to rung 3 and this gate could not tell "
            "that from a resolver that skipped rung 2 as well.")
    for a, b_, why in ((hr["sec"], hr["preset"], "rungs 1 and 2"),
                       (hr["sec"], hr["act"], "rungs 1 and 3"),
                       (hr["preset"], hr["act"], "rungs 2 and 3")):
        if a == b_:
            raise SetupError(
                f"section {home}'s {why} both hold {sym_name(a, inv)}, so a resolver using "
                "the wrong precedence would install exactly what the right one does and the "
                "crossing witness below cannot fail. Rebind the content or record in "
                "DEFERRED_WORK that this act can no longer witness the precedence.")
    if home_cfg == away_cfg:
        raise SetupError(
            f"sections {home} and {away} both resolve to {sym_name(home_cfg, inv)}, so a "
            "crossing between them changes nothing observable and neither direction of the "
            "walk below is a test.")

    # ---- the run -------------------------------------------------------------
    async with Server(args.rom) as s:
        b = s.client
        await boot_at(b, sym, args.lst, boot_x, boot_y)
        # ONE tick before the baseline sample, and that frame is not slack. `Parallax_Init`
        # seeds Parallax_Prev_Sec_X/Y to the $FF,$FF sentinel on purpose, so at the init's
        # exit the trackers name no section at all; the first `Parallax_CheckBoundary` of the
        # update loop is what commits the start section (a no-op against the config the init
        # already selected). Sampling before that would read $FF,$FF — which is what this
        # gate did on its first run.
        start = await settle(b, sym, k, 1)
        cross_a, walk_a = await walk_to_section(b, sym, k, "right", away)
        final_a = await settle(b, sym, k, k["SETTLE"])
        cross_b, walk_b = await walk_to_section(b, sym, k, "left", home)
        final_b = await settle(b, sym, k, k["SETTLE"])
        # STILL ALIVE? Every assertion above reads RAM, and RAM that stopped changing because
        # the 68000 parked in the error handler reads exactly like RAM that settled.
        t0 = final_b["tick"]
        await _c(b, "emulator/run_frames", {"frames": 2})
        t1 = await rd(b, sym["Logic_Tick"], 4)

    fails: list[str] = []

    # 0. THE BASELINE, before any crossing: the boot put us in the home section on the home
    #    section's config. Not a restatement of boot_override_gate's witness (that one samples
    #    at the init's exit; this is after the first Update tick, so the first
    #    Parallax_CheckBoundary has already re-crossed into the same section) — it is the
    #    control that says the walk starts from a KNOWN state, so a later reading of
    #    `home_cfg` cannot be the value that was simply never touched.
    _fail(fails, start["prev_sec"] == home,
          f"baseline: the boot at ({boot_x},{boot_y}) left Parallax_Prev_Sec_X/Y at "
          f"{start['prev_sec']}, not the intended start section {home}")
    _fail(fails, start["current"] == home_cfg,
          f"baseline: the boot seeded Parallax_Current_Config = "
          f"{sym_name(start['current'], inv)}, but section {home} resolves to "
          f"{sym_name(home_cfg, inv)} [{home_rung}] — the walk would start from an unknown "
          "config and neither crossing below would mean anything")

    # A. OUTBOUND — into a section that binds NOTHING, so the resolver must fall to rung 3.
    check_crossing(fails, f"crossing A {home}->{away}", away, cross_a, final_a, ra, inv, k)
    # A NEGATIVE CONTROL THAT IS NOT FREE: crossing A must actually have CHANGED the config.
    # Without this, a resolver frozen on the away config would satisfy A on its own.
    _fail(fails, final_a["current"] != start["current"],
          f"crossing A: Parallax_Current_Config is still {sym_name(start['current'], inv)} — "
          f"section {away} resolves to {sym_name(away_cfg, inv)} [{away_rung}] and "
          f"section {home} to {sym_name(home_cfg, inv)}, so a crossing that changed nothing "
          "did not resolve anything")

    # B. INBOUND — the crossing DEFERRED_WORK item (a) names. Into the section aurora bound,
    #    where rung 1 must beat both the preset's ep_parallax and the act default.
    check_crossing(fails, f"crossing B {away}->{home}", home, cross_b, final_b, ra, inv, k)
    _fail(fails, final_b["current"] != final_a["current"],
          f"crossing B: Parallax_Current_Config is still {sym_name(final_a['current'], inv)} "
          f"from crossing A — section {home} resolves to {sym_name(home_cfg, inv)} "
          f"[{home_rung}], so the crossing back never re-resolved")
    # Said in the booking's own terms, because this is the sentence the reader carries away.
    _fail(fails, final_b["current"] == hr["sec"],
          f"crossing B: after re-entering section {home}, Parallax_Current_Config is "
          f"{sym_name(final_b['current'], inv)} and NOT the per-section editor record "
          f"{sym_name(hr['sec'], inv)} that section binds through Sec.sec_parallax_config. "
          f"The preset's ep_parallax is {sym_name(hr['preset'], inv)} and the act default is "
          f"{sym_name(hr['act'], inv)}; landing on either means the crossing is resolving "
          "with the wrong precedence, which is exactly the 2026-08-26 defect")

    _fail(fails, t1 > t0,
          f"Logic_Tick stuck at ({t0}, {t1}) after the walk — the 68000 is parked (the error "
          "handler?), so every reading above is of a machine that stopped running")

    report = {
        "route": {"boot": [boot_x, boot_y], "section_px": size,
                  "home": list(home), "away": list(away),
                  "walk_frames": {"out": walk_a, "back": walk_b},
                  "settle_frames": k["SETTLE"]},
        "rungs_at_home": {
            "1_sec_parallax_config": sym_name(hr["sec"], inv),
            "2_ep_parallax": sym_name(hr["preset"], inv),
            "3_act_parallax_config": sym_name(hr["act"], inv),
            "resolves_to": sym_name(home_cfg, inv), "rung": home_rung,
        },
        "away_resolves_to": sym_name(away_cfg, inv), "away_rung": away_rung,
        "baseline": {"prev_sec": list(start["prev_sec"]),
                     "current": sym_name(start["current"], inv)},
        "crossing_a": {
            "at_crossing": sym_name(installed(cross_a)[0], inv), "how": installed(cross_a)[1],
            "frames_left": cross_a["frames"],
            "settled": sym_name(final_a["current"], inv),
            "mode3": final_a["mode3"], "mode3_derived": ra.mode3(away_cfg),
            "bands": ra.band_count(away_cfg),
            "pcfg_transition": ra.transition(away_cfg),
        },
        "crossing_b": {
            "at_crossing": sym_name(installed(cross_b)[0], inv), "how": installed(cross_b)[1],
            "frames_left": cross_b["frames"],
            "settled": sym_name(final_b["current"], inv),
            "mode3": final_b["mode3"], "mode3_derived": ra.mode3(home_cfg),
            "bands": ra.band_count(home_cfg),
            "pcfg_transition": ra.transition(home_cfg),
        },
        "logic_tick": [t0, t1],
        "fails": fails,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"parallax_crossing_gate: OJZ act 1, {size}px sections, boot "
              f"({boot_x},{boot_y}) in {home}")
        print(f"  section {home} rungs — 1 Sec.sec_parallax_config "
              f"{sym_name(hr['sec'], inv)}")
        print(f"                         2 EffectsPreset.ep_parallax "
              f"{sym_name(hr['preset'], inv)}")
        print(f"                         3 Act.act_parallax_config "
              f"{sym_name(hr['act'], inv)}")
        print(f"    -> resolves to {sym_name(home_cfg, inv)} [{home_rung}]; section {away} "
              f"-> {sym_name(away_cfg, inv)} [{away_rung}]")
        print(f"  baseline (post-boot, pre-crossing): prev_sec {start['prev_sec']}, "
              f"config {sym_name(start['current'], inv)}")
        for label, sec, cr, fi, walk, cfgw in (
                ("A", away, cross_a, final_a, walk_a, away_cfg),
                ("B", home, cross_b, final_b, walk_b, home_cfg)):
            got, how = installed(cr)
            print(f"  crossing {label} -> {sec} after {walk} walked frames: {how} "
                  f"{sym_name(got, inv)} (pcfg_transition="
                  f"{ra.transition(cfgw)}, {cr['frames']} frames left)")
            print(f"    settled +{k['SETTLE']}f: Parallax_Current_Config "
                  f"{sym_name(fi['current'], inv)}; reg $0B {fi['mode3']:#05b} "
                  f"(derived {ra.mode3(cfgw):#05b}); pcfg_band_count {ra.band_count(cfgw)}")
        print(f"  walk cost: {walk_a} frames out, {walk_b} frames back; "
              f"Logic_Tick {t0} -> {t1}")
    if fails:
        print("FAIL:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("parallax_crossing_gate: PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        return asyncio.run(main_async(args))
    except SetupError as e:
        print(f"SETUP ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
