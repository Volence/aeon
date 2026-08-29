#!/usr/bin/env python3
"""The rolling balls of all three playable characters seat flush on the floor.

OWNER RULING d-36 (2026-08-28, "theyy should all be flush"). This is the ONE
row of tools/measure_character_boxes.py's table that is an adopted project
convention rather than an observation, and therefore the one row that is
asserted. Everything else that tool prints stays a report, for the reasons its
docstring gives: get-up crouches, tucked flight legs and glide poses are off the
ground BY DESIGN, and a fixture holding the whole measured table could not tell
a regression from an intentional re-export.

WHAT IS ASSERTED, precisely:

    for each of Sonic / Tails / Knuckles, over the frames its `Roll` animation
    row names,   max(lowest opaque art pixel row)  ==  BALL_Y_RADIUS

i.e. `delta == 0` in that tool's language: the ball's deepest pixel rests
exactly on the collision floor, and no ball frame sinks into it.

DERIVED, NOT PINNED. Nothing here is a number copied out of a measurement:

  * the ball radius is read from engine/system/constants.emp,
  * the frame set is read from each character's .emp animation table,
  * the pixels are decoded out of the shipped mapping/DPLC/art blobs,

all via measure_character_boxes.py's own machinery, reused rather than
duplicated. So moving BALL_Y_RADIUS, editing a `Roll` row, or re-exporting the
art re-derives the expectation instead of leaving a stale literal behind. An
assertion of the shape "y_off == -15" would track the constant in neither
direction; this one tracks it in both.

WHY THAT DOES NOT MAKE IT VACUOUS. The expectation is derived; the SUBJECT is
the shipped blobs, which come from a different producer entirely
(games/sonic4/data/characters_staging/gen_characters.py for Tails and Knuckles,
tools/convert_s2_mappings.py for Sonic). The generator derives its shift with
its own tile decoder; this gate re-measures the result with
measure_character_boxes.py's independent one. The two must agree.

LOUD ON UNMEASURABLE. A missing blob, a missing `Roll` row, a frame index past
the end of the mapping set, a frame with no opaque pixels, or a ball radius that
cannot be read all FAIL here. None of them is allowed to render as 0 or as
"couldn't measure".

Run by: build.sh's tool-suite lane (`python3 -m pytest tools/ -q --no-header`,
build.sh:466-472), build-fatally. It reads only committed source blobs, never a
ROM, so running before the build is correct.

Companion report: python3 tools/measure_character_boxes.py
Companion document: docs/CHARACTER_BOX_AUDIT.md
"""

import unittest

import measure_character_boxes as mcb


class BallSeating(unittest.TestCase):

    def test_ball_frames_seat_flush(self):
        try:
            cast = mcb.build_cast()
        except SystemExit as e:
            self.fail("could not build the character cast (a radius constant or "
                      "a blob is missing): %s" % e)

        self.assertEqual(len(cast), 3,
                         "expected the three playable characters; the roster "
                         "changed and this gate has not been re-ruled")

        measured = {}
        for label, ch, (anim_path, anim_table), radii in cast:
            radius = radii['roll']
            self.assertIsNotNone(
                radius, "%s: no ball radius — BALL_Y_RADIUS could not be read "
                        "from source, so nothing here can be measured" % label)

            anims = mcb.read_anim_frames(anim_path, anim_table)
            self.assertIn(
                mcb.BALL_STATE, anims,
                "%s: `%s` in %s has no `%s` row with frame bytes — the ball frame "
                "set cannot be derived. Fix the table or the parser; do NOT "
                "hardcode the frames here."
                % (label, anim_table, anim_path, mcb.BALL_STATE))

            frames = sorted(set(anims[mcb.BALL_STATE]))
            self.assertTrue(frames, "%s: `%s` names no frames" % (label, mcb.BALL_STATE))

            lows = {}
            for f in frames:
                self.assertLess(
                    f, ch.frame_count,
                    "%s: `%s` names frame $%02X but the mapping set holds only %d "
                    "frames — the animation table and the mappings disagree"
                    % (label, mcb.BALL_STATE, f, ch.frame_count))
                extent = ch.extent(f)
                self.assertIsNotNone(
                    extent,
                    "%s: ball frame $%02X decodes to NO opaque pixels — it cannot "
                    "be measured, and an unmeasurable ball is not a seated one"
                    % (label, f))
                lows[f] = extent[1]

            lowest = max(lows.values())
            delta = lowest - radius
            measured[label] = (frames, lows, radius, delta)

            self.assertEqual(
                delta, 0,
                "%s's rolling ball is not flush: its lowest opaque art row is %+d "
                "but the ball collision floor is at +%d (delta %+d, ball %s). "
                "Frames $%s, per-frame lowest row %s. "
                "Owner ruling d-36 says all three balls seat flush. For Tails and "
                "Knuckles the seating shift is derived in "
                "games/sonic4/data/characters_staging/gen_characters.py "
                "(derive_ball_shift) — re-run it rather than editing the .bin. "
                "Sonic's ball art comes from tools/convert_s2_mappings.py."
                % (label, lowest, radius, delta,
                   'FLOATS %d px' % -delta if delta < 0 else 'OVERLAPS %d px' % delta,
                   ' $'.join('%02X' % f for f in frames),
                   {'$%02X' % f: v for f, v in lows.items()}))

        # The three characters share one ball box, so they must share one answer.
        # A per-character radius appearing here would silently make "flush" mean
        # three different things.
        radii_seen = {m[2] for m in measured.values()}
        self.assertEqual(
            len(radii_seen), 1,
            "the three characters no longer share one ball radius (%s) — "
            "`delta == 0` now means something different per character and this "
            "gate needs re-ruling" % sorted(radii_seen))


if __name__ == '__main__':
    unittest.main()
