"""The landing gate (tools/land_gate.py + tools/hooks/pre-push) refuses what CTRL-3 says it
must, and lets through what "doesn't hamper too much" says it must.

WHY THIS FILE EXISTS. CTRL-3 (docs/decisions.jsonl, the owner's answer of
2026-09-13T22:06:54Z): the landing check (tools/landing_build.sh, whatever shapes its
LANDING_SHAPES list names; nothing here counts them) becomes the only way code reaches
master. The gate is a pre-push hook plus a content-keyed stamp that
tools/landing_build.sh writes. Every row below is one clause of that contract, driven
through REAL `git push` calls.

HERMETIC. One scratch repository and a bare "origin" are built per module under a
temporary directory, and every row works on its own copy of them. The real
tools/land_gate.py and tools/hooks/pre-push are copied in, and the hook is installed
with the exact command the docs give the controller. Nothing here touches this
repository, its hooks, its config or its stamps: git runs with GIT_CONFIG_GLOBAL=/dev/null
and GIT_CONFIG_NOSYSTEM=1, and the stamp directory is the scratch repository's own. The
copy's RULES block is replaced by a table naming scratch paths (a docs path the build
reads, a CHECKED ledger and folder with a real reader test, and unnamed docs), because
the real table names this repository's files.

WHAT IS ASSERTED (each refusal also checks that the remote did NOT move):
  * a parcel/* push, and a push of local master to a parcel ref: untouched and silent;
  * a docs-only master push: allowed with no stamp and no build;
  * a code master push with no stamp: refused, naming the code paths;
  * the same after `begin`/`finish` wrote a stamp: allowed;
  * the ledger commit on top of stamped code: allowed, and its reader test ran; a ledger
    line that breaks the reader: refused; a new file under a CHECKED prefix: validated;
  * checked paths are validated in the PUSHED commit, not the pushing working tree (a
    broken dirty file does not refuse a good commit, a good dirty file does not rescue a
    broken one);
  * a docs path the rules call CODE: needs a stamp like any code;
  * a stamp for OTHER content, and a stamp that is not a complete green one: refused;
  * `finish` writes no stamp when HEAD moved, when the tree changed during the run, when
    code was dirty at the start, or when the run was not finished=0, and does write one
    when only docs were dirty;
  * deleting master: refused;
  * the printed bypass (AEON_LAND_GATE=skip) and git's own, silent, --no-verify;
  * a checkout that predates the gate: a master push is refused, other refs still pass.

RUNNER: build.sh's pre-build tool-suite lane (source only, no marker).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(TOOLS, "land_gate.py")
HOOK = os.path.join(TOOLS, "hooks", "pre-push")
#: Verbatim the install command docs/OVERSEER-REFERENCE.md gives the controller.
INSTALL = 'install -m 0755 tools/hooks/pre-push "$(git rev-parse --git-common-dir)/hooks/pre-push"'

TEST_RULES = '''RULES = (
    ("docs/read-by-build.md", CODE, (), "scratch: a docs file the build reads"),
    ("docs/ledger.jsonl", CHECKED, ("tools/test_ledger_shape.py",), "scratch ledger"),
    ("docs/checkdir/", CHECKED, ("tools/test_ledger_shape.py",), "scratch prefix"),
)
'''

READER = '''import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def test_ledger_lines_parse():
    with open(os.path.join(ROOT, "docs", "ledger.jsonl")) as f:
        for line in f:
            if line.strip():
                json.loads(line)
'''


def _env(root):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "AEON_LAND_GATE", "PYTEST_"))}
    # HOME is NOT redirected: pytest lives in the user's site-packages under it, and the
    # hook's validation runs `python3 -m pytest`. Measured: with HOME in the scratch dir the
    # child printed "No module named pytest" and exited 1, which the gate reads, correctly,
    # as a refusal, so a row asserting a refusal went green for the wrong reason. The two
    # GIT_CONFIG_* variables are what keep the user's git config out.
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
               GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return env


def _git(cwd, env, *args):
    p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p.stdout.strip()


def _write(work, files):
    for rel, text in files.items():
        p = os.path.join(work, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)


@pytest.fixture(scope="module")
def template():
    """origin.git + work/, with the gate committed and the hook installed. Built once."""
    root = tempfile.mkdtemp(prefix="land-gate-tpl-")
    env = _env(root)
    work = os.path.join(root, "work")
    _git(root, env, "init", "-q", "--bare", "-b", "master", "origin.git")
    _git(root, env, "init", "-q", "-b", "master", "work")
    _git(work, env, "remote", "add", "origin", "../origin.git")    # relative: survives a copy
    base = {"engine/a.emp": "a\n", "docs/notes.md": "n\n", "docs/read-by-build.md": "r\n",
            "docs/ledger.jsonl": '{"a":1}\n', "docs/checkdir/x.md": "x\n"}
    _write(work, base)
    _git(work, env, "add", *base)
    _git(work, env, "commit", "-q", "-m", "base, before the gate")
    with open(GATE) as f:
        gate, n = re.subn(r"# >>> RULES.*?# <<< RULES",
                          "# >>> RULES\n" + TEST_RULES + "# <<< RULES", f.read(), flags=re.S)
    assert n == 1, "tools/land_gate.py must carry exactly one '# >>> RULES ... # <<< RULES' block"
    with open(HOOK) as f:
        hook = f.read()
    _write(work, {"tools/land_gate.py": gate, "tools/test_ledger_shape.py": READER,
                  "tools/hooks/pre-push": hook})
    os.chmod(os.path.join(work, "tools/hooks/pre-push"), 0o755)
    _git(work, env, "add", "tools")
    _git(work, env, "commit", "-q", "-m", "the gate")
    _git(work, env, "push", "-q", "--no-verify", "origin", "master")
    r = subprocess.run(["sh", "-c", INSTALL], cwd=work, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert os.access(os.path.join(work, ".git", "hooks", "pre-push"), os.X_OK)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


class Repo:
    def __init__(self, template, root):
        self.root = os.path.join(root, "r")
        shutil.copytree(template, self.root, symlinks=True)
        self.work = os.path.join(self.root, "work")
        self.env = _env(self.root)
        self.base = self.git("rev-parse", "HEAD~1")

    def git(self, *args, cwd=None):
        return _git(cwd or self.work, self.env, *args)

    def write(self, files):
        _write(self.work, files)

    def commit(self, files, msg="c"):
        self.write(files)
        self.git("add", *files)
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def push(self, *refspec, env=None, args=(), cwd=None):
        e = dict(self.env)
        e.update(env or {})
        p = subprocess.run(["git", "push", *args, "origin", *refspec], cwd=cwd or self.work,
                           env=e, capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def remote(self, ref="refs/heads/master"):
        out = self.git("ls-remote", "origin", ref)
        return out.split()[0] if out else None

    def gate(self, *args):
        p = subprocess.run([sys.executable, "tools/land_gate.py", *args], cwd=self.work,
                           env=self.env, capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def begin(self):
        rc, out = self.gate("begin")
        assert rc == 0, out
        line = [l for l in out.splitlines() if l.startswith("LAND_GATE_START ")]
        assert len(line) == 1, out
        return line[0].split()[1:], out

    def finish(self, head, key, clean, rc="0"):
        return self.gate("finish", "--head", head, "--key", key, "--clean", clean, "--rc", rc)

    def stamp(self):
        """What tools/landing_build.sh does around a green run, by the same two calls."""
        (head, key, clean), _ = self.begin()
        rc, out = self.finish(head, key, clean)
        return rc, out, key

    def stamp_file(self, key):
        return os.path.join(self.work, ".git", "aeon-land-gate", key + ".json")


@pytest.fixture
def repo(template):
    d = tempfile.mkdtemp(prefix="land-gate-")
    try:
        yield Repo(template, d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _refused(repo, rc, out, before):
    assert rc != 0, out
    assert "land-gate: REFUSED" in out, out
    assert repo.remote() == before, "the remote moved although the gate refused"


def test_other_refs_are_untouched_and_silent(repo):
    repo.git("checkout", "-q", "-b", "parcel/x")
    repo.commit({"engine/a.emp": "changed code, no stamp\n"})
    rc, out = repo.push("parcel/x")
    assert rc == 0, out
    assert "land-gate" not in out, out
    rc, out = repo.push("parcel/x:refs/heads/parcel/y")
    assert rc == 0 and "land-gate" not in out, out
    assert repo.remote("refs/heads/parcel/y") == repo.git("rev-parse", "HEAD")


def test_a_docs_only_master_push_needs_no_stamp(repo):
    sha = repo.commit({"docs/notes.md": "a booking\n", "docs/new/page.md": "p\n"})
    rc, out = repo.push("master")
    assert rc == 0, out
    assert "0 code, 0 checked, 2 docs" in out and "ALLOWED" in out, out
    assert "validating" not in out, out
    assert repo.remote() == sha


def test_a_code_push_without_a_stamp_is_refused(repo):
    before = repo.remote()
    repo.commit({"engine/a.emp": "new code\n"})
    rc, out = repo.push("master")
    _refused(repo, rc, out, before)
    assert "no stamp for this content" in out and "code: engine/a.emp" in out, out


def test_a_stamped_code_push_is_allowed(repo):
    sha = repo.commit({"engine/a.emp": "new code\n"})
    rc, out, key = repo.stamp()
    assert rc == 0 and "STAMP WRITTEN" in out, out
    with open(repo.stamp_file(key)) as f:
        assert json.load(f)["head"] == sha
    rc, out = repo.push("master")
    assert rc == 0 and "code proven green" in out, out
    assert repo.remote() == sha


def test_the_ledger_commit_after_a_verified_merge_needs_no_rebuild(repo):
    repo.commit({"engine/a.emp": "new code\n"})
    assert repo.stamp()[0] == 0
    sha = repo.commit({"docs/ledger.jsonl": '{"a":1}\n{"landed":true}\n',
                       "docs/notes.md": "the lane log\n"}, "ledger rows")
    rc, out = repo.push("master")
    assert rc == 0, out
    assert "code proven green" in out and "validated in" in out, out
    assert repo.remote() == sha


def test_a_ledger_line_that_breaks_its_reader_is_refused(repo):
    before = repo.remote()
    repo.commit({"docs/ledger.jsonl": '{"a":1}\nnot json\n'})
    rc, out = repo.push("master")
    _refused(repo, rc, out, before)
    # The READER must be what failed, on the bad line: not a missing pytest, not a missing file.
    assert "checked-path tests FAILED (exit 1)" in out and "1 failed" in out, out
    assert "JSONDecodeError" in out, out


def test_a_new_file_under_a_checked_prefix_is_validated(repo):
    sha = repo.commit({"docs/checkdir/new.md": "new\n"})
    rc, out = repo.push("master")
    assert rc == 0 and "0 code, 1 checked, 0 docs" in out and "validated in" in out, out
    assert repo.remote() == sha


def test_checked_paths_are_validated_in_the_pushed_commit_not_the_working_tree(repo):
    good = repo.commit({"docs/ledger.jsonl": '{"a":2}\n'})
    repo.write({"docs/ledger.jsonl": "dirty and not json\n"})
    rc, out = repo.push("master")
    assert rc == 0 and "validated in" in out, out        # the dirty file was not what ran
    assert repo.remote() == good
    repo.git("checkout", "--", "docs/ledger.jsonl")
    repo.commit({"docs/ledger.jsonl": "committed and not json\n"})
    repo.write({"docs/ledger.jsonl": '{"fixed":"but only on disk"}\n'})
    rc, out = repo.push("master")
    _refused(repo, rc, out, good)
    assert "1 failed" in out and "JSONDecodeError" in out, out


def test_a_docs_path_the_build_reads_needs_a_stamp(repo):
    before = repo.remote()
    repo.commit({"docs/read-by-build.md": "the build reads this\n"})
    rc, out = repo.push("master")
    _refused(repo, rc, out, before)
    assert "code: docs/read-by-build.md" in out, out


def test_a_stamp_for_other_content_does_not_count(repo):
    repo.commit({"engine/a.emp": "proven\n"})
    assert repo.stamp()[0] == 0
    before = repo.remote()
    repo.commit({"engine/a.emp": "proven, then changed\n"})
    rc, out = repo.push("master")
    _refused(repo, rc, out, before)


def test_a_stamp_that_is_not_complete_and_green_does_not_count(repo):
    repo.commit({"engine/a.emp": "new code\n"})
    rc, out = repo.gate("key")
    key = out.strip()
    os.makedirs(os.path.dirname(repo.stamp_file(key)), exist_ok=True)
    before = repo.remote()
    for body in ('{"key": "%s", "finished": 1}' % key, '{"key": "%s", "fini' % key,
                 '{"key": "%s"}' % key, '{"key": "%s", "finished": "0"}' % key, "", "[]"):
        with open(repo.stamp_file(key), "w") as f:
            f.write(body)
        rc, out = repo.push("master")
        _refused(repo, rc, out, before)


def test_finish_writes_no_stamp_when_head_moved(repo):
    repo.commit({"engine/a.emp": "at start\n"})
    (head, key, clean), _ = repo.begin()
    repo.commit({"engine/a.emp": "committed during the run\n"})
    rc, out = repo.finish(head, key, clean)
    assert rc == 3 and "HEAD MOVED" in out, out
    d = os.path.dirname(repo.stamp_file(key))
    assert not os.path.isdir(d) or not os.listdir(d), os.listdir(d)


def test_finish_writes_no_stamp_when_the_tree_changed_during_the_run(repo):
    (head, key, clean), _ = repo.begin()
    assert clean == "1"
    repo.write({"engine/a.emp": "edited during the run\n"})
    rc, out = repo.finish(head, key, clean)
    assert rc == 3 and "CHANGED during the run" in out, out
    assert not os.path.exists(repo.stamp_file(key))


def test_finish_writes_no_stamp_over_dirty_code_but_tolerates_dirty_docs(repo):
    repo.write({"engine/b.emp": "untracked code\n"})
    (head, key, clean), out = repo.begin()
    assert clean == "0" and "engine/b.emp" in out, out
    rc, out = repo.finish(head, key, clean)
    assert rc == 1 and "dirty at start" in out, out
    assert not os.path.exists(repo.stamp_file(key))
    os.remove(os.path.join(repo.work, "engine/b.emp"))
    repo.write({"docs/notes.md": "an unsaved booking\n", "docs/ledger.jsonl": "{}\n"})
    rc, out, key = repo.stamp()
    assert rc == 0 and "STAMP WRITTEN" in out, out


def test_finish_writes_no_stamp_for_a_run_that_was_not_green(repo):
    (head, key, clean), _ = repo.begin()
    for code in ("1", "2", "137"):
        rc, out = repo.finish(head, key, clean, rc=code)
        assert rc == 1 and "finished=%s" % code in out, out
        assert not os.path.exists(repo.stamp_file(key))


def test_deleting_master_is_refused(repo):
    before = repo.remote()
    rc, out = repo.push(":refs/heads/master")
    _refused(repo, rc, out, before)
    assert "DELETES master" in out, out


def test_the_bypasses(repo):
    sha = repo.commit({"engine/a.emp": "unproven\n"})
    rc, out = repo.push("master", env={"AEON_LAND_GATE": "skip"})
    assert rc == 0 and "GATE SKIPPED" in out and "UNVERIFIED" in out, out
    assert repo.remote() == sha
    sha = repo.commit({"engine/a.emp": "unproven again\n"})
    rc, out = repo.push("master", args=("--no-verify",))
    assert rc == 0 and "land-gate" not in out, out     # silent: why the variable is the one to use
    assert repo.remote() == sha


def test_a_checkout_that_predates_the_gate_refuses_master_only(repo):
    old = os.path.join(repo.root, "old")
    repo.git("worktree", "add", "-q", "--detach", old, repo.base)
    assert not os.path.exists(os.path.join(old, "tools", "land_gate.py"))
    rc, out = repo.push("HEAD:refs/heads/parcel/old", cwd=old)
    assert rc == 0 and "land-gate" not in out, out
    before = repo.remote()
    rc, out = repo.push("HEAD:refs/heads/master", args=("--force",), cwd=old)
    assert rc != 0 and "has no" in out and "REFUSED" in out, out
    assert repo.remote() == before


def test_nothing_outside_docs_is_ever_anything_but_code():
    sys.path.insert(0, TOOLS)
    import land_gate
    for p in ("build.sh", "CLAUDE.md", "README.md", "tools/x.py", "games/sonic4/map.toml",
              "docsx/a.md", "doc/a.md", ".gitignore", "tools/docs/a.md"):
        assert land_gate.classify(p) == land_gate.CODE, p
