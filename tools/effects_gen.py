#!/usr/bin/env python3
"""effects_gen.py — bake Aurora-authored effect scenes into generated `.emp`.

Scanline-services **P5**. This is the aeon consumer half of the Aurora effects
contract; the NORMATIVE read set it is built to is `tools/EFFECTS_CONSUMER_CONTRACT.md`
§2 — *"P5 implements exactly this and nothing more"*. Do not grow a reader for a field
that section does not list: adding one is a CONTRACT change that amends that file and
the empyrean schema pair in the same series, and Aurora re-pins its writer golden.

SLICE 1 (this commit) — discovery, load posture, and SHAPE validation only. Emission
of the generated module, the per-section binding labels and the `act_descriptor.emp`
import seam are later slices; the seam in particular waits on design Q-c (wave-1 design
§9), which is an open decision and not one to settle silently inside an implementation.

Validation posture (scanline design §7, contract §2.1, restated because it is the whole
architecture of this tool): the generator validates **SHAPE** — schema version, id,
unknown keys — and refuses rather than guessing. Authored **VALUES** are validated by
sigil when the generated `.emp` calls the real `scene()` / `layer()` constructors, whose
`ensure` text is the v1 error surface. This tool must never grow a value check that
duplicates a constructor guard: two sources for one rule is how they drift.

Error handling (contract §3, normative): aeon consumers **fail loud**. Bare `json.load`
plus direct subscripting, exactly the `inject_editor_bg.py:58-61` reference posture — a
malformed input raises, the build STOPS, and nothing is written back over the input. No
tolerate-garbage path, no repair path. Note the asymmetry the contract calls out: a
MISSING scene directory is legitimately "no editor scenes" and is not an error, while an
UNREADABLE file fails the bake. "Degrade gracefully" must not collapse those two.
"""

import json
import os
import re

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Scene ids are symbol-safe because they become `.emp` label components
# (`EditorScene_Act1_Sec0`-style). Pattern is design Q-d.
SCENE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

SCHEMA_VERSION = 1

# --- contract §2.1, top level -------------------------------------------------
# Read by the generator. `budget_class` is deliberately passthrough-unvalidated:
# sigil is its validator.
SCENE_KEYS = frozenset({
    "schema", "id", "layers",
    "v_factor", "v_center", "v_offset", "v_factor_fg",
    "deform_fg", "deform_bg", "v_deform",
    "anchor", "left_column_mask", "precision", "transition", "budget_class",
})

# Accepted and deliberately IGNORED. `name` is the one writer-only field in the
# format: a display label Aurora owns. The contract says the generator "ignores it
# and MUST keep ignoring it", so it is neither read nor refused.
SCENE_IGNORED_KEYS = frozenset({"name"})

# Excluded from the JSON surface (contract §2.1, empyrean schema §2.1). These are
# the byte-identity bridges for hand-migrated scenes; editor scenes DERIVE them.
# Refused rather than ignored — deliberate, and flagged here because the contract
# says "not read" without saying which: refusing catches a writer bug loudly,
# whereas ignoring would silently discard authored intent, and Aurora is not
# supposed to emit these at all. If that reading is wrong the fix is one line.
SCENE_REFUSED_KEYS = {
    "layer_mask_raw": "a byte-identity bridge for hand-migrated scenes; editor scenes derive it",
    "v_deform_shift_raw": "a byte-identity bridge for hand-migrated scenes; editor scenes derive it",
}

# --- contract §2.1, per layer -------------------------------------------------
LAYER_KEYS = frozenset({
    "world_y", "fa", "fb", "dsa", "dsb", "phase", "enabled",
    "deform", "curve", "vsplit",
})

LAYER_IGNORED_KEYS = frozenset({"name"})


# --- factor vocabulary (contract §2.1: "named FACTOR_* or {s1,s2,op}") --------
# Mirrored from engine/level/parallax_dsl.emp. This list is a SPELLING check, not a
# value check: it exists so a typo'd factor name becomes a generator refusal naming
# the near misses, instead of a sigil "unknown symbol" pointing at generated code the
# author never wrote. The authority remains parallax_dsl; if it grows a factor and
# this list lags, the failure is a refusal of something legal — loud and obvious —
# never a silently wrong emission.
FACTOR_NAMES = frozenset({
    "FACTOR_LOCKED", "FACTOR_0",
    "FACTOR_1", "FACTOR_1_2", "FACTOR_1_4", "FACTOR_1_8", "FACTOR_1_16", "FACTOR_1_32",
    "FACTOR_3_4", "FACTOR_3_8", "FACTOR_3_16",
    "FACTOR_5_8", "FACTOR_5_16",
    "FACTOR_7_8", "FACTOR_7_16", "FACTOR_15_16",
})

# --- attachment spellings ------------------------------------------------------
# THE CANONICAL "ABSENT" SPELLING IS THE STRING "none", not JSON null. Taken from
# the writer-side schema at empyrean origin/main
# (`contract/schema/aurora-effects-scene.schema.json`), where every attachment is
# `oneOf [{"const": "none"}, {object}]` with `"default": "none"`.
#
# Slices 1-2 assumed JSON null, having been written from the aeon-side field list
# without reading the writer's value spellings — so they would have REFUSED every
# real Aurora scene, since `"none"` is a non-null value and the refusal fired on
# `is not None`. That is the cross-repo-claim lesson in miniature: our contract
# enumerates the field NAMES and the schema owns their VALUES, and only reading
# the other repo catches it.
#
# `None` (JSON null) is accepted as a synonym: unambiguous, costs nothing, and
# refusing it would be strictness with no defect behind it.
ATTACH_NONE = ("none", None)

# Attachments that carry a tableRef, and the single arm each one legally takes.
SCENE_TABLE_ATTACHMENTS = {"deform_fg": "shared", "deform_bg": "shared",
                           "v_deform": "columns"}
LAYER_TABLE_ATTACHMENTS = {"deform": "own"}

# --- tableRef generators (contract §2.1) --------------------------------------
# name -> (.emp comptime fn, its parameters IN THE CONSTRUCTOR'S ORDER). The fns
# live in engine/level/parallax_dsl.emp and each returns [i8; 256]. Parameter
# ORDER is emitted as keyword arguments, so it is documentation rather than
# meaning — but the NAMES are meaning, and they are the fn's, not the schema's.
TABLE_GENERATORS = {
    "sine": ("deform_sine", ("amplitude", "period")),
    "triangle": ("deform_triangle", ("amplitude", "period")),
    "zero": ("deform_zero", ()),
    "v_column_perspective": ("v_column_perspective", ("focal", "max_offset")),
    "v_column_floor": ("v_column_floor", ("center", "max_offset")),
}

# `bin` tableRef paths resolve relative to this, reject `..`, and must be exactly
# 256 bytes — one signed byte per line of a 256-entry table.
TABLE_BIN_ROOT = ("games", "sonic4", "data", "editor", "effects")
TABLE_BIN_BYTES = 256

# Scene-level scalars, emitted in the constructor's own argument order.
SCENE_SCALARS = ("v_factor", "v_center", "v_offset", "v_factor_fg")
LAYER_SCALARS = ("dsa", "dsb", "phase", "enabled")

# Enum-valued scene fields: the schema spells these as lowercase strings and the
# `.emp` wants the constant. Slices 1-2 emitted the raw string, which would have
# generated `precision: cell` — a sigil unknown-symbol error pointing at generated
# code, for a scene the author spelled exactly right.
PRECISION_NAMES = {"cell": "PRECISION_CELL", "line": "PRECISION_LINE"}
TRANSITION_NAMES = {"smooth": "TRANS_SMOOTH", "instant": "TRANS_INSTANT"}
LEFT_COL_MASK_NAMES = {
    "undeclared": "SceneLeftColMask.Undeclared",
    "sprite_mask": "SceneLeftColMask.SpriteMask",
    "factor0_lock": "SceneLeftColMask.Factor0Lock",
    "accept": "SceneLeftColMask.Accept",
}

MAX_PARALLAX_BANDS = 8


class SceneShapeError(Exception):
    """A scene file that the generator refuses. Raised, never swallowed."""


def scene_dir(game: str = "sonic4", repo: str = REPO) -> str:
    return os.path.join(repo, "games", game, "data", "editor", "effects")


def discover_scene_files(game: str = "sonic4", repo: str = REPO):
    """Scene files, sorted by id. An ABSENT directory means 'no editor scenes'.

    Contract §2.1: absence is not an error. This is the one place the tool is
    permissive, and it is permissive about a *missing* input rather than a
    malformed one — the distinction §3 turns on.
    """
    d = scene_dir(game, repo)
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, n) for n in os.listdir(d) if n.endswith(".json")
    )


def _refuse(path: str, msg: str):
    raise SceneShapeError(f"{path}: {msg}")


def _check_keys(path: str, obj: dict, allowed, ignored, refused, where: str):
    """Refuse unknown keys — 'refuse, don't guess' (contract §2.1)."""
    for key in sorted(obj):
        if key in allowed or key in ignored:
            continue
        if refused and key in refused:
            _refuse(path, f"{where} carries `{key}`, which is excluded from the "
                          f"editor JSON surface: {refused[key]}. Remove it — the "
                          f"generator derives this from the authored fields.")
        _refuse(path, f"{where} carries unknown key `{key}`. The generator reads "
                      f"exactly the contract §2 field list and refuses rather than "
                      f"guessing; if this field is intended, it is a CONTRACT change "
                      f"(amend tools/EFFECTS_CONSUMER_CONTRACT.md and the empyrean "
                      f"schema pair together, then re-pin Aurora's golden). "
                      f"Known here: {', '.join(sorted(allowed))}.")


def load_scene(path: str) -> dict:
    """Load and SHAPE-validate one scene file. Raises on anything malformed.

    Deliberately bare `json.load` + direct subscripting (contract §3): a broken
    file must stop the build, not be repaired or routed around.
    """
    with open(path, "r") as f:
        scene = json.load(f)

    if not isinstance(scene, dict):
        _refuse(path, f"top level must be a JSON object, got {type(scene).__name__}")

    if "schema" not in scene:
        _refuse(path, "no `schema` key. Every editor scene declares its schema "
                      f"version; this generator accepts {SCHEMA_VERSION}.")
    if scene["schema"] != SCHEMA_VERSION:
        _refuse(path, f"`schema` is {scene['schema']!r}, this generator implements "
                      f"{SCHEMA_VERSION}. Refusing rather than guessing at a "
                      f"version it was not built against.")

    stem = os.path.splitext(os.path.basename(path))[0]
    if "id" not in scene:
        _refuse(path, f"no `id` key (expected `{stem}`, matching the filename stem)")
    if scene["id"] != stem:
        _refuse(path, f"`id` is {scene['id']!r} but the filename stem is {stem!r}. "
                      f"They must match: the id becomes a generated symbol component "
                      f"and the filename is how a human finds the file.")
    if not SCENE_ID_RE.match(stem):
        _refuse(path, f"id {stem!r} is not symbol-safe. Scene ids become `.emp` label "
                      f"components, so they must match {SCENE_ID_RE.pattern} "
                      f"(lowercase, digits and underscore; no hyphens, no leading digit).")

    _check_keys(path, scene, SCENE_KEYS, SCENE_IGNORED_KEYS, SCENE_REFUSED_KEYS,
                "scene")

    if "layers" not in scene:
        _refuse(path, "no `layers` key")
    layers = scene["layers"]
    if not isinstance(layers, list):
        _refuse(path, f"`layers` must be a list, got {type(layers).__name__}")
    if not layers:
        _refuse(path, "`layers` is empty. A scene with no layers renders nothing; "
                      "if the intent is 'no scene here', clear the sceneRef instead.")

    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            _refuse(path, f"layers[{i}] must be an object, got {type(layer).__name__}")
        _check_keys(path, layer, LAYER_KEYS, LAYER_IGNORED_KEYS, None,
                    f"layers[{i}]")
        for required in ("world_y", "fa", "fb"):
            if required not in layer:
                _refuse(path, f"layers[{i}] has no `{required}`. world_y/fa/fb are "
                              f"the three `layer()` arguments with no default.")

    return scene


def load_all_scenes(game: str = "sonic4", repo: str = REPO) -> dict:
    """All editor scenes for a game, keyed by id. Empty dict when none exist."""
    scenes = {}
    for path in discover_scene_files(game, repo):
        scene = load_scene(path)
        if scene["id"] in scenes:
            _refuse(path, f"duplicate scene id {scene['id']!r}")
        scenes[scene["id"]] = scene
    return scenes


def render_factor(path: str, value, where: str) -> str:
    """A factor, in either contract-legal spelling.

    Named (`"FACTOR_1_2"`) emits the bare symbol; composed (`{s1,s2,op}`) emits
    `packed(s1: .., s2: .., op: ..)`. Both are `engine.level.parallax_dsl` spellings
    and both are checked for SPELLING only — the packed field values are sigil's.
    """
    if isinstance(value, str):
        if value not in FACTOR_NAMES:
            near = sorted(n for n in FACTOR_NAMES if n.startswith(value[:9]))
            _refuse(path, f"{where}: unknown factor name {value!r}. Legal spellings "
                          f"are the parallax_dsl FACTOR_* constants or a composed "
                          f"{{s1, s2, op}} object."
                          + (f" Did you mean: {', '.join(near)}?" if near else ""))
        return value
    if isinstance(value, dict):
        missing = [k for k in ("s1", "s2", "op") if k not in value]
        if missing:
            _refuse(path, f"{where}: composed factor is missing {', '.join(missing)}. "
                          f"The composed spelling is {{s1, s2, op}} — all three.")
        extra = sorted(set(value) - {"s1", "s2", "op"})
        if extra:
            _refuse(path, f"{where}: composed factor carries unknown key(s) "
                          f"{', '.join(extra)}; it is exactly {{s1, s2, op}}.")
        return (f"packed(s1: {value['s1']}, s2: {value['s2']}, op: {value['op']})")
    _refuse(path, f"{where}: factor must be a FACTOR_* name or a {{s1, s2, op}} "
                  f"object, got {type(value).__name__}")


def is_absent(value) -> bool:
    """True for the schema's `"none"` and for JSON null. See ATTACH_NONE."""
    return value in ATTACH_NONE


def _single_arm(path: str, value, arm: str, where: str):
    """Unwrap a single-armed attachment object and return the arm's value.

    The arm's value is NOT always an object: `curve` is `{"to": <factor>}` and
    `vsplit` is `{"at": <int>}`, while `anchor` is `{"at": {...}}`. Callers check
    the shape they need.
    """
    if not isinstance(value, dict):
        _refuse(path, f"{where}: attachment must be \"none\" or an object, got "
                      f"{type(value).__name__}")
    if arm not in value:
        _refuse(path, f"{where}: attachment object must carry `{arm}`; got "
                      f"{', '.join(sorted(value)) or '(empty)'}.")
    extra = sorted(set(value) - {arm})
    if extra:
        _refuse(path, f"{where}: attachment carries unknown arm(s) "
                      f"{', '.join(extra)}; the only arm here is `{arm}`.")
    return value[arm]


def _fields(path: str, body: dict, required, where: str):
    missing = [k for k in required if k not in body]
    if missing:
        _refuse(path, f"{where}: missing {', '.join(missing)}. Required here: "
                      f"{', '.join(required)}.")
    extra = sorted(set(body) - set(required))
    if extra:
        _refuse(path, f"{where}: unknown key(s) {', '.join(extra)}. "
                      f"Exactly: {', '.join(required)}.")
    return [body[k] for k in required]


class TableRegistry:
    """Distinct deform tables realized across a bake, DEDUPED by content.

    Two scenes naming the same generator with the same parameters share one
    emitted table. That matches the shipped hand-authored idiom, where six
    `DeformTable_*` Labels are declared once in `scene_registry.emp` and
    referenced by many scenes — duplication there was the defect, not the design
    (`ojz_scenes.emp`'s comment block on why duplicate records differed).

    Emitted in the two-step form the hand tables use:

        pub const SceneSrc_EditorDeform_x = deform_sine(amplitude: 8, period: 32)
        pub data  EditorDeform_x: [i8; 256] = SceneSrc_EditorDeform_x

    The `pub data` half is what attachments reference, and it must be a LABEL:
    label imports travel as symbol references, whereas a const import
    re-evaluates its initializer in the consumer's scope and would duplicate
    every table into the importing section (EMP_PITFALLS §2/§8).
    """

    def __init__(self):
        self._by_key = {}   # canonical key -> label name
        self._decls = []    # (label, initializer) in first-seen order

    def intern(self, key: str, label: str, initializer: str) -> str:
        if key not in self._by_key:
            self._by_key[key] = label
            self._decls.append((label, initializer))
        return self._by_key[key]

    def declarations(self) -> str:
        """The table block, in first-seen order — deterministic for a given input."""
        out = []
        for label, init in self._decls:
            if init.startswith("embed("):
                out.append(f"pub data {label} (align: 2) = {init}")
            else:
                out.append(f"pub const SceneSrc_{label} = {init}")
                out.append(f"pub data {label}: [i8; 256] = SceneSrc_{label}")
        return "\n".join(out)

    def __len__(self):
        return len(self._decls)


def render_table_ref(path: str, ref, where: str, tables: TableRegistry) -> str:
    """Realize one tableRef and return the LABEL name an attachment references."""
    if not isinstance(ref, dict):
        _refuse(path, f"{where}: tableRef must be an object, got "
                      f"{type(ref).__name__}")

    if "bin" in ref:
        extra = sorted(set(ref) - {"bin"})
        if extra:
            _refuse(path, f"{where}: a `bin` tableRef takes no other key; got "
                          f"{', '.join(extra)}.")
        rel = ref["bin"]
        if ".." in rel.split("/"):
            _refuse(path, f"{where}: tableRef path {rel!r} contains a `..` segment. "
                          f"Paths resolve under "
                          f"{'/'.join(TABLE_BIN_ROOT)}/ and may not escape it.")
        full = os.path.join(REPO, *TABLE_BIN_ROOT, rel)
        if not os.path.isfile(full):
            _refuse(path, f"{where}: tableRef file not found: "
                          f"{'/'.join(TABLE_BIN_ROOT)}/{rel}")
        size = os.path.getsize(full)
        if size != TABLE_BIN_BYTES:
            _refuse(path, f"{where}: tableRef {rel!r} is {size} bytes; a deform "
                          f"table is exactly {TABLE_BIN_BYTES} (one signed byte "
                          f"per line).")
        label = "EditorDeform_bin_" + re.sub(r"[^a-z0-9]+", "_", rel.lower()).strip("_")
        embed_path = "/".join(TABLE_BIN_ROOT) + "/" + rel
        return tables.intern(f"bin:{rel}", label, f'embed("{embed_path}")')

    if "generator" not in ref:
        _refuse(path, f"{where}: tableRef needs `generator` or `bin`; got "
                      f"{', '.join(sorted(ref)) or '(empty)'}.")
    gen = ref["generator"]
    if gen not in TABLE_GENERATORS:
        _refuse(path, f"{where}: unknown generator {gen!r}. One of: "
                      f"{', '.join(sorted(TABLE_GENERATORS))}, or a `bin` path.")
    fn, params = TABLE_GENERATORS[gen]
    values = _fields(path, {k: v for k, v in ref.items() if k != "generator"},
                     params, f"{where}.{gen}")
    args = ", ".join(f"{p}: {v}" for p, v in zip(params, values))
    key = f"{gen}:" + ",".join(str(v) for v in values)
    label = "EditorDeform_" + gen + ("_" + "_".join(str(v) for v in values)
                                     if values else "")
    return tables.intern(key, label, f"{fn}({args})")


def render_table_attachment(path: str, value, key: str, arm: str, where: str,
                            tables: TableRegistry) -> str:
    """A table-bearing attachment → its `.emp` variant call.

    Payload slots are POSITIONAL in the enums (scene_dsl.emp), so the order here
    is meaning, not formatting.
    """
    body = _single_arm(path, value, arm, f"{where}.{key}")
    if not isinstance(body, dict):
        _refuse(path, f"{where}.{key}.{arm}: must be an object, got "
                      f"{type(body).__name__}")
    if arm == "own":       # SceneDeform.Own(table, shift_a, shift_b, phase, speed)
        fields = ("table", "shift_a", "shift_b", "phase", "speed")
        variant = "SceneDeform.Own"
    elif arm == "shared":  # SceneDeform.Shared(table, speed)
        fields = ("table", "speed")
        variant = "SceneDeform.Shared"
    else:                  # SceneVDeform.Columns(table, speed, amp_shift)
        fields = ("table", "speed", "amp_shift")
        variant = "SceneVDeform.Columns"
    vals = _fields(path, body, fields, f"{where}.{key}.{arm}")
    label = render_table_ref(path, vals[0], f"{where}.{key}.{arm}.table", tables)
    rest = ", ".join(str(v) for v in vals[1:])
    return f"{variant}({label}" + (f", {rest}" if rest else "") + ")"


def render_curve(path: str, value, where: str) -> str:
    """`{"to": <factor>}` → `SceneCurve.To(<factor>)`. The payload is a packed factor."""
    to = _single_arm(path, value, "to", where)
    return f"SceneCurve.To({render_factor(path, to, where + '.to')})"


def render_vsplit(path: str, value, where: str) -> str:
    """`{"at": <int>}` → `SceneVSplit.At(<int>)`."""
    at = _single_arm(path, value, "at", where)
    if not isinstance(at, int) or isinstance(at, bool):
        _refuse(path, f"{where}.at: must be an integer scanline, got "
                      f"{type(at).__name__}")
    return f"SceneVSplit.At({at})"


def render_anchor(path: str, value, where: str) -> str:
    """`{"at": {channel, dsa, dsb}}` → `SceneAnchor.At(channel, dsa, dsb)`."""
    at = _single_arm(path, value, "at", where)
    if not isinstance(at, dict):
        _refuse(path, f"{where}.at: must be an object with channel/dsa/dsb, got "
                      f"{type(at).__name__}")
    ch, dsa, dsb = _fields(path, at, ("channel", "dsa", "dsb"), where + ".at")
    return f"SceneAnchor.At({ch}, {dsa}, {dsb})"


def _render_enum(path: str, value, table: dict, where: str) -> str:
    """A lowercase schema enum string → its `.emp` constant."""
    if value not in table:
        _refuse(path, f"{where}: {value!r} is not a legal value. One of: "
                      f"{', '.join(sorted(table))}.")
    return table[value]


def render_layer(path: str, layer: dict, where: str,
                 tables: TableRegistry) -> str:
    args = [f"world_y: {layer['world_y']}",
            f"fa: {render_factor(path, layer['fa'], where + '.fa')}",
            f"fb: {render_factor(path, layer['fb'], where + '.fb')}"]
    for key in LAYER_SCALARS:
        if layer.get(key) is not None:
            args.append(f"{key}: {layer[key]}")
    if not is_absent(layer.get("curve")):
        args.append(f"curve: {render_curve(path, layer['curve'], where + '.curve')}")
    if not is_absent(layer.get("vsplit")):
        args.append(f"vsplit: {render_vsplit(path, layer['vsplit'], where + '.vsplit')}")
    for key, arm in LAYER_TABLE_ATTACHMENTS.items():
        if not is_absent(layer.get(key)):
            args.append(f"{key}: " + render_table_attachment(
                path, layer[key], key, arm, where, tables))
    return "layer(" + ", ".join(args) + ")"


def render_scene(path: str, scene: dict, tables: TableRegistry = None) -> str:
    """The `pub const … : Scene = scene(…)` text for one validated scene.

    Deliberately returns TEXT and writes nothing. The generated module is not wired
    into the build until the descriptor import seam exists (wave-1 design §3, open
    question Q-c): an UNREACHED `.emp` module gets zero body elaboration, so
    `ensure(1 == 0)` inside one builds green. Emitting a module nothing imports
    would look finished while validating nothing — the failure this pipeline is
    least able to notice.
    """
    if tables is None:
        tables = TableRegistry()
    layers = scene["layers"]
    if len(layers) > MAX_PARALLAX_BANDS:
        _refuse(path, f"{len(layers)} layers exceeds MAX_PARALLAX_BANDS "
                      f"({MAX_PARALLAX_BANDS}); scene() refuses this too, but the "
                      f"generator would have to pad past the array to reach it.")
    rendered = [render_layer(path, l, f"layers[{i}]", tables)
                for i, l in enumerate(layers)]
    # The array is ALWAYS eight slots, padded with no_layer() — the hand-authored
    # idiom (games/sonic4/data/effects/ojz_scenes.emp) and what scene() indexes.
    rendered += ["no_layer()"] * (MAX_PARALLAX_BANDS - len(rendered))

    body = ["    layers: [ " + ",\n              ".join(rendered) + " ]",
            f"    count: {len(layers)}"]
    for key in SCENE_SCALARS:
        if scene.get(key) is not None:
            body.append(f"    {key}: {scene[key]}")
    # Enum-valued fields: lowercase schema strings, `.emp` constants.
    if scene.get("precision") is not None:
        body.append("    precision: " + _render_enum(
            path, scene["precision"], PRECISION_NAMES, "scene.precision"))
    if scene.get("transition") is not None:
        body.append("    transition: " + _render_enum(
            path, scene["transition"], TRANSITION_NAMES, "scene.transition"))
    if scene.get("left_column_mask") is not None:
        body.append("    left_column_mask: " + _render_enum(
            path, scene["left_column_mask"], LEFT_COL_MASK_NAMES,
            "scene.left_column_mask"))
    if not is_absent(scene.get("anchor")):
        body.append("    anchor: " + render_anchor(
            path, scene["anchor"], "scene.anchor"))
    for key, arm in SCENE_TABLE_ATTACHMENTS.items():
        if not is_absent(scene.get(key)):
            body.append(f"    {key}: " + render_table_attachment(
                path, scene[key], key, arm, "scene", tables))
    # layer_mask_raw / v_deform_shift_raw are deliberately NOT emitted: they are the
    # hand-migration byte-identity bridges, their -1 defaults mean "derive", and
    # editor scenes derive. The loader refuses them in the JSON for the same reason.
    return (f"pub const Scene_Editor_{scene['id']}: Scene = scene(\n"
            + ",\n".join(body) + ")")


if __name__ == "__main__":
    import sys

    found = load_all_scenes()
    if not found:
        print("effects_gen: no editor scenes (absent directory or no .json files)")
        sys.exit(0)
    for sid, scene in sorted(found.items()):
        print(f"effects_gen: {sid} — {len(scene['layers'])} layer(s), shape OK")
