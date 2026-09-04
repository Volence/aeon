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
    # EFFECTS-W1 item 10's authoring half — the reels' per-band rates. Sibling to
    # `v_deform` and NOT a layer key; the REELS banner further down carries the whole
    # account, including why it lowers into the generated module and nowhere else.
    "reels",
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
    "deform", "curve", "vsplit", "drift", "rowRemap",
})

LAYER_IGNORED_KEYS = frozenset({"name"})

# THE LADDER IS NOT SPELLED, IT IS DERIVED — and the two names for it are refused BY NAME
# rather than merely absent, because "unknown key `ladder`" would read as a typo when it is
# actually a contract question. `rowRemap` lowers to `SceneRemap.Ladder(<Label>, plane_y,
# height_shift)` and the Label is a pure function of `height_shift`: exactly one ladder
# exists, `row_remap_ladder16()` (engine/level/parallax_dsl.emp:220), and its H is the module
# const ROW_REMAP_H16 = 16 rather than a parameter. Naming it in the document would be one
# number spelled twice, which is `layer()`'s own build error at scene_dsl.emp:879 ("two
# sources for one byte is how they drift"), and it would ship a required field with one legal
# value. A named ladder is the SECOND VARIANT extension when a non-perspective ladder is
# wanted (heat haze, a mirror); a oneOf can widen where a required field cannot be taken back.
LAYER_REFUSED_KEYS = {
    "ladder": "the ladder is DERIVED from `height_shift`, not named. A named ladder is the "
              "second-variant extension and is not in this contract yet",
    "table": "the ladder is DERIVED from `height_shift`, not named. `table` is reserved for "
             "the second-variant extension (a generated non-perspective ladder) and is not "
             "in this contract yet",
}

# THE ONLY LADDER THAT EXISTS, keyed by the shift it is the ladder for. The other four legal
# shifts (3, 5, 6, 7) are refused BY NAME below until EFFECTS-W1 item 9b's generator lands:
# `layer()` accepts them (scene_dsl.emp:1006 bounds 3..7), so without this the emission would
# fail on an undefined Label and name a missing symbol instead of the authoring mistake.
ROW_REMAP_LADDERS = {4: "RowRemapLadder_Waterline16"}


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
# REELS — the scene's independently scrolling background strips (item 10, step 4).
# =============================================================================
#
# The key is `reels` on a SCENE document, and it is NOT a layer key: a reel band is
# one of five vertical COLUMN strips, while `band_record` partitions the screen into
# horizontal ROW bands. Those two share a noun and nothing else — this is the third
# meaning of "band" on this seam (`BAND_KEYS` below is the raster preset's scanline
# region, the second) and this arm adds no fourth.
#
# NORMATIVE: empyrean docs/AURORA_EFFECTS_SCHEMA.md §2.7 read at
# ff3f43f2e9c2b0b98e6c283f5cb87eb106f0fe5c. The aeon decision note it ratifies is
# docs/superpowers/specs/2026-09-04-reels-per-scene-key-shape.md.
#
# DEBUG TIER, AND THE PROHIBITION IS A PROHIBITION (CR ruling 1). Everything this arm
# emits sits inside `if DEBUG == 1`, in THIS generated module, and MUST NOT become a
# field of `Scene`, `parallax_config` or `Sec`. Any of those three puts reels bytes in
# the shipped ROM and turns an owner-free parcel into a look call — promotion is the
# owner's parked question, not this arm's. `tools/reels_gate.py --shape release`
# asserts the absence and stays green by construction.
#
# AND THE GENERATED MODULE IS NOT AN ARBITRARY CHOICE OF SITE. `tools/reels_gate.py`
# is ADJACENCY-COUPLED: it measures the table as the gap `OJZ_Reel_Speed` ->
# `OJZ_Reels_Fill` and the proc as `OJZ_Reels_Fill` -> `ObjDef_Static`. New
# byte-emitting content between either pair makes it raise `Unmeasurable` — not FAIL —
# so emitting these tables into games/sonic4/data/effects/ojz_effects.emp, the natural
# place beside the hand table, would silently DISARM the gate that proves the reel
# source reaches the ROM.
REELS_KEY = "reels"
REELS_RATES_KEY = "rates"

# `const REEL_BAND_COUNT = <literal>` in the game's own constants module. Same shape as
# tools/reels_gate.py's `emp_const`, and tools/test_effects_gen.py pins the two against
# each other rather than letting a second parser drift — the remedy MAX_PARALLAX_BANDS
# above needed after it spent months unpinned.
_EMP_INT_CONST = r"^\s*(?:pub\s+)?const\s+{}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)\s*(?://.*)?$"


def reel_band_count(game: str = "sonic4", repo: str = REPO) -> int:
    """REEL_BAND_COUNT, RE-DERIVED from the game's constants module — never 5.

    The schema's `minItems: 5` / `maxItems: 5` is a hardcoded COPY of an `.emp`
    constant in another repo (CR §2.7, "what the schema cannot express"). If
    REEL_BAND_COUNT ever moves, that copy is silently wrong in the permissive
    direction and the build fails much later, inside sigil, on a length the author
    never typed. So the length check the generator applies is derived from the
    declaration itself, and a declaration this function cannot find is a REFUSAL:
    reading "no bands" out of a file it failed to parse is how a length check goes
    vacuous.
    """
    path = os.path.join(repo, "games", game, "config", "constants.emp")
    try:
        with open(path, "r") as f:
            src = f.read()
    except OSError as e:
        _refuse(path, f"cannot read the game constants module to re-derive "
                      f"REEL_BAND_COUNT: {e}. The `reels` key's length check derives "
                      f"its expectation from that declaration, and a check that "
                      f"cannot run must not pass.")
    m = re.search(_EMP_INT_CONST.format(re.escape("REEL_BAND_COUNT")), src, re.M)
    if not m:
        _refuse(path, "no `const REEL_BAND_COUNT = <literal>` declaration. The "
                      "`reels` key's rate array is exactly one rate per reel band and "
                      "that count is the engine's, not the schema's — this generator "
                      "refuses rather than falling back on the 5 the schema happens "
                      "to spell today.")
    tok = m.group(1)
    return int(tok[1:], 16) if tok.startswith("$") else int(tok)


def _check_reels(path: str, scene: dict, bands: int) -> None:
    """SHAPE-validate a `reels` payload. Values are sigil's (`reel_rates_ok`).

    On the right side of the shape/value line, deliberately and per the module
    docstring's rule: a TYPE is shape, a LENGTH is shape, a RANGE is value. So the
    magnitude bound (-128..127) and pairwise distinctness are NOT checked here —
    they are `reel_rates_ok`'s ensures in games/sonic4/config/constants.emp, which
    every generated AND hand-written rate table routes through. Two sources for one
    rule is how they drift.
    """
    body = scene[REELS_KEY]
    if body is None:
        _refuse(path, f"scene.{REELS_KEY} is null. There is no `none` spelling for "
                      f"reels (CR ruling 2): the binding table is generated whole, so "
                      f"\"keep\" and \"off\" are one state and one state gets one "
                      f"spelling — OMIT the key.")
    if not isinstance(body, dict):
        _refuse(path, f"scene.{REELS_KEY} must be an object with one member "
                      f"`{REELS_RATES_KEY}`, got {type(body).__name__}")
    unknown = sorted(set(body) - {REELS_RATES_KEY})
    if unknown:
        _refuse(path, f"scene.{REELS_KEY} carries unknown member(s) "
                      f"{', '.join(repr(k) for k in unknown)}. The object is CLOSED "
                      f"and carries exactly `{REELS_RATES_KEY}`. In particular "
                      f"`cols_per_band` is refused by closure and not by oversight: "
                      f"the geometry is FIXED at "
                      f"REEL_BAND_COUNT x REEL_COLS_PER_BAND (CR ruling 5) because "
                      f"the column->band map is a hardcoded shift, not a value read "
                      f"at runtime. It is recoverable additively later.")
    if REELS_RATES_KEY not in body:
        _refuse(path, f"scene.{REELS_KEY} has no `{REELS_RATES_KEY}`. It is the "
                      f"object's one member and it has no default.")
    rates = body[REELS_RATES_KEY]
    if not isinstance(rates, list):
        _refuse(path, f"scene.{REELS_KEY}.{REELS_RATES_KEY} must be an array, got "
                      f"{type(rates).__name__}")
    for i, r in enumerate(rates):
        # `bool` is an `int` in Python and would render as `True` — a bare symbol in
        # generated source. Same trap `_render_int` carries, same exclusion.
        if isinstance(r, bool) or not isinstance(r, int):
            _refuse(path, f"scene.{REELS_KEY}.{REELS_RATES_KEY}[{i}] must be a bare "
                          f"integer, got {type(r).__name__} ({r!r}). A rate is "
                          f"SIGNED WHOLE PIXELS PER FRAME and is emitted as a bare "
                          f"`.emp` literal; anything else lands in generated source "
                          f"as a symbol.")
    if len(rates) != bands:
        _refuse(path, f"scene.{REELS_KEY}.{REELS_RATES_KEY} carries {len(rates)} "
                      f"rate(s), not one per reel band. REEL_BAND_COUNT is {bands}, "
                      f"re-derived from games/sonic4/config/constants.emp rather than "
                      f"copied from the schema's minItems — OJZ_Reels_Fill walks "
                      f"exactly that many signed bytes from whichever table it "
                      f"selected, so a short array feeds the phase accumulators "
                      f"whatever follows it in ROM.")


# --- the RUNG model: which sections a lowered config can be reached through ---
#
# THE REFUSAL THE CR ADDS (ruling 4), and it exists because the silent case is the bad
# one. The reels binding table is keyed on `Parallax_Current_Config`, the pointer the
# engine holds to the ACTIVE parallax_config. `Effects_ResolveParallax`
# (engine/effects/preset.emp) resolves that pointer through three rungs:
#
#   1. Sec.sec_parallax_config   the PER-SECTION binding — the editor's `sceneRef`,
#                                lowered by THIS generator, one `pub data` per section
#   2. EffectsPreset.ep_parallax the PRESET binding, SHARED by every section whose
#                                `preset()` names it
#   3. Act.act_parallax_config   the act default, shared by everything that falls through
#
# The pointer is a UNIQUE key only at rung 1 — which is exactly the population an
# authoring key targets, because rung 1 is what a `sceneRef` produces. A section
# resolving at rung 2 or 3 holds a pointer SHARED with other sections, so a table keyed
# on it hands those sections ANOTHER SECTION'S MOTION rather than none. That failure is
# silent: nothing errors, nothing is missing, the wrong strips simply scroll.
#
# So a `reels` key is legal only on a scene every one of whose bindings is rung 1, and
# the three arms below refuse the rest BY NAME. Not hypothetical: `d-53` gave section 5
# `ParallaxConfig_OJZ_Underwater` through rung 2, the same object `OJZ_Preset_Sec0`
# names — two sections, one pointer, in the shipped tree today.
#
# THESE SCANS RUN ONLY WHEN A SCENE AUTHORS `reels`. A tree with no reels key reads no
# `.emp` at all and is byte-identical to what it baked before this arm existed.

# A `pub data <Name>: EffectsPreset = preset(` declaration, and the `parallax:` argument
# inside one. The window is CLIPPED AT THE NEXT declaration, `walk_patch_sites`'s rule
# and for its reason: a preset with no `parallax:` of its own must not inherit the next
# preset's.
_PRESET_DECL = re.compile(
    r"^[ \t]*(?:pub[ \t]+)?data[ \t]+([A-Za-z_]\w*)[ \t]*:[ \t]*EffectsPreset[ \t]*=",
    re.M)
_PARALLAX_ARG = re.compile(r"\bparallax[ \t]*:[ \t]*([A-Za-z_]\w*)")
# `ojz_sec(sec: N, ..., effects: OJZ_Preset_SecN, ...)` in the act descriptor. Read as
# two independent streams and paired by position — each `effects:` belongs to the
# nearest NUMERIC `sec:` before it — rather than by a game-specific constructor name,
# which this generator does not know and must not hardcode.
_SEC_INDEX = re.compile(r"\bsec[ \t]*:[ \t]*(\d+)\b")
_SEC_EFFECTS = re.compile(r"\beffects[ \t]*:[ \t]*([A-Za-z_]\w*)")


def _strip_line_comments(src: str) -> str:
    """`//` comments removed, line structure preserved (offsets are NOT preserved).

    Crude on purpose and safe for what these two scans read: a `parallax:` or an
    `effects:` argument is never written inside a string literal. It exists because the
    prose in this tree is dense enough that a scan reading comments finds the WORD it
    is looking for in a sentence about it — `OJZ_Preset_Sec5`'s own d-53 comment
    discusses its parallax binding two lines above the argument.
    """
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


def preset_parallax_bindings(game: str = "sonic4", repo: str = REPO) -> list:
    """Every `preset(.. parallax: X ..)` in a game's effects library, in file order.

    Each entry is {"preset", "target", "file", "line"} — the rung-2 population. An
    ABSENT library is an empty list and not a refusal: a game with no effects library
    genuinely has no preset bindings, which is a different observation from a library
    this walk could not read (that raises, per contract §3's bare-open posture).
    """
    out = []
    lib = os.path.join(repo, "games", game, "data", "effects")
    if not os.path.isdir(lib):
        return out
    for name in sorted(os.listdir(lib)):
        if not name.endswith(".emp"):
            continue
        with open(os.path.join(lib, name), "r") as f:
            src = _strip_line_comments(f.read())
        decls = list(_PRESET_DECL.finditer(src))
        for i, m in enumerate(decls):
            stop = decls[i + 1].start() if i + 1 < len(decls) else len(src)
            window = src[m.end():stop]
            q = _PARALLAX_ARG.search(window)
            if not q:
                continue
            out.append({"preset": m.group(1), "target": q.group(1), "file": name,
                        "line": src.count("\n", 0, m.start()) + 1})
    return out


def section_preset_symbols(names: "ActNames", repo: str = REPO) -> dict:
    """{section index: the EffectsPreset symbol its `Sec` record binds}.

    Read from the act descriptor, which is the only place the section->preset edge is
    written down. Returns {} when the descriptor is absent — the caller then refuses
    WITHOUT a section number rather than inventing one, and says so in the message.
    """
    path = names.descriptor_path(repo)
    if not os.path.isfile(path):
        return {}
    with open(path, "r") as f:
        src = _strip_line_comments(f.read())
    indices = [(m.start(), int(m.group(1))) for m in _SEC_INDEX.finditer(src)]
    out = {}
    for m in _SEC_EFFECTS.finditer(src):
        prior = [sec for pos, sec in indices if pos < m.start()]
        if prior:
            out[prior[-1]] = m.group(1)
    return out


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
# `cycles` and `variants` joined this set on 2026-09-02 (EFFECTS-W1 DoD item 5). They were
# in PRESET_REFUSED_KEYS below until then, refused BY NAME, and the hub ruled their shape
# in `empyrean docs/AURORA_EFFECTS_SCHEMA.md` §7.2 ("The ten rulings", 2026-08-30) against
# this repo's demand artifact
# `docs/superpowers/specs/2026-08-30-item5-variants-cycles-key-shapes.md`. §7.2 and the
# committed `contract/schema/aurora-effects-preset.schema.json` are the authority for the
# shape below — NOT the artifact's §2, which is a proposal the hub overrode in three places
# (Q2, Q5, Q7).
# `patch_world_ys` and `patch_motion` joined on 2026-09-03 (EFFECTS-W1 DoD item 4, step 4 of
# four). The shape is aeon's own
# `docs/superpowers/specs/2026-09-03-anchor-authoring-key-shape.md` §2 as ruled by the hub in
# `empyrean docs/AURORA_EFFECTS_SCHEMA.md` §7.3, and the SCHEMA is the authority where the
# two differ — §7.3 is STRICTER than the aeon artifact on purpose (see PATCH_* below).
# `ramp` joined on 2026-09-03 too (EFFECTS-W1 DoD item 6, step 4 of four — the LAST of the
# four keys this file's own step-1 artifact
# (docs/superpowers/specs/2026-09-03-item6-dense-perline-vscroll-key-shape.md) named as
# blocked). Shape and the exactly-one-of-bands-or-ramp rule are
# `contract/schema/aurora-effects-preset.schema.json` §`ramp`/its top-level `oneOf`
# (empyrean docs/AURORA_EFFECTS_SCHEMA.md §7.4) — the SCHEMA is the authority, not the
# artifact's §5, which that page states outright is a proposal only.
# `base_swap` joined 2026-09-03 too (EFFECTS-W1 DoD item 11a's authorable half). UNLIKE the
# four keys above, THIS ONE SHIPS AHEAD OF A HUB RULING — the hub's own sequencing note
# (docs/DEFERRED_WORK.md, the item-11a booking) calls 11a's authorable half strictly
# SMALLER than item 10a's ("it already has its constructor... needs only a key and a
# per-scene binding") and says its shape note "can be the two-line kind rather than a full
# artifact" — i.e. build first, file the CR after, the opposite order from `ramp`'s
# artifact-then-build sequence. The shape note is
# `docs/superpowers/specs/2026-09-03-item11a-base-swap-key-shape.md`; there is no
# `contract/schema/aurora-effects-preset.schema.json` entry for it yet in this tree — that
# is the CR this note is filed against. `base_swap` occupies the SAME `ep_raster` channel
# `bands`/`ramp` do (one mid-frame `OP_SET_REG`, `engine/effects/raster_dsl.emp`'s generic
# `fire`/`reg_set`/`raster_program` — the exact three calls
# `games/sonic4/data/effects/ojz_effects.emp`'s hand-authored `OJZ_BaseSwap` already makes),
# so it joins the same exactly-one-of group below rather than opening a second `oneOf`.
PRESET_KEYS = frozenset({"schema", "id", "bands", "cycles", "variants",
                         "patch_world_ys", "patch_motion", "ramp", "base_swap"})

# `base_swap`'s own shape (EFFECTS-W1 item 11a's authorable half; no schema `$defs` entry
# exists yet — this generator IS the shape until the CR lands). Two fields, both required,
# both forwarded VERBATIM to engine constructs that already own the range:
#   `line`   — the screen line the swap fires on. `fire()`'s own ensure bounds it
#              (engine/effects/raster_dsl.emp:360-361) — restated nowhere in this file.
#   `target` — the VRAM byte address Plane A's base register is re-pointed at.
#              `vdp_base_reg(VdpBase.PlaneA, target)`'s own ensure refuses anything that is
#              not a multiple of reg $02's granule, $2000 (engine/vdp.emp:116-117), and
#              names the granule in its own message — so an illegal `target` fails the BUILD
#              by name, not a byte this file could silently mis-encode. Spelled as a raw
#              VRAM address rather than a `VdpBase` enum name, the same "spelled out
#              explicitly beats one fact computed twice" precedent `pal_region.addr` and
#              `ramp.target.vsram.addr` already set.
BASE_SWAP_KEYS = ("line", "target")

# `ramp`'s own shape (contract §7.4, `$defs/ramp` / `$defs/ramp_target` / `$defs/fp16`).
# SHAPE ONLY, this file's standing posture: every numeric bound named in the schema
# (top 3..222, lines 1..220, addr 0..78, fp16 whole -512..511 / frac256 0..255) is ALSO an
# engine `ensure` — `raster_ramp_program()`'s own guards for top/lines/addr
# (engine/effects/raster.emp:631/632/640-641/654-655) and `fp16()`'s own two guards for
# whole/frac256 (:685-686, now ALSO restated as a direct start/step bound inside
# raster_ramp_program itself — EFFECTS-W1 item 6 step 4's engine-side gap close) — so
# restating any of them here would be the second copy that drifts (`bands`' top/bot
# precedent: TestBandValuesAreNotValidatedHere). What IS this file's job, because nothing
# else checks it: the OBJECT SHAPE (closed keys, all five required, the single `vsram` arm,
# `start`/`step` as fp16 OBJECTS and never a raw integer) and the top-level exactly-one-of
# rule, both structural facts the schema's `oneOf`/`unevaluatedProperties` encode and this
# generator is the actual BUILD GATE for, since no schema validator runs in this build.
RAMP_TARGET_ARM = "vsram"
RAMP_KEYS = ("top", "lines", "target", "start", "step")
FP16_KEYS = ("whole", "frac256")

# `name` for the scene files' reason: a writer-owned display label.
PRESET_IGNORED_KEYS = frozenset({"name"})

# The rest of empyrean §7's reserved wave-2 vocabulary. These are NOT unknown keys — they
# are names the suite has agreed on and this generator has not built — so they get a
# refusal that says which, rather than the generic "unknown key" sentence that would send
# an author to file a contract change for a field the contract already reserves.
#
# ONE NAME LEFT. `variants` and `cycles` were here and are now built (item 5); `fires`
# stays reserved on both sides — empyrean §7 still holds it, and the schema's own
# reserved-and-refused line is down to it alone.
PRESET_REFUSED_KEYS = {
    "fires": "a reserved wave-2 preset key (empyrean AURORA_EFFECTS_SCHEMA.md §7) that "
             "this generator does not implement. `bands`, `cycles` and `variants` are "
             "built: a band lowers to the two or three fires band() derives, and a "
             "general fire list would need the vscroll/register/patchable vocabulary as "
             "well",
}

# =============================================================================
# PALETTE CYCLES AND VARIANTS — the other two EffectsPreset channels (contract §2.4).
# =============================================================================
#
# ⚠ WHICH "CYCLE" THIS KEY MEANS, SAID ONCE (hub ruling Q10, and the contract says the
# same sentence once in its §2.4). `cycles` is PALETTE cycling: the rotation of a span of
# CRAM entries by `Palette_DoCycle` / `Palette_RotateSpan` in engine/effects/palette.emp.
# It is UNRELATED to the DEBUG hotkey's **raster cycle table** (`RASTER_CYCLE_COUNT`,
# tools/test_raster_cycle_table_lint.py), which steps a human through raster PROGRAMS.
#
# WHAT THEY LOWER TO. A document's `cycles` array IS one script — `ep_cycle` is one
# pointer — and its `variants` array is POSITIONAL, index = `ep_variants[i]` = the slot
# `Palette_SetVariant` takes = the `slot` a `pal_region` band names in the same document:
#
#     pub data EditorCycle_OJZ_Act1_<id>: PalCycleScript1 = cycle_script1(
#         [ cycle_channel(line: .., first: .., count: .., period: .., dir: ..) ])
#     pub data EditorVariant_OJZ_Act1_<id>_<slot>: pal_variant = variant(shift_r: .., ..)
#
# plus two always-emitted zero-byte choosers beside the raster one, whose `hand:` argument
# is the caller's existing hand-authored channel.
#
# THREE STATES PER KEY, ONE SPELLING EACH (rulings Q2 and Q5) — this is the part that is
# easy to get backwards, and getting it backwards is silent:
#   * `cycles` ABSENT           -> the section keeps its hand-authored cycle (`hand:`)
#   * `cycles: null`            -> cycling OFF; lowers to `Pal_Cycle_None`, never to 0
#   * `cycles: [ .. ]`          -> the authored script; `[]` is REFUSED here
#   * `variants` index ABSENT   -> that slot keeps its hand-authored value (`hand:`)
#   * `variants[i] == null`     -> that slot is CLEARED (lowers to 0)
#   * `variants[i] == { .. }`   -> that slot is authored
# There is NO key-level `variants: null`: clearing both slots is `[null, null]`, and a
# key-level null is refused BY NAME below rather than falling through to "absent", which
# is the one state a null-filling writer would otherwise produce silently.
#
# ABSENT-KEEPS IS LOAD-BEARING, NOT A CONVENIENCE. Every shipped OJZ preset carries
# `variants: [Variant_Water_Deep, 0]`, so a document whose silence CLEARED the slot would
# drop the act-wide water tint at the first section crossing
# (games/sonic4/data/effects/ojz_effects.emp, the block above OJZ_Preset_Sec0).
#
# NOT ONE VALUE BOUND IS RESTATED HERE, with exactly one deliberate exception named at
# CYCLE_PERIOD_DOC_MIN below. `variant()` and `cycle_channel()` in
# engine/effects/palette_dsl.emp carry every range as an `ensure`, and a `pub data` in a
# lowered module is elaborated unconditionally, so the author reads the engine's own
# sentence. The two mirrors this file does carry are the two SHAPE limits — how many
# slots an array may have — and both are pinned against engine source by
# tools/test_effects_gen.py::TestTheEngineMirrorsArePinned.

# Required, IN `cycle_channel()`'s OWN ARGUMENT ORDER. `dir` is optional and is the only
# one, because it is the only one the constructor defaults (`dir: int = 0`).
CYCLE_CHANNEL_KEYS = ("line", "first", "count", "period")
CYCLE_CHANNEL_OPTIONAL_KEYS = ("dir",)

# Every field optional, because every one has a constructor default — which is what lets
# the shipped deep-water variant be `{"shift_r": 1, "shift_g": 1}` verbatim. Order is
# `variant()`'s own, so the emitted call reads like the hand one. `v_pad` is not a
# document field.
VARIANT_KEYS = ("shift_r", "bias_r", "shift_g", "bias_g", "shift_b", "bias_b", "lines")

# A MIRROR of engine/effects/palette.emp's `PAL_MAX_VARIANTS`, carried for the same reason
# MAX_PARALLAX_BANDS above is: the generator emits a POSITIONAL array and a chooser with a
# slot ensure, so it has to know how many positions exist before the engine can speak.
PAL_MAX_VARIANTS = 2

# A MIRROR of which `cycle_scriptN` wrappers engine/effects/palette_dsl.emp actually
# declares — NOT of `PAL_CYCLE_MAX_CHANNELS`, which is 4. Only 1 and 2 exist, so a
# 3-channel document has no constructor to lower into and the refusal has to name the
# engine limit rather than let sigil say "unknown function" about generated code. Rider 1
# (empyrean §7.2) adds cycle_script3/4; the pin below goes red and names this line.
CYCLE_SCRIPT_WRAPPERS = (1, 2)

# THE ONE VALUE BOUND THIS FILE OWNS, AND IT IS OWED AN ARGUMENT (hub ruling Q7).
#
# The document's `period` is in FRAMES — the author's meaning, "a rotation every N frames"
# — and the generator emits `pc_period = period - 1`, because the engine's timer reloads
# `period` and rotates at 0, so its runtime cadence is `period + 1` frames
# (engine/effects/palette.emp, Palette_DoCycle's timer logic).
#
# `cycle_channel()`'s own floor is `period >= 1`. With the `-1` applied, an authored
# `period: 1` emits 0 and the engine fires a sentence about **0** — a number the author
# never wrote and cannot find in their file. That is the single place the forward-verbatim
# posture breaks, and it is written deliberately rather than discovered: the floor below is
# the engine's floor SHIFTED BY THE SAME TRANSLATION, and the refusal names the author's
# number. It is a unit translation, which this file's docstring classifies as SHAPE.
CYCLE_PERIOD_ENGINE_MIN = 1
CYCLE_PERIOD_DOC_MIN = CYCLE_PERIOD_ENGINE_MIN + 1

# =============================================================================
# THE PATCH CHANNELS — the anchor mover's authoring key (EFFECTS-W1 DoD item 4).
# =============================================================================
#
# `patch_world_ys` is the per-channel world-anchor SEED and `patch_motion` the per-channel
# packed SWEEP word. Both are `preset()` parameters (engine/effects/preset.emp:141-148) and
# both are POSITIONAL, index = patch channel, exactly like `variants`. Three states per
# index, one spelling each, and they are the same three `variants` has:
#
#   * an index the array does not reach -> KEEP the section's hand-authored value (`hand:`)
#   * `null`                            -> the engine SENTINEL, never 0
#   * a value                           -> authored
#
# ⚠ THE UNIT, WHICH IS THE TRAP THIS BLOCK EXISTS FOR. `patch_world_ys[i]` is WHOLE PIXELS
# in absolute level space and NEITHER SIDE CONVERTS — 1:1, both directions, no scaling
# anywhere in this file or in the editor. That is NOT item 3's `drift.rate`, which is
# 1/256 px per frame with the editor multiplying by 256 on export. Carrying that habit here
# puts the anchor 256x down the level; `Effects_LatchWorldLines` derives a screen line as
# `anchor - Camera_Y`, so the band lands far below the screen and SILENTLY NEVER APPEARS.
# There is no error to read, so grep this file for a `* 256` before believing a bug report:
# there is none, and there must never be one.
#
# ⚠ `0` IS A REAL WORLD Y AND IT IS THE WORST ONE. `anchor - Camera_Y` at anchor 0 reads as
# ABOVE the screen top, i.e. "fully submerged" — the most invasive state a channel nobody
# asked for can have. "Unused" is `null`, which lowers to PATCH_ANCHOR_NONE. Same rule as
# item 5's `cycles: null -> Pal_Cycle_None, never 0`.
#
# WHERE THE BOUNDS LIVE, and this key DEPARTS from the shape-only posture in exactly two
# places, on the hub's own ruling (empyrean §7.3, "ONE departure from §7.1's shape-only
# posture, ruled here"). The sweep's three ranges stay the engine's: `anchor_sweep()`'s
# ensures (its three amplitude/period/phase guards) carry the derived ladders and the worked
# conversion, so this file forwards `amp_shift` / `period_shift` / `phase` VERBATIM — never
# rounded, never snapped, because rounding an off-ladder rung silently doubles or halves the
# motion where refusing it names the value. But the SEED has no engine bound at all:
# `preset()` ensures the array LENGTH, not its values, so a seed of 32767 (a stationary
# channel the author thinks is authored) and a seed outside u16 (a truncated anchor) both
# reach the ROM with no message from anywhere. The schema encodes them and so does this
# file — "the party validating is the party publishing", and here that is both of us.
PATCH_ANCHOR_NONE = 0x7FFF          # engine/effects/raster_dsl.emp
ANCHOR_MOTION_NONE = 0              # engine/effects/raster_dsl.emp
PATCH_WORLD_Y_MAX = 0xFFFF          # ep_patch_world_ys is [u16; RASTER_MAX_PATCH]

# A MIRROR of engine/effects/raster_dsl.emp's `RASTER_MAX_PATCH`, carried for
# `PAL_MAX_VARIANTS`' reason one channel over: both keys are POSITIONAL arrays and the
# emitted chooser carries a `ch` ensure, so this file has to know how many positions exist
# before the engine can speak. The engine's own ceiling is not reachable from a fifth entry
# — `preset()` checks `patch_world_ys.len == RASTER_MAX_PATCH` at the CALL SITE, which
# writes all four positions literally whatever the document said, so a five-channel document
# would simply lose its fifth entry with nothing anywhere to say so.
RASTER_MAX_PATCH = 4

# The one arm `patch_motion` has. There is deliberately NO `approach` arm and the schema
# reserves none: APPROACH has no preset seed field (preset.emp:81-87), its runtime handle is
# `Effects_SetTargetY`, and a reserved arm would be a key with nothing behind it. Adding one
# is its own contract change.
PATCH_MOTION_ARM = "sweep"
SWEEP_KEYS = ("amp_shift", "period_shift")
SWEEP_OPTIONAL_KEYS = ("phase",)

# CAP_ANCHOR_MOTION, and the ASYMMETRY that makes this a generator refusal rather than an
# engine one (aeon artifact §4b). `Effects_InstallPreset`'s SEED is not capability-gated —
# 34 bytes every game pays, a measured decision at preset.emp:333-340 — while the latch loop
# that READS the motion is (`engine/effects/raster.emp`, the `if (Game.SCANLINE_CAPS &
# CAP_ANCHOR_MOTION) != 0` block). So in a game that does not raise the bit, an authored
# sweep is written into the preset record, installed into `Effects_Motion[]`, folded into
# `Effects_Motion_Any` — and NOTHING EVER READS IT. The boundary does not move and nothing
# says why. That is a silent no-op with data behind it, which is worse than an error, so the
# combination is refused here where both facts are visible at once.
CAP_ANCHOR_MOTION = 0x0100

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


def load_scene(path: str, game: str = "sonic4", repo: str = REPO) -> dict:
    """Load and SHAPE-validate one scene file. Raises on anything malformed.

    Deliberately bare `json.load` + direct subscripting (contract §3): a broken
    file must stop the build, not be repaired or routed around.

    `game`/`repo` exist for ONE check: the `reels` key's rate-array length, which is
    REEL_BAND_COUNT re-derived from the game's own constants module rather than copied
    from the schema's `minItems` (CR §2.7). They are read ONLY when a scene carries the
    key, so a tree with no reels authored opens no `.emp` at all and every fixture that
    predates this arm keeps working with no game sources on disk.
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
        _check_keys(path, layer, LAYER_KEYS, LAYER_IGNORED_KEYS, LAYER_REFUSED_KEYS,
                    f"layers[{i}]")
        for required in ("world_y", "fa", "fb"):
            if required not in layer:
                _refuse(path, f"layers[{i}] has no `{required}`. world_y/fa/fb are "
                              f"the three `layer()` arguments with no default.")

    if REELS_KEY in scene:
        _check_reels(path, scene, reel_band_count(game, repo))

    return scene


def load_all_scenes(game: str = "sonic4", repo: str = REPO) -> dict:
    """All editor scenes for a game, keyed by id. Empty dict when none exist."""
    scenes = {}
    for path in discover_scene_files(game, repo):
        scene = load_scene(path, game, repo)
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

    # EXACTLY ONE OF `bands`, `ramp` OR `base_swap` (contract §7.4's top-level `oneOf` for
    # the first two, widened here to a third arm for EFFECTS-W1 item 11a's authorable
    # half — see `base_swap`'s own banner above for why this key ships ahead of a schema
    # entry). All three lower into the SAME EffectsPreset.ep_raster channel and the engine
    # has no combinator that mixes any two of a sparse fire list, a dense run and a single
    # mid-frame register op, so this is a real structural fact and not a style preference —
    # refused here BECAUSE this file is the actual build gate (no schema validator runs
    # against these documents in this repo).
    has_bands, has_ramp, has_base_swap = ("bands" in preset, "ramp" in preset,
                                          "base_swap" in preset)
    chosen = [k for k, present in (("bands", has_bands), ("ramp", has_ramp),
                                    ("base_swap", has_base_swap)) if present]
    if len(chosen) > 1:
        _refuse(path, f"carries more than one of `bands`/`ramp`/`base_swap` "
                      f"({', '.join(chosen)}). Exactly one raster program per preset "
                      f"document: all three lower into the same EffectsPreset.ep_raster "
                      f"channel and the engine has no combinator that mixes any two of "
                      f"them. Drop all but one — a future contract change may widen this "
                      f"once a combinator exists; today the schema refuses the "
                      f"combination on purpose (a schema can widen later and cannot "
                      f"narrow once a consumer has emitted the wider shape).")
    if not chosen:
        _refuse(path, "no `bands`, `ramp` or `base_swap` key. A preset document must "
                      "carry exactly one raster program (hub ruling Q1a for `bands`; "
                      "contract §7.4's `oneOf` for `bands`/`ramp`; `base_swap`'s own "
                      "banner above for the third arm): `bands` for the sparse "
                      "fire-list tier, `ramp` for the dense per-line vertical scroll "
                      "(EFFECTS-W1 item 6), or `base_swap` for the mid-frame "
                      "nametable-base swap (EFFECTS-W1 item 11a). `cycles` and "
                      "`variants` are optional channels beside any one of the three, "
                      "and a cycle-only or variant-only document is a future contract "
                      "change. The one name empyrean's schema doc §7 still reserves "
                      "(`fires`) is refused by name above.")

    if has_bands:
        bands = preset["bands"]
        if not isinstance(bands, list):
            _refuse(path, f"`bands` must be a list, got {type(bands).__name__}")
        if not bands:
            _refuse(path, "`bands` is empty. A preset document with no bands would lower "
                          "to `compose([])` and then to an EMPTY raster program, which "
                          "the engine refuses one layer down with a message about "
                          "`compose` rather than about this file — and a document that "
                          "emits a zero-band program is a document that should not exist. "
                          "If the intent is 'no raster here', delete the file.")

        for i, band in enumerate(bands):
            if not isinstance(band, dict):
                _refuse(path, f"bands[{i}] must be an object, got {type(band).__name__}")
            _check_keys(path, band, frozenset(BAND_KEYS), frozenset(), None, f"bands[{i}]")
            for required in BAND_KEYS:
                if required not in band:
                    _refuse(path, f"bands[{i}] has no `{required}`. A band is exactly "
                                  f"{', '.join(BAND_KEYS)} — all four, none with a "
                                  f"default. `sh` has none in the engine either: "
                                  f"raster_dsl.emp's `region_boundary` note is that "
                                  f"whether an effect changes a mode register is worth "
                                  f"stating at the call site.")

    _check_ramp(path, preset)
    _check_base_swap(path, preset)
    _check_cycles(path, preset)
    _check_variants(path, preset)
    _check_cleared_slot_is_not_streamed(path, preset)
    _check_patch_world_ys(path, preset)
    _check_patch_motion(path, preset)
    _check_motion_has_an_anchor(path, preset)
    return preset


def _check_ramp(path: str, preset: dict) -> None:
    """SHAPE of the `ramp` key (contract §7.4, `$defs/ramp`/`ramp_target`/`fp16`).

    SHAPE ONLY — see RAMP_KEYS' banner above for why not one numeric bound is restated:
    every range the schema names is ALSO an engine `ensure` (raster_ramp_program's own for
    top/lines/addr, fp16's own — now also restated as a direct start/step bound inside
    raster_ramp_program — for whole/frac256), so this function forwards top/lines/addr and
    the fp16 fields VERBATIM and checks only that the document is the right SHAPE to
    forward at all: closed keys, all five ramp fields required, the single `vsram` arm
    (never `cram`, never a `curve` key), and `start`/`step` as fp16 OBJECTS rather than a
    raw integer — clause 3 of the CR: a raw integer here would reach
    `raster_ramp_program()` with no `fp16()` between it and the constructor, which is
    exactly the bypass the schema's fp16-object shape exists to close on the generator
    side (the engine-side close is the new ensure in raster_ramp_program itself).
    """
    if "ramp" not in preset:
        return
    ramp = preset["ramp"]
    if not isinstance(ramp, dict):
        _refuse(path, f"`ramp` must be an object, got {type(ramp).__name__}. A preset "
                      f"has exactly one raster: channel (EffectsPreset.ep_raster), so "
                      f"there is one ramp per document, never an array of them.")
    _check_keys(path, ramp, frozenset(RAMP_KEYS), frozenset(), None, "ramp")
    for required in RAMP_KEYS:
        if required not in ramp:
            _refuse(path, f"ramp has no `{required}`. All five of "
                          f"{', '.join(RAMP_KEYS)} are required — "
                          f"raster_ramp_program() defaults none of them "
                          f"(engine/effects/raster.emp:629-678).")

    top, lines = ramp["top"], ramp["lines"]
    if isinstance(top, bool) or not isinstance(top, int):
        _refuse(path, f"ramp.top must be an integer, got {type(top).__name__} {top!r}. "
                      f"Whether it is IN RANGE (3..222) is raster_ramp_program's own "
                      f"ensure (raster.emp:631, :640-641), not this file's.")
    if isinstance(lines, bool) or not isinstance(lines, int):
        _refuse(path, f"ramp.lines must be an integer, got {type(lines).__name__} "
                      f"{lines!r}. Whether it is IN RANGE (1..220) is "
                      f"raster_ramp_program's own ensure (raster.emp:632, :640-641), not "
                      f"this file's.")

    target = ramp["target"]
    if not isinstance(target, dict):
        _refuse(path, f"ramp.target must be an object, got {type(target).__name__}. "
                      f"It names a target ARM plus an explicit byte address, the "
                      f"`pal_region` precedent of spelling an address out rather than "
                      f"deriving it (effects_gen.py's own PALETTE banner references "
                      f"this precedent for `pal_region.addr`).")
    vsram = _single_arm(path, target, RAMP_TARGET_ARM, "ramp.target")
    if not isinstance(vsram, dict):
        _refuse(path, f"ramp.target.{RAMP_TARGET_ARM} must be an object, got "
                      f"{type(vsram).__name__}")
    addr, = _fields(path, vsram, ("addr",), f"ramp.target.{RAMP_TARGET_ARM}")
    if isinstance(addr, bool) or not isinstance(addr, int):
        _refuse(path, f"ramp.target.{RAMP_TARGET_ARM}.addr must be an integer, got "
                      f"{type(addr).__name__} {addr!r}. Whether it is IN RANGE (0..78) "
                      f"is raster_ramp_program's own ensure (raster.emp:654-655; VSRAM "
                      f"is 80 bytes), not this file's.")

    for key in ("start", "step"):
        _check_fp16(path, ramp[key], f"ramp.{key}")


def _check_fp16(path: str, value, where: str) -> None:
    """SHAPE of one fp16 object — clause 3 of the CR, made structural.

    `start`/`step` route ONLY through `fp16(whole, frac256)`: this is the whole reason the
    schema spells them as OBJECTS rather than raw 16.16 integers, so this check is a shape
    gate for a real defect class (a bare integer here would emit a raw literal straight
    into `raster_ramp_program`, bypassing fp16's own range ensures entirely) and not
    decoration. `whole`/`frac256`'s RANGES are fp16's own ensures
    (engine/effects/raster.emp:685-686); forwarded verbatim, not restated.
    """
    if not isinstance(value, dict):
        _refuse(path, f"{where} must be an fp16 object ({{whole, frac256}}), got "
                      f"{type(value).__name__} {value!r}. start/step are fp16 OBJECTS on "
                      f"purpose: the generator emits `fp16(whole, frac256)` verbatim so "
                      f"no raw 16.16 literal can reach raster_ramp_program() and bypass "
                      f"fp16's own range ensures.")
    _check_keys(path, value, frozenset(FP16_KEYS), frozenset(), None, where)
    for required in FP16_KEYS:
        if required not in value:
            _refuse(path, f"{where} has no `{required}`. fp16 requires both `whole` and "
                          f"`frac256`, no default on either (raster.emp:684).")
    whole, frac256 = value["whole"], value["frac256"]
    if isinstance(whole, bool) or not isinstance(whole, int):
        _refuse(path, f"{where}.whole must be an integer, got {type(whole).__name__} "
                      f"{whole!r}. Whether it is IN RANGE (-512..511) is fp16's own "
                      f"ensure (raster.emp:686), not this file's.")
    if isinstance(frac256, bool) or not isinstance(frac256, int):
        _refuse(path, f"{where}.frac256 must be an integer, got "
                      f"{type(frac256).__name__} {frac256!r}. Whether it is IN RANGE "
                      f"(0..255) is fp16's own ensure (raster.emp:685), not this file's.")


def _check_base_swap(path: str, preset: dict) -> None:
    """SHAPE of the `base_swap` key (EFFECTS-W1 item 11a's authorable half).

    SHAPE ONLY, `_check_ramp`'s own posture: `line` and `target` are forwarded VERBATIM to
    `fire()` and `vdp_base_reg()`, which own their own ranges (BASE_SWAP_KEYS' banner
    above), so this function checks only that the document is the right SHAPE to forward
    at all — closed keys, both fields required, both plain integers.
    """
    if "base_swap" not in preset:
        return
    bs = preset["base_swap"]
    if not isinstance(bs, dict):
        _refuse(path, f"`base_swap` must be an object, got {type(bs).__name__}. A preset "
                      f"has exactly one raster: channel (EffectsPreset.ep_raster), so "
                      f"there is one mid-frame base swap per document, never an array of "
                      f"them.")
    _check_keys(path, bs, frozenset(BASE_SWAP_KEYS), frozenset(), None, "base_swap")
    for required in BASE_SWAP_KEYS:
        if required not in bs:
            _refuse(path, f"base_swap has no `{required}`. Both `line` and `target` are "
                          f"required, no default on either — the hand-authored precedent "
                          f"(`games/sonic4/data/effects/ojz_effects.emp`'s `OJZ_BaseSwap`) "
                          f"authors both explicitly.")

    line = bs["line"]
    if isinstance(line, bool) or not isinstance(line, int):
        _refuse(path, f"base_swap.line must be an integer, got {type(line).__name__} "
                      f"{line!r}. Whether it is IN RANGE is fire()'s own ensure "
                      f"(engine/effects/raster_dsl.emp:360-361), not this file's.")

    target = bs["target"]
    if isinstance(target, bool) or not isinstance(target, int):
        _refuse(path, f"base_swap.target must be an integer VRAM byte address, got "
                      f"{type(target).__name__} {target!r}. It must be a multiple of "
                      f"$2000 — Plane A's base register (reg $02) encodes only the "
                      f"address bits above that granule and drops the rest SILENTLY, so "
                      f"an unaligned target would point the VDP at a different address "
                      f"than every other VRAM_* consumer while nothing outside the "
                      f"encoding could see the difference. Whether it IS a multiple of "
                      f"$2000 is vdp_base_reg()'s own ensure (engine/vdp.emp:116-117), "
                      f"not this file's — it fails the build by name rather than "
                      f"silently encoding the wrong register byte.")


def _check_cleared_slot_is_not_streamed(path: str, preset: dict) -> None:
    """The NARROW half of ruling Q6, which is the half that is available today.

    A `pal_region` band names a `Pal_Variant_Stage` SLOT and `variants[slot]` names that
    slot's descriptor — the same integer, now in one file for the first time, which is the
    whole reason the hub noted the binding becomes visible when both keys live in one
    document. The BROAD check (refuse a band naming a slot the document leaves ABSENT) is
    deferred as rider 2 and would be WRONG today: absent means "the hand `preset()` call's
    value is still there", which the generator cannot see, and that is the majority case.

    EXPLICIT `null` has no such ambiguity. The document is saying "clear this slot" and
    "stream from this slot" in the same breath, and there is no reading under which that is
    what someone meant — the band would stream whatever the staging buffer last held.

    Deliberately lenient about everything it is not asking: a malformed band or a
    non-integer slot is `render_band_on`'s refusal, with its own sentence, and this
    function must not pre-empt it with a crash.
    """
    slots = preset.get("variants")
    if not isinstance(slots, list):
        return
    cleared = {i for i, v in enumerate(slots) if v is None}
    if not cleared:
        return
    # A ramp document has no `bands` at all (contract §7.4's oneOf) — nothing to walk.
    for i, band in enumerate(preset.get("bands") or []):
        if not isinstance(band, dict):
            continue
        on = band.get("on")
        if not isinstance(on, dict):
            continue
        region = on.get("pal_region")
        if not isinstance(region, dict):
            continue
        slot = region.get("slot")
        if isinstance(slot, bool) or not isinstance(slot, int):
            continue
        if slot in cleared:
            _refuse(path, f"bands[{i}] streams from variant slot {slot} "
                          f"(`on.pal_region.slot`), but this document sets "
                          f"`variants[{slot}]` to null, which CLEARS that slot. The band "
                          f"would stream whatever `Pal_Variant_Stage` last held for slot "
                          f"{slot}. Author the slot, or drop the null so the section's "
                          f"hand-authored variant keeps it, or point the band at the "
                          f"other slot.")


def _check_cycles(path: str, preset: dict) -> None:
    """SHAPE of the `cycles` key. Three states, one spelling each (hub ruling Q2).

    Absent is not checked at all — it is the no-cost majority case and the state of every
    document shipped before item 5. `null` is OFF and carries no channels to check. Only
    the array form reaches the per-channel walk.
    """
    if "cycles" not in preset or preset["cycles"] is None:
        return
    chs = preset["cycles"]
    if not isinstance(chs, list):
        _refuse(path, f"`cycles` must be a list of channel objects or null, got "
                      f"{type(chs).__name__}. The array IS the script (one script per "
                      f"document, because `ep_cycle` is one pointer); `null` means "
                      f"cycling OFF for this section.")
    if not chs:
        _refuse(path, "`cycles` is an EMPTY array, which is not one of the three states "
                      "this key has. Write `\"cycles\": null` for \"cycling OFF here\" "
                      "(it lowers to the engine's `Pal_Cycle_None` sentinel), or OMIT "
                      "the key to keep this section's hand-authored cycle. An empty "
                      "array would lower to a script with no channels, which is what "
                      "`null` already spells — and one state on the wire two ways is "
                      "the defect the rule exists to prevent.")
    if len(chs) not in CYCLE_SCRIPT_WRAPPERS:
        _refuse(path, f"`cycles` has {len(chs)} channels, and "
                      f"engine/effects/palette_dsl.emp declares script wrappers for "
                      f"{', '.join(str(n) for n in CYCLE_SCRIPT_WRAPPERS)} only "
                      f"(`cycle_script1`, `cycle_script2`). There is no constructor to "
                      f"lower a wider script into — a `PalCycleScriptN` struct and its "
                      f"wrapper are an ENGINE addition (empyrean §7.2 rider 1), never a "
                      f"second lowering in generated code. The engine's own channel "
                      f"ceiling (`PAL_CYCLE_MAX_CHANNELS`) is higher than the wrappers "
                      f"go, which is why this refusal names the wrappers and not it.")
    for i, ch in enumerate(chs):
        if not isinstance(ch, dict):
            _refuse(path, f"cycles[{i}] must be an object, got {type(ch).__name__}")
        _check_keys(path, ch,
                    frozenset(CYCLE_CHANNEL_KEYS) | frozenset(CYCLE_CHANNEL_OPTIONAL_KEYS),
                    frozenset(), None, f"cycles[{i}]")
        for required in CYCLE_CHANNEL_KEYS:
            if required not in ch:
                _refuse(path, f"cycles[{i}] has no `{required}`. A cycle channel is "
                              f"{', '.join(CYCLE_CHANNEL_KEYS)} — all four required, "
                              f"none with a default — plus the optional "
                              f"`{CYCLE_CHANNEL_OPTIONAL_KEYS[0]}`, which is the only "
                              f"field `cycle_channel()` itself defaults.")


def _check_variants(path: str, preset: dict) -> None:
    """SHAPE of the `variants` key. Positional, index = slot (hub ruling Q5).

    A key-level `null` is refused BY NAME rather than treated as absent. The hub ruled
    that state does not exist (clearing both slots is `[null, null]`), and a writer that
    nulls every key it knows would otherwise produce "absent" — the one state whose
    meaning is "keep the hand value", which is the opposite of what such a writer meant.
    An unnamed fall-through here is exactly the silent case.
    """
    if "variants" not in preset:
        return
    slots = preset["variants"]
    if slots is None:
        _refuse(path, "`variants` is null at KEY level, and that state does not exist "
                      "(hub ruling Q5). Positions are what carry the three states: OMIT "
                      "the key to keep every slot's hand-authored value, write "
                      "`[null, null]` to CLEAR both, or put an object at the index you "
                      "are authoring. A key-level null is refused rather than read as "
                      "\"absent\", because a writer that nulls every key it knows would "
                      "otherwise silently mean the opposite of what it wrote.")
    if not isinstance(slots, list):
        _refuse(path, f"`variants` must be a list, got {type(slots).__name__}. It is "
                      f"POSITIONAL — index i is `ep_variants[i]`, the slot "
                      f"`Palette_SetVariant` takes and the `slot` a `pal_region` band "
                      f"names in this same document — so a map would lose the one "
                      f"property the key exists for.")
    if len(slots) > PAL_MAX_VARIANTS:
        _refuse(path, f"`variants` has {len(slots)} entries but the engine has "
                      f"{PAL_MAX_VARIANTS} staging slots (`PAL_MAX_VARIANTS`, "
                      f"engine/effects/palette.emp). The array is positional, so entry "
                      f"{PAL_MAX_VARIANTS} names a slot that does not exist — "
                      f"`Palette_SetVariant` masks the index with a power-of-two mask "
                      f"and would fold it back onto slot 0.")
    for i, v in enumerate(slots):
        if v is None:
            continue                      # CLEAR this slot. A legal state, not a gap.
        if not isinstance(v, dict):
            _refuse(path, f"variants[{i}] must be an object or null, got "
                          f"{type(v).__name__}. null CLEARS the slot; an object authors "
                          f"it; an index the array does not reach keeps the "
                          f"hand-authored value.")
        _check_keys(path, v, frozenset(VARIANT_KEYS), frozenset(), None,
                    f"variants[{i}]")


def _check_positional_patch_array(path: str, preset: dict, key: str):
    """The half `patch_world_ys` and `patch_motion` share: positional, <= 4, key-level null
    refused by NAME.

    Returns the list, or None when the key is absent (the "keep the hand value" state).

    A KEY-LEVEL `null` is refused for `_check_variants`' measured reason and it is the same
    writer that produces it: a writer that nulls every key it knows would otherwise emit the
    one state whose meaning is "keep the hand-authored value", which is the OPPOSITE of what
    it wrote. Positions carry the three states; the key does not.
    """
    if key not in preset:
        return None
    arr = preset[key]
    if arr is None:
        _refuse(path, f"`{key}` is null at KEY level, and that state does not exist. "
                      f"Positions are what carry the three states: OMIT the key to keep "
                      f"every channel's hand-authored value, write `[null, null, null, "
                      f"null]` to set every channel to the engine sentinel, or put a value "
                      f"at the index you are authoring. A key-level null is refused rather "
                      f"than read as \"absent\", because a writer that nulls every key it "
                      f"knows would otherwise silently mean the opposite of what it wrote.")
    if not isinstance(arr, list):
        _refuse(path, f"`{key}` must be a list, got {type(arr).__name__}. It is "
                      f"POSITIONAL — index i is patch CHANNEL i, the same channel a "
                      f"`patchable(ch: i, ..)` call declares a band for — so a map would "
                      f"lose the one property the key exists for.")
    if len(arr) > RASTER_MAX_PATCH:
        _refuse(path, f"`{key}` has {len(arr)} entries but the engine has "
                      f"{RASTER_MAX_PATCH} patch channels (`RASTER_MAX_PATCH`, "
                      f"engine/effects/raster_dsl.emp). The array is positional, so entry "
                      f"{RASTER_MAX_PATCH} names a channel that does not exist — and "
                      f"NOTHING DOWNSTREAM WOULD SAY SO: `preset()`'s length ensure fires "
                      f"on the CALL SITE's array, which writes exactly "
                      f"{RASTER_MAX_PATCH} positions whatever this document carried, so a "
                      f"fifth entry is simply dropped in silence. Refused here because "
                      f"here is the only place it is visible.")
    return arr


def _check_patch_world_ys(path: str, preset: dict) -> None:
    """SHAPE and the two bounds the hub ruled onto the writer side (empyrean §7.3).

    `0 … 65535` and "not the sentinel" are the ONLY numeric bounds this file owns on this
    key, and each is owed its argument because the file's standing posture is that ranges
    belong to the engine (this module's SHAPE-vs-VALUE docstring). The argument is that
    NEITHER HAS AN ENGINE SITE: `preset()` ensures `patch_world_ys.len`, not its values, so
    a 70000 truncates into the u16 and a 32767 installs a channel the runtime reads as
    UNUSED — both reaching the ROM with no message from any layer. A bound with no other
    enforcing site is not a duplicated bound.
    """
    ys = _check_positional_patch_array(path, preset, "patch_world_ys")
    if ys is None:
        return
    for i, y in enumerate(ys):
        if y is None:
            continue                      # the sentinel. A legal state, not a gap.
        if isinstance(y, bool) or not isinstance(y, int):
            _refuse(path, f"patch_world_ys[{i}] must be an integer or null, got "
                          f"{type(y).__name__} {y!r}. null is the engine's "
                          f"PATCH_ANCHOR_NONE sentinel (\"this channel is unused\"); an "
                          f"integer is a world Y in WHOLE PIXELS; an index the array does "
                          f"not reach keeps the section's hand-authored anchor.")
        if not 0 <= y <= PATCH_WORLD_Y_MAX:
            _refuse(path, f"patch_world_ys[{i}] is {y}, outside 0..{PATCH_WORLD_Y_MAX}. "
                          f"`ep_patch_world_ys` is [u16; {RASTER_MAX_PATCH}], so this "
                          f"value is stored in sixteen bits and a larger one TRUNCATES — "
                          f"the anchor lands somewhere else entirely and nothing reports "
                          f"it. Note the unit before you widen the number: this field is "
                          f"WHOLE PIXELS in absolute level space, 1:1, and nothing on "
                          f"either side of the wire scales it. A value near 57344 is very "
                          f"often 224 that has been through item 3's `drift.rate` x256 "
                          f"conversion by mistake.")
        if y == PATCH_ANCHOR_NONE:
            _refuse(path, f"patch_world_ys[{i}] is {PATCH_ANCHOR_NONE}, which is the "
                          f"engine's PATCH_ANCHOR_NONE sentinel — the value that means "
                          f"\"this channel is UNUSED\". Written as an integer it reads as "
                          f"an authored anchor to every human and as \"unused\" to the "
                          f"runtime, and the two never meet: the channel simply does "
                          f"nothing. Spell the intent as `null`, which lowers to the same "
                          f"word and says what it is. If you really did mean world Y "
                          f"{PATCH_ANCHOR_NONE}, use {PATCH_ANCHOR_NONE - 1} or "
                          f"{PATCH_ANCHOR_NONE + 1} — one pixel is not the difference "
                          f"between a working effect and a missing one, and this is.")


def _check_patch_motion(path: str, preset: dict) -> None:
    """SHAPE of `patch_motion`. One arm, `sweep`, and its three fields forwarded verbatim.

    NOT ONE SWEEP RANGE IS CHECKED HERE. `anchor_sweep()` carries all three, each with the
    derived ladder in its message, and its ladders are DERIVED from
    ANCHOR_SINE_AMP / ANCHOR_SCREEN_LINES / ANCHOR_SINE_ENTRIES / ANCHOR_TICK_BITS rather
    than picked — so a copy here would be a second source that drifts the day the screen or
    the sine table moves. What this file does own is that the value arrives UNCHANGED: these
    are base-2 LOGARITHMS on quantized ladders (7 amplitude rungs, 9 period rungs), so
    rounding one rung doubles or halves the motion in silence where refusing it prints the
    ladder. There is no rounding, no snapping and no unit translation on this path.
    """
    motions = _check_positional_patch_array(path, preset, "patch_motion")
    if motions is None:
        return
    for i, m in enumerate(motions):
        if m is None:
            continue                      # ANCHOR_MOTION_NONE — a static channel.
        if not isinstance(m, dict):
            _refuse(path, f"patch_motion[{i}] must be an object or null, got "
                          f"{type(m).__name__}. null is the engine's ANCHOR_MOTION_NONE "
                          f"(\"this channel does not move\"); an object is "
                          f"`{{\"{PATCH_MOTION_ARM}\": {{..}}}}`; an index the array does "
                          f"not reach keeps the section's hand-authored motion.")
        body = _single_arm(path, m, PATCH_MOTION_ARM, f"patch_motion[{i}]")
        if not isinstance(body, dict):
            _refuse(path, f"patch_motion[{i}].{PATCH_MOTION_ARM} must be an object with "
                          f"{'/'.join(SWEEP_KEYS)}, got {type(body).__name__}")
        _check_keys(path, body,
                    frozenset(SWEEP_KEYS) | frozenset(SWEEP_OPTIONAL_KEYS),
                    frozenset(), None, f"patch_motion[{i}].{PATCH_MOTION_ARM}")
        for required in SWEEP_KEYS:
            if required not in body:
                _refuse(path, f"patch_motion[{i}].{PATCH_MOTION_ARM} has no `{required}`. "
                              f"A sweep is {', '.join(SWEEP_KEYS)} — both required, "
                              f"neither with a default — plus the optional "
                              f"`{SWEEP_OPTIONAL_KEYS[0]}`, which is the only field "
                              f"`anchor_sweep()` itself defaults. Both required fields are "
                              f"base-2 SHIFTS and not pixels or frames: the peak excursion "
                              f"is `256 >> amp_shift` px and one cycle is "
                              f"`256 << period_shift` ticks.")


def _check_motion_has_an_anchor(path: str, preset: dict) -> None:
    """A motion on a channel this document also sets to the SENTINEL is a no-op, said once.

    The narrow half of "two keys or nothing" (aeon artifact §1), and it is narrow for
    `_check_cleared_slot_is_not_streamed`'s reason: an index the document does not reach
    keeps the section's hand-authored anchor, which this file cannot see and which is the
    majority case, so ABSENCE is not checkable. An explicit `null` beside a sweep has no
    such ambiguity — the document says "this channel is unused" and "this channel sweeps" in
    the same breath, and the runtime resolves that as unused.
    """
    ys = preset.get("patch_world_ys")
    motions = preset.get("patch_motion")
    if not isinstance(ys, list) or not isinstance(motions, list):
        return
    for i, m in enumerate(motions):
        if m is None or i >= len(ys) or ys[i] is not None:
            continue
        _refuse(path, f"patch_motion[{i}] authors a sweep on channel {i}, but this "
                      f"document also sets `patch_world_ys[{i}]` to null, which is the "
                      f"PATCH_ANCHOR_NONE sentinel — \"channel {i} is unused\". A sweep is "
                      f"a displacement of an anchor; with no anchor there is nothing to "
                      f"displace and the channel is inert, so this pair authors an effect "
                      f"that cannot appear. Give channel {i} a world Y, or drop the null "
                      f"so the section's hand-authored anchor stands, or drop the motion.")


def game_scanline_caps(game: str = "sonic4", repo: str = REPO) -> int:
    """`Game.SCANLINE_CAPS` for one game, read from its own config.

    Parsed rather than mirrored: the mask is a per-GAME declaration (sonic4 $01DE, demo 0),
    so there is no single value to carry and a stale copy would refuse or admit the wrong
    game. A missing declaration is a refusal and not a 0 — reading "no capabilities" out of
    a file this function failed to find is exactly how a capability check goes vacuous.
    """
    path = os.path.join(repo, "games", game, "config", "game.emp")
    try:
        with open(path, "r") as f:
            src = f.read()
    except OSError as e:
        _refuse(path, f"cannot read the game config to resolve Game.SCANLINE_CAPS: {e}. "
                      f"The capability check below would otherwise read as \"no "
                      f"capabilities declared\" and refuse every authored motion.")
    m = re.search(r"^\s*const SCANLINE_CAPS\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$",
                  src, re.M)
    if not m:
        _refuse(path, "no `const SCANLINE_CAPS = <literal>` declaration. Every game "
                      "declares the scanline services it wants lowered; without it the "
                      "capability check on `patch_motion` cannot run, and a check that "
                      "cannot run must not pass.")
    tok = m.group(1)
    return int(tok[1:], 16) if tok.startswith("$") else int(tok)


def declared_patch_channels(game: str = "sonic4", repo: str = REPO) -> dict:
    """{channel: [the source sites that consume it]} for one game's effects library.

    THE THREE CONSUMERS, and it is three rather than one. `Effects_LatchWorldLines` derives
    ONE screen line per channel and three things read it (engine/effects/raster.emp's own
    banner): the raster fire of a `patchable(..)` record, the parallax band split of a scene
    carrying `SceneAnchor.At(ch, ..)`, and the off-screen ship. A liveness check that looked
    only at `patchable()` — which is how the aeon artifact's §4c phrases it — would refuse a
    sweep that a scene anchor legitimately consumes, so both spellings are collected.

    IT IS A SUPERSET CHECK AND THE MESSAGE SAYS SO. Whether a given SECTION consumes a given
    channel depends on which raster program and which parallax config that section's
    `preset()` binds, and that binding lives in the hand-authored library and the act
    descriptor rather than in anything this generator reads. So this catches the channel
    NOTHING in the game consumes — channels 2 and 3 today — and not the channel some other
    section consumes. Named rather than silently ignored, because "checked and fine" and
    "not checkable" must not print the same.
    """
    channels = {}
    for site in walk_patch_sites(game, repo):
        channels.setdefault(site["channel"], []).append(
            f"{site['file']} {site['kind']}")
    return channels


def walk_patch_sites(game: str = "sonic4", repo: str = REPO) -> list:
    """Every channel-consuming site in one game's effects library, in file order.

    ONE WALK, TWO CONSUMERS, and the second one is why the bounds are kept. This walk
    used to read each `patchable(` for its `ch:` and DROP the `lo:`/`hi:` beside it —
    the only place in the repo where a band's screen extent is written down. Aurora's
    timeline strip could therefore author a sweep whose travel leaves its channel's
    band and say nothing, because the bounds were unknowable to it. They are now
    captured here and published by `render_channel_bands()`; see RASTER-CHBAND-1.

    THE WINDOW IS CLIPPED AT THE NEXT `patchable(`. The 400-char scan is the one this
    function has always used, but reading three fields out of it instead of one makes
    a cross-call read possible: a record missing its own `lo:` would otherwise silently
    inherit the NEXT record's bounds and publish a band nobody authored. Clipping means
    a missing bound is a refusal instead — see the `_refuse` below.
    """
    sites = []
    lib = os.path.join(repo, "games", game, "data", "effects")
    if not os.path.isdir(lib):
        return sites
    for name in sorted(os.listdir(lib)):
        if not name.endswith(".emp"):
            continue
        path = os.path.join(lib, name)
        with open(path, "r") as f:
            src = f.read()
        starts = [m.end() for m in re.finditer(r"patchable\s*\(", src)]
        for i, start in enumerate(starts):
            stop = min(start + 400, starts[i + 1] if i + 1 < len(starts) else len(src))
            window = src[start:stop]
            q = re.search(r"\bch\s*:\s*(-?\d+)", window)
            if not q:
                continue
            line = src.count("\n", 0, start) + 1
            lo = re.search(r"\blo\s*:\s*(-?\d+)", window)
            hi = re.search(r"\bhi\s*:\s*(-?\d+)", window)
            if not lo or not hi:
                _refuse(path, f"the `patchable(` at line {line} declares `ch: "
                              f"{q.group(1)}` but no "
                              f"{'`lo:`' if not lo else '`hi:`'} inside its own call. "
                              f"Every patchable record carries a band — "
                              f"`engine/effects/raster_dsl.emp` takes lo/hi as required "
                              f"arguments — so this is either a call this 400-char scan "
                              f"cannot see the end of, or a spelling it does not know. "
                              f"Refusing rather than publishing a channel with no band: "
                              f"the generated sidecar this walk feeds is the ONLY place "
                              f"an editor can learn a channel's screen extent, and a "
                              f"channel silently missing from it reads as \"no band "
                              f"declared\", which is the one answer that must never be "
                              f"guessed.")
            sites.append({"channel": int(q.group(1)), "file": name, "line": line,
                          "kind": "patchable()",
                          "lo": int(lo.group(1)), "hi": int(hi.group(1))})
        for m in re.finditer(r"SceneAnchor\s*\.\s*At\s*\(\s*(-?\d+)", src):
            sites.append({"channel": int(m.group(1)), "file": name,
                          "line": src.count("\n", 0, m.start()) + 1,
                          "kind": "SceneAnchor.At()", "lo": None, "hi": None})
    return sites


# THE TWO EDGES DO DIFFERENT THINGS, AND A CONSUMER TOLD OTHERWISE WILL WARN WRONG.
# Past `hi` Raster_BuildSchedule DROPS the record — no fire is emitted, so the band is
# not pinned to hi, it is GONE until the latched line comes back inside [lo, hi]. Below
# `lo` the record is still emitted, CLAMPED UP to the floor, because the frame-top ship
# covers the rows above. Deliberate, and asymmetric.
#
# THESE LINE NUMBERS ARE DERIVED, NOT WRITTEN DOWN. `Raster_GetChannelBand`'s own banner
# spent months citing :895-901 for this clamp and calling it symmetric (both corrected
# 2026-09-04); a sidecar that hardcoded the same two facts would rot the same way and
# take an editor's warning with it. So each edge is located by matching the INSTRUCTION
# in engine/effects/raster.emp, and a marker that stops matching — or matches twice — is
# a refusal, not a stale number quietly published to aurora.
_EDGE_MARKERS = (
    ("hi", "drop", r"^[ \t]*bgt[ \t]+\.suppress\b",
     "Past hi the record is NOT EMITTED this frame: no boundary is drawn anywhere and "
     "the band vanishes until the latched line re-enters [lo, hi]. It does NOT pin to hi."),
    ("lo", "clamp_up", r"^[ \t]*move\.w[ \t]+\(a0\), d2[ \t]*//[ \t]*clamp UP",
     "Below lo the record IS still emitted, clamped UP to lo, so the boundary pins at the "
     "top of the band and stays visible. The frame-top ship covers what is above it."),
)


def _edge_behaviour(repo: str = REPO) -> dict:
    """Each band edge's behaviour, with the engine line that implements it, located now."""
    path = os.path.join(repo, "engine", "effects", "raster.emp")
    with open(path, "r") as f:
        lines = f.read().splitlines()
    edges = {}
    for edge, behaviour, pattern, note in _EDGE_MARKERS:
        hits = [i + 1 for i, ln in enumerate(lines) if re.match(pattern, ln)]
        if len(hits) != 1:
            _refuse(path, f"the `{edge}` band edge's marker matched {len(hits)} lines "
                          f"(expected exactly 1) for /{pattern}/. This walk publishes "
                          f"`{behaviour}` at the {edge} edge to every editor that reads "
                          f"the generated channel-band sidecar, and it refuses to publish "
                          f"a behaviour it can no longer point at. If Raster_BuildSchedule "
                          f"changed, fix the marker AND re-read the asymmetry: the hi edge "
                          f"is a DROP and the lo edge is a CLAMP, and an editor that is "
                          f"told they are the same warns in the wrong direction.")
        edges[edge] = {"behaviour": behaviour, "note": note,
                       "engine": f"engine/effects/raster.emp:{hits[0]}"}
    return edges


def channel_bands_path(game: str = "sonic4", repo: str = REPO) -> str:
    """Where the generated read-only channel-band sidecar lives."""
    return os.path.join(repo, "games", game, "data", "generated",
                        "effects_channel_bands.json")


def render_channel_bands(game: str = "sonic4", repo: str = REPO) -> str:
    """The channel -> {lo, hi, source} sidecar, as JSON text. Reads only; writes nothing.

    WHAT IT IS FOR, in one sentence: `patchable(fires, ch, lo, hi)` is hand-authored `.emp`
    the editor cannot read, so aurora's timeline strip has no way to know that a sweep it
    just authored — peak `256 >> amp_shift` px, a document key it already holds — does not
    fit the band its channel is confined to. A 64 px sweep on a 40-line band was authorable
    and silent. This publishes the missing half of that comparison. Booked RASTER-CHBAND-1.

    IT IS DERIVED AND READ-ONLY. Nothing reads it back into the build; it is an export.
    That is exactly the shape that goes vacuous unnoticed, so two things watch it: a
    channel whose `patchable(` carries no `lo:`/`hi:` is a REFUSAL in `walk_patch_sites`
    (an empty map can therefore only mean a library with no `patchable(` at all), and the
    committed artifact is compared against a fresh render by `effects_gen.py check`, which
    build.sh runs build-fatally. An emptied sidecar is a red build, not a quiet export.
    """
    channels = {}
    for site in walk_patch_sites(game, repo):
        if site["lo"] is None:
            continue                      # SceneAnchor.At() consumes a channel, declares no band
        ch = str(site["channel"])
        if ch in channels:
            continue                      # guard 11 refuses two records on one channel; first wins
        channels[ch] = {
            "lo": site["lo"], "hi": site["hi"],
            "lines": site["hi"] - site["lo"] + 1,
            "source": f"games/{game}/data/effects/{site['file']}:{site['line']}",
        }
    doc = {
        "_generated_by": "GENERATED by tools/effects_gen.py. DO NOT EDIT; "
                         "run `effects_gen.py emit`.",
        "schema": "aeon-effects-channel-bands/1",
        "game": game,
        "units": "SCREEN LINES, 1:1 with the authored patchable(lo:, hi:). Not fire lines: "
                 "the engine subtracts 1 once, in Raster_BuildSchedule. Do not convert.",
        # ⚠ PEAK-TO-PEAK, NOT PEAK. The engine's own ladder ensure
        # (engine/effects/raster.emp:397) compares `2 * (SINE_AMPLITUDE >> shift)` against
        # SCREEN_HEIGHT -- the TRAVEL, not the excursion. This sentence said "peak excursion
        # (256 >> amp_shift)" until 2026-09-04 and was wrong by a factor of two IN THE
        # PERMISSIVE DIRECTION: on channel 1 (2 lines) an amp_shift of 7 gives excursion 2,
        # which "fits", and travel 4, which cannot -- so a warning written faithfully to the
        # old sentence green-lit the exact mistake this file exists to catch, on the narrower
        # of the two live channels. Found by the aurora lane before anything was built
        # against it.
        "how_to_use": "A sweep on channel c fits when its PEAK-TO-PEAK TRAVEL "
                      "(2 * (256 >> amp_shift), whole pixels) is <= channels[c].lines. "
                      "It is travel, not peak excursion: the engine's own ladder ensure "
                      "(engine/effects/raster.emp:397) compares 2 * (SINE_AMPLITUDE >> shift) "
                      "against the screen. `lines` is an INCLUSIVE COUNT of lines in [lo, hi], "
                      "and travel is a DISTANCE, so a sweep of travel == lines is the widest "
                      "that fits. THE TEST IS ONE-DIRECTIONAL: travel > lines is a CERTAIN "
                      "refusal and worth warning on; travel <= lines is CANNOT TELL, never a "
                      "clearance -- the latched line is (anchor - Camera_Y), so where the sweep "
                      "sits inside [lo, hi] is camera-dependent and unknowable at author time. "
                      "Leaving the band is NOT symmetric: read `edges` below before writing "
                      "the warning.",
        "edges": _edge_behaviour(repo),
        "channels": channels,
    }
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _check_patch_context(path: str, preset: dict, caps: int, live: dict, game: str) -> None:
    """The two refusals that need the GAME and not just the document.

    Both are silent no-ops rather than errors if they get through, which is the whole reason
    they are refusals: an author gets no comptime message, no crash and no wrong picture —
    just an effect that is not there.
    """
    motions = preset.get("patch_motion")
    if not isinstance(motions, list):
        return
    authored = [i for i, m in enumerate(motions) if m is not None]
    if not authored:
        return

    # (1) THE SEED/CAPABILITY MISMATCH — aeon artifact §4b.
    if (caps & CAP_ANCHOR_MOTION) == 0:
        _refuse(path, f"`patch_motion` authors channel(s) "
                      f"{', '.join(str(i) for i in authored)}, but game {game!r} does not "
                      f"raise CAP_ANCHOR_MOTION (${CAP_ANCHOR_MOTION:04X}) in its "
                      f"`Game.SCANLINE_CAPS` (games/{game}/config/game.emp). The two "
                      f"halves of the mover are gated DIFFERENTLY on purpose: "
                      f"`Effects_InstallPreset` seeds `Effects_Motion[]` from every preset "
                      f"unconditionally (34 bytes every game pays, preset.emp:333-340), "
                      f"while the latch loop that READS it is inside "
                      f"`if (Game.SCANLINE_CAPS & CAP_ANCHOR_MOTION) != 0` "
                      f"(engine/effects/raster.emp). So this sweep would be installed, "
                      f"folded into Effects_Motion_Any, and never read — the boundary does "
                      f"not move and nothing anywhere says why. Either raise the bit in "
                      f"that game's SCANLINE_CAPS, or stop authoring motion in a game that "
                      f"does not lower the mover.")

    # (2) CHANNEL LIVENESS — aeon artifact §4c, widened to all three consumers.
    for i in authored:
        if i in live:
            continue
        _refuse(path, f"`patch_motion[{i}]` authors a sweep on patch channel {i}, and "
                      f"NOTHING in games/{game}/data/effects consumes that channel: no "
                      f"`patchable(ch: {i}, ..)` record declares a band for it and no "
                      f"`SceneAnchor.At({i}, ..)` scene splits on it. "
                      f"`Effects_LatchWorldLines` would derive a swept screen line every "
                      f"frame and no consumer would read it, so the sweep costs cycles and "
                      f"moves nothing. Channels with a consumer today: "
                      f"{', '.join(str(c) for c in sorted(live)) or '(none)'}. "
                      f"This is a SUPERSET check — it can see that a channel is consumed "
                      f"SOMEWHERE in the game, not that the section binding this document "
                      f"is the place that consumes it, because which program and which "
                      f"parallax config a section binds lives in the hand-authored library "
                      f"and the act descriptor. A green here is not a promise the effect "
                      f"is visible; a red is a promise it is not.")


def load_all_presets(game: str = "sonic4", repo: str = REPO) -> dict:
    """All preset documents for a game, keyed by id. Empty dict when none exist.

    THE GAME-DEPENDENT CHECKS RUN HERE and not in `load_preset`, because they need the game
    and `load_preset` takes a path. Both are cheap and read-only, but they read the game's
    config and effects library once per bake rather than once per document.
    """
    paths = discover_preset_files(game, repo)
    presets = {}
    caps = live = None
    for path in paths:
        preset = load_preset(path)
        if preset["id"] in presets:
            _refuse(path, f"duplicate preset id {preset['id']!r}")
        if preset.get("patch_motion"):
            if caps is None:
                caps, live = game_scanline_caps(game, repo), \
                             declared_patch_channels(game, repo)
            _check_patch_context(path, preset, caps, live, game)
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


def render_drift(path: str, value, where: str) -> str:
    """`{"rate": <int>}` → `SceneDrift.Rate(<int>)`.

    THE UNIT IS 1/256 px PER FRAME, SIGNED — and this function deliberately does not
    convert it. The writer schema's `layer.drift.rate` (empyrean
    `contract/schema/aurora-effects-scene.schema.json`, `$defs.layer.drift`) is already
    in the engine's unit: `{"minimum": -4096, "maximum": 4096, "not": {"const": 0}}`,
    the exact bounds of `layer()`'s two drift `ensure`s in
    `engine/level/scene_dsl.emp`. The px/frame ↔ 1/256-px/frame conversion the design
    calls for (`docs/superpowers/specs/2026-08-29-band-drift-design.md` §7.1 mitigation
    2) happens in AURORA'S UI, on export, above the wire — so a multiply here would
    apply it twice and every authored rate would come out 256x too fast. The wire value
    goes to the constructor verbatim, sign included.

    WHY THE RANGE AND THE ZERO ARE NOT CHECKED HERE. Design §7 row 10 says it in as many
    words: "after it lands, the range is enforced by row 2's `ensure` at build time, not
    by the generator." `Rate(0)` and `Rate(9000)` are SHAPE-legal and this tool forwards
    them, because `layer()`'s messages are the field's real documentation — they state
    the unit, give the worked conversion (1 px/frame = 256) and name the corpus max —
    and a bound copied down here would be the second source that drifts. Same posture as
    every other slot; see `_render_int`'s SHAPE-vs-VALUE block.

    PER LAYER, NOT PER BAND, and the choice is the engine's rather than this tool's:
    `drift` is an argument of `layer()` and a scene layer IS a parallax band — one layer
    lowers to one `band_record`, so per-layer already spells everything per-band could.
    (`BAND_KEYS` in this file is the RASTER preset's scanline region, an unrelated use of
    the word.) The shipped hand-authored precedent gives all four OJZ canopy layers ONE
    rate on purpose — `games/sonic4/data/effects/ojz_scenes.emp`, chain 201 — because
    that art is one visual plane cut into four records and per-band rates would shear its
    full-height features at a band boundary. That is a choice an author makes by writing
    the same rate four times, which this key lets them do; it is not a reason to move the
    key up a level and take the other choice away.
    """
    rate = _single_arm(path, value, "rate", where)
    return f"SceneDrift.Rate({_render_int(path, rate, where + '.rate')})"


def render_row_remap(path: str, value, where: str) -> str:
    """`{"plane_y": N, "height_shift": N}` → `SceneRemap.Ladder(<Label>, N, N)`.

    THE PAYLOAD IS FLAT AND SPELLS NO VARIANT TAG, which is the house pattern rather than a
    shortcut: `drift` is `{"rate": N}`, `vsplit` is `{"at": N}`, `curve` is `{"to": F}`, and
    none of the three names its `SceneDrift.Rate` / `SceneVSplit.At` / `SceneCurve.To` tag.
    A `rowRemap` spelling `"ladder"` would be the first, for a variant with no sibling. It
    takes two fields rather than one, so it uses `_fields` where those three use `_single_arm`.

    BOTH NUMBERS ARE FORWARDED 1:1, VERBATIM, WITH NO UNIT CONVERSION — the standing rule on
    this seam (`patch_world_ys`' own banner: "there is no `* 256` anywhere on this path and
    there must never be one"). `height_shift` is where a helpful editor does the most damage:
    it is a SHIFT and `H = 1 << height_shift`, so an editor presenting "band height = 16
    lines" and exporting `16` asks for H = 65536. `scene_dsl.emp:1006` catches 16 because it
    is outside 3..7 — but every value 3..7 is legal, so a conversion bug inside that window
    lands as a band four times too tall rather than as a refusal. The editor may DISPLAY
    `1 << height_shift`; it must EXPORT the shift.

    ABSENT AND `"none"` BOTH EMIT NO ARGUMENT, which follows the three siblings in
    `render_layer` rather than the key-shape note's §5 table, and costs nothing to do so:
    `layer()`'s default is `SceneRemap.None` (scene_dsl.emp:860) and a NULL `brm_ladder` is
    the per-band gate (parallax.emp:419), so the two lower to the same eight bytes either
    way. The distinction is an authoring one, not a ROM one; making this one key emit an
    explicit `SceneRemap.None` where `curve`/`vsplit`/`drift` emit nothing would be a
    difference a reader has to explain with no byte behind it.
    """
    body = value
    if not isinstance(body, dict):
        _refuse(path, f"{where}: must be \"none\" or an object carrying plane_y and "
                      f"height_shift, got {type(body).__name__}")
    vals = _fields(path, body, ("plane_y", "height_shift"), where)
    plane_y, height_shift = vals
    if not isinstance(height_shift, int) or isinstance(height_shift, bool):
        _refuse(path, f"{where}.height_shift: must be an integer 3..7, got "
                      f"{height_shift!r}. IT IS A SHIFT, NOT A LINE COUNT: H = "
                      f"1 << height_shift, so 4 is a 16-line ladder and 6 is 64 lines. "
                      f"If you meant 64 LINES, you want 6.")
    if height_shift not in ROW_REMAP_LADDERS:
        _refuse(path, f"{where}.height_shift: {height_shift} has no ladder. `layer()` "
                      f"accepts shifts 3..7 (engine/level/scene_dsl.emp:1006), but only "
                      f"{', '.join(str(s) for s in sorted(ROW_REMAP_LADDERS))} "
                      f"{'has' if len(ROW_REMAP_LADDERS) == 1 else 'have'} a ladder the "
                      f"engine can generate today: `row_remap_ladder16()` "
                      f"(engine/level/parallax_dsl.emp:220) is the only one that exists, "
                      f"and its H is the module const ROW_REMAP_H16 = 16 rather than a "
                      f"parameter. Refusing here, by name, because the alternative is an "
                      f"emission that fails on an undefined Label and names a missing "
                      f"symbol instead of the thing you authored. The generated ladder for "
                      f"the other shifts is EFFECTS-W1 item 9b.")
    return (f"SceneRemap.Ladder({ROW_REMAP_LADDERS[height_shift]}, "
            f"{_render_int(path, plane_y, where + '.plane_y')}, "
            f"{_render_int(path, height_shift, where + '.height_shift')})")


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
    if not is_absent(layer.get("drift")):
        args.append(f"drift: {render_drift(path, layer['drift'], where + '.drift')}")
    if not is_absent(layer.get("rowRemap")):
        args.append("rowRemap: " + render_row_remap(
            path, layer["rowRemap"], where + ".rowRemap"))
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
    if "ramp" in preset:
        return render_ramp_preset(path, preset, names)
    if "base_swap" in preset:
        return render_base_swap_preset(path, preset, names)
    src, label = names.raster_src(pid), names.raster(pid)
    bands = [render_band(path, b, f"bands[{i}]")
             for i, b in enumerate(preset["bands"])]
    return (f"const {src} = compose([\n    "
            + ",\n    ".join(bands) + ",\n])\n"
            + f"pub data {label}: [u16; raster_words({src})] = raster_program({src})")


def render_fp16(path: str, value: dict, where: str) -> str:
    """One fp16 object → `fp16(whole, frac256)`, VERBATIM — clause 3 of the CR.

    Never a computed integer, never the raw 16.16 longword: fp16()'s own two ensures
    (whole -512..511, frac256 0..255, engine/effects/raster.emp:685-686) are the entire
    authored-range enforcement for a ramp's rate and starting offset, so the ONLY thing
    this function may do with `whole`/`frac256` is forward them into the `fp16(...)` call
    unchanged.
    """
    return ("fp16(" + _render_int(path, value["whole"], where + ".whole")
            + ", " + _render_int(path, value["frac256"], where + ".frac256") + ")")


def render_ramp_target(path: str, target: dict, where: str) -> str:
    """The `target` arm → the exact `vdp_comm(...)` word `raster_ramp_program` re-issues
    every line — clause 2 of the CR: NEVER a raw command word from the document, always
    built through `vdp_comm(addr, VdpTarget.Vsram, VdpOp.Write)` so the constructor's own
    discriminant ensures (`is_cram + is_vsram == 1`, raster.emp:652-653) see exactly the
    shape they expect. Only the `vsram` arm exists in this contract (§7.4); a `cram` arm
    is refused at LOAD time (`_check_ramp`), so this function only ever sees `vsram`.
    """
    vsram = target[RAMP_TARGET_ARM]
    addr = _render_int(path, vsram["addr"], where + f".{RAMP_TARGET_ARM}.addr")
    return f"vdp_comm({addr}, VdpTarget.Vsram, VdpOp.Write)"


def render_ramp_preset(path: str, preset: dict, names) -> str:
    """One `ramp` preset document → its CAP_DENSE_TIER ensure plus its
    `raster_ramp_program(...)` call, under the SAME `names.raster(pid)` label `bands`
    uses (EFFECTS-W1 DoD item 6, contract §7.4).

    ONE LABEL, EITHER SHAPE — this is what lets `{names.fn_sec_raster}` stay the single
    chooser bands already uses (clause 5 of the CR, effects_gen.py's own
    `RASTER_BINDING_BANNER`): the chooser only ever reads `names.raster(pid)` as a `Label`
    and neither knows nor cares whether the bytes behind it are a `[u16; N]` compose or a
    `RasterRampProgram` — so no second raster-channel writer is needed or added.

    THE ENSURE IS RE-EMITTED HERE, NOT ONCE GLOBALLY, because a comptime fn's free names
    resolve at the CALL SITE and `Game` does not travel into `raster_ramp_program`'s own
    body (docs/EMP_PITFALLS.md §2; the game-side precedent this mirrors verbatim is
    `games/sonic4/data/effects/ojz_effects.emp`'s own `OJZ_TestRamp` gate). Without a copy
    beside EVERY generated call site, a game that has not declared CAP_DENSE_TIER would
    build a `RasterRampProgram` the interpreter silently no-ops for, with no diagnostic
    anywhere (artifact §1.4/§3.3).
    """
    pid = preset["id"]
    label = names.raster(pid)
    ramp = preset["ramp"]
    top = _render_int(path, ramp["top"], "ramp.top")
    lines = _render_int(path, ramp["lines"], "ramp.lines")
    cmd = render_ramp_target(path, ramp["target"], "ramp.target")
    start = render_fp16(path, ramp["start"], "ramp.start")
    step = render_fp16(path, ramp["step"], "ramp.step")
    ensure = (
        f'ensure((Game.SCANLINE_CAPS & CAP_DENSE_TIER) != 0,\n'
        f'       "{label}: this game\'s Game.SCANLINE_CAPS ({{Game.SCANLINE_CAPS}}) does '
        f'not declare CAP_DENSE_TIER — EFFECTS-W1 item 6 gates construction of a '
        f'dense-tier RAMP program on that bit (engine/level/scene_dsl.emp), so a game '
        f'must declare intent to spend the dense tier\'s ramp axis before it may author '
        f'one. Add CAP_DENSE_TIER to this game\'s SCANLINE_CAPS in its config/game.emp")'
    )
    return (f"{ensure}\n"
            f"pub data {label}: RasterRampProgram = raster_ramp_program(\n"
            f"    top:   {top},\n"
            f"    lines: {lines},\n"
            f"    cmd:   {cmd},\n"
            f"    start: {start},\n"
            f"    step:  {step})")


def render_base_swap_preset(path: str, preset: dict, names) -> str:
    """One `base_swap` preset document → its `raster_program(...)` call (EFFECTS-W1 item
    11a's authorable half).

    NO CAPABILITY ENSURE IS RE-EMITTED HERE, unlike `render_ramp_preset` — and that
    asymmetry is a fact about the mechanism, not an oversight. `OP_SET_REG` is `fire()`'s
    cheapest op and dispatches UNCONDITIONALLY in every game (raster_dsl.emp's own `fire()`
    banner: it "used to be the chain's fall-through and the DEAREST op to dispatch, and it
    is now the cheapest"); there is no `CAP_*` bit anywhere in the tree that gates
    constructing a register-write raster op the way `CAP_DENSE_TIER` gates a ramp/gradient
    or `CAP_BAND_DRIFT` gates a drifting band — `games/sonic4/data/effects/ojz_effects.emp`'s
    own hand-authored `OJZ_BaseSwap` checks none either.

    Three calls, and they are the SAME three `OJZ_BaseSwap` already makes —
    `fire`/`reg_set`/`raster_program` — reused verbatim rather than reimplemented, per the
    brief's own instruction not to build a second constructor for a mechanism that already
    has one. `VdpBase`/`vdp_base_reg` come from `engine.vdp`, ambient in every placed
    module the same way `vdp_comm`/`VdpTarget`/`VdpOp` already are for `render_ramp_target`
    above (verified against the shipped `ramp_probe` fixture in the generated module,
    which calls `vdp_comm(...)` with no `use engine.vdp` line anywhere in this file).
    """
    pid = preset["id"]
    src, label = names.raster_src(pid), names.raster(pid)
    bs = preset["base_swap"]
    line = _render_int(path, bs["line"], "base_swap.line")
    target = _render_int(path, bs["target"], "base_swap.target")
    word = f"$8200 | vdp_base_reg(VdpBase.PlaneA, {target})"
    return (f"const {src} = [fire({line}, [reg_set({word})])]\n"
            f"pub data {label}: [u16; raster_words({src})] = raster_program({src})")


def render_cycle_channel(path: str, ch: dict, where: str) -> str:
    """One authored channel → its `cycle_channel(line:, first:, count:, period:, dir:)`.

    Every other number is forwarded VERBATIM: `line`'s 1..3, `first`'s 0..15 and the
    `first + count <= 16` span rule are all `cycle_channel()` ensures with the engine's own
    sentences, and none is repeated here.
    """
    period = ch["period"]
    if isinstance(period, bool) or not isinstance(period, int):
        _render_int(path, period, where + ".period")     # raises with the shape sentence
    if period < CYCLE_PERIOD_DOC_MIN:
        # THE ONE PLACE FORWARD-VERBATIM BREAKS, and it breaks because of the line above.
        # An authored `period: 1` would emit 0 and the engine would refuse "period 0
        # outside 1..255" — a number the author never wrote and cannot find in their file.
        _refuse(path, f"{where}.period is {period}, and the smallest period a document "
                      f"can carry is {CYCLE_PERIOD_DOC_MIN}. `period` here is in FRAMES, "
                      f"the author's unit — a rotation every {period} frame(s) — and the "
                      f"generator emits `period - 1` because the engine's timer rotates "
                      f"one frame later than the byte says. So {period} would emit "
                      f"{period - 1}, and the engine's own floor is "
                      f"{CYCLE_PERIOD_ENGINE_MIN}. The refusal is here, naming YOUR "
                      f"number, rather than one frame down naming a number you never "
                      f"wrote.")
    # ---- RIDER 5 PAIRING — engine/effects/palette.emp, `Palette_DoCycle`'s timer logic ----
    #
    # THE `- 1` BELOW IS HALF OF A PAIR AND THE OTHER HALF IS IN THE ENGINE.
    # `Palette_DoCycle` reloads the period byte when a channel's timer reaches 0 and rotates
    # on that frame, and `Palette_LoadCycle` seeds every timer to 0 — so `pc_period = P`
    # produces a rotation every `P + 1` frames, not every P. The document's `period` is the
    # AUTHOR's unit (frames between rotations), so this generator absorbs the off-by-one
    # (hub ruling Q7, empyrean docs/AURORA_EFFECTS_SCHEMA.md §7.2).
    #
    # empyrean §7.2 books RIDER 5: the runtime cadence fix. THE DAY IT LANDS, THIS LINE
    # BECOMES `period` UNCHANGED, IN THE SAME PARCEL. Split across two parcels, a generator
    # still emitting `period - 1` against a fixed runtime shifts EVERY authored cycle one
    # frame faster — silently. NOTHING GATES THAT: no test compares an authored period
    # against an observed cadence, there is no cycling row in tools/effects_budget_model.toml,
    # and no effects gate measures cycling at all. This comment is the only thing that will
    # tell the engine-side parcel it is about to break something. CYCLE_PERIOD_DOC_MIN above
    # moves with it (the floor is the engine's floor shifted by this same translation).
    args = [f"line: " + _render_int(path, ch["line"], where + ".line"),
            f"first: " + _render_int(path, ch["first"], where + ".first"),
            f"count: " + _render_int(path, ch["count"], where + ".count"),
            f"period: {period - 1}"]
    if "dir" in ch:
        args.append("dir: " + _render_int(path, ch["dir"], where + ".dir"))
    return "cycle_channel(" + ", ".join(args) + ")"


def render_variant(path: str, v: dict, where: str) -> str:
    """One authored variant → its `variant(...)` call.

    ABSENT FIELDS ARE OMITTED so the constructor's own defaults stand — the scene arm's
    rule (`test_absent_optional_scalars_are_omitted_so_constructor_defaults_stand`),
    applied here. The demand artifact's §3.2 illustration spells all seven arguments
    explicitly; omitting them instead is strictly better for the one thing item 5 has to
    prove, because it makes `{"shift_r": 1, "shift_g": 1}` emit the string
    `variant(shift_r: 1, shift_g: 1)` — character-for-character the hand
    `Variant_Water_Deep` call in games/sonic4/data/effects/ojz_effects.emp, so the text
    golden is a literal comparison with nothing to normalise.
    """
    args = [f"{k}: " + _render_int(path, v[k], f"{where}.{k}")
            for k in VARIANT_KEYS if k in v]
    return "variant(" + ", ".join(args) + ")"


def render_preset_cycle(path: str, preset: dict, names) -> str:
    """The `pub data` for one document's cycle script, or "" when it authors none.

    A `cycles: null` document emits NOTHING here: OFF is the sentinel `Pal_Cycle_None`,
    which the engine already ships, and minting a second zero-channel script per document
    would be two bytes of ROM per document saying what one shipped symbol says.
    """
    if not preset.get("cycles"):
        return ""
    chs = preset["cycles"]
    calls = [render_cycle_channel(path, ch, f"cycles[{i}]")
             for i, ch in enumerate(chs)]
    n = len(chs)
    return (f"pub data {names.cycle(preset['id'])}: PalCycleScript{n} = cycle_script{n}(\n"
            + "    [ " + ",\n      ".join(calls) + " ])")


def render_patch_motion(path: str, value, where: str) -> str:
    """One authored motion → its `anchor_sweep(amp_shift:, period_shift:[, phase:])`.

    FORWARD-VERBATIM, with the emphasis on VERBATIM. `amp_shift` and `period_shift` are
    base-2 logarithms on quantized ladders — seven amplitude rungs and nine period rungs,
    derived in raster_dsl.emp from the sine table and the screen height — so the difference
    between two adjacent legal values is a FACTOR OF TWO in travel or in period. Nothing
    here rounds, snaps, clamps or scales: an off-ladder value goes through untouched and
    `anchor_sweep()` refuses it with the derived ladder in the sentence, which is the only
    outcome that tells an author which rungs exist. (Contrast `render_cycle_channel`, which
    translates a unit and therefore owns a floor. This one translates nothing, so it owns
    nothing.)

    `phase` is OMITTED when the document omits it, so `anchor_sweep()`'s own default stands
    and the emitted text is character-for-character the shipped hand call in
    games/sonic4/data/effects/ojz_effects.emp — the scene arm's absent-optional rule, which
    makes the text golden a literal comparison with nothing to normalise.
    """
    body = _single_arm(path, value, PATCH_MOTION_ARM, where)
    args = [f"{k}: " + _render_int(path, body[k], f"{where}.{PATCH_MOTION_ARM}.{k}")
            for k in SWEEP_KEYS + SWEEP_OPTIONAL_KEYS if k in body]
    return "anchor_sweep(" + ", ".join(args) + ")"


def render_preset_variants(path: str, preset: dict, names) -> list:
    """The `pub data`s for one document's authored variant slots, in slot order.

    A `null` slot and an index the array does not reach both emit NOTHING — the first is
    a 0 in the chooser, the second is the chooser's `hand:`. Only an authored object mints
    a descriptor.
    """
    out = []
    for i, v in enumerate(preset.get("variants") or []):
        if v is None:
            continue
        out.append(f"pub data {names.variant(preset['id'], i)}: pal_variant = "
                   + render_variant(path, v, f"variants[{i}]"))
    return out


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
        # The other two EffectsPreset channels (EFFECTS-W1 item 5). PER-SLOT for the
        # variant chooser, and that is a choice with a reason: ruling Q5's three states are
        # PER INDEX (absent keeps `hand:`, null clears, an object authors), and a single
        # `-> [Label; 2]` chooser would have to express "keep the caller's hand value at
        # index 1 only" by indexing its own `hand:` array parameter. A per-slot chooser
        # spells that as the word `hand`. The `[Label; 2]` form is proven to reach the ROM
        # (docs/superpowers/probes/2026-09-02-item5-comptime-probe.md, verdict Q1) and is
        # the tidier shape for a pair that always moves together; it is not this one.
        self.fn_sec_cycle = f"{stem}_sec_cycle"
        self.fn_sec_variant = f"{stem}_sec_variant"
        # THE PATCH CHANNELS (EFFECTS-W1 item 4). Per-(sec, ch) for `fn_sec_variant`'s
        # reason exactly: the three states are PER INDEX, and a `-> [int; 4]` chooser would
        # have to express "keep the caller's hand value on channel 2 only" by indexing its
        # own `hand:` array parameter. A per-channel chooser spells that as the word `hand`.
        # They return `int` and not `Label` because a world Y and a packed sweep word are
        # VALUES, not addresses — `ep_patch_world_ys` / `ep_patch_motion` are inline
        # `[u16; RASTER_MAX_PATCH]` fields for the reason preset.emp states (a Label carries
        # no length, so the array-length ensure would be unevaluable and silently pass).
        self.fn_sec_patch_world_y = f"{stem}_sec_patch_world_y"
        self.fn_sec_patch_motion = f"{stem}_sec_patch_motion"
        self.binding_default = f"EditorSceneBinding_{cap}_Default"
        self.scene_array = f"EditorScenes_{cap}"
        self.equ_scenes = f"EditorScenes_{cap}_Count"
        self.equ_bindings = f"EditorScenes_{cap}_Bindings"
        # The RASTER binding witness. Capital `_Bindings` where a preset id is
        # `^[a-z]...` by SCENE_ID_RE, so it cannot collide with `raster(pid)` below —
        # the near-miss is deliberate (the prefix is what makes it read as the raster
        # channel's witness) and the regex is what makes it safe.
        self.equ_raster_bindings = f"EditorRaster_{cap}_Bindings"
        # The other two channels' witnesses, same mechanism and same reason: an equ is
        # minted only if the module is LOWERED, so a value of 0 is positive evidence the
        # module was reached and carries no binding, which is a DIFFERENT observation from
        # the symbol being absent.
        self.equ_cycle_bindings = f"EditorCycle_{cap}_Bindings"
        self.equ_variant_bindings = f"EditorVariant_{cap}_Bindings"
        self.equ_patch_bindings = f"EditorPatch_{cap}_Bindings"
        # The reels channel (item 10). Same near-miss as the raster witness and safe
        # for the same reason: `_Bindings` is capitalised and a scene id is
        # `^[a-z]...` by SCENE_ID_RE, so the witness cannot collide with `reels(sid)`.
        self.equ_reel_bindings = f"EditorReels_{cap}_Bindings"
        # THE ASSOCIATION TABLE, act-qualified for `raster()`'s reason: this generator
        # emits one module PER ACT and an unqualified name collides the day a second
        # act's module renders. `OJZ_Reels_Fill` names act 1's by hand today — whether
        # a second act needs a second table, or one global one, is aeon Q5 and is NOT
        # traced (docs/DEFERRED_WORK.md).
        self.reel_bindings = f"EditorReelBindings_{cap}"

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

    def cycle(self, preset_id: str) -> str:
        """The emitted cycle-script LABEL for one preset document. Act-qualified for
        `raster()`'s reason."""
        return f"EditorCycle_{self.cap}_{preset_id}"

    def variant(self, preset_id: str, slot: int) -> str:
        """The emitted variant LABEL for one document's slot. The SLOT is part of the
        name because the array is positional and two slots of one document are two
        descriptors, not one."""
        return f"EditorVariant_{self.cap}_{preset_id}_{slot}"

    def reels(self, scene_id: str) -> str:
        """The emitted rate-table LABEL for one authoring scene. Act-qualified for
        `raster()`'s reason, and named the way `EditorCycle_*`/`EditorVariant_*` are so
        the naming rule needed no invention."""
        return f"EditorReels_{self.cap}_{scene_id}"

    def reels_src(self, scene_id: str) -> str:
        """The UNANNOTATED source const the guard reads. `EditorRasterSrc_*`'s shape."""
        return f"EditorReelsSrc_{self.cap}_{scene_id}"

    def reels_ok(self, scene_id: str) -> str:
        """The guard's result, held in a const an `ensure` reads — an unreferenced
        top-level `const X = f(..)` is comptime-INERT (docs/EMP_PITFALLS.md §3)."""
        return f"EditorReelsOk_{self.cap}_{scene_id}"

    def descriptor_path(self, repo: str = REPO) -> str:
        """The act descriptor — the only place the section->preset edge is written.

        Derived from the zone/act ids by the tree's own convention rather than declared
        in project.json, which carries no path for it. A caller that cannot find it
        refuses WITHOUT a section number rather than inventing one.
        """
        return os.path.join(repo, "games", "sonic4", "data", "levels",
                            self.zone_id, self.act_id, "act_descriptor.emp")

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
                  sec_raster_refs: dict = None, repo: str = REPO) -> str:
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

    # ---- the OTHER TWO CHANNELS of the same documents (item 5) ----
    #
    # THERE IS NO SECOND SIDECAR KEY, and that is ruling Q1: one `rasterRef` binds the
    # WHOLE preset document, every channel it carries. The engine binds ONE preset record
    # per section and `ep_cycle` / `ep_variants` are fields of that record, so three refs
    # could name three documents the engine has one slot to put. `rasterRef` is therefore a
    # deliberate HISTORICAL SPELLING, from the day a preset document had only `bands`;
    # renaming it is a separate CR nobody has asked for, and `effectsRef` stays reserved
    # and unspent for the TOTAL binding, which still needs a palette reference `ep_pal`
    # cannot default.
    presets = presets or {}
    # The wrapper arities actually used, so the import line names only those.
    cycle_names = {len(presets[pid]["cycles"])
                   for pid in presets if presets[pid].get("cycles")}
    any_variants = any(
        any(v is not None for v in (presets[pid].get("variants") or []))
        for pid in presets)
    # EFFECTS-W1 item 6 — whether ANY document carries `ramp`, which decides two imports
    # below: the dense-tier wire types and CAP_DENSE_TIER's own home. Not a per-section
    # gate — every document with `ramp` re-emits its own `ensure` (render_ramp_preset), so
    # this flag only decides whether the generated module needs the names at all.
    any_ramp = any("ramp" in presets[pid] for pid in presets)
    # {section index: preset id} for the sections whose bound document carries each key.
    cycle_bound = {i: raster_bound[i] for i in raster_bound
                   if "cycles" in presets[raster_bound[i]]}
    variant_bound = {i: raster_bound[i] for i in raster_bound
                     if presets[raster_bound[i]].get("variants") is not None}
    # The patch channels ride the SAME `rasterRef`, ruling Q1 again: one ref binds the whole
    # document. Either key alone is enough to bind — a document may author only the seed
    # (a boundary that sits somewhere new but does not move) or, having kept the section's
    # hand anchor, only the motion.
    patch_bound = {i: raster_bound[i] for i in raster_bound
                   if ("patch_world_ys" in presets[raster_bound[i]]
                       or "patch_motion" in presets[raster_bound[i]])}

    # ---- (item 10) THE REELS KEY: refuse anything that is not a rung-1 binding ----
    #
    # See the REELS banner above for the mechanism. The three arms are the CR's ruling
    # (4) split by what the generator can see, and every one of them names the SECTION
    # rather than only the scene, because the section is what receives the wrong motion.
    reels_authored = sorted(sid for sid in scenes if REELS_KEY in scenes[sid])
    reels_bound = {}                        # section index -> scene id, rung 1 only
    if reels_authored:
        aliases = preset_parallax_bindings("sonic4", repo)
        sec_presets = section_preset_symbols(names, repo)
        for sid in reels_authored:
            spath = os.path.join(scene_dir("sonic4", repo), sid + ".json")
            rung1 = [i for i in sorted(bound) if bound[i] == sid]
            if act_ref == sid:
                fallthrough = sorted(set(range(sections)) - set(bound))
                _refuse(spath,
                        f"scene {sid!r} carries a `{REELS_KEY}` key AND is this act's "
                        f"DEFAULT scene ({PROJECT_JSON}'s `{ACT_SCENE_REF_KEY}`), which "
                        f"is Effects_ResolveParallax's RUNG 3. The act default is ONE "
                        f"lowered record shared by every section that falls through to "
                        f"it — here section(s) "
                        f"{', '.join(str(i) for i in fallthrough) or '(none)'} do not "
                        f"bind a scene at rung 1, so each resolves to this same pointer "
                        f"unless its own preset binds `ep_parallax` (rung 2). A reels "
                        f"table keyed on a shared pointer hands all of them one "
                        f"section's motion, silently. Bind the scene per section with a "
                        f"`{ACT_SCENE_REF_KEY}` sidecar, or drop the `{REELS_KEY}` key.")
            if not rung1:
                _refuse(spath,
                        f"scene {sid!r} carries a `{REELS_KEY}` key but no section binds "
                        f"it with a `{ACT_SCENE_REF_KEY}` sidecar, so it is never "
                        f"Effects_ResolveParallax's rung 1 and the binding table would "
                        f"have no config pointer to key on. Reels bind to a SECTION's "
                        f"lowered record, not to a scene in the library — assign the "
                        f"scene to a section, or drop the key.")
            emitted = {names.binding_sec(i) for i in rung1}
            hits = [a for a in aliases if a["target"] in emitted]
            if hits:
                # EVERY alias, not the first: a refusal that stopped at one would send
                # an author round the loop once per preset, and the set is what says
                # whether the fix is one `parallax:` argument or a shared record.
                where = []
                owners = set()
                for a in hits:
                    mine = sorted(i for i, p in sec_presets.items()
                                  if p == a["preset"])
                    owners |= set(mine)
                    where.append(f"`{a['preset']}` ({a['file']}:{a['line']}) -> "
                                 f"`{a['target']}`")
                who = (f"section(s) {', '.join(str(i) for i in sorted(owners))}"
                       if owners else
                       f"section(s) UNKNOWN — {names.descriptor_path(repo)} could not "
                       f"be read to attribute the preset(s)")
                _refuse(spath,
                        f"scene {sid!r} carries a `{REELS_KEY}` key, but its lowered "
                        f"record is ALSO named by a hand-authored preset's "
                        f"`parallax:` argument — {'; '.join(where)} — which is "
                        f"Effects_ResolveParallax's RUNG 2, bound by {who}. Those "
                        f"sections resolve to the SAME pointer this scene's own "
                        f"section does, so the reels binding table would hand them "
                        f"this scene's motion rather than none. Point those presets' "
                        f"`parallax:` at a record of their own, or drop the "
                        f"`{REELS_KEY}` key.")
            for i in rung1:
                reels_bound[i] = sid

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
                   "BAND_EXT_N, band_curve, BAND_CURVE_N, band_drift, BAND_DRIFT_N, band_remap, BAND_REMAP_N}")
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
    # THE PALETTE WIRE-FORMAT STRUCTS (item 5). `engine.effects.palette_dsl` is a sigil
    # COMPTIME_HELPERS member and is glob-injected into every placed module, so
    # `variant()` / `cycle_channel()` / `cycle_scriptN()` need no import — but
    # `engine.effects.palette` is a PLACED module and its struct names do. A comptime fn's
    # struct-literal field values resolve at the EMISSION site's scope
    # (engine/effects/palette_dsl.emp's banner), which is why the hand library imports the
    # same two halves. `pal_cycle_channel` rides with the wrapper for
    # docs/EMP_PITFALLS.md §8's reason: a struct declaration is re-elaborated in every
    # module that imports one that contains it.
    #
    # EMITTED ONLY WHEN A DOCUMENT CARRIES THE KEY, so the no-content bake and every bake
    # of the pre-item-5 documents stay TEXT-IDENTICAL and the four-CRC check stays a real
    # check (the `bands` arm's rule, one channel over).
    # THE REELS IMPORTS (item 10). `REEL_BAND_COUNT` types the rate tables and
    # `reel_rates_ok` is the ONE guard every rate table in the tree routes through, both
    # from games.sonic4.constants — which imports nothing game-side, so this edge cannot
    # cycle the way an import of games.sonic4.ojz_effects would (that module imports
    # THIS one). EMITTED ONLY WHEN A SCENE AUTHORS `reels`, the `cycles`/`variants`
    # rule: with no reels key the bake stays text-identical apart from the always-
    # emitted binding table below.
    if reels_bound:
        out.append("use games.sonic4.constants.{REEL_BAND_COUNT, reel_rates_ok}")
    if cycle_names:
        out.append("use engine.effects.palette.{pal_cycle_channel, "
                   + ", ".join(f"PalCycleScript{n}" for n in sorted(cycle_names)) + "}")
    if any_variants:
        out.append("use engine.effects.palette.{pal_variant}")
    # THE DENSE-TIER WIRE TYPES (item 6). `engine.effects.raster` is NOT a
    # COMPTIME_HELPERS module (ojz_effects.emp imports these explicitly, the same
    # precedent `pal_cycle_channel`'s own comment two lines up follows for `palette`), so
    # they need an explicit import here too — and NOT JUST the three names the call site
    # spells: `raster_ramp_program`'s OWN BODY is free names that resolve at ITS call
    # site (docs/EMP_PITFALLS.md §2), so this list is every name that body references —
    # `OP_RUN_RAMP`, `RASTER_ARM_EVERY_LINE`, `RASTER_ARM_PARK`, `RASTER_OPS_END` and
    # `raster_arm` — the EXACT set `ojz_effects.emp` itself imports (its own two `use
    # engine.effects.raster.{...}` lines) for the same constructor, for the same reason.
    # Missing even one of these degrades silently into a link extern that only shows up
    # as `expected an integer for u16, got label` at EMIT time, not at this file's own
    # shape checks — measured red-first while writing this arm.
    #
    # `CAP_DENSE_TIER` lives in `engine.level.scene_dsl`, already glob-imported above
    # whenever `used` is non-empty (`use engine.level.scene_dsl.*`) — a SECOND explicit
    # import of the same name would be redundant, so this only adds one when a ramp
    # document exists with NO scene bound at all (a preset needs no scene to emit —
    # TestPresetsInTheGeneratedModule's own rule, one channel over).
    #
    # EMITTED ONLY WHEN A DOCUMENT CARRIES `ramp`, the `cycles`/`variants` rule one channel
    # over: with no ramp document the no-content bake and every pre-item-6 bake stay
    # TEXT-IDENTICAL and the four-CRC check stays a real check.
    if any_ramp:
        out.append("use engine.effects.raster.{RasterRampProgram, raster_ramp_program, "
                   "fp16, OP_RUN_RAMP, RASTER_ARM_EVERY_LINE, RASTER_ARM_PARK, "
                   "RASTER_OPS_END, raster_arm}")
        if not used:
            out.append("use engine.level.scene_dsl.{CAP_DENSE_TIER}")
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

    # ---- (item 10) THE REEL RATE TABLES AND THE ASSOCIATION TABLE ----
    #
    # ALWAYS EMITTED, unlike the raster/palette arms above, and for a mechanical reason
    # rather than a stylistic one: `OJZ_Reels_Fill` (games/sonic4/data/effects/
    # ojz_effects.emp) names the association table in a `lea`, so the symbol has to
    # EXIST in every bake or the game does not link. With no authored reels it is one
    # terminator long — 4 bytes in the DEBUG shape, ZERO in release.
    out.append(REELS_BANNER)
    reels_emit = f"REEL_RATE_EMIT_LEN_{names.cap}"
    if reels_bound:
        # Guarded with the tables it lengths, not emitted unconditionally: its
        # `REEL_BAND_COUNT` arrives on the `use games.sonic4.constants` line above,
        # which is itself emitted only when a scene authors the key.
        out.append(f"const {reels_emit} = "
                   f"if DEBUG == 1 {{ REEL_BAND_COUNT }} else {{ 0 }}")
        out.append("")
    for i in sorted(reels_bound):
        sid = reels_bound[i]
        rates = scenes[sid][REELS_KEY][REELS_RATES_KEY]
        # DOCUMENT ORDER, VERBATIM. Index i owns column-pairs 4i..4i+3, i.e. screen X
        # 64i..64i+63, and that mapping lives in a hardcoded `lsr.b #2` the JSON cannot
        # see. Sorting, reversing, or round-tripping this array through a dict keyed by
        # band name silently relocates every strip (CR §2.7, "what the schema cannot
        # express", item 1).
        lit = "[" + ", ".join(str(r) for r in rates) + "]"
        src, ok, tbl = (names.reels_src(sid), names.reels_ok(sid), names.reels(sid))
        out.append(f"// section {i} <- scene {sid}: {lit} px/frame, left to right")
        # UNANNOTATED ON PURPOSE. `reel_rates_ok`'s magnitude arm must see the RAW
        # authored ints: whether sigil refuses an out-of-`i8` literal in an `[i8; N]`
        # initializer is NOT ESTABLISHED, and if it silently narrowed instead, a
        # `[i8; N]`-typed source would hand the guard an already-truncated value and the
        # one check that catches Aurora's x256 drift-export mistake would pass
        # vacuously. The length contract is carried by the guard and by the `pub data`.
        out.append(f"const {src} = {lit}")
        out.append(f"const {ok} = reel_rates_ok({src}, REEL_BAND_COUNT)")
        out.append(f'ensure({ok} == REEL_BAND_COUNT,\n'
                   f'       "{tbl}: reel_rates_ok checked {{{ok}}} rates, not the '
                   f'REEL_BAND_COUNT ({{REEL_BAND_COUNT}}) OJZ_Reels_Fill walks — a '
                   f'guard that examined a different number of rates than the loop '
                   f'reads is gating the wrong table")')
        out.append(f"pub data {tbl}: [i8; {reels_emit}] = "
                   f"if DEBUG == 1 {{ {src} }} else {{ [] }}")
        out.append("")
    # EVEN, and load-bearing: REEL_BAND_COUNT is odd today, so an odd number of rate
    # tables leaves the pointer table below on an odd address — and a `move.l` through
    # an odd address is a 68000 ADDRESS ERROR, not a warning. `align 2` on an
    # already-even address costs nothing, so it is unconditional.
    out.append("align 2")
    # `extern("Name")` AND NOT A BARE NAME, measured rather than chosen: a bare label
    # inside a `[*u8; N]` array literal does not resolve, even for a symbol declared in
    # this same module ten lines up — `unknown name EditorSceneBinding_OJZ_Act1_Sec4`,
    # sigil 0a58f2ec, 2026-09-04. `extern()` is how every address table in the tree
    # spells its entries (games/sonic4/player/characters.emp's `CharacterDefs`, the
    # generated bg_anim.emp's bank tables), which is why the idiom exists.
    pairs = []
    for i in sorted(reels_bound):
        pairs.append(f'extern("{names.binding_sec(i)}"), '
                     f'extern("{names.reels(reels_bound[i])}")')
    pairs.append("0")
    bind_emit = f"REEL_BINDING_EMIT_LEN_{names.cap}"
    out.append(f"const {bind_emit} = if DEBUG == 1 {{ {2 * len(reels_bound) + 1} }} "
               f"else {{ 0 }}")
    out.append(f"pub data {names.reel_bindings}: [*u8; {bind_emit}] = "
               f"if DEBUG == 1 {{ [" + ", ".join(pairs) + "] } else { [] }")
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

    # ---- the PALETTE channels from the same documents (item 5) ----
    # Same "appends nothing at all" rule as the raster arm above, one channel over: a tree
    # whose documents carry neither key renders the same TEXT it rendered before item 5.
    palette_decls = []
    for pid in sorted(presets):
        ppath = os.path.join(preset_dir(), pid + ".json")
        cyc = render_preset_cycle(ppath, presets[pid], names)
        if cyc:
            palette_decls.append(cyc)
        palette_decls.extend(render_preset_variants(ppath, presets[pid], names))
    if palette_decls:
        out.append(PALETTE_BANNER)
        for decl in palette_decls:
            out.append(decl)
            out.append("")

    # ---- the witness equates (zero ROM bytes, link-visible) ----
    out.append(WITNESS_BLOCK.format(
        equ_scenes=names.equ_scenes, scenes=len(used),
        equ_bindings=names.equ_bindings,
        bindings=len(bound) + (1 if act_ref else 0),
        equ_raster_bindings=names.equ_raster_bindings,
        raster_bindings=len(raster_bound),
        equ_cycle_bindings=names.equ_cycle_bindings,
        cycle_bindings=len(cycle_bound),
        equ_variant_bindings=names.equ_variant_bindings,
        variant_bindings=len(variant_bound),
        equ_patch_bindings=names.equ_patch_bindings,
        patch_bindings=len(patch_bound),
        equ_reel_bindings=names.equ_reel_bindings,
        reel_bindings=len(reels_bound)))
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
    out.append("")

    # ---- (e) THE OTHER TWO PRESET CHANNELS' CHOOSERS — always emitted (item 5) ----
    out.append(PALETTE_BINDING_BANNER)
    out.append(f"pub comptime fn {names.fn_sec_cycle}(sec: int, hand: Label = 0) "
               f"-> Label {{")
    out.append(f'    ensure(sec >= 0 && sec < {sections}, "{names.fn_sec_cycle}(sec: '
               f'{{sec}}): this act has {sections} sections, so there is no binding '
               f'slot for that index — the section preset and project.json\'s grid '
               f'have drifted apart")')
    out.append("    comptime var out = hand")
    for i in sorted(cycle_bound):
        pid = cycle_bound[i]
        # `cycles: null` = OFF, and OFF is the engine's sentinel, never 0. `Pal_Cycle_None`
        # is a FREE NAME here and resolves at the CALL SITE (docs/EMP_PITFALLS.md §2) —
        # the same rule that makes `hand:` a parameter. The call site is the game's own
        # effects library, which already imports it for its hand-authored presets.
        target = (names.cycle(pid) if presets[pid]["cycles"] else "Pal_Cycle_None")
        out.append(f"    if sec == {i} {{ out = {target} }}")
    out.append("    return out")
    out.append("}")
    out.append("")
    out.append(f"pub comptime fn {names.fn_sec_variant}(sec: int, slot: int, "
               f"hand: Label = 0) -> Label {{")
    out.append(f'    ensure(sec >= 0 && sec < {sections}, "{names.fn_sec_variant}(sec: '
               f'{{sec}}): this act has {sections} sections, so there is no binding '
               f'slot for that index — the section preset and project.json\'s grid '
               f'have drifted apart")')
    # The literal below is PAL_MAX_VARIANTS, inlined for SECTION_PIN's reason: a comptime
    # fn's free names resolve at the CALL SITE, so a named engine constant here would
    # resolve in the effects library's scope or silently not at all.
    out.append(f'    ensure(slot >= 0 && slot < {PAL_MAX_VARIANTS}, '
               f'"{names.fn_sec_variant}(slot: {{slot}}): the engine has '
               f'{PAL_MAX_VARIANTS} palette variant staging slots (PAL_MAX_VARIANTS) — '
               f'Palette_SetVariant masks the index with a power-of-two mask, so a '
               f'higher slot would fold back onto slot 0")')
    out.append("    comptime var out = hand")
    for i in sorted(variant_bound):
        pid = variant_bound[i]
        for slot, v in enumerate(presets[pid]["variants"]):
            # A `null` slot CLEARS, and clear is 0 — the engine's own "unused slots
            # 0 = clear". An index the array does not reach emits no row at all, which
            # is how "keep the hand value" is spelled.
            target = "0" if v is None else names.variant(pid, slot)
            out.append(f"    if sec == {i} && slot == {slot} {{ out = {target} }}")
    out.append("    return out")
    out.append("}")

    # ---- (f) THE PATCH CHANNELS' CHOOSERS — always emitted (item 4) ----
    out.append("")
    out.append(PATCH_BINDING_BANNER)
    for fn, key, sentinel, render in (
            (names.fn_sec_patch_world_y, "patch_world_ys", PATCH_ANCHOR_NONE, None),
            (names.fn_sec_patch_motion, "patch_motion", ANCHOR_MOTION_NONE,
             render_patch_motion)):
        # THE DEFAULT IS THE SENTINEL AS A LITERAL, and both halves of that are deliberate.
        # It is the SENTINEL and not 0 because 0 is a real world Y — `anchor - Camera_Y` at
        # 0 reads as above the screen top, the most invasive state a channel nobody asked
        # for can have (raster_dsl.emp's PATCH_ANCHOR_NONE note). It is a LITERAL because a
        # comptime fn's free names resolve at the CALL SITE (docs/EMP_PITFALLS.md §2): a
        # default parameter is the one position in the signature where that rule has never
        # been measured either way, so this file does not bet on it. The BODIES below do use
        # the named constants, which IS the proven case — `Pal_Cycle_None` has ridden the
        # cycle chooser's body since item 5, and `engine.effects.raster_dsl` is a sigil
        # COMPTIME_HELPERS member glob-injected into every placed module, so
        # PATCH_ANCHOR_NONE / ANCHOR_MOTION_NONE / anchor_sweep are ambient wherever this
        # module lands and wherever it is called from.
        out.append(f"pub comptime fn {fn}(sec: int, ch: int, hand: int = {sentinel}) "
                   f"-> int {{")
        out.append(f'    ensure(sec >= 0 && sec < {sections}, "{fn}(sec: '
                   f'{{sec}}): this act has {sections} sections, so there is no binding '
                   f'slot for that index — the section preset and project.json\'s grid '
                   f'have drifted apart")')
        # RASTER_MAX_PATCH inlined for SECTION_PIN's reason, one channel over from the
        # variant chooser's PAL_MAX_VARIANTS: a named engine constant here would resolve in
        # the effects library's scope or silently not at all.
        out.append(f'    ensure(ch >= 0 && ch < {RASTER_MAX_PATCH}, "{fn}(ch: {{ch}}): '
                   f'the engine has {RASTER_MAX_PATCH} patch channels '
                   f'(RASTER_MAX_PATCH) — the runtime patcher masks the channel index '
                   f'with RASTER_MAX_PATCH minus 1, so a higher channel would fold back '
                   f'onto channel 0")')
        out.append("    comptime var out = hand")
        for i in sorted(patch_bound):
            pid = patch_bound[i]
            for ch, v in enumerate(presets[pid].get(key) or []):
                # `null` is the ENGINE SENTINEL and never 0, on both keys — the same rule
                # `cycles: null -> Pal_Cycle_None` follows. An index the array does not
                # reach emits no row at all, which is how "keep the hand value" is spelled.
                if v is None:
                    target = "PATCH_ANCHOR_NONE" if key == "patch_world_ys" \
                             else "ANCHOR_MOTION_NONE"
                elif render is None:
                    # WHOLE PIXELS, INTERPOLATED VERBATIM. No `* 256`, no `>> 8`, no offset:
                    # this is the one field whose unit differs from item 3's `drift.rate`
                    # and the whole failure mode is that a conversion looks harmless.
                    target = _render_int(os.path.join(preset_dir(), pid + ".json"), v,
                                         f"{key}[{ch}]")
                else:
                    target = render(os.path.join(preset_dir(), pid + ".json"), v,
                                    f"{key}[{ch}]")
                out.append(f"    if sec == {i} && ch == {ch} {{ out = {target} }}")
        out.append("    return out")
        out.append("}")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


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
// EVERY `pub comptime fn` AT THE BOTTOM IS EMITTED FOR EVERY ACT, ALWAYS — the act
// default, the section scene, and one per `EffectsPreset` channel (raster, cycle,
// variant, patch world Y, patch motion) —
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
// is in the target's `use` closure — so the presence of these names in the
// listing is positive evidence that `act_descriptor.emp`'s import edge is live. That
// matters because an unreached `.emp` module gets ZERO body elaboration: every guard
// below, including the budget fold, builds green while asserting nothing. Measured
// on this very module (2026-08-22): with the descriptor's `use` line removed, an
// `ensure(1 == 0)` here built GREEN with an unchanged CRC.
pub equ {equ_scenes} = {scenes}
pub equ {equ_bindings} = {bindings}
pub equ {equ_raster_bindings} = {raster_bindings}
pub equ {equ_cycle_bindings} = {cycle_bindings}
pub equ {equ_variant_bindings} = {variant_bindings}
pub equ {equ_patch_bindings} = {patch_bindings}
pub equ {equ_reel_bindings} = {reel_bindings}\
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

REELS_BANNER = """\
// ---- AURORA-AUTHORED REEL RATES + THE BINDING TABLE (item 10, DEBUG TIER) ----
//
// The scene document's `reels: { "rates": [..] }` key. One `[i8; REEL_BAND_COUNT]` per
// authoring scene, plus the flat (config label, rates label) list `OJZ_Reels_Fill`
// walks against `Parallax_Current_Config` to pick a table — on a miss it keeps
// `OJZ_Reel_Speed`, so the built-in demo and tools/reels_witness.py go on working.
//
// A RATE IS SIGNED WHOLE PIXELS PER FRAME, and there is no fixed point anywhere on this
// path: `add.b (a2)+, d0` adds the authored byte straight into the strip's phase. This
// is NOT item 3's `drift.rate`, which is 1/256 px per frame with the editor multiplying
// by 256 on export — that conversion applied here emits 768 for an intended 3. Rates
// are emitted in DOCUMENT ORDER, verbatim: index i owns column-pairs 4i..4i+3, screen X
// 64i..64i+63, and that mapping is a hardcoded `lsr.b #2` the JSON cannot see.
//
// EVERYTHING HERE IS INSIDE `if DEBUG == 1` AND EMITS ZERO BYTES IN RELEASE, which is
// the CR's ruling (1) carried as a prohibition rather than a caveat: nothing in the
// release shape can set `OJZ_Reel_Active` (its only writer is tools/reels_witness.py
// poking a DEBUG-only RAM cell), so a release emission would be a dormant scaffold in
// the ROM the owner ships. Promotion is the owner's parked question and nothing here
// designs it.
//
// THE BINDING TABLE IS ALWAYS EMITTED even with no authored reels — `OJZ_Reels_Fill`
// names it in a `lea`, so the symbol must exist in every bake — and is then one
// terminator long. Everything above it is emitted only when a scene authors the key.
//
// EVERY RATE TABLE ROUTES THROUGH `reel_rates_ok` (games/sonic4/config/constants.emp),
// the same fn the hand-written table uses, so the length / magnitude / distinctness
// rules travel instead of being copied. The generator repeats NONE of them: it checks
// SHAPE (the key set, the element type, the array's LENGTH against REEL_BAND_COUNT
// re-derived from constants.emp) and leaves the values to sigil.\
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

PALETTE_BANNER = """\
// ---- AURORA-AUTHORED PALETTE CYCLES AND VARIANTS, through the REAL constructors ----
//
// The other two `EffectsPreset` channels the same preset documents carry (EFFECTS-W1 DoD
// item 5; the shape is empyrean docs/AURORA_EFFECTS_SCHEMA.md §7.2). One `pub data` per
// authored cycle script and one per authored variant SLOT — the `variants` array is
// positional, so slot 0 and slot 1 of one document are two descriptors under two names.
//
// ⚠ `cycles` HERE IS PALETTE CYCLING — the CRAM-span rotation Palette_DoCycle performs.
// It is NOT the DEBUG hotkey's raster cycle table (RASTER_CYCLE_COUNT), which steps a
// human through raster PROGRAMS. Said once, here, per hub ruling Q10.
//
// THE `period` ON EVERY cycle_channel BELOW IS AN ENGINE BYTE, ONE LESS THAN THE DOCUMENT
// SAYS. The document's `period` is in frames, the author's unit; the engine's timer
// rotates one frame later than the byte, so the generator emits `period - 1` (ruling Q7).
// Reading the two numbers as a contradiction is the mistake this note exists to prevent —
// see the RIDER 5 PAIRING block in tools/effects_gen.py's `render_cycle_channel`.
//
// Every `ensure` in variant() and cycle_channel() fires on authored content HERE, because
// a `pub data` in a lowered module is elaborated unconditionally. Not one of their ranges
// is restated in the generator.\
"""

PALETTE_BINDING_BANNER = """\
// ---- THE PALETTE BINDINGS — the same seam, the other two channels ----
//
// Two more always-emitted choosers beside the raster one, called from the same place: the
// section's own `preset()` in games/sonic4/data/effects/ojz_effects.emp. There is no
// second sidecar key — ONE `rasterRef` binds the WHOLE preset document, every channel it
// carries (ruling Q1), because the engine binds one preset RECORD per section and
// `ep_cycle` / `ep_variants` are fields of it.
//
// `hand:` IS THE CALLER'S, AND FOR `cycle:` IT IS `Pal_Cycle_None`, NEVER 0. NULL cannot
// mean "off" while it also means "keep" (ARCH §7.12), which is why the engine ships a
// non-NULL zero-channel sentinel. For a variant slot the `hand:` is whatever the section
// carries today — for every OJZ section that is `Variant_Water_Deep` in slot 0 and 0 in
// slot 1 — and this is LOAD-BEARING: a document that said nothing and cleared the slots
// would drop the act-wide water tint at the first crossing.
//
// THE VARIANT CHOOSER IS PER-SLOT because ruling Q5's three states are per INDEX: an
// index the array does not reach keeps `hand:`, `null` clears, an object authors. A
// single `[Label; 2]`-returning chooser would have to index its own `hand:` array to say
// "keep the caller's value at slot 1 only"; per-slot spells it as the word `hand`.
//
// With no document carrying either key the bodies below are `return out` over an
// unmodified `hand`, and this whole block is zero ROM bytes — a `pub comptime fn` emits
// nothing.\
"""

PATCH_BINDING_BANNER = """\
// ---- THE PATCH-CHANNEL BINDINGS — the anchor mover's authoring seam (item 4) ----
//
// Two more always-emitted choosers on the same seam, called from the same `preset()` in
// games/sonic4/data/effects/ojz_effects.emp. They return `int` and not `Label`, because a
// world Y and a packed sweep word are VALUES: `ep_patch_world_ys` and `ep_patch_motion` are
// inline `[u16; RASTER_MAX_PATCH]` fields, which is what gives preset() a `.len` it can
// check (engine/effects/preset.emp).
//
// ⚠ `patch_world_ys` IS WHOLE PIXELS AND NEITHER SIDE CONVERTS — 1:1, editor to ROM. This
// is NOT item 3's `drift.rate`, which is 1/256 px per frame with the editor multiplying by
// 256 on export. A world Y carried through that habit lands 256x down the level;
// `Effects_LatchWorldLines` derives the screen line as `anchor - Camera_Y`, so the band
// simply never appears and nothing reports it. There is no `* 256` anywhere on this path
// and there must never be one.
//
// ⚠ THE SWEEP FIELDS ARE BASE-2 LOGARITHMS ON QUANTIZED LADDERS — seven amplitude rungs
// (peak = 256 >> amp_shift px) and nine period rungs (cycle = 256 << period_shift ticks),
// derived in engine/effects/raster_dsl.emp from the sine table and the screen height. The
// generator forwards them VERBATIM and refuses nothing about their values: adjacent rungs
// differ by a factor of two, so rounding one silently doubles or halves the motion where
// `anchor_sweep()`'s own ensure prints the whole ladder.
//
// `hand:` IS THE CALLER'S, and its default here is the ENGINE SENTINEL and never 0 — 0 is a
// real world Y, and it is the worst one: it reads as ABOVE the screen top, i.e. fully
// submerged, for a channel nobody asked for.
//
// WHAT THIS SEAM CANNOT CHECK, said here because the author gets no comptime error for any
// of it: (a) a sweep's peak-to-peak travel must fit its channel's `patchable(lo, hi)` band,
// and above `hi` Raster_BuildSchedule DROPS the record rather than clamping — the band
// vanishes for the frame. `lo`/`hi` live in the raster program and the amplitude in the
// preset, associated by a pointer at runtime, so no comptime scope holds both;
// tools/test_anchor_sweep_band.py is that scope. (b) whether the SECTION binding this
// document is one of the places the channel is actually consumed — the generator checks
// only that the game consumes it somewhere.
//
// With no document carrying either key the bodies below are `return out` over an unmodified
// `hand`, and this whole block is zero ROM bytes — a `pub comptime fn` emits nothing.\
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
        load_section_raster_refs(repo, zone, act),
        repo)


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
            band_path, band_text = channel_bands_path(), render_channel_bands()
            _atomic_write(band_path, band_text)
            print(f"effects_gen: wrote {os.path.relpath(band_path, REPO)}")
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
            # THE SIDECAR RIDES THE SAME GATE, and it needs one because nothing in the
            # build READS it — it is an export to aurora, the shape that goes vacuous
            # unnoticed. Here an emptied or stale channel map is a red build.
            band_path, band_text = channel_bands_path(), render_channel_bands()
            if not os.path.isfile(band_path):
                print(f"effects_gen: MISSING — {os.path.relpath(band_path, REPO)} does "
                      f"not exist. It is the generated read-only band sidecar aurora "
                      f"reads to warn about a sweep that leaves its channel's band "
                      f"(RASTER-CHBAND-1).")
                print("  Run `python3 tools/effects_gen.py emit` and commit it.")
                sys.exit(1)
            with open(band_path, "r") as f:
                have_bands = f.read()
            if have_bands != band_text:
                print(f"effects_gen: DRIFT — {os.path.relpath(band_path, REPO)} is not "
                      f"what the current effects library declares. A `patchable(` band "
                      f"moved, or the sidecar was hand-edited.")
                print("  Run tools/regenerate-level.sh (or `python3 "
                      "tools/effects_gen.py emit`) and commit the result.")
                sys.exit(1)
            print("effects_gen: OK — generated effects module matches its inputs")
            print(f"effects_gen: OK — channel-band sidecar matches the effects library "
                  f"({len(json.loads(band_text)['channels'])} banded channel(s))")
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
                what = (f"{len(preset['bands'])} band(s)" if "bands" in preset
                        else "1 ramp")
                print(f"effects_gen: preset {pid} — {what}, shape OK")
    except SceneShapeError as e:
        print(f"effects_gen: REFUSED — {e}")
        sys.exit(1)
