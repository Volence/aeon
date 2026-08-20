"""Gate for the level-data staleness check (tools/level_staleness.py).

WHY THIS EXISTS. The check it tests is a build.sh HARD FAILURE, so both of its error
directions are expensive: a miss re-opens the silent-stale-data trap it was written to
close (Aurora session, 2026-08-19 — save, build, reload, get the PREVIOUS level data),
and a spurious fire blocks every build on a clean checkout. Neither direction is visible
from reading the tool, because both depend on mtimes.

These tests build synthetic trees rather than looking at the repo's real one, so they
assert the MECHANISM and not today's timestamps. The exception is the last test, which
does look at the repo — to make sure the real editor tree contains at least one of the
excluded directories, so that the exclusion list is being exercised by something and not
just described.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import level_staleness as ls  # noqa: E402

REPO = ls.REPO


def _touch(path, mtime):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x")
    os.utime(path, (mtime, mtime))


class _Tree:
    """A minimal fake repo: project.json + games/g/data/{editor,generated}."""

    def __init__(self, base, game="g", editor_t=1000, generated_t=2000):
        self.base = base
        self.game = game
        self.editor = os.path.join(base, "games", game, "data", "editor")
        self.generated = os.path.join(base, "games", game, "data", "generated")
        _touch(os.path.join(base, "project.json"), editor_t)
        _touch(os.path.join(self.editor, "ojz", "act1", "section_0.tiles.bin"), editor_t)
        _touch(os.path.join(self.generated, "ojz", "act1", "sec0_blocks.bin"), generated_t)

    def check(self):
        return ls.check(self.game, repo=self.base)


class TestStaleness(unittest.TestCase):
    def test_generated_newer_is_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            stale, msg = _Tree(d, editor_t=1000, generated_t=2000).check()
            self.assertFalse(stale, msg)

    def test_editor_newer_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            stale, msg = _Tree(d, editor_t=3000, generated_t=2000).check()
            self.assertTrue(stale, msg)
            self.assertIn("section_0.tiles.bin", msg)

    def test_equal_seconds_is_fresh(self):
        """THE fresh-clone case. `git clone`/`git worktree add` write every file within
        the same second in arbitrary order, so equal-second must NOT read as an edit —
        otherwise every pristine checkout fails its first build."""
        with tempfile.TemporaryDirectory() as d:
            stale, msg = _Tree(d, editor_t=2000, generated_t=2000).check()
            self.assertFalse(stale, msg)

    def test_sub_second_difference_is_fresh(self):
        """Whole-second truncation: 2000.9 editor vs 2000.1 generated is NOT stale."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=2000.1, generated_t=2000.1)
            os.utime(
                os.path.join(t.editor, "ojz", "act1", "section_0.tiles.bin"),
                (2000.9, 2000.9),
            )
            stale, msg = t.check()
            self.assertFalse(stale, msg)

    def test_project_json_counts_as_an_editor_source(self):
        """ojz_strip_gen reads zones[0].tileset out of it, so it is a real input."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            _touch(os.path.join(d, "project.json"), 3000)
            stale, msg = t.check()
            self.assertTrue(stale, msg)
            self.assertIn("project.json", msg)

    def test_editor_bg_override_counts_as_an_editor_source(self):
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            _touch(
                os.path.join(d, "games", "g", "data", "editor_bg_override.json"), 3000
            )
            stale, msg = t.check()
            self.assertTrue(stale, msg)

    def test_backup_dirs_are_excluded(self):
        """A restored/created backup snapshot must not read as an edit."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            for backup in (
                ".pre-sk-import-backup",
                ".empty-collattr-backup",
                ".reset-backup-2026-06-20",
                ".pre-wysiwyg-backup-2026-06-20",
            ):
                _touch(
                    os.path.join(t.editor, "ojz", "act1", backup, "section_0.tiles.bin"),
                    9000,
                )
            stale, msg = t.check()
            self.assertFalse(stale, msg)

    def test_export_dir_is_excluded(self):
        """data/editor/ojz/act1/export/ is an editor OUTPUT, not a generator input."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            _touch(os.path.join(t.editor, "ojz", "act1", "export", "dump.bin"), 9000)
            stale, msg = t.check()
            self.assertFalse(stale, msg)

    def test_dotfiles_and_scratch_are_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            _touch(os.path.join(t.editor, ".DS_Store"), 9000)
            _touch(os.path.join(t.editor, "section_0.tiles.bin.tmp"), 9000)
            _touch(os.path.join(t.editor, "objects.json~"), 9000)
            stale, msg = t.check()
            self.assertFalse(stale, msg)

    def test_missing_generated_tree_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            os.remove(os.path.join(t.generated, "ojz", "act1", "sec0_blocks.bin"))
            stale, msg = t.check()
            self.assertTrue(stale, msg)
            self.assertIn("NO generated tree", msg)

    def test_game_without_an_editor_tree_is_not_applicable(self):
        """demo has no data/editor — the gate must be silent, not stale."""
        with tempfile.TemporaryDirectory() as d:
            stale, msg = ls.check("nosucheditor", repo=d)
            self.assertFalse(stale)
            self.assertIn("n/a", msg)

    def test_the_real_repo_exercises_at_least_one_exclusion_or_says_why(self):
        """Not a timestamp assertion — a check that the exclusion list is aimed at
        something real. The repo's editor tree carries manual backup snapshots
        (.pre-sk-import-backup and friends) on an authoring checkout; a fresh worktree
        has none, which is fine and is what the skip message records."""
        editor = os.path.join(REPO, "games", "sonic4", "data", "editor")
        if not os.path.isdir(editor):
            self.skipTest("no sonic4 editor tree here")
        excluded = [
            os.path.join(dp, d)
            for dp, dn, _ in os.walk(editor)
            for d in dn
            if ls._skip_dir(d)
        ]
        if not excluded:
            self.skipTest(
                "this checkout carries no excluded editor dirs (backup snapshots and "
                "export/ are untracked, so a fresh worktree has none) — nothing to exercise"
            )
        # Whatever is excluded must not be able to move the answer.
        _, before = ls.newest(ls.editor_sources("sonic4"))
        for path in excluded:
            self.assertFalse(
                os.path.commonpath([before, path]) == path,
                f"{before} was selected as the newest editor source but lives under the "
                f"excluded directory {path} — the walk is not pruning.",
            )


if __name__ == "__main__":
    unittest.main()
