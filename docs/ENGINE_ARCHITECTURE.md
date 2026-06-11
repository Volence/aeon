# Sonic 4 Engine Architecture

Target design document for the Sonic 4 engine. Describes the final-state architecture as a coherent system — what each subsystem does, how it works, why this approach was chosen, and how it interacts with other subsystems.

This is the **design bible**. This document describes the engine we're building from scratch in `s4_engine/`.

**Sources:** S.C.E. (Sonic Clean Engine), Batman & Robin (Clockwork Tortoise), Vectorman (BlueSky), Gunstar Heroes (Treasure), Alien Soldier (Treasure), Thunder Force IV (Technosoft), Flamewing's community tools, SGDK (Stephane-D), Amiga demoscene, modern homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg), Titan Overdrive tech demos, Kabuto hardware research, plutiedev, modern engine design principles.

---

## System Index

| # | System | Key Decisions |
|---|--------|---------------|
| 0 | Hardware Init & Boot | SSP at $FFFFFF00 (Treasure/Vectorman — stack isolated from game data), RAM-patched HBlank+VBlank vectors (interrupt dispatch table — modern event system), VDP shadow table with dirty tracking (Batman — only changed registers written during VBlank), DMA-parallel init (VRAM fill runs while CPU clears RAM/inits Z80 — modern async I/O), compile-time VDP register table with AS validation, deterministic cold/warm boot (CrossResetRAM), region detection with PAL timing constants, 6-button controller port init, Z80 init with YM2612-safe timing, build-time sine table generation |
| 1 | Core VDP Pipeline | 3 priority sub-queue DMA, hybrid unrolled/looped drain, static DMA for fixed transfers, variable hscroll dirty tracking, adaptive byte budget, DPLC lookahead, deferred plane buffer, HUD dirty flags |
| 2 | Art & Compression Pipeline | Two-tier compression (measured 2026-06-11): S4LZ v3 (word-aligned LZ + per-section block dictionaries, ~510-640 KB/s) for the runtime block path; ZX0 (~76 KB/s, zlib-class ratio) for load-time tile art. Uncompressed sprite art + improved DPLC/DMA (zero CPU, proven by every commercial Genesis game — UFTC dropped after 0.82-0.86 ratio on real data, see `docs/research/tile-format-survey.md`). Raw tilemaps (menu/level select). **Unified VRAM art pool $000-$5BF (1,472 tiles)**, **64×64 scroll planes** ($9011 — validated by Vectorman, enables ±288px vertical buffer + VSRAM deformation), **build-time tile graph coloring** (NOVEL — non-adjacent sections reuse VRAM indices, zero-DMA transitions), **character sprites + VDP tables embedded in off-screen nametable rows**. Dynamic VRAM allocator (novel — no Genesis game does this), refcount-based art caching with lazy reclaim, per-section tile art (~22KB RAM saved), per-section BG support. DPLC improvements: lookahead (NOVEL — predictive pre-load), priority integration, generic Perform_DPLC, build-time contiguous art layout. Nemesis/Kosinski/Comper/Enigma/UFTC not used |
| 3 | Object System | $50 SST with hot/cold reorder (novel), free slot stack O(1) allocation (beats all references), data-driven child creation (4 strategies from S.C.E.), collision_response type dispatch with width/height from SST (novel — more modular than any reference), animation events as behavior sequencer (novel), per-frame delays, multi-sprite animation, per-frame art via DPLC/DMA from uncompressed ROM, **sprite link-order cycling (overflow fairness)**, **sprite X=0 masking (hardware clipping)**, **scanline-aware sprite budgeting** |
| 4 | Level / World | 2D section grid with signed Y (novel), 2-slot bidirectional leapfrog (novel), block-based 2D tile cache (Batman — eliminates chunks/blocks from RAM), deferred plane buffer (S.C.E.+overflow fix), 8-layer computed parallax with dual FG/BG deformation + per-block linear interpolation (TF4+S.C.E.), velocity-based preload, per-section everything, diagonal preview loading, **camera-driven entity window with 3×3 rolling collected bitmask (novel)**, per-section type tables, flat X-sorted ring lists, unified ring buffer with 3×3 rolling collected bitmask, **zero-lag teleport (progressive nametable preload + palette crossfade, novel)**, player position history buffer, state-dependent camera speed caps, dynamic terrain override, scroll table pre-computation over HInt where possible, **collision embedded in block data (S.C.E.-style per-placement, zero separate maps)**, **per-section full palette copies (128 bytes, instant load)** |
| 5 | Player / Character | 6-button controller support, per-section terrain physics (novel), air drag apex-only fix (S3K), roll-jump air control fix (S3K), flat acceleration with per-character tuning, angle continuity for loop stability, vector projection on slope landing, state entry/exit hooks, hierarchical state machine evaluation, landing camera lock, spindash charge curve (table-based), slope muls→shift optimization, configurable physics tables, 3-character shared code via Player_Common, shield system unified, **SWAP-based 16.16 fixed point (Treasure)** |
| 6 | Audio | Flamedriver (full Z80 autonomy), Zyrinx log volume + per-algorithm carrier mask, verified Z80 writes, DPCM + 32kHz DAC + DMA protection buffering (24KB survival), YM Timer A sub-frame tempo (NTSC/PAL independent), bank switch optimization (pack per-section, 100+ cycle savings), section-aware sound banking (novel), distance-based attenuation (novel), pseudo-stereo DAC, PSG pause silencing, Ch3 special mode for sound design, **SSG-EG envelope modes (evolving FM tones)**, LFO limitations documented, continuous SFX, music fade state machine, build-time DC offset tool, **multi-channel DAC mixing (2-4 channels, per-channel sample rate)** |
| 7 | Visual Effects | **Unified raster command table (Batman — stackable per-scanline VDP register changes)**, Shadow/Highlight hardware lighting (novel for platformers — zero CPU cost), per-scanline palette gradients (Sonic 3 technique, **CRAM/VSRAM 2x active-display DMA speed**), computed water palette (novel), palette cross-fading, white/negative flash effects, window plane HUD + dynamic letterboxing, 16-oscillator system (S.C.E.), screen shake, 512-entry sine table, compound rotation (Batman), effect sequencer, line+column pseudo-rotation, display-disable burst DMA (advanced), mid-frame nametable register swapping (Batman — multi-layer Plane B), mid-frame VSRAM manipulation (Batman — per-scanline column deformation), **FIFO slot-precise mid-scanline writes (Titan Overdrive)**, hit-stop/freeze frames, SNES-style S/H transparency (2024), **sprite cache table-switching (Bloodlines — free water reflections)**, **vertical border opening (Kabuto — 19 extra NTSC scanlines)**, **sprite mapping format — VDP-order reorder (8 bytes/piece)**, **palette cycling animation (Jon Burton — 4x frames from CRAM cycling)**, **Project MD reflection floor**, **interlace Mode 2 (320x448, available for high-res overlays)** |
| 8 | Tooling & Build | **Authoring pipeline (tile/block/chunk editor stamps → build tool: flatten, deduplicate, graph-color VRAM, generate block data with embedded collision + S4LZ art)**, **level editor tile budget UI (per-section shared/unique counts, per-corner budget view, warning system)**, pre-computed nametable build tool, **debug system architecture (S.C.E. two-phase gating + 10 per-subsystem toggles)**, **MD Debugger v2.6 error handler (backtrace, symbol resolution, console programs)**, **per-module debug assertions (S.C.E. + Vectorman pointer bounds/breadcrumbs/corruption detection + CHK instruction)**, **frame profiler (raster bars + VDP window lagometer + KDebug + lag detection + stack guard + watchdog)**, RAM layout documentation, build system improvements (jump sizing 10-50x speedup, dual build targets, convsym pipeline, assembly pass checking, compile-time validation), Exodus MCP integration, level editor integration |
| 9 | Cross-Cutting Systems | Level database (unified descriptors, S.C.E. levartptrs evolution), object communication (Treasure parent-child links + S.C.E. trigger array + boss event buffer), error handler with stack guard (Batman high-byte vector IDs + watchdog), 6-button controller (rapid TH cycling protocol + detection), **soft-reset persistence (CrossResetRAM cold/warm boot detection)**, SRAM save system (Sonic 3 dual-copy checksums), **cooperative multitasking (NOVEL — supervisor/user mode context switching, background S4LZ decompression)**, **ROM banking awareness (SSF2 mapper, conditional on ROM >4MB)**, **128KB VRAM mode (investigated, Kabuto byte-wide DMA)**, **PC-relative addressing audit (Batman leads with 986 refs)**, **clearRAM performance variants (3 S.C.E. macros + MOVEM bulk clear)**, **game state machine (function pointer dispatch, 11 states)**, **text/font rendering (96-char ASCII, DrawString/DrawHex/DrawDecimal)**, **screen/menu system (lifecycle init/update, title cards, credits)** |

---

## 0. Hardware Initialization & Boot Sequence

The foundation everything else sits on. This section covers the first ~2000 cycles of execution: ROM header, exception vectors, TMSS handshake, VDP/Z80/PSG init, RAM clearing, region detection, and the transition into the game state machine. Every design here is informed by what Vectorman, Batman & Robin, Treasure (Gunstar/Alien Soldier), Thunder Force IV, and S.C.E. actually do on real hardware, cross-referenced with plutiedev, Kabuto, md.railgun.works, and modern engine initialization patterns.

### 0.1 ROM Header & Vector Table

**Vector Table** ($000000-$0000FF, 64 longwords):

The first 256 bytes of ROM are the 68000 exception vector table. Two entries matter most:

| Vector | Offset | Our Value | Purpose |
|--------|--------|-----------|---------|
| Initial SSP | $000000 | `$FFFFFF00` | Stack pointer — high RAM, away from game data |
| Reset PC | $000004 | `EntryPoint` | First instruction after power-on or reset |
| Bus Error | $000008 | `ExceptionHandler` | Invalid bus cycle |
| Address Error | $00000C | `ExceptionHandler` | Odd-address word/long access |
| Illegal Instruction | $000010 | `ExceptionHandler` | Invalid opcode |
| Division by Zero | $000014 | `ExceptionHandler` | `divu`/`divs` with divisor 0 |
| CHK Exception | $000018 | `ExceptionHandler` | CHK instruction out of bounds |
| TRAPV | $00001C | `ExceptionHandler` | Overflow trap |
| Privilege Violation | $000020 | `ExceptionHandler` | User-mode restricted instruction |
| Trace | $000024 | `ExceptionHandler` | Single-step debugging |
| Line 1010 | $000028 | `ExceptionHandler` | Unimplemented A-line trap |
| Line 1111 | $00002C | `ExceptionHandler` | Unimplemented F-line trap |
| Reserved | $000030-$000060 | `ExceptionHandler` | 12 reserved vectors |
| Spurious Interrupt | $000060 | `ExceptionHandler` | Uninitialized interrupt |
| IRQ1 (External) | $000064 | `NullInterrupt` | External device (unused) |
| IRQ2 (External) | $000068 | `NullInterrupt` | External device (unused) |
| IRQ3 | $00006C | `NullInterrupt` | Unused on Genesis |
| IRQ4 (HBlank) | $000070 | `HBlank_Dispatch` | **RAM-patched** — reads handler pointer from RAM |
| IRQ5 | $000074 | `NullInterrupt` | Unused on Genesis |
| IRQ6 (VBlank) | $000078 | `VBlank_Handler` | Vertical blanking interrupt |
| IRQ7 (NMI) | $00007C | `NullInterrupt` | Non-maskable (unused on standard hardware) |
| TRAP #0-15 | $000080-$0000BC | `ExceptionHandler` | 16 TRAP vectors — used for debug system |
| Reserved | $0000C0-$0000FF | `ExceptionHandler` | Remaining reserved vectors |

**Design decisions:**

- **SSP = $FFFFFF00** (not $00000000): Vectorman, Gunstar Heroes, and Alien Soldier all use high RAM. Stack grows downward from near-top of 64KB RAM, staying far from game data at low RAM addresses. $00000000 (used by S.C.E., Batman, Thunder Force IV) makes the stack grow down from the very bottom of the address space — wrapping bugs are silent and catastrophic. $FFFFFF00 gives 256 bytes of headroom below the RAM ceiling ($FFFFFFFF), which is sufficient since our deepest call chain is audited.
- **RAM-patched HBlank**: The vector table entry at $70 points to a tiny ROM stub that reads and jumps through a pointer in RAM. This allows swapping raster effect handlers per-section without modifying ROM. Vectorman ($FFFF9D2E), Batman ($FFFFE560), Gunstar/Alien Soldier ($FFFFEE00) all do this. Thunder Force IV is the only holdout (ROM-based), and it can't change HBlank behavior between levels.
- **VBlank in ROM**: Unlike HBlank (which changes per-section), VBlank always does the same core work: drain DMA queue, update sprites, read controllers, process sound, set VBlank flag. A single ROM handler with conditional dispatch is sufficient.
- **Exception routing**: All exceptions go to `ExceptionHandler` which integrates with the MD Debugger v2.6 error handler (§8.3). In debug builds this shows register dumps, backtraces, and symbol resolution. In release builds it does a soft reset.
- **TRAP vectors**: Reserved for the debug system. TRAP #0 can be wired to `RaiseError` for debug assertions. Other TRAPs available for future use (e.g., system calls for cooperative multitasking §9.7).

**ROM Header** ($000100-$0001FF):

Standard Sega header format, populated at build time:

```
$100: "SEGA GENESIS    "          ; Console name (TMSS requires "SEGA" at $100)
$110: "(C)     2026.XXX"          ; Copyright
$120: "SONIC THE HEDGEHOG 4                    "  ; Domestic name (48 bytes)
$150: "SONIC THE HEDGEHOG 4                    "  ; Overseas name (48 bytes)
$180: "GM S4-0001-00   "          ; Serial/version
$18E: dc.w Checksum                ; Computed by fixheader tool
$190: "J               "          ; I/O support (J = 3/6-button joypad)
$1A0: dc.l $00000000               ; ROM start
$1A4: dc.l ROM_End-1               ; ROM end (computed by assembler)
$1A8: dc.l $00FF0000               ; RAM start
$1AC: dc.l $00FFFFFF               ; RAM end
$1B0-$1EF: Zeroed                  ; No SRAM/modem (SRAM handled in software §9.6)
$1F0: "JUE             "          ; Region: Japan + US + Europe
```

**Build-time validation** (AS catches errors before we ever run):

```asm
    if (ROM_End & 1) <> 0
      error "ROM size is odd — padding error"
    endif
    if ROM_End > $3FFFFF
      error "ROM exceeds 4MB without banking"
    endif
```

### 0.2 TMSS Handshake

The Trademark Security System exists on Model 1 VA7+ and all Model 2/3 units. If TMSS is present but not satisfied, the next VDP data port access hangs the CPU permanently.

```asm
EntryPoint:
        tst.l   ($A10008).l         ; Port A control register — non-zero on soft reset
        bne.s   .warm_boot          ; Skip hardware init on soft reset (§9.5 CrossResetRAM)
        tst.w   ($A1000C).l         ; Expansion port control — second soft-reset check
.cold_boot:
        move.b  ($A10001).l, d0     ; Read version register
        andi.b  #$F, d0             ; Isolate hardware revision nibble
        beq.s   .no_tmss            ; Revision 0 = original Model 1 (no TMSS)
        move.l  #$53454741, ($A14000).l  ; Write "SEGA" to TMSS register
.no_tmss:
```

**Why this order:** The soft-reset detection (port A control + expansion control) must come before TMSS because on soft reset, VDP state is already initialized — reinitializing could corrupt in-progress DMA or VRAM state. S.C.E. does exactly this check. On cold boot (power-on), both port registers read zero.

### 0.3 VDP Register Initialization

24 VDP registers ($00-$17) configured from a compile-time validated table. During init, display is OFF and DMA is enabled — this allows DMA fill of VRAM while the CPU continues working.

**Register table** (values chosen for our 64×64 plane, unified-pool VRAM layout from §2.3):

| Reg | Value | Setting | Why |
|-----|-------|---------|-----|
| $00 | `$04` | Mode 5 enabled, HInt OFF, HV counter readable | HInt enabled later per-section |
| $01 | `$14` | Display OFF, VInt OFF, DMA ON, V28 (224px), M5 | Display enabled after init completes |
| $02 | `$30` | Plane A nametable at $C000 | §2.3 — tile $600 × 32 = byte $C000, reg bits 5-3 = 6 → $30 |
| $03 | `$3C` | Window nametable at $F000 | HUD overlay, letterboxing (§7) |
| $04 | `$07` | Plane B nametable at $E000 | §2.3 — tile $700 × 32 = byte $E000, reg bits 2-0 = 7 → $07 |
| $05 | `$5C` | Sprite attribute table at $B800 | 80 sprites × 8 bytes = 640 bytes |
| $06 | `$00` | Sprite generator base (normal mode) | Not used in standard 64KB VRAM |
| $07 | `$00` | Background color = palette 0, entry 0 | Black background default |
| $08 | `$00` | Unused (Master System compat) | Must be zero |
| $09 | `$00` | Unused (Master System compat) | Must be zero |
| $0A | `$FF` | HInt counter = every 256 lines | Effectively disabled until gameplay |
| $0B | `$00` | Full-screen VScroll, full-screen HScroll | Changed per-section for effects (§7.2) |
| $0C | `$81` | H40 (320px), no interlace, no S/H | S/H enabled per-section (§7.3) |
| $0D | `$37` | HScroll table at $DC00 | 224 entries × 4 bytes for per-line scroll |
| $0E | `$00` | Nametable generator base (normal mode) | Not used in standard 64KB VRAM |
| $0F | `$01` | Auto-increment = 1 byte | Set to 1 for DMA fill (byte-by-byte), reset to 2 after fill completes |
| $10 | `$11` | **64×64 cell scroll planes** | §2.3 — validated by Vectorman, enables vertical streaming |
| $11 | `$00` | Window H pos = disabled | Enabled dynamically for HUD (§7) |
| $12 | `$00` | Window V pos = disabled | Enabled dynamically for letterbox (§7) |
| $13 | `$FF` | DMA length low = $FF | Set per-transfer, init value doesn't matter |
| $14 | `$FF` | DMA length high = $FF | Set per-transfer |
| $15 | `$00` | DMA source low | Set per-transfer |
| $16 | `$00` | DMA source mid | Set per-transfer |
| $17 | `$80` | DMA source high = fill mode | Primes VRAM fill for clearing |

**Reg $02/$04 calculation for our VRAM layout:**

```asm
; §2.3 VRAM map:
;   $000-$5BF  = art pool (1,472 tiles)
;   $600-$6FF  = Plane A nametable (64×64 = 8KB)
;   $700-$7FF  = Plane B nametable (64×64 = 8KB)
;
; Tile-to-byte conversion: tile_index × 32 bytes/tile
;   Tile $600 × 32 = byte $C000 (Plane A)
;   Tile $700 × 32 = byte $E000 (Plane B)
;
; VDP nametable register encoding:
;   Reg $02 bits 5-3 = address / $2000.  $C000/$2000 = 6 → bits %110 → reg = $30
;   Reg $04 bits 2-0 = address / $2000.  $E000/$2000 = 7 → bits %111 → reg = $07
;
; With 64×64 planes, each nametable is 64×64×2 = 8,192 bytes = $2000.
; Plane A: $C000-$DFFF. Plane B: $E000-$FFFF. They fill VRAM exactly.
; Sprite table at $B800 overlaps Plane A nametable — $B800-$BA7F (640 bytes)
; are sprite entries occupying "off-screen" nametable cells (no visual conflict).
```

**Compile-time validation of register table:**

```asm
; AS function for VDP register command
vdpReg  function reg,val, ($8000 | ((reg) << 8) | (val))

; Plane size validation
PLANE_H_CELLS = 64
PLANE_V_CELLS = 64
    if (PLANE_H_CELLS <> 32) && (PLANE_H_CELLS <> 64) && (PLANE_H_CELLS <> 128)
      error "Invalid horizontal plane size: \{PLANE_H_CELLS}"
    endif
    if PLANE_H_CELLS * PLANE_V_CELLS > 4096
      error "Plane exceeds 8KB: \{PLANE_H_CELLS}x\{PLANE_V_CELLS} = \{PLANE_H_CELLS*PLANE_V_CELLS} entries"
    endif
```

**Init method — preloaded register approach** (from S.C.E., used by every commercial game):

```asm
; Pack hardware addresses into registers with movem (S.C.E. pattern)
        lea.l   BootData(pc), a5
        movem.w (a5)+, d5-d7        ; d5=$8000 (VDP reg base), d6=$3FFF (RAM loop), d7=$0100 (Z80 bus)
        movem.l (a5)+, a0-a4        ; a0=Z80_RAM, a1=Z80_Bus, a2=Z80_Reset, a3=VDP_Data, a4=VDP_Ctrl

; Write 24 VDP registers from table
        moveq   #23, d0
.vdp_loop:
        move.b  (a5)+, d5           ; Load register value into low byte of d5
        move.w  d5, (a4)            ; Write $80xx to VDP control port
        addi.w  #$100, d5           ; Advance to next register number
        dbf     d0, .vdp_loop
```

### 0.4 VDP Shadow Table — RAM-Resident Register Mirror (from Batman & Robin)

**Source:** Batman & Robin (`main_loop.asm:4579-4584`) bulk-writes all 19 gameplay VDP registers from a RAM table every VBlank. Alien Soldier does the same. This is the GPU state object pattern from modern 3D engines, adapted for VDP.

**Design:**

```asm
    struct VDP_Shadow
vdp_mode1           ds.b 1      ; reg $00
vdp_mode2           ds.b 1      ; reg $01
vdp_plane_a         ds.b 1      ; reg $02
vdp_window          ds.b 1      ; reg $03
vdp_plane_b         ds.b 1      ; reg $04
vdp_sprite          ds.b 1      ; reg $05
vdp_sprite_gen      ds.b 1      ; reg $06
vdp_bgcolor         ds.b 1      ; reg $07
vdp_unused08        ds.b 1      ; reg $08
vdp_unused09        ds.b 1      ; reg $09
vdp_hint_rate       ds.b 1      ; reg $0A
vdp_mode3           ds.b 1      ; reg $0B
vdp_mode4           ds.b 1      ; reg $0C
vdp_hscroll         ds.b 1      ; reg $0D
vdp_nametable_gen   ds.b 1      ; reg $0E
vdp_increment       ds.b 1      ; reg $0F
vdp_plane_size      ds.b 1      ; reg $10
vdp_window_h        ds.b 1      ; reg $11
vdp_window_v        ds.b 1      ; reg $12
    endstruct VDP_Shadow
; Registers $13-$17 (DMA) are NOT shadowed — they are set per-transfer by the DMA queue.
```

**Why shadow only $00-$12** (19 registers, not 24): Registers $13-$17 control DMA source/length/mode and are set immediately before each DMA transfer by the queue system (§1.1). Shadowing them would be wrong — they change per-transfer, not per-frame.

**Dirty tracking** (NOVEL — no reference game does this):

Batman and Alien Soldier bulk-write all 19 registers every VBlank regardless of changes. That's 19 × `move.b`/`move.w` pairs = ~190 cycles. For most frames, only 1-3 registers actually change (background color, scroll mode, window position).

```asm
; Modern approach: dirty-bit bitmask
VDP_Dirty_Mask:     ds.w 1      ; 16-bit mask, one bit per register $00-$0F
                                ; Bit 0 = reg $00, bit 1 = reg $01, etc.
VDP_Dirty_Mask_Hi:  ds.b 1      ; 3-bit mask for registers $10-$12
```

**Write-through macro** (game code uses this, never writes VDP directly):

```asm
SetVDPReg macro reg, val
        move.b  val, VDP_Shadow+\reg    ; Update shadow
        ori.w   #(1<<(\reg)), (VDP_Dirty_Mask).w   ; Mark dirty
        endm

; VBlank flush — only writes changed registers
Flush_VDP_Shadow:
        move.w  (VDP_Dirty_Mask).w, d6
        beq.s   .no_changes             ; Fast path: nothing dirty
        lea.l   (VDP_Shadow_Table).w, a0
        move.w  #$8000, d5
        moveq   #18, d4                 ; 19 registers (0-18)
.loop:
        btst    d4, d6
        beq.s   .skip
        move.b  (a0,d4.w), d5          ; Read shadow value
        move.w  d5, (a4)               ; Write to VDP
.skip:
        addi.w  #$100, d5
        dbf     d4, .loop
        clr.w   (VDP_Dirty_Mask).w     ; Reset dirty flags
.no_changes:
        rts
```

**Tradeoff:** The dirty tracking adds overhead when registers DO change (~8 extra cycles per changed register for the btst/branch). But it saves ~150 cycles on frames where nothing changes, which is most gameplay frames. Net win for our engine where HInt handler changes happen at section boundaries, not every frame.

**Fallback:** If profiling shows dirty tracking isn't worth it, revert to Batman's bulk-write approach. 190 cycles is only ~4.4% of VBlank and is completely predictable.

**Direct VDP register-write conventions** (audited 2026-04-27, see `docs/superpowers/specs/2026-04-27-vdp-shadow-dma-audit-design.md`):

The `setVDPReg` macro is the only sanctioned write path for **persistent** frame state on registers `$00-$12`. Direct writes to those registers (e.g., `move.w #$8Fxx, (VDP_CTRL).l`) are permitted **only** for transient setup that the caller fully controls and that does not represent shared frame state:

1. **Pre-DMA autoincrement (`$0F`) configuration.** Caller sets `$8Fxx` immediately before a VRAM/CRAM/VSRAM transfer; subsequent transfers either tolerate the value or restore it. Examples: `engine/level/bg.asm`, `engine/level/plane_buffer.asm`. Shadow drift is harmless because nothing reads back the shadow as authoritative state — `Flush_VDP_Shadow` only writes registers whose dirty bit is set.
2. **HInt-handler-internal raster effects (future §7.2).** HInt handlers may freely write VDP registers during the active line — that's the entire point of raster effects. They MUST NOT update the shadow or set the dirty mask. The shadow represents settled frame state, not transient mid-frame VDP changes. When the section's HInt program exits, hardware register state is whatever the last write left; the next VBlank's `Flush_VDP_Shadow` re-asserts settled values for any dirty registers, and HInt handlers re-establish their own per-line program from scratch.
3. **DMA register writes (`$13-$17`)** are not shadowed and are set per-transfer by the DMA queue. This is by design — `setVDPReg` only covers `$00-$12`.

**Hard rule:** any direct VDP write to `$00-$12` that represents settled state (display enable, scroll mode, plane base, etc.) MUST go through `setVDPReg`. Bypassing the shadow for settled state risks the next dirty-flush overwriting a hardware-only change with a stale shadow value. Audit grep: `grep -rEn 'move\.w\s+#\$8[0-9A-Fa-f]|#\$9[0-2][0-9A-Fa-f]' engine/` periodically; classify each new hit as transient (OK) or settled (use shadow).

### 0.5 Z80 Initialization & Sound System Bootstrap

**Z80 bus control registers:**

| Register | Address | Write |
|----------|---------|-------|
| Bus Request | `$A11100` | `$0100` = request, `$0000` = release |
| Reset | `$A11200` | `$0100` = run, `$0000` = assert reset |
| Z80 RAM | `$A00000-$A01FFF` | 8KB, **byte writes only** |

**Init sequence** (with YM2612-safe timing):

```asm
; Phase 1: Assert reset, request bus
        move.w  #$0000, (a2)            ; Assert Z80 reset (active low)
        move.w  d7, (a1)                ; Request Z80 bus (d7 = $0100)
        move.w  d7, (a2)                ; Release Z80 reset

; Phase 2: Wait for bus grant
.wait_z80:
        btst    #0, (a1)                ; Poll bus grant
        bne.s   .wait_z80              ; Loop until Z80 stops

; Phase 3: Load Z80 idle program (byte writes!)
        lea.l   Z80_IdleProgram(pc), a6
        moveq   #Z80_IdleProgramSize-1, d0
.load_z80:
        move.b  (a6)+, (a0)+            ; Copy to Z80 RAM
        dbf     d0, .load_z80

; Phase 4: Reset with YM2612-safe delay
        move.w  #$0000, (a2)            ; Assert reset
        moveq   #25, d0                 ; ~200 cycles delay (YM2612 needs ≥192)
.ym_delay:
        dbf     d0, .ym_delay
        move.w  d7, (a2)                ; Release reset — Z80 starts running idle loop
        move.w  #$0000, (a1)            ; Release bus — Z80 has control
```

**Z80 idle program** (runs after init, before Flamedriver loads):

```z80
; Clear all Z80 RAM via LDIR, set IM 1, loop forever
        xor     a
        ld      bc, $1FF9               ; 8KB - overhead
        ld      de, $0001
        ld      hl, $0000
        ld      sp, $2000               ; Stack at top of Z80 RAM
        ld      (hl), a                 ; Zero first byte
        ldir                            ; Fill rest
        pop     ix                      ; Clear IX
        pop     iy                      ; Clear IY
        ld      i, a                    ; Clear I
        ld      r, a                    ; Clear R
        di                              ; Disable Z80 interrupts
        im      1                       ; Interrupt mode 1
.idle:
        jp      .idle                   ; Wait for Flamedriver load
```

**Flamedriver loading** happens later, during the game state machine's title screen init. The boot sequence only needs the Z80 idle — loading the full sound driver during boot would waste time before we need sound.

**Critical hardware rule** (from plutiedev): Always stopZ80 before any DMA transfer. If Z80 accesses the 68K bus during DMA (e.g., reading ROM for music data), DMA loads garbage. This is not optional — it corrupts art on real hardware, especially early board revisions.

### 0.6 PSG Silence & YM2612 Reset

**PSG** ($C00011, SN76489 — 3 tone + 1 noise channel):

Volume attenuation of $F = silent. Each channel has a latch byte format: `1 CC 1 AAAA` where CC = channel, AAAA = attenuation.

```asm
; Silence table — 4 bytes
PSG_Silence:  dc.b $9F, $BF, $DF, $FF  ; Channels 0-3 at max attenuation

; Init code
        lea.l   PSG_Silence(pc), a6
        moveq   #3, d0
.silence_psg:
        move.b  (a6)+, $11(a3)          ; a3 = $C00000 (VDP data), +$11 = PSG input
        dbf     d0, .silence_psg
```

**YM2612 reset** (FM synth at $A04000-$A04003):

The Z80 idle program handles this implicitly by clearing Z80 RAM (which includes the YM2612 register cache). But on soft reset, leftover FM voices may still be sounding. Explicit silence:

```asm
; Key-off all 6 FM channels (register $28)
        stopZ80
        lea.l   ($A04000).l, a0
        move.b  #$28, (a0)             ; Select Key On/Off register
        moveq   #2, d1                 ; Channels 0-2 (Part I)
.keyoff_part1:
        move.b  d1, 1(a0)              ; Key off (all operators off, channel = d1)
        dbf     d1, .keyoff_part1
        moveq   #6, d1                 ; Channels 3-5 (Part II: $04, $05, $06)
        moveq   #2, d0
.keyoff_part2:
        move.b  d1, 1(a0)
        subq.w  #1, d1
        dbf     d0, .keyoff_part2
        startZ80
```

### 0.7 Memory Clearing — DMA-Parallel Pattern (NOVEL)

**Key insight from modern async I/O:** DMA fill runs on the VDP's own clock, independent of the 68000. While VRAM fills, the CPU can clear Work RAM, init the Z80, and silence PSG simultaneously. No reference game exploits this during boot — they all wait serially.

**Sequence:**

```
1. Prime DMA fill (set regs $13-$17 during VDP init — already done in §0.3)
2. Start VRAM fill: write destination + trigger word to VDP → DMA runs in background
3. While DMA runs: clear 68K RAM (64KB = ~180,000 cycles)
4. While DMA runs: init Z80, silence PSG
5. After CPU work: poll DMA busy bit, wait for fill to complete
6. Clear CRAM (128 bytes — fast CPU loop)
7. Clear VSRAM (80 bytes — fast CPU loop)
```

**Work RAM clear** (64KB, ~180,000 cycles):

```asm
        moveq   #0, d0
        movea.l d0, a6                  ; a6 = $00000000
        move.w  #$3FFF, d6             ; 16384 longwords = 65536 bytes
.clear_ram:
        move.l  d0, -(a6)              ; Write zero, decrement address
        dbf     d6, .clear_ram         ; a6 wraps: $00000000 → $FFFFFFFC → ... → $FFFF0000
```

**CRAM clear** (128 bytes = 64 colors):

```asm
        move.l  #$C0000000, (a4)       ; vdpComm($0000, CRAM, WRITE)
        moveq   #$1F, d0              ; 32 longwords
.clear_cram:
        move.l  d1, (a3)               ; d1 = 0, a3 = VDP data port
        dbf     d0, .clear_cram
```

**VSRAM clear** (80 bytes = 40 scroll values):

```asm
        move.l  #$40000010, (a4)       ; vdpComm($0000, VSRAM, WRITE)
        moveq   #$13, d0              ; 20 longwords
.clear_vsram:
        move.l  d1, (a3)
        dbf     d0, .clear_vsram
```

**DMA Fill cannot clear CRAM or VSRAM** — it only works on VRAM. CPU loops are required for those, but they're small (128 + 80 bytes = ~210 cycles total).

### 0.8 Region Detection & Timing Constants

**Version register** ($A10001):

```
Bit 7: MODE  — 0 = Domestic (Japan), 1 = Overseas (US/Europe)
Bit 6: VMOD  — 0 = NTSC (60Hz), 1 = PAL (50Hz)
Bit 5: DISK  — 0 = FDD connected, 1 = no FDD
Bit 4: Reserved
Bits 3-0: VER — Hardware revision
```

**Timing constants** derived from region:

| Parameter | NTSC | PAL |
|-----------|------|-----|
| Frame rate | 60 Hz | 50 Hz |
| Scanlines/frame | 262 | 312 |
| Active display | 224 lines (V28) | 224 or 240 lines (V30) |
| VBlank lines | ~38 | ~72 (PAL has nearly **double** VBlank time) |
| CPU clock | 7,670,454 Hz | 7,600,489 Hz |
| Cycles/scanline | ~488 | ~488 |
| VBlank cycles | ~18,500 | ~35,100 |
| DMA bandwidth/VBlank | ~7.5 KB (NTSC) | ~14 KB (PAL) |

**Design — compile-time AND runtime constants:**

```asm
; Detection (runs once at boot)
        move.b  ($A10001).l, d0
        move.b  d0, (Hardware_Region).w ; Store full byte for later queries
        andi.b  #$C0, d0
        move.b  d0, (Region_Flags).w    ; Bit 7 = overseas, bit 6 = PAL

; Runtime queries (branching)
        btst    #6, (Region_Flags).w
        bne.s   .pal_timing

; Compile-time constants for the common case (NTSC)
NTSC_VBLANK_LINES      = 38
PAL_VBLANK_LINES        = 72
NTSC_CYCLES_PER_VBLANK  = 18500
PAL_CYCLES_PER_VBLANK   = 35100
DMA_BUDGET_NTSC         = 7200      ; usable DMA bytes per VBlank
DMA_BUDGET_PAL          = 15000     ; usable DMA bytes per VBlank
```

**PAL compensation** (from modern frame-rate independent design):

PAL runs at 50Hz vs NTSC's 60Hz. Physics must compensate or the game plays 17% slower. Two approaches:

1. **Speed multiplier** (Sonic 3 approach): multiply velocities by 6/5 on PAL. Simple but introduces rounding drift.
2. **Frame skip** (Treasure approach): run two game logic ticks every 5th frame. Maintains exact NTSC behavior but causes occasional visual stutter.
3. **Fixed timestep accumulator** (modern approach, NOVEL for Genesis): accumulate real time, consume fixed 1/60s ticks. On PAL, every 5th frame accumulates enough for 2 ticks. Same as approach 2 but expressed as a general-purpose system.

We use approach 3 — the accumulator. It handles both PAL compensation and future lag-frame recovery (if a frame takes >100% CPU, the accumulator catches up next frame rather than permanently falling behind).

```asm
; In RAM
Frame_Accumulator:      ds.w 1      ; 8.8 fixed-point, incremented by TIMING_STEP each frame
NTSC_TIMING_STEP        = $0100     ; 1.0 — one tick per frame
PAL_TIMING_STEP         = $0133     ; 1.2 — 6/5 ratio, so every 5 frames we get 6 ticks
```

### 0.9 Controller Port Initialization

**I/O control registers:**

| Port | Data | Control |
|------|------|---------|
| Port 1 (player 1) | `$A10003` | `$A10009` |
| Port 2 (player 2) | `$A10005` | `$A1000B` |
| Expansion | `$A10007` | `$A1000D` |

**Init** (TH pin as output for joypad protocol):

```asm
        move.b  #$40, ($A10009).l       ; Port 1: TH = output
        move.b  #$40, ($A1000B).l       ; Port 2: TH = output
        move.b  #$40, ($A1000D).l       ; Expansion: TH = output
```

6-button detection and full controller reading protocol are in §9.4. Boot only sets pin direction — actual polling happens in VBlank.

### 0.10 Interrupt System — Dispatch Architecture

**VBlank (IRQ6) — function pointer dispatch with lag detection (implemented in §1):**

```asm
VBlank_Handler:
        movem.l d0-a6, -(sp)
        tst.b   (VBlank_Ready).w        ; Main loop signals readiness each frame
        beq.s   .lag
        movea.l (VInt_Ptr).w, a0        ; Dispatch through RAM pointer (VInt_Level, etc.)
        jsr     (a0)
        bra.s   .done
.lag:
        bsr.w   VInt_Lag                ; Minimal handler — Critical DMA only
.done:
        clr.b   (VBlank_Ready).w
        movem.l (sp)+, d0-a6
        rte
```

`VInt_Level` (normal frames) runs: stopZ80 → Flush_VDP_Shadow → VSRAM write → Enqueue_Dirty_Buffers → Process_DMA_Critical → budget set → Process_DMA_Important → Process_DMA_Deferrable → startZ80 → Read_Controllers → frame counter → VBlank_Flag. `VInt_Lag` runs only Critical DMA and controllers. See §1.4 for details.

**HBlank (IRQ4) — RAM-patched dispatch** (Vectorman/Batman/Treasure pattern):

```asm
; ROM stub (in vector table, never changes)
HBlank_Dispatch:
        movem.l d0-d1/a0, -(sp)        ; Save minimal registers
        movea.l (HBlank_Handler_Ptr).w, a0  ; Read handler pointer from RAM
        jsr     (a0)                    ; Call current handler
        movem.l (sp)+, d0-d1/a0
        rte

; In RAM
HBlank_Handler_Ptr:     ds.l 1          ; Swapped per-section for raster effects (§7.2)
```

**Default HBlank handler** (when no raster effects are active):

```asm
HBlank_Null:
        rts                             ; Immediate return — ~16 cycles total including dispatch
```

**Why RAM-patched HBlank but pointer-dispatched VBlank:** HBlank fires up to 224 times per frame and must be as fast as possible. The dispatch through a RAM pointer adds only 16 cycles to the null case. VBlank fires once per frame but needs mode-specific behavior (VInt_Level, VInt_Lag, future VInt_Menu/VInt_Load). The `VInt_Ptr` RAM pointer selects the mode; the lag detection is handled in the ROM dispatcher itself via the `VBlank_Ready` flag.

### 0.11 Soft Reset Detection (CrossResetRAM §9.5)

**Problem:** When the user presses RESET, only the 68000 resets. VDP, Z80, VRAM, CRAM, all retain their state. A running DMA may still be in progress.

**Solution — two-tier detection:**

```asm
; At $000200 (entry point)
        tst.l   ($A10008).l             ; Port A control — zero on cold boot, non-zero on soft reset
        bne.s   .warm_boot
        tst.w   ($A1000C).l             ; Expansion control — second check
        beq.s   .cold_boot

.warm_boot:
; VDP may have in-progress DMA — wait for it
.wait_dma:
        move.w  ($C00004).l, d0
        btst    #1, d0                  ; DMA busy flag
        bne.s   .wait_dma

; Preserve CrossResetRAM region (§9.5 — lives/continues/score survive reset)
; Clear everything else, re-enter game state machine at title screen
        bra.w   Warm_Reset

.cold_boot:
; Full hardware init (§0.2-§0.9)
        bra.w   Cold_Boot
```

**CrossResetRAM** is a small region of Work RAM (e.g., $FFFFE0-$FFFFFF) that survives soft reset. On cold boot, it's detected as zero (freshly cleared RAM) and initialized. On warm boot, it's preserved. This allows "press RESET to return to title screen with score intact" behavior.

### 0.12 Boot Sequence — Complete Execution Order

```
Power On
  ├── 68000 reads SSP from $000000 ($FFFFFF00)
  ├── 68000 reads Reset PC from $000004 (EntryPoint)
  │
  EntryPoint:
  ├── Soft reset check ($A10008 / $A1000C)
  │     ├── Warm: wait DMA busy, preserve CrossResetRAM, → Warm_Reset
  │     └── Cold: continue below
  │
  Cold_Boot:
  ├── TMSS handshake (read $A10001, write "SEGA" to $A14000 if needed)
  ├── Read VDP control port (reset command word state machine)
  ├── Load hardware addresses into a0-a4 via movem
  │
  ├── VDP register init ($00-$17, 24 registers from table)
  │     └── Register $17 = $80 primes DMA fill
  │
  ├── Start VRAM DMA fill (write dest+trigger → VDP fills 64KB in background)
  │
  ├── WHILE DMA RUNS (parallel work):
  │     ├── Init Z80 (bus request, load idle program, reset with YM2612 delay)
  │     ├── Clear Work RAM (64KB, ~180,000 cycles)
  │     └── Silence PSG (4 bytes to $C00011)
  │
  ├── Wait for DMA fill completion (poll VDP status bit 1)
  ├── Set auto-increment to 2 ($8F02) — fill used increment=1, restore for word writes
  ├── Clear CRAM (128 bytes via CPU loop)
  ├── Clear VSRAM (80 bytes via CPU loop)
  │
  ├── Region detection (read $A10001, store flags)
  ├── Controller port init (TH = output on ports 1, 2, expansion)
  │
  ├── Init VDP shadow table in RAM (copy init values)
  ├── Init HBlank handler pointer (→ HBlank_Null)
  ├── Init interrupt dispatch
  │
  ├── Clear all 68K registers (movem from zeroed RAM)
  ├── Set SR = $2700 (supervisor mode, all interrupts masked)
  │
  └── Branch to Game_StateInit (state machine entry)
        └── Load Flamedriver, show logos, transition to title screen
```

### 0.13 Build-Time Data Generation (AS Features)

Several boot-time data tables are generated by the assembler rather than maintained by hand:

**Sine/Cosine table** (512 entries, computed by AS `rept` + math — see CODING_CONVENTIONS.md §1.8):

```asm
Sine_Table:
__angle = 0
        rept 512
        dc.w (__angle * 3.14159265 * 2.0 / 512.0) * $7FFF
__angle = __angle + 1
        endr
; No external binary, no hand-maintained table, no drift from "the correct values"
```

**RNG** (linear congruential, same as S.C.E.):

```asm
Random_Number:
        move.l  (RNG_Seed).w, d1
        bne.s   .non_zero
        move.l  #$2A6D365A, d1          ; Rescue from zero-seed degenerate case
.non_zero:
        move.l  d1, d0
        asl.l   #2, d1
        add.l   d0, d1
        asl.l   #3, d1
        add.l   d0, d1
        move.w  d1, d0
        swap    d1
        add.w   d1, d0
        move.w  d0, d1
        swap    d1
        move.l  d1, (RNG_Seed).w
        rts
; Returns random value in d0.w
```

**Fixed-point convention** (documented here, used everywhere):

| Type | Format | Range | Use |
|------|--------|-------|-----|
| Position | 16.16 | ±32767.9999 pixels | Object/camera X/Y |
| Velocity | 8.8 | ±127.996 px/frame | Object speeds |
| Subpixel | 0.8 (low byte of word) | 0.004-0.996 | Fractional accumulation |
| Angle | 0-255 (byte) | 360° in 256 steps | Slope angles, rotation |
| Sine result | 1.15 (signed word) | -0.99997 to +0.99997 | Trig results |

### 0.14 Cascade Effects

Changes in this section that ripple to other sections:

| Decision | Affects | How |
|----------|---------|-----|
| SSP = $FFFFFF00 | §8.3 Error Handler | Stack guard checks adjusted for high-RAM stack |
| VDP shadow table | §1 DMA Pipeline | DMA queue writes to shadow, not direct VDP |
| VDP shadow table | §7 Visual Effects | HInt/section transitions use shadow writes, flush in VBlank |
| RAM-patched HBlank | §7.2 HBlank System | Section transitions swap handler pointer, not vector |
| 64×64 plane init | §2.3 VRAM Layout | Plane size register confirmed, nametable addresses validated |
| Region detection | §5 Player Physics | PAL timing accumulator affects physics tick rate |
| Region detection | §1.1 DMA Queue | PAL gets nearly double DMA budget — adaptive byte count |
| Controller port init | §9.4 6-Button | Boot sets TH output; VBlank reads using rapid TH cycling |
| Frame accumulator | §9.7 Cooperative Multitasking | Tick count determines how many logic frames to simulate |
| Z80 idle program | §6 Audio | Flamedriver loads over idle program when sound system initializes |
| CrossResetRAM | §9.5 Soft-Reset | Boot detects warm/cold, preserves CrossResetRAM region |
| DMA-parallel init | §1.1 DMA Queue | Validates that DMA fill + CPU work can overlap safely |

---

## 1. Core VDP Pipeline

The VDP pipeline governs everything that reaches the screen: DMA transfers, sprite rendering, scroll plane drawing, and interrupt handling. Every system in the engine ultimately feeds data into this pipeline.

### 1.1 DMA Queue System

**Purpose:** Centralize all VDP memory transfers through a single, priority-ordered queue system. The main game loop never stalls on DMA — it enqueues transfers, and VBlank drains them.

**Architecture: Three Priority Sub-Queues**

```
┌─────────────────────────────────────────────────┐
│                  DMA Queue RAM                  │
├──────────────┬───────────────┬───────────────────┤
│  Critical    │  Important    │  Deferrable       │
│  8 slots     │  12 slots     │  12 slots         │
│  112 bytes   │  168 bytes    │  168 bytes        │
├──────────────┼───────────────┼───────────────────┤
│ Palette      │ Char DPLCs    │ S4LZ art stream   │
│ Sprite table │ Animated tiles│ Section preload    │
│ Hscroll buf  │ DPLC lookahead│ Background art     │
├──────────────┼───────────────┼───────────────────┤
│ ALWAYS drain │ Budget-gated  │ Skip on lag frames │
│ Unrolled     │ Linear loop   │ Linear loop        │
│ ~514 cycles  │ ~932 cycles   │ ~932 cycles        │
└──────────────┴───────────────┴───────────────────┘
Total: 32 slots × 14 bytes = 448 bytes RAM
```

**Entry format:** Flamewing Ultra DMA Queue 14-byte entries. VDP register numbers are interleaved at odd byte offsets using `movep`, so the drain loop writes pre-computed VDP commands directly — zero computation during VBlank.

**Drain strategy — hybrid unrolled/looped:**

- **Critical queue (8 slots):** Jump-table unrolled drain. The slot pointer is converted to a queue offset (`suba.w #DMA_Critical, a1`) then used as a jump index into fully unrolled `move.l (a1)+,(a5)` sequences. Zero comparisons, zero branches per entry. ~514 cycles to drain all 8 entries. Note: S.C.E. uses `jmp table-queue(a1)` directly, but our RAM layout puts the queue too far from ROM for a 16-bit displacement — the two-instruction split is functionally equivalent. Ported from S.C.E.'s `Process_DMA_Queue`.
- **Important + Deferrable queues (12 slots each):** Linear loop drain with `dbf` counter. ~932 cycles per queue. The loop overhead (~14 cycles/entry for branch + counter) is acceptable for non-critical transfers.

**Why hybrid, not fully unrolled:** Unrolling all 32 slots costs 704 bytes ROM. The hybrid approach costs ~280 bytes — 60% smaller with 60% of the performance benefit. The critical queue (where every cycle matters for visual stability) gets the fast path. The deferrable queues (where one extra frame of latency is acceptable) get the compact path.

**Static DMA for fixed transfers:** Sprite table ($280 bytes → VRAM $B800) always transfers from the same RAM address to the same VRAM address with the same size. Its 14-byte DMA entry is pre-computed once at level init and copied directly into the Critical queue each frame, bypassing the `QueueDMATransfer` enqueue logic entirely. Saves ~200 cycles/frame.

**Per-palette-line dirty DMA:** Palette uses a 4-bit dirty bitmask (`Palette_Dirty`, one bit per palette line = 32 bytes). Each frame, only dirty lines are enqueued as Critical DMA. On a typical gameplay frame, only Line 3 (effects/water) changes — 32 bytes instead of 128. On section transitions, all 4 bits set. Palette line mapping: Line 0 = BG/environment, Line 1 = player character, Line 2 = objects, Line 3 = effects/water/fade.

**Variable-size hscroll DMA:** Unlike palette and sprites, the hscroll buffer benefits from dirty-range tracking. The scroll update routines record `Hscroll_Dirty_Start` and `Hscroll_Dirty_End` (scanline indices). The DMA entry is computed each frame to transfer only the changed portion: source = `Horiz_Scroll_Buf + start*4`, dest = `$FC00 + start*4`, length = `(end - start + 1) * 4`. On slow-scroll frames (camera moved 1-2 pixels), this can reduce the hscroll DMA from 448 bytes to ~20 bytes — a 95% reduction in a Priority 0 transfer.

**Adaptive byte budget:** Each frame tracks total DMA bytes transferred. After a lag frame, the budget for Important and Deferrable queues is reduced for the next frame to prevent consecutive drops. After N clean frames, the budget gradually restores to maximum. This creates a self-tuning system that finds optimal DMA throughput for the current scene complexity. Inspired by Vectorman's `cmpi.w #$B40` budget check, extended with feedback.

**Lag recovery budget:** After a lag frame causes the Deferrable queue to be skipped, those entries pile up. To prevent cascade (one lag frame → backlog → another lag frame), temporarily grant 1.5× budget to the Deferrable queue for 2-3 frames after a lag event. This flushes the backlog without risking another overrun.

**VBlank DMA budget (concrete numbers from hardware research):**

| System | VBlank Lines | 68K Cycles | DMA Bytes (68K→VRAM) | Practical Budget |
|--------|-------------|------------|---------------------|-----------------|
| NTSC H40 | 38 | ~18,544 | 7,524 | ~7,200 |
| PAL H40 (224p) | 89 | ~43,432 | 17,622 | ~15,000 |

The practical budget accounts for CPU overhead (drain loop, VDP shadow flush, controller polling, sound driver). Vectorman's $B40 (2,880 bytes) is conservative — our 3-queue system with ~7,200 bytes available has substantial headroom for art streaming in the Deferrable queue.

**128KB boundary safety:** The VDP increments only the low 17 bits of the 23-bit DMA source address. Transfers crossing a 128KB boundary wrap within the same block, producing garbage. This is fundamental to VDP silicon — all hardware revisions are affected. **DEFERRED:** `QueueDMATransfer` does not currently split boundary-crossing transfers. No current consumer crosses a 128KB boundary (test art is 10KB, palette is 32 bytes). When S4LZ art streaming (§3) introduces larger transfers, add Flamewing's overflow detection via subtraction carry.

**RAM source address safety:** When a RAM source address ($FF0000+) is right-shifted by 1 for the VDP, bit 23 can become set, which the VDP interprets as a VRAM copy flag instead of 68K→VDP DMA. `QueueDMATransfer` clears bit 23 after the shift (`bclr.l #23,d1`).

**VInt safety:** SR masking (disable interrupts) during `QueueDMATransfer`. Costs 46 cycles per enqueue call. Prevents queue corruption if VBlank fires mid-enqueue. Enabled for all three queues.

**Three entry points:** `QueueDMA_Critical`, `QueueDMA_Important`, `QueueDMA_Deferrable` — each sets up the target sub-queue (slot pointer address + end address), then branches to the shared `QueueDMATransfer` core. Callers provide: d1.l = source address, d2.w = VRAM destination, d3.w = transfer length (bytes).

**No double buffering.** Vectorman uses double-buffered queues (write to A, drain B, swap). With SR masking preventing mid-enqueue interrupts, double buffering solves a problem we don't have. Saves 448 bytes RAM.

**QueueStaticDMA macro:** For transfers with build-time-known source, destination, and length (sprite table, individual palette lines), a `QueueStaticDMA` macro bypasses `QueueDMATransfer` entirely. The 14-byte entry is pre-computed at boot by `BuildStaticDMA` (5 entries: 4 palette lines + sprite table), then block-copied into the next queue slot with `3×move.l + 1×move.w`. ~52 cycles inlined vs 184 cycles for the full function. Used by `Enqueue_Dirty_Buffers` to populate the Critical queue from dirty flags. Adapted from Flamewing's `QueueStaticDMA`.

**Critical queue overflow assertion:** In debug builds, `QueueDMATransfer` and `QueueStaticDMA` assert (via `trap`) if the Critical queue is full. Critical overflow means a design bug — the queue should always have capacity for the fixed transfers. In release builds, silently returns without enqueueing (graceful degradation). Important/Deferrable queues do not assert on overflow — budget-gated skipping is expected behavior.

**Debug profiling counters (§8 integration):** Behind `ifdebug` guards, the DMA system tracks: `DMA_Bytes_ThisFrame` (total bytes enqueued), `DMA_Peak_Queue_Fill` (high-water mark per sub-queue), `DMA_Overflow_Count` (enqueue rejections), `Lag_Frame_Count` (VBlank overruns). Readable via Exodus MCP or KDebug console. Zero cost in release builds.

**Why not S.C.E.'s hybrid (immediate + queued):** S.C.E. DMAs palette, sprites, and hscroll immediately during VBlank, using the queue only for art streaming (7 slots). We route everything through the queue because: (a) one code path to maintain, (b) the priority system gives us the same "critical transfers always complete" guarantee, (c) the queue provides byte budget enforcement and lag-frame behavior that immediate DMA can't.

**Cross-references:**
- Flamewing Ultra DMA Queue: entry format, boundary safety, VInt protection, QueueStaticDMA
- S.C.E. `DMA Queue.asm`: jump-table drain mechanism
- Vectorman: byte budget concept ($B40), pre-computed VDP command words, atomic batch enqueue
- Alien Soldier: variable-size DMA based on dirty region (applied to hscroll), dirty flags for palette/sprites
- Batman: pre-staged VDP command buffer at fixed RAM addresses (applied to static DMA)
- Gunstar Heroes: conditional sprite DMA via dirty flags
- Thunder Force IV: round-robin sprite flicker for overflow (deferred to §1.2)
- plutiedev.com, Kabuto hardware notes: VBlank timing, DMA transfer rates, 128KB boundary, sprite cache write-through

---

### 1.2 Sprite System

**Purpose:** Convert object state into the VDP sprite attribute table efficiently, with priority sorting, overflow protection, and conditional DMA.

**Architecture: Two-Phase Render**

```
Phase 1 — During Object Loop          Phase 2 — Render_Sprites
┌─────────────────────────┐           ┌──────────────────────────┐
│ Object calls Draw_Sprite│           │ Walk priority-band lists │
│ → stores RAM addr into  │           │ → convert to VDP format  │
│   priority-band list    │           │ → write to Sprite_Table  │
│ (one pointer store,     │    then   │ → set Sprite_Table_Dirty │
│  no conversion yet)     │  ──────►  │ → clear unused entries   │
└─────────────────────────┘           └──────────────────────────┘
```

**Phase 1 — Draw_Sprite (during object loop):** Each visible object calls `Draw_Sprite`, which resolves the object's current mapping frame, culls exactly against the frame's precomputed bounding box (the 4-byte flip-invariant extent header at the front of each frame — 7.8), and on pass adds the object's RAM address to a priority-band list at `Sprite_Table_Input + priority`. No sprite data conversion happens here — pieces are emitted in Phase 2. Objects are automatically sorted by priority when they register.

**Phase 2 — Render_Sprites (after all objects processed):** Single pass through the priority-sorted lists. For each registered object, reads mappings, applies position offsets and flip flags, writes 8-byte VDP sprite entries to `Sprite_Table`. Sets `Sprite_Table_Dirty` flag when any entries are written.

**Why two-phase:** A naive approach iterates all objects N times (once per priority level), scanning the full object list each pass. With 40+ objects and 8 priority levels, that's 320+ iterations. The two-phase approach does one pass during the object loop (piggybacks on existing iteration) and one pass during Render_Sprites (only processes registered objects). Eliminates redundant full-table scans.

**Link chain pre-initialization:** `Init_SpriteTable` runs at level load and fills the 80-entry sprite link chain: entry 0 links to 1, 1 to 2, ..., 79 to 0. During gameplay, `Render_Sprites` writes the link byte for each emitted piece (sequential 0,1,2,...) and patches the last rendered piece's link to 0 as the chain terminator. The pre-init covers the unused tail of the SAT; per-frame writes are the source of truth for active entries. ("Never rebuilt" was investigated as a 68000 cycle optimization but is genuinely a wash — `move.b Dn,(An)+` and `addq.l #1,An` both cost 8 cycles, so skipping the write doesn't save anything once you account for advancing the pointer. S.C.E./Batman use the advance-past style, sonic_hack rewrites; both end up at the same per-piece cost.) Unused entries keep Y=0 (off-screen) from Init_SpriteTable; Render_Sprites writes link=0 to the last emitted entry to halt the VDP's chain walk early.

**Sprite overflow handling — two layers:**

1. **Band overflow (from S.C.E.):** When a priority band is full ($80 bytes = 16 entries), `Draw_Sprite` overflows to the next band via `lea $80(a1),a1`. Prevents crashes but can cause priority inversion.
2. **Round-robin flicker (from TF4, optional):** If sprite overflow becomes visible in gameplay, add a frame counter that rotates which sprites get the first 80 slots. Over a 4-frame window, every sprite gets at least one frame of visibility. No sprite permanently hidden.

**Multi-sprite batching:** Composite objects (multi-part bosses, Tails' tails) set `render_flags.multi_sprite`. `Render_Sprites` gives the parent a single bounds check, then renders all child sprite pieces without redundant per-piece culling. Ported from S.C.E.'s `Render_Sprites_MultiDraw`.

**Sprite count per object:** Each object's SST includes a `sprite_piece_count` field, set at init from mapping data. This enables overflow prediction — before calling Draw_Sprite, the system can check if adding this object would exceed the 80-sprite limit. Inspired by Batman's `sprite_link_count` at object offset $18.

**Sprite table dirty flag:** `Sprite_Table_Dirty` byte, set by `Render_Sprites` after writing entries, cleared after DMA. Before enqueueing the sprite table DMA in the Critical queue, check this flag. If clear (no objects moved or animated since last frame), skip the $280-byte DMA entirely. This saves a Priority 0 queue slot and VBlank transfer time on static frames (pauses, cutscenes, menus, any calm moment). Confirmed by Gunstar Heroes' conditional sprite DMA pattern.

**VDP sprite cache is write-through:** The VDP maintains an internal cache of Y-position and size/link fields. This cache updates only via VRAM writes to the sprite table address — changing the sprite table base address register does NOT update the cache. Therefore the full sprite table must always be DMA'd to VRAM; you cannot swap tables by changing the VDP register alone.

**Cross-references:**
- S.C.E. `Draw Sprite.asm`, `Render Sprites.asm`: two-phase system, Init_SpriteTable, MultiDraw, band overflow
- TF4: round-robin sprite flicker for overflow
- Batman: sprite_link_count per object for overflow prediction
- Gunstar: conditional sprite DMA via dirty flags

---

### 1.3 Scroll / Plane Drawing

**Purpose:** Update VDP nametable planes (scroll layers) without touching the VDP during the game loop. All tile writes are deferred to VBlank via a RAM buffer.

**Architecture: Deferred Plane Buffer**

```
Game Loop                              VBlank
┌──────────────────────┐              ┌─────────────────────────┐
│ Camera scrolls       │              │ VInt_DrawLevel:          │
│ → Draw_TileColumn    │              │   for each buffer entry: │
│   queues tile updates│   deferred   │     set VDP increment    │
│   to Plane_buffer    │  ─────────►  │     set VRAM address     │
│ → Draw_TileRow       │              │     move.l tiles to VDP  │
│   queues tile updates│              │   clear buffer           │
│ → Never writes to VDP│              └─────────────────────────┘
└──────────────────────┘
```

**Buffer structure:** 768 words (1536 bytes) in RAM. Each entry consists of:
- Word 0: VRAM destination address
- Word 1: Tile count - 1. Bit 15 set = vertical write mode (column), clear = horizontal (row).
- Data: 2 words per tile (VDP nametable format: tile index + palette + priority + flip bits)
- Terminated by a zero word.

**Why 768 words (vs S.C.E.'s 576):** Worst-case diagonal fast-scroll with double-update on both axes can reach ~400 words per plane. S.C.E.'s 576-word buffer can overflow in extreme cases (no bounds checking). Our 768 words provides 40% headroom for section transitions and fast diagonal scrolling.

**Overflow protection (gap in S.C.E.):** Before each entry write, check remaining buffer capacity. If full, defer excess tile updates to next frame rather than corrupting memory. The deferred updates are re-queued on the next scroll check. Slight visual pop (one frame of missing tiles at screen edge) is preferable to memory corruption.

**Dual plane support with independent dirty flags:** Separate `Plane_A_Dirty` and `Plane_B_Dirty` flags allow FG and BG planes to be updated independently. Camera scroll on one axis may only affect Plane A (foreground), while Plane B (background parallax) updates on a different schedule. `VInt_DrawLevel` checks each flag and only processes the corresponding buffer if dirty. Section transitions that change only the BG art don't force FG redraws and vice versa. Each plane has its own buffer: `Plane_A_Buffer` (primary) and `Plane_B_Buffer` (secondary).

**Double-update mechanism:** When camera moves >16 pixels in one frame (fast scrolling), `Draw_TileColumn`/`Draw_TileRow` queues two sequential updates instead of one. The `Plane_Double_Update_Flag` triggers automatically based on camera delta.

**How tile data reaches the buffer:** During the game loop, `Draw_TileColumn` (horizontal scroll) or `Draw_TileRow` (vertical scroll) detects that the camera has crossed a 16-pixel block boundary. It calls `Setup_TileColumnDraw` / `Setup_TileRowDraw`, which:
1. Calculates the VRAM nametable address for the new column/row
2. Looks up chunk → block → tile data from Level_Layout RAM
3. Applies flip flags and palette bits
4. Writes the complete VDP nametable words into the Plane_buffer
5. Writes a zero terminator after the last entry

**VBlank processing:** `VInt_DrawLevel` (called after DMA queue drain) iterates through the buffer:
1. Reads VRAM address, sets VDP write command
2. Sets VDP auto-increment register ($8F02 for horizontal, $8F80 for vertical)
3. Writes tile data via `move.l (a0)+, VDP_data_port` loop
4. Processes entries until zero terminator
5. Resets VDP auto-increment to default ($8F02)

Tile writes use direct CPU writes to VDP data port (not DMA). This is correct — the updates are small sequential writes (typically 16-32 tiles per column = 64-128 bytes), where DMA setup overhead would exceed the transfer itself.

**Pre-computed nametable data:** The build tool generates pre-computed VDP nametable words per section, stored in the 2D tile cache. At runtime, `Setup_TileColumnDraw` copies nametable words from the tile cache to Plane_buffer — zero runtime tile conversion. The buffer infrastructure handles the rest.

**Why deferred, not direct VDP writes:** Writing to the VDP data port during the game loop means the 68K is touching $C00000 during active display, competing with the VDP's rendering engine. The deferred approach eliminates all game-loop VDP access, giving the VDP uncontested bus during active display and consolidating all writes to VBlank where bus arbitration is clean.

**Cross-references:**
- S.C.E. `Draw Level.asm`: Plane_buffer, VInt_DrawLevel, Draw_TileColumn/Row, double-update mechanism
- Batman: VDP-ready nametable format in ROM (validates the pre-computed nametable direction)
- All 5 commercial games + S.C.E.: producer-consumer pattern (main loop writes RAM, VBlank writes VDP)

---

### 1.4 VBlank Structure

**Purpose:** Process all time-critical VDP operations within the vertical blanking interval. Prioritize visual stability over throughput.

**Handler dispatch:** Function pointer `VInt_Ptr` selects the mode-specific handler. `VBlank_Handler` (ROM) checks `VBlank_Ready` to detect lag frames — if the main loop hasn't finished, `VInt_Lag` runs instead of the selected handler.

| Mode | When | What it does | Status |
|------|------|-------------|--------|
| `VInt_Level` | Gameplay | Full pipeline: shadow flush + VSRAM + dirty buffers + DMA queue + controllers | Implemented |
| `VInt_Menu` | Menus/title | DMA queue + sound (no plane buffer, no HUD) | Planned |
| `VInt_Load` | Loading screens | DMA queue + S4LZ processing (no gameplay state) | Planned |
| `VInt_Lag` | Lag frame detected | Critical DMA only (Important/Deferrable persist to next frame) | Implemented |

**VInt_Level execution order (as implemented):**

```
Step  System                    Priority    Timing
─────────────────────────────────────────────────────
  1   stopZ80                   Bus safety  ~20 cycles
  2   Flush_VDP_Shadow          Critical    ~50-190 cycles
  3   VSRAM write (direct)      Critical    ~32 cycles
  4   Enqueue_Dirty_Buffers     Critical    ~20-260 cycles
  5   Drain Critical DMA queue  Critical    ~514 cycles
  6   Set DMA budget            Setup       ~12 cycles
  7   Drain Important DMA queue Budget-gated ~932 cycles
  8   Drain Deferrable DMA queue Budget-gated ~932 cycles
  9   startZ80                  Bus release ~16 cycles
 10   Read_Controllers          I/O         ~200 cycles
 11   Frame_Counter increment   Tracking    ~8 cycles
 12   VBlank_Flag signal        Sync        ~8 cycles
```

Steps 1-9 run with Z80 bus stopped (required for safe VDP access). Steps 10-12 run after Z80 release. `Enqueue_Dirty_Buffers` checks palette dirty bitmask (4 bits) and sprite dirty flag, enqueueing pre-computed static DMA entries to the Critical queue via `QueueStaticDMA`. Plane buffer processing, HUD update, S4LZ, and sound are deferred to later §§.

**Step 3 — VSRAM:** Direct VDP write, not queued. Vertical scroll data is 4 bytes (FG + BG) written to VSRAM via control port command + data port write. Too small to justify queue overhead. RAM shadow at `Vscroll_Factor` updated by scroll routines.

**Steps 5-8 — DMA queue drain:** Critical queue always drains fully via jump-table dispatch (zero branches per entry). Important and Deferrable queues are budget-gated: check `DMA_Budget_Remaining` before each entry. Budget is reset from `DMA_Budget_Default` (7,200 NTSC / 15,000 PAL) at the start of Important drain. On lag frames (`VInt_Lag`), only the Critical queue drains — Important and Deferrable entries persist in the queue for the next frame.

**Plane buffer, HUD update, sound:** Not yet implemented (deferred to §4, §9.13, §6 respectively). These will be inserted into VInt_Level after the DMA pipeline and before startZ80 (or after, depending on bus requirements).

**Lag frame handling:** `VBlank_Handler` checks `VBlank_Ready` (set by `VSync_Wait` in the main loop). If clear, `VInt_Lag` runs instead of the handler selected by `VInt_Ptr`. On a lag frame:
- Critical DMA drains (palette, sprites — player never sees visual glitches)
- Important/Deferrable entries remain in queue (drained next normal frame)
- Controllers still read, frame counter still advances
- `Lag_Frame_Count` increments for debugging (debug builds only)
- `VBlank_Ready` is cleared by VBlank_Handler after dispatch

**Why this order:** Visual stability first (VSRAM + Critical DMA ensure correct display), then throughput (Important/Deferrable DMA for art streaming), then deferred writes (plane buffer), then housekeeping (HUD, sound). Each step is independently skippable without corrupting state.

**Cross-references:**
- S.C.E. `Interrupt Handler.asm`: VInt function pointer dispatch, VInt_Lag, Do_ControllerPal ordering
- Batman: early DMA burst before other VBlank processing
- Gunstar: conditional VBlank steps based on dirty flags

---

### 1.5 Background Work During Idle Time

**Superseded by §9.7 (Cooperative Multitasking).** The supervisor/user mode context switching system automatically gives background tasks (S4LZ decompression, section preloading, palette computation) whatever CPU time remains after the foreground game loop completes each frame. No manual chunking, no bookmark systems, no polling — VBlank preempts the background task and context-switches back to the foreground automatically. See §9.7 for the full design.

---

### 1.6 DPLC Lookahead — Predictive Art Loading

**Purpose:** Eliminate single-frame art latency during character animation transitions by pre-loading the next animation frame's art before the animation advances.

**Mechanism:** During `AnimateSprite`, when `anim_timer <= 1` (one frame before the animation changes), peek at the next frame in the animation script. If it requires different DPLC tiles than the current frame, queue the DPLC load as an Important-priority DMA entry. When the animation actually advances next frame, the art is already in VRAM.

**Trigger guard:** Only activates when `anim_timer <= 1`, not every frame. This prevents doubling DPLC traffic during steady-state animation. The pre-load fires once per animation transition, not once per frame.

**Waste case:** Player changes state (e.g., jumps while running) and the pre-loaded art is never used. Cost: one wasted Important-priority DMA entry that gets budget-gated. Minimal impact.

**No Genesis game does predictive DPLC loading.** All load reactively: frame changes → trigger DPLC → art appears next frame. With lookahead, art appears on the same frame as the animation change.

---

### 1.7 VDP Register & VSRAM Management

**VDP register shadow:** Full 19-register shadow table with dirty tracking (§0.4). Game code never writes VDP registers directly — all changes go through `SetVDPReg`, which updates the RAM shadow and sets a dirty bit. `Flush_VDP_Shadow` in VBlank writes only the changed registers. Most frames, 0-3 registers change, so the dirty-tracking approach skips 16-19 register writes vs Batman's bulk-write-all approach.

**Key register change points:**
- `vdp_mode2` (reg $01): Display enable/disable — toggled during loading screens and display-disable burst DMA (§7.2)
- `vdp_hint_rate` (reg $0A): H-Int line counter — set per-section for water line, raster effects
- `vdp_mode3` (reg $0B): Scroll mode — changed per-section for different parallax configurations
- `vdp_mode4` (reg $0C): S/H mode — toggled per-section (§7.3)
- `vdp_window_h`/`vdp_window_v` (regs $11/$12): Window plane — toggled for HUD overlay, letterboxing

**VSRAM:** Direct write during VBlank step 1. RAM shadow at `Vscroll_Factor` (foreground + background, 4 bytes total). If per-column V-scroll is needed for parallax, extend to a RAM buffer (40 columns × 4 bytes = 160 bytes) and write via a direct loop during VBlank (like hscroll, but smaller).

---

### 1.8 H-Blank Dispatch Mechanism

**Purpose:** Execute per-scanline raster effects via a section-installable interrupt handler. The dispatch mechanism is simple — the raster command table system (§7.2) defines what actually runs.

**RAM-patched pointer dispatch (§0.10):** The HBlank vector in the exception table points to a tiny ROM stub (`HBlank_Dispatch`) that reads a handler pointer from RAM (`HBlank_Handler_Ptr`) and calls it. The handler pointer always points to the raster command table walker (§7.2), which processes the current section's pre-built command list. When no raster effects are active, the table is empty (just a terminator) and the handler returns in ~20 cycles.

**H-Int counter:** Set via VDP shadow table (§0.4, §1.7) to control which scanline triggers the interrupt. For single-event effects (water line): set to the trigger scanline. For continuous effects (deformation, gradient): set to 0 (fire every scanline) or the effect start line. The raster command table handles multiple effects at different scanlines automatically.

**Production-proven:** 4 out of 5 analyzed commercial games (Vectorman, TF4, Gunstar Heroes, Alien Soldier) RAM-patch HBlank. Vectorman ($FFFF9D2E), Batman ($FFFFE560), and Treasure ($FFFFEE00) all use pointer dispatch.

---

### 1.9 Cascade Effects

The systems in this cluster create a chain of enablements:

```
Plane Buffer (no game-loop VDP access)
  → VDP has uncontested bus during active display
    → Cleaner rendering, no bus contention artifacts
  → More VBlank time available (no game-loop VDP cleanup)
    → More aggressive art streaming via Deferrable DMA
      → Smoother section transitions
        → Smaller sections viable (faster art swap)

Priority DMA + Adaptive Budget + Lag Recovery
  → Visual stability under heavy load
    → More objects/effects affordable per scene
      → Richer gameplay without frame drops
  → Self-tuning throughput
    → No manual per-zone DMA budget tuning needed

Sprite Dirty Flag + Static DMA + Variable Hscroll
  → 1-3 fewer DMA entries on calm frames
    → More budget available for art streaming
      → Faster S4LZ decompression throughput

Background Task (§9.7) + DPLC Lookahead
  → Free S4LZ decompression in leftover CPU time
    → Art pre-loaded before section boundary reached
      → Zero visible loading artifacts
  → Character art pre-loaded before animation changes
    → Zero-frame animation transition latency

Raster Command Table (§7.2) + Section Streaming
  → Per-section stackable raster effects via pre-built command tables
    → Visual variety between sections, multiple effects per frame
```

---

## 2. Art & Compression Pipeline

The art pipeline handles getting graphical data from ROM into VRAM — compressed art decompression, VRAM address assignment, section-aware streaming, and background plane support. Every visual element in the game flows through this pipeline.

### 2.1 Compression & Art Formats: Two-Tier (S4LZ v3 + ZX0) + Uncompressed/DPLC

**Purpose:** Formats chosen by DECODE-SPEED TIER, with all ratios MEASURED on the real
(post-dedup) corpus — the original projections assumed pre-dedup redundancy and did not
survive contact with shipped data (see `docs/research/compression-audit-2026-06-11.md`,
the audit that produced this design, and `compression-audit-landscape.md` for the
external survey). All compressed art carries a 4-byte wrapper: [u16 BE uncompressed
size][u8 flags][u8 version: 1 = S4LZ v3, 2 = ZX0]; `Art_Decompress` dispatches on the
version byte.

| Tier | Format | Measured speed | Measured ratio | Use Case |
|------|--------|-------|-------|----------|
| Runtime hot path | **S4LZ v3 + per-section block dictionary** | ~510-640 KB/s | blocks 0.49 (streams), ~0.29 effective with dict | 16×16 block decompression, 6/frame budget |
| Load-time bulk | **ZX0** (salvador / unzx0_68000) | ~76 KB/s (measured: 5 frames / 6.3 KB) | tile art 0.605 | Section tile art at init; any init-time bulk |
| Sprite art | **Uncompressed + DPLC** | Bus speed (DMA) | 1.0 | Per-frame character/object art via DMA from ROM |
| Tilemaps | **Raw** | instant | 1.0 | Menu/level select nametables — direct DMA to VDP |

**S4LZ v3 (runtime word-aligned LZ):**
- **Header:** the 4-byte wrapper above (flags bit 0 = tile-delta XOR, currently unused — it MEASURED 9 points WORSE on post-dedup tile data and was dropped from the pipeline)
- **Token word:** [token.b][offmark.b]. Token nibbles: hi = literal words, lo = match words; $00 = EOS (full word consumed). offmark = match_offset/2 for even offsets 2-510 (the byte that v1 wasted as alignment padding); offmark 0 = long form, u16 BE offset word follows the literals. Nibble 15 → u16 count extension (after token word for literals; after the offset position for matches)
- All copies word-aligned `move.w (a0)+,(a1)+`; matches may overlap (offset ≥ 2), copies ascend
- **Offsets ≤ 32766** (decoder uses `suba.w`; encoder enforces). Minimum match 2 words
- **Per-section block dictionary:** the compressor pre-seeds the LZ window with K raw blocks from the same section (K = 0..3 swept per section at build, min total size; OJZ optimum K=1). Dict blocks are stored RAW in the blob and serve double duty as their own storage (index entry bit 31 = raw-direct copy). `S4LZ_DecompressDict` rebases below-buffer match sources into the ROM dict with one compare-branch per match (~16 cycles, both entries pay it; the plain entry's branch never fires on valid streams). Measured: per-block compression recovers whole-stream-class ratios while keeping random access (0.524 → 0.486 streams; ~0.29 effective with dict accounting)
- Compressor: `tools/s4lz.py` — optimal parse (forward DP, dual match candidates per position: best-overall + best-short-offset). The parse is provably optimal for the cost model; known gap: literal-extension words are uncharged (measured < 0.5% ceiling, DEFERRED_WORK)
- Decompressor: `engine/s4lz_decompress.asm`, ~300 B, measured ~510-640 KB/s realistic mix. Micro-optimizations (move.l copy tables, extended-loop unroll, 256-entry token jump table → ~770+ KB/s) are documented in the audit and DEFERRED — current block budgets fit (6 blocks/frame ≈ half a frame; vertical scroll protocol unchanged at +4/512px with dicts on)

**ZX0 (load-time bulk):**
- Einar Saukas' ZX0 v2 format; compressed by vendored salvador (`tools/salvador/`, zlib/CC0/MIT licenses), decoded by vendored unzx0_68000 (`engine/zx0_decompress.asm`, zlib license, adaptation = mnemonic spelling only — algorithm byte-identical to upstream)
- Measured 0.605 on section tile art vs 0.85 for the best word-aligned S4LZ — bitstream rep-offset + elias-gamma + byte-granular matching, ~zlib-class ratio without entropy tables
- **~76 KB/s — init/preload tier ONLY.** Used today at level init (5 frames per section blob, invisible). Any future mid-gameplay deferred section load must NOT call it synchronously — that's the §9.7 cooperative-multitasking budgeted-decode design (DEFERRED_WORK)
- Clobbers d0-d1/a0-a2 only (narrower than S4LZ)

**Pipeline guarantees:**
- **Golden self-test:** every DEBUG boot decompresses build-time vectors (all v3 token paths, dict rebase, ZX0 via dispatch) on the 68000 and verifies checksum + byte-exact payload against the encoder's output — the asm decoders are continuously proven against the Python/salvador encoders
- **Content dedup:** identical section blobs (tiles AND blocks) collapse to one ROM copy via generated `equ` aliases (−37.8 KB on OJZ today)
- **Build guards:** blob size vs wrapper field (64 KB) and vs `Decomp_Buffer` capacity (9,600 B) fail the build, not the console
- See `docs/research/lz-compression-survey.md` for the original (partially superseded) LZ survey and the audit docs for what replaced it and why

**Uncompressed sprite art + DPLC/DMA (per-frame character/object art):**

UFTC was originally planned for random-access sprite decompression, but measured only 0.82-0.86 ratio on real Sonic sprite art (not the projected ~0.50). Every commercial Genesis game stores sprite art uncompressed and uses DMA from ROM. We follow suit with several improvements. See `docs/research/tile-format-survey.md` for full measurements and `docs/research/dplc-improvements.md` for the improvement design.

- Sprite art stored as uncompressed tiles in ROM (`ArtUnc_*` labels)
- **DPLC tables** map each animation frame to tile ranges in the art data (S2/S3K format: word entry count + word entries with 4-bit tile_count/12-bit tile_start)
- On animation frame change, `Perform_DPLC` queues DMA transfers from ROM directly to VRAM — zero CPU decompression cost
- Per-object `ros_prev_frame` field prevents redundant DMA when frame unchanged (S.C.E. pattern)
- **Build-time contiguous art layout:** Build tool rearranges tiles so each animation frame's tiles are contiguous in ROM, guaranteeing 1 DMA entry per frame change (12% ROM overhead from tile duplication — acceptable in 4MB ROM)
- **Build-time entry merging:** Merge adjacent DPLC entries at build time, reducing average DMA entries from 3.1 to 1.2 per frame change for pre-existing DPLC tables
- **Priority integration:** Character DPLCs → Important priority (guaranteed delivery). Object DPLCs → Deferrable priority (budget-gated, can slip one frame). Prevents VBlank overflow when many objects change frame simultaneously
- **DPLC Lookahead (§1.6):** When `anim_timer <= 1`, pre-load next frame's art as Important-priority DMA. Zero-latency animation transitions. No Genesis game does this
- **128KB DMA boundary safety:** `QueueDMATransfer` splits any transfer crossing a 128KB ROM boundary ($20000, $40000, etc.) into two entries. DMA source address wraps within 128KB banks on the Genesis — without splitting, art loads from wrong ROM addresses

**DMA bandwidth analysis (from `docs/research/dplc-improvements.md`):**
- Average tiles per frame change: 17.1 (547 bytes)
- VBlank DMA budget: ~7,000 bytes (NTSC)
- Single frame change = 7.8% of budget
- Worst case (3 characters + 8 objects simultaneous change): 4,202 bytes (60%)
- Amortized (frame changes every ~7 frames on average): 1.1% of budget
- **DPLC is not a DMA bandwidth bottleneck**

**ROM budget for uncompressed sprites (~463 KB):**
- Character sprites: ~308 KB (Sonic, Tails, Knuckles + shields/effects)
- Object/enemy sprites: ~155 KB
- Total: 11.3% of 4 MB ROM — fits comfortably with 2,783 KB free

**Raw tilemaps (menu/level select):**
- Menu tilemaps are small and infrequent — compression overhead isn't justified
- Stored as uncompressed VDP nametable data. Load via direct DMA from ROM — zero CPU cost, instant
- Even a dozen full-screen tilemaps at ~2-5 KB each is under 0.5% of a 4 MB cart

**Why S4LZ over existing LZ formats:**
- **vs KosPM:** S4LZ projects 700-1,100 KB/s vs KosPM's 190-310 KB/s. 3-4x faster. Comparable or better compression ratio with tile-delta preprocessing
- **vs Comper:** S4LZ is faster (word-aligned with unrolled tables vs Comper's simpler loop) AND compresses better (64KB dictionary + tile-delta vs Comper's 512-byte window at ~0.65-0.75 ratio)
- **vs LZ4W (SGDK):** S4LZ improves on LZ4W's design — big-endian offsets (14 cycles/match saved vs LZ4's little-endian), much larger dictionary (64KB vs 512 bytes), tile-delta preprocessing for better ratio
- **vs Nemesis:** S4LZ is ~8-14x faster than Nemesis for sequential loads, with comparable or better ratio via tile-delta
- **vs Raw/uncompressed (Batman):** Sonic needs 10+ zones — uncompressed level art would exceed 4MB ROM. Per-section tile art with S4LZ compression keeps ROM manageable while decompressing faster than any bit-stream format

**Why uncompressed + DPLC over UFTC:**
- Zero CPU overhead for per-frame sprite loading (DMA runs on VDP clock)
- UFTC achieves only 0.82-0.86 ratio on real Sonic sprite art — saves ~55 KB (1.3% of ROM) at cost of added complexity and per-frame CPU work
- Every commercial Genesis game (and all 7 reference disassemblies) stores sprite art uncompressed
- DPLC tables from sonic_hack can be migrated directly
- Simpler codebase (no UFTC encoder/decompressor/format handling)

**Cross-references:** See `docs/research/lz-compression-survey.md` for LZ format survey. See `docs/research/tile-format-survey.md` for UFTC evaluation. See `docs/research/dplc-improvements.md` for DPLC improvement design.

### 2.2 Dynamic VRAM Allocator (NOVEL)

**Purpose:** Assign VRAM tile addresses to objects at runtime with section-aware lifecycle management. No Genesis game — commercial or community — has ever done dynamic VRAM allocation. This is the most architecturally ambitious VRAM system on the platform.

**Architecture:**
```
┌──────────────────────────────────────────────────────────┐
│              DYNAMIC VRAM ALLOCATOR                       │
├──────────────────────────────────────────────────────────┤
│ State (in RAM, ~100 bytes):                              │
│   VRAM_Alloc_Cursor  — next free tile in unified pool    │
│   VRAM_Loaded_Table  — what's currently in VRAM          │
│     per entry: type_id, vram_addr, tile_count, refcount  │
│   VRAM_Loaded_Count  — number of loaded entries          │
├──────────────────────────────────────────────────────────┤
│ API:                                                     │
│   AllocVRAM(type_id) → vram_addr                         │
│     1. Scan loaded table — already in VRAM? bump refcount│
│     2. Not loaded: read tile_count from art metadata│
│     3. Bump cursor, register in loaded table             │
│     4. Check format: S4LZ → queue stream (Deferrable)    │
│                      S4LZ blocking → instant decompress   │
│                      Uncompressed → set art_source for DPLC│
│     5. Return VRAM address                               │
│                                                          │
│   FreeVRAM(type_id)                                      │
│     Decrement refcount. Art stays in VRAM (lazy reclaim). │
│     Available for free re-use if same type re-spawns.    │
│                                                          │
│   Section_ResetVRAM()                                    │
│     Keep entries with refcount > 0 (shared objects).     │
│     Compact survivors, reset cursor. Reclaim dead art.   │
├──────────────────────────────────────────────────────────┤
│ Pool: unified $000-$5FF (1,536 tiles). Level tiles,      │
│       object tiles, permanent tiles all share one pool.  │
│ Design: bump allocator (O(1) alloc), lazy reclaim,       │
│         zero fragmentation during section lifetime,      │
│         compaction only on section transition             │
└──────────────────────────────────────────────────────────┘
```

**Object init integration:** When `Load_Object` spawns an object, it calls `AllocVRAM(type_id)`. The allocator scans the loaded table (~20 cycles if found, ~50 if new allocation needed). Most spawns find art already loaded — refcount bumps and returns immediately. First spawn of a new type triggers S4LZ streaming, S4LZ instant decompression (blocking call for small art sets), or sets up the art_source pointer for DPLC-based per-frame loading (uncompressed sprite art).

**Art caching via refcounting:** Shared objects (springs, monitors, rings) accumulate high refcounts across sections. On section transition, `FreeVRAM` decrements but art stays in VRAM. `Section_ResetVRAM` only reclaims entries with refcount = 0. This means backtracking through previously visited sections has near-zero art loading cost — the art is still there.

**Why dynamic allocation over static/epoch approaches:**
- **Boss phase transitions:** Phase 2 art loads on demand via S4LZ blocking, phase 1 art freed. No need to pre-reserve VRAM for all phases.
- **Cross-section projectiles:** A projectile moving from section A to section B keeps its art via refcount — no special handling.
- **Debug spawns:** Spawn any object type anywhere — the allocator loads its art automatically.
- **Instant iteration:** Change level layouts, test immediately. No build pipeline dependency.
- **Lazy reclaim = free caching:** Freed art stays in VRAM until pool needs space. Eliminates redundant decompression.

**Debug safety:** In debug builds, `AllocVRAM` asserts on pool overflow — the crash screen (§8.3) shows "VRAM POOL OVERFLOW in Section(X,Y)" with full context (which objects are loaded, current cursor, refcounts).

**Cross-references:** §2.1 (S4LZ + uncompressed/DPLC formats), §2.3 (VRAM layout), §4.8 (predictive pre-allocation)

### 2.3 VRAM Layout — Unified Pool + 64×64 Scroll Planes

**Purpose:** Maximize available art tiles through a single unified pool, with 64×64 scroll planes for vertical buffering and visual effects. Character sprites and VDP tables embed in off-screen nametable rows — no dedicated VRAM regions needed.

```
VRAM (64KB = 2048 tiles)
┌───────────────┬─────────────────────────────────────────────────────┐
│ $000-$5BF     │ UNIFIED ART POOL (1,472 tiles)                     │
│ (1472 tiles)  │   Level tiles — build-time assigned per section     │
│               │   Object tiles — runtime allocator (2.2)            │
│               │   Permanent tiles — HUD, rings, monitors (alloc once)│
├───────────────┼─────────────────────────────────────────────────────┤
│ $600-$6FF     │ PLANE A NAMETABLE (256 tiles = 8KB, 64×64)         │
│ (256 tiles)   │   Visible area: ~40×28 tiles (1,120 entries)       │
│               │   Off-screen rows: character sprites + VDP tables   │
│               │   (sprite attr table, HScroll table embedded here)  │
├───────────────┼─────────────────────────────────────────────────────┤
│ $700-$7FF     │ PLANE B NAMETABLE (256 tiles = 8KB, 64×64)         │
│ (256 tiles)   │   Visible area: ~40×28 tiles                       │
│               │   Off-screen rows 48-63: §2 A.2 region 2 (64 tiles) │
└───────────────┴─────────────────────────────────────────────────────┘

VDP byte addresses: $000×32=$0000 ... $600×32=$C000 ... $700×32=$E000
VDP register $90 = $11 (64×64 scroll planes)
Plane A nametable base: VDP reg $02 → $C000
Plane B nametable base: VDP reg $04 → $E000
```

**Why unified pool:** Fragmented VRAM layouts (separate regions for level art, permanent objects, zone pools) waste tiles at region boundaries — a region with 5 free tiles and a neighbor with 0 free tiles can't share. The unified pool makes all 1,472 tiles available to the allocator. Tile overflow is impossible by construction — the allocator assigns tiles anywhere in $000-$5BF.

**Why 64×64 scroll planes ($9011):**

Our 4×3 section grid has true vertical transitions — vertical scrolling is a first-class concern, not an occasional exception.

| Property | 64×32 ($9001) | 64×64 ($9011) |
|---|---|---|
| Vertical buffer | ~32px beyond 224px display | ~288px beyond display |
| VSRAM deformation range | ±32px per column | ±288px per column |
| Nametable size per plane | 128 tiles (4KB) | 256 tiles (8KB) |
| Visual effects enabled | Basic horizontal | Perspective floors, dramatic water reflections, earthquake shake, vertical parallax |

With 64×32, fast vertical scrolling constantly hammers nametable updates with only 4 rows of buffer. With 64×64, 36 rows of buffer absorbs even the fastest vertical movement. The extended VSRAM range enables per-column vertical deformation effects that make levels look dramatically more alive.

**Validated by:** Vectorman (BlueSky) commercially ships with dynamic 64×32 ↔ 64×64 switching — the only known commercial Genesis game to use 64×64 scroll planes. S.C.E. validates off-screen nametable embedding by storing sprite art at $680+ between nametable regions. Batman & Robin and S3K use 64×32 because their levels are primarily horizontal — our vertical section grid justifies the larger planes.

**Off-screen nametable embedding:** With 64×64 planes, each nametable has 4,096 entries but only ~1,120 are visible (40×28). The remaining ~2,976 entries occupy VRAM that the VDP reads as nametable data for off-screen positions — the resulting tile lookups are never rendered. This VRAM can store arbitrary data (character sprite tiles, VDP tables) without visual artifacts. Character sprites are DMA'd to off-screen row addresses within Plane A's nametable each frame.

**Character sprite budget:** Up to 128 tiles for the current animation frame, DMA'd every frame. If strictly one character at a time (no AI follower), this can shrink to 64 tiles. The tiles occupy off-screen nametable space that would otherwise be wasted — zero cost against the art pool.

**Build-time tile graph coloring (NOVEL):** The build tool analyzes all sections in the zone and constructs an adjacency graph (which sections can be simultaneously visible — up to 4 at any corner of the 2D grid). Non-adjacent sections can reuse the same VRAM tile indices, like register allocation in a compiler. Shared tiles (used by multiple sections) get permanent VRAM indices. Unique tiles get reusable indices freed when their section scrolls off-screen, overwritten by the next section's tiles.

Result: most section transitions require zero tile DMA. Nametable entries already point to the correct tile indices because they were preloaded to non-conflicting addresses. No commercial Genesis game does build-time VRAM tile allocation with graph coloring — this is novel but grounded in proven compiler algorithms.

**Section VRAM lifecycle:**
1. **Build time:** Graph coloring assigns VRAM indices. Shared tiles get permanent indices; unique tiles get reusable indices.
2. **Level load:** Permanent tiles (HUD, rings) and initial section tiles loaded via S4LZ.
3. **Section preload (~85 frames before boundary):** New section's unique tiles streamed via S4LZ to their assigned VRAM addresses (Deferrable DMA, spread across frames). No conflict with currently visible tiles because the graph coloring guarantees non-overlapping assignments for simultaneously visible sections.
4. **Section exit:** Unique tile VRAM addresses marked as reclaimable. Art stays cached (lazy reclaim) — backtracking reuses it without re-decompression.

**Auto-calculated addresses:** Permanent-category objects (HUD, rings, monitors, springs, etc.) are defined sequentially in `VRAM_Layout.asm` with tile counts. The assembler computes addresses automatically — adding/removing an object shifts everything after it. Compile-time overflow check ensures permanent allocations don't exceed the pool budget.

**Cross-references:** §2.2 (allocator). Vectorman: 64×64 plane validation. S.C.E.: off-screen nametable embedding. Batman: raw nametable data in ROM.

### 2.4 Per-Section Background Support

**Purpose:** Enable per-section visual variety on Plane B (background) independently from Plane A (foreground).

The Genesis VDP has completely separate planes — Plane A and Plane B have independent nametables, scroll positions, and can reference different tiles. This means per-section BG data is architecturally straightforward.

**Three tiers:**

| Tier | Layout | Art | VRAM Cost | Use Case |
|------|--------|-----|-----------|----------|
| 1. Zone-wide shared | One BG layout for zone | Shared BG tile region (zone-wide, fixed) | 256 slots reserved | Simple parallax, most sections |
| 2. Per-section layout | Different BG arrangement | Shared BG tile region (zone-wide, fixed) | 256 slots reserved | Visual variety with existing BG art |
| 3. Per-section art+layout | Different BG tiles+layout | Section's A.3 art group | Pool tiles | Unique BG (mountain skyline, etc.) |

**Shared BG tile region (T1/T2):** A fixed VRAM range — slots 1280-1535, byte addresses $A000-$BFFF, 256 tiles × 32 B = 8 KB capacity — is reserved for BG-only tile art. Loaded **once** at level init alongside the initial FG section pools and **never** overwritten by section transitions. This solves the architectural mismatch with A.3's per-section graph-colored FG pool: BG tiles must remain at consistent VRAM slots across all section transitions for the BG nametable's tile-index references to stay valid.

T1 ships with the shared region populated from `act_bg_tiles` (zone-wide pointer). T2 reuses the same region — only the per-section nametable changes. T3 sidesteps the region entirely and lives in the section's A.3 art group (per-section, swapped on transition), giving each T3 section unique BG tile art at the cost of additional FG-pool budget pressure.

**Section entry integration (post-§2 A.5):**
- `act_bg_layout` (Act struct, longword at $16) — zone-wide BG nametable pointer; drawn once at level load by `BG_Init`.
- `act_bg_tiles` (Act struct, longword at $1A) — zone-wide BG tile blob pointer; loaded once at level load into VRAM $A000 by `BG_Init`.
- `sec_bg_layout` (Sec struct, longword at $1C) — per-section BG nametable pointer (NULL = use Act default). Drawn by `Section_RedrawPlanes` at level init / cache recovery. Teleports no longer redraw Plane B (pure rebase, §4.4); a per-section BG *swap* at the seam needs a future deferred mechanism if a zone ever authors differing per-section BG layouts.

**Storage shape:** Each layout is a **raw 64×32 nametable** (4096 bytes uncompressed). BG tile blob is raw uncompressed tiles (32 B per tile, ≤ 256 tiles per zone). No `sec_bg_plc_off` field — T3 BG tile art folds into the section's existing A.3 art group (`sec_tile_art`). T3 BG tiles ride the unified per-section blob loaded by `Section_LoadArt` — no parallel streaming code for T3. (A.4's `Section_StreamArtGroup` was deleted 2026-06-11: the union-blob model leaves neighbor art already resident, so runtime art streaming had zero callers.)

**Tier detection (build-time):** `sec_bg_layout=NULL` → T1; `sec_bg_layout≠NULL` and BG tile refs ⊆ shared BG region → T2; `sec_bg_layout≠NULL` with section-specific BG-only tiles → T3.

**Engine cost:** T1 = one 4 KB nametable blit + one BG-tile-blob DMA at level init, zero per-frame. T2 = same load cost; one 4 KB nametable blit on FWD/BWD teleport (~0.6 ms blocking via VDP DATA port). T3 = nametable blit + tile streaming via A.4. Deferrable-DMA optimisation tracked in DEFERRED_WORK.

**Allocator integration:** T3 BG tiles are part of the section's existing tile-art group, so the allocator treats them identically to FG tiles. Debug assertions catch pool overflow if FG + BG combined exceeds the section's color-graph slot budget. Shared BG tile region (T1/T2) is allocator-owned but treated as a single permanent allocation — never freed.

**VRAM map summary (post-§2 A.5):**
```
$0000-$0E1F  color-0 section's FG tile pool (113 tiles for OJZ; per-section, swapped)
$0E20-$1EBF  color-1 section's FG tile pool (113 tiles for OJZ; per-section, swapped)
...          (free for FG growth as zones get bigger; up to slot 1279)
$A000-$BFFF  shared BG tile region (256 tiles max; fixed, loaded once)
$C000-$CFFF  Plane A nametable
$E000-$EFFF  Plane B nametable
$F800-$FFFF  region-2 spill (A.2; off-screen Plane B rows)
```

### 2.5 Art Loading Flow

**Level load (blocking):**
```
LoadSectionTiles
  → S4LZ decompress current section's FG tile art → VRAM $000+
    (tile-delta preprocessing reversed during decompression)
  → S4LZ decompress block data → 2D tile cache
    (no chunk/block tables — section grid handles layout directly)
LoadArt (S4LZ blocking, synchronous)
  → Decompress permanent art (HUD, rings, etc.) → VRAM permanent region
  → AllocVRAM for each zone object type → bump allocator + queue S4LZ
  → ProcessDMAQueue flush after each entry
```

**Section transition (streaming, non-blocking):**
```
Section_Preload (~16 frames before boundary)
  → Scan incoming section's object layout
  → AllocVRAM for each type:
      Already loaded (refcount > 0)? → skip, bump refcount
      New type? → bump cursor, queue S4LZ stream
  → If incoming section has unique tile art:
      → S4LZ stream section tiles into ~4KB RAM decompression buffer
      → DMA to VRAM $000+ region (Deferrable priority, spread across frames)
  → FreeVRAM for outgoing section's unique types
  → Palette fade begins (2-axis interpolation)

Section_Enter (at boundary)
  → Section_ResetVRAM: compact unified pool, reclaim dead art
  → All art already in VRAM (preloaded ~16 frames ago)
  → Section tile art already DMA'd from preload buffer
  → Objects spawned with art_tile from allocator's loaded table
  → Zero visible loading artifacts
```

**Emergency spawn (mid-gameplay):**
```
Boss spawns new enemy type not in section layout
  → AllocVRAM(new_type_id)
  → Art metadata says S4LZ_BLOCKING + 12 tiles
  → Instant S4LZ decompress to allocated VRAM address
  → Object spawns with valid art_tile same frame
  → No streaming delay, no pre-planning needed
  (S4LZ at 700-1100 KB/s: 12 tiles = 384 bytes decompressed in <0.5ms)
```

**Sprite art via DPLC/DMA (per-frame):**
```
AnimateSprite
  → Animation frame changes (ros_prev_frame != current frame)
  → Perform_DPLC: read DPLC table for this animation frame
    → DPLC entry: tile_count + tile_start → ROM source address
    → Build-time contiguous layout: 1 DMA entry per frame change
  → Queue DMA from ROM directly to allocated VRAM address
    (Important priority for characters, Deferrable for objects)
  → DPLC Lookahead (§1.6): if anim_timer <= 1, peek next frame's DPLC
    → Pre-queue as Important DMA → art ready before animation advances
  → Zero CPU decompression cost — DMA runs on VDP clock
```

**Per-section tile art — RAM footprint:**
```
S4LZ decomp buffer: ~$1000 (4,096 bytes)

No chunk tables, block tables, level layout arrays, or UFTC tile buffers in RAM.
All tile data streams from ROM via S4LZ on demand.
Sprite art DMA'd directly from ROM — no RAM buffer needed.
```

### 2.6 Data Format Summary

The engine uses one compression format (S4LZ), one random-access format (uncompressed + DPLC), and raw tilemaps. No other decompressors exist in the codebase.

| Data Class | Format | Build Tool | ROM Label Convention |
|---|---|---|---|
| Level/bulk art | S4LZ (with tile-delta preprocessing) | `s4lz_compress` (Python/C, optimal parsing) | `ArtS4LZ_*` |
| Sprite art | Uncompressed + DPLC tables | `dplc_layout` (build-time contiguous rearrangement + entry merging) | `ArtUnc_*` / `DPLC_*` |
| Tilemaps | Raw (uncompressed VDP nametable words) | Direct export from editor | `Tilemap_*` |

**Art source pipeline:** Original art assets (extracted from Sonic 2/3K or created new) are stored as raw uncompressed tiles in `art/raw/`. Level art is compressed to S4LZ at build time. Sprite art stays uncompressed — the build tool rearranges tiles for contiguous per-frame layout and generates optimized DPLC tables.

**ROM footprint:** S4LZ decompressor is ~2-5 KB (jump table dominates). DPLC routine (`Perform_DPLC`) is ~0.2 KB. Raw tilemaps need no decompressor. Total decompression/loading code: ~2.5-5.5 KB ROM.

### 2.7 Cascade Effects

```
Two-Tier Compression (2.1)
  → S4LZ handles all bulk/level art
    → Streaming mode: interruptible via cooperative multitasking (§9.7), Deferrable DMA
    → Blocking mode: instant same-frame decompression for small art
    → 700-1100 KB/s throughput
    → Tile-delta preprocessing: 10-25% better compression at build time
      → Runtime undo: ~8.5 cycles/byte (negligible)
  → Uncompressed sprite art + DPLC/DMA — zero CPU decode cost
    → Build-time contiguous layout: 1 DMA per animation frame change
    → DMA from ROM on VDP clock — CPU free for game logic
    → DPLC Lookahead (§1.6) pre-loads next frame's art
  → Raw tilemaps for menus — direct DMA from ROM, zero decode cost

Dynamic VRAM Allocator (2.2)
  → AllocVRAM reads art metadata for tile counts + format
    → S4LZ format → queue Deferrable DMA stream (streaming)
    → S4LZ blocking → instant decompress (small/emergency)
    → Uncompressed → set art_source pointer for DPLC per-frame loading
  → Refcounting keeps shared art across section transitions
    → Springs, monitors, rings never re-decompress
    → Lazy reclaim = free caching for backtracking
  → Section_ResetVRAM compacts on transition
    → Zero fragmentation within section lifetime
  → Debug assertion on overflow → crash screen with full context

Per-Section Tile Art (2.5)
  → Each section can have unique foreground tile graphics
    → S4LZ compressed with tile-delta in ROM (~4KB buffer in RAM)
    → DMA'd to VRAM $000+ during section preload (spread across frames)
  → No chunk/block tables in RAM
    → Pre-computed block data from build tool, zero runtime conversion
      → Zero per-frame cost for level rendering (tile cache → plane buffer → VDP)
  → Tile overflow impossible by construction
    → Unified pool: each section's tiles allocated anywhere in $000-$5FF
    → Build-time graph coloring prevents conflicts between visible sections

Allocator + Load_Object Integration (3.7)
  → Load_Object calls AllocVRAM(type_id)
    → Already loaded? Return addr in ~20 cycles
    → New type? Allocate + decompress in ~50 cycles + stream time
      → No hardcoded VRAM constants in object data blocks
        → Adding new objects = add to layout + art metadata, done

Predictive Pre-Allocation (4.8)
  → Section grid knows adjacent sections
    → Section_Preload scans incoming objects → AllocVRAM for each
      → Proactive FreeVRAM for outgoing-only types
        → Pool compaction makes room before new art loads
      → Section_Preload also streams incoming section tile art
        → Art + tiles both ready before player crosses boundary
          → Zero visible loading at section transitions

Build Pipeline (8.1)
  → S4LZ compressor (Python/C, optimal parsing)
  → DPLC layout tool (contiguous art rearrangement + entry merging)
    → Raw tilemap export (no encoder needed — direct nametable data)
```

---

## 3. Object System

The object system is the backbone — every gameplay entity (players, badniks, rings, monitors, bosses, effects, HUD elements) is an object with a fixed-size slot in RAM, running a state machine each frame. The design targets: O(1) allocation, data-driven spawning and child creation, a modular collision system, and an animation system that doubles as a lightweight behavior sequencer.

### 3.1 SST Layout — $50 Bytes, Logical Field Grouping

Every object occupies an 80-byte ($50) Sprite Status Table entry. Fields are grouped by logical function — dispatch, physics, render/collision, animation, links, engine, and custom data. The 68000 has no data cache, so there is no hardware benefit to field ordering. The grouping is a code-maintenance and `movem` optimization: related fields at contiguous offsets means routines that access multiple fields can batch them, and the layout is self-documenting.

The one field that IS performance-critical at $00: `move.w (a0), d0` (zero offset) saves 2 bytes + 4 cycles per dispatch versus any non-zero `d(a0)` offset. All `d(An)` displacements within a $50 SST are 16-bit and cost the same — $00 is the only special case.

```
; === Dispatch ===
$00  code_addr              ; (word) — object code offset from ObjCodeBase
                            ;          zero = empty slot

; === Physics ===
$02  x_pos                  ; (long) — 16.16 subpixel position [patched at spawn]
$06  y_pos                  ; (long) — 16.16 subpixel position [patched at spawn]

; === Template block $0A-$1F — burst-copied verbatim from ObjDef at spawn ===
$0A  x_vel                  ; (word) — horizontal velocity (8.8 fixed-point)
$0C  y_vel                  ; (word) — vertical velocity (8.8 fixed-point)
$0E  render_flags           ; (byte) — bit 0 on-screen, 1 x-flip, 2 y-flip,
                            ;          3 coord mode, 4 multi-sprite,
                            ;          bits 5-7 priority band (absorbs old $16 word)
$0F  collision_resp         ; (byte) — collision type dispatch (0 = none)
$10  mappings               ; (long) — sprite mapping pointer (ROM)
$14  art_tile               ; (word) — VRAM tile index + palette + priority
$16  width_pixels           ; (byte) — collision width (FULL, not half)
$17  height_pixels          ; (byte) — collision height (FULL, not half)
$18  anim                   ; (byte) — desired animation ID
$19  subtype                ; (byte) — object subtype
$1A  anim_table             ; (long) — animation table pointer (ROM)
$1E  status                 ; (byte) — player/object status bits (ST_*)
$1F  angle                  ; (byte) — terrain angle

; === Runtime block $20+ — initialized individually at spawn ===
$20  prev_anim              ; (byte) — previous anim ID ($FF at spawn)
$21  anim_frame             ; (byte) — byte offset within animation script
$22  anim_timer             ; (byte) — frame duration countdown
$23  mapping_frame          ; (byte) — current mapping frame index
$24  prev_frame             ; (byte) — previous mapping_frame ($FF at spawn)
$25  sprite_piece_count     ; (byte) — current frame's piece count (overflow prediction)
$26  parent_ptr             ; (word) — parent object RAM address
$28  sibling_ptr            ; (word) — sibling link (multi-part objects)
$2A  slot_tag               ; (byte) — entity window slot tag (SLOT_TAG_*; $FF = untagged)
$2B  entity_section_id      ; (byte) — spawning section's flat id (despawn bookkeeping)
$2C  entity_list_index      ; (byte) — index in section's ROM object list (killed bitmask)
$2D  layer                  ; (byte) — collision layer select (0 = path A, 1 = path B)

; === Custom data — per-object overlays ===
$2E-$4F  sst_custom (34 bytes) ; Player overlay, boss overlay, or custom
                               ; (objvarsCheck asserts overlay fits)
```

**Dispatch:** Word code_addr at $00 stores an offset from `ObjCodeBase` (a $10000-aligned label). Dispatch reconstructs the full address: `moveq #BANK, d0; swap d0; move.w (a0), d0; movea.l d0, a1; jsr (a1)`. The `objroutine` AS function computes offsets at build time: `objroutine function x, (x)-ObjCodeBase`. `tst.w (a0); beq.s .skip` tests for empty slots. This is the sonic_hack pattern — validated across the full game.

**Template block:** The 26-byte ObjDef archetype image (3.7) is a verbatim ROM copy of SST $00 (code_addr) plus $0A-$21 — spawning burst-copies $0A-$21 (24 bytes) with `movem.l`, zero field reordering ($20-$21 land as pad and are immediately re-initialized by the runtime init). Sprite priority lives in render_flags bits 5-7 (`RF_PRIORITY_SHIFT`/`RF_PRIORITY_MASK`) — the old separate priority word at $16 is gone.

**Links:** `sibling_ptr` replaces `child_ptr` — Alien Soldier's research shows dual link fields (parent + sibling) are more useful than parent + child for multi-part boss communication.

**SST size stays $50.** The objects-v2 field audit removed the dead fields (`respawn_index`, `wait_timer`, the separate priority word) and packed the entity-window metadata (`slot_tag`/`entity_section_id`/`entity_list_index`/`layer`) into the freed space, growing `sst_custom` to 34 bytes at $2E. Whether player overlays need more than 34 bytes (variable-size pools, per-pool stride) remains open for the §5 player work — see DEFERRED_WORK.md.

**Slot ranges:**
- Slots 0-1: Players (Sonic, Tails)
- Slots 2-41: Dynamic level objects (40 slots)
- Slots 42-57: Effects/particles (16 slots — ring scatter, explosions, dust, score popups)
- Slots 58-65: System objects (HUD, shields, title cards)

Each range has its own free stack for targeted allocation. Effect objects can never fill gameplay slots. Spawn guard (from Thunder Force IV): `cmp.w #MAX, spawn_count; bhi .skip` prevents cascade pool exhaustion.

### 3.2 Free Slot Stack — O(1) Allocation (NOVEL)

All reference engines use linear scan for object allocation. S.C.E.'s `Create_New_Object` scans with `tst.l code_addr(a1); dbeq d0,.find`. Batman uses a doubly-linked free list (heavier). Our approach is simpler and faster than both:

```
Free_Slot_Stack:    ds.w  MAX_DYNAMIC_SLOTS   ; word array of free slot addresses
Free_Slot_SP:       ds.w  1                    ; stack pointer

; Allocate: one instruction
AllocSlot:
    movea.w -(Free_Slot_SP), a1     ; pop free slot address

; Free: one instruction  
FreeSlot:
    move.w  a0, (Free_Slot_SP)+     ; push slot back

; Init at level start: push all dynamic slot addresses
```

O(1) allocate, O(1) free, zero overhead, no linked-list pointers consuming SST space. All five `SingleObjLoad` variants collapse into one stack pop. `DeleteObject` becomes a stack push + slot clear (via `movem.l` — two instructions clear all 80 bytes). No commercial Genesis game uses this approach — all use linear scan. This is the single biggest algorithmic win in the object system.

**Deletion strategy: immediate.** Research across 7 references overwhelmingly favors immediate deletion (5/7 use it). `DeleteObject` pushes the slot address back to the free stack, then zeros the entire SST. No mark bits, no sweep pass, no deferred phase. `RunObjects` skips empty slots via `tst.w (a0); beq.s .skip`. Parent-child cascades are safe: children check `tst.w (parent_ptr)` — if parent's code_addr is zero, child self-deletes. Alien Soldier's mark-and-sweep exists to solve mid-iteration mutation of a pointer list, which our stride-based iteration avoids by design.

**Spawn guard (from Thunder Force IV):** `cmp.w #MAX_SPAWNS_PER_FRAME, spawn_count; bhi .skip` prevents pathological pool exhaustion from spawn cascades (e.g., ring scatter triggering multiple explosion spawns).

### 3.3 Data-Driven Child Creation (from S.C.E.)

S.C.E. has 12 child creation routines, all driven by descriptor tables. Distilled to 4 core strategies that cover all use cases:

| Strategy | Descriptor Fields | Use Case |
|---|---|---|
| **CreateChild_Normal** | code_addr, XY offsets | Badnik projectiles, debris |
| **CreateChild_Complex** | code_addr, setup_addr, animations, wait_addr, XY offsets, velocity | Boss sub-objects with full init |
| **CreateChild_Linked** | code_addr (repeated, doubly-linked chain) | Snake segments, train cars |
| **CreateChild_FlipAware** | Same as Complex, negates X when parent flipped | Directional boss weapons |

All use the free slot stack for allocation. All auto-set `parent_ptr`/`sibling_ptr`. Children inherit `mappings` and `art_tile` from parent (no separate VRAM allocation for shared art).

**Cleanup chain:** On parent death, walk sibling_ptr chain and delete all children. Children also check parent — if parent's code_addr is zero, self-delete. S.C.E.'s `Child_Draw_Sprite` auto-delete behavior is ported into the render path.

**Descriptor table example:**
```
BossChildren:
    dc.w  3-1                ; 3 children (dbf format)
    dc.l  BossArm            ; child 1 code
    dc.b  -24, -16           ; child 1 XY offset
    dc.l  BossArm            ; child 2 code
    dc.b  24, -16            ; child 2 XY offset
    dc.l  BossHead           ; child 3 code
    dc.b  0, -32             ; child 3 XY offset
```

### 3.3.1 Effect Pool Spawning (fire-and-forget)

`CreateEffect_Normal` and `CreateEffect_Simple` mirror the child creation API but allocate from the **effect pool** (16 dedicated slots) instead of the dynamic pool. Effects are fire-and-forget: no sibling chain linking, no parent lifecycle management. They auto-despawn via `AF_DELETE` when their animation ends.

| Routine | Inputs | Behavior |
|---|---|---|
| **CreateEffect_Normal** | a0=parent, a1=descriptor (same 4-byte format as CreateChild_Normal) | Allocate from effect pool, inherit mappings/art_tile, set parent_ptr, position from parent + offsets |
| **CreateEffect_Simple** | a0=parent, d0.w=code_addr, d1.w=count | Spawn N identical effects at parent position from effect pool |

Both fail silently on pool exhaustion. Effects use `AllocEffect`/`DeleteObject` which manages the effect free stack independently from dynamic slots — effect objects can never consume gameplay object slots.

**Render_Sprites mid-frame guard:** Objects added to a sprite band via `Draw_Sprite` can be deleted later in the same `RunObjects` pass (e.g., `DeleteChildren` cascade). `Render_Sprites` guards against this by checking for null mappings before processing each band entry, skipping zeroed slots.

### 3.4 Collision System — Type Dispatch with Direct Dimensions (NOVEL)

The collision system is a custom design that's more modular than any reference engine. Traditional approaches pack collision type + size into one byte and look up dimensions from a table. S.C.E. uses a registration list. Our approach:

- `collision_response` is a **pure type byte** — determines *how* the object reacts to contact (solid, enemy, spring, hurt, etc.)
- `width_pixels` / `height_pixels` in the SST provide collision dimensions directly — no lookup table needed
- `TouchResponse` iterates all dynamic slots, checks `collision_response` for non-zero, and dispatches to the appropriate handler

**Collision types:**
```
COLLISION_NONE          = 0
COLLISION_ENEMY         = 1     ; killable by spin/roll
COLLISION_BOSS          = 2     ; killable, HP-based
COLLISION_HURT          = 3     ; hurts on any contact
COLLISION_MONITOR       = 4     ; breakable from below/spin
COLLISION_RING          = 5     ; collectible
COLLISION_BUBBLE        = 6     ; air bubble
COLLISION_PROJECTILE    = 7     ; fire-and-forget damage
COLLISION_SOLID         = 8     ; full AABB solid
COLLISION_SOLID_BREAK   = 9     ; solid, breaks when spinning
COLLISION_SPRING        = 10    ; solid + bounce (5 directions)
COLLISION_SOLID_HURT    = 11    ; solid + hurts on specific face
COLLISION_TOUCH         = 12    ; generic touch (object handles via ckhit)
```

Each handler uses doubled-delta AABB math with the full `width_pixels`/`height_pixels` values. Touch_Solid does axis detection (which side was contacted) for proper standing/push/slide behavior. Touch_Spring reads orientation from subtype bits. Touch_SolidHurt checks contact face against `objoff_3A` (SPIKE_FACE_TOP/BOTTOM/SIDES).

**Why this beats every reference:** Objects set collision_response to a type and width/height to their actual dimensions — done. No size table, no registration, no bit packing. Any object can become solid, or an enemy, or a spring, just by changing one byte. New collision behaviors are new handler routines + a new type constant.

### 3.5 Sprite Rendering Pipeline (from S.C.E.)

S.C.E.'s two-phase approach:

**Phase 1 (during object loop):** Each object calls `Draw_Sprite`, which resolves the current mapping frame, culls exactly against its precomputed bbox header (7.8), and adds the object's RAM address to a priority-band list. No sprite data conversion.

**Phase 2 (`Render_Sprites`):** Single pass through priority-sorted lists, converting object data to VDP sprite table entries. Handles:
- **Standard sprites:** `BuildSprites_Classic` — dynamic frame indexing from mapping table
- **Static sprites:** `BuildSprites_Static` — fixed mapping, no animation
- **Compound sprites:** `BuildSprites_Compound` — walks sibling_ptr chain (3.3), one bounds check for parent, all children render under it

**Multi-sprite batching:** `render_flags.multi_sprite` routes to `Render_Sprites_MultiDraw`. Combined with parent-driven animation (3.7), a multi-part boss is: one AnimateSprite call on parent → one bounds check → all children render. Three systems converge.

**Additional features:**
- Pre-initialized link chain (80 entries, set at level init); per-frame Render_Sprites rewrites links for emitted pieces and patches the terminator after the last one (the "never rebuilt" optimization is a wash on 68000 — see §1.2)
- Overflow protection: full priority band overflows to next band (S.C.E.), with TF4-style round-robin rotation if overflow is visible
- Sprite count per object in SST for overflow prediction (from Batman's `sprite_link_count`)
- Sprite table dirty flag — skip $280-byte DMA on static frames (confirmed by Gunstar's conditional sprite DMA pattern)
- VDP-order mapping format eliminates field reordering (pre-formatted SAT already achieved)

**Sprite link-order cycling for overflow fairness (IMPLEMENTED):** When >20 sprites land on one scanline, the VDP drops everything past the 20th in link-chain order. `Render_Sprites` reverses intra-band object processing direction on odd frames via `Sprite_Cycle_Counter`, distributing dropout as flicker rather than permanent disappearance. Step direction (+2/-2) stored on stack to avoid register pressure. Cost: +3 scanlines on Render_Sprites. Only Thunder Force IV among commercial games implements this.

**Sprite X=0 masking (IMPLEMENTED):** `InsertSpriteMasks` writes 8×32px sprites at X=0 between priority bands during SAT construction. Configured via `SpriteMask_Y` (VDP Y position), `SpriteMask_Height` (scanlines to cover), `SpriteMask_After_Band` (insertion point). The VDP stops rendering subsequent sprites on covered scanlines. Zero cost when disabled (`SpriteMask_Y = 0`). Used for HUD/status bar clipping without the Window plane.

**Scanline-aware sprite budgeting (IMPLEMENTED):** Screen divided into 7 bands of 32 scanlines. `Scanline_Band_Sprites` array tracks accumulated sprite pieces per band. At `.have_pos` in `Render_Sprites`, objects are skipped when their band exceeds `SCANLINE_SPRITE_LIMIT` (24 pieces). Threshold optimization: budget check skipped entirely when total rendered pieces < 24 (no band can overflow yet). Cost: +6 scanlines on Render_Sprites. No commercial Genesis game implements per-band sprite budgeting.

**VDP sprite cache behavior (from Kabuto hardware notes):** The VDP processes sprites in 4 phases per scanline: (1) scan Y/size/link from write-through cache, (2) fetch X/tile fresh from VRAM, (3) render tiles to line buffer, (4) display. Y/size/link are cached via write-through — CPU writes to SAT VRAM update the cache immediately. X/tile is re-read from VRAM each frame. Both per-scanline limits (20 sprites AND 320 sprite pixels) are enforced simultaneously — whichever is hit first causes dropout.

### 3.6 Animation System — Behavior Sequencer (NOVEL)

The animation system is a **lightweight behavior sequencer** — bytecode-driven animation with frame-triggered callbacks. No Genesis game has this.

**Bytecode animation script format:**
```
Ani_Walk:
    dc.b  4              ; frame duration (ticks)
    dc.b  0, 1, 2, 3     ; mapping frame indices
    dc.b  $FF             ; loop
; Control codes: $FF=loop, $FE=jump back, $FD=branch, $FC=routine-inc, $FB=delete
```

**Animation events (NOVEL):**
All events consume an even number of bytes (for PerFrame alignment). Events execute inline when encountered and continue reading the next byte — multiple events can chain before a frame.
```
$FA = AF_CALLBACK   (dc.b $FA, target_hi, target_lo, 0) — call objroutine offset (big-endian byte pair; scripts are unaligned)
$F9 = AF_SOUND      (dc.b $F9, sound_id)             — play sound effect (stub until driver)
$F8 = AF_COLLISION  (dc.b $F8, collision_type)        — set SST_collision_resp
$F7 = AF_SET_FIELD  (dc.b $F7, sst_offset, value, 0) — set arbitrary SST byte
```

Speed-linked animation and per-frame delays are handled by calling conventions (`AnimateSprite` vs `AnimateSprite_PerFrame`), not by event codes. Speed formula: `duration = max(0, ($800 - abs_speed)) >> 8`.

**Example — boss attack with events (PerFrame mode):**
```
Ani_BossAttack:
    dc.b  0, 8             ; frame 0: 8 ticks (slow wind-up)
    dc.b  1, 6             ; frame 1: 6 ticks
    dc.b  AF_COLLISION, COLLISION_HURT  ; EVENT: become dangerous
    dc.b  2, 2             ; frame 2: 2 ticks (strike)
    dc.b  AF_SOUND, sfx_Impact         ; EVENT: play impact sound
    dc.b  AF_CALLBACK, (objroutine(BossFireHook))>>8, (objroutine(BossFireHook))&$FF, 0 ; EVENT: call routine
    dc.b  AF_COLLISION, COLLISION_SOLID ; EVENT: safe again
    dc.b  3, 4             ; frame 3: follow-through
    dc.b  AF_END            ; loop
    even
```

Objects that currently do "check timer → spawn thing" delete that logic entirely. Animation scripts handle all timing. New attack patterns = new data, not new code.

**Animation table in SST:** Stored at `anim_table` ($1A), set by `Load_Object` from the archetype template. `AnimateSprite` reads it internally — no more `lea (Ani_Table).l,a1` before every call. Saves ~60 `lea` instructions per frame across all active objects.

**Multi-sprite animation (from S.C.E.):** `Animate_MultiSprite` drives all children from the parent's animation script. Each child reads the parent's `mapping_frame` and applies its own mapping offset. Multi-part objects animate in sync with one call.

### 3.7 Object Loading — Archetype Templates (objects-v2)

Each object type is a 26-byte ObjDef archetype: a verbatim ROM image of SST $00 (code_addr) plus the $0A-$21 template block, emitted by the `objdef` macro (macros.asm):

```
; ObjDef layout (26 bytes — exact SST image, zero field reordering):
;   +0:  dc.w  objroutine(Code)              ; code_addr
;   +2:  dc.w  x_vel, y_vel                  ; $0A-$0D image
;   +6:  dc.b  render_flags, collision_resp  ; $0E-$0F image (priority in RF bits 5-7)
;   +8:  dc.l  mappings                      ; $10-$13 image
;   +12: dc.w  art_tile                      ; $14-$15 image
;   +14: dc.b  width, height                 ; $16-$17 image
;   +16: dc.b  anim, subtype                 ; $18-$19 image
;   +18: dc.l  anim_table                    ; $1A-$1D image
;   +22: dc.b  status, angle                 ; $1E-$1F image
;   +24: dc.w  0                             ; $20-$21 pad (re-inited at spawn)

objdef code=TestEnemy_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
       zpri=4, xvel=ENEMY_PATROL_SPEED, wdth=16, hght=16, col=COLLISION_HURT
```

`Load_Object` spawns in three steps:

1. **Allocate:** `AllocDynamic` pops a free SST address (3.2) and tags the slot `SLOT_TAG_UNTAGGED` ($FF) — the entity window (4.9) re-tags slots it owns.
2. **Burst copy:** code_addr word, then the 24-byte $0A-$21 block via three `movem.l` pairs — no per-field parsing, no format byte, no conditional paths. The ObjDef layout IS the SST layout.
3. **Per-placement patch:** X/Y converted to 16.16 and stored; placement subtype overwrites the template default; placement flip bits (OEF bits 13-14) rotate into position with a single `rol.w #4` and OR into both render_flags (RF_XFLIP/RF_YFLIP) and status; runtime block re-initialized (prev_anim/prev_frame = $FF for change detection); `sprite_piece_count` seeded from mapping frame 0's piece count (at +4, after the bbox header — 7.8).

Art is referenced by `art_tile` directly (build-time VRAM layout); per-frame character art goes through the DPLC pipeline (3.9). Every object type's full spawn state lives in its objdef line — single source of truth, and the macro build-fails on overflow (priority > 7, image size ≠ 26).

### 3.8 Per-Frame Systems — Design Rationale

Comparative analysis across S.C.E. and 5 commercial Genesis engines informed which per-frame system patterns to adopt vs. redesign:

| System | Approach | Architecture |
|--------|----------|--------------|
| **Render_Sprites** | S.C.E. two-phase | 8-priority-level iteration with pre-computed link numbers at init, render callbacks for level-specific sprite injection. |
| **RunObjects** | Tiered execution | 4-tier execution (Reserved/Dynamic/LevelOnly/Deferred). Slot-based entity management (4.9) handles spawn/despawn lifecycle. |
| **Entity Management** | Camera-driven window (novel) | Camera-driven entity window (4.9) with per-section X-sorted ROM lists, unified ring buffer, 3×3 rolling collected bitmask. Free slot stack (3.2) for runtime-spawned objects. |
| **AnimateSprite** | Bytecode sequencer | Bytecode system ($FF/$FE/$FD/$FC/$FB) with animation events (3.6) and pause flag. |
| **TouchResponse** | Type dispatch | Two-pass gather→respond with per-type handlers (3.4). Collision masks for early-exit. Modular file structure per collision type. |
| **Ring System** | Camera-driven (novel) | Unified 128-entry ring buffer, flat X-sorted ROM lists per section, swap-with-last O(1) removal, 3×3 rolling collected bitmask (4.9). |

**Dynamic allocator integration with free slot stack (3.2):** The free slot stack provides the allocation primitive for both paths. Level objects spawn via the camera-driven entity window (4.9) — as objects scroll into camera range, their compact 6-byte ROM entries are read, the section's ROM type table is consulted for the ObjDef pointer, and `Load_Object` calls `AllocDynamic` to pop a free SST address. Dynamic objects (boss parts, projectiles, cutscene actors) call `AllocDynamic` directly. Both paths produce objects in the same SST — the execution loop doesn't distinguish them.

**Parent-child links (from Treasure — Gunstar Heroes / Alien Soldier):** The `parent_ptr` ($26) and `sibling_ptr` ($28) fields in the SST (3.1) enable multi-part boss coordination: child auto-delete when parent dies, sibling chain iteration, inherited art/palette. Validated by 380+ references in Alien Soldier.

### 3.9 Per-Frame Art Loading (DPLC Pipeline)

Two tiers of per-frame art management:

- **Static object art:** Loaded via `AllocVRAM` at spawn (§2.2). Stays resident until section transition or refcount reaches zero. No per-frame processing needed.
- **Animated sprite art:** Per-frame — animation frame changes need different tiles. Generic `Perform_DPLC` routine (works for all objects, not per-character) detects frame changes via per-object `ros_prev_frame` field, reads DPLC table for the new frame, and queues DMA from uncompressed ROM art directly to the object's allocated VRAM address. Build-time contiguous art layout guarantees 1 DMA entry per frame change. Character DPLCs → Important priority (guaranteed delivery). Object DPLCs → Deferrable priority (budget-gated).
- **DPLC Lookahead (NOVEL — §1.6):** When `anim_timer <= 1`, peek at the next animation frame's DPLC requirements and pre-load as an Important-priority DMA entry. Art arrives before the frame changes — zero-latency animation transitions. No Genesis game does this.
- **128KB DMA boundary safety:** All DPLC DMA transfers are checked for 128KB ROM boundary crossings. Transfers that would cross a boundary are split into two entries. See §2.1 for details.

### 3.10 Cascade Effects

```
Object System Cascades:

Free Slot Stack (3.2)
  → All child creation strategies use stack pop, not linear scan
    → DeleteObject pushes back to stack
      → Ring scatter pool uses dedicated stack range (slot ranges from 3.1)

Data-Driven Child Creation (3.3)
  → parent_ptr / sibling_ptr in SST link objects
    → BuildSprites_Compound walks child chain (3.5)
      → Animate_MultiSprite drives children from parent (3.6)
        → Child_Draw_Sprite auto-deletes orphans
          → Boss death = one walk + delete, zero orphaned sprites

Collision Type Dispatch (3.4)
  → collision_response set by Load_Object data block
    → width/height from SST, no lookup table
      → New collision behaviors = new handler routine + type constant
        → No registration, no bit packing, no size table

Animation Events (3.6)
  → Frame-triggered callbacks replace manual timer logic
    → Object code shrinks (delete "check timer → do thing" patterns)
      → New attack patterns = new animation data, not new code
        → Animation speed scaling links to velocity (one anim, continuous speed)

Load_Object + Allocator (3.7)
  → The archetype template includes art requirements
    → AllocVRAM checks loaded table → refcount bump or new load
      → S4LZ (streamed or blocking) or uncompressed (DPLC) based on format flag
        → art_tile written to SST from allocator return value
          → Child objects inherit parent art_tile (no separate alloc)

Per-Frame Art Loading (3.9)
  → Static object art: allocator handles at spawn (no per-frame processing)
  → Animated sprite art: Perform_DPLC queues DMA from ROM on frame change
    → Build-time contiguous layout: 1 DMA per frame change
    → Character DPLCs → Important priority, Object DPLCs → Deferrable
    → DPLC Lookahead (§1.6) pre-loads next frame's tiles
      → Zero-latency animation transitions

Camera-Driven Entity Integration (4.9 → 3.2 + 3.7)
  → Level objects spawn via camera-driven entity window
    → AllocSlot (3.2) provides SST address, Load_Object (3.7) initializes fields
      → Per-section type table resolves 5-bit index to routine pointer
        → Warp-based preview: objects live in preview zone before teleport
```

---

## 4. Level / World System

The level system is the engine's most unique feature. A 2D section grid with bidirectional streaming enables levels with true vertical depth — jungle canopy → floor → lake → cave. Each section is a 16×16 chunk cell with its own art, palette, parallax, objects, and music. The engine streams sections as the camera moves, loading and unloading content seamlessly. No Genesis game has achieved this level of per-area independence.

### 4.1 2D Section Grid — Bidirectional Streaming (NOVEL)

No Genesis game, S.C.E., or commercial engine streams level data in two dimensions. This is the engine's flagship architectural feature.

**2-slot block-paired streaming:**

2 slots per axis. Each teleport slides the window by one section: the trailing slot is despawned, the near slot shifts into the trailing position (coordinates adjust by ±SECTION_SHIFT), and the new leading slot loads fresh. The section map advances by 2 (`[Sec0,Sec1] → [Sec2,Sec3]`). Entity state is managed by the camera-driven entity window (4.9) — `EntityWindow_TeleportShift` shifts surviving entities' coordinates and rebuilds scan state from the updated slot map. The 3×3 rolling collected bitmask preserves ring collection state across nearby section revisits.

2 slots per axis with full bidirectional symmetry — no pinned slots:

```
Horizontal: [Slot L][Slot R]  — leapfrog L↔R in both directions
Vertical:   [Slot U][Slot D]  — leapfrog U↔D in both directions
Combined: 2×2 = 4 layout slots

        Slot L       Slot R
Slot U  [LU]         [RU]     ← upper row
Slot D  [LD]         [RD]     ← lower row
```

**Section addressing:** `section(X, Y)` where X is always positive (0 = level start) and Y is signed (0 = starting height, negative = above, positive = below). The camera Y position becomes a signed word — the Y=0 ceiling is removed.

**Leapfrog cycle (same pattern on both axes):**
1. Camera crosses midpoint of current section → preload next section into the behind slot (offscreen, safe to overwrite)
2. Preview is streaming-integrated (§4.2 — `PREVIEW_COLS = 24`): the linear-buffer streaming engine extends its range by `PREVIEW_COLS` into neighbor section data at each boundary. Neighbor data pointers cached in `Section_Fwd/Bwd_Neighbor_Data` (set at teleport/init, cleared when deferred cold-load overwrites the art). Preview content only becomes visible when the camera reaches the boundary, by construction — the streaming cursor writes preview cols just as they rotate off the visible right edge and onto the leading edge.
3. Camera reaches slot edge → teleport: positions shift, slots swap roles, camera wraps. The new pair's second slot is **NOT** cold-loaded inline — the load is deferred to mid-traversal of the new pair's first section (`SECTION_DEFERRED_FWD_LOAD = $0600` going right, `SECTION_DEFERRED_BWD_LOAD = $0C00` going left), keeping the just-left section's art alive for the BWD/FWD preview-visible window.

**Diagonal corner handling:** Both axes operate independently. At a corner, up to 3 sections may need preloading (H, V, and diagonal). The diagonal resolves naturally — you teleport on one axis first, then the diagonal cell becomes a normal neighbor. Diagonal preload queued at Priority 2 (deferrable) in the DMA system.

**Section size: 16×16 chunks (2048×2048 pixels per cell).** Sized for granular diversity — each cell gets its own palette, parallax, art, music. At max speed (~12px/frame), crossing takes ~170 frames with preload at midpoint giving ~85 frames for art streaming.

**Boundary clamping is data-driven:** When `section(X, Y)` has no neighbor (null in table), the camera clamps. No hardcoded boundaries. Levels can be irregularly shaped:
```
Example: Oracle Jungle Zone Act 1
              X=0      X=1      X=2      X=3
  Y=-1 (sky): [sky]    [sky]    [canopy]  [canopy]
  Y=0 (main): [intro]  [jungle] [ruins]   [temple]
  Y=1 (below):         [lake]   [cave]
  Y=2 (deep):                   [deep]
```

### 4.2 Section Definition — Per-Cell Configuration

Each section in the 2D grid is fully self-describing — almost its own level:

```
; Section definition — 72 bytes per (X, Y) cell (Sec struct in structs.asm):
    dc.l    sec_block_index      ; +$00: 256-entry block index (ROM pointer, see §4.3/§4.7)
    dc.l    sec_objects         ; +$04: object layout (compact 4-byte entries, X-sorted, see 4.9)
    dc.l    sec_rings           ; +$08: ring layout (flat X-sorted dc.w pairs, section-local coords, see 4.9)
    dc.l    sec_plc             ; +$0C: art PLC list (S4LZ format)
    dc.l    sec_pal             ; +$10: palette pointer — full 128-byte copy (0 = no change)
    dc.l    sec_parallax_config ; +$14: parallax_config pointer (0 = inherit act default; §4.6)
    dc.l    sec_raster_table    ; +$18: raster command table pointer (0 = keep current, see §7.2)
    dc.l    sec_bg_layout       ; +$1C: per-section Plane B layout pointer (NULL = use Act default; §2 A.5)
    dc.l    sec_type_table      ; +$20: type table (ROM): dc.b count,pad; dc.l ObjDef×N (§4.9)
    dc.l    sec_pal_cycle       ; +$24: palette cycling script (0 = keep current)
    dc.l    sec_sound_bank      ; +$28: DAC sample bank pointer (0 = keep current)
    dc.l    sec_reserved_2C      ; +$2C: reserved
    dc.l    sec_anim_blocks     ; +$30: animated tile script (0 = none)
    dc.l    sec_collision_s4lz  ; +$34: reserved (collision embedded in block data; §4.7)
    dc.w    sec_flags           ; +$38: SF_* bitmask (see below)
    dc.w    sec_music           ; +$3A: music change (0 = keep current)
    dc.b    sec_pcfg_pad_3C     ; +$3C: reserved (parallax config moved to sec_parallax_config)
    dc.b    sec_camera_lookahead; +$3D: camera look-ahead pixels (0 = zone default)
    dc.b    sec_pcfg_pad_3E     ; +$3E: reserved
    dc.b    sec_pcfg_pad_3F     ; +$3F: reserved
    dc.l    sec_tile_art_s4lz   ; +$40: per-section S4LZ tile pool ptr (§2 A.3)
    dc.w    sec_tile_art_vram   ; +$44: VRAM byte dest (color base × 32)
    dc.w    sec_pad_46          ; +$46: pad
; Sec_len = $48 (72 bytes)

; sec_flags: SF_HAS_WATER | SF_UNDERGROUND | SF_NO_Y_WRAP | SF_PRESERVE_STATE | SF_HAS_ANIMATED_BLOCKS
```

Fields default to 0 (keep current state). Each section is effectively its own world — unique terrain art, unique background motion, unique palette cycling, unique physics, unique music, unique parallax, all from data alone. No Genesis game has this level of per-area control within a single level.

**Palette format:** `sec_pal` points to a full 128-byte palette copy (all 4 palette lines × 16 colors × 2 bytes). No delta format, no compression — raw CRAM data, instant load on section transition. Palette cross-fading (7.1) interpolates between the outgoing and incoming 128-byte copies over ~16 frames.

### 4.3 Pre-Computed Nametable Data (Block-Based) (confirmed by Batman & Robin)

**Batman proof:** Batman stores raw VDP nametable words at $100000-$1DDFFF (909 KB of ROM). Zero CPU cost at scroll time — pure DMA from ROM to VRAM. This directly validates our approach.

**Our implementation — block-based format:**
- Level editor continues using chunks/blocks for design (unchanged workflow)
- Build pipeline converts chunk layouts into 16×16 tile blocks per section
- Each block contains a 2×2 grid of nametable words (8 bytes) plus embedded collision data
- Blocks are independently S4LZ-compressed in ROM with a 256-entry block index per section
- At level load, block data is decompressed into the 2D tile cache (§4.7) — an 80×60 array in RAM
- Scrolling reads nametable words from the tile cache and writes them to the plane buffer
- `Section_BuildRAMLayout` decompresses block data into the tile cache instead of chunk→block→tile conversion

**ROM cost:** 2-4 KB per section, 16-48 KB per act, ~128-384 KB for 8 acts = 3-10% of a 4 MB ROM.

**Dynamic terrain (breakable floors, moving platforms):** A small per-section runtime override table in RAM. When the scroll engine writes a new column to VRAM, it checks the override table and patches any modified tiles. Override table resets on section transition. Pre-computed nametables handle 99% of tiles; the override table handles the 1% that change.

**Prerequisite:** Deferred plane buffer (4.4) must be in place first — block-based cache data feeds into the buffer infrastructure.

### 4.4 Deferred Plane Buffer (from S.C.E., enhanced)

Producer-consumer pattern: all tile writes are buffered in RAM during the game loop, then flushed to VDP during VBlank. All 5 analyzed commercial games + S.C.E. use this approach — the game loop never touches the VDP data port.

- **Plane_buffer:** 768 words (1536 bytes) in RAM — 40% headroom beyond worst-case diagonal fast-scroll
- **Game loop:** `Draw_TileColumn` / `Draw_TileRow` queue updates into the buffer. Never touch VDP.
- **VBlank:** `VInt_DrawLevel` processes the buffer after DMA queue drain
- **Overflow protection:** Bounds check before each entry. If buffer full, defer to next frame (one frame of missing edge tiles is preferable to memory corruption)
- **Double-update:** When camera moves >16px/frame, auto-queue two column/row updates
- **Dual plane:** Separate pointer for Plane A + Plane B simultaneous updates

**Teleports are pure coordinate rebases — no plane redraw, no cache work (2026-06-10).** The camera/player shift (±`SECTION_SHIFT` = ±512 tiles) and the slot-map advance (±2 sections = ±512 tiles in `Engine_To_World_Col/Row`) cancel exactly, so every world coordinate — tile cache bounds, fill-resume slots, staging keys, draw trackers — is invariant; plane mapping (`engine & 63`, 512 ≡ 0 mod 64) and scroll values (`camera & $1FF`, 4096 ≡ 0 mod 512) shift by multiples of their modulus. This matches S3K/S.C.E. level wrap, which redraws nothing at the seam (`docs/research/teleport-rebase.md`). Measured before/after: vertical teleport was a 13-frame synchronous freeze (10 in `TileCache_Reinit`'s FillAll + 3 in `Section_RedrawPlanes`), now 0 frames. What remains on the teleport frame: position shifts, slot-map update, `EntityWindow_TeleportShift(Y)`, parallax snap, guard/preload flags.

**`Section_RedrawPlanes` (§4.2) is now the level-init draw and cache-recovery path only** (triggered by `Section_Plane_Dirty`, set at init and by `TileCache_Reinit`). Full 4096-byte BG nametable + 64-column Plane A written synchronously via direct VDP pokes with interrupts masked (`move.w #$2700, sr` — VBlank's `VInt_DrawLevel` changes the autoincrement register from $80 to $02, which would corrupt remaining column writes mid-loop). `TileCache_Reinit` (~10 frames synchronous) is likewise recovery-only and currently uncalled.

**Anti-oscillation teleport guard.** `SECTION_SHIFT = $1000` (exact slot width) means a FWD teleport from threshold $1200 lands exactly on the BWD threshold $0200 (and vice versa). `Section_Teleport_Guard` is a position-based flag (not a timer): set on teleport, cleared only when the player moves off both thresholds. Zero dead zone — moving 1 pixel clears the guard, allowing immediate re-teleport on return. Matches sonic_hack's landing-flag pattern.

### 4.5 Camera System (from S.C.E. ExtendedCamera, enhanced)

Port S.C.E.'s `ExtendedCamera` with lookahead panning, then extend with novel features:

**Per-section camera lookahead (NOVEL):** S.C.E. hardcodes ±64px. Our `sec_camera_lookahead` byte makes this per-section: wide-open jungle = 96px, tight cave = 32px, vertical shaft = 0px (vertical-only tracking). The camera reads the current section's value rather than a constant.

**Velocity-adaptive deadzone (NOVEL):** `deadzone_width = base_deadzone + (abs(x_vel) >> shift_factor)`. At high speed, the deadzone widens to show more of what's ahead. At walking speed, tight tracking. No Genesis game adapts the camera deadzone to speed.

**Player-state-dependent speed caps (from S.C.E.):** Different Y-scroll behavior based on player state: ±$20 pixel deadzone at $18 pixels/frame when airborne (prevents jitter during jumps), strict following at $06 pixels/frame on ground (tight tracking), forced positions for cutscene moments.

**Position history buffer (from S.C.E.):** `Pos_table` stores last N frames of player X/Y position. Camera can lag N frames behind via `H_scroll_frame_offset`. Enables whip-effect camera follow at high speed, smooth camera recovery after section teleport.

**Additional enhancements:**
- Velocity-proportional vertical tracking (faster player = faster vertical camera)
- Section streaming integration: camera bounds adjusted for preview zones
- Dead zone persists for smooth centering

**Preview-aware clamp toggle (§4.2):** `camera_min_x` and `camera_max_x` are dynamically extended by `PREVIEW_PIXELS` (= 192px = 24 tile cols) unless the current pair is at an act boundary:
- `camera_min_x = $0200` when `Slot_Section_Map[0] = 0` (first pair — no BWD neighbour). Otherwise `$0200 - PREVIEW_PIXELS`, allowing camera to scroll into BWD preview zone.
- `camera_max_x = Act_cam_max_x` when slot 1 sec_x + 1 ≥ `Act_grid_w` (last pair — no FWD neighbour). Otherwise `Act_cam_max_x + PREVIEW_PIXELS`, allowing camera to scroll into FWD preview zone.
- Mirrors apply on the Y axis once vertical streaming is implemented.

### 4.6 Multi-Band Computed Parallax — As Shipped

**Foundation:** S.C.E.'s `HScroll_Deform` deformation script extended with TF4's per-band model. Replaces per-zone hardcoded scroll routines with a data-driven system that auto-selects mode per section, supports per-band gradients, and lerps smoothly across section boundaries.

**Multiply-free shift-add factor encoding.** Each band has a `factor_a` (FG) and `factor_b` (BG) packed into 24 bits: `s1` (4 bits, 0..14 = shift; 15 = "term zero"), `s2` (4 bits, same semantics), `op` (1 bit: 0 = ADD second term, 1 = SUB). Scroll = `(camX >> s1) op (camX >> s2)` per term — pure shift+add, no `muls`. Pre-defined factors: `FACTOR_0` (locked), `FACTOR_1`, `FACTOR_1_2`, `FACTOR_1_4`, `FACTOR_1_8`, `FACTOR_1_16`, `FACTOR_3_4`, `FACTOR_3_8`, `FACTOR_3_16`, `FACTOR_5_8`, `FACTOR_5_16`, `FACTOR_7_8`, `FACTOR_7_16`, `FACTOR_15_16`. New factors added by composing two shifts.

**Per-band Plane A + Plane B factor split.** Each band carries independent FG and BG factors. Plane A's "ground" band typically uses `FACTOR_1` (1:1 with camera); Plane B layers progressively slower (`FACTOR_1_4` mountains, `FACTOR_1_8` clouds). Gives each Y-region its own scroll rate.

**Per-band amplitude shift + phase offset.** `BAND_DSA` / `BAND_DSB` (per-band shift on FG/BG deform sample, set before each `band` macro call) downscale the deform amplitude per band — clouds full-amplitude, hills faint, ground none. Sentinel value `15` skips the sample entirely. `BAND_PHASE` desyncs each band's wave from neighbours so they don't pulse in lockstep.

**FG / BG H-deformation tables (256-byte signed sine/triangle/custom, sampled per line).** When `pcfg_deform_table_fg` and/or `pcfg_deform_table_bg` are non-NULL, the pipeline auto-selects per-line HScroll mode and samples the table at `(phase + band_phase + line) & $FF` per scanline, downscaled by the band's shift, added to the band's base scroll. Phase advances by `pcfg_deform_speed_fg/bg` per frame. Generators in `engine/parallax_macros.inc`: `deform_table_sine`, `deform_table_triangle`, `v_column_perspective`.

**Vertical parallax (whole-plane and per-column).** Whole-plane: `pcfg_v_factor_bg` shift + `pcfg_v_center_y` + `pcfg_v_offset` produce `target_b = ((camY - vCenter) >> v_factor_bg) + vOffset`, lerped each frame. Sentinel `v_factor_bg = 15` locks BG vscroll to `vOffset` (camera-Y-independent). Per-column: when `pcfg_v_deform_table_bg` is non-NULL, mode bit 2 enables per-column VSRAM; the pipeline samples 20 column-pairs from the table each frame, shift-scaled by `pcfg_v_deform_shift_bg`, animated by `pcfg_v_deform_speed_bg`.

**Section transition smoothing (16-frame lerp) — plane B only.** `Parallax_StartTransition` stages `Parallax_Target_Config` and sets `Parallax_Transition_Frames = 16` when entering a new section's config. `Parallax_Update` uses Target_Config to compute band targets; the per-band scroll lerp (`>>4`) eases the **plane B** values toward them only while `Transition_Frames > 0` — outside transitions every band locks exactly to its decoded target. **Plane A is never lerped under any circumstance** (fixed 2026-06-10): the FG streaming engine draws columns in a camera-anchored 64-col wrap window, so any FG scroll offset from the camera drags the plane-wrap seam into view at the screen edge. The original always-on lerp trailed the camera by ~15 × velocity (≈240 px at 16 px/frame), painting "content from 512 px ahead" over the visible left edge during rightward scroll. `pcfg_transition = 1` overrides smooth → instant snap (additionally sets `Parallax_Snap_Pending` so plane B values jump to targets without lerp). `Parallax_Snap_Pending` is also set automatically on section teleport (`Section_TeleportFwd/Bwd`) — Camera_X just jumped `SECTION_SHIFT` pixels, no lerp can reasonably catch up.

**Per-cell vs per-line auto-mode.** `Parallax_Update` checks both H-deform tables. Both NULL → per-cell HScroll (28 entries × 4 bytes = 112-byte DMA), no per-line wave possible. Either non-NULL → per-line HScroll (224 entries × 4 bytes = 896-byte DMA). VDP register `$0B` mode bit set accordingly via shadow + dirty flag during `Parallax_StartTransition`.

**Layer enable mask.** `pcfg_layer_mask` disables individual bands; a disabled band's **BG** scroll inherits the previous band's value (or zero if first band, = locked). The **FG** word of a disabled band stays hard-locked to -Camera_X — the inheritance seed is -camX, never zero — because the FG streaming engine draws a camera-anchored 64-col window and any FG scroll offset drags the plane-wrap seam into view (bug found 2026-06-11: zero-seeded FG froze Plane A's top 32 lines under LockedClouds). `LAYER_MASK = $1E` locks the cloud band while mountains/hills/ground continue scrolling.

**RAM footprint:** `Parallax_State` ≈ 126 B in `$FF000000`-range RAM:
- `Parallax_Deform_Phase_FG/BG/V_BG` (3 × ds.w 1 = 6 B)
- `Parallax_Current_Scroll_A/B[8 bands]` (2 × 16 = 32 B)
- `Parallax_Current_Vscroll_BG` (2 B)
- `Parallax_Current_Config / Target_Config` (8 B pointers)
- `Parallax_Transition_Frames / Snap_Pending` (2 B)
- `Parallax_Vscroll_Column_Buf` (80 B for 20 VSRAM column-pairs)

**ROM cost per section:** 28-byte `parallax_config` header + 10-byte `band_entry` per band. 5-band default = 78 B per section. Deform tables (256 B each) are shared across sections that use the same wave shape.

**Effects library at `data/parallax/effects/`:** reusable single-effect building blocks. `shimmer.asm` (subtle H-wobble, plane-agnostic), `haze.asm` (graduated H-wobble — heaviest at bottom, plane-agnostic with optional uniform mode), `rocking.asm` (per-column V-scroll rocking). Each file exposes a parameterised `<effect>_config` macro plus pre-named `_Slow / default / _Fast` variants.

**Composite scenes at `data/parallax/scenes/`:** hand-authored configs that mix multiple effects with custom per-band gradients. `windy_haze.asm` (windy gradient BG + uniform FG haze), `sky_haze.asm` (split-screen via `parallax_combine_split` — windy top, haze bottom), `caves.asm` (slow BG factor gradient), `locked_clouds.asm` (layer-mask demo).

**Composition macros in `parallax_macros.inc`:**
- `parallax_section` — workhorse, emits a complete config record from named keyword params.
- `parallax_combine` — sugar for stacking up to three deform tables (FG H, BG H, BG per-column V) in one single-band config.
- `parallax_combine_split` — 2-band variant with `PARALLAX_TOP / PARALLAX_BOTTOM / PARALLAX_ALL` bitmask `*Where` params for regional effect placement.

**Performance:** ~410 NTSC cycles per frame for 5-band per-cell pure shift-add (no deform sampling). Per-line mode adds ~2× (~800 cycles for 224-line fill with deform sampling). Cheaper than processing two objects.

**Foundation:** S.C.E.'s `HScroll_Deform` deformation script, extended with shift-add factor encoding (novel), per-band amplitude/phase split (novel), and section-boundary lerp transitions (novel).

### 4.7 Level Collision — Block-Embedded Collision + 2D Tile Cache

**Collision is embedded in block data.** Each 16×16 block in the tile cache carries its collision type alongside its 2×2 nametable words. The 2D tile cache stores nametable and collision data in separate parallel arrays (80 cols × 60 rows), enabling direct indexed access to either layer.

**2D Tile Cache:** The tile cache is an 80-column × 60-row linear array in RAM, covering the viewport plus margins (20 columns each side, 16 rows above/below). Two parallel arrays:
- **Nametable array** (80 × 60 × 2 bytes = 9,600 bytes): VDP nametable words, one per 8×8 tile
- **Collision array** (2 planes × 80 × 30 × 1 byte = 4,800 bytes): collision type bytes, one per 16px cell per layer (loop path A at +0, path B at +TILE_CACHE_COLL_SIZE; objects select via `SST_layer`)

The linear layout enables direct 2D indexing: `cache[col + row * 80]` with both axes circular. Columns slide via `Cache_Origin_Col`, rows via `Cache_Origin_Row` (added 2026-06-10 — replaced the `TileCache_VSlide`/`VSlideUp` memmoves, which cost ~87k cycles per 2-row evict and lagged hard under sustained vertical scroll). Eviction in both axes is O(1) origin arithmetic; the recycled physical rows are overwritten by `TileCache_FillRow` before they can become visible, same validity contract the memmove had. Physical position = `(logical + origin) mod size`. Consumers that walk rows down a column (`TileCache_CopyBlockColumn`, `Draw_TileColumn`, `Section_RedrawPlanes`) carry an end-of-buffer sentinel in an address register and subtract the buffer size on crossing (~16 cycles per row walked); single-row consumers (`Tile_Cache_GetTile`/`GetCollision`, `TileCache_FillRow`, `Draw_TileRow_FromCache`) just remap the row index. **`Cache_Top_Row` and `Cache_Origin_Row` are always even**: init/reinit round down, vertical eviction and upward extension step by 2 tile rows. This keeps 16px collision cells aligned with world block data — and makes `physical_row / 2` exactly the physical collision row, so the collision array shares the same origin. An odd top row would skew every collision lookup by half a cell.

**Cache fill (as shipped, 2026-06-10):**
- **Block staging cache:** decompressed 16×16-tile blocks land in a 12-slot staging cache (`Block_Stage_Buffers`, 768 bytes/slot — 512 nametable + 2×128 collision planes (path A/B, added 2026-06-10), keyed by packed sec_x|sec_y|block_index, round-robin evict). Column fills cross 4–5 blocks vertically and row fills cross 6 horizontally; without staging, each block would be re-decompressed up to 16 times as the cache slides across it (~94% redundant work). 12 slots let a column fill and a row fill coexist on diagonal scroll.
- **Per-frame decompress budget:** `TileCache_FillColumn` AND `TileCache_FillRow` draw from a shared frame allowance (`BLOCK_DECOMP_BUDGET` = 6 blocks, reset in `Tile_Cache_Fill`). Steady-state horizontal scroll costs ~0.3 decompresses per column (staging absorbs the rest); a cold block-column burst (≤5) fits in one frame's budget. Rows additionally cap at `VFILL_ROWS_PER_FRAME` = 2 per frame with their own partial-resume (`Cache_Fill_RowResume_Row/Col`), and leftover budget prefetches one block of the next block-row in the scroll direction. **The vertical contract is structural:** `Camera_Update` clamps Y movement to `CAM_MAX_Y_STEP` = 16 px/frame (S2's number — S3K uses 24) so the fill can never fall behind; the binding constraint is the VBLANK window, not CPU: each filled row adds a 64-word plane-buffer entry to the VBlank drain, and >2 rows/frame overflows VBlank into FIFO-throttled active display (measured 2026-06-10: 4 rows/frame cost +15 lag frames per 512px descent; 2 rows/frame costs +4).
- **Keyed partial resume:** a budget-out stores `Cache_Fill_Resume_Col/Row`; the next frame finishes that exact column before extending either edge. Both edges commit their bound *before* filling, so at most one partial is ever outstanding and a budget-out simply ends column work for the frame.
- **FillRow copies collision too:** the odd row of each 16px cell (cell-completing row, well-defined because Top is even) writes the cell's collision byte alongside the nametable words.

**Runtime collision lookup** reads directly from the tile cache — no separate collision maps, no per-section decompression, no slot rotation at teleport. The tile cache already has the data:
```asm
; Collision lookup from tile cache
; d0.w = engine X pixels, d1.w = Y pixels
    lsr.w   #4, d0                      ; X pixels → tile col (16px cells)
    lsr.w   #4, d1                      ; Y pixels → tile row (16px cells)
    bsr.w   Tile_Cache_GetCollision     ; d0.b = collision type byte
```

**Collision type byte:** Indexes into height maps and angle arrays. The byte IS the collision ID — no further indirection. Embedded in the block data by the build tool (S.C.E./S3K-style: collision is a property of placement, not a separate data structure).

**Floor distance formula** (S.C.E. convention): `distance = 16 - height - sub_cell_Y`, where `sub_cell_Y = Y_pixels & $F` and `height` is the height map value (0-16) at `(collision_type × 16) + (X_pixels & $F)`. Negative distance = embedded in solid (snap up), zero = on surface, positive = gap below foot.

**Dual-sensor system** (unchanged from S.C.E./S3K):
- **Two floor sensors** (left/right foot) positioned at `x_pos ± width_pixels/2, y_pos + height_pixels/2`
- **Height maps** in ROM: `HeightMaps` (vertical collision) + `HeightMapsRot` (wall sensors)
- **Angle arrays:** Pre-computed terrain angles indexed by collision ID
- **Height map indexing:** `(collision_type × 16) + (x_pixel & 0xF)` — single-cycle lookup

**Build tool embeds collision in blocks:** The build tool generates 16×16 blocks with nametable words and collision bytes derived from tile placement. Currently uses VDP priority bit (bit 15) to distinguish ground (priority=1 → type 1, solid) from sky (priority=0 → type 0, air). Future: proper tile→collision LUT for slopes and varied terrain types.

**Why embedded over separate maps:** S.C.E./S3K embed collision indices directly in their block mapping words. Our block format adapts this by storing collision bytes alongside nametable words in the tile cache. Benefits: no separate per-section collision files, no collision map RAM slots, no collision decompression at init/preload/teleport, collision is inherently tied to position (same visual tile can have different collision in different placements). The collision array adds ~4.8 KB RAM but eliminates all runtime collision map management.

### 4.8 Section Streaming Integration

The section system touches nearly every other engine system. These cascades are defined as integration points:

**Section + DMA Queue:**
- `Section_PreloadArt` queues S4LZ streams into the Priority 2 (deferrable) queue
- **Two-tier priority:** object art → Priority 1 (important, immediate), background tiles → Priority 2 (deferrable, spread over frames)
- Art streaming starts ~85 frames before teleport — multiple frames to spread the work
- The 32-slot DMA queue absorbs section preload alongside normal per-frame transfers
- **Preload abort:** If player reverses direction, cancel current S4LZ stream (reset bookmark) and start new direction's preload

**Section + VRAM Allocator (2.2):**
- On section preload, `AllocVRAM` pre-allocates art for incoming objects
- On section exit, `FreeVRAM` decrements refcounts — art stays cached for backtracking
- Pool compaction only runs at section boundaries

**Camera-Driven Entity Window (4.9):**
- Objects and rings load when their section loads into a slot — not viewport-based
- Objects spawn via `AllocSlot` (3.2) with coordinates from compact 4-byte entries
- Per-section type table maps 5-bit indices to routine pointers (128-byte RAM lookup)
- On preload, entities spawn at warped coordinates (+SECTION_SHIFT) for seamless preview
- On teleport, uniform -SECTION_SHIFT applied to all positions — no rebuild needed
- Art pre-allocation via `AllocVRAM` (2.2) still applies: section preload allocates art before objects spawn

**Section + Parallax (4.6):**
- Each section's `sec_parallax_config` pointer loads a new parallax config on teleport
- Different sections in the same zone can have different parallax (outdoor → cave → underwater)
- Layer enable mask disables unused layers per section (saves cycles + DMA)
- Parallax transition smoothing interpolates scroll factors over 8-16 frames at boundaries

**Animated Terrain Per-Section (NOVEL):**
Each section can define its own animated tile set via `sec_anim_blocks` — conveyor belts, pulsing lava, swaying grass, shimmering ice. Animation system cycles frames and DMAs current tiles via the DMA queue (Priority 1). On teleport, old tiles stop, new tiles start. Each section becomes visually distinct not just in static art but in dynamic terrain behavior.

**Section State Preservation via Sliding Window:**
The sliding window teleport preserves entity state for the surviving slot naturally — the ring bitmask and object positions carry over with coordinate adjustment. Collected rings stay collected, destroyed objects stay gone, as long as the section remains in one of the two active slots. Once a section leaves both slots (player has moved ≥2 sections away), its entities reset to ROM defaults on next load — matching classic Sonic behavior where distant areas respawn.

**Zero-Lag Teleport — Progressive Preload + Crossfade Masking (NOVEL):**

A naive teleport does all work in a single frame: layout conversion, ring/object rebuild, full-screen nametable DMA. This engine distributes that work across systems so the teleport frame itself is near-free:

| System | Work it handles | Cycles on teleport frame |
|---|---|---|
| Camera-driven entities (4.9) | EntityWindow_TeleportShift: shift/despawn + rebuild scan state | ~200 (shift + scan) |
| Block-based cache data (4.3) | Layout data ready in tile cache | ~0 (pointer swap) |
| Progressive preload (below) | Nametable already in VDP | ~0 |

What remains on the teleport frame: position shifts (~800 cycles), pointer updates (~100 cycles), ring origin warp (~20 cycles), palette (~200 cycles). Total: **~1,500 cycles** — 1% of the frame budget.

The remaining problem is the nametable DMA: the VDP still has old nametable tiles, and the full visible area (~2,240 bytes Plane A + Plane B) needs updating from ROM. Two techniques eliminate this as a visual hitch:

**1. Progressive nametable preload during the preload window:**

The preload phase runs ~85 frames before the teleport. During this window, the preloaded slot's nametable data is DMA'd to VDP progressively at 1-2 columns per frame as Priority 2 (deferrable) entries:

```
; During preload phase (each frame):
preload_col = preload_col + 1
if preload_col < SECTION_WIDTH
    DMA pre-computed cache data for column preload_col → VDP nametable
    (Priority 2: skipped on lag frames, no impact on gameplay)
```

At 2 columns/frame, 16 columns (one section width) complete in 8 frames. The preload window is 85 frames — more than enough time, even with lag frames causing Priority 2 skips. By teleport time, the preloaded slot's nametable data is already in the VDP. Only the other slot needs immediate DMA on the teleport frame — ~1,120 bytes, fits trivially in a single VBlank alongside palette and sprite table transfers.

The nametable entries are written to the off-screen columns of the VDP plane (the toroidal nametable has 64 columns but only 40 are visible). The preloaded cache data writes to columns that will become visible after the teleport's position shift. Before the teleport, these columns are off-screen — no visual artifact.

**2. Palette crossfade to mask the remaining half-screen update:**

Even with half the screen preloaded, the other slot's nametable update takes 1 frame. During that frame, a few columns might show stale tiles. A 3-4 frame palette crossfade (darken → teleport → brighten) masks this entirely:

```
Frame -2: Begin palette darken (50% brightness)
Frame -1: Full dark (palette all $000 or near-black)
Frame  0: TELEPORT — position shift, nametable DMA (invisible behind dark palette)
Frame  1: Begin brighten (50% brightness)
Frame  2: Full brightness, new palette applied
```

This serves double duty: it masks the nametable transition AND provides a natural visual cue for the section boundary (especially useful when sections have different palettes). The fade is ~200 cycles/frame (palette lerp), negligible. The darkening starts 2 frames before the teleport, triggered by proximity to the teleport boundary.

For sections with the same palette, the fade can be shortened to 2 frames total (darken on teleport frame, brighten next frame) or skipped entirely if the progressive nametable preload covers the full screen.

**3. Preview is streaming-integrated (implemented §4.2):**

Preview columns are no longer separate copy operations. The linear-buffer streaming engine (`Section_UpdateColumns`) extends its range by `PREVIEW_COLS` into neighbor section data at each boundary. Neighbor data pointers are cached at teleport/init (`Section_Fwd/Bwd_Neighbor_Data`). Preview content appears naturally as the streaming cursor advances past the section boundary — no teleport-frame layout work, no separate preview pass. The teleport frame does only position math, slot-map update, entity-window shift, and the parallax snap — no dirty-flag, no redraw (§4.4 pure rebase, 2026-06-10).

**Result:** The teleport becomes ~1,500 cycles of CPU work (position math) + zero visual glitch (nametable already in VDP + palette crossfade masks any residual). No Genesis game achieves zero-lag section streaming with full section independence (different art, palette, parallax, entities). This is the combination of 6 systems working together: block-based cache data (4.3), camera-driven entity window (4.9), progressive preload, palette crossfade, DMA priority queue (1.1), and velocity-based timing.

**Transition / Blend Sections (NOVEL):**
Transition cells in the grid interpolate between adjacent sections' palettes, parallax, and physics over the cell's width. Jungle gradually darkens into cave, water tint deepens as you descend, wind picks up as you climb. Creates seamless geographic flow instead of hard boundaries.

**Streaming During Cutscenes (NOVEL):**
During boss deaths, story sequences, or triggered animations, the DMA queue has spare capacity (no scrolling). The engine preloads the next section's art via S4LZ streaming as Priority 2. By cutscene end, art is already in VRAM — transition is instant.

**Velocity-Based Preload Timing (NOVEL):**
Factor player velocity into the preload trigger:
```
preload_at = threshold - (x_vel × lead_frames)
```
A player at max speed (~$C00 subpixels/frame) gets the preload trigger ~96 pixels earlier = 8 extra frames for S4LZ to decompress. A walking player barely changes. Ensures smooth transitions regardless of speed. No game does adaptive preload timing.

### 4.9 Camera-Driven Entity Management

Entities (rings and objects) load when they scroll into camera range and despawn when they leave. This replaces the earlier teleport-triggered bulk loading. Per-section X-sorted ROM lists with per-section scan pointers enable early-exit scanning — only entities near the camera edge are checked each frame.

**Why separate rings from objects:** Rings are high-volume (40-50 per section), stateless (no behavior code), and need only collision + rendering. Objects are lower-volume (10-20), stateful (SST slots with behavior routines), and diverse. Segregated pools with type-specific fast paths outperform unified processing.

#### 4.9.1 Ring Layout — Flat X-Sorted, Section-Local

Ring data in ROM per-section, flat `dc.w X, dc.w Y` pairs in section-local coordinates, X-sorted ascending, terminated by `dc.l 0`:

```
OJZ_Sec0_Rings:
    dc.w    $080, $060      ; ring 0
    dc.w    $090, $060      ; ring 1
    dc.w    $0A0, $060      ; ring 2
    dc.l    0               ; terminator
```

No pattern encoding — rings are pre-expanded at build time. Flat lists eliminate per-frame decode overhead and enable binary/linear scanning with early exit. The X-sorted order means once a ring's engine-space X exceeds the camera's load edge, all subsequent entries are also out of range.

#### 4.9.2 Object Layout — 6-Byte v2 Entries with Per-Section Type Table

Object entries in ROM use full-resolution section-local coordinates with a local type index, X-sorted ascending, terminated by `dc.w -1`:

```
; 6-byte entry: dc.w x, y, flags|type|subtype
;   x.w, y.w:  section-local ($000-$7FF; X bit 15 reserved as terminator)
;   word 3:    bit 15 = OEF_ANY_Y (spawn regardless of camera Y — phase 2)
;              bit 14 = OEF_YFLIP, bit 13 = OEF_XFLIP (rol.w #4 → RF bits in Load_Object)
;              bits 12-8 = type (0-31, OEF_TYPE_SHIFT/OEF_TYPE_MASK)
;              bits 7-0  = subtype (OEF_SUBTYPE_MASK)
```

Hand-authored lists use the `objentry`/`objend` macros (macros.asm), which build-fail on non-monotonic X, out-of-range coordinates, type/subtype overflow, and lists exceeding `MAX_LIST_ENTRIES` (128 — the killed-bitmask capacity):

```
OJZ_Sec2_Objects:
    objentry $100, $0B0, 1      ; x, y, type [, subtype] [, oflags]
    objentry $300, $060, 0
    objend                      ; emits dc.w -1 terminator, resets guards
```

Each section defines a count-prefixed type table in ROM:

```
OJZ_Sec0_TypeTable:
    dc.b    2, 0                ; count, pad byte
    dc.l    ObjDef_Static       ; type 0
    dc.l    ObjDef_Solid        ; type 1
```

Object spawning reads the 6-byte entry, indexes the ROM type table for the ObjDef pointer (one indexed `move.l`), and passes the flags/type/subtype word to `Load_Object`, which patches subtype and rotates the flip bits into render_flags/status. The 5-bit type index means each section independently uses up to 32 object types with no global ID space.

**`OEF_ANY_Y` semantics (shipped with the vertical window):** an ANY_Y object spawns whenever the camera's X window reaches it, regardless of camera Y, and is exempt from Y despawn (X despawn and section-tracking despawn still apply — when its section leaves the 2×2 window the object goes with it, and respawns when the section is re-tracked). The flag persists past spawn time as **bit 7 of `SST_slot_tag`** (low bits = entry index 0-3): the per-frame Y despawner tests that bit instead of re-reading ROM. Use it for vertical-corridor hazards, elevators, and anything whose behavior spans a section's full height.

#### 4.9.3 Entity Window — 2×2 Quadrant Camera-Driven Lifecycle

The entity window tracks the **2×2 section quadrant** around the camera: both slot columns (L/R from `Slot_Section_Map`) × two section rows (`sec_y` and `sec_y+1`). `EntityWindow_BuildEntries` derives the four entries purely from `Slot_Section_Map` + the act grid — entry 0 = slot L row r, entry 1 = slot R row r, entry 2 = slot L row r+1, entry 3 = slot R row r+1. Each entry gets an `EntityScanState` ($1A bytes):

```
EntityScanState struct ($1A bytes):
    ess_ring_right_idx   ds.w 1      ; next unloaded ring index (right scan)
    ess_ring_left_idx    ds.w 1      ; next unloaded ring index (left scan)
    ess_obj_right_idx    ds.w 1      ; next unloaded object index (right scan)
    ess_obj_left_idx     ds.w 1      ; next unloaded object index (left scan)
    ess_rom_ring_ptr     ds.l 1      ; pointer to section's ROM ring list
    ess_rom_obj_ptr      ds.l 1      ; pointer to section's ROM object list
    ess_rom_type_tbl_ptr ds.l 1      ; pointer to section's ROM type table
    ess_origin_x         ds.w 1      ; section's engine-space X origin
    ess_section_id       ds.b 1      ; section flat grid id, or SEC_VOID
    ess_entry_idx        ds.b 1      ; entry index 0-3 (loaded-mask base derives from it)
    ess_origin_y         ds.w 1      ; section's engine-space Y origin (per-entry — rows differ)
```

**Validity mask + SEC_VOID:** entries whose section falls outside the act grid (right edge on odd-width grids, bottom rows when `sec_y+1 ≥ grid_h`) are stamped `ess_section_id = SEC_VOID` ($FF) and their bit cleared in `Entity_Window_Active` (bit n = entry n valid). The void stamp is load-bearing: despawn paths read entry ids unconditionally, and a stale id would keep dead-section survivors alive forever. All scan/populate loops skip inactive entries.

**Per-frame scan (`EntityWindow_Scan`):**

```
For each ACTIVE entry (Entity_Window_Active bit set):
  1. ScanRingsRight/Left: advance ring indices through X-sorted ROM list
     - Convert section-local X/Y to engine space (add ess_origin_x/y)
     - If engine X > camera right load edge: stop (X-sorted early exit)
     - Skip if outside the camera Y band (below)
     - Check Collected_CheckRing bitmask: skip if already collected
     - Check + set the entry's loaded-ring bit: skip if already loaded
     - Add to unified Ring_Buffer via RingBuffer_Add
  2. ScanObjectsRight/Left: same shape for 6-byte object entries
     - OEF_ANY_Y entries bypass the Y band test
     - Check + set loaded-object bit; Load_Object; tag SST_slot_tag with
       entry index (bit 7 = ANY_Y mirror)

Vertical re-scan (EntityWindow_RescanY): when camY & ENTITY_RESCAN_COARSE_MASK
  changes (one 128px coarse row crossed), re-walk each active entry's ROM lists
  from index 0 up to the X ratchet (right_idx), spawning entries that the new
  Y band now covers. Loaded bits make this idempotent — already-loaded
  entities are one btst+skip.

After all entries:
  3. DespawnRings: backward iterate Ring_Buffer, remove entries outside the
     X keep range OR the Y despawn band; clear the loaded-ring bit
     (clearLoadedRing) before swap-with-last removal
  4. DespawnObjects: scan Dynamic_Slots, delete tagged objects outside range
     (ANY_Y objects exempt from the Y test); clear loaded-object bit
     (clearLoadedObj) before DeleteObject
```

**Y band + hysteresis:** entities load inside `[camY − ENTITY_LOAD_BUFFER_Y, camY + SCREEN_HEIGHT + ENTITY_LOAD_BUFFER_Y]` ($100) and despawn outside `[camY − ENTITY_DESPAWN_BUFFER_Y, camY + SCREEN_HEIGHT + ENTITY_DESPAWN_BUFFER_Y]` ($180). This mirrors the X hysteresis (load $180 / despawn $200 past the screen edge): the gap prevents load/despawn oscillation at band edges. Two build-time guards in constants.asm enforce the band invariants:

```
(ENTITY_DESPAWN_BUFFER_Y - ENTITY_LOAD_BUFFER_Y) >= coarse row size (128)
    ; else hysteresis < re-scan granularity -> edge oscillation returns
ENTITY_LOAD_BUFFER_Y >= coarse row size (128)
    ; else a re-scan fired up to 127px ago can leave a gap inside the
    ;   nominal band -> vertical re-scan can skip entities
```

(Consequence of the coarse trigger: the *guaranteed* load margin is `ENTITY_LOAD_BUFFER_Y − 128` past the screen edge, since the last re-scan may have fired up to one coarse row away. Verified on hardware: a ring 240px above the camera stays unloaded until the next crossing — by design.)

**Loaded bitmasks (idempotent spawns):** `Entity_Loaded_Masks` holds 4 entries × 32 bytes (16B ring bits + 16B object bits, indexed by ROM list position). A bit is set at spawn and cleared at despawn. This is what makes every overlapping spawn path safe to re-run: the vertical re-scan, the teleport-rebuild populate, and the left/right X scans can all visit the same ROM entry without double-spawning — the mechanism that originally fixed the §4.9 duplicate-spawn bug now generalizes to every path. `EntityWindow_InitSection` compare-clears an entry's mask slot only when its `section_id` changes, so an unchanged section keeps its bits across rebuilds.

**Vertical re-scan cost shape:** O(entities already passed by the X ratchet) per 128px camY crossing, across the ≤4 active entries — each candidate is a band compare + btst when already loaded. Trivial on test fixtures; unbudgeted on dense production levels (see DEFERRED_WORK "RescanY burst is unbudgeted").

#### 4.9.4 Unified Ring Buffer

A single 128-entry ring buffer replaces the old dual per-slot buffers. Each entry is 6 bytes:

```
Ring_Buffer entry (6 bytes):
    dc.w    engine_X        ; +0: engine-space X
    dc.w    engine_Y        ; +2: engine-space Y
    dc.b    section_id      ; +4: which section owns this ring
    dc.b    list_index      ; +5: index into section's ROM ring list
```

**Operations:**
- `RingBuffer_Add`: append to end of buffer, increment Ring_Count. Carry set if full.
- `RingBuffer_Remove`: swap target entry with last entry, decrement Ring_Count. O(1).
- `DrawRings`: single-pass iteration over Ring_Count entries, 6-byte stride.
- `RingCollision`: backward iteration (safe with swap-with-last removal). On collect, calls `Collected_MarkRing` then `RingBuffer_Remove`.

**Diagnostics:** `Ring_HighWater` records the max Ring_Count ever observed (capacity headroom check per level); `Ring_Add_Dropped` counts `RingBuffer_Add` failures and is **DEBUG-fatal** — a dropped ring means the 128-entry buffer is undersized for the level's band density, which must be caught in testing, not shipped. Both reset with `RingBuffer_Clear` at level init.

#### 4.9.5 Rolling Collected Bitmask (3×3 Window)

A 9-slot rolling window tracks ring collection + badnik kill state across section revisits. Each slot is 34 bytes: `[tag.b][pad.b][ring bitmask × 16][killed bitmask × 16]`. Tag = section_id ($00-$FE) or $FF (empty).

```
Ring_Collected_Window: 9 slots × 34 bytes = 306 bytes

Collected_ClaimSlot(section_id): claim empty slot, clear bitmask
Collected_MarkRing(section_id, list_index): set bit in section's bitmask
Collected_CheckRing(section_id, list_index): test bit (Z set = uncollected)
Collected_UpdateCenter(center_id, grid_w): evict slots outside 3×3 grid range
```

The 3×3 window centered on the player's current section means collection state persists for all adjacent sections. Backtracking within ±1 section preserves collected rings. Moving beyond the 3×3 range evicts distant slots, and revisiting those sections later loads them fresh. The 128-bit bitmask per slot supports up to 128 rings per section (build-enforced by `objentry`'s MAX_LIST_ENTRIES cap for object lists).

**Gameplay consequence:** persistence depth is exactly one section of backtrack. A round trip of 2+ sections re-claims evicted slots with fresh bitmasks — collected rings respawn and killed badniks revive. This is the accepted cost of capping the window at 9 slots (162 bytes); classic Sonic behaves the same way for off-screen respawning objects.

#### 4.9.6 Teleport Entity Shift

When a teleport fires, `EntityWindow_TeleportShift(±SECTION_SHIFT)` (X) or `EntityWindow_TeleportShiftY(±SECTION_SHIFT)` (Y) handles the transition:

```
1. Compute keep-range: Camera ± load buffer (X or Y axis)
2. Shift surviving rings: add shift to engine coord, remove (and clear
   loaded bit) if outside keep-range
3. Shift surviving objects: add shift to x_pos/y_pos (16.16), delete (and
   clear loaded bit) if outside range
4. Rebuild EntityScanState entries from the updated Slot_Section_Map
5. Run populate scan to load entities in the new window
```

The uniform SECTION_SHIFT applied to all positions preserves distances between entities. A projectile 50 pixels from the player stays 50 pixels away after the shift.

**Loaded-mask migration is a verified no-op.** The window tracks the 2×2 block `{slotL,slotR} × {sec_y, sec_y+1}`, and `SECTION_SHIFT = 2×SECTION_SIZE`, so every teleport moves that block by exactly TWO sections along one axis (from the verified mapping table, duplicated at both rebuild call sites in entity_window.asm):

```
dir    d4 sign          slot map before -> after
X-FWD  -SECTION_SHIFT   (x,y),(x+1,y) -> (x+2,y),(x+3,y)
                        [edge: slot1 = SEC_VOID when x+3 >= grid_w]
X-BWD  +SECTION_SHIFT   (x,y),(*  ,y) -> (x-2,y),(x-1,y)
                        [same from the FWD-edge state (x,VOID);
                         new slot1 = old slot0 MINUS 1, so the
                         edge "heal" never re-tracks old slot0]
Y-DOWN -SECTION_SHIFT   sec_y += 2 on both slots
Y-UP   +SECTION_SHIFT   sec_y -= 2 on both slots
```

The old and new tracked sets are **disjoint** in all four directions, including every grid-edge case. No section keeps (or regains) an entry, so there are no surviving (section, entry) pairs whose loaded bits could move — there is nothing to migrate. Mask hygiene comes from the rebuild instead: `EntityWindow_InitSection` compare-clears each entry's 32-byte mask slot because every entry's section_id changes. (The flip side — survivor continuity for sections that just left the window — is a known open item; see DEFERRED_WORK "No survivor continuity across teleports".)

#### 4.9.7 RAM Budget

| Component | Size |
|---|---|
| Ring_Buffer (128 entries × 6 bytes) | 768 B |
| Ring_Count + Ring_HighWater + Ring_Add_Dropped + pad | 4 B |
| Entity_Window_Active + Entity_Window_Center_ID | 2 B |
| Entity_Scan_State (4 × $1A bytes) | 104 B |
| Entity_Loaded_Masks (4 × 32 bytes) | 128 B |
| Camera_Y_Coarse_Prev (re-scan trigger baseline) | 2 B |
| Ring_Collected_Window (9 × 34 bytes) | 306 B |
| **Total** | **~1,314 B** |

Comparable to the old dual-buffer system (1,187 B) while supporting far more: camera-driven loading on both axes, 2×2 quadrant tracking, idempotent spawns, kill persistence, unified buffer, and buffer diagnostics.

### 4.10 Cascade Effects

```
Level / World System Cascades:

2D Section Grid (4.1)
  → Camera Y becomes signed word, Y=0 ceiling removed
    → Vertical leapfrog mirrors horizontal exactly
      → Corner preload uses Priority 2 DMA for diagonal section
        → Velocity-based timing (4.8) ensures lead time at all speeds

Pre-Computed Nametable Strips (4.3)
  → Build pipeline converts chunks at build time (Batman-proven)
    → Scroll = DMA strip from ROM to VRAM (zero CPU)
      → Section_BuildRAMLayout becomes pointer setup, not conversion
        → Override table patches dynamic terrain (breakable floors)

Deferred Plane Buffer (4.4)
  → Game loop never touches VDP during active display
    → VDP has uncontested bus → more VBlank time for DMA
      → Enables more aggressive art streaming → smoother section transitions
        → Prerequisite for pre-computed nametable strips (4.3)

8-Layer Parallax (4.6)
  → Per-section layer table via sec_scroll in section definition
    → Deformation tables create animated wave motion from ROM data
      → Layer enable mask disables unused layers per section
        → Parallax transition smoothing blends scroll factors at boundaries
          → Per-section raster command tables enable raster-level visual variety

Section + Allocator Integration (4.8)
  → Section preload pre-allocates art for incoming objects
    → Two-tier priority: object art immediate, background tiles deferrable
      → Load_Object finds art already in VRAM (refcount bump, no decompress)
        → Section exit decrements refcounts, art cached for backtracking
          → Pool compaction at section boundary makes room for new section

Section-Local Entity Management (4.9)
  → Rings: pattern-encoded ROM → expanded to engine-space buffer at section load
    → Flat (X,Y) word pairs — no per-frame coordinate translation
      → Ring collision iterates expanded buffer directly against player position
  → Objects: compact 4-byte entries → Load_Object with per-section type table lookup
    → Slot tag tracks which slot spawned each object
      → Teleport: despawn outgoing slot, shift surviving objects by ±SECTION_SHIFT
        → Ring buffers copied with X adjustment, bitmasks preserved
  → State: rolling buffer deferred — sections load fresh on revisit for now

Zero-Lag Teleport (4.8 — 6 systems converging)
  → Pre-computed strips (4.3): pointer swap, no layout conversion
  → Entity shift (4.9): ±SECTION_SHIFT to surviving positions, despawn+spawn for slot swap
  → Progressive nametable preload: DMA strips to VDP during 85-frame preload window
    → Half screen already in VDP at teleport time, other half fits one VBlank
  → Palette crossfade: 3-4 frame darken/brighten masks residual nametable update
  → DMA priority queue (1.1): critical transfers always drain, preload is deferrable
  → Velocity-based timing (4.8): faster player → earlier preload → more prep time
  → Result: ~1,500 cycles on teleport frame (1% budget), zero visual glitch

Section as Independent World (4.2 + 4.8 + 4.9)
  → Each section defines: layout, art, palette, music, physics, parallax, raster table, deformation, animated tiles, rings, objects, type table
    → Transition sections blend between adjacent worlds smoothly
      → Rolling state preservation deferred — fresh load on revisit for now
        → Streaming during cutscenes eliminates loading pauses
          → Result: interconnected worlds, not level chunks
```

---

## 5. Player / Character System

Three playable characters (Sonic, Tails, Knuckles) with shared physics via `Player_Common.asm`, per-character abilities, and a unified shield system. The key innovations: per-section terrain physics (novel — generalizes underwater physics to any terrain type), configurable physics tables that separate character identity from terrain modifiers, and preserving Sonic's classic flat-acceleration feel while enabling per-character tuning.

### 5.1 6-Button Controller Support

**6-button pad support:** Detect X/Y/Z/Mode buttons via rapid TH cycling protocol (see Section 9.4). Extra buttons provide debug shortcuts in debug builds (frame advance, profiler toggle) without conflicting with gameplay controls. In release builds, X/Y/Z can map to character-specific actions if needed.

### 5.2 Per-Section Terrain Physics (NOVEL)

With the 2D section grid (Section 4.1), different sections can have different physics properties via composable modifier tables:

**Per-character base table:**
```
PhysicsTable_Sonic:
    dc.w  $000C   ; acceleration
    dc.w  $0080   ; deceleration
    dc.w  $0680   ; top_speed
    dc.w  $0038   ; gravity
    dc.w  $0400   ; jump_force
    dc.w  $0020   ; air_drag_rate
```

**Per-section modifier table (applied as multipliers):**
```
SectionPhysics_Lake:
    dc.w  $0080   ; gravity_mult ($100 = 1.0, $80 = half)
    dc.w  $0040   ; friction_mult (low = underwater drift)
    dc.w  $0040   ; air_density (high = strong drag)
```

Section transitions smoothly interpolate modifiers via Lerp so physics don't snap at boundaries. No Genesis game has per-region physics modifiers — Sonic games hardcode underwater as a special case. This generalizes it to any terrain type.

**Used for:** underwater (high drag, low gravity), ice caves (low friction), sandy areas (high friction), sky/space (low gravity, floaty jumps), industrial zones (conveyor effects).

### 5.3 Physics Improvements

**Air drag — apex-only:** Air drag (`x_vel -= x_vel / 32`) applies only during the apex window (`y_vel` between `-$400` and `0`), not during descent. Preserves horizontal momentum through fall arcs. S3K established this as the correct behavior.

**Roll-jump air control:** Air acceleration is allowed when jumping from a rolling state. Roll-jumps are fully responsive — no special-case lockout.

**Per-character acceleration tuning:** Flat acceleration model — same increment every frame regardless of current speed. Core to Sonic's tight, predictable feel. Per-character values via configurable physics tables: Sonic accelerates fastest, Knuckles has most friction. Terrain friction applied from per-section physics data (5.2).

**SWAP-based 16.16 fixed point (from Treasure):** Position uses 32-bit longwords: high word = integer pixels, low word = subpixel fraction. `SWAP d0` moves between integer and fraction halves in 4 cycles, enabling single-register position+subpixel with no separate hi/lo register pairs. Velocity addition is a single `add.l`; pixel position extraction is `swap d0; ext.l d0` or `move.w d0, d1; swap d1` depending on context. Gunstar Heroes and Alien Soldier use this throughout.

**Slope physics refinement:** With dual collision sensors from S.C.E. (Section 4.7):
- Angle continuity checking: reject angle jumps > $20 between frames (prevents loop fallthrough)
- Full vector projection on landing: `inertia = x_vel * cos(angle) + y_vel * sin(angle)` (preserves full momentum on slopes instead of axis-select)
- Unroll wall clip fix: check clearance before height adjustment when exiting rolling
- Steep slope slide: small gravity push when standing still on slopes > ~67°
- Slope factor `muls.w` → `lsl` optimization: saves ~54 cycles/ground frame
- Fix dead spots, ceiling-sticking bug, smooth angle transitions via interpolation

**Spindash charge curve:** Table-based approach (S.C.E. uses 8 entries from $800 to $F00). More tunable than a formula — designers edit a table, not math.

**Landing camera lock:** Don't scroll camera down during jumps until player lands or exits bottom dead zone. Prevents camera bounce on every jump.

### 5.4 Character Architecture

**Shared code in `Player_Common.asm`:** Ground movement, jumping, rolling, slope resistance, roll repel, water handling, speed table selection, and display logic. Character-specific files only contain unique behavior:
- **Sonic:** Instashield, dropdash, spindash, Super Sonic transformation
- **Tails:** Flying physics, CPU AI with 4-state machine (Init, Spawning, Flying, Normal), position history buffer following (reads Sonic's position 16 frames back)
- **Knuckles:** Gliding, climbing, wall detection (needs audit — 220+ unnamed labels from disassembly)

**State entry/exit hooks:** Each player state gets `State_Enter` and `State_Exit` routines. Transition code calls `OldState_Exit` then `NewState_Enter`. Centralizes all state-setup code (height/width changes, animation resets, collision mode) that's currently scattered across 3+ locations per state. Ensures consistency across all 3 characters.

**Hierarchical state machine (evaluate):** Replace 2-bit status + status3 parallel bits with 1-byte `player_state` + 1-byte `player_substate`. Categories: GROUNDED (7 substates), AIRBORNE (5), ROLLING (2), SPECIAL (5). Same dispatch cost, but adding new states (e.g., wall-run, grinding) doesn't require finding free bits.

**Shield system:** Unified per-shield objects (fire, lightning, bubble, wind) with consistent DPLC loading across all characters. Shields integrate with the VRAM allocator — shield art allocated on pickup, freed on loss.

### 5.5 Cascade Effects

```
Player / Character Cascades:

6-Button Controller (5.1)
  → Extra buttons for debug shortcuts (frame advance, profiler toggle)
    → Character-specific actions available via X/Y/Z in release builds

Per-Section Physics (5.2)
  → Section definition includes physics modifier table
    → Section transition interpolates modifiers (Lerp)
      → Water becomes just another section modifier (not hardcoded special case)
        → New terrain types = new modifier table, zero code

Character Architecture (5.4)
  → State entry/exit hooks centralize state setup
    → Hierarchical state machine enables clean new states
      → Player_Common.asm handles all shared movement/collision
        → Physics tables separate character identity from movement code
          → Per-section modifiers compose on top of character tables
            → New character = new ability code + new physics table + new ability states

Physics Polish (5.3)
  → Air drag fix (apex-only) preserves jump momentum
    → Roll-jump air control fix makes roll-jumps responsive
      → Vector projection on landing preserves slope momentum
        → Angle continuity prevents loop fallthrough
          → Landing camera lock eliminates jump bounce
```

---

## 6. Audio System

Full Z80 autonomy via Flamedriver — the 68K has zero sound processing overhead beyond a byte write per command. Audio quality enhanced with techniques stolen from Batman's Zyrinx driver and MegaPCM 2.0, integrated with the section streaming system for dynamic per-section soundscapes.

### 6.1 Flamedriver — Full Z80 Autonomy

**Why Flamedriver over alternatives:**
- **Batman Zyrinx driver:** Excellent quality but runs 16KB of DAC mixing on the 68K — the opposite of what we want
- **Clone Driver v2 + MegaPCM 2.0:** Good community option, but 68K still runs SMPS sequencing every frame
- **Flamedriver:** Everything on Z80. 68K sends `PlayMusic` and never thinks about sound again. Every freed cycle goes to DMA, objects, or section streaming.

S3K SMPS format provides FM3 special mode (effectively 6 FM channels vs 5), better modulation, S3K PSG envelope support. Music composed/converted via SMPS2ASM toolchain.

### 6.2 DAC Enhancements (from MegaPCM 2.0, ported to Flamedriver)

All Z80-side, zero 68K cost:
- **DPCM compression:** Delta-encoded samples use ~50% less ROM. Decode on Z80 during playback.
- **High sample rates:** Up to 32kHz (vs stock 8-11kHz). Noticeably cleaner.
- **Per-sample panning:** Left/Right/Center via YM2612 register $B6. Enables pseudo-stereo.
- **Multi-channel DAC mixing:** Mix 2-4 samples simultaneously on Z80. XGM2 achieves 4 channels at 14kHz; MDSDRV does 2-3 at 17.5kHz with per-channel volume. Budget: 2-3 channels at ~16-23 kHz is the sweet spot between quality and Z80 headroom. 4 channels drops to ~14 kHz and eats 70% of Z80 time with effectively 6-bit output. Per-channel selectable half-speed (6.65kHz) for low-frequency samples (bass drums, ambient rumbles) saves ~50% ROM with no audible quality loss.
- **Independent DAC volume:** Separate from FM/PSG levels.
- **DC offset removal (from Batman):** Subtract pre-computed DC bias per sample before YM2612 output. Eliminates pops/clicks at sample boundaries. One subtraction per sample tick.
- **Pitch-shifted SFX (from Batman):** Step-based pitch control — same ROM sample played at different rates. Jump sound pitched up for mini-hop, down for heavy landing. Saves ROM, adds variety. One multiply per tick when pitch != 1.0.
- **DMA protection buffering (from MegaPCM 2.0):** Buffer ~100+ bytes of upcoming sample data in Z80 RAM during active scan. Play from buffer during VBlank/DMA when Z80 bus is stalled. MegaPCM 2.0 survives up to 24 KB of DMA per frame without audio glitches. Critical for section streaming with heavy DMA loads.

**NOTE:** Hold on finalizing DAC features until MegaPCM 2.1 is available (expected April 2026). 2.1 may introduce custom sample compression or other improvements that change the approach.

### 6.3 Zyrinx Techniques (from Batman & Robin)

**Logarithmic volume curve:** 256-byte lookup table mapping linear volume to perceptually correct attenuation. Human hearing is logarithmic — linear volume steps sound wrong. Zero runtime cost (pure lookup). Single easiest audio quality win.

**Per-algorithm carrier mask:** Volume adjustments via TL must only modify carrier operators (not modulators, which would change timbre). Carrier set varies by algorithm: algo 0-3 = op4 only, algo 4 = ops 2+4, algo 5-6 = ops 2+3+4, algo 7 = all 4. 8-byte lookup table indexed by algorithm gives the carrier bitmask. Essential for the log volume curve to work correctly without distorting instrument patches.

**Verified Z80 bus writes:** Read-back verification on 68K→Z80 command writes: `move.b d0,(a1); cmp.b (a1),d0; bne.b retry`. Prevents silent data loss during bus contention. ~8 extra cycles per verified write.

**Pseudo-stereo DAC:** Alternate YM2612 panning between left/right per DAC tick. Creates wider sound from mono output. One register write per tick on Z80.

**Frequency-based FM panning (NOVEL):** A zero-cost composition convention — pan FM channels by frequency range: FM1 (high melody) → right, FM2 (mid) → center, FM3 (bass) → left, PSG distributed. Creates wider perceived stereo image from FM synthesis alone. No CPU cost, no Z80 cost — purely how music is composed in the S3K SMPS format.

### 6.4 Section-Aware Sound Banking (NOVEL)

Batman uses static per-level sound banks. We make them per-section and dynamic:
- `sec_music` and `sec_sound_bank` in section definitions trigger music changes or sample set swaps
- Different sections use different DAC samples (outdoor → nature, cave → echo/drip, boss → heavy percussion)
- **Music anticipation:** `Section_Preload` pre-loads the next section's sample bank into Z80 DAC buffer before teleport. Zero gap.
- **Music transition types:** Per-section `sec_music_fade_type` controls how music changes:
  - `FADE_CUT` — instant switch (for dramatic moments)
  - `FADE_CROSSFADE` — 30-60 frame crossfade via Z80 volume envelopes (seamless environmental flow)
  - `FADE_STINGER` — transition SFX, then new music (boss entrance style)
- **Conditional bank swaps:** Game state triggers can override section banks — boss spawns → heavy percussion, water entry → echo/reverb samples, speed shoes → higher-energy samples. 68K checks state flags at preload time, selects bank.

No commercial game ties sound banking to level streaming.

### 6.5 Distance-Based Sound Attenuation (NOVEL)

`PlaySoundLocal` currently plays or doesn't play based on on-screen check. Add distance-based volume:
```
volume = max_volume - (distance_to_player × falloff_rate)
```
Objects far from the player are quieter. Log volume table makes attenuation perceptually correct. Cost: one subtraction + one table lookup per `PlaySoundLocal` call.

Enables: distant enemies audible before visible (audio foreshadowing), explosions fading with distance, environmental sounds building as you approach. Gives the game world audio depth that no 2D Genesis game has.

**Priority-based SFX mixing:** When multiple SFX trigger simultaneously, rank by priority (explosion > enemy > pickup > UI). Higher-priority SFX get louder; lower-priority quieter. Combined with distance, creates natural "selective hearing" — a close explosion dominates a distant ring pickup. Cost: ~20 cycles on 68K for ranking, volume adjustment on Z80.

### 6.6 Procedural Ambient Soundscape (NOVEL)

No Genesis game does this. Define an ambient sample pool per section via `sec_ambient_pool`:
- Forest: bird chirps, leaf rustles, distant water
- Cave: water drips, echoes, distant rumbles
- Factory: machinery clanks, steam hisses, electric hums

Z80 firmware includes a LFSR-based random trigger — every 0.5-3 seconds (randomized interval), pick a random sample from the pool, play at low volume. Completely decoupled from main music. ~50 bytes of Z80 code. Each pool entry: `(sample_id, min_interval, max_interval, volume)`.

The game world sounds alive without dedicated ambient tracks. Combined with section-aware banking (6.4) and distance attenuation (6.5), each section becomes a distinct auditory environment.

### 6.7 Continuous SFX (verify in Flamedriver)

S.C.E. supports continuous SFX — sounds that loop while a condition is held (spindash charge, shield buzz, speed shoes whoosh). Separate from normal SFX queue (`v_current_contsfx`), allowing seamless looping without re-triggering every frame. If Flamedriver doesn't support this natively, add a `PlaySoundContinuous` / `StopSoundContinuous` 68K-side API managing a dedicated SFX slot with auto-loop.

### 6.8 Tempo & Timing (from web research)

**YM Timer A for sub-frame tempo:** Use YM2612 Timer A (10-bit, registers $24-$25) as the Z80 driver's tempo timebase instead of VBlank counting. Timer A gives sub-frame precision independent of NTSC/PAL frame rate differences. Polled (not interrupt-driven on Genesis — hardware limitation). This decouples music timing from game frame rate entirely — lag frames become irrelevant to music tempo.

**Bank switch optimization:** The Z80 bank register costs 100+ Z80 cycles per switch (9 serial writes to $6000). This is the #1 Z80 performance threat after DAC mixing. Pack samples contiguously per-section in ROM. Bank-aware sample table skips switch if current bank matches. Build pipeline verifies no sample crosses a 32KB boundary.

**PSG silence on pause:** Z80 writes $9F,$BF,$DF,$FF to $7F on pause command to immediately silence all 4 PSG channels. Without this, tones sustain during pause.

**Channel 3 special mode:** Per-operator frequencies for detuned unison, bell/metallic sounds, inharmonic timbres. Flamedriver already supports this via S3K SMPS — ensure SMPS2ASM workflow documents the capability for composers.

**LFO awareness:** Hardware LFO has only 8 fixed global rates (3.82-72.2 Hz) affecting all enabled channels uniformly. For per-channel vibrato, software modulation (direct F-Number manipulation) is required and already handled by SMPS modulation envelopes. Reserve hardware LFO for global tremolo/vibrato where uniform rate is acceptable.

**SSG-EG envelope modes (YM2612 registers $90-$9F):** Vestigial SSG envelope generator modes that loop the ADSR envelope in configurable shapes — sawtooth, triangle, inverted sawtooth, and combinations. Creates evolving, pulsing FM tones impossible with standard one-shot ADSR envelopes. Almost no commercial game used these (Olympic Gold is a rare exception). Furnace tracker exposes all SSG-EG modes. Useful for: alarm tones, energy fields, textural pads, pulsing ambient sound design. Zero Z80 cost — entirely YM2612 hardware. Ensure SMPS2ASM workflow and instrument editor support SSG-EG register writes.

### 6.9 Music Fade State Machine (implementation for 6.4)

The transition types (FADE_CUT, CROSSFADE, STINGER) require an explicit state machine:
- `Music_Fade_State`: IDLE → FADING_OUT → SWITCHING → FADING_IN (or STINGER_PLAY for stingers)
- `Music_Fade_Counter`: frames remaining in current phase
- `Music_Fade_Volume`: current fade level ($00-$7F)
- `Music_Next_ID`: track queued after fade completes

Section_Preload reads `sec_transition_type` and initiates the state machine. Runs in main loop alongside palette cross-fading. By teleport time, music and visual transitions match.

### 6.10 Cascade Effects

```
Audio System Cascades (updated with web research):

Flamedriver (6.1) + Tempo/Timing (6.8)
  → Zero 68K cost — all sound processing on Z80
    → YM Timer A tempo decouples music from VBlank — lag frames irrelevant
      → Z80 bus stops minimized to controller reads only
        → PSG silence on pause prevents sustained tones

Section-Aware Banking (6.4) + Bank Optimization (6.8)
  → Section preload triggers sample bank swap on Z80
    → Music transition type controls fade/cut/stinger
      → Bank switch optimization packs samples per-section (minimize 100+ cycle switches)
        → Conditional bank swaps respond to game state (boss, water, speed shoes)
          → Ambient soundscape pool creates per-section sonic identity

Distance Attenuation (6.5) + Priority Mixing
  → PlaySoundLocal computes volume from distance + log table
    → Per-algorithm carrier mask ensures correct TL modification per FM algorithm
      → Multiple SFX ranked by priority for natural mixing
        → Audio foreshadowing: enemies audible before visible

DAC Enhancements (6.2)
  → DMA protection buffering survives 24KB DMA without audio dropout
    → DPCM saves ~50% ROM on samples
      → Pitch-shifted SFX reuse samples at different rates
        → DC offset removal eliminates boundary clicks
          → Pseudo-stereo + frequency panning creates wide stereo image
```

---

## 7. Visual Effects System

Palette management, raster effects, hardware-driven lighting, and a lightweight effects engine. The palette system is fully section-aware with computed water palettes (novel). Raster effects are driven by a unified per-scanline command table (§7.2) — Batman & Robin's core raster architecture, enabling stackable VDP register changes per frame. Shadow/Highlight mode provides hardware transparency and lighting at zero CPU cost. Boss and special stage effects use Batman-inspired compound rotation math.

### 7.1 Palette System

**Palette cross-fading:** Section transitions smoothly cross-fade between palettes over ~16 frames using per-component RGB Lerp. Start during preload phase — by teleport, the transition is complete. Eliminates jarring palette snap at section boundaries. ~3840 cycles during the transition window, run in idle time.

**Computed water palette (NOVEL):** Instead of maintaining separate water palette data per zone, compute at runtime: `water_color = (base_color >> 1) + blue_bias`. Automatically adapts to palette cycling AND cross-fading — water palette is always derived from current palette, never stale. No Genesis game computes water palettes at runtime.

**Per-section palette cycling (NOVEL):** Palette cycling scripts are per-section via `sec_pal_cycle` in the section definition. Different sections within a zone have different cycling effects (forest shimmer → ice sparkle → sunset glow). Combined with computed water palette, section transitions smoothly cross-fade both base and water palettes with cycling effects changing seamlessly.

**Palette DMA via queue:** All palette uploads route through Priority 0 (critical) DMA queue. Prevents CRAM dots, synchronizes with other VRAM updates.

**Fade-to-white:** Both black and white fades (from S.C.E.). Same 22-frame component-stepping algorithm targeting $EEE. Used for dramatic exits, bright entries.

**Screen flash effects :** Two flash types from S.C.E.:
- White flash: fill CRAM with $EEE for N frames (boss explosions, lightning)
- Negative flash: XOR palette with $EEE mask, flicker every 4 frames (damage feedback, power-up activation)

**Per-scanline palette gradient :** Cycle-exact CRAM writes during HInt — 3 colors per scanline pushed into overscan (Sonic 3 technique). Enables smooth 224-step sky/water gradients. Pre-computed gradient table: 224 × 6 bytes = 1,344 bytes RAM. **Key timing detail:** DMA to CRAM and VSRAM during active display runs at 2x the speed of VRAM DMA (36 bytes/scanline in H40 vs 18 bytes/scanline). This doubled bandwidth makes mid-frame palette gradient writes and VSRAM column-scroll updates significantly more practical than VRAM transfers during active display.

### 7.2 Unified Raster Command Table (from Batman & Robin)

Rather than separate per-effect HBlank handlers, the engine uses a **unified per-scanline command table** — a pre-computed list of VDP register changes that the HBlank handler walks sequentially. This is Batman & Robin's core raster architecture, and the reason it achieves visual effects no other Genesis game matches.

**Architecture:**
```
Raster_Command_Table:   ; pre-built per section, sorted by scanline
    dc.w  SCANLINE       ; trigger line
    dc.w  REGISTER        ; VDP register to write
    dc.w  VALUE           ; value to write
    ; ... repeat for all raster events this frame
    dc.w  $FFFF           ; terminator

; HBlank handler walks the table:
HBlank_Handler:
    ; compare current scanline to next command's trigger line
    ; if match: execute command, advance pointer
    ; multiple commands can fire on the same scanline
    rte
```

**What this enables (stackable per frame):**
- Palette swap at water line (line 140)
- Nametable register swap for multi-layer Plane B (line 96, line 160)
- VSRAM column deformation per scanline range (lines 80-160)
- S/H mode toggle at section boundary (line 112)
- Window plane resize for letterboxing (lines 0-32, 192-224)
- Per-scanline palette gradient (every line, via CRAM writes)

All from ONE handler walking ONE table. No per-effect handler swapping, no priority conflicts between effects, no limit on how many effects stack in a single frame.

**Section installs its raster table:** `sec_raster_table` pointer in the section definition. Section preload copies or points to the section's command table. Default is an empty table (just the terminator) — zero cost when no raster effects are needed.

**Build-time generation:** The build tool compiles high-level raster effect descriptions (water line, parallax bands, nametable splits) into sorted command tables. The 68K never sorts or builds tables at runtime.

**PAL compensation:** S.C.E. uses a `$700`-cycle delay loop on PAL to hide CRAM dots during HBlank palette swaps.

**Mid-frame nametable register swapping (from Batman & Robin):** VDP registers #2/#4 (Plane A/B nametable base) are NOT latched at line start. Writing register #4 during HBlank changes Plane B's nametable address for the next scanline, giving **multiple Plane B nametables per frame**. Each section specifies nametable split scanlines and VRAM addresses as raster commands. VRAM cost: 2KB (H32) or 4KB (H40) per extra nametable. With ~20KB VRAM free after tiles, room for 2-3 extra nametables.

**Mid-frame VSRAM manipulation (from Batman & Robin):** VSRAM column scroll values are read per-column, not latched. Writing VSRAM during HBlank gives per-scanline column offsets. Practical limit: 2-4 columns per HInt (full 20-column update is too many VDP writes for HBlank). Used for boss deformation, shearing effects, pseudo-3D perspective. **Key timing:** VSRAM DMA during active display runs at 2x speed (36 bytes/scanline in H40), making bulk VSRAM updates more feasible than VRAM transfers.

**FIFO slot-precise mid-scanline writes (from Titan Overdrive):** 18 external access slots per H40 scanline at known pixel positions. H-counter polling can target specific slots for VSRAM/CRAM writes between HBlanks, enabling finer-grained raster effects than HBlank-only dispatch. Available for specialized effects but increases CPU cost significantly.

**Scroll table vs H-interrupt efficiency:** Most parallax does NOT need HInt — the VDP hardware scroll table handles per-line H-scroll and per-column V-scroll natively. Reserve HInt for operations requiring mid-frame VDP register changes: palette swaps, nametable register swaps, VSRAM manipulation, S/H mode toggling. Per-line HInt processing consumes 30-50% CPU; pre-computing scroll tables during main loop is far cheaper.

**Interlace Mode 2 (320x448, available):** Register $0C LSM=11 gives double vertical resolution with odd/even field alternation. Not useful for gameplay (flicker at 30fps effective), but available for high-resolution text overlays in menus, cutscene stills, or special stage effects at half framerate.

### 7.3 Shadow/Highlight Mode — Hardware-Driven Lighting (NOVEL for platformers)

VDP Register $0C enables per-pixel brightness manipulation at **zero CPU cost**:
- Low-priority plane pixels auto-shadow (RGB halved)
- High-priority tiles render at normal brightness
- Palette line 4 sprite pixels 14/15 become transparent highlight/shadow operators

**Section-aware S/H:** `sec_shadow_highlight` flag in section definition. Sections independently enable/disable S/H. HInt toggles at water line for zoned lighting.

**Applications:**
- Semi-transparent water (Mega Turrican pattern — S/H enabled below water line)
- Cave darkness with player spotlight (highlight-operator sprites around player)
- Day/night per section (toggle tile priorities)
- Translucent boss barriers (shadow-operator sprites)

**Trade-off:** Palette line 4 colors 14-15 become operators (not visible as sprite colors). Art pipeline must account for this. Fully compatible across all Genesis hardware revisions.

**SNES-style transparency via S/H (2024 discovery):** Shannon Birt demonstrated genuine translucent sprites by pre-computing palette entries so shadow/highlight math of `sprite_color + underlying_color` produces the desired blended result. Shadow math: `(color >> 1) & %011011011`. Processes 5,120 pixels/frame at 60fps. Requires knowing underlying plane colors — best for fixed backgrounds (water surface overlays, glass/crystal effects, shield effects), not arbitrary overlap. Niche but available for specific per-section effects.

### 7.4 Effects Engine (from Batman & Robin, simplified)

**512-entry sine table :** Upgrade from 256 entries. Batman quarter-wave trick: `cos(θ) = SineTable[θ + 128]` — one table, both trig functions. 512 extra bytes ROM.

**Compound rotation :** Batman's two-sine formula: `x = A1×cos(θ1) + A2×cos(θ2)`, `y = A1×sin(θ1) + A2×sin(θ2)`. Creates circles, figure-8s, spirals, Lissajous curves from varying angle ratios. ~50 cycles per point (4 muls + 8 adds). Used for boss projectile spirals.

**Pre-rotated frame selection :** Map angle to pre-rendered frame: `lsr.w #5, d0` (512 angles ÷ 32 = 16 frames). Zero CPU cost beyond lookup. Used for directional sprites (projectiles, rotating objects).

**Effect sequencer :** Simplified Batman command interpreter with opcodes: wait, set_palette, loop, branch, call, set_scroll, fade, end. Drives boss intros, special stage sequences, section transition effects. Data-driven — new effects are new scripts, not new code.

**Combined line+column scroll pseudo-rotation :** Per-scanline H-scroll offsets + per-column V-scroll offsets create pseudo-plane-rotation. `H_offset[y] = y × sin(θ)`, `V_offset[x] = x × cos(θ)`. Approximates rotation ±15°. Used for special stage backgrounds, dramatic camera tilts. CPU cost: just writing scroll tables once per frame.

### 7.5 Utility Systems

**Screen shake (from S.C.E.):** Two pre-computed offset tables applied as camera Y displacement. Timed shake (20 entries, escalating amplitude) for impacts. Infinite shake (64-entry pseudo-random pattern) for earthquakes. Data-driven — new patterns are new tables.

**Oscillator system (from S.C.E.):** 16 simultaneous oscillators in a single per-frame loop. Each has frequency, amplitude, direction, velocity. 64 bytes RAM. Used for platform bobbing, ring animation timing, water surface oscillation, boss breathing. Objects read oscillator values instead of maintaining individual timers.

**Window plane HUD :** HUD renders to the VDP window plane (non-scrolling, overlays Plane A where active). Frees 8-12 sprite slots for gameplay. HInt-driven resize for dynamic letterboxing during boss intros and cutscenes.

**Hit-stop / freeze frame system :** Skip the object update loop for N frames (3-6 = 50-100ms) while keeping display, DMA, and input processing active. Combined with 1-2 frame white palette flash, creates ~30% stronger perceived impact. 1 byte RAM (`Hit_Stop_Counter`), ~12 cycles/frame when inactive (tst+beq). Trigger points: boss damage (3-4 frames), player hit (2-3 frames), enemy kill (1-2 frames), boss death (8-12 frames + camera shake).

### 7.6 Sprite Cache Table-Switching — Free Water Reflections (from Castlevania: Bloodlines)

The VDP caches sprite Y-positions, sizes, and link data internally — but NOT X-positions or tile IDs. Switching the sprite attribute table address register (VDP reg #5) mid-frame causes the VDP to use cached Y/size/link from the first table but read X/tile from the second table.

**Application:** Two sprite attribute tables in VRAM. At the water surface (via HBlank), write VDP reg #5 to point to table 2. Sprites above water render from table 1 normally. Below the water line, the VDP reads table 2's X/tile (allowing Y-flip, darker palette, position offset for reflections) while using table 1's cached Y and link chain. **Zero CPU cost** for the reflection — just one VDP register write in HBlank.

**VRAM cost:** $280 bytes for the second sprite table. The reflection table can be pre-built during the object loop: copy each sprite entry with flipped Y and palette swap. Or use a simpler approach — same entries but with a different base tile offset pointing to pre-darkened palette variants.

**Why this beats software reflections:** Software sprite doubling (writing each sprite twice) costs 80+ entries in the sprite table and doubles DMA bandwidth. This hardware trick uses the same 80 entries, adds one HBlank register write, and produces free reflections with zero CPU overhead.

Source: Castlevania: Bloodlines, rasterscroll.com sprite raster effects

### 7.7 Vertical Border Opening — 19 Extra Scanlines (from Kabuto)

Switching from V28 (224 lines) to V30 (240 lines) during active scan, then back to V28 before line 240, causes the VDP to "forget" to start the vertical border. Result: 243 displayable lines on NTSC instead of 224.

**Technique:** At the end of line 224, briefly set V30 mode then immediately revert to V28. The VDP border state machine misses its trigger. Sprites and HScroll work normally in the opened border area.

**Uses:** Bottom HUD in the border region (saves 2+ tile rows of play area). Taller play area for specific zones. Cinematic letterbox removal for dramatic reveals.

**Caveats:** 256x1024 plane size fails (9-bit counter overflow). HIRQ runs continuously without frame reset in the border region. Must be coordinated with the HBlank system (7.2) if raster effects span the border area.

Source: Kabuto hardware notes

### 7.8 Sprite Mapping Format — VDP-Order Reorder

Reorder sprite mapping fields to match VDP sprite table entry layout for sequential word copies in `build_sprites`. The traditional Sonic format (`{Y, size, tile, X}` with different bit packing) requires field extraction and rearrangement per piece. The new format matches VDP order directly.

**Format:** 6-byte frame header (bounding box + piece count) + 8 bytes per piece:
```
; frame header (6 bytes):
dc.b  bbox_x_min               ; +0: signed — leftmost piece pixel
dc.b  bbox_x_max               ; +1: signed — rightmost piece pixel (right EDGE: x_off + width)
dc.b  bbox_y_min               ; +2: signed — topmost piece pixel
dc.b  bbox_y_max               ; +3: signed — bottommost piece pixel (bottom EDGE: y_off + height)
dc.w  piece_count              ; +4: number of sprite pieces in this frame
; per piece (8 bytes at +6, VDP sprite table order):
dc.w  y_offset                 ; signed, relative to object origin
dc.w  size_template            ; VDP size in high byte, low byte = 0 (link merged at runtime)
dc.w  tile_offset              ; relative tile index + palette/priority/flip bits
dc.w  x_offset                 ; signed, relative to object origin
```

**Bounding box:** The 4 signed extent bytes are precomputed at build time as the union of all piece rectangles, made flip-invariant (union of the unflipped and flipped extents) so one box is valid for all four flip states. `Draw_Sprite` culls exactly against this box — no fixed ±32 margins, no per-piece checks, asymmetric frames never pop at screen edges.

**Why VDP-order:** Each VDP sprite table entry is 8 bytes: `{Y, size+link, tile+attr, X}`. When the mapping format matches this layout, `build_sprites` can process each piece with sequential word reads from the mapping data and sequential word writes to the sprite table — no field shuffling, no bit extraction. The link byte is the only field merged at runtime (low byte of word 1).

**Termination:** The `piece_count` header (at +4, after the bbox) eliminates per-piece terminator checks entirely. A sentinel-based approach ($8000 terminator) saves one word of data but costs a `cmpi` per piece — with 60-100 sprite pieces per frame, the count header is faster.

**Savings:** Eliminates field reordering and bit manipulation per sprite piece per frame. With 20+ objects rendering 3-5 pieces each at 60fps, this saves hundreds of instructions per frame — effectively free performance from a data format change.

**Build pipeline:** The build tool generates all sprite mapping data in VDP-order format directly. `Render_Sprites` consumes it with sequential word copies.

Source: plutiedev.com/blog/20241013 (original reorder concept), extended with VDP-order alignment and count header.

### 7.9 Palette Cycling Animation Trick (from Jon Burton / Sonic 3D Blast)

Each tile uses only 4 of 16 palette entries per "sub-frame." By cycling which 4 entries are active each frame, one stored tile frame becomes 4 displayed frames. 15fps tile animation appears as 60fps to the eye.

**Application:** Waterfalls, energy fields, fire effects, animated crystals — store 1/4 the animation frames, get 4x the visual frames via CRAM writes. Zero DMA cost for the animation (just palette changes, which are Priority 0 and always transfer). Zero additional VRAM for animation frames.

**Trade-off:** Each sub-frame uses only 4 colors, so the combined effect has limited color depth. Best for effects where motion matters more than color variety.

### 7.10 Project MD Reflection Floor (safe, no undocumented features)

Render objects twice: normal sprites at high priority, reflection sprites at low priority with Y-flip and dark palette. High-priority Plane B acts as the floor surface. Reflections show through transparent pixels in the floor tiles. Per-line H-scroll on the floor creates perspective distortion.

**Why this is notable:** Creates convincing 3D reflective floors using only standard VDP features. No undocumented registers, no hardware tricks. Works on all Genesis hardware revisions. Barely costs CPU — just duplicate sprite entries with modified attributes.

**Combines with:** Shadow/Highlight mode (7.3) for automatic darkening of the reflection. Sprite cache table-switching (7.6) for zero-cost reflection generation if the floor is at a fixed Y position.

### 7.11 Cascade Effects

```
Visual Effects Cascades:

Palette Cross-Fading (7.1)
  → Section_Preload starts fade, teleport completes it
    → Computed water palette auto-derives from current fade state
      → Per-section cycling scripts install alongside cross-fade
        → Per-scanline gradient updates from cross-faded palette
          → Base + water + cycling + gradient all transition seamlessly

Shadow/Highlight Mode (7.3)
  → sec_shadow_highlight flag per section
    → HInt toggles S/H at water line for zoned lighting
      → Highlight-operator sprites around player = spotlight in dark sections
        → Combines with computed water palette (shadow below water = auto-darker)

Unified Raster Command Table (7.2)
  → Section definition specifies sec_raster_table
    → Section_Preload installs new command table
      → Water palette swap + S/H toggle + gradient + nametable split + VSRAM deform stack in ONE table
        → Build tool compiles high-level effect descriptions into sorted commands
          → Window plane resize, letterboxing, multi-layer Plane B — all just table entries
            → Scroll table pre-computation handles parallax WITHOUT HInt overhead
              → HInt reserved only for register changes that require mid-frame VDP writes

Effects Engine (7.4)
  → Sine table shared by: rotation math, parallax deformation, oscillation, pseudo-rotation
    → Compound rotation creates boss patterns from data
      → Effect sequencer drives cutscene/transition visual sequences
        → Pseudo-rotation creates special stage backgrounds

Hit-Stop System (7.5)
  → Boss damage triggers freeze + white flash + camera shake
    → Object loop skipped but display/DMA/input remain active
      → Combined with palette flash (7.1) for compound impact feel
        → Per-trigger-point frame counts tuned for game feel

Oscillator System (7.5)
  → 16 oscillators drive: platform motion, water surface, ring timing, shake amplitude
    → Objects read oscillator values (no per-object timer state)
      → Screen shake reads oscillator for natural amplitude variation
```

---

## 8. Tooling & Build System

Build-time tools that convert human-friendly level data into optimized runtime formats, plus runtime debug/profiling systems for data-driven optimization. Commercial Genesis games shipped with zero debug infrastructure; the community (Vladikcomper, Flamewing, S.C.E.) has since built what 90s studios lacked.

**Cross-reference (5 games + S.C.E.):** No commercial game has runtime profiling or assertions. Vectorman is the only game with runtime bounds checking (`illegal` on out-of-range pointers). Batman & Robin is the only game with lag frame detection (dual frame counter comparison). S.C.E. has the most comprehensive debug system: two-phase gating (`if DEBUG_xxx` + `ifdebug`), 10 per-subsystem debug toggles, Vladikcomper MD Debugger v2.6 with crash screen/backtrace/symbol resolution, and a VDP window plane lagometer.

### 8.1 Authoring Pipeline — Editor to ROM

The authoring pipeline decouples the level editor's creative tools from the runtime data formats. The editor works with human-friendly concepts (tiles, blocks, chunks); the build tool converts everything into optimized runtime formats (nametable strips, collision maps, compressed tile art).

**Editor workflow — paint at any granularity:**
- **Tile creation:** Artist draws 8×8 tiles in the art editor. These are the atomic art units.
- **Block creation:** Artist groups tiles into 16×16 blocks (2×2 tiles each) — reusable stamps with per-tile flip/palette attributes.
- **Chunk creation (optional):** Artist groups blocks into 128×128 chunks (8×8 blocks) — larger reusable patterns for terrain structures.
- **Level painting:** Artist paints the level layout using any combination:
  - Place individual 16×16 blocks for fine detail
  - Stamp 128×128 chunks for repeated structures (platforms, terrain patterns)
  - Mix freely — chunks and individual blocks in the same section
- Chunks, blocks, and tiles are **editor-only concepts** — they exist for creative reuse and workflow speed. The runtime never sees them.

**Build tool pipeline (runs as part of `build.sh`):**

1. **Flatten:** Convert each section's layout from chunks/blocks into a flat grid of 8×8 tile references.
2. **Deduplicate tiles:** Identify identical tiles across sections (including flip variants). Build a master tile set per zone.
3. **Graph-color VRAM indices (2.3):** Construct section adjacency graph from the 2D grid. Assign VRAM tile indices so non-adjacent sections reuse indices. Shared tiles get permanent indices; unique tiles get reusable indices.
4. **Generate nametable strips:** Output raw VDP nametable words (tile index + palette + priority + flip bits) per column per section. Stored in ROM, ready for direct DMA to VDP scroll planes.
5. **Embed collision in strips:** Append 24 collision bytes + 8 padding to each 96-byte nametable column, producing 128-byte wide strips. Collision derived from tile→collision assignments (one type per 16×16 cell).
6. **Compress tile art:** S4LZ-compress each section's tile art with tile-delta preprocessing. Output per-section compressed art blobs for streaming decompression.
7. **Report:** Total ROM size per section and per zone. Tile budget usage per section and per corner intersection. Warnings for any corner exceeding budget.

**Cross-reference:** Batman & Robin stores level nametable data at `$100000+` in raw VDP format — 16-bit nametable words encoding tile index + palette + flip bits, ready for DMA straight from ROM to VRAM scroll planes. Zero runtime conversion. Our tool does the same thing, but for the section streaming system's per-column strips rather than full-screen pages.

**Build integration:** Tool runs after level data export, before assembly. Outputs `.bin` files that get `BINCLUDE`'d per-section. Reports total ROM size contribution — if nametable strips push past 1.5MB, escalate ROM banking awareness (Section 9.8).

### 8.1b Level Editor Tile Budget UI

The build tool generates tile budget data that the level editor displays in real time, giving artists immediate feedback on VRAM constraints while painting.

**Per-section tile panel:**
- Shared tile count (used by this section AND at least one adjacent neighbor)
- Unique tile count (only this section uses them)
- Color-coded tile palette: shared tiles in one color, unique tiles in another
- Total tile count vs pool budget (1,536 tiles minus permanent allocations)

**Per-corner budget view:**
- For each 2×2 intersection in the section grid, show: total tiles needed by all 4 sections vs budget remaining
- Green / yellow / red indicator (green = comfortable, yellow = within 10% of limit, red = over budget)
- Click a corner to see exactly which tiles are shared vs unique to each of the 4 sections

**Warning system:**
- **Build-time error** if any corner exceeds the tile budget — ROM will not build
- **Build-time warning** when any corner is within 10% of the limit
- **Smart suggestions:** "Sections A and C have 12 tiles that differ by only flip — merging saves 12 slots"
- **Flip-variant detection:** Identify tiles that are horizontal/vertical flips of existing tiles (VDP handles flipping for free via nametable bits)

**Why this matters:** Without budget visualization, artists would paint sections in isolation and discover at build time that a 4-way corner exceeds the 1,536-tile pool. The budget UI makes VRAM constraints visible during the creative process, not after it.

### 8.2 Debug System Architecture (from S.C.E. + Vladikcomper + Vectorman)

**Two-phase debug gating (from S.C.E.):** Two independent debug dimensions that compose cleanly:

1. **`GameDebug`** — in-game debug mode (fly around, place objects). Gameplay feature, always available in debug builds.
2. **`__DEBUG__`** — engine assertions and diagnostics. Defined by assembler flag `-D __DEBUG__` in `build_debug.sh`. Gates all `RaiseError` checks, `ifdebug` blocks, and the profiler overlay. The `ifdebug` macro expands its arguments only when `__DEBUG__` is defined — zero overhead in release.

**Per-subsystem debug toggles (from S.C.E.):** Each engine subsystem has its own compile-time flag, all OR'd with a master `DEBUG_ALL` switch:
```
DEBUG_ALL                = 1           ; master switch
DEBUG_DMA                = 0|DEBUG_ALL ; DMA queue overflow
DEBUG_DrawLevel          = 0|DEBUG_ALL ; plane buffer overflow
DEBUG_S4LZ               = 0|DEBUG_ALL ; S4LZ buffer overflow
DEBUG_LoadObjects        = 0|DEBUG_ALL ; object slot bitmask / type table overflow
DEBUG_LoadRings          = 0|DEBUG_ALL ; ring slot buffer / bitmask overflow
DEBUG_RenderSprites      = 0|DEBUG_ALL ; object/mappings address validation
DEBUG_SectionStreaming    = 0|DEBUG_ALL ; section boundary/preload checks
DEBUG_VRAMAllocator      = 0|DEBUG_ALL ; VRAM allocation overflow
```

Individual checks can be enabled/disabled without recompiling everything. The two-layer gating means: compile-time `if DEBUG_xxx` controls whether the check is assembled, and `ifdebug` requires `__DEBUG__` at the assembler level.

**Build scripts:** Release and debug builds are identical except for `-D __DEBUG__`. Debug includes all assertion modules, error handler, profiler, and symbol table. Release compiles them all out — zero ROM cost.

### 8.3 Error Handler (Vladikcomper MD Debugger v2.6)

**Cross-reference:** Commercial Genesis games had minimal exception handling. Vectorman points all exception vectors to `$000000` (relies on dev hardware catching null jumps). Gunstar Heroes and Alien Soldier use unique 4-byte stubs per exception type for identification in stack traces. Batman & Robin packs error type IDs into the high byte of exception vector addresses (`$0240800C` = error ID `$02`, handler at `$800C`) — the 68000's 24-bit address bus ignores the high byte, but it's readable on the exception stack frame. Thunder Force IV gives each exception 12 bytes of handler space for in-place diagnostic code.

**Our approach:** Vladikcomper's MD Debugger v2.6 surpasses all of these. Integrated as a pre-compiled ~3.8KB blob with:

- **All 68000 exception types handled:** Bus error, address error, illegal instruction, divide by zero, CHK, TRAPV, privilege violation, trace, Line-A/F emulators. Each displays a human-readable error message.
- **Register dump:** All d0-d7 and a0-a7 with symbol resolution for address values.
- **Backtrace:** Walks the stack looking for return addresses and resolves them to symbol names. Available via button press on crash screen (A = address register details, B = backtrace, C = configurable).
- **Symbol resolution:** `convsym` extracts symbols from the AS assembler listing file and appends them to the ROM. The error handler reads this table at runtime to resolve any address to its nearest symbol name. Must be the very last thing in ROM.
- **Bus/address error details:** The 68000's exception stack frame includes the faulting access address, a read/write flag, and function code (code vs data space). The error handler decodes these for immediate diagnosis.
- **`RaiseError` macro:** Manual error raising with formatted strings and register value interpolation. Used at system boundaries (see 8.4).
- **`assert` macro:** Conditional check with automatic error message generation. Saves and restores CCR so it can be inserted between any two instructions without side effects: `assert.l mappings(a0),ne` crashes if an object has null mappings.
- **Console programs:** `RaiseError` can specify a console program that runs after the crash screen for extended diagnostics — formatted table dumps, human-readable descriptions of error codes.
- **Works on real hardware and all emulators.** No emulator-specific features required.

### 8.4 Per-Module Debug Assertions (from S.C.E., enhanced with Vectorman patterns)

Proactive `RaiseError` checks at every system boundary. Each gated behind its `DEBUG_xxx` flag. Catches bugs at the source, not at the crash.

**S.C.E. assertion sites (ported to our systems):**
- DMA queue overflow — `cmpa.w #DMA_queue_end,a1` before enqueue
- Plane buffer overflow — `cmpa.w #Plane_buffer_end,a0` before write
- S4LZ decompression buffer overflow — bounds check on queue pointer
- Object slot bitmask overflow — bounds check against 64-object-per-section limit
- Ring slot buffer overflow — bounds check against expanded ring count vs buffer size
- Ring pattern expansion — validate count + spacing don't exceed section bounds
- Object type table index — bounds check 5-bit type index against section's table size
- Render sprites invalid object — `assert.l code_addr(a0),ne` and `assert.l mappings(a0),ne`
- MegaPCM/Flamedriver sample table errors — error code + human-readable description via console program

**Vectorman-inspired additions (NOVEL):**
- **Pointer bounds checking before indirect calls:** `cmpa.l #ROM_End,a0` before any `jsr (a0)` through a function pointer. Catches corrupted pointers before they cause an address error in a completely unrelated location.
- **Debug breadcrumbs:** Save function pointer, object pointer, and parameter to fixed RAM addresses before indirect calls. These survive a crash and can be inspected in the emulator memory viewer for post-mortem diagnosis. Zero cost in release (compiled out).
- **Parameter corruption detection:** After returning from an indirect call, verify that caller-saved registers weren't corrupted. `cmp.w saved_value,dn; bne RaiseError`. Catches register clobbering bugs that would otherwise manifest as mysterious later failures.

**CHK instruction bounds checking:** The 68000's `chk #MAX,Dn` auto-triggers a CHK exception (vector 6) if Dn < 0 or Dn > MAX. 10 cycles when in-bounds — comparable to a CMP+BCC pair but in one instruction. Use for: jump table dispatch indices, object slot indices, animation frame range, VRAM tile indices. Compiled out in release via conditional assembly. No commercial Genesis game uses CHK for bounds checking — it was designed for Pascal compilers, but it's a perfect fit for our debug system.

### 8.5 Frame Profiler (NOVEL — no Genesis game has this)

Two complementary profiling approaches, both debug-only:

**Raster bar profiler (backdrop color technique):** Change CRAM entry 0 (backdrop color) at key code boundaries to visualize timing as colored horizontal bands. The band height directly corresponds to CPU time consumed. If colors extend past the active display area, you're overrunning the frame budget. Creates "CRAM dot" artifacts (single rogue pixels) during active display — acceptable for debug. Implementation: write to VDP data port with CRAM write command pre-loaded.

**VDP window plane lagometer (from S.C.E.):** Before the VSync wait loop, set window plane H position to default (hidden). After VSync completes, shift the window plane right. The visible bar width shows how much frame budget was consumed. No RAM variables needed — just two VDP register writes per frame. Cleaner than raster bars (no CRAM dots) but less granular (shows total frame time, not per-system breakdown).

**KDebug timer interface (from S.C.E.):** Writes to VDP register `$9F` are intercepted by Gens KMod and compatible emulators as debugger commands. `KDebug.StartTimer` / `KDebug.EndTimer` measure exact cycle counts between two points. `KDebug.BreakPoint` pauses emulation. Only works in KMod-compatible emulators, but provides the most precise timing data. All gated behind `ifdebug`.

**Lag frame detection (from Batman & Robin):** Dual frame counters — VBlank increments one, main loop samples it with a threshold comparison. If VBlank has fired multiple times before the main loop finished, lag is detected. Batman uses `addq.l #2; cmp.l` to allow up to 1 frame of slack. Our implementation: `Lag_frame_count` incremented in VBlank, reset in main loop. Value > 1 = lag frame. The profiler overlay displays a lag indicator.

**Stack depth tracking:** Place sentinel word `$DEAD` below the stack base. VBlank checks it once per frame — if overwritten, the stack has overflowed. Zero cost on the happy path (one `cmpi.w`). No commercial Genesis game has stack overflow detection.

**Watchdog timer:** VBlank increments a counter, main loop resets to zero. Counter reaching 3 means the main loop hung for 3 frames. Error handler fires with context showing where the main loop was stuck (PC from the VBlank stack frame). Zero cost on the happy path.

### 8.6 RAM Layout Documentation (NOVEL)

Build-time script that parses `S4.constants.asm` and outputs a visual RAM map showing all regions, sizes, and remaining free space. Flags overlapping regions, warns if any region exceeds its budget. Prevents the silent RAM collisions that plague Genesis development.

**Cross-reference:** S.C.E.'s `Variables.asm` uses `phase`/`dsset` directives with a compile-time overflow check: `if * > 0; fatal "RAM declarations too large by $\{*} bytes."; endif`. Our script goes further — it generates a visual map and warns about near-misses, not just hard overflows.

**Integration with sprite table safety:** Any RAM layout change that shifts `Sprite_Table` triggers a warning, preventing silent misalignment bugs.

### 8.7 Build System Improvements

**Jump size specification (from AS assembler analysis):** AS is a multi-pass assembler — forward references cause instruction length changes between passes, triggering additional passes. Some programs require up to 12 passes. Explicitly specifying `.s`/`.w`/`.l` on all branch/jump instructions eliminates this iteration entirely. Single-pass assembly is **10-50× faster** than multi-pass resolution. The `-r` flag issues warnings about pass-forcing situations, useful for finding branches that need explicit sizing.

**Dual build targets (from S.C.E.):** `build.sh` (release) and `build_debug.sh` (debug) with identical pipelines except for `-D __DEBUG__`. Both generate listing files and symbol tables.

**Symbol generation pipeline (from S.C.E.):**
1. `convsym S4.lst s4.bin -input as_lst -range 0 FFFFFF -exclude -filter "z[A-Z].+" -a` — append ROM symbol table (excludes Z80 symbols)
2. `convsym S4.lst S4_RAM.lst -in as_lst -out asm -range FF0000 FFFFFF` — generate RAM-only symbol file for emulator memory watches

The ROM symbol table must be appended after all other ROM data. The error handler reads it at runtime for address-to-symbol resolution.

**Assembly pass checking (from S.C.E.):** At end of assembly, check `MOMPASS` against a maximum allowed pass count. Warn if the assembler needed more passes than expected — indicates new forward references or unsized branches were introduced.

**Compile-time validation macros:**
- `clearRAM`/`copyRAM`: Fatal error if start > end, warning if clearing zero bytes
- `org` macro: Fatal error if org address would overwrite previously assembled bytes
- `QueueStaticDMA`: Fatal errors for odd source, odd length, zero length, 128KB boundary crossing
- `zonewarning` (from S.C.E.): Fatal if any zone-indexed table doesn't match `ZoneCount` — catches mismatched table sizes when adding levels

**Level editor integration:** SonLVL via `./run_sonlvl.sh`, exports to formats compatible with the nametable build tool.

### 8.8 Exodus MCP Integration (NOVEL)

Live emulator debugging via the Exodus MCP server, configured in `.mcp.json`. Direct inspection of hardware state without theorizing:

- **VRAM inspection:** Verify art loaded to correct tile addresses (tile index × 32 = byte address)
- **CRAM inspection:** Verify palette data (64 entries, 2 bytes each)
- **VDP registers:** Scroll positions, display settings, interrupt state
- **68k registers and RAM:** Object state, variable values, execution state
- **Breakpoints and watchpoints:** Set on specific addresses or conditions
- **Symbol loading:** Load `S4.lst` symbols for address resolution in all debug views

Direct observation beats guesswork. When a visual bug occurs, look at VRAM/CRAM/RAM directly rather than theorizing from code.

### 8.9 Cascade Effects

**Profiler → DMA budget:** Profiler data directly informs the adaptive DMA byte budget (§1.1). Measured VBlank usage determines safe DMA thresholds rather than guessing.

**Debug assertions → stability:** Every `RaiseError` site is a potential crash point caught during development. The assertion list grows as new systems are implemented — each new subsystem adds its own `DEBUG_xxx` flag and boundary checks.

**Symbol table → error handler → crash diagnosis:** The `convsym` → ROM append → `RaiseError` pipeline means every crash shows human-readable function names, not hex addresses. This turns multi-hour debugging sessions into minutes.

**Build validation → correctness:** Compile-time checks (`zonewarning`, `clearRAM` validation, org overlap detection, assembly pass counting) catch entire categories of bugs before the ROM is even built. These are effectively unit tests for the build system.

**RAM layout tool → sprite table safety:** The RAM documentation tool visualizes exactly what's adjacent to `Sprite_Table` and flags address-dependent regions, preventing silent misalignment bugs.

---

## 9. Cross-Cutting Systems

Systems that span multiple clusters or coordinate between them. These are the connective tissue that makes the engine work as a coherent whole rather than a collection of independent subsystems.

**Cross-reference (5 games + S.C.E.):** Every commercial Genesis game has cross-cutting coordination, but none have formalized it. Batman & Robin's bytecode yield system is the most sophisticated coordination mechanism (script pointer IS the state). Treasure's link fields ($58/$5C) coordinate multi-part bosses across 380+ references. S.C.E. has the cleanest level database (per-zone directories with `levartptrs` macro packing). No commercial game has SRAM save functionality among the 5 analyzed.

### 9.1 Level Database — Unified Level Descriptors (replacing Zone ID system)

A unified level database that consolidates all per-level configuration into a single self-contained descriptor per level. Eliminates the scattered-table pattern (common in Genesis engines) where adding a new level requires touching 12+ files with synchronized table entries.

**Evolution of level data organization across engines:**

| Engine | Approach | Tables to touch for new level |
|--------|----------|-------------------------------|
| Sonic 2 | Scattered fixed-size tables, zone ID indexing | 12+ files, 17 entries each |
| Sonic 3K | Level Load Block (semi-unified, high-byte packing) | 6+ files, still scattered |
| S.C.E. | Per-zone directories with `Pointer.asm` files | 4-5 files, mostly in zone dir |
| Batman & Robin | Binary level tables at `$021400` (11KB block) | 1 binary file |
| **Sonic 4 (target)** | Single descriptor per level, one file per level | **1 file** |

**S.C.E.'s approach (current best-in-class community):** Each zone has its own directory under `Levels/` containing `Blocks/`, `Chunks/`, `Collision/`, `Layout/`, `Palettes/`, `Pointers/`, etc. The `Pointer.asm` file per act uses the `levartptrs` macro to pack 23 parameters (art, blocks, chunks, layouts, collision, objects, rings, palette, music, water flag) into a flat RAM structure. Palette ID, water palette, music ID, and water flag are packed into the high bytes of longword art/layout pointers — eliminating separate lookup tables.

Loading: `LoadLevelPointer` calculates zone×act offset, then bulk-copies the entire pointer block ($A2 bytes) via unrolled `movem.l` into `Level_data_addr_RAM`. One copy operation instead of dozens of individual table lookups.

**Compile-time safety:** S.C.E.'s `zonewarning` macro fatals if any zone-indexed table doesn't match `ZoneCount`. Catches mismatched table sizes at build time.

**Our target architecture:** Go beyond S.C.E.'s approach. One self-contained level descriptor file per level containing ALL data pointers, configuration values, and section definitions:

```
LevelDescriptor_OJZ1:
    ; Art pointers (high byte = palette ID)
    dc.l (Pal_OJZ)<<24|ArtS4LZ_OJZ_FG
    dc.l ArtS4LZ_OJZ_BG
    ; Layout, collision, objects, rings
    dc.l Layout_OJZ1, Collision_OJZ
    dc.l ObjLayout_OJZ1, RingLayout_OJZ1
    ; Section table pointer
    dc.l SectionTable_OJZ1
    ; Music, water, physics
    dc.w Music_OJZ, 0  ; music ID, water flag
    dc.l PhysicsTable_OJZ  ; per-section terrain physics (5.2)
    ; Scroll/parallax definition
    dc.l DeformScript_OJZ  ; 8-layer parallax definition (4.6)
    ; Event hooks (function pointers, 0 = none)
    dc.l ScreenEvent_OJZ, BackgroundEvent_OJZ
    dc.l AnimatePalette_OJZ, AnimateTiles_OJZ
```

Adding a new level = write one descriptor file + add one `include` line to the level index. No scattered tables, no fixed slot counts, no dead entries.

### 9.2 Object Communication — Hierarchical Links + Flag Array

Objects communicate through three mechanisms, chosen by coupling tightness:

**Parent-child link fields (from Treasure, validated at scale):** Two dedicated SST offsets store object pointers for hierarchical coordination. Gunstar Heroes uses one link field ($58) with 71 references; Alien Soldier evolved to two ($58 + $5C) with 484 total references. Boss sub-objects read parent state (`btst #status.defeated,status(a1)`) and position themselves relative to parents every frame.

Our implementation uses `parent_ptr` and `sibling_ptr` fields in the SST. S.C.E.'s 12 child creation routines (`CreateChild1_Normal` through `CreateChild12_Simple`) demonstrate the full range of parent-child patterns: simple children, linked lists, tree lists, repeated spawns. `DeleteFamily` cascades to all children when a parent is destroyed.

**Level trigger array (from S.C.E.):** A 16-byte shared flag array indexed by trigger ID. Button objects set bits; door/platform objects read them. Simple, fast (one byte read per frame), and decoupled — the button doesn't know what it opens, the door doesn't know what opens it. The trigger ID in the object subtype byte is the only connection.

**Boss event buffer:** 32 bytes of boss-specific shared state for complex multi-phase boss coordination. Phase transitions, attack patterns, and defeat conditions communicate through this buffer rather than direct SST reads.

**Why not a general event/message system:** No 16-bit commercial game uses event dispatch or message queuing. The overhead of dispatch tables and message queues is not justified at 7.67 MHz with 64KB RAM. Direct flag reads and parent-child links are cheaper and sufficient for all known use cases. The three mechanisms above cover: tight coupling (parent-child links), loose coupling (trigger array), and domain-specific coordination (boss events).

### 9.3 Error Handler with Stack Guard

**Exception vector engineering (from Batman & Robin + Thunder Force IV):** Pack error type IDs into the high byte of exception vector addresses. The 68000's 24-bit address bus ignores the high byte, but it's preserved on the exception stack frame. One shared handler can identify the exception type without needing separate handlers. Batman uses `$02-$07` for Bus/Address/Illegal/Zero/CHK/TRAPV. Thunder Force IV gives each exception 12 bytes of handler space — enough for in-place diagnostic code.

**Our approach combines both:** Exception vectors use high-byte IDs (Batman technique) pointing to the Vladikcomper MD Debugger (Section 8.3). The error handler decodes the ID and displays the appropriate error message with full register dump, backtrace, and symbol resolution.

**Stack guard word:** Place `$DEAD` below the stack base during init. VBlank checks once per frame — `cmpi.w #$DEAD,(Stack_guard).w; bne RaiseError`. If overwritten, the stack overflowed. Zero cost on the happy path. No commercial Genesis game has stack overflow detection.

**Watchdog timer:** VBlank increments counter, main loop resets to zero. Counter reaching 3 = main loop hung for 3 frames → error handler fires with the VBlank's saved PC showing where the main loop was stuck. Zero cost on the happy path.

### 9.4 6-Button Controller Support

**Protocol (from web research + plutiedev):** The 6-button controller IC has an internal counter that increments on each TH pin transition. Rapid TH cycling (3 toggles within 1.5ms) triggers extra read modes:

1. Cycles 1-2: Standard 3-button reads (Up/Down/Left/Right/A/B/C/Start)
2. Cycle 3 (TH=LOW): If pins 1-4 all read LOW → 6-button pad detected (3-button shows different values)
3. Cycle 4 (TH=HIGH): Extra buttons available: X, Y, Z, Mode
4. Cycle 5+: Reset the IC counter

**Detection:** After 3 rapid TH toggles, check TH=LOW state. All RLDU bits zero = 6-button. Save controller type flag at detection; skip extra reads for 3-button pads to avoid compatibility issues (some games toggle TH too frequently and break 6-button controllers — the Mode button forces 3-button emulation as a user workaround).

**Edge detection:** Two RAM bytes per controller: `Ctrl_Held` (current state) and `Ctrl_Press` (newly pressed this frame). The EOR+AND trick: `eor.b d0,d1; and.b d0,d1` — XOR finds changed bits, AND isolates newly-pressed ones. Virtually zero cost.

**Uses for extra buttons:** X = cycle debug overlay modes, Y = frame advance (debug), Z = quick shield swap, Mode = reserved. In release builds, X/Y/Z/Mode are available for gameplay features if desired.

### 9.5 Soft-Reset Persistence (CrossResetRAM)

**Hardware behavior:** All 64KB of work RAM survives a soft reset (Start+A+B+C or reset button). The 68000 CPU resets but RAM contents persist. The VDP also keeps running during reset — any in-progress DMA continues while the 68000 restarts, potentially overwriting freshly-loaded init code. Robust startup code must account for this (brief delay or VDP disable before initialization).

**Cold vs warm detection (from S.C.E.):** Write a magic string (`'INIT'`) to a fixed RAM address during first boot. On subsequent boots, check for the magic string — if present, it's a warm boot (skip full init, preserve game state). If absent, cold boot (full init, clear everything).

**CrossResetRAM region (from S.C.E.):** Explicit RAM region between `CrossResetRAM` and `CrossResetRAM_end` that is NOT cleared on warm boot. Contains:
- Current zone/act and section coordinates
- Music state (so music doesn't restart)
- Star post / checkpoint saves (zone, position, rings, timer, camera, water level)
- HUD state (score, lives, continues)
- Debug mode saved state
- Graphics flags (PAL/NTSC detection result)

Startup sequence:
1. Always clear `RAM_start` to `CrossResetRAM` (volatile state)
2. Check magic string at `Checksum_string`
3. If absent (cold boot): clear `CrossResetRAM` to `CrossResetRAM_end`, write magic string
4. If present (warm boot): skip CrossResetRAM clear, resume from saved state

**Player experience:** On soft reset, the player resumes at their last section checkpoint rather than restarting from the beginning. Music continues from the current track. This is free — just organizing RAM correctly.

### 9.6 SRAM Save System

**Hardware (from web research + plutiedev):** SRAM mapped at `$200001+` (odd bytes only due to 8-bit SRAM chip on D0-D7 via /LWR). Controlled by register `$A130F1`: write `$01` to enable SRAM, `$00` to disable. Standard capacity: up to 32KB usable (64KB address range / 2 for odd-byte access). Battery-backed with CR2032.

**ROM header declaration:** Offset `$1B0` must declare SRAM: `dc.b "RA", $F8, $20` with start/end addresses. Some emulators (BizHawk) won't enable SRAM without correct header.

**Implementation (from Sonic 3's proven approach):**
- Store save data twice (primary + backup) for redundancy
- Each copy has its own byte-sum checksum
- On load: verify primary checksum. If corrupt, try backup. If both corrupt, initialize fresh.
- Include a version byte for forward-compatible save data
- First-run detection: magic signature at start of SRAM. If absent, initialize all SRAM.
- Lock/unlock discipline: disable SRAM writes when not actively saving to prevent accidental corruption.

**Save data contents:** Section coordinates, collected items, unlocked zones, total play time, star post state. Compact — under 256 bytes per save slot, allowing 4+ slots in the smallest SRAM.

**ROM banking interaction:** For ROMs >2MB that also need SRAM, a mapper switches the `$200000-$3FFFFF` range between upper ROM banks and SRAM. Sound data and frequently-accessed code should live in bank 0 (`$000000-$07FFFF`, fixed) to avoid switching conflicts.

### 9.7 Background Task System — Cooperative Multitasking (from plutiedev, NOVEL for Sonic engines)

The 68000's supervisor/user mode distinction enables a two-task system where background work (decompression, art preloading) runs automatically in leftover CPU time without manual chunking or bookmark systems.

**Architecture:**
- **Foreground task** (supervisor mode): Main game loop. Runs to completion every frame, guaranteed 60fps execution. Uses the supervisor stack pointer (SSP).
- **Background task** (user mode): S4LZ decompression, section art preloading, or any work that can tolerate interruption. Uses the user stack pointer (USP). Runs in whatever CPU time remains after the foreground finishes.

**Context switching:** Two switches per frame, ~80-120 cycles total overhead:
1. Foreground finishes → `YieldToBgTask`: push SR to stack (so VBlank's `rte` returns to foreground), restore background registers from RAM via `MOVEM.L`, push background's saved PC and SR, execute `rte` to jump to background task in user mode.
2. VBlank fires → `TaskSwitchIrq`: test bit 5 of stacked SR (supervisor flag). If clear, background was running — save its d0-d7/a0-a6 to RAM, extract its SR/PC from interrupt stack frame, then `rte` to foreground using its saved context.

**Why cooperative multitasking over manual chunking:**
- S4LZ decompressor runs straight through — no need to chunk into "process N bytes, check VBlank, stop." The VBlank interrupt preempts it automatically and the context switch saves all register state.
- No bookmark system needed — the context switch natively saves and restores all decompression state.
- Background task automatically adapts: heavy foreground frames give it less time, light frames give it more. Self-tuning throughput without explicit budget management.
- Simpler code — no "check if VBlank is coming" polling loops in decompression routines.

**Constraints:**
- Background task runs in user mode — cannot access privileged operations (interrupt masking, VDP registers). All hardware access stays in the foreground.
- USP is consumed (no longer available as scratch register — rarely used anyway).
- Background task must not assume it gets any minimum amount of time per frame. On lag frames, it gets nothing.

**Primary use case:** S4LZ streaming decompression. The background task runs the S4LZ decompressor continuously. Each frame, it decompresses as many bytes as the leftover CPU time allows. Completed 4KB chunks are queued for DMA to VRAM via the Deferrable DMA queue (§1.1). On light frames (standing still, few objects), decompression runs fast. On heavy frames (boss fights, many objects), it naturally throttles. No tuning required.

**Secondary use cases:** Section ring/object pre-scanning (pre-building the ring and object buffers for upcoming sections before the player reaches them), palette blend computation (computing fade/blend palettes in background rather than blocking the main loop).

### 9.8 ROM Banking Awareness

**When needed:** If pre-computed nametable strips, expanded art, or additional music push ROM past 4MB, the SSF2 mapper provides bank switching via 7 registers at `$A130F3-$A130FF`. Bank 0 (`$000000-$07FFFF`) is fixed; banks 1-7 are switchable to any 512KB page.

**Design constraints:**
- Sound data and Z80 driver must live in bank 0 (Z80 accesses ROM through the 68000 bus — bank switches during Z80 ROM access would read wrong data)
- Code must live in bank 0 or handle bank switching transparently
- S4LZ decompression from banked ROM requires the correct bank to be mapped before starting decompression — the background task (9.7) must coordinate with the bank register
- DMA from banked ROM works correctly as long as the source bank is mapped when DMA is enqueued (not when it executes — the DMA source address in the queue entry is already physical)

**Implementation:** Only add banking if ROM exceeds 4MB. Track via build-time ROM size checkpoint. If banking is needed, add a `SetROMBank` helper that writes the page number and records the current mapping for restoration.

### 9.9 128KB VRAM Mode (investigated, available for specialized effects)

**From Kabuto hardware notes:** The VDP's 128KB mode (normally for unreleased 128KB VRAM chips) can be enabled on standard 64KB hardware. In this mode, the VDP does byte-wide DMA (writing only the low byte of each word) with a different address mapping: `(((a & 2) >> 1) ^ 1) | ((a & $400) >> 9) | a & $3FC | ((a & $1F800) >> 1)`.

Setting DMA auto-increment to 4 updates every 4th byte, enabling targeted byte-level VRAM modifications without touching adjacent bytes. Page boundaries (1KB increments) require separate writes.

**Potential uses:** Partial tile updates (modifying individual pixel rows within tiles), targeted palette bit manipulation in tile data, byte-granularity VRAM clearing. Titan Overdrive 2 uses this mode for its border rendering effects.

Available as an advanced technique for specialized visual effects if needed. The address remapping is deterministic but complex — any code using it needs thorough testing on multiple hardware revisions.

### 9.10 PC-Relative Addressing Optimization

**Savings:** `lea label(pc),a0` saves 2 bytes and 4 cycles vs `lea label.l,a0` for every reference within ±32KB range. At scale, this adds up significantly.

**Cross-reference (5 engines):** Batman & Robin leads with 986 `(pc)` references. Alien Soldier has 414, Vectorman 325, Gunstar 197. Thunder Force IV has 0 — entirely absolute addressing. S.C.E. has 196, concentrated in objects (130) and engine (44). The pattern is opportunistic but consistent: used whenever a data table is within PC-relative range of its consumer (typically right below the referencing code).

**Our approach:** Systematic conversion during each code area we touch (opportunistic, per genesis-dev skill guidelines). Focus on hot paths first — object dispatch, collision routines, scroll calculations. The most impactful pattern: jump tables with `lea Table(pc,d0.w),a0; jmp (a0)` — saves 2 bytes AND 4 cycles on every dispatch. `moveq #n,dn` (2 bytes) replacing `move.l #n,dn` (6 bytes) for values -128 to +127 is the complementary optimization.

No automated conversion tool exists. Manual conversion guided by the assembler's `-r` flag, which warns about references that could be PC-relative but aren't.

### 9.11 Memory Clearing Optimization

**Three macro variants (from S.C.E.), each for a different size/speed tradeoff:**

1. **`clearRAM` (loop-based):** `moveq #0,d0` + `move.l d0,(a1)+` in a `dbf` loop. Standard clear, compact code. Used for most RAM regions.
2. **`clearRAM2` (fully unrolled):** `REPT` emits inline `move.l` instructions. Zero loop overhead. Used for small regions (<64 bytes) where code expansion is acceptable.
3. **`clearRAM3` (hybrid):** Unrolled inner loop of 16 `move.l`s inside a `dbf` outer loop. Best of both worlds for large regions — maximum throughput without massive code bloat.

**MOVEM-based bulk clear (from web research, fastest known approach):** Zero d0-d7/a0-a6 (15 registers = 60 bytes), then `movem.l d0-d7/a0-a6,(a0)` repeatedly. Each MOVEM writes 60 bytes with one instruction fetch overhead. ~2.4× faster than simple MOVE loops for large clears. Best for level-load clears where code size doesn't matter and speed does.

All macros handle odd start addresses (emit a `move.b` first) and leftover bytes after the main loop. Auto-select `.w` vs `.l` addressing based on whether the address is in the upper 32KB RAM range (sign-extended word addressing).

### 9.12 Cascade Effects

**Level database → every level-indexed system:** Unified descriptors eliminate scattered zone-indexed tables. Every system that needs level-specific data (art loading, collision, music, water, parallax, events) reads from the loaded level descriptor in RAM. One copy at level load, zero per-frame lookups.

**Background task → decompression throughput:** The multitasking system (9.7) enables S4LZ to run continuously in spare CPU time. Combined with the priority DMA queue (§1.1), this creates a pipeline: background decompresses to RAM buffer → main loop enqueues DMA → VBlank transfers to VRAM. Each stage runs independently at its own pace. S4LZ's 700-1100 KB/s throughput means per-section tile art can decompress in 1-2 frames of background time even on busy scenes.

**SRAM → CrossResetRAM → player experience:** SRAM provides permanent saves across power cycles. CrossResetRAM provides session persistence across soft resets. Together, the player never loses more than one section of progress.

**Error handler → debug assertions → stability:** The Vladikcomper error handler (8.3) is the foundation. Per-module assertions (8.4) are the sensors. Together, they catch bugs at their source — buffer overflows, null pointers, corrupted indices — before they cascade into mysterious crashes elsewhere.

**6-button controller → debug workflow:** Extra buttons (X/Y/Z) provide debug shortcuts without conflicting with gameplay controls. Frame advance, profiler toggle, and debug overlay cycling are available during normal gameplay in debug builds.

**PC-relative + clearRAM optimization → ROM size + speed:** These are cumulative micro-optimizations. Each individual instance saves 2-4 bytes or a few cycles. Across thousands of references and dozens of RAM clears, the total impact is measurable — tighter ROM, faster level loads, more headroom for content.

### 9.13 Game State Machine

**Purpose:** Drive top-level program flow — which screen is active, how transitions between screens work, and how each screen's main loop is structured. §0.12 ends with "Branch to Game_StateInit" — this section defines what that means.

**Architecture — function pointer dispatch:**

```asm
Game_State:         ds.l 1      ; pointer to current state's main loop routine
Game_State_ID:      ds.b 1      ; numeric state for save/restore and debug display

GameLoop:
        bsr.w   VSync_Wait              ; wait for VBlank flag
        movea.l (Game_State).w, a0
        jsr     (a0)                    ; run current state's frame logic
        bra.s   GameLoop
```

**States:**

| ID | State | Routine | VBlank Mode | Description |
|----|-------|---------|-------------|-------------|
| 0 | `GS_SEGA` | `GameState_Sega` | `VInt_Menu` | Sega logo (TMSS tie-in) |
| 1 | `GS_TITLE` | `GameState_Title` | `VInt_Menu` | Title screen + press start |
| 2 | `GS_MENU` | `GameState_Menu` | `VInt_Menu` | Main menu (1P, options, etc.) |
| 3 | `GS_LEVELSELECT` | `GameState_LevelSelect` | `VInt_Menu` | Debug level select |
| 4 | `GS_LEVEL_LOAD` | `GameState_LevelLoad` | `VInt_Load` | Level loading (art, layout, objects) |
| 5 | `GS_LEVEL` | `GameState_Level` | `VInt_Level` | Gameplay |
| 6 | `GS_SPECIAL` | `GameState_Special` | `VInt_Level` | Special stage |
| 7 | `GS_CONTINUE` | `GameState_Continue` | `VInt_Menu` | Continue screen |
| 8 | `GS_GAMEOVER` | `GameState_GameOver` | `VInt_Menu` | Game over |
| 9 | `GS_ENDING` | `GameState_Ending` | `VInt_Menu` | Ending sequence |
| 10 | `GS_CREDITS` | `GameState_Credits` | `VInt_Menu` | Credits roll |

**State transitions:** Each state routine sets `Game_State` and `Game_State_ID` to transition. The transition itself happens on the next `GameLoop` iteration — no mid-frame jumps, no stack unwinding. Each state is responsible for its own initialization on first entry (detected via a per-state init flag or `objroutine`-style dispatch within the state).

**VBlank mode selection:** Each state sets `VInt_ptr` to the appropriate VBlank handler during its init phase. `VInt_Level` runs the full gameplay pipeline (DMA queue, plane buffer, HUD, sound). `VInt_Menu` runs DMA queue and sound only. `VInt_Load` runs DMA queue and S4LZ processing.

**Init/teardown:** Each state has an init routine (load art, set palette, configure VDP, install VBlank mode) and implicit teardown (next state's init overwrites everything). No explicit teardown needed — the init fully owns the hardware state.

**Pause sub-state:** During `GS_LEVEL`, Start button triggers a pause overlay (darken palette, show "PAUSED" text, stop object updates, keep sound driver running). Unpausing restores palette and resumes. This is a sub-state within `GS_LEVEL`, not a top-level game state — the level state is preserved.

**Cross-references:**
- §0.12 Boot Sequence: cold boot ends at `Game_StateInit` → `GS_SEGA`
- §1.4 VBlank Structure: `VInt_ptr` selects handler per game state
- §9.5 CrossResetRAM: warm boot resumes at `GS_TITLE` with preserved score/lives

### 9.14 Text & Font Rendering

**Purpose:** Render text strings to VDP nametable planes for HUD, menus, debug console, title cards, and any screen that displays text. Every Genesis game needs this; no architecture doc should omit it.

**Font storage:** A single 96-character ASCII font (characters $20-$7F) stored as uncompressed 8×8 tiles in ROM. Loaded to a fixed VRAM region within the unified art pool (§2.3) during any state that needs text. ~3 KB ROM (96 tiles × 32 bytes). A second bold/outlined font variant for title cards costs another 3 KB.

**Tile mapping:** Character code → VRAM tile index: `tile = VRAM_Font + (char - $20)`. Palette and priority bits added per-context (HUD uses palette 0, menus use palette 1, debug uses palette 3).

**String rendering API:**

```asm
; Draw null-terminated string to plane
; a0 = string pointer, d0 = VDP nametable command (position), d1 = base art_tile word
DrawString:
        move.l  d0, (VDP_ctrl_port).l   ; set VRAM write position
.loop:
        moveq   #0, d2
        move.b  (a0)+, d2               ; read character
        beq.s   .done                   ; null terminator
        subi.b  #$20, d2                ; ASCII to tile offset
        add.w   d1, d2                  ; add base tile + palette bits
        move.w  d2, (VDP_data_port).l   ; write to nametable
        bra.s   .loop
.done:
        rts
```

**Number rendering:** `DrawHex` (register value → hex string) and `DrawDecimal` (BCD score → decimal string) for HUD and debug. BCD is the natural format for score display — no division needed, just nibble extraction.

**Deferred text:** For gameplay screens, text writes go through the Plane_buffer (§1.3, §4.4) like any other nametable update. For menu/loading screens where VDP access is less constrained, direct writes are acceptable.

**Debug text:** The MD Debugger error handler (§8.3) has its own text rendering for crash screens. The game's `DrawString` is separate — simpler, used for gameplay text. Both share the same font tiles.

### 9.15 Screen & Menu System

**Purpose:** Manage non-gameplay screens (title, menus, level select, game over, credits). Each screen is a game state (§9.13) with its own art, palette, input handling, and VBlank mode.

**Screen lifecycle:**

```
ScreenInit:
  1. Disable display (VDP reg $01)
  2. Load screen art via S4LZ blocking → VRAM
  3. Load palette → CRAM (via Priority 0 DMA)
  4. Load tilemap → nametable (raw DMA from ROM, §2.1)
  5. Load font if needed → VRAM
  6. Set VBlank mode to VInt_Menu
  7. Enable display
  8. Set Game_State to this screen's update routine

ScreenUpdate (runs each frame via GameLoop):
  1. Read controller input
  2. Update cursor/selection state
  3. Update animations (palette cycling, sprite movement)
  4. Check for state transition (Start pressed → next state)
```

**Menu cursor:** A sprite object (allocated via the standard object system) that moves between menu options. Input moves cursor position, A/C/Start confirms selection. Menu options are a ROM table of `{y_position, target_state_id}` pairs.

**Title card system:** Transition overlay between level select/continue and gameplay. Draws zone name + act number using the outlined font variant, animates in/out via horizontal scroll position. Runs as a brief sub-state within `GS_LEVEL_LOAD` — art loads behind the title card, card animates out when loading is complete.

**Credits roll:** Vertical scroll of text strings rendered to Plane A. Scroll speed controlled by a timer. Background animation (palette cycling, parallax) runs simultaneously via the standard VBlank pipeline.
