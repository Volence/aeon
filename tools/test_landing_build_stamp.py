"""tools/landing_build.sh writes the land gate's stamp only for a completed green run of a
tree that did not move, and never changes what it builds or how it reports otherwise.

WHY THIS FILE EXISTS. CTRL-3: the pre-push hook (tools/hooks/pre-push) lets code onto
master only with a stamp for its content, and landing_build.sh is the only writer of that
stamp (via tools/land_gate.py begin/finish). So the stamp's honesty is the gate's
honesty: a killed run, a red run, a run over a dirty tree, or a run under which HEAD or
the tree moved must leave NO stamp.

SANDBOXED like tools/test_landing_build_logfile.py, and for its reason (a test that runs
a build from inside the lane that build runs must not be able to reach the repo): the
real landing_build.sh and the real land_gate.py are copied into a scratch GIT repository
beside a stub build.sh and a stub needs_build lane. The stamp directory is the scratch
repository's own. Subprocesses run in their own session and are killed as a group.

WHAT IS ASSERTED:
  * green: finished=0, 'STAMP WRITTEN', and the stamp's key is `land_gate.py key HEAD`;
  * a failed shape (finished=1): no stamp;
  * code dirty at the start: the run still builds and reports as before, and no stamp;
  * a commit during the run: no stamp, 'HEAD MOVED', and the run reports COULD NOT RUN
    (finished=2), because nothing it printed describes a commit;
  * a code edit during the run: no stamp, 'CHANGED during the run', finished=2;
  * a killed run (no finished= line): no stamp;
  * a tree that is not a git repository (the logfile sandbox's case): the builds are
    graded exactly as before, the gate says UNMEASURABLE, and no stamp.

RUNNER: build.sh's pre-build tool-suite lane, build-fatal. Source only, no marker.
"""
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
from test_landing_lane_shapes import landing_shapes  # noqa: E402

#: The LAST shape the real script builds, from its one declared list (CTRL-3b): the failed-
#: shape and the during-the-run rows act there, so every earlier shape (and the land gate's
#: `begin`) has already run. It was `demo` when the check built four shapes; demo normal
#: left the check under option A, and a stub keyed to a shape nobody builds never fires.
with open(os.path.join(TOOLS, "landing_build.sh"), encoding="utf-8") as _f:
    LAST = landing_shapes(_f.read())[-1]

STUB_BUILD = r"""#!/bin/bash
g="${1:-sonic4}"
if [ "$g" = sonic4 ]; then r=s4; else r="$g"; fi
if [ "${DEBUG:-0}" = 1 ]; then r="$r.debug"; fi
echo "stub build $r"
if [ -n "${STUB_FAIL_SHAPE:-}" ] && [ "$STUB_FAIL_SHAPE" = "$r" ]; then exit 1; fi
if [ -n "${STUB_DURING:-}" ] && [ "$r" = "${STUB_DURING_SHAPE:-}" ]; then
    case "$STUB_DURING" in
        commit) echo moved > engine/a.emp; git add engine/a.emp; git commit -q -m during ;;
        edit)   echo edited > engine/a.emp ;;
        sleep)  touch stub-sleeping; sleep 30 ;;
    esac
fi
printf x > "$r.bin"
"""

STUB_LANE = "import sys; print('stub needs_build lane'); sys.exit(0)\n"


def _sandbox(root, git=True):
    os.makedirs(os.path.join(root, "tools"))
    os.makedirs(os.path.join(root, "engine"))
    for name in ("landing_build.sh", "land_gate.py"):
        shutil.copy(os.path.join(TOOLS, name), os.path.join(root, "tools", name))
    with open(os.path.join(root, "build.sh"), "w") as f:
        f.write(STUB_BUILD)
    os.chmod(os.path.join(root, "build.sh"), 0o755)
    with open(os.path.join(root, "tools", "needs_build_lane.py"), "w") as f:
        f.write(STUB_LANE)
    with open(os.path.join(root, "engine", "a.emp"), "w") as f:
        f.write("a\n")
    with open(os.path.join(root, ".gitignore"), "w") as f:
        f.write("*.bin\n*.landing-tmp\nstub-sleeping\n")
    env = _env()
    if git:
        for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
            subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True)
    return os.path.join(root, "tools", "landing_build.sh")


def _env(**extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "AEON_LAND_GATE")) and
           k not in ("FAST", "NO_LINT", "DEBUG", "STUB_FAIL_SHAPE", "STUB_DURING",
                     "STUB_DURING_SHAPE", "AEON_LANDING_LANES_RECEIPT")}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
               GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               SIGIL_BUILD="/bin/false", SIGIL_EMIT="/bin/false", STUB_DURING_SHAPE=LAST)
    env.update(extra)
    return env


def _run(script, root, **extra):
    p = subprocess.Popen(["bash", script], cwd=root, env=_env(**extra), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        raise AssertionError("landing_build.sh did not finish in 60 s inside the sandbox")
    return p.returncode, out


def _stamps(root):
    d = os.path.join(root, ".git", "aeon-land-gate")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def _key(root):
    return subprocess.run([sys.executable, "tools/land_gate.py", "key"], cwd=root, env=_env(),
                          capture_output=True, text=True, check=True).stdout.strip()


def _last(out):
    return [l for l in out.splitlines() if l.strip()][-1]


def test_a_green_run_writes_the_stamp_for_its_content():
    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d), d)
        assert rc == 0 and _last(out) == "finished=0", out
        assert "STAMP WRITTEN" in out, out
        assert _stamps(d) == [_key(d) + ".json"], (_stamps(d), out)
        s = json.load(open(os.path.join(d, ".git", "aeon-land-gate", _stamps(d)[0])))
        assert s["finished"] == 0 and s["key"] == _key(d)


def test_a_failed_shape_writes_no_stamp():
    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d), d, STUB_FAIL_SHAPE=LAST)
        assert rc == 1 and _last(out) == "finished=1", out
        assert "NO STAMP" in out and _stamps(d) == [], out


def test_dirty_code_at_the_start_builds_as_before_and_writes_no_stamp():
    with tempfile.TemporaryDirectory() as d:
        script = _sandbox(d)
        with open(os.path.join(d, "engine", "a.emp"), "w") as f:
            f.write("uncommitted\n")
        rc, out = _run(script, d)
        assert rc == 0 and _last(out) == "finished=0", out
        assert "dirty at start" in out and _stamps(d) == [], out


def test_a_commit_during_the_run_writes_no_stamp_and_is_could_not_run():
    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d), d, STUB_DURING="commit")
        assert "HEAD MOVED" in out and _stamps(d) == [], out
        assert rc == 2 and _last(out) == "finished=2", out


def test_an_edit_during_the_run_writes_no_stamp_and_is_could_not_run():
    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d), d, STUB_DURING="edit")
        assert "CHANGED during the run" in out and _stamps(d) == [], out
        assert rc == 2 and _last(out) == "finished=2", out


def test_a_killed_run_writes_no_stamp():
    with tempfile.TemporaryDirectory() as d:
        script = _sandbox(d)
        p = subprocess.Popen(["bash", script], cwd=d, env=_env(STUB_DURING="sleep"),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             start_new_session=True)
        for _ in range(300):
            if os.path.exists(os.path.join(d, "stub-sleeping")):
                break
            time.sleep(0.05)
        assert os.path.exists(os.path.join(d, "stub-sleeping")), "the stub never started"
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        assert "finished=" not in out, out
        assert _stamps(d) == [], out


def test_outside_a_git_repository_the_builds_report_as_before_and_no_stamp():
    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d, git=False), d)
        assert rc == 0 and _last(out) == "finished=0", out
        assert "UNMEASURABLE" in out and "NO STAMP" in out, out
