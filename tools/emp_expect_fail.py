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
    (f"{POISON}/poison_scene_grid.emp",           "P1 grid",    "world_y 4 is not on the 8-px cell grid", 1),
    (f"{POISON}/poison_scene_capacity.emp",       "P1 capacity", "an anchored scene SPLITS a layer at runtime, so the shadow view needs count+1 entries — 8+1", 1),
    (f"{POISON}/poison_scene_mask.emp",           "P1 mask A/B", "FIXTURE B folds to 5 against fixture A's declared 1; the UNDECLARED bits are 4", 1),
    (f"{POISON}/poison_scene_proof.emp",          "P1 proof",   "differs at cfg field 4 (band field -1)", 1),
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
