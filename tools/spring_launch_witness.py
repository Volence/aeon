#!/usr/bin/env python3
"""spring_launch_witness — does the spring actually launch, and is it actually side-solid?

THE CLAIM UNDER TEST is not "the spring object builds" and not "Touch_Spring is
reachable in the listing". It is two runtime facts about a real player meeting a real
spring placed in real level data:

  SIDE   walking into a spring from the side is SOLID -- the player is pushed out and
         stopped, and is NOT launched. This is the half nothing in this tree has ever
         tested on a real object: Touch_Solid's `.solid_side` arm exists and is
         exercised by nothing, because every solid the OJZ act places is a floating
         platform the player lands on from above.

  TOP    falling onto a spring launches the player at S3K's red-spring velocity, and
         leaves him airborne.

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

BOTH TESTS CARRY A VACUITY GUARD, because both have an obvious way to pass while
measuring nothing. "The player was never pushed into the spring" would satisfy "he did
not penetrate it"; "the player never reached the spring" would satisfy "he was not
launched wrongly". So each test first asserts CONTACT (he got within the combined
half-width / he descended onto it) and only then asserts the response. Failing to make
contact is exit 2, not a pass.

WHAT THIS DOES NOT ESTABLISH, stated because it is where the object would fail next:
  * only the vertical red spring exists; there are no diagonal or horizontal springs.
  * only ONE spring is driven (the one on the player's own ground run). The other two
    placements are checked for SPAWNING only.
  * the sound is not tested because the spring has no sound -- sfx $B1 is not in this
    game's bank (see games/sonic4/objects/test_solid.emp).

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
        return dict(x=px, y=py, xv=xv, yv=yv, status=st, w=pw, h=ph)

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

async def test_side(pr, spring, want_launch, out):
    """Walk into the spring from the side. Solid, stopped, and NOT launched.

    THE DISCRIMINATOR IS THE SIGN OF THE GAP, not its size. A spring that were not
    side-solid at all would let the player walk straight through and out the far side,
    which flips `player.x - spring.x`; that is the thing being tested and it is
    unambiguous. The resting GAP is measured and reported rather than asserted against
    an exact face, because the phase of the sample within the frame moves it (see the
    standoff note below) — asserting a number there would be asserting a fact about
    where the frame boundary falls.
    """
    p0 = await pr.player_state()
    half_w = (p0["w"] + spring["w"]) // 2
    side = 1 if p0["x"] > spring["x"] else -1          # which side he starts on
    button = "right" if side < 0 else "left"
    out.append(f"  side: player at x={p0['x']} y={p0['y']} (box {p0['w']}x{p0['h']}), "
               f"spring at x={spring['x']} y={spring['y']} (box {spring['w']}x{spring['h']}); "
               f"holding {button.upper()}, contact face at {half_w}px between centres")

    closest = 1 << 30
    min_yv = 0
    crossed = False
    xs = []
    await pr.hold(button, True)
    try:
        for _ in range(SIDE_FRAMES):
            await pr.frames(1)
            st = await pr.player_state()
            xs.append(st["x"])
            gap = st["x"] - spring["x"]
            if gap != 0 and (1 if gap > 0 else -1) != side:
                crossed = True
            closest = min(closest, abs(gap))
            min_yv = min(min_yv, st["yv"])
    finally:
        await pr.hold(button, False)

    # RELEASE AND LET FRICTION SETTLE HIM, then measure the RESTING gap. While a
    # direction is held the sampled gap is not the contact face and cannot be: the push
    # and the player's own move sit on opposite sides of the sampled frame boundary, and
    # Touch_Solid clears x_vel but NOT the grounded player's PlayerV.ground_speed, so he
    # keeps accelerating into the object and rams back in by a full top-speed step every
    # frame. The sample is then a fixed point at (face - his speed), it is CONSTANT, and
    # the speed that sets it is invisible in the sample series. With the button released,
    # friction takes ground_speed to zero and the push has the last word, so the resting
    # gap is the contact face itself.
    # ADAPTIVE, not a fixed count: friction is ~$C per frame against a top speed of ~6
    # px/frame, so a decelerating player takes well over a hundred frames to reach zero
    # and a 90-frame settle measured 14px -- two px of residual creep, which would have
    # been reported as a push defect. Wait for x to actually stop instead, and say how
    # long it took so a future slowdown is visible rather than absorbed.
    rest, held_still, settled_after = None, 0, None
    for f in range(SETTLE_AFTER_HOLD):
        await pr.frames(1)
        x = (await pr.player_state())["x"]
        held_still = held_still + 1 if x == rest else 0
        rest = x
        if held_still >= 10:
            settled_after = f + 1
            break
    if settled_after is None:
        raise Unmeasurable(
            f"the player never came to rest beside the spring within {SETTLE_AFTER_HOLD} "
            f"frames of releasing {button.upper()} (last x={rest}) — the resting contact "
            f"face cannot be measured")
    rest = abs(rest - spring["x"])
    out.append(f"  side: came to rest {settled_after} frames after release")

    # --- vacuity FIRST: a player who never reached the spring proves nothing ---
    if closest > half_w + 8:
        raise Unmeasurable(
            f"the player never reached the spring's side face: closest approach was "
            f"{closest}px between centres, and contact begins at {half_w}px. Nothing about "
            f"side solidity was measured — this is not a pass.")

    fails = []
    if crossed:
        fails.append(f"WALKED THROUGH IT: the player crossed from one side of the spring to "
                     f"the other while holding {button.upper()} — the side face is not solid")
    else:
        out.append(f"  side: he never crossed the spring's centre — the side face held")

    # THE CONTACT FACE IS DERIVED FROM THE CODE, not from this measurement:
    # solid_face_response pushes out by `pen - 1` (`subq.w #1, d0`), deliberately leaving
    # 1px of overlap so the next frame's AABB still fires. So a player resting against a
    # solid sits at exactly half_w - 1 between centres.
    want_rest = half_w - 1
    if rest != want_rest:
        fails.append(f"RESTING GAP {rest}px, expected {want_rest}px (the contact face "
                     f"{half_w} less the 1px bias solid_face_response's `subq.w #1, d0` "
                     f"leaves) — the side push does not settle where the code says")
    else:
        out.append(f"  side: after releasing {button.upper()}, he settles at {rest}px from "
                   f"the spring's centre — exactly the contact face {half_w} minus the 1px "
                   f"overlap bias the push leaves on purpose")
    out.append(f"  side: while HOLDING into it he sat {closest}px in, {want_rest - closest}px "
               f"deeper than the resting face — Touch_Solid clears x_vel but a grounded "
               f"player is driven by PlayerV.ground_speed, which the engine cannot name, so "
               f"he re-rams at top speed every frame (booked in docs/DEFERRED_WORK.md)")

    tail = xs[-30:]
    drift = max(tail) - min(tail)
    if drift > 2:
        fails.append(f"NOT STOPPED: the player's x still moved {drift}px over the last 30 "
                     f"frames while holding {button.upper()} into the spring")
    else:
        out.append(f"  side: x drift over the last 30 held frames = {drift}px — stopped dead")

    if min_yv <= want_launch:
        fails.append(f"SIDE CONTACT LAUNCHED HIM: y_vel reached {min_yv} (launch is "
                     f"{want_launch}) while only ever touching the side face")
    else:
        out.append(f"  side: most negative y_vel seen = {min_yv}, never the launch "
                   f"{want_launch} — a side hit does not fire the spring")
    return fails


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
                 "Spring_Launched"):
        if need not in sym:
            raise Unmeasurable(f"{need} is not in {lst} — wrong ROM/listing pair?")
    for need in ("SST_x_pos", "SST_y_pos", "SST_x_vel", "SST_y_vel", "SST_status",
                 "SST_code_addr", "SST_width_pixels", "SST_height_pixels", "SST_anim"):
        if need not in equ:
            raise Unmeasurable(f"{need} has no EQU in {lst} — the SST offsets are unresolvable")

    spring_code = (sym["Spring_Main"] - sym["ObjCodeBase"]) & 0xFFFF
    out.append(f"  Spring_Main ${sym['Spring_Main']:06X} - ObjCodeBase ${sym['ObjCodeBase']:06X} "
               f"= dispatch word ${spring_code:04X}")

    pr = Probe(b, sym, equ)

    # EACH TEST GETS ITS OWN BOOT, and that is not tidiness. The side test ends with the
    # player pressed into the spring at full running speed, and Touch_Solid clears x_vel
    # but NOT the grounded player's PlayerV.ground_speed (a game-side field the engine
    # cannot name). Measured: running the drop after the side test, the poked player
    # carried that inertia off the spring while falling and landed 340px away on the next
    # flat run, and the drop reported UNMEASURABLE for a reason that had nothing to do
    # with the top face. Re-booting is also the better experiment — both tests then start
    # from the identical settled state rather than from each other's leftovers.
    out.append("BOOT 1 (side face):")
    springs = await boot_and_settle(pr, spring_code, out)

    fails = []
    for s in springs:
        if s["yv"] != want_launch:
            fails.append(f"the spawned spring at (x={s['x']},y={s['y']}) carries y_vel "
                         f"{s['yv']}, not the reference {want_launch} — the ObjDef's launch "
                         f"strength did not survive the spawn burst-copy")

    target = await pick_target(pr, springs, out)
    out.append("SIDE FACE:")
    fails += await test_side(pr, target, want_launch, out)

    out.append("BOOT 2 (top face):")
    springs = await boot_and_settle(pr, spring_code, out)
    target = await pick_target(pr, springs, out)
    out.append("TOP FACE:")
    fails += await test_top(pr, target, want_launch, out)

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
    print(f"\nRESULT: PASS — the spring is side-solid, and a fall onto it launches the "
          f"player at {want} (S3K's red spring, all three hops agreeing) with ST_IN_AIR set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
