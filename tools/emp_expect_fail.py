#!/usr/bin/env python3
"""emp_expect_fail — the tree's negative-build lane (Parcel R1, spec §10.4).

Each case is a poison .emp module that MUST fail to build, with the expected guard
message fragment. A case passes iff the real build exits nonzero AND its output
contains the fragment. Poison modules live in games/sonic4/test/poison/: syntactically
valid (the manifest scan parses them on EVERY build), never imported by a real entry,
evaluated only by this lane.

BACKEND — the carrier (temporary, aeon-side, Fable-ruled 2026-08-17)
----------------------------------------------------------------------
R1 Task 7's invocation (`sigil emp <poison> --root <aeon-root>`) evaluates the given
module as the entry of a whole-tree manifest scan, and its own top-level `ensure`s run
regardless of reachability. THAT IS TRUE ONLY OF A SELF-CONTAINED POISON. R1 Task 8's
seven poisons each reach a real guard in `engine/effects/raster_dsl.emp`, and `sigil emp
--root` (`run_emp_program`, sigil-cli/src/main.rs) does NOT apply the two manifest
rewrites `sigil build` applies (`sigil-harness/src/native.rs`, `build_emp`):

    publicize_helper_comptime(&mut manifest, COMPTIME_HELPERS)
    normalize_helper_imports(&mut manifest, COMPTIME_HELPERS, &[])

so the helper vocabulary raster_dsl's guards depend on is not in scope under that
invocation. Measured 2026-08-17, full derivation in docs/BUGS.md (EFX-10).

The proper fix is sigil-side: `--extra-entry <module>` on `sigil build`, which would
elaborate a poison inside the real profile by adding it to `synthetic_entry_src`'s `use`
list. Until that lands, this lane runs each poison through a CARRIER module instead —
`games/sonic4/test/poison_carrier.emp`, a real module already pulled into the real
build's `use` closure (one edge from `games/sonic4/data/effects/ojz_effects.emp`, which
is where R1 Task 8's splice verification already lived). Per case, this script REWRITES
the carrier's body to the poison's body and runs the real `sigil build --native`
invocation on the whole tree — the same shape an author's module would be checked in,
because the carrier IS one. The carrier's canonical resting state (module line + a
short header, nothing else) is restored after every case, on entry (self-heal against
crash residue), and re-verified at the end of the run.

This backend is temporary. It retires — carrier file, use edge, and the mutation this
docstring describes — the day `--extra-entry` lands (docs/BUGS.md EFX-10). A standalone
run of this script has no clean-tree control beyond the self-heal below: build.sh's own
subsequent real build is what actually proves the carrier was left canonical, since that
build only succeeds if the carrier is inert. Running this script in isolation trusts the
self-heal and the final re-read; it does not re-derive them with a second process.
"""
import os, subprocess, sys, pathlib, tempfile, time

AEON = pathlib.Path(__file__).resolve().parent.parent
SIGIL = os.environ.get("SIGIL_BUILD")
if not SIGIL:
    sys.exit("SIGIL_BUILD not set (same contract as build.sh)")

POISON = "games/sonic4/test/poison"
CARRIER = AEON / "games/sonic4/test/poison_carrier.emp"

# The carrier's canonical resting state, embedded here so the lane can self-heal and
# verify it without trusting the on-disk file to already be correct. Must match
# games/sonic4/test/poison_carrier.emp byte-for-byte.
CANONICAL_CARRIER = """// games/sonic4/test/poison_carrier.emp — the expect-fail lane's carrier backend (EFX-10).
//
// Temporary, aeon-side. Fable-ruled 2026-08-17 as the interim fix for EFX-10
// (docs/BUGS.md): `sigil emp --root` cannot elaborate a poison that reaches a
// real guard, because it skips the `publicize_helper_comptime` /
// `normalize_helper_imports` manifest rewrites `sigil build` applies. This file
// sidesteps that hole by being a REAL module inside the real build's `use`
// closure — tools/emp_expect_fail.py REWRITES this file's body per case (the
// canonical module line below plus one poison's body, verbatim) and invokes
// `sigil build --native` on the whole tree, then restores this file to exactly
// the form below.
//
// This is the file's CANONICAL RESTING STATE: the module line and this comment
// block, nothing else. Zero bytes, ensures-only — outside a lane run this
// module declares no data, no code, no `ensure`, and changes no build output.
//
// Removal condition: retire this file (and the mutation it exists to avoid)
// the day `--extra-entry <module>` lands on `sigil build` — the properly-scoped
// fix named in docs/BUGS.md EFX-10, which elaborates a poison inside the real
// profile without needing a host module's body rewritten out from under it.
module games.sonic4.test.poison_carrier
"""

SENTINEL_BODY = (
    'ensure(false, "POISON_CARRIER_SENTINEL — if this builds clean the carrier fell '
    'out of the build closure and every case below is vacuous")\n'
)

# (poison module path relative to AEON, entry id, expected message fragment, expected
# [Error] count). Count defaults to 1 — one poison, one legitimately-firing guard — and
# is stated explicitly only where a poison is known to trip more than one ensure.
# Moved verbatim from BLOCKED_CASES — the Task 8 poisons, each independently verified
# (by splicing into ojz_effects.emp and running `sigil build`) to trip its guard.
# Task 8 review (2026-08-17) added poison_patchable_partner.emp (rule 6 half 2, review
# I-2) and poison_direct_8a.emp (the $8A direct-construction clause, review I-3), and
# corrected 8b C-A's count to 2: it legitimately trips BOTH the "would bury" ensure
# (its own unequal-span intersecting op) AND the isect_earlier count ensure (2
# strictly-earlier intersecting ops, only one of which is the equal-span partner) —
# see the poison's own header comment. The two $8F cases (8d D-C and 8d E-D) now expect
# DISTINCT fragments so a case passing does not merely mean "the string 'autoincrement'
# appeared somewhere": D-C is the reg_set constructor's own ensure (fragment "assumes
# stride 2"), E-D is the program-level scan that catches direct enum construction
# (fragment "cannot be dodged").
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
]


def read_carrier() -> str:
    return CARRIER.read_text()


def write_carrier(body: str) -> None:
    CARRIER.write_text(body)


def poison_body(path: pathlib.Path) -> str:
    """Everything after the poison's own `module ...` line, verbatim."""
    lines = path.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("module "):
            return "".join(lines[i + 1:])
    sys.exit(f"emp_expect_fail: {path} has no `module` line — cannot carry it")


def run_build() -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as td:
        out_bin = os.path.join(td, "probe.bin")
        p = subprocess.run(
            [SIGIL, "build", "--aeon", ".", "--native", "--game", "sonic4", "-o", out_bin],
            capture_output=True, text=True, cwd=AEON,
        )
    return p.returncode, p.stdout + p.stderr


def run_one(label: str, carrier_body: str, expect: str, want_clean: bool,
            expect_count: int = 1) -> tuple[bool, str, float, str]:
    """Write carrier_body, run the real build, restore canonical, evaluate.

    The canonical restore runs on ANY exit from the build step — normal return,
    a raised exception, or KeyboardInterrupt — via try/finally, so a case that dies
    mid-build (Ctrl-C, a sigil crash) cannot leave the carrier holding a poison's
    body. This is belt-and-suspenders with main()'s own crash-residue self-heal
    (that self-heal covers the NEXT run after a residue-leaving crash; this one is
    what makes that residue rare in the first place).

    Returns (ok, why, elapsed_seconds, raw_output).
    """
    write_carrier(CANONICAL_CARRIER + carrier_body)
    try:
        t0 = time.monotonic()
        rc, out = run_build()
        elapsed = time.monotonic() - t0
    finally:
        write_carrier(CANONICAL_CARRIER)

    if want_clean:
        # not used (kept for symmetry / future self-contained cases)
        if rc == 0:
            return True, "ok", elapsed, out
        return False, f"expected a clean build, got exit {rc}", elapsed, out

    if rc == 0:
        return False, f"BUILT CLEAN — the guard did not fire ({label})", elapsed, out
    if expect not in out:
        tail = " | ".join(out.strip().splitlines()[-3:])
        return False, (
            f"failed WITHOUT the expected fragment {expect!r} — wording drift or "
            f"wrong guard; got: {tail}"
        ), elapsed, out
    got_count = out.count("[Error]")
    if got_count != expect_count:
        tail = " | ".join(out.strip().splitlines()[-3:])
        return False, (
            f"fragment {expect!r} present but got {got_count} [Error] diagnostic(s), "
            f"expected {expect_count} — a diagnostic count drift can mean a guard "
            f"stopped firing (or a NEW one started); got: {tail}"
        ), elapsed, out
    return True, "ok", elapsed, out


def main() -> int:
    if not CARRIER.is_file():
        print(f"emp_expect_fail: FAIL — carrier module missing: {CARRIER}")
        return 1

    # Trap 1: crash residue. A previous run that died mid-case (Ctrl-C, OOM, a sigil
    # crash) can leave the carrier poisoned on disk. Self-heal before doing anything
    # else, loudly, so a poisoned carrier is never silently mistaken for canonical.
    on_disk = read_carrier()
    if on_disk != CANONICAL_CARRIER:
        print("emp_expect_fail: CRASH RESIDUE — carrier was left poisoned by a "
              "previous run; self-healed")
        write_carrier(CANONICAL_CARRIER)

    missing = [c for c in CASES if not (AEON / c[0]).is_file()]
    if missing:
        print("emp_expect_fail: FAIL — CASES names poison modules that do not exist:")
        for path, entry, _, _ in missing:
            print(f"  {entry}: {path}")
        return 1

    bad = 0

    # CASE 0, permanent, first: the sentinel. If this builds clean, the carrier is not
    # actually in the build's `use` closure and every case below is testing nothing.
    ok, why, elapsed, out = run_one("sentinel", SENTINEL_BODY, "POISON_CARRIER_SENTINEL",
                                     want_clean=False, expect_count=1)
    print(f"  {'PASS' if ok else 'FAIL'}  sentinel ({elapsed:.2f}s): {why}")
    if not ok:
        print("emp_expect_fail: FAIL — the sentinel did not fire. The carrier has "
              "fallen out of the real build's `use` closure (check the `use` edge in "
              "games/sonic4/data/effects/ojz_effects.emp); every case below would be "
              "vacuous, so this run stops here.")
        return 1

    for path, entry, expect, expect_count in CASES:
        body = poison_body(AEON / path)
        ok, why, elapsed, out = run_one(entry, body, expect, want_clean=False,
                                         expect_count=expect_count)
        print(f"  {'PASS' if ok else 'FAIL'}  {entry} ({elapsed:.2f}s): {why}")
        bad += 0 if ok else 1

    # Final restore + verify. run_one already restores after every case, including the
    # last one, but re-read the file rather than trust that write succeeded.
    write_carrier(CANONICAL_CARRIER)
    final = read_carrier()
    if final != CANONICAL_CARRIER:
        print("emp_expect_fail: FAIL — carrier did not return to canonical rest after "
              "the run. DO NOT COMMIT the tree in this state.")
        return 1

    print(f"emp_expect_fail: {'OK' if not bad else 'FAIL'} — {len(CASES) - bad}/{len(CASES)} cases")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
