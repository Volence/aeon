#!/usr/bin/env python3
"""Unit tests for tools/dma_defer_headroom.py's SOURCE READERS and arithmetic.

Split the same way test_dplc_straddle.py is (build.sh:62-74): nothing here opens
a `.lst` or a `.bin`, because build.sh's pytest lane runs BEFORE sigil and a
listing-reading test there would measure a PREVIOUS build. The listing-reading
half is the post-sigil `--gate` in build.sh.

What IS in scope here is every input the tool reads out of SOURCE -- constants,
the static DMA entry lengths, and the premise pin -- because source files are
the same before and after the build. Each expectation is derived longhand from
the file it names rather than copied from a run of the tool.
"""

import json
import struct
import tempfile
import unittest
from pathlib import Path

import dma_defer_headroom as H


class TestConstantResolution(unittest.TestCase):
    """`_const` must resolve the DERIVED chain, not just integer literals.

    ART_STAGING_BUFFER_SIZE is `ART_POOL_PAGE_BYTES`, which is
    `ART_POOL_PAGE_TILES * TILE_SIZE`. Retyping 2048 here would create the
    second copy of a number that this tool exists to stop existing, so the test
    re-derives it from its own two factors instead.
    """

    def test_literal_constant(self):
        self.assertEqual(H._const("MAX_VDP_SPRITES"), 80)

    def test_derived_constant_resolves_through_its_chain(self):
        tiles = H._const("ART_POOL_PAGE_TILES")
        tile_size = H._const("TILE_SIZE")
        self.assertEqual(H._const("ART_STAGING_BUFFER_SIZE"), tiles * tile_size)

    def test_page_bytes_shift_agrees_with_page_bytes(self):
        # The same pairing constants.emp's own `ensure` makes; if the reader
        # resolved either side wrongly this would not hold.
        self.assertEqual(
            1 << H._const("ART_POOL_PAGE_BYTES_SHIFT"),
            H._const("ART_POOL_PAGE_BYTES"))

    def test_unknown_constant_is_unmeasurable_not_a_number(self):
        with self.assertRaises(H.Unmeasurable):
            H._const("NO_SUCH_CONSTANT_EXISTS_HERE")


class TestStaticCriticalLengths(unittest.TestCase):
    """The Critical charge must come out of buffers.emp, and agree with itself."""

    def test_four_equal_palette_lines_one_sat_one_hscroll(self):
        c = H.static_critical_lengths()
        self.assertEqual(c["palette_lines"], 4)
        # CRAM is 4 lines x 16 entries x 2 bytes.
        self.assertEqual(c["palette_line"], 16 * 2)
        # The SAT entry's boot length is the worst case: MAX_VDP_SPRITES x 8.
        self.assertEqual(c["sat"], H._const("MAX_VDP_SPRITES") * 8)
        # The HScroll table is 224 display lines x 4 bytes; buffers.emp says so
        # in prose at the enqueue site and in the entry length at the init site.
        self.assertEqual(c["hscroll"], 224 * 4)

    def test_a_changed_sat_length_is_unmeasurable(self):
        """The SAT length and MAX_VDP_SPRITES are cross-checked, so breaking the
        pair must raise rather than quietly report the stale one."""
        p = Path(H.BUFFERS_EMP)
        text = p.read_text()
        anchor = "move.w  #dma_length(640), d3"
        self.assertEqual(text.count(anchor), 1)
        p.write_text(text.replace(anchor, "move.w  #dma_length(648), d3", 1))
        try:
            with self.assertRaises(H.Unmeasurable):
                H.static_critical_lengths()
        finally:
            p.write_text(text)


class TestPremisePin(unittest.TestCase):
    """The report is only about this engine while the ship asymmetry holds."""

    def test_asymmetry_holds_on_this_tree(self):
        self.assertTrue(H.assert_ship_asymmetry())


class TestDeficitArithmetic(unittest.TestCase):
    """residual = budget - plane - critical; deficit = demand - residual.

    Derived from engine/system/vblank.emp's order: the budget is seeded at :136,
    the plane drain is charged at :169, the whole Critical queue at :190, and
    only then does Process_DMA_Important see what is left (:264).
    """

    def test_ntsc_residual_is_budget_minus_both_charges(self):
        c = H.static_critical_lengths()
        critical = c["palette_line"] * c["palette_lines"] + c["sat"] + c["hscroll"]
        want = H._const("DMA_BUDGET_NTSC") - H._const("PLANE_BUFFER_SIZE") - critical
        self.assertEqual(want, 6144 - 1536 - (128 + 640 + 896))

    def test_pal_has_strictly_more_residual_than_ntsc(self):
        """PAL's larger blanking window is why this mechanism is a region
        question, and why 'does he see it on PAL' is a discriminator."""
        self.assertGreater(H._const("DMA_BUDGET_PAL"), H._const("DMA_BUDGET_NTSC"))


# ------------------------------------------------------------------- route 2
#
# LS-15b-resid (2026-09-08). The tool's pin is written by the harness itself, so
# it caught DRIFT and could never say the pinned numbers were RIGHT. The fix is a
# SECOND statement of every pinned quantity read out of the ASSEMBLED build, with
# disagreement raised as `Unmeasurable` naming both sides.
#
# The readers below take a `.lst` and a `.bin`, and this lane runs BEFORE sigil
# (see the module docstring), so every fixture here is SYNTHETIC and hand-built --
# never this repo's artifacts, which at this point in build.sh belong to a
# PREVIOUS build. The route-2 readers are exercised against the real ones by the
# post-sigil `--gate` and by `--selftest`.


class TestCrossCheck(unittest.TestCase):
    """`_cross_check` must REFUSE, and must name BOTH numbers when it does.

    The whole parcel turns on not silently preferring one reader, so "it raised"
    is not the assertion -- "it raised saying 1472 AND 1536" is.
    """

    def test_agreement_is_silent(self):
        self.assertIsNone(H._cross_check("x", 1536, 1536, "how"))

    def test_disagreement_names_both_sides(self):
        with self.assertRaises(H.Unmeasurable) as cm:
            H._cross_check("PLANE_BUFFER_SIZE", 1472, 1536, "the EQU row")
        msg = str(cm.exception)
        self.assertIn("1472", msg)
        self.assertIn("1536", msg)
        self.assertIn("PLANE_BUFFER_SIZE", msg)
        self.assertIn("the EQU row", msg)

    def test_disagreement_warns_against_re_cutting(self):
        """The one action that would DESTROY the evidence is a re-cut, because
        the pin is written by the harness. The message has to say so."""
        with self.assertRaises(H.Unmeasurable) as cm:
            H._cross_check("x", 1, 2, "how")
        self.assertIn("launder", str(cm.exception))


class TestEquTable(unittest.TestCase):
    """The listing's Equate Table is route 2 for every constant."""

    def _lst(self, body):
        d = tempfile.mkdtemp()
        p = Path(d) / "fixture.lst"
        p.write_text(body)
        return p

    def test_reads_hex_values(self):
        p = self._lst("(0) 1/0 :        Vectors:\n"
                      "EQU DMA_BUDGET_NTSC = $00001800\n"
                      "EQU TILE_SIZE = $00000020\n")
        self.assertEqual(H.equ_table(p),
                         {"DMA_BUDGET_NTSC": 0x1800, "TILE_SIZE": 0x20})

    def test_a_listing_with_no_equates_is_unmeasurable(self):
        """sigil OMITS the Equate Table entirely when a link has no equates, so
        an empty read is indistinguishable from a format change. Either way
        route 2 is gone, and falling back to route 1 alone is exactly the
        self-confirming reading this parcel removed."""
        p = self._lst("(0) 1/0 :        Vectors:\n(0) 2/100 :        GameHeader:\n")
        with self.assertRaises(H.Unmeasurable):
            H.equ_table(p)

    def test_missing_file_is_unmeasurable(self):
        with self.assertRaises(H.Unmeasurable):
            H.equ_table(Path(tempfile.mkdtemp()) / "absent.lst")


class TestRomStaticCriticalLengths(unittest.TestCase):
    """Route 2 for the Critical entry lengths: the immediates sigil ENCODED.

    Expectations are derived from the 68000 encoding, not from this repo's ROM:
    MOVE.W with an immediate source (mode 7 reg 4) into D3 (mode 0 reg 3) is
    0011 011 000 111 100 = $363C, and `dma_length` (engine/vdp.emp) is
    `(bytes >> 1) & $FFFF`, so a fixture built to mean N bytes stores N // 2.
    """

    def _tree(self, byte_lengths, pad_between=b"\x4e\x71"):
        """A synthetic listing + ROM holding one proc of `move.w #imm, d3`."""
        d = Path(tempfile.mkdtemp())
        base = 0x100
        body = b""
        for n in byte_lengths:
            body += pad_between + b"\x36\x3c" + struct.pack(">H", n // 2)
        end = base + len(body) + 2
        (d / "f.lst").write_text(
            f"(0) 1/{base:X} :        {H._STATIC_DMA_PROC}:\n"
            f"(0) 2/{end:X} :        Next_Proc:\n")
        (d / "f.bin").write_bytes(b"\x00" * base + body + b"\x4e\x75" + b"\x00" * 16)
        return d / "f.lst", d / "f.bin"

    def test_decodes_six_lengths_and_doubles_words_to_bytes(self):
        lst, rom = self._tree([32, 32, 32, 32, 640, 896])
        self.assertEqual(
            H.rom_static_critical_lengths(lst, rom),
            {"palette_line": 32, "palette_lines": 4, "sat": 640, "hscroll": 896})

    def test_a_different_count_is_unmeasurable_not_a_guess(self):
        """Five encodings means the routine changed shape or the scan
        misaligned. Reporting the five it found would be a number with no
        provenance."""
        lst, rom = self._tree([32, 32, 32, 32, 640])
        with self.assertRaises(H.Unmeasurable) as cm:
            H.rom_static_critical_lengths(lst, rom)
        self.assertIn("decoded 5", str(cm.exception))

    def test_unequal_palette_entries_are_unmeasurable(self):
        lst, rom = self._tree([32, 32, 32, 48, 640, 896])
        with self.assertRaises(H.Unmeasurable) as cm:
            H.rom_static_critical_lengths(lst, rom)
        self.assertIn("palette", str(cm.exception))

    def test_a_missing_proc_symbol_is_unmeasurable(self):
        d = Path(tempfile.mkdtemp())
        (d / "f.lst").write_text("(0) 1/100 :        Something_Else:\n")
        (d / "f.bin").write_bytes(b"\x00" * 512)
        with self.assertRaises(H.Unmeasurable) as cm:
            H.rom_static_critical_lengths(d / "f.lst", d / "f.bin")
        self.assertIn(H._STATIC_DMA_PROC, str(cm.exception))

    def test_the_named_proc_exists_in_the_engine(self):
        """The reader takes its extent from a routine by NAME, and the name it
        used until this parcel (`Init_Static_DMA_Entries`) was in NO source file
        in this tree -- it survived in a docstring and, worse, in an
        `Unmeasurable` MESSAGE, which is the text someone reads when the reader
        breaks. Pin the name against the file that has to define it."""
        text = H.BUFFERS_EMP.read_text()
        self.assertIn(f"pub proc {H._STATIC_DMA_PROC} ", text)


class TestPinnedShape(unittest.TestCase):
    """`pinned()` is the ONE definition of what the baseline covers; `gate` and
    `--write-baseline` both go through it. This checks the committed pin has not
    grown or lost a top-level section relative to it -- a drift the value
    comparison itself cannot report, because a section absent from both sides
    compares equal."""

    def test_committed_baseline_has_exactly_the_pinned_sections(self):
        want = set(H.pinned({k: {} for k in
                             ("constants", "critical_entry_bytes",
                              "dplc_peak_bytes", "regions")}))
        got = set(json.loads(H.BASELINE.read_text()))
        self.assertEqual(want, got)


if __name__ == "__main__":
    unittest.main()
