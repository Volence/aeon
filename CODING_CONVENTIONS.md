# Sonic 4 Engine — Coding Conventions

Rules for writing clean, fast, maintainable 68000 assembly for the Sega Genesis. Every line in this engine follows these conventions from the first instruction. No exceptions, no "we'll fix it later."

These conventions encode lessons from: S.C.E. (Sonic Clean Engine), Batman & Robin (Clockwork Tortoise), Vectorman (BlueSky), Gunstar Heroes & Alien Soldier (Treasure), Thunder Force IV (Technosoft), SGDK, plutiedev, Kabuto hardware research, Titan Overdrive tech demos, Amiga demoscene, and 40 years of modern game engine design.

---

## 1. AS Assembler — Use It to the Fullest

### 1.1 `function` — Every Constant Calculation

Any formula that's constant at build time MUST be a `function`. Never compute at runtime what the assembler can compute at build time.

```asm
; VDP command generation — zero runtime cost
vdpComm     function addr,type,rwd, \
              (((type & rwd) & 3) << 30) | ((addr & $3FFF) << 16) | (((type & rwd) & $FC) << 2) | ((addr & $C000) >> 14)

; Art tile encoding
vram_art    function tile,pal,pri, (pri<<15)|(pal<<13)|tile
vram_bytes  function tile, tile<<5

; Sprite size encoding (width/height in cells: 1-4)
sprSize     function w,h, ((((h)-1)<<2)|((w)-1))<<8

; Section grid index
secIndex    function x,y, ((y)*GRID_WIDTH+(x))*SEC_ENTRY_SIZE

; Collision map index (128-column shift-based)
collCell    function x,y, ((y)<<7)+(x)

; DMA word count
dmaWords    function bytes, (bytes)>>1
```

### 1.2 `struct` / `endstruct` — Named Field Offsets

Never manually chain `equ` values. Define structures so the assembler calculates offsets and catches layout errors.

```asm
        struct OBJ
code_addr       ds.l 1      ; routine pointer
mappings        ds.l 1      ; sprite mapping pointer
art_tile        ds.w 1      ; VRAM tile + palette + priority
render_flags    ds.w 1      ; on-screen, flip, multi-sprite
x_pos           ds.l 1      ; 16.16 fixed-point
y_pos           ds.l 1      ; 16.16 fixed-point
x_vel           ds.w 1      ; 8.8 fixed-point
y_vel           ds.w 1      ; 8.8 fixed-point
        endstruct OBJ
; OBJ_len is auto-generated — use for size assertions
```

### 1.3 `phase` / `dephase` — RAM Layout

Declare RAM layout sequentially. The assembler tracks addresses; overflow is caught at build time.

```asm
        phase RAM_START
Object_RAM:         ds.b MAX_OBJECTS * OBJ_SIZE
Sprite_Table:       ds.b 80 * 8
DMA_Queue:          ds.b DMA_SLOTS * DMA_ENTRY_SIZE
Horiz_Scroll_Buf:   ds.b 224 * 4
; ...
RAM_Used_End:
        if * > RAM_END
          error "RAM overflow by \{* - RAM_END} bytes!"
        endif
        dephase
```

### 1.4 Single-Pass Discipline

Specify `.s`, `.w`, or `.l` on EVERY branch, jump, and memory reference. No exceptions. This eliminates AS's multi-pass resolution and gives 10-50x faster builds.

```asm
; CORRECT — explicit sizing
        bra.s   .local_label
        bra.w   Distant_Routine
        bne.s   .skip
        jsr     Far_Function

; WRONG — forces multi-pass resolution
        bra     .local_label    ; assembler doesn't know the size
        bne     .skip           ; might be .s or .w
```

### 1.5 Local Label Scoping

Every routine's internal labels use `.prefix` scoping. Reuse `.loop`, `.done`, `.skip` freely — AS scopes them to the enclosing global label.

```asm
Process_DMA:
        tst.w   d0
        beq.s   .empty
.loop:
        move.l  (a0)+, (a5)
        dbf     d0, .loop
.done:
        rts
.empty:
        moveq   #0, d0
        bra.s   .done

; From outside: bsr Process_DMA.done (fully qualified)
```

### 1.6 Compile-Time Validation

Catch errors at build time, not at runtime. Every boundary, table size, and layout assumption gets an assembler check.

```asm
; Struct size assertion
        if OBJ_len <> $50
          error "OBJ struct is \{OBJ_len} bytes, expected $50"
        endif

; Table size consistency
        if (Table_End - Table_Start) / ENTRY_SIZE <> EXPECTED_COUNT
          error "Table entry count mismatch"
        endif

; RAM overflow
        if RAM_Used_End > $FFFFFFFF
          error "RAM overflow by \{RAM_Used_End - $FFFFFFFF} bytes"
        endif

; VRAM pool budget (final pass only)
        if MOMPASS > 1
          if Permanent_Tiles_End > VRAM_POOL_END
            error "Permanent tiles overflow pool by \{Permanent_Tiles_End - VRAM_POOL_END}"
          endif
        endif
```

### 1.7 Conditional Debug Assembly

Two-layer gating for zero-cost debug in release builds.

```asm
; Per-subsystem flags
DEBUG_ALL           = 1
DEBUG_DMA           = 0 | DEBUG_ALL
DEBUG_VRAM          = 0 | DEBUG_ALL
DEBUG_Objects       = 0 | DEBUG_ALL
DEBUG_Collision     = 0 | DEBUG_ALL

; Debug wrapper macros
ifdebug macro subsystem
        if __DEBUG__ && DEBUG_\subsystem
        endm

debugend macro
        endif
        endm

; Usage — compiled out entirely in release
        ifdebug DMA
        cmpa.w  #DMA_Queue_End, a1
        blo.s   .dma_ok
        RaiseError "DMA queue overflow at %a1"
.dma_ok:
        debugend
```

### 1.8 Build-Time Data Generation

Use `rept`, `irp`, and math functions to generate lookup tables at assembly time.

```asm
; Sine table — computed, not included as binary
Sine_Table:
angle = 0
        rept 512
        dc.w (sin(angle * 3.14159265 * 2.0 / 512.0)) * $7FFF
angle = angle + 1
        endr

; Power-of-two table
Powers_Of_Two:
        irp val, 1,2,4,8,16,32,64,128,256,512,1024,2048
        dc.w val
        endr
```

---

## 2. 68000 Optimization Rules

These are hard rules, not guidelines. The 68000 at 7.67 MHz has no margin for sloppy code.

### 2.1 Arithmetic

| Slow | Fast | Savings |
|------|------|---------|
| `mulu #8, d0` (70 cycles) | `lsl.w #3, d0` (12 cycles) | 58 cycles |
| `mulu #10, d0` (70 cycles) | `move.w d0,d1; lsl.w #2,d0; add.w d1,d0; add.w d1,d0` (20 cycles) | 50 cycles |
| `divu #4, d0` (140 cycles) | `lsr.w #2, d0` (10 cycles) | 130 cycles |
| `mulu` for table index | Lookup table or shift | 50-130 cycles |

**Rule:** No `mulu`/`muls`/`divu`/`divs` in any code that runs per-frame. Use shifts, adds, or lookup tables. The ONLY exception is code that runs once (level load, init).

**Technique — shift-add fraction decomposition.** Any fractional scaling `p/q` where `q` is a power of 2 reduces to ≤2 shift-add operations. The supported set: `0`, `1`, `1/q`, `(q-1)/q`, `3/q`, `5/q` for q in {1, 2, 4, 8, 16, 32, ...}. Examples:

| Fraction | Decomposition | Cost |
|---|---|---|
| `1/8` | `x >> 3` | 12 cycles (1 shift) |
| `3/8` | `(x >> 2) + (x >> 3)` | 28 cycles (2 shifts + add) |
| `1/2` | `x >> 1` (or `add x,x` for shift-by-1 saving 2 cycles) | 12 cycles |
| `3/4` | `x - (x >> 2)` | 24 cycles (1 shift + sub) |
| `7/8` | `x - (x >> 3)` | 24 cycles |
| `5/8` | `(x >> 1) + (x >> 3)` | 28 cycles |

Encode bands' factors as `(shift1, shift2, op)` byte triples in ROM data; runtime decodes via `asr.w Dn,Dm` with the shift count in a data register. A sentinel value (e.g., `shift1=15`) means "factor = 0" (locked). For arbitrary fractions outside this set (e.g., `2/3`), build a lookup table at compile time — never `mulu` for fractional scaling.

### 2.2 Branching

- **Fall-through for the common case.** The 68000 has no branch predictor — taken branches cost 10 cycles, not-taken costs 8. Put the likely path as fall-through.
- **`.s` branches when in range.** `bra.s` = 10 cycles, `bra.w` = 10 cycles but 2 bytes larger. Always use `.s` for local labels within the same routine.
- **`dbf` for counted loops.** `dbf` = 10 cycles (taken) / 14 cycles (exit). Cheaper than `subq + bne`.

### 2.3 Register Usage

- **All hot variables in registers.** In inner loops (sprite rendering, object iteration, DMA drain), every accessed value must be in a register. Zero RAM round-trips.
- **`moveq` for constants -128 to 127.** 4 cycles vs `move.l #imm, Dn` at 12 cycles.
- **`addq`/`subq` for 1-8.** 4 cycles on Dn, 8 on An. vs `add.w #imm` at 8+ cycles.
- **`lea` for address math.** `lea $10(a0), a1` = 8 cycles. `movea.l a0, a1; adda.w #$10, a1` = 12 cycles.

### 2.4 Memory Access

- **PC-relative for ROM reads.** `move.w Table(pc), d0` saves 2 bytes and 4 cycles vs absolute. Use for all ROM data within ±32KB. Batman & Robin uses 986 PC-relative references.
- **Word-align everything.** The 68000 bus is 16-bit. Unaligned word/long access causes an address error (crash). Use `even` after any byte data.
- **Prefer `(a0)+` post-increment.** Sequential reads with `(a0)+` are the fastest access pattern — 0 extra cycles vs base addressing.
- **Avoid `(d0.w, a0)` in tight loops.** Indexed addressing = 10 extra cycles. Pre-compute the effective address with `lea` outside the loop.

### 2.5 Instruction Selection

| Instead of | Use | Why |
|---|---|---|
| `move.w #0, d0` | `moveq #0, d0` or `clr.w d0` | Smaller, faster |
| `cmp.w #0, d0` | `tst.w d0` | 4 cycles shorter |
| `move.l a0, a1` | `movea.l a0, a1` | Same encoding, clearer intent |
| `and.w #$FF, d0` | `andi.w #$FF, d0` | (identical, but be consistent) |
| `add.w #1, d0` | `addq.w #1, d0` | 4 cycles saved |
| `sub.w d0, d0` | `moveq #0, d0` or `clr.w d0` | Clearer |
| `swap d0; clr.w d0` | `clr.l d0` (if upper word not needed) | Simpler |
| `lsl.w #1, d0` | `add.w d0, d0` | 2 cycles faster |
| `subq + bne` loop | `dbf` loop | 2 cycles/iteration saved |
| `clr.l (a0)` (read-modify-write) | `moveq #0,d0; move.l d0,(a0)` | Avoids spurious read cycle |

### 2.6 Advanced 68000 Techniques

**Branchless conditional via Scc:** `Scc Dn` sets a byte to $FF or $00 based on condition codes. Follow with `ext.w`/`ext.l` to create a full bitmask, then AND/OR to conditionally apply a value. Avoids branch penalty (10 cycles taken, 8 not-taken). Example: `slt d1; ext.w d1; and.w d1,d0` zeroes d0 if d0 was negative, preserves it otherwise.

**MOVEP for interleaved byte access:** `movep.w d0, 0(a0)` writes the high byte to `(a0)` and low byte to `(a0+2)`, skipping alternate bytes. Useful for palette fade operations (modify every other byte of CRAM words), VDP register shadow updates, and any case where data is interleaved at even/odd offsets. Amiga demoscene staple, rarely seen in Genesis code.

**Self-modifying immediates:** The 68000 has no instruction cache. Patching immediate values in instruction streams (e.g., writing a new value into the `#xxxx` field of a `move.w #xxxx,d0`) is safe and eliminates a memory load. Useful for per-frame constants like scroll base offsets, palette indices, or tile base addresses that change once per frame but are read many times. Cost: one `move.w` to patch vs one `move.w (a0),d0` per read — same speed but removes the pointer setup.

**Word-align hot branch targets:** The 68000 fetches 16-bit words. Branch targets on odd word boundaries cost a wasted prefetch. Use `even` or `align 2` before frequently-hit labels — especially loop tops and hot-path branch destinations. Saves 4 cycles on taken branches to misaligned targets.

**LEA displacement chaining:** Instead of multiple `adda` operations, chain `lea`: `lea 8(a0),a1` then `lea 12(a1),a2`. LEA sets up the effective address in the calculation stage while ADDA stalls on the address bus. Useful when computing multiple derived pointers from a base.

**SWAP as free register:** `swap d2` stashes the lower word in the upper half, freeing the lower word for subroutine use. `swap d2` after the call restores it. Cost: 4 cycles per swap (8 total) vs 32+36=68 cycles for a `movem.l` save/restore pair with 3 registers. Use this when you need to preserve exactly one data register across a call and have no other use for its upper word. From Gunstar Heroes — used pervasively in their sprite renderer.

```asm
; Instead of:
        movem.l d4, -(sp)          ; 16 cycles
        jsr     SomeRoutine
        movem.l (sp)+, d4          ; 16 cycles  (32 total)

; Use:
        swap    d4                  ; 4 cycles
        jsr     SomeRoutine         ; (clobbers d4.w but upper word is safe)
        swap    d4                  ; 4 cycles   (8 total, saves 24 cycles)
```

**SWAP for 16.16 fixed-point extraction:** After a 32-bit fixed-point add, `swap` brings the integer part into the low word without a shift or divide. From Gunstar Heroes' physics engine.

```asm
; Extract integer pixel delta from 16.16 fixed-point:
        add.l   d0, d1              ; full 32-bit position += velocity
        swap    d0                  ; integer part of velocity now in d0.w
        swap    d1                  ; integer part of position now in d1.w
        sub.w   d0, d1              ; pixel delta = new_int - vel_int
```

**Hybrid SoA for batch operations:** When batch-processing a single field across all objects (e.g., culling by X position, updating all Y velocities), struct-of-arrays layout enables sequential `(a0)+` access instead of strided `offset(a0)` with stride advances. The 68000 has no cache, but sequential access eliminates offset encoding (2 bytes saved per access) and enables MOVEM batch loads. Use SoA for hot-path batch fields (x_pos, y_pos, render_flags) alongside AoS for per-object logic.

**Exponential lerp via shift:** Smooth transitions without keeping a frame counter or interpolation table. Each frame, advance `current` toward `target` by a power-of-2 fraction:

```asm
; current += (target - current) >> N
        move.w  Current(a0), d0
        sub.w   d0, d_target              ; delta
        asr.w   #LERP_SHIFT, d_target     ; >> N
        add.w   d_target, d0
        move.w  d0, Current(a0)
```

Convergence vs frame count (assuming target stays fixed):

| Shift `N` | Frames to ~95% | Frames to ~99% | Use case |
|---|---|---|---|
| 2 | ~4 | ~6 | Snappy (UI, hit-stop recovery) |
| 3 | ~8 | ~13 | Camera, parallax transitions |
| 4 | ~16 | ~26 | Audio fade, palette crossfade |
| 5 | ~32 | ~52 | Gentle environmental drift |

Cost: ~6 cycles per value. Idempotent — safe to run when already converged (delta = 0 → no-op). Works for any signed value. Use this everywhere a transition needs to feel smooth: camera lookahead pan, parallax factor changes across section boundaries, palette fade, audio gain ramps, animation easing. Avoid frame-counter-driven lerps (`current = lerp(start, end, frame/N)`) — they require state and a multiply, this requires neither.

### 2.7 Loop Patterns

```asm
; BEST — dbf with post-increment reads
        moveq   #COUNT-1, d7
.loop:
        move.w  (a0)+, (a1)+
        dbf     d7, .loop

; GOOD — unrolled for small known counts
        move.l  (a0)+, (a1)+    ; 4 iterations unrolled
        move.l  (a0)+, (a1)+    ; saves 4x dbf overhead (40 cycles)
        move.l  (a0)+, (a1)+
        move.l  (a0)+, (a1)+

; BAD — indexed access in loop
.loop:
        move.w  (a0, d0.w), d1  ; 10 extra cycles per iteration!
        addq.w  #2, d0
        dbf     d7, .loop
```

### 2.8 Subroutine Discipline

- **`bsr.s` / `bsr.w`** — always sized. `bsr.s` when the target is within the same file/nearby.
- **Keep hot routines short.** If a routine is called per-object per-frame, it should fit in ~50 instructions. Large routines should be split into inlined fast-path + called slow-path.
- **Leaf routines don't need `movem`.** If a routine doesn't call other routines, don't save/restore registers — just document which registers it clobbers. The caller manages its own register state.
- **Document register clobber.** Every routine header states inputs, outputs, and clobbered registers.
- **Tail calls.** When the last instruction before `rts` is `jsr Target`, replace with `jmp Target`. Saves 10 cycles and 4 bytes by eliminating the `jsr`/`rts` pair overhead.

```asm
; -----------------------------------------------
; Get_Collision_Type
; In:  d0.w = X position (section-local)
;      d1.w = Y position (section-local)
;      a0   = collision map base
; Out: d0.b = collision type
; Clobbers: d1
; -----------------------------------------------
Get_Collision_Type:
        lsr.w   #4, d0
        lsr.w   #4, d1
        lsl.w   #7, d1
        add.w   d0, d1
        move.b  (a0, d1.w), d0
        rts
```

---

## 3. VDP & Hardware Discipline

### 3.1 VDP Access Rules

1. **Never write to VDP data/control ports during active display** — except for intentional raster effects (HBlank palette swaps, VSRAM manipulation).
2. **All tile/palette/scroll updates go through the DMA queue or deferred plane buffer.** No direct VDP writes from the game loop.
3. **`stopZ80` before ANY VDP access.** The Z80 shares the bus. Failing to stop it risks data corruption. Always pair with `startZ80`.
4. **VDP register writes use cached values.** Store a copy of each register in RAM so code can read back register state (VDP registers are write-only hardware).
5. **Settled state goes through `setVDPReg`; transient goes direct.** Persistent frame state on registers `$00-$12` (display enable, scroll mode, plane base, palette base, etc.) MUST use `setVDPReg` so the shadow stays in sync and `Flush_VDP_Shadow` writes the right value next VBlank. Transient register writes are legitimate ONLY for: (a) pre-DMA autoincrement (`$0F`) setup that the caller controls, (b) HInt-handler raster effects during active scan that do NOT touch the shadow. Anything else direct-writing `$00-$12` is a bug — `Flush_VDP_Shadow` will overwrite hardware with the stale shadow value the next time that register's dirty bit is set. See `ENGINE_ARCHITECTURE.md` §0.4 for the full convention.

### 3.2 DMA Safety

- Set VDP auto-increment (`$8F02`) BEFORE every DMA operation.
- Never cross a 128KB ROM boundary in a single DMA source address.
- Check DMA busy bit before starting a new DMA (real hardware can drop commands).
- Verify source address is even (odd source = address error on real hardware).

### 3.3 VBlank Budget

NTSC VBlank = ~4,300 68K cycles. Everything that touches the VDP must finish within this window:

| Operation | Typical Cost | Priority |
|---|---|---|
| Palette DMA | ~80 cycles + 128 bytes DMA | Critical — always |
| Sprite table DMA | ~80 cycles + 640 bytes DMA | Critical — always |
| HScroll DMA | ~80 cycles + variable DMA | Critical — always |
| Plane buffer flush | ~200-800 cycles (CPU writes) | Critical — always |
| Art streaming DMA | Variable | Deferrable — skip on lag |

**Rule:** Critical operations get unrolled/pre-computed drain. Deferrable operations use linear loop drain and are skipped when the frame budget is tight.

### 3.4 VBlank Step Ordering — Data Before State

When a frame's display depends on **both** VRAM data (HScroll table, tile art, sprite table) **and** VDP state writes (VSRAM, register changes), the data must be DMA'd before the state is written. The VDP latches scroll/state registers per scanline; if VSRAM changes before HScroll-table DMA completes, scanline 1 reads stale HScroll values against new VSRAM, producing a one-frame tear.

**Required VBlank order:**

```
1. stopZ80
2. Flush_VDP_Shadow              ; register changes go through shadow first
3. Enqueue_Dirty_Buffers         ; queue palette + sprite + HScroll DMAs
4. VInt_DrawLevel                ; plane buffer drain (VRAM nametable writes)
5. Process_DMA_Critical          ; drain queued DMAs — palette, sprites, HScroll
6. VSRAM writes                  ; whole-plane Vscroll OR per-column buffer
7. Process_DMA_Important / Deferrable
8. startZ80
```

**Hard rule:** Any new VBlank work must respect: VRAM data → state-register writes → less-critical DMAs. Don't write VSRAM at the top of the handler "because it's quick" — it has to come after HScroll DMA finishes. Source: SpritesMind t=1482 documents this exact one-frame tear bug.

This applies to any pair of (data, state) that are both consumed mid-scanline. New entries to think about: palette CRAM writes during a S/H mode toggle, font tile DMA before VSRAM column changes, etc. When in doubt, DMA first.

---

## 4. Naming Conventions

### 4.1 Label Types

| Type | Style | Examples |
|---|---|---|
| Routines | `PascalCase_Underscored` | `VDP_Init`, `DMA_Queue_Process`, `Object_Load` |
| RAM variables | `PascalCase_Underscored` | `Camera_X_Pos`, `Player_State`, `V_Int_Flag` |
| ROM constants | `ALL_CAPS_UNDERSCORED` | `MAX_OBJECTS`, `VRAM_POOL_SIZE`, `SEC_ENTRY_SIZE` |
| Local labels | `.lowercase_dotted` | `.loop`, `.skip`, `.done`, `.return`, `.not_found` |
| Struct fields | `lowercase_underscored` | `x_pos`, `art_tile`, `render_flags`, `code_addr` |
| AS functions | `camelCase` | `vdpComm`, `vram_art`, `sprSize`, `secIndex` |
| AS macros | `camelCase` | `stopZ80`, `setVDPReg`, `queueStaticDMA`, `ifdebug` |
| Enum values | `ALL_CAPS` with prefix | `STATE_IDLE`, `STATE_RUNNING`, `FLAG_ON_SCREEN` |
| SST custom overlays | `_lowercase_underscored` | `_dplc_ptr`, `_patrol_left`, `_art_base` |
| Overlay var structs | `<Object>V` PascalCase | `TEnemyV`, `TPlayerV`, `DplcV` (shared) |

SST custom field overlays use a leading underscore to distinguish them from global labels. Each object defines a `<Object>V` struct for its layout (assembler computes offsets), follows it with `objvarsCheck <Object>V_len` (build-aborts on sst_custom overflow), and derives the underscore accessors from struct fields: `_patrol_left = SST_sst_custom+TEnemyV_patrol_left`. Raw `= SST_sst_custom + N` arithmetic is banned. When multiple objects share the same custom layout, guard the whole block (struct + check + equates) with `ifndef` in EVERY file that uses it so include order doesn't matter.

### 4.2 Routine Naming

Routines are named as `System_Action` or `System_Action_Detail`:

```asm
VDP_Init                ; system = VDP, action = init
DMA_Queue_Add           ; system = DMA queue, action = add entry
Object_Load             ; system = objects, action = load
Object_Load_Child       ; system = objects, action = load, detail = child
Collision_Get_Floor     ; system = collision, action = get floor height
Section_Preload_Art     ; system = section, action = preload art
```

### 4.3 Descriptive Labels

Every label must describe what the code DOES, not where it IS. No `loc_`, `sub_`, `byte_`, `word_`, `unk_` labels. If you don't know what something does, investigate until you do, then name it.

---

## 5. Code Organization

### 5.1 File Structure

One logical unit per file. A file should contain one routine and its helpers, or one data table and its accessors.

```
s4_engine/
  main.asm              ; entry point, includes everything
  constants.asm         ; all ROM constants and enums
  macros.asm            ; all macros and AS functions
  ram.asm               ; RAM layout via phase/dephase
  structs.asm           ; all struct definitions (OBJ, SEC, DMA, etc.)
  
  engine/
    vdp_init.asm        ; VDP register setup
    dma_queue.asm       ; DMA queue system
    sprites.asm         ; sprite rendering (build_sprites + render)
    plane_buffer.asm    ; deferred plane buffer
    vblank.asm          ; VBlank handler and frame loop
    hblank.asm          ; HBlank handler (RAM-patched)
    controllers.asm     ; joypad reading (3-button + 6-button)
    
  objects/
    object_core.asm     ; Object_Load, Object_Delete, RunObjects
    object_draw.asm     ; Draw_Sprite, Render_Sprites
    object_collision.asm; collision_response dispatch
    
  level/
    section_grid.asm    ; section streaming, preload, teleport
    camera.asm          ; camera system
    collision_map.asm   ; per-section collision lookup
    parallax.asm        ; 8-layer computed parallax
    
  player/
    player_common.asm   ; shared movement, collision, hurt
    sonic.asm           ; Sonic-specific code
    tails.asm
    knuckles.asm
    
  vram/
    allocator.asm       ; dynamic VRAM allocator
    art_loading.asm     ; S4LZ/UFTC decompression integration
    
  effects/
    palette.asm         ; fade, crossfade, cycling, water
    deformation.asm     ; scroll deformation tables
    effects_engine.asm  ; effect sequencer
    
  screens/
    game_modes.asm      ; mode dispatcher
    title.asm
    level_select.asm
    
  sound/
    flamedriver.asm     ; Z80 sound driver (BINCLUDE or inline)
    sound_commands.asm  ; 68K side: play/stop/fade API
    
  debug/
    error_handler.asm   ; MD Debugger integration
    assertions.asm      ; per-subsystem debug checks
    profiler.asm        ; raster bars, lagometer
    
  data/
    art/                ; compressed art files
    mappings/           ; sprite mappings (VDP-order format)
    palettes/           ; raw 128-byte palette files
    levels/             ; section data, collision maps, nametable strips
    sound/              ; music, SFX, DAC samples
```

### 5.2 File Header

Every `.asm` file starts with a one-line description. No multi-line headers, no ASCII art, no changelog.

```asm
; DMA queue — 3-priority sub-queue system with hybrid drain
```

### 5.3 Routine Header

Every public routine has a register contract. Local helpers (`.prefixed`) don't need one unless the contract is non-obvious.

```asm
; -----------------------------------------------
; DMA_Queue_Add — Enqueue a DMA transfer
; In:  d0.l = source address (68K, even)
;      d1.w = destination (VRAM/CRAM/VSRAM word address)
;      d2.w = length in bytes (even, non-zero)
;      d3.w = priority (0=critical, 1=important, 2=deferrable)
; Out: none
; Clobbers: d0-d3, a1
; -----------------------------------------------
```

### 5.4 No Comments Unless Non-Obvious

Default: no comments. Code should be self-documenting through naming.

```asm
; BAD — restating what the code does
        moveq   #0, d0          ; clear d0
        move.w  (a0)+, d1       ; read next word
        addq.w  #1, d2          ; increment counter

; GOOD — explaining WHY
        moveq   #0, d0          ; high word must be clear for divu below
        
; GOOD — documenting a hardware constraint
        nop                     ; TH transition needs 8-cycle settling time
```

---

## 6. Data Format Standards

### 6.1 Alignment

- Word-align ALL word and long data. Use `even` after any byte sequence.
- Long-align data that will be accessed with `move.l` in tight loops.
- Tables indexed by shift or multiply must be at addresses the indexing can reach.

### 6.2 Table Design

- Entry sizes should be powers of 2 (2, 4, 8, 16, 32, 64 bytes) so indexing uses shifts instead of multiply.
- Include a count word or terminator — never rely on external knowledge of table size.
- Document entry format at the table definition.

```asm
; Section object layout — 4 bytes per entry, count header
Section_0_0_Objects:
        dc.w    3                       ; object count
        ; format: type.b, subtype.b, x_pos.w (section-local)
        dc.b    OBJ_SPRING, $00
        dc.w    $0340
        dc.b    OBJ_RING_LINE, $05
        dc.w    $0180
        dc.b    OBJ_BADNIK, $02
        dc.w    $0600
        even
```

### 6.3 ROM Data Ordering

Group data by access pattern, not by type:
- Section data (layout + objects + rings + collision + art) grouped per-section, not all layouts then all objects then all rings.
- Frequently co-accessed data adjacent in ROM for bus prefetch benefit.

---

## 7. Design Principles — Modern Thinking on Retro Hardware

### 7.1 Build-Time Over Runtime

Every computation that CAN happen at build time MUST happen at build time. The 68000 gets 7.67 million cycles per second. The build PC gets billions. Use the build PC.

- Nametable strips: pre-computed, not chunk→block→tile at runtime
- VRAM tile indices: graph-colored at build time, not allocated at runtime
- Collision maps: flattened at build time, not chunk→block→collision at runtime
- Sine tables: computed by AS, not stored as opaque binaries
- Lookup tables: generated by macros/functions, not hand-typed

### 7.2 Zero-Copy Data Paths

Data should flow from ROM to hardware with minimal CPU intermediary:

```
ROM → DMA → VRAM    (nametable strips, tile art)
ROM → DMA → CRAM    (palettes)
ROM → RAM buffer → DMA → VRAM    (deferred plane buffer — one copy)
```

Never: ROM → RAM → process → RAM → DMA → VRAM (two copies + processing). If the data needs processing, do it at build time.

### 7.3 Amortized Work

Spread expensive operations across frames. Never do all work on the transition frame.

- S4LZ decompression: streaming across ~16 frames
- Nametable preload: progressive DMA during preload window
- Palette fade: interpolated over ~16 frames
- Object preloading: spread across preload window

### 7.4 Lazy Evaluation

Don't do work until you need the result.

- VRAM lazy reclaim: freed art stays until pool needs space
- Dirty flags: only DMA sprite table / hscroll buffer if changed
- Deferred plane buffer: only flush tiles that actually scrolled
- Conditional sound updates: only process if sound state changed

### 7.5 Data-Oriented Layout

Organize data by access pattern, not by logical grouping. The 68000 has no data cache, but sequential bus access is still faster than random access due to bus arbitration.

- Object SST: hot fields (position, velocity, state) first, cold fields (mappings, art metadata) after
- Sprite rendering: priority-band lists so rendering traverses objects in draw order
- Section data: co-locate all data for one section (nametable + collision + palette + objects)

### 7.6 Event-Driven Over Polling

Where possible, use dirty flags and state change detection instead of checking every value every frame.

```asm
; POLLING (wasteful) — check HUD values every frame
        move.w  Ring_Count, d0
        cmp.w   HUD_Ring_Display, d0
        beq.s   .no_change
        ; update HUD...
.no_change:

; EVENT-DRIVEN (efficient) — set flag when value changes
; In ring collection code:
        addq.w  #1, Ring_Count
        st      HUD_Dirty_Rings         ; flag that HUD needs update
; In HUD update:
        tst.b   HUD_Dirty_Rings
        beq.s   .skip_rings
        sf      HUD_Dirty_Rings
        ; update HUD...
.skip_rings:
```

### 7.7 Fail at Build Time, Not Runtime

Every assumption should be checked at build time. Runtime assertion checks (debug mode) catch what build time can't. Silent runtime failure is never acceptable.

Priority order:
1. AS `error` / `warning` at build time (cheapest — ROM won't even build)
2. Debug `RaiseError` at runtime in debug builds (catches dynamic errors)
3. `CHK` instruction bounds checking in debug builds (auto-triggers exception)
4. Never: silent corruption, mystery crashes, "it works if you don't do X"

### 7.8 No Unshifted Absolute Coordinates in Object State

**No unshifted absolute coordinates in object state.** Teleport rebases shift
`SST_x_pos`/`SST_y_pos` for every slot-tagged object but cannot see absolute
world coordinates stored in `sst_custom` (patrol anchors, waypoint targets,
"return home" positions) — those go stale by ±SECTION_SHIFT at a seam and the
object lurches. Keep positional state relative (offsets, counters, velocities)
or re-derivable from the ROM placement. An object that genuinely needs a stored
absolute coordinate must register it for teleport shifting (design the mechanism
when the need first arises — likely a per-ObjDef shift mask of custom longwords).

---

## 8. Performance Measurement

### 8.1 Know Your Budget

| Resource | Budget | How to Measure |
|---|---|---|
| Frame CPU | ~120,000 cycles (NTSC) | Raster bar profiler |
| VBlank CPU | ~4,300 cycles | Window plane lagometer |
| VBlank DMA | ~7.5 KB | DMA byte counter |
| VRAM tiles | 1,536 (unified pool) | Build tool report |
| RAM | 65,536 bytes | `phase`/`dephase` overflow check |
| Sprites/frame | 80 | Sprite counter in debug overlay |
| Sprites/line | 20 | Visual inspection (flicker = overflow) |

### 8.2 Optimization Order

1. **Don't optimize until you measure.** Raster bars and the lagometer show where time is spent.
2. **Algorithmic first.** O(1) allocation beats an optimized O(n) scan. Lookup tables beat optimized multiplication.
3. **Data layout second.** Sequential access beats random. Co-located data beats scattered.
4. **Instruction-level last.** `moveq` vs `move.l` matters, but only after the algorithm and data layout are right.

---

## 9. Source Control

- **Commit after every working milestone.** Not "end of session" — after each routine that assembles and runs.
- **Commit message describes the system, not the files.** "Implement DMA queue with 3-priority drain" not "Add dma_queue.asm"
- **Never commit broken code to main.** Use branches for work-in-progress.
- **Tag milestones.** When a major system is complete and tested, tag it: `v0.1-vdp-init`, `v0.2-dma-queue`, etc.
