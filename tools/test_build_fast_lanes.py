#!/usr/bin/env python3
"""Gates for what `FAST=1 ./build.sh` does and does not do (aurora walkthrough b3, b4).

WHY THESE ARE TESTS AND NOT A COMMENT IN build.sh. Both defects below were invisible
from reading the script: one is a redirect that looks like ordinary noise suppression,
the other is an absence — a gate that simply is not invoked on this path. Neither shows
up in any output, and the cost of both landed on the author, not on the build.

  b3  The FAST re-bake ran as `tools/regenerate-level.sh > /dev/null`, and on failure
      printed a FIXED message guessing at the cause ("it needs the out-of-repo
      donors"). The generators print their refusals on STDOUT, so the redirect ate the
      one actionable line in the run. A dangling `rasterRef` sent the author hunting
      for donor directories while `effects_gen: REFUSED — ... names no preset document
      ... Known ids: ...` had been written and discarded.

  b4  `FAST=1` sets NO_LINT=1, which skips the pytest lane, and the post-sigil seam
      gate is guarded by `FAST == 0`. So binding a raster preset to a section no preset
      threads the chooser for — an ordinary click in Aurora — was GREEN in the loop the
      author is told to use and RED in the canonical build, discovered at landing after
      the work was done.

HOW b3 IS TESTED. Not by grepping for the absence of `/dev/null` — that is an absence
test, and an absence test passes when the block is renamed, moved or deleted. The block
between the `FAST_REBAKE_BLOCK` markers in build.sh is LIFTED AND EXECUTED here against
a stub `regenerate-level.sh` that prints a known refusal and fails. If the diagnosis
does not reach the caller's output, this file goes red. The markers are load-bearing and
build.sh says so at the marker.
"""

import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
BUILD_SH = os.path.join(REPO, "build.sh")

BEGIN = "# >>> FAST_REBAKE_BLOCK"
END = "# <<< FAST_REBAKE_BLOCK"


def build_sh() -> str:
    with open(BUILD_SH, "r", encoding="utf-8") as f:
        return f.read()


def fast_rebake_block(src: str) -> str:
    """The bytes build.sh runs when a FAST build finds the level tree stale."""
    i = src.index(BEGIN) + len(BEGIN)
    j = src.index(END, i)
    return textwrap.dedent(src[i:j])


class TestTheRebakeDiagnosisReachesTheAuthor(unittest.TestCase):
    """b3, executed rather than asserted about."""

    REFUSAL = ("effects_gen: REFUSED — section_0.meta.json: rasterRef 'cold_test_band' "
               "names no preset document in .../effects/presets — Known ids: "
               "authored_probe, ojz_sec3_shimmer, ojz_sec5_showcase.")

    def run_block(self, stub_body: str, stub_rc: int):
        """Execute build.sh's own FAST re-bake block against a stub re-bake."""
        block = fast_rebake_block(build_sh())
        with tempfile.TemporaryDirectory() as d:
            tools = os.path.join(d, "tools")
            os.makedirs(tools)
            stub = os.path.join(tools, "regenerate-level.sh")
            with open(stub, "w") as f:
                f.write("#!/bin/bash\n" + stub_body + f"\nexit {stub_rc}\n")
            os.chmod(stub, 0o755)
            script = f'set -euo pipefail\nTOOLS="{tools}"\n' + block + "\n"
            return subprocess.run(["bash", "-c", script],
                                  capture_output=True, text=True, cwd=d)

    def test_a_failed_rebake_prints_the_generators_OWN_message(self):
        p = self.run_block(f'echo "{self.REFUSAL}"', 1)
        out = p.stdout + p.stderr
        self.assertNotEqual(p.returncode, 0, out)
        self.assertIn("names no preset document", out,
                      "the re-bake's own refusal did not reach the caller — the FAST "
                      "wrapper is swallowing the only actionable message in the run "
                      "(walkthrough b3). Do NOT redirect it to /dev/null.")
        self.assertIn("cold_test_band", out,
                      "the message reached the caller with the offending id stripped")

    def test_stderr_is_captured_too(self):
        """A generator that refuses on stderr must not be silenced by capturing only
        stdout — the redirect this replaced took stdout alone, and the next generator
        to use stderr would have re-opened the same hole from the other side."""
        p = self.run_block('echo "STDERR-ONLY-REFUSAL" >&2', 1)
        self.assertIn("STDERR-ONLY-REFUSAL", p.stdout + p.stderr)

    def test_the_donor_guess_is_a_FOOTNOTE_not_the_headline(self):
        """The old message asserted the cause. It may only be offered as a fallback,
        and it must come after the generator's own words, or the reader stops there."""
        p = self.run_block(f'echo "{self.REFUSAL}"', 1)
        out = p.stdout
        self.assertIn("donors", out, "the donor hint was dropped entirely")
        self.assertLess(out.index("names no preset document"), out.index("donors"),
                        "the donor guess is printed before the real diagnosis")

    def test_a_SUCCESSFUL_rebake_stays_quiet(self):
        """The other half of the contract: FAST is the loop, and dumping a full re-bake
        log on every save would be its own defect. Capture, then print only on failure."""
        p = self.run_block('echo "Generating OJZ section data..."; '
                           'echo "Re-bake complete."', 0)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("Generating OJZ section data", p.stdout)
        self.assertIn("re-bake done in", p.stdout)

    def test_the_real_exit_code_is_reported_not_the_inversions(self):
        """`$?` inside `if ! cmd; then` is the inversion's status, i.e. always 0. A
        wrapper that prints `rc=0` beside a failure teaches the reader to distrust it."""
        p = self.run_block(f'echo "{self.REFUSAL}"', 3)
        self.assertIn("rc=3", p.stdout, p.stdout)

    def test_the_markers_this_file_depends_on_are_present_exactly_once(self):
        src = build_sh()
        self.assertEqual(src.count(BEGIN), 1)
        self.assertEqual(src.count(END), 1)
        self.assertLess(src.index(BEGIN), src.index(END))
        self.assertIn("regenerate-level.sh", fast_rebake_block(src))


class TestFastRunsTheSeamSourceCheck(unittest.TestCase):
    """b4: the iteration loop must not be green on a tree the canonical build refuses."""

    def test_the_FAST_path_invokes_the_seam_gate_source_arm(self):
        src = build_sh()
        m = re.search(
            r'if \[\[ "\$FAST" == "1" && "\$\{GAME\}" == "sonic4" \]\]; then'
            r'(.*?)\nfi\n', src, re.S)
        self.assertIsNotNone(
            m,
            "no FAST-and-sonic4 block in build.sh invokes anything — `FAST=1` skips "
            "every check of the editor-scene binding seam, so the loop goes green on a "
            "tree ./build.sh refuses (walkthrough b4).")
        body = m.group(1)
        self.assertIn("effects_seam_gate.py", body)
        self.assertIn("--source-only", body)
        self.assertIn("exit 1", body,
                      "the FAST seam pre-check runs but its failure is not fatal — a "
                      "gate whose exit code is discarded is not a gate.")

    def test_it_runs_BEFORE_the_sigil_build(self):
        """Fail-fast is the entire value: after the build it would cost the author the
        build anyway, and the canonical path already covers that position."""
        src = build_sh()
        self.assertLess(src.index("--source-only"),
                        src.index('echo "Building ${MAIN_ASM} (sigil)..."'))

    def test_the_FAST_banners_do_not_claim_the_whole_gate_ran(self):
        """A partial check reported as the whole one is how the next reader concludes
        the loop is safe to land from. Both banners must name what was NOT measured.

        SCOPED TO THE BANNER BODIES, not to the whole file: build.sh already contained
        the word REACHABILITY (in the comment above the canonical seam-gate call), so a
        file-wide `assertIn` passed against the very revision this test exists to fail.
        A search whose haystack is bigger than its subject is not a test.
        """
        src = build_sh()
        for start, end in (("FAST BUILD — VERIFICATION LANES SKIPPED", "NO_LINT=1"),
                           ("FAST BUILD COMPLETE", "run ./build.sh before you land it")):
            i = src.index(start)
            banner = src[i:src.index(end, i)]
            self.assertIn("REACHABILITY", banner,
                          f"the {start!r} banner does not say the seam gate's "
                          f"reachability half was skipped:\n{banner}")
            self.assertIn("source-only", banner,
                          f"the {start!r} banner does not say which half DID run")

    def test_the_source_arm_is_cheap_enough_to_belong_in_the_loop(self):
        """FAST exists to be ~1.3 s and its whole value is that speed. This is the
        assertion that keeps 'just add one more check' honest: measured, here, now.
        The ceiling is deliberately loose (a loaded build box is the normal case) —
        it is a REGRESSION bar, not a benchmark."""
        import time
        t0 = time.time()
        p = subprocess.run([sys.executable,
                            os.path.join(TOOLS, "effects_seam_gate.py"),
                            "--source-only"],
                           capture_output=True, text=True, cwd=REPO)
        elapsed = time.time() - t0
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertLess(elapsed, 2.0,
                        f"the FAST seam pre-check took {elapsed:.2f}s — that is a "
                        f"visible fraction of the FAST loop's whole budget.")


if __name__ == "__main__":
    unittest.main()
