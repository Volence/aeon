#!/usr/bin/env python3
"""Tests for effects_budget_check — the budget model's code-derived rows."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effects_budget_check import (
    emp_constants, eval_int_expr, check, make_resolver, main as budget_main,
)

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every `const` form the shipped tree actually uses, so the regex is measured against
# reality rather than a convenient sample:
#   DECOY / BLOCKED   — a commented-out declaration must not become a constant
#   SIMPLE/HEXY/BINNY — the three integer literal bases `.emp` accepts
#   SUM / SHIFTED     — expressions referencing other constants (RASTER_STATE_SIZE's shape)
#   TYPED / NEWTYPED  — `const NAME : Type = v`, live in games/sonic4/config/sound_ids.emp
#   PRIVATE           — no `pub`; raster_dsl.emp's RASTER_PRE_CRAM_CYC is one
#   Act_grid_w_lo     — a non-ALL_CAPS const name, which the tree does contain
#   NO_VALUE          — a contract declaration with no `=`; not a constant
#   ARRAY             — a multi-line array; its head is not an integer expression
SAMPLE_EMP = """\
module engine.fake
// pub const DECOY = 999
/* pub const BLOCKED = 998
   pub const ALSO_BLOCKED = 997 */
pub const SIMPLE = 3
pub const HEXY = $10
pub const BINNY = %1110
pub const BUF = 128
pub const SUM = 4 + 4 + 2 + BUF + BUF
pub const SHIFTED = BUF << 1
pub const TYPED : SongId = 3
pub const NEWTYPED  : VramTile = $03E0   // trailing comment
const PRIVATE = 4
pub const Act_grid_w_lo = 7
    const NO_VALUE: bool
    const ARRAY: [u8; 2] = [
        1, 2,
    ]
"""


class TestEmpConstants(unittest.TestCase):
    def setUp(self):
        fh = tempfile.NamedTemporaryFile("w", suffix=".emp", delete=False)
        fh.write(SAMPLE_EMP)
        fh.close()
        self.path = fh.name

    def tearDown(self):
        os.unlink(self.path)

    def test_reads_decimal_hex_and_binary(self):
        c = emp_constants(self.path)
        self.assertEqual(eval_int_expr(c["SIMPLE"], c), 3)
        self.assertEqual(eval_int_expr(c["HEXY"], c), 16)
        self.assertEqual(eval_int_expr(c["BINNY"], c), 14)

    def test_resolves_expressions_referencing_other_constants(self):
        c = emp_constants(self.path)
        self.assertEqual(eval_int_expr(c["SUM"], c), 266)
        self.assertEqual(eval_int_expr(c["SHIFTED"], c), 256)

    def test_ignores_commented_out_constants(self):
        c = emp_constants(self.path)
        self.assertNotIn("DECOY", c)
        self.assertNotIn("BLOCKED", c)
        self.assertNotIn("ALSO_BLOCKED", c)

    def test_reads_the_type_annotated_form(self):
        """`pub const SONG_HCZ2 : SongId = 3` — a real form in games/sonic4/config."""
        c = emp_constants(self.path)
        self.assertEqual(eval_int_expr(c["TYPED"], c), 3)
        self.assertEqual(eval_int_expr(c["NEWTYPED"], c), 0x03E0)

    def test_reads_private_and_non_all_caps_constants(self):
        c = emp_constants(self.path)
        self.assertEqual(eval_int_expr(c["PRIVATE"], c), 4)
        self.assertEqual(eval_int_expr(c["Act_grid_w_lo"], c), 7)

    def test_a_declaration_without_a_value_is_not_a_constant(self):
        self.assertNotIn("NO_VALUE", emp_constants(self.path))

    def test_a_non_integer_value_fails_loudly_when_read(self):
        c = emp_constants(self.path)
        self.assertIn("ARRAY", c)          # matched, because it does have a value
        with self.assertRaises(ValueError):
            eval_int_expr(c["ARRAY"], c)   # but it is not an integer expression

    def test_rejects_a_non_arithmetic_expression(self):
        with self.assertRaises(ValueError):
            eval_int_expr("__import__('os').system('true')", {})

    def test_rejects_an_unknown_name_rather_than_defaulting(self):
        with self.assertRaises(ValueError):
            eval_int_expr("NOT_A_CONSTANT + 1", {})

    def test_rejects_a_circular_reference(self):
        with self.assertRaises(ValueError):
            eval_int_expr("A", {"A": "B", "B": "A"})


class TestLiveEmpFiles(unittest.TestCase):
    """The regex measured against the two shipped files, not a synthetic sample."""

    def test_resolves_the_two_state_size_constants(self):
        # Through `make_resolver` — the path the tool actually ships — NOT a hand-built
        # scope. This test used to read raster.emp alone and evaluate against its own
        # constants, which stopped working the moment RASTER_STATE_SIZE came to name
        # RASTER_MAX_PATCH: that lives in the sibling raster_dsl.emp and is glob-injected
        # by sigil rather than imported. The tool grew the sibling injection for exactly
        # that reason (see make_resolver's comment); this test was never moved onto it,
        # so it sat red in a suite nothing ran.
        #
        # NO LITERAL SIZE IS ASSERTED HERE, deliberately. The old form pinned 288, and by
        # the time anyone ran it the real value was 318 — the number had grown legitimately
        # and the stale literal was invisible behind the traceback above it. Both spans are
        # ALREADY pinned at build time by an `ensure` against the linker's own
        # `X_State_End - X_State`, so re-asserting a copy here adds no authority and one
        # more thing to rot. What is genuinely this tool's job is that the expressions
        # RESOLVE at all, cross-module names included.
        resolve = make_resolver(AEON)
        for ref in ("engine/effects/raster.emp:RASTER_STATE_SIZE",
                    "engine/effects/palette.emp:PALETTE_STATE_SIZE"):
            v = resolve(ref)
            self.assertIsInstance(v, int)
            self.assertGreater(v, 0, f"{ref} resolved to a non-positive size")

    def test_cross_module_names_need_the_sibling_injection(self):
        # The regression guard for the bug the test above was masking. RASTER_STATE_SIZE
        # names RASTER_MAX_PATCH, which is NOT in raster.emp. Without the sibling
        # *_dsl.emp injection the resolver must fail loudly rather than resolve to
        # something plausible — and this test proves the injection is load-bearing rather
        # than decorative, which the previous version never did.
        import glob as _glob
        real = _glob.glob
        _glob.glob = lambda pattern: []
        try:
            with self.assertRaises(ValueError) as cm:
                make_resolver(AEON)("engine/effects/raster.emp:RASTER_STATE_SIZE")
            self.assertIn("RASTER_MAX_PATCH", str(cm.exception))
        finally:
            _glob.glob = real


class TestCheck(unittest.TestCase):
    def test_reports_a_disagreeing_row(self):
        rows = check(
            {"ram": {"raster_state_bytes": 286}},
            {"ram.raster_state_bytes": "fake.emp:RASTER_STATE_SIZE"},
            resolver=lambda ref: 288,
        )
        self.assertEqual(rows, [("ram.raster_state_bytes", 286, 288)])

    def test_agreeing_rows_report_nothing(self):
        rows = check(
            {"ram": {"raster_state_bytes": 288}},
            {"ram.raster_state_bytes": "fake.emp:RASTER_STATE_SIZE"},
            resolver=lambda ref: 288,
        )
        self.assertEqual(rows, [])

    def test_a_symbol_naming_a_missing_row_is_an_error_not_a_pass(self):
        with self.assertRaises(KeyError):
            check({"ram": {}}, {"ram.nope": "fake.emp:X"}, resolver=lambda ref: 1)

    def test_a_symbol_naming_a_missing_table_is_an_error_not_a_pass(self):
        with self.assertRaises(KeyError):
            check({}, {"nosuch.row": "fake.emp:X"}, resolver=lambda ref: 1)

    def test_a_symbol_indexing_THROUGH_a_scalar_is_an_error_not_a_pass(self):
        with self.assertRaises(KeyError):
            check({"ram": {"n": 1}}, {"ram.n.deeper": "fake.emp:X"},
                  resolver=lambda ref: 1)


class TestLiveTree(unittest.TestCase):
    def test_the_shipped_budget_model_agrees_with_the_shipped_code(self):
        """The live gate. Fails the suite the moment a constant and the TOML drift."""
        rc = budget_main([AEON])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
