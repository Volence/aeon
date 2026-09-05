#!/usr/bin/env python3
"""perspective_floor_gen — a PLACEHOLDER skewed wooden floor for the OJZ Plane-B map.

IT DREW A FAN UNTIL 2026-09-05. It now draws PARALLEL planks, all leaning one
way, because the owner chose that over a fan whose apex the 512-px wrap copies
off the side of the screen. The two sections after the next one are the whole
argument; the next one is the hardware background and is unchanged.

WHY THIS TOOL EXISTS, AND WHAT THE HARDWARE ACTUALLY ALLOWS
===========================================================
The owner asked for the Toy Story (Mega Drive) floor: wooden boards that FAN OUT
from a vanishing point — boards on the right leaning right at the bottom, boards
on the left leaning left, the centre board pointing straight down.

**The fan cannot be computed by the VDP, and the reason is measurable.** The
HScroll table this engine ships is 896 bytes (engine/system/buffers.emp:149) =
224 lines x 2 planes x 2 bytes: ONE horizontal scroll word per plane per
scanline. Whatever value a line carries shifts that line AS A WHOLE. So per-line
HScroll can only produce a SHEAR (every board leaning the same way), never a
fan, which needs the shift to vary ACROSS one line. Nothing on this hardware
varies a horizontal position within a scanline: VSRAM is per-two-cell-column but
it is a VERTICAL offset, and there is no scaling unit. The only two mechanisms
that put differing horizontal displacement inside one line are sprites (a floor
of them blows the sprite budget) and redrawing the nametable (8-px granularity,
a plane rewrite per frame).

So the splay lives in the ART. That is what this tool draws — and note that the
only thing the hardware CAN do to a whole line is exactly the uniform shear the
art is now drawn as, which is why the two now agree instead of fighting.

WHAT THE ENGINE CONTRIBUTES, AND WHY IT IS EXACTLY RIGHT
========================================================
The scene DSL's per-layer `curve` ramps Plane B's scroll factor LINEARLY across
the layer's screen span (engine/level/parallax.emp:1954-2044, re-derived in
tools/curve_probe.py:210-255):

    BG(y) = base + floor((y - top) * (end - base) / span)

Author `fb: FACTOR_0` at the layer top and `to: FACTOR_1` at its bottom and the
scroll rate becomes EXACTLY proportional to the distance below the layer top:

    rate(y) = camX * (y - horizon) / span

That is the perspective law. A board drawn as a straight line through the
vanishing point sits, at depth row dy, at

    x = vx + k * W * dy / H          (W = board pitch at the near row, H = span)

Translate row dy by delta * dy / H — which is precisely what the curve does —
and the boards land at

    x = vx + (k + delta/W) * W * dy / H

**the same fan, with the board index relabelled.** The vanishing point does not
move, the fan does not shear, and the pattern slides board-by-board exactly as a
real plank floor does when you walk sideways across it. The art's board pitch
and the curve's factor ramp are proportional to the same s(y), so they are
self-consistent. This is not an approximation that happens to look acceptable;
it is the correct construction for this hardware.

THE FAN IS GONE. THE OWNER CHOSE A UNIFORM SKEW INSTEAD (2026-09-05)
====================================================================
Everything above still describes the SCROLL, which is unchanged and correct. What
changed is the ART. A radial fan cannot live in a plane that wraps every 512 px,
and the reason is not a budget and not a bug — it is that periodicity copies the
apex:

    a drawn board is the locus |u| = j*p(dy), i.e. plane x = vx +- j*P*dy + 512m,
    so on screen it is the straight line  x = vx + dy*(+-jP - C) + 512m.

Every board is therefore a line through an apex at screen x = vx + 512m. ONE of
those apexes is on screen; the copies at vx +- 512 are not. The boards belonging
to an off-screen copy converge somewhere off the side of the screen — which is
exactly the owner's report: *"the first few are good then a few after get weird
and point away"*. Making the wrap period a divisor of the pitch would remove the
copies, but the pitch has to be proportional to dy (that is the whole scroll law
above) and 512/p(dy) is then a hyperbola, not an integer. Forcing it to an even
integer quantises the pitch, and MEASURED on this band that leaves only 6 distinct
periods over the 43 rows that draw seams, held for runs of up to 12 pixel rows. A
pitch held constant over a run of rows IS a run of vertical stripes — the exact
defect commit 5751123d removed. Fan + wrap + closure: pick two.

So the owner picked differently, and named the trade himself: *"we need it all
just skewed in one direction instead of trying to work around it having one part
point at us, so the art is consistent and the effect is consistent in what it's
doing."*

THE SHEAR, AND WHY IT CLOSES ON THE WRAP FOR FREE
=================================================
The planks are now PARALLEL. Plank centres sit at

    plane x = vx + j*PITCH + SKEW*dy          (j integer, PITCH divides 512)

so the whole band is one lattice of period PITCH, translated by SKEW px per pixel
row. Two consequences, both of them the point:

  * IT TILES BY TRANSLATION. `PITCH` divides 512 and 512/PITCH is EVEN (the
    plank-alternation parity has to survive the wrap too), so the pattern is
    exactly 512-periodic on every row with no fold, no mirror axis, no straddling
    plank and no apex to copy. `render_band` therefore has no `% 512` fold at
    all — the periodicity is a property of the lattice, not something recovered
    afterwards.
  * IT IS MUCH CHEAPER. The fan put every seam at a different sub-pixel offset on
    every row; a shear puts row r's pattern exactly SKEW*r px from row 0's, and
    the HV-flip of a diagonal stripe is the same stripe, so the band repeats
    along its own diagonal. MEASURED on this band: 39 unique tiles against the
    fan's 120, into 120 recycled slots, 0 appended, 81 slots left stranded.

WHAT THE SHEAR COSTS, STATED RATHER THAN DISCOVERED
===================================================
  1. THERE IS NO VANISHING POINT. Parallel planks converge nowhere; the apex at
     screen centre is gone. That is not a regression, it is the owner's choice —
     he asked for it in place of "having one part point at us".
  2. THE PLANK ANGLE ROTATES WITH THE CAMERA, and this is the one the owner has
     not seen yet. The band's scroll is C*dy px with C proportional to camera x,
     so the angle on screen is (SKEW - C) px per row. MEASURED off the engine's
     own ramp (tools/curve_probe.py, via the previewer's hscroll()):

         camera x      0     36     90    180    300    420    600
         C px/row  +0.000 +0.507 +1.254 +2.507 +4.169 +5.845 +8.338
         on screen +0.500 -0.007 -0.754 -2.007 -3.669 -5.345 -7.838

     so the planks lean right at camera 0, stand VERTICAL at camera x ~= 36, and
     lean progressively further left after that. Uniform at every instant —
     never two directions at once, which is the whole ask — but not a fixed
     angle, and by camera 420 they are steeper than anything the fan drew. This
     is inherent to "one plank angle in the art plus a depth-ramped scroll": the
     fan avoided it only by drawing every angle at once, which is exactly what
     produced the apex copies the owner rejected. If the rotation reads badly,
     the lever is the layer's `curve` end factor (a shallower ramp rotates
     slower and recedes less), NOT `--skew`, which only moves where the vertical
     crossing happens.
  3. PLANK WIDTH NO LONGER FORESHORTENS. Constant period is what buys exact
     closure. The recession is carried instead by the depth SHADE ramp — which
     the freed budget let us take from 0.9 ramp steps to 1.6 — by the seam
     contrast fading out toward the horizon (`--fade-rows`), and by the
     perspective-spaced CROSS seams (the plank ends, `--cross-seam-px`), which
     are horizontal and therefore both scroll-invariant and nearly free
     (measured: +7 tiles, and they were OFF under the fan because they did not
     fit).

WHERE THE TILES COME FROM (measured, not asserted)
==================================================
`games/sonic4/data/editor_bg_override.json` holds 320 unique tiles. The region
`bg_region` (games/sonic4/vram.toml) is 400 tiles with `band_reserve = 80`
withheld from the static importer, so 80 tiles are PHYSICALLY free but are
policy-reserved for BgAnim band art. (It was 448/128 until EFFECTS-W1 item 9d
moved the top 48 slots into the `waterline_strips` region; the reserve moved with
it in the same edit, so the static budget this tool measures against is unchanged
at 320 and the numbers below did not move.)

**This tool spends none of them.** Cell rows 48..63 of the plane (the ground-
level undergrowth) currently repeat rows 48..55 verbatim at 56..63, and 123 of
their tiles are referenced by NO other row. Overwriting that band therefore
RECYCLES its own slots. The tool reuses freed indices in place, keeps
`tiles[0:32]` (the BgAnim band's prefix, whose phase-0 art IS those slots)
byte-identical, and only appends past the current blob length if the floor
genuinely needs more than the band frees — which it reports loudly, because
appending is what spends the reserve.

Revert `games/sonic4/data/editor_bg_override.json` and re-run
`tools/regenerate-level.sh` to get the undergrowth back; this is a PLACEHOLDER.

USAGE
=====
    python3 tools/perspective_floor_gen.py --report      # measure, write nothing
    python3 tools/perspective_floor_gen.py --preview /tmp/floor.png
    python3 tools/perspective_floor_gen.py               # write the override
    python3 tools/inject_editor_bg.py                    # bake it
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bg_override_io import read_existing_override, atomic_write_json

# This tool authors layout + tiles and PASSES `anims` THROUGH UNCHANGED. It must
# own `anims` to be allowed to write the file at all (bg_override_io refuses on
# any unowned key), and owning it without touching it is the only safe shape: a
# band's phases[0] must stay byte-identical to tiles[slot_base:...], and this
# tool never writes below index 32.
OWNED_KEYS = ("layout", "tiles", "anims")

OVERRIDE = "games/sonic4/data/editor_bg_override.json"

PLANE_COLS = 64                 # cells; 512 px, the horizontal wrap period
PLANE_ROWS = 64                 # cells; Plane B is 64x64 for OJZ
PLANE_W = PLANE_COLS * 8        # 512
BG_TILE_CAPACITY = 400          # cross-checked against tools/vram_map.py below
                                # (448 -> 400 with EFFECTS-W1 item 9d: the top 48
                                #  slots are `waterline_strips`, and the reserve
                                #  went 128 -> 80 so the STATIC budget stayed 320)

# ── The wood ramp, straight out of the palette already in CRAM ────────────────
# games/sonic4/data/generated/ojz/act1/ojz_palette.bin source line 1 -> CRAM
# line 2, which 3804 of the map's 4096 cells already use. Darkest to lightest.
# No `palette` stamp: a stamp would recolour every FG object sharing the line.
PAL_LINE = 2
WOOD = (1, 3, 4, 5, 6, 7)       # #240000 #482424 #904824 #B46C24 #D89048 #FCB46C
SEAM = 1                        # the near-black warm — plank seams and shadow

# ── THE SHIPPED BAKE, in ONE place ────────────────────────────────────────────
# `main()`'s CLI defaults ARE these values, and tools/perspective_floor_predict.py
# imports this dict instead of restating them. It restated them until 2026-09-05
# and drifted: it was still rendering `lod_px=20, shade 3.2/2.7, sym=2` — a
# picture the ROM had not carried since the parameters last moved. A previewer
# that shows different art from the bake is worse than no previewer, because it
# is believed.
#
# WHY EVERY NUMBER HERE MOVED WITH THE SHEAR (2026-09-05). The band has to fit
# the 121 slots its own rows recycle, or it appends past the 320 static budget
# games/sonic4/vram.toml declares and spends the BgAnim reserve — which is the
# owner's number, not this tool's. The radial fan cost 120 of the 121 and that
# ceiling is what had forced `lod_px` to 26 and flattened the depth ramp to 0.9
# steps. A shear repeats along its own diagonal, so the same picture costs far
# less: MEASURED on this band, 39 tiles with the cross seams ON, against the
# fan's 120. The 81 slots that bought back are spent on the recession cues the
# constant plank width no longer provides — a 1.6-step depth ramp (against 0.9),
# a seam contrast that fades out over the 24 rows below the horizon, and
# perspective-spaced cross seams, which were OFF under the fan because they did
# not fit. `crown` is DOWN to 0.0 and that is a look call, not a budget one: at
# 0.45 it costs +24 tiles (63 total, still inside the 120) but the highlight
# crosses a wood-ramp rounding step part-way down each plank and renders as pale
# notches rather than a continuous crown. The knob stays for when the palette or
# the ramp makes it land cleanly.
#
# `lod_px` is GONE, not renamed: it thresholded on the per-row board pitch, and
# under the shear there is no per-row pitch to threshold on. `fade_rows` is the
# replacement cue and it is indexed on the depth row directly.
SHIPPED = dict(row0=48, row1=63, pitch=64, vp_col=20, skew=0.5,
               horizon_row=55, shade_near=3.8, shade_far=2.2, cross_seam_px=14.0,
               cross_near_frac=0.9, fade_rows=24.0, crown=0.0)


def plank_lattice(pitch):
    """Validate the plank period against the 512-px wrap, and return 512/pitch.

    THE ONE CONSTRAINT THE SHEAR HAS, AND THE WHOLE REASON IT CLOSES. Plane B
    wraps horizontally every 512 px (parallax.emp: PLANE_B_SPAN). A lattice of
    period `pitch`, translated by `skew` px per row, is exactly 512-periodic on
    every row if and only if 512 is a whole number of periods — and the plank
    ALTERNATION (neighbouring planks take different wood tones) is 512-periodic
    only if that whole number is EVEN, since crossing the wrap advances the plank
    index by 512/pitch and the tone is its parity.

    Get either wrong and the wrap becomes a seam again: an odd count flips the
    tone across x = 0, a non-divisor leaves a straddling plank of the wrong width.
    Both are exactly the artefacts the fan had, so they are asserted, not hoped.

    WHY THIS IS NOT THE QUANTISATION THAT KILLED THE FAN. The fan needed the
    period to be proportional to the depth row AND to divide 512 at every row,
    which is a hyperbola forced onto a discrete set — measured, 6 distinct periods
    over 43 rows, held for runs of up to 12 pixel rows, i.e. vertical stripes. The
    shear needs ONE period to divide 512, once, for the whole band. There is
    nothing left to quantise.
    """
    assert pitch > 0 and PLANE_W % pitch == 0, (
        "plank pitch %r does not divide the %d-px plane wrap: the pattern would "
        "not tile by translation and the wrap would carry a straddling plank"
        % (pitch, PLANE_W))
    n = PLANE_W // pitch
    assert n % 2 == 0, (
        "%d planks across the %d-px wrap is ODD: the plank tone alternation has "
        "period 2, so it would flip across the wrap and put a same-tone pair at "
        "plane x 0" % (n, PLANE_W))
    return n


def shade(level):
    """Clamp a float brightness onto the six-step wood ramp."""
    i = int(round(level))
    return WOOD[max(0, min(len(WOOD) - 1, i))]


def render_band(rows, pitch, vp_col, skew, horizon_row, shade_near, shade_far,
                crown, fade_rows, cross_seam_px, cross_near_frac):
    """Rasterise the floor into a (rows*8) x 512 array of palette indices.

    `horizon_row` is the CELL ROW where the floor meets the wall. Rows above it
    are the shadowed wall behind the floor — a pure vertical gradient, which is
    both the right picture (the jungle floor in shade, meeting the boards at a
    hard line) and nearly free: a gradient row is one tile wide-flipped, so the
    whole upper half costs single digits. Rows at and below it carry the planks.

    THE PLANKS ARE PARALLEL. Centres at plane x = vx + j*pitch + skew*dy, one
    lattice for the whole band, translated `skew` px per pixel row. There is no
    fold and no `% 512` anywhere below: `pitch` divides 512 an even number of
    times (plank_lattice() asserts it), so the lattice is already exactly
    512-periodic on every row. See the module header for why the fan it replaced
    could not be, and for what parallel planks cost.

    Returns a list of pixel rows, each a list of 512 ints in 1..15.
    """
    top_row = rows[0]
    horizon = top_row if horizon_row is None else horizon_row
    shade_px = (horizon - top_row) * 8    # pixel rows above the floor's top edge
    span = len(rows) * 8 - shade_px       # the floor's own height in pixels
    plank_lattice(pitch)                  # the closure precondition, asserted
    # The lattice PHASE, in plane pixels. Under the fan this was the vanishing
    # point and the half-pixel was load-bearing (it put the mirror axis between
    # cells). There is no mirror any more, so the half-pixel is now only a
    # phase choice: it centres a plank on the cell boundary rather than a seam,
    # which is what keeps the seam off the cell edges where it would cost a
    # tile for a single dark column.
    vx = vp_col * 8 - 0.5
    out = []
    # `dy` is BOTH the art's depth index and the engine's per-line ramp index,
    # and they have to be the same number (test_scene_curve_band_matches_the_art
    # _band checks the two windows agree). The band's first pixel row is dy 0,
    # where the engine's ramp is 0.
    # The shadowed wall above the horizon: darkest at the join with the jungle,
    # lifting slightly toward the horizon line so the two do not merge.
    for sy in range(shade_px):
        lvl = 0.15 + 0.9 * (sy / max(1, shade_px - 1))
        out.append([shade(lvl)] * PLANE_W)

    for dy in range(span):
        t = dy / max(1, span - 1)         # 0 at the horizon, 1 at the near row

        # Depth shading, and now the PRIMARY recession cue: the plank width no
        # longer foreshortens, so this ramp and the cross seams below are what
        # say "this recedes". Under the fan it had to stay inside 0.9 ramp steps
        # to fit the tile budget; the shear's dedup bought that back and it runs
        # at 1.6 here.
        #
        # STILL DELIBERATELY SHORT OF THE FULL RAMP. A steep ramp (0.6 -> 4.2
        # was the first try) crosses four of the six wood steps, and because the
        # plank alternation rides on top of it, neighbouring planks cross each
        # step at DIFFERENT rows — so the floor reads as a flight of stairs
        # rather than a plane. Under the shear the tile count barely notices the
        # ramp at all (0.9 steps -> 40 tiles, 1.6 -> 39, 2.8 -> 40), so 1.6 is
        # chosen on the PICTURE: it is the deepest ramp that still crosses only
        # one wood step inside a plank.
        base = shade_near + (shade_far - shade_near) * (1.0 - t)

        # Seam contrast fades OUT toward the horizon. Under the fan this was
        # `lod_px`, a threshold on the per-row board pitch; a shear has no
        # per-row pitch, so the cue is indexed on the depth row directly. It is
        # doing the same two jobs: it keeps the far rows from becoming a hard
        # grid where a real floor would blur, and it is most of why the top of
        # the band dedups to a handful of tiles.
        detail = min(1.0, dy / float(fade_rows)) if fade_rows > 0 else 1.0

        # A perspective-spaced cross seam (the plank ENDS): constant-depth lines
        # sit at dy = cross_near_frac * span / m. Horizontal lines are invariant
        # under horizontal scroll, so these cost nothing under motion and stay
        # put — and with the plank width no longer receding they are the only
        # thing in the art that measures depth. `cross_near_frac` pulls the
        # nearest row of ends up off the band's bottom edge; at 1.0 the m=1 line
        # lands below the last row and the whole near half has no ends at all.
        cross = False
        if cross_seam_px > 0:
            for m in range(1, 64):
                d = cross_near_frac * span / m
                if d < cross_seam_px:       # stop before the ends alias into a grid
                    break
                if int(round(d)) == dy:
                    cross = True
                    break

        line = []
        for x in range(PLANE_W):
            # The lattice. `q` is the plank index as a real number; the sheared
            # term is what leans every plank the same way. No fold: q advances by
            # exactly PLANE_W/pitch (an even integer) across the wrap, so both
            # `frac` and the tone parity come back to themselves at x = 512.
            q = (x - vx - skew * dy) / float(pitch)
            j = int(math.floor(q + 0.5))
            frac = abs(q - j)             # 0 at a plank centre, 0.5 at a seam

            level = base
            # Alternating plank tones, on the parity of the plank index. Unlike
            # the fan's `abs(j)` this is the SIGNED index, which is what makes
            # the pattern even nowhere — a fan is mirror-symmetric about its
            # apex and that symmetry is precisely what the owner rejected.
            level += 0.6 if (j & 1) else -0.6

            if detail > 0.0:
                seam_w = 0.5 - (0.9 / pitch)     # ~0.9 px of seam, in plank units
                if frac > seam_w:
                    # the seam itself
                    level -= 2.4 * detail
                elif frac < 0.10 and crown > 0.0:
                    # A soft highlight along the plank's crown. Under the fan
                    # this was the band's most expensive feature (every row put
                    # it at a different sub-pixel offset, +19 tiles for 0.55).
                    # Under the shear every row's crown is the previous row's
                    # translated by `skew`, so it costs +24 tiles rather than
                    # being unaffordable — but it is SHIPPED AT 0.0 anyway,
                    # because the highlight crosses a wood-ramp rounding step
                    # part-way down each plank and reads as pale notches. Budget
                    # is no longer what decides this knob; the picture is.
                    level += crown * detail
            if cross:
                level -= 1.6

            # A hard shadow line right under the horizon. Two pixel rows, so it
            # costs almost nothing, and it is what stops the far planks bleeding
            # into the wall above and turning the join into mush.
            if dy < 2:
                level -= (2 - dy) * 0.9

            line.append(shade(level))
        out.append(line)
    return out


def shipped_band():
    """The band exactly as the bake draws it, from SHIPPED and nothing else.

    THE SINGLE ENTRY POINT, and it exists because a previewer that restates the
    bake's parameters drifts off it silently. tools/perspective_floor_predict.py
    did exactly that until 2026-09-05 and spent weeks rendering a picture the ROM
    had not carried. Everything that wants "the floor as it ships" — the
    previewer, the gate, this tool's own main() — calls THIS, so a parameter can
    only be changed in one place. Returns (pixels, rows, shade_px, span).
    """
    s = SHIPPED
    rows = list(range(s["row0"], s["row1"] + 1))
    kw = {k: v for k, v in s.items() if k not in ("row0", "row1")}
    px = render_band(rows, **kw)
    shade_px = (s["horizon_row"] - s["row0"]) * 8
    return px, rows, shade_px, len(rows) * 8 - shade_px


def canon(tile):
    """Flip-canonical key for an 8x8 tile plus the flag that reproduces it."""
    def flip_h(t):
        return [t[r * 8 + (7 - c)] for r in range(8) for c in range(8)]

    def flip_v(t):
        return [t[(7 - r) * 8 + c] for r in range(8) for c in range(8)]

    cands = {
        "": tuple(tile),
        "H": tuple(flip_h(tile)),
        "V": tuple(flip_v(tile)),
        "HV": tuple(flip_h(flip_v(tile))),
    }
    key = min(cands.values())
    for flag, v in cands.items():
        if v == key:
            return key, flag
    raise AssertionError("unreachable")


def word(pal_line, flag, idx):
    w = (pal_line & 3) << 13
    if "V" in flag:
        w |= 1 << 12
    if "H" in flag:
        w |= 1 << 11
    w |= idx & 0x7FF
    assert w != 0, ("layout word 0 is passed through inject_editor_bg.py "
                    "UNCHANGED (no +BG_TILE_BASE_SLOT) and would address VRAM "
                    "tile 0, inside fg_art_pool")
    return w


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--override", default=OVERRIDE)
    ap.add_argument("--out", default=None, help="default: rewrite --override in place")
    ap.add_argument("--row0", type=int, default=SHIPPED["row0"],
                    help="first cell row of the floor")
    ap.add_argument("--row1", type=int, default=SHIPPED["row1"],
                    help="last cell row (inclusive)")
    ap.add_argument("--pitch", type=int, default=SHIPPED["pitch"],
                    help="plank period in plane px, the SAME at every depth row. "
                         "MUST divide 512 an even number of times or the pattern "
                         "stops tiling the wrap by translation — see "
                         "plank_lattice()")
    ap.add_argument("--skew", type=float, default=SHIPPED["skew"],
                    help="plane px the whole lattice slides per pixel row: the "
                         "plank lean, and the ONLY thing that leans them. Every "
                         "plank takes the same value, which is the point — a "
                         "per-plank lean is a fan, and a fan in a wrapping plane "
                         "copies its apex every 512 px")
    ap.add_argument("--vp-col", type=int, default=SHIPPED["vp_col"],
                    help="lattice phase, in cell columns. There is no vanishing "
                         "point any more; this only chooses which plane x a "
                         "plank is centred on, and 20 keeps the seams off the "
                         "cell boundaries")
    ap.add_argument("--fade-rows", type=float, default=SHIPPED["fade_rows"],
                    help="depth rows over which the seam contrast fades in below "
                         "the horizon; 0 = full contrast everywhere. Replaces "
                         "the fan's --lod-px, which thresholded on a per-row "
                         "pitch the shear does not have")
    ap.add_argument("--cross-near-frac", type=float,
                    default=SHIPPED["cross_near_frac"],
                    help="depth fraction of the NEAREST row of plank ends; 1.0 "
                         "puts it below the band and leaves the near half with "
                         "no ends at all")
    ap.add_argument("--horizon-row", type=int, default=SHIPPED["horizon_row"],
                    help="cell row where the floor meets the wall; rows above it "
                         "are the shadowed wall behind the floor")
    ap.add_argument("--shade-near", type=float, default=SHIPPED["shade_near"],
                    help="wood-ramp level at the near (bottom) row, 0..5")
    ap.add_argument("--shade-far", type=float, default=SHIPPED["shade_far"],
                    help="wood-ramp level at the horizon, 0..5")
    ap.add_argument("--crown", type=float, default=SHIPPED["crown"],
                    help="highlight along each board's crown, 0 = none. The most "
                         "expensive feature per unit of picture — see render_band")
    ap.add_argument("--cross-seam-px", type=float, default=SHIPPED["cross_seam_px"],
                    help="plank-end spacing below which cross seams stop; 0 = none")
    ap.add_argument("--preview", default=None, help="write a PNG of the whole plane")
    ap.add_argument("--report", action="store_true", help="measure only, write nothing")
    args = ap.parse_args()

    # One authority for the capacity, not a restated literal.
    from vram_map import (GAME as _G, BG_TILE_CAPACITY as CAP,
                          BG_BAND_RESERVE as RESERVE,
                          BG_STATIC_TILE_BUDGET as STATIC_BUDGET)
    assert _G == "sonic4", f"tools/vram_map.py was generated for {_G!r}"
    assert CAP == BG_TILE_CAPACITY, (
        f"BG_TILE_CAPACITY moved to {CAP}; this tool's mirror says "
        f"{BG_TILE_CAPACITY}")

    data = read_existing_override(args.override, OWNED_KEYS, "perspective_floor_gen")
    if not data:
        sys.exit(f"ERROR: {args.override} is empty or missing — nothing to build on.")
    layout = list(data["layout"])
    tiles = [list(t) for t in data["tiles"]]
    if len(layout) != PLANE_COLS * PLANE_ROWS:
        sys.exit(f"ERROR: layout is {len(layout)} words, expected "
                 f"{PLANE_COLS * PLANE_ROWS} (64x64)")

    rows = list(range(args.row0, args.row1 + 1))
    if not rows or args.row0 < 0 or args.row1 >= PLANE_ROWS:
        sys.exit(f"ERROR: rows {args.row0}..{args.row1} outside 0..{PLANE_ROWS - 1}")

    # ── Which slots does this band own exclusively? Those are recyclable. ─────
    band_cells = {r * PLANE_COLS + c for r in rows for c in range(PLANE_COLS)}
    used_rows = {}
    for i, w in enumerate(layout):
        used_rows.setdefault(w & 0x7FF, set()).add(i // PLANE_COLS)
    band_rows = set(rows)
    recyclable = sorted(t for t in {layout[i] & 0x7FF for i in band_cells}
                        if used_rows[t] <= band_rows)
    # Never recycle a BgAnim band slot: phases[0] must stay == tiles[0:n].
    anim_slots = 0
    for a in data.get("anims", []):
        anim_slots += a["cols"] * a["rows"]
    recyclable = [t for t in recyclable if t >= anim_slots]

    # ── Rasterise ────────────────────────────────────────────────────────────
    px = render_band(rows, pitch=args.pitch, vp_col=args.vp_col,
                     skew=args.skew, horizon_row=args.horizon_row,
                     shade_near=args.shade_near, shade_far=args.shade_far,
                     crown=args.crown, fade_rows=args.fade_rows,
                     cross_seam_px=args.cross_seam_px,
                     cross_near_frac=args.cross_near_frac)

    # ── Cut into tiles, dedup flip-canonically against the WHOLE blob ─────────
    existing = {}
    for i, t in enumerate(tiles):
        k, _ = canon(t)
        existing.setdefault(k, i)
    # A recyclable slot's old content must not be matched against — it is about
    # to be overwritten. Drop those keys unless another row still uses them.
    for t in recyclable:
        k, _ = canon(tiles[t])
        if existing.get(k) == t:
            del existing[k]

    new_keys = {}                   # canonical key -> tile pixels
    plan = []                       # (cell_index, canonical key, flip flag)
    for ri, r in enumerate(rows):
        for c in range(PLANE_COLS):
            tile = [px[ri * 8 + y][c * 8 + x] for y in range(8) for x in range(8)]
            k, flag = canon(tile)
            new_keys.setdefault(k, list(k))
            plan.append((r * PLANE_COLS + c, k, flag))

    fresh = [k for k in new_keys if k not in existing]
    reused_existing = len(new_keys) - len(fresh)

    # ── Assign indices: recycled slots first, then append ─────────────────────
    assign = dict(existing)
    spare = list(recyclable)
    appended = 0
    for k in fresh:
        if spare:
            idx = spare.pop(0)
            tiles[idx] = list(k)
        else:
            idx = len(tiles)
            tiles.append(list(k))
            appended += 1
        assign[k] = idx

    for cell, k, flag in plan:
        layout[cell] = word(PAL_LINE, flag, assign[k])

    # Slots the band freed and the floor did not need. They stay in the blob as
    # dead weight (pruning them would renumber every layout word and break the
    # BgAnim prefix), so they are reported rather than reclaimed.
    stranded = len(spare)

    # ── Report ───────────────────────────────────────────────────────────────
    before = len(data["tiles"])
    after = len(tiles)
    print(f"perspective floor: plane rows {args.row0}..{args.row1} "
          f"({len(rows) * 8} px), plank period {args.pitch} px "
          f"({PLANE_W // args.pitch} across the wrap), skew {args.skew} px/row")
    print(f"  unique tiles the floor needs      : {len(new_keys)}")
    print(f"    of which matched existing art   : {reused_existing}")
    print(f"    of which written into recycled  : {len(fresh) - appended}")
    print(f"    of which APPENDED (new tiles)   : {appended}")
    print(f"  slots the band freed              : {len(recyclable)}")
    print(f"  freed slots left stranded         : {stranded}")
    print(f"  blob length  {before} -> {after}   (capacity {CAP}, "
          f"static budget {STATIC_BUDGET}, band reserve {RESERVE})")
    if args.preview:
        write_preview(layout, tiles, args.preview)
        print(f"  preview -> {args.preview}")

    if after > CAP:
        msg = (f"{after} tiles exceeds BG_TILE_CAPACITY {CAP} — "
               "inject_editor_bg.py would abort. Shrink the detailed band "
               "(--detail-rows), raise --lod-px, or coarsen --pitch.")
        if args.report:
            print(f"  OVER BUDGET: {msg}")
            print("  --report: nothing written")
            return
        sys.exit(f"ERROR: {msg}")
    if not appended:
        print("  ** zero net tiles: the floor fits entirely in the slots its "
              "own band freed. band_reserve is untouched. **")
    elif after > STATIC_BUDGET:
        print(f"  ** OVER THE DECLARED STATIC BUDGET: {after} tiles against "
              f"{STATIC_BUDGET}. Nothing in the bake enforces this — "
              f"inject_editor_bg.py gates on BG_TILE_CAPACITY ({CAP}) only — so "
              f"the blob would ship with games/sonic4/vram.toml's contract "
              f"silently wrong. Lower bg_region's band_reserve to "
              f"{CAP - after} and re-run tools/gen_vram_map.py. **")
    else:
        print(f"  ** {appended} appended tile(s), inside the declared static "
              f"budget of {STATIC_BUDGET} with {STATIC_BUDGET - after} to "
              f"spare. band_reserve stands at {RESERVE}; that is what a future "
              f"BgAnim band has left. **")

    if args.report:
        print("  --report: nothing written")
        return

    data["layout"] = layout
    data["tiles"] = tiles
    dest = args.out or args.override
    atomic_write_json(dest, data)
    print(f"  wrote {dest}")
    print("  next: python3 tools/inject_editor_bg.py && ./build.sh")


def write_preview(layout, tiles, path):
    """Render the whole 512x512 plane through the OJZ palette, for eyeballing."""
    import struct
    from PIL import Image
    pal_path = "games/sonic4/data/generated/ojz/act1/ojz_palette.bin"
    pal = struct.unpack(">48H", open(pal_path, "rb").read())

    def rgb(w):
        return (((w >> 1) & 7) * 36, ((w >> 5) & 7) * 36, ((w >> 9) & 7) * 36)

    img = Image.new("RGB", (PLANE_W, PLANE_ROWS * 8))
    p = img.load()
    for cy in range(PLANE_ROWS):
        for cx in range(PLANE_COLS):
            w = layout[cy * PLANE_COLS + cx]
            t = tiles[w & 0x7FF]
            hf, vf = (w >> 11) & 1, (w >> 12) & 1
            line = ((w >> 13) & 3) - 1
            for y in range(8):
                sy = 7 - y if vf else y
                for x in range(8):
                    sx = 7 - x if hf else x
                    p[cx * 8 + x, cy * 8 + y] = rgb(pal[line * 16 + t[sy * 8 + sx]])
    img.save(path)


if __name__ == "__main__":
    main()
