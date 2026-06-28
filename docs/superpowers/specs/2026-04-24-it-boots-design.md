# "It Boots" Milestone — Full §0 Boot Sequence

The first milestone for the Sonic 4 engine: a ROM that cold boots through the complete hardware initialization sequence described in ENGINE_ARCHITECTURE.md §0, displays a solid-color screen, and runs a stable 60Hz (or 50Hz PAL) main loop.

Built incrementally — each step produces a bootable ROM, verified before moving to the next. MD Debugger v2.6 integrated at step 4 so that 70% of the boot code has proper error reporting during development.

## Scope

**In scope:** Everything in ENGINE_ARCHITECTURE.md §0 (§0.1-§0.11), plus MD Debugger (§8.3) and a minimal game state machine (§9.13).

**Out of scope:** §0.13 Build-Time Data Generation (sine table, RNG) — these are utility data that no boot code uses. They come in naturally when systems that need them are built (player physics, objects). Compression (§2), DMA queue (§1.1), sprites, art loading — all future milestones.

## Architecture References

Every design decision traces back to ENGINE_ARCHITECTURE.md. Section references (§X.Y) point there. CODING_CONVENTIONS.md governs all code style, naming, optimization rules, and AS assembler usage.

---

## Step 0: Project Scaffold & Build Script

### Build Script (`build.sh`)

Minimal fresh pipeline:
1. `asw` (AS Macro Assembler) — assemble `main.asm` into `.p` file
2. `p2bin` — convert AS `.p` output to flat binary ROM
3. `fixheader` — compute and patch ROM checksum

No `rings.exe`, no sonic_hack-specific tools. Environment variables: `AS_MSGPATH`, `USEANSI=n`. Wine used for win32 assembler tools (same as sonic_hack, but independent script).

Debug build support: pass `__DEBUG__` define to assembler for debug/release gating.

### Source Files

| File | Purpose |
|------|---------|
| `main.asm` | Top-level include file, assembly options, include chain |
| `constants.asm` | Hardware addresses ($C00000, $A11100, etc.), ROM constants, enums |
| `macros.asm` | AS functions (`vdpComm`, `vdpReg`, `vram_art`, `vram_bytes`, `sprSize`), hardware macros (`stopZ80`, `startZ80`, `clearRAM`, `dma68kToVDP`, `dmaFillVRAM`), debug macros (`ifdebug`, `debugend`) |
| `structs.asm` | `VDP_Shadow` struct definition |
| `ram.asm` | RAM layout via `phase`/`dephase` with overflow check |

`main.asm` include order follows the architecture: assembly options → constants → structs → macros → RAM layout → engine code.

### Verification

`./build.sh` produces a `.bin` file that assembles without errors.

---

## Step 1: ROM Header + Vector Table

### Vector Table ($000000-$0000FF)

Per §0.1:
- Initial SSP = `$FFFFFF00` (Vectorman/Treasure pattern — stack isolated from game data at low RAM)
- Reset PC = `EntryPoint`
- All exception vectors → temporary halt (replaced by MD Debugger in step 4)
- IRQ4 (HBlank) → `HBlank_Dispatch` (RAM-patched stub)
- IRQ6 (VBlank) → `VBlank_Handler` (ROM-based)
- All other IRQs → `NullInterrupt` (just `rte`)

### ROM Header ($000100-$0001FF)

Standard Sega header: "SEGA GENESIS", "SONIC THE HEDGEHOG 4", serial "GM S4-0001-00", region "JUE". ROM start/end addresses computed by assembler.

### Entry Point

`EntryPoint:` loops forever (`bra.s *`) — placeholder until step 2 adds real init.

### Build-Time Validation

```
- ROM size is even
- ROM does not exceed 4MB (no banking)
```

### Verification

ROM loads in BlastEm/Exodus without crashing. Valid ROM structure confirmed.

---

## Step 2: TMSS Handshake + Soft Reset Detection

### Soft Reset Detection (§0.11)

At `EntryPoint`, before any hardware init:
- Read port A control register ($A10008) — non-zero on soft reset
- Read expansion port control ($A1000C) — second check
- Cold boot: both zero → fall through to `Cold_Boot`
- Warm boot: non-zero → wait for any in-progress DMA to complete (poll VDP status bit 1), then loop (warm boot path is a placeholder until the state machine exists in step 7)

### TMSS Handshake (§0.2)

On cold boot path:
- Read hardware version register ($A10001), isolate revision nibble (bits 3-0)
- Revision 0 (original Model 1): skip TMSS
- Revision > 0: write `$53454741` ("SEGA") to $A14000

### Verification

ROM still boots. TMSS satisfied on Model 2+ hardware.

---

## Step 3: VDP Register Init + Memory Clearing

The largest single step — tightly coupled systems that must execute in a specific order per §0.3, §0.5-§0.7.

### Hardware Address Preload

S.C.E. `movem` pattern: load boot data table containing hardware addresses into a0-a4 and key constants into d5-d7 in two `movem` instructions. Eliminates repeated long-address encoding throughout init.

```
d5 = $8000 (VDP register base)
d6 = loop counter
d7 = $0100 (Z80 bus request value)
a0 = $A00000 (Z80 RAM)
a1 = $A11100 (Z80 bus request)
a2 = $A11200 (Z80 reset)
a3 = $C00000 (VDP data port)
a4 = $C00004 (VDP control port)
```

### VDP Register Init (§0.3)

24 registers ($00-$17) written from compile-time validated table in a `dbf` loop. Key settings:
- Display OFF, VInt OFF, DMA ON (reg $01 = $14)
- 64x64 scroll planes (reg $10 = $11)
- Plane A nametable at $C000 (reg $02 = $30)
- Plane B nametable at $E000 (reg $04 = $07)
- Sprite table at $D800 (reg $05 = $6C)
- HScroll table at $DC00 (reg $0D = $37)
- Auto-increment = 1 for DMA fill (reg $0F = $01)
- DMA source high = fill mode (reg $17 = $80)

Compile-time validation: plane size legal, nametable addresses correct for 64x64 layout, no overlap violations.

### DMA-Parallel Init (§0.7 — NOVEL)

After VDP registers are set, DMA fill is primed. Execution order:

1. **Start VRAM DMA fill** — write destination + trigger word to VDP. DMA fills 64KB VRAM with zeros in the background on VDP's own clock.
2. **While DMA runs (parallel CPU work):**
   - Z80 init (§0.5): assert reset → request bus → wait for bus grant → load Z80 idle program (byte writes to $A00000+) → reset with YM2612-safe delay (~192 cycles) → release bus
   - Work RAM clear: 64KB zeroed via `move.l d0, -(a6)` loop (~180,000 cycles)
   - PSG silence (§0.6): write 4 max-attenuation bytes ($9F, $BF, $DF, $FF) to $C00011
3. **After CPU work:** poll VDP status bit 1, wait for DMA fill completion
4. **Restore auto-increment** to 2 (reg $0F = $02) — fill used 1
5. **Clear CRAM** (128 bytes via CPU loop to VDP data port)
6. **Clear VSRAM** (80 bytes via CPU loop to VDP data port)

### Z80 Idle Program (§0.5)

Loaded during init, runs until Flamedriver replaces it in a later milestone:
- Clear all Z80 RAM via LDIR
- Set IM 1, disable interrupts
- Infinite `jp` loop

### YM2612 Key-Off (§0.6)

After Z80 init, key-off all 6 FM channels (register $28) to silence any leftover voices from soft reset. Requires `stopZ80`/`startZ80` around YM2612 port access.

### Verification

Boots to black screen. No audio garbage. VRAM, CRAM, VSRAM all zeroed (verifiable in Exodus VRAM viewer).

---

## Step 4: MD Debugger v2.6 Integration

The critical inflection point. Every subsequent step gets register dumps and backtraces on failure.

### Integration

- Adapt Vladikcomper's MD Debugger v2.6 from S.C.E.'s copy (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Debugger/`)
- Wire exception vectors in vector table:
  - `BusError` → "BUS ERROR" with address error details
  - `AddressError` → "ADDRESS ERROR" with address error details
  - `IllegalInstr` → "ILLEGAL INSTRUCTION"
  - `ZeroDivide` → "ZERO DIVIDE"
  - `ChkInstr` → "CHK INSTRUCTION"
- `RaiseError` macro available for runtime debug assertions
- Gated by `__DEBUG__` flag — release builds strip all debug code entirely

### Build Script Addition

Add `convsym` to `build.sh` pipeline — generates symbol table from assembler output. MD Debugger uses this for backtrace symbol resolution (shows routine names instead of raw addresses).

### Debug Macros

The `ifdebug`/`debugend` two-phase gating from CODING_CONVENTIONS.md §1.7:
- Master `__DEBUG__` flag gates all debug code
- Per-subsystem flags (`DEBUG_DMA`, `DEBUG_VRAM`, etc.) for granular control
- Zero cost in release builds — code is not assembled at all

### Verification

Insert a deliberate `illegal` instruction after boot init. The error handler displays a crash screen with register values, SR, PC, and backtrace with symbol names. Remove the `illegal` — ROM boots clean. This confirms the entire debug pipeline: assembler → convsym → symbol table → error handler display.

---

## Step 5: VDP Shadow Table + Region Detection + Controller Init

### VDP Shadow Table (§0.4)

RAM-resident mirror of VDP registers $00-$12 (19 registers). Registers $13-$17 (DMA control) are NOT shadowed — they change per-transfer, not per-frame.

- `VDP_Shadow` struct in RAM (defined in `structs.asm`)
- Copy VDP init values into shadow table during boot
- Dirty tracking bitmask: `VDP_Dirty_Mask` (word) for regs $00-$0F, `VDP_Dirty_Mask_Hi` (byte) for regs $10-$12
- `SetVDPReg` macro: writes to shadow + marks dirty bit. All future VDP register writes go through this — never write VDP control port directly.
- `Flush_VDP_Shadow` routine: iterates dirty bits, writes only changed registers to VDP, clears dirty mask. Called during VBlank (step 6).

### Region Detection (§0.8)

- Read version register ($A10001)
- Store full byte as `Hardware_Region`
- Extract bits 7-6 as `Region_Flags` (bit 7 = overseas, bit 6 = PAL)
- Store timing step value: NTSC = $0100, PAL = $0133
- Initialize `Frame_Accumulator` to 0

### Controller Port Init (§0.9)

- Set TH pin as output ($40) on port 1 ($A10009), port 2 ($A1000B), expansion ($A1000D)
- Actual controller reading happens in VBlank (step 6) — boot only sets pin direction

### Verification

Boots clean. Debug assertions can validate shadow table contents match VDP init values. Region flags readable in Exodus memory viewer.

---

## Step 6: Interrupt System

### VBlank Handler (§0.10)

ROM-based, fires once per frame:

```
VBlank_Handler:
  1. Save all registers (movem.l d0-a6, -(sp))
  2. Set VBlank_Flag = 1
  3. bsr.w Flush_VDP_Shadow (from step 5)
  4. bsr.w Read_Controllers (basic joypad reading — TH cycling protocol for 3-button, 6-button detection deferred)
  5. Increment Frame_Counter
  6. Restore all registers
  7. rte
```

Stubs for future additions: DMA queue drain, sprite table upload, sound driver update. These are `bsr.w` targets that just `rts` for now — the call structure is in place so adding them later is non-disruptive.

### HBlank Dispatch (§0.10)

RAM-patched pattern (Vectorman/Batman/Treasure):
- ROM stub at IRQ4 vector: save minimal registers (d0-d1/a0), load `HBlank_Handler_Ptr` from RAM, `jsr (a0)`, restore, `rte`
- Default handler: `HBlank_Null` — just `rts` (~16 cycles total)
- `HBlank_Handler_Ptr` initialized to `HBlank_Null` during boot

### VSync_Wait

Main loop synchronization:
- Loop until `VBlank_Flag` is non-zero
- Clear flag
- Return

### Controller Reading

Basic 3-button joypad reading (full 6-button protocol deferred to a later milestone):
- Read port 1 data register ($A10003) with TH high/low cycling
- Store `Ctrl_1_Held` (current state) and `Ctrl_1_Press` (newly pressed this frame)
- Same for port 2

### Enable Interrupts

- Set VDP reg $01 bit 5 (VInt enable) via `SetVDPReg`
- Set SR to $2300 (supervisor mode, IPL 3 — allows IRQ4/6 through)

### Verification

`Frame_Counter` increments every frame (visible in Exodus memory viewer). `VSync_Wait` returns exactly once per frame. Controller input readable in RAM.

---

## Step 7: Game State Machine + Display Enable

### Game State Machine (§9.13 — minimal)

- `Game_State` (longword in RAM) — pointer to current state's frame routine
- `Game_State_ID` (byte in RAM) — numeric ID for debug display
- `GameLoop`: `bsr.w VSync_Wait` → `movea.l (Game_State).w, a0` → `jsr (a0)` → `bra.s GameLoop`

### Boot State

Single state: `GameState_Boot`
- On first call: write a visible color (blue, $0E00) to CRAM entry 0 via VDP data port (background color)
- Enable display: set VDP reg $01 bit 6 via `SetVDPReg`
- Subsequent frames: do nothing (just `rts`)
- This proves the full pipeline: VSync → state dispatch → VDP shadow flush → visible output

### CrossResetRAM (§0.11)

- Write magic string (`'INIT'`) to fixed RAM address at end of cold boot
- Warm boot path (step 2) checks for this magic — if present, skip full hardware init and preserve designated RAM region
- For this milestone, warm boot still just resets to cold boot behavior. Full warm-boot preservation comes when there's game state worth preserving.

### Verification

Solid blue screen. Stable 60Hz loop (50Hz PAL). Frame counter incrementing. No crashes over extended run time. Soft reset returns to blue screen. The "it boots" milestone is complete.

---

## File Structure (Final State)

After all 7 steps, the project contains:

```
aeon/
  build.sh
  main.asm
  constants.asm
  macros.asm
  structs.asm
  ram.asm
  engine/
    boot.asm            ; TMSS, cold/warm boot, hardware init, DMA-parallel clearing
    vdp_init.asm        ; VDP register table, shadow table init, Flush_VDP_Shadow
    z80_init.asm        ; Z80 idle program, bus control
    psg_ym2612.asm      ; PSG silence, YM2612 key-off
    vblank.asm          ; VBlank handler, VSync_Wait
    hblank.asm          ; HBlank dispatch stub
    controllers.asm     ; Joypad reading (3-button)
    game_loop.asm       ; GameLoop, game state dispatch
  debug/
    error_handler.asm   ; MD Debugger v2.6 integration
  docs/
    ENGINE_ARCHITECTURE.md
    superpowers/specs/
      2026-04-24-it-boots-design.md  (this file)
  CLAUDE.md
  CODING_CONVENTIONS.md
```

Files are created as each step is implemented — no empty stubs created in advance.

## Dependencies & Tools

| Tool | Source | Purpose |
|------|--------|---------|
| `asw` | AS Macro Assembler (win32 via Wine) | Assemble 68000 + Z80 |
| `p2bin` | AS toolchain | Convert .p to flat binary |
| `fixheader` | sonic_hack/win32/ or custom | Compute ROM checksum |
| `convsym` | Vladikcomper md-modules | Generate symbol table for MD Debugger |
| MD Debugger v2.6 | S.C.E. copy or vladikcomper/md-modules | Error handler + backtrace |

## Success Criteria

1. ROM assembles with zero errors and zero warnings
2. ROM boots in BlastEm and Exodus without crashing
3. Solid colored screen displayed at correct refresh rate (60Hz NTSC / 50Hz PAL)
4. VBlank fires and Frame_Counter increments every frame
5. Controller input registers update when buttons are pressed
6. Deliberate `illegal` instruction triggers MD Debugger error screen with register dump and symbol backtrace
7. Soft reset returns to boot state without hanging
8. All code follows CODING_CONVENTIONS.md: sized branches, `function` for compile-time math, `struct` for data structures, `phase`/`dephase` for RAM, PascalCase routines, no `mulu`/`divu`, no unstopped Z80 during VDP access
