#!/usr/bin/env python3
"""spring_clip_ab — WHAT IS STILL HAPPENING at a side-facing spring, A/B across two ROMs.

THIS IS A MEASUREMENT, NOT A GATE. It has no pass/fail verdict about whether
`parcel/solid-touch-reach` should be kept, because the open question is a LOOK call and
nothing here can answer it. What it does is replace "looks a little better but still have
this effect" with numbers: exactly which pixel band around a side spring produces a
launch, exactly which band produces nothing, and exactly what the player's sprite is
doing across that band -- separately for a STANDING and a CURLED player, on each build.

THE THREE INSTRUMENTS, and why each exists.

  A. CONTACT BAND SWEEP (the A/B that matters).
     The engine's object AABB is `2*|dx| < player_w + object_w` (engine/objects/aabb.emp).
     Under master the player's contribution is his LIVE `width_pixels` -- 19 standing, 15
     curled. Under the branch it is the constant SOLID_TOUCH_W = 2*PUSH_RADIUS+1 = 21 for
     the SOLID family regardless of state. That predicts three different bands, so the
     sweep MEASURES the band rather than computing it: seat the player at every dx from
     far outside to deep inside, step ONE frame, and record whether the spring fired.
     A stationary player is a legitimate subject here -- Touch_Spring's side arm tests
     only the sign agreement of delta_x with the spring's x_vel, never the player's speed
     -- and it removes approach speed as a variable, which a walk-in cannot.

     THE CURLED HALF IS A POKE AND IT IS THE HONEST ONE. `width_pixels`/`height_pixels`
     are the fields the collision test reads, and TouchResponse runs BEFORE the player's
     own tick, so a poked box is the box the test sees on the very next frame. The poke
     is read back and asserted. Under the branch the poke is IGNORED for solids by
     design, and that is the result, not a broken instrument.

  B. SPRITE EXTENTS (what turns a pixel band into a look).
     A band in world coordinates says nothing about "visibly touching" until you know
     where the pixels are. This reads the live VDP sprite table and reports the drawn
     left/right edges of the spring and of the player relative to their SST centres, so
     the band can be stated as "N px of DRAWN OVERLAP with no reaction" rather than as an
     abstract coordinate.

  C. WALK-IN and ROLL-IN TRACES (verify DURING motion).
     The band sweep is a static probe and static probes hide exactly the artefacts an
     owner notices: a one-frame position snap, a re-fire, a frame of penetration. So each
     build also gets a per-frame table of a real approach -- walking, and rolling (which
     is the state the branch is explicitly about) -- with the per-frame position delta
     compared against the velocity that could have produced it. A |dx| step larger than
     the velocity allows is a DISCONTINUITY and is flagged.

WHAT THIS FILE DELIBERATELY DOES NOT DO: recommend keeping or reverting the branch.

Usage:
    python3 tools/spring_clip_ab.py --rom A.bin --lst A.lst --label master
    python3 tools/spring_clip_ab.py --json out.json ...      # machine-readable dump
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, write_bytes  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402
from spring_launch_witness import parse_equs, s16  # noqa: E402

BOOT_FRAMES = 60
SETTLE_FRAMES = 300      # spawn is ~900px above the floor
SEAT_SETTLE = 90         # land on the floor and come to rest
SWEEP_FAR = 46           # px from the spring's centre the sweep starts
SWEEP_NEAR = 6           # ...and ends
WALK_START_DX = 60       # px out the walk/roll approach starts
TRACE_FRAMES = 90
ROLL_SEED_GSP = 0x500     # the ground speed the roll leg SEEDS before pressing DOWN.
                          # A walked-up roll cannot be made to happen here and that was
                          # measured twice: from a 60px start the player accelerates at
                          # PHYS_ACCEL ($C/frame) and is still at $204 when he reaches the
                          # spring on frame 43, so a trigger at $400 fired on frame 44 --
                          # one frame AFTER the launch -- and the leg reported "ball box
                          # worn: True" from a player who curled in mid-air on the way
                          # out. Seeding the speed is the only way this act's geometry
                          # admits a genuinely ROLLING approach, and the box actually
                          # worn on the last pre-launch frame is reported rather than
                          # inferred from the button press.


class Unmeasurable(RuntimeError):
    pass


# ------------------------------------------------------------------ machine access

class Probe:
    def __init__(self, b, sym, equ):
        self.b, self.sym, self.equ = b, sym, equ
        self.player = sym["Player_1"]
        # The two VRAM tile windows sprite attribution is derived from, straight out of
        # the listing (see `attribute`). Required, not defaulted: a build that stops
        # publishing them is a build this file cannot ask its question about.
        self.vram = dict(s_lo=equ["VRAM_SPRING"],
                         s_hi=equ["VRAM_SPRING"] + equ["VRAM_SPRING_TILES"],
                         p_lo=equ["VRAM_TEST_SONIC"],
                         p_hi=equ["VRAM_TEST_SONIC"] + equ["VRAM_TEST_SONIC_TILES"])

    async def rd(self, addr, n):
        return await read_bytes(self.b, addr, n)

    async def byte(self, addr):
        return int(await self.rd(addr, 1), 16)

    async def word(self, addr):
        return int(await self.rd(addr, 2), 16)

    async def sword(self, addr):
        return s16(await self.word(addr))

    async def frames(self, n=1):
        await self.b.call("emulator/run_frames", {"frames": n})

    async def hold(self, buttons, down):
        await self.b.call("emulator/hold", {"buttons": list(buttons), "down": bool(down)})

    async def sst(self, base):
        e = self.equ
        return dict(
            x=await self.sword(base + e["SST_x_pos"]),
            y=await self.sword(base + e["SST_y_pos"]),
            xsub=await self.word(base + e["SST_x_pos"] + 2),
            xv=await self.sword(base + e["SST_x_vel"]),
            yv=await self.sword(base + e["SST_y_vel"]),
            w=await self.byte(base + e["SST_width_pixels"]),
            h=await self.byte(base + e["SST_height_pixels"]),
            status=await self.byte(base + e["SST_status"]),
            anim=await self.byte(base + e["SST_anim"]),
            sub=await self.byte(base + e["SST_subtype"]),
        )

    async def player_state(self):
        st = await self.sst(self.player)
        st["gsp"] = await self.sword(self.player + self.equ["_pl_gsp"])
        st["air"] = (st["status"] >> self.equ["ST_IN_AIR"]) & 1
        st["onobj"] = (st["status"] >> self.equ["ST_ON_OBJECT"]) & 1
        return st

    async def put_player(self, x=None, y=None, xv=None, yv=None, gsp=None, wh=None):
        e = self.equ
        if x is not None:
            await write_bytes(self.b, self.player + e["SST_x_pos"], f"{x & 0xFFFF:04X}0000")
        if y is not None:
            await write_bytes(self.b, self.player + e["SST_y_pos"], f"{y & 0xFFFF:04X}0000")
        if xv is not None:
            await write_bytes(self.b, self.player + e["SST_x_vel"], f"{xv & 0xFFFF:04X}")
        if yv is not None:
            await write_bytes(self.b, self.player + e["SST_y_vel"], f"{yv & 0xFFFF:04X}")
        if gsp is not None:
            await write_bytes(self.b, self.player + e["_pl_gsp"], f"{gsp & 0xFFFF:04X}")
        if wh is not None:
            # width_pixels and height_pixels are adjacent (size_wh_off) -- one word store,
            # which is what the game's own set_ball_size does.
            await write_bytes(self.b, self.player + e["SST_width_pixels"],
                              f"{wh[0] & 0xFF:02X}{wh[1] & 0xFF:02X}")

    async def objects(self, code_word):
        """Every LIVE dynamic slot dispatching to `code_word` -- the walk TouchResponse does."""
        n = await self.word(self.sym["Dynamic_Live_Count"])
        out = []
        for i in range(n):
            ent = await self.word(self.sym["Dynamic_Live"] + 2 * i)
            if not ent:
                continue
            base = 0xFF0000 | ent
            if await self.word(base + self.equ["SST_code_addr"]) != code_word:
                continue
            st = await self.sst(base)
            st["sst"] = base
            out.append(st)
        return out

    async def sprites(self):
        try:
            return await self.b.call("emulator/sprites", {})
        except Exception as exc:                      # noqa: BLE001
            return {"error": str(exc)}


async def boot(pr, spring_code, note):
    """Reset, LEAVE DEBUG-FLY, and let him fall to the floor.

    s4.debug.bin boots into free flight (CHEAT_DEBUG_FLY -> Player_DebugEnter suspends the
    state dispatch), and a run that skips this step measures a floating statue: measured
    here first, the player sat at (256,256) with y_vel 0 for 450 frames and every seat
    poke stayed exactly where it was put. B is the real exit path. The fall is tested
    FIRST so a build with the cheat clear does not get a buffered jump instead.
    """
    await pr.b.call("emulator/reset", {})
    await pr.frames(BOOT_FRAMES)
    placed = (await pr.player_state())["y"]
    if placed == 0:
        raise Unmeasurable(f"player slot still all-zero after {BOOT_FRAMES} frames")
    await pr.frames(8)
    after = (await pr.player_state())["y"]
    if after == placed:
        await pr.b.call("emulator/press", {"buttons": ["b"]})
        await pr.frames(8)
        moved = (await pr.player_state())["y"]
        if moved == after:
            raise Unmeasurable(f"player still frozen at y={moved} after a B press — "
                               f"nothing in this run would be physics")
        note.append(f"  left debug-fly with B: y {after} -> {moved}")
    else:
        note.append(f"  already falling ({placed} -> {after}) — no debug-fly to leave")
    await pr.frames(SETTLE_FRAMES)
    objs = await pr.objects(spring_code)
    if not objs:
        raise Unmeasurable("no live spring object after the settle")
    note.append(f"  live springs after settle: " + ", ".join(
        f"(x={o['x']},y={o['y']} box {o['w']}x{o['h']} sub=${o['sub']:02X} "
        f"vec=({o['xv']},{o['yv']}))" for o in objs))
    return objs


def pick_side_spring(objs):
    side = [o for o in objs if o["xv"] != 0]
    if not side:
        raise Unmeasurable("no live SIDE-facing spring (x_vel != 0) in this act")
    return side[0]


async def seat(pr, x, y, note, what, wh=None, want_grounded=True):
    """Poke a position, let PHYSICS settle it, and assert the result."""
    await pr.put_player(x=x, y=y, xv=0, yv=0, gsp=0)
    got = await pr.player_state()
    if got["x"] != x or got["y"] != y:
        raise Unmeasurable(f"{what}: seat poke did not take -- asked ({x},{y}), read "
                           f"({got['x']},{got['y']})")
    await pr.frames(SEAT_SETTLE)
    st = await pr.player_state()
    if want_grounded and st["air"]:
        raise Unmeasurable(f"{what}: still AIRBORNE after {SEAT_SETTLE} frames at "
                           f"({st['x']},{st['y']}) -- no floor under that seat")
    if wh is not None:
        await pr.put_player(wh=wh)
        st = await pr.player_state()
        if (st["w"], st["h"]) != wh:
            raise Unmeasurable(f"{what}: box poke did not take -- asked {wh}, read "
                               f"({st['w']},{st['h']})")
    return st


# ------------------------------------------------------------------ A: contact band

async def band_sweep(pr, spring, ground_y, wh, tag, note):
    """For every dx on the launching side: does ONE frame produce a launch?

    Returns the list of (dx, launched, resulting x_vel, resulting player x).
    The sweep goes OUTSIDE-IN and re-seats between samples, so no sample inherits the
    previous one's state.
    """
    side = 1 if spring["xv"] > 0 else -1        # the face the spring throws from
    rows = []
    for d in range(SWEEP_FAR, SWEEP_NEAR - 1, -1):
        x = spring["x"] + side * d
        await pr.put_player(x=x, y=ground_y, xv=0, yv=0, gsp=0)
        if wh is not None:
            await pr.put_player(wh=wh)
        pre = await pr.player_state()
        if pre["x"] != x or (wh is not None and (pre["w"], pre["h"]) != wh):
            raise Unmeasurable(f"{tag}: sample dx={d} did not seat "
                               f"(x={pre['x']} box {pre['w']}x{pre['h']})")
        await pr.frames(1)
        post = await pr.player_state()
        launched = launched_by(spring, post["xv"])
        rows.append(dict(dx=d, launched=bool(launched), xv=post["xv"], gsp=post["gsp"],
                         x=post["x"], y=post["y"], w=pre["w"], h=pre["h"],
                         moved=post["x"] - x))
    hits = [r["dx"] for r in rows if r["launched"]]
    outer = max(hits) if hits else None
    # A CONTIGUITY CHECK, because a band with a hole in it is a different finding from a
    # band that is merely narrow, and a summary that reported only the outer edge would
    # not distinguish them.
    holes = []
    if hits:
        for d in range(min(hits), max(hits) + 1):
            if d not in hits:
                holes.append(d)
    note.append(f"  {tag}: box {rows[0]['w']}x{rows[0]['h']}, launching side "
                f"{'+' if side > 0 else '-'} -- launch fires for |dx| <= "
                f"{outer if outer is not None else 'NEVER'}"
                + (f", HOLES at {holes}" if holes else ""))
    return dict(side=side, rows=rows, outer=outer, holes=holes,
                w=rows[0]["w"], h=rows[0]["h"])


# ------------------------------------------------------------------ B: sprite extents

def launched_by(spring, xv):
    """Did the SIDE LAUNCH fire, as opposed to the solid push or nothing?

    NOT `xv == spring.x_vel`. That was this file's first detector and it under-counted:
    the standing sweep read -4084 against a -4096 spring and reported NEVER LAUNCHED for
    every dx, because one tick of the game's own deceleration lands between the impulse
    and the frame boundary the sample is taken at. The launch and its two alternatives are
    still unambiguous -- the solid push CLEARS x_vel and never sets it, and a seated
    player has none -- so the discriminator is direction plus a magnitude far above any
    walking speed (PHYS_TOP_SPEED is $600 against a $1000 launch).
    """
    if xv == 0 or spring["xv"] == 0:
        return False
    return (xv < 0) == (spring["xv"] < 0) and abs(xv) >= abs(spring["xv"]) // 2


async def sprite_rows(pr):
    """The visible sprites, in SCREEN pixels.

    THE SERVER ALREADY REMOVES THE VDP'S $80 BIAS. This file subtracted it a second time
    at first, which put every sprite 128px to the left of where it is drawn and made the
    whole attribution step return "spring: 0 pieces" while looking like it had run.
    Measured on the control ROM: player world x=406 with Camera_X=246 (screen 160) drew at
    reported x 142..173, and the side spring at world 360 (screen 114) drew at 106..121 --
    both correct as reported, both nonsense with a second subtraction.
    """
    r = await pr.b.call("emulator/sprites", {})
    out = []
    for s in r.get("sprites") or []:
        if s.get("widthCells") is None:
            continue
        left, top = s["x"], s["y"]
        right = left + s["widthCells"] * 8 - 1
        bot = top + s["heightCells"] * 8 - 1
        if right < 0 or left > 320 or bot < 0 or top > 240:
            continue                       # parked / offscreen rows
        out.append(dict(left=left, right=right, top=top, bot=bot,
                        tile=s.get("baseTile"), pri=s.get("priority"),
                        hflip=s.get("hflip"), vflip=s.get("vflip")))
    return out


def attribute(rows, psx, ssx, vram, sreach=24):
    """Split drawn sprites between the player and the spring by VRAM TILE RANGE.

    NOT BY NEAREST CENTRE, and not by a learned tile set. Both of those were tried here
    and both are measurably wrong:

      nearest centre    at dx=-22 it started handing the player's leading piece to the
                        spring, and the spring's "drawn" span drifted -8..+7 -> -14..+7
                        -> -12..+7 -> -10..+7 over three frames of an object that never
                        moved. Every close-range number built on it is an artefact.
      a learned tile set the player's art is DPLC'd, so his RUNNING frames draw from tiles
                        his IDLE frame did not. Learning the set at a clean separation
                        silently dropped his leading arm piece and understated his reach
                        by 8px -- measured against `object_at`, which put a player-owned
                        dot at screen 170..177 that the tile-set rule had discarded.

    The listing publishes both regions, so the rule is derived rather than guessed:
    VRAM_SPRING (24 tiles) is the spring sheet and VRAM_TEST_SONIC (32 tiles) is the
    player's DPLC window. A piece's `baseTile` therefore names its owner exactly. The
    spring range additionally has to be NEAR the subject spring, because the act places
    six springs and they all draw from the same 24 tiles.
    """
    per = {"player": [], "spring": []}
    for q in rows:
        t = q["tile"]
        mid = (q["left"] + q["right"]) / 2
        if vram["s_lo"] <= t < vram["s_hi"]:
            if abs(mid - ssx) <= sreach:
                per["spring"].append(q)
        elif vram["p_lo"] <= t < vram["p_hi"]:
            per["player"].append(q)
    return per


def decode_tile_columns(raw: bytes, wcells: int, hcells: int, hflip: bool):
    """Which of a sprite piece's 8*wcells pixel columns contain ANY non-transparent pixel.

    THIS IS THE DIFFERENCE BETWEEN A SPRITE AND WHAT YOU SEE. A sprite piece's frame is
    whole 8px cells and is padded with colour 0 to reach them; the owner sees the INK, not
    the frame. Sonic's standing frame reports 32px of sprite against a 19px collision box,
    and how much of that 13px surplus is actually drawn is the whole question.

    Genesis 4bpp, one tile = 32 bytes = 8 rows of 4 bytes, high nibble = the LEFT pixel;
    a piece's tiles run COLUMN-MAJOR (down a column of cells, then the next column).
    """
    cols = set()
    for c in range(wcells):
        for r in range(hcells):
            base = (c * hcells + r) * 32
            tile = raw[base:base + 32]
            if len(tile) < 32:
                continue
            for row in range(8):
                for byte_i in range(4):
                    v = tile[row * 4 + byte_i]
                    if v >> 4:
                        cols.add(c * 8 + byte_i * 2)
                    if v & 0xF:
                        cols.add(c * 8 + byte_i * 2 + 1)
    if hflip:
        span = wcells * 8
        cols = {span - 1 - x for x in cols}
    return cols


async def ink_span(pr, pieces, centre):
    """The leftmost/rightmost INKED screen column of a set of sprite pieces, centre-relative.

    Reads each piece's tiles out of VRAM and keeps only the columns that actually draw.
    """
    lo, hi = None, None
    for q in pieces:
        w = (q["right"] - q["left"] + 1) // 8
        h = (q["bot"] - q["top"] + 1) // 8
        n = w * h * 32
        if n == 0 or n > 4096:
            continue
        r = await pr.b.call("emulator/read_vram", {"addr": hex(q["tile"] * 32), "len": n})
        raw = bytes.fromhex(str(r["bytes"]).removeprefix("0x"))
        cols = decode_tile_columns(raw, w, h, bool(q.get("hflip")))
        for c in cols:
            sx = q["left"] + c
            lo = sx if lo is None else min(lo, sx)
            hi = sx if hi is None else max(hi, sx)
    if lo is None:
        return None
    return dict(left_rel=lo - centre, right_rel=hi - centre, width=hi - lo + 1)


def span_of(rows, centre):
    if not rows:
        return None
    lo = min(q["left"] for q in rows)
    hi = max(q["right"] for q in rows)
    return dict(left_rel=lo - centre, right_rel=hi - centre, width=hi - lo + 1,
                pieces=len(rows))


async def drawn_extents(pr, spring, note, tag):
    """WHERE THE PIXELS ARE, relative to each object's SST centre.

    A contact band in world coordinates says nothing about "visibly touching" until you
    know how wide each thing is DRAWN. The collision boxes are 19 (standing player) and 16
    (side spring); the sprites are whatever the mappings say, and the gap between the two
    is the whole of what an owner can see.

    Reads the live VDP sprite table (`x`/`y` carry the VDP's $80 bias; `widthCells` is
    1..4 cells of 8px) and attributes each sprite to whichever of the two centres is
    nearer in SCREEN x, so the answer needs no knowledge of the mappings at all.

    THE ATTRIBUTION IS ASSERTED, not assumed: the player and the spring are seated far
    enough apart (46px) that a mis-attribution would have to cross a 23px midline, and the
    per-object extents are returned so a nonsense value is visible rather than folded into
    a summary.
    """
    camx = await pr.word(pr.sym["Camera_X"])
    p = await pr.player_state()
    psx, ssx = p["x"] - camx, spring["x"] - camx
    if not (0 <= psx <= 320 and 0 <= ssx <= 320):
        note.append(f"  {tag}: BLOCKED — Camera_X {camx} puts player at screen {psx} and "
                    f"spring at {ssx}; one of them is off screen, so nothing is drawn to "
                    f"measure")
        return None
    rows = await sprite_rows(pr)
    per = attribute(rows, psx, ssx, pr.vram)
    out = dict(camera_x=camx, player_screen_x=psx, spring_screen_x=ssx,
               frame_player=span_of(per["player"], psx),
               frame_spring=span_of(per["spring"], ssx),
               player_box_w=p["w"], spring_box_w=spring["w"], anim=p["anim"],
               tiles_player=sorted({q["tile"] for q in per["player"]}),
               tiles_spring=sorted({q["tile"] for q in per["spring"]}))
    out["ink_player"] = await ink_span(pr, per["player"], psx)
    out["ink_spring"] = await ink_span(pr, per["spring"], ssx)
    if not (out["frame_player"] and out["frame_spring"]):
        note.append(f"  {tag}: BLOCKED — attribution found "
                    f"player={len(per['player'])} spring={len(per['spring'])} pieces")
        return out
    side = 1 if spring["xv"] > 0 else -1

    def touch_dx(pl, sp):
        if not (pl and sp):
            return None
        return (-pl["left_rel"] + sp["right_rel"]) if side > 0 else \
               (pl["right_rel"] - sp["left_rel"])

    out["frame_touch_dx"] = touch_dx(out["frame_player"], out["frame_spring"])
    out["ink_touch_dx"] = touch_dx(out["ink_player"], out["ink_spring"])
    fp, fs, ip, isp = (out["frame_player"], out["frame_spring"],
                       out["ink_player"], out["ink_spring"])
    note.append(
        f"  {tag}: anim {p['anim']} — player SPRITE FRAME {fp['left_rel']:+d}.."
        f"{fp['right_rel']:+d} ({fp['width']}px, {fp['pieces']} pieces) but INKED "
        f"{ip['left_rel']:+d}..{ip['right_rel']:+d} ({ip['width']}px) against a "
        f"{p['w']}px collision box; spring frame {fs['left_rel']:+d}..{fs['right_rel']:+d} "
        f"({fs['width']}px) inked {isp['left_rel']:+d}..{isp['right_rel']:+d} "
        f"({isp['width']}px) against a {spring['w']}px box. "
        f"VISIBLE PIXELS FIRST TOUCH at |dx| = {out['ink_touch_dx']} "
        f"(sprite frames at {out['frame_touch_dx']})")
    return out


# ------------------------------------------------------------------ C: motion traces

async def trace_approach(pr, spring, ground_y, roll, tag, note,
                         start_dx=WALK_START_DX):
    """Walk (or roll) into the spring's launching face and table every frame.

    THE ROLL THRESHOLD WAS A CONFOUND AND THIS IS THE FIX. The first version pressed DOWN
    once |ground_speed| passed $300, and measured that it first does so on frame 44 -- one
    frame AFTER the launch on frame 43. So the roll leg never rolled, and its table came
    out byte-identical to the walk's on both builds. A reader would have concluded the
    branch changes nothing for a curled player, from a run in which no player ever curled.
    DOWN now goes down at $100, and whether the ball box was ever actually worn is
    RETURNED and asserted by the caller rather than assumed from the button press.
    """
    side = 1 if spring["xv"] > 0 else -1
    button = "right" if side < 0 else "left"
    start = spring["x"] + side * start_dx
    st = await seat(pr, start, ground_y, note, tag)
    stand_w = st["w"]
    rows = []
    rolled_at, ever_curled = None, False
    if roll:
        # THE DIRECTION MUST BE OFF WHEN DOWN GOES DOWN. player_ground.emp's roll gate is
        # "down held, L/R NOT held (raw bits -- any sideways intent vetoes the curl)", so
        # the first version of this leg added DOWN to a held direction and could never
        # curl at all while reporting itself as the curled case.
        # side < 0 = he stands to the spring's LEFT and travels +x toward it.
        await pr.put_player(gsp=ROLL_SEED_GSP if side < 0 else -ROLL_SEED_GSP)
        await pr.hold(["down"], True)
        rolled_at = 0
    else:
        await pr.hold([button], True)
    try:
        for f in range(TRACE_FRAMES):
            await pr.frames(1)
            prev = st
            st = await pr.player_state()
            dx = st["x"] - spring["x"]
            half_w = (st["w"] + spring["w"]) // 2
            half_h = (st["h"] + spring["h"]) // 2
            dy = st["y"] - spring["y"]
            pen_x = half_w - abs(dx)
            pen_y = half_h - abs(dy)
            step = st["x"] - prev["x"]
            # THE DISCONTINUITY TEST. x_vel is 8.8 fixed point, so a frame's honest
            # travel is at most ceil(|x_vel|/256)+1 px (the +1 covers the subpixel carry).
            allowed = (max(abs(prev["xv"]), abs(st["xv"])) + 255) // 256 + 1
            row = dict(f=f, x=st["x"], y=st["y"], xv=st["xv"], yv=st["yv"],
                       gsp=st["gsp"], w=st["w"], h=st["h"], anim=st["anim"],
                       air=st["air"], onobj=st["onobj"], dx=dx, dy=dy,
                       pen_x=pen_x, pen_y=pen_y, overlap=bool(pen_x > 0 and pen_y > 0),
                       step=step, allowed=allowed,
                       jump=abs(step) - allowed if abs(step) > allowed else 0,
                       spring_anim=await pr.byte(spring["sst"] + pr.equ["SST_anim"]))
            # THE DRAWN EDGES, on the frames where they can matter. The whole question is
            # whether the pixels touch before the boxes do, so the table carries the
            # drawn gap beside the box gap rather than leaving it to be inferred.
            if st["w"] != stand_w:
                ever_curled = True
            if abs(dx) <= 44:
                camx = await pr.word(pr.sym["Camera_X"])
                psx, ssx = st["x"] - camx, spring["x"] - camx
                if 0 <= psx <= 320 and 0 <= ssx <= 320:
                    per = attribute(await sprite_rows(pr), psx, ssx, pr.vram)
                    ps = await ink_span(pr, per["player"], psx)
                    ss = await ink_span(pr, per["spring"], ssx)
                    if ps and ss:
                        row["ink_p"] = [ps["left_rel"], ps["right_rel"]]
                        row["ink_s"] = [ss["left_rel"], ss["right_rel"]]
                        # THE NUMBER OF SCREEN COLUMNS THE TWO SILHOUETTES SHARE.
                        # Approaching from the LEFT, the player's rightmost drawn column
                        # is at screen (x + pr) and the spring's leftmost at (S + sl), so
                        # they share (x + pr) - (S + sl) + 1 = dx + pr - sl + 1 columns.
                        # THE +1 IS NOT COSMETIC: without it "0" meant one shared column
                        # and "-1" meant abutting, and every count in the report would
                        # have been one pixel optimistic. 0 now means a clean 1px gap.
                        row["ink_overlap"] = 1 + (
                            dx + ps["right_rel"] - ss["left_rel"] if side < 0
                            else -dx + ss["right_rel"] - ps["left_rel"])
            rows.append(row)
            if launched_by(spring, st["xv"]):
                # launched -- keep sampling a few more frames to see the departure
                if sum(1 for r in rows if launched_by(spring, r["xv"])) >= 6:
                    break
    finally:
        await pr.hold([button, "down"], False)
    over = [r for r in rows if r["overlap"]]
    jumps = [r for r in rows if r["jump"] > 0]
    li = next((i for i, r in enumerate(rows) if launched_by(spring, r["xv"])), None)
    launch = rows[li] if li is not None else None
    # The launch row's own dx is already 16px AWAY -- the impulse moved him before the
    # frame boundary this samples at. The dx that made contact is the previous row's.
    contact = rows[li - 1] if li else None
    # THE NUMBER THE OWNER CAN SEE: how many frames he spends with the two INKED
    # silhouettes already overlapping and nothing having happened yet.
    blind = [r for r in rows if r.get("ink_overlap", -99) > 0
             and (launch is None or r["f"] < launch["f"])]
    note.append(
        f"  {tag}: {len(rows)} frames, start dx {start_dx}"
        + (f", DOWN pressed frame {rolled_at}, ball box worn: {ever_curled}" if roll else "")
        + f"; {len(over)} with AABB overlap"
        + (f" (deepest pen_x {max(r['pen_x'] for r in over)}px)" if over else "")
        + (f"; launch on frame {launch['f']}, last pre-launch frame dx="
           f"{contact['dx'] if contact else '?'} box "
           f"{contact['w'] if contact else '?'}x{contact['h'] if contact else '?'}"
           f" inked overlap {contact.get('ink_overlap') if contact else '?'}"
           if launch else "; NO LAUNCH")
        + (f"; {len(blind)} frame(s) of VISIBLE CONTACT WITH NO REACTION, deepest "
           f"{max(r['ink_overlap'] for r in blind)}px of inked overlap" if blind
           else "; no frame of visible-contact-without-reaction")
        + (f"; {len(jumps)} DISCONTINUITIES, largest "
           f"{max((r['step'] for r in jumps), key=abs)}px" if jumps
           else "; no position discontinuity"))
    return dict(rows=rows, rolled_at=rolled_at, ever_curled=ever_curled,
                launch_frame=launch["f"] if launch else None,
                contact_dx=contact["dx"] if contact else None,
                contact_box=[contact["w"], contact["h"]] if contact else None,
                contact_ink_overlap=contact.get("ink_overlap") if contact else None,
                blind_frames=len(blind), start_dx=start_dx)


# ------------------------------------------------------------------ driver

async def run(sock, lst, label, note):
    b = BusClient(socket_path=sock, client_id="clipab", client_name="spring_clip_ab")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym, equ = parse_lst(lst), parse_equs(lst)
    for need in ("Player_1", "Dynamic_Live", "Dynamic_Live_Count", "Spring_Main",
                 "ObjCodeBase"):
        if need not in sym:
            raise Unmeasurable(f"{need} absent from {lst}")
    for need in ("SST_x_pos", "SST_y_pos", "SST_x_vel", "SST_y_vel", "SST_status",
                 "SST_code_addr", "SST_width_pixels", "SST_height_pixels", "SST_anim",
                 "SST_subtype", "_pl_gsp", "ST_IN_AIR", "ST_ON_OBJECT",
                 "PLAYER_X_RADIUS", "BALL_X_RADIUS", "PUSH_RADIUS",
                 "VRAM_SPRING", "VRAM_SPRING_TILES", "VRAM_TEST_SONIC",
                 "VRAM_TEST_SONIC_TILES"):
        if need not in equ:
            raise Unmeasurable(f"{need} has no EQU in {lst}")

    pr = Probe(b, sym, equ)
    spring_code = (sym["Spring_Main"] - sym["ObjCodeBase"]) & 0xFFFF
    stand_wh = (2 * equ["PLAYER_X_RADIUS"] + 1, None)
    ball_wh = (2 * equ["BALL_X_RADIUS"] + 1, None)
    solid_touch = equ.get("SOLID_TOUCH_W")
    note.append(f"[{label}] PLAYER_X_RADIUS={equ['PLAYER_X_RADIUS']} "
                f"BALL_X_RADIUS={equ['BALL_X_RADIUS']} PUSH_RADIUS={equ['PUSH_RADIUS']}; "
                f"SOLID_TOUCH_W={'ABSENT (control build)' if solid_touch is None else solid_touch}")

    result = dict(label=label, lst=lst, solid_touch_w=solid_touch,
                  radii=dict(stand=equ["PLAYER_X_RADIUS"], ball=equ["BALL_X_RADIUS"],
                             push=equ["PUSH_RADIUS"]))

    # ---- boot 1: geometry + the two band sweeps
    objs = await boot(pr, spring_code, note)
    spring = pick_side_spring(objs)
    result["spring"] = {k: spring[k] for k in ("x", "y", "w", "h", "xv", "yv", "sub")}
    side = 1 if spring["xv"] > 0 else -1
    st = await seat(pr, spring["x"] + side * WALK_START_DX, spring["y"] - 20, note, "seat")
    ground_y = st["y"]
    result["ground_y"] = ground_y
    stand_w, stand_h = st["w"], st["h"]
    note.append(f"  [{label}] side spring at (x={spring['x']},y={spring['y']}) box "
                f"{spring['w']}x{spring['h']} launch vector ({spring['xv']},{spring['yv']}); "
                f"player rests at y={ground_y} with the standing box {stand_w}x{stand_h}")

    # the curled box, taken from the game's own record rather than written here
    ball_w = 2 * equ["BALL_X_RADIUS"] + 1
    ball_h = stand_h - 10 if stand_h > 10 else stand_h     # reported, asserted below
    result["stand_box"] = [stand_w, stand_h]

    # ---- B FIRST: drawn extents, with the box the game itself put there.
    # BEFORE the sweeps, deliberately: the curled sweep POKES width_pixels, and a drawn
    # measurement taken after it would report the poked box beside the standing sprite.
    await pr.put_player(x=spring["x"] + side * 46, y=ground_y, xv=0, yv=0, gsp=0)
    await pr.frames(2)
    result["drawn_standing"] = await drawn_extents(pr, spring, note,
                                                   f"[{label}] DRAWN standing")

    result["band_standing"] = await band_sweep(pr, spring, ground_y, None,
                                               f"[{label}] STANDING", note)
    result["band_curled"] = await band_sweep(pr, spring, ground_y, (ball_w, ball_h),
                                             f"[{label}] CURLED (box poked to "
                                             f"{ball_w}x{ball_h})", note)

    # ---- C: the motion traces.
    # TWO START OFFSETS PER APPROACH, ONE PIXEL APART, and that is not padding. A walking
    # player covers 2px on the frames that matter, so a single approach samples only every
    # other dx and CANNOT resolve a 1px change in the contact band: measured, master and
    # branch launched on the identical frame at the identical dx=-16 because dx=-17 was
    # never visited. The odd/even pair visits both parities.
    for phase in (0, 1):
        objs = await boot(pr, spring_code, note)
        spring = pick_side_spring(objs)
        result[f"trace_walk_{phase}"] = await trace_approach(
            pr, spring, ground_y, False, f"[{label}] WALK-IN phase {phase}", note,
            WALK_START_DX + phase)
    for phase in (0, 1):
        objs = await boot(pr, spring_code, note)
        spring = pick_side_spring(objs)
        result[f"trace_roll_{phase}"] = await trace_approach(
            pr, spring, ground_y, True, f"[{label}] ROLL-IN phase {phase}", note,
            WALK_START_DX + phase)
        if not result[f"trace_roll_{phase}"]["ever_curled"]:
            note.append(f"  [{label}] ROLL-IN phase {phase}: WARNING — the ball box was "
                        f"never worn, so this leg measured a WALK and says nothing about "
                        f"the curled case")

    await b.close()
    return result


def compare(pa, pb):
    """Print the A/B table from two --json dumps. Reports only what both runs measured."""
    A, B = json.loads(Path(pa).read_text()), json.loads(Path(pb).read_text())
    out = []
    out.append(f"A = {A['label']}  (SOLID_TOUCH_W = {A['solid_touch_w'] or 'absent'})")
    out.append(f"B = {B['label']}  (SOLID_TOUCH_W = {B['solid_touch_w'] or 'absent'})")
    sp = A["spring"]
    out.append(f"subject: side spring at world ({sp['x']},{sp['y']}), collision box "
               f"{sp['w']}x{sp['h']}, launch vector ({sp['xv']},{sp['yv']}); the player "
               f"approaches its launching face on the floor at y={A['ground_y']}")
    d = A["drawn_standing"]
    out.append(f"drawn geometry (identical in both builds): spring inked "
               f"{d['ink_spring']['left_rel']:+d}..{d['ink_spring']['right_rel']:+d} "
               f"against its {sp['w']}px box; standing player inked "
               f"{d['ink_player']['left_rel']:+d}..{d['ink_player']['right_rel']:+d} "
               f"against a {d['player_box_w']}px box")
    out.append("")
    out.append("  contact band -- the |dx| between centres at which the side launch fires")
    for k, what in (("band_standing", "STANDING (box 19)"),
                    ("band_curled", "CURLED   (box 15)")):
        out.append(f"    {what:22s}  A: |dx| <= {A[k]['outer']}      "
                   f"B: |dx| <= {B[k]['outer']}      "
                   f"delta {B[k]['outer'] - A[k]['outer']:+d}px")
    # THE DEAD BAND -- the whole point of the exercise. Between the |dx| at which the two
    # silhouettes first share a screen column and the |dx| at which the launch fires,
    # there is a range where the player is VISIBLY TOUCHING the spring and nothing
    # happens. The leading ink edge is taken per POSE from the approach traces (a running
    # frame and a ball frame draw differently), as a RANGE across the animation, because
    # a single frame's value would understate it.
    def lead(dump, key):
        """The player's leading inked column, over the APPROACH frames only.

        PRE-LAUNCH ONLY, and that filter is load-bearing: the launched frames draw a
        different pose entirely (the ball leaving at 16px/frame reads +29..+30 against an
        approach's +9..+13), and including them stretched the reported dead band from 4px
        to 21px -- a number three times the whole contact face, which is how it was
        caught.
        """
        lf = dump[key]["launch_frame"]
        vals = [r["ink_p"][1] for r in dump[key]["rows"]
                if r.get("ink_p") and r["dx"] < 0 and (lf is None or r["f"] < lf)]
        return (min(vals), max(vals)) if vals else None
    sl = A["drawn_standing"]["ink_spring"]["left_rel"]
    out.append("")
    out.append("  DEAD BAND -- |dx| where the pixels overlap but no launch fires")
    for tk, bk, what in (("trace_walk_0", "band_standing", "running (box 19)"),
                         ("trace_roll_0", "band_curled", "rolling (box 15)")):
        L = lead(A, tk)
        if not L:
            continue
        touch_lo, touch_hi = L[0] - sl, L[1] - sl
        for tag, dump in (("A " + A["label"], A), ("B " + B["label"], B)):
            fire = dump[bk]["outer"]
            lo, hi = fire + 1, touch_hi
            width = max(0, hi - lo + 1)
            out.append(f"    {what:18s} {tag:10s} pixels touch from |dx| "
                       f"{touch_lo}..{touch_hi} (leading inked column {L[0]}..{L[1]}, "
                       f"spring edge {sl}); launch fires at |dx| <= {fire}; "
                       f"DEAD BAND {'none' if width <= 0 else f'|dx| {lo}..{hi} = {width}px'}")
    out.append("")
    out.append("  approach traces -- last frame before the launch fires")
    for k in sorted(x for x in A if x.startswith("trace_")):
        a, b = A[k], B[k]
        out.append(f"    {k:16s} A: dx={a['contact_dx']} box={a['contact_box']} "
                   f"inked-overlap={a['contact_ink_overlap']}px   "
                   f"B: dx={b['contact_dx']} box={b['contact_box']} "
                   f"inked-overlap={b['contact_ink_overlap']}px")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom")
    ap.add_argument("--lst")
    ap.add_argument("--label")
    ap.add_argument("--json")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"))
    a = ap.parse_args()
    if a.compare:
        print(compare(*a.compare))
        return 0
    if not (a.rom and a.lst and a.label):
        ap.error("--rom, --lst and --label are required unless --compare is given")
    note = []
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            res = asyncio.run(run(sock, a.lst, a.label, note))
    except Unmeasurable as exc:
        print("\n".join(note))
        print(f"UNMEASURABLE: {exc}")
        return 2
    print("\n".join(note))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1))
        print(f"wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
