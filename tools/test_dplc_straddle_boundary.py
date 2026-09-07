"""LS-15b — the DMA source-boundary period, and the proof that it is DERIVED.

WHY THIS FILE EXISTS. `dplc_straddle.py --selftest` printed "the gate is green
here and provably red elsewhere" and exited 0 through SEVEN arms while the period
every one of them measured through was wrong by a factor of two. The mutation was
one character in the harness:

    word_bits = 16   ->   word_bits = 15        # boundary 0x20000 -> 0x10000

MEASURED before the fix, against `s4.debug.lst` / `s4.debug.bin`: all seven arm
lines came out character-for-character identical and the verdict printed at exit
0, while the SAME mutation moved the tool's own report substantially — knuckles'
and tails' straddling REACHABLE frames from 0 to 1 each, and the concurrent
demand on the 2-slot `DPLC_ENTRY_RESERVE` from 0 to 2. The arms could not see it
because each of them re-derived the period from `boundary_from_source()` and then
compared results that all shared it. The proof was RELATIVE: it showed the arms
agreed with each other, not that any of them was right.

THE FIX AND WHAT MAKES IT ABSOLUTE. There is no local number left to mutate.
`boundary_from_text` reads the operand size out of the borrow test's own suffix
letter (`sub.w` -> 16) and the unit size out of the source conversion's own shift
count (`lsr.l #1` -> 2 bytes), so the period is a function of engine source text.
`boundary_declared` then reads what the engine's other files SAY the period is,
and the two must agree.

WHAT THAT STILL DOES NOT REACH, stated here rather than left to be inferred: both
routes can be wrong TOGETHER. If the split code and every declaration beside it
moved to the same wrong period, nothing in this repository disagrees, because
there is no third statement of it — the authority is the VDP and no file here
quotes it. What is now impossible is the LS-15b shape specifically: a period that
disagrees with the engine while the tool stays consistent with itself.

NO FILE IS WRITTEN. Every perturbation below is a string, handed in through
`boundary_from_text(text)` / `boundary_from_source(src_text=...)`. That is
deliberate: the sibling harness (`dma_defer_headroom.py --selftest`) proves its
arms red by rewriting tracked engine files in place, which is exactly why it
cannot live in a lane.
"""

import pathlib
import re
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import dplc_straddle as D                                             # noqa: E402

LIVE = D._read("engine/system/dma_queue.emp")


def _sub_size(text, size):
    """Rewrite BOTH halves of the borrow test to `sub.<size>`."""
    return re.sub(r'^(\s*sub\.)[bwl](\s+d[13],\s*d0\b)', r'\g<1>' + size + r'\2',
                  text, flags=re.M)


def _lsr_shift(text, n):
    """Rewrite BOTH unit conversions to shift by `n`."""
    return re.sub(r'^(\s*lsr\.[lw]\s+#)\d+(,\s*d[13]\b)', r'\g<1>' + str(n) + r'\2',
                  text, flags=re.M)


class TestTheLiveSourceStillSpellsTheTestWeDecode(unittest.TestCase):
    """The perturbations below are worthless if their anchors are not in the live
    file, so each anchor is asserted present before anything is measured. A
    positive control on the perturbation itself, not on the subject."""

    def test_the_borrow_test_is_present_ONCE_as_a_contiguous_block(self):
        """Exactly one `moveq/sub/sub/blo` block, and the lookalike is NOT it.

        `sub.w d1, d0` occurs three times in this file; two of them are the
        borrow test and the third (the drain path's budget subtraction) is a
        lookalike a per-instruction search would read the operand size off. The
        block anchor is what keeps them apart, so both facts are asserted."""
        block = re.compile(
            r'^[ \t]*moveq[ \t]+#0,[ \t]*d0[ \t]*(?://.*)?\n'
            r'[ \t]*sub\.(\w)[ \t]+d3,[ \t]*d0\b[^\n]*\n'
            r'[ \t]*sub\.(\w)[ \t]+d1,[ \t]*d0\b[^\n]*\n'
            r'[ \t]*blo[ \t]+\.split\b', re.M)
        self.assertEqual(len(block.findall(LIVE)), 1)
        self.assertGreater(len(re.findall(r'^\s*sub\.[bwl]\s+d[13],\s*d0\b', LIVE, re.M)), 2,
                           "the lookalike this anchor exists to exclude is gone; "
                           "if it never comes back the block anchor is merely harmless")
        self.assertNotEqual(_sub_size(LIVE, "b"), LIVE)

    def test_both_unit_conversions_are_present_and_perturbable(self):
        self.assertEqual(len(re.findall(r'^\s*lsr\.[lw]\s+#\d+,\s*d[13]\b', LIVE, re.M)), 2)
        self.assertNotEqual(_lsr_shift(LIVE, 2), LIVE)


class TestTheOperandSizeIsREAD(unittest.TestCase):
    """`word_bits` used to be typed. Each case below asserts a period the 68000's
    own semantics imply for that suffix — never a number copied from a run."""

    def test_the_live_period_is_the_word_borrow_over_two_byte_units(self):
        got, prov = D.boundary_from_text(LIVE)
        self.assertEqual(got, (1 << 16) * 2)
        self.assertIn("sub.w", prov)
        self.assertIn("lsr.l #1", prov)

    def test_a_byte_borrow_gives_a_byte_sized_period(self):
        got, _ = D.boundary_from_text(_sub_size(LIVE, "b"))
        self.assertEqual(got, (1 << 8) * 2)

    def test_a_long_borrow_gives_a_long_sized_period(self):
        got, _ = D.boundary_from_text(_sub_size(LIVE, "l"))
        self.assertEqual(got, (1 << 32) * 2)

    def test_the_three_sizes_are_all_different(self):
        # The guard against a derivation that reads the letter and ignores it.
        seen = {D.boundary_from_text(_sub_size(LIVE, s))[0] for s in "bwl"}
        self.assertEqual(len(seen), 3)

    def test_two_different_borrow_widths_are_refused(self):
        mixed = re.sub(r'^(\s*sub\.)[bwl](\s+d1,\s*d0\b)', r'\g<1>l\2', LIVE, flags=re.M)
        with self.assertRaises(D.Unmeasurable) as cm:
            D.boundary_from_text(mixed)
        self.assertIn("one wrap point", str(cm.exception))


class TestTheUnitSizeIsREAD(unittest.TestCase):
    def test_doubling_both_shifts_doubles_the_period(self):
        base, _ = D.boundary_from_text(LIVE)
        got, _ = D.boundary_from_text(_lsr_shift(LIVE, 2))
        self.assertEqual(got, base * 2)

    def test_shifting_the_source_alone_is_refused_not_decoded(self):
        # Source in longs and length in words is not a period at all. Decoding it
        # from either half would be the LS-15b failure in a new place.
        one = re.sub(r'^(\s*lsr\.l\s+#)\d+(,\s*d1\b)', r'\g<1>2\2', LIVE, count=1, flags=re.M)
        with self.assertRaises(D.Unmeasurable) as cm:
            D.boundary_from_text(one)
        self.assertIn("DIFFERENT units", str(cm.exception))

    def test_an_absurd_shift_is_refused(self):
        with self.assertRaises(D.Unmeasurable):
            D.boundary_from_text(_lsr_shift(LIVE, 31))


class TestItIsLoudWhenTheSpellingGoes(unittest.TestCase):
    def test_no_source_conversion(self):
        with self.assertRaises(D.Unmeasurable):
            D.boundary_from_text(re.sub(r'^\s*lsr\.l\s+#\d+,\s*d1\b.*$', '', LIVE, flags=re.M))

    def test_no_length_conversion(self):
        with self.assertRaises(D.Unmeasurable):
            D.boundary_from_text(re.sub(r'^\s*lsr\.w\s+#\d+,\s*d3\b.*$', '', LIVE, flags=re.M))

    def test_no_borrow_test(self):
        with self.assertRaises(D.Unmeasurable):
            D.boundary_from_text(re.sub(r'^\s*sub\.[bwl]\s+d[13],\s*d0\b.*$', '',
                                        LIVE, flags=re.M))

    def test_no_split_branch(self):
        with self.assertRaises(D.Unmeasurable) as cm:
            D.boundary_from_text(re.sub(r'^\s*blo\s+\.split\b.*$', '', LIVE, flags=re.M))
        self.assertIn("blo", str(cm.exception))


class TestTheSecondRoute(unittest.TestCase):
    """The declarations. Not a derivation — what the engine's own files say the
    period is, read out of files that are neither the split code nor this tool."""

    def test_every_declaration_site_yields_one_and_they_agree(self):
        value, sites = D.boundary_declared()
        self.assertTrue(sites)
        for path in D.BOUNDARY_DECLARATION_SITES:
            self.assertTrue(any(s.startswith(path + ":") for s in sites),
                            f"{path} declares no boundary; the cross-check lost a route")
        self.assertEqual(value, D.boundary_from_text(LIVE)[0])

    def test_the_declared_sites_are_really_in_those_files(self):
        # Positive control on the regex, checked against the files directly.
        for path in D.BOUNDARY_DECLARATION_SITES:
            self.assertRegex(D._read(path), D._DECLARED_BOUNDARY)


class TestTheCrossCheckFires(unittest.TestCase):
    """THE LS-15b REGRESSION. A period that disagrees with what the engine
    declares must be refused, loudly, naming both sides."""

    def test_the_live_pair_agrees(self):
        self.assertEqual(D.boundary_from_source(), D.boundary_declared()[0])

    def test_a_perturbed_split_test_is_refused_against_the_declarations(self):
        with self.assertRaises(D.Unmeasurable) as cm:
            D.boundary_from_source(src_text=_sub_size(LIVE, "b"))
        msg = str(cm.exception)
        self.assertIn("DECODED from the split test", msg)
        self.assertIn(f"0x{(1 << 8) * 2:X}", msg)       # what the decode said
        self.assertIn(f"0x{D.boundary_declared()[0]:X}", msg)   # what the tree declares

    def test_a_doubled_period_is_refused_too(self):
        # Both directions: a refusal that only fires when the period SHRINKS
        # would have missed half of the failure it exists for.
        with self.assertRaises(D.Unmeasurable):
            D.boundary_from_source(src_text=_lsr_shift(LIVE, 2))


class TestNoLocalConstantSurvives(unittest.TestCase):
    """The behavioural statement of "there is no number left to mutate": the
    period is a FUNCTION of the text, so no single text-independent value can be
    returned for two different texts."""

    def test_the_period_is_not_constant_across_texts(self):
        vals = {D.boundary_from_text(_sub_size(LIVE, s))[0] for s in "bwl"}
        vals |= {D.boundary_from_text(_lsr_shift(LIVE, n))[0] for n in (1, 2, 3)}
        self.assertGreater(len(vals), 1)

    def test_the_only_written_down_numbers_are_the_isa_size_table(self):
        # `_SIZE_BITS` is the 68000's, not this tree's, and is the one table the
        # module is allowed to state. If it ever stopped matching the ISA every
        # case above would move with it, which is what makes that acceptable.
        self.assertEqual(D._SIZE_BITS, {"b": 8, "w": 16, "l": 32})


if __name__ == "__main__":
    unittest.main()
