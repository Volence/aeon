#!/usr/bin/env python3
"""Tests for `tools/effects_seam_gate.py` — the seam-reachability gate.

THE GATE'S OWN FAILURE MODE IS WHAT THESE TEST. A reachability check is easy to
write vacuously: "the module is NOT in the [module.unreachable] list" passes when
the module name is misspelled, when the warning format moves, and when the build
never ran. This gate is a PRESENCE test on a link symbol instead, which inverts
that — a wrong name fails — and the tests below pin the inversion rather than the
happy path.

The listing parse is exercised against real `EQU` rows in the format sigil emits
(`EQU NAME = $0000001F`), so a format move is caught here rather than by the gate
silently reporting "symbol absent" on a listing it could not read.
"""

import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
GATE = os.path.join(TOOLS, "effects_seam_gate.py")

sys.path.insert(0, TOOLS)
import effects_seam_gate  # noqa: E402
import effects_gen  # noqa: E402


class TestEquParse(unittest.TestCase):
    """The listing parse, against the real emitted format."""

    SAMPLE = (
        "some preamble\n"
        "EQU SceneBudget_CapsFolded = $0000001F\n"
        "EQU EditorScenes_OJZ_Act1_Count = $00000000\n"
        "EQU EditorScenes_OJZ_Act1_Bindings = $00000003\n"
        "0001A000  4E75             rts\n"
    )

    def test_it_reads_name_and_hex_value(self):
        got = {n: int(v, 16)
               for n, v in effects_seam_gate.EQU_RE.findall(self.SAMPLE)}
        self.assertEqual(got["EditorScenes_OJZ_Act1_Count"], 0)
        self.assertEqual(got["EditorScenes_OJZ_Act1_Bindings"], 3)
        self.assertEqual(got["SceneBudget_CapsFolded"], 0x1F)

    def test_it_does_not_match_disassembly_lines(self):
        self.assertNotIn("rts", dict(effects_seam_gate.EQU_RE.findall(self.SAMPLE)))


class TestGateAgainstTheRealTree(unittest.TestCase):
    """End-to-end, against the committed tree's own generated module."""

    def run_gate(self, lst):
        return subprocess.run([sys.executable, GATE, "--lst", lst],
                              capture_output=True, text=True, cwd=REPO)

    def test_a_listing_with_no_witnesses_FAILS_and_says_why(self):
        """The gate's whole subject: an unreached module defines no equates, so an
        absent witness means the descriptor's `use` edge is gone — and with it the
        elaboration of every guard in the generated module."""
        with tempfile.NamedTemporaryFile("w", suffix=".lst", delete=False) as f:
            f.write("EQU SomethingElse = $00000001\n")
            path = f.name
        try:
            p = self.run_gate(path)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("is ABSENT", p.stdout)
            self.assertIn("use` closure", p.stdout)
        finally:
            os.unlink(path)

    def test_an_UNPARSEABLE_listing_is_loud_about_being_unmeasurable(self):
        """Never render 'could not measure' as 'symbol absent'. A listing with zero
        EQU rows means the format moved; reporting a broken seam there would send
        the reader after the wrong defect entirely."""
        with tempfile.NamedTemporaryFile("w", suffix=".lst", delete=False) as f:
            f.write("no equates here at all\n")
            path = f.name
        try:
            p = self.run_gate(path)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("parsed ZERO", p.stdout)
            self.assertIn("do NOT read this as a broken seam", p.stdout)
        finally:
            os.unlink(path)

    def test_a_missing_listing_does_not_fall_back_to_reasoning(self):
        p = self.run_gate(os.path.join(tempfile.gettempdir(), "no_such_file.lst"))
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("not found", p.stdout)

    def test_a_WRONG_witness_value_fails_even_though_the_symbol_is_present(self):
        """Presence proves reachability; it does not prove the artifact carries what
        the editor inputs declare. The expected value is re-derived from
        project.json + the sidecars, never read out of the generated `.emp`, so this
        arm and the drift gate fail for genuinely different reasons."""
        names = effects_gen.act_names(REPO)
        with tempfile.NamedTemporaryFile("w", suffix=".lst", delete=False) as f:
            f.write(f"EQU {names.equ_scenes} = $00000063\n")
            f.write(f"EQU {names.equ_bindings} = $00000063\n")
            path = f.name
        try:
            p = self.run_gate(path)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("but the editor inputs say", p.stdout)
            self.assertIn("99", p.stdout)     # $63, so the gate really read it
        finally:
            os.unlink(path)

    def test_the_committed_seam_and_the_committed_generated_module_agree(self):
        """The source half of the gate, run against the real tree: the descriptor's
        import is a NAME LIST naming BOTH bindings, and every section index 0..N-1
        reaches the binding exactly once. No build needed."""
        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.DESCRIPTOR)) as f:
            desc = f.read()
        self.assertIn(f"use {names.module}.{{", desc)
        self.assertNotIn(f"use {names.module}.*", desc)
        self.assertIn(names.fn_act_default, desc)
        self.assertIn(names.fn_sec_scene, desc)
        import re
        passed = sorted(int(n) for n in re.findall(r"ojz_sec\(sec:\s*(\d+)", desc))
        self.assertEqual(passed, list(range(effects_gen.act_section_count(REPO))))


class TestPresetRecordParse(unittest.TestCase):
    """`preset_records` — paren balance, not a line regex.

    The shipped records wrap across three lines and a line-anchored pattern would see
    half of one, so the parse is the arm to break first.
    """

    SRC = (
        "pub data OJZ_Preset_Sec1: EffectsPreset = preset(pal: P, raster: R)\n"
        "pub data OJZ_Preset_Sec0:  EffectsPreset = preset(pal: P, patched: T,\n"
        "                                                  parallax: X,\n"
        "                                                  patch_world_ys: [1, 2, 3, 4])\n"
        "pub data NotAPreset: [u16; 3] = raster_program(preset(nope))\n"
    )

    def test_it_takes_the_whole_wrapped_record(self):
        recs = effects_seam_gate.preset_records(self.SRC)
        self.assertEqual(sorted(recs), ["OJZ_Preset_Sec0", "OJZ_Preset_Sec1"])
        # the third line of the wrap is inside the record, and the nested [] survives
        self.assertIn("patch_world_ys: [1, 2, 3, 4]", recs["OJZ_Preset_Sec0"])
        self.assertIn("parallax: X", recs["OJZ_Preset_Sec0"])
        # ...and the record STOPS at its own closing paren
        self.assertNotIn("NotAPreset", recs["OJZ_Preset_Sec0"])

    def test_a_preset_call_that_is_not_a_pub_data_EffectsPreset_is_not_a_record(self):
        self.assertNotIn("NotAPreset", effects_seam_gate.preset_records(self.SRC))


class TestRasterCallSiteParse(unittest.TestCase):
    """`raster_call_sites` — which presets thread the chooser, on which index."""

    FN = "ojz_act1_sec_raster"

    def test_a_literal_raster_channel_is_not_a_call_site(self):
        src = "pub data P: EffectsPreset = preset(pal: A, raster: Raster_Program_None)\n"
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN), {})

    def test_it_reads_the_index_and_notices_the_hand_argument(self):
        src = ("pub data P: EffectsPreset = preset(pal: A,\n"
               f"    raster: {self.FN}(sec: 5, hand: Raster_Program_None),\n"
               "    cycle: C)\n")
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN),
                         {"P": (5, True)})

    def test_a_missing_hand_argument_is_VISIBLE_and_not_assumed(self):
        src = f"pub data P: EffectsPreset = preset(pal: A, raster: {self.FN}(sec: 5))\n"
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN),
                         {"P": (5, False)})

    def test_the_chooser_on_some_OTHER_channel_is_not_a_raster_call_site(self):
        """`patched:` is the exclusive twin of `raster:`; a chooser threaded there is a
        different (and build-fatal) mistake, and this parse must not launder it into a
        raster binding the gate then reports as healthy."""
        # `hand: Raster_Program_None` and not `hand: 0`: a bare 0 in a `Label` argument
        # does not assemble (measured 2026-09-04), and a fixture that spells an
        # unbuildable call teaches the spelling every time someone reads the test.
        src = (f"pub data P: EffectsPreset = preset(pal: A, "
               f"patched: {self.FN}(sec: 5, hand: Raster_Program_None))\n")
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN), {})


class TestDescriptorBindingParse(unittest.TestCase):
    """`descriptor_effects_bindings` — which section points at which preset."""

    SRC = ("    ojz_sec(sec: 4, blocks: B4,\n"
           "            effects: OJZ_Preset_Depth,\n"
           "            dict_len: L),\n"
           "    ojz_sec(sec: 5, blocks: B5,\n"
           "            effects: OJZ_Preset_Sec5,\n"
           "            dict_len: L),\n"
           "    ojz_sec(sec: 6, blocks: B6,\n"
           "            dict_len: L),\n")

    def test_it_pairs_each_index_with_its_preset(self):
        got = effects_seam_gate.descriptor_effects_bindings(self.SRC)
        self.assertEqual(got, {4: "OJZ_Preset_Depth", 5: "OJZ_Preset_Sec5"})

    def test_a_section_binding_no_preset_is_ABSENT_not_None(self):
        """`sec_effects` defaults to 0 = no preset and that is legal, so section 6 must
        not appear at all — mapping it to None would make an `owners` lookup match it."""
        self.assertNotIn(6, effects_seam_gate.descriptor_effects_bindings(self.SRC))


class TestRasterSeamFaults(unittest.TestCase):
    """`raster_seam_faults` — every combination, on synthetic inputs.

    PURE ON PURPOSE. Two of these states cannot be produced by editing the real tree:
    a duplicate index needs two chooser-threaded presets (the tree has one), and the
    sidecar arm needs a `rasterRef` in a sidecar, which nothing in this tree carries
    (that is step 6's landing, and step 3's four-CRC byte-identity depends on it staying
    that way). An arm exercisable only by violating the precondition it waits on would
    never be exercised, so it is exercised here instead.
    """

    FN = "ojz_act1_sec_raster"

    def faults(self, calls, bindings, sections=9, refs=None):
        return effects_seam_gate.raster_seam_faults(
            calls, bindings, sections, refs or {}, self.FN)

    # ---- the healthy state, which is also the committed one ----
    def test_the_committed_shape_has_NO_faults(self):
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": (5, True)}, {5: "OJZ_Preset_Sec5"}), [])

    def test_a_section_bound_to_a_preset_that_does_NOT_choose_is_fine(self):
        """Most sections hand `raster:` a literal. That is what unbound looks like and
        it must not be a fault, or the gate would demand a chooser everywhere."""
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": (5, True)},
                        {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Plain",
                         7: "OJZ_Preset_Plain", 8: "OJZ_Preset_Plain"}), [])

    # ---- one arm each, firing ALONE ----
    def test_no_call_site_at_all_is_a_fault(self):
        f = self.faults({}, {5: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("nothing calls it", f[0])

    def test_a_missing_hand_argument_is_a_fault(self):
        f = self.faults({"OJZ_Preset_Sec5": (5, False)}, {5: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("NO `hand:`", f[0])

    def test_an_out_of_range_index_is_a_fault(self):
        f = self.faults({"P": (9, True)}, {9: "P"}, sections=9)
        self.assertEqual(len(f), 1)
        self.assertIn("this act has 9 sections", f[0])

    def test_a_SHARED_preset_is_a_fault_and_the_message_says_split_it(self):
        """§3.3(b), the hazard the whole split exists for: a section-keyed chooser in a
        record two sections point at gives BOTH of them sec 5's band."""
        f = self.faults({"OJZ_Preset_Sec5": (5, True)},
                        {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("SHARED by 2 sections", f[0])
        self.assertIn("Split it first", f[0])

    def test_an_index_that_disagrees_with_the_binding_is_a_fault(self):
        f = self.faults({"OJZ_Preset_Sec5": (4, True)}, {5: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("chooses on sec 4 but is bound by section(s) [5]", f[0])

    def test_a_preset_no_section_binds_is_a_fault(self):
        f = self.faults({"OJZ_Preset_Sec5": (5, True)}, {5: "OJZ_Preset_Plain"})
        self.assertEqual(len(f), 1)
        self.assertIn("NO section binds it", f[0])

    def test_two_presets_on_ONE_index_is_a_fault(self):
        """Unreachable from the real tree today — there is one chooser-threaded preset."""
        f = self.faults({"A": (5, True), "B": (5, True)}, {5: "A", 3: "B"})
        self.assertIn("both choose on sec 5", " | ".join(f))

    def test_a_sidecar_rasterRef_with_no_call_site_is_a_fault(self):
        """THE ARM THAT GOES LIVE AT STEP 6, exercised now because no sidecar in this
        tree carries the key. An author's assignment that reaches the generator but no
        `preset()` presents as an assignment that did nothing."""
        f = self.faults({"OJZ_Preset_Sec5": (5, True)}, {5: "OJZ_Preset_Sec5"},
                        refs={7: "kelp_shimmer"})
        self.assertEqual(len(f), 1)
        self.assertIn("section 7's sidecar names rasterRef 'kelp_shimmer'", f[0])

    def test_a_sidecar_rasterRef_WITH_its_call_site_is_not_a_fault(self):
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": (5, True)}, {5: "OJZ_Preset_Sec5"},
                        refs={5: "kelp_shimmer"}), [])

    # ---- the inversion: stub the checker green and the arms above must go red ----
    def test_stubbing_the_checker_to_ALWAYS_HEALTHY_breaks_these_tests(self):
        """The countermeasure of docs/EMP_PITFALLS.md §10, applied to this gate: if
        `raster_seam_faults` always returned [], every fault test above would pass a
        `[] == []` comparison it never intended. Proven here rather than assumed."""
        real = effects_seam_gate.raster_seam_faults
        try:
            effects_seam_gate.raster_seam_faults = lambda *a, **k: []
            self.assertEqual(self.faults({}, {}), [])          # would have been a fault
            with self.assertRaises(AssertionError):
                self.test_a_SHARED_preset_is_a_fault_and_the_message_says_split_it()
            with self.assertRaises(AssertionError):
                self.test_a_sidecar_rasterRef_with_no_call_site_is_a_fault()
        finally:
            effects_seam_gate.raster_seam_faults = real
        # and the real function is back
        self.assertEqual(len(self.faults({}, {})), 1)


class TestRasterSeamAgainstTheRealTree(unittest.TestCase):
    """The committed effects library really does thread the chooser. No build needed."""

    def test_the_committed_effects_library_threads_the_chooser_for_one_owned_section(self):
        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as f:
            lib = f.read()
        with open(os.path.join(REPO, effects_seam_gate.DESCRIPTOR)) as f:
            desc = f.read()
        calls = effects_seam_gate.raster_call_sites(lib, names.fn_sec_raster)
        self.assertTrue(calls, "no preset threads the raster chooser")
        self.assertEqual(
            effects_seam_gate.raster_seam_faults(
                calls,
                effects_seam_gate.descriptor_effects_bindings(desc),
                effects_gen.act_section_count(REPO),
                effects_gen.load_section_raster_refs(REPO),
                names.fn_sec_raster),
            [])

    def test_the_bound_sections_are_exactly_the_threaded_ones(self):
        """Step 5's precondition was `no sidecar carries a rasterRef`, and its own
        docstring said this test is the one step 6 must change DELIBERATELY. Step 6
        landed `ojz_sec5_showcase` on section 5, so the precondition is now false by
        design and asserting it would be asserting the absence of the feature.

        WHAT REPLACES IT IS NOT `{5: ...}` TYPED IN. The invariant that actually
        matters is the one the seam gate exists for: every section that BINDS a
        rasterRef must be a section some preset THREADS the chooser for. Typing the
        expected dict would pin today's content and go stale the first time an author
        binds a second section; deriving it from the call sites cannot. The literal
        that remains is the section index, and it is cross-checked against the
        threaded set rather than standing alone."""
        bound = effects_gen.load_section_raster_refs(REPO)
        self.assertTrue(bound, "no sidecar carries a rasterRef — step 6's band is gone")

        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as f:
            lib = f.read()
        threaded = {sec for sec, _hand in
                    effects_seam_gate.raster_call_sites(lib, names.fn_sec_raster).values()}
        self.assertTrue(
            set(bound) <= threaded,
            f"sections {sorted(set(bound) - threaded)} bind a rasterRef that no preset "
            f"threads — the generator emits the binding and nothing reads it, which "
            f"presents to the author as an assignment that did nothing")

    def test_section_5_and_6_are_the_bound_ones_and_their_ids_are_the_shipped_documents(self):
        """The content assertion, kept separate from the invariant above so a content
        change cannot look like a mechanism failure. Section 5 was the owner's ruling
        (the 38-byte split that evicts nothing); section 6 joined it at EFFECTS-W1 item
        11a's authorable half (the same split, paid again, for `base_swap`). The id must
        name a document that really ships, which is what the reachability lint would
        otherwise catch late."""
        bound = effects_gen.load_section_raster_refs(REPO)
        self.assertEqual(sorted(bound), [5, 6],
                         f"the bound sections are {sorted(bound)}, not [5, 6]")
        presets = effects_gen.load_preset_documents(REPO) \
            if hasattr(effects_gen, "load_preset_documents") else None
        if presets is not None:
            self.assertIn(bound[5], presets,
                          f"section 5 binds {bound[5]!r}, which names no shipped preset document")
            self.assertIn(bound[6], presets,
                          f"section 6 binds {bound[6]!r}, which names no shipped preset document")


class TestSourceOnlyMode(unittest.TestCase):
    """`--source-only` — the arm `FAST=1 ./build.sh` runs (walkthrough finding b4).

    FAST used to run NO part of this gate: it sets NO_LINT=1 (skipping the pytest
    lane) and the post-build invocation is under `FAST == 0`. So binding a raster
    preset to a section no preset threads the chooser for was green in the loop and
    red in the canonical build, found at landing. Steps 1/2/2b read source only, so
    they can run before the build; step 3 reads the listing and cannot.

    THE SPLIT IS THE THING BEING TESTED, in both directions. `--source-only` has to
    reach step 2b (or FAST is still blind to the class it was added for) and has to
    stop before step 3 (or it cannot run before the build at all). Asserting only the
    exit code would be satisfied by a flag that skipped everything.
    """

    def run_gate(self, *args):
        return subprocess.run([sys.executable, GATE, *args],
                              capture_output=True, text=True, cwd=REPO)

    MISSING_LST = "/nonexistent/there-is-no-listing-here.lst"

    def test_it_stops_before_the_LISTING_step(self):
        """The discriminator: point both modes at a listing that does not exist. The
        full gate must refuse (step 3 has no artifact to read); --source-only must
        not care, because it never gets there."""
        full = self.run_gate("--lst", self.MISSING_LST)
        self.assertEqual(full.returncode, 1, full.stdout)
        self.assertIn("not found", full.stdout)

        src = self.run_gate("--source-only", "--lst", self.MISSING_LST)
        self.assertEqual(src.returncode, 0,
                         f"--source-only read the listing anyway:\n{src.stdout}")

    def test_it_REACHES_the_raster_binding_step(self):
        """Not merely 'exits 0'. The line it prints must name the threaded call sites,
        which only step 2b can know — that is the step the FAST loop was missing."""
        p = self.run_gate("--source-only")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as f:
            calls = effects_seam_gate.raster_call_sites(f.read(), names.fn_sec_raster)
        self.assertTrue(calls, "the tree threads no chooser — nothing to observe here")
        for preset, (sec, _hand) in calls.items():
            self.assertIn(f"{preset}(sec: {sec})", p.stdout)

    def test_it_says_what_it_did_NOT_check(self):
        """A partial gate reporting only its green half is how a loop-level pass gets
        read as a landing-level one. The FAST banner leans on this line."""
        p = self.run_gate("--source-only")
        self.assertIn("NOT CHECKED", p.stdout)
        self.assertIn("canonical", p.stdout)

    def test_a_broken_raster_binding_FAILS_it(self):
        """The class FAST was blind to, driven through the same code path the flag
        takes. `raster_seam_faults` is the only thing between the sidecars and the
        gate's exit code, so a fault here is a `--source-only` refusal there."""
        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as f:
            calls = effects_seam_gate.raster_call_sites(f.read(), names.fn_sec_raster)
        threaded = {sec for sec, _h in calls.values()}
        sections = effects_gen.act_section_count(REPO)
        unwired = next(s for s in range(sections) if s not in threaded)
        with open(os.path.join(REPO, effects_seam_gate.DESCRIPTOR)) as f:
            bindings = effects_seam_gate.descriptor_effects_bindings(f.read())
        refs = dict(effects_gen.load_section_raster_refs(REPO))
        refs[unwired] = "cold_test_band"          # the click Aurora offers
        faults = effects_seam_gate.raster_seam_faults(
            calls, bindings, sections, refs, names.fn_sec_raster)
        self.assertTrue(faults, f"binding section {unwired} raised no fault")
        self.assertIn(f"section {unwired}'s sidecar names rasterRef 'cold_test_band'",
                      faults[0])


if __name__ == "__main__":
    unittest.main()
