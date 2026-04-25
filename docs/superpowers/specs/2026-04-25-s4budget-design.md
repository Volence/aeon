# s4budget — ROM/RAM Budget Dashboard

## Overview

A build-time tool that parses the AS Macro Assembler listing file (`s4.lst`) to report ROM, RAM, and VRAM usage. Two modes: a compact one-liner integrated into `build.sh`, and a full detailed report run on-demand.

Genesis hard limits: 4MB ROM, 64KB RAM, 64KB VRAM. The object code bank has an additional 64KB sub-limit.

## Data Source

The primary data source is `s4.lst`, the AS listing file already produced by the build (`-L -OLIST s4.lst`). No new assembler flags are needed.

The listing contains:

1. **Source listing** — each line shows include depth, source line number, ROM/RAM address, assembled opcode, and source text. Include directives show the filename, allowing the tool to map ROM address ranges to source files.

   Format:
   ```
   (depth) line/  addr : opcode                source
   (1)   10/     416 : 41FA FFAE              lea.l   BootData_VDPRegs(pc), a0
         14/       0 :                         include "constants.asm"
   ```

   - Depth `(N)` = include nesting level; no prefix = top-level (`main.asm`)
   - Address = hex ROM address, or `FFFFFFFFFFFF____` for RAM phase blocks
   - Include lines show `include "filename.asm"` — the tool tracks file transitions

2. **Symbol table** (end of file) — every label and constant with its address. Two entries per line, pipe-separated.

   Format:
   ```
    SYMBOL : addr C |  SYMBOL : addr - |
   ```

   - `C` = code/data label (has a ROM or RAM address)
   - `-` = constant (equate, no address)
   - `*` prefix = unused symbol
   - RAM addresses appear as `FFFFFFFFFFFF8000` etc. (AS sign-extends the 24-bit 68000 address)

3. **ROM binary** (`s4.bin`) — `stat` for actual file size.

## Sentinel Labels

Add zero-cost labels to `main.asm` at region boundaries so the tool can identify ROM regions unambiguously:

```asm
__BUDGET_VECTORS:       ; $000000 — exception vector table
; ... vectors ...

__BUDGET_ENGINE:        ; ~$000200 — engine code
; ... engine includes ...

__BUDGET_OBJBANK:       ; $010000 — object code bank (64KB limit)
; ... object includes ...

__BUDGET_DATA:          ; after object bank — game data, art, mappings
; ... data includes ...

EndOfRom:               ; end of ROM (already exists)
```

These labels produce no ROM output. The tool computes region sizes as address gaps between consecutive sentinels.

## Output: Detailed Report

Run: `python tools/s4budget.py s4.lst s4.bin`

```
=== ROM Budget ===
ROM: 209,408 / 4,194,304 bytes (5.0%)

  Vectors      $000000-$0001FF       512 B
  Engine       $000200-$00FFFF    63.0 KB
  Object Bank  $010000-$01A3FF    41.0 KB  (of 64 KB limit: 64.1%)
  Game Data    $01A400-$0331FF   101.4 KB
  Free                             3.8 MB

  Engine (63.0 KB):
    engine/boot.asm              484 B
    engine/z80_init.asm           52 B
    engine/vdp_init.asm           76 B
    engine/dma_queue.asm         738 B
    engine/buffers.asm           384 B
    engine/vblank.asm            212 B
    engine/hblank.asm             18 B
    engine/controllers.asm        82 B
    engine/game_loop.asm          14 B
    engine/s4lz_decompress.asm   480 B
    engine/objects/dplc.asm      152 B
    engine/objects/core.asm      446 B
    engine/objects/sprites.asm   662 B
    engine/objects/animate.asm   618 B
    engine/objects/collision.asm 352 B
    engine/objects/children.asm  716 B
    engine/objects/load_object.asm 384 B

  Object Bank (41.0 KB of 64 KB):
    objects/test_static.asm        4 B
    objects/test_animated.asm     90 B
    ...

  Game Data (101.4 KB):
    data/...
    art/...

=== RAM Budget ===
RAM: 26,624 / 32,512 bytes (81.9%)  [5,888 free before stack]

  Lower RAM ($FFFF0000-$FFFF7FFF):
    Decomp_Buffer            32,768 B

  Upper RAM ($FFFF8000-$FFFFA000):
    VBlank_Flag                   1 B
    Frame_Counter                 2 B
    Game_State                    4 B
    ...
    VDP_Shadow_Table             19 B
    DMA_Queue                   432 B
    Palette_Buffer              128 B
    Sprite_Table_Buffer         640 B
    Hscroll_Buffer              896 B
    Object_RAM                6,912 B
    ...
    [Free]                    5,888 B  → $FFFFFF00 (stack)

=== VRAM Budget ===
VRAM: 65,536 bytes (2,048 tiles)

  Plane A        $C000-$DFFF   8,192 B  (256 tiles)
  Plane B        $E000-$FFFF   8,192 B  (256 tiles)
  Sprite Table   $D800-$D9FF     512 B
  Hscroll Table  $DC00-$DFFF   1,024 B
  Window Plane   $F000-$F7FF   2,048 B  (64 tiles)
  Art Tiles      $0000-$BFFF  49,152 B  (1,536 tiles available)
```

## Output: Build One-Liner

Run: `python tools/s4budget.py s4.lst s4.bin --summary`

Prints a single line to stderr:

```
ROM: 209KB/4MB (5%) | ObjBank: 41KB/64KB (64%) | RAM: 26KB/32KB (82%) | Free: 5.8KB before stack
```

## Build Integration

Add one line to `build.sh` after the existing ROM size report:

```bash
python3 tools/s4budget.py s4.lst s4.bin --summary
```

The full report is run on-demand only: `python3 tools/s4budget.py s4.lst s4.bin`

## Parsing Strategy

### Source Listing Parser

Walk each line of the listing (before the symbol table):

1. **Detect include transitions**: lines with `include "filename.asm"` push the filename onto a stack. When include depth decreases, pop.
2. **Track ROM addresses**: extract the hex address from each line. Non-phase lines with a valid address contribute to the current file's byte count.
3. **Detect region sentinels**: when a line contains a `__BUDGET_*` label, record the current address as a region boundary.

The file-to-byte-count mapping comes from tracking which file is "active" (innermost include = top of the include stack) at each ROM address. The size of each file's contribution is the sum of bytes assembled while that file was active.

### Symbol Table Parser

Start parsing when we see the `Symbol Table:` header (or the first symbol-table-formatted line after the source listing ends). Each line has 1-2 entries in the format:

```
[*]NAME : value [C|-] |
```

Parse with a regex. Filter:
- ROM labels: value < `$400000`, type `C`
- RAM labels: value contains `FFFFFFFFFFFF` prefix, type `C`
- Constants: type `-`

### RAM Layout

Collect all RAM-addressed symbols, sort by address, compute sizes as gaps between consecutive symbols. The two phase blocks (lower at `$FFFF0000`, upper at `$FFFF8000`) are identified by address ranges.

Free space = `SYSTEM_STACK` (`$FFFFFF00`) minus the highest RAM symbol's address.

### VRAM Layout

Read VRAM constants from the symbol table (`VRAM_PLANE_A`, `VRAM_PLANE_B`, `VRAM_SPRITE_TABLE`, `VRAM_HSCROLL_TABLE`, `VRAM_WINDOW`, `PLANE_H_CELLS`, `PLANE_V_CELLS`). Compute sizes from the plane dimensions and VDP table sizes.

## CLI Interface

```
python tools/s4budget.py <listing-file> <rom-file> [options]

Positional:
  listing-file    Path to s4.lst
  rom-file        Path to s4.bin

Options:
  --summary       Print compact one-liner only (for build integration)
  --rom-only      Show only ROM budget
  --ram-only      Show only RAM budget
  --vram-only     Show only VRAM budget
  --json          Output as JSON (for tooling integration)
```

## Error Handling

- If `s4.lst` doesn't exist or can't be parsed: print error to stderr, exit 1
- If sentinel labels are missing: fall back to `org`-based region detection (less precise but still useful)
- If `s4.bin` doesn't exist: skip ROM file size, use `EndOfRom` symbol address instead

## What This Tool Does NOT Do

- **Track changes over time** — no history, no trend graphs. Run `git log` and compare sizes if you want trends.
- **Dynamic VRAM allocation** — reports static layout only until the VRAM allocator (§2.2) exists.
- **DMA budget analysis** — per-frame DMA tracking is a runtime concern. `verify_sprites.py` already handles sprite DMA statistics.
- **Unused code detection** — the listing's `unused symbols` count is shown in the stats, but identifying dead code is a deeper analysis (deferred).

## Testing

Unit tests in `tools/test_s4budget.py`:

- Symbol table parsing (ROM labels, RAM labels, constants, unused symbols)
- Source listing parsing (include depth tracking, file-to-address mapping)
- Region detection (sentinel labels present, sentinel labels missing with org fallback)
- RAM layout computation (two phase blocks, free space calculation)
- VRAM layout computation (from constants)
- Summary one-liner formatting
- JSON output format
- Error cases (missing files, malformed listing)
