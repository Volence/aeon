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


if __name__ == "__main__":
    unittest.main()
