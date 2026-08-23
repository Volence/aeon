#!/usr/bin/env python3
"""Tests for `tools/effects_seam_gate.py` — the seam-reachability gate.

THE GATE'S OWN FAILURE MODE IS WHAT THESE TEST. A reachability check is easy to
write vacuously: "the module is NOT in the [module.unreachable] list" passes when
the module name is misspelled, when the warning format moves, and when the build
never ran. This gate is a PRESENCE test on a link symbol instead, which inverts
that — a wrong name fails — and the tests below pin the inversion rather than the
happy path.

The listing parse is exercised against real `EQU` rows in the format sigil emits
(`EQU NAME = $0000001F`), so a format move is caught here rather than by the gate
silently reporting "symbol absent" on a listing it could not read.
"""

import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
GATE = os.path.join(TOOLS, "effects_seam_gate.py")

sys.path.insert(0, TOOLS)
import effects_seam_gate  # noqa: E402
import effects_gen  # noqa: E402


class TestEquParse(unittest.TestCase):
    """The listing parse, against the real emitted format."""

    SAMPLE = (
        "some preamble\n"
        "EQU SceneBudget_CapsFolded = $0000001F\n"
        "EQU EditorScenes_OJZ_Act1_Count = $00000000\n"
        "EQU EditorScenes_OJZ_Act1_Bindings = $00000003\n"
        "0001A000  4E75             rts\n"
    )

    def test_it_reads_name_and_hex_value(self):
        got = {n: int(v, 16)
               for n, v in effects_seam_gate.EQU_RE.findall(self.SAMPLE)}
        self.assertEqual(got["EditorScenes_OJZ_Act1_Count"], 0)
        self.assertEqual(got["EditorScenes_OJZ_Act1_Bindings"], 3)
        self.assertEqual(got["SceneBudget_CapsFolded"], 0x1F)

    def test_it_does_not_match_disassembly_lines(self):
        self.assertNotIn("rts", dict(effects_seam_gate.EQU_RE.findall(self.SAMPLE)))


class TestGateAgainstTheRealTree(unittest.TestCase):
    """End-to-end, against the committed tree's own generated module."""

    def run_gate(self, lst):
        return subprocess.run([sys.executable, GATE, "--lst", lst],
                              capture_output=True, text=True, cwd=REPO)

    def test_a_listing_with_no_witnesses_FAILS_and_says_why(self):
        """The gate's whole subject: an unreached module defines no equates, so an
        absent witness means the descriptor's `use` edge is gone — and with it the
        elaboration of every guard in the generated module."""
        with tempfile.NamedTemporaryFile("w", suffix=".lst", delete=False) as f:
            f.write("EQU SomethingElse = $00000001\n")
            path = f.name
        try:
            p = self.run_gate(path)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("is ABSENT", p.stdout)
            self.assertIn("use` closure", p.stdout)
        finally:
            os.unlink(path)

    def test_an_UNPARSEABLE_listing_is_loud_about_being_unmeasurable(self):
        """Never render 'could not measure' as 'symbol absent'. A listing with zero
        EQU rows means the format moved; reporting a broken seam there would send
        the reader after the wrong defect entirely."""
        with tempfile.NamedTemporaryFile("w", suffix=".lst", delete=False) as f:
            f.write("no equates here at all\n")
            path = f.name
        try:
            p = self.run_gate(path)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("parsed ZERO", p.stdout)
            self.assertIn("do NOT read this as a broken seam", p.stdout)
        finally:
            os.unlink(path)

    def test_a_missing_listing_does_not_fall_back_to_reasoning(self):
        p = self.run_gate(os.path.join(tempfile.gettempdir(), "no_such_file.lst"))
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("not found", p.stdout)

    def test_a_WRONG_witness_value_fails_even_though_the_symbol_is_present(self):
        """Presence proves reachability; it does not prove the artifact carries what
        the editor inputs declare. The expected value is re-derived from
        project.json + the sidecars, never read out of the generated `.emp`, so this
        arm and the drift gate fail for genuinely different reasons."""
        names = effects_gen.act_names(REPO)
        with tempfile.NamedTemporaryFile("w", suffix=".lst", delete=False) as f:
            f.write(f"EQU {names.equ_scenes} = $00000063\n")
            f.write(f"EQU {names.equ_bindings} = $00000063\n")
            path = f.name
        try:
            p = self.run_gate(path)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("but the editor inputs say", p.stdout)
            self.assertIn("99", p.stdout)     # $63, so the gate really read it
        finally:
            os.unlink(path)

    def test_the_committed_seam_and_the_committed_generated_module_agree(self):
        """The source half of the gate, run against the real tree: the descriptor's
        import is a NAME LIST naming BOTH bindings, and every section index 0..N-1
        reaches the binding exactly once. No build needed."""
        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.DESCRIPTOR)) as f:
            desc = f.read()
        self.assertIn(f"use {names.module}.{{", desc)
        self.assertNotIn(f"use {names.module}.*", desc)
        self.assertIn(names.fn_act_default, desc)
        self.assertIn(names.fn_sec_scene, desc)
        import re
        passed = sorted(int(n) for n in re.findall(r"ojz_sec\(sec:\s*(\d+)", desc))
        self.assertEqual(passed, list(range(effects_gen.act_section_count(REPO))))


if __name__ == "__main__":
    unittest.main()
