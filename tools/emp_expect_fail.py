#!/usr/bin/env python3
"""emp_expect_fail — the tree's negative-build lane (Parcel R1, spec §10.4).

Each case is a poison .emp module that MUST fail to build, with the expected guard
message fragment and the expected number of `[Error]` diagnostics. A case passes iff the
build exits nonzero, its output contains the fragment, and the diagnostic count matches.
Poison modules live in games/sonic4/test/poison/: syntactically valid (the manifest scan
parses them on EVERY build), never imported by a real entry, evaluated only by this lane.

BACKEND — `sigil build --extra-entry <module>`
---------------------------------------------
One real build invocation per case, with the poison named as an extra entry:

    sigil build --aeon . --native --game sonic4 -o <scratch>.bin --extra-entry <poison>

`--extra-entry` evaluates the named module inside the REAL build profile — the same
manifest rewrites (`publicize_helper_comptime`, `normalize_helper_imports`) and the same
`-D` interface values — so a poison reaching a guard in `engine/effects/raster_dsl.emp`
resolves the helper vocabulary exactly as an author's module does. The poison's
module-level `ensure`s run because the flag names it, not because anything imports it:
no file's body is rewritten, and the tree is never left in a state that must be restored.
A missing or unresolvable module, or one that would contribute bytes, is a loud nonzero
error rather than a silent skip.

Case 0 is the SENTINEL (permanent, first): games/sonic4/test/poison/poison_sentinel.emp,
whose single self-contained guard always fires. If it builds clean, --extra-entry is not
evaluating the module it names and every case after it would pass vacuously, so the lane
fails right there instead of reporting green.
"""
import os, subprocess, sys, pathlib, tempfile, time

AEON = pathlib.Path(__file__).resolve().parent.parent
SIGIL = os.environ.get("SIGIL_BUILD")
if not SIGIL:
    sys.exit("SIGIL_BUILD not set (same contract as build.sh)")

POISON = "games/sonic4/test/poison"

# The anti-vacuity sentinel: (module path relative to AEON, expected fragment, expected
# [Error] count). Its guard names nothing outside its own file, so a failure isolates the
# mechanism — module resolved, module-level `ensure`s evaluated — from every question
# about helper vocabulary or engine guards.
SENTINEL: tuple[str, str, int] = (
    f"{POISON}/poison_sentinel.emp", "EMP_EXPECT_FAIL_SENTINEL", 1,
)

# (poison module path relative to AEON, entry id, expected message fragment, expected
# [Error] count). Count defaults to 1 — one poison, one legitimately-firing guard — and
# is stated explicitly only where a poison is known to trip more than one ensure.
# The Task 8 poisons, each independently verified to trip its guard.
# Task 8 review (2026-08-17) added poison_patchable_partner.emp (rule 6 half 2, review
# I-2) and poison_direct_8a.emp (the $8A direct-construction clause, review I-3), and
# corrected 8b C-A's count to 2: it legitimately trips BOTH the "would bury" ensure
# (its own unequal-span intersecting op) AND the isect_earlier count ensure (2
# strictly-earlier intersecting ops, only one of which is the equal-span partner) —
# see the poison's own header comment. The two $8F cases (8d D-C and 8d E-D) expect
# DISTINCT fragments so a case passing does not merely mean "the string 'autoincrement'
# appeared somewhere": D-C is the reg_set constructor's own ensure (fragment "assumes
# stride 2"), E-D is the program-level scan that catches direct enum construction
# (fragment "cannot be dodged").
# R1 Task 9 added the two band() minima cases, both count 2 and both for the same
# structural reason: band() refuses the height AND returns its fires anyway (ensure is
# non-aborting), so check_density refuses the same overrun a second time in its own
# words. That pair IS claim E-C — with band()'s minima removed, both poisons fail on
# check_density ALONE, with a message naming fires band() synthesised and the author
# never wrote. A drop to 1 on either case means one of the two stopped firing; the
# constructor's is the one that matters.
CASES: list[tuple[str, str, str, int]] = [
    (f"{POISON}/poison_two_restores.emp",         "8a",         "one band per program", 1),
    (f"{POISON}/poison_band_buried_tint.emp",     "8b C-A",     "would bury", 2),
    (f"{POISON}/poison_patchable_band_fire.emp",  "8b rule6 half1", "must be static", 1),
    (f"{POISON}/poison_patchable_partner.emp",    "8b rule6 half2", "must be static — a patchable partner", 1),
    (f"{POISON}/poison_setreg_on_restore.emp",    "8c D-B",     "carries the restore ONLY", 1),
    (f"{POISON}/poison_regset_8f.emp",            "8d D-C",     "assumes stride 2", 1),
    (f"{POISON}/poison_direct_8f.emp",            "8d E-D",     "cannot be dodged", 1),
    (f"{POISON}/poison_direct_8a.emp",            "8d E-D $0A", "detonates the relative-arm chain", 1),
    (f"{POISON}/poison_ship_plus_restore.emp",    "8e claim6",  "offscreen_ship", 1),
    (f"{POISON}/poison_band_h1_region.emp",       "9 D-D sh0",  "below this ON op's minimum", 2),
    (f"{POISON}/poison_band_h2_sh.emp",           "9 E-C sh1",  "needs height >= 3", 2),
    # ---- Scanline P1 Task 8: the scene model's guards (spec 2026-08-17 §8.2) ----
    # Every fragment below quotes an INTERPOLATED NUMBER as well as the guard's wording,
    # because these four guards have near-twins the wording alone would not separate.
    #  - "scene grid": `layer()`'s ensure is the only one in the tree that speaks of the
    #    8-px cell grid, and "world_y 4" pins the offending value, so a poison that
    #    started failing on the span guard one line below (a different message) or on a
    #    different world_y cannot match.
    #  - "scene capacity": games/sonic4/data/parallax/configs.emp's `hdr()` carries the
    #    SAME guard, ported by name, and its message differs only in the nouns — "an
    #    anchored CONFIG splits a BAND ... needs BAND_COUNT+1". Quoting scene()'s own
    #    "anchored scene SPLITS a layer" plus "count+1" is what distinguishes the scene
    #    model's copy from the legacy one, and "8+1" pins the arity.
    #  - "scene mask A/B": the TWO-FIXTURE DIFFERENTIAL, and the count of 1 is half the
    #    assertion. The module holds THREE ensures: two for fixture A (its fold equals the
    #    hand-derived $0001, and it is a subset of the declared word) which MUST PASS, and
    #    one for fixture B which must fail. A count of 2 or 3 means fixture A stopped
    #    passing, i.e. the subset test is no longer proven able to pass and fail on the
    #    same property; a count of 0 means the fold stopped distinguishing the fixtures.
    #    The fragment quotes all three numbers (5 folded, 1 declared, 4 undeclared) so a
    #    case can only pass when scene_caps()/fold_caps() really produced them.
    #  - "scene proof": `cfg_eq` tests fields in REVERSE order so the LOWEST differing
    #    index survives — which means an extra mismatch at a higher index would be masked
    #    by the planted field 4 and the poison would go red for a reason indistinguishable
    #    from the intended one (a misspelled Label lands at field 10/11/12 and does not
    #    error). "band field -1" is the other half: the band oracle is transcribed
    #    correctly, so a comparator that invented a difference would change that number.
    #    Both halves are reported by one ensure, hence one diagnostic.
    # P3 Task 7 CHANGED THIS CASE'S SUBJECT, not just its wording. `layer()`'s 8-px grid
    # ensure was REMOVED (world-Y re-glue made an off-grid top representable), and its job
    # moved into scene_forces_per_line()'s arm 5 — off-grid now FORCES the per-line
    # pipeline instead of being refused. The poison is now a two-fixture differential and
    # asserts the false half, so the diagnostic it captures is the proof arm 5 fired.
    # Count stays 1: the on-grid control must stay green.
    (f"{POISON}/poison_scene_grid.emp",           "P3 off-grid forcer", "forced the per-line pipeline", 1),
    # P3 Task 15: "capacity under re-glue plus an anchor" is THIS EXISTING ROW — Task 7
    # kept scene()'s anchored-capacity ensure byte-for-byte (capacity stays 8, its own
    # ruling), so the P1 fixture (eight layers + anchor = nine shadow entries, exactly ONE
    # over) already is the one-unit poison and a second module would be a duplicate row.
    # The poison's header records the re-verification.
    (f"{POISON}/poison_scene_capacity.emp",       "P1 capacity", "an anchored scene SPLITS a layer at runtime, so the shadow view needs count+1 entries — 8+1", 1),
    (f"{POISON}/poison_scene_mask.emp",           "P1 mask A/B", "FIXTURE B folds to 5 against fixture A's declared 1; the UNDECLARED bits are 4", 1),
    (f"{POISON}/poison_scene_proof.emp",          "P1 proof",   "differs at cfg field 4 (band field -1)", 1),
    # ---- Scanline P3 Task 9: `deform: own(..)`, the per-layer deform ref ----
    # Three cases for three DIFFERENT questions, and none of them is "own() is refused":
    #  - "own caps": the two-fixture differential on the capability fold. Design §2 rules
    #    that shared(phase) does NOT trip MULTI_DEFORM_TABLE and own() does, and only a
    #    PAIR can tell that from "anything with a table trips it". The fragment quotes all
    #    three numbers (5 folded for A, 37 for B, 32 undeclared) so the case cannot pass
    #    on the word "UNDECLARED" appearing somewhere. Count 1: fixture A's two ensures
    #    must stay green, and a 2 means shared/None started raising the bit.
    #  - "own placement": SceneDeform is ONE enum authored in TWO positions, and the
    #    scene-level slot has nowhere to put a per-layer speed. Without the guard the Own
    #    lowers silently — `scene_deform_table()` returns the Label from that arm too, so
    #    the table would reach the header and the shifts/phase/speed would vanish with no
    #    diagnostic. Count 1 is half the assertion: with the Own in a SCENE slot there is
    #    no per-layer own, so derived_own() is 0 and neither the scene-level-table guard
    #    nor the fold's implication pin fires.
    #  - "own flat": the guard that makes CAP_MULTI_DEFORM_TABLE ⇒ CAP_DEFORM structural.
    #    COUNT 2, and the pair IS the assertion — this is the R1-Task-9 band() shape
    #    exactly. `ensure` is non-aborting, so layer() refuses the flat own() and builds
    #    the layer anyway; scene_caps() then folds it to $0021 and the implication pin
    #    fires in its own words, because the amplitude that would have supplied $0004 is
    #    the one the constructor just refused. A drop to 1 means one of the two stopped
    #    firing, and WHICH one matters: the constructor's is the guard that keeps the
    #    runtime honest (the per-band reload is emitted inside the CAP_DEFORM block), the
    #    fold's is the backstop that proves the implication is not merely asserted in a
    #    comment. The expected fragment names the constructor's, so a 1 that kept only the
    #    fold's would fail on the fragment as well as the count.
    #    (Predicted 1 when the case was written, measured 2 — recorded because the
    #    prediction was wrong for an instructive reason: $0020 is raised by the VARIANT
    #    and $0004 by the AMPLITUDE, so refusing the amplitude is exactly what separates
    #    them.)
    (f"{POISON}/poison_scene_own_caps.emp",       "P3 T9 own caps",  "FIXTURE B folds to 37 against fixture A's declared 5; the UNDECLARED bits are 32", 1),
    (f"{POISON}/poison_scene_own_placement.emp",  "P3 T9 placement", "deform: Own(..) is a PER-LAYER attachment", 1),
    (f"{POISON}/poison_scene_own_flat.emp",       "P3 T9 flat own",  "attaches a table this layer never samples", 2),
    # ---- P3 T10: curves. Two cases, one per half of the mechanism's guard surface. ----
    #  - "curve percell": the FORCER. scene_forces_per_line() ARM 3 was authored DEAD by
    #    Task 6 and woken by Task 10, and this is the only fixture in the tree whose control
    #    half folds to capability mask ZERO — every other arm removed — so the single
    #    authored difference is the `curve:`. The fragment quotes 65 = $0041, which is BOTH
    #    the capability bit AND the per-line bit arm 3 raises; a 64 would mean the arm went
    #    dead again. Exactly 1 diagnostic: fixture A's two ensures must pass.
    #  - "curve deform": the PROHIBITION, both halves in one build — layer() refuses a curve
    #    beside a live amplitude, scene() refuses one beside an anchor with live shifts. TWO
    #    diagnostics, and the count is half the assertion: a 1 means one of the two guards
    #    stopped firing, and the two live in different constructors for different reasons.
    (f"{POISON}/poison_scene_curve_percell.emp",  "P3 T10 curve forcer", "FIXTURE B folds to 65 against fixture A's declared 0; the UNDECLARED bits are 65", 1),
    (f"{POISON}/poison_scene_curve_deform.emp",   "P3 T10 curve+deform", "this layer authors BOTH a curve and a live deform amplitude", 2),
    # ---- Substrate item 1c: check_landings, both edges of the measured window ----
    # Two cases, not one, because the two edges have different evidentiary standing: the
    # LATE edge is the sampling instant the sweep measured directly, the EARLY edge is
    # derived from the H40 blanking width and could never be observed. A single poison
    # would leave whichever edge it missed unproven.
    #  - "landing late": exactly 1 diagnostic. Three reg_sets push a cram op past the
    #    window before it spins at all, so the EARLY test passes and only the LATE one
    #    fires. A count of 2 means a second guard started firing.
    #  - "landing early": exactly 2, and the count is half the assertion — the solver
    #    centres the COMBINED span of a two-stream-op fire, which puts op 0 before the
    #    window opens AND op 1 after it closes. A count of 1 means the pair stopped being
    #    solved together.
    # Both fragments quote the guard's own wording rather than a number, because the
    # numbers here move whenever a cost term does and the case would then fail for a
    # reason unrelated to the guard.
    (f"{POISON}/poison_landing_late.emp",         "1c late edge",  "past the latest legal", 1),
    (f"{POISON}/poison_landing_early.emp",        "1c early edge", "EARLIER than the earliest legal", 2),
    # ---- The per-class burst ceilings (RASTER_BURST_MAX_CRAM 3 -> 4, 2026-08-19) ----
    # The raise is a one-token edit to a guard whose SHAPE did not change, which is the
    # edit most likely to become no guard at all without anything noticing. Two cases,
    # one per half of the split, because the two halves fail for different reasons and a
    # single case would leave the other half unproven:
    #  - "cram 4 words": the first width the cram class refuses, and the interesting one —
    #    it PASSES the placeability arithmetic with 14.9 cycles to spare and is refused
    #    anyway, because the solved spin's rounding leaves 0.9 cycles at the early edge.
    #    A raise has to come here and argue. Exactly 1 — `raster_words` reaches only the
    #    constructor's own ensure, and check_landings would NOT fire at this width.
    #  - "deep 4 words": the same width reaching a DIFFERENT guard. The op is built as the
    #    variant so the constructor never runs, and check_landings refuses it on the early
    #    edge — where the cram class at the same width is refused by the CONSTRUCTOR and
    #    would clear the landing guard. Two widths' worth of evidence that the two classes
    #    fail for different reasons. Exactly 1 — the late edge passes.
    #    Its fragment quotes the interpolated opcode and width rather than the guard's
    #    wording, which "landing early" already covers; matching wording alone would make
    #    the two cases indistinguishable.
    (f"{POISON}/poison_cram_four_words.emp",      "cram 4 words",  "4 colours exceeds RASTER_BURST_MAX_CRAM (3)", 1),
    (f"{POISON}/poison_deep_four_words.emp",      "deep 4 words",  "opcode 4, 4-word burst", 1),
    # ---- Scanline P2 Task 13: the scene budget axes (design §5) ----
    # ONE case, not four, and the count is a finding rather than a shortfall — see the
    # "FALSIFIABILITY" block in tools/effects_budget_model.toml [scene_budget]. Of the four
    # axes P2 enforces, only AXIS 1 has an input that can cross its budget at all:
    #   axis 2 charges 0 or 1792 B against a 6260 B budget — two-valued, always fits;
    #   axis 3 charges 0 or 4270 cyc against 9920 — likewise;
    #   axis 4b is bounded ABOVE by the 4a density guard (a fire's cost must fit its gap, so
    #     a whole screen cannot exceed 224 x 488 = 109312) and, at the shipped burst
    #     ceilings, tops out near 77000 against an 84595 budget.
    # Writing three more "poisons" that cannot go red would be the vacuous-gate defect this
    # lane exists to prevent, so they are booked instead of faked.
    #
    # AXIS 1 is genuinely falsifiable and the unit is ONE BAND: fixture A at 115 bands costs
    # 103332.74 and PASSES, fixture B at 116 costs 104188.01 and fails by 82.01 cyc (0.08%).
    # Exactly 1 [Error] — fixture B's axis-2/axis-3 charges are unchanged from A's and both
    # fit, so neither of those ensures fires. A count of 2 means another axis started
    # failing; a count of 0 means the fold stopped separating 115 bands from 116.
    (f"{POISON}/poison_budget_axis1.emp",         "P2 axis 1",     "scene budget AXIS 1 (main-loop cycles)", 1),
    # ---- Scanline P3 Task 15: one red-first row per remaining new walker guard ----
    # Four rows. Each is a two-fixture differential whose fixtures differ by ONE authored
    # unit, with the control's pass MEASURED by an in-module ensure on a hand-derived
    # value (P1's mask-poison footnote: a control whose pass is assumed proves nothing).
    #  - "act span": Task 7's DERIVED bound — the registry-level fold's `wy < act_span`
    #    ensure, which replaced layer()'s typed `world_y < 512` when tops became ACT
    #    coordinates. Fixture A tops at 6143 (the LAST legal act Y, and deliberately
    #    off-grid — plane image 383 at v_factor 4 — so the pass also witnesses that the
    #    retired grid rule stays retired); fixture B at 6144, ONE act pixel over. The
    #    span argument is the registry's own SCENE_ACT_SPAN_Y import, never typed, so the
    #    fragment's interpolated "(6144) ... (6144)" pins both the offending top and the
    #    derived bound. Exactly 1: the fold's ensure fires once for B's one top; A's
    #    return count is ensured at the hand-derived 1 (one top, no anchor).
    #  - "lcm undeclared": the CASES row P3 Task 12's DONE block explicitly left to this
    #    task. scene()'s MANDATORY left-column policy: fixture A declares Accept (the
    #    answer both shipped per-column families actually use), fixture B omits the
    #    declaration — one authored field. The fragment quotes the WHOLE interpolated
    #    scene signature (1 layer / speed 0 / shift 2) because sigil reports the ensure
    #    at its own span, and the signature triple is the only thing that says WHICH
    #    scene failed. Exactly 1: guard (2) (no-policy-without-a-subject) passes for B,
    #    a 2 means Accept stopped being legal on the control.
    #  - "twinkey table": the INPUT-REACHABLE twin-key desync, both halves in one build —
    #    scene() refuses an own() layer whose table would be the scene's only one (the
    #    runtime mode key reads HEADER words and cannot see bands), and, because ensure
    #    is non-aborting, the refused scene folds to $0020 alone and scene_caps()'s
    #    MULTI_DEFORM_TABLE implication pin fires as the backstop. COUNT 2 and the pair
    #    is the assertion (the poison_scene_own_flat shape): a 1 that kept only the
    #    fold's fails the fragment too — the expected fragment names the constructor's.
    #    One authored field: fixture B is fixture A minus `deform_bg:`.
    #  - "twinkey anchor": the poison_scene_grid INVERSION — the diagnostic is the PROOF.
    #    Task 6's CAP_ANCHORS-implies-CAP_PER_LINE pin cannot itself be driven red by any
    #    input (both bits derive from the one sc_anchor field through the same accessor;
    #    measured 2026-08-22 with this very fixture asserted both ways), so this row
    #    witnesses the AGREEMENT instead: the Scene{ .. } back-door anchored scene is
    #    asserted to fold to $0008 alone — false by exactly the one bit under test — and
    #    the captured diagnostic quotes the true fold, 9. A CLEAN build is the
    #    regression (an anchored input really folding to $0008 alone). Exactly 1: no
    #    constructor runs (back door) and no fold pin fires at $0009.
    (f"{POISON}/poison_scene_actspan.emp",        "P3 T7 act span",       "a world-Y layer top (6144) is outside this act's vertical span (6144)", 1),
    (f"{POISON}/poison_scene_lcm_undeclared.emp", "P3 T12 lcm undeclared", "a scene with 1 layer(s) attaching a per-column V-deform table (SceneVDeform.Columns, sample speed 0, amplitude shift 2) declares NO left_column_mask policy", 1),
    (f"{POISON}/poison_scene_twinkey_table.emp",  "P3 twinkey table",     "attaches NO plane-shared table on either plane", 2),
    (f"{POISON}/poison_scene_twinkey_anchor.emp", "P3 twinkey anchor",    "back-door anchored scene folds to 9", 1),
    # ---- VFACTOR: the two whole-plane vertical-shift range guards ----
    # TWO ROWS AGAINST ONE MODULE, and the pairing is the point: the module holds two
    # control/poison pairs (v_factor 15 vs 255, v_factor_fg 0 vs 255), so a single build
    # yields exactly two diagnostics and each row asserts that ITS guard produced one of
    # them. The count of 2 is half of each row's assertion — a 3 or 4 means a control
    # stopped passing (a bound excluding 15 would refuse most of the shipped registry;
    # one excluding 0 would refuse every scene in the tree), and a 1 means one guard went
    # dead while the other's row still passed, which is exactly what the two distinct
    # fragments exist to catch.
    #
    # THE FRAGMENTS ARE NOT INTERCHANGEABLE, deliberately. The second field's NAME
    # CONTAINS the first's, and both messages open "outside 0 .. 15" — matching that
    # alone would pass against either diagnostic. Each fragment therefore quotes the
    # interpolated 255 plus a clause only its own guard says: the v_factor guard names
    # `Parallax_Step5_Vscroll`, the reserved twin names itself as the FG twin.
    #
    # 255 is the DEFECT'S OWN VALUE, not a convenient out-of-range one: Aurora's editor
    # default for a new scene is the string "FACTOR_0", which is parallax_dsl's PACKED
    # factor (FACTOR_LOCKED = $0FF) landing in a RAW-SHIFT field whose sentinel is 15.
    # Measured red-first at this parcel: with the two guards stashed out, this module
    # builds CLEAN (rc 0, zero [Error]) — the silence the parcel exists to end.
    (f"{POISON}/poison_scene_vfactor_range.emp",  "VFACTOR v_factor",     "v_factor 255 outside 0 .. 15 — Parallax_Step5_Vscroll reads this byte as", 2),
    (f"{POISON}/poison_scene_vfactor_range.emp",  "VFACTOR v_factor_fg",  "v_factor_fg 255 outside 0 .. 15 — this is v_factor's FG twin", 2),
]


def run_build(poison: str) -> tuple[int, str]:
    """The real build invocation, with `poison` (an AEON-relative path) as an extra entry."""
    with tempfile.TemporaryDirectory() as td:
        out_bin = os.path.join(td, "probe.bin")
        p = subprocess.run(
            [SIGIL, "build", "--aeon", ".", "--native", "--game", "sonic4", "-o", out_bin,
             "--extra-entry", poison],
            capture_output=True, text=True, cwd=AEON,
        )
    return p.returncode, p.stdout + p.stderr


def run_one(label: str, poison: str, expect: str,
            expect_count: int = 1) -> tuple[bool, str, float]:
    """Build with `poison` as an extra entry and evaluate the diagnostic.

    Returns (ok, why, elapsed_seconds).
    """
    t0 = time.monotonic()
    rc, out = run_build(poison)
    elapsed = time.monotonic() - t0

    if rc == 0:
        return False, f"BUILT CLEAN — the guard did not fire ({label})", elapsed
    if expect not in out:
        tail = " | ".join(out.strip().splitlines()[-3:])
        return False, (
            f"failed WITHOUT the expected fragment {expect!r} — wording drift or "
            f"wrong guard; got: {tail}"
        ), elapsed
    got_count = out.count("[Error]")
    if got_count != expect_count:
        tail = " | ".join(out.strip().splitlines()[-3:])
        return False, (
            f"fragment {expect!r} present but got {got_count} [Error] diagnostic(s), "
            f"expected {expect_count} — a diagnostic count drift can mean a guard "
            f"stopped firing (or a NEW one started); got: {tail}"
        ), elapsed
    return True, "ok", elapsed


def main() -> int:
    sentinel_path, sentinel_expect, sentinel_count = SENTINEL

    named = [(sentinel_path, "sentinel")] + [(path, entry) for path, entry, _, _ in CASES]
    missing = [(path, entry) for path, entry in named if not (AEON / path).is_file()]
    if missing:
        print("emp_expect_fail: FAIL — named poison modules that do not exist:")
        for path, entry in missing:
            print(f"  {entry}: {path}")
        return 1

    bad = 0

    # CASE 0, permanent, first: the sentinel. If this builds clean, --extra-entry is not
    # evaluating the module it names and every case below is testing nothing.
    ok, why, elapsed = run_one("sentinel", sentinel_path, sentinel_expect, sentinel_count)
    print(f"  {'PASS' if ok else 'FAIL'}  sentinel ({elapsed:.2f}s): {why}")
    if not ok:
        print("emp_expect_fail: FAIL — the sentinel did not fire. `sigil build "
              "--extra-entry` is not evaluating the module it is given, so every case "
              "below would be vacuous; this run stops here.")
        return 1

    for path, entry, expect, expect_count in CASES:
        ok, why, elapsed = run_one(entry, path, expect, expect_count)
        print(f"  {'PASS' if ok else 'FAIL'}  {entry} ({elapsed:.2f}s): {why}")
        bad += 0 if ok else 1

    print(f"emp_expect_fail: {'OK' if not bad else 'FAIL'} — {len(CASES) - bad}/{len(CASES)} cases")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
