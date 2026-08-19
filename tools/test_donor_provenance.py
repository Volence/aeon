"""Gate: the donor-revision stamp tells the truth, including when it cannot.

WHY THIS EXISTS. The committed level tree is baked from two out-of-repo donors
(`sonic_hack`, `skdisasm`) whose revisions were recorded NOWHERE — the closing
remainder of the 2026-08-18 tools lens packet. `tools/donor_provenance.py` stamps
them during a re-bake. This suite tests that stamping in ISOLATION, against real
throwaway git repositories built in a tempdir: a full re-bake is destructive and
needs both donors present, so it is not a thing a test lane may run.

WHAT IT ASSERTS, and why each one is a way the stamp could lie rather than fail:

  * a clean checkout is recorded with its real HEAD and dirty=false
  * a checkout with an uncommitted edit is recorded dirty — a SHA alone does not
    identify what was read, and silently implying it does is the failure this
    whole file exists to prevent
  * untracked files are counted SEPARATELY from tracked modifications, so a stray
    editor swapfile in a donor does not cry wolf
  * a non-git directory and an absent directory are DISTINGUISHABLE, and neither
    is reported as clean by omission (head=None, dirty=None) — "unknown" must
    never render as "fine"
  * the record is a deterministic function of its inputs: two calls with nothing
    changed produce byte-identical output, so a re-bake that changed nothing
    produces no diff here
  * mode is constrained to the two honest claims, and `backfill` is not silently
    upgradeable to `rebake`
  * the path `generate()` writes derives from its out_dir and agrees with the
    module constant — the tools-lens-D8 property (a module-constant destination
    writes committed data straight through a test's redirect)
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donor_provenance  # noqa: E402

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _git(repo, *args):
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
    )
    return subprocess.run(["git", "-C", repo, *args], capture_output=True,
                          text=True, env=env, check=True).stdout.strip()


def _make_repo(path):
    """A throwaway git repo with one commit; returns its HEAD sha."""
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    with open(os.path.join(path, "donor.txt"), "w") as f:
        f.write("original\n")
    _git(path, "add", "donor.txt")
    _git(path, "commit", "-qm", "seed")
    return _git(path, "rev-parse", "HEAD")


class TestDescribeRepo(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name
        self.addCleanup(self._td.cleanup)

    def test_clean_repo_records_head_and_is_not_dirty(self):
        p = os.path.join(self.tmp, "clean")
        sha = _make_repo(p)
        rec = donor_provenance.describe_repo(p)
        self.assertEqual(rec["status"], "git")
        self.assertEqual(rec["head"], sha)
        self.assertEqual(len(rec["head"]), 40, "HEAD must be the full sha, not abbreviated")
        self.assertFalse(rec["dirty"])
        self.assertEqual(rec["modified_tracked"], 0)
        self.assertEqual(rec["untracked"], 0)

    def test_modified_tracked_file_makes_it_dirty(self):
        p = os.path.join(self.tmp, "dirty")
        sha = _make_repo(p)
        with open(os.path.join(p, "donor.txt"), "w") as f:
            f.write("EDITED — this byte is not in the recorded sha\n")
        rec = donor_provenance.describe_repo(p)
        self.assertEqual(rec["head"], sha, "HEAD is still recorded; the sha is just not sufficient")
        self.assertTrue(rec["dirty"], "an uncommitted donor edit MUST show as dirty — "
                                      "otherwise the stamp claims reproducibility it does not have")
        self.assertEqual(rec["modified_tracked"], 1)

    def test_untracked_file_is_counted_but_is_not_dirtiness(self):
        p = os.path.join(self.tmp, "untracked")
        _make_repo(p)
        with open(os.path.join(p, "scratch.tmp"), "w") as f:
            f.write("x\n")
        rec = donor_provenance.describe_repo(p)
        self.assertFalse(rec["dirty"], "an untracked stray file is not a modification of what was read")
        self.assertEqual(rec["untracked"], 1)
        self.assertEqual(rec["modified_tracked"], 0)

    def test_non_git_directory_is_unknown_not_clean(self):
        p = os.path.join(self.tmp, "plain")
        os.makedirs(p)
        rec = donor_provenance.describe_repo(p)
        self.assertEqual(rec["status"], "not-a-git-repo")
        self.assertIsNone(rec["head"])
        self.assertIsNone(rec["dirty"], "unknown dirtiness must be None, never False — "
                                        "False reads as 'verified clean'")

    def test_absent_directory_is_distinguishable_from_non_git(self):
        rec = donor_provenance.describe_repo(os.path.join(self.tmp, "does-not-exist"))
        self.assertEqual(rec["status"], "absent")
        self.assertIsNone(rec["head"])
        self.assertIsNone(rec["dirty"])

    def test_describe_repo_does_not_write_to_the_repo_it_inspects(self):
        """Donors are other people's repositories; a query must not mutate one.

        Plain `git status` refreshes and REWRITES the index as a side effect, which
        is why the implementation passes --no-optional-locks. Measured by mtime over
        the whole .git directory.
        """
        p = os.path.join(self.tmp, "readonly")
        _make_repo(p)
        with open(os.path.join(p, "donor.txt"), "w") as f:
            f.write("touched so a refresh would have work to do\n")

        def snap():
            out = {}
            for dirpath, _d, files in os.walk(os.path.join(p, ".git")):
                for fn in files:
                    fp = os.path.join(dirpath, fn)
                    try:
                        out[fp] = os.stat(fp).st_mtime_ns
                    except OSError:
                        pass
            return out

        before = snap()
        self.assertGreater(len(before), 0)
        donor_provenance.describe_repo(p)
        after = snap()
        changed = sorted(k for k in set(before) | set(after)
                         if before.get(k) != after.get(k))
        self.assertEqual(changed, [], f"inspecting a donor wrote into its .git: {changed}")


class TestRecordShape(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name
        self.addCleanup(self._td.cleanup)
        self.sh = os.path.join(self.tmp, "sonic_hack")
        self.sk = os.path.join(self.tmp, "skdisasm")
        self.gen = os.path.join(self.tmp, "aeon")
        self.sh_sha = _make_repo(self.sh)
        self.sk_sha = _make_repo(self.sk)
        self.gen_sha = _make_repo(self.gen)

    def _build(self, mode="rebake", **kw):
        return donor_provenance.build_provenance(
            mode, sonic_hack=self.sh, skdisasm=self.sk, generator_repo=self.gen, **kw)

    def test_both_donor_shas_are_present(self):
        rec = self._build()
        self.assertEqual(rec["donors"]["sonic_hack"]["head"], self.sh_sha)
        self.assertEqual(rec["donors"]["skdisasm"]["head"], self.sk_sha)
        self.assertEqual(rec["generator"]["head"], self.gen_sha)
        self.assertEqual(rec["mode"], "rebake")
        self.assertEqual(rec["schema"], donor_provenance.SCHEMA)
        # The env var is recorded so a reader knows how to point at the checkout.
        self.assertEqual(rec["donors"]["sonic_hack"]["env_var"], "AEON_SONIC_HACK_DIR")
        self.assertEqual(rec["donors"]["skdisasm"]["env_var"], "AEON_SKDISASM_DIR")

    def test_generator_records_its_revision_but_not_its_checkout_location(self):
        """A re-bake from a git worktree must not stamp a throwaway agent path."""
        rec = self._build()
        self.assertEqual(rec["generator"]["head"], self.gen_sha)
        self.assertNotIn("path", rec["generator"])
        self.assertNotIn("branch", rec["generator"])
        self.assertIn("path", rec["donors"]["sonic_hack"],
                      "donor paths DO belong: they are out-of-repo checkouts")

    def test_mode_backfill_carries_its_caveat_date_and_rebake_does_not(self):
        back = self._build("backfill", recorded_at="2026-08-18")
        self.assertEqual(back["mode"], "backfill")
        self.assertEqual(back["recorded_at"], "2026-08-18")
        rebake = self._build("rebake")
        self.assertNotIn("recorded_at", rebake,
                         "a re-bake stamp must stay a deterministic function of its "
                         "inputs — a clock reading makes every re-bake diff")

    def test_an_invented_mode_is_refused(self):
        """POISON: the two modes are different truth claims. No third one may pass."""
        for bad in ("verified", "reproducible", "", None, "REBAKE"):
            with self.assertRaises(ValueError, msg=f"mode={bad!r} was accepted"):
                self._build(bad)

    def test_render_is_deterministic(self):
        a = donor_provenance.render(self._build())
        b = donor_provenance.render(self._build())
        self.assertEqual(a, b)
        self.assertTrue(a.endswith("\n"))
        json.loads(a)

    def test_a_dirty_donor_survives_into_the_written_file(self):
        with open(os.path.join(self.sh, "donor.txt"), "w") as f:
            f.write("uncommitted\n")
        out = os.path.join(self.tmp, "out", "DONOR_PROVENANCE.json")
        donor_provenance.write_provenance(
            "rebake", path=out, sonic_hack=self.sh, skdisasm=self.sk,
            generator_repo=self.gen)
        with open(out) as f:
            written = json.load(f)
        self.assertTrue(written["donors"]["sonic_hack"]["dirty"])
        self.assertFalse(written["donors"]["skdisasm"]["dirty"])

    def test_missing_donor_is_stamped_unknown_rather_than_omitted(self):
        rec = donor_provenance.build_provenance(
            "backfill", sonic_hack=os.path.join(self.tmp, "gone"),
            skdisasm=self.sk, generator_repo=self.gen)
        d = rec["donors"]["sonic_hack"]
        self.assertEqual(d["status"], "absent")
        self.assertIsNone(d["head"])
        self.assertIn("skdisasm", rec["donors"], "one bad donor must not drop the other")
        self.assertEqual(rec["donors"]["skdisasm"]["head"], self.sk_sha)


class TestWiring(unittest.TestCase):
    def test_generate_writes_provenance_into_its_own_out_dir(self):
        """D8 property, read off the source: the destination must derive from out_dir.

        A module-constant destination is how a redirected generator kept writing
        committed ROM data. Asserted structurally because running generate() needs
        both donors and is destructive.
        """
        src = open(os.path.join(REPO, "tools", "ojz_strip_gen.py")).read()
        self.assertIn('donor_provenance.write_provenance(', src)
        self.assertIn('path=os.path.join(out_dir, "DONOR_PROVENANCE.json")', src,
                      "generate() must derive the provenance destination from out_dir; "
                      "a module constant writes the committed file through the "
                      "tempdir redirect test_full_pipeline_runs installs (tools lens D8)")

    def test_the_module_constant_names_the_same_file_generate_writes(self):
        import ojz_strip_gen
        self.assertEqual(
            os.path.normpath(donor_provenance.PROVENANCE_PATH),
            os.path.normpath(os.path.join(ojz_strip_gen.OUTPUT_DIR, "DONOR_PROVENANCE.json")),
            "the --backfill entry point and the re-bake would write DIFFERENT files, "
            "so one would silently shadow the other")

    def test_one_authority_for_the_skdisasm_donor_root(self):
        """preflight, the importer and the stamp must resolve the SAME checkout.

        If they diverge, preflight passes for a run that then fails destructively
        (tools lens D1) and the stamp names a checkout that contributed nothing.
        """
        import ojz_common
        # RESTORE, do not delete: on an authoring machine AEON_SKDISASM_DIR is set,
        # and deleting it here left every later test in the same pytest process
        # unable to find the donor. Caught by running the whole lane rather than
        # this file — a test that passes alone and poisons its neighbours is the
        # worst kind.
        prior = os.environ.get("AEON_SKDISASM_DIR")
        os.environ["AEON_SKDISASM_DIR"] = "/nonexistent/sk-probe"
        try:
            self.assertEqual(ojz_common.skdisasm_root(), "/nonexistent/sk-probe")
        finally:
            if prior is None:
                os.environ.pop("AEON_SKDISASM_DIR", None)
            else:
                os.environ["AEON_SKDISASM_DIR"] = prior
        # Both consumers call the shared resolver rather than re-deriving it.
        for tool in ("ojz_strip_gen.py", "import_sk_collision.py"):
            src = open(os.path.join(REPO, "tools", tool)).read()
            self.assertIn("skdisasm_root()", src, f"{tool} no longer uses the shared resolver")
            self.assertNotIn('os.environ.get("AEON_SKDISASM_DIR")', src,
                             f"{tool} re-derives the skdisasm root instead of calling "
                             f"ojz_common.skdisasm_root()")


if __name__ == "__main__":
    unittest.main()
