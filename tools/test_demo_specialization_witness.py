"""Scanline P2 Task 8 — unit cover for the demo witness's own machinery.

THE WITNESS ITSELF RUNS POST-BUILD (tools/effects_gates.py invokes it), because it
reads two listings and build.sh's pytest lane runs BEFORE sigil. What lives HERE is
the half that can be checked without a build: the listing readers the witness's
verdicts rest on, exercised against synthetic listings whose right answers are known
by construction.

That split matters. `lst_proc_sizes` is the instrument behind the image backstop, and
a reader that silently mis-parsed (mangled locals counted as heads, RAM addresses
mixed into the ROM run, the last head sized off the end of the file) would make the
backstop report a comfortable number for a broken build. Those three are exactly what
the cases below poke at.
"""

import os
import tempfile
import unittest

import demo_specialization_witness as W
from scene_spans import (capability_bits, expected_spans, game_caps,
                         lst_proc_sizes, lst_spans, span_capability)

# A miniature listing in the real format: `(0) N/HEX :        Label:`. Two top-level
# heads 0x20 apart, a mangled local between them (must NOT be a head), a bracketing
# span, and a RAM-address row (must not join the ROM run — it would size the last ROM
# head as a negative or absurd number).
SAMPLE = """(0) 1/100 :        Alpha:
(0) 2/108 :        $engine.m$Alpha$inner:
(0) 3/10C :        $engine.m$Alpha$cap_anchors_overlay_begin:
(0) 4/118 :        $engine.m$Alpha$cap_anchors_overlay_end:
(0) 5/120 :        Beta:
(0) 6/130 :        Gamma:
(0) 7/FFFFB000 :        Some_RAM_Var:
"""


def write(text):
    fd, path = tempfile.mkstemp(suffix=".lst")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    return path


class TestListingReaders(unittest.TestCase):

    def setUp(self):
        self.path = write(SAMPLE)

    def tearDown(self):
        os.unlink(self.path)

    def test_only_unmangled_labels_are_section_heads(self):
        sizes = lst_proc_sizes(self.path)
        self.assertEqual(sorted(sizes), ["Alpha", "Beta", "Gamma"])
        self.assertNotIn("$engine.m$Alpha$inner", sizes)

    def test_head_size_is_the_distance_to_the_next_head(self):
        sizes = lst_proc_sizes(self.path)
        self.assertEqual(sizes["Alpha"], 0x20)   # 0x100 -> 0x120, mangled rows ignored
        self.assertEqual(sizes["Beta"], 0x10)

    def test_ram_addresses_do_not_join_the_rom_run(self):
        """A RAM head at 0xFFFFB000 sorted into the ROM run would size Gamma as
        0xFFFFAED0 — a number that looks like a huge proc rather than a parse bug."""
        sizes = lst_proc_sizes(self.path)
        self.assertNotIn("Some_RAM_Var", sizes)
        self.assertEqual(sizes["Gamma"], 0)      # last ROM head: no successor

    def test_spans_are_read_from_the_mangled_form(self):
        self.assertEqual(lst_spans(self.path), {"anchors_overlay"})

    def test_a_listing_with_no_spans_reads_as_empty_not_as_an_error(self):
        p = write("(0) 1/100 :        Alpha:\n")
        try:
            self.assertEqual(lst_spans(p), set())
        finally:
            os.unlink(p)


class TestDerivations(unittest.TestCase):

    def test_demo_declares_the_zero_mask_the_witness_rests_on(self):
        self.assertEqual(game_caps("demo"), 0)

    def test_sonic4_declares_a_nonzero_mask(self):
        """Both fixtures matter: with sonic4 at zero the differential would compare
        two identical builds and pass on nothing."""
        self.assertNotEqual(game_caps("sonic4"), 0)

    def test_expected_spans_respects_enclosing_gates(self):
        """A span survives only if EVERY gate around it is raised.
        cap_multi_deform_table_band sits inside the CAP_DEFORM sampling gate, so a mask
        with CAP_MULTI_DEFORM_TABLE but not CAP_DEFORM must not expect it — getting this
        wrong makes the differential a hand list with extra steps. (Until 2026-08-26 the
        worked example was cap_deform_sample inside the CAP_PER_LINE body gate; that
        outer gate is gone with the per-cell path, and so is the bit.)"""
        bits = capability_bits()
        mdt_only = bits["CAP_MULTI_DEFORM_TABLE"]
        both = bits["CAP_MULTI_DEFORM_TABLE"] | bits["CAP_DEFORM"]
        self.assertNotIn("multi_deform_table_band", expected_spans(mdt_only))
        self.assertIn("multi_deform_table_band", expected_spans(both))

    def test_the_zero_mask_expects_no_span_at_all(self):
        self.assertEqual(expected_spans(0), set())

    def test_the_full_mask_expects_every_authored_span(self):
        full = 0
        for v in capability_bits().values():
            full |= v
        self.assertTrue(expected_spans(full))

    def test_span_capability_resolves_the_longest_prefix(self):
        bits = capability_bits()
        self.assertEqual(span_capability("per_col_vsram_emit", bits), "CAP_PER_COL_VSRAM")
        self.assertEqual(span_capability("deform_sample", bits), "CAP_DEFORM")
        self.assertIsNone(span_capability("per_line_body", bits),
                          "CAP_PER_LINE is retired; a span must not resolve to it")
        self.assertIsNone(span_capability("not_a_capability", bits))


class TestThePin(unittest.TestCase):
    """The committed reference the derived scans cannot edit. Its VALUE is checked by
    the witness against a real build; what is checkable here is that it is a real
    reference and not an empty one."""

    def test_the_pin_is_not_empty(self):
        self.assertTrue(W.DEMO_SPECIALISED_PROCS,
                        "the image backstop's pin is empty — it would pass on any build")

    def test_every_pinned_proc_is_a_proc_that_actually_hosts_a_gated_span(self):
        """Not a derivation OF the pin (that would re-create the shared blind spot the
        poison exposed) — a check that the two agree TODAY, so a stale row is loud."""
        from scene_spans import gated_procs
        hosts = gated_procs()
        for proc in W.DEMO_SPECIALISED_PROCS:
            self.assertIn(
                proc, hosts,
                "%s is pinned as specialised but hosts no capability-gated span. If it "
                "genuinely stopped specialising, remove the row and say why." % proc)


if __name__ == "__main__":
    unittest.main()
