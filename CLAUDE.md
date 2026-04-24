# CLAUDE.md — Sonic 4 Engine

## Overview

Fresh Sega Genesis engine for Sonic 4, built from scratch using the AS Macro Assembler. This is NOT a disassembly mod — every line of code is written intentionally following modern design principles adapted for 68000 hardware.

All game DATA (art, music, physics values, palette files) will be migrated from the sonic_hack/ project. All CODE is new.

## Build

```bash
./build.sh          # Build s4.bin ROM
```

Assembler: AS Macro Assembler (`asw`). Mixed 68000 + Z80 assembly in a single project.

## Conventions

**Read `CODING_CONVENTIONS.md` before writing ANY code.** It is the law of this codebase.

Key rules that are easy to forget:
- `.s`/`.w`/`.l` on EVERY branch and jump — no unsized references
- `function` for ALL compile-time math — never compute at runtime what AS can compute at build time
- `struct`/`endstruct` for ALL data structures — no manual `equ` chains
- `phase`/`dephase` for RAM layout — assembler catches overflow
- PascalCase for routines and global variables, ALL_CAPS for constants, .lowercase for locals
- No `mulu`/`divu` — use shifts, adds, or lookup tables
- No unstopped Z80 during VDP access

## Architecture

Design documents:
- `docs/ENGINE_ARCHITECTURE.md` — master design document (VRAM layout, section streaming, collision, sprites, etc.)
- `CODING_CONVENTIONS.md` — assembly style, optimization rules, AS features

## Reference Projects

When researching how to implement a system, check these in order:
1. **S.C.E.** (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`) — cleanest Sonic reference
2. **Batman & Robin** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/`) — best visual techniques, VDP shadow table
3. **Vectorman** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/`) — 64×64 planes, advanced sprite work
4. **Gunstar Heroes** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/`) — multi-sprite objects, Treasure optimization
5. **Alien Soldier** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/`) — extreme 68000 optimization
6. **Thunder Force IV** (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/`) — scroll effects, layer management
7. **sonic_hack/** (`/home/volence/sonic_hacks/sonic_hack/`) — original S2 disassembly with our modifications (data source)

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
- **Graph algorithms for resource allocation** (VRAM graph coloring)
- Any modern pattern that makes the hardware faster, code cleaner, or builds more reliable

## Testing

- Build and load in the user's debug emulator (Exodus with MCP)
- Never auto-launch emulators — user handles that
- Use Exodus MCP tools to inspect VRAM, CRAM, registers, RAM directly

## What This Engine Is

A section-streaming Sonic engine with:
- Unified VRAM art pool ($000-$5FF) with build-time graph coloring
- 64×64 scroll planes for vertical transitions and VSRAM effects
- Per-section collision maps (shift-based lookup, no multiply)
- VDP-order sprite mappings (zero field reordering)
- Two-tier compression: S4LZ (art), UFTC (random-access sprites). Enigma/Nemesis/Kosinski all removed
- Flamedriver sound driver (full Z80 autonomy)
- Build tool pipeline: editor stamps → flatten → deduplicate → graph-color → generate
