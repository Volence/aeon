; Dynamic-pool churn stressor — A2 mid-walk-compact soak vehicle.
;
; Purpose: drive genuine DYNAMIC-pool churn (unlike the effect-pool churn of the
; existing ObjectTest scene, which left the dynamic pool static at 40/40 and
; never reached AllocDynamic's compact-on-full path — see
; sigil notes/2026-07-12-retro-fix-batch-packet.md, "A2 soak report").
;
; TestChurnObj is a self-replacing dynamic-pool object: each lives a short,
; staggered lifetime, then on expiry allocs a REPLACEMENT dynamic child
; (AllocDynamic, code_addr set immediately per the AllocDynamic caller
; invariant) and deletes ITSELF. Deletes zero their live-list entry but leave
; Dynamic_Live_Count unchanged until frame-end compaction, so a saturated pool
; (GameState_ObjectTestChurn spawns exactly NUM_DYNAMIC of these) rides
; Dynamic_Live_Count == NUM_DYNAMIC across a frame while deletions free stack
; slots mid-walk. When two churners expire in the same RunObjects .run_culled
; walk: the first's alloc finds the free stack empty (saturated) and fails, but
; its self-delete frees a slot; the second's alloc then finds count==NUM_DYNAMIC
; WITH a free slot -> AllocDynamic runs CompactDynamicLive mid-dispatch, the
; exact A2 precondition. In a DEBUG build the Dynamic_Live_Walking rail asserts.

CHURN_MIN_LIFE  = 4                     ; shortest lifetime (frames)
CHURN_SPREAD    = 8                     ; lifetime stagger range (power of two)

TChurnV struct
life            ds.w 1                  ; countdown to self-replace + delete
TChurnV endstruct
        objvarsCheck TChurnV_len
_churn_life     = SST_sst_custom+TChurnV_life

; -----------------------------------------------
; TestChurnObj — init (also the replacement code_addr)
; In:  a0 = SST pointer (slot allocated, x/y_pos already set by spawner)
; Out: none
; Clobbers: d0-d1, a1-a2
; -----------------------------------------------
TestChurnObj:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        move.b  #1, SST_mapping_frame(a0)
        ori.b   #4<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        move.b  #COLLISION_TOUCH, SST_collision_resp(a0)  ; TouchResponse work, non-lethal
        movea.l a0, a2
        jsr     PopulateSpawnedPieceCount
        ; Staggered lifetime = MIN + ((Frame_Counter + slot>>3) & (SPREAD-1)).
        ; slot term spreads the initial batch across positions; Frame_Counter
        ; term spreads successive replacement generations -> steady expiry.
        move.w  (Frame_Counter).w, d0
        move.w  a0, d1
        lsr.w   #3, d1
        add.w   d1, d0
        andi.w  #CHURN_SPREAD-1, d0
        addi.w  #CHURN_MIN_LIFE, d0
        move.w  d0, _churn_life(a0)
        move.w  #objroutine(TestChurnObj_Main), SST_code_addr(a0)
        ; fall through to Main for first frame

; -----------------------------------------------
; TestChurnObj_Main — per-frame: countdown; on expiry replace + self-delete
; In:  a0 = SST pointer
; Out: none  (a0/d7 preserved for the RunObjects loop contract)
; Clobbers: d0-d1, a1-a2
; -----------------------------------------------
TestChurnObj_Main:
        subq.w  #1, _churn_life(a0)
        bne.s   .draw                   ; still alive — draw

        ; Expired: alloc a replacement (code_addr set immediately), then
        ; delete self unconditionally (self-delete frees the stack slot a
        ; sibling's replacement alloc consumes mid-walk).
        move.l  a0, -(sp)               ; save self
        jsr     AllocDynamic
        bne.s   .no_replace             ; free stack empty (saturated) — skip
        move.w  #objroutine(TestChurnObj), SST_code_addr(a1)  ; invariant: set before any next alloc
        movea.l (sp), a0                ; reload self for position inherit
        move.l  SST_x_pos(a0), SST_x_pos(a1)
        move.l  SST_y_pos(a0), SST_y_pos(a1)
.no_replace:
        movea.l (sp)+, a0               ; restore self
        jsr     DeleteObject            ; self-delete (a0) — zeros entry, frees slot, sets dirty
        rts                             ; SST now zeroed — do NOT draw

.draw:
        jmp     Draw_Sprite
