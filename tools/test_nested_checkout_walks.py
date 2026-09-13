#!/usr/bin/env python3
"""A tool that finds "source" by walking a checkout must not count a NESTED checkout.

THE DEFECT (measured 2026-09-13; booked in docs/DEFERRED_WORK.md, "CHAR-6 LEFT THREE
THINGS OPEN, AND A BUILD CHECK COUNTS SOURCE IN NESTED COPIES OF THE TREE", item 4).
A worktree registered as `.aeon-land-cv` sat inside the main folder.
`test_system_pool_release_empty.py` walked the whole checkout, counted `DeleteObject`'s
`cmpa.w #extern("System_Slots")` (engine/objects/core.emp) once in the tree and once in
the nested copy, expected 2 System-pool compares where the ROM correctly had 1, and
`tools/landing_build.sh` ended `finished=1` on correct code. The same content was green
in a clean checkout.

THE RULE the fixed walks now share is sigil's own: its module scan
(`crates/sigil-frontend-emp/src/resolve/manifest.rs`, `is_nested_checkout_dir`) does not
enter a child directory named `.worktrees` or one holding a `.git` entry (a FILE in a
linked worktree, a DIRECTORY in a clone); the root is always walked, whatever it holds.
`tools/artifact_provenance.py` already reproduced that rule to digest the scan; the
predicate now lives there once, as `is_nested_checkout_dir`, and every fixed walk imports
it. So "this checkout's sources" means the same thing to these tools as to the assembler.

WHY NOT `git ls-files`. Measured in a scratch repo (git 2.55.0): `git ls-files --cached
--others --exclude-standard` lists a nested worktree or clone as ONE directory entry
(`nested/`) and a `*.emp` pathspec drops it, so it would also have fixed the nesting. But
`--exclude-standard` drops a gitignored file, and sigil reads the disk, not the index: a
gitignored or untracked `.emp` under the root is in its module scan. The walks below
count exactly what they counted before, minus nested checkouts, and
`test_own_untracked_and_ignored_sources_still_count` holds that in place so a later
"simplify it to ls-files" shows up as a red here rather than as a silent shortfall.

WHAT IS COVERED HERE, and what is not:
  * `test_system_pool_release_empty` source derivation (`_emp_sources` and the three
    counts built on it). Build lane: its artifact tests are `needs_build`; these are not.
  * `emp_helper_closure.module_index`. It pruned dot-directories only, so a nested
    checkout whose name has no leading dot declared every module twice and failed the
    pre-build pytest lane (tools/test_emp_helper_closure.py).
  * `tools/emdash/count_dashes.py scan`. It skipped paths containing `/worktrees/` only.
  * NOT HERE: `tools/ls8_pin_redproof.py clear_pycache` got the same prune, but that
    script runs its mutations at import, so it cannot be imported by a test.
  The full enumeration of walking sites, with a verdict per site, is in
  docs/superpowers/notes/2026-09-13-test-walk.md.

THE SCRATCH CHECKOUT is a real `git init` in pytest's tmp_path with a real nested copy,
made both ways (`git worktree add` and `git clone`) and under both kinds of name (with a
leading dot, the case that bit; and without, the case the dot rule missed). Nothing is
created inside the real checkout.

Collected by build.sh's PRE-build pytest lane (`python3 -m pytest tools -m "not
needs_build"`), which runs in every canonical shape and therefore in landing_build.sh.
"""

import importlib.util
import os
import shutil
import subprocess

import pytest

import emp_helper_closure
import test_system_pool_release_empty as pool

HERE = os.path.dirname(os.path.abspath(__file__))

#: The line the pool derivation counts, spelled as engine/objects/core.emp spells it. The
#: comment carries ONE em dash (written as an escape here) so count_dashes has a subject.
COMPARE_LINE = '        cmpa.w  #extern("System_Slots"), a0   // pool classification \u2014 one\n'
CORE_REL = os.path.join("engine", "objects", "core.emp")

NESTED_KINDS = ("worktree", "clone")
#: `.nested-probe` is the shape that bit (`.aeon-land-cv`); `nested-probe` is the one
#: `emp_helper_closure`'s dot-directory rule could not see.
NESTED_NAMES = (".nested-probe", "nested-probe")


def _load_count_dashes():
    spec = importlib.util.spec_from_file_location(
        "count_dashes", os.path.join(HERE, "emdash", "count_dashes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd, *args):
    """Run git hermetically: no inherited repository, no user or system config."""
    if shutil.which("git") is None:
        pytest.fail("git is not on PATH, so a real nested checkout cannot be built and "
                    "this file cannot ask its question. That is not a pass.")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    r = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=cwd, env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, "git %s failed:\n%s%s" % (" ".join(args), r.stdout, r.stderr)
    return r.stdout


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _make_checkout(tmp_path, kind, name):
    """A committed scratch checkout with ONE compare line, plus a nested copy of it."""
    outer = str(tmp_path / "outer")
    os.makedirs(outer)
    _git(outer, "init", "-q")
    _write(os.path.join(outer, CORE_REL), "module engine.objects.core\n" + COMPARE_LINE)
    _git(outer, "add", CORE_REL)
    _git(outer, "commit", "-q", "-m", "base")
    nested = os.path.join(outer, name)
    if kind == "worktree":
        _git(outer, "worktree", "add", "-q", nested, "HEAD")
    else:
        _git(outer, "clone", "-q", outer, nested)
    # Anti-vacuity: the nested copy really is a checkout, really holds the line, and a
    # walk that does not prune it really does see two. Without this, a nested copy that
    # silently failed to appear would let every assertion below pass for the wrong reason.
    assert os.path.exists(os.path.join(nested, ".git")), "the nested copy is not a checkout"
    naive = 0
    for dirpath, dirs, files in os.walk(outer):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if f.endswith(".emp"):
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    naive += fh.read().count('cmpa.w  #extern("System_Slots")')
    assert naive == 2, "control: an unpruned walk should see the line twice, saw %d" % naive
    return outer, nested


@pytest.mark.parametrize("name", NESTED_NAMES)
@pytest.mark.parametrize("kind", NESTED_KINDS)
class TestNestedCheckoutIsNotSource:

    def test_pool_compare_count_is_this_checkouts(self, tmp_path, kind, name):
        """The measured defect: 2 where the checkout holds 1."""
        outer, _ = _make_checkout(tmp_path, kind, name)
        assert pool.source_compare_sites(root=outer) == [(CORE_REL, 2)]

    def test_pool_source_list_stops_at_the_nested_checkout(self, tmp_path, kind, name):
        outer, _ = _make_checkout(tmp_path, kind, name)
        assert [os.path.relpath(p, outer) for p in pool._emp_sources(root=outer)] == [CORE_REL]

    def test_the_nested_checkout_is_still_walked_as_its_own_root(self, tmp_path, kind, name):
        """The root is always walked even though it holds a `.git` (every linked worktree's
        root does, this one's included), so pruning children does not empty a worktree."""
        _, nested = _make_checkout(tmp_path, kind, name)
        assert pool.source_compare_sites(root=nested) == [(CORE_REL, 2)]

    def test_module_index_declares_each_module_once(self, tmp_path, kind, name):
        """Before the fix a nested checkout without a leading dot raised
        `module id engine.objects.core declared twice`."""
        outer, _ = _make_checkout(tmp_path, kind, name)
        assert emp_helper_closure.module_index(outer) == {
            "engine.objects.core": os.path.join(outer, CORE_REL)}

    def test_count_dashes_counts_this_checkouts_dashes(self, tmp_path, kind, name):
        import pathlib
        outer, _ = _make_checkout(tmp_path, kind, name)
        _per, _files, em, en, _esc = _load_count_dashes().scan(pathlib.Path(outer))
        assert (em, en) == (1, 0)


def test_own_untracked_and_ignored_sources_still_count(tmp_path):
    """No FEWER than before: sigil's scan reads the disk, not the index, so an untracked
    `.emp` and a gitignored one under the root are both this checkout's sources. A
    `git ls-files --exclude-standard` enumeration would drop the ignored one (count 2)."""
    outer, _ = _make_checkout(tmp_path, "worktree", ".nested-probe")
    _write(os.path.join(outer, ".gitignore"), "gen/\n")
    _write(os.path.join(outer, "gen", "made.emp"), COMPARE_LINE)
    _write(os.path.join(outer, "engine", "objects", "new.emp"), COMPARE_LINE)
    assert _git(outer, "check-ignore", "gen/made.emp").strip() == "gen/made.emp"
    got = sorted(pool.source_compare_sites(root=outer))
    assert got == sorted([(CORE_REL, 2), (os.path.join("engine", "objects", "new.emp"), 1),
                          (os.path.join("gen", "made.emp"), 1)])
