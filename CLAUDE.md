# CLAUDE.md — Sonic 4 Engine

## Overview

Fresh Sega Genesis engine for Sonic 4, built from scratch and assembled by **sigil**, the suite's from-scratch Rust toolchain (`.emp` source language). This is NOT a disassembly mod — every line of code is written intentionally following modern design principles adapted for 68000 hardware.

All game DATA (art, music, physics values, palette files) will be migrated from the sonic_hack/ project. All CODE is new.

## Build

```bash
./build.sh          # Build s4.bin ROM (release shape)
DEBUG=1 ./build.sh  # Build s4.debug.bin (debug shape — suffixed artifacts)
```

Assembler: **sigil** — `sigil build` IS the build (Spec-5 Stage 2 flip). The AS Macro Assembler (`asl`) + `p2bin` + `fixheader` have left the pipeline; one sigil invocation assembles every `.emp` module natively (plus the residual `.asm` via sigil-frontend-as), links in declared order (`games/<game>/map.toml`), folds the header checksum, emits the `.lst`, and appends the deb2 symbol table via the surviving `convsym`.

**Required env vars** (build.sh hard-errors without them — no asl fallback):
- `SIGIL_BUILD` — path to the sigil repo's release `sigil` binary
- `SIGIL_EMIT` — path to the sigil repo's release `emit_sound_blob` binary (needed for any sound-ON game, i.e. every sonic4 build)

Source is `.emp` — the `.asm` CODE twins are deleted. The only surviving `.asm` files are the per-game residual root `games/<game>/game_root.asm` (defines/externs only, emits no bytes) and the vendored MD Debugger (`engine/debug/debugger.asm`). Mixed 68000 + Z80 in a single project. `build.sh [game]` selects the game (default `sonic4` → `s4.bin`; `demo` → `demo.bin`, sound off via its `build.conf`).

Shapes: build.sh ships the two canonical shapes only — plain (release) and `DEBUG=1` — and both carry the MD Debugger island + deb2 symbols (crash-report ruling 2026-08-04). A plain `./build.sh` builds with sound (`SOUND_DRIVER_ENABLED` defaults ON); non-canonical sonic4 sound shapes (silent, `SOUND_DEBUG_HOTKEYS`, `SOUND_DBG_MIRROR`) and `CRASH_REPORT=0` are **refused** by build.sh — they are named off-canonical sigil profiles (`sigil build --native --config-a/--config-b/--lean`) gated by their own goldens. `CONTRACTS=0` is the emergency opt-out for the contract-closure gate, not a normal knob.

## Repository Layout

Aeon draws a hard **engine / game** wall (restructure 2026-06-28; agnostic engine shipped 2026-07-07/08):

- `engine/` — the reusable Aeon engine, no Sonic specifics:
  - `system/` — boot, VDP/Z80 init, DMA queue, IRQs (vblank/hblank), controllers, game loop, math
  - `compression/` — S4LZ + ZX0 decompressors
  - `level/` — section streaming, camera, parallax, plane/tile buffers, collision lookup
  - `objects/` — object system (core, sprites, animate, DPLC, collision, children, load)
  - `sound/` — Z80 driver + FM/PSG/sequencer/SFX
  - `debug/` — debugger, error handler, self-tests
  - `structs.emp`, `ram.emp`, `coords.emp`, `vdp.emp`, `irq.emp`, `z80_bus.emp` — engine-owned defs at the engine root (constants live in `engine/system/constants.emp`, sound constants in `engine/sound/sound_constants.emp`); `ram.emp` ends at the `Engine_RAM_End` seam a game's RAM continues from
  - the ROM layout is no longer an include-file manifest: `main.asm` + `engine/engine.inc` are DELETED. Placement is the declared sigil map (`games/<game>/map.toml`) consumed by the sigil chainer. See `docs/ENGINE_ARCHITECTURE.md`, "Engine/game contract" section, for the full manifest/contract reference
- `games/sonic4/` — the Sonic 4 game built on Aeon: `player/` (all player code incl. `sonic.emp`), `objects/`, `config/` (`constants.emp`, `sound_ids.emp`, `game.emp`, `ram.emp`, `header.emp` — the game-side def/RAM slices + contract declarations, incl. the `Game` interface binding in `game.emp`), `data/` (levels, art, sound, parallax, mappings, collision, editor), `test/` (game state test scaffolding), `map.toml` (the declared ROM placement contract), and `game_root.asm` (the minimal AS residual root — defines/externs only, emits no bytes).
- `games/demo/` — the minimal starter game: boots to a white 16×16 box on a dark-blue backdrop, zero Sonic code. Both the "start here" template for a new game and the permanent proof the engine is actually game-agnostic (`DEBUG=1 ./build.sh demo`).
- `tools/` build generators · `docs/` design + specs.

## Conventions

**Read `CODING_CONVENTIONS.md` before writing ANY code.** It is the law of this codebase.

Key rules that are easy to forget:
- Transfers are auto-sized in `.emp`: unsized `bcc .label` for conditionals, `jbsr` for calls, `jbra` for jumps (sigil relaxes by reach, incl. the far `jsr`/`jmp` rung); raw `jsr` only for register-indirect; explicit `.s`/`.w` only in `@as_compat` ports, patched fields, and residual `.asm`
- `comptime fn` for ALL compile-time math — never compute at runtime what sigil can compute at build time (AS's `function` maps 1:1, residual `.asm` only)
- `struct (size: N)` for ALL data structures — no manual `const`/`equ` chains (AS `struct`/`endstruct` is residual `.asm` only)
- `region`/`vars` for RAM layout — compiler catches overflow (AS `phase`/`dephase` is residual `.asm` only)
- PascalCase for routines and global variables, ALL_CAPS for constants, .lowercase for locals
- No `mulu`/`divu` — use shifts, adds, or lookup tables
- No unstopped Z80 during VDP access

## Architecture

Design documents:
- `docs/ENGINE_ARCHITECTURE.md` — master design document (VRAM layout, section streaming, collision, sprites, etc.)
- `docs/DEFERRED_WORK.md` — work identified but blocked by missing dependencies. **Check at the start of every planning phase.**
- `CODING_CONVENTIONS.md` — assembly style, optimization rules, AS features

**Keep ENGINE_ARCHITECTURE.md in sync with reality.** Whenever research or implementation reveals a better approach that changes an engine decision, update the relevant section in `docs/ENGINE_ARCHITECTURE.md` immediately. The architecture doc is the source of truth — if code diverges from it, one of them is wrong.

## Git Workflow

**Commit early and often.** Lost work from uncommitted changes is unacceptable.

- Each implementation step should be committed as it's completed
- At the end of each plan's implementation, all work is merged into `master`
- The next planning phase always starts from a clean `master`
- Use feature branches for implementation plans — merge to `master` when the plan is complete and verified

## Research Checklist

**Every design/brainstorm phase MUST complete ALL of these before proposing approaches:**

1. **All reference disassemblies** — check each one for how they solve the problem:
   - S.C.E., Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, Ristar, sonic_hack
2. **Online sources** — search plutiedev, md.railgun.works, segaretro, SpritesMind, Hidden Palace prototype dumps, GitHub homebrew
3. **Modern techniques** — look for patterns from modern engine design that apply to 68000

Do not skip any source. Do not assume one reference covers the others. Each project made different tradeoffs worth understanding.

## Reference Projects

When researching how to implement a system, check these in order:
1. **S.C.E.** (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`) — cleanest Sonic reference
2. **Batman & Robin** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/`) — best visual techniques, VDP shadow table
3. **Vectorman** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/`) — 64×64 planes, advanced sprite work
4. **Gunstar Heroes** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/`) — multi-sprite objects, Treasure optimization
5. **Alien Soldier** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/`) — extreme 68000 optimization
6. **Thunder Force IV** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/`) — scroll effects, layer management
7. **Ristar** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/ristar_disasm/`) — Sonic 1-derived platformer (NOT Sonic 3K, despite the team overlap); cinematic per-stage HInt scripting (HBlank → `$FFEA70` RAM), chained-sprite rope rendering (grab arm), event-tagged animation frames, SMPS 68k Type 2 + custom Z80 dual-PCM mixer, Star compression (Kosinski cousin). v1 raw disasm + ANALYSIS.md + MEMORY_MAP.md + labels.txt produced locally via capstone (`scripts/disasm.py`). Cross-references at `aeon/docs/research/ristar-techniques.md`.
8. **sonic_hack/** (`/home/volence/sonic_hacks/sonic_hack/`) — original S2 disassembly with our modifications (data source)

## Online Research & Modern Techniques

**Always search online sources** when designing or implementing any system. The Genesis homebrew and retro dev communities have discovered techniques that no commercial game ever used. Key sources:
- **plutiedev.com** — hardware reference (VDP registers, DMA, Z80, controllers, timing)
- **md.railgun.works** — Mega Drive development wiki (init sequences, hardware quirks)
- **Kabuto hardware notes** — deep VDP timing, undocumented features, border tricks
- **segaretro.org** — technical specifications, format documentation
- **Titan Overdrive / tech demos** — pushing hardware limits beyond what any game achieved
- **Amiga demoscene** — similar-era hardware, decades of optimization tricks applicable to 68000
- **SpritesMind forum** — Genesis dev community discussions
- **GitHub** — modern homebrew projects (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD)

**Think beyond 1990s conventions.** This engine benefits from 40 years of game engine evolution:
- **Build-time computation** over runtime (like modern shader compilation)
- **Data-oriented design** (struct-of-arrays, cache-friendly layout adapted for 68K bus)
- **Event-driven architecture** (interrupt dispatch tables, state machines with entry/exit hooks)
- **Async I/O patterns** (DMA-parallel work, double buffering)
- **Compile-time validation** (catch errors at build time, not on hardware)
- **Graph algorithms for resource allocation**
- Any modern pattern that makes the hardware faster, code cleaner, or builds more reliable

## Testing

- Build and load in the user's debug emulator (Oracle with MCP)
- Oracle auto-launch/relaunch is user-approved (2026-07-02) — ONE instance only (verify with
  `pgrep -x oracle_gui`; multiple instances contend for the MCP socket and you end up debugging
  a stale binary). Other emulators: never auto-launch — user handles that
- Use Oracle MCP tools to inspect VRAM, CRAM, registers, RAM directly

## What This Engine Is

A section-streaming Sonic engine with:
- Unified VRAM art pool — globally-deduped, spatially-ordered, paged act tileset as a VRAM residency cache: small 64-tile pages streamed in on demand + prefetch via a VBlank supervisor-bookmark idle-time decoder, capped by ROM not VRAM (degenerates to fully-resident for acts whose window fits the pool). See ARCH §9.7.
- 64×64 scroll planes for vertical transitions and VSRAM effects
- Per-section collision maps (shift-based lookup, no multiply)
- VDP-order sprite mappings (zero field reordering)
- Two-tier compression — ZX0/raw-direct 64-tile pages for the act art pool (per-page form election; the resumable ZX0R decoder sliced across idle time, §9.7), S4LZ v3 for the runtime block stream (per-section block dictionaries); uncompressed sprite art + improved DPLC/DMA. Enigma/Nemesis/Kosinski/UFTC all removed
- From-scratch custom Z80-autonomous sound driver — FM/PSG music sequencer + DMA-survival DAC drums (Flamedriver-informed, not Flamedriver)
- Build tool pipeline: editor stamps → flatten → deduplicate → spatial-order → page → generate
