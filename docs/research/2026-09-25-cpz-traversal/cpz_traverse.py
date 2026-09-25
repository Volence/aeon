#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate, no runner): how far right can the player actually get in
a widened Chemical Plant clip, on the one plane he ever uses? S2CLIP-CPZ-LONGER, owner
answer to S2CLIP-CPZ-FURTHER: "extend as far as Sonic can actually run".

Runs the real clip ROM headless (tools/aether_instance, the same harness and drive
preamble as tools/tunnel_run_witness.py: leave debug-fly with a real B press, write the
camera and the player together, pin the player while streaming settles, check he landed).
Then it drives RIGHT under one of four strategies and records the furthest x reached:

  hold      RIGHT held from rest (the input alone).
  top/cap   RIGHT held after injecting PHYS_TOP_SPEED / PHYS_GSP_CAP ground speed ONCE,
            after landing (tunnel_run_witness's injection rule).
  hop       RIGHT held; whenever the player is grounded and has not set a new max x
            for HOP_AFTER frames, jump (C held JUMP_HOLD frames, the full-height jump).
  spin      as hop, but alternate a jump with a spindash (release RIGHT, hold DOWN,
            press C SPIN_REVS times, release DOWN, hold RIGHT again).
  randomN   a crude random explorer, seed N: every 20..90 frames pick RIGHT, LEFT,
            RIGHT+jump, LEFT+jump (random hold length), a spindash, or nothing held.
            Stuck = no new max x for 4 x STUCK_FRAMES.

A run ENDS when (a) x reaches --end-x (crossed), (b) no new max x for STUCK_FRAMES frames
(stuck: the reason is read from the last frames' x / y / gsp / state), (c) y passes
--fall-y (fell into the act's unbounded fall: this engine has no death, so a body under the
terrain falls forever), (d) --frames runs out, or (e) the ROM faults (ErrorHandler at pc).

What it cannot see: pixels, objects (the clip carries none), plane B (the player never
leaves plane A in this act). What stops him is read from coordinates, then from the
collision around them (--dump prints the plane-A solidity map there).

Usage:
    python3 docs/research/2026-09-25-cpz-traversal/cpz_traverse.py \\
        --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --manifest games/sonic4/data/clips/s2_ehz_cpz/clips.json \\
        --start-x 13960 --end-x 18300 [--strategies hold,top,cap,hop,spin]
"""
import argparse
import asyncio
import pathlib
import random
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import loop_step_over_witness as L                         # noqa: E402
import tunnel_run_witness as T                             # noqa: E402
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402
import clip_manifest as CM                                 # noqa: E402

STUCK_FRAMES = 600
HOP_AFTER = 20
JUMP_HOLD = 24
SPIN_REVS = 4


async def run(sock, syms, equs, act, start_x, end_x, fall_y, strategy, max_frames):
    feet = T.ground_y(act, start_x, 0)
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    client = BusClient(socket_path=sock, client_id="cpzt", client_name="cpz-traverse")
    await client.connect()
    b = L.Bus(client)
    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_YVEL = P + equs["SST_y_vel"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    A_STATE = P + T.PL_STATE_OFF
    grounded = {equs["PSTATE_GROUND"], equs["PSTATE_ROLL"]}

    async def hold(btn, down):
        await client.call("emulator/hold", {"buttons": [btn], "down": down})

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")
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
    await b.frames(L.LAND_FRAMES * 4)
    await b.check_alive("placement")
    if int.from_bytes(await b.read(A_YVEL, 2), "big"):
        await client.close()
        raise SystemExit(f"cpz_traverse: the player never landed at x={start_x}")

    await hold("right", True)
    if strategy in ("top", "cap"):
        await b.write(A_GSP, equs["PHYS_TOP_SPEED" if strategy == "top" else "PHYS_GSP_CAP"], 2)
    rows, best, best_f, outcome = [], start_x, 0, "frames"
    action, action_left, jumps, spins, next_is_spin = None, 0, 0, 0, False
    rng = random.Random(strategy)          # "random<N>": seed N, reproducible
    next_pick = 0
    for f in range(max_frames):
        await b.frames(1)
        sym = (await b.status()).get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            outcome = f"FAULT {sym}"
            break
        x = int.from_bytes(await b.read(A_X, 4), "big") >> 16
        y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
        g = int.from_bytes(await b.read(A_GSP, 2), "big")
        g = g - 0x10000 if g >= 0x8000 else g
        st = (await b.read(A_STATE, 1))[0]
        rows.append((f, x, y, g, st))
        if x > best:
            best, best_f = x, f
        if x >= end_x:
            outcome = "crossed"
            break
        if y >= fall_y:
            outcome = "fell"
            break
        if f - best_f >= STUCK_FRAMES * (4 if strategy.startswith("random") else 1):
            outcome = "stuck"
            break
        # ---- the strategies' inputs ----
        if action_left:
            action_left -= 1
            if action == "jump" and action_left == 0:
                await hold("c", False)
            elif action == "spin":
                k = SPIN_REVS * 4 - action_left            # 4 frames per rev
                if k % 4 == 1:
                    await hold("c", True)
                elif k % 4 == 3:
                    await hold("c", False)
                if action_left == 0:
                    await hold("down", False)
                    await hold("right", True)
            continue
        if strategy.startswith("random") and f >= next_pick:
            # a crude random explorer: every 20..90 frames pick one of RIGHT, LEFT,
            # RIGHT+jump, LEFT+jump, a rightward spindash, or nothing held.
            for btn in ("right", "left", "c", "down"):
                await hold(btn, False)
            pick = rng.choice(("right", "right", "right", "left", "rjump", "rjump",
                               "ljump", "spin", "none"))
            if pick in ("right", "left"):
                await hold(pick, True)
            elif pick in ("rjump", "ljump"):
                await hold("right" if pick == "rjump" else "left", True)
                await hold("c", True)
                action, action_left = "jump", rng.randint(4, JUMP_HOLD)
                jumps += 1
            elif pick == "spin" and st in grounded:
                await hold("down", True)
                action, action_left = "spin", SPIN_REVS * 4
                spins += 1
            next_pick = f + rng.randint(20, 90)
            continue
        if strategy in ("hop", "spin") and st in grounded and f - best_f >= HOP_AFTER:
            if strategy == "spin" and next_is_spin:
                await hold("right", False)
                await hold("down", True)
                action, action_left = "spin", SPIN_REVS * 4
                spins += 1
            else:
                await hold("c", True)
                action, action_left = "jump", JUMP_HOLD
                jumps += 1
            next_is_spin = not next_is_spin
    for btn in ("right", "c", "down"):
        await hold(btn, False)
    await client.close()
    return rows, best, outcome, jumps, spins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--start-x", type=int, required=True)
    ap.add_argument("--end-x", type=int, required=True)
    ap.add_argument("--fall-y", type=int, default=2400)
    ap.add_argument("--frames", type=int, default=6000)
    ap.add_argument("--strategies", default="hold,top,cap,hop,spin")
    ap.add_argument("--tail", type=int, default=6, help="last rows to print per run")
    a = ap.parse_args()
    syms, equs = L.parse_lst(a.lst)
    act = CM.load(a.manifest)
    print(f"cpz_traverse: {a.rom} start x {a.start_x} -> end x {a.end_x}, fall y {a.fall_y}")
    overall = a.start_x
    for s in a.strategies.split(","):
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            rows, best, outcome, jumps, spins = asyncio.run(
                run(sock, syms, equs, act, a.start_x, a.end_x, a.fall_y, s, a.frames))
        overall = max(overall, best)
        at = next(r for r in rows if r[1] == best) if rows else None
        print(f"  {s:>5}: furthest x {best} (first at frame {at[0] if at else '-'}, y {at[2] if at else '-'})"
              f" outcome {outcome} after {len(rows)} frames; jumps {jumps} spindashes {spins};"
              f" y range {min(r[2] for r in rows)}..{max(r[2] for r in rows)}")
        for r in rows[-a.tail:]:
            print(f"        f{r[0]} x {r[1]} y {r[2]} gsp {r[3]} state {r[4]}")
    print(f"cpz_traverse: furthest x over all strategies = {overall}")
    print("finished=1")


if __name__ == "__main__":
    main()
