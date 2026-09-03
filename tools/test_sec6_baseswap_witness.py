"""Unit cover for `tools/sec6_baseswap_witness.py` — the pure halves and the source reads.

WHY THIS FILE NEVER OPENS A ROM OR AN EMULATOR, `test_plane_base_swap_gate.py`'s reason:
build.sh runs this tree's pytest on every canonical build, and a test that booted an
emulator would put a 30-second headless server inside a lane that must stay fast. The
witness itself is the emulator half and rides `tools/effects_gates.py`.

WHAT IT ACTUALLY PROTECTS. Three of the witness's judgements are pure functions, and they
are the ones a green run depends on being *unable* to lie:

  * `classify` must answer "sparse" and "ambiguous" — never "A" or "T" — whenever the
    fingerprint cannot name a base. A classifier that guessed on a tie would turn the whole
    instrument into a coin flip that reports certainty.
  * `find_run` must wrap horizontally, because a scanline's cells cross the right edge of a
    64-cell nametable row routinely, and a non-wrapping search would report "not found" for
    a perfectly good run — i.e. an UNMEASURABLE that is really a bug in the searcher.
  * `base_swap_expectation` must REFUSE a target equal to Plane A's own base. That is the
    silent-no-op case `plane_base_swap_gate.py`'s docstring names: a swap that re-points
    Plane A at the base it already has changes no pixel, and every picture arm downstream
    would then be measuring nothing while reporting a boundary it never found.

The source-read tests assert against the LIVE tree, so a rename in `constants.emp`,
`preset.emp` or the generated chooser surfaces here rather than as a mystery mismatch.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sec6_baseswap_witness as W  # noqa: E402

REPO = W.REPO
COLS = W.PLANE_COLS


def row_map(rows):
    """A 64x64 nametable whose row i is `rows[i]` cycled; unnamed rows are a constant filler."""
    out = []
    for r in range(W.PLANE_ROWS):
        src = rows.get(r)
        out += [src[c % len(src)] for c in range(COLS)] if src else [0x9999] * COLS
    return out


class TestFindRun(unittest.TestCase):
    def test_finds_a_plain_run(self):
        m = row_map({3: list(range(COLS))})
        self.assertIn((3, 10), W.find_run(m, [10, 11, 12, 13]))

    def test_wraps_the_right_edge(self):
        m = row_map({0: list(range(COLS))})
        # 62, 63, 0, 1 exists only if the search wraps.
        self.assertIn((0, 62), W.find_run(m, [62, 63, 0, 1]))

    def test_wildcards_do_not_constrain(self):
        m = row_map({5: list(range(COLS))})
        self.assertIn((5, 20), W.find_run(m, [20, None, 22]))

    def test_absent_run_is_absent(self):
        self.assertEqual(W.find_run(row_map({1: [7, 8, 9]}), [1, 2, 3, 4, 5]), [])


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.a = row_map({0: [0x1000 + i for i in range(COLS)]})
        self.t = row_map({0: [0x2000 + i for i in range(COLS)]})

    def run_from(self, base):
        return [base + i for i in range(W.MIN_RESOLVED)]

    def test_names_plane_a(self):
        self.assertEqual(W.classify(self.run_from(0x1000), self.a, self.t), "A")

    def test_names_the_target(self):
        self.assertEqual(W.classify(self.run_from(0x2000), self.a, self.t), "T")

    def test_too_few_resolved_dots_is_sparse_not_a_verdict(self):
        run = self.run_from(0x1000)[:W.MIN_RESOLVED - 1] + [None]
        self.assertEqual(W.classify(run, self.a, self.t), "sparse")

    def test_found_in_both_is_ambiguous(self):
        same = row_map({0: [0x3000 + i for i in range(COLS)]})
        self.assertEqual(W.classify(self.run_from(0x3000), same, same), "ambiguous")

    def test_found_in_neither_is_ambiguous(self):
        self.assertEqual(W.classify(self.run_from(0x7000), self.a, self.t), "ambiguous")


class TestContiguous(unittest.TestCase):
    def test_gap_is_not_contiguous(self):
        self.assertFalse(W.contiguous([161, 162, 164]))
        self.assertTrue(W.contiguous([161, 162, 163]))
        self.assertFalse(W.contiguous([]))


class TestExpectation(unittest.TestCase):
    def doc(self, **kw):
        d = {"id": "x", "base_swap": {"line": 160, "target": 0xE000}}
        d["base_swap"].update(kw)
        return d

    def test_derives_the_one_line_window(self):
        e = W.base_swap_expectation(self.doc(), "doc", 0xC000)
        self.assertEqual(e["first_window"], (160, 161))
        self.assertEqual((e["line"], e["target"]), (160, 0xE000))

    def test_refuses_a_target_equal_to_plane_as_own_base(self):
        with self.assertRaises(W.Refused):
            W.base_swap_expectation(self.doc(target=0xC000), "doc", 0xC000)

    def test_refuses_a_line_outside_the_display(self):
        for bad in (0, W.ACTIVE_H, 400):
            with self.assertRaises(W.Refused):
                W.base_swap_expectation(self.doc(line=bad), "doc", 0xC000)

    def test_refuses_a_document_with_no_base_swap(self):
        with self.assertRaises(W.Refused):
            W.base_swap_expectation({"id": "x", "bands": []}, "doc", 0xC000)


class TestSourceReads(unittest.TestCase):
    """Against the LIVE tree: a rename should surface here, not as a mystery mismatch."""

    def test_geometry_reads_the_shipped_constants(self):
        g = W.geometry(REPO)
        self.assertEqual(g["plane_a"], 0xC000)
        self.assertEqual(g["size"], 1 << g["shift"])
        self.assertGreater(g["grid_w"], 0)

    def test_ep_raster_offset_comes_from_the_struct(self):
        text = open(os.path.join(REPO, W.PRESET_STRUCT), encoding="utf-8").read()
        self.assertEqual(W.struct_field_offset(text, "EffectsPreset", "ep_raster",
                                               W.PRESET_STRUCT), 0x08)

    def test_a_missing_struct_field_refuses_rather_than_returning_zero(self):
        text = open(os.path.join(REPO, W.PRESET_STRUCT), encoding="utf-8").read()
        with self.assertRaises(W.Refused):
            W.struct_field_offset(text, "EffectsPreset", "ep_not_a_field", W.PRESET_STRUCT)

    def test_section_6_is_bound_to_the_document_the_witness_measures(self):
        ref, _ = W.sidecar_ref(REPO, W.SECTION)
        label, arms = W.chooser_binding(REPO, W.SECTION)
        self.assertIsNotNone(ref, "section 6's rasterRef is null — there is nothing to witness")
        self.assertEqual(label, f"EditorRaster_OJZ_Act1_{ref}")
        preset, _ = W.load_preset(REPO, ref)
        self.assertIn("base_swap", preset)


if __name__ == "__main__":
    unittest.main()
