#!/usr/bin/env python3
"""warp_mailbox_gate — does the DEBUG warp mailbox land a COHERENT frame?

WHAT IS BEING ASSERTED, and why this shape of assertion.

The warp mailbox exists because a bare camera poke TEARS: everything downstream of
the camera latches per-frame deltas off it, so a teleport-sized jump mis-latches the
prefetch direction (`Cache_Prev_Cam_X` / `Cache_Prev_Cam_Row`) and leaves the tile
cache WINDOW describing the old locality, where every plane write outside it is
silently dropped (`Draw_TileColumn`'s bounds gate). The nametable therefore keeps
showing pre-jump content until the 1-column/2-row-per-frame crawl arrives.

Aurora measured that failure independently, from the client side (aurora master
64aee42, `scratchpad/warp-tearing-harness.mjs`, on `s4.bin` from camera (96,429)):

    jump px | plane-A nametable words differing from the walked reference
        64  | 0
       128  | 0
       256  | 0
       512  | 73
      1024  | 94
      2048  | 699 of 2048   (34.1%)

  METRIC NOTE (Aurora's own correction, 2026-08-19, after adopting this gate's
  visible-window restriction): the table above is WHOLE-PLANE at a ~90-frame settle,
  not visible-window — the view reconciles well before the ring does, so at 90f the
  visible-window equivalent is already 0. The like-for-like client-side figures at
  THIS gate's +30f sample are: bare poke 19 window words (50 whole-plane), mailbox
  0 window words (10 whole-plane, inside the 26-word correct-walk floor). Direction
  identical on both metrics; this gate's own engine-side 698-at-+30f is the
  authoritative visible-window negative figure.

  ... with `Cache_Prev_Cam_X` still reading 96 while `Camera_X` read 2144 — the stale
  baseline observed directly. Two further findings of theirs govern this gate:

  * the tearing SELF-HEALS (699 -> 437 at +120 frames -> 0 at +150). So the negative
    control asserts BOUNDED wrongness at a fixed EARLY sample, never permanence: a
    "still torn at +600" assertion passes today and starts failing for the wrong
    reason the moment recovery gets faster.
  * the metric is the plane-A NAMETABLE, not pixels. Animated tiles change tile
    PIXELS, not nametable entries, so they cannot pollute it, and sprites are
    excluded by construction. This gate adopts their metric so the two instruments —
    theirs client-side, this one engine-side — pin the same failure mode.

THE REFERENCE IS DERIVED, NOT DECLARED. There is no authored "correct nametable" to
compare against. The reference is the SAME DESTINATION REACHED BY WALKING: the camera
is stepped there in sub-threshold hops (<= 256 px, which Aurora measured as tear-free)
with settle frames between, which is exactly the streaming path the engine is built
for. Two independent walks with DIFFERENT step sizes (256 px and 128 px) must land on
byte-identical plane-A content; that is this gate's self-control, and it is stronger
than running one walk twice, because it also proves the destination state is a
property of the DESTINATION rather than of the path taken to it. If those two ever
disagree, nothing below is a verdict about the warp — exit 2.

THE FOUR RUNS (each a fresh oracle-aether process, each capturing at the SAME +30
frames after its jump, so warp and poke are judged on an identical settle budget):

    ref256   walk to the destination in 256 px diagonal steps      -> the reference
    ref128   walk to the same destination in 128 px steps          -> self-control
    warp     one mailbox warp                                      -> must equal ref
    poke     one bare `Camera_X`/`Camera_Y` poke, same destination -> must NOT equal

A NEGATIVE CONTROL THAT PASSES IS NOT A CONTROL. `poke` must differ from `ref256` by
at least a floor DERIVED IN-RUN (a fraction of `content_delta`, the number of words
that legitimately differ between the origin and the destination) so that a one-word
flake cannot masquerade as a detected tear. `content_delta` is measured, never typed.

THE SECOND GATE FAMILY is the streaming state itself, and its expectations are
DERIVED from the post-warp camera plus constants read out of `engine/system/
constants.emp` — never copied from a neighbouring pin. `Tile_Cache_Init` is the
authority for every one of them (tile_cache.emp:541-586):

    Cache_Left_Col    == max(0, camX/8 - TILE_CACHE_MARGIN_H)
    Cache_Head_Col    == Cache_Left_Col + TILE_CACHE_COLS - 1
    Cache_Top_Row     == max(0, camY/8 - TILE_CACHE_MARGIN_V)  rounded down to even
    Cache_Bottom_Row  == Cache_Top_Row + TILE_CACHE_ROWS - 1
    Cache_Prev_Cam_X  == camX            (the baseline Aurora caught stale)
    Cache_Prev_Cam_Row== camY/8

They hold for the walked reference too — a settled stream converges on the same
window — which is what makes them a property of "being at the destination" rather
than of "having been re-initialised". The bare poke must FAIL them.

THE INSTRUMENT. oracle-aether, because `emulator/scanlines` is the only pixel
readback with a `source` field; every capture hard-fails on `source != "raster"`
(a post-hoc `stateRender` reply is rendered from end-of-frame VDP state and cannot
witness anything about WHEN a write landed). The scanline capture answers the "is
there real level content here, or a flat backdrop?" half of coherence, against a
distinct-colour floor taken from the REFERENCE run's own capture.

Plane A is 64x64 cells = 8192 bytes at VRAM_PLANE_A; `read_vram` caps at
`limits.maxReadLen` = 4096, so it is read in TWO 4096-byte chunks. That chunking is
stated here so a reviewer can tell a region change from a chunking change.

Exit codes (the house contract): 0 pass, 1 an assertion failed, 2 setup /
could-not-measure — never a verdict.
"""

import argparse
import asyncio
import json
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

from aether import BusClient            # noqa: E402
from aether_instance import assert_rust_server  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

SERVER = str(suite_path("oracle-next", "target", "release", "oracle-aether"))
SOCK = f"/tmp/aeon_warpbox_{os.getpid()}.sock"     # short + per-process: AF_UNIX caps at 108

SETTLE_FRAMES = 180          # boot -> gameplay (the tree-wide constant; no buttons are pressed:
                             # the sonic4 DEBUG shape boots straight into the OJZ scroll test)
POST_FREEZE_FRAMES = 3
STEP_SETTLE = 60             # frames allowed per walked step; a 256 px hop is 32 tile columns
                             # and the fill is budgeted, so this is deliberately generous
JUMP_SETTLE = 30             # THE sample point, identical for warp and poke (see the module note)
HEAL_SETTLE = 220            # advisory second sample: shows the bare poke healing, per Aurora
POKE_FLOOR_FRACTION = 0.05   # negative control must reach 5% of the legitimate content delta

# The jump. Diagonal and multi-section on BOTH axes (a direction-contradicting jump is
# what the mis-latch needs): OJZ act 1 is a 3x3 grid of 2048 px sections, boot spawns
# the player at (256,256) in section (0,0), and this lands in section (1,1).
JUMP_PX = 2048               # >= 512, the threshold Aurora measured; 2048 for a fat signal
SCANLINE_START, SCANLINE_COUNT = 100, 8


class SetupError(Exception):
    """Something made the measurement impossible. Not a verdict — exit 2, never exit 1."""


def emp_const(rel: str, name: str) -> int:
    """A `const NAME = $HEX` / `= 123` out of an .emp source, so the gate cannot drift from it."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        raise SetupError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


class Server:
    """One oracle-aether process. A fresh one per run — every run starts from reset."""

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
            raise SetupError(f"oracle-aether never created {self.sock}")
        self.client = BusClient(self.sock, client_id="warpbox",
                                client_name="warp_mailbox_gate")
        info = await self.client.connect()
        # The identity assertion, shared with every other gate in this lane
        # (`tools/aether_instance.py`): this gate has ALWAYS spawned oracle-aether,
        # but nothing checked that the thing which answered was it. A gate silently
        # talking to the legacy server reports a verdict measured on the wrong
        # emulator and nothing goes red.
        assert_rust_server(info)
        for m in ("emulator/scanlines", "emulator/read_vram", "emulator/write_memory"):
            if not self.client.supports(m):
                raise SetupError(f"the server does not advertise `{m}`")
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


async def _c(b, method, params=None, timeout=180.0):
    """Every RPC gets a deadline. A resume that never breaks otherwise blocks the NEXT
    call with no timeout of its own — the half-hour hang raster_frame_epoch_probe books."""
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


# ---- readback ---------------------------------------------------------------

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


async def read_word(b, sym, name: str) -> int:
    r = await _c(b, "emulator/read_memory", {"addr": hex(sym[name]), "len": 2})
    return int(r["bytes"].removeprefix("0x").removeprefix("0X"), 16)


async def read_long(b, sym, name: str) -> int:
    r = await _c(b, "emulator/read_memory", {"addr": hex(sym[name]), "len": 4})
    return int(r["bytes"].removeprefix("0x").removeprefix("0X"), 16)


STATE_WORDS = ["Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row", "Cache_Bottom_Row",
               "Cache_Prev_Cam_X", "Cache_Prev_Cam_Row", "Cache_Origin_Col",
               "Cache_Origin_Row", "Section_Left_Col_Written", "Section_Right_Col_Written",
               "Section_Top_Row_Written", "Section_Bottom_Row_Written"]


async def snapshot(b, sym, plane_base: int) -> dict:
    st = {n: await read_word(b, sym, n) for n in STATE_WORDS}
    st["Camera_X"] = (await read_long(b, sym, "Camera_X")) >> 16
    st["Camera_Y"] = (await read_long(b, sym, "Camera_Y")) >> 16
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
            "colours": len(colours), "mode": r.get("mode")}


# ---- derived expectations ---------------------------------------------------

def derived_expectations(cam_x: int, cam_y: int, k: dict) -> dict:
    """Tile_Cache_Init (tile_cache.emp:541-586) IS the authority; this restates its
    arithmetic against the constants read out of engine/system/constants.emp."""
    left = max(0, (cam_x >> 3) - k["MH"])
    top = max(0, (cam_y >> 3) - k["MV"]) & 0xFFFE
    return {
        "Cache_Left_Col": left,
        "Cache_Head_Col": left + k["COLS"] - 1,
        "Cache_Top_Row": top,
        "Cache_Bottom_Row": top + k["ROWS"] - 1,
        "Cache_Prev_Cam_X": cam_x,
        "Cache_Prev_Cam_Row": cam_y >> 3,
    }


def check_coherent(snap: dict, k: dict) -> list[str]:
    exp = derived_expectations(snap["state"]["Camera_X"], snap["state"]["Camera_Y"], k)
    bad = []
    for name, want in exp.items():
        got = snap["state"][name]
        if got != want:
            bad.append(f"{name}={got} wanted {want}")
    return bad


# ---- the runs ---------------------------------------------------------------

async def boot(b, sym, lst: str) -> None:
    await _c(b, "emulator/load_symbols", {"path": lst})
    await _c(b, "emulator/reset", {})
    await _c(b, "emulator/run_frames", {"frames": SETTLE_FRAMES})
    # Freeze BEFORE anything is poked: Camera_Update would otherwise drag the camera back
    # to the player every frame and no poked position would survive. Parallax_CheckBoundary
    # runs OUTSIDE the freeze gate, so section crossings still install their own presets.
    await _c(b, "emulator/write_memory",
             {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await _c(b, "emulator/run_frames", {"frames": POST_FREEZE_FRAMES})


async def poke_camera(b, sym, x: int, y: int) -> None:
    await _c(b, "emulator/write_memory", {"addr": hex(sym["Camera_X"]), "value": x << 16,
                                          "width": 4})
    await _c(b, "emulator/write_memory", {"addr": hex(sym["Camera_Y"]), "value": y << 16,
                                          "width": 4})


async def run_walk(rom, sym, lst, k, step: int, plane_base: int) -> dict:
    """Reach the destination by sub-threshold camera hops — the reference path."""
    async with Server(rom) as s:
        b = s.client
        await boot(b, sym, lst)
        x0 = (await read_long(b, sym, "Camera_X")) >> 16
        y0 = (await read_long(b, sym, "Camera_Y")) >> 16
        origin = await snapshot(b, sym, plane_base)
        n = JUMP_PX // step
        if n * step != JUMP_PX:
            raise SetupError(f"step {step} does not divide the {JUMP_PX} px jump")
        for i in range(1, n + 1):
            await poke_camera(b, sym, x0 + i * step, y0 + i * step)
            await _c(b, "emulator/run_frames", {"frames": STEP_SETTLE})
        await _c(b, "emulator/run_frames", {"frames": JUMP_SETTLE})
        return {"origin": origin, "final": await snapshot(b, sym, plane_base),
                "cam0": (x0, y0)}


async def run_warp(rom, sym, lst, k, plane_base: int) -> dict:
    """One mailbox warp: X, Y, then the FLAG last; poll the flag for the ack."""
    async with Server(rom) as s:
        b = s.client
        await boot(b, sym, lst)
        x0 = (await read_long(b, sym, "Camera_X")) >> 16
        y0 = (await read_long(b, sym, "Camera_Y")) >> 16
        # The mailbox carries a PLAYER position; the consumer centres the camera on it.
        # Target the player position that puts the camera exactly where the walk left it.
        tx = x0 + JUMP_PX + k["HALF_W"]
        ty = y0 + JUMP_PX + k["HALF_H"]
        await _c(b, "emulator/write_memory", {"addr": hex(sym["Warp_Req_X"]), "value": tx,
                                              "width": 2})
        await _c(b, "emulator/write_memory", {"addr": hex(sym["Warp_Req_Y"]), "value": ty,
                                              "width": 2})
        await _c(b, "emulator/write_memory", {"addr": hex(sym["Warp_Req_Flag"]), "value": 1,
                                              "width": 1})
        acked = None
        for i in range(1, 121):
            await _c(b, "emulator/run_frames", {"frames": 1})
            r = await _c(b, "emulator/read_memory",
                         {"addr": hex(sym["Warp_Req_Flag"]), "len": 1})
            if int(r["bytes"].removeprefix("0x").removeprefix("0X"), 16) == 0:
                acked = i
                break
        if acked is None:
            raise SetupError("Warp_Req_Flag never cleared in 120 frames — the consumer "
                             "did not run (wrong ROM shape? not in the level state?)")
        # The engine publishes the CLAMPED destination back into the mailbox.
        back_x = await read_word(b, sym, "Warp_Req_X")
        back_y = await read_word(b, sym, "Warp_Req_Y")
        await _c(b, "emulator/run_frames", {"frames": JUMP_SETTLE})
        snap = await snapshot(b, sym, plane_base)
        # STILL ALIVE? Tile_Cache_Init's DEBUG tail runs PageCache_Audit, so a wrong
        # refcount reset raises and parks the 68000 in the error handler. A Logic_Tick
        # that still advances is the proof the audit passed — the warp checks its own
        # residency bookkeeping and this reads the verdict.
        t0 = await read_long(b, sym, "Logic_Tick")
        await _c(b, "emulator/run_frames", {"frames": 2})
        t1 = await read_long(b, sym, "Logic_Tick")
        return {"final": snap, "ack_frames": acked, "ticks": (t0, t1),
                "clamped": (back_x, back_y), "requested": (tx, ty)}


async def run_poke(rom, sym, lst, k, plane_base: int) -> dict:
    """THE NEGATIVE CONTROL: the same destination by bare camera poke."""
    async with Server(rom) as s:
        b = s.client
        await boot(b, sym, lst)
        x0 = (await read_long(b, sym, "Camera_X")) >> 16
        y0 = (await read_long(b, sym, "Camera_Y")) >> 16
        await poke_camera(b, sym, x0 + JUMP_PX, y0 + JUMP_PX)
        await _c(b, "emulator/run_frames", {"frames": JUMP_SETTLE})
        early = await snapshot(b, sym, plane_base)
        await _c(b, "emulator/run_frames", {"frames": HEAL_SETTLE})
        return {"final": early, "healed": await snapshot(b, sym, plane_base)}


def visible_words(snap: dict) -> list[int]:
    """The plane cells the camera is actually SHOWING, in a fixed order.

    THE WHOLE 64x64 PLANE IS NOT A VALID METRIC and the first run of this gate proved
    it: two correct walks to the same destination disagreed by 26 words. The nametable
    is a 512x512 px ring while the view is 320x224, so roughly three quarters of it
    holds whatever the camera last wrote there — genuinely path-dependent, and nothing
    the engine promises to converge. Comparing it would make the reference a property
    of the route after all, which is exactly what the self-control exists to refuse.

    What the engine DOES promise is the visible window, and that is what "torn or
    stale rows on screen" means. 41x29 cells covers 320x224 px including both partial
    edge cells. Cell (col,row) lives at (world_row & 63)*64 + (world_col & 63) —
    continuous scroll wraps the world through the ring (section.emp:277-279)."""
    cam_x, cam_y = snap["state"]["Camera_X"], snap["state"]["Camera_Y"]
    c0, r0 = cam_x >> 3, cam_y >> 3
    out = []
    for r in range(r0, r0 + 29):
        for c in range(c0, c0 + 41):
            out.append(snap["plane"][(r & 63) * 64 + (c & 63)])
    return out


def word_diff(a: list[int], b: list[int]) -> int:
    if len(a) != len(b):
        raise SetupError(f"plane captures differ in length ({len(a)} vs {len(b)})")
    return sum(1 for x, y in zip(a, b) if x != y)


# ---- main -------------------------------------------------------------------

async def main_async(args) -> int:
    k = {
        "COLS": emp_const("engine/system/constants.emp", "TILE_CACHE_COLS"),
        "ROWS": emp_const("engine/system/constants.emp", "TILE_CACHE_ROWS"),
        "MH": emp_const("engine/system/constants.emp", "TILE_CACHE_MARGIN_H"),
        "MV": emp_const("engine/system/constants.emp", "TILE_CACHE_MARGIN_V"),
        "HALF_W": emp_const("engine/system/constants.emp", "CAM_SCREEN_HALF_W"),
        "HALF_H": emp_const("engine/system/constants.emp", "CAM_SCREEN_HALF_H"),
    }
    plane_base = emp_const("engine/system/constants.emp", "VRAM_PLANE_A")
    sym = parse_lst(args.lst)
    for need in ("Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Debug_Scene_Freeze",
                 "Camera_X", "Camera_Y", "Logic_Tick", *STATE_WORDS):
        if need not in sym:
            raise SetupError(f"symbol {need} is not in {args.lst} — wrong ROM shape? "
                             "(this gate needs the sonic4 DEBUG listing)")

    ref = await run_walk(args.rom, sym, args.lst, k, 256, plane_base)
    ctl = await run_walk(args.rom, sym, args.lst, k, 128, plane_base)
    wrp = await run_warp(args.rom, sym, args.lst, k, plane_base)
    pke = await run_poke(args.rom, sym, args.lst, k, plane_base)

    vis_ref = visible_words(ref["final"])
    content_delta = word_diff(visible_words(ref["origin"]), vis_ref)
    d_ctl = word_diff(visible_words(ctl["final"]), vis_ref)
    d_wrp = word_diff(visible_words(wrp["final"]), vis_ref)
    d_pke = word_diff(visible_words(pke["final"]), vis_ref)
    d_heal = word_diff(visible_words(pke["healed"]), vis_ref)
    floor = max(1, int(content_delta * POKE_FLOOR_FRACTION))

    results: list[tuple[str, bool, str]] = []

    # --- SELF-CONTROL FIRST. Everything below is a verdict about the warp only if the
    #     reference is real; two walks with different step sizes must converge. ---
    if content_delta == 0:
        raise SetupError(f"the destination's plane-A content is IDENTICAL to the origin's "
                         f"({content_delta} words differ) — this jump measures nothing; "
                         "pick a destination whose art differs")
    if d_ctl != 0:
        raise SetupError(f"the 256 px and 128 px walks disagree by {d_ctl} words — the "
                         "reference is not a property of the destination, so nothing "
                         "below is a verdict about the warp")

    results.append((f"self-control: 256px walk == 128px walk (content_delta={content_delta} "
                    f"words legitimately differ origin->destination)", True, "0 words"))

    # --- THE POSITIVE ASSERTION ---
    results.append(("mailbox warp lands the reference nametable", d_wrp == 0,
                    f"{d_wrp} words differ from the walked reference"))

    # --- THE NEGATIVE CONTROL: the same assertion must FAIL for a bare poke ---
    ok_neg = d_pke >= floor
    results.append((f"negative control: bare camera poke TEARS (>= {floor} words = "
                    f"{POKE_FLOOR_FRACTION:.0%} of content_delta)", ok_neg,
                    f"{d_pke} words differ at +{JUMP_SETTLE}f "
                    f"(advisory: {d_heal} still differ at +{JUMP_SETTLE + HEAL_SETTLE}f)"))

    # --- DERIVED STREAMING-STATE COHERENCE ---
    bad_w = check_coherent(wrp["final"], k)
    results.append(("warp: streaming state matches Tile_Cache_Init's derived window",
                    not bad_w, "; ".join(bad_w) or "all 6 derived cells agree"))
    bad_r = check_coherent(ref["final"], k)
    results.append(("reference: the settled walk satisfies the SAME derived window",
                    not bad_r, "; ".join(bad_r) or "all 6 derived cells agree"))
    bad_p = check_coherent(pke["final"], k)
    results.append(("negative control: bare poke FAILS the derived window", bool(bad_p),
                    "; ".join(bad_p) or "no cell disagreed — the control is vacuous"))

    # --- REAL CONTENT AT THE DESTINATION (scanline readback, source==raster asserted
    #     inside snapshot()); the floor comes from the reference's own capture. ---
    ref_col = ref["final"]["colours"]
    results.append((f"warp: scanline capture shows real level content "
                    f"(>= reference's {ref_col} distinct colours)",
                    wrp["final"]["colours"] >= ref_col,
                    f"{wrp['final']['colours']} distinct colours over rows "
                    f"{SCANLINE_START}..{SCANLINE_START + SCANLINE_COUNT - 1}, "
                    f"mode {wrp['final']['mode']}"))

    # --- the reference is the TRUE destination state, not an artifact of walking:
    #     the torn poke, left alone, converges on it. This is measured, not assumed. ---
    results.append(("the torn poke CONVERGES on the reference (so the reference is the "
                    "destination's own state, not the walk's)", d_heal == 0,
                    f"{d_heal} words differ at +{JUMP_SETTLE + HEAL_SETTLE}f"))

    # --- the DEBUG residency audit inside the warp did not raise ---
    t0, t1 = wrp["ticks"]
    results.append(("warp: PageCache_Audit held (the game loop still ticks afterwards)",
                    t1 > t0, f"Logic_Tick {t0} -> {t1} over 2 frames"))

    # --- the clamp is observable: the engine writes the clamped target back ---
    results.append(("warp: engine published a clamped destination back to the client",
                    wrp["clamped"] == wrp["requested"],
                    f"requested {wrp['requested']}, read back {wrp['clamped']} "
                    f"(ack after {wrp['ack_frames']} frame(s))"))

    width = max(len(n) for n, _, _ in results)
    fails = 0
    for name, ok, detail in results:
        if not ok:
            fails += 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"warp_mailbox_gate: {len(results) - fails}/{len(results)} assertions held")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "content_delta": content_delta, "d_ctl": d_ctl, "d_warp": d_wrp,
            "d_poke_early": d_pke, "d_poke_healed": d_heal, "floor": floor,
            "warp_state": wrp["final"]["state"], "ref_state": ref["final"]["state"],
            "poke_state": pke["final"]["state"],
        }, indent=2))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    # ABSOLUTE paths: a relative ROM resolves against the emulator's cwd, silently loads
    # nothing, and every read still answers ok against blank RAM.
    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    for p in (args.rom, args.lst, SERVER):
        if not Path(p).exists():
            print(f"warp_mailbox_gate: missing {p}", file=sys.stderr)
            return 2
    try:
        return asyncio.run(main_async(args))
    except SetupError as e:
        print(f"warp_mailbox_gate: SETUP — {e}", file=sys.stderr)
        return 2
    except asyncio.TimeoutError:
        print("warp_mailbox_gate: SETUP — an RPC exceeded its deadline (emulator wedge)",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
