#!/usr/bin/env python3
"""test_perspective_floor — the law the OJZ floor's plank lattice rests on, checked.

WHY THIS FILE EXISTS. Between 2026-08-16 and 2026-09-05 the floor's drawn board
pitch was a nine-step staircase (`boards_across()` snapped the board count to an
even integer per row so the lattice would close on the 512-px plane wrap) while
the engine ramped that band's scroll LINEARLY across the same rows. Four shapes
built green the whole time, the tile budget was respected, the room gate passed,
and nothing anywhere compared the art's geometry with the scroll that would be
applied to it. These three tests are that comparison.

THE ART CHANGED SHAPE ON 2026-09-05 and one arm was retired with it — see the
block above test_drawn_planks_are_one_translation_tiled_lattice, which says what
the retired arm tested and why a shear makes it unfailable. The floor is no
longer a fan: it is one lattice of parallel planks, period 64 px, leaning 0.5 px
per row, chosen by the owner over a fan whose apex the 512-px wrap copies off
the side of the screen.

THE PROPERTY THAT MAKES THIS FILE WORTH ANYTHING, and it survived the rewrite:
every number checked below is VOTED FOR OFF THE RENDERED PIXELS. Nothing here
asks perspective_floor_gen what it meant to draw. An early draft compared the
drawn seams against `board_pitch()`'s own output, which made the check a
tautology — the even-snap mutation was applied on disk and the test still passed
(measured 2026-09-05). Any arm added here must keep that property.

They are cheap and boot nothing: build.sh's pytest lane sweeps tools/test_*.py.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perspective_floor_gen as pfg

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDE = os.path.join(REPO, "games/sonic4/data/editor_bg_override.json")
SCENES = os.path.join(REPO, "games/sonic4/data/effects/ojz_scenes.emp")

SCREEN_H = 224                   # engine/system/constants.emp SCREEN_HEIGHT; the
                                 # curve hoist's span for the LAST band is
                                 # SCREEN_HEIGHT - that band's top line.
WOOD_INDEX = {v: i for i, v in enumerate(pfg.WOOD)}


# ---------------------------------------------------------------- helpers ----
def seam_centres(row):
    """Plane-x centres of the drawn plank seams in one 512-px row.

    Measured OFF THE PIXELS, not read back from the model: a seam is where
    render_band subtracts 2.4 from the wood level, which lands it on WOOD index
    0 or 1 whichever way the plank alternation went, while no non-seam pixel
    gets below index 2. Thresholding on the index rather than on the row minimum
    is what makes both plank parities count — taking the minimum finds only the
    darker parity and reports twice the pitch.

    The run that straddles x = 0 is stitched back together and reported at its
    true (negative) centre, so the wrap is not scored as two half-seams.
    """
    ind = [1 if WOOD_INDEX[v] <= 1 else 0 for v in row]
    if not any(ind) or all(ind):
        return []
    runs, cur = [], None
    for x in range(pfg.PLANE_W):
        if ind[x]:
            cur = [x, x] if cur is None else [cur[0], x]
        elif cur:
            runs.append(cur)
            cur = None
    if cur:
        runs.append(cur)
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == pfg.PLANE_W - 1:
        runs[0] = [runs[-1][0] - pfg.PLANE_W, runs[0][1]]   # the run across x=0
        runs.pop()
    return sorted((a + b) / 2.0 for a, b in runs)


DARK_ROW_FRACTION = 0.20         # above this, the dark runs in a row are not
                                 # seams. A seam is drawn where `frac` exceeds
                                 # 0.5 - 0.9/pitch, i.e. ~1.8 px of every
                                 # `pitch`, so a row of real seams is a few
                                 # percent dark. A CROSS-seam row (the plank
                                 # ends) subtracts 1.6 from the whole row, which
                                 # pushes the darker plank PARITY under the
                                 # threshold as well — measured on the shipped
                                 # band, those rows come back 51% dark and the
                                 # run centres they report are plank centres,
                                 # half a period away from the seams. Scoring
                                 # them would be scoring the wrong feature, so
                                 # they are dropped and COUNTED.


def seam_rows(px, shade_px, span, min_seams=4):
    """(dy, [seam plane-x]) for every floor row whose seams can be located.

    Rows whose dark fraction says the runs are not seams are dropped; the count
    is returned so the caller can refuse to conclude anything if too many were.
    """
    out, dropped = [], 0
    for dy in range(span):
        row = px[shade_px + dy]
        dark = sum(1 for v in row if WOOD_INDEX[v] <= 1)
        if dark > DARK_ROW_FRACTION * pfg.PLANE_W:
            dropped += 1
            continue
        cs = seam_centres(row)
        if len(cs) >= min_seams:
            out.append((dy, cs))
    return out, dropped


def plank_tones(px, shade_px, span, period, phase):
    """Mean wood index of each plank's interior, averaged down the whole floor.

    The plank interior is the middle half of each period, which keeps the seam
    and the crown out of the mean. `phase` and `period` are the values VOTED FOR
    off the pixels by estimate_skew/estimate_period, so this reads the planks the
    art actually drew, not the ones the generator meant to.
    """
    n = int(round(pfg.PLANE_W / period))
    sums = [0.0] * n
    counts = [0] * n
    for dy, _cs in seam_rows(px, shade_px, span)[0]:
        row = px[shade_px + dy]
        for k in range(n):
            centre = phase + period * (k + 0.5)
            for t in range(int(-period / 4), int(period / 4) + 1):
                x = int(round(centre + t)) % pfg.PLANE_W
                sums[k] += WOOD_INDEX[row[x]]
                counts[k] += 1
    return [sums[k] / counts[k] for k in range(n) if counts[k]]


def estimate_period(rows_seams, tol=1.2):
    """The plank period, voted for over the drawn seams and NOTHING ELSE.

    A one-parameter Hough vote across every located row at once: for each
    candidate period p, count the seams that land within `tol` px of SOME
    lattice of period p (the phase is fitted per row, so a sheared lattice
    scores exactly as well as an upright one). Among ties the LARGEST p wins.

    WHY "LARGEST TIE WINS" IS THE WHOLE CORRECTNESS ARGUMENT, and it is
    unchanged from the fan-era version of this file. A p above the true period
    always misses seams, so it can never tie. A p below it can: p/3 puts its
    lattice on multiples of p/3, which contains every multiple of p, so it fits
    the true seams and adds spurious ones. Taking the largest maximiser
    therefore lands on the true period. NOTHING here consults
    perspective_floor_gen's model — that is the property that made the previous
    draft of this file worth keeping and it is preserved deliberately: an
    earlier draft compared the drawn seams against `board_pitch()`'s own output,
    the mutation was applied on disk, and the test still passed.
    """
    best = None
    p = 4.0
    while p <= 130.0:
        hits = 0
        for dy, cs in rows_seams:
            # fit the phase for this row from its own first seam, then count
            phase = cs[0]
            for c in cs:
                r = (c - phase) / p
                if abs(r - round(r)) * p <= tol:
                    hits += 1
        if best is None or hits > best[0] or (hits == best[0] and p > best[1]):
            best = (hits, p)
        p += 0.02
    return best


def estimate_skew(rows_seams, period, tol=1.2):
    """The lattice's lean in plane px per pixel row, voted for over the seams.

    Same shape of argument as estimate_period: for each candidate skew k, score
    how many seams land on the SINGLE lattice {phase + k*dy + j*period} with one
    global phase, fitted from the residues. A shear has one k that explains
    every row; a fan has none, because its period changes with the row.
    """
    best = None
    k = -4.0
    while k <= 4.0001:
        # residues of every seam against a k-sheared lattice, as a circular mean
        import math as _m
        sx = sy = 0.0
        n = 0
        for dy, cs in rows_seams:
            for c in cs:
                a = 2 * _m.pi * ((c - k * dy) % period) / period
                sx += _m.cos(a)
                sy += _m.sin(a)
                n += 1
        if n:
            phase = (_m.atan2(sy, sx) / (2 * _m.pi)) * period
            hits = 0
            for dy, cs in rows_seams:
                for c in cs:
                    d = ((c - k * dy - phase) % period)
                    d = min(d, period - d)
                    if d <= tol:
                        hits += 1
            if best is None or hits > best[0]:
                best = (hits, k, phase)
        k += 0.01
    return best


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


# ------------------------------------------------------------------ tests ----
#
# RETIRED 2026-09-05: test_drawn_board_pitch_is_linear_in_the_ramp_index.
#
# It fitted the drawn board pitch against the depth row and required the fit to
# be linear with a zero intercept, because a radial fan survives horizontal
# scroll only when each row's pitch is proportional to that row's scroll. That
# law was real and the arm was doing its job — it is what caught the nine-step
# staircase. It is retired because THE FAN IS GONE, not because it went green:
# the owner chose parallel planks over a fan whose apex the 512-px wrap copies
# off the side of the screen ("we need it all just skewed in one direction
# instead of trying to work around it having one part point at us"). Under a
# shear the drawn period is the SAME on every row by construction, so a fit of
# pitch against depth row is a fit of a constant: slope 0, residual 0, and it
# would pass for any shear whatsoever, including a broken one. An arm that
# cannot fail is worse than no arm.
#
# test_drawn_planks_are_one_translation_tiled_lattice below is its replacement
# and it tests the shear's own two preconditions instead — one period for the
# whole band, and that period an even divisor of the wrap. It keeps the retired
# arm's one non-negotiable property: every number it checks is voted for OFF THE
# PIXELS, and it never calls perspective_floor_gen.render_band's model to find
# out what it should have drawn.


def test_drawn_planks_are_one_translation_tiled_lattice():
    """THE SHEAR'S LAW, measured off the rendered pixels with no model in the loop.

    Three things have to hold, and each one is a defect the fan actually had:

      (1) ONE PERIOD FOR THE WHOLE BAND. The fan's period was proportional to the
          depth row; forcing that to close on the 512-px wrap quantised it into a
          staircase of constant-pitch runs, and a constant pitch over a run of
          rows draws VERTICAL boards. Here there is a single period, so every row
          must vote for the same one.
      (2) THAT PERIOD DIVIDES THE WRAP AN EVEN NUMBER OF TIMES. This is the whole
          reason the shear closes: 512/period integer means the lattice tiles by
          translation with no straddling plank, and EVEN means the plank tone
          alternation comes back to itself across x = 0 instead of putting a
          same-tone pair at the wrap.
      (3) THE PLANKS ACTUALLY LEAN, AND ALL THE SAME WAY. One skew explains every
          seam on every row. A non-zero skew is what stops the floor being the
          vertical stripes the owner rejected ("it's just a line pointing down").

    RED-FIRST. Every row below was measured on 2026-09-05 by rewriting
    tools/perspective_floor_gen.py ON DISK, running this arm alone, and restoring
    the file from the COMMITTED baseline (`git show HEAD:...`) before the next
    one. The mutation text is quoted from the file after the edit, not from the
    patch that made it. Exit codes are pytest's, read directly.

      mutation, as it read on disk                              exit  arm
      (unmutated baseline)                                        0   pass
      q = (((x-vx+256.0)%512.0)-256.0)/max(1e-6,pitch*dy/(span-1))  1   (1): one
        [the fan restored: period proportional to the depth row]        period
                                                                        explains
                                                                        523/676
                                                                        seams
      level += 0.6 if (j % 3) else -0.6                            1   (4): same-
                                                                        tone
                                                                        neighbours
                                                                        at planks
                                                                        [0,3,6,7]
      q = (x - vx - 0.0 * dy) / float(pitch)                       1   (3): lean
                                                                        -0.01
      SHIPPED pitch=52 (does not divide 512)                       1   caught
                                                                        UPSTREAM by
                                                                        plank_lattice
                                                                        (), not by
                                                                        this arm
      q = (x - vx - skew * dy) / float(52)                         1   (2): 52.02
        [52 in the rasteriser only, so plank_lattice() sees 64]          px goes
                                                                        9.842 times
                                                                        into 512
      SHIPPED pitch=128 (divides 512 four times, EVEN)             0   pass
        [the CONTROL: a different-but-legal lattice must stay green]

    THE METHOD CHANGED PART-WAY, and the earlier rows were re-run after it did.
    The first battery had arms (1)-(3) only, and `if (j % 3)` came back GREEN —
    applied-and-still-green, which is a defect in the arm and not a pass. Arms
    (1)-(3) only ever look at where the SEAMS are, and every tone scheme puts its
    seams in the same places. Arm (4) was added for exactly that hole and the
    WHOLE battery above, including the rows that had already gone red, was re-run
    against the arm as it now stands.
    """
    s = pfg.SHIPPED
    px, rows, shade_px, span = pfg.shipped_band()
    located, dropped = seam_rows(px, shade_px, span)

    # LOUD ON UNMEASURABLE, FIRST. A change that stopped drawing seams — or
    # stopped cutting them past WOOD index 1 — would leave every assertion below
    # vacuously true. The floor is derived from the art, not pinned: the rows
    # that can draw seams are the rows below the horizon whose contrast has faded
    # in, i.e. every row past dy 0, and at the shipped period there are
    # PLANE_W/pitch of them per row.
    assert located, (
        "not one row of the band draws a locatable plank seam — this arm can "
        "prove nothing. Did --fade-rows or the seam depth change?")
    assert len(located) >= (span - int(s["fade_rows"])) // 2, (
        "located seams on only %d of the %d floor rows; the detector is not "
        "seeing the art" % (len(located), span))
    assert dropped <= span // 8, (
        "%d of the %d floor rows are more than %.0f%% dark, so their runs are "
        "plank bodies rather than seams and this arm cannot read them. That is "
        "expected for the handful of cross-seam rows; this many means the band "
        "as a whole went dark and the measurement below is not about seams."
        % (dropped, span, 100 * DARK_ROW_FRACTION))

    hits, period = estimate_period(located)
    total = sum(len(cs) for _, cs in located)

    # (1) ONE PERIOD. The vote has to explain essentially every seam in the band.
    #     Slack is the half-pixel a seam centre can sit off the true lattice
    #     because it is a run of whole pixels: at the shipped period that is
    #     inside the 1.2 px tolerance, so a correct band scores ~100%.
    assert hits >= 0.97 * total, (
        "a single plank period explains only %d of the %d drawn seams (%.1f%%). "
        "The rows disagree about the period, which is what a depth-ramped pitch "
        "looks like — and a pitch held constant over a run of rows draws "
        "vertical boards, then shears under the engine's linear scroll ramp. "
        "Best period %.2f px." % (hits, total, 100.0 * hits / total, period))

    # (2) EVEN DIVISOR OF THE WRAP. Derived from the plane width, not from
    #     SHIPPED: the wrap is a property of Plane B, the period is measured.
    n = pfg.PLANE_W / period
    assert abs(n - round(n)) <= 0.02, (
        "the measured plank period %.2f px goes %.3f times into the %d-px plane "
        "wrap, not a whole number of times. The lattice does not tile the wrap "
        "by translation, so the wrap carries a straddling plank of the wrong "
        "width — the artefact the fan had." % (period, n, pfg.PLANE_W))
    assert int(round(n)) % 2 == 0, (
        "%d planks across the %d-px wrap is ODD. The plank tone alternation has "
        "period 2, so it flips across x = 0 and puts a same-tone pair at the "
        "wrap." % (int(round(n)), pfg.PLANE_W))

    # (3) ONE LEAN, AND IT IS NOT ZERO. Voted for the same way as the period.
    shits, skew, _phase = estimate_skew(located, period)
    assert shits >= 0.97 * total, (
        "a single lean explains only %d of the %d drawn seams (%.1f%%) — the "
        "planks are not all parallel. Best skew %.2f px/row."
        % (shits, total, 100.0 * shits / total, skew))
    # (4) THE PLANK TONE ALTERNATION CLOSES ON THE WRAP. Added 2026-09-05 after
    #     the red-first battery found arms (1)-(3) BLIND to it: mutating
    #     `level += 0.6 if (j & 1)` to `if (j % 3)` left all three green, because
    #     they only ever looked at where the SEAMS are, and a tone scheme of any
    #     period puts its seams in the same places. A 3-periodic tone over the 8
    #     planks of the wrap draws +,-,-,+,-,-,+,- and the wrap then butts two
    #     same-tone planks together at plane x 0 — a plank of double width, which
    #     is the straddling-plank artefact wearing a different hat.
    #
    #     Read cyclically INCLUDING the pair that straddles x = 0, adjacent plank
    #     tones must differ. Measured off the plank interiors, and the two-class
    #     split is taken from the data (the midpoint of the observed means), not
    #     from the generator's +-0.6.
    tones = plank_tones(px, shade_px, span, period, _phase)
    assert len(tones) >= 4, (
        "read only %d plank tones; cannot say whether they alternate" % len(tones))
    mid = (min(tones) + max(tones)) / 2.0
    assert max(tones) - min(tones) > 0.5, (
        "the planks are all one tone (spread %.2f wood steps): there is no "
        "alternation to close on the wrap, and neighbouring planks are told "
        "apart by the seam alone" % (max(tones) - min(tones)))
    cls = [t > mid for t in tones]
    bad = [i for i in range(len(cls)) if cls[i] == cls[(i + 1) % len(cls)]]
    assert not bad, (
        "plank tones do not alternate around the wrap: same-tone neighbours at "
        "plank index %s of %d (the last entry is the pair that straddles plane "
        "x 0). Two same-tone planks butted together read as one plank of double "
        "width." % (bad, len(cls)))

    assert abs(skew) >= 0.2, (
        "the measured lean is %.2f px per row: the planks are drawn effectively "
        "VERTICAL. At camera x 0 the floor is then a field of upright stripes, "
        "which is what the owner reported as \"just a line pointing down\"."
        % skew)


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
    """
    src = open(SCENES).read()

    fn = re.search(r"pub comptime fn perspective_floor_layers\(\).*?\n\}", src, re.S)
    assert fn, ("perspective_floor_layers() is gone from %s — this test cannot "
                "locate the floor layer and is therefore proving nothing" % SCENES)
    curve_layers = [m for m in re.finditer(
        r"layer\(world_y:\s*(\d+)[^)]*?fb:\s*(FACTOR_\w+)[^)]*?curve:\s*SceneCurve\.To\((FACTOR_\w+)\)",
        fn.group(0), re.S)]
    assert len(curve_layers) == 1, (
        "expected exactly one curve layer in perspective_floor_layers(); found %d. "
        "The floor's whole geometry assumes a single linear ramp over the fan."
        % len(curve_layers))
    world_y, fb, curve_to = curve_layers[0].groups()
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
        "the band at a non-zero scroll and the fan's apex would not sit at the "
        "art's vanishing point" % fb)
    assert curve_to == "FACTOR_1", (
        "the floor's curve ramps to %s; the art's pitch is calibrated so that the "
        "near row scrolls at the full camera rate" % curve_to)

    s = pfg.SHIPPED
    art_fan_plane_top = s["horizon_row"] * 8          # first plane row of the fan
    art_fan_rows = (s["row1"] + 1 - s["horizon_row"]) * 8

    band_top_line = world_y - v_offset                # scene_plane_line's mapping
    band_span = SCREEN_H - band_top_line              # the curve hoist's last-band span

    assert world_y == art_fan_plane_top, (
        "the curve layer starts at plane row %d but the art's fan starts at plane "
        "row %d (horizon_row %d * 8). The ramp's line index and the art's depth "
        "index must be the same number."
        % (world_y, art_fan_plane_top, s["horizon_row"]))
    assert band_span == art_fan_rows, (
        "the curve ramps over %d screen lines (%d .. 223) but the art draws %d "
        "rows of fan (plane rows %d .. %d). The ratio scroll/pitch is constant "
        "only when the two spans agree."
        % (band_span, band_top_line, art_fan_rows,
           art_fan_plane_top, (s["row1"] + 1) * 8 - 1))


if __name__ == "__main__":
    test_drawn_planks_are_one_translation_tiled_lattice()
    test_committed_override_carries_the_generated_band()
    test_scene_curve_band_matches_the_art_band()
    print("perspective floor: all three checks pass")
