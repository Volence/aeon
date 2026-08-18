# Scanline Services P1 — Scene Model + Registry + Byte-Identical Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.
>
> **HARD RULE — CONTROLLER-ONLY tasks:** Tasks 10 and 11 use the emulator / `refreeze
> --ab` harness. **Never dispatch these to a subagent** (oracle MCP from background agents
> deadlocks). All other tasks are subagent-safe (build + file edits only).
>
> **PRE-EXECUTION DEPENDENCY:** the raster-substrate lens sweep (running in a parallel
> session over engine/effects/* + bg_anim) must have its findings adjudicated and any fixes
> LANDED before Task 9 onward executes — the migration freezes those bytes as the identity
> baseline. Tasks 1–8 (new modules, no engine edits) may proceed in parallel with the sweep.
>
> **DEPENDENCY STATUS 2026-08-18 — RESOLVED. The sweep exists; it had run in a session that
> wrote its packet only to `/tmp`.** My earlier note here said "never launched" on the
> evidence that no `review/raster-*` branch or worktree existed and the string appeared
> nowhere in the repo. That evidence was sound and the conclusion was wrong — a scratchpad
> artifact is invisible to every other session. Now imported to master:
> `docs/superpowers/2026-08-18-raster-substrate-sweep-adjudication.md` (+ `…-packet.jsonl`,
> 16 seats raw), and booked in `docs/DEFERRED_WORK.md` under "Raster substrate lens sweep".
>
> **What it means for Task 9.** 15 seats, 117 raw findings, **7 confirmed defects** (4
> substrate + 3 gate-soundness), 1 major refuted. Two facts change the shape of the gate:
> - **The charter EXCLUDED the parallax walker and fill internals** (P3 rewrites them);
>   `bg_anim` was in scope. So the sweep says nothing about the config records THIS parcel
>   re-authors — unexamined, not cleared. Do not read it as blessing the migration's subject.
> - **Nothing it found is in P1's removal set.** P1 deletes only
>   `games/sonic4/data/parallax/`; `raster.emp`, `raster_dsl.emp`, `palette.emp`,
>   `buffers.emp`, `bg_anim` and `tools/` all survive untouched, so no finding expires and
>   none of it needs folding into this parcel's diff.
>
> **RULING: the substrate fixes land as their OWN parcel off master, NOT in this branch.**
> Two byte-moving changes in one branch make a crc diff unattributable (the confounding that
> voided the prebatch A/B). Sequence: tasks 4–8 here (new modules, byte-neutral) ∥ substrate
> parcel on master → merge master into this branch → **then** Task 9 freezes against the
> corrected baseline. Byte-moving fixes are free before Task 9 and cost a deliberate repin +
> `refreeze --freeze --ab` after; that cost is modest and is explicitly NOT a reason to leave
> a defect standing — this gate is differential (did the migration change anything), never a
> claim that the frozen bytes are good.

**Goal:** Introduce the authored scene model (`layer()`/`scene()` constructors), the
per-game scene registry with capability-mask fold, and migrate all 20 shipped parallax
configs to scenes — producing image-identical ROMs across all four shapes.

**Architecture:** New pure-comptime `engine/level/scene_dsl.emp` (enum attachments,
constructors, capability fold, lowering to the EXISTING `parallax_config`/`band_entry`
records); new `games/sonic4/data/effects/scene_registry.emp` (the sole emission path) and
`ojz_scenes.emp` (the 20 migrated configs + 6 deform tables, emitting the SAME data symbol
names so consumers don't change); an equivalence-proof test module that keeps the old
`hdr()`/`band()` constructors alive as the word-level oracle; `data/parallax/` deleted.
No runtime code changes in P1 — the walker, raster, preset, and buffers modules are
untouched.

**Tech Stack:** sigil `.emp` (comptime), `emp_expect_fail.py` poison lane, `refreeze
--freeze --ab` + replay fixtures for image identity.

**Spec (single source of truth):**
`docs/superpowers/specs/2026-08-17-scanline-services-design.md` r2 (§2, §3, §8.1, §10-P1).
Where this plan and the spec disagree, the spec wins — stop and reconcile.

**Standing project rules that bind every task:**
- Build both shapes: `DEBUG=1 ./build.sh` AND `./build.sh`; also `./build.sh demo` +
  `DEBUG=1 ./build.sh demo` (P1's gate is FOUR-shape). `SIGIL_BUILD`/`SIGIL_EMIT` exported.
- Commit after every task — exact paths only, `git branch --show-current` first.
- `.emp` gotchas: comptime free names resolve at the CALL SITE (inline literals in helper
  bodies — never rely on imported names inside constructor bodies); `Label` vs int
  comparisons are silently unevaluable in `ensure` (compare ints only); no multi-line
  ensure conditions; `ensure` is non-aborting (Poison); unreachable modules validate
  NOTHING (guards live in always-reachable constructors).
- If a step's premise is false at the file (missing helper, moved line, spike fails),
  **STOP and report BLOCKED** — do not silently adapt the design.

**Branch:** create `feature/scanline-p1-scene-model` from master before Task 1.

---

## File Map

| File | Role in this parcel |
|---|---|
| `engine/level/scene_dsl.emp` | NEW — enums, `layer()`, `scene()`, capability fold, lowering (Tasks 2–3) |
| `engine/system/game_contract.emp` | +`const SCANLINE_CAPS` in the Game interface (Task 4) |
| `games/sonic4/config/game.emp` | bind SCANLINE_CAPS (computed or verified-hand-written per spike) (Task 4) |
| `games/demo/config/game.emp` | bind `SCANLINE_CAPS = 0` (Task 4) |
| `games/sonic4/data/effects/scene_registry.emp` | NEW — `SCENES` list, fold, emission, registry ensures (Task 5) |
| `games/sonic4/data/effects/ojz_scenes.emp` | NEW — 20 scenes + 6 deform tables, emits old symbol names (Task 6) |
| `games/sonic4/test/scene_equiv_proof.emp` | NEW — old `hdr()`/`band()` as oracle, per-config word proofs; the PERMANENT capability-off witness (Task 7) |
| `games/sonic4/test/poison/poison_scene_*.emp` + `tools/emp_expect_fail.py` CASES | NEW poisons (Task 8) |
| `games/sonic4/data/parallax/` (delete), `act_descriptor.emp`, `ojz_effects.emp`, `ojz_scroll_test.emp`, `map.toml` | consumer rewire + deletion (Task 9) |
| `docs/ENGINE_ARCHITECTURE.md`, `docs/DEFERRED_WORK.md` | sync (Task 12) |

---

### Task 1: Spike — registry emission, typed records, computed Game const

**Files:** scratch module `games/sonic4/test/spike_scene_registry.emp` (deleted at task end)

Three feasibility questions the spec left to P1. Build a throwaway module answering each
with a compiling (or cleanly-failing) probe; report findings verbatim in the task report.

- [x] **Step 1:** Probe A — can a `pub const` (or comptime array) hold an array of struct
  values (`[parallax_config; 2]`-of-values built by a comptime fn) and can a comptime fn
  fold over it (`for` + field access) into an int? Mirror the shape `RasterOp` arrays use
  in `raster_dsl.emp` (comptime enum arrays exist — confirm the same works for plain
  structs).
- [x] **Step 2:** Probe B — can one comptime fn return different wrapper types
  (ParallaxCfg1 vs ParallaxCfg5)? Expected NO (no generics) — confirm, so the lowering
  keeps per-count emission (`if` chains or per-count fns). Also probe: `data X: T = <call>`
  where the call returns the nested struct — this is exactly how configs.emp works today,
  so it must pass.
- [x] **Step 3:** Probe C — in `implement Game`, can a const bind a computed comptime
  expression (e.g. `const SCANLINE_CAPS = caps_fold()` where caps_fold is imported)?
  Precedent is only an imported literal (`ENTRY_ID = GS_OJZ_SCROLL_TEST`,
  games/sonic4/config/game.emp:23). If NO: the fallback is RULED (spec §3.2) — game
  hand-writes the mask word; a registry-side `ensure(mask == folded)` verifies it.
- [x] **Step 4:** Delete the scratch module. Report: A yes/no, B shape chosen, C
  computed-vs-fallback. Commit nothing except the report (no files remain).

> **TASK 1 SPIKE FINDINGS (2026-08-17, all build-proven; bind later tasks):**
> - **A:** `pub const X: [T; N] = [ctor(), ctor()]` + `for b in bands { acc + b.field }`
>   folds work. **One-dot rule:** chained access (`c.bands.len`) NEVER resolves — split
>   through a `comptime var`. Unwired modules' ensures are DEAD — wire via `use` before
>   trusting any guard.
> - **B:** comptime fn return annotations are documentation; enforcement is the typed
>   `data X: CfgN = fn()` binding (`array length mismatch` on wrong count). Per-count
>   typed `data` is the emission shape. A NEW emitting module needs `module … in <sect>`
>   AND a `map.toml` order entry for its head label (build fails loud without both).
> - **C:** computed `const SCANLINE_CAPS = fold()` in `implement Game` WORKS and the
>   engine reads `Game.SCANLINE_CAPS` in comptime `if`. CATCH: the manifest call site
>   re-evaluates the whole chain — game.emp must `use` every pub helper + const the fold
>   touches, transitively (misses fail LOUD). Keep the fold's helper chain small.

### Task 2: scene_dsl — enums + `layer()` constructor

**Files:** Create `engine/level/scene_dsl.emp`

Pure-comptime module (emits zero bytes itself — mirror the `parallax_dsl.emp:9-11`
banner). All ensures live HERE (always in the use closure of any game that authors scenes
— the dead-guard rule).

- [x] **Step 1:** Module skeleton + capability-bit consts:

```
// engine/level/scene_dsl.emp — the authored scene model (spec 2026-08-17 §2/§3).
// Pure comptime: constructors, capability fold, lowering to parallax_config/band_entry.
// GUARDS LIVE HERE: this module is in the use closure of every scene author, so its
// ensures always evaluate (the preset.emp reachability lesson).
module engine.level.scene_dsl in scene_dsl

use engine.structs.{parallax_config}
use engine.parallax.{band_entry}
use engine.constants.{MAX_PARALLAX_BANDS, PARALLAX_ANCHOR_NONE}
use engine.effects.raster_dsl.{RASTER_MAX_PATCH}

// Capability bits (packed mask; consumed by the engine from P2 on).
pub const CAP_PER_LINE       = $0001
pub const CAP_PER_COL_VSRAM  = $0002
pub const CAP_DEFORM         = $0004
pub const CAP_ANCHORS        = $0008
pub const CAP_TRANSITIONS    = $0010
// Reserved (P3+): CAP_MULTI_DEFORM_TABLE=$0020, CAP_FACTOR_CURVE=$0040,
// CAP_FG_SPRITE_STRIPS=$0080, CAP_BGANIM_BOUND=$0100, CAP_DENSE_TIER=$0200,
// CAP_COMPUTED=$0400, CAP_DEGRADE=$0800
```

- [x] **Step 2:** Attachment enums — comptime enums with payloads (the `RasterOp`
  precedent, raster_dsl.emp:83-105). NO `Label = 0` defaults anywhere (spec §3.1):

```
// Scene-level shared deform (today's semantics: one table+speed per plane).
pub comptime enum SceneDeform {
    none,
    shared(table: Label, speed: int),
}
// Per-column VSRAM (rocking/perspective family).
pub comptime enum SceneVDeform {
    none,
    columns(table: Label, speed: int, shift: int),
}
// World-anchored overlay (Parcel W).
pub comptime enum SceneAnchor {
    none,
    at(ch: int, dsa: int, dsb: int),
}
pub const PRECISION_CELL = 0
pub const PRECISION_LINE = 1
pub const TRANS_SMOOTH = 0
pub const TRANS_INSTANT = 1
```

- [x] **Step 3:** `SceneLayer` + `layer()` — world-Y authored, cell-quantum ensured:

```
pub struct SceneLayer {
    ly_world_y:  int,   // act-space top, px
    ly_fa:       int,   // packed FACTOR_* (parallax_dsl encoding)
    ly_fb:       int,
    ly_dsa:      int,   // deform amplitude shifts (15 = skip)
    ly_dsb:      int,
    ly_phase:    int,
    ly_enabled:  int,   // 1 = in layer_mask
}

pub comptime fn layer(world_y: int, fa: int, fb: int, dsa: int = 15, dsb: int = 15,
                      phase: int = 0, enabled: int = 1) -> SceneLayer {
    // P1 lowering targets band_top_cell exactly (spec §3.1 byte-identity precondition).
    ensure(world_y % 8 == 0,
           "layer(): world_y {world_y} is not on the 8-px cell grid — P1 lowering requires cell alignment (spec 3.1); off-grid tops arrive with world-Y re-glue (P3)")
    ensure(world_y >= 0 && world_y < 512,
           "layer(): world_y {world_y} outside the 512-px BG plane span (P1 keeps plane-cell anchoring; act-tall world-Y arrives in P3)")
    return SceneLayer{ ly_world_y: world_y, ly_fa: fa, ly_fb: fb, ly_dsa: dsa,
                       ly_dsb: dsb, ly_phase: phase, ly_enabled: enabled }
}
```

- [x] **Step 4:** Build both sonic4 shapes (module not yet used — must not break
  anything). Expected: green, ROM bytes unchanged.
- [x] **Step 5:** Commit `engine/level/scene_dsl.emp`.

### Task 3: scene_dsl — `scene()`, capability fold, lowering

**Files:** Modify `engine/level/scene_dsl.emp`

- [x] **Step 1:** The `Scene` value + `scene()` constructor. Ports the two load-bearing
  hdr() guards BY NAME (spec §3.1). `layer_mask_raw` exists solely because shipped configs
  carry mask bits beyond band_count (OJZ_Default: 4 bands, mask $1F) that derived masks
  cannot reproduce — byte-identity bridge, documented:

```
pub struct Scene {
    sc_layers:      [SceneLayer; 8],  // padded; sc_count says how many are real
    sc_count:       int,
    sc_v_factor:    int, sc_v_center: int, sc_v_offset: int, sc_v_factor_fg: int,
    sc_deform_fg:   SceneDeform,
    sc_deform_bg:   SceneDeform,
    sc_v_deform:    SceneVDeform,
    sc_anchor:      SceneAnchor,
    sc_precision:   int,
    sc_transition:  int,
    sc_mask_raw:    int,   // -1 = derive from ly_enabled
}

pub comptime fn scene(layers: [SceneLayer; 8], count: int,
                      v_factor: int, v_center: int = 0, v_offset: int = 0,
                      v_factor_fg: int = 0,
                      deform_fg: SceneDeform = SceneDeform.none,
                      deform_bg: SceneDeform = SceneDeform.none,
                      v_deform: SceneVDeform = SceneVDeform.none,
                      anchor: SceneAnchor = SceneAnchor.none,
                      precision: int = PRECISION_CELL,
                      transition: int = TRANS_SMOOTH,
                      layer_mask_raw: int = -1) -> Scene {
    ensure(count >= 1 && count <= MAX_PARALLAX_BANDS,
           "scene(): {count} layers exceeds MAX_PARALLAX_BANDS ({MAX_PARALLAX_BANDS})")
    // Ported hdr() guard 1: an anchored scene SPLITS a layer at runtime (+1 shadow entry).
    // Ported hdr() guard 2: anchor channel must index the patch bank.
    // Both compare INTS (enum match first) — Label comparisons are unevaluable.
    ...match anchor { at(ch, dsa, dsb) => {
        ensure(count + 1 <= MAX_PARALLAX_BANDS, "scene(): anchored scene needs count+1 shadow entries — {count}+1 exceeds MAX_PARALLAX_BANDS")
        ensure(ch < RASTER_MAX_PATCH, "scene(): anchor ch {ch} is not a patch channel (RASTER_MAX_PATCH {RASTER_MAX_PATCH})")
    }, none => {} }
    // P1 scope fences (reserved features fail loud, not silently):
    ...ensure precision == PRECISION_LINE requires deform_bg != none in P1
       (message: "P1: precision line rides a zero-deform table (DeformTable_Zero pattern); standalone precision lowering lands with the forcer-set derivation (P2/P3)")
    return Scene{ ... }
}
```

  (The `...match` sketches above are written out fully in the file — exhaustive match on
  every enum, no default arms.)

- [x] **Step 2:** Capability fold — one scene → mask, and the registry-level OR:

```
pub comptime fn scene_caps(s: Scene) -> int {
    // per-line forcers (P1 subset of the spec's forcer set: deform tables + anchor;
    // curves/strips/off-grid arrive with their capabilities):
    // CAP_PER_LINE if any deform table attached or anchored;
    // CAP_DEFORM if any table with a non-15 amplitude anywhere;
    // CAP_PER_COL_VSRAM if v_deform != none; CAP_ANCHORS if anchored;
    // CAP_TRANSITIONS if transition == TRANS_SMOOTH is USED by a multi-scene game —
    //   P1 ruling: always set when the registry holds >1 scene.
    ...
}
```

- [x] **Step 3:** Lowering — `scene_hdr(s) -> parallax_config` and
  `scene_band(s, i) -> band_entry`, producing field-for-field what configs.emp's `hdr()`
  and `band()` produce today (same packing: `fa & 15`, `(fa >> 4) & 15`, `(fa >> 8) & 1`;
  mask = raw override or derived; enum matches map to the pcfg_* fields, `SceneDeform.none`
  → table 0 speed 1, exactly hdr()'s defaults). All literal packing INLINE in the fn body
  (call-site resolution rule).
- [x] **Step 4:** Build both sonic4 shapes: green, bytes unchanged. Commit.

> **TASK 3 FINDINGS (2026-08-18, all build-proven; commits a82cab59 + c9029388; two
> review stages passed). Bind later tasks:**
> - **The authored surface** is `scene(layers, count, v_factor, v_center, v_offset,
>   v_factor_fg, deform_fg, deform_bg, v_deform, anchor, precision, transition,
>   layer_mask_raw, v_deform_shift_raw)`, lowering through `scene_hdr(s)` /
>   `scene_band(s, i)`, folding through `scene_caps(s)` / `fold_caps(scenes)`.
> - **`match` is expression-form only** (`Expr::Match` exists, no statement form), so the
>   spec's `match anchor { at(..) => ensure(..) }` sketch is unwritable. Enum payloads are
>   read through ten exhaustive `pub` accessors and every `ensure` compares INTS at the top
>   level of `scene()` — which is also the only *correct* spelling, since an `ensure`
>   comparing a `Label` to an int is silently unevaluable. The two `hdr()` guards are ported
>   by name and read identically to the originals, which is what keeps Task 7 a proof.
> - **LANGUAGE TRAP — an `if` in block-tail position evaluates to UNIT, not a value.**
>   `if a {1} else { if b {1} else {0} }` yields `()` whenever only the inner test is true.
>   No diagnostic. This silently folded a BG-only-deform scene to `caps = 0` and was caught
>   only by an independently-derived expected value. Use a flat accumulator over statement
>   `if`s. Single-level if-expressions are fine; a *call* in block-tail position is fine.
>   General trap for every `comptime fn` in the tree — booked for upstream in Task 12.
> - **An unreached module has parse + scan coverage and ZERO body-elaboration coverage.**
>   Measured: a syntax error in the file fails the build, but `return unknown_name +
>   MISSING_CONST` inside an uncalled `pub comptime fn` builds green with an unchanged CRC.
>   So Task 2's banner claim that these guards "always evaluate" was false, and every guard
>   here stays dead until Task 6 supplies a caller. Red-first via a temporary probe wired
>   from a placed module is the only evidence that a guard in this file can fail.
> - **`derived_mask(layers, count)` works as a SHARED helper** called from both `scene()`
>   (superset guard) and `scene_hdr()` (emitted mask) — one derivation, no drift. The
>   one-dot rule is not violated: `layers[i]` then `l.ly_enabled` is index-then-one-dot.
> - **`for i in count..8` is valid** (variable lower bound). Degenerate case is benign:
>   `ensure` is non-aborting, so `count: 9` runs `for i in 9..8`, an empty reverse range
>   with no spurious diagnostic — no clamp needed.
> - **Byte identity is MEASURED, not assumed.** Nine shipped configs were re-authored
>   through this surface, emitted beside the originals and byte-compared at `.lst` offsets:
>   all identical, covering both bridges, the anchored case, split FG/BG tables, and the
>   opposite-polarity deform-speed defaults. **No third bridge species exists.**
> - **The int surface is closed:** five `ensure`s in `scene()` cover the pad slots, the mask
>   superset (`raw` may only ADD bits), `layer_mask_raw` in `-1..$FF` (a wider value wraps
>   the i16 bridge and silently reads back as derive), `v_deform_shift_raw` in `-1..15`, and
>   both selectors pinned to `0 || 1`.

### Task 4: Game contract — SCANLINE_CAPS

**Files:** Modify `engine/system/game_contract.emp`, `games/sonic4/config/game.emp`,
`games/demo/config/game.emp`

- [x] **Step 1:** Add to the Game interface: `const SCANLINE_CAPS` with a doc comment
  ("packed capability mask; derived-and-verified from the game's scene registry; engine
  consumers arrive in P2 — until then this is contract surface only").
- [x] **Step 2:** demo binds `const SCANLINE_CAPS = 0`.
- [x] **Step 3:** sonic4 binds per the Task-1 spike: computed
  (`const SCANLINE_CAPS = SceneRegistry_CapsFolded` imported from the registry) or the
  RULED fallback (hand-written `$001D`-style literal; the registry ensure in Task 5
  verifies it — derive-and-verify, never hand-maintained-unchecked).
- [x] **Step 4:** Build all four shapes green (no engine consumer yet — pure contract).
  Commit all three files.

> **TASK 4 SEQUENCING + DERIVED VALUE (controller, 2026-08-18) — read before executing:**
> - **Forward dependency, resolved:** Step 3's preferred binding
>   (`SCANLINE_CAPS = SceneRegistry_CapsFolded`) imports from the registry, which does not
>   exist until Task 5. Adding a const to the Game interface obliges BOTH games to bind it
>   or the contract-closure gate fails, so Task 4 cannot wait. Ruling: Task 4 binds sonic4
>   to the **declared literal** with the registry ensure named in a comment as its pending
>   verifier; **Task 5 adds the `folded ⊆ declared` ensure** and may then flip the binding
>   to computed. This is the spec's derive-and-verify posture, not hand-maintained-unchecked
>   — but it means **Task 5 must not be skipped or reordered**, because until its ensure
>   lands the declared word is unverified. Task 1's spike proved computed consts work, so
>   the flip is available; it is a preference, not a blocker.
> - **The declared word is `$001F`,** derived from the shipped configs (do NOT copy the
>   plan's illustrative "`$001D`-style" literal in Step 3 — it is wrong by one bit):
>   `CAP_PER_LINE $01` (deform tables throughout) | `CAP_PER_COL_VSRAM $02`
>   (`v_deform_bg` at configs.emp:216 Rocking, :236 Perspective — the bit `$001D` omits) |
>   `CAP_DEFORM $04` (live non-15 amplitudes, e.g. anchor_dsb 2 at :135, Windy dsa 4) |
>   `CAP_ANCHORS $08` (anchor_ch 0 at :135, Underwater) | `CAP_TRANSITIONS $10` (registry
>   holds 20 > 1). Re-derive rather than trusting this; it is recorded so a mismatch is a
>   conversation, not a silent overwrite.

### Task 5: Scene registry

**Files:** Create `games/sonic4/data/effects/scene_registry.emp`

- [x] **Step 1:** The registry module — the SOLE emission path (spec §3.2):

```
// games/sonic4/data/effects/scene_registry.emp — the game's scene registry.
// THE ONLY module that lowers scenes to ROM records. A scene value not listed in
// SCENES emits nothing — its section reference fails at link with a missing symbol.
// Cross-scene checks and the capability fold live here (they need VALUES, not Labels).
module games.sonic4.scene_registry in scene_registry
```

  Holds: `pub const SCENES = [Scene_OJZ_Default, Scene_OJZ_Underwater, ...]` (all 20,
  imported from ojz_scenes), the fold
  `pub const SceneRegistry_CapsFolded = fold_caps(SCENES)`, and (fallback mode) the
  verify ensure `ensure(Game.SCANLINE_CAPS == SceneRegistry_CapsFolded, "game.emp mask
  {Game.SCANLINE_CAPS} != folded {SceneRegistry_CapsFolded} — update the declared word")`.
  Force-enable semantics (spec §3.2): the ensure becomes `folded ⊆ declared`:
  `ensure((SceneRegistry_CapsFolded & ~Game.SCANLINE_CAPS) == 0, ...)`.
- [x] **Step 2:** Emission fold: per registry entry, emit the lowered records under the
  entry's declared symbol name (per Task-1 probe B shape — per-count `if` chains are
  acceptable; ugly beats unbuildable).
- [x] **Step 3:** Build: green (registry not yet in map order — verify it participates
  once ojz_scenes lands in Task 6; if module placement is needed NOW, coordinate with
  Task 9's map.toml step and note it in the task report). Commit.

> **TASKS 4-5 FINDINGS (2026-08-18, build-proven; commits b14fa113 + 42e3e0f7). Bind Tasks 6-9:**
> - **The Game const is `const SCANLINE_CAPS: u16`**, sonic4 `$001F`, demo `0`. `$001F` was
>   independently re-derived twice (the plan's `$001D` was missing `CAP_PER_COL_VSRAM $0002`,
>   set by `v_deform_bg` at configs.emp:216/236). Contract closure is REAL — poison-probed:
>   `required member Game.SCANLINE_CAPS (a const) is not bound by the implement block`.
> - **A declared interface const type ENFORCES NOTHING.** sigil's `check_const_type` only
>   checks int-ish — no width or range check — so `ENTRY_ID: u8` is not range-guarded either.
>   `u16` documents intent only, which makes the registry's subset ensure the ONLY real check
>   on that word. (Booked for upstream in Task 12.)
> - **The registry's verify is the SUBSET form** `(folded & ~declared) == 0`, so a partially
>   populated registry stays legal while Task 6 migrates configs one at a time. `~` confirmed
>   present. **`ensure` messages interpolate ARBITRARY EXPRESSIONS** (`{folded & ~declared}`),
>   so a message can name the offending bits, not just the two operands — decimal only.
> - **REACHING AN UNPLACED MODULE: use the WHOLE PATH, never a name list.** A selective
>   `use games.sonic4.scene_registry.{Name}` makes sigil inject a CLONE of the const whose
>   initializer re-evaluates in the CONSUMER's scope — producing bogus errors (`unknown
>   function fold_caps`) at a span inside the registry while the module never elaborates at
>   all. `use games.sonic4.scene_registry` (no list) is what pulls it into placement. **This
>   will bite Task 7's oracle wiring.**
> - **An unreached module's `pub data` symbols do NOT enter the symbol table** — measured by
>   naming a placeholder `ParallaxConfig_OJZ_Default` while `configs.emp` still emits that
>   symbol: build green, crc unmoved. **So Task 6 may use the 20 SHIPPED names immediately,
>   which makes Task 9 a pure placement change with no rename step.**
> - **Emission must index `SCENES[i]`, never a scene const directly** — that is what makes
>   "every emitted record has been folded" structural instead of guarded.
> - **`lower1/2/4/5` exist and are proven by real emission** at 38/48/68/78 bytes. `lower3`,
>   `lower6/7/8` and their `SceneCfgN` DO NOT EXIST — the 20 shipped configs use only counts
>   1, 2, 4, 5 (14x Cfg1/2, 6x Cfg4/5). Adding a count is a struct line plus a `lowerN`.
> - Deform tables stay in `data/parallax/configs.emp` for Task 6 (they are Labels); **Task 9
>   rehomes them.**
> - Spelling trap: `./build.sh --no-lint` must be `./build.sh sonic4 --no-lint` — the game is
>   positional, so a bare flag parses as the game name.

### Task 6: Migrate the 20 configs — ojz_scenes.emp

**Files:** Create `games/sonic4/data/effects/ojz_scenes.emp` (configs.emp stays alive
until Task 9 — both exist during Tasks 6–8; the DUPLICATE data symbols must not both be
linked, so ojz_scenes' emitted data uses temporary `SceneOut_` prefixes until Task 9 swaps
names atomically. The equivalence proof compares SceneOut_* against the live ParallaxConfig_*.)

- [x] **Step 1:** Move the 6 deform tables verbatim (same generator calls, same names —
  these are data, not constructors: `DeformTable_Zero`, `_Shimmer`, `_OJZ_Calm`, `_Haze`,
  `_Rocking`, `_Perspective`) — temporary names `SceneOut_DeformTable_*` until Task 9.
- [x] **Step 2:** Author all 20 scenes. Complete mapping (source: configs.emp @ current
  master; `cell: N` → `world_y: N*8`):

```
// 4-band OJZ family (Default shown; Underwater = same layers + shimmer/anchor)
pub const Scene_OJZ_Default = scene(
    layers: [ layer(world_y: 0,   fa: FACTOR_1, fb: FACTOR_1_2),
              layer(world_y: 64,  fa: FACTOR_1, fb: FACTOR_1_2),
              layer(world_y: 320, fa: FACTOR_1, fb: FACTOR_1_2),
              layer(world_y: 384, fa: FACTOR_1, fb: FACTOR_1_2), PAD, PAD, PAD, PAD ],
    count: 4, v_factor: 3, v_center: 512,
    deform_bg: SceneDeform.shared(table: SceneOut_DeformTable_Zero, speed: 1),
    precision: PRECISION_LINE, layer_mask_raw: $1F)   // raw: shipped mask has bit 4 set

pub const Scene_OJZ_Underwater = scene(
    layers: [ same four layers ],
    count: 4, v_factor: 3, v_center: 512,
    deform_bg: SceneDeform.shared(table: SceneOut_DeformTable_Shimmer, speed: 3),
    anchor: SceneAnchor.at(ch: 0, dsa: 15, dsb: 2),
    precision: PRECISION_LINE, layer_mask_raw: $1F)
```

  Full roster with parameters (executor transcribes each from configs.emp lines cited):
  | Scene | Source | Distinguishing fields |
  |---|---|---|
  | OJZ_Default | :107 | above |
  | OJZ_Underwater | :132 | above (THE Parcel W fixture) |
  | OJZ_Windy | :150 | 1 layer, fb 1/4 dsa 4 dsb 0, Calm speed 1, v_factor 15, mask $01 |
  | Shimmer_Slow/med/Fast | :163-172 | shimmer_bg(speed 1/3/6) → keep a local comptime fn `shimmer_scene(speed)` mirroring it |
  | Haze_Slow/med/Fast/Uniform | :181-203 | `haze_scene(speed, gradient)` — 5 layers, world_y 0/32/80/112/160, fb 1_8..1, dsa/dsb per gradient arm, deform_fg Haze |
  | Rocking_Slow/med/Fast | :213-223 | `rocking_scene(speed, shift=0)` — 1 layer fb FACTOR_0 dsa 4 dsb 4, deform_bg Zero, v_deform columns(Rocking, speed, shift) |
  | Perspective_Subtle/med/Dramatic | :232-246 | `perspective_scene(v_shift,h_speed,v_speed)` — 5 layers fb FACTOR_0, deform_bg Shimmer, v_deform columns(Perspective, v_speed, v_shift) |
  | WindyHaze | :253 | 5 layers, per-layer phase 0/64/128/192/0, deform_fg Haze 2 + deform_bg Calm 1 |
  | SkyHaze | :269 | 2 layers world_y 0/112, deform pair, v_deform_shift 0 → carried via SceneVDeform? NO — shipped hdr sets v_deform_shift_bg: 0 with NO v-table; scene() lowers SceneVDeform.none to hdr's default shift 4, so SkyHaze needs the raw shift: add `v_deform_shift_raw: int = -1` scene field (byte-identity bridge, same species as layer_mask_raw) |
  | OJZ_Caves | :283 | 5 layers fb 1_16/1_16/1_8/1_4/1, transition INSTANT, deform Zero, mask $1F |
  | OJZ_LockedClouds | :299 | 5 layers, layer 0 enabled: 0, mask_raw $1E, transition INSTANT, deform Zero |

  `PAD` = `layer(world_y: 0, fa: FACTOR_1, fb: FACTOR_1, enabled: 0)` slots beyond
  sc_count — never lowered (sc_count bounds every fold; an ensure in scene() confirms
  pads beyond count are untouched by lowering).

> **TASK 6 AUTHORING FACTS (controller, 2026-08-18 — established by Task 3 + its two
> reviews; four correct the text above):**
> - **`PAD` is spelled `no_layer()`**, a constructor Task 3 added because `sc_layers` is a
>   fixed `[SceneLayer; 8]` and every author must spell 8 elements. Do NOT hand-write
>   `layer(..., enabled: 0)` as the pad: the pad ensure discriminates on `ly_fa == 0`, and
>   `FACTOR_1` is nonzero, so a `layer()`-built pad FAILS the guard. `no_layer()` is the
>   only thing in the model with `fa == 0`.
> - **`OJZ_LockedClouds` must NOT use the mask bridge.** The roster row above prescribes
>   `mask_raw $1E`; that is over-prescription. `$1E` **derives** from `enabled: 0` on layer
>   0, and the byte-identity probe confirmed the derived path reproduces it exactly. Author
>   it derived and leave `layer_mask_raw` unset — a bridge used where derivation works is a
>   guard surrendered for nothing.
> - **The mask bridge is needed TWICE, not once.** `OJZ_Underwater` (configs.emp:132-134)
>   has the same `band_count: 4, layer_mask: $1F` shape as `OJZ_Default`. Those two configs
>   are the complete set of mask-bridge users.
> - **`precision: PRECISION_LINE` does not synthesize a table.** Spec §2 reads as though it
>   lowers to a DeformTable_Zero attachment; the implemented constructor instead *fences*
>   it (line precision requires an attached BG table). So the zero-table configs must
>   **explicitly spell `deform_bg: SceneDeform.Shared(DeformTable_Zero, 1)`** alongside
>   `precision: PRECISION_LINE`. Byte-identical either way; the fence fails loud, so a
>   miss cannot ship silently.
> - **Scene modules MUST glob-import: `use engine.level.scene_dsl.*`** — never selective.
>   `scene_dsl` is not in sigil's `COMPTIME_HELPERS`, so its bodies' free names resolve at
>   the game call site. A selective import fails loud (~217 `unknown function` errors), so
>   this cannot ship broken, but it will waste a build cycle.
> - **Enum variants are PascalCase** (`SceneDeform.None`/`.Shared`, `SceneVDeform.None`/
>   `.Columns`, `SceneAnchor.None`/`.At`) — the lowercase spelling in the sketches above is
>   not the real surface.
- [x] **Step 3:** Register all 20 in scene_registry SCENES; emission produces
  `SceneOut_ParallaxConfig_*` records.
- [x] **Step 4:** Build both sonic4 shapes green (both old and SceneOut_ symbols linked —
  ROM grows temporarily; that's fine mid-branch, Task 9 restores). Commit.

> **TASK 6 FINDINGS (2026-08-18, commit e8babd62). Bind Tasks 7-10:**
> - **THE FOLD OVER ALL 20 REAL SCENES IS `$001F`** — hand-derived AND measured (a temporary
>   poison printed `folded=31 declared=31`, reverted before commit). The capability word is
>   now COMPUTED from the migrated data, not asserted. Per bit: CAP_PER_LINE all 20 ·
>   CAP_PER_COL_VSRAM Rocking x3 + Perspective x3 · CAP_DEFORM 17 (not OJZ_Default, Caves,
>   LockedClouds) · CAP_ANCHORS OJZ_Underwater alone · CAP_TRANSITIONS len > 1.
>   **OJZ_Underwater raises CAP_DEFORM only through its ANCHOR `dsb 2`** — all four of its
>   layers sit at 15 — which is exactly the case `scene_caps()`'s cross-plane anchor scan
>   exists for. That scan is now load-bearing, not defensive.
> - **NOTHING in the 20 source configs was inexpressible in the scene model, and no layer
>   count outside 1/2/4/5 was needed.** The model is complete for the shipped corpus.
> - **Exactly two mask bridges** (OJZ_Default, OJZ_Underwater) and one shift bridge
>   (SkyHaze). **LockedClouds derived `$1E` with no bridge**, as ruled. **No third bridge
>   species exists** — Task 3's finding now confirmed at full scale.
> - **THE ROSTER TABLE IN THIS PLAN WAS WRONG FOUR TIMES.** Transcribe from `configs.emp`,
>   never from the roster: (1) **Haze** — the roster says "dsa/dsb per gradient arm"; `dsb`
>   is **4 on every layer in both arms** and only `dsa` varies (`15/15/15/4/3` vs
>   `3/3/3/3/3`). Following the roster literally produces a WRONG Haze_Uniform. (2) Rocking's
>   `shift` does not vary — all three take the default. (3) Perspective omits the per-layer
>   `dsb` ramp `15/15/15/4/2` and the uniform `dsa 4`, which is the only thing distinguishing
>   its layers. (4) OJZ_Windy `$01` / OJZ_Caves `$1F` are listed as prescribed masks; both
>   derive.
> - **ROM growth: +684 debug / +671 plain** (s4.debug `89dc4c54` len 713436, s4
>   `72ef55f1` len 698539). Both demo shapes UNCHANGED at `10aad76c` / `2ecd1031` — nothing
>   leaked across the game wall. **`EndOfRom` is UNMOVED at `$A30D0` in both shapes**: the
>   2766 bytes of new records absorbed into the padding before the fixed sound-bank anchors,
>   so the whole image delta is the deb2 appendix for 26 new symbols. **Task 10 should expect
>   the post-swap ROM to return to the pre-Task-6 crcs exactly, not merely to a similar size.**
> - **LANGUAGE TRAP — `d0`-`d7` / `a0`-`a7` are REGISTER TOKENS.** A comptime `let d0 = ...`
>   binds a register, not an int. It fails loud (`a register is not a valid int argument`)
>   but the diagnostic points at the CALL SITE, not the binding, so the message does not name
>   the cause. Caught by the expect-fail lane's sentinel via diagnostic-count drift — that
>   guard earned its keep. Name comptime bindings `dsa0..dsa3`, never a register spelling.
>
> **CONTROLLER RULING — `precision` is a DEFAULT, not a claim (2026-08-18).** Task 6 asked
> whether the five flat-pathed configs (OJZ_Caves, OJZ_LockedClouds, Rocking x3) should join
> OJZ_Default/Underwater at `PRECISION_LINE`, since all seven use the identical
> zero-table-selects-per-line idiom. **Ruling: leave them, and BOOK the ambiguity instead** —
> `scene_dsl.emp` documents TWO different meanings for the field (the constants say band-top
> granularity; the fence says per-line HScroll pipeline selection) and they are not the same
> claim. In P1 the field is inert (not emitted, not read by `scene_caps()`, and `layer()`
> forces every top onto the 8-px grid anyway, so no shipped scene can want per-line tops).
> Marking five more scenes LINE would invent an unverifiable claim; leaving it undocumented
> would let the freeze enshrine a default as evidence. The ambiguity is now written at the
> constants in `scene_dsl.emp`, with the instruction that P2/P3 must settle the reading and
> RE-DERIVE all 20. Deriving it is the likely right answer — a hand-authored field with no
> consumer and no derivation is exactly how the capability mask started, and the mask now has
> both.

### Task 7: Equivalence proof module (the permanent witness)

**Files:** Create `games/sonic4/test/scene_equiv_proof.emp`; move (do not copy-and-keep)
`hdr()`/`band()` from configs.emp INTO this module at Task 9 — during Tasks 7–8 the proof
imports them from configs.emp.

- [x] **Step 1:** Field-wise compare helpers:
  `cfg_eq(a: parallax_config, b: parallax_config) -> int` returning the FIRST differing
  field index (-1 = equal; mirrors the "COMPOSITION EQUIVALENCE PROOF" localization idea
  at ojz_effects.emp:443-456 but field-wise, since these are structs not word arrays) and
  `band_eq(a, b, i)` likewise.
- [x] **Step 2:** Per-config proof, all 20 — pattern (full code for each in the file):

```
// Proof: Scene_OJZ_Default lowers to exactly the shipped record.
ensure(cfg_eq(scene_hdr(Scene_OJZ_Default), hdr(band_count: 4, layer_mask: $1F,
       v_factor_bg: 3, v_center: 512, v_offset: 0, deform_bg: SceneOut_DeformTable_Zero)) == -1,
       "Scene_OJZ_Default hdr mismatch at field {…}")
ensure(band_eq(scene_band(Scene_OJZ_Default, 0), band(cell: 0, fa: FACTOR_1,
       fb: FACTOR_1_2, dsa: 15, dsb: 15), 0) == -1, "…")
// … ×4 bands, ×20 configs
```

  NOTE the oracle hdr() call passes the SceneOut_ deform table (same generator output) —
  table CONTENT equality is proven separately by one
  `ensure(first_mismatch_i8(SceneOut_DeformTable_Zero_src, deform_zero()) == -1, …)`
  per table against the generator call (both sides comptime arrays).
- [x] **Step 3:** Reachability: wire the proof module into the test lane the way the
  existing test modules reach the build (check how `ojz_scroll_test.emp` and the poison
  sentinel enter the closure — `--extra-entry` lane per BUGS.md EFX-10 replacement; use
  the same mechanism). Verify it actually evaluates: temporarily flip one expected field,
  see the build FAIL, flip back (red-first, recorded in the task report).
- [x] **Step 4:** Build green. Commit. **This module is permanent** (spec §8.1 standing
  witness) — its banner says so and names the spec.


> **TASK 7 FINDINGS (2026-08-18, build-proven, all four crcs unchanged). Bind Tasks 8-10:**
> - **REACHABILITY IS ONE `use` EDGE, AND `--extra-entry` WOULD HAVE BEEN THE WRONG ANSWER.**
>   Placement is the sigil REGISTRY — a hardcoded Rust list (`registry()` in
>   crates/sigil-harness/src/native.rs), whose ids seed the synthetic entry module — so a
>   zero-emitting module can never be "placed" and `--extra-entry` only adds an edge to
>   THAT invocation (the expect-fail lane's per-poison build), leaving the witness dark on a
>   normal build. The witness therefore hangs off a whole-path
>   `use games.sonic4.scene_equiv_proof` in `games/sonic4/test/ojz_scroll_test.emp` — the
>   game's one PLACED test-lane module, which survives Task 9. No `in <section>`, no
>   map.toml entry, no registry row, no sigil change.
> - **A SECOND, CHEAP REACHABILITY INSTRUMENT EXISTS AND NOBODY WAS USING IT:** sigil's
>   `[module.unreachable]` warning names every module outside the profile's use closure AND
>   COUNTS ITS DEAD ENSURES (`SIGIL_WARNINGS=full`). 25 fire on a sonic4 debug build (the
>   Z80 seam modules, demo constants, the 12 poisons). scene_equiv_proof is absent from the
>   list = in the closure. Necessary, not sufficient — it proves the closure, not that a
>   given ensure ran — but it is a free standing check for every future guard module.
> - **RED-FIRST ON A PLAIN `DEBUG=1 ./build.sh`, five flips, five different fixtures, all
>   correct:** OJZ_Default hdr v_center -> `cfg field 4`; Haze_Uniform BAND 0 dsa -> `band
>   field 7`; Rocking_Fast hdr v_deform_shift -> `cfg field 14`; SkyHaze BAND 1 dsa -> `band
>   field 7`; Shimmer table amplitude 8->9 -> `diverges ... at index 3`. A sixth flip
>   perturbed TWO header fields at once and reported the LOWER index (0), confirming the
>   reverse-order accumulator really yields the FIRST differing field.
> - **NO MISMATCH ANYWHERE.** All 20 headers, all 67 bands and all 6 tables passed on the
>   first green build, against an oracle transcribed independently from configs.emp. Task 6's
>   twenty scenes and the roster corrections in its findings block are confirmed value-wise.
> - **`band` COLLIDES ON IMPORT with `engine.effects.raster_dsl.band`** (a COMPTIME_HELPER,
>   glob-injected into every module), and .emp has NO `as` alias (parser `use_decl` takes a
>   path, a glob or a name list). A local definition wins over the injected glob, which is
>   why configs.emp itself was fine — only the IMPORT breaks, on both the glob and the
>   name-list spelling. configs.emp's constructor is therefore renamed `cfg_band` (44 sites,
>   byte-neutral) and both it and `hdr` are now `pub`. **Task 9 moves `hdr`/`cfg_band`, not
>   `hdr`/`band`.**
> - **Label FIELDS ARE COMPARABLE AT COMPTIME, and the comparison is SYMBOL IDENTITY, not
>   content** (measured both ways): pointing the oracle at a different SceneOut_ table
>   reports cfg field 11, and `DeformTable_Zero` vs `SceneOut_DeformTable_Zero` — same 256
>   bytes — compares UNEQUAL. So the pcfg table pointers ARE proven (which table is
>   attached), the oracle must spell the SceneOut_ names while both sets are emitted, and
>   table CONTENT needs its own array-wise proof. **Also measured: an UNKNOWN name in a
>   Label position does not error — it silently becomes a link extern and compares unequal.**
>   A typo'd table name shows up as a field-10/11/12 mismatch, never as "unknown name".
> - **A `pub data` SYMBOL IS NOT READABLE AT COMPTIME**, so the plan's table proof
>   (`first_mismatch_i8(SceneOut_DeformTable_Zero_src, deform_zero())`) has no such `_src`
>   to name. ojz_scenes.emp now splits each generator call out as
>   `pub const SceneSrc_DeformTable_*` and initialises the `pub data` from it (byte-neutral);
>   the witness compares those six against the generator calls transcribed from configs.emp.
>   Task 9 keeps the split when it drops the `SceneOut_` prefixes.
> - **THE ORACLE IS A TRANSCRIPTION and the module says so.** The CONSTRUCTORS are imported
>   (no stale copy of the packing rules), but the ARGUMENTS are hand-copied from configs.emp
>   with line citations. So this gate proves "scene model == the shipped parameters as
>   transcribed"; "as transcribed == what configs.emp holds" is Task 10's byte identity.
>   Neither gate substitutes for the other.
> - **`band_eq` TAKES TWO ARGUMENTS, not the sketched `(a, b, i)`** — the band index has no
>   work inside a field-wise compare and belongs in the failure message, where it is already
>   a literal. **Task 8's proof poison should trip `cfg_eq`/`band_eq` in this two-arg shape.**
> - Each comparison is bound to a `const` before the `ensure` so the oracle call is
>   transcribed ONCE (the message interpolates the index); a second inline copy inside the
>   message would be a second hand transcription free to drift.

### Task 8: Poisons

**Files:** Create `games/sonic4/test/poison/poison_scene_grid.emp`,
`poison_scene_capacity.emp`, `poison_scene_mask.emp`, `poison_scene_proof.emp`; modify
`tools/emp_expect_fail.py` CASES

- [x] **Step 1:** Four poison modules (syntactically valid, unreachable except via the
  expect-fail lane — the house pattern per `games/sonic4/test/poison/README.md`):
  grid = `layer(world_y: 4, …)` (trips the %8 ensure); capacity = 8 layers + anchor;
  mask = a registry fixture pair for the fold — fixture A: one scene, no deform →
  folded mask WITHOUT CAP_DEFORM; fixture B: same + dsb 2 on a shimmer table → mask WITH
  it; the poison declares B's scenes with A's mask word (trips the ⊆ ensure). This is the
  two-fixture differential form (spec §8.2) — A also exists as a PASSING fixture so the
  ensure is proven able to pass and fail on the same property;
  proof = a deliberate one-field-off oracle call (trips cfg_eq).
- [x] **Step 2:** Register 4 CASES rows in `tools/emp_expect_fail.py` with matched message
  fragments. Run the lane: all four RED for the right reason, then confirm the lane is
  green overall (expected-fail = pass).
- [x] **Step 3:** Commit poisons + CASES.

### Task 9: The swap — consumers, deletion, map.toml (ATOMIC)

**Files:** Modify `games/sonic4/data/effects/ojz_scenes.emp` (drop SceneOut_ prefixes),
`games/sonic4/data/effects/ojz_effects.emp` (use lines), `games/sonic4/data/levels/ojz/act1/act_descriptor.emp`
(use line), `games/sonic4/test/ojz_scroll_test.emp` (use lines — enumerate first),
`games/sonic4/test/scene_equiv_proof.emp` (receives hdr()/band()), `games/sonic4/map.toml`;
Delete `games/sonic4/data/parallax/` (configs.emp)

One commit — master-facing state is never half-migrated (the branch protects mid-task).

- [x] **Step 1:** Enumerate every consumer NOW (do not trust this list — regenerate):
  `grep -rn "parallax_configs\|ParallaxConfig_\|DeformTable_" games/ engine/ tools/ --include='*.emp' --include='*.toml' --include='*.py'`
  Known: act_descriptor.emp:113 (`ParallaxConfig_OJZ_Default` act fallback),
  ojz_effects.emp (preset ep_parallax bindings + `use …parallax_configs`),
  map.toml:74 ("DeformTable_Zero" in order) + :149 (budget cursor), ojz_scroll_test.emp.
  Anything NEW found → add to this task, note in report.
- [x] **Step 2:** Move `hdr()`/`band()` + the record-shape structs (ParallaxCfg1/2/4/5)
  from configs.emp into scene_equiv_proof.emp (test-only oracle now — the spec's
  "authoring entry points DELETED" is satisfied: no game data module can reach them).
- [x] **Step 3:** Rename SceneOut_* → the shipped names (ParallaxConfig_*, DeformTable_*)
  in ojz_scenes + registry emission; delete `games/sonic4/data/parallax/`; update all
  `use` lines (consumers now import from the scenes/registry module); update map.toml:
  the `parallax_configs` module entry → the scenes module, verify "DeformTable_Zero" and
  the budget `cursor = "DeformTable_Zero"` still resolve (same symbol name, new module —
  if the chainer keys on module-qualified names, update; subsequence check will fail loud).
- [x] **Step 4:** Build ALL FOUR shapes green. Run the full tool-suite test block
  (`./build.sh` runs it) + the expect-fail lane + the proof module (still red-first-proven).
- [x] **Step 5:** Commit (exact paths: the 6 modified + 1 deleted dir + map.toml).

> **TASKS 7-9 FINDINGS (2026-08-18; commits edb1ecc1, c21fb8c6, 92fafc3e). Bind Tasks 10-12:**
> - **THE SWAP IS BYTE-IDENTICAL AND MEASURED STRONGER THAN CRC.** All four shapes returned
>   to their exact pre-migration values (`ab1055d4` / `7e4dc5de` / `10aad76c` / `2ecd1031`),
>   AND the 2766-byte record block at `$121C8` is byte-equal to the pre-migration block
>   (extracted before editing, diffed after), with all 26 symbols at their original `.lst`
>   addresses.
> - **EMISSION ORDER WAS THE WHOLE GAME, and the plan had it wrong.** The shipped block
>   INTERLEAVES tables with the records that attach them (`$121C8` Zero, `$122C8` Default,
>   `$1230C` Underwater, `$12350` Calm, ...). An `.emp` section is contiguous per module, so
>   leaving the six tables in `ojz_scenes.emp` emits them as one 1536-byte run AHEAD of the
>   records, moving every table address and rewriting `pcfg_deform_table_*` inside all 20.
>   Diagnosed by measuring the Task-6 both-sets ROM: each duplicate record differed from its
>   shipped twin **in exactly bytes 18-19 (the BG table pointer) and nowhere else**. Fix: the
>   six `pub data` tables live in `scene_registry.emp`, interleaved in shipped order;
>   `ojz_scenes.emp` keeps only the `SceneSrc_*` generator consts and **emits ZERO bytes**.
>   The registry is now literally the sole emission path, as §3.2 intended.
> - **A PAIRED SIGIL EDIT IS OWED — Task 10 owns it.** sigil synthesizes its entry root as
>   one `use <module_id>` per ModuleSpec row (`crates/sigil-harness/src/native.rs`, row at
>   `:518`), so deleting `configs.emp` broke EVERY sonic4 build with `no module
>   games.sonic4.parallax_configs found under the scan root`. Held by a deliberate zero-byte
>   shim, `games/sonic4/data/effects/parallax_configs_retired.emp`, whose banner names all
>   five retirement edits (native.rs row, `pins::PARALLAX_CONFIGS`, `repin.toml` region, the
>   `parallax_configs_port` test, delete the shim). **All are renames, not re-measures — the
>   bytes did not move.** DO NOT make these on sigil master: the registry is global, and
>   removing that row would break every aeon branch that still has `configs.emp`. The paired
>   sigil branch `feature/scanline-p1-scene-model` already exists at
>   `sigil/.worktrees/scanline-p1`; **aeon and sigil merge as a pair.**
> - **`act_descriptor.emp` had NO import for `ParallaxConfig_OJZ_Default`** — it was
>   resolving as a silent link extern. Now explicit. Latent hazard, found by the swap.
> - **`ojz_effects.emp` carries TWO `use` lines for the registry** — a name list for the
>   symbol AND a whole-path line as the closure edge that `configs.emp` used to hold.
>   Without the whole-path edge the registry's subset ensure and all of `scene_dsl.emp`
>   behind it go dark.
> - **The whole-path rule is about CONSTS, not functions** (correcting the Task 4-5 block
>   above): a selective import of a CONST clones its initializer into the consumer's scope;
>   for FUNCTIONS the name list is the working form and is what the witness uses. A glob on
>   the witness would re-evaluate all 20 proof consts in the consumer's scope.
> - `ParallaxCfg1/2/4/5` were DELETED, not moved — the registry's `SceneCfgN` supersede them.
> - **Witness re-verified red-first AFTER the rewiring** (`v_center 512 -> 513` fails a plain
>   debug build at cfg field 4). `[module.unreachable]` baseline is **29** modules; the
>   witness, `ojz_scenes` and `scene_registry` are all absent from it. Lane 15/15; tool suite
>   990 passed / 2 skipped; s4lint clean; budget check 20 rows.
> - **Task 8's method is the standard to hold later tasks to:** every poison was verified
>   against a CONTROL build with the planted defect removed, which is what separates "the
>   intended guard fired" from "something failed". And the mask fixture's declared word had
>   to be a HAND-DERIVED literal — `fold_caps([A])` would make the subset test
>   `(x & ~x) == 0`, true for every input and evidence of nothing.

### Task 10 (CONTROLLER-ONLY): Image identity ×4 + repin ritual

- [ ] **Step 1:** Record pre-migration reference: master SHA before the branch
  (`git merge-base master HEAD`). Build all four shapes at THAT ref into scratch
  (worktree), record crc32s.
- [ ] **Step 2:** Build all four shapes at branch head. Placement moved (module
  restructure) → run the frozen-table repin, then
  `cargo run --release -p sigil-harness --bin refreeze -- --freeze <table> --ab <pre-migration-ref>`
  per the byte-changing ritual (rebuild BOTH sigil binaries first if sigil changed —
  it should NOT have in P1; if it did, STOP/BLOCKED). **`--check` is not evidence.**
- [ ] **Step 3:** Evidence bar (spec §8.1): the `--ab` run's emulator prose note ×
  both replay fixtures green × demo.bin/demo.debug.bin crc UNCHANGED from the
  pre-migration ref (demo links no scenes — its image must not move AT ALL; if it moved,
  a lowering leak exists — STOP/BLOCKED).
- [ ] **Step 4:** Write `docs/benchmarks/scanline-p1/GATE-EVIDENCE.md`: the four crc
  pairs, the ab prose, replay results, proof-module red-first note, poison lane output.
  Commit.

### Task 11 (CONTROLLER-ONLY): Runtime spot-verification

Belt-and-braces beyond image identity (image identity is the real gate; this catches
harness blind spots): boot the branch ROM in the emulator, verify during MOTION
(feedback_verify_during_motion): OJZ scroll test state, hold right 300+ frames across a
section boundary (Default→Caves transition), read `Parallax_Current_Scroll_B` + memory_hash
the HScroll buffer at a pinned camera state, compare against the same reads on the
pre-migration ROM (identical images ⇒ identical values — this is a harness sanity check,
expected trivially green; any diff = investigate the harness, not the ROM).

- [ ] Run it; append results to GATE-EVIDENCE.md; commit.

### Task 12: Docs sync + merge

- [ ] **Step 1:** ENGINE_ARCHITECTURE §4.6: add the scene-model authoring paragraph
  (constructors live in scene_dsl, registry is the emission path, configs are lowered
  artifacts; pointer to the spec). DEFERRED_WORK: update the per-band-deform/frequency
  entries to point at the spec's P3 (mechanism now scheduled), add the layer_mask_raw /
  v_deform_shift_raw byte-identity bridges as a hygiene note (normalize post-P1 only with
  a deliberate refreeze).
- [ ] **Step 2:** Commit docs. Merge branch → master (all four shapes green at merge
  point; verify branch first). Push if remote configured.

> **TASK 12 ADDITIONS (controller, 2026-08-18 — booked out of Task 3's reviews):**
> - [ ] **Step 3:** Book the `COMPTIME_HELPERS` move as a paired aeon+sigil follow-up
>   (DEFERRED_WORK entry). `engine.level.scene_dsl` is the only authoring DSL in its family
>   NOT in sigil's helper set (`crates/sigil-harness/src/native.rs:1942` — `parallax_dsl`,
>   `palette_dsl`, `raster_dsl` all are). Joining it deletes the glob-import requirement,
>   lets Task 3's ten `pub` accessors go private, returns the inlined literals to names, and
>   — the real argument — subjects the set to `tools/emp_helper_closure.py`, which exists
>   to prove helper names are disjoint. Nothing currently gates a hand-written glob against
>   collisions, and this injects names as generic as `layer`, `scene`, `no_layer` into game
>   modules. Staying out is the ungated option; joining is the gated one. Correctly declined
>   mid-parcel (paired change), correctly owed at the tail.
> - [ ] **Step 4:** Book the sigil language defect: **an `if` in block-tail position
>   evaluates to unit with no diagnostic**, so nested if-expressions silently yield `()`.
>   Measured twice; it mis-folded a capability mask to 0 during Task 3 and was caught only
>   by an independently-derived expected value. General trap for every `comptime fn` in the
>   tree, not a scene_dsl issue.
> - **MERGE SAFETY (blocks Step 2):** `scene_dsl.emp` must NOT reach master without a
>   module that `use`s it. Unreached, it has parse+scan coverage and **zero body-elaboration
>   coverage** (measured: undefined names inside an uncalled `pub comptime fn` build green),
>   so all of its guards and drift pins are dead. Task 6 supplies the caller and Task 7 the
>   permanent witness — if the parcel is descoped after Task 4/5, do not merge the DSL
>   alone.

---

## Self-review notes (author)

- Spec coverage: §2 layer/scene vocabulary (Tasks 2–3), §3.1 lowering + enums + guards +
  migration scope (3, 6, 9), §3.2 registry + fold + Game const + force-enable (4, 5),
  §8.1 gates incl. standing witness + 4-shape identity + --ab discipline (7, 10),
  §8.2 poisons incl. two-fixture differential (8), P1 phasing row (all). NOT in P1 by
  design: specialization consumers (P2), forcer-set derivation feeding the twins (P2/P3 —
  P1 scenes reproduce today's mode selection byte-identically), budget rows (P2).
- Two byte-identity bridges surfaced by transcription (layer_mask_raw, v_deform_shift_raw)
  are DESIGN-CONSISTENT (spec §3.1 "byte-identity preconditions") but were not in the
  spec's text — folded into DEFERRED_WORK hygiene note (Task 12); if the executor finds a
  THIRD bridge species, STOP and reconcile with the spec.
- Type consistency: layer()/scene()/scene_caps/scene_hdr/scene_band names used
  consistently across Tasks 2, 3, 5, 6, 7; SceneOut_ prefix lifecycle defined (6→9).
