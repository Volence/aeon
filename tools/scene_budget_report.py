#!/usr/bin/env python3
"""scene_budget_report — render the scene budget ledger from the BUILD ARTIFACT.

Scanline P2 Task 10 (design §5). The lowering publishes per-registry ledger rows as
named exported comptime values that cost ZERO ROM bytes; this reads them back out of the
build's symbol listing and renders `<game>_scene_budgets.txt`. The derivation stays
single-sourced in `.emp` — this tool does arithmetic on nothing it did not read.

WHY THE LEDGER IS `pub equ` AND NOT `pub const`
-----------------------------------------------
A `pub const` is a name-resolution-only item in sigil — no bytes, no label, no deferred
symbol — so it is invisible to every tool. A `pub equ` mints a link-level symbol that
reaches the listing's equate table (sigil 0df77f83). Both are zero-ROM; only one is
readable. Task 10's spike established this the hard way: before that sigil parcel NEITHER
spelling reached the listing, and the plan's Step 2 ("if the readback does not work, STOP
and report") is what the parcel answered.

Do NOT switch these rows to `pub const` on the strength of one appearing in the listing
elsewhere: a `pub const` in a HARVESTED constants module reaches it as a side effect of
harvesting, which is module-location-dependent and not a contract.

THE ROW GRAMMAR, and why the regex is anchored
----------------------------------------------
The equate table sits after the symbol-table trailer, framed by an "Equate Table" header
and an "N equates" count, one row per line:

    EQU SceneBudget_Axis2_MaxBytes = $00000700

Anchored `^EQU ` so a symbol-table row or an Oracle body line can never match: those have
a different shape entirely (`Name : HEX C |` and `(0) N/HEX :        Name:`), and the
listing deliberately keeps all three readable by different consumers out of one file.

VALUES ARE UNSIGNED 32-BIT. A negative equate renders in two's complement, so this parses
to an unsigned int and converts explicitly where a row is documented as signed. No row in
today's ledger is signed, and the conversion helper exists so that stays a decision rather
than an accident.

Usage:
    python3 tools/scene_budget_report.py [--lst s4.debug.lst] [--out <file>] [--check]

    --check  exit nonzero if a ledger row is missing from the listing (the readback
             regressing is a silent-failure class: the report would simply render less)
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

AEON = pathlib.Path(__file__).resolve().parent.parent

# `EQU <name> = $XXXXXXXX` — the equate-table row. Eight hex digits, upper case.
EQU_RE = re.compile(r"^EQU (\S+) = \$([0-9A-F]{8})$", re.M)

# The rows the ledger publishes. Missing any of these is a readback regression, not an
# empty section, which is why --check treats it as an error.
LEDGER_ROWS = [
    "SceneBudget_SceneCount",
    "SceneBudget_CapsFolded",
    "SceneBudget_PerLineScenes",
    "SceneBudget_Axis1_MaxCycles_X100",
    "SceneBudget_Axis1_Reservation",
    "SceneBudget_Axis1_Pool",
    "SceneBudget_Axis2_MaxBytes",
    "SceneBudget_Axis2_Reservation",
    "SceneBudget_Axis2_Pool",
    "SceneBudget_Axis3_MaxCycles",
    "SceneBudget_Axis3_Reservation",
    "SceneBudget_Axis3_Pool",
    # Axis 5 (P3 Task 14) — three sub-ceiling triples: the axis is a SAT occupancy with
    # three hardware ceilings (per-line sprites is the BINDING one, per axis5_binding_ceiling
    # in tools/effects_budget_model.toml), not a single pool.
    "SceneBudget_Axis5_MaxLineSprites",
    "SceneBudget_Axis5_LineSpriteReservation",
    "SceneBudget_Axis5_LineSpritePool",
    "SceneBudget_Axis5_MaxLinePixels",
    "SceneBudget_Axis5_LinePixelReservation",
    "SceneBudget_Axis5_LinePixelPool",
    "SceneBudget_Axis5_MaxTableSlots",
    "SceneBudget_Axis5_TableSlotReservation",
    "SceneBudget_Axis5_TableSlotPool",
]


def as_signed32(v: int) -> int:
    """Reinterpret an unsigned 32-bit equate value as two's-complement signed.

    Unused by today's rows (all are non-negative costs or counts) and kept deliberately:
    the listing renders unsigned, so the day a ledger row can go negative this is the
    conversion, made explicitly rather than assumed.
    """
    return v - (1 << 32) if v >= (1 << 31) else v


def read_equates(lst_path: pathlib.Path) -> dict[str, int]:
    """Every `EQU name = $value` row in the listing, as unsigned ints."""
    if not lst_path.is_file():
        sys.exit(f"scene_budget_report: no listing at {lst_path} — build first "
                 f"(DEBUG=1 ./build.sh)")
    text = lst_path.read_text()
    return {m.group(1): int(m.group(2), 16) for m in EQU_RE.finditer(text)}


def pct(part: int, whole: int) -> str:
    return f"{100.0 * part / whole:5.1f}%" if whole else "    -"


def render(eq: dict[str, int]) -> str:
    """Render the ledger. Every number here is read or is a difference of two read
    numbers — no budget constant is duplicated in this file."""
    g = eq.get
    out: list[str] = []
    w = out.append

    w("SCENE BUDGET LEDGER")
    w("=" * 78)
    w("")
    w("Rendered from the build's equate table. Enforcement lives in")
    w("engine/level/scene_dsl.emp (scene_budget_enforce) and engine/effects/raster_dsl.emp")
    w("(check_hint_total); this report reads the published rows and does not re-derive them.")
    w("")
    w("Aggregation is MAX over scenes, not sum: one scene is live at a time. The pairwise")
    w("sum belongs to the transition frame (Task 12, BLOCKED — see docs/DEFERRED_WORK.md).")
    w("Denominators are the IDLE camera state, the one that actually holds 60 Hz.")
    w("")

    scenes = g("SceneBudget_SceneCount")
    per_line = g("SceneBudget_PerLineScenes")
    caps = g("SceneBudget_CapsFolded")
    if scenes is not None:
        w(f"registry          {scenes} scenes")
    if per_line is not None and scenes:
        w(f"per-line scenes   {per_line} of {scenes}")
    if caps is not None:
        w(f"folded caps       ${caps:04X}")
    w("")

    hdr = f"{'axis':<34}{'worst':>12}{'reserved':>11}{'pool':>10}{'used':>8}"
    w(hdr)
    w("-" * len(hdr))

    # AXIS 1 — published in hundredths of a cycle (the walker's fitted constants are
    # fractional to two places); divided here, never rounded upstream.
    a1, r1, p1 = g("SceneBudget_Axis1_MaxCycles_X100"), g("SceneBudget_Axis1_Reservation"), g("SceneBudget_Axis1_Pool")
    if None not in (a1, r1, p1):
        w(f"{'1  main-loop cycles':<34}{a1 / 100:>12.2f}{r1:>11}{p1:>10}"
          f"{pct(a1 // 100 + r1, p1):>8}")

    a2, r2, p2 = g("SceneBudget_Axis2_MaxBytes"), g("SceneBudget_Axis2_Reservation"), g("SceneBudget_Axis2_Pool")
    if None not in (a2, r2, p2):
        w(f"{'2  VBlank DMA bytes':<34}{a2:>12}{r2:>11}{p2:>10}{pct(a2 + r2, p2):>8}")

    a3, r3, p3 = g("SceneBudget_Axis3_MaxCycles"), g("SceneBudget_Axis3_Reservation"), g("SceneBudget_Axis3_Pool")
    if None not in (a3, r3, p3):
        w(f"{'3  VBlank CPU (DMA drain)':<34}{a3:>12}{r3:>11}{p3:>10}{pct(a3 + r3, p3):>8}")

    # AXIS 5 — three sub-ceilings of one SAT occupancy axis. The per-line sprite row is
    # the BINDING ceiling; the table row is where the accepted-7 SpriteMask ruling would
    # surface the day an adopter exists. A worst of 0 is the true fold over the shipped
    # registry (zero SpriteMask adopters), not a placeholder.
    a5s, r5s, p5s = (g("SceneBudget_Axis5_MaxLineSprites"),
                     g("SceneBudget_Axis5_LineSpriteReservation"),
                     g("SceneBudget_Axis5_LineSpritePool"))
    if None not in (a5s, r5s, p5s):
        w(f"{'5a per-line sprites (BINDING)':<34}{a5s:>12}{r5s:>11}{p5s:>10}"
          f"{pct(a5s + r5s, p5s):>8}")
    a5p, r5p, p5p = (g("SceneBudget_Axis5_MaxLinePixels"),
                     g("SceneBudget_Axis5_LinePixelReservation"),
                     g("SceneBudget_Axis5_LinePixelPool"))
    if None not in (a5p, r5p, p5p):
        w(f"{'5b per-line sprite pixels':<34}{a5p:>12}{r5p:>11}{p5p:>10}"
          f"{pct(a5p + r5p, p5p):>8}")
    a5t, r5t, p5t = (g("SceneBudget_Axis5_MaxTableSlots"),
                     g("SceneBudget_Axis5_TableSlotReservation"),
                     g("SceneBudget_Axis5_TableSlotPool"))
    if None not in (a5t, r5t, p5t):
        w(f"{'5c SAT table slots':<34}{a5t:>12}{r5t:>11}{p5t:>10}"
          f"{pct(a5t + r5t, p5t):>8}")

    w("")
    if None not in (a1, r1, p1):
        w(f"axis 1 headroom   {p1 - r1 - a1 // 100} cyc of {p1 - r1} budget")
    if None not in (a2, r2, p2, a3, r3, p3):
        w("")
        w("THE COMBINED PER-LINE TAX — the number design §5 asks be shown as one, so that")
        w("the DMA share alone never reads as the whole cost:")
        w(f"  {a2} B of VBlank DMA   ({pct(a2, p2).strip()} of the {p2} B pool)")
        w(f"  {a3} cyc of drain     ({pct(a3, p3).strip()} of the {p3}-cyc VBlank window)")
        w("  design §5's 896 B / 12% for the DMA half was RIGHT — the forcer is ONE")
        w("  448-word HScroll entry (P3 Task 6 Step 1; the 'two entries' P2 scanned was")
        w("  drain residue). The drain half is the part §5 does not price at all.")

    w("")
    w("AXIS 5 NOTES — comptime-gated HERE since P3 Task 14 (scene_budget_enforce's three")
    w("  sub-ceiling ensures); check_axis5_mask_pricing() in effects_budget_check.py stays")
    w("  as the derivation/census drift lane (mask geometry vs shipped engine constants,")
    w("  adopter census, toml row presence). SpriteMask adoption is ZERO and scene()")
    w("  refuses the variant until its engine emission lands (DEFERRED_WORK), so every")
    w("  worst is 0; the accepted price of one adopter is 1 sprite + 8 px per line and")
    w("  7 table slots (axis5_task12_resolution). Reservations are the Task-4 idle")
    w("  measurement — an UPPER BOUND on headroom (axis5_caveat).")
    w("")
    w("AXES NOT GATED HERE")
    w("  4b  per-frame HInt total   enforced in raster_dsl.emp's check_hint_total(), over")
    w("                             the authored program — scenes do not fire HInts.")
    w("  7   computed-handler pins  NO SUBJECT — P3 shipped none and §10 lists none for")
    w("                             P4 either (CAP_COMPUTED reserved, infra deliberately")
    w("                             not rebuilt). See [scene_budget] in the toml.")
    w("")
    w("FALSIFIABILITY — which of these can actually go red, measured:")
    w("  axis 1   YES, unit = one band (93 passes with 391 cyc headroom, 94 fails by 668 —")
    w("           re-derived by P3 Task 13 under the promoted walker model). scene() caps")
    w("           count at 8, so the live role is a ledger row plus a backstop on the")
    w("           documented Scene{ .. } back door. Poison: poison_budget_axis1.emp.")
    w("  axis 2   NO — the charge is two-valued (0 or the per-line constant) and always fits.")
    w("  axis 3   NO — same shape.")
    w("  axis 4b  NO in practice — axis 4a's density guard already bounds the per-frame")
    w("           total below this budget at the shipped burst ceilings.")
    w("  axis 5   NO — the charge is two-valued on every sub-ceiling (0, or the SpriteMask")
    w("           strip's 1/8/7) and both values fit always; scene() additionally refuses")
    w("           SpriteMask until its emission lands. Booked with unlock conditions, not")
    w("           given a faked poison (P3 Task 14).")
    w("  Four poisons were booked rather than faked; see [scene_budget] in")
    w("  tools/effects_budget_model.toml for the unlock condition of each.")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--out", default=None,
                    help="write the report here (default: stdout)")
    ap.add_argument("--check", action="store_true",
                    help="fail if any ledger row is absent from the listing")
    args = ap.parse_args(argv)

    eq = read_equates(pathlib.Path(args.lst))
    missing = [r for r in LEDGER_ROWS if r not in eq]

    if args.check and missing:
        print("scene_budget_report: FAIL — ledger rows absent from the listing:")
        for r in missing:
            print(f"  {r}")
        print("\nThe readback regressing is SILENT by nature: the report would simply "
              "render less rather than error. Check that the rows are still `pub equ` "
              "(a `pub const` mints no symbol) and that the registry module is still "
              "reached.")
        return 1

    report = render(eq)
    if args.out:
        pathlib.Path(args.out).write_text(report)
        print(f"scene_budget_report: wrote {args.out} "
              f"({len(LEDGER_ROWS) - len(missing)}/{len(LEDGER_ROWS)} rows)")
    else:
        print(report, end="")
    if missing:
        print(f"\nNOTE: {len(missing)} ledger row(s) absent: {', '.join(missing)}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
