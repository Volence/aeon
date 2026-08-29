#!/usr/bin/env python3
"""measure_character_boxes.py — where every character's ART sits inside its
COLLISION BOX, per state, for all three characters.

WHY THIS EXISTS. The collision box and the drawn sprite are two independent
subsystems that only ever meet on screen, and a mismatch between them looks
exactly like a physics bug while being a data fact. This tool measures the one
number that connects them:

    delta = (lowest opaque art pixel row, relative to y_pos)  -  y_radius

delta == 0  the sprite's bottom row sits exactly on the collision floor
delta <  0  the sprite FLOATS |delta| px above its own collision box
delta >  0  the sprite OVERLAPS the ground by delta px

MOSTLY A REPORT, WITH ONE ROW GATED. There is still no engine-wide invariant
that delta must be 0, and there never will be: poses that are legitimately off
the ground (get-up crouches, Tails' tucked flight legs, Knuckles' glide tumble)
have large deltas by design, and stock S3K holds no such rule even for its
balls (measured: its three ball frames give delta -1 / +1 / +2 for Tails /
Sonic / Knuckles). Asserting the whole measured table would freeze today's art
with no way to tell a regression from an intentional re-export. So this prints,
and a human reads.

The ONE exception, and the only thing anything asserts:

    for the `Roll` row of all three playable characters, the BALL BODY must
    reach exactly BALL_Y_RADIUS.

That is the owner's ruling d-36 (2026-08-28, "theyy should all be flush") — an
adopted project convention for the rolling balls specifically, not an
observation and not a claim about any other row.

NOTE THE QUANTITY. It is the body bottom, NOT this table's `delta` column,
because those two differ wherever a stray pixel hangs below the ball: Knuckles'
$96 has a single opaque pixel (a dreadlock tip) one row below his entire roll
cycle, so his `delta` column reads +1 while his ball is flush. The Roll rows
print both readings for exactly that reason. body_bottom_from_profile() below
defines the body rule and derives its one constant.

Enforced by tools/test_ball_seating.py, which reuses build_cast(),
read_anim_frames() and body_bottom_from_profile() below so it measures the same
blobs against the same frame set and the same rule this report does; it gates
that row and nothing else. Tails' and Knuckles' halves of the ruling are
implemented in games/sonic4/data/characters_staging/gen_characters.py, which
DERIVES the mapping shift rather than carrying a tuned number.

RUN IT after any character art / mapping / DPLC re-export
(games/sonic4/data/characters_staging/gen_characters.py,
tools/convert_s2_mappings.py) or after changing any *_RADIUS constant:

    python3 tools/measure_character_boxes.py            # from the repo root
    python3 tools/measure_character_boxes.py --grounded # only feet-on-floor states

Every radius is READ FROM SOURCE (engine/system/constants.emp, the three
character records), never restated here, so a constant that moves re-measures
instead of lying. Frame lists are read from the .emp animation tables the same
way. The one hand-maintained table is STATE_BOX below — which of the three
boxes each state installs — because that is code structure (the PHook_* enter
hooks), not a constant; its source lines are cited there.

Companion document: docs/CHARACTER_BOX_AUDIT.md
"""

import argparse
import os
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- source reads

def read_const(path, name):
    """Read `const NAME = <int>` (or `pub const`) out of a .emp file."""
    text = (ROOT / path).read_text()
    m = re.search(r'^\s*(?:pub\s+)?const\s+%s\s*=\s*(\$?[0-9A-Fa-f]+)\s*$'
                  % re.escape(name), text, re.M)
    if not m:
        raise SystemExit("could not find const %s in %s" % (name, path))
    tok = m.group(1)
    return int(tok[1:], 16) if tok.startswith('$') else int(tok)


def read_anim_frames(path, table):
    """Parse ONE `offsets <table> { ... }` animation block into
    {StateName: [frame, ...]}.

    The block must be named: tails_anims.emp holds both Ani_Tails and
    Ani_TailsAppendage, whose rows share every state name, so an unscoped
    parse silently reports the twin-tails object's frames as Tails'.

    Rows look like:  Roll:  [u8; 5] = [1, $96, $97, $98, AF_END],
    The FIRST element is the duration, not a frame; AF_END / AF_BACK / any
    other AF_* symbol and the count that follows AF_BACK are control data.
    """
    text = (ROOT / path).read_text()
    # strip // comments so a commented-out row or a trailing note cannot leak in
    text = re.sub(r'//[^\n]*', '', text)
    m = re.search(r'^offsets\s+%s\s*\{(.*?)^\}' % re.escape(table),
                  text, re.M | re.S)
    if not m:
        raise SystemExit("could not find `offsets %s { ... }` in %s" % (table, path))
    text = m.group(1)
    out = {}
    for m in re.finditer(r'^\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*\[u8;\s*\d+\]\s*=\s*\[(.*?)\]\s*,',
                         text, re.M | re.S):
        name, body = m.group(1), m.group(2)
        toks = [t.strip() for t in body.split(',') if t.strip()]
        frames, skip_next = [], False
        for i, t in enumerate(toks):
            if skip_next:
                skip_next = False
                continue
            if i == 0:
                continue                      # duration byte
            if t.startswith('AF_'):
                if t == 'AF_BACK':
                    skip_next = True          # AF_BACK's operand is a count
                continue
            if t.startswith('$'):
                frames.append(int(t[1:], 16))
            elif t.isdigit():
                frames.append(int(t))
        if frames:
            out[name] = frames
    return out


# ------------------------------------------------------------- blob decoding
#
# Mapping blob: u16 offset table (count = table[0]/2), then per frame
#   +0 i8 bbox x_min   +1 i8 bbox x_max   +2 i8 bbox y_min   +3 i8 bbox y_max
#   +4 u16 piece count                    +6.. pieces
# Piece (8 bytes, VDP order, engine/objects/sprites.emp:194-199):
#   +0 i16 Y offset (px, relative to y_pos)
#   +2 u8  VDP size code (bits 3:2 = width-1, bits 1:0 = height-1, in cells)
#   +3 u8  pad (link at emit time)
#   +4 u16 tile attributes (relative to art_tile; bit 11 xflip, bit 12 yflip)
#   +6 i16 X offset
#
# DPLC blob (engine/objects/dplc.emp:3-6): u16 offset table, then per frame
#   u16 entry count, then that many entry words: bits 15-12 = tile_count-1,
#   bits 11-0 = tile_start. Entries concatenate into the frame's tile list, and
#   a piece's tile field indexes THAT list, not the art directly.

def _u16(b, o):
    return struct.unpack_from('>H', b, o)[0]


def longest_run(columns):
    """Longest run of horizontally adjacent columns in a set of x positions."""
    best = run = 0
    prev = None
    for x in sorted(columns):
        run = run + 1 if prev is not None and x == prev + 1 else 1
        prev = x
        best = max(best, run)
    return best


# ------------------------------------------------------- the ball BODY statistic
#
# WHY THIS IS NOT `max(lowest opaque row)`. That statistic is stray-sensitive by
# construction, and one stray pixel was in fact driving the answer: Knuckles'
# ball frame $96 carries a SINGLE opaque pixel one row below every other row of
# every frame in his roll cycle — a dreadlock tip, not the ball. Seating the ball
# on it put the actual 8 px-wide ball body 1 px above the floor on all five
# frames, i.e. it shipped the exact symptom the owner reported on Tails. So the
# quantity that matters is where the BODY ends, and a row is body only if it is
# still part of the silhouette's edge rather than a spur hanging off it.
#
# THE RULE. Walking up from the lowest opaque row, a row belongs to the body if
# its longest contiguous run is at least half the longest run of the row directly
# above it. Rows failing that are spurs and are skipped; the first row that
# passes is the body bottom.
#
# WHERE THE 1/2 COMES FROM — it is a geometric bound, not a number picked to make
# today's art come out. Near the bottom of a convex silhouette of radius R the
# half-width at height h above the bottom edge is sqrt(R^2 - (R-h)^2) ~= sqrt(2Rh),
# i.e. width grows as sqrt(h). Two rows 1 px apart therefore stand in the ratio
# sqrt(h / (h+1)). A row only rasterizes at all once its centre line is inside the
# shape, so the coarsest case is h = 0.5, giving sqrt(0.5/1.5) = 0.577. Rounded
# DOWN to the nearest simple fraction — because the art is a drawn curled
# character, not a true disc, and does dip slightly below the convex bound — that
# is 1/2.
#
# MEASURED AGAINST THE SHIPPED ART (2026-08-29, all 14 candidate bottom rows of
# all three characters' roll cycles): 13 genuine body rows, ratios 0.533 .. 1.333,
# every one accepted; 1 stray, ratio 0.125, rejected. The threshold sits 4.0x
# above the stray and 6.7% below the tightest genuine row (Knuckles $97). That
# accept-side margin is thin ON ONE FRAME, but the callers take `max` over the
# whole cycle, so a single frame flipping cannot move the answer — Knuckles' other
# four frames put the body bottom at the same row.
BODY_MIN_RUN_RATIO_DEN = 2      # "at least 1/DEN of the run directly above"


def body_bottom_from_profile(profile):
    """(body_row, its run, [(skipped_row, its run), ...]) from {row: longest run}.

    `profile` must be non-empty. Returns None only if EVERY row is a spur, which
    is a frame whose geometry this rule does not understand — callers must treat
    that as a hard failure, never as a zero.
    """
    skipped = []
    for row in sorted(profile, reverse=True):
        above = profile.get(row - 1)
        # A row with nothing directly above it is detached from the body, not an
        # edge of it. A row that more than halves the run above it is a spur.
        if above is not None and profile[row] * BODY_MIN_RUN_RATIO_DEN >= above:
            return row, profile[row], skipped
        skipped.append((row, profile[row]))
    return None


class Character:
    def __init__(self, name, mappings, dplc, art):
        self.name = name
        self.m = (ROOT / mappings).read_bytes()
        self.d = (ROOT / dplc).read_bytes()
        self.a = (ROOT / art).read_bytes()
        self.frame_count = _u16(self.m, 0) // 2

    def _tiles_for(self, frame):
        fo = _u16(self.d, 2 * frame)
        n = _u16(self.d, fo)
        tiles, o = [], fo + 2
        for _ in range(n):
            e = _u16(self.d, o)
            o += 2
            tiles += range(e & 0xFFF, (e & 0xFFF) + (e >> 12) + 1)
        return tiles

    def _tile_rows(self, art_index):
        base = art_index * 32
        t = self.a[base:base + 32]
        if len(t) < 32:
            return None
        rows = []
        for r in range(8):
            row = []
            for c in range(4):
                byte = t[r * 4 + c]
                row.append(byte >> 4)
                row.append(byte & 0xF)
            rows.append(row)
        return rows

    def extent(self, frame):
        """(y_min, y_max) of the opaque pixels, relative to y_pos. None if empty."""
        if frame >= self.frame_count:
            return None
        fo = _u16(self.m, 2 * frame)
        count = _u16(self.m, fo + 4)
        tiles = self._tiles_for(frame)
        o, lo, hi = fo + 6, None, None
        for _ in range(count):
            dy = struct.unpack_from('>h', self.m, o)[0]
            size = self.m[o + 2]
            attr = _u16(self.m, o + 4)
            o += 8
            w = ((size >> 2) & 3) + 1
            h = (size & 3) + 1
            ti = attr & 0x7FF
            yflip = (attr >> 12) & 1
            k = 0
            for _cx in range(w):
                for _cy in range(h):
                    idx = ti + k
                    k += 1
                    if idx >= len(tiles):
                        continue
                    rows = self._tile_rows(tiles[idx])
                    if rows is None:
                        continue
                    for ry in range(8):
                        if not any(rows[ry]):
                            continue
                        sy = _cy * 8 + ry
                        if yflip:
                            sy = h * 8 - 1 - sy
                        y = dy + sy
                        lo = y if lo is None else min(lo, y)
                        hi = y if hi is None else max(hi, y)
        return None if lo is None else (lo, hi)

    def row_profile(self, frame):
        """{row relative to y_pos: longest contiguous opaque run, in px}.

        The run, not the raw count: a row can carry pixels in two separate
        clusters (Sonic's $9A does), and the silhouette's edge is the longest of
        them, not their sum.
        """
        if frame >= self.frame_count:
            return None
        fo = _u16(self.m, 2 * frame)
        count = _u16(self.m, fo + 4)
        tiles = self._tiles_for(frame)
        o, cols = fo + 6, {}
        for _ in range(count):
            dy = struct.unpack_from('>h', self.m, o)[0]
            size = self.m[o + 2]
            attr = _u16(self.m, o + 4)
            dx = struct.unpack_from('>h', self.m, o + 6)[0]
            o += 8
            w = ((size >> 2) & 3) + 1
            h = (size & 3) + 1
            ti = attr & 0x7FF
            xflip = (attr >> 11) & 1
            yflip = (attr >> 12) & 1
            k = 0
            for cx in range(w):
                for cy in range(h):
                    idx = ti + k
                    k += 1
                    if idx >= len(tiles):
                        continue
                    rows = self._tile_rows(tiles[idx])
                    if rows is None:
                        continue
                    for ry in range(8):
                        sy = cy * 8 + ry
                        if yflip:
                            sy = h * 8 - 1 - sy
                        for rx, v in enumerate(rows[ry]):
                            if not v:
                                continue
                            sx = cx * 8 + rx
                            if xflip:
                                sx = w * 8 - 1 - sx
                            cols.setdefault(dy + sy, set()).add(dx + sx)
        return {y: longest_run(c) for y, c in cols.items()}

    def body_bottom(self, frame):
        """Where this frame's BALL BODY ends. See body_bottom_from_profile."""
        prof = self.row_profile(frame)
        if not prof:
            return None
        return body_bottom_from_profile(prof)


# ------------------------------------------------------------ the state table
#
# Which collision box each animation state runs with, and whether the state is
# a feet-on-the-floor pose (only those make `delta` meaningful as an alignment
# reading). Derived by reading the enter-hook table in
# games/sonic4/player/player_common.emp:1122-1195 — PHook_GroundEnter /
# PHook_AirEnter / PHook_SpindashEnter install the STANDING box, PHook_RollEnter
# / PHook_AirBallEnter the ROLL box, PHook_GlideEnter / PHook_SlideEnter /
# PHook_ClimbEnter the ABILITY box.
#
#   state -> (box, grounded)
STATE_BOX = {
    'Walk':       ('stand',   True),
    'Run':        ('stand',   True),
    'Roll':       ('roll',    True),
    'Spindash':   ('stand',   True),   # charge is pinned at standing size
    'Push':       ('stand',   True),
    'Wait':       ('stand',   True),
    'Balance':    ('stand',   True),
    'LookUp':     ('stand',   True),
    'Duck':       ('stand',   True),
    'Skid':       ('stand',   True),
    'GetUp':      ('stand',   True),
    'Fly':        ('stand',   False),  # Tails' flight keeps the standing box
    'FlyTired':   ('stand',   False),
    'Glide0':     ('ability', False),
    'Glide1':     ('ability', False),
    'Glide2':     ('ability', False),
    'Glide3':     ('ability', False),
    'Glide4':     ('ability', False),
    'GlideFall':  ('ability', False),
    'Slide':      ('ability', True),
    'SlideGetUp': ('ability', True),
    'GlideLand':  ('stand',   True),
    'Climb':      ('ability', False),  # attached to a wall, not the floor
    'Ledge':      ('ability', False),
}


# The animation row whose frames ARE the ball, for every character. The one row
# an outside gate asserts on (see the module docstring); named here so the gate
# and this report cannot disagree about which state that is.
BALL_STATE = 'Roll'


def build_cast():
    """The three playable characters, their blobs, their animation table and
    their radii — every radius read from source.

    Returns [(label, Character, (anim_path, anim_table), {box: y_radius}), ...].
    Shared with tools/test_ball_seating.py so the gate measures exactly what this
    report measures; a path or a radius that moves moves for both at once.
    """
    stand_y = read_const('engine/system/constants.emp', 'PLAYER_Y_RADIUS')
    ball_y = read_const('engine/system/constants.emp', 'BALL_Y_RADIUS')
    tails_y = read_const('games/sonic4/player/tails.emp', 'TAILS_Y_RADIUS')
    knux_ability = read_const('games/sonic4/player/knuckles.emp', 'KNUX_ABILITY_RADIUS')

    return [
        ('SONIC', Character('sonic',
                            'games/sonic4/data/mappings/sonic.bin',
                            'games/sonic4/data/dplc/optimized/sonic.bin',
                            'art/optimized/characters/sonic.bin'),
         ('games/sonic4/data/animations/sonic_anims.emp', 'Ani_Sonic'),
         {'stand': stand_y, 'roll': ball_y, 'ability': None}),
        ('TAILS', Character('tails',
                            'games/sonic4/data/mappings/tails.bin',
                            'games/sonic4/data/dplc/optimized/tails.bin',
                            'art/optimized/characters/tails.bin'),
         ('games/sonic4/data/animations/tails_anims.emp', 'Ani_Tails'),
         {'stand': tails_y, 'roll': ball_y, 'ability': None}),
        ('KNUCKLES', Character('knuckles',
                               'games/sonic4/data/mappings/knuckles.bin',
                               'games/sonic4/data/dplc/knuckles.bin',
                               'art/optimized/characters/knuckles.bin'),
         ('games/sonic4/data/animations/knuckles_anims.emp', 'Ani_Knuckles'),
         {'stand': stand_y, 'roll': ball_y, 'ability': knux_ability}),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--grounded', action='store_true',
                    help='only states whose pose rests on the floor')
    args = ap.parse_args()

    cast = build_cast()
    stand_y = read_const('engine/system/constants.emp', 'PLAYER_Y_RADIUS')
    ball_y = read_const('engine/system/constants.emp', 'BALL_Y_RADIUS')
    tails_y = read_const('games/sonic4/player/tails.emp', 'TAILS_Y_RADIUS')
    knux_ability = read_const('games/sonic4/player/knuckles.emp', 'KNUX_ABILITY_RADIUS')

    print('radii read from source: standing y=%d, ball y=%d, '
          'Tails standing y=%d, Knuckles ability=%d'
          % (stand_y, ball_y, tails_y, knux_ability))
    print('delta = (lowest opaque art row) - y_radius   '
          '[0 = flush, <0 = floats, >0 = overlaps]\n')

    for label, ch, (anim_path, anim_table), radii in cast:
        anims = read_anim_frames(anim_path, anim_table)
        print('=' * 78)
        print('%s   (%d mapping frames)' % (label, ch.frame_count))
        print('  %-11s %-8s %-5s %-14s %s'
              % ('state', 'box', 'y_rad', 'art rows', 'delta'))
        for state, frames in anims.items():
            if state not in STATE_BOX:
                continue                      # appendage-only or unknown row
            box, grounded = STATE_BOX[state]
            if args.grounded and not grounded:
                continue
            r = radii[box]
            ext = [ch.extent(f) for f in sorted(set(frames))]
            ext = [e for e in ext if e is not None]
            if not ext:
                print('  %-11s %-8s %-5s %s' % (state, box, '-', 'NO ART'))
                continue
            lo = min(e[0] for e in ext)
            hi = max(e[1] for e in ext)
            if r is None:
                print('  %-11s %-8s %-5s [%+d,%+d]%s'
                      % (state, box, 'n/a', lo, hi, '    (no ability box)'))
                continue
            d = hi - r
            note = ''
            if d < 0:
                note = 'FLOATS %d px' % -d
            elif d > 0:
                note = 'OVERLAPS %d px' % d
            if not grounded:
                note += ('  ' if note else '') + '(pose is off the floor)'
            if state == BALL_STATE:
                # The gated quantity is the BODY bottom, not this row's raw
                # lowest opaque pixel — they differ wherever a stray pixel hangs
                # below the ball (Knuckles $96). Print both so the gap is visible
                # rather than something the reader has to know about.
                bodies = [ch.body_bottom(f) for f in sorted(set(frames))]
                bodies = [b for b in bodies if b is not None]
                if bodies:
                    deep = max(b[0] for b in bodies)
                    run = min(b[1] for b in bodies)
                    spurs = sum(len(b[2]) for b in bodies)
                    note += ('  ' if note else '')
                    note += ('body row %+d (min run %d px%s) -> body delta %+d '
                             '[GATED == 0 by test_ball_seating]'
                             % (deep, run,
                                ', %d spur row(s) skipped' % spurs if spurs else '',
                                deep - r))
            print('  %-11s %-8s %-5d [%+d,%+d]%s  %+d   %s'
                  % (state, box, r, lo, hi, ' ' * max(0, 6 - len('[%+d,%+d]' % (lo, hi))),
                     d, note))
        print()

    return 0


if __name__ == '__main__':
    os.chdir(ROOT)
    sys.exit(main())
