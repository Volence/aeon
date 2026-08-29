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

    the `Roll` row of all three playable characters must read delta == 0.

That is the owner's ruling d-36 (2026-08-28, "theyy should all be flush") — an
adopted project convention for the rolling balls specifically, not an
observation and not a claim about any other row. It is enforced by
tools/test_ball_seating.py, which reuses build_cast() and read_anim_frames()
below so it measures the same blobs against the same frame set this report
does; it deliberately gates that row and nothing else. Tails' and Knuckles'
halves of the ruling are implemented in
games/sonic4/data/characters_staging/gen_characters.py, which DERIVES the
mapping shift from BALL_Y_RADIUS rather than carrying a tuned number.

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
                note += ('  ' if note else '') + '[GATED == 0 by test_ball_seating]'
            print('  %-11s %-8s %-5d [%+d,%+d]%s  %+d   %s'
                  % (state, box, r, lo, hi, ' ' * max(0, 6 - len('[%+d,%+d]' % (lo, hi))),
                     d, note))
        print()

    return 0


if __name__ == '__main__':
    os.chdir(ROOT)
    sys.exit(main())
