#!/usr/bin/env python3
"""S3 — five implementations of "where does this routine end", ONE rule.

Routed from sigil `79767f26` (2026-09-05): `instashield_gate`, `sprite_tilt_gate`,
`loop_crossover_gate` and `waterline_art_gate` each infer a routine's ROM extent as
"up to the next symbol above it", and none of the four filtered PHASED symbols.
`scene_spans.lst_proc_sizes` does, via `vma_phased_symbol_names()`.

THE FIFTH IS THE CONTROL, and it is what makes the other four legible: this is not
four sites to fix by taste, it is one already-correct implementation and three that
predate it. So this file tests the RULE across every consumer rather than testing four
functions, and it holds a registry that a sixth consumer has to be added to.

WHY PHASED SYMBOLS ARE NOT BOUNDARIES. A symbol declared inside a
`section ... (vma: $HEX)` block carries its BANK-LOCAL VMA in the listing, not its ROM
address, so it can land — purely by numeric coincidence — inside an unrelated
routine's real address run. Measured on a real build (2026-09-03):
`SoundTablesZ80_Head` at listing $8000 cut `Parallax_Step5_Vscroll` to 64 B and
`SfxBlobWinTab` at $845F cut `Raster_HInt` to 21 B. The listing carries NO MARKER for
this, so it is a source derivation and cannot be recovered from the listing alone.

NO LISTING IS OPENED HERE. build.sh's pytest lane runs BEFORE sigil, so a
listing-reading test there would measure a PREVIOUS build (test_dplc_straddle.py's
header rule). The symbol maps below are hand-built and the one real input is the
phased NAME SET, which is derived from source and so is current at any point in a
build.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import instashield_gate                                            # noqa: E402
import loop_crossover_gate                                         # noqa: E402
import scene_spans                                                 # noqa: E402
import sprite_tilt_gate                                            # noqa: E402
import waterline_art_gate                                          # noqa: E402

#: The routine under test in every synthetic map, and its true neighbours.
START, END = 0x010000, 0x0100C0

#: A REAL phased name, taken from the tree's own derivation rather than invented —
#: a made-up name would pass a filter that only knows the real ones and the plant
#: would assert nothing.
POISON = "SoundTablesZ80_Head"


def consumers():
    """(label, callable(syms) -> (start, end)) for every extent inference in tools/.

    Each adapter builds the local-label spelling ITS site expects, so a change that
    broke the local rule while fixing the phased one still goes red here.
    """
    def instashield(syms):
        return instashield_gate.routine_extent(syms, "P", prefix="$m$P$")

    def sprite_tilt(syms):
        return sprite_tilt_gate.routine_extent(syms, "Player_ApplyTilt")

    def loop_crossover(syms):
        return loop_crossover_gate.routine_extent(syms, "P")

    def waterline(syms):
        return waterline_art_gate.proc_span(syms, "P")

    return [
        ("instashield_gate.routine_extent", instashield, "P", "$m$P$loop"),
        ("sprite_tilt_gate.routine_extent", sprite_tilt, "Player_ApplyTilt",
         "$games.sonic4.player_common$Player_ApplyTilt$loop"),
        ("loop_crossover_gate.routine_extent", loop_crossover, "P", "$m$P$loop"),
        ("waterline_art_gate.proc_span", waterline, "P", "$m$P$loop"),
    ]


def base_map(name, local):
    return {name: START, local: START + 0x20, "NextProc": END}


class TestThePhasedNameSetIsReal(unittest.TestCase):
    def test_the_poison_is_a_name_the_tree_actually_declares_phased(self):
        """A plant built from an invented name could not go red against a filter that
        only knows the real ones — it would pass for the wrong reason."""
        self.assertIn(POISON, scene_spans.vma_phased_symbol_names())

    def test_the_set_is_not_empty(self):
        """An empty set makes every filter below a no-op and every test here vacuous."""
        self.assertTrue(scene_spans.vma_phased_symbol_names())


class TestEveryConsumerIsImmuneToAPhasedBoundary(unittest.TestCase):

    def test_the_true_extent_is_measured_first(self):
        """THE CONTROL. Without it an 'immune' result could be a function that returns
        the same wrong answer either way."""
        for label, fn, name, local in consumers():
            with self.subTest(label):
                self.assertEqual(fn(base_map(name, local)), (START, END))

    def test_a_phased_symbol_INSIDE_the_run_does_not_end_it(self):
        for label, fn, name, local in consumers():
            with self.subTest(label):
                syms = base_map(name, local)
                syms[POISON] = START + 1          # one byte inside the real run
                self.assertEqual(
                    fn(syms), (START, END),
                    f"{label} let a phased symbol end the routine — measured on the "
                    f"real build before this fix, all four truncated a 46..204 B "
                    f"routine to 1 B")

    def test_a_NON_phased_symbol_inside_the_run_STILL_ends_it(self):
        """The filter must be the phased set and not 'ignore anything inconvenient'.
        An ordinary symbol at the same address is a real boundary and must stay one —
        otherwise these tests would pass against a function that returns END always."""
        for label, fn, name, local in consumers():
            with self.subTest(label):
                syms = base_map(name, local)
                syms["An_Ordinary_Symbol"] = START + 1
                self.assertEqual(fn(syms), (START, START + 1))


class TestTheControl(unittest.TestCase):
    """`scene_spans.lst_proc_sizes` — the implementation the other four were corrected
    to match. It is measured, not cited: a control asserted from a docstring is not a
    control."""

    def write_lst(self, tmp, rows):
        p = os.path.join(tmp, "synthetic.lst")
        with open(p, "w") as f:
            for addr, name in rows:
                f.write(f"(0) 1/{addr:X} :        {name}:\n")
        return p

    def test_it_ignores_a_phased_symbol_and_keeps_an_ordinary_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            good = self.write_lst(tmp, [(START, "P"), (END, "NextProc")])
            self.assertEqual(scene_spans.lst_proc_sizes(good)["P"], END - START)
            poisoned = self.write_lst(tmp, [(START, "P"), (START + 1, POISON),
                                            (END, "NextProc")])
            self.assertEqual(scene_spans.lst_proc_sizes(poisoned)["P"], END - START)
            ordinary = self.write_lst(tmp, [(START, "P"), (START + 1, "Ordinary"),
                                            (END, "NextProc")])
            self.assertEqual(scene_spans.lst_proc_sizes(ordinary)["P"], 1)


class TestNoSIXTHConsumerSlipsIn(unittest.TestCase):
    """FAIL-SAFE, the shape `dplc_straddle.WRITERS` uses: the population is built by
    SCANNING for what touches the value, not from a list somebody remembered to
    update. A new tool that infers an extent the same way must be added to
    `consumers()` above (and filtered) or this goes red.
    """

    #: The two spellings of "the next symbol above the head" this tree actually uses:
    #: the filter comprehension (`a > start`, the four gates) and the address-sorted
    #: pairwise difference (`scene_spans.lst_proc_sizes`).
    #:
    #: THE SCAN IS SPELLING-BASED AND THAT IS ITS LIMIT, said out loud rather than
    #: left to be discovered: a sixth consumer written a THIRD way escapes it. It
    #: catches the case that actually happened — three copies of one spelling — and a
    #: population built from spellings cannot contain what nobody has written yet.
    #: The third string is narrowed to `rom[i + 1]` on purpose: the bare
    #: `[i + 1][0] - a` also matches `ramp_authored_witness`'s slope arithmetic over
    #: scanline accumulators, which is not a symbol extent at all. A detector that
    #: fires on an unrelated file trains its reader to widen CLAIMED, and a CLAIMED
    #: set with a passenger in it stops meaning anything.
    IDIOM = ("a > start", "v > start", "rom[i + 1][0] - a")

    CLAIMED = {
        "instashield_gate.py", "sprite_tilt_gate.py", "loop_crossover_gate.py",
        "waterline_art_gate.py", "scene_spans.py",
    }

    def test_every_file_using_the_next_symbol_idiom_is_claimed_and_filtered(self):
        here = os.path.dirname(os.path.abspath(__file__))
        found = set()
        for name in sorted(os.listdir(here)):
            if not name.endswith(".py") or name.startswith("test_"):
                continue
            with open(os.path.join(here, name), errors="replace") as f:
                src = f.read()
            if any(i in src for i in self.IDIOM):
                found.add(name)
                self.assertIn(
                    "vma_phased_symbol_names", src,
                    f"{name} infers a routine extent as 'the next symbol above the "
                    f"head' and does NOT filter phased symbols. This is S3's whole "
                    f"class: import the ONE derivation "
                    f"(scene_spans.vma_phased_symbol_names) rather than writing a "
                    f"fifth opinion, and add the site to consumers() above.")
        self.assertEqual(
            found, self.CLAIMED,
            "the set of files using the next-symbol idiom moved. Added: "
            f"{sorted(found - self.CLAIMED)}; gone: {sorted(self.CLAIMED - found)}")


if __name__ == "__main__":
    unittest.main()
