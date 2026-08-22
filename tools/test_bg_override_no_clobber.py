"""png_to_bg_override.py must not silently destroy keys already in the override file.

The defect: the tool wrote games/sonic4/data/editor_bg_override.json as a
whole-file overwrite that never read it. `out` was built as a fresh dict
({"layout", "tiles"}, plus {"palette", "palette_line"} only when stamping), so
an EXTRACT+stamp run followed by an ordinary lock-mode re-import silently threw
the stamped BG palette away -- on a path that ships, because
inject_editor_bg.py consumes `palette`/`palette_line` and stamps them into
ojz_palette.bin. The same mechanism destroys `anims` (BgAnim bands), which
inject_editor_bg.py also already consumes.

Two obligations are tested here:
  1. The tool's OWN keys survive its OWN modes (palette carried through a
     non-stamping run; a stamping run's fresh values win).
  2. Any key the tool does NOT own is a LOUD REFUSAL -- non-zero exit naming
     the key -- never a silent overwrite and never a silent merge. Per-key
     ownership of this file is PARKED for the repo owner; refusal takes
     neither side of that ruling.

The owned-key set asserted below is DERIVED by running the tool in both of its
modes and unioning the keys it actually emits -- never copied from a doc.
"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import png_to_bg_override as tool


# A 64x64 PNG: 8 vertical 8px stripes, so 8 distinct colours (<= 16, so EXTRACT
# mode accepts it) and width 64 divides the 512px plane (no seam gate trip).
_STRIPES = [(0, 0, 0), (34, 34, 34), (68, 68, 68), (102, 102, 102),
            (136, 136, 136), (170, 170, 170), (204, 204, 204), (255, 255, 255)]

_PAL_LINE = 3
# The palette a lock-mode run is allowed to carry is exactly the one it
# quantised against, so it is DERIVED from GEN_PALETTE rather than invented.
_PALETTE = tool.gen_palette_line_words(_PAL_LINE)


def _write_png(path):
    a = np.zeros((64, 64, 3), np.uint8)
    for i, c in enumerate(_STRIPES):
        a[:, i * 8:(i + 1) * 8] = c
    Image.fromarray(a).save(path)


def _run(override_path, png_path, extra_argv=()):
    """Run the tool's main() against override_path. Returns captured stdout."""
    saved_override, saved_argv = tool.OVERRIDE, sys.argv
    tool.OVERRIDE = override_path
    sys.argv = ["png_to_bg_override.py", png_path] + list(extra_argv)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            tool.main()
    finally:
        tool.OVERRIDE, sys.argv = saved_override, saved_argv
    return buf.getvalue()


class BgOverrideNoClobber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = __import__("tempfile").TemporaryDirectory()
        cls.png = os.path.join(cls._tmp.name, "bg.png")
        _write_png(cls.png)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _override(self, name, payload):
        p = os.path.join(self._tmp.name, name)
        with open(p, "w") as f:
            json.dump(payload, f)
        return p

    # ---- the owned-key set, derived from the tool's own emissions -------------

    def test_owned_keys_match_what_the_tool_emits(self):
        """OWNED_KEYS == union of keys the tool writes across BOTH its modes."""
        lock = self._override("derive_lock.json", {})
        _run(lock, self.png)
        lock_keys = set(json.load(open(lock)))

        extract = self._override("derive_extract.json", {})
        _run(extract, self.png, ["--new-palette"])
        extract_keys = set(json.load(open(extract)))

        derived = lock_keys | extract_keys
        self.assertEqual(
            set(tool.OWNED_KEYS), derived,
            f"OWNED_KEYS {sorted(tool.OWNED_KEYS)} disagrees with the keys the "
            f"tool actually emits {sorted(derived)}")

    # ---- 1. the tool's own keys survive its own modes -------------------------

    def test_lock_mode_preserves_stamped_palette_as_bytes_on_disk(self):
        """A non-stamping run must not destroy a palette an earlier run stamped."""
        p = self._override("palette.json", {
            "layout": [0], "tiles": [], "palette": _PALETTE, "palette_line": _PAL_LINE})
        _run(p, self.png)                      # lock mode: nothing stamped

        raw = open(p, "rb").read()
        self.assertIn(b'"palette"', raw,
                      "lock-mode run destroyed the stamped palette on disk")
        self.assertIn(b'"palette_line"', raw,
                      "lock-mode run destroyed palette_line on disk")
        data = json.loads(raw)
        self.assertEqual(data["palette"], _PALETTE)
        self.assertEqual(data["palette_line"], _PAL_LINE)
        # and it really did do its job
        self.assertEqual(len(data["layout"]), tool.PLANE_W * tool.PLANE_H)

    def test_palette_that_disagrees_with_gen_palette_is_refused(self):
        """Carrying a palette the art was not quantised against is refused.

        Lock mode quantises to GEN_PALETTE, which ojz_strip_gen.py re-copies
        from sonic_hack every build. Retaining a stale palette would restamp
        colours the new art was never fitted to -- silently wrong, just in the
        opposite direction from losing it.
        """
        stale = [(w ^ 0x0E0) & 0xFFFF for w in _PALETTE]
        self.assertNotEqual(stale, _PALETTE)
        p = self._override("stale_pal.json", {
            "layout": [0], "tiles": [], "palette": stale, "palette_line": _PAL_LINE})
        with self.assertRaises(SystemExit) as cm:
            _run(p, self.png)
        self.assertIn("does not match", str(cm.exception.code))

    def test_stamping_mode_overwrites_the_palette(self):
        """When the run IS stamping, the fresh values win -- that is the job."""
        p = self._override("restamp.json", {
            "layout": [0], "tiles": [], "palette": _PALETTE, "palette_line": _PAL_LINE})
        _run(p, self.png, ["--new-palette", "--pal-line", "2"])

        data = json.load(open(p))
        self.assertEqual(data["palette_line"], 2)
        self.assertNotEqual(data["palette"], _PALETTE,
                            "a stamping run must replace the old palette")
        self.assertEqual(len(data["palette"]), 16)

    # ---- 2. keys the tool does not own are a loud refusal ---------------------

    def test_unknown_key_anims_refuses_loudly_and_leaves_the_file_intact(self):
        """`anims` (BgAnim bands) must stop the tool, not be silently erased."""
        payload = {"layout": [0], "tiles": [],
                   "anims": [{"slot_base": 0, "cols": 2, "rows": 2}]}
        p = self._override("anims.json", payload)
        before = open(p, "rb").read()

        with self.assertRaises(SystemExit) as cm:
            _run(p, self.png)

        code = cm.exception.code
        self.assertNotEqual(code, 0, "refusal must be a non-zero exit")
        self.assertIn("anims", str(code),
                      f"the refusal must NAME the offending key; got: {code!r}")
        self.assertEqual(open(p, "rb").read(), before,
                         "a refusing run must not modify the file at all")

    def test_unknown_key_legacy_anim_also_refuses(self):
        """inject_editor_bg.py still honours the legacy single-band `anim`."""
        p = self._override("anim.json", {
            "layout": [0], "tiles": [], "anim": {"slot_base": 0}})
        with self.assertRaises(SystemExit) as cm:
            _run(p, self.png)
        self.assertIn("anim", str(cm.exception.code))

    def test_arbitrary_unrecognised_key_refuses(self):
        """Refusal is the default for anything unowned, not an `anims` special case."""
        p = self._override("weird.json", {
            "layout": [0], "tiles": [], "some_future_key": 1})
        with self.assertRaises(SystemExit) as cm:
            _run(p, self.png)
        self.assertIn("some_future_key", str(cm.exception.code))

    def test_the_real_historical_loss_is_now_refused(self):
        """Replay the actual regression: the b0e5a661 file with its two bands.

        This is the file OJZ shipped before dd93a840 -- the commit that added
        png_to_bg_override.py and ran it, silently deleting both bands. Running
        the tool over that exact content must now STOP instead.
        """
        import subprocess
        blob = subprocess.run(
            ["git", "cat-file", "blob",
             "33892d82c95d61a9214cb449fa7c67f683247ad3"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True)
        if blob.returncode != 0:
            self.skipTest("historical blob not present in this clone")
        historical = json.loads(blob.stdout)
        self.assertEqual(len(historical["anims"]), 2, "fixture must carry both bands")

        p = self._override("historical.json", historical)
        before = open(p, "rb").read()
        with self.assertRaises(SystemExit) as cm:
            _run(p, self.png)
        self.assertIn("anims", str(cm.exception.code))
        self.assertEqual(open(p, "rb").read(), before,
                         "the bands must still be on disk after the refusal")

    def test_out_flag_redirects_and_leaves_the_live_file_alone(self):
        """--out is the escape hatch, so a refusal never forces a deletion."""
        live = self._override("live_with_anims.json", {
            "layout": [0], "tiles": [], "anims": [{"slot_base": 0}]})
        before = open(live, "rb").read()
        elsewhere = os.path.join(self._tmp.name, "redirected.json")

        _run(live, self.png, ["--out", elsewhere])

        self.assertEqual(open(live, "rb").read(), before,
                         "--out must not touch the live override file")
        self.assertEqual(set(json.load(open(elsewhere))), {"layout", "tiles"})

    # ---- 3. the write is atomic ----------------------------------------------

    def test_write_leaves_no_temp_file_behind(self):
        """_atomic_write idiom: tmp sibling is renamed, never left in the tree."""
        d = os.path.join(self._tmp.name, "atomic")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "override.json")
        with open(p, "w") as f:
            json.dump({}, f)
        _run(p, self.png)
        self.assertEqual(sorted(os.listdir(d)), ["override.json"],
                         "a temp file survived the write")

    def test_missing_override_file_is_not_an_error(self):
        """First-ever run has nothing to preserve and must still work."""
        p = os.path.join(self._tmp.name, "does_not_exist_yet.json")
        self.assertFalse(os.path.exists(p))
        _run(p, self.png)
        self.assertEqual(set(json.load(open(p))), {"layout", "tiles"})


class ForestBgGenNoClobber(unittest.TestCase):
    """The THIRD writer of this file gets the same treatment.

    tools/forest_bg_gen.py authors layout/tiles/anims and used to json.dump a
    fresh dict over the file, destroying palette/palette_line in the opposite
    direction. It is the tool that authored the bands dd93a840 deleted.
    """

    TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forest_bg_gen.py")

    def _run(self, out_path):
        import subprocess
        env = dict(os.environ, BG_OUT=out_path)
        return subprocess.run([sys.executable, self.TOOL], env=env,
                              capture_output=True, text=True)

    def test_refuses_to_destroy_a_stamped_palette(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "override.json")
            payload = {"layout": [0], "tiles": [],
                       "palette": [0] * 16, "palette_line": 2}
            with open(p, "w") as f:
                json.dump(payload, f)
            before = open(p, "rb").read()

            r = self._run(p)
            self.assertNotEqual(r.returncode, 0, "refusal must be a non-zero exit")
            self.assertIn("palette", r.stderr)
            self.assertEqual(open(p, "rb").read(), before,
                             "a refusing run must not modify the file")

    def test_generates_normally_into_a_clean_destination(self):
        """The refusal must not have broken the generator's actual job."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "override.json")
            r = self._run(p)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.load(open(p))
            self.assertEqual(set(data), {"layout", "tiles", "anims"})
            # and what it emits satisfies the coherence invariant
            import inject_editor_bg
            inject_editor_bg.validate_band_coherence(data["anims"], data["tiles"])


if __name__ == "__main__":
    unittest.main()
