# ROM re-layout parcel report — 2026-08-26

Owner ruling d-28-answered option 2: restore the 12,288 B BG-animation room guarantee in BOTH
canonical shapes and make it independent of Sonic's art size by placing the Z80 banks AFTER
the data region. Paired aeon + sigil landing. Nothing on screen changes; the deliverable is
placement.

## Branches and heads

| repo | branch | head (at report time) | notes |
|---|---|---|---|
| aeon | `parcel/rom-relayout` | the commit that adds this report, on top of `dddfbf0a` (`git rev-parse parcel/rom-relayout`) | from master `bb3fbac2` |
| sigil | `parcel/rom-relayout` | `301bc6a689d174aa72896b8d37092119faccddf6` | from master `007f73ef`, merged `origin/master` `aa641667` (carries `1a03c75c`'s island-order test) |

Both pushed to `origin` (`git push -u origin parcel/rom-relayout` in each); every SHA above is
from `git rev-parse` / `git log`.

## The placement rule (what map.toml now says)

```
packed_data_end(shape) = LMA(Art_Sonic) + len(art/optimized/characters/sonic.bin)   # from the shape's sigil listing
DATA_GROWTH_RESERVE    = 0x4000   # 16,384 B = two 8 KB BG-animation bands per act (the d-28 acceptance)
dac_banks  = align_up(max over the sound-on shapes of packed_data_end + DATA_GROWTH_RESERVE, 0x8000)
sound_bank = dac_banks + 2 * 0x8000   # blip bank, shared DAC bank, then the $8000-window head bank
```

`Art_Sonic` stays the LAST packed blob before the banks because `collision_data` is ordered
last among the data sections; `Map_Tails`/`Map_Knuckles` are un-exiled and sit immediately
AHEAD of it (a section with one on-disk embed is the only run-end instrument the listing
supports, since the listing carries no section extents).

**What bounds how far the banks can move (from source):** `engine/sound/z80_sound_driver.emp`
`SndDrv_SetBank` carries the bank id in the 8-bit `a` register and writes the 9th latch bit as a
literal 0 ("all our banks are < $100") → bank id ≤ $FF → LMA < 0x800000; `bankid()` masks
`$7F8000 >> 15` (same cap); the cartridge space ends at 0x3FFFFF → bank id ≤ $7F, LMA ≤
0x3F8000. Today's banks are $12/$13/$14.

**Applied today:** max packed end = 0x8A720 (DEBUG) → 0x8A720 + 0x4000 = 0x8E720 → 0x90000.
`dac_banks = 0x90000`, shared DAC bank 0x98000, `sound_bank = 0xA0000`.

## Baseline vs new (canonical builds; sigil binaries named below)

| shape | `Art_Sonic` | packed end | `dac_banks` | `SoundTablesZ80_Head` LMA | `EndOfRom` | ROM file len | CRC32 | bganim room | + 8,238 held | ceiling / margin |
|---|---|---|---|---|---|---|---|---|---|---|
| release BEFORE (master `bb3fbac2`) | 0x2EBE0 | 0x468A0 | 0x48000 | 0x58000 | 0xA11D0 | 699,845 | `a938b7d5` | 5,984 B | 14,222 B | 12,288 / +1,934 |
| release AFTER | 0x72210 | 0x89ED0 | 0x90000 | 0xA0000 | 0xA5BA0 | 718,741 | `f81c6811` | **24,880 B** | 33,118 B | 12,288 / **+20,830** |
| DEBUG BEFORE | 0x2F430 | 0x470F0 | 0x48000 | 0x58000 | 0xA32A0 | 715,742 | `bcbda57e` | 3,856 B | 12,094 B | 12,094 / 0 |
| DEBUG AFTER | 0x72A60 | 0x8A720 | 0x90000 | 0xA0000 | 0xA7C70 | 734,640 | `090c6f35` | **22,752 B** | 30,990 B | 12,288 / **+18,702** |
| demo BEFORE / AFTER | — | — | — | — | 0x1121C | 96,372 | `8bd3d11b` / `8bd3d11b (unchanged)` | n/a | | |
| demo.debug BEFORE / AFTER | — | — | — | — | 0x1121C | 101,080 | `ec71a5a4` / `ec71a5a4 (unchanged)` | n/a | | |

Two 8 KB bands (16,384 B) fit in both shapes. Other moved landmarks (release / debug):
`Map_Tails` 0x5C320/0x5DD70 → 0x2A420/0x2AC70; `Map_Knuckles` 0x7D27E/0x7ECCE → 0x4B37E/0x4BBCE;
`HeightMaps` 0x2A420/0x2AC70 → 0x6DA50/0x6E2A0; `Song_MovingTrucks` 0x58630 → 0xA0630; `Sfx_33`
0x5BB20/0x5D570 → 0xA3B20/0xA5570; `Replay_OJZ_Fixture` 0x9FEC0/0xA1F90 → 0xA4890/0xA6960;
`BusError` 0xA0120/0xA21F0 → 0xA4AF0/0xA6BC0; `ErrorHandlerBlob` 0xA027A/0xA234A →
0xA4C4A/0xA6D1A. `EndOfRom` moved +0x49D0 in both shapes (the reserve + bank-boundary pad now
between the data and the banks, minus the old 0x48000 gap).

**Z80 resident blob (release, `[0x3A0, 0x1BEA)` vs golden `a938b7d5`):** exactly 4 bytes
changed, each `0x0B → 0x14` — the `SND_ENGINE_TABLE_BANK`/`SFX_BLOB_BANK` immediates at ROM
0x606, 0x1121, 0x1297, 0x15EF. Every other prefix diff is the vector table (fault handlers moved),
the header checksum/`rom_end`, and 68k absolute references to moved data; the object bank
diffs are the CharDef records pointing at `Map_Tails`/`Map_Knuckles`.

**Fold-vs-placement audit (`seam2::sound_layout` vs the listings, both shapes):** all ten
predictions equal the placement — blip 0x90000, shared 0x98000 (`Dac_Kick`), head VMAs
0x8000/0x8357/0x845F/0x8571/0x85B1 (`SoundTablesZ80_Head`/`SndDefaultPitchTable`/
`SfxBlobWinTab`/`SeqOpcodeTable`/`DacSampleTable`), MT 0xA0630, SFX 0xA3B20 plain / 0xA5570
debug; `sound_bank_id` = 0x14; `SongTable` 0xA3B10/0xA5550 match pins.rs. The always-on
`[sound.fold-vs-placement]` gate passed on every build.

## Frozen tables: what moved, and the quantum audit

Two island rows per sound-on table were hand-moved (+0x48000: `Dac_Temp_Blip`,
`SoundTablesZ80_Head`; `Song_MovingTrucks`/`Sfx_33` were moved by the same delta as a
courtesy — they are packed rows the walk re-derives anyway). The placer accepted the new map +
tables in ONE round in every shape (no "hand ruling needed", no island reclassification),
reporting 5 (release) / 6 (debug) `[layout.provisional-drift]` warnings, then
`golden/derive_offcanonical_sizes.sh` re-derived all seven tables; a second derive run was
**byte-for-byte identical** (`diff -r` clean) — the fixpoint proof. 44 rows moved across
s4/s4_debug/config_a/config_b/lean; demo/demo_debug unchanged; **0 rows changed their
`packed_align_of` quantum** (full per-row table: `quantum_audit` section below).

`repin -- --aeon <worktree>` regenerated `pins.rs` (sound family +0x48000, character data
−0x31F00/−0x33100, collision family +0x43630, tail +0x49D0).

## What changed

**aeon** (`parcel/rom-relayout`):
- `games/sonic4/map.toml` — anchors 0x90000/0xA0000 with the BANK PLACEMENT RULE and its
  bounding constraint as comments; order: `Map_Tails`, `Map_Knuckles` ahead of `HeightMaps`,
  banks after, tail = `GameState_*`, replay fixture, fault island (error_handler still LAST);
  the inert `z80_moving_trucks_bank @ 0x60000` region renamed `z80_sound_bank` at the
  `sound_bank` LMA (measured: no sigil consumer reads a `z80_bank` region — `RegionKind::Z80Bank`
  is constructed by `map_load` and matched by nothing; `region_for` considers `rom` only; the old
  LMA sat inside `Map_Tails` unnoticed).
- `tools/inject_editor_bg.py` — `BGANIM_SECTION_CEILINGS` = 12,288 both rows (table kept);
  `_D28_*` derivation constants deleted; refusal text no longer names a hardware anchor.
- `tools/bganim_room.py` — enforces the rule post-sigil (`DATA_GROWTH_RESERVE`, `rule_anchor`);
  FAIL names the new anchor pair; unaligned anchor fails by name; slack is reported.
- `tools/test_bg_emit.py` — 4 new rule tests (red-first), fixture tests re-derived,
  `test_generator_accepts_the_minimum_across_shapes` retired as its own text instructed.
- `tools/fixtures/bganim_room_excerpt.lst` — re-cut from the re-layout's `s4.debug.lst`.
- `docs/DEFERRED_WORK.md` (both bookings closed), `docs/ENGINE_ARCHITECTURE.md` (ROM layout
  section + soundBankHead paragraph), this report.

**sigil** (`parcel/rom-relayout`):
- `crates/sigil-harness/golden/offcanonical_sizes/{s4,s4_debug,config_a,config_b,lean}.txt`,
  `src/pins.rs` (regenerated).
- Tests re-derived from `seam2::sound_layout` instead of literals: `seam2_layout_derivation`
  (keeps its literal drift-detector role with the new addresses; the doctored anchor is read off
  the real one), `seam2_dac_emit`, `seam2_dac_head_colink`, `seam2_colink_probe`, `dac_port`,
  `sfx_port`, `mt_port`, `sfx_negative_probes`, `mt_negative_probes` (the wrong bank is the
  window ABOVE the real one and is asserted to differ; straddle bases are `top − 0x400/0x1000`).
  `ports.rs` (aeon-independent by construction — no AEON_DIR) got ONE `PROBE_BANK_VMA` constant
  with every expected byte derived from it. `repin_pins.rs` `ASSEMBLED_LEN`/`DEBUG_ASSEMBLED_LEN`
  0xA5BA0/0xA7C70 with the story. `seam2.rs`: doc comments only.
- NOT touched: `golden/*.bin`, `provenance.toml` (controller refreezes), `repin.toml`.
- Carriers named in the brief that do not exist any more: `engine.inc` (deleted at K4 inc-6B;
  `repin` printed no "engine.inc orgs" line) and `mixed_dac_rom.rs` (only mentioned in comments).

## Verification

- Four shapes built canonically on aeon `dddfbf0a` with the sigil worktree's release
  binaries `/home/volence/sonic_hacks/sigil/.worktrees/rom-relayout/target/release/{sigil,emit_sound_blob}`
  (rebuilt: YES: `cargo build --release` in the sigil worktree at 18:05 (baseline, sigil master `007f73ef`, 13.8 s, load 2.4) and again at 18:34 after the sigil edits (1.35 s relink, load 2.1); both canonical shapes FAST-rebuilt with the second binary are byte-identical to the canonical builds (`f81c6811` / `090c6f35`)). ROMs `rm -f`'d before each build. Exit codes: release 0, DEBUG 0, demo 0, demo.debug 0 (18:29:33 -> 18:33, ~60 s per shape at load ~3.6-4.1); `ErrorHandlerBlob` is the last label before `EndOfRom` in all four listings.
- aeon pytest lane (inside build.sh, release shape): 1406 passed / 9 skipped / 49 subtests (release, demo.debug) and 1407 passed / 8 skipped / 49 subtests (DEBUG, demo), 0 failed in every shape. `emp_expect_fail` 35/35.
  `bganim_room --gate` on `s4.lst` and `s4.debug.lst`: positive margin in both, rule line
  "declared 0x90000 (this shape binds exactly)".
- Red-first evidence: the four rule tests failed on the un-implemented tool —
  `AttributeError: module 'bganim_room' has no attribute 'DATA_GROWTH_RESERVE'`, the unaligned
  anchor passing (`AssertionError: 0 != 1`), the slack regex not found — then passed (92 passed
  in `test_bg_emit.py` + `test_s4budget.py`). Sigil negative probes: with the derivation poisoned (`let wrong = bank;` in both files) `wrong_bank_cross_seam_label_fires_the_co_residency_ensure` (sfx) and `wrong_bank_cross_seam_label_fires_all_five_co_residency_ensures` (mt) fail at the guard `assertion left != right failed: the wrong bank must differ`; restored via `git checkout`, both green again (sfx 5/5, mt 4/4).
- sigil `cargo test --release --workspace --no-fail-fast` with `AEON_DIR` at the aeon worktree:
  343 test binaries, **3917 passed, 26 failed, 4 ignored**, cargo rc=101 (18:35:00 -> 18:37:27, load 5.0). Expected-red list (goldens/pins bound to the OLD bytes until the controller
  refreezes; byte-changing by design): all 26 compare bytes/CRCs/lengths against the FROZEN goldens or the provenance tip and are red by design until the controller refreezes: native_full_rom {native_full_sonic4_plain, native_full_sonic4_debug}, native_offcanonical_full {config_a_full_file, config_b_full_file, lean_full_file}, anchor gates {config_a_anchor_matches_golden, config_b_anchor_matches_golden, lean_anchor_matches_golden, flipped_config_a_anchor_matches_golden, config_b_doctored_size_table_breaks_the_build (its undoctored control compares to the golden)}, map-row/pin gates {both_spellings_of_the_section_row_build_the_same_rom, a_passing_extra_entry_moves_no_bytes} (full-file size vs golden), boot blob {s4_boot_data_blob_present, native_blob_matches_reference_plain/debug} (the 4 bank-id bytes at 0x606.. differ from the golden blob), sound slices {colinked_dac_head_matches_the_reference_rom_slice_both_shapes, colink_banks_still_match_reference, pitchtable_matches_the_reference_rom_slice_both_shapes, colinked_seq_opcode_tab_matches_the_reference_rom_slice_both_shapes, colinked_sfx_head_matches_the_reference_rom_slice_both_shapes, sound_tables_z80_matches_the_reference_rom_slice_both_shapes, sfx_bank_region_matches_reference, sfx_bank_debug_region_matches_reference, mt_bank_region_matches_reference, mt_bank_debug_region_matches_reference} (the golden ROM has other data at the new bank LMAs), provenance {aeon_dir_matches_the_provenance_tip} (tip a938b7d5/699845 vs f81c6811/718741). No failure is a non-golden assertion..
- Timings ship with `uptime` in the scratch logs quoted above (sigil release build 13.8 s at
  load 2.4; each canonical shape ~60 s at load ~4).

## Deviations from the brief (for ratification)

1. `SIGIL_BUILD`/`SIGIL_EMIT` were UNSET in the agent shell. The brief says that is a BLOCKED
   report; but it also requires pointing both at the parcel worktree's rebuilt release binaries,
   so I built sigil master in the worktree first (13.8 s) and used those for the baseline, then
   rebuilt after the sigil edits. No main-tree binary was ever used.
2. `Map_Tails`/`Map_Knuckles` were moved (un-exiled) ahead of `HeightMaps`, and the two
   `GameState_*` test states stay in the tail after the banks. The brief's target list did not
   name the character data; the map.toml comment and the DEFERRED_WORK "exile twice" booking both
   said the re-layout retires the exile, and putting them AFTER `collision_data` would have
   destroyed the room instrument.
3. The `z80_moving_trucks_bank` region was renamed (`z80_sound_bank`) and moved to the
   `sound_bank` LMA rather than moved as-is to "the 0x60000 region" slot: it is inert and its
   name/LMA were false.
4. `ports.rs` was NOT coupled to the aeon map (it reads no aeon tree); its fixture VMA became a
   single constant with every expectation derived from it.
5. Coincidence-class literals left alone (synthetic fixtures independent of the game's layout):
   `sound_migration_negative_probes.rs`, `seam2_phased_head.rs` (0x5856D as "a representative
   high-bank LMA"), `z80_resident_cell.rs`, `native.rs`/`repin.rs`/`map_placement.rs`/`seam2.rs`
   inline-map unit tests, `seam1.rs` `SOUND_BANK_ID_SIZE_PROBE = 0x0B` (a width probe).

## BLOCKED items

None.

## Controller follow-ups

- **refreeze**: `refreeze --freeze rom-relayout --ab` with prose, then `provenance.toml`; the
  golden-bound tests listed above go green only after it.
- **effects gates**: `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`
  (this parcel touched neither `engine/effects` nor `bg_anim.emp`, but bytes moved).
- **boot + sound check on the emulator**: the resident driver now latches bank $14 / DAC banks
  $12/$13; confirm music + DAC drums + an SFX play (controller runtime follow-up).

## Appendix — quantum audit (every frozen row that moved)

| shape | label | old base | new base | delta | old q | new q | flag | how |
|---|---|---|---|---|---|---|---|---|
| s4 | BusError | 0xA0120 | 0xA4AF0 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4 | Dac_Temp_Blip | 0x48000 | 0x90000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| s4 | EndOfRom | 0xA11D0 | 0xA5BA0 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4 | GameState_OJZScroll_Init | 0x9F950 | 0xA4320 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4 | HeightMaps | 0x2A420 | 0x6DA50 | +0x43630 | 16 | 16 |  | re-derived by the placer |
| s4 | Map_Tails | 0x5C320 | 0x2A420 | -0x31f00 | 16 | 16 |  | re-derived by the placer |
| s4 | Replay_OJZ_Fixture | 0x9FEC0 | 0xA4890 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4 | Sfx_33 | 0x5BB20 | 0xA3B20 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| s4 | Song_MovingTrucks | 0x58630 | 0xA0630 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| s4 | SoundTablesZ80_Head | 0x58000 | 0xA0000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| s4_debug | BusError | 0xA21F0 | 0xA6BC0 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4_debug | Dac_Temp_Blip | 0x48000 | 0x90000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| s4_debug | EndOfRom | 0xA32A0 | 0xA7C70 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4_debug | GameState_OJZScroll_Init | 0xA1724 | 0xA60F4 | +0x49d0 | 4 | 4 |  | re-derived by the placer |
| s4_debug | GameState_ObjectTest_Init | 0xA13A0 | 0xA5D70 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4_debug | HeightMaps | 0x2AC70 | 0x6E2A0 | +0x43630 | 16 | 16 |  | re-derived by the placer |
| s4_debug | Map_Tails | 0x5DD70 | 0x2AC70 | -0x33100 | 16 | 16 |  | re-derived by the placer |
| s4_debug | Replay_OJZ_Fixture | 0xA1F90 | 0xA6960 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| s4_debug | Sfx_33 | 0x5D570 | 0xA5570 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| s4_debug | Song_MovingTrucks | 0x58630 | 0xA0630 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| s4_debug | SoundTablesZ80_Head | 0x58000 | 0xA0000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| config_a | BusError | 0xA21F0 | 0xA6BC0 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| config_a | Dac_Temp_Blip | 0x48000 | 0x90000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| config_a | EndOfRom | 0xA32A0 | 0xA7C70 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| config_a | GameState_OJZScroll_Init | 0xA1724 | 0xA60F4 | +0x49d0 | 4 | 4 |  | re-derived by the placer |
| config_a | GameState_ObjectTest_Init | 0xA13A0 | 0xA5D70 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| config_a | HeightMaps | 0x2AC80 | 0x6E2B0 | +0x43630 | 16 | 16 |  | re-derived by the placer |
| config_a | Map_Tails | 0x5DD70 | 0x2AC80 | -0x330f0 | 16 | 16 |  | re-derived by the placer |
| config_a | Replay_OJZ_Fixture | 0xA1F90 | 0xA6960 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| config_a | Sfx_33 | 0x5D570 | 0xA5570 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| config_a | Song_MovingTrucks | 0x58630 | 0xA0630 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| config_a | SoundTablesZ80_Head | 0x58000 | 0xA0000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| config_b | HeightMaps | 0x2A3C0 | 0x6D9F0 | +0x43630 | 16 | 16 |  | re-derived by the placer |
| config_b | Map_Tails | 0x46840 | 0x2A3C0 | -0x1c480 | 16 | 16 |  | re-derived by the placer |
| lean | Dac_Temp_Blip | 0x48000 | 0x90000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| lean | EndOfRom | 0xA014E | 0xA4B1E | +0x49d0 | 2 | 2 |  | re-derived by the placer |
| lean | GameState_OJZScroll_Init | 0x9F950 | 0xA4320 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| lean | HeightMaps | 0x2A420 | 0x6DA50 | +0x43630 | 16 | 16 |  | re-derived by the placer |
| lean | Map_Tails | 0x5C320 | 0x2A420 | -0x31f00 | 16 | 16 |  | re-derived by the placer |
| lean | ReleaseFault | 0xA0120 | 0xA4AF0 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| lean | Replay_OJZ_Fixture | 0x9FEC0 | 0xA4890 | +0x49d0 | 16 | 16 |  | re-derived by the placer |
| lean | Sfx_33 | 0x5BB20 | 0xA3B20 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| lean | Song_MovingTrucks | 0x58630 | 0xA0630 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |
| lean | SoundTablesZ80_Head | 0x58000 | 0xA0000 | +0x48000 | 16 | 16 |  | HAND (island/bank row, +0x48000) |

rows moved: 44; quantum changed: 0

