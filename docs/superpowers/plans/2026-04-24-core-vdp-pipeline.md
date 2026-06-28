# §1 Core VDP Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the DMA queue infrastructure, VBlank restructuring, RAM buffers with dirty flags, and a verification test that displays decompressed Sonic 2 title screen art.

**Architecture:** Flamewing Ultra DMA Queue format (14-byte interleaved entries, movep enqueue) split into three priority sub-queues (Critical/Important/Deferrable). VBlank dispatches through a RAM function pointer with lag frame detection. RAM buffers (palette, sprite table, hscroll, vscroll) use dirty flags to skip unchanged DMA. A full-pipeline test loads art, palette, and nametable to prove everything works end-to-end.

**Tech Stack:** 68000 assembly, AS Macro Assembler, Exodus emulator MCP for verification

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `structs.asm` | Add DMAEntry struct (14 bytes) |
| Modify | `constants.asm` | Add DMA slot counts, budget values, GS_DMATEST |
| Modify | `macros.asm` | Add vdpCommDelta, planeLoc, dmaSource, dmaLength functions; vdpCommReg, QueueStaticDMA macros |
| Modify | `ram.asm` | Add all §1 RAM: queues, buffers, dirty flags, static entries, VInt_Ptr, debug counters |
| Create | `engine/dma_queue.asm` | Init_DMA_Queue, QueueDMATransfer (3 entry points), Process_DMA_Critical (jump table), Process_DMA_Important/Deferrable (budgeted loop) |
| Create | `engine/buffers.asm` | Init_SpriteTable, BuildStaticDMA, PlaneMapToVRAM, Enqueue_Dirty_Buffers |
| Modify | `engine/vblank.asm` | Full rewrite: VBlank_Handler dispatch, VInt_Level, VInt_Lag, VSync_Wait |
| Modify | `engine/game_loop.asm` | GameState_DMATest, test data (art, palette, nametable) |
| Modify | `engine/boot.asm` | Add §1 init calls (Init_DMA_Queue, Init_SpriteTable, BuildStaticDMA, VInt_Ptr, DMA budget) |
| Modify | `main.asm` | Add includes for dma_queue.asm, buffers.asm |
| Create | `test/title_art.bin` | Decompressed Nemesis art (10752 bytes, offline) |
| Create | `test/title_palette.bin` | Raw 32-byte CRAM palette (copied from sonic_hack) |

---

### Task 1: DMAEntry struct and DMA constants

**Files:**
- Modify: `structs.asm:30+` (after VDP_Shadow endstruct)
- Modify: `constants.asm:83+` (after game state IDs)

- [ ] **Step 1: Add DMAEntry struct to structs.asm**

Append after the VDP_Shadow struct and its size assertion:

```asm
; -----------------------------------------------
; DMA Queue Entry (§1.2)
; Flamewing Ultra format — VDP reg numbers at even offsets,
; data at odd offsets. movep writes interleave naturally.
; -----------------------------------------------

DMAEntry struct
Reg94           ds.b 1          ; +0  VDP reg $14 marker
SizeH           ds.b 1          ; +1  DMA length high byte
Reg93           ds.b 1          ; +2  VDP reg $13 marker
SizeL           ds.b 1          ; +3  DMA length low byte
Reg97           ds.b 1          ; +4  VDP reg $17 marker
SrcH            ds.b 1          ; +5  source address bits 22-16
Reg96           ds.b 1          ; +6  VDP reg $16 marker
SrcM            ds.b 1          ; +7  source address bits 15-8
Reg95           ds.b 1          ; +8  VDP reg $15 marker
SrcL            ds.b 1          ; +9  source address bits 7-0
Command         ds.l 1          ; +10 VDP command (destination + DMA trigger)
DMAEntry endstruct

        if DMAEntry_len <> 14
          error "DMAEntry struct is \{DMAEntry_len} bytes, expected 14"
        endif
```

- [ ] **Step 2: Add DMA constants and game state ID to constants.asm**

Append after the game state IDs section:

```asm
GS_DMATEST              = 1

; -----------------------------------------------
; DMA Queue (§1.1)
; -----------------------------------------------
DMA_CRITICAL_SLOTS      = 8
DMA_IMPORTANT_SLOTS     = 12
DMA_DEFERRABLE_SLOTS    = 12
DMA_TOTAL_SLOTS         = DMA_CRITICAL_SLOTS+DMA_IMPORTANT_SLOTS+DMA_DEFERRABLE_SLOTS

DMA_BUDGET_NTSC         = 7200          ; usable DMA bytes per NTSC VBlank
DMA_BUDGET_PAL          = 15000         ; usable DMA bytes per PAL VBlank
```

- [ ] **Step 3: Build to verify struct and constants compile**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean, no errors

- [ ] **Step 4: Commit**

```bash
git add structs.asm constants.asm
git commit -m "feat(§1): add DMAEntry struct and DMA queue constants"
```

---

### Task 2: New macros and functions

**Files:**
- Modify: `macros.asm:25+` (after bytesToLcnt function)
- Modify: `macros.asm:65+` (after SetVDPReg macro)

- [ ] **Step 1: Add new AS functions to macros.asm**

After the `bytesToLcnt` function (line 24), add:

```asm
; VDP command delta — scrambled offset for row advancement in PlaneMapToVRAM
vdpCommDelta    function addr, (((addr)&$3FFF)<<16)|(((addr)&$C000)>>14)

; Plane cell byte offset — offset for cell (col, row) in plane of given width
planeLoc        function width,col,row, (((width)*(row)+(col))*2)

; DMA source word address (bit 23 cleared for RAM safety)
dmaSource       function addr, (((addr)>>1)&$7FFFFF)

; DMA length in words
dmaLength       function bytes, (((bytes)>>1)&$FFFF)
```

- [ ] **Step 2: Add vdpCommReg macro to macros.asm**

After the SetVDPReg macro, add:

```asm
; -----------------------------------------------
; vdpCommReg — runtime VDP command from register
; Converts a VRAM/CRAM/VSRAM byte address in a data register
; to a VDP command longword (in-place).
; type/rwd must be assembly-time constants.
; clr: 1 = clear upper word of reg first, 0 = assume clean
; From Flamewing Ultra DMA Queue.
; -----------------------------------------------
vdpCommReg macro reg, type, rwd, clr
        lsl.l   #2, reg
    if ((type)&(rwd))&3 <> 0
        addq.w  #((type)&(rwd))&3, reg
    endif
        ror.w   #2, reg
        swap    reg
    if (clr) <> 0
        andi.w  #3, reg
    endif
    if ((type)&(rwd))&$FC = $20
        tas.b   reg
    elseif ((type)&(rwd))&$FC <> 0
        ori.w   #(((type)&(rwd))&$FC)<<2, reg
    endif
        endm

; -----------------------------------------------
; QueueStaticDMA — inline block-copy of pre-computed 14-byte DMA entry
; Copies from a RAM source entry into the next free queue slot.
; In: slot_var = queue slot pointer variable (e.g. DMA_Critical_Slot)
;     queue_end = queue end address constant
;     entry_var = pre-computed entry variable (e.g. Static_Pal_Line0)
; Clobbers: a1, a2
; -----------------------------------------------
QueueStaticDMA macro slot_var, queue_end, entry_var
        movea.w (slot_var).w, a1
        cmpa.w  #queue_end, a1
        beq.s   .done
        lea     (entry_var).w, a2
        move.l  (a2)+, (a1)+
        move.l  (a2)+, (a1)+
        move.l  (a2)+, (a1)+
        move.w  (a2)+, (a1)+
        move.w  a1, (slot_var).w
.done:
        endm
```

- [ ] **Step 3: Build to verify macros compile**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 4: Commit**

```bash
git add macros.asm
git commit -m "feat(§1): add DMA utility functions and macros (vdpCommReg, QueueStaticDMA)"
```

---

### Task 3: RAM layout for §1

**Files:**
- Modify: `ram.asm` (add new section between RNG_Seed and RAM_End)

- [ ] **Step 1: Add §1 RAM regions to ram.asm**

Insert before `RAM_End:` (after the RNG section), replacing the existing `RAM_End:` line:

```asm
; -----------------------------------------------
; VBlank dispatch (§1 — VDP Pipeline)
; -----------------------------------------------
VInt_Ptr:               ds.l 1          ; pointer to current VBlank handler
VBlank_Ready:           ds.b 1          ; set by main loop, cleared by VBlank
                        ds.b 1          ; pad

; -----------------------------------------------
; DMA Queue (§1.1)
; Three priority sub-queues, contiguous in memory
; -----------------------------------------------
DMA_Queue:
DMA_Critical:           ds.b DMA_CRITICAL_SLOTS*DMAEntry_len
DMA_Critical_End:
DMA_Important:          ds.b DMA_IMPORTANT_SLOTS*DMAEntry_len
DMA_Important_End:
DMA_Deferrable:         ds.b DMA_DEFERRABLE_SLOTS*DMAEntry_len
DMA_Deferrable_End:
DMA_Queue_End:

DMA_Critical_Slot:      ds.w 1          ; next free Critical slot
DMA_Important_Slot:     ds.w 1          ; next free Important slot
DMA_Deferrable_Slot:    ds.w 1          ; next free Deferrable slot

DMA_Budget_Default:     ds.w 1          ; per-frame byte budget (set at boot)
DMA_Budget_Remaining:   ds.w 1          ; remaining bytes this frame

; -----------------------------------------------
; RAM Buffers and Dirty Flags (§1.3)
; -----------------------------------------------
Palette_Buffer:         ds.b 128        ; 4 lines × 32 bytes
Palette_Dirty:          ds.b 1          ; bits 0-3 = per-line dirty
                        ds.b 1          ; pad

Sprite_Table_Buffer:    ds.b 640        ; 80 entries × 8 bytes
Sprite_Table_Dirty:     ds.b 1
                        ds.b 1          ; pad

Hscroll_Buffer:         ds.b 896        ; 224 lines × 4 bytes (FG + BG)
Hscroll_Dirty_Start:    ds.b 1          ; first dirty scanline ($FF = clean)
Hscroll_Dirty_End:      ds.b 1          ; last dirty scanline

Vscroll_Factor:         ds.l 1          ; FG word + BG word

; -----------------------------------------------
; Static DMA Entries (§1.5)
; Pre-computed 14-byte entries for fixed transfers
; -----------------------------------------------
Static_Pal_Line0:       ds.b DMAEntry_len
Static_Pal_Line1:       ds.b DMAEntry_len
Static_Pal_Line2:       ds.b DMAEntry_len
Static_Pal_Line3:       ds.b DMAEntry_len
Static_Sprite_DMA:      ds.b DMAEntry_len

; -----------------------------------------------
; Debug profiling (§1.7) — zero in release builds
; -----------------------------------------------
    ifdef __DEBUG__
DMA_Bytes_ThisFrame:    ds.w 1
DMA_Peak_Critical:      ds.w 1
DMA_Peak_Important:     ds.w 1
DMA_Peak_Deferrable:    ds.w 1
DMA_Overflow_Count:     ds.w 1
Lag_Frame_Count:        ds.l 1
    endif

RAM_End:
```

- [ ] **Step 2: Build to verify RAM layout compiles and fits**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean (no "RAM overflow into stack" error)

- [ ] **Step 3: Commit**

```bash
git add ram.asm
git commit -m "feat(§1): add RAM layout for DMA queues, buffers, dirty flags, and static entries"
```

---

### Task 4: Init_DMA_Queue

**Files:**
- Create: `engine/dma_queue.asm`
- Modify: `main.asm:97` (add include)
- Modify: `engine/boot.asm:143+` (add init call)

- [ ] **Step 1: Create engine/dma_queue.asm with Init_DMA_Queue**

```asm
; DMA queue — 3-priority sub-queue system with Flamewing Ultra format

; -----------------------------------------------
; Init_DMA_Queue — pre-fill all 32 slots with VDP register markers
; Called once at boot. Uses rept to unroll at assembly time.
; In:  none
; Out: none
; Clobbers: d0-d1, a0
; -----------------------------------------------
Init_DMA_Queue:
        lea     (DMA_Queue).w, a0
        moveq   #-$6C, d0                      ; $94 sign-extended
        move.l  #$93979695, d1

    set .c, 0
    rept DMA_TOTAL_SLOTS
        move.b  d0, .c+DMAEntry_Reg94(a0)
        movep.l d1, .c+DMAEntry_Reg93(a0)
    set .c, .c+DMAEntry_len
    endr

        move.w  #DMA_Critical, (DMA_Critical_Slot).w
        move.w  #DMA_Important, (DMA_Important_Slot).w
        move.w  #DMA_Deferrable, (DMA_Deferrable_Slot).w
        rts
```

- [ ] **Step 2: Add include to main.asm**

After the `include "engine/vdp_init.asm"` line (line 93), add:

```asm
    include "engine/dma_queue.asm"
```

- [ ] **Step 3: Add Init_DMA_Queue call to boot.asm**

After the `bsr.w VDP_Shadow_Init` call (line 144), add:

```asm
        ; Init DMA queue (§1.1)
        bsr.w   Init_DMA_Queue
```

- [ ] **Step 4: Build**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 5: Verify in Exodus**

Build and load ROM in Exodus. Use MCP to verify the DMA queue memory:

```
emulator_read_memory address=<DMA_Queue_address> length=28
```

Expected: first entry has bytes $94 at offset 0, $93 at offset 2, $97 at offset 4, $96 at offset 6, $95 at offset 8. Second entry same pattern starting 14 bytes later.

Also verify slot pointers:
```
emulator_read_memory address=<DMA_Critical_Slot_address> length=6
```
Expected: three words pointing to DMA_Critical, DMA_Important, DMA_Deferrable respectively.

- [ ] **Step 6: Commit**

```bash
git add engine/dma_queue.asm main.asm engine/boot.asm
git commit -m "feat(§1): add Init_DMA_Queue — pre-fills 32 slots with register markers"
```

---

### Task 5: QueueDMATransfer

**Files:**
- Modify: `engine/dma_queue.asm` (append after Init_DMA_Queue)

- [ ] **Step 1: Add the three entry point wrappers and core QueueDMATransfer**

Append to `engine/dma_queue.asm`:

```asm
; -----------------------------------------------
; QueueDMA_Critical / QueueDMA_Important / QueueDMA_Deferrable
; Entry points that select the target sub-queue, then fall
; through to the shared QueueDMATransfer core.
;
; In:  d1.l = source address (bytes, even)
;      d2.w = VRAM destination (byte address)
;      d3.w = transfer length (bytes, even, non-zero)
; Out: none (carry set = queue was full)
; Clobbers: d0-d4, a1-a2
; -----------------------------------------------
QueueDMA_Critical:
        lea     (DMA_Critical_Slot).w, a2
        move.w  #DMA_Critical_End, d4
        bra.s   QueueDMATransfer

QueueDMA_Important:
        lea     (DMA_Important_Slot).w, a2
        move.w  #DMA_Important_End, d4
        bra.s   QueueDMATransfer

QueueDMA_Deferrable:
        lea     (DMA_Deferrable_Slot).w, a2
        move.w  #DMA_Deferrable_End, d4

; -----------------------------------------------
; QueueDMATransfer — shared enqueue core
; In:  d1.l = source (bytes), d2.w = dest, d3.w = length (bytes)
;      a2 = pointer to slot variable, d4.w = queue end address
; -----------------------------------------------
QueueDMATransfer:
        move.w  sr, -(sp)
        disableInts
        movea.w (a2), a1
        cmpa.w  d4, a1
        beq.s   .full

        lsr.l   #1, d1                          ; source to words
        bclr.l  #23, d1                         ; RAM source safety
        movep.l d1, DMAEntry_SizeL(a1)          ; source → offsets 3,5,7,9

        lsr.w   #1, d3                          ; length to words
        movep.w d3, DMAEntry_SizeH(a1)          ; length → offsets 1,3 (overwrites junk at 3)

        moveq   #0, d0
        move.w  d2, d0
        vdpCommReg d0, VRAM, DMA, 0
        move.l  d0, DMAEntry_Command(a1)

        lea     DMAEntry_len(a1), a1
        move.w  a1, (a2)

        move.w  (sp)+, sr
        rts

.full:
    ifdef __DEBUG__
        addq.w  #1, (DMA_Overflow_Count).w
    endif
        move.w  (sp)+, sr
        rts
```

- [ ] **Step 2: Build to verify**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 3: Commit**

```bash
git add engine/dma_queue.asm
git commit -m "feat(§1): add QueueDMATransfer with 3 priority entry points"
```

---

### Task 6: DMA drain routines

**Files:**
- Modify: `engine/dma_queue.asm` (append after QueueDMATransfer)

- [ ] **Step 1: Add Process_DMA_Critical with jump-table unrolled drain**

Append to `engine/dma_queue.asm`:

```asm
; -----------------------------------------------
; Process_DMA_Critical — drain Critical queue via jump table
; Zero branches per entry. ~64 cycles/entry, ~514 for all 8.
; Ported from S.C.E. Process_DMA_Queue (Flamewing).
; In:  none
; Out: none
; Clobbers: a1, a5
; -----------------------------------------------
Process_DMA_Critical:
        movea.w (DMA_Critical_Slot).w, a1
        jmp     .jump_table-DMA_Critical(a1)

.jump_table:
        bra.w   .done
        rept 5
        trap    #0
        endr

    set .c, 1
    rept DMA_CRITICAL_SLOTS
        lea     (VDP_CTRL).l, a5
        lea     (DMA_Critical).w, a1
    if .c <> DMA_CRITICAL_SLOTS
        bra.w   .drain_end-.c*8
    endif
    set .c, .c+1
    endr

    rept DMA_CRITICAL_SLOTS
        move.l  (a1)+, (a5)
        move.l  (a1)+, (a5)
        move.l  (a1)+, (a5)
        move.w  (a1)+, (a5)
    endr

.drain_end:
        move.w  #DMA_Critical, (DMA_Critical_Slot).w
.done:
        rts
```

- [ ] **Step 2: Add Process_DMA_Important and Process_DMA_Deferrable with shared budgeted drain**

Append to `engine/dma_queue.asm`:

```asm
; -----------------------------------------------
; Process_DMA_Important — drain Important queue with byte budget
; In:  none (reads DMA_Budget_Remaining)
; Out: none
; Clobbers: d0-d1, a0-a2, a5
; -----------------------------------------------
Process_DMA_Important:
        movea.w (DMA_Important_Slot).w, a1
        lea     (DMA_Important).w, a0
        cmpa.l  a0, a1
        bls.s   .done
        bsr.s   Drain_Budgeted_Queue
.done:
        move.w  #DMA_Important, (DMA_Important_Slot).w
        rts

; -----------------------------------------------
; Process_DMA_Deferrable — drain Deferrable queue with byte budget
; In:  none (reads DMA_Budget_Remaining)
; Out: none
; Clobbers: d0-d1, a0-a2, a5
; -----------------------------------------------
Process_DMA_Deferrable:
        movea.w (DMA_Deferrable_Slot).w, a1
        lea     (DMA_Deferrable).w, a0
        cmpa.l  a0, a1
        bls.s   .done
        bsr.s   Drain_Budgeted_Queue
.done:
        move.w  #DMA_Deferrable, (DMA_Deferrable_Slot).w
        rts

; -----------------------------------------------
; Drain_Budgeted_Queue — shared loop for Important/Deferrable
; In:  a0 = queue start, a1 = slot pointer (first free)
;      DMA_Budget_Remaining must be set
; Out: none
; Clobbers: d0-d1, a0, a5
; -----------------------------------------------
Drain_Budgeted_Queue:
        lea     (VDP_CTRL).l, a5
.loop:
        move.w  (DMA_Budget_Remaining).w, d0
        ble.s   .done
        movep.w DMAEntry_SizeH(a0), d1          ; read size in words
        add.w   d1, d1                          ; words → bytes
        sub.w   d1, (DMA_Budget_Remaining).w
        move.l  (a0)+, (a5)
        move.l  (a0)+, (a5)
        move.l  (a0)+, (a5)
        move.w  (a0)+, (a5)
        cmpa.l  a0, a1
        bhi.s   .loop
.done:
        rts
```

- [ ] **Step 3: Build to verify**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 4: Commit**

```bash
git add engine/dma_queue.asm
git commit -m "feat(§1): add DMA drain routines — jump-table Critical, budgeted Important/Deferrable"
```

---

### Task 7: Buffer init and static DMA entries

**Files:**
- Create: `engine/buffers.asm`
- Modify: `main.asm` (add include)
- Modify: `engine/boot.asm` (add init calls)

- [ ] **Step 1: Create engine/buffers.asm with Init_SpriteTable**

```asm
; Buffer initialization, static DMA entries, and plane utilities

; -----------------------------------------------
; Init_SpriteTable — pre-init sprite link chain 0→1→2→...→79→0
; Y positions = 0 (off-screen), size = 0, tiles = 0
; In:  none
; Out: none
; Clobbers: d0-d2, a0
; -----------------------------------------------
Init_SpriteTable:
        lea     (Sprite_Table_Buffer).w, a0
        moveq   #0, d0
        moveq   #1, d1
        moveq   #79-1, d2
.loop:
        move.w  d0, (a0)+                      ; Y = 0
        move.b  d0, (a0)+                      ; size = 0
        move.b  d1, (a0)+                      ; link → next
        move.l  d0, (a0)+                      ; tile = 0, X = 0
        addq.b  #1, d1
        dbf     d2, .loop
        move.w  d0, (a0)+                      ; entry 79: Y = 0
        move.b  d0, (a0)+                      ; size = 0
        move.b  d0, (a0)+                      ; link = 0 (terminate)
        move.l  d0, (a0)+                      ; tile = 0, X = 0
        rts
```

- [ ] **Step 2: Add BuildStaticDMA to engine/buffers.asm**

Append to `engine/buffers.asm`:

```asm
; -----------------------------------------------
; BuildStaticDMA — pre-compute the 5 static DMA entries
; (4 palette lines + 1 sprite table)
; Called once at boot after Init_DMA_Queue.
; In:  none
; Out: none
; Clobbers: d0-d3, d5, a0
; -----------------------------------------------
BuildStaticDMA:
        moveq   #-$6C, d0                      ; $94 sign-extended
        move.l  #$93979695, d5

        ; Palette line 0: Palette_Buffer+$00 → CRAM $0000, 32 bytes
        lea     (Static_Pal_Line0).w, a0
        move.l  #dmaSource(Palette_Buffer), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm(0, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Palette line 1: Palette_Buffer+$20 → CRAM $0020, 32 bytes
        lea     (Static_Pal_Line1).w, a0
        move.l  #dmaSource(Palette_Buffer+$20), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm($20, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Palette line 2: Palette_Buffer+$40 → CRAM $0040, 32 bytes
        lea     (Static_Pal_Line2).w, a0
        move.l  #dmaSource(Palette_Buffer+$40), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm($40, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Palette line 3: Palette_Buffer+$60 → CRAM $0060, 32 bytes
        lea     (Static_Pal_Line3).w, a0
        move.l  #dmaSource(Palette_Buffer+$60), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm($60, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Sprite table: Sprite_Table_Buffer → VRAM $D800, 640 bytes
        lea     (Static_Sprite_DMA).w, a0
        move.l  #dmaSource(Sprite_Table_Buffer), d1
        move.w  #dmaLength(640), d3
        move.l  #vdpComm(VRAM_SPRITE_TABLE, VRAM, DMA), d2

.build_entry:
        move.b  d0, DMAEntry_Reg94(a0)
        movep.l d5, DMAEntry_Reg93(a0)
        movep.l d1, DMAEntry_SizeL(a0)          ; source → offsets 3,5,7,9
        movep.w d3, DMAEntry_SizeH(a0)          ; length → offsets 1,3
        move.l  d2, DMAEntry_Command(a0)
        rts
```

- [ ] **Step 3: Add include to main.asm and init calls to boot.asm**

In `main.asm`, after the `include "engine/dma_queue.asm"` line, add:

```asm
    include "engine/buffers.asm"
```

In `engine/boot.asm`, after the `bsr.w Init_DMA_Queue` call (added in Task 4), add:

```asm
        ; Init sprite table link chain (§1.3)
        bsr.w   Init_SpriteTable

        ; Build static DMA entries (§1.5)
        bsr.w   BuildStaticDMA
```

- [ ] **Step 4: Build**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 5: Verify in Exodus**

Build and load ROM. Use MCP to verify sprite table link chain:

```
emulator_read_memory address=<Sprite_Table_Buffer_address> length=32
```

Expected: entry 0 = Y:0000, size:00, link:01, tile+X:00000000. Entry 1 = Y:0000, size:00, link:02, ...

Verify a static DMA entry:

```
emulator_read_memory address=<Static_Pal_Line0_address> length=14
```

Expected: byte 0 = $94, byte 2 = $93, byte 4 = $97, byte 6 = $96, byte 8 = $95. Data bytes contain Palette_Buffer word-address and length 16 (words).

- [ ] **Step 6: Commit**

```bash
git add engine/buffers.asm main.asm engine/boot.asm
git commit -m "feat(§1): add Init_SpriteTable and BuildStaticDMA — link chain + 5 static entries"
```

---

### Task 8: PlaneMapToVRAM

**Files:**
- Modify: `engine/buffers.asm` (append)

- [ ] **Step 1: Add PlaneMapToVRAM to engine/buffers.asm**

Append to `engine/buffers.asm`:

```asm
; -----------------------------------------------
; PlaneMapToVRAM — CPU-based row-by-row nametable writer
; For one-shot plane loads (title screens, menus, level init).
; Use during display-off or VBlank only.
; In:  a1   = source nametable data (VDP-ready words)
;      d0.l = VDP write command for top-left cell
;      d1.w = width in cells - 1
;      d2.w = height in rows - 1
; Out: none
; Clobbers: d0-d4, a1, a5-a6
; -----------------------------------------------
PlaneMapToVRAM:
        move.l  #vdpCommDelta(planeLoc(PLANE_H_CELLS,0,1)), d4
        lea     (VDP_DATA).l, a6
        lea     VDP_CTRL-VDP_DATA(a6), a5
.row:
        move.l  d0, (a5)                        ; set VRAM write address
        move.w  d1, d3
.cell:
        move.w  (a1)+, (a6)                     ; write one nametable word
        dbf     d3, .cell
        add.l   d4, d0                          ; advance to next row
        dbf     d2, .row
        rts
```

- [ ] **Step 2: Build to verify**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 3: Commit**

```bash
git add engine/buffers.asm
git commit -m "feat(§1): add PlaneMapToVRAM — row-by-row nametable writer"
```

---

### Task 9: VBlank restructuring

**Files:**
- Modify: `engine/vblank.asm` (complete rewrite)
- Modify: `engine/boot.asm` (set VInt_Ptr and DMA budget)

- [ ] **Step 1: Add Enqueue_Dirty_Buffers to engine/buffers.asm**

Append to `engine/buffers.asm`. This is shared by VInt_Level and VInt_Lag:

```asm
; -----------------------------------------------
; Enqueue_Dirty_Buffers — enqueue dirty palette lines and sprite table
; Called from VBlank handlers (Z80 already stopped).
; In:  none
; Out: none
; Clobbers: d0, a1-a2
; -----------------------------------------------
Enqueue_Dirty_Buffers:
        move.b  (Palette_Dirty).w, d0
        beq.s   .no_pal
        btst    #0, d0
        beq.s   .skip_pal0
        QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line0
.skip_pal0:
        btst    #1, d0
        beq.s   .skip_pal1
        QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line1
.skip_pal1:
        btst    #2, d0
        beq.s   .skip_pal2
        QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line2
.skip_pal2:
        btst    #3, d0
        beq.s   .skip_pal3
        QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line3
.skip_pal3:
        clr.b   (Palette_Dirty).w
.no_pal:
        tst.b   (Sprite_Table_Dirty).w
        beq.s   .no_spr
        QueueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Sprite_DMA
        clr.b   (Sprite_Table_Dirty).w
.no_spr:
        rts
```

- [ ] **Step 2: Rewrite engine/vblank.asm**

Replace the entire contents of `engine/vblank.asm`:

```asm
; VBlank handler with function pointer dispatch and lag detection (§1.2)

; -----------------------------------------------
; VBlank_Handler — IRQ6 entry point
; Dispatches through VInt_Ptr on normal frames,
; VInt_Lag when main loop hasn't finished.
; -----------------------------------------------
VBlank_Handler:
        movem.l d0-a6, -(sp)
        tst.b   (VBlank_Ready).w
        beq.s   .lag
        movea.l (VInt_Ptr).w, a0
        jsr     (a0)
        bra.s   .done
.lag:
        bsr.w   VInt_Lag
.done:
        clr.b   (VBlank_Ready).w
        movem.l (sp)+, d0-a6
        rte

; -----------------------------------------------
; VInt_Level — full pipeline handler (normal frames)
; Execution order: shadow flush → VSRAM → dirty enqueue →
;   Critical drain → budget → Important drain → Deferrable drain →
;   controllers → frame counter → VBlank flag
; -----------------------------------------------
VInt_Level:
        ; --- VDP work (Z80 stopped) ---
        stopZ80

        bsr.w   Flush_VDP_Shadow

        move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
        move.l  (Vscroll_Factor).w, (VDP_DATA).l

        bsr.w   Enqueue_Dirty_Buffers

        bsr.w   Process_DMA_Critical

        move.w  (DMA_Budget_Default).w, (DMA_Budget_Remaining).w
        bsr.w   Process_DMA_Important
        bsr.w   Process_DMA_Deferrable

        startZ80

        ; --- Non-VDP work ---
        bsr.w   Read_Controllers
        addq.w  #1, (Frame_Counter).w
        move.b  #1, (VBlank_Flag).w
        rts

; -----------------------------------------------
; VInt_Lag — minimal handler (lag frames)
; Critical DMA only. Important/Deferrable entries persist.
; -----------------------------------------------
VInt_Lag:
        stopZ80

        bsr.w   Flush_VDP_Shadow

        move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
        move.l  (Vscroll_Factor).w, (VDP_DATA).l

        bsr.w   Enqueue_Dirty_Buffers
        bsr.w   Process_DMA_Critical

        startZ80

        bsr.w   Read_Controllers
        addq.w  #1, (Frame_Counter).w
        move.b  #1, (VBlank_Flag).w

    ifdef __DEBUG__
        addq.l  #1, (Lag_Frame_Count).w
    endif
        rts

; -----------------------------------------------
; VSync_Wait — block until VBlank fires (§1.2.5)
; In:  none
; Out: none
; Clobbers: none
; -----------------------------------------------
VSync_Wait:
        move.b  #1, (VBlank_Ready).w
.wait:
        tst.b   (VBlank_Flag).w
        beq.s   .wait
        clr.b   (VBlank_Flag).w
    ifdef __DEBUG__
        clr.w   (DMA_Bytes_ThisFrame).w
    endif
        rts
```

- [ ] **Step 3: Add VInt_Ptr and DMA budget init to boot.asm**

In `engine/boot.asm`, after the `bsr.w BuildStaticDMA` call (added in Task 7), add:

```asm
        ; Set initial VBlank handler (§1.2)
        move.l  #VInt_Level, (VInt_Ptr).w
```

In the region detection section, modify the NTSC/PAL branches. Replace:

```asm
        btst    #6, d0
        bne.s   .pal
        move.w  #NTSC_TIMING_STEP, (Timing_Step).w
        bra.s   .region_done
.pal:
        move.w  #PAL_TIMING_STEP, (Timing_Step).w
.region_done:
```

With:

```asm
        btst    #6, d0
        bne.s   .pal
        move.w  #NTSC_TIMING_STEP, (Timing_Step).w
        move.w  #DMA_BUDGET_NTSC, (DMA_Budget_Default).w
        bra.s   .region_done
.pal:
        move.w  #PAL_TIMING_STEP, (Timing_Step).w
        move.w  #DMA_BUDGET_PAL, (DMA_Budget_Default).w
.region_done:
```

- [ ] **Step 4: Remove old VBlank stubs from vblank.asm**

The old stubs (`DMA_Queue_Drain_Stub`, `Sprite_Table_Upload_Stub`, `Sound_Update_Stub`) are removed by the full rewrite in step 2.

- [ ] **Step 5: Build**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 6: Verify in Exodus**

Build and load ROM. The blue screen from GameState_Boot should still display. The new VBlank handler fires without crashing. Use MCP:

```
emulator_screenshot
```

Expected: blue screen (GameState_Boot still active). No crash, VBlank runs correctly with the new dispatch system.

- [ ] **Step 7: Commit**

```bash
git add engine/vblank.asm engine/buffers.asm engine/boot.asm
git commit -m "feat(§1): restructure VBlank — function pointer dispatch, VInt_Level/Lag, VSync_Wait"
```

---

### Task 10: Prepare test art data

**Files:**
- Create: `test/title_art.bin` (offline decompression)
- Create: `test/title_palette.bin` (copy)

- [ ] **Step 1: Create test/ directory**

```bash
mkdir -p /home/volence/sonic_hacks/aeon/test
```

- [ ] **Step 2: Decompress title screen art**

```bash
/home/volence/sonic_hacks/sonic_hack/tools/nemdec -d \
  "/home/volence/sonic_hacks/sonic_hack/art/nemesis/Main patterns from title screen.bin" \
  /home/volence/sonic_hacks/aeon/test/title_art.bin
```

Expected: creates `test/title_art.bin` (10752 bytes = 336 tiles)

- [ ] **Step 3: Copy palette**

```bash
cp "/home/volence/sonic_hacks/sonic_hack/art/palettes/Title screen.bin" \
   /home/volence/sonic_hacks/aeon/test/title_palette.bin
```

Expected: creates `test/title_palette.bin` (32 bytes = 1 palette line)

- [ ] **Step 4: Commit test data**

```bash
git add test/
git commit -m "feat(§1): add decompressed title screen art and palette for DMA pipeline test"
```

---

### Task 11: GameState_DMATest

**Files:**
- Modify: `engine/game_loop.asm` (replace GameState_Boot with GameState_DMATest)
- Modify: `engine/boot.asm` (update initial game state)

- [ ] **Step 1: Replace GameState_Boot with GameState_DMATest**

Replace the entire contents of `engine/game_loop.asm`:

```asm
; Game state machine and main loop (§9.13)

; -----------------------------------------------
; GameLoop — master loop
; VSync → dispatch current state → repeat
; -----------------------------------------------
GameLoop:
        bsr.w   VSync_Wait
        movea.l (Game_State).w, a0
        jsr     (a0)
        bra.s   GameLoop

; -----------------------------------------------
; GameState_DMATest — §1 verification test
; Frame 1: load palette, DMA art, write nametable, enable display
; Frame 2+: idle (image stays on screen)
; -----------------------------------------------
GameState_DMATest:
        tst.b   (Game_State_Init).w
        bne.s   .update

        move.b  #1, (Game_State_Init).w

        ; Copy palette to buffer line 0
        lea     Test_Palette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #(32/4)-1, d0
.pal_copy:
        move.l  (a0)+, (a1)+
        dbf     d0, .pal_copy
        move.b  #1, (Palette_Dirty).w           ; mark line 0 dirty

        ; Queue art DMA to Critical queue (display is off — no budget concern)
        move.l  #Test_TileArt, d1
        move.w  #0, d2
        move.w  #TEST_ART_SIZE, d3
        bsr.w   QueueDMA_Critical

        ; Write nametable to Plane A (direct CPU write, display is off)
        stopZ80
        lea     Test_Nametable(pc), a1
        move.l  #vdpComm(VRAM_PLANE_A, VRAM, WRITE), d0
        move.w  #TEST_MAP_WIDTH-1, d1
        move.w  #TEST_MAP_HEIGHT-1, d2
        bsr.w   PlaneMapToVRAM
        startZ80

        ; Enable display for next VBlank
        SetVDPReg VDP_Shadow_vdp_mode2, #$74

.update:
        rts

; -----------------------------------------------
; Test data — included in ROM
; -----------------------------------------------
TEST_MAP_WIDTH          = 40
TEST_MAP_HEIGHT         = 28

Test_TileArt:
        binclude "test/title_art.bin"
Test_TileArt_End:
TEST_ART_SIZE           = Test_TileArt_End-Test_TileArt

        even

Test_Palette:
        binclude "test/title_palette.bin"
        even

Test_Nametable:
__tile = 0
    rept TEST_MAP_HEIGHT
    rept TEST_MAP_WIDTH
        dc.w    __tile
__tile = __tile+1
    endr
    endr
Test_Nametable_End:
```

- [ ] **Step 2: Update initial game state in boot.asm**

In `engine/boot.asm`, change the game state initialization from:

```asm
        move.l  #GameState_Boot, (Game_State).w
        move.b  #GS_BOOT, (Game_State_ID).w
```

To:

```asm
        move.l  #GameState_DMATest, (Game_State).w
        move.b  #GS_DMATEST, (Game_State_ID).w
```

- [ ] **Step 3: Build**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean

- [ ] **Step 4: Full verification in Exodus**

Build and load ROM. Run through verification checklist using MCP:

**Check 1 — Screenshot:**
```
emulator_screenshot
```
Expected: title screen art tiles visible with correct colors (sequential tile layout, not the original arrangement — but recognizable art with blues/whites from the Sonic 2 title palette)

**Check 2 — Palette in CRAM:**
```
emulator_read_memory address=0x0000 length=32 memory_domain=cram
```
Expected: matches the 32 bytes from `test/title_palette.bin` ($0E20, $0000, $0222, $0A66, ...)

**Check 3 — Tiles in VRAM:**
```
emulator_read_memory address=0x0000 length=64 memory_domain=vram
```
Expected: non-zero tile data (first 2 tiles = 64 bytes of decompressed art)

**Check 4 — Nametable in VRAM:**
```
emulator_read_memory address=0xC000 length=80 memory_domain=vram
```
Expected: sequential tile indices: 0000, 0001, 0002, ... 0027 (first row of 40 tiles)

**Check 5 — DMA queue empty (drained):**
```
emulator_read_memory address=<DMA_Critical_Slot_address> length=2
```
Expected: points to DMA_Critical base address (queue has been drained and reset)

**Check 6 — No lag frames (debug build only):**
If built with `DEBUG=1`:
```
emulator_read_memory address=<Lag_Frame_Count_address> length=4
```
Expected: 00000000

- [ ] **Step 5: Commit**

```bash
git add engine/game_loop.asm engine/boot.asm
git commit -m "feat(§1): add GameState_DMATest — full pipeline verification with title screen art"
```

---

### Task 12: Update ENGINE_ARCHITECTURE.md and final cleanup

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (update §1 with implementation details)

- [ ] **Step 1: Update ENGINE_ARCHITECTURE.md §1**

Update any §1 sections that differ from the spec based on implementation decisions:

- Note that 128KB boundary split is deferred (QueueDMATransfer does not currently split)
- Note that QueueStaticDMA is defined as a block-copy macro (not inline assembly)
- Note that VInt_Level and VInt_Lag share Enqueue_Dirty_Buffers subroutine
- Document the Z80 stop/start boundaries in VBlank handlers
- Note the three QueueDMA entry points (QueueDMA_Critical/Important/Deferrable)

- [ ] **Step 2: Build final verification**

Run: `cd /home/volence/sonic_hacks/aeon && ./build.sh`
Expected: assembles clean. ROM loads in Exodus and displays title screen art.

- [ ] **Step 3: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs: update ENGINE_ARCHITECTURE.md §1 with implementation notes"
```

- [ ] **Step 4: Merge to master**

```bash
git checkout master
git merge --no-ff <feature-branch> -m "feat: §1 Core VDP Pipeline — DMA queue, VBlank restructure, buffer system, verification test"
```

(If working directly on master, this step is a no-op.)
