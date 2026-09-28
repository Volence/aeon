#!/usr/bin/env python3
"""clip_bg_scroll_witness — the BUILT clip ROM's own Hscroll_Buffer, against Sonic 2's.

S2CLIP-ORIGINAL-BGS parcel B-2. `tools/clip_bg_scroll.py` derives each zone's scroll from
s2.asm and `tools/test_clip_bg_scroll.py` holds the derivation and the engine MODEL to Sonic 2's
own routine. Neither boots the ROM. This does: a headless oracle-aether process runs the DEBUG
clip ROM, the camera is placed through the DEBUG warp mailbox (`--place warp`, the default since
2026-09-27; `--place poke` is the old raw Camera_X/Y write, see _place) and held there by
Debug_Scene_Freeze (it pins Camera_Update), the frame loop runs the real crossing (Parallax_CheckBoundary -> the zone's preset ->
its parallax config) and the real walker, and the 224-line buffer the VDP would read is
compared, word for word, against:

  1. the ENGINE MODEL (`clip_bg_scroll.engine_bg_words`) at the camera, vscroll and deform
     phase read back from RAM — EXACT equality on every line, both planes' words. This is what
     proves the lowered records the ROM carries are the ones the model describes.
  2. for Emerald Hill, SONIC 2 ITSELF (`run_swscrl_ehz`, s2.asm executed) — reported per band
     as the worst difference on lines where S2 writes a new value and on lines where S2 holds
     one (the ramp's pairs and triples). Reported, not graded: the grade is (1) plus the
     derivation tests, which bound these same differences.

It also checks the installed pointer: Parallax_Current_Config must be the zone's own
OJZ_Clip_Parallax_<key> (from the listing), and the config lerp must have finished.

RUNNER: manual (it boots an emulator, so it cannot live in build.sh — the effects-gates
ruling's reason). Run after `S2CLIP=s2_ehz_cpz DEBUG=1 ./build.sh`:
    python3 tools/clip_bg_scroll_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst
Exit 0 all probes exact, 1 a mismatch, 2 could not measure (symbols missing, a probe that never
settled, a config pointer that is not a clip parallax record).

LEGS past the settled probes, each wired in tools/keepalive_manifest.toml (the nightly
instrument keepalive): `--warp-entry` (the ENTRY leg, every frame after a warp into each tall
layout, and the FLIGHT leg) and `--boot-entry` (the BOOT leg, BOOT-ENTRY-PICTURE 2026-09-28: the
same per-frame grade on the first frames of a LEVEL START, through the DEBUG Boot_At override
into each tall layout and at the act's authored start; `--require-authored-tall` makes an
authored start outside every tall zone COULD NOT MEASURE). See _entry_leg and _boot_leg.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path, harness_path  # noqa: E402
add_client_path()
sys.path.insert(0, str(harness_path()))
from aether import BusClient            # noqa: E402
from aether_instance import aether_emulator   # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402
import clip_bg_scroll as CBS             # noqa: E402
import clip_manifest as CM               # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SYMS = ["Hscroll_Buffer", "Camera_X", "Camera_Y", "Debug_Scene_Freeze",
        "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag",
        "Parallax_Current_Config", "Parallax_Current_Vscroll_BG", "Parallax_Transition_Frames",
        "Parallax_Deform_Phase_BG"]
HSCROLL_BYTES = CBS.SCREEN_LINES * 4
SETTLE_MAX = 900
# Parallax_Drift_Acc: one 16.16 long per band, MAX_PARALLAX_BANDS (engine/structs.emp: 16) of
# them, [pixels:i16][fraction:u16] (engine/level/parallax.emp's drift banner).
DRIFT_BANDS = 16
COHERENT_TRIES = 8
STABLE_FRAMES = 30
#: the player centre sits CAM_SCREEN_HALF_W/H from the camera (center_camera_on's rule), so a
#: warp to camera + these lands the camera on the request. Read out of
#: engine/system/constants.emp in main() (never typed); None until then.
CAM_HALF_W = CAM_HALF_H = None
#: the player's SST x_pos / y_pos offsets, out of the listing's equates in main()
SST_POS = None
WARP_ACK_FRAMES = 120


def probes(act, specs=None, chains=None):
    """Camera positions per zone: its own x span (camera left edge, clamped so the CENTRE is
    inside the zone's clip) at a few heights inside its paste. Derived from the manifest.

    Plus, when `specs` is given and the zone's BG scrolls vertically, the camera Y where its
    plane V-scroll is mid-way between its clamps (engine_vscroll's own [0, max]): without it a
    windowed zone can be probed only where the clamp holds the plane (Wing Fortress's 1:1 sky
    moves over camera Y 640..928 of its solo act and the three manifest heights are 0, 523 and
    1312, all clamped)."""
    out = []
    half_w, half_h = 160, 112
    for c in act.clips:
        x0, y0, w, h = c.dst
        xs = sorted({x0 + 64, x0 + w // 3 + 37, x0 + (2 * w) // 3 + 5, x0 + w - 2 * half_w - 3})
        ys = {y0, y0 + h // 3 + 11, y0 + h - 2 * half_h}
        sp = (specs or {}).get(c.zone_key)
        if sp is not None and sp["v_factor"] != CBS.LOCKED:
            top = CBS.engine_vscroll(sp, 0x7FFF)
            mid = [y for y in range(y0, y0 + h - 2 * half_h + 1)
                   if CBS.engine_vscroll(sp, y) >= top // 2]
            if mid and 0 < CBS.engine_vscroll(sp, mid[0]) < top:
                ys.add(mid[0])
        # a TALL zone's chain: the camera tops either side of every layout switch (the last
        # top of layout i and the first of i + 1), and the middle of each layout's own
        # stretch, where they fall inside this clip (WINDOWED-BG-VERTICAL-CLAMP)
        ch = (chains or {}).get(c.zone_key)
        if ch:
            ys.update(y for cut in ch["cuts"] for y in (cut - half_h - 1, cut - half_h)
                      if y0 <= y <= y0 + h - 2 * half_h)
            for sp_ in ch["specs"]:
                a, b_ = sp_["tall"]["valid"]
                hit = [y for y in range(y0, y0 + h - 2 * half_h + 1)
                       if CBS.engine_vscroll(sp_, y) + sp_["window_top"] >= (a + b_) // 2]
                if hit:
                    ys.add(hit[0])
        ys = sorted(ys)
        for x in xs:
            for y in ys:
                out.append((c.zone_key, c.zone, c.dst[1] - c.src[1], max(0, x), max(0, y)))
    return out


#: engine/system/constants.emp VRAM_PLANE_B_BYTES; a nametable row is 64 cells = 128 bytes.
VRAM_PLANE_B = 0xE000
PLANE_ROW_BYTES = 128
PLANE_BYTES = 64 * PLANE_ROW_BYTES


def _hex(r):
    h = r["bytes"]
    return h[2:] if h[:2].lower() == "0x" else h


async def _place(b, sym, camx, camy, how):
    """Put the camera at (camx, camy). `warp` (the default since WOVEN-HPZ-BG-MISALIGNED,
    2026-09-27): the DEBUG warp mailbox with the player's centre at camera + (160, 112), the
    engine's own teleport (Debug_Warp_Consume re-seeds the tile cache, the section trackers and
    both planes synchronously). `poke`: the raw Camera_X/Y write this witness used before; it
    teleports the camera WITHOUT that reseed, so the tile cache walks column by column from the
    previous probe across the act and Section_UpdateColumns fills Plane_Buffer with the walk
    (MEASURED on s2_woven crc 2a0f1df3: Plane_Buffer_Ptr $05D8 of $0600 at every
    Draw_BG_TileRow, so the BG streamer is refused for 50+ frames). No player path does that,
    which is why it is kept only as an option."""
    if how == "poke":
        await b.call("emulator/write_memory", {"addr": hex(sym["Camera_X"]), "value": camx << 16,
                                               "width": 4})
        await b.call("emulator/write_memory", {"addr": hex(sym["Camera_Y"]), "value": camy << 16,
                                               "width": 4})
        return True
    for n, v, w in (("Warp_Req_X", camx + CAM_HALF_W, 2), ("Warp_Req_Y", camy + CAM_HALF_H, 2),
                    ("Warp_Req_Flag", 1, 1)):
        await b.call("emulator/write_memory", {"addr": hex(sym[n]), "value": v, "width": w})
    for _ in range(WARP_ACK_FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        r = await b.call("emulator/read_memory", {"addr": hex(sym["Warp_Req_Flag"]), "len": 1})
        if int(_hex(r), 16) == 0:
            break
    else:
        return False
    # The warp clamps the PLAYER into the act (Player_Bound_*), which can leave the camera short
    # of a probe on the act's bottom row (MEASURED: Oil Ocean's probes at camera Y 5920 land at
    # 5808). The rest is a raw write of at most that residue, inside the window the warp just
    # seeded, so the cache and the planes stream it the way they stream a camera step.
    for n, v in (("Camera_X", camx), ("Camera_Y", camy)):
        r = await b.call("emulator/read_memory", {"addr": hex(sym[n]), "len": 2})
        if int(_hex(r), 16) != v:
            await b.call("emulator/write_memory", {"addr": hex(sym[n]), "value": v << 16,
                                                   "width": 4})
    return True


async def _probe(b, sym, camx, camy, rates=None, plane=False, how="warp"):
    if not await _place(b, sym, camx, camy, how):
        return None
    # SETTLED means all three, for STABLE_FRAMES frames running: no config lerp in flight, the
    # BG vertical scroll no longer moving (Step 5's rate clamp walks it a few px per logic
    # tick, and a camera jump makes lag frames, so "unchanged for 3 frames" was measured to be
    # too short: it sampled vscroll mid-walk), and the buffer's first FG word equal to -camX
    # (a buffer built for the camera just written, not the previous probe's).
    last, stable = None, 0
    want_fg = (-camx) & 0xFFFF
    for n in range(SETTLE_MAX):
        await b.call("emulator/run_frames", {"frames": 1})
        tf = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Transition_Frames"]), "len": 1})
        vs = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Current_Vscroll_BG"]), "len": 2})
        fg = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Hscroll_Buffer"]), "len": 2})
        cur = (tf["bytes"], vs["bytes"])
        ok = int(_hex(tf), 16) == 0 and int(_hex(fg), 16) == want_fg
        stable = stable + 1 if cur == last and ok else 0
        last = cur
        if stable >= STABLE_FRAMES:
            break
    else:
        return None
    reads = [("Hscroll_Buffer", HSCROLL_BYTES), ("Camera_X", 4), ("Camera_Y", 4),
             ("Parallax_Current_Config", 4), ("Parallax_Current_Vscroll_BG", 2),
             ("Parallax_Deform_Phase_BG", 2)]
    if "Parallax_Drift_Acc" in sym:
        reads.append(("Parallax_Drift_Acc", 4 * DRIFT_BANDS))
    if plane and "BG_Plane_Top" in sym:
        reads.append(("BG_Plane_Top", 2))
    if plane:
        # the NAMETABLE leg of a tall zone: the whole Plane B, read from VRAM
        # (4096 bytes a call, as tools/bg_window_gate.py reads it; a short read is COULD NOT
        # MEASURE, never a pass)
        plane_b = b""
        for off in range(0, PLANE_BYTES, 4096):
            r = await b.call("emulator/read_vram", {"addr": hex(VRAM_PLANE_B + off), "len": 4096})
            h = _hex(r)
            if len(h) != 4096 * 2:
                return None
            plane_b += bytes.fromhex(h)
    # A DRIFTING scene changes every frame, so a snapshot taken while the frame loop is still
    # inside Parallax_Update's band loop (a lag frame) is a mix of two frames. MEASURED on
    # s2_wfz_solo at camera (4101, 0): accumulators [240, 120, 60, 240, 119, 59, 239, ...]
    # for three rates repeated, i.e. the loop stopped part-way. COHERENT means every band
    # with the same drift rate holds the same accumulator (they start together at 0 and
    # advance on the same frames); an incoherent snapshot is re-taken one frame later, up to
    # COHERENT_TRIES times, and the number of re-takes is reported. A probe that never gets a
    # coherent snapshot is COULD NOT MEASURE, never a pass.
    for tries in range(COHERENT_TRIES):
        rd = {}
        for name, ln in reads:
            r = await b.call("emulator/read_memory", {"addr": hex(sym[name]), "len": ln})
            rd[name] = bytes.fromhex(_hex(r))
        if _coherent(rd.get("Parallax_Drift_Acc", b""), rates):
            if plane:
                rd["PlaneB"] = plane_b
            return rd, n + 1, tries
        await b.call("emulator/run_frames", {"frames": 1})
    return None


def _coherent(acc, rates):
    """Every band sharing a non-zero drift rate holds the same 16.16 accumulator."""
    seen = {}
    for k, rate in enumerate(rates or []):
        if rate and 4 * k + 4 <= len(acc):
            if seen.setdefault(rate, acc[4 * k:4 * k + 4]) != acc[4 * k:4 * k + 4]:
                return False
    return True


#: frames graded after each warp of the ENTRY leg (and each boot of the BOOT leg): the longest
#: ratchet a tall map can need is its whole scroll range at BG_VSCROLL_MAX_STEP (16) a frame,
#: 928 / 16 = 58 on Hidden Palace
ENTRY_FRAMES = 90


def _chain_ctx(rom, act, sym, key, ch, blob_lab):
    """What every per-frame grade of tall zone `key` reads, derived once: its clip, Sonic 2's
    KIND per BG row (`kind_of`), the ROM's own nametable blob at its listing address, the TILE
    rows (8 lines each) whose 64 cells are all the transparent word (free, derive_tall's rule),
    and the band that may scroll each Sonic 2 kind (`factor_of`, per layout index since drift is
    per index). Shared by the ENTRY, BOOT and FLIGHT legs so they grade one expectation."""
    clip = next(c for c in act.clips if c.zone_key == key)
    _raw, kind_of = CBS._tall_source(clip.donor, clip.zone, 0, ch["v_hi"])
    base = sym[blob_lab[key]] & 0xFFFFFF
    blob = rom[base:base + ch["span"] // 8 * PLANE_ROW_BYTES]
    wild = {t for t in range(ch["span"] // 8)
            if not any(blob[t * PLANE_ROW_BYTES:(t + 1) * PLANE_ROW_BYTES])}
    factor_of = {}
    for sp in ch["specs"]:
        for bd in sp["bands"]:
            k = ("drift", bd["drift"]) if bd.get("drift") else \
                ("flat", bd.get("s2_ratio", bd["ratio"]))
            factor_of.setdefault(k, bd["factor"])
    return {"clip": clip, "kind_of": kind_of, "blob": blob, "wild": wild, "factor_of": factor_of}


def _layout_targets(plan, key, ch, spec_at):
    """Per band layout i of tall zone `key`: the first probe of the plan inside it, or None."""
    return [(i, next((p for p in plan if p[0] == key and spec_at(key, p[4])[0] == i), None))
            for i in range(len(ch["specs"]))]


async def _grade_frames(b, sym, key, ch, cx, spec_at, frames):
    """Grade `frames` consecutive frames of tall zone `key`, the first one AS THE MACHINE STANDS
    (the frame a warp or a boot hands the screen), then one run_frames each: every visible line
    against Sonic 2's kind for the map row it shows, the plane rows against the ROM's blob, the
    BG vscroll against its target (engine_vscroll). Returns (bad_frames, slide, slide_bad,
    first, at0): frames AT their target with a wrong line or row, frames not at their target,
    how many of those were torn as well, the first at-target bad frame's particulars, and the
    first frame's (vscroll, target)."""
    r0, blob, wild = ch["r0"], cx["blob"], cx["wild"]
    kind_of, factor_of = cx["kind_of"], cx["factor_of"]
    bad_frames, slide, slide_bad, first, at0 = 0, 0, 0, None, None
    for f in range(frames):
        rd = {}
        for name, ln in (("Hscroll_Buffer", HSCROLL_BYTES), ("Camera_X", 4),
                         ("Camera_Y", 4), ("Parallax_Current_Vscroll_BG", 2),
                         ("Parallax_Drift_Acc", 4 * DRIFT_BANDS)):
            if name in sym:
                r = await b.call("emulator/read_memory", {"addr": hex(sym[name]), "len": ln})
                rd[name] = bytes.fromhex(_hex(r))
        pb = b""
        for off in range(0, PLANE_BYTES, 4096):
            r = await b.call("emulator/read_vram", {"addr": hex(VRAM_PLANE_B + off),
                                                    "len": 4096})
            pb += bytes.fromhex(_hex(r))
        camy = int.from_bytes(rd["Camera_Y"][:2], "big")
        vs = CBS._sx(int.from_bytes(rd["Parallax_Current_Vscroll_BG"], "big"), 16)
        li, spec = spec_at(key, camy)
        acc = rd.get("Parallax_Drift_Acc", b"")
        dpx = [CBS._sx(int.from_bytes(acc[j * 4:j * 4 + 2], "big"), 16)
               for j in range(len(acc) // 4)]
        buf = rd["Hscroll_Buffer"]
        # THE CAMERA X THE BUFFER WAS BUILT FOR, not Camera_X now: while the camera moves
        # the buffer can be one Camera_Update behind the RAM word (MEASURED in free
        # flight: every line off by exactly one frame's 16 px). Plane A is hard-locked
        # to -camX (Parallax_Update's factor_a), so line 0's FG word names it.
        camx = -CBS._sx(int.from_bytes(buf[0:2], "big"), 16)
        wrong = []
        for line in range(CBS.SCREEN_LINES):
            m = vs + line
            if not 0 <= m < ch["span"] or (m >> 3) in wild:
                continue
            kd = kind_of(r0 + m)
            if kd is None or kd not in factor_of:
                continue
            want = -CBS.engine_factor_scroll(factor_of[kd], camx)
            if kd[0] == "drift":
                j = next(j for j, bd in enumerate(spec["bands"])
                         if bd.get("drift") == kd[1])
                want += dpx[j] if j < len(dpx) else 0
            got = CBS._sx(int.from_bytes(buf[line * 4 + 2:line * 4 + 4], "big"), 16)
            if CBS._sx(want, 16) != got:
                wrong.append(line)
        rows = [m for m in range(vs >> 3, min((vs + CBS.SCREEN_LINES - 1) >> 3,
                                              ch["span"] // 8 - 1) + 1)
                if pb[(m & 63) * PLANE_ROW_BYTES:((m & 63) + 1) * PLANE_ROW_BYTES]
                != blob[m * PLANE_ROW_BYTES:(m + 1) * PLANE_ROW_BYTES]]
        target = CBS.engine_vscroll(spec, camy)
        sliding = vs != target
        slide += sliding
        if at0 is None:
            at0 = (vs, target)
        if wrong or rows:
            if sliding:
                slide_bad += 1
            else:
                bad_frames += 1
                if first is None:
                    first = (f, vs, target, li, len(wrong), wrong[:1] + wrong[-1:], rows[:4])
        await b.call("emulator/run_frames", {"frames": 1})
    return bad_frames, slide, slide_bad, first, at0


def _entry_line(leg, what, graded, who, closed_by):
    """One printable row of the ENTRY or BOOT leg: the same verdict, in the same words."""
    bad_frames, slide, slide_bad, first = graded[:4]
    return (
        (f"FAIL {leg} {what}: {bad_frames} of {ENTRY_FRAMES} frames, the scroll AT its "
         f"target, show a line Sonic 2 scrolls differently or a wrong plane row; first "
         f"at frame {first[0]}: vscroll {first[1]}, layout {first[3]}, {first[4]} "
         f"line(s) {first[5]}, rows {first[6]}" if bad_frames else
         f"{'FAIL' if slide else 'OK  '} {leg} {what}: every frame with the scroll at its "
         f"target exact")
        + f"; the scroll slid to its target over {slide} frame(s)"
        + (f" ({slide_bad} of them torn): BG-RATE-PRIME-EXEMPTION is back — {who} "
           f"must store the BG scroll at its target and prime the plane from it, so "
           f"no frame after it may slide ({closed_by})" if slide else ""))


async def _entry_leg(b, sym, act, chains, plan, spec_at, ctxs, rates_of):
    """THE ENTRY LEG (`--warp-entry`, WOVEN-HPZ-BG-MISALIGNED 2026-09-27): what the screen shows
    on EVERY frame after a teleport INTO a tall zone, not only once it has settled.

    For each tall zone and each of its band layouts: warp to a probe of ANOTHER zone, let it
    settle, warp to the probe inside the layout's own stretch, and for ENTRY_FRAMES frames grade
    every visible line against SONIC 2: line L shows map row m = vscroll + L, i.e. Sonic 2's BG
    row window_top + m, whose Sonic 2 KIND (ratio, or drift rate) names the one band of the
    chain that may scroll it; the HScroll word must be that band's (engine_factor_scroll at the
    live camera X, plus its drift accumulator). Rows whose 64 cells are all transparent are
    free (derive_tall's rule). The nametable leg runs on every frame too (_grade_frames).

    GRADED, TWO WAYS. (1) Every frame whose vscroll is AT its target (engine_vscroll) must be
    exact: what this leg was written to catch is a frame with the scroll where Sonic 2 has it
    and the picture still torn (WOVEN-HPZ-BG-MISALIGNED: another zone's band-drift accumulators
    added to this zone's bands, on every frame, forever). (2) Since WARP-VSCROLL-PRIME
    (2026-09-28) NO frame may be sliding at all: the warp stores the BG scroll at its target
    and primes the plane from it, so a frame whose vscroll is not at its target is the
    BG-RATE-PRIME-EXEMPTION ratchet come back (on the chained tall map most of those frames
    show a band on rows Sonic 2 scrolls differently, so they are torn as well as late). Until
    that parcel the slide was REPORTED, NOT GRADED; RED on the unfixed ROM (crc 615ff7ff):
    layouts 1 / 2 / 3 slid 15 / 31 / 44 frames, 14 / 30 / 38 of them torn.

    Returns (fails, lines): the number of frames with a wrong line or row, and printable rows."""
    out, fails = [], 0
    for key, ch in chains.items():
        clip = ctxs[key]["clip"]
        # another zone's probe; a one-zone act starts from its own first probe (another layout)
        origin = next((p for p in plan if p[0] != key), plan[0])
        targets = []
        for i, t in _layout_targets(plan, key, ch, spec_at):
            if t is None:
                out.append(f"COULD NOT MEASURE entry {clip.zone} layout {i}: no probe inside it")
                fails += 1
                continue
            targets.append((i, t))
        for i, (_k, zone, _dy, x, y) in targets:
            if await _probe(b, sym, origin[3], origin[4], rates_of[origin[0]]) is None:
                out.append(f"COULD NOT MEASURE entry {zone} layout {i}: the origin never settled")
                fails += 1
                continue
            if not await _place(b, sym, x, y, "warp"):
                out.append(f"COULD NOT MEASURE entry {zone} layout {i}: the warp was not acked")
                fails += 1
                continue
            g = await _grade_frames(b, sym, key, ch, ctxs[key], spec_at, ENTRY_FRAMES)
            fails += g[0] > 0 or g[1] > 0
            out.append(_entry_line("entry", f"{zone} layout {i} ({origin[1]} "
                                   f"({origin[3]},{origin[4]}) -> ({x},{y}))" if g[0] else
                                   f"{zone} layout {i} ({origin[1]} -> ({x},{y}))",
                                   g, "the warp", "WARP-VSCROLL-PRIME"))
    return fails, out


#: run_to ceiling for the boot to reach GameState_OJZScroll_Init and then its Update (the DEBUG
#: shape's boot, bg_vscroll_rate_witness's figure)
BOOT_MAX_FRAMES = 600


async def _boot_to_update(b, sym, at):
    """Reset and run the boot ladder, with the DEBUG boot-position override aimed at `at` (a
    player centre; None = the act's AUTHORED start), to the first GameState_OJZScroll_Update:
    the frame the init hands the screen. The mailbox is written at the Init breakpoint, as
    tools/boot_override_gate.py and bg_vscroll_rate_witness leg B write it (boot clears all of
    Work RAM, so an earlier write is zeroed). Debug_Scene_Freeze is set in the same window so
    the camera is pinned from frame 1 exactly as the ENTRY leg pins it. Returns None, or the
    reason this boot could not be measured."""
    await b.call("emulator/reset", {})
    got = await b.call("emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Init"]),
                                           "maxFrames": BOOT_MAX_FRAMES})
    if not got.get("reached"):
        return f"run_to GameState_OJZScroll_Init never reached it: {got}"
    writes = [("Debug_Scene_Freeze", 1, 1)]
    if at is not None:
        writes = [("Boot_At_X", at[0], 2), ("Boot_At_Y", at[1], 2), ("Boot_At_Flag", 1, 1)] \
            + writes
    for n, v, w in writes:
        await b.call("emulator/write_memory", {"addr": hex(sym[n]), "value": v, "width": w})
    got = await b.call("emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Update"]),
                                           "maxFrames": BOOT_MAX_FRAMES})
    if not got.get("reached"):
        return f"run_to GameState_OJZScroll_Update never reached it: {got}"
    r = await b.call("emulator/read_memory", {"addr": hex(sym["Boot_At_Flag"]), "len": 1})
    if int(_hex(r), 16) != 0:
        return "the init never consumed the boot override (Boot_At_Flag still set)"
    return None


async def _read_cam(b, sym):
    out = []
    for n in ("Camera_X", "Camera_Y"):
        r = await b.call("emulator/read_memory", {"addr": hex(sym[n]), "len": 2})
        out.append(int(_hex(r), 16))
    return tuple(out)


async def _boot_leg(b, sym, act, chains, plan, spec_at, ctxs, need_authored):
    """THE BOOT LEG (`--boot-entry`, BOOT-ENTRY-PICTURE 2026-09-28): the ENTRY leg's question
    asked of a LEVEL START instead of a warp. BOOT-TALL-VSCROLL-RATCHET found the boot ladder
    priming Plane B from a scroll capped at the act-default ceiling (288) and sliding to its
    target at the rate clamp (s2_hpz_solo's AUTHORED start: 288 -> 446 over 10 frames);
    bg_vscroll_rate_witness leg B (A8) grades that SCROLL VALUE on DEBUG OJZ. This grades the
    PICTURE on Hidden Palace's band chain: every visible line and plane row of the first
    ENTRY_FRAMES frames, from the one the init hands the screen, by _grade_frames, the grade
    the ENTRY leg uses (at-target frames exact, and no frame may slide).

    Boots: (1) for each tall zone and each of its band layouts, a boot through the DEBUG
    boot-position override (Aurora's "Build & Run at the cursor") at the same probe the ENTRY
    leg warps to, i.e. the player centre camera + (CAM_SCREEN_HALF_W, CAM_SCREEN_HALF_H);
    (2) the act's AUTHORED start, no override. LOUD ON UNMEASURABLE: an override boot whose
    camera is not the probe's, or whose camera centre is not in that zone's clip and layout,
    is COULD NOT MEASURE; so is an authored start outside every tall zone when `need_authored`
    (the row that names s2_hpz_solo, whose authored start IS the subject); without it that is
    a SKIP row that counts nothing (the woven act starts in a one-plane map).

    Returns (fails, lines) as the ENTRY leg does."""
    out, fails = [], 0
    for key, ch in chains.items():
        clip = ctxs[key]["clip"]
        boots = []
        for i, t in _layout_targets(plan, key, ch, spec_at):
            if t is None:
                out.append(f"COULD NOT MEASURE boot {clip.zone} layout {i}: no probe inside it")
                fails += 1
                continue
            # the ENTRY leg's probe (the layout's first), and its DEEPEST probe at the same x:
            # a target above VSCROLL_BG_MAX is what the capped prime could not reach, and the
            # deepest camera of a layout is where its target is highest
            deep = max((p for p in plan if p[0] == key and p[3] == t[3]
                        and spec_at(key, p[4])[0] == i), key=lambda p: p[4])
            boots += [(i, t)] + ([(i, deep)] if deep[4] != t[4] else [])
        for i, (_k, zone, _dy, x, y) in boots:
            why = await _boot_to_update(b, sym, (x + CAM_HALF_W, y + CAM_HALF_H))
            if why is None:
                cam = await _read_cam(b, sym)
                if cam != (x, y):
                    why = (f"the override did not land the camera on the probe: camera {cam}, "
                           f"wanted ({x},{y})")
                elif spec_at(key, y)[0] != i:
                    why = f"the camera centre is in layout {spec_at(key, y)[0]}, not {i}"
            if why:
                out.append(f"COULD NOT MEASURE boot {zone} layout {i} at ({x},{y}): {why}")
                fails += 1
                continue
            g = await _grade_frames(b, sym, key, ch, ctxs[key], spec_at, ENTRY_FRAMES)
            fails += g[0] > 0 or g[1] > 0
            out.append(_entry_line("boot", f"{zone} layout {i} (Boot_At -> ({x},{y}), first frame "
                                   f"vscroll {g[4][0]} target {g[4][1]})", g,
                                   "the boot ladder", "BOOT-TALL-VSCROLL-RATCHET"))
    why = await _boot_to_update(b, sym, None)
    if why:
        out.append(f"COULD NOT MEASURE boot authored start: {why}")
        return fails + 1, out
    cx_, cy_ = await _read_cam(b, sym)
    home = next((c for c in act.clips
                 if c.dst[0] <= cx_ + CAM_HALF_W < c.dst[0] + c.dst[2]
                 and c.dst[1] <= cy_ + CAM_HALF_H < c.dst[1] + c.dst[3]), None)
    if home is None or home.zone_key not in chains:
        where = home.zone if home else "no clip"
        if need_authored:
            out.append(f"COULD NOT MEASURE boot authored start: camera ({cx_},{cy_}) centre is in "
                       f"{where}, not a tall zone, and --require-authored-tall names it the "
                       f"subject")
            return fails + 1, out
        out.append(f"SKIP boot authored start: camera ({cx_},{cy_}) centre is in {where}, not a "
                   f"tall zone; nothing on this boot can slide (graded: nothing)")
        return fails, out
    key = home.zone_key
    g = await _grade_frames(b, sym, key, chains[key], ctxs[key], spec_at, ENTRY_FRAMES)
    fails += g[0] > 0 or g[1] > 0
    out.append(_entry_line("boot", f"{home.zone} layout {spec_at(key, cy_)[0]} (AUTHORED start, "
                           f"camera ({cx_},{cy_}), first frame vscroll {g[4][0]} target "
                           f"{g[4][1]})", g, "the boot ladder",
                           "BOOT-TALL-VSCROLL-RATCHET"))
    return fails, out



#: free flight moves the player PLAYER_DEBUG_FLY_SPEED (16) px a frame; a waypoint is reached
#: within this many px, and a flight that has not reached one in FLY_MAX_FRAMES is COULD NOT RUN
FLY_TOL = 16
FLY_MAX_FRAMES = 1500


def _fly_route(act, drifting, key):
    """The connectors from a clip of a DRIFTING zone to a clip of zone `key`, breadth first:
    a shaft is crossed DOWN only (free flight could climb one; a player drops through it), a
    corridor either way. Returns [(connector, clip left, clip entered)] or None."""
    edges = []
    for co in act.connectors:
        ax, a, b_ = CM.connector_ends(act, co)
        if a is None or b_ is None:
            continue
        edges.append((co, a, b_))
        if ax == "x":
            edges.append((co, b_, a))
    start = [c for c in act.clips if c.zone_key in drifting]
    prev = {id(c): None for c in start}
    todo = list(start)
    while todo:
        c = todo.pop(0)
        if c.zone_key == key:
            path = []
            while prev[id(c)] is not None:
                co, frm = prev[id(c)]
                path.append((co, frm, c))
                c = frm
            return path[::-1]
        for co, a, b_ in edges:
            if a is c and id(b_) not in prev:
                prev[id(b_)] = (co, a)
                todo.append(b_)
    return None


def _waypoints(co, frm, to):
    """Player-centre points that carry free flight through one connector: its mouth on the
    `frm` side, then well past its far mouth inside `to` (clamped into that clip)."""
    x, y, w, h = co.dst
    if getattr(co, "axis", "x") == "y":
        cx = x + w // 2
        return [(cx, y - 2 * FLY_TOL), (cx, min(y + h + 256, to.dst[1] + to.dst[3] - 128))]
    cy = y + h // 2
    if frm.dst[0] < to.dst[0]:
        return [(x - 2 * FLY_TOL, cy), (min(x + w + 256, to.dst[0] + to.dst[2] - 200), cy)]
    return [(x + w + 2 * FLY_TOL, cy), (max(x - 256, to.dst[0] + 200), cy)]


async def _fly_leg(b, sym, act, chains, specs, plan, spec_at, ctxs):
    """THE FLIGHT LEG (`--warp-entry` runs it after the ENTRY leg): the same question asked of
    a WALKED crossing, with no teleport between the drifting zone and the tall one. Warp into a
    zone whose bands DRIFT, let it run STABLE_FRAMES * 10 frames so the accumulators move, then
    fly (DEBUG free flight, held directions, 16 px a frame) through the connectors the route
    search finds into each tall zone and down to its lowest probe, through every layout of its
    chain, grading every frame whose camera centre is inside the tall clip exactly as the ENTRY
    leg grades one: every visible line against Sonic 2's kind for its row (drift rows aside,
    their phase is the zone's own), the plane rows on frames with no sweep in flight. This is
    the path WOVEN-HPZ-BG-MISALIGNED is reached by in play: a crossing carried the drift in."""
    out, fails = [], 0
    drifting = {k for k, sp in specs.items() if any(bd.get("drift") for bd in sp["bands"])}
    for key, ch in chains.items():
        clip = next(c for c in act.clips if c.zone_key == key)
        if key in drifting:
            out.append(f"OK   fly {clip.zone}: the zone drifts itself; nothing to inherit")
            continue
        if not drifting:
            out.append(f"OK   fly {clip.zone}: no zone of this act drifts; nothing to inherit")
            continue
        route = _fly_route(act, drifting, key)
        if not route:
            out.append(f"COULD NOT MEASURE fly {clip.zone}: no route from a drifting zone "
                       f"({sorted(drifting)}) through the act's connectors")
            fails += 1
            continue
        start = route[0][1]
        sx = route[0][0].dst[0] + route[0][0].dst[2] // 2
        sy = start.dst[1] + start.dst[3] // 2
        if not await _place(b, sym, sx - CAM_HALF_W, sy - CAM_HALF_H, "warp"):
            out.append(f"COULD NOT MEASURE fly {clip.zone}: the start warp was not acked")
            fails += 1
            continue
        await b.call("emulator/write_memory", {"addr": hex(sym["Debug_Scene_Freeze"]),
                                               "value": 0, "width": 1})
        await b.call("emulator/run_frames", {"frames": STABLE_FRAMES * 10})
        pts = [p for co, frm, to in route for p in _waypoints(co, frm, to)]
        low = max(p[4] for p in plan if p[0] == key)
        pts.append((clip.dst[0] + 64 + CAM_HALF_W, low + CAM_HALF_H))
        res = await _fly_grade(b, sym, pts, key, ch, ctxs[key], spec_at)
        await b.call("emulator/write_memory", {"addr": hex(sym["Debug_Scene_Freeze"]),
                                               "value": 1, "width": 1})
        names = " -> ".join(co.id for co, _f, _t in route)
        if isinstance(res, str):
            out.append(f"COULD NOT MEASURE fly {clip.zone} via {names}: {res}")
            fails += 1
            continue
        graded, bad, first, layouts = res
        if not graded:
            out.append(f"COULD NOT MEASURE fly {clip.zone} via {names}: no frame was graded")
            fails += 1
        elif bad:
            fails += 1
            out.append(f"FAIL fly {clip.zone} via {names}: {bad} of {graded} frames inside it "
                       f"show a line Sonic 2 scrolls differently or a wrong plane row "
                       f"(layouts seen {sorted(layouts)}); first: camera {first[0]}, vscroll "
                       f"{first[1]}, layout {first[2]}, {first[3]} line(s) {first[4]}, rows "
                       f"{first[5]}")
        else:
            out.append(f"OK   fly {clip.zone} via {names}: {graded} frames inside it exact "
                       f"(layouts seen {sorted(layouts)})")
    return fails, out


async def _fly_grade(b, sym, pts, key, ch, cx, spec_at):
    """Fly through `pts` (player centres) in DEBUG free flight, grading every frame whose
    camera centre is inside `cx`'s clip. Returns (graded, bad, first, layouts) or a reason."""
    r0, clip = ch["r0"], cx["clip"]
    kind_of, blob, wild, factor_of = cx["kind_of"], cx["blob"], cx["wild"], cx["factor_of"]
    pos = (sym["Player_1"] + SST_POS[0], sym["Player_1"] + SST_POS[1])
    graded, bad, first, layouts = 0, 0, None, set()
    x0, y0, w0, h0 = clip.dst
    held = set()

    async def hold(want):
        for d in held - want:
            await b.call("emulator/hold", {"buttons": [d], "down": False})
        for d in want - held:
            await b.call("emulator/hold", {"buttons": [d], "down": True})
        held.clear()
        held.update(want)

    try:
        for tx, ty in pts:
            for _n in range(FLY_MAX_FRAMES):
                r = await b.call("emulator/read_memory", {"addr": hex(pos[0]), "len": 2})
                px = int(_hex(r), 16)
                r = await b.call("emulator/read_memory", {"addr": hex(pos[1]), "len": 2})
                py = int(_hex(r), 16)
                if abs(px - tx) <= FLY_TOL and abs(py - ty) <= FLY_TOL:
                    break
                want = set()
                if abs(px - tx) > FLY_TOL:
                    want.add("right" if tx > px else "left")
                else:
                    want.add("down" if ty > py else "up")
                await hold(want)
                await b.call("emulator/run_frames", {"frames": 1})
                rd = {}
                for name, ln in (("Hscroll_Buffer", HSCROLL_BYTES), ("Camera_X", 4),
                                 ("Camera_Y", 4), ("Parallax_Current_Vscroll_BG", 2),
                                 ("BG_Wipe_Cursor", 1), ("BG_Wipe_Row", 1)):
                    rr = await b.call("emulator/read_memory", {"addr": hex(sym[name]), "len": ln})
                    rd[name] = bytes.fromhex(_hex(rr))
                camx = int.from_bytes(rd["Camera_X"][:2], "big")
                camy = int.from_bytes(rd["Camera_Y"][:2], "big")
                if not (x0 <= camx + CAM_HALF_W < x0 + w0 and y0 <= camy + CAM_HALF_H < y0 + h0):
                    continue
                vs = CBS._sx(int.from_bytes(rd["Parallax_Current_Vscroll_BG"], "big"), 16)
                li, _spec = spec_at(key, camy)
                layouts.add(li)
                buf = rd["Hscroll_Buffer"]
                # THE CAMERA X THE BUFFER WAS BUILT FOR, not Camera_X now: while the camera moves
                # the buffer can be one Camera_Update behind the RAM word (MEASURED in free
                # flight: every line off by exactly one frame's 16 px). Plane A is hard-locked
                # to -camX (Parallax_Update's factor_a), so line 0's FG word names it.
                camx = -CBS._sx(int.from_bytes(buf[0:2], "big"), 16)
                wrong = []
                for line in range(CBS.SCREEN_LINES):
                    m = vs + line
                    if not 0 <= m < ch["span"] or (m >> 3) in wild:
                        continue
                    kd = kind_of(r0 + m)
                    if kd is None or kd not in factor_of or kd[0] == "drift":
                        continue
                    want_w = CBS._sx(-CBS.engine_factor_scroll(factor_of[kd], camx), 16)
                    got = CBS._sx(int.from_bytes(buf[line * 4 + 2:line * 4 + 4], "big"), 16)
                    if want_w != got:
                        wrong.append(line)
                rows = []
                if rd["BG_Wipe_Cursor"][0] == 0 and rd["BG_Wipe_Row"][0] == 0:
                    pb = b""
                    for off in range(0, PLANE_BYTES, 4096):
                        rr = await b.call("emulator/read_vram", {"addr": hex(VRAM_PLANE_B + off),
                                                                 "len": 4096})
                        pb += bytes.fromhex(_hex(rr))
                    rows = [m for m in range(vs >> 3, min((vs + CBS.SCREEN_LINES - 1) >> 3,
                                                          ch["span"] // 8 - 1) + 1)
                            if pb[(m & 63) * PLANE_ROW_BYTES:((m & 63) + 1) * PLANE_ROW_BYTES]
                            != blob[m * PLANE_ROW_BYTES:(m + 1) * PLANE_ROW_BYTES]]
                graded += 1
                if wrong or rows:
                    bad += 1
                    if first is None:
                        first = ((camx, camy), vs, li, len(wrong), wrong[:1] + wrong[-1:],
                                 rows[:4])
            else:
                return f"free flight never reached ({tx},{ty}) in {FLY_MAX_FRAMES} frames"
    finally:
        await hold(set())
    return graded, bad, first, layouts

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.s2clip.debug.bin")
    ap.add_argument("--lst", default="s4.s2clip.debug.lst")
    ap.add_argument("--clip", default="s2_ehz_cpz")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--json", default="")
    ap.add_argument("--warp-entry", action="store_true",
                    help="after the probes, the ENTRY leg: every frame after a warp into each "
                         "tall zone's layouts, graded against Sonic 2 (see _entry_leg)")
    ap.add_argument("--place", choices=("warp", "poke"), default="warp",
                    help="how each probe moves the camera (see _place); `poke` is the pre-"
                         "2026-09-27 raw Camera_X/Y write, kept to reproduce what it measured")
    ap.add_argument("--boot-entry", action="store_true",
                    help="after the probes (and --warp-entry), the BOOT leg: the first frames of "
                         "a level start in each tall zone's layouts (DEBUG Boot_At) and at the "
                         "act's authored start, graded as the ENTRY leg grades (see _boot_leg)")
    ap.add_argument("--require-authored-tall", action="store_true",
                    help="with --boot-entry: an authored start outside every tall zone is COULD "
                         "NOT MEASURE, not a SKIP (the act whose authored start is the subject)")
    a = ap.parse_args()
    if a.require_authored_tall and not a.boot_entry:
        ap.error("--require-authored-tall grades the BOOT leg; pass --boot-entry")
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    global CAM_HALF_W, CAM_HALF_H
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(str(REPO / "engine" / "system" / "constants.emp"))
    CAM_HALF_W, CAM_HALF_H = int(src.get("CAM_SCREEN_HALF_W")), int(src.get("CAM_SCREEN_HALF_H"))
    sym = parse_lst(lst)
    global SST_POS
    import loop_step_over_witness as LSW
    _s, equs = LSW.parse_lst(lst)
    SST_POS = (equs["SST_x_pos"], equs["SST_y_pos"])
    act = CM.load(str(REPO / "games" / "sonic4" / "data" / "clips" / a.clip / "clips.json"))
    zones = {c.zone_key: c for c in act.clips}
    specs = {k: CBS.derive(c.donor, c.zone, c.dst[1] - c.src[1]) for k, c in zones.items()}
    # A TALL zone (WINDOWED-BG-VERTICAL-CLAMP) carries a CHAIN of band layouts, the region row
    # under the camera centre naming one; the bake's own tall_chains() re-derives it, and the
    # probe's expectation is the layout its camera centre selects (count of cuts <= centre).
    import clip_rom_bake as CRB
    chains = CRB.tall_chains(act)
    for k, ch in chains.items():
        specs[k] = ch["specs"][0]

    def spec_at(key, camy):
        ch = chains.get(key)
        if not ch:
            return 0, specs[key]
        i = sum(1 for c in ch["cuts"] if c <= camy + CBS.CAM_HALF_H)
        return i, ch["specs"][i]
    # A drifting band (WFZ's clouds) moves with Parallax_Drift_Acc, not the camera: without
    # the accumulator the model cannot be compared, so it is REQUIRED when any spec drifts.
    labels = {CBS.PARALLAX_LABEL.format(key=k): (k, 0) for k in zones}
    for k, ch in chains.items():
        labels.update({CRB.tall_parallax_label(k, i): (k, i) for i in range(len(ch["specs"]))})
    blob_lab = {k: f"OJZ_Clip_BG_Layout_{k}" for k in chains}
    need = SYMS + sorted(labels) + sorted(blob_lab.values()) + (
        ["Boot_At_X", "Boot_At_Y", "Boot_At_Flag", "GameState_OJZScroll_Init",
         "GameState_OJZScroll_Update"] if a.boot_entry else []) + (
        ["Parallax_Drift_Acc"] if any(b.get("drift") for sp in specs.values()
                                      for b in sp["bands"]) else [])
    missing = [s for s in need if s not in sym]
    if missing:
        print(f"COULD NOT RUN: symbols missing from {a.lst}: {', '.join(missing)}")
        return 2
    with open(CBS.s2_asm_path(zones[min(zones)].donor), errors="replace") as fh:
        text = fh.read()
    cfg_of = {sym[lab] & 0xFFFFFF: ki for lab, ki in labels.items()}
    plan = probes(act, specs, chains)
    rates_of = {k: [b.get("drift") or 0 for b in sp["bands"]] for k, sp in specs.items()}
    results = []
    entry = []
    boot = []
    with open(rom, "rb") as fh:
        rom_bytes = fh.read()
    ctxs = {k: _chain_ctx(rom_bytes, act, sym, k, ch, blob_lab) for k, ch in chains.items()}

    async def run(sock):
        b = BusClient(socket_path=sock, client_id="clipscroll", client_name="clip_bg_scroll_witness")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": lst})
        # the Rust core (aether_instance): reset takes no params and boots paused
        await b.call("emulator/reset", {})
        await b.call("emulator/run_frames", {"frames": a.settle})
        await b.call("emulator/write_memory", {"addr": hex(sym["Debug_Scene_Freeze"]),
                                               "value": 1, "width": 1})
        await b.call("emulator/run_frames", {"frames": 2})
        for key, zone, dy, x, y in plan:
            results.append((key, zone, x, y, await _probe(b, sym, x, y, rates_of[key],
                                                          plane=key in chains, how=a.place)))
        if a.warp_entry:
            if not chains:
                entry.extend((1, ["COULD NOT MEASURE entry: this act has no tall zone"]))
            else:
                f1, l1 = await _entry_leg(b, sym, act, chains, plan, spec_at, ctxs, rates_of)
                f2, l2 = await _fly_leg(b, sym, act, chains, specs, plan, spec_at, ctxs)
                entry.extend((f1 + f2, l1 + l2))
        # LAST: every boot resets the machine, so nothing above may run after it
        if a.boot_entry:
            if not chains:
                boot.extend((1, ["COULD NOT MEASURE boot: this act has no tall zone"]))
            else:
                boot.extend(await _boot_leg(b, sym, act, chains, plan, spec_at, ctxs,
                                            a.require_authored_tall))
        await b.close()

    with aether_emulator(rom, symbols=lst) as sock:
        asyncio.run(run(sock))

    bad, unmeasured, report = 0, 0, []
    for key, zone, x, y, got in results:
        if got is None:
            print(f"COULD NOT MEASURE {zone} cam ({x},{y}): never settled in {SETTLE_MAX} frames, "
                  f"or no coherent drift snapshot in {COHERENT_TRIES} re-takes")
            unmeasured += 1
            continue
        rd, frames, retakes = got
        camx = int.from_bytes(rd["Camera_X"][:2], "big")
        camy = int.from_bytes(rd["Camera_Y"][:2], "big")
        cfg = int.from_bytes(rd["Parallax_Current_Config"], "big") & 0xFFFFFF
        vs = CBS._sx(int.from_bytes(rd["Parallax_Current_Vscroll_BG"], "big"), 16)
        ph = int.from_bytes(rd["Parallax_Deform_Phase_BG"], "big")
        buf = rd["Hscroll_Buffer"]
        fg = [CBS._sx(int.from_bytes(buf[i * 4:i * 4 + 2], "big"), 16) for i in range(224)]
        bg = [CBS._sx(int.from_bytes(buf[i * 4 + 2:i * 4 + 4], "big"), 16) for i in range(224)]
        acc = rd.get("Parallax_Drift_Acc", b"")
        dpx = [CBS._sx(int.from_bytes(acc[i * 4:i * 4 + 2], "big"), 16)
               for i in range(len(acc) // 4)]
        line = (f"{zone} cam ({camx},{camy}) settled {frames}f vscroll {vs} phase {ph}"
                + (f" drift px {[d for d in dpx if d]}" if any(dpx) else "")
                + (f" (re-taken {retakes}x: incoherent drift snapshot)" if retakes else ""))
        if (camx, camy) != (x, y):
            print(f"COULD NOT MEASURE {line}: the camera did not stay at ({x},{y})")
            unmeasured += 1
            continue
        idx, spec = spec_at(key, camy)
        want_lab = CRB.tall_parallax_label(key, idx) if key in chains else \
            CBS.PARALLAX_LABEL.format(key=key)
        if cfg_of.get(cfg) != (key, idx):
            print(f"FAIL {line}: Parallax_Current_Config ${cfg:06X} is not "
                  f"{want_lab} (${sym[want_lab] & 0xFFFFFF:06X})")
            bad += 1
            continue
        line += f" layout {idx}" if key in chains else ""
        want_vs = CBS.engine_vscroll(spec, camy)
        model = CBS.engine_bg_words(spec, camx, vscroll=vs, phase_bg=ph, drift_px=dpx)
        miss = [i for i in range(224) if model[i] != bg[i]]
        fg_miss = [i for i in range(224) if fg[i] != CBS._sx(-camx, 16)]
        ok = not miss and not fg_miss and vs == want_vs
        nt_bad = []
        if key in chains:
            # THE NAMETABLE (BG-TALL's leg 2, on a clip): every MAP row the screen shows must
            # sit in plane row (m & 63) byte for byte, the bytes being the blob the ROM names
            # (read out of the ROM at its listing address, not re-lowered here). Where two map
            # rows hold identical bytes (Hidden Palace's chunk rows 7-8) this cannot tell them
            # apart; everywhere else it names the row.
            span = chains[key]["span"]
            base = sym[blob_lab[key]] & 0xFFFFFF
            with open(rom, "rb") as fh:
                fh.seek(base)
                blob = fh.read(span // 8 * PLANE_ROW_BYTES)
            pb = rd["PlaneB"]
            for m in range(vs >> 3, min((vs + 223) >> 3, span // 8 - 1) + 1):
                p = (m & 63) * PLANE_ROW_BYTES
                if pb[p:p + PLANE_ROW_BYTES] != blob[m * PLANE_ROW_BYTES:(m + 1) * PLANE_ROW_BYTES]:
                    nt_bad.append(m)
            if nt_bad:
                # WHAT the wrong rows hold: the map row(s) whose bytes they are, or none
                held = {}
                for m in nt_bad[:6]:
                    p = (m & 63) * PLANE_ROW_BYTES
                    held[m] = [k for k in range(span // 8)
                               if blob[k * PLANE_ROW_BYTES:(k + 1) * PLANE_ROW_BYTES]
                               == pb[p:p + PLANE_ROW_BYTES]][:4]
                line += (f" plane rows WRONG {len(nt_bad)} of the visible, first {nt_bad[:8]};"
                         f" they hold map rows {held} (BG_Plane_Top "
                         f"{int.from_bytes(rd.get('BG_Plane_Top', b''), 'big') if rd.get('BG_Plane_Top') else '?'})")
            else:
                line += " plane rows OK"
            ok = ok and not nt_bad
        extra = ""
        if zone == "EHZ" and ok:
            rows, _ = CBS.run_swscrl_ehz(text, camx)
            per = {}
            for k_, b_ in enumerate(spec["bands"]):
                st = set(CBS.group_starts(b_)) if b_["kind"] == "ramp" else None
                for i in range(b_["plane_top"], b_.get("engine_end") or 224):
                    if rows[i] is None:
                        continue
                    d = abs(CBS._sx(bg[i] - CBS._sx(rows[i][1], 16), 16))
                    slot = 0 if st is None or i in st else 1
                    per.setdefault(k_, [0, 0])[slot] = max(per.setdefault(k_, [0, 0])[slot], d)
            extra = f"  vs Sonic 2 (new-value, held) px per band: {per}"
        print(("OK   " if ok else "FAIL ") + line
              + ("" if ok else f"  BG lines differing from the model: {miss[:12]}"
                 f"{'...' if len(miss) > 12 else ''} ({len(miss)}), FG {len(fg_miss)}, "
                 f"vscroll want {want_vs}") + extra)
        bad += 0 if ok else 1
        report.append({"zone": zone, "cam": [camx, camy], "vscroll": vs, "phase": ph,
                       "ok": ok, "bg_miss": len(miss)})
    total = len(results)
    print(f"clip_bg_scroll_witness: {total} probe(s), {total - bad - unmeasured} exact, "
          f"{bad} FAIL, {unmeasured} could not measure  (rom {os.path.basename(rom)})")
    entry_fail = 0
    if a.warp_entry:
        entry_fail, lines = entry
        for ln in lines:
            print(ln)
        n_cnm = sum(1 for ln in lines if ln.startswith("COULD NOT"))
        print(f"clip_bg_scroll_witness ENTRY + FLIGHT legs: {len(lines)} row(s), "
              f"{entry_fail - n_cnm} FAIL, {n_cnm} could not measure")
        unmeasured += n_cnm
        bad += entry_fail - n_cnm
    if a.boot_entry:
        boot_fail, lines = boot
        for ln in lines:
            print(ln)
        n_cnm = sum(1 for ln in lines if ln.startswith("COULD NOT"))
        n_graded = sum(1 for ln in lines if ln.startswith(("OK", "FAIL")))
        print(f"clip_bg_scroll_witness BOOT leg: {len(lines)} row(s), {n_graded} graded, "
              f"{boot_fail - n_cnm} FAIL, {n_cnm} could not measure")
        bad += boot_fail - n_cnm
        if n_graded == 0 and not n_cnm:
            print("COULD NOT MEASURE boot: no boot was graded")
            n_cnm = 1
        unmeasured += n_cnm
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1))
    return 2 if unmeasured else (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
