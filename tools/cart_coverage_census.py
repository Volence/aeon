#!/usr/bin/env python3
"""cart_coverage_census — how many bus-reaching tools can be measuring the WRONG cart.

WHY THIS IS A COMMITTED TOOL AND NOT A SHELL LOOP. The `CART-VERIFY-COVERAGE` row in
`docs/DEFERRED_WORK.md` published its count WRONG THREE TIMES — twice a bad matcher
(numerator), once a bad population (denominator) — and every wrong number was
plausible, quotable and in the same direction of alarm. A one-off `grep | wc -l`
re-derives none of that; this file re-derives all of it on demand, carries BOTH
controls in the same loop shape as the real question, and FAILS if a control does
not behave.

    python3 tools/cart_coverage_census.py            # print the census
    python3 tools/cart_coverage_census.py --check    # + exit 1 if a control misbehaves

TWO LOOPS, and both get both controls, because the three wrong counts were split
across them:

  ENUMERATION (who is in the population at all) — by what a file IMPORTS, parsed with
  `ast`, not grepped. Grep is what matched `int.from_bytes(...)` for `rom_bytes` and
  what missed the tools that reach the bus through a bare `from aether import
  BusClient`. Controls: a bogus module name must hit 0, and three CANARIES -- one per
  matcher arm that uniquely reaches any file -- must all still be in the population.
  The run also prints how many files each arm reaches ALONE, because an arm reaching 0
  files alone is an arm no control can cover, and a green canary set must not be read
  as proof that such an arm works.

  CLASSIFICATION (who INHERITS the spawner's check) — by CALL SITES, not by imports.
  This is a correction to the row's own framing and it moves the number: five files
  import `assert_rust_server` from `aether_instance` and then spawn `oracle-aether`
  with their own `subprocess.Popen`. They import the spawner module and do not use the
  spawner, so a check inside `AetherInstance` does not reach them. Counting them as
  covered would be exactly the "names are not behaviour" error. Controls: a bogus
  token must hit 0; a token every population member must contain hits all of them.

The categories a non-inheriting tool falls into are reported separately, because they
need different fixes and only one of them is in this parcel's reach.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent

# Excluded from the population: the helper modules themselves (they ARE the seam under
# test, not users of it) and pytest files (they exercise the seam deliberately, often
# with fakes, so "does this measure the wrong cart" is not a question about them).
# BOTH exclusions are choices. Vary them with --keep-tests / --keep-helpers and the
# numbers move; that is the point of making them flags rather than silent constants.
HELPER_MODULES = {"aether_instance.py", "cart_identity.py", "aether_bytes.py"}

# POSITIVE CONTROL for the enumeration loop, and getting it right took two goes. The
# first version was four "obviously different" members — fg_left_edge_gate (imports
# AetherInstance), band_witness (imports aether_emulator), evict_witness (bare BusClient),
# warp_mailbox_gate (imports assert_rust_server and spawns by hand). It looked like four
# routes. IT WAS NOT: breaking the `mod == "aether_instance"` arm outright left all four
# canaries in the population and the census exited 0. Every one of those four is reached
# by MORE THAN ONE arm, so no single-arm break can drop any of them.
#
# MEASURED ARM CONTRIBUTION (printed live on every run, so it cannot go stale silently):
#   mod-only  (`from aether_instance import <anything>` and nothing else)   1 file
#   name-only (`aether_emulator` / `AetherInstance` by name and nothing else)  0 files
#   bus-only  (bare `from aether import BusClient`)                        17 files
#
# So the NAME arm is currently REDUNDANT — it is kept for files that may arrive later,
# and a canary cannot cover it because no file needs it. Saying that out loud is the
# point: otherwise a green canary set reads as proof all three arms work.
#
# The canaries are therefore the two files that ARE uniquely reachable, one per
# load-bearing arm, plus one ordinary member as a shape check.
CANARIES = {
    "depth_onset_probe.py":  "the ONLY file reached solely by the `aether_instance` arm",
    "evict_witness.py":      "reached solely by the bare `from aether import BusClient` arm",
    "fg_left_edge_gate.py":  "an ordinary member (the row's own model tool)",
}


def imports_of(path: Path):
    """Every (module, name) this file imports, from the AST. None if it will not parse."""
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except SyntaxError:
        return None
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.add((a.name, None))
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                out.add((n.module or "", a.name))
    return out


def arm_mod(imps) -> bool:
    """Arm 1: imports anything out of the spawner module, by any spelling."""
    return any(m == "aether_instance" or m.endswith(".aether_instance") for m, _ in imps)


def arm_name(imps) -> bool:
    """Arm 2: names the spawner itself. Measured REDUNDANT today — 0 files need it."""
    return any(n in ("aether_emulator", "AetherInstance") for _, n in imps)


def arm_bus(imps) -> bool:
    """Arm 3: a bare `from aether import BusClient`, naming no helper at all."""
    return any(m == "aether" and n == "BusClient" for m, n in imps)


ARMS = (("mod", arm_mod), ("name", arm_name), ("bus", arm_bus))


def reaches_bus(imps) -> bool:
    """The enumeration parameter: what a file IMPORTS. Any arm.

    Split into named arms rather than written as one `or` chain so the run can report
    which of them are actually load-bearing. That report is what caught the
    canary set being unable to fail: see CANARIES.
    """
    return any(fn(imps) for _, fn in ARMS)


def calls_spawner(src: str) -> bool:
    """CALL SITES, not imports: does this file actually construct the spawner?"""
    return "aether_emulator(" in src or "AetherInstance(" in src


def spawn_style(src: str, imps, siblings: set[str]) -> str:
    """How a non-inheriting file gets to a bus. The four differ in fixability.

    The `borrows` arm is not cosmetic. `depth_onset_probe.py` has no `Popen` and no
    socket constant of its own; it does `from curve_desc_probe import Server` and every
    emulator it drives is that sibling's hand-rolled one. Classified on its own text it
    falls through to "attaches to an already-running socket", which is FALSE and would
    have put it in the wrong fix bucket.
    """
    if "headless_emulator(" in src:
        return "legacy launcher.headless_emulator"
    if "subprocess.Popen(" in src and ("oracle-aether" in src or "SERVER" in src
                                       or "BIN" in src):
        return "hand-rolled subprocess.Popen of oracle-aether"
    for mod, name in imps:
        if mod in siblings and name in ("Server", "Emu", "Instance"):
            return f"borrows a sibling tool's hand-rolled Server ({mod})"
    return "attaches to an already-running socket"


def census(tools_dir: Path, keep_tests=False, keep_helpers=False):
    files = sorted(tools_dir.glob("*.py"))
    parsed, unparsed = {}, []
    for p in files:
        imps = imports_of(p)
        if imps is None:
            unparsed.append(p.name)
        else:
            parsed[p] = imps

    bus = [p for p, i in parsed.items() if reaches_bus(i)]
    dropped_tests = [] if keep_tests else [p for p in bus if p.name.startswith("test_")]
    dropped_help = [] if keep_helpers else [p for p in bus if p.name in HELPER_MODULES]
    drop = set(dropped_tests) | set(dropped_help)
    pop = sorted(p for p in bus if p not in drop)
    src = {p: p.read_text(errors="replace") for p in pop}

    inherits = [p for p in pop if calls_spawner(src[p])]
    residual = [p for p in pop if p not in inherits]
    return dict(files=files, parsed=parsed, unparsed=unparsed, bus=bus,
                dropped_tests=dropped_tests, dropped_help=dropped_help,
                pop=pop, src=src, inherits=inherits, residual=residual)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if either control in either loop misbehaves")
    ap.add_argument("--keep-tests", action="store_true")
    ap.add_argument("--keep-helpers", action="store_true")
    ap.add_argument("--dir", default=str(TOOLS_DIR))
    a = ap.parse_args()
    c = census(Path(a.dir).resolve(), a.keep_tests, a.keep_helpers)
    parsed, pop, src = c["parsed"], c["pop"], c["src"]
    bad = []

    print("=== ENUMERATION LOOP — what a file IMPORTS (ast, not grep) ===")
    # BOTH controls read the SAME `imps` object the real question reads, in the same
    # loop. That is what makes the positive one load-bearing: if `imports_of` silently
    # returned empty sets, the bogus-module control would still be 0 and the real
    # question would be 0, and nothing would say the instrument had stopped working.
    # "every parsed file imports SOMETHING" is the cheapest statement that goes red then.
    neg = [p for p, i in parsed.items() if any(m == "zz_no_such_module_zz" for m, _ in i)]
    posn = [p for p, i in parsed.items() if len(i) > 0]
    noimp = sorted(p.name for p, i in parsed.items() if not i)
    in_pop = {p.name for p in pop}
    missing_canaries = sorted(n for n in CANARIES if n not in in_pop)
    print(f"  tools/*.py parsed                : {len(parsed)}"
          + (f"   UNPARSED: {c['unparsed']}" if c["unparsed"] else ""))
    print(f"  CONTROL-  bogus module import    : {len(neg)}   (must be 0)")
    print(f"  CONTROL+  canaries in population : {len(CANARIES) - len(missing_canaries)}"
          f" of {len(CANARIES)}   (must be all)")
    for name, why in sorted(CANARIES.items()):
        print(f"      {'MISSING  ' if name in missing_canaries else 'present  '}"
              f"{name:26s} {why}")
    print(f"  (informational) import anything  : {len(posn)} of {len(parsed)}"
          f"   zero-import files: {noimp}")
    if neg:
        bad.append("enumeration negative control matched something")
    if missing_canaries:
        bad.append(f"enumeration positive control LOST known members: {missing_canaries}")

    # WHICH ARMS ARE LOAD-BEARING. A file reached by two arms cannot fall out when one
    # breaks, so an arm with 0 unique files is an arm no control can cover — and a
    # canary set that does not say so reads as proof of coverage it does not have.
    print("  arm contribution (files reached by THIS ARM ALONE):")
    for label, fn in ARMS:
        others = [f for lbl, f in ARMS if lbl != label]
        uniq = sorted(p.name for p, i in parsed.items()
                      if fn(i) and not any(o(i) for o in others))
        note = "  <- REDUNDANT: no control can cover this arm" if not uniq else ""
        print(f"      {label:5s}: {len(uniq):3d}{note}"
              + ("   " + ", ".join(uniq) if 0 < len(uniq) <= 3 else ""))
        if uniq and not any(n in CANARIES for n in uniq):
            bad.append(f"arm {label!r} uniquely reaches {len(uniq)} file(s) and NO canary "
                       f"covers it — a break in it would pass silently")
    print(f"  reach a bus (spawner OR direct)  : {len(c['bus'])}")
    print(f"    minus test_*                   : -{len(c['dropped_tests'])}")
    print(f"    minus helper modules           : -{len(c['dropped_help'])} "
          f"{sorted(p.name for p in c['dropped_help'])}")
    print(f"  POPULATION                       : {len(pop)}")
    print()

    print("=== CLASSIFICATION LOOP — CALL SITES, over the population only ===")
    cneg = [p for p in pop if "zz_no_such_token_zz" in src[p]]
    cpos = [p for p in pop if "import" in src[p]]
    print(f"  CONTROL-  bogus token            : {len(cneg)} of {len(pop)}   (must be 0)")
    print(f"  CONTROL+  contains 'import'      : {len(cpos)} of {len(pop)}   "
          f"(must be {len(pop)})")
    if cneg:
        bad.append("classification negative control matched something")
    if len(cpos) != len(pop):
        bad.append("classification positive control did not match every member")
    print(f"  CONSTRUCT the spawner            : {len(c['inherits'])} of {len(pop)}"
          f"   -> inherit the cart check")
    print(f"  reach a bus WITHOUT the spawner  : {len(c['residual'])} of {len(pop)}"
          f"   -> RESIDUAL EXPOSURE")
    print()

    print("=== RESIDUAL EXPOSURE, by how each one gets its bus ===")
    siblings = {p.stem for p in c["files"]}
    by_style: dict[str, list[str]] = {}
    for p in c["residual"]:
        by_style.setdefault(spawn_style(src[p], parsed[p], siblings), []).append(p.name)
    for style in sorted(by_style):
        names = sorted(by_style[style])
        print(f"  {style}  ({len(names)})")
        for n in names:
            print(f"      {n}")
    print()

    print("=== WHO ASKS THE CART QUESTION IN THEIR OWN SOURCE ===")

    def compares_rombytes(s: str) -> bool:
        """`romBytes` MENTIONED is not `romBytes` CHECKED.

        The row's own second wrong count came from a matcher that counted mentions. A
        mention is a read; what defends a run is a COMPARISON that raises. So require
        `romBytes` and a comparison operator on the SAME line — crude, but it is a
        different question from "contains the word", and the two numbers are printed
        side by side so the gap between them is visible rather than assumed.
        """
        return any("romBytes" in ln and ("!=" in ln or "==" in ln) for ln in s.splitlines())

    checks = [("import cart_identity", lambda s: "cart_identity" in s),
              ("mention romBytes", lambda s: "romBytes" in s),
              ("COMPARE romBytes", compares_rombytes),
              ("hash via memory_hash", lambda s: "memory_hash" in s),
              ("call reload_rom", lambda s: "reload_rom" in s)]
    verified = set()
    for label, fn in checks:
        names = sorted(p.name for p in pop if fn(src[p]))
        if label in ("import cart_identity", "COMPARE romBytes", "hash via memory_hash"):
            verified.update(names)
        print(f"  {label:24s}: {len(names):3d} of {len(pop)}"
              + ("   " + ", ".join(names) if len(names) <= 8 else ""))
    # The headline: a tool is DEFENDED if it inherits the spawner check or asks in its
    # own source. Both halves are counted, because a hand-rolled check is still a check.
    #
    # WHETHER THE SPAWNER CHECKS IS READ OUT OF THE TREE BEING MEASURED, not assumed.
    # That is what lets `--dir` be pointed at a checkout of an older commit and produce a
    # BEFORE number from the same instrument as the AFTER number — which is the only way
    # the two are comparable at all.
    spawner_src = (Path(a.dir).resolve() / "aether_instance.py")
    spawner_checks = (spawner_src.is_file()
                      and "assert_cart_matches_disk" in spawner_src.read_text(errors="replace"))
    print(f"  spawner verifies the cart: {spawner_checks}"
          f"   ({spawner_src})")
    inherit_names = {p.name for p in c["inherits"]} if spawner_checks else set()
    defended = inherit_names | verified
    print(f"  {'DEFENDED (either way)':24s}: {len(defended):3d} of {len(pop)}")
    print(f"  {'UNDEFENDED':24s}: {len(pop) - len(defended):3d} of {len(pop)}")

    if bad:
        print()
        print("CONTROLS MISBEHAVED — this census is NOT a measurement:")
        for b in bad:
            print(f"  * {b}")
        return 1
    if a.check:
        print()
        print("controls OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
