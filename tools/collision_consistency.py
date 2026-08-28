#!/usr/bin/env python3
"""Collision height/angle consistency gate — refuse authored collision whose
GEOMETRY and METADATA contradict each other.

Two real defects motivated this file (both diagnosed 2026-08-28, both invisible
to every other check in the tree):

  * docs/GLIDE_LANDING_ANGLE_DIAGNOSIS.md — a 640 px flat slab of uniformly-full
    16x16 cells carrying angle $E0 (a 45-degree slope). Knuckles glides onto it,
    Glide_Collide installs the raw angle, and he is pushed into the left act
    boundary forever. (That doc arrives with branch `diag/glide-momentum`; if the
    path does not resolve, that branch has not merged yet.)
  * docs/2026-08-28-ojz-act1-floor-collision-defects.md — 300 floor cells painted
    with S&K base shape 114 X-flipped: a full block MISSING ONE PIXEL COLUMN, so
    the floor has a 1 px hole at every world X = 15 (mod 16). The single-point
    ledge probe falls into it and Knuckles teeters on flat ground.

RULE A (flat-run / angle) and RULE B (pinhole) below are the two checks. Neither
is a list of known-bad values: both are derived from what the ENGINE does with
the pair, and both are checked against the bytes that actually reach the ROM.

-----------------------------------------------------------------------------
WHAT IS CHECKED, AND AGAINST WHAT
-----------------------------------------------------------------------------
Input is entirely COMMITTED, in-repo, donor-free:

  games/sonic4/data/generated/ojz/act1/sec{N}_strips_a.bin
        the baked per-cell attr grid — 128 collision rows x 256 columns, TWO
        planes, decoded by tools/ojz_block_gen.parse_strips (reused, not
        reimplemented). A collision cell is 8 px WIDE and 16 px TALL: see
        engine/level/collision_lookup.emp Collision_GetType, which does
        `lsr.w #3, d0` on X (8 px columns) and `lsr.w #3` then `lsr.w #1` on Y
        (16 px rows).
  games/sonic4/data/collision/{heightmaps,angles,solidity}.bin
        the interned runtime tables those attr bytes index.
  engine/system/constants.emp
        PLAYER_X_RADIUS and SOLID_TOP are READ FROM THE SOURCE at runtime, never
        copied here. A parse failure is a LOUD failure, not a default.

This deliberately checks the BAKED artifact rather than the editor tree: the
baked strips are what `ojz_block_gen` packs into the ROM, so a green result is
about the shipped bytes and not about authoring intent.

-----------------------------------------------------------------------------
RULE A — a flat run cannot be a slope
-----------------------------------------------------------------------------
Derivation, from games/sonic4/player/player_sensors.emp `probe_core`:

  * A floor probe that lands on a cell whose height is 16 (full) takes the
    `.full_back` path: it re-probes ONE CELL UP, and when that cell is air for
    the floor class it KEEPS THE PRIMARY CELL'S OWN angle and attr
    ("back cell empty -> primary's attr / ... and angle"). So a full cell whose
    upper neighbour fails the floor class SUPPLIES ITS OWN ANGLE to the floor
    sensor. A full cell with a solid cell above it never does, and is exempt.
  * The class gate is `SolidityTable[attr] & d6` with d6 = SOLID_TOP for the
    floor class, so "passes the floor class" means `solidity & SOLID_TOP`.

Now the geometry. Take a maximal horizontal run of such floor-exposed full
cells in one collision row. Every one of them is solid to the top of its cell,
so the surface across the whole run is a straight horizontal line at the row's
top edge. A horizontal line has slope 0. Therefore every cell in the run must
carry a flat angle.

Which angles count as flat:
  * $00 — flat. Obviously legitimate.
  * any ODD byte — the "no usable angle" sentinel. `Player_SensorFloor` does
    `btst #0, d1 / bne .substitute` BEFORE the value is used as a direction, so
    an odd byte is never consumed as an angle at all. S&K's own full block is
    shape 255 with angle $FF, used 11,493 times across its 28 zone collision
    indexes — it is THE full-solid block of that entire game. Refusing odd would
    refuse essentially all legitimate flat ground.
  * an EVEN NON-ZERO byte is a positive claim of slope, and is the violation.

RUN_MIN_COLUMNS = 4 (32 px), and it is derived, not chosen for the bug:
  * a base shape's height profile is 16 px wide (PROFILE_LEN), spanning TWO
    8 px attr columns, so a run of 2 columns can be a single shape placement;
  * a run of 4 columns spans TWO adjacent 16 px shape placements, which is the
    smallest run that proves the surface is horizontal for longer than any one
    authored shape.
This exemption is not academic. S&K ships FOUR full-block shapes with even
45-degree angles — 251 ($E0), 252 ($20), 253 ($A0), 254 ($60) — and uses them
184 times across its zones, always sparsely (2, 4, 6, 10, 16 placements), as
isolated corner/loop fillers, never as bulk floor. A per-attr rule of the form
"full block => angle must be flat" would refuse all 184 of those and would
refuse future loop authoring here. That is the over-strict gate that gets
switched off, so this gate does not make that claim. It only fires when the
surface is provably horizontal across more than one shape.

The observed defects have runs of 8, 12 and 16 columns (64-128 px), so the
threshold has 2-4x margin over the shortest real violation.

-----------------------------------------------------------------------------
RULE B — a floor gap narrower than the sensor pair is not level design
-----------------------------------------------------------------------------
Derivation, from two engine consumers of the same bytes:

  * `Player_SensorFloor` runs a PAIR of probes at x - r and x + r where
    r = PLAYER_X_RADIUS (9), i.e. 2*r = 18 px apart, and keeps the CLOSER
    result. A gap in the floor narrower than 18 px can therefore never be under
    both sensors at once: it can never detach a standing player, and nothing
    can ever fall through it.
  * `Player_AtLedgeEdge` (player_sensors.emp:503) probes a SINGLE point at
    x +/- LEDGE_PROBE_REACH and calls anything past LEDGE_NO_GROUND a ledge. A
    1 px gap IS visible to it.

So for every floor gap narrower than 2 * PLAYER_X_RADIUS the two consumers
disagree about the same data, and the only observable effect is a false ledge —
the teeter-on-flat-ground the owner reported. A gap that cannot be fallen into
and cannot be seen is not level design; it is an authoring slip. Gaps at or
above the pair separation are real ledges and are left alone.

The per-pixel floor line is reconstructed the way the engine reads it:
`probe_core` indexes the height profile with `andi.w #$F, d0` on the WORLD X
pixel, so world X uses column `x & 15` of the attr found at 8 px column `x >> 3`.

-----------------------------------------------------------------------------
WHAT A GREEN RESULT RULES OUT — AND WHAT IT DOES NOT
-----------------------------------------------------------------------------
Green means: across every committed OJZ act-1 section and BOTH collision planes,
no floor surface that the engine can actually read claims a slope it does not
have (Rule A), and no floor has a hole too narrow for the sensor pair to see
(Rule B).

Green does NOT mean:
  * that BURIED full blocks are consistent. A full cell with a solid cell above
    it never supplies its angle to a floor probe, so its angle is not checked.
    That is deliberate, not an oversight.
  * that WALL and CEILING readings are consistent. `HeightMapsRot` and the
    ceiling branch of `Player_SensorFloor` (which keeps the raw angle under the
    odd-flag rule alone, without the divergence snap) are NOT audited here.
  * that partial-height shapes carry correct angles. Only the degenerate
    zero-rise case is provable from geometry; S&K's authored angles for sloped
    shapes are hand-tuned and are not the least-squares fit of their profiles,
    so a general angle-vs-profile check would produce false positives.
  * anything about `sec{N}_blocks.bin`, the S4LZ blob that actually reaches the
    ROM. This gate reads the strips it is packed from; the strips->blocks
    pairing is tools/ojz_block_gen.py's and the staleness gate's job.
  * anything about games/demo (it has no collision data at all).

VACUITY: this gate REFUSES TO PASS on an empty population. If it finds no
section files, no non-air cells, or no floor-exposed spans, it exits non-zero
saying so. A green line from this tool always carries the counts it examined, so
"passed because there is nothing there" cannot be mistaken for "passed because
the content is correct" (docs/DEFERRED_WORK.md GATE-VACUITY).

-----------------------------------------------------------------------------
THE BASELINE, AND WHY THERE IS ONE
-----------------------------------------------------------------------------
Both defects are in the tree RIGHT NOW and their repaint is HELD: it lands in
the owner's live editor tree, which no lane may write (see
tools/repaint_ojz_collision.py). A gate that hard-failed every build until the
owner got round to repainting would be switched off within a day, so this one
ratchets instead:

    --baseline FILE   violations recorded in FILE are reported as KNOWN and do
                      not fail. ANY OTHER violation fails the build.

New bad data can therefore never land, while the existing debt stays visible and
countable. A baseline entry that no longer matches anything is reported as STALE
with an instruction to delete it — the file is meant to shrink to empty and then
be removed along with the --baseline flag. Run WITHOUT --baseline to see the
unexempted truth; that is the mode a lane should use.

Exit codes: 0 clean, 1 violations found, 2 could not measure.

Usage:
    python3 tools/collision_consistency.py            # gate: exit 1 on violation
    python3 tools/collision_consistency.py --verbose  # + per-section population
    python3 tools/collision_consistency.py --root DIR # audit another checkout
        (thresholds are derived from THAT tree's engine/system/constants.emp;
         only the strip LAYOUT constants come from this tree's ojz_block_gen)
    python3 tools/collision_consistency.py --baseline tools/collision_baseline.json
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ojz_block_gen  # noqa: E402  (strip layout + parse_strips live there)

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def gen_dir_for(root=None):
    return os.path.join(root or ROOT, "games", "sonic4", "data", "generated",
                        "ojz", "act1")


def coll_dir_for(root=None):
    return os.path.join(root or ROOT, "games", "sonic4", "data", "collision")


def constants_emp_for(root=None):
    return os.path.join(root or ROOT, "engine", "system", "constants.emp")


GEN = gen_dir_for()
COLL = coll_dir_for()
CONSTANTS_EMP = constants_emp_for()

PROFILE_LEN = 16          # height columns per attr (collision_pipeline.PROFILE_LEN)
MAX_ATTRS = 256
CELL_PX_W = 8             # Collision_GetType: lsr.w #3 on X
CELL_PX_H = 16            # Collision_GetType: lsr.w #3 then lsr.w #1 on Y

# See RULE A above: 4 columns = 32 px = two adjacent 16 px shape placements, the
# smallest run that proves a horizontal surface longer than any one shape.
RUN_MIN_COLUMNS = (2 * PROFILE_LEN) // CELL_PX_W


class GateError(Exception):
    """Something could not be MEASURED. Never rendered as 0 or as green."""


# ---------------------------------------------------------------------------
# Constants are DERIVED from the engine source, never copied into this file.
# ---------------------------------------------------------------------------

def read_emp_const(path: str, name: str) -> int:
    """Read `pub const NAME = <int>` out of an .emp module. Loud on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as exc:
        raise GateError(f"cannot read {path} to derive {name}: {exc}") from exc
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*"
                  r"(\$[0-9A-Fa-f]+|\d+)\s*(?://.*)?$", src, re.M)
    if not m:
        raise GateError(
            f"could not find `const {name} = ...` in {path}. This gate DERIVES "
            f"its thresholds from the engine source; it will not fall back to a "
            f"hard-coded value, because a stale copy is exactly how a gate stops "
            f"measuring the thing it names.")
    tok = m.group(1)
    return int(tok[1:], 16) if tok.startswith("$") else int(tok)


def load_attr_tables(coll_dir=None):
    """(heights[256][16], angles[256], solidity[256]) from the interned tables."""
    coll_dir = coll_dir or COLL

    def _read(name, size):
        p = os.path.join(coll_dir, name)
        try:
            with open(p, "rb") as f:
                d = f.read()
        except OSError as exc:
            raise GateError(f"cannot read {p}: {exc}") from exc
        if len(d) != size:
            raise GateError(f"{p} is {len(d)} B, expected {size} B — refusing to "
                            f"guess the layout")
        return d

    hm = _read("heightmaps.bin", MAX_ATTRS * PROFILE_LEN)
    an = _read("angles.bin", MAX_ATTRS)
    so = _read("solidity.bin", MAX_ATTRS)
    heights = [list(hm[i * PROFILE_LEN:(i + 1) * PROFILE_LEN]) for i in range(MAX_ATTRS)]
    return heights, list(an), list(so)


# ---------------------------------------------------------------------------
# Pure predicates (unit-testable without any file I/O)
# ---------------------------------------------------------------------------

def is_full_block(profile) -> bool:
    """Uniformly solid to the top of the cell: zero rise across all columns."""
    return len(profile) == PROFILE_LEN and all(h == PROFILE_LEN for h in profile)


def is_flat_angle(angle: int) -> bool:
    """Angles a flat surface may legitimately carry.

    $00 is flat. Any ODD byte is the 'no usable angle' sentinel and is rejected
    by `btst #0` before it can be used as a direction, so it is never consumed
    as a slope. Everything else is a positive claim of slope.
    """
    return angle == 0 or (angle & 1) == 1


def find_flat_run_violations(coll_rows, heights, angles, solidity, solid_top,
                             run_min=RUN_MIN_COLUMNS):
    """RULE A. coll_rows = [ [attr]*num_cols ] * num_rows for ONE plane.

    Returns (violations, stats). A violation is a dict describing one maximal
    horizontal run of floor-exposed full cells, of at least `run_min` columns,
    in which at least one cell claims an even non-zero angle.
    """
    num_rows = len(coll_rows)
    num_cols = len(coll_rows[0]) if num_rows else 0

    def passes_floor_class(row, col):
        if row < 0 or row >= num_rows or col < 0 or col >= num_cols:
            return False
        a = coll_rows[row][col]
        return a != 0 and bool(solidity[a] & solid_top)

    def floor_exposed_full(row, col):
        a = coll_rows[row][col]
        if a == 0 or not (solidity[a] & solid_top):
            return False
        if not is_full_block(heights[a]):
            return False
        # `.full_back`: the cell above must NOT pass the floor class, or the
        # back cell supplies the angle instead of this one.
        return not passes_floor_class(row - 1, col)

    violations = []
    exposed_cells = 0
    runs = 0
    for row in range(num_rows):
        col = 0
        while col < num_cols:
            if not floor_exposed_full(row, col):
                col += 1
                continue
            start = col
            while col < num_cols and floor_exposed_full(row, col):
                col += 1
            length = col - start
            exposed_cells += length
            runs += 1
            if length < run_min:
                continue
            bad = {}
            for c in range(start, col):
                ang = angles[coll_rows[row][c]]
                if not is_flat_angle(ang):
                    bad.setdefault(ang, []).append(c)
            if bad:
                violations.append({
                    "row": row,
                    "col_start": start,
                    "col_end": col - 1,
                    "columns": length,
                    "width_px": length * CELL_PX_W,
                    "world_y": row * CELL_PX_H,
                    "world_x0": start * CELL_PX_W,
                    "world_x1": col * CELL_PX_W - 1,
                    "angles": {a: len(v) for a, v in sorted(bad.items())},
                    "attrs": sorted({coll_rows[row][c] for c in range(start, col)}),
                })
    return violations, {"exposed_full_cells": exposed_cells, "exposed_runs": runs}


def find_pinhole_violations(coll_rows, heights, solidity, solid_top, min_gap_px):
    """RULE B. Per collision row, rebuild the per-world-pixel floor line the way
    `probe_core` reads it, then report gaps narrower than `min_gap_px` that have
    floor on BOTH sides.

    Returns (violations, stats).
    """
    num_rows = len(coll_rows)
    num_cols = len(coll_rows[0]) if num_rows else 0
    width_px = num_cols * CELL_PX_W

    violations = []
    spans = 0
    floor_px = 0
    for row in range(num_rows):
        # solid[x] — is there floor at world X x in this collision row?
        solid = bytearray(width_px)
        for col in range(num_cols):
            a = coll_rows[row][col]
            if a == 0 or not (solidity[a] & solid_top):
                continue
            prof = heights[a]
            for px in range(col * CELL_PX_W, (col + 1) * CELL_PX_W):
                # probe_core: height column index is the WORLD X pixel & $F
                if prof[px & (PROFILE_LEN - 1)] != 0:
                    solid[px] = 1
        n_solid = sum(solid)
        if n_solid == 0:
            continue
        floor_px += n_solid
        spans += 1
        x = 0
        while x < width_px:
            if solid[x]:
                x += 1
                continue
            gap_start = x
            while x < width_px and not solid[x]:
                x += 1
            gap_len = x - gap_start
            # A gap only counts when it is a HOLE: floor on both sides. A gap
            # running off either end of the section is an ordinary edge.
            if gap_start == 0 or x >= width_px:
                continue
            if gap_len < min_gap_px:
                violations.append({
                    "row": row,
                    "world_y": row * CELL_PX_H,
                    "x_start": gap_start,
                    "x_end": x - 1,
                    "gap_px": gap_len,
                    "attrs": sorted({coll_rows[row][c]
                                     for c in range(gap_start // CELL_PX_W,
                                                    min(num_cols,
                                                        (x - 1) // CELL_PX_W + 1))
                                     if coll_rows[row][c]}),
                })
    return violations, {"floor_rows": spans, "floor_pixels": floor_px}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def enumerate_sections(gen_dir=GEN):
    out = []
    if not os.path.isdir(gen_dir):
        raise GateError(f"generated level tree not found at {gen_dir} — this gate "
                        f"cannot measure anything. Re-bake with "
                        f"tools/regenerate-level.sh.")
    for n in range(64):
        p = os.path.join(gen_dir, f"sec{n}_strips_a.bin")
        if os.path.isfile(p):
            out.append((n, p))
    return out


def check(gen_dir=None, verbose=False, out=sys.stdout, root=None):
    """Run both rules over every committed section and plane.

    `root` points the gate at a different aeon checkout (the owner's live tree,
    say). Thresholds are always derived from THAT tree's engine source, never
    from this one's.

    Returns (violations_a, violations_b, population). Raises GateError when the
    population is empty — an unmeasurable run is never rendered as green.
    """
    gen_dir = gen_dir or gen_dir_for(root)
    solid_top = read_emp_const(constants_emp_for(root), "SOLID_TOP")
    x_radius = read_emp_const(constants_emp_for(root), "PLAYER_X_RADIUS")
    min_gap_px = 2 * x_radius        # the floor sensor pair's separation
    heights, angles, solidity = load_attr_tables(coll_dir_for(root))

    sections = enumerate_sections(gen_dir)
    if not sections:
        raise GateError(
            f"no sec*_strips_a.bin under {gen_dir}: the gate examined ZERO "
            f"collision cells. Refusing to report success on an empty "
            f"population.")

    pop = {"sections": 0, "planes": 0, "cells": 0, "nonair_cells": 0,
           "exposed_full_cells": 0, "exposed_runs": 0,
           "floor_rows": 0, "floor_pixels": 0}
    va, vb = [], []

    for sec, path in sections:
        with open(path, "rb") as f:
            raw = f.read()
        if len(raw) % ojz_block_gen.STRIP_BYTE_SIZE:
            raise GateError(
                f"{path} is {len(raw)} B, not a multiple of "
                f"STRIP_BYTE_SIZE={ojz_block_gen.STRIP_BYTE_SIZE} — refusing to "
                f"guess the strip layout")
        _nt, ca, cb = ojz_block_gen.parse_strips(raw)
        pop["sections"] += 1
        for plane_name, grid in (("A", ca), ("B", cb)):
            pop["planes"] += 1
            pop["cells"] += sum(len(r) for r in grid)
            pop["nonair_cells"] += sum(1 for r in grid for a in r if a)
            ra, sa = find_flat_run_violations(grid, heights, angles, solidity,
                                              solid_top)
            rb, sb = find_pinhole_violations(grid, heights, solidity, solid_top,
                                             min_gap_px)
            pop["exposed_full_cells"] += sa["exposed_full_cells"]
            pop["exposed_runs"] += sa["exposed_runs"]
            pop["floor_rows"] += sb["floor_rows"]
            pop["floor_pixels"] += sb["floor_pixels"]
            for v in ra:
                v.update(section=sec, plane=plane_name)
                va.append(v)
            for v in rb:
                v.update(section=sec, plane=plane_name)
                vb.append(v)
            if verbose:
                print(f"  sec{sec} plane {plane_name}: "
                      f"{sum(1 for r in grid for a in r if a)} non-air cells, "
                      f"{sa['exposed_runs']} floor-exposed full runs "
                      f"({sa['exposed_full_cells']} cells), "
                      f"{sb['floor_rows']} rows with floor "
                      f"({sb['floor_pixels']} floor px)", file=out)

    # VACUITY guards — each names the rule it would have made meaningless.
    if pop["nonair_cells"] == 0:
        raise GateError(
            f"{pop['sections']} section(s) examined but ZERO non-air collision "
            f"cells. Both rules would pass vacuously. Refusing.")
    if pop["exposed_full_cells"] == 0 and pop["floor_pixels"] == 0:
        raise GateError(
            f"{pop['nonair_cells']} non-air cells but no floor-class surface at "
            f"all: RULE A and RULE B both had nothing to examine. Refusing.")
    return va, vb, pop


def violation_key(v, rule):
    """A stable identity for one violation, for baseline matching.

    Deliberately EXCLUDES the attr index: the attr-set is content-addressed and
    re-derived on every bake, so the same bad cell is $02 in one tree and $0E in
    another (see GLIDE_LANDING_ANGLE_DIAGNOSIS.md section 5). Keying on the attr
    would let a re-bake silently un-exempt or re-exempt entries.
    """
    if rule == "A":
        return ["A", v["section"], v["plane"], v["row"], v["col_start"],
                v["col_end"], sorted(v["angles"])]
    return ["B", v["section"], v["plane"], v["row"], v["x_start"], v["gap_px"]]


def load_baseline(path):
    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except OSError as exc:
        raise GateError(f"--baseline {path}: {exc}") from exc
    except ValueError as exc:
        raise GateError(f"--baseline {path} is not valid JSON: {exc}") from exc
    entries = doc.get("known_violations")
    if not isinstance(entries, list):
        raise GateError(f"--baseline {path}: expected a 'known_violations' list")
    return {tuple(map(_hashable, e)) for e in entries}


def _hashable(x):
    return tuple(x) if isinstance(x, list) else x


def main(argv):
    verbose = "--verbose" in argv or "-v" in argv
    root = None
    baseline_path = None
    for i, a in enumerate(argv):
        if a == "--root" and i + 1 < len(argv):
            root = argv[i + 1]
        elif a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--baseline" and i + 1 < len(argv):
            baseline_path = argv[i + 1]
        elif a.startswith("--baseline="):
            baseline_path = a.split("=", 1)[1]
    try:
        baseline = load_baseline(baseline_path) if baseline_path else set()
        va, vb, pop = check(verbose=verbose, root=root)
    except GateError as exc:
        print("=" * 78)
        print("COLLISION CONSISTENCY GATE: COULD NOT MEASURE")
        print(exc)
        print("=" * 78)
        return 2

    print(f"Collision consistency: {pop['sections']} section(s) x "
          f"{pop['planes'] // max(pop['sections'], 1)} planes, "
          f"{pop['cells']} cells ({pop['nonair_cells']} non-air); "
          f"RULE A examined {pop['exposed_runs']} floor-exposed full runs "
          f"({pop['exposed_full_cells']} cells), "
          f"RULE B examined {pop['floor_rows']} rows carrying floor "
          f"({pop['floor_pixels']} floor px).")

    # Split into exempted (baseline) and new. Only NEW violations fail.
    seen = set()
    known_a, known_b = [], []
    if baseline:
        kept_a, kept_b = [], []
        for v in va:
            k = tuple(map(_hashable, violation_key(v, "A")))
            (known_a if k in baseline else kept_a).append(v)
            seen.add(k)
        for v in vb:
            k = tuple(map(_hashable, violation_key(v, "B")))
            (known_b if k in baseline else kept_b).append(v)
            seen.add(k)
        va, vb = kept_a, kept_b
        n_known = len(known_a) + len(known_b)
        if n_known:
            print(f"Collision consistency: {n_known} KNOWN violation(s) exempted "
                  f"by {baseline_path} (rule A {len(known_a)}, rule B "
                  f"{len(known_b)}) — held repaint, see "
                  f"tools/repaint_ojz_collision.py")
        stale = baseline - seen
        if stale:
            print(f"Collision consistency: {len(stale)} baseline entr(ies) no "
                  f"longer match anything — DELETE them from {baseline_path} so "
                  f"the ratchet tightens:")
            for k in sorted(stale, key=str):
                print(f"    stale: {list(k)}")

    if not va and not vb:
        print("Collision consistency: OK (rule A: 0 new violations, "
              "rule B: 0 new violations)")
        return 0

    print("=" * 78)
    print("COLLISION CONSISTENCY GATE FAILED")
    if va:
        print()
        print(f"RULE A — {len(va)} flat run(s) claim a slope they do not have.")
        print("  A run of floor-exposed FULL blocks is a horizontal surface; a")
        print("  horizontal surface has slope 0. An even non-zero angle byte on")
        print("  such a cell is installed verbatim by Glide_Collide and pushes the")
        print("  player sideways forever (docs/GLIDE_LANDING_ANGLE_DIAGNOSIS.md).")
        for v in va:
            angs = ", ".join(f"${a:02X} x{n}" for a, n in v["angles"].items())
            print(f"    sec{v['section']} plane {v['plane']} row {v['row']} "
                  f"(world y={v['world_y']}): cols {v['col_start']}..{v['col_end']} "
                  f"= {v['width_px']} px of flat floor (world x "
                  f"{v['world_x0']}..{v['world_x1']}) carrying angle {angs}; "
                  f"attrs {[f'${a:02X}' for a in v['attrs']]}")
        print("  FIX: repaint with a full block whose angle is flat ($00) or the")
        print("  odd 'no usable angle' sentinel — S&K base shape 255 (angle $FF).")
        print("  NOT shape 251: it is also all-16 but carries angle $E0.")
    if vb:
        print()
        print(f"RULE B — {len(vb)} pinhole(s) in the floor.")
        print("  A gap narrower than the floor sensor pair separation cannot be")
        print("  fallen into and cannot detach a standing player, but the")
        print("  single-point ledge probe DOES see it and reports a false ledge")
        print("  (docs/2026-08-28-ojz-act1-floor-collision-defects.md).")
        for v in vb[:40]:
            print(f"    sec{v['section']} plane {v['plane']} row {v['row']} "
                  f"(world y={v['world_y']}): {v['gap_px']} px gap at world x "
                  f"{v['x_start']}..{v['x_end']}; attrs "
                  f"{[f'${a:02X}' for a in v['attrs']]}")
        if len(vb) > 40:
            print(f"    ... and {len(vb) - 40} more")
        print("  FIX: repaint the offending cells with an all-16 shape (S&K 255).")
    print("=" * 78)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
