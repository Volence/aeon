# Engine/Game Agnostic Split — Execution Plan (2026-07-07 refresh)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **SUPERSEDES** `2026-07-02-engine-game-split.md` (same spec, same goal). That plan's
> line anchors and two of its seams went stale when the 2026-07-03 sound packages merged.
> This refresh re-verified EVERY anchor against master @ `9bacc93` (2026-07-07) and adds
> four seams the old plan does not cover. Use THIS plan; the old one is marked superseded.
> Anchors re-verified again @ `2e42ec2` (post package-2 SFX Stage B/C merge): drifts in
> items h/j and the T5 sound-constants game slice (SFXPRI_* ladder) are folded in.

**Goal:** Real engine/game wall — `engine/engine.inc` + game manifest + `gameHeader` + parameterized boot + `soundBankHead` contract + def/RAM splits + `games/demo/` booting on oracle. Sonic 4 behavior and `s4.bin` unchanged.

**Spec:** `docs/superpowers/specs/2026-07-02-engine-game-split-design.md` (APPROVED). Read it fully first. Spec deltas discovered in this refresh are listed below — where they conflict, THIS plan wins (the code moved after the spec was written).

**Architecture:** T2 vectors/header/boot seams → T3 stray inversions (now TEN of them) → T4 soundBankHead → T5 def split → T6 RAM split → T7 engine.inc + manifest (moved LATE deliberately: every earlier stage keeps main.asm as the working orchestrator, so the big include-reshuffle is one mechanical byte-identical step at the end) → T8 build gating + games/demo → T9 grep gate + docs + merge.

**Stage classes:** **[BYTE]** = `s4.bin` must hash identical (md5) to the previous stage. **[BEHAV]** = behavior-identical: oracle boot + full OJZ circuit (walk/jump/spindash left and right across at least one section boundary) + sound smoke.

---

## Spec deltas (verified 2026-07-07 — these override the spec/old plan)

1. **The `GAME_FM_PATCHES` seam is DEAD.** `z80_sound_driver.asm` no longer includes any
   game FM-patch file (the inline patch table was deleted in the budget-recovery phase;
   patches are read per-song via `SongPatchTable` through the banked window). Do not
   create `GAME_FM_PATCHES`.
2. **NEW seam — default pitch table:** `engine/sound/sound_fm.asm:690` loads game label
   `MovingTrucks_PitchTable` as the engine's default pitch table. Becomes contract label
   `SndDefaultPitchTable` (T3.8).
3. **NEW seam — ring SFX ids:** `engine/sound/sound_api.asm:215,218` reference
   `SFXID_RING_RIGHT`/`SFXID_RING_LEFT`. These become documented contract constants the
   game must define (T3.7) — the ring system stays engine.
4. **NEW seam — camera jump-lock:** `engine/level/camera.asm:180-184` reads
   `Player_1+_pl_state` and compares `PSTATE_JUMP`/`PSTATE_ROLLJUMP` — all three symbols
   are game-defined (`games/sonic4/player/player_common.asm:33`, `constants.asm:271+`).
   This would break the demo build. Gate it behind game-declared
   `GAME_CAMERA_JUMP_LOCK` (T3.9).
5. **NEW seam — ring placeholder art slot:** engine `rings.asm` (DrawRings) uses
   `VRAM_RING_PLACEHOLDER` (`constants.asm:538`), which derives from game-slice
   `VRAM_TEST_OBJ`. `VRAM_RING_PLACEHOLDER` becomes a game-declared contract constant
   (T5).
6. **The Z80 bank head grew.** It is now FOUR engine table files with a game pitch table
   and the (engine→game reclassified) SFX window table interleaved
   (`games/sonic4/main.asm:283-308`): `sound_tables_z80` → game pitch table →
   `sfx_blob_win_tab` → `seq_opcode_tab` → `dac_sample_tab`. `soundBankHead` takes the
   two game files as macro arguments to preserve byte-identity (T4).
7. **Boot autoplay changed shape.** The DEBUG boot song block is now behind
   `SOUND_DEBUG_HOTKEYS` (`boot.asm:209-221`) and also sets `Dbg_Music_On`. The spec's
   `GAME_BOOT_SONG` constant is replaced by a game-supplied **`gameBootHook` macro**
   (required, may be empty) — same intent, matches the code's current shape (T2).
8. **`gameHeader` is symbol-driven, not parameter-driven.** The game defines `GAME_*`
   string symbols; the engine macro emits and width-asserts the header. Same contract,
   fewer AS macro-argument pitfalls (T2).
9. **Root `test/` is game content.** `test/object_test_state.asm` + `test/ojz_scroll_test.asm`
   (+ their binaries) move to `games/sonic4/test/` (T3.10). The old plan left them; the
   manifest model makes leaving them untenable.
10. **`sound_banked_z80.asm` does not exist** (folded into the resident blob) — already
    noted in the spec header; repeated here so nobody hunts for it.

## Standing rules (read before every task)

- Branch: `feat/engine-game-split`. Merge to master only at T9. Commit after EVERY task
  with exact paths (`git add <file> <file>` — never `-A`).
- Build BOTH variants per stage: `SOUND_DRIVER_ENABLED=1 SOUND_DEBUG_HOTKEYS=1 DEBUG=1 ./build.sh`
  AND plain `./build.sh`. A plain build excludes ALL sound — a green plain build proves
  nothing about sound code.
- **Hash discipline:** the autocommit daemon can trigger plain rebuilds of `s4.bin`
  mid-session. NEVER hash a stale ROM — always rebuild immediately before `md5sum`, and
  hash both flag variants separately.
- **No functional changes ride along.** Known latent issues (e.g. the `sprSize` w/h swap
  noted in memory) are explicitly NOT fixed here. Restructure only.
- `tools/ojz_strip_gen.py` and `games/sonic4/data/editor/ojz/**` are daemon-watched —
  never edit them. This plan never needs to.
- Oracle/emulator work is done by the CONTROLLER session in the foreground — never from
  a background subagent (MCP socket deadlocks).
- Oracle symbol lookups go stale after `reload_rom` — resolve addresses from `s4.lst`.
- After ANY RAM-layout or org change, a green build is NOT sufficient — oracle runtime
  boot-verify is mandatory (AS does not auto-align `ds.w`/`ds.l`; an odd `ds.b` run
  address-errors the next word field at runtime).
- AS is multi-pass: forward references between equates are fine. If the assembler loops
  with warning #80 ("symbol value changes force additional pass"), you created an
  order-dependent definition — restructure the split, don't suppress the warning.

## The verified coupling inventory (master @ 9bacc93; re-verified @ 2e42ec2 after the package-2 SFX Stage B/C merge)

Every engine→game reference that exists today. T2/T3 must clear ALL of these:

| # | Site | Symbol(s) | Fix (task) |
|---|------|-----------|------------|
| a | `engine/system/boot.asm:225-226` | `GameState_OJZScroll_Init`, `GS_OJZ_SCROLL_TEST` | `Game_Entry`/`GAME_ENTRY_ID` contract (T2) |
| b | `engine/system/boot.asm:209-221` | `SONG_MOVINGTRUCKS`, `Dbg_Music_On` | `gameBootHook` macro (T2) |
| c | `engine/system/game_loop.asm:12-16, 27-135` | `Debug_MusicToggle`, `Dbg_SfxIdTable`, `SONG_*`, `SFXID_*` | move harness game-side + `gameDebugTick` macro (T3.3) |
| d | `engine/system/math.asm:27` | `games/sonic4/data/misc/sine.bin` | move bin to `engine/data/` (T3.1) |
| e | `engine/debug/compression_selftest.asm:92` | `games/sonic4/data/generated/test/vectors.asm` | generator emits engine-side (T3.2) |
| f | `engine/sound/sfx_blob_win_tab.asm` (whole file) | `Sfx_*` blob labels, `SFXID_*` gaps | reclassify: move file game-side (T3.4) |
| g | `engine/sound/sound_sfx.asm:64` | `SFX_BLOB_BANK = sfx_bankid(Sfx_33)` | game-declared constant (T3.5) |
| h | `engine/sound/sound_sfx.asm:698-699` | `SFXID_SPINDASH` (spindash-rev special case; coexists with the Stage-C `SHF_CONTINUOUS` class — separate mechanisms, do not conflate) | `SFXID_REV_LOOP` contract, −1 = off (T3.6) |
| i | `engine/sound/sound_api.asm:215,218` | `SFXID_RING_RIGHT`, `SFXID_RING_LEFT` | contract constants (T3.7) |
| j | `engine/sound/sound_fm.asm:690` (comment :673) | `MovingTrucks_PitchTable` | `SndDefaultPitchTable` contract label (T3.8) |
| k | `engine/level/camera.asm:180-184` | `_pl_state`, `PSTATE_JUMP`, `PSTATE_ROLLJUMP` | `GAME_CAMERA_JUMP_LOCK` gate (T3.9) |
| l | `engine/level/camera.asm` + `ram.asm:319` | `Camera_Spindash_Lag` (Sonic-flavored engine RAM name) | rename → `Camera_Hold_Frames` (T3.9) |

Engine data labels consumed under `SOUND_DRIVER_ENABLED` (`SongTable`, `SfxTable`,
`SND_ENGINE_TABLE_BANK`) are game-supplied by design — they become documented contract
symbols (T4/T9), not code changes.

NOT couplings (verified): `HeightMaps`/`AngleTable`/`SolidityTable` and act/objdef/entity
data are consumed via RAM pointers set by game states — no engine label references.
`Map_Sonic` in `engine/debug/debugger.asm:61` is a comment. `Player_1`/`Player_2` (the two
reserved SST slots) and the ring system STAY ENGINE (documented decision — the engine's
"tracked entity" slots and collectible system; re-taxonomize only with a second game's
evidence).

---

### Task 1: Branch + baselines

- [ ] **Step 1: Read.** The spec (`2026-07-02-engine-game-split-design.md`), this plan's
  coupling inventory, `games/sonic4/main.asm` in full (446 lines — it is the document
  being decomposed), `engine/system/boot.asm:190-293`, `build.sh` in full.
- [ ] **Step 2: Branch + hash.**

```bash
git checkout -b feat/engine-game-split
SOUND_DRIVER_ENABLED=1 SOUND_DEBUG_HOTKEYS=1 DEBUG=1 ./build.sh && md5sum s4.bin   # record: SOUND+DEBUG hash
./build.sh && md5sum s4.bin                                                        # record: plain hash
```

  Record both hashes in the scratchpad. These are the T-anchor baselines; every [BYTE]
  stage re-derives and compares.
- [ ] **Step 3: Behavior baseline on oracle.** Rebuild the SOUND+DEBUG variant (hash
  discipline!), load in oracle, run: boot → OJZ circuit → sound smoke (START toggles
  music; B cycles SFX 0-7; hotkeys need the `SOUND_DEBUG_HOTKEYS=1` build). Screenshot
  the running scene for reference.

### Task 2: Vectors + gameHeader + parameterized boot **[BEHAV]**

**Files:**
- Create: `engine/system/vectors.asm`, `engine/system/header.inc`, `games/sonic4/config/game.asm`
- Modify: `games/sonic4/main.asm` (lines 25-90 replaced; add config include after line 19), `engine/system/boot.asm:205-227`

- [ ] **Step 1: Create `engine/system/vectors.asm`** — main.asm lines 30-71 verbatim
  (the `__BUDGET_VECTORS`/`Vectors:` labels through the last `ErrorTrap` row). Header
  comment: engine-owned 64-vector table; every target is an engine symbol
  (`EntryPoint`, error vectors, `HBlank_Dispatch`, `VBlank_Handler`, `NullInterrupt`,
  `ErrorTrap`). NOTE: `NullInterrupt` (`rte`) does NOT move here — the org-0 image is
  pure data until $200; the routine stays where it is emitted today (main.asm:420) and
  joins the engine.inc epilogue in T7.
- [ ] **Step 2: Create `engine/system/header.inc`** with the `gameHeader` macro:

```asm
; gameHeader — emits the $100-$1FF Mega Drive ROM header from game-declared
; string symbols. Invoke immediately after the vectors include (org-0 image:
; $000-$0FF vectors, $100-$1FF header). Every field width-asserts at build
; time — a wrong-length string is a build error, not a corrupt header.
; The checksum word at $18E is emitted 0; tools/fixheader patches it.
; ROM start/end and RAM range are engine-owned (EndOfRom = engine epilogue label).
;
; Required game symbols (string, exact width):
;   GAME_CONSOLE(16) GAME_COPYRIGHT(16) GAME_TITLE_DOM(48) GAME_TITLE_OVS(48)
;   GAME_SERIAL(14) GAME_IO(16) GAME_SRAM(12) GAME_MEMO(52) GAME_REGION(16)
gameHeader macro
        if strlen(GAME_CONSOLE) <> 16
          fatal "GAME_CONSOLE must be exactly 16 chars"
        endif
        if strlen(GAME_COPYRIGHT) <> 16
          fatal "GAME_COPYRIGHT must be exactly 16 chars"
        endif
        if strlen(GAME_TITLE_DOM) <> 48
          fatal "GAME_TITLE_DOM must be exactly 48 chars"
        endif
        if strlen(GAME_TITLE_OVS) <> 48
          fatal "GAME_TITLE_OVS must be exactly 48 chars"
        endif
        if strlen(GAME_SERIAL) <> 14
          fatal "GAME_SERIAL must be exactly 14 chars"
        endif
        if strlen(GAME_IO) <> 16
          fatal "GAME_IO must be exactly 16 chars"
        endif
        if strlen(GAME_SRAM) <> 12
          fatal "GAME_SRAM must be exactly 12 chars"
        endif
        if strlen(GAME_MEMO) <> 52
          fatal "GAME_MEMO must be exactly 52 chars"
        endif
        if strlen(GAME_REGION) <> 16
          fatal "GAME_REGION must be exactly 16 chars"
        endif
        dc.b    GAME_CONSOLE                ; $100
        dc.b    GAME_COPYRIGHT              ; $110
        dc.b    GAME_TITLE_DOM              ; $120
        dc.b    GAME_TITLE_OVS              ; $150
        dc.b    GAME_SERIAL                 ; $180
Checksum:
        dc.w    0                           ; $18E — fixheader patches
        dc.b    GAME_IO                     ; $190
        dc.l    $00000000                   ; $1A0 ROM start
        dc.l    EndOfRom-1                  ; $1A4 ROM end
        dc.l    $00FF0000                   ; $1A8 RAM start
        dc.l    $00FFFFFF                   ; $1AC RAM end
        dc.b    GAME_SRAM                   ; $1B0
        dc.b    GAME_MEMO                   ; $1BC
        dc.b    GAME_REGION                 ; $1F0
    endm
```

- [ ] **Step 3: Create `games/sonic4/config/game.asm`** (the game contract file — grows
  in T3):

```asm
; Sonic 4 — game contract declarations consumed by the engine.
; (See engine/engine.inc header for the full contract list — T7.)

; --- ROM header fields (exact widths asserted by gameHeader) ---
GAME_CONSOLE    equ "SEGA GENESIS    "
GAME_COPYRIGHT  equ "(C)     2026.APR"
GAME_TITLE_DOM  equ "SONIC THE HEDGEHOG 4                            "
GAME_TITLE_OVS  equ "SONIC THE HEDGEHOG 4                            "
GAME_SERIAL     equ "GM S4-0001-00 "
GAME_IO         equ "J               "
GAME_SRAM       equ "            "
GAME_MEMO       equ "                                                    "
GAME_REGION     equ "JUE             "

; --- Boot handoff: the engine boot ends by entering the game here ---
Game_Entry      = GameState_OJZScroll_Init
GAME_ENTRY_ID   = GS_OJZ_SCROLL_TEST

; --- gameBootHook — engine boot invokes this after Sound_Init, before the
;     game-state handoff. May be empty. Sonic 4: sound test-harness ping +
;     autoplay (moved verbatim from engine/system/boot.asm).
gameBootHook macro
    ifdef SOUND_DRIVER_ENABLED
      ifdef SOUND_DEBUG_HOTKEYS
        moveq   #$3C, d0                 ; ping with a recognizable value
        bsr.w   Sound_Ping
        moveq   #SONG_MOVINGTRUCKS, d0   ; autoplay the test song
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w     ; track play state for the Start-toggle
      endif
    endif
    endm
```

  The exact strings above were lifted from main.asm:76-90 — verify by diff, not by eye.
- [ ] **Step 4: Rewire `games/sonic4/main.asm`.** After line 19 (`include "ram.asm"`),
  add `include "games/sonic4/config/game.asm"`. Replace lines 25-90 (org 0 through the
  region string) with:

```asm
    org 0
    include "engine/system/header.inc"
    include "engine/system/vectors.asm"
    gameHeader
```

- [ ] **Step 5: Parameterize `engine/system/boot.asm`.** Replace lines 205-227
  (the `ifdef SOUND_DRIVER_ENABLED` block + state handoff) with:

```asm
    ifdef SOUND_DRIVER_ENABLED
        ; Sound mailbox idle handshake. Z80 already has the bus and the
        ; driver is running; registers are free here (post-boot setup).
        bsr.w   Sound_Init
    endif
        gameBootHook                     ; game-supplied (may be empty)

        ; Set initial game state — the game supplies the entry contract:
        ;   Game_Entry    = the first game-state routine
        ;   GAME_ENTRY_ID = its game-state id
        move.l  #Game_Entry, (Game_State).w
        move.b  #GAME_ENTRY_ID, (Game_State_ID).w
        clr.b   (Game_State_Init).w
```

- [ ] **Step 6: Verify.** Build both variants. `cmp` the first 512 bytes of the
  SOUND+DEBUG `s4.bin` against the Task-1 baseline ROM (`cmp -n 512 s4.bin <baseline>`)
  — must be identical (vectors + header are byte-frozen). Full-ROM hash should ALSO
  match (the boot rewrite emits identical bytes when both flags are on — the moved
  instructions are verbatim); if it doesn't, diff `s4.lst` around `EntryPoint` and
  justify every delta before proceeding. Oracle: boot + circuit + sound smoke.
- [ ] **Step 7: Commit.**

```bash
git add engine/system/vectors.asm engine/system/header.inc games/sonic4/config/game.asm games/sonic4/main.asm engine/system/boot.asm
git commit -m "feat(engine): engine-owned vectors + gameHeader + parameterized boot (E1)"
```

### Task 3: The ten stray inversions **[BEHAV]**

Work through the coupling inventory items c-l. Each sub-step is independently
verifiable; build after each, commit once at the end (or per sub-step if convenient).

- [ ] **3.1 sine.bin →  engine.** `git mv games/sonic4/data/misc/sine.bin engine/data/sine.bin`
  (create `engine/data/`). Update `engine/system/math.asm:27` to
  `BINCLUDE "engine/data/sine.bin"`. Check nothing else references the old path:
  `grep -rn "misc/sine" --include='*.asm' --include='*.py' .` → only math.asm (fix any
  tool hit found).
- [ ] **3.2 Self-test vectors → engine.** Read `tools/gen_compression_vectors.py`; change
  its output dir from `games/sonic4/data/generated/test/` to
  `engine/debug/generated/` (it is NOT daemon-watched — only ojz_strip_gen.py is).
  Update `engine/debug/compression_selftest.asm:92` to
  `include "engine/debug/generated/vectors.asm"`. Mirror whatever gitignore treatment
  the old generated dir has (`git check-ignore games/sonic4/data/generated/test/vectors.asm`
  tells you; add an equivalent `.gitignore` rule for the new path). Run
  `./build.sh` (the generator runs inside it) and check the file lands in the new spot.
  If any pytest under `tools/` asserts the old path (`grep -rn "generated/test" tools/`),
  repoint it and run the tool tests.
- [ ] **3.3 Debug sound harness → game.** Create `games/sonic4/debug/game_debug.asm`;
  move `engine/system/game_loop.asm` lines 26-136 into it VERBATIM (the two nested
  `ifdef SOUND_DEBUG_HOTKEYS`/`ifdef SOUND_DRIVER_ENABLED` blocks containing
  `Debug_MusicToggle` + `Dbg_SfxIdTable`). In `game_loop.asm`, replace the call block
  (lines 12-16) with a single `gameDebugTick` macro invocation. Add to
  `games/sonic4/config/game.asm`:

```asm
; --- gameDebugTick — engine GameLoop invokes this once per frame after
;     VSync/SFX-drain. May be empty. Sonic 4: sound test-harness hotkeys.
gameDebugTick macro
    ifdef SOUND_DEBUG_HOTKEYS
      ifdef SOUND_DRIVER_ENABLED
        jsr     Debug_MusicToggle       ; (was bsr.w — jsr is placement-free)
      endif
    endif
    endm
```

  Include the new file from `games/sonic4/main.asm` in the engine-code region,
  immediately after the `player_sensors.asm` include (line 119) — co-locating ALL
  game-in-engine-block code at one slot so T7 needs exactly one hook there.
- [ ] **3.4 sfx_blob_win_tab → game data.**
  `git mv engine/sound/sfx_blob_win_tab.asm games/sonic4/data/sound/sfx_blob_win_tab.asm`;
  update the include at `games/sonic4/main.asm:294`. (It is transcoder-shaped game data —
  a table of game SFX-blob window pointers; engine-side was backwards.)
- [ ] **3.5 SFX_BLOB_BANK → game-declared.** Find where `sfx_bankid` is defined
  (`grep -rn "sfx_bankid" --include='*.asm' .` — expect `sound_constants.asm`). Delete
  `engine/sound/sound_sfx.asm:64` (`SFX_BLOB_BANK = sfx_bankid(Sfx_33)`) and add the same
  line to `games/sonic4/config/game.asm` under a `; --- sound contract ---` header,
  IF `sfx_bankid` is visible there (defined in the defs files included earlier). If it
  is not, put the declaration at the top of `games/sonic4/data/sound/sfx_table.asm`
  instead and note the placement in the config file's comment.
- [ ] **3.6 SFXID_SPINDASH → SFXID_REV_LOOP contract.** Read
  `engine/sound/sound_sfx.asm:690-715` (the spindash-rev special case around the
  `cp SFXID_SPINDASH` at :699). This is the LEGACY rev special case — distinct from
  the Stage-C `SHF_CONTINUOUS` mechanism nearby; touch only the `SFXID_SPINDASH`
  compare block. Replace `SFXID_SPINDASH` with `SFXID_REV_LOOP` and wrap
  the ENTIRE special-case compare-and-branch block in `if SFXID_REV_LOOP >= 0` /
  `endif` (assemble the feature out, not a runtime check — Z80 side). Add to
  `games/sonic4/config/game.asm`: `SFXID_REV_LOOP = SFXID_SPINDASH` (with comment:
  −1 = no rev-loop SFX; games without a spindash define −1).
- [ ] **3.7 Ring SFX contract.** No code change — `SFXID_RING_LEFT`/`SFXID_RING_RIGHT`
  stay referenced by `engine/sound/sound_api.asm` (the engine ring system's L/R
  alternation). Add them to the contract comment block in `config/game.asm` (they are
  defined in the SFXID block that T5 moves to `config/sound_ids.asm`); they join the T9
  gate allowlist.
- [ ] **3.8 Default pitch table contract.** In
  `games/sonic4/data/sound/movingtrucks_pitchtable.asm`, add directly above the
  `MovingTrucks_PitchTable:` label: `SndDefaultPitchTable:` (a second label on the same
  address; comment: engine contract — the bank head MUST define this inside the $8000
  window; `sound_fm.asm` falls back to it when a song's `pitchtable_ptr` is 0). Change
  `engine/sound/sound_fm.asm:668` to `ld hl, SndDefaultPitchTable` (keep the comment,
  updated). Byte-identical (same address, renamed reference).
- [ ] **3.9 Camera de-Sonicization.** In `engine/level/camera.asm`, wrap the jump-state
  landing-lock block — from the `move.b (Player_1+_pl_state).w, d2` at :180 through the
  `.land_lock` block's `bra.w .clamp_y` — in `if GAME_CAMERA_JUMP_LOCK` / `endif` so
  that with the flag 0 the code falls straight into `.down_ok`. Keep `.check_down:` and
  `.down_ok:` OUTSIDE the conditional. Add `GAME_CAMERA_JUMP_LOCK = 1` to
  `games/sonic4/config/game.asm` (comment: requires the game to define `_pl_state`,
  `PSTATE_JUMP`, `PSTATE_ROLLJUMP`; 0 = plain deadzone follow). Then rename
  `Camera_Spindash_Lag` → `Camera_Hold_Frames` everywhere
  (`grep -rn "Camera_Spindash_Lag" --include='*.asm' .` — expect `ram.asm`,
  `engine/level/camera.asm`, and the setter in `games/sonic4/player/player_spindash.asm`);
  update the comment to describe it generically ("frames the camera holds position;
  game code sets it, e.g. spindash charge"). RAM-symbol rename — no ROM bytes change.
- [ ] **3.10 Root test/ → game.** `mkdir games/sonic4/test`;
  `git mv test/object_test_state.asm test/ojz_scroll_test.asm games/sonic4/test/`.
  Move the rest of `test/`'s referenced files with them: first
  `grep -rn '"test/' --include='*.asm' .` to find every include/BINCLUDE of the old
  paths (main.asm:414-415 at minimum, plus any BINCLUDE inside the two state files);
  `git mv` whatever they reference (`title_art.s4lz`, `*.bin` as applicable) and fix all
  paths. Delete `test/` remnants that nothing references (the stray `.png`s can move
  wholesale — they're artifacts of this test scene).
- [ ] **3.11 Verify.** Both builds green. SOUND+DEBUG hash will differ from baseline
  (jsr-for-bsr, moved includes) — that is expected; this stage is [BEHAV]: oracle boot,
  full circuit, ALL sound hotkeys (START music toggle, B-cycle through all 8 SFX —
  the harness moved, this is the regression surface), spindash rev SFX specifically
  (3.6 touched its dispatch), spindash camera hold + jump camera behavior (3.9 touched
  camera paths — jump around and confirm the camera doesn't chase a rising jump).
- [ ] **3.12 Commit.**

```bash
git add -u
git add engine/data/sine.bin games/sonic4/debug/game_debug.asm games/sonic4/data/sound/sfx_blob_win_tab.asm games/sonic4/test/ engine/debug/generated/.gitignore
git commit -m "refactor(engine): invert all ten engine->game strays (E2) — sine, selftest vectors, debug harness, sfx table+bank, rev-loop/ring/pitch contracts, camera jump-lock gate, test/ relocation"
```

  (Check `git status` first — `git add -u` catches the moves/edits; enumerate any new
  file it misses. Verify the commit with `git show --stat HEAD`.)

### Task 4: soundBankHead contract **[BYTE]**

**Files:**
- Create: `engine/sound/sound_bank.inc`
- Modify: `games/sonic4/main.asm:283-308`, `games/sonic4/data/sound/movingtrucks_pitchtable.asm`

- [ ] **Step 1: Research.** Re-read `games/sonic4/main.asm:235-310` (the bank-head
  region — line numbers will have drifted slightly after T2/T3). Identify exactly:
  the `save`/`cpu z80`/`phase 08000h` bracket, the five includes inside it, the pitch
  table size assert (lines 288-290 pre-drift), and the NO-CODE comment block. The
  `SND_ENGINE_TABLE_BANK` equate and `MovingTrucks_Bank_Start` label stay game-side
  (they derive from the game's bank placement).
- [ ] **Step 2: Create `engine/sound/sound_bank.inc`:**

```asm
; soundBankHead — the engine-tables-at-bank-head contract.
;
; Every bank the Z80 sequencer RUNS A FRAME ON (any bank SND_SONG_BANK or
; SFX_BLOB_BANK can name) MUST invoke this macro FIRST inside its
;     align $8000  /  save  /  cpu z80  /  phase 08000h
; region. The reader labels emitted here are fixed $8000-window addresses —
; a frame on a bank without this head reads garbage pitch/volume/dispatch.
; Today exactly ONE such bank exists (songs + SFX blobs + tables co-located;
; asserted in the game's song_table.asm and SFX guards). A future second bank
; needs a label-free data-only twin of this head at its start (see
; DEFERRED_WORK "Bank-D DAC co-location hook" for the generator approach).
;
; NO CODE may be authored in the banked window — only DATA tables. Z80 opcode
; fetches from $8000-$FFFF traverse the 68k bus; 68k contention (VRAM DMA-from-
; ROM / BUSREQ) corrupts fetched opcodes -> wild PC -> Z80 self-reinit. Banked
; DATA reads tolerate contention (worst case a one-frame glitch); banked CODE
; fetches do not. All in-frame code lives in the resident blob.
;
; args:
;   pitchfile  — game include that must define SndDefaultPitchTable (the
;                fallback pitch table sound_fm.asm uses when a song's
;                pitchtable_ptr is 0), inside the window.
;   sfxtabfile — game include defining SfxBlobWinTab (the id->blob window-
;                pointer table both sound_sfx.asm readers use under
;                SetBank(SFX_BLOB_BANK)).
; The game must also define, game-side, at the bank start (BEFORE the phase
; bracket): a bank-start label and SND_ENGINE_TABLE_BANK = <label> >> 15.
soundBankHead macro pitchfile, sfxtabfile
        include "engine/sound/sound_tables_z80.asm"
        include pitchfile
        include sfxtabfile
        include "engine/sound/seq_opcode_tab.asm"
        include "engine/sound/dac_sample_tab.asm"
    endm
```

  The include ORDER is the current main.asm order exactly — byte-frozen.
- [ ] **Step 3: Move the pitch-table size assert.** Cut the
  `if (MovingTrucks_PitchTable_End - MovingTrucks_PitchTable) <> 2*PITCHTAB_COUNT`
  /`fatal`/`endif` from main.asm into
  `games/sonic4/data/sound/movingtrucks_pitchtable.asm` (at its end, after
  `MovingTrucks_PitchTable_End`). Asserts emit nothing — byte-safe.
- [ ] **Step 4: Rewire main.asm.** Add `include "engine/sound/sound_bank.inc"` in the
  defs region (after the macros include). Replace the five includes inside the phase
  bracket (and the assert moved in Step 3, and the big invariant comment blocks the
  macro now carries) with:

```asm
        save
        cpu     z80
        phase   08000h
        soundBankHead "games/sonic4/data/sound/movingtrucks_pitchtable.asm", "games/sonic4/data/sound/sfx_blob_win_tab.asm"
        dephase
        restore
```

  Keep game-side in main.asm: `MovingTrucks_Bank_Start:`, `SND_ENGINE_TABLE_BANK`, the
  `align $8000`, and everything after `restore` (songs, stream pitch table, patches,
  SFX blobs, guards) untouched.
- [ ] **Step 5: Verify byte-identical.** Rebuild SOUND+DEBUG variant, `md5sum s4.bin`
  vs the Task-3 post-commit hash of the same variant (rebuild that from the T3 commit
  if you didn't record it). MUST match exactly. Plain build green too.
- [ ] **Step 6: Commit.**

```bash
git add engine/sound/sound_bank.inc games/sonic4/main.asm games/sonic4/data/sound/movingtrucks_pitchtable.asm
git commit -m "feat(sound): soundBankHead — the engine-tables-at-bank-head contract formalized (E3)"
```

### Task 5: Def split **[BYTE-target, lst-diff fallback]**

**Files:**
- Create: `engine/constants.asm`, `engine/sound_constants.asm`, `games/sonic4/config/constants.asm`, `games/sonic4/config/sound_ids.asm`
- Move: `structs.asm` → `engine/structs.asm`, `macros.asm` → `engine/macros.asm`
- Delete: root `constants.asm`, root `sound_constants.asm`
- Modify: `games/sonic4/main.asm:14-17`

- [ ] **Step 1: Classify.** Root `constants.asm` is 550 lines. The game slice (verified
  2026-07-07 — re-verify each, lines may have drifted):
  - `GS_OBJECT_TEST` (:213), `GS_OJZ_SCROLL_TEST` (:432) — game state ids.
    `GS_BOOT`/`GS_IDLE` (:112-113) stay ENGINE (boot/dispatch core).
  - `ANIM_RUN_THRESHOLD`, `SPINDASH_BASE/CHARGE_STEP/CHARGE_MAX` (:249-253).
  - The `PSTATE_*` block + its ordering assert (:271-281) and the `ANIM_*` block
    (:286-297) — player state/animation rows.
  - `VRAM_TEST_OBJ` (:535), `VRAM_TEST_SONIC` (:547) and their neighbors in the test
    region; **`VRAM_RING_PLACEHOLDER` (:538) moves WITH them but is an engine-consumed
    CONTRACT constant** (DrawRings uses it) — mark it as such in the comment and add it
    to the T9 allowlist.
  - Test scaffold values: `STUB_FLOOR_Y`, `ENEMY_PATROL_SPEED` (grep for them).
  - Ring-system SIZING (`MAX_RING_BUFFER`, `RING_BUFFER_ENTRY_SIZE`, `RING_WIDTH`,
    :439-441, plus the `COLLECTED_*` sizing family nearby) — game-tunable capacity;
    the ring CODE and the `COLLISION_*` enum stay engine.
  For each candidate, decide by the rule: **referenced by engine code ⇒ engine (or
  contract); referenced only by game code/data ⇒ game.** Check with
  `grep -rn "<SYM>" engine/` before moving anything. Record the final line-level list
  in the scratchpad BEFORE cutting.
  Also check `structs.asm` for game structures before moving it wholesale:
  `grep -n "PlayerV\|Player\|Sonic" structs.asm` — if the player SST overlay struct
  (`PlayerV_*`) lives there, split it out to `games/sonic4/config/constants.asm` too
  (the SST core struct is engine; the player overlay is game).
- [ ] **Step 2: Check tool readers.** `grep -rn "constants.asm\|sound_constants.asm\|structs.asm\|macros.asm" tools/ .github 2>/dev/null` —
  s4lint/s4budget/pytest may parse these by path. Repoint every hit to the new paths.
- [ ] **Step 3: Cut.** `git mv structs.asm engine/structs.asm`,
  `git mv macros.asm engine/macros.asm`. Create `engine/constants.asm` (root file minus
  the game slice) + `games/sonic4/config/constants.asm` (the game slice, in original
  relative order, with a header comment naming the file's role); same for
  `engine/sound_constants.asm` + `games/sonic4/config/sound_ids.asm` (the game slice of
  sound_constants.asm is the `SFXID_*` block, :770-778, AND the `SFXPRI_*` priority
  ladder INCLUDING its 7-bit guard assert, :799-812 (added by package 2) — move them
  together; the guard protects the engine's bit-7 non-latching flag, so keep the assert
  with the values. `SONG_*` ids already live game-side in `song_table.asm`. The
  `SfxHeader` struct (:875+) and `SHF_*` flags are driver format — ENGINE. Also repoint
  the mirror comments in `tools/sfx_transcode.py` (:16, :76 — "mirrors
  sound_constants.asm SFXPRI_*") to the new config path. Delete the root files. Update main.asm's defs
  prologue to:

```asm
    include "engine/constants.asm"
    include "engine/sound_constants.asm"
    include "engine/structs.asm"
    include "engine/macros.asm"
    include "engine/parallax_macros.inc"
    include "engine/sound/sound_bank.inc"
    include "games/sonic4/config/constants.asm"
    include "games/sonic4/config/sound_ids.asm"
    include "games/sonic4/config/game.asm"
    include "ram.asm"
    include "engine/debug/debugger.asm"
```

  (Engine defs first, ALL game config after, ram last-but-debugger — this is the final
  engine.inc order, established now. AS resolves forward equate references across
  passes; if assembly diverges (warning #80 loop), a game symbol is consumed in an
  order-dependent way — find it and leave THAT symbol engine-side with a comment.)
- [ ] **Step 4: Verify.** Rebuild SOUND+DEBUG; target byte-identical hash. Pure def
  relocation SHOULD be byte-identical; if the hash moves, diff `s4.lst` against the
  previous stage's listing and prove every delta is file/line metadata only — any
  value/address delta is a bug. For each game-slice symbol moved, confirm
  `grep -rln "<SYM>" engine/` is empty (or contract-listed). Plain build green. Tool
  tests green if Step 2 touched any.
- [ ] **Step 5: Commit.**

```bash
git add engine/constants.asm engine/sound_constants.asm engine/structs.asm engine/macros.asm games/sonic4/config/constants.asm games/sonic4/config/sound_ids.asm games/sonic4/main.asm
git rm constants.asm sound_constants.asm
git commit -m "refactor: engine/game def split — constants, sound ids, structs, macros under engine/ (E4)"
```

  (Plus any tool files from Step 2 — enumerate exactly.)

### Task 6: RAM split **[BEHAV + MANDATORY oracle runtime verify]**

**Files:**
- Create: `engine/ram.asm`, `games/sonic4/config/ram.asm`
- Delete: root `ram.asm`
- Modify: `games/sonic4/main.asm` defs prologue

- [ ] **Step 1: Research.** Read root `ram.asm` in full (478 lines). It has TWO phase
  regions: `phase $FFFF0000` (:10-43) and `phase $FFFF8000` (:48 onward, the
  `.w`-addressable block) plus a trailing guard/alignment note (:414-420). The game
  slice (verified 2026-07-07; re-verify):
  - `Dbg_Music_On`, `Dbg_Sfx_Sel` (:208-209 — inside a DEBUG ifdef among the engine
    `Prof_*` vars; the `Prof_*` profiler vars stay ENGINE).
  - The Player physics/state block (:276-295): `Player_Phys` .. `Player_Phys_End`,
    `Player_Quadrant`, `Player_JumpBuffer`, `Player_Death_Pending`.
  - The player history rings (:415-431): `Player_Pos_Ring`, `Player_Stat_Ring`,
    `Player_Ring_Index` **and their 256-alignment assert** — see Step 2.
  - `Player_1`/`Player_2` SST slots (:218-219) STAY ENGINE — they are the object
    system's reserved tracked-entity slots (engine camera/rings/collision address them).
    Add that sentence as a comment above them.
  - `Ring_*` buffers/counters, `Ring_Sfx_Speaker`, `Sfx_Ring_*`, `Sound_Dbg_Mirror`
    stay ENGINE (engine ring system + sound API + engine sound debug).
  Confirm each candidate with `grep -rln "<SYM>" engine/` (engine hit ⇒ stays engine).
- [ ] **Step 2: Split.** `engine/ram.asm` = root file minus the game slice; at the end
  of its `$FFFF8000` phase block (BEFORE its overflow guard), add:

```asm
; -----------------------------------------------
; Engine RAM ends here — game RAM continues from Engine_RAM_End
; (games/<game>/config/ram.asm phases from this address).
; -----------------------------------------------
Engine_RAM_End:
```

  Keep the engine file's `dephase` + guard structure intact (the guard now checks the
  ENGINE region; copy its existing form). Create `games/sonic4/config/ram.asm`:

```asm
; Sonic 4 game RAM — phased continuation from Engine_RAM_End.
; RULES (the AS alignment lesson): AS does NOT auto-align ds.w/ds.l — every
; block must end even; an odd ds.b run address-errors the next word field at
; RUNTIME with a green build. Oracle runtime boot-verify is mandatory after
; any change here.
        phase Engine_RAM_End

    ifdef __DEBUG__
Dbg_Music_On:           ds.w 1          ; (moved from engine ram — game debug harness)
Dbg_Sfx_Sel:            ds.w 1
    endif

; --- Player physics/state (moved verbatim from root ram.asm §5 block) ---
        ; <the Player_Phys .. Player_Death_Pending block, verbatim,
        ;  including its comments and any trailing even-pad>

; --- Player history rings — Player_Pos_Ring REQUIRES 256-byte alignment ---
        align 256                       ; low-byte index wrap needs a 256 boundary
        ; <the Player_Pos_Ring / Player_Stat_Ring / Player_Ring_Index block,
        ;  verbatim, KEEPING its existing alignment assert>

Game_RAM_End:
        if Game_RAM_End > SYSTEM_STACK_FLOOR_OR_EXISTING_GUARD_LIMIT
          fatal "game RAM overflows"
        endif
        dephase
```

  Replace the guard's limit symbol with whatever the root file's trailing guard
  actually checks against (read it — likely the stack base / $FFFFxxxx ceiling); use
  the SAME limit. Copy the moved blocks verbatim — comments included. Delete root
  `ram.asm`. Update main.asm: `include "engine/ram.asm"` then
  `include "games/sonic4/config/ram.asm"` (game config constants are already included
  before ram — ring sizing feeds engine ram).
- [ ] **Step 3: Verify — runtime, not just build.** Both builds green. Then oracle,
  MANDATORY: boot (watch for address-error black screens), full circuit (spindash,
  jump, rings collect — ring counter increments, ring SFX alternates L/R), sound smoke,
  and spot-check via `s4.lst`: eyeball the new RAM map against the old listing —
  `Engine_RAM_End` present, game vars phased after it, `Player_Pos_Ring` at a
  256-aligned address, every engine symbol that FOLLOWED the removed game blocks now
  shifted but even-aligned. Verify `Dbg_Music_On` still works (START music toggle) —
  it moved files.
- [ ] **Step 4: Commit.**

```bash
git add engine/ram.asm games/sonic4/config/ram.asm games/sonic4/main.asm
git rm ram.asm
git commit -m "refactor: engine/game RAM split — Engine_RAM_End seam, player state game-side (E5)"
```

### Task 7: engine.inc + the manifest **[BYTE]**

The include-reshuffle. After T2-T6, `games/sonic4/main.asm` is already ordered exactly
as engine.inc wants — this task moves the engine-owned scaffolding into
`engine/engine.inc` and shrinks main.asm to the manifest. Byte-identical because every
include lands in the same order.

**Files:**
- Create: `engine/engine.inc`
- Rewrite: `games/sonic4/main.asm`
- Modify: `games/sonic4/config/game.asm` (gains the module-list macros)

- [ ] **Step 1: Create `engine/engine.inc`.** Contract header + the full orchestration.
  The body is main.asm's current content with every game include replaced by a macro
  invocation:

```asm
; engine.inc — the single entry point for a game built on Aeon.
;
; A game manifest (games/<game>/main.asm) must, BEFORE including this file:
;   1. define PAD_TO_POWER_OF_TWO (0/1)
;   2. define the required macros (may be empty unless noted):
;        gameConfigIncludes       — game constants / sound ids / game.asm contract file
;        gameRamIncludes          — game RAM continuation (phases from Engine_RAM_End)
;        gameEngineBlockIncludes  — game code that must live in the engine block
;                                   (no code_addr entry points; e.g. player sensors)
;        gameObjectBankIncludes   — object-bank code (org $10000, objroutine targets)
;        gameDataIncludes         — game data: parallax, objdefs, levels, mappings,
;                                   collision binaries, animations, game states
;        gameSoundDataIncludes    — song/SFX banks (only assembled when
;                                   SOUND_DRIVER_ENABLED; must follow the
;                                   soundBankHead contract — see sound_bank.inc)
;   (gameBootHook and gameDebugTick are defined in the game's contract file,
;    which gameConfigIncludes pulls in.)
;
; Contract symbols the game's config must define (consumed by engine code):
;   Game_Entry, GAME_ENTRY_ID          — boot handoff (engine/system/boot.asm)
;   GAME_CAMERA_JUMP_LOCK              — 1 needs _pl_state/PSTATE_JUMP/PSTATE_ROLLJUMP
;   GAME_* header strings              — see engine/system/header.inc
;   VRAM_RING_PLACEHOLDER              — ring art tile (engine DrawRings)
;   with SOUND_DRIVER_ENABLED also:
;     SFXID_REV_LOOP (-1 = off), SFXID_RING_LEFT/RIGHT, SFX_BLOB_BANK,
;     SND_ENGINE_TABLE_BANK, SndDefaultPitchTable + SfxBlobWinTab (bank head),
;     SongTable/SfxTable (+ song data) per the sound driver's data contract.

    cpu 68000
    padding off
    supmode on

; --- definitions (no ROM output) ---
    include "engine/constants.asm"
    include "engine/sound_constants.asm"
    include "engine/structs.asm"
    include "engine/macros.asm"
    include "engine/parallax_macros.inc"
    include "engine/sound/sound_bank.inc"
    gameConfigIncludes
    include "engine/ram.asm"
    gameRamIncludes
    include "engine/debug/debugger.asm"

; --- ROM image: org-0 = engine vectors + game header ---
    org 0
    include "engine/system/header.inc"
    include "engine/system/vectors.asm"
    gameHeader

; --- engine code block ---
__BUDGET_ENGINE:
    include "engine/system/boot.asm"
    ; ... (main.asm's engine include list :96-118 VERBATIM) ...
    include "engine/level/collision_lookup.asm"
    gameEngineBlockIncludes
    include "engine/level/section.asm"
    ; ... (rest of the engine list :120-134 VERBATIM, incl. the
    ;      SOUND_DRIVER_ENABLED / __DEBUG__ conditional includes) ...

; --- object code bank (64KB, objroutine-addressed) ---
    org $10000
ObjCodeBase:
    rts                         ; offset 0 = empty slot safety net
__BUDGET_OBJBANK:
    gameObjectBankIncludes
    if * > $20000
      error "Object code bank overflows 64KB by \{*-$20000} bytes"
    endif

; --- game data ---
__BUDGET_DATA:
    gameDataIncludes

; --- sound data banks ---
    ifdef SOUND_DRIVER_ENABLED
    gameSoundDataIncludes
    endif

; --- epilogue ---
NullInterrupt:
    rte

    include "engine/debug/error_handler.asm"

EndOfRom:
    align 2
    if (EndOfRom & 1) <> 0
      error "ROM size is odd"
    endif
    if EndOfRom > $3FFFFF
      error "ROM exceeds 4MB without banking"
    endif
    if PLANE_H_CELLS * PLANE_V_CELLS > 4096
      error "Plane exceeds 8KB"
    endif
```

  Copy the elided include runs from the CURRENT main.asm verbatim — do not retype from
  this plan. `gameEngineBlockIncludes` sits exactly where `player_sensors.asm` +
  `game_debug.asm` sit today (between collision_lookup and section).
- [ ] **Step 2: Rewrite `games/sonic4/main.asm`** as the manifest:

```asm
; Sonic 4 — game manifest. The engine owns the ROM layout (engine/engine.inc);
; this file declares the game's config, module lists, and data.

PAD_TO_POWER_OF_TWO     = 1

gameConfigIncludes macro
    include "games/sonic4/config/constants.asm"
    include "games/sonic4/config/sound_ids.asm"
    include "games/sonic4/config/game.asm"
    endm

gameRamIncludes macro
    include "games/sonic4/config/ram.asm"
    endm

gameEngineBlockIncludes macro
    include "games/sonic4/player/player_sensors.asm"
    include "games/sonic4/debug/game_debug.asm"
    endm

gameObjectBankIncludes macro
    ; player_common first — it defines the overlay equates the state files use
    include "games/sonic4/player/player_common.asm"
    ; ... (the object-bank include list from old main.asm :153-168, verbatim) ...
    endm

gameDataIncludes macro
    ; ... (old main.asm :178-233 verbatim: parallax, objdefs, entity/act data,
    ;      mappings, animations, collision BINCLUDEs + guards, Sonic art) ...
    ; game states
    include "games/sonic4/test/object_test_state.asm"
    include "games/sonic4/test/ojz_scroll_test.asm"
    endm

gameSoundDataIncludes macro
    ; ... (old main.asm :240-409 verbatim: dac_samples, the MT bank with
    ;      soundBankHead, songs, patches, sfx blobs, guards) ...
    endm

    include "engine/engine.inc"
    END
```

  Every `; ...` is a verbatim block CUT from the pre-rewrite main.asm — build the new
  file by moving lines, not retyping. Multi-line conditionals (`ifdef __DEBUG__` song
  blocks, the SFX guards) move inside the macros unchanged.
- [ ] **Step 3: Verify byte-identical.** Rebuild SOUND+DEBUG → hash MUST equal the
  Task-6 hash. Plain build green (and hash equal to T6 plain). If AS chokes on any
  include-inside-macro edge case, fix the mechanism (e.g. hoist that one file) and
  document it in engine.inc — do NOT abandon byte-identity.
- [ ] **Step 4: Oracle boot + short circuit** (cheap insurance on top of the hash).
- [ ] **Step 5: Commit.**

```bash
git add engine/engine.inc games/sonic4/main.asm games/sonic4/config/game.asm
git commit -m "feat(engine): engine.inc — the engine owns the ROM layout; sonic4 main.asm becomes the manifest"
```

### Task 8: Build gating + games/demo **[sonic4 BYTE; demo = new artifact]**

**⚠ Generator coordination:** sonic4 generator PATHS stay unchanged — only the
invocations move into `games/sonic4/prebuild.sh`. Do not touch `tools/ojz_strip_gen.py`.

**Files:**
- Create: `games/sonic4/prebuild.sh`, `games/demo/main.asm`,
  `games/demo/config/{game.asm,constants.asm,ram.asm}`,
  `games/demo/objects/demo_box.asm`, `games/demo/data/demo_data.asm`,
  `games/demo/demo_state.asm`
- Modify: `build.sh`

- [ ] **Step 1: Extract prebuild.** Create `games/sonic4/prebuild.sh` containing
  build.sh's game-generator block VERBATIM (currently :72-146 **minus** the salvador
  bootstrap :64-70, `gen_compression_vectors.py` :142-143, and the lint block — those
  stay core):

```bash
#!/bin/bash
# sonic4 prebuild — game content generators. Invoked by build.sh from repo root.
set -euo pipefail
TOOLS="${TOOLS:-tools}"
# ... (the import_sk_collision / ojz_strip_gen / inject_editor_bg / art-pool
#      compression + pool-include emission / ojz_block_gen / sfx_transcode
#      block, moved verbatim from build.sh) ...
```

  `chmod +x games/sonic4/prebuild.sh`. In `build.sh`, replace the moved block with:

```bash
if [[ -x "games/${GAME}/prebuild.sh" ]]; then
    "games/${GAME}/prebuild.sh"
fi

echo "Generating compression self-test vectors..."
python3 "${TOOLS}/gen_compression_vectors.py"
```

  (Keep the salvador bootstrap BEFORE the prebuild invocation — sonic4's prebuild uses
  it. Keep lint after, running on `${MAIN_ASM}` as today.)
  Verify: `./build.sh` (sonic4) output byte-identical to Task 7.
- [ ] **Step 2: Author the demo.** Six small files.

  `games/demo/config/constants.asm`:

```asm
; demo game constants
GS_DEMO                 = 2             ; entry state id (0/1 = engine GS_BOOT/GS_IDLE)
VRAM_DEMO_OBJ           = $03E0        ; demo box art (4 tiles) — free tile region
VRAM_RING_PLACEHOLDER   = VRAM_DEMO_OBJ+4 ; engine contract (DrawRings) — unused here,
                                        ; points at a blank tile
```

  `games/demo/config/game.asm`:

```asm
; demo — game contract declarations (see engine/engine.inc header)
GAME_CONSOLE    equ "SEGA GENESIS    "
GAME_COPYRIGHT  equ "(C)     2026.JUL"
GAME_TITLE_DOM  equ "AEON ENGINE DEMO                                "
GAME_TITLE_OVS  equ "AEON ENGINE DEMO                                "
GAME_SERIAL     equ "GM DEMO-000-00"
GAME_IO         equ "J               "
GAME_SRAM       equ "            "
GAME_MEMO       equ "                                                    "
GAME_REGION     equ "JUE             "

Game_Entry              = GameState_Demo_Init
GAME_ENTRY_ID           = GS_DEMO
GAME_CAMERA_JUMP_LOCK   = 0             ; no player states in the demo

gameBootHook macro
    endm
gameDebugTick macro
    endm
```

  (Count the header string widths CHARACTER BY CHARACTER against the asserts —
  titles 48, serial 14. The gameHeader fatals catch mistakes at build time.)

  `games/demo/config/ram.asm`:

```asm
; demo game RAM — nothing yet. TODO: your game's variables start here.
        phase Engine_RAM_End
Game_RAM_End:
        dephase
```

  (Copy the guard form from `games/sonic4/config/ram.asm` if it has one.)

  `games/demo/objects/demo_box.asm`:

```asm
; Demo object — static display (the engine-boots-without-Sonic proof)
DemoBox_Main:
        jmp     Draw_Sprite
```

  `games/demo/data/demo_data.asm`:

```asm
; Demo data — objdef, mapping, art, palette. TODO: your game's data starts here.
ObjDef_DemoBox:
        objdef code=DemoBox_Main, map=Map_DemoBox, art=vram_art(VRAM_DEMO_OBJ,0,0)

Map_DemoBox:
        dc.w    Map_DemoBox_F0 - Map_DemoBox
Map_DemoBox_F0:
        dc.b    -8, 8, -8, 8                    ; extents
        dc.w    1                               ; 1 piece
        dc.w    -8                              ; Y offset
        dc.b    sprSize(2,2)>>8, 0              ; 16x16
        dc.w    0                               ; tile 0
        dc.w    -8                              ; X offset

DemoArt:                                        ; 4 tiles, solid color 1
        rept 4
        dc.l    $11111111, $11111111, $11111111, $11111111
        dc.l    $11111111, $11111111, $11111111, $11111111
        endr
        rept 8                                  ; +1 blank tile (ring placeholder slot)
        dc.l    0
        endr
DemoArt_End:

DemoPalette:                                    ; 16 colors: backdrop, white box
        dc.w    $0622, $0EEE, $0000, $0000, $0000, $0000, $0000, $0000
        dc.w    $0000, $0000, $0000, $0000, $0000, $0000, $0000, $0000
```

  `games/demo/demo_state.asm` (modeled on `games/sonic4/test/object_test_state.asm`,
  trimmed):

```asm
; GameState_Demo_Init — one-shot setup: palette, art, one object.
GameState_Demo_Init:
        lea     DemoPalette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #32/4-1, d0
.copy_pal:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_pal
        move.b  #$0F, (Palette_Dirty).w

        move.l  #DemoArt, d1
        move.w  #vram_bytes(VRAM_DEMO_OBJ), d2
        move.w  #DemoArt_End-DemoArt, d3
        jsr     QueueDMA_Critical

        jsr     InitObjectRAM
        jsr     Init_SpriteTable
        move.l  #0, (Camera_X).w
        move.l  #0, (Camera_Y).w

        lea     DemoObjectList(pc), a0
        jsr     Load_ObjectList
        ; TODO: your game starts here — spawn objects, load level data, add states

        setVDPReg VDP_Shadow_vdp_mode2, #$74    ; display on

        move.l  #GameState_Demo, (Game_State).w
        rts

; GameState_Demo — per-frame: run + render the object system.
GameState_Demo:
        jsr     InitSpriteSystem
        jsr     RunObjects
        jsr     TouchResponse
        jsr     Render_Sprites
        rts

DemoObjectList:
        dc.l    ObjDef_DemoBox
        dc.w    160, 112, 0                     ; screen center
        dc.l    0                               ; end
```

  `games/demo/main.asm`:

```asm
; Aeon engine demo — the minimal game. Proof the engine boots without Sonic 4,
; and the "start here" template for a new game.
;
; KNOWN LIMITATION (v1): build WITHOUT SOUND_DRIVER_ENABLED — the sound driver's
; data contract (song banks, SFX blobs, bank-head tables) has no demo content
; yet. TODO: a demo sound bank via the soundBankHead contract.

PAD_TO_POWER_OF_TWO     = 1

gameConfigIncludes macro
    include "games/demo/config/constants.asm"
    include "games/demo/config/game.asm"
    endm

gameRamIncludes macro
    include "games/demo/config/ram.asm"
    endm

gameEngineBlockIncludes macro
    endm

gameObjectBankIncludes macro
    include "games/demo/objects/demo_box.asm"
    endm

gameDataIncludes macro
    include "games/demo/data/demo_data.asm"
    include "games/demo/demo_state.asm"
    endm

gameSoundDataIncludes macro
    endm

    include "engine/engine.inc"
    END
```

- [ ] **Step 3: First demo build — expect a punch list.** `DEBUG=1 ./build.sh demo` →
  `demo.bin`. Work through undefined symbols one at a time; each is either (a) a
  missed game-slice constant the demo must define (add to `games/demo/config/constants.asm`
  with a comment), or (b) an engine→game reference T2-T5 missed — if (b), fix it as a
  T3-style inversion IN THE ENGINE (contract constant or gate), rebuild sonic4, confirm
  sonic4 still hashes/behaves, and note it in the commit message. Do NOT stub engine
  code demo-side. If the engine block references `player_sensors` symbols outside the
  hook (it shouldn't — it's included via the hook), that's category (b).
  Plain sonic4 `./build.sh` must stay byte-identical throughout.
- [ ] **Step 4: Verify demo on oracle.** Load `demo.bin` (controller, foreground):
  boots, backdrop color visible, the white 16×16 box renders at screen center.
  Screenshot saved. Then rebuild + reverify sonic4 (both variants, hash + quick boot).
- [ ] **Step 5: Commit.**

```bash
git add build.sh games/sonic4/prebuild.sh games/demo/
git commit -m "feat: games/demo — the engine boots without Sonic (E6); per-game prebuild hook"
```

### Task 9: The gate, docs, merge

- [ ] **Step 1: The grep gate.**

```bash
grep -rnE "SONG_|SFXID_|OJZ|GS_OJZ|Sonic|sonic4|games/" engine/ --include='*.asm' --include='*.inc'
```

  Every hit must be (a) a comment, or (b) one of the documented CONTRACT symbols:
  `SFXID_REV_LOOP`, `SFXID_RING_LEFT`, `SFXID_RING_RIGHT` (plus `Game_Entry`,
  `GAME_ENTRY_ID`, `GAME_CAMERA_JUMP_LOCK`, `SndDefaultPitchTable`, `SFX_BLOB_BANK`,
  `SND_ENGINE_TABLE_BANK`, `VRAM_RING_PLACEHOLDER`, `SongTable`, `SfxTable`,
  `SfxBlobWinTab`, the `gameBootHook`/`gameDebugTick`/`game*Includes` macro names, and
  `GAME_*` header symbols). Fix any straggler as a T3-style inversion. Record the final
  gate output in the commit message body.
- [ ] **Step 2: Full verification sweep.** sonic4 both variants green + BEHAV suite on
  oracle (boot, circuit, all sound hotkeys); `demo.bin` boots + renders; tool pytest
  suite green (`cd tools && python -m pytest` or the repo's documented invocation).
- [ ] **Step 3: Docs.**
  - `docs/ENGINE_ARCHITECTURE.md`: new "Engine/game contract" section — engine.inc
    layout contract, the required macros/symbols table (copy from engine.inc's header),
    gameHeader, Game_Entry, soundBankHead, the prebuild hook, games/demo as the
    agnosticism regression.
  - `CLAUDE.md` (aeon): REMOVE the "Deferred (its own design pass)" paragraph; update
    the repo-layout section (defs now under `engine/` + `games/sonic4/config/`,
    `engine/engine.inc`, `games/demo/`, root `test/` gone); update the build section
    (`./build.sh demo`).
  - `docs/superpowers/specs/2026-06-28-aeon-engine-game-restructure-design.md`: status
    → SHIPPED IN FULL (Tasks 3-6 via the 2026-07-02 design, executed 2026-07-xx).
  - `docs/superpowers/specs/2026-07-02-engine-game-split-design.md`: status line → note
    executed per THIS plan, with the spec-deltas list (this plan's header) referenced.
  - `docs/superpowers/2026-07-02-design-week-queue.md` log + `docs/superpowers/2026-07-03-sound-banking-queue.md`:
    add a path-migration note — **all banked-but-unexecuted plans citing
    `constants.asm`, `sound_constants.asm`, `structs.asm`, `macros.asm`, `ram.asm`,
    root `test/`, or `engine/system/game_loop.asm`'s debug harness must rebase those
    paths mechanically** (the "whichever executes first wins" rule those plans carry).
  - `docs/DEFERRED_WORK.md`: close/annotate any entries owned by this split; add one
    entry: "demo sound bank via soundBankHead (v1 demo builds without sound)".
- [ ] **Step 4: Merge.**

```bash
git checkout master && git merge --no-ff feat/engine-game-split
SOUND_DRIVER_ENABLED=1 SOUND_DEBUG_HOTKEYS=1 DEBUG=1 ./build.sh && ./build.sh && DEBUG=1 ./build.sh demo
```

  All three green on master. Do not push (user pushes).

---

## Self-review (done at write time, 2026-07-07)

- **Spec coverage:** §2.1-2.2 → T2; §2.3 → T4 + T3.4/3.5/3.6 (fm_patches item replaced
  by delta #1/#2 → T3.8); §2.4 → T3.1/3.2/3.3 + hook in T7 (sine, vectors, debug
  harness, engine-block hook); §3 → T7; §4 → T5/T6; §5 → T8; §6 → stage tags + T9.
  Additions beyond spec: T3.7 (ring ids), T3.9 (camera gate + rename), T3.10 (test/),
  delta #5 (VRAM_RING_PLACEHOLDER) — all justified by the 2026-07-07 coupling grep.
- **Placeholders:** the `; ...` blocks in T7/T8 Step 1 are verbatim-move instructions
  pointing at exact current line ranges, not TBDs. T8 Step 3 is an explicit
  expect-and-resolve loop with a decision rule, not "handle errors".
- **Consistency:** `gameHeader`, `Game_Entry`/`GAME_ENTRY_ID`, `gameBootHook`,
  `gameDebugTick`, `gameConfigIncludes`/`gameRamIncludes`/`gameEngineBlockIncludes`/
  `gameObjectBankIncludes`/`gameDataIncludes`/`gameSoundDataIncludes`, `soundBankHead`,
  `SndDefaultPitchTable`, `SFXID_REV_LOOP`, `GAME_CAMERA_JUMP_LOCK`,
  `Camera_Hold_Frames`, `Engine_RAM_End`, `VRAM_RING_PLACEHOLDER` used uniformly
  across tasks and the T9 allowlist.
