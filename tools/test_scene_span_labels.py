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

  So the `.lst` half of the convention lives in `tools/effects_gates.py` (Task 9),
  which runs AFTER a build and against the two fixtures it needs. This file owns the
  half that is a property of the SOURCE and is therefore checkable at any time: every
  bracket is paired, every bracket names a real capability, and (from Task 7 on) every
  capability-gated block carries a pair.

EXPECTATIONS ARE DERIVED, NEVER COPIED. The capability set comes from
engine/level/scene_dsl.emp's own `pub const CAP_*` declarations — the model's sole
authority. Adding a bit there and bracketing against it needs no edit here; naming a
bracket after a bit that does not exist fails.
"""

import os
import re
import unittest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENE_DSL = os.path.join(AEON, "engine", "level", "scene_dsl.emp")

# `pub const CAP_PER_LINE       = $0001` — declaration lines only. The reserved-bit
# COMMENT block a few lines below (`CAP_MULTI_DEFORM_TABLE=$0020, ...`) deliberately
# does not match: those bits have no lowering yet, so a bracket naming one would be
# bracketing a block that cannot exist.
CAP_DECL_RE = re.compile(r"^pub const (CAP_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)\s*$", re.M)

# A capability-gated block opens with the mask test. The engine spells it exactly one
# way on purpose (`if (Game.SCANLINE_CAPS & CAP_X) != 0 {`) so this scan cannot be
# defeated by a re-spelling that still gates.
GATE_RE = re.compile(r"if\s*\(\s*Game\.SCANLINE_CAPS\s*&\s*(CAP_[A-Z0-9_]+)\s*\)\s*!=\s*0\s*\{")

# `.cap_anchors_overlay_begin:` — the label as authored in `.emp`.
LABEL_RE = re.compile(r"^\s*\.cap_([a-z0-9_]+)_(begin|end):", re.M)

# Every engine module that may carry a gated block. Kept as a directory walk rather
# than a file list so a new gated module cannot escape by not being listed.
ENGINE = os.path.join(AEON, "engine")


def capability_bits():
    """The CAP_* authority, parsed from scene_dsl.emp. Never a copy of the mask."""
    with open(SCENE_DSL, encoding="utf-8") as f:
        src = f.read()
    bits = {m.group(1): int(m.group(2), 16) for m in CAP_DECL_RE.finditer(src)}
    if not bits:
        raise AssertionError(
            "no `pub const CAP_*` declarations found in %s — the capability authority "
            "moved or was re-spelled, and every derivation in this file (and in "
            "effects_gates.py) reads it from here. Fix the parse, do not hard-code the "
            "bits." % SCENE_DSL)
    return bits


def span_capability(span, bits):
    """Resolve a bracket's span name to its capability by LONGEST matching prefix.

    Bracket names are `cap_<capability>_<site>`: one capability can be gated at
    several sites, and two labels of the same name in one proc is a redefinition, so
    the site token is what keeps them distinct. `per_line_fill` -> CAP_PER_LINE,
    `per_col_vsram_emit` -> CAP_PER_COL_VSRAM. Longest-prefix (not first-match)
    because a shorter capability name could otherwise shadow a longer one.
    """
    lowered = {name[len("CAP_"):].lower(): name for name in bits}
    hits = [low for low in lowered
            if span == low or span.startswith(low + "_")]
    if not hits:
        return None
    return lowered[max(hits, key=len)]


def emp_sources():
    for dirpath, dirnames, filenames in os.walk(ENGINE):
        dirnames[:] = [d for d in dirnames if d not in (".git", "generated")]
        for name in sorted(filenames):
            if name.endswith(".emp"):
                yield os.path.join(dirpath, name)


def _block_end(src, open_brace):
    """Index just past the `}` closing the brace at `open_brace`.

    Brace-counting over `.emp` is honest here because the gated regions are plain
    instruction blocks: no string literals carrying braces occur inside them, and
    `ensure`/`raise_error` messages (which do carry `{name}` interpolations) are
    counted symmetrically, so they cannot desync the depth.
    """
    depth = 0
    i = open_brace
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise AssertionError("unbalanced braces after offset %d" % open_brace)


def gated_blocks():
    """(path, capability, block_source) for every `Game.SCANLINE_CAPS` gate."""
    out = []
    for path in emp_sources():
        with open(path, encoding="utf-8") as f:
            src = f.read()
        for m in GATE_RE.finditer(src):
            brace = src.index("{", m.start())
            end = _block_end(src, brace)
            out.append((path, m.group(1), src[brace:end + 1]))
    return out


def brackets():
    """(path, span, kind) for every bracketing label in the engine tree."""
    out = []
    for path in emp_sources():
        with open(path, encoding="utf-8") as f:
            src = f.read()
        for m in LABEL_RE.finditer(src):
            out.append((path, m.group(1), m.group(2)))
    return out


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
        for path, span, kind in brackets():
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
        for path, span, kind in brackets():
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


if __name__ == "__main__":
    unittest.main()
