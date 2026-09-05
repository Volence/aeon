#!/usr/bin/env python3
"""test_perspective_floor — the law the OJZ floor's fan rests on, checked.

WHY THIS FILE EXISTS. Between 2026-08-16 and 2026-09-05 the floor's drawn board
pitch was a nine-step staircase (`boards_across()` snapped the board count to an
even integer per row so the lattice would close on the 512-px plane wrap) while
the engine ramped that band's scroll LINEARLY across the same rows. A drawn fan
survives horizontal scroll only when each row's scroll is proportional to THAT
ROW's drawn pitch, so the two disagreed by a factor that varied down the band —
at rest every plank pointed straight down, and in motion every plank sheared the
same way. Four shapes built green the whole time, the tile budget was respected,
the room gate passed, and nothing anywhere compared the art's geometry with the
scroll that would be applied to it. These three tests are that comparison.

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
def shipped_band():
    """The floor band exactly as the generator bakes it, plus its geometry."""
    s = pfg.SHIPPED
    rows = list(range(s["row0"], s["row1"] + 1))
    px = pfg.render_band(rows, pitch=s["pitch"], vp_col=s["vp_col"],
                         seam_rows=s["cross_seam_px"], lod_px=s["lod_px"],
                         horizon_row=s["horizon_row"], shade_near=s["shade_near"],
                         shade_far=s["shade_far"], crown=s["crown"])
    shade_px = (s["horizon_row"] - s["row0"]) * 8
    span = len(rows) * 8 - shade_px
    return px, rows, shade_px, span


def seam_centres(row):
    """Plane-x centres of the drawn plank seams in one 512-px row.

    Measured OFF THE PIXELS, not read back from the model: a seam is where
    render_band subtracts 2.4 from the wood level, which lands it on WOOD index
    0 or 1 whichever way the plank alternation went, while no non-seam pixel
    gets below index 2. Thresholding on the index rather than on the row minimum
    is what makes both plank parities count — taking the minimum finds only the
    darker parity and reports twice the pitch.
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


SEAM_SEARCH_CUT = 200.0          # plane px either side of the vanishing point to
                                 # take seams from. Comfortably inside the wrap
                                 # fold's |u| = 256 axis for every pitch this band
                                 # draws (the widest is `pitch`, 64), so the
                                 # straddling plank never enters the fit.


def estimate_pitch(us, tol=1.2):
    """The row's board pitch, estimated from seam positions and NOTHING ELSE.

    A one-parameter Hough vote: for each candidate pitch p, count how many of the
    detected seams land within `tol` px of the lattice {(k + 1/2) p}. Take the
    candidate with the most hits, and among ties the LARGEST p.

    WHY "LARGEST TIE WINS" IS THE WHOLE CORRECTNESS ARGUMENT. A p above the true
    pitch always misses seams, so it can never tie. A p below it can: p/3 puts its
    lattice on odd multiples of p/6, which contains every odd multiple of p/2, so
    it fits the true seams and adds spurious ones. Taking the largest maximiser
    therefore lands on the true pitch, and the estimate never consults the
    generator's model — which is the point. An earlier draft of this test compared
    the drawn seams against `board_pitch()`'s own output, which made the check a
    tautology: the even-snap mutation was applied on disk and the test still
    passed (measured 2026-09-05).
    """
    best = None
    p = 4.0
    while p <= 130.0:
        hits = 0
        for u in us:
            r = u / p - 0.5
            if abs(r - round(r)) * p <= tol:
                hits += 1
        if best is None or hits > best[0] or (hits == best[0] and p > best[1]):
            best = (hits, p)
        p += 0.02
    return best


def measured_pitches(px, shade_px, span, vx):
    """(dy, pitch) for every fan row whose seams can be located, from pixels."""
    out = []
    for dy in range(span):
        us = sorted(u for u in (((c - vx + 256.0) % 512.0) - 256.0
                                for c in seam_centres(px[shade_px + dy]))
                    if 0 < u <= SEAM_SEARCH_CUT)
        if len(us) < 3:
            continue
        hits, p = estimate_pitch(us)
        if hits < 3:
            continue
        out.append((dy, p))
    return out


def least_squares_line(points):
    n = len(points)
    sx = sum(q[0] for q in points)
    sy = sum(q[1] for q in points)
    sxx = sum(q[0] ** 2 for q in points)
    sxy = sum(q[0] * q[1] for q in points)
    a = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    b = (sy - a * sx) / n
    residual = max(abs(q[1] - (a * q[0] + b)) / q[1] for q in points)
    return a, b, residual


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
def test_drawn_board_pitch_is_linear_in_the_ramp_index():
    """THE LAW, measured off the rendered pixels with no model in the loop.

    The engine's per-line scroll across this band is linear in the screen line
    (parallax.emp `.lp_curve`: an exact-remainder Bresenham, so the emitted word
    is floor((line - top) * camX / span)). A drawn fan survives horizontal scroll
    only when each row's scroll is proportional to THAT ROW's drawn board pitch,
    so the pitch must be linear in the same index, with a ZERO intercept — the
    band's first line is the vanishing point, where the pitch is 0 and the scroll
    is 0.

    Three assertions, each with a bound derived from the geometry rather than
    read off a nearby number. RED-FIRST, all three measured on 2026-09-05 by
    rendering the alternative constructions and running this same fit:

        construction                 slope a   intercept b   max rel residual
        radial (shipped here)         0.9077     -0.070 px       0.0035
        even-snap (the defect)        0.9485     -1.306 px       0.1170
        radial, depth index off by 1  0.9078     +0.831 px       0.0035

    so the residual bound catches the staircase and the intercept bound catches
    the off-by-one, and neither bound is anywhere near the shipped values.
    """
    s = pfg.SHIPPED
    px, rows, shade_px, span = shipped_band()
    vx = s["vp_col"] * 8 - 0.5
    fit_rows = measured_pitches(px, shade_px, span, vx)

    # LOUD ON UNMEASURABLE, FIRST. A change that stopped drawing seams — or
    # stopped cutting them past WOOD index 1 — would leave the fit with nothing
    # and every assertion below vacuously true. The floor is derived: the rows
    # that draw seams are the rows whose pitch reaches lod_px, and the fit must
    # have located at least half of them.
    step = s["pitch"] / float(span - 1)          # the per-row pitch increment
    seam_rows = sum(1 for dy in range(span) if step * dy >= s["lod_px"])
    assert seam_rows > 0, (
        "no row of the band reaches lod_px (%.1f) — it draws no plank seams at "
        "all, and this test can prove nothing" % s["lod_px"])
    assert len(fit_rows) >= seam_rows // 2, (
        "located seams on only %d of the %d rows whose pitch reaches lod_px — "
        "the detector is not seeing the art" % (len(fit_rows), seam_rows))

    a, b, residual = least_squares_line(fit_rows)

    # (1) LINEARITY. A seam centre is a run of whole pixels, so it can sit half a
    #     pixel off the true lattice; relative to the pitch that is 0.5 / p, and
    #     p is at least lod_px on every row in the fit.
    res_bound = 0.5 / s["lod_px"]
    assert residual <= res_bound, (
        "the drawn board pitch is not linear in the depth row: worst relative "
        "residual %.4f over %d rows against a derived bound of %.4f "
        "(0.5 px / lod_px %.1f). A residual of this size means the pitch is "
        "QUANTISED — pitch held constant over a run of rows draws vertical "
        "boards, and under the engine's linear ramp every board in the run picks "
        "up the same slope and shears the same way. That was the 2026-09-05 "
        "defect. Fitted a=%.4f b=%+.3f."
        % (residual, len(fit_rows), res_bound, s["lod_px"], a, b))

    # (2) ZERO INTERCEPT. The pitch at the band's first line must be 0, because
    #     that line is where the engine's ramp is 0. Getting the depth index off
    #     by one row moves the intercept by exactly one `step`; half a step is
    #     the bound that separates the two.
    assert abs(b) <= 0.5 * step, (
        "the drawn pitch extrapolates to %+.3f px at the band's first line, not "
        "0, against a bound of half a row's pitch step (%.3f px). The art's depth "
        "index and the engine ramp's line index are not the same number, and "
        "every row of the floor carries a constant scroll offset — the whole fan, "
        "apex included, then translates with the camera."
        % (b, 0.5 * step))

    # (3) THE NEAR ROW IS THE PITCH THAT WAS ASKED FOR. Slack is the same
    #     half-pixel seam quantisation, spread over the fit.
    assert abs(a - step) <= 0.03 * step, (
        "the fitted pitch gradient is %.4f px/row but --pitch %d over %d rows "
        "asks for %.4f — the near row is not %d px of plank."
        % (a, s["pitch"], span, step, s["pitch"]))


def test_committed_override_carries_the_generated_band():
    """The ROM's art must BE the generator's art.

    The generator's parameters are edited far more often than the bake is re-run,
    and a stale band is invisible: the blob length does not move (the floor
    recycles its own slots), so neither the tile budget report nor the room gate
    can see it. tools/level_staleness.py catches an unbaked editor_bg_override
    .json; nothing caught an override that was never regenerated after the
    generator changed. This does.
    """
    px, rows, _, _ = shipped_band()
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
    test_drawn_seams_lie_on_a_pitch_linear_lattice()
    test_committed_override_carries_the_generated_band()
    test_scene_curve_band_matches_the_art_band()
    print("perspective floor: all three checks pass")
