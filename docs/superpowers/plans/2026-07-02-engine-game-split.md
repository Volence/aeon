# Engine/Game Agnostic Split Implementation Plan

> **⚠ SUPERSEDED (2026-07-07)** by `2026-07-07-engine-game-split-execution.md`.
> The 2026-07-03 sound merges (SFX Stage A hotkey rework, table banking) drifted this
> plan's anchors and killed one seam (`GAME_FM_PATCHES` — the driver's fm_patches
> include no longer exists) while adding four new ones (default pitch table, ring SFX
> ids, camera `_pl_state` read, root `test/`). Execute the 2026-07-07 plan instead.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real engine/game wall — engine.inc + gameHeader macro + parameterized boot + soundBankHead contract + def/RAM splits + `games/demo/` booting on oracle.

**Architecture:** E1 vectors/header/boot (the org-0 + entry seams), E2 stray inversions (sine/patches/vectors/debug harness/sfx table), E3 sound-bank-head contract, E4 def split, E5 RAM split, E6 build gating + games/demo, E7 grep-gate + docs + merge. Spec: `docs/superpowers/specs/2026-07-02-engine-game-split-design.md` (APPROVED). Stage classes: **[BYTE]** = byte-identical `s4.bin` required (hash compare); **[BEHAV]** = behavior-identical (oracle boot + circuit + sound smoke).

**Standing rules:** research step first (anchors as of the 2026-07-02 coupling map WILL drift); build `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` AND plain `./build.sh` per stage (sound flag lesson); runtime-boot after any ram/org change; exact-path commits; branch `feat/engine-game-split`; merge at E7. **`tools/ojz_strip_gen.py` + `games/sonic4/data/editor/ojz/**` are daemon-watched — coordinate with the user for the generator-path repoints in E6; never edit autonomously.** Record the baseline `md5sum s4.bin` in Task 1 and re-hash per [BYTE] stage.

---

### Task 1: Branch + baseline hashes

- [ ] **Step 1: Research.** Read the spec + the 2026-06-28 restructure design (both, fully). Read `games/sonic4/main.asm` in full — it is the document being decomposed. Read `engine/system/boot.asm:190-293`, `build.sh` in full.
- [ ] **Step 2: Branch + hash.** `git checkout -b feat/engine-game-split`; build both flag variants; record `md5sum s4.bin` for each in the scratchpad + a full oracle circuit + sound smoke (UP/A/B/C hotkeys) as the behavior baseline.

### Task 2: E1 — vectors.asm + gameHeader + parameterized boot **[BEHAV]**

**Files:**
- Create: `engine/system/vectors.asm`, `engine/system/header.inc` (the `gameHeader` macro), first slice of `engine/engine.inc`
- Modify: `games/sonic4/main.asm` (org-0 region replaced by the macro invocation), `engine/system/boot.asm:217,224-225`, `games/sonic4/` (new `config/game.asm` declaring `GAME_ENTRY_ID`, `GAME_BOOT_SONG`)

- [ ] **Step 1: Research.** Verify the vector table contents (main.asm:25-71) reference only engine symbols; confirm `EndOfRom` + checksum span mechanics (fixheader consumes the header at fixed offsets — the macro must emit the exact byte layout; diff the emitted $100-$1FF against baseline).
- [ ] **Step 2: Implement.** `vectors.asm` = the 64 vectors + `NullInterrupt`. `gameHeader` macro emits $100-$1FF from named params (console string, copyright, domestic/overseas, serial, IO, ROM start/`EndOfRom-1`, RAM range, SRAM decl, region) with per-field width asserts (each string padded/truncated to its exact field width at build time — a wrong-length title is a build error, not a corrupt header). Boot: `move.l #Game_Entry,(Game_State).w` / `move.b #GAME_ENTRY_ID,(Game_State_ID).w`; the DEBUG ping becomes `if GAME_BOOT_SONG>=0` around boot.asm:215-218. sonic4: `Game_Entry = GameState_OJZScroll_Init` equate + ids in `config/game.asm` (the test states still live where they live — E6 does not move them; the equate is the contract).
- [ ] **Step 3: Verify.** Build; **compare $000-$1FF bytes against baseline ROM** (`cmp` the first 512 bytes — must be identical); oracle boot + circuit + sound smoke. Commit: `feat(engine): engine-owned vectors + gameHeader macro + parameterized boot (E1)`

### Task 3: E2 — invert the strays **[BEHAV]**

**Files:**
- Move: `games/sonic4/data/misc/sine.bin` → `engine/data/sine.bin` (+ math.asm:27)
- Create: `games/sonic4/debug/game_debug.asm` (Debug_MusicToggle + Dbg_SfxIdTable move from `engine/system/game_loop.asm:26-136`), engine `GAME_DEBUG_TICK` hook in GameLoop
- Modify: `engine/sound/z80_sound_driver.asm:1445` (→ `include GAME_FM_PATCHES` symbol; sonic4 declares it), `engine/debug/compression_selftest.asm:92` + `tools/gen_compression_vectors.py` output path (engine-side generated dir), `games/sonic4/main.asm`
- Move: `engine/sound/sfx_blob_win_tab.asm` → `games/sonic4/data/sound/sfx_blob_win_tab.asm`; `engine/sound/sound_sfx.asm:63` (`SFX_BLOB_BANK` → game-declared), `:677` (`SFXID_SPINDASH` → `SFXID_REV_LOOP` contract constant, -1 = off)

- [ ] **Step 1: Research.** Re-verify each reference live; check `gen_compression_vectors.py` for daemon status (it is NOT daemon-watched — only ojz_strip_gen.py is; confirm); find every consumer of the moved files (grep include paths).
- [ ] **Step 2: Implement** the six inversions per the spec §2.3-2.4. The Z80-side `SFXID_REV_LOOP` check must handle -1 cleanly (assemble the compare out under `if`, not runtime).
- [ ] **Step 3: Verify.** Build both variants; oracle: boot, circuit, ALL sound hotkeys (they moved — regression-critical), spindash SFX rev still behaves. Commit: `refactor(engine): engine→game references inverted — sine, patches, vectors, debug harness, sfx window table (E2)`

### Task 4: E3 — soundBankHead contract **[BYTE]**

**Files:**
- Create: the `soundBankHead` macro (in `engine/sound/` bank-contract include)
- Modify: `games/sonic4/main.asm:258-285` (the song-bank head becomes: align/save/cpu z80/phase → `soundBankHead` → game pitch table → dephase → songs)

- [ ] **Step 1: Research.** Re-read main.asm:235-378 with the coupling map §2 in hand; confirm exactly which lines the macro absorbs (sound_tables_z80 include + the invariant comments) and which stay game-side (MT pitch table, contiguity guards — game data).
- [ ] **Step 2: Implement.** The macro emits the engine tables + carries the invariant documentation (window-relative labels, co-location requirement, NO-CODE rule, the multi-bank replicate rule from sound docs). Game bank invokes it first.
- [ ] **Step 3: Verify.** **Byte-identical s4.bin** (pure restructure — same bytes, same order). Hash compare. Commit: `feat(sound): soundBankHead — the engine-tables-at-bank-head contract formalized (E3)`

### Task 5: E4 — def split **[BYTE-target, BEHAV-fallback]**

**Files:**
- Create: `engine/constants.asm`, `engine/sound_constants.asm`, `games/sonic4/config/constants.asm`, `games/sonic4/config/sound_ids.asm`; `engine/engine.inc` grows the defs prologue
- Move: `structs.asm`, `macros.asm` → `engine/` wholesale
- Modify: `games/sonic4/main.asm` defs prologue

- [ ] **Step 1: Research.** Re-run the classification greps from the coupling map §5 against CURRENT files (designs may have landed constants); build the exact line-level split lists BEFORE cutting; check `tools/` for Python readers of the def files (the constants-sync pytest pattern — s4budget/s4lint may parse paths).
- [ ] **Step 2: Split.** Engine slices to `engine/`, game slices to `config/`; include order preserved exactly (defs are order-sensitive — game config AFTER engine defs, before ram). No value changes, no renames.
- [ ] **Step 3: Verify.** Target byte-identical (pure def relocation should be); if the hash moves, diff the listing (`s4.lst`) to prove only line-number/file metadata changed, then run the full BEHAV suite. pytest green. Commit: `refactor: engine/game def split — constants + sound ids (E4)`

### Task 6: E5 — RAM split **[BEHAV + mandatory runtime verify]**

**Files:**
- Create: `engine/ram.asm` (exports `Engine_RAM_End`), `games/sonic4/config/ram.asm`
- Modify: manifest include order

- [ ] **Step 1: Research.** Current ram.asm game-slice list (coupling map §5: player block, pos rings, Dbg_* — re-verify against landed designs); the phase/dephase + overflow-guard structure; every alignment-sensitive boundary.
- [ ] **Step 2: Split.** Engine region phases from RAM base → `Engine_RAM_End`; game region phases from there; both keep overflow guards; every block ends even (the AS lesson — an odd `ds.b` crashes the NEXT word field at runtime with a green build).
- [ ] **Step 3: Verify.** Build; **oracle runtime boot MANDATORY** + full circuit + sound smoke + entity/ring spot checks (addresses moved — watch for silent word-misalignment crashes); `s4.lst` RAM map eyeballed against the old. Commit: `refactor: engine/game RAM split — Engine_RAM_End seam (E5)`

### Task 7: E6 — build gating + games/demo **[new artifact]**

**⚠ Generator-path coordination:** if any generator output path changes, coordinate with the user (daemon watches ojz_strip_gen.py + the editor tree). The design keeps sonic4 generator paths UNCHANGED — only the invocation moves into `games/sonic4/prebuild.sh`.

**Files:**
- Create: `games/sonic4/prebuild.sh` (the seven generator calls, verbatim), `games/demo/{main.asm, config/{game.asm, constants.asm, ram.asm}, data/placeholder_sprite.bin}`
- Modify: `build.sh` (invoke `games/$GAME/prebuild.sh` if present; drop the inline generator block)

- [ ] **Step 1: Research.** build.sh:63-137 verbatim (what env each generator needs); the object-test state (`test/object_test_state.asm`) as the model for the demo's entry state; minimal sprite spawn requirements (objdef? or direct SST setup — find the smallest correct path through Load_Object/AllocDynamic).
- [ ] **Step 2: Implement.** prebuild extraction (sonic4 output byte-identical — hash); the demo: manifest per spec §5 (gameHeader "AEON ENGINE DEMO", GAME_BOOT_SONG=-1, engine-default FM patches, one spawned test object with an uncompressed 4-tile placeholder sprite, backdrop color, TODO hooks). `build.sh demo` → `demo.bin`.
- [ ] **Step 3: Verify.** sonic4 build byte-identical to Task-6 output; **`demo.bin` boots on oracle: backdrop + the sprite renders** (screenshot). This is the spec's success criterion made real. Commit: `feat: games/demo — the engine boots without Sonic (E6)`

### Task 8: E7 — the grep gate, docs, merge

- [ ] **Step 1: The gate.** `grep -rnE "SONG_|SFXID_|OJZ|GS_OJZ|Sonic" engine/` → comments only (fix any stragglers found). Both build variants green for both games; full BEHAV suite on sonic4; demo boot.
- [ ] **Step 2: Docs.** ARCH: the engine/game contract section written as-designed (engine.inc layout contract, gameHeader, Game_Entry, soundBankHead, gameEngineBlockIncludes, prebuild hook); the 2026-06-28 spec's status updated to SHIPPED-in-full (+ the sound_banked_z80 stale-name note); CLAUDE.md's "Deferred (its own design pass)" paragraph REMOVED (it shipped); DEFERRED_WORK closeouts; queue-doc log.
- [ ] **Step 3: Merge** `feat/engine-game-split` → master.

---

## Self-review (done at write time)

- **Spec coverage:** §2.1-2.2→T2; §2.3→T4 + T3 (sfx table/const moves); §2.4→T3; §3→T2/T4 (engine.inc grows across E1/E3/E4, completed by E4); §4→T5-6; §5→T7; §6 verification classes→per-task tags + T8 gate.
- **Placeholders:** none. The one open implementation choice (demo sprite spawn path) is a researched decision in T7 Step 1 with the criterion stated (smallest correct path).
- **Consistency:** `gameHeader`, `Game_Entry`/`GAME_ENTRY_ID`, `GAME_BOOT_SONG`, `GAME_FM_PATCHES`, `GAME_DEBUG_TICK`, `gameEngineBlockIncludes`, `soundBankHead`, `objBankStart/End`, `Engine_RAM_End`, `prebuild.sh` uniform.
