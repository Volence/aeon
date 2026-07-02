# Engine/Game Agnostic Split — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02)
**Extends:** `2026-06-28-aeon-engine-game-restructure-design.md` (directory wall
SHIPPED; this designs its deferred Tasks 3–6 around the ROM-layout realities that
blocked the naive split). One stale-doc fix: that doc names `sound_banked_z80.asm`,
which no longer exists (folded into the resident blob).
**Design-week queue:** #5 of 5 (+#6 added)

---

## 1. Goal

Make the engine/game wall real: `engine/` contains zero game symbols, a game is a
manifest + content, and `games/demo/` (a ~30-line game) builds and boots — the
permanent proof + template. Sonic 4's behavior and `s4.bin` are unchanged.

Precedent basis: SGDK (the shipped proof — engine owns all 64 vectors + everything
before/after one game-supplied `main`; the game's ROM header rides in as a pure
data artifact inside the engine-owned org-0 image), S.C.E. (assembly-native
manifest: engine owns the top-level include; the game plugs in through fixed
pointer-table files), plutiedev header-field ownership (game: title/serial/region/
SRAM/ROM-end; engine: vectors/entry/checksum convention). Treasure's "shared
engine" is copy-forward conventions, not a boundary — not a model.

## 2. The four seams (from the 2026-07-02 coupling map)

### 2.1 org-0: engine vectors + game header macro
`engine/system/vectors.asm` owns the 64-vector table + `NullInterrupt` (moves from
main.asm:25–71, 389–390). The game supplies header data via a **`gameHeader`
macro** (engine-defined, game-invoked with named params: domestic/overseas title,
serial, region, IO, SRAM declaration, checksum span uses the engine `EndOfRom`).
`engine.inc` assembles org-0 as: vectors → the game's header invocation. The
header is data; the game never touches a vector. (SGDK's rom_header.c pattern,
expressed as an AS macro since we are one assembly unit, not a linker.)

### 2.2 Parameterized boot
`boot.asm:224-225`'s hardcoded `GameState_OJZScroll_Init`/`GS_OJZ_SCROLL_TEST`
become the contract: the game defines `Game_Entry` (initial state routine) and
`GAME_ENTRY_ID` (its GS id); boot writes those. The DEBUG boot-song ping
(boot.asm:217) keys off game-declared `GAME_BOOT_SONG` (games without one define
`GAME_BOOT_SONG = -1` → no ping). `BootData_VDPRegs` stays engine-owned (the
baseline VDP config; a game wanting different plane setup does it in `Game_Entry`
— no config table until a game needs one). `SOUND_DRIVER_ENABLED` remains the
model flag.

### 2.3 The sound-bank head contract
The Z80 song bank's engine-tables-at-head invariant (main.asm:258-285) becomes a
named contract instead of an include-order accident:
- Engine provides **`soundBankHead`** — a macro a game's song-bank file MUST
  invoke first inside its `align $8000` + `phase 08000h` region; it emits
  `engine/sound/sound_tables_z80.asm`. The macro carries the invariant's
  documentation (window-relative labels; every song co-located reuses the tables;
  NO CODE in the banked window).
- **`sfx_blob_win_tab.asm` is reclassified game-side**: it is a table of game
  SFX-blob pointers (engine file referencing game labels today — backwards). It
  moves to `games/sonic4/data/sound/` (it is transcoder-generated data). The
  engine consumes it via the manifest.
- **`SFX_BLOB_BANK`** (engine `sound_sfx.asm:63` deriving a constant from a game
  label) becomes a game-declared constant in the game's sound config.
- The one engine code reference to a game SFX id (`sound_sfx.asm:677`
  `SFXID_SPINDASH` spindash-rev special case) becomes a game-declared
  `SFXID_REV_LOOP` contract constant (games without one: -1 = feature off).

### 2.4 Inverted includes + strays
- `engine/system/math.asm:27` sine BINCLUDE: `sine.bin` is engine substrate →
  moves to `engine/data/sine.bin` (engine asset; removed from game data).
- `engine/sound/z80_sound_driver.asm:1445` `fm_patches.inc`: game data included
  inside the driver image → becomes a manifest seam: the game defines
  `GAME_FM_PATCHES` (path symbol) that the driver's include site uses; the demo
  supplies a minimal default the ENGINE ships (engine-owned fallback patch set).
- `engine/debug/compression_selftest.asm:92` test vectors: generator output is
  engine test data → `gen_compression_vectors.py` emits to an engine-side
  generated path; include updated.
- `Debug_MusicToggle` + `Dbg_SfxIdTable` (game_loop.asm:40-135) is a game debug
  harness naming game songs/SFX → moves to `games/sonic4/` (a game debug module
  included by the manifest under `__DEBUG__`); the engine `GameLoop` keeps only a
  game-suppliable debug hook (`GAME_DEBUG_TICK` symbol, optional).
- `games/sonic4/player/player_sensors.asm`'s deliberate engine-block interleave
  (main.asm:119) is preserved via an explicit manifest hook: `engine.inc` invokes
  a game-defined `gameEngineBlockIncludes` macro at that slot (documented: for
  game code with no `code_addr` entry points that must live outside the object
  bank).

## 3. `engine.inc` + the manifest

`engine/engine.inc` becomes the single entry: defs (engine constants → structs →
macros → parallax macros → engine ram), org-0 (vectors + the game's `gameHeader`),
the engine code block (with the `gameEngineBlockIncludes` hook), the object-bank
scaffold, and the epilogue (error handler, `EndOfRom`, size guards). The **object
bank** is engine scaffold macros — `objBankStart` (org $10000, `ObjCodeBase`, the
empty-slot `rts`) / `objBankEnd` (the 64KB overflow guard) — with the game's
player/object includes between them in the manifest.

`games/sonic4/main.asm` shrinks to the manifest: game config includes (constants,
sound ids, ram), `gameHeader` params, `include engine/engine.inc` orchestration
per the layout contract, game module lists (engine-block hook, object bank, data,
sound banks with `soundBankHead`), `Game_Entry`. Target ≤ ~80 lines of substance
(the ROM-layout documentation moves into engine.inc/macros where it belongs).

## 4. Def + RAM split (refreshed classification, 2026-07-02)

- `constants.asm` → `engine/constants.asm` (~480L: hardware, VDP, SST layout,
  level/world, VRAM layout, DMA budgets) + `games/sonic4/config/constants.asm`
  (~60L: spindash tuning, PSTATE/ANIM game rows, GS ids, ring-system sizing,
  VRAM_TEST_* slots, collision-type game semantics stay engine — the enum is an
  engine contract; designs #3/#4 constants land game-side per their tags).
- `sound_constants.asm` → engine (~1410L driver) + game SFXID_* (~11L) into
  `games/sonic4/config/sound_ids.asm` (SONG_* already game-side).
- `structs.asm`, `macros.asm` → engine wholesale.
- `ram.asm` → `engine/ram.asm` (exports `Engine_RAM_End`) +
  `games/sonic4/config/ram.asm` (player block, pos rings, game debug vars) phased
  from `Engine_RAM_End`. Ring-system RAM/code stays ENGINE for now (documented:
  the engine's collectible system; re-taxonomize only with a second game's
  evidence). Even-alignment + oracle runtime boot-verify mandatory (the AS
  alignment lesson).

## 5. `build.sh` + `games/demo/`

- The seven sonic4 generator invocations (build.sh:63-137) gate on the game:
  each game may ship `games/<game>/prebuild.sh` (sonic4's wraps the current
  seven); no per-game logic inline in build.sh. Assemble→p2bin→convsym→fixheader
  →budget stay generic. `ROM_NAME` from the game (s4 for sonic4, `demo` → demo.bin).
- `games/demo/`: manifest + `gameHeader` ("AEON ENGINE DEMO"), minimal config
  (GS id, ram continuation, `GAME_BOOT_SONG=-1`, `GAME_FM_PATCHES` default),
  entry GameState setting backdrop + spawning ONE test object through the object
  system (uncompressed placeholder sprite shipped with the demo — no content
  pipeline), `; TODO: your game starts here` hooks. `build.sh demo` boots on
  oracle = the permanent agnosticism regression.

## 6. Sequencing & verification

- Stages mirror the old doc's 3→6 with the new couplings folded in; every stage
  ends green + committed. Stages that only MOVE content with preserved order
  target **byte-identical `s4.bin`** (verified by hash); stages that relocate
  (sine.bin, debug harness, def splits) target behavior-identical + oracle
  boot/render/sound check; the RAM split additionally gets the runtime boot-verify
  + a full circuit + sound smoke (HCZ2/MT/SFX hotkeys — which now live game-side).
- Designs #1–4 interaction: their plans cite current paths; whichever executes
  first wins, the others rebase paths mechanically (stated in all five).
- Success = the old doc's criteria + the new ones: zero game symbols in engine/
  (`grep` gate: SONG_|SFXID_|OJZ|Sonic|GS_OJZ across engine/ = comments only),
  demo boots + renders its object, sonic4 byte-or-behavior-identical per stage.

## 7. Research provenance

2026-07-02 two-agent pass: the coupling map (main.asm anatomy segment-by-segment;
the sound-bank seam verbatim invariant; the complete engine→game reference list —
boot handoff, debug ids, sfx window table, three include inversions; the
game→engine surface ~15-20 calls + the def namespace; refreshed def/RAM counts;
build.sh gating analysis) and the precedents report (SGDK sega.s/rom_header.c/
main() contract + XGM's driver-vs-data split; S.C.E. Engine/Includes.asm manifest
shape; plutiedev header-field ownership; GB Studio engine-eject/per-file override
as the modern analog; Treasure = temporal fork, negative result).
