"""Scene band-count coverage — the record-shape set is a PROPERTY of MAX_PARALLAX_BANDS.

WHAT THIS GATE IS FOR, stated as the defect it was written after:

  games/sonic4/data/effects/scene_registry.emp declared `SceneCfg1/2/4/5` and
  `lower1/2/4/5` — not a decision, just the counts the twenty hand-authored scenes
  happened to use. The engine's own declared maximum lives in
  engine/system/constants.emp (`MAX_PARALLAX_BANDS`, pinned at
  engine/level/scene_dsl.emp:54, enforced by `scene()`), and every count from 1 up to it
  is exactly as reachable as 4 and 5 — the others were just off the hand-authoring path.
  Aurora's first writer-originated scene had EIGHT layers and tools/effects_gen.py
  refused it.

  Adding the missing pairs closes it ONCE. Listing the counts as a literal in a test
  would keep it closed only until the constant moves, and would then go quietly stale —
  which is the same failure one level up. So the required set is DERIVED from the
  constant on every run, and a count with no pair is named in the failure.

  THIS GATE HAS NOW WORKED TWICE, WHICH IS THE POINT OF DERIVING IT. On the 2026-08-27
  ceiling raise (8 -> 16) it named the whole missing set — "declares no record shape for
  band count(s) [9, 10, 11, 12, 13, 14, 15, 16]" — without a line of it being edited.

  DOWNSTREAM, NOT YET MOVED: empyrean's writer schema still mirrors the OLD ceiling as
  `layers minItems 1 / maxItems 8` and Aurora computes its Add-layer cap from that schema
  at load. This gate deliberately does not read the schema — it is another repo's file and
  a cross-repo read here would make an aeon test red for an empyrean edit — so the schema
  lagging is invisible to it. That gap is tracked in docs/DEFERRED_WORK.md.

WHY PYTHON AND NOT AN `.emp` `ensure` IN THE REGISTRY (the alternative considered):

  `scene_registry.emp` can see `MAX_PARALLAX_BANDS` directly, so an `ensure` there looks
  like the closer fit. It cannot express this property. `.emp` has no reflection over
  declared type or function NAMES — an `ensure` cannot ask "does a struct called
  SceneCfg3 exist?". The most it could write is `ensure(MAX_PARALLAX_BANDS == N, ...)`,
  which is a re-pin of a constant scene_dsl.emp already pins and says nothing whatever
  about coverage. That is a gate that cannot see its subject, i.e. exactly the vacuous
  shape docs/DEFERRED_WORK.md's gate history is a record of paying for. A source-level
  reader CAN see the declarations, so the check lives where the evidence is.

  (Instantiating the shapes in `.emp` to force elaboration was the other `.emp` option
  and is worse still: it emits ROM bytes for records no scene uses.)

WHY SOURCE-LEVEL AND NOT `.lst`-LEVEL: build.sh runs `python3 -m pytest tools` BEFORE it
invokes sigil, so a listing-reading test would read the PREVIOUS build's artifact. Same
reasoning as tools/test_scene_span_labels.py — see its banner.

RUNNER: `python3 -m pytest tools` at build.sh:414-416, a BUILD-FATAL lane on every
canonical build (skipped only by FAST=1, which prints a banner saying so). No new runner,
no conftest.py, no pytest.ini.

PROVEN RED: deleting `pub struct SceneCfg7` from the registry fails
test_every_admissible_band_count_has_a_record_shape with
`scene_registry.emp declares no record shape for band count(s) 7 ...`; deleting
`pub comptime fn lower7` fails the lowering twin the same way. Restored after.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from effects_budget_check import emp_constants, eval_int_expr  # noqa: E402
import effects_gen  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))

CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")
SCENE_DSL_EMP = os.path.join(REPO, "engine", "level", "scene_dsl.emp")
REGISTRY_EMP = os.path.join(REPO, "games", "sonic4", "data", "effects",
                            "scene_registry.emp")

# `pub` is part of the match on purpose: a non-`pub` shape is invisible to the generated
# editor module that imports it, so a shape that exists but is private is NOT coverage.
SHAPE_RE = re.compile(r"^\s*pub\s+struct\s+SceneCfg(\d+)\b", re.M)
LOWER_RE = re.compile(r"^\s*pub\s+comptime\s+fn\s+lower(\d+)\s*\(", re.M)
# The pin scene_dsl.emp carries for its own inlined ceiling (EMP_PITFALLS §2: a comptime
# fn's free names resolve at the call site, so the DSL bodies spell `8` and hold it with
# this ensure rather than naming the constant).
DSL_PIN_RE = re.compile(r"ensure\(\s*MAX_PARALLAX_BANDS\s*==\s*(\d+)\s*,")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def max_parallax_bands():
    """The engine constant, read from its declaring file. THE authority here."""
    consts = emp_constants(CONSTANTS_EMP)
    if "MAX_PARALLAX_BANDS" not in consts:
        raise AssertionError(
            "MAX_PARALLAX_BANDS is not declared in %s — every derivation in this file "
            "would silently resolve against nothing, so this is a hard failure rather "
            "than a skip. If the constant moved file, move this reader with it."
            % CONSTANTS_EMP)
    return eval_int_expr(consts["MAX_PARALLAX_BANDS"], consts)


def admissible_band_counts():
    """1..MAX_PARALLAX_BANDS — every count `scene()` will build and Aurora can author.

    The low end is 1 and not 0 because effects_gen refuses an empty `layers` outright
    and the writer schema says `minItems: 1`.
    """
    return tuple(range(1, max_parallax_bands() + 1))


def declared_shapes():
    return {int(m) for m in SHAPE_RE.findall(_read(REGISTRY_EMP))}


def declared_lowerings():
    return {int(m) for m in LOWER_RE.findall(_read(REGISTRY_EMP))}


class TestTheReaderItself(unittest.TestCase):
    """A floor under the derivations: an empty parse and a closed gate look identical."""

    def test_the_engine_constant_reads_as_a_positive_integer(self):
        n = max_parallax_bands()
        self.assertIsInstance(n, int)
        self.assertGreater(n, 0, "MAX_PARALLAX_BANDS read as %r" % (n,))

    def test_the_registry_parse_finds_shapes_and_lowerings_at_all(self):
        """If either regex stops matching (the file re-spells its declarations, or the
        path moves), every coverage assertion below would pass against an empty set
        — green for the wrong reason. Anchor both."""
        self.assertTrue(declared_shapes(),
                        "no `pub struct SceneCfgN` matched in %s" % REGISTRY_EMP)
        self.assertTrue(declared_lowerings(),
                        "no `pub comptime fn lowerN` matched in %s" % REGISTRY_EMP)


class TestBandCountCoverage(unittest.TestCase):

    def test_every_admissible_band_count_has_a_record_shape(self):
        want = set(admissible_band_counts())
        missing = sorted(want - declared_shapes())
        self.assertFalse(missing, (
            "%s declares no record shape for band count(s) %s. MAX_PARALLAX_BANDS is %d "
            "(%s), so `scene()` admits 1..%d and Aurora's editor lets an author produce "
            "any of them — a count with no `pub struct SceneCfgN` is a scene the writer "
            "can author and the tree cannot lower. Add the pair (a struct line and a "
            "`lowerN` with N `scene_band` terms), `pub` like the others; never a second "
            "lowering in generated code."
            % (os.path.relpath(REGISTRY_EMP, REPO), missing, max_parallax_bands(),
               os.path.relpath(CONSTANTS_EMP, REPO), max_parallax_bands())))

    def test_every_admissible_band_count_has_a_lowering(self):
        want = set(admissible_band_counts())
        missing = sorted(want - declared_lowerings())
        self.assertFalse(missing, (
            "%s declares no `pub comptime fn lowerN` for band count(s) %s. The struct "
            "alone is not coverage: the generated editor module emits "
            "`pub data ...: SceneCfgN = lowerN(...)`, so a shape without its lowering "
            "fails at link with an unknown function."
            % (os.path.relpath(REGISTRY_EMP, REPO), missing)))

    def test_shapes_and_lowerings_are_declared_in_matching_pairs(self):
        """The two halves are only useful together, in both directions — an orphan
        `SceneCfgN` or `lowerN` is dead weight that reads as coverage."""
        self.assertEqual(sorted(declared_shapes()), sorted(declared_lowerings()),
                         "SceneCfgN set and lowerN set differ in %s"
                         % os.path.relpath(REGISTRY_EMP, REPO))

    def test_no_shape_exceeds_the_engine_ceiling(self):
        """The other direction, and the reason an anchored 8-band scene is NOT a case
        for one shape PAST the ceiling: an anchored scene SPLITS a layer at runtime and so needs
        count+1 shadow entries (scene_dsl.emp:1062). `Parallax_Shadow_Bands` is sized
        for MAX_PARALLAX_BANDS entries, so that refusal is a real engine limit. A
        `SceneCfg9` added to route around it would emit a record the shadow view cannot
        hold."""
        n = max_parallax_bands()
        over = sorted(c for c in declared_shapes() | declared_lowerings() if c > n)
        self.assertFalse(over, (
            "%s declares band count(s) %s above MAX_PARALLAX_BANDS (%d). `scene()` "
            "refuses those, so nothing can reach the shape; if this was added to work "
            "around the ANCHORED count+1 refusal, that is a shadow-view capacity limit "
            "and the record would not fit."
            % (os.path.relpath(REGISTRY_EMP, REPO), over, n)))


class TestTheGeneratorMirrorsTheEngine(unittest.TestCase):
    """tools/effects_gen.py carries its own copy of the ceiling. Nothing compared the
    two before this parcel, so it could drift from the engine in either direction and
    the only symptom would be a wrongly refused (or wrongly accepted) writer scene."""

    def test_the_generators_ceiling_equals_the_engine_constant(self):
        self.assertEqual(
            effects_gen.MAX_PARALLAX_BANDS, max_parallax_bands(),
            "tools/effects_gen.py MAX_PARALLAX_BANDS=%d but %s says %d"
            % (effects_gen.MAX_PARALLAX_BANDS,
               os.path.relpath(CONSTANTS_EMP, REPO), max_parallax_bands()))

    def test_the_generator_will_lower_every_admissible_count(self):
        """Derived on both sides — the generator's set is `range(1, MAX+1)`, this
        rebuilds it from the engine file. A generator that refuses a count the registry
        has a shape for is the original defect wearing the opposite face."""
        self.assertEqual(tuple(effects_gen.LOWERABLE_BAND_COUNTS),
                         admissible_band_counts())

    def test_the_generator_only_names_shapes_the_registry_declares(self):
        """Every count the generator would emit a `lowerN(` call for must exist in the
        registry — this is the join that makes a green `effects_gen emit` mean the
        module will actually link."""
        unbacked = sorted(set(effects_gen.LOWERABLE_BAND_COUNTS)
                          - (declared_shapes() & declared_lowerings()))
        self.assertFalse(unbacked, (
            "effects_gen would emit SceneCfgN/lowerN for band count(s) %s that %s does "
            "not declare — a green emit followed by a link failure."
            % (unbacked, os.path.relpath(REGISTRY_EMP, REPO))))


class TestTheDslPinAgrees(unittest.TestCase):

    def test_scene_dsls_inlined_ceiling_pin_names_the_same_number(self):
        """scene_dsl.emp spells its ceiling as an INLINED LITERAL in comptime bodies (it
        has to — EMP_PITFALLS §2) and holds it with a module-level `ensure`. If that pin ever
        disagreed with the constant the DSL would cap at one number while everything
        derived here used another."""
        m = DSL_PIN_RE.search(_read(SCENE_DSL_EMP))
        self.assertIsNotNone(
            m, "no `ensure(MAX_PARALLAX_BANDS == N, ...)` pin found in %s — the DSL's "
               "inlined ceiling would be unpinned" % os.path.relpath(SCENE_DSL_EMP, REPO))
        self.assertEqual(int(m.group(1)), max_parallax_bands())


if __name__ == "__main__":
    unittest.main()
