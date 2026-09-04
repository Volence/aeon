#!/usr/bin/env python3
"""perspective_floor_gen — a PLACEHOLDER fanned wooden floor for the OJZ Plane-B map.

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

So the splay lives in the ART. That is what this tool draws.

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

THE 512-PX WRAP, AND WHY THE SEAM IS INVISIBLE
==============================================
Plane B wraps horizontally every 512 px (parallax.emp: PLANE_B_SPAN) and the
window is never wider than that, so a true unbounded fan would show a phase
discontinuity where plane x=511 meets x=0. Two things remove it:

  1. `boards_across()` snaps the board count to an EVEN integer per row, so the
     lattice closes exactly on 512 px. The deviation from a mathematically
     straight radial line is at most 512/(n*(n+1)) px — sub-pixel for every row
     this tool draws, so the boards still read as straight.
  2. With an even count and board CENTRES on the axes, the pattern is symmetric
     under x -> -x (mod 512). On a 512-circumference circle, reflection about 0
     and reflection about 256 are the SAME map, so one symmetry gives mirror
     axes at BOTH the vanishing point and the wrap seam. The seam is a mirror
     line, not a discontinuity.

That symmetry is also the tile budget: only plane columns 0..31 are unique, and
columns 32..63 are their H-flips, which the nametable expresses for free.

WHERE THE TILES COME FROM (measured, not asserted)
==================================================
`games/sonic4/data/editor_bg_override.json` holds 320 unique tiles. The region
`bg_region` (games/sonic4/vram.toml) is 448 tiles with `band_reserve = 128`
withheld from the static importer, so 128 tiles are PHYSICALLY free but are
policy-reserved for BgAnim band art.

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
BG_TILE_CAPACITY = 448          # cross-checked against tools/vram_map.py below

# ── The wood ramp, straight out of the palette already in CRAM ────────────────
# games/sonic4/data/generated/ojz/act1/ojz_palette.bin source line 1 -> CRAM
# line 2, which 3804 of the map's 4096 cells already use. Darkest to lightest.
# No `palette` stamp: a stamp would recolour every FG object sharing the line.
PAL_LINE = 2
WOOD = (1, 3, 4, 5, 6, 7)       # #240000 #482424 #904824 #B46C24 #D89048 #FCB46C
SEAM = 1                        # the near-black warm — plank seams and shadow


def boards_across(dy, span, pitch, sym=4, plane_w=PLANE_W):
    """Board count across the full 512-px plane at depth row `dy` (1..span).

    True perspective wants pitch*dy/span px between boards, i.e.
    plane_w*span/(pitch*dy) boards. Snapped to a multiple of `sym` so the
    lattice closes on the wrap AND so the reflection axes land on board centres.

    WHY `sym` IS THE TILE BUDGET. The pattern is symmetric under x -> -x about
    any axis the board lattice makes a fixed point of. With sym=2 those axes are
    plane x 255.5 (the vanishing point) and 511.5 (the wrap) — one reflection,
    so plane columns 32..63 are the H-flips of 31..0 and only 32 columns are
    unique. With sym=4 the quarter points 127.5 and 383.5 join them, because the
    reflection about 127.5 sends board j to -j - n/2 and that preserves j's
    PARITY exactly when n/2 is even. Only 16 columns are then unique.

    MEASURED on this act's band (rows 48..63, horizon 53, pitch 64, lod 12):
    sym=2 costs 181 tiles, sym=4 costs 99 -- but sym=4 puts FOUR vanishing
    points inside the 512-px plane, so a 320-px screen shows two or three of
    them and the picture reads as a hall of mirrors rather than one floor. That
    is why the default is 2 and the extra 58 tiles are spent. The other price is
    a coarser step in the
    board count as the rows recede (multiples of 4 rather than 2), which shows
    as a slightly stronger seam where the count changes.
    """
    ideal = plane_w * span / (pitch * dy)
    n = int(round(ideal / float(sym))) * sym
    return max(sym, n)


def shade(level):
    """Clamp a float brightness onto the six-step wood ramp."""
    i = int(round(level))
    return WOOD[max(0, min(len(WOOD) - 1, i))]


def render_band(rows, pitch, vp_col, seam_rows, lod_px, horizon_row=None,
                shade_near=3.5, shade_far=2.0, sym=4):
    """Rasterise the floor into a (rows*8) x 512 array of palette indices.

    `horizon_row` is the CELL ROW carrying the vanishing point. Rows above it
    are the shadowed wall behind the floor — a pure vertical gradient, which is
    both the right picture (the jungle floor in shade, meeting the boards at a
    hard line) and nearly free: a gradient row is one tile wide-flipped, so the
    whole upper half costs single digits. Rows at and below it carry the fan.

    Returns a list of pixel rows, each a list of 512 ints in 1..15.
    """
    top_row = rows[0]
    horizon = top_row if horizon_row is None else horizon_row
    shade_px = (horizon - top_row) * 8    # pixel rows above the vanishing point
    span = len(rows) * 8 - shade_px       # the fan's own height in pixels
    # THE HALF-PIXEL IS LOAD-BEARING. The reflection that makes the pattern
    # seamless across the 512-px wrap must map CELL column c to column 63-c, so
    # its axis sits BETWEEN pixels 255 and 256, not on pixel 256. Reflecting
    # about a whole pixel maps col 32 onto a pair of half-columns, every H-flip
    # match is lost, and the tile count roughly doubles (measured: 679 -> 355).
    vx = vp_col * 8 - 0.5                 # vanishing point x, plane pixels
    out = []
    # The shadowed wall above the horizon: darkest at the join with the jungle,
    # lifting slightly toward the horizon line so the two do not merge.
    for sy in range(shade_px):
        lvl = 0.15 + 0.9 * (sy / max(1, shade_px - 1))
        out.append([shade(lvl)] * PLANE_W)

    for dy in range(1, span + 1):
        t = dy / span                     # 0 at the horizon, 1 at the near row
        n = boards_across(dy, span, pitch, sym)
        p = PLANE_W / n                   # board pitch at this row, px

        # Depth shading: dark at the horizon, bright underfoot. The ramp is the
        # single strongest "this recedes" cue once the boards get too fine to
        # resolve, so it runs the whole height and not just the far rows.
        #
        # DELIBERATELY SHALLOW. A steep ramp (0.6 -> 4.2 was the first try)
        # crosses four of the six ramp steps, and because the plank alternation
        # rides on top of it, neighbouring boards cross each step at DIFFERENT
        # rows — so the floor read as a flight of stairs rather than a plane.
        # Keeping the ramp inside ~1.5 steps lets the alternation dominate and
        # the boards read as continuous stripes. It also halves the tile count,
        # because far fewer rows differ.
        base = shade_near + (shade_far - shade_near) * (1.0 - t)

        # Level of detail. Below ~lod_px the seams alias into noise and cost a
        # unique tile per cell; blend them out instead and let the shading carry
        # the depth. This is also what makes the far rows dedup to a handful.
        detail = 0.0 if p < lod_px else min(1.0, (p - lod_px) / lod_px)

        # A perspective-spaced cross seam (the plank ENDS): constant-depth lines
        # sit at dy = span/m. Horizontal lines are invariant under horizontal
        # scroll, so these cost nothing under motion and stay put.
        cross = False
        if seam_rows > 0:
            for m in range(1, 64):
                d = span / m
                if d < seam_rows:           # stop before the ends alias into a grid
                    break
                if int(round(d)) == dy:
                    cross = True
                    break

        line = []
        for x in range(PLANE_W):
            # Board centres at vx + j*p; the mirror axes (x = vx and x = vx-256)
            # are both centres because n is even.
            off = (x - vx) / p
            j = int(round(off))
            frac = abs(off - j)           # 0 at a board centre, 0.5 at a seam

            level = base
            # Alternating plank tones. Keyed on the PARITY of |j|, which is the
            # only per-board variation that survives the reflection x -> -x: it
            # is what keeps the wrap seam a mirror line, and it is also what
            # keeps the tile count finite (two variants, not one per board).
            #
            # SCALED BY `detail`, and that is not cosmetic. Left unfaded, the
            # alternation keeps flipping once the boards are thinner than a
            # pixel, so the far rows become per-pixel noise: every one of the 32
            # unique columns became a distinct tile and the top six cell rows
            # alone cost 192 of them (measured). Faded, they cost 1-3 each.
            # A HARD cutoff, not the seam's smooth fade. Fading the amplitude
            # through the middle values makes neighbouring boards round to
            # different ramp steps at different rows, which reads as blocky
            # rubble rather than distance. On/off keeps the far half clean.
            if p >= lod_px:
                level += 0.6 if (abs(j) & 1) else -0.6

            if detail > 0.0:
                seam_w = 0.5 - (0.9 / p)          # ~0.9 px of seam, in board units
                if frac > max(0.30, seam_w):
                    # the seam itself
                    level -= 2.4 * detail
                elif frac < 0.10:
                    # a soft highlight along the board's crown
                    level += 0.55 * detail
            if cross:
                level -= 1.6

            # A hard shadow line right under the horizon. Two pixel rows, so it
            # costs almost nothing, and it is what stops the far boards bleeding
            # into the wall above and turning the join into mush.
            if dy <= 2:
                level -= (3 - dy) * 0.9

            line.append(shade(level))
        out.append(line)
    return out


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
    ap.add_argument("--row0", type=int, default=48, help="first cell row of the floor")
    ap.add_argument("--row1", type=int, default=63, help="last cell row (inclusive)")
    ap.add_argument("--pitch", type=int, default=64,
                    help="board pitch in px at the near (bottom) row")
    ap.add_argument("--vp-col", type=int, default=20,
                    help="vanishing-point cell column. The apex sits at a FIXED "
                         "SCREEN x equal to this plane x, because the horizon "
                         "row's scroll factor is 0 and every row below it "
                         "scrolls in proportion; 20 (plane x 160) is therefore "
                         "the centre of a 320-px screen")
    ap.add_argument("--lod-px", type=float, default=20.0,
                    help="board pitch below which seams stop being drawn")
    ap.add_argument("--horizon-row", type=int, default=55,
                    help="cell row carrying the vanishing point; rows above it "
                         "are the shadowed wall behind the floor")
    ap.add_argument("--sym", type=int, default=2, choices=(2, 4),
                    help="board-count granularity; 4 adds the quarter-point "
                         "mirror axes and roughly halves the tile cost")
    ap.add_argument("--shade-near", type=float, default=3.2,
                    help="wood-ramp level at the near (bottom) row, 0..5")
    ap.add_argument("--shade-far", type=float, default=2.7,
                    help="wood-ramp level at the horizon, 0..5")
    ap.add_argument("--cross-seam-px", type=float, default=0.0,
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
    px = render_band(rows, args.pitch, args.vp_col,
                     seam_rows=args.cross_seam_px, lod_px=args.lod_px,
                     horizon_row=args.horizon_row,
                     shade_near=args.shade_near, shade_far=args.shade_far,
                     sym=args.sym)

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
          f"({len(rows) * 8} px), board pitch {args.pitch} px at the near row, "
          f"vanishing point at plane x {args.vp_col * 8}")
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
