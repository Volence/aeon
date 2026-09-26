# Gate-predicate audit (GATE-ON-WHAT-THE-REFUSAL-PROTECTS), 2026-09-26

Parcel `parcel/gate-predicate-audit`, queue id GATE-PREDICATE-VS-PROMISE. This is a tools-only parcel,
and no ROM byte moves (the CRC table is at the end). The booking and its 13 open rows are in
`docs/DEFERRED_WORK.md`, `## GATE-ON-WHAT-THE-REFUSAL-PROTECTS`.

**The question, per gate:** what a reader takes its red and its green to MEAN (the PROMISE), what it
literally DECIDES (the PREDICATE), and whether the second entails the first. Where that was doubtful,
ONE mutation was written that breaks the promised subject without moving what the predicate reads.
It was put on disk and run through the gate, then restored from `origin/master` (`git show
origin/master:<path>`, never `git checkout --`).

## Population, and how it was enumerated

It was read off the RUNNERS, not grepped from names.

| runner | what it runs | count |
|---|---|---|
| `build.sh` canonical shapes (`s4`, `s4.debug`, `demo.debug` via `tools/landing_build.sh`) | every `gate strict` call reached with `S2CLIP` unset and `FAST=0`, plus `level_staleness.py` | **24 scripts** (`effects_seam_gate.py` twice: `--source-only` and `--lst`) |
| `tools/landing_build.sh` | `needs_build_lane.py`, `land_gate.py` | **2** |
| **landing path total** | | **26, all audited below** |
| `build.sh` with `S2CLIP` set (not on the landing path) | `clip_reachability.py`, `clip_anchors.py` | 2, not audited |
| `tools/nightly_effects_gates.sh` | `effects_gates.py` registry (18 gates), `preset_lab_witness.py`, `evict_witness.py` | 20, not audited |
| `tools/nightly_instrument_keepalive.sh` → `keepalive_lane.py` | `[wired.*]` rows of `tools/keepalive_manifest.toml` | 38, not audited except `parallax_hscroll_identity.py` (the booked candidate) |

The pytest lanes (`pytest tools -m "not needs_build"`, 3,519 cases, and the `needs_build` half) are
LANES of many assertions, not single gates. They were not audited case by case. Sigil's own
`ensure`/contract guards live in the sigil repo and are out of scope.

## Method, and the controls

- **Control first.** All 15 post-sigil gates were run standalone, with build.sh's exact arguments, on the
  baseline `s4.debug.bin`/`.lst` (origin/master `0563434a`, `landing_build.sh` `finished=0`):
  **15/15 exit 0.** The first attempt returned exit 2 on 10 gates because my runner had not exported
  `SIGIL_BUILD`, so provenance could not be checked. That was a runner defect, fixed before anything counted.
- **Pre-sigil gates:** one mutation at a time, gate run standalone, restored.
- **Post-sigil gates (b2):** 12 mutations applied together, one `DEBUG=1 NO_LINT=1 ./build.sh`
  (**rc=0**, `s4.debug.bin` fresh, crc `556b28ae` vs baseline `1ff17f52`), then every post-sigil gate
  standalone. Each mutation was then **confirmed in the ROM image** by decoding its routine in both
  images: an instruction-level diff for every code mutation, and `OJZ_ShimmerCycle` bytes
  `00 01 02 08` → `00 01 08 02` for the struct reorder. None stayed green because it was absent from
  the build. (`seam` is byte-neutral by construction, because `sceneRef` is null today. Its subject is
  the wiring, and b3 without it produced the identical crc `556b28ae`.)
  A green gate in a combined build is green on its own mutation too: the other 11 edits are in routines
  the gate does not read.
- **Unrelated-change control (b4):** one RAM-layout mutation (`ramfill`), built rc 0. **All 15
  post-sigil gates, including the 9 fixed ones, exit 0.** The new predicates do not fire on a change
  outside their subject.

## The table

`entails?`: **yes** / **no-measured** (a subject-breaking mutation stayed green) / **doubtful-unmeasured**.
In the `action` column, FIXED means red on the same mutation and green on today's tree after this
parcel; the evidence is in the Fixes section.

| gate | runner | promise (what red/green are read as) | predicate (what it decides) | entails? | mutation (on disk) → result | action |
|---|---|---|---|---|---|---|
| `level_staleness.py` | build.sh pre | "the committed generated tree was baked from the editor sources here now" | editor mtime vs generated mtime; editor sha256 vs `editor_sources.stamp.json`. Nothing reads `generated/` content | **no-measured** | section 0's previous bake (`bc166855^`) put back into `generated/`, editor and stamp untouched → **exit 0**. `verify_level_bin` refused the same tree (360 words), so the subject is held on the path | BOOKED GPP-LEVEL-STALENESS |
| `effects_seam_gate.py --source-only` | build.sh pre (also FAST) | "imports `ojz_act1_act_default` but never calls it … the act default would stop flowing through the editor seam" | substring `ojz_act1_act_default(hand:` in the RAW descriptor text, **comments included**; same for `(sec:` and the library's `(preset:` | **no-measured** | `act_descriptor.emp:229` → `act_parallax_config: ParallaxConfig_OJZ_Default,` → **exit 0** (line 100's comment satisfies the substring) | **FIXED** |
| `effects_seam_gate.py --lst` | build.sh post | "is the editor-scene binding seam actually REACHED?" | step 2 as above, plus witness equs present in the `.lst` whose values equal a recount through `effects_gen`'s own loaders | **no-measured** | same `seam` mutation, built → **exit 0** | step 2 **FIXED**; step 3 BOOKED GPP-SEAM-WITNESSES |
| `effects_budget_check.py` | build.sh pre | "Effects budget model vs the shipped code" | each toml row == a Python evaluation of a `.emp` `const` expression | yes (constant rows) | `palstage` (Stage −8 B, Ptr +8 B, span kept) → exit 0, not built. **Not counted:** RAM field layout is not this gate's promise but the concern of palette.emp:93's `ensure` | noted in GPP row 13 |
| `emp_expect_fail.py` | build.sh shared lane | "a poison module built clean or a guard's message drifted", with rows labelled as the shipped guards | each poison module fails with its fragment. Three poisons carry their OWN copy of the guard | **no-measured** | `ring_sparkle.emp:113` shipped ensure → `>= 0` → **exit 0** | BOOKED GPP-EXPECT-FAIL-RESTATES |
| `verify_level_bin.py` | build.sh pre | "the link from the strips to the bytes the engine actually decompresses" | `secN_blocks.bin` decodes to `secN_strips`. Never read which blob descriptor row N gives section N | **no-measured** | `secwire` (row 1 → `OJZ_Sec5_Blocks`/dict/len) → **exit 0** | **FIXED** |
| `fg_page_order.py check` | build.sh pre | the committed placed act never needs more than `PAGE_FRAMES` pages | page grid read from files by SECTION INDEX; windows from a Python transcription of `Tile_Cache_Fill` | **no-measured** | `secwire` → **exit 0** | wiring half closed by the `verify_level_bin` fix (same path); model half BOOKED GPP-FG-WINDOW-MODEL |
| `effects_gen.py check` | build.sh pre | generated effects module matches its inputs | regenerate-and-compare | yes | none needed | none |
| `collision_consistency.py` | build.sh pre | "checked against the bytes that actually reach the ROM" | rules over the three `.bin` files on disk; pre-sigil, so it cannot see what `AngleTable` binds | **no-measured** | `collision_data.emp:223` `AngleTable = _solidity` → **exit 0** | BOOKED GPP-COLLISION-ROM-TABLES |
| `art_rom_report.py` | build.sh pre | "the pool's ROM footprint … this report is that budget's watchdog" | sums only the embeds a `PageManifest` row names, plus a glob of local maps | **no-measured** | `ojz_act_pool.emp` + orphan `embed(sonic.bin)` → **exit 0**, identical report | BOOKED GPP-ART-ROM-UNNAMED-EMBEDS |
| `s4budget.py` | build.sh post | "a real ROM / object-bank / RAM-into-stack breach" | RAM axis: `SYSTEM_STACK − highest RAM label > 0`, so the stack is modelled as zero bytes deep | **no-measured** | `Debug_Fill_Probe: [u8; 3776]` (16 B left before `$FFFFFF00`), built rc 0 → **exit 0**, "Free: 0.0KB before stack" | BOOKED GPP-S4BUDGET-STACK-DEPTH |
| `row_remap_gate.py` | build.sh post | invariants are "what lets the pass cap the remapped run at span/2 and know every fetch lands inside the band's OWN longwords" | ladder bytes at the record's derived offset. The loop's `span/2` cap was never read | **no-measured** | `parallax.emp:4183` `lsr.w #1,d2` → `nop` → **exit 0** | **FIXED** |
| `waterline_art_gate.py` | build.sh post | arm 3 "catches … a gather with a stale stride reads plausible pixels from the wrong rows" | decoded five immediates. The per-row source stride `lsl.w #3,d1` was not one of them | **no-measured** | `bg_anim.emp:470` `lsl.w #3` → `#2` → **exit 0** | **FIXED** |
| `anim_frame_bound.py --gate` | build.sh post | "bound the animation frame BYTE against the mappings table it indexes" | paired `mappings`/`anim_table` writes by FIELD NAME inside a routine, whatever base register each went through | **no-measured** | `ring_sparkle.emp:170` `Sst.mappings(a1)` → `(a0)` → **exit 0** | **FIXED** |
| `editor_palette_golden.py` | build.sh post | "do the emitted `cycles` bytes SAY WHAT THE DOCUMENT SAID?" | decoded channels in the order the STRUCT DECLARES. `Palette_DoCycle` reads them positionally with `(a0)+` | **no-measured** | `palette.emp:151-152` swap `pc_line`/`pc_first` → **exit 0** (ROM `02 08` → `08 02`) | **FIXED** (as a pin; residual GPP-PALETTE-ORDER-IS-A-PIN) |
| `band_drift_golden.py` | build.sh post | the drift rate in each band record is the authored rate | 4 bytes at a stride/offset tied to the runtime's `band_drift_rate` by an `ensure` | yes | none needed | none |
| `plane_base_swap_gate.py` | build.sh post | "is the mid-frame nametable-base change actually in the ROM" | every program word equals words derived from sources the fixture does not author | yes | none needed (a stale "11 words" comment in build.sh ~1673 noted) | none |
| `reels_gate.py` | build.sh post | "proves OJZ_Reels_Fill itself (the code, not just its data) reaches the ROM" | for the code: `proc_gap > 0`. Never read what the code loads | **no-measured** | `ojz_effects.emp:2882` `lea OJZ_Reel_Speed(pc),a2` → `lea OJZ_TestPal(pc),a2` → **exit 0** | **FIXED** |
| `plane_role_swap_gate.py` | build.sh post | "does it write the RIGHT byte to the RIGHT register on BOTH arms?" | the four (reg, value) pairs in ADDRESS ORDER. `normal_addr` was printed, never used | **no-measured** | `parallax.emp:1778` `beq .normal` → `bne .normal` → **exit 0** | **FIXED** |
| `bganim_room.py` | build.sh post | "the ONLY ENFORCEMENT of BGANIM_SECTION_CEILINGS against a real listing" | room is measured; `live` is a formula over the override JSON (shape-blind, ~138 B over on release) | doubtful-unmeasured | none reaches the subject today (the reserve arm fires first) | BOOKED GPP-BGANIM-LIVE-FORMULA |
| `dplc_straddle.py --gate` | build.sh post | the Important-queue DPLC reserve covers the players' peak frames | `SUBJECTS[].queue = "Important"` was a typed claim, printed and never checked against the call site | **no-measured** | `characters.emp:106` `jbsr Perform_DPLC` → `Perform_DPLC_Deferrable` → **exit 0** | **FIXED** |
| `dma_defer_headroom.py --gate` | build.sh post | every pinned quantity has "a SECOND statement read out of THIS build" | constants vs listing EQUs and the static-DMA immediates. The RAM budget SEED in boot was never read | **no-measured** | `boot.emp:327` `#DMA_BUDGET_NTSC` → `#DMA_BUDGET_NTSC-512` → **exit 0** (ROM `$1800` → `$1600`) | **FIXED** |
| `sprite_tilt_gate.py --gate` | build.sh post | "the sprite's mapping frame changes with the terrain angle" | executes `Player_ApplyTilt`'s bytes against a model. Never checked that anything calls it | **no-measured** | `player_common.emp:1653` `jbsr Player_ApplyTilt` → `nop` → **exit 0** (sigil kept the proc) | **FIXED** |
| `instashield_gate.py --gate` | build.sh post | "a jump press made after walking off a ledge must NOT fire the ability" | the routine refuses every state but JUMP/ROLLJUMP. That a walk-off is not JUMP was a one-time hand enumeration | **no-measured** | `player_ground.emp:559` `moveq #PSTATE_AIR,d0` → `#PSTATE_JUMP` → **exit 0** (still 0 after this parcel, b3) | BOOKED GPP-INSTASHIELD-WALKOFF |
| `loop_crossover_gate.py --gate` | build.sh post | "a byte of CrossoverTable DECIDES a player's collision plane" | the byte decides `Sst.layer`. Never checks that the sensors read `layer` | **no-measured** | `player_sensors.emp:344` `move.b layer(a0),d3` → `nop` → **exit 0** (still 0 after this parcel, b3) | BOOKED GPP-CROSSOVER-SENSORS |
| `needs_build_lane.py` | landing_build, nightly | "every collected marked test RAN and passed" on artifacts this run wrote | JUnit: no `<skipped>`. Freshness by `artifact_provenance` on DECLARED artifacts | yes (landing config) | none needed; an undeclared-read audit is a nice-to-have | none |
| `land_gate.py` | landing_build, pre-push | "code reaches master only if a completed landing run proved that exact content green" | key = CODE-class `git ls-tree` of HEAD. "clean" = `git status`, which cannot see gitignored inputs | doubtful-unmeasured (needs a commit-and-push drill) | proposed: embed a gitignored `.bin` copy; a clone would not build | BOOKED GPP-LAND-GATE-IGNORED-INPUTS |

**Tally, landing path (26):** entails = **5** (`effects_gen`, `effects_budget_check`,
`band_drift_golden`, `plane_base_swap_gate`, `needs_build_lane`); **no-measured = 19**;
doubtful-unmeasured = **2** (`bganim_room`, `land_gate`). **20 subject-breaking mutation runs across
those 19 gates; all 20 stayed green before this parcel.** Fixed: **11**, plus `fg_page_order`'s wiring
half closed by the `verify_level_bin` fix. Booked: 13 rows (DEFERRED_WORK, `GPP-*`).

## Fixes: red first, then green on today's tree

"Counted red" for the 9 post-sigil fixes is **b3**: a real `DEBUG=1 NO_LINT=1 ./build.sh` with the 11
post-sigil mutations on disk (`seam` excluded, because the fixed `--source-only` half now refuses it
before sigil runs), graded by the fixed tools. That produced the same ROM as b2 (crc `556b28ae`), and
**build.sh itself now exits 1, stopping at `row_remap_gate: FAIL`**; in b2 the same tree built with rc
0. The 2 source-side fixes were graded by `redgreen.sh`: mutation on disk, gate, restore, gate.

| gate (commit) | red on the mutation | green on today's tree |
|---|---|---|
| `effects_seam_gate` (`--source-only` and `--lst`) | exit 1: "imports ojz_act1_act_default but never calls it with a `hand:` fallback" | exit 0 (both modes); `test_effects_seam_gate.py` 67 passed |
| `verify_level_bin` | exit 1: "row 1 names blocks=OJZ_Sec5_Blocks … section 1 must stream OJZ_Sec1_Blocks" | exit 0 (the first draft false-alarmed on the `comptime fn ojz_sec(` declaration; fixed before commit) |
| `plane_role_swap_gate` | b3 exit 1: "the instruction after `tst.b d0` is `bne.b $8020` … want `beq` to `.normal`" | exit 0 debug and release; tests 10 → 13 (inverted-branch case on the file's real captured bytes) |
| `row_remap_gate` | b3 exit 1: "does not cap the run at span/2 … found 0 `lsr.w #1, d2`" | exit 0 debug and release ("loop cap … present") |
| `waterline_art_gate` | b3 exit 1: "source row stride immediate is 4, derived 8" | exit 0 debug and release (7 immediates) |
| `reels_gate` | b3 exit 1: "loads its fallback rate table into a2 from $014F88 (OJZ_TestPal)" | exit 0 debug and release (the first draft refused a legitimate RAM-cursor `a0` load; fixed before commit) |
| `anim_frame_bound` | b3 exit 1: "SPLIT anim/mappings binding … Ani_RingSparkle written through a1, mappings only through a0" | exit 0 |
| `editor_palette_golden` | b3 exit 1: "`pal_cycle_channel` declares ['pc_first', 'pc_line', …] but Palette_DoCycle … reads … ['pc_line', 'pc_first', …]" | exit 0 |
| `dplc_straddle` | b3 exit 1 for sonic/tails/knuckles: "Player_LoadArt calls Perform_DPLC x0, Perform_DPLC_Deferrable x1" | exit 0 debug and release |
| `dma_defer_headroom` | b3 exit 3 (the tool's two-route disagreement; build.sh `strict` refuses it): "DECLARES [6144, 11648] … BUILD says [5632, 11648]" | exit 0 debug and release; `--selftest` exit 0 (the first draft bounded the extent at a local label and read nothing; fixed before commit) |
| `sprite_tilt_gate` | b3 exit 1: "Player_Display calls Player_ApplyTilt 0 time(s)" | exit 0 debug and release |

The two booked gates in b3 (`instashield_gate`, `loop_crossover_gate`) still exit 0, and the gates
with no mutation exit 0. Those are the controls showing the red rows are the fixes and not the build.

## The booked candidate: `parallax_hscroll_identity.shipped_precedent()` (keepalive, nightly)

Re-read against the promise. B3 (2026-09-19) mutated the TOOL's own offset arithmetic
(`_preset_field(...) + 2`), not the subject. The offset is already derived from the declaration
(`@ $1C` in `engine/effects/preset.emp`, which the assembler places, not a comment), and `_preset_field`
refuses when the annotation is absent. So the promise ("the loaded act still pairs a config consuming
channel 0 with a preset seeding a real anchor on it") IS entailed by the predicate on any tree where
the tool's code is unmodified. B3 measures that a check is only as good as its own code, which is true of
every gate. It is not the proxy-versus-subject shape. **Reclassified: entails, and B3 is not a gap in the
predicate.** No change was made.

## Not audited

The 58 nightly-only rows (the 18-gate `effects_gates.py` registry, `preset_lab_witness.py`,
`evict_witness.py`, and 37 of the 38 keepalive rows) and the 2 S2CLIP-only gates. The pytest lanes
were not audited case by case.

## Verification (final tip)

Filled in after the final run: see the section below.
