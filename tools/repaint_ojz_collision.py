#!/usr/bin/env python3
"""Repaint the two OJZ act-1 collision authoring defects. CHECK MODE BY DEFAULT.

This tool is HELD, not applied. It exists because the two defects diagnosed on
2026-08-28 live in the OWNER'S LIVE EDITOR TREE, which no lane may write:

  * docs/2026-08-28-ojz-act1-floor-collision-defects.md — floor cells painted
    with S&K base shape 114 (a full block MISSING ITS LEFTMOST PIXEL COLUMN),
    X-flipped, so the floor has a 1 px hole at every world X = 15 (mod 16).
  * docs/GLIDE_LANDING_ANGLE_DIAGNOSIS.md — flat floor painted with S&K base
    shape 251, a full block that carries angle $E0 (a 45-degree slope).

    NOTE, and this is the correction that matters: the shape-114 diagnosis
    recommends repainting to "shape 255 (or 251), both of which are all-16".
    Shape 251 IS all-16, but its angle is $E0 — repainting the floor to 251
    installs the SECOND bug across the whole floor. Only 255 is safe: all-16
    with angle $FF, the odd 'no usable angle' sentinel, which is the full-solid
    block S&K itself uses 11,493 times across its 28 zones. This tool only ever
    paints 255.

-----------------------------------------------------------------------------
HOW IT DECIDES WHAT TO REPAINT (nothing here is a literal cell word)
-----------------------------------------------------------------------------
It reads the editor cell words, resolves each one against the committed S&K base
bank exactly as tools/collision_pipeline.bake_plane_cell does (shape -> profile +
angle, then X-flip, then Y-flip), and applies tools/collision_consistency.py's
two rules to the resolved grid. It repaints ONLY cells those rules flag:

  TARGET-PINHOLE  a cell whose resolved profile is full except for one or two
                  zero columns (shape 114 and its flips are the instance here).
  TARGET-FLATRUN  a cell inside a Rule-A violating run: a floor-exposed full
                  block, in a horizontal run of >= 4 columns, carrying an even
                  non-zero angle.

Both are recomputed from the tree's current bytes on every run, so the tool is
safe against a tree that has moved: floor added or moved since the diagnosis is
matched on its geometry, and an isolated 45-degree corner block (which S&K uses
legitimately, 184 times) is NOT a Rule-A violation and is left alone.

The repaint itself preserves each cell's SOLIDITY bits. Whether the main floor
should be SOL_TOP or SOL_ALL is Defect 2 of the shape-114 diagnosis and is a
gameplay ruling for the owner, not something this tool decides.

It also preserves each cell's LOOP CROSSOVER mark (bits 15:14,
cp.XOVER_SHIFT — docs/LOOP_CROSSOVER_ENCODING.md §3.4). That field is empty in
every shipped plane file today, so this is a rule ahead of its content: the
moment Aurora's brush paints one, a re-run of this tool must not eat it. A
marked cell among the targets is reported as a NOTICE below the summary — it is
NOT a refusal, because the anchor rules geometry and path membership
independent axes (§4 Q4).

-----------------------------------------------------------------------------
WHY AN ABSENCE CANNOT READ AS SUCCESS
-----------------------------------------------------------------------------
Success is defined by the VERIFIED END STATE, never by a count of cells touched:

  targets found, end state clean      -> REPAINTED / WOULD REPAINT   exit 0
  no targets,    end state clean      -> ALREADY CLEAN (idempotent)  exit 0
  no targets,    end state NOT clean  -> REFUSED                     exit 3
  targets found, end state NOT clean  -> REFUSED                     exit 3
  no section files / no floor at all  -> REFUSED (unmeasurable)      exit 2

So a run that silently repaints nothing on a tree that still has the defect is
an explicit, loud REFUSAL saying the matcher does not cover what is there. It
can never print success.

Re-running after a successful apply lands in ALREADY CLEAN: idempotent.

-----------------------------------------------------------------------------
AFTER APPLYING
-----------------------------------------------------------------------------
This writes the EDITOR tree only. The generated tree and the ROM collision
tables do not follow until the level is re-baked:

    tools/regenerate-level.sh     (needs the sonic_hack + skdisasm donors)
    ./build.sh                    (runs tools/collision_consistency.py)

Usage:
    python3 tools/repaint_ojz_collision.py                 # CHECK, writes nothing
    python3 tools/repaint_ojz_collision.py --root DIR      # check another checkout
    python3 tools/repaint_ojz_collision.py --apply         # WRITE the repaint
    python3 tools/repaint_ojz_collision.py --apply --root DIR
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import collision_consistency as cc            # noqa: E402
import collision_pipeline as cp               # noqa: E402

ROOT = cc.ROOT
SAFE_FULL_SHAPE = 255          # all-16 profile, angle $FF (odd sentinel)
EDITOR_W = 256                 # editor grid is 256x256 tiles
PROFILE_LEN = cp.PROFILE_LEN


def editor_dir_for(root=None):
    return os.path.join(root or ROOT, "games", "sonic4", "data", "editor",
                        "ojz", "act1")


def base_bank_for(root=None):
    base = os.path.join(cc.coll_dir_for(root), "base")
    try:
        with open(os.path.join(base, "heightmaps.bin"), "rb") as f:
            hm = f.read()
        with open(os.path.join(base, "angles.bin"), "rb") as f:
            an = f.read()
    except OSError as exc:
        raise cc.GateError(f"cannot read the S&K base bank under {base}: {exc}")
    if len(hm) != 256 * PROFILE_LEN or len(an) != 256:
        raise cc.GateError(
            f"base bank under {base} is {len(hm)}/{len(an)} B, expected "
            f"{256 * PROFILE_LEN}/256 — refusing to guess the layout")
    return hm, an


def resolve_word(word, hm, an):
    """Editor cell word -> (heights, angle, solidity), or None for air.

    Mirrors collision_pipeline.bake_plane_cell exactly (shape, xflip, yflip,
    this plane's solidity in bits 13:12), so what this tool judges is what the
    bake will intern.
    """
    shape = word & cp.BLOCK_ID_MASK
    sol = (word >> cp.PATH_A_SOL_SHIFT) & 3
    if sol == 0 or shape == 0:
        return None
    heights = hm[shape * PROFILE_LEN:(shape + 1) * PROFILE_LEN]
    angle = an[shape]
    if word & cp.CHUNK_XFLIP_BIT:
        heights = cp.flip_profile_x(heights)
        angle = cp.flip_angle_x(angle)
    if word & cp.CHUNK_YFLIP_BIT:
        heights = cp.flip_profile_y(heights)
        angle = cp.flip_angle_y(angle)
    return list(heights), angle, sol


def repaint_word(word):
    """Same solidity, same crossover mark, shape 255, no flips.

    This function REBUILDS the word, so every field it does not name is a field
    it silently destroys. Two are named and carried through:

      solidity (bits 13:12) — the owner's gameplay ruling (Defect 2), not this
        tool's to decide.
      XOVER (bits 15:14, cp.XOVER_SHIFT) — the loop crossover mark, which is a
        property of the PATH, not of the surface's geometry. This tool paints
        geometry; docs/LOOP_CROSSOVER_ENCODING.md §3.4 makes preserving the mark
        a rule (§6 change 6, rule R4) and names this very function as its only
        violator on our side of the wall. Carried, not refused: §4 Q4 rules the
        two axes independent and all four combinations legal, and §6 change (1)
        goes out of its way to keep a crossover alive on a cell with NO geometry
        at all. Repainting to shape 255 only makes such a cell more solid, so it
        can make the mark fire more reliably and cannot lose it.

    Anything added to this word in future must be added here too, or the next
    run of this tool erases it.
    """
    sol = (word >> cp.PATH_A_SOL_SHIFT) & 3
    xover = (word >> cp.XOVER_SHIFT) & cp.XOVER_MASK
    return ((xover << cp.XOVER_SHIFT) | (sol << cp.PATH_A_SOL_SHIFT) |
            SAFE_FULL_SHAPE)


def is_pinhole_profile(heights):
    """Full except for one or two zero columns — a floor with a hole in it.

    Derived, not a shape id: shape 114 X-flipped is [16 x15, 0], and any shape
    that resolves to the same geometry has the same 1 px hole. The bound is 2
    columns because a 16 px cell is 2 collision columns wide, so a gap of 3+
    columns starts to be a real ledge rather than a pinhole.
    """
    zeros = sum(1 for h in heights if h == 0)
    fulls = sum(1 for h in heights if h == PROFILE_LEN)
    return 1 <= zeros <= 2 and fulls == PROFILE_LEN - zeros


class Section:
    """One editor collattr plane file, decoded into a (row, col) cell grid."""

    def __init__(self, path, hm, an):
        self.path = path
        with open(path, "rb") as f:
            self.data = bytearray(f.read())
        expect = EDITOR_W * EDITOR_W * 2
        if len(self.data) != expect:
            raise cc.GateError(f"{path} is {len(self.data)} B, expected {expect} "
                               f"— refusing to guess the layout")
        self.hm, self.an = hm, an
        self.rows = cc.MAX_ATTRS and (EDITOR_W // 2)   # 128 collision rows

    def offset(self, col, cr):
        """Byte offset of the cell word. `apply_editor_collision_overlay` samples
        the TOP tile row of each 16 px collision cell: o = (cr*2)*256 + col."""
        return 2 * ((cr * 2) * EDITOR_W + col)

    def word(self, col, cr):
        o = self.offset(col, cr)
        return (self.data[o] << 8) | self.data[o + 1]

    def set_word(self, col, cr, w):
        """Write the cell word into BOTH tile rows of the 16 px collision cell.

        The bake only reads the even (top) row, but the editor renders both, so
        writing one would leave Aurora showing the old shape on the odd row.
        """
        for tile_row in (cr * 2, cr * 2 + 1):
            o = 2 * (tile_row * EDITOR_W + col)
            self.data[o] = (w >> 8) & 0xFF
            self.data[o + 1] = w & 0xFF

    def grid(self):
        """(resolved, attrs) — resolved[(col,cr)] = (heights, angle, sol);
        attrs is a synthetic per-cell attr grid Rule A can run over."""
        resolved = {}
        for cr in range(self.rows):
            for col in range(EDITOR_W):
                r = resolve_word(self.word(col, cr), self.hm, self.an)
                if r:
                    resolved[(col, cr)] = r
        return resolved


def build_rule_inputs(resolved):
    """Turn a resolved editor grid into the (coll_rows, heights, angles,
    solidity) shape collision_consistency's rules expect, by interning each
    distinct (heights, angle, sol) into a local attr table."""
    heights = [[0] * PROFILE_LEN for _ in range(cc.MAX_ATTRS)]
    angles = [0] * cc.MAX_ATTRS
    solidity = [0] * cc.MAX_ATTRS
    index = {}
    rows = EDITOR_W // 2
    coll = [[0] * EDITOR_W for _ in range(rows)]
    nxt = 1
    for (col, cr), (h, a, s) in resolved.items():
        key = (tuple(h), a, s)
        idx = index.get(key)
        if idx is None:
            if nxt >= cc.MAX_ATTRS:
                raise cc.GateError(
                    "more than 255 distinct (profile, angle, solidity) combos in "
                    "one editor plane — the bake would overflow the attr-set too")
            idx = nxt
            nxt += 1
            index[key] = idx
            heights[idx] = list(h)
            angles[idx] = a
            solidity[idx] = s
        coll[cr][col] = idx
    return coll, heights, angles, solidity


def analyse(sec, solid_top, min_gap_px):
    """(targets, rule_a_violations, rule_b_violations) for one plane file."""
    resolved = sec.grid()
    coll, heights, angles, solidity = build_rule_inputs(resolved)
    va, _ = cc.find_flat_run_violations(coll, heights, angles, solidity, solid_top)
    vb, _ = cc.find_pinhole_violations(coll, heights, solidity, solid_top,
                                       min_gap_px)

    targets = {}     # (col, cr) -> reason
    for (col, cr), (h, _a, _s) in resolved.items():
        if is_pinhole_profile(h):
            targets[(col, cr)] = "PINHOLE"
    for v in va:
        for col in range(v["col_start"], v["col_end"] + 1):
            targets.setdefault((col, v["row"]), "FLATRUN")
    return resolved, targets, va, vb


def run(root=None, apply_changes=False, out=sys.stdout):
    hm, an = base_bank_for(root)
    solid_top = cc.read_emp_const(cc.constants_emp_for(root), "SOLID_TOP")
    x_radius = cc.read_emp_const(cc.constants_emp_for(root), "PLAYER_X_RADIUS")
    min_gap_px = 2 * x_radius

    edir = editor_dir_for(root)
    paths = sorted(glob.glob(os.path.join(edir, "section_*.collattr.bin")) +
                   glob.glob(os.path.join(edir, "section_*.collattrb.bin")))
    if not paths:
        raise cc.GateError(
            f"no section_*.collattr*.bin under {edir}: nothing to inspect. "
            f"Refusing to report a clean run on an empty population.")

    mode = "APPLY" if apply_changes else "CHECK (writes nothing)"
    print(f"repaint_ojz_collision — mode: {mode}", file=out)
    print(f"  editor tree: {edir}", file=out)
    print(f"  sensor-pair separation (2 x PLAYER_X_RADIUS) = {min_gap_px} px, "
          f"SOLID_TOP = {solid_top}  [derived from "
          f"{os.path.relpath(cc.constants_emp_for(root), root or ROOT)}]", file=out)

    total_targets = 0
    total_cells = 0
    before_a = before_b = 0
    after_a = after_b = 0
    written = []
    marked = []     # target cells carrying a loop crossover mark

    for path in paths:
        sec = Section(path, hm, an)
        resolved, targets, va, vb = analyse(sec, solid_top, min_gap_px)
        total_cells += len(resolved)
        before_a += len(va)
        before_b += len(vb)
        if not resolved:
            print(f"  {os.path.basename(path):32s} no solid cells", file=out)
            continue

        by_reason = {}
        for r in targets.values():
            by_reason[r] = by_reason.get(r, 0) + 1
        total_targets += len(targets)

        # Simulate (or perform) the repaint, then RE-VERIFY on the result.
        for (col, cr) in targets:
            w = sec.word(col, cr)
            x = (w >> cp.XOVER_SHIFT) & cp.XOVER_MASK
            if x != cp.XOVER_NONE:
                marked.append((os.path.basename(path), col, cr, x))
            sec.set_word(col, cr, repaint_word(w))
        _res2, _t2, va2, vb2 = analyse(sec, solid_top, min_gap_px)
        after_a += len(va2)
        after_b += len(vb2)

        print(f"  {os.path.basename(path):32s} {len(resolved):5d} solid cells | "
              f"targets {len(targets):4d} {by_reason or ''} | "
              f"rule A {len(va)}->{len(va2)}  rule B {len(vb)}->{len(vb2)}",
              file=out)

        if apply_changes and targets:
            with open(path, "wb") as f:
                f.write(sec.data)
            written.append(path)

    clean_after = (after_a == 0 and after_b == 0)
    print(file=out)
    print(f"  population: {total_cells} solid editor cells across {len(paths)} "
          f"plane file(s)", file=out)
    print(f"  violations before: rule A {before_a}, rule B {before_b}", file=out)
    print(f"  violations after:  rule A {after_a}, rule B {after_b}", file=out)
    print(f"  cells targeted:    {total_targets}", file=out)

    if marked:
        print(file=out)
        print(f"  NOTICE: {len(marked)} target cell(s) carry a loop crossover "
              f"mark (bits 15:14).", file=out)
        print("    The mark is PRESERVED — this tool repaints geometry, and "
              "docs/LOOP_CROSSOVER_ENCODING.md", file=out)
        print("    §4 Q4 rules geometry and path membership independent axes. "
              "Listed so the repaint of a", file=out)
        print("    loop's marked column is never a surprise. This is not a "
              "refusal.", file=out)
        for name, col, cr, x in marked[:16]:
            print(f"      {name} col {col} row {cr} XOVER={x}", file=out)
        if len(marked) > 16:
            print(f"      ... and {len(marked) - 16} more", file=out)

    if total_cells == 0:
        print("REFUSED: not one solid collision cell in the whole editor tree. "
              "Nothing could be checked.", file=out)
        return 2

    if not clean_after:
        print(file=out)
        print("=" * 78, file=out)
        print("REFUSED — the repaint does NOT clear this tree.", file=out)
        if total_targets == 0:
            print("  It matched ZERO cells and the tree still violates. The "
                  "defect present here is\n  NOT the one this tool knows how to "
                  "repaint. Do not treat this as a clean run.", file=out)
        else:
            print(f"  It matched {total_targets} cells but {after_a} rule-A and "
                  f"{after_b} rule-B violations\n  survive. Repainting would be "
                  f"an incomplete fix.", file=out)
        print("  Nothing was written." if not written else
              f"  WROTE {len(written)} file(s) BEFORE this was detected — "
              f"`git checkout --` them.", file=out)
        print("  Run tools/collision_consistency.py for the full violation list.",
              file=out)
        print("=" * 78, file=out)
        return 3

    if total_targets == 0:
        print(file=out)
        print("ALREADY CLEAN — no cell matched, and both rules are already at "
              "zero on this tree.", file=out)
        print("  Idempotent no-op. This is the expected result of a second run "
              "after --apply.", file=out)
        return 0

    print(file=out)
    if apply_changes:
        print(f"REPAINTED {total_targets} cells in {len(written)} file(s); both "
              f"rules verified at zero afterwards.", file=out)
        for p in written:
            print(f"    wrote {p}", file=out)
        print("  NEXT: tools/regenerate-level.sh  (the generated tree and the ROM",
              file=out)
        print("        collision tables do NOT follow until the level is re-baked)",
              file=out)
        print("  THEN: ./build.sh  (runs tools/collision_consistency.py)", file=out)
    else:
        print(f"WOULD REPAINT {total_targets} cells; simulated result verified "
              f"clean under both rules.", file=out)
        print("  Nothing was written. Re-run with --apply to perform it.", file=out)
    return 0


def main(argv):
    apply_changes = "--apply" in argv
    root = None
    for i, a in enumerate(argv):
        if a == "--root" and i + 1 < len(argv):
            root = argv[i + 1]
        elif a.startswith("--root="):
            root = a.split("=", 1)[1]
    try:
        return run(root=root, apply_changes=apply_changes)
    except cc.GateError as exc:
        print("=" * 78)
        print("repaint_ojz_collision: COULD NOT MEASURE")
        print(exc)
        print("=" * 78)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
