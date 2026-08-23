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


# =============================================================================
# SLICE 5 — assignments, the generated binding module, and the descriptor seam.
# =============================================================================
#
# THE OWNER RULING THIS IMPLEMENTS (2026-08-22, design §9 Q-c): the ALWAYS-EMITTED
# default binding. The generator emits the act-default binding for EVERY act,
# whether or not editor content exists — with no editor scenes it resolves to the
# hand-authored default, with editor scenes to the editor-authored one — so
# `act_descriptor.emp` has exactly ONE path, always live, no conditional and no
# branch that is dead in either state. §3's older text ("the stub always exports the
# act-default label aliased to nothing only when project.json/sidecars are silent")
# is SUPERSEDED by that ruling.
#
# ---- WHAT THE BINDING IS, AND WHY IT IS NOT A LABEL ----
#
# Design §3 mandates `pub data` **Labels** over `const`s, because a const import
# re-evaluates its initializer in the consumer's scope. That mandate is CORRECT and
# is kept for everything with bytes: the deform tables and the lowered records below
# are `pub data` Labels under STABLE names, and the descriptor could import them by
# name list exactly as `ojz_scenes.emp` imports `DeformTable_*`.
#
# It cannot express the ZERO-CONTENT arm, and that was measured, not assumed
# (2026-08-22, this parcel, each one a real `sigil build`):
#
#   1. `pub equ EditorSceneDefault_.. = ParallaxConfig_OJZ_Default` — an equ is the
#      natural spelling for "a link-level name for an address", and
#      `empyrean/docs/SIGIL_SPEC2_LANGUAGE.md` §7.5 says "`pub equ` adds module
#      visibility like every other `pub` item". It does not: sigil's
#      `item_pub_name()` (crates/sigil-frontend-emp/src/resolve/imports.rs:128-160)
#      has no `Item::Equ` arm, so the descriptor's `use` fails with
#      `module ... has no `pub` name `EditorSceneDefault_OJZ_Act1``. Spec/impl
#      divergence — reported, not worked around.
#   2. `pub const EditorSceneDefault_.. = ParallaxConfig_OJZ_Default` — fails with
#      `unknown name `ParallaxConfig_OJZ_Default`` reported at a span inside the
#      DEFINING file. The mechanism is visible in sigil at
#      resolve/mod.rs:204-224: an imported const's initializer is FOLDED to an i64
#      at the definition site, best-effort; a Label does not fold, so the clone
#      keeps its expression and re-evaluates in the consumer, where the bare name is
#      not in the rename map. This is the design's clone-injection trap firing on
#      exactly the shape the design warned about.
#   3. There is no zero-byte label-alias form in `.emp` at all: `item_pub_name()`
#      carries data/proc/offsets/dispatch/script/const/comptime-fn/context/struct/
#      enum/bitfield/newtype/vars, and only `data` mints a ROM label — and `data`
#      always emits bytes.
#
# So the binding is a `pub comptime fn` returning a Label — the third mechanism, and
# the only one that carries a link symbol across a hand-authored, content-independent
# `use` name list:
#
#     pub comptime fn ojz_act1_act_default(hand: Label) -> Label { return hand }
#     pub comptime fn ojz_act1_act_default(hand: Label) -> Label { return EditorSceneBinding_OJZ_Act1_Default }
#
# It is NOT the const axis: a comptime fn's body carries no image, so nothing can be
# cloned into the descriptor's section — which is the property the Label mandate
# existed to protect. The fallback travels as a PARAMETER (`hand:`), so the
# descriptor keeps naming its own hand default and the generator only chooses.
# MEASURED: the fn-body reference to the module's own `pub data` resolves at the
# descriptor call site and links to the generated record (fixture build, crc
# 7e0d4aaf); and the descriptor's name-list `use` of the fn is a REAL lowering edge —
# a poisoned `ensure(1 == 0)` in this module fails the build with the seam in place
# and builds GREEN with an unchanged CRC when the `use` line is removed.
#
# ---- WHAT IS NOT DONE HERE, DELIBERATELY ----
#
# No `games/sonic4/map.toml` `order` row is authored for this module's section. The
# row must name the section's HEAD LABEL (sigil keys the order check on the
# lowest-offset label, native.rs:3194-3203), and the head label of this block is
# CONTENT-DERIVED — in the fixture build it was `EditorDeform_probe`, a deduped
# table name that depends on which scenes exist. There is nothing correct to write
# before the first editor scene exists, the section emits zero bytes until then so a
# row would be inert AND unverifiable, and the day content lands sigil stops the
# build loudly and by name (`[map.order-undeclared] byte-emitting section
# `<head>` is not in the declared `order``). map.toml carries a reserved-slot
# COMMENT at the intended position instead of a guessed row.

ACT_SCENE_REF_KEY = "sceneRef"
PROJECT_JSON = "project.json"


def _act_entry(repo: str = REPO, zone: int = 0, act: int = 0) -> dict:
    """The project.json act entry. Bare load + direct subscripting (contract §3)."""
    with open(os.path.join(repo, PROJECT_JSON), "r") as f:
        project = json.load(f)
    return project["zones"][zone]["acts"][act], project["zones"][zone]


def _scene_ref(path: str, value, where: str):
    """One `sceneRef` value → a scene id string, or None for absent.

    Contract §2.2, stated in the contract's own words: "`sceneRef` is a string id or
    null, NEVER a numeric index" — because AURORA's parser nulls a non-string
    SILENTLY (`section-meta.ts:29-30`), so `sceneRef: 3` presents as "the assignment
    didn't stick". The generator refuses it instead: the one writer that can still
    see the mistake is the build.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        _refuse(path, f"{where}: sceneRef must be a scene-id STRING or null, got "
                      f"{type(value).__name__} ({value!r}). A numeric index is "
                      f"refused on purpose — Aurora's sidecar parser nulls a "
                      f"non-string value silently, so this would present as an "
                      f"assignment that did not stick.")
    if not SCENE_ID_RE.match(value):
        _refuse(path, f"{where}: sceneRef {value!r} is not a legal scene id "
                      f"({SCENE_ID_RE.pattern}) — ids become `.emp` symbol "
                      f"components.")
    return value


def load_section_scene_refs(repo: str = REPO, zone: int = 0, act: int = 0) -> dict:
    """`{section_index: scene_id}` from the per-section sidecars.

    THE MISSING/UNREADABLE SPLIT IS THE POINT (contract §2.2/§3). A sidecar that is
    absent is all-refs-null — Aurora only writes one when a ref is non-null, so the
    all-default act legitimately has no file on disk. A sidecar that EXISTS but does
    not parse fails the bake loudly: "degrade gracefully" must not collapse those
    two, because all-null is exactly the state that triggers Aurora's destructive
    cleared-overwrite.
    """
    entry, _zone = _act_entry(repo, zone, act)
    data_path = os.path.join(repo, entry["dataPath"])
    out = {}
    for i in range(act_section_count(repo, zone, act)):
        path = os.path.join(data_path, f"section_{i}.meta.json")
        if not os.path.isfile(path):
            continue                      # absent = all refs null. NOT an error.
        with open(path, "r") as f:        # unreadable = raises. Deliberate.
            meta = json.load(f)
        if not isinstance(meta, dict):
            _refuse(path, f"sidecar top level must be a JSON object, got "
                          f"{type(meta).__name__}")
        ref = _scene_ref(path, meta.get(ACT_SCENE_REF_KEY), f"section {i}")
        if ref is not None:
            out[i] = ref
    return out


def load_act_scene_ref(repo: str = REPO, zone: int = 0, act: int = 0):
    """The act-level default scene id from project.json, or None.

    None = "the hand-authored `act_parallax_config` default stands" (ruling Q4).
    Under the Q-c ruling that is still an EMITTED binding — it resolves to the
    `hand:` argument rather than to nothing.
    """
    entry, _zone = _act_entry(repo, zone, act)
    return _scene_ref(os.path.join(repo, PROJECT_JSON), entry.get(ACT_SCENE_REF_KEY),
                      f"act {entry['id']}")


def act_section_count(repo: str = REPO, zone: int = 0, act: int = 0) -> int:
    """grid_w * grid_h — the act's flat section count, the binding table's domain."""
    entry, _zone = _act_entry(repo, zone, act)
    return entry["gridWidth"] * entry["gridHeight"]


class ActNames:
    """Every generated symbol/​path name for one act, derived from project.json ids.

    Derived and not typed: the zone/act ids are the authority, so a second act
    cannot silently collide with act 1's module or section name (which is a latent
    hazard in the `bg_anim.emp` precedent, whose section name carries no act
    suffix — noted, not fixed here).
    """

    def __init__(self, zone_id: str, act_id: str):
        self.zone_id, self.act_id = zone_id, act_id
        stem = f"{zone_id}_{act_id}"                      # ojz_act1
        cap = f"{zone_id.upper()}_{act_id.capitalize()}"  # OJZ_Act1
        self.module = f"games.sonic4.{zone_id}_effects_editor_{act_id}"
        self.section = f"{zone_id}_effects_editor_{act_id}"
        self.fn_act_default = f"{stem}_act_default"
        self.fn_sec_scene = f"{stem}_sec_scene"
        self.binding_default = f"EditorSceneBinding_{cap}_Default"
        self.scene_array = f"EditorScenes_{cap}"
        self.equ_scenes = f"EditorScenes_{cap}_Count"
        self.equ_bindings = f"EditorScenes_{cap}_Bindings"

    def binding_sec(self, i: int) -> str:
        return f"EditorSceneBinding_{self.zone_id.upper()}_" \
               f"{self.act_id.capitalize()}_Sec{i}"

    def out_path(self, repo: str = REPO) -> str:
        return os.path.join(repo, "games", "sonic4", "data", "generated",
                            self.zone_id, self.act_id, "effects_scenes.emp")


def act_names(repo: str = REPO, zone: int = 0, act: int = 0) -> ActNames:
    entry, zone_entry = _act_entry(repo, zone, act)
    return ActNames(zone_entry["id"], entry["id"])


# The record shapes + lowerings live in games/sonic4/data/effects/scene_registry.emp
# and are IMPORTED, never re-declared here: it stays the single authority for what a
# lowered record looks like, and a band count it has no shape for is a refusal naming
# that file rather than a second, drifting copy of `lowerN`.
LOWERABLE_BAND_COUNTS = (1, 2, 4, 5)


def _lowering(path: str, scene: dict) -> tuple:
    n = len(scene["layers"])
    if n not in LOWERABLE_BAND_COUNTS:
        _refuse(path, f"scene has {n} layers, and games/sonic4/data/effects/"
                      f"scene_registry.emp declares record shapes for "
                      f"{', '.join(str(c) for c in LOWERABLE_BAND_COUNTS)} bands "
                      f"only. Adding one is a mechanical copy there (a `SceneCfg{n}` "
                      f"struct and a `lower{n}` with {n} scene_band terms), made "
                      f"`pub` like the others — never a second lowering in "
                      f"generated code.")
    return f"SceneCfg{n}", f"lower{n}"


def render_module(scenes: dict, act_ref, sec_refs: dict, sections: int,
                  names: ActNames) -> str:
    """The whole generated `.emp` module, for any content state including none.

    Deterministic for a given input: scenes are walked in sorted-id order and the
    table registry emits in first-seen order, so a re-bake with unchanged inputs is
    byte-identical (which is what the build's drift gate compares).
    """
    # ---- resolve the assignments against the library, loudly ----
    bound = {}                              # section index -> scene id
    for i in sorted(sec_refs):
        if sec_refs[i] not in scenes:
            raise SceneShapeError(
                f"section_{i}.meta.json: sceneRef {sec_refs[i]!r} names no scene in "
                f"{scene_dir()} — wave 1 is editor-library ids only, so a sceneRef "
                f"cannot name a hand-authored `.emp` scene (design §4). Known ids: "
                f"{', '.join(sorted(scenes)) or '(none)'}.")
        bound[i] = sec_refs[i]
    if act_ref is not None and act_ref not in scenes:
        raise SceneShapeError(
            f"{PROJECT_JSON}: act sceneRef {act_ref!r} names no scene in "
            f"{scene_dir()}. Known ids: {', '.join(sorted(scenes)) or '(none)'}.")

    used = sorted(set(bound.values()) | ({act_ref} if act_ref else set()))
    unused = sorted(set(scenes) - set(used))

    tables = TableRegistry()
    scene_decls = [render_scene(os.path.join(scene_dir(), sid + ".json"),
                                scenes[sid], tables) for sid in used]

    out = [HEADER.format(
        module=names.module, section=names.section,
        act=f"{names.zone_id}/{names.act_id}", sections=sections,
        scenes=len(used), bindings=len(bound) + (1 if act_ref else 0),
        unused=(", ".join(unused) if unused else "none"))]

    out.append(f"module {names.module} in {names.section}\n")
    out.append("use engine.constants.{MAX_ACT_SECTIONS}")
    if used:
        # The same four imports scene_registry.emp carries, for the same four
        # reasons — see its banner. `band_entry`/`band_ext`/BAND_EXT_N/`band_curve`/
        # BAND_CURVE_N are load-bearing even though nothing here spells them: a
        # struct's declaration is re-elaborated in every module that imports it
        # (docs/EMP_PITFALLS.md §8), and a partial import fails pointing at
        # engine/level/parallax.emp.
        out.append("use engine.structs.{parallax_config}")
        out.append("use engine.parallax.{band_entry, band_record, band_ext, "
                   "BAND_EXT_N, band_curve, BAND_CURVE_N}")
        # GLOBS, MANDATORY. A comptime fn's free names resolve at the CALL SITE, so
        # scene()/layer()/lowerN reach their helpers through what is in scope HERE;
        # a selective import is LOUD on the function axis and SILENT on the constant
        # axis (docs/EMP_PITFALLS.md §2, scene_dsl.emp's pin block).
        out.append("use engine.level.scene_dsl.*")
        out.append("use engine.level.parallax_dsl.*")
        shapes = sorted({s for s, _ in (_lowering("", scenes[sid]) for sid in used)})
        lowers = sorted({l for _, l in (_lowering("", scenes[sid]) for sid in used)})
        out.append("use games.sonic4.scene_registry.{"
                   + ", ".join(shapes + lowers) + "}")
    out.append("")

    if used:
        out.append("// ---- deform tables, deduped by content across the act ----")
        decls = tables.declarations()
        if decls:
            out.append(decls)
            out.append("")
        out.append("// ---- the authored scenes, through the REAL constructors ----")
        out.append("// Every `ensure` in layer()/scene() fires on authored content here;")
        out.append("// this generator validates SHAPE only and never duplicates a")
        out.append("// constructor guard (contract §2.1).")
        for decl in scene_decls:
            out.append(decl)
            out.append("")
        out.append(f"pub const {names.scene_array}: [Scene; {len(used)}] = [")
        for sid in used:
            out.append(f"    Scene_Editor_{sid},")
        out.append("]")
        out.append("")
        out.append(BUDGET_BLOCK.format(array=names.scene_array, n=len(used)))
        out.append("")
        out.append("// ---- the lowered records, under STABLE binding names ----")
        if act_ref:
            shape, lower = _lowering("", scenes[act_ref])
            out.append(f"pub data {names.binding_default}: {shape} = "
                       f"{lower}({names.scene_array}[{used.index(act_ref)}])")
        for i in sorted(bound):
            shape, lower = _lowering("", scenes[bound[i]])
            out.append(f"pub data {names.binding_sec(i)}: {shape} = "
                       f"{lower}({names.scene_array}[{used.index(bound[i])}])")
        out.append("")

    # ---- the witness equates (zero ROM bytes, link-visible) ----
    out.append(WITNESS_BLOCK.format(
        equ_scenes=names.equ_scenes, scenes=len(used),
        equ_bindings=names.equ_bindings,
        bindings=len(bound) + (1 if act_ref else 0)))
    out.append("")
    out.append(SECTION_PIN.format(sections=sections))
    out.append("")

    # ---- (d) THE BINDINGS — always emitted, both of them, every act ----
    out.append(BINDING_BANNER)
    out.append(f"pub comptime fn {names.fn_act_default}(hand: Label) -> Label {{")
    if act_ref:
        out.append(f"    return {names.binding_default}")
    else:
        out.append("    return hand")
    out.append("}")
    out.append("")
    out.append(f"pub comptime fn {names.fn_sec_scene}(sec: int, hand: Label = 0) -> Label {{")
    out.append(f'    ensure(sec >= 0 && sec < {sections}, "{names.fn_sec_scene}(sec: '
               f'{{sec}}): this act has {sections} sections, so there is no binding '
               f'slot for that index — the descriptor and project.json\'s grid have '
               f'drifted apart")')
    out.append("    comptime var out = hand")
    for i in sorted(bound):
        out.append(f"    if sec == {i} {{ out = {names.binding_sec(i)} }}")
    out.append("    return out")
    out.append("}")
    return "\n".join(out) + "\n"


HEADER = """\
// AUTO-GENERATED by tools/effects_gen.py — DO NOT EDIT.
//
// Aurora-authored effect scenes for {act}, and the two binding functions
// `act_descriptor.emp` calls. Scanline-services P5 slice 5; the contract is
// tools/EFFECTS_CONSUMER_CONTRACT.md §2 and the design is
// docs/superpowers/specs/2026-08-22-aurora-effects-wave1-design.md §3.
//
// STATE OF THIS BAKE: {scenes} editor scene(s) reached by an assignment,
// {bindings} binding(s), {sections} act sections. Authored but unassigned: {unused}.
//
// THE TWO `pub comptime fn`s AT THE BOTTOM ARE EMITTED FOR EVERY ACT, ALWAYS —
// owner ruling 2026-08-22 (design §9 Q-c, the always-emitted default). With no
// editor content they return the `hand:` fallback the descriptor passes; with
// editor content they return the lowered record above. The descriptor therefore
// has ONE path, always live, and never a conditional. They are functions and not
// Labels for a measured reason: see the block comment above `render_module()` in
// tools/effects_gen.py — `pub equ` is not importable and a `pub const` carrying a
// Label fails the clone-injection re-evaluation, both verified against sigil.
//
// Placed at the `{section}` section
// (module `{module}`). While the block above emits no
// bytes there is no map.toml `order` row: the row must name the section's
// content-derived HEAD LABEL, and sigil stops the build by name the moment there is
// one to write.
"""

WITNESS_BLOCK = """\
// ---- REACHABILITY WITNESSES (tools/effects_seam_gate.py) ----
//
// `equ` and NOT `const`, and the distinction is the whole gate: an equ mints a
// link-level symbol that reaches the build's listing, while a `pub const` is a
// name-resolution-only item invisible to every tool (scene_registry.emp's ledger
// rows, same mechanism). Both are zero ROM bytes.
//
// An equ is only defined if this module is LOWERED, and a module is lowered iff it
// is in the target's `use` closure — so the presence of these two names in the
// listing is positive evidence that `act_descriptor.emp`'s import edge is live. That
// matters because an unreached `.emp` module gets ZERO body elaboration: every guard
// below, including the budget fold, builds green while asserting nothing. Measured
// on this very module (2026-08-22): with the descriptor's `use` line removed, an
// `ensure(1 == 0)` here built GREEN with an unchanged CRC.
pub equ {equ_scenes} = {scenes}
pub equ {equ_bindings} = {bindings}\
"""

SECTION_PIN = """\
// The binding table's domain, held against the engine's flat-section ceiling. The
// literal below is repeated inside `sec_scene`'s ensure ON PURPOSE — a comptime fn's
// free names resolve at the CALL SITE, so a named constant there would resolve in
// act_descriptor's scope (or silently not at all); docs/EMP_PITFALLS.md §2's rule is
// to inline the literal and pin it where the authority IS visible, which is here.
ensure({sections} <= MAX_ACT_SECTIONS,
       "this act declares {sections} sections in project.json, past the engine's MAX_ACT_SECTIONS ceiling ({{MAX_ACT_SECTIONS}}) — the binding table has slots the section grid cannot address")\
"""

BUDGET_BLOCK = """\
// ---- THE BUDGET GATE OVER EDITOR SCENES (design §3(e)) ----
//
// The same hard, build-time gate the hand scenes get, mirroring
// games/sonic4/data/effects/scene_registry.emp's `SceneRegistry_BudgetChecked` —
// editor scenes are not a softer class. Enforcement is the `ensure`s INSIDE
// scene_budget_enforce(); the reference below is load-bearing, because an
// unreferenced top-level `const X = f(..)` is comptime-INERT and the fold would
// never run (docs/EMP_PITFALLS.md §3).
pub const {array}_BudgetChecked = scene_budget_enforce({array})
ensure({array}_BudgetChecked == {n},
       "editor scenes: the budget fold checked {{{array}_BudgetChecked}} scenes, not the {n} bound by this act's assignments — a fold that examines fewer scenes than it was handed is gating a subset")

// THE CAPABILITY SUBSET TEST, one-sided exactly as the registry's is. An editor
// scene that demands a scanline service the game does not declare would have its
// machinery omitted by the P2 lowering — a wrong picture on hardware — and the
// registry's fold cannot see it, because the registry folds the HAND scenes only.
// A declared SUPERSET only forgoes a specialisation, so the test stays one-sided.
pub const {array}_CapsFolded = fold_caps({array})
ensure(({array}_CapsFolded & ~Game.SCANLINE_CAPS) == 0,
       "editor scenes: the folded capability mask {{{array}_CapsFolded}} is NOT a subset of Game.SCANLINE_CAPS {{Game.SCANLINE_CAPS}}; the UNDECLARED bits are {{{array}_CapsFolded & ~Game.SCANLINE_CAPS}} — an Aurora-authored scene demands a scanline service this game does not declare. Either widen SCANLINE_CAPS in games/sonic4/config/game.emp, or stop authoring the capability in the scene that raises it")\
"""

BINDING_BANNER = """\
// =====================================================================
// THE BINDINGS — the seam act_descriptor.emp calls. ALWAYS BOTH, ALWAYS LIVE.
//
// `hand:` is the descriptor's own fallback, carried as a PARAMETER rather than
// named here: a comptime fn's free names resolve at the call site, so the hand
// default has to arrive from the caller — and that is the better contract anyway,
// since the descriptor keeps owning its hand bindings and this module only chooses.
// =====================================================================\
"""


def generate(repo: str = REPO, zone: int = 0, act: int = 0) -> tuple:
    """(output path, module text) for one act. Reads only; writes nothing."""
    names = act_names(repo, zone, act)
    return names.out_path(repo), render_module(
        load_all_scenes("sonic4", repo),
        load_act_scene_ref(repo, zone, act),
        load_section_scene_refs(repo, zone, act),
        act_section_count(repo, zone, act),
        names)


def _atomic_write(path: str, text: str) -> None:
    """Write via a temp file + rename (contract §3, the ojz_block_gen idiom).

    A partial generated module is never observable, so an interrupted bake cannot
    leave a file that parses as something else.
    """
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "shapes"
    try:
        if cmd == "emit":
            path, text = generate()
            _atomic_write(path, text)
            print(f"effects_gen: wrote {os.path.relpath(path, REPO)}")
        elif cmd == "check":
            # THE DRIFT GATE. Regenerate in memory and compare against the committed
            # artifact — the generated tree is a committed input to the build, so
            # "someone edited it by hand" and "someone changed an editor scene
            # without re-baking" are the two failures this catches. Cheap enough for
            # every build: pure Python over in-repo inputs, no donor, no compressor.
            path, text = generate()
            if not os.path.isfile(path):
                print(f"effects_gen: MISSING — {os.path.relpath(path, REPO)} does "
                      f"not exist. It is a COMMITTED artifact that "
                      f"act_descriptor.emp imports, emitted for every act whether "
                      f"or not editor content exists (owner ruling 2026-08-22).")
                print("  Run `python3 tools/effects_gen.py emit` and commit it.")
                sys.exit(1)
            with open(path, "r") as f:
                have = f.read()
            if have != text:
                print(f"effects_gen: DRIFT — {os.path.relpath(path, REPO)} is not "
                      f"what the current editor inputs generate.")
                print("  Run tools/regenerate-level.sh (or `python3 "
                      "tools/effects_gen.py emit`) and commit the result.")
                sys.exit(1)
            print("effects_gen: OK — generated effects module matches its inputs")
        else:
            found = load_all_scenes()
            if not found:
                print("effects_gen: no editor scenes (absent directory or no "
                      ".json files)")
                sys.exit(0)
            for sid, scene in sorted(found.items()):
                print(f"effects_gen: {sid} — {len(scene['layers'])} layer(s), "
                      f"shape OK")
    except SceneShapeError as e:
        print(f"effects_gen: REFUSED — {e}")
        sys.exit(1)
