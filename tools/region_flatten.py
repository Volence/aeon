#!/usr/bin/env python3
"""region_flatten — the act's painted regions turned into the engine's Region rows.

WHAT THIS IS. The aeon half of the regions seam: `{dataPath}regions.json` (aurora's
document, contract schema `aurora-regions.schema.json` at empyrean `c3f892f`) becomes the
flat, disjoint, act-covering list of INCLUSIVE rectangles `engine/structs.emp`'s `Region`
wants. `tools/effects_gen.py:load_act_regions` does the reading and the ref resolution;
this module is the pure geometry and the rule checks, with no filesystem in it, so the
golden fixture and aurora's TypeScript side have one arithmetic to agree with.

⚠ THE SPEC'S §5.2 DESCRIBES A DIFFERENT ALGORITHM FROM THE ONE BELOW, AND THE DIFFERENCE
IS A RULING, NOT A DRIFT. `empyrean docs/superpowers/specs/2026-09-14-aurora-regions-editor-design.md`
§5.2 writes out a PAINTER'S-ORDER flatten: an act-wide bottom layer, later regions
subtracted out of earlier ones, then an adjacency merge to keep a cut from multiplying
rows. §8 of the same document then records the owner overturning the model it was written
against, verbatim at 2026-09-14T14:54:34Z — *"Yeah probablyy go with how we think about
it"* — ruling **A, cut right away**: the editor trims the rectangles at the moment of the
draw, so `regions.json` holds each region's OWN area, already disjoint, and (the ruling's
own words) *"flattening becomes a check that the rows are disjoint and cover the act, not
a subtraction"*. §5.2's prose was never rewritten, which is the whole hazard: a reader who
stops at §5.2 implements the superseded model.

THE LANDED CONTRACT AGREES WITH THE RULING AND NOT WITH §5.2, which is what settles it for
this module rather than leaving it a reading of two paragraphs. The schema that shipped at
empyrean `c3f892f` carries `{schema, act, regions[]}` with ONE `rect` per region and a
REQUIRED non-null `preset`; it has no `defaults` object, no `bindings` wrapper and no
`rects` array, so the document §2.3 sketches cannot be written against it at all. A
subtraction flatten has nothing to subtract: there is no bottom layer in the file.

SO WHAT IS LEFT OF §5.2 HERE. Step 1 and step 2 are gone with the bottom layer. Step 3's
merge is gone with them, and that is worth saying plainly because it is the step the
acceptance test was framed around: under the ruling nothing ever splits a row, so nothing
needs re-merging, and act 1's ten rows come back because the document HAS ten regions, not
because a merge recovered them from more. Step 4 — the per-row rule checks — is the part
that survives whole, and it is `_check_row` below. What replaces steps 1-3 is the pair the
ruling names, disjointness and coverage, and they are not a weaker check than the
subtraction was: subtraction made coverage true by construction and therefore unfalsifiable,
while here a hole is a thing the author can actually have, so `uncovered()` has to be able
to FIND one and name it. That is the direction of travel the ruling chose — the editor
shows the hole in red, the build refuses it — and a check that cannot fail would be no
use to either side.

WHY THE SUBTRACTION PRIMITIVE IS STILL IN THIS FILE. `subtract()` is not left over from the
superseded flatten; it is how `uncovered()` works. Start from the whole act and subtract
every row, and what remains IS the set of holes, as rectangles the refusal can print. The
alternative — area arithmetic alone, which is what the engine's own `ensure` does, since a
comptime fn cannot allocate — says THAT a hole exists and never where.

BOUNDS COME FROM THE ACT'S OWN DESCRIPTOR, never from this file. `act_bounds()` folds
`ACT_W`, `CENTRE_X_MIN` and the rest out of the `.emp` `const` lines that declare them,
seeded with `engine/system/constants.emp`, so the reachable-band formula stays the
descriptor's sentence and only its leaves are imported. A descriptor missing one of them is
a `RuleError` naming it: this module never supplies a default for a bound, because a bound
it invented would be a rule the engine does not have.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

try:
    from emp_consts import emp_consts
except ImportError:                                   # pragma: no cover - path shim
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from emp_consts import emp_consts

AEON = Path(__file__).resolve().parent.parent
ENGINE_CONSTANTS = "engine/system/constants.emp"
#: The GENERATED act grid the descriptor folds GRID_W/GRID_H out of since
#: S2-COMPRESSED-ACT parcel 9 (tools/act_grid.py). Seeded alongside the engine
#: constants for the same reason they are: the FORMULA stays the descriptor's line,
#: only its leaves are imported, and `GRID_W = OJZ_ACT_GRID_W` made this a leaf.
ACT_GRID_EMP = "games/sonic4/data/generated/ojz/act1/act_grid.emp"

# The bounds `ojz_region()` checks each row against, by the names the descriptor declares
# them under. Every one is read; none is defaulted. A descriptor that renames one refuses
# here rather than silently dropping that rule — a dropped rule is a check that passes
# because it never ran, which is the failure shape this tree calls a vacuous gate.
BOUND_NAMES = ("ACT_W", "ACT_H", "REGION_MIN_SPAN",
               "CENTRE_X_MIN", "CENTRE_X_MAX", "CENTRE_Y_MIN", "CENTRE_Y_MAX")


class RuleError(Exception):
    """A document that cannot become a legal region table, or a descriptor this module
    cannot read its rules out of. Callers surface it as a build refusal naming the file."""


# ---------------------------------------------------------------------------
# Rectangle algebra. EXCLUSIVE (x, y, w, h) throughout — the editor's form and the
# document's — until `to_inclusive` at the very end. The conversion happens once, in this
# module, which is the split the spec assigns (§5.1: "Aurora converts nothing").
# ---------------------------------------------------------------------------

def _norm(r) -> tuple:
    """A document rect (a dict or a 4-tuple) as `(x, y, w, h)`, with w/h positive."""
    if isinstance(r, dict):
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
    else:
        x, y, w, h = r
    if w <= 0 or h <= 0:
        raise RuleError(f"rect {(x, y, w, h)} has a non-positive extent. `w` and `h` are "
                        f"SIZES in the document's exclusive form, so the smallest legal "
                        f"rectangle is w = 1, h = 1 — never 0, and never a second corner.")
    return (x, y, w, h)


def intersects(a, b) -> bool:
    """Do two exclusive rects share a pixel?"""
    ax, ay, aw, ah = _norm(a)
    bx, by, bw, bh = _norm(b)
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def subtract(a, b) -> list:
    """`a` minus `b`, as up to four disjoint exclusive rects.

    The decomposition is the spec's, in its order: the part of `a` ABOVE `b`, the part
    BELOW, then LEFT and RIGHT *within the overlapping rows only* — which is what keeps
    the four pieces disjoint instead of double-counting the corners. `a` untouched when
    they do not meet; `[]` when `b` covers `a`.
    """
    ax, ay, aw, ah = _norm(a)
    bx, by, bw, bh = _norm(b)
    if not intersects((ax, ay, aw, ah), (bx, by, bw, bh)):
        return [(ax, ay, aw, ah)]
    out = []
    top, bottom = ay, ay + ah
    if by > top:                                   # above
        out.append((ax, top, aw, by - top))
        top = by
    if by + bh < bottom:                           # below
        out.append((ax, by + bh, aw, bottom - (by + bh)))
        bottom = by + bh
    if bottom > top:                               # the band of rows `b` actually cuts
        if bx > ax:
            out.append((ax, top, bx - ax, bottom - top))
        if bx + bw < ax + aw:
            out.append((bx + bw, top, (ax + aw) - (bx + bw), bottom - top))
    return out


def uncovered(rects, act_w: int, act_h: int) -> list:
    """The parts of the act no rect covers, as exclusive rects. `[]` means exact coverage.

    THIS IS THE INSTRUMENT THAT CAN PRODUCE A NON-EMPTY ANSWER, and that matters more than
    it sounds: the engine's own coverage `ensure` is an area sum, which reports a hole as a
    wrong total and can never say where. A refusal an author cannot act on sends them to
    re-read their whole document. So this subtracts every row out of the act and hands back
    what is left, and `tools/test_regions_doc.py` punches a hole on purpose to prove the
    list is not empty-by-construction.
    """
    remaining = [(0, 0, act_w, act_h)]
    for r in rects:
        nxt = []
        for piece in remaining:
            nxt.extend(subtract(piece, r))
        remaining = nxt
        if not remaining:
            break
    return sorted(remaining)


def first_overlap(rects) -> tuple | None:
    """The first `(i, j)`, i < j, whose rects share a pixel — or None.

    `region_first_overlap` in the act descriptor restated, and deliberately the same scan
    order, so the pair this names is the pair the `.emp` ensure would name. The engine
    packs it as `i * 1000 + j`; a Python caller gets the pair.
    """
    norm = [_norm(r) for r in rects]
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            if intersects(norm[i], norm[j]):
                return (i, j)
    return None


def area_sum(rects) -> int:
    return sum(w * h for _x, _y, w, h in (_norm(r) for r in rects))


def to_inclusive(r) -> dict:
    """`{x, y, w, h}` -> `{x0, x1, y0, y1}`, the engine's inclusive, span-major edges.

    THE ONE CONVERSION SITE IN THE SUITE (spec §5.1, part 2 §6.3). `x1 = x + w - 1`, so a
    one-pixel column is `x0 == x1` and never `x1 < x0`. Aurora's flatten stays exclusive
    and crosses the line only at the shared golden.
    """
    x, y, w, h = _norm(r)
    return {"x0": x, "x1": x + w - 1, "y0": y, "y1": y + h - 1}


# ---------------------------------------------------------------------------
# The rules, read out of the act descriptor rather than restated.
# ---------------------------------------------------------------------------

def act_bounds(descriptor: str, aeon: Path = AEON) -> dict:
    """`ojz_region()`'s bounds, folded out of the descriptor's own `const` lines.

    `descriptor` is repo-relative. Seeded with `engine/system/constants.emp` AND the
    generated `act_grid.emp`, because every one of these formulas reaches into them
    (`ACT_W = GRID_W << SECTION_SIZE_SHIFT`, `GRID_W = OJZ_ACT_GRID_W`,
    `CENTRE_X_MAX = ACT_W - SCREEN_WIDTH + CAM_SCREEN_HALF_W`). The FORMULA stays the
    descriptor's line; only its leaves are imported.
    """
    path = aeon / descriptor
    if not path.is_file():
        raise RuleError(f"{descriptor} does not exist, so the per-row bounds this act "
                        f"checks against cannot be read. Every bound in "
                        f"{', '.join(BOUND_NAMES)} is read from the descriptor and none "
                        f"is defaulted here: a bound this module invented would be a rule "
                        f"the engine does not have.")
    grid_path = aeon / ACT_GRID_EMP
    if not grid_path.is_file():
        raise RuleError(
            f"{ACT_GRID_EMP} does not exist, so `GRID_W`/`GRID_H` are free names in "
            f"{descriptor} and every bound below folds to nothing. It is GENERATED "
            f"(python3 tools/act_grid.py emit) — emit it rather than letting this module "
            f"carry on with a rule set that silently stopped running.")
    seed = emp_consts(aeon / ENGINE_CONSTANTS)
    # MERGED, not replaced: emp_consts returns the FILE's own consts and drops the seed it
    # was given, so `seed = emp_consts(grid, seed=seed)` would throw the engine constants
    # away and every bound below would go missing.
    seed = {**seed, **emp_consts(grid_path, seed=seed)}
    vals = emp_consts(path, seed=seed)
    missing = [n for n in BOUND_NAMES if n not in vals]
    if missing:
        raise RuleError(f"{descriptor} declares no foldable `const` for {missing}. Those "
                        f"are the bounds `ojz_region()` checks every row against; this "
                        f"module reads them and never supplies one, because a rule that "
                        f"silently stops running is a check that passes for the wrong "
                        f"reason.")
    return {n: vals[n] for n in BOUND_NAMES}


def _check_row(row: dict, b: dict, who: str) -> list:
    """The per-row rules of `ojz_region()`, restated against ONE inclusive row.

    Returns a list of complaint strings (empty = legal). Every message names the rule and
    the number that broke it, because a refusal whose stated reason is wrong is worse than
    one that fails without a reason.
    """
    x0, x1, y0, y1 = row["x0"], row["x1"], row["y0"], row["y1"]
    out = []
    if x0 < 0 or y0 < 0:
        out.append(f"{who}: a negative edge ({x0}, {y0}) is outside every act — world px "
                   f"start at 0")
    if x0 > x1 or y0 > y1:
        out.append(f"{who}: inverted rectangle ({x0}..{x1}, {y0}..{y1}) contains no point")
    if x1 >= b["ACT_W"] or y1 >= b["ACT_H"]:
        out.append(f"{who}: reaches past the act — inclusive maximum is "
                   f"({b['ACT_W'] - 1}, {b['ACT_H'] - 1}), this row ends at ({x1}, {y1})")
    span = b["REGION_MIN_SPAN"]
    if x1 - x0 + 1 < span or y1 - y0 + 1 < span:
        out.append(f"{who}: {x1 - x0 + 1}x{y1 - y0 + 1} px is narrower than "
                   f"REGION_MIN_SPAN ({span} px) on an axis — the camera moves up to 16 px "
                   f"a frame and could step over it")
    # THE REACHABLE-EDGE RULES, SPELLED OUT PER SIDE AND NOT "MIRRORED". Both sides assert
    # the same thing over their own crossing PAIR — that both pixels straddling the edge lie
    # in the band — and that produces DIFFERENT expressions, which is what a reflection does.
    # The tempting simplification (reuse the left expression with x1 substituted) disagrees
    # with the engine on exactly two edges in this act, x = CENTRE_X_MIN and x = CENTRE_X_MAX,
    # so it survives any test that does not land an edge precisely on a band endpoint.
    # Measured by aurora over all 6144 edges, 2026-09-16; see the spec's §2.1 table.
    if x0 != 0 and not (x0 - 1 >= b["CENTRE_X_MIN"] and x0 <= b["CENTRE_X_MAX"]):
        out.append(f"{who}: interior LEFT edge x0 = {x0} is outside the camera centre's "
                   f"reachable band [{b['CENTRE_X_MIN']}, {b['CENTRE_X_MAX']}] and can "
                   f"never be crossed")
    if x1 != b["ACT_W"] - 1 and not (x1 >= b["CENTRE_X_MIN"] and x1 + 1 <= b["CENTRE_X_MAX"]):
        out.append(f"{who}: interior RIGHT edge x1 = {x1} is outside the camera centre's "
                   f"reachable band [{b['CENTRE_X_MIN']}, {b['CENTRE_X_MAX']}] and can "
                   f"never be crossed")
    if y0 != 0 and not (y0 - 1 >= b["CENTRE_Y_MIN"] and y0 <= b["CENTRE_Y_MAX"]):
        out.append(f"{who}: interior TOP edge y0 = {y0} is outside the camera centre's "
                   f"reachable band [{b['CENTRE_Y_MIN']}, {b['CENTRE_Y_MAX']}] and can "
                   f"never be crossed")
    if y1 != b["ACT_H"] - 1 and not (y1 >= b["CENTRE_Y_MIN"] and y1 + 1 <= b["CENTRE_Y_MAX"]):
        out.append(f"{who}: interior BOTTOM edge y1 = {y1} is outside the camera centre's "
                   f"reachable band [{b['CENTRE_Y_MIN']}, {b['CENTRE_Y_MAX']}] and can "
                   f"never be crossed")
    return out


def flatten(regions, bounds: dict, where: str = "regions.json") -> list:
    """The document's regions as the engine's rows, refusing rather than repairing.

    `regions` is the document's list, each entry a dict carrying at least `id` and `rect`;
    everything else on the entry is copied through untouched, so the caller's resolved
    bindings ride along. Row order is DOCUMENT order (the schema: "regions in author
    order"), which is what makes the emitted table stable across runs and what keeps every
    region INDEX a tool already names meaning the same place.

    The three checks, in the order a failing document most usefully meets them:
      1. per-row (`_check_row`), so a bad rectangle is named as itself before it is
         described as an overlap with its neighbour;
      2. pairwise disjointness, naming the two ids — `Region_Resolve` returns the FIRST
         containing row, so an overlap makes identity depend on table order;
      3. coverage, naming the uncovered rectangles — "a hole is a place with no identity".

    It never drops a region, fills a hole, clamps a rect, or reads a sidecar for something
    the document left out (spec §5.3).
    """
    rows = []
    complaints = []
    for i, reg in enumerate(regions):
        rid = reg.get("id", f"#{i}")
        row = dict(reg)
        row.pop("rect", None)
        row.update(to_inclusive(reg["rect"]))
        row["index"] = i
        rows.append(row)
        complaints.extend(_check_row(row, bounds, f"{where}: region {rid!r} (row {i})"))
    if complaints:
        raise RuleError("\n".join(complaints))

    rects = [(r["x0"], r["y0"], r["x1"] - r["x0"] + 1, r["y1"] - r["y0"] + 1) for r in rows]
    pair = first_overlap(rects)
    if pair is not None:
        i, j = pair
        raise RuleError(
            f"{where}: regions {rows[i]['id']!r} (row {i}) and {rows[j]['id']!r} (row {j}) "
            f"overlap — {rows[i]['x0']}..{rows[i]['x1']} x {rows[i]['y0']}..{rows[i]['y1']} "
            f"against {rows[j]['x0']}..{rows[j]['x1']} x {rows[j]['y0']}..{rows[j]['y1']}. "
            f"Identity must be a function of the camera centre alone; with an overlap it "
            f"depends on scan order, because Region_Resolve returns the FIRST containing "
            f"row. The editor cuts on draw (owner ruling 2026-09-14), so an overlap in the "
            f"file means the document was hand-edited or written by something that does not "
            f"cut.")

    holes = uncovered(rects, bounds["ACT_W"], bounds["ACT_H"])
    if holes:
        shown = ", ".join(f"x {x}..{x + w - 1} y {y}..{y + h - 1}" for x, y, w, h in holes[:6])
        more = "" if len(holes) <= 6 else f" (and {len(holes) - 6} more)"
        raise RuleError(
            f"{where}: {len(holes)} rectangle(s) of the {bounds['ACT_W']}x{bounds['ACT_H']} "
            f"act belong to no region: {shown}{more}. A hole is a place with no identity — "
            f"Region_Resolve would return nothing there and the crossing would keep whatever "
            f"region the camera came from. Give the area to a region; the generator will not "
            f"fill it with a default it was not handed.")
    return rows


def area_of_rows(rows) -> int:
    """The summed inclusive area, the `region_area_sum` ensure's number."""
    return sum((r["x1"] - r["x0"] + 1) * (r["y1"] - r["y0"] + 1) for r in rows)
