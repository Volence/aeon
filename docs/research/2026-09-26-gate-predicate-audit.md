# Gate-predicate audit (GATE-ON-WHAT-THE-REFUSAL-PROTECTS), 2026-09-26

Parcel `parcel/gate-predicate-audit`, queue id GATE-PREDICATE-VS-PROMISE. This is a tools-only parcel,
and no ROM byte moves (the CRC table is at the end).

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

The pytest lanes (`pytest tools -m "not needs_build"`, about 3,519 cases, and the `needs_build` half) are LANES
of many assertions, not single gates. They were not audited case by case. Sigil's own `ensure`/contract
guards live in the sigil repo and are out of scope.

## Method, and the control

- **Control first.** All 15 post-sigil gates were run standalone, with build.sh's exact arguments, on the
  baseline `s4.debug.bin`/`.lst` (origin/master `0563434a`, `landing_build.sh` `finished=0`):
  **15/15 exit 0.** The first attempt returned exit 2 on 10 gates because my runner had not exported
  `SIGIL_BUILD`, so provenance could not be checked. That was a runner defect, fixed before anything counted.
- **Pre-sigil gates (batch 1):** one mutation at a time, gate run standalone, restored.
- **Post-sigil gates (batch 2):** 12 mutations applied together, one `DEBUG=1 NO_LINT=1 ./build.sh`
  (**rc=0**, `s4.debug.bin` fresh, crc `556b28ae` vs baseline `1ff17f52`), then every post-sigil gate
  standalone. Each mutation was then **confirmed in the ROM image** by decoding its routine in both
  images: an instruction-level diff for every code mutation, and `OJZ_ShimmerCycle` bytes `00 01 02 08` →
  `00 01 08 02` for the struct reorder. None survived because it was absent from the build.
  (`seam` is byte-neutral by construction, because `sceneRef` is null today. Its subject is the wiring.)
  A green gate in a combined build is green on its own mutation too: the other 11 edits are in routines
  the gate does not read.

## The table

`entails?`: **yes** / **no-measured** (a subject-breaking mutation stayed green) / **doubtful-unmeasured**.

| gate | runner | promise (what red/green are read as) | predicate (what it decides) | entails? | mutation (on disk) → result | action |
|---|---|---|---|---|---|---|
| `level_staleness.py` | build.sh pre | "the committed generated tree was baked from the editor sources here now" | editor mtime vs generated mtime; editor sha256 vs `editor_sources.stamp.json`. Nothing reads `generated/` content | doubtful-unmeasured | (proposed: restore an older bake of `generated/`; both arms pass by construction) | BOOKED |
| `effects_seam_gate.py --source-only` | build.sh pre (also FAST) | "imports `ojz_act1_act_default` but never calls it … the act default would stop flowing through the editor seam" | substring `ojz_act1_act_default(hand:` in the RAW descriptor text, **comments included**; same for `(sec:` and the library's `(preset:` | **no-measured** | `act_descriptor.emp:229` → `act_parallax_config: ParallaxConfig_OJZ_Default,` → **exit 0** (line 100's comment satisfies the substring) | see Fixes |
| `effects_seam_gate.py --lst` | build.sh post | "is the editor-scene binding seam actually REACHED?" | witness equs present in the `.lst`; their values equal a recount through `effects_gen`'s own loaders | **no-measured** | same `seam` mutation, built → **exit 0** | step-3 half BOOKED |
| `effects_budget_check.py` | build.sh pre | "Effects budget model vs the shipped code" | each toml row == a Python evaluation of a `.emp` `const` expression | yes (constant rows) | `palstage` (Stage −8 B, Ptr +8 B, span kept) → exit 0. **Not counted as a gap:** RAM field layout is not this gate's promise; it is the `ensure` at palette.emp:93's | noted in the row booking |
| `emp_expect_fail.py` | build.sh shared lane | "a poison module built clean or a guard's message drifted", with rows labelled as the shipped guards | each poison module fails with its fragment. Three poisons carry their OWN copy of the guard | **no-measured** | `ring_sparkle.emp:113` shipped ensure → `>= 0` → **exit 0** | BOOKED (the fix is a design choice) |
| `verify_level_bin.py` | build.sh pre | "the link from the strips to the bytes the engine actually decompresses" | `secN_blocks.bin` decodes to `secN_strips`. Never reads which blob the descriptor's row N gives section N | **no-measured** | `secwire` (row 1 → `OJZ_Sec5_Blocks`/dict/len) → **exit 0** | see Fixes |
| `fg_page_order.py check` | build.sh pre | the committed placed act never needs more than `PAGE_FRAMES` pages | page grid read from files by SECTION INDEX; windows from a Python transcription of `Tile_Cache_Fill` | **no-measured** | `secwire` → **exit 0** | wiring half closed by the `verify_level_bin` fix; window-model half BOOKED |
| `effects_gen.py check` | build.sh pre | generated effects module matches its inputs | regenerate-and-compare | yes | none needed | none |
| `collision_consistency.py` | build.sh pre | "checked against the bytes that actually reach the ROM" | rules over the three `.bin` files on disk. Runs pre-sigil, so it cannot see what `AngleTable` binds | **no-measured** | `collision_data.emp:223` `AngleTable = _solidity` → **exit 0** | BOOKED (needs a post-sigil arm) |
| `art_rom_report.py` | build.sh pre | "the pool's ROM footprint … this report is that budget's watchdog" | sums only the embeds a `PageManifest` row names, plus a glob of local maps | **no-measured** | `ojz_act_pool.emp` + orphan `embed(sonic.bin)` → **exit 0** | BOOKED |
| `s4budget.py` | build.sh post | "a real ROM / object-bank / RAM-into-stack breach" | RAM axis: `SYSTEM_STACK − highest RAM label > 0`, so the stack is treated as zero bytes deep | doubtful-unmeasured | (proposed: grow `Debug_*` RAM to 16 B below the SP) | BOOKED (needs a declared stack reserve) |
| `row_remap_gate.py` | build.sh post | invariants are "what lets the pass cap the remapped run at span/2 and know every fetch lands inside the band's OWN longwords" | ladder bytes at the record's derived offset. The loop's `span/2` cap is never read | **no-measured** | `parallax.emp:4183` `lsr.w #1,d2` → `nop` → **exit 0** | see Fixes |
| `waterline_art_gate.py` | build.sh post | arm 3 "catches … a gather with a stale stride reads plausible pixels from the wrong rows" | decodes five immediates. The per-row source stride `lsl.w #3,d1` is not one of them | **no-measured** | `bg_anim.emp:470` `lsl.w #3` → `#2` → **exit 0** | see Fixes |
| `anim_frame_bound.py --gate` | build.sh post | "bound the animation frame BYTE against the mappings table it indexes" | pairs `mappings`/`anim_table` writes by FIELD NAME inside a routine, whatever base register each goes through | **no-measured** | `ring_sparkle.emp:170` `Sst.mappings(a1)` → `(a0)` → **exit 0** | see Fixes |
| `editor_palette_golden.py` | build.sh post | "do the emitted `cycles` bytes SAY WHAT THE DOCUMENT SAID?" | decodes channels in the order the STRUCT DECLARES. `Palette_DoCycle` reads them positionally with `(a0)+` | **no-measured** | `palette.emp:151-152` swap `pc_line`/`pc_first` → **exit 0** (ROM bytes `02 08` → `08 02`) | see Fixes |
| `band_drift_golden.py` | build.sh post | the drift rate in each band record is the authored rate | 4 bytes at a stride/offset tied to the runtime's `band_drift_rate` by an `ensure` | yes | none needed | none |
| `plane_base_swap_gate.py` | build.sh post | "is the mid-frame nametable-base change actually in the ROM" | every program word equals words derived from sources the fixture does not author | yes | none needed (stale "11 words" comment in build.sh noted) | none |
| `reels_gate.py` | build.sh post | "proves OJZ_Reels_Fill itself (the code, not just its data) reaches the ROM" | for the code: `proc_gap > 0`. Never reads what the code loads | **no-measured** | `ojz_effects.emp:2882` `lea OJZ_Reel_Speed(pc),a2` → `lea OJZ_TestPal(pc),a2` → **exit 0** | see Fixes |
| `plane_role_swap_gate.py` | build.sh post | "does it write the RIGHT byte to the RIGHT register on BOTH arms?" | the four (reg, value) pairs in ADDRESS ORDER. `normal_addr` is printed, never used | **no-measured** | `parallax.emp:1778` `beq .normal` → `bne .normal` → **exit 0** | see Fixes |
| `bganim_room.py` | build.sh post | "the ONLY ENFORCEMENT of BGANIM_SECTION_CEILINGS against a real listing" | room is measured; `live` is a formula over the override JSON (shape-blind, ~138 B over on release) | doubtful-unmeasured | none reaches the subject today (the reserve arm fires first) | BOOKED |
| `dplc_straddle.py --gate` | build.sh post | the Important-queue DPLC reserve covers the players' peak frames | `SUBJECTS[].queue = "Important"` is a typed claim, printed and never checked against the call site | **no-measured** | `characters.emp:106` `jbsr Perform_DPLC` → `Perform_DPLC_Deferrable` → **exit 0** | see Fixes |
| `dma_defer_headroom.py --gate` | build.sh post | every pinned quantity has "a SECOND statement read out of THIS build" | constants vs listing EQUs and the static-DMA immediates. The RAM budget SEED in boot is never read | **no-measured** | `boot.emp:327` `#DMA_BUDGET_NTSC` → `#DMA_BUDGET_NTSC-512` → **exit 0** (ROM `$1800` → `$1600`) | see Fixes |
| `sprite_tilt_gate.py --gate` | build.sh post | "the sprite's mapping frame changes with the terrain angle" | executes `Player_ApplyTilt`'s bytes against a model. Never checks that anything calls it | **no-measured** | `player_common.emp:1653` `jbsr Player_ApplyTilt` → `nop` → **exit 0** | see Fixes |
| `instashield_gate.py --gate` | build.sh post | "a jump press made after walking off a ledge must NOT fire the ability" | the routine refuses every state but JUMP/ROLLJUMP. That a walk-off is not JUMP was a one-time hand enumeration | **no-measured** | `player_ground.emp:559` `moveq #PSTATE_AIR,d0` → `#PSTATE_JUMP` → **exit 0** | BOOKED |
| `loop_crossover_gate.py --gate` | build.sh post | "a byte of CrossoverTable DECIDES a player's collision plane" | the byte decides `Sst.layer`. Never checks that the sensors read `layer` | **no-measured** | `player_sensors.emp:344` `move.b layer(a0),d3` → `nop` → **exit 0** | BOOKED |
| `needs_build_lane.py` | landing_build, nightly | "every collected marked test RAN and passed" on artifacts this run wrote | JUnit: no `<skipped>`. Freshness by `artifact_provenance` on DECLARED artifacts | yes (landing config) | none needed; an undeclared-read audit is a nice-to-have | none |
| `land_gate.py` | landing_build, pre-push | "code reaches master only if a completed landing run proved that exact content green" | key = CODE-class `git ls-tree` of HEAD. "clean" = `git status`, which cannot see gitignored inputs | doubtful-unmeasured | (proposed: embed a gitignored `.bin` copy; a clone would not build) | BOOKED |

**Tally, landing path (26):** entails = 6 (`effects_gen`, `effects_budget_check`, `band_drift_golden`,
`plane_base_swap_gate`, `needs_build_lane`, and the constant rows of the budget check, counted once).
**No-measured = 16 gate invocations** (15 scripts, with `effects_seam_gate` counted in both modes). Doubtful-unmeasured = 5
(`level_staleness`, `s4budget`, `bganim_room`, `land_gate`, and the step-3 half of the seam gate, which
is the `--lst` row above). **19 subject-breaking mutations were run; 19 SURVIVED before this parcel.**

## The booked candidate: `parallax_hscroll_identity.shipped_precedent()` (keepalive, nightly)

Re-read against the promise. B3 (2026-09-19) mutated the TOOL's own offset arithmetic
(`_preset_field(...) + 2`), not the subject. The offset is already derived from the declaration
(`@ $1C` in `engine/effects/preset.emp`, which the assembler places, not a comment), and `_preset_field`
refuses when the annotation is absent. So the promise ("the loaded act still pairs a config consuming
channel 0 with a preset seeding a real anchor on it") IS entailed by the predicate on any tree where
the tool's code is unmodified. B3 measures that a check is only as good as its own code, which is true of
every gate. It is not the proxy-versus-subject shape. **Reclassified: entails, and B3 is not a gap in the
predicate.** No change was made.
