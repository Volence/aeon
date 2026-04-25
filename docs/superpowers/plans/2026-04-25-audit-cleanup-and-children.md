# Audit Cleanup + Child Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix correctness issues and apply performance improvements found by auditing allocation, sprites, animation, and DPLC against all 7 reference disassemblies + online sources, then implement Task 13 (data-driven child creation).

**Architecture:** Each task is a focused fix to one subsystem. Tasks 1-4 are cleanup (allocation, sprites, animation, DPLC). Task 5 is new feature (child creation). All tasks produce a working, buildable ROM at each commit.

**Tech Stack:** Motorola 68000 assembly, AS Macro Assembler, existing s4_engine §3 object system

---

## File Map

| File | Responsibility | Tasks |
|------|----------------|-------|
| `engine/objects.asm` | Object allocation, deallocation, dispatch | Task 1 |
| `engine/sprites.asm` | Sprite rendering, SAT building, priority bands | Task 2 |
| `engine/animate.asm` | Animation system, control codes, flip propagation | Task 3 |
| `engine/dplc.asm` | DPLC art streaming, change detection | Task 4 |
| `main.asm` | ROM includes, data file references | Task 4, 5 |
| `objects/test_animated.asm` | Test object with DPLC (caller cleanup) | Task 4 |
| `objects/test_player.asm` | Test player with DPLC (caller cleanup) | Task 4 |
| `engine/children.asm` | Child creation + deletion (NEW) | Task 5 |

---

### Task 1: Allocation cleanup

**Files:**
- Modify: `engine/objects.asm`

**Audit findings addressed:**
- Deferred deletion sweep scans all 64 slots every frame (~2000-4000 cycles wasted)
- CCR flag protocol costs 16 extra cycles per allocation
- Dead `moveq #0, d1` in DeleteObject

- [ ] **Step 1: Switch AllocDynamic and AllocEffect to Z-flag protocol**

Replace carry-flag signaling with Z-flag (d0). In `engine/objects.asm`, replace `AllocDynamic`:

```asm
AllocDynamic:
        cmpi.w  #Dynamic_Free_Stack, (Dynamic_Free_SP).w
        beq.s   .full
        movea.w (Dynamic_Free_SP).w, a1
        subq.w  #2, (Dynamic_Free_SP).w
        movea.w -(a1), a1
        moveq   #0, d0                  ; Z set = success
        rts
.full:
        moveq   #1, d0                  ; Z clear = pool exhausted
        rts
```

Replace `AllocEffect` with the same pattern:

```asm
AllocEffect:
        cmpi.w  #Effect_Free_Stack, (Effect_Free_SP).w
        beq.s   .full
        movea.w (Effect_Free_SP).w, a1
        subq.w  #2, (Effect_Free_SP).w
        movea.w -(a1), a1
        moveq   #0, d0
        rts
.full:
        moveq   #1, d0
        rts
```

Callers check `bne.s .alloc_failed` instead of `bcs.s .alloc_failed`.

- [ ] **Step 2: Update all AllocDynamic/AllocEffect callers to use Z-flag**

Search for `bcs` after any `jsr AllocDynamic` or `jsr AllocEffect` call and change to `bne.s`. Current callers are in `test/object_test_state.asm`. The test_player is manually placed in Player_1 slot (no alloc call), so only the test state's enemy/solid spawn code needs updating.

- [ ] **Step 3: Remove dead register in DeleteObject**

In `DeleteObject`, at the `.clear_slot` label, remove `moveq #0, d1` — only `d0` is used for the 20 `move.l` clears.

- [ ] **Step 4: Replace deferred deletion sweep with immediate deletion**

Remove the `.deletion_sweep` section from `RunObjects` (the loop at lines 248-260 that walks all dynamic+system+effect slots checking RF_DELETE every frame).

Remove `MarkForDeletion` (no longer needed — objects call `DeleteObject` directly).

Update `RunObjects` to end after the effect slots `bsr.s .run_always` + `rts`, removing the `bra.w .deletion_sweep` at line 196.

Note: `RunObjects` iterates slots by address (`lea SST_len(a0), a0`). An object calling `DeleteObject` on itself during dispatch zeroes its own slot, which is safe because the dispatch loop has already read the code_addr for this iteration. The loop advances to the next slot normally.

- [ ] **Step 5: Build and verify**

```bash
./build.sh
```

Expected: ROM builds. Load in emulator, verify test scene still works — player moves, enemies patrol, solids work. No functional change.

- [ ] **Step 6: Commit**

```bash
git add engine/objects.asm test/object_test_state.asm
git commit -m "perf(§3): Z-flag alloc protocol, remove deferred deletion sweep, clean DeleteObject"
```

---

### Task 2: Sprite rendering — Y-flip, band overflow, performance

**Files:**
- Modify: `engine/sprites.asm`

**Audit findings addressed:**
- No Y-flip handling (any Y-flipped object renders incorrectly)
- Band overflow silently drops objects instead of cascading to next band
- X-flip width uses 5 instructions instead of 16-byte lookup table
- `suba.w #1, a5` should be `subq.w #1, a5`

- [ ] **Step 1: Add flip width/height lookup tables**

Add these tables at the bottom of `sprites.asm`, before any `rts` that ends the file (or after the last routine). These are the same tables used by S.C.E. and sonic_hack:

```asm
; Width adjustment for X-flipped sprites (indexed by raw VDP size byte)
; VDP size byte: bits 3-2 = width-1, bits 1-0 = height-1
; Table returns pixel width: (((size>>2)&3)+1)*8
CellOffsets_XFlip:
        dc.b  8,  8,  8,  8            ; width=1 (8px)
        dc.b 16, 16, 16, 16            ; width=2 (16px)
        dc.b 24, 24, 24, 24            ; width=3 (24px)
        dc.b 32, 32, 32, 32            ; width=4 (32px)

; Height adjustment for Y-flipped sprites (indexed by raw VDP size byte)
; Table returns pixel height: ((size&3)+1)*8
CellOffsets_YFlip:
        dc.b  8, 16, 24, 32            ; height=1,2,3,4 for width=1
        dc.b  8, 16, 24, 32            ; height=1,2,3,4 for width=2
        dc.b  8, 16, 24, 32            ; height=1,2,3,4 for width=3
        dc.b  8, 16, 24, 32            ; height=1,2,3,4 for width=4
```

- [ ] **Step 2: Refactor piece rendering into 4 flip variants**

Replace the current 2-loop structure (`.piece_loop` unflipped + `.piece_loop_flip` X-only) with a 4-way branch after `.have_pos`:

```asm
.have_pos:
        move.w  SST_art_tile(a0), d6

        ; Determine flip variant from render_flags bits 1-2
        move.b  SST_render_flags(a0), d0
        andi.w  #(1<<RF_XFLIP)|(1<<RF_YFLIP), d0
        beq.s   .pieces_unflipped
        cmpi.b  #1<<RF_XFLIP, d0
        beq.w   .pieces_xflip
        cmpi.b  #1<<RF_YFLIP, d0
        beq.w   .pieces_yflip
        bra.w   .pieces_xyflip
```

- [ ] **Step 3: Write unflipped piece loop with lookup table and dbeq**

Replace the existing `.piece_loop` with:

```asm
.pieces_unflipped:
        subq.w  #1, d4
.piece_loop:
        ; Read mapping piece (8 bytes)
        move.w  (a3)+, d0               ; Y offset (signed)
        move.b  (a3)+, d1               ; VDP size code
        addq.w  #1, a3                  ; skip padding byte
        move.w  (a3)+, a6              ; tile attrs (relative)
        move.w  (a3)+, a1              ; X offset (signed)

        ; VDP Y: screen_y + y_offset + 128
        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+              ; SAT +0: Y

        ; SAT +2: size | link
        move.b  d1, (a4)+              ; size code
        addq.b  #1, d5
        move.b  d5, (a4)+              ; link = next sprite index

        ; SAT +4: tile attributes
        move.w  a6, d0
        add.w   d6, d0
        move.w  d0, (a4)+

        ; SAT +6: X position
        move.w  a1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok
        moveq   #1, d0
.x_ok:
        move.w  d0, (a4)+

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop
        bra.w   .next_object
```

Note the changes from current code:
- `d5` incremented BEFORE writing link (so link = current sprite index + 1, matching VDP expectations — sprite 0 links to 1, etc.)
- `addq.b #1, d5` + `move.b d5, (a4)+` replaces the 3-instruction `move.w d5,d0; addq.w #1,d0; move.b d0,(a4)+`
- `cmpi.b`/`dbeq` replaces separate limit check at loop top

- [ ] **Step 4: Write X-flip piece loop**

```asm
.pieces_xflip:
        subq.w  #1, d4
.piece_loop_xf:
        move.w  (a3)+, d0
        move.b  (a3)+, d1
        addq.w  #1, a3
        move.w  (a3)+, a6
        move.w  (a3)+, a1

        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+

        move.b  d1, (a4)+
        addq.b  #1, d5
        move.b  d5, (a4)+

        ; Toggle X flip bit
        move.w  a6, d0
        eori.w  #$0800, d0
        add.w   d6, d0
        move.w  d0, (a4)+

        ; Negate X offset and subtract sprite width via lookup table
        move.w  a1, d0
        neg.w   d0
        moveq   #0, d1                  ; d1 was size code, re-zero for index
        move.b  -6(a3), d1              ; re-read VDP size code from mapping piece
        move.b  CellOffsets_XFlip(pc,d1.w), d1
        sub.w   d1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok_xf
        moveq   #1, d0
.x_ok_xf:
        move.w  d0, (a4)+

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop_xf
        bra.w   .next_object
```

Note: VDP size code is re-read from `a3-6` (6 bytes back from current a3: 2 for X offset we just read + 2 for tile attrs + 1 for pad + 1 for size byte = 6). This avoids needing an extra register to preserve d1 across the tile attribute writes.

- [ ] **Step 5: Write Y-flip piece loop**

```asm
.pieces_yflip:
        subq.w  #1, d4
.piece_loop_yf:
        move.w  (a3)+, d0               ; Y offset (signed)
        move.b  (a3)+, d1               ; VDP size code
        addq.w  #1, a3
        move.w  (a3)+, a6
        move.w  (a3)+, a1

        ; Negate Y offset and subtract sprite height via lookup table
        neg.w   d0
        move.b  CellOffsets_YFlip(pc,d1.w), d1
        sub.w   d1, d0
        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+

        move.b  -6(a3), d1              ; re-read VDP size code
        move.b  d1, (a4)+
        addq.b  #1, d5
        move.b  d5, (a4)+

        ; Toggle Y flip bit
        move.w  a6, d0
        eori.w  #$1000, d0
        add.w   d6, d0
        move.w  d0, (a4)+

        ; X position (normal, no X flip)
        move.w  a1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok_yf
        moveq   #1, d0
.x_ok_yf:
        move.w  d0, (a4)+

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop_yf
        bra.w   .next_object
```

- [ ] **Step 6: Write XY-flip piece loop**

```asm
.pieces_xyflip:
        subq.w  #1, d4
.piece_loop_xyf:
        move.w  (a3)+, d0               ; Y offset
        move.b  (a3)+, d1               ; VDP size code
        addq.w  #1, a3
        move.w  (a3)+, a6
        move.w  (a3)+, a1

        ; Negate Y offset, subtract sprite height
        neg.w   d0
        move.b  CellOffsets_YFlip(pc,d1.w), d1
        sub.w   d1, d0
        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+

        move.b  -6(a3), d1              ; re-read VDP size code
        move.b  d1, (a4)+
        addq.b  #1, d5
        move.b  d5, (a4)+

        ; Toggle both flip bits
        move.w  a6, d0
        eori.w  #$1800, d0
        add.w   d6, d0
        move.w  d0, (a4)+

        ; Negate X offset, subtract sprite width
        move.w  a1, d0
        neg.w   d0
        moveq   #0, d1
        move.b  -6(a3), d1              ; re-read VDP size code again
        move.b  CellOffsets_XFlip(pc,d1.w), d1
        sub.w   d1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok_xyf
        moveq   #1, d0
.x_ok_xyf:
        move.w  d0, (a4)+

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop_xyf
        bra.w   .next_object
```

- [ ] **Step 7: Fix band overflow to cascade instead of drop**

In `Draw_Sprite`, replace the current `.band_full` handler (which just returns) with S.C.E.'s cascade pattern. Replace:

```asm
        cmpi.b  #SPRITES_PER_BAND, d1
        beq.s   .band_full
```

with a cascade loop that tries the next band down:

```asm
        cmpi.b  #SPRITES_PER_BAND, d1
        blo.s   .band_has_room

        ; Band full — cascade to next lower band
.cascade:
        subq.w  #1, d0
        bmi.s   .all_bands_full         ; all bands full, truly drop
        move.b  (a1,d0.w), d1
        cmpi.b  #SPRITES_PER_BAND, d1
        bhs.s   .cascade

.band_has_room:
```

And change `.band_full` to `.all_bands_full`:

```asm
.all_bands_full:
        rts
```

- [ ] **Step 8: Fix `suba.w` to `subq.w`**

In Render_Sprites `.next_band`, replace:

```asm
        suba.w  #1, a5
```

with:

```asm
        subq.w  #1, a5
```

- [ ] **Step 9: Fix sprite index tracking**

The current code initializes `d5 = 0` and increments AFTER writing each sprite. With the new `addq.b #1, d5` BEFORE writing link, d5 represents "next available index" and starts at 0. The first sprite written gets link=1 (pointing to sprite index 1), which is correct. The last sprite's link gets patched to 0 at `.done`.

Verify the `.done` fixup still works: `move.b #0, -5(a4)` writes to the link byte of the last sprite entry (SAT entry is 8 bytes, link is at offset +3, so `(a4) - 8 + 3 = (a4) - 5`). This is correct.

Update `Sprites_Rendered` to store `d5` directly (it now equals the count of rendered sprites, since we increment before writing).

- [ ] **Step 10: Build and verify**

```bash
./build.sh
```

Expected: ROM builds. Load in emulator, verify Sonic sprites render correctly. Test X-flip by walking left (Sonic should flip). Y-flip is not used by current test objects but should not crash.

- [ ] **Step 11: Commit**

```bash
git add engine/sprites.asm
git commit -m "fix(§3): add Y-flip, band overflow cascade, lookup table X-flip width, dbeq sprite limit"
```

---

### Task 3: Animation — flip propagation, jump table, $FB delete code

**Files:**
- Modify: `engine/animate.asm`

**Audit findings addressed:**
- Missing status-to-render_flags flip propagation (bug-in-waiting)
- Sequential compare-branch for control codes (suboptimal with 10+ codes planned)
- No $FB delete control code (S.C.E. and S3K have this)
- Duplicated control code logic in PerFrame variant

- [ ] **Step 1: Add $FB delete control code constant**

At the top of `animate.asm`, add:

```asm
AF_DELETE           = $FB
```

The full constant list becomes:

```asm
AF_END              = $FF
AF_BACK             = $FE
AF_CHANGE           = $FD
AF_ROUTINE          = $FC
AF_DELETE           = $FB
```

- [ ] **Step 2: Add status-to-render_flags flip propagation**

In `AnimateSprite`, after `move.b d0, SST_mapping_frame(a0)` at the `.next` label (currently at line 50), add the S.C.E. flip copy pattern. This copies status bits 1-2 (x_flip, y_flip) into render_flags bits 1-2:

In the current code, there are two places where `mapping_frame` is set:
1. After timer expiry (line 50): `move.b d0, SST_mapping_frame(a0)`
2. After anim change (line 66): `move.b d0, SST_mapping_frame(a0)`

Both should call a shared `.set_frame` label that does the flip copy:

```asm
.set_frame:
        move.b  d0, SST_mapping_frame(a0)
        moveq   #(1<<RF_XFLIP)|(1<<RF_YFLIP), d1
        and.b   SST_status(a0), d1
        andi.b  #~((1<<RF_XFLIP)|(1<<RF_YFLIP)), SST_render_flags(a0)
        or.b    d1, SST_render_flags(a0)
        rts
```

Replace both `move.b d0, SST_mapping_frame(a0); rts` sequences with `bra.s .set_frame`.

- [ ] **Step 3: Replace sequential compare-branch with PC-relative jump table for control codes**

Replace the current `.control_code` handler (lines 70-109) with a jump table. Control codes range from $FB to $FF (5 values). The jump table is indexed by `$FF - code`:

```asm
.control_code:
        ; d0 = control code byte ($FB-$FF)
        ; a1 = animation script base
        ; d1 = anim_frame offset (only valid after timer expiry, not after anim change)
        neg.b   d0                      ; $FF→$01, $FE→$02, $FD→$03, $FC→$04, $FB→$05
        andi.w  #$FF, d0
        cmpi.b  #5, d0
        bhi.s   .cc_end                 ; unknown code → treat as loop
        add.w   d0, d0
        add.w   d0, d0                  ; d0 * 4 (bra.w entry size)
        jmp     .cc_table-4(pc,d0.w)    ; -4 because index starts at 1

.cc_table:
        bra.w   .cc_end                 ; $FF (neg=1) — loop
        bra.w   .cc_back                ; $FE (neg=2) — jump back
        bra.w   .cc_change              ; $FD (neg=3) — switch anim
        bra.w   .cc_routine             ; $FC (neg=4) — advance routine
        bra.w   .cc_delete              ; $FB (neg=5) — delete object
```

- [ ] **Step 4: Implement $FB delete handler**

```asm
.cc_delete:
        ; $FB — mark object for deletion (move off-screen)
        ; Object will be cleaned up by its own code or by DeleteObject
        jmp     DeleteObject
```

This calls DeleteObject directly (which zeros the slot and returns it to the free stack). The `jmp` tail-call means we don't return to the animation caller.

- [ ] **Step 5: Factor PerFrame control codes into shared handler**

Replace the entire `.pf_control` section (lines 157-197) with a jump to the shared handler. The only difference is that AF_BACK rewinds by N*2 in PerFrame mode. Handle this with a flag:

Replace `AnimateSprite_PerFrame`'s control code section with:

```asm
.pf_control:
        ; Set per-frame flag so .cc_back knows to double the rewind
        st      (Anim_PerFrame_Flag).w
        bra.s   .control_code_pf
```

Then in `.cc_back`, add the doubling:

```asm
.cc_back:
        addq.b  #1, d1
        move.b  1(a1,d1.w), d0          ; read rewind count
        tst.b   (Anim_PerFrame_Flag).w
        beq.s   .cc_back_apply
        add.b   d0, d0                  ; double for per-frame pairs
.cc_back_apply:
        sub.b   d0, SST_anim_frame(a0)
        clr.b   (Anim_PerFrame_Flag).w

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
```

After rewinding, PerFrame must read the duration from the next byte. Add at the end of `.cc_back`:

```asm
        ; Read frame at new position
        tst.b   (Anim_PerFrame_Flag).w  ; already cleared, but check stride
        ; For per-anim: frame is at offset 1+d1 (skip duration byte 0)
        ; For per-frame: frame is at offset d1 (no skip)
```

Actually, this shared-handler approach gets complex because per-anim skips byte 0 (duration) while per-frame doesn't. A cleaner approach: keep two entry points but have them both call the same jump table. The per-frame variants read their frame/duration differently after the control code resolves.

Simpler approach — just have PerFrame's control code section call into the same jump table but with a different return path:

```asm
.pf_control:
        ; Same control codes, shared table
        neg.b   d0
        andi.w  #$FF, d0
        cmpi.b  #5, d0
        bhi.s   .pfc_end
        add.w   d0, d0
        add.w   d0, d0
        jmp     .pf_cc_table-4(pc,d0.w)

.pf_cc_table:
        bra.w   .pfc_end                ; $FF — loop
        bra.w   .pfc_back               ; $FE — jump back (double rewind)
        bra.w   .pfc_change             ; $FD — switch anim
        bra.w   .pfc_routine            ; $FC — advance routine
        bra.w   .cc_delete              ; $FB — delete (shared, same behavior)

.pfc_end:
        clr.b   SST_anim_frame(a0)
        move.b  (a1), d0
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1), SST_anim_timer(a0)
        bra.s   .pf_set_frame

.pfc_back:
        addq.b  #1, d1
        move.b  (a1,d1.w), d0
        add.b   d0, d0                  ; double for per-frame pairs
        sub.b   d0, SST_anim_frame(a0)
        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  (a1,d1.w), d0
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1,d1.w), SST_anim_timer(a0)
        bra.s   .pf_set_frame

.pfc_change:
        addq.b  #1, d1
        move.b  (a1,d1.w), SST_anim(a0)
        bra.w   AnimateSprite_PerFrame

.pfc_routine:
        addq.b  #2, SST_sst_custom(a0)
        rts

.pf_set_frame:
        ; Flip propagation for PerFrame variant
        moveq   #(1<<RF_XFLIP)|(1<<RF_YFLIP), d1
        and.b   SST_status(a0), d1
        andi.b  #~((1<<RF_XFLIP)|(1<<RF_YFLIP)), SST_render_flags(a0)
        or.b    d1, SST_render_flags(a0)
        rts
```

This keeps the PerFrame control codes as their own jump table but shares the `.cc_delete` handler and the overall structure. The `$FB` delete handler is identical for both variants.

- [ ] **Step 6: Build and verify**

```bash
./build.sh
```

Expected: ROM builds. Load in emulator. Sonic walk animation still works. Walk left → Sonic flips (render_flags now gets flip bits from status). Walk right → flips back. Jump → roll animation plays. No regressions.

- [ ] **Step 7: Commit**

```bash
git add engine/animate.asm
git commit -m "fix(§3): add status→render_flags flip propagation, jump table control codes, AF_DELETE"
```

---

### Task 4: DPLC — wire optimized data, move change detection inside

**Files:**
- Modify: `engine/dplc.asm`
- Modify: `main.asm`
- Modify: `objects/test_animated.asm`
- Modify: `objects/test_player.asm`

**Audit findings addressed:**
- Optimized DPLC/art data exists but isn't wired into the build
- Change detection duplicated in every caller (should be inside Perform_DPLC)
- Unnecessary movem.l save/restore (with 1-entry optimized data, loop runs once)

- [ ] **Step 1: Wire optimized DPLC and art data in main.asm**

In `main.asm`, replace:

```asm
DPLC_Sonic:
    BINCLUDE "data/dplc/sonic.bin"
    align 2
Art_Sonic:
    BINCLUDE "art/uncompressed/characters/sonic.bin"
    align 2
```

with:

```asm
DPLC_Sonic:
    BINCLUDE "data/dplc/optimized/sonic.bin"
    align 2
Art_Sonic:
    BINCLUDE "art/optimized/characters/sonic.bin"
    align 2
```

- [ ] **Step 2: Move change detection into Perform_DPLC**

Rewrite `Perform_DPLC` to accept the SST pointer and handle change detection internally. New signature:

```asm
; Perform_DPLC — load art for current mapping frame if changed
;
; In:  a0 = SST pointer
;      a2 = DPLC table pointer (ROM)
;      a3 = uncompressed art base address (ROM)
;      d1.w = VRAM destination (byte address)
; Out: none
; Clobbers: d0-d4, a1-a2
Perform_DPLC:
        move.b  SST_mapping_frame(a0), d0
        cmp.b   SST_prev_frame(a0), d0
        beq.s   .done                           ; frame unchanged, skip
        move.b  d0, SST_prev_frame(a0)

        ; Resolve DPLC frame data
        andi.w  #$FF, d0
        add.w   d0, d0
        adda.w  (a2,d0.w), a2                   ; a2 = frame data pointer
        move.w  (a2)+, d4                        ; d4 = entry count
        subq.w  #1, d4
        bmi.s   .done                            ; 0 entries

        move.w  d1, d2                           ; d2 = running VRAM dest

.entry_loop:
        move.w  (a2)+, d0                        ; DPLC entry word
        move.w  d0, d3
        lsr.w   #8, d3
        lsr.w   #4, d3                           ; d3 = tile_count - 1
        addq.w  #1, d3                           ; d3 = tile_count

        andi.l  #$0FFF, d0                       ; tile_start_index
        lsl.l   #5, d0                           ; byte offset
        move.l  a3, d1                           ; art base
        add.l   d0, d1                           ; d1.l = source address

        lsl.w   #5, d3                           ; d3.w = length (bytes)

        movem.l d2-d4/a0/a2-a3, -(sp)
        jsr     QueueDMA_Important
        movem.l (sp)+, d2-d4/a0/a2-a3

        add.w   d3, d2
        dbf     d4, .entry_loop
.done:
        rts
```

Key changes from current version:
- Takes SST pointer in a0 (instead of frame number in d0)
- Does prev_frame comparison internally
- Updates prev_frame internally
- Uses a2 for DPLC table (was a0), a3 for art base (was a1) — frees a0 for SST
- Saves a0 in the movem.l (since QueueDMA clobbers a1-a2 but not a0 — wait, let me check: QueueDMA clobbers `d0-d4, a1-a2`. So a0 is safe. But a2 and a3 are needed. Save `d2-d4/a2-a3`.)

Actually, QueueDMA clobbers `d0-d4, a1-a2`. The DPLC loop needs: d2 (VRAM dest), d4 (loop counter), a2 (DPLC data pointer), a3 (art base). d3 is computed fresh each iteration from the entry. So we need to save: `d2/d4/a2-a3`. That's 4 registers = 16 bytes on stack. a0 (SST pointer) is NOT clobbered by QueueDMA, so it's safe.

Revised movem.l:

```asm
        movem.l d2/d4/a2-a3, -(sp)
        jsr     QueueDMA_Important
        movem.l (sp)+, d2/d4/a2-a3
```

- [ ] **Step 3: Write Perform_DPLC_Deferrable with same pattern**

```asm
Perform_DPLC_Deferrable:
        move.b  SST_mapping_frame(a0), d0
        cmp.b   SST_prev_frame(a0), d0
        beq.s   .done
        move.b  d0, SST_prev_frame(a0)

        andi.w  #$FF, d0
        add.w   d0, d0
        adda.w  (a2,d0.w), a2
        move.w  (a2)+, d4
        subq.w  #1, d4
        bmi.s   .done

        move.w  d1, d2

.entry_loop:
        move.w  (a2)+, d0
        move.w  d0, d3
        lsr.w   #8, d3
        lsr.w   #4, d3
        addq.w  #1, d3
        andi.l  #$0FFF, d0

        lsl.l   #5, d0
        move.l  a3, d1
        add.l   d0, d1

        lsl.w   #5, d3

        movem.l d2/d4/a2-a3, -(sp)
        jsr     QueueDMA_Deferrable
        movem.l (sp)+, d2/d4/a2-a3

        add.w   d3, d2
        dbf     d4, .entry_loop
.done:
        rts
```

- [ ] **Step 4: Simplify test_animated.asm DPLC caller**

Replace the current DPLC calling code (lines 22-38) with:

```asm
        ; DPLC: art streaming handled inside Perform_DPLC (change detection included)
        movea.l _dplc_ptr(a0), a2
        movea.l _art_base(a0), a3
        move.w  #vram_bytes(VRAM_TEST_SONIC), d1
        jsr     Perform_DPLC
```

Remove the `movea.l a0, a3` / `movea.l a3, a0` dance — Perform_DPLC now preserves a0.

Remove the `move.b SST_mapping_frame(a0), d0` / `cmp.b SST_prev_frame(a0), d0` / `beq.s .no_dplc` / `move.b d0, SST_prev_frame(a0)` block — change detection is now inside Perform_DPLC.

Remove the `.no_dplc` label.

The full `TestAnimated_Main` becomes:

```asm
TestAnimated_Main:
        jsr     AnimateSprite

        movea.l _dplc_ptr(a0), a2
        movea.l _art_base(a0), a3
        move.w  #vram_bytes(VRAM_TEST_SONIC), d1
        jsr     Perform_DPLC

        jsr     Draw_Sprite
        rts
```

- [ ] **Step 5: Simplify test_player.asm DPLC caller**

Replace the DPLC section (lines 200-216) with:

```asm
        ; DPLC art streaming
        movea.l _dplc_ptr(a0), a2
        movea.l _art_base(a0), a3
        move.w  #vram_bytes(VRAM_TEST_SONIC), d1
        jsr     Perform_DPLC
```

Remove the prev_frame comparison, the a0/a3 swap, and the `.no_dplc` label.

- [ ] **Step 6: Build and verify**

```bash
./build.sh
```

Expected: ROM builds. Load in emulator, verify Sonic animation still works with optimized art data. Walk cycle should look identical. DPLC streaming should be transparent (1 DMA per frame change).

- [ ] **Step 7: Commit**

```bash
git add engine/dplc.asm main.asm objects/test_animated.asm objects/test_player.asm
git commit -m "fix(§3): wire optimized DPLC/art data, move change detection into Perform_DPLC"
```

---

### Task 5: Data-driven child creation + deletion

**Files:**
- Create: `engine/children.asm`
- Modify: `main.asm` (add include)

**This is the original Task 13 from the object system plan.**

- [ ] **Step 1: Create engine/children.asm with CreateChild_Normal**

```asm
; Child creation — data-driven parent-child object spawning

; -----------------------------------------------
; CreateChild_Normal — spawn children from a descriptor table
; Allocates from Dynamic pool. Each child inherits parent's
; mappings and art_tile. Child's parent_ptr set to parent address.
; Parent's sibling_ptr set to first child (head of chain).
; Subsequent children chain via sibling_ptr.
;
; Descriptor format (4 bytes per child, terminated by dc.w 0):
;   dc.w objroutine(ChildCode)   ; child code_addr (0 = end)
;   dc.b x_offset_signed         ; signed byte, relative to parent X
;   dc.b y_offset_signed         ; signed byte, relative to parent Y
;
; In:  a0 = parent SST pointer
;      a1 = descriptor table pointer (ROM)
; Out: none (children allocated, or silently skipped if pool full)
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
CreateChild_Normal:
        moveq   #0, d3                  ; d3 = previous child addr (0 = none)
.child_loop:
        move.w  (a1)+, d2               ; d2 = child code_addr
        beq.s   .done                   ; 0 = end of descriptor table

        movem.l a0-a1, -(sp)
        jsr     AllocDynamic            ; a1 = new child SST (uses Z-flag)
        bne.s   .alloc_fail

        movea.l a1, a2                  ; a2 = child SST
        movem.l (sp)+, a0-a1

        ; Set child code_addr
        move.w  d2, SST_code_addr(a2)

        ; Set child position = parent position + signed byte offsets
        move.l  SST_x_pos(a0), d0
        move.b  (a1)+, d2               ; x_offset (signed byte)
        ext.w   d2
        swap    d2
        clr.w   d2                      ; d2 = x_offset << 16 (16.16)
        add.l   d2, d0
        move.l  d0, SST_x_pos(a2)

        move.l  SST_y_pos(a0), d0
        move.b  (a1)+, d2               ; y_offset (signed byte)
        ext.w   d2
        swap    d2
        clr.w   d2
        add.l   d2, d0
        move.l  d0, SST_y_pos(a2)

        ; Inherit parent's mappings and art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Set parent link
        move.w  a0, SST_parent_ptr(a2)

        ; Chain: first child → parent's sibling_ptr
        ;        subsequent children → previous child's sibling_ptr
        tst.w   d3
        bne.s   .chain_sibling
        move.w  a2, SST_sibling_ptr(a0) ; first child: parent points to it
        bra.s   .chain_done
.chain_sibling:
        movea.w d3, a2                  ; wait, d3 is prev child address
        move.w  a2, SST_sibling_ptr(a2) ; that's wrong...
```

Actually, let me reconsider the chaining. The cleanest pattern:
- Parent's `sibling_ptr` → first child
- Each child's `sibling_ptr` → next child in chain
- Last child's `sibling_ptr` = 0

This allows `DeleteChildren` to walk: start at `parent.sibling_ptr`, follow `child.sibling_ptr` until 0.

Let me rewrite this cleanly:

```asm
CreateChild_Normal:
        move.w  SST_sibling_ptr(a0), d3 ; d3 = chain tail (0 if no children yet)
.child_loop:
        move.w  (a1)+, d2               ; d2 = child code_addr
        beq.s   .done                   ; 0 = end of table

        movem.l d3/a0-a1, -(sp)
        jsr     AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = child SST
        movem.l (sp)+, d3/a0-a1

        move.w  d2, SST_code_addr(a2)

        ; Position = parent + signed byte offset (16.16)
        move.b  (a1)+, d0               ; x_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        move.b  (a1)+, d0               ; y_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Link: child → parent
        move.w  a0, SST_parent_ptr(a2)

        ; Chain into sibling list (prepend)
        move.w  d3, SST_sibling_ptr(a2) ; child points to previous head
        move.w  a2, d3                  ; new head = this child
        move.w  a2, SST_sibling_ptr(a0) ; parent always points to newest child

        bra.s   .child_loop

.alloc_fail:
        movem.l (sp)+, d3/a0-a1
        ; Skip remaining descriptor bytes (code_addr already consumed)
        addq.w  #2, a1                  ; skip x_off, y_off
        tst.w   (a1)                    ; check next entry
        bne.s   .alloc_fail_skip        ; more entries to skip
.done:
        rts
.alloc_fail_skip:
        addq.w  #4, a1                  ; skip code_addr + offsets
        tst.w   (a1)
        bne.s   .alloc_fail_skip
        rts
```

- [ ] **Step 2: Implement CreateChild_Complex**

```asm
; -----------------------------------------------
; CreateChild_Complex — spawn children with velocity and animation
; Like Normal but descriptor includes velocity and animation data.
;
; Descriptor format (12 bytes per child, terminated by dc.w 0):
;   dc.w objroutine(ChildCode)   ; child code_addr (0 = end)
;   dc.b x_offset_signed         ; signed byte
;   dc.b y_offset_signed         ; signed byte
;   dc.w x_velocity              ; child x_vel
;   dc.w y_velocity              ; child y_vel
;   dc.l anim_table_ptr          ; child anim_table (ROM)
;   dc.b anim_id                 ; starting animation
;   dc.b pad                     ; alignment
;
; In:  a0 = parent SST, a1 = descriptor table (ROM)
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
CreateChild_Complex:
        move.w  SST_sibling_ptr(a0), d3
.child_loop:
        move.w  (a1)+, d2
        beq.s   .done

        movem.l d3/a0-a1, -(sp)
        jsr     AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2
        movem.l (sp)+, d3/a0-a1

        move.w  d2, SST_code_addr(a2)

        ; Position
        move.b  (a1)+, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        move.b  (a1)+, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; Velocity
        move.w  (a1)+, SST_x_vel(a2)
        move.w  (a1)+, SST_y_vel(a2)

        ; Animation
        move.l  (a1)+, SST_anim_table(a2)
        move.b  (a1)+, SST_anim(a2)
        move.b  #$FF, SST_prev_anim(a2)
        addq.w  #1, a1                  ; skip pad byte

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Parent link + sibling chain
        move.w  a0, SST_parent_ptr(a2)
        move.w  d3, SST_sibling_ptr(a2)
        move.w  a2, d3
        move.w  a2, SST_sibling_ptr(a0)

        bra.s   .child_loop

.alloc_fail:
        movem.l (sp)+, d3/a0-a1
.skip_rest:
        ; Skip remaining bytes to find terminator
        addq.w  #2, a1                  ; x/y offsets
        addq.w  #4, a1                  ; velocity
        addq.w  #4, a1                  ; anim_table
        addq.w  #2, a1                  ; anim_id + pad
        tst.w   (a1)
        bne.s   .skip_rest
.done:
        rts
```

- [ ] **Step 3: Implement CreateChild_FlipAware**

```asm
; -----------------------------------------------
; CreateChild_FlipAware — Complex + mirror for parent X-flip
; Negates x_offset and x_vel when parent RF_XFLIP is set.
; Same descriptor format as CreateChild_Complex.
;
; In:  a0 = parent SST, a1 = descriptor table (ROM)
; Out: none
; Clobbers: d0-d4, a1-a2
; -----------------------------------------------
CreateChild_FlipAware:
        moveq   #0, d4                  ; d4 = flip flag
        btst    #RF_XFLIP, SST_render_flags(a0)
        beq.s   .no_flip
        moveq   #1, d4
.no_flip:
        move.w  SST_sibling_ptr(a0), d3
.child_loop:
        move.w  (a1)+, d2
        beq.w   .done

        movem.l d3-d4/a0-a1, -(sp)
        jsr     AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2
        movem.l (sp)+, d3-d4/a0-a1

        move.w  d2, SST_code_addr(a2)

        ; X position (negate offset if flipped)
        move.b  (a1)+, d0
        ext.w   d0
        tst.w   d4
        beq.s   .x_no_flip
        neg.w   d0
.x_no_flip:
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        ; Y position (never flipped)
        move.b  (a1)+, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; X velocity (negate if flipped)
        move.w  (a1)+, d0
        tst.w   d4
        beq.s   .xv_no_flip
        neg.w   d0
.xv_no_flip:
        move.w  d0, SST_x_vel(a2)
        move.w  (a1)+, SST_y_vel(a2)

        ; Animation
        move.l  (a1)+, SST_anim_table(a2)
        move.b  (a1)+, SST_anim(a2)
        move.b  #$FF, SST_prev_anim(a2)
        addq.w  #1, a1

        ; Inherit + flip child render_flags if parent is flipped
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)
        tst.w   d4
        beq.s   .rf_no_flip
        bset    #RF_XFLIP, SST_render_flags(a2)
.rf_no_flip:

        ; Links
        move.w  a0, SST_parent_ptr(a2)
        move.w  d3, SST_sibling_ptr(a2)
        move.w  a2, d3
        move.w  a2, SST_sibling_ptr(a0)

        bra.w   .child_loop

.alloc_fail:
        movem.l (sp)+, d3-d4/a0-a1
.skip_rest:
        lea     14(a1), a1              ; skip 14 bytes (offsets+vel+anim+pad)
        tst.w   (a1)
        bne.s   .skip_rest
.done:
        rts
```

- [ ] **Step 4: Implement CreateChild_Linked**

```asm
; -----------------------------------------------
; CreateChild_Linked — spawn a chain of identical children
; Each child's sibling_ptr links to the next child in the chain.
; Used for multi-segment objects (snake, train, beam).
;
; In:  a0 = parent SST
;      d0.w = child code_addr (objroutine value)
;      d1.w = number of children to spawn
;      d2.b = X spacing between children (signed byte)
;      d3.b = Y spacing between children (signed byte)
; Out: none
; Clobbers: d0-d5, a1-a2
; -----------------------------------------------
CreateChild_Linked:
        subq.w  #1, d1                  ; adjust for dbf
        bmi.s   .done
        move.w  d0, d4                  ; d4 = code_addr (preserved)
        move.w  d1, d5                  ; d5 = counter (preserved)
        moveq   #0, d1                  ; d1 = previous child addr

        ; Start position = parent position
        move.l  SST_x_pos(a0), -(sp)    ; save running X on stack
        move.l  SST_y_pos(a0), -(sp)    ; save running Y on stack

.spawn_loop:
        movem.l d1-d5/a0, -(sp)
        jsr     AllocDynamic
        bne.s   .link_fail
        movea.l a1, a2                  ; a2 = child SST
        movem.l (sp)+, d1-d5/a0

        move.w  d4, SST_code_addr(a2)

        ; Position from running coordinates
        move.l  4(sp), SST_x_pos(a2)   ; running X (on stack)
        move.l  (sp), SST_y_pos(a2)    ; running Y (on stack)

        ; Advance running position by spacing
        move.b  d2, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   d0, 4(sp)              ; advance running X

        move.b  d3, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   d0, (sp)               ; advance running Y

        ; Inherit from parent
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)
        move.w  a0, SST_parent_ptr(a2)

        ; Chain: previous child's sibling_ptr → this child
        tst.w   d1
        beq.s   .first_child
        movea.w d1, a1
        move.w  a2, SST_sibling_ptr(a1)
        bra.s   .linked
.first_child:
        move.w  a2, SST_sibling_ptr(a0) ; parent → first child
.linked:
        move.w  a2, d1                  ; this child becomes previous

        dbf     d5, .spawn_loop
        addq.w  #8, sp                  ; clean running position from stack
.done:
        rts

.link_fail:
        movem.l (sp)+, d1-d5/a0
        addq.w  #8, sp                  ; clean running position
        rts
```

- [ ] **Step 5: Implement DeleteChildren**

```asm
; -----------------------------------------------
; DeleteChildren — walk sibling chain from parent and delete each child
; Call before deleting the parent object.
;
; In:  a0 = parent SST
; Out: parent's sibling_ptr cleared
; Clobbers: d0-d1, a1-a2
; -----------------------------------------------
DeleteChildren:
        move.w  SST_sibling_ptr(a0), d0
        beq.s   .done                   ; no children

        clr.w   SST_sibling_ptr(a0)     ; disconnect from parent

.walk_chain:
        movea.w d0, a1                  ; a1 = current child
        move.w  SST_sibling_ptr(a1), d0 ; d0 = next child (save before delete)

        ; Delete this child (push its slot back to the free stack)
        movem.l d0/a0, -(sp)
        movea.l a1, a0                  ; DeleteObject expects a0
        jsr     DeleteObject
        movem.l (sp)+, d0/a0

        tst.w   d0                      ; more children?
        bne.s   .walk_chain
.done:
        rts
```

- [ ] **Step 6: Add include in main.asm**

After `include "engine/collision.asm"`, add:

```asm
    include "engine/children.asm"
```

- [ ] **Step 7: Build and verify**

```bash
./build.sh
```

Expected: ROM builds. No test objects use children yet, but the routines should assemble without errors. Existing test scene works unchanged.

- [ ] **Step 8: Commit**

```bash
git add engine/children.asm main.asm
git commit -m "feat(§3): add data-driven child creation (Normal, Complex, FlipAware, Linked) + DeleteChildren"
```

---

## Summary

| Task | Type | What | Key Changes |
|------|------|------|-------------|
| 1 | Cleanup | Allocation | Z-flag protocol, remove deletion sweep, clean dead code |
| 2 | Cleanup | Sprites | Y-flip, band cascade, lookup tables, dbeq limit |
| 3 | Cleanup | Animation | Flip propagation, jump table control codes, AF_DELETE |
| 4 | Cleanup | DPLC | Wire optimized data, internalize change detection |
| 5 | Feature | Children | CreateChild_Normal/Complex/FlipAware/Linked + DeleteChildren |
