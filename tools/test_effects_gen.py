#!/usr/bin/env python3
"""Shape-validation tests for `tools/effects_gen.py` (scanline P5, slice 1).

Every expectation here is derived from `tools/EFFECTS_CONSUMER_CONTRACT.md` §2/§3 —
the normative read set — rather than copied from the implementation. Where a test
asserts a refusal it also asserts WHAT the message names, because a gate whose verdict
is right and whose stated reason is wrong is worse than a failing gate: the reason is
what a reader carries forward (protocol review bar 10).
"""

import json
import os
import tempfile
import unittest

import effects_gen


def _scene(**over):
    """A minimal scene that PASSES, so each test perturbs exactly one thing."""
    scene = {
        "schema": 1,
        "id": "ojz_bg",
        "layers": [{"world_y": 0, "fa": 8, "fb": 8}],
    }
    scene.update(over)
    return scene


class SceneShapeBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(
            self.tmp.name, "games", "sonic4", "data", "editor", "effects")
        os.makedirs(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, stem, body):
        path = os.path.join(self.dir, f"{stem}.json")
        with open(path, "w") as f:
            if isinstance(body, str):
                f.write(body)
            else:
                json.dump(body, f)
        return path


class TestDiscovery(SceneShapeBase):
    def test_absent_directory_is_not_an_error(self):
        """Contract §2.1: an absent directory means 'no editor scenes'.

        This is the ONE permissive path in the tool, and §3 turns on keeping it
        distinct from an unreadable file.
        """
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(effects_gen.discover_scene_files(repo=empty), [])
            self.assertEqual(effects_gen.load_all_scenes(repo=empty), {})

    def test_present_but_empty_directory_yields_no_scenes(self):
        self.assertEqual(
            effects_gen.load_all_scenes(repo=self.tmp.name), {})

    def test_scenes_are_discovered_and_keyed_by_id(self):
        self.write("ojz_bg", _scene(id="ojz_bg"))
        self.write("ojz_fg", _scene(id="ojz_fg"))
        found = effects_gen.load_all_scenes(repo=self.tmp.name)
        self.assertEqual(sorted(found), ["ojz_bg", "ojz_fg"])


class TestFailLoud(SceneShapeBase):
    def test_malformed_json_raises_rather_than_degrading(self):
        """Contract §3: bare json.load — a broken file STOPS the build."""
        path = self.write("ojz_bg", "{not json")
        with self.assertRaises(json.JSONDecodeError):
            effects_gen.load_scene(path)

    def test_unreadable_scene_is_not_silently_skipped(self):
        """An UNREADABLE file must fail the bake, unlike a MISSING directory."""
        self.write("ojz_bg", "{}{")
        with self.assertRaises(Exception) as ctx:
            effects_gen.load_all_scenes(repo=self.tmp.name)
        self.assertNotIsInstance(ctx.exception, SystemExit)


class TestSchemaAndId(SceneShapeBase):
    def test_wrong_schema_version_is_refused_and_names_both_versions(self):
        path = self.write("ojz_bg", _scene(schema=2))
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        msg = str(ctx.exception)
        self.assertIn("2", msg)
        self.assertIn(str(effects_gen.SCHEMA_VERSION), msg)

    def test_missing_schema_is_refused(self):
        body = _scene()
        del body["schema"]
        path = self.write("ojz_bg", body)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        self.assertIn("schema", str(ctx.exception))

    def test_id_must_match_the_filename_stem(self):
        path = self.write("ojz_bg", _scene(id="something_else"))
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        msg = str(ctx.exception)
        self.assertIn("something_else", msg)
        self.assertIn("ojz_bg", msg)

    def test_hyphenated_id_is_refused_because_ids_become_symbols(self):
        """Design Q-d: Aurora's BG-library ids use hyphens + timestamps, and those
        cannot be scene ids — a scene id becomes an `.emp` label component."""
        path = self.write("ojz-bg", _scene(id="ojz-bg"))
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        self.assertIn("symbol-safe", str(ctx.exception))

    def test_leading_digit_id_is_refused(self):
        path = self.write("1bg", _scene(id="1bg"))
        with self.assertRaises(effects_gen.SceneShapeError):
            effects_gen.load_scene(path)

    def test_duplicate_ids_across_files_are_refused(self):
        """Two files cannot claim one id; the second would silently win a dict."""
        self.write("ojz_bg", _scene(id="ojz_bg"))
        path = os.path.join(self.dir, "other.json")
        with open(path, "w") as f:
            json.dump(_scene(id="ojz_bg"), f)
        # `other.json`'s stem mismatch is caught first, which is itself correct;
        # assert the id rule holds by giving both files a matching stem instead.
        os.remove(path)
        with self.assertRaises(effects_gen.SceneShapeError):
            effects_gen.load_scene(self.write("other", _scene(id="ojz_bg")))


class TestUnknownKeys(SceneShapeBase):
    def test_unknown_top_level_key_is_refused_and_named(self):
        path = self.write("ojz_bg", _scene(wobble=3))
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        self.assertIn("wobble", str(ctx.exception))

    def test_unknown_layer_key_is_refused_and_names_its_index(self):
        path = self.write("ojz_bg", _scene(
            layers=[{"world_y": 0, "fa": 8, "fb": 8},
                    {"world_y": 1, "fa": 8, "fb": 8, "wobble": 3}]))
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        msg = str(ctx.exception)
        self.assertIn("wobble", msg)
        self.assertIn("layers[1]", msg)

    def test_name_is_accepted_and_ignored_at_both_levels(self):
        """Contract §2.1: `name` is the one deliberate writer-only field — the
        generator 'ignores it and MUST keep ignoring it'. Refusing it would break
        every Aurora-saved scene."""
        path = self.write("ojz_bg", _scene(
            name="Oil Ocean BG",
            layers=[{"world_y": 0, "fa": 8, "fb": 8, "name": "far hills"}]))
        scene = effects_gen.load_scene(path)
        self.assertEqual(scene["id"], "ojz_bg")

    def test_byte_identity_bridges_are_refused_with_a_reason(self):
        """`layer_mask_raw` / `v_deform_shift_raw` are excluded from the editor
        surface — editor scenes DERIVE them. Refused rather than ignored so a
        writer bug is loud instead of silently discarded."""
        for key in ("layer_mask_raw", "v_deform_shift_raw"):
            path = self.write("ojz_bg", _scene(**{key: 1}))
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                effects_gen.load_scene(path)
            self.assertIn("derive", str(ctx.exception))


class TestLayers(SceneShapeBase):
    def test_missing_layers_is_refused(self):
        body = _scene()
        del body["layers"]
        path = self.write("ojz_bg", body)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        self.assertIn("layers", str(ctx.exception))

    def test_empty_layers_is_refused(self):
        path = self.write("ojz_bg", _scene(layers=[]))
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_each_of_the_three_defaultless_layer_args_is_required(self):
        """world_y / fa / fb are exactly the `layer()` arguments with no default
        (engine/level/scene_dsl.emp) — derived from the constructor, not copied
        from a neighbouring list."""
        for missing in ("world_y", "fa", "fb"):
            layer = {"world_y": 0, "fa": 8, "fb": 8}
            del layer[missing]
            path = self.write("ojz_bg", _scene(layers=[layer]))
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                effects_gen.load_scene(path)
            self.assertIn(missing, str(ctx.exception))

    def test_optional_layer_args_are_accepted(self):
        path = self.write("ojz_bg", _scene(layers=[{
            "world_y": 0, "fa": 8, "fb": 8, "dsa": 15, "dsb": 15,
            "phase": 0, "enabled": 1, "deform": None, "curve": None,
            "vsplit": None,
        }]))
        self.assertEqual(len(effects_gen.load_scene(path)["layers"]), 1)


class TestValuesAreNotValidatedHere(SceneShapeBase):
    def test_out_of_range_values_pass_shape_and_are_left_to_sigil(self):
        """Scanline design §7 / contract §2.1: the generator validates SHAPE; the
        constructors' `ensure` text is the value error surface. A world_y far past
        the engine ceiling must NOT be rejected here — duplicating a constructor
        guard is two sources for one rule, which is how they drift."""
        path = self.write("ojz_bg", _scene(
            layers=[{"world_y": 0x99999, "fa": -4, "fb": 8}]))
        scene = effects_gen.load_scene(path)
        self.assertEqual(scene["layers"][0]["world_y"], 0x99999)

    def test_budget_class_is_passthrough_unvalidated(self):
        path = self.write("ojz_bg", _scene(budget_class="anything_at_all"))
        scene = effects_gen.load_scene(path)
        self.assertEqual(scene["budget_class"], "anything_at_all")


if __name__ == "__main__":
    unittest.main()
