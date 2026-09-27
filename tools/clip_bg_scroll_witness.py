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


#: frames graded after each warp of the ENTRY leg: the longest ratchet a tall map can need is
#: its whole scroll range at BG_VSCROLL_MAX_STEP (16) a frame, 928 / 16 = 58 on Hidden Palace
ENTRY_FRAMES = 90


async def _entry_leg(b, sym, rom, act, chains, specs, plan, spec_at, blob_lab, rates_of):
    """THE ENTRY LEG (`--warp-entry`, WOVEN-HPZ-BG-MISALIGNED 2026-09-27): what the screen shows
    on EVERY frame after a teleport INTO a tall zone, not only once it has settled.

    For each tall zone and each of its band layouts: warp to a probe of ANOTHER zone, let it
    settle, warp to the probe inside the layout's own stretch, and for ENTRY_FRAMES frames grade
    every visible line against SONIC 2: line L shows map row m = vscroll + L, i.e. Sonic 2's BG
    row window_top + m, whose Sonic 2 KIND (ratio, or drift rate) names the one band of the
    chain that may scroll it; the HScroll word must be that band's (engine_factor_scroll at the
    live camera X, plus its drift accumulator). Rows whose 64 cells are all transparent are
    free (derive_tall's rule). The nametable leg runs on every frame too.

    GRADED: every frame whose vscroll is AT its target (engine_vscroll). A frame still sliding
    to it (Step 5's rate clamp after a warp: BG-RATE-PRIME-EXEMPTION, booked) is COUNTED and,
    if it shows a wrong band, REPORTED by name, but not failed: on a chained tall map the slide
    carries rows outside the live layout's stretch, which is that booking's open question and
    reachable only through the DEBUG warp. What this leg exists to catch is a frame with the
    scroll where Sonic 2 has it and the picture still torn (WOVEN-HPZ-BG-MISALIGNED: another
    zone's band-drift accumulators added to this zone's bands, on every frame, forever).

    Returns (fails, lines): the number of frames with a wrong line or row, and printable rows."""
    out, fails = [], 0
    for key, ch in chains.items():
        r0 = ch["r0"]
        clip = next(c for c in act.clips if c.zone_key == key)
        raw, kind_of = CBS._tall_source(clip.donor, clip.zone, 0, ch["v_hi"])
        base = sym[blob_lab[key]] & 0xFFFFFF
        blob = rom[base:base + ch["span"] // 8 * PLANE_ROW_BYTES]
        # TILE rows (8 lines each) whose 64 cells are all the transparent word
        wild = {t for t in range(ch["span"] // 8)
                if not any(blob[t * PLANE_ROW_BYTES:(t + 1) * PLANE_ROW_BYTES])}
        # the band that may scroll a Sonic 2 kind, and its index per layout (drift is per index)
        factor_of = {}
        for sp in ch["specs"]:
            for bd in sp["bands"]:
                k = ("drift", bd["drift"]) if bd.get("drift") else \
                    ("flat", bd.get("s2_ratio", bd["ratio"]))
                factor_of.setdefault(k, bd["factor"])
        origin = next(p for p in plan if p[0] != key)
        targets = []
        for i in range(len(ch["specs"])):
            t = next((p for p in plan if p[0] == key and spec_at(key, p[4])[0] == i), None)
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
            bad_frames, slide, slide_bad, first = 0, 0, 0, None
            for f in range(ENTRY_FRAMES):
                rd = {}
                for name, ln in (("Hscroll_Buffer", HSCROLL_BYTES), ("Camera_X", 4),
                                 ("Camera_Y", 4), ("Parallax_Current_Vscroll_BG", 2),
                                 ("Parallax_Drift_Acc", 4 * DRIFT_BANDS)):
                    if name in sym:
                        r = await b.call("emulator/read_memory", {"addr": hex(sym[name]),
                                                                  "len": ln})
                        rd[name] = bytes.fromhex(_hex(r))
                pb = b""
                for off in range(0, PLANE_BYTES, 4096):
                    r = await b.call("emulator/read_vram", {"addr": hex(VRAM_PLANE_B + off),
                                                            "len": 4096})
                    pb += bytes.fromhex(_hex(r))
                camx = int.from_bytes(rd["Camera_X"][:2], "big")
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
                if wrong or rows:
                    if sliding:
                        slide_bad += 1
                    else:
                        bad_frames += 1
                        if first is None:
                            first = (f, vs, target, li, len(wrong), wrong[:1] + wrong[-1:],
                                     rows[:4])
                await b.call("emulator/run_frames", {"frames": 1})
            fails += bad_frames > 0
            out.append(
                (f"FAIL entry {zone} layout {i} ({origin[1]} ({origin[3]},{origin[4]}) -> "
                 f"({x},{y})): {bad_frames} of {ENTRY_FRAMES} frames, the scroll AT its "
                 f"target, show a line Sonic 2 scrolls differently or a wrong plane row; first "
                 f"at frame {first[0]}: vscroll {first[1]}, layout {first[3]}, {first[4]} "
                 f"line(s) {first[5]}, rows {first[6]}" if bad_frames else
                 f"OK   entry {zone} layout {i} ({origin[1]} -> ({x},{y})): every frame with "
                 f"the scroll at its target exact")
                + f"; the scroll slid to its target over {slide} frame(s)"
                + (f", and {slide_bad} of THOSE showed a band on rows Sonic 2 scrolls "
                   f"differently: BG-RATE-PRIME-EXEMPTION (a DEBUG warp's ratchet across a "
                   f"band chain), REPORTED, NOT GRADED" if slide_bad else ""))
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


async def _fly_leg(b, sym, rom, act, chains, specs, plan, spec_at, blob_lab, rates_of):
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
        res = await _fly_grade(b, sym, rom, pts, key, ch, clip, spec_at, blob_lab)
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


async def _fly_grade(b, sym, rom, pts, key, ch, clip, spec_at, blob_lab):
    """Fly through `pts` (player centres) in DEBUG free flight, grading every frame whose
    camera centre is inside `clip`. Returns (graded, bad, first, layouts) or a reason string."""
    r0 = ch["r0"]
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
    a = ap.parse_args()
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
    with open(rom, "rb") as fh:
        rom_bytes = fh.read()

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
                f1, l1 = await _entry_leg(b, sym, rom_bytes, act, chains, specs, plan, spec_at,
                                          blob_lab, rates_of)
                f2, l2 = await _fly_leg(b, sym, rom_bytes, act, chains, specs, plan, spec_at,
                                        blob_lab, rates_of)
                entry.extend((f1 + f2, l1 + l2))
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
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1))
    return 2 if unmeasured else (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
