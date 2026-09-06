#!/usr/bin/env python3
"""spring_launch_witness — is a solid's SIDE face really solid, and do the springs launch?

THE CLAIM UNDER TEST is not "the spring object builds" and not "Touch_Spring is
reachable in the listing". It is eight runtime facts about a real player meeting real
objects placed in real level data. SIX DRIVE LEGS AND TWO CONTROLS, and the count is
asserted at the end so a leg that silently did not run cannot be read as a leg that
passed:

  L1 SPRING SIDE   walking into a spring from the side is SOLID -- the player is pushed
                   out, HIS RUNNING SPEED IS KILLED, and he is NOT launched.

  L2 BLOCK SIDE    the identical measurement against a plain COLLISION_SOLID block.
                   TWO SOLIDS, NOT ONE, and that is the point of the leg rather than
                   thoroughness: `solid_side_push` is a comptime template spliced into
                   Touch_Solid AND Touch_Spring, so the ROM holds TWO copies of the
                   side arm. A fix that showed up only on the spring would have been
                   made in the wrong place, and only a second solid can see that.

  L3 ESCAPE        having been stopped by a solid, the player can still WALK AWAY from
                   it. This is the control on L1/L2, not a courtesy check -- see "THE
                   ESCAPE LEG IS THE CONTROL" below.

  L4 TOP           falling onto a spring launches the player at S3K's red-spring
                   velocity, and leaves him airborne.

  L5 SIDE LAUNCH   walking into a LEFT-pointing spring ON THE FACE IT POINTS OUT OF
                   throws the player horizontally at the derived speed, writes that
                   speed into the GROUNDED driver too, and carries him away from it.

  L6 UNDERSIDE     JUMPING into a DOWN-pointing spring's underside from below throws
                   the player downward at the derived speed.

  C1 BACK FACE     the CONTROL on L5: the SAME side spring, hit on its BACK face, is a
                   plain solid -- pushed out, speed killed, NOT launched, and its fire
                   animation never starts. Without this leg L5 is nearly vacuous: it
                   would not distinguish "the spring launches" from "the spring launches
                   whatever touches it", which is what an object with no direction gate
                   at all would do and what L5 alone would happily call a pass.

  C2 TOP LAND      the CONTROL on the shared top face: landing on the TOP of a
                   SIDE-pointing spring must be an ordinary landing and must NOT produce
                   a sideways launch. This is the exact failure the SP-5 merge describes
                   -- without `y_vel < 0` on the top arm a sideways spring would hand the
                   player its ZERO y_vel and drop him airborne with no impulse, and with
                   the game hook still invoked its HORIZONTAL arm would write the
                   spring's x_vel into his inertia. A spring you fall through the top of,
                   sideways.

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

  (1) skdisasm at the pinned revision -- `word_22EF0`'s first TWO `dc.w` (the red and
      yellow magnitudes, both written in S3K's UP sense, i.e. negative) are parsed out
      of sonic3k.asm at 2fcd861c208f342b6d14df694c6422c74f20a4be. Nothing in THIS repo
      can change them.
  (2) the built ROM's own Spring_Launch table -- read out of the ROM file at the address
      the listing gives, and validated in FULL rather than at one entry: all four
      implemented directions at both strengths, eight vectors, each of which must be the
      axis and sign that direction's NAME requires at the magnitude (1) gives. This is
      what catches a spring whose velocity table was retuned away from the reference.
      It read ObjDef_Spring+4 until 2026-09-06; see objdef_y_vel_from_rom for why that
      stopped being the authority without stopping being readable.
  (3) the running machine -- the velocity the player actually receives at the launch
      hook must equal the (2) entry for the spring that threw him.

A mismatch anywhere is reported as which hop disagreed. If skdisasm is not available the
run exits 2 UNMEASURABLE; it never falls back to a literal.

HOP 2 DOES NOT KNOW THE SUBTYPE BIT LAYOUT AND IS NOT TOLD IT. `Spring_Launch` is indexed
by direction and strength, and the row for a direction is found from the LISTING's own
published `ObjSub_Spring__<Dir>_<Strength>` equates with the two field weights SOLVED FOR
rather than written down: the strength weight is `Up_Yellow - Up_Red`, and the direction
weight is the gcd of the four `*_Red` values. A hardcoded `>> 4` here would be a fourth
copy of the encoding that could silently drift from the three that already exist
(spring_subtype(), Spring_Init's shift-fold, and the placement JSON). The solve is then
CHECKED, not trusted: all eight entries are read and compared, so a wrong weight reads
wrong rows and goes loud rather than quiet. See spring_subtype_encoding().

THE HORIZONTAL SIGN IS THE ONE FACT TAKEN FROM READING, and the machine witnesses it
anyway. S3K writes its spring magnitudes in the UP sense, so Up = (0, m) and Down =
(0, -m) are forced; for the horizontal pair, sub_23190 builds a RIGHTWARD velocity from
the same magnitude and only then negates it under the flip bit (sonic3k.asm:47898), so
Right = (-m, 0) and Left = (m, 0). If that reading were backwards, L5 would not merely
report a sign: the spring would throw the player INTO itself and L5's "he ended up
further from it" assertion would go red on the machine, with no reference to consult.

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

THE THREE NEW LEGS DO NOT WALK IN FROM THE PLAYER'S SPAWN, and the reason is a measured
property of the level rather than a shortcut. SP-5 placed the side and underside springs
at y=632 and y=424 in OJZ act 1 section 0; the walkable surface a player reaches from the
spawn runs at y=525..573 across that whole span, and the three new springs are in
CHAMBERS above and below it, sealed off by terrain. Measured on this ROM: the two side
springs float at the ends of a 120px ledge at y=621 in a lower chamber, the up spring at
(700,632) sits between them and blocks the ledge with its own solid side face, and a
player launched off that up spring hits the chamber ceiling at y=578 -- 127px BELOW the
down spring at (700,424), which lives in a different chamber entirely. So the "bounce
corridor" the placement commit describes does not close, and no path from the spawn
reaches any of the three. Each new leg therefore SEATS the player in the chamber its
spring lives in (the same `put_player` poke L4 already uses for its drop) and then PLAYS
from there -- walks, jumps, falls -- so everything the leg asserts is physics. The
placement gap is a real finding and is booked, not papered over.

WHAT THIS DOES NOT ESTABLISH, stated because it is where the object would fail next:
  * the two DIAGONAL directions still do not exist -- they decode to a (0, 0) vector and
    are a plain block on all four faces. Nothing below drives one.
  * the YELLOW strength is validated in the ROM's table (hop 2) but never driven: every
    placement in section 0 is red.
  * the RIGHT spring is driven on its TOP face only (C2). Its launching face is checked
    by symmetry with the LEFT spring's, not by its own drive.
  * no leg reaches any of the three new springs by WALKING FROM THE SPAWN, because no
    such path exists in this level -- see the paragraph above.
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
import math
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

# --- SP-5c, the three new springs. Every offset below is a POSITION IN A CHAMBER the
# player cannot walk to (see the docstring); each is chosen against a property of the
# chamber that was measured on this ROM, and each is ASSERTED at the start of its leg so
# a level edit that invalidates it goes UNMEASURABLE instead of quietly measuring
# something else.
SIDE_APPROACH_DX = 40    # px from the side spring's centre the L5 walk starts. Outside
                         # the contact face (17) by more than a body width, and inside
                         # the measured 120px ledge the two side springs bracket.
SIDE_SEAT_DY = 20        # px above the spring's centre to seat him for that walk — the
                         # ledge is 11px above it and this is a short, safe drop onto it.
SIDE_SETTLE = 90         # frames to land and come to rest on the ledge
SIDE_LAUNCH_FRAMES = 240 # frames of walking allowed before the launch is called absent
BACK_DX = 34             # px from the centre C1's back-face approach starts, on the far
                         # side. Twice the contact face, so he starts clear of the box.
BACK_FRAMES = 16         # frames sampled across the back-face contact. He is airborne
                         # there (the ledge does not extend past the spring) and falls
                         # out of the chamber after ~20.
SIDE_DROP_HEIGHT = 62    # px above the side spring's centre for C2's top-land drop.
                         # NOT L4's 72: measured, this chamber's ceiling sits 88px above
                         # the spring and a 72px drop starts the player inside it.
TOP_LAND_FRAMES = 90     # frames allowed for that drop to land
JUMP_GROUND_DY = 100     # px BELOW the down spring's centre to seat the L6 jumper. The
                         # floor there was measured at 93-110px below it across the span
                         # the jump uses; the seat falls onto it and the settle asserts
                         # he is grounded, so the exact number only has to be above it.
JUMP_DX = 30             # px to the LEFT of the down spring the L6 jump starts from. The
                         # floor under it slopes, so a standing jump drifts right; the
                         # leg holds TOWARD the spring and this offset is what puts the
                         # apex under it. Measured to work over a 15px window of starts.
JUMP_TRACE_FRAMES = 45   # frames of ascent sampled before the underside contact
DRIVE_LEGS = 6           # L1 · L2 · L3 · L4 · L5 side launch · L6 underside launch
CONTROL_LEGS = 2         # C1 back face · C2 top land
LEGS = DRIVE_LEGS + CONTROL_LEGS

# The four directions this engine implements, and the two strengths, spelled exactly as
# the published `ObjSub_Spring__<Dir>_<Strength>` equates spell them — these strings are
# the ONLY thing that ties this file to the game's naming, and a rename goes loud.
SPRING_DIRS = ("Up", "Right", "Down", "Left")
SPRING_STRENGTHS = ("Red", "Yellow")
SPRING_ENTRY_BYTES = 4   # one Spring_Launch entry is the (x_vel, y_vel) word pair

# THE AXIS AND SIGN EACH DIRECTION NAME REQUIRES, at a magnitude `m` written in S3K's UP
# sense (negative). Up and Down are forced by that sense alone. The horizontal pair comes
# from sub_23190 (sonic3k.asm:47898), which builds the RIGHTWARD velocity and negates it
# under the flip bit — so the un-negated case is Right. See the docstring for why a
# backwards reading here cannot pass L5 anyway.
SPRING_AXIS = {
    "Up":    lambda m: (0, m),
    "Down":  lambda m: (0, -m),
    "Right": lambda m: (-m, 0),
    "Left":  lambda m: (m, 0),
}
# The two animation ids, from games/sonic4/objects/test_solid.emp. They are `pub const`
# and a `const` emits NOTHING into a listing, so unlike every other number in this file
# they cannot be read back from the build. What anchors them instead is the machine: each
# leg asserts the spring reads SPRING_ANIM_IDLE BEFORE its contact, so a build where 0 is
# not idle goes UNMEASURABLE at the top of the leg rather than passing on a stale value.
SPRING_ANIM_IDLE = 0
SPRING_ANIM_FIRE = 1

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

def s3k_spring_magnitudes() -> tuple:
    """`word_22EF0`'s first TWO entries at the pinned skdisasm revision (:47654-47656).

    Located by the LABEL, not by line number: a line number is a fact about one checkout
    and would go quietly wrong against a different one, while the label is what the
    engine's own comments cite.

    Returns (red, yellow), both in S3K's UP sense and therefore both NEGATIVE. It read
    only the first until SP-5c; the second is what lets hop 2 validate the whole table
    rather than one entry, and a table half-checked is a table where a yellow row can be
    anything at all.
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
    vals = []
    for l in lines[at + 1:at + 6]:
        m = re.search(r"dc\.w\s+(-?)\$([0-9A-Fa-f]+)", l)
        if not m:
            if vals:
                break
            continue
        v = int(m.group(2), 16)
        vals.append(-v if m.group(1) else v)
        if len(vals) == len(SPRING_STRENGTHS):
            break
    if len(vals) != len(SPRING_STRENGTHS):
        raise Unmeasurable(f"found `word_22EF0:` but only {len(vals)} `dc.w` under it — "
                           f"{len(SPRING_STRENGTHS)} magnitudes (red, yellow) are needed")
    if not all(v < 0 for v in vals):
        raise Unmeasurable(f"word_22EF0 holds {vals}; S3K writes spring magnitudes in the "
                           f"UP sense and they must all be negative — the axis convention "
                           f"every expectation below is built on does not hold")
    if abs(vals[0]) <= abs(vals[1]):
        raise Unmeasurable(f"word_22EF0[0] {vals[0]} is not the STRONGER of {vals} — red is "
                           f"supposed to be the strong spring, so the two entries are in "
                           f"the other order and every strength expectation is swapped")
    return tuple(vals)


def s3k_red_spring_velocity() -> int:
    """Hop 1 for L1-L4, unchanged: the RED magnitude alone."""
    return s3k_spring_magnitudes()[0]


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
    """The UP/RED spring's launch y_vel, read straight out of the ROM image.

    IT USED TO READ `ObjDef_Spring+4`, AND THAT WENT SILENTLY WRONG. The archetype
    carried the launch velocity until 2026-09-06, when the subtype decode moved it into
    `Spring_Launch` — a 64-byte table indexed by direction and strength — and stopped
    seeding the ObjDef at all. `objdef()` defaults an absent field to 0, so this
    function kept reading a real address in a real ROM and returning a real number, and
    that number was 0. It never raised; hop 2 simply disagreed with hop 1 and the whole
    witness exited 1 on a tree where nothing was broken. Nothing pointed at it, because
    a ROM offset does not stop being readable when it stops being the authority.

    The authority is now `Spring_Launch`'s FIRST ENTRY: direction 0 (up), strength 0
    (red), held as the (x_vel, y_vel) pair the object carries for the rest of its life.
    So x is at +0 and the y this returns is at +2.

    x IS CHECKED TO BE ZERO, and that check is what keeps this honest rather than
    tidy: it is the one fact that distinguishes "I read the up spring's y" from "I read
    some word two bytes into a table whose axis order I assumed". A table that swapped
    its axes would otherwise hand back a plausible number.
    """
    for name in ("Spring_Launch",):
        if name not in sym:
            raise Unmeasurable(f"{name} is not in the listing — is this a build with the spring? "
                               "(before 2026-09-06 the launch velocity lived in ObjDef_Spring+4)")
    data = Path(rom).read_bytes()
    at = sym["Spring_Launch"]
    if at + 4 > len(data):
        raise Unmeasurable(f"Spring_Launch at ${at:06X} is past the end of {rom}")
    x = s16((data[at + 0] << 8) | data[at + 1])
    y = s16((data[at + 2] << 8) | data[at + 3])
    if x != 0:
        raise Unmeasurable(
            f"Spring_Launch[up,red].x = {x}, expected 0 — the first entry is supposed to be "
            f"the UP spring, whose launch is purely vertical. Either the table's direction "
            f"order changed (up is no longer direction 0) or its two words are (y, x) rather "
            f"than (x, y), and the y read here would be the wrong word either way")
    return y


def spring_subtype_encoding(equ: dict) -> tuple:
    """Solve the subtype bit layout out of the LISTING's own published equates.

    Returns (dir_index_by_name, subtype_value_by_(name, strength), weak_weight,
    dir_weight).

    WHY SOLVE RATHER THAN WRITE `>> 4`. The encoding already exists in three places —
    `spring_subtype()` in test_solid.emp, `Spring_Init`'s `lsr.w #1 / andi.w #$38` fold,
    and the hand-written subtype numbers in the placement JSON. A fourth copy here would
    be a fourth thing to drift, and the drift would be silent: a witness reading the
    wrong Spring_Launch row still reads a real vector out of a real table.

    THE SOLVE. `ObjSub_Spring__Up_Red` is the origin and must be 0 (test_solid.emp's
    oldest ensure holds it there, because the three springs already placed in OJZ act 1
    carry placement word $0000). The strength field's weight is then
    `Up_Yellow - Up_Red`, read straight off. The direction field's weight is the gcd of
    the four `*_Red` values, which is exactly the largest number they can all be
    multiples of.

    THE SOLVE IS CHECKED, NOT TRUSTED, and that is what makes it safe. The gcd can
    OVERESTIMATE the direction weight if every implemented direction index happened to
    share a factor — four even indices would return twice the true weight and halve every
    row number. Nothing here can rule that out from the equates alone, so nothing tries:
    spring_launch_table() reads all eight entries at the rows this returns and requires
    each to be the vector its direction NAME demands. A doubled weight reads a
    neighbouring direction's row and fails loudly on the first name it checks.
    """
    vals = {}
    for d in SPRING_DIRS:
        for s in SPRING_STRENGTHS:
            name = f"ObjSub_Spring__{d}_{s}"
            if name not in equ:
                raise Unmeasurable(
                    f"{name} has no EQU in the listing — the subtype encoding cannot be "
                    f"solved, and every SP-5c leg indexes Spring_Launch through it. "
                    f"(`pub equ` lands in the Equate Table; a `pub const` emits nothing, "
                    f"so a name changed from one to the other looks exactly like this.)")
            vals[(d, s)] = equ[name]
    if vals[("Up", "Red")] != 0:
        raise Unmeasurable(
            f"ObjSub_Spring__Up_Red is ${vals[('Up', 'Red')]:02X}, not 0 — subtype 0 is no "
            f"longer up/red, which silently re-aims the three springs already placed in "
            f"OJZ act 1 with placement word $0000 and invalidates L1/L2/L4's subject")
    weak_w = vals[("Up", "Yellow")] - vals[("Up", "Red")]
    if weak_w <= 0:
        raise Unmeasurable(f"the strength field has weight {weak_w} (Up_Yellow "
                           f"${vals[('Up', 'Yellow')]:02X} - Up_Red "
                           f"${vals[('Up', 'Red')]:02X}) — it must be positive")
    dir_w = 0
    for d in SPRING_DIRS:
        dir_w = math.gcd(dir_w, vals[(d, "Red")])
    if dir_w == 0 or dir_w <= weak_w:
        raise Unmeasurable(
            f"the direction field solves to weight {dir_w} against a strength weight of "
            f"{weak_w} — the two fields overlap or every direction is 0, and no row index "
            f"derived from them would mean anything")
    dirs = {}
    for d in SPRING_DIRS:
        red = vals[(d, "Red")]
        if red % dir_w:
            raise Unmeasurable(f"ObjSub_Spring__{d}_Red ${red:02X} is not a multiple of the "
                               f"solved direction weight ${dir_w:02X}")
        for i, s in enumerate(SPRING_STRENGTHS):
            want = red + i * weak_w
            if vals[(d, s)] != want:
                raise Unmeasurable(
                    f"ObjSub_Spring__{d}_{s} is ${vals[(d, s)]:02X}, but the solved layout "
                    f"says ${want:02X} (direction ${red:02X} + strength {i} x ${weak_w:02X}) "
                    f"— the strengths of one direction are not consecutive in the encoding")
        dirs[d] = red // dir_w
    if len(set(dirs.values())) != len(dirs):
        raise Unmeasurable(f"two directions solve to the same row: {dirs} — the direction "
                           f"weight is wrong and the rows would collide")
    return dirs, vals, weak_w, dir_w


def spring_launch_table(rom: str, sym: dict, equ: dict, mags: tuple) -> tuple:
    """HOP 2, WHOLE: every implemented (direction, strength) vector in the ROM image.

    Returns (vectors_by_(dir, strength), disagreements). A disagreement is a string; the
    caller reports them as a hop-2/hop-1 FAIL exactly the way the single-entry check
    already did, and does not fall back to anything.

    Each entry is the (x_vel, y_vel) word pair the object carries for the rest of its
    life, at row `dir * len(SPRING_STRENGTHS) + strength`, entries being
    SPRING_ENTRY_BYTES apart. Neither the row count nor the direction count is needed to
    INDEX it — only the two-strengths-per-direction shape the published names enumerate —
    but every read is bounds-checked against the file.
    """
    if "Spring_Launch" not in sym:
        raise Unmeasurable("Spring_Launch is not in the listing — is this a build with the "
                           "spring? (before 2026-09-06 the launch velocity lived in "
                           "ObjDef_Spring+4)")
    dirs, vals, weak_w, dir_w = spring_subtype_encoding(equ)
    data = Path(rom).read_bytes()
    base = sym["Spring_Launch"]
    got, bad = {}, []
    for d in SPRING_DIRS:
        for si, s in enumerate(SPRING_STRENGTHS):
            at = base + (dirs[d] * len(SPRING_STRENGTHS) + si) * SPRING_ENTRY_BYTES
            if at + SPRING_ENTRY_BYTES > len(data):
                raise Unmeasurable(f"Spring_Launch[{d},{s}] at ${at:06X} is past the end of "
                                   f"{rom} ({len(data)} bytes)")
            x = s16((data[at + 0] << 8) | data[at + 1])
            y = s16((data[at + 2] << 8) | data[at + 3])
            got[(d, s)] = (x, y)
            want = SPRING_AXIS[d](mags[si])
            if (x, y) != want:
                bad.append(f"Spring_Launch[{d},{s}] (row {dirs[d]}, entry {si}, "
                           f"${at:06X}) = ({x}, {y}), reference ({want[0]}, {want[1]}) — "
                           f"S3K's {s.lower()} magnitude {mags[si]} on the axis and sign "
                           f"the name {d} requires")
    return got, dirs, vals, bad, (weak_w, dir_w, base)



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
                # THE LAUNCH VECTOR, BOTH HALVES, and the subtype it was decoded
                # from. Since SP-5 (2026-09-06) a spring's direction lives in this
                # pair and not in its archetype, so reading y_vel alone would call
                # a leftward spring a broken upward one.
                xv=s16(await self.word(sst + self.equ["SST_x_vel"])),
                yv=s16(await self.word(sst + self.equ["SST_y_vel"])),
                sub=int(await self.rd(sst + self.equ["SST_subtype"], 1), 16),
            ))
        return found

    async def frames(self, n=1):
        await self.b.call("emulator/run_frames", {"frames": n})

    async def hold(self, button, down):
        await self.b.call("emulator/hold", {"buttons": [button], "down": bool(down)})

    async def anim(self, sst):
        return int(await self.rd(sst + self.equ["SST_anim"], 1), 16)

    async def run_to_hook(self, max_frames):
        """Stop the machine INSIDE Game.spring_launched, before the player's own tick.

        The only instant at which "the launch velocity" is a well-defined quantity — see
        test_top's header for the frame-boundary reading this avoids. Note the hook has
        not yet executed its FIRST instruction here, so the spring's `anim` still reads
        SPRING_ANIM_IDLE at this stop; every leg that wants the fire animation as a
        witness must step a frame first.
        """
        return await self.b.call("emulator/run_to",
                                 {"addr": hex(self.sym["Spring_Launched"]),
                                  "maxFrames": max_frames})

    async def put_player(self, x=None, y=None, xv=None, yv=None, gsp=None):
        if x is not None:
            await write_bytes(self.b, self.player + self.equ["SST_x_pos"], f"{x & 0xFFFF:04X}0000")
        if y is not None:
            await write_bytes(self.b, self.player + self.equ["SST_y_pos"], f"{y & 0xFFFF:04X}0000")
        if xv is not None:
            await write_bytes(self.b, self.player + self.equ["SST_x_vel"], f"{xv & 0xFFFF:04X}")
        if yv is not None:
            await write_bytes(self.b, self.player + self.equ["SST_y_vel"], f"{yv & 0xFFFF:04X}")
        if gsp is not None:
            await write_bytes(self.b, self.player + self.equ["_pl_gsp"], f"{gsp & 0xFFFF:04X}")


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

    THE DISCRIMINATOR FOR THE SPEED KILL IS THE STEADY STATE WHILE HOLDING, and both of
    its numbers are derived from the code rather than from a run:

      DEPTH   the push moves the player out by `pen - 1` (`subq.w #1, d0` in
              solid_face_response), deliberately leaving 1px of overlap so the next
              frame's AABB still fires, and it writes the INTEGER part of x_pos only.
              So a player whose speed is killed can sit at most 1px inside the resting
              face -- the subpixel sawtooth PHYS_ACCEL builds between pushes. A player
              whose speed is NOT killed re-accelerates to the running cap and parks a
              full top-speed step further in, which is the flat 10-against-17 SP-1
              measured.
      SPEED   his ground speed may be at most ONE frame of running acceleration
              (PHYS_ACCEL, read from the listing): the kill zeroes it and the next
              tick's input adds one step back. Under the defect it is PHYS_TOP_SPEED.

    NEITHER IS ASSERTED ON THE ENTRY FRAME, and that is not a softened bar. TouchResponse
    runs before the player's own tick, so the frame on which he first overlaps is always
    one uncorrected step deep at his full approach speed -- true of any once-per-frame
    collision test, S3K's included, and true with the fix in place. The entry frame is
    reported; what is asserted is every frame after it.
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
    contact_frames = 0
    entry_gap = None         # how deep the FIRST overlapping frame put him
    entry_gsp = None
    samples = []             # (|gap|, |gsp|) per held frame, for the steady-state tail
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
            samples.append((abs(gap), abs(st["gsp"])))
            # IN CONTACT means the AABB overlaps, which is the condition under which the
            # side arm runs at all -- the same `< half_w` the engine tests. Sampling
            # OUTSIDE that window would fold his approach run into the "while pushing"
            # number and make the defect invisible.
            if abs(gap) < half_w:
                if entry_gap is None:
                    entry_gap, entry_gsp = abs(gap), abs(st["gsp"])
                contact_frames += 1
            else:
                approach_top_gsp = max(approach_top_gsp, abs(st["gsp"]))
    finally:
        await pr.hold(button, False)

    # THE ASSERTED NUMBERS ARE THE STEADY STATE, NOT THE ENTRY FRAME, and the difference
    # is a real property of the engine rather than a convenience. TouchResponse runs
    # BEFORE the player's own tick in a frame (measured: on the frame he first overlaps,
    # the frame-boundary sample still holds his full approach speed, because the pass
    # that would kill it ran while he was still outside the box). So the entry frame
    # ALWAYS shows one uncorrected step of penetration and one uncorrected speed, in any
    # implementation that tests collision once per frame -- S3K included. What
    # distinguishes a killed speed from an unkilled one is what happens on every frame
    # AFTER that, which is the fixed point SP-1 described: under the defect he sat 6px
    # inside the face at the full running cap, FOREVER; under the fix he is pushed back
    # to the face and stays there.
    tail = samples[-30:]
    steady_gap = min(g for g, _ in tail)
    steady_gsp = max(v for _, v in tail)

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
    if contact_frames == 0 or entry_gap is None:
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

    # ---- SP-1, measurement 1 of 3: how deep he sits while PUSHING ----
    # The bound is want_rest - 1, and that 1px is derived rather than allowed for. The
    # push writes the INTEGER part of x_pos (`add.w d0, x_pos`) and leaves the 16.16
    # subpixel alone, while a killed player still gains PHYS_ACCEL every tick — 12/65536
    # of a pixel — so the subpixel creeps until it carries into the integer, one pixel,
    # and the next frame's push takes it straight back. A sawtooth of exactly 1px is
    # therefore the FLOOR for this engine, and it is two orders below the 6px fixed point
    # the defect held (the two regimes are 15-16 against a flat 10).
    accel = pr.equ["PHYS_ACCEL"]
    top = pr.equ["PHYS_TOP_SPEED"]
    creep_floor = want_rest - 1
    out.append(f"  {leg}: entry frame — the one uncorrected step, before any push: "
               f"{entry_gap}px between centres carrying {entry_gsp} (8.8). TouchResponse "
               f"runs before the player's tick, so this frame is uncorrectable by design "
               f"and is NOT what is asserted")
    if steady_gap < creep_floor:
        fails.append(f"{leg}: SP-1 PENETRATION: over the last {len(tail)} held frames he sat "
                     f"as deep as {steady_gap}px between centres, {want_rest - steady_gap}px "
                     f"INSIDE the {want_rest}px resting face (floor {creep_floor}px, the "
                     f"1px subpixel sawtooth). He is being pushed out and walking straight "
                     f"back in every frame, which is what an unkilled ground speed looks "
                     f"like")
    else:
        out.append(f"  {leg}: steady state over the last {len(tail)} held frames — deepest "
                   f"{steady_gap}px against a {want_rest}px resting face, i.e. within the "
                   f"1px subpixel sawtooth and never a running step inside")

    # ---- SP-1, measurement 2 of 3: the speed he carries while pushing ----
    contact_top_gsp = steady_gsp
    # The approach number is NOT the comparison baseline and is reported only as the
    # vacuity witness (he was actually running). It is smaller than the in-contact
    # number even under the defect, because the object sits close enough to his spawn
    # that he is still accelerating when he first overlaps it; what the defect does is
    # let him go on accelerating INSIDE the box, all the way to the cap. The baseline
    # that means something is PHYS_TOP_SPEED, the speed he is running at.
    if contact_top_gsp > accel:
        fails.append(f"{leg}: SP-1 GROUND SPEED: over the last {len(tail)} held frames, with "
                     f"{button.upper()} pressed into the face, he carried up to "
                     f"{contact_top_gsp} (8.8) — {100 * contact_top_gsp // top}% of the "
                     f"PHYS_TOP_SPEED {top} running cap, and past the {accel} bound "
                     f"(PHYS_ACCEL, the one frame of re-acceleration a killed speed can "
                     f"regain). His inertia is not being killed on contact")
    else:
        out.append(f"  {leg}: ground speed in the steady state peaked at {contact_top_gsp} "
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


# ---------------------------------------------------------------- SP-5c: the new legs

async def seat_and_settle(pr, x, y, out, what, want_grounded=True):
    """Put the player somewhere in the chamber and let PHYSICS take it from there.

    Every SP-5c leg starts this way for the reason the docstring gives: the three new
    springs are in chambers no path from the spawn reaches. The poke is a POSITION only —
    the settle that follows is the engine's own ground probe, and its result is asserted
    rather than assumed, so a level edit that moves the floor makes the leg UNMEASURABLE
    instead of quietly measuring a player standing somewhere else.
    """
    await pr.put_player(x=x, y=y, xv=0, yv=0, gsp=0)
    got = await pr.player_state()
    if got["x"] != x or got["y"] != y:
        raise Unmeasurable(f"{what}: the seat poke did not take — asked for ({x},{y}), the "
                           f"slot reads ({got['x']},{got['y']})")
    await pr.frames(SIDE_SETTLE)
    st = await pr.player_state()
    airborne = (st["status"] >> ST_IN_AIR) & 1
    if want_grounded and airborne:
        raise Unmeasurable(
            f"{what}: seated at ({x},{y}) the player is still AIRBORNE {SIDE_SETTLE} frames "
            f"later (now at ({st['x']},{st['y']}) y_vel {st['yv']}, status ${st['status']:02X}) "
            f"— there is no floor under that seat any more, so the walk this leg needs "
            f"cannot happen")
    out.append(f"  {what}: seated at ({x},{y}), settled to ({st['x']},{st['y']}) "
               f"status ${st['status']:02X} box {st['w']}x{st['h']}")
    return st


def launch_side_of(spring):
    """Which side of a horizontal spring is the one it throws from.

    Touch_Spring launches when the sign of the player's delta_x agrees with the sign of
    the spring's own x_vel, so the launching face is the one x_vel POINTS AT: -1 for a
    leftward spring (its left face), +1 for a rightward one. Read from the spawned
    object's live velocity pair, never from its subtype — that is the whole point of the
    SP-5 seam, and a leg that decoded the subtype itself would stop testing the thing the
    engine actually reads.
    """
    if spring["xv"] == 0:
        raise Unmeasurable(f"the spring at (x={spring['x']},y={spring['y']}) carries x_vel 0 "
                           f"— it is not a horizontal spring and has no launching side")
    return 1 if spring["xv"] > 0 else -1


async def test_side_launch(pr, spring, want, out, leg):
    """L5 — walk into a side spring's LAUNCHING face and be thrown horizontally.

    THREE THINGS ARE ASSERTED AND THEY FAIL FOR DIFFERENT REASONS.

      the ENGINE-side launch    x_vel at the hook must be EXACTLY the vector the ROM's
                                Spring_Launch table holds for this spring's direction and
                                strength. Exact, not a threshold: Touch_Spring copies the
                                spring's own word and nothing has integrated yet.
      the GAME-side launch      one frame later the GROUNDED driver (PlayerV.ground_speed,
                                located through the `_pl_gsp` offset the game exports)
                                must carry it too. This is the half that only
                                Game.spring_launched's horizontal arm can write, and
                                without it Ground_Move_Cap rebuilds x_vel from a stale
                                inertia on the very next tick and the launch is erased —
                                which is the same wall Game.solid_pushed exists for. The
                                bound allows exactly one frame of PHYS_FRICTION, derived,
                                because a frame has passed.
      he actually LEFT          his distance from the spring must grow by at least half
                                one launch step. A walking player covers ~2px/frame and
                                the launch is 16, so the two regimes cannot be confused;
                                this is also the assertion that would catch a horizontal
                                sign read backwards, with no reference consulted.
    """
    side = launch_side_of(spring)
    button = "right" if side < 0 else "left"       # he starts ON the launching side
    p0 = await pr.player_state()
    half_w = (p0["w"] + spring["w"]) // 2
    dx0 = p0["x"] - spring["x"]
    if abs(dx0) <= half_w:
        raise Unmeasurable(
            f"{leg}: the player settled {abs(dx0)}px from the spring's centre, already "
            f"inside its {half_w}px contact face — he would be launched before taking a "
            f"step and nothing about walking into it would be measured")
    if (1 if dx0 > 0 else -1) != side:
        raise Unmeasurable(
            f"{leg}: the player settled on the side x={dx0:+d}, but this spring's x_vel "
            f"{spring['xv']} points the other way — he is on its BACK face, which is C1's "
            f"experiment and the opposite of this one")
    if await pr.anim(spring["sst"]) != SPRING_ANIM_IDLE:
        raise Unmeasurable(f"{leg}: the spring is already animating before the walk starts")
    out.append(f"  {leg}: spring at (x={spring['x']},y={spring['y']}) sub=${spring['sub']:02X} "
               f"launch=({spring['xv']},{spring['yv']}); its launching face is the "
               f"{'RIGHT' if side > 0 else 'LEFT'} one. Player {abs(dx0)}px out on that "
               f"side, holding {button.upper()} into it (contact face {half_w}px)")

    approach_top = 0
    reached_box = False
    await pr.hold(button, True)
    try:
        for _ in range(SIDE_LAUNCH_FRAMES):
            await pr.frames(1)
            st = await pr.player_state()
            if abs(st["x"] - spring["x"]) < half_w:
                reached_box = True
                break
            # TOWARD the spring only: a sample taken while he is drifting the other way
            # would let a stationary player pass the vacuity check below.
            if (1 if st["gsp"] > 0 else -1) != side and st["gsp"] != 0:
                approach_top = max(approach_top, abs(st["gsp"]))
        if not reached_box:
            st = await pr.player_state()
            raise Unmeasurable(
                f"{leg}: {SIDE_LAUNCH_FRAMES} frames of holding {button.upper()} never took "
                f"the player inside the spring's {half_w}px contact face — he ended at "
                f"(x={st['x']},y={st['y']}) status ${st['status']:02X}, "
                f"{abs(st['x'] - spring['x'])}px away. Either the ledge he was walking "
                f"along no longer reaches the spring or something solid stopped him first; "
                f"either way no side launch was measured and this is not a pass.")
        if approach_top == 0:
            raise Unmeasurable(
                f"{leg}: the player carried no ground speed TOWARD the spring on his "
                f"approach — a stationary player parked inside the box would satisfy every "
                f"assertion below without walking into anything")
        r = await pr.run_to_hook(4)
    finally:
        await pr.hold(button, False)

    if not r.get("reached"):
        st = await pr.player_state()
        raise Unmeasurable(
            f"{leg}: the player entered the spring's contact face on its LAUNCHING side and "
            f"Spring_Launched was NOT invoked within 4 frames — he is at "
            f"(x={st['x']},y={st['y']}) x_vel={st['xv']} ground_speed={st['gsp']}. The side "
            f"face did something, but it was not a launch, so the launch velocity has no "
            f"value to compare and this is UNMEASURABLE rather than a number that failed.")

    st = await pr.player_state()
    fails = []
    dx = st["x"] - spring["x"]
    out.append(f"  {leg}: stopped INSIDE Spring_Launched (${pr.sym['Spring_Launched']:06X}) "
               f"with the player {dx:+d}px from the spring's centre, {approach_top} (8.8) of "
               f"walk behind him")
    if abs(dx) >= half_w or (1 if dx > 0 else -1) != side:
        fails.append(f"{leg}: the hook fired with the player {dx:+d}px out — not inside the "
                     f"{half_w}px contact face on the launching side. Something else "
                     f"launched him and this leg's subject is not the spring it names")
    if st["xv"] != want:
        fails.append(f"{leg}: SIDE LAUNCH VELOCITY {st['xv']} at the hook, reference {want} "
                     f"(difference {st['xv'] - want})")
    else:
        out.append(f"  {leg}: x_vel at the hook = {st['xv']} == the ROM's "
                   f"Spring_Launch[Left,Red].x {want} ({want / 256:.1f} px/frame) — the "
                   f"engine-side launch is the derived one")

    await pr.frames(1)
    a1 = await pr.player_state()
    friction = pr.equ["PHYS_FRICTION"]
    if (1 if a1["gsp"] > 0 else -1) != (1 if want > 0 else -1) or \
            abs(a1["gsp"]) < abs(want) - friction:
        fails.append(f"{leg}: THE GROUNDED DRIVER DID NOT GET IT: one frame after the hook "
                     f"his ground_speed is {a1['gsp']}, against the {want} launch less one "
                     f"frame of PHYS_FRICTION {friction} (floor {abs(want) - friction} in "
                     f"magnitude, matching sign). Game.spring_launched's horizontal arm is "
                     f"not writing PlayerV.ground_speed, and Ground_Move_Cap rebuilds x_vel "
                     f"from it every tick — the launch is erased on the next frame")
    else:
        out.append(f"  {leg}: one frame on, ground_speed = {a1['gsp']} — the {want} launch "
                   f"less at most one PHYS_FRICTION step ({friction}). The GROUNDED driver "
                   f"carries it, not just the engine's x_vel")
    fire = await pr.anim(spring["sst"])
    if fire != SPRING_ANIM_FIRE:
        fails.append(f"{leg}: the spring's anim is {fire}, not SPRING_ANIM_FIRE "
                     f"{SPRING_ANIM_FIRE}, one frame after the launch — the fire script "
                     f"never started and a second hit would show no spring motion")
    else:
        out.append(f"  {leg}: the spring's anim is now {fire} — the fire script is running")

    gap0 = abs(dx)
    for _ in range(2):
        await pr.frames(1)
    a3 = await pr.player_state()
    gap = abs(a3["x"] - spring["x"])
    step_px = abs(want) // 256
    floor_px = step_px // 2
    if gap - gap0 < floor_px:
        fails.append(f"{leg}: HE DID NOT LEAVE: three frames after a {step_px}px/frame launch "
                     f"he is {gap}px from the spring's centre against {gap0}px at the hook, "
                     f"a gain of {gap - gap0}px under the {floor_px}px floor (half one launch "
                     f"step). He was thrown INTO the spring, or not thrown at all")
    else:
        out.append(f"  {leg}: three frames on he is {gap}px out (was {gap0}px), +{gap - gap0}px "
                   f"AWAY from the spring against a {floor_px}px floor — a walking player "
                   f"covers ~2px/frame, so this is the launch and not the walk")
    return fails


async def test_back_face(pr, spring, want, out, leg):
    """C1 — the same side spring's BACK face is a plain solid, and does NOT launch.

    WITHOUT THIS LEG, L5 IS NEARLY VACUOUS. "The spring threw him" and "the spring throws
    whatever touches it" produce the same reading on L5, and the second is what an object
    with no direction gate does — which is not a hypothetical, it is what deleting one
    `bmi` from Touch_Spring's side arm leaves behind. Only a hit on the OTHER face
    separates them.

    HE IS AIRBORNE HERE AND THAT IS THE CHAMBER'S DOING, not a softening: the ledge the
    L5 walk uses ends AT the spring, so there is no floor on its far side to walk in
    along. Airborne is if anything the sharper test of "not launched" — his x_vel is the
    only thing moving him, so a launch would be unmissable and the solid response has
    nothing else to hide behind.

    THE ANIMATION IS THE HOOK WITNESS. Game.spring_launched's first act is to restart the
    fire animation, so an `anim` that never leaves SPRING_ANIM_IDLE across the whole
    contact window is the hook never having run — a direct observation, not an inference
    from the absence of a velocity.
    """
    side = launch_side_of(spring)
    back = -side
    start_x = spring["x"] + back * BACK_DX
    approach = -back * pr.equ["PHYS_TOP_SPEED"]     # moving INTO the back face
    await pr.put_player(x=start_x, y=spring["y"], xv=approach, yv=0, gsp=approach)
    got = await pr.player_state()
    if got["x"] != start_x or got["y"] != spring["y"]:
        raise Unmeasurable(f"{leg}: the poke did not take — asked for ({start_x},"
                           f"{spring['y']}), the slot reads ({got['x']},{got['y']})")
    half_w = (got["w"] + spring["w"]) // 2
    out.append(f"  {leg}: spring at (x={spring['x']},y={spring['y']}) launches "
               f"{'RIGHT' if side > 0 else 'LEFT'} ({spring['xv']}); the player is placed "
               f"{BACK_DX}px out on its BACK face at x={start_x} carrying {approach} (8.8) "
               f"straight into it, contact face {half_w}px")

    closest, peak_xv, peak_gsp, anim_seen = 1 << 30, 0, 0, set()
    rows, wrong_side = [], False
    entry, pushed = None, None
    for f in range(BACK_FRAMES):
        await pr.frames(1)
        st = await pr.player_state()
        dx = st["x"] - spring["x"]
        if dx != 0 and (1 if dx > 0 else -1) != back:
            wrong_side = True
        closest = min(closest, abs(dx))
        peak_xv = max(peak_xv, abs(st["xv"]))
        peak_gsp = max(peak_gsp, abs(st["gsp"]))
        anim_seen.add(await pr.anim(spring["sst"]))
        rows.append(st)
        if entry is None and abs(dx) < half_w:
            entry = (f, st)          # the one uncorrected step — see below
        elif entry is not None and pushed is None:
            pushed = (f, st)         # the first frame the push and kill have run

    fails = []
    if closest >= half_w:
        raise Unmeasurable(
            f"{leg}: the player never got inside the spring's {half_w}px contact face over "
            f"{BACK_FRAMES} frames (closest {closest}px) — the back face never ran, so "
            f"'it did not launch him' is a statement about a collision that did not happen")
    if peak_gsp == 0 and peak_xv == 0:
        raise Unmeasurable(f"{leg}: the player carried no speed at all into the back face")

    # THE LAUNCH EVIDENCE IS WEIGHED BEFORE THE CROSSING GUARD, and that ORDER is the
    # difference between this leg reporting a defect and reporting that it could not look.
    # Proved by the red-first mutation that deletes the side face's direction gate (`bmi
    # .spring_side_push` -> a branch that never fires): the back face then launches him at
    # 16px/frame straight THROUGH the spring, so `wrong_side` is set — and a guard
    # evaluated first turned the sharpest possible symptom into "the player crossed, so
    # nothing was measured", exit 2. He crossed BECAUSE he was launched. So the peaks and
    # the animation, both sampled across the whole window and both valid however he
    # travelled, are judged first; crossing is then a FAIL that the launch explains, and
    # stays UNMEASURABLE only when no launch was seen and something else moved him.
    floor = abs(want) // 2
    launched = peak_xv >= floor or peak_gsp >= floor or anim_seen != {SPRING_ANIM_IDLE}
    out.append(f"  {leg}: closest approach {closest}px inside a {half_w}px face, peak "
               f"|x_vel| {peak_xv}, peak |ground_speed| {peak_gsp}")
    if peak_xv >= floor or peak_gsp >= floor:
        fails.append(f"{leg}: THE BACK FACE LAUNCHED HIM: |x_vel| reached {peak_xv} and "
                     f"|ground_speed| {peak_gsp}, past the {floor} threshold (half the "
                     f"{want} launch). This spring throws whatever touches it, and L5's "
                     f"pass says nothing about direction")
    else:
        out.append(f"  {leg}: neither driver came near the {floor} launch threshold (half "
                   f"the {want} launch) — the back face did not fire")
    if wrong_side:
        if launched:
            fails.append(f"{leg}: he ended up on the spring's LAUNCHING side — thrown "
                         f"straight through it by the face that was supposed to stop him")
            return fails
        raise Unmeasurable(
            f"{leg}: the player crossed to the spring's LAUNCHING side during the approach "
            f"without any sign of a launch (peak |x_vel| {peak_xv}, |ground_speed| "
            f"{peak_gsp}, anim {sorted(anim_seen)}) — something other than this spring "
            f"moved him and the back face was not what was measured")
    if anim_seen != {SPRING_ANIM_IDLE}:
        fails.append(f"{leg}: the spring's anim took the value(s) {sorted(anim_seen)} during "
                     f"the back-face contact — Game.spring_launched restarts the fire "
                     f"animation as its first act, so the launch hook RAN on a face that "
                     f"must not launch")
    else:
        out.append(f"  {leg}: the spring's anim stayed SPRING_ANIM_IDLE for all "
                   f"{BACK_FRAMES} frames — the launch hook was never invoked, which is the "
                   f"hook's own witness and not an inference from a velocity")

    # THE PUSH IS ASSERTED ON THE FRAME IT COMPLETES, NOT AT THE END OF THE WINDOW, and
    # both halves of that are measured facts rather than preferences.
    #
    # NOT THE ENTRY FRAME, for L1's reason (see test_side): TouchResponse runs before the
    # player's tick, so the frame he first overlaps is always one uncorrected step deep
    # at his full approach speed. Measured here: he enters at 14px and is at 16px with
    # both drivers zeroed on the very next frame.
    #
    # NOT THE LAST FRAME EITHER, and this leg is the one place in the file where that
    # distinction bites. He is AIRBORNE on the back face (there is no floor on that side
    # of the spring — see the header) and therefore FALLING out of the chamber while the
    # window runs. Measured: he holds 16px from the centre for six frames and then moves
    # to 17px on the frame his y passes 644, which is his own terrain wall probe against
    # the chamber wall and not this spring's side face — the section holds exactly one
    # other live object at the time, 800px away at (808,210). A resting gap read at
    # frame 16 is a statement about the chamber, so it is reported and not asserted.
    if pushed is None:
        raise Unmeasurable(
            f"{leg}: the player entered the back face on the last sampled frame of "
            f"{BACK_FRAMES}, so the frame the push and speed kill complete was never "
            f"observed — BACK_FRAMES is too small for this approach speed")
    ef, est = entry
    pf, pst = pushed
    want_rest = half_w - 1
    rest = abs(pst["x"] - spring["x"])
    out.append(f"  {leg}: entry frame {ef} — the one uncorrected step, before any push: "
               f"{abs(est['x'] - spring['x'])}px from the centre carrying x_vel {est['xv']}. "
               f"TouchResponse runs before the player's tick, so that frame is "
               f"uncorrectable by design and is NOT what is asserted")
    if rest != want_rest:
        fails.append(f"{leg}: on the frame the push completes (frame {pf}) he sits {rest}px "
                     f"from the centre, expected {want_rest}px (the {half_w}px contact face "
                     f"less the 1px overlap bias solid_face_response's `subq.w #1, d0` "
                     f"leaves) — the ordinary side push did not run on this face")
    else:
        out.append(f"  {leg}: pushed out to {rest}px from the centre on frame {pf} — the "
                   f"{half_w}px contact face less the 1px bias, i.e. exactly where a plain "
                   f"solid puts him")
    if pst["xv"] != 0 or pst["gsp"] != 0:
        fails.append(f"{leg}: his speed was not killed on the back face: x_vel {pst['xv']}, "
                     f"ground_speed {pst['gsp']} on the frame after contact, both of which a "
                     f"solid clears (`clr.w x_vel` + Game.solid_pushed)")
    else:
        out.append(f"  {leg}: x_vel and ground_speed are both 0 on that frame — the speed "
                   f"kill ran, so the back face is the ordinary solid and not a no-op")
    out.append(f"  {leg}: x across the whole {BACK_FRAMES}-frame window (he is airborne and "
               f"falling out of the chamber): " +
               " ".join(str(r["x"] - spring["x"]) for r in rows))
    return fails


async def test_top_land(pr, spring, out, leg):
    """C2 — landing on the TOP of a SIDE-pointing spring is a landing, not a launch.

    THE FAILURE THIS NAMES IS THE ONE SP-5 ALMOST SHIPPED. The top arm is shared, and
    without its `y_vel < 0` test a sideways spring's top face would hand the player the
    spring's ZERO y_vel and drop him into the airborne state with no impulse — a spring
    you fall through the top of. Worse, the game hook would still be invoked, and because
    the discriminator there is the SPRING's x_vel it would take the HORIZONTAL arm and
    write 16px/frame of inertia into a player who only landed on something.

    So this leg asserts a landing (seated at the derived top edge, grounded, ST_ON_OBJECT,
    y_vel zeroed) AND the absence of a sideways launch in both drivers AND that the fire
    animation never started.

    IT DRIVES THE OTHER SIDE SPRING FROM L5/C1, deliberately: this chamber's ceiling sits
    88px above it against 48px above L5's, so it is the placement with room for a drop
    that is unambiguously a fall. The leg first asserts its subject really is
    side-pointing, so it cannot quietly become a second run of L4.
    """
    if spring["xv"] == 0 or spring["yv"] != 0:
        raise Unmeasurable(
            f"{leg}: the spring at (x={spring['x']},y={spring['y']}) carries "
            f"({spring['xv']}, {spring['yv']}) — this leg is about a SIDE-pointing spring "
            f"(x_vel nonzero, y_vel zero) and that is not one")
    start_y = spring["y"] - SIDE_DROP_HEIGHT
    await pr.put_player(x=spring["x"], y=start_y, xv=0, yv=0, gsp=0)
    got = await pr.player_state()
    if got["y"] != start_y or got["x"] != spring["x"]:
        raise Unmeasurable(f"{leg}: the poke did not take — asked for ({spring['x']},"
                           f"{start_y}), the slot reads ({got['x']},{got['y']})")
    half_h = (got["h"] + spring["h"]) // 2
    half_w = (got["w"] + spring["w"]) // 2
    if SIDE_DROP_HEIGHT <= half_h:
        raise Unmeasurable(f"{leg}: the {SIDE_DROP_HEIGHT}px drop starts inside the spring's "
                           f"{half_h}px vertical contact face — he would be in contact "
                           f"before falling and no descent would be measured")
    out.append(f"  {leg}: side spring at (x={spring['x']},y={spring['y']}) launch "
               f"({spring['xv']},{spring['yv']}); dropped from y={start_y}, "
               f"{SIDE_DROP_HEIGHT}px above its centre against a {half_h}px contact face")

    peak_yv, peak_xv, peak_gsp, anim_seen = 0, 0, 0, set()
    landed, touched = None, False
    for f in range(TOP_LAND_FRAMES):
        await pr.frames(1)
        st = await pr.player_state()
        peak_yv = max(peak_yv, st["yv"])
        peak_xv = max(peak_xv, abs(st["xv"]))
        peak_gsp = max(peak_gsp, abs(st["gsp"]))
        anim_seen.add(await pr.anim(spring["sst"]))
        if abs(st["y"] - spring["y"]) < (st["h"] + spring["h"]) // 2 and \
                abs(st["x"] - spring["x"]) < half_w:
            touched = True
        if (st["status"] >> pr.equ["ST_ON_OBJECT"]) & 1:
            landed = (f + 1, st)
            break
    if peak_yv <= 0:
        raise Unmeasurable(f"{leg}: the player never carried a downward y_vel on the way — "
                           f"he did not descend onto anything")

    fails = []
    # CONTACT IS THE VACUITY LINE, NOT LANDING, and the two are different questions.
    # Proved by the red-first mutation that disarms the top face's `y_vel < 0` test: the
    # side spring's top then LAUNCHES instead of landing, hands the player its ZERO y_vel
    # and drops him airborne — a spring you fall through the top of. He therefore never
    # stands on anything, and the first version of this leg, which treated "did not land"
    # as its vacuity case, reported UNMEASURABLE for the exact defect it exists to catch.
    # So the line moved to where it belongs: he must have OVERLAPPED the spring, and the
    # absence of that overlap is genuinely unmeasurable (he fell past it). Having
    # overlapped it, NOT landing is a failure and is reported as one.
    if not touched:
        st = await pr.player_state()
        raise Unmeasurable(
            f"{leg}: over {TOP_LAND_FRAMES} frames the player never overlapped the spring at "
            f"all (he is at ({st['x']},{st['y']}), the spring is at ({spring['x']},"
            f"{spring['y']})) — he fell PAST it, so no top contact happened and nothing "
            f"about the top face was measured")
    if landed is None:
        st = await pr.player_state()
        fails.append(
            f"{leg}: HE FELL THROUGH THE TOP: he overlapped the spring and {TOP_LAND_FRAMES} "
            f"frames later has still not stood on anything (at ({st['x']},{st['y']}) y_vel "
            f"{st['yv']} status ${st['status']:02X}). A side spring's top face must be an "
            f"ordinary landing; this one handed him its zero y_vel and dropped him airborne")
        landed = (TOP_LAND_FRAMES, st)
    frames_to_land, st = landed
    want_y = spring["y"] - half_h + 1
    out.append(f"  {leg}: {'landed' if not fails else 'the window ended'} after "
               f"{frames_to_land} frames at y={st['y']}, peak fall speed {peak_yv} (8.8)")
    if st["y"] != want_y:
        fails.append(f"{leg}: seated at y={st['y']}, expected {want_y} (the spring's centre "
                     f"{spring['y']} less the {half_h}px contact face plus the 1px contact "
                     f"bias solid_top_land's `addq.w #1, d1` leaves)")
    else:
        out.append(f"  {leg}: seated at y={want_y} — the spring's centre less the {half_h}px "
                   f"contact face plus solid_top_land's 1px bias, i.e. an ordinary landing")
    if (st["status"] >> ST_IN_AIR) & 1:
        fails.append(f"{leg}: ST_IN_AIR is still set (status ${st['status']:02X}) after "
                     f"landing on the spring's top face — he was dropped airborne rather "
                     f"than stood up, which is exactly what a top arm missing its "
                     f"`y_vel < 0` test does to a sideways spring")
    else:
        out.append(f"  {leg}: status ${st['status']:02X} — ST_ON_OBJECT set, ST_IN_AIR clear")
    if st["yv"] != 0:
        fails.append(f"{leg}: y_vel is {st['yv']} on the landing frame, not 0 — the fall was "
                     f"not zeroed")
    floor = abs(spring["xv"]) // 2
    if peak_xv >= floor or peak_gsp >= floor:
        fails.append(f"{leg}: A TOP LANDING PRODUCED A SIDEWAYS LAUNCH: |x_vel| reached "
                     f"{peak_xv} and |ground_speed| {peak_gsp}, past the {floor} threshold "
                     f"(half this spring's {spring['xv']} horizontal launch). Landing on a "
                     f"side spring is throwing the player sideways")
    else:
        out.append(f"  {leg}: |x_vel| peaked at {peak_xv} and |ground_speed| at {peak_gsp}, "
                   f"both under the {floor} threshold (half this spring's {spring['xv']} "
                   f"launch) — no sideways launch")
    if anim_seen != {SPRING_ANIM_IDLE}:
        fails.append(f"{leg}: the spring's anim took the value(s) {sorted(anim_seen)} during "
                     f"the drop and landing — Game.spring_launched ran on a top contact "
                     f"with a spring that does not point up")
    else:
        out.append(f"  {leg}: the spring's anim stayed SPRING_ANIM_IDLE throughout — the "
                   f"launch hook was never invoked")
    return fails


async def test_underside_launch(pr, spring, want, out, leg):
    """L6 — JUMP into a down spring's underside and be thrown downward.

    THE APPROACH IS A JUMP, NOT A POKED VELOCITY, and that is worth the trouble it costs.
    The floor under this spring slopes, so a standing jump drifts sideways and leaves the
    box; the leg holds TOWARD the spring for the whole ascent, which is what a player
    would do, and JUMP_DX is the offset that puts the apex under it. It also means the
    player is CURLED for the whole leg (jumping sets ST_ROLLING and shrinks his box from
    19x39 to 15x29), so every geometry number below is read from his live box rather than
    from the standing one — a leg that used the standing half-height would compute a
    22px contact face as 27 and place the seat 5px wrong.

    THE INTERLOCK IS PART OF THE CLAIM. The underside arm fires only for a player who is
    RISING; a falling player under the spring is leaving it. So the ascent is traced
    frame by frame and the leg asserts he was still rising when he entered the contact
    band — without that, a launch measured on the way DOWN would read identically here
    and would be the re-fire bug the interlock exists to prevent.
    """
    # He is seated JUMP_DX to the LEFT of the spring's axis (seat_and_settle, in the
    # driver), so "toward" is RIGHT. Derived from where he actually stands rather than
    # written down, so a seat that moved cannot leave him holding away from the spring.
    st0 = await pr.player_state()
    toward = "right" if st0["x"] < spring["x"] else "left"
    half_h = (st0["h"] + spring["h"]) // 2
    if st0["y"] <= spring["y"] + half_h:
        raise Unmeasurable(
            f"{leg}: the player settled at y={st0['y']}, already within the spring's "
            f"{half_h}px vertical contact face below its centre {spring['y']} — there is no "
            f"jump to make and the rising interlock would never be exercised")
    out.append(f"  {leg}: down spring at (x={spring['x']},y={spring['y']}) sub="
               f"${spring['sub']:02X} launch=({spring['xv']},{spring['yv']}); the player "
               f"stands {st0['y'] - spring['y']}px below it at x={st0['x']}, "
               f"{spring['x'] - st0['x']:+d} off its axis, and jumps holding "
               f"{toward.upper()}")
    if await pr.anim(spring["sst"]) != SPRING_ANIM_IDLE:
        raise Unmeasurable(f"{leg}: the spring is already animating before the jump")

    top_y, in_band, rising_at_band = st0["y"], None, None
    early_launch = None
    await pr.hold("a", True)
    await pr.hold(toward, True)
    try:
        for _ in range(JUMP_TRACE_FRAMES):
            await pr.frames(1)
            st = await pr.player_state()
            top_y = min(top_y, st["y"])
            half_h = (st["h"] + spring["h"]) // 2
            dy = st["y"] - spring["y"]
            if st["yv"] >= abs(want) // 2:
                early_launch = st
                break
            if dy > 0 and dy < half_h:
                in_band, rising_at_band = st, st["yv"]
                break
        if early_launch is not None:
            raise Unmeasurable(
                f"{leg}: the player's y_vel was already {early_launch['yv']} at a frame "
                f"boundary (at y={early_launch['y']}), i.e. the launch fired before the "
                f"trace could see him enter the contact band. The velocity at a frame "
                f"boundary is the launch plus a gravity step and is not the quantity this "
                f"leg compares, so this is UNMEASURABLE rather than a near miss.")
        if in_band is None:
            raise Unmeasurable(
                f"{leg}: {JUMP_TRACE_FRAMES} frames of jumping never put the player inside "
                f"the spring's contact band below it. He reached y={top_y} at best "
                f"(the band starts at y={spring['y'] + half_h}, the spring's centre is "
                f"{spring['y']}), and ended {(await pr.player_state())['x'] - spring['x']:+d}px "
                f"off its axis. The jump does not reach the underside from this floor — no "
                f"underside launch was measured and this is not a pass.")
        if rising_at_band >= 0:
            raise Unmeasurable(
                f"{leg}: the player entered the contact band with y_vel {rising_at_band}, "
                f"i.e. FALLING. The underside arm fires only for a rising player, so what "
                f"happens next is not the launch this leg is about")
        r = await pr.run_to_hook(4)
    finally:
        await pr.hold("a", False)
        await pr.hold(toward, False)

    if not r.get("reached"):
        st = await pr.player_state()
        raise Unmeasurable(
            f"{leg}: the player rose into the spring's underside contact band (y="
            f"{in_band['y']}, {in_band['y'] - spring['y']}px below its centre, rising at "
            f"{rising_at_band}) and Spring_Launched was NOT invoked within 4 frames — he is "
            f"now at (x={st['x']},y={st['y']}) y_vel={st['yv']}. The underside did "
            f"something, but it was not a launch.")

    st = await pr.player_state()
    fails = []
    half_h = (st["h"] + spring["h"]) // 2
    dy = st["y"] - spring["y"]
    out.append(f"  {leg}: rose from y={st0['y']} to y={in_band['y']} (apex reached {top_y}), "
               f"entered the band rising at {rising_at_band}, and stopped INSIDE "
               f"Spring_Launched (${pr.sym['Spring_Launched']:06X}) at y={st['y']}, "
               f"{dy:+d}px from the spring's centre")
    if dy <= 0 or dy >= half_h:
        fails.append(f"{leg}: the hook fired with the player {dy:+d}px from the spring's "
                     f"centre, outside the {half_h}px band BELOW it — something other than "
                     f"this spring's underside launched him")
    want_y = spring["y"] + half_h - 1
    if st["y"] != want_y:
        fails.append(f"{leg}: seated at y={st['y']}, expected {want_y} (the spring's centre "
                     f"{spring['y']} plus the {half_h}px contact face less the 1px bias the "
                     f"underside arm's `subq.w #1, d1` leaves)")
    else:
        out.append(f"  {leg}: seated at y={want_y} — the centre plus the {half_h}px contact "
                   f"face less the underside arm's 1px bias, exactly where the code puts him")
    if st["yv"] != want:
        fails.append(f"{leg}: UNDERSIDE LAUNCH VELOCITY {st['yv']} at the hook, reference "
                     f"{want} (difference {st['yv'] - want})")
    else:
        out.append(f"  {leg}: y_vel at the hook = {st['yv']} == the ROM's "
                   f"Spring_Launch[Down,Red].y {want} ({want / 256:.1f} px/frame, DOWNWARD) "
                   f"— the underside launch is the derived one")

    await pr.frames(2)
    after = await pr.player_state()
    if after["y"] <= st["y"]:
        fails.append(f"{leg}: the player did not DESCEND after the underside launch: y went "
                     f"{st['y']} -> {after['y']} over two frames")
    else:
        out.append(f"  {leg}: he fell {after['y'] - st['y']}px over the next two frames — "
                   f"thrown down, not merely stopped")
    if not (after["status"] >> ST_IN_AIR) & 1:
        fails.append(f"{leg}: the player is not AIRBORNE two frames after the underside "
                     f"launch (status ${after['status']:02X})")
    fire = await pr.anim(spring["sst"])
    if fire != SPRING_ANIM_FIRE:
        fails.append(f"{leg}: the spring's anim is {fire}, not SPRING_ANIM_FIRE "
                     f"{SPRING_ANIM_FIRE}, after the launch")
    else:
        out.append(f"  {leg}: the spring's anim is now {fire} — the fire script is running")
    return fails



# --------------------------------------------------------------------------- driver

async def run(sock, rom, lst, want_launch, table, subtypes, out):
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
                 "SST_collision_resp", "SST_subtype",
                 # SP-1's own three: the inertia offset the game exports for this witness,
                 # the acceleration constant the in-contact speed bound is derived from,
                 # and the two collision-type ids the L2 retype moves between.
                 "_pl_gsp", "PHYS_ACCEL", "PHYS_TOP_SPEED", "COLLISION_SOLID",
                 "COLLISION_SPRING",
                 # SP-5c: the friction step L5's grounded-driver bound allows for, and the
                 # two status bits C2's landing is asserted on.
                 "PHYS_FRICTION", "ST_ON_OBJECT", "ST_IN_AIR"):
        if need not in equ:
            raise Unmeasurable(f"{need} has no EQU in {lst} — the SP-1 legs cannot be "
                               f"measured without it (an older ROM/listing pair?)")

    # The one status bit this file names as a module constant, checked against the build
    # that is about to be driven. The comment beside ST_IN_AIR has claimed this since the
    # file was written; SP-5c made it true.
    if equ["ST_IN_AIR"] != ST_IN_AIR:
        raise Unmeasurable(f"the listing puts ST_IN_AIR at bit {equ['ST_IN_AIR']}, this file "
                           f"reads bit {ST_IN_AIR} — every airborne assertion below would be "
                           f"testing the wrong bit")

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
    # ONLY THE UP/RED SPRINGS ARE HELD TO THE REFERENCE IMPULSE. Since SP-5 a placed
    # spring's subtype chooses its direction AND strength, and Spring_Init writes the
    # result into the SST's velocity PAIR at spawn — so a subtype-$50 spring carrying
    # y_vel 0 and x_vel +4096 is correct, not broken. Subtype 0 is up/red by the
    # encoder's own oldest ensure, which is why it is the one value this can hold to a
    # number derived from S3K.
    up_red = [s for s in springs if s["sub"] == 0]
    if not up_red:
        raise Unmeasurable(
            "no spawned spring carries subtype 0 (up/red) — every leg below drives one, "
            "and the reference velocity has no other subject in this level")
    for s in up_red:
        if s["yv"] != want_launch or s["xv"] != 0:
            fails.append(f"the spawned up/red spring at (x={s['x']},y={s['y']}) carries "
                         f"(x_vel {s['xv']}, y_vel {s['yv']}), not the reference "
                         f"(0, {want_launch}) — Spring_Init's subtype decode did not "
                         f"produce the reference launch vector")
    driven = {subtypes[("Left", "Red")]: "L5 + C1",
              subtypes[("Down", "Red")]: "L6",
              subtypes[("Right", "Red")]: "C2"}
    for s in springs:
        if s["sub"] != 0:
            who = driven.get(s["sub"])
            out.append(f"  the spring at (x={s['x']},y={s['y']}) is subtype ${s['sub']:02X}, "
                       f"launch vector (x_vel {s['xv']}, y_vel {s['yv']}) — "
                       + (f"driven by {who}" if who else
                          "NOT DRIVEN: no leg below has a subject with this subtype"))

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

    # ---- SP-5c. Each new leg boots fresh and seats the player in the chamber its
    # spring lives in, for the same reason the four above boot fresh: every leg starts
    # from an identical settled state rather than from the previous leg's leftovers.
    out.append("BOOT 4 (L5 side launch):")
    springs = await boot_and_settle(pr, spring_code, out)
    left = pick_by_subtype(springs, subtypes, ("Left", "Red"), "L5")
    side = launch_side_of(left)
    await seat_and_settle(pr, left["x"] + side * SIDE_APPROACH_DX,
                          left["y"] - SIDE_SEAT_DY, out, "L5")
    out.append("L5 SIDE LAUNCH (Touch_Spring's `.spring_side` launch arm):")
    fails += await test_side_launch(pr, left, table[("Left", "Red")][0], out, "L5")
    legs.append("L5 side launch")

    out.append("BOOT 5 (C1 back face — the control on L5):")
    springs = await boot_and_settle(pr, spring_code, out)
    left = pick_by_subtype(springs, subtypes, ("Left", "Red"), "C1")
    out.append("C1 BACK FACE (the SAME spring, hit on the face it does NOT point at):")
    fails += await test_back_face(pr, left, table[("Left", "Red")][0], out, "C1")
    legs.append("C1 back face")

    out.append("BOOT 6 (C2 top land — the control on the shared top face):")
    springs = await boot_and_settle(pr, spring_code, out)
    right = pick_by_subtype(springs, subtypes, ("Right", "Red"), "C2")
    out.append("C2 TOP LAND (landing on a SIDE spring must not throw him sideways):")
    fails += await test_top_land(pr, right, out, "C2")
    legs.append("C2 top land")

    out.append("BOOT 7 (L6 underside launch):")
    springs = await boot_and_settle(pr, spring_code, out)
    down = pick_by_subtype(springs, subtypes, ("Down", "Red"), "L6")
    await seat_and_settle(pr, down["x"] - JUMP_DX, down["y"] + JUMP_GROUND_DY, out, "L6")
    out.append("L6 UNDERSIDE LAUNCH (Touch_Spring's `.spring_below` launch arm):")
    fails += await test_underside_launch(pr, down, table[("Down", "Red")][1], out, "L6")
    legs.append("L6 underside launch")

    # THE LEG COUNT IS ITSELF AN ASSERTION. A leg that raised Unmeasurable never reaches
    # here (the run exits 2), but a leg deleted or short-circuited during an edit would
    # otherwise leave a smaller run reading exactly like a clean pass.
    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != LEGS:
        fails.append(f"LEG COUNT {len(legs)}, expected {LEGS} — a leg did not run, and the "
                     f"rest of this report is a smaller experiment than it claims to be")

    await b.close()
    return fails


def pick_by_subtype(springs, subtypes, key, leg):
    """The spawned spring whose subtype IS the published `ObjSub_Spring__<Dir>_<Str>` value.

    Matched by the equate the ROM publishes, never by a literal: `$50` appears nowhere in
    this file, so a re-encoding moves the leg's subject with it instead of silently
    pointing it at whatever now carries the old number.
    """
    want = subtypes[key]
    hits = [s for s in springs if s["sub"] == want]
    if not hits:
        raise Unmeasurable(
            f"{leg}: no spawned spring carries subtype ${want:02X} "
            f"(ObjSub_Spring__{key[0]}_{key[1]}) — this level places none, or the entity "
            f"window never spawned it. The leg has no subject and this is not a pass.")
    if len(hits) > 1:
        raise Unmeasurable(
            f"{leg}: {len(hits)} spawned springs carry subtype ${want:02X} "
            f"(ObjSub_Spring__{key[0]}_{key[1]}), at " +
            ", ".join(f"(x={s['x']},y={s['y']})" for s in hits) +
            " — the leg's chamber geometry is measured against ONE placement and picking "
            "arbitrarily would make the run depend on spawn order")
    return hits[0]


async def pick_target(pr, springs, out):
    """The UP spring on the player's own ground run — the only one he can walk into.

    SUBTYPE 0 ONLY, and that filter is load-bearing rather than tidy. Section 0 has had
    placed SIDE springs at the player's own ground level since SP-5 (2026-09-06), and
    walking into one of THOSE is supposed to launch him — the exact opposite of what L1
    asserts. Without the filter this would sometimes pick a side spring and report the
    feature working as a failure of the thing it tests.
    """
    p0 = await pr.player_state()
    out.append(f"  player settled at x={p0['x']} y={p0['y']} y_vel={p0['yv']} "
               f"status=${p0['status']:02X}")
    springs = [s for s in springs if s["sub"] == 0]
    if not springs:
        raise Unmeasurable("no subtype-0 (up/red) spring spawned — L1/L2/L4 all drive one")
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
               ", ".join(f"(x={s['x']},y={s['y']},sub=${s['sub']:02X},"
                         f"launch=({s['xv']},{s['yv']}))" for s in springs))
    return springs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()

    out = ["REFERENCE CHAIN:"]
    try:
        mags = s3k_spring_magnitudes()
        want = mags[0]
        out.append(f"  hop 1  skdisasm {SKDISASM_REV[:8]} sonic3k.asm word_22EF0 = "
                   + ", ".join(f"{s.lower()} {m} (-${-m:X}, {m / 256:.1f} px/frame)"
                               for s, m in zip(SPRING_STRENGTHS, mags)))
        sym = parse_lst(a.lst)
        equ = parse_equs(a.lst)
        rom_v = objdef_y_vel_from_rom(a.rom, sym, equ)
        out.append(f"  hop 2a {a.rom} Spring_Launch[up,red].y = {rom_v}")
        if rom_v != want:
            print("\n".join(out))
            print(f"\nRESULT: FAIL — hop 2 disagrees with hop 1: the built Spring_Launch "
                  f"carries {rom_v} for the up/red spring, S3K's red spring is {want}")
            return 1
        table, dirs, subtypes, bad, (weak_w, dir_w, base) = \
            spring_launch_table(a.rom, sym, equ, mags)
        out.append(f"  hop 2b the subtype encoding SOLVED out of the listing's own "
                   f"ObjSub_Spring__* equates: strength weight ${weak_w:02X}, direction "
                   f"weight ${dir_w:02X}, rows " +
                   ", ".join(f"{d}={dirs[d]}" for d in SPRING_DIRS))
        out.append(f"  hop 2c Spring_Launch at ${base:06X}, all "
                   f"{len(SPRING_DIRS) * len(SPRING_STRENGTHS)} implemented entries checked "
                   f"against S3K's magnitudes: " +
                   ", ".join(f"{d}/{s}=({table[(d, s)][0]},{table[(d, s)][1]})"
                             for d in SPRING_DIRS for s in SPRING_STRENGTHS))
        if bad:
            print("\n".join(out))
            print(f"\nRESULT: FAIL — hop 2 disagrees with hop 1 in {len(bad)} entr(ies):")
            for m in bad:
                print(f"  * {m}")
            return 1
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nRESULT: UNMEASURABLE — {e}")
        return 2

    out.append("MACHINE:")
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            fails = asyncio.run(run(sock, a.rom, a.lst, want, table, subtypes, out))
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
    print(f"\nRESULT: PASS — {LEGS} legs ({DRIVE_LEGS} drives + {CONTROL_LEGS} controls): a "
          f"spring AND a plain block are side-solid and kill the player's running speed on "
          f"contact, he can still walk away from them, a fall onto an up spring launches "
          f"him at {want} (S3K's red spring, all three hops agreeing) with ST_IN_AIR set, "
          f"a walk into a LEFT spring's launching face throws him sideways at "
          f"{table[('Left', 'Red')][0]} in BOTH drivers, a jump into a DOWN spring's "
          f"underside throws him down at {table[('Down', 'Red')][1]}, and neither that side "
          f"spring's BACK face nor a side spring's TOP face launches anything")
    return 0


if __name__ == "__main__":
    sys.exit(main())
