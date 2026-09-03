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

from scene_spans import (retired_capability_bits, SCENE_DSL, brackets, capability_bits, gated_blocks,
                         span_capability)


class TestCapabilityAuthority(unittest.TestCase):

    def test_the_declared_bits_are_the_p1_survivors_plus_the_p3_and_p4_promotions(self):
        """A sanity floor on the parse itself: if scene_dsl re-spells its consts,
        every derivation below would quietly resolve against an empty set.

        P3 Task 5 promoted CAP_MULTI_DEFORM_TABLE and CAP_FACTOR_CURVE out of the
        reserved comment so their gates become measurable AHEAD of the lowerings that
        raise them (Tasks 7 and 10). CAP_BAND_DRIFT was promoted by the band-drift parcel
        WITH its lowering and its three bracketed spans in one commit, per the standing
        rule in scene_dsl's own CAP_* block — and it took $0080, the next bit, which
        shifted the five still-reserved names up one each. CAP_ANCHOR_MOTION did the same a
        day later (EFFECTS-W1 item 4, the anchor mover) at $0100, shifting them up again;
        unlike every bit before it, it gates spans in engine/effects/raster.emp rather than
        in parallax.emp, because the mover is evaluated inside Effects_LatchWorldLines — the
        single derivation all three edge consumers read. CAP_DENSE_TIER did the same again
        (EFFECTS-W1 item 6, the dense tier's VSRAM axis) at $0200 — its three brackets sit
        around `OP_RUN_RAMP`'s dispatch entry, ENTER block and per-line body in
        engine/effects/raster.emp, the mechanism `raster_ramp_program` already shipped
        2026-08-14; this bit is the gate that mechanism never got. CAP_ROLE_SWAP landed
        the SAME DAY, on a separate branch (EFFECTS-W1 item 10b, the plane-role swap),
        and independently derived $0200 too — the collision was ruled in item 6's favour
        (landed first) and CAP_ROLE_SWAP took $0400 instead, five sites in
        engine/level/parallax.emp. CAP_PER_LINE was RETIRED
        2026-08-26 (d-29-corrected) when the per-cell HScroll path it selected against was
        deleted — it is parsed as retired, never as declared. This list is the whole
        promotion contract: it is the file that says which bits a span may name."""
        bits = capability_bits()
        self.assertEqual(
            sorted(bits),
            ["CAP_ANCHORS", "CAP_ANCHOR_MOTION", "CAP_BAND_DRIFT", "CAP_DEFORM",
             "CAP_DENSE_TIER", "CAP_FACTOR_CURVE", "CAP_MULTI_DEFORM_TABLE",
             "CAP_PER_COL_VSRAM", "CAP_ROLE_SWAP", "CAP_TRANSITIONS"])
        self.assertEqual(len(set(bits.values())), len(bits),
                         "two capabilities share a bit: %r" % (bits,))
        self.assertEqual(retired_capability_bits(), {"CAP_PER_LINE": 0x0001})
        self.assertNotIn("CAP_PER_LINE", bits,
                         "a retired bit came back as a declaration without its mechanism")

    def test_the_declared_and_retired_bits_are_a_gapless_run_from_bit_zero(self):
        """DERIVED, not copied off the declarations: the mask is allocated one bit at a
        time from bit 0, so N declared-or-retired capabilities must occupy exactly bits
        0..N-1. A retired bit keeps its hole (it is never re-used, so every hand-derived
        mask in the tree keeps meaning what it meant), which is why the run is checked
        over declared ∪ retired rather than declared alone.

        This is what catches the promotion hazard that a name list cannot — promoting a
        reserved bit to `pub const` at the WRONG value (a gap, or a value a still-reserved
        bit already claims in the comment, or a retired bit's hole) leaves the names
        right and the arithmetic wrong, and every downstream mask would be silently off."""
        bits = dict(capability_bits())
        retired = retired_capability_bits()
        self.assertFalse(set(bits) & set(retired), "a bit is both declared and retired")
        self.assertFalse(set(bits.values()) & set(retired.values()),
                         "a declaration re-used a retired bit's hole: %r vs %r"
                         % (bits, retired))
        both = {**bits, **retired}
        self.assertEqual(
            sorted(both.values()), [1 << i for i in range(len(both))],
            "capability bits (declared + retired) are not a gapless run from bit 0 — a "
            "promotion picked a value that leaves a hole or collides with a reserved "
            "bit: %r" % (both,))

    def test_reserved_comment_bits_are_not_parsed_as_declarations(self):
        """The five still-reserved bits live in a comment and have no lowering. A
        bracket naming one would bracket a block that cannot exist, so the parse must
        not see them.

        All four are listed, not a sample: P3/P4 promoted three of the original seven
        (CAP_MULTI_DEFORM_TABLE, CAP_FACTOR_CURVE, CAP_BAND_DRIFT, CAP_ANCHOR_MOTION and
        now CAP_DENSE_TIER — five, not three; the "original seven" is P1's count) and the
        reason the rest stayed is that promoting a bit NOTHING raises is the vacuous-gate
        shape. A partial list here would let the next promotion slip through unchecked."""
        bits = capability_bits()
        for reserved in ("CAP_FG_SPRITE_STRIPS", "CAP_BGANIM_BOUND",
                         "CAP_COMPUTED", "CAP_DEGRADE"):
            self.assertNotIn(
                reserved, bits,
                "%s is parsed as a declared capability but nothing lowers or raises it "
                "— a span gate on it would have no subject" % reserved)


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
        capability name also matches. With today's eight bits it cannot; this fails
        the day a new CAP_ makes it possible, which is when the rule needs revisiting.

        P3 Task 5 is exactly such a day and this check is why it is safe: CAP_DEFORM
        and CAP_MULTI_DEFORM_TABLE are both live, the fill loop already brackets
        `.cap_deform_sample_begin/_end` (parallax.emp:1297/1421), and `deform` is not a
        prefix of `multi_deform_table` in either direction, so no existing span moved.
        Had the new bit been spelled CAP_DEFORM_TABLE it would have, and this fails."""
        lowered = sorted(name[len("CAP_"):].lower() for name in capability_bits())
        for a in lowered:
            for b in lowered:
                if a != b:
                    self.assertFalse(
                        b.startswith(a + "_"),
                        "capability names %r and %r nest, so longest-prefix span "
                        "resolution is ambiguous" % (a, b))

    def test_no_capability_name_is_a_bare_prefix_of_another(self):
        """The check above is scene_spans.span_capability's rule (`_`-delimited). It is
        NOT the rule effects_gates.py:859 uses, which groups spans per capability with a
        bare `s.startswith(cap[len("CAP_"):].lower())` — no separator required. That
        looser resolver has had no test at all, and it is the one the shipped span gate
        runs on.

        A span resolves to two capabilities under the loose rule iff one capability name
        is a bare prefix of another, so this condition — not any property of the span
        names themselves — is the whole of span ambiguity. Checking it here rather than
        enumerating spans is deliberate: an enumeration over today's brackets would pass
        vacuously the moment the bracket set is empty, while this holds over every span
        name that could ever be written."""
        lowered = sorted(name[len("CAP_"):].lower() for name in capability_bits())
        for a in lowered:
            for b in lowered:
                if a != b:
                    self.assertFalse(
                        b.startswith(a),
                        "capability name %r is a bare prefix of %r, so effects_gates.py's "
                        "per-capability span grouping would file the same span under "
                        "both bits" % (a, b))


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
