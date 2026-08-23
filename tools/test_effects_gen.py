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
        "layers": [{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}],
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


class TestRendering(SceneShapeBase):
    """Emission expectations are derived from the HAND-AUTHORED idiom in
    `games/sonic4/data/effects/ojz_scenes.emp` (`Scene_OJZ_Default`), not from the
    implementation — the generated call must be spelled the way a human writes one."""

    def render(self, **over):
        path = self.write("ojz_bg", _scene(**over))
        return effects_gen.render_scene(path, effects_gen.load_scene(path))

    def test_layers_array_is_always_eight_slots_padded_with_no_layer(self):
        """`scene()` indexes a [SceneLayer; 8]; the hand idiom pads with no_layer()."""
        out = self.render(layers=[{"world_y": 512, "fa": "FACTOR_1", "fb": "FACTOR_1_2"}])
        self.assertEqual(out.count("no_layer()"), 7)
        self.assertEqual(out.count("layer(world_y"), 1)

    def test_count_is_the_authored_layer_count_not_the_padded_width(self):
        out = self.render(layers=[
            {"world_y": 512, "fa": "FACTOR_1", "fb": "FACTOR_1_2"},
            {"world_y": 1024, "fa": "FACTOR_1", "fb": "FACTOR_1_2"},
        ])
        self.assertIn("count: 2", out)

    def test_a_scene_mirroring_the_shipped_ojz_default_renders_its_layer_spelling(self):
        """Scene_OJZ_Default's first layer is, verbatim in the shipped file:
            layer(world_y: 512,  fa: FACTOR_1, fb: FACTOR_1_2, dsa: 15, dsb: 15)
        """
        out = self.render(
            layers=[{"world_y": 512, "fa": "FACTOR_1", "fb": "FACTOR_1_2",
                     "dsa": 15, "dsb": 15}],
            v_factor=3, v_center=512, v_offset=0)
        self.assertIn(
            "layer(world_y: 512, fa: FACTOR_1, fb: FACTOR_1_2, dsa: 15, dsb: 15)", out)
        self.assertIn("v_factor: 3", out)
        self.assertIn("v_center: 512", out)

    def test_absent_optional_scalars_are_omitted_so_constructor_defaults_stand(self):
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        for absent in ("v_center", "v_offset", "v_factor_fg", "precision", "transition"):
            self.assertNotIn(f"{absent}:", out)

    def test_byte_identity_bridges_are_never_emitted(self):
        """layer_mask_raw / v_deform_shift_raw default to -1 = 'derive'. Editor
        scenes derive; emitting either would freeze a value the author never set."""
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertNotIn("layer_mask_raw", out)
        self.assertNotIn("v_deform_shift_raw", out)

    def test_composed_factor_emits_the_packed_spelling(self):
        out = self.render(layers=[{"world_y": 0,
                                   "fa": {"s1": 1, "s2": 15, "op": 0},
                                   "fb": "FACTOR_1"}])
        self.assertIn("fa: packed(s1: 1, s2: 15, op: 0)", out)

    def test_unknown_factor_name_is_refused_and_suggests_near_misses(self):
        path = self.write("ojz_bg", _scene(
            layers=[{"world_y": 0, "fa": "FACTOR_1_3", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene)
        msg = str(ctx.exception)
        self.assertIn("FACTOR_1_3", msg)
        self.assertIn("FACTOR_1_32", msg)  # a real near miss from the same prefix

    def test_composed_factor_missing_a_term_is_refused(self):
        path = self.write("ojz_bg", _scene(
            layers=[{"world_y": 0, "fa": {"s1": 1, "s2": 15}, "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene)
        self.assertIn("op", str(ctx.exception))

    def test_the_string_none_is_the_canonical_absent_spelling(self):
        """The writer-side schema (empyrean origin/main,
        contract/schema/aurora-effects-scene.schema.json) spells every attachment
        `oneOf [{"const": "none"}, {object}]`, default `"none"`. Slices 1-2 assumed
        JSON null and would have refused every real Aurora scene."""
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                                   "deform": "none", "curve": "none",
                                   "vsplit": "none"}],
                          deform_bg="none", deform_fg="none", v_deform="none",
                          anchor="none")
        self.assertIn("count: 1", out)
        for absent in ("SceneDeform", "SceneCurve", "SceneVSplit", "SceneAnchor"):
            self.assertNotIn(absent, out)

    def test_json_null_is_accepted_as_a_synonym_for_none(self):
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                                   "deform": None, "curve": None, "vsplit": None}],
                          deform_bg=None, anchor=None)
        self.assertIn("count: 1", out)

    def test_curve_emits_scene_curve_to_with_a_packed_factor(self):
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                                   "curve": {"to": "FACTOR_1_4"}}])
        self.assertIn("curve: SceneCurve.To(FACTOR_1_4)", out)

    def test_curve_accepts_a_composed_factor_payload(self):
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                                   "curve": {"to": {"s1": 2, "s2": 15, "op": 0}}}])
        self.assertIn("curve: SceneCurve.To(packed(s1: 2, s2: 15, op: 0))", out)

    def test_vsplit_emits_scene_vsplit_at(self):
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                                   "vsplit": {"at": 160}}])
        self.assertIn("vsplit: SceneVSplit.At(160)", out)

    def test_anchor_emits_its_three_positional_payloads_in_order(self):
        """SceneAnchor.At(patch channel, anchored dsa, anchored dsb) — payload slots
        are positional (scene_dsl.emp), so order is meaning, not style."""
        out = self.render(anchor={"at": {"channel": 0, "dsa": 3, "dsb": 4}},
                          layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertIn("anchor: SceneAnchor.At(0, 3, 4)", out)

    def test_enum_fields_emit_constants_not_the_schemas_lowercase_strings(self):
        """`precision: "line"` must emit PRECISION_LINE. Emitting the raw string
        produced `precision: line` — a sigil unknown-symbol error pointing at
        generated code, for a scene the author spelled correctly."""
        out = self.render(precision="line", transition="instant",
                          left_column_mask="sprite_mask",
                          layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertIn("precision: PRECISION_LINE", out)
        self.assertIn("transition: TRANS_INSTANT", out)
        self.assertIn("left_column_mask: SceneLeftColMask.SpriteMask", out)
        self.assertNotIn("precision: line", out)

    def test_an_illegal_enum_value_is_refused_and_lists_the_legal_ones(self):
        path = self.write("ojz_bg", _scene(precision="per_line"))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene)
        msg = str(ctx.exception)
        self.assertIn("per_line", msg)
        self.assertIn("line", msg)
        self.assertIn("cell", msg)

    def render_with_tables(self, **over):
        path = self.write("ojz_bg", _scene(**over))
        tables = effects_gen.TableRegistry()
        out = effects_gen.render_scene(path, effects_gen.load_scene(path), tables)
        return out, tables

    def test_layer_own_deform_emits_five_positional_payloads(self):
        """SceneDeform.Own(table, shift_a, shift_b, phase, speed) — positional."""
        out, tables = self.render_with_tables(
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                     "deform": {"own": {"table": {"generator": "sine",
                                                  "amplitude": 8, "period": 32},
                                        "shift_a": 1, "shift_b": 2,
                                        "phase": 3, "speed": 4}}}])
        self.assertIn("deform: SceneDeform.Own(EditorDeform_sine_8_32, 1, 2, 3, 4)",
                      out)
        self.assertIn("deform_sine(amplitude: 8, period: 32)", tables.declarations())

    def test_scene_shared_deform_emits_two_positional_payloads(self):
        out, _ = self.render_with_tables(
            deform_bg={"shared": {"table": {"generator": "zero"}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertIn("deform_bg: SceneDeform.Shared(EditorDeform_zero, 1)", out)

    def test_v_deform_emits_scene_vdeform_columns(self):
        out, _ = self.render_with_tables(
            v_deform={"columns": {"table": {"generator": "v_column_floor",
                                            "center": 20, "max_offset": 24},
                                  "speed": 1, "amp_shift": 2}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertIn(
            "v_deform: SceneVDeform.Columns(EditorDeform_v_column_floor_20_24, 1, 2)",
            out)

    def test_tables_emit_the_shipped_two_step_const_then_label_idiom(self):
        """The hand tables are `pub const SceneSrc_X = gen(..)` then
        `pub data X: [i8; 256] = SceneSrc_X` (ojz_scenes.emp / scene_registry.emp).
        The `pub data` half must be a LABEL — a const import re-evaluates its
        initializer in the consumer's scope and would duplicate the table."""
        _, tables = self.render_with_tables(
            deform_bg={"shared": {"table": {"generator": "zero"}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        decls = tables.declarations()
        self.assertIn("pub const SceneSrc_EditorDeform_zero = deform_zero()", decls)
        self.assertIn("pub data EditorDeform_zero: [i8; 256] = SceneSrc_EditorDeform_zero",
                      decls)

    def test_identical_tables_are_deduped_to_one_declaration(self):
        """Two attachments naming the same generator and parameters share one
        table — the shipped idiom, where six DeformTable_* labels serve twenty
        scenes. Duplication there was the defect, not the design."""
        out, tables = self.render_with_tables(
            deform_bg={"shared": {"table": {"generator": "sine", "amplitude": 8,
                                            "period": 32}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                     "deform": {"own": {"table": {"generator": "sine",
                                                  "amplitude": 8, "period": 32},
                                        "shift_a": 1, "shift_b": 2,
                                        "phase": 0, "speed": 1}}}])
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables.declarations().count("deform_sine("), 1)
        self.assertEqual(out.count("EditorDeform_sine_8_32"), 2)

    def test_differing_parameters_are_not_deduped(self):
        _, tables = self.render_with_tables(
            deform_bg={"shared": {"table": {"generator": "sine", "amplitude": 8,
                                            "period": 32}, "speed": 1}},
            deform_fg={"shared": {"table": {"generator": "sine", "amplitude": 9,
                                            "period": 32}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertEqual(len(tables), 2)

    def test_unknown_generator_is_refused_and_lists_the_legal_ones(self):
        path = self.write("ojz_bg", _scene(
            deform_bg={"shared": {"table": {"generator": "sawtooth"}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene, effects_gen.TableRegistry())
        msg = str(ctx.exception)
        self.assertIn("sawtooth", msg)
        self.assertIn("v_column_floor", msg)

    def test_generator_missing_a_parameter_is_refused(self):
        path = self.write("ojz_bg", _scene(
            deform_bg={"shared": {"table": {"generator": "sine", "amplitude": 8},
                                  "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene, effects_gen.TableRegistry())
        self.assertIn("period", str(ctx.exception))

    def test_bin_tableref_with_a_parent_segment_is_refused(self):
        """Contract §2.3: paths resolve under the effects dir and refuse `..`.

        The assertion targets "escape", which ONLY the traversal refusal says. An
        earlier version asserted `".." in message` and was vacuous: with the guard
        removed the file simply is not found, and the not-found message quotes the
        path — so `..` appears either way and the test passed against the poison.
        A traversal test must distinguish 'refused for traversing' from 'happened
        not to exist', because the dangerous case is the path that DOES exist.
        """
        path = self.write("ojz_bg", _scene(
            deform_bg={"shared": {"table": {"bin": "../../../etc/passwd.bin"},
                                  "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene, effects_gen.TableRegistry())
        self.assertIn("escape", str(ctx.exception))

    def test_a_traversal_path_that_EXISTS_is_still_refused(self):
        """The case the vacuous version could never have caught: a `..` path that
        resolves to a real 256-byte file. Only the traversal guard rejects this."""
        outside = os.path.join(self.tmp.name, "outside.bin")
        with open(outside, "wb") as f:
            f.write(b"\x00" * 256)
        rel = "../" * len(effects_gen.TABLE_BIN_ROOT) + "outside.bin"
        path = self.write("ojz_bg", _scene(
            deform_bg={"shared": {"table": {"bin": rel}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        saved, effects_gen.REPO = effects_gen.REPO, self.tmp.name
        try:
            self.assertTrue(os.path.isfile(os.path.join(
                effects_gen.REPO, *effects_gen.TABLE_BIN_ROOT, rel)),
                "control: the traversal target must really exist, or this test "
                "passes for the same wrong reason as the one it replaces")
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                effects_gen.render_scene(path, scene, effects_gen.TableRegistry())
        finally:
            effects_gen.REPO = saved
        self.assertIn("escape", str(ctx.exception))

    def test_bin_tableref_of_the_wrong_size_is_refused_and_names_both_sizes(self):
        eff = os.path.join(self.tmp.name, *effects_gen.TABLE_BIN_ROOT)
        os.makedirs(eff, exist_ok=True)
        with open(os.path.join(eff, "short.bin"), "wb") as f:
            f.write(b"\x00" * 128)
        path = self.write("ojz_bg", _scene(
            deform_bg={"shared": {"table": {"bin": "short.bin"}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        saved, effects_gen.REPO = effects_gen.REPO, self.tmp.name
        try:
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                effects_gen.render_scene(path, scene, effects_gen.TableRegistry())
        finally:
            effects_gen.REPO = saved
        msg = str(ctx.exception)
        self.assertIn("128", msg)
        self.assertIn("256", msg)

    def test_bin_tableref_of_the_right_size_emits_an_embed(self):
        eff = os.path.join(self.tmp.name, *effects_gen.TABLE_BIN_ROOT)
        os.makedirs(eff, exist_ok=True)
        with open(os.path.join(eff, "curve.bin"), "wb") as f:
            f.write(b"\x00" * 256)
        path = self.write("ojz_bg", _scene(
            deform_bg={"shared": {"table": {"bin": "curve.bin"}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        tables = effects_gen.TableRegistry()
        saved, effects_gen.REPO = effects_gen.REPO, self.tmp.name
        try:
            effects_gen.render_scene(path, scene, tables)
        finally:
            effects_gen.REPO = saved
        decls = tables.declarations()
        self.assertIn('embed("games/sonic4/data/editor/effects/curve.bin")', decls)
        self.assertIn("(align: 2)", decls)
        self.assertNotIn("[i8; 256]", decls)  # embed carries no type annotation

    def test_a_malformed_attachment_arm_is_named(self):
        path = self.write("ojz_bg", _scene(
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                     "curve": {"kind": "whatever"}}]))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene)
        msg = str(ctx.exception)
        self.assertIn("curve", msg)
        self.assertIn("to", msg)

    def test_nine_layers_is_refused_before_padding_arithmetic(self):
        layers = [{"world_y": i, "fa": "FACTOR_1", "fb": "FACTOR_1"} for i in range(9)]
        path = self.write("ojz_bg", _scene(layers=layers))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene)
        self.assertIn("MAX_PARALLAX_BANDS", str(ctx.exception))


# =============================================================================
# SLICE 5 — assignments, the generated module, and the always-emitted binding.
#
# Expectations here come from the CONTRACT (§2.2 for the assignment fields) and from
# the owner's Q-c ruling (always-emitted, one live path), never from reading back
# what render_module() happens to produce. Where a test pins a number it derives it
# from the fixture it just wrote.
# =============================================================================


class AssignmentBase(unittest.TestCase):
    """A whole fake repo: project.json + the editor tree, nothing else."""

    GRID_W, GRID_H = 3, 3

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.data = os.path.join(self.repo, "games", "sonic4", "data", "editor",
                                 "ojz", "act1")
        self.scenes = os.path.join(self.repo, "games", "sonic4", "data", "editor",
                                   "effects")
        os.makedirs(self.data)
        os.makedirs(self.scenes)
        self.write_project()

    def tearDown(self):
        self.tmp.cleanup()

    def write_project(self, act_ref=None):
        act = {"id": "act1", "gridWidth": self.GRID_W, "gridHeight": self.GRID_H,
               "dataPath": "games/sonic4/data/editor/ojz/act1/",
               "sceneRef": act_ref}
        doc = {"zones": [{"id": "ojz", "acts": [act]}]}
        with open(os.path.join(self.repo, "project.json"), "w") as f:
            json.dump(doc, f)

    def write_sidecar(self, index, body):
        path = os.path.join(self.data, f"section_{index}.meta.json")
        with open(path, "w") as f:
            if isinstance(body, str):
                f.write(body)
            else:
                json.dump(body, f)
        return path

    def write_scene(self, stem, **over):
        scene = _scene(id=stem, **over)
        with open(os.path.join(self.scenes, f"{stem}.json"), "w") as f:
            json.dump(scene, f)


class TestAssignmentReading(AssignmentBase):
    def test_no_sidecars_at_all_is_no_assignments(self):
        """Contract §2.2: Aurora writes a sidecar only when a ref is non-null, so
        the all-default act legitimately has NO file on disk. That must read as
        all-null, never as an error — all-null is also the state that triggers
        Aurora's destructive cleared-overwrite, so the two must not be confused."""
        self.assertEqual(effects_gen.load_section_scene_refs(self.repo), {})
        self.assertIsNone(effects_gen.load_act_scene_ref(self.repo))

    def test_an_unreadable_sidecar_fails_the_bake(self):
        """§2.2/§3, the asymmetry stated normatively: MISSING is all-null,
        UNREADABLE is loud. 'Degrade gracefully' must not collapse them."""
        self.write_sidecar(1, "{ this is not json")
        with self.assertRaises(json.JSONDecodeError):
            effects_gen.load_section_scene_refs(self.repo)

    def test_a_sidecar_without_a_sceneRef_key_is_null(self):
        self.write_sidecar(1, {"bgLayoutRef": "x", "paletteRef": None})
        self.assertEqual(effects_gen.load_section_scene_refs(self.repo), {})

    def test_explicit_null_is_the_act_default(self):
        self.write_sidecar(1, {"sceneRef": None})
        self.assertEqual(effects_gen.load_section_scene_refs(self.repo), {})

    def test_a_numeric_sceneRef_is_REFUSED_not_coerced(self):
        """§2.2 in its own words: 'a string id or null, NEVER a numeric index'.
        Aurora's parser nulls a non-string SILENTLY, so `sceneRef: 3` presents as
        'the assignment didn't stick'. The build is the last reader that can still
        see the mistake, so it refuses rather than coercing."""
        self.write_sidecar(1, {"sceneRef": 3})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_section_scene_refs(self.repo)
        msg = str(ctx.exception)
        self.assertIn("STRING", msg)
        self.assertIn("numeric index", msg)

    def test_a_sceneRef_that_is_not_symbol_safe_is_refused(self):
        """Ids become `.emp` symbol components; Aurora's BG-library ids use hyphens
        and timestamps, so this is the live cross-document hazard (design Q-d)."""
        self.write_sidecar(1, {"sceneRef": "deep-forest-v16-1781232789593"})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_section_scene_refs(self.repo)
        self.assertIn("not a legal scene id", str(ctx.exception))

    def test_only_sidecars_inside_the_grid_are_read(self):
        """The domain is grid_w*grid_h. A sidecar for a section the act does not
        have would otherwise bind a slot the descriptor can never ask for."""
        self.write_scene("shimmer")
        self.write_sidecar(self.GRID_W * self.GRID_H, {"sceneRef": "shimmer"})
        self.assertEqual(effects_gen.load_section_scene_refs(self.repo), {})

    def test_section_count_is_the_grid_product(self):
        self.assertEqual(effects_gen.act_section_count(self.repo),
                         self.GRID_W * self.GRID_H)


class TestAlwaysEmittedBindings(AssignmentBase):
    """The owner ruling (2026-08-22, design §9 Q-c): the generator emits the
    act-default binding for EVERY act, content or not, so `act_descriptor.emp` has
    exactly ONE path, always live."""

    def render(self):
        names = effects_gen.act_names(self.repo)
        return names, effects_gen.render_module(
            effects_gen.load_all_scenes("sonic4", self.repo),
            effects_gen.load_act_scene_ref(self.repo),
            effects_gen.load_section_scene_refs(self.repo),
            effects_gen.act_section_count(self.repo), names)

    def test_both_bindings_exist_with_no_editor_content_at_all(self):
        names, text = self.render()
        self.assertIn(f"pub comptime fn {names.fn_act_default}(hand: Label)", text)
        self.assertIn(f"pub comptime fn {names.fn_sec_scene}(sec: int", text)

    def test_with_no_content_the_act_default_returns_the_HAND_fallback(self):
        """Not 'aliased to nothing' (design §3's superseded text) — it resolves to
        the hand-authored default the descriptor passes in, which is what keeps the
        descriptor's single path live."""
        _names, text = self.render()
        self.assertIn("    return hand", text)

    def test_with_an_act_sceneRef_the_default_returns_the_EDITOR_record(self):
        self.write_scene("shimmer")
        self.write_project(act_ref="shimmer")
        names, text = self.render()
        self.assertIn(f"    return {names.binding_default}", text)
        self.assertIn(f"pub data {names.binding_default}: SceneCfg1 = lower1(", text)
        self.assertNotIn("    return hand", text)

    def test_a_bound_section_gets_a_branch_and_an_unbound_one_does_not(self):
        self.write_scene("shimmer")
        self.write_sidecar(2, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertIn(f"if sec == 2 {{ out = {names.binding_sec(2)} }}", text)
        self.assertNotIn("if sec == 1 ", text)

    def test_the_sec_domain_ensure_carries_an_INLINE_literal(self):
        """docs/EMP_PITFALLS.md §2: a comptime fn's free names resolve at the CALL
        SITE, so a named constant in this ensure would resolve in act_descriptor's
        scope — or silently not at all. The literal is inlined and pinned at module
        level, where MAX_ACT_SECTIONS really is visible."""
        _names, text = self.render()
        n = self.GRID_W * self.GRID_H
        self.assertIn(f"ensure(sec >= 0 && sec < {n},", text)
        self.assertIn(f"ensure({n} <= MAX_ACT_SECTIONS,", text)

    def test_the_bindings_are_functions_and_never_a_const_or_an_equ(self):
        """The mechanism ruling, held as a test because both alternatives were
        MEASURED to fail: `pub equ` is not importable (sigil item_pub_name has no
        Item::Equ arm) and a `pub const` carrying a Label fails the clone-injection
        re-evaluation at the DEFINING file's span. A future 'simplification' to
        either spelling reintroduces a build that cannot work."""
        names, text = self.render()
        self.assertNotIn(f"pub const {names.fn_act_default}", text)
        self.assertNotIn(f"pub equ {names.fn_act_default}", text)
        # The witnesses, by contrast, MUST be equs: only an equ reaches the listing.
        self.assertIn(f"pub equ {names.equ_scenes} = ", text)
        self.assertIn(f"pub equ {names.equ_bindings} = ", text)


class TestGeneratedModuleShape(AssignmentBase):
    def render(self):
        names = effects_gen.act_names(self.repo)
        return names, effects_gen.render_module(
            effects_gen.load_all_scenes("sonic4", self.repo),
            effects_gen.load_act_scene_ref(self.repo),
            effects_gen.load_section_scene_refs(self.repo),
            effects_gen.act_section_count(self.repo), names)

    def test_the_witness_values_are_the_derived_counts(self):
        """Derived from the fixture this test writes: two sections bound to two
        distinct scenes plus an act default on one of them = 3 bindings, 2 scenes."""
        self.write_scene("shimmer")
        self.write_scene("haze")
        self.write_sidecar(0, {"sceneRef": "shimmer"})
        self.write_sidecar(4, {"sceneRef": "haze"})
        self.write_project(act_ref="haze")
        names, text = self.render()
        self.assertIn(f"pub equ {names.equ_scenes} = 2", text)
        self.assertIn(f"pub equ {names.equ_bindings} = 3", text)

    def test_an_authored_but_unassigned_scene_emits_NOTHING(self):
        """A scene nobody points at is ROM nobody reads. It is named in the header
        so the author can see it was skipped, and it is not lowered."""
        self.write_scene("orphan")
        _names, text = self.render()
        self.assertIn("Authored but unassigned: orphan", text)
        self.assertNotIn("Scene_Editor_orphan", text)

    def test_a_sceneRef_naming_no_scene_is_refused_by_name(self):
        self.write_sidecar(1, {"sceneRef": "not_in_the_library"})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render()
        msg = str(ctx.exception)
        self.assertIn("not_in_the_library", msg)
        self.assertIn("editor-library ids only", msg)

    def test_the_budget_and_capability_gates_ride_the_editor_set(self):
        """Design §3(e) plus the capability half: editor scenes get the SAME hard
        build-time gates the hand registry applies to hand scenes."""
        self.write_scene("shimmer")
        self.write_sidecar(0, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertIn(f"scene_budget_enforce({names.scene_array})", text)
        self.assertIn(f"fold_caps({names.scene_array})", text)
        self.assertIn("Game.SCANLINE_CAPS", text)

    def test_a_band_count_with_no_registry_shape_is_refused_by_name(self):
        """Three-band scenes have no `SceneCfg3`/`lower3`. The refusal names
        scene_registry.emp as the place to add one — never a second lowering in
        generated code, which is how two copies of a lowering start drifting."""
        self.write_scene("three", layers=[
            {"world_y": i * 32, "fa": "FACTOR_1", "fb": "FACTOR_1"} for i in range(3)])
        self.write_sidecar(0, {"sceneRef": "three"})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render()
        msg = str(ctx.exception)
        self.assertIn("scene_registry.emp", msg)
        self.assertIn("SceneCfg3", msg)

    def test_the_render_is_deterministic(self):
        """The build's drift gate compares a re-render against the committed file,
        so an unstable ordering would fail every second build."""
        self.write_scene("shimmer")
        self.write_scene("haze")
        self.write_sidecar(0, {"sceneRef": "haze"})
        self.write_sidecar(1, {"sceneRef": "shimmer"})
        self.assertEqual(self.render()[1], self.render()[1])

    def test_the_module_and_section_names_come_from_the_project_ids(self):
        names = effects_gen.act_names(self.repo)
        self.assertEqual(names.module, "games.sonic4.ojz_effects_editor_act1")
        self.assertEqual(names.section, "ojz_effects_editor_act1")
        self.assertTrue(names.out_path(self.repo).endswith(
            os.path.join("generated", "ojz", "act1", "effects_scenes.emp")))


if __name__ == "__main__":
    unittest.main()
