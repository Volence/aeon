#!/usr/bin/env python3
"""test_perspective_floor — the law the OJZ floor's fan rests on, checked.

WHY THIS FILE EXISTS. Between 2026-08-16 and 2026-09-05 the floor's drawn board
pitch was a nine-step staircase while the engine ramped that band's scroll
LINEARLY across the same rows. Four shapes built green the whole time, the tile
budget was respected, the room gate passed, and nothing anywhere compared the
art's geometry with the scroll that would be applied to it. These tests are that
comparison.

THE ART CHANGED SHAPE TWICE ON 2026-09-05: fan -> parallel planks -> fan. The
owner settled it:

    "the effect should make it so when one of the beams of the floor at the top
     hits the center, the bottom should hit the center. the other had that
     effect a little, this just consistently skews and continues to do so"

So the subject is a FAN with its apex pinned to the screen centre column at every
camera x, and the arms below check exactly that. The shear-era arm is retired,
not deleted — the block above test_drawn_beam_period_is_proportional_to_the_depth
_row says what it tested and why the fan makes it unfailable.

THE PROPERTY THAT MAKES THIS FILE WORTH ANYTHING, and it has survived two
rewrites: every number checked below is VOTED FOR OFF RENDERED PIXELS. Nothing
here asks perspective_floor_gen what it meant to draw. An early draft compared
the drawn seams against `board_pitch()`'s own output, which made the check a
tautology — the even-snap mutation was applied on disk and the test still passed
(measured 2026-09-05). Any arm added here must keep that property. The one model
these arms are allowed to consult is the ENGINE's — tools/curve_probe.py's
transcription of the per-line Bresenham ramp — because the thing under test is
whether the ART agrees with the SCROLL, and you cannot test that without both.

They are cheap and boot nothing: build.sh's pytest lane sweeps tools/test_*.py.
"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perspective_floor_gen as pfg
import curve_probe as cp

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDE = os.path.join(REPO, "games/sonic4/data/editor_bg_override.json")
SCENES = os.path.join(REPO, "games/sonic4/data/effects/ojz_scenes.emp")

SCREEN_W = 320
SCREEN_H = 224                   # engine/system/constants.emp SCREEN_HEIGHT; the
                                 # curve hoist's span for the LAST band is
                                 # SCREEN_HEIGHT - that band's top line.
BAND_TOP = 96                    # screen line the 128-px art band starts at,
                                 # via the scene's `v_offset: 288`
WOOD_INDEX = {v: i for i, v in enumerate(pfg.WOOD)}

# Packed FACTOR_* words, mirrored from engine/level/parallax_dsl.emp.
FACTOR_0 = 0x0FF
FACTOR_1 = 0x0F0


# ---------------------------------------------------------------- helpers ----
def seam_centres(row, width=None, x0=0):
    """x centres of the drawn beam seams in one row of pixels.

    Measured OFF THE PIXELS, not read back from the model: a seam is where
    render_band subtracts 2.4 from the wood level, which lands the DARKER of the
    two alternating beam tones on WOOD index 0 or 1, while no beam interior gets
    below index 2. Every seam therefore contributes exactly one dark run (its
    darker half), so the runs are one-per-seam and evenly spaced even though
    each run is offset a fraction of a pixel inside its seam — a constant offset,
    which cancels in every gap this file measures.
    """
    width = len(row) if width is None else width
    ind = [1 if WOOD_INDEX[row[x0 + x]] <= 1 else 0 for x in range(width)]
    if not any(ind) or all(ind):
        return []
    runs, cur = [], None
    for x in range(width):
        if ind[x]:
            cur = [x, x] if cur is None else [cur[0], x]
        elif cur:
            runs.append(cur)
            cur = None
    if cur:
        runs.append(cur)
    return sorted((a + b) / 2.0 for a, b in runs)


DARK_ROW_FRACTION = 0.25         # above this, the dark runs in a row are not
                                 # seams. A seam is ~1.8 px of every period, and
                                 # only its darker half crosses the threshold, so
                                 # a row of real seams is under 10% dark even at
                                 # the tightest period drawn. A CROSS-seam row
                                 # (the beam ends) subtracts 1.6 from the WHOLE
                                 # row, which pushes the darker tone under the
                                 # threshold everywhere — measured, those rows
                                 # come back about half dark and the run centres
                                 # they report are beam centres, not seams.
                                 # Scoring them would be scoring the wrong
                                 # feature, so they are dropped and COUNTED.
MIN_SEAMS = 6


def plane_seam_rows(px, shade_px, span):
    """(dy, [seam plane-x]) for every floor row whose seams can be located."""
    out, dropped = [], 0
    for dy in range(span):
        row = px[shade_px + dy]
        dark = sum(1 for v in row if WOOD_INDEX[v] <= 1)
        if dark > DARK_ROW_FRACTION * pfg.PLANE_W:
            dropped += 1
            continue
        cs = seam_centres(row)
        if len(cs) >= MIN_SEAMS:
            out.append((dy, cs))
    return out, dropped


def row_period(cs):
    """The beam period of one row, from its seam positions and nothing else.

    A row's seams are a uniform lattice, so the period is (last - first) / k for
    an INTEGER interval count k. k is not len(cs)-1, because seams get missed: a
    seam is ~1.8 px wide, only its darker half crosses the WOOD-index threshold,
    and that half can fall between two pixel centres and vanish. Seams are only
    ever missed, never invented, so k >= len(cs)-1, and the true k is found by
    scoring each candidate against the seams and taking the best fit.

    THE SEARCH IS CAPPED AT 1.5*(len(cs)-1) AND THAT CAP IS LOAD-BEARING. A
    lattice 3x too fine contains the true one and fits every seam perfectly, so
    an uncapped search reports a third of the period — measured, it put whole
    rows at ratio 0.150 against a true 0.451. Missing a third of the seams is
    already implausible; missing two thirds is not a measurement.

    Returns (period, worst residual in px). The residual is the caller's quality
    signal: a row the lattice cannot explain is a row this file must not score.
    """
    n = len(cs)
    lo, hi = cs[0], cs[-1]
    best = None
    for k in range(n - 1, int(math.ceil(1.5 * (n - 1))) + 2):
        p = (hi - lo) / k
        r = max(abs(((c - lo) / p) - round((c - lo) / p)) * p for c in cs)
        if best is None or r < best[1] - 1e-9:
            best = (p, r)
    return best


ROW_RESIDUAL_TOL = 2.0           # px. A row whose seams are more than this far
                                 # off any uniform lattice is unreadable, not
                                 # wrong — drop it and count it. Measured across
                                 # near_pitch 32/40/48: 0, 1 and 0 rows dropped.


def hscroll(cam_x, curve_to):
    """The 224 per-line Plane-B HScroll words the engine's ramp would write."""
    layers = [(0, FACTOR_1, FACTOR_0, None),
              (horizon_line(), FACTOR_1, FACTOR_0, curve_to)]
    buf = cp.derive_curve_buffer(layers, cam_x)
    return [cp.php.s16(buf[y][1]) for y in range(cp.php.HSCROLL_LINES)]


def horizon_line():
    s = pfg.SHIPPED
    return BAND_TOP + (s["horizon_row"] - s["row0"]) * 8      # 152


def screen_seam_rows(px, shade_px, span, h):
    """(dy, [seam SCREEN-x]) after compositing the art through the engine ramp."""
    out = []
    for dy in range(span):
        row = px[shade_px + dy]
        shift = h[horizon_line() + dy]
        vals = [row[(x - shift) % pfg.PLANE_W] for x in range(SCREEN_W)]
        dark = sum(1 for v in vals if WOOD_INDEX[v] <= 1)
        if dark > DARK_ROW_FRACTION * SCREEN_W:
            continue
        cs = seam_centres(vals)
        if len(cs) >= 4:
            out.append((dy, cs))
    return out


def apex_votes(rows):
    """Every adjacent-row seam pair votes for the column the beams converge on.

    A beam is a straight line through the apex, so from its x at two rows the
    apex column follows as x - slope*dy. A beam that belongs to a WRAP COPY of
    the fan votes for an apex about 512 px away — which is precisely the "point
    away" artefact, so this vote is the artefact's direct measurement.
    """
    votes, prev = [], None
    for dy, cs in rows:
        if prev is not None and dy - prev[0] <= 2:
            pdy, pcs = prev
            for x in cs:
                m = min(pcs, key=lambda y: abs(y - x))
                slope = (x - m) / float(dy - pdy)
                votes.append(x - slope * dy)
        prev = (dy, cs)
    return votes


def override_band_pixels():
    """The floor band as it is COMMITTED, decoded through layout words + flips."""
    with open(OVERRIDE) as fh:
        data = json.load(fh)
    layout, tiles = data["layout"], data["tiles"]
    s = pfg.SHIPPED
    out = []
    for cy in range(s["row0"], s["row1"] + 1):
        for iy in range(8):
            line = []
            for cx in range(pfg.PLANE_COLS):
                w = layout[cy * pfg.PLANE_COLS + cx]
                t = tiles[w & 0x7FF]
                sy = 7 - iy if (w >> 12) & 1 else iy
                for ix in range(8):
                    sx = 7 - ix if (w >> 11) & 1 else ix
                    line.append(t[sy * 8 + sx])
            out.append(line)
    return out


def scene_curve_to():
    """The FACTOR_* identifier the scene ramps its floor band TO, parsed."""
    src = open(SCENES).read()
    fn = re.search(r"pub comptime fn perspective_floor_layers\(\).*?\n\}", src, re.S)
    assert fn, ("perspective_floor_layers() is gone from %s — this file cannot "
                "locate the floor layer and is therefore proving nothing" % SCENES)
    m = [x for x in re.finditer(
        r"layer\(world_y:\s*(\d+)[^)]*?fb:\s*(FACTOR_\w+)[^)]*?"
        r"curve:\s*SceneCurve\.To\((FACTOR_\w+)\)", fn.group(0), re.S)]
    assert len(m) == 1, (
        "expected exactly one curve layer in perspective_floor_layers(); found "
        "%d. The floor's whole geometry assumes a single linear ramp over the "
        "fan." % len(m))
    return m[0].groups()          # (world_y, fb, curve_to)


FACTOR_WORDS = {                  # engine/level/parallax_dsl.emp `packed()`
    "FACTOR_1": (0x0F0, 1.0),
    "FACTOR_1_2": ((15 << 4) | 1, 0.5),
    "FACTOR_1_4": ((15 << 4) | 2, 0.25),
    "FACTOR_1_8": ((15 << 4) | 3, 0.125),
    "FACTOR_1_16": ((15 << 4) | 4, 0.0625),
    "FACTOR_1_32": ((15 << 4) | 5, 0.03125),
    "FACTOR_3_4": ((1 << 8) | (2 << 4) | 0, 0.75),
    "FACTOR_7_16": ((1 << 8) | (4 << 4) | 1, 0.4375),
    "FACTOR_3_8": ((3 << 4) | 2, 0.375),
}


# ------------------------------------------------------------------ tests ----
#
# RETIRED 2026-09-05 (second retirement of the day):
# test_drawn_planks_are_one_translation_tiled_lattice.
#
# It checked the parallel-plank shear's four preconditions — one period for the
# whole band, that period an even divisor of the 512-px wrap, one non-zero lean
# explaining every seam, and the tone alternation closing across x = 0. Each was
# a real property of that art and its red-first battery was run. It is retired
# because THE SHEAR IS GONE, not because it went green: the owner rejected it in
# the sentence quoted at the top of this file, and every one of those four
# checks is now actively WRONG for the subject. "One period for the whole band"
# is the exact opposite of a fan, whose period is proportional to the depth row;
# demanding it would fail the correct art. An arm that fails the correct subject
# is worse than an arm that cannot fail.
#
# Its two replacements below split the job the way the geometry does: one arm on
# the ART alone (the period law), one on the ART COMPOSITED THROUGH THE ENGINE'S
# SCROLL (the apex), because the shear-era failure was invisible to any check
# that looked at only one of them.


def test_drawn_beam_period_is_proportional_to_the_depth_row():
    """THE FAN'S LAW IN THE ART, measured off the rendered pixels.

    A beam is a straight line through the vanishing point exactly when its row's
    period is proportional to that row's distance below the apex — and the
    engine's curve ramps its scroll over the same rows from the same zero, so
    the RATIO scroll/period is constant and the composited beams stay straight
    lines through a FIXED point. Break the proportionality and the ratio moves
    with the row, which is a shear; that is what a nine-step snapped staircase
    did for three weeks and what a constant period (the shear) did for an hour.

    So: fit the measured period against the depth row and require a straight
    line through the origin. The intercept is the part that matters — a snapped
    or offset period fits a line with the wrong intercept even when its slope is
    right.

    RED-FIRST, run 2026-09-05 by rewriting tools/perspective_floor_gen.py ON
    DISK, running this arm alone, and restoring from `git show HEAD:...` before
    the next. Mutation text quoted from the file after the edit; exit codes are
    pytest's, read from a redirected file.

      mutation, as it read on disk                    exit  measured spread
      (unmutated baseline)                              0   0.66%  pass
      return near_pitch                                 1   3457%  (66 rows)
        [constant period = the parallel-plank shear]
      return near_pitch * dy / float(span - 1) + 8.0    1   21.6%  (37 rows)
        [the period offset: proportional plus a constant]
      p = near_pitch*dy/(span-1);                       1   4.81%  (18 rows)
        return 512.0/max(1, round(512.0/p))
        [wrap-exact snapping — the OTHER candidate art, the one that tiles
         the plane wrap exactly and is rejected for the reason in
         perspective_floor_gen.py's header. This is the row that sets the
         tolerance, and it is the row an earlier draft went GREEN on]
      SHIPPED near_pitch=40.0                           0   0.48%  pass
        [the CONTROL: a different-but-correct fan must stay green. It did NOT
         on the first attempt — the period estimator mis-read one row by 3x
         and reported 7.8% — which is a defect in the ARM, and row_period()'s
         cap and ROW_RESIDUAL_TOL are the fix. The whole battery was re-run
         against the estimator as it now stands.]
    """
    px, rows, shade_px, span = pfg.shipped_band()
    located, dropped = plane_seam_rows(px, shade_px, span)

    # LOUD ON UNMEASURABLE, FIRST. A change that stopped drawing seams — or
    # stopped cutting them past WOOD index 1 — would leave everything below
    # vacuously true. The floor of "how many rows must draw seams" is DERIVED
    # from the art's own knobs, not pinned: a row draws seams when its period
    # clears --lod-px, and the period is near_pitch*dy/(span-1).
    s = pfg.SHIPPED
    # Rows at FULL seam contrast, i.e. period past --lod-px AND past the fade.
    # A row inside the fade draws its seams too faintly for some of them to
    # cross the WOOD-index threshold, so it is a row this detector may partly
    # miss BY DESIGN; counting those into the floor would make the floor a lie.
    full = sum(1 for dy in range(span)
               if pfg.beam_period(dy, span, s["near_pitch"])
               > s["lod_px"] + s["lod_fade"])
    assert full >= 12, (
        "the shipped knobs only ask for %d rows of full-contrast seams; there "
        "is not enough fan here to fit a line to. Lower --lod-px or coarsen "
        "--near-pitch." % full)
    # Slack: the cross-seam rows are dropped by DARK_ROW_FRACTION and there are
    # up to span/12 of them, so a band where EVERY row clears --lod-px still
    # loses that many. Measured red-first: at `full - 2` a constant-period
    # mutation tripped THIS guard instead of the ratio assert below, which
    # reports the wrong defect. The guard is only here to stop the arm going
    # vacuous, so it is set to catch "the detector saw nothing", not "the
    # detector saw a different amount than I predicted".
    assert len(located) >= full - max(2, span // 12), (
        "located seams on only %d rows, against the %d the art draws at full "
        "contrast (period past --lod-px %.1f + --lod-fade %.1f); the detector "
        "is not seeing the art it is supposed to score"
        % (len(located), full, s["lod_px"], s["lod_fade"]))
    assert dropped <= span // 8, (
        "%d of the %d floor rows are more than %.0f%% dark, so their runs are "
        "beam bodies rather than seams. That is expected for the handful of "
        "cross-seam rows; this many means the band as a whole went dark."
        % (dropped, span, 100 * DARK_ROW_FRACTION))

    # THE TEST IS ON THE RATIO period/dy, NOT ON A FITTED INTERCEPT. Both say
    # "proportional", but the seam rows all sit in the near third of the band
    # (dy 53..71 at the shipped knobs, because --lod-px stops the far rows), so
    # extrapolating a fitted line back to dy = 0 multiplies the measurement
    # noise by the lever arm ~53/18 and the intercept is worth +-1.5 px before
    # the art has done anything wrong. The ratio needs no extrapolation.
    ratios, unreadable = [], 0
    for dy, cs in located:
        if dy <= 0:
            continue
        period, resid = row_period(cs)
        if resid > ROW_RESIDUAL_TOL:
            unreadable += 1
            continue
        ratios.append((dy, period / dy))
    assert len(ratios) >= 8, (
        "only %d rows could be read as a uniform seam lattice (%d were dropped "
        "as unreadable); that is not enough to say anything about the period law"
        % (len(ratios), unreadable))
    assert unreadable <= max(2, len(located) // 8), (
        "%d of %d seam rows do not fit ANY uniform lattice within %.1f px. The "
        "seams are not evenly spaced within a row, which no fan draws."
        % (unreadable, len(located), ROW_RESIDUAL_TOL))
    lo = min(r for _, r in ratios)
    hi = max(r for _, r in ratios)
    spread = (hi - lo) / lo

    assert hi > 0.05, (
        "the drawn period is %.4f px per depth row or less: the beams are "
        "parallel, not a fan, and there is no vanishing point for them to "
        "converge on." % hi)
    # MEASURED on the shipped band: 0.66%. The tolerance is 2%, which is 3x
    # that, and every mutation in the battery above clears it by a wide margin
    # (constant period 34%, +8 px offset 6.8%, wrap-exact snapping 2.4%).
    assert spread <= 0.02, (
        "the drawn period is not proportional to the depth row: period/row runs "
        "from %.5f to %.5f across the %d measured rows, a spread of %.2f%%. The "
        "engine's scroll IS proportional to the depth row, so a period that is "
        "not means the ratio scroll/period moves down the band — and a moving "
        "ratio is a shear, which is the defect this file exists for. A constant "
        "period (parallel beams) reads ~34%% here and a snapped one ~2.4%%."
        % (lo, hi, len(ratios), 100 * spread))


def test_composited_beams_converge_on_the_screen_centre_column():
    """THE OWNER'S OWN PROPERTY, measured on the composited screen.

    "when one of the beams of the floor at the top hits the center, the bottom
    should hit the center" — i.e. one vanishing point, on the screen's centre
    column, at EVERY camera x. This arm composites the rendered art through
    curve_probe's transcription of the engine's per-line ramp, then lets every
    adjacent-row seam pair vote for the column its beam converges on.

    IT IS ALSO THE WRAP GATE, and that is why it sweeps camera x. Plane B wraps
    every 512 px against a 320-px screen, so the floor's near row may slide 192
    px before the wrap brings the NEXT copy of the fan onto the screen; that
    copy's apex is 512 px away and its beams vote for it. The slide rate is the
    scene's curve end factor, so this arm fails if that factor is raised without
    the art changing — which is the coupling nothing could see before.

    RED-FIRST, 2026-09-05, same method as the arm above:

      mutation, as it read on disk                    exit  what fired
      (unmutated baseline)                              0   pass
      scene curve To(FACTOR_1)                          1   at camX 420 the
        [the factor the scene carried until this            beams converge on
         morning; clean range 192 px]                       column 194.0, not
                                                            159.5
      scene curve To(FACTOR_1_2)                        1   clean range 384 px,
        [clean range 384 px, i.e. inside a walk]            which the forward-
                                                            looking assert
                                                            refuses
      SHIPPED vp_col 20 -> 12                           1   at camX 0 the beams
        [the apex moved 64 px off the centre column]        converge on column
                                                            97.0, not 159.5
        [THIS ONE WENT GREEN ON THE FIRST DRAFT, exit 0, because the arm took
         its expectation from SHIPPED["vp_col"] — so moving the art moved the
         expectation with it. That is the tautology this whole file is written
         against. The expectation now comes from SCREEN_W.]
    """
    px, rows, shade_px, span = pfg.shipped_band()
    _world_y, _fb, curve_to = scene_curve_to()
    assert curve_to in FACTOR_WORDS, (
        "the floor's curve ramps to %s, which this file has no packed word for. "
        "Add it to FACTOR_WORDS from engine/level/parallax_dsl.emp rather than "
        "letting the arm skip it." % curve_to)
    word, frac = FACTOR_WORDS[curve_to]

    # The clean camera range the wrap allows, DERIVED here rather than copied:
    # the window is SCREEN_W wide inside a PLANE_W wrap and slides at camX*frac.
    clean = (pfg.PLANE_W - SCREEN_W) / frac
    cams = [0, 180, 420]

    # THE APEX EXPECTATION COMES FROM THE SCREEN, NOT FROM THE GENERATOR. It was
    # `pfg.SHIPPED["vp_col"] * 8 - 0.5` in the first draft of this arm, and the
    # red-first battery caught that: mutating vp_col 20 -> 12 moved the art's
    # apex 64 px off centre AND moved this expectation with it, and the arm
    # stayed GREEN (measured, exit 0). The requirement is the owner's — the
    # beams converge on the SCREEN's centre column — so that is what is written
    # here, and the generator gets no vote on it.
    apex = SCREEN_W / 2.0 - 0.5                      # 159.5
    for cam in cams:
        rows_s = screen_seam_rows(px, shade_px, span, hscroll(cam, word))
        assert len(rows_s) >= 12, (
            "camera x %d composites only %d readable seam rows; this arm cannot "
            "conclude anything at that camera position" % (cam, len(rows_s)))
        votes = apex_votes(rows_s)
        assert len(votes) >= 60, (
            "camera x %d yields only %d apex votes" % (cam, len(votes)))
        votes.sort()
        median = votes[len(votes) // 2]
        # The matcher pairs seams between adjacent rows by nearest neighbour;
        # seams 20-32 px apart moving up to 5 px per row mis-pair occasionally,
        # and a mis-pair votes anywhere. MEASURED on a correct fan across camera
        # x 0..1400: 8-21% of votes land more than 60 px off. A wrap copy pushes
        # that to 62% at camX 420 and 97% at 600, so 35% separates them cleanly.
        off = sum(1 for a in votes if abs(a - apex) > 60)
        assert abs(median - apex) <= 25.0, (
            "at camera x %d the beams converge on screen column %.1f, not on "
            "the screen's centre column %.1f. The floor has a vanishing point "
            "but it is in the wrong place — the owner asked for it on the "
            "centre, and this arm takes that number from SCREEN_W, not from the "
            "art." % (cam, median, apex))
        assert off <= 0.35 * len(votes), (
            "at camera x %d, %d of %d beam votes (%.0f%%) point at an apex more "
            "than 60 px off %.1f. Beams that vote for an apex ~512 px away are "
            "the 512-px plane wrap showing the NEXT copy of the fan — the "
            "owner's \"the first few are good then a few after get weird and "
            "point away\". The scene ramps to %s, whose clean camera range is "
            "%.0f px." % (cam, off, len(votes), 100.0 * off / len(votes), apex,
                          curve_to, clean))

    # LAST, so that a factor raised past what the art can carry fails on the
    # BEAMS above (the real defect, with its vote count) rather than here. This
    # is the same statement looking forward instead of at the three sampled
    # camera positions: he does not stop walking at 420.
    assert clean > max(cams) * 1.1, (
        "the scene ramps the floor to %s, so the wrap's next apex reaches the "
        "screen at camera x %.0f — inside, or barely past, the range this arm "
        "samples (%s), and well inside a walk. Either lower the curve end "
        "factor or stop drawing a fan." % (curve_to, clean, cams))


def test_committed_override_carries_the_generated_band():
    """The ROM's art must BE the generator's art.

    The generator's parameters are edited far more often than the bake is re-run,
    and a stale band is invisible: the blob length does not move (the floor
    recycles its own slots), so neither the tile budget report nor the room gate
    can see it. tools/level_staleness.py catches an unbaked editor_bg_override
    .json; nothing caught an override that was never regenerated after the
    generator changed. This does.
    """
    px, rows, _, _ = pfg.shipped_band()
    got = override_band_pixels()
    assert len(got) == len(px) == len(rows) * 8
    for i, (a, b) in enumerate(zip(px, got)):
        assert a == b, (
            "plane pixel row %d (cell row %d) of the committed floor band is not "
            "what tools/perspective_floor_gen.py renders today. Re-run "
            "`python3 tools/perspective_floor_gen.py && ./tools/regenerate-level.sh`."
            % (pfg.SHIPPED["row0"] * 8 + i, pfg.SHIPPED["row0"] + i // 8))


def test_baked_plane_b_carries_the_generated_band():
    """The BAKED artifacts, not the editor document, must carry the fan.

    test_committed_override_carries_the_generated_band above compares the
    generator against `editor_bg_override.json` — the editor-side SOURCE. This
    arm goes one stage further down the pipeline and decodes what the build
    actually consumes: `zone_bg.bin` (the 64x64 nametable, COLUMN-major, with
    BG_TILE_BASE_SLOT already folded into every non-zero word) and
    `bg_tiles.bin` (a 2-byte BE blob LENGTH then 4bpp tile data). The build reads
    games/sonic4/data/generated/ DIRECTLY — prebuild.sh is a no-op — so these
    two files are the plane the ROM ships.

    The gap this closes is real and was live for part of 2026-09-05: running
    `tools/inject_editor_bg.py` by hand updates these files but not the editor
    stamp, and running neither leaves them from the PREVIOUS art while the
    override and every generator-side check agree with each other perfectly.
    tools/level_staleness.py catches the stamp; this catches the pixels.
    """
    import struct
    from vram_map import BG_TILE_BASE_SLOT
    gen = os.path.join(REPO, "games/sonic4/data/generated/ojz/act1")
    nt_path = os.path.join(gen, "zone_bg.bin")
    tl_path = os.path.join(gen, "bg_tiles.bin")
    for f in (nt_path, tl_path):
        assert os.path.isfile(f), (
            "%s is missing — the level tree has never been baked, and this arm "
            "would otherwise pass by not running" % f)

    nt = open(nt_path, "rb").read()
    raw = open(tl_path, "rb").read()
    assert len(nt) == pfg.PLANE_COLS * pfg.PLANE_ROWS * 2, (
        "zone_bg.bin is %d bytes, expected %d for a 64x64 nametable"
        % (len(nt), pfg.PLANE_COLS * pfg.PLANE_ROWS * 2))
    # The 2-byte BE header is the BLOB LENGTH IN BYTES, not a tile count —
    # measured: it reads 10240 for a 320-tile blob.
    nbytes = struct.unpack_from(">H", raw, 0)[0]
    assert len(raw) == 2 + nbytes and nbytes % 32 == 0, (
        "bg_tiles.bin declares %d bytes of tile data but carries %d, or the "
        "length is not a whole number of 32-byte tiles" % (nbytes, len(raw) - 2))
    count = nbytes // 32

    def tile_px(idx):
        out = []
        for b in raw[2 + idx * 32:2 + idx * 32 + 32]:
            out.append((b >> 4) & 15)
            out.append(b & 15)
        return out

    px, rows, _shade, _span = pfg.shipped_band()
    s = pfg.SHIPPED
    for ri, cy in enumerate(range(s["row0"], s["row1"] + 1)):
        for iy in range(8):
            want = px[ri * 8 + iy]
            for cx in range(pfg.PLANE_COLS):
                # COLUMN-major: inject_editor_bg.py packs at (col*ROWS + row)*2
                w = struct.unpack_from(">H", nt, (cx * pfg.PLANE_ROWS + cy) * 2)[0]
                idx = (w & 0x7FF) - BG_TILE_BASE_SLOT
                assert 0 <= idx < count, (
                    "plane cell (%d,%d) addresses VRAM tile %d, which is %d "
                    "after removing BG_TILE_BASE_SLOT %d — outside the %d-tile "
                    "blob" % (cx, cy, w & 0x7FF, idx, BG_TILE_BASE_SLOT, count))
                t = tile_px(idx)
                sy = 7 - iy if (w >> 12) & 1 else iy
                for ix in range(8):
                    sx = 7 - ix if (w >> 11) & 1 else ix
                    assert t[sy * 8 + sx] == want[cx * 8 + ix], (
                        "the BAKED plane differs from the art at plane pixel "
                        "(%d,%d): zone_bg.bin/bg_tiles.bin say %d, "
                        "perspective_floor_gen renders %d. The generated tree "
                        "was not re-baked from the current art — run "
                        "`tools/regenerate-level.sh` (NOT inject_editor_bg.py "
                        "alone, which leaves the editor stamp behind)."
                        % (cx * 8 + ix, cy * 8 + iy, t[sy * 8 + sx],
                           want[cx * 8 + ix]))


def test_scene_curve_band_matches_the_art_band():
    """THE CROSS-FILE SEAM, and the one nothing could see.

    The art's depth index and the engine ramp's line index have to be the SAME
    number. The art's fan starts at plane pixel row `horizon_row * 8` and runs to
    the bottom of the band; the engine's ramp starts at the curve layer's top
    screen line and runs to line 223, and the curve hoist derives that band's
    span as SCREEN_HEIGHT minus its top line (parallax.emp, `.curve_have_end`).
    If those two windows disagree by even one row, every row of the floor picks
    up a constant scroll offset and the whole fan — apex included — translates
    with the camera. That was live until 2026-09-05, at one row.

    Parsed rather than pinned: the numbers come out of ojz_scenes.emp, so moving
    the layer moves the expectation and moving only ONE of them fails here.

    THE END FACTOR IS DELIBERATELY NOT PINNED HERE. It used to be asserted
    == FACTOR_1. That was a pin on a value whose correct setting depends on the
    art, and it would have had to be edited by hand every time either moved.
    test_composited_beams_converge_on_the_screen_centre_column tests it the way
    it actually matters — by compositing the art through it and looking at where
    the beams point — so this arm only insists the ramp still STARTS at zero.
    """
    src = open(SCENES).read()
    world_y, fb, curve_to = scene_curve_to()
    world_y = int(world_y)

    scene = re.search(r"pub const Scene_Perspective_Floor: Scene = scene\((.*?)\n\n",
                      src, re.S)
    assert scene, "Scene_Perspective_Floor is gone from %s" % SCENES
    vo = re.search(r"v_offset:\s*(\d+)", scene.group(1))
    assert vo, "Scene_Perspective_Floor authors no v_offset"
    v_offset = int(vo.group(1))

    # The ramp must start at zero scroll, or the band's first line is already
    # displaced and the apex is not on the art's vanishing point.
    assert fb == "FACTOR_0", (
        "the floor's curve layer bases at %s, not FACTOR_0: the ramp would start "
        "the band at a non-zero scroll, so the apex row itself would slide and "
        "the vanishing point would travel with the camera" % fb)

    s = pfg.SHIPPED
    art_fan_plane_top = s["horizon_row"] * 8          # first plane row of the fan
    art_fan_rows = (s["row1"] + 1 - s["horizon_row"]) * 8

    band_top_line = world_y - v_offset                # scene_plane_line's mapping
    band_span = SCREEN_H - band_top_line              # the curve hoist's last-band span

    assert band_top_line == horizon_line(), (
        "the curve layer lands on screen line %d but this file composites the "
        "band from line %d. One of v_offset (%d), world_y (%d) and the art's "
        "row0/horizon_row (%d/%d) moved without the others."
        % (band_top_line, horizon_line(), v_offset, world_y, s["row0"],
           s["horizon_row"]))
    assert world_y == art_fan_plane_top, (
        "the curve layer starts at plane row %d but the art's fan starts at plane "
        "row %d (horizon_row %d * 8). The ramp's line index and the art's depth "
        "index must be the same number."
        % (world_y, art_fan_plane_top, s["horizon_row"]))
    assert band_span == art_fan_rows, (
        "the curve ramps over %d screen lines (%d .. 223) but the art draws %d "
        "rows of fan (plane rows %d .. %d). The ratio scroll/period is constant "
        "only when the two spans agree."
        % (band_span, band_top_line, art_fan_rows,
           art_fan_plane_top, (s["row1"] + 1) * 8 - 1))


if __name__ == "__main__":
    test_drawn_beam_period_is_proportional_to_the_depth_row()
    test_composited_beams_converge_on_the_screen_centre_column()
    test_committed_override_carries_the_generated_band()
    test_baked_plane_b_carries_the_generated_band()
    test_scene_curve_band_matches_the_art_band()
    print("perspective floor: all five checks pass")
