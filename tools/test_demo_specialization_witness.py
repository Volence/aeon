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
import re
import tempfile
import unittest

import demo_specialization_witness as W
from scene_spans import (AEON, capability_bits, expected_spans, game_caps,
                         lst_proc_sizes, lst_spans, span_capability,
                         vma_phased_symbol_names)

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

# A listing shaped like the real 2026-09-03 collision: a routine (`RealBefore`) whose
# own interior runs well past a PHASED symbol's listing address (`SoundTablesZ80_Head`
# is real — see `games/sonic4/data/sound/soundbankhead.emp`'s `section soundbankhead
# (cpu: m68000, vma: $8000)` — its listing value is a bank-local VMA, not the ROM LMA
# `RealBefore`'s bytes actually occupy). Sized so that, WITHOUT the phased-symbol
# exclusion, `RealBefore` would be truncated to the gap up to the phased symbol
# (0x8A) instead of its real extent up to `RealAfter` (0x18A) — i.e. exactly the
# defect measured against the live build (Parallax_Step5_Vscroll truncated to 138 B,
# Raster_HInt to 21 B, both by this same symbol).
PHASED_COLLISION_SAMPLE = """(0) 1/7F76 :        RealBefore:
(0) 2/7FFE :        $engine.m$RealBefore$interior:
(0) 3/8000 :        SoundTablesZ80_Head:
(0) 4/8026 :        $engine.m$RealBefore$deep_interior:
(0) 5/8100 :        RealAfter:
"""

_LST_ROW_RE = re.compile(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s*:\s+([A-Za-z_]\w*):\s*$", re.M)


def _addr(sample_text, name):
    """The address a synthetic SAMPLE gives `name` — parsed, not retyped, so the
    fixture and its expectation cannot silently drift apart."""
    for hexaddr, label in _LST_ROW_RE.findall(sample_text):
        if label == name:
            return int(hexaddr, 16)
    raise AssertionError("%r not in this sample" % name)


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

    def test_a_phased_vma_symbol_does_not_truncate_the_routine_it_lands_inside(self):
        """The 2026-09-03 collision, reproduced from a synthetic listing shaped like
        the real one. `SoundTablesZ80_Head` is a REAL name (soundbankhead.emp's
        phased `vma: $8000` section) — this test calls the real
        `vma_phased_symbol_names()` over the actual source tree, not a mock, so it
        fails if that derivation stops finding it.

        Without the exclusion, `RealBefore` sizes to the gap up to the phased
        symbol (0x8000 - 0x7F76 = 0x8A) even though its own interior labels run
        well past it — exactly how `Parallax_Step5_Vscroll` measured 138 B and
        `Raster_HInt` measured 21 B against the live build before this fix.
        """
        self.assertIn("SoundTablesZ80_Head", vma_phased_symbol_names(),
                      "the source derivation no longer finds the real phased "
                      "symbol this test's fixture models — re-check "
                      "soundbankhead.emp's `vma:` section")
        p = write(PHASED_COLLISION_SAMPLE)
        try:
            sizes = lst_proc_sizes(p)
        finally:
            os.unlink(p)
        truncated = (_addr(PHASED_COLLISION_SAMPLE, "SoundTablesZ80_Head")
                     - _addr(PHASED_COLLISION_SAMPLE, "RealBefore"))
        real = (_addr(PHASED_COLLISION_SAMPLE, "RealAfter")
                - _addr(PHASED_COLLISION_SAMPLE, "RealBefore"))
        self.assertEqual(sizes["RealBefore"], real,
                         "RealBefore must size to its real neighbour RealAfter "
                         "(0x%X), not to the phased symbol sitting inside its "
                         "own interior (0x%X) — the collision is back" % (real, truncated))
        self.assertNotIn("SoundTablesZ80_Head", sizes,
                         "a phased symbol should not surface as a sized proc at "
                         "all: its own listing address is not its true ROM "
                         "location, so no size derived from it means anything")

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


class TestVmaPhasedSymbols(unittest.TestCase):
    """`vma_phased_symbol_names()` is a SOURCE derivation (the listing carries no
    marker of its own — see the function's docstring), so these check it against
    the real tree rather than a mock.
    """

    def test_finds_the_real_soundbankhead_phase_bank_names(self):
        names = vma_phased_symbol_names()
        # All six heads of games/sonic4/data/sound/soundbankhead.emp's
        # `section soundbankhead (cpu: m68000, vma: $8000)` — the section that
        # produced BOTH measured collisions (SoundTablesZ80_Head, SfxBlobWinTab).
        for name in ("SoundTablesZ80_Head", "SndDefaultPitchTable",
                     "MovingTrucks_PitchTable", "SfxBlobWinTab",
                     "SeqOpcodeTable", "DacSampleTable"):
            self.assertIn(name, names, "%s is declared in soundbankhead.emp's "
                          "phased section but the derivation missed it" % name)

    def test_cpu_z80_alone_is_neither_necessary_nor_sufficient(self):
        """The collision is a PHASED-SECTION class, not a `cpu: z80` class —
        `soundbankhead.emp`'s section is `cpu: m68000` (not sufficient: z80 isn't
        required), and the resident Z80 driver's `cpu: z80` sections (no `vma:`,
        compiled to a separate blob that never reaches the 68000 listing) must NOT
        be in this set (not necessary: z80 alone isn't enough) — including them
        would just be a differently-shaped name-based guess."""
        names = vma_phased_symbol_names()
        # Real proc names from engine/sound/z80_sound_driver.emp — a `cpu: z80`
        # module with NO `vma:` on its section.
        for name in ("SndDrv_Init", "Fm_YmWrite", "Psg_HwCh", "Sfx_Frame",
                     "Sequencer_Frame", "Z80_Sound_Entry"):
            self.assertNotIn(name, names,
                             "%s is a resident Z80-driver proc with no `vma:` on "
                             "its section — it never reaches the 68000 listing, "
                             "so it must not be treated as a phased symbol" % name)

    def test_an_ordinary_68000_routine_is_not_swept_in(self):
        names = vma_phased_symbol_names()
        self.assertNotIn("Raster_HInt", names)
        self.assertNotIn("Parallax_Step5_Vscroll", names)


@unittest.skipUnless(
    os.path.isfile(os.path.join(AEON, "s4.debug.lst")),
    "s4.debug.lst not built — this is the POST-BUILD half (build with "
    "`DEBUG=1 ./build.sh` to exercise it; the synthetic-listing tests above cover "
    "the same mechanism without a build)")
class TestAgainstARealListing(unittest.TestCase):
    """The synthetic fixture above proves the MECHANISM; this proves it against
    whatever the tree last built, with no byte count hardcoded (the PIN in
    demo_specialization_witness.py carries the committed numbers — this test
    only proves the collision signature is gone, which stays true as the ROM
    grows).
    """

    def test_raster_hint_no_longer_equals_the_gap_to_sfxblobwintab(self):
        path = os.path.join(AEON, "s4.debug.lst")
        sizes = lst_proc_sizes(path)
        addrs = {}
        with open(path, encoding="utf-8", errors="replace") as f:
            for hexaddr, label in _LST_ROW_RE.findall(f.read()):
                addrs.setdefault(label, int(hexaddr, 16))
        if "Raster_HInt" not in addrs or "SfxBlobWinTab" not in addrs:
            self.skipTest("this build does not link both Raster_HInt and "
                          "SfxBlobWinTab — nothing to prove here")
        collision_signature = addrs["SfxBlobWinTab"] - addrs["Raster_HInt"]
        self.assertNotEqual(
            sizes["Raster_HInt"], collision_signature,
            "Raster_HInt's measured size equals the raw address gap to "
            "SfxBlobWinTab again — the phased-symbol exclusion regressed")


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
