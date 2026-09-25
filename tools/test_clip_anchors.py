"""tools/clip_anchors.py and bganim_room's --anchor-overlay (d-35-revised, clip-overlay-file).

Hermetic: every file is written into a temp dir except the two LIVE reads that are the
point (build.sh's clip shape names, and the committed anchors.toml against map.toml).
Expectations are computed from the rule function and map.toml's own rows, never pinned.

RUNNER: build.sh's pre-build tool-suite lane (`pytest tools -m "not needs_build"`),
build-fatal, every shape; picked up by the directory sweep. The in-build half, on a real
clip ROM, is `tools/clip_anchors.py` itself, run by build.sh after `sigil build` on S2CLIP.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bganim_room  # noqa: E402
import clip_anchors  # noqa: E402

AEON = clip_anchors.AEON
LIVE_CLIPS = os.path.join(AEON, clip_anchors.CLIPS_REL)


def _measure(end, crc="00000000", size=0):
    return {"packed_end": end, "rom_crc": crc, "rom_size": size}


class RuleProperties(unittest.TestCase):
    def test_rule_anchor_is_the_first_bank_at_or_above_reserve_plus_grace(self):
        need = bganim_room.DATA_GROWTH_RESERVE + bganim_room.DATA_GROWTH_GRACE
        for end in (0x9A408, 0x9AF1C, 0xA0000 - need, 0xA0000 - need + 1, 0x80001):
            a = bganim_room.rule_anchor(end)
            self.assertEqual(a % bganim_room.BANK_ALIGN, 0)
            self.assertGreaterEqual(a, end + need)
            self.assertLess(a - bganim_room.BANK_ALIGN, end + need)


class RenderAndVerdict(unittest.TestCase):
    def setUp(self):
        self.map_rows = clip_anchors.map_anchor_rows(AEON)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "anchors.toml")
        # Two shapes whose rules land in different windows, so the max is meaningful.
        need = bganim_room.DATA_GROWTH_RESERVE + bganim_room.DATA_GROWTH_GRACE
        self.ends = {"s4.s2clip": 0x98000 - need - 0x10,
                     "s4.s2clip.debug": 0x98000 - need + 0x10}
        self.rules = {s: bganim_room.rule_anchor(e) for s, e in self.ends.items()}
        self.assertNotEqual(self.rules["s4.s2clip"], self.rules["s4.s2clip.debug"])

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, text=None):
        if text is None:
            text = clip_anchors.render_overlay(
                "c", {s: _measure(e) for s, e in self.ends.items()}, self.map_rows)
        with open(self.path, "w") as f:
            f.write(text)
        return text

    def test_render_takes_the_max_over_shapes_and_keeps_the_pair(self):
        self._write()
        anchors, measured, rows = clip_anchors.parse_overlay(self.path)
        want = max(self.rules.values())
        self.assertEqual(anchors["dac_banks"], want)
        self.assertEqual(anchors["sound_bank"], want + bganim_room.SOUND_BANK_OFFSET)
        self.assertEqual({s: r for s, (_e, r) in measured.items()}, self.rules)
        for name in clip_anchors.ANCHORS:
            for key in ("vma", "when"):
                self.assertEqual(rows[name].get(key), self.map_rows[name].get(key))
        # bganim_room reads the same file to the same values.
        self.assertEqual(bganim_room.load_anchor_overlay(self.path), anchors)

    def test_fresh_when_this_shapes_rule_is_the_recorded_one(self):
        self._write()
        for shape, rule in self.rules.items():
            code, problems = clip_anchors.verdict(self.path, shape, rule, self.map_rows)
            self.assertEqual((code, problems), (clip_anchors.FRESH, []))

    def test_stale_when_the_data_grew_or_shrank_across_a_bank(self):
        self._write()
        for delta, word in ((bganim_room.BANK_ALIGN, "GREW"), (-bganim_room.BANK_ALIGN, "SHRANK")):
            code, problems = clip_anchors.verdict(
                self.path, "s4.s2clip", self.rules["s4.s2clip"] + delta, self.map_rows)
            self.assertEqual(code, clip_anchors.STALE)
            self.assertTrue(any(word in p for p in problems), problems)

    def test_stale_when_hand_edited(self):
        text = self._write()
        want = max(self.rules.values())
        edited = text.replace(f"at = 0x{want:X}", f"at = 0x{want + 0x8000:X}", 1)
        self.assertNotEqual(edited, text)
        self._write(edited)
        code, problems = clip_anchors.verdict(self.path, "s4.s2clip",
                                              self.rules["s4.s2clip"], self.map_rows)
        self.assertEqual(code, clip_anchors.STALE)
        self.assertTrue(any("max of its own" in p for p in problems), problems)

    def test_stale_without_a_measured_line_or_for_an_unrecorded_shape(self):
        text = self._write()
        bare = "\n".join(ln for ln in text.splitlines() if not ln.startswith("# measured:"))
        self._write(bare + "\n")
        code, problems = clip_anchors.verdict(self.path, "s4.s2clip",
                                              self.rules["s4.s2clip"], self.map_rows)
        self.assertEqual(code, clip_anchors.STALE)
        self.assertTrue(any("no `# measured:`" in p for p in problems), problems)

    def test_stale_when_a_row_changes_more_than_the_position(self):
        text = self._write()
        self.assertIn('when = "sound_on"', text)
        self._write(text.replace('when = "sound_on"', 'when = "sound_off"', 1))
        code, problems = clip_anchors.verdict(self.path, "s4.s2clip",
                                              self.rules["s4.s2clip"], self.map_rows)
        self.assertEqual(code, clip_anchors.STALE)
        self.assertTrue(any("when" in p for p in problems), problems)


class BganimRoomOverlay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.map = os.path.join(AEON, clip_anchors.MAP_REL)

    def tearDown(self):
        self.tmp.cleanup()

    def _ov(self, text):
        p = os.path.join(self.tmp.name, "o.toml")
        with open(p, "w") as f:
            f.write(text)
        return p

    def test_overlay_replaces_by_name_and_leaves_the_rest(self):
        canon = {n: bganim_room.anchor_addr(self.map, n) for n in clip_anchors.ANCHORS}
        moved = canon["dac_banks"] + 0x18000
        ov = bganim_room.load_anchor_overlay(self._ov(
            f'[[anchor]]\nname = "dac_banks"\nat = 0x{moved:X}\nwhen = "sound_on"\n'))
        self.assertEqual(bganim_room.anchor_addr(self.map, "dac_banks", ov), moved)
        self.assertEqual(bganim_room.anchor_addr(self.map, "sound_bank", ov),
                         canon["sound_bank"])
        plain = bganim_room.declared_addresses(self.map)
        over = bganim_room.declared_addresses(self.map, ov)
        self.assertIn((canon["dac_banks"], "[[anchor]] dac_banks"), plain)
        self.assertNotIn(canon["dac_banks"], [a for a, w in over if "dac_banks" in w])
        self.assertIn((moved, "[[anchor]] dac_banks (overlay)"), over)
        self.assertEqual(len(plain), len(over))

    def test_overlay_refusals(self):
        for text in ("", "x = 1\n", '[[anchor]]\nname = "a"\n',
                     '[[anchor]]\nname = "a"\nat = 1\n[[anchor]]\nname = "a"\nat = 2\n',
                     "not toml [[["):
            with self.assertRaises(bganim_room.Unmeasurable, msg=text):
                bganim_room.load_anchor_overlay(self._ov(text))
        with self.assertRaises(bganim_room.Unmeasurable):
            bganim_room.load_anchor_overlay(os.path.join(self.tmp.name, "absent.toml"))

    def test_cli_takes_the_switch_once(self):
        self.assertEqual(bganim_room.main(["--lst", "x.lst", "--anchor-overlay", "a",
                                           "--anchor-overlay", "b"]), 2)


class Live(unittest.TestCase):
    def test_build_sh_names_both_clip_shapes(self):
        shapes = clip_anchors.clip_shapes(AEON)
        self.assertEqual(len(shapes), 2)
        self.assertEqual(sorted(shapes, key=len)[1], sorted(shapes, key=len)[0] + ".debug")

    def test_every_committed_clip_overlay_is_its_own_derivation(self):
        """A hand edit to a committed anchors.toml is caught here, before any clip build:
        each recorded shape's own rule value must give a FRESH verdict."""
        map_rows = clip_anchors.map_anchor_rows(AEON)
        found = 0
        for clip in sorted(os.listdir(LIVE_CLIPS)):
            path = clip_anchors.overlay_path(clip, AEON)
            if not os.path.exists(path):
                continue
            found += 1
            _anchors, measured, _rows = clip_anchors.parse_overlay(path)
            self.assertEqual(sorted(measured), sorted(clip_anchors.clip_shapes(AEON)), path)
            for shape, (end, rule) in measured.items():
                self.assertEqual(rule, bganim_room.rule_anchor(end), (path, shape))
                code, problems = clip_anchors.verdict(path, shape, rule, map_rows)
                self.assertEqual((code, problems), (clip_anchors.FRESH, []), path)
        # Not a pin on a count: a measurement that saw no file would pass vacuously.
        self.assertGreater(found, 0, "no committed clip anchors.toml to check")


if __name__ == "__main__":
    unittest.main()
