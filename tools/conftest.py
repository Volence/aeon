"""Pytest configuration for the aeon tool suite — the build-artifact lane split.

WHY THIS FILE EXISTS (LS-1, 2026-09-06).

build.sh ran the tool-suite pytest lane BEFORE the sigil build, and four tests in
it read a build artifact (`s4*.lst` / `s4*.bin` / `demo*.lst`) out of the WORKING
TREE. On a tree carrying a previous build's listing those tests asked a stale
listing about today's source, failed, and build.sh exited at the pytest lane —
BEFORE the sigil invocation that would have refreshed the listing. Nothing in the
loop could clear it: the effects-gate nightly failed nine consecutive nights
(2026-08-29 .. 2026-09-06) at nine DIFFERENT master SHAs, and none of those SHAs
was ever built. Every merge puts a tree in the same state; the only escape anyone
found by hand was deleting the artifact the gate was blocking the regeneration of.

THE FIX IS ORDERING, NOT A STALENESS CHECK. The model is sigil's own gate lane,
which does not jam: it rebuilds its inputs first and only then runs the gates.
Tests that read a build artifact declare it with
`@pytest.mark.needs_build("<artifact>", ...)`; build.sh's PRE-build lane deselects
them (`-m "not needs_build"`) and a POST-sigil lane runs exactly them, against the
listing THIS invocation emitted. Refusing an old listing would have been a
staleness check — it treats the symptom, and leaves the lane unable to reach the
build that fixes it.

THE THREE-STATE AXIS MATTERS AS MUCH AS THE ORDERING. A skipped test reads as a
pass in every aggregate, which is how a listing-reading test in the wrong lane
stayed invisible until it went stale. So:

  * A marked test whose declared artifacts are ALL on disk MUST run. If it skips
    anyway this file converts the skip into a FAILURE. Post-build, with its inputs
    present, a skip is the invisible state and never legitimate.

  * A marked test missing a declared artifact is DEFERRED — printed by nodeid,
    naming the missing files, in the terminal summary AND counted on a line of its
    own. This is legitimate: the four tests want different build shapes, and no
    single `./build.sh` produces all of them (the segments parent needs a DEBUG
    sonic4 *and* a DEBUG demo). Legitimate, but never silent.

  * An UNMARKED test that skips for a reason naming a build artifact is a FAILURE
    telling the author to add the marker — the backstop for a new artifact-reading
    test landing in the pre-build lane. It is deliberately a TEXT heuristic over
    the skip reason, so it cannot see a test that skips for an artifact without
    naming one. It is a net, not a proof; the marker is the proof.

EXISTENCE IS NOT ENOUGH, AND THE FIRST END-TO-END RUN PROVED IT (2026-09-06). The
paragraph that used to stand here said this file reasons about existence alone,
because "post-sigil the listing on disk IS this invocation's". That is true of the
artifact this invocation emitted and FALSE of every other one. One `DEBUG=1
./build.sh` refreshes `s4.debug.*` and touches nothing else; the segments parent
also reads `demo.debug.lst`, which only `DEBUG=1 ./build.sh demo` writes. Measured
on the real jam: with the 2026-08-28 nightly artifacts planted, the split lane got
sigil to run and the ROM rebuilt — the deadlock WAS broken — and then failed on the
one `demo_witness` row that reads the stale demo listing. On a tree where that file
merely EXISTS the failure repeats every night, and `tools/nightly_effects_gates.sh`
exits at the sonic4 build BEFORE it reaches the demo build that would clear it. The
deadlock would have been reproduced one artifact to the left.

So the DEFERRED arm is about what THIS INVOCATION PRODUCED, not about what happens
to be on disk: with `--artifacts-built-after <epoch>` a declared artifact older than
that instant is deferred as `stale`, exactly as absent ones are. This is the same
`--built-after ${SIGIL_T0}` provenance rule every neighbouring post-sigil gate takes
from build.sh (row_remap_gate, editor_palette_golden, band_drift_golden,
sprite_tilt_gate), applied to the same axis rather than bolted beside it. WITHOUT
the option nothing changes: existence alone, as before.

WHAT THIS FILE STILL CANNOT DO. It cannot tell a stale artifact from a fresh one
without being told when the build began — freshness here is a BUILD-TIME
comparison, and `pytest tools` run by hand passes no threshold and therefore grades
whatever is on disk. That is the right default for a hand run and the wrong one for
a lane, which is why build.sh's post-sigil lane passes `${SIGIL_T0}`.
"""

import os

import pytest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The working-tree build artifacts. Enumerated by tracing every filesystem touch
#: of a repo-root path during a full `pytest tools` run with all eight present —
#: not by grepping for names, which cannot see a test that builds its path.
BUILD_ARTIFACTS = (
    "s4.bin", "s4.lst", "s4.debug.bin", "s4.debug.lst",
    "demo.bin", "demo.lst", "demo.debug.bin", "demo.debug.lst",
)

MARKER = "needs_build"

#: Deferred rows for the terminal summary: (nodeid, ["<name> (absent)", ...]).
_deferred = []

#: Epoch second this invocation's build began, from `--artifacts-built-after`.
#: None = existence only (a hand `pytest tools` run has no build to date against).
_built_after = None


def pytest_addoption(parser):
    parser.addoption(
        "--artifacts-built-after", type=int, default=None, metavar="EPOCH",
        help="Treat a declared build artifact older than EPOCH as DEFERRED-stale "
             "rather than running the test against it. build.sh's post-sigil lane "
             "passes ${SIGIL_T0}; a hand run passes nothing and grades what is on "
             "disk. Whole seconds truncate DOWN, so an artifact written in the same "
             "second as EPOCH counts as fresh — the same rule the sibling "
             "--built-after gates use.")


def pytest_configure(config):
    global _built_after
    _built_after = config.getoption("--artifacts-built-after")
    config.addinivalue_line(
        "markers",
        "%s(*artifacts): this test reads a build artifact out of the working tree. "
        "build.sh's pre-build lane deselects it; the post-sigil lane runs it. Name "
        "every artifact the test needs — they decide whether a skip is DEFERRED or "
        "a failure." % MARKER)
    _deferred.clear()


def _declared(item):
    """Every artifact named by every needs_build marker on this item."""
    names = []
    for mark in item.iter_markers(name=MARKER):
        names.extend(mark.args)
    return names


def _unusable(names):
    """The declared artifacts this invocation did not produce, each with its reason.

    ABSENT and STALE are one state on purpose. Both mean "the build shape that writes
    this file did not run", and both must defer rather than grade: a test run against
    either is answering about a build nobody made.
    """
    out = []
    for n in names:
        p = os.path.join(AEON, n)
        if not os.path.isfile(p):
            out.append("%s (absent)" % n)
        elif _built_after is not None and int(os.path.getmtime(p)) < _built_after:
            out.append("%s (stale — written %d, this build began %d)"
                       % (n, int(os.path.getmtime(p)), _built_after))
    return out


def pytest_collection_modifyitems(config, items):
    """Defer, BEFORE running, every marked test whose declared artifacts this
    invocation did not produce.

    THIS HOOK IS WHY DEFERRAL WORKS AT ALL. Deferral used to be inferred from a test
    SKIPPING on its own guard, which covers only the artifacts a test happens to check
    for itself — and the one that mattered, `demo.debug.lst` in the segments parent, is
    guarded by that test but STALE rather than absent, so the guard passed, the test
    ran, and it failed on a build nobody made. A test cannot be trusted to notice; the
    lane decides, from the declaration.

    An item skipped here is reported as skipped, lands in the DEFERRED block below with
    its reason, and is never silent. An item whose artifacts are all usable is left
    completely alone — if it then skips on its own, that is the FAILURE arm.
    """
    for item in items:
        declared = _declared(item)
        if not declared:
            continue
        unusable = _unusable(declared)
        if unusable:
            item.add_marker(pytest.mark.skip(
                reason="DEFERRED: this build shape did not produce " +
                       ", ".join(unusable)))


def _skip_reason(report):
    """The reason text out of a skip report's longrepr tuple."""
    lr = report.longrepr
    if isinstance(lr, tuple) and len(lr) == 3:
        return str(lr[2])
    return str(lr)


def _fail(report, message):
    report.outcome = "failed"
    report.longrepr = message


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.skipped or report.when not in ("setup", "call"):
        return

    declared = _declared(item)
    reason = _skip_reason(report)

    if declared:
        unusable = _unusable(declared)
        if unusable:
            _deferred.append((item.nodeid, unusable))
            return
        _fail(report, (
            "SKIPPED WITH ITS INPUTS ON DISK.\n"
            "  %s carries @pytest.mark.%s(%s) and every one of those artifacts is\n"
            "  present under %s, so this test had everything it declared and still\n"
            "  did not run. A skip reads as a pass in every aggregate — that is the\n"
            "  invisible state LS-1 was about, and post-build it is never legitimate.\n"
            "  Its own reason was: %s\n"
            "  Either the test's internal guard disagrees with its marker (fix one of\n"
            "  them) or it declares the wrong artifacts."
            % (item.nodeid, MARKER, ", ".join(repr(a) for a in declared), AEON, reason)))
        return

    named = [a for a in BUILD_ARTIFACTS if a in reason]
    if named:
        _fail(report, (
            "UNMARKED TEST SKIPPED FOR A BUILD ARTIFACT.\n"
            "  %s is not marked @pytest.mark.%s, so it runs in build.sh's PRE-build\n"
            "  lane — before the sigil invocation that writes %s. Today it skipped;\n"
            "  the day that artifact exists but is STALE it will FAIL instead, and it\n"
            "  will fail in the lane that runs before the build that would refresh it.\n"
            "  That is the LS-1 deadlock. Add @pytest.mark.%s(%s) so the post-sigil\n"
            "  lane owns it.\n"
            "  Its own reason was: %s\n"
            "\n"
            "  WHAT THIS SUGGESTION DOES NOT COVER, and it is the failure it is most\n"
            "  likely to cause: the artifact list above is what your SKIP TEXT happened\n"
            "  to name, which is not the same as what the test reads. Declare every\n"
            "  artifact it TOUCHES, including any built into a subprocess argv or a\n"
            "  constructed path — one of the four tests in this lane guards on\n"
            "  s4.debug.bin alone and hands s4.debug.lst to a child, and no reading of\n"
            "  its skip text can see the second one. Trace the touches; do not grep."
            % (item.nodeid, MARKER, ", ".join(named), MARKER,
               ", ".join(repr(a) for a in named), reason)))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """DEFERRED rows, by name. build.sh reads the exit status alone, so a lane that
    ran nothing at all has to be visible in the log it leaves behind."""
    if not _deferred:
        return
    terminalreporter.write_sep(
        "=", "DEFERRED — marked tests this build shape did not produce inputs for")
    for nodeid, unusable in _deferred:
        terminalreporter.write_line("  %s  (%s)" % (nodeid, ", ".join(unusable)))
    terminalreporter.write_line(
        "  %d deferred. These are NOT passes: each needs a build shape this run did "
        "not produce." % len(_deferred))
