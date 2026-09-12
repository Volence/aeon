"""tools/nightly_effects_gates.sh tests a freshly fetched origin/master, never the main
checkout's local master, and a fetch that fails is COULD NOT RUN.

WHY THIS FILE EXISTS. Until 2026-09-12 the nightly resolved its target as the MAIN
checkout's LOCAL `master` (`worktree add ... master`, `SHA=$(git rev-parse master)`). The
owner's main checkout sat 34 commits behind origin/master (an uncommitted edit blocked its
fast-forward), so on 2026-09-12T08:17Z the nightly tested a38ce7c9, printed three OK lines,
and graded none of that day's landings. Its log named the SHA it tested and not the one it
should have tested. Booked in docs/DEFERRED_WORK.md, "The nightly backstop tests the MAIN
checkout's LOCAL `master`". Every landing here is pushed, so origin/master is what "landed"
means.

THE SCRIPT RUNS IN A THROWAWAY SUITE, NEVER AGAINST THIS REPO. Each row builds, in a temp
dir:
    <tmp>/origin.git                  a bare "origin"
    <tmp>/suite/aeon                  a clone of it (the MAIN checkout), with the REAL script
                                      copied to tools/nightly_effects_gates.sh
    <tmp>/suite/sigil/target/release/{sigil,emit_sound_blob}
                                      fake executables: the script derives SUITE as MAIN's
                                      parent and refuses (exit 2) when these are absent. They
                                      are never executed on the --checkout-only path.
and runs the copy with `--checkout-only`, which executes the script's own resolution block
and worktree cut/checkout (the same lines the real run executes, not a copy of them), prints
the SHA it checked out, and exits 0 before any build. So <tmp>/suite/.aeon-nightly is a
real worktree, and its HEAD is what a real night would have built. `notify-send` is stubbed
on PATH so the COULD NOT RUN row raises no desktop notification and the stub records that
the loud path fired. XDG_STATE_HOME points into the temp dir, so the log is the row's own.

EXPECTATIONS ARE DERIVED, NEVER TYPED: every SHA compared is read back out of the temp repos
with `git rev-parse` in the same row, and each row first asserts that local master and origin
master really differ in the direction it is about. A row whose setup failed to create the
divergence would otherwise pass against either resolution.

WHAT IS ASSERTED:
  * local master BEHIND origin (the 2026-09-12 state): the nightly checks out ORIGIN's SHA,
    and its local remote-tracking ref was stale before the run, so a resolver that read
    `origin/master` without fetching fails this row too. The log names both SHAs and says
    "behind";
  * a SECOND run after origin advances again moves an EXISTING nightly worktree to the new
    origin SHA (the checkout line, not only the worktree-add line);
  * local master AHEAD of origin (unpushed commits): origin's SHA is tested; the log says
    "ahead";
  * NO local master branch at all: still tests origin, exit 0, log says so;
  * local == origin: the control; exit 0, the log says they are the same;
  * the fetch FAILS (origin URL does not exist): exit 2, a COULD NOT RUN line naming the
    fetch, the notify-send stub fired, no SHA printed, and no nightly worktree created.

WHAT IT DOES NOT COVER: the builds and the three lanes after the checkout, and a real fetch
from GitHub under the systemd unit's environment (no agent socket there on 2026-09-12; see
the DEFERRED closure). The rows grade what the script resolves and what it says about it.

RUNNER: build.sh's pre-build tool-suite lane (`python3 -m pytest tools -m "not needs_build"`),
build-fatal. Source only, no marker; it reads no build artifact.
"""
import os
import shutil
import signal
import stat
import subprocess
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(TOOLS, "nightly_effects_gates.sh")

STUB_NOTIFY = """#!/bin/sh
# stub: record the notification instead of raising one on the owner's desktop
printf '%s\\n' "$*" >> "$NOTIFY_RECORD"
"""


def _env(root, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # Isolated from the caller's git config: a global hooksPath, signing, or a default
    # branch name must not change what these rows measure.
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "nightly-target-test"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "nightly-target-test@invalid"
    env["XDG_STATE_HOME"] = os.path.join(root, "state")
    env["NOTIFY_RECORD"] = os.path.join(root, "notify.record")
    env["PATH"] = os.path.join(root, "bin") + os.pathsep + env.get("PATH", "")
    env.update(extra)
    return env


def _git(root, *args):
    return subprocess.run(["git", *args], env=_env(root), check=True,
                          capture_output=True, text=True).stdout.strip()


def _commit(root, repo, name):
    with open(os.path.join(repo, name), "w") as f:
        f.write(name + "\n")
    _git(root, "-C", repo, "add", name)
    _git(root, "-C", repo, "commit", "-q", "-m", name)


def _suite(root):
    """The throwaway suite. Returns (main, origin, pusher): local == origin at one commit."""
    origin = os.path.join(root, "origin.git")
    main = os.path.join(root, "suite", "aeon")
    pusher = os.path.join(root, "pusher")
    os.makedirs(os.path.join(root, "bin"))
    notify = os.path.join(root, "bin", "notify-send")
    with open(notify, "w") as f:
        f.write(STUB_NOTIFY)
    os.chmod(notify, os.stat(notify).st_mode | stat.S_IXUSR)
    release = os.path.join(root, "suite", "sigil", "target", "release")
    os.makedirs(release)
    for b in ("sigil", "emit_sound_blob"):
        p = os.path.join(release, b)
        with open(p, "w") as f:
            f.write("#!/bin/sh\necho 'fake assembler: must never run' >&2\nexit 99\n")
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)

    _git(root, "init", "-q", "--bare", "-b", "master", origin)
    _git(root, "clone", "-q", origin, main)
    _git(root, "-C", main, "checkout", "-q", "-b", "master")
    os.makedirs(os.path.join(main, "tools"))
    shutil.copy(SCRIPT, os.path.join(main, "tools", "nightly_effects_gates.sh"))
    _git(root, "-C", main, "add", "tools/nightly_effects_gates.sh")
    _git(root, "-C", main, "commit", "-q", "-m", "base")
    _git(root, "-C", main, "push", "-q", "origin", "master")
    _git(root, "clone", "-q", origin, pusher)
    return main, origin, pusher


def _advance_origin(root, pusher, name):
    """A landing somebody else pushed: origin moves, the MAIN checkout does not."""
    _git(root, "-C", pusher, "pull", "-q", "--ff-only")
    _commit(root, pusher, name)
    _git(root, "-C", pusher, "push", "-q", "origin", "master")


def _run(root, main):
    script = os.path.join(main, "tools", "nightly_effects_gates.sh")
    p = subprocess.Popen(["bash", script, "--checkout-only"], cwd=root, env=_env(root),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        raise AssertionError("nightly_effects_gates.sh --checkout-only did not finish in 120 s")
    return p.returncode, out, err


def _log(root):
    path = os.path.join(root, "state", "aeon-nightly", "nightly.log")
    assert os.path.isfile(path), "the script wrote no log at %s" % path
    with open(path) as f:
        return f.read()


def _target_lines(log):
    return [l for l in log.splitlines() if " target: " in l]


def _nightly_head(root):
    nightly = os.path.join(root, "suite", ".aeon-nightly")
    assert os.path.isdir(nightly), "no nightly worktree at %s" % nightly
    return _git(root, "-C", nightly, "rev-parse", "HEAD")


def _assert_tested_origin(root, main, origin, rc, out, err):
    want = _git(root, "-C", origin, "rev-parse", "master")
    assert rc == 0, (rc, out, err, _log(root))
    local = (_git(root, "-C", main, "rev-parse", "master")
             if _has_local_master(root, main) else "none")
    assert out.strip() == want, (
        "the nightly resolved %r, origin/master is %s (local master %s)\nlog:\n%s"
        % (out.strip(), want, local, _log(root)))
    assert _nightly_head(root) == want, "the nightly worktree is not at origin/master"
    return want


def _has_local_master(root, main):
    return subprocess.run(["git", "-C", main, "rev-parse", "--verify", "-q", "refs/heads/master"],
                          env=_env(root), capture_output=True).returncode == 0


def test_local_master_BEHIND_origin_tests_origin_and_says_so():
    """The 2026-09-12 state: landings were pushed, the main checkout never pulled them."""
    with tempfile.TemporaryDirectory() as root:
        main, origin, pusher = _suite(root)
        _advance_origin(root, pusher, "landing-1")
        _advance_origin(root, pusher, "landing-2")
        local = _git(root, "-C", main, "rev-parse", "master")
        stale_tracking = _git(root, "-C", main, "rev-parse", "refs/remotes/origin/master")
        landed = _git(root, "-C", origin, "rev-parse", "master")
        # Preconditions: the divergence this row is about really exists, and the local
        # remote-tracking ref is stale (so a resolver that skips the fetch cannot pass).
        assert local != landed and stale_tracking == local, (local, stale_tracking, landed)

        rc, out, err = _run(root, main)
        want = _assert_tested_origin(root, main, origin, rc, out, err)
        assert want == landed and want != local
        log = _log(root)
        [line] = _target_lines(log)
        assert landed in line and local in line, line
        assert "2 behind" in line and "0 ahead" in line, line
        assert "COULD NOT RUN" not in log, log
        # The main checkout itself is untouched: the nightly does not pull on the owner's behalf.
        assert _git(root, "-C", main, "rev-parse", "master") == local

        # A second night: origin advances again and the EXISTING worktree must follow it,
        # which is the checkout line rather than the worktree-add line.
        _advance_origin(root, pusher, "landing-3")
        rc, out, err = _run(root, main)
        want2 = _assert_tested_origin(root, main, origin, rc, out, err)
        assert want2 != want


def test_local_master_AHEAD_of_origin_tests_origin_not_the_unpushed_commit():
    with tempfile.TemporaryDirectory() as root:
        main, origin, _ = _suite(root)
        _commit(root, main, "unpushed")
        local = _git(root, "-C", main, "rev-parse", "master")
        landed = _git(root, "-C", origin, "rev-parse", "master")
        assert local != landed, (local, landed)

        rc, out, err = _run(root, main)
        want = _assert_tested_origin(root, main, origin, rc, out, err)
        assert want == landed
        [line] = _target_lines(_log(root))
        assert "0 behind" in line and "1 ahead" in line and local in line, line


def test_no_local_master_branch_still_tests_origin():
    """Nothing in the nightly needs a local master; the old `worktree add ... master` did."""
    with tempfile.TemporaryDirectory() as root:
        main, origin, pusher = _suite(root)
        _advance_origin(root, pusher, "landing-1")
        _git(root, "-C", main, "checkout", "-q", "-b", "feature")
        _git(root, "-C", main, "branch", "-q", "-D", "master")
        assert not _has_local_master(root, main)

        rc, out, err = _run(root, main)
        _assert_tested_origin(root, main, origin, rc, out, err)
        [line] = _target_lines(_log(root))
        assert "no local master" in line, line


def test_local_AT_origin_is_the_control():
    with tempfile.TemporaryDirectory() as root:
        main, origin, _ = _suite(root)
        local = _git(root, "-C", main, "rev-parse", "master")
        assert local == _git(root, "-C", origin, "rev-parse", "master")

        rc, out, err = _run(root, main)
        _assert_tested_origin(root, main, origin, rc, out, err)
        [line] = _target_lines(_log(root))
        assert "AT origin/master" in line, line


def test_a_failed_fetch_is_COULD_NOT_RUN_and_grades_nothing():
    """No silent fallback to the origin/master ref already on disk: it is exactly as stale
    as the last fetch that worked."""
    with tempfile.TemporaryDirectory() as root:
        main, _, _ = _suite(root)
        gone = os.path.join(root, "no-such-origin.git")
        assert not os.path.exists(gone)
        _git(root, "-C", main, "remote", "set-url", "origin", gone)
        # A tracking ref IS on disk, so a resolver that falls back to it would have a SHA.
        assert _git(root, "-C", main, "rev-parse", "refs/remotes/origin/master")

        rc, out, err = _run(root, main)
        assert rc == 2, (rc, out, err, _log(root))
        assert out.strip() == "", "a SHA was printed after a failed fetch: %r" % out
        log = _log(root)
        assert "COULD NOT RUN: git fetch of origin master failed" in log, log
        assert gone in log, "the COULD NOT RUN line does not name the remote it failed on"
        assert not _target_lines(log), log
        assert not os.path.exists(os.path.join(root, "suite", ".aeon-nightly"))
        with open(os.path.join(root, "notify.record")) as f:
            assert "COULD NOT RUN: git fetch" in f.read()


def test_every_verdict_line_names_the_tested_and_the_local_sha():
    """Source row: each OK / FAILED / COULD NOT RUN line past the resolution says `at $AT`.

    `$AT` is "origin/master <tested> (local master <local>)". A verdict line that still
    names a bare `${SHA:0:8}` is the log that could not say what it should have tested.
    """
    with open(SCRIPT) as f:
        text = f.read()
    verdicts = [l for l in text.splitlines()
                if not l.lstrip().startswith("#")
                and ('"$(date -Is) OK at' in l or "FAILED at" in l or "failed at" in l)]
    assert len(verdicts) >= 7, "found only %d verdict lines; the pattern stopped matching" % len(verdicts)
    bare = [l for l in verdicts if "at $AT" not in l]
    assert not bare, "verdict lines that do not carry $AT:\n  " + "\n  ".join(bare)
    assert 'AT="origin/master ${SHA:0:8} (local master $LOCAL_SHORT)"' in text
