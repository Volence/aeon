"""The entity generator's list cap IS the engine's, checked rather than trusted.

`tools/ojz_entity_gen.py` refuses a section whose ring or object list is longer than
`MAX_LIST_ENTRIES`, and it has to carry its own copy of that number: a Python generator
cannot import a `.emp` constant. The engine's value is `pub const MAX_LIST_ENTRIES` in
`engine/system/constants.emp`, the width in bits of each section's collected / killed /
loaded bitmask, which `entity_window.emp` pins against the mask geometry with its own
`ensure` lines. Until this file nothing compared the two (side finding (b) of the
2026-09-11 lens-pins parcel, merge `f1b3fae6`; the pin message beside
`COLLECTED_MASK_BYTES` in `entity_window.emp` says the same in its WHAT THIS PIN DOES NOT
COVER clause).

What a drift costs, in each direction:
  * engine value LOWERED, copy not: the generator accepts a list the masks cannot index.
    Release has no bound on that index (the DEBUG `assert.w ..., lo, #MAX_LIST_ENTRIES`
    lines in entity_window.emp are the only one), so a ring past the mask width sets a bit
    in the neighbouring mask and an object stays dead for the rest of the act.
  * engine value RAISED, copy not: the generator refuses content the engine could hold.
    Loud, but it blames the author's layout for the tool's stale number.

THE ENGINE VALUE IS READ OFF ITS OWN LINE, never retyped here: a second literal in this
file would be one more copy for the next edit to miss. The generator's value is read by
IMPORTING the module, so the test sees the number the refusal code actually compares
against, not a line of text that might not be the one in use.

LOUD WHEN IT CANNOT MEASURE. A missing declaration, a second declaration anywhere under
engine/ or games/, or a right-hand side that is not an integer literal (an expression this
reader cannot evaluate) is a FAILURE naming the file and line. Never a skip: a skipped
comparison reads as a passing one in every aggregate.

RUNNER: build.sh's pre-build tool-suite lane (`python3 -m pytest tools -m "not needs_build"`),
build-fatal in every canonical shape. It reads source only and carries no needs_build marker.

WHAT THIS DOES NOT COVER, so nobody reads a green as more than it is:
  * the other copies in the same header block of ojz_entity_gen.py (SECTION_SIZE,
    MAX_TYPES_PER_SECTION, MAX_SUBTYPE, OEF_TYPE_SHIFT, the OEF_* flag bit numbers), which
    carry the same "must match constants.emp" comment and the same absence of a check;
  * whether MAX_LIST_ENTRIES is the right width for the masks. That is entity_window.emp's
    `COLLECTED_MASK_BYTES * 8 == MAX_LIST_ENTRIES` pin, and nothing here repeats it;
  * FAST=1 and NO_LINT=1 builds, which skip this lane: a copy edited in a FAST loop builds
    green there and fails at the next canonical ./build.sh.
"""
import os
import re
import sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import ojz_entity_gen as GEN  # noqa: E402

NAME = "MAX_LIST_ENTRIES"
AUTHORITY = os.path.join("engine", "system", "constants.emp")
DECL = re.compile(r"^\s*(?:pub\s+)?const\s+" + NAME + r"\s*=\s*(.*?)\s*(?://.*)?$")


def _literal(expr):
    """An integer out of a `.emp` integer literal ($hex, %binary, decimal), else None."""
    if re.fullmatch(r"\$[0-9A-Fa-f]+", expr):
        return int(expr[1:], 16)
    if re.fullmatch(r"%[01]+", expr):
        return int(expr[1:], 2)
    if re.fullmatch(r"[0-9]+", expr):
        return int(expr, 10)
    return None


def _declarations():
    """(relpath, lineno, rhs) for every `const MAX_LIST_ENTRIES =` under engine/ and games/."""
    out = []
    for top in ("engine", "games"):
        for root, _dirs, files in os.walk(os.path.join(REPO, top)):
            for f in sorted(files):
                if not f.endswith(".emp"):
                    continue
                rel = os.path.relpath(os.path.join(root, f), REPO)
                with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                    for n, line in enumerate(fh, 1):
                        m = DECL.match(line)
                        if m:
                            out.append((rel, n, m.group(1)))
    return out


def _engine_value():
    decls = _declarations()
    if not decls:
        pytest.fail("UNMEASURABLE: no `const %s =` found under engine/ or games/. The "
                    "authority was %s; if it moved or was renamed, point this test at the "
                    "new declaration. Do not retype the number here." % (NAME, AUTHORITY))
    if len(decls) != 1 or decls[0][0] != AUTHORITY:
        pytest.fail("expected exactly one declaration of %s, in %s; found %d: %s. A second "
                    "declaration is a second authority, and this test cannot tell which "
                    "one the engine uses." % (NAME, AUTHORITY, len(decls),
                                              ["%s:%d" % (r, n) for r, n, _ in decls]))
    rel, n, rhs = decls[0]
    value = _literal(rhs)
    if value is None:
        pytest.fail("UNMEASURABLE: %s:%d declares %s = %r, which is not an integer literal "
                    "this reader can evaluate. Extend _literal (do not retype the value "
                    "here, and do not skip)." % (rel, n, NAME, rhs))
    return rel, n, value


def test_the_generator_cap_is_the_engine_cap():
    rel, n, engine = _engine_value()
    assert GEN.MAX_LIST_ENTRIES == engine, (
        "tools/ojz_entity_gen.py MAX_LIST_ENTRIES = %d, but %s:%d declares %s = %d. The "
        "generator's refusal would then %s. Change the generator's copy to %d (the engine "
        "constant is the authority: the bitmask widths are derived from it)."
        % (GEN.MAX_LIST_ENTRIES, rel, n, NAME, engine,
           "accept lists the engine's masks cannot index"
           if GEN.MAX_LIST_ENTRIES > engine else
           "refuse lists the engine could hold", engine))
