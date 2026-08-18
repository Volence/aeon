"""Gate: a generator invoked with a redirected output must not touch the committed tree.

WHY THIS EXISTS. tools lens sweep D8. `ojz_strip_gen.test_full_pipeline_runs()` redirects
`OUTPUT_DIR` to a tempdir and calls `generate()`. But `generate()`'s Pass 8 called
`ojz_entity_gen.generate()`, whose `OUTPUT_PATH` is a module CONSTANT pointing at
`games/sonic4/data/generated/ojz/act1/entity_data.emp` — a COMMITTED artifact. The redirect
did not reach it, so `./test.sh` (which runs that test) mutated committed ROM data.

It hid for months because the generator is deterministic: with unchanged inputs it rewrote
byte-identical content, so `git status` stayed clean and only the mtime moved. Proven by
mtime on 2026-08-18 — the file was written seconds ago by the test while every properly
redirected sibling still carried its original date. The moment editor data or a donor
changes, a TEST RUN silently rewrites committed data instead.

`import_sk_collision.py` documents this precise incident class: a test silently reverted a
committed bake and turned ~10 sigil port targets red. That was the sibling generator; this
was the same bug still live in this one.

WHAT THIS ASSERTS. Not "the output is correct" — that a generator handed an explicit output
path writes THERE and nowhere near the committed tree. mtime is the instrument on purpose: a
content comparison passes for a deterministic rewrite, which is exactly how this stayed
invisible. Cheap (entity gen only, not the full pipeline) so it can live on build.sh's lane.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
GENERATED = os.path.join(REPO, "games", "sonic4", "data", "generated")


def _mtimes(root: str) -> dict:
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                out[p] = os.stat(p).st_mtime_ns
            except OSError:
                pass
    return out


class TestGeneratorRespectsRedirect(unittest.TestCase):
    def test_entity_gen_accepts_an_output_path(self):
        """The escape hatch D8 exploited: no way to redirect it."""
        import inspect

        import ojz_entity_gen

        sig = inspect.signature(ojz_entity_gen.generate)
        self.assertIn(
            "out_path",
            sig.parameters,
            "ojz_entity_gen.generate() lost its out_path parameter. Without it the "
            "function writes its module-constant OUTPUT_PATH — a COMMITTED artifact — "
            "no matter what the caller redirected, which is how ./test.sh came to "
            "mutate committed ROM data (tools lens sweep D8).",
        )

    def test_entity_gen_with_out_path_leaves_the_committed_tree_alone(self):
        """The property itself, measured by mtime rather than content.

        A deterministic generator rewriting identical bytes leaves git clean, so a
        content check would have passed throughout the months this was broken.
        """
        if not os.path.isdir(GENERATED):
            self.skipTest("generated tree absent")

        import ojz_entity_gen

        before = _mtimes(GENERATED)
        self.assertGreater(len(before), 0, "generated tree unexpectedly empty")

        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "entity_data.emp")
            try:
                ojz_entity_gen.generate(out_path=dest)
            except SystemExit as e:
                self.skipTest(f"entity gen needs inputs unavailable here: {e}")
            self.assertTrue(
                os.path.isfile(dest),
                f"generate(out_path=...) wrote nothing to {dest} — if it wrote "
                f"somewhere else, that is the defect this gate exists for.",
            )

        after = _mtimes(GENERATED)
        touched = sorted(
            os.path.relpath(p, REPO)
            for p in after
            if p not in before or after[p] != before.get(p)
        )
        self.assertEqual(
            touched,
            [],
            "a generator handed an explicit out_path still wrote into the COMMITTED "
            f"tree: {touched}. Redirected output must not reach "
            "games/sonic4/data/generated/ — a test that writes committed data will "
            "eventually revert a real bake, which has happened here before.",
        )


if __name__ == "__main__":
    unittest.main()
