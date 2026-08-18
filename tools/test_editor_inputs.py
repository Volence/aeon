"""Gate: the build-consumed editor inputs named by project.json are REAL and CARRIED.

WHY THIS EXISTS. The tools lens sweep (2026-08-13, D2/D3) found the level re-bake path
dead for two months, and both halves of that failure are about the same one field —
`project.json`'s `zones[0].tileset`:

  D2  It pointed at `ojz_tiles.bin`, which `.gitignore`'s blanket `*.bin` swallowed. The
      file lived on the authoring checkout and was carried by nothing, so
      `tools/regenerate-level.sh` could not run in any fresh clone or worktree, and
      `build.sh`'s STRESS_ART=1 shape was dead with it.
  D3  The obvious repair — point it at the TRACKED `chunks_tiles.bin` — is worse: that
      file is 0 bytes, and a zero-byte tileset bakes a BLANK LEVEL that every existing
      gate passes (every nametable index falls out of range, each is silently replaced
      by tile 0, the act dedupes to a 1-page 32-byte pool, and the only trace is the
      generator printing "Deduped: 1 (99.9% reduction)").

So the two failure modes that ACTUALLY HAPPENED are "points at something git does not
carry" and "points at something empty". This gate asserts the negation of both, and it
deliberately asserts a PROPERTY rather than a filename: whatever `project.json` names
must be tracked and non-empty. Hard-coding `ojz_tiles.bin` would pass the day someone
re-points the field at another untracked or empty blob, which is exactly the event worth
catching.

THE DRIFT VECTOR THIS DEFENDS AGAINST. The editor rewrites `project.json` wholesale on
save, so any repo-side correction to an editor-owned field has a shelf life of one
editing session — that is how the 2026-06-11 fix was reverted the very next day by an
editor state save the auto-commit daemon landed unreviewed. Tracking the tileset removed
the consequence; it did not remove the mechanism. This gate is the mechanism's alarm: a
revert now fails the build immediately instead of surfacing as a dead re-bake two months
later.

Runs on build.sh's pytest lane (build.sh runs `pytest tools`), so it is a real gate and
not a convention.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJECT_JSON = os.path.join(REPO, "project.json")


def _resolved_tileset() -> str:
    """Resolve zones[0].tileset the way ojz_strip_gen._project_tileset_path does.

    Kept in step with that function on purpose: a gate that resolves the path
    differently from the consumer can pass for a file the consumer never reads.
    """
    with open(PROJECT_JSON, "r") as f:
        proj = json.load(f)
    return os.path.join(os.path.dirname(PROJECT_JSON), proj["zones"][0]["tileset"])


def _is_tracked(path: str) -> bool:
    r = subprocess.run(
        ["git", "-C", REPO, "ls-files", "--error-unmatch", os.path.relpath(path, REPO)],
        capture_output=True,
    )
    return r.returncode == 0


class TestEditorInputsAreRealAndCarried(unittest.TestCase):
    def test_project_json_exists(self):
        self.assertTrue(
            os.path.isfile(PROJECT_JSON),
            f"project.json missing at {PROJECT_JSON} — the generators read zones[0].tileset "
            f"from it, so its absence kills the whole re-bake path.",
        )

    def test_resolved_tileset_exists_and_is_non_empty(self):
        """D3: a present-but-EMPTY tileset bakes a blank level every other gate passes."""
        p = _resolved_tileset()
        self.assertTrue(
            os.path.isfile(p),
            f"project.json's zones[0].tileset resolves to {p}, which does not exist. "
            f"The re-bake reads this blob; a dangling path means regenerate-level.sh "
            f"cannot run.",
        )
        self.assertGreater(
            os.path.getsize(p),
            0,
            f"project.json's zones[0].tileset resolves to {p}, which is ZERO BYTES. "
            f"This is the tools-lens D3 detonation: every nametable index falls out of "
            f"range, each is silently replaced by tile 0, and the act bakes to a 1-page "
            f"32-byte pool that verify_act_pool, verify_local_maps and art_rom_report all "
            f"ACCEPT. Point it at a real tile blob.",
        )

    def test_resolved_tileset_is_tracked_by_git(self):
        """D2: an untracked tileset works on the authoring box and nowhere else."""
        p = _resolved_tileset()
        self.assertTrue(
            _is_tracked(p),
            f"project.json's zones[0].tileset resolves to {p}, which git does NOT track. "
            f"It will be absent in every fresh clone and worktree, so the re-bake "
            f"(tools/regenerate-level.sh) and build.sh's STRESS_ART=1 shape both die there "
            f"while working fine here. If this is genuinely source data, negate it in "
            f".gitignore like games/sonic4/data/editor/ojz_tiles.bin — do NOT silently "
            f"force-add it, which is how the last one went missing for two months.",
        )

    def test_the_tileset_is_a_whole_number_of_tiles(self):
        """Cheap shape check: a 32-byte 4bpp tile blob divides evenly.

        Not a content check — it is here because it costs nothing and would catch a
        field re-pointed at some other kind of file that happens to be tracked and
        non-empty, which the two guards above would both accept.
        """
        p = _resolved_tileset()
        size = os.path.getsize(p)
        self.assertEqual(
            size % 32,
            0,
            f"{p} is {size} bytes, not a whole number of 32-byte tiles ({size % 32} over). "
            f"zones[0].tileset is expected to be a 4bpp tile blob.",
        )


if __name__ == "__main__":
    unittest.main()
