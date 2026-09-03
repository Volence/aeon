# The reels' key shape — EFFECTS-W1 DoD item 10a (DEMAND ARTIFACT)

*Status: **DEMAND ARTIFACT, documents only**, 2026-09-03. Nothing here is implemented; this
parcel moves no ROM byte and runs no build. Written for the reason item 6's artifact
was — the hub cannot transcribe a source that does not exist — and per `docs/DEFERRED_WORK.md`'s
own sequencing note: "item 6's per-line field first (two lanes wait on it), then a reels
field, then the item-11 field" (`:17439`). **This document is that "reels field" deliverable.**

*Every claim below is transcribed from source in this tree at aeon
`9e85baf0575d8995e71adfd4da60c3f096e3985d` — the tip of `origin/master` at the moment this
branch (`docs/item10a-key-shape`) was cut, verified by `git rev-parse HEAD` in this worktree.
Every `file:line` cite anchors to a symbol name beside the line number, so a later move does
not silently invalidate it. `docs/DEFERRED_WORK.md`'s own item-10a landing block
(`:18840`-end of file, 19162 lines total) and its item-10/11 authoring-key ruling
(`:17429`-`17466`) are used only as POINTERS to what to go read — every fact they state is
re-derived directly from `games/sonic4/data/effects/ojz_effects.emp`,
`games/sonic4/config/{constants,ram}.emp`, `games/sonic4/test/ojz_scroll_test.emp`,
`engine/level/scene_dsl.emp`, `engine/level/parallax.emp` and `tools/effects_gen.py` in this
pass, not copied from the booking. Anything not found is marked **NOT FOUND** or
**NOT ESTABLISHED** rather than guessed.*

*Follows item 6's structure (`docs/superpowers/specs/2026-09-03-item6-dense-perline-vscroll-key-shape.md`),
which follows item 5's (`docs/superpowers/specs/2026-08-30-item5-variants-cycles-key-shapes.md`):
transcribe the engine fields, state what a generator would emit, give the authored-range
account against storage width, and list what is left open. Where this item's shape genuinely
differs from item 6's — and it differs in three load-bearing ways, flagged inline — this
document says so rather than forcing the parallel.*

---

## 0. Where item 10a sits, and exactly what is being asked

- DoD row: `docs/DEFERRED_WORK.md:17426` — item 10, "Reels / plane-role swap / window as
  third layer", **10a LANDED 2026-09-03**, `parcel/item10a-reels`. That parcel shipped
  `OJZ_Reels_Fill`, a DEBUG-gated demo mechanism, and `tools/reels_gate.py` to prove its
  source reached the ROM. It shipped **no authoring surface** — this is not an inference,
  it is the booking's own stated finding, re-verified against source in §2 below.
- `docs/DEFERRED_WORK.md:17429`-`17466` is a hub ruling, dated the same day, that items 10
  and 11 ARE inside wave 1's definition of done for an authoring key (DoD item 12's closing
  clause, "controls for items 7 to 11 as each lands") and sequences reels second, after
  item 6's per-line field (`:17438`-`17439`). **This document is that reels-field
  deliverable**, following item 6's now-shipped precedent.
- The same ruling names the trap this document's §1 and §6 exist to carry: *"the obvious
  surface for a reels key is WRONG. `SceneVDeform` samples one table at one global phase,
  which is precisely why 10a needed new code, so a key hung there would let an author ask
  for reels and receive lagging columns."* (`:17455`-`17458`). **Verified against source
  below, not repeated on the booking's word.**

---

## 1. What the engine can do TODAY (transcribed from source at `9e85baf0`)

### 1.1 The reel source — `OJZ_REEL_SPEEDS` / `OJZ_Reel_Speed`

`games/sonic4/data/effects/ojz_effects.emp:1666`:

```
const OJZ_REEL_SPEEDS: [i8; REEL_BAND_COUNT] = [3, -5, 2, -4, 6]
```

`REEL_BAND_COUNT` (5) and `REEL_COLS_PER_BAND` (4) are declared in
`games/sonic4/config/constants.emp:66-67` as plain `pub const` integers — **fixed engine
geometry, not per-effect authored values**. This is the first structural difference from
item 6: `raster_ramp_program` is a general-purpose constructor callable with fresh
arguments at any number of call sites; `REEL_BAND_COUNT`/`REEL_COLS_PER_BAND` are single
global constants checked once against the buffer they carve up
(`engine/level/parallax.emp:723`, `VSCROLL_COL_PAIRS = SCREEN_WIDTH / 16`, `:725-726`'s own
`ensure(VSCROLL_COL_PAIRS == 20 && ...)` H40 pin). The only thing an author could plausibly
name per-effect is the **rate array itself** — 5 signed per-band speeds — not the band
count or width, which are structural.

`OJZ_Reel_Speed` is the emitted table (`ojz_effects.emp:1676-1677`):

```
const REEL_SPEED_EMIT_LEN = if DEBUG == 1 { REEL_BAND_COUNT } else { 0 }
pub data OJZ_Reel_Speed: [i8; REEL_SPEED_EMIT_LEN] = if DEBUG == 1 { OJZ_REEL_SPEEDS } else { [] }
```

DEBUG-gated for `OJZ_BaseSwap`'s reason (item 11a's precedent, restated at
`ojz_effects.emp:1672-1675`): nothing in the release shape can ever set `OJZ_Reel_Active`
(§1.2), so an unconditional emission would be a dormant scaffold.

### 1.2 The reader — `OJZ_Reels_Fill`, and it is CODE, not a constructed data record

`games/sonic4/data/effects/ojz_effects.emp:1703-1737`, `pub proc OJZ_Reels_Fill ()
clobbers(d0-d5/a0-a2)`, whole body inside `if DEBUG == 1 {}` (`:1704`, `:1736`). Each call:

1. Advances 5 independent byte phase accumulators (`OJZ_Reel_Phase`, `games/sonic4/config/ram.emp:357`)
   by their own constant speed, wrapping mod 256 by plain byte `add.b` (`:1708-1715`).
2. Rebuilds all 20 column-pairs of `Parallax_Vscroll_Column_Buf`: the FG word is copied
   unchanged from whatever `Parallax_Update` already wrote (`:1719`, `:1724`); the BG word
   is `Parallax_Current_Vscroll_BG` (the camera's own BG base) plus the owning band's live
   phase, band computed as `column >> 2` (`lsr.b #2, d2`, `:1727` — a shift, not a divide,
   per CODING_CONVENTIONS §2.1).

This is the **second structural difference from item 6**: `RasterRampProgram` is a `struct`
value a `comptime fn` constructs and a caller assigns into a data slot (`preset()`'s
`raster:` parameter). `OJZ_Reels_Fill` is a hand-written 68000 loop with no comptime
constructor of any kind behind it — there is nothing analogous to `raster_ramp_program()`
that a second author, or a future generator, could call with different arguments to get a
second independently-parameterized reel instance. Reproducing this feature for a new
instance means literally copying the pattern (module-level `ensure`s + a hardcoded const
array + a hardcoded proc), not calling a reusable function. See §4's "no constructor to ask
the question of" for what this means for refusal-site enforcement.

### 1.3 The call site — a `Parallax_Update` override, not a preset or scene channel

`games/sonic4/test/ojz_scroll_test.emp:1294-1313`:

```
jbsr    Parallax_Update
...
if DEBUG == 1 {
        tst.b   OJZ_Reel_Active
        beq     .skip_reels_fill
        jbsr    OJZ_Reels_Fill
.skip_reels_fill:
}
...
jbsr    BgAnim_Update
```

`OJZ_Reels_Fill` runs immediately after `Parallax_Update` (which fills
`Parallax_Vscroll_Column_Buf` from the active scene's per-column deform, if any) and before
`BgAnim_Update`, gated on `OJZ_Reel_Active` (`games/sonic4/config/ram.emp:356`, a `u8`
inside the `if DEBUG == 1 @shape_divergent {}` RAM-tail group opened at `:187`, closed
before `mark Game_RAM_End` at `:361`). There is **no hotkey**: `OJZ_Reel_Active`'s only
writer in this tree is `tools/reels_witness.py` poking the RAM cell directly
(`ojz_effects.emp:1618-1621`).

**This is the third structural difference from item 6, and it is the one that answers §2's
question outright**: item 6's `RasterRampProgram` occupies `EffectsPreset.ep_raster`
(`engine/effects/preset.emp:62`), a real per-preset data slot that an authoring key could
target. Reels touch **no preset field and no `EffectsPreset` at all** — `OJZ_Reels_Fill`
overrides RAM (`Parallax_Vscroll_Column_Buf`) that `Parallax_Update` itself just wrote,
called from game-state code (`GameState_OJZScroll_Update`), entirely outside the
preset/bands/raster machinery. Grep confirms: `games/sonic4/data/effects/ojz_effects.emp`
has zero occurrences of `ep_raster`, `preset(`, or `raster:` anywhere near the `OJZ_Reels`
block (`:1583`-`:1737`).

### 1.4 No capability gate at all — the fourth asymmetry with item 6

Item 6's `raster_ramp_program()` call is refused unless the game declares
`CAP_DENSE_TIER` (`ojz_effects.emp:1048-1049` in that item's own artifact). **Reels has no
equivalent.** Grepping `ojz_effects.emp:1583`-`:1737` (the whole `OJZ_Reels` block) for
`CAP_` returns zero hits. The mechanism is gated only by (a) the DEBUG build shape and (b)
the `OJZ_Reel_Active` RAM flag — no `Game.SCANLINE_CAPS` bit is checked or required. This
is a genuine finding, not an oversight this document is inferring: nothing in
`games/sonic4/config/game.emp` or `games/demo/config/game.emp` is referenced by the reels
code at all.

### 1.5 Cost

Not separately measured in this documents-only pass (out of scope per the brief — this
parcel changes no code). The item-10a landing record states `RASTER_DENSE_LINE_RAMP_CYC`-style
per-scanline HBlank costing does not apply here at all: `OJZ_Reels_Fill` is a per-FRAME
proc called once from game-state code (not a raster HInt fire), so its cost class is a
main-loop budget question, not an HBlank one — **not measured in this pass, and no `ensure`
in the reels code itself checks a cycle budget** (contrast with item 6's
`RASTER_DENSE_LINE_RAMP_CYC < RASTER_SCANLINE_CYC` ensure, `raster_dsl.emp:1908-1909`,
re-cited from that artifact, not re-verified here since it is a different mechanism's gate).

---

## 2. Spine question 1 — the PRESET/SCENE-document key: **NONE EXISTS for reels — and the ONE existing adjacent key is the wrong one, verified**

This is a starker version of item 6's finding, not the same one. Item 6 found no key at
either the preset or scene level. Item 10a's tree has a **scene-level** key surface
(`v_deform`) that is exactly type-adjacent to what a reels field would need — and it is
provably the wrong mechanism, not merely an unbuilt one.

- **`tools/effects_gen.py` has zero hits for "reel" or "strip"** (`grep -n -i
  "reel\|strip" tools/effects_gen.py` → no output outside an unrelated `.strip()` string
  method call and unrelated prose). The generator does not know reels exist in any form.
- **`SCENE_KEYS`** (`tools/effects_gen.py:70-90`) includes `"v_deform"` (`:88`) as an
  accepted top-level *scene*-document key (reels would be scene-level too, per §1.3 — it
  is not a preset-document concept at all). `PRESET_KEYS` (`:285-286`) —
  `{schema, id, bands, cycles, variants, patch_world_ys, patch_motion}` — has nothing
  reel-shaped either, confirming reels cannot be reached from the preset side (consistent
  with §1.3: `EffectsPreset` is never touched).
- **`v_deform` is real, built, and lowers to exactly the mechanism the hub ruling calls
  WRONG.** `SCENE_TABLE_ATTACHMENTS = {"deform_fg": "shared", "deform_bg": "shared",
  "v_deform": "columns"}` (`tools/effects_gen.py:159-160`); `render_table_attachment`'s
  `columns` arm (`:1410-1412`) emits `SceneVDeform.Columns(table, speed, amp_shift)` — a
  **shipped, generator-reachable JSON key today**, `{"v_deform": {"columns": {"table":
  ..., "speed": ..., "amp_shift": ...}}}`.
- **Verified at the engine, not assumed from the generator's naming**:
  `engine/level/scene_dsl.emp:353-356`:
  ```
  pub comptime enum SceneVDeform {
      None,
      Columns(Label, int, int),   // (column table Label, sample speed, amplitude shift)
  }
  ```
  and its runtime consumer, `engine/level/parallax.emp:2232-2270` (`cap_per_col_vsram_fill`
  span): **one** phase accumulator, `Parallax_V_Deform_Phase_BG`, advanced once per frame
  by the scene's single `pcfg_v_deform_speed_bg` (`:2237-2241`), then sampled at
  `table[phase + column]` inside a 20-iteration column loop where the sample INDEX
  increments by exactly 1 per column (`d4` incremented by `addq.b #1, d4`, `:2268`, into
  `move.b (a1, d4.w), d5`, `:2261`). **This is the literal mechanism the ruling describes**:
  every column reads the same table at consecutive offsets of one shared, monotonically
  advancing phase — two adjacent columns' values differ only by how steep the table is
  between two adjacent samples, and a bounded table (`deform_sine`/`deform_triangle`,
  `TABLE_GENERATORS` at `effects_gen.py:168-174`) keeps that difference small and
  self-correcting. **There is no per-column independent rate anywhere in this path** — one
  `speed`, one `phase`, one `table`, for the whole scene's per-column deform.
- **Confirmed as the naming trap the brief flagged**: a reels-shaped author asking for
  `v_deform` (or a new arm added to it) would receive `SceneVDeform.Columns`' shared-phase
  sampling — lagging columns that periodically re-synchronise whenever the table
  wraps — never the pairwise-distinct, never-resynchronising, independent constant rates
  `OJZ_REEL_SPEEDS` demonstrates (`ojz_effects.emp:1656-1665`'s own `distinct5()` property).
  **This is why the field must be its own, not a widening of `v_deform`**: `v_deform`'s
  wire shape (`SceneVDeform.Columns(Label, int, int)`, one table + one speed + one shift)
  structurally cannot carry 5 independent per-band rates — there is no array slot to add
  one to.
- **`v_deform`'s absence is a real, working default**, precedent for what an absent reels
  key should mean: `scene_dsl.emp:1505`, `v_deform: SceneVDeform = SceneVDeform.None` — the
  scene simply has no per-column deform at all when the key is omitted, and the generator
  only emits the `v_deform:` argument `if not is_absent(scene.get(key))`
  (`effects_gen.py:1567-1570`).

**So the answer is: a scene-level key surface exists and is even the right SHAPE of
surface (scene-level, not preset-level, since §1.3 established reels are scene/game-state
content, not preset/raster content) — but the one key that exists there (`v_deform`) is
mechanically incompatible with reels' defining property (independent per-band rates), and
no other scene key or arm carries anything reel-shaped.** Nothing reserves the name by
refusal either — unlike item 6's `"fires"` entry in `PRESET_REFUSED_KEYS`
(`effects_gen.py:299-305`), there is no `SCENE_REFUSED_KEYS` entry naming "reel" or
"strips" (`SCENE_REFUSED_KEYS` is `{"layer_mask_raw", "v_deform_shift_raw"}` only,
`:112-115`, both byte-identity bridges unrelated to reels).

**What this means for where a CR would land, stated but NOT decided here (the hub's
call):**
- It cannot be a new arm of `v_deform`/`SceneVDeform` — the wire shape (one table, one
  speed, one shift) has no array slot for 5 independent rates, and widening it would
  change `SceneVDeform.Columns`'s meaning for the six shipped scenes that already use it
  (Rocking/Perspective family, per the item-10a landing record, not re-verified here since
  it changes no code this document touches).
- It would most naturally be a **new, sibling scene-level key** — `SCENE_KEYS` already has
  room for scene-scoped mechanisms distinct from `v_deform` (`bob_shift`/`bob_period` for
  item 7, `anchor` for the moving-bands item, `drift` at the LAYER level for item 3) — but
  unlike those, a reels key's natural payload is a **fixed-length array of 5 signed
  values** (`REEL_BAND_COUNT`), not a scalar or an object with named sub-fields. There is
  no existing `SCENE_SCALARS`/array-valued scene key precedent in this file to imitate
  directly; `LAYER_SCALARS`/`SCENE_SCALARS` (`effects_gen.py:187-189`) are all single
  integers. **NOT ESTABLISHED**: whether the hub would want this expressed as `"reel_rates":
  [3, -5, 2, -4, 6]` (a bare 5-element array) or as an object keyed by band index — this
  page names the shape constraint (5 signed values, order-significant since band = column
  >> 2 maps position to array index) without picking a JSON spelling.
- **It is unclear whether this belongs at the scene level at all, or should instead be a
  brand-new mechanism the way `scene_registry.emp`'s fixed `SCENES: [Scene; 20]` array is**
  (`games/sonic4/data/effects/scene_registry.emp:307`, `SCENE_CYCLE_COUNT = 20` at `:350`)
  — a DEBUG-only, hand-registered demo table cycled by `Debug_SceneCycleHotkey`, NOT the
  editor-authored per-section JSON `scene()` documents `effects_gen.py` renders. The
  DEFERRED_WORK booking's own cost estimate for "the write site" names exactly this
  registry (five files: the `SCENES` array, `SCENE_CYCLE_COUNT`, the hotkey's `dc.l`
  table, and its lint) rather than a JSON schema key — which means even the booking's own
  costed path is NOT the authoring-surface key the hub ruling asks for; it is a second,
  separate built-in-demo-registration cost. **Flagged as open, not resolved**: whether the
  hub's CR wants (a) a real per-section JSON key reaching a NEW engine mechanism (a
  `layer()`-shaped or `scene()`-shaped `reel_rates` argument that `Parallax_Update` itself
  would have to grow, since today only `OJZ_Reels_Fill`'s override touches the buffer this
  way), or (b) registering `OJZ_Reels_Fill`'s existing fixed 5-band demo as one more
  `Debug_SceneCycleHotkey`-cycled built-in scene, which is authorable by nobody outside
  this repo's own debug tooling and is not "authoring" in the Aurora sense at all. This
  page names both readings; picking between them is the hub's call.

---

## 3. Spine question 2 — the lowering path, with line cites at `9e85baf0`

**There is no document-to-`.emp` lowering today** (§2). What exists is the hand-authored
demo path, and unlike item 6 it is not organized around a reusable constructor a lowering
step could simply call — see §1.2's "no constructor" finding. The stops a hypothetical
generator would have to reproduce, in full, since none of them is a general-purpose
function:

1. **`games/sonic4/config/constants.emp:66-67`** — `REEL_BAND_COUNT` (5),
   `REEL_COLS_PER_BAND` (4). These are FIXED engine geometry, checked once
   (`ojz_effects.emp:1642-1643`, `:1648-1649`, §4 rows 1-2) against
   `VSCROLL_COL_PAIRS` (`engine/level/parallax.emp:723`). A generator would not author
   these per-effect; it would only ever emit a `[i8; REEL_BAND_COUNT]`-shaped rate array
   consistent with whatever these already are.
2. **`games/sonic4/data/effects/ojz_effects.emp:1663-1665`** — `distinct5(a,b,c,d,e) ->
   int`, a plain `comptime fn`, hardcoded to exactly 5 parameters (not `REEL_BAND_COUNT`
   parametric — it would need generalizing, or a different pairwise-distinctness idiom,
   the moment band count ever changed). A generator reproducing the pairwise-distinct
   property for a *different* set of 5 authored rates would call this exact function, in
   this exact positional order (`ojz_effects.emp:1669`,
   `distinct5(OJZ_REEL_SPEEDS[0..4])`); reproducing it for any OTHER band count has
   **no existing helper at all** — `distinct5` is literally 5-ary, not generic.
3. **`games/sonic4/data/effects/ojz_effects.emp:1666-1670`** — the const array declaration
   plus its two `ensure`s (length-matches-`REEL_BAND_COUNT`, pairwise-distinct). A
   generator emitting a new array of authored rates MUST re-emit both `ensure`s beside its
   own generated const, exactly as item 6's artifact found for `CAP_DENSE_TIER`
   (§4 below) — neither check lives inside anything the new array would automatically
   inherit.
4. **`games/sonic4/config/ram.emp:356-357`** — `OJZ_Reel_Active` / `OJZ_Reel_Phase`, both
   inside the `if DEBUG == 1 @shape_divergent {}` group opened at `:187`. A generated
   feature that wanted per-scene (rather than one fixed global demo) reel state would need
   its own RAM allocation here or a redesign of this single-instance RAM shape into
   something indexable by scene/section — **NOT ESTABLISHED** whether that redesign is
   small or a rewrite; not attempted in this documents-only pass.
5. **`games/sonic4/test/ojz_scroll_test.emp:1294-1313`** — the `Parallax_Update` /
   `OJZ_Reels_Fill` / `BgAnim_Update` call order. This is inside `GameState_OJZScroll_Update`,
   a specific game state's per-frame update — NOT a general engine entry point every
   scene's frame passes through by construction. A generator-driven reels feature that
   needed to run for an arbitrary section (not just this one demo game state) would need
   the call moved into (or duplicated into) whatever general per-frame parallax/scene
   update path real sections use — **NOT ESTABLISHED** whether `GameState_OJZScroll_Update`
   is itself that general path or a demo-only harness; not traced further in this pass
   (out of scope for a document that changes no code).

`engine/level/scene_dsl.emp` and `engine/level/parallax.emp` contribute the EXISTING (wrong)
`v_deform` surface (§2) but no reels-specific authoring code of any kind — their only
reels-adjacent content is `SceneVDeform`'s own shared-phase mechanism, which this document
establishes is NOT what a lowering step should target.

---

## 4. Spine question 3 — the refusal sites, every comptime `ensure`, by line

| # | Refuses | Site |
|---|---|---|
| 1 | `REEL_BAND_COUNT * REEL_COLS_PER_BAND != VSCROLL_COL_PAIRS` | `games/sonic4/data/effects/ojz_effects.emp:1642-1643` |
| 2 | `REEL_COLS_PER_BAND != 4` (the hardcoded `lsr.b #2` shift in `OJZ_Reels_Fill`'s column→band map) | `:1648-1649` |
| 3 | `OJZ_REEL_SPEEDS.len != REEL_BAND_COUNT` | `:1667-1668` |
| 4 | `OJZ_REEL_SPEEDS` not pairwise distinct (`distinct5(...) != 1`) | `:1669-1670` |

**That is the entire refusal-site list for this feature — four `ensure`s, all in one
module, all UNGATED (run in every shape, every build, per `:1652-1654`'s own comment).**

**No `ensure` anywhere bounds an individual speed's MAGNITUDE.** Contrast item 6, where
`fp16()`'s two `ensure`s (`raster.emp:685-686`) bound `whole`/`frac256` even though nothing
forces a caller to route through `fp16()`. Here, the only per-element check is
**pairwise distinctness** (row 4) — a value's absolute size is constrained by nothing
beyond the `i8` element type of `[i8; REEL_BAND_COUNT]` (`ojz_effects.emp:1666`), i.e.
-128..127. **Whether an out-of-range `i8` literal (outside -128..127) is refused by
sigil's own type-checking of the array-literal-to-`[i8;N]` assignment, or would silently
wrap/truncate, is a sigil-frontend implementation question this document does NOT resolve**
— it is outside this pass's scope (aeon source only; item 6's own artifact drew the same
line around `raster.emp`'s `u16`/`u32` field widths, never verifying sigil's own literal
overflow behaviour). **Flagged as NOT ESTABLISHED**, not assumed either way.

**"Is there a path that reaches the constructor without passing through the check?" —
the question does not apply the way it did for item 6, and that absence is itself the
finding.** Item 6's `raster_ramp_program()` is a reusable `comptime fn`; a caller could in
principle build a `RasterRampProgram` by hand, bypassing `fp16()`'s bounds (the constructor
itself has no `ensure` on `start`/`step` — item 6 §1.2/§7). Item 10a has **no reusable
constructor of any kind** (§1.2) — `OJZ_REEL_SPEEDS` is a single hardcoded module-level
const, and its two `ensure`s (rows 3-4) sit directly beside it and always run. There is no
"call site that skips the check" because there is only ONE site, ever, in this tree. **The
real gap is the one this exposes for the future, not the present**: if a generator (or a
second hand-author) ever created a SECOND reel-speed array for a different scene, nothing
would force them to copy `distinct5()`'s call and the length-match `ensure` alongside it —
exactly item 6's "the `ensure` does not travel with the mechanism" finding for
`CAP_DENSE_TIER` (that item's §1.4, §3 step 3), reached here by a different route: not
because the check lives outside a constructor's body, but because **there is no
constructor at all for the check to conditionally belong to** — reproducing the feature
means reproducing the whole module-level idiom by hand, checks included, and nothing
enforces that a copy remembers to.

---

## 5. Spine question 4 — three states or absent-key semantics: **N/A today; the shape a future key would need**

Since §2 establishes no reels key exists (and the one adjacent key, `v_deform`, is the
wrong mechanism), neither item 4's positional three-state model nor item 5's "one script"
array-is-the-value model applies to anything built. Stated as a proposal only:

- **Not naturally positional the way `patch_world_ys`/`variants` are.** Those are arrays
  over independent SLOTS the constructor addresses by index with different per-slot
  meaning. A reels array is closer to item 5's `cycles` precedent — "the array IS the one
  script" — except the array's LENGTH is fixed at the engine constant `REEL_BAND_COUNT`
  (5) rather than an author-chosen count (item 5's `cycles` channel count is 1..4, author's
  choice; reels' band count is NOT authorable per §1.1 — it is checked, not chosen).
- **Consistent with `v_deform`'s existing absent-key precedent** (`scene_dsl.emp:1505`,
  `SceneVDeform.None` default; `effects_gen.py:1567-1570`, the key is only emitted if
  present), **absent should mean "no reels for this scene"** — the mechanism simply does
  not run, which for a NEW mechanism (§2's open question on whether this needs a new
  `Parallax_Update`-level engine hook) would presumably mean the per-column buffer keeps
  whatever `Parallax_Update`'s existing `v_deform`/flat-scroll path already puts there,
  the same "hand channel stands" rule item 6's artifact stated for `rasterRef`
  (`docs/superpowers/specs/2026-09-03-item6-dense-perline-vscroll-key-shape.md` §5,
  itself citing `tools/effects_gen.py:1972`; not independently re-derived for reels in
  this pass since no such `rasterRef`-equivalent sidecar exists for reels today).
- **Order is meaning, not formatting, and this document flags it explicitly because
  `OJZ_Reels_Fill`'s hardware loop depends on it.** `OJZ_Reels_Fill`'s column→band map
  (`ojz_effects.emp:1727`, `lsr.b #2, d2`) is POSITIONAL: array index 0 owns columns
  0-3 (screen X 0-63), index 1 owns columns 4-7, and so on — a reels key's array MUST
  preserve this left-to-right screen-position order, the same way `RasterRampProgram`'s
  fields are positional-by-constructor-argument-order (item 6 §1.1's note) rather than
  named. A JSON spelling that let authors name bands out of screen order, or that
  round-tripped through a dict keyed by an arbitrary band name, would silently scramble
  which strip is where on screen unless the generator re-imposed left-to-right order
  before emission.

---

## 6. The naming trap, stated as its own section per the brief's instruction

**The obvious surface is `v_deform` (or an arm added to it), and it is WRONG — verified
against source in §2, not assumed from the brief or the booking.** The reasoning, restated
for this document's own record rather than only the ruling's:

- `SceneVDeform.Columns(Label, int, int)` (`engine/level/scene_dsl.emp:353-356`) carries
  exactly one table, one speed, one amplitude shift — no per-band array field anywhere in
  its payload for independent rates to occupy, the same class of absence item 6's artifact
  found in `RasterRampProgram` for a per-line curve (§6 of that document): "the engine has
  no field to receive either."
- The runtime consumer (`engine/level/parallax.emp:2232-2270`) advances exactly ONE phase
  (`Parallax_V_Deform_Phase_BG`) per frame and samples ONE table at `phase + column` for
  every column in the loop (`:2258-2268`) — verified at the instruction level in this
  pass, not paraphrased. Two adjacent columns' values necessarily differ by at most the
  table's own slope between two adjacent entries; with a bounded, wrapping 256-entry
  table (`TABLE_GENERATORS`, `effects_gen.py:168-174`, all sine/triangle/zero/perspective/
  floor shapes) that difference is bounded and PERIODIC — the columns re-synchronise every
  time the shared phase completes a table cycle.
- `OJZ_Reels_Fill`'s own defining property is the opposite: 5 UNBOUNDED, NEVER-
  RESYNCHRONISING per-band accumulators (`ojz_effects.emp:1651-1665`'s own header:
  "band 3's strip moves at -4 px/frame whether band 0's is moving at +3 or has been
  swapped for +30, permanently, not 'for a few frames until the phases realign'"). A `v_deform`
  arm, by construction, cannot produce this — it is architecturally a shared-phase-sampled
  wave, and no amount of table authoring changes that.
- **The MUST-NOT, stated as its own sentence for this document's own description**: a
  `reel`-named key must author `REEL_BAND_COUNT` independent constant per-band rates over
  a fixed column split, and must NOT be built as a new arm, mode, or parameter of
  `SceneVDeform`/`v_deform` — that enum's wire shape has no field to receive independent
  per-band state, and giving it one would either break the six shipped `v_deform` scenes'
  existing meaning or require a parallel, differently-typed variant that is not really
  `v_deform` at all (i.e., it would just be this document's proposed new key, wearing the
  old key's name).

---

## 7. The authored range — resolved from the `ensure`s, and where this item's story differs from item 6's

**The AUTHORED RANGE is the contract, not the storage width — the same rule item 6's
artifact restated from `patch_world_ys`.** Applied here, field by field:

| field | authored contract (the `ensure`s) | storage (implementation note only) |
|---|---|---|
| `REEL_BAND_COUNT` | **fixed at 5**, not author-chosen — no range at all, only an identity `ensure` (`ojz_effects.emp:1642-1643`) tying it to `VSCROLL_COL_PAIRS` | plain `pub const` int (`constants.emp:66`), untyped/unsized in `.emp` terms |
| `REEL_COLS_PER_BAND` | **fixed at 4**, not author-chosen — `ensure(REEL_COLS_PER_BAND == 4, ...)` (`:1648-1649`) refuses ANY other value outright, because the shift amount in `OJZ_Reels_Fill` is hand-coded to match | plain `pub const` int (`constants.emp:67`) |
| each element of `OJZ_REEL_SPEEDS` | **NO explicit numeric range `ensure` at all.** The only per-array checks are `.len == REEL_BAND_COUNT` (`:1667-1668`) and pairwise distinctness (`:1669-1670`) — neither bounds a single value's magnitude | `i8` (`ojz_effects.emp:1666`'s `[i8; REEL_BAND_COUNT]` annotation) — nominally -128..127, but see §4's flag: whether sigil's literal-to-`i8` array assignment actually refuses an out-of-range literal is **NOT ESTABLISHED** in this pass |
| `OJZ_Reel_Phase` (runtime accumulator, not authored) | N/A — not an authored quantity; wraps mod 256 by design (`ojz_effects.emp:1706`'s own comment, "wraps at 256... exactly like a slot-machine reel") | `u8` (`games/sonic4/config/ram.emp:357`) |

**Applying item 6's lesson pre-emptively, as the brief asked, and finding it does NOT
reproduce the same gap — a different one instead.** Item 6's trap was a storage width
roughly 64x wider than the authored contract (`ensure`-bounded `-512..511` inside a raw
16.16 `u32`). Here, for the one field that actually varies per authored instance
(`OJZ_REEL_SPEEDS`'s elements), **the storage type (`i8`, -128..127) and the "authored
contract" are the SAME range, because no `ensure` narrows it further** — there is no gap
between a stated contract and a wider storage box, because there is effectively no
stated numeric contract at all beyond whatever `i8` itself enforces (and per §4, even that
enforcement point is not confirmed from this pass). **The real finding for this item is
not "the range disagrees with storage" — it is "there is no authored-range `ensure` to
disagree with in the first place."** A future CR's generator, if it wants speeds bounded
to something narrower than raw `i8` (e.g., a sane "on-screen" ceiling the way `layer()`'s
`drift.rate` has `-4096..4096` even though its underlying storage is wider, per item 6's
artifact's own citation of that field), would be introducing a NEW bound that does not
exist in the engine today, not merely restating an existing one correctly.

---

## 8. What could NOT be established in this pass

- **Whether sigil's frontend actually refuses an out-of-`i8`-range literal inside a
  `[i8; N]` const array assignment**, or silently truncates/wraps it (§4, §7). This is a
  sigil-frontend implementation question, and this pass deliberately stayed inside aeon
  source per its own bar (transcribe from THIS tree at THIS SHA), the same boundary item
  6's artifact drew around `u16`/`u32` field-width behaviour.
- **Whether `GameState_OJZScroll_Update` (`games/sonic4/test/ojz_scroll_test.emp`) is a
  general per-frame update path every real section would go through, or a demo-only
  harness** — load-bearing for §3 step 5's claim about what a generator-driven (as opposed
  to fixed-demo) reels feature would need to hook into. Not traced further; out of scope
  for a document that changes no code and was not needed to answer the four spine
  questions from the shipped mechanism's own shape.
- **Whether a real per-section reels mechanism needs a NEW engine hook in
  `Parallax_Update` itself** (rather than an override called after it, as `OJZ_Reels_Fill`
  is today), or whether the override-after-fill pattern is fine to keep and simply needs
  per-scene rate storage instead of the one fixed global `OJZ_Reel_Phase`/`OJZ_Reel_Speed`
  pair. This is the single largest open architectural question for the hub's CR — the
  DEFERRED_WORK booking's own "costed, not built" note
  (`docs/DEFERRED_WORK.md:19100`-`19113`, the "Aurora authoring key was deliberately NOT
  built" paragraph) names it as at least size M without resolving it, and this pass adds
  no new information toward resolving it — it only confirms, from source, that no such
  hook exists today.
- **What a JSON spelling for the 5-element rate array should look like** (bare array vs.
  object-keyed-by-band, per §2's closing paragraph) — named as a candidate shape
  constraint (order-significant, left-to-right screen position, per §5), not decided.
- **Whether `distinct5()`'s hardcoded 5-ary shape would need generalizing** if
  `REEL_BAND_COUNT` ever changed, and what that generalization would look like (a
  `comptime for`-driven all-pairs check, presumably, but no such idiom was found reused
  elsewhere in this pass to confirm the pattern against).
- **Cost/budget for `OJZ_Reels_Fill` itself** (main-loop cycles per frame, not an HBlank
  raster-fire cost) — not measured; `tools/reels_gate.py`'s own scope (per the landing
  record, not re-run here) proves the SOURCE reached the ROM, not a cycle count.
- **Whether `OJZ_Reels_Fill` has ever been observed on screen** — the landing record
  states the tagged runtime pass (`tools/reels_witness.py`) has been run and found the
  mechanism sound with a corrected expectation (`docs/DEFERRED_WORK.md:19023`-`19060`),
  but that is a numeric RAM-buffer check, not a rendered-picture confirmation, and no
  build or emulator run was performed in this documents-only pass to re-verify either
  claim (bar: "no build is required... but if you touch anything the build reads, verify
  all four shapes", and this parcel touches nothing the build reads).

---

## 9. Doc sync

`docs/DEFERRED_WORK.md`'s item 10a booking (`:18840` heading) now points at this
artifact — a pointer paragraph was appended at the end of the item 10a block (the true end
of the file at the time of this edit, after the "Research" subsection's closing bullet),
mirroring the paragraph item 6's booking carries for its own key-shape document
(`docs/DEFERRED_WORK.md:17069-17075`). Only that one paragraph was added; no other line in
the file was touched, and the edit lands at the file's tail, away from the sections the
two other agents in this tree are working in (`tools/effects_gen.py`,
`engine/effects/raster.emp`, and an unrelated `tools/` listing-reading fix).
