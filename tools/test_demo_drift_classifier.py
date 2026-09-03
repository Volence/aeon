"""Unit cover for demo_drift_classifier's `rom_spans` — the same head-to-next-head
extent inference `scene_spans.lst_proc_sizes` has, written independently in this
tool rather than shared with it. See tools/test_demo_specialization_witness.py for
the fuller writeup of the defect this guards against (a PHASED symbol's listing
value is a bank-local VMA, not its real ROM address, so it can land numerically
inside an unrelated routine's true span and truncate it).

Currently latent in practice — this tool is documented and used against
`games/demo`, which builds with sound off and links no `vma:`-phased section, so no
real invocation has hit this yet. `rom_spans` itself takes two plain symbol dicts,
so nothing stops it being pointed at two sonic4 listings, which DO carry phased
symbols (`SoundTablesZ80_Head`, `SfxBlobWinTab`, ...).
"""

import unittest

from demo_drift_classifier import rom_spans
from scene_spans import vma_phased_symbol_names


class TestRomSpansPhasedExclusion(unittest.TestCase):

    def test_a_phased_symbol_does_not_truncate_the_routine_it_lands_inside(self):
        # RealBefore's own bytes run to 0x8100 (RealAfter), but a phased symbol
        # (a REAL name — soundbankhead.emp's `vma: $8000` section) sits at 0x8000,
        # numerically inside that run. `rom_spans` must not let it stand as a
        # boundary.
        self.assertIn("SoundTablesZ80_Head", vma_phased_symbol_names(),
                      "the source derivation no longer finds the real phased "
                      "symbol this test's fixture models")
        old = {"RealBefore": 0x7F76, "SoundTablesZ80_Head": 0x8000, "RealAfter": 0x8100}
        new = dict(old)   # nothing moved between "old" and "new" for this check
        spans = rom_spans(old, new, appendix=0x20000)
        by_name = {name: (start, end) for start, end, name, _ in spans}
        self.assertIn("RealBefore", by_name)
        start, end = by_name["RealBefore"]
        self.assertEqual((start, end), (0x7F76, 0x8100),
                         "RealBefore's span must run to its real neighbour "
                         "RealAfter, not to the phased symbol inside its own "
                         "interior")
        self.assertNotIn("SoundTablesZ80_Head", by_name,
                         "a phased symbol should not surface as a span at all — "
                         "its own listing address is not its true ROM location")

    def test_an_ordinary_pair_is_unaffected(self):
        old = {"Alpha": 0x100, "Beta": 0x120, "Gamma": 0x130}
        new = {"Alpha": 0x100, "Beta": 0x120, "Gamma": 0x130}
        spans = rom_spans(old, new, appendix=0x1000)
        by_name = {name: (start, end) for start, end, name, _ in spans}
        self.assertEqual(by_name["Alpha"], (0x100, 0x120))
        self.assertEqual(by_name["Beta"], (0x120, 0x130))
        self.assertEqual(by_name["Gamma"], (0x130, 0x1000))


if __name__ == "__main__":
    unittest.main()
