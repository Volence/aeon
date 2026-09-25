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


def ground_y(act, x, y_from):
    """The first TOP-solid pixel at world column x scanning down from y_from, plane A."""
    pa, _pb = CM.collision_grids(act)
    hm, _an = CM._bank(CM.collision_banks(act))
    for y in range(y_from, y_from + 1024):
        h = CM._word_heights(int(pa[y // 16 * 2, x // 8]), hm)
        if h is not None and CP.covers(h[x % 16], y % 16):
            return y
    raise SystemExit(f"tunnel_run_witness: no ground under x={x} below y={y_from}")


async def drive(sock, syms, equs, act, direction, gsp, max_frames, window=None):
    co = act.corridors[0]
    x_in, x_out = window or (co.dst[0], co.dst[0] + co.dst[2])
    top = co.tunnel.ceiling_y if co.tunnel and window is None else 0
    if direction == "right":
        start_x, end_x, button = x_in - RUN_MARGIN, x_out + RUN_MARGIN, "right"
    else:
        start_x, end_x, button = x_out + RUN_MARGIN, x_in - RUN_MARGIN, "left"
    feet = ground_y(act, start_x, top)
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
    # streamer catches up. So both are written together and the player is PINNED (x, y,
    # y_vel rewritten every frame) until streaming has settled; 600 frames measured to
    # land him on the first frame after release.
    await b.write(syms["Camera_X"], (start_x - 160) << 16, 4)
    await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
    for _ in range(PIN_FRAMES):
        await b.write(A_X, start_x << 16, 4)
        await b.write(A_Y, (feet - radius - 2) << 16, 4)
        await b.write(A_YVEL, 0, 2)
        await b.frames(1)
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
    co = act.corridors[0]
    span = a.control_window or (co.dst[0], co.dst[0] + co.dst[2])
    print(f"tunnel_run_witness: {a.rom} — "
          + (f"CONTROL window x {span[0]}..{span[1]} (not the corridor)" if a.control_window
             else f"corridor {co.id} x {span[0]}..{span[1]}"))
    for direction in ("right", "left"):
        for gsp in speeds:
            with aether_emulator(a.rom, symbols=a.lst) as sock:
                rows, geo = asyncio.run(drive(sock, syms, equs, act, direction, gsp, a.frames,
                                              a.control_window))
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
