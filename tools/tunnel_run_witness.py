#!/usr/bin/env python3
"""tunnel_run_witness.py — run a player through a clip act's corridor, headless, frame by frame.

WHY IT EXISTS. `tools/test_clip_two_zone.py` proves the tunnel's collision STATICALLY: no
floor step over 1 px across either seam, a ceiling with a standing player's clearance. A
static profile cannot show the engine's own sensors meeting it at speed — a ramp block's
wall side, a ceiling probe firing on a player who never jumps, a camera outrunning the
streamed window. This runs the real clip ROM with the shipped physics and records what
happened, one frame at a time. The owner's words it answers: "the tunnel to transition
has to be like an FG hiding the bg ... It doesn't have to be so long", plus the 4-px step
he hit at the seam, and the brief's "walkable at speed, no snag".

THIS IS A WITNESS, NOT A GATE: it has no runner, and it is run by hand against an
`S2CLIP=<id> ./build.sh` ROM (a clip ROM is a throwaway shape, so no build lane owns one).
It reports; exit 1 only when a drive could not run or the ROM faulted — a faulted or
never-landed machine is not a result, and reporting it as a crossing would be a lie.

WHAT IS INJECTED, and nothing else: `PlayerV.ground_speed`, ONCE, after the player has
landed (loop_step_over_witness's measured drive order — a pre-landing injection is erased
by the landing frame). Everything after is the engine's, with RIGHT (or LEFT) held. Speeds
are the build's own constants: 0 (a walk from rest, the input alone), PHYS_TOP_SPEED, and
PHYS_GSP_CAP.

THE DRIVE ORDER (loop_step_over_witness's, each item paid for there): leave debug-fly with
a real B press; set the camera FIRST and let streaming settle, THEN place the player; let
the camera follow afterwards.

WHAT IT READS FROM THE MANIFEST, not typed here: the corridor rectangle and the floor
surface each side (clip_manifest.collision_grids), which place the player and bound the
"inside the tunnel" window.

WHAT A "STALL" IS AND IS NOT. A stall is a frame on which x did not move and
Lag_Frame_Count did not advance. It is NOT a snag detector on its own: MEASURED 2026-09-25
on s4.s2clip.debug.bin, `--control-window 10000 10832` (plain Emerald Hill ground, no
corridor) counts 107 stalls in 314 frames at a walk, against 44 in 199 through the tunnel —
under this harness's per-frame stepping the game skips player updates that the lag counter
does not see. A snag shows as |gsp| collapsing (a wall zeroes it) or a player left
short of the far end; read `|gsp| inside` and `crossed`, and always beside a control.
RE-MEASURED after merging the lag fix (origin/master 8939377f): the same six tunnel runs
count 23 stalls in total (was 299) and at most 3 lag frames per run, so most of that count
was the page-cache lag the fix removed, not the harness and not the tunnel.

WHAT IT CANNOT SEE, said out loud: pixels. Whether the tunnel LOOKS right, whether the
background is hidden on screen, and how the palette fade reads are the owner's look.

Usage:
    python3 tools/tunnel_run_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --manifest games/sonic4/data/clips/s2_ehz_cpz/clips.json
"""
import argparse
import asyncio
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import loop_step_over_witness as L                         # noqa: E402  (Bus, parse_lst, paths)
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402
import clip_manifest as CM                                 # noqa: E402
import collision_pipeline as CP                            # noqa: E402

LAND_FRAMES = L.LAND_FRAMES
#: frames the player is pinned at the start while the camera's window streams in (measured,
#: see `drive`).
PIN_FRAMES = 600
#: how far outside the corridor each run starts and must end, px. One screen half: the
#: camera centre is past the mouth on both ends, so the whole corridor has been streamed
#: through the camera by the time a run is called complete.
RUN_MARGIN = 160
#: PlayerV.player_state's offset in the SST: sst_custom $30 + 2. A `.emp` struct field, not an
#: EQU line, so it is stated here exactly as engine/level/camera.emp states it (PL_STATE_OFF).
PL_STATE_OFF = 0x32
_EQUS = {}


def equs_state(name):
    return _EQUS[name]


def corridor_geometry(act, cid=None):
    """(corridor, the clip it leaves on the left, the clip it enters on the right).

    `cid` names the corridor; None is allowed only for an act with exactly one (the two-clip
    acts these witnesses were written for). The flanking clips are read off the rectangles:
    the clip whose right edge is the nearest at or left of the corridor's left edge, and the
    nearest whose left edge is at or right of its right edge. A woven act (s2_mtz_cpz,
    2026-09-27) has two corridors and three clips, two of one zone."""
    if cid is None:
        if len(act.corridors) != 1:
            raise SystemExit(f"this act has {len(act.corridors)} corridors "
                             f"({', '.join(c.id for c in act.corridors)}); name one with "
                             f"--corridor")
        co = act.corridors[0]
    else:
        co = next((c for c in act.corridors if c.id == cid), None)
        if co is None:
            raise SystemExit(f"no corridor {cid!r} in the act "
                             f"({', '.join(c.id for c in act.corridors)})")
    x0, x1 = co.dst[0], co.dst[0] + co.dst[2]
    left = [c for c in act.clips if c.dst[0] + c.dst[2] <= x0]
    right = [c for c in act.clips if c.dst[0] >= x1]
    if not left or not right:
        raise SystemExit(f"corridor {co.id!r} has no clip on {'both sides' if not left and not right else 'one side'}")
    return (co, max(left, key=lambda c: c.dst[0] + c.dst[2]), min(right, key=lambda c: c.dst[0]))


async def place(client, b, syms, x, y, frames=None):
    """Put the player at (x, y) (his centre) and hold him there while the window streams.

    THE DEBUG SHAPE PLACES THROUGH THE WARP MAILBOX (Debug_Warp_Consume re-runs the boot
    ladder, Section_Init -> EntityWindow_Init included): a bare camera write of thousands of
    px halts it on EntityWindow_Slide's step assert (since 7c7ccf96). The plain shape has no
    warp consumer; there the camera and the pinned player are written together (this file's
    original, measured order). Either way the player is then PINNED for `frames`
    (PIN_FRAMES by default)."""
    frames = PIN_FRAMES if frames is None else frames
    P = syms["Player_1"]
    A_X, A_Y = P + _EQUS["SST_x_pos"], P + _EQUS["SST_y_pos"]
    A_YVEL = P + _EQUS["SST_y_vel"]
    if "Warp_Req_Flag" in syms:
        await b.write(syms["Warp_Req_X"], x, 2)
        await b.write(syms["Warp_Req_Y"], y, 2)
        await b.write(syms["Warp_Req_Flag"], 1, 1)
        for _ in range(120):
            await b.frames(1)
            if (await b.read(syms["Warp_Req_Flag"], 1))[0] == 0:
                break
        else:
            raise SystemExit("the warp mailbox was never acknowledged; COULD NOT RUN")
    else:
        await b.write(syms["Camera_X"], (x - 160) << 16, 4)
        await b.write(syms["Camera_Y"], (y - 112) << 16, 4)
    for _ in range(frames):
        await b.write(A_X, x << 16, 4)
        await b.write(A_Y, y << 16, 4)
        await b.write(A_YVEL, 0, 2)
        await b.frames(1)


def run_up(act, co, side, want):
    """(x, feet y): where a run toward corridor `co` starts, on the `side` ("left"/"right") of
    it, as far as `want` px out from its mouth. THE RUN-UP IS MEASURED, not assumed: from the
    corridor's floor at the mouth, walk out 8 px at a time along plane A's surface while each
    step is within 16 px of the last (Chemical Plant's track drops 10 px in the first 8 past
    the woven act's first tunnel); the start is the farthest column reached whose surface is
    within 1 px of its neighbour's (level ground), so a pinned player released there stands
    instead of sliding. MEASURED 2026-09-27: placed where Metropolis's quarter pipe falls 13 px
    in 8 he slid off and never landed; placed at its foot, 4 px in 8, he slid LEFT through the
    whole tunnel during the landing frames, before the drive began. The two-clip acts have ground all the way out; Metropolis's
    walkway at the woven act's first tunnel is 112 px, with a pit behind it that Sonic 2
    crosses on objects this act does not carry."""
    sign = -1 if side == "left" else 1
    mouth = co.dst[0] - 1 if side == "left" else co.dst[0] + co.dst[2]
    prev = co.floor_y
    best = None
    for d in range(0, want + 1, 8):
        x = mouth + sign * d
        try:
            y = ground_y(act, x, prev - 32)
        except SystemExit:
            break
        if abs(y - prev) > 16:
            break
        if abs(y - prev) <= 1:
            best = (x, y)
        prev = y
    if best is None:
        raise SystemExit(f"tunnel_run_witness: no ground at corridor {co.id!r}'s {side} mouth "
                         f"at its floor y {co.floor_y}; nothing to run from")
    return best


def ground_y(act, x, y_from):
    """The first TOP-solid pixel at world column x scanning down from y_from, plane A."""
    pa, _pb = CM.collision_grids(act)
    hm, _an = CM._bank(CM.collision_banks(act))
    for y in range(y_from, y_from + 1024):
        h = CM._word_heights(int(pa[y // 16 * 2, x // 8]), hm)
        if h is not None and CP.covers(h[x % 16], y % 16):
            return y
    raise SystemExit(f"tunnel_run_witness: no ground under x={x} below y={y_from}")


async def drive(sock, syms, equs, act, direction, gsp, max_frames, window=None, cid=None):
    co = corridor_geometry(act, cid)[0]
    x_in, x_out = window or (co.dst[0], co.dst[0] + co.dst[2])
    top = co.tunnel.ceiling_y if co.tunnel and window is None else 0
    if window is not None:
        if direction == "right":
            start_x, end_x, button = x_in - RUN_MARGIN, x_out + RUN_MARGIN, "right"
        else:
            start_x, end_x, button = x_out + RUN_MARGIN, x_in - RUN_MARGIN, "left"
        feet = ground_y(act, start_x, top)
    elif direction == "right":
        (start_x, feet), end_x, button = run_up(act, co, "left", RUN_MARGIN), x_out + RUN_MARGIN, "right"
    else:
        (start_x, feet), end_x, button = run_up(act, co, "right", RUN_MARGIN), x_in - RUN_MARGIN, "left"
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))

    client = BusClient(socket_path=sock, client_id="trw", client_name="tunnel-run")
    await client.connect()
    b = L.Bus(client)
    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_YVEL = P + equs["SST_y_vel"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    A_STATE = P + PL_STATE_OFF
    A_LAG = syms["Lag_Frame_Count"]

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")
    if (await b.read(A_DBG, 1))[0]:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
    await b.check_alive("debug-fly exit")
    # The corridor is ~11,000 px from the boot spawn, not a camera-width away as in
    # loop_step_over_witness, so its "camera first, then player" order does not hold here:
    # MEASURED 2026-09-25, the camera set alone walks back toward the boot player at 16 px a
    # frame, and a player placed after 40 settle frames falls through ground the collision
    # cache does not cover yet, with the game ticking once every ~5 frames while the
    # streamer catches up. So the player is PINNED (x, y, y_vel rewritten every frame) until
    # streaming has settled; 600 frames measured to land him on the first frame after
    # release. `place` puts him there (the warp mailbox in the DEBUG shape).
    await place(client, b, syms, start_x, feet - radius - 2)
    await b.check_alive("streaming settle")
    await b.frames(LAND_FRAMES * 4)        # 2 px of fall is several frames from rest
    await b.check_alive("placement")
    yv = int.from_bytes(await b.read(A_YVEL, 2), "big")
    if yv:
        await client.close()
        raise SystemExit(f"tunnel_run_witness: the player never landed at x={start_x} "
                         f"(y_vel={yv}); this run cannot say anything about the tunnel")
    await client.call("emulator/hold", {"buttons": [button], "down": True})
    if gsp:
        await b.write(A_GSP, gsp if direction == "right" else (-gsp) & 0xFFFF, 2)
    rows = []
    for f in range(max_frames):
        await b.frames(1)
        st = await b.status()
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            rows.append({"frame": f, "fault": sym})
            break
        x = int.from_bytes(await b.read(A_X, 4), "big") >> 16
        y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
        g = int.from_bytes(await b.read(A_GSP, 2), "big")
        v = int.from_bytes(await b.read(A_YVEL, 2), "big")
        state = (await b.read(A_STATE, 1))[0]
        lag = int.from_bytes(await b.read(A_LAG, 4), "big")
        rows.append({"frame": f, "x": x, "y": y, "gsp": g - 0x10000 if g >= 0x8000 else g,
                     "yv": v - 0x10000 if v >= 0x8000 else v, "state": state, "lag": lag})
        if (x >= end_x) if direction == "right" else (x <= end_x):
            break
    await client.call("emulator/hold", {"buttons": [button], "down": False})
    await client.close()
    return rows, (start_x, end_x, x_in, x_out, feet)


def summarise(rows, geo, direction, gsp):
    start_x, end_x, x_in, x_out, feet = geo
    live = [r for r in rows if "x" in r]
    fault = next((r for r in rows if "fault" in r), None)
    crossed = bool(live) and ((live[-1]["x"] >= end_x) if direction == "right"
                              else (live[-1]["x"] <= end_x))
    inside = [r for r in live if x_in <= r["x"] < x_out]
    # A frame where x did not move is a STALL only if the game actually ticked on it: a
    # frame on which Lag_Frame_Count advanced (engine/system/vblank.emp) ran no game logic,
    # so nothing could have moved. Lag frames are counted separately, never as snags.
    near = [(a, c) for a, c in zip(live, live[1:]) if x_in - 16 <= c["x"] < x_out + 16]
    lag_frames = sum(1 for a, c in near if c["lag"] != a["lag"])
    stalls = sum(1 for a, c in near if c["x"] == a["x"] and c["lag"] == a["lag"])
    grounded = {equs_state("PSTATE_GROUND"), equs_state("PSTATE_ROLL")}
    air = sum(1 for r in inside if r["state"] not in grounded)
    out = {"direction": direction, "gsp": gsp, "crossed": crossed, "faulted": bool(fault),
           "frames": len(live), "frames_inside": len(inside), "stall_frames": stalls,
           "lag_frames_near": lag_frames, "airborne_frames_inside": air,
           "gsp_inside": (min(abs(r["gsp"]) for r in inside),
                          max(abs(r["gsp"]) for r in inside)) if inside else None,
           "y_inside": (min(r["y"] for r in inside), max(r["y"] for r in inside))
           if inside else None,
           "last": live[-1] if live else None}
    print(f"  {direction:>5} gsp ${gsp:04X}: crossed={crossed} frames={len(live)} "
          f"inside={len(inside)} stalls={stalls} lag-frames={lag_frames} airborne-inside={air} "
          f"|gsp| inside={out['gsp_inside']} y inside={out['y_inside']}"
          + (f" FAULT {fault['fault']}" if fault else "")
          + ("" if crossed else f" last={out['last']}"))
    return out


def seam_trace(rows, x_seam, span=24):
    """Per-frame rows within `span` px of a seam: where a snag would show."""
    return [r for r in rows if "x" in r and abs(r["x"] - x_seam) <= span]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--corridor", help="the corridor to run (required when the act has more "
                                       "than one)")
    ap.add_argument("--trace", action="store_true", help="print per-frame rows at both seams")
    ap.add_argument("--control-window", nargs=2, type=int, metavar=("X0", "X1"),
                    help="THE CONTROL: run the identical drive over this x span instead of "
                         "the corridor (a stretch of donor ground), so a count that is the "
                         "engine's pacing rather than the tunnel's shows up in both")
    a = ap.parse_args()
    syms, equs = L.parse_lst(a.lst)
    _EQUS.update(equs)
    for need in ("Lag_Frame_Count",):
        if need not in syms:
            raise SystemExit(f"tunnel_run_witness: {a.lst} carries no {need}")
    act = CM.load(a.manifest)
    if not act.corridors:
        raise SystemExit("tunnel_run_witness: the manifest has no corridor")
    speeds = [0, equs["PHYS_TOP_SPEED"], equs["PHYS_GSP_CAP"]]
    results, bad = [], 0
    co = corridor_geometry(act, a.corridor)[0]
    span = a.control_window or (co.dst[0], co.dst[0] + co.dst[2])
    print(f"tunnel_run_witness: {a.rom} — "
          + (f"CONTROL window x {span[0]}..{span[1]} (not the corridor)" if a.control_window
             else f"corridor {co.id} x {span[0]}..{span[1]}"))
    for direction in ("right", "left"):
        for gsp in speeds:
            with aether_emulator(a.rom, symbols=a.lst) as sock:
                rows, geo = asyncio.run(drive(sock, syms, equs, act, direction, gsp, a.frames,
                                              a.control_window, a.corridor))
            r = summarise(rows, geo, direction, gsp)
            results.append(r)
            bad += r["faulted"]
            if a.trace:
                for seam in (geo[2], geo[3]):
                    for row in seam_trace(rows, seam):
                        print(f"      seam {seam}: {row}")
    n_cross = sum(r["crossed"] for r in results)
    print(f"tunnel_run_witness: {n_cross} of {len(results)} runs crossed the whole corridor; "
          f"{sum(r['stall_frames'] for r in results)} stall frame(s) at or inside it "
          f"(frames the game ticked and x did not move); "
          f"{sum(r['airborne_frames_inside'] for r in results)} airborne frame(s) inside; "
          f"{bad} faulted")
    print("finished=1")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
