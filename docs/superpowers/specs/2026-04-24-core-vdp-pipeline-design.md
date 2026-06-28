# §1 Core VDP Pipeline — Design Spec

**Date:** 2026-04-24
**Scope:** DMA queue infrastructure, VBlank restructuring, RAM buffers with dirty flags, utility macros, PlaneMapToVRAM, verification test.
**Dependencies:** §0 (Hardware Init & Boot) — complete.
**Deferred:** Sprite rendering (needs §3), plane streaming (needs §4), DPLC lookahead (needs §3), adaptive budget (needs real workloads), variable hscroll DMA (needs §4), background work (needs §9.7). See `docs/DEFERRED_WORK.md`.

---

## 1. DMA Queue System

### 1.1 RAM Layout

Three contiguous priority sub-queues in RAM. Each entry is 14 bytes (Flamewing Ultra DMA Queue format).

```
DMA_Queue:
  Critical:   8 slots ×  14 bytes =  112 bytes
  Important: 12 slots ×  14 bytes =  168 bytes
  Deferrable: 12 slots × 14 bytes =  168 bytes
                           Total  =  448 bytes

DMA_Queue_Slots:
  DMA_Critical_Slot:   ds.w 1    ; pointer to next free Critical slot
  DMA_Important_Slot:  ds.w 1    ; pointer to next free Important slot
  DMA_Deferrable_Slot: ds.w 1    ; pointer to next free Deferrable slot
                         Total = 6 bytes
```

Per-queue slot pointer is a word containing the RAM address of the next free entry. When slot pointer equals the queue end address, the queue is full.

### 1.2 Entry Format (14 bytes)

Flamewing's interleaved format. VDP register numbers at even offsets, data at odd offsets. Pre-initialized at startup so enqueue only writes data bytes.

```
Offset  Field      Purpose
  +0    $94        VDP reg marker (pre-initialized)
  +1    SizeH      DMA length high byte
  +2    $93        VDP reg marker (pre-initialized)
  +3    SizeL      DMA length low byte
  +4    $97        VDP reg marker (pre-initialized)
  +5    SrcH       Source address high byte (word address, bit 23 cleared)
  +6    $96        VDP reg marker (pre-initialized)
  +7    SrcM       Source address mid byte
  +8    $95        VDP reg marker (pre-initialized)
  +9    SrcL       Source address low byte
  +10   CmdHi      VDP command high word (destination + DMA trigger)
  +11   CmdLo      VDP command low word
```

Struct definition:

```asm
DMAEntry struct
Reg94           ds.b 1
SizeH           ds.b 1
Reg93           ds.b 1
SizeL           ds.b 1
Reg97           ds.b 1
SrcH            ds.b 1
Reg96           ds.b 1
SrcM            ds.b 1
Reg95           ds.b 1
SrcL            ds.b 1
Command         ds.l 1
DMAEntry endstruct
; DMAEntry_len = 14
```

### 1.3 Init_DMA_Queue

Run once at startup. Pre-fills all 32 slots with VDP register numbers ($93-$97) at the marker positions using `movep.l`. Sets all three slot pointers to their respective queue start addresses.

```asm
; For each slot:
;   move.b  #$94, DMAEntry_Reg94(a0)
;   movep.l #$93979695, DMAEntry_Reg93(a0)   ; writes $93, $97, $96, $95 to odd offsets
```

Uses `rept` to unroll across all slots at assembly time. One-time cost, no runtime overhead.

### 1.4 QueueDMATransfer

Full enqueue routine for dynamic transfers. Used for art streaming, animated tiles, and any transfer with runtime-determined parameters.

**Input:** d1.l = source address (bytes), d2.w = VRAM destination, d3.w = transfer length (bytes). An additional parameter selects the target sub-queue (Critical/Important/Deferrable).

**Algorithm:**
1. `move.w sr, -(sp)` / `disableInts` — SR masking for VInt safety (46 cycles)
2. Load slot pointer for the target queue
3. Compare against queue end — if full, restore SR + return failure
4. Critical queue: `trap` assertion in debug builds if full (Critical overflow = design bug)
5. Convert source to word address: `lsr.l #1, d1`
6. Clear bit 23 for RAM source safety: `bclr.l #23, d1`
7. Write source bytes via `movep.l d1, DMAEntry_SrcH(a1)` (interleaved into marker positions)
8. Convert length to words: `lsr.w #1, d3`
9. Check 128KB boundary: `moveq #0, d0; sub.w d3, d0; sub.w d1, d0; blo.s .split`
10. Write length via `movep.w d3, DMAEntry_SizeH(a1)`
11. Build VDP command from d2 via `vdpCommReg` bit manipulation
12. Write command longword: `move.l d0, DMAEntry_Command(a1)`
13. Advance slot pointer: `adda.w #DMAEntry_len, a1` / store back
14. Debug: `add.w d3, (DMA_Bytes_ThisFrame).w` (behind ifdebug)
15. `move.w (sp)+, sr` — restore interrupts

**128KB boundary split:** If detected, enqueue two entries — first for bytes up to boundary, second for remainder. Check queue capacity for the second entry before splitting.

**Cycle cost:** ~184 cycles normal, ~338 cycles with boundary split. 48 cycles if queue full (early exit).

### 1.5 QueueStaticDMA Macro

Inline block-copy for pre-computed entries. Used for fixed transfers (sprite table, individual palette lines).

```asm
QueueStaticDMA macro queue_slot, queue_end, source_entry
    movea.w (queue_slot).w, a1
    cmpa.w  #queue_end, a1
    beq.s   .full\@
    ; ifdebug: trap if Critical queue full
    lea     (source_entry).w, a2
    move.l  (a2)+, (a1)+               ; bytes 0-3
    move.l  (a2)+, (a1)+               ; bytes 4-7
    move.l  (a2)+, (a1)+               ; bytes 8-11
    move.w  (a2)+, (a1)+               ; bytes 12-13
    move.w  a1, (queue_slot).w
.full\@:
    endm
```

~52 cycles inlined (4× faster than QueueDMATransfer). No address conversion, no safety checks — the entry is known-correct at build time. Uses a2 as scratch (callers must not rely on a2 across the macro).

Pre-computed entries stored in RAM, built once at init by `BuildStaticDMA`.

### 1.6 Drain Routines

**Critical queue — jump-table unrolled:**

Queue slot pointer doubles as a jump offset into fully unrolled `move.l (a1)+, (a5)` sequences. Each entry drains as 3 longword writes + 1 word write to VDP control port. Zero branches, zero comparisons. ~64 cycles per entry, ~514 cycles for all 8 entries.

Jump table structure (ported from S.C.E. `Process_DMA_Queue`):
```asm
Process_DMA_Critical:
    movea.w (DMA_Critical_Slot).w, a1
    jmp     .jump_table - DMA_Critical(a1)

.jump_table:
    bra.w   .done           ; 0 entries
    ; ... unrolled entries via rept ...

.done:
    move.w  #DMA_Critical, (DMA_Critical_Slot).w    ; reset slot pointer
    rts
```

**Important + Deferrable — looped with byte budget:**

```asm
Process_DMA_Budgeted:
    lea     (VDP_CTRL).l, a5
    movea.w (queue_slot).w, a1
    lea     (queue_start).w, a0
    cmpa.l  a0, a1
    bls.s   .done
.loop:
    ; Check byte budget before draining
    move.w  (DMA_Budget_Remaining).w, d0
    ble.s   .done
    ; Read length from entry, subtract from budget
    move.b  DMAEntry_SizeH(a0), d1
    lsl.w   #8, d1
    move.b  DMAEntry_SizeL(a0), d1
    add.w   d1, d1              ; words to bytes
    sub.w   d1, (DMA_Budget_Remaining).w
    ; Drain entry
    move.l  (a0)+, (a5)         ; length regs
    move.l  (a0)+, (a5)         ; source regs
    move.l  (a0)+, (a5)         ; source low + cmd high
    move.w  (a0)+, (a5)         ; cmd low — triggers DMA
    cmpa.l  a0, a1
    bhi.s   .loop
.done:
    move.w  #queue_start, (queue_slot).w
    rts
```

~78 cycles per entry (14 cycles loop overhead). Budget check adds ~20 cycles per entry.

### 1.7 Debug Profiling Counters

All behind `ifdebug` guards. Zero code/RAM in release builds.

```
DMA_Bytes_ThisFrame:    ds.w 1    ; total bytes enqueued this frame
DMA_Peak_Critical:      ds.w 1    ; high-water mark (slot offset from base)
DMA_Peak_Important:     ds.w 1
DMA_Peak_Deferrable:    ds.w 1
DMA_Overflow_Count:     ds.w 1    ; enqueue rejections (queue full)
Lag_Frame_Count:        ds.l 1    ; VBlank overruns
```

`DMA_Bytes_ThisFrame` reset to zero each frame in VBlank. Peak values only increase (track worst case across gameplay). Readable via Exodus MCP `emulator_read_memory`.

---

## 2. VBlank Restructuring

### 2.1 Function Pointer Dispatch

Replace the current fixed VBlank handler with a function pointer in RAM:

```
VInt_Ptr:  ds.l 1    ; pointer to current VBlank handler
```

The VBlank entry point reads and calls through this pointer:

```asm
VBlank_Handler:
    movem.l d0-a6, -(sp)
    tst.b   (VBlank_Ready).w
    beq.s   .lag
    movea.l (VInt_Ptr).w, a0
    jsr     (a0)
    bra.s   .done
.lag:
    jsr     VInt_Lag(pc)
.done:
    clr.b   (VBlank_Ready).w
    movem.l (sp)+, d0-a6
    rte
```

### 2.2 Lag Frame Detection

**Mechanism:** The main game loop sets `VBlank_Ready` to 1 after completing a frame's work. VBlank checks this flag:
- If set → normal frame, call `VInt_Ptr` handler, clear flag
- If clear → lag frame (main loop didn't finish in time), call `VInt_Lag`

Replaces the current `VBlank_Flag` with a two-flag system:
- `VBlank_Ready`: set by main loop when frame work is done, cleared by VBlank
- `VBlank_Flag`: set by VBlank to signal main loop that VSync occurred, cleared by `VSync_Wait`

### 2.3 VInt_Level — Full Pipeline Handler

Execution order (each step independently skippable):

```
Step  System                           Timing
────────────────────────────────────────────────
 1    Flush_VDP_Shadow (dirty regs)    ~50-200 cycles (0-3 regs typical)
 2    VSRAM direct write               ~32 cycles
 3    Enqueue dirty palette lines       ~32-128 cycles (0-4 lines)
 4    Enqueue sprite table (if dirty)   ~32 cycles
 5    Drain Critical DMA queue          ~514 cycles max (unrolled)
 6    Set DMA budget for frame          ~20 cycles
 7    Drain Important DMA queue         ~932 cycles max (budget-gated)
 8    Drain Deferrable DMA queue        ~932 cycles max (budget-gated)
 9    Read controllers                  ~200 cycles (existing code)
10    Increment frame counter           ~8 cycles
11    Set VBlank_Flag                   ~8 cycles
12    Sound driver call (stub)          ~0 cycles (future)
```

Steps 1-5 are the visual-stability core — they must complete every frame. Steps 6-8 are budget-gated and can be partially skipped. Steps 9-12 are housekeeping.

The dirty-flag enqueue (steps 3-4) happens BEFORE the drain (step 5) so that this frame's dirty buffers are included in this frame's DMA.

### 2.4 VInt_Lag — Minimal Handler

Only runs when the main loop didn't finish in time:

```
 1    Flush_VDP_Shadow (dirty regs only)
 2    VSRAM direct write
 3    Enqueue dirty palette lines
 4    Enqueue sprite table (if dirty)
 5    Drain Critical DMA queue ONLY
 6    Read controllers
 7    Set VBlank_Flag
 8    Increment Lag_Frame_Count (debug)
```

Important and Deferrable queues are NOT drained. Their entries persist until the next normal frame.

### 2.5 VSync_Wait Update

The existing `VSync_Wait` loop becomes:

```asm
VSync_Wait:
    move.b  #1, (VBlank_Ready).w    ; signal: main loop is done
.wait:
    tst.b   (VBlank_Flag).w
    beq.s   .wait
    clr.b   (VBlank_Flag).w
    ; ifdebug: clear DMA_Bytes_ThisFrame
    rts
```

---

## 3. RAM Buffers and Dirty Flags

### 3.1 Palette Buffer

```
Palette_Buffer:     ds.b 128    ; 4 lines × 32 bytes (16 colors × 2 bytes/color)
Palette_Dirty:      ds.b 1      ; bits 0-3 = dirty flags per palette line
```

Palette line mapping:
- Bit 0 / Line 0 ($00-$1F): Background / environment
- Bit 1 / Line 1 ($20-$3F): Player character
- Bit 2 / Line 2 ($40-$5F): Objects
- Bit 3 / Line 3 ($60-$7F): Effects / water / fade

**Static DMA entries:** Four 14-byte pre-computed entries stored in RAM, built once at init:

```
Static_Pal_Line0:   ds.b DMAEntry_len   ; Palette_Buffer+$00 → CRAM $0000, 32 bytes
Static_Pal_Line1:   ds.b DMAEntry_len   ; Palette_Buffer+$20 → CRAM $0020, 32 bytes
Static_Pal_Line2:   ds.b DMAEntry_len   ; Palette_Buffer+$40 → CRAM $0040, 32 bytes
Static_Pal_Line3:   ds.b DMAEntry_len   ; Palette_Buffer+$60 → CRAM $0060, 32 bytes
```

VBlank enqueue logic (in VInt_Level step 3):
```asm
    move.b  (Palette_Dirty).w, d0
    beq.s   .no_pal                     ; fast path: nothing dirty
    btst    #0, d0
    beq.s   .skip0
    QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line0
.skip0:
    btst    #1, d0
    beq.s   .skip1
    QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line1
.skip1:
    ; ... same for bits 2, 3
    clr.b   (Palette_Dirty).w
.no_pal:
```

### 3.2 Sprite Table Buffer

```
Sprite_Table_Buffer:    ds.b 640    ; 80 entries × 8 bytes
Sprite_Table_Dirty:     ds.b 1      ; non-zero = needs DMA
Static_Sprite_DMA:      ds.b DMAEntry_len   ; pre-computed: buffer → VRAM $D800, 640 bytes
```

**Link chain pre-initialization:** At init, fill the link fields so entry 0 → 1, 1 → 2, ..., 78 → 79, 79 → 0. Y positions all set to 0 (off-screen). During gameplay, only positions/sizes/tiles are updated — links never change.

```asm
Init_SpriteTable:
    lea     (Sprite_Table_Buffer).w, a0
    moveq   #0, d0                      ; Y = 0 (off-screen)
    moveq   #1, d1                      ; link starts at 1
    moveq   #79-1, d2                   ; 79 entries (last handled separately)
.loop:
    move.w  d0, (a0)+                   ; Y position = 0
    move.b  #0, (a0)+                   ; size = 0 (1x1, invisible)
    move.b  d1, (a0)+                   ; link to next
    move.l  d0, (a0)+                   ; tile = 0, X = 0
    addq.b  #1, d1
    dbf     d2, .loop
    ; Last entry: link = 0 (terminates chain)
    move.w  d0, (a0)+
    move.b  #0, (a0)+
    move.b  #0, (a0)+                   ; link = 0
    move.l  d0, (a0)+
    rts
```

VBlank enqueue (VInt_Level step 4):
```asm
    tst.b   (Sprite_Table_Dirty).w
    beq.s   .no_spr
    QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Sprite_DMA
    clr.b   (Sprite_Table_Dirty).w
.no_spr:
```

### 3.3 HScroll Buffer

```
Hscroll_Buffer:         ds.b 896    ; 224 lines × 4 bytes (FG word + BG word)
Hscroll_Dirty_Start:    ds.b 1      ; first dirty scanline ($FF = clean)
Hscroll_Dirty_End:      ds.b 1      ; last dirty scanline
```

When dirty, compute a variable-size DMA entry at runtime and enqueue to Critical queue via `QueueDMATransfer`:
- Source: `Hscroll_Buffer + start × 4`
- Dest: `VRAM_HSCROLL_TABLE + start × 4`
- Length: `(end - start + 1) × 4`

After enqueue, reset both start/end to `$FF`.

### 3.4 VScroll Shadow

```
Vscroll_Factor:     ds.l 1      ; FG word + BG word (4 bytes)
```

Direct VDP write in VBlank step 2 (too small for DMA overhead):
```asm
    move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
    move.l  (Vscroll_Factor).w, (VDP_DATA).l
```

---

## 4. Utility Macros and Functions

### 4.1 New AS Functions

Add to `macros.asm`:

```asm
; VDP command delta — convert byte offset to scrambled command format for row advancement
vdpCommDelta    function addr, ((addr&$3FFF)<<16)|((addr&$C000)>>14)

; Plane cell byte offset — compute offset for cell (col, line) in a plane of given width
planeLoc        function width,col,line, (((width)*(line)+(col))*2)

; VDP register command (already exists, used by QueueStaticDMA)
; vdpReg        function reg,val, ($8000|((reg)<<8)|(val))

; DMA entry helpers
dmaSource       function addr, ((addr)>>1)&$7FFFFF
dmaLength       function bytes, ((bytes)>>1)&$FFFF
```

### 4.2 ResetDMAQueue Macro

```asm
ResetDMAQueue macro queue_start, queue_slot
    move.w  #queue_start, (queue_slot).w
    endm
```

### 4.3 BuildStaticDMA Routine

Called once at init to pre-compute the 5 static DMA entries (4 palette lines + 1 sprite table) from known RAM addresses and VRAM destinations. Writes the 14-byte entries into their RAM slots, with VDP register markers already set by `Init_DMA_Queue`.

---

## 5. PlaneMapToVRAM

CPU-based row-by-row nametable writer for one-shot plane loads (title screens, menus, level init). Used during display-off or VBlank — NOT during active display.

```asm
; PlaneMapToVRAM — write a rectangular tilemap to a VDP plane
; In:  a1 = source nametable data (VDP-ready words, packed width×height)
;      d0.l = VDP write command for top-left cell (built with vdpComm)
;      d1.w = width in cells - 1
;      d2.w = height in rows - 1
; Out: none
; Clobbers: d0-d4, a1, a5-a6

PlaneMapToVRAM:
    move.l  #vdpCommDelta(planeLoc(PLANE_H_CELLS,0,1)), d4
    lea     (VDP_DATA).l, a6
    lea     VDP_CTRL-VDP_DATA(a6), a5
.row:
    move.l  d0, (a5)                    ; set VRAM write address
    move.w  d1, d3                      ; copy width counter
.cell:
    move.w  (a1)+, (a6)                 ; write one nametable word
    dbf     d3, .cell
    add.l   d4, d0                      ; advance to next row
    dbf     d2, .row
    rts
```

The `vdpCommDelta(planeLoc(64,0,1))` resolves to `$00800000` at assembly time — the scrambled VDP command delta for advancing one row in a 64-wide plane.

---

## 6. Verification Test

### 6.1 Test Art Preparation (offline, before build)

1. Decompress a piece of art from sonic_hack using `tools/nemdec` and/or `tools/kosdec`
2. Extract the corresponding palette
3. Build or extract a nametable mapping
4. Place raw files in `aeon/test/` as binary includes

Use the Sonic 2 title screen art — large enough to exercise real DMA workloads, recognizable, known palette. Decompress with `nemdec`/`kosdec` from `sonic_hack/tools/`, extract palette from sonic_hack palette data.

### 6.2 Test GameState

Replace `GameState_Boot` (blue screen) with a new `GameState_DMATest` that:

1. **Frame 1 (init):**
   - Load palette data into `Palette_Buffer` lines 0 and 1
   - Set `Palette_Dirty` bits 0 and 1
   - Queue tile art DMA to VRAM via `QueueDMATransfer` (Important queue)
   - Write nametable to Plane A via `PlaneMapToVRAM` (display is off)
   - Enable display via `SetVDPReg`

2. **Frame 2+ (update):**
   - No-op (image stays on screen)
   - Verifiable: screenshot shows the loaded art

### 6.3 Verification Steps (via Exodus MCP)

Each step verified before proceeding to the next implementation step:

| Check | Tool | Expected |
|-------|------|----------|
| DMA queue initialized | `read_memory` at DMA_Queue | Register markers at even offsets |
| Palette in buffer | `read_memory` at Palette_Buffer | Matches source palette data |
| Palette dirty set | `read_memory` at Palette_Dirty | Non-zero before VBlank |
| Palette in CRAM | `screenshot` | Correct colors visible |
| Tiles in VRAM | `read_memory` VRAM region | Tile data present |
| Nametable in VRAM | `read_memory` at $C000+ | Tile indices in expected pattern |
| Art on screen | `screenshot` | Recognizable image displayed |
| No lag frames | `read_memory` Lag_Frame_Count | Zero |

---

## 7. RAM Budget

New RAM allocations for §1:

| Region | Size | Purpose |
|--------|------|---------|
| DMA_Queue | 448 bytes | 32 slots × 14 bytes |
| DMA_Queue_Slots | 6 bytes | 3 slot pointers |
| Palette_Buffer | 128 bytes | 4 palette lines |
| Palette_Dirty | 1 byte | Per-line dirty bits |
| Static_Pal_Lines | 56 bytes | 4 × 14-byte pre-computed entries |
| Sprite_Table_Buffer | 640 bytes | 80 sprites × 8 bytes |
| Sprite_Table_Dirty | 1 byte | Single dirty flag |
| Static_Sprite_DMA | 14 bytes | Pre-computed entry |
| Hscroll_Buffer | 896 bytes | 224 lines × 4 bytes |
| Hscroll_Dirty | 2 bytes | Start + end scanline |
| Vscroll_Factor | 4 bytes | FG + BG scroll words |
| VInt_Ptr | 4 bytes | VBlank handler pointer |
| VBlank_Ready | 1 byte | Main loop completion flag |
| DMA_Budget_Remaining | 2 bytes | Per-frame byte budget |
| Debug counters | 14 bytes | Behind ifdebug (6 words + 1 long) |
| **Total** | **~2,217 bytes** | Well within 64KB RAM |

Stack at `$FFFFFF00`, RAM starts at `$FFFF8000` — 32,512 bytes available. Current usage is ~50 bytes (§0). After §1: ~2,267 bytes used, ~30,245 bytes remaining.

---

## 8. File Organization

New files:
- `engine/dma_queue.asm` — Init_DMA_Queue, QueueDMATransfer, drain routines, debug counters
- `engine/buffers.asm` — Init_SpriteTable, BuildStaticDMA, PlaneMapToVRAM, buffer init
- `test/` — decompressed art, palette, nametable binary data

Modified files:
- `main.asm` — add includes for new engine files
- `macros.asm` — add vdpCommDelta, planeLoc, dmaSource, dmaLength, QueueStaticDMA, ResetDMAQueue
- `structs.asm` — add DMAEntry struct
- `ram.asm` — add all new RAM regions (§1 section)
- `constants.asm` — add DMA queue constants (slot counts, budget values)
- `engine/vblank.asm` — restructure to VInt_Ptr dispatch, add VInt_Level, VInt_Lag
- `engine/game_loop.asm` — update VSync_Wait, replace GameState_Boot with GameState_DMATest
