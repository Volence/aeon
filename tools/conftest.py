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

WHAT THIS FILE CANNOT DO. It reasons about EXISTENCE, never about freshness. A
marked test handed a stale-but-present listing still runs and still fails — as it
should, because post-sigil the listing on disk IS this invocation's. The gates that
need more than existence take `--built-after ${SIGIL_T0}` from build.sh instead.
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

#: Deferred rows for the terminal summary: (nodeid, missing artifacts).
_deferred = []


def pytest_configure(config):
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


def _missing(names):
    return [n for n in names if not os.path.isfile(os.path.join(AEON, n))]


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
        missing = _missing(declared)
        if missing:
            _deferred.append((item.nodeid, missing))
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
            "  Its own reason was: %s"
            % (item.nodeid, MARKER, ", ".join(named), MARKER,
               ", ".join(repr(a) for a in named), reason)))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """DEFERRED rows, by name. build.sh reads the exit status alone, so a lane that
    ran nothing at all has to be visible in the log it leaves behind."""
    if not _deferred:
        return
    terminalreporter.write_sep("=", "DEFERRED — marked tests whose artifacts are absent")
    for nodeid, missing in _deferred:
        terminalreporter.write_line("  %s  (missing: %s)" % (nodeid, ", ".join(missing)))
    terminalreporter.write_line(
        "  %d deferred. These are NOT passes: each needs a build shape this run did "
        "not produce." % len(_deferred))
