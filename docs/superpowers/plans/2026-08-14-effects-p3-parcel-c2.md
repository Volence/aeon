# Effects P3 Parcel C2 — preset binding, total-binding install, data relocation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the byte-moving half of Parcel C — an `EffectsPreset` struct bound through a renamed `Sec` field, a single total-binding installer that replaces three keep-current legacy consumers, and the relocation of the game-side effects library out of the parallax file — behaviour-identical against a declared delta list.

**Architecture:** `sec_collision_s4lz` (`$34`, reserved, zero engine consumers) is RENAMED to `sec_effects`, so the binding costs zero bytes and `sizeof(Sec)` stays 66. A section names *either* a preset *or* the legacy fields, never both, enforced at comptime. `Effects_InstallPreset` writes **every** channel on install (`_None` sentinels mean "off"), which is what actually fixes "water survives exactly one crossing". Water and a world-anchored gradient share ONE generically-named patched channel, because `RasterGradientProgram`'s `rgp_arm0` sits at the same byte offset with the same formula as the water template's — making "at most one patched effect per section" structurally unrepresentable rather than merely checked.

**Tech Stack:** `.emp` (sigil-assembled 68000), sigil harness (`repin`/`refreeze`), oracle MCP + the headless `replay_runner` for gates.

---

## Facts verified against the tree on 2026-08-14 (the spec drifted; trust these)

The spec (`docs/superpowers/specs/2026-08-13-effects-p3-design.md`) was written 2026-08-13. Three of its concrete references have since moved. **These were re-measured for this plan:**

| Spec says | Actually |
|---|---|
| relocate `configs.emp:278-453` | **`configs.emp:311-705`** — see below |
| `test_support.rs:142` carries the `Sec_` rider | **`:146`** |
| `Sec` field is at `structs.emp:124` | confirmed `:124`, `sec_collision_s4lz: *u8 = 0, // $34 — reserved` |
| the five variants are at `palette.emp:824-830` | **`:776-780`** — the file is 780 lines |
| `Palette_LoadSection` reads `sec_pal` at `:265`, head at `:250-252` | proc is **`:214-241`**, reads `sec_pal` at **`:215`**, head declared at **`:201`** |
| `Raster_InstallSection` at `:544-554` | **`:753-763`**, reads `sec_raster_table` at **`:754`** |
| `Palette_InstallCycleSection` at `:374-395` | **`:324-345`**; the twin `Palette_LoadCycle` at **`:293-311`** |
| §5.4 needs a SET_REG-first `ensure` | **ALREADY IMPLEMENTED** as `check_mixed_fire` (`raster_dsl.emp:641`) — and as a stronger PREFIX test, with a recorded note that the naive `first_set == 0` spelling passed a case it should have refused. **Do not re-add it.** |
| budget model has `full_line_fire_cost` and `sparse_tier_cycles_per_frame = 8358` | **both already corrected** — renamed `full_line_fire_lines` (`:68`) and `sparse_tier_cycles_per_frame_SUPERSEDED` (`:41`). One residual remains: `:78` still cites "vs sparse 8358 (6.5%)" in prose. |

Two more facts the survey established that change task scope:

- **`Raster_Install` (`raster.emp:462`) is `raster.emp`'s SECTION HEAD**, listed in `games/sonic4/map.toml:64` **and** `games/demo/map.toml:24`. It has no `jbsr` caller — but deleting it is a map edit in **both** games, not a local deletion. `Raster_Clear` (`:470`) has zero callers and zero order entries. `Palette_LoadCycle` has zero callers.
- **`configs.emp`'s section head is `DeformTable_Zero`** (`map.toml:74`). The effects data is referenced from `OJZ_Act1_Descriptor` (`:75`), which comes after — so a new effects head placed adjacent to `DeformTable_Zero` on `:74` keeps existing relative order intact.

**The relocation range is the important correction.** `configs.emp` is 705 lines. Line 310 closes the last parallax config (`ParallaxConfig_OJZ_LockedClouds`, opened `:301`); line **311** opens the banner `// EFFECTS P1 GATE FIXTURES`. Everything from 311 to EOF is the game-side effects library. The spec's `278-453` both starts too early (it would drag `ParallaxConfig_OJZ_Caves` `:285` and `ParallaxConfig_OJZ_LockedClouds` `:301` — parallax data — into `data/effects/`) and ends far too early (it cuts the water cluster in half and abandons the gradient, vsram and ramp fixtures entirely). Those last three **shipped after the spec was written** (`cb86e130` vsram, `561ea028` ramp).

Symbols that move (`pub data` unless noted), in file order:

| line | symbol | emits |
|---|---|---|
| 327-374 | `OJZ_TEST_CRAM_ADDR`, `OJZ_TEST_PROG`, `OJZ_TEST_HAND` + 3 `ensure` | no |
| 377 | `OJZ_TestRaster` | yes |
| 388 | `comptime fn test_palette` | no |
| 394 | `OJZ_TestPal` | yes |
| 414 | `OJZ_ShimmerCycle` | yes |
| 440-505 | `OJZ_WATER_*` consts + `ensure`s | no |
| 507 | `OJZ_WaterRaster` | yes |
| 510-547 | `OJZ_GRAD_*` consts, `comptime fn grad_word` | no |
| 548 | `OJZ_GradientStream` | yes |
| 557 | `OJZ_TestGradient` | yes |
| 560-662 | `OJZ_VSRAM_*` consts + `ensure`s + `OJZ_VSRAM_VIA_PRESET` | no |
| 663 | `OJZ_TestVsram` | yes |
| 665-699 | `OJZ_RAMP_*` consts | no |
| 700 | `OJZ_TestRamp` | yes |

Also verified: `sec_collision_s4lz` has exactly **three** references tree-wide — the definition, one `sec_collision_s4lz: default,` at `act_descriptor.emp:152`, and `test_support.rs:146`. Zero engine consumers, as the spec claimed. `sizeof(Sec) == 66` is pinned at `section.emp:27`, `tile_cache.emp:31`, and `act_descriptor.emp:87`, with the literal `#66` at `section.emp:151` and `tile_cache.emp:302`. A rename trips none of them — but Task 3 verifies that rather than assuming it.

**Known stale-comment site:** `games/sonic4/data/editor/ojz/act1/export/act_descriptor.asm` (untracked, auto-commit-daemon territory) emits `dc.l 0  ; sec_collision_s4lz` nine times. It is a generated editor export and the name appears only in a trailing comment, so it cannot break the build. Regenerate it if the editor pipeline is run; do not hand-edit it.

---

## KNOWN-RED BASELINE for this parcel — read before gating any task

**Task 1 moved instruction bytes, so every whole-ROM golden test is stale from that point until Task 14 refreezes.** This is by design and must not be chased. Measured on the branch after Task 3:

```
3702 passed / 14 failed / 4 ignored, across 327 binaries
```

The 14, and ONLY these 14, are expected red:

```
config_a_anchor_matches_golden        config_b_anchor_matches_golden
config_a_full_file                    config_b_full_file
config_b_doctored_size_table_breaks_the_build
demo_debug_anchor_matches_golden      demo_plain_anchor_matches_golden
demo_debug_full_file                  demo_plain_full_file
flipped_config_a_anchor_matches_golden
lean_anchor_matches_golden            lean_full_file
native_full_sonic4_debug              native_full_sonic4_plain
```

Goldens frozen at chain 116 vs the live branch:

| shape | golden | branch (after Task 3) |
|---|---|---|
| `s4.debug.bin` | `3cffc29b` | `377407be` |
| `s4.bin` | `a6efe203` | `ba056e11` |
| `demo.bin` | `8c6abbfe` | `6c232c5d` |
| `demo.debug.bin` | `fdda99a7` | `a47dc369` |

**The per-task gate is therefore NOT "suite green".** It is:
1. all four shapes BUILD,
2. both replay-net fixtures PASS,
3. the sigil suite shows **exactly** the 14 failures above and no others.

A 15th failure, or a different name in the list, is a real regression. Count precisely — never tail the output.

**A trap this already caused:** Task 3's implementer saw the 14 reds and attributed them to unrelated dirty editor JSON in the aeon tree, because stashing its own (byte-neutral) change did not make them go away. It could not have: the cause was Task 1's COMMITTED byte change. Byte-neutral tasks cannot clear a red the goldens inherited from an earlier task in the same parcel.

---

## File structure

| File | Responsibility | Task |
|---|---|---|
| `engine/effects/palette.emp` | EFX-3 fix (2 procs); `Palette_LoadSection` pointer-taking core; the five starter variants LEAVE | 1, 6, 11 |
| `engine/structs.emp` | `sec_collision_s4lz` -> `sec_effects` | 3 |
| `engine/effects/preset.emp` | **NEW.** `EffectsPreset` struct, `preset()` constructor, `Preset_None`, `Effects_InstallPreset` | 4, 5, 8 |
| `engine/effects/raster.emp` | `Raster_InstallWater` world-Y entry point + buffer-bound `ensure`; imperative install deleted | 7, 13 |
| `engine/level/parallax.emp` | crossing routes to the preset installer; `Parallax_Init` resolves a spawn preset | 9 |
| `games/sonic4/data/effects/ojz_effects.emp` | **NEW.** Everything from `configs.emp:311-705` | 10 |
| `games/sonic4/data/effects/ojz_presets.emp` | **NEW.** The nine OJZ act-1 presets | 12 |
| `games/sonic4/data/parallax/configs.emp` | sheds 311-705, keeps the parallax library | 10 |
| `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` | nine sections converted to `effects:` | 12 |
| `games/sonic4/map.toml` | order entries for the two new sections | 10, 12 |
| `sigil/crates/sigil-harness/src/test_support.rs` | rename the rider; add the harvest cross-check (EFX-6) | 3 |
| `tools/effects_budget_model.toml` | EFX-5 + the §4.3 header claim | 2 |

---

## Task 1: EFX-3 — a count-0 cycle script must not leave cycling ACTIVE

**This is a prerequisite, not a rider.** `Pal_Cycle_None` (Task 5) is a non-NULL script with `channel_count == 0` — precisely the input that triggers this. Shipping the sentinel first would re-arm the ~19,332-cycle (15.1%-of-frame) variant derive that `ff0720ff` recovered.

**Files:**
- Modify: `engine/effects/palette.emp` — `Palette_InstallCycleSection` and `Palette_LoadCycle`

- [ ] **Step 1: Read both procs and confirm the shape**

Run: `grep -n "ori.b   #PAL_ACT_CYCLE" engine/effects/palette.emp`

Expected: two hits, one in each proc. Both currently sit BEFORE the `subq.w #1, d0` / `bmi` pair.

- [ ] **Step 2: Fix `Palette_InstallCycleSection`**

Current (the `ori.b` runs before the count is even read):

```
        move.l  d0, d1
        beq   .keep                           // empty install path (defensive)
        ori.b   #PAL_ACT_CYCLE, Pal_Active
        movea.l d0, a1
        move.w  (a1)+, d0                       // channel_count
        subq.w  #1, d0
        bmi   .keep
```

Replace with:

```
        move.l  d0, d1
        beq   .keep                           // empty install path (defensive)
        movea.l d0, a1
        move.w  (a1)+, d0                       // channel_count
        subq.w  #1, d0
        bmi   .keep                           // count 0: script recorded, cycling stays OFF
        // ARM ONLY ONCE THE COUNT IS KNOWN NON-ZERO. Arming above the test left a
        // non-NULL count-0 script with PAL_ACT_CYCLE set, and Palette_Compose's
        // `.cycling` arm then sets PAL_ACT_VARIANT_STALE every frame forever — the
        // 15.1%-of-frame full variant re-derive the ff0720ff gate fix recovered.
        // Latent until Pal_Cycle_None, which IS a non-NULL count-0 script.
        ori.b   #PAL_ACT_CYCLE, Pal_Active
```

Note the `andi.b #~PAL_ACT_CYCLE, Pal_Active` earlier in the proc already cleared the flag, so the count-0 path correctly ends with cycling off.

- [ ] **Step 3: Fix `Palette_LoadCycle` (the identical shape)**

Current:

```
        move.l  a0, d0
        beq   .done
        ori.b   #PAL_ACT_CYCLE, Pal_Active
        // reset each channel's frame timer to its period so cycling starts in phase
        movea.l a0, a1
        move.w  (a1)+, d0                       // channel_count
        subq.w  #1, d0
        bmi   .done
```

Replace with:

```
        move.l  a0, d0
        beq   .done
        // reset each channel's frame timer to its period so cycling starts in phase
        movea.l a0, a1
        move.w  (a1)+, d0                       // channel_count
        subq.w  #1, d0
        bmi   .done                           // count 0: cycling stays OFF (see InstallCycleSection)
        ori.b   #PAL_ACT_CYCLE, Pal_Active
```

- [ ] **Step 4: Add the negative probe — this guard must be seen to fail**

This codebase has a documented history of guards that were never watched to fire (`docs/BUGS.md`, the verified-vacuous-gates entries). Add a temporary count-0 script, build DEBUG, and confirm `Pal_Active` bit 1 is CLEAR after a crossing that installs it.

Add to `games/sonic4/data/parallax/configs.emp` temporarily:

```
pub data OJZ_EmptyCycleProbe: [u16; 1] = [ 0 ]      // SCRATCH — REVERT
```

Bind it as `cycle:` on OJZ section 3 in `act_descriptor.emp`, build `DEBUG=1 ./build.sh`, boot, walk into section 3, then read `Pal_Active`:

Run (oracle MCP, controlling session only — never a subagent):
`emulator_lookup_symbol name=Pal_Active` then `emulator_read_memory` 1 byte.

Expected BEFORE the fix: bit 1 (`PAL_ACT_CYCLE`, value `$02`) SET.
Expected AFTER the fix: bit 1 CLEAR.

Record both readings in the task's evidence. Then REVERT the probe data and the binding, rebuild, and confirm the CRC returns to the pre-probe value.

- [ ] **Step 5: Commit**

```bash
git add engine/effects/palette.emp
git commit -m "fix(palette): EFX-3 — arm PAL_ACT_CYCLE only after the count test

A non-NULL script with channel_count == 0 exited with cycling ACTIVE, so
Palette_Compose's .cycling arm set PAL_ACT_VARIANT_STALE every frame — the
15.1%-of-frame full variant re-derive ff0720ff recovered. Latent until
Pal_Cycle_None, which is exactly a non-NULL count-0 script. Both procs fixed;
negative-probed with a scratch count-0 script (flag observed set before, clear
after) and the probe reverted."
```

---

## Task 2: EFX-5 — the budget model's `raster_state_bytes` is wrong

**Files:**
- Modify: `tools/effects_budget_model.toml`

**RESOLVED 2026-08-14 — EFX-5 was ALREADY FIXED; the only real work was a comment.** Recorded here because "the spec named a defect" is not evidence the defect exists.

- `raster_state_bytes` already reads **288** (`:127`), and is gate-checked: `[symbols]:148` maps it to `engine/effects/raster.emp:RASTER_STATE_SIZE`, which is why it did not drift.
- `full_line_fire_cost` was already renamed `full_line_fire_lines` (`:68`).
- `sparse_tier_cycles_per_frame` is already `_SUPERSEDED` (`:41`) with the instrument bug documented at `:34-40`.

**The one change made, and a trap avoided.** An earlier draft of this plan said to replace the "vs sparse 8358" citation at `:78`. That would have been WRONG. `(41579 - 8358) / 97 = ~342 cyc/line` is a **differential**: both figures came off the same profiler on the same day under the same instrument bug, so the constant per-frame VBlank contamination CANCELS in the subtraction. The derived 342 is sound even though neither absolute is a clean tier cost. Swapping in the `:44-58` differentials would have compared two different instruments and silently corrupted it.

- [ ] **Step 1: Verify the three values above are still as described.** If any differs, re-derive before touching anything.
- [ ] **Step 2: The only edit** — a comment at `:78` stating why the superseded figure is legitimately used there as a differential baseline, so the next reader does not "fix" it.
- [ ] **Step 3: Commit**

```bash
git add tools/effects_budget_model.toml
git commit -m "docs(effects): EFX-5 was already fixed; pin why the 8358 differential is legitimate"
```

---

## Task 3: Rename `sec_collision_s4lz` -> `sec_effects` (byte-neutral)

**Files:**
- Modify: `engine/structs.emp:124`
- Modify: `games/sonic4/data/levels/ojz/act1/act_descriptor.emp:152`
- Modify: `sigil/crates/sigil-harness/src/test_support.rs:146`

- [ ] **Step 1: Confirm the field is still free**

Run: `grep -rn "sec_collision_s4lz" --include='*.emp' --include='*.rs' . /home/volence/sonic_hacks/sigil/crates | grep -v '^./docs'`

Expected: exactly three hits (definition, `act_descriptor.emp` default, `test_support.rs`). **If there are more, STOP and report** — a new consumer appeared and the binding strategy needs re-deciding.

- [ ] **Step 2: Rename in the struct**

`engine/structs.emp:124`:

```
    sec_effects:         *u8 = 0,       // $34 — EffectsPreset* (0 = use the legacy fields)
```

- [ ] **Step 3: Rename the descriptor default**

`act_descriptor.emp:152`: `sec_collision_s4lz:   default,` becomes `sec_effects:          default,`

- [ ] **Step 4: Rename the sigil rider**

`test_support.rs:146`: `("Sec_sec_collision_s4lz", "$34")` becomes `("Sec_sec_effects", "$34")`.

- [ ] **Step 5: EFX-6 — make the rider unable to go stale again**

Nothing cross-checks that blob against `harvest_engine_struct_offsets` (`native.rs:1315-1331`), so a stale name silently supplies a dead equ. Add a test asserting the two name sets agree:

```rust
#[test]
fn sec_field_equ_names_match_the_harvest() {
    let harvested = harvest_engine_struct_offsets();       // authoritative
    for (name, _) in SEC_FIELD_EQUS {
        assert!(
            harvested.contains_key(*name),
            "test_support.rs supplies `{name}`, which no longer exists in engine/structs.emp — \
             a renamed Sec/Act field leaves this blob supplying a DEAD equ that standalone port \
             oracles then resolve against nothing (EFX-6)"
        );
    }
}
```

Place it beside the blob. Wire the exact accessor names to whatever `native.rs` actually exports — if `harvest_engine_struct_offsets` is not callable from the test's scope, STOP and report rather than duplicating the harvest.

- [ ] **Step 6: Build all four shapes and prove the rename moved nothing**

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
for g in "" "DEBUG=1"; do for game in sonic4 demo; do env $g ./build.sh $game 2>&1 | grep -E "^built:"; done; done
```

Expected: **all four CRCs identical to the pre-rename build.** A field rename reaches neither the image nor the deb2 table. If any CRC moves, STOP — something is consuming the field name.

- [ ] **Step 7: Commit**

```bash
git add engine/structs.emp games/sonic4/data/levels/ojz/act1/act_descriptor.emp
git commit -m "refactor(structs): sec_collision_s4lz -> sec_effects (byte-neutral)

The $34 slot was reserved with zero engine consumers, so the preset pointer
costs no bytes and sizeof(Sec) stays 66 — which matters because 66 is pinned in
three ensures and spelled as a literal in two runtime multiplies. All four ROM
CRCs unchanged, which is the proof."
```

Commit the sigil side separately on its own branch (the two repos merge as a pair at Task 14).

---

## Task 4: The `EffectsPreset` struct and the `preset()` constructor

**Files:**
- Create: `engine/effects/preset.emp` — ONE new file, a CODE module (`module engine.effects.preset in preset`)

**Module placement, settled 2026-08-14 (do not re-decide):** modules are NOT tree-walked; sigil places them from a fixed registry. Pure-comptime helper modules must be listed in `COMPTIME_HELPERS` (`sigil .../native.rs:1767`), which is order-sensitive (a later helper silently wins a duplicate name) and gated by `tools/emp_helper_closure.py`.

We avoid that entirely. The established pattern is that **every runtime-read struct lives in the CODE module** — `pal_variant` and `PalCycleScript1` in `palette.emp:126,158`; `RasterGradientProgram` and `RasterRampProgram` in `raster.emp:279,354` — while only *constructors* live in `*_dsl`. `EffectsPreset` is read at runtime by `Effects_InstallPreset` (Task 8), so it belongs in a code module.

Put **both** the struct and `preset()` in `engine/effects/preset.emp` and have consumers import explicitly (`use engine.effects.preset.{EffectsPreset, preset}`). A comptime fn in a code module is normal (`comptime fn test_palette()` lives in `configs.emp`, which emits plenty). This needs **no sigil change and no `COMPTIME_HELPERS` entry** in this task.

**The vacuity trap this creates, and the required guard:** because `preset()` is NOT glob-injected, its free names resolve at the CALL SITE, and an unresolved name there fails SILENTLY (empty range / zero results — a recorded `.emp` hazard). **Defining `preset()` proves nothing.** Task 4 must include a real call site that exercises it, and the `ensure`s must be shown to actually evaluate — see Step 5.

**If the build rejects a `module ... in preset` section that emits no bytes yet** (it has a struct but no procs until Task 8), STOP and report rather than inventing a placeholder byte. The map's `order` array excludes zero-byte sections, so it should be accepted, but verify rather than assume.

- [ ] **Step 1: Write the struct with a size assertion**

Field order avoids an odd count of `u8` before any pointer — sigil does not auto-align.

```
// EffectsPreset — the total-binding description of one section's effects.
//
// TOTAL BINDING: every channel is written on install. `_None` sentinels mean
// "off"; 0 is illegal except ep_parallax (act default) and ep_patched (none).
// Keep-current semantics are what let water survive exactly one crossing and
// then render at a stale line forever (spec §10 defect 1) — this struct exists
// to make that unrepresentable.
pub struct EffectsPreset (size: 36) {
    ep_pal:            *u8,        // $00 — required; the preset CARRIES the palette
    ep_parallax:       *u8,        // $04 — 0 = act default (the one legal 0)
    ep_raster:         *u8,        // $08 — static program; 0 illegal, use Raster_Program_None
    ep_patched:        *u8,        // $0C — patched template (water / world-anchored gradient); 0 = none
    ep_cycle:          *u8,        // $10 — 0 illegal, use Pal_Cycle_None
    ep_variants:       [*u8; 2],   // $14 — PAL_MAX_VARIANTS; unused slots 0 = clear
    ep_patch_world_y:  u16,        // $1C — meaningful only when ep_patched != 0
    ep_transition:     u16,        // $1E — cross-fade arm; unused by every C2 fixture
}
```

`PAL_MAX_VARIANTS` is spelled as the literal `2` here because `palette.emp:323` masks with `andi.w #(PAL_MAX_VARIANTS - 1), d0` — a power-of-two mask that would silently fold slot 2 onto slot 0 at 3. Add:

```
ensure(PAL_MAX_VARIANTS == 2,
       "EffectsPreset spells ep_variants as [*u8; 2]; palette.emp's andi.w #(PAL_MAX_VARIANTS-1) mask is power-of-two only, so raising this needs that mask fixed FIRST")
```

- [ ] **Step 2: Write `preset()` with the exclusivity twin**

```
pub comptime fn preset(pal: Label, parallax: Label = 0, raster: Label = 0,
                       patched: Label = 0, cycle: Label = 0,
                       variants: [Label; 2] = [0, 0],
                       patch_world_y: int = 0, transition: int = 0) -> EffectsPreset {
    ensure(raster == 0 || patched == 0,
           "preset(): ep_raster and ep_patched are mutually exclusive. Whichever installs last wins DESTRUCTIVELY — Raster_InstallWater clears Raster_Pending (killing a staged static program), and the reverse order lets VBlank re-point Active_Buf at Buf_A while the patch keeps writing Buf_B.")
    ensure(patched != 0 || patch_world_y == 0,
           "preset(): patch_world_y is meaningful only with a patched template")
    return EffectsPreset{ ep_pal: pal, ep_parallax: parallax, ep_raster: raster,
                          ep_patched: patched, ep_cycle: cycle, ep_variants: variants,
                          ep_patch_world_y: patch_world_y, ep_transition: transition }
}
```

- [ ] **Step 3: Add the `Label != 0` comptime witness**

The exclusivity `ensure` rests on a *variant mismatch*, not a designed predicate: an unbound `Label = 0` param binds `Value::Int(0)`, and comparing a `Value::Label` to an int reaches `values_equal`'s cross-variant arm, which returns false — so `!= 0` is true. There is no precedent in the tree for this comparison. **If sigil ever diagnoses cross-class comparison, the `ensure` inverts silently to always-pass.** Pin the mechanism:

```
// WITNESS for the mechanism the exclusivity ensure above depends on. If this
// stops holding, that ensure has become vacuous rather than loud.
const _PRESET_LABEL_WITNESS_UNBOUND = 0
ensure(_PRESET_LABEL_WITNESS_UNBOUND == 0, "an unbound Label default must compare equal to 0")
ensure(Raster_Program_None != 0, "a BOUND Label must compare unequal to 0 — if this fails, preset()'s exclusivity ensure is inverted and silently always-passes")
```

- [ ] **Step 4: (§5.4 needs NOTHING — verify and move on)**

The spec asks for a SET_REG-first mixed-fire `ensure`. **It already exists** as `check_mixed_fire` (`engine/effects/raster_dsl.emp:641`, called from `raster_program` at `:686`), and it is STRONGER than the spec's ask: a prefix test (`last_set < first_cram`) rather than "a SetReg is first". Its own comment records that the naive `first_set == 0` spelling passed `[sh_on(), pal_region(..), set_reg(..)]` — the exact ordering the guard exists to forbid.

Confirm it is still wired, then move on:

Run: `grep -n "check_mixed_fire" engine/effects/raster_dsl.emp`
Expected: a definition near `:641` and a call from `raster_program`.

**Do not add a second guard.** Re-adding the spec's weaker version would regress a deliberate improvement.

- [ ] **Step 5: Build; confirm zero byte movement so far**

Nothing in this task emits. All four CRCs must still match Task 3's.

- [ ] **Step 6: Commit**

```bash
git add engine/effects/preset.emp engine/effects/raster_dsl.emp
git commit -m "feat(effects): EffectsPreset + preset() with total-binding semantics

Zero bytes: struct + comptime constructor only. Carries the Label!=0 witness
that preset()'s exclusivity ensure silently depends on, and the SET_REG-first
mixed-fire invariant (§5.4) which OJZ_WaterRaster already satisfies."
```

---

## Task 5: The `_None` sentinels

**Files:**
- Modify: `engine/effects/preset.emp` (add `Preset_None`)
- Modify: `engine/effects/palette.emp` (add `Pal_Cycle_None`)

- [ ] **Step 1: `Pal_Cycle_None`**

A non-NULL script whose channel count is 0. **Task 1 must be merged first** or this activates EFX-3.

```
// A non-NULL cycle script with zero channels — the "cycling off" sentinel that
// total binding needs. Depends on EFX-3 being fixed: before that, installing
// this left PAL_ACT_CYCLE SET and cost a full variant re-derive every frame.
pub data Pal_Cycle_None: [u16; 1] = [ 0 ]
```

- [ ] **Step 2: `Preset_None`**

```
// The preset a section names to turn effects OFF. Every channel is a sentinel
// or a legal 0 — this is what a legacy neighbour of a preset section must adopt,
// since a preset cannot be cleared by a section that does not have one.
pub data Preset_None: EffectsPreset = preset(
    pal:      OJZ_Palette,          // a preset must carry a palette; §5.2
    raster:   Raster_Program_None,
    cycle:    Pal_Cycle_None)
```

**DECIDED (controller, 2026-08-14): `Preset_None` is GAME-SIDE.** It lives in `games/sonic4/data/effects/ojz_presets.emp` (Task 12), not in `engine/`. Reason: a preset must carry a palette (§5.2) and palettes are game content, so an engine-side `Preset_None` would either hardcode a game's palette or need a comptime fn manufacturing per-game data — indirection for no gain, across a wall `CLAUDE.md` calls hard. `Pal_Cycle_None` DOES stay engine-side: it is a zero-channel script with no game content in it.

Therefore in this task create **only `Pal_Cycle_None`**. `Preset_None` is created in Task 12 beside the presets that use it.

- [ ] **Step 3: Build. Bytes MOVE here** (two new `pub data`). Expect all four CRCs to change; that is correct and this is the first task where it happens.

- [ ] **Step 4: Commit**

---

## Task 6: `Palette_LoadSection` gets a pointer-taking core

`Palette_LoadSection` (`palette.emp:214-241`) reads `Sec.sec_pal(a0)` directly at `:215`, but a preset carries its palette in `ep_pal`. Split the Sec-reading wrapper off a pointer-taking core. The snap path copies 96 bytes into `Pal_Base` (`:221-228`); the fade path copies into `Pal_Target` (`:230-238`) — the core must preserve BOTH.

**Watch the frozen table:** `Palette_LoadSection` is deliberately the section head of the `palette` region, stated in the comment at `palette.emp:201` (and reiterated at `:775`, which is why the five variants sit last in the file). Adding a proc ABOVE it moves the region boundary. Put the new core BELOW it, or re-point `repin.toml`'s `start` — and say which in the commit.

**Files:**
- Modify: `engine/effects/palette.emp`

- [ ] **Step 1: Add the core below the existing proc**

```
// Palette_LoadPal — the pointer-taking core. a0 = *palette (128 bytes), NOT a Sec*.
// Split out for the preset path, which carries its palette in ep_pal rather than
// reading Sec.sec_pal. Placed BELOW Palette_LoadSection on purpose: that proc is
// the section head of the `palette` pins region, so a proc above it would move a
// frozen boundary for no behavioural reason.
pub proc Palette_LoadPal (a0: u32) clobbers(d0-d1/a1) {
        // <body moved verbatim from Palette_LoadSection after its Sec read>
}
```

- [ ] **Step 2: Reduce `Palette_LoadSection` to the wrapper**

```
pub proc Palette_LoadSection (a0: u32) clobbers(d0-d1/a1) {
        move.l  Sec.sec_pal(a0), d0
        beq   .keep
        movea.l d0, a0
        jbra    Palette_LoadPal
    .keep:
        rts
}
```

Preserve the existing one-shot `Palette_ArmFade` consumption ordering (`palette.emp:269`, `:281`, `:300-303`) — a preset wanting a cross-fade must arm BEFORE the base load.

- [ ] **Step 3: Build; run the replay net; confirm behaviour-identical**

```bash
/home/volence/sonic_hacks/oracle-next/target/release/replay_runner --rom s4.debug.bin --lst s4.debug.lst --fixture ojz_fixture
/home/volence/sonic_hacks/oracle-next/target/release/replay_runner --rom s4.debug.bin --lst s4.debug.lst --fixture ojz_slide_fixture
```

Expected: both PASS. This is a pure refactor; a desync here means the split changed behaviour.

- [ ] **Step 4: Commit**

---

## Task 7: `Raster_InstallWater` gets a world-Y entry point (§5.3 defect 1)

`Raster_InstallWater` takes `d0 = water SCREEN line` and *derives* world Y from the camera (`raster.emp:616-621`). Feeding it an authored `ep_patch_world_y` would yield `world_y + Camera_Y` — the boundary lands wrong on install and re-anchors differently on every re-entry.

**Files:**
- Modify: `engine/effects/raster.emp`

- [ ] **Step 1: Add the world-Y entry point**

```
// Raster_InstallPatchedWorldY — install a patched template anchored to an
// authored WORLD y. a0 = template, d0 = world Y.
//
// NOT Raster_InstallWater with a different argument: that proc takes a SCREEN
// line and derives world Y from the camera, so handing it an authored world Y
// yields world_y + Camera_Y — wrong on install and differently wrong on every
// re-entry. This is the entry point the preset installer uses.
pub proc Raster_InstallPatchedWorldY (a0: u32, d0: u16) clobbers(d0-d2/a1-a2) {
        // copy template -> Raster_Buf_B  (bounded; see step 2)
        // move.w  d0, Raster_Water_World_Y
        // jbsr    Raster_PatchWaterWorldY
}
```

- [ ] **Step 2: EFX-4 — VERIFY ONLY, add nothing**

Already guarded. `engine/effects/raster_dsl.emp:708` carries
```
ensure(out.len * 2 <= 128, "raster_program: ... exceeds RASTER_BUF_SIZE (128) — Raster_VBlank and Raster_InstallWater copy a fixed 128 bytes")
```
and its comment states the split deliberately: *"the ensure below closes that entry's overflow half and the over-read half stays open"* — the over-read of a SHORT template is harmless because the walker never reaches past the terminator.

So the dangerous half (a program longer than the buffer being silently truncated live) is covered, and the benign half is a recorded decision, not an oversight. Confirm with `grep -n "RASTER_BUF_SIZE (128)" engine/effects/raster_dsl.emp` and **add no second guard** — the same mistake §5.4 would have caused with `check_mixed_fire`.

- [ ] **Step 3: Gate `Raster_PatchWaterWorldY` on a live patched channel — with NO new RAM**

It is currently called every frame from the test loop only (`games/sonic4/test/ojz_scroll_test.emp:379`). Promoting it to the engine loop needs a "is a patched channel live?" predicate, or every section without one pays the call each frame.

**Do not add a RAM flag** — a new byte moves the RAM pins and forces a repin for nothing. The predicate already exists in live state: a patched channel is live exactly when `Raster_Active_Buf` points at `Raster_Buf_B`. Both install paths set it there, and `Raster_VBlank`'s `.copy_program` re-points it at `Raster_Buf_A` whenever a static `Pending` install is consumed — which is also why patched -> static teardown needs nothing explicit. Gate on that comparison.

- [ ] **Step 4: Build + replay net. Commit.**

---

## Task 8: `Effects_InstallPreset`

**Files:**
- Modify: `engine/effects/preset.emp`

- [ ] **Step 1: Write the installer**

Order matters in exactly one place: `Palette_ArmFade` is a one-shot consumed by the base load, so `ep_transition` (if ever used) arms first.

```
// Effects_InstallPreset — a0 = Sec*. Writes EVERY channel. Called INSTEAD of the
// three legacy consumers, never in addition.
pub proc Effects_InstallPreset (a0: u32) clobbers(d0-d2/a1-a3) {
        // a1 = EffectsPreset* from Sec.sec_effects(a0); caller guarantees != 0
        //  1. ep_transition -> Palette_ArmFade   (one-shot; MUST precede the base load)
        //  2. ep_pal        -> Palette_LoadPal
        //  3. ep_cycle      -> Palette_LoadCycle  (Pal_Cycle_None = off)
        //  4. ep_variants   -> Palette_SetVariant per slot, SKIPPING slots whose
        //                      pointer already matches (see step 2)
        //  5. ep_raster     -> Raster_Pending     (Raster_Program_None = off)
        //     ep_patched    -> Raster_InstallPatchedWorldY with ep_patch_world_y
        //     (exclusive by construction — preset() ensures it)
        //  6. ep_parallax   -> config, 0 = act default
}
```

- [ ] **Step 2: The variant "already live?" guard is required, not an optimisation**

`Palette_SetVariant` sets `PAL_ACT_VARIANT_STALE` (`palette.emp:335`) on EVERY call, even when re-binding an identical pointer — forcing a ~19,332-cycle full re-derive at every crossing, including between two sections that share a preset, on the frame already under streaming pressure. Both sibling installers already guard this way (`raster.emp:547`, `palette.emp:377`); match them.

- [ ] **Step 3: `ep_raster == 0` inside a present preset means `Raster_Program_None`, not "keep"**

Inheriting `Raster_InstallSection`'s keep-current semantics would leave a previous section's water rendering forever — the mirror of the defect this parcel exists to fix. `preset()` makes 0 illegal, but the installer must not silently treat a 0 as "keep" if one ever reaches it.

- [ ] **Step 4: RE-VERIFY THE GUARDS TASK 4 SHIPPED DEAD.** Task 4 measured that a top-level `ensure` in `engine/effects/preset.emp` is NOT evaluated while nothing references the module — `ensure(PAL_MAX_VARIANTS == 99, ...)`, trivially false, built clean, while a syntax error in the same file did fail. This task is what makes the module reachable, so the guard should come alive here. Flip the `== 2` to `== 99`, confirm the build now **FAILS**, flip it back. If it still builds, the module is STILL not evaluated and that is a finding — report it rather than leaving a documented-dead guard in the tree.

- [ ] **Step 5: Build + replay net. Commit.**

---

## Task 9: Route the crossing, and resolve a preset at spawn

**Files:**
- Modify: `engine/level/parallax.emp` (`Parallax_CheckBoundary` ~`:184-190`, `Parallax_Init`)

- [ ] **Step 1: Route the crossing**

Today:

```
        jbsr    Palette_LoadSection                 // sec_pal   -> Pal_Base + recompose
        jbsr    Palette_InstallCycleSection          // sec_pal_cycle -> Pal_Cycle_Script
        jbsr    Raster_InstallSection               // sec_raster_table -> Raster_Pending
```

Becomes: if `Sec.sec_effects(a0) != 0`, call `Effects_InstallPreset` **instead of** all three.

- [ ] **Step 2: Resolve a preset at spawn too**

`Parallax_Init` picks its config before the first `CheckBoundary`, so a section-0 preset with non-default parallax would lerp in over 16 frames at spawn. Resolve the preset in init as well.

- [ ] **Step 3: RE-VERIFY THE GUARD THAT IS STILL DEAD.** Task 4 measured `engine/effects/preset.emp`'s `ensure(PAL_MAX_VARIANTS == 2, ...)` as never evaluated. Task 8 re-checked after adding the module to `map.toml`'s `order` and it was STILL dead, which established the rule:

> **`order` placement is not reachability.** It only says where a module's bytes land *if* it is lowered. A module is lowered only when something already in the target's `use` closure actually `use`s it.

Sigil says so itself — `SIGIL_WARNINGS=full` emits `[module.unreachable] module ... is outside this profile's use closure, so its N ensure guard(s) are never evaluated for this target`. **This task adds the `use` and the call site, so it is the one that makes the module reachable.** Verify:
1. Flip `== 2` to `== 99`; build; it MUST now FAIL with that ensure's message.
2. Flip back, rebuild.
3. Confirm `engine/effects/preset.emp` no longer appears in `SIGIL_WARNINGS=full ... | grep module.unreachable` for the sonic4 target.

If it is still dead after wiring, STOP and report — a guard that no target ever evaluates is worse than no guard, because it reads as protection.

(For calibration: 14 modules are unreachable in the sonic4 target and 40 in demo, but that is BY DESIGN — each evaluates in the target that uses it, and the Z80 sound modules evaluate through the seam-1/seam-2 blob path instead. `games/demo/config/constants.emp` is unreachable for sonic4 and reachable for demo, which is the shape of a healthy case. `preset.emp` is the only module currently unreachable in BOTH.)

- [ ] **Step 4: Build + replay net. Commit.**

---

## Task 10: Relocate the effects library out of `configs.emp`

**Files:**
- Create: `games/sonic4/data/effects/ojz_effects.emp`
- Modify: `games/sonic4/data/parallax/configs.emp` (sheds 311-705)
- Modify: `games/sonic4/map.toml`

- [ ] **Step 1: Move lines 311-705 verbatim**

Re-derive the range before moving — do not trust this plan's line numbers if the file has changed. The seam is the `// EFFECTS P1 GATE FIXTURES` banner; everything from it to EOF moves. **`ParallaxConfig_OJZ_Caves` and `ParallaxConfig_OJZ_LockedClouds` STAY** — they are parallax data and the spec's range wrongly included them.

- [ ] **Step 2: Carry the imports**

Comptime helper free names resolve at the CALL SITE and imported names break SILENTLY (empty range, zero results) — see `docs/` on the `.emp` helper-import rule. Every `use` the moved block depends on must be present in the new file, and the move must be proven byte-identical, not merely compiling.

- [ ] **Step 3: Add the section to `map.toml`'s `order`**

Insert the new section head next to the existing parallax entry so the derived order stays a subsequence.

- [ ] **Step 4: Prove the move emitted identical bytes**

The relocation moves data, so ROM CRCs WILL change. What must NOT change is the emitted content of the moved symbols. Compare each moved `pub data`'s bytes before and after by reading them out of both ROMs at their `.lst` addresses.

- [ ] **Step 5: Commit**

---

## Task 11: Move the five starter palette variants

**Files:**
- Modify: `engine/effects/palette.emp:776-780` (the LAST five lines of the file)
- Modify: `games/sonic4/data/effects/ojz_effects.emp`

Exactly 40 bytes (`pal_variant` is 8 bytes, defined `palette.emp:126-132`) leaving `engine/` for the game side. This is the move Parcel A deferred precisely because it shifts every downstream section.

```
776  pub data Variant_Water_Deep:  pal_variant = variant(shift_r: 1, shift_g: 1)
777  pub data Variant_Water_Murky: pal_variant = variant(shift_b: 1, bias_r: 1)
778  pub data Variant_Poison:      pal_variant = variant(shift_r: 1, shift_b: 1, bias_g: 1)
779  pub data Variant_CaveDark:    pal_variant = variant(shift_r: 1, shift_g: 1, shift_b: 1)
780  pub data Variant_Dusk:        pal_variant = variant(shift_b: 1, bias_r: 1)
```

- [ ] **Step 1: Move them; confirm no engine module references them.** If any does, STOP — the engine would then depend on game data.
- [ ] **Step 2: Note the duplicate and decide deliberately.** `Variant_Water_Murky` (777) and `Variant_Dusk` (780) are **byte-identical** (`shift_b: 1, bias_r: 1`) — two names for the same 8 bytes. Either keep both as intentional aliases (and say so in a comment) or drop one. Do NOT silently dedupe: the 8 bytes are cheap and the names may be doing documentation work.
- [ ] **Step 3: The comment at `palette.emp:774-775` explains these sit last to keep `Palette_LoadSection` the section head.** Removing them entirely is therefore safe for the head — but confirm the head is unchanged after the move.
- [ ] **Step 4: Build + replay net. Commit.**

---

## Task 12: Convert OJZ act 1's nine sections to presets

**Files:**
- Create: `games/sonic4/data/effects/ojz_presets.emp`
- Modify: `games/sonic4/data/levels/ojz/act1/act_descriptor.emp`
- Modify: `games/sonic4/map.toml`

Conversion is all-or-nothing per neighbourhood: a legacy neighbour of a preset section cannot clear the preset without becoming one itself. All nine convert.

- [ ] **Step 1: Write one preset per section**, preserving today's bindings exactly — section 0 `OJZ_TestRamp`, section 1 `OJZ_TestRaster`, section 2 `OJZ_TestPal` + `OJZ_TestGradient`, section 3 `OJZ_ShimmerCycle`, sections 4-8 plain. Sections with nothing get `Preset_None`.
- [ ] **Step 2: Replace the legacy fields with `effects:` in `ojz_sec`.** The exclusivity `ensure` fires if any section keeps both.
- [ ] **Step 3: Re-run the P1 and P2 GATE-EVIDENCE captures.** Section 1's sparse raster, section 2's palette snap + dense gradient, section 3's cycle. These must render as before.
- [ ] **Step 4: Commit**

---

## Task 13: Delete the imperative install path

**Files:**
- Modify: `engine/effects/raster.emp` (`Raster_InstallSection` `:753`), `engine/effects/palette.emp` (`Palette_InstallCycleSection` `:324`)
- Possibly: `games/sonic4/map.toml:64` **and** `games/demo/map.toml:24`

Once all sections are presets, the three keep-current consumers are dead **for sonic4** — but `demo` and any future game still use `Sec` without presets. **Do not delete anything still reachable.**

**The trap that makes this task bigger than it looks:** `Raster_Install` (`raster.emp:462`, a two-instruction proc with no `jbsr` caller anywhere) is `raster.emp`'s **section head**, named in `games/sonic4/map.toml:64` and `games/demo/map.toml:24`. Deleting it re-heads the section to `Raster_Clear` (`:470`) or `Raster_VBlank` (`:492`) and requires an order edit in BOTH map files. `Raster_Clear` itself has zero callers and zero order entries. `Palette_LoadCycle` (`:293`) has zero callers.

- [ ] **Step 1: Establish reachability per proc, across BOTH games,** before deleting anything. Report the finding as a table (proc, callers, is-a-section-head, order entries).
- [ ] **Step 2: Delete only what is provably unreachable tree-wide.** If a proc is dead only for sonic4, LEAVE IT and record why. An unreferenced proc that is a section head is not free to delete.
- [ ] **Step 3: Build all four shapes; replay net; commit.**

---

## Task 14: The ritual and the parcel gate

- [ ] **Step 1: Rebuild both sigil binaries** (a stale binary greens against the wrong compiler)
- [ ] **Step 2: `repin`**, then `refreeze --freeze effects-p3-parcel-c2 --ab <evidence path>`
- [ ] **Step 3: Full sigil suite** — `cargo test --release --no-fail-fast`, aggregate totals, never a tail. Expect ≥3715/0.
- [ ] **Step 4: Replay net** — both fixtures plus the negative control.
- [ ] **Step 5: Boot all four shapes.** Not optional: this is the gap that let the release shape ship blank for weeks.
- [ ] **Step 6: Write the declared delta list.** C's gate is behaviour-identical *against a declared delta*, so the deltas must be written BEFORE the captures, not rationalised after:
  1. **Frame-1 un-varianted water** — deleting the imperative install moves variant binding from init to update frame 1. Must not be read as a failed install in a press-frame capture.
  2. **Water becomes per-section** — this IS the fix for "water survives exactly one crossing", so the old behaviour disappearing is the point.
- [ ] **Step 7: Merge aeon + sigil AS A PAIR** and record the verified pair.

---

## Task 15: Documentation obligations

- [ ] `docs/ENGINE_ARCHITECTURE.md` §7 — **reconcile the P2 drift**, which is an explicit Parcel-C obligation, not an incidental edit: the banner (`:3343-3380`) says P2 shipped cycling/cross-fade/gradients while §7.1 (`:3392-3396`) still calls them PLANNED with "no shipped code", and §7.2 (`:3417-3419`) still attributes the sparse tier to `engine/system/hblank.emp`.
- [ ] `docs/DEFERRED_WORK.md` — the water/underwater hooks entry (cite by heading; the file has two independently numbered lists).
- [ ] `docs/BUGS.md` — record EFX-1, EFX-2, EFX-4, EFX-6; mark EFX-3 and EFX-5 fixed here.
- [ ] `configs.emp` — the stale `run_to_scanline` + `read_cram` comment on the gradient gate. `emulator_read_cram` is frame-latched and cannot see a mid-frame CRAM write, so it is invalid for `OP_CRAM`/`OP_PAL_REGION`/`OP_RUN_GRADIENT`; measure the framebuffer. It IS valid for a whole-frame `sec_pal` base palette DMA'd at VBlank.
- [ ] `repin.toml` / `native.rs` doc comments — this tree treats those as the placement rationale of record.

---

## Self-review

**Spec coverage.** §5.1 binding -> Task 3. §5.2 exclusivity + preset-carried palette -> Tasks 4, 6. §5.3 one patched channel + its three routing defects -> Tasks 4, 7, 8. §5.4 SET_REG-first -> Task 4 step 4. §5.5 field inventory -> Task 4 step 1. §5.6 install correctness -> Tasks 8, 9. §8.1 C gate -> Task 14. §10 defects: 1 -> Task 8 (total binding), 2 -> Task 15 (recorded, `ep_transition` deliberately unused), 3 -> Task 1, 4 -> Task 7 step 2, 5 -> Task 2, 6 -> Task 3 step 5. §11 docs -> Task 15.

**Gaps deliberately left, and why.** The roadmap's "one declared seam for parameters" on `ep_raster` is NOT implemented here — `ep_raster` stays a plain program reference. Parameterisation is the **P** parcel (patch generalisation), which the roadmap sequences after C and which would otherwise smuggle a second layout mover into this one.

**Placeholder scan.** Task 8 step 1 and Task 7 step 1 give proc bodies as commented step lists rather than final assembly. That is deliberate: both depend on register allocations in procs the implementer will have open, and inventing exact `movea.l`/`jbsr` sequences here would be guessing at clobber sets that `clobbers()` declarations must match. Every semantic decision they encode IS specified. Task 13 is scoped as "establish reachability, then delete only what is provably dead" rather than naming deletions, because sonic4-only deadness is not deadness.

**Type consistency.** `Palette_LoadPal` (Task 6) is the name used by `Effects_InstallPreset` (Task 8). `Raster_InstallPatchedWorldY` (Task 7) is the name used in Task 8. `Preset_None`/`Pal_Cycle_None` (Task 5) are the sentinels named in Tasks 8 and 12. `sec_effects` (Task 3) is the field read in Tasks 8 and 9.
