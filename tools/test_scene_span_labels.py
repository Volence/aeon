"""Scanline P2 Task 6 — the bracketing-label emission convention.

Design §3.3 states the convention as an EMISSION rule, not an afterthought, because
§8.2's path-level span gates cannot measure a capability-gated block that carries no
boundary symbols: the flat `.lst` drops `$`-mangled locals, which is why
`raster_source_gate` had to hand-roll a resolver. Labels first, gating second.

WHY THIS FILE IS SOURCE-LEVEL AND NOT `.lst`-LEVEL, stated plainly so nobody
"fixes" it back:

  build.sh runs `python3 -m pytest tools/` BEFORE it invokes sigil (build.sh:209 vs
  build.sh:318). A test in this lane that read `s4.debug.lst` would be reading the
  PREVIOUS build's listing — it would pass on stale evidence for the edit that broke
  it, and it would make a clean checkout unbuildable (no listing exists yet, and a
  hard failure here aborts the build before the listing can be produced).

  So the `.lst` half of the convention lives POST-BUILD, in
  tools/demo_specialization_witness.py and the span gates in tools/effects_gates.py.
  This file owns the half that is a property of the SOURCE and is checkable at any
  time: every bracket is paired, every bracket names a real capability, every gated
  block carries a pair, and every bracket sits inside a gate.

EXPECTATIONS ARE DERIVED, NEVER COPIED — see tools/scene_spans.py, the one reader all
three consumers share.
"""

import unittest

from scene_spans import (SCENE_DSL, brackets, capability_bits, gated_blocks,
                         span_capability)


class TestCapabilityAuthority(unittest.TestCase):

    def test_the_five_p1_bits_are_declared(self):
        """A sanity floor on the parse itself: if scene_dsl re-spells its consts,
        every derivation below would quietly resolve against an empty set."""
        bits = capability_bits()
        self.assertEqual(
            sorted(bits),
            ["CAP_ANCHORS", "CAP_DEFORM", "CAP_PER_COL_VSRAM",
             "CAP_PER_LINE", "CAP_TRANSITIONS"])
        self.assertEqual(len(set(bits.values())), len(bits),
                         "two capabilities share a bit: %r" % (bits,))

    def test_reserved_comment_bits_are_not_parsed_as_declarations(self):
        """The reserved P3+ bits live in a comment and have no lowering. A bracket
        naming one would bracket a block that cannot exist, so the parse must not
        see them."""
        self.assertNotIn("CAP_COMPUTED", capability_bits())
        self.assertNotIn("CAP_DENSE_TIER", capability_bits())


class TestBracketConvention(unittest.TestCase):

    def test_the_convention_is_in_force_at_all(self):
        """Red-first anchor: before Task 6 there are no brackets anywhere, and every
        span gate downstream of this file has nothing to measure."""
        found = brackets()
        self.assertTrue(
            found,
            "no bracketing labels (.cap_<capability>_<site>_begin/_end) anywhere under "
            "engine/ — the emission convention is not in force, so §8.2's path-level "
            "span gates cannot see any capability-gated block")

    def test_every_bracket_is_paired_within_its_file(self):
        opens, closes = {}, {}
        for path, span, kind, _off in brackets():
            (opens if kind == "begin" else closes).setdefault((path, span), 0)
            (opens if kind == "begin" else closes)[(path, span)] += 1
        self.assertEqual(
            sorted(opens), sorted(closes),
            "unbalanced brackets: %r" % (set(opens) ^ set(closes),))
        for key, n in opens.items():
            self.assertEqual(n, 1, "%s opened %d times in one file — a duplicate "
                                   "label is a redefinition; give each site its own "
                                   "site token" % (key[1], n))
        for key, n in closes.items():
            self.assertEqual(n, 1, "%s closed %d times in one file" % (key[1], n))

    def test_every_span_name_resolves_to_a_declared_capability(self):
        bits = capability_bits()
        for path, span, kind, _off in brackets():
            self.assertIsNotNone(
                span_capability(span, bits),
                "%s: bracket `cap_%s_%s` names no declared capability — span names are "
                "`cap_<capability>_<site>` and the capability half must be a CAP_* "
                "declared in scene_dsl.emp" % (path, span, kind))

    def test_longest_prefix_resolution_is_unambiguous(self):
        """`per_line` must not be able to claim a `per_line_...` span that a longer
        capability name also matches. With today's five bits it cannot; this fails
        the day a new CAP_ makes it possible, which is when the rule needs revisiting."""
        lowered = sorted(name[len("CAP_"):].lower() for name in capability_bits())
        for a in lowered:
            for b in lowered:
                if a != b:
                    self.assertFalse(
                        b.startswith(a + "_"),
                        "capability names %r and %r nest, so longest-prefix span "
                        "resolution is ambiguous" % (a, b))


class TestGatesAndBracketsAgree(unittest.TestCase):
    """The two directions §8.2 needs, and they are NOT the same check.

    A gate without brackets is a specialisation no span gate can see. A bracket
    without a gate reports a specialisation that never happens — the span lane would
    call `cap_X` absent from demo while the bytes it names were never conditional at
    all. Both are silent; both are checked here.
    """

    def test_the_gates_are_in_force_at_all(self):
        self.assertTrue(
            gated_blocks(),
            "no `if (Game.SCANLINE_CAPS & CAP_*) != 0` block anywhere under engine/ — "
            "the brackets are decoration until something gates on them")

    def test_every_gated_block_carries_a_bracket_pair_for_its_own_capability(self):
        bits = capability_bits()
        for path, cap, start, end in gated_blocks():
            own = [span for _p, span, _k, off in brackets()
                   if _p == path and start < off < end
                   and span_capability(span, bits) == cap]
            self.assertTrue(
                own,
                "%s: a `Game.SCANLINE_CAPS & %s` block carries no bracketing label of "
                "its own capability — §8.2's span gates cannot measure it" % (path, cap))

    def test_every_bracket_sits_inside_a_gate_for_its_own_capability(self):
        bits = capability_bits()
        blocks = gated_blocks()
        for path, span, kind, off in brackets():
            cap = span_capability(span, bits)
            enclosing = [c for p, c, s, e in blocks
                         if p == path and s < off < e and c == cap]
            self.assertTrue(
                enclosing,
                "%s: bracket `.cap_%s_%s` is not inside any `Game.SCANLINE_CAPS & %s` "
                "block — an unGATED bracket makes the span lane report a specialisation "
                "that never happens" % (path, span, kind, cap))


if __name__ == "__main__":
    unittest.main()
