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
import os, re, subprocess, sys, pathlib, tempfile, time

AEON = pathlib.Path(__file__).resolve().parent.parent
SIGIL = os.environ.get("SIGIL_BUILD")
if not SIGIL:
    sys.exit("SIGIL_BUILD not set (same contract as build.sh)")

POISON = "games/sonic4/test/poison"


def emp_const(rel: str, name: str) -> int:
    """A `const NAME = <int>` read out of an .emp source.

    WHY A FRAGMENT MAY NOT SPELL AN ENGINE BOUND AS A LITERAL. A poison fixture sized
    against a ceiling, matched by a fragment quoting that ceiling, is only loud when the
    ceiling moves UP: the fixture stops being over-long, the guard stops firing, and the
    lane says so. Move the same ceiling DOWN and the fixture is still over it, the guard
    still fires, the literal still matches, and the case reports GREEN about a bound that
    no longer exists. Measured on the 2026-08-27 MAX_PARALLAX_BANDS 8 -> 16 raise, where
    poison_scene_capacity's "8+1" was hardcoded on both sides with nothing pinning it.
    So the fragment is COMPUTED from the source of truth and tracks it in both directions.

    A constant this cannot read is a LOUD exit, never a default: a fragment silently
    computed from a fallback would pass or fail for a reason unrelated to the guard.
    """
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        sys.exit(f"emp_expect_fail: cannot find `const {name}` in {rel} — a case fragment "
                 "is computed from it and a guessed value would make that case vacuous")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


# The engine's band ceiling, for the two scene-capacity fragments below.
MAX_PARALLAX_BANDS = emp_const("engine/system/constants.emp", "MAX_PARALLAX_BANDS")

# The DPLC entry word's tile_start width, for the tile_start-ceiling fragment below.
# Folded here exactly as engine/objects/dplc.emp folds it, from the ONE name — never
# typed as 12 or 4095, so the fixture and the fragment track the field in both
# directions (see emp_const's note above for why that matters).
DPLC_TILE_START_BITS = emp_const("engine/objects/dplc.emp", "DPLC_TILE_START_BITS")
DPLC_TILE_START_MAX = (1 << DPLC_TILE_START_BITS) - 1
DPLC_ADDRESSABLE_TILES = DPLC_TILE_START_MAX + 1

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
    # RENAMED AND RE-AIMED BY PARCEL P2a, which deleted the refusal this row used to hold.
    # It was `poison_two_restores` / "one band per program": two well-formed bands over
    # disjoint spans whose only defect was the count. Admitting exactly that program IS
    # P2a, so the case could not survive as written — and dropping it would have been a
    # silent coverage loss at the one spot where a lifted refusal is most likely to stop
    # guarding. It is re-aimed at the refusal that INHERITED the job of capping N: the
    # 64-word program buffer. Its old body did not disappear either — it is now a POSITIVE
    # fixture in engine/effects/raster_dsl.emp (`zz_disjoint`) that must BUILD through
    # raster_program on every build. The two are the before and after of one deletion.
    #
    # THE FRAGMENT'S 142 IS THE FIXTURE'S OWN SIZE, NOT THE CEILING, which is what makes it
    # loud in the direction `emp_const`'s note above warns about. Four 1-word-cram bands are
    # 7 + 4 x 16 = 71 words = 142 bytes, derived from the shipped `op_size`; if a band's wire
    # cost changes, 142 moves and this row goes red. The OTHER direction — a buffer that
    # shrank, leaving this poison failing for a bound that no longer exists — is caught in
    # raster_dsl.emp instead, by a THREE-band program that must build. Neither half suffices:
    # this lane can only prove a refusal, and a refusal for a vanished bound reports green.
    (f"{POISON}/poison_four_bands.emp",           "P2a buffer cap", "142 bytes exceeds RASTER_BUF_SIZE", 1),
    (f"{POISON}/poison_band_buried_tint.emp",     "P1 OWN-1 bury",  "would bury", 2),
    (f"{POISON}/poison_patchable_band_fire.emp",  "8b rule6 half1", "must be static", 1),
    (f"{POISON}/poison_patchable_partner.emp",    "8b rule6 half2", "must be static — a patchable partner", 1),
    (f"{POISON}/poison_setreg_on_restore.emp",    "8c D-B",     "carries the restore ONLY", 1),
    # ---- band ENTRY OWNERSHIP, parcel P1 (design 2026-08-28 §3, rules OWN-1/2/3) ----
    # These five replace guard C-A's coverage and extend it. C-A inferred a band's pairing
    # from span equality and fire order; ownership is now DECLARED on the op, so the guards
    # can refuse things C-A could not see (an ownerless restore, an id naming no ON, a
    # hand-built restore whose span differs from its ON's, two bands nested on one entry)
    # and can name the program rather than its own bookkeeping when they refuse.
    #
    # THE COUNTS ARE DERIVED FROM THE WALK, not observed and pasted. OWN-1 carries one
    # `poisoned` flag PER CRAM ENTRY and reports at most one sentence for each, so a
    # fixture's count is (entries the fault covers) x (guards that see it). Three of these
    # fixtures are deliberately ONE CRAM WORD wide so that product is 1 or 2. A count that
    # drifts UP means the poison flag stopped suppressing a cascade; a count that drifts
    # DOWN means a guard stopped firing.
    #
    # PARCEL P2a MOVED EXACTLY ONE OF THESE COUNTS, and it was predicted here before it
    # happened. At P1 every TWO-BAND fixture also tripped `restore_n <= 1`, so its count
    # carried a second error that had nothing to do with its own subject. P2a deleted that
    # count, so `poison_band_nested` — the only two-band fixture in this block — drops 2 -> 1
    # and now reports the nesting sentence ALONE. The other four each carry exactly ONE
    # restore op, so the deleted count never contributed to them and their counts are
    # unchanged; `poison_band_span_mismatch` in particular looks like two restores and is
    # not, because it takes only index [0] of its band (the ON fire) and supplies the
    # restore by hand.
    (f"{POISON}/poison_band_no_owner.emp",        "P1 OWN-2 no owner",  "carries no band id", 1),
    (f"{POISON}/poison_band_orphan_restore.emp",  "P1 OWN-2 orphan",    "has 0 ON op(s) carrying its id", 2),
    (f"{POISON}/poison_band_span_mismatch.emp",   "P1 OWN-2 span",      "must name the SAME span", 2),
    (f"{POISON}/poison_band_nested.emp",          "P1 OWN-1 nested",    "two bands are live on CRAM entry", 1),
    (f"{POISON}/poison_band_base_above.emp",      "P1 OWN-1 base",      "does not hold this frame's base palette", 1),
    (f"{POISON}/poison_regset_8f.emp",            "8d D-C",     "assumes stride 2", 1),
    (f"{POISON}/poison_direct_8f.emp",            "8d E-D",     "cannot be dodged", 1),
    (f"{POISON}/poison_direct_8a.emp",            "8d E-D $0A", "detonates the relative-arm chain", 1),
    (f"{POISON}/poison_ship_plus_restore.emp",    "8e claim6",  "offscreen_ship", 1),
    (f"{POISON}/poison_band_h1_region.emp",       "9 D-D sh0",  "below this ON op's minimum", 2),
    (f"{POISON}/poison_band_h2_sh.emp",           "9 E-C sh1",  "needs height >= 3", 2),
    # ---- Scanline P1 Task 8: the scene model's guards (spec 2026-08-17 §8.2) ----
    # Every fragment below quotes an INTERPOLATED NUMBER as well as the guard's wording,
    # because these guards have near-twins the wording alone would not separate.
    #  (The "scene grid" case is gone twice over: P3 Task 7 retired layer()'s 8-px grid
    #   ensure, and 2026-08-26 retired the per-line forcer arm that replaced it.)
    #  - "scene capacity": games/sonic4/data/parallax/configs.emp's `hdr()` carries the
    #    SAME guard, ported by name, and its message differs only in the nouns — "an
    #    anchored CONFIG splits a BAND ... needs BAND_COUNT+1". Quoting scene()'s own
    #    "anchored scene SPLITS a layer" plus "count+1" is what distinguishes the scene
    #    model's copy from the legacy one, and the trailing "<MAX>+1" pins the arity.
    #    THAT ARITY IS COMPUTED, not typed (2026-08-27): see emp_const()'s note. The
    #    fixture reads the same constant for its layer count, so the pair moves together
    #    and the case cannot go green about a ceiling that has moved underneath it.
    #  - "scene mask A/B": the TWO-FIXTURE DIFFERENTIAL, and the count of 1 is half the
    #    assertion. The module holds THREE ensures: two for fixture A (its fold equals the
    #    hand-derived $0000 — a bare table raises nothing since CAP_PER_LINE was retired
    #    2026-08-26 — and it is a subset of the declared word) which MUST PASS, and
    #    one for fixture B which must fail. A count of 2 or 3 means fixture A stopped
    #    passing, i.e. the subset test is no longer proven able to pass and fail on the
    #    same property; a count of 0 means the fold stopped distinguishing the fixtures.
    #    The fragment quotes all three numbers (4 folded, 0 declared, 4 undeclared) so a
    #    case can only pass when scene_caps()/fold_caps() really produced them.
    #  - "scene proof": `cfg_eq` tests fields in REVERSE order so the LOWEST differing
    #    index survives — which means an extra mismatch at a higher index would be masked
    #    by the planted field 4 and the poison would go red for a reason indistinguishable
    #    from the intended one (a misspelled Label lands at field 10/11/12 and does not
    #    error). "band field -1" is the other half: the band oracle is transcribed
    #    correctly, so a comparator that invented a difference would change that number.
    #    Both halves are reported by one ensure, hence one diagnostic.
    # (The "P3 off-grid forcer" row — poison_scene_grid.emp — was DELETED 2026-08-26 with
    # scene_forces_per_line(): an off-grid top is simply legal now that the per-line fill
    # is the only fill, d-29-corrected. Nothing is left for a poison to drive red.)
    # P3 Task 15: "capacity under re-glue plus an anchor" is THIS EXISTING ROW — the
    # fixture is MAX_PARALLAX_BANDS layers + an anchor = MAX+1 shadow entries, exactly ONE
    # over, so it is the one-unit poison at whatever the ceiling is and a second module
    # would be a duplicate row. The poison's header records the derivation.
    (f"{POISON}/poison_scene_capacity.emp",       "P1 capacity", f"an anchored scene SPLITS a layer at runtime, so the shadow view needs count+1 entries — {MAX_PARALLAX_BANDS}+1", 1),
    (f"{POISON}/poison_scene_mask.emp",           "P1 mask A/B", "FIXTURE B folds to 4 against fixture A's declared 0; the UNDECLARED bits are 4", 1),
    # The index is pcfg_v_center_y's position in scene_equiv_proof.emp's CFG FIELD INDEX
    # table, which is engine/structs.emp's declaration order. It moved 4 -> 3 on
    # 2026-08-27 when pcfg_layer_mask widened to a u16 and took byte $02.
    (f"{POISON}/poison_scene_proof.emp",          "P1 proof",   "differs at cfg field 3 (band field -1)", 1),
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
    (f"{POISON}/poison_scene_own_caps.emp",       "P3 T9 own caps",  "FIXTURE B folds to 36 against fixture A's declared 4; the UNDECLARED bits are 32", 1),
    (f"{POISON}/poison_scene_own_placement.emp",  "P3 T9 placement", "deform: Own(..) is a PER-LAYER attachment", 1),
    (f"{POISON}/poison_scene_own_flat.emp",       "P3 T9 flat own",  "attaches a table this layer never samples", 2),
    # ---- P3 T10: curves. One case: the prohibition. ----
    #  (The "curve forcer" row — poison_scene_curve_percell.emp, scene_forces_per_line()
    #   ARM 3 — was DELETED 2026-08-26 with the forcer itself, d-29-corrected: a curve no
    #   longer has to force anything, the fill is per-line for every scene.)
    #  - "curve deform": the PROHIBITION, both halves in one build — layer() refuses a curve
    #    beside a live amplitude, scene() refuses one beside an anchor with live shifts. TWO
    #    diagnostics, and the count is half the assertion: a 1 means one of the two guards
    #    stopped firing, and the two live in different constructors for different reasons.
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
    #  - "own-only table": both halves in one build — scene() refuses an own() layer whose
    #    table would be the scene's only one (the fill loads the HEADER words once and only
    #    an own() band reloads them, so the other bands would sample address 0), and,
    #    because ensure is non-aborting, the refused scene folds to $0020 alone and
    #    scene_caps()'s MULTI_DEFORM_TABLE-implies-DEFORM pin fires as the backstop. COUNT
    #    2 and the pair is the assertion (the poison_scene_own_flat shape): a 1 that kept
    #    only the fold's fails the fragment too — the expected fragment names the
    #    constructor's. One authored field: fixture B is fixture A minus `deform_bg:`.
    #    (Was "twinkey table" until 2026-08-26; the guard's mode-key rationale went with
    #    the per-cell path, its sampling rationale stayed.)
    #  (The "twinkey anchor" row — poison_scene_twinkey_anchor.emp — was DELETED
    #   2026-08-26 with the CAP_ANCHORS-implies-CAP_PER_LINE pin it witnessed.)
    (f"{POISON}/poison_scene_actspan.emp",        "P3 T7 act span",       "a world-Y layer top (6144) is outside this act's vertical span (6144)", 1),
    (f"{POISON}/poison_scene_lcm_undeclared.emp", "P3 T12 lcm undeclared", "a scene with 1 layer(s) attaching a per-column V-deform table (SceneVDeform.Columns, sample speed 0, amplitude shift 2) declares NO left_column_mask policy", 1),
    (f"{POISON}/poison_scene_own_only_table.emp", "P3 own-only table",    "attaches NO plane-shared table on either plane", 2),
    # ---- FACTOR0LOCK: the five halves of the verified claim, one module, count 5 ----
    # FIVE ROWS AGAINST ONE MODULE, for the VFACTOR rows' reason and one more. The module
    # holds a passing control plus five poisons, each differing from it in exactly the
    # field its guard reads, so one build yields five diagnostics and each row asserts
    # that ITS half produced one of them. The shared count is half of every row's
    # assertion: a 6 means the CONTROL stopped passing (Factor0Lock became unclaimable
    # even for a genuinely locked scene — an over-fire, not a stricter gate), a 4 or less
    # means one half went dead and every row says so.
    #
    # THE EXTRA REASON, and it is why FB and DSB are here at all: three of these halves
    # (FA, CV, DSA) were added 2026-08-28 when the verification was extended from plane B
    # to both planes, and a guard rewritten to look at plane A must not have stopped
    # looking at plane B. FB and DSB are the converse rows — they fail on bare master too,
    # which is exactly what makes them the control on the rewrite rather than on the
    # feature. (Measured on the pre-change tree: this module yields 2 errors, FB and DSB;
    # on the post-change tree, 5.)
    #
    # THE FRAGMENTS ARE NOT INTERCHANGEABLE. All five messages open with the same
    # "left_column_mask: Factor0Lock claims" clause, so matching that would pass against
    # any of them; each fragment below quotes the one clause only its own guard says, and
    # each was verified to occur exactly once in the tree.
    # SIX halves since the band-drift parcel: drift is a plane-B scroll source in TIME
    # that the fb scan cannot see, the same class as the curve far end. All six rows share
    # the count, so a half going dead is reported by every one of them.
    (f"{POISON}/poison_scene_lcm_factor0.emp", "P3 T12 f0 plane-A factor", "PLANE A is not locked", 6),
    (f"{POISON}/poison_scene_lcm_factor0.emp", "P3 T12 f0 plane-B factor", "PLANE B is not locked", 6),
    (f"{POISON}/poison_scene_lcm_factor0.emp", "P3 T12 f0 curve far end",  "RAMPS its plane-B factor", 6),
    (f"{POISON}/poison_scene_lcm_factor0.emp", "P3 T12 f0 plane-A deform", "live H-deform on PLANE A", 6),
    (f"{POISON}/poison_scene_lcm_factor0.emp", "P3 T12 f0 plane-B deform", "live H-deform on PLANE B", 6),
    (f"{POISON}/poison_scene_lcm_factor0.emp", "drift f0 lock",            "but a layer DRIFTS", 6),
    # BAND DRIFT — layer()'s two rate guards. Both messages spell the unit, because the
    # 256x units error is the hazard no assertion can catch; each row quotes the clause
    # only its own guard says, never the shared sentence.
    (f"{POISON}/poison_layer_drift.emp", "drift Rate(0)",     "is not a slow drift, it is no drift", 2),
    (f"{POISON}/poison_layer_drift.emp", "drift rate range",  "THIS IS A TASTE BOUND", 2),
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
    # VOFFSET — the two fields BESIDE v_factor, which the VFACTOR parcel left open. Four rows
    # against one module, one per poisoned fixture (one past each end of each span), count 4
    # = the four poisons fire and the five controls (both ends of each span, plus the
    # booking's own `v_offset: -8`, which must be LEGAL and lower to $FFF8) stay green. The
    # bounds are derived in the poison's header: v_offset is the SIGNED word `add.w`
    # carries, v_center is the world-Y span the camera clamp + act-extent ensure give
    # layer()'s world_y. Measured red-first at this parcel: with the two guards stashed
    # out, this module builds with ZERO [Error] (the i16/u16 fields take the values
    # without complaint) — the silence the parcel exists to end.
    (f"{POISON}/poison_scene_vbounds_range.emp",  "VOFFSET v_offset low",  "v_offset -32769 outside -32768 .. 32767 — Parallax_Step5_Vscroll adds this field", 4),
    (f"{POISON}/poison_scene_vbounds_range.emp",  "VOFFSET v_offset high", "v_offset 32768 outside -32768 .. 32767 — Parallax_Step5_Vscroll adds this field", 4),
    (f"{POISON}/poison_scene_vbounds_range.emp",  "VOFFSET v_center low",  "v_center -1 outside 0 .. 32767 — this is a WORLD Y", 4),
    (f"{POISON}/poison_scene_vbounds_range.emp",  "VOFFSET v_center high", "v_center 32768 outside 0 .. 32767 — this is a WORLD Y", 4),
    # ---- Ring sparkle (2026-08-26): the S3K-derived display-frame gate ----
    # One case: script_display_frames() (games/sonic4/objects/ring_sparkle.emp) fed a script
    # one frame short must report 18 (3 x (5+1)) against the reference 24. The fragment
    # quotes the interpolated 18, so a fn that stopped counting frame bytes cannot match.
    (f"{POISON}/poison_ring_sparkle_frames.emp", "ring sparkle frames", "RING_SPARKLE_POISON: a 3-frame script shows 18 display frames", 1),
    # ---- Triangle-fold parcel (2026-08-26): EMP_PITFALLS §1's unit fold IS catchable ----
    # A verbatim copy of the pre-fix deform_triangle body (block-tail if in the comptime
    # for element) folds every sample to `()` with no sigil diagnostic; the case proves
    # the ONE engine-side catch surface — a value ensure over the folded samples — fires
    # loudly on it (`() == int` compares false rather than erroring). The fragment quotes
    # BOTH interpolated values, so the case passes only while the broken shape folds `()`
    # AND the shipped generator folds a real -16 beside it. If sigil ever fixes block-tail
    # if folding, this module builds CLEAN and the case fails — the retirement signal, see
    # the poison's header. Exactly 1: the module holds one ensure.
    (f"{POISON}/poison_tail_if_unit_fold.emp",   "tri unit fold", "TAIL_IF_UNIT_FOLD: the block-tail-if element folded P[0] to () while the shipped generator folds -16", 1),
    # One case: script_display_frames() (games/sonic4/player/player_instashield.emp) fed a
    # 3-frame script that ends in S3K's own two-byte `$FD, 0` terminator — the shape whose
    # ARGUMENT is a legal frame index. The fragment quotes the folded 3, so a walker that
    # counted that argument (printing 4) fails the case rather than passing it.
    (f"{POISON}/poison_instashield_frames.emp", "insta-shield frames", "INSTASHIELD_POISON: a 3-frame script shows 3 display frames", 1),
    # ---- DPLC tile_start ceiling (2026-08-30): the 12-bit field's one machine check ----
    # A two-fixture module, and the COUNT OF 1 IS HALF THE ASSERTION. Fixture A is the real
    # Knuckles sheet (4,092 tiles, the tightest in the tree) and must PASS; fixture B is a
    # sheet sized FROM the ceiling at exactly one tile over and must FAIL. A count of 2 means
    # A stopped passing — a ceiling that moved DOWN, which a refusal-only lane cannot see;
    # a count of 0 means B stopped firing.
    # BOTH SIDES OF THE FRAGMENT ARE COMPUTED. The tile count and the "0..max" are
    # DPLC_ADDRESSABLE_TILES and DPLC_TILE_START_MAX folded here from DPLC_TILE_START_BITS,
    # the same single name the poison and the six shipped ensures fold from, so moving the
    # width moves the fixture and the fragment together in both directions.
    (f"{POISON}/poison_dplc_tile_start.emp", "DPLC tile_start ceiling",
     f"DPLC_TILE_START_POISON: a {DPLC_ADDRESSABLE_TILES + 1}-tile art sheet cannot be "
     f"addressed by a DPLC entry's tile_start, which names only 0..{DPLC_TILE_START_MAX}", 1),
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
        # The verdict (something is wrong) and the REASON are separately checkable, and
        # this branch used to assert the reason unconditionally. run_one() returns False
        # for THREE different worlds and only the first of them means the mechanism is
        # broken:
        #   (a) BUILT CLEAN            -> --extra-entry really is not evaluating the module
        #   (b) fired, wrong fragment  -> wording drift, or a different guard caught it
        #   (c) fired, right fragment,
        #       wrong diagnostic count -> the tree itself is red for an unrelated reason
        # Lived 2026-08-27 (found by the aurora lane against a poisoned real tree): a
        # leaked poison made every --extra-entry build red, the sentinel fired CORRECTLY
        # reporting `got 5 [Error] diagnostic(s), expected 1`, and this tool announced
        # that --extra-entry was not evaluating its module at all. A sound verdict with a
        # fabricated justification, and the justification is what a reader carries away —
        # it sends them to debug the harness instead of their own tree.
        if why.startswith("BUILT CLEAN"):
            print("emp_expect_fail: FAIL — the sentinel BUILT CLEAN. `sigil build "
                  "--extra-entry` is not evaluating the module it is given, so every case "
                  "below would be vacuous; this run stops here.")
        else:
            print("emp_expect_fail: FAIL — the sentinel did not report as expected, but it "
                  "DID fail the build, so --extra-entry is evaluating the module. Suspect "
                  "the TREE before the harness: an unrelated error already present in the "
                  "sources reaches every --extra-entry build and changes what the sentinel "
                  "sees. Reason given above; this run stops here because the cases below "
                  "would inherit the same noise.")
        return 1

    for path, entry, expect, expect_count in CASES:
        ok, why, elapsed = run_one(entry, path, expect, expect_count)
        print(f"  {'PASS' if ok else 'FAIL'}  {entry} ({elapsed:.2f}s): {why}")
        bad += 0 if ok else 1

    print(f"emp_expect_fail: {'OK' if not bad else 'FAIL'} — {len(CASES) - bad}/{len(CASES)} cases")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
