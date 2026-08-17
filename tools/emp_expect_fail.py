#!/usr/bin/env python3
"""emp_expect_fail — the tree's negative-build lane (Parcel R1, spec §10.4).

Each case is a poison .emp module that MUST fail to build, with the expected guard
message fragment. A case passes iff sigil exits nonzero AND its output contains the
fragment. Known properties (spec [S5-10]): the manifest scan parses the WHOLE --root
tree per invocation (CI cost, not soundness), and the message match is fragile against
wording edits — a wrong/missing message still FAILS here (so drift is caught), but
attribute failures to wording first. Poison modules live in games/sonic4/test/poison/:
syntactically valid (the scan parses them on EVERY build), never imported by a real
entry, evaluated only by this lane.

Invocation form (verified by experiment, R1 Task 7): `sigil emp <module.emp> --root
<aeon-root>` evaluates the given module as the ENTRY of a whole-tree manifest scan —
its own top-level `ensure`s always run (entry modules are exempt from the
`module.unreachable` skip that applies to everything else NOT pulled in by `use`), no
ROM is emitted, and the process exits nonzero iff any `ensure` in the entry module
fired. `sigil emp` has no separate `--entry` flag; the input path itself IS the entry.

THAT VERIFICATION WAS INCOMPLETE, and R1 Task 8 is where it broke. Everything above is
true of a SELF-CONTAINED poison — one whose `ensure` names nothing outside itself. It is
false of every poison that has to reach a real guard, because `sigil emp --root`
(`run_emp_program`, sigil-cli/src/main.rs) does NOT apply the two manifest rewrites that
`sigil build` applies (`sigil-harness/src/native.rs`, `build_emp`):

    publicize_helper_comptime(&mut manifest, COMPTIME_HELPERS)
    normalize_helper_imports(&mut manifest, COMPTIME_HELPERS, &[])

Measured 2026-08-17, three failures deep, each one blocking the next:

  1. A poison that names `raster_program` gets `unknown function raster_program` — the
     helper globs are what put it in scope in an ordinary module.
  2. Adding `use engine.effects.raster_dsl.*` fixes that name and NOT the guard, because
     `raster_program`'s BODY resolves its free names at the CALL SITE and raster_dsl's
     own helpers (`fire_ops`, `arm_at`, `check_intervals`, `op_stream_words`, …) are
     PRIVATE. A glob imports only `pub` items; it is `publicize_helper_comptime` that
     makes them importable in the real build. Result: 20+ `unknown function` errors
     inside raster_dsl itself.
  3. The `use` also drags `engine.effects.raster` into the closure, which resolves
     `RASTER_MAX_PATCH` / `vdp_comm_reg` only through those same globs and its RAM
     labels only because `engine.ram` is reachable via the real build's synthetic entry.
     Seeding `engine.ram` from the poison then demands the build's `-D` interface values
     (DEBUG, MAX_RING_BUFFER, COLLECTED_WINDOW_SLOTS), which this lane does not pass.

So NO poison that reaches `raster_program` can be spelled under the current invocation.
The seven Task 8 poisons are written and each is VERIFIED to trip its guard — by
splicing its body into a module that IS in the real build's `use` closure and running
`sigil build`. They are listed in BLOCKED_CASES below, ready to move into CASES verbatim
the day the invocation can elaborate them. Booked as EFX-10 in docs/BUGS.md.

WHAT UNBLOCKS IT (sigil side, not aeon side): give `sigil emp --root` the same helper
treatment `build_emp` performs — the COMPTIME_HELPERS list plus a way to seed extra
reachability (`engine.ram`) and the `-D` interface values. An `--extra-entry <module>`
on `sigil build`, which would add the poison to `synthetic_entry_src`'s `use` list and
elaborate it inside the REAL profile, is the smaller and more faithful change: the
poison would then be checked in exactly the shape an author's module is.
"""
import os, subprocess, sys, pathlib

AEON = pathlib.Path(__file__).resolve().parent.parent
SIGIL = os.environ.get("SIGIL_BUILD")
if not SIGIL:
    sys.exit("SIGIL_BUILD not set (same contract as build.sh)")

POISON = "games/sonic4/test/poison"

# (poison module path relative to AEON, entry id, expected message fragment)
CASES: list[tuple[str, str, str]] = [
    # EMPTY, and not because Task 8 wrote no poisons — see the BLOCKED note in the
    # module docstring. Every entry in BLOCKED_CASES below belongs here.
]

# The Task 8 poisons: written, each verified to trip its guard, none runnable through
# this lane's invocation. Moving a row from here to CASES is the whole re-wiring.
BLOCKED_CASES: list[tuple[str, str, str]] = [
    (f"{POISON}/poison_direct_8f.emp",           "8d E-D",  "autoincrement"),
    (f"{POISON}/poison_regset_8f.emp",           "8d D-C",  "autoincrement"),
    (f"{POISON}/poison_two_restores.emp",        "8a",      "one band per program"),
    (f"{POISON}/poison_band_buried_tint.emp",    "8b C-A",  "would bury"),
    (f"{POISON}/poison_patchable_band_fire.emp", "8b rule6", "must be static"),
    (f"{POISON}/poison_setreg_on_restore.emp",   "8c D-B",  "carries the restore ONLY"),
    (f"{POISON}/poison_ship_plus_restore.emp",   "8e claim6", "offscreen_ship"),
]

def run_case(path: str, entry: str, expect: str) -> tuple[bool, str]:
    p = subprocess.run([SIGIL, "emp", path, "--root", str(AEON)],
                       capture_output=True, text=True, cwd=AEON)
    out = p.stdout + p.stderr
    if p.returncode == 0:
        return False, f"BUILT CLEAN — the guard did not fire ({path})"
    if expect not in out:
        tail = " | ".join(out.strip().splitlines()[-3:])
        return False, f"failed WITHOUT the expected fragment {expect!r} — wording drift or wrong guard; got: {tail}"
    return True, "ok"

def main() -> int:
    # A lane that runs nothing must SAY it runs nothing. Printing "OK" over an empty
    # case list is the vacuous-gate shape this tree has a documented history of, so the
    # skip is loud, names its blocker, and counts the poisons it is failing to run.
    missing = [c for c in BLOCKED_CASES if not (AEON / c[0]).is_file()]
    if missing:
        print("emp_expect_fail: FAIL — BLOCKED_CASES names poison modules that do not exist:")
        for path, entry, _ in missing:
            print(f"  {entry}: {path}")
        return 1
    if not CASES:
        print(f"emp_expect_fail: SKIPPED — 0 runnable cases, {len(BLOCKED_CASES)} poisons "
              f"written and UNRUNNABLE through `sigil emp --root` (helper injection; "
              f"docs/BUGS.md EFX-10). These guards are NOT gated here:")
        for path, entry, expect in BLOCKED_CASES:
            print(f"  {entry}: expects {expect!r} from {path}")
        return 0
    bad = 0
    for path, entry, expect in CASES:
        ok, why = run_case(path, entry, expect)
        print(f"  {'PASS' if ok else 'FAIL'}  {entry}: {why}")
        bad += 0 if ok else 1
    print(f"emp_expect_fail: {'OK' if not bad else 'FAIL'} — {len(CASES) - bad}/{len(CASES)} cases")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
