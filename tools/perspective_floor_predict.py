#!/usr/bin/env python3
"""perspective_floor_predict — a COMPUTED PREDICTION of the pseudo-3D floor.

THIS IS NOT A CAPTURE. No emulator ran. Every pixel below is computed from two
things that are already in this tree, and from nothing else:

  1. THE ART — tools/perspective_floor_gen.py's own `render_band()`, called with
     that tool's shipped argument defaults (rows 48..63, pitch 64, vp_col 20,
     lod_px 20, horizon_row 55, sym 2, shade 3.2/2.7). So the boards you see are
     the boards that tool would bake, not an artist's impression of them.
  2. THE SCROLL — tools/curve_probe.py's `derive_curve_buffer()`, which is the
     transcription of the engine's own per-line Bresenham ramp
     (engine/level/parallax.emp `.lp_curve`, and Step 4a's step/rem/span hoist).
     So the per-line HScroll words are the words `Parallax_Fill_PerLine` would
     write, not an idealised `camX * (y - horizon) / span`.

WHAT IS THEREFORE PREDICTED, AND WHAT IS ASSUMED
================================================
PREDICTED (traceable to the two models above): the board geometry, the per-line
HScroll word at every screen line, and hence where each board edge lands on
screen at each camera X.

ASSUMED (stated so it is not mistaken for a result):
  * that the floor art is baked into plane cell rows the visible window reaches.
    It is NOT baked today — games/sonic4/data/editor_bg_override.json still
    carries the original undergrowth (rows 48..55 repeat verbatim at 56..63).
  * that the scene authors `v_offset` so the band is on screen. Every shipped
    scene authors `v_offset: 0`, which shows plane rows 0..27 only.
  * the composite ignores Plane A entirely (no foreground, no sprites) and
    ignores the per-column V-deform, which is a SEPARATE axis — see the report.
  * colours are the OJZ act-1 wood ramp (palette SOURCE line 1, which the
    importer lands on CRAM line 2), decoded exactly as
    perspective_floor_gen.write_preview() decodes it.
  * the band is placed at screen line 96 via `v_offset: 288`, and the ramp
    starts at the HORIZON line (152), not at the band top — see HORIZON_LINE.

USAGE
=====
    python3 tools/perspective_floor_predict.py --out /tmp/floor_predict.png
    python3 tools/perspective_floor_predict.py --ascii
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perspective_floor_gen as pfg
import curve_probe as cp

# Packed FACTOR_* words, mirrored from engine/level/parallax_dsl.emp:25-40. The
# assert below is the drift guard: these are the only three this tool uses.
FACTOR_0 = 0x0FF
FACTOR_1 = 0x0F0

SCREEN_W = 320
SCREEN_H = 224
PLANE_W = pfg.PLANE_W            # 512

# The art band and where it lands on screen.
BAND_ROW0, BAND_ROW1 = 48, 63    # perspective_floor_gen's shipped --row0/--row1
HORIZON_ROW = 55                 # its shipped --horizon-row
BAND_TOP = 96                    # screen line the 128-px art band starts at.
                                 # Reached with `v_offset: 288` on a LOCKED plane
                                 # (Vscroll_BG = v_offset), because plane y 384
                                 # (cell row 48) - 288 = screen line 96.
# The ramp must be ZERO AT THE VANISHING POINT and grow below it — that is the
# perspective law, and the vanishing point is the horizon ROW, not the band top.
# Rows above the horizon are the shadowed wall behind the floor and must stay
# locked, or the wall shears while the floor slides.
HORIZON_LINE = BAND_TOP + (HORIZON_ROW - BAND_ROW0) * 8      # 96 + 56 = 152
PAL_PATH = "games/sonic4/data/generated/ojz/act1/ojz_palette.bin"
# CAREFUL: perspective_floor_gen.PAL_LINE (= 2) is the CRAM DESTINATION line, not
# an index into this file. Its own comment says so — "source line 1 -> CRAM line
# 2" — so the wood ramp is read from SOURCE line 1. The assert in palette() is
# what stops that off-by-one coming back; it cost one wrong-coloured render.
PAL_SRC_LINE = 1


def floor_art():
    """The floor band exactly as perspective_floor_gen would bake it."""
    rows = list(range(BAND_ROW0, BAND_ROW1 + 1))
    return pfg.render_band(rows, pitch=64, vp_col=20, seam_rows=0.0,
                           lod_px=20.0, horizon_row=HORIZON_ROW,
                           shade_near=3.2, shade_far=2.7, sym=2)


def hscroll(cam_x):
    """The 224 per-line Plane-B HScroll words the engine's ramp would write.

    Layer set: everything above HORIZON_LINE locked (FACTOR_0, no curve); the
    floor layer from HORIZON_LINE to line 223 with `fb: FACTOR_0, curve:
    To(FACTOR_1)`.
    That is the authored shape the report recommends, spelled as curve_probe
    takes it: (top, fa, fb, curve_to).
    """
    layers = [(0, FACTOR_1, FACTOR_0, None),
              (HORIZON_LINE, FACTOR_1, FACTOR_0, FACTOR_1)]
    buf = cp.derive_curve_buffer(layers, cam_x)
    return [cp.php.s16(buf[y][1]) for y in range(cp.php.HSCROLL_LINES)]


def palette():
    with open(PAL_PATH, "rb") as fh:
        words = struct.unpack(">48H", fh.read())
    line = words[PAL_SRC_LINE * 16:(PAL_SRC_LINE + 1) * 16]
    # Same decode as perspective_floor_gen.write_preview().
    pal = [((((w >> 1) & 7) * 36), (((w >> 5) & 7) * 36), (((w >> 9) & 7) * 36))
           for w in line]
    # The line we read must actually BE the wood ramp perspective_floor_gen names
    # in its WOOD comment (#240000 .. #FCB46C). If the palette is regenerated and
    # the ramp moves, this fires instead of quietly rendering a green floor.
    got = ["#%02X%02X%02X" % pal[i] for i in pfg.WOOD]
    want = ["#240000", "#482424", "#904824", "#B46C24", "#D89048", "#FCB46C"]
    assert got == want, ("palette source line %d is not the wood ramp: %s != %s"
                         % (PAL_SRC_LINE, got, want))
    return pal


def composite(art, h, pal):
    """Screen RGB for one camera X. Rows above the floor are left black."""
    out = [[(0, 0, 0)] * SCREEN_W for _ in range(SCREEN_H)]
    for y in range(BAND_TOP, SCREEN_H):
        art_row = art[y - BAND_TOP]
        # HScroll word H shifts the plane RIGHT by H, so the plane pixel shown
        # at screen x is (x - H). decode_factor already returns the NEGATED
        # camera term (parallax.emp's Decode_Factor_B), so no second negation.
        shift = h[y]
        for x in range(SCREEN_W):
            out[y][x] = pal[art_row[(x - shift) % PLANE_W]]
    return out


def write_png(panels, labels, path):
    from PIL import Image, ImageDraw
    gap, pad = 8, 16
    w = SCREEN_W * len(panels) + gap * (len(panels) - 1) + pad * 2
    h = SCREEN_H + pad * 2 + 14 + 16       # +16 so the labels sit BELOW the panels
    img = Image.new("RGB", (w, h), (24, 24, 28))
    for i, panel in enumerate(panels):
        sub = Image.new("RGB", (SCREEN_W, SCREEN_H))
        sub.putdata([px for row in panel for px in row])
        img.paste(sub, (pad + i * (SCREEN_W + gap), pad + 14))
    d = ImageDraw.Draw(img)
    d.text((pad, 3), "COMPUTED PREDICTION - no emulator ran.  "
                     "Art: perspective_floor_gen.render_band().  "
                     "Scroll: curve_probe.derive_curve_buffer().",
           fill=(200, 200, 200))
    for i, lab in enumerate(labels):
        d.text((pad + i * (SCREEN_W + gap), pad + 14 + SCREEN_H + 4), lab,
               fill=(240, 240, 120))
    img.save(path)


def ascii_figure(cams):
    """The per-line HScroll ramp, as text. Pure arithmetic, no art."""
    print("Plane-B HScroll word per screen line "
          "(fb: FACTOR_0 at the horizon, line %d; curve: To(FACTOR_1) at line 223)"
          % HORIZON_LINE)
    print("Values from curve_probe.derive_curve_buffer() = the engine's own ramp.\n")
    hs = {c: hscroll(c) for c in cams}
    print("  line |" + "".join("  camX=%-4d" % c for c in cams) + "   depth cue")
    print("  -----+" + "-" * (10 * len(cams)) + "---------------")
    for y in range(HORIZON_LINE, SCREEN_H, 8):
        cells = "".join("  %7d" % hs[c][y] for c in cams)
        frac = (y - HORIZON_LINE) / (SCREEN_H - 1 - HORIZON_LINE)
        bar = "#" * int(round(frac * 20))
        print("   %3d |%s   %s" % (y, cells, bar))
    y = SCREEN_H - 1
    cells = "".join("  %7d" % hs[c][y] for c in cams)
    print("   %3d |%s   %s" % (y, cells, "#" * 20))
    print("\n  The horizon line does not move at any camera X; the near edge moves")
    print("  at the full camera rate. That ratio IS the perspective, and it is")
    print("  what per-column V-scroll cannot express on any axis.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="write the 3-panel PNG here")
    ap.add_argument("--ascii", action="store_true", help="print the ramp table")
    ap.add_argument("--cams", default="0,32,64",
                    help="camera X positions to render, comma-separated")
    args = ap.parse_args()

    assert FACTOR_0 == 0x0FF and FACTOR_1 == 0x0F0, "FACTOR_* mirror drifted"
    cams = [int(c) for c in args.cams.split(",")]

    if args.ascii or not args.out:
        ascii_figure(cams)
    if args.out:
        art, pal = floor_art(), palette()
        panels = [composite(art, hscroll(c), pal) for c in cams]
        labels = ["camera X = %d" % c for c in cams]
        write_png(panels, labels, args.out)
        print("\nwrote %s  (COMPUTED PREDICTION, not a capture)" % args.out)


if __name__ == "__main__":
    main()
