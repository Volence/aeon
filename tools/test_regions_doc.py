#!/usr/bin/env python3
"""Tests for the regions seam — `effects_gen.load_act_regions` + `region_flatten`.

THE ONE THAT MATTERS is `TestSharedGolden`: the golden document flattens to act 1's ten
shipped rows, exactly, row for row. The expected rows were typed by hand out of
`act_descriptor.emp` and NOT produced by the flattener, so the comparison is not circular;
if the two ever disagree the finding is which of them is wrong, and that outranks a green.

RUNNER: `build.sh`'s pre-build tool-suite lane (`python3 -m pytest tools -m "not
needs_build"`), build-fatal in every canonical shape. Everything here reads source and
fixtures only — no ROM, no emulator, no assembler — except `TestShippedTableMatchesGolden`,
which carries the `needs_build` marker and compares the golden against the table read out of
a BUILT ROM.

⚠ ACT 1 IS IN REGION MODE (2026-09-16, REGIONS-EMIT-BINDINGS). The three bullets that stood
here said the opposite — "nothing has assembled the emitted text", "act 1's rows are still
hand-written", "no act in this repo has a `regions.json`" — and all three are now false. The
act's identity IS `games/sonic4/data/editor/ojz/act1/regions.json`, its rows are lowered into
`games/sonic4/data/generated/ojz/act1/regions.emp`, and both build shapes assemble that file.
The flip moved zero ROM bytes.

WHAT A GREEN HERE DOES NOT MEAN, said so nobody reads it as more:
  * ⚠ THESE TESTS READ TEXT, NOT BYTES, and the first assembly proved that gap is real: the
    emitter's rows were five-field struct literals, every test here was green, and sigil
    answered with 150 `[struct.missing-field]` errors. That the text ASSEMBLES is the build's
    verdict; that the ROM's rows are the golden's rows is `TestShippedTableMatchesGolden`'s,
    which reads the image.
  * The LEGACY arm is still live and is still the default — `games/demo` and every unmigrated
    act take it. It is exercised in a sandbox with the document removed, which is what a
    legacy act IS; `TestRealTreeIsInRegionMode` pins which arm the shipped tree takes, so a
    sandbox test cannot quietly become the only thing describing this repo.
  * Every region-mode test below still builds its own sandbox and writes its own document.
    `RegionSandbox.setUp` REMOVES the copied `regions.json` for that reason: without it every
    sandbox arrived carrying act 1's real document and the legacy-mode assertions were being
    made against a tree that was already in region mode.
  * `bg.layoutRef` is refused for every value but the act sentinel, so the derived-span
    check (a span must equal its layout's height) is UNREACHABLE today and untested. It is
    what the parcel that opens `layoutRef` owes.
  * THE GOLDEN'S `bg` PAIR IS THE DEFAULT HALF ONLY (2026-09-16). Every row's background is
    the act's, so `TestSharedGolden` pins the one fact the seam can check while that is
    true — that `bg` absent, `bg.layoutRef` null and `bg.layoutRef` `"@act"` all flatten to
    the SAME row — and pins NOTHING about a region that names its own layout. That half is
    blocked (REGIONS-BG-GOLDEN-GAP); `TestBackgroundBinding`'s tripwire is what stops it
    from being forgotten, by failing the day the refusal above is lifted.

RED-FIRST. Every refusal test below was written by taking the golden — a document that
passes — and perturbing exactly one thing, which is the discipline `test_effects_gen.py`
uses for scenes. The two that are easy to get wrong for a reason worth naming:
  * `test_uncovered_can_actually_find_a_hole` exists because `uncovered()` returning `[]`
    is what a correct document produces AND what a broken instrument produces. It punches a
    hole and requires the list to name it.
  * `test_right_edge_rule_is_not_the_left_rule_mirrored` sits the edge precisely ON a band
    endpoint, because the naive transcription of the right-edge rule disagrees with the
    engine on exactly two edges in this act and passes every test that lands anywhere else.
"""

import copy
import glob
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import effects_gen                                              # noqa: E402
import region_flatten                                           # noqa: E402

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(AEON, "tools", "fixtures", "regions")
GOLDEN_DOC = os.path.join(FIXTURES, "ojz_act1.regions.json")
GOLDEN_ROWS = os.path.join(FIXTURES, "ojz_act1.rows.json")
# The emitter's own golden: the `.emp` module the BINDING-FREE golden document lowers to.
# Committed so a header caveat, a `_ROW_*` constant or a row cannot go missing without a
# diff to review.
#
# ⚠ THE `.emp.txt` SUFFIX IS LOAD-BEARING AND WAS MEASURED, NOT CHOSEN FOR TIDINESS.
# `sigil build` PARSES EVERY `.emp` IN THE TREE, wherever it sits — this fixture is never
# emitted, never placed and never imported, and while it was named `.emp` it took the plain
# demo build to exit 1 (`error: file must start with a `module` declaration`) and 50 tests
# in test_artifact_provenance.py / test_provenance_consumers.py down with it. A test
# fixture that is legal `.emp` would be worse, not better: it would be silently compiled
# into every build. Keep the suffix.
GOLDEN_EMP = os.path.join(FIXTURES, "ojz_act1.regions.emp.txt")
ACT1_DESCRIPTOR = "games/sonic4/data/levels/ojz/act1/act_descriptor.emp"
ACT1_EDITOR = "games/sonic4/data/editor/ojz/act1"

# The shared vocabulary the golden pins. NOT `.emp` symbol names: both repos have to be able
# to check these, and aurora cannot resolve an EditorSceneBinding_* label.
ROW_KEYS = ("index", "id", "x0", "x1", "y0", "y1", "preset", "sceneRef", "rasterRef", "bg")

# Row 9's id, ruled rather than chosen: a KEY-LESS row's id is its `preset` symbol lowercased
# (empyrean `a718ea7c`, `docs/AURORA_REGIONS_SCHEMA.md`). Named once here so a test that looks
# the row up and a test that requires a refusal to NAME it cannot drift apart — and so the
# `assertIn` near-miss at `test_an_overlap_is_refused_and_names_both_regions` has one place to
# be fixed rather than two.
NIGHT_ID = "ojz_preset_night"

# Everything the sandbox borrows from the real tree by SYMLINK rather than copy: the effects
# library, the scene and preset libraries, the descriptor whose `const` lines are the rules,
# and the engine constants they fold against. Only the act's editor directory is a real copy,
# because that is the one the tests mutate.
SANDBOX_LINKS = ("project.json", "engine", "games/sonic4/config",
                 "games/sonic4/data/effects", "games/sonic4/data/editor/effects",
                 "games/sonic4/data/levels",
                 # The GENERATED act grid the descriptor's `const GRID_W` folds against
                 # since S2-COMPRESSED-ACT parcel 9. Without it every bound in
                 # region_flatten.BOUND_NAMES goes unfoldable and act_bounds refuses.
                 "games/sonic4/data/generated/ojz/act1/act_grid.emp")


def golden_doc() -> dict:
    with open(GOLDEN_DOC) as f:
        return json.load(f)


def golden_rows() -> list:
    with open(GOLDEN_ROWS) as f:
        return json.load(f)["rows"]


class RegionSandbox(unittest.TestCase):
    """A repo whose act 1 is in REGION mode, built fresh per test.

    The real tree is in LEGACY mode and must stay there — that is what keeps this parcel
    reversible — so every region-mode assertion needs a tree of its own. Symlinks for the
    read-only libraries keep it to one directory copy.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = self.tmpdir.name
        for rel in SANDBOX_LINKS:
            dst = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.symlink(os.path.join(AEON, rel), dst)
        self.act_dir = os.path.join(self.repo, ACT1_EDITOR)
        shutil.copytree(os.path.join(AEON, ACT1_EDITOR), self.act_dir)
        # Region mode means the sidecars carry no identity. Removing them is what
        # `Migrate sections` does on the document store; a test that left them would be
        # testing the mode conflict instead of whatever it meant to test.
        for f in glob.glob(os.path.join(self.act_dir, "section_*.meta.json")):
            os.remove(f)
        # ⚠ AND THE SHIPPED DOCUMENT IS REMOVED TOO, SINCE THE FLIP (2026-09-16). The act
        # directory is COPIED from the real tree, and the real tree now carries a
        # `regions.json` — so every sandbox arrived pre-populated with act 1's real document
        # and the tests that write their own were editing on top of it. Worse, the tests that
        # assert LEGACY mode (`has_act_regions()` false) were asserting against a tree that
        # was in region mode before they touched it. Each test writes the document it means
        # to test, or writes none; the sandbox supplies neither.
        doc = os.path.join(self.act_dir, effects_gen.REGIONS_FILE)
        if os.path.isfile(doc):
            os.remove(doc)

    def tearDown(self):
        self.tmpdir.cleanup()

    def write_doc(self, doc):
        with open(os.path.join(self.act_dir, "regions.json"), "w") as f:
            json.dump(doc, f, sort_keys=True, indent=2)
            f.write("\n")

    def rows(self, doc=None, resolve=True):
        self.write_doc(golden_doc() if doc is None else doc)
        return effects_gen.act_region_rows(repo=self.repo, resolve=resolve)

    def refuses(self, doc, *fragments, resolve=True):
        """Assert the document is refused AND that the message names each fragment.

        A gate whose verdict is right and whose stated reason is wrong is worse than a
        failing gate: the reason is what the author carries to the file they have to edit.
        """
        self.write_doc(doc)
        with self.assertRaises(effects_gen.SceneShapeError) as cm:
            effects_gen.act_region_rows(repo=self.repo, resolve=resolve)
        msg = str(cm.exception)
        for frag in fragments:
            self.assertIn(frag, msg, f"refusal did not name {frag!r}:\n{msg}")
        return msg


# ---------------------------------------------------------------------------
# THE ACCEPTANCE TEST
# ---------------------------------------------------------------------------

class TestSharedGolden(RegionSandbox):
    def test_the_golden_flattens_to_act_ones_ten_rows_exactly(self):
        """The whole parcel in one assertion (spec §5.4).

        Ten regions in, ten rows out, every field equal to the hand transcription of
        `OJZ_ACT1_REGION_ROWS`. A disagreement here is a FINDING about which side is
        wrong, never a reason to adjust the flattener toward the table.
        """
        rows = self.rows()
        want = golden_rows()
        self.assertEqual(len(rows), 10, "act 1 ships ten release rows")
        self.assertEqual([{k: r[k] for k in ROW_KEYS} for r in rows], want)

    def test_area_and_disjointness_are_the_engines_own_two_numbers(self):
        """`region_area_sum` and `region_first_overlap` restated, over the golden."""
        rows = self.rows()
        bounds = region_flatten.act_bounds(ACT1_DESCRIPTOR)
        self.assertEqual(region_flatten.area_of_rows(rows),
                         bounds["ACT_W"] * bounds["ACT_H"])
        rects = [(r["x0"], r["y0"], r["x1"] - r["x0"] + 1, r["y1"] - r["y0"] + 1)
                 for r in rows]
        self.assertIsNone(region_flatten.first_overlap(rects))
        self.assertEqual(region_flatten.uncovered(rects, bounds["ACT_W"], bounds["ACT_H"]), [])

    def test_the_night_region_straddles_the_section_line(self):
        """The case a naive fixture would miss, asserted as a property of the fixture.

        If someone "tidies" the golden onto the section grid, every other test here still
        passes and the fixture silently stops exercising the thing it exists for.
        """
        night = next(r for r in self.rows() if r["id"] == NIGHT_ID)
        section = 1 << 11
        self.assertLess(night["x0"], 2 * section)
        self.assertGreaterEqual(night["x1"], 2 * section)
        self.assertNotEqual(night["x0"] % section, 0)
        self.assertNotEqual((night["x1"] + 1) % section, 0)

    def test_the_key_less_rows_id_is_its_preset_symbol_lowercased(self):
        """The hub's id ruling, asserted with the expectation DERIVED from the document.

        Ruled 2026-09-16T10:5xZ, empyrean `a718ea7c`, `docs/AURORA_REGIONS_SCHEMA.md`, "A
        KEY-LESS ROW'S ID IS ITS PRESET SYMBOL, LOWERCASED". Rows 0-8 are keyed to sections
        and keep `sec0`..`sec8`; row 9 is key-less, so its id is minted from its preset.

        THE EXPECTATION IS COMPUTED FROM THE ROW'S OWN `preset` FIELD, never typed beside it.
        Typing `ojz_preset_night` on both sides would pass against a fixture where somebody
        had changed the preset and forgotten the id, which is precisely the drift the ruling
        names as its own accepted cost (a rename leaves the id bound to another preset) and
        so the one thing worth pinning at the moment of writing.

        AEON DOES NOT IMPLEMENT THE SANITISATION and this test is not a place to start: the
        minting is Aurora's migration's, written once, and a second implementation here is a
        drift source rather than a check. The row's preset carries no character outside
        `[a-z0-9_]` once lowercased, so `.lower()` IS the rule for this input and the parts
        of it that do not bite (the fold, the strip, the truncation) are deliberately
        untested here rather than half-reimplemented.
        """
        night = next(r for r in golden_rows() if r["id"] == NIGHT_ID)
        self.assertEqual(night["id"], night["preset"].lower())
        self.assertTrue(len(night["id"]) <= 32, "the schema pattern caps an id at 32")
        # And the label the ruling makes a CONDITION of itself: the ugly id is only
        # acceptable because nothing legible is lost.
        doc_region = next(r for r in golden_doc()["regions"] if r["id"] == NIGHT_ID)
        self.assertEqual(doc_region["name"], "Night")

    def test_the_golden_document_and_rows_files_agree_on_their_act(self):
        with open(GOLDEN_ROWS) as f:
            rows_doc = json.load(f)
        self.assertEqual(rows_doc["act"], golden_doc()["act"])
        self.assertEqual(len(rows_doc["rows"]), len(golden_doc()["regions"]))


# ---------------------------------------------------------------------------
# MODE
# ---------------------------------------------------------------------------

class TestTheSectionLookProbeAgreesWithTheLegacyAnswER(unittest.TestCase):
    """`section_preset_symbols`' REGION arm reproduces what the LEGACY arm used to say.

    THE HINGE THE FLIP TURNED ON. Seven tools ask "what look is at section N" — the seam gate,
    the anchor-sweep band file, `sec5_band_witness`, `lens_residue_raster_witness`, the
    reachability lint, and the generator's own B′ re-key. Region mode DELETED the edge those
    tools were reading (regions part 1 step 4 removed section identity on purpose), so the
    region arm answers the same question GEOMETRICALLY instead: which region's rectangle
    contains the section's centre.

    ⚠ IT IS NOT A BINDING AND MUST NOT BE READ AS ONE. A section can straddle several regions
    and several sections can share one; what makes the probe legitimate is that the engine
    resolves identity by camera CENTRE per frame, and this samples that same rule once per
    section. What makes it SAFE is that it yields no entry when a section's centre is not in
    exactly one region, and every consumer treats a missing entry as "not evaluated".

    THE AGREEMENT IS ASSERTED AND NOT ASSUMED, row for row, because "it happens to match
    today" is the kind of sentence that decays without an author. The LEGACY expectation is
    read with `section_preset_symbols_legacy` against the descriptor AS IT WAS BEFORE THE FLIP
    — out of git, at the parcel's base — so this is a comparison against a real historical
    answer and not against the same function agreeing with itself.
    """

    BASE = "a7b1cd2e"          # the parcel's base: act 1 still hand-written, still legacy

    def test_every_section_resolves_to_the_record_the_hand_table_bound_it_to(self):
        import subprocess
        if not effects_gen.has_act_regions():
            self.skipTest("act 1 is in legacy mode; the two arms are the same code path")
        rel = "games/sonic4/data/levels/ojz/act1/act_descriptor.emp"
        p = subprocess.run(["git", "-C", AEON, "show", f"{self.BASE}:{rel}"],
                           capture_output=True, text=True)
        if p.returncode != 0:
            self.skipTest(f"{self.BASE} is not in this repository (a shallow clone or a "
                          f"rewritten history) — this comparison needs the pre-flip "
                          f"descriptor and will not invent one")
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "act_descriptor.emp")
            with open(old, "w") as f:
                f.write(p.stdout)

            class _At:
                def descriptor_path(self, _repo):
                    return old
            legacy = effects_gen.section_preset_symbols_legacy(_At())
        self.assertEqual(len(legacy), effects_gen.act_section_count(),
                         f"the pre-flip descriptor at {self.BASE} resolved {len(legacy)} "
                         f"sections, not this act's {effects_gen.act_section_count()} — the "
                         f"baseline this compares against is itself unreadable, so a match "
                         f"would mean nothing")
        region = effects_gen.section_preset_symbols(effects_gen.act_names())
        self.assertEqual(region, legacy,
                         "the region arm's section -> record map is not the one act 1's "
                         "hand-written table bound. The FINDING is which of them the "
                         "consumers wanted, not which to adjust: seven tools read this edge.")


class TestRealTreeIsInRegionMode(unittest.TestCase):
    """⚠ WAS `TestLegacyModeUnchanged`, AND THE RENAME IS THE FLIP (2026-09-16).

    It read "the arm the real tree takes, and the one that makes this parcel reversible", and
    asserted `has_act_regions()` FALSE. Act 1 now has a document, so that assertion is exactly
    backwards — and it is renamed rather than deleted because the fact it pinned still matters
    and has simply changed sign: this suite must know which mode the shipped tree is in, or
    every sandbox below is testing a path nothing takes.

    THE LEGACY ARM IS NOT LEFT UNTESTED. It is the arm `games/demo` and every unmigrated act
    take, and `TestRegionTableEmitter::test_legacy_mode_emits_nothing_and_that_is_not_an_error`
    exercises it in a sandbox with the document removed, which is what a legacy act IS.
    Reversibility is likewise unchanged and is still one `rm`: delete the document and the
    generator takes the same code path it took before regions existed.
    """

    def test_the_shipped_act_is_in_region_mode_and_its_rows_come_from_the_document(self):
        self.assertTrue(effects_gen.has_act_regions(),
                        "act 1 has no regions.json — the flip is not in this tree, and every "
                        "region-mode assertion in this file is about a path nothing takes")
        doc = effects_gen.load_act_regions()
        self.assertIsNotNone(doc)
        rows = effects_gen.act_region_rows()
        self.assertEqual([r["id"] for r in rows], [r["id"] for r in golden_rows()],
                         "the shipped act's rows are not the shared golden's rows, in order")

    def test_no_section_sidecar_still_carries_identity(self):
        """The other half of the flip, and the half that would fail SILENTLY.

        `check_mode_conflict` refuses a tree where both sources carry identity — but it is a
        REFUSAL, so it only speaks when it fires. This asserts the state it defends, so a
        merge or a half-applied editor save that re-added a `sceneRef` is a named test failure
        rather than a build error whose message is about something else.
        """
        for key in (effects_gen.ACT_SCENE_REF_KEY, effects_gen.ACT_RASTER_REF_KEY):
            self.assertEqual(effects_gen._load_section_refs(key), {},
                             f"a section sidecar still carries {key} while act 1 is in "
                             f"region mode — two sources of truth for one fact")

    def test_generate_is_byte_identical_to_the_committed_module(self):
        """The regions code changed `generate()`; this proves it changed no output.

        `effects_scenes.emp` is a committed artifact with its own drift gate, so a byte
        difference here would be the build failing later with a less informative message.
        """
        path, text = effects_gen.generate()
        with open(path) as f:
            self.assertEqual(text, f.read())


class TestModeConflict(RegionSandbox):
    def test_a_sidecar_carrying_a_sceneRef_beside_a_document_is_refused(self):
        self.write_doc(golden_doc())
        with open(os.path.join(self.act_dir, "section_3.meta.json"), "w") as f:
            json.dump({"sceneRef": "ojz_act1_start"}, f)
        with self.assertRaises(effects_gen.SceneShapeError) as cm:
            effects_gen.generate(repo=self.repo)
        msg = str(cm.exception)
        self.assertIn("section_3.meta.json", msg)
        self.assertIn("sceneRef", msg)
        self.assertIn("Migrate sections", msg)

    def test_a_sidecar_carrying_a_rasterRef_beside_a_document_is_refused(self):
        self.write_doc(golden_doc())
        with open(os.path.join(self.act_dir, "section_5.meta.json"), "w") as f:
            json.dump({"rasterRef": "ojz_sec5_showcase"}, f)
        with self.assertRaises(effects_gen.SceneShapeError) as cm:
            effects_gen.generate(repo=self.repo)
        self.assertIn("rasterRef", str(cm.exception))

    def test_an_all_null_sidecar_beside_a_document_is_fine(self):
        """The state `Migrate sections` leaves behind. Aurora's save plan overwrites a
        sidecar with an all-null tuple rather than deleting it, so this IS the migrated
        tree and refusing it would refuse every migration.

        ⚠ THIS ASSERTS `check_mode_conflict` AND NOT `generate()`, AND THE REASON IS A
        FINDING THIS SANDBOX TURNED UP RATHER THAN A CONVENIENCE. A migrated act 1 — every
        sidecar `sceneRef` nulled — does not bake at all today, and the refusal has nothing
        to do with regions: `ojz_act1_depth.json` carries a `reels` key, and
        `render_module`'s rung-1 rule requires some SECTION to bind that scene through a
        `sceneRef` sidecar, because the reels table is keyed on the pointer identity of
        `EditorSceneBinding_OJZ_Act1_Sec4`. With identity moved to regions there is no such
        sidecar and the rule refuses the whole bake. Measured here, not predicted. It is a
        real blocker for flipping act 1 into region mode and it is booked in
        docs/DEFERRED_WORK.md under REGIONS-GOLDEN-GAP; narrowing this assertion to hide it
        would have been the thing this parcel exists to stop doing."""
        self.write_doc(golden_doc())
        with open(os.path.join(self.act_dir, "section_5.meta.json"), "w") as f:
            json.dump({"bgLayoutRef": None, "paletteRef": None,
                       "rasterRef": None, "sceneRef": None}, f)
        effects_gen.check_mode_conflict(repo=self.repo)   # no raise

    def test_a_migrated_act_BAKES_and_keeps_every_binding_the_document_names(self):
        """⚠ THIS TEST TOLD ITS AUTHOR TO DELETE IT, AND THIS IS WHAT REPLACED IT INSTEAD.

        It was `test_a_migrated_act_does_not_bake_yet_and_the_reason_is_reels`, and it
        asserted a REFUSAL: a migrated act would not bake, because `render_module`'s rung-1
        reels rule requires some SECTION to bind `ojz_act1_depth` through a sidecar, and a
        migrated act has no sidecars. Its docstring said "the day the re-key lands, THIS test
        fails and tells its author to delete it — rather than the tree quietly gaining a
        capability nobody recorded". The re-key is REGIONS-EMIT-BINDINGS and it has landed.

        DELETING IT OUTRIGHT WOULD HAVE THROWN AWAY THE MEASUREMENT THAT MADE IT WORTH
        WRITING. The refusal was never about reels; it was the last thing standing between a
        migrated act and a GREEN BUILD OF A SILENTLY DE-BOUND ROM — measured in this same
        sandbox at `docs/superpowers/notes/2026-09-16-regions-emit.md` §1.2: drop the rule
        alone and the bake succeeds with FOUR scene bindings and FOURTEEN chooser arms gone to
        zero. So the successor asserts the thing the refusal was protecting: a migrated act
        bakes AND keeps every binding its document names. A tree that relaxed the rule without
        doing the re-key passes the old test's deletion and fails this one.
        """
        self.write_doc(golden_doc())
        _path, text = effects_gen.generate(repo=self.repo)
        doc = golden_doc()

        # (1) EVERY `sceneRef` IN THE DOCUMENT REACHES A LOWERED BINDING RECORD. Derived from
        # the document, never typed: the count that made the old measurement frightening was
        # four, and four is what this reads out of the golden rather than what it asserts.
        names = effects_gen.act_names(repo=self.repo)
        want = [r["id"] for r in doc["regions"]
                if r.get(effects_gen.ACT_SCENE_REF_KEY) is not None]
        self.assertTrue(want, "the golden binds no scene at all, so this test would pass "
                              "against a generator that emits nothing")
        for rid in want:
            self.assertIn(f"pub data {names.binding_region(rid)}: ", text,
                          f"region {rid!r} names a {effects_gen.ACT_SCENE_REF_KEY} and the "
                          f"generated module lowers no binding record for it")

        # (2) THE REELS TABLE IS STILL KEYED ON ONE OF THEM. `ojz_act1_depth` carries the
        # `reels` key and it is the region `sec4` that binds it; the association table pairs
        # that binding's ADDRESS with the reel rates, so the rung-1 rule is satisfied by a
        # REGION now instead of by a sidecar. This is the exact sentence the old refusal said
        # could not be true.
        self.assertIn(f'extern("{names.binding_region("sec4")}")', text)

        # (3) THE CHOOSER ARMS SURVIVED. Fourteen was the shipped count when the loss was
        # measured; asserting a number would pin content, so this asserts the PROPERTY the
        # number stood for — every preset-channel chooser that has a document behind it has
        # an arm, and none of them degenerated to `comptime var out = hand; return out`.
        for rid in [r["id"] for r in doc["regions"]
                    if r.get(effects_gen.ACT_RASTER_REF_KEY) is not None]:
            rec = next(r["preset"] for r in doc["regions"] if r["id"] == rid)
            self.assertIn(f"// {rec}", text,
                          f"region {rid!r} binds a raster document to {rec} and no chooser "
                          f"arm in the generated module names that record")

    def test_the_guard_is_inert_without_a_document(self):
        """No `regions.json` means the sidecars are read exactly as today."""
        shutil.copy2(os.path.join(AEON, ACT1_EDITOR, "section_5.meta.json"),
                     os.path.join(self.act_dir, "section_5.meta.json"))
        effects_gen.check_mode_conflict(repo=self.repo)   # no raise

    def test_an_unreadable_document_is_not_treated_as_absent(self):
        """The missing/unreadable split, which the sidecar loader's docstring says is the
        point of the shape: absent means 'never migrated', unreadable means 'identity
        unknown', and shipping the second as the first builds a ROM from a stale table."""
        with open(os.path.join(self.act_dir, "regions.json"), "w") as f:
            f.write("{ this is not json")
        with self.assertRaises(json.JSONDecodeError):
            effects_gen.load_act_regions(repo=self.repo)


# ---------------------------------------------------------------------------
# DOCUMENT SHAPE — closed at every level
# ---------------------------------------------------------------------------

class TestDocumentShape(RegionSandbox):
    def test_unknown_top_level_key_is_refused_and_named(self):
        doc = golden_doc()
        doc["defaults"] = {"preset": "OJZ_Preset_Plain"}
        self.refuses(doc, "defaults", "unknown key")

    def test_unknown_region_key_is_refused_and_named(self):
        doc = golden_doc()
        doc["regions"][0]["bindings"] = {"preset": "OJZ_Preset_Sec0"}
        self.refuses(doc, "bindings", "regions[0]")

    def test_the_superseded_rects_array_is_refused_rather_than_half_read(self):
        """`rects` (plural) is the SUPERSEDED painter's-order shape from spec §2.3. The
        landed schema carries one `rect`, so a document written against the old prose must
        fail loudly and not silently lose every rectangle after the first."""
        doc = golden_doc()
        r = doc["regions"][0]
        r["rects"] = [r.pop("rect")]
        self.refuses(doc, "rects")

    def test_unknown_rect_key_is_refused(self):
        doc = golden_doc()
        doc["regions"][0]["rect"]["x1"] = 2047
        self.refuses(doc, "x1")

    def test_a_missing_required_key_is_refused_and_never_defaulted(self):
        for key in ("schema", "act", "regions"):
            doc = golden_doc()
            del doc[key]
            with self.subTest(key=key):
                self.refuses(doc, key)

    def test_a_region_without_a_preset_is_refused(self):
        doc = golden_doc()
        del doc["regions"][4]["preset"]
        self.refuses(doc, "preset", "NO default")

    def test_a_null_preset_is_refused_because_rg_effects_has_no_default(self):
        doc = golden_doc()
        doc["regions"][4]["preset"] = None
        self.refuses(doc, "preset")

    def test_wrong_schema_version_is_refused_and_names_both(self):
        doc = golden_doc()
        doc["schema"] = 2
        self.refuses(doc, "schema", "2", "1")

    def test_a_document_naming_another_act_is_refused(self):
        doc = golden_doc()
        doc["act"] = "ojz_act2"
        self.refuses(doc, "ojz_act2", "ojz_act1")

    def test_duplicate_region_ids_are_refused_and_name_both_positions(self):
        doc = golden_doc()
        doc["regions"][2]["id"] = "sec1"
        self.refuses(doc, "sec1", "regions[1]")

    def test_a_hyphenated_id_is_refused_because_ids_become_symbols(self):
        doc = golden_doc()
        doc["regions"][0]["id"] = "sec-0"
        self.refuses(doc, "sec-0")

    def test_an_empty_regions_array_is_refused_with_its_own_reason(self):
        doc = golden_doc()
        doc["regions"] = []
        self.refuses(doc, "empty", "delete the file")

    def test_a_float_coordinate_is_refused_rather_than_rounded(self):
        doc = golden_doc()
        doc["regions"][0]["rect"]["w"] = 2048.0
        self.refuses(doc, "rect.w", "integer")

    def test_a_numeric_sceneRef_is_refused_on_auroras_silent_null_grounds(self):
        doc = golden_doc()
        doc["regions"][0]["sceneRef"] = 3
        self.refuses(doc, "sceneRef", "did not stick")

    def test_name_is_accepted_and_carries_no_engine_meaning(self):
        doc = golden_doc()
        doc["regions"][0]["name"] = "anything at all"
        rows = self.rows(doc)
        self.assertEqual(rows[0]["name"], "anything at all")
        self.assertEqual([{k: r[k] for k in ROW_KEYS} for r in rows], golden_rows())

    def test_absent_optional_keys_normalise_to_explicit_nulls(self):
        """A caller comparing rows must not pass by reading a MISSING key through `.get`
        as the null it wanted. `sec1` writes neither ref, so both must come back None."""
        doc = golden_doc()
        loaded = None
        self.write_doc(doc)
        loaded = effects_gen.load_act_regions(repo=self.repo)
        sec1 = next(r for r in loaded["regions"] if r["id"] == "sec1")
        self.assertIn("sceneRef", sec1)
        self.assertIn("rasterRef", sec1)
        self.assertIsNone(sec1["sceneRef"])
        self.assertIsNone(sec1["rasterRef"])


# ---------------------------------------------------------------------------
# REF RESOLUTION
# ---------------------------------------------------------------------------

class TestRefResolution(RegionSandbox):
    def test_an_unknown_preset_record_is_refused_and_lists_the_known_ones(self):
        doc = golden_doc()
        doc["regions"][0]["preset"] = "OJZ_Preset_Nope"
        msg = self.refuses(doc, "OJZ_Preset_Nope", "OJZ_Preset_Night")
        self.assertIn("ojz_effects.emp", msg)

    def test_an_unknown_sceneRef_is_refused_and_lists_the_known_ids(self):
        doc = golden_doc()
        doc["regions"][0]["sceneRef"] = "ojz_act1_nope"
        self.refuses(doc, "ojz_act1_nope", "ojz_act1_start")

    def test_an_unknown_rasterRef_is_refused(self):
        doc = golden_doc()
        doc["regions"][5]["rasterRef"] = "ojz_nope"
        self.refuses(doc, "ojz_nope", "ojz_sec5_showcase")

    def test_the_library_records_include_every_shipped_preset(self):
        """Derived, not listed: the vocabulary is read from the library's own `pub data
        <Name>: EffectsPreset` declarations, so a record added there is bindable the same
        day. Asserting a couple of known members keeps the reader honest without pinning a
        count that every new preset would break."""
        names = effects_gen.act_names()
        records = effects_gen.effects_library_records(names)
        for want in ("OJZ_Preset_Sec0", "OJZ_Preset_Night", "OJZ_Preset_Plain",
                     "OJZ_Preset_Depth"):
            self.assertIn(want, records)
        self.assertEqual(records & {r["preset"] for r in golden_rows()},
                         {r["preset"] for r in golden_rows()},
                         "every preset the golden binds must exist in the library")

    def test_geometry_can_be_flattened_without_the_libraries(self):
        """`resolve=False` is what lets the pure-geometry tests run with no act on disk."""
        doc = golden_doc()
        doc["regions"][0]["preset"] = "Not_A_Real_Record"
        rows = self.rows(doc, resolve=False)
        self.assertEqual(len(rows), 10)


# ---------------------------------------------------------------------------
# THE BACKGROUND HALF — refused until the engine consumes it
# ---------------------------------------------------------------------------

class TestBackgroundBinding(RegionSandbox):
    def test_all_three_spellings_of_the_act_default_flatten_to_one_row(self):
        """The collapse, asserted over the spelling the golden does NOT already carry.

        The golden itself ships `"@act"` on `sec0`, null on `sec3` and an absent `bg` on the
        other eight, so `TestSharedGolden` already crosses all three. This moves the two
        explicit spellings onto DIFFERENT rows and requires the same ten rows back, which is
        what says the collapse is a rule and not a fact about two particular regions.
        """
        doc = golden_doc()
        del doc["regions"][0]["bg"]                 # sec0: "@act" -> absent
        del doc["regions"][3]["bg"]                 # sec3: null   -> absent
        doc["regions"][5]["bg"] = {"layoutRef": None}
        doc["regions"][9]["bg"] = {"layoutRef": "@act"}
        rows = self.rows(doc)
        self.assertEqual([{k: r[k] for k in ROW_KEYS} for r in rows], golden_rows())

    def test_the_sentinel_does_not_reach_the_row_as_a_string(self):
        """`"@act"` IS `rg_bg_layout = 0`, and the row must say the engine's fact.

        Separated from the test above because the two fail for different reasons: that one
        goes red if the collapse is applied inconsistently across spellings, this one goes
        red if the collapse is not applied at all — a flattener that copied the sentinel
        through would hand a consumer a STRING where the engine dereferences a POINTER, and
        every row would still be "equal" to a fixture written the same wrong way.
        """
        rows = self.rows()
        for r in rows:
            self.assertIsNone(r["bg"]["layoutRef"],
                              f"row {r['index']} ({r['id']}) carries "
                              f"{r['bg']['layoutRef']!r} — the act default is null on the "
                              f"row whatever the document spelled")
            self.assertIsNone(r["bg"]["span"])
        self.assertIn("@act", json.dumps(golden_doc()),
                      "the golden document no longer spells the sentinel anywhere, so the "
                      "assertion above is vacuous — restore an `@act` layoutRef or this "
                      "test stops testing the collapse")

    def test_a_named_layout_is_refused_and_the_reason_is_the_undERIVABLE_span(self):
        """The refusal stands; its stated REASON has now been corrected TWICE in one day.

        Round 1: it said "NOTHING IN THE ENGINE READS IT YET", which step 3 (`17bf60fe`)
        made false for `rg_bg_layout`. Round 2 (the emitter parcel): the replacement leaned
        on "nothing lowers this document into a region table", which the emitter falsified,
        AND on "`rg_bg_span` has no engine reader until step 4's clamp", which step 4 had
        ALREADY falsified before the sentence was written.

        What is left is the reason that was load-bearing all along and was never checked
        because two easier ones were in front of it: `ojz_bglib.json` carries `id` and
        `name` and NO HEIGHT, so the derived-span check this generator owes has nothing to
        derive from. That one is measured, not remembered.
        """
        doc = golden_doc()
        doc["regions"][0]["bg"] = {"layoutRef": "ojz_cave"}
        msg = self.refuses(doc, "ojz_cave", "NO HEIGHT")
        self.assertNotIn("NOTHING IN THE ENGINE READS IT YET", msg)
        # ...and not the SECOND stale sentence either. "nothing lowers this document" was
        # true when written and the emitter parcel falsified it; "rg_bg_span has no engine
        # reader" was falsified the same day it was written, by step 4's clamp. Both are
        # asserted absent, because a refusal whose reason is wrong sends the author to the
        # wrong file, and a reason that USED to be right is the hardest kind to notice.
        self.assertNotIn("NOTHING LOWERS THIS DOCUMENT", msg)
        self.assertNotIn("no engine reader", msg)
        self.assertIn("Parallax_Step5_Vscroll", msg)

    def test_TRIPWIRE_opening_layoutRef_without_the_golden_fails_here(self):
        """The day `bg.layoutRef` opens, the shared golden owes a non-default row.

        WHY THIS EXISTS. `REGIONS-BG-GOLDEN-GAP` says a golden published before the engine
        reads these fields out of the DOCUMENT costs one parcel and the same golden published
        after costs a debugging session first. The golden's `bg` half is the DEFAULT half
        only — no row names a layout, so nothing above would notice a flattener that got a
        named layout wrong. This is what stops that from being discovered later.

        WHAT IT WOULD ACCEPT AT RANDOM, stated because the weak arm is today's: while the
        refusal stands, this asserts the golden carries no non-default row, which is trivial.
        The arm with teeth is the other one, and it was proven by MUTATION rather than
        argument — `_check_region_bg` was patched to accept a named layout and this test went
        red naming the fixture. The subject is `_check_region_bg` itself, the single site that
        refuses, so a later stage refusing for its own reasons cannot mask the opening.
        """
        try:
            effects_gen._check_region_bg("(tripwire)", {"layoutRef": "ojz_cave"},
                                         "regions[0]")
        except effects_gen.SceneShapeError:
            opened = False
        else:
            opened = True

        # THE EMITTER IS THE SECOND SITE THAT MUST MOVE (added 2026-09-16), and it is a
        # site the original tripwire could not have known about. `render_region_table`
        # writes five of `struct Region`'s eight fields and refuses a non-default `bg`
        # rather than lowering one, so opening `_check_region_bg` alone would let a named
        # layout be validated, flattened, and DROPPED AT EMISSION — the same failure one
        # layer further in, and invisible to the assertion below.
        try:
            effects_gen._refuse_unlowerable_bindings(
                [{"id": "x", "index": 0, "sceneRef": None, "rasterRef": None,
                  "bg": {"layoutRef": "ojz_cave", "span": 2048}}], "(tripwire)")
        except effects_gen.SceneShapeError:
            emitter_drops_it = False
        else:
            emitter_drops_it = True
        if opened:
            self.assertFalse(
                emitter_drops_it,
                "`bg.layoutRef` now ACCEPTS a named layout and `render_region_table` still "
                "emits no `rg_bg_layout`/`rg_bg_span`, so a named layout is validated, "
                "flattened and then dropped at emission. Open both sites together or "
                "neither: REGIONS-BG-GOLDEN-GAP in docs/DEFERRED_WORK.md.")

        non_default = [r for r in golden_rows()
                       if r["bg"]["layoutRef"] is not None or r["bg"]["span"] is not None]
        if opened:
            self.assertTrue(non_default,
                            "`bg.layoutRef` now ACCEPTS a named layout, and every row of "
                            "tools/fixtures/regions/ojz_act1.rows.json still leaves "
                            "rg_bg_layout/rg_bg_span at their defaults. The seam is now "
                            "untested on exactly the values that just became expressible: "
                            "give at least one region in ojz_act1.regions.json a `bg` with a "
                            "named layoutRef and its derived span, hand-derive the matching "
                            "row here, say in `_provenance` what is no longer a transcription "
                            "of act_descriptor.emp, and tell aurora — their flattener has to "
                            "reproduce the same two values. REGIONS-BG-GOLDEN-GAP in "
                            "docs/DEFERRED_WORK.md is the booking.")
        else:
            self.assertEqual(non_default, [],
                             "the golden carries a non-default `bg` row that the loader "
                             "refuses — the fixture and the generator disagree about what a "
                             "document may say, and the FINDING is which of them is wrong")

    def test_a_typed_span_is_refused_as_derived_and_never_authored(self):
        """Two rules at once, and the message says both: `ojz_region()`'s
        `bg_layout != 0 || bg_span == 0`, and part 2 §6.2's "derived from the referenced
        layout's height and never typed" — which is the check only this generator can make,
        because the schema never sees the layout."""
        doc = golden_doc()
        doc["regions"][0]["bg"] = {"layoutRef": "@act", "span": 2048}
        self.refuses(doc, "span", "DERIVED")

    def test_an_unknown_bg_key_is_refused(self):
        doc = golden_doc()
        doc["regions"][0]["bg"] = {"layoutRef": "@act", "anchor": 3}
        self.refuses(doc, "anchor")


# ---------------------------------------------------------------------------
# THE EMITTER
# ---------------------------------------------------------------------------

class TestRegionTableEmitter(RegionSandbox):
    """`render_region_table` + `generate_region_table` — the rows as `.emp` text.

    ⚠ THE SENTENCE THAT STOOD HERE IS NOW FALSE, AND THAT IS THE HEADLINE (2026-09-16).
    It read: *"NOTHING HAS ASSEMBLED THIS TEXT. No act in this tree is in region mode, so the
    emitter is inert in every build and its output has never been through sigil."* Act 1 is in
    region mode; `games/sonic4/data/generated/ojz/act1/regions.emp` is a build input, and both
    shapes assemble it. The first assembly found a real fault these tests could not have seen
    — a struct literal takes no declaration defaults, so the five-field rows sigil was handed
    produced 150 errors (see `test_every_declared_region_field_is_written_by_every_row`).

    WHAT A GREEN HERE STILL DOES NOT MEAN: these tests read TEXT. That the text assembles is
    the build's verdict, and that the ROM's rows are the golden's rows is
    `TestShippedTableMatchesGolden`'s, which reads bytes out of the image.
    """

    def emit(self, doc=None):
        """The golden document, whole, lowered.

        ⚠ IT USED TO BE `self.bare_doc()` — the golden with every `sceneRef` and `rasterRef`
        STRIPPED — because the emitter refused a binding it could not lower. That refusal is
        spent (REGIONS-EMIT-BINDINGS), and the stripping went with it: a fixture that removed
        six of the document's ten interesting facts before testing it would now be hiding the
        half this parcel added. The committed `.emp.txt` golden is therefore the WHOLE
        document's output, bindings included, which is also what makes it comparable by eye
        with the real generated artifact.
        """
        self.write_doc(golden_doc() if doc is None else doc)
        return effects_gen.generate_region_table(repo=self.repo)

    def test_the_emitted_rows_are_the_golden_rows(self):
        """The acceptance test: every emitted call carries the golden's own numbers.

        Parsed back out of the text rather than compared as a string, so the assertion is
        about the ROWS and not about spacing — a formatting change is not a content
        change and should not read as one.
        """
        _path, text = self.emit()
        names = effects_gen.act_names(repo=self.repo)
        calls = re.findall(
            r"Region\{ rg_x0:\s*(\d+), rg_x1:\s*(\d+), rg_y0:\s*(\d+), "
            r"rg_y1:\s*(\d+), rg_effects: (\w+),\s*rg_parallax: (\w+),\s*"
            r"rg_bg_layout: 0, rg_bg_span: 0, rg_bg_tiles: 0 \},", text)
        self.assertEqual(len(calls), len(golden_rows()))
        for call, want in zip(calls, golden_rows()):
            x0, x1, y0, y1, preset, par = call
            # THE PARALLAX COLUMN IS PART OF THE ROW NOW (REGIONS-EMIT-BINDINGS), so it is
            # compared with the rest rather than pattern-matched as a constant `0`. The
            # expectation is DERIVED from the golden's own `sceneRef` — typing the symbol
            # beside the row would pass against a generator that emitted the same wrong
            # binding for every row.
            want_par = (names.binding_region(want["id"])
                        if want.get("sceneRef") is not None else "0")
            self.assertEqual((int(x0), int(x1), int(y0), int(y1), preset, par),
                             (want["x0"], want["x1"], want["y0"], want["y1"],
                              want["preset"], want_par),
                             f"emitted row {want['index']} ({want['id']}) disagrees with "
                             f"the shared golden")

    def test_the_emitted_text_is_the_committed_golden_fragment(self):
        """Byte-for-byte against a committed `.emp`, which is what a drift gate compares.

        The row test above is about VALUES and would pass through a header rewrite, a
        lost caveat, or a dropped `_ROW_*` constant. This one is about the artifact. The
        fixture is REGENERATED by `python3 tools/effects_gen.py emit` for a region-mode
        act, so when it legitimately changes the diff is the review.
        """
        _path, text = self.emit()
        with open(GOLDEN_EMP) as f:
            self.assertEqual(text, f.read())

    def test_every_row_gets_an_index_constant_named_by_its_document_id(self):
        """The DEBUG-delta ruling's named-row mechanism (empyrean `a718ea7c`).

        The delta shortens `sec2`, so the descriptor has to address that row by NAME. A
        renamed region deletes the constant its ensure reads; a moved one changes its
        value. Both fail the build, which is the whole point of the condition.
        """
        _path, text = self.emit()
        for row in golden_rows():
            self.assertIn(f"const OJZ_ACT1_ROW_{row['id'].upper()} = {row['index']}",
                          text)
        # The row the ruling names, spelled out: it is row 2 and it ends at the grid edge.
        self.assertIn("const OJZ_ACT1_ROW_SEC2 = 2", text)

    def test_the_header_points_at_the_release_shape_only_note(self):
        """A CONDITION of the DEBUG-delta ruling, not decoration: *"the emitter should
        point at that note from the generated table's header."*

        Asserted on the fixture's real path, so moving or renaming the golden without
        updating the header fails here rather than leaving a dangling pointer in a
        generated file nobody edits."""
        _path, text = self.emit()
        self.assertIn("release_shape_only", text)
        self.assertIn("tools/fixtures/regions/ojz_act1.rows.json", text)
        self.assertIn("release_shape_only",
                      json.load(open(GOLDEN_ROWS))["_provenance"])

    def test_the_golden_LOWERS_its_bindings_instead_of_being_refused(self):
        """⚠ WAS `test_the_golden_itself_is_refused_for_its_bindings`, AND THE REFUSAL IT
        PINNED IS SPENT (2026-09-16), NOT RELAXED.

        It read: *"`sceneRef`/`rasterRef` are REFUSED, never emitted as `parallax: 0`. This is
        the parcel's stop condition made executable."* That was right: `render_module`'s
        binding half was keyed on the section index end to end, so a region-mode act lowered
        every binding to NOTHING and a zero here would have been the row silently losing its
        picture. REGIONS-EMIT-BINDINGS re-keyed it, so the six bindings the golden carries now
        have somewhere to land.

        THE SUCCESSOR IS THE SAME ASSERTION WITH THE SIGN FLIPPED, and it is written to fail
        against the one outcome the old refusal existed to prevent: a `sceneRef` that lowers
        to `rg_parallax: 0`. A test that only checked "no exception" would pass against
        exactly that.
        """
        self.write_doc(golden_doc())
        _path, text = effects_gen.generate_region_table(repo=self.repo)
        names = effects_gen.act_names(repo=self.repo)
        rows = golden_rows()
        bound = [r for r in rows if r.get("sceneRef") is not None]
        self.assertTrue(bound, "the golden binds no scene, so this test has no subject")
        for want in rows:
            line = next(ln for ln in text.splitlines()
                        if ln.lstrip().startswith("Region{")
                        and ln.rstrip().endswith(f"— {want['id']}"))
            expect = (names.binding_region(want["id"]) if want.get("sceneRef") is not None
                      else "0")
            self.assertIn(f"rg_parallax: {expect}", line,
                          f"row {want['index']} ({want['id']}) should carry "
                          f"rg_parallax: {expect}\n{line}")
        # And the RASTER half, which reaches the ROM through the record's channels rather
        # than through this table — so the table must NOT have grown a column for it.
        self.assertNotIn("rg_raster", text)

    def test_legacy_mode_emits_nothing_and_that_is_not_an_error(self):
        """`None`, never an empty file. The whole mode decision, and today's answer for
        every act in this repo.

        The sandbox writes no document until a test asks for one, so this asserts against
        the tree as `setUp` leaves it — and it checks the presence guard positively first,
        because "returned None" and "returned None for the wrong reason" are the same
        value.
        """
        self.assertFalse(effects_gen.has_act_regions(repo=self.repo))
        self.assertIsNone(effects_gen.generate_region_table(repo=self.repo))
        # ...and the same call with a document present is NOT None, so the assertion above
        # is not passing because the emitter is broken in some other way.
        self.write_doc(golden_doc())
        self.assertIsNotNone(effects_gen.generate_region_table(repo=self.repo))

    def test_the_emitted_module_declares_itself(self):
        """THE GATE WHOSE RED WAS AN ACTUAL BUILD FAILURE, not a contrived mutation.

        The emitter's first draft wrote a module-less fragment. `sigil build` parses every
        `.emp` in the tree, so the committed FIXTURE alone — never emitted, never placed,
        never imported — took the plain demo build to exit 1 with `error: file must start
        with a `module` declaration` and 50 tests in test_artifact_provenance.py /
        test_provenance_consumers.py with it. This asserts the shape that measurement
        forced, on the emitted TEXT, so the emitter can never reintroduce it.

        The module name is DERIVED from the act's own ids (`ActNames`), the way the
        generated effects module's is, so a second act cannot collide with this one.
        """
        _path, text = self.emit()
        lines = [ln for ln in text.splitlines()
                 if ln.strip() and not ln.lstrip().startswith("//")]
        self.assertTrue(lines[0].startswith("module "),
                        f"the first non-comment line must be a `module` declaration, "
                        f"got {lines[0]!r}")
        names = effects_gen.act_names(repo=self.repo)
        self.assertEqual(lines[0],
                         f"module games.sonic4.{names.zone_id}_regions_{names.act_id}")

    def test_the_imports_are_derived_from_the_rows_not_from_the_library(self):
        """Every preset the rows bind is imported, and nothing else is.

        Importing the whole effects library would work and would hide a real fault: a row
        binding a record that vanished. `resolve_act_regions` refuses that upstream, and
        this keeps the emitted import list an honest statement of what the table names.
        """
        _path, text = self.emit()
        line = next(ln for ln in text.splitlines()
                    if ln.startswith("use games.sonic4.") and "_effects.{" in ln)
        imported = [s.strip() for s in line.split("{")[1].rstrip("}").split(",")]
        self.assertEqual(imported, sorted({r["preset"] for r in golden_rows()}))

    def test_the_struct_fields_are_READ_from_the_engine_not_assumed(self):
        """The one structural check a generator with no assembler can make.

        The literal's field names come from `engine/structs.emp`'s own `pub struct Region`
        declaration. Proven by renaming a field in a copy of the engine and requiring the
        emission to REFUSE — a test that only asserted the string `rg_x0` would pass
        against a hard-coded list.
        """
        # The sandbox symlinks `engine`; swap in a real copy to edit.
        eng = os.path.join(self.repo, "engine")
        real = os.path.realpath(eng)
        os.unlink(eng)
        shutil.copytree(real, eng)
        sp = os.path.join(eng, "structs.emp")
        with open(sp) as f:
            src = f.read()
        self.assertIn("rg_x0:", src)
        with open(sp, "w") as f:
            f.write(src.replace("rg_x0:", "rg_left:"))
        self.write_doc(golden_doc())
        with self.assertRaises(effects_gen.SceneShapeError) as cm:
            effects_gen.generate_region_table(repo=self.repo)
        msg = str(cm.exception)
        self.assertIn("rg_x0", msg)
        self.assertIn("engine/structs.emp", msg)

    def test_every_declared_region_field_is_written_by_every_row(self):
        """A STRUCT LITERAL TAKES NO DECLARATION DEFAULTS, measured the hard way.

        Until 2026-09-16 this emitter wrote five of `struct Region`'s eight fields and its
        own banner explained that the other three "each carry an `= 0` default in the
        declaration, which is what makes omitting them legal". Nothing had ever assembled
        the text — the banner said so, in capitals — and when the first act flipped, sigil
        answered with 150 `[struct.missing-field]` errors over ten rows. A declared `= 0`
        defaults a `comptime fn` PARAMETER, which is how `ojz_region(...)` reaches the same
        three fields; it does not default a literal's field.

        THE EXPECTATION IS DERIVED FROM `engine/structs.emp`, never typed here: this reads
        the declaration the way the generator does and requires every field of it to appear
        in every emitted row. Add `rg_foo` to the engine struct and this fails, which is the
        whole point — the old shape could not fail, because the list it checked against was
        the same list it emitted from.
        """
        _path, text = self.emit()
        fields = effects_gen.region_struct_fields(repo=self.repo)
        self.assertGreaterEqual(len(fields), 5, "read no fields from the declaration — "
                                                "a green here would be vacuous")
        rows = [ln for ln in text.splitlines() if ln.lstrip().startswith("Region{")]
        self.assertEqual(len(rows), len(golden_rows()))
        # AGGREGATED, NOT SHORT-CIRCUITED, and the first draft of this test was the other
        # way. A per-field `assertIn` inside the loop raises on the FIRST omission, so a
        # subject missing four fields reported exactly as much as one missing one — the
        # gate got no louder as the subject got more broken, which is the failure family
        # this repo keeps finding in its own gates. Checked by mutation: dropping
        # `rg_parallax` alone reports 10 misses, dropping `rg_y1` as well reports 20.
        misses = [f"row {i}: `{f}`" for i, ln in enumerate(rows)
                  for f in fields if f"{f}:" not in ln]
        self.assertEqual(misses, [],
                         f"{len(misses)} emitted field omission(s) across {len(rows)} "
                         f"row(s); `pub struct Region` declares {len(fields)} field(s) and "
                         f"a struct literal must provide every one of them. "
                         f"{'; '.join(misses)}\nfirst row as emitted:\n{rows[0]}")

    def test_an_added_engine_field_refuses_the_emission_by_name(self):
        """The other direction of the same rule, proven by mutating the engine.

        `test_the_struct_fields_are_READ_from_the_engine_not_assumed` proves a RENAMED
        field refuses. A field ADDED is the case that produced the 150-error build: the
        emitter went on writing the fields it knew and the result could not compile, on a
        generated file nobody edits. The refusal has to name the engine declaration and the
        new field.
        """
        eng = os.path.join(self.repo, "engine")
        real = os.path.realpath(eng)
        os.unlink(eng)
        shutil.copytree(real, eng)
        sp = os.path.join(eng, "structs.emp")
        with open(sp) as f:
            src = f.read()
        self.assertIn("    rg_bg_span:          u16 = 0,", src)
        with open(sp, "w") as f:
            f.write(src.replace("    rg_bg_span:          u16 = 0,",
                                "    rg_bg_span:          u16 = 0,\n"
                                "    rg_probe_field:      u16 = 0,"))
        self.write_doc(golden_doc())
        with self.assertRaises(effects_gen.SceneShapeError) as cm:
            effects_gen.generate_region_table(repo=self.repo)
        msg = str(cm.exception)
        self.assertIn("rg_probe_field", msg)
        self.assertIn("engine/structs.emp", msg)
        self.assertIn("every declared field", msg)

    def test_the_header_says_the_consumer_owes_the_per_row_checks(self):
        """A literal does not go through `ojz_region()`, so it carries none of its ensures.

        That is a real loss and the emitted file has to say so where the person wiring it
        up will read it — not only in a note they may never open.
        """
        _path, text = self.emit()
        self.assertIn("ojz_region()", text)
        # ⚠ WAS `assertIn("REGIONS-EMIT-BINDINGS")`, THE BOOKING THAT OWED THE WALK. The
        # walk has landed (`ojz_region_table_check` in act_descriptor.emp), so pointing a
        # reader at a closed booking would send them to a section that says the work is done
        # without saying where it went. The header now names the walk itself, and this asserts
        # the CONSUMER'S obligation is still stated — the debt is per consumer, so a second
        # act's descriptor owes its own and the sentence must survive act 1 paying it.
        self.assertIn("TABLE WALK", text)
        self.assertIn("ojz_region_table_check", text)
        # ⚠ WAS `assertIn("NOTHING HAS ASSEMBLED THIS FILE")`, AND THAT SENTENCE IS NOW A
        # LIE THE HEADER MUST NOT TELL. Act 1 is in region mode and this module is a build
        # input in both shapes. Asserting the old caveat would have kept a warning alive that
        # sends its reader looking for a gap that has closed — and the assertion would have
        # been the thing keeping it there. What the header must still say is WHY the rows are
        # literals, because that is the fact the consumer's obligation follows from.
        self.assertIn("struct LITERAL takes no", text)
        self.assertIn("BUILD INPUT", text)


# ---------------------------------------------------------------------------
# THE PER-ROW AND WHOLE-TABLE RULES
# ---------------------------------------------------------------------------

class TestRowRules(RegionSandbox):
    def test_an_overlap_is_refused_and_names_both_regions(self):
        doc = golden_doc()
        doc["regions"][1]["rect"]["w"] += 64       # sec1 eats into the night region
        # ⚠ `NIGHT_ID` AND NOT THE BARE WORD, and the reason is a near-miss worth recording:
        # `refuses` uses `assertIn`, and "night" is a SUBSTRING of "ojz_preset_night", so
        # this assertion would have gone on passing un-edited through the id ruling while
        # no longer naming the id the author has to go and find. A green that survives the
        # change it was supposed to track is the failure mode, not the rename.
        self.refuses(doc, "sec1", NIGHT_ID, "overlap", resolve=False)

    def test_a_hole_is_refused_and_names_the_uncovered_rectangle(self):
        doc = golden_doc()
        doc["regions"][1]["rect"]["w"] -= 64       # sec1 retreats from night
        msg = self.refuses(doc, "belong to no region", resolve=False)
        self.assertIn("x 3336..3399", msg)

    def test_a_row_narrower_than_the_minimum_span_is_refused(self):
        doc = golden_doc()
        doc["regions"][1]["rect"]["w"] -= 16
        doc["regions"][9]["rect"]["x"] -= 16
        doc["regions"][9]["rect"]["w"] += 16
        rows = self.rows(doc, resolve=False)       # still legal: 1336 px wide
        self.assertEqual(rows[1]["x1"], 3383)
        doc = golden_doc()
        doc["regions"].append({
            "id": "sliver", "preset": "OJZ_Preset_Plain",
            "rect": {"x": 3000, "y": 1000, "w": 16, "h": 512}})
        self.refuses(doc, "sliver", "REGION_MIN_SPAN", "32", resolve=False)

    def test_a_row_reaching_past_the_act_is_refused(self):
        doc = golden_doc()
        doc["regions"][2]["rect"]["w"] += 64
        self.refuses(doc, "sec2", "past the act", resolve=False)

    def test_an_interior_edge_outside_the_reachable_band_is_refused(self):
        """An edge the camera centre can never reach makes a region nothing can enter."""
        doc = golden_doc()
        doc["regions"][0]["rect"]["w"] = 64        # sec0 right edge at x = 63
        doc["regions"].append({
            "id": "filler", "preset": "OJZ_Preset_Plain",
            "rect": {"x": 64, "y": 0, "w": 1984, "h": 2048}})
        self.refuses(doc, "reachable band", resolve=False)

    def test_right_edge_rule_is_not_the_left_rule_mirrored(self):
        """THE TWO-EDGE CASE, and the reason this test lands exactly on the endpoint.

        The naive transcription of the right-edge rule — reuse the left expression with
        `x1` substituted, `x1 - 1 >= CENTRE_X_MIN and x1 <= CENTRE_X_MAX` — disagrees with
        the engine on exactly two of this act's 6144 vertical edges: `x = CENTRE_X_MIN` and
        `x = CENTRE_X_MAX` (aurora, measured over all of them, 2026-09-16). An edge one
        pixel to either side cannot tell the two readings apart, so a test that sampled
        NEAR the boundary would pass under the wrong rule.

        Derived here rather than copied: both readings are evaluated over the whole axis
        and the disagreement set is REQUIRED to be exactly those two endpoints. If the
        engine's rule ever changes, this fails with the new set rather than going stale.
        """
        b = region_flatten.act_bounds(ACT1_DESCRIPTOR)
        lo, hi, w = b["CENTRE_X_MIN"], b["CENTRE_X_MAX"], b["ACT_W"]

        def engine(x1):
            return x1 == w - 1 or (x1 >= lo and x1 + 1 <= hi)

        def naive(x1):
            return x1 == w - 1 or (x1 - 1 >= lo and x1 <= hi)

        disagree = {x for x in range(w) if engine(x) != naive(x)}
        self.assertEqual(disagree, {lo, hi},
                         "the two readings must differ on exactly the band endpoints")
        # And the implementation must be the ENGINE's reading on both of them.
        for x1, legal in ((lo, True), (hi, False)):
            row = {"x0": 0, "x1": x1, "y0": 0, "y1": b["ACT_H"] - 1}
            complaints = [c for c in region_flatten._check_row(row, b, "probe")
                          if "RIGHT edge" in c]
            self.assertEqual(not complaints, legal,
                             f"x1 = {x1}: engine says legal={legal}")


# ---------------------------------------------------------------------------
# THE GEOMETRY, on its own
# ---------------------------------------------------------------------------

class TestRectAlgebra(unittest.TestCase):
    def test_subtract_disjoint_returns_the_original(self):
        self.assertEqual(region_flatten.subtract((0, 0, 10, 10), (20, 20, 5, 5)),
                         [(0, 0, 10, 10)])

    def test_subtract_covering_returns_nothing(self):
        self.assertEqual(region_flatten.subtract((5, 5, 10, 10), (0, 0, 100, 100)), [])

    def test_subtract_a_stripe_splits_into_two(self):
        pieces = region_flatten.subtract((0, 0, 10, 10), (0, 4, 10, 2))
        self.assertEqual(sorted(pieces), sorted([(0, 0, 10, 4), (0, 6, 10, 4)]))

    def test_subtract_a_corner_splits_into_two(self):
        pieces = region_flatten.subtract((0, 0, 10, 10), (0, 0, 4, 4))
        self.assertEqual(sorted(pieces), sorted([(0, 4, 10, 6), (4, 0, 6, 4)]))

    def test_subtract_an_interior_hole_splits_into_four(self):
        pieces = region_flatten.subtract((0, 0, 10, 10), (4, 4, 2, 2))
        self.assertEqual(len(pieces), 4)
        self.assertEqual(sum(w * h for _x, _y, w, h in pieces), 100 - 4)
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                self.assertFalse(region_flatten.intersects(pieces[i], pieces[j]),
                                 "the four pieces must be disjoint, not double-count "
                                 "the corners")

    def test_subtract_an_edge_bite_splits_into_three(self):
        pieces = region_flatten.subtract((0, 0, 10, 10), (4, 0, 2, 4))
        self.assertEqual(len(pieces), 3)
        self.assertEqual(sum(w * h for _x, _y, w, h in pieces), 100 - 8)

    def test_touching_rects_do_not_intersect(self):
        """Exclusive form: `[0, 10)` and `[10, 20)` share no pixel. An off-by-one here
        would make every neighbouring pair of regions an overlap."""
        self.assertFalse(region_flatten.intersects((0, 0, 10, 10), (10, 0, 10, 10)))
        self.assertTrue(region_flatten.intersects((0, 0, 10, 10), (9, 0, 10, 10)))

    def test_uncovered_can_actually_find_a_hole(self):
        """THE INSTRUMENT CHECK. `[]` is what a covered act produces and also what a
        broken `uncovered()` produces; this proves it can return the other answer."""
        act = [(0, 0, 100, 100)]
        self.assertEqual(region_flatten.uncovered(act, 100, 100), [])
        with_hole = region_flatten.subtract((0, 0, 100, 100), (40, 40, 10, 10))
        holes = region_flatten.uncovered(with_hole, 100, 100)
        self.assertEqual(holes, [(40, 40, 10, 10)])

    def test_to_inclusive_is_the_one_conversion_site(self):
        self.assertEqual(region_flatten.to_inclusive({"x": 3400, "y": 0,
                                                      "w": 1400, "h": 2048}),
                         {"x0": 3400, "x1": 4799, "y0": 0, "y1": 2047})
        self.assertEqual(region_flatten.to_inclusive({"x": 5, "y": 7, "w": 1, "h": 1}),
                         {"x0": 5, "x1": 5, "y0": 7, "y1": 7})

    def test_first_overlap_reports_the_lowest_pair_in_scan_order(self):
        rects = [(0, 0, 10, 10), (100, 0, 10, 10), (5, 5, 10, 10), (5, 5, 2, 2)]
        self.assertEqual(region_flatten.first_overlap(rects), (0, 2))

    def test_a_zero_extent_rect_is_refused_rather_than_treated_as_empty(self):
        with self.assertRaises(region_flatten.RuleError):
            region_flatten.subtract((0, 0, 10, 0), (0, 0, 1, 1))

    def test_bounds_are_read_from_the_descriptor_and_never_defaulted(self):
        with self.assertRaises(region_flatten.RuleError) as cm:
            region_flatten.act_bounds("games/sonic4/data/levels/ojz/act9/act_descriptor.emp")
        self.assertIn("act9", str(cm.exception))

    def test_every_bound_comes_from_the_act_descriptors_own_const_lines(self):
        """Not restated in Python. The seeded fold is what keeps the reachable-band
        formula the descriptor's sentence."""
        b = region_flatten.act_bounds(ACT1_DESCRIPTOR)
        src = open(os.path.join(AEON, ACT1_DESCRIPTOR)).read()
        for name in region_flatten.BOUND_NAMES:
            self.assertIn(f"const {name} =", src,
                          f"{name} must be declared in the descriptor, not here")
            self.assertIsInstance(b[name], int)


# ---------------------------------------------------------------------------
# GATE ROWS-IDENTICAL — the golden against the table in a BUILT ROM
# ---------------------------------------------------------------------------

class TestShippedTableMatchesGolden(unittest.TestCase):
    """The byte-exact half: the golden reproduces the table the ROM actually carries.

    Everything above compares the flattener with a hand TRANSCRIPTION of
    `OJZ_ACT1_REGION_ROWS`. That transcription could itself be wrong, and a wrong one would
    make every test above agree with itself. This reads the rows out of the assembled image
    through `tools/region_table.py` — whose struct layout is parsed from `engine/structs.emp`
    rather than typed — so the comparison is against bytes nobody transcribed.

    RELEASE SHAPE ONLY, and that is not a convenience. The DEBUG ROM carries TWO extra rows
    and THREE shortened ones, none of which a closed regions document can express; comparing
    against it would fail for a reason that is not a flattener defect. The marker declares
    `s4.bin`/`s4.lst`, which only the plain `./build.sh` writes.

    ⚠ THE COUNT WAS WRONG HERE UNTIL 2026-09-16 AND SO IS THE FIGURE IN `DEFERRED_WORK`.
    This said "an eleventh row (`OJZ_E2_SNAP_ROWS`) and a shortened `sec2`" — singular on both
    halves, and true when written. Regions part 2 step 5 added `OJZ_TALL_BG_ROWS`, a TWELFTH
    row that carves the right end off rows 5 AND 8. Measured off the built images rather than
    counted from source: release 10 rows x 22 B = 220 B, DEBUG 12 x 22 = 264 B (the booking's
    "11 x 22 = 242" is the stale pair). The DEBUG shortenings are sec2 -> x1 5599, sec5 -> 5119
    and sec8 -> 5119.

    MARKED needs_build (LS-1): the pre-build lane deselects it, the post-sigil lane runs it
    against the artifacts THIS invocation emitted. Absent artifacts => DEFERRED, never a
    silent skip.
    """

    @pytest.mark.needs_build("s4.bin", "s4.lst")
    def test_the_golden_rows_are_the_rows_the_release_rom_carries(self):
        import region_table
        from raster_cost_probe import parse_lst

        rom = open(os.path.join(AEON, "s4.bin"), "rb").read()
        sym = parse_lst(os.path.join(AEON, "s4.lst"))
        self.assertIn("OJZ_Act1_Descriptor", sym,
                      "the listing carries no OJZ_Act1_Descriptor, so the table could not "
                      "be located — a measurement that could not be made, not a pass")
        rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"] & 0xFFFFFF)
        want = golden_rows()

        self.assertEqual(len(rows), len(want),
                         f"the release ROM carries {len(rows)} region rows and the golden "
                         f"has {len(want)}. TWELVE means this is a DEBUG image (the E2 snap "
                         f"fixture plus the tall-background row); anything else is a real "
                         f"disagreement and the FINDING is which side is wrong, not which "
                         f"to adjust.")

        # Geometry, row for row. Reported per row so a disagreement names the row AND the
        # axis rather than dumping two lists.
        for got, exp in zip(rows, want):
            with self.subTest(row=exp["index"], id=exp["id"]):
                for axis in ("x0", "x1", "y0", "y1"):
                    self.assertEqual(got[axis], exp[axis],
                                     f"row {exp['index']} ({exp['id']}): {axis} is "
                                     f"{got[axis]} in the ROM and {exp[axis]} in the golden")

        # `rg_effects` resolves to the record name the document binds.
        by_addr = {}
        for name, addr in sym.items():
            by_addr.setdefault(addr & 0xFFFFFF, set()).add(name)
        for got, exp in zip(rows, want):
            with self.subTest(row=exp["index"], field="rg_effects"):
                self.assertIn(exp["preset"], by_addr.get(got["effects"] & 0xFFFFFF, set()),
                              f"row {exp['index']} ({exp['id']}): rg_effects points at "
                              f"{got['effects']:#x}, whose listing names are "
                              f"{sorted(by_addr.get(got['effects'] & 0xFFFFFF, set()))} — "
                              f"the golden binds {exp['preset']!r}")

        # `rg_parallax`: DERIVED from the document, not from the emitted symbol names. The
        # claim is presence-for-presence — a region that names a scene has a non-zero
        # parallax pointer and one that does not has zero — because the SYMBOL a sceneRef
        # lowers to is section-keyed today and is exactly what the emitter parcel changes.
        for got, exp in zip(rows, want):
            with self.subTest(row=exp["index"], field="rg_parallax"):
                if exp["sceneRef"] is None:
                    self.assertEqual(got["parallax"], 0,
                                     f"row {exp['index']} ({exp['id']}) names no sceneRef "
                                     f"but the ROM row binds {got['parallax']:#x}")
                else:
                    self.assertNotEqual(got["parallax"], 0,
                                        f"row {exp['index']} ({exp['id']}) names sceneRef "
                                        f"{exp['sceneRef']!r} but the ROM row binds 0")
                    names = by_addr.get(got["parallax"] & 0xFFFFFF, set())
                    self.assertTrue(any(n.startswith("EditorSceneBinding_") for n in names),
                                    f"row {exp['index']}: rg_parallax {got['parallax']:#x} "
                                    f"names {sorted(names)}, none of them an editor scene "
                                    f"binding")

        # The whole-table invariants, against the ROM's own numbers.
        bounds = region_flatten.act_bounds(ACT1_DESCRIPTOR)
        self.assertEqual(region_flatten.area_of_rows(rows),
                         bounds["ACT_W"] * bounds["ACT_H"])
        rects = [(r["x0"], r["y0"], r["x1"] - r["x0"] + 1, r["y1"] - r["y0"] + 1)
                 for r in rows]
        self.assertIsNone(region_flatten.first_overlap(rects))

        # The background pair, DERIVED FROM THE GOLDEN'S OWN ROWS rather than pinned at
        # (0, 0). Today every golden row says null/null and the expectation is 0/0 — the
        # same numbers the old hardcoded line carried — but the day one row names a layout
        # this comparison must not keep asserting the defaults and passing. A named layout
        # cannot be checked against the ROM without the emitter's symbol resolution, so it
        # fails LOUD here instead of silently weakening.
        for got, exp in zip(rows, want):
            with self.subTest(row=exp["index"], field="bg"):
                if exp["bg"]["layoutRef"] is None:
                    self.assertEqual((got["bg_layout"], got["bg_span"]), (0, 0),
                                     f"row {exp['index']} ({exp['id']}) defers its "
                                     f"background to the act in the golden "
                                     f"(rg_bg_layout/rg_bg_span = 0/0) but the ROM row "
                                     f"carries {got['bg_layout']:#x}/{got['bg_span']}")
                else:
                    self.fail(f"row {exp['index']} ({exp['id']}) names layout "
                              f"{exp['bg']['layoutRef']!r} with span "
                              f"{exp['bg']['span']!r}, and this ROM comparison has no way "
                              f"to resolve a layout id to the blob address the row carries "
                              f"({got['bg_layout']:#x}) — the emitter parcel owes that "
                              f"resolution, exactly as it does for rg_parallax's "
                              f"EditorSceneBinding_* names. A measurement that cannot be "
                              f"made, not a pass.")


# ---------------------------------------------------------------------------
# AN ACT WIDER THAN ITS REGION DOCUMENT (S2-COMPRESSED-ACT parcel 9)
# ---------------------------------------------------------------------------

class TestActWiderThanItsDocument(unittest.TestCase):
    """`regions.json` and the ACT stopped being the same width on 2026-09-17.

    A clip act declares its own grid (games/sonic4/data/generated/ojz/act1/act_grid.emp) and
    the S2CLIP throwaway bake does NOT run effects_gen, so the act can be 10,240 px wide with
    the shipped 6,144-wide document under it. act_descriptor.emp closes that with one appended
    `OJZ_WIDE_FILL_ROWS` region, and region_flatten's coverage step has to know — otherwise the
    build refuses a band that the ROM's own table does cover.

    THE ACT IS WIDENED THE WAY THE BAKE WIDENS IT — by emitting a wider act_grid.emp into a
    sandbox — and NOT by poking ACT_W into the bounds dict. That matters: ACT_W is the leaf
    four other bounds fold from (the camera-centre band above all), and a poked ACT_W produced
    a tree whose rows failed the reachable-edge rule instead of the coverage rule, i.e. a test
    that would have been measuring the wrong refusal.

    THE EXEMPTION IS THE SUBJECT AND ITS BOUNDARY IS WHAT THESE ROWS TEST. Three of the four
    are ways it must NOT apply; a declaration channel is a weakening unless its edges bite.
    """

    DESC_REL = ACT1_DESCRIPTOR

    def sandbox(self, grid_w, grid_h, drop_fill=False):
        """A repo whose act_grid.emp declares (grid_w, grid_h). Returns its path."""
        import act_grid
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.symlink(os.path.join(AEON, "engine"), os.path.join(d, "engine"))
        rel_dir = os.path.dirname(self.DESC_REL)
        os.makedirs(os.path.join(d, rel_dir), exist_ok=True)
        src = open(os.path.join(AEON, self.DESC_REL)).read()
        if drop_fill:
            # The declaration act_bounds looks for, removed. Same band, no fill.
            src = src.replace("const OJZ_WIDE_FILL_ROWS: array = if ACT_W > OJZ_AUTHORED_ACT_W {",
                              "const OJZ_WIDE_FILL_ROWS: array = if 0 == 1 {")
        open(os.path.join(d, self.DESC_REL), "w").write(src)
        os.makedirs(os.path.join(d, os.path.dirname(act_grid.ACT_GRID_EMP.replace(
            AEON + os.sep, ""))), exist_ok=True)
        act_grid.emit(grid_w, grid_h,
                      os.path.join(d, act_grid.ACT_GRID_EMP.replace(AEON + os.sep, "")))
        return d

    def grid(self):
        """The shipped act's grid, read where the engine reads it."""
        import act_grid
        return act_grid.descriptor_grid()

    def test_a_wider_act_is_covered_by_the_descriptors_fill_row(self):
        gw, gh = self.grid()
        d = self.sandbox(gw + 2, gh)
        b = region_flatten.act_bounds(self.DESC_REL, aeon=pathlib.Path(d))
        self.assertTrue(b["WIDE_FILL"], "the descriptor's fill declaration was not found; "
                                        "this row would be testing nothing")
        rows = region_flatten.flatten(golden_doc()["regions"], b, where="widened")
        self.assertEqual(len(rows), len(golden_doc()["regions"]))

    def test_the_exemption_needs_the_declaration_to_be_IN_the_descriptor(self):
        """WIDE_FILL is read out of act_descriptor.emp by act_bounds, exact in shape. With the
        declaration gone the same band is a hole again, which is what it would be."""
        gw, gh = self.grid()
        d = self.sandbox(gw + 2, gh, drop_fill=True)
        b = region_flatten.act_bounds(self.DESC_REL, aeon=pathlib.Path(d))
        self.assertFalse(b["WIDE_FILL"])
        with self.assertRaises(region_flatten.RuleError) as e:
            region_flatten.flatten(golden_doc()["regions"], b, where="widened")
        self.assertIn("belong to no region", str(e.exception))

    def test_the_exemption_does_not_cover_an_INTERIOR_hole(self):
        """One document row removed. The trailing band is still exempt-shaped, but the holes
        no longer tile it alone, so the whole thing refuses — the case that matters most,
        because an interior hole beside a legitimate band is how this would go quiet."""
        gw, gh = self.grid()
        d = self.sandbox(gw + 2, gh)
        b = region_flatten.act_bounds(self.DESC_REL, aeon=pathlib.Path(d))
        doc = golden_doc()
        del doc["regions"][1]
        with self.assertRaises(region_flatten.RuleError) as e:
            region_flatten.flatten(doc["regions"], b, where="widened")
        self.assertIn("belong to no region", str(e.exception))

    def test_the_exemption_does_not_cover_a_TALLER_act(self):
        """The fill row spans the act's full height, so a taller act's bottom band is not
        inside it. Those holes are not at or past the document's right edge and the exemption
        must not reach them."""
        gw, gh = self.grid()
        d = self.sandbox(gw + 2, gh + 1)
        b = region_flatten.act_bounds(self.DESC_REL, aeon=pathlib.Path(d))
        with self.assertRaises(region_flatten.RuleError) as e:
            region_flatten.flatten(golden_doc()["regions"], b, where="widened")
        self.assertIn("belong to no region", str(e.exception))


if __name__ == "__main__":
    unittest.main()
