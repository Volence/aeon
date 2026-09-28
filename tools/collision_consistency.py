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
    ledge probe falls into it and Knuckles teeters on flat ground. (That probe
    was replaced by S3K's centre-plus-sensor rule on 2026-09-27,
    WOVEN-FALSE-BALANCE; RULE B now models the new rule, see below.)

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
  * `Player_AtLedgeEdge` (player_sensors.emp) balances when the floor under the
    CENTRE is at least BALANCE_DROP_MIN below the foot AND one floor sensor
    (x +/- r) finds no surface at all (S3K's Sonic_Balance rule, since
    2026-09-27, WOVEN-FALSE-BALANCE; before that it was a single point at
    x +/- (r+2), which saw a 1 px gap). A gap wide enough to hold the centre
    and a sensor, and deep enough that the sensor's two-cell probe finds
    nothing, IS visible to it.

So for every floor gap narrower than 2 * PLAYER_X_RADIUS the two consumers
disagree about the same data, and the only observable effect is a false ledge —
the teeter-on-flat-ground the owner reported (2026-08-28, under the old probe). A gap that cannot be fallen into
and cannot be seen is not level design; it is an authoring slip. Gaps at or
above the pair separation are real ledges and are left alone.

The per-pixel floor line is reconstructed the way the engine reads it:
`probe_core` indexes the height profile with `andi.w #$F, d0` on the WORLD X
pixel, so world X uses column `x & 15` of the attr found at 8 px column `x >> 3`.

A narrow gap in one row is only a CANDIDATE (refined 2026-09-25, S2CLIP-CPZ-
FURTHER). The harm above needs a standing player whose balance rule reads the
gap, and a one-row scan cannot see whether one can exist: Sonic 2's Chemical
Plant has 34 such candidates, and every one is the floor of an air pocket
sealed inside rock, a notch in the underside of a slab, or an air cell with
solid ground 1 px under it (docs/research/2026-09-25-cpz-floor-gaps.md). None
can make anyone teeter. So a candidate is a VIOLATION only when some position
is (1) STANDING, the floor sensor pair reads distance 0; (2) has ROOM, no
SOLID_LRB pixel in the standing body box; (3) is REACHABLE, its air region (a
cell is open when EITHER plane leaves it open, since a plane switch can be
anywhere) is connected to the section edge; and (4) its centre is over the
gap and the balance rule fires there. The four stages and why every
simplification in them errs toward flagging are spelled out at
`classify_pinhole`. The collision bytes are never changed by this refinement:
it is a change to what the gate calls a defect, not to the data.
BALANCE_DROP_MIN is read from games/sonic4/player/player_sensors.emp,
PLAYER_X_RADIUS, PLAYER_Y_RADIUS and SOLID_LRB from engine/system/constants.emp.

-----------------------------------------------------------------------------
WHAT A GREEN RESULT RULES OUT — AND WHAT IT DOES NOT
-----------------------------------------------------------------------------
Green means: across every committed OJZ act-1 section and BOTH collision planes,
no floor surface that the engine can actually read claims a slope it does not
have (Rule A), and no floor has a hole too narrow for the sensor pair to see
that a reachable standing player's balance rule reads as a ledge (Rule B).

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

-----------------------------------------------------------------------------
THE POST-SIGIL ARM (--rom-tables), GPP-COLLISION-ROM-TABLES 2026-09-28
-----------------------------------------------------------------------------
The rules above grade FILES. Until this arm, nothing tied those files to the
ROM: `pub data AngleTable = _solidity` built and this gate exited 0 (measured,
docs/research/2026-09-26-gate-predicate-audit.md). build.sh now also runs,
after sigil,

    collision_consistency.py --rom-tables --lst s4[.debug].lst --rom s4[.debug].bin
                             --built-after T0

which reads the BUILT image and refuses (exit 1) unless:
  (1) DATA: the bytes at the listing's HeightMaps / AngleTable / SolidityTable
      are heightmaps.bin / angles.bin / solidity.bin, whole;
  (2) READ SITES: Collision_ProbeDown's `.cell` loads each of the three in the
      role the rules model (SolidityTable -> d0 then `and.b d6,d0`, AngleTable
      -> d1, HeightMaps -> d0), exactly once each;
  (3) ODD-ANGLE PREMISE: Player_SensorSurface resolves the odd flag with
      `btst #0,d1` / `bne .substitute` / `.substitute: move.b d3,d1`, the
      fact Rule A's odd-byte exemption stands on.
Exit 2 when it cannot measure (a label, the ROM or a graded file is missing, or
the pair is not fresh). It reads byte patterns, so a re-encoding of the same
behaviour fails closed with the premise named: re-derive, then update the arm.
What it does NOT cover: the odd-flag resolution at the OTHER angle consumers
(Player_SensorWallDir `.resolve`, Glide_Collide) or any future one, the d6 =
SOLID_TOP each floor caller passes, and HeightMapsRot (not graded here). Those
are booked in docs/DEFERRED_WORK.md under GPP-COLLISION-ROM-TABLES.

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
        (--baseline repeats; the union is exempted. An S2CLIP build adds the clip act's
         own games/sonic4/data/clips/<id>/collision_baseline.json when it has one.)
    python3 tools/collision_consistency.py --rom-tables --lst s4.debug.lst \\
            --rom s4.debug.bin [--built-after EPOCH]
        (the post-sigil arm above; exit 0 agree, 1 disagree, 2 could not measure)
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


def player_sensors_emp_for(root=None):
    """Where BALANCE_DROP_MIN lives (Player_AtLedgeEdge)."""
    return os.path.join(root or ROOT, "games", "sonic4", "player",
                        "player_sensors.emp")


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


def dirty_inputs(root=None):
    """Which of the files this gate READ differ from HEAD, as a list of paths.

    WHY THIS EXISTS. A failure here prints coordinates and nothing else, and the
    reader's first move is to look at what LANDED. On 2026-09-10 that cost a
    session a search: the two new violations came from UNCOMMITTED edits to
    section 0's collision in the working tree (last written 05:40Z that morning),
    while the last commit touching the baked file was five days old. Nothing in
    the gate's own output could have told anyone that -- the word "committed"
    appears in this module's prose and means "in-repo, donor-free", not "at HEAD",
    and the test wrapping this gate is named `test_committed_tree_...`, so both
    point a reader at history when the answer is in `git status`.

    Returns (paths, could_tell). `could_tell` is False when git is absent, this is
    not a repo, or the query failed -- because an empty list and a failed lookup are
    the same artifact, and the empty one reads as "your bytes are committed", which
    is the more misleading of the two. Never raises and never blocks a verdict; the
    caller prints this as ADDITIONAL context, never as a finding.
    """
    import subprocess
    base = root or ROOT
    rel = []
    for d in (gen_dir_for(root), coll_dir_for(root)):
        try:
            rel.append(os.path.relpath(d, base))
        except ValueError:
            return [], False
    try:
        out = subprocess.run(["git", "-C", base, "status", "--porcelain", "--", *rel],
                             capture_output=True, text=True, timeout=20)
    except Exception:
        return [], False
    if out.returncode != 0:
        return [], False
    return [ln[3:] for ln in out.stdout.split("\n") if ln.strip()], True


def dirty_note(root=None):
    """One line for a failure message, or "" when there is nothing to say."""
    d, could_tell = dirty_inputs(root)
    if not could_tell:
        return ("\nNOTE: could not determine whether this gate's input files differ "
                "from HEAD (git unavailable, or this is not a repo), so nothing here "
                "says whether the bytes graded above are committed. This is an "
                "UNKNOWN, not a clean tree.")
    if not d:
        return ""
    # Surface the files the RULES actually read first. gen_dir also holds the art
    # pool, which is dirty far more often and is not what either rule grades, so an
    # unsorted sample shows four page blobs and buries the collision file that
    # produced the violation.
    def _rank(path):
        base = os.path.basename(path)
        return (0 if ("strips" in base or "coll" in base) else 1, base)
    d = sorted(d, key=_rank)
    shown = ", ".join(d[:4]) + (f" (+{len(d) - 4} more)" if len(d) > 4 else "")
    return (f"\nNOTE: {len(d)} of this gate's INPUT file(s) differ from HEAD, so the "
            f"bytes graded above are UNCOMMITTED work in this tree and not what "
            f"landed: {shown}. Check `git status` before reading this as a "
            f"regression in committed data.")


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


def read_emp_const_expr(path: str, name: str, names: dict) -> int:
    """Read `const NAME = <expr>` where <expr> is integers, names from `names`
    and + - *, e.g. `REACH = PLAYER_X_RADIUS+2`. Loud on anything
    else: an expression this cannot evaluate is a GateError, never a guess."""
    import ast
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as exc:
        raise GateError(f"cannot read {path} to derive {name}: {exc}") from exc
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*"
                  r"([^/\n]+?)\s*(?://.*)?$", src, re.M)
    if not m:
        raise GateError(f"could not find `const {name} = ...` in {path}; this "
                        f"gate derives its thresholds from source and will not "
                        f"fall back to a copied value.")
    text = re.sub(r"\$([0-9A-Fa-f]+)", lambda mm: str(int(mm.group(1), 16)),
                  m.group(1))

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op,
                                                      (ast.Add, ast.Sub, ast.Mult)):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            return a - b if isinstance(node.op, ast.Sub) else a * b
        raise GateError(f"`const {name} = {m.group(1)}` in {path} is not an "
                        f"expression this gate can evaluate (known names: "
                        f"{sorted(names)}). Refusing to guess.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise GateError(f"`const {name} = {m.group(1)}` in {path}: {exc}") from exc
    return ev(tree)


def ledge_params(root=None):
    """Every threshold RULE B uses, derived from the engine/game source."""
    cpath = constants_emp_for(root)
    p = {n: read_emp_const(cpath, n) for n in
         ("SOLID_TOP", "SOLID_LRB", "PLAYER_X_RADIUS", "PLAYER_Y_RADIUS")}
    spath = player_sensors_emp_for(root)
    p["BALANCE_DROP_MIN"] = read_emp_const_expr(spath, "BALANCE_DROP_MIN", p)
    return p


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
                             run_min=RUN_MIN_COLUMNS, above=None):
    """RULE A. coll_rows = [ [attr]*num_cols ] * num_rows for ONE plane.

    `above` is the SAME plane's bottom collision row of the section directly above
    (None: nothing above, the act's top edge). probe_core's `.full_back` re-probes one
    cell up in WORLD space, so row 0's upper neighbour is that section's last row, not
    air. Reading it as air flagged buried full blocks at every section-row boundary as
    exposed (MEASURED 2026-09-27, the woven clip act s2_mtz_cpz: 4 false runs, section 5
    row 0, each under a solid cell in section 2's last row).

    Returns (violations, stats). A violation is a dict describing one maximal
    horizontal run of floor-exposed full cells, of at least `run_min` columns,
    in which at least one cell claims an even non-zero angle.
    """
    num_rows = len(coll_rows)
    num_cols = len(coll_rows[0]) if num_rows else 0

    def passes_floor_class(row, col):
        if col < 0 or col >= num_cols or row >= num_rows or row < -1:
            return False
        if row == -1:
            if above is None:
                return False
            a = above[col]
        else:
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
# RULE B, second stage: is the candidate EXPOSED to the ledge probe?
#
# `find_pinhole_violations` reads ONE collision row at a time, so it cannot tell
# a hole in open floor from the floor of an air pocket sealed inside rock, from a
# notch in the underside of a slab, or from an air cell with solid ground one
# pixel under it (docs/research/2026-09-25-cpz-floor-gaps.md: all 34 Sonic 2 CPZ
# candidates are one of those three). RULE B's derivation names exactly one
# harm: a standing player's balance rule (`Player_AtLedgeEdge`) reads the gap as
# a ledge. A candidate is therefore a violation only when some position
# satisfies ALL FOUR stages, in this order:
#
#   1. STANDING   the floor sensor pair (x -/+ PLAYER_X_RADIUS at the foot,
#                 `Player_SensorFloor`, closer result wins) reads distance 0, with
#                 `Collision_ProbeDown` emulated as probe_core runs it: primary
#                 cell, ONE cell forward when empty, ONE cell back when full,
#                 hanging runs by the bmi rule. The foot is searched over the gap's
#                 row and the row above it: those are the only primaries whose
#                 single probe can read the gap (a primary two rows up never
#                 reaches it; one row down only looks back into it when full,
#                 which returns <= 0 = supported).
#   2. ROOM       the standing body box, (2*PLAYER_X_RADIUS+1) x (2*PLAYER_Y_RADIUS)
#                 above the foot, holds no SOLID_LRB pixel. Top-only cells do not
#                 block the body (a player jumps up through them).
#   3. REACHABLE  the body's cell lies in an air region connected to the section
#                 edge. A cell is a wall for this flood only when it is a FULL
#                 (every column |h| >= 16) SOLID_LRB cell on BOTH planes: a player
#                 can change planes inside a region (the act's layer-switch lines,
#                 Act.act_layer_lines), and this gate does not read where those
#                 are, so every cell is assumed to be a possible switch. Partial and
#                 sloped cells count as open, and touching the section edge counts
#                 as open because the neighbour section is not read.
#   4. SEEN       the player's CENTRE is on a gap pixel, the centre probe returns
#                 at least BALANCE_DROP_MIN, and one floor sensor (x -/+
#                 PLAYER_X_RADIUS) finds nothing at all (probe_core's `.nothing`,
#                 32 here): the exact test `Player_AtLedgeEdge` makes (S3K's rule,
#                 since WOVEN-FALSE-BALANCE 2026-09-27; until then this stage
#                 modelled the single point at x +/- (r+2), > 8 px).
#
# Every relaxation above (top-only cells never block, partial cells are open, the
# section edge is open, object placement is never credited) finds MORE positions,
# never fewer, so the second stage can only clear a candidate that no player can
# be beside. Thresholds are read from the engine/game source by `check`.
# ---------------------------------------------------------------------------

EXPOSURE_STAGES = ("no_stand", "no_room", "sealed", "ground_within_limit",
                   "exposed")


def _signed(b):
    return b - 256 if b >= 128 else b


class CollisionPlane:
    """Pixel-level reading of ONE plane's collision grid, the way probe_core
    reads it. Anything outside the grid reads as air. `other_rows` is the
    OTHER plane of the same section: the reachability flood treats a cell as
    open when either plane leaves it open (stage 3)."""

    def __init__(self, coll_rows, heights, solidity, other_rows=None):
        self.rows = coll_rows
        self.other = other_rows
        self.nr = len(coll_rows)
        self.nc = len(coll_rows[0]) if self.nr else 0
        self.heights = heights
        self.solidity = solidity
        self._comp = None
        self._open = None

    def attr(self, x, y):
        if x < 0 or y < 0:
            return 0
        col, row = x // CELL_PX_W, y // CELL_PX_H
        if col >= self.nc or row >= self.nr:
            return 0
        return self.rows[row][col]

    def cell_h(self, x, y, mask):
        """probe_core `.cell`: effective height, 0 (air/rejected) .. 16 (full)."""
        a = self.attr(x, y)
        if a == 0 or not (self.solidity[a] & mask):
            return 0
        h = _signed(self.heights[a][x & (PROFILE_LEN - 1)])
        if h == 0:
            return 0
        if h < 0:                  # hanging run: embedded = full, else air
            return PROFILE_LEN if (y & (CELL_PX_H - 1)) + h < 0 else 0
        return min(h, PROFILE_LEN)

    def probe_down(self, x, y, mask):
        """Collision_ProbeDown's returned distance for a probe at (x, y)."""
        sub = y & (CELL_PX_H - 1)
        h = self.cell_h(x, y, mask)
        if h == 0:                                   # `.empty_fwd`
            h2 = self.cell_h(x, y + CELL_PX_H, mask)
            return 32 if h2 == 0 else 32 - h2 - sub  # 32 = `.nothing`
        if h == PROFILE_LEN:                         # `.full_back`
            return -(self.cell_h(x, y - CELL_PX_H, mask) + sub)
        return 16 - h - sub

    def pixel_solid(self, x, y, mask):
        """Is world pixel (x, y) inside a solid shape of this class?"""
        a = self.attr(x, y)
        if a == 0 or not (self.solidity[a] & mask):
            return False
        h = _signed(self.heights[a][x & (PROFILE_LEN - 1)])
        r = y & (CELL_PX_H - 1)
        if h == 0:
            return False
        if abs(h) >= PROFILE_LEN:
            return True
        return r >= PROFILE_LEN - h if h > 0 else r < -h

    def _is_wall(self, row, col, lrb):
        if not self._full_lrb(self.rows, row, col, lrb):
            return False
        return self.other is None or self._full_lrb(self.other, row, col, lrb)

    def _full_lrb(self, grid, row, col, lrb):
        a = grid[row][col]
        if a == 0 or not (self.solidity[a] & lrb):
            return False
        x0 = col * CELL_PX_W
        return all(abs(_signed(self.heights[a][(x0 + i) & (PROFILE_LEN - 1)]))
                   >= PROFILE_LEN for i in range(CELL_PX_W))

    def open_region(self, x, y, lrb):
        """Is the cell holding pixel (x, y) in an air region connected to the
        section edge? Regions are labelled once per plane, on first use."""
        if self._comp is None:
            from collections import deque
            comp = [[-1] * self.nc for _ in range(self.nr)]
            is_open = []
            for r0 in range(self.nr):
                for c0 in range(self.nc):
                    if comp[r0][c0] != -1 or self._is_wall(r0, c0, lrb):
                        continue
                    cid = len(is_open)
                    touches = False
                    comp[r0][c0] = cid
                    q = deque([(r0, c0)])
                    while q:
                        r, c = q.popleft()
                        if r in (0, self.nr - 1) or c in (0, self.nc - 1):
                            touches = True
                        for rr, c2 in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                            if (0 <= rr < self.nr and 0 <= c2 < self.nc
                                    and comp[rr][c2] == -1
                                    and not self._is_wall(rr, c2, lrb)):
                                comp[rr][c2] = cid
                                q.append((rr, c2))
                    is_open.append(touches)
            self._comp, self._open = comp, is_open
        col, row = x // CELL_PX_W, y // CELL_PX_H
        if not (0 <= col < self.nc and 0 <= row < self.nr):
            return True            # outside this section: not read, so open
        cid = self._comp[row][col]
        return cid == -1 or self._open[cid]


def balances(plane, x, foot_y, solid_top, x_radius, drop_min):
    """`Player_AtLedgeEdge`'s terrain rule at a standing position: None when
    supported, else the side ("right"/"left") it turns the player to face.
    Right is asked first, as S3K asks next_tilt first."""
    if plane.probe_down(x, foot_y, solid_top) < drop_min:
        return None
    if plane.probe_down(x + x_radius, foot_y, solid_top) == 32:
        return "right"
    if plane.probe_down(x - x_radius, foot_y, solid_top) == 32:
        return "left"
    return None


def classify_pinhole(plane, v, solid_top, solid_lrb, x_radius, y_radius,
                     drop_min):
    """(stage, witness) for one RULE-B candidate `v` on `plane` (a CollisionPlane).

    `stage` is the furthest of EXPOSURE_STAGES any position reached; only
    "exposed" is a violation. `witness` is (player x, foot y, side) of the
    position that reached it (side = the edge `balances` turns him to face, None
    below the last stage), or None when nothing stood at all.
    """
    row = v["row"]
    best, witness = 0, None
    for x in range(v["x_start"], v["x_end"] + 1):
        for foot_y in range((row - 1) * CELL_PX_H, (row + 1) * CELL_PX_H):
            if min(plane.probe_down(x - x_radius, foot_y, solid_top),
                   plane.probe_down(x + x_radius, foot_y, solid_top)) != 0:
                continue
            if best < 1:
                best, witness = 1, (x, foot_y, None)
            if any(plane.pixel_solid(xx, yy, solid_lrb)
                   for yy in range(foot_y - 2 * y_radius, foot_y)
                   for xx in range(x - x_radius, x + x_radius + 1)):
                continue
            if best < 2:
                best, witness = 2, (x, foot_y, None)
            if not plane.open_region(x, foot_y - 1, solid_lrb):
                continue
            if best < 3:
                best, witness = 3, (x, foot_y, None)
            # SEEN: the gap pixel under the centre is the primary (foot in
            # the gap's row), or the one forward cell of an EMPTY primary
            # (foot in the row above), and the balance rule fires.
            seen = (foot_y // CELL_PX_H == row
                    or plane.cell_h(x, foot_y, solid_top) == 0)
            side = seen and balances(plane, x, foot_y, solid_top, x_radius,
                                     drop_min)
            if side:
                return "exposed", (x, foot_y, side)
    return EXPOSURE_STAGES[best], witness


def find_exposed_pinhole_violations(coll_rows, heights, solidity, solid_top,
                                    solid_lrb, x_radius, y_radius, drop_min,
                                    other_rows=None):
    """RULE B as the gate applies it: the one-row candidates of
    `find_pinhole_violations` (gap < 2 * x_radius, floor both sides), kept only
    when `classify_pinhole` finds a reachable standing position whose balance
    rule reads them as a ledge. `other_rows` is the section's other plane,
    read only by the reachability flood; None floods this plane alone (which
    can only call MORE regions sealed, so every real caller passes it).

    Returns (violations, stats). stats adds the candidate count and how many were
    cleared at each stage, so a green line says what it cleared and why.
    """
    cand, stats = find_pinhole_violations(coll_rows, heights, solidity,
                                          solid_top, 2 * x_radius)
    stats = dict(stats, candidates=len(cand),
                 **{f"cleared_{s}": 0 for s in EXPOSURE_STAGES[:-1]})
    if not cand:
        return [], stats
    plane = CollisionPlane(coll_rows, heights, solidity, other_rows)
    out = []
    for v in cand:
        stage, witness = classify_pinhole(plane, v, solid_top, solid_lrb,
                                          x_radius, y_radius, drop_min)
        if stage == "exposed":
            v["stand"] = witness
            out.append(v)
        else:
            stats[f"cleared_{stage}"] += 1
    return out, stats


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
    lp = ledge_params(root)
    solid_top = lp["SOLID_TOP"]
    heights, angles, solidity = load_attr_tables(coll_dir_for(root))

    sections = enumerate_sections(gen_dir)
    if not sections:
        raise GateError(
            f"no sec*_strips_a.bin under {gen_dir}: the gate examined ZERO "
            f"collision cells. Refusing to report success on an empty "
            f"population.")

    pop = {"sections": 0, "planes": 0, "cells": 0, "nonair_cells": 0,
           "exposed_full_cells": 0, "exposed_runs": 0,
           "floor_rows": 0, "floor_pixels": 0, "candidates": 0,
           **{f"cleared_{s}": 0 for s in EXPOSURE_STAGES[:-1]}}
    va, vb = [], []

    # The section grid's width, so RULE A can read the section ABOVE's last row (see
    # find_flat_run_violations). Read from the tree's own act_grid.emp, as the engine
    # compiles it; a tree without one has no stacking to read across.
    grid_path = os.path.join(gen_dir, "act_grid.emp")
    grid_w = None
    if os.path.isfile(grid_path):
        import act_grid
        grid_w = act_grid.descriptor_grid(grid_path)[0]

    parsed = {}
    for sec, path in sections:
        with open(path, "rb") as f:
            raw = f.read()
        if len(raw) % ojz_block_gen.STRIP_BYTE_SIZE:
            raise GateError(
                f"{path} is {len(raw)} B, not a multiple of "
                f"STRIP_BYTE_SIZE={ojz_block_gen.STRIP_BYTE_SIZE} — refusing to "
                f"guess the strip layout")
        _nt, ca, cb = ojz_block_gen.parse_strips(raw)
        parsed[sec] = {"A": ca, "B": cb}

    for sec, _path in sections:
        ca, cb = parsed[sec]["A"], parsed[sec]["B"]
        up = parsed.get(sec - grid_w) if grid_w and sec >= grid_w else None
        pop["sections"] += 1
        for plane_name, grid in (("A", ca), ("B", cb)):
            pop["planes"] += 1
            pop["cells"] += sum(len(r) for r in grid)
            pop["nonair_cells"] += sum(1 for r in grid for a in r if a)
            ra, sa = find_flat_run_violations(grid, heights, angles, solidity,
                                              solid_top,
                                              above=up[plane_name][-1] if up else None)
            rb, sb = find_exposed_pinhole_violations(
                grid, heights, solidity, solid_top, lp["SOLID_LRB"],
                lp["PLAYER_X_RADIUS"], lp["PLAYER_Y_RADIUS"],
                lp["BALANCE_DROP_MIN"],
                other_rows=cb if plane_name == "A" else ca)
            pop["exposed_full_cells"] += sa["exposed_full_cells"]
            pop["exposed_runs"] += sa["exposed_runs"]
            pop["floor_rows"] += sb["floor_rows"]
            pop["floor_pixels"] += sb["floor_pixels"]
            for k in ["candidates"] + [f"cleared_{s}" for s in EXPOSURE_STAGES[:-1]]:
                pop[k] += sb[k]
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


def load_baselines(paths):
    """The union of several baseline files. build.sh passes the tree's own
    (tools/collision_baseline.json) and, in an S2CLIP build, the clip act's
    (`games/sonic4/data/clips/<id>/collision_baseline.json`): FAITHFUL DONOR DATA the
    gate refuses, declared beside the clip the way its floorless columns are. A clip
    baseline must say why (`why`, non-empty), because an exemption with no reason
    cannot be told from a silenced bug."""
    out = set()
    for p in paths:
        out |= load_baseline(p)
        if os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(p)))) == "clips":
            import json
            with open(p, "r", encoding="utf-8") as f:
                why = json.load(f).get("why")
            if not (isinstance(why, str) and why.strip()):
                raise GateError(f"--baseline {p} is a clip act's baseline with no `why`: "
                                f"say what donor content each entry is and why it ships")
    return out


def _hashable(x):
    return tuple(x) if isinstance(x, list) else x


# ---------------------------------------------------------------------------
# THE POST-SIGIL ARM (--rom-tables): the graded files ARE what the ROM carries
# under the names the engine reads, and the premises Rule A rests on are in the
# emitted code. GPP-COLLISION-ROM-TABLES, 2026-09-28.
# ---------------------------------------------------------------------------
#
# WHY IT EXISTS. Everything above grades three FILES on disk. Measured
# 2026-09-26 (docs/research/2026-09-26-gate-predicate-audit.md, row
# `collision_consistency.py`): `pub data AngleTable = _solidity` in
# games/sonic4/data/collision/collision_data.emp built, and this gate exited 0 —
# both blobs are 256 B, and nothing here ever learned which bytes the label the
# engine reads is bound to. So a green said nothing about the shipped tables.
#
# THE ROLE MAP BELOW IS THE GATE'S OWN MODEL, NOT A COPY OF collision_data.emp.
# It says which graded file plays which role. Deriving it from the `pub data`
# lines would reproduce exactly the mutation this arm exists to catch.
# HeightMapsRot is deliberately absent: the gate does not grade it (see
# "Green does NOT mean" in the module docstring), so this arm does not either.
ROM_TABLE_ROLES = (
    ("HeightMaps", "heightmaps.bin", MAX_ATTRS * PROFILE_LEN),
    ("AngleTable", "angles.bin", MAX_ATTRS),
    ("SolidityTable", "solidity.bin", MAX_ATTRS),
)

# The premises, as 68000 encodings (the arm reads BYTES, so a re-encoding of the
# same behaviour, e.g. pc-relative, fails closed with a message naming the
# premise; that is the intended failure, re-derive the premise and update here).
_LEA_ABS_L_A1 = bytes.fromhex("43F9")          # lea (xxx).l, a1
_MOVEA_L_IMM_A1 = bytes.fromhex("227C")        # movea.l #imm, a1
_MOVE_B_A1_D3W_D0 = bytes.fromhex("10313000")  # move.b (a1,d3.w), d0
_MOVE_B_A1_D3W_D1 = bytes.fromhex("12313000")  # move.b (a1,d3.w), d1
_AND_B_D6_D0 = bytes.fromhex("C006")           # and.b d6, d0
_BTST_0_D1 = bytes.fromhex("08010000")         # btst #0, d1
_MOVE_B_D3_D1 = bytes.fromhex("1203")          # move.b d3, d1


def parse_listing_labels(path):
    """{label: address} for every label row of a sigil listing, locals included
    (`(0) 914/6EE4 :        Collision_ProbeDown:`). Raises GateError when the
    file cannot be read or yields no labels: an empty map is not a pass."""
    rx = re.compile(r"\(\d+\) \d+/([0-9A-Fa-f]+) :\s+(\S+):\s*$")
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                m = rx.match(ln)
                if m:
                    out[m.group(2)] = int(m.group(1), 16)
    except OSError as exc:
        raise GateError(f"cannot read listing {path}: {exc}") from exc
    if not out:
        raise GateError(f"{path} yielded no label rows — not a sigil listing")
    return out


def _span(labels, name):
    """[start, end) of global label `name`: end is the next GLOBAL label (no `$`)
    above it. Raises GateError when the label is absent or is the last one."""
    if name not in labels:
        raise GateError(f"label {name} is not in the listing")
    start = labels[name]
    above = [a for n, a in labels.items() if "$" not in n and a > start]
    if not above:
        raise GateError(f"{name} has no global label after it, so its extent is unknown")
    return start, min(above)


def _local(labels, lo, hi, suffix):
    """The address of the ONE local label ending in `$<suffix>` inside [lo, hi).
    Several or none is a GateError: the premise has no single subject."""
    hits = sorted(a for n, a in labels.items()
                  if n.endswith("$" + suffix) and lo <= a < hi)
    if len(hits) != 1:
        raise GateError(f"expected exactly one local label `.{suffix}` in "
                        f"${lo:X}..${hi:X}, found {len(hits)}")
    return hits[0]


def _next_label(labels, addr):
    above = [a for a in labels.values() if a > addr]
    if not above:
        raise GateError(f"no label after ${addr:X}, so the span is unknown")
    return min(above)


def _count(hay, needle):
    n, i = 0, hay.find(needle)
    while i >= 0:
        n += 1
        i = hay.find(needle, i + 1)
    return n


def check_rom_tables(lst, rom_path, root=None):
    """The post-sigil arm. Returns (problems, facts): each problem is a sentence
    naming what disagrees; `facts` is what was measured, printed on green so a
    pass carries its referents. GateError = could not measure (exit 2)."""
    labels = parse_listing_labels(lst)
    try:
        with open(rom_path, "rb") as fh:
            rom = fh.read()
    except OSError as exc:
        raise GateError(f"cannot read ROM {rom_path}: {exc}") from exc
    coll = coll_dir_for(root)
    problems, facts = [], []

    def u32(a):
        return a.to_bytes(4, "big")

    # (1) DATA: the bytes at each role's label are the graded file, whole.
    for sym, fname, size in ROM_TABLE_ROLES:
        fpath = os.path.join(coll, fname)
        try:
            with open(fpath, "rb") as fh:
                want = fh.read()
        except OSError as exc:
            raise GateError(f"cannot read graded file {fpath}: {exc}") from exc
        if len(want) != size:
            raise GateError(f"{fpath} is {len(want)} B, expected {size} B")
        if sym not in labels:
            raise GateError(f"{sym} is not in {lst}; the engine's read of it has no "
                            f"subject this arm can find")
        addr = labels[sym]
        got = rom[addr:addr + size]
        if len(got) != size:
            raise GateError(f"{rom_path} ends before {sym} ${addr:X} + {size} B")
        if got != want:
            diff = sum(1 for x, y in zip(got, want) if x != y)
            others = [f for _, f, s in ROM_TABLE_ROLES
                      if f != fname and s == size
                      and open(os.path.join(coll, f), "rb").read() == got]
            also = (f"; the ROM bytes there ARE {others[0]}" if others else "")
            problems.append(
                f"DATA: {sym} @ ${addr:X} carries {diff} of {size} bytes that differ "
                f"from the graded {fname}{also}. The rules above graded a file the "
                f"engine does not read under that name (check the `pub data {sym} = ...` "
                f"binding in games/sonic4/data/collision/collision_data.emp)")
        else:
            facts.append(f"{sym} @ ${addr:X} == {fname} ({size} B)")

    # (2) READ SITES: the floor probe core reads each table in the role the rules
    # model. Rule A's class gate is `SolidityTable[attr] & d6`, its angle is
    # `AngleTable[attr]`, and both rules read heights from HeightMaps. Checked in
    # Collision_ProbeDown's `.cell` only: that is the floor probe the rules derive
    # from (the other three cores are ceiling/wall reads the gate does not audit).
    lo, hi = _span(labels, "Collision_ProbeDown")
    cell = _local(labels, lo, hi, "cell")
    cell_end = _next_label(labels, cell)
    body = rom[cell:cell_end]
    sites = (
        ("SolidityTable", _LEA_ABS_L_A1, _MOVE_B_A1_D3W_D0 + _AND_B_D6_D0,
         "lea SolidityTable,a1 / move.b (a1,d3.w),d0 / and.b d6,d0 (the class gate)"),
        ("AngleTable", _LEA_ABS_L_A1, _MOVE_B_A1_D3W_D1,
         "lea AngleTable,a1 / move.b (a1,d3.w),d1 (the raw angle)"),
        ("HeightMaps", _MOVEA_L_IMM_A1, _MOVE_B_A1_D3W_D0,
         "movea.l #HeightMaps,a1 / move.b (a1,d3.w),d0 (the height column)"),
    )
    for sym, op, tail, text in sites:
        n = _count(body, op + u32(labels[sym]) + tail)
        if n != 1:
            problems.append(
                f"READ SITE: Collision_ProbeDown `.cell` (${cell:X}..${cell_end:X}) "
                f"carries {n} copies of `{text}`, expected exactly 1. The rules model "
                f"{sym} in that role; the probe the engine runs does not read it so "
                f"(games/sonic4/player/player_sensors.emp probe_core)")
        else:
            facts.append(f"Collision_ProbeDown.cell reads {sym} as modelled")

    # (3) THE ODD-ANGLE PREMISE: Rule A exempts every odd angle byte because the
    # floor pair tests `btst #0,d1` and substitutes the cardinal before the value
    # is used. Checked in Player_SensorSurface (Player_SensorFloor/Land/Ceiling
    # all resolve there): between `.pair` and `.substitute`, exactly one
    # `btst #0,d1` immediately followed by a `bne` to `.substitute`, whose first
    # instruction is `move.b d3,d1`.
    lo, hi = _span(labels, "Player_SensorSurface")
    pair = _local(labels, lo, hi, "pair")
    sub = _local(labels, lo, hi, "substitute")
    if not pair < sub:
        raise GateError(f"Player_SensorSurface `.pair` ${pair:X} is not before "
                        f"`.substitute` ${sub:X}; the premise's shape moved")
    region = rom[pair:sub]
    hits = []
    i = region.find(_BTST_0_D1)
    while i >= 0:
        at = pair + i + 4
        op = rom[at:at + 4]
        target = None
        if len(op) >= 2 and op[0] == 0x66 and op[1] not in (0x00, 0xFF):
            target = at + 2 + (op[1] - 256 if op[1] >= 128 else op[1])
        elif len(op) == 4 and op[0] == 0x66 and op[1] == 0x00:
            d = int.from_bytes(op[2:4], "big")
            target = at + 2 + (d - 65536 if d >= 32768 else d)
        hits.append((pair + i, target))
        i = region.find(_BTST_0_D1, i + 1)
    good = [h for h in hits if h[1] == sub]
    if len(hits) != 1 or len(good) != 1 or rom[sub:sub + 2] != _MOVE_B_D3_D1:
        problems.append(
            f"ODD-ANGLE PREMISE: Player_SensorSurface ${pair:X}..${sub:X} carries "
            f"{len(hits)} `btst #0,d1` ({len(good)} followed by a bne to `.substitute` "
            f"${sub:X}), and `.substitute` begins {rom[sub:sub + 2].hex().upper()} "
            f"(want 1203, move.b d3,d1). Rule A exempts every ODD angle as 'never "
            f"consumed as an angle'; that is only true while the floor pair resolves "
            f"it. Without this, the exemption hides real slope claims")
    else:
        facts.append(f"Player_SensorSurface btst #0,d1 @ ${good[0][0]:X} -> "
                     f".substitute ${sub:X} (move.b d3,d1)")
    return problems, facts


def rom_tables_main(argv):
    """`--rom-tables --lst L --rom R [--built-after T0] [--root DIR]`.
    Exit 0 agree, 1 disagree, 2 could not measure (incl. a stale pair)."""
    import argparse
    ap = argparse.ArgumentParser(prog="collision_consistency.py --rom-tables")
    ap.add_argument("--rom-tables", action="store_true", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--built-after", type=float, default=None)
    ap.add_argument("--root", default=None)
    a = ap.parse_args(argv)
    if a.built_after is not None:
        import artifact_provenance
        rc = artifact_provenance.gate_check("collision_consistency --rom-tables",
                                            a.rom, a.lst, a.built_after,
                                            expect_game="sonic4")
        if rc:
            return rc
    try:
        problems, facts = check_rom_tables(a.lst, a.rom, root=a.root)
    except GateError as exc:
        print("=" * 78)
        print("COLLISION CONSISTENCY ROM-TABLES ARM: COULD NOT MEASURE")
        print(exc)
        print("=" * 78)
        return 2
    if not problems:
        print(f"Collision consistency (ROM tables, {a.rom}): OK — " + "; ".join(facts))
        return 0
    print("=" * 78)
    print(f"COLLISION CONSISTENCY ROM-TABLES ARM FAILED ({a.rom})")
    print("  The pre-sigil rules graded the files in games/sonic4/data/collision/;")
    print("  this build does not ship them, or read them, the way those rules assume.")
    for p in problems:
        print(f"  * {p}")
    print("=" * 78)
    return 1


def main(argv):
    if "--rom-tables" in argv:
        return rom_tables_main(argv)
    verbose = "--verbose" in argv or "-v" in argv
    root = None
    baseline_paths = []
    for i, a in enumerate(argv):
        if a == "--root" and i + 1 < len(argv):
            root = argv[i + 1]
        elif a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--baseline" and i + 1 < len(argv):
            baseline_paths.append(argv[i + 1])
        elif a.startswith("--baseline="):
            baseline_paths.append(a.split("=", 1)[1])
    baseline_path = " + ".join(baseline_paths)
    try:
        baseline = load_baselines(baseline_paths)
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
    print(f"Collision consistency: RULE B found {pop['candidates']} one-row gap "
          f"candidate(s) and cleared "
          + ", ".join(f"{pop['cleared_' + s]} {s}" for s in EXPOSURE_STAGES[:-1])
          + " (no reachable standing position whose balance rule reads a false "
          "ledge in them).")

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
                  f"{len(known_b)}) — a held repaint (tools/repaint_ojz_collision.py) "
                  f"or a clip act's declared donor data (its collision_baseline.json)")
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
    note = dirty_note(root)
    if note:
        print(note.lstrip("\n"))
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
        print("  balance rule (Player_AtLedgeEdge) DOES see it and teeters")
        print("  (docs/2026-08-28-ojz-act1-floor-collision-defects.md).")
        for v in vb[:40]:
            print(f"    sec{v['section']} plane {v['plane']} row {v['row']} "
                  f"(world y={v['world_y']}): {v['gap_px']} px gap at world x "
                  f"{v['x_start']}..{v['x_end']}; attrs "
                  f"{[f'${a:02X}' for a in v['attrs']]}; a player standing at "
                  f"x={v['stand'][0]} foot y={v['stand'][1]} teeters "
                  f"toward the {v['stand'][2]} on it")
        if len(vb) > 40:
            print(f"    ... and {len(vb) - 40} more")
        print("  FIX: repaint the offending cells with an all-16 shape (S&K 255).")
    print("=" * 78)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
