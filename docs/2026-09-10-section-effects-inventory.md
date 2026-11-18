# OJZ act 1 — what each section carries, what is inconsistent, what must not move

> ⚠ CORRECTED 2026-11-17 (pre-landing review). Read against master `81efe8f4`; Scheme A already landed as `parcel/section-effects-record-fix` (`docs/DEFERRED_WORK.md` "SECTION/EFFECTS RECORD FIX"). Four statements below are wrong:
> (1) **"Reordering or renaming the preset records is safe" / "Rename Depth→Sec4: safe" — false for RENAME.** Sigil pins `OJZ_Preset_*` and `EditorSceneBinding_OJZ_Act1_*` BY NAME (`repin.toml`, generated `pins.rs` = compile error, `act_descriptor_port.rs`). Reorder is absorbed by regeneration; rename must be coordinated. "Nothing derives from order/address" does not imply "free to rename".
> (2) **Reverting section 5's Underwater loan does NOT strand `CAP_ROW_REMAP`.** `scene_registry.emp:488` folds caps over the `SCENES` registry, not section bindings; `Scene_OJZ_Underwater` stays registered, so the build stays green. The cost is only that no level section displays the remap (the DEBUG lab rows 1/37 still install it).
> (3) **Finding 8: `OJZ_GradientStream` is not unbound.** It is `OJZ_TestGradient`'s `stream:` (same file), bound to section 2. Six of the thirteen programs reach a section directly (plus one indirectly), not eight.
> (4) **Finding 1's gate mechanism:** deleting Sec0's `parallax:` zeroes rung 2 and trips the gate's "preset no longer binds ep_parallax" setup error, not the rung-coincidence check. The conclusion (do not delete it) stands.
> Also superseded since: the `[5, 6]` pin at `test_effects_seam_gate.py:783` is gone on master; sections are now regions. Line citations are to `deb52a95`. The section-5 frame checks remain open.

Research-only inventory. No code changed, nothing built, no emulator used.

**Tree read:** git worktree `/home/volence/sonic_hacks/.aeon-recon-effects`, branch
`recon/section-effects-inventory`, at **`deb52a95`**.

**Which "master" that is — resolved, because the two disagree.** The brief named master tip
`deb52a95`. In the main checkout, local `master` is `60846831` and `deb52a95` is
**`origin/master`**. `git rev-list --left-right --count master...origin/master` = `0 7`:
local master is 0 ahead, 7 behind, so it is a strict ancestor — not a divergence. I read
`deb52a95` (the briefed SHA). The 7 commits between them are the palette-writer pipeline
(`876aea44`..`89ea0df5`) and
`git diff --stat master origin/master -- games/sonic4/data/effects/ games/sonic4/data/editor/effects/`
is **empty**, so every value in this map is identical on both. `deb52a95` is also checked
out at `/home/volence/sonic_hacks/.aeon-land-palette` on branch `recon/loops-p-and-section0-order`.

**The pending edit, quarantined as instructed.** The MAIN checkout has one uncommitted edit to
`ojz_effects.emp`. I verified it firsthand with `git diff`; it is exactly what the brief said:

```
-  patch_world_ys: [PATCH_ANCHOR_NONE, 314, PATCH_ANCHOR_NONE, PATCH_ANCHOR_NONE],
-  patch_motion:   [ANCHOR_MOTION_NONE,
+  patch_world_ys: [224, 314, PATCH_ANCHOR_NONE, PATCH_ANCHOR_NONE],
+  patch_motion:   [anchor_sweep(amp_shift: 4, period_shift: 1),
```

**Everything below is committed `deb52a95` with channel 0 OFF.** The pending re-enable is
folded in nowhere. (Note also: the main checkout's working tree carries other modifications
beyond this one — `games/sonic4/data/editor/effects/ojz_act1_start.json`,
`presets/aurora_ramp_witness.json`, and the whole regenerated `data/generated/ojz/act1/` tree
are listed as modified. I did not read those; they are outside the briefed scope but you
should know the tree is not otherwise clean.)

---

## D2 — What is actually "all over"

Nine findings. Each states the argument, and each carries the sentence a reader would wrongly
conclude from the current state. Findings 1, 2 and 3 are the ones I would act on first; they
are not stylistic.

### 1. Section 0's `parallax:` binding is inert *by design* — and the comments describing it are wrong

⚠ **I revised this finding against my own first conclusion.** I initially wrote it up as dead
code that a cleanup should delete. That is wrong, and the correction matters more than the
original claim, so it leads.

`OJZ_Preset_Sec0` binds `parallax: ParallaxConfig_OJZ_Underwater` (`ojz_effects.emp:1517`).
It is never *reached* — but it must not be removed.

The resolver is three-rung, and I read the code rather than the field comment
(`engine/effects/preset.emp:228-245`):

```
pub proc Effects_ResolveParallax (a0: u32) out(a0) {
        tst.l   Sec.sec_parallax_config(a0)     // (1) the per-section binding
        beq     .no_sec_binding
        movea.l Sec.sec_parallax_config(a0), a0
        rts
```

Rung 1 wins outright and rung 2 (`ep_parallax`) is never read when rung 1 is non-zero.
`act_descriptor.emp:229` sets `sec_parallax_config: ojz_act1_sec_scene(sec: sec)`, and the
generated chooser (`effects_scenes.emp:344`) has `if sec == 0 { out = EditorSceneBinding_OJZ_Act1_Sec0 }`.
That binding is `pub data EditorSceneBinding_OJZ_Act1_Sec0: SceneCfg5 = lower5(EditorScenes_OJZ_Act1[3])`
(`effects_scenes.emp:166`) — a real emitted record, so non-zero. Section 0 therefore installs the
**editor** scene (`ojz_act1_start`: 5 bands, `v_factor: 15`, `v_center: 0`, `anchor: SceneAnchor.At(0, 15, 2)`),
not Underwater (4 bands, `v_factor: 3`, `v_center: 512`, `anchor: SceneAnchor.At(0, 15, 0)`,
`ojz_scenes.emp:248`).

The override has stood since **2026-08-25** (`62caef0e`, which added `"sceneRef": "ojz_act1_start"`
to `section_0.meta.json`); the `parallax:` line predates it (`560a47be`, 2026-08-15).

**Why it must stay — this is a D3 item hiding inside a D2 item.** `docs/DEFERRED_WORK.md:3690`
("PARALLAX CONFIG PRECEDENCE — CLOSED 2026-08-26") records that this override is intended,
measured, and gated by `tools/parallax_crossing_gate.py`, which walks the pad across the
(0,0)|(1,0) edge and asserts that crossing back into (0,0) snaps `EditorSceneBinding_OJZ_Act1_Sec0`,
"not the preset's `ParallaxConfig_OJZ_Underwater` and not the act default". And then:

> "Section (0,0) is the only section in the act where **all three rungs hold DIFFERENT
> pointers**, and that is what makes the measurement possible at all; **the gate raises a setup
> error rather than passing if content ever makes any two of them coincide.**"

So the inert-looking `parallax:` line *is* rung 2's distinct pointer. Deleting it — the obvious
tidy — would collapse rung 2 onto rung 3 and break that gate with a setup error. **Section 0's
three-rung divergence is a fixture, and it pins section 0 by IDENTITY.**

**What is genuinely wrong, then, is the prose — and it is wrong in the tree's own voice.**

- `ojz_scenes.emp:253` says Underwater is measured "in OJZ act 1 section 0 (**the only section
  that binds this config** and the only one with a live patch channel)". Both halves are false:
  section 0's binding is overridden, and section 5 also binds it (finding 2) with no rung-1
  override — making **section 5 the only section that actually installs Underwater**.
- `ojz_effects.emp:1748` states the rule correctly for section 7 ("Rung 1 beats rung 2, so a
  bound record here would be overwritten by the first `sceneRef` anyway") and in the same breath
  names section 0 as a section that *binds* Underwater — applying the rule everywhere except the
  case sitting 200 lines above it.

**The consequence nobody appears to have joined up.** `Scene_OJZ_Underwater` layer 1 is the sole
carrier of `rowRemap: SceneRemap.Ladder(RowRemapLadder_Waterline16, 101, 4)` (`ojz_scenes.emp:327`)
and the sole subject keeping `CAP_ROW_REMAP` declared (`scene_registry.emp:488`). If Underwater
installs only on section 5, **the row-remap waterline is a section-5 effect** — while its entire
layer-choice and `101` derivation is written against section 0's measured camera and anchor
("Camera_Y 144 … `Effects_Screen_L[0]` sweeping 93 -> 75"). The rowRemap landed 2026-09-03, by
which time section 0 had been overridden since 2026-08-25, so it was **never** on section 0.

I checked whether that invalidates the tuning and it may well not: section 5's anchor `2272` is
exactly `2048 + 224`, i.e. section 0's anchor translated down one section row, so at the same
in-section camera offset the screen line `L` lands at the same `80`. **I am not asserting the
derivation is broken — I am asserting it is written against the wrong section and nobody can
tell from the file.**

> **A reader would wrongly conclude** that section 0's look comes from
> `ParallaxConfig_OJZ_Underwater`, and that the row-remap waterline is a section-0 effect. Both
> are false. A reader who then *acts* on the first — deleting the inert line — silently breaks
> `parallax_crossing_gate.py`.

⚠ Static read of the binding graph, not a frame capture. **TAGGED for your foreground check:**
confirm on the running DEBUG ROM that the row remap is observable on section 5 and absent on
section 0, and that its `p` at rest on section 5 matches the `p >= 8` the derivation requires.

### 2. Section 5 wears a look it was lent, and the loan is the only thing making a mechanism visible

`OJZ_Preset_Sec5` carries `parallax: ParallaxConfig_OJZ_Underwater` with this at the binding
(`ojz_effects.emp:1669-1675`):

> "d-53, owner 2026-09-03 (\"Sure let's do it to see it?\"): the one reversible word that gives
> channel 0 a CONSUMER. […] This **LOANS section 5 a look it does not otherwise have**;
> deleting this line puts the picture back exactly."

This is a binding that exists because a mechanism needed a consumer, not because the level
wants it — exactly the category the brief asked for. It is also load-bearing by accident: per
finding 1 it is now the *only* live install of Underwater, so "deleting this line puts the
picture back exactly" is true for section 5 and false for the act, which would lose its only
row-remap surface and strand `CAP_ROW_REMAP` on the half-done-retreat arm at
`scene_registry.emp:488`.

> **A reader would wrongly conclude** that section 5 was authored to look underwater, and that
> the loan is freely reversible. It is a fixture prop, and reverting it now silently retires
> the act's only row-remap effect.

### 3. Two sections carry a waterline, built two different ways

Both are a swept channel-0 boundary with `anchor_sweep(amp_shift: 4, period_shift: 1)` — the
same motion word, to the token.

| | section 0 | section 5 |
|---|---|---|
| anchor Y | `224` (pending; `PATCH_ANCHOR_NONE` committed) | `2272` |
| motion | `anchor_sweep(4, 1)` (pending) | `anchor_sweep(4, 1)` |
| authored in | **hand-written `.emp` literal**, `ojz_effects.emp:1518-1522` | **editor JSON**, `presets/ojz_sec5_showcase.json` -> generated chooser `effects_scenes.emp:525,536` |
| program | `patched: OJZ_TwoChannel` (hand) | `raster:` via `ojz_act1_sec_raster(sec: 5)` (editor) |

`ojz_sec5_showcase.json`'s own `name` is *"OJZ act 1 section 5 - moonlit canopy void,
**waterline over BOTH planes**"*. Section 0's is the waterline you just turned off. Same visual
idea, two authoring paths, two storage locations, no cross-reference between them.

> **A reader would wrongly conclude** that the act has one waterline. It has two, they are
> authored by different mechanisms, and turning one off in `.emp` leaves the other untouched in
> JSON where an `.emp` search will not find it.

### 4. Three sections use patch channels, on three disjoint channel pairs, for a global reason

- section 0 -> channel 1 (and channel 0, pending)
- section 5 -> channel 0
- section 7 -> channels 2 and 3

Section 7's choice is explained at `act_descriptor.emp:344`: *"Channels 2 and 3 rather than 0
and 1 so the act-wide channel->band map the effects tools build stays unambiguous."* So channel
indices are being allocated **act-globally** even though `ep_patch_world_ys` is a per-preset
field and channels are per-section state. The constraint is a tooling artifact, not an engine
one.

> **A reader would wrongly conclude** that a section's channel number carries meaning (that
> "channel 2" is the water channel). It is a uniqueness token handed out to keep an external
> tool's map unambiguous, and it costs sections the ability to use the natural channel 0.

### 5. Sentinel anchors sit beside real ones with nothing marking which is which

Every patch bank is 4 wide and mostly sentinel:

- sec 0: `[NONE, 314, NONE, NONE]` / `[NONE, NONE, NONE, NONE]` — one real anchor, no motion
- sec 5: `[2272, NONE, NONE, NONE]` / `[sweep(4,1), NONE, NONE, NONE]`
- sec 7: `[NONE, NONE, SURFACE_Y, SPLIT_Y]` / `[NONE, NONE, sweep(5,0), NONE]`

Section 0's channel 1 has a real anchor (`314`) and `ANCHOR_MOTION_NONE`, and the reason is
buried 60 lines up (`ojz_effects.emp:1477-1483`): its band is lines 222..223, so a sweep there
"is invisible almost everywhere and a two-line stutter in the window, which is not motion."
Section 7's channel 3 is likewise anchored-but-still, for an unstated reason.

> **A reader would wrongly conclude** that an anchored channel with `ANCHOR_MOTION_NONE` is an
> unfinished sweep waiting to be switched on. In at least section 0 channel 1 it is a
> deliberate, derived decision that a sweep there would be wrong.

### 6. `ep_raster` is fed by two authoring mechanisms with no marker distinguishing them

Sections 1, 2, 3 carry **hand-written gate fixtures** (`OJZ_TestRaster`, `OJZ_TestGradient`,
`OJZ_ShimmerCycle`). Sections 5, 6 carry **editor-authored programs** resolved through
`ojz_act1_sec_raster`. Section 4 carries `OJZ_DepthVSplit`, which is *generated from* an editor
scene but bound by hand. All land in the same field.

The split is visible only by absence: sections 1, 2, 3 have **no `section_N.meta.json` at all**.
I checked this two ways, per the "an absence needs a second instrument" bar: `find` over
`games/sonic4/data/editor/ojz/act1/` returns exactly six meta files (0, 4, 5, 6, 7, 8) — so the
instrument does produce hits — and independently, no `if sec ==` arm in any of the seven
choosers in `effects_scenes.emp` names 1, 2 or 3. Sections 1-3 are editor-invisible.

> **A reader would wrongly conclude** that the whole act is editor-authored, or that opening the
> editor shows them every section's effects. Three of nine sections cannot be reached from the
> editor at all, and nothing in the editor says so.

### 7. The preset names imply a grouping the bindings do not honour

Section 4 binds `OJZ_Preset_Depth`. Every other bound preset is `OJZ_Preset_SecN` or
`OJZ_Preset_Plain`. Nothing named `OJZ_Preset_Sec4` exists. Meanwhile `OJZ_Preset_Sec5` and
`OJZ_Preset_Sec6` exist *only* to be per-section split points and are otherwise byte-identical
to `OJZ_Preset_Plain` (their own comments say so, `ojz_effects.emp:1592-1596`, `1686-1696`).

The generated scene array is also index-scrambled relative to section order
(`effects_scenes.emp:166-169`): Sec0 -> `[3]`, Sec4 -> `[0]`, Sec7 -> `[2]`, Sec8 -> `[1]`.

> **A reader would wrongly conclude** that `OJZ_Preset_SecN` is the naming law and that a
> section without one shares `Plain` — so that section 4 is a Plain section. It is the act's
> showcase section, under the one name that breaks the pattern.

### 8. Roughly a third of the programs in the effects file reach no section

Counting references outside `ojz_effects.emp` and checking each binding, these are defined but
bound to no section: `OJZ_TestPal`, `OJZ_WaterRaster`, `OJZ_TestVsram`, `OJZ_TestRamp`,
`OJZ_GradientStream` (0 external refs), plus `OJZ_BandDemo` and `OJZ_BaseSwap`, which are
`DEBUG == 1`-only demos emitting `[]` in release (`ojz_effects.emp:511-512`, `794-795`).

`games/sonic4/config/game.emp:111` says of one of them outright: *"`OJZ_TestRamp` constructs one
(a gate fixture that never renders)"*. And `ojz_scroll_test.emp:929`: *"The hand install of
`OJZ_WaterRaster` that used to sit here is GONE (P-b Task 6)"* — the installer was removed, the
program was not.

> **A reader would wrongly conclude** that the ~13 programs in `ojz_effects.emp` are the act's
> effects. Eight reach a section; the rest are fixtures, retired installs, or DEBUG demos, and
> nothing in the file separates the two groups.

### 9. Section 7's descriptor comment describes a tree that no longer exists

`act_descriptor.emp:346-350` states:

> "THE SCENE HALF IS UNBOUND ON PURPOSE. Section 7 has **no `section_7.meta.json`**, so
> `ojz_act1_sec_scene(sec: 7)` returns 0 and the act default stands."

`section_7.meta.json` exists and reads `"sceneRef": "ojz_act1_sec7_worldwater"`; the chooser has
`if sec == 7 { out = EditorSceneBinding_OJZ_Act1_Sec7 }` (`effects_scenes.emp:346`). The same
stale belief is load-bearing inside a test's reasoning — `ojz_scroll_test.emp:2757` justifies a
technique with "section 8 carries [`sec_parallax_config`] and section 7 does not", which is now
false. The sidecar landed `c1d0a6be`, **2026-09-05**.

**A second instance in the same file, verified.** `act_descriptor.emp:298` says of section 5:
"Identical to `OJZ_Preset_Plain` in every byte today". `OJZ_Preset_Sec5` now differs from `Plain`
in **four** fields — `raster:`, `parallax:`, `patch_world_ys[0]`, `patch_motion[0]`.

**And the same staleness has already propagated into the next refactor's design.**
`docs/superpowers/designs/2026-09-09-regions-v1-design.md:§3.1` — a table headed "What act 1
looks like today, **verified**" — carries the row `| 7 | … | ojz_act1_sec_scene(sec: 7) — returns
0, act default stands |`. It does not return 0. The design proposes a **1:1 transcription** of
that table into regions, so this row would carry the error forward into the migration.

> **A reader would wrongly conclude** that section 7 is scene-free and available for authoring,
> that section 5 is a byte-copy of Plain, and — if that reader is writing the regions migration —
> that section 7 has no scene binding to transcribe.

---

## D1 — The map

All values read from the definitions cited, at `deb52a95`. Effective parallax is computed
through `Effects_ResolveParallax`'s three rungs, not copied from the `parallax:` argument.

| Sec | Preset (`act_descriptor.emp`) | Palette | Raster / patched channel | Cycle | Variants | Effective parallax | Patch anchors `[ch0..3]` | Patch motion |
|---|---|---|---|---|---|---|---|---|
| 0 | `OJZ_Preset_Sec0` :239 | `OJZ_Palette` | `patched: OJZ_TwoChannel` (hand) — ch0 `fx_tint_band(line 100, pal_line 2, entry 4, count 3, sh 1)`, ch1 `fx_vscroll_split(line 222, offset $0043)` | `Pal_Cycle_None` | `[Variant_Water_Deep, 0]` | **editor `ojz_act1_start`** (rung 1) — 5 bands, `v_factor 15`, `anchor At(0,15,2)`. *`parallax: ParallaxConfig_OJZ_Underwater` is written but dead* | `[NONE, 314, NONE, NONE]` *(pending: ch0 -> `224`)* | all `NONE` *(pending: ch0 -> `sweep(4,1)`)* |
| 1 | `OJZ_Preset_Sec1` :255 | `OJZ_Palette` | `raster: OJZ_TestRaster` (hand fixture) | `Pal_Cycle_None` | `[Variant_Water_Deep, 0]` | act default `ParallaxConfig_OJZ_Default` | — | — |
| 2 | `OJZ_Preset_Sec2` :263 | `OJZ_Palette` | `raster: OJZ_TestGradient` (hand fixture, 96-line ramp, lines 96..191) | `Pal_Cycle_None` | `[Variant_Water_Deep, 0]` | act default | — | — |
| 3 | `OJZ_Preset_Sec3` :277 | `OJZ_Palette` | `raster: Raster_Program_None` | `ojz_act1_sec_cycle(sec: 3, hand: OJZ_ShimmerCycle)` -> **`OJZ_ShimmerCycle`** (no arm; hand wins) | `[ojz_act1_sec_variant(sec:3,slot:0,hand:Variant_Water_Deep), ojz_act1_sec_variant(sec:3,slot:1)]` -> `[Variant_Water_Deep, 0]` | act default | — | — |
| 4 | **`OJZ_Preset_Depth`** :285 | `OJZ_Palette` | `raster: OJZ_DepthVSplit` (lowered from editor scene `ojz_act1_depth`) | `Pal_Cycle_None` | `[Variant_Water_Deep, 0]` | **editor `ojz_act1_depth`** (rung 1) — 5 bands, `v_factor 15`, no anchor | — | — |
| 5 | `OJZ_Preset_Sec5` :295 | `OJZ_Palette` | `raster: ojz_act1_sec_raster(sec: 5)` -> **`EditorRaster_OJZ_Act1_ojz_sec5_showcase`** (3 `pal_region` bands, tops 32/34/36) | `Pal_Cycle_None` | `[Variant_Water_Deep, 0]` | **`ParallaxConfig_OJZ_Underwater`** via rung 2 — no rung-1 arm. *The act's only live install; carries the `rowRemap` waterline* | `[2272, NONE, NONE, NONE]` (editor) | `[sweep(4,1), NONE, NONE, NONE]` (editor) |
| 6 | `OJZ_Preset_Sec6` :305 | `OJZ_Palette` | `raster: ojz_act1_sec_raster(sec: 6)` -> **`EditorRaster_OJZ_Act1_ojz_sec6_baseswap`** — PlaneB base -> `$C000` lines 3..64, PlaneA base -> `$E000` lines 159..220 | `Pal_Cycle_None` | `[Variant_Water_Deep, 0]` | act default (no rung-1 arm, no `parallax:`) | — | — |
| 7 | `OJZ_Preset_Sec7` :334 | `OJZ_Palette` | `patched: OJZ_WorldWater` (hand) — ch2 tint band + S/H (3..160, `offscreen_ship`), ch3 vscroll split `$0043` (162..223) | `Pal_Cycle_None` | **`[Variant_OJZ_Water, 0]`** (the only section not on `Variant_Water_Deep`) | **editor `ojz_act1_sec7_worldwater`** (rung 1) — 3 bands, `v_factor 15`, `v_offset 288`, no anchor | `[NONE, NONE, OJZ_SEC7_SURFACE_Y, OJZ_SEC7_SPLIT_Y]` (= camera + 80 / +170, hand) | `[NONE, NONE, sweep(5,0), NONE]` |
| 8 | `OJZ_Preset_Plain` :355 | `OJZ_Palette` | `raster: Raster_Program_None` | `Pal_Cycle_None` | `[Variant_Water_Deep, 0]` | **editor `ojz_act1_floor`** (rung 1) — 3 bands, `v_factor 15`, `v_offset 288`, no anchor | — | — |

Chooser arms in `effects_scenes.emp`, for reference — this is the whole editor surface:
`sec_scene` {0,4,7,8}; `sec_raster` {5,6}; `sec_patched` {} (empty, `return hand`);
`sec_cycle` {} ; `sec_variant` {}; `sec_patch_world_y` {5}; `sec_patch_motion` {5}.

`OJZ_SEC7_SURFACE_Y`/`SPLIT_Y` derive from `OJZ_SEC7_CAMERA_Y = (2 << SECTION_SIZE_SHIFT) + 144`,
which `ojz_effects.emp:1780` marks **`// ASSUMED`** — an unverified constant feeding two live
anchors.

---

## D3 — What is load-bearing and must not move

**How I enumerated.** Not from the names in the brief. I swept, across the whole worktree and
all file types, (i) every preset symbol `OJZ_Preset_Sec0..Sec7`/`Plain`/`Depth`, (ii) every
program/fixture symbol those presets reference, (iii) section-index-keyed logic (`sec ==`,
`sec: N`, camera/warp coordinates), (iv) every file under any `fixtures/` directory, (v) tools
computing values from symbol *adjacency*, and (vi) every gate `tools/effects_gates.py` invokes.

**The frame check the brief asked for: my enumeration did NOT reduce to the names given.** The
brief named `effects_gates.py`, `tools/fixtures/anchor_sweep/`, sigil `*_port` tests, replay
fixtures and `boot_override_gate`. The sweep found at least nine consumers outside that set —
`test_effects_seam_gate.py`, `test_lab_index_lint.py`, `preset_lab_witness.py`,
`base_swap_witness.py`, `editor_palette_golden.py`, `band_drift_golden.py`,
`waterline_tint_coverage.py`, `sec7_waterline_probe.py`, `depth_onset_probe.py`, plus the
`.lab_index` table in `ojz_scroll_test.emp` and the scene JSONs in `tools/scenes/`. Two of the
named ones (`effects_gates.py`, `boot_override_gate.py`) turned out to be **PROPERTY**-based and
are among the *safest* things in the tree. **The brief's frame and the code's did not match.**

I verified the four highest-stakes pins firsthand; the rest of the sweep I am relaying.

### The three pins that decide what a cleanup may do

**1. `tools/test_effects_seam_gate.py:783` — the hardest identity pin in the tree.** Verified:

```python
        bound = effects_gen.load_section_raster_refs(REPO)
        self.assertEqual(sorted(bound), [5, 6],
                         f"the bound sections are {sorted(bound)}, not [5, 6]")
```

Sections 5 and 6 by literal index. **Any** move of a `rasterRef` to a different section is a
hard red. It is pytest, so it is build-fatal. Its PROPERTY twin sits immediately above it
(`:760-774`) and is deliberately separate — so the mechanism is tested property-wise and the
*content* is pinned by identity, on purpose.

**2. Section 0's three-rung divergence** (finding 1) — `parallax_crossing_gate.py` raises a setup
error if any two of section 0's three parallax rungs coincide. Pins section 0 by **IDENTITY**.

**3. Four order-sensitive gates**, three of them build-fatal. These derive a size from the *gap*
between two symbols, so **reordering definitions breaks them** even though nothing moves:

| Tool | Pins | Build-gated |
|---|---|---|
| `tools/plane_base_swap_gate.py:118` | `OJZ_BaseSwap` -> `OJZ_TestPal` adjacency | yes |
| `tools/band_drift_golden.py:72-78` | `ParallaxConfig_OJZ_Default` -> `_Underwater` -> `DeformTable_OJZ_Calm` | yes |
| `tools/reels_gate.py:150-160` | `OJZ_Reels_Fill` -> `ObjDef_Static` (crosses into `map.toml:128`) | yes |
| `tools/waterline_tint_coverage.py:84` | `OJZ_Preset_Sec7` name **and the first element** of its `variants:` | no |

This is why `OJZ_TestPal` must stay put even though finding 8 lists it as bound to nothing —
`ojz_effects.emp:1547` says so explicitly. `reels_gate.py:152-157` records that the `OJZ_Reels`
block was moved to the end of the file precisely to avoid landing between `OJZ_BaseSwap` and
`OJZ_TestPal`, "measured red the first time this file was drafted."

**Good news, and it is the load-bearing negative:** no tool derives anything from the address or
emission order of `OJZ_Preset_Sec*` **itself**. Reordering or renaming the preset records is
safe; reordering the four pairs above is not.

### Per-section pins, IDENTITY vs PROPERTY

| Sec | Pinned by | I/P | Fails how |
|---|---|---|---|
| 0 | `tools/fixtures/anchor_sweep/*.emp` (4 files, `if sec == 0 && ch == N`) | **IDENTITY** | goes **vacuous**, not red |
| 0 | `test_anchor_sweep_band.py:164` `SPAWN_SECTION = 0` | **IDENTITY** | "not evaluated" |
| 0 | `parallax_crossing_gate.py` three-rung divergence | **IDENTITY** | setup error |
| 0 | `effects_gates.py:769-798` ch0/ch1 band map | PROPERTY | exit 2 on channel collision |
| 1 | `.lab_index` row 29 `SPLT` | IDENTITY (name only) | **silent** |
| 2 | `tools/scenes/effects_raster_dense.json` `Camera_X: 4960` | **IDENTITY (coordinate)** | **silent, wrong preset** |
| 3 | `editor_palette_golden.py:76-80` `GOLDEN_TWINS` | **IDENTITY (symbol)** | build-fatal on rename |
| 4 | `ojz_effects.emp:1342,1364` ensure on `Scene_Editor_ojz_act1_depth` | IDENTITY (doc id) | build-fatal |
| 4 | `depth_onset_probe.py` (`boot_into_section4`, `config_is_sec4`) | **IDENTITY** | premise breaks |
| 5,6 | `test_effects_seam_gate.py:783` `[5, 6]` | **IDENTITY (hard)** | **hard red** |
| 5 | `sec5_band_witness.py:368` `--section` default 5 | IDENTITY (default) | default runs break |
| 6 | `base_swap_witness.py:153` `AUTHORED_SYM` | IDENTITY (doc id) | on rename |
| 7 | `waterline_tint_coverage.py:83-86` | **IDENTITY + ORDER** | dies on rename/reorder |
| 7 | `sec7_waterline_probe.py:65` `WARP_X, WARP_Y = 3000, 4400` | **IDENTITY (coordinate)** | **silent** |
| 8 | `section_8.meta.json` `sceneRef`, generated `if sec == 8` | IDENTITY (regenerated) | re-bake |

### The real hazard is the silent set, and three of them are already wrong

These do not go red — they go quiet or stay green while describing a tree that no longer exists:

- The nine `.lab_index` PRESET row **names** (`ojz_scroll_test.emp:2318-2326`) describe each
  section's effect and **nothing checks them against content**. Row 35 already reads
  `BARE // sec 7 plain, nothing bound` — section 7 binds `OJZ_Preset_Sec7` with a patched
  program, since 2026-09-05.
- `preset_lab_witness.py:30` calls section 0 "the act's only PATCHED preset" — false since
  section 7 landed.
- `test_anchor_sweep_band.py:1387` records this exact rot happening before: a diagnostic
  "asserting a content fact that had stopped being true" when you turned the waterline off.
- `tools/scenes/effects_raster_dense.json` reaches section 2 by the magic number `4960`
  (= section column 2). Nothing names "2". Move `OJZ_TestGradient` and it silently measures
  the wrong preset.

---

## D4 — Three coherent schemes

**The rule I applied:** anything that changes what is on screen is flagged, priced, and left to
you. I have decided nothing visual.

### Scheme A — Fix the record, move no bytes (pure tidying)

Correct only what is *written*. Zero pixel change, zero gate risk, no re-bake.

- The six stale statements this inventory found: `ojz_scenes.emp:253` (Underwater / "the only
  section"), `ojz_effects.emp:1748` (section 0 "binds" Underwater), `act_descriptor.emp:346-350`
  (section 7 "has no `section_7.meta.json`"), `act_descriptor.emp:298` (section 5 "identical to
  `OJZ_Preset_Plain` in every byte" — it now differs in four fields), `ojz_scroll_test.emp:2757`
  + `:2755` (sections 7/8), `preset_lab_witness.py:30,52`.
- `.lab_index` row 35 `BARE` -> the truth for section 7.
- **`docs/superpowers/designs/2026-09-09-regions-v1-design.md:§3.1`**, whose "verified" table
  says section 7's `sec_parallax_config` "returns 0, act default stands". It does not. This is
  the highest-value single correction in the whole report — see below.
- Add, at the top of `ojz_effects.emp`, the D1 table: which programs reach a section and which
  are fixtures. Finding 8 exists only because that table does not.

**Cost:** careful editing plus one canonical `./build.sh`. **Gives up:** nothing. The act still
carries fixtures in content sections.
**Regions: HELPS.** It repairs the exact fact the regions migration gets wrong *before* a 1:1
transcription bakes it in.

### Scheme B — Separate instruments from content

Give the gate fixtures an explicit home and let content sections carry only content. Sections 1,
2 and 3 exist today to host `OJZ_TestRaster`, `OJZ_TestGradient` and `OJZ_ShimmerCycle` — the
descriptor says so in as many words ("Effects P1 gate:", "Effects P2 Task 5 gate:").

**Cost, and it is not small:** `tools/scenes/effects_raster_dense.json`'s `Camera_X: 4960`
(silent), `editor_palette_golden.py`'s `GOLDEN_TWINS`, the `.lab_index` rows, and section 2's
dense-tier assertions in `effects_gates.py`. Each is enumerated above.
**⚠ OWNER CALL — this changes what is on screen** in sections 1, 2 and 3. Whether an act meant to
be played should show a synthetic S/H split and a near-monochrome ramp is a taste question I
cannot answer. (`ojz_effects.emp:1533-1536` already notes the ramp's three entries differ by one
intensity step and calls it "a subtle effect".)
**Regions: NEUTRAL now, HELPS later.** More churn to transcribe, but regions are authored
rectangles — content-only regions with fixtures held separately is the shape regions wants.

### Scheme C — One authoring mechanism per channel

Migrate the hand-written `.emp` bindings into editor documents so every section is authored one
way, killing findings 3 and 6 at the root.

**Blocked, and the blocker is booked.** `docs/DEFERRED_WORK.md:711-722`: section 0
**structurally cannot bind an editor preset document** — a document must carry `bands`, and
`preset()` makes `ep_raster`/`ep_patched` mutually exclusive. Three rules close the door
together. It needs the schema CR that item names.
It would also break `test_effects_seam_gate.py:783`'s `[5, 6]` by construction.
**Regions: HELPS strongly** — regions mode *refuses* a sidecar carrying a non-null `sceneRef`
(design §3.3), so a uniform editor path is where this is going anyway — **but it should not be
attempted before the CR lands.**

### My recommendation on sequencing, not on looks

**Do Scheme A now, before regions starts.** It is the only one that is pure tidying, it is the
one the owner's sentence actually describes ("too all over" is largely that the file *says*
things that are not true), and it fixes a wrong fact in the design document for the refactor
that lands next. Hold B behind an owner ruling on sections 1-3. Hold C behind the 9c schema CR.

### What is yours to settle, priced

| Decision | Changes screen? | Cost if yes |
|---|---|---|
| Section 0's waterline back on (the pending edit) | **yes** | already written; 2 tokens |
| Does section 5 keep the Underwater loan? | **yes** | reverting it retires the act's only row-remap surface and strands `CAP_ROW_REMAP` (`scene_registry.emp:488`) |
| Should the row-remap waterline be on section 0 or 5? | **yes** | its `101` derivation is written against section 0; the anchors differ by exactly one section row |
| Do sections 1-3 keep visible gate fixtures? | **yes** | Scheme B's full cost |
| Rename `OJZ_Preset_Depth` -> `OJZ_Preset_Sec4` | **no** | safe: nothing pins preset symbol order/address |
| Correct the stale prose | **no** | Scheme A |

---

## What I could not settle

1. **Everything here is a static read of the binding graph. I ran no ROM.** Three claims want a
   frame: that section 0 installs the 5-band editor scene; that the row remap is visible on
   section 5 and absent on section 0; and that the `101` tuning still holds at section 5's
   anchor. **TAGGED for your foreground follow-up.**
2. **`tools/test_build_fast_lanes.py:61-63`** carries a stale literal id list (missing
   `ojz_sec6_baseswap`, `ramp_probe`, `aurora_ramp_witness`). I could not determine whether that
   string is asserted against real generator output or is a fixture fed in — the surrounding code
   stubs `regenerate-level.sh`, which suggests the latter. Stating it rather than guessing.
3. **`OJZ_SEC7_CAMERA_Y`** (`ojz_effects.emp:1780`) is marked `// ASSUMED` in source and feeds
   both of section 7's live anchors. I did not verify it; it needs the same runtime check.
4. **I did not read the main checkout's other uncommitted changes** (the regenerated
   `data/generated/ojz/act1/` tree, `ojz_act1_start.json`, `aurora_ramp_witness.json`). If any of
   them touch a binding, this map is behind on those paths.
5. **Sigil `*_port` tests:** the brief named them; my sweep of this repo found no `*_port`
   consumer of a section binding. They live in the sigil repo, which I did not enter. Absence
   here is not absence there.
