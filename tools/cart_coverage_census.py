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
  BusClient`. Controls: a bogus module name must hit 0; "every parsed file" must hit
  all of them.

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

# POSITIVE CONTROL for the enumeration loop, and it has to be non-vacuous. "every parsed
# file imports something" is not: it is nearly true by accident, it comes back 287 of 289
# here (two tools/*.py import nothing at all), and a threshold on it invites a fudge.
# These four are hand-verified members of the population reached by FOUR DIFFERENT
# routes, so losing any one of them means a specific arm of `reaches_bus` stopped
# working rather than "the number moved":
#   fg_left_edge_gate.py   `from aether_instance import AetherInstance`  (the row's model)
#   band_witness.py        `from aether_instance import aether_emulator`
#   evict_witness.py       bare `from aether import BusClient`, no spawner import at all
#   warp_mailbox_gate.py   imports `assert_rust_server` only, and spawns by hand
# The last is the one that matters most: it is IN the population and NOT covered by the
# spawner, which is the distinction the classification loop exists to draw.
CANARIES = {"fg_left_edge_gate.py", "band_witness.py", "evict_witness.py",
            "warp_mailbox_gate.py"}


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


def reaches_bus(imps) -> bool:
    """The enumeration parameter: what a file IMPORTS.

    Either arm of the row's definition — the spawner module by any spelling, or a
    direct `from aether import BusClient`.
    """
    for mod, name in imps:
        if mod == "aether_instance" or mod.endswith(".aether_instance"):
            return True
        if name in ("aether_emulator", "AetherInstance"):
            return True
        if mod == "aether" and name == "BusClient":
            return True
    return False


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
          f" of {len(CANARIES)}   (must be all; see CANARIES)")
    print(f"  (informational) import anything  : {len(posn)} of {len(parsed)}"
          f"   zero-import files: {noimp}")
    if neg:
        bad.append("enumeration negative control matched something")
    if missing_canaries:
        bad.append(f"enumeration positive control LOST known members: {missing_canaries}")
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
    for label, tok in (("import cart_identity", "cart_identity"),
                       ("mention romBytes", "romBytes"),
                       ("hash via memory_hash", "memory_hash"),
                       ("call reload_rom", "reload_rom")):
        names = sorted(p.name for p in pop if tok in src[p])
        print(f"  {label:24s}: {len(names):3d} of {len(pop)}"
              + ("   " + ", ".join(names) if len(names) <= 8 else ""))

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
