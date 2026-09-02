#!/usr/bin/env python3
"""effects_gen.py — bake Aurora-authored effect scenes into generated `.emp`.

Scanline-services **P5**. This is the aeon consumer half of the Aurora effects
contract; the NORMATIVE read set it is built to is `tools/EFFECTS_CONSUMER_CONTRACT.md`
§2 — *"P5 implements exactly this and nothing more"*. Do not grow a reader for a field
that section does not list: adding one is a CONTRACT change that amends that file and
the empyrean schema pair in the same series, and Aurora re-pins its writer golden.

TWO INPUT CLASSES, and they are not the same thing: **scene files** (§2.1, a scene IS a
`parallax_config`) and **preset documents** (§2.4, `presets/<id>.json`, whose `bands` key
lowers to a raster program). The band arm is the second one and lives further down under
its own banner; a band on a SCENE file is refused, and §2.4 carries the ruling.

What this file does, end to end: it discovers the editor scene files, refuses a
malformed one, renders each into a `scene()` / `layer()` call, reads the per-section
`sceneRef` sidecars, discovers the preset documents and lowers their bands into raster
programs, and emits the generated binding module that `act_descriptor.emp` imports. The descriptor seam is ALWAYS EMITTED — the bindings exist with no editor
content at all, which is the owner's ruling on design §9's Q-c and the reason a scene
can be added without touching the seam. `build.sh` runs `effects_gen.py check` on every
canonical build (a re-bake in memory, compared against the committed module), and
`regenerate-level.sh` bakes it; the CLI verbs are the authority on the rest.

Read the code for the schedule, not this comment. The paragraph that stood here named a
slice and an "open decision" that had both been closed for days, and because it sits at
the top of the file that IMPLEMENTS the ruling it out-argued every doc that recorded it
and propagated a refuted blocker into a cross-lane contract. A comment that dates itself
rots; the two paragraphs below do not, because they describe what the code IS.

Validation posture (scanline design §7, contract §2.1, restated because it is the whole
architecture of this tool): the generator validates **SHAPE** — schema version, id,
unknown keys — and refuses rather than guessing. Authored **VALUES** are validated by
sigil when the generated `.emp` calls the real `scene()` / `layer()` constructors, whose
`ensure` text is the v1 error surface. This tool must never grow a value check that
duplicates a constructor guard: two sources for one rule is how they drift.

WHERE THAT LINE FALLS, since it is not self-evident and one defect has already crossed
it: a TYPE is shape (`_render_int` — "you gave me a string where a bare integer literal
gets emitted"), a RANGE is value (`scene()`'s `v_factor` bound — "255 is an absurd
shift"). The type check duplicates nothing, because sigil cannot see the difference: a
string in a numeric slot lands in generated source as a bare SYMBOL, and if it resolves
— every `parallax_dsl` FACTOR_* does — it assembles green at the wrong number. A
SPELLING translation is shape too (TRANSITION_NAMES, `_render_bool_int`, `symbol_token`):
the writer's vocabulary is not the `.emp` vocabulary, and mapping between them is this
tool's job — and a value that is legal as a VALUE can still be illegal as a SYMBOL.

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
    # The vertical bob (EFFECTS-W1 item 7): two scene-level shifts, amplitude and period.
    # BOTH OPTIONAL AND BOTH OMITTED BY EVERY SAVED SCENE TODAY — the generator renders a
    # scalar only when the key is present, so `scene()`'s own defaults (bob_shift 15 = no
    # bob) are what an editor scene takes and the emitted .emp is byte-identical to what
    # it was before this key existed.
    #
    # ACCEPTED HERE AHEAD OF THE WRITER, deliberately and in the one direction that is
    # safe. empyrean's AURORA_EFFECTS_SCHEMA is the JSON surface's authority and is not
    # this repo's to edit, so Aurora cannot emit these yet; without the two names in this
    # set, the day it does, every saved scene in the tree is REFUSED with "unknown key"
    # and the editor stops round-tripping. Accepting a key the writer does not yet send
    # costs nothing and refuses nothing. (The reverse — a writer key this generator does
    # not know — is exactly the `precision` situation documented under
    # SCENE_IGNORED_KEYS.) The schema row is booked in docs/DEFERRED_WORK.md.
    "bob_shift", "bob_period",
    "deform_fg", "deform_bg", "v_deform",
    "anchor", "left_column_mask", "transition", "budget_class",
})

# Accepted and deliberately IGNORED. `name` is the one writer-only field in the
# format: a display label Aurora owns. The contract says the generator "ignores it
# and MUST keep ignoring it", so it is neither read nor refused.
#
# `precision` is RETIRED ON THE ENGINE SIDE (2026-08-26, owner ruling d-29-corrected):
# the per-cell HScroll path it selected between was deleted, the fill is per-line for
# every scene, and `scene()` no longer takes the argument. Aurora's schema (wave 1)
# still spells the field, and Aurora is not this repo's to edit — so the generator
# ACCEPTS the key and IGNORES its value, whatever it is, rather than refusing files
# that carry it. Its removal from the schema is Aurora's (booked in
# docs/DEFERRED_WORK.md, "Per-cell HScroll fill — DELETED"); when that lands this
# entry moves to SCENE_REFUSED_KEYS so a stale writer is caught loudly.
SCENE_IGNORED_KEYS = frozenset({"name", "precision"})

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

# Scene-level scalars, emitted in the constructor's own argument order. Forwarded
# VERBATIM including sign: `scene()` takes a signed int for each, `v_offset` is a
# SIGNED scroll word (-32768 .. 32767, stored as i16 and two's-complement encoded
# into the u16 config word by scene_hdr()) and `v_center` is a world Y (0 .. $7FFF).
# Both ranges are `scene()`'s ensures, not this tool's — see _render_int. The only
# thing this tool owes them is to emit a negative as a negative literal.
SCENE_SCALARS = ("v_factor", "v_center", "v_offset", "v_factor_fg",
                 "bob_shift", "bob_period")
LAYER_SCALARS = ("dsa", "dsb", "phase", "enabled")

# Enum-valued scene fields: the schema spells these as lowercase strings and the
# `.emp` wants the constant. Slices 1-2 emitted the raw string, which would have
# generated `precision: cell` — a sigil unknown-symbol error pointing at generated
# code, for a scene the author spelled exactly right. (`precision` itself is retired
# and ignored since 2026-08-26 — see SCENE_IGNORED_KEYS — so the lesson now lives on
# `transition` and `left_column_mask`.)
TRANSITION_NAMES = {"smooth": "TRANS_SMOOTH", "instant": "TRANS_INSTANT"}
LEFT_COL_MASK_NAMES = {
    "undeclared": "SceneLeftColMask.Undeclared",
    "sprite_mask": "SceneLeftColMask.SpriteMask",
    "factor0_lock": "SceneLeftColMask.Factor0Lock",
    "accept": "SceneLeftColMask.Accept",
    # d-50 (2026-09-02): the arm that turns the column-19 borrow OFF on one scene. It is
    # the only left_column_mask value that changes emitted bytes -- it ORs $80 into
    # pcfg_v_deform_shift_bg -- so an editor writing this key is moving the ROM, not
    # annotating it. The editor half is NOT built yet; this entry is what the day it lands
    # will need, and until then no scene JSON spells it.
    "decline_borrow": "SceneLeftColMask.DeclineBorrow",
}

# A MIRROR of engine/system/constants.emp's `MAX_PARALLAX_BANDS`, and it was unpinned
# until the band-count-range parcel: nothing compared the two, so this could drift from
# the engine silently in either direction. tools/test_scene_band_shape_coverage.py now
# reads the engine constant and pins this against it.
MAX_PARALLAX_BANDS = 16

# =============================================================================
# RASTER BANDS — the preset-document arm (contract §2.4).
# =============================================================================
#
# A BAND IS NOT A SCENE FIELD, AND THAT IS A RULING, NOT A PREFERENCE. The parcel that
# built this arm was dispatched to put the band on the scene file. It is not there, and
# the two reasons are both written down at committed revisions rather than reasoned out
# here:
#
#   1. `docs/superpowers/specs/2026-08-28-raster-band-ownership-design.md` §16.1 — "A
#      scene IS a `parallax_config`. It is not an effects bundle. The palette, the palette
#      cycle, the variants and *the raster program* are channels of an `EffectsPreset`,
#      and an `EffectsPreset` is bound per SECTION, never per scene." Its closing line is
#      addressed to exactly this reader: "'put a band in a scene' is not a thing you can
#      do."
#   2. `empyrean` origin/main `docs/AURORA_EFFECTS_SCHEMA.md` §7 already RESERVES the
#      right place: `games/sonic4/data/editor/effects/presets/` — "preset composition
#      documents" — for "raster preset composition (tint bands, vscroll splits, …)". A
#      band field on the scene file would have contradicted a reservation the suite had
#      already committed to.
#
# So the input is a PRESET DOCUMENT in the reserved directory, and a scene file that
# carries a band key is refused by the scene loader's ordinary unknown-key path.
#
# WHAT IT LOWERS TO, and where each half's guards live:
#
#     const EditorRasterSrc_OJZ_Act1_x = compose([ band(top: .., bot: .., on: .., sh: ..) ])
#     pub data EditorRaster_OJZ_Act1_x: [u16; raster_words(EditorRasterSrc_OJZ_Act1_x)]
#                                     = raster_program(EditorRasterSrc_OJZ_Act1_x)
#
# The `pub data` is what puts words in the ROM, and it is also what makes every guard in
# `engine/effects/raster_dsl.emp` a REAL error surface for authored content: a data item
# in a lowered module is elaborated unconditionally, so `band()`, `stream_cram()`,
# `fire()`, `compose()`, `raster_program()` and the ownership walks all run on the
# author's numbers (docs/EMP_PITFALLS.md §3 is about the module that is NOT lowered; this
# one is — `act_descriptor.emp` imports its bindings).
#
# NOT ONE NUMERIC BOUND IS RESTATED HERE. That is the whole design of this arm and it is
# checkable by reading it: there is no screen-line range, no CRAM address range, no burst
# ceiling, no band count, no height minimum, and no palette-line-0 rule anywhere in this
# file. Every one of them exists as an `ensure` in `raster_dsl.emp` with a paragraph of
# measurement behind it, and a copy down here is a copy that drifts (the module docstring's
# SHAPE-vs-VALUE paragraph is the standing rule; `MAX_PARALLAX_BANDS` above is the one
# mirror this file carries, and it exists only because the generator PADS an array to that
# width and would run off the end before the engine could speak). A band list is passed
# straight through to `compose`, so nothing here has to know how many is too many.
#
# ZERO BYTES UNTIL A PRESET DOCUMENT EXISTS. With no `presets/` directory the emitted
# module is BYTE-IDENTICAL to what it was before this arm existed — not "unchanged in
# effect", literally the same text: nothing below appends so much as a comment line when
# `presets` is empty, which is what makes the four-CRC check a real check rather than a
# ritual.
PRESET_SUBDIR = "presets"

# --- contract §2.4, top level -------------------------------------------------
PRESET_KEYS = frozenset({"schema", "id", "bands"})

# `name` for the scene files' reason: a writer-owned display label.
PRESET_IGNORED_KEYS = frozenset({"name"})

# The rest of empyrean §7's reserved wave-2 vocabulary. These are NOT unknown keys — they
# are names the suite has agreed on and this generator has not built — so they get a
# refusal that says which, rather than the generic "unknown key" sentence that would send
# an author to file a contract change for a field the contract already reserves.
PRESET_REFUSED_KEYS = {
    "fires": "a reserved wave-2 preset key (empyrean AURORA_EFFECTS_SCHEMA.md §7) that "
             "this generator does not implement. Only `bands` is built: a band lowers to "
             "the two or three fires band() derives, and a general fire list would need "
             "the vscroll/register/patchable vocabulary as well",
    "variants": "a reserved wave-2 preset key (empyrean AURORA_EFFECTS_SCHEMA.md §7) — "
                "palette variants are a different EffectsPreset channel and this "
                "generator does not implement them",
    "cycles": "a reserved wave-2 preset key (empyrean AURORA_EFFECTS_SCHEMA.md §7) — "
              "palette cycling is a different EffectsPreset channel and this generator "
              "does not implement it",
}

# --- contract §2.4, per band ---------------------------------------------------
# ALL FOUR REQUIRED, IN `band()`'s OWN ARGUMENT ORDER. `sh` has no default here because it
# has none in the engine either, and raster_dsl.emp says why at `region_boundary`: "whether
# an effect changes a mode register is worth stating at the call site". Giving it a default
# in the JSON would restore exactly the silence that ruling removed.
BAND_KEYS = ("top", "bot", "on", "sh")

# The ON op's legal arms: JSON spelling -> (the `.emp` constructor, its parameters IN THE
# CONSTRUCTOR'S ORDER). A SPELLING table, like FACTOR_NAMES: it exists so a typo'd arm is a
# generator refusal naming the legal ones instead of a sigil "unknown function" pointing at
# generated code. The authority is raster_dsl.emp.
#
# WHY `pal_region` TAKES `addr` EXPLICITLY rather than deriving it from pal_line/entry the
# way `fx_tint_band` does: that derivation is a formula, and a copy of it here would be a
# second source for it (raster_dsl holds its own copy against `pal_stage_off` with a
# module-level ensure — this file has no such pin available). Spelled out, the address and
# the staging coordinates arrive at `stream_pal_region`, whose three agreement ensures
# refuse a mismatch with the engine's own sentence. Two facts, checked against each other,
# beats one fact computed twice.
#
# `stream_vsram` is deliberately ABSENT: `band()` refuses a VSRAM ON op ("the ON op has no
# CRAM span"), so an arm for it would exist only to be refused one layer down.
BAND_ON_ARMS = {
    "cram":       ("stream_cram",       ("addr", "colours")),
    "pal_region": ("stream_pal_region", ("addr", "slot", "pal_line", "entry", "count")),
}

# Arm fields that are JSON ARRAYS of integers rather than scalars.
BAND_ON_ARRAY_FIELDS = frozenset({"colours"})


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


def preset_dir(game: str = "sonic4", repo: str = REPO) -> str:
    """The reserved wave-2 preset-document directory (empyrean schema doc §7)."""
    return os.path.join(scene_dir(game, repo), PRESET_SUBDIR)


def discover_preset_files(game: str = "sonic4", repo: str = REPO):
    """Preset documents, sorted by id. An ABSENT directory means 'no presets'.

    Same permissiveness as `discover_scene_files`, for the same contract §3 reason and
    with the same limit: absent is fine, unreadable is not. Today this directory does
    not exist in the tree at all, which is why adding this arm moves no bytes.
    """
    d = preset_dir(game, repo)
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, n) for n in os.listdir(d) if n.endswith(".json")
    )


def load_preset(path: str) -> dict:
    """Load and SHAPE-validate one preset document. Raises on anything malformed.

    SHAPE ONLY, and the line falls exactly where `load_scene`'s does: this function asks
    "is `top` an integer" and never "is 240 a legal screen line" — `fire()` owns that, and
    says so in a sentence with the priming records in it. The one place it looks like a
    value check is the empty-`bands` refusal, which is the `layers` precedent: an authored
    document with no content in it is a SHAPE fact about the document, and the engine's
    backstop (`compose: nothing to compose`) would name a function the author never wrote.
    """
    with open(path, "r") as f:
        preset = json.load(f)

    if not isinstance(preset, dict):
        _refuse(path, f"top level must be a JSON object, got {type(preset).__name__}")

    if "schema" not in preset:
        _refuse(path, "no `schema` key. Every preset document declares its schema "
                      f"version; this generator accepts {SCHEMA_VERSION}.")
    if preset["schema"] != SCHEMA_VERSION:
        _refuse(path, f"`schema` is {preset['schema']!r}, this generator implements "
                      f"{SCHEMA_VERSION}. Refusing rather than guessing at a version it "
                      f"was not built against.")

    stem = os.path.splitext(os.path.basename(path))[0]
    if "id" not in preset:
        _refuse(path, f"no `id` key (expected `{stem}`, matching the filename stem)")
    if preset["id"] != stem:
        _refuse(path, f"`id` is {preset['id']!r} but the filename stem is {stem!r}. "
                      f"They must match: the id becomes a generated symbol component "
                      f"and the filename is how a human finds the file.")
    if not SCENE_ID_RE.match(stem):
        _refuse(path, f"id {stem!r} is not symbol-safe. Preset ids become `.emp` label "
                      f"components (`EditorRaster_OJZ_Act1_<id>`), so they must match "
                      f"{SCENE_ID_RE.pattern} (lowercase, digits and underscore; no "
                      f"hyphens, no leading digit).")

    _check_keys(path, preset, PRESET_KEYS, PRESET_IGNORED_KEYS, PRESET_REFUSED_KEYS,
                "preset")

    if "bands" not in preset:
        _refuse(path, "no `bands` key. `bands` is the only channel this generator "
                      "implements; the other names empyrean's schema doc §7 reserves "
                      "(`fires`, `variants`, `cycles`) are refused by name above.")
    bands = preset["bands"]
    if not isinstance(bands, list):
        _refuse(path, f"`bands` must be a list, got {type(bands).__name__}")
    if not bands:
        _refuse(path, "`bands` is empty. A preset document with no bands would lower to "
                      "`compose([])` and then to an EMPTY raster program, which the "
                      "engine refuses one layer down with a message about `compose` "
                      "rather than about this file — and a document that emits a "
                      "zero-band program is a document that should not exist. If the "
                      "intent is 'no raster here', delete the file.")

    for i, band in enumerate(bands):
        if not isinstance(band, dict):
            _refuse(path, f"bands[{i}] must be an object, got {type(band).__name__}")
        _check_keys(path, band, frozenset(BAND_KEYS), frozenset(), None, f"bands[{i}]")
        for required in BAND_KEYS:
            if required not in band:
                _refuse(path, f"bands[{i}] has no `{required}`. A band is exactly "
                              f"{', '.join(BAND_KEYS)} — all four, none with a default. "
                              f"`sh` has none in the engine either: raster_dsl.emp's "
                              f"`region_boundary` note is that whether an effect changes "
                              f"a mode register is worth stating at the call site.")

    return preset


def load_all_presets(game: str = "sonic4", repo: str = REPO) -> dict:
    """All preset documents for a game, keyed by id. Empty dict when none exist."""
    presets = {}
    for path in discover_preset_files(game, repo):
        preset = load_preset(path)
        if preset["id"] in presets:
            _refuse(path, f"duplicate preset id {preset['id']!r}")
        presets[preset["id"]] = preset
    return presets


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
        s1, s2, op = (_render_int(path, value[k], f"{where}.{k}")
                      for k in ("s1", "s2", "op"))
        return f"packed(s1: {s1}, s2: {s2}, op: {op})"
    _refuse(path, f"{where}: factor must be a FACTOR_* name or a {{s1, s2, op}} "
                  f"object, got {type(value).__name__}")


def _render_int(path: str, value, where: str) -> str:
    """A slot that becomes an INTEGER LITERAL in the generated `.emp`.

    THIS IS A SHAPE CHECK AND NOT A VALUE CHECK, and the distinction is the whole
    reason it is allowed to exist here: it says "this must be a number" and says
    NOTHING about which numbers are legal. The ranges belong to `scene()` / `layer()`
    (see the SHAPE-vs-VALUE paragraph in this module's docstring); a bound copied down
    here would be the second source that drifts.

    THE DEFECT IT EXISTS FOR. Every scalar slot is interpolated verbatim into
    generated source, so a STRING there does not become a quoted value — it becomes a
    bare SYMBOL. Aurora's new-scene default for `v_factor` is the string `"FACTOR_0"`,
    and `FACTOR_0` is `parallax_dsl`'s PACKED HORIZONTAL factor (`FACTOR_LOCKED` =
    `$0FF` = 255), while `sc_v_factor` is a RAW SHIFT whose lock sentinel is 15. Two
    namespaces, one field name. Because `parallax_dsl` is a sigil COMPTIME_HELPERS
    member and is glob-injected into every module, that name RESOLVES wherever the
    generated scene lands — and 255 fits the `u8`, so nothing downstream objects. The
    scene assembles green with a number nobody authored.

    `bool` is refused on purpose: `isinstance(True, int)` is true in Python, and
    `f"{True}"` interpolates as the bare word `True`, which is not an `.emp` integer.
    `enabled` is the one field the writer schema genuinely spells as a boolean, and it
    is TRANSLATED by `_render_bool_int` below rather than passed through here.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        _refuse(path, f"{where}: expected an integer, got {type(value).__name__} "
                      f"{value!r}. This slot is interpolated verbatim into generated "
                      f"`.emp` as a bare integer literal, so a non-integer lands "
                      f"there as a SYMBOL rather than a number — and a symbol that "
                      f"happens to resolve (every parallax_dsl FACTOR_* does; they "
                      f"are glob-injected into every module) assembles silently with "
                      f"a value nobody authored. Whether the number is in RANGE is "
                      f"the constructor's question, not this tool's.")
    return str(value)


def _render_bool_int(path: str, value, where: str) -> str:
    """`enabled` — the one field the writer spells as a JSON boolean.

    Read from the WRITER's own schema rather than inferred from our field list
    (empyrean `contract/schema/aurora-effects-scene.schema.json`, `$defs.layer.enabled`
    = `{"type": "boolean", "default": true}`), while `layer()` takes `enabled: int = 1`
    (`engine/level/scene_dsl.emp`). Passing the JSON value straight through emits the
    bare words `True` / `False` into `.emp` — the same class of defect as slices 1-2
    emitting `precision: cell`, and the same fix: translate the writer's spelling
    instead of forwarding it. This is the cross-repo lesson the ATTACH_NONE block
    records, applied to the second field it bites.

    An integer is accepted as a synonym, for ATTACH_NONE's reason: unambiguous, costs
    nothing, and it is what a hand-written fixture spells.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    return _render_int(path, value, where)


def symbol_token(value: int) -> str:
    """An INTEGER that becomes a component of an `.emp` SYMBOL, not of a value.

    THE THIRD INSTANCE OF THE CLASS `_render_bool_int` and the enum-name tables are the
    first two of: a legal JSON value rendered into an illegal `.emp` token. A table
    generator's parameters name its dedup key AND its emitted label
    (`EditorDeform_sine_8_32`), and `str(-8)` is `-8` — a `-` is not legal in a symbol,
    so a scene the author spelled exactly right died as a sigil parse error pointing at
    generated code. The engine accepts negatives here (measured 2026-08-25: no
    TABLE_GENERATOR carries a sign `ensure`; an inverted sine or an opposite tilt is a
    meaningful table), so this is a LIVE emission path and the token must EXIST, not
    be refused.

    Spelling: a negative renders as `m<abs>` (`-8` -> `m8`); a non-negative renders as
    its digits, byte-for-byte what it was before this helper, so every existing label is
    unchanged. `m` cannot collide with a non-negative rendering because those are digits
    only, and it is injective over sign because `-0` IS `0`. The joiner is `_`, which is
    why `_` is not the marker. The VALUE handed to the constructor is never this token —
    the call site still spells the true signed literal, so an engine guard fires with the
    engine's message.

    Labels are the GENERATOR's own domain. This is not a value rule, so it does not
    add a second owner to any constructor bound (the da43a036 ruling).
    """
    return f"m{-value}" if value < 0 else str(value)


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
        self._by_key = {}    # canonical key -> label name
        self._by_label = {}  # label name -> canonical key (the injectivity check)
        self._decls = []     # (label, initializer) in first-seen order

    def intern(self, key: str, label: str, initializer: str, path: str = "?") -> str:
        """Key and label must agree on identity. Two DIFFERENT keys folding to ONE
        label would emit two declarations under one symbol — a duplicate-symbol error
        in generated code, for two tables the author named apart (the `bin` fold
        `[^a-z0-9]+ -> _` is lossy: `a-b.bin` and `a_b.bin`). Refused here, at the
        one seam every table passes, naming both."""
        if key not in self._by_key:
            other = self._by_label.get(label)
            if other is not None and other != key:
                _refuse(path, f"tables {other!r} and {key!r} would both emit under "
                              f"one label `{label}` — the label fold is not "
                              f"injective over these two spellings. Rename one so "
                              f"they fold apart.")
            self._by_key[key] = label
            self._by_label[label] = key
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
        return tables.intern(f"bin:{rel}", label, f'embed("{embed_path}")', path)

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
    # The CALL carries the true signed literal (shape-checked, value left to the
    # engine); the key and the label carry the symbol-safe token of the same int.
    rendered = [_render_int(path, v, f"{where}.{gen}.{p}")
                for p, v in zip(params, values)]
    tokens = [symbol_token(v) for v in values]
    args = ", ".join(f"{p}: {v}" for p, v in zip(params, rendered))
    key = f"{gen}:" + ",".join(tokens)
    label = "EditorDeform_" + gen + ("_" + "_".join(tokens) if tokens else "")
    return tables.intern(key, label, f"{fn}({args})", path)


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
    # fields[0] is the tableRef; everything after it is a bare integer payload slot.
    rest = ", ".join(_render_int(path, v, f"{where}.{key}.{arm}.{f}")
                     for f, v in zip(fields[1:], vals[1:]))
    return f"{variant}({label}" + (f", {rest}" if rest else "") + ")"


def render_curve(path: str, value, where: str) -> str:
    """`{"to": <factor>}` → `SceneCurve.To(<factor>)`. The payload is a packed factor."""
    to = _single_arm(path, value, "to", where)
    return f"SceneCurve.To({render_factor(path, to, where + '.to')})"


def render_vsplit(path: str, value, where: str) -> str:
    """`{"at": <int>}` → `SceneVSplit.At(<int>)`.

    The integer check was this file's FIRST one, written inline before the hole was
    understood to be general; it now defers to `_render_int` so there is one rule
    rather than one precedent and seven slots that never got it.
    """
    at = _single_arm(path, value, "at", where)
    return f"SceneVSplit.At({_render_int(path, at, where + '.at')})"


def render_anchor(path: str, value, where: str) -> str:
    """`{"at": {channel, dsa, dsb}}` → `SceneAnchor.At(channel, dsa, dsb)`."""
    at = _single_arm(path, value, "at", where)
    if not isinstance(at, dict):
        _refuse(path, f"{where}.at: must be an object with channel/dsa/dsb, got "
                      f"{type(at).__name__}")
    vals = _fields(path, at, ("channel", "dsa", "dsb"), where + ".at")
    ch, dsa, dsb = (_render_int(path, v, f"{where}.at.{f}")
                    for f, v in zip(("channel", "dsa", "dsb"), vals))
    return f"SceneAnchor.At({ch}, {dsa}, {dsb})"


def _render_enum(path: str, value, table: dict, where: str) -> str:
    """A lowercase schema enum string → its `.emp` constant."""
    if value not in table:
        _refuse(path, f"{where}: {value!r} is not a legal value. One of: "
                      f"{', '.join(sorted(table))}.")
    return table[value]


def render_layer(path: str, layer: dict, where: str,
                 tables: TableRegistry) -> str:
    args = [f"world_y: {_render_int(path, layer['world_y'], where + '.world_y')}",
            f"fa: {render_factor(path, layer['fa'], where + '.fa')}",
            f"fb: {render_factor(path, layer['fb'], where + '.fb')}"]
    for key in LAYER_SCALARS:
        if layer.get(key) is not None:
            render = _render_bool_int if key == "enabled" else _render_int
            args.append(f"{key}: {render(path, layer[key], f'{where}.{key}')}")
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

    Deliberately returns TEXT and writes nothing.

    WHY THE SEAM IS ALWAYS EMITTED, restated here because this is the function whose
    output depends on it: an UNREACHED `.emp` module gets zero body elaboration, so
    `ensure(1 == 0)` inside one builds green. A generated module nothing imports would
    look finished while validating nothing — the failure this pipeline is least able to
    notice. That is the reason the descriptor binding exists with no editor content at
    all rather than appearing with the first scene, and it is why the `scene()` /
    `layer()` guards are a REAL error surface for this text rather than an aspirational
    one. (This paragraph used to say the module "is not wired into the build until the
    descriptor import seam exists". It does exist; the sentence was the same rot the
    module docstring now warns about, and it was the one that would tell a reader their
    constructor guards do not run.)
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
    # The array is ALWAYS MAX_PARALLAX_BANDS slots, padded with no_layer() — the
    # hand-authored idiom (games/sonic4/data/effects/ojz_scenes.emp) and what scene()
    # indexes. Sixteen since 2026-08-27; the generator has always derived the width from
    # the mirror below, so the raise cost this function nothing.
    rendered += ["no_layer()"] * (MAX_PARALLAX_BANDS - len(rendered))

    body = ["    layers: [ " + ",\n              ".join(rendered) + " ]",
            f"    count: {len(layers)}"]
    for key in SCENE_SCALARS:
        if scene.get(key) is not None:
            body.append(f"    {key}: "
                        + _render_int(path, scene[key], f"scene.{key}"))
    # Enum-valued fields: lowercase schema strings, `.emp` constants. (`precision` is
    # accepted and ignored — SCENE_IGNORED_KEYS — and is never rendered.)
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


def render_band_on(path: str, value, where: str) -> str:
    """One band's ON op → its `.emp` constructor call.

    Single-armed like the scene attachments, but over TWO legal arms rather than one, so
    it cannot reuse `_single_arm` (whose whole shape is "the only arm here is `x`").
    """
    if not isinstance(value, dict):
        _refuse(path, f"{where}: the ON op must be an object with exactly one of "
                      f"{', '.join(sorted(BAND_ON_ARMS))}, got "
                      f"{type(value).__name__}")
    arms = sorted(set(value) & set(BAND_ON_ARMS))
    extra = sorted(set(value) - set(BAND_ON_ARMS))
    if extra:
        _refuse(path, f"{where}: unknown ON-op arm(s) {', '.join(extra)}. The legal arms "
                      f"are {', '.join(sorted(BAND_ON_ARMS))} — the two raster_dsl stream "
                      f"constructors that carry a CRAM span. `vsram` is absent on "
                      f"purpose: band() refuses a VSRAM ON op, because a band's restore "
                      f"is DERIVED from the ON op's CRAM span and a VSRAM op has none.")
    if len(arms) != 1:
        _refuse(path, f"{where}: an ON op is exactly ONE arm, got "
                      f"{', '.join(arms) or '(none)'}. Two arms would be two writes and "
                      f"therefore two restores, which is two bands.")
    arm = arms[0]
    fn, fields = BAND_ON_ARMS[arm]
    body = value[arm]
    if not isinstance(body, dict):
        _refuse(path, f"{where}.{arm}: must be an object with "
                      f"{', '.join(fields)}, got {type(body).__name__}")
    vals = _fields(path, body, fields, f"{where}.{arm}")
    args = []
    for field, v in zip(fields, vals):
        if field in BAND_ON_ARRAY_FIELDS:
            if not isinstance(v, list):
                _refuse(path, f"{where}.{arm}.{field}: must be a list of integers, got "
                              f"{type(v).__name__}. It becomes an `.emp` array literal, "
                              f"and how many entries are legal is "
                              f"{fn}'s question — see its burst-ceiling ensure.")
            items = ", ".join(_render_int(path, c, f"{where}.{arm}.{field}[{j}]")
                              for j, c in enumerate(v))
            args.append(f"{field}: [{items}]")
        else:
            args.append(f"{field}: "
                        + _render_int(path, v, f"{where}.{arm}.{field}"))
    return f"{fn}(" + ", ".join(args) + ")"


def render_band(path: str, band: dict, where: str) -> str:
    """One authored band → its `band(top:, bot:, on:, sh:)` call.

    Every number here is forwarded VERBATIM. Whether `top` is a legal screen line, whether
    the band is tall enough for its ON op's measured cost, whether the ON op's colours fit
    the burst window, whether the CRAM address is on the character's palette line — all
    four are `raster_dsl.emp` ensures with measurements behind them, and none of them is
    repeated here. REFUSE, DON'T CLAMP is therefore automatic for the ranges: this
    function has no range to clamp against.
    """
    return ("band(top: " + _render_int(path, band["top"], where + ".top")
            + ", bot: " + _render_int(path, band["bot"], where + ".bot")
            + ", on: " + render_band_on(path, band["on"], where + ".on")
            + ", sh: " + _render_bool_int(path, band["sh"], where + ".sh")
            + ")")


def render_preset(path: str, preset: dict, names) -> str:
    """One preset document → the two declarations that put its program in the ROM.

    `compose([...])` even for a single band, which is the shipped hand idiom
    (`OJZ_BandDemo`) and not decoration: compose is what merges two bands that share a
    line and what enforces the ascending order `fire_lines` requires, so a one-band
    program that skipped it would take a different path through the encoder than a
    two-band one — the last thing a generator wants is for band count to change the
    lowering shape.

    The `const` half is REFERENCED TWICE below and that is load-bearing: an unreferenced
    top-level `const X = f(..)` is comptime-INERT and would fold nothing
    (docs/EMP_PITFALLS.md §3, the same trap `scene_budget_enforce`'s reference exists for).
    Here `raster_words()` and `raster_program()` both name it, so both folds run and every
    guard inside them fires on the authored numbers.
    """
    pid = preset["id"]
    src, label = names.raster_src(pid), names.raster(pid)
    bands = [render_band(path, b, f"bands[{i}]")
             for i, b in enumerate(preset["bands"])]
    return (f"const {src} = compose([\n    "
            + ",\n    ".join(bands) + ",\n])\n"
            + f"pub data {label}: [u16; raster_words({src})] = raster_program({src})")


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
# ---- THE map.toml ROW — SETTLED, and this paragraph used to say otherwise ----
#
# CORRECTED 2026-08-29. What stood here said "no `order` row is authored for this module's
# section … map.toml carries a reserved-slot COMMENT instead of a guessed row." That has
# been false since Aurora's first saved scene made the block emit (2026-08-26):
# `games/sonic4/map.toml` carries `"section:ojz_effects_editor_act1"`, a SECTION-NAME row,
# which resolves to the section's head label at placement time. The name row is the answer
# to the problem the old paragraph correctly identified — sigil keys the order check on the
# lowest-offset label, and this block's head label is CONTENT-DERIVED (whatever the
# generator emits first, which changes as scenes, deform tables and now raster programs come
# and go) — so a LABEL row would rot with content and the NAME row does not.
#
# The consequence for anyone extending this generator, which is why the correction matters:
# NEW BYTE-EMITTING CONTENT IN THIS MODULE NEEDS NO map.toml EDIT. The raster-band arm below
# was written against this file, and the stale paragraph would have sent its author to
# invent a placement problem that had already been solved.

ACT_SCENE_REF_KEY = "sceneRef"
# THE RASTER BINDING KEY, AND THIS LINE IS THE ONLY PLACE THE WIRE SPELLING IS WRITTEN.
#
# Adjudicated by the empyrean CR (docs/2026-08-30-effectsref-contract-change.md), carried
# at empyrean da91abce as OPTION B: a NEW key takes the narrow raster-channel binding and
# `effectsRef` stays reserved, unspent, for the total binding it was named for. Option A
# (narrow `effectsRef` in place) was refused because it leaves a name outliving its
# meaning; option C (grow the preset document to total) because it makes this arm depend
# on DoD item 5 and inverts the ratified sequence.
#
# NOTHING ELSE IN THE TREE HARDCODES IT. The sidecar reader, the resolution error, the
# tests, tools/effects_seam_gate.py and tools/test_raster_cycle_table_lint.py all read
# THIS constant, so a re-spelling is a one-line change. That property is load-bearing and
# not decoration: this key spent a day un-adjudicated with an arm being built against it.
ACT_RASTER_REF_KEY = "rasterRef"
PROJECT_JSON = "project.json"


def _act_entry(repo: str = REPO, zone: int = 0, act: int = 0) -> dict:
    """The project.json act entry. Bare load + direct subscripting (contract §3)."""
    with open(os.path.join(repo, PROJECT_JSON), "r") as f:
        project = json.load(f)
    return project["zones"][zone]["acts"][act], project["zones"][zone]


def _scene_ref(path: str, value, where: str, key: str = ACT_SCENE_REF_KEY):
    """One sidecar/project ref value → an id string, or None for absent.

    Contract §2.2, stated in the contract's own words: "`sceneRef` is a string id or
    null, NEVER a numeric index" — because AURORA's parser nulls a non-string
    SILENTLY (`section-meta.ts:29-30`), so `sceneRef: 3` presents as "the assignment
    didn't stick". The generator refuses it instead: the one writer that can still
    see the mistake is the build.

    `key` IS A PARAMETER AND NOT A LITERAL because `rasterRef` reuses this validator
    whole — same shape, same id regex, same numeric ban, same reason — and the empyrean
    §3.1 obligation is that a refusal names the key it refused. A shared message that
    said "sceneRef" while refusing a `rasterRef` would send the author to the wrong
    line of the wrong file.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        _refuse(path, f"{where}: {key} must be an id STRING or null, got "
                      f"{type(value).__name__} ({value!r}). A numeric index is "
                      f"refused on purpose — Aurora's sidecar parser nulls a "
                      f"non-string value silently, so this would present as an "
                      f"assignment that did not stick.")
    if not SCENE_ID_RE.match(value):
        _refuse(path, f"{where}: {key} {value!r} is not a legal id "
                      f"({SCENE_ID_RE.pattern}) — ids become `.emp` symbol "
                      f"components.")
    return value


def _load_section_refs(key: str, repo: str = REPO, zone: int = 0,
                      act: int = 0) -> dict:
    """`{section_index: id}` for ONE sidecar ref key.

    THE MISSING/UNREADABLE SPLIT IS THE POINT (contract §2.2/§3). A sidecar that is
    absent is all-refs-null — Aurora only writes one when a ref is non-null, so the
    all-default act legitimately has no file on disk. A sidecar that EXISTS but does
    not parse fails the bake loudly: "degrade gracefully" must not collapse those
    two, because all-null is exactly the state that triggers Aurora's destructive
    cleared-overwrite.

    SHARED RATHER THAN COPIED, and that is the point of the shape. `rasterRef` and
    `sceneRef` differ in exactly one thing — which key they pull — and the split above
    is the part that is easy to get subtly wrong. A near-copy would let the two readers
    drift on the failure that has no symptom.

    NO UNKNOWN-KEY CHECK IS APPLIED HERE, deliberately and by ruling (empyrean §3.1):
    the sidecar is Aurora's document and it will grow keys this generator does not read.
    `_check_keys` guards the scene and preset DOCUMENTS, where a stray key is an author's
    typo; here it would make every future Aurora key a build break.
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
        ref = _scene_ref(path, meta.get(key), f"section {i}", key)
        if ref is not None:
            out[i] = ref
    return out


def load_section_scene_refs(repo: str = REPO, zone: int = 0, act: int = 0) -> dict:
    """`{section_index: scene_id}` from the per-section sidecars."""
    return _load_section_refs(ACT_SCENE_REF_KEY, repo, zone, act)


def load_section_raster_refs(repo: str = REPO, zone: int = 0, act: int = 0) -> dict:
    """`{section_index: preset_id}` from the per-section sidecars.

    The raster half of §2.2's assignment set: a section names one Aurora-authored PRESET
    DOCUMENT and gets that document's raster program on its `preset()` call's `raster:`
    channel. Absent / null = "this section keeps its hand-authored raster channel", which
    is the majority case and the reason this arm can cost nothing (design §3.4).
    """
    return _load_section_refs(ACT_RASTER_REF_KEY, repo, zone, act)


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
        # The same JSON->symbol seam as scene ids, for the one writer-owned pair of
        # ids the scene regex did not already cover (`ojz-1` would land in a label and
        # a module name; `1ojz` in a leading digit; a capital in a case-folded twin).
        for what, value in (("zone", zone_id), ("act", act_id)):
            if not isinstance(value, str) or not SCENE_ID_RE.match(value):
                _refuse(PROJECT_JSON, f"{what} id {value!r} is not symbol-safe "
                                      f"({SCENE_ID_RE.pattern}) — project ids become "
                                      f"`.emp` symbol components (EditorScenes_*, the "
                                      f"generated module name).")
        self.zone_id, self.act_id = zone_id, act_id
        stem = f"{zone_id}_{act_id}"                      # ojz_act1
        cap = f"{zone_id.upper()}_{act_id.capitalize()}"  # OJZ_Act1
        self.cap = cap
        self.module = f"games.sonic4.{zone_id}_effects_editor_{act_id}"
        self.section = f"{zone_id}_effects_editor_{act_id}"
        self.fn_act_default = f"{stem}_act_default"
        self.fn_sec_scene = f"{stem}_sec_scene"
        self.fn_sec_raster = f"{stem}_sec_raster"
        self.binding_default = f"EditorSceneBinding_{cap}_Default"
        self.scene_array = f"EditorScenes_{cap}"
        self.equ_scenes = f"EditorScenes_{cap}_Count"
        self.equ_bindings = f"EditorScenes_{cap}_Bindings"
        # The RASTER binding witness. Capital `_Bindings` where a preset id is
        # `^[a-z]...` by SCENE_ID_RE, so it cannot collide with `raster(pid)` below —
        # the near-miss is deliberate (the prefix is what makes it read as the raster
        # channel's witness) and the regex is what makes it safe.
        self.equ_raster_bindings = f"EditorRaster_{cap}_Bindings"

    def binding_sec(self, i: int) -> str:
        return f"EditorSceneBinding_{self.zone_id.upper()}_" \
               f"{self.act_id.capitalize()}_Sec{i}"

    def raster(self, preset_id: str) -> str:
        """The emitted raster-program LABEL for one preset document.

        ACT-QUALIFIED even though preset documents are a game-level library, for the
        reason `ActNames`' own docstring gives about `bg_anim.emp`: the generator emits
        one module PER ACT, and an unqualified name would collide the day a second act's
        module renders the same library. The cost is that two acts binding the same
        preset each carry a copy of its words — visible, and cheaper to fix than a
        duplicate-symbol error nobody predicted.
        """
        return f"EditorRaster_{self.cap}_{preset_id}"

    def raster_src(self, preset_id: str) -> str:
        return f"EditorRasterSrc_{self.cap}_{preset_id}"

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
#
# DERIVED FROM THE CEILING, NOT LISTED. This used to be the literal `(1, 2, 4, 5)` — the
# counts the hand-authored scenes happened to use — which meant a writer-originated scene
# with 3, 6, 7 or 8 layers was refused despite the engine admitting it (that is exactly
# how Aurora's first writer-originated scene, an 8-layer one, was blocked). The registry
# now declares a shape for every count in 1..MAX_PARALLAX_BANDS, so the lowerable set IS
# that range, and tools/test_scene_band_shape_coverage.py holds the three mirrors
# together: engine/system/constants.emp's constant, the MAX_PARALLAX_BANDS below, and the
# `SceneCfgN`/`lowerN` pairs the registry actually declares. Move the constant and the
# gate names the shapes that went missing rather than going quietly stale.
LOWERABLE_BAND_COUNTS = tuple(range(1, MAX_PARALLAX_BANDS + 1))


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
                  names: ActNames, presets: dict = None,
                  sec_raster_refs: dict = None) -> str:
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

    # The RASTER half of the same resolution, symmetric with the scene half above by
    # construction: same class, same "names no X, here are the known ids" shape. A
    # `rasterRef` naming no document is an author's typo and the build is the last
    # place it can still be seen — after the bake it is simply a section with no band.
    raster_bound = {}                       # section index -> preset id
    for i in sorted(sec_raster_refs or {}):
        if (sec_raster_refs[i] not in (presets or {})):
            raise SceneShapeError(
                f"section_{i}.meta.json: {ACT_RASTER_REF_KEY} "
                f"{sec_raster_refs[i]!r} names no preset document in "
                f"{preset_dir()} — a {ACT_RASTER_REF_KEY} binds one Aurora-authored "
                f"preset document's raster program, so it cannot name a "
                f"hand-authored `.emp` program. Known ids: "
                f"{', '.join(sorted(presets or {})) or '(none)'}.")
        raster_bound[i] = sec_raster_refs[i]

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
        # The same imports scene_registry.emp carries, for the same reasons — see its
        # banner. `band_entry`/`band_ext`/BAND_EXT_N/`band_curve`/BAND_CURVE_N/
        # `band_drift`/BAND_DRIFT_N are load-bearing even though nothing here spells
        # them: a struct's declaration is re-elaborated in every module that imports it
        # (docs/EMP_PITFALLS.md §8), and a partial import fails pointing at
        # engine/level/parallax.emp.
        #
        # THIS LIST GROWS WITH EVERY CAPABILITY TAIL band_record COMPOSES, and the
        # generated module is the FOURTH importer — the one a mirror-set enumeration
        # written from the hand-authored sources misses, because it is not in the tree
        # until this generator writes it. Measured on the band-drift parcel: adding
        # band_drift to the three hand importers left THIS list short and the whole
        # build red with `unknown type: band_drift` pointing at parallax.emp, exactly as
        # §8 predicts. If you are adding a tail, this line is part of the parcel.
        out.append("use engine.structs.{parallax_config}")
        out.append("use engine.parallax.{band_entry, band_record, band_ext, "
                   "BAND_EXT_N, band_curve, BAND_CURVE_N, band_drift, BAND_DRIFT_N}")
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

    # ---- the raster BANDS from the preset documents ----
    # APPENDS NOTHING AT ALL when there are none — not a banner, not a blank line. That is
    # what makes "adding this capability moved zero bytes" checkable by CRC rather than
    # merely argued: with no preset documents this function returns the same TEXT it
    # returned before the arm existed, so the committed generated artifact does not even
    # have to be re-emitted.
    if presets:
        out.append(RASTER_BANNER)
        for pid in sorted(presets):
            out.append(render_preset(
                os.path.join(preset_dir(), pid + ".json"), presets[pid], names))
            out.append("")

    # ---- the witness equates (zero ROM bytes, link-visible) ----
    out.append(WITNESS_BLOCK.format(
        equ_scenes=names.equ_scenes, scenes=len(used),
        equ_bindings=names.equ_bindings,
        bindings=len(bound) + (1 if act_ref else 0),
        equ_raster_bindings=names.equ_raster_bindings,
        raster_bindings=len(raster_bound)))
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
    out.append("")
    out.append(RASTER_BINDING_BANNER)
    out.append(f"pub comptime fn {names.fn_sec_raster}(sec: int, hand: Label = 0) "
               f"-> Label {{")
    out.append(f'    ensure(sec >= 0 && sec < {sections}, "{names.fn_sec_raster}(sec: '
               f'{{sec}}): this act has {sections} sections, so there is no binding '
               f'slot for that index — the section preset and project.json\'s grid '
               f'have drifted apart")')
    out.append("    comptime var out = hand")
    for i in sorted(raster_bound):
        out.append(f"    if sec == {i} {{ out = {names.raster(raster_bound[i])} }}")
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
// THE THREE `pub comptime fn`s AT THE BOTTOM ARE EMITTED FOR EVERY ACT, ALWAYS —
// owner ruling 2026-08-22 (design §9 Q-c, the always-emitted default). With no
// editor content they return the `hand:` fallback their caller passes; with
// editor content they return the lowered record above. The caller therefore
// has ONE path, always live, and never a conditional. They are functions and not
// Labels for a measured reason: see the block comment above `render_module()` in
// tools/effects_gen.py — `pub equ` is not importable and a `pub const` carrying a
// Label fails the clone-injection re-evaluation, both verified against sigil.
//
// Placed at the `{section}` section
// (module `{module}`). Its ROM position is declared in
// games/sonic4/map.toml by SECTION NAME (`"section:{section}"`) rather
// than by label, because this block's head label is content-derived — whatever the
// generator emits first, which moves as scenes, deform tables and raster programs come
// and go. So new byte-emitting content here needs NO map.toml edit.
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
pub equ {equ_bindings} = {bindings}
pub equ {equ_raster_bindings} = {raster_bindings}\
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

RASTER_BANNER = """\
// ---- AURORA-AUTHORED RASTER BANDS, through the REAL constructors ----
//
// One `pub data` per preset document in games/sonic4/data/editor/effects/presets/. These
// are the ONLY bytes an editor-authored raster effect contributes, and the section they
// land in is declared in games/sonic4/map.toml by NAME (`"section:ojz_effects_editor_act1"`)
// precisely because its head label is content-derived — so a program appearing here needs
// no map.toml edit.
//
// A BAND IS NOT A SCENE CHANNEL. A `Scene` IS a parallax_config; the raster program is an
// EffectsPreset channel, bound per SECTION (band-ownership design §16.1). This generator
// therefore EMITS the program under a stable name and does NOT bind it: which section
// installs it is a `preset()` call in the game's own effects library, and choosing that is
// a content decision with a picture attached.
//
// Every `ensure` in band()/stream_cram()/fire()/compose()/raster_program() and both
// ownership walks fire on authored content HERE — a `pub data` in a lowered module is
// elaborated unconditionally. The generator validates SHAPE only and repeats not one of
// those bounds (tools/effects_gen.py, the RASTER BANDS banner).\
"""

BINDING_BANNER = """\
// =====================================================================
// THE SCENE BINDINGS — the seam act_descriptor.emp calls. ALWAYS BOTH, ALWAYS LIVE.
//
// `hand:` is the descriptor's own fallback, carried as a PARAMETER rather than
// named here: a comptime fn's free names resolve at the call site, so the hand
// default has to arrive from the caller — and that is the better contract anyway,
// since the descriptor keeps owning its hand bindings and this module only chooses.
// =====================================================================\
"""


RASTER_BINDING_BANNER = """\
// ---- THE RASTER BINDING — the seam the GAME'S EFFECTS LIBRARY calls ----
//
// The third always-emitted chooser, and the one that does NOT go to
// act_descriptor.emp: a raster program is an `EffectsPreset` channel, not a scene
// channel, so its call site is the section's own `preset()` in
// games/sonic4/data/effects/ojz_effects.emp — `raster: <this>(sec: N, hand: ...)`.
//
// `hand:` IS THE CALLER'S, AND ON A PATCHED SECTION IT MUST BE `0`. `preset()` asserts
// `ep_raster == 0 || ep_patched == 0` and that assert DOES read this function's result
// (measured 2026-08-30, both arms). So a section that binds `patched:` must pass
// `hand: 0`, because `Raster_Program_None` is a real non-zero label and would fire the
// exclusivity ensure for a section that bound nothing at all. Every other section
// passes `hand: Raster_Program_None`, since NULL cannot mean "off" while it also means
// "keep" (ARCH §7.12).
//
// With no `rasterRef` in any sidecar the body below is `return hand` and this whole
// block is zero ROM bytes — a `pub comptime fn` emits nothing.\
"""


def generate(repo: str = REPO, zone: int = 0, act: int = 0) -> tuple:
    """(output path, module text) for one act. Reads only; writes nothing."""
    names = act_names(repo, zone, act)
    return names.out_path(repo), render_module(
        load_all_scenes("sonic4", repo),
        load_act_scene_ref(repo, zone, act),
        load_section_scene_refs(repo, zone, act),
        act_section_count(repo, zone, act),
        names,
        load_all_presets("sonic4", repo),
        load_section_raster_refs(repo, zone, act))


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
            presets = load_all_presets()
            if not found and not presets:
                print("effects_gen: no editor scenes or preset documents (absent "
                      "directory or no .json files)")
                sys.exit(0)
            for sid, scene in sorted(found.items()):
                print(f"effects_gen: {sid} — {len(scene['layers'])} layer(s), "
                      f"shape OK")
            for pid, preset in sorted(presets.items()):
                print(f"effects_gen: preset {pid} — {len(preset['bands'])} band(s), "
                      f"shape OK")
    except SceneShapeError as e:
        print(f"effects_gen: REFUSED — {e}")
        sys.exit(1)
