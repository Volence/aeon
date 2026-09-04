# The row remap's key shape — EFFECTS-W1 DoD item 9c (SHORT form)

*Status: **the mechanism SHIPPED** (parcel 9a, 2026-09-03) and this note is the CR the hub
files against `contract/schema/aurora-effects-scene.schema.json` and empyrean's
`AURORA_EFFECTS_SCHEMA.md`. It is written the way item 11a's was — **against the landed
code, not against the design** — because the design's proposal is stale and would file the
wrong shape.*

*Authored against `origin/master` `d8baf84f`. Every `file:line` below was opened in that
tree in this pass. The design doc
`docs/superpowers/specs/2026-09-03-hydrocity-row-remap-design.md` §11.2 is used ONLY as a
pointer to what to go read; **not one of its three proposed field names survives contact
with the shipped constructor**, and §11.3's "closed door" is answered here.*

---

## 0. ⚠ THE DESIGN'S §11.2 IS STALE — the exact delta

§11.2 proposed `{ "ladder": string, "height": int, "anchor": 0..3 }`. What landed is
`SceneRemap.Ladder(t, y, h)` (`engine/level/scene_dsl.emp:518-521`), and **all three keys
are wrong**:

| §11.2 proposed | what landed | why the proposal cannot be filed |
|---|---|---|
| `ladder: string` — names a generated artifact | `t: Label`, and **exactly one ladder exists**, `row_remap_ladder16()` (`engine/level/parallax_dsl.emp:220-222`), a pure function of `ROW_REMAP_H16 = 16` (`:207`) | there is nothing to choose between; see §3(a) |
| `height: int` — "the band's maximum remapped height in lines" | `h: int` — **a SHIFT, 3..7**, `H = 1 << h` (`scene_dsl.emp:1006-1007`) | an author writing `height: 16` gets `H = 65536` if the generator forwards it; writing `height: 4` meaning 4 lines gets 16. Two units, one name |
| `anchor: 0..3` on the layer | **the channel comes from the SCENE's own `anchor:`** — `brm_anchor_ch: scene_anchor_ch(s.sc_anchor)` (`scene_dsl.emp:3463`), stated as a ruling at `:823-824` and `:3452-3456` | a per-layer channel could only ever disagree with the one the overlay splits on. The field does not exist |
| — (§11.2 had no such key) | `y: int` — the **surface's PLANE-B LINE**, guarded at `scene_dsl.emp:1008-1009` | the third authored value has no proposal at all |

**One key of §11.2's four survives in spirit and none in spelling.** Filing §11.2 would
produce a schema for a constructor that is not in the ROM.

---

## 1. The hub's file:line claims, checked one by one

| claim | verdict |
|---|---|
| `SceneRemap.Ladder(t, y, h)` — `scene_dsl.emp` around `:487-518` | **CORRECT.** Banner `:487-517`, `pub comptime enum SceneRemap` at `:518`, the `Ladder` arm at `:520` |
| `t` is a ladder `Label` | **CORRECT** (`:520`; `scene_remap_ladder()` returns `Label`, `:1320-1325`) |
| `y` is a **PLANE-B LINE 0..511**, ensure at `:1008` | **CORRECT ON THE LINE, INCOMPLETE ON THE BOUND.** The `ensure` is at `:1008` and its message (`:1009`) does say "IT IS A PLANE-B LINE (0..511)". **But the predicate is only `scene_remap_plane_y(rowRemap) >= 0`.** The 511 ceiling is prose, not a guard. `brm_plane_y` is `u16` (`engine/level/parallax.emp:420`), so 512..65535 is a **silently-wrong** window — representable, emitted, and read as `plane_y - Vscroll_BG` by a runtime that has no idea. See §6 |
| `h` is a **HEIGHT SHIFT 3..7**, ensure at `:1006` | **CORRECT** (`:1006`, message `:1007`) |
| `H = 1 << shift`, table is `(H+1)` rows of `H` bytes | **CORRECT** (`:495-496` banner, `:1007` message, `[u8; 272]` = 17×16 at `parallax_dsl.emp:220`) |
| the anchor channel comes from the SCENE's `anchor:` — `:824`, `:3446-3462` | **CORRECT, with the cites one to three lines off.** The layer-field statement is `:822-824` (the `ly_remap:` declaration is `:825`); the lowering ruling is `:3451-3456` and the emission `:3460-3463` |
| `scene()` refuses: nothing to vary `:1907` · no `anchor:` `:1913` · more than one remapped layer `:1920` | **ALL THREE CORRECT** (the `ensure(` statements are on exactly those lines; messages on `:1908`, `:1914`, `:1921`) |
| the one authored site — `games/sonic4/data/effects/ojz_scenes.emp:252`, `Ladder(RowRemapLadder_Waterline16, 101, 4)` | **CORRECT, verbatim, exact line** |
| the only ladder is `row_remap_ladder16()` in `parallax_dsl.emp:220`, a pure function of H | **CORRECT ON THE LINE; SHARPEN "of H".** `H` is not a parameter — it is the module const `ROW_REMAP_H16 = 16` (`:207`), baked into the function name and into the `[u8; 272]` return type. There is one ladder function and it makes one ladder |
| no generator script yet (9b unbuilt) | **HALF WRONG, and the half that is wrong is good news.** No *generator* exists — but **the gate does**: `tools/row_remap_gate.py` (reads the three ladder invariants out of the linked ROM) and `tools/row_remap_witness.py` both landed with 9a. 9b's own booking says "write the gate before the generator" (`docs/DEFERRED_WORK.md:18377`); half of 9b is already done |

**Two corrections, one addition.** Nothing in the brief was fabricated; the `y` bound and
the "no 9b artifacts" line are the two that would have put a wrong sentence in a schema.

---

## 2. THE KEY — the verbatim block

**`rowRemap`** — a **layer** key on the SCENE document
(`contract/schema/aurora-effects-scene.schema.json`, `$defs.layer`), sibling to `drift`,
`vsplit` and `curve`. **Not a preset key**, and that is settled twice over: a row remap
lowers into `parallax_config`'s band array (`scene_dsl.emp:3460`), never into
`EffectsPreset.ep_raster`, so it must not join the preset schema's
`bands | ramp | base_swap` exactly-one-of group (`tools/effects_gen.py:726-750`).

```json
"rowRemap": { "plane_y": 101, "height_shift": 4 }
```

`"none"` or absent = no remap.

**It follows `drift`/`vsplit`/`curve`'s shape exactly** — `oneOf: [ {const "none"},
{object with the variant's payload FLAT} ]`, no variant tag spelled — which is why there is
no `"ladder": {...}` wrapper:

```json
"rowRemap": {
  "description": "EFFECTS-W1 item 9's row remap: this layer's plane-B scroll words are re-fetched through a perspective-selected index ladder, so screen line i of the band takes the value that belonged to line ladder[i]. Rows are reordered, repeated and dropped; the band compresses toward the surface as the camera separates the background's picture of the surface from the foreground's truth about it. \"none\" or absent = this layer's plane-B scroll words are whatever the line loops wrote (every shipped layer but one). It is the ONLY thing that raises CAP_ROW_REMAP. AT MOST ONE LAYER PER SCENE may carry it. The ladder is NOT named here: it is derived from height_shift (aeon scene_dsl.emp SceneRemap.Ladder). Engine contract: aeon docs/superpowers/specs/2026-09-04-item9-row-remap-key-shape.md.",
  "oneOf": [
    { "const": "none" },
    {
      "type": "object",
      "properties": {
        "plane_y": {
          "type": "integer", "minimum": 0, "maximum": 511,
          "description": "The BG PLANE LINE at which this layer's ART paints the surface. NOT a world Y and NOT a screen line: the runtime computes the background's image of the surface as (plane_y - Vscroll_BG). It is a different number from the layer's own world_y. Plane B is 512 lines tall in this engine's 64x64 configuration. ⚠ AEON ONLY GUARDS >= 0 (scene_dsl.emp:1008) — the 511 ceiling is enforced NOWHERE ELSE, so this schema is its only enforcement; see the aeon note's section 6."
        },
        "height_shift": {
          "type": "integer", "minimum": 3, "maximum": 7,
          "description": "A SHIFT, NOT A LINE COUNT: H = 1 << height_shift. 4 is a 16-line ladder (272 B), 6 is 64 lines (4,160 B, S3K LBZ2's own height), 7 is 128 lines (16,512 B). The ladder is QUADRATIC in H: (H+1) rows of H bytes. Below 3 the remapped run is under 8 lines and nothing is visible; above 7 the table is larger than the act's whole parallax data. If you meant 64 LINES, you want 6. UNIT HAZARD: an editor presenting a line count MUST NOT export it here. Aeon refuses 0..2 and 8+ at build time (scene_dsl.emp:1006). ⚠ TODAY ONLY 4 BUILDS: it is the only ladder the engine can generate (parallax_dsl.emp:220)."
        }
      },
      "required": ["plane_y", "height_shift"],
      "unevaluatedProperties": false
    }
  ],
  "default": "none"
}
```

**Lowering** (what a generator emits into `layer(...)`, `tools/effects_gen.py`'s
`render_scene` path):

```
rowRemap: SceneRemap.Ladder(RowRemapLadder_Waterline16, 101, 4)
```

— the ladder Label resolved from `height_shift`, the two numbers forwarded verbatim.

---

## 3. (a) Does the document spell `ladder`? — **NO. The generator derives it from
`height_shift`.** And the word `ladder` should be REFUSED BY NAME, not merely absent.

**Three independent reasons, in the order of how much they'd cost to ignore:**

1. **It is a second source for one fact, and the design's own §11.2 said so in the act of
   creating the problem**: *"The generator refuses a `height` that disagrees with the named
   ladder's own width — one number, two consumers, checked once."* That refusal exists only
   because the proposal made two names for one number. Delete the name and the refusal has
   nothing to do. This is `layer()`'s own house rule, spelled as a build error at
   `scene_dsl.emp:879`: *"two sources for one byte is how they drift."*

2. **The mapping is total and injective today, and structurally so tomorrow.** The ladder
   is `(H+1)` rows of `H` bytes with `entry(k)` a closed form in `H` alone
   (`parallax_dsl.emp:213-218`). Given `h`, the table is determined; given the table, `h`
   is its width. A `ladder` key could only ever be `h` spelled twice.

3. **The house pattern already refuses variant tags.** `drift` carries `{"rate": N}`, not
   `{"rate": {"rate": N}}`; `vsplit` carries `{"at": N}`; `curve` carries `{"to": F}`. None
   of the three names its `SceneDrift.Rate` / `SceneVSplit.At` / `SceneCurve.To` tag. A
   `rowRemap` spelling `"ladder"` would be the first, for a variant that has no sibling.

**The extension point is real and it is NOT a `ladder` string.** §12 Q6 asks whether a
non-perspective ladder (heat haze, a mirror, a cylinder edge-on) should be authorable. When
it is, it arrives as a **second variant** in this `oneOf` — `{ "table": "<generated id>",
"plane_y": N, "height_shift": N }` — the way `SceneDeform` grew `Own(..)` beside `None`.
A schema can widen a `oneOf` and cannot narrow one; adding an arm later is free, and
committing to a `ladder` string today would ship a required field that every document must
fill with the one legal value.

**Consequence the CR must state:** `ladder` and `table` are both **reserved names** on
`$defs.layer.rowRemap` — refused by name, with the sentence "the ladder is derived from
`height_shift`; a named ladder is the second-variant extension and is not in this contract
yet". The generator's `PRESET_REFUSED_KEYS`/`_check_keys` machinery
(`tools/effects_gen.py:715`) already has the shape for this on the preset side.

---

## 4. (b) `plane_y` and `height_shift` — **1:1, verbatim, no unit conversion anywhere**

The item 4 precedent, quoted from the generator that enforces it
(`tools/effects_gen.py:3008-3013`): *"⚠ `patch_world_ys` IS WHOLE PIXELS AND NEITHER SIDE
CONVERTS — 1:1, editor to ROM… There is no `* 256` anywhere on this path and there must
never be one."*

- **`plane_y`** is the integer the constructor takes. It is a **plane line**, and the
  runtime's only use of it is `plane_y - Vscroll_BG` (`scene_dsl.emp:1009`). No editor
  arithmetic can improve it: an editor that converted a world Y or a screen line into it
  would be doing a subtraction whose second term is a per-frame runtime quantity.
- **`height_shift`** is the integer the constructor takes. **This is the field where a
  helpful editor does the most damage**: presenting "band height = 16 lines" and exporting
  `16` yields `H = 65536`, which sails past nothing — `scene_dsl.emp:1006` catches it,
  because 16 is outside 3..7. But presenting "height 64" and exporting `64` is also caught,
  and presenting height 8 and exporting `8` is caught, while presenting height 128 and
  exporting `7` is *correct by accident*. The rule that survives all four: **the editor may
  DISPLAY `1 << height_shift` beside the control; it must EXPORT the shift.**

**An editor that converts is an editor that can be wrong**, and here it can be wrong in a
direction the build cannot see: every value 3..7 is legal, so a conversion bug lands as a
band four times too tall rather than as a refusal.

---

## 5. (c) The three states

The house rule, unchanged from `drift`/`variants`/`patch_world_ys`:

| state | meaning | lowering |
|---|---|---|
| **key absent** | the section keeps whatever its scene already had | the generator emits no `rowRemap:` argument; `layer()`'s default is `SceneRemap.None` (`scene_dsl.emp:860`) |
| **`"none"`** | explicitly off | `rowRemap: SceneRemap.None` — emitted, so the ROM says "the author chose no remap" rather than "the author said nothing" |
| **object** | authored | `rowRemap: SceneRemap.Ladder(<derived>, plane_y, height_shift)` |

Absent and `"none"` lower to the same eight bytes (a NULL `brm_ladder` is the per-band
gate — `parallax.emp:419`), so the distinction is an authoring one, not a ROM one. State
that in the CR: it is the same "absent = keep / null = off, never a silent default" wording
`rasterRef` and `ramp` already carry, and it is the reason `"none"` is spelled at all.

---

## 6. (d) Which refusals the schema encodes, and who owns each — **I AGREE with the hub's
read, and it needs one correction and one addition**

**Agreed:** the three `scene()` refusals are **generator** refusals, not schema ones. The
reason is sharper than "they need the scene's anchor and deform tables" — it is that JSON
Schema cannot express a **cross-key conditional over an array element's siblings**:
"if any element of `layers[]` has `rowRemap` then the DOCUMENT must have `anchor` AND that
element must have `curve` or (a live `dsb` and a document `deform_bg`)". A `oneOf`/`if-then`
encoding of that is writable and unreadable, and its error message would name a JSON path
rather than the thing the author did wrong.

| refusal | enforced where, TODAY | who should own it | why |
|---|---|---|---|
| `height_shift` outside 3..7 | `scene_dsl.emp:1006` | **schema AND engine.** Schema `minimum: 3, maximum: 7` | it is a per-field range with no cross-key term; a schema that can catch it should, so the editor's control can't even offer 8 |
| `plane_y < 0` | `scene_dsl.emp:1008` | **schema AND engine** | same |
| **`plane_y > 511`** | ⚠ **NOWHERE** | **schema, today; engine, once someone tightens `:1008`** | see the correction below |
| "nothing to vary" (§9.1 precondition 1) | `scene_dsl.emp:1907` | **generator** (`tools/effects_gen.py`), and the engine `ensure` STAYS | every input is a document key (`layers[i].curve`, `layers[i].dsb`, `deform_bg`, `anchor.at.dsb`), so the generator genuinely can check it — and must, because the generator IS the build gate for documents (`effects_gen.py:721-725`). The engine ensure stays because `Scene_OJZ_Underwater` is hand-authored `.emp` the generator never reads |
| no `anchor:` (§9.1 precondition 2) | `scene_dsl.emp:1913` | **generator**, engine ensure STAYS | `anchor` is a top-level scene document key (verified in the scene schema); one `if "rowRemap" in any layer and doc.get("anchor","none") == "none"` |
| more than one remapped layer | `scene_dsl.emp:1920` | **generator**, engine ensure STAYS | a count over `layers[]`. Note this one is *nearly* schema-expressible (`maxContains: 1`) but the message is worth more than the encoding |
| CAP_ROW_REMAP not raised in the game | **nowhere on the document path** | **generator** | the direct analogue of `_check_patch_context`'s CAP_ANCHOR_MOTION refusal (`effects_gen.py:1300-1315`). Without it a document authors a remap into a game whose `BAND_REMAP_N` is 0, the tail does not exist, and nothing anywhere says why |

**The correction the hub should carry into the schema description: `plane_y`'s upper bound
has no enforcement in the tree at all.** `scene_dsl.emp:1008` tests `>= 0` only;
`brm_plane_y` is `u16` (`parallax.emp:420`), so 512..65535 emits cleanly and the runtime
reads `plane_y - Vscroll_BG` against a plane that is 512 lines tall. `vsplit.at` — the same
coordinate space — **already carries `minimum: 0, maximum: 511` in the scene schema**, so
the precedent is set and the CR should simply match it. This is the one place where the
schema is not a restatement of an engine guard but the only guard there is, and the
description must say so rather than implying aeon checks it.

**The addition:** a `height_shift` other than 4 currently has no ladder. `scene_dsl.emp`
will accept 3, 5, 6 or 7 and the emission will then fail on an undefined Label — a build
error, but one that names a missing symbol rather than the authoring mistake. Until 9b's
generator lands, the schema description must carry **"⚠ today only 4 builds"** (it does,
above), and the *generator* should refuse the other four by name. That is a 9b obligation,
booked below.

---

## 7. (e) §11.3's closed door — **TESTED IN SOURCE, AND IT IS OPEN.** Way out #1 works.

§11.3 wrote: *"a document-authored, anchor-driven water band cannot today be bound to the
one section that has an anchor,"* and named the cheap check as way out #1 — *"whether a
section binding `raster:` can carry a seeded patch channel."*

**I checked it. It can.** Five independent cites, all in the tree at `d8baf84f`:

1. **`preset()`'s mutual exclusion is `raster` vs `patched` ONLY** —
   `ensure(raster == 0 || patched == 0, ...)` at `engine/effects/preset.emp:153-154`.
   `patch_world_ys` and `patch_motion` are checked for `.len == RASTER_MAX_PATCH`
   (`:161`, `:167`) and for **nothing else**. There is no term coupling a seed to `ep_patched`.
2. **The seed is installed unconditionally, on every install, by design** —
   `Effects_InstallPreset`'s own banner at `preset.emp:283-290`: *"ep_patch_world_ys ->
   Effects_World_Y[], UNCONDITIONALLY (Parcel W0). This is the channel total binding
   forgot. The seed used to live inside `Raster_InstallPatched`, so it ran only when
   `ep_patched != 0`."* That is exactly the coupling §11.3 feared, named as a defect that
   was already removed.
3. **The install latches immediately** — `jbsr Effects_LatchWorldLines` at `preset.emp:366`,
   and the per-frame latch runs from the level loop between `Camera_Update` and
   `Parallax_Update` (`games/sonic4/test/ojz_scroll_test.emp:1009`), gated on
   `Debug_Scene_Freeze` and on nothing raster-related.
4. **The generator already accepts the seed on a `rasterRef` document** — `patch_world_ys`
   and `patch_motion` are in `PRESET_KEYS` (`tools/effects_gen.py:306-307`) and
   `patch_bound` is derived from `raster_bound` (`:2528-2533`) with the comment *"The patch
   channels ride the SAME `rasterRef`, ruling Q1 again: one ref binds the whole document."*
5. **A scene anchor counts as a channel consumer** — `_collect_live_channels` collects
   `SceneAnchor.At(ch)` alongside `patchable(ch: …)` (`effects_gen.py:1280-1281`), so a
   channel consumed only by a remapping scene passes the liveness refusal at `:1316-1333`.

**The one real constraint, stated so it is not rediscovered:** a preset document **must**
carry exactly one of `bands`/`ramp`/`base_swap` (`effects_gen.py:739-750` refuses a
document with none). So the section that seeds the channel also ships a raster program it
may not want. The cheapest filler is `base_swap` (one `OP_SET_REG`) or a single `bands`
entry; it is a cost, not a wall.

**Therefore: 9c is USABLE by a document-bound section, and the hub should file without
waiting.** The working binding is:

> section N binds a **scene** document carrying `anchor: {at: {channel: c, …}}` and one
> layer carrying `rowRemap`, **and** a **preset** document carrying `patch_world_ys[c]`
> (plus whichever of `bands`/`ramp`/`base_swap` it can afford). Neither document needs
> `patched:`, because the row remap reads `Effects_Screen_L[c]` and never needs a palette
> boundary.

**⚠ SAY WHAT KIND OF TEST THIS WAS.** This is **source-verified, not build-verified.**
Proving it end to end means writing a preset JSON and a section meta into
`games/sonic4/data/editor/`, which this parcel is forbidden to touch, and running
`./build.sh`. Five reads is a strong argument and it is not a green build. **The CR should
carry the limit as "verified in source at `d8baf84f`; no ROM has been built through this
path"**, and 9c's first parcel should build it as its own first step — if it fails, the
failure is in the generator's scene path, not in the engine, because nothing in the engine
couples the two.

For completeness, the other two ways out are now unnecessary rather than merely expensive:
way #2 (hand-author and skip the document) is what 9a already did, and way #3 (a
`raster:` + `patched:` combinator) remains a hub-scale change nobody needs for this item.

---

## 8. What this note did NOT settle

1. **The generated ladder for `height_shift` != 4.** 9b. Until it lands, four of the five
   legal shifts emit an undefined Label. The gate half of 9b already exists
   (`tools/row_remap_gate.py`).
2. **`plane_y > 511` is unguarded in aeon.** Booked — see `docs/DEFERRED_WORK.md`, the
   `ROWREMAP-PLANEY-CEILING` row.
3. **The visible amplitude is ±2 px and that is owner content** — the anchor's `dsb` on
   `Scene_OJZ_Underwater`, unchanged by 9a on purpose
   (`docs/DEFERRED_WORK.md:18478-18481`). A `rowRemap` key does not make the effect more
   visible; it makes it authorable.
4. **The shipped section does not install the shipped scene.** OJZ act 1 section 0 installs
   `EditorSceneBinding_OJZ_Act1_Sec0`, not `ParallaxConfig_OJZ_Underwater`
   (`docs/DEFERRED_WORK.md:18482-18486`). §7's binding is the route that fixes this; it has
   not been walked.
