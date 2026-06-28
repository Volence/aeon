# Aeon engine/game restructure — design

**Date:** 2026-06-28
**Status:** Design (approved in brainstorm; pending spec review)

## Motivation

Aeon is now positioned as a **reusable Genesis engine**; *Sonic 4* is the **first game built on
it**, not the engine itself. The current directory layout — inherited from the old `sonic_hack`
disassembly — intermixes reusable engine code with Sonic-4-specific code and content. This
restructure draws a **hard engine/game wall** at the directory level so the engine is genuinely
game-agnostic and a second game is just a sibling folder.

This is a **structural / organizational change only**. No engine behavior changes. The ROM output
stays byte-equivalent in intent (`s4.bin`), and every migration stage ends with a green build.

## Guiding decisions (settled in brainstorm)

1. **Real reusable engine** — draw the hard wall now, not "tidy toward it later."
2. **All player code is game-specific** — Sonic physics (slopes, rolling, spindash, sensors,
   `sonic.asm`) lives in the game. The engine exposes the *substrate* the player consumes
   (collision lookup, object/sprite/animation system, camera, streaming). Do **not** invent a
   "generic platformer kit" from one example; extract shared physics only when a second platformer
   proves what's common.
3. **Approach A naming** — `engine/` + `games/sonic4/` (plural `games/`), so the engine is honestly
   multi-game and game #2 is a new sibling.
4. **The engine owns boot boilerplate** — vectors, ROM-header, reset/init move into the engine; a
   game's `main.asm` becomes a thin manifest.
5. **`games/demo/`** — a minimal starter game that boots to a blank canvas, serving as both the
   "start here" template and a permanent engine-boots-without-Sonic regression check.

## Target structure

```
aeon/
├── engine/                      # reusable Aeon — ZERO Sonic-isms
│   ├── system/                  # boot, reset/init, vectors, vdp_init, z80_init, dma_queue,
│   │                            #   buffers, vblank, hblank, controllers, game_loop, math
│   ├── compression/             # s4lz_decompress, zx0_decompress
│   ├── level/                   # streaming: plane_buffer, tile_cache, collision_lookup,
│   │                            #   section, camera, parallax, load_art, bg, bg_anim
│   ├── objects/                 # object SYSTEM: core, sprites, animate, dplc, collision,
│   │                            #   children, load_object, entity_window, aabb.inc
│   ├── sound/                   # driver: z80_sound_driver, sound_fm, sound_psg,
│   │                            #   sound_sequencer, sound_sfx, sound_api, sound_banked_z80,
│   │                            #   sound_tables_z80, sfx_blob_win_tab
│   ├── structs.asm              # engine structs (object SST, section/act descriptors, …)
│   ├── macros.asm               # VDP/DMA/general macros
│   ├── constants.asm            # engine constants (VRAM layout, hardware regs, object offsets…)
│   ├── sound_constants.asm      # sound-driver constants (MEV opcodes, channel/FM/PSG defs)
│   ├── ram.asm                  # engine RAM block → exports Engine_RAM_End
│   └── engine.inc               # single entry: pulls all engine defs + code in correct order
│
├── games/
│   ├── demo/                    # minimal starter template
│   │   ├── main.asm             # ~30-line manifest
│   │   └── config/              # RAM start (from Engine_RAM_End), minimal constants
│   │                            #   entry GameState boots to a visible blank canvas + TODO hooks
│   └── sonic4/                  # the real game
│       ├── main.asm             # game manifest
│       ├── player/              # ALL player code incl sonic.asm, sensors, spindash, air/ground
│       ├── objects/             # game object implementations (test_* today)
│       ├── config/              # game constants (object IDs, tuning), song/SFX IDs, game RAM
│       └── data/                # levels, art, sound content, parallax scenes, mappings,
│                                #   collision, dplc, animations, objdefs, editor
│
├── tools/                       # Crucible build generators (paths updated to new tree)
├── docs/
├── build.sh                     # build.sh [game]  (default: sonic4)
├── test.sh
├── README.md · CLAUDE.md · CODING_CONVENTIONS.md
```

Notes:
- `source/` (vestigial — only held `source/data/ojz_strips/`) is folded into `games/sonic4/data/`
  or removed if regenerated; resolved during migration.
- `debug/` (debugger, error_handler, compression_selftest, sound_debug) is engine tooling → moves
  under `engine/` (e.g. `engine/debug/`).

## Detailed decisions

### 1. Engine subsystem grouping
Every engine file lives under a subsystem folder; nothing loose at `engine/` root except the
shared defs and `engine.inc`. Sound (9 files) and compression (2 files) — currently loose — get
their folders.

### 2. Shared-def split
Verified mix (engine-token vs game-token line counts):
- `structs.asm` (249L, ~all engine) → engine wholesale.
- `macros.asm` (VDP/DMA) → engine.
- `constants.asm` (539L; 60 engine / 14 game) → engine constants stay; game slice (object IDs,
  ring/monitor/spindash, OJZ) → `games/sonic4/config/constants.asm`.
- `sound_constants.asm` (1405L; 246 engine / 16 game) → driver constants stay in engine; song/SFX
  **IDs** → `games/sonic4/config/`.
- All engine defs are surfaced through `engine/engine.inc`.

### 3. RAM ownership
`ram.asm` (478L, mostly engine) splits:
- `engine/ram.asm` phases the engine RAM region from the base; exports `Engine_RAM_End`.
- `games/<game>/config/ram.asm` continues the phase from `Engine_RAM_End` for game/player state.
- Safe because nothing hardcodes addresses (the suite resolves symbols live via Oracle). Constraints:
  keep even-alignment (odd `ds.b` runs address-error the next word field), and **runtime boot-verify
  on Oracle** after the RAM change (build + asserts passing is not sufficient for RAM layout changes).

### 4. Boot boilerplate → engine; `main.asm` becomes a manifest
The 68000 vector table, ROM-header, and reset/init move into `engine/system/` (e.g. `vectors.asm`
plus a header macro). A game's `main.asm` shrinks to a manifest (~30 lines):
- game metadata (title, region, `ROM_NAME`),
- `include "engine/engine.inc"`,
- the list of game modules,
- its RAM extension (continues from `Engine_RAM_End`),
- the entry `GameState`.

**Boot must be decoupled from Sonic 4.** Today the engine boot hard-jumps into the Sonic-specific
`GameState_OJZScroll_Init`. For the manifest (and `games/demo/`) to work, the engine boot must end
by jumping to a **game-supplied entry symbol** (e.g. `Game_Entry`, the game's first GameState),
declared by the manifest — not a hardcoded OJZ init. This is the previously-deferred
"parameterized boot" step from the Aeon hand-off brief; this restructure is what unblocks it. The
engine defines the GameState dispatch mechanism; the game provides the initial GameState value and
its handlers.

### 5. `games/demo/`
Minimal game proving engine agnosticism:
- `main.asm` = the ~30-line manifest; `config/` = RAM start + minimal constants.
- Entry GameState boots to a **visible blank canvas** (backdrop color / placeholder tile) with
  `; TODO: your first object / GameState here` hooks.
- **No** dependency on the art/section/streaming content pipeline (that's game content).
- `build.sh demo` is the smoke test that the engine boots without Sonic 4.

### 6. Build
`build.sh [game]` defaults to `sonic4`; assembles `games/<game>/main.asm`. **`ROM_NAME` stays `s4`**
for sonic4 → still builds `s4.bin` / `s4.lst` (game content; Oracle resolves by filename). The ROM
is emitted at repo root (unchanged) so Oracle's load path is undisturbed. `demo` builds `demo.bin`.

## Migration strategy

Big move on a fragile engine → strictly incremental, each stage ends with a **green build**
(`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`), committed:

1. **Engine subfolders** — create `engine/{system,compression,sound,debug}/`, move files, fix
   includes. Build green.
2. **Game tree** — create `games/sonic4/`, move `player/`, `objects/`, `data/`, `main.asm`; update
   includes + `build.sh`. Build green.
3. **Boot boilerplate to engine + parameterized boot** — extract vectors/header/init into
   `engine/system/`; replace the hardcoded `GameState_OJZScroll_Init` jump with a handoff to a
   game-supplied entry symbol; reduce `sonic4/main.asm` to a manifest. Build green + Oracle boot
   check (boot path changed).
4. **Shared-def split** — bisect `constants.asm` / `sound_constants.asm`; engine defs via
   `engine.inc`. Build green.
5. **RAM split** — `engine/ram.asm` + `games/sonic4/config/ram.asm`. Build green **+ Oracle boot /
   render / sound check** (RAM layout changed).
6. **`games/demo/`** — author the minimal manifest + boot GameState. `build.sh demo` boots on Oracle.
7. **Cleanup** — update `tools/` generator paths, `docs/`, `CLAUDE.md`, `.ctags`; remove vestigial
   `source/`.

All on a feature branch; merge to `master` when green and Oracle-verified end to end.

## Coordination flags (cross-tool, same class as the dir rename)
- **Python generators** (`tools/`) emit into `data/` paths → must update to `games/sonic4/data/`.
- **Autocommit daemon** watches `data/editor/ojz` → its watch path moves to
  `games/sonic4/data/editor/ojz`. `tools/ojz_strip_gen.py` is daemon-watched — coordinate, don't
  edit it mid-flight.
- **Oracle** — ROM stays `s4.bin` at repo root, so `load_symbols` path is unaffected.

## Non-goals
- No engine behavior changes; no functional refactors riding along.
- `s4.bin` / `s4.lst` / `ROM_NAME=s4` / "Sonic 4" stay (game content).
- No generic-platformer-physics extraction (YAGNI until game #2).
- The `s4`-prefixed **tool** names (`s4lint`, `s4lz`, `s4budget`, `s4p2bin`) are **not** renamed —
  separate, larger decision out of scope here.

## Success criteria
- `engine/` contains zero Sonic-specific identifiers, paths, or content.
- `build.sh` (sonic4) produces `s4.bin`; Sonic 4 boots/renders/sounds identically on Oracle.
- `build.sh demo` produces a ROM that boots to a blank canvas on Oracle.
- A new game = copy `games/demo/`, no engine edits.
- Every migration stage was committed green; final tree merged to `master`.
