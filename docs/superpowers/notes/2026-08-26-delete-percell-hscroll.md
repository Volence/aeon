# Delete the per-cell HScroll path — measurements (2026-08-26, `parcel/delete-percell-hscroll`)

Owner ruling: `d-29-corrected` (`docs/decisions.jsonl`, committed on master at `32e33ff0`).
Branch base: master `32e33ff0`. Every number below names its shape and whether it came from a
canonical `./build.sh` or a `FAST=1` build. Timings carry `uptime`.

## 1. Config-mode scan (which shipped configs would the deleted runtime key have put in per-cell)

`git show diag/showcase-invisible:tools/showcase_diag_cfgscan.py`, run from a scratch copy
(not committed), over the canonical DEBUG ROM + listing:

| image | configs | per-line | per-cell |
|---|---|---|---|
| master `32e33ff0` (`s4.debug.bin` f8d06cae) | 21 | **21** | **0** |
| branch `55ab501f` (`s4.debug.bin` 5a3069d7) | 21 | 21 | 0 |

The brief's expectation (21 / 0) holds. The 21 are the 20 `ParallaxConfig_*` hand configs
plus `EditorSceneBinding_OJZ_Act1_Sec0` (anchor, no table — the config whose fill and
register disagreed on master).

## 2. Four canonical shapes, before / after

All four ROMs `rm -f`'d before each build so existence proves freshness. Both trees built with
the same sigil release binary (`sigil` at `defeb444`).

| shape | master `32e33ff0` | branch `55ab501f` | Δ bytes (ROM file) |
|---|---|---|---|
| `s4.bin` (sonic4 release) | 699672 B, crc `654bcd74` | 699340 B, crc `d4986f79` | **−332** |
| `s4.debug.bin` (sonic4 DEBUG) | 715582 B, crc `f8d06cae` | 715252 B, crc `5a3069d7` | **−330** |
| `demo.bin` (demo release) | 96412 B, crc `bf2cdb42` | 96354 B, crc `ee735ae2` | **−58** |
| `demo.debug.bin` (demo DEBUG) | 101120 B, crc `62a0019e` | 101062 B, crc `77026d79` | **−58** |

Build wall clock (canonical, four shapes back to back): master 13:02:22 → 13:06:32; branch
13:22:50 → 13:26:49, `uptime` load 0.58 → 8.88 (the sigil test run and the gate lane were
starting alongside). Every shape's build lane was green (`rc=0`).

**What the ROM-file delta is made of.** `EndOfRom` did not move in any shape I have a master
listing for (`s4.debug` 0xa32a0, `s4` 0xa11d0, `demo.debug` 0x1121c — identical before and
after): the placer absorbs a code elision as fill between anchored sections, exactly as
`tools/demo_specialization_witness.py`'s banner says. The ROM *file* shrank because the deb2
symbol appendix lost symbols (`Parallax_Fill_PerCell`, `Static_Hscroll_Cell`, the four
`cap_per_line_*` span pairs, `.hs_cell`, `.fill_per_cell`, `.fill_done`, `.h_done`,
`.mode3_h_done`, `cap_anchors_mode`, `cap_per_line_mode`). The CODE delta is the per-proc
listing spans (head-to-next-head, `tools/scene_spans.py::lst_proc_sizes`):

| proc | s4.debug | s4 (release) | demo.debug |
|---|---|---|---|
| `Enqueue_Dirty_Buffers` | 570 → 498 (−72) | 562 → 506 (−56) | 514 → 506 (−8) |
| `Parallax_Fill_PerLine` | 686 → 690 (+4) | 686 → 690 (+4) | 2 → 100 (**+98**) |
| `Parallax_StartTransition` | 118 → 106 (−12) | 118 → 106 (−12) | 90 → 78 (−12) |
| `Parallax_Step4_Fill` | 528 → 502 (−26) | 528 → 502 (−26) | 170 → 188 (**+18**) |
| `Parallax_Update` | 258 → 246 (−12) | 258 → 246 (−12) | 258 → 246 (−12) |
| `Parallax_Fill_PerCell` | 62 → 0 (−62) | 62 → 0 (−62) | 60 → 0 (−60) |
| `BuildStaticDMA` | 166 → 142 (−24) | 166 → 142 (−24) | 166 → 142 (−24) |
| **net code** | **−204 B** | **−188 B** | **±0 B** |

(No master `demo.lst` was kept, so demo release is reported at the ROM-file level only: −58 B,
the same appendix shrink as demo DEBUG; its code delta is the same ±0 by construction — the
demo's parallax procs carry no DEBUG-shape code.)

## 3. Demo growth — the number the owner said could reverse the ruling

**The demo did not grow.** Its ROM file is 58 B *smaller* in both shapes, and its parallax
code is net **zero**: it gains the flat per-line filler (+98 B, `Parallax_Fill_PerLine`
2 → 100, with every deform / multi-table / curve span still elided under `SCANLINE_CAPS = 0`)
and the two phase accumulators plus tail call (+18 B in `Parallax_Step4_Fill`), and loses
exactly as much in the per-cell filler (−60), the cell DMA entry build (−24), the two reg
`$0B` arms (−12, −12) and the cell DMA arm (−8). Sonic4 shrinks by 204 B (DEBUG) / 188 B
(release) of code. The `fix-single-key` fallback the ruling kept open is not needed on this
count.

## 4. `bganim_room` — the d-28 figure

`python3 tools/bganim_room.py --lst <lst> --gate` (this is what `tools/test_bg_emit.py` runs
build-fatally inside every canonical build):

| tree | shape | build | `Art_Sonic` | free before `0x48000` | + section holds | room | vs 12288 ceiling | rc |
|---|---|---|---|---|---|---|---|---|
| master `32e33ff0` | sonic4 DEBUG | canonical | 0x2F090 | 4784 B | 8238 B | **13022 B** | +734 | 0 |
| master `32e33ff0` | sonic4 release | canonical | 0x2E840 | 6912 B | 8238 B | 15150 B | +2862 | 0 |
| branch `55ab501f` | sonic4 DEBUG | canonical | 0x2F090 | 4784 B | 8238 B | **13022 B** | +734 | 0 |
| branch `55ab501f` | sonic4 release | canonical | 0x2E840 | 6912 B | 8238 B | 15150 B | +2862 | 0 |
| **throwaway** branch + `parcel/showcase-effects` | sonic4 DEBUG | **FAST** | 0x2F430 | 3856 B | 8238 B | **12094 B** | **−194** | 1 |

The throwaway merge (detached, in a scratch clone; one conflict, `games/sonic4/config/game.emp`
`SCANLINE_CAPS`: `$001E` vs `$005F`, resolved to `$005E` = the showcase mask less the retired
`$0001`; not a deliverable) reports **exactly the figure d-28 was ruled on: 12094 B, −194 B.**
This parcel does not move it, and the table says why: `Art_Sonic` sits at the same LMA before
and after in every shape — the placement comes from the FROZEN tables, so the 204 B of code
this parcel deletes upstream of `Art_Sonic` shows up as placer fill, not as room. Whether a
refreeze (the controller's sigil landing step) re-derives `Art_Sonic` lower by roughly that
amount — which would put the merged tree at ~12298 B, +10 B against the ceiling — is a
question for the refreeze, and it is **not** proven here. d-28's menu stands as written; the
"shrink the ceiling by ~250 B" option is unchanged in kind, and the number it has to cover is
still 194 B until a refreeze says otherwise.

## 5. Effects gate ritual (mandatory — `engine/level/*` and `engine/system/buffers.emp` touched)

`python3 tools/effects_gates.py --rom <worktree>/s4.debug.bin --lst <worktree>/s4.debug.lst`
in the worktree, against the four `tools/scenes/*.json` repointed to the worktree's listing
(uncommitted, reverted after; the committed fixtures hardcode the main tree's path).

Run 1, at `55ab501f` (before the gate fix), 13:27:49 → 13:31:04, load 3.66 → 5.26:
**`FAIL — 2 of 27`**, exit 1. Twelve segments PASS; `boot_override` and `parallax_crossing`
FAIL with the same message shape — *"VDP reg $0B shadow reads 0b11, wanted the authored
section's 0b10 from EditorSceneBinding_OJZ_Act1_Sec0 … derives 0b010 from its deform-table
fields"*. Both gates had transcribed the deleted third mode key (`%11` iff a header table);
the config they name is the anchored, table-less one whose fill and register disagreed on
master. The red is real and it is the gate's derivation, not the engine: the register now
reads `%11` for every config, which is the ruling. Fixed in `tools/boot_override_gate.py`
and `tools/parallax_crossing_gate.py` (`mode3()` = `%11` | bit 2 per V-column table), with
the honest consequence recorded in both: reg `$0B` no longer *discriminates* between
candidate configs — the band-scroll tail is the check that does.

Re-run of the two, in-process (`--only boot_override,parallax_crossing`): **`OK — 2 gates`**,
exit 0.

Run 2, full lane after the fix, same ROM (`s4.debug.bin` 5a3069d7), 13:32:44 → 13:35:57,
load 2.89 → 2.24: **`effects_gates: OK — 27 gates`**, exit 0. All fourteen segments PASS
(scene:mid_band / suppressed / above_screen / dense 38.3-38.5 s each, cost_model 24.6 s,
the rest ≤ 5.8 s; the lane's own "27 gates" is its count — the brief's "28" was off by one
on master too, the lane reported "2 of 27" there before the fix).

**Unreachable-module check (EMP_PITFALLS §3).** `SIGIL_WARNINGS=full` FAST DEBUG sonic4 on
pristine master: 48 `module.unreachable`; on the branch: 45. The diff is exactly the four
deleted poison modules leaving (`poison_scene_curve_percell`, `poison_scene_grid`,
`poison_scene_twinkey_anchor`, `poison_scene_twinkey_table`) and the renamed
`poison_scene_own_only_table` arriving — no engine or game module changed reachability.
`import.no-names` (2) is pre-existing (`ojz_effects.emp:70`, `ojz_scroll_test.emp:75`). The
FAST DEBUG ROM is byte-identical to the canonical one (crc 5a3069d7 both).

## 6. pytest (the build's own lane, build-fatal)

| shape | master `32e33ff0` | branch `55ab501f` |
|---|---|---|
| sonic4 release | 1394 passed, 9 skipped, 49 subtests | 1392 passed, 9 skipped, 49 subtests |
| sonic4 DEBUG | 1394 passed, 9 skipped | 1392 passed, 9 skipped |
| demo release | 1395 passed, 8 skipped | 1393 passed, 8 skipped |
| demo DEBUG | 1395 passed, 8 skipped | 1393 passed, 8 skipped |

**0 failed on every shape, both trees.** The count drops by two because
`TestModeKey` (three tests) and `test_per_cell_mode_writes_only_28_entries` left
`tools/test_parallax_hscroll_probe.py` with the mode key, and two tests were added
(`test_precision_is_accepted_and_never_rendered`, the retired-bit gapless-run test). The
`emp_expect_fail` lane (part of the canonical build) is green on every shape with the
re-derived poison fragments (mask 1→0/5→4, own_caps 5→4/37→36, own_flat $0025→$0024,
own_placement 1→0, curve_deform 69→68; grid / curve_percell / twinkey_anchor deleted;
twinkey_table renamed own_only_table, same two diagnostics).

## 7. Sigil pairing — `cargo test --release --workspace --no-fail-fast` in the sigil repo (`defeb444`, `master`)

| `AEON_DIR` | passed | failed | suites failing |
|---|---|---|---|
| pristine master `32e33ff0` export (control; four FAST-built shapes, CRCs identical to the canonical ones) | **3928** | **0** | — |
| this worktree (`55ab501f`, canonical ROMs) | **3803** | **125** | 48 |

Control run: 13:28:13 → 13:30:23, load 3.48 → 6.75, cargo rc 0. Branch run: 13:24:42 → 13:26:50, load 2.16 → 8.88,
cargo rc 101. Every one of the 125 is a byte-golden / frozen-pin class test — this is the
pairing, not a defect:

- `*_region_matches_reference` / `*_regions_match_reference` / `*_undoctored_compile_equals_
  the_reference_window` for every ported module (animate, bg, bg_anim, buffers, camera,
  children, collision, collision_lookup, compression_selftest, controllers, core, dma_queue,
  dplc, entity_window, game_loop, hblank, load_art, load_object, parallax, plane_buffer,
  raster, rings, s4lz, section, sound_api, sprites, tile_cache, vblank, vectors, the
  g1-g4 / test object groups, p1/p2/p4 player groups) — the ROM windows moved;
- `native_full_sonic4_plain/debug`, `demo_*_full_file`, `demo_*_anchor_matches_golden`,
  `demo_*_game_modules_match_golden`, `*_size_table_rederives_native`, `config_a_*`,
  `config_b_*`, `lean_*`, `flipped_config_a_anchor_matches_golden` — the whole-ROM goldens;
- `pins_rs_is_current` (`repin_pins`), `two_module_ownership_flip_*`, `two_module_tail_call_
  flip_*`, `a_passing_extra_entry_moves_no_bytes`, `a_doctored_indexed_mode_changes_the_bytes`,
  `deform_pointer_equals_placed_label_vma`, `vector_table_matches_reference_rom_first_256_bytes`.

**What the sigil landing step has to touch (not done here — controller's):**
`crates/sigil-harness/src/pins.rs` and `repin.toml` name `Static_Hscroll_Cell`
(`pins::STATIC_HSCROLL_CELL`, `buffers_port.rs:135`); `buffers_port.rs` and
`parallax_port.rs` assert `parallax_mode_key` exists in `scene_dsl.emp` ("the port shim is
stale against the tree") and shim `use engine.level.scene_dsl.{CAP_PER_LINE, CAP_ANCHORS,
parallax_mode_key}`; `buffers.emp` no longer imports `scene_dsl` at all. Then the refreeze
(`--freeze NAME --ab`, with prose) re-pins every golden.

Observation for the controller, not explained here: some `*_port` length mismatches name
modules this parcel did not touch (`camera` candidate 466 vs 480 debug / 456 vs 464 plain,
`children` 924 vs 928, `bg` 308 vs 320) — the same control run passes them all against
master, so they are pairing fallout of the whole-tree relink rather than independent
defects, but the mechanism is sigil's to state.

## Deviations from the brief

1. **`d-29-corrected` is committed on master (`32e33ff0`), not only in the working tree.** The
   brief said "last entry, read it first"; the worktree was cut at `36423e69` and lacked it.
   The branch was re-based to `32e33ff0` before any edit, so the baseline is the commit that
   carries the ruling.
2. **No editor scene JSON in the tree carries `precision`.** The brief says "every existing
   scene JSON does"; `games/sonic4/data/editor/effects/ojz_act1_start.json` does not, and
   neither does the showcase branch's `ojz_act1_depth.json`. The generator still accepts and
   ignores the key (the schema can emit it), so the decision is implemented as briefed; the
   premise was wrong.
3. **The demo did not grow — it shrank** (§3). The brief expected growth "by a few hundred
   bytes"; the deleted per-cell machinery in the demo (filler, entry build, register arms,
   DMA arm) weighed exactly what the unconditional flat filler weighs.
4. **On NULL config `Enqueue_Dirty_Buffers` now enqueues nothing** rather than the 896-byte
   entry "unconditionally": a NULL config means nothing wrote `Hscroll_Buffer`, and the old
   code shipped the 112-byte cell entry there only as a "per-cell default". Shipping 896 B of
   an unwritten buffer every VBlank in a game with no parallax (the demo) would be pure DMA
   cost. The entry is unconditional on the config-present path.
5. **`scene()`'s own()-needs-a-scene-table guard and its poison survive** (renamed
   `poison_scene_own_only_table`). The brief listed the twin-key ensures for deletion; this
   one has a second, independent reason (the fill loads the header tables once, only an
   own() band reloads a5/a6, so the other bands would sample address 0), which the guard now
   states. The CURVE⇒PER_LINE and ANCHORS⇒PER_LINE pins, `scene_forces_per_line()`,
   `parallax_mode_key()` and the other three poisons are deleted as briefed.
6. **CAP_PER_LINE's bit is retired, not renumbered.** Bit 0 stays a hole (`// RETIRED:` line
   parsed by `tools/scene_spans.py`; the gapless-run test runs over declared ∪ retired) so
   every hand-derived mask keeps its meaning; sonic4's mask is `$001E`.
7. **Two gates were red and the fix was in the gates** (§5) — they transcribed the deleted
   key. Recorded red-first in the gate docstrings.
8. **`base_cycles` in the budget model is a derived sum** (3116 + 1548 = 4664), not a re-take:
   the walker's `base` and `line_mode` columns only ever appear summed now and every scene's
   axis-1 charge is unchanged to the cycle; `band_percell` is gone. The next
   `parallax_cost_probe` run fits one `base` column. `SB_WALK_BASE_X100` mirrors it.

## Open / TAGGED for the controller

- **Foreground emulator check** (not this parcel's; MCP is off-limits from here): watch
  section (1,1) of the merged tree (this branch + `parcel/showcase-effects`) scroll under
  motion — the curve should now draw. The throwaway merge builds (`FAST` DEBUG crc
  `bcbda57e`, len 715742) and its only red is the `bganim_room` ceiling, unchanged at −194.
- **Sigil pair landing**: pins/port shims above; refreeze; then re-measure `bganim_room` on the
  merged tree — the only route by which this parcel could move d-28's number.
- **Aurora + empyrean**: drop `precision` from the scene schema and `scene-ui`; then move the
  key from `effects_gen.py`'s ignored set to its refused set (booked in DEFERRED_WORK).
- **`tools/scenes/*.json` hardcode the main tree's listing path** — every worktree run of the
  lane needs the repoint; a `--lst`-driven symbol source in `ab_runner`/the lane would retire
  the ritual. Pre-existing, not this parcel's.
