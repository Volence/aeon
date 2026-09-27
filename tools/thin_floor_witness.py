#!/usr/bin/env python3
"""thin_floor_witness.py — drop a real player onto every thin floor in OJZ act 1 at the fastest
speeds a fall there can reach, and count the drops that pass through.

WHAT IT IS FOR (feel/s3k-fall, owner ruling FALL-FEEL 2026-09-27). The fall is uncapped now, as
S3K's is (skdisasm sonic3k.asm:36035). One collision probe only resolves a move shorter than a
collision cell, so the airborne move splits any frame faster than PHYS_SWEEP_STEP into parts no
larger than it and probes after each (games/sonic4/player/player_air.emp, Air_Move). This is the
proof that it holds on the ROM: a floor ONE CELL thick or thinner is exactly the surface a
whole-cell step can skip, so every such pixel column the act has is dropped onto, at every
speed on the ladder up to the fastest a fall from the top of the act reaches there, from every
integer start height inside one cell above it. The model for it was FALL-CAP-15's own
tunnelling argument (docs/DEFERRED_WORK.md, "Fall cap"); that parcel shipped a derived
constant and no emulator witness, so there was none to extend and this is the first.

THE TARGETS ARE DERIVED, never typed: from the committed editor collision the bake reads
(games/sonic4/data/editor/ojz/act1/section_0.collattr{,b}.bin — section 0 is the only section
with collision authored, docs/research/2026-09-27-ojz-feel.md), sampled exactly as
loop_step_over_witness.ground_feet does (the S&K shape bank, flips, SOL_TOP for the floor
class the landing probe uses). A TARGET is a column x on plane A or B whose floor-class solid
run starting at `top` (air above it) is at most COLL_CELL_H (16) px thick, and whose centre
column has DROP_CLEAR px of air of ANY class above `top` on that plane, so the start is not
inside anything. Plane B is dropped only where its column differs from plane A's.

THE DROP (nothing else is injected). Through the DEBUG warp mailbox (Warp_Req_X/Y/Flag, never a
bare camera write): the warp re-centres the camera, re-inits the collision ring and puts the
player in PSTATE_AIR at rest with the subpixel cleared. Then the layer byte and y_vel are set,
and frames run until he is grounded or has passed the floor. The start is the player's FEET
`d` px above `top` (d = 1..16); y_vel is v << 8 for v on the SPEED LADDER:
  * vmax(top): the y_vel a fall from rest at the act's top edge (y 0) has on the frame it
    reaches `top`, integrated with the ROM's own PHYS_GRAVITY in the classic order (move, then
    gravity). No fall in the act is faster there; a jump off the top edge adds at most the
    ~7 px of a jump's rise, far inside the ladder's slack.
  * every rung of LADDER (px/frame): one cell, the airborne camera's step, two cells, three —
    where a split's part count changes. Section 0 is the act's TOP section, so its vmax is
    under ~30 px/frame; the rungs above a target's vmax are not reachable there and are
    dropped anyway, as a check of the mechanism rather than of this act.
The DEFAULT arm drops every target at vmax from every d; `--ladder` adds the rungs (every
LADDER_STRIDE-th target); `--targets N` caps the count for a quick look.

THE GRADE, per drop:
  PASS-THROUGH  the feet ended below the slab's bottom (top + thickness) on a sample, i.e. the
                player went through it. THIS IS THE FAILURE.
  LANDED        grounded with the feet at or above `top` (on this floor, or on something a
                sensor caught above it).
  UNRESOLVED    neither within RUN_FRAMES (reported with the drop; counts as a failure too:
                a drop this witness cannot classify is not a pass).
  DEFLECTED     he went UP out of the drop (a spring or another object sitting on the floor
                launched him): reported with its count, not graded — an object, not the floor,
                decided it.
  NOT PLACED    the warp did not put him where asked (the clamp, or the act edge): reported,
                not graded.

EXIT: 0 at least one drop graded and none passed through or went unresolved; 1 a pass-through,
an unresolved drop, or a fault; 2 COULD NOT RUN (no target, the listing lacks a symbol, the
DEBUG warp mailbox is absent, or nothing could be placed).

CONTROL (it must be able to see a tunnel): on a ROM whose air move is ONE ObjectMove at any
speed — the base before feel/s3k-fall, whose cap only clamps y_vel AFTER the move, so a poked
y_vel moves the full distance once — the same drops pass through (measured in
docs/research/2026-09-27-s3k-fall.md; the red-first mutation is recorded there too).

Usage:
    thin_floor_witness.py --rom s4.debug.bin --lst s4.debug.lst
    thin_floor_witness.py ... --ladder            (adds the speed ladder)
    thin_floor_witness.py ... --targets 40 -v     (a quick look)
    thin_floor_witness.py ... --json out.json
"""

import argparse
import asyncio
import json
import pathlib
import re
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path                     # noqa: E402
add_client_path()
from aether_instance import aether_emulator                 # noqa: E402
from aether import BusClient                                # noqa: E402

EDITOR_ACT = REPO / "games" / "sonic4" / "data" / "editor" / "ojz" / "act1"
SHAPE_BANK = REPO / "games" / "sonic4" / "data" / "collision" / "base" / "heightmaps.bin"
SECTION_PX = 2048                     # section 0: 256 cells of 8 px across and down
NEED_SYMS = ("Player_1", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Logic_Tick")
NEED_EQUS = ("SST_x_pos", "SST_y_pos", "SST_x_vel", "SST_y_vel", "SST_layer", "SST_status",
             "_pl_state", "PSTATE_GROUND", "PSTATE_ROLL", "PSTATE_AIR", "PLAYER_Y_RADIUS",
             "PHYS_GRAVITY", "COLL_CELL_H", "LAYER_PATH_A", "LAYER_PATH_B", "ST_IN_AIR")
PLAYERV_DEBUG_FLAG = 0x3C             # PlayerV.debug_flag (an .emp struct field, no EQU line)
LADDER = (16, 24, 32, 48)             # px/frame: one cell, the air camera, two cells, three
LADDER_STRIDE = 8
RUN_FRAMES = 6
ACK_FRAMES = 120                      # a warp re-inits the ring: several frames of one tick
DMAX = 16                             # start heights d = 1..DMAX px above the floor
LEFT_BOUND = 16                       # player_common.emp PBOUND_LEFT_MARGIN (a file-local const)


def parse_lst(path):
    sym_re = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
    equ_re = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = sym_re.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = equ_re.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    missing = [n for n in NEED_SYMS if n not in syms] + [n for n in NEED_EQUS if n not in equs]
    return syms, equs, missing


def plane_columns(name):
    """{x: [bool]*SECTION_PX} floor-class solidity (SOL_TOP) and any-class solidity, per column,
    from the committed editor collision, sampled as the bake samples it."""
    import collision_pipeline as cp
    raw = (EDITOR_ACT / name).read_bytes()
    words = [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw), 2)]
    hm = SHAPE_BANK.read_bytes()
    n = cp.PROFILE_LEN
    floor, anyc = [], []
    for x in range(SECTION_PX):
        fcol, acol = [], []
        for y in range(SECTION_PX):
            w = words[(y // 16 * 2) * 256 + x // 8]
            shape = w & cp.BLOCK_ID_MASK
            sol = (w >> cp.PLANE_SOL_SHIFT) & 3
            if not shape or not sol:
                fcol.append(False)
                acol.append(False)
                continue
            h = hm[shape * n:(shape + 1) * n]
            if w & cp.CHUNK_XFLIP_BIT:
                h = cp.flip_profile_x(h)
            if w & cp.CHUNK_YFLIP_BIT:
                h = cp.flip_profile_y(h)
            c = cp.covers(h[x % 16], y % 16)
            acol.append(c)
            fcol.append(c and bool(sol & cp.SOL_TOP))
        floor.append(fcol)
        anyc.append(acol)
    return floor, anyc


def targets(cell, yr):
    """[(plane, x, top, thickness)] — see the header's TARGET."""
    clear = 2 * yr + 1 + DMAX
    planes = [plane_columns("section_0.collattr.bin"), plane_columns("section_0.collattrb.bin")]
    out, dropped = [], 0
    for p, (floor, anyc) in enumerate(planes):
        for x in range(SECTION_PX):
            if p == 1 and floor[x] == planes[0][0][x] and anyc[x] == planes[0][1][x]:
                continue                                  # plane B's column is plane A's
            if x < LEFT_BOUND:
                continue                                  # the warp clamps x to the act's bound
            col, acol = floor[x], anyc[x]
            y = 1
            while y < SECTION_PX:
                if col[y] and not col[y - 1]:
                    t = 0
                    while y + t < SECTION_PX and col[y + t]:
                        t += 1
                    if t <= cell:
                        if y >= clear and not any(acol[y - clear:y]):
                            out.append((p, x, y, t))
                        else:
                            dropped += 1
                    y += t
                else:
                    y += 1
    return out, dropped


def vmax_at(top, gravity):
    """y_vel (8.8) on the frame a fall from rest at y 0 first reaches `top` (move, then
    gravity: the old y_vel moves you, PState_AirShared step 4)."""
    y, v = 0, 0
    while True:
        ny = y + (v << 8)
        if (ny >> 16) >= top:
            return v
        y = ny
        v += gravity


async def drive(sock, syms, equs, jobs, verbose, progress):
    c = BusClient(socket_path=sock, client_id="tfw", client_name="thin-floor-witness")
    await c.connect()

    async def rd(addr, n):
        r = await c.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = r["bytes"]
        return bytes.fromhex(s[2:] if s[:2].lower() == "0x" else s)

    async def wr(addr, hexstr):
        await c.call("emulator/write_memory", {"addr": hex(addr & 0xFFFFFF), "bytes": "0x" + hexstr})

    async def frames(n):
        await c.call("emulator/run_frames", {"frames": n})

    async def alive(where):
        st = await c.call("emulator/status", {})
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            raise RuntimeError(f"the ROM FAULTED during {where}: symbolAtPc={sym!r}")

    P = syms["Player_1"]
    yr = equs["PLAYER_Y_RADIUS"]
    grounded = {equs["PSTATE_GROUND"], equs["PSTATE_ROLL"]}
    await c.call("emulator/reset", {})
    await frames(300)
    await alive("boot")
    if (await rd(P + PLAYERV_DEBUG_FLAG, 1))[0]:
        await c.call("emulator/press", {"buttons": ["b"]})       # a REAL press leaves free flight
        await frames(8)
    if (await rd(P + PLAYERV_DEBUG_FLAG, 1))[0]:
        raise RuntimeError("still in debug free flight after the B press")
    results = []
    t0 = time.time()
    for k, (p, x, top, t, v, d) in enumerate(jobs):
        cy = top - d - yr                                         # centre: feet d px above top
        await wr(syms["Warp_Req_X"], "%04x%04x01" % (x & 0xFFFF, cy & 0xFFFF))
        for _ in range(ACK_FRAMES):                               # the ack frame, and no later
            await frames(1)
            if not (await rd(syms["Warp_Req_Flag"], 1))[0]:
                break
        s = await rd(P, 0x40)
        px = int.from_bytes(s[equs["SST_x_pos"]:equs["SST_x_pos"] + 2], "big")
        py = int.from_bytes(s[equs["SST_y_pos"]:equs["SST_y_pos"] + 4], "big")
        flag = (await rd(syms["Warp_Req_Flag"], 1))[0]
        # The ack can land a tick early or late against the frame boundary, so the player may
        # have fallen for one tick at the warp's zero velocity: at most a pixel. More than that,
        # or a clamped X, is a placement the warp refused (the act edge), and is not graded.
        if flag or px != x or abs((py >> 16) - cy) > 1:
            results.append(dict(plane=p, x=x, top=top, t=t, v=v, d=d, grade="NOT PLACED",
                                at=[px, py >> 16, py & 0xFFFF, flag]))
            continue
        await wr(P + equs["SST_layer"], "%02x" % (equs["LAYER_PATH_A"] if p == 0 else equs["LAYER_PATH_B"]))
        # the exact start (y_pos with the subpixel cleared), x_vel 0 and y_vel v, in one write:
        # SST x_pos .l, y_pos .l, x_vel .w, y_vel .w are contiguous (checked in main)
        await wr(P + equs["SST_x_pos"], "%04x0000%04x0000%04x%04x" % (
            x & 0xFFFF, cy & 0xFFFF, 0, v & 0xFFFF))
        trace, grade = [], None
        for f in range(RUN_FRAMES):
            await frames(1)
            s = await rd(P, 0x40)
            y = int.from_bytes(s[equs["SST_y_pos"]:equs["SST_y_pos"] + 2], "big")
            y = y - 0x10000 if y & 0x8000 else y
            st = s[equs["_pl_state"]]
            feet = y + yr
            trace.append([y, st])
            if feet >= top + t:
                grade = "PASS-THROUGH"
                break
            if y < cy - 2:
                grade = "DEFLECTED"                               # launched upward: an object
                break
            if st in grounded:
                grade = "LANDED" if feet <= top else "LANDED LOW"
                break
        if grade is None:
            grade = "UNRESOLVED"
        results.append(dict(plane=p, x=x, top=top, t=t, v=v, d=d, grade=grade, trace=trace))
        if verbose and grade != "LANDED":
            print("  %-12s plane %s x %4d top %4d t %2d v %5.1f d %2d  %s" % (
                grade, "AB"[p], x, top, t, v / 256, d, trace), flush=True)
        if progress and (k + 1) % 2000 == 0:
            print("  ... %d/%d drops, %.0f s" % (k + 1, len(jobs), time.time() - t0), flush=True)
    await alive("the last drop")
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--ladder", action="store_true", help="add the speed ladder (every %dth target)" % LADDER_STRIDE)
    ap.add_argument("--targets", type=int, default=0, help="cap the target count (a quick look)")
    ap.add_argument("--json", help="write every drop here")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    syms, equs, missing = parse_lst(a.lst)
    if missing:
        print("thin_floor_witness: COULD NOT RUN: %s carries no %s (a DEBUG listing is needed: "
              "the warp mailbox is DEBUG-only)" % (a.lst, ", ".join(missing)))
        print("finished=2")
        return 2
    if not (equs["SST_y_pos"] == equs["SST_x_pos"] + 4 and equs["SST_x_vel"] == equs["SST_y_pos"] + 4
            and equs["SST_y_vel"] == equs["SST_x_vel"] + 2):
        print("thin_floor_witness: COULD NOT RUN: the SST no longer lays x_pos.l, y_pos.l, "
              "x_vel.w, y_vel.w out contiguously; the one-write placement would scatter")
        print("finished=2")
        return 2
    cell = equs["COLL_CELL_H"]
    tg, excluded = targets(cell, equs["PLAYER_Y_RADIUS"])
    if a.targets:
        tg = tg[:: max(1, len(tg) // a.targets)][:a.targets]
    if not tg:
        print("thin_floor_witness: COULD NOT RUN: no thin floor found in the editor collision")
        print("finished=2")
        return 2
    g = equs["PHYS_GRAVITY"]
    jobs = []
    for i, (p, x, top, t) in enumerate(tg):
        speeds = {vmax_at(top, g)}
        if a.ladder and i % LADDER_STRIDE == 0:
            speeds |= {r << 8 for r in LADDER}
        for v in sorted(speeds):
            for d in range(1, DMAX + 1):
                jobs.append((p, x, top, t, v, d))
    thick = {}
    for _, _, _, t in tg:
        thick[t] = thick.get(t, 0) + 1
    vms = [vmax_at(top, g) for _, _, top, _ in tg]
    print("thin_floor_witness: %s" % a.rom)
    print("  targets: %d floor columns <= %d px thick (plane A %d, plane B where it differs %d); "
          "%d thin surfaces excluded (no %d px of clear air above to start in)" % (
              len(tg), cell, sum(1 for q in tg if q[0] == 0), sum(1 for q in tg if q[0] == 1),
              excluded, 2 * equs["PLAYER_Y_RADIUS"] + 1 + DMAX))
    print("  thickness histogram: %s" % sorted(thick.items()))
    print("  vmax over targets: %.1f .. %.1f px/frame; %d drops (start heights 1..%d px)" % (
        min(vms) / 256, max(vms) / 256, len(jobs), DMAX))
    t0 = time.time()
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            res = asyncio.run(drive(sock, syms, equs, jobs, a.verbose, True))
    except RuntimeError as e:
        print("thin_floor_witness: FAILED: %s" % e)
        print("finished=1")
        return 1
    counts = {}
    for r in res:
        counts[r["grade"]] = counts.get(r["grade"], 0) + 1
    graded = sum(v for k, v in counts.items() if k not in ("NOT PLACED", "DEFLECTED"))
    bad = [r for r in res if r["grade"] in ("PASS-THROUGH", "UNRESOLVED")]
    print("  %.0f s; grades: %s" % (time.time() - t0, sorted(counts.items())))
    for r in bad[:40]:
        print("  %-12s plane %s x %4d top %4d t %2d v %5.1f d %2d trace %s" % (
            r["grade"], "AB"[r["plane"]], r["x"], r["top"], r["t"], r["v"] / 256, r["d"], r.get("trace")))
    if len(bad) > 40:
        print("  ... %d more" % (len(bad) - 40))
    if bad:
        by_t = {}
        for r in bad:
            by_t[r["t"]] = by_t.get(r["t"], 0) + 1
        print("  failures by floor thickness: %s" % sorted(by_t.items()))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(dict(rom=a.rom, counts=counts, drops=res)))
    if graded == 0:
        print("thin_floor_witness: COULD NOT RUN: no drop could be placed")
        rc = 2
    elif bad:
        print("thin_floor_witness: FAILED: %d of %d graded drops passed through or went "
              "unresolved" % (len(bad), graded))
        rc = 1
    else:
        print("thin_floor_witness: OK: %d graded drops, 0 passed through" % graded)
        rc = 0
    print("finished=%d" % rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
