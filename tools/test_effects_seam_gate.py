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

THE PRESET CHOOSERS ARE KEYED ON THE RECORD SINCE SHAPE B′ (aeon `3fc9ffa5`), and
every fixture below is written in that spelling. The five `EffectsPreset`-channel
choosers used to be called `<fn>(sec: N)` and to key on the SIDECAR INDEX; they are
now `<fn>(preset: <Record>_KEY)` and key on the `EffectsPreset` RECORD. (The scene
chooser `fn_sec_scene` is NOT part of B′ and is still section-keyed — the descriptor
tests below are unchanged for that reason.) Two consequences run through this file:

  * A fixture left in the old spelling would not merely test the old thing, it would
    test NOTHING — the parses match `preset: <name>_KEY` and return `{}` for a
    `sec: N` call whatever the rest of the pattern does, so every `assertEqual(..., {})`
    and every "no fault" case would pass vacuously. They are all re-spelled.
  * The invariant `chooser_call_faults` enforces changed KIND, not just spelling. It
    was "a preset chosen by section index must belong to exactly one region row, and
    to that index"; it is now SELF-KEYING — a record must thread its OWN key. The two
    tests whose premise died with that (the two `SHARED preset` ones) carry a comment
    at their site recording what they used to assert and why it is no longer a fault.
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

# THE ACT'S REAL CHOOSER NAMES, read once from the generator rather than typed. Every
# fixture below spells its call sites with these, so a rename in `ActNames` moves the
# fixtures with it instead of leaving them matching a function that no longer exists —
# which is exactly how the B′ re-key turned a parse test into a vacuous one.
NAMES = effects_gen.act_names(REPO)


def real_channel_calls(lib: str, names) -> dict:
    """The non-arm channels' call sites out of a real effects library, as `main` builds
    them. Walked from `SECTION_CHANNELS` rather than listed, for the reason the gate
    itself derives the required set: a seventh channel joins with no edit here."""
    return {ch.channel: effects_seam_gate.channel_call_sites(
                lib, getattr(names, ch.names_attr), ch.index_param)
            for ch in effects_gen.SECTION_CHANNELS
            if ch.channel not in effects_gen.ARM_CHANNELS}


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
        code = re.sub(r"//[^\n]*", "", desc)
        passed = sorted(int(n) for n in
                        re.findall(re.escape(names.fn_sec_scene) + r"\(sec:\s*(\d+)", code))
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
    """`raster_call_sites` — which presets thread the chooser, and on WHICH RECORD KEY.

    RE-SPELLED FOR SHAPE B′ (aeon `3fc9ffa5`). The call was `<fn>(sec: N)` and this
    parse returned the section index; it is now `<fn>(preset: <Record>_KEY)` and the
    parse returns the RECORD NAME the key spells. Leaving the fixtures in the old
    spelling would not have tested the old behaviour — the pattern requires
    `preset: <name>_KEY` and returns `{}` for a `sec:` call however broken the rest of
    it is, so the two negative cases here would have passed against any parse at all.
    """

    FN = NAMES.fn_preset_raster

    def test_a_literal_raster_channel_is_not_a_call_site(self):
        src = "pub data P: EffectsPreset = preset(pal: A, raster: Raster_Program_None)\n"
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN), {})

    def test_it_reads_the_KEYED_RECORD_and_notices_the_hand_argument(self):
        src = ("pub data P: EffectsPreset = preset(pal: A,\n"
               f"    raster: {self.FN}(preset: P_KEY, hand: Raster_Program_None),\n"
               "    cycle: C)\n")
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN),
                         {"P": ("P", True)})

    def test_it_reports_the_KEY_AS_WRITTEN_and_does_not_assume_self_keying(self):
        """The parse must report what the line SAYS, not what it should say. Self-keying
        is `chooser_call_faults`' invariant, and a parse that silently reported the
        enclosing record's name would make that invariant unfalsifiable."""
        src = ("pub data P: EffectsPreset = preset(pal: A,\n"
               f"    raster: {self.FN}(preset: Q_KEY, hand: Raster_Program_None))\n")
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN),
                         {"P": ("Q", True)})

    def test_a_missing_hand_argument_is_VISIBLE_and_not_assumed(self):
        src = (f"pub data P: EffectsPreset = preset(pal: A, "
               f"raster: {self.FN}(preset: P_KEY))\n")
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN),
                         {"P": ("P", False)})

    def test_the_chooser_on_some_OTHER_channel_is_not_a_raster_call_site(self):
        """`patched:` is the exclusive twin of `raster:`; a chooser threaded there is a
        different (and build-fatal) mistake, and this parse must not launder it into a
        raster binding the gate then reports as healthy."""
        # `hand: Raster_Program_None` and not `hand: 0`: a bare 0 in a `Label` argument
        # does not assemble (measured 2026-09-04), and a fixture that spells an
        # unbuildable call teaches the spelling every time someone reads the test.
        src = (f"pub data P: EffectsPreset = preset(pal: A, "
               f"patched: {self.FN}(preset: P_KEY, hand: Raster_Program_None))\n")
        self.assertEqual(effects_seam_gate.raster_call_sites(src, self.FN), {})
        # ...and the SAME text on the right channel IS one, so the negative above is a
        # statement about the channel rather than about an unmatchable fixture.
        self.assertEqual(
            effects_seam_gate.raster_call_sites(src.replace("patched:", "raster:"),
                                                self.FN),
            {"P": ("P", True)})


class TestDescriptorBindingParse(unittest.TestCase):
    """`descriptor_effects_bindings` — which sidecar's region row names which preset
    (painted-regions v1: region rows bind presets; sections bind none)."""

    SRC = ("comptime fn ojz_region(x0: int, effects: Label, parallax: Label = 0) -> Region {\n"
           "    return Region{ rg_effects: effects, rg_parallax: parallax }\n"
           "}\n"
           "    // quoted in prose: ojz_region(effects: OJZ_Preset_Ghost, parallax: f(sec: 7))\n"
           "    ojz_region(x0: 2048, effects: OJZ_Preset_Depth,\n"
           "               parallax: ojz_act1_sec_scene(sec: 4)),\n"
           "    ojz_region(x0: 4096, effects: OJZ_Preset_Sec5,\n"
           "               parallax: ojz_act1_sec_scene(sec: 5)),\n"
           "    ojz_region(x0: 0, effects: OJZ_Preset_Sec6),\n")

    def test_it_pairs_each_index_with_its_preset(self):
        got = effects_seam_gate.descriptor_effects_bindings(self.SRC)
        self.assertEqual(got, {4: "OJZ_Preset_Depth", 5: "OJZ_Preset_Sec5"})

    def test_a_row_keyed_on_no_sidecar_is_ABSENT_not_None(self):
        """A region row with no sidecar-keyed binding is legal, so its preset must not appear
        under any index — mapping it to None would make an `owners` lookup match it — and a
        row quoted in a comment is not a row at all."""
        got = effects_seam_gate.descriptor_effects_bindings(self.SRC)
        self.assertNotIn("OJZ_Preset_Sec6", got.values())
        self.assertNotIn(7, got)


class TestSeamFaults(unittest.TestCase):
    """`seam_faults` — every combination, on synthetic inputs.

    PURE ON PURPOSE. Several of these states cannot be produced by editing the real tree:
    a record threading ANOTHER record's key does not assemble the picture its author
    meant but assembles fine, and EVERY patched-arm state needs a `boundary` document,
    which this tree deliberately does not carry — "aeon's tree carries no boundary
    document" is a true fact about the game and a test must not falsify it. An arm
    exercisable only by violating the precondition it waits on would never be exercised,
    so it is exercised here instead. `TestBoundaryFixtureClassification` below closes the
    one gap that leaves: that a REAL boundary document, loaded through the generator's own
    reader, classifies the way these synthetic dicts assume.

    SHAPE B′ (aeon `3fc9ffa5`) MOVED THE KEY AND WITH IT SOME OF THESE PREMISES. The call
    tuples are `(RECORD NAME keyed, whether `hand:` was passed)` where they used to be
    `(section index, ...)`, `seam_faults`' fifth parameter is the library's RECORD NAMES
    where it used to be the section COUNT, and the arm partition asks `bindings[sec] in
    <chosen records>` where it used to ask `sec in <chosen indices>`. Where a premise died
    outright rather than being re-spelled, the test says so at its own site.
    """

    FN = NAMES.fn_preset_raster
    FN_PATCHED = NAMES.fn_preset_patched

    # A document dict as `document_arm` reads it. Only the presence of `boundary`
    # matters, so the rest of the shape is deliberately absent rather than faked.
    RASTER_DOC = {"bands": []}
    BOUNDARY_DOC = {"boundary": {}}

    def faults(self, calls, bindings, records=None, refs=None, presets=None, patched=None,
               channels=None):
        """`presets` DEFAULTS TO A RASTER-ARM DOCUMENT PER REF, and that default is
        stated rather than silent: every pre-2026-09-04 case in this class is a
        raster-arm one, so defaulting keeps those tests reading as what they test. The
        unknown-document arm has its own test below, so the default cannot hide it.

        `RASTER_DOC` CARRIES NO NON-ARM KEY, so it owes no non-arm chooser and
        `channels` defaulting to empty adds no fault to any pre-existing case. The
        no-chooser arm is exercised by `TestChannelFaults` below, where the documents
        carry the keys.

        THE CHOOSER NAMES ARRIVE AS `names` (2026-09-04). `FN`/`FN_PATCHED` above are read
        off that same object rather than typed, so a rename moves the fixtures and the
        message assertions together.

        `records` IS THE LIBRARY'S RECORD VOCABULARY (shape B′), and it DEFAULTS TO
        "everything this fixture mentions" rather than to a literal set. That default is
        deliberate and is derived, not typed: `chooser_call_faults`' undeclared-record arm
        must not fire incidentally in the twenty cases that are about something else, and
        a hand-typed set would go stale the moment a fixture gained a record. The arm has
        its own test below, which passes `records` explicitly, so the default cannot hide
        it."""
        refs = refs or {}
        patched = patched or {}
        if presets is None:
            presets = {pid: self.RASTER_DOC for pid in refs.values()}
        if records is None:
            records = (set(calls) | set(patched) | set(bindings.values())
                       | {keyed for keyed, _hand in calls.values()}
                       | {keyed for keyed, _hand in patched.values()})
        return effects_seam_gate.seam_faults(
            calls, patched, channels or {}, bindings, records, refs, presets, NAMES)

    # ---- the healthy state, which is also the committed one ----
    def test_the_committed_shape_has_NO_faults(self):
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5"}), [])

    def test_a_section_bound_to_a_preset_that_does_NOT_choose_is_fine(self):
        """Most sections hand `raster:` a literal. That is what unbound looks like and
        it must not be a fault, or the gate would demand a chooser everywhere."""
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Plain",
                         7: "OJZ_Preset_Plain", 8: "OJZ_Preset_Plain"}), [])

    # ---- one arm each, firing ALONE ----
    def test_no_call_site_at_all_is_a_fault(self):
        f = self.faults({}, {5: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("nothing calls it", f[0])

    def test_a_missing_hand_argument_is_a_fault(self):
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", False)},
                        {5: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("NO `hand:`", f[0])

    def test_a_key_naming_NO_DECLARED_RECORD_is_a_fault(self):
        """RE-AIMED BY SHAPE B′. This was `test_an_out_of_range_index_is_a_fault`: the
        chooser's `ensure` bounded `sec` by the act's section count, so `(sec: 9)` in a
        nine-section act was the "the key argument names nothing that exists" fault, and
        it was caught here so the message could name the preset rather than leaving the
        author with a generated file's `ensure`.

        The key is now an ordinal minted per DECLARED RECORD, so the bound is the
        library's record vocabulary instead of the section grid — the same fault, one
        vocabulary over, with the same build-fatal severity (`<Record>_KEY` for a record
        nobody declares is an unknown identifier in a generated file). `records` is passed
        explicitly here because the helper's default is "everything the fixture mentions",
        which is precisely what this arm needs to not be true."""
        f = self.faults({"P": ("P", True)}, {9: "P"}, records={"OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("is not an `EffectsPreset` record this library declares", f[0])
        self.assertIn("'P'", f[0])

    def test_a_record_threading_ANOTHER_RECORDS_key_is_a_fault(self):
        """RE-AIMED BY SHAPE B′; THE OLD PREMISE IS DEAD, NOT RELAXED.

        This test was `test_a_SHARED_preset_is_a_fault_and_the_message_says_split_it`. It
        asserted the design's §3.3(b) hazard: `Region.rg_effects` is a POINTER to a record
        several rows may share, so a SECTION-KEYED `<fn>(sec: 5)` threaded into a record
        two rows point at silently gave BOTH of them section 5's band, and the gate's
        message told the author to split the record (one 38-byte `EffectsPreset` per
        section that needs its own channel).

        THAT IS NO LONGER A FAULT, and asserting it would now be asserting a bug. The
        chooser keys on the RECORD, so two rows sharing a record get the same channels —
        which is what sharing a record MEANS, and is how a non-rectangular area is drawn
        under the regions model. The positive control below is the load-bearing half:
        the exact fixture that used to be RED is now GREEN by construction.

        WHAT REPLACED IT is `chooser_call_faults`' SELF-KEYING invariant, and it is the
        same FAMILY of failure — a record receiving another record's band, with no symptom
        but the wrong picture — one altitude down, where it is a property of a single line
        rather than of the section grid. That is what this test asserts now.
        """
        # The fault that replaced it: Sec5's own `preset()` threads Sec6's key.
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec6", True)},
                        {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Sec6"})
        self.assertEqual(len(f), 1, f)
        self.assertIn("it threads ANOTHER RECORD'S key", f[0])
        self.assertIn("would show 'OJZ_Preset_Sec6'", f[0])

        # THE DEAD PREMISE, AS AN EXECUTABLE STATEMENT. The fixture the old test asserted
        # was a fault — one record, two region rows — must now raise none at all, or B′
        # has not actually landed. A comment alone would not catch a re-introduction.
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Sec5"}), [])

    def test_the_self_keying_fault_PRESCRIBES_the_records_own_key(self):
        """RE-AIMED BY SHAPE B′, from `test_an_index_that_disagrees_with_the_binding_is_a
        _fault` — the singular half of the old `owners != [sec]` sentence ("chooses on sec
        4 but is bound by section 5"), whose successor is the same self-keying fault the
        test above fires. This one is kept distinct by asserting the message's PRESCRIPTION
        rather than its occurrence: a gate's stated reason is separately checkable from its
        verdict in this repo, and "it threads the wrong key" is only actionable if the
        sentence also names the right one."""
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Depth", True)},
                        {5: "OJZ_Preset_Sec5", 4: "OJZ_Preset_Depth"})
        self.assertEqual(len(f), 1, f)
        self.assertIn("Write `preset: OJZ_Preset_Sec5_KEY`", f[0])
        # ...and it names the foreign key it found, so the author can see the swap.
        self.assertIn("OJZ_Preset_Depth_KEY", f[0])
        # THE SENTENCE IS A PROPERTY OF THE LINE ALONE, which is the substantive half of
        # what B′ changed and is asserted rather than described: the old sentence quoted
        # the section grid ("chooses on sec 4 but is bound by section 5"), so moving the
        # bindings changed it. Move them now and the message must not move at all — a
        # message that still varied with the grid would send the author to the descriptor
        # for a defect that lives on one library line. (Compared as the whole list, so a
        # second fault appearing under the other grid is caught too.)
        self.assertEqual(
            f,
            self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Depth", True)},
                        {0: "OJZ_Preset_Sec5", 8: "OJZ_Preset_Depth"}))

    def test_a_preset_no_section_binds_is_a_fault(self):
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Plain"})
        self.assertEqual(len(f), 1)
        self.assertIn("NOTHING binds it", f[0])

    def test_two_records_keyed_on_ONE_of_them_faults_the_IMPOSTOR_only(self):
        """RE-AIMED BY SHAPE B′, from `test_two_presets_on_ONE_index_is_a_fault`. Two
        presets calling `<fn>(sec: 5)` used to be its own sentence, because one section
        index could serve only one of them and the other could never receive its band.
        A key is now a record's own name, so two records cannot legitimately collide on
        one — the shape that survives is one record threading another's key, and what
        this test adds over the two above is WHICH record the gate blames. Blaming the
        keyed record instead of the caller would send the author to edit a line that is
        correct."""
        f = self.faults({"A": ("A", True), "B": ("A", True)}, {5: "A", 3: "B"})
        self.assertEqual(len(f), 1, f)
        self.assertIn("B calls", f[0])
        self.assertIn("A_KEY", f[0])
        self.assertNotIn("A calls", f[0])

    # ---- THE ARM PARTITION (2026-09-04, RASTER-BOUNDARY-2) ----
    #
    # THREE SITUATIONS, THREE MESSAGES, and each is asserted on the sentence rather than
    # only on "some fault fired". A gate that is right for the wrong reason is a defect
    # here: "no preset threads this section" used to cover all three states below, and a
    # reader acting on it would have deleted a correct binding.

    def test_a_BOUNDARY_document_threaded_on_the_PATCHED_arm_is_NOT_a_fault(self):
        """THE BUG. A correct patched binding — the spelling this tree's own docs
        prescribe — was refused outright before the partition existed, under a message
        telling the author to thread a raster chooser that has no arm for the record."""
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Sec6"},
                        refs={5: "kelp_shimmer", 6: "the_boundary"},
                        presets={"kelp_shimmer": self.RASTER_DOC,
                                 "the_boundary": self.BOUNDARY_DOC},
                        patched={"OJZ_Preset_Sec6": ("OJZ_Preset_Sec6", False)}), [])

    def test_a_BOUNDARY_document_threaded_on_the_RASTER_arm_is_a_fault(self):
        """THE HOLE, and the reason "threaded in either arm" was rejected: this
        combination BUILDS. The raster chooser has no arm for the record, so it returns
        the `hand:` label, ep_raster is set, ep_patched stays 0, the exclusivity ensure
        passes — and the authored boundary is never installed, with no other symptom."""
        f = self.faults({"OJZ_Preset_Sec6": ("OJZ_Preset_Sec6", True)},
                        {6: "OJZ_Preset_Sec6"},
                        refs={6: "the_boundary"},
                        presets={"the_boundary": self.BOUNDARY_DOC})
        self.assertEqual(len(f), 1)
        self.assertIn("which carries `boundary`", f[0])
        self.assertIn("BUILDS AND DOES NOTHING", f[0])
        self.assertIn(f"patched: {self.FN_PATCHED}(preset: OJZ_Preset_Sec6_KEY)", f[0])

    def test_a_RASTER_document_threaded_on_the_PATCHED_arm_is_a_fault(self):
        """The other direction, and it fails DIFFERENTLY — build-fatal, not silent — so
        it gets its own sentence. Two faults fire: the wrong arm, and the `hand:`-less
        call the unarmed chooser cannot satisfy."""
        f = self.faults({}, {6: "OJZ_Preset_Sec6"},
                        refs={6: "kelp_shimmer"},
                        presets={"kelp_shimmer": self.RASTER_DOC},
                        patched={"OJZ_Preset_Sec6": ("OJZ_Preset_Sec6", False)})
        joined = " | ".join(f)
        self.assertIn("which carries no `boundary` key", joined)
        self.assertIn("does not assemble", joined)
        self.assertIn(
            f"raster: {self.FN}(preset: OJZ_Preset_Sec6_KEY, hand: Raster_Program_None)",
            joined)

    def test_a_BOUNDARY_document_threaded_on_NEITHER_arm_is_a_fault(self):
        """The third situation, and its message must name the PATCHED chooser — the
        pre-partition message named the raster one, which is the fix that cannot work.

        SECTION 6 NOW NEEDS A BINDING IN THE FIXTURE (shape B′): the chooser is keyed on
        the record, so the gate can only name the `preset()` that owes the threading if
        the descriptor says which record that section installs. A fixture without one
        fires a DIFFERENT (and correct) sentence — see
        `test_a_rasterRef_whose_section_binds_NO_RECORD_is_a_fault` below."""
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Sec6"},
                        refs={6: "the_boundary"},
                        presets={"the_boundary": self.BOUNDARY_DOC})
        self.assertEqual(len(f), 1)
        self.assertIn("owes a PATCHED binding", f[0])
        self.assertIn(
            f"no preset threads {self.FN_PATCHED}(preset: OJZ_Preset_Sec6_KEY)", f[0])
        self.assertNotIn(f"threads {self.FN}(preset: OJZ_Preset_Sec6_KEY)", f[0])

    def test_a_rasterRef_whose_section_binds_NO_RECORD_is_a_fault(self):
        """NEW WITH SHAPE B′, and it is the sentence that makes the arm partition able to
        stay silent about the grid everywhere else. A section carrying a `rasterRef` whose
        region row names no `EffectsPreset` record has no key to thread, so the document's
        channels have nowhere to land — and the gate says exactly that instead of naming a
        chooser call it cannot spell.

        TWO SENTENCES, ONE CAUSE, and that is recorded rather than smoothed over: the arm
        partition and `channel_faults` each own a message for this state, so the author
        sees it twice. It is asserted as TWO here because that is what the gate does; note
        the contrast with `test_an_UNKNOWN_document_is_left_to_the_arm_partitions_loud
        _message` next door, where `channel_faults` deliberately stays silent on the
        ground that "two messages for one cause is worse than one". Whether this state
        should follow that precedent is the gate author's call, not a test's."""
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5"},
                        refs={6: "the_boundary"},
                        presets={"the_boundary": self.BOUNDARY_DOC})
        self.assertEqual(len(f), 2, f)
        joined = " | ".join(f)
        # the arm partition's: it cannot name the `preset()` that owes the threading
        self.assertIn("which `EffectsPreset` record that section installs", joined)
        # `channel_faults`': there is no key to thread at all
        self.assertIn("there is no key to thread", joined)
        for s in f:
            self.assertIn("section 6's sidecar names rasterRef 'the_boundary'", s)

    def test_the_THREE_situations_produce_THREE_DIFFERENT_sentences(self):
        """Asserted as a set, because each message above could be checked in isolation
        and still be the same string. The verdict is the same in all three cases; the
        REASON is what the author acts on, and this repo treats a gate's stated reason
        as separately checkable from its verdict."""
        cases = {
            "threaded on raster": dict(
                calls={"P": ("P", True)}, bindings={6: "P"}, refs={6: "b"},
                presets={"b": self.BOUNDARY_DOC}),
            "threaded on neither": dict(
                calls={"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                bindings={5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Sec6"},
                refs={6: "b"}, presets={"b": self.BOUNDARY_DOC}),
            # A raster call site is present in this one only to keep the "nothing calls
            # the raster chooser" arm quiet, so the count below is about the arm
            # partition and nothing else.
            "threaded on patched": dict(
                calls={"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                bindings={5: "OJZ_Preset_Sec5", 6: "P"}, refs={6: "r"},
                presets={"r": self.RASTER_DOC}, patched={"P": ("P", True)}),
        }
        msgs = []
        for label, kw in cases.items():
            f = self.faults(**kw)
            # Indexed only after the count is asserted, so a stubbed-green checker fails
            # HERE with an AssertionError rather than an IndexError three lines down.
            self.assertEqual(len(f), 1, f"{label!r} produced {len(f)} faults, not 1")
            msgs.append(f[0])
        self.assertEqual(len(set(msgs)), 3,
                         "two of the three situations produce the SAME sentence")

    def test_an_unknown_rasterRef_document_is_LOUD_and_not_assumed_raster(self):
        """The arm is the DOCUMENT's property, so a ref naming no loadable document
        leaves this gate unable to answer. Guessing the raster arm would have been the
        convenient default and would silently re-create the bug for that section."""
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5"},
                        refs={6: "nowhere"}, presets={})
        self.assertEqual(len(f), 1)
        self.assertIn("no preset document with that id loaded", f[0])

    def test_a_preset_threading_BOTH_arms_is_a_fault(self):
        f = self.faults({"P": ("P", True)}, {6: "P"}, patched={"P": ("P", True)})
        self.assertIn("threads BOTH", " | ".join(f))

    def test_threading_ANOTHER_RECORDS_key_is_a_fault_on_the_PATCHED_arm_TOO(self):
        """RE-AIMED BY SHAPE B′; THE OLD PREMISE IS DEAD, NOT RELAXED.

        This test was `test_a_SHARED_preset_is_a_fault_on_the_PATCHED_arm_TOO`. It
        asserted that §3.3(b) — a chooser-threaded record pointed at by two region rows
        giving BOTH of them one section's band — was a property of section-keyed CHOOSING
        rather than of the raster channel, and therefore fired on `patched:` as well. Its
        real subject was the FACTORING: `chooser_call_faults` is shared by the two arms
        rather than copied, and a copied check is the one that drifts.

        A record shared by two rows is correct by construction under B′ (see the raster
        twin above for the full reasoning), so the premise is gone. The factoring is not:
        SELF-KEYING is the invariant that replaced §3.3(b) inside the same shared
        function, so this test keeps its subject by asserting the successor fault on the
        patched arm. `hand: True` here isolates it from the patched arm's own
        `hand:`-less case, which has its own test below.
        """
        f = self.faults({"A": ("A", True)}, {5: "A", 6: "P", 7: "Q"},
                        refs={6: "b"}, presets={"b": self.BOUNDARY_DOC},
                        patched={"P": ("Q", True)})
        joined = " | ".join(f)
        self.assertIn("it threads ANOTHER RECORD'S key", joined)
        self.assertIn(f"P calls {self.FN_PATCHED}(preset: Q_KEY)", joined)

        # THE DEAD PREMISE, AS AN EXECUTABLE STATEMENT, on this arm too: one record, two
        # region rows, threaded on `patched:` with its document armed — no fault at all.
        self.assertEqual(
            self.faults({"A": ("A", True)}, {5: "A", 6: "P", 7: "P"},
                        refs={6: "b"}, presets={"b": self.BOUNDARY_DOC},
                        patched={"P": ("P", True)}), [])

    def test_a_patched_call_site_for_an_UNARMED_record_is_a_fault(self):
        """`hand:` omitted and no `boundary` document bound to the record: the chooser
        returns its int default and `preset(patched:)` refuses it. Build-fatal, caught
        here so the message names the preset — the undeclared-key arm's precedent."""
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5", 6: "P"},
                        patched={"P": ("P", False)})
        self.assertIn("there is no `Patched_Program_None` to pass", " | ".join(f))

    def test_a_patched_call_site_with_a_real_hand_on_an_UNARMED_record_is_fine(self):
        """The mirror of "a section bound to a preset that does NOT choose is fine": a
        hand-authored patched program flowing through the chooser is what an unbound
        patched record looks like, and demanding a binding would be demanding the
        feature."""
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5", 6: "P"},
                        patched={"P": ("P", True)}), [])

    def test_a_sidecar_rasterRef_with_no_call_site_is_a_fault(self):
        """THE ARM THAT GOES LIVE AT STEP 6, exercised now because no sidecar in this
        tree carries the key. An author's assignment that reaches the generator but no
        `preset()` presents as an assignment that did nothing.

        Section 7's region row names a record here (shape B′): without one the gate fires
        the "no record installs that section" sentence instead, which is a different and
        separately-tested state."""
        f = self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5", 7: "OJZ_Preset_Sec7"},
                        refs={7: "kelp_shimmer"})
        self.assertEqual(len(f), 1)
        self.assertIn("section 7's sidecar names rasterRef 'kelp_shimmer'", f[0])
        self.assertIn(f"no preset threads {self.FN}(preset: OJZ_Preset_Sec7_KEY)", f[0])

    def test_a_sidecar_rasterRef_WITH_its_call_site_is_not_a_fault(self):
        self.assertEqual(
            self.faults({"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},
                        {5: "OJZ_Preset_Sec5"},
                        refs={5: "kelp_shimmer"}), [])

    # ---- the inversion: stub the checker green and the arms above must go red ----
    def test_stubbing_the_checker_to_ALWAYS_HEALTHY_breaks_these_tests(self):
        """The countermeasure of docs/EMP_PITFALLS.md §10, applied to this gate: if
        `seam_faults` always returned [], every fault test above would pass a
        `[] == []` comparison it never intended. Proven here rather than assumed.

        THE ARM-PARTITION TESTS ARE IN THE STUB SET TOO, and deliberately: the arm that
        this parcel's whole point is a POSITIVE one ("a correct patched binding raises no
        fault"), which a stubbed-green checker satisfies trivially. Its companions here
        are what make that positive mean something."""
        real = effects_seam_gate.seam_faults
        try:
            effects_seam_gate.seam_faults = lambda *a, **k: []
            self.assertEqual(self.faults({}, {}), [])          # would have been a fault
            with self.assertRaises(AssertionError):
                self.test_a_record_threading_ANOTHER_RECORDS_key_is_a_fault()
            with self.assertRaises(AssertionError):
                self.test_the_self_keying_fault_PRESCRIBES_the_records_own_key()
            with self.assertRaises(AssertionError):
                self.test_a_sidecar_rasterRef_with_no_call_site_is_a_fault()
            with self.assertRaises(AssertionError):
                self.test_a_BOUNDARY_document_threaded_on_the_RASTER_arm_is_a_fault()
            with self.assertRaises(AssertionError):
                self.test_a_BOUNDARY_document_threaded_on_NEITHER_arm_is_a_fault()
            with self.assertRaises(AssertionError):
                self.test_the_THREE_situations_produce_THREE_DIFFERENT_sentences()
        finally:
            effects_seam_gate.seam_faults = real
        # and the real function is back
        self.assertEqual(len(self.faults({}, {})), 1)


class TestChannelFaults(unittest.TestCase):
    """`channel_faults` — the FOUR non-arm choosers the same `rasterRef` binds.

    THE HOLE THESE CLOSE, stated as the measurement rather than as a design. Aurora bound
    a section-6 document carrying `boundary` + `patch_world_ys` + `patch_motion`, threaded
    the patched arm and neither patch chooser, and the build was GREEN AND BYTE-IDENTICAL
    (their `docs/reviews/2026-09-04-boundary-moving-witness.md`, lane-log `630def5c`).
    `TestAuroraNoChooserCase` below reproduces exactly that input; this class pins the
    arm's shape on synthetic documents the real tree cannot produce.

    WHY THE DOCUMENTS HERE ARE MINIMAL DICTS. `channel_faults` reads only which KEYS a
    document carries and how long its arrays are — `effects_gen.SECTION_CHANNELS`' own
    predicates — so a full document would add shape this arm never looks at.
    `TestAuroraNoChooserCase` runs a REAL document through the generator's own reader,
    which is where the "is the key where the table looks" question belongs.

    THE CALL MAP IS DOUBLY KEYED ON THE RECORD SINCE SHAPE B′ (aeon `3fc9ffa5`):
    `{RECORD the call site is in: {RECORD its `preset:` key names: {indices}}}`, where the
    inner key used to be the section index. `channel_faults` reads it SELF-KEYED —
    `.get(owner, {}).get(owner, set())` — so a record threading someone else's key does
    not also satisfy this arm and let the two faults cancel into a green pair. The
    fixtures below spell both levels with the record name for that reason.
    """

    NAMES = None            # set in setUpClass; the real act's chooser names

    @classmethod
    def setUpClass(cls):
        cls.NAMES = effects_gen.act_names(REPO)

    def faults(self, refs, presets, bindings, channels=None):
        return effects_seam_gate.channel_faults(
            channels or {}, bindings, refs, presets, self.NAMES)

    # ---- a document carrying NO non-arm key owes nothing ----
    def test_a_plain_raster_document_owes_no_non_arm_chooser(self):
        """The control. Without it, an arm that faulted unconditionally would pass every
        test below."""
        self.assertEqual(
            self.faults({5: "p"}, {"p": {"bands": []}}, {5: "OJZ_Preset_Sec5"}), [])

    # ---- the four keys, one at a time, threaded NOWHERE ----
    def one_key_unthreaded(self, ch):
        """A document carrying ONLY this channel's key, beside a raster-arm program,
        threaded nowhere. `ch.key` and NOT `ch.param`: the document key is `cycles` where
        the `preset()` parameter is `cycle`, and conflating them is exactly the mistake
        the table's two fields exist to prevent."""
        doc = {"bands": [], ch.key: [{}]}
        f = self.faults({5: "p"}, {"p": doc}, {5: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1, f)
        self.assertIn(getattr(self.NAMES, ch.names_attr), f[0])
        self.assertIn("NOWHERE", f[0])
        self.assertIn(f"carries `{ch.key}`", f[0])

    def test_each_non_arm_key_owes_its_own_chooser(self):
        """DERIVED FROM THE TABLE, NOT FROM A LIST OF FOUR. The cases are walked out of
        `effects_gen.SECTION_CHANNELS`, so a seventh channel is covered by this test on
        the commit that adds it — which is the whole point of deriving the required set.

        NO `subTest` HERE, deliberately: a `subTest` failure does not propagate out of the
        method, so the stub check below could not tell a green stub from a real pass."""
        seen = 0
        for ch in effects_gen.SECTION_CHANNELS:
            if ch.channel in effects_gen.ARM_CHANNELS:
                continue
            self.one_key_unthreaded(ch)
            seen += 1
        self.assertEqual(seen, len(effects_gen.SECTION_CHANNELS)
                         - len(effects_gen.ARM_CHANNELS))

    def test_the_fault_prescribes_the_argument_to_WRITE(self):
        """A gate's stated REASON is separately checkable from its verdict, and "the four
        required threadings are only findable by copying Sec5" is the failure this fixes."""
        doc = {"bands": [], "patch_motion": [None, None, None, None]}
        f = self.faults({5: "p"}, {"p": doc}, {5: "OJZ_Preset_Sec5"})
        self.assertEqual(len(f), 1)
        self.assertIn("patch_motion: [", f[0])
        self.assertIn(f"{self.NAMES.fn_preset_patch_motion}"
                      f"(preset: OJZ_Preset_Sec5_KEY, ch: 0, "
                      f"hand: ANCHOR_MOTION_NONE)", f[0])
        # THE ARRAY IS THE ENGINE'S ARITY, not the document's: `preset()` asserts
        # `patch_motion.len == RASTER_MAX_PATCH` at the call site, so a trimmed
        # prescription would not build. Derived, never typed — and counted over the
        # PRESCRIBED TEXT only, because the diagnosis above it names the same call once
        # more ("threads <fn>(preset: <owner>_KEY) NOWHERE") and counting the whole
        # sentence would pin arity + 1, which is a number about the prose.
        written = f[0].split("Write, inside that `preset()`:", 1)[1]
        self.assertEqual(
            written.count(f"{self.NAMES.fn_preset_patch_motion}"
                          f"(preset: OJZ_Preset_Sec5_KEY"),
            effects_gen.RASTER_MAX_PATCH)

    def test_a_threaded_channel_is_NOT_a_fault(self):
        doc = {"bands": [], "patch_motion": [None, None, None, None]}
        ch = {"patch motion": {"OJZ_Preset_Sec5":
                               {"OJZ_Preset_Sec5": {0, 1, 2, 3}}}}
        self.assertEqual(
            self.faults({5: "p"}, {"p": doc}, {5: "OJZ_Preset_Sec5"}, ch), [])

    def test_a_PARTIALLY_threaded_channel_is_a_fault_naming_the_missing_indices(self):
        """`render_module` emits one row per index the document's array reaches, so a
        call site that threads `ch: 0` alone leaves three rows emitted and unread."""
        doc = {"bands": [], "patch_motion": [None, None, None, None]}
        ch = {"patch motion": {"OJZ_Preset_Sec5": {"OJZ_Preset_Sec5": {0}}}}
        f = self.faults({5: "p"}, {"p": doc}, {5: "OJZ_Preset_Sec5"}, ch)
        self.assertEqual(len(f), 1, f)
        self.assertIn("only at ch [0]", f[0])
        self.assertIn("ch [1, 2, 3] would be", f[0])

    def test_a_SHORTER_document_array_owes_only_the_indices_it_reaches(self):
        """The other half of the index rule: the document decides which indices are
        CHOSEN, and a one-entry array does not owe channels 1-3."""
        doc = {"bands": [], "patch_motion": [None]}
        ch = {"patch motion": {"OJZ_Preset_Sec5": {"OJZ_Preset_Sec5": {0}}}}
        self.assertEqual(
            self.faults({5: "p"}, {"p": doc}, {5: "OJZ_Preset_Sec5"}, ch), [])

    def test_a_threading_on_ANOTHER_preset_does_not_count(self):
        """The act-wide reading is exactly what was green: `OJZ_Preset_Sec5` calling the
        chooser satisfied step 2b on behalf of every other section in the act."""
        doc = {"bands": [], "patch_motion": [None]}
        ch = {"patch motion": {"OJZ_Preset_Sec5": {"OJZ_Preset_Sec5": {0}}}}
        f = self.faults({6: "p"}, {"p": doc}, {6: "OJZ_Preset_Sec6"}, ch)
        self.assertEqual(len(f), 1, f)
        self.assertIn("OJZ_Preset_Sec6", f[0])

    def test_a_threading_keyed_on_ANOTHER_RECORD_does_not_count_either(self):
        """NEW WITH SHAPE B′, and it is the arm `channel_faults`' own comment names: the
        call map is read SELF-KEYED on both levels. The right record's `preset()` calling
        the chooser with the WRONG key returns the other record's rows, so accepting any
        inner key would let this fault and `chooser_call_faults`' self-keying fault cancel
        each other — two real defects reading green as a pair."""
        doc = {"bands": [], "patch_motion": [None]}
        ch = {"patch motion": {"OJZ_Preset_Sec6": {"OJZ_Preset_Sec5": {0}}}}
        f = self.faults({6: "p"}, {"p": doc}, {6: "OJZ_Preset_Sec6"}, ch)
        self.assertEqual(len(f), 1, f)
        self.assertIn("NOWHERE", f[0])

    def test_a_section_binding_NO_preset_says_so(self):
        doc = {"bands": [], "cycles": [{}]}
        f = self.faults({6: "p"}, {"p": doc}, {})
        self.assertEqual(len(f), 1, f)
        self.assertIn("no `EffectsPreset` record installs that section", f[0])

    def test_an_UNKNOWN_document_is_left_to_the_arm_partitions_loud_message(self):
        """Silence here, not a second sentence: `seam_faults` already refuses to guess an
        arm for a `rasterRef` naming no document, and two messages for one cause is worse
        than one."""
        self.assertEqual(self.faults({5: "nope"}, {}, {5: "OJZ_Preset_Sec5"}), [])

    def test_stubbing_channel_faults_GREEN_breaks_these_tests(self):
        """docs/EMP_PITFALLS.md §10 again: a stubbed-green checker must break the arms
        above, or `assertEqual(f, [])` in the positive cases means nothing."""
        real = effects_seam_gate.channel_faults
        try:
            effects_seam_gate.channel_faults = lambda *a, **k: []
            for name in ("test_each_non_arm_key_owes_its_own_chooser",
                         "test_the_fault_prescribes_the_argument_to_WRITE",
                         "test_a_PARTIALLY_threaded_channel_is_a_fault_naming_the_"
                         "missing_indices",
                         "test_a_threading_on_ANOTHER_preset_does_not_count",
                         "test_a_threading_keyed_on_ANOTHER_RECORD_does_not_count_either",
                         "test_a_section_binding_NO_preset_says_so"):
                with self.assertRaises(AssertionError, msg=name):
                    getattr(self, name)()
        finally:
            effects_seam_gate.channel_faults = real


class TestAuroraNoChooserCase(unittest.TestCase):
    """THE DECISIVE CASE, reproduced: Aurora's section-6 binding, threading none of them.

    Their packet `docs/reviews/2026-09-04-boundary-moving-witness.md` (aurora master
    `80550655`, lane-log `630def5c`) lists what section 6 needed in `ojz_effects.emp`:
    (1) `ojz_act1_sec_patched` in the editor-module import, (2)
    `patched: ojz_act1_sec_patched(sec: 6)`, (3) `patch_world_ys: [...(sec: 6, ch: 0..3,
    hand: PATCH_ANCHOR_NONE)]`, (4) `patch_motion: [...(sec: 6, ch: 0..3, hand:
    ANCHOR_MOTION_NONE)]`. (1) and (2) went red under the gate's arm partition
    (`aeb9cda7`). (3) and (4) did NOT: re-derived against the committed gate in this tree,
    `seam_faults` returned ZERO faults for this exact input.

    THE DOCUMENT IS THE COMMITTED FIXTURE, run through the generator's OWN reader, so a
    schema move that renamed or nested a key fails here instead of silently un-requiring
    the threading. Its two patch keys are transcribed from the packet's "What was
    authored" section (`patch_world_ys: [5220]`, `patch_motion: [{sweep: {amp_shift: 2,
    period_shift: 0, phase: 0}}]`) — the same transcription posture, and the same reasons
    for living in `tools/fixtures/` rather than under `games/`, as
    `TestBoundaryFixtureClassification` states.

    THE PACKET IS QUOTED IN ITS OWN SPELLING ABOVE and is deliberately NOT retro-edited:
    it is a record of what Aurora wrote on 2026-09-04, and a quote that drifts to match
    today's tree stops being evidence of anything. Shape B′ (aeon `3fc9ffa5`) re-keyed
    those four threadings from the sidecar index to the record — `ojz_act1_sec_patched`
    became `ojz_act1_preset_patched` and `(sec: 6)` became
    `(preset: OJZ_Preset_Sec6_KEY)`, `OJZ_Preset_Sec6` being the record their section 6
    binds. Nothing the measurement was ABOUT moved: the same four threadings are owed by
    the same document, and the same three were silent before the fix. `run_gate` below
    states the same thing beside the inputs it builds.
    """

    FIXTURE = os.path.join(TOOLS, "fixtures", "aurora_boundary_witness.json")

    def setUp(self):
        self.doc = effects_gen.load_preset(self.FIXTURE)
        self.names = effects_gen.act_names(REPO)
        self.refs = {6: "aurora_boundary_witness"}
        self.presets = {"aurora_boundary_witness": self.doc}
        self.bindings = {5: "OJZ_Preset_Sec5", 6: "OJZ_Preset_Sec6"}

    def run_gate(self, channels):
        # SHAPE B′: the call tuples carry the RECORD each site keys on (self-keyed, as
        # `chooser_call_faults` requires) and `seam_faults`' fifth argument is the
        # library's record vocabulary, not the section count. Aurora's threadings (2),
        # (3) and (4) are the same threadings re-keyed — `(sec: 6)` became
        # `(preset: OJZ_Preset_Sec6_KEY)` — so the input this class reproduces is
        # unchanged in everything the arm actually reads.
        records = set(self.bindings.values())
        return effects_seam_gate.seam_faults(
            {"OJZ_Preset_Sec5": ("OJZ_Preset_Sec5", True)},   # shipped raster-arm binding
            {"OJZ_Preset_Sec6": ("OJZ_Preset_Sec6", False)},  # (2), threaded correctly
            channels, self.bindings, records, self.refs, self.presets, self.names)

    def test_the_fixture_carries_the_two_patch_keys_AURORA_AUTHORED(self):
        """The transcription check for the added half, beside the boundary one next door."""
        self.assertEqual(self.doc["patch_world_ys"], [5220])
        self.assertEqual(self.doc["patch_motion"],
                         [{"sweep": {"amp_shift": 2, "period_shift": 0, "phase": 0}}])

    def test_the_document_owes_FOUR_threadings(self):
        """Threadings (2), (3), (4) are channels; (1) is the import, checked in step 2b."""
        owed = [c.channel for c in effects_gen.document_channels(self.doc)]
        self.assertEqual(sorted(owed), ["patch motion", "patch world-Y", "patched"])

    def test_threading_NONE_of_them_is_RED_and_names_BOTH_missing_choosers(self):
        f = self.run_gate({})
        self.assertEqual(len(f), 2, f)
        joined = " | ".join(f)
        self.assertIn(self.names.fn_preset_patch_world_y, joined)
        self.assertIn(self.names.fn_preset_patch_motion, joined)
        for s in f:
            self.assertIn("Write, inside that `preset()`:", s)

    def test_threading_ALL_of_them_is_GREEN(self):
        """The positive control: the fix Aurora applied must satisfy this gate, or the arm
        would demand a spelling nobody can write — the RASTER-BOUNDARY-2 failure."""
        ch = {"patch world-Y": {"OJZ_Preset_Sec6":
                                {"OJZ_Preset_Sec6": {0, 1, 2, 3}}},
              "patch motion": {"OJZ_Preset_Sec6":
                               {"OJZ_Preset_Sec6": {0, 1, 2, 3}}}}
        self.assertEqual(self.run_gate(ch), [])

    def test_the_prescribed_spelling_is_the_one_AURORA_APPLIED(self):
        """A prescription is only useful if it is the thing that works. Compared against
        their packet's list, not against this gate's own idea of it.

        RE-KEYED, NOT RE-CHOSEN (shape B′). Their packet wrote `(sec: 6, ch: 0, hand:
        PATCH_ANCHOR_NONE)`; the same call is now `(preset: OJZ_Preset_Sec6_KEY, ch: 0,
        hand: PATCH_ANCHOR_NONE)`, because `OJZ_Preset_Sec6` is the record their section 6
        binds. Everything the comparison is FOR — that the chooser, the index parameter,
        the index range and the `hand:` label are the ones they had to write — is
        unchanged. The cross-check that keeps this honest is the next test: the
        prescription is compared against a spelling the shipped library already carries
        and this repo already assembles."""
        f = self.run_gate({})
        joined = "\n".join(f)
        self.assertIn(f"{self.names.fn_preset_patch_world_y}"
                      f"(preset: OJZ_Preset_Sec6_KEY, ch: 0, "
                      f"hand: PATCH_ANCHOR_NONE)", joined)
        self.assertIn(f"{self.names.fn_preset_patch_motion}"
                      f"(preset: OJZ_Preset_Sec6_KEY, ch: 3, "
                      f"hand: ANCHOR_MOTION_NONE)", joined)

    def test_the_SHIPPED_spelling_matches_the_prescription(self):
        """The prescription is checkable against the tree rather than asserted: every call
        it prescribes for `OJZ_Preset_Sec6` is the one `OJZ_Preset_Sec5` already carries
        for itself, and that record assembles in every shape this repo builds."""
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as fh:
            lib = fh.read()
        for fn, hand in ((self.names.fn_preset_patch_world_y, "PATCH_ANCHOR_NONE"),
                         (self.names.fn_preset_patch_motion, "ANCHOR_MOTION_NONE")):
            self.assertIn(f"{fn}(preset: OJZ_Preset_Sec5_KEY, ch: 0, hand: {hand})", lib)


class TestRasterSeamAgainstTheRealTree(unittest.TestCase):
    """The committed effects library really does thread the chooser. No build needed."""

    def test_the_committed_effects_library_threads_the_chooser_for_one_owned_section(self):
        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as f:
            lib = f.read()
        with open(os.path.join(REPO, effects_seam_gate.DESCRIPTOR)) as f:
            desc = f.read()
        calls = effects_seam_gate.raster_call_sites(lib, names.fn_preset_raster)
        self.assertTrue(calls, "no preset threads the raster chooser")
        self.assertEqual(
            effects_seam_gate.seam_faults(
                calls,
                effects_seam_gate.patched_call_sites(lib, names.fn_preset_patched),
                real_channel_calls(lib, names),
                effects_seam_gate.descriptor_effects_bindings(desc),
                effects_gen.effects_library_records(names, REPO),
                effects_gen.load_section_raster_refs(REPO),
                effects_gen.load_all_presets("sonic4", REPO),
                names),
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
        threaded set rather than standing alone.

        BOTH CHOOSERS COUNT AS THREADED (2026-09-04). `threaded` was the raster call
        sites alone, which was the same blindness the gate itself carried: the first
        `boundary` document bound would have failed this test for being spelled
        correctly. The union is derived from the two parses, not typed.

        THE JOIN IS THE DESCRIPTOR'S SINCE SHAPE B′. A call site no longer names a
        section, so "is this section threaded" is no longer a set membership on the
        parses alone: it is "does the RECORD the descriptor binds to this section thread
        a chooser". The extra hop is the descriptor's region rows, read through the
        gate's own parse rather than typed, so the invariant is still derived end to
        end — and it is now a stronger statement than the old one, because a section
        bound to a record that threads nothing is caught even when some OTHER record
        threads a chooser."""
        bound = effects_gen.load_section_raster_refs(REPO)
        self.assertTrue(bound, "no sidecar carries a rasterRef — step 6's band is gone")

        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as f:
            lib = f.read()
        with open(os.path.join(REPO, effects_seam_gate.DESCRIPTOR)) as f:
            bindings = effects_seam_gate.descriptor_effects_bindings(f.read())
        threaded = set(effects_seam_gate.raster_call_sites(lib, names.fn_preset_raster))
        threaded |= set(effects_seam_gate.patched_call_sites(
            lib, names.fn_preset_patched))
        unwired = sorted(sec for sec in bound if bindings.get(sec) not in threaded)
        self.assertFalse(
            unwired,
            f"sections {unwired} bind a rasterRef, but the record each one installs "
            f"({[bindings.get(s) for s in unwired]}) threads NEITHER chooser — the "
            f"generator emits the binding and nothing reads it, which presents to the "
            f"author as an assignment that did nothing")

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
            calls = effects_seam_gate.raster_call_sites(f.read(),
                                                        names.fn_preset_raster)
        self.assertTrue(calls, "the tree threads no chooser — nothing to observe here")
        for preset, (rec, _hand) in calls.items():
            self.assertIn(f"raster {preset}(preset: {rec}_KEY)", p.stdout)

    def test_it_says_what_it_did_NOT_check(self):
        """A partial gate reporting only its green half is how a loop-level pass gets
        read as a landing-level one. The FAST banner leans on this line."""
        p = self.run_gate("--source-only")
        self.assertIn("NOT CHECKED", p.stdout)
        self.assertIn("canonical", p.stdout)

    def test_a_broken_raster_binding_FAILS_it(self):
        """The class FAST was blind to, driven through the same code path the flag
        takes. `seam_faults` is the only thing between the sidecars and the
        gate's exit code, so a fault here is a `--source-only` refusal there.

        THE UNWIRED SECTION IS CHOSEN THROUGH THE DESCRIPTOR SINCE SHAPE B′: a chooser
        call names a RECORD, so "a section no preset threads the chooser for" is a
        section whose region row installs a record that appears in neither call map.
        Derived from the two parses and the descriptor, never typed, so it still finds a
        live section on the day someone threads a chooser into another record."""
        names = effects_gen.act_names(REPO)
        with open(os.path.join(REPO, effects_seam_gate.EFFECTS_LIB)) as f:
            lib = f.read()
        calls = effects_seam_gate.raster_call_sites(lib, names.fn_preset_raster)
        patched = effects_seam_gate.patched_call_sites(lib, names.fn_preset_patched)
        threaded = set(calls) | set(patched)
        with open(os.path.join(REPO, effects_seam_gate.DESCRIPTOR)) as f:
            bindings = effects_seam_gate.descriptor_effects_bindings(f.read())
        refs = dict(effects_gen.load_section_raster_refs(REPO))
        unwired = next(s for s in sorted(bindings)
                       if s not in refs and bindings[s] not in threaded)
        refs[unwired] = "cold_test_band"          # the click Aurora offers
        presets = dict(effects_gen.load_all_presets("sonic4", REPO))
        presets["cold_test_band"] = {"bands": []}  # a RASTER-arm document
        faults = effects_seam_gate.seam_faults(
            calls, patched, real_channel_calls(lib, names), bindings,
            effects_gen.effects_library_records(names, REPO), refs, presets, names)
        self.assertTrue(faults, f"binding section {unwired} raised no fault")
        self.assertIn(f"section {unwired}'s sidecar names rasterRef 'cold_test_band'",
                      faults[0])
        # ...and the reason names the record that owes the threading, which is the only
        # thing the author can act on: the section index no longer appears in the call.
        self.assertIn(f"{names.fn_preset_raster}(preset: {bindings[unwired]}_KEY)",
                      faults[0])


class TestBoundaryFixtureClassification(unittest.TestCase):
    """A REAL `boundary` document classifies onto the patched arm.

    WHY A FIXTURE AND NOT A SYNTHETIC DICT. Every arm-partition test above asserts on
    `{"boundary": {}}`, which pins the gate's LOGIC and says nothing about whether a
    document an editor actually writes carries that key where `document_arm` looks. This
    test closes that gap by running the generator's OWN reader over a real document — the
    same `load_preset` the bake uses — so a schema move that renamed or nested the key
    fails here instead of silently reclassifying every boundary document as a raster one.

    WHY IT LIVES IN `tools/fixtures/` AND NOT UNDER `games/`. "aeon's tree carries no
    `boundary` document" is a true fact about the GAME, and this parcel must not falsify
    it to test itself: a document under `games/sonic4/data/editor/` is content, reaches
    the bake, and would move ROM bytes. A fixture is an input to a test and reaches
    nothing else.

    PROVENANCE, stated because it is not what it might look like. The pose is Aurora's,
    from their packet `docs/reviews/2026-09-04-boundary-seam-gate-conflict.md` (aurora
    `c6acf1b4`) and its sibling `2026-09-04-boundary-reels-witness.md` §4, which records
    the exact lowered call their `newBoundary()`-seeded document produced. Their
    `aurora_boundary_witness.json` itself is NOT committed at that revision — it was
    written into a disposable copy — so THIS FILE IS A TRANSCRIPTION, not their bytes.
    What makes the transcription checkable rather than asserted is the test below: it
    lowers the fixture through `render_boundary_preset` and compares against the call
    Aurora measured, character for character. If the two ever disagree, the fixture is
    wrong and this test says so.
    """

    FIXTURE = os.path.join(TOOLS, "fixtures", "aurora_boundary_witness.json")

    # Aurora's packet §4, quoted. Their document lowered to exactly this.
    AURORA_MEASURED = ("patchable(fx_tint_band(line: 100, slot: 0, pal_line: 2, "
                       "entry: 4, count: 3, sh: 1),\n    ch: 0, lo: 3, hi: 220, "
                       "offscreen_ship: 1)")

    def test_the_generators_own_reader_accepts_it(self):
        doc = effects_gen.load_preset(self.FIXTURE)
        self.assertEqual(doc["id"], "aurora_boundary_witness")

    def test_it_lowers_to_the_call_AURORA_MEASURED(self):
        """The transcription check. Not a round-trip of Aurora's writer — we do not have
        it — but a comparison against the one artifact of theirs that IS on the record."""
        doc = effects_gen.load_preset(self.FIXTURE)
        names = effects_gen.act_names(REPO)
        lowered = effects_gen.render_boundary_preset(self.FIXTURE, doc, names)
        self.assertIn(self.AURORA_MEASURED, lowered)

    def test_document_arm_puts_it_on_the_PATCHED_arm(self):
        """The one that matters to this gate, and the one a synthetic dict cannot ask."""
        doc = effects_gen.load_preset(self.FIXTURE)
        self.assertEqual(effects_seam_gate.document_arm(doc), "patched")

    def test_a_SHIPPED_document_is_on_the_RASTER_arm(self):
        """The control. Without it, `document_arm` returning "patched" unconditionally
        would pass the test above."""
        shipped = effects_gen.load_all_presets("sonic4", REPO)
        self.assertTrue(shipped, "no preset documents ship — nothing to control against")
        for pid, doc in shipped.items():
            self.assertEqual(effects_seam_gate.document_arm(doc), "raster",
                             f"{pid} classifies as patched; this tree is supposed to "
                             f"carry no `boundary` document")


if __name__ == "__main__":
    unittest.main()
