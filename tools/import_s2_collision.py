#!/usr/bin/env python3
"""Import Sonic 2's collision shape set as a SECOND base bank, beside S&K's.

Sibling of `tools/import_sk_collision.py`, for the S2-COMPRESSED-ACT showcase act
(`docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 4). It reads the
donor's per-column VERTICAL height array plus its angle table, REGENERATES the
rotated (wall-probe) twin, and writes the five ROM-shaped tables to

    games/sonic4/data/collision/base_s2/{heightmaps,heightmaps_rot,angles,
                                         solidity,crossover}.bin

WHY A SECOND BANK AND NOT THE S&K ONE. Of the 151 distinct collision shapes the six
showcase zones actually reference, **68 are unreachable from the S&K bank's shapes
even allowing all four flips** (re-derived 2026-09-17, `check reach`; the design's
prose said 75, which does not reproduce — see the parcel report). S2 geometry cannot
be expressed in S&K's vocabulary, so it gets its own bank.

WHY THE ROTATED TABLE IS REGENERATED AND NEVER COPIED. S2 and aeon use OPPOSITE
sign conventions for the anchor of a partial-width wall row:

    S2   (s2.asm FindWall2, loc_1EA78/loc_1EAE0):  +w = run touches the RIGHT edge
                                                   -w = run touches the LEFT edge
    aeon (probe_core/Collision_ProbeLeft/Right,
          games/sonic4/player/player_sensors.emp): +w = run touches the LEFT edge
                                                   -w = run touches the RIGHT edge

Copying S2's `Collision array - Horizontal.bin` in would mirror the solid side of
every partial wall row: a wall solid on the left of a cell would push from the
right. Measured over the donor bank: of 256 shapes, **211 disagree with
`collision_pipeline.rotate_profile`, every one of them a pure sign disagreement**
(1,519 rows S2-positive where aeon wants negative, 139 the other way); the 44 that
agree are exactly the shapes whose rows are only 0 and 16, i.e. the values that
carry no sign. Decoded to solid-column sets, the two conventions describe the SAME
geometry on 4,080 of 4,080 rows — so this is a pure transcription, not a fidelity
loss. `check sign` re-derives all of that.

The same sign confusion is live and PRE-EXISTING in `import_sk_collision.py`, which
copies S&K's rotated table verbatim into `base/`. It does not reach the ROM (the bake
regenerates the live table via `collision_pipeline.emit_tables`, and `load_base_bank`
reads only heightmaps + angles), and it is NOT this tool's to fix.

THE `$18` RULING. Aeon's rotated table stores ONE signed byte per row, so it can name
a solid run only by an edge anchor plus a width. Shape `$18` is a symmetric 45-degree
PEAK, and its upper 14 rows have a CENTRED run touching neither edge — unrepresentable.
`collision_pipeline.rotate_profile` raises for it, and it is the only shape in the S2
bank that does (the S&K bank has none). RULED: **preserve the run's width and anchor it
at the RIGHT edge**, `(256 - w) & 0xFF`.

  * It is what Sonic 2 itself shipped. S2's own `Collision array - Horizontal.bin`
    row for `$18` is [2,2,4,4,6,6,8,8,10,10,12,12,14,14,16,16] — the run WIDTH at each
    row, positive, which in S2's convention means right-anchored. Translated into
    aeon's inverted convention that is exactly the bytes this rule produces, and
    `test_shape_18_ruling_reproduces_the_donors_own_answer` asserts that equality
    rather than a hand-typed pin. It is the only evidence of intent that exists.
  * It keeps an invariant BOTH donors satisfy with zero exceptions (measured: 0 rows
    in either donor's bank are vertically covered but zero in its rotated array).
    Emitting 0 — the alternative considered first, and rejected on this measurement —
    would make aeon's the only bank of the three where a wall probe sees air through
    solid geometry.
  * The cost is bounded and local: the run keeps its width, only its anchor moves,
    and `$18` is referenced by NONE of the six showcase zones (`check reach` prints
    this), so no clip this act can cut is affected either way.

A row with MULTIPLE solid runs still raises. There is no defensible single byte for
one, the S2 bank contains none, and a silent answer there would be a fabrication.

WHAT THIS TOOL DELIBERATELY DOES NOT DO. It never writes `games/sonic4/data/collision/`
or `.../collision/base/` — the shipping act's tables and the S&K bank are untouched,
and the output directory is a separate `base_s2/`. It emits no per-cell collision:
turning a clip into `section_N.collattr.bin` is §10 row 5. And `ojz_strip_gen
.load_base_bank()` still hard-codes `base/` — teaching the bake to select a bank is
row 5's first move, not this parcel's.

    python3 tools/import_s2_collision.py build [outdir]
    python3 tools/import_s2_collision.py check          # every falsifiable check
    python3 tools/import_s2_collision.py check reach|sign|roundtrip|findfloor
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import collision_pipeline as CP  # noqa: E402
import s2_donor  # noqa: E402

SHAPES, ROW, SOLID_ALL = 256, 16, 3   # s4 solidity: 0 none, 1 top, 2 sides-bottom, 3 all

#: The six zones of the showcase act. HPZ exists only in the prototype donor.
SHOWCASE_ZONES: tuple = (
    ("EHZ", s2_donor.S2_FINAL),
    ("CPZ", s2_donor.S2_FINAL),
    ("OOZ", s2_donor.S2_FINAL),
    ("MTZ", s2_donor.S2_FINAL),
    ("WFZ", s2_donor.S2_FINAL),
    ("HPZ", s2_donor.S2_PROTOTYPE),
)


def default_out() -> str:
    """The bank's output directory, resolved AT CALL TIME.

    A module-level constant here would bind the repo root at import time, which is
    the defect parcel 3 shipped twice (a default bound at import cannot be redirected
    by a test that has already imported the module). Every default in this file is a
    function for that reason.
    """
    return os.path.normpath(
        os.path.join(HERE, "..", "games", "sonic4", "data", "collision", "base_s2"))


def default_donor() -> str:
    return s2_donor.S2_FINAL


# ---------------------------------------------------------------------------
# The rotated table, regenerated — with the neither-edge ruling
# ---------------------------------------------------------------------------

def rotate_row_ruled(heights: bytes, row: int) -> tuple[int, bool]:
    """One row of the rotated profile, plus whether the `$18` ruling was applied.

    Returns (byte, ruled). `ruled` is True only for a single solid run that touches
    NEITHER edge, where the value is the run's width anchored at the RIGHT edge (see
    the module docstring). A row with multiple runs raises, as `rotate_profile` does.
    """
    solid = [CP.covers(heights[col], row) for col in range(CP.PROFILE_LEN)]
    if not any(solid):
        return 0, False
    if all(solid):
        return 16, False

    runs = []
    start = None
    for col, s in enumerate(solid + [False]):
        if s and start is None:
            start = col
        elif not s and start is not None:
            runs.append((start, col - start))
            start = None
    if len(runs) > 1:
        raise ValueError(
            f"rotate_row_ruled: row {row} has {len(runs)} solid runs "
            f"(heights={list(heights)}); there is no single-byte answer and the S2 "
            f"bank contains no such row — this needs a ruling, not a default")

    start, width = runs[0]
    if start == 0:
        return width, False                          # left-anchored: positive
    if start + width == CP.PROFILE_LEN:
        return (256 - width) & 0xFF, False           # right-anchored: negative
    return (256 - width) & 0xFF, True                # centred: RULED right-anchored


def rotate_profile_ruled(heights: bytes) -> tuple[bytes, list[int]]:
    """(rotated 16 bytes, the row indices where the ruling fired).

    SELF-CHECKING: when no row needed the ruling the result must equal
    `collision_pipeline.rotate_profile` exactly. That assert is what keeps this from
    becoming a silent fork of the shared convention — the two can only disagree where
    the shared one refuses to answer at all.
    """
    out = bytearray(CP.PROFILE_LEN)
    ruled: list[int] = []
    for row in range(CP.PROFILE_LEN):
        out[row], was_ruled = rotate_row_ruled(heights, row)
        if was_ruled:
            ruled.append(row)
    result = bytes(out)
    if not ruled:
        assert result == CP.rotate_profile(heights), (
            "rotate_profile_ruled diverged from collision_pipeline.rotate_profile on a "
            f"shape that needed no ruling: heights={list(heights)}")
    return result, ruled


# ---------------------------------------------------------------------------
# The import
# ---------------------------------------------------------------------------

def _write_tables(out_dir, hm, hr, an, sol):
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "heightmaps.bin"), "wb").write(hm)
    open(os.path.join(out_dir, "heightmaps_rot.bin"), "wb").write(hr)
    open(os.path.join(out_dir, "angles.bin"), "wb").write(an)
    open(os.path.join(out_dir, "solidity.bin"), "wb").write(bytes(sol))
    # crossover.bin — the 5th table, addressed by the same attr byte as solidity.bin.
    # A shape VOCABULARY has no cell words behind it, so every slot is XOVER_NONE.
    # Written anyway so the set of five is never short a file (same reasoning as
    # import_sk_collision.py).
    open(os.path.join(out_dir, "crossover.bin"), "wb").write(bytes(SHAPES))


def build(out=None, donor=None, quiet=False) -> dict:
    """Import S2's vertical array + angles as a base bank. Returns a summary dict.

    `out` and `donor` are PARAMETERS with call-time defaults, for the reason
    import_sk_collision.build() states: a caller that only wants to CHECK the
    importer must be able to redirect it, or the check dirties tracked build inputs.
    """
    out = default_out() if out is None else out
    donor = default_donor() if donor is None else donor

    hm, an = s2_donor.collision_arrays(donor, "vertical")
    assert len(hm) == SHAPES * ROW and len(an) == SHAPES  # collision_arrays checks too

    hr = bytearray(SHAPES * ROW)
    sol = bytearray(SHAPES)
    ruled: dict[int, list[int]] = {}
    for i in range(SHAPES):
        shape = hm[i * ROW:(i + 1) * ROW]
        sol[i] = 0 if (i == 0 or not any(shape)) else SOLID_ALL
        rot, rows = rotate_profile_ruled(shape)
        hr[i * ROW:(i + 1) * ROW] = rot
        if rows:
            ruled[i] = rows

    _write_tables(out, hm, bytes(hr), an, sol)

    n = sum(1 for i in range(SHAPES) if any(hm[i * ROW:(i + 1) * ROW]))
    summary = {"out": out, "donor": donor, "solid_shapes": n, "ruled": ruled}
    if not quiet:
        print(f"Imported {n} Sonic 2 collision shapes from {donor} -> {out}")
        print(f"  heightmaps.bin     {len(hm)} B  (donor vertical array, verbatim)")
        print(f"  heightmaps_rot.bin {len(hr)} B  (REGENERATED — never copied; see the "
              f"module docstring)")
        print(f"  angles.bin         {len(an)} B  · solidity.bin {SHAPES} B "
              f"(all 'all' but air) · crossover.bin {SHAPES} B (all NONE)")
        if ruled:
            print(f"  RULING APPLIED to {len(ruled)} shape(s) with a centred solid run:")
            for i, rows in sorted(ruled.items()):
                print(f"    ${i:02X}: rows {rows} anchored RIGHT at the run's own width")
        else:
            print("  no shape needed the centred-run ruling")
    return summary


# ---------------------------------------------------------------------------
# S2's own lookup, transcribed — the reference the checks measure against
# ---------------------------------------------------------------------------
#
# `s2.asm:43030 FindFloor2` and its caller `s2.asm:42942 FindFloor`, line for line, so
# the equivalence check compares against the DONOR'S ARITHMETIC rather than against a
# restatement of aeon's. No ROM is run: this is the re-implementation the parcel brief
# calls for in place of an emulator.

AIR_FWD, FULL_BACK, SURFACE = "air-probe-forward", "full-probe-back", "surface"


#: S2's `top_solid_bit` / `lrb_solid_bit` (s2.constants.asm:70-71, set to $C/$D for
#: path A at s2.asm:33737 and $E/$F for path B) paired with the class mask aeon's
#: probe_core ANDs against SolidityTable for the same sensor. Bit $C (value 1 in the
#: 2-bit field) is TOP, bit $D (value 2) is L/R/B — which is also what
#: collision_pipeline's SOL_TOP/SOL_LRB mean, so the pairing is a transcription.
SENSOR_CLASSES = (("top", 12, CP.SOL_TOP), ("lrb", 13, CP.SOL_LRB))


def s2_find_floor(word: int, index: bytes, vert: bytes, angles: bytes,
                  x: int, y: int, solid_bit: int = 12) -> tuple:
    """S2's FindFloor classification of ONE 16x16 block. Returns (kind, h, angle, dist).

    `word` is the chunk-entry word, `x`/`y` the probe position in pixels, `solid_bit`
    the bit FindFloor's `btst d5,d4` tests ($C = path-A top, $D = path-A L/R/B,
    $E/$F = path B). `dist` is S2's own `d1` and is meaningful only for SURFACE.

    The three kinds are S2's own three exits, and they are the three probe_core has:
      AIR_FWD    loc_1E7E2 — nothing here, evaluate the cell one step FORWARD
      FULL_BACK  loc_1E86A — solid through, evaluate the cell one step BACK
      SURFACE    the fallthrough — the surface is in this cell, d1 = $F - (sub + h)
    """
    block = word & 0x3FF
    if block == 0 or not (word >> solid_bit) & 1:
        return (AIR_FWD, 0, None, None)
    col_id = index[block] if block < len(index) else 0
    if col_id == 0:
        return (AIR_FWD, 0, None, None)

    angle = angles[col_id]
    d1 = x
    if word & 0x400:                       # btst #$A — X flip
        d1 = ~d1                           # not.w d1
        angle = (-angle) & 0xFF            # neg.b (a4)
    if word & 0x800:                       # btst #$B — Y flip
        angle = (-((angle + 0x40) & 0xFF) - 0x40) & 0xFF   # +$40 ; neg ; -$40

    h = vert[col_id * ROW + (d1 & 0xF)]
    h = h - 256 if h >= 0x80 else h         # ext.w of the byte
    if word & 0x800:
        h = -h                              # neg.w d0, after `eor.w d6,d4`

    if h == 0:
        return (AIR_FWD, 0, angle, None)
    sub = y & 0xF
    if h < 0:                               # bmi — hanging run
        if sub + h >= 0:                    # bpl loc_1E7E2 — not embedded
            return (AIR_FWD, h, angle, None)
        return (FULL_BACK, h, angle, None)  # embedded -> loc_1E86A
    if h == 16:                             # cmpi.b #$10 ; beq loc_1E86A
        return (FULL_BACK, h, angle, None)
    return (SURFACE, h, angle, 0xF - (sub + h))


def aeon_probe_cell(word: int, index: bytes, vert: bytes, angles: bytes,
                    x: int, y: int, attrset=None, class_mask: int = CP.SOL_TOP) -> tuple:
    """The same block through AEON's path: bake_cell -> attr -> the tables probe_core
    reads. Returns (kind, h, angle, dist) in the same three kinds.

    This is `collision_pipeline.bake_cell` for the interning, then the arithmetic of
    `probe_core`'s `.cell` + primary-cell exits (games/sonic4/player/player_sensors.emp):
    0 -> .empty_fwd, 16 -> .full_back, hanging embedded -> 16 -> .full_back, else
    dist = 16 - h - sub.

    `class_mask` is probe_core's `d6`, and the `and.b d6,d0 / beq .cl_air` against
    SolidityTable is NOT optional here. bake_cell interns a cell whose solidity is
    non-zero for EITHER class, because the runtime — not the bake — decides which
    sensor is asking. Omitting the gate made this function answer FULL_BACK for
    158,442 of 1,806,336 probes where S2 answers air, all of them L/R/B-only cells
    read by a floor sensor. That was a defect in the CHECK, not in the bank.
    """
    attrset = CP.AttrSet() if attrset is None else attrset
    attr_a, _ = CP.bake_cell(word, index, index, vert, angles, attrset)
    if attr_a == 0:
        return (AIR_FWD, 0, None, None)
    heights, angle, sol, _xo = attrset.entries[attr_a]
    if not sol & class_mask:                 # and.b d6,d0 ; beq .cl_air
        return (AIR_FWD, 0, None, None)

    h = heights[x & 0xF]
    h = h - 256 if h >= 0x80 else h          # ext.w
    if h == 0:
        return (AIR_FWD, 0, angle, None)
    sub = y & 0xF
    if h < 0:                                # bmi .cl_hanging
        if sub + h >= 0:                     # bpl .cl_air
            return (AIR_FWD, h, angle, None)
        return (FULL_BACK, 16, angle, None)  # moveq #16,d0 -> .full_back
    if h == 16:
        return (FULL_BACK, 16, angle, None)
    return (SURFACE, h, angle, 16 - h - sub)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _sk_bank() -> bytes:
    from ojz_common import skdisasm_root
    p = os.path.join(skdisasm_root(), "Levels", "Misc", "Height Maps.bin")
    with open(p, "rb") as f:
        return f.read()


def _flip_closure(bank: bytes) -> set:
    """Every height profile in `bank` under all four flips."""
    out = set()
    for i in range(SHAPES):
        p = bytes(bank[i * ROW:(i + 1) * ROW])
        if not any(p):
            continue
        fx = bytes(CP.flip_profile_x(p))
        fy = bytes(CP.flip_profile_y(p))
        out.update((p, fx, fy, bytes(CP.flip_profile_x(CP.flip_profile_y(p)))))
    return out


def shapes_used(zones=None) -> dict:
    """{shape id: [zone names]} over the showcase zones' own collision indices."""
    used: dict[int, list[str]] = {}
    for zone, donor in (SHOWCASE_ZONES if zones is None else zones):
        _chunks, _grid, ia, ib = s2_donor.collision_inputs(zone, donor)
        for s in sorted((set(ia) | set(ib)) - {0}):
            used.setdefault(s, []).append(zone)
    return used


def check_reach(donor=None) -> dict:
    """§1.3 item 2, re-derived: how many shapes the act needs that S&K cannot express."""
    donor = default_donor() if donor is None else donor
    vert, _ = s2_donor.collision_arrays(donor, "vertical")
    closure = _flip_closure(_sk_bank())
    used = shapes_used()
    missing = [i for i in sorted(used)
               if bytes(vert[i * ROW:(i + 1) * ROW]) not in closure]
    return {"used": len(used), "unreachable": len(missing), "missing": missing,
            "closure": len(closure), "shape_18_used_by": used.get(0x18, [])}


def check_sign(donor=None) -> dict:
    """§1.3 item 3, re-derived: rotate_profile vs the donor's shipped rotated array.

    Also decodes BOTH to solid-column sets and compares each against the vertical
    array's own coverage — the constructive form, which shows the disagreement is a
    convention and not a geometry difference.
    """
    donor = default_donor() if donor is None else donor
    vert, _ = s2_donor.collision_arrays(donor, "vertical")
    horiz, _ = s2_donor.collision_arrays(donor, "horizontal")

    def dec(byte, s2_convention):
        if byte == 0:
            return frozenset()
        if byte == 16:
            return frozenset(range(ROW))
        if byte < 0x80:
            w, right = byte, s2_convention
        else:
            w, right = 256 - byte, not s2_convention
        return frozenset(range(ROW - w, ROW) if right else range(0, w))

    same = differ = sign_only = other = 0
    pos_to_neg = neg_to_pos = 0
    ruled_shapes: dict[int, list[int]] = {}
    rows_agree = rows_disagree = 0
    truth_mismatch: list = []
    for i in range(SHAPES):
        v = bytes(vert[i * ROW:(i + 1) * ROW])
        h = bytes(horiz[i * ROW:(i + 1) * ROW])
        r, ruled = rotate_profile_ruled(v)
        if ruled:
            ruled_shapes[i] = ruled
        if r == h:
            same += 1
        else:
            differ += 1
            pure = all(r[k] == h[k] or (h[k] != 0 and r[k] == ((256 - h[k]) & 0xFF))
                       for k in range(ROW))
            if pure:
                sign_only += 1
            else:
                other += 1
            for k in range(ROW):
                if r[k] == h[k]:
                    continue
                if h[k] < 0x80 <= r[k]:
                    pos_to_neg += 1
                elif r[k] < 0x80 <= h[k]:
                    neg_to_pos += 1
        if not any(v):
            continue
        for k in range(ROW):
            t = frozenset(c for c in range(ROW) if CP.covers(v[c], k))
            a, s = dec(r[k], False), dec(h[k], True)
            if a == s:
                rows_agree += 1
            else:
                rows_disagree += 1
            if i not in ruled_shapes:
                if a != t:
                    truth_mismatch.append(("aeon", i, k))
                if s != t:
                    truth_mismatch.append(("s2", i, k))
    return {"identical": same, "differ": differ, "pure_sign": sign_only,
            "other": other, "s2_pos_aeon_neg": pos_to_neg,
            "s2_neg_aeon_pos": neg_to_pos, "ruled": ruled_shapes,
            "rows_agree": rows_agree, "rows_disagree": rows_disagree,
            "truth_mismatch": truth_mismatch}


def check_roundtrip(out=None, donor=None) -> dict:
    """§10 row 4, half one: all 256 shapes round-trip with no raise.

    Reads the BANK THIS TOOL WROTE (not the in-memory profile) so the check measures
    the artifact, and re-derives every rotated row from heightmaps.bin.
    """
    out = default_out() if out is None else out
    donor = default_donor() if donor is None else donor
    with open(os.path.join(out, "heightmaps.bin"), "rb") as f:
        hm = f.read()
    with open(os.path.join(out, "heightmaps_rot.bin"), "rb") as f:
        hr = f.read()
    with open(os.path.join(out, "angles.bin"), "rb") as f:
        an = f.read()
    vert, ang = s2_donor.collision_arrays(donor, "vertical")
    assert hm == vert, "heightmaps.bin is not the donor's vertical array"
    assert an == ang, "angles.bin is not the donor's angle table"

    ok = raised = ruled = 0
    bad = []
    for i in range(SHAPES):
        shape = hm[i * ROW:(i + 1) * ROW]
        try:
            rot, rows = rotate_profile_ruled(shape)
        except ValueError as e:
            raised += 1
            bad.append((i, str(e)))
            continue
        if rot != hr[i * ROW:(i + 1) * ROW]:
            bad.append((i, "the written rotated row is not what the rule produces"))
            continue
        ok += 1
        if rows:
            ruled += 1
    return {"shapes": SHAPES, "ok": ok, "raised": raised, "ruled": ruled, "bad": bad}


def check_findfloor(donor=None, zones=None, limit_words=None) -> dict:
    """§10 row 4, half two: aeon's baked height and angle against S2's own FindFloor.

    Exhaustive, not hand-picked: every DISTINCT chunk-entry word every showcase zone's
    chunks contain, crossed with all 16 x and all 16 y sub-positions, for BOTH sensor
    classes (top and L/R/B). For each, S2's transcribed FindFloor and aeon's bake+probe
    must agree on the exit taken and on the angle byte, and where a surface is found
    aeon's distance must be S2's + 1 (the two measure to opposite sides of the boundary
    pixel: S2 `$F - (sub+h)`, aeon `16 - h - sub`).

    Both classes are run because the solidity gate is the one place the two sides can
    agree for the wrong reason: a bank error invisible to a floor sensor on an
    L/R/B-only cell is visible to the wall sensor on the same cell, and vice versa.
    """
    donor = default_donor() if donor is None else donor
    vert, ang = s2_donor.collision_arrays(donor, "vertical")

    tried = kind_bad = angle_bad = dist_bad = 0
    per_kind: dict = {}
    examples = []
    for zone, dn in (SHOWCASE_ZONES if zones is None else zones):
        chunks, _grid, ia, _ib = s2_donor.collision_inputs(zone, dn)
        words = sorted({w for ch in chunks for w in ch})
        if limit_words:
            words = words[:limit_words]
        attrset = CP.AttrSet()
        for label, bit, mask in SENSOR_CLASSES:
            for w in words:
                for x in range(16):
                    for y in range(16):
                        tried += 1
                        s = s2_find_floor(w, ia, vert, ang, x, y, solid_bit=bit)
                        a = aeon_probe_cell(w, ia, vert, ang, x, y, attrset,
                                            class_mask=mask)
                        per_kind[(label, s[0])] = per_kind.get((label, s[0]), 0) + 1
                        if s[0] != a[0]:
                            kind_bad += 1
                            if len(examples) < 5:
                                examples.append((zone, label, hex(w), x, y, "kind", s, a))
                            continue
                        if s[2] != a[2]:
                            angle_bad += 1
                            if len(examples) < 5:
                                examples.append((zone, label, hex(w), x, y, "angle", s, a))
                        if s[0] == SURFACE and a[3] != s[3] + 1:
                            dist_bad += 1
                            if len(examples) < 5:
                                examples.append((zone, label, hex(w), x, y, "dist", s, a))
    return {"probes": tried, "kind_mismatch": kind_bad, "angle_mismatch": angle_bad,
            "dist_mismatch": dist_bad, "examples": examples, "per_kind": per_kind}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_check(which) -> int:
    rc = 0
    if which in ("all", "reach"):
        r = check_reach()
        print(f"[reach] {r['used']} distinct shapes referenced by the six showcase zones; "
              f"S&K flip closure holds {r['closure']} profiles")
        print(f"[reach] UNREACHABLE from S&K even with all four flips: {r['unreachable']}")
        print(f"[reach] shape $18 is referenced by: {r['shape_18_used_by'] or 'NO zone'}")
    if which in ("all", "sign"):
        r = check_sign()
        print(f"[sign] rotate_profile vs the donor's shipped rotated array: "
              f"{r['identical']} identical, {r['differ']} differ "
              f"({r['pure_sign']} pure sign, {r['other']} other)")
        print(f"[sign]   S2 positive where aeon wants negative: {r['s2_pos_aeon_neg']} rows; "
              f"the other way: {r['s2_neg_aeon_pos']} rows")
        print(f"[sign] decoded to solid-column sets: {r['rows_agree']} rows agree, "
              f"{r['rows_disagree']} disagree; rows disagreeing with the vertical "
              f"array's own coverage: {len(r['truth_mismatch'])}")
        print(f"[sign] shapes needing the centred-run ruling: "
              f"{ {hex(k): v for k, v in r['ruled'].items()} }")
        if r["other"] or r["truth_mismatch"]:
            rc = 1
    if which in ("all", "roundtrip"):
        out = default_out()
        if not os.path.isfile(os.path.join(out, "heightmaps.bin")):
            print(f"[roundtrip] no bank at {out}; run `build` first")
            rc = 1
        else:
            r = check_roundtrip()
            print(f"[roundtrip] {r['ok']}/{r['shapes']} shapes round-trip with no raise "
                  f"({r['ruled']} via the centred-run ruling); raised: {r['raised']}")
            if r["bad"]:
                rc = 1
                for i, why in r["bad"][:5]:
                    print(f"[roundtrip]   ${i:02X}: {why}")
    if which in ("all", "findfloor"):
        r = check_findfloor()
        print(f"[findfloor] {r['probes']} probes (every distinct chunk word of all six "
              f"zones x 16 x-sub x 16 y-sub x both sensor classes) against S2's own "
              f"FindFloor")
        pop = ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(r["per_kind"].items()))
        print(f"[findfloor]   population (S2's exit): {pop}")
        print(f"[findfloor]   exit-kind mismatches {r['kind_mismatch']} · angle "
              f"{r['angle_mismatch']} · distance (aeon == S2+1) {r['dist_mismatch']}")
        if r["kind_mismatch"] or r["angle_mismatch"] or r["dist_mismatch"]:
            rc = 1
            for e in r["examples"]:
                print(f"[findfloor]   {e}")
    return rc


def main(argv) -> int:
    mode = argv[1] if len(argv) > 1 else "build"
    if mode == "build":
        build(argv[2] if len(argv) > 2 else None)
        return 0
    if mode == "check":
        return _cli_check(argv[2] if len(argv) > 2 else "all")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
