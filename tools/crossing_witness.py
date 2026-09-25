#!/usr/bin/env python3
"""crossing_witness.py — what does a player SEE while a clip act's zone crossing happens?

WHY IT EXISTS (research 2026-09-25, docs/research/2026-09-25-shorter-connector.md). The
tunnel between two clip zones is as long as it is because two things must happen while the
screen shows nothing but tunnel: the palette changes (lines 1-3 go from one zone's colours
to the other's) and the BACKGROUND changes (Plane B's tile arena is overwritten with the
other zone's art, then every plane row is repainted). Z2 (tools/clip_rom_bake.py) models the
first as a 16-frame fade; nothing in the clip tools models the second. This witness measures
both on a running clip ROM instead of arguing about them, one tick at a time, so a shorter
connector can be judged by what actually reaches the screen.

THIS IS A WITNESS, NOT A GATE (the same status as tools/tunnel_run_witness.py): no runner
owns a clip ROM (it is a throwaway shape), so it is run by hand against an
`S2CLIP=<id> DEBUG=1 ./build.sh` ROM. Exit 1 when a drive could not run or the ROM faulted;
exit 3 when it ran and saw a glitch frame; 0 when it ran and saw none.

WHAT ONE TICK'S ROW SAYS (all read from RAM/CRAM, never inferred):
  cam       Camera_X after tick T's logic. The displayed frame for tick T scrolls to it:
            Parallax_Update fills the HScroll buffer from this camera in the same tick, and
            the VBlank that follows ships it.
  pal       which zone's colours Palette_Buffer lines 1-3 hold after tick T's compose
            (A / B / `mix` = mid-fade), and `cram`, which zone's colours the HARDWARE held at
            the SAME sample (read after the VBlank that follows tick T; see analyse) — i.e. what tick T's frame is scanned out with. A row whose two
            disagree is a dropped palette DMA (buffers.emp leaves the line dirty and retries).
  bg        the BG tile arena (BG_Tiles_Current / BG_Tiles_Target: `A`, `B`, or `->B` while
            an overwrite is in flight), the layout the plane is promised (BG_Plane_Layout),
            and BG_Wipe_Cursor (plane rows left to repaint; 0 = settled).
  show      which zones' CELLS the screen's world-x span [cam, cam+319] reaches: `A`
            (x < zone A's right edge), `B` (x+319 >= zone B's left edge), `-` (only corridor).

A GLITCH FRAME is a tick whose screen reaches a zone's cells while that zone's palette is
not the one scanned out, or while the background is not settled on that zone's picture
(arena holds its blob, plane promised its layout, and the wipe has painted at least the
BG_SCREEN_ROWS rows the screen can show — the wipe starts at the top visible row and walks
down, engine/level/bg.emp). That is geometry on logged state, so it is exact for the
foreground; it is CONSERVATIVE for the background (a background pixel is only visible
through a zone's transparent pixels, which this does not model).

THE PIXEL CHECK (`--scan`): on every tick from the crossing until everything is settled,
plus two either side, a full-screen emulator/pixel_attribution scan counts the pixels whose
winning CRAM index is on lines 1-3. The hypothesis the short connector rests on is that this
count is ZERO while anything is in flight — the tunnel is drawn on line 0 and hides the
background, and Sonic and the HUD are line 0 — so no colour change can be seen however it
happens. A non-zero count names the layer (planeA/planeB/sprite/backdrop) so it can be
chased. The attribution describes the LAST COMPLETED video frame, which trails the state
read beside it by one tick (tools/e2_snap_capture.py's header finding); the scan window is
widened by two ticks either side so that offset cannot hide a pixel.

Usage:
    python3 tools/crossing_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --manifest games/sonic4/data/clips/<id>/clips.json [--scan] [--speeds 0,top,cap]
"""
import argparse
import asyncio
import os
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import loop_step_over_witness as L                         # noqa: E402  (Bus, parse_lst)
import tunnel_run_witness as T                             # noqa: E402  (ground_y, PIN_FRAMES)
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402
import clip_manifest as CM                                 # noqa: E402

SCREEN_W = 320
SCREEN_H = 224
#: plane rows the screen can touch at once — engine/level/bg.emp BG_SCREEN_ROWS
#: (SCREEN_HEIGHT / BG_STREAM_ROW_PX + 1). Read from the listing when it is there.
BG_PLANE_ROWS = 64
#: engine/level/parallax.emp BG_VSCROLL_MAX_STEP = BG_VSCROLL_MAX_STEP_ROWS (2) x 8 px: the
#: Step 5 ratchet's clamp. main() re-reads it from the engine source and refuses if it cannot.
BG_VSCROLL_MAX_STEP = 16
ROW_BYTES = 128           # PLANE_H_CELLS (64) words: one plane row, one layout row
RUN_MARGIN = 400          # start/end this far outside the corridor: past every mouth
NEED = ("Camera_X", "Camera_Y", "Region_Current", "Palette_Buffer", "Pal_Fade_Frames",
        "Parallax_Transition_Frames",
        "BG_Tiles_Current", "BG_Tiles_Target", "BG_Plane_Layout", "BG_Wipe_Cursor",
        "Lag_Frame_Count", "Logic_Tick", "Player_1")


def zone_palettes(act):
    root = CM._root(None)
    out = []
    for donor, zone in act.zone_table:
        data = open(os.path.join(root, donor, zone, "palette.bin"), "rb").read()
        out.append([(data[i] << 8) | data[i + 1] for i in range(0, 96, 2)])
    return out


def classify(words, pals, names):
    for p, n in zip(pals, names):
        if [w & 0x0EEE for w in words] == [w & 0x0EEE for w in p]:
            return n
    return "mix"


async def cram_1_3(client):
    out = []
    for line in (1, 2, 3):
        c = await client.call("emulator/read_cram", {"line": line})
        ents = next((v for v in c.values()
                     if isinstance(v, list) and v and isinstance(v[0], dict) and "raw" in v[0]),
                    None)
        if ents is None or len(ents) != 16:
            raise SystemExit(f"crossing_witness: read_cram line {line} returned no 16-entry "
                             f"list — UNMEASURABLE: {str(c)[:200]}")
        out += [int(e["raw"], 16) for e in ents]
    return out


async def scan_lines_1_3(client):
    """Full-screen attribution: {layer: pixels whose winning CRAM index is on lines 1-3}."""
    hits = {}
    for y in range(SCREEN_H):
        for x in range(SCREEN_W):
            a = await client.call("emulator/pixel_attribution", {"x": x, "y": y})
            idx = a.get("cramIndex")
            if idx is None:
                raise SystemExit("crossing_witness: pixel_attribution returned no cramIndex "
                                 "— UNMEASURABLE")
            if idx >= 16:
                lay = (a.get("winner") or {}).get("layer", "?")
                hits[lay] = hits.get(lay, 0) + 1
    return hits


async def drive(sock, syms, equs, act, geo, direction, gsp, max_frames, scan, jump=False):
    a_right, b_left, x_in, x_out = geo
    if direction == "right":
        start_x, end_x, button = x_in - RUN_MARGIN, x_out + RUN_MARGIN, "right"
    else:
        start_x, end_x, button = x_out + RUN_MARGIN, x_in - RUN_MARGIN, "left"
    co = act.corridors[0]
    feet = T.ground_y(act, start_x, co.tunnel.ceiling_y if co.tunnel else 0)
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    client = BusClient(socket_path=sock, client_id="cxw", client_name="crossing-witness")
    await client.connect()
    b = L.Bus(client)
    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_YVEL = P + equs["SST_y_vel"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")
    if (await b.read(A_DBG, 1))[0]:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
    # tunnel_run_witness's measured placement: camera and player written together, the player
    # PINNED while the far-away window streams in.
    await b.write(syms["Camera_X"], (start_x - 160) << 16, 4)
    await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
    for _ in range(T.PIN_FRAMES):
        await b.write(A_X, start_x << 16, 4)
        await b.write(A_Y, (feet - radius - 2) << 16, 4)
        await b.write(A_YVEL, 0, 2)
        await b.frames(1)
    await b.check_alive("streaming settle")
    await b.frames(T.LAND_FRAMES * 4)
    if int.from_bytes(await b.read(A_YVEL, 2), "big"):
        await client.close()
        raise SystemExit(f"crossing_witness: the player never landed at x={start_x}; "
                         f"COULD NOT RUN")

    async def state():
        rd = lambda n, w: b.read(syms[n], w)                            # noqa: E731
        pb = await b.read(syms["Palette_Buffer"] + 0x20, 96)
        return {
            "tick": int.from_bytes(await rd("Logic_Tick", 4), "big"),
            "lag": int.from_bytes(await rd("Lag_Frame_Count", 4), "big"),
            "cam": int.from_bytes(await rd("Camera_X", 4), "big") >> 16,
            "camy": int.from_bytes(await rd("Camera_Y", 4), "big") >> 16,
            "px": int.from_bytes(await b.read(A_X, 4), "big") >> 16,
            "region": int.from_bytes(await rd("Region_Current", 4), "big"),
            "pbuf": [(pb[i] << 8) | pb[i + 1] for i in range(0, 96, 2)],
            "fade": (await rd("Pal_Fade_Frames", 1))[0],
            "bg_cur": int.from_bytes(await rd("BG_Tiles_Current", 4), "big"),
            "bg_tgt": int.from_bytes(await rd("BG_Tiles_Target", 4), "big"),
            "bg_lay": int.from_bytes(await rd("BG_Plane_Layout", 4), "big"),
            "wipe": (await rd("BG_Wipe_Cursor", 1))[0],
            "cram": await cram_1_3(client),
            "vs_bg": int.from_bytes(await rd("Parallax_Current_Vscroll_BG", 2), "big"),
            # the parallax CONFIG lerp (Parallax_StartTransition): frames left, 0 = settled.
            # Since B-2 each zone's preset binds its own scroll record, so a crossing lerps
            # the background SCROLL too; a zone on screen mid-lerp shows its background
            # sliding toward where it belongs.
            "plx": (await rd("Parallax_Transition_Frames", 1))[0],
            "plane": await read_plane_b(client, equs["VRAM_PLANE_B_BYTES"]),
        }

    rows = [await state()]
    await client.call("emulator/hold", {"buttons": [button], "down": True})
    if gsp:
        await b.write(A_GSP, gsp if direction == "right" else (-gsp) & 0xFFFF, 2)
    for f in range(max_frames):
        await b.frames(1)
        st = await b.status()
        if "ErrorHandler" in (st.get("symbolAtPc") or ""):
            rows.append({"fault": st.get("symbolAtPc")})
            break
        s = await state()
        s["frame"] = f
        rows.append(s)
        # THE VERTICAL MOVE AT THE MOUTH (--jump): one jump press as the player leaves the
        # tunnel, so the camera moves vertically while the background may still be finishing
        # the rows the screen was not showing when the sweep started.
        if jump and not s.get("_jumped_any") and not any(r.get("jumped") for r in rows):
            leaving = (s["px"] >= x_out - 8) if direction == "right" else (s["px"] <= x_in + 8)
            if leaving:
                await client.call("emulator/press", {"buttons": ["c"]})
                s["jumped"] = True
        if (s["px"] >= end_x) if direction == "right" else (s["px"] <= end_x):
            break
    await client.call("emulator/hold", {"buttons": [button], "down": False})
    scans = {}
    if scan and not any("fault" in r for r in rows):
        scans = await rescan(client, b, rows, button, gsp, direction, syms, equs, start_x,
                             feet, radius, A_X, A_Y, A_YVEL, A_GSP, A_DBG)
    await client.close()
    return rows, scans


async def read_plane_b(client, base):
    """Plane B's whole nametable (PLANE_H_CELLS x PLANE_V_CELLS words) out of VRAM."""
    out = bytearray()
    for off in range(0, BG_PLANE_ROWS * ROW_BYTES, 4096):
        r = await client.call("emulator/read_vram", {"addr": hex(base + off), "len": 4096})
        h = r["bytes"][2:] if r["bytes"][:2].lower() == "0x" else r["bytes"]
        if len(h) != 8192:
            raise SystemExit(f"crossing_witness: short VRAM read at ${base + off:04X} — "
                             f"UNMEASURABLE")
        out += bytes.fromhex(h)
    return bytes(out)


async def rescan(client, b, rows, button, gsp, direction, syms, equs, start_x, feet, radius,
                 A_X, A_Y, A_YVEL, A_GSP, A_DBG):
    """Replay the identical drive (the machine is deterministic from reset) and pixel-scan the
    in-flight window. Two passes rather than one so the scan's wall-clock cannot perturb the
    run it describes; the replay is checked tick-for-tick against the first pass's camera."""
    live = [r for r in rows if "tick" in r]
    inflight = [i for i, r in enumerate(live) if r.get("_inflight")]
    if not inflight:
        return {}
    lo, hi = max(0, inflight[0] - 2), min(len(live) - 1, inflight[-1] + 2)
    await client.call("emulator/reset", {})
    await b.frames(240)
    if (await b.read(A_DBG, 1))[0]:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
    await b.write(syms["Camera_X"], (start_x - 160) << 16, 4)
    await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
    for _ in range(T.PIN_FRAMES):
        await b.write(A_X, start_x << 16, 4)
        await b.write(A_Y, (feet - radius - 2) << 16, 4)
        await b.write(A_YVEL, 0, 2)
        await b.frames(1)
    await b.frames(T.LAND_FRAMES * 4)
    await client.call("emulator/hold", {"buttons": [button], "down": True})
    if gsp:
        await b.write(A_GSP, gsp if direction == "right" else (-gsp) & 0xFFFF, 2)
    out = {}
    for i in range(1, hi + 1):
        await b.frames(1)
        if i < lo:
            continue
        cam = int.from_bytes(await b.read(syms["Camera_X"], 4), "big") >> 16
        if cam != live[i]["cam"]:
            out["replay_diverged_at"] = i
            break
        out[i] = await scan_lines_1_3(client)
    await client.call("emulator/hold", {"buttons": [button], "down": False})
    return out


def analyse(rows, scans, pals, names, geo, blobs_seen, rom=None):
    a_right, b_left, _x_in, _x_out = geo
    live = [r for r in rows if "tick" in r]
    zone_of_region = {}
    for r in live:
        zone_of_region.setdefault(r["region"], None)
    # the region the run STARTS in is the start side's zone; the other is the far side's
    order = []
    for r in live:
        if r["region"] not in order:
            order.append(r["region"])
    lay_ptr = {z: k[1] for k, z in blobs_seen.items() if isinstance(k, tuple) and k[0] == "lay"}
    out_rows, glitches = [], []
    glide_prev = False
    for i, r in enumerate(live):
        pal = classify(r["pbuf"], pals, names)
        # SAME-SAMPLE ALIGNMENT (measured 2026-09-25 on the 336-px clip: the tick-710 install
        # is already in CRAM at the sample whose Logic_Tick reads 710). run_frames stops after
        # the VBlank that follows tick i, before tick i+1: the frame the player then sees is
        # tick i's camera with the CRAM and nametable that VBlank shipped, all read here.
        nxt = r
        cram = classify(r["cram"], pals, names)
        zone_here = names[0] if r["cam"] + SCREEN_W // 2 < (a_right + b_left) // 2 else names[1]
        shows = ("A" if r["cam"] < a_right else "") + ("B" if r["cam"] + SCREEN_W > b_left else "")
        bg_blob = blobs_seen.get(r["bg_cur"], "?") if r["bg_cur"] else "partial"
        bg_tgt = blobs_seen.get(r["bg_tgt"], "?") if r["bg_tgt"] else ""
        lay = blobs_seen.get(("lay", r["bg_lay"]), "?")
        # THE BACKGROUND ON SCREEN, READ FROM VRAM (not the tracker's promise): the plane after
        # the VBlank that follows tick i is read at the SAME sample (see above); the rows the screen shows are
        # BG_SCREEN_ROWS from the top visible one (a one-plane map: map row = plane row).
        # Each is compared, whole, with the zone's layout row in ROM.
        top = (r["vs_bg"] >> 3) & (BG_PLANE_ROWS - 1)
        vis = [(top + k) % BG_PLANE_ROWS for k in range(BG_SCREEN_ROWS)]
        bg_visible_ok, bad_rows = {}, {}
        for z in names:
            ptr = lay_ptr.get(z)
            if nxt is None or rom is None or ptr is None:
                wrong = None
            else:
                wrong = [p for p in vis
                         if nxt["plane"][p * ROW_BYTES:(p + 1) * ROW_BYTES]
                         != rom[ptr + p * ROW_BYTES:ptr + (p + 1) * ROW_BYTES]]
            bad_rows[z] = wrong
            bg_visible_ok[z] = (bg_blob in (z, "*") and not r["bg_tgt"]
                                and wrong is not None and not wrong)
        # THE BACKGROUND'S VERTICAL SCROLL STILL RATCHETING (engine/level/parallax.emp Step 5:
        # at most BG_VSCROLL_MAX_STEP px a frame toward its target). The mapping is
        # ((camY - v_center) >> v_factor) + v_offset, never steeper than 1:1. The ratchet is
        # ENGAGED on a frame whose next step is the clamp itself (|step| >= BG_VSCROLL_MAX_STEP
        # with the camera moving less), and its last, partial step is the frame after an
        # engaged one whose step still outruns the camera. Such a frame's value is not yet the
        # zone's. (Small steps with a still camera happen in CPZ's own mapping and are NOT
        # counted: measured, they are 1-4 px and never follow a clamped step.)
        after = live[i + 1] if i + 1 < len(live) else None
        step = abs(after["vs_bg"] - r["vs_bg"]) if after is not None else 0
        cam_step = abs(after["camy"] - r["camy"]) if after is not None else 0
        glide = after is not None and step > cam_step and (
            step >= BG_VSCROLL_MAX_STEP or glide_prev)
        glide_prev = glide
        inflight = (pal == "mix" or r["fade"] or r["bg_tgt"] or r["wipe"] or not r["bg_cur"]
                    or r["plx"] or glide
                    or (cram != pal and nxt is not None))
        r["_inflight"] = bool(inflight)
        bad = []
        for z, flag in ((names[0], "A" in shows), (names[1], "B" in shows)):
            if not flag:
                continue
            if cram != z and nxt is not None:
                bad.append(f"{z} on screen, scanned out in {cram} colours")
            if glide:
                bad.append(f"{z} on screen, background vertical scroll still sliding "
                           f"({r['vs_bg']} -> {after['vs_bg']} while the camera moved "
                           f"{after['camy'] - r['camy']} px)")
            if r["plx"]:
                bad.append(f"{z} on screen, background scroll mid-lerp ({r['plx']} frame(s) of "
                           f"the parallax config transition left)")
            if not bg_visible_ok[z] and nxt is not None:
                bad.append(f"{z} on screen, background {bg_blob}{'->' + bg_tgt if bg_tgt else ''}"
                           f" layout {lay} wipe {r['wipe']}; visible plane rows not {z}'s: "
                           f"{bad_rows[z]}")
        row = {"i": i, "tick": r["tick"], "cam": r["cam"], "px": r["px"], "zone": zone_here,
               "bg_ok": dict(bg_visible_ok),
               "shows": shows or "-", "pal": pal, "cram": cram, "fade": r["fade"],
               "bg": bg_blob + ("->" + bg_tgt if bg_tgt else ""), "lay": lay,
               "wipe": r["wipe"], "plx": r["plx"], "vs_bg": r["vs_bg"], "glide": glide,
               "lag": r["lag"], "bad": bad}
        out_rows.append(row)
        if bad:
            glitches.append(row)
    return out_rows, glitches


BG_SCREEN_ROWS = SCREEN_H // 8 + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--speeds", default="0,top,cap",
                    help="comma list of ground speeds: an integer, `top` (PHYS_TOP_SPEED) or "
                         "`cap` (PHYS_GSP_CAP)")
    ap.add_argument("--directions", default="right,left")
    ap.add_argument("--scan", action="store_true",
                    help="replay each run and pixel-scan the in-flight window (slow: ~5 s a tick)")
    ap.add_argument("--trace", action="store_true", help="print every in-flight row")
    ap.add_argument("--jump", action="store_true",
                    help="press jump as the player leaves the tunnel: a vertical camera move at "
                         "the mouth, while the background may still be finishing its rows")
    a = ap.parse_args()
    syms, equs = L.parse_lst(a.lst)
    T._EQUS.update(equs)
    global BG_VSCROLL_MAX_STEP
    from fg_working_set import ConstantSource
    src = ConstantSource()
    for rel in ("engine/system/constants.emp", "engine/level/parallax.emp"):
        src.load_file(str(TOOLS.parent / rel))
    BG_VSCROLL_MAX_STEP = int(src.get("BG_VSCROLL_MAX_STEP"))
    missing = [n for n in NEED if n not in syms]
    if missing:
        raise SystemExit(f"crossing_witness: {a.lst} carries no {missing} — COULD NOT RUN")
    act = CM.load(a.manifest)
    clips = sorted(act.clips, key=lambda c: c.dst[0])
    if len(clips) != 2 or not act.corridors:
        raise SystemExit("crossing_witness: this reads a two-clip act with one corridor")
    a_right, b_left = clips[0].dst[0] + clips[0].dst[2], clips[1].dst[0]
    co = act.corridors[0]
    geo = (a_right, b_left, co.dst[0], co.dst[0] + co.dst[2])
    pals = zone_palettes(act)
    rom = open(a.rom, "rb").read()
    if "VRAM_PLANE_B_BYTES" not in equs or "Parallax_Current_Vscroll_BG" not in syms:
        raise SystemExit("crossing_witness: the listing carries no VRAM_PLANE_B_BYTES / "
                         "Parallax_Current_Vscroll_BG — COULD NOT RUN")
    names = [z for _d, z in act.zone_table]
    speed_of = {"top": equs["PHYS_TOP_SPEED"], "cap": equs["PHYS_GSP_CAP"]}
    speeds = [speed_of.get(s, None) if s in speed_of else int(s, 0) for s in a.speeds.split(",")]
    print(f"crossing_witness: {a.rom} — zones {names}, {names[0]} ends x {a_right}, "
          f"{names[1]} starts x {b_left}, corridor {b_left - a_right} px")
    total_bad, faults, n = 0, 0, 0
    results = []
    for direction in a.directions.split(","):
        for gsp in speeds:
            with aether_emulator(a.rom, symbols=a.lst) as sock:
                rows, _ = asyncio.run(drive(sock, syms, equs, act, geo, direction, gsp,
                                            a.frames, False, jump=a.jump))
            n += 1
            if any("fault" in r for r in rows):
                faults += 1
                print(f"  {direction} gsp ${gsp:04X}: FAULT {rows[-1]['fault']}")
                continue
            live = [r for r in rows if "tick" in r]
            # which blob/layout pointer belongs to which zone: the value each settles on while
            # the camera centre is deep inside that zone's side (first and last rows).
            first, last = live[0], live[-1]
            start_zone, end_zone = (names[0], names[1]) if direction == "right" else (names[1], names[0])
            # ONE arena blob on both sides = the zones' tiles are CO-RESIDENT (clip_rom_bake's
            # per-clip override): the arena is right for either zone, `*`.
            shared = first["bg_cur"] == last["bg_cur"]
            blobs = ({first["bg_cur"]: "*"} if shared else
                     {first["bg_cur"]: start_zone, last["bg_cur"]: end_zone})
            blobs.update({("lay", first["bg_lay"]): start_zone, ("lay", last["bg_lay"]): end_zone})
            out_rows, glitches = analyse(rows, {}, pals, names, geo, blobs, rom=rom)
            scans = {}
            if a.scan:
                with aether_emulator(a.rom, symbols=a.lst) as sock:
                    scans = asyncio.run(_scan_only(sock, syms, equs, act, geo, direction, gsp,
                                                   rows))
            infl = [r for r in out_rows if live[r["i"]]["_inflight"]]
            span = (infl[0], infl[-1]) if infl else None
            cross = next((r for r in out_rows[1:] if live[r["i"]]["region"] != live[0]["region"]), None)
            print(f"  {direction:>5} gsp ${gsp:04X}: {len(out_rows)} ticks; crossing at tick-row "
                  f"{cross['i'] if cross else None} cam {cross['cam'] if cross else None} "
                  f"(centre {cross['cam'] + 160 if cross else None}); in flight "
                  + (f"{len(infl)} tick(s), rows {span[0]['i']}..{span[1]['i']}, cam "
                     f"{span[0]['cam']}..{span[1]['cam']}" if span else "never")
                  + f"; GLITCH ticks {len(glitches)}")
            if cross:
                # THE TIMELINE the connector's length has to cover, in frames after the
                # crossing frame, at this speed: the arriving zone's palette scanned out, its
                # background settled on every row the screen can show, and the first frame
                # whose screen reaches that zone's cells. slack = the last minus the later
                # of the first two; negative = frames of visible glitch.
                far = end_zone
                arrive = "B" if direction == "right" else "A"
                c0 = cross["i"]
                t_pal = next((r["i"] - c0 for r in out_rows[c0:] if r["cram"] == far), None)
                t_bg = next((r["i"] - c0 for r in out_rows[c0:]
                             if r["bg_ok"][far] and not r["plx"] and not r["glide"]), None)
                t_show = next((r["i"] - c0 for r in out_rows[c0:] if arrive in r["shows"]), None)
                done = max(t_pal, t_bg) if None not in (t_pal, t_bg) else None
                slack = (t_show - done) if None not in (t_show, done) else None
                print(f"      timeline (frames after the crossing frame): {far} palette on "
                      f"screen +{t_pal}, {far} background settled on the visible rows +{t_bg}, "
                      f"screen first reaches {far} +{t_show}; SLACK {slack} frame(s)")
                results.append({"direction": direction, "gsp": gsp, "t_pal": t_pal,
                                "t_bg": t_bg, "t_show": t_show, "slack": slack,
                                "glitches": len(glitches)})
            if a.trace:
                for r in infl:
                    print(f"      {r}")
            for g in glitches[:12]:
                print(f"      GLITCH {g}")
            if scans:
                div = scans.pop("replay_diverged_at", None)
                lit = {i: h for i, h in scans.items() if h}
                print(f"      pixel scan: {len(scans)} tick(s) scanned (rows {min(scans)}..{max(scans)})"
                      f"; {len(lit)} with any line 1-3 pixel"
                      + (f"; REPLAY DIVERGED at row {div} — scan truncated" if div else ""))
                for i, h in sorted(lit.items())[:12]:
                    print(f"        row {i} cam {out_rows[i]['cam']} bg {out_rows[i]['bg']} "
                          f"wipe {out_rows[i]['wipe']} pal {out_rows[i]['pal']}: {h}")
            total_bad += len(glitches)
    slacks = [r["slack"] for r in results if r["slack"] is not None]
    print(f"crossing_witness: {n} run(s), {faults} faulted, {total_bad} glitch tick(s) in total; "
          f"worst slack {min(slacks) if slacks else None} frame(s) over {len(slacks)} timed run(s)")
    print("finished=1")
    if faults:
        return 1
    return 3 if total_bad else 0


async def _scan_only(sock, syms, equs, act, geo, direction, gsp, rows):
    """Second pass: replay the same drive and pixel-scan the first pass's in-flight window."""
    a_right, b_left, x_in, x_out = geo
    if direction == "right":
        start_x, button = x_in - RUN_MARGIN, "right"
    else:
        start_x, button = x_out + RUN_MARGIN, "left"
    co = act.corridors[0]
    feet = T.ground_y(act, start_x, co.tunnel.ceiling_y if co.tunnel else 0)
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    client = BusClient(socket_path=sock, client_id="cxs", client_name="crossing-scan")
    await client.connect()
    b = L.Bus(client)
    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_YVEL = P + equs["SST_y_vel"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    out = await rescan(client, b, rows, button, gsp, direction, syms, equs, start_x, feet,
                       radius, A_X, A_Y, A_YVEL, A_GSP, A_DBG)
    await client.close()
    return out


if __name__ == "__main__":
    sys.exit(main())
