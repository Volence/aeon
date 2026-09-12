"""tools/landing_build.sh writes its whole output to the [logfile] its usage line advertises,
and every way it can stop ends in a `finished=` stamp.

WHY THIS FILE EXISTS. The script's header has said `Usage: tools/landing_build.sh
[logfile]` since it was written, and until 2026-09-11 it never read `$1`: no log file was
written, everything went to stdout only. Measured twice on 2026-09-11 (the LS-8 landing and
the contracts parcel, booked in docs/DEFERRED_WORK.md as a side finding of the contracts
parcel, merge `92a17978`). This script IS the landing evidence, so a log that silently is
not there is the absence family, not a cosmetic miss.

THE SCRIPT RUNS IN A SANDBOX, NEVER AGAINST THIS REPO. Each row copies the real
tools/landing_build.sh into a temporary tree beside a STUB build.sh (writes a one-byte
<rom>.bin, or fails on request) and a STUB tools/needs_build_lane.py (exits with a chosen
code). The script `cd`s to its own parent directory, so the copy builds the stubs and
nothing else. This is not tidiness. The first draft of this file ran the real script
against the real repo, relying on FAST=1 to refuse before any build; one row omitted
FAST, the unfixed script went on to build, and that build's own pytest lane collected
this file and launched the script again: a recursion, stopped by hand (2026-09-11,
recorded in docs/superpowers/notes/2026-09-11-lens-tools-parcel.md). A test that calls a
build from inside the lane that build runs must not be able to reach the repo at all.
Each subprocess also runs in its own session and is KILLED as a group on timeout, so a
hang cannot leave an orphan behind.

WHAT IS ASSERTED:
  * the GREEN path (four stub shapes build, stub lane exits 0): with a logfile, the log
    holds exactly what stdout received, `finished=0` is the LAST line of both, exit 0;
  * a FAILED shape: `finished=1` last in both, exit 1, and the lane is reported skipped;
  * a lane that COULD NOT RUN (stub exits 2): `finished=2` last in both, exit 2;
  * the FAST=1 and NO_LINT=1 refusals: `finished=2` last in both, exit 2;
  * an unset or EMPTY SIGIL_BUILD or SIGIL_EMIT: COULD NOT RUN, `finished=2` last in both,
    exit 2, naming the variable, before any shape is built, with and without a logfile.
    Until 2026-09-11 these were `${VAR:?}` expansions, which exit 1 with NO stamp: a run
    that died there trailed like a killed one, under the code that means a shape FAILED
    (docs/DEFERRED_WORK.md, side findings of the 2026-09-11 lens-tools parcel, item (b));
  * a RELATIVE logfile path is relative to the CALLER's directory, not the repo root the
    script `cd`s to;
  * a logfile that cannot be written is COULD NOT RUN (exit 2, `finished=2`) BEFORE any
    shape is built: the stub build.sh leaves a marker, and it must not be there;
  * with no argument nothing changes: stdout only, same exit code, same last line, no
    file appears. This is the control for every row above.

WHAT IT DOES NOT COVER: the real build.sh and the real needs_build lane. What the script
RUNS is stubbed on purpose; the rows grade how it reports and where the report goes.
That the real four shapes end in `finished=0` is witnessed only by a real landing run.

RUNNER: build.sh's pre-build tool-suite lane, build-fatal. Source only, no marker.
"""
import os
import shutil
import signal
import stat
import subprocess
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(TOOLS, "landing_build.sh")

STUB_BUILD = r"""#!/bin/bash
# stub: the .bin a shape writes, by build.sh's own naming rule
g="${1:-sonic4}"
if [ "$g" = sonic4 ]; then r=s4; else r="$g"; fi
if [ "${DEBUG:-0}" = 1 ]; then r="$r.debug"; fi
echo "stub build $r"
touch stub-build-ran
if [ -n "${STUB_FAIL_SHAPE:-}" ] && [ "$STUB_FAIL_SHAPE" = "$r" ]; then exit 1; fi
printf x > "$r.bin"
"""

STUB_LANE = """import os, sys
print("stub needs_build lane")
sys.exit(int(os.environ.get("STUB_LANE_RC", "0")))
"""


def _sandbox(root):
    """A tree the script can `cd` into: the real script, a stub build.sh, a stub lane."""
    os.makedirs(os.path.join(root, "tools"))
    script = os.path.join(root, "tools", "landing_build.sh")
    shutil.copy(SCRIPT, script)
    build = os.path.join(root, "build.sh")
    with open(build, "w") as f:
        f.write(STUB_BUILD)
    os.chmod(build, os.stat(build).st_mode | stat.S_IXUSR)
    with open(os.path.join(root, "tools", "needs_build_lane.py"), "w") as f:
        f.write(STUB_LANE)
    return script


def _env(**extra):
    env = dict(os.environ)
    for k in ("FAST", "NO_LINT", "DEBUG", "STUB_FAIL_SHAPE", "STUB_LANE_RC"):
        env.pop(k, None)
    # Set, because the script's assembler checks come first; /bin/false, because the only
    # use is `$SIGIL_BUILD --version` after the stubs, and it must never be a real assembler.
    env["SIGIL_BUILD"] = "/bin/false"
    env["SIGIL_EMIT"] = "/bin/false"
    env.update(extra)
    # A value of None REMOVES the variable: that is how the unset-assembler rows ask for
    # it, and it is the only way to take one out after the two defaults above.
    for k in [k for k, v in env.items() if v is None]:
        del env[k]
    return env


def _run(script, args, cwd, **extra):
    p = subprocess.Popen(["bash", script, *args], cwd=cwd, env=_env(**extra),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        raise AssertionError("landing_build.sh did not finish in 60 s inside the sandbox")
    return p.returncode, out, err


def _last_line(text):
    lines = [l for l in text.splitlines() if l.strip()]
    assert lines, "no output at all"
    return lines[-1]


def _assert_logged(root, args, want_rc, cwd=None, **extra):
    script = _sandbox(root)
    log = os.path.join(root, "landing.log")
    rc, out, err = _run(script, args or [log], cwd or root, **extra)
    assert rc == want_rc, (rc, out, err)
    assert _last_line(out) == "finished=%d" % want_rc, out
    assert os.path.isfile(log), "no log file at %s; stdout was:\n%s" % (log, out)
    with open(log) as f:
        logged = f.read()
    assert _last_line(logged) == "finished=%d" % want_rc, logged
    assert logged == out, (
        "the log is not the whole stdout.\n--- log ---\n%s--- stdout ---\n%s" % (logged, out))
    return out


def test_the_green_path_is_logged_whole_and_ends_finished_0():
    with tempfile.TemporaryDirectory() as d:
        out = _assert_logged(d, None, 0)
        for rom in ("s4", "s4.debug", "demo", "demo.debug"):
            assert "EXIT_%s=0" % rom in out, (rom, out)
        assert "EXIT_needs_build=0" in out, out


def test_a_failed_shape_is_logged_and_ends_finished_1():
    with tempfile.TemporaryDirectory() as d:
        out = _assert_logged(d, None, 1, STUB_FAIL_SHAPE="demo")
        assert "EXIT_demo=FAILED" in out, out
        assert "needs_build lane SKIPPED" in out, out


def test_a_lane_that_could_not_run_is_logged_and_ends_finished_2():
    with tempfile.TemporaryDirectory() as d:
        out = _assert_logged(d, None, 2, STUB_LANE_RC="2")
        assert "EXIT_needs_build=2" in out, out


def test_the_refusals_are_logged_and_end_finished_2():
    for knob in ("FAST", "NO_LINT"):
        with tempfile.TemporaryDirectory() as d:
            _assert_logged(d, None, 2, **{knob: "1"})
            assert not os.path.exists(os.path.join(d, "stub-build-ran")), knob


def test_an_unset_or_empty_assembler_variable_is_could_not_run_with_the_stamp():
    """Each of the two variables, unset and set-but-empty (the old `:?` form refused both),
    through the logfile path: exit 2, `finished=2` last in stdout AND in the log, the
    variable named, nothing built."""
    for var in ("SIGIL_BUILD", "SIGIL_EMIT"):
        for value in (None, ""):
            with tempfile.TemporaryDirectory() as d:
                out = _assert_logged(d, None, 2, **{var: value})
                assert "COULD NOT RUN" in out and var in out, (var, value, out)
                assert not os.path.exists(os.path.join(d, "stub-build-ran")), \
                    "%s=%r: a shape was built with no assembler named" % (var, value)


def test_an_unset_assembler_variable_without_a_logfile_still_ends_finished_2():
    """The same refusal on the no-argument path, the one a detached landing run uses:
    the stamp has to be stdout's last line there too, not only the log's."""
    for var in ("SIGIL_BUILD", "SIGIL_EMIT"):
        with tempfile.TemporaryDirectory() as d:
            script = _sandbox(d)
            rc, out, err = _run(script, [], d, **{var: None})
            assert rc == 2, (var, rc, out, err)
            assert _last_line(out) == "finished=2", (var, out, err)
            assert var in out, (var, out)
            assert not os.path.exists(os.path.join(d, "stub-build-ran")), var


def test_a_relative_logfile_is_relative_to_the_caller_not_the_repo_root():
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "repo")
        caller = os.path.join(d, "caller")
        os.makedirs(caller)
        script = _sandbox(root)
        rc, out, err = _run(script, ["rel.log"], caller)
        assert rc == 0, (rc, out, err)
        assert os.path.isfile(os.path.join(caller, "rel.log")), (
            "the log did not land in the caller's directory; stdout:\n%s" % out)
        assert not os.path.exists(os.path.join(root, "rel.log")), \
            "the log landed at the repo root the script cd's to"


def test_an_unwritable_logfile_is_could_not_run_before_anything_builds():
    with tempfile.TemporaryDirectory() as d:
        script = _sandbox(d)
        log = os.path.join(d, "no-such-dir", "landing.log")
        rc, out, err = _run(script, [log], d)
        assert rc == 2, (rc, out, err)
        assert _last_line(out) == "finished=2", out
        assert "logfile" in out, out
        assert not os.path.exists(os.path.join(d, "stub-build-ran")), \
            "a shape was built although the evidence had nowhere to go"


def test_without_a_logfile_nothing_changes():
    """The control: stdout only, the same exit code and last line, no file appears."""
    with tempfile.TemporaryDirectory() as d:
        script = _sandbox(d)
        before = set(os.listdir(d))
        rc, out, err = _run(script, [], d, FAST="1")
        assert rc == 2, (rc, out, err)
        assert _last_line(out) == "finished=2", out
        assert set(os.listdir(d)) == before, set(os.listdir(d)) - before
