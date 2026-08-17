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
"""
import os, subprocess, sys, pathlib

AEON = pathlib.Path(__file__).resolve().parent.parent
SIGIL = os.environ.get("SIGIL_BUILD")
if not SIGIL:
    sys.exit("SIGIL_BUILD not set (same contract as build.sh)")

# (poison module path relative to AEON, entry id, expected message fragment)
CASES: list[tuple[str, str, str]] = [
    # populated by R1 Task 8 — one line per guard poison
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
    if not CASES:
        print("emp_expect_fail: OK — no cases registered yet (R1 Task 8 adds them)")
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
