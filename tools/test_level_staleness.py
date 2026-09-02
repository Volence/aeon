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

THE DELETION CLASS (added 2026-09-02, aurora walkthrough finding b2). The gate had ONE
arm — newest editor mtime vs newest generated mtime — and its docstring claimed the arm
"cannot miss a real edit". It missed the commonest revert there is. mtime is monotonic
per file, so DELETING an editor document lowers nothing: the tree read fresh, the
re-bake never ran, and the same build error came back byte-identical about a file that
was already gone, as many times as the author ran the build. `TestDeletionIsVisible`
below is that repro, and it asserts BOTH halves — that the mtime arm alone says fresh
(so the test is measuring the real blindness, not a strawman) and that the content-stamp
arm says stale and names the file. A test that only asserted the new arm's `True` would
pass just as well against a gate that was never blind.
"""

import json
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
    """A minimal fake repo: project.json + games/g/data/{editor,generated}.

    STAMPED BY DEFAULT, because that is the state a checked-out tree is in: the
    re-bake writes the stamp and it is committed with the generated tree. A test that
    built an unstamped tree would be testing the bootstrap case, not the gate.
    """

    def __init__(self, base, game="g", editor_t=1000, generated_t=2000, stamp=True):
        self.base = base
        self.game = game
        self.editor = os.path.join(base, "games", game, "data", "editor")
        self.generated = os.path.join(base, "games", game, "data", "generated")
        _touch(os.path.join(base, "project.json"), editor_t)
        _touch(os.path.join(self.editor, "ojz", "act1", "section_0.tiles.bin"), editor_t)
        _touch(os.path.join(self.generated, "ojz", "act1", "sec0_blocks.bin"), generated_t)
        if stamp:
            self.stamp()

    def stamp(self):
        return ls.write_stamp(self.game, repo=self.base)

    def add(self, *parts, content=b"x", mtime=1000):
        """Write a file under the editor tree, at a chosen mtime."""
        path = os.path.join(self.editor, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        os.utime(path, (mtime, mtime))
        return path

    def check(self):
        return ls.check(self.game, repo=self.base)

    def mtime_arm(self):
        return ls.mtime_arm(self.game, repo=self.base)

    def stamp_arm(self):
        return ls.stamp_arm(self.game, repo=self.base)


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


class TestDeletionIsVisible(unittest.TestCase):
    """THE b2 REPRO. Author something illegal, then revert it by DELETING the file.

    Every test here holds the two arms apart on purpose. The claim being made is not
    "the gate fires" — it is "the gate fires on the one input the old gate could not
    represent", and the only way to say that is to show the old arm still saying fresh
    on the same tree, at the same moment.
    """

    def test_a_deleted_editor_file_is_STALE_and_the_mtime_arm_alone_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            victim = t.add("effects", "presets", "cold_test_band.json", mtime=1000)
            t.stamp()                       # the bake read it
            self.assertFalse(t.check()[0])  # ... and the tree is fresh

            os.remove(victim)               # the revert a person actually performs
            self.assertFalse(os.path.exists(victim))

            # ARM A — the whole gate before this parcel. Deleting lowers no mtime, so
            # it still reads fresh. THIS assertion is the defect, pinned.
            a_stale, a_msg = t.mtime_arm()
            self.assertFalse(
                a_stale,
                "the mtime arm reported the deletion — then this test is no longer "
                "measuring the blindness it exists for, and its companion assertion "
                f"below proves nothing: {a_msg}")

            # ARM B — the fix.
            b_stale, b_msg = t.stamp_arm()
            self.assertTrue(b_stale, b_msg)
            self.assertIn("cold_test_band.json", b_msg)
            self.assertIn("removed", b_msg)

            stale, msg = t.check()
            self.assertTrue(stale, msg)

    def test_it_stays_stale_however_many_times_you_ask(self):
        """The other half of the owner's complaint: the error REPEATED. A gate that
        fired once and then latched clean would reproduce the bug in a new place."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            victim = t.add("effects", "presets", "gone.json", mtime=1000)
            t.stamp()
            os.remove(victim)
            for attempt in range(3):
                self.assertTrue(t.check()[0], f"went green on attempt {attempt + 1}")

    def test_touch_is_NOT_the_escape_hatch(self):
        """The old escape was `touch` on any editor file, which nothing documented.
        Arm B reads no timestamps, so touching cannot clear it — and touching in fact
        makes the OTHER arm fire too, which is the honest outcome."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            victim = t.add("effects", "presets", "gone.json", mtime=1000)
            t.stamp()
            os.remove(victim)
            survivor = os.path.join(t.editor, "ojz", "act1", "section_0.tiles.bin")
            os.utime(survivor, (9000, 9000))
            stale, msg = t.check()
            self.assertTrue(stale, f"`touch` cleared the gate: {msg}")
            self.assertTrue(t.stamp_arm()[0], "the stamp arm was cleared by a touch")

    def test_re_baking_is_the_escape_hatch(self):
        """And it must actually work, or the gate is a wall rather than a gate."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            victim = t.add("effects", "presets", "gone.json", mtime=1000)
            t.stamp()
            os.remove(victim)
            self.assertTrue(t.check()[0])
            t.stamp()                                   # what the re-bake does, last
            os.utime(os.path.join(t.generated, "ojz", "act1", "sec0_blocks.bin"),
                     (9000, 9000))                      # ...and what it writes
            stale, msg = t.check()
            self.assertFalse(stale, msg)

    def test_an_ADDED_file_with_an_OLD_mtime_is_STALE(self):
        """The set can grow invisibly too: `cp -p` / a restored backup / a moved file
        arrives with an mtime older than the bake, so arm A sees nothing there either."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            t.add("effects", "presets", "arrived.json", mtime=1500)
            self.assertFalse(t.mtime_arm()[0], "arm A saw a file older than the bake")
            b_stale, b_msg = t.stamp_arm()
            self.assertTrue(b_stale, b_msg)
            self.assertIn("added", b_msg)
            self.assertIn("arrived.json", b_msg)

    def test_a_CONTENT_change_under_an_old_mtime_is_STALE(self):
        """Same shape, third direction — content restored over a file without moving
        its timestamp forward. Arm A is blind; the digest is not."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            p = t.add("effects", "presets", "edited.json", content=b"before", mtime=1000)
            t.stamp()
            with open(p, "wb") as f:
                f.write(b"after!")           # same length, so a size compare would miss
            os.utime(p, (1000, 1000))
            self.assertFalse(t.mtime_arm()[0])
            b_stale, b_msg = t.stamp_arm()
            self.assertTrue(b_stale, b_msg)
            self.assertIn("changed", b_msg)
            self.assertIn("edited.json", b_msg)


class TestTheStampItself(unittest.TestCase):
    def test_a_missing_stamp_is_STALE_not_a_skip(self):
        """'No record of what was baked' must not read as 'it was baked from this'.
        The safe direction is the one whose remedy is a re-bake."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000, stamp=False)
            stale, msg = t.check()
            self.assertTrue(stale, msg)
            self.assertIn("missing or unreadable", msg)

    def test_a_stamp_from_another_schema_is_STALE_not_silently_compared(self):
        """A manifest built by different walk/exclusion/digest rules is not evidence
        about this one. Version it, or the next rules change compares apples to pears
        and reports a tree-wide diff or, worse, a spurious match."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            path = ls.stamp_path(t.game, repo=d)
            with open(path) as f:
                doc = json.load(f)
            doc["schema"] = ls.STAMP_SCHEMA + 1
            with open(path, "w") as f:
                json.dump(doc, f)
            self.assertIsNone(ls.read_stamp(t.game, repo=d))
            self.assertTrue(t.check()[0])

    def test_a_corrupt_stamp_is_STALE_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            with open(ls.stamp_path(t.game, repo=d), "w") as f:
                f.write("{not json")
            self.assertTrue(t.check()[0])

    def test_the_stamp_honours_the_SAME_exclusions_as_the_mtime_arm(self):
        """Both arms call walk_files, so this is structural — but it is exactly the
        kind of structure that gets forked by a later 'small' change, and a stamp that
        recorded backup snapshots would go stale every time one was written."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            t.add("ojz", "act1", ".pre-sk-import-backup", "section_0.tiles.bin", mtime=9000)
            t.add("ojz", "act1", "export", "dump.bin", mtime=9000)
            t.add(".DS_Store", mtime=9000)
            t.add("objects.json~", mtime=9000)
            t.add("section_0.tiles.bin.tmp", mtime=9000)
            fp = ls.editor_fingerprint(t.game, repo=d)
            for excluded in (".pre-sk-import-backup", "export", ".DS_Store",
                             "objects.json~", ".tmp"):
                self.assertFalse([k for k in fp if excluded in k],
                                 f"{excluded} entered the stamp: {sorted(fp)}")
            self.assertFalse(t.check()[0])

    def test_the_stamp_is_NOT_inside_the_editor_tree_or_the_generated_tree(self):
        """Inside `editor/` it would be an input to itself (writing it makes the tree
        stale, forever). Under `generated/` verify_level_bin.py's orphan sweep would
        report it as an artifact nothing embeds."""
        with tempfile.TemporaryDirectory() as d:
            t = _Tree(d, editor_t=1000, generated_t=2000)
            path = os.path.abspath(ls.stamp_path(t.game, repo=d))
            self.assertFalse(path.startswith(os.path.abspath(t.editor) + os.sep))
            self.assertFalse(path.startswith(os.path.abspath(t.generated) + os.sep))
            self.assertNotIn(path, ls.walk_files(ls.editor_sources(t.game, d)))
            # ...and writing it twice in a row does not make the tree stale.
            t.stamp()
            t.stamp()
            self.assertFalse(t.check()[0])

    def test_the_real_sonic4_tree_carries_a_matching_stamp(self):
        """THE ONE THAT WOULD HAVE CAUGHT A FORGOTTEN COMMIT. The stamp is a committed
        artifact; if it is absent or stale on master, every canonical build hard-fails
        and the remedy is a re-bake, so this failing here is much cheaper than it
        failing in someone's build."""
        if not os.path.isdir(os.path.join(REPO, "games", "sonic4", "data", "editor")):
            self.skipTest("no sonic4 editor tree in this checkout")
        stamped = ls.read_stamp("sonic4")
        self.assertIsNotNone(
            stamped,
            f"{os.path.relpath(ls.stamp_path('sonic4'), REPO)} is missing or "
            f"unreadable — run `tools/regenerate-level.sh` and commit it.")
        added, removed, changed = ls.stamp_diff(ls.editor_fingerprint("sonic4"), stamped)
        self.assertEqual(
            (added, removed, changed), ([], [], []),
            "the committed editor-source stamp does not match the editor tree "
            "(added/removed/changed above) — re-bake and commit the stamp.")


if __name__ == "__main__":
    unittest.main()
