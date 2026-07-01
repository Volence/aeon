# Aeon

A from-scratch Sega Genesis / Mega Drive game engine in 68000 + Z80 assembly.

Aeon is **not** a disassembly mod. Every line is written intentionally, applying modern
engine-design principles to 1990s hardware: build-time computation over runtime work,
data-oriented layout adapted for the 68000 bus, and compile-time validation that catches
errors at assembly time instead of on hardware.

Aeon is a **reusable engine**. *Sonic 4* — the game this repo currently builds — is the first
game built *on* Aeon, not Aeon itself. Game-specific content keeps the `s4` / "Sonic 4" name
(e.g. the `s4.bin` ROM); the engine is `aeon`.

Aeon is one tool in the **Empyrean** Genesis development suite (engine **Aeon**, emulator
**Oracle**, editor **Aurora**, DAW **Seraph**, build node **Crucible**), which communicate over a
shared bus.

## What it is

A section-streaming engine with:

- **Unified VRAM art pool** — globally-deduped, spatially-ordered, paged act tileset, loaded once at init
- **64×64 scroll planes** for vertical transitions and per-line VSRAM parallax
- **Per-section collision maps** — shift-based lookup, no runtime multiply
- **VDP-order sprite mappings** — zero field reordering at render time
- **Two-tier compression** — ZX0 for load-time art-pool pages, S4LZ v3 for the runtime block stream
- **Custom Z80-autonomous sound driver** — FM/PSG music sequencer + DMA-survival DAC drums
- **Build-tool pipeline** — editor stamps → flatten → deduplicate → spatial-order → page → generate

See [`docs/ENGINE_ARCHITECTURE.md`](docs/ENGINE_ARCHITECTURE.md) for the full design.

## Build

```bash
./build.sh            # assemble s4.bin (default game: sonic4; native tools/asl, no Wine)
./build.sh <game>     # assemble games/<game>/main.asm (first arg selects the game)
./build.sh sonic4 -pe # print errors only (the game must be given first, since $1 = game)
```

Pipeline: build-tool generators (S&K collision import, OJZ strip/block gen, ZX0 art-pool packing
via `salvador`, compression vectors, SFX transcode) → `s4lint` → AS Macro Assembler (`tools/asl`) →
`p2bin` → `convsym` symbol table → `fixheader` checksum. Output is `s4.bin` (the game ROM) plus
`s4.lst` (symbols, fed to `convsym` so debuggers resolve names live — addresses are expected to drift
between builds and are never hardcoded). The build is game-parameterized; `sonic4` keeps the historical
`s4` ROM name, other games use their own.

The Z80 sound driver and DEBUG features are gated behind build flags:

```bash
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
```

## Repository layout

| Path | Contents |
|---|---|
| `constants.asm`, `macros.asm`, `ram.asm`, `structs.asm`, `sound_constants.asm` | Top-level global definitions |
| `engine/` | Reusable Aeon engine — `system/`, `compression/`, `level/`, `objects/` (object system), `sound/`, `debug/`. No game specifics. |
| `games/sonic4/` | The Sonic 4 game built on Aeon: `main.asm`, `player/`, `objects/` (game objects), `data/` |
| `data/` | Engine-shared data: `collision/`, `generated/` (game data lives under `games/<game>/data/`) |
| `art/` | Compressed and uncompressed graphics |
| `tools/` | Native build tools (`asl`, `p2bin`, `convsym`, `fixheader`) + Python generators (art paging, compression, collision, sound tables) |
| `docs/` | Architecture, deferred work, research, and design specs |
| `test/` | In-ROM test scaffolds |

## Conventions

**Read [`CODING_CONVENTIONS.md`](CODING_CONVENTIONS.md) before writing any code** — it is the law of
this codebase. Highlights: explicit `.s`/`.w`/`.l` sizes on every branch, `function` for all
compile-time math, `struct`/`endstruct` for data layout, `phase`/`dephase` for RAM with
overflow checking, no `mulu`/`divu`, and no unstopped Z80 during VDP access.

Active design decisions live in [`docs/ENGINE_ARCHITECTURE.md`](docs/ENGINE_ARCHITECTURE.md);
blocked or deferred work is tracked in [`docs/DEFERRED_WORK.md`](docs/DEFERRED_WORK.md).
