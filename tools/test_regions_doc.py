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

WHAT A GREEN HERE DOES NOT MEAN, said so nobody reads it as more:
  * Nothing in the build emits these rows. `generate()` calls `check_mode_conflict` and
    stops; act 1's table is still hand-written. The emitter is a second parcel.
  * No act in this repo has a `regions.json`, so every region-mode test below builds its
    own sandbox. The real tree exercises exactly one of these paths: the legacy arm, which
    `TestLegacyModeUnchanged` pins.
  * `bg.layoutRef` is refused for every value but the act sentinel, so the derived-span
    check (a span must equal its layout's height) is UNREACHABLE today and untested. It is
    what the parcel that opens `layoutRef` owes.

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
ACT1_DESCRIPTOR = "games/sonic4/data/levels/ojz/act1/act_descriptor.emp"
ACT1_EDITOR = "games/sonic4/data/editor/ojz/act1"

# The shared vocabulary the golden pins. NOT `.emp` symbol names: both repos have to be able
# to check these, and aurora cannot resolve an EditorSceneBinding_* label.
ROW_KEYS = ("index", "id", "x0", "x1", "y0", "y1", "preset", "sceneRef", "rasterRef")

# Everything the sandbox borrows from the real tree by SYMLINK rather than copy: the effects
# library, the scene and preset libraries, the descriptor whose `const` lines are the rules,
# and the engine constants they fold against. Only the act's editor directory is a real copy,
# because that is the one the tests mutate.
SANDBOX_LINKS = ("project.json", "engine", "games/sonic4/config",
                 "games/sonic4/data/effects", "games/sonic4/data/editor/effects",
                 "games/sonic4/data/levels")


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
        night = next(r for r in self.rows() if r["id"] == "night")
        section = 1 << 11
        self.assertLess(night["x0"], 2 * section)
        self.assertGreaterEqual(night["x1"], 2 * section)
        self.assertNotEqual(night["x0"] % section, 0)
        self.assertNotEqual((night["x1"] + 1) % section, 0)

    def test_the_golden_document_and_rows_files_agree_on_their_act(self):
        with open(GOLDEN_ROWS) as f:
            rows_doc = json.load(f)
        self.assertEqual(rows_doc["act"], golden_doc()["act"])
        self.assertEqual(len(rows_doc["rows"]), len(golden_doc()["regions"]))


# ---------------------------------------------------------------------------
# MODE
# ---------------------------------------------------------------------------

class TestLegacyModeUnchanged(unittest.TestCase):
    """The arm the real tree takes, and the one that makes this parcel reversible."""

    def test_absent_document_is_legacy_mode_and_not_an_error(self):
        self.assertFalse(effects_gen.has_act_regions())
        self.assertIsNone(effects_gen.load_act_regions())
        self.assertIsNone(effects_gen.act_region_rows())

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

    def test_a_migrated_act_does_not_bake_yet_and_the_reason_is_reels(self):
        """The finding above, asserted rather than left in a comment.

        It is written as a test so that the day the second parcel fixes the rung-1 rule,
        THIS test fails and tells its author to delete it — rather than the tree quietly
        gaining a capability nobody recorded. The assertion is on the message, because a
        bake that failed for some other reason would prove nothing about this one."""
        self.write_doc(golden_doc())
        with self.assertRaises(effects_gen.SceneShapeError) as cm:
            effects_gen.generate(repo=self.repo)
        msg = str(cm.exception)
        self.assertIn("reels", msg)
        self.assertIn("ojz_act1_depth", msg)
        self.assertIn("sceneRef", msg)

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
    def test_the_act_sentinel_and_null_are_accepted(self):
        doc = golden_doc()
        doc["regions"][0]["bg"] = {"layoutRef": "@act"}
        doc["regions"][1]["bg"] = {"layoutRef": None}
        rows = self.rows(doc)
        self.assertEqual([{k: r[k] for k in ROW_KEYS} for r in rows], golden_rows())

    def test_a_named_layout_is_refused_because_nothing_reads_it_yet(self):
        doc = golden_doc()
        doc["regions"][0]["bg"] = {"layoutRef": "ojz_cave"}
        self.refuses(doc, "ojz_cave", "NOTHING IN THE ENGINE READS IT YET")

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
# THE PER-ROW AND WHOLE-TABLE RULES
# ---------------------------------------------------------------------------

class TestRowRules(RegionSandbox):
    def test_an_overlap_is_refused_and_names_both_regions(self):
        doc = golden_doc()
        doc["regions"][1]["rect"]["w"] += 64       # sec1 eats into night
        self.refuses(doc, "sec1", "night", "overlap", resolve=False)

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

    RELEASE SHAPE ONLY, and that is not a convenience. The DEBUG ROM carries an eleventh row
    (`OJZ_E2_SNAP_ROWS`) and a shortened `sec2`, neither of which a closed regions document
    can express; comparing against it would fail for a reason that is not a flattener defect.
    The marker declares `s4.bin`/`s4.lst`, which only the plain `./build.sh` writes.

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
                         f"has {len(want)}. Eleven means this is a DEBUG image (the E2 snap "
                         f"fixture); anything else is a real disagreement and the FINDING "
                         f"is which side is wrong, not which to adjust.")

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

        # The background half is the act default on every shipped row, which is what the
        # golden says by carrying no `bg` at all. A non-zero here would mean part 2 grew a
        # consumer and this fixture went stale.
        for got, exp in zip(rows, want):
            with self.subTest(row=exp["index"], field="bg"):
                self.assertEqual((got["bg_layout"], got["bg_span"]), (0, 0),
                                 f"row {exp['index']} ({exp['id']}) carries a background "
                                 f"binding the golden does not express")


if __name__ == "__main__":
    unittest.main()
