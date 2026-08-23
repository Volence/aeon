# Aeon

A from-scratch Sega Genesis / Mega Drive game engine in 68000 + Z80 assembly.

Aeon is **not** a disassembly mod. Every line of code is written intentionally, applying modern
engine-design principles to 1990s hardware: build-time computation over runtime work,
data-oriented layout adapted for the 68000 bus, and compile-time validation that catches
errors at assembly time instead of on hardware. Game *data* (art, music, physics values,
palettes) is migrated from an older Sonic 2-based project; the code is not.

Aeon is a **reusable engine**. *Sonic 4* — the game this repo builds by default — is the first
game built *on* Aeon, not Aeon itself. `games/demo/` is the minimal starter game for a new
project and the standing proof that the engine really is game-agnostic.

Aeon is one part of the **Empyrean** Genesis development suite, alongside **Sigil** (the
assembler that builds it), **Oracle** (emulator/debugger), **Aurora** (editor) and
**Seraph** (DAW).

## What it is

A section-streaming Sonic engine with:

- **Unified VRAM art pool** — globally-deduped, spatially-ordered, paged act tileset used as a
  VRAM residency cache: 64-tile pages streamed in on demand and decoded across idle time
- **64×64 scroll planes** for vertical transitions and VSRAM effects
- **Per-section collision maps** — shift-based lookup, no runtime multiply
- **VDP-order sprite mappings** — zero field reordering at render time
- **Two-tier compression** — ZX0 (or raw, elected per page) for act art-pool pages, S4LZ v3 for
  the runtime block stream
- **Custom Z80-autonomous sound driver** — FM/PSG music sequencer + DMA-survival DAC drums
- **Raster and palette effects** — scenes authored at build time and compiled into the ROM
- **Build-tool pipeline** — editor stamps → flatten → deduplicate → spatial-order → page → generate

See [`docs/ENGINE_ARCHITECTURE.md`](docs/ENGINE_ARCHITECTURE.md) for the full design.

## Build

```bash
./build.sh                  # release ROM — default game sonic4 -> s4.bin
DEBUG=1 ./build.sh          # debug shape -> s4.debug.bin
./build.sh demo             # first arg selects the game -> demo.bin
FAST=1 DEBUG=1 ./build.sh   # content-authoring loop — SKIPS every verification lane
```

`build.sh` needs `SIGIL_BUILD` and `SIGIL_EMIT` set to the sigil repo's release binaries and
hard-errors without them. A `FAST=1` ROM is byte-identical to the canonical one, but nothing
checked that — re-run a plain `./build.sh` before you land, merge, or quote a number.

**`sigil build` *is* the build.** One sigil invocation assembles every `.emp` module, links in
the order declared by `games/<game>/map.toml`, folds the header checksum and emits the `.lst`;
the surviving `convsym` appends the deb2 symbol table. The AS Macro Assembler (`asl`), `p2bin`
and `fixheader` have left the pipeline. Around the assemble run the generators (level bake, ZX0
art-pool packing via the vendored `salvador`, sound blob, compression vectors) and the
verification lanes (lint, budget checks, pytest, the negative-build lane).

Source is `.emp`. The only `.asm` files left in the tree are the per-game residual root
`games/<game>/game_root.asm` (defines and externs — emits no bytes) and the vendored MD
Debugger `engine/debug/debugger.asm`.

`./test.sh` runs the data and tool self-tests, a ROM build, and a headless replay net.

ROM addresses and sizes change constantly — never hardcode or quote them. The `.lst` is fed to
`convsym` so a debugger resolves symbol names live.

## Repository layout

| Path | Contents |
|---|---|
| `engine/` | The reusable Aeon engine, no game specifics — `system/`, `compression/`, `level/`, `objects/`, `effects/`, `sound/`, `debug/`, plus engine-owned definitions at the root (`structs.emp`, `ram.emp`, `coords.emp`, `vdp.emp`, `irq.emp`, `z80_bus.emp`) |
| `games/sonic4/` | The Sonic 4 game built on Aeon — `player/`, `objects/`, `config/`, `data/`, `test/`, `map.toml` (the declared ROM placement contract), `game_root.asm` |
| `games/demo/` | The minimal starter game and the proof the engine is game-agnostic |
| `art/` | Character and shield sprite art plus palettes (level art lives under `games/<game>/data/`) |
| `tools/` | Python build generators and test lanes, the vendored `salvador` ZX0 packer, `convsym` |
| `docs/` | Architecture, deferred work, specs, research |

## Conventions

**Read [`CODING_CONVENTIONS.md`](CODING_CONVENTIONS.md) before writing any code** — it is the law
of this codebase. Highlights: transfers are auto-sized (`jbsr`, `jbra`, unsized `bcc`), `comptime
fn` for all compile-time math, `struct (size: N)` for data layout, `region`/`vars` for RAM with
compiler-checked overflow, PascalCase routines and ALL_CAPS constants, no `mulu`/`divu`, and no
unstopped Z80 during VDP access.

Working rules for this repo are in [`CLAUDE.md`](CLAUDE.md). Active design decisions live in
[`docs/ENGINE_ARCHITECTURE.md`](docs/ENGINE_ARCHITECTURE.md); blocked or deferred work is tracked
in [`docs/DEFERRED_WORK.md`](docs/DEFERRED_WORK.md).
