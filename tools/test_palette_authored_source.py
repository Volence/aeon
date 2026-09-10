#!/usr/bin/env python3
"""THE ACT PALETTE HAS EXACTLY ONE WRITER, AND IT IS THE EDITOR.

WHY THIS FILE EXISTS. For six months every palette the owner picked in the editor
was discarded before it reached the ROM. `tools/ojz_strip_gen.py` `shutil.copy`-ed
the sonic_hack donor `art/palettes/OJZ.bin` over the generated `ojz_palette.bin` on
EVERY build, while `project.json`'s `zones[0].palette` pointed the editor AT THAT
GENERATED FILE. So the editor wrote a file the next build overwrote.

NOTHING REPORTED A FAILURE, AND THAT IS THE LESSON FOR THIS TEST. The save saved.
The build genuinely did regenerate the palette. And the emulator DID show the new
colour, because the editor's live preview pushes CRAM directly and never goes near
the build. THE LIVE PATH WORKING IS WHAT HID IT. A check aimed at the live preview
would have passed for six years and proved nothing, so THERE IS NO SUCH CHECK HERE:
every assertion below follows the bytes from the AUTHORED file to the GENERATED
artifact the ROM embeds.

Runner: `build.sh`'s tool-suite lane (`python3 -m pytest "${TOOLS}" -q`) collects
every `tools/test_*.py`, so these run on the canonical path of every build. They do
NOT run under `FAST=1`, which skips that lane by design.

The three obligations:
  1. The declared source is an AUTHORED file that exists and is committed.
  2. The donor is a SEED, not a per-build overwrite -- proven by mutating an
     authored palette and running the real refresh over it.
  3. A stamp from inject_editor_bg.py lands on the authored file and SURVIVES the
     next re-bake. This is the sub-case that would otherwise have shipped the same
     bug at one-CRAM-line scale.
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ojz_common
import inject_editor_bg

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJECT_JSON = os.path.join(REPO, "project.json")

#: The act this parcel covers. project.json is the authority for the path; these
#: two ids only pick which zone/act row to read, so a renamed directory fails in
#: project.json rather than here.
ZONE_INDEX, ACT_INDEX = 0, 0

#: 96 bytes = 3 CRAM lines of 16 big-endian words. DERIVED below from the file
#: itself (len % 32 == 0) rather than asserted as a literal; this constant is only
#: the CRAM line the mirror lands at, which docs/ART_PIPELINE_CONTRACT_ADDENDUM.md
#: §A1.3 fixes at 1 and inject_editor_bg's `file_line = cram_line - 1` restates.
CRAM_FIRST_LINE = 1

#: A colour that is NOT in the donor, so "the generated file happens to match"
#: cannot pass by luck. Checked against the real donor in the test that uses it.
DISTINCT_WORD = 0x0E8E   # bright magenta-ish; any value the donor lacks would do


def _project():
    with open(PROJECT_JSON) as f:
        return json.load(f)


def _declared_palette_rel():
    return _project()["zones"][ZONE_INDEX]["palette"]


def _git_tracked(abs_path):
    rel = os.path.relpath(abs_path, REPO)
    r = subprocess.run(["git", "-C", REPO, "ls-files", "--error-unmatch", rel],
                       capture_output=True, text=True)
    return r.returncode == 0


def _shaped_tree(root, zone="ojz", act="act1"):
    """A tmp tree with the ONE shape ojz_common.authored_palette_for accepts."""
    gen = os.path.join(root, "games", "sonic4", "data", "generated", zone, act)
    ed = os.path.join(root, "games", "sonic4", "data", "editor", zone, act)
    os.makedirs(gen)
    os.makedirs(ed)
    return gen, os.path.join(ed, ojz_common.AUTHORED_PALETTE_NAME)


class DeclaredSource(unittest.TestCase):
    """1. project.json points the editor at an AUTHORED file, and it is committed."""

    def test_declared_palette_is_under_data_editor(self):
        """`data/editor/` specifically, and the reason is not cosmetic.

        tools/level_staleness.py's `editor_sources()` covers that whole tree
        (`games/<game>/data/editor`), so an authored palette there makes the
        staleness gate SEE a palette edit and re-bake. Anywhere else and the build
        cannot tell a palette changed at all -- which is half of how the defect
        stayed invisible. This assertion is DERIVED from that function, not from a
        hardcoded prefix, so moving the tree moves the expectation with it.
        """
        import level_staleness
        covered = [os.path.normpath(p) for p in level_staleness.editor_sources("sonic4", REPO)]
        declared = os.path.normpath(os.path.join(REPO, _declared_palette_rel()))
        self.assertTrue(
            any(declared.startswith(c + os.sep) or declared == c for c in covered),
            f"project.json's zones[{ZONE_INDEX}].palette is {_declared_palette_rel()}, "
            f"which no entry of level_staleness.editor_sources() covers ({covered}). "
            f"An edit to it would not make the build re-bake, so the ROM would keep "
            f"the previous palette -- the exact six-month defect this file guards.")

    def test_declared_palette_is_not_a_generated_artifact(self):
        rel = _declared_palette_rel()
        self.assertNotIn(
            "/generated/", "/" + rel.replace(os.sep, "/"),
            f"zones[{ZONE_INDEX}].palette points at a GENERATED artifact ({rel}). "
            f"The editor writes this path; a generator overwrites it every build.")

    def test_declared_palette_exists_and_is_committed(self):
        p = os.path.join(REPO, _declared_palette_rel())
        self.assertTrue(os.path.exists(p),
                        f"{_declared_palette_rel()} does not exist -- the editor would "
                        f"save into a directory nothing reads.")
        self.assertTrue(_git_tracked(p),
                        f"{_declared_palette_rel()} is not tracked by git, so a fresh "
                        f"clone has no palette and the seed would silently re-introduce "
                        f"the donor as the source of truth.")

    def test_declared_palette_is_whole_cram_lines(self):
        p = os.path.join(REPO, _declared_palette_rel())
        n = os.path.getsize(p)
        self.assertEqual(n % 32, 0,
                         f"{_declared_palette_rel()} is {n} bytes, not a whole number of "
                         f"16-word CRAM lines.")
        self.assertGreater(n, 0, "authored palette is empty")


class GeneratedIsAPureMirror(unittest.TestCase):
    """The committed generated artifact equals the committed authored file."""

    def test_committed_generated_matches_committed_authored(self):
        authored = os.path.join(REPO, _declared_palette_rel())
        gen = os.path.join(REPO, "games/sonic4/data/generated/ojz/act1/ojz_palette.bin")
        if not os.path.exists(gen):
            self.skipTest(f"{gen} absent -- run tools/regenerate-level.sh")
        a, g = open(authored, "rb").read(), open(gen, "rb").read()
        self.assertEqual(
            a, g,
            "the committed ojz_palette.bin does not match the committed authored "
            "palette. Either a second writer touched the generated file, or the tree "
            "needs tools/regenerate-level.sh. The generated palette is a MIRROR and "
            "nothing but ojz_common.sync_palette_to_generated may write it.")


class DonorIsASeedNotAnOverwrite(unittest.TestCase):
    """2. The end-to-end no other test performs: an authored colour reaches the
    generated artifact, and a re-bake does not revert it."""

    def _donor(self):
        d = ojz_common.DONOR_PALETTE_PATH
        if not os.path.exists(d):
            # LOUD ON UNMEASURABLE: an absent donor makes the seed half of this
            # untestable. Say so; do not pass quietly.
            self.skipTest(
                f"sonic_hack donor absent at {d} (set AEON_SONIC_HACK_DIR). The SEED "
                f"path cannot be measured on this machine.")
        return open(d, "rb").read()

    def test_seed_creates_the_authored_file_when_it_is_missing(self):
        donor = self._donor()
        with tempfile.TemporaryDirectory() as root:
            gen, authored = _shaped_tree(root)
            self.assertFalse(os.path.exists(authored))
            created = ojz_common.seed_authored_palette(authored)
            self.assertTrue(created, "seed_authored_palette did not report a creation")
            self.assertEqual(open(authored, "rb").read(), donor)

    def test_seed_never_touches_an_authored_file_that_exists(self):
        """The whole difference between a seed and the defect."""
        self._donor()
        with tempfile.TemporaryDirectory() as root:
            gen, authored = _shaped_tree(root)
            mine = bytes(range(96))
            open(authored, "wb").write(mine)
            for _ in range(3):
                created = ojz_common.seed_authored_palette(authored)
                self.assertFalse(created, "seed_authored_palette re-created an existing "
                                          "authored palette -- that is the defect.")
            self.assertEqual(open(authored, "rb").read(), mine,
                             "the donor overwrote an authored palette. This is the "
                             "six-month defect, byte for byte.")

    def test_an_authored_colour_reaches_the_generated_artifact(self):
        """MUTATION SHOWN, then followed all the way to the generated bytes.

        This is the check nothing else in the suite performs. It deliberately does
        NOT look at CRAM or at any preview: the live preview worked throughout the
        defect and would have passed this whether or not the bug existed.
        """
        donor = self._donor()
        with tempfile.TemporaryDirectory() as root:
            gen, authored = _shaped_tree(root)
            # seed, then AUTHOR a distinct colour over CRAM line 2 entry 5
            ojz_common.seed_authored_palette(authored)
            pal = bytearray(open(authored, "rb").read())
            file_line, entry = 1, 5           # CRAM line 2 = file line 1
            off = file_line * 32 + entry * 2
            before = struct.unpack_from(">H", pal, off)[0]
            self.assertNotEqual(before, DISTINCT_WORD,
                                "pick a DISTINCT_WORD the donor does not already hold")
            struct.pack_into(">H", pal, off, DISTINCT_WORD)
            open(authored, "wb").write(pal)

            # the real refresh the build runs
            seeded, out = ojz_common.refresh_act_palette(gen)
            self.assertFalse(seeded, "an existing authored palette was re-seeded")

            g = open(os.path.join(gen, "ojz_palette.bin"), "rb").read()
            self.assertEqual(g, bytes(pal),
                             "the generated palette is not the authored one")
            self.assertEqual(struct.unpack_from(">H", g, off)[0], DISTINCT_WORD,
                             "the authored colour did not reach the generated artifact")
            self.assertNotEqual(g, donor,
                                "the generated palette is still the donor -- a per-build "
                                "donor copy has been re-introduced.")

            # and it survives repetition: three re-bakes, still the authored colour
            for _ in range(3):
                ojz_common.refresh_act_palette(gen)
            g2 = open(os.path.join(gen, "ojz_palette.bin"), "rb").read()
            self.assertEqual(g2, bytes(pal), "a later re-bake reverted the colour")

    def test_missing_authored_and_missing_donor_is_a_loud_refusal(self):
        with tempfile.TemporaryDirectory() as root:
            gen, authored = _shaped_tree(root)
            missing = os.path.join(root, "no-such-donor.bin")
            with self.assertRaises(RuntimeError) as cm:
                ojz_common.seed_authored_palette(authored, donor_path=missing)
            msg = str(cm.exception)
            self.assertIn(authored, msg)
            self.assertIn(missing, msg)


class InjectStampsTheAuthoredFile(unittest.TestCase):
    """3. inject_editor_bg's BG-palette stamp survives the next re-bake.

    Under the old code the stamp went straight into the generated file, which the
    donor copy then reverted -- the workaround's own comment said so. Fixing only
    the seed would have left THIS path writing the generated file, so one CRAM line
    stayed unauthorable: the same defect at smaller blast radius, shipped by its
    own fix. The assertion that would have caught that is the last one here.
    """

    def _skip_without_donor(self):
        if not os.path.exists(ojz_common.DONOR_PALETTE_PATH):
            self.skipTest(f"sonic_hack donor absent at {ojz_common.DONOR_PALETTE_PATH}")

    def test_stamp_writes_the_authored_file_and_mirrors_it(self):
        self._skip_without_donor()
        with tempfile.TemporaryDirectory() as root:
            gen, authored = _shaped_tree(root)
            # PIPELINE ORDER: strip_gen bakes first, so the generated palette
            # already exists by the time inject runs. Establish that here, or the
            # stamp is being tested against a state the build never presents.
            ojz_common.refresh_act_palette(gen)
            words = [(0x0200 + i) for i in range(16)]
            inject_editor_bg.stamp_palette_line(gen, 2, words)

            self.assertTrue(os.path.exists(authored),
                            "the stamp did not create/write the AUTHORED palette")
            a = open(authored, "rb").read()
            g = open(os.path.join(gen, "ojz_palette.bin"), "rb").read()
            self.assertEqual(a, g, "the stamp left generated and authored diverged")
            got = list(struct.unpack_from(">16H", a, 1 * 32))   # cram 2 -> file line 1
            self.assertEqual(got, words)

    def test_a_stamped_line_survives_the_next_rebake(self):
        """THE ONE-LINE VERSION OF THE DEFECT. Red against a stamp that writes the
        generated file: the following refresh mirrors the authored palette over it
        and the stamped line is gone."""
        self._skip_without_donor()
        with tempfile.TemporaryDirectory() as root:
            gen, authored = _shaped_tree(root)
            ojz_common.refresh_act_palette(gen)      # strip_gen's bake, first
            words = [(0x0400 + i) for i in range(16)]
            inject_editor_bg.stamp_palette_line(gen, 2, words)   # then inject

            ojz_common.refresh_act_palette(gen)      # the next build's re-bake

            g = open(os.path.join(gen, "ojz_palette.bin"), "rb").read()
            got = list(struct.unpack_from(">16H", g, 1 * 32))
            self.assertEqual(
                got, words,
                "a re-bake reverted the stamped CRAM line. The stamp must write the "
                "AUTHORED palette; writing the generated file makes that one line "
                "unauthorable, which is the original defect at one-line scale.")

    def test_stamp_refuses_an_unshaped_out_dir(self):
        """LOUD ON UNMEASURABLE. A bare tmpdir has no `generated` component, so the
        authored path cannot be derived -- and a naive three-levels-up derivation
        would have written OUTSIDE the tree (tools/test_bg_emit.py rebinds OUT_DIR
        to exactly such a bare tmpdir)."""
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError) as cm:
                inject_editor_bg.stamp_palette_line(root, 2, [0] * 16)
            self.assertIn("generated", str(cm.exception))


class NoSecondDonorCopy(unittest.TestCase):
    """A source guard against re-introducing the exact regression.

    Labelled for what it is: this checks SPELLING, not behaviour -- the behavioural
    checks are above. Its value is that the defect was a single `shutil.copy` line,
    and a grep for the donor path outside ojz_common catches that line coming back
    in a form the behavioural tests would only see once the tree was already wrong.
    """

    DONOR_SPELLINGS = ('art", "palettes", "OJZ.bin', "art/palettes/OJZ.bin")
    ALLOWED = {"ojz_common.py"}          # the one place the donor path is named

    def test_no_tool_names_the_donor_palette_except_ojz_common(self):
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        offenders = []
        for name in sorted(os.listdir(tools_dir)):
            if not name.endswith(".py") or name in self.ALLOWED or name == os.path.basename(__file__):
                continue
            try:
                text = open(os.path.join(tools_dir, name), encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for spelling in self.DONOR_SPELLINGS:
                if spelling in text:
                    offenders.append(f"{name} (names {spelling!r})")
        self.assertEqual(
            offenders, [],
            "these tools name the sonic_hack donor palette directly: "
            + ", ".join(offenders) +
            ". The donor is a ONE-TIME SEED reached through "
            "ojz_common.seed_authored_palette(); a direct reference is how the "
            "six-month every-build overwrite was written in the first place.")


if __name__ == "__main__":
    unittest.main()
