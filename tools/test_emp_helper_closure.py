#!/usr/bin/env python3
"""Tests for emp_helper_closure — the COMPTIME_HELPERS name-collision gate."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emp_helper_closure import (
    comptime_items, helper_ids_from_native, find_collisions,
    default_native_rs, module_index, main as closure_main,
)

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGIL_NATIVE = default_native_rs(AEON)

# Every declaration form the `.emp` grammar can put in ITEM position, paired with
# the answer sigil gives for it. `publicize_helper_comptime` force-publicizes
# Const/Struct/Enum/Bitfield/Newtype/ComptimeFn/Vars(named) and recurses into
# `section` bodies; `collect_pub_comptime` then injects those PLUS an
# already-`pub` Context and an already-`pub` Data whose type is a single bare
# named type (the type-only stub). Everything else is invisible to a consumer.
SAMPLE = """\
// a comment mentioning const NOT_A_COMMENT_ITEM = 1
module engine.fake.dsl

use engine.structs.{Sec}

/// doc comment mentioning const NOT_A_DOC_ITEM = 1
pub const ALPHA = 3
const BETA = $10
pub comptime fn gamma(x: int) -> int { return x }
comptime fn delta() -> int {
    let inner_not_an_item = 1
    return inner_not_an_item
}
pub struct Epsilon { e_a: u16 }
comptime enum Zeta { One, Two }
pub comptime enum Eta { A(int) }
bitfield Theta : u8 { b0: 1 }
newtype Iota = u16
pub vars Kappa: Sst.sst_custom { k: u16 }
pub vars not_an_item_region { r: u16 }
pub context Lambda { acquire { nop } release { nop } }
context NotPubContext { acquire { nop } release { nop } }
pub data Mu: Epsilon = Epsilon{ e_a: 0 }
pub data NotThisEither: [u16; 1] = [0]
pub data NotDottedEither: engine.structs.Sec = 0
data NotPubData: Epsilon = Epsilon{ e_a: 0 }
pub proc NotAnItem () clobbers() { rts }
ensure(1 == 1, "not an item, and this brace { is inside a string")
/*
pub const NOT_IN_BLOCK_COMMENT = 1
*/
section fake_section {
    pub const NU = 7
    comptime fn xi() -> int { return 1 }
}
"""

SAMPLE_EXPECTED = {
    "ALPHA", "BETA", "gamma", "delta", "Epsilon", "Zeta", "Eta", "Theta",
    "Iota", "Kappa", "Lambda", "Mu", "NU", "xi",
}


def _items_of(text):
    with tempfile.NamedTemporaryFile("w", suffix=".emp", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        return comptime_items(path)
    finally:
        os.unlink(path)


class TestComptimeItems(unittest.TestCase):

    def test_extracts_every_comptime_kind_public_and_private(self):
        self.assertEqual(_items_of(SAMPLE), SAMPLE_EXPECTED)

    def test_excludes_procs_data_ensures_and_comments(self):
        names = _items_of(SAMPLE)
        for excluded in ("NotAnItem", "NotThisEither", "NOT_A_COMMENT_ITEM",
                         "NOT_A_DOC_ITEM", "NOT_IN_BLOCK_COMMENT"):
            self.assertNotIn(excluded, names)

    def test_vars_region_form_is_not_exported_but_overlay_form_is(self):
        """`Item::Vars(d) if d.name.is_some()` — only the `Name: region` overlay."""
        names = _items_of(SAMPLE)
        self.assertIn("Kappa", names)
        self.assertNotIn("not_an_item_region", names)

    def test_private_context_is_not_exported_but_pub_context_is(self):
        """publicize_helper_comptime never touches Context, so private stays private."""
        names = _items_of(SAMPLE)
        self.assertIn("Lambda", names)
        self.assertNotIn("NotPubContext", names)

    def test_pub_data_of_bare_named_type_is_exported_as_a_type_only_stub(self):
        """pub_struct_data_name: `pub data X: Named` injects; array/dotted/private do not."""
        names = _items_of(SAMPLE)
        self.assertIn("Mu", names)
        self.assertNotIn("NotThisEither", names)
        self.assertNotIn("NotDottedEither", names)
        self.assertNotIn("NotPubData", names)

    def test_section_bodies_are_walked_one_level_deep(self):
        """publicize_helper_comptime recurses into Item::Section."""
        names = _items_of(SAMPLE)
        self.assertIn("NU", names)
        self.assertIn("xi", names)

    def test_fn_body_locals_are_not_items(self):
        """Only item position counts — a `let` in a comptime fn body is not exported."""
        self.assertNotIn("inner_not_an_item", _items_of(SAMPLE))

    def test_block_comment_hides_a_declaration(self):
        self.assertEqual(_items_of("module m\n/* pub const HIDDEN = 1 */\n"), set())

    def test_unbalanced_braces_are_a_hard_error_not_a_silent_miss(self):
        """A desynced depth scan would silently drop items; fail loudly instead."""
        with self.assertRaises(ValueError):
            _items_of("module m\npub struct Broken {\n  a: u16\n")


class TestRealHelperForms(unittest.TestCase):
    """Forms that genuinely occur in the twelve shipped helpers."""

    def test_irq_pub_contexts_are_seen(self):
        names = comptime_items(os.path.join(AEON, "engine", "irq.emp"))
        self.assertIn("ints_off", names)
        self.assertIn("vblank", names)

    def test_structs_module_exports_its_structs_and_consts(self):
        names = comptime_items(os.path.join(AEON, "engine", "structs.emp"))
        self.assertIn("Sec", names)
        self.assertGreater(len(names), 5)

    def test_sst_exports_its_private_const_but_not_its_struct_fields(self):
        """Force-publicization is the whole hazard: TEMPLATE_COPY_SHIFT is `const`,
        not `pub const`, and still lands in every module's ambient scope. Struct
        FIELDS (x_pos, sst_custom, ...) are not items and never do."""
        names = comptime_items(os.path.join(AEON, "engine", "objects", "sst.emp"))
        self.assertEqual(
            names,
            {"Sst", "ObjDef", "interact_off", "size_wh_off",
             "TEMPLATE_COPY_SHIFT", "set_priority_band"},
        )

    def test_every_helper_module_parses_and_exports_something(self):
        ids = helper_ids_from_native(SIGIL_NATIVE)
        index = module_index(AEON)
        for mod in ids:
            self.assertIn(mod, index, f"{mod} has no .emp file declaring it")
            self.assertTrue(comptime_items(index[mod]), f"{mod} exported nothing")


class TestHelperList(unittest.TestCase):

    def test_helper_ids_parsed_from_native_rs(self):
        ids = helper_ids_from_native(SIGIL_NATIVE)
        self.assertIn("engine.vdp", ids)
        self.assertIn("engine.level.parallax_dsl", ids)
        self.assertGreaterEqual(len(ids), 12)

    def test_locator_finds_the_paired_sigil_checkout(self):
        self.assertTrue(os.path.exists(default_native_rs(AEON)))


class TestModuleIndex(unittest.TestCase):

    def test_module_id_is_read_from_the_declaration_not_the_path(self):
        """engine.types lives at engine/system/types.emp — path mapping would miss it."""
        index = module_index(AEON)
        self.assertTrue(index["engine.types"].endswith(
            os.path.join("engine", "system", "types.emp")))
        self.assertTrue(index["engine.constants"].endswith(
            os.path.join("engine", "system", "constants.emp")))


class TestCollisions(unittest.TestCase):

    def test_reports_a_duplicate_across_two_helpers(self):
        found = find_collisions({"a.one": {"X", "Y"}, "b.two": {"Y", "Z"}})
        self.assertEqual(found, [("Y", ["a.one", "b.two"])])

    def test_clean_set_reports_nothing(self):
        self.assertEqual(find_collisions({"a.one": {"X"}, "b.two": {"Y"}}), [])


class TestLiveTree(unittest.TestCase):

    def test_the_shipped_helper_set_is_collision_free(self):
        """The live gate. Fails the suite the moment a helper shadows another."""
        rc = closure_main([AEON, SIGIL_NATIVE])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
