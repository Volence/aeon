#!/usr/bin/env python3
"""boot_override_gate — does the DEBUG boot-position override put the FIRST
displayed frame at the editor cursor, with the same streaming the warp produces?

WHAT IS BEING ASSERTED, AND WHY IT IS A DIFFERENT QUESTION FROM THE WARP'S.

`warp_mailbox_gate` asks "does a mid-play teleport land a coherent frame?". This
asks "does a BOOT land a coherent frame somewhere other than the authored start?",
which is a different mechanism with a different failure mode. The override does not
re-seed anything: it substitutes for the authored start at the point the level init
consumes it, so every streaming step below the hook (Section_Init, Player_BoundsInit,
Tile_Cache_Init, the synchronous plane fill, the parallax config select) runs once,
in its authored order, already aimed at the destination. The failure this gate exists
to catch is therefore NOT tearing-over-time but a HOOK IN THE WRONG PLACE: a consumer
that reads the authored start after the override wrote, or an override applied after
a consumer already latched the authored one. Both show up as "the boot streams the
wrong place", and both are visible in the very first displayed frame.

THE REFERENCE IS NOT DECLARED — IT IS THE WARP. There is no authored "correct
nametable" for an arbitrary cursor, and deriving one by walking (what warp_mailbox_gate
does) would re-litigate a question that gate already settled. The warp is proven
coherent AT THE SAME DESTINATION by that gate, so this one uses it directly: boot
normally, warp to (X,Y), settle — that is the reference. Then boot WITH the override
at the same (X,Y), settle the same budget, and the visible plane-A window must be
IDENTICAL. If the boot override streams somewhere else, or streams the right place
badly, it cannot match a warp that streamed it well.

...EXCEPT FOR THE SECOND CONSUMER, WHERE THE WARP IS NOT A REFERENCE AT ALL. The override
feeds two consumers: the placement hook (camera + leader), which the plane/scanline
comparison above witnesses hard, and the init's PARALLAX CONFIG SELECT, which must read the
section containing the destination rather than `Act.start_sec_x/y`. The warp cannot arbitrate
that one, for a reason that is about mechanism and not resolution: the warp sets
`Parallax_Snap_Pending`, so it SNAPS to the destination section's config, and a boot whose
select picked the WRONG config is corrected a few frames later by the first
`Parallax_CheckBoundary` (which re-selects from the camera — already the destination).
Settle either route long enough and both land on the same config, so "the init picked the
right config" and "the crossing corrected it" render identically. That is the whole content
of the author's original instruction to compare "against a walked arrival, not against a warp
that snaps".

This gate takes the other option that instruction allowed — a DIRECT READBACK of the
installed config, sampled at the init's EXIT (`GameState_OJZScroll_Update`'s first
instruction), before a single Update tick can launder the answer. Three observables, all
derived from the ROM's own section grid, never pinned:

  * `Parallax_Current_Config` must equal `Effects_ResolveParallax`'s answer for the
    DESTINATION's section (Sec.sec_parallax_config > EffectsPreset.ep_parallax >
    Act.act_parallax_config), and the control's must equal the AUTHORED section's. The gate
    refuses to run (setup error) if those two resolve the same, because then the witness
    could not fail.
  * `Parallax_Target_Config` = 0 and `Parallax_Transition_Frames` = 0 — the init SEEDED the
    config, it did not stage a transition toward it.
  * IN ADDITION, and stronger in kind because a pointer in a cell proves only storage: the
    VDP reg $0B (Mode Set 3) shadow and the band-scroll tail, both of which `Parallax_Update`
    writes FROM the active config. Reg $0B is %11 for every config since 2026-08-26 (plus
    bit 2 for a V-deform table); the tail from its `pcfg_band_count` against the span
    `Parallax_Init` zeroed. A
    select that stored the right pointer where nothing read it passes the first check and
    fails these.

(Until 2026-08-26 this half was UNWITNESSED and the gate said so with a premise tripwire —
every act 1 section deferred to the act default, so the select was unobservable. Aurora's
first authored scene made it observable and the tripwire fired as designed; this is its
replacement.)

THE VISIBLE WINDOW, NOT THE WHOLE PLANE, and for warp_mailbox_gate's reason: the
nametable is a 512x512 px ring behind a 320x224 view, so three quarters of it holds
whatever was last written there and is legitimately path-dependent. 41x29 cells covers
the view including both partial edge cells.

THE TIMING TRUTH THIS GATE ENCODES. Boot clears ALL 64KB of Work RAM
(engine/system/boot.emp `.clear_ram`), so the mailbox CANNOT be written at the
reset-paused machine — a pre-resume write is zeroed before the init can see it. The
supported client window is after that clear and before the init: `emulator/run_to`
GameState_OJZScroll_Init, write X/Y/flag, then continue. Every run below uses exactly
that sequence, so the gate is also the executable spec of the client procedure. (A
pre-resume write is not merely unsupported — run PRE proves it is silently ignored.)

THE RUNS (each a fresh oracle-aether process, each from reset):

    control   no write at all                -> the authored start, byte-for-byte today
    override  write at the init breakpoint   -> the destination, from the first frame
    warp      boot + mailbox warp there      -> the REFERENCE plane for `override`
    clamp     a request past the act edge    -> clamped AND published back
    poisonA   flag set, garbage X/Y          -> clamped, machine still alive
    poisonB   cells written, flag NOT set    -> boots authored (the flag is the gate)
    pre       cells written BEFORE resume    -> boots authored (the RAM clear ate them)

EXPECTATIONS ARE DERIVED, NEVER COPIED. The authored start comes out of the ROM's own
act descriptor; the clamp edges out of `grid_w/grid_h` and the two constants
Player_BoundsInit uses; the tile-cache window out of Tile_Cache_Init's arithmetic
against engine/system/constants.emp; the two parallax configs out of the section grid
through a restatement of Effects_ResolveParallax. Nothing here is a number lifted from
a pin.

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
    AetherInstance, SpawnError, WrongServerError, run_to_addr)
from raster_cost_probe import parse_lst  # noqa: E402

BOOT_MAX_FRAMES = 600        # ceiling for run_to(Init) / run_to(Update); the DEBUG shape
                             # boots straight into the OJZ scroll test, no buttons pressed
SETTLE = 30                  # the sample budget, identical for override and warp
PAINT_LAG = 2                # frames between the init's RETURN and the first fully painted
                             # frame. MEASURED, not assumed: the init enables the display
                             # through the VDP shadow, which the next VBlank flushes, so the
                             # frame in progress is still blanked and the one after it is the
                             # first the beam draws whole. Sampling earlier reads a black
                             # raster (probe: 1 colour at +0f and +1f, 5-9 from +2f on) and
                             # would make the colour control a lie either way.
ACK_MAX_FRAMES = 120         # the warp reference's ack poll ceiling

# THE DESTINATION. Diagonal and multi-section on both axes so a hook that only fixed one
# axis (or only the camera, or only the player) cannot pass: OJZ act 1 is a 3x3 grid of
# 2048 px sections and the authored start is in section (0,0), so this lands in (1,1) —
# a different section, hence a different parallax config, which is the second consumer.
DEST_X, DEST_Y = 2560, 2400

SCANLINE_START, SCANLINE_COUNT = 100, 8

# Sst field offsets — the listing's own equates would do, but parse_lst reads addresses
# only, and these two are the whole of what a placement check needs.
SST_X_POS, SST_Y_POS = 0x02, 0x06

# Sec record (engine/structs.emp `struct Sec`, sizeof 66 — pinned by an `ensure` in
# engine/level/section.emp because the generated grid data assumes it).
SEC_SIZE = 66
SEC_PARALLAX_CONFIG = 0x14
SEC_EFFECTS = 0x34
ACT_SEC_GRID_PTR = 0x00

# Act descriptor field offsets (engine/structs.emp `struct Act`).
ACT_GRID_W, ACT_GRID_H = 0x04, 0x06
ACT_START_LX, ACT_START_LY = 0x08, 0x0A
ACT_START_SX, ACT_START_SY = 0x0C, 0x0D
ACT_PARALLAX_CONFIG = 0x16

# EffectsPreset (engine/effects/preset.emp) — the middle rung of the resolution below.
EP_PARALLAX = 0x04

# parallax_config (engine/structs.emp `struct parallax_config`) — only the fields the two
# derivations below read. PCFG_V_DEFORM_TABLE_BG shares its offset with SEC_PARALLAX_CONFIG
# by coincidence; they are different structs.
PCFG_BAND_COUNT = 0x00
PCFG_DEFORM_TABLE_FG = 0x0C
PCFG_DEFORM_TABLE_BG = 0x10
PCFG_V_DEFORM_TABLE_BG = 0x14


class SetupError(Exception):
    """Something made the measurement impossible. Not a verdict — exit 2, never exit 1."""


def emp_const(rel: str, name: str) -> int:
    """A `const NAME = $HEX` / `= 123` out of an .emp source, so the gate cannot drift."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        raise SetupError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


class Server:
    """One oracle-aether process. A fresh one per run — every run starts from reset.

    Spawning is `tools/aether_instance.AetherInstance` since 2026-08-26 — this gate used to
    carry its own hand-copied Popen loop (one of three such copies in the tree, booked in
    DEFERRED_WORK). What that copy lacked and this gains: readiness by socket ACCEPT rather
    than by the socket FILE existing (a file can exist before the listener binds), a private
    mkdtemp socket instead of a shared /tmp path, PR_SET_PDEATHSIG so a SIGKILLed gate cannot
    strand a server, the server's own output captured and quoted in a spawn failure, and an
    rmtree that removes the socket file the server leaves behind on SIGTERM.

    `AetherInstance.start()` runs its own `asyncio.run` for the handshake, so it CANNOT be
    called from inside a running loop — hence `asyncio.to_thread`. That is the one wrinkle in
    an otherwise drop-in fold, and the reason the other two aether gates are worth converting
    with the same line rather than by hand.

    The identity assertion (`assert_rust_server`) now runs inside `start()`: a gate silently
    talking to the legacy C++ server reports a verdict measured on the wrong emulator and
    nothing goes red.
    """

    def __init__(self, rom: str):
        self.rom, self.inst, self.client = rom, None, None

    async def __aenter__(self) -> "Server":
        self.inst = AetherInstance(self.rom)
        try:
            sock = await asyncio.to_thread(self.inst.start)
        except (SpawnError, WrongServerError) as e:
            raise SetupError(str(e)) from e
        self.client = BusClient(sock, client_id="bootovr",
                                client_name="boot_override_gate")
        await self.client.connect()
        for m in ("emulator/scanlines", "emulator/read_vram", "emulator/write_memory",
                  "emulator/run_to"):
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
    """Every RPC gets a deadline — a run that never breaks otherwise blocks the next
    call, which has no timeout of its own."""
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def _run_to(b, addr: int, what: str, hint: str = "", timeout: float = 180.0) -> dict:
    """`run_to` an address and INSIST the target was REACHED.

    The reply key is `reached` (oracle-aether `engine.rs`: `"reached": run.predicate_fired`).
    A run that ended on its `maxFrames` bound instead answers `reached: false` and leaves the
    machine wherever it happened to be, so every reading taken afterwards is a confident wrong
    answer rather than an error.

    ALL THREE `run_to` sites in this file route through here. Until 2026-08-26 two of them
    tested `r.get("fired", True)` — `fired` is a key this server has never emitted, so the
    default always applied and NEITHER GUARD COULD FIRE — and the third checked nothing at
    all. Measured with the same poison each time (target $00FEED, an ODD address the 68000's
    PC can never take, so the run provably ends on its bound):

      `_init_to_update`   pre-fix PASS, exit 0 — every assertion green off a machine 566
                          frames past where it should have stopped.
      `_boot_to_init`     pre-fix exit 1 with SIXTEEN confident FAIL lines blaming the
                          engine's parallax select — a setup failure dressed as a verdict.
      `run_pre_resume`    pre-fix PASS, exit 0, output BYTE-IDENTICAL to a healthy run. The
                          worst of the three: that run asserts the mailbox cells read ZERO
                          at the init, and a run that sails past the init has gone through
                          boot's RAM clear too, so it reads zero and AGREES. The gate
                          confirmed its own premise from a place it never stood.

    All three now stop at the raise below instead.

    The check is `aether_instance.run_to_addr` — the tree's one correct spelling, whose own
    docstring is about exactly this hazard. What it does not carry is this file's per-RPC
    deadline (see `_c`), which is why the call is wrapped rather than made directly; and its
    `RuntimeError` becomes this file's `SetupError`, because a run that could not reach its
    target is a measurement that could not be made (exit 2), never a verdict about the ROM.
    """
    try:
        return await asyncio.wait_for(run_to_addr(b, addr, what, BOOT_MAX_FRAMES),
                                      timeout=timeout)
    except RuntimeError as e:
        raise SetupError(f"{e}{hint}") from e


# ---- readback ---------------------------------------------------------------

def _hexint(r) -> int:
    return int(r["bytes"].removeprefix("0x").removeprefix("0X"), 16)


async def read_at(b, addr: int, n: int) -> int:
    return _hexint(await _c(b, "emulator/read_memory", {"addr": hex(addr), "len": n}))


async def read_word(b, sym, name: str) -> int:
    return await read_at(b, sym[name], 2)


async def read_long(b, sym, name: str) -> int:
    return await read_at(b, sym[name], 4)


async def frame_token(b) -> int:
    """The emulated frame index — the only clock available AT the sample points, which are
    `run_frames` returns and not `run_to` returns.

    The text here used to say `run_to` answers a `frames` count of frames advanced inside
    the call, and that a boot finishing mid-frame therefore reports a misleading 0. Both
    halves are wrong and were wrong when written. MEASURED against the live server
    (2026-08-26, DEBUG ROM): `run_to`'s whole reply key set is `caveat, droppedEvents,
    frame, maxFrames, mclk, pc, reached, running, symbol, symbolDisp, target` — there is
    no `frames`, and `r.get("frames", 0)` was reading a key that has never existed. What
    the reply does carry is `frame`, the ABSOLUTE halt index off the envelope stamp, and
    at `GameState_OJZScroll_Init` it reads 34 — the same 34 this `frameToken` reports at
    the same instant. So there was never a units problem to solve here: the reason to
    sample this way is WHERE the sample is taken, not what it counts.
    """
    return int((await _c(b, "emulator/status", {}))["frameToken"])


async def read_plane_a(b, base: int) -> list[int]:
    """Plane A's 4096 nametable WORDS, read as two 4096-byte chunks (maxReadLen = 4096)."""
    raw = ""
    for off in (0, 4096):
        r = await _c(b, "emulator/read_vram", {"addr": hex(base + off), "len": 4096})
        chunk = r["bytes"].upper().removeprefix("0X")
        if len(chunk) != 8192:
            raise SetupError(f"read_vram returned {len(chunk)//2} bytes, wanted 4096")
        raw += chunk
    return [int(raw[i:i + 4], 16) for i in range(0, len(raw), 4)]


STATE_WORDS = ["Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row", "Cache_Bottom_Row",
               "Cache_Prev_Cam_X", "Cache_Prev_Cam_Row"]


async def read_state(b, sym) -> dict:
    st = {n: await read_word(b, sym, n) for n in STATE_WORDS}
    st["Camera_X"] = (await read_long(b, sym, "Camera_X")) >> 16
    st["Camera_Y"] = (await read_long(b, sym, "Camera_Y")) >> 16
    st["Player_X"] = (await read_at(b, sym["Player_1"] + SST_X_POS, 4)) >> 16
    st["Player_Y"] = (await read_at(b, sym["Player_1"] + SST_Y_POS, 4)) >> 16
    return st


async def read_words(b, addr: int, n: int) -> list[int]:
    """`n` big-endian words from `addr`, sliced from ONE read.

    `.removeprefix("0x")` before slicing is not decoration: the Rust core prefixes every
    hex byte string and a positional slice two characters off returns plausible garbage
    with nothing raised (tools/aether_instance.py `unprefix`)."""
    r = await _c(b, "emulator/read_memory", {"addr": hex(addr), "len": n * 2})
    raw = r["bytes"].upper().removeprefix("0X")
    if len(raw) != n * 4:
        raise SetupError(f"read_memory returned {len(raw)//2} bytes, wanted {n * 2}")
    return [int(raw[i:i + 4], 16) for i in range(0, len(raw), 4)]


async def read_parallax(b, sym, bands: int, mode3_off: int) -> dict:
    """The parallax select's observable state, read where it is still the INIT's answer.

    Every field here is captured at `GameState_OJZScroll_Update`'s first instruction, i.e.
    after the init ran to completion and before a single Update tick. That timing is the
    whole point: `Parallax_Init` seeds Prev_Sec_X/Y to $FF, so the first
    `Parallax_CheckBoundary` of the update loop re-selects from the CAMERA — which under an
    override is already the destination. A poisoned select is therefore corrected a few
    frames later (as a staged smooth transition, `Parallax_StartTransition`), and any sample
    taken after the update loop starts cannot tell "the init chose right" from "the crossing
    fixed it". That is the same reason the warp is not a valid reference here."""
    return {
        "config": await read_long(b, sym, "Parallax_Current_Config"),
        "target": await read_long(b, sym, "Parallax_Target_Config"),
        "trans_frames": await read_at(b, sym["Parallax_Transition_Frames"], 1),
        "mode3": await read_at(b, sym["VDP_Shadow_Table"] + mode3_off, 1),
        "scroll_a": await read_words(b, sym["Parallax_Current_Scroll_A"], bands),
        "scroll_b": await read_words(b, sym["Parallax_Current_Scroll_B"], bands),
    }


async def snapshot(b, sym, plane_base: int) -> dict:
    st = await read_state(b, sym)
    r = await _c(b, "emulator/scanlines",
                 {"startLine": SCANLINE_START, "count": SCANLINE_COUNT})
    if r.get("source") != "raster":
        raise SetupError(f"emulator/scanlines answered source={r.get('source')!r} "
                         f"(caveat {r.get('caveat')!r}) — a post-hoc render is blind here")
    colours = set()
    for row in r["rows"]:
        h = row["rgb"].removeprefix("0x").removeprefix("0X")
        b3 = bytes.fromhex(h)
        colours |= {b3[i:i + 3] for i in range(0, len(b3), 3)}
    return {"state": st, "plane": await read_plane_a(b, plane_base),
            "colours": len(colours), "mode": r.get("mode"),
            "rows": [row["rgb"].upper().removeprefix("0X") for row in r["rows"]]}


def visible_words(snap: dict) -> list[int]:
    """The plane cells the camera is actually SHOWING, in a fixed order.

    41x29 cells covers 320x224 px including both partial edge cells. Cell (col,row)
    lives at (row & 63)*64 + (col & 63) — continuous scroll wraps the world through
    the 64x64 ring. The whole plane is NOT a valid metric (warp_mailbox_gate proved
    two correct walks disagree on it by 26 words)."""
    c0, r0 = snap["state"]["Camera_X"] >> 3, snap["state"]["Camera_Y"] >> 3
    return [snap["plane"][(r & 63) * 64 + (c & 63)]
            for r in range(r0, r0 + 29) for c in range(c0, c0 + 41)]


def word_diff(a: list[int], b: list[int]) -> int:
    if len(a) != len(b):
        raise SetupError(f"plane captures differ in length ({len(a)} vs {len(b)})")
    return sum(1 for x, y in zip(a, b) if x != y)


# ---- derived expectations ---------------------------------------------------

def derived_cache(cam_x: int, cam_y: int, k: dict) -> dict:
    """Tile_Cache_Init IS the authority; this restates its arithmetic against the
    constants read out of engine/system/constants.emp."""
    left = max(0, (cam_x >> 3) - k["MH"])
    top = max(0, (cam_y >> 3) - k["MV"]) & 0xFFFE
    return {"Cache_Left_Col": left, "Cache_Head_Col": left + k["COLS"] - 1,
            "Cache_Top_Row": top, "Cache_Bottom_Row": top + k["ROWS"] - 1,
            "Cache_Prev_Cam_X": cam_x, "Cache_Prev_Cam_Row": cam_y >> 3}


def check_cache(snap: dict, k: dict) -> list[str]:
    exp = derived_cache(snap["state"]["Camera_X"], snap["state"]["Camera_Y"], k)
    return [f"{n}={snap['state'][n]} wanted {w}" for n, w in exp.items()
            if snap["state"][n] != w]


def clamp_expect(x: int, y: int, act: dict) -> tuple[int, int]:
    """Player_BoundsInit's own formula, re-derived from the descriptor + the two
    constants it reads. Signed: bit 15 set is out of range by definition."""
    def s16(v):
        return v - 0x10000 if v & 0x8000 else v
    cx, cy = s16(x), s16(y)
    return (min(max(cx, 0), act["bound_right"]), min(max(cy, 0), act["bound_bottom"]))


def camera_expect(px: int, py: int, act: dict, k: dict) -> tuple[int, int]:
    """center_camera_on's own clamp, against Camera_Init's precomputed ceilings."""
    return (min(max(px - k["HALF_W"], 0), act["cam_x_max"]),
            min(max(py - k["HALF_H"], 0), act["cam_y_max"]))


# ---- the parallax select, derived --------------------------------------------
#
# THE OVERRIDE'S SECOND CONSUMER. Everything above witnesses the placement hook. The init
# ALSO picks the parallax config for the first painted frame, and under an override that
# select must read the section containing the DESTINATION rather than the authored
# `Act.start_sec_x/y`. What follows restates the engine's own two derivations against the
# ROM image, in the gate's house style — nothing here is a pointer copied from a pin.


class RomAct:
    """The act's section grid, read out of the ROM image. One object so the three ROM
    walks below (grid lookup, resolution, config fields) cannot disagree on the base."""

    def __init__(self, rom_img: bytes, act_base: int, grid_w: int, grid_h: int):
        self.rom, self.grid_w, self.grid_h = rom_img, grid_w, grid_h
        self.act_base = act_base
        self.grid = self.u32(act_base + ACT_SEC_GRID_PTR)
        self.act_default = self.u32(act_base + ACT_PARALLAX_CONFIG)

    def u32(self, off: int) -> int:
        if off + 4 > len(self.rom):
            raise SetupError(f"ROM read at {off:#x} is past the end of the image")
        return int.from_bytes(self.rom[off:off + 4], "big")

    def u8(self, off: int) -> int:
        if off >= len(self.rom):
            raise SetupError(f"ROM read at {off:#x} is past the end of the image")
        return self.rom[off]

    def sec_ptr(self, gx: int, gy: int) -> int | None:
        """Section_GetSecPtrXY: flat = sec_y * grid_w + sec_x, stride sizeof(Sec).
        None is that routine's "Z set = no such section", which both callers answer
        with the act default."""
        if not (0 <= gx < self.grid_w and 0 <= gy < self.grid_h):
            return None
        return self.grid + (gy * self.grid_w + gx) * SEC_SIZE

    def resolve_parallax(self, gx: int, gy: int) -> tuple[int, str]:
        """`Effects_ResolveParallax` (engine/effects/preset.emp) restated. THE one
        three-way resolution both the boot select and the crossing site call, precedence
        Sec.sec_parallax_config > EffectsPreset.ep_parallax > Act.act_parallax_config,
        a 0 at either upper rung meaning "defer" and never "keep". Returns the pointer
        and which rung produced it, so a failure message can say WHY."""
        sec = self.sec_ptr(gx, gy)
        if sec is None:
            return self.act_default, "act default (no section at that grid coord)"
        p = self.u32(sec + SEC_PARALLAX_CONFIG)
        if p:
            return p, "Sec.sec_parallax_config"
        preset = self.u32(sec + SEC_EFFECTS)
        if preset:
            p = self.u32(preset + EP_PARALLAX)
            if p:
                return p, "EffectsPreset.ep_parallax"
        return self.act_default, "Act.act_parallax_config"

    def band_count(self, cfg: int) -> int:
        return self.u8(cfg + PCFG_BAND_COUNT)

    def mode3(self, cfg: int) -> int:
        """`Parallax_Update`'s own reg $0B (Mode Set 3) derivation from the ACTIVE config:
        bits 1:0 = %11 ALWAYS (one HScroll mode since 2026-08-26, d-29-corrected — the
        per-cell %10 arm that used to key off the two H-deform table words is deleted),
        bit 2 = per-column VScroll if a V-deform table is attached. Restated here because
        this byte is the cheapest observable that proves the config was CONSUMED by the
        per-frame build rather than merely parked in Parallax_Current_Config — though with
        the H bits constant it discriminates between configs only through bit 2 now; the
        band-scroll tail is the check that still tells two configs apart.

        RED-FIRST, the other way round: this transcription carried the deleted arm until
        the deletion parcel, and the gate went red on the branch with `shadow reads 0b11,
        wanted 0b10` for EditorSceneBinding_OJZ_Act1_Sec0 (anchored, no table) — the config
        whose fill and register had disagreed on master. The fix is the derivation, not the
        engine."""
        m = 0b11
        if self.u32(cfg + PCFG_V_DEFORM_TABLE_BG):
            m |= 0b100
        return m


def sym_name(addr: int, inv: dict) -> str:
    """`0x12c38 (ParallaxConfig_OJZ_Default)` — a failure message that names both configs
    is the difference between a red gate and a red gate someone can act on."""
    if addr == 0:
        return "NULL"
    names = inv.get(addr)
    return f"{addr:#x} ({'/'.join(sorted(names))})" if names else f"{addr:#x} (unnamed)"


def check_bands(p: dict, cfg_bands: int, who: str, axis: str) -> list[str]:
    """The band-scroll tail, derived from the config's own `pcfg_band_count`.

    `Parallax_Init` zeroes the whole Parallax_State span (PARALLAX_STATE_LONGS) before
    seeding the config, and `Parallax_Update`'s band loop then writes exactly
    `pcfg_band_count` entries. So entries at and above that count must still read 0, and
    at least one below it must not (a config that produced nothing was not consumed)."""
    words = p[f"scroll_{axis}"]
    bad = [f"{who}: Parallax_Current_Scroll_{axis.upper()}[{i}] = {words[i]:#06x}, but the "
           f"selected config drives only {cfg_bands} bands and Parallax_Init zeroed the rest"
           for i in range(cfg_bands, len(words)) if words[i]]
    if not any(words[:cfg_bands]):
        bad.append(f"{who}: all {cfg_bands} live entries of Parallax_Current_Scroll_"
                   f"{axis.upper()} are 0 — the band pipeline never ran against the "
                   "selected config")
    return bad


# ---- the runs ---------------------------------------------------------------

async def _boot_to_init(b, sym, lst: str) -> None:
    """Reset, then stop at the level init's first instruction — i.e. AFTER boot's 64KB
    Work-RAM clear and BEFORE any consumer of the mailbox. THE client window.

    Returns nothing on purpose. This used to end `return int(r.get("frames", 0))` against
    a reply that has no `frames` key (see `frame_token`), so it returned a constant 0 that
    all nine call sites discarded. Deleted rather than respelled: the quantity it claimed
    to return — frames advanced INSIDE the call — does not exist on this wire at all, so
    there is nothing to rename it to.
    """
    await _c(b, "emulator/load_symbols", {"path": lst})
    await _c(b, "emulator/reset", {})
    await _run_to(b, sym["GameState_OJZScroll_Init"], "GameState_OJZScroll_Init",
                  " — wrong ROM shape?")


async def _init_to_update(b, sym) -> None:
    """Run the init out. Stopping at the UPDATE state's first instruction is the first
    frame the display is on with the init's synchronous plane fill complete — 'the first
    visible frame' made operable. Returns nothing, for `_boot_to_init`'s reason."""
    await _run_to(b, sym["GameState_OJZScroll_Update"], "GameState_OJZScroll_Update")


async def _write_mailbox(b, sym, prefix: str, x: int, y: int, flag: int = 1) -> None:
    """X, then Y, then the FLAG last — the write order IS the protocol."""
    await _c(b, "emulator/write_memory", {"addr": hex(sym[f"{prefix}_X"]), "value": x,
                                          "width": 2})
    await _c(b, "emulator/write_memory", {"addr": hex(sym[f"{prefix}_Y"]), "value": y,
                                          "width": 2})
    if flag:
        await _c(b, "emulator/write_memory", {"addr": hex(sym[f"{prefix}_Flag"]),
                                              "value": flag, "width": 1})


async def run_control(rom, sym, lst, k, plane_base: int) -> dict:
    """No write at all: today's boot, unchanged."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _init_to_update(b, sym)
        # The parallax select AT the init's exit — see read_parallax for why this sample
        # cannot be taken any later.
        parallax = await read_parallax(b, sym, k["BANDS"], k["MODE3_OFF"])
        # Past the init to the first FULLY PAINTED frame — see PAINT_LAG.
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        t_playable = await frame_token(b)
        first = await snapshot(b, sym, plane_base)
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        return {"t_playable": t_playable, "parallax": parallax,
                "first": first, "final": await snapshot(b, sym, plane_base),
                "boot_flag": await read_at(b, sym["Boot_At_Flag"], 1)}


async def run_override(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """The subject: write at the init breakpoint, then let the init consume it."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _write_mailbox(b, sym, "Boot_At", x, y)
        await _init_to_update(b, sym)
        # The state AT the init's exit — before a single Update tick has run. This is
        # where "the init aimed ITSELF at the override" is either true or not.
        at_exit = await read_state(b, sym)
        parallax = await read_parallax(b, sym, k["BANDS"], k["MODE3_OFF"])
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        t_playable = await frame_token(b)
        first = await snapshot(b, sym, plane_base)
        published = (await read_word(b, sym, "Boot_At_X"),
                     await read_word(b, sym, "Boot_At_Y"))
        flags = {"Boot_At_Flag": await read_at(b, sym["Boot_At_Flag"], 1),
                 "Warp_Req_Flag": await read_at(b, sym["Warp_Req_Flag"], 1)}
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        final = await snapshot(b, sym, plane_base)
        # STILL ALIVE? Tile_Cache_Init's DEBUG tail runs PageCache_Audit, and a bad
        # residency reset raises and parks the 68000 in the error handler. A Logic_Tick
        # that still advances is the proof the audit passed.
        t0 = await read_long(b, sym, "Logic_Tick")
        await _c(b, "emulator/run_frames", {"frames": 2})
        t1 = await read_long(b, sym, "Logic_Tick")
        return {"t_playable": t_playable, "at_exit": at_exit, "parallax": parallax,
                "first": first, "final": final, "published": published, "flags": flags,
                "ticks": (t0, t1)}


async def run_warp_reference(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """The REFERENCE: today's supported route to the same place — boot, then warp."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _init_to_update(b, sym)
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})   # the same first-painted-
                                                                    # frame baseline the
                                                                    # override run uses
        await _write_mailbox(b, sym, "Warp_Req", x, y)
        acked = None
        for i in range(1, ACK_MAX_FRAMES + 1):
            await _c(b, "emulator/run_frames", {"frames": 1})
            if await read_at(b, sym["Warp_Req_Flag"], 1) == 0:
                acked = i
                break
        if acked is None:
            raise SetupError(f"Warp_Req_Flag never cleared in {ACK_MAX_FRAMES} frames")
        t_playable = await frame_token(b)
        await _c(b, "emulator/run_frames", {"frames": SETTLE})
        return {"t_playable": t_playable, "ack_frames": acked,
                "final": await snapshot(b, sym, plane_base),
                "published": (await read_word(b, sym, "Warp_Req_X"),
                              await read_word(b, sym, "Warp_Req_Y"))}


async def run_flag_clear(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """POISON: cells written, FLAG NOT SET. Must boot authored, and must NOT publish —
    an override that ran anyway, or a clamp that ran anyway, both show here."""
    async with Server(rom) as s:
        b = s.client
        await _boot_to_init(b, sym, lst)
        await _write_mailbox(b, sym, "Boot_At", x, y, flag=0)
        await _init_to_update(b, sym)
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        first = await snapshot(b, sym, plane_base)
        return {"first": first, "cells": (await read_word(b, sym, "Boot_At_X"),
                                          await read_word(b, sym, "Boot_At_Y"))}


async def run_pre_resume(rom, sym, lst, k, plane_base: int, x: int, y: int) -> dict:
    """THE TIMING TRUTH, made a measurement: write the mailbox at the RESET-PAUSED
    machine, the way the warp mailbox's prose would suggest. Boot's 64KB Work-RAM clear
    eats it, so the boot must be the AUTHORED one and the cells must read back zero.
    This is why the client procedure is a breakpoint and not a pre-resume poke."""
    async with Server(rom) as s:
        b = s.client
        await _c(b, "emulator/load_symbols", {"path": lst})
        await _c(b, "emulator/reset", {})
        await _write_mailbox(b, sym, "Boot_At", x, y)
        # This run CANNOT go unchecked, and this site is the sharpest of the three: the
        # assertion below is that the cells read ZERO, and a run that overshoots the init
        # has passed through the RAM clear too — so it reads zero, agrees, and the gate
        # confirms its premise without ever having stood where it claims to stand.
        # MEASURED: with this target poisoned to $00FEED the pre-fix gate printed PASS,
        # exit 0, output BYTE-IDENTICAL to a healthy run. See `_run_to`.
        await _run_to(b, sym["GameState_OJZScroll_Init"], "GameState_OJZScroll_Init",
                      " — wrong ROM shape?")
        at_init = (await read_word(b, sym, "Boot_At_X"),
                   await read_word(b, sym, "Boot_At_Y"),
                   await read_at(b, sym["Boot_At_Flag"], 1))
        await _init_to_update(b, sym)
        await _c(b, "emulator/run_frames", {"frames": PAINT_LAG})
        return {"at_init": at_init, "first": await snapshot(b, sym, plane_base)}


# ---- main -------------------------------------------------------------------

def _fail(msgs: list[str], cond: bool, text: str) -> None:
    if not cond:
        msgs.append(text)


async def main_async(args) -> int:
    k = {
        "COLS": emp_const("engine/system/constants.emp", "TILE_CACHE_COLS"),
        "ROWS": emp_const("engine/system/constants.emp", "TILE_CACHE_ROWS"),
        "MH": emp_const("engine/system/constants.emp", "TILE_CACHE_MARGIN_H"),
        "MV": emp_const("engine/system/constants.emp", "TILE_CACHE_MARGIN_V"),
        "HALF_W": emp_const("engine/system/constants.emp", "CAM_SCREEN_HALF_W"),
        "HALF_H": emp_const("engine/system/constants.emp", "CAM_SCREEN_HALF_H"),
        "SHIFT": emp_const("engine/system/constants.emp", "SECTION_SIZE_SHIFT"),
        "SCREEN_W": emp_const("engine/system/constants.emp", "SCREEN_WIDTH"),
        "SCREEN_H": emp_const("engine/system/constants.emp", "SCREEN_HEIGHT"),
        "PBOUND": emp_const("games/sonic4/player/player_common.emp", "PBOUND_RIGHT_MARGIN"),
        "BANDS": emp_const("engine/system/constants.emp", "MAX_PARALLAX_BANDS"),
        "MODE3_OFF": emp_const("engine/vdp.emp", "VDP_MODE3_OFF"),
    }
    plane_base = emp_const("engine/system/constants.emp", "VRAM_PLANE_A")
    sym = parse_lst(args.lst)
    inv: dict[int, list[str]] = {}
    for nm, addr in sym.items():
        inv.setdefault(addr, []).append(nm)
    for need in ("Boot_At_X", "Boot_At_Y", "Boot_At_Flag", "Warp_Req_X", "Warp_Req_Y",
                 "Warp_Req_Flag", "GameState_OJZScroll_Init", "GameState_OJZScroll_Update",
                 "Camera_X", "Camera_Y", "Logic_Tick", "Player_1",
                 "Parallax_Current_Config", "Parallax_Target_Config",
                 "Parallax_Transition_Frames", "Parallax_Current_Scroll_A",
                 "Parallax_Current_Scroll_B", "VDP_Shadow_Table",
                 "OJZ_Act1_Descriptor", *STATE_WORDS):
        if need not in sym:
            raise SetupError(f"symbol {need} is not in {args.lst} — wrong ROM shape? "
                             "(this gate needs the sonic4 DEBUG listing)")

    # The act descriptor, read out of the ROM image itself — the authored start and the
    # clamp edges are DERIVED from it, never typed here.
    rom_img = Path(args.rom).read_bytes()
    d = sym["OJZ_Act1_Descriptor"]
    if d >= len(rom_img):
        raise SetupError(f"OJZ_Act1_Descriptor {d:#x} is past the end of {args.rom}")

    def rw(off):
        return int.from_bytes(rom_img[d + off:d + off + 2], "big")

    act = {
        "grid_w": rw(ACT_GRID_W), "grid_h": rw(ACT_GRID_H),
        "start_lx": rw(ACT_START_LX), "start_ly": rw(ACT_START_LY),
        "start_sx": rom_img[d + ACT_START_SX], "start_sy": rom_img[d + ACT_START_SY],
    }
    act["level_w"] = act["grid_w"] << k["SHIFT"]
    act["level_h"] = act["grid_h"] << k["SHIFT"]
    act["bound_right"] = act["level_w"] - k["PBOUND"]
    act["bound_bottom"] = act["level_h"] - k["SCREEN_H"]
    act["cam_x_max"] = act["level_w"] - k["SCREEN_W"]
    act["cam_y_max"] = act["level_h"] - k["SCREEN_H"]
    # The authored start as the init ladder actually produces it: Camera_Init clamps the
    # seed, and the spawn is camera + half-screen. Near a world edge those disagree with
    # the raw start point, which is exactly why this is computed and not assumed.
    a_start_x = (act["start_sx"] << k["SHIFT"]) + act["start_lx"]
    a_start_y = (act["start_sy"] << k["SHIFT"]) + act["start_ly"]
    a_cam_x = min(max(a_start_x - k["HALF_W"], 0), act["cam_x_max"])
    a_cam_y = min(max(a_start_y - k["HALF_H"], 0), act["cam_y_max"])
    authored = (a_cam_x + k["HALF_W"], a_cam_y + k["HALF_H"])

    dest = (args.x, args.y)
    dest_clamped = clamp_expect(*dest, act)
    dest_cam = camera_expect(*dest_clamped, act, k)
    # A destination that clamps is not testing what this gate is about.
    if dest_clamped != dest:
        raise SetupError(f"destination {dest} clamps to {dest_clamped} in this act — "
                         "pick one inside the bounds for the main runs")

    # WAS: a PREMISE TRIPWIRE. Until 2026-08-26 these lines asserted that no OJZ act 1
    # section bound its own `sec_parallax_config` and raised a setup error the day one did,
    # because while every section deferred to the act default the init's parallax select —
    # the override's SECOND consumer — returned the same pointer whatever section index it
    # was handed, so poisoning it changed nothing this gate measured (poison p2 passed) and
    # a green run would have implied coverage it did not have. That premise is now false
    # (aurora's first authored scene binds section 0) and the tripwire is REPLACED, not
    # relaxed: the block below WITNESSES the select directly instead of asserting the
    # condition under which it was unwitnessable. Parcel `parcel/boot-override-witness`,
    # 2026-08-26; the DEFERRED_WORK riders it closes are §"Boot-position override (§4.12b)"
    # item 1 and the precedence parcel's left-open item (b).
    #
    # The reference is a DIRECT READBACK of the installed config, not a rendered comparison,
    # and the author's own note says why a warp cannot serve: the warp sets
    # Parallax_Snap_Pending and therefore SNAPS, so it cannot distinguish "the init picked
    # the right config" from "the first Parallax_CheckBoundary corrected it". Reading
    # `Parallax_Current_Config` at the init's exit — before the update loop has ticked once —
    # removes that ambiguity at the source instead of arguing about pixels downstream of it.
    ra = RomAct(rom_img, d, act["grid_w"], act["grid_h"])
    dest_gxy = (dest_clamped[0] >> k["SHIFT"], dest_clamped[1] >> k["SHIFT"])
    auth_gxy = (act["start_sx"], act["start_sy"])
    dest_cfg, dest_rung = ra.resolve_parallax(*dest_gxy)
    auth_cfg, auth_rung = ra.resolve_parallax(*auth_gxy)
    if not dest_cfg:
        raise SetupError("the destination section resolves to a NULL parallax config — "
                         "the act binds no default, so there is nothing to witness")
    if dest_cfg == auth_cfg:
        raise SetupError(
            f"the authored start section {auth_gxy} and the destination section {dest_gxy} "
            f"both resolve to {sym_name(dest_cfg, inv)}, so a select that read the authored "
            "section instead of the destination would be INDISTINGUISHABLE from a correct "
            "one and the witness below cannot fail. Pick a destination whose section "
            "resolves differently (Sec.sec_parallax_config > EffectsPreset.ep_parallax > "
            "Act.act_parallax_config), or say in DEFERRED_WORK that this act can no longer "
            "witness the select.")
    dest_bands, auth_bands = ra.band_count(dest_cfg), ra.band_count(auth_cfg)
    dest_mode3, auth_mode3 = ra.mode3(dest_cfg), ra.mode3(auth_cfg)
    # The SECOND observable is not always discriminating — two different configs can drive
    # the same band count and the same reg $0B. Say so rather than let a reader assume it
    # is carrying weight it is not.
    second_discriminates = (dest_bands != auth_bands) or (dest_mode3 != auth_mode3)
    # Informational, kept from the tripwire it replaced: how much of the grid binds its own
    # config today. No longer a verdict.
    sec_bound = sum(1 for i in range(act["grid_w"] * act["grid_h"])
                    if ra.u32(ra.grid + i * SEC_SIZE + SEC_PARALLAX_CONFIG))

    ctl = await run_control(args.rom, sym, args.lst, k, plane_base)
    ovr = await run_override(args.rom, sym, args.lst, k, plane_base, *dest)
    wrp = await run_warp_reference(args.rom, sym, args.lst, k, plane_base, *dest)
    # The clamp run: one axis past the act edge, one axis negative — both directions of
    # the clamp in a single boot.
    clamp_req = (act["level_w"] + 4096, 0xFFF0)
    clamp_exp = clamp_expect(*clamp_req, act)
    clm = await run_override(args.rom, sym, args.lst, k, plane_base, *clamp_req)
    # POISON: the maximum-garbage request. $7FFF/$7FFF is the largest positive word, far
    # past any act edge, and $8000-set values are covered by the clamp run's negative axis.
    psn = await run_override(args.rom, sym, args.lst, k, plane_base, 0x7FFF, 0x7FFF)
    psn_exp = clamp_expect(0x7FFF, 0x7FFF, act)
    flg = await run_flag_clear(args.rom, sym, args.lst, k, plane_base, *dest)
    pre = await run_pre_resume(args.rom, sym, args.lst, k, plane_base, *dest)

    fails: list[str] = []

    # 1. CONTROL — an unwritten mailbox boots exactly where the act says.
    _fail(fails, (ctl["first"]["state"]["Player_X"], ctl["first"]["state"]["Player_Y"])
          == authored,
          f"control: player at ({ctl['first']['state']['Player_X']},"
          f"{ctl['first']['state']['Player_Y']}), authored start is {authored}")
    _fail(fails, ctl["boot_flag"] == 0,
          f"control: Boot_At_Flag reads {ctl['boot_flag']} on a boot nothing wrote")

    # 2. THE OVERRIDE, AT THE INIT'S OWN EXIT — before a single Update tick has run.
    #    Player, camera and the tile-cache window all already at the destination is the
    #    difference between "the init aimed itself" and "something corrected it after".
    xs = ovr["at_exit"]
    _fail(fails, (xs["Player_X"], xs["Player_Y"]) == dest_clamped,
          f"override: at the init's exit the player is ({xs['Player_X']},{xs['Player_Y']}), "
          f"wanted {dest_clamped}")
    _fail(fails, (xs["Camera_X"], xs["Camera_Y"]) == dest_cam,
          f"override: at the init's exit the camera is ({xs['Camera_X']},{xs['Camera_Y']}), "
          f"wanted {dest_cam}")
    bad_exit = check_cache({"state": xs}, k)
    _fail(fails, not bad_exit,
          f"override: the init did not seed the tile-cache window at the destination: {bad_exit}")

    # 2b. AND STILL THERE ON THE FIRST PAINTED FRAME.
    fs = ovr["first"]["state"]
    _fail(fails, (fs["Player_X"], fs["Player_Y"]) == dest_clamped,
          f"override: first-frame player ({fs['Player_X']},{fs['Player_Y']}) "
          f"wanted {dest_clamped}")
    _fail(fails, (fs["Camera_X"], fs["Camera_Y"]) == dest_cam,
          f"override: first-frame camera ({fs['Camera_X']},{fs['Camera_Y']}) "
          f"wanted {dest_cam}")
    bad = check_cache(ovr["first"], k)
    _fail(fails, not bad, f"override: tile-cache window not seeded at the destination: {bad}")
    _fail(fails, ovr["published"] == dest_clamped,
          f"override: published {ovr['published']}, wanted {dest_clamped}")
    _fail(fails, ovr["flags"]["Boot_At_Flag"] == 0,
          "override: Boot_At_Flag not cleared — the ack never landed")
    _fail(fails, ovr["flags"]["Warp_Req_Flag"] == 0,
          "override: Warp_Req_Flag is set — a warp was involved, which is the whole "
          "thing this replaces")
    _fail(fails, ovr["ticks"][1] > ovr["ticks"][0],
          f"override: Logic_Tick stuck at {ovr['ticks']} — the 68000 is parked "
          "(PageCache_Audit raised?)")
    _fail(fails, ovr["first"]["colours"] > 1,
          f"override: first frame shows {ovr['first']['colours']} colour(s) — a flat "
          "screen is not level content")

    # 2c. THE PARALLAX SELECT — the override's SECOND consumer, witnessed.
    #     Sampled at the init's EXIT, where the value is still the init's own answer: the
    #     first Parallax_CheckBoundary of the update loop re-selects from the camera (which
    #     under an override is already the destination) and would launder a wrong choice
    #     into a right one over a staged transition. Expectations come from the ROM's own
    #     section grid through Effects_ResolveParallax's three rungs — never a pin.
    op, cp = ovr["parallax"], ctl["parallax"]
    _fail(fails, cp["config"] == auth_cfg,
          f"control: the init seeded Parallax_Current_Config = {sym_name(cp['config'], inv)}, "
          f"wanted the authored start section {auth_gxy}'s {sym_name(auth_cfg, inv)} "
          f"[{auth_rung}]")
    _fail(fails, op["config"] == dest_cfg,
          f"override: the init seeded Parallax_Current_Config = {sym_name(op['config'], inv)}, "
          f"wanted the DESTINATION section {dest_gxy}'s {sym_name(dest_cfg, inv)} "
          f"[{dest_rung}]. The authored start section {auth_gxy} resolves to "
          f"{sym_name(auth_cfg, inv)} [{auth_rung}] — a select that read the authored "
          f"section instead of the destination lands exactly there. Act default is "
          f"{sym_name(ra.act_default, inv)}")
    # The init must have picked it OUTRIGHT. A staged transition at the init's exit means
    # something downstream is correcting the select rather than the init making it, which
    # is the precise confusion that made the warp useless as a reference here.
    for who, p in (("control", cp), ("override", op)):
        _fail(fails, p["target"] == 0 and p["trans_frames"] == 0,
              f"{who}: at the init's exit Parallax_Target_Config = "
              f"{sym_name(p['target'], inv)} with {p['trans_frames']} transition frames "
              "left — the config was STAGED, not seeded, so the first painted frame is "
              "lerping toward it rather than starting on it")
    # 2d. AND THE CONFIG WAS CONSUMED, not merely stored. `Parallax_Current_Config` is a
    #     cell; reg $0B and the band-scroll tail are what the per-frame build actually did
    #     with it. A select that wrote the right pointer into a cell nothing read would
    #     pass 2c and fail here — which is why this is IN ADDITION rather than instead.
    _fail(fails, op["mode3"] == dest_mode3,
          f"override: VDP reg $0B (Mode Set 3) shadow reads {op['mode3']:#04b}, but the "
          f"destination's {sym_name(dest_cfg, inv)} derives {dest_mode3:#04b} "
          f"(the authored section's {sym_name(auth_cfg, inv)} derives {auth_mode3:#04b}) — "
          "Parallax_Update built the frame from a different config than the one selected")
    _fail(fails, cp["mode3"] == auth_mode3,
          f"control: VDP reg $0B (Mode Set 3) shadow reads {cp['mode3']:#04b}, wanted the "
          f"authored section's {auth_mode3:#04b} from {sym_name(auth_cfg, inv)}")
    band_bad = []
    for who, p, n in (("control", cp, auth_bands), ("override", op, dest_bands)):
        for axis in ("a", "b"):
            band_bad += check_bands(p, n, who, axis)
    _fail(fails, not band_bad,
          "the band-scroll tail disagrees with the selected config's pcfg_band_count: "
          + "; ".join(band_bad))

    # 3. NO DRAW-THEN-JUMP. The first displayed frame's visible plane must already equal
    #    the settled one: the init's synchronous fill did the whole job, nothing crawls in.
    d_first_final = word_diff(visible_words(ovr["first"]), visible_words(ovr["final"]))
    _fail(fails, d_first_final == 0,
          f"override: {d_first_final} visible words changed between the first painted "
          f"frame and +{SETTLE}f — the destination was NOT complete on frame 1")

    # 3b. A NEGATIVE CONTROL THAT IS NOT FREE. Every assertion above would still pass if
    #     the destination happened to look like the authored start, so require the two
    #     first frames to differ by most of the LEGITIMATE content delta between the two
    #     places — measured in-run (control settled vs warp settled), never typed.
    content_delta = word_diff(visible_words(ctl["final"]), visible_words(wrp["final"]))
    d_ctl_ovr = word_diff(visible_words(ctl["first"]), visible_words(ovr["first"]))
    _fail(fails, content_delta > 0,
          "negative control: the authored start and the destination render the SAME visible "
          "plane, so nothing below distinguishes them — pick a different destination")
    _fail(fails, d_ctl_ovr >= content_delta // 2,
          f"negative control: the override's first frame differs from the authored boot's by "
          f"only {d_ctl_ovr} words against a legitimate content delta of {content_delta} — "
          "the override did not move the screen")

    # 3c. THE PIXELS, not just the nametable. The plane-A comparison is blind to the
    #     parallax config — palette, band offsets and Plane B all live outside it, and the
    #     init's parallax select is the SECOND consumer of the override. `emulator/scanlines`
    #     is the only pixel-truthful instrument on this bus (source=="raster", asserted in
    #     `snapshot`), so the same 8 scanlines rendered by the two routes must agree.
    px_diff = sum(1 for a, bb in zip(ovr["final"]["rows"], wrp["final"]["rows"]) if a != bb)
    _fail(fails, px_diff == 0,
          f"override vs warp reference: {px_diff} of {len(ovr['final']['rows'])} rendered "
          "scanlines differ — the two routes agree on the nametable but not on what is "
          "actually drawn (parallax config / palette)")

    # 4. THE REFERENCE. The boot override must reproduce the warp's settled plane exactly.
    d_vs_warp = word_diff(visible_words(ovr["final"]), visible_words(wrp["final"]))
    _fail(fails, d_vs_warp == 0,
          f"override vs warp reference: {d_vs_warp} of "
          f"{len(visible_words(ovr['final']))} visible plane-A words differ")
    _fail(fails, (ovr["final"]["state"]["Camera_X"], ovr["final"]["state"]["Camera_Y"])
          == (wrp["final"]["state"]["Camera_X"], wrp["final"]["state"]["Camera_Y"]),
          "override vs warp reference: the two runs settled on different cameras, so the "
          "plane comparison above is not like-for-like")

    # 5. THE CLAMP, both directions, published back.
    _fail(fails, clm["published"] == clamp_exp,
          f"clamp: requested {clamp_req}, published {clm['published']}, wanted {clamp_exp}")
    cs = clm["first"]["state"]
    _fail(fails, (cs["Player_X"], cs["Player_Y"]) == clamp_exp,
          f"clamp: player at ({cs['Player_X']},{cs['Player_Y']}), wanted {clamp_exp}")

    # 6. POISON — garbage past every edge is clamped and the machine survives it.
    _fail(fails, psn["published"] == psn_exp,
          f"poison: $7FFF/$7FFF published {psn['published']}, wanted {psn_exp}")
    ps = psn["first"]["state"]
    _fail(fails, (ps["Player_X"], ps["Player_Y"]) == psn_exp,
          f"poison: player at ({ps['Player_X']},{ps['Player_Y']}), wanted {psn_exp}")
    _fail(fails, psn["ticks"][1] > psn["ticks"][0],
          f"poison: Logic_Tick stuck at {psn['ticks']} — a garbage request faulted the machine")
    _fail(fails, not check_cache(psn["first"], k),
          f"poison: tile-cache window incoherent at the clamped destination: "
          f"{check_cache(psn['first'], k)}")

    # 7. POISON — the FLAG is the gate. Cells written, flag left clear: authored boot,
    #    and the cells come back untouched (no clamp, no publish).
    gs = flg["first"]["state"]
    _fail(fails, (gs["Player_X"], gs["Player_Y"]) == authored,
          f"flag-clear: player at ({gs['Player_X']},{gs['Player_Y']}), wanted the "
          f"authored {authored} — the override ran without its flag")
    _fail(fails, flg["cells"] == dest,
          f"flag-clear: cells read back {flg['cells']}, wanted the untouched {dest} — "
          "the clamp ran without the flag")

    # 8. THE RAM-CLEAR TRUTH. A pre-resume write is zeroed, so the boot is authored.
    _fail(fails, pre["at_init"] == (0, 0, 0),
          f"pre-resume: the mailbox read {pre['at_init']} at the init — boot's Work-RAM "
          "clear was expected to zero it, so the client procedure's premise moved")
    prs = pre["first"]["state"]
    _fail(fails, (prs["Player_X"], prs["Player_Y"]) == authored,
          f"pre-resume: player at ({prs['Player_X']},{prs['Player_Y']}), wanted the "
          f"authored {authored}")

    # ---- the saving, measured engine-side --------------------------------------
    # Absolute emulated frame indices (`frameToken`), so the two routes are compared on
    # one clock — but NOT for the reason this comment used to give. `run_to` has no
    # `frames` key at all and its `frame` is this same absolute clock (see `frame_token`);
    # and these three samples are taken after `run_frames`, where no `run_to` reply is in
    # scope to prefer or reject in the first place.
    boot_frames = ctl["t_playable"]
    ovr_frames = ovr["t_playable"]
    warp_frames = wrp["t_playable"]
    saving = warp_frames - ovr_frames

    report = {
        "destination": dest, "clamped": dest_clamped, "camera": dest_cam,
        "authored_start": authored,
        "act": {kk: act[kk] for kk in ("grid_w", "grid_h", "bound_right", "bound_bottom")},
        "frames": {
            "boot_to_first_painted_frame": boot_frames,
            "override_boot_to_destination": ovr_frames,
            "warp_boot_to_destination": warp_frames,
            "warp_ack_frames": wrp["ack_frames"],
            "saving_frames": saving,
            "saving_seconds_ntsc": round(saving / 60.0, 3),
        },
        "parallax_sections_binding_own_config": sec_bound,
        "parallax_select": {
            "authored_section": list(auth_gxy),
            "authored_config": sym_name(auth_cfg, inv), "authored_rung": auth_rung,
            "authored_seeded": sym_name(cp["config"], inv),
            "destination_section": list(dest_gxy),
            "destination_config": sym_name(dest_cfg, inv), "destination_rung": dest_rung,
            "destination_seeded": sym_name(op["config"], inv),
            "act_default": sym_name(ra.act_default, inv),
            "band_counts": {"authored": auth_bands, "destination": dest_bands},
            "mode_set_3": {"authored": auth_mode3, "destination": dest_mode3,
                           "control_read": cp["mode3"], "override_read": op["mode3"]},
            "second_observable_discriminates": second_discriminates,
            "control_scroll_b": [f"{w:#06x}" for w in cp["scroll_b"]],
            "override_scroll_b": [f"{w:#06x}" for w in op["scroll_b"]],
        },
        "planes": {
            "visible_words": len(visible_words(ovr["final"])),
            "authored_vs_destination_content_delta": content_delta,
            "control_first_vs_override_first": d_ctl_ovr,
            "override_vs_warp_scanline_rows": px_diff,
            "override_first_vs_settled": d_first_final,
            "override_vs_warp_reference": d_vs_warp,
        },
        "published": {"override": ovr["published"], "warp": wrp["published"],
                      "clamp": clm["published"], "poison": psn["published"]},
        "fails": fails,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"boot_override_gate: destination {dest} -> clamped {dest_clamped}, "
              f"camera {dest_cam}")
        print(f"  authored start (derived from the act descriptor): {authored}")
        print(f"  boot -> first painted frame:          {boot_frames} frames")
        print(f"  override: boot -> AT the destination: {ovr_frames} frames")
        print(f"  warp:     boot -> AT the destination: {warp_frames} frames "
              f"({wrp['ack_frames']} of them the ack)")
        print(f"  SAVING: {saving} frames = {saving / 60.0:.2f} s at 60 Hz, and the "
              f"override shows the destination on frame 1 rather than the authored start")
        print(f"  visible plane-A words: {len(visible_words(ovr['final']))}; "
              f"first-vs-settled {d_first_final}; vs warp reference {d_vs_warp}")
        print(f"  negative control: authored-vs-destination content delta {content_delta}, "
              f"control-first vs override-first {d_ctl_ovr}")
        print(f"  rendered scanlines differing from the warp reference: {px_diff} of "
              f"{len(ovr['final']['rows'])}")
        print(f"  parallax select at the init's exit — authored section {auth_gxy} -> "
              f"{sym_name(auth_cfg, inv)} [{auth_rung}], seeded "
              f"{sym_name(cp['config'], inv)}")
        print(f"                                        destination section {dest_gxy} -> "
              f"{sym_name(dest_cfg, inv)} [{dest_rung}], seeded "
              f"{sym_name(op['config'], inv)}")
        print(f"    reg $0B {cp['mode3']:#04b}/{op['mode3']:#04b} (derived "
              f"{auth_mode3:#04b}/{dest_mode3:#04b}); bands {auth_bands}/{dest_bands}; "
              f"{sec_bound} of {act['grid_w'] * act['grid_h']} sections bind their own config")
        if not second_discriminates:
            print("    NOTE: the two configs drive the same band count AND the same reg $0B, "
                  "so the consumption checks are not discriminating here — the config "
                  "POINTER is carrying the witness alone.")
        print(f"  published — override {ovr['published']}, clamp {clm['published']}, "
              f"poison {psn['published']}")
    if fails:
        print("FAIL:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("boot_override_gate: PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--x", type=int, default=DEST_X)
    ap.add_argument("--y", type=int, default=DEST_Y)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        return asyncio.run(main_async(args))
    except SetupError as e:
        print(f"SETUP ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
