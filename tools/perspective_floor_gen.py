#!/usr/bin/env python3
"""perspective_floor_gen — a PLACEHOLDER pseudo-3D wooden floor for the OJZ Plane-B map.

IT IS A FAN AGAIN AS OF 2026-09-05, and the parallel planks that stood here for
part of that day are gone. The owner's words that put them here were read too
literally, and his correction is the specification this file now implements:

    "it has the correct floor but not the correct effect, the effect should make
     it so when one of the beams of the floor at the top hits the center, the
     bottom should hit the center. the other had that effect a little, this just
     consistently skews and continues to do so"

So: a VANISHING POINT PINNED TO THE SCREEN CENTRE COLUMN, at every camera x.
Beams left of it lean left, beams right of it lean right, and the beam through
it is vertical. Parallel planks cannot do that and were never going to — see
"WHAT THE SHEAR COST" below, which is kept because it is the argument for not
going back.

WHY THIS TOOL EXISTS, AND WHAT THE HARDWARE ACTUALLY ALLOWS
===========================================================
The HScroll table this engine ships is 896 bytes (engine/system/buffers.emp:149)
= 224 lines x 2 planes x 2 bytes: ONE horizontal scroll word per plane per
scanline. Whatever value a line carries shifts that line AS A WHOLE. So per-line
HScroll can only produce a SHEAR, never a fan, which needs the shift to vary
ACROSS one line. Nothing on this hardware varies horizontal position within a
scanline: VSRAM is per-two-cell-column but it is a VERTICAL offset, and there is
no scaling unit.

So the splay lives in the ART, and the scroll's only job is to be CONSISTENT
with it. That consistency is the whole design and it has one equation.

THE ONE EQUATION
================
The scene DSL's per-layer `curve` ramps Plane B's scroll factor linearly across
the layer's screen span (engine/level/parallax.emp:1954-2044, re-derived in
tools/curve_probe.py:210-255). Author `fb: FACTOR_0` at the layer top and
`curve: To(F)` at its bottom and the plane offset at depth row dy becomes

    S(dy) = camX * F * dy / span                                            (1)

Draw the art's beams at plane x = vx + j*P*dy (period PROPORTIONAL to dy) and
the composited beam lands at

    screen x = vx + dy * (j*P - camX*F/span)                                (2)

which is a straight line through (vx, dy=0) for EVERY j and EVERY camX. That is
the vanishing point, it sits on the art's column vx, and it does not move when
the camera does — the beams merely relabel, which is exactly how a real plank
floor behaves when you walk across it. `vp_col = 20` puts vx at plane 159.5,
i.e. screen column 159.5 of a 320-px screen: the centre column the owner asked
for.

The art's period and the scroll's factor are the SAME function of dy — both
linear, both zero at the horizon row. That is the "f(r)" identity: get them out
of step and the floor shears, which is the defect this file was built to fix
twice now.

THE WRAP IS THE REAL CONSTRAINT, AND IT IS A CAMERA-TRAVEL BUDGET
=================================================================
Plane B wraps every 512 px; the screen is 320. So the plane has 192 px of SLACK,
and the floor's near row consumes it at rate camX*F. While S(dy) <= 192 the
window [S, S+320) lies inside one copy of the drawn fan and every beam on screen
belongs to the apex at screen 159.5. Past that, the right of the screen shows
plane x near 0 through the wrap, and those beams belong to the NEXT copy of the
fan, whose apex is at screen 159.5 + 512 = 671.5. They lean hard right and
converge off the side. That is the owner's report, exactly:

    "the first few are good then a few after get weird and point away"

MEASURED (tools/perspective_floor_gen.py's own art, composited through
curve_probe's transcription of the engine ramp; every adjacent-row seam pair
votes for an apex column, and a vote more than 60 px off 159.5 is a beam
pointing somewhere else). Baseline noise is 8-20% -- seams 20-32 px apart moving
up to 5 px/row mis-match occasionally:

    curve To(...)   camX  0    90   180   300   420   600   900  1400
    FACTOR_1              8%   17%   21%   35%   62%   97%   99%  100%
    FACTOR_1_2            8%   20%   17%   12%   13%   35%   69%  100%
    FACTOR_1_4            8%   18%   20%   10%   17%   12%   14%   43%
    FACTOR_1_8            8%   11%   18%   21%   18%   10%   15%   19%

The onset is at camX = 192/F px, and the table lands on it: 195, 389, 778, 1557.
THE SHIPPED SCENE AUTHORS `To(FACTOR_1_4)` and is therefore clean out to camera
x ~778. This is a TRADE THE OWNER SHOULD SEE: the floor's near row now scrolls
at a quarter of the camera rate instead of the full rate. It is one identifier
in games/sonic4/data/effects/ojz_scenes.emp and moving it up or down trades
scroll rate against clean travel along that table.

WHY THERE IS NO SETTING THAT IS CLEAN AT EVERY CAMERA X
=======================================================
A finite wrapping plane holds a PERIODIC texture; a fan is not periodic. Two
escapes were measured and both are refused:

  * MAKE THE PERIOD DIVIDE THE WRAP AT EVERY ROW (period 512/n, n integer). This
    does tile exactly -- no straddling beam, no copies, at any camera x. But it
    breaks (1): a wrap-exact period is a STAIRCASE in dy while the engine's ramp
    is linear, so the composited lattice phase scatters. MEASURED, peak-to-peak
    over the seam rows, in periods (0 = a perfect fan, 0.5 = rows half a beam
    out of step): camX 0 -> 0.00, 180 -> 0.30, 420 -> 0.65, 900 -> 0.89, against
    0.00/0.12/0.18/0.12 for the linear period under the same integer HScroll.
    The centre beam's worst row-to-row jump goes 0.1 px -> 4.8 px at camX 420.
    It trades a defect that arrives at camX 195 for one that arrives at 90.
    NOTE FOR ANYONE RE-DERIVING THIS: the docs that stood here before measured
    the quantisation by forcing the PERIOD to an even integer and reported a
    nine-step staircase, ratio 0.887..1.092. That constraint is not the tiling
    constraint -- 18 px is an even integer and does not divide 512. The real
    constraint is on the BEAM COUNT, and 512/n with n integer is a much finer
    grid. It is still not fine enough, but for the reason above, not that one.
  * MAKE THE ENGINE'S PER-ROW GAIN FOLLOW THE STAIRCASE. That closes (1) exactly
    and would be clean at every camera x. It needs a per-row scroll factor the
    parallax band vocabulary cannot express (band factors are <=2 shift terms,
    so the achievable set is 2^-a +- 2^-b; making 512/n(dy) proportional to one
    of those forces n to powers of two, i.e. a four-step fan). It is ENGINE
    work, outside this tool.

WHAT THE SHEAR COST, KEPT SO IT IS NOT RE-PROPOSED
==================================================
Parallel planks (period constant, one lean) tile the wrap by pure translation
and cost only 39 tiles, and they are what shipped for part of 2026-09-05. They
have no vanishing point at all, and worse, the on-screen plank angle is
`skew - camX*F/span`: it ROTATES with the camera, measured from +0.5 px/row at
camX 0 through vertical at camX ~36 to -5.3 px/row at camX 420. That is the
"consistently skews and continues to do so" the owner rejected. The fan's angles
are camera-INVARIANT; only which beam is vertical changes.

WHERE THE TILES COME FROM (measured, not asserted)
==================================================
`games/sonic4/data/editor_bg_override.json` holds 320 unique tiles against
`bg_region`'s 400 (games/sonic4/vram.toml) with `band_reserve = 80` withheld for
BgAnim band art, i.e. a 320-tile static budget.

**This tool spends none of it.** Cell rows 48..63 of the plane were originally a
verbatim repeat of rows 48..55, and the slots only those rows referenced are
recycled in place. Since 2026-09-05 the recycler ALSO reclaims slots that no
layout cell references at all -- a previous bake of this band stranded 84 of
them, and without this they would have been lost to every later bake, silently
shrinking the budget from 123 to 39. `tiles[0:32]` (the BgAnim band's phase-0
prefix) is never touched, and anything past the current blob length is reported
loudly, because appending is what spends the reserve.

THE SHIPPED FAN COSTS 121 OF THE 123 RECLAIMABLE SLOTS. It is at the ceiling,
and that ceiling is what sets `lod_px`: the tile count is driven almost entirely
by HOW MANY ROWS DRAW SEAMS, because every row's period differs so no two rows
share a tile. Measured, at pitch 32 with the tone alternation and cross seams
on: lod 10 -> 247 tiles / 49 seam rows, lod 12 -> 240/45, lod 14 -> 204/40,
lod 16 -> 176/36, lod 20 -> 121/27. Flattening the depth shade ramp buys almost
nothing (3.6/2.4 -> 3.2/3.2 moves 121 to 122). So the fan is drawn on the
nearest 27 of the floor's 72 rows and the rest is graded floor. Raising it needs
`band_reserve` to come down, which is the OWNER'S number, not this tool's.

Revert `games/sonic4/data/editor_bg_override.json` and re-run
`tools/regenerate-level.sh` to get the original undergrowth back; this is a
PLACEHOLDER.

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
SCREEN_W = 320                  # the window the wrap has to hold, with 192 spare
BG_TILE_CAPACITY = 400          # cross-checked against tools/vram_map.py below

# ── The wood ramp, straight out of the palette already in CRAM ────────────────
# games/sonic4/data/generated/ojz/act1/ojz_palette.bin source line 1 -> CRAM
# line 2, which 3804 of the map's 4096 cells already use. Darkest to lightest.
PAL_LINE = 2
WOOD = (1, 3, 4, 5, 6, 7)       # #240000 #482424 #904824 #B46C24 #D89048 #FCB46C
SEAM = 1                        # the near-black warm — beam seams and shadow

# ── THE SHIPPED BAKE, in ONE place ────────────────────────────────────────────
# `main()`'s CLI defaults ARE these values, and tools/perspective_floor_predict.py
# imports this dict instead of restating them. It restated them until 2026-09-05
# and drifted, rendering a picture the ROM had not carried for weeks.
#
# `near_pitch` 32 and `lod_px` 20 are the TILE CEILING talking, not taste: see
# the module header's measured lod/tile/seam-row table. `near_pitch` also has to
# be coarse enough that the beams are further apart than the seam is wide at the
# nearest row that draws one (period 20 px, seam ~1.8 px).
SHIPPED = dict(row0=48, row1=63, near_pitch=32.0, vp_col=20, horizon_row=55,
               shade_near=3.6, shade_far=2.4, lod_px=20.0, lod_fade=6.0,
               seam_px=0.9, cross_seam_px=14.0, cross_near_frac=0.9, crown=0.0)

# The camera-travel budget the 512-px wrap allows, as a function of the scene's
# curve end factor. Derived, not fitted: the window is SCREEN_W wide inside a
# PLANE_W wrap, so the near row may slide PLANE_W - SCREEN_W px before the next
# copy of the fan reaches the screen edge, and it slides at camX * F.
WRAP_SLACK_PX = PLANE_W - SCREEN_W        # 192


def clean_camera_range(end_factor):
    """Camera x at which the wrap's next apex first reaches the screen."""
    assert 0 < end_factor <= 1
    return WRAP_SLACK_PX / float(end_factor)


def beam_period(dy, span, near_pitch):
    """The drawn beam period at depth row dy: PROPORTIONAL TO dy, and that
    proportionality IS the perspective law.

    dy is measured from the horizon row, where it is 0 and the beams meet. The
    engine's curve ramps its scroll factor over the same window from the same
    zero (test_scene_curve_band_matches_the_art_band checks the two windows
    agree, to the row). Because both are linear in dy with a zero at the same
    place, their RATIO is constant, and a constant ratio is precisely the
    statement that the composited beams are straight lines through a fixed
    vanishing point — see the module header's equation (2).

    Anything else here — a snapped period, a staircase, a floor on the period —
    breaks that ratio and the floor shears. Two different snappings have been
    tried and measured; both are in the header.
    """
    return near_pitch * dy / float(span - 1)


def shade(level):
    """Clamp a float brightness onto the six-step wood ramp."""
    i = int(round(level))
    return WOOD[max(0, min(len(WOOD) - 1, i))]


def render_band(rows, near_pitch, vp_col, horizon_row, shade_near, shade_far,
                lod_px, lod_fade, seam_px, cross_seam_px, cross_near_frac,
                crown):
    """Rasterise the floor into a (rows*8) x 512 array of palette indices.

    `horizon_row` is the CELL ROW where the floor meets the wall, and it is the
    fan's apex row. Rows above it are the shadowed wall behind the floor — a
    pure vertical gradient, which is both the right picture and nearly free (a
    gradient row is one tile wide-flipped). Rows at and below it carry the fan.

    THE BEAMS ARE A FAN. Centres at plane x = vx + j*period(dy), with period
    proportional to dy, so every beam is a straight line through the apex at
    plane x = vx — and stays one under the engine's scroll, which translates row
    dy by an amount also proportional to dy.

    There is no fold and no `% 512` anywhere below. The plane simply carries one
    copy of the fan and the wrap is a camera-travel budget, not a rasteriser
    concern — see the module header.

    Returns a list of pixel rows, each a list of 512 ints in 1..15.
    """
    top_row = rows[0]
    horizon = top_row if horizon_row is None else horizon_row
    shade_px = (horizon - top_row) * 8    # pixel rows above the floor's top edge
    span = len(rows) * 8 - shade_px       # the floor's own height in pixels
    # The apex column, in plane pixels. The half-pixel puts the apex between two
    # pixel centres, so the fan is symmetric about it rather than sitting a
    # half-beam to one side.
    vx = vp_col * 8 - 0.5
    out = []
    # The shadowed wall above the horizon: darkest at the join with the jungle,
    # lifting slightly toward the horizon line so the two do not merge.
    for sy in range(shade_px):
        lvl = 0.15 + 0.9 * (sy / max(1, shade_px - 1))
        out.append([shade(lvl)] * PLANE_W)

    for dy in range(span):
        t = dy / max(1, span - 1)         # 0 at the horizon, 1 at the near row
        base = shade_near + (shade_far - shade_near) * (1.0 - t)
        period = beam_period(dy, span, near_pitch)

        # LEVEL OF DETAIL, indexed on the PERIOD and not on the row. Toward the
        # horizon the beams crowd together; below `lod_px` they would alias into
        # a solid dark band, and every row that draws them costs its own tiles
        # (no two rows share art, because no two rows share a period). This one
        # knob therefore sets both the picture and the budget — the module
        # header has the measured lod/tile/seam-row table.
        detail = 0.0 if period <= lod_px else min(1.0, (period - lod_px) / lod_fade)

        # A perspective-spaced cross seam (the beam ENDS): constant-depth lines
        # sit at dy = cross_near_frac * span / m. Horizontal lines are invariant
        # under horizontal scroll, so these cost nothing under motion and stay
        # put, and they read as depth in the graded rows the fan does not reach.
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
            level = base
            if detail > 0.0:
                q = (x - vx) / period      # the beam index as a real number
                j = int(math.floor(q + 0.5))
                frac = abs(q - j)          # 0 at a beam centre, 0.5 at a seam
                # Alternating beam tones on the parity of the SIGNED index. It
                # does not have to close on the wrap: the wrap is never on
                # screen inside the clean camera range, and outside it the tone
                # is the least of what is wrong.
                level += (0.6 if (j & 1) else -0.6) * detail
                if frac > 0.5 - (seam_px / period):
                    level -= 2.4 * detail          # the seam itself
                elif frac < 0.10 and crown > 0.0:
                    level += crown * detail
            if cross:
                level -= 1.6

            # A hard shadow line right under the horizon. Two pixel rows, so it
            # costs almost nothing, and it is what stops the far beams bleeding
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


def reclaimable_slots(layout, tiles, rows, anim_slots):
    """Slots this bake may overwrite, and they are of TWO kinds.

    (a) BAND-EXCLUSIVE: referenced by cells in `rows` and by no other row, so
        overwriting the band frees them.
    (b) UNREFERENCED: referenced by no layout cell at all. These are what a
        PREVIOUS bake of this band stranded when it needed fewer tiles than the
        band freed. Measured on the committed override on 2026-09-05: 39
        band-exclusive and 84 unreferenced, i.e. the shear had quietly taken the
        reclaimable budget from 123 down to 39 and every later bake would have
        inherited that. A slot nothing points at is free by definition.

    Neither kind may dip below `anim_slots`: a BgAnim band's phases[0] must stay
    byte-identical to tiles[0:anim_slots].
    """
    used_rows = {}
    for i, w in enumerate(layout):
        used_rows.setdefault(w & 0x7FF, set()).add(i // PLANE_COLS)
    band_rows = set(rows)
    band_cells = {r * PLANE_COLS + c for r in rows for c in range(PLANE_COLS)}
    exclusive = sorted(t for t in {layout[i] & 0x7FF for i in band_cells}
                       if used_rows[t] <= band_rows)
    dead = sorted(t for t in range(len(tiles)) if t not in used_rows)
    out = sorted(set(t for t in exclusive + dead if t >= anim_slots))
    return out, len(exclusive), len(dead)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--override", default=OVERRIDE)
    ap.add_argument("--out", default=None, help="default: rewrite --override in place")
    ap.add_argument("--row0", type=int, default=SHIPPED["row0"],
                    help="first cell row of the floor")
    ap.add_argument("--row1", type=int, default=SHIPPED["row1"],
                    help="last cell row (inclusive)")
    ap.add_argument("--near-pitch", type=float, default=SHIPPED["near_pitch"],
                    help="beam period in plane px at the NEAREST row. Every "
                         "other row's period is this scaled by dy/span, which "
                         "is what makes the beams a fan through a fixed "
                         "vanishing point — see beam_period()")
    ap.add_argument("--vp-col", type=int, default=SHIPPED["vp_col"],
                    help="vanishing point, in cell columns. 20 puts it at plane "
                         "x 159.5 = screen column 159.5, the centre column the "
                         "owner asked the beams to converge on")
    ap.add_argument("--lod-px", type=float, default=SHIPPED["lod_px"],
                    help="beam period below which no seam is drawn. THE TILE "
                         "KNOB: every seam row costs its own tiles because no "
                         "two rows share a period")
    ap.add_argument("--lod-fade", type=float, default=SHIPPED["lod_fade"],
                    help="px of period over which the seam contrast fades in "
                         "above --lod-px")
    ap.add_argument("--seam-px", type=float, default=SHIPPED["seam_px"],
                    help="half-width of a beam seam, in plane px")
    ap.add_argument("--cross-near-frac", type=float,
                    default=SHIPPED["cross_near_frac"],
                    help="depth fraction of the NEAREST row of beam ends")
    ap.add_argument("--horizon-row", type=int, default=SHIPPED["horizon_row"],
                    help="cell row where the floor meets the wall; this is the "
                         "fan's apex row and the engine ramp's zero")
    ap.add_argument("--shade-near", type=float, default=SHIPPED["shade_near"],
                    help="wood-ramp level at the near (bottom) row, 0..5")
    ap.add_argument("--shade-far", type=float, default=SHIPPED["shade_far"],
                    help="wood-ramp level at the horizon, 0..5")
    ap.add_argument("--crown", type=float, default=SHIPPED["crown"],
                    help="highlight along each beam's crown, 0 = none")
    ap.add_argument("--cross-seam-px", type=float, default=SHIPPED["cross_seam_px"],
                    help="beam-end spacing below which cross seams stop; 0 = none")
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

    anim_slots = 0
    for a in data.get("anims", []):
        anim_slots += a["cols"] * a["rows"]
    recyclable, n_excl, n_dead = reclaimable_slots(layout, tiles, rows, anim_slots)

    # ── Rasterise ────────────────────────────────────────────────────────────
    px = render_band(rows, near_pitch=args.near_pitch, vp_col=args.vp_col,
                     horizon_row=args.horizon_row,
                     shade_near=args.shade_near, shade_far=args.shade_far,
                     lod_px=args.lod_px, lod_fade=args.lod_fade,
                     seam_px=args.seam_px, crown=args.crown,
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

    stranded = len(spare)

    # ── Report ───────────────────────────────────────────────────────────────
    before = len(data["tiles"])
    after = len(tiles)
    span = len(rows) * 8 - (args.horizon_row - args.row0) * 8
    seam_rows = sum(1 for dy in range(span)
                    if beam_period(dy, span, args.near_pitch) > args.lod_px)
    print(f"perspective floor: plane rows {args.row0}..{args.row1} "
          f"({len(rows) * 8} px), FAN with apex at plane x "
          f"{args.vp_col * 8 - 0.5}, near-row beam period {args.near_pitch} px")
    print(f"  rows that draw beam seams         : {seam_rows} of {span} "
          f"(period > lod {args.lod_px} px)")
    print(f"  unique tiles the floor needs      : {len(new_keys)}")
    print(f"    of which matched existing art   : {reused_existing}")
    print(f"    of which written into recycled  : {len(fresh) - appended}")
    print(f"    of which APPENDED (new tiles)   : {appended}")
    print(f"  slots reclaimable                 : {len(recyclable)} "
          f"({n_excl} band-exclusive + {n_dead} unreferenced)")
    print(f"  reclaimable slots left stranded   : {stranded}")
    print(f"  blob length  {before} -> {after}   (capacity {CAP}, "
          f"static budget {STATIC_BUDGET}, band reserve {RESERVE})")
    print(f"  clean camera range at curve To(FACTOR_1_4): "
          f"{clean_camera_range(0.25):.0f} px "
          f"(FACTOR_1 would give {clean_camera_range(1.0):.0f})")
    if args.preview:
        write_preview(layout, tiles, args.preview)
        print(f"  preview -> {args.preview}")

    if after > CAP:
        msg = (f"{after} tiles exceeds BG_TILE_CAPACITY {CAP} — "
               "inject_editor_bg.py would abort. Raise --lod-px (the tile count "
               "is almost entirely the seam-row count) or coarsen --near-pitch.")
        if args.report:
            print(f"  OVER BUDGET: {msg}")
            print("  --report: nothing written")
            return
        sys.exit(f"ERROR: {msg}")
    if not appended:
        print("  ** zero net tiles: the floor fits entirely in the slots the "
              "band and the previous bake freed. band_reserve is untouched. **")
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
              f"spare. band_reserve stands at {RESERVE}. **")

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
