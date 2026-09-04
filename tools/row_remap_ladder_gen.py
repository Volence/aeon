#!/usr/bin/env python3
"""row_remap_ladder_gen — THE row-remap ladder generator (EFFECTS-W1 item 9, parcel 9b).

A ladder is `(H+1)` rows of `H` bytes. Row `r` is selected each frame as `r = H - |p|`,
where `p` is the perspective quantity — the separation, in screen lines, between the
BACKGROUND's image of the water surface and the FOREGROUND's truth about it. Screen line
`i` of the band takes the plane-B scroll word that belonged to line `ladder[r][i]`.

WHAT THIS FILE IS FOR. `engine/level/parallax_dsl.emp` carries `row_remap_ladder16()`, one
instantiation of this model at one hard-coded height, because an `.emp` `comptime fn` must
return a CONCRETE array type and so cannot take H as an argument. Its own banner says so and
hands the parameterisation to this parcel. This module is that parameterisation: one place
the model is written down, callable at every band height the runtime can express, and the
thing `tools/test_row_remap_ladder_gen.py` and `tools/row_remap_gate.py` both check against.

THE MODEL, and it is CHOSEN rather than fitted — booked, not smuggled:

    entry(H, r, i) = i + (i*i*p) // (H * (H-1)),   p = H - r

`extra` is quadratic in the output line and linear in the separation: the resampling step
grows smoothly from 1 line at the surface to 2 lines at the far end, and the whole family
scales with `|p|`. Every property the runtime depends on falls out of the algebra rather
than out of a table anybody inspected:

  entry[i] >= i          trivially, `extra >= 0`.
  strictly increasing    `(i+1)^2 > i^2`, so the floor term never decreases and the leading
                         `i` supplies +1. (Stronger than the non-decreasing the runtime
                         needs, and that is deliberate: see the "REPEATS" note below.)
  entry[i] <= 2i         `extra <= i^2*H / (H*(H-1)) = i^2/(H-1)`, and with `i <= H-1`,
                         `i^2 <= (H-1)*i < (H-1)*(i+1)`, so `floor(i^2/(H-1)) <= i`.
  row H is the identity  `p = 0` kills the whole `extra` term.
  row 0 saturates        at `i = H-1`, `p = H`: `extra = (H-1)^2*H / (H*(H-1)) = H-1`
                         exactly, so `entry[H-1] = 2(H-1)` — the read bound, reached and
                         not crossed.
  monotone in r          `p` decreases as `r` increases and `extra` is linear in `p`.

THE u8 CEILING IS DERIVED, NOT PREFERRED. The ladder is emitted as `[u8]` and the largest
entry any row produces is the saturating `2*(H-1)`, so `2*(H-1) <= 255` bounds `H <= 128`.
`MAX_H` below is computed from that inequality rather than typed, so widening the ladder to
`u16` is a one-line change here and the gate re-derives with it.

⚠ S3K's OWN TABLES CANNOT BE USED DIRECTLY, AND THAT SETTLES THE DESIGN'S OPEN QUESTION 5.
The design (§ open question 5) left "fit S3K's shipped 97x96 table instead of generating
one" as a legitimate cheap alternative and gave this parcel the job of settling it.
MEASURED HERE, by decoding both donor files (`--donor`, 2026-09-04):

    HCZ Waterline Scroll Data.bin   9,312 B = 97 x 96   (H+1)xH: YES
    LBZ Waterline Scroll Data.bin   4,160 B = 65 x 64   (H+1)xH: YES
      entry[i] >= i        0 violations in either file
      non-decreasing       0 violations in either file
      entry[i] <= 2i       5,871 of 9,312 violated (HCZ) · 2,603 of 4,160 (LBZ)

The first two invariants hold in the donor. THE THIRD DOES NOT, and not marginally — it is
violated by 63% of HCZ's entries. The reason is structural, not a defect in S3K: their table
indexes a **192-row source image** and the selected row is a 96-row WINDOW into it, so their
row 96 is `96..191` (an identity shifted by a whole band) and their row 0 is the plain
identity. Aeon's rows run the OTHER WAY — `r = H - |p|` makes row H the identity — and
aeon's pass permutes the band's OWN longwords in place, which is what `entry[i] <= 2i` pays
for. Importing S3K's bytes would need a 2H-line source the pass does not have and would
break the bound `Parallax_Fill_PerLine` caps its run at span/2 on.

So: the donor table is a decoding target and a shape witness, NOT a drop-in. `--donor` is
kept for exactly that — re-deriving the numbers above rather than trusting this banner.

REPEATS, AND WHY THE MODEL DOES NOT PRODUCE THEM. The runtime needs non-decreasing; this
model gives strictly increasing, so no source line is ever shown TWICE. S3K's shipped table
does the same (design §1.2's own step histograms — row 10 = 84x1, 10x2, 1x87 — contain no
zero step), so this is not a divergence from the donor, and a gate written to design §9.2's
"a repeat adjacent to a skip" tell would pass vacuously on both. That correction is already
booked in docs/DEFERRED_WORK.md's 9a block; it is restated here because this is the file
somebody would change the model in.

WHAT THIS DOES NOT DO. It does not write into the tree. `--emit emp` prints `.emp` source
for a `row_remap_ladder<H>()` to stdout for a human to paste and review; nothing in build.sh
regenerates `parallax_dsl.emp` from here. A generator that silently rewrote a checked-in
engine source would make the gate's subject and the gate's oracle the same file.

USAGE
    row_remap_ladder_gen.py --height 16 --emit text
    row_remap_ladder_gen.py --height 32 --emit emp
    row_remap_ladder_gen.py --height 16 --emit bin --out ladder16.bin
    row_remap_ladder_gen.py --check                     # every expressible H
    row_remap_ladder_gen.py --donor "$AEON_SKDISASM_DIR/Levels/HCZ/Misc/HCZ Waterline Scroll Data.bin" --donor-height 96
"""
from __future__ import annotations

import argparse
import os
import sys

EXIT_OK, EXIT_FAIL = 0, 1

#: The ladder's element type, as declared in engine/level/parallax_dsl.emp.
ENTRY_MAX = 255

#: The smallest usable band height. The model divides by `H - 1`, and a one-line band has no
#: interior to resample.
MIN_H = 2


def _derive_max_h() -> int:
    """The largest power-of-two H whose ladder still fits the element type.

    The saturating entry is `2*(H-1)` (row 0, i = H-1), so the constraint is
    `2*(H-1) <= ENTRY_MAX`. Computed, never typed: at ENTRY_MAX = 255 this is 128."""
    h = MIN_H
    while 2 * (2 * h - 1) <= ENTRY_MAX:
        h *= 2
    return h


#: Derived, see _derive_max_h.
MAX_H = _derive_max_h()


def expressible_heights() -> list[int]:
    """Every band height a `band_remap` record can NAME.

    `brm_hshift` (engine/level/parallax.emp) is a byte consumed as `H = 1 << brm_hshift`, so
    the expressible set is the powers of two — from MIN_H up to the derived MAX_H."""
    out, h = [], MIN_H
    while h <= MAX_H:
        out.append(h)
        h *= 2
    return out


def _validate_height(H: int) -> None:
    if not isinstance(H, int) or isinstance(H, bool):
        raise TypeError(f"band height must be an int, got {H!r}")
    if H < MIN_H:
        raise ValueError(
            f"band height {H} is below MIN_H = {MIN_H}: the model divides by H-1, and a "
            f"one-line band has no interior to resample.")
    if H & (H - 1):
        raise ValueError(
            f"band height {H} is not a power of two. `band_remap.brm_hshift` is consumed as "
            f"`H = 1 << brm_hshift`, so a non-power-of-two ladder is a table no band record "
            f"can name — bytes in the ROM that nothing indexes.")
    if H > MAX_H:
        raise ValueError(
            f"band height {H} exceeds MAX_H = {MAX_H}. The ladder is emitted as bytes and "
            f"this model's largest entry is the saturating 2*(H-1) = {2 * (H - 1)}, which "
            f"does not fit {ENTRY_MAX}. Raising this needs a wider ladder element in "
            f"engine/level/parallax.emp and in the pass that indexes it, not a bigger "
            f"constant here.")


def entry(H: int, r: int, i: int) -> int:
    """One ladder entry. `r` is the selected row (0 .. H), `i` the output line (0 .. H-1)."""
    p = H - r
    return i + (i * i * p) // (H * (H - 1))


def ladder(H: int) -> bytes:
    """The whole `(H+1) x H` table, row-major, ready to emit."""
    _validate_height(H)
    return bytes(entry(H, k // H, k % H) for k in range(H * (H + 1)))


# ------------------------------------------------------------------ self-check (the model)


def check(H: int) -> list[str]:
    """Re-derive every property the runtime depends on, on the produced bytes.

    This duplicates `tools/test_row_remap_ladder_gen.py` on purpose and the duplication is
    not waste: the pytest gate is what a build runs, and this is what somebody typing
    `--height 96` at a prompt gets told before they paste anything into an engine source."""
    bad = []
    tab = ladder(H)
    if len(tab) != (H + 1) * H:
        return [f"H={H}: produced {len(tab)} bytes, not (H+1)*H = {(H + 1) * H}"]
    rows = [list(tab[r * H:(r + 1) * H]) for r in range(H + 1)]
    for r, row in enumerate(rows):
        prev = -1
        for i, v in enumerate(row):
            if v > ENTRY_MAX:
                bad.append(f"H={H} row {r} entry {i} = {v} does not fit the element type")
            if v < i:
                bad.append(f"H={H} row {r} entry {i} = {v} < i (in-place forward permute)")
            if v > 2 * i:
                bad.append(f"H={H} row {r} entry {i} = {v} > 2i (read bound)")
            if v < prev:
                bad.append(f"H={H} row {r} entry {i} = {v} descends from {prev}")
            prev = v
        if bad:
            break
    if rows[H] != list(range(H)):
        bad.append(f"H={H}: row {H} is not the identity — |p| = 0 must be the no-op rung")
    if rows[0][-1] != 2 * (H - 1):
        bad.append(f"H={H}: row 0's last entry is {rows[0][-1]}, not the saturating "
                   f"{2 * (H - 1)}")
    for i in range(H):
        col = [rows[r][i] for r in range(H + 1)]
        if any(col[r] < col[r + 1] for r in range(H)):
            bad.append(f"H={H}: column {i} is not non-increasing in r — more separation must "
                       f"compress at least as hard")
            break
    if all(rows[r] == list(range(H)) for r in range(H)):
        bad.append(f"H={H}: every row is the identity — the pass would write the buffer back "
                   f"unchanged")
    return bad


def describe(H: int) -> list[str]:
    tab = ladder(H)
    rows = [list(tab[r * H:(r + 1) * H]) for r in range(H + 1)]
    moved = sum(1 for r in range(H) if rows[r] != list(range(H)))
    return [
        f"H = {H}: {H + 1} rows x {H} bytes = {len(tab)} B",
        f"  rows differing from the identity : {moved} of {H} "
        f"(row {H} is the identity by construction and is exempt)",
        f"  row 0    (|p| = {H}, max) tail    : {rows[0][-min(8, H):]}",
        f"  row {H:<4} (|p| = 0)  tail        : {rows[H][-min(8, H):]}   (the identity)",
        f"  largest entry                    : {max(tab)}  (bound is 2*(H-1) = {2 * (H - 1)})",
    ]


# --------------------------------------------------------------------------- emitters


def emit_emp(H: int) -> str:
    tab = ladder(H)
    lines = [
        f"// GENERATED by tools/row_remap_ladder_gen.py --height {H} --emit emp.",
        f"// Regenerate rather than hand-edit; tools/test_row_remap_ladder_gen.py checks the",
        f"// model's properties and tools/row_remap_gate.py re-checks the linked bytes.",
        f"pub const ROW_REMAP_H{H} = {H}",
        "",
        f"comptime fn row_remap_entry{H}(k: int) -> int {{",
        f"    let r = k / ROW_REMAP_H{H}",
        f"    let i = k % ROW_REMAP_H{H}",
        f"    let p = ROW_REMAP_H{H} - r",
        f"    return i + ((i * i * p) / (ROW_REMAP_H{H} * (ROW_REMAP_H{H} - 1)))",
        "}",
        "",
        f"pub comptime fn row_remap_ladder{H}() -> [u8; {len(tab)}] {{",
        f"    return comptime for k in 0..{len(tab)} {{ row_remap_entry{H}(k) }}",
        "}",
    ]
    return "\n".join(lines) + "\n"


def emit_text(H: int) -> str:
    tab = ladder(H)
    out = []
    for r in range(H + 1):
        row = list(tab[r * H:(r + 1) * H])
        out.append(f"row {r:>4} |p|={H - r:>4}: " + " ".join(f"{v:>3}" for v in row))
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- donor


def donor_report(path: str, H: int) -> tuple[list[str], bool]:
    """Decode an S3K waterline table and re-derive its properties.

    Kept so the "S3K's bytes are not a drop-in" ruling in this file's banner can be
    RE-MEASURED rather than believed. It returns (lines, usable_as_is)."""
    if not os.path.isfile(path):
        return ([f"donor: {path} does not exist"], False)
    b = open(path, "rb").read()
    lines = [f"donor: {os.path.basename(path)}  {len(b)} B, asked to read as {H}-wide rows"]
    if H < 2 or len(b) % H:
        lines.append(f"  NOT a whole number of {H}-byte rows — the height is wrong")
        return (lines, False)
    rows = len(b) // H
    lines.append(f"  {rows} rows x {H} = {len(b)} B · (H+1)xH identity: "
                 f"{'YES' if rows == H + 1 else f'NO (expected {H + 1} rows)'}")
    v_ge = v_mono = v_bound = 0
    for r in range(rows):
        row = b[r * H:(r + 1) * H]
        prev = -1
        for i, v in enumerate(row):
            if v < i:
                v_ge += 1
            if v < prev:
                v_mono += 1
            if v > 2 * i:
                v_bound += 1
            prev = v
    lines.append(f"  entry[i] >= i      : {v_ge} violation(s)")
    lines.append(f"  non-decreasing     : {v_mono} violation(s)")
    lines.append(f"  entry[i] <= 2i     : {v_bound} violation(s) of {len(b)} entries")
    lines.append(f"  row 0    head      : {list(b[0:8])}")
    lines.append(f"  row {rows - 1:<4} head      : {list(b[(rows - 1) * H:(rows - 1) * H + 8])}")
    usable = (v_ge == 0 and v_mono == 0 and v_bound == 0 and rows == H + 1)
    if not usable:
        lines.append("  VERDICT: NOT usable as an aeon ladder as-is.")
        if v_bound:
            lines.append("    The read bound is what fails. S3K indexes a 2H-row SOURCE image "
                         "and selects an H-row window into it (their row H is the identity "
                         "shifted by a whole band); aeon's pass permutes the band's own "
                         "longwords in place and caps its run at span/2 on `entry[i] <= 2i`.")
    else:
        lines.append("  VERDICT: satisfies all three invariants at this height.")
    return (lines, usable)


# ------------------------------------------------------------------------------ cli


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--height", type=int,
                    help=f"band height H; a power of two in {MIN_H}..{MAX_H}")
    ap.add_argument("--emit", choices=("emp", "bin", "text"), default=None,
                    help="emit the ladder: `emp` source, raw `bin`, or a readable `text` dump")
    ap.add_argument("--out", help="write the emission here instead of stdout")
    ap.add_argument("--check", action="store_true",
                    help="re-derive every property at every expressible H (or at --height)")
    ap.add_argument("--donor", help="decode an S3K waterline table and report its properties")
    ap.add_argument("--donor-height", type=int, default=96,
                    help="row width to read the donor as (HCZ 96, LBZ 64)")
    a = ap.parse_args(argv)

    rc = EXIT_OK

    if a.donor:
        lines, _ = donor_report(a.donor, a.donor_height)
        print("\n".join(lines))

    if a.check or (not a.emit and not a.donor):
        heights = [a.height] if a.height else expressible_heights()
        print(f"row_remap_ladder_gen: MAX_H = {MAX_H} (derived from 2*(H-1) <= {ENTRY_MAX}), "
              f"expressible heights {expressible_heights()}")
        for H in heights:
            try:
                bad = check(H)
            except (ValueError, TypeError) as exc:
                print(f"  H={H}: REFUSED — {exc}")
                rc = EXIT_FAIL
                continue
            for ln in describe(H):
                print("  " + ln)
            if bad:
                rc = EXIT_FAIL
                for ln in bad:
                    print("  FAIL " + ln)
            else:
                print(f"    all properties hold at H = {H}")

    if a.emit:
        if not a.height:
            print("--emit needs --height", file=sys.stderr)
            return EXIT_FAIL
        try:
            if a.emit == "bin":
                blob = ladder(a.height)
                if a.out:
                    open(a.out, "wb").write(blob)
                else:
                    sys.stdout.buffer.write(blob)
            else:
                text = emit_emp(a.height) if a.emit == "emp" else emit_text(a.height)
                if a.out:
                    open(a.out, "w", encoding="utf-8").write(text)
                else:
                    sys.stdout.write(text)
        except (ValueError, TypeError) as exc:
            print(f"REFUSED — {exc}", file=sys.stderr)
            return EXIT_FAIL

    return rc


if __name__ == "__main__":
    sys.exit(main())
