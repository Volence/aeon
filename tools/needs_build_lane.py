#!/usr/bin/env python3
"""needs_build_lane — run the `@pytest.mark.needs_build` tests and grade the LANE, not just the tests.

WHY THIS EXISTS (LS-1b, 2026-09-06).

LS-1 split the tool-suite pytest lane around the sigil build: tests that read a build
artifact out of the working tree carry `@pytest.mark.needs_build(<artifact>...)`,
`build.sh`'s pre-build lane deselects them, and a post-sigil lane runs exactly them
against the listing THIS invocation emitted. That fixed a nine-night outage.

It also stopped running one test. `tools/test_effects_gates_segments.py::
test_segmented_parent_checks_the_row_set_it_aggregated` declares THREE artifacts —
`s4.debug.bin`, `s4.debug.lst`, `demo.debug.lst` — and one `build.sh` invocation
writes exactly one game's `.bin`/`.lst` pair (`ROM_NAME` is a single scalar threaded
through `-o` and `--emit-lst`, and there is exactly one `${SIGIL_BUILD} build` call).
So no shape can produce all three, and under `--artifacts-built-after ${SIGIL_T0}` that
test DEFERS in all four canonical shapes. It is the exact test whose failure killed the
nightly nine times. A gate that stopped running is this tree's own definition of a
vacuous gate, so it was booked as a debt, not accepted.

`tools/nightly_effects_gates.sh` is the one place several shapes are built back to back
in one checkout, so it is the only place the whole marked lane is reachable. This tool
is the lane it runs there. It is NOT wired into `build.sh` and must not be: `build.sh`
structurally cannot make the artifact set, and bolting a second game's build onto it
would change what one invocation means.

THE GRADE IS ABOUT THE LANE, WHICH IS THE WHOLE POINT

  exit 0  every collected marked test RAN and passed.
  exit 1  at least one marked test ran and FAILED.
  exit 2  the lane could not answer: nothing was collected, a marked test DEFERRED
          (an artifact it declared is absent or older than --built-after), pytest
          itself failed to run, or the JUnit report is missing/unreadable.

A DEFERRAL IS EXIT 2 AND NEVER A PASS. In `build.sh` a deferral is legitimate — no
single shape produces every artifact — but in the caller that builds every shape the
lane declares, a deferral means an artifact that was supposed to be written was not.
Reporting green there would rebuild, one level up, exactly the defect LS-1 closed: a
lane that reports success because its subject did not run. `pytest` cannot express
this: its exit status is 0 when every test was skipped, which is why the decision is
made here from the JUnit report rather than from a return code.

WHAT `--built-after` CLAIMS (since LS-1a, 2026-09-12). It is forwarded to
tools/conftest.py as `--artifacts-built-after`, where a declared artifact is usable
only when tools/artifact_provenance.py calls its (.bin, .lst) pair FRESH: both written
at or after the threshold (the caller's own build wrote them) AND the listing's Source
Digest reproduces (the ROM it names, every file the build read, the module scan, the
assembler). Until then this paragraph said the lane checked time only and that content
was nobody's question here; a `touch`ed or content-stale artifact read as fresh. This
file still does no comparison of its own: the verdict is the primitive's, the same one
every build.sh gate uses. The threshold is a whole second, and `date +%s` truncates
DOWN, so a file written in the same second counts as written after it. Passing nothing
grades whatever is on disk, which is right for a hand run and wrong for a lane.

THE POPULATION CHECK IS DIRECTIONAL ON PURPOSE. The count of `@pytest.mark.needs_build`
decorators in the tests directory is a source-derived floor on how many test cases the
run must contain. FEWER cases than decorators means markers exist that the run did not
reach (a collection error, a drifted `-m` expression) and is exit 2. MORE is fine and
must stay fine: one decorator on a parametrized or class-level test legitimately yields
several cases, and a check that went red on that would be a maintenance trap rather
than a gate. Deleting a marker outright is NOT caught here — decorator count and case
count fall together — which is why the count is also PRINTED: the log is the record.
"""

import argparse
import ast
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

TOOLS = os.path.dirname(os.path.abspath(__file__))
MARKER = "needs_build"


def decorator_count(tests_dir):
    """How many `@pytest.mark.needs_build(...)` decorators the tests directory carries.

    PARSED, NOT GREPPED, and that is not fastidiousness: the first regex version of this
    counted 6 in a tree that has 4, because `tools/test_needs_build_lane.py` builds its
    synthetic fixtures out of a triple-quoted string whose lines begin with the decorator
    at column 0. A grep cannot tell a decorator from a decorator inside a string, and the
    consequence was the lane refusing to run — exit 2 with "markers the run never reached"
    — on a perfectly healthy tree. A gate that goes red on nothing is worse than absent.

    A syntactically broken module counts ZERO here rather than raising: the case count
    would drop with it, so the directional floor still fires, and pytest's own collection
    error is the better message for that.
    """
    n = 0
    for name in sorted(os.listdir(tests_dir)):
        if not name.endswith(".py"):
            continue
        try:
            with open(os.path.join(tests_dir, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(target, ast.Attribute) and target.attr == MARKER:
                    n += 1
    return n


def run_pytest(tests_dir, built_after, junit, extra=()):
    """Run the marked lane, writing a JUnit report. Returns pytest's exit status."""
    cmd = [sys.executable, "-m", "pytest", tests_dir, "-q", "-p", "no:cacheprovider",
           "-m", MARKER, "--junit-xml=%s" % junit]
    if built_after is not None:
        cmd += ["--artifacts-built-after", str(built_after)]
    cmd += list(extra)
    print("$ %s" % " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=os.path.dirname(tests_dir)).returncode


def classify(junit):
    """(cases, failed, deferred) out of a JUnit report.

    `cases` is every testcase element as "classname::name"; `failed` and `deferred` are
    (label, message) pairs. A <skipped> case is a DEFERRAL: `tools/conftest.py` turns a
    marked test that skips WITH its inputs on disk into a failure, so the only skip that
    survives to here is one the collection hook deferred for a missing or stale artifact.
    """
    root = ET.parse(junit).getroot()
    cases, failed, deferred = [], [], []
    for tc in root.iter("testcase"):
        label = "%s::%s" % (tc.get("classname", "?"), tc.get("name", "?"))
        cases.append(label)
        for child in tc:
            msg = (child.get("message") or child.text or "").strip().splitlines()
            msg = msg[0] if msg else ""
            if child.tag in ("failure", "error"):
                failed.append((label, "%s: %s" % (child.tag, msg)))
            elif child.tag == "skipped":
                deferred.append((label, msg))
    return cases, failed, deferred


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tests", default=TOOLS,
                    help="directory of the test suite (default: this tool's own directory)")
    ap.add_argument("--built-after", type=int, default=None, metavar="EPOCH",
                    help="PROVENANCE threshold: a declared artifact older than EPOCH is a "
                         "deferral, i.e. exit 2. Pass the instant the caller's first build "
                         "began. Omitting it grades whatever is on disk.")
    ap.add_argument("--junit", default=None,
                    help="where to write the JUnit report (default: a temporary file)")
    args, extra = ap.parse_known_args(argv)

    tests_dir = os.path.abspath(args.tests)
    declared = decorator_count(tests_dir)
    print("needs_build lane over %s" % tests_dir)
    print("  %d @pytest.mark.%s decorator(s) in the tests directory" % (declared, MARKER))
    print("  provenance threshold: %s" % (
        args.built_after if args.built_after is not None
        else "NONE — grading whatever is on disk (hand-run mode)"))

    tmp = None
    junit = args.junit
    if junit is None:
        fd, tmp = tempfile.mkstemp(prefix="needs_build_", suffix=".xml")
        os.close(fd)
        junit = tmp
    try:
        rc = run_pytest(tests_dir, args.built_after, junit, extra)
        try:
            cases, failed, deferred = classify(junit)
        except (OSError, ET.ParseError) as exc:
            print("\nCOULD NOT RUN: no readable JUnit report at %s (%s); pytest exit %d."
                  % (junit, exc, rc))
            print("  The lane's verdict is read from that report, not from pytest's exit")
            print("  status, because pytest exits 0 when every test was SKIPPED.")
            return 2
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)

    ran = [c for c in cases if c not in dict(deferred)]
    # pytest's own status is PRINTED and never trusted as the verdict: it is 0 when every
    # marked test was deferred, which is precisely the state this lane exists to catch.
    print("\n  pytest exit %d — %d case(s) in the report: %d ran, %d deferred, %d failed"
          % (rc, len(cases), len(ran), len(deferred), len(failed)))
    # EVERY CASE THAT RAN IS NAMED, not just the ones that went wrong (LS-1c, 2026-09-10).
    # A green log and an absent run are the same artifact: "4 passed" cannot tell a reader
    # WHICH four, and the whole reason this lane exists is one specific test —
    # test_segmented_parent_checks_the_row_set_it_aggregated — that no build.sh shape can
    # reach. A count is not evidence that it ran; its name in the log is. This is also what
    # makes the marker-deletion case visible in practice: the decorator count and the case
    # count fall together silently, but a name that stops appearing does not.
    for label in ran:
        print("  RAN       %s" % label)
    for label, msg in deferred:
        print("  DEFERRED  %s  — %s" % (label, msg))
    for label, msg in failed:
        print("  FAILED    %s  — %s" % (label, msg))

    if not cases:
        print("\nCOULD NOT RUN: the lane collected NO tests (pytest exit %d)." % rc)
        print("  Either nothing carries @pytest.mark.%s any more — which silently restores"
              % MARKER)
        print("  the pre-LS-1 state — or collection failed. An empty lane and a green lane")
        print("  are indistinguishable in an exit status, so this is a failure, not a pass.")
        return 2
    if len(cases) < declared:
        print("\nCOULD NOT RUN: %d decorator(s) in the source but only %d case(s) ran."
              % (declared, len(cases)))
        print("  Markers exist that this run never reached — a collection error, or an `-m`")
        print("  expression that no longer selects them. (MORE cases than decorators is")
        print("  fine and is not checked: one decorator on a parametrized test is several")
        print("  cases.)")
        return 2
    if deferred:
        print("\nCOULD NOT RUN: %d marked test(s) DEFERRED." % len(deferred))
        print("  A deferral means a declared artifact is absent, or older than the")
        print("  provenance threshold above. In build.sh that is legitimate — no single")
        print("  shape writes every artifact. HERE it is not: this lane is run by a caller")
        print("  that builds every shape the marked tests declare, so a deferral means a")
        print("  build did not write what it was supposed to. Reporting a pass on a test")
        print("  that did not run is the exact defect LS-1 closed.")
        return 2
    if failed or rc not in (0,):
        if failed:
            print("\nFAILED: %d marked test(s) failed against artifacts this caller built."
                  % len(failed))
            return 1
        print("\nCOULD NOT RUN: pytest exited %d with no failing case in the report." % rc)
        print("  That is an internal error, a usage error or an interrupt — not a verdict.")
        return 2
    print("\nOK — all %d marked test(s) ran and passed." % len(cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
