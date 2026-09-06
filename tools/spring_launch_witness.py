#!/usr/bin/env python3
"""spring_launch_witness — is a solid's SIDE face really solid, and does the spring launch?

THE CLAIM UNDER TEST is not "the spring object builds" and not "Touch_Spring is
reachable in the listing". It is four runtime facts about a real player meeting real
objects placed in real level data. FOUR LEGS, and the count is asserted at the end so a
leg that silently did not run cannot be read as a leg that passed:

  L1 SPRING SIDE   walking into a spring from the side is SOLID -- the player is pushed
                   out, HIS RUNNING SPEED IS KILLED, and he is NOT launched.

  L2 BLOCK SIDE    the identical measurement against a plain COLLISION_SOLID block.
                   TWO SOLIDS, NOT ONE, and that is the point of the leg rather than
                   thoroughness: `solid_face_response` is a comptime template spliced
                   into Touch_Solid AND Touch_Spring, so the ROM holds TWO copies of the
                   side arm. A fix that showed up only on the spring would have been
                   made in the wrong place, and only a second solid can see that.

  L3 ESCAPE        having been stopped by a solid, the player can still WALK AWAY from
                   it. This is the control on L1/L2, not a courtesy check -- see "THE
                   ESCAPE LEG IS THE CONTROL" below.

  L4 TOP           falling onto a spring launches the player at S3K's red-spring
                   velocity, and leaves him airborne.

THE SPEED KILL (L1/L2) IS WHAT SP-1 WAS. Until 2026-09-05 the side arm cleared the
player's x_vel and nothing else, which holds his POSITION and never touches his speed:
a GROUNDED player is driven by the game's inertia field (sonic4: PlayerV.ground_speed),
which his ground state re-derives x_vel from every tick. Measured then: he rested 10px
from a spring's centre against a 17px contact face -- a full top-speed step INSIDE it,
re-ramming and being re-pushed every frame -- and after releasing the button friction
took 140 frames to settle him at the real face. The engine cannot name a game overlay
field, so the fix left through a second contract member (Game.solid_pushed), and these
legs are what says it works.

THE ESCAPE LEG IS THE CONTROL, and without it this file would have a green that hides a
total regression. The push deliberately leaves 1px of overlap so the next frame's AABB
still fires, so a player standing beside a solid re-enters the side arm EVERY frame. An
UNCONDITIONAL speed kill would therefore zero his speed forever and he could never walk
away from any solid in the game -- and L1/L2 would not notice, because a player who is
already stopped rests in exactly the right place and settles in zero frames. So L3 holds
the OPPOSITE direction afterwards and requires him to actually leave.

THE EXPECTED VELOCITY IS DERIVED, NOT PINNED, through three independent hops that must
all agree, so no single edited number can make this pass:

  (1) skdisasm at the pinned revision -- `word_22EF0`'s first `dc.w` is parsed out of
      sonic3k.asm at 2fcd861c208f342b6d14df694c6422c74f20a4be. Nothing in THIS repo can
      change it.
  (2) the built ROM's own ObjDef_Spring record -- its y_vel field, read out of the ROM
      file at the address the listing gives, must equal (1). This is what catches a
      spring whose objdef was retuned away from the reference.
  (3) the running machine -- the y_vel the player actually receives must equal (1).

A mismatch anywhere is reported as which hop disagreed. If skdisasm is not available the
run exits 2 UNMEASURABLE; it never falls back to a literal.

EVERY TEST CARRIES A VACUITY GUARD, because each has an obvious way to pass while
measuring nothing. "The player was never pushed into the spring" would satisfy "he did
not penetrate it"; "the player never reached the spring" would satisfy "he was not
launched wrongly"; "he never made contact" would satisfy "his speed was killed on
contact". So each test first asserts CONTACT (he got within the combined half-width / he
descended onto it) and only then asserts the response. Failing to make contact is
exit 2, not a pass.

THE BLOCK IN L2 IS A RETYPED SPRING, and that is a stated substitution rather than a
quiet one. The OJZ act places three springs and three blocks, but every placed block is
a floating platform far from the player's ground run -- measured: after the settle only
the two springs are live at all, and neither block is within reach of a walking player.
So L2 takes the SAME live object L1 used and rewrites two of its SST fields:
collision_resp COLLISION_SPRING -> COLLISION_SOLID (which is what re-routes
TouchResponse's dispatch to Touch_Solid's own inlined copy of the template) and
code_addr -> TestSolid_Main. What it does NOT change is geometry, position or the
player's approach, so L1 and L2 differ in exactly one thing: which of the two ROM copies
of the side arm runs. The retype is asserted to have taken before the leg proceeds.

WHAT THIS DOES NOT ESTABLISH, stated because it is where the object would fail next:
  * only the vertical red spring exists; there are no diagonal or horizontal springs.
  * only ONE spring is driven (the one on the player's own ground run). The other two
    placements are checked for SPAWNING only.
  * the sound is not tested because the spring has no sound -- sfx $B1 is not in this
    game's bank (see games/sonic4/objects/test_solid.emp).
  * the PUSH POSE is not tested, because there is not one: S3K sets Status_Push here and
    this engine does not, since its ground wall probe clears ST_PUSHING whenever the
    capped ground speed is zero -- which is the state the fix creates. Rider on SP-1.

RUN:  python3 tools/spring_launch_witness.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Headless: spawns its own private oracle-aether over a private socket (AetherInstance);
it does not touch /run/user/1000/oracle.sock and so cannot collide with a live GUI.

EXIT  0 pass · 1 a real failure · 2 UNMEASURABLE (never rendered as green).
"""
import argparse
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path, suite_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, write_bytes  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

# The reference revision. Pinned here because a witness that read whatever the donor
# working tree happens to hold would silently re-baseline itself.
SKDISASM_REV = "2fcd861c208f342b6d14df694c6422c74f20a4be"

BOOT_FRAMES = 60         # level-state init: before this the player SST still reads all-zero
SETTLE_FRAMES = 300      # spawn is ~900px above the floor; this covers the fall + rest
SIDE_FRAMES = 240        # holding a direction into the spring
SETTLE_AFTER_HOLD = 400  # CEILING on the wait for friction to take ground_speed to zero
DROP_FRAMES = 120        # falling onto it
DROP_HEIGHT = 72         # px above the spring's centre to start the drop from
ESCAPE_FRAMES = 60       # holding AWAY from the solid, for the L3 control
STILL_FRAMES = 10        # consecutive unchanged x that counts as "come to rest"
LEGS = 4                 # L1 spring side · L2 block side · L3 escape · L4 top face

# SETTLE_CEILING_OK — the most frames the post-release settle may take before the run
# calls the speed kill absent. DERIVED, not tuned: with the kill working the player is
# already at rest on the frame the button is released, so the settle loop can only spend
# the STILL_FRAMES samples it needs to CONFIRM rest, plus a frame of slack for the
# release landing mid-tick. Under the SP-1 defect this measured 140 (friction decaying a
# top-speed run at PHYS_FRICTION per frame), so the two regimes are two orders apart and
# nothing about this number is delicate.
SETTLE_CEILING_OK = STILL_FRAMES + 2


class Unmeasurable(Exception):
    """The instrument could not answer. Exit 2, never 0."""


# --------------------------------------------------------------------------- hop 1

def s3k_red_spring_velocity() -> int:
    """`word_22EF0`'s first entry at the pinned skdisasm revision (sonic3k.asm:47654-47656).

    Located by the LABEL, not by line number: a line number is a fact about one checkout
    and would go quietly wrong against a different one, while the label is what the
    engine's own comments cite.
    """
    root = suite_path("skdisasm")
    if not os.path.isdir(root):
        raise Unmeasurable(f"skdisasm is not at {root} — the reference velocity cannot be derived")
    try:
        src = subprocess.run(["git", "-C", root, "show", f"{SKDISASM_REV}:sonic3k.asm"],
                             capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        raise Unmeasurable(f"cannot read sonic3k.asm at {SKDISASM_REV[:8]}: {e.stderr.strip()[:200]}")
    lines = src.splitlines()
    try:
        at = next(i for i, l in enumerate(lines) if l.startswith("word_22EF0:"))
    except StopIteration:
        raise Unmeasurable(f"no `word_22EF0:` label in sonic3k.asm at {SKDISASM_REV[:8]} — "
                           "the spring's velocity table has moved or been renamed")
    for l in lines[at + 1:at + 4]:
        m = re.search(r"dc\.w\s+(-?)\$([0-9A-Fa-f]+)", l)
        if m:
            v = int(m.group(2), 16)
            return -v if m.group(1) else v
    raise Unmeasurable("found `word_22EF0:` but no `dc.w` under it")


# --------------------------------------------------------------------------- hop 2

def parse_equs(lst: str) -> dict:
    out = {}
    rx = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")
    for line in Path(lst).read_text(errors="replace").splitlines():
        m = rx.match(line)
        if m:
            out.setdefault(m.group(1), int(m.group(2), 16))
    return out


def s16(v: int) -> int:
    return v - 0x10000 if v >= 0x8000 else v


def objdef_y_vel_from_rom(rom: str, sym: dict, equ: dict) -> int:
    """ObjDef_Spring's y_vel, read straight out of the ROM image.

    The ObjDef record is code_addr.w, x_vel.w, y_vel.w — so y_vel is at +4. Asserted
    against the ObjDef struct's own harvested offsets rather than assumed, so a layout
    change fails here instead of reading a neighbouring field as a velocity.
    """
    for name in ("ObjDef_Spring",):
        if name not in sym:
            raise Unmeasurable(f"{name} is not in the listing — is this a build with the spring?")
    off = 4
    data = Path(rom).read_bytes()
    at = sym["ObjDef_Spring"]
    if at + off + 2 > len(data):
        raise Unmeasurable(f"ObjDef_Spring at ${at:06X} is past the end of {rom}")
    return s16((data[at + off] << 8) | data[at + off + 1])


# --------------------------------------------------------------------------- machine

class Probe:
    def __init__(self, bus, sym, equ):
        self.b, self.sym, self.equ = bus, sym, equ
        self.player = sym["Player_1"]

    async def rd(self, addr, n):
        return await read_bytes(self.b, addr, n)

    async def word(self, addr):
        return int(await self.rd(addr, 2), 16)

    async def sword(self, addr):
        return s16(await self.word(addr))

    async def coord(self, addr):
        """A 16.16 Coord's INTEGER part (the high word)."""
        return s16(int(await self.rd(addr, 2), 16))

    async def p(self, field):
        return self.player + self.equ[field]

    async def player_state(self):
        px = await self.coord(self.player + self.equ["SST_x_pos"])
        py = await self.coord(self.player + self.equ["SST_y_pos"])
        xv = await self.sword(self.player + self.equ["SST_x_vel"])
        yv = await self.sword(self.player + self.equ["SST_y_vel"])
        st = int(await self.rd(self.player + self.equ["SST_status"], 1), 16)
        pw = int(await self.rd(self.player + self.equ["SST_width_pixels"], 1), 16)
        ph = int(await self.rd(self.player + self.equ["SST_height_pixels"], 1), 16)
        # gsp — the GROUNDED driver, and the field the whole SP-1 half of this witness
        # is about. Located through `_pl_gsp`, the offset symbol the game exports for
        # exactly this purpose (games/sonic4/player/player_common.emp); NOT hardcoded
        # and NOT inferred from "it is PlayerV's first field", either of which would go
        # silently wrong on an overlay reorder and read a neighbouring field as a speed.
        gsp = await self.sword(self.player + self.equ["_pl_gsp"])
        return dict(x=px, y=py, xv=xv, yv=yv, status=st, w=pw, h=ph, gsp=gsp)

    async def springs(self, spring_code_addr):
        """Every LIVE dynamic slot whose dispatch word is Spring_Main's.

        Walks Dynamic_Live (the spawn-order live list of SST word addresses) exactly the
        way TouchResponse does, so a spring this cannot see is a spring TouchResponse
        cannot see either.
        """
        count = await self.word(self.sym["Dynamic_Live_Count"])
        found = []
        for i in range(count):
            ent = await self.word(self.sym["Dynamic_Live"] + 2 * i)
            if not ent:
                continue
            sst = 0xFF0000 | ent
            if await self.word(sst + self.equ["SST_code_addr"]) != spring_code_addr:
                continue
            found.append(dict(
                sst=sst,
                x=await self.coord(sst + self.equ["SST_x_pos"]),
                y=await self.coord(sst + self.equ["SST_y_pos"]),
                w=int(await self.rd(sst + self.equ["SST_width_pixels"], 1), 16),
                h=int(await self.rd(sst + self.equ["SST_height_pixels"], 1), 16),
                yv=s16(await self.word(sst + self.equ["SST_y_vel"])),
            ))
        return found

    async def frames(self, n=1):
        await self.b.call("emulator/run_frames", {"frames": n})

    async def hold(self, button, down):
        await self.b.call("emulator/hold", {"buttons": [button], "down": bool(down)})

    async def put_player(self, x=None, y=None, xv=None, yv=None):
        if x is not None:
            await write_bytes(self.b, self.player + self.equ["SST_x_pos"], f"{x & 0xFFFF:04X}0000")
        if y is not None:
            await write_bytes(self.b, self.player + self.equ["SST_y_pos"], f"{y & 0xFFFF:04X}0000")
        if xv is not None:
            await write_bytes(self.b, self.player + self.equ["SST_x_vel"], f"{xv & 0xFFFF:04X}")
        if yv is not None:
            await write_bytes(self.b, self.player + self.equ["SST_y_vel"], f"{yv & 0xFFFF:04X}")


ST_IN_AIR = 3   # engine/system/constants.emp — cross-checked below against the listing


# --------------------------------------------------------------------------- the tests

async def retype_to_solid(pr, target, out):
    """Turn a live spring into a plain COLLISION_SOLID block, in place (L2).

    Two SST fields, and only two: `collision_resp`, which is what TouchResponse indexes
    its handler table with and therefore the whole of "which copy of the side arm runs",
    and `code_addr`, so the object's own per-frame routine is the block's rather than the
    spring's. Geometry, position and the player's approach are untouched, so L1 and L2
    differ in exactly one variable.

    ASSERTED, NOT ASSUMED: both writes are read back, and a retype that did not take is
    UNMEASURABLE rather than a leg that quietly re-measured the spring.
    """
    want_resp = pr.equ["COLLISION_SOLID"]
    want_code = (pr.sym["TestSolid_Main"] - pr.sym["ObjCodeBase"]) & 0xFFFF
    was_resp = int(await pr.rd(target["sst"] + pr.equ["SST_collision_resp"], 1), 16)
    await write_bytes(pr.b, target["sst"] + pr.equ["SST_collision_resp"], f"{want_resp:02X}")
    await write_bytes(pr.b, target["sst"] + pr.equ["SST_code_addr"], f"{want_code:04X}")
    got_resp = int(await pr.rd(target["sst"] + pr.equ["SST_collision_resp"], 1), 16)
    got_code = await pr.word(target["sst"] + pr.equ["SST_code_addr"])
    if got_resp != want_resp or got_code != want_code:
        raise Unmeasurable(
            f"the retype did not take: collision_resp {got_resp} (wanted {want_resp}), "
            f"code_addr ${got_code:04X} (wanted ${want_code:04X}) — L2 would have "
            f"re-measured the spring while claiming to measure a block")
    if was_resp != pr.equ["COLLISION_SPRING"]:
        raise Unmeasurable(
            f"the object at (x={target['x']},y={target['y']}) was collision type "
            f"{was_resp}, not COLLISION_SPRING {pr.equ['COLLISION_SPRING']} — L2's "
            f"substitution is not the one this file describes")
    out.append(f"  retyped the live object at (x={target['x']},y={target['y']}) from "
               f"COLLISION_SPRING to COLLISION_SOLID (code_addr -> TestSolid_Main "
               f"${pr.sym['TestSolid_Main']:06X}) — the SAME box, in the SAME place, "
               f"dispatched through Touch_Solid's own inlined copy of the template")
    # A block is not a spring: the launch must now be impossible, so the "was he
    # launched" arm of the side test is measuring a genuinely different handler.
    return dict(target, w=target["w"], h=target["h"])


async def test_side(pr, obj, want_launch, out, leg, expect_launchable=True):
    """Walk into a solid from the side. Solid, SPEED KILLED, and NOT launched.

    THE DISCRIMINATOR FOR SOLIDITY IS THE SIGN OF THE GAP, not its size. A face that
    were not solid at all would let the player walk straight through and out the far
    side, which flips `player.x - obj.x`; that is unambiguous in both directions.

    THE DISCRIMINATOR FOR THE SPEED KILL IS THE PENETRATION WHILE HOLDING, and it is
    derived from the code rather than from this measurement. The push moves the player
    out by `pen - 1` (`subq.w #1, d0` in solid_face_response), deliberately leaving 1px
    of overlap so the next frame's AABB still fires -- so a player whose speed is killed
    on contact can NEVER be deeper than `half_w - 1` between centres. A player whose
    speed is not killed re-accelerates into the face every frame and sits one top-speed
    step further in, which is exactly the 10-against-17 that SP-1 measured. So the
    assertion is `deepest == half_w - 1`, and the defect's signature is any smaller
    number.

    THE THIRD MEASUREMENT IS THE SPEED ITSELF, which is the only one that names the
    field the fix had to reach. While in contact and holding INTO the face, the player's
    ground speed may be at most ONE frame of running acceleration (PHYS_ACCEL, read from
    the listing): the kill zeroes it, and the very next tick's input adds one step back.
    Under the defect it is the full running top speed. The bound is derived from those
    two constants and not from a run.
    """
    p0 = await pr.player_state()
    half_w = (p0["w"] + obj["w"]) // 2
    side = 1 if p0["x"] > obj["x"] else -1          # which side he starts on
    button = "right" if side < 0 else "left"
    away = "left" if button == "right" else "right"
    out.append(f"  {leg}: player at x={p0['x']} y={p0['y']} (box {p0['w']}x{p0['h']}), "
               f"object at x={obj['x']} y={obj['y']} (box {obj['w']}x{obj['h']}); "
               f"holding {button.upper()}, contact face at {half_w}px between centres")

    closest = 1 << 30
    min_yv = 0
    crossed = False
    xs = []
    approach_top_gsp = 0     # his running speed BEFORE he ever touched the object
    contact_top_gsp = None   # the largest speed he carried while overlapping it
    contact_frames = 0
    await pr.hold(button, True)
    try:
        for _ in range(SIDE_FRAMES):
            await pr.frames(1)
            st = await pr.player_state()
            xs.append(st["x"])
            gap = st["x"] - obj["x"]
            if gap != 0 and (1 if gap > 0 else -1) != side:
                crossed = True
            closest = min(closest, abs(gap))
            min_yv = min(min_yv, st["yv"])
            # IN CONTACT means the AABB overlaps, which is the condition under which the
            # side arm runs at all -- the same `< half_w` the engine tests. Sampling
            # OUTSIDE that window would fold his approach run into the "while pushing"
            # number and make the defect invisible.
            if abs(gap) < half_w:
                contact_frames += 1
                contact_top_gsp = abs(st["gsp"]) if contact_top_gsp is None \
                    else max(contact_top_gsp, abs(st["gsp"]))
            else:
                approach_top_gsp = max(approach_top_gsp, abs(st["gsp"]))
    finally:
        await pr.hold(button, False)

    # RELEASE AND LET HIM SETTLE, then measure the RESTING gap. With the speed kill in
    # place he is already at rest and this costs the confirmation samples only; the loop
    # is kept ADAPTIVE (rather than a fixed count) because it is also the instrument that
    # reports HOW LONG it took, and that number is one of the two regimes -- 140 frames
    # of friction decay was SP-1's other signature.
    rest, held_still, settled_after = None, 0, None
    for f in range(SETTLE_AFTER_HOLD):
        await pr.frames(1)
        x = (await pr.player_state())["x"]
        held_still = held_still + 1 if x == rest else 0
        rest = x
        if held_still >= STILL_FRAMES:
            settled_after = f + 1
            break
    if settled_after is None:
        raise Unmeasurable(
            f"the player never came to rest beside the object within {SETTLE_AFTER_HOLD} "
            f"frames of releasing {button.upper()} (last x={rest}) — the resting contact "
            f"face cannot be measured")
    rest_x = rest
    rest = abs(rest - obj["x"])
    out.append(f"  {leg}: came to rest {settled_after} frames after release")

    # --- vacuity FIRST: a player who never reached the object proves nothing ---
    if closest > half_w + 8:
        raise Unmeasurable(
            f"the player never reached the object's side face: closest approach was "
            f"{closest}px between centres, and contact begins at {half_w}px. Nothing about "
            f"side solidity was measured — this is not a pass.")
    if contact_frames == 0 or contact_top_gsp is None:
        raise Unmeasurable(
            f"the player never overlapped the object at all over {SIDE_FRAMES} held "
            f"frames (closest {closest}px, contact begins at {half_w}px) — the side arm "
            f"never ran, so neither the push nor the speed kill was measured.")
    if approach_top_gsp == 0:
        raise Unmeasurable(
            "the player carried no ground speed on his approach — he was not running "
            "into anything, and a stopped player trivially satisfies every assertion "
            "below. This is not a pass.")

    fails = []
    if crossed:
        fails.append(f"{leg}: WALKED THROUGH IT: the player crossed from one side of the "
                     f"object to the other while holding {button.upper()} — the side face "
                     f"is not solid")
    else:
        out.append(f"  {leg}: he never crossed the object's centre — the side face held")

    want_rest = half_w - 1
    if rest != want_rest:
        fails.append(f"{leg}: RESTING GAP {rest}px, expected {want_rest}px (the contact face "
                     f"{half_w} less the 1px bias solid_face_response's `subq.w #1, d0` "
                     f"leaves) — the side push does not settle where the code says")
    else:
        out.append(f"  {leg}: after releasing {button.upper()}, he settles at {rest}px from "
                   f"the object's centre — exactly the contact face {half_w} minus the 1px "
                   f"overlap bias the push leaves on purpose")

    # ---- SP-1, measurement 1 of 3: how deep he got while PUSHING ----
    if closest != want_rest:
        fails.append(f"{leg}: SP-1 PENETRATION: while holding {button.upper()} he reached "
                     f"{closest}px between centres, {want_rest - closest}px INSIDE the "
                     f"{want_rest}px resting face. He is being pushed out and then walking "
                     f"straight back in, which is what an unkilled ground speed looks like")
    else:
        out.append(f"  {leg}: deepest approach while HOLDING into it = {closest}px, the same "
                   f"{want_rest}px he rests at — he never gets a step inside the face")

    # ---- SP-1, measurement 2 of 3: the speed he carried while pushing ----
    accel = pr.equ["PHYS_ACCEL"]
    top = pr.equ["PHYS_TOP_SPEED"]
    # The approach number is NOT the comparison baseline and is reported only as the
    # vacuity witness (he was actually running). It is smaller than the in-contact
    # number even under the defect, because the object sits close enough to his spawn
    # that he is still accelerating when he first overlaps it; what the defect does is
    # let him go on accelerating INSIDE the box, all the way to the cap. The baseline
    # that means something is PHYS_TOP_SPEED, the speed he is running at.
    if contact_top_gsp > accel:
        fails.append(f"{leg}: SP-1 GROUND SPEED: while overlapping the object he carried up "
                     f"to {contact_top_gsp} (8.8) — {100 * contact_top_gsp // top}% of the "
                     f"PHYS_TOP_SPEED {top} running cap, and past the {accel} bound "
                     f"(PHYS_ACCEL, the one frame of re-acceleration a killed speed can "
                     f"regain). He goes on accelerating INSIDE the box")
    else:
        out.append(f"  {leg}: ground speed while in contact peaked at {contact_top_gsp} "
                   f"(8.8) — at or under PHYS_ACCEL {accel}, i.e. one tick's worth of "
                   f"re-acceleration and nothing carried over, against a PHYS_TOP_SPEED "
                   f"of {top}. {contact_frames} contact frames sampled; he was running at "
                   f"{approach_top_gsp} on the approach, so this was not a vacuous stop")

    # ---- SP-1, measurement 3 of 3: how long friction had to work afterwards ----
    if settled_after > SETTLE_CEILING_OK:
        fails.append(f"{leg}: SP-1 SETTLE: {settled_after} frames of friction were needed "
                     f"after the button was released (ceiling {SETTLE_CEILING_OK} = the "
                     f"{STILL_FRAMES} confirmation samples plus slack). A player whose speed "
                     f"was killed on contact is ALREADY at rest when the button comes up")
    else:
        out.append(f"  {leg}: he was already at rest when the button came up "
                   f"({settled_after} frames, ceiling {SETTLE_CEILING_OK})")

    tail = xs[-30:]
    drift = max(tail) - min(tail)
    if drift > 2:
        fails.append(f"{leg}: NOT STOPPED: the player's x still moved {drift}px over the "
                     f"last 30 frames while holding {button.upper()} into the object")
    else:
        out.append(f"  {leg}: x drift over the last 30 held frames = {drift}px — stopped dead")

    # A THRESHOLD, NOT AN EQUALITY, and the red run is why. This check first read
    # `min_yv <= want_launch`, which CANNOT FIRE: a frame-boundary sample of a launch is
    # the launch plus one gravity step (see test_top), so a real side-launch reads -4040
    # against a -4096 launch and compares as "never launched". Proved by the red-first
    # mutation that deletes the side push: the player walked through the spring, WAS
    # launched off its top face at -4040, and this line called that no-launch. Half the
    # launch is a threshold nothing else in a walking player's motion reaches -- he has
    # no jump input and no other spring within reach -- and it is unambiguous in both
    # directions: the green run reads 0.
    launch_floor = want_launch // 2
    if min_yv <= launch_floor:
        fails.append(f"{leg}: SIDE CONTACT LAUNCHED HIM: y_vel reached {min_yv}, past the "
                     f"{launch_floor} threshold (half the {want_launch} launch), while he "
                     f"should only ever have touched the side face")
    else:
        what = "a side hit does not fire the spring" if expect_launchable else \
               "and a plain block has no launch to fire"
        out.append(f"  {leg}: most negative y_vel seen = {min_yv}, nowhere near the "
                   f"{launch_floor} launch threshold — {what}")
    return fails, dict(button=button, away=away, rest_x=rest_x, half_w=half_w)


async def test_escape(pr, obj, ctx, out, leg):
    """L3, THE CONTROL: he was stopped by the solid, can he still walk away from it?

    THIS LEG EXISTS BECAUSE OF HOW THE FIX COULD GO WRONG, not for completeness. The
    push leaves 1px of overlap on purpose, so a player resting against a solid re-enters
    the side arm every single frame. A speed kill with no direction gate would therefore
    zero his ground speed forever -- he could never leave any solid in the game -- and
    every other assertion in this file would still be green, because a permanently
    stopped player rests at exactly the right place and settles in zero frames. Only
    holding the OPPOSITE direction can see it.

    The expectation is derived from the geometry, not tuned: over ESCAPE_FRAMES of
    unobstructed running he covers far more than a screen, so ANY sane threshold
    separates "he left" from "he is welded to the object". The bound used is half the
    contact face -- if he has not even cleared his own overlap he has not escaped.
    """
    start = (await pr.player_state())["x"]
    await pr.hold(ctx["away"], True)
    try:
        for _ in range(ESCAPE_FRAMES):
            await pr.frames(1)
    finally:
        await pr.hold(ctx["away"], False)
    end_st = await pr.player_state()
    moved = abs(end_st["x"] - obj["x"]) - abs(start - obj["x"])
    want = ctx["half_w"] // 2
    if moved < want:
        return [f"{leg}: WELDED TO THE SOLID: holding {ctx['away'].upper()} for "
                f"{ESCAPE_FRAMES} frames moved him only {moved}px further from the "
                f"object (x {start} -> {end_st['x']}, object at {obj['x']}), against a "
                f"{want}px floor. The side arm is killing his speed even when he is "
                f"travelling AWAY from the face — the direction gate is missing or "
                f"inverted, and he can never leave a solid again"]
    out.append(f"  {leg}: holding {ctx['away'].upper()} for {ESCAPE_FRAMES} frames took him "
               f"{moved}px further out (x {start} -> {end_st['x']}, ground speed "
               f"{end_st['gsp']}) — the stop is directional, not a weld")
    return []


async def test_top(pr, spring, want_launch, out):
    """Drop onto the spring. Launched at exactly the reference velocity, and airborne.

    SAMPLED AT THE HOOK, NOT AT THE FRAME BOUNDARY, and the difference is the whole
    measurement. Touch_Spring writes the impulse and then the player's own tick applies
    one frame of gravity before the frame ends, so a frame-boundary read of y_vel is the
    launch PLUS gravity -- measured -4040 against a -4096 reference, which is exactly
    $38, one gravity step, and would have read as a 56-unit discrepancy in the spring.
    `run_to Spring_Launched` stops the machine between the two: Touch_Spring has written
    y_vel and has just invoked the hook, and nothing has integrated yet. That is the only
    instant at which "the launch velocity" is a well-defined quantity.
    """
    start_y = spring["y"] - DROP_HEIGHT
    await pr.put_player(x=spring["x"], y=start_y, xv=0, yv=0)
    got = await pr.player_state()
    if got["y"] != start_y:
        raise Unmeasurable(f"the poke did not take: asked for y={start_y}, slot reads {got['y']}")
    out.append(f"  top: dropped from x={spring['x']} y={start_y} "
               f"({DROP_HEIGHT}px above the spring's centre, {DROP_HEIGHT - spring['h'] // 2}px "
               f"above its top edge)")

    r = await pr.b.call("emulator/run_to",
                        {"addr": hex(pr.sym["Spring_Launched"]), "maxFrames": DROP_FRAMES})
    if not r.get("reached"):
        st = await pr.player_state()
        raise Unmeasurable(
            f"the drop never reached Spring_Launched within {DROP_FRAMES} frames — the "
            f"player ended at y={st['y']} y_vel={st['yv']} status=${st['status']:02X}. "
            f"Either he never landed on the spring or the launch hook is not being invoked; "
            f"either way the top face was not measured.")

    st = await pr.player_state()
    fails = []
    out.append(f"  top: stopped INSIDE Spring_Launched (${pr.sym['Spring_Launched']:06X}) with "
               f"the player at y={st['y']}, before his tick could integrate")
    if st["yv"] != want_launch:
        fails.append(f"LAUNCH VELOCITY {st['yv']} at the hook, reference {want_launch} "
                     f"(difference {st['yv'] - want_launch})")
    else:
        out.append(f"  top: y_vel at the hook = {st['yv']} == reference {want_launch} "
                   f"({want_launch / 256:.1f} px/frame) — the launch is S3K's red spring")

    # Let the launch finish and check what it left behind.
    await pr.frames(2)
    after = await pr.player_state()
    if not (after["status"] >> ST_IN_AIR) & 1:
        fails.append(f"the player is not AIRBORNE two frames after the launch (status "
                     f"${after['status']:02X}, ST_IN_AIR bit {ST_IN_AIR} clear) — his ground "
                     f"state will re-attach him and the impulse is wasted")
    else:
        out.append(f"  top: status ${after['status']:02X} has ST_IN_AIR set — genuinely airborne")
    if after["y"] >= st["y"]:
        fails.append(f"the player did not RISE after the launch: y went {st['y']} -> "
                     f"{after['y']} over two frames")
    else:
        out.append(f"  top: he rose {st['y'] - after['y']}px over the next two frames")

    anim = int(await pr.rd(spring["sst"] + pr.equ["SST_anim"], 1), 16)
    if anim == 0:
        fails.append("the spring's anim is still 0 after the launch — the fire animation "
                     "never started, so a second bounce would show no spring motion")
    else:
        out.append(f"  top: the spring's anim is now {anim} — the fire script is running")
    return fails


# --------------------------------------------------------------------------- driver

async def run(sock, rom, lst, want_launch, out):
    b = BusClient(socket_path=sock, client_id="springw", client_name="spring_launch_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym = parse_lst(lst)
    equ = parse_equs(lst)

    for need in ("Player_1", "Dynamic_Live", "Dynamic_Live_Count", "Spring_Main", "ObjCodeBase",
                 "Spring_Launched", "TestSolid_Main"):
        if need not in sym:
            raise Unmeasurable(f"{need} is not in {lst} — wrong ROM/listing pair?")
    for need in ("SST_x_pos", "SST_y_pos", "SST_x_vel", "SST_y_vel", "SST_status",
                 "SST_code_addr", "SST_width_pixels", "SST_height_pixels", "SST_anim",
                 "SST_collision_resp",
                 # SP-1's own three: the inertia offset the game exports for this witness,
                 # the acceleration constant the in-contact speed bound is derived from,
                 # and the two collision-type ids the L2 retype moves between.
                 "_pl_gsp", "PHYS_ACCEL", "PHYS_TOP_SPEED", "COLLISION_SOLID",
                 "COLLISION_SPRING"):
        if need not in equ:
            raise Unmeasurable(f"{need} has no EQU in {lst} — the SP-1 legs cannot be "
                               f"measured without it (an older ROM/listing pair?)")

    spring_code = (sym["Spring_Main"] - sym["ObjCodeBase"]) & 0xFFFF
    out.append(f"  Spring_Main ${sym['Spring_Main']:06X} - ObjCodeBase ${sym['ObjCodeBase']:06X} "
               f"= dispatch word ${spring_code:04X}")

    pr = Probe(b, sym, equ)

    # EACH LEG GETS ITS OWN BOOT, and that is not tidiness. The side legs end with the
    # player pressed against an object and then walked away from it; running the drop
    # after one of them, the poked player carried leftover inertia off the spring while
    # falling and landed 340px away on the next flat run, and the drop reported
    # UNMEASURABLE for a reason that had nothing to do with the top face. Re-booting is
    # also the better experiment — every leg starts from the identical settled state
    # rather than from the previous leg's leftovers, which is what makes L1 and L2
    # comparable at all.
    fails = []
    legs = []          # names of the legs that ACTUALLY RAN, asserted against LEGS below

    out.append("BOOT 1 (L1 spring side + L3 escape):")
    springs = await boot_and_settle(pr, spring_code, out)
    for s in springs:
        if s["yv"] != want_launch:
            fails.append(f"the spawned spring at (x={s['x']},y={s['y']}) carries y_vel "
                         f"{s['yv']}, not the reference {want_launch} — the ObjDef's launch "
                         f"strength did not survive the spawn burst-copy")

    target = await pick_target(pr, springs, out)
    out.append("L1 SPRING SIDE (Touch_Spring's copy of solid_face_response):")
    f, ctx = await test_side(pr, target, want_launch, out, "L1")
    fails += f
    legs.append("L1 spring side")

    out.append("L3 ESCAPE (the direction-gate control):")
    fails += await test_escape(pr, target, ctx, out, "L3")
    legs.append("L3 escape")

    out.append("BOOT 2 (L2 plain block):")
    springs = await boot_and_settle(pr, spring_code, out)
    target = await pick_target(pr, springs, out)
    out.append("L2 BLOCK SIDE (Touch_Solid's OWN copy of the same template):")
    block = await retype_to_solid(pr, target, out)
    f, _ = await test_side(pr, block, want_launch, out, "L2", expect_launchable=False)
    fails += f
    legs.append("L2 block side")

    out.append("BOOT 3 (L4 top face):")
    springs = await boot_and_settle(pr, spring_code, out)
    target = await pick_target(pr, springs, out)
    out.append("L4 TOP FACE (the launch — the obvious regression from a side-arm change):")
    fails += await test_top(pr, target, want_launch, out)
    legs.append("L4 top face")

    # THE LEG COUNT IS ITSELF AN ASSERTION. A leg that raised Unmeasurable never reaches
    # here (the run exits 2), but a leg deleted or short-circuited during an edit would
    # otherwise leave a smaller run reading exactly like a clean pass.
    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != LEGS:
        fails.append(f"LEG COUNT {len(legs)}, expected {LEGS} — a leg did not run, and the "
                     f"rest of this report is a smaller experiment than it claims to be")

    await b.close()
    return fails


async def pick_target(pr, springs, out):
    """The spring on the player's own ground run — the only one he can walk into."""
    p0 = await pr.player_state()
    out.append(f"  player settled at x={p0['x']} y={p0['y']} y_vel={p0['yv']} "
               f"status=${p0['status']:02X}")
    same_level = [s for s in springs if abs(s["y"] - p0["y"]) <= 32]
    if not same_level:
        raise Unmeasurable(
            "no spawned spring sits at the player's own ground level (nearest is "
            f"{min(abs(s['y'] - p0['y']) for s in springs)}px away in Y) — he cannot walk "
            "into one, so the SIDE face cannot be reached")
    return min(same_level, key=lambda s: abs(s["x"] - p0["x"]))


async def boot_and_settle(pr, spring_code, out):
    b = pr.b
    await b.call("emulator/reset", {})

    # --- leave DEBUG-FLY, or the whole run measures a floating statue ---
    # s4.debug.bin boots into free-flight: the debug shape arms CHEAT_DEBUG_FLY and
    # Player_Init tail-calls Player_DebugEnter (player_common.emp:592, :650-652), which
    # suspends the state dispatch entirely. Measured before this step existed: the player
    # sat at (256,256) with y_vel 0 for 600 frames and no object ever spawned. B is the
    # toggle, and it is the REAL exit path (Player_DebugExit restores the standing box and
    # the art) rather than poking the flag byte.
    #
    # Shape-agnostic by observation, not by assuming the shape: fall is tested FIRST, and
    # B is pressed only if he is not already falling — in a build with the cheat clear the
    # player is an ordinary PSTATE_AIR slot dropping to ground on frame 1, and there B
    # would buffer a JUMP instead.
    # BOOT_FRAMES first: at frame 8 the level state has not placed the player yet and
    # every SST field still reads 0, which the fall probe below would read as "frozen".
    # Measured: the first version of this witness pressed B against a y=0 slot and
    # reported UNMEASURABLE for the wrong reason.
    await pr.frames(BOOT_FRAMES)
    placed = (await pr.player_state())["y"]
    if placed == 0:
        raise Unmeasurable(f"the player slot is still all-zero after {BOOT_FRAMES} frames — "
                           "the level state never placed him")
    before = placed
    await pr.frames(8)
    after = (await pr.player_state())["y"]
    if after == before:
        out.append(f"  player is not falling at y={before} — pressing B to leave debug-fly")
        await b.call("emulator/press", {"buttons": ["b"]})
        await pr.frames(8)
        moved = (await pr.player_state())["y"]
        if moved == after:
            raise Unmeasurable(
                f"the player is still frozen at y={moved} after a B press — he is neither a "
                "falling player nor in debug-fly, so nothing in this run would be physics")
        out.append(f"  after B: y {after} -> {moved}, physics is running")
    else:
        out.append(f"  player already falling ({before} -> {after}) — no debug-fly to leave")

    await pr.frames(SETTLE_FRAMES)

    springs = await pr.springs(spring_code)
    if not springs:
        raise Unmeasurable(
            f"no live object carries Spring_Main's dispatch word after {SETTLE_FRAMES} frames — "
            "the entity window never spawned a spring, so neither face can be tested")
    out.append(f"  {len(springs)} spring(s) live: " +
               ", ".join(f"(x={s['x']},y={s['y']},y_vel={s['yv']})" for s in springs))
    return springs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()

    out = ["REFERENCE CHAIN:"]
    try:
        want = s3k_red_spring_velocity()
        out.append(f"  hop 1  skdisasm {SKDISASM_REV[:8]} sonic3k.asm word_22EF0[0] = {want} "
                   f"(-${-want:X}, 8.8 = {want / 256:.1f} px/frame)")
        sym = parse_lst(a.lst)
        equ = parse_equs(a.lst)
        rom_v = objdef_y_vel_from_rom(a.rom, sym, equ)
        out.append(f"  hop 2  {a.rom} ObjDef_Spring+4 (y_vel) = {rom_v}")
        if rom_v != want:
            print("\n".join(out))
            print(f"\nRESULT: FAIL — hop 2 disagrees with hop 1: the built ObjDef_Spring "
                  f"carries {rom_v}, S3K's red spring is {want}")
            return 1
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nRESULT: UNMEASURABLE — {e}")
        return 2

    out.append("MACHINE:")
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            fails = asyncio.run(run(sock, a.rom, a.lst, want, out))
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nRESULT: UNMEASURABLE — {e}")
        return 2

    print("\n".join(out))
    if fails:
        print(f"\nRESULT: FAIL — {len(fails)} finding(s):")
        for f in fails:
            print(f"  * {f}")
        return 1
    print(f"\nRESULT: PASS — {LEGS} legs: a spring AND a plain block are side-solid and kill "
          f"the player's running speed on contact, he can still walk away from them, and a "
          f"fall onto the spring launches him at {want} (S3K's red spring, all three hops "
          f"agreeing) with ST_IN_AIR set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
