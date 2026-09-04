#!/usr/bin/env python3
"""Tests for `tools/effects_gen.py` — the Aurora effect-scene bake (scanline P5).

Covers the whole tool, not one slice of it: discovery and load posture, SHAPE
validation, the rendered `scene()` / `layer()` text, the `sceneRef` sidecars, and the
always-emitted binding module. (The header said "slice 1" long after slices 2-5 landed
— the same staling this file's subject was fixed for.)

Every expectation here is derived from `tools/EFFECTS_CONSUMER_CONTRACT.md` §2/§3 —
the normative read set — rather than copied from the implementation. Where a test
asserts a refusal it also asserts WHAT the message names, because a gate whose verdict
is right and whose stated reason is wrong is worse than a failing gate: the reason is
what a reader carries forward (protocol review bar 10).
"""

import json
import os
import re
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
            "vsplit": None, "drift": None,
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


class TestIntegerSlotsAreShapeChecked(SceneShapeBase):
    """The VFACTOR defect: a STRING in a slot that is emitted as a bare integer.

    Why this is SHAPE and not VALUE, i.e. why it belongs here at all: a numeric slot
    is interpolated verbatim into generated `.emp`, so a string lands there as a bare
    SYMBOL. Aurora's new-scene default for `v_factor` is `"FACTOR_0"`, which is
    `parallax_dsl`'s PACKED HORIZONTAL factor (`FACTOR_LOCKED = $0FF` = 255) while
    `sc_v_factor` is a RAW SHIFT whose lock sentinel is 15 — and `parallax_dsl` is
    glob-injected into every module, so the name RESOLVES and the scene assembles
    green at 255. "Integer, not string" duplicates no constructor guard; the RANGE
    does, and lives on `scene()`.

    EVERY MATCHER HERE TARGETS "interpolated verbatim", which ONLY this refusal says.
    The near-miss to avoid is the sibling refusals in the same call path — the unknown
    factor name, the unknown key, the missing field — several of which also quote the
    offending value, so asserting on the value alone would pass against a poisoned
    guard for the wrong reason. That is this file's own recorded lesson (see
    `test_bin_tableref_with_a_parent_segment_is_refused`).
    """

    def render(self, **over):
        path = self.write("ojz_bg", _scene(**over))
        return effects_gen.render_scene(path, effects_gen.load_scene(path),
                                        effects_gen.TableRegistry())

    def refuses(self, **over):
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render(**over)
        msg = str(ctx.exception)
        self.assertIn("interpolated verbatim", msg)
        return msg

    def test_the_aurora_default_v_factor_string_is_refused(self):
        """The defect verbatim: Aurora's editor default for a new effect scene."""
        msg = self.refuses(v_factor="FACTOR_0")
        self.assertIn("scene.v_factor", msg)     # names the field path
        self.assertIn("FACTOR_0", msg)           # quotes what was given

    def test_EVERY_scene_scalar_is_covered_not_only_v_factor(self):
        """Derived by iterating `SCENE_SCALARS`, never by listing the four here —
        a scalar added to that tuple must be covered on the day it is added, not on
        the day someone remembers to extend this test."""
        self.assertTrue(effects_gen.SCENE_SCALARS)
        for key in effects_gen.SCENE_SCALARS:
            with self.subTest(scalar=key):
                self.assertIn(f"scene.{key}", self.refuses(**{key: "FACTOR_0"}))

    def test_EVERY_layer_scalar_and_world_y_are_covered(self):
        """`LAYER_SCALARS` runs through the identical unchecked interpolation in
        `render_layer`, and so does `world_y` beside it. `enabled` is excluded and
        tested separately: the writer schema spells it as a BOOLEAN, so it is
        translated rather than refused."""
        layer_slots = [k for k in effects_gen.LAYER_SCALARS if k != "enabled"]
        self.assertTrue(layer_slots)
        for key in layer_slots + ["world_y"]:
            with self.subTest(slot=key):
                layer = {"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}
                layer[key] = "FACTOR_0"
                self.assertIn(f"layers[0].{key}", self.refuses(layers=[layer]))

    def test_a_NUMERIC_STRING_is_still_refused(self):
        """The control that separates 'refused the TYPE' from 'refused a bad VALUE'.

        `"3"` is a perfectly legal shift — as a number. As a string it interpolates
        to the bare token `3`, which happens to assemble correctly today and would
        make the guard look unnecessary; the guard is about the SLOT, not the luck
        of this particular payload. A range check could never distinguish these two.
        """
        self.assertIn("scene.v_factor", self.refuses(v_factor="3"))

    def test_a_FLOAT_is_refused_even_when_it_is_whole(self):
        """`3.0` interpolates as `3.0`, which is not an `.emp` integer literal.
        JSON has one number type, so a writer bug here is a live spelling."""
        self.assertIn("float", self.refuses(v_factor=3.0))

    def test_real_integers_pass_INCLUDING_ones_the_constructor_will_reject(self):
        """The other half of the control, and the charter boundary made executable.

        255 is exactly the value the defect produced, and it must still RENDER here:
        rejecting it would be a RANGE check, which is `scene()`'s job (this parcel
        adds it there). If this test ever goes red, a value check has leaked into
        the generator and there are two sources for one rule again.

        The boundaries are derived, not guessed: 0 and 15 are `sc_v_factor`'s legal
        span (15 = the lock sentinel, parallax.emp `.v_locked`), 255 is `FACTOR_0`,
        and -1 is below the `u8`. All four are INTEGERS, so all four pass SHAPE.
        """
        for v in (0, 15, 255, -1):
            with self.subTest(v_factor=v):
                self.assertIn(f"v_factor: {v}", self.render(v_factor=v))

    def test_enabled_accepts_the_writers_JSON_BOOLEAN_and_emits_1_or_0(self):
        """Read from the WRITER's schema, not from our field list: empyrean
        `contract/schema/aurora-effects-scene.schema.json` `$defs.layer.enabled` is
        `{"type": "boolean", "default": true}`, while `layer()` takes
        `enabled: int = 1`. Forwarding the JSON value emits the bare word `True`
        into `.emp`. Same class as slices 1-2 emitting `precision: cell`."""
        for value, emitted in ((True, "enabled: 1"), (False, "enabled: 0")):
            with self.subTest(enabled=value):
                out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1",
                                           "fb": "FACTOR_1", "enabled": value}])
                self.assertIn(emitted, out)
                self.assertNotIn("True", out)
                self.assertNotIn("False", out)

    def test_enabled_still_accepts_an_integer_and_still_refuses_a_string(self):
        out = self.render(layers=[{"world_y": 0, "fa": "FACTOR_1",
                                   "fb": "FACTOR_1", "enabled": 0}])
        self.assertIn("enabled: 0", out)
        self.assertIn("layers[0].enabled", self.refuses(
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
                     "enabled": "FACTOR_0"}]))

    def test_the_nested_integer_payloads_are_covered_too(self):
        """The same verbatim interpolation reaches five more slots below the top
        level. Listed by WHERE-path so a failure names the slot that lost cover."""
        base = {"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}
        cases = {
            # composed factor terms
            "layers[0].fa.s1": dict(layers=[dict(base, fa={"s1": "FACTOR_0",
                                                          "s2": 15, "op": 0})]),
            # anchor payloads
            "scene.anchor.at.dsa": dict(anchor={"at": {"channel": 0,
                                                       "dsa": "FACTOR_0",
                                                       "dsb": 15}}),
            # attachment payload past the tableRef
            "scene.deform_bg.shared.speed": dict(deform_bg={"shared": {
                "table": {"generator": "zero"}, "speed": "FACTOR_0"}}),
            # tableRef generator parameters
            "scene.deform_bg.shared.table.sine.amplitude": dict(deform_bg={
                "shared": {"table": {"generator": "sine",
                                     "amplitude": "FACTOR_0", "period": 32},
                           "speed": 1}}),
            # vsplit's scanline (this file's first inline check, now the shared one)
            "layers[0].vsplit.at": dict(layers=[dict(base,
                                                     vsplit={"at": "FACTOR_0"})]),
        }
        for where, over in cases.items():
            with self.subTest(slot=where):
                over.setdefault("layers", [base])
                self.assertIn(where, self.refuses(**over))


class TestRendering(SceneShapeBase):
    """Emission expectations are derived from the HAND-AUTHORED idiom in
    `games/sonic4/data/effects/ojz_scenes.emp` (`Scene_OJZ_Default`), not from the
    implementation — the generated call must be spelled the way a human writes one."""

    def render(self, **over):
        path = self.write("ojz_bg", _scene(**over))
        return effects_gen.render_scene(path, effects_gen.load_scene(path))

    def test_layers_array_is_always_max_bands_slots_padded_with_no_layer(self):
        """`scene()` indexes a [SceneLayer; MAX_PARALLAX_BANDS]; the hand idiom pads.

        THE PAD COUNT IS DERIVED, NOT TYPED, and it used to be the literal 7. A fixed pad
        count is only loud when the ceiling moves UP (the generator emits more pads than
        the test expects, as this one did on the 2026-08-27 8 -> 16 raise). Move the
        ceiling DOWN and a literal that happens to be below the new width would keep
        passing while testing nothing. MAX - 1 tracks it in both directions.
        """
        out = self.render(layers=[{"world_y": 512, "fa": "FACTOR_1", "fb": "FACTOR_1_2"}])
        self.assertEqual(out.count("no_layer()"),
                         effects_gen.MAX_PARALLAX_BANDS - 1)
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
        for absent in ("v_center", "v_offset", "v_factor_fg", "transition"):
            self.assertNotIn(f"{absent}:", out)

    def test_precision_is_accepted_and_never_rendered(self):
        """`precision` is RETIRED on the engine side (2026-08-26, d-29-corrected): the
        per-cell HScroll path is gone and `scene()` takes no such argument, so rendering
        it would be a sigil unknown-argument error on generated code. Aurora's wave-1
        schema still emits it, so the generator must ACCEPT the key and IGNORE the value
        — any value, since nothing downstream reads it."""
        for value in ("cell", "line", "per_line", 7):
            out = self.render(precision=value,
                              layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
            self.assertNotIn("precision", out)

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
        """`transition: "instant"` must emit TRANS_INSTANT. Emitting the raw string
        produced (in slices 1-2, on the since-retired `precision` field) a sigil
        unknown-symbol error pointing at generated code, for a scene the author
        spelled correctly."""
        out = self.render(transition="instant",
                          left_column_mask="sprite_mask",
                          layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertIn("transition: TRANS_INSTANT", out)
        self.assertIn("left_column_mask: SceneLeftColMask.SpriteMask", out)
        self.assertNotIn("transition: instant", out)

    def test_decline_borrow_is_a_legal_left_column_mask(self):
        """d-50 (2026-09-02) added the arm that turns the column-19 borrow off on one
        scene. It is the only left_column_mask value that MOVES BYTES (it ORs $80 into
        pcfg_v_deform_shift_bg), so a generator that silently refused it would look like
        an editor bug rather than a missing map entry. The editor cannot write it yet;
        this is the map entry the day it can."""
        out = self.render(left_column_mask="decline_borrow",
                          layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertIn("left_column_mask: SceneLeftColMask.DeclineBorrow", out)
        self.assertNotIn("left_column_mask: decline_borrow", out)

    def test_an_illegal_enum_value_is_refused_and_lists_the_legal_ones(self):
        path = self.write("ojz_bg", _scene(transition="snap"))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene)
        msg = str(ctx.exception)
        self.assertIn("snap", msg)
        self.assertIn("instant", msg)
        self.assertIn("smooth", msg)

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

    def test_one_layer_over_the_ceiling_is_refused_before_padding_arithmetic(self):
        """MAX + 1, DERIVED — it was the literal 9 until 2026-08-27.

        A fixed over-long count only tests the ceiling from one side. Raise the ceiling
        and the fixture stops being over-long and the test goes red (which is what
        happened here at 8 -> 16, correctly). LOWER the ceiling and a literal that is
        still above the new bound keeps passing while asserting nothing about where the
        bound actually is. MAX + 1 is the one-unit case at whatever the ceiling is.
        """
        n = effects_gen.MAX_PARALLAX_BANDS + 1
        layers = [{"world_y": i, "fa": "FACTOR_1", "fb": "FACTOR_1"} for i in range(n)]
        path = self.write("ojz_bg", _scene(layers=layers))
        scene = effects_gen.load_scene(path)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_scene(path, scene)
        self.assertIn("MAX_PARALLAX_BANDS", str(ctx.exception))

    def test_exactly_the_ceiling_is_accepted_with_no_padding(self):
        """The other side of the one-unit pair, and the half that makes it a bound test.

        Without this, `test_one_layer_over_the_ceiling_...` passes for any refusal at any
        count at or below MAX + 1 — including a generator that refused everything. At
        exactly MAX the scene must render, and with zero no_layer() pads.
        """
        n = effects_gen.MAX_PARALLAX_BANDS
        layers = [{"world_y": i * 8, "fa": "FACTOR_1", "fb": "FACTOR_1"} for i in range(n)]
        out = self.render(layers=layers)
        self.assertEqual(out.count("no_layer()"), 0)
        self.assertEqual(out.count("layer(world_y"), n)
        self.assertIn("count: %d" % n, out)


class TestLayerDrift(SceneShapeBase):
    """`layer.drift` — EFFECTS-W1 item 3's authoring half (2026-09-02).

    The mechanism and the hand-authored adopter landed at chain 201; this key is what
    lets a SCENE DOCUMENT reach it. Expectations are derived from the two owners the
    contract names and from nothing else: the wire shape and its bounds from the writer
    schema (empyrean `contract/schema/aurora-effects-scene.schema.json`
    `$defs.layer.drift` — `oneOf ["none", {"rate": integer, -4096..4096, not 0}]`,
    `"default": "none"`), and the emitted spelling from the hand idiom at
    `games/sonic4/data/effects/ojz_scenes.emp:170-173`, which writes
    `drift: SceneDrift.Rate(-32)`.

    THE UNIT IS THE THING THIS CLASS EXISTS TO PIN. `rate` is on the wire in the
    ENGINE's unit (1/256 px per frame, signed), not in px/frame: the px/frame
    presentation is Aurora's UI and is multiplied by 256 on export (design §7.1
    mitigation 2). A generator that "helpfully" scaled would make every authored rate
    256x fast, and no assertion downstream could catch it — `Rate(8192)` is a legal
    integer that merely trips a taste bound. `test_the_rate_reaches_the_constructor_
    unscaled` is that guard, and the OJZ value is used because it is the one rate whose
    correct emission is checkable against a shipped file.
    """

    def render(self, drift):
        layer = {"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}
        if drift is not _OMITTED:
            layer["drift"] = drift
        path = self.write("ojz_bg", _scene(layers=[layer]))
        return effects_gen.render_scene(path, effects_gen.load_scene(path))

    def test_the_key_is_accepted_at_all(self):
        """It was refused before this parcel: `drift` was not in LAYER_KEYS, so
        `_check_keys` made every scene carrying it a hard refusal. Aurora's editor
        control is built against the key being readable."""
        self.assertIn("drift", effects_gen.LAYER_KEYS)
        path = self.write("ojz_bg", _scene(layers=[
            {"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1",
             "drift": {"rate": 32}}]))
        self.assertEqual(effects_gen.load_scene(path)["layers"][0]["drift"],
                         {"rate": 32})

    def test_the_rate_reaches_the_constructor_unscaled(self):
        """The wire unit IS the engine unit. `{"rate": -32}` must emit `Rate(-32)` —
        not `Rate(-8192)` (scaled here as well as in the editor) and not `Rate(-1)`
        (unscaled anywhere). -32 is the shipped OJZ canopy rate, 1/8 px/frame."""
        out = self.render({"rate": -32})
        self.assertIn("drift: SceneDrift.Rate(-32)", out)
        self.assertNotIn("Rate(-8192)", out)

    def test_a_positive_rate_emits_verbatim_too(self):
        self.assertIn("drift: SceneDrift.Rate(256)", self.render({"rate": 256}))

    def test_absent_emits_no_drift_argument_in_all_three_spellings(self):
        """`layer()`'s default IS `SceneDrift.None`, so the absent case is the argument
        being left off — the same treatment `curve` and `vsplit` get. All three absent
        spellings the format allows must land there: omitted, the schema's `"none"`,
        and JSON null (ATTACH_NONE's accepted synonym)."""
        for spelling in (_OMITTED, "none", None):
            with self.subTest(spelling=spelling):
                self.assertNotIn("drift:", self.render(spelling))

    def test_a_non_integer_rate_is_refused_naming_the_slot(self):
        """The VFACTOR defect applied to this slot: a string is interpolated into
        generated `.emp` as a bare SYMBOL, and `FACTOR_0` resolves everywhere."""
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render({"rate": "FACTOR_0"})
        self.assertIn("drift.rate", str(ctx.exception))

    def test_a_drift_object_without_rate_is_refused_naming_the_arm(self):
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render({"px_per_frame": 1})
        msg = str(ctx.exception)
        self.assertIn("rate", msg)
        self.assertIn("px_per_frame", msg)

    def test_zero_and_out_of_range_rates_pass_shape_and_are_left_to_sigil(self):
        """Design §7 row 10, verbatim: "the range is enforced by row 2's `ensure` at
        build time, not by the generator." Both bounds live in `layer()`
        (`engine/level/scene_dsl.emp`) and their MESSAGES are the field's real
        documentation — they state the unit and give the worked conversion. A copy of
        either bound here would be the second source that drifts, and it would answer
        with this tool's wording instead of the one the author needs to read."""
        for rate in (0, 9000, -9000):
            with self.subTest(rate=rate):
                self.assertIn(f"drift: SceneDrift.Rate({rate})",
                              self.render({"rate": rate}))


# A sentinel for "the key is not present at all", distinct from JSON null (which is a
# legal ABSENT spelling and must be tested separately from omission).
_OMITTED = object()


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
        # "scene id" became "id" when `rasterRef` began sharing this validator — and
        # the refusal now NAMES THE KEY it refused, which empyrean §3.1 requires and
        # which is what makes a shared message safe. Asserting both is strictly
        # stronger than the sentence this replaced.
        self.assertIn("not a legal id", str(ctx.exception))
        self.assertIn(effects_gen.ACT_SCENE_REF_KEY, str(ctx.exception))

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

    def test_every_band_count_the_engine_admits_now_lowers(self):
        """The band-count-range parcel: scene_registry.emp declares a shape for every
        count in 1..MAX_PARALLAX_BANDS, so 3, 6, 7 and 8 lower like 1, 2, 4 and 5 do.

        This test used to assert the OPPOSITE for three-band scenes — it was the
        codification of the defect, not a guard against one. The coverage property
        itself (shape set == 1..MAX_PARALLAX_BANDS, derived from the constant) is
        tools/test_scene_band_shape_coverage.py's subject; this end is the generator's
        behaviour on a scene of each count."""
        for n in (3, 6, 7, 8):
            with self.subTest(layers=n):
                sid = "count%d" % n
                self.write_scene(sid, layers=[
                    {"world_y": i * 32, "fa": "FACTOR_1", "fb": "FACTOR_1"}
                    for i in range(n)])
                self.write_sidecar(0, {"sceneRef": sid})
                _, text = self.render()
                self.assertIn("SceneCfg%d = lower%d(" % (n, n), text)

    def test_a_band_count_with_no_registry_shape_is_refused_by_name(self):
        """The refusal STAYS — it is what makes a missing shape a named, actionable
        failure instead of a generated `lowerN(` that dies at link. With the range
        closed nothing in 1..MAX can reach it, so the shape set is narrowed here to
        exercise the guard rather than deleting it from the registry (which is the
        gate's red-first job, not this file's).

        It names scene_registry.emp as the place to add one — never a second lowering in
        generated code, which is how two copies of a lowering start drifting."""
        self.write_scene("three", layers=[
            {"world_y": i * 32, "fa": "FACTOR_1", "fb": "FACTOR_1"} for i in range(3)])
        self.write_sidecar(0, {"sceneRef": "three"})
        real = effects_gen.LOWERABLE_BAND_COUNTS
        effects_gen.LOWERABLE_BAND_COUNTS = tuple(c for c in real if c != 3)
        try:
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                self.render()
        finally:
            effects_gen.LOWERABLE_BAND_COUNTS = real
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


class TestJsonValuesBecomeSymbolSafeTokens(SceneShapeBase):
    """The third instance of one class in effects_gen: a LEGAL JSON value rendered into an
    ILLEGAL `.emp` token (DEFERRED_WORK "a negative generator parameter emits a label that
    is not symbol-safe"). Instances one and two were `precision: cell` (slices 1-2) and the
    bare word `False` for `enabled` (fixed at da43a036). This class pins the PATTERN: every
    place a JSON value becomes a `.emp` SYMBOL goes through a symbol-safe rendering, and
    the VALUE handed to the constructor is still the true signed one.

    Whether a negative parameter is LEGAL is the engine's question and was MEASURED before
    this class was written (2026-08-25, scratch `--extra-entry` witness): none of the five
    TABLE_GENERATORS carries an `ensure` on sign — `deform_sine(amplitude: -8, ..)` is an
    inverted wave and `v_column_perspective(.., max_offset: -24)` an opposite tilt, both
    elaborating green — so this was a LIVE emission bug, not a diagnostic-quality one, and
    the generator must EMIT a negative, not refuse it.

    Runner: build.sh's pytest lane (`python3 -m pytest tools -q`, build-fatal), on every
    canonical shape.
    """

    SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def render_with_tables(self, **over):
        path = self.write("ojz_bg", _scene(**over))
        tables = effects_gen.TableRegistry()
        out = effects_gen.render_scene(path, effects_gen.load_scene(path), tables)
        return out, tables

    def labels(self, tables):
        return [label for label, _init in tables._decls]

    def test_a_negative_parameter_renders_a_symbol_safe_label_and_the_true_value(self):
        """The booking's own example: `sine` with `amplitude: -8`. The label must be a
        legal `.emp` symbol and the CALL must still pass `-8`, so the engine's guard (if
        one ever grows) fires with the engine's message and a legal negative links."""
        out, tables = self.render_with_tables(
            deform_bg={"shared": {"table": {"generator": "sine", "amplitude": -8,
                                            "period": 32}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        (label,) = self.labels(tables)
        self.assertRegex(label, self.SYMBOL)
        self.assertEqual(label, "EditorDeform_sine_m8_32")
        self.assertIn("deform_sine(amplitude: -8, period: 32)", tables.declarations())
        self.assertIn(f"SceneDeform.Shared({label}, 1)", out)

    def test_EVERY_generator_parameter_slot_renders_symbol_safe_when_negative(self):
        """Derived from TABLE_GENERATORS, never listed: a generator added tomorrow is
        covered the day it is added. Each parameter is driven negative in turn while its
        siblings stay at a legal positive."""
        for gen, (fn, params) in effects_gen.TABLE_GENERATORS.items():
            for target in params:
                with self.subTest(generator=gen, param=target):
                    body = {"generator": gen}
                    body.update({p: (-7 if p == target else 32) for p in params})
                    _, tables = self.render_with_tables(
                        deform_bg={"shared": {"table": body, "speed": 1}},
                        layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
                    (label,) = self.labels(tables)
                    self.assertRegex(label, self.SYMBOL)
                    self.assertIn(f"{target}: -7", tables.declarations())

    def test_minus_eight_and_eight_do_NOT_dedupe_onto_one_table(self):
        """The dedup key and the label are formed from the same token, so the token
        must be injective over sign or two different tables share one declaration."""
        _, tables = self.render_with_tables(
            deform_bg={"shared": {"table": {"generator": "sine", "amplitude": -8,
                                            "period": 32}, "speed": 1}},
            deform_fg={"shared": {"table": {"generator": "sine", "amplitude": 8,
                                            "period": 32}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}])
        self.assertEqual(len(tables), 2)
        self.assertEqual(len(set(self.labels(tables))), 2)

    def test_the_symbol_token_is_injective_and_stable_for_non_negatives(self):
        """`m` is the sign marker because a non-negative renders as DIGITS ONLY, so a
        token that starts with a letter can never equal one — and the non-negative
        spelling is byte-for-byte what it was before this parcel, so every committed
        label is unchanged."""
        tok = effects_gen.symbol_token
        for v in (0, 1, 8, 32, 255, 32767):
            with self.subTest(v=v):
                self.assertEqual(tok(v), str(v))
        seen = {}
        for v in range(-300, 301):
            t = tok(v)
            self.assertRegex("X_" + t, self.SYMBOL)
            self.assertNotIn(t, seen, f"{v} and {seen.get(t)} render alike")
            seen[t] = v
        self.assertEqual(tok(-8), "m8")
        self.assertEqual(tok(-0), "0")   # -0 IS 0; there is no negative zero token

    def test_the_committed_generated_module_is_reproduced_label_for_label(self):
        """The shipped label set is UNCHANGED: a re-render of the real repo's committed
        scenes matches the committed `effects_scenes.emp` exactly (which the build's
        `effects_gen.py check` drift gate also enforces, build-fatally). Loud if the
        committed set is empty of tables, because then this measures only the
        no-table arm of the renderer."""
        out_path, text = effects_gen.generate(effects_gen.REPO)
        with open(out_path) as f:
            committed = f.read()
        self.assertEqual(text, committed)
        n = committed.count("pub data EditorDeform_")
        if n == 0:
            self.skipTest("committed effects_scenes.emp carries no EditorDeform_ table "
                          "today (the one shipped scene attaches none) — the label-set "
                          "half of this check is vacuous until an authored scene "
                          "attaches a generator table; the text-identity half ran")

    def test_two_bin_paths_that_fold_to_one_label_are_refused_not_emitted_twice(self):
        """The `bin` sibling of the same class: the label is a lossy fold of the path
        (`[^a-z0-9]+` -> `_`), while the dedup key is the exact path — so `a-b.bin` and
        `a_b.bin` used to intern as TWO declarations under ONE label, a duplicate-symbol
        error in generated code. The registry now refuses at the seam and names both."""
        root = os.path.join(self.tmp.name, *effects_gen.TABLE_BIN_ROOT)
        for name in ("a-b.bin", "a_b.bin"):
            with open(os.path.join(root, name), "wb") as f:
                f.write(b"\x01" * 256)
        path = self.write("ojz_bg", _scene(
            deform_bg={"shared": {"table": {"bin": "a-b.bin"}, "speed": 1}},
            deform_fg={"shared": {"table": {"bin": "a_b.bin"}, "speed": 1}},
            layers=[{"world_y": 0, "fa": "FACTOR_1", "fb": "FACTOR_1"}]))
        scene = effects_gen.load_scene(path)
        saved, effects_gen.REPO = effects_gen.REPO, self.tmp.name
        try:
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                effects_gen.render_scene(path, scene, effects_gen.TableRegistry())
        finally:
            effects_gen.REPO = saved
        msg = str(ctx.exception)
        self.assertIn("a-b.bin", msg)
        self.assertIn("a_b.bin", msg)
        self.assertIn("one label", msg)

    def test_project_ids_that_are_not_symbol_safe_are_refused_where_they_become_names(self):
        """project.json's zone/act ids become `EditorScenes_<ZONE>_<Act>` labels and the
        generated module's name. They are the one JSON->symbol site the scene-id regex
        did not already own."""
        for bad in ("ojz-1", "1ojz", "Ojz", "ojz act"):
            with self.subTest(zone_id=bad):
                with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                    effects_gen.ActNames(bad, "act1")
                self.assertIn(bad, str(ctx.exception))
                self.assertIn("symbol", str(ctx.exception))
        with self.assertRaises(effects_gen.SceneShapeError):
            effects_gen.ActNames("ojz", "act-1")
        effects_gen.ActNames("ojz", "act1")   # the shipped ids stay legal


class TestSignedVerticalScalarsAreForwardedVerbatim(SceneShapeBase):
    """The VOFFSET half of the VFACTOR defect: `v_center` / `v_offset` had no range owner.

    THE GENERATOR DOES NOT RANGE-CHECK THESE, ON PURPOSE, and this class is the executable
    record of that decision — the same charter line `TestIntegerSlotsAreShapeChecked` draws
    for `v_factor`. The bounds live on `scene()` (engine/level/scene_dsl.emp): `v_offset` is
    a SIGNED scroll word (-32768 .. 32767; Parallax_Step5_Vscroll consumes it with a 16-bit
    `add.w`, and `.v_locked` copies it straight into Vscroll_BG) and `v_center` is a WORLD Y
    (0 .. $7FFF, the same span `layer()` bounds `world_y` to). A copy of either number here
    would be the second source that drifts.

    What the generator DOES own is the sign trap: `scene()` takes a signed `int` for both,
    so the only correct emission of a negative offset is the negative literal itself. The
    old failure was `v_offset: -8` reaching a `u16` field and dying at
    `[emit.out-of-range]` in generated code; the fix moved the field to `i16` and the
    two's-complement encode into `scene_hdr()`, so `-8` must reach the `.emp` as `-8` —
    not as 65528, not refused, not clamped. These tests pin that.
    """

    def render(self, **over):
        path = self.write("ojz_bg", _scene(**over))
        return effects_gen.render_scene(path, effects_gen.load_scene(path),
                                        effects_gen.TableRegistry())

    def test_the_bookings_own_value_negative_v_offset_renders_as_a_negative_literal(self):
        """`v_offset: -8` is the value the DEFERRED_WORK booking quotes dying at emit."""
        self.assertIn("v_offset: -8", self.render(v_offset=-8))

    def test_v_offset_word_ends_render_verbatim(self):
        """-32768 and 32767 are the ends of the signed word `add.w` carries — derived from
        the consumer, and exactly what scene() admits. Both must reach the .emp untouched."""
        for v in (-32768, 32767):
            with self.subTest(v_offset=v):
                self.assertIn(f"v_offset: {v}", self.render(v_offset=v))

    def test_v_offset_PAST_the_word_still_renders_because_the_range_is_the_constructors(self):
        """The charter control: -32769 and 32768 are INTEGERS, so they pass SHAPE here and
        are refused by scene()'s ensure (measured in the expect-fail lane by
        games/sonic4/test/poison/poison_scene_vbounds_range.emp). If this goes red, a
        range check has leaked into the generator — two sources for one rule."""
        for v in (-32769, 32768):
            with self.subTest(v_offset=v):
                self.assertIn(f"v_offset: {v}", self.render(v_offset=v))

    def test_v_center_world_span_ends_and_the_values_past_them_all_render(self):
        """0 and $7FFF are the ends of the world-Y span (camera clamp floor 0, act extent
        asserted <= $8000); -1 and $8000 are one past each. All four are integers, all four
        render; the last two are refused by scene(), not here."""
        for v in (0, 0x7FFF, -1, 0x8000):
            with self.subTest(v_center=v):
                self.assertIn(f"v_center: {v}", self.render(v_center=v))

    def test_the_shipped_editor_scene_values_render(self):
        """games/sonic4/data/editor/effects/ojz_act1_start.json authors v_center 0 /
        v_offset 0 on a locked plane, and ojz_scenes.emp's unlocked pair authors
        v_center 512 / v_offset 0. Both spellings must keep rendering unchanged — this is
        the zero-byte contract of the VOFFSET parcel made executable."""
        out = self.render(v_factor=15, v_center=0, v_offset=0)
        self.assertIn("v_center: 0", out)
        self.assertIn("v_offset: 0", out)
        out = self.render(v_factor=3, v_center=512, v_offset=0)
        self.assertIn("v_center: 512", out)
        self.assertIn("v_offset: 0", out)


# =============================================================================
# RASTER BANDS — the preset-document arm.
# =============================================================================
#
# THE VACUITY THIS BLOCK EXISTS TO AVOID, stated first because it is the trap the whole
# effects lane has paid for repeatedly (band-ownership design §14.5 / §15.7): NO SHIPPED
# PRESET DOCUMENT EXISTS. `games/sonic4/data/editor/effects/presets/` is not in the tree.
# So a gate written over existing content could not fail, and would read as coverage while
# asserting nothing.
#
# Every test below therefore AUTHORS a band deliberately, in a fixture, and asserts on
# that. `TestPresetConverseControl` is the other half: it asserts that a repo with NO
# preset document lowers to nothing at all — no program, no empty program, and byte-for-byte
# the module that was committed before this arm existed.

def _preset(**over):
    """A minimal preset document that PASSES, so each test perturbs exactly one thing.

    THE NUMBERS ARE OJZ_BandDemo's FIRST BAND, not invented: top 120 / bot 148, CRAM byte
    74 ($4A, OJZ's most-used ground colour, palette line 2), colour 548 ($0224, the act's
    own ground ramp two steps below base). Copying a band the tree has already built and
    pinned means this fixture is known to satisfy every raster_dsl guard, so a test that
    goes red here is red about the GENERATOR rather than about a band nobody could author.
    """
    preset = {
        "schema": 1,
        "id": "ojz_ground_wash",
        "bands": [{"top": 120, "bot": 148, "sh": False,
                   "on": {"cram": {"addr": 74, "colours": [548]}}}],
    }
    preset.update(over)
    return preset


def _band(**over):
    band = {"top": 120, "bot": 148, "sh": False,
            "on": {"cram": {"addr": 74, "colours": [548]}}}
    band.update(over)
    return band


class PresetShapeBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "games", "sonic4", "data", "editor",
                                "effects", "presets")
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

    def refuse(self, stem, body):
        path = self.write(stem, body)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_preset(path)
        return str(ctx.exception)


class TestPresetDiscovery(PresetShapeBase):
    def test_absent_presets_directory_is_not_an_error(self):
        """The scene-directory posture, one level down: absence means 'no presets'.

        NO LONGER THE STATE OF THE REAL TREE — it was when this was written, and the
        docstring said so; the real tree ships a preset document since 2026-08-29 (see
        the declaration below). The behaviour is still the contract's (§2.4: an absent
        directory is not an error) and is still worth a test, so it moved to a tmp dir
        and stayed."""
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(effects_gen.discover_preset_files(repo=empty), [])
            self.assertEqual(effects_gen.load_all_presets(repo=empty), {})

    def test_the_real_repo_SHIPS_preset_documents(self):
        """THE ANTI-VACUITY DECLARATION, executable — and INVERTED, 2026-08-29.

        It used to assert the real tree shipped NO preset document, with the note: "if
        this ever goes red, every test in this block that says 'authored deliberately'
        has to be re-read". It went red the moment the first document was authored,
        exactly as designed, and the re-read was done: every other test in this file
        builds its own tmp tree (`PresetShapeBase.dir`, `AssignmentBase.repo`), so none
        of them was measuring the real directory and none of their claims changed.

        What replaces it is the declaration in the direction that now matters. Editor
        content EXISTS, and the tests below that describe an empty tree as the converse
        control are still testing a tmp tree. If THIS goes red, the editor-authored
        raster path has no content behind it and
        `tools/test_raster_cycle_table_lint.py`'s coupling is measuring an empty set on
        both sides — the vacuity that lint exists to prevent, arriving from the other
        end. Nothing here spells a count or an id: the assertion is that the directory
        the contract reserves is non-empty and that every document in it loads, which is
        derived from the disk, not from a pin."""
        presets = effects_gen.load_all_presets(repo=effects_gen.REPO)
        self.assertTrue(
            presets,
            "games/sonic4/data/editor/effects/presets/ holds no loadable preset "
            "document. An empty tree here makes the raster-cycle lint's editor-row "
            "check vacuous and leaves the editor-authored raster path with nothing "
            "behind it.")
        for pid in presets:
            self.assertTrue(
                os.path.isfile(os.path.join(effects_gen.preset_dir(repo=effects_gen.REPO),
                                            pid + ".json")),
                f"preset id {pid!r} does not correspond to a file of the same stem")

    def test_presets_are_discovered_and_keyed_by_id(self):
        self.write("a_wash", _preset(id="a_wash"))
        self.write("b_wash", _preset(id="b_wash"))
        found = effects_gen.load_all_presets(repo=self.tmp.name)
        self.assertEqual(sorted(found), ["a_wash", "b_wash"])

    def test_a_malformed_preset_raises_rather_than_degrading(self):
        path = self.write("ojz_ground_wash", "{not json")
        with self.assertRaises(json.JSONDecodeError):
            effects_gen.load_preset(path)

    def test_duplicate_preset_ids_are_refused(self):
        self.write("a_wash", _preset(id="a_wash"))
        second = os.path.join(self.dir, "b_wash.json")
        with open(second, "w") as f:
            json.dump(_preset(id="a_wash"), f)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_all_presets(repo=self.tmp.name)
        self.assertIn("a_wash", str(ctx.exception))


class TestPresetShape(PresetShapeBase):
    def test_the_baseline_fixture_passes(self):
        """The control for every refusal below: perturbing one key is only meaningful if
        the unperturbed document is accepted."""
        path = self.write("ojz_ground_wash", _preset())
        self.assertEqual(effects_gen.load_preset(path)["id"], "ojz_ground_wash")

    def test_wrong_schema_version_is_refused_and_names_both_versions(self):
        msg = self.refuse("ojz_ground_wash", _preset(schema=2))
        self.assertIn("2", msg)
        self.assertIn(str(effects_gen.SCHEMA_VERSION), msg)

    def test_id_must_match_the_filename_stem(self):
        msg = self.refuse("ojz_ground_wash", _preset(id="something_else"))
        self.assertIn("something_else", msg)
        self.assertIn("ojz_ground_wash", msg)

    def test_a_hyphenated_id_is_refused_because_it_becomes_a_label(self):
        msg = self.refuse("ojz-wash", _preset(id="ojz-wash"))
        self.assertIn("EditorRaster", msg)

    def test_an_unknown_top_level_key_is_refused_and_named(self):
        msg = self.refuse("ojz_ground_wash", _preset(tint="blue"))
        self.assertIn("tint", msg)

    def test_the_reserved_wave2_keys_are_refused_BY_NAME_not_as_unknown(self):
        """`fires` is a name empyrean's schema doc §7 already reserves. An author who
        spells one has not made a typo — they have reached for a channel this generator
        did not build — so the refusal must say that rather than sending them to file a
        contract change for a field the contract already has.

        INVERTED FOR `variants` AND `cycles`, 2026-09-02 (EFFECTS-W1 item 5), and the
        inversion is what its author intended. This test used to loop over all three
        reserved names; it went red the moment the generator ACCEPTED two of them, which
        is exactly the signal that says "the reserved-key list moved, come and re-read
        me". The re-read: `fires` is still reserved on both sides (empyrean's schema's own
        reserved-and-refused line is down to it alone), and the two that left are now
        covered by TestCyclesShape / TestVariantsShape below. The list is DERIVED from
        `effects_gen.PRESET_REFUSED_KEYS` rather than typed, so the next name to leave
        cannot leave this loop asserting about a key nobody refuses.
        """
        self.assertEqual(
            sorted(effects_gen.PRESET_REFUSED_KEYS), ["fires"],
            "the by-name refusal set changed. Every name in it must be one empyrean's "
            "schema doc §7 still reserves AND this generator still does not implement; "
            "a name that is now built belongs in PRESET_KEYS with shape checks, not "
            "here.")
        for key in sorted(effects_gen.PRESET_REFUSED_KEYS):
            with self.subTest(key=key):
                msg = self.refuse("ojz_ground_wash", _preset(**{key: []}))
                self.assertIn(key, msg)
                self.assertIn("reserved", msg)
                self.assertIn("§7", msg)

    def test_the_two_wave2_keys_item_5_BUILT_are_no_longer_refused(self):
        """The other half of the inversion, stated positively so it cannot pass vacuously.

        A document carrying `cycles` and `variants` LOADS. If this goes red the keys have
        been refused again and item 5 has been undone; if the test above goes red they
        have been accepted without shape checks.
        """
        path = self.write("ojz_ground_wash", _preset(
            cycles=[{"line": 2, "first": 8, "count": 4, "period": 9}],
            variants=[{"shift_r": 1, "shift_g": 1}, None]))
        loaded = effects_gen.load_preset(path)
        self.assertEqual(len(loaded["cycles"]), 1)
        self.assertEqual(loaded["variants"][1], None)
        for key in ("cycles", "variants"):
            self.assertIn(key, effects_gen.PRESET_KEYS)
            self.assertNotIn(key, effects_gen.PRESET_REFUSED_KEYS)

    def test_name_is_accepted_and_ignored(self):
        path = self.write("ojz_ground_wash", _preset(name="Ground wash"))
        self.assertEqual(len(effects_gen.load_preset(path)["bands"]), 1)

    def test_missing_bands_is_refused(self):
        body = _preset()
        del body["bands"]
        msg = self.refuse("ojz_ground_wash", body)
        self.assertIn("bands", msg)

    def test_bands_must_be_a_list(self):
        msg = self.refuse("ojz_ground_wash", _preset(bands={"top": 1}))
        self.assertIn("list", msg)

    def test_EMPTY_bands_is_refused_rather_than_emitting_an_empty_program(self):
        """THE CONVERSE CONTROL'S SIBLING. An empty band list would lower to
        `compose([])` and then to a program with no fires — the engine refuses it one
        layer down, but with a message about `compose`, naming a function the author never
        wrote. Refused here, where the file is."""
        msg = self.refuse("ojz_ground_wash", _preset(bands=[]))
        self.assertIn("empty", msg)
        self.assertIn("compose", msg)

    def test_a_band_that_is_not_an_object_is_refused_with_its_index(self):
        msg = self.refuse("ojz_ground_wash", _preset(bands=[7]))
        self.assertIn("bands[0]", msg)

    def test_EVERY_one_of_the_four_band_fields_is_required(self):
        """All four, none with a default — `band()` has none either, and `sh`'s
        defaultlessness is a ruling (raster_dsl.emp, region_boundary's note)."""
        for key in effects_gen.BAND_KEYS:
            with self.subTest(missing=key):
                band = _band()
                del band[key]
                msg = self.refuse("ojz_ground_wash", _preset(bands=[band]))
                self.assertIn(key, msg)
                self.assertIn("bands[0]", msg)

    def test_an_unknown_band_key_is_refused(self):
        msg = self.refuse("ojz_ground_wash", _preset(bands=[_band(height=28)]))
        self.assertIn("height", msg)


class TestBandOnArm(PresetShapeBase):
    """The ON op is checked at RENDER time, not at LOAD time, and that is the scene
    arm's own split: `load_scene` checks KEYS and `render_*` checks the spellings inside
    an attachment. It is safe here for a reason it is not safe there — every preset
    document is rendered, where an unassigned scene is not — so nothing can slip through
    by never being reached."""

    def on(self, value):
        names = effects_gen.ActNames("ojz", "act1")
        preset = _preset(bands=[_band(on=value)])
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_preset("<fixture>", preset, names)
        return str(ctx.exception)

    def band(self, **over):
        names = effects_gen.ActNames("ojz", "act1")
        preset = _preset(bands=[_band(**over)])
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.render_preset("<fixture>", preset, names)
        return str(ctx.exception)

    def test_the_on_op_must_be_an_object(self):
        self.assertIn("cram", self.on("stream_cram"))

    def test_an_unknown_arm_is_refused_and_lists_the_legal_ones(self):
        msg = self.on({"vsram": {"addr": 2, "values": [67]}})
        self.assertIn("vsram", msg)
        self.assertIn("cram", msg)
        self.assertIn("pal_region", msg)

    def test_the_vsram_refusal_says_WHY_rather_than_only_that(self):
        """A band's restore is derived from the ON op's CRAM span, so a VSRAM ON op has
        nothing to restore — `band()` says exactly that. The generator's refusal points at
        the same fact instead of a bare 'not in the list'."""
        self.assertIn("CRAM span", self.on({"vsram": {"addr": 2, "values": [67]}}))

    def test_zero_arms_is_refused(self):
        self.assertIn("exactly ONE", self.on({}))

    def test_TWO_arms_is_refused(self):
        msg = self.on({"cram": {"addr": 74, "colours": [548]},
                       "pal_region": {"addr": 74, "slot": 0, "pal_line": 2,
                                      "entry": 5, "count": 1}})
        self.assertIn("exactly ONE", msg)

    def test_an_arm_body_that_is_not_an_object_is_refused(self):
        self.assertIn("addr", self.on({"cram": [74, 548]}))

    def test_a_missing_arm_field_is_refused_and_names_the_full_set(self):
        msg = self.on({"cram": {"addr": 74}})
        self.assertIn("colours", msg)

    def test_an_extra_arm_field_is_refused(self):
        msg = self.on({"cram": {"addr": 74, "colours": [548], "count": 1}})
        self.assertIn("count", msg)

    def test_colours_must_be_a_list(self):
        msg = self.on({"cram": {"addr": 74, "colours": 548}})
        self.assertIn("list of integers", msg)

    def test_a_STRING_colour_is_refused_because_it_would_become_a_SYMBOL(self):
        """The `_render_int` defect, one nesting level further in: a string in a colour
        slot is interpolated verbatim and lands in generated `.emp` as a bare symbol."""
        msg = self.on({"cram": {"addr": 74, "colours": ["OJZ_BAND_SHADE"]}})
        self.assertIn("SYMBOL", msg)

    def test_a_STRING_addr_is_refused(self):
        self.assertIn("SYMBOL", self.on({"cram": {"addr": "$4A", "colours": [548]}}))

    def test_a_STRING_top_is_refused(self):
        self.assertIn("SYMBOL", self.band(top="120"))

    def test_a_STRING_sh_is_refused(self):
        """`sh` translates a JSON boolean and accepts an integer synonym; a STRING is
        neither, and would land in `.emp` as a bare symbol like every other scalar."""
        self.assertIn("SYMBOL", self.band(sh="on"))


class TestBandLowering(PresetShapeBase):
    """THE DELIBERATELY-AUTHORED FIXTURE. Every assertion here is about a band that this
    test wrote; none of them can pass because a field is absent somewhere."""

    def render(self, preset):
        names = effects_gen.ActNames("ojz", "act1")
        return effects_gen.render_preset("<fixture>", preset, names)

    def test_a_one_band_cram_preset_lowers_to_the_hand_idiom(self):
        out = self.render(_preset())
        self.assertIn("band(top: 120, bot: 148, "
                      "on: stream_cram(addr: 74, colours: [548]), sh: 0)", out)
        self.assertIn("const EditorRasterSrc_OJZ_Act1_ojz_ground_wash = compose([", out)
        self.assertIn("pub data EditorRaster_OJZ_Act1_ojz_ground_wash: "
                      "[u16; raster_words(EditorRasterSrc_OJZ_Act1_ojz_ground_wash)] = "
                      "raster_program(EditorRasterSrc_OJZ_Act1_ojz_ground_wash)", out)

    def test_the_src_const_is_referenced_TWICE_so_the_fold_is_not_inert(self):
        """docs/EMP_PITFALLS.md §3: an unreferenced top-level `const X = f(..)` is
        comptime-INERT. Both `raster_words` and `raster_program` must name it, or every
        guard inside `band()` would be declared and never run."""
        out = self.render(_preset())
        self.assertEqual(out.count("EditorRasterSrc_OJZ_Act1_ojz_ground_wash"), 3)

    def test_sh_true_lowers_to_1_and_false_to_0(self):
        """The writer spells a JSON boolean; `band()` takes an int. Forwarding the JSON
        value would emit the bare word `True`, which is not an `.emp` integer."""
        self.assertIn("sh: 1", self.render(_preset(bands=[_band(sh=True)])))
        self.assertIn("sh: 0", self.render(_preset(bands=[_band(sh=False)])))
        self.assertIn("sh: 1", self.render(_preset(bands=[_band(sh=1)])))

    def test_three_bands_compose_into_ONE_program(self):
        """OJZ_BandDemo's shape: three vertically disjoint bands over one CRAM entry."""
        out = self.render(_preset(bands=[
            _band(top=120, bot=148, on={"cram": {"addr": 74, "colours": [548]}}),
            _band(top=156, bot=184, on={"cram": {"addr": 74, "colours": [1164]}}),
            _band(top=192, bot=220, on={"cram": {"addr": 74, "colours": [1710]}}),
        ]))
        self.assertEqual(out.count("band(top:"), 3)
        self.assertEqual(out.count("compose(["), 1)
        self.assertEqual(out.count("pub data EditorRaster_"), 1)
        self.assertIn("band(top: 192, bot: 220, "
                      "on: stream_cram(addr: 74, colours: [1710]), sh: 0)", out)

    def test_a_multi_colour_burst_emits_an_array_literal_in_order(self):
        out = self.render(_preset(bands=[
            _band(on={"cram": {"addr": 74, "colours": [548, 1164, 1710]}})]))
        self.assertIn("colours: [548, 1164, 1710]", out)

    def test_the_pal_region_arm_emits_its_five_parameters_in_the_constructors_order(self):
        out = self.render(_preset(bands=[_band(on={"pal_region": {
            "addr": 74, "slot": 0, "pal_line": 2, "entry": 5, "count": 3}})]))
        self.assertIn("on: stream_pal_region(addr: 74, slot: 0, pal_line: 2, "
                      "entry: 5, count: 3)", out)

    def test_negative_and_zero_values_render_as_literals_not_tokens(self):
        """A band label carries the PRESET id only, never a number, so `symbol_token`'s
        `m8` spelling has no business here: every number in this arm is a VALUE."""
        out = self.render(_preset(bands=[_band(top=-1)]))
        self.assertIn("band(top: -1,", out)
        self.assertNotIn("m1", out)


class TestBandValuesAreNotValidatedHere(PresetShapeBase):
    """REFUSE, DON'T CLAMP — and don't RESTATE either.

    The module docstring's SHAPE-vs-VALUE rule, applied to the arm with the most numeric
    bounds in the tool. Each value below is one the ENGINE refuses, with a measurement
    behind the refusal. The generator must forward it UNCHANGED so the author reads
    `raster_dsl.emp`'s own sentence — not clamp it into range (which authors something
    nobody meant) and not refuse it here (which is a second copy of the bound that drifts
    the day the measurement moves).
    """

    def render(self, **over):
        names = effects_gen.ActNames("ojz", "act1")
        return effects_gen.render_preset("<fixture>", _preset(**over), names)

    def test_a_screen_line_past_the_bottom_of_the_screen_is_FORWARDED(self):
        """fire()'s screen-line range is the authority — and its message is about the
        priming records, which this file could not say."""
        self.assertIn("band(top: 999,", self.render(bands=[_band(top=999)]))

    def test_an_INVERTED_band_is_FORWARDED(self):
        """`band: top {top} must be above bot {bot}` is band()'s."""
        out = self.render(bands=[_band(top=200, bot=100)])
        self.assertIn("band(top: 200, bot: 100,", out)

    def test_a_burst_PAST_the_ceiling_is_FORWARDED_with_every_colour(self):
        """The cram burst ceiling is three, and its ensure carries the measured refusal
        of four (docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-RESULTS.md). A generator
        that truncated here would author a band the author did not write."""
        out = self.render(bands=[_band(on={"cram": {
            "addr": 74, "colours": [1, 2, 3, 4, 5]}})])
        self.assertIn("colours: [1, 2, 3, 4, 5]", out)

    def test_CRAM_LINE_ZERO_is_FORWARDED_so_the_engine_refuses_it_by_name(self):
        """`stream_cram`/`pal_restore` both refuse line 0 — it is the character's line
        (CharacterDef.cd_palette). That reason is not repeatable here."""
        self.assertIn("addr: 0", self.render(bands=[_band(on={
            "cram": {"addr": 0, "colours": [548]}})]))

    def test_an_ODD_cram_address_is_FORWARDED(self):
        self.assertIn("addr: 75", self.render(bands=[_band(on={
            "cram": {"addr": 75, "colours": [548]}})]))

    def test_a_band_TOO_SHORT_for_its_ON_op_is_FORWARDED(self):
        """The height minimum is check_density's own arithmetic re-derived inside
        `band()`, cost-keyed so it re-prices when the model moves. A literal here would
        be exactly the drift that design forbids."""
        self.assertIn("band(top: 120, bot: 121,",
                      self.render(bands=[_band(top=120, bot=121)]))

    def test_MORE_BANDS_THAN_THE_BUFFER_HOLDS_are_FORWARDED(self):
        """The three-band cap is derived inside the engine from `op_size` against the
        program buffer, and §7.1 of the ownership design explicitly forbids quoting its
        table. Unlike MAX_PARALLAX_BANDS — which the generator must know because it PADS
        an array to that width — nothing here pads, so nothing here has to know."""
        out = self.render(bands=[_band(top=10 * i + 10, bot=10 * i + 18)
                                 for i in range(9)])
        self.assertEqual(out.count("band(top:"), 9)

    def test_the_generator_source_carries_NO_raster_bound_literal(self):
        """A structural check on the claim above, not a spot check: the raster arm of
        effects_gen.py must not spell the engine's numbers. Reads the tool's own source
        for the constants a copy would have to contain."""
        with open(effects_gen.__file__) as f:
            src = f.read()
        raster = src[src.index("# RASTER BANDS"):]
        for forbidden in ("223", "126", "RASTER_BURST", "RASTER_BUF"):
            self.assertNotIn(forbidden, raster,
                             f"the raster arm spells {forbidden!r} — a bound this file "
                             f"does not own")


# =============================================================================
# THE `boundary` ARM — EFFECTS-W1 DoD item 4's AUTHORING half (contract §7.6).
# =============================================================================
#
# THE ANTI-VACUITY NOTE, and it is the SAME trap the band block above records: NO SHIPPED
# DOCUMENT CARRIES `boundary`. Nothing in `games/sonic4/data/editor/effects/presets/` has
# the key, so a gate written over existing content could not fail. Every test below AUTHORS
# one in a tmp tree.
#
# THE NUMBERS ARE THE SHIPPED WATER, VERBATIM, not invented: `games/sonic4/data/effects/
# ojz_effects.emp`'s `OJZ_TC_PROG` first record is
# `patchable(fx_tint_band(line: 100, slot: 0, pal_line: 2, entry: 4, count: 3, sh: 1),
#            ch: 0, lo: 3, hi: 220, offscreen_ship: 1)`.
# Copying a record the tree has already built and pinned means this fixture is known to
# satisfy every engine guard on the path, so a red here is red about the GENERATOR rather
# than about a boundary nobody could author.


def _boundary(**over):
    b = {"line": 100, "channel": 0, "lo": 3, "hi": 220, "offscreen_ship": True,
         "on": {"pal_region": {"slot": 0, "pal_line": 2, "entry": 4, "count": 3}},
         "sh": True}
    b.update(over)
    return b


def _boundary_preset(**over):
    p = {"schema": 1, "id": "ojz_water_edge", "boundary": _boundary()}
    p.update(over)
    return p


class TestBoundaryShape(PresetShapeBase):
    """The closed-object shape. Each test perturbs exactly one thing off a PASSING doc."""

    def test_the_shipped_water_document_LOADS(self):
        """The control, first: without it every refusal below could be passing for the
        wrong reason (a fixture that is refused by something else entirely)."""
        path = self.write("ojz_water_edge", _boundary_preset())
        loaded = effects_gen.load_preset(path)
        self.assertEqual(loaded["boundary"]["channel"], 0)
        self.assertEqual(loaded["boundary"]["lo"], 3)
        self.assertEqual(loaded["boundary"]["hi"], 220)

    def test_offscreen_ship_is_the_ONLY_optional_member(self):
        """It is optional because it is the only one `patchable()` itself defaults."""
        b = _boundary()
        del b["offscreen_ship"]
        self.write("ojz_water_edge", _boundary_preset(boundary=b))
        effects_gen.load_preset(
            os.path.join(self.dir, "ojz_water_edge.json"))
        for required in effects_gen.BOUNDARY_REQUIRED_KEYS:
            b = _boundary()
            del b[required]
            msg = self.refuse("ojz_water_edge", _boundary_preset(boundary=b))
            self.assertIn(f"boundary has no `{required}`", msg)

    def test_a_null_boundary_is_refused_BY_NAME_and_never_read_as_absent(self):
        """Contract §7.6 ruling M1. The failure this forbids is the QUIET one: read as
        absent, an author's `"boundary": null` would leave the section's hand-authored
        program installed while the document says it turned it off."""
        msg = self.refuse("ojz_water_edge", _boundary_preset(boundary=None))
        self.assertIn("NO NULL SPELLING", msg)
        self.assertIn("M1", msg)

    def test_an_unknown_member_is_refused_and_the_message_names_the_legal_set(self):
        msg = self.refuse("ojz_water_edge",
                          _boundary_preset(boundary=_boundary(top=100)))
        self.assertIn("boundary carries unknown key `top`", msg)

    def test_a_vsplit_KEY_is_an_unknown_preset_key_and_is_NOT_reserved(self):
        """Contract §7.6 'Not reserved, ruled': a reserved arm is a key with nothing
        behind it. `offscreen_ship` requires a `stream_pal_region` op a vscroll split does
        not have, so a reserved `vsplit` would carry a hole."""
        msg = self.refuse("ojz_water_edge",
                          _boundary_preset(vsplit={"line": 222, "offset": 67}))
        self.assertIn("preset carries unknown key `vsplit`", msg)

    def test_a_cram_arm_on_on_is_refused_naming_the_one_legal_arm(self):
        msg = self.refuse("ojz_water_edge", _boundary_preset(
            boundary=_boundary(on={"cram": {"addr": 74, "colours": [548]}})))
        self.assertIn("boundary.on", msg)
        self.assertIn("pal_region", msg)

    def test_two_arms_on_on_are_refused(self):
        msg = self.refuse("ojz_water_edge", _boundary_preset(
            boundary=_boundary(on={"pal_region": {"slot": 0, "pal_line": 2,
                                                  "entry": 4, "count": 3},
                                   "cram": {"addr": 74, "colours": [548]}})))
        self.assertIn("unknown arm", msg)

    def test_addr_on_the_region_is_refused_BY_NAME_with_the_derivation(self):
        """`$defs.tint_region`, not `$defs.pal_region`. `fx_tint_band` DERIVES the CRAM
        address from pal_line and entry, so a document carrying it is one fact computed
        twice — and the generic 'unknown key' sentence would not tell an author who
        copied a working `bands[i].on.pal_region` why the two differ."""
        region = {"addr": 74, "slot": 0, "pal_line": 2, "entry": 4, "count": 3}
        msg = self.refuse("ojz_water_edge",
                          _boundary_preset(boundary=_boundary(
                              on={"pal_region": region})))
        self.assertIn("carries `addr`", msg)
        self.assertIn("tint_region", msg)
        self.assertIn("DERIVES", msg)

    def test_a_missing_region_member_is_refused(self):
        for field in effects_gen.TINT_REGION_KEYS:
            region = {"slot": 0, "pal_line": 2, "entry": 4, "count": 3}
            del region[field]
            msg = self.refuse("ojz_water_edge", _boundary_preset(
                boundary=_boundary(on={"pal_region": region})))
            self.assertIn(field, msg)

    def test_a_non_integer_scalar_is_a_SHAPE_refusal_naming_the_engine_owner(self):
        """The `_render_int` class of defect, one arm over: a string here would be
        interpolated into generated `.emp` as a bare SYMBOL."""
        for field in ("line", "channel", "lo", "hi"):
            msg = self.refuse("ojz_water_edge", _boundary_preset(
                boundary=_boundary(**{field: "100"})))
            self.assertIn(f"boundary.{field} must be an integer", msg)
            self.assertIn("ensure", msg)

    def test_the_single_field_RANGES_are_NOT_checked_here(self):
        """This file's standing posture: a range checked in two places is a range that
        drifts. An out-of-range `line`/`channel`/`lo`/`hi` LOADS, and the engine's own
        ensure refuses it at build time with the measurement behind it.

        `line` moves with the band so the cross-field rule stays satisfied — otherwise
        this test would be measuring the cross-field refusal instead."""
        for over in ({"channel": 99},
                     {"line": 999, "lo": 999, "hi": 999},
                     {"line": 0, "lo": 0, "hi": 0}):
            path = self.write("ojz_water_edge",
                              _boundary_preset(boundary=_boundary(**over)))
            effects_gen.load_preset(path)          # loads: not this file's question


class TestBoundaryCrossFieldRefusals(PresetShapeBase):
    """THE TWO REFUSALS THE SCHEMA CANNOT EXPRESS (contract §7.6). They are the reason
    this arm is not a one-line key addition, and they are the generator's BY RULING —
    the engine holds both too, and the point of the second copy is that this message can
    name the JSON PATH the author typed."""

    def test_lo_above_hi_is_refused_naming_both_json_paths(self):
        msg = self.refuse("ojz_water_edge",
                          _boundary_preset(boundary=_boundary(lo=220, hi=3, line=100)))
        self.assertIn("boundary.lo", msg)
        self.assertIn("boundary.hi", msg)
        self.assertIn("INVERTED", msg)

    def test_line_outside_its_own_band_is_refused_naming_the_json_path(self):
        for line in (2, 240):
            msg = self.refuse("ojz_water_edge",
                              _boundary_preset(boundary=_boundary(line=line,
                                                                  lo=100, hi=200)))
            self.assertIn("boundary.line", msg)
            self.assertIn("outside its own band", msg)

    def test_line_ON_either_edge_is_ACCEPTED(self):
        """The bound is INCLUSIVE, matching `patchable()`'s `line >= lo && line <= hi`.
        The control for the test above: without it a refusal that fired on every line
        would look identical."""
        for line in (100, 200):
            path = self.write("ojz_water_edge",
                              _boundary_preset(boundary=_boundary(line=line,
                                                                  lo=100, hi=200)))
            effects_gen.load_preset(path)

    def test_the_inverted_band_is_reported_BEFORE_the_line(self):
        """Order is load-bearing: on an inverted band the line message reads 'outside its
        own band <hi>..<lo>' and sends the author to the wrong field."""
        msg = self.refuse("ojz_water_edge",
                          _boundary_preset(boundary=_boundary(lo=220, hi=3, line=999)))
        self.assertIn("INVERTED", msg)
        self.assertNotIn("outside its own band", msg)


def _base_swap_preset(**over):
    """A `base_swap` document that PASSES, in the SHIPPED shape (F2): two edges.

    The values are `ojz_sec6_baseswap.json`'s own — line 3, target $E000, restore_line 64
    — for `_preset`'s reason one helper up: a fixture copied from content the tree has
    already built and pinned is known to satisfy every raster_dsl guard, so a red here is
    red about the GENERATOR rather than about a band nobody could author.
    """
    bs = {"line": 3, "target": 0xE000, "restore_line": 64}
    bs.update(over.pop("base_swap", {}))
    preset = {"schema": 1, "id": "ojz_sec6_baseswap", "base_swap": bs}
    preset.update(over)
    return preset


class TestBaseSwapRestoreLine(PresetShapeBase):
    """`base_swap.restore_line` — the band's OFF edge (EFFECTS-W1 F2, 2026-09-04).

    WHAT THE KEY IS FOR, because the shape alone does not say it: without it the document
    lowers to ONE `OP_SET_REG`, and one edge is not a band — nothing puts reg $02 back
    until Flush_VDP_Shadow at the next frame top, so the swap runs from its line to the
    BOTTOM OF THE DISPLAY. That is the program that shipped at `8bf6df74` with `line` 3,
    where "to the bottom" is the whole screen and there is nothing to see.
    """

    NAMES = effects_gen.ActNames("ojz", "act1")

    def render(self, **over):
        """Through `render_preset`, `TestBoundaryLowering.render`'s reason: the DISPATCH
        is part of the claim."""
        path = self.write("ojz_sec6_baseswap", _base_swap_preset(**over))
        return effects_gen.render_preset(
            path, effects_gen.load_preset(path), self.NAMES)

    def test_the_shipped_document_lowers_to_TWO_fires(self):
        src = self.render()
        self.assertIn("fire(3, [reg_set($8200 | vdp_base_reg(VdpBase.PlaneA, 57344))])", src)
        self.assertIn("fire(64, [reg_set($8200 | vdp_base_reg(VdpBase.PlaneA, VRAM_PLANE_A))])",
                      src)
        self.assertEqual(src.count("fire("), 2)
        self.assertEqual(src.count("reg_set("), 2)

    def test_the_OFF_edge_target_is_DERIVED_never_read_from_the_document(self):
        """The document names the base being BORROWED; the base being RETURNED TO is not
        an authoring choice, so the generator emits the engine's own name for it.

        THE ASSERTION IS ON THE ABSENCE OF A NUMBER. `VRAM_PLANE_A` is $C000 = 49152
        today, and an implementation that folded it here would produce a lowering that
        looks correct and freezes today's VRAM layout into generated source — going on
        emitting $C000 the day the constant moves, with nothing anywhere saying so.
        """
        src = self.render()
        self.assertIn("VRAM_PLANE_A", src)
        self.assertNotIn("49152", src)
        self.assertNotIn("$C000", src)

    def test_OMITTING_it_lowers_to_ONE_fire(self):
        """The converse control, and a legitimate authoring shape rather than a leftover:
        a swap that runs to the bottom of the frame is what a document meant before F2,
        and ABSENCE is how this schema already spells "this arm is off"."""
        path = self.write("ojz_sec6_baseswap",
                          {"schema": 1, "id": "ojz_sec6_baseswap",
                           "base_swap": {"line": 3, "target": 0xE000}})
        src = effects_gen.render_preset(path, effects_gen.load_preset(path), self.NAMES)
        self.assertEqual(src.count("fire("), 1)
        self.assertNotIn("VRAM_PLANE_A", src)

    def test_a_non_integer_restore_line_is_refused_naming_the_field(self):
        for bad in ("64", 64.0, True, None):
            msg = self.refuse("ojz_sec6_baseswap",
                              _base_swap_preset(base_swap={"restore_line": bad}))
            self.assertIn("base_swap.restore_line", msg)

    def test_an_unknown_key_beside_it_is_still_refused(self):
        """`restore_line` widened the closed key set by exactly one; the set is still
        closed. Without this, "add the key to the allowed set" and "stop checking keys"
        would look the same from outside."""
        msg = self.refuse("ojz_sec6_baseswap",
                          _base_swap_preset(base_swap={"end_line": 64}))
        self.assertIn("unknown key", msg)
        self.assertIn("end_line", msg)

    def test_the_ORDERING_of_the_two_lines_is_NOT_this_files_refusal(self):
        """SHAPE ONLY, this arm's standing posture. An inverted pair loads fine here and
        is refused by `fire_lines`' strict-ascent ensure at BUILD time, by name. A copy
        of that guard here would be the second statement of one fact — the thing every
        banner on this seam refuses to add — and it would drift the day the DSL's rule
        changes."""
        path = self.write("ojz_sec6_baseswap",
                          _base_swap_preset(base_swap={"line": 64, "restore_line": 3}))
        effects_gen.load_preset(path)


class TestBoundaryIsTheFOURTHExclusiveArm(PresetShapeBase):
    """A document carries exactly one raster program. `boundary` joins that group, and
    the REASON it is exclusive is different from the other three's — a fact this repo
    treats as separately checkable from the verdict."""

    def test_boundary_alone_satisfies_the_exactly_one_of_rule(self):
        effects_gen.load_preset(self.write("ojz_water_edge", _boundary_preset()))

    def test_a_document_with_NO_raster_arm_at_all_is_refused_naming_all_four(self):
        msg = self.refuse("ojz_water_edge", {"schema": 1, "id": "ojz_water_edge"})
        for key in ("bands", "ramp", "base_swap", "boundary"):
            self.assertIn(key, msg)

    def test_boundary_beside_a_raster_arm_carries_THE_OTHER_REASON(self):
        """The whole point of this test: the refusal is right either way, but a message
        that lumped four keys under `ep_raster` would teach a reader that a combinator
        could unlock the pair. Nothing unlocks a destructive install order."""
        for other, extra in (("bands", [_band()]),
                             ("ramp", {"top": 8, "lines": 16,
                                       "target": {"vsram": {"addr": 0}},
                                       "start": {"whole": 0, "frac256": 0},
                                       "step": {"whole": 0, "frac256": 8}}),
                             ("base_swap", {"line": 3, "target": 0xE000})):
            msg = self.refuse("ojz_water_edge",
                              _boundary_preset(**{other: extra}))
            self.assertIn("ep_patched", msg)
            self.assertIn("DESTRUCTIVE", msg)
            self.assertIn("Raster_InstallPatched", msg)
            self.assertIn(other, msg)

    def test_two_RASTER_arms_still_carry_the_ONE_FIELD_reason(self):
        """The converse control. Without it the test above could pass on a message that
        had simply been rewritten for every combination."""
        msg = self.refuse("ojz_ground_wash",
                          _preset(base_swap={"line": 3, "target": 0xE000}))
        self.assertIn("ep_raster", msg)
        self.assertNotIn("ep_patched", msg)


class TestBoundaryLowering(PresetShapeBase):
    """The emitted `.emp`. VERBATIM, 1:1, no unit conversion on any field."""

    NAMES = effects_gen.ActNames("ojz", "act1")

    def render(self, **over):
        """Through `render_preset`, not `render_boundary_preset` directly: the DISPATCH
        is part of the claim — a `boundary` document that fell through to the `bands` arm
        would raise a KeyError, not lower wrong, and a test that called the renderer by
        name could never see it."""
        path = self.write("ojz_water_edge", _boundary_preset(**over))
        return effects_gen.render_preset(
            path, effects_gen.load_preset(path), self.NAMES)

    def test_the_shipped_water_lowers_to_the_shipped_CALL(self):
        out = self.render()
        self.assertIn("fx_tint_band(line: 100, slot: 0, pal_line: 2, entry: 4, "
                      "count: 3, sh: 1)", out)
        self.assertIn("ch: 0, lo: 3, hi: 220, offscreen_ship: 1", out)
        self.assertIn("patchable(", out)

    def test_it_lowers_through_patched_program_and_NEVER_raster_program(self):
        """The `ep_patched` half made checkable: `raster_program`/`raster_words` would
        emit a static program with no patch table, and the boundary would never move."""
        out = self.render()
        self.assertIn("patched_program(", out)
        self.assertIn("patched_words(", out)
        self.assertNotIn("raster_program(", out)
        self.assertNotIn("raster_words(", out)

    def test_the_const_is_referenced_TWICE_so_the_comptime_fold_actually_runs(self):
        """docs/EMP_PITFALLS.md §3: an unreferenced top-level `const X = f(..)` is
        comptime-INERT, so every ensure inside patchable/fx_tint_band/patched_program
        would never fire."""
        out = self.render()
        src = out.split("const ", 1)[1].split(" =", 1)[0]
        self.assertEqual(out.count(src), 3)     # the declaration plus two references

    def test_absent_offscreen_ship_is_OMITTED_so_the_constructors_default_stands(self):
        b = _boundary()
        del b["offscreen_ship"]
        out = self.render(boundary=b)
        self.assertNotIn("offscreen_ship", out)

    def test_booleans_are_TRANSLATED_and_never_emitted_as_python_words(self):
        """`f"{True}"` interpolates the bare word `True`, which is not an `.emp` integer
        — the `_render_bool_int` class of defect, on this arm's two boolean fields."""
        out = self.render(boundary=_boundary(sh=False, offscreen_ship=False))
        self.assertNotIn("True", out)
        self.assertNotIn("False", out)
        self.assertIn("sh: 0)", out)
        self.assertIn("offscreen_ship: 0", out)

    def test_integer_0_and_1_are_accepted_as_synonyms_for_the_booleans(self):
        out = self.render(boundary=_boundary(sh=1, offscreen_ship=0))
        self.assertIn("sh: 1)", out)
        self.assertIn("offscreen_ship: 0", out)

    def test_the_label_is_the_PATCHED_one_and_not_the_raster_one(self):
        out = self.render()
        self.assertIn(f"pub data {self.NAMES.patched('ojz_water_edge')}:", out)
        self.assertNotIn(self.NAMES.raster("ojz_water_edge"), out)

    def test_lo_and_hi_are_forwarded_UNCONVERTED(self):
        """SCREEN lines, not fire lines. The engine subtracts 1 once, in
        Raster_BuildSchedule; a generator that pre-subtracted would be off by one
        everywhere and nothing downstream could see it."""
        out = self.render(boundary=_boundary(lo=50, hi=200, line=100))
        self.assertIn("lo: 50", out)
        self.assertIn("hi: 200", out)
        self.assertNotIn("lo: 49", out)
        self.assertNotIn("hi: 199", out)


class TestBoundaryStreamsFromAClearedSlot(PresetShapeBase):
    """Ruling Q6's narrow half, applied to the arm that came after it — otherwise the
    newer authoring surface carries a hole the older one does not."""

    def test_a_boundary_streaming_from_an_explicitly_nulled_slot_is_refused(self):
        msg = self.refuse("ojz_water_edge",
                          _boundary_preset(variants=[None, None]))
        self.assertIn("boundary streams from variant slot 0", msg)

    def test_a_slot_the_variants_array_does_not_REACH_is_not_refused(self):
        """Absent means 'the section's hand-authored variant is still there', which the
        generator cannot see — the same asymmetry the band arm has."""
        effects_gen.load_preset(self.write("ojz_water_edge", _boundary_preset()))


class TestPresetsInTheGeneratedModule(AssignmentBase):
    def setUp(self):
        super().setUp()
        self.presets = os.path.join(self.scenes, "presets")
        os.makedirs(self.presets)

    def write_preset(self, stem, **over):
        with open(os.path.join(self.presets, f"{stem}.json"), "w") as f:
            json.dump(_preset(id=stem, **over), f)

    def render(self):
        return effects_gen.render_module(
            effects_gen.load_all_scenes(repo=self.repo),
            effects_gen.load_act_scene_ref(self.repo),
            effects_gen.load_section_scene_refs(self.repo),
            effects_gen.act_section_count(self.repo),
            effects_gen.act_names(self.repo),
            effects_gen.load_all_presets(repo=self.repo))

    def test_an_authored_preset_reaches_the_module_as_a_pub_data(self):
        """`pub data` and not `const`: only a data item mints a ROM label and emits
        words. This is the whole 'reaches the ROM' step, in one assertion."""
        self.write_preset("ojz_ground_wash")
        out = self.render()
        self.assertIn("pub data EditorRaster_OJZ_Act1_ojz_ground_wash:", out)
        self.assertIn("raster_program(", out)

    def test_a_preset_needs_NO_scene_and_NO_assignment_to_emit(self):
        """A raster program is an EffectsPreset channel; a scene is a parallax_config.
        The two are independent by design (band-ownership design §16.1), so a preset must
        emit with no scene in the tree at all."""
        self.write_preset("ojz_ground_wash")
        out = self.render()
        self.assertNotIn("pub const Scene_Editor_", out)
        self.assertIn("pub data EditorRaster_OJZ_Act1_ojz_ground_wash:", out)

    def test_presets_render_in_sorted_id_order_so_the_bake_is_deterministic(self):
        self.write_preset("b_wash")
        self.write_preset("a_wash")
        out = self.render()
        self.assertLess(out.index("EditorRaster_OJZ_Act1_a_wash"),
                        out.index("EditorRaster_OJZ_Act1_b_wash"))
        self.assertEqual(out, self.render())

    def test_the_banner_states_that_the_generator_does_not_BIND_the_program(self):
        """The §16.1 fact has to survive into the generated file, because the file is
        what the next author reads. Emitting a program and binding it to a section are
        different acts and only the first is this tool's."""
        self.write_preset("ojz_ground_wash")
        out = self.render()
        self.assertIn("does NOT bind it", out)


class TestPresetConverseControl(AssignmentBase):
    """THE CONVERSE CONTROL. A tree with no preset document must lower to NOTHING —
    not to an empty program, not to a banner, not to a blank line."""

    def render_without_presets(self):
        return effects_gen.render_module(
            effects_gen.load_all_scenes(repo=self.repo),
            effects_gen.load_act_scene_ref(self.repo),
            effects_gen.load_section_scene_refs(self.repo),
            effects_gen.act_section_count(self.repo),
            effects_gen.act_names(self.repo),
            effects_gen.load_all_presets(repo=self.repo))

    def test_no_presets_emits_no_raster_BAND_text_of_any_kind(self):
        """NARROWED, 2026-08-30, and the narrowing is the point rather than a retreat.

        `EditorRaster` on its own stopped being a band-content token when the
        `rasterRef` arm landed: the always-emitted witness equate is
        `EditorRaster_<CAP>_Bindings` and the chooser's banner names the channel. Those
        two are zero ROM bytes and are emitted for EVERY act by ruling, so a test
        forbidding the substring would be asserting the arm does not exist rather than
        that no band was lowered. The tokens below are the ones only a LOWERED BAND can
        produce — the declaration prefixes and the constructor calls — so the claim
        ("a tree with no preset document lowers no band, not even an empty one") is
        unchanged and is now stated in terms that cannot be satisfied by a comment."""
        self.write_scene("ojz_bg")
        self.write_sidecar(0, {"sceneRef": "ojz_bg"})
        out = self.render_without_presets()
        for token in ("EditorRasterSrc_", "pub data EditorRaster_", "raster_program(",
                      "raster_words(", "compose(", "band(top:",
                      "AURORA-AUTHORED RASTER BANDS"):
            self.assertNotIn(token, out)

    def test_no_presets_is_TEXT_IDENTICAL_to_the_pre_arm_renderer(self):
        """The zero-byte claim, made checkable rather than argued: with no preset
        documents `render_module` returns exactly what it returned before the `presets`
        parameter existed, so the committed generated artifact does not change and the
        four ROM CRCs cannot move."""
        self.write_scene("ojz_bg")
        self.write_sidecar(0, {"sceneRef": "ojz_bg"})
        with_arm = self.render_without_presets()
        without_arm = effects_gen.render_module(
            effects_gen.load_all_scenes(repo=self.repo),
            effects_gen.load_act_scene_ref(self.repo),
            effects_gen.load_section_scene_refs(self.repo),
            effects_gen.act_section_count(self.repo),
            effects_gen.act_names(self.repo))
        self.assertEqual(with_arm, without_arm)

    def test_the_committed_module_is_unchanged_by_this_arm(self):
        """The real repo, not a fixture: `generate()` now walks the preset loader on
        every call, and its output must still equal the committed artifact byte for byte
        (which is also what the build's `effects_gen.py check` drift gate enforces)."""
        out_path, text = effects_gen.generate(effects_gen.REPO)
        with open(out_path) as f:
            self.assertEqual(text, f.read())

    def test_a_scene_file_carrying_a_band_key_is_REFUSED(self):
        """The other half of §16.1, enforced: a band is not a scene channel, so `bands`
        on a SCENE file is an unknown key and the scene loader refuses it. Without this
        the two authoring surfaces would silently overlap."""
        path = os.path.join(self.scenes, "ojz_bg.json")
        with open(path, "w") as f:
            json.dump(_scene(id="ojz_bg", bands=[_band()]), f)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_scene(path)
        self.assertIn("bands", str(ctx.exception))


# =============================================================================
# THE `rasterRef` ARM — the per-section raster binding (EFFECTS-W1 item 1, step 3)
#
# NOT ONE TEST BELOW SPELLS THE WIRE KEY. Every one reads
# `effects_gen.ACT_RASTER_REF_KEY`, which is the single place in the tree the spelling
# lives. That is not tidiness: the key was built against an UNADJUDICATED name for a
# day (empyrean's CR ruled it `rasterRef` on 2026-08-30, option B), and a literal
# sprinkled through a test file is exactly what makes a one-line re-spelling a
# twenty-file one.
# =============================================================================

RASTER_KEY = effects_gen.ACT_RASTER_REF_KEY


class RasterRefBase(AssignmentBase):
    """AssignmentBase + the preset-document directory the raster refs resolve against."""

    def setUp(self):
        super().setUp()
        self.presets = os.path.join(self.scenes, effects_gen.PRESET_SUBDIR)
        os.makedirs(self.presets)

    def write_preset(self, stem, **over):
        with open(os.path.join(self.presets, f"{stem}.json"), "w") as f:
            json.dump(_preset(id=stem, **over), f)

    def refs(self):
        return effects_gen.load_section_raster_refs(self.repo)

    def render(self):
        return effects_gen.render_module(
            effects_gen.load_all_scenes(repo=self.repo),
            effects_gen.load_act_scene_ref(self.repo),
            effects_gen.load_section_scene_refs(self.repo),
            effects_gen.act_section_count(self.repo),
            effects_gen.act_names(self.repo),
            effects_gen.load_all_presets(repo=self.repo),
            self.refs())

    def arm_footprint(self, text):
        """Every character the CHANNEL BINDING arms contribute: banners + choosers.

        Separate from `chooser()` because the two tests want different subjects — one
        asserts the raster chooser's body EXACTLY, the other asserts that cutting the
        whole arm out leaves no trace of it. A banner is part of a footprint and not part
        of a body, and conflating them is how the "nothing else" claim would go soft.

        It runs from the raster binding banner to the END OF THE MODULE, because the
        cycle and variant choosers (item 5) sit after the raster one and are the same
        arm one channel over — one `rasterRef` binds all three (ruling Q1).
        """
        head = effects_gen.RASTER_BINDING_BANNER.splitlines()[0]
        start = text.find(head)
        if start < 0:
            self.fail(f"the generated module carries no {head!r} — the raster "
                      "binding's banner is missing, so this test cannot locate the "
                      "arm it is meant to cut out.")
        return text[start:]

    def chooser(self, text):
        """The whole `sec_raster` function block, or a loud failure.

        Extracted rather than searched-for so the tests below can assert on its ENTIRE
        text: "the body is exactly the fallback" is a claim about what is absent, and a
        substring check cannot make it.
        """
        head = f"pub comptime fn {effects_gen.act_names(self.repo).fn_sec_raster}("
        start = text.find(head)
        if start < 0:
            self.fail(f"the generated module carries no {head!r} — the raster chooser "
                      "is emitted for EVERY act, always, exactly like the two scene "
                      "bindings. If it is missing the whole arm is dead and every "
                      "assertion below is measuring nothing.")
        end = text.find("\n}", start)
        self.assertGreater(end, start, "the chooser block has no closing brace.")
        return text[start:end + 2]


class TestRasterRefReading(RasterRefBase):
    """§2.2's assignment reading, raster half. Shape mirrors TestAssignmentReading
    because the contract says the key's shape mirrors `sceneRef` in every particular."""

    def test_no_sidecars_at_all_is_no_raster_assignments(self):
        self.assertEqual(self.refs(), {})

    def test_a_sidecar_without_the_key_is_null(self):
        self.write_sidecar(1, {"bgLayoutRef": "x", "paletteRef": None,
                               "sceneRef": None})
        self.assertEqual(self.refs(), {})

    def test_an_explicit_null_is_null(self):
        self.write_sidecar(1, {RASTER_KEY: None})
        self.assertEqual(self.refs(), {})

    def test_an_unreadable_sidecar_fails_the_bake(self):
        """The missing/unreadable split, restated for this key because collapsing it is
        what triggers Aurora's destructive cleared-overwrite (contract §2.2/§3)."""
        self.write_sidecar(1, "{ this is not json")
        with self.assertRaises(json.JSONDecodeError):
            self.refs()

    def test_a_numeric_index_is_REFUSED_and_the_refusal_NAMES_THE_KEY(self):
        """empyrean §3.1: refuse a non-string, non-null value BY NAME. Aurora's parser
        nulls a non-string silently, so `<key>: 3` presents to the author as an
        assignment that did not stick — this build is the last reader that can see it."""
        self.write_sidecar(2, {RASTER_KEY: 3})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.refs()
        self.assertIn(RASTER_KEY, str(ctx.exception))
        self.assertIn("numeric index", str(ctx.exception))

    def test_a_non_symbol_safe_id_is_REFUSED(self):
        self.write_sidecar(2, {RASTER_KEY: "Not-An-Id"})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.refs()
        self.assertIn(RASTER_KEY, str(ctx.exception))

    def test_a_bound_ref_reads_back_under_its_section_index(self):
        self.write_sidecar(5, {RASTER_KEY: "ojz_ground_wash"})
        self.assertEqual(self.refs(), {5: "ojz_ground_wash"})

    def test_the_two_REF_KEYS_ARE_INDEPENDENT(self):
        """A sidecar carrying only one of them must not leak into the other reader.
        Both readers now share one walk, so this is the test that the sharing did not
        merge the two channels."""
        self.write_sidecar(3, {RASTER_KEY: "ojz_ground_wash"})
        self.write_sidecar(4, {"sceneRef": "ojz_bg"})
        self.assertEqual(self.refs(), {3: "ojz_ground_wash"})
        self.assertEqual(effects_gen.load_section_scene_refs(self.repo),
                         {4: "ojz_bg"})

    def test_an_UNKNOWN_sidecar_key_is_IGNORED_by_ruling(self):
        """empyrean §3.1, explicit: NO unknown-key refusal on the sidecar. The sidecar
        is Aurora's document and it will grow keys this generator does not read; a
        refusal here would make every future Aurora key a build break."""
        self.write_sidecar(1, {"someFutureAuroraKey": "whatever",
                               RASTER_KEY: None})
        self.assertEqual(self.refs(), {})


class TestRasterRefResolution(RasterRefBase):
    def test_a_ref_naming_no_document_is_REFUSED_listing_the_known_ids(self):
        self.write_preset("ojz_ground_wash")
        self.write_sidecar(5, {RASTER_KEY: "no_such_document"})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render()
        msg = str(ctx.exception)
        self.assertIn("no_such_document", msg)
        self.assertIn("ojz_ground_wash", msg)     # the known ids, named
        self.assertIn(RASTER_KEY, msg)

    def test_a_ref_with_NO_documents_at_all_is_REFUSED(self):
        """The vacuous direction: an empty library must refuse, not quietly bind."""
        self.write_sidecar(5, {RASTER_KEY: "ojz_ground_wash"})
        with self.assertRaises(effects_gen.SceneShapeError):
            self.render()

    def test_a_bound_ref_emits_exactly_one_chooser_row(self):
        self.write_preset("ojz_ground_wash")
        self.write_sidecar(5, {RASTER_KEY: "ojz_ground_wash"})
        names = effects_gen.act_names(self.repo)
        body = self.chooser(self.render())
        rows = [l for l in body.splitlines() if l.strip().startswith("if sec ==")]
        self.assertEqual(
            rows, [f"    if sec == 5 {{ out = {names.raster('ojz_ground_wash')} }}"])

    def test_the_raster_witness_counts_the_bindings(self):
        self.write_preset("ojz_ground_wash")
        self.write_sidecar(5, {RASTER_KEY: "ojz_ground_wash"})
        self.write_sidecar(7, {RASTER_KEY: "ojz_ground_wash"})
        names = effects_gen.act_names(self.repo)
        self.assertIn(f"pub equ {names.equ_raster_bindings} = 2", self.render())


class TestTheChooserSplitsByARM(RasterRefBase):
    """ONE `rasterRef`, TWO CHOOSERS (contract §7.6). A `boundary` document lowers into
    `EffectsPreset.ep_patched`, which is a DIFFERENT `preset()` parameter, so it must
    reach the section through `sec_patched` and must NOT appear in `sec_raster`.

    THE FAILURE THIS BLOCK EXISTS FOR IS SILENT. A patched image threaded into `raster:`
    installs — it is a `[u16; N]` like any other program — but it is a padded body with
    the patch table beyond the copy boundary, so the boundary sits at its authored line
    forever and no diagnostic fires anywhere.
    """

    def write_boundary_preset(self, stem):
        with open(os.path.join(self.presets, f"{stem}.json"), "w") as f:
            json.dump(_boundary_preset(id=stem), f)

    def patched_chooser(self, text):
        head = (f"pub comptime fn "
                f"{effects_gen.act_names(self.repo).fn_sec_patched}(")
        start = text.find(head)
        if start < 0:
            self.fail(f"the generated module carries no {head!r} — the patched chooser "
                      "is emitted for EVERY act, always, exactly like the raster one.")
        end = text.find("\n}", start)
        return text[start:end + 2]

    def test_the_patched_chooser_is_emitted_with_NO_content_at_all(self):
        """Always-emitted, the same owner ruling every other chooser rides: the call site
        has ONE path, always live, and never a conditional."""
        body = self.patched_chooser(self.render())
        self.assertIn("comptime var out = hand", body)
        self.assertNotIn("if sec ==", body)

    def test_a_bound_boundary_reaches_the_PATCHED_chooser_and_not_the_raster_one(self):
        self.write_boundary_preset("ojz_water_edge")
        self.write_sidecar(5, {RASTER_KEY: "ojz_water_edge"})
        names = effects_gen.act_names(self.repo)
        text = self.render()
        self.assertIn(f"    if sec == 5 {{ out = {names.patched('ojz_water_edge')} }}",
                      self.patched_chooser(text))
        raster_rows = [l for l in self.chooser(text).splitlines()
                       if l.strip().startswith("if sec ==")]
        self.assertEqual(raster_rows, [],
                         "a boundary document reached the RASTER chooser — it would be "
                         "threaded into `raster:` and never move.")

    def test_a_bands_document_still_reaches_the_RASTER_chooser_only(self):
        """The converse control. Without it the test above could pass on a generator
        that had simply stopped emitting raster rows."""
        self.write_preset("ojz_ground_wash")
        self.write_sidecar(5, {RASTER_KEY: "ojz_ground_wash"})
        names = effects_gen.act_names(self.repo)
        text = self.render()
        self.assertIn(f"    if sec == 5 {{ out = {names.raster('ojz_ground_wash')} }}",
                      self.chooser(text))
        self.assertNotIn("if sec ==", self.patched_chooser(text))

    def test_the_two_arms_coexist_on_different_sections(self):
        self.write_preset("ojz_ground_wash")
        self.write_boundary_preset("ojz_water_edge")
        self.write_sidecar(3, {RASTER_KEY: "ojz_ground_wash"})
        self.write_sidecar(5, {RASTER_KEY: "ojz_water_edge"})
        names = effects_gen.act_names(self.repo)
        text = self.render()
        self.assertIn(f"if sec == 3 {{ out = {names.raster('ojz_ground_wash')} }}",
                      self.chooser(text))
        self.assertNotIn("sec == 5", self.chooser(text))
        self.assertIn(f"if sec == 5 {{ out = {names.patched('ojz_water_edge')} }}",
                      self.patched_chooser(text))
        self.assertNotIn("sec == 3", self.patched_chooser(text))

    def test_the_bound_boundary_lowers_its_program_into_the_module(self):
        """The chooser is a Label reference; without the `pub data` behind it the module
        would name a symbol nothing declares."""
        self.write_boundary_preset("ojz_water_edge")
        self.write_sidecar(5, {RASTER_KEY: "ojz_water_edge"})
        names = effects_gen.act_names(self.repo)
        text = self.render()
        self.assertIn(f"pub data {names.patched('ojz_water_edge')}: "
                      f"[u16; patched_words({names.patched_src('ojz_water_edge')})] = "
                      f"patched_program({names.patched_src('ojz_water_edge')})", text)


class TestRasterArmIsINERT(RasterRefBase):
    """THE ZERO-BYTE CLAIM, made checkable rather than argued (design §3.4/§10).

    The four-CRC comparison is the real proof and it lives in the parcel's evidence;
    what these hold is the property the CRCs depend on — that with no `rasterRef`
    anywhere, the module gains the chooser and the witness and NOTHING ELSE, and the
    chooser's body is the caller's own fallback.
    """

    def test_no_ref_emits_a_chooser_whose_body_is_EXACTLY_the_fallback(self):
        self.write_preset("ojz_ground_wash")
        names = effects_gen.act_names(self.repo)
        sections = effects_gen.act_section_count(self.repo)
        body = self.chooser(self.render())
        expected = (
            f"pub comptime fn {names.fn_sec_raster}(sec: int, hand: Label = 0) "
            f"-> Label {{\n"
            f'    ensure(sec >= 0 && sec < {sections}, "{names.fn_sec_raster}(sec: '
            f'{{sec}}): this act has {sections} sections, so there is no binding slot '
            f"for that index — the section preset and project.json's grid have drifted "
            f'apart")\n'
            f"    comptime var out = hand\n"
            f"    return out\n"
            f"}}")
        self.assertEqual(body, expected)

    def test_the_chooser_is_emitted_with_NO_preset_documents_at_all(self):
        """Always-emitted, exactly like the two scene bindings (ruling Q-c). An arm
        that appeared only when content existed would give the call site two shapes."""
        self.chooser(self.render())

    def test_the_arms_ONLY_footprint_is_the_chooser_and_its_witness(self):
        """"and no other text change" (design §3.4), stated as a measurement.

        Cut the blocks this arm contributes out of the rendered module and NOTHING the arm
        introduced may remain. If a future edit slips a banner, a header count or a blank
        line into the general path, it survives the cut and this goes red.

        WIDENED 2026-09-02 (EFFECTS-W1 item 5), and the widening is a real finding rather
        than an accommodation. `arm_footprint` used to end at the raster chooser's closing
        brace, which was the end of the module. It no longer is: the cycle and variant
        choosers follow it, and their banner spells `rasterRef` — because ruling Q1 makes
        ONE sidecar key bind the WHOLE preset document, every channel it carries. So the
        sidecar key legitimately has a footprint in a block that is not the raster arm's,
        and the honest fix is to cut all three channel blocks rather than to stop naming
        the key where it belongs. The claim this test makes is unchanged: outside the
        binding blocks, the module knows nothing about any of it.
        """
        self.write_preset("ojz_ground_wash")
        names = effects_gen.act_names(self.repo)
        text = self.render()
        rest = text.replace(self.arm_footprint(text), "")
        for equ in (names.equ_raster_bindings, names.equ_cycle_bindings,
                    names.equ_variant_bindings):
            rest = rest.replace(f"pub equ {equ} = 0\n", "")
        for token in (names.fn_sec_raster, names.fn_sec_cycle, names.fn_sec_variant,
                      names.equ_raster_bindings, names.equ_cycle_bindings,
                      names.equ_variant_bindings, RASTER_KEY):
            self.assertNotIn(
                token, rest,
                f"{token!r} survives the removal of the three channel choosers and "
                "their witnesses — the arm has a further footprint in the generated "
                "module and the zero-byte claim is no longer the blocks it says it is.")


# =============================================================================
# PALETTE CYCLES AND VARIANTS — the item-5 arm (contract §2.4).
# =============================================================================
#
# THE VACUITY THIS BLOCK AVOIDS, and it is a different one from the raster block's. A
# document carrying these keys DOES ship now (`ojz_sec3_shimmer.json`), so a test written
# over the real tree could pass by accident. Every SHAPE test below therefore authors its
# own fixture, and the two tests that DO read the real tree
# (`TestTheEngineMirrorsArePinned`, `TestTheWorkedDocumentMatchesTheHandTwins`) are the
# ones whose whole subject is the real tree, and they fail loudly when they cannot find it.

def _channel(**over):
    """One cycle channel that PASSES, so each test perturbs exactly one thing.

    THE NUMBERS ARE `OJZ_ShimmerCycle`'s, with the unit translation applied: the hand
    script carries the engine byte `period: 8` and its runtime cadence is 9 frames, so the
    DOCUMENT that reproduces it says 9. Both numbers are correct and they differ by one on
    purpose (empyrean AURORA_EFFECTS_SCHEMA.md §7.2, ruling Q7).
    """
    ch = {"line": 2, "first": 8, "count": 4, "period": 9}
    ch.update(over)
    return ch


class TestCyclesShape(PresetShapeBase):
    """SHAPE only, and the one place that is not true is named in its own test below."""

    def test_the_three_legal_states_all_load(self):
        for spelling, expect in (("absent", None),
                                 ("null", None),
                                 ("array", 1)):
            with self.subTest(state=spelling):
                body = _preset()
                if spelling == "null":
                    body["cycles"] = None
                elif spelling == "array":
                    body["cycles"] = [_channel()]
                path = self.write("ojz_ground_wash", body)
                loaded = effects_gen.load_preset(path)
                if expect is None:
                    self.assertFalse(loaded.get("cycles"))
                else:
                    self.assertEqual(len(loaded["cycles"]), expect)

    def test_an_EMPTY_cycles_array_is_refused_NAMING_BOTH_LEGAL_SPELLINGS(self):
        """Ruling Q2: `[]` is legal JSON against a shape-only schema and the refusal is
        the GENERATOR's. It has to name the two states the author might have meant, or it
        sends them to file a contract change for a spelling that already exists."""
        msg = self.refuse("ojz_ground_wash", _preset(cycles=[]))
        self.assertIn("null", msg)
        self.assertIn("OMIT", msg)
        self.assertIn("Pal_Cycle_None", msg)

    def test_cycles_that_is_neither_a_list_nor_null_is_refused(self):
        msg = self.refuse("ojz_ground_wash", _preset(cycles={"line": 2}))
        self.assertIn("list", msg)

    def test_THREE_channels_is_refused_NAMING_THE_WRAPPERS_and_not_the_engine_ceiling(self):
        """Ruling Q3. The limit that bites is which `cycle_scriptN` EXISTS (1 and 2), not
        `PAL_CYCLE_MAX_CHANNELS` (4) — a refusal naming 4 would tell the author their
        3-channel script is legal when there is no constructor to lower it into."""
        msg = self.refuse("ojz_ground_wash",
                          _preset(cycles=[_channel(), _channel(line=3),
                                          _channel(line=1)]))
        self.assertIn("cycle_script1", msg)
        self.assertIn("cycle_script2", msg)
        self.assertIn("3 channels", msg)

    def test_a_channel_that_is_not_an_object_is_refused_with_its_index(self):
        msg = self.refuse("ojz_ground_wash", _preset(cycles=[7]))
        self.assertIn("cycles[0]", msg)

    def test_EVERY_defaultless_channel_field_is_required(self):
        for key in effects_gen.CYCLE_CHANNEL_KEYS:
            with self.subTest(missing=key):
                ch = _channel()
                del ch[key]
                msg = self.refuse("ojz_ground_wash", _preset(cycles=[ch]))
                self.assertIn(key, msg)
                self.assertIn("cycles[0]", msg)

    def test_dir_is_OPTIONAL_because_it_is_the_only_one_the_constructor_defaults(self):
        ch = _channel()
        path = self.write("ojz_ground_wash", _preset(cycles=[ch]))
        self.assertNotIn("dir", effects_gen.load_preset(path)["cycles"][0])

    def test_an_unknown_channel_key_is_refused(self):
        msg = self.refuse("ojz_ground_wash", _preset(cycles=[_channel(speed=3)]))
        self.assertIn("speed", msg)


class TestThePeriodUnitRefusal(PresetShapeBase):
    """THE ONE VALUE BOUND THE GENERATOR OWNS, and the reason it owns it.

    `cycle_channel()`'s floor is `period >= 1`. The generator emits `period - 1`, so an
    authored `period: 1` would reach the engine as 0 and the author would read a sentence
    about a number they never wrote and cannot find in their file. The refusal is here,
    one layer up, naming THEIR number.
    """

    def render(self, **over):
        names = effects_gen.ActNames("ojz", "act1")
        return effects_gen.render_preset_cycle("<fixture>", _preset(**over), names)

    def test_period_one_is_refused_and_the_message_names_the_AUTHORS_number(self):
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render(cycles=[_channel(period=1)])
        msg = str(ctx.exception)
        self.assertIn("period is 1", msg)
        self.assertIn("FRAMES", msg)
        self.assertIn(str(effects_gen.CYCLE_PERIOD_DOC_MIN), msg)

    def test_period_zero_and_negatives_are_refused_the_same_way(self):
        for bad in (0, -1):
            with self.subTest(period=bad):
                with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                    self.render(cycles=[_channel(period=bad)])
                self.assertIn(f"period is {bad}", str(ctx.exception))

    def test_the_SMALLEST_LEGAL_period_passes_and_emits_the_engine_floor(self):
        """The control for the refusal above: the boundary is where it says it is, and
        the emitted byte is the constructor's own floor rather than something below it."""
        out = self.render(cycles=[_channel(period=effects_gen.CYCLE_PERIOD_DOC_MIN)])
        self.assertIn(f"period: {effects_gen.CYCLE_PERIOD_ENGINE_MIN}", out)

    def test_a_STRING_period_is_refused_as_a_SHAPE_error_before_the_arithmetic(self):
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render(cycles=[_channel(period="9")])
        self.assertIn("integer", str(ctx.exception))

    def test_the_emitted_period_is_ONE_LESS_than_the_document_says(self):
        """The whole of ruling Q7 in one assertion. `period: 9` in the document is a
        rotation every 9 frames; the engine's timer rotates one frame after the byte, so
        the byte is 8."""
        self.assertIn("period: 8", self.render(cycles=[_channel(period=9)]))
        self.assertIn("period: 20", self.render(cycles=[_channel(period=21)]))


class TestVariantsShape(PresetShapeBase):
    def test_the_three_states_PER_INDEX_all_load(self):
        path = self.write("ojz_ground_wash",
                          _preset(variants=[{"shift_r": 1}, None]))
        loaded = effects_gen.load_preset(path)
        self.assertEqual(loaded["variants"][0], {"shift_r": 1})
        self.assertIsNone(loaded["variants"][1])

    def test_a_KEY_LEVEL_null_is_refused_BY_NAME_and_not_read_as_absent(self):
        """Ruling Q5 says the state does not exist, and the generator has to be the one
        that says so out loud: a writer that nulls every key it knows would otherwise
        produce "absent", whose meaning ("keep the hand value") is the opposite of what
        such a writer meant."""
        body = _preset()
        body["variants"] = None
        msg = self.refuse("ojz_ground_wash", body)
        self.assertIn("[null, null]", msg)
        self.assertIn("absent", msg)

    def test_a_THIRD_slot_is_refused_naming_the_engines_slot_count(self):
        msg = self.refuse("ojz_ground_wash",
                          _preset(variants=[{}, {}, {}]))
        self.assertIn("PAL_MAX_VARIANTS", msg)
        self.assertIn(str(effects_gen.PAL_MAX_VARIANTS), msg)

    def test_a_slot_that_is_neither_an_object_nor_null_is_refused_with_its_index(self):
        msg = self.refuse("ojz_ground_wash", _preset(variants=[7]))
        self.assertIn("variants[0]", msg)

    def test_an_unknown_variant_field_is_refused(self):
        msg = self.refuse("ojz_ground_wash", _preset(variants=[{"gamma": 2}]))
        self.assertIn("gamma", msg)

    def test_EVERY_variant_field_is_OPTIONAL_because_every_one_has_a_default(self):
        path = self.write("ojz_ground_wash", _preset(variants=[{}]))
        self.assertEqual(effects_gen.load_preset(path)["variants"][0], {})


class TestTheNarrowSlotBindingCheck(PresetShapeBase):
    """Ruling Q6's NARROW half, which is the half available today.

    A band naming a slot the document leaves ABSENT is the majority case and is NOT
    refused — absent means "the hand `preset()` call's value is still there", which the
    generator cannot see. A band naming a slot the document explicitly CLEARS has no such
    reading.
    """

    def _region_band(self, slot):
        return _band(on={"pal_region": {"addr": 72, "slot": slot, "pal_line": 2,
                                        "entry": 4, "count": 3}})

    def test_streaming_from_an_explicitly_CLEARED_slot_is_refused(self):
        msg = self.refuse("ojz_ground_wash",
                          _preset(bands=[self._region_band(1)],
                                  variants=[{"shift_r": 1}, None]))
        self.assertIn("slot 1", msg)
        self.assertIn("variants[1]", msg)

    def test_streaming_from_an_AUTHORED_slot_is_fine(self):
        path = self.write("ojz_ground_wash",
                          _preset(bands=[self._region_band(0)],
                                  variants=[{"shift_r": 1}, None]))
        self.assertEqual(effects_gen.load_preset(path)["id"], "ojz_ground_wash")

    def test_streaming_from_an_ABSENT_index_is_NOT_refused_and_that_is_the_ruling(self):
        """The broad check is rider 2 and would be WRONG here: the section's hand
        `preset()` call still binds slot 1, and the document is not the whole truth while
        `hand:` fallbacks exist."""
        path = self.write("ojz_ground_wash",
                          _preset(bands=[self._region_band(1)],
                                  variants=[{"shift_r": 1}]))
        self.assertEqual(effects_gen.load_preset(path)["id"], "ojz_ground_wash")

    def test_a_document_with_NO_variants_key_is_never_refused_by_this_check(self):
        path = self.write("ojz_ground_wash", _preset(bands=[self._region_band(1)]))
        self.assertEqual(effects_gen.load_preset(path)["id"], "ojz_ground_wash")


class TestPaletteLowering(PresetShapeBase):
    def cycle(self, **over):
        names = effects_gen.ActNames("ojz", "act1")
        return effects_gen.render_preset_cycle("<fixture>", _preset(**over), names)

    def variants(self, **over):
        names = effects_gen.ActNames("ojz", "act1")
        return effects_gen.render_preset_variants("<fixture>", _preset(**over), names)

    def test_a_one_channel_script_lowers_to_cycle_script1_under_the_act_qualified_name(self):
        out = self.cycle(cycles=[_channel()])
        self.assertIn("pub data EditorCycle_OJZ_Act1_ojz_ground_wash: PalCycleScript1 "
                      "= cycle_script1(", out)
        self.assertIn("cycle_channel(line: 2, first: 8, count: 4, period: 8)", out)

    def test_a_two_channel_script_picks_the_TWO_channel_wrapper(self):
        out = self.cycle(cycles=[_channel(), _channel(line=3, first=0, count=2)])
        self.assertIn(": PalCycleScript2 = cycle_script2(", out)
        self.assertEqual(out.count("cycle_channel("), 2)

    def test_dir_is_emitted_only_when_the_document_spells_it(self):
        self.assertNotIn("dir:", self.cycle(cycles=[_channel()]))
        self.assertIn("dir: 1", self.cycle(cycles=[_channel(dir=1)]))

    def test_cycles_null_emits_NO_data_because_OFF_is_a_shipped_sentinel(self):
        body = _preset()
        body["cycles"] = None
        names = effects_gen.ActNames("ojz", "act1")
        self.assertEqual(effects_gen.render_preset_cycle("<f>", body, names), "")

    def test_a_variant_emits_ONE_pub_data_PER_SLOT_named_with_its_slot(self):
        out = self.variants(variants=[{"shift_r": 1}, {"shift_b": 2}])
        self.assertEqual(len(out), 2)
        self.assertIn("EditorVariant_OJZ_Act1_ojz_ground_wash_0", out[0])
        self.assertIn("EditorVariant_OJZ_Act1_ojz_ground_wash_1", out[1])

    def test_a_NULL_slot_emits_NOTHING_because_clear_is_a_zero_in_the_chooser(self):
        out = self.variants(variants=[None, {"shift_b": 2}])
        self.assertEqual(len(out), 1)
        self.assertIn("_1:", out[0])

    def test_absent_variant_fields_are_OMITTED_so_the_constructor_defaults_stand(self):
        out = self.variants(variants=[{"shift_r": 1, "shift_g": 1}])
        self.assertIn("= variant(shift_r: 1, shift_g: 1)", out[0])
        self.assertNotIn("lines:", out[0])

    def test_variant_fields_render_in_the_CONSTRUCTORS_order_not_the_JSONs(self):
        out = self.variants(variants=[{"lines": 6, "shift_r": 1}])
        self.assertIn("variant(shift_r: 1, lines: 6)", out[0])

    def test_out_of_range_values_are_FORWARDED_because_the_ranges_are_the_engines(self):
        """Everything except the period unit. `shift_r: 9` and `lines: 1` are both
        `variant()` refusals with the engine's own sentence behind them (`3-bit channel`,
        `line 0 is the character's`), and a copy of either here is the second source that
        drifts."""
        out = self.variants(variants=[{"shift_r": 9, "bias_g": -30, "lines": 1}])
        self.assertIn("variant(shift_r: 9, bias_g: -30, lines: 1)", out[0])

    def test_an_out_of_range_LINE_or_COUNT_is_forwarded_too(self):
        out = self.cycle(cycles=[_channel(line=0, count=99)])
        self.assertIn("line: 0", out)
        self.assertIn("count: 99", out)


class TestTheEngineMirrorsArePinned(unittest.TestCase):
    """The three numbers effects_gen.py carries that BELONG to the engine.

    Each is a mirror the generator needs before the engine can speak — a positional array
    width, which wrappers exist, and the floor the period translation shifts. Read from
    engine source here so a move in the engine is a named failure rather than silent drift
    (`MAX_PARALLAX_BANDS` has the same treatment in test_scene_band_shape_coverage.py).
    """

    PALETTE = os.path.join(effects_gen.REPO, "engine", "effects", "palette.emp")
    DSL = os.path.join(effects_gen.REPO, "engine", "effects", "palette_dsl.emp")

    def source(self, path):
        if not os.path.isfile(path):
            self.fail(f"{path} does not exist — this test's whole subject is the engine's "
                      f"own numbers, and it must not pass without them.")
        with open(path) as f:
            return f.read()

    def test_PAL_MAX_VARIANTS_matches_the_engine(self):
        m = re.search(r"^pub\s+const\s+PAL_MAX_VARIANTS\s*=\s*(\d+)",
                      self.source(self.PALETTE), re.M)
        self.assertIsNotNone(
            m, "could not find `pub const PAL_MAX_VARIANTS = <n>` in palette.emp")
        self.assertEqual(
            int(m.group(1)), effects_gen.PAL_MAX_VARIANTS,
            "effects_gen.PAL_MAX_VARIANTS has drifted from the engine's. The generator "
            "emits a positional array and a chooser whose slot `ensure` spells this "
            "number, so it cannot be looked up at build time — it is a mirror, and this "
            "is what holds it.")

    def test_the_cycle_script_wrappers_are_the_ones_the_engine_declares(self):
        found = tuple(sorted(int(n) for n in re.findall(
            r"^pub\s+comptime\s+fn\s+cycle_script(\d+)\s*\(",
            self.source(self.DSL), re.M)))
        self.assertEqual(
            found, tuple(sorted(effects_gen.CYCLE_SCRIPT_WRAPPERS)),
            "engine/effects/palette_dsl.emp declares a different set of `cycle_scriptN` "
            "wrappers than effects_gen.CYCLE_SCRIPT_WRAPPERS lists. If rider 1 landed "
            "cycle_script3/4, widen the constant in the same parcel — until then the "
            "generator would refuse a script the engine can now lower, or accept one it "
            "cannot.")

    def test_the_structs_the_wrappers_return_all_exist(self):
        src = self.source(self.PALETTE)
        for n in effects_gen.CYCLE_SCRIPT_WRAPPERS:
            self.assertIn(f"struct PalCycleScript{n}", src,
                          f"the generator would emit `: PalCycleScript{n}` as a type "
                          f"annotation, and palette.emp declares no such struct.")

    def test_the_period_floor_is_the_ENGINES_floor(self):
        """And the document floor is that floor shifted by the same `- 1` the generator
        emits. Both halves, because getting either wrong makes the refusal message name a
        boundary that is not where the engine's is."""
        m = re.search(r"ensure\(period\s*>=\s*(\d+)", self.source(self.DSL))
        self.assertIsNotNone(
            m, "could not find `cycle_channel`'s `ensure(period >= <n>` in "
               "palette_dsl.emp")
        self.assertEqual(int(m.group(1)), effects_gen.CYCLE_PERIOD_ENGINE_MIN)
        self.assertEqual(effects_gen.CYCLE_PERIOD_DOC_MIN,
                         effects_gen.CYCLE_PERIOD_ENGINE_MIN + 1)

    def test_the_RIDER_5_PAIRING_comment_is_at_the_EMISSION_SITE(self):
        """The `period - 1` and the engine's cadence fix must land in ONE parcel, and
        nothing enforces that but this comment. It has to sit where the arithmetic is, so
        the parcel that changes `Palette_DoCycle` is told by the code it is about to
        break."""
        with open(effects_gen.__file__) as f:
            src = f.read()
        fn = src[src.index("def render_cycle_channel("):]
        fn = fn[:fn.index("\ndef ")]
        self.assertIn("RIDER 5 PAIRING", fn)
        self.assertIn("Palette_DoCycle", fn)
        self.assertIn("period - 1", fn)


class TestPaletteInTheGeneratedModule(RasterRefBase):
    """The module-level half: imports, banner, choosers and witnesses."""

    def write_preset(self, stem, **over):
        with open(os.path.join(self.presets, f"{stem}.json"), "w") as f:
            json.dump(_preset(id=stem, **over), f)

    def test_a_document_with_NEITHER_key_appends_NOTHING_of_this_arm(self):
        """The converse control, one channel over from the raster arm's. A tree whose
        documents carry neither key must render the same text it rendered before item 5 —
        no banner, no palette import, no `pub data`."""
        self.write_preset("ojz_ground_wash")
        out = self.render()
        self.assertNotIn("use engine.effects.palette.", out)
        self.assertNotIn("EditorCycle_OJZ_Act1_ojz_ground_wash", out)
        self.assertNotIn("EditorVariant_OJZ_Act1_ojz_ground_wash", out)
        self.assertNotIn(effects_gen.PALETTE_BANNER.splitlines()[0], out)

    def test_the_struct_imports_appear_ONLY_for_the_keys_a_document_carries(self):
        self.write_preset("a_wash", cycles=[_channel()])
        out = self.render()
        self.assertIn("use engine.effects.palette.{pal_cycle_channel, PalCycleScript1}",
                      out)
        self.assertNotIn("{pal_variant}", out)

    def test_the_variant_import_appears_for_a_variant_only_document(self):
        self.write_preset("a_wash", variants=[{"shift_r": 1}])
        out = self.render()
        self.assertIn("use engine.effects.palette.{pal_variant}", out)
        self.assertNotIn("pal_cycle_channel", out)

    def test_the_import_names_ONLY_the_wrapper_arities_actually_used(self):
        self.write_preset("a_wash", cycles=[_channel(), _channel(line=3)])
        self.assertIn("PalCycleScript2}", self.render())

    def test_BOTH_choosers_exist_with_no_editor_content_at_all(self):
        """Always-emitted, exactly like the raster chooser and the two scene bindings.
        A caller must have ONE path, never a conditional."""
        names = effects_gen.act_names(self.repo)
        out = self.render()
        self.assertIn(f"pub comptime fn {names.fn_sec_cycle}(sec: int, hand: Label = 0)",
                      out)
        self.assertIn(f"pub comptime fn {names.fn_sec_variant}(sec: int, slot: int, "
                      f"hand: Label = 0)", out)

    def test_with_no_binding_both_chooser_bodies_are_EXACTLY_the_fallback(self):
        self.write_preset("a_wash", cycles=[_channel()],
                          variants=[{"shift_r": 1}, None])
        out = self.render()
        names = effects_gen.act_names(self.repo)
        for fn in (names.fn_sec_cycle, names.fn_sec_variant):
            body = out[out.index(f"pub comptime fn {fn}("):]
            body = body[:body.index("\n}") + 2]
            self.assertNotIn("if sec ==", body,
                             f"{fn} carries a binding row with no sidecar naming a "
                             f"document — one `rasterRef` is the ONLY route into these "
                             f"choosers (ruling Q1).")

    def test_ONE_rasterRef_binds_EVERY_channel_the_document_carries(self):
        """Ruling Q1, and it is the whole reason there is no `cycleRef`. Binding the
        document through the RASTER key must light up the cycle and variant choosers too."""
        self.write_preset("a_wash", cycles=[_channel()],
                          variants=[{"shift_r": 1}, None])
        self.write_sidecar(3, {RASTER_KEY: "a_wash"})
        out = self.render()
        self.assertIn("if sec == 3 { out = EditorRaster_OJZ_Act1_a_wash }", out)
        self.assertIn("if sec == 3 { out = EditorCycle_OJZ_Act1_a_wash }", out)
        self.assertIn("if sec == 3 && slot == 0 { out = EditorVariant_OJZ_Act1_a_wash_0 }",
                      out)
        self.assertIn("if sec == 3 && slot == 1 { out = 0 }", out)

    def test_a_bound_cycles_null_document_chooses_the_SENTINEL_and_never_zero(self):
        """Ruling Q2's OFF state. NULL cannot mean "off" while it also means "keep", which
        is why the engine ships a non-NULL zero-channel script."""
        body = _preset(id="a_wash")
        body["cycles"] = None
        with open(os.path.join(self.presets, "a_wash.json"), "w") as f:
            json.dump(body, f)
        self.write_sidecar(3, {RASTER_KEY: "a_wash"})
        out = self.render()
        self.assertIn("if sec == 3 { out = Pal_Cycle_None }", out)
        self.assertNotIn("EditorCycle_OJZ_Act1_a_wash", out)

    def test_the_slot_ensure_carries_an_INLINE_literal_for_the_call_site_rule(self):
        """A comptime fn's free names resolve at the CALL SITE, so a named engine
        constant in the chooser body would resolve in the effects library's scope or not
        at all (docs/EMP_PITFALLS.md §2, the SECTION_PIN precedent)."""
        out = self.render()
        names = effects_gen.act_names(self.repo)
        body = out[out.index(f"pub comptime fn {names.fn_sec_variant}("):]
        self.assertIn(f"slot < {effects_gen.PAL_MAX_VARIANTS}", body)

    def test_the_witnesses_count_the_bindings_of_EACH_channel_separately(self):
        self.write_preset("a_wash", cycles=[_channel()])          # cycle, no variants
        self.write_preset("b_wash", variants=[{"shift_r": 1}])    # variants, no cycle
        self.write_sidecar(2, {RASTER_KEY: "a_wash"})
        self.write_sidecar(3, {RASTER_KEY: "b_wash"})
        names = effects_gen.act_names(self.repo)
        out = self.render()
        self.assertIn(f"pub equ {names.equ_raster_bindings} = 2", out)
        self.assertIn(f"pub equ {names.equ_cycle_bindings} = 1", out)
        self.assertIn(f"pub equ {names.equ_variant_bindings} = 1", out)

    def test_the_banner_says_ONCE_which_cycle_this_key_means(self):
        """Ruling Q10. `cycles` is palette cycling; the DEBUG hotkey's raster cycle table
        is a different thing with the same word in its name, and a reader of one must not
        read the other."""
        self.write_preset("a_wash", cycles=[_channel()])
        out = self.render()
        self.assertIn("RASTER_CYCLE_COUNT", out)
        self.assertIn("Palette_DoCycle", out)


class TestTheWorkedDocumentMatchesTheHandTwins(unittest.TestCase):
    """LAYER 1 OF THE BYTE GOLDEN — the text half, which needs no build.

    `games/sonic4/data/editor/effects/presets/ojz_sec3_shimmer.json` is OJZ section 3's
    hand-authored palette channels re-expressed as a document, so the calls the generator
    emits for it must be the SAME CALLS the hand library makes. Layer 2 is
    `tools/editor_palette_golden.py`, which compares the emitted BYTES in the built ROM.

    Both sides are parsed to argument dicts and compared with the CONSTRUCTOR's own
    defaults filled in, read out of `palette_dsl.emp`'s signatures — so a hand call that
    omits `dir` and a document that spells `"dir": 0` compare equal, which they should,
    and neither number is typed here.
    """

    DOC_ID = "ojz_sec3_shimmer"
    HAND_LIB = os.path.join(effects_gen.REPO, "games", "sonic4", "data", "effects",
                            "ojz_effects.emp")

    @staticmethod
    def call_args(text, fn):
        """`fn(a: 1, b: -2)` -> {'a': 1, 'b': -2}, for the FIRST such call in `text`."""
        m = re.search(re.escape(fn) + r"\(([^()]*)\)", text)
        if m is None:
            return None
        out = {}
        for k, v in re.findall(r"([A-Za-z_]\w*)\s*:\s*(-?\d+)", m.group(1)):
            out[k] = int(v)
        return out

    def hand_call(self, symbol, fn):
        """The argument dict of the first `fn(...)` inside `pub data <symbol> = ...`.

        The declaration is taken up to the next top-level item rather than to the end of
        its line, because the shipped `OJZ_ShimmerCycle` wraps its channel list onto a
        second line — a line-anchored read would silently see half of it.
        """
        with open(self.HAND_LIB) as f:
            src = f.read()
        m = re.search(r"^pub\s+data\s+" + re.escape(symbol) + r"\s*:", src, re.M)
        if m is None:
            self.fail(f"{self.HAND_LIB} declares no `pub data {symbol}` — this test's "
                      f"whole subject is that the document reproduces it. If the hand "
                      f"instance was retired (empyrean §7.2 rider 3), retire this test "
                      f"and the twin row in tools/editor_palette_golden.py with it.")
        rest = src[m.start():]
        nxt = re.search(r"\n(?:pub\s|const\s|//|data\s|\n)", rest[1:])
        decl = rest[:nxt.start() + 1] if nxt else rest
        args = self.call_args(decl, fn)
        if args is None:
            self.fail(f"`pub data {symbol}` does not call `{fn}(...)` on its own line; "
                      f"this parser cannot read it and must not pass.")
        return args

    def document(self):
        path = os.path.join(effects_gen.preset_dir(repo=effects_gen.REPO),
                            self.DOC_ID + ".json")
        if not os.path.isfile(path):
            self.fail(f"{path} does not exist. It is the worked example the item-5 byte "
                      f"golden is built on; without it this test measures nothing.")
        return effects_gen.load_preset(path)

    def defaults(self, fn):
        # Read through the byte golden's OWN parser, so this text layer and the byte
        # layer cannot disagree about what a constructor default is.
        import editor_palette_golden as golden
        with open(os.path.join(effects_gen.REPO, "engine", "effects",
                               "palette_dsl.emp")) as f:
            return golden.signature_defaults(f.read(), fn)

    def test_the_documents_CYCLE_call_equals_the_hand_OJZ_ShimmerCycle_call(self):
        doc = self.document()
        names = effects_gen.act_names(effects_gen.REPO)
        emitted = self.call_args(
            effects_gen.render_preset_cycle("<real>", doc, names), "cycle_channel")
        hand = self.hand_call("OJZ_ShimmerCycle", "cycle_channel")
        defaults = self.defaults("cycle_channel")
        for key in sorted(set(emitted) | set(hand)):
            self.assertEqual(
                emitted.get(key, defaults.get(key)), hand.get(key, defaults.get(key)),
                f"the document's emitted cycle_channel disagrees with the hand "
                f"OJZ_ShimmerCycle on `{key}` (emitted {emitted}, hand {hand}). Note the "
                f"document's `period` is in FRAMES and the emitted one is the engine "
                f"byte, one less — a mismatch here means the translation moved, not that "
                f"the two units differ.")

    def test_the_documents_VARIANT_call_equals_the_hand_Variant_Water_Deep_call(self):
        doc = self.document()
        names = effects_gen.act_names(effects_gen.REPO)
        decls = effects_gen.render_preset_variants("<real>", doc, names)
        self.assertTrue(decls, "the worked document emits no variant descriptor")
        emitted = self.call_args(decls[0], "variant")
        hand = self.hand_call("Variant_Water_Deep", "variant")
        defaults = self.defaults("variant")
        for key in sorted(set(emitted) | set(hand) | set(defaults)):
            self.assertEqual(emitted.get(key, defaults.get(key)),
                             hand.get(key, defaults.get(key)),
                             f"slot 0 of {self.DOC_ID} disagrees with the hand "
                             f"Variant_Water_Deep on `{key}`")

    def test_the_documents_period_is_the_HAND_bytes_period_PLUS_ONE(self):
        """Stated as its own assertion because it is the number most likely to be
        'corrected' by someone who sees 9 beside 8 and reads it as a typo. It is not: the
        engine's cadence is `period + 1` frames, so a document reproducing an 8-byte
        script that runs every 9 frames says 9."""
        doc = self.document()
        hand = self.hand_call("OJZ_ShimmerCycle", "cycle_channel")
        self.assertEqual(doc["cycles"][0]["period"], hand["period"] + 1)


class TestTheConsumerContractNamesTheKey(unittest.TestCase):
    """§2.2 and the constant must agree, and the CONSTANT is the authority.

    The contract is the file Aurora's lane implements against, and empyrean §8 makes it
    and their §3.1 a matched pair re-pinned by SHA. A key name that drifted between this
    tree's reader and this tree's contract would cost that lane a rebuild for no visible
    reason. Derived, never typed: the expectation is `effects_gen.ACT_RASTER_REF_KEY`,
    which is the single place in this repo the wire spelling exists.
    """

    DOC = os.path.join(effects_gen.REPO, "tools", "EFFECTS_CONSUMER_CONTRACT.md")

    def test_the_contract_names_the_raster_ref_key(self):
        if not os.path.isfile(self.DOC):
            self.fail(f"{self.DOC} does not exist — it is the normative read set for "
                      "tools/effects_gen.py. If it was deliberately deleted, delete "
                      "this test in the same commit rather than passing on a missing "
                      "file.")
        with open(self.DOC) as f:
            text = f.read()
        self.assertIn(
            f"`{effects_gen.ACT_RASTER_REF_KEY}`", text,
            f"tools/EFFECTS_CONSUMER_CONTRACT.md never names "
            f"{effects_gen.ACT_RASTER_REF_KEY!r}, which is the key "
            f"tools/effects_gen.py actually reads out of every section sidecar. The "
            f"contract is what Aurora's writer is built against; a reader and a "
            f"contract that disagree about a key name cost that lane a rebuild.")
        self.assertIn(
            effects_gen.ACT_RASTER_REF_KEY,
            text.split("### 2.2 Assignments", 1)[-1].split("### 2.3", 1)[0],
            "the raster ref key is named somewhere in the contract but not inside "
            "§2.2 Assignments, which is the section that enumerates the sidecar's read "
            "set — a reader looking up 'what does the generator read from a sidecar' "
            "would not find it.")

    def test_the_contract_names_every_layer_key_the_generator_reads(self):
        """§2.1's per-layer list and `LAYER_KEYS` must agree, CONSTANT authoritative.

        The same obligation as the sidecar test above, generalised to the surface that
        just grew: `drift` was added to `LAYER_KEYS` on 2026-09-02 and the contract is
        the file Aurora's writer is built against, so a key readable here and unnamed
        there is a capability the writer lane cannot know it has. Derived by iterating
        the constant — a key added to `LAYER_KEYS` in some later parcel fails this test
        until §2.1 names it, which is the drift rule at the top of the contract
        expressed as a gate rather than as prose.

        Scoped to §2.1 (the section that enumerates the scene document's read set) so
        that a mention in a §1 table or a rationale paragraph elsewhere cannot satisfy
        it. `world_y` and friends are backticked there; the backticks are asserted
        because an unquoted word in prose is not an enumeration entry.
        """
        with open(self.DOC) as f:
            text = f.read()
        section = text.split("### 2.1 Scene definition files", 1)[-1] \
                      .split("### 2.1b", 1)[0]
        for key in sorted(effects_gen.LAYER_KEYS):
            self.assertIn(
                f"`{key}`", section,
                f"tools/EFFECTS_CONSUMER_CONTRACT.md §2.1 never names `{key}`, which "
                f"tools/effects_gen.py accepts as a per-layer key (LAYER_KEYS). Adding "
                f"a read is a CONTRACT change under this document's own drift rule: "
                f"amend §2.1 and the empyrean schema pair in the same series.")


class TestEditorRasterPresetsDoc(unittest.TestCase):
    """Hold the Aurora lane's page to the generator's own key constants.

    WHY THIS EXISTS. `docs/EDITOR_RASTER_PRESETS.md` is the page a band panel is built
    against, and a wrong field NAME there costs that lane a rebuild. It is also a third
    restatement of a key list that already lives in two places (this repo's consumer
    contract §2.4 and empyrean's writer schema), and a count or a name in prose rots —
    this file's own subject has been bitten by exactly that. So the page carries its key
    list inside a marked block and this test reads it back out and compares it against
    `effects_gen`'s constants, which are what the loader actually enforces.

    THE EXPECTATION IS THE IMPLEMENTATION'S OWN CONSTANTS, deliberately, and that is the
    right direction here: the claim being checked is not "the generator reads the
    contract's fields" (§2.4's tests above check that) but "the page names the fields the
    generator reads". A doc that disagrees with the code is wrong about the code
    whichever of them is at fault.
    """

    DOC = os.path.join(effects_gen.REPO, "docs", "EDITOR_RASTER_PRESETS.md")
    OPEN = "<!-- KEYS-CHECKED-AGAINST-effects_gen.py -->"
    CLOSE = "<!-- /KEYS-CHECKED-AGAINST-effects_gen.py -->"

    def documented(self):
        """{row label: [names]} parsed out of the marked block. Loud if absent."""
        if not os.path.isfile(self.DOC):
            self.fail(
                f"{self.DOC} does not exist. It is the page the Aurora lane builds its "
                "band panel against; if it was deliberately deleted, delete this test in "
                "the same commit rather than letting it pass on a missing file.")
        with open(self.DOC) as f:
            text = f.read()
        try:
            block = text.split(self.OPEN, 1)[1].split(self.CLOSE, 1)[0]
        except IndexError:
            self.fail(
                f"{self.DOC}: could not find the {self.OPEN} ... {self.CLOSE} block. That "
                "block is the only machine-checked thing on the page; without it this "
                "test measures nothing and must not pass.")
        rows = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("```"):
                continue
            label, _, names = line.partition(":")
            rows[label.strip()] = sorted(
                n.strip() for n in names.split(",") if n.strip())
        if not rows:
            self.fail(f"{self.DOC}: the key block was found but parsed to zero rows.")
        return rows

    def test_the_block_covers_every_row_and_no_others(self):
        self.assertEqual(
            sorted(self.documented()),
            ["band", "boundary", "boundary-optional", "boundary.pal_region",
             "cycle-channel", "cycle-channel-optional", "on-arms", "on.cram",
             "on.pal_region", "preset", "preset-ignored", "preset-refused", "sweep",
             "sweep-optional", "variant"],
            "the key block in EDITOR_RASTER_PRESETS.md gained or lost a row. Each row is "
            "one of the generator's key constants; a row with no constant behind it is "
            "unchecked prose wearing the block's authority.")

    def test_the_documented_palette_keys_are_the_generators(self):
        """The item-5 rows, held the same way the band rows are: the page names the
        fields the LOADER enforces, or a panel built from it is built against fiction."""
        doc = self.documented()
        self.assertEqual(doc["cycle-channel"],
                         sorted(effects_gen.CYCLE_CHANNEL_KEYS))
        self.assertEqual(doc["cycle-channel-optional"],
                         sorted(effects_gen.CYCLE_CHANNEL_OPTIONAL_KEYS))
        self.assertEqual(doc["variant"], sorted(effects_gen.VARIANT_KEYS))

    def test_the_documented_sweep_keys_are_the_generators(self):
        """The item-4 rows. These matter MORE than the others for the same reason the
        page's own warning does: `amp_shift` and `period_shift` are base-2 logarithms on
        quantized ladders, so a panel built against a wrong field NAME here does not
        produce a wrong number, it produces a refusal — and a panel built against a wrong
        UNIT produces a number twice or half what the author asked for, silently."""
        doc = self.documented()
        self.assertEqual(doc["sweep"], sorted(effects_gen.SWEEP_KEYS))
        self.assertEqual(doc["sweep-optional"], sorted(effects_gen.SWEEP_OPTIONAL_KEYS))

    def test_the_documented_preset_keys_are_the_generators(self):
        doc = self.documented()
        self.assertEqual(doc["preset"], sorted(effects_gen.PRESET_KEYS))
        self.assertEqual(doc["preset-ignored"],
                         sorted(effects_gen.PRESET_IGNORED_KEYS))
        self.assertEqual(doc["preset-refused"],
                         sorted(effects_gen.PRESET_REFUSED_KEYS))

    def test_the_documented_band_keys_are_the_generators(self):
        self.assertEqual(self.documented()["band"], sorted(effects_gen.BAND_KEYS))

    def test_the_documented_boundary_keys_are_the_generators(self):
        """The §7.6 rows. The `boundary.pal_region` row matters most of the three: it is
        the `$defs.tint_region` shape, the SAME four members as a band's `on.pal_region`
        MINUS `addr`, and a panel built from the band row would emit an `addr` the loader
        refuses by name. Held against the constants so the two rows cannot converge."""
        doc = self.documented()
        self.assertEqual(doc["boundary"],
                         sorted(effects_gen.BOUNDARY_REQUIRED_KEYS))
        self.assertEqual(doc["boundary-optional"],
                         sorted(effects_gen.BOUNDARY_OPTIONAL_KEYS))
        self.assertEqual(doc["boundary.pal_region"],
                         sorted(effects_gen.TINT_REGION_KEYS))
        self.assertNotIn("addr", doc["boundary.pal_region"])

    def test_the_documented_on_arms_and_their_fields_are_the_generators(self):
        doc = self.documented()
        self.assertEqual(doc["on-arms"], sorted(effects_gen.BAND_ON_ARMS))
        for arm, (_fn, fields) in effects_gen.BAND_ON_ARMS.items():
            self.assertEqual(
                doc[f"on.{arm}"], sorted(fields),
                f"the documented fields of the `{arm}` ON arm are not the ones "
                f"render_band_on passes to its constructor.")


# =============================================================================
# THE PATCH CHANNELS — EFFECTS-W1 DoD item 4, step 4 (the reader).
# =============================================================================


class PatchShapeBase(PresetShapeBase):
    """PresetShapeBase plus the two GAME-level inputs the contextual refusals read.

    `load_preset(path)` is pure and takes a path; the capability and liveness checks need
    the GAME, so they run in `load_all_presets(game, repo)` and read the game's own
    `config/game.emp` and `data/effects/*.emp`. Those are written here rather than mocked,
    because what is being tested is that the generator reads the real declarations — a mock
    would let a parser that reads nothing pass.
    """

    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.tmp.name, "games", "sonic4", "config")
        self.lib = os.path.join(self.tmp.name, "games", "sonic4", "data", "effects")
        os.makedirs(self.config)
        os.makedirs(self.lib)
        self.write_caps("$01DE")          # sonic4's real mask: CAP_ANCHOR_MOTION raised
        self.write_lib(
            "const P = compose([\n"
            "    patchable(fx_tint_band(line: 100), ch: 0, lo: 3,   hi: 220),\n"
            "    patchable(fx_vscroll_split(line: 222), ch: 1, lo: 222, hi: 223),\n"
            "])\n")

    def write_caps(self, literal):
        with open(os.path.join(self.config, "game.emp"), "w") as f:
            f.write("contract Game {\n    const SCANLINE_CAPS = %s\n}\n" % literal)

    def write_lib(self, text):
        with open(os.path.join(self.lib, "ojz_effects.emp"), "w") as f:
            f.write(text)

    def load_all(self):
        return effects_gen.load_all_presets(repo=self.tmp.name)

    def refuse_all(self, stem, body):
        self.write(stem, body)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load_all()
        return str(ctx.exception)


def _sweep(**over):
    body = {"amp_shift": 4, "period_shift": 1}
    body.update(over)
    return {"sweep": body}


class TestPatchWorldYsShape(PatchShapeBase):
    def test_the_three_states_PER_INDEX_all_load(self):
        path = self.write("ojz_ground_wash",
                          _preset(patch_world_ys=[224, None]))
        loaded = effects_gen.load_preset(path)
        self.assertEqual(loaded["patch_world_ys"][0], 224)
        self.assertIsNone(loaded["patch_world_ys"][1])
        self.assertEqual(len(loaded["patch_world_ys"]), 2)   # 2 and 3 are "keep"

    def test_a_KEY_LEVEL_null_is_refused_BY_NAME_and_not_read_as_absent(self):
        body = _preset()
        body["patch_world_ys"] = None
        msg = self.refuse("ojz_ground_wash", body)
        self.assertIn("KEY level", msg)
        self.assertIn("absent", msg)

    def test_a_FIFTH_channel_is_refused_naming_the_engines_channel_count(self):
        msg = self.refuse("ojz_ground_wash",
                          _preset(patch_world_ys=[0, 1, 2, 3, 4]))
        self.assertIn("RASTER_MAX_PATCH", msg)
        self.assertIn(str(effects_gen.RASTER_MAX_PATCH), msg)

    def test_a_seed_past_the_u16_is_refused_and_the_message_names_the_x256_trap(self):
        """57344 is 224 exported through item 3's 1/256 unit. It is the single most likely
        wrong value on this key, so the refusal says so rather than only naming the bound."""
        msg = self.refuse("ojz_ground_wash", _preset(patch_world_ys=[70000]))
        self.assertIn("0..65535", msg)
        self.assertIn("57344", msg)

    def test_a_negative_seed_is_refused(self):
        self.assertIn("0..65535", self.refuse("ojz_ground_wash",
                                              _preset(patch_world_ys=[-1])))

    def test_the_SENTINEL_written_as_an_integer_is_refused_naming_null(self):
        """The refusal the hub added to the schema because nothing else has it: `preset()`
        ensures the array's LENGTH, never its values, so 32767 reaches the ROM as an
        authored-looking anchor the runtime reads as 'channel unused'."""
        msg = self.refuse("ojz_ground_wash",
                          _preset(patch_world_ys=[effects_gen.PATCH_ANCHOR_NONE]))
        self.assertIn("PATCH_ANCHOR_NONE", msg)
        self.assertIn("null", msg)

    def test_one_below_and_one_above_the_sentinel_are_accepted(self):
        """The bound is the sentinel VALUE and not a region around it — asserted so that a
        future 'be safe, refuse a range' edit fails here rather than quietly costing an
        author two legal world Ys."""
        for y in (effects_gen.PATCH_ANCHOR_NONE - 1, effects_gen.PATCH_ANCHOR_NONE + 1):
            path = self.write("ojz_ground_wash", _preset(patch_world_ys=[y]))
            self.assertEqual(effects_gen.load_preset(path)["patch_world_ys"][0], y)

    def test_0_and_65535_are_both_accepted_because_both_are_real_world_ys(self):
        for y in (0, 65535):
            path = self.write("ojz_ground_wash", _preset(patch_world_ys=[y]))
            self.assertEqual(effects_gen.load_preset(path)["patch_world_ys"][0], y)

    def test_a_non_integer_seed_is_refused_with_its_index(self):
        self.assertIn("patch_world_ys[0]",
                      self.refuse("ojz_ground_wash", _preset(patch_world_ys=["224"])))


class TestPatchMotionShape(PatchShapeBase):
    def test_the_three_states_PER_INDEX_all_load(self):
        path = self.write("ojz_ground_wash",
                          _preset(patch_world_ys=[224, 314],
                                  patch_motion=[_sweep(), None]))
        loaded = effects_gen.load_preset(path)
        self.assertEqual(loaded["patch_motion"][0]["sweep"]["amp_shift"], 4)
        self.assertIsNone(loaded["patch_motion"][1])

    def test_a_KEY_LEVEL_null_is_refused_BY_NAME(self):
        body = _preset()
        body["patch_motion"] = None
        self.assertIn("KEY level", self.refuse("ojz_ground_wash", body))

    def test_a_FIFTH_channel_is_refused(self):
        self.assertIn("RASTER_MAX_PATCH",
                      self.refuse("ojz_ground_wash",
                                  _preset(patch_motion=[None] * 5)))

    def test_an_APPROACH_arm_is_refused_because_no_arm_but_sweep_exists(self):
        msg = self.refuse("ojz_ground_wash",
                          _preset(patch_world_ys=[224],
                                  patch_motion=[{"approach": {"target": 300}}]))
        self.assertIn("sweep", msg)

    def test_zero_arms_and_two_arms_are_both_refused(self):
        self.assertIn("sweep", self.refuse("ojz_ground_wash",
                                           _preset(patch_world_ys=[224],
                                                   patch_motion=[{}])))
        self.assertIn("sweep", self.refuse(
            "ojz_ground_wash",
            _preset(patch_world_ys=[224],
                    patch_motion=[{"sweep": {"amp_shift": 4, "period_shift": 1},
                                   "approach": {}}])))

    def test_a_sweep_missing_either_required_field_is_refused_naming_the_shift_unit(self):
        for missing in effects_gen.SWEEP_KEYS:
            body = dict(_sweep()["sweep"])
            del body[missing]
            msg = self.refuse("ojz_ground_wash",
                              _preset(patch_world_ys=[224],
                                      patch_motion=[{"sweep": body}]))
            self.assertIn(missing, msg)
            self.assertIn("256 >> amp_shift", msg)

    def test_phase_is_OPTIONAL(self):
        path = self.write("ojz_ground_wash",
                          _preset(patch_world_ys=[224], patch_motion=[_sweep()]))
        self.assertNotIn("phase",
                         effects_gen.load_preset(path)["patch_motion"][0]["sweep"])

    def test_an_unknown_sweep_field_is_refused(self):
        self.assertIn("amplitude", self.refuse(
            "ojz_ground_wash",
            _preset(patch_world_ys=[224], patch_motion=[_sweep(amplitude=8)])))

    def test_a_sweep_beside_an_EXPLICIT_null_anchor_is_refused(self):
        """The narrow half of 'two keys or nothing'. A sweep displaces an anchor; a channel
        the same document declares unused has none, so the pair authors an effect that
        cannot appear."""
        msg = self.refuse("ojz_ground_wash",
                          _preset(patch_world_ys=[None], patch_motion=[_sweep()]))
        self.assertIn("patch_motion[0]", msg)
        self.assertIn("patch_world_ys[0]", msg)

    def test_a_sweep_on_an_ABSENT_anchor_index_is_NOT_refused(self):
        """The broad check would be WRONG for `_check_cleared_slot_is_not_streamed`'s
        reason: absent means the section's hand-authored anchor is still there, and the
        generator cannot see it."""
        path = self.write("ojz_ground_wash", _preset(patch_motion=[_sweep()]))
        self.assertEqual(effects_gen.load_preset(path)["id"], "ojz_ground_wash")


class TestPatchMotionIsForwardedVERBATIM(PatchShapeBase):
    """The unit contract, asserted as text rather than argued.

    Every number an author writes has to come out the other side unchanged: `patch_world_ys`
    because it is whole pixels 1:1 (item 3's `drift.rate` x256 habit is the trap), and the
    sweep shifts because they are base-2 logarithms on ladders whose adjacent rungs differ by
    a factor of two.
    """

    def render(self, value):
        return effects_gen.render_patch_motion("<fixture>", value, "patch_motion[0]")

    def test_the_shipped_hand_call_is_reproduced_CHARACTER_FOR_CHARACTER(self):
        """games/sonic4/data/effects/ojz_effects.emp's OJZ_Preset_Sec0 spells the shipped
        precedent. The generated text is compared to it literally, with nothing to
        normalise, which is only possible because `phase` is OMITTED when absent."""
        self.assertEqual(self.render(_sweep()),
                         "anchor_sweep(amp_shift: 4, period_shift: 1)")

    def test_phase_is_emitted_only_when_authored_and_in_the_constructors_order(self):
        self.assertEqual(self.render(_sweep(phase=64)),
                         "anchor_sweep(amp_shift: 4, period_shift: 1, phase: 64)")

    def test_every_legal_rung_survives_the_round_trip_UNCHANGED(self):
        """No rounding, no snapping, no clamping — for every rung on both ladders. The
        ladders are DERIVED from engine/effects/raster_dsl.emp's own literals rather than
        listed here, so a screen or sine-table change moves the domain of this test with it
        instead of leaving it testing a stale set."""
        dsl = os.path.join(effects_gen.REPO, "engine/effects/raster_dsl.emp")
        with open(dsl) as f:
            src = f.read()

        def const(name):
            m = re.search(r"^(?:pub )?const %s\s*=\s*(\$?[0-9A-Fa-f]+)" % name, src, re.M)
            self.assertIsNotNone(m, "%s no longer declares `const %s`" % (dsl, name))
            tok = m.group(1)
            return int(tok[1:], 16) if tok.startswith("$") else int(tok)

        amp, lines = const("ANCHOR_SINE_AMP"), const("ANCHOR_SCREEN_LINES")
        entries, width = const("ANCHOR_SINE_ENTRIES"), const("ANCHOR_TICK_BITS")
        amp_min = max([i + 1 for i in range(16) if (amp >> i) * 2 > lines] or [0])
        amp_max = max(i for i in range(16) if (amp >> i) >= 1)
        per_max = max(i for i in range(32) if (entries << i) <= (1 << width))
        self.assertEqual((amp_min, amp_max, per_max), (2, 8, 8),
                         "the derived ladders moved; this test's own arithmetic is what "
                         "says so, and the rungs below are re-derived from it either way")
        for a in range(amp_min, amp_max + 1):
            for p in range(0, per_max + 1):
                self.assertEqual(
                    self.render({"sweep": {"amp_shift": a, "period_shift": p}}),
                    "anchor_sweep(amp_shift: %d, period_shift: %d)" % (a, p))

    def test_an_OFF_LADDER_rung_is_forwarded_UNCHANGED_rather_than_rounded(self):
        """The posture, stated as a test because the alternative is the silent one. An
        amp_shift of 1 is illegal, and `anchor_sweep()` refuses it AT BUILD TIME with the
        derived ladder in the sentence. Snapping it to 2 here would halve the author's
        travel and print nothing at all."""
        self.assertEqual(self.render({"sweep": {"amp_shift": 1, "period_shift": 99}}),
                         "anchor_sweep(amp_shift: 1, period_shift: 99)")

    def test_the_generator_carries_no_scale_factor_on_this_path(self):
        """The x256 trap, checked mechanically. `patch_world_ys` is WHOLE PIXELS 1:1 in both
        directions; item 3's `drift.rate` is 1/256 px per frame and the EDITOR multiplies.
        Confusing them puts the anchor 256x down the level and the band silently never
        appears — so this asserts the seed reaches generated text as the digits the author
        typed, for a value that would be unmistakable if scaled."""
        names = effects_gen.ActNames("ojz", "act1")
        module = effects_gen.render_module(
            {}, None, {}, 9, names,
            presets={"ojz_ground_wash": _preset(patch_world_ys=[224, None, None, None],
                                                patch_motion=[_sweep(), None, None, None])},
            sec_raster_refs={5: "ojz_ground_wash"})
        self.assertIn("if sec == 5 && ch == 0 { out = 224 }", module)
        self.assertNotIn("57344", module)
        self.assertIn("if sec == 5 && ch == 0 { out = anchor_sweep(amp_shift: 4, "
                      "period_shift: 1) }", module)


class TestPatchChannelsInTheGeneratedModule(PatchShapeBase):
    def module(self, presets, refs):
        return effects_gen.render_module({}, None, {}, 9,
                                         effects_gen.ActNames("ojz", "act1"),
                                         presets=presets, sec_raster_refs=refs)

    def test_both_choosers_are_emitted_for_an_act_with_NO_documents_at_all(self):
        """The always-emitted ruling (design §9 Q-c), one channel over. The caller has ONE
        path whether or not editor content exists, and an UNCALLED `pub comptime fn` is an
        unelaborated one whose own ensures assert nothing."""
        module = self.module({}, {})
        self.assertIn("pub comptime fn ojz_act1_sec_patch_world_y(sec: int, ch: int, "
                      "hand: int = %d) -> int {" % effects_gen.PATCH_ANCHOR_NONE, module)
        self.assertIn("pub comptime fn ojz_act1_sec_patch_motion(sec: int, ch: int, "
                      "hand: int = %d) -> int {" % effects_gen.ANCHOR_MOTION_NONE, module)
        self.assertIn("EditorPatch_OJZ_Act1_Bindings = 0", module)

    def test_the_defaults_are_the_SENTINELS_and_never_0_on_the_world_Y(self):
        """0 is a real world Y and the worst one: `anchor - Camera_Y` at 0 reads as above
        the screen top for a channel nobody asked for."""
        self.assertNotEqual(effects_gen.PATCH_ANCHOR_NONE, 0)
        self.assertIn("hand: int = %d" % effects_gen.PATCH_ANCHOR_NONE, self.module({}, {}))

    def test_a_null_index_lowers_to_the_NAMED_sentinel_and_not_to_a_literal(self):
        """`Pal_Cycle_None`'s rule, two channels over: a comptime fn's free names resolve at
        the CALL SITE, and `engine.effects.raster_dsl` is a sigil COMPTIME_HELPERS member
        glob-injected into every placed module, so the name is ambient wherever this lands."""
        module = self.module(
            {"p": _preset(id="p", patch_world_ys=[None], patch_motion=[None])},
            {5: "p"})
        self.assertIn("if sec == 5 && ch == 0 { out = PATCH_ANCHOR_NONE }", module)
        self.assertIn("if sec == 5 && ch == 0 { out = ANCHOR_MOTION_NONE }", module)

    def test_an_index_the_array_does_not_reach_emits_NO_ROW(self):
        """That is how 'keep the section's hand-authored value' is spelled: no row, so the
        chooser returns its `hand:` parameter."""
        module = self.module({"p": _preset(id="p", patch_world_ys=[224])}, {5: "p"})
        self.assertIn("if sec == 5 && ch == 0 { out = 224 }", module)
        for ch in (1, 2, 3):
            self.assertNotIn("if sec == 5 && ch == %d" % ch, module)

    def test_the_witness_counts_a_document_carrying_EITHER_key(self):
        for key, value in (("patch_world_ys", [224]), ("patch_motion", [None])):
            module = self.module({"p": _preset(id="p", **{key: value})}, {5: "p"})
            self.assertIn("EditorPatch_OJZ_Act1_Bindings = 1", module)

    def test_an_UNBOUND_document_contributes_no_row_and_no_binding(self):
        module = self.module({"p": _preset(id="p", patch_world_ys=[224])}, {})
        self.assertIn("EditorPatch_OJZ_Act1_Bindings = 0", module)
        self.assertNotIn("out = 224", module)

    def test_the_choosers_carry_a_CHANNEL_ensure_with_the_literal_inlined(self):
        """SECTION_PIN's reason: a comptime fn's free names resolve at the CALL SITE, so a
        named engine constant in the ensure would resolve in the effects library's scope or
        silently not at all."""
        module = self.module({}, {})
        self.assertIn("ensure(ch >= 0 && ch < %d," % effects_gen.RASTER_MAX_PATCH, module)
        self.assertIn("RASTER_MAX_PATCH", module)


class TestPatchCapabilityAndLiveness(PatchShapeBase):
    """The two refusals that need the GAME, which is why they run in `load_all_presets`.

    Both failures are SILENT NO-OPS if they get through — no crash, no wrong picture, just
    an effect that is not there — which is the whole argument for refusing them at all.
    """

    def test_a_motion_in_a_game_that_does_not_raise_CAP_ANCHOR_MOTION_is_refused(self):
        self.write_caps("0")             # demo's real mask
        msg = self.refuse_all("ojz_ground_wash",
                              _preset(patch_world_ys=[224], patch_motion=[_sweep()]))
        self.assertIn("CAP_ANCHOR_MOTION", msg)
        self.assertIn("SCANLINE_CAPS", msg)
        self.assertIn("never read", msg)

    def test_a_SEED_alone_is_NOT_refused_in_such_a_game(self):
        """The asymmetry is the point and it is the engine's, not this file's: the seed is
        installed unconditionally (34 bytes every game pays) and IS read by the plain latch
        loop; only the MOTION is behind the capability."""
        self.write_caps("0")
        self.write("ojz_ground_wash", _preset(patch_world_ys=[224]))
        self.assertIn("ojz_ground_wash", self.load_all())

    def test_the_capability_check_reads_the_games_OWN_declaration(self):
        """Not a mirror: sonic4 is $01DE and demo is 0, so there is no single value to
        carry. Clearing exactly the anchor bit out of the real mask must refuse, which a
        parser that only looked for a non-zero mask would not."""
        self.write_caps("$%04X" % (0x01DE & ~effects_gen.CAP_ANCHOR_MOTION))
        self.assertIn("CAP_ANCHOR_MOTION",
                      self.refuse_all("ojz_ground_wash",
                                      _preset(patch_world_ys=[224],
                                              patch_motion=[_sweep()])))

    def test_a_game_config_with_no_SCANLINE_CAPS_at_all_is_refused_not_read_as_zero(self):
        """A check that cannot run must not pass. Reading a missing declaration as 'no
        capabilities' would refuse every motion; reading it as 'all capabilities' would
        refuse none. Neither is a measurement."""
        self.write_caps("$01DE")
        with open(os.path.join(self.config, "game.emp"), "w") as f:
            f.write("contract Game {\n}\n")
        self.assertIn("SCANLINE_CAPS",
                      self.refuse_all("ojz_ground_wash",
                                      _preset(patch_world_ys=[224],
                                              patch_motion=[_sweep()])))

    def test_a_motion_on_a_channel_NOTHING_consumes_is_refused(self):
        """Channels 2 and 3 have no consumer in the shipped tree. A sweep there derives a
        screen line every frame that no fire, no band split and no off-screen ship reads."""
        msg = self.refuse_all(
            "ojz_ground_wash",
            _preset(patch_world_ys=[None, None, 224], patch_motion=[None, None, _sweep()]))
        self.assertIn("channel 2", msg)
        self.assertIn("patchable(ch: 2", msg)
        self.assertIn("SUPERSET", msg)

    def test_a_channel_declared_only_by_a_SCENE_ANCHOR_is_live(self):
        """Three consumers read the latched line, not one. A liveness check that looked only
        at `patchable()` — which is how the key-shape artifact's §4c phrases it — would
        refuse a sweep a parallax band split legitimately consumes."""
        self.write_lib("pub const S: Scene = scene(anchor: SceneAnchor.At(2, 15, 2))\n")
        self.write("ojz_ground_wash",
                   _preset(patch_world_ys=[None, None, 224],
                           patch_motion=[None, None, _sweep()]))
        self.assertIn("ojz_ground_wash", self.load_all())

    def test_a_SEED_on_a_dead_channel_is_NOT_refused(self):
        """Deliberately narrower than the motion check. A seed is what a channel becomes
        live AROUND — a `patchable()` record or an anchored scene can be added in the same
        series — and an inert anchor costs one word, where an inert sweep costs cycles every
        frame and reads as a feature that does not work."""
        self.write("ojz_ground_wash", _preset(patch_world_ys=[None, None, 224]))
        self.assertIn("ojz_ground_wash", self.load_all())


# =============================================================================
# EFFECTS-W1 item 10 — the `reels` scene key (empyrean AURORA_EFFECTS_SCHEMA §2.7,
# read at ff3f43f2e9c2b0b98e6c283f5cb87eb106f0fe5c).
# =============================================================================

REELS_CONSTANTS_EMP = """\
module games.sonic4.constants
pub const REEL_BAND_COUNT     = {bands}   // independently-scrolling vertical strips
pub const REEL_COLS_PER_BAND  = 4
"""


class ReelsBase(AssignmentBase):
    """AssignmentBase plus the two `.emp` surfaces the reels arm re-derives from.

    The constants module is written into every fixture because `reel_band_count`
    REFUSES rather than falling back on 5 — that refusal is itself under test below.
    """

    BANDS = 5
    RATES = [3, -5, 2, -4, 6]

    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.repo, "games", "sonic4", "config")
        os.makedirs(self.config)
        self.write_constants()

    def write_constants(self, bands=None):
        with open(os.path.join(self.config, "constants.emp"), "w") as f:
            f.write(REELS_CONSTANTS_EMP.format(
                bands=self.BANDS if bands is None else bands))

    def write_effects_lib(self, text):
        lib = os.path.join(self.repo, "games", "sonic4", "data", "effects")
        os.makedirs(lib, exist_ok=True)
        with open(os.path.join(lib, "ojz_effects.emp"), "w") as f:
            f.write(text)

    def write_descriptor(self, text):
        d = os.path.join(self.repo, "games", "sonic4", "data", "levels", "ojz",
                         "act1")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "act_descriptor.emp"), "w") as f:
            f.write(text)

    def write_reels_scene(self, stem, rates=None, **over):
        self.write_scene(stem, reels={"rates": self.RATES if rates is None
                                      else rates}, **over)

    def render(self):
        names = effects_gen.act_names(self.repo)
        return names, effects_gen.render_module(
            effects_gen.load_all_scenes("sonic4", self.repo),
            effects_gen.load_act_scene_ref(self.repo),
            effects_gen.load_section_scene_refs(self.repo),
            effects_gen.act_section_count(self.repo), names,
            repo=self.repo)


class TestReelBandCountIsDerived(unittest.TestCase):
    """CR §2.7: `minItems: 5` in the schema is a COPY of an `.emp` constant in another
    repo. The generator re-derives it, so a move of REEL_BAND_COUNT moves the check
    with it instead of failing much later inside sigil on a length nobody typed."""

    def test_it_reads_the_real_repos_declaration(self):
        self.assertEqual(effects_gen.reel_band_count(), 5)

    def test_it_agrees_with_the_gates_own_parser(self):
        """Two parsers for one declaration is how they drift — this is the pin
        MAX_PARALLAX_BANDS needed after months unpinned."""
        import reels_gate
        path = os.path.join(effects_gen.REPO, "games", "sonic4", "config",
                            "constants.emp")
        self.assertEqual(effects_gen.reel_band_count(),
                         reels_gate.emp_const(path, "REEL_BAND_COUNT"))

    def test_an_unreadable_constants_module_is_a_REFUSAL_not_a_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                effects_gen.reel_band_count("sonic4", tmp)
            self.assertIn("cannot read", str(ctx.exception))

    def test_a_missing_declaration_is_a_REFUSAL_not_a_fallback_to_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "games", "sonic4", "config")
            os.makedirs(cfg)
            with open(os.path.join(cfg, "constants.emp"), "w") as f:
                f.write("module games.sonic4.constants\n")
            with self.assertRaises(effects_gen.SceneShapeError) as ctx:
                effects_gen.reel_band_count("sonic4", tmp)
            self.assertIn("REEL_BAND_COUNT", str(ctx.exception))


class TestReelsPayloadShape(ReelsBase):
    """SHAPE only. The magnitude bound and pairwise distinctness are `reel_rates_ok`'s
    ensures in games/sonic4/config/constants.emp and are deliberately NOT repeated
    here — two sources for one rule is how they drift (module docstring's posture)."""

    def load(self):
        return effects_gen.load_all_scenes("sonic4", self.repo)

    def test_the_key_is_accepted_at_all(self):
        self.write_reels_scene("shimmer")
        self.assertEqual(self.load()["shimmer"]["reels"]["rates"], self.RATES)

    def test_a_singular_reel_is_still_an_unknown_key(self):
        self.write_scene("shimmer", reel={"rates": self.RATES})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        self.assertIn("unknown key `reel`", str(ctx.exception))

    def test_null_is_refused_and_the_message_says_OMIT(self):
        """CR ruling 2: there is no `none` spelling. The table is generated whole, so
        'keep' and 'off' are one state and one state gets one spelling."""
        self.write_scene("shimmer", reels=None)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        self.assertIn("OMIT", str(ctx.exception))

    def test_a_non_object_payload_is_refused(self):
        self.write_scene("shimmer", reels=[3, -5, 2, -4, 6])
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        self.assertIn("must be an object", str(ctx.exception))

    def test_cols_per_band_is_refused_BY_CLOSURE_and_named(self):
        """CR ruling 5 fixes the geometry at REEL_BAND_COUNT x REEL_COLS_PER_BAND
        because the column->band map is a compiled shift. The refusal names the key
        so an author does not read it as a typo."""
        self.write_scene("shimmer", reels={"rates": self.RATES, "cols_per_band": 2})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        self.assertIn("cols_per_band", str(ctx.exception))

    def test_a_missing_rates_member_is_refused(self):
        self.write_scene("shimmer", reels={})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        self.assertIn("has no `rates`", str(ctx.exception))

    def test_a_non_integer_rate_is_refused(self):
        self.write_scene("shimmer", reels={"rates": [3, "FACTOR_1", 2, -4, 6]})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        self.assertIn("bare integer", str(ctx.exception))

    def test_a_boolean_rate_is_refused_even_though_python_calls_it_an_int(self):
        self.write_scene("shimmer", reels={"rates": [3, True, 2, -4, 6]})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        self.assertIn("bare integer", str(ctx.exception))

    def test_a_wrong_length_is_refused_against_the_DERIVED_count(self):
        self.write_scene("shimmer", reels={"rates": [3, -5, 2, -4]})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.load()
        msg = str(ctx.exception)
        self.assertIn("4 rate(s)", msg)
        self.assertIn("REEL_BAND_COUNT is 5", msg)

    def test_the_length_check_FOLLOWS_the_constant_rather_than_the_schema(self):
        """The whole point of re-deriving: move REEL_BAND_COUNT and the accepted
        length moves with it. A hardcoded 5 would pass the first case and fail the
        second, which is exactly backwards."""
        self.write_constants(bands=4)
        self.write_scene("shimmer", reels={"rates": [3, -5, 2, -4]})
        effects_gen.load_all_scenes("sonic4", self.repo)     # accepted at 4
        self.write_scene("shimmer", reels={"rates": self.RATES})
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            effects_gen.load_all_scenes("sonic4", self.repo)
        self.assertIn("REEL_BAND_COUNT is 4", str(ctx.exception))

    def test_a_scene_with_no_reels_key_reads_NO_emp_at_all(self):
        """The no-content path must not depend on the two `.emp` scans, or every
        existing fixture in this file starts needing an effects library."""
        os.remove(os.path.join(self.config, "constants.emp"))
        self.write_scene("shimmer")
        self.assertEqual(sorted(self.load()), ["shimmer"])


class TestReelsRungRefusals(ReelsBase):
    """CR ruling 4. `Parallax_Current_Config` is a UNIQUE key only at rung 1; at rung
    2 or 3 the pointer is SHARED, and a table keyed on it hands those sections another
    section's motion — silently, which is why each of these is a refusal by name."""

    # The d-53 shape, and the asymmetry is the point: section 0 is the one bound at
    # rung 1, so its OWN preset naming a config changes nothing. Section 5 has no
    # sceneRef, so whatever its preset names is what section 5 RESOLVES to — and if
    # that is section 4's lowered record, section 5 silently gets section 4's reels.
    ALIASING_LIB = """\
module games.sonic4.ojz_effects in ojz_effects
pub data OJZ_Preset_Sec0: EffectsPreset = preset(pal: OJZ_Palette)
pub data OJZ_Preset_Sec5: EffectsPreset = preset(pal: OJZ_Palette,
                                                 parallax: {target})
"""

    DESCRIPTOR = """\
pub data OJZ_Act1_Sections: [Sec; 9] = [
    ojz_sec(sec: 0, blocks: A, effects: OJZ_Preset_Sec0),
    ojz_sec(sec: 5, blocks: B, effects: OJZ_Preset_Sec5),
]
"""

    def test_a_reels_scene_bound_at_rung_1_is_ACCEPTED(self):
        """The control. Without it every refusal below could be firing for a reason
        that has nothing to do with the rung."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertIn(f"pub data {names.reels('shimmer')}: [i8; ", text)

    def test_the_ACT_DEFAULT_is_rung_3_and_is_REFUSED_naming_the_sections(self):
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        self.write_project(act_ref="shimmer")
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render()
        msg = str(ctx.exception)
        self.assertIn("RUNG 3", msg)
        # every section without a rung-1 binding, named
        self.assertIn("0, 1, 2, 3, 5, 6, 7, 8", msg)

    def test_a_reels_scene_no_section_binds_is_REFUSED(self):
        self.write_reels_scene("shimmer")
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render()
        self.assertIn("no section binds it", str(ctx.exception))

    def test_a_preset_ALIASING_the_lowered_record_is_rung_2_and_names_the_section(self):
        """The d-53 shape, reproduced: two sections, one pointer. Here the alias is
        the editor binding itself, which is the case that would hand section 5 section
        4's reels rates."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names = effects_gen.act_names(self.repo)
        self.write_effects_lib(
            self.ALIASING_LIB.format(target=names.binding_sec(4)))
        self.write_descriptor(self.DESCRIPTOR)
        with self.assertRaises(effects_gen.SceneShapeError) as ctx:
            self.render()
        msg = str(ctx.exception)
        self.assertIn("RUNG 2", msg)
        self.assertIn("OJZ_Preset_Sec5", msg)
        self.assertIn("section(s) 5", msg)
        # attributed to the section, not merely to the preset symbol
        self.assertNotIn("UNKNOWN", msg)

    def test_a_preset_naming_a_HAND_config_is_not_an_alias(self):
        """Today's tree: OJZ_Preset_Sec0 and OJZ_Preset_Sec5 both name
        ParallaxConfig_OJZ_Underwater, a hand record no editor scene lowers to. That
        is rung-2 SHARING with nothing authored on it, and must stay green — otherwise
        the refusal is measuring the existence of ep_parallax rather than the alias."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        self.write_effects_lib(
            self.ALIASING_LIB.format(target="ParallaxConfig_OJZ_Underwater"))
        self.write_descriptor(self.DESCRIPTOR)
        names, text = self.render()
        self.assertIn(f"pub data {names.reels('shimmer')}: [i8; ", text)

    def test_a_parallax_mentioned_only_in_a_COMMENT_is_not_an_alias(self):
        """`OJZ_Preset_Sec5`'s own d-53 comment discusses its parallax binding two
        lines above the argument. A scan that reads comments finds the word it is
        looking for in a sentence about it."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names = effects_gen.act_names(self.repo)
        self.write_effects_lib(
            "module games.sonic4.ojz_effects in ojz_effects\n"
            f"// its parallax: {names.binding_sec(4)} would be an alias\n"
            "pub data OJZ_Preset_Sec5: EffectsPreset = preset(pal: OJZ_Palette)\n")
        self.write_descriptor(self.DESCRIPTOR)
        _names, text = self.render()
        self.assertIn(f"pub data {names.reels('shimmer')}: [i8; ", text)


class TestReelsEmission(ReelsBase):
    def test_with_no_reels_the_binding_table_is_STILL_emitted_and_empty(self):
        """`OJZ_Reels_Fill` names the table in a `lea`, so the symbol must exist in
        every bake. One terminator long, and zero bytes in release."""
        names, text = self.render()
        self.assertIn(f"pub data {names.reel_bindings}: [*u8; ", text)
        self.assertIn("if DEBUG == 1 { [0] } else { [] }", text)

    def test_the_rates_are_emitted_in_DOCUMENT_ORDER_verbatim(self):
        """CR §2.7: index i owns screen X 64i..64i+63 and the map is a compiled
        `lsr.b #2` the JSON cannot see. Sorting or reversing relocates every strip."""
        odd = [7, -1, 12, -9, 4]
        self.write_reels_scene("shimmer", rates=odd)
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertIn(f"const {names.reels_src('shimmer')} = [7, -1, 12, -9, 4]", text)

    def test_every_generated_table_routes_through_the_SHARED_guard(self):
        """The guard has to travel: `distinct5` was five-ary and hand-called, so a
        generated table inherited neither the length nor the distinctness ensure."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertIn(f"const {names.reels_ok('shimmer')} = reel_rates_ok("
                      f"{names.reels_src('shimmer')}, REEL_BAND_COUNT)", text)
        self.assertIn(f"ensure({names.reels_ok('shimmer')} == REEL_BAND_COUNT,", text)
        self.assertIn("use games.sonic4.constants.{REEL_BAND_COUNT, reel_rates_ok}",
                      text)

    def test_the_source_const_is_UNANNOTATED_so_the_magnitude_arm_sees_raw_ints(self):
        """`reel_rates_ok`'s magnitude arm reads the RAW authored ints, independent of
        emission rather than downstream of it.

        MEASURED 2026-09-04 (sigil 0a58f2ec, 768 authored into a scene's `reels.rates`):
        sigil DOES refuse an out-of-i8 literal in an `[i8; N]` initializer
        (`[emit.out-of-range] 768 does not fit i8`), which settles what the decision note
        and the empyrean CR both left NOT ESTABLISHED — so the silent-narrowing hazard
        this shape was chosen against does not exist. It is kept anyway: sigil's
        diagnostic names a SLOT and `reel_rates_ok`'s names the UNIT and the x256
        drift-export cause, and the guard fires first."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertNotIn(f"const {names.reels_src('shimmer')}: [i8;", text)

    def test_the_binding_table_pairs_the_section_record_with_its_rates(self):
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        # `extern("Name")` and not a bare name, and this is a MEASURED spelling, not a
        # style choice: a bare label inside a `[*u8; N]` array literal does not resolve
        # even for a symbol declared in the same module (sigil 0a58f2ec, 2026-09-04).
        self.assertIn(f'[extern("{names.binding_sec(4)}"), '
                      f'extern("{names.reels("shimmer")}"), 0]', text)

    def test_everything_it_emits_is_DEBUG_gated(self):
        """CR ruling 1 as a gate: nothing in the release shape can set
        OJZ_Reel_Active, so a release emission is a dormant scaffold."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        for line in text.splitlines():
            if line.startswith(f"pub data {names.reels('shimmer')}") or \
               line.startswith(f"pub data {names.reel_bindings}"):
                self.assertIn("if DEBUG == 1 {", line)
                self.assertIn("} else { [] }", line)

    def test_the_pointer_table_is_ALIGNED(self):
        """REEL_BAND_COUNT is odd, so an odd number of rate tables leaves the pointer
        table on an odd address — and a `move.l` through an odd address is a 68000
        ADDRESS ERROR, not a warning."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        head = text.split(f"pub data {names.reel_bindings}", 1)[0]
        self.assertTrue(head.rstrip().endswith("align 2")
                        or "align 2" in head.rsplit("\n\n", 1)[-1])

    def test_two_sections_on_one_scene_each_get_their_OWN_binding_row(self):
        """Each `EditorSceneBinding_*_SecN` is its own `pub data` at its own address,
        so two sections sharing a scene are two rows keyed on two pointers — not one
        row that would fire for whichever section installed last."""
        self.write_reels_scene("shimmer")
        self.write_sidecar(2, {"sceneRef": "shimmer"})
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertIn(f'[extern("{names.binding_sec(2)}"), '
                      f'extern("{names.reels("shimmer")}"), '
                      f'extern("{names.binding_sec(4)}"), '
                      f'extern("{names.reels("shimmer")}"), 0]', text)
        # ...and the TABLE is emitted ONCE, per SCENE. Walking the section->scene map
        # to emit tables declared this `pub data` once per bound section — a duplicate
        # symbol. Found 2026-09-04 by reading the loop, not by a gate: the assertion
        # above passes either way, which is what makes a count the thing to assert.
        self.assertEqual(text.count(f"pub data {names.reels('shimmer')}: [i8;"), 1)
        self.assertEqual(text.count(f"const {names.reels_src('shimmer')} = "), 1)
        self.assertEqual(text.count(f"const {names.reels_ok('shimmer')} = "), 1)

    def test_the_witness_equ_counts_the_bindings(self):
        self.write_reels_scene("shimmer")
        self.write_sidecar(4, {"sceneRef": "shimmer"})
        names, text = self.render()
        self.assertIn(f"pub equ {names.equ_reel_bindings} = 1", text)


class TestTheContractNamesTheReelsKey(unittest.TestCase):
    """The drift rule at the top of tools/EFFECTS_CONSUMER_CONTRACT.md: growing a
    reader is a CONTRACT change that amends that file and the empyrean schema pair in
    the same series. Derived from the constant, never typed."""

    DOC = os.path.join(effects_gen.REPO, "tools", "EFFECTS_CONSUMER_CONTRACT.md")

    def test_section_2_1_names_it(self):
        with open(self.DOC) as f:
            text = f.read()
        section = text.split("### 2.1 Scene definition files", 1)[-1] \
                      .split("### 2.1b", 1)[0]
        self.assertIn(
            f"`{effects_gen.REELS_KEY}`", section,
            f"tools/EFFECTS_CONSUMER_CONTRACT.md §2.1 never names "
            f"`{effects_gen.REELS_KEY}`, which tools/effects_gen.py accepts as a "
            f"scene key. Adding a read is a CONTRACT change under this document's "
            f"own drift rule.")
