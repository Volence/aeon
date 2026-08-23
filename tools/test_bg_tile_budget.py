"""png_to_bg_override.py must refuse above the STATIC budget, not the capacity.

The defect this gates (docs/BUGS.md TOOL-01): the importer treated
BG_TILE_CAPACITY as a pass/fail line — it refused above 448 and was indifferent
everywhere below — so band space was "whatever the art happened not to use",
which trends to zero because nothing pushes back. The 2026-07-21 import packed
to 448/448 and destroyed two shipped BgAnim bands that cannot now be re-authored
at any size, 1x1 included.

The fix is a reserve declared in games/sonic4/vram.toml (`band_reserve` on
bg_region), flowing through gen_vram_map.py into tools/vram_map.py as
BG_BAND_RESERVE / BG_STATIC_TILE_BUDGET. A --max-tiles flag was rejected: a flag
is forgotten on the next import, which recreates the exact bug.

EVERY expectation here is DERIVED from the imported constants or measured from
the tool's own output. There is no 448 in this file, and none of the boundaries
are copied from a nearby pin — a hardcoded 448 would keep passing after someone
changed the region, which is the failure mode these tests exist to catch.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import png_to_bg_override as tool

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIVE_OVERRIDE = os.path.join(REPO, "games/sonic4/data/editor_bg_override.json")

# Wording that ONLY the reserve refusal produces. Deliberately not "budget" or
# "tiles": both of those also appear in the zero-reserve refusal, and this repo
# has already shipped a poison that passed with its guard deleted because the
# matcher hit a substring a DIFFERENT message also produced.
RESERVE_ONLY_PHRASE = "are withheld"


def _write_png(path):
    """8 vertical 8px stripes over 64x64 — width 64 divides the 512px plane."""
    a = np.zeros((64, 64, 3), np.uint8)
    for i, c in enumerate([(0, 0, 0), (34, 34, 34), (68, 68, 68), (102, 102, 102),
                           (136, 136, 136), (170, 170, 170), (204, 204, 204),
                           (255, 255, 255)]):
        a[:, i * 8:(i + 1) * 8] = c
    Image.fromarray(a).save(path)


class _Reserve:
    """Patch the tool's reserve, keeping the budget DERIVED from it.

    Setting the two globals independently would let a test assert against a
    budget the reserve does not imply, i.e. test its own arithmetic instead of
    the tool's. Here the budget is always capacity - reserve, exactly as
    gen_vram_map.py computes it.
    """

    def __init__(self, reserve):
        self.reserve = reserve

    def __enter__(self):
        self.saved = (tool.BG_BAND_RESERVE, tool.BG_STATIC_TILE_BUDGET)
        tool.BG_BAND_RESERVE = self.reserve
        tool.BG_STATIC_TILE_BUDGET = tool.BG_TILE_CAPACITY - self.reserve
        return self

    def __exit__(self, *exc):
        tool.BG_BAND_RESERVE, tool.BG_STATIC_TILE_BUDGET = self.saved
        return False


class TestShippedDefault(unittest.TestCase):
    """Reserve 0 must behave exactly as before this field existed."""

    def test_shipped_reserve_is_zero(self):
        self.assertEqual(
            tool.BG_BAND_RESERVE, 0,
            "the shipped default must stay 0 — a non-zero reserve is the "
            "owner's call at their next art pass, not this parcel's")

    def test_budget_is_capacity_minus_reserve(self):
        self.assertEqual(tool.BG_STATIC_TILE_BUDGET,
                         tool.BG_TILE_CAPACITY - tool.BG_BAND_RESERVE)

    def test_at_zero_reserve_the_budget_is_the_whole_region(self):
        self.assertEqual(tool.BG_STATIC_TILE_BUDGET, tool.BG_TILE_CAPACITY)

    def test_the_live_saturated_blob_still_passes(self):
        """The shipped override is at the ceiling; reserve 0 must still accept it.

        The tile count is READ from the file, never asserted as a literal: this
        test's job is "today's data still passes", not "today's data is 448".
        """
        if not os.path.exists(LIVE_OVERRIDE):
            self.skipTest(f"no live override at {LIVE_OVERRIDE} — nothing to check "
                          "(reported as a skip, not as a pass)")
        n = len(json.load(open(LIVE_OVERRIDE))["tiles"])
        self.assertLessEqual(
            n, tool.BG_TILE_CAPACITY,
            f"the live override carries {n} tiles, past the "
            f"{tool.BG_TILE_CAPACITY}-tile VRAM boundary")
        tool.check_tile_budget(n)   # must not raise at the shipped reserve


class TestBoundaryIsExact(unittest.TestCase):
    """BUDGET passes, BUDGET + 1 refuses — at zero AND non-zero reserve."""

    def test_exact_boundary_at_the_shipped_reserve(self):
        tool.check_tile_budget(tool.BG_STATIC_TILE_BUDGET)
        with self.assertRaises(SystemExit):
            tool.check_tile_budget(tool.BG_STATIC_TILE_BUDGET + 1)

    def test_exact_boundary_at_a_non_zero_reserve(self):
        # 192 = the historical animated-slot count (32x4 + 16x4 bands), used
        # here only as a plausible non-zero value; every assertion below is
        # derived from the resulting budget, not from 192 or from 448.
        with _Reserve(192) as r:
            budget = tool.BG_TILE_CAPACITY - r.reserve
            self.assertEqual(tool.BG_STATIC_TILE_BUDGET, budget)
            tool.check_tile_budget(budget)
            with self.assertRaises(SystemExit):
                tool.check_tile_budget(budget + 1)

    def test_a_full_reserve_leaves_no_static_budget(self):
        with _Reserve(tool.BG_TILE_CAPACITY):
            tool.check_tile_budget(0)
            with self.assertRaises(SystemExit):
                tool.check_tile_budget(1)


class TestReservePoison(unittest.TestCase):
    """Art under the capacity but over the budget must be refused, by name."""

    def test_tiles_that_fit_the_region_but_not_the_budget_are_refused(self):
        reserve = 192
        with _Reserve(reserve):
            budget = tool.BG_STATIC_TILE_BUDGET
            n = budget + 1
            # the poison's premise: this art WOULD have passed before the
            # reserve existed. If that stops holding, the test is no longer
            # testing the reserve and must say so rather than pass quietly.
            self.assertLessEqual(
                n, tool.BG_TILE_CAPACITY,
                "premise broken: the poison tile count no longer fits the "
                "region, so it would be refused with or without a reserve")
            with self.assertRaises(SystemExit) as cm:
                tool.check_tile_budget(n)
            msg = str(cm.exception)
            self.assertIn(RESERVE_ONLY_PHRASE, msg)
            self.assertIn(str(reserve), msg)
            self.assertIn(str(budget), msg)
            self.assertIn(str(tool.BG_TILE_CAPACITY), msg)
            self.assertIn(str(n), msg)

    def test_the_matcher_does_not_also_match_the_zero_reserve_refusal(self):
        """Guard the guard: RESERVE_ONLY_PHRASE must be unique to this rule.

        The repo has shipped a poison that stayed green with its guard deleted,
        because the phrase it matched was also produced by a different refusal.
        So assert the OTHER refusal does not carry it.
        """
        with _Reserve(0):
            with self.assertRaises(SystemExit) as cm:
                tool.check_tile_budget(tool.BG_STATIC_TILE_BUDGET + 1)
            self.assertNotIn(RESERVE_ONLY_PHRASE, str(cm.exception))

    def test_zero_reserve_refusal_does_not_fabricate_a_reserve(self):
        """A right verdict with an invented reason is worse than a red gate."""
        with _Reserve(0):
            with self.assertRaises(SystemExit) as cm:
                tool.check_tile_budget(tool.BG_STATIC_TILE_BUDGET + 1)
            msg = str(cm.exception)
            self.assertIn("band_reserve is 0", msg)
            self.assertNotIn("withheld", msg)

    def test_refusal_states_the_shortfall_correctly(self):
        """Every number the message prints must match the data it printed for."""
        with _Reserve(64):
            budget = tool.BG_STATIC_TILE_BUDGET
            n = budget + 37
            with self.assertRaises(SystemExit) as cm:
                tool.check_tile_budget(n)
            msg = str(cm.exception)
            self.assertIn(f"Simplify the art by {n - budget} unique tiles", msg)
            self.assertIn(f"{tool.BG_TILE_CAPACITY} - 64 = {budget}", msg)


class TestEndToEndThroughMain(unittest.TestCase):
    """The wiring, not just the helper: constant -> main() -> refusal.

    check_tile_budget could be perfect while main() still gated on the capacity.
    These run the real entry point over real art, with the boundary derived from
    that art's MEASURED unique-tile count.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.png = os.path.join(cls._tmp.name, "bg.png")
        _write_png(cls.png)
        cls.n_tiles = cls._measure()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @classmethod
    def _run(cls, out_name):
        out = os.path.join(cls._tmp.name, out_name)
        saved = sys.argv
        sys.argv = ["png_to_bg_override.py", cls.png, "--out", out]
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                tool.main()
        finally:
            sys.argv = saved
        return out, buf.getvalue()

    @classmethod
    def _measure(cls):
        """The art's actual unique-tile count, from the file the tool wrote."""
        out, _ = cls._run("measure.json")
        return len(json.load(open(out))["tiles"])

    def test_the_measurement_is_usable(self):
        """Loud on unmeasurable: a 0 here would make every boundary vacuous."""
        self.assertGreater(
            self.n_tiles, 0,
            "the fixture art produced no tiles — the boundary tests below "
            "would be meaningless, so this fails rather than reporting green")
        self.assertLessEqual(self.n_tiles, tool.BG_TILE_CAPACITY)

    def test_main_accepts_art_exactly_at_the_budget(self):
        with _Reserve(tool.BG_TILE_CAPACITY - self.n_tiles):
            self.assertEqual(tool.BG_STATIC_TILE_BUDGET, self.n_tiles)
            out, log = self._run("at_budget.json")
            self.assertEqual(len(json.load(open(out))["tiles"]), self.n_tiles)
            self.assertIn(f"unique tiles: {self.n_tiles}/{self.n_tiles}", log)

    def test_main_refuses_art_one_tile_over_the_budget(self):
        with _Reserve(tool.BG_TILE_CAPACITY - self.n_tiles + 1):
            self.assertEqual(tool.BG_STATIC_TILE_BUDGET, self.n_tiles - 1)
            with self.assertRaises(SystemExit) as cm:
                self._run("over_budget.json")
            msg = str(cm.exception)
            self.assertIn(RESERVE_ONLY_PHRASE, msg)
            self.assertIn(str(self.n_tiles), msg)

    def test_main_refusal_writes_no_file(self):
        """The refusal must land before the write, not after a partial one."""
        with _Reserve(tool.BG_TILE_CAPACITY - self.n_tiles + 1):
            out = os.path.join(self._tmp.name, "never_written.json")
            saved = sys.argv
            sys.argv = ["png_to_bg_override.py", self.png, "--out", out]
            try:
                with self.assertRaises(SystemExit):
                    with redirect_stdout(io.StringIO()):
                        tool.main()
            finally:
                sys.argv = saved
            self.assertFalse(os.path.exists(out),
                             "a refused import left an output file behind")


if __name__ == "__main__":
    unittest.main()
