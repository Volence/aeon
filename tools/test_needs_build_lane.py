"""The lane's own gate: every arm of tools/needs_build_lane.py's exit contract.

RUNNER: `build.sh`'s PRE-build tool-suite lane (`pytest tools -m "not needs_build"`).
Nothing here reads a build artifact, so nothing here carries the marker — these tests
build their own synthetic tests directory, with a COPY of `tools/conftest.py` in it, and
drive the real tool over it as a subprocess. The tool is never mocked: what is asserted
is the tool's exit status and the words it prints, which is exactly what
`tools/nightly_effects_gates.sh` routes on.

WHY A SYNTHETIC DIRECTORY. The real marked lane needs three build shapes to be reachable
(that is LS-1b itself), so a test that drove it would defer on any developer machine and
grade nothing. The synthetic directory lets each arm be MADE — a failing marked test, an
absent artifact, a stale artifact, an empty lane — instead of waited for.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
TOOL = TOOLS / "needs_build_lane.py"
CONFTEST = TOOLS / "conftest.py"


def make_lane(tmp_path, body, artifacts=(), extra_files=None):
    """A synthetic tests directory the real tool can be pointed at.

    The conftest is COPIED rather than imported so the marker semantics under test are the
    ones that actually ship. It computes its artifact root as the parent of its own
    directory, so `<tmp>/lane/conftest.py` looks for artifacts in `<tmp>` — which is what
    `artifacts` creates.
    """
    lane = tmp_path / "lane"
    lane.mkdir()
    shutil.copy(CONFTEST, lane / "conftest.py")
    (lane / "test_marked.py").write_text(body, encoding="utf-8")
    for name in artifacts:
        (tmp_path / name).write_bytes(b"x")
    for name, text in (extra_files or {}).items():
        (lane / name).write_text(text, encoding="utf-8")
    return lane


def run_lane(lane, *args):
    return subprocess.run([sys.executable, str(TOOL), "--tests", str(lane), *args],
                          capture_output=True, text=True, timeout=300)


TWO_PASSING = """\
import pytest

@pytest.mark.needs_build("s4.debug.bin")
def test_one():
    assert True

@pytest.mark.needs_build("s4.debug.lst", "demo.debug.lst")
def test_two():
    assert True
"""


def test_clean_lane_runs_every_marked_test_and_exits_0(tmp_path):
    lane = make_lane(tmp_path, TWO_PASSING,
                     artifacts=("s4.debug.bin", "s4.debug.lst", "demo.debug.lst"))
    p = run_lane(lane)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "OK — all 2 marked test(s) ran and passed." in p.stdout
    assert "2 ran, 0 deferred, 0 failed" in p.stdout


def test_a_marked_test_that_fails_is_exit_1_and_is_named(tmp_path):
    """The 'ran and failed' state. Distinct from 'did not run' — they route differently."""
    body = TWO_PASSING.replace("def test_two():\n    assert True",
                               "def test_two():\n    assert False, 'deliberate'")
    lane = make_lane(tmp_path, body,
                     artifacts=("s4.debug.bin", "s4.debug.lst", "demo.debug.lst"))
    p = run_lane(lane)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "FAILED" in p.stdout and "test_marked::test_two" in p.stdout
    assert "1 marked test(s) failed" in p.stdout
    assert "COULD NOT RUN" not in p.stdout


def test_an_absent_artifact_defers_and_is_exit_2_not_a_pass(tmp_path):
    """THE ARM THIS TOOL EXISTS FOR.

    `demo.debug.lst` is missing, so `test_two` is deferred by the conftest collection hook.
    pytest's OWN status is 0 — a skipped test is not a failure to pytest — and the assertion
    on that line is the point: routing on pytest's exit code would report this lane green
    while half of it did not run.
    """
    lane = make_lane(tmp_path, TWO_PASSING, artifacts=("s4.debug.bin", "s4.debug.lst"))
    p = run_lane(lane)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "pytest exit 0" in p.stdout, "pytest itself saw nothing wrong — that is the trap"
    assert "DEFERRED" in p.stdout and "test_marked::test_two" in p.stdout
    assert "demo.debug.lst (absent)" in p.stdout
    assert "1 marked test(s) DEFERRED" in p.stdout
    assert "OK —" not in p.stdout


def test_a_stale_artifact_defers_under_the_provenance_threshold(tmp_path):
    """Present but older than the caller's build start is the same state as absent."""
    lane = make_lane(tmp_path, TWO_PASSING,
                     artifacts=("s4.debug.bin", "s4.debug.lst", "demo.debug.lst"))
    stale = tmp_path / "demo.debug.lst"
    os.utime(stale, (1_600_000_000, 1_600_000_000))
    p = run_lane(lane, "--built-after", "1700000000")
    assert p.returncode == 2, p.stdout + p.stderr
    assert "demo.debug.lst (stale" in p.stdout
    assert "1 marked test(s) DEFERRED" in p.stdout
    # And WITHOUT the threshold the same tree grades it — that is the hand-run default, and
    # the control that shows the deferral above came from the threshold and not from the file.
    q = run_lane(lane)
    assert q.returncode == 0, q.stdout + q.stderr


def test_an_empty_lane_is_exit_2_not_a_pass(tmp_path):
    """Every marker deleted silently restores the pre-LS-1 state; pytest calls it exit 5."""
    lane = make_lane(tmp_path, "def test_unmarked():\n    assert True\n")
    p = run_lane(lane)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "collected NO tests" in p.stdout
    assert "OK —" not in p.stdout


def test_markers_the_run_never_reached_are_exit_2(tmp_path):
    """The directional population floor: 3 decorators in the directory, 2 cases in the run.

    The third lives in a module pytest does not collect, which is the cheapest way to make
    'a marker exists that the lane did not reach' without breaking collection outright.
    """
    lane = make_lane(
        tmp_path, TWO_PASSING,
        artifacts=("s4.debug.bin", "s4.debug.lst", "demo.debug.lst"),
        extra_files={"helper_marked.py": (
            "import pytest\n\n"
            "@pytest.mark.needs_build(\"s4.debug.bin\")\n"
            "def test_never_collected():\n    assert True\n")})
    p = run_lane(lane)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "3 decorator(s) in the source but only 2 case(s) ran" in p.stdout


def test_more_cases_than_decorators_is_fine(tmp_path):
    """The floor must stay directional: one decorator, three parametrized cases, exit 0."""
    lane = make_lane(tmp_path, (
        "import pytest\n\n"
        "@pytest.mark.needs_build(\"s4.debug.bin\")\n"
        "@pytest.mark.parametrize(\"n\", [1, 2, 3])\n"
        "def test_param(n):\n    assert n\n"), artifacts=("s4.debug.bin",))
    p = run_lane(lane)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "OK — all 3 marked test(s) ran and passed." in p.stdout


def test_a_decorator_inside_a_string_literal_is_not_counted(tmp_path):
    """REGRESSION, and it is this file's own bug (2026-09-06, before first use).

    The first version of `decorator_count` was a regex over the file text, so the
    triple-quoted `TWO_PASSING` fixture above — whose lines begin with the decorator at
    column 0 — counted as two more markers than the tree has. Over the real `tools/`
    directory it read 6 against 4 real ones, and the lane's directional floor would have
    exited 2 with "markers the run never reached" on a healthy tree, every night. The
    count is parsed from the AST now. This fixture reproduces the shape exactly: ONE real
    decorator, and a string literal that looks like two more.
    """
    lane = make_lane(tmp_path, (
        "import pytest\n\n"
        "FIXTURE = '''\n"
        "@pytest.mark.needs_build(\"s4.debug.bin\")\n"
        "def test_in_a_string(): pass\n"
        "@pytest.mark.needs_build(\"s4.lst\")\n"
        "def test_also_in_a_string(): pass\n"
        "'''\n\n"
        "@pytest.mark.needs_build(\"s4.debug.bin\")\n"
        "def test_real():\n    assert FIXTURE\n"), artifacts=("s4.debug.bin",))
    p = run_lane(lane)
    assert "1 @pytest.mark.needs_build decorator(s)" in p.stdout, p.stdout
    assert p.returncode == 0, p.stdout + p.stderr


def test_pytest_failing_to_run_at_all_is_exit_2(tmp_path):
    """A usage error writes no report; a missing verdict is COULD NOT RUN, never a pass."""
    lane = make_lane(tmp_path, TWO_PASSING, artifacts=("s4.debug.bin",))
    p = run_lane(lane, "--no-such-pytest-flag")
    assert p.returncode == 2, p.stdout + p.stderr
    assert "COULD NOT RUN" in p.stdout
    assert "OK —" not in p.stdout
