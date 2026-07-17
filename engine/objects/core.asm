; Object system core — allocation, dispatch, deletion

; -----------------------------------------------
; InitObjectRAM — clear all slots, push addresses to free stacks
; Called at game state init (level start, etc.)
; In:  none
; Out: none
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
InitObjectRAM:
        ; Zero all Object RAM
        lea     (Object_RAM).w, a0
        move.w  #(Object_RAM_End-Object_RAM)/4-1, d0
        moveq   #0, d1
.clear:
        move.l  d1, (a0)+
        dbf     d0, .clear

        ; Init dynamic free stack — push slot addresses low-to-high (slot 2
        ; pushed first ... slot 41 pushed last). Pops are LIFO, so the
        ; LAST-pushed (highest) slot is allocated first; the pool fills
        ; downward toward slot 2.
        lea     (Dynamic_Free_Stack).w, a0
        lea     (Dynamic_Slots).w, a1
        move.w  #NUM_DYNAMIC-1, d0
.push_dyn:
        move.w  a1, (a0)+
        lea     SST_len(a1), a1
        dbf     d0, .push_dyn
        move.w  #Dynamic_Free_Stack+NUM_DYNAMIC*2, (Dynamic_Free_SP).w

        ; Init effect free stack
        lea     (Effect_Free_Stack).w, a0
        lea     (Effect_Slots).w, a1
        move.w  #NUM_EFFECTS-1, d0
.push_eff:
        move.w  a1, (a0)+
        lea     SST_len(a1), a1
        dbf     d0, .push_eff
        move.w  #Effect_Free_Stack+NUM_EFFECTS*2, (Effect_Free_SP).w

        ; Reset the dynamic live-list (spawn-order occupancy): empty, not dirty.
        ; The Dynamic_Live array itself needs no clear — Count 0 means no entry
        ; is valid. d1 still 0 from the .clear loop.
        move.w  d1, (Dynamic_Live_Count).w
        move.b  d1, (Dynamic_Live_Dirty).w

        ; Reset spawn counter (d1 still 0 from .clear loop)
        move.w  d1, (Spawn_Count).w
        rts

; -----------------------------------------------
; AllocDynamic — pop a free dynamic slot
; In:  none
; Out: a1 = SST address of allocated slot (d0=0/Z set on success)
;      d0=1/Z clear if pool exhausted
;      Slot is tagged SLOT_TAG_UNTAGGED on return.
; Clobbers: d0
; CALLER INVARIANT (item 3): the caller MUST write the returned slot's code_addr
; before the NEXT AllocDynamic. The append-on-full guard runs CompactDynamicLive,
; which treats code_addr==0 as dead and drops the slot — a caller that allocs a
; second slot before initializing the first would silently lose the first (a
; claimed-but-invisible zombie), reachable only at a full count. All current
; callers write code_addr immediately (children/load_object/object_test emitters).
; -----------------------------------------------
AllocDynamic:
        cmpi.w  #Dynamic_Free_Stack, (Dynamic_Free_SP).w
        beq.s   .full
        movea.w (Dynamic_Free_SP).w, a1
        subq.w  #2, (Dynamic_Free_SP).w
        movea.w -(a1), a1
        move.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a1)
        ; Spawn-order occupancy: append the popped slot to the live list
        ; (Dynamic_Live[Count++] = a1), UNIQUE by construction — DeleteObject (A1)
        ; zeroed any prior entry for this slot. a0 saved LONG (callers hold a
        ; 32-bit ROM ptr). Spawn-time only.
        ; A2 overflow latch (spec §9): at a FULL live list, latch the popped slot
        ; for the frame-end drain instead of compacting mid-frame under a held
        ; walker cursor (the A2 hazard). The slot IS allocated (caller sets
        ; code_addr); it joins Dynamic_Live at the frame-end drain and first
        ; dispatches NEXT frame (misses same-frame TouchResponse). The live list
        ; is never mutated mid-frame by the alloc path now.
        cmpi.w  #NUM_DYNAMIC, (Dynamic_Live_Count).w
        bne.s   .append
        cmpi.w  #NUM_DYNAMIC_PENDING, (Dynamic_Live_Pending_Count).w
        beq.s   .latch_full            ; latch full → roll back the pop, alloc-fail
        move.l  a0, -(sp)
        lea     (Dynamic_Live_Pending).w, a0
        move.w  (Dynamic_Live_Pending_Count).w, d0
        add.w   d0, d0                 ; word index -> byte offset
        move.w  a1, (a0,d0.w)
        addq.w  #1, (Dynamic_Live_Pending_Count).w
        movea.l (sp)+, a0
        moveq   #0, d0                 ; Z set = success (latched; dispatches next frame)
        rts
.append:
        move.l  a0, -(sp)
        lea     (Dynamic_Live).w, a0
        move.w  (Dynamic_Live_Count).w, d0
        add.w   d0, d0                  ; word index -> byte offset
        move.w  a1, (a0,d0.w)
        addq.w  #1, (Dynamic_Live_Count).w
        movea.l (sp)+, a0
        moveq   #0, d0                  ; Z set = success
        rts
.latch_full:
        ; The slot was already popped before the full count was known; return it
        ; to the free stack so it is not leaked (re-exposed at the current SP).
        addq.w  #2, (Dynamic_Free_SP).w
.full:
        moveq   #1, d0                  ; Z clear = pool exhausted (or latch full)
        rts

; -----------------------------------------------
; AllocEffect — pop a free effect slot
; In:  none
; Out: a1 = SST address of allocated slot (d0=0/Z set on success)
;      d0=1/Z clear if pool exhausted
; Clobbers: d0
; -----------------------------------------------
AllocEffect:
        cmpi.w  #Effect_Free_Stack, (Effect_Free_SP).w
        beq.s   .full
        movea.w (Effect_Free_SP).w, a1
        subq.w  #2, (Effect_Free_SP).w
        movea.w -(a1), a1
        ; No slot_tag write (unlike AllocDynamic): slot_tag is the entity-window
        ; quadrant index, read ONLY by the entity-window Y-despawn band. Effects
        ; are never entity-window-managed (object code allocs them and they
        ; self-delete), so their slot_tag is never read — nothing to initialize.
        moveq   #0, d0
        rts
.full:
        moveq   #1, d0
        rts

; -----------------------------------------------
; DeleteObject — push slot back to appropriate free stack, zero SST
; Pool detection (RAM order: Player | Dynamic | System | Effect):
;   addr < Dynamic_Slots           → player slot (no stack push)
;   addr >= Dynamic_Slots AND
;          addr < System_Slots     → dynamic pool
;   addr >= System_Slots AND
;          addr < Effect_Slots     → system slot (no stack push)
;   addr >= Effect_Slots AND
;          addr < Effect_Slots+
;                 SST_len*NUM_EFFECTS → effect pool
; In:  a0 = SST address of object to delete
; Out: none
; Clobbers: d0, a1
; -----------------------------------------------
DeleteObject:
    ifdef __DEBUG__
        ; DEBUG rails (item 2): a0 must point at a live SST inside Object_RAM.
        ; An out-of-range a0 falls to .clear_slot and zeroes wild memory; a
        ; code_addr==0 slot is an already-deleted (double-delete) slot whose
        ; re-push corrupts the free stack. d0 is clobbered — free as scratch.
        assert.l a0, hs, #Object_RAM
        assert.l a0, lo, #Object_RAM_End
        move.w  SST_code_addr(a0), d0
        assert.w d0, ne, #0
    endif
        ; Check Effect pool first (highest address range)
        cmpa.w  #Effect_Slots, a0
        bhs.s   .check_effect

        ; Below Effect_Slots — check System_Slots
        cmpa.w  #System_Slots, a0
        bhs.s   .clear_slot             ; system slot: just clear, no push

        ; Below System_Slots — check Dynamic_Slots
        cmpa.w  #Dynamic_Slots, a0
        bhs.s   .dynamic_pool

        ; Below Dynamic_Slots — player slot: just clear, no push
        bra.s   .clear_slot

.check_effect:
        ; Past Effect_Slots — confirm it's within the effect range
        cmpa.w  #Effect_Slots+SST_len*NUM_EFFECTS, a0
        bhs.s   .clear_slot             ; out of effect range (shouldn't happen)
        ; Fall through: it's a valid effect slot

.effect_pool:
        movea.w (Effect_Free_SP).w, a1
        move.w  a0, (a1)+
        move.w  a1, (Effect_Free_SP).w
        bra.s   .clear_slot

.dynamic_pool:
        movea.w (Dynamic_Free_SP).w, a1
        move.w  a0, (a1)+
        move.w  a1, (Dynamic_Free_SP).w
        st      (Dynamic_Live_Dirty).w  ; dynamic deletion -> compact live list at frame end
        ; A1: ZERO this slot's live-list entry so a same-frame LIFO realloc can't
        ; list it twice (the permanent-duplicate hazard, §6). <=NUM_DYNAMIC-word
        ; scan, deletes rare; zeroing moves nothing (cursor-safe). d1 saved — not
        ; in the clobber contract.
        move.w  d1, -(sp)
        move.w  a0, d1                  ; d1 = low16(slot addr) = the entry to find
        lea     (Dynamic_Live).w, a1
        move.w  (Dynamic_Live_Count).w, d0
        beq.s   .dyn_zero_pending
        subq.w  #1, d0
.dyn_zero_scan:
        cmp.w   (a1)+, d1
        beq.s   .dyn_zero_hit
        dbf     d0, .dyn_zero_scan
        bra.s   .dyn_zero_pending
.dyn_zero_hit:
        clr.w   -(a1)                  ; (a1)+ passed the match; step back and zero it
.dyn_zero_pending:
        ; A2: also zero a matching PENDING-latch entry — a slot latched this frame
        ; (allocated, not yet in the live list) can be deleted the same frame; the
        ; stale latch entry would make the drain re-append (LIFO re-latch would
        ; double it). Same exactly-once fix as the live-list zero above.
        lea     (Dynamic_Live_Pending).w, a1
        move.w  (Dynamic_Live_Pending_Count).w, d0
        beq.s   .dyn_zero_done
        subq.w  #1, d0
.dyn_pend_scan:
        cmp.w   (a1)+, d1
        beq.s   .dyn_pend_hit
        dbf     d0, .dyn_pend_scan
        bra.s   .dyn_zero_done
.dyn_pend_hit:
        clr.w   -(a1)
.dyn_zero_done:
        move.w  (sp)+, d1

.clear_slot:
        ; Zero all $50 bytes of the SST entry
        moveq   #0, d0
        move.l  d0, (a0)+       ; $00
        move.l  d0, (a0)+       ; $04
        move.l  d0, (a0)+       ; $08
        move.l  d0, (a0)+       ; $0C
        move.l  d0, (a0)+       ; $10
        move.l  d0, (a0)+       ; $14
        move.l  d0, (a0)+       ; $18
        move.l  d0, (a0)+       ; $1C
        move.l  d0, (a0)+       ; $20
        move.l  d0, (a0)+       ; $24
        move.l  d0, (a0)+       ; $28
        move.l  d0, (a0)+       ; $2C
        move.l  d0, (a0)+       ; $30
        move.l  d0, (a0)+       ; $34
        move.l  d0, (a0)+       ; $38
        move.l  d0, (a0)+       ; $3C
        move.l  d0, (a0)+       ; $40
        move.l  d0, (a0)+       ; $44
        move.l  d0, (a0)+       ; $48
        move.l  d0, (a0)+       ; $4C
        lea     -SST_len(a0), a0 ; restore a0 to slot start
        rts

; -----------------------------------------------
; CompactDynamicLive — reconcile the dynamic live-list (see core.emp)
; Keeps nonzero + live-code_addr entries in place, drops zeroed (A1 delete) and
; dead-code_addr entries alike, recounts, clears dirty. Because it MOVES entries
; down, it MUST run only when no dynamic live-list walk holds a cursor. Post A2
; (spec §9) it is called ONLY from the RunObjects frame-end reconcile (no walk
; live) — AllocDynamic's full-count path now LATCHES instead of compacting, so
; the mid-walk-compact hazard is gone. The DEBUG Dynamic_Live_Walking rail
; asserts the walk flag is clear here as a regression guard (should never fire).
; The §6-2/§6-3 post-state asserts moved to DrainDynamicPending (verify the list
; AFTER the latch drain appends).
; In: none  Out: none  Clobbers: d0, d1, a0, a1, a2
; -----------------------------------------------
CompactDynamicLive:
    ifdef __DEBUG__
        ; A2 rail (item 1): a live-list walk must NOT be in progress — compaction
        ; moves entries down under any held cursor (the mid-walk double-dispatch
        ; hazard). d0 is free at entry. Byte-neutral in release.
        move.b  (Dynamic_Live_Walking).w, d0
        assert.b d0, eq, #0
    endif
        lea     (Dynamic_Live).w, a0    ; read cursor
        lea     (Dynamic_Live).w, a1    ; write cursor (compacts down over drops)
        move.w  (Dynamic_Live_Count).w, d1
        assert.w d1, ls, #NUM_DYNAMIC   ; §6 (1): count never exceeds capacity
        beq.s   .recount
        subq.w  #1, d1
.loop:
        move.w  (a0)+, d0               ; entry word
        beq.s   .next                   ; zeroed (A1 delete) — drop
        movea.w d0, a2
        tst.w   (a2)                    ; slot code_addr
        beq.s   .next                   ; dead slot — drop
        move.w  d0, (a1)+               ; keep — copy down
.next:
        dbf     d1, .loop
.recount:
        lea     (Dynamic_Live).w, a0    ; new count = (write - base) / 2
        suba.l  a0, a1
        move.w  a1, d0
        lsr.w   #1, d0
        move.w  d0, (Dynamic_Live_Count).w
        sf      (Dynamic_Live_Dirty).w
        rts

; -----------------------------------------------
; DrainDynamicPending — append the A2 overflow latch to the live list (spec §9).
; Runs at the RunObjects frame-end reconcile, right AFTER CompactDynamicLive
; (which reclaimed room from the frame's deletions). Appends each non-zero
; Dynamic_Live_Pending entry to Dynamic_Live IN ALLOC ORDER (spawn-order
; preserved; a latched spawn first runs NEXT frame); a zeroed entry
; (deleted-while-latched, DeleteObject A2) is dropped. Clears the latch count.
; Room is guaranteed (no overflow): occupied slots (live list + non-zero latch)
; <= NUM_DYNAMIC, since each occupied slot has exactly one live entry in the list
; OR the latch (never both), so room >= latch entries. See core.emp / spec §9.
; In: none  Out: none  Clobbers: d0, d1, d2, a0, a1
; -----------------------------------------------
DrainDynamicPending:
        move.w  (Dynamic_Live_Pending_Count).w, d1
        beq.s   .clear                  ; empty (dirty-only reconcile) — nothing to append
        subq.w  #1, d1
        lea     (Dynamic_Live_Pending).w, a0
        lea     (Dynamic_Live).w, a1
        move.w  (Dynamic_Live_Count).w, d0
        add.w   d0, d0                  ; d0 = live byte offset (append cursor)
.drain_loop:
        move.w  (a0)+, d2               ; latched entry
        beq.s   .drain_next             ; zeroed (deleted while latched) — drop
        move.w  d2, (a1,d0.w)           ; append in alloc order → spawn-order preserved
        addq.w  #2, d0
        addq.w  #1, (Dynamic_Live_Count).w
.drain_next:
        dbf     d1, .drain_loop
.clear:
        clr.w   (Dynamic_Live_Pending_Count).w
    ifdef __DEBUG__
        ; §6-2/§6-3 on the FINAL reconciled list (moved from CompactDynamicLive,
        ; which now runs pre-drain): post-drain count == a full-pool tst.w live
        ; sweep (no duplicate, none missing — the A1 double-dispatch check; count
        ; == occupied <= NUM_DYNAMIC is the §9 room proof), every entry in-pool.
        move.w  (Dynamic_Live_Count).w, d0
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d1
.drain_sweep_loop:
        tst.w   (a0)
        beq.s   .drain_sweep_next
        subq.w  #1, d0
.drain_sweep_next:
        lea     SST_len(a0), a0
        dbf     d1, .drain_sweep_loop
        assert.w d0, eq, #0
        move.w  (Dynamic_Live_Count).w, d1
        beq.w   .drain_dbg_done
        lea     (Dynamic_Live).w, a0
        subq.w  #1, d1
.drain_entry_check:
        movea.w (a0)+, a1
        assert.l a1, hs, #Object_RAM
        assert.l a1, lo, #Object_RAM_End
        dbf     d1, .drain_entry_check
.drain_dbg_done:
    endif
        rts

; -----------------------------------------------
; RunObjects — dispatch all active object slots
; Per-pool loops: players/system/effects always execute,
; dynamic pool is culled by distance from camera.
; Objects that want to die call DeleteObject directly.
;
; Convention: object routines receive a0 = self SST pointer.
; Object routines MUST preserve a0 and d7.
; In:  none
; Out: none
; Clobbers: d0-d6, a0-a6 (object code may clobber freely except a0/d7)
; -----------------------------------------------
RunObjects:
        moveq   #0, d0
        move.w  d0, (Spawn_Count).w

        tst.b   (Game_Paused).w
        ; LOCKSTEP core.emp: .emp uses a bare `bne` that sigil width-selects.
        ; Since the object-pool occupancy step-2 retrofit grew .run_culled, the
        ; plain-shape disp to RunObjects_Frozen now also exceeds .s (it fit .s
        ; pre-step-2), so BOTH shapes force .w — the twin drops the ifdef split.
        bne.w   RunObjects_Frozen

        ; --- Player slots (always execute) ---
        lea     (Player_1).w, a0
        move.w  #NUM_PLAYERS-1, d7
        bsr.s   .run_always

        ; --- Dynamic slots (culled by distance, walked in spawn order via
        ;     the live list — empty slots cost zero; .run_culled sets up its
        ;     own cursor + count) ---
        bsr.s   .run_culled

        ; --- System slots (always execute) ---
        lea     (System_Slots).w, a0
        move.w  #NUM_SYSTEM-1, d7
        bsr.s   .run_always

        ; --- Effect slots (always execute) ---
        lea     (Effect_Slots).w, a0
        move.w  #NUM_EFFECTS-1, d7
        bsr.s   .run_always

        ; --- Frame-end reconcile (step 6 + A2 §9): every walk is done (no walk
        ;     live), so CompactDynamicLive can move entries down, then
        ;     DrainDynamicPending appends the overflow latch IN ALLOC ORDER.
        ;     Runs when a deletion dirtied the list OR the latch holds pending
        ;     spawns (latch non-empty => dirty by construction; the OR guards
        ;     against ever leaking a latched object). O(1) on a quiet frame.
        ;     LOCKSTEP core.emp: the two jbsr widths are hand-set to sigil's
        ;     per-shape relaxation (backward disp; the debug shape's larger
        ;     CompactDynamicLive/DrainDynamicPending push it past .s).
        tst.b   (Dynamic_Live_Dirty).w
        bne.s   .reconcile
        tst.w   (Dynamic_Live_Pending_Count).w
        beq.s   .no_reconcile
.reconcile:
        bsr.w   CompactDynamicLive      ; .w both shapes (disp past .s: plain -158, debug -666)
    ifdef __DEBUG__
        bsr.w   DrainDynamicPending     ; debug: disp -432 → .w
    else
        bsr.s   DrainDynamicPending     ; plain: disp -110 → .s (sigil relaxes per shape)
    endif
.no_reconcile:
        rts

; Dispatch loop — no culling
.run_always:
.always_loop:
        moveq   #OBJ_CODE_BANK, d0
        swap    d0
        move.w  (a0), d0
        beq.s   .always_next
        movea.l d0, a1
        jsr     (a1)
        ; debug builds: catch object routines violating the a0/d7
        ; preservation contract at the source
        ifdebug bsr.s Debug_AssertObjLoop  ; LOCKSTEP core.emp C-A1: jbsr shrink (was bsr.w; Debug_AssertObjLoop is near → disp reaches .s → −2 bytes, DEBUG shape only)
.always_next:
        lea     SST_len(a0), a0
        dbf     d7, .always_loop
        rts

; Dispatch loop — dynamic pool, walked in SPAWN order via the live list.
; Empty slots cost ZERO (never appended); a dead-but-uncompacted entry costs
; one tst.w guard. d7 snapshots the count at entry (a child appended mid-walk
; runs NEXT frame). a2 = list cursor, saved across dispatch (object code may
; clobber it — only a0/d7 are preserved).
.run_culled:
    ifdef __DEBUG__
        ; A2 rail (item 1): dispatched object code may AllocDynamic mid-walk while
        ; a2 holds a live cursor — flag the walk so a resulting CompactDynamicLive
        ; trips the assert instead of moving entries silently.
        st      (Dynamic_Live_Walking).w
    endif
        lea     (Dynamic_Live).w, a2
        move.w  (Dynamic_Live_Count).w, d7
        beq.s   .culled_done
        subq.w  #1, d7
.culled_loop:
        move.w  (a2)+, d0               ; A1: load entry, null-guard a zeroed
        beq.s   .culled_next            ;     entry (same-frame delete) — no deref
        movea.w d0, a0
        tst.w   (a0)                    ; truth guard: skip a dead-uncompacted slot
        beq.s   .culled_next

        ; X distance check: abs(obj_x - camera_x)
        move.w  SST_x_pos(a0), d0
        sub.w   (Camera_X).w, d0
        bpl.s   .culled_xpos
        neg.w   d0
.culled_xpos:
        cmpi.w  #CULL_DISTANCE_X, d0
        bhi.s   .culled_next

        ; Y distance check: abs(obj_y - camera_y)
        move.w  SST_y_pos(a0), d0
        sub.w   (Camera_Y).w, d0
        bpl.s   .culled_ypos
        neg.w   d0
.culled_ypos:
        cmpi.w  #CULL_DISTANCE_Y, d0
        bhi.s   .culled_next

        ; Within range — dispatch (a2 saved: object code may clobber it)
        moveq   #OBJ_CODE_BANK, d0
        swap    d0
        move.w  (a0), d0
        movea.l d0, a1
        move.l  a2, -(sp)
        jsr     (a1)
        movea.l (sp)+, a2
        ifdebug bsr.s Debug_AssertObjLoop  ; LOCKSTEP core.emp: preservation-contract check
.culled_next:
        dbf     d7, .culled_loop
.culled_done:
    ifdef __DEBUG__
        sf      (Dynamic_Live_Walking).w
    endif
        rts

    ifdef __DEBUG__
; -----------------------------------------------
; Debug_AssertObjLoop — verify the RunObjects loop contract after dispatch
; Object routines must return with a0 = own SST and d7 = loop counter
; intact. A violation here means object routines clobbered a0/d7,
; causing free-stack words to dispatch as code offsets.
; In:  a0 = slot just dispatched, d7 = loop counter
; Out: none (raises debugger error on violation)
; Clobbers: none
; -----------------------------------------------
Debug_AssertObjLoop:
        assert.l a0, hs, #Object_RAM
        assert.l a0, lo, #Object_RAM_End
        assert.w d7, lo, #NUM_DYNAMIC
        rts
    endif

; -----------------------------------------------
; RunObjects_Frozen — render-only pass (player death, pause)
; Player + system + effect keep small fixed sweeps (26 slots); the dynamic
; segment walks the spawn-order live list, so paused frames skip the ~37 empty
; dynamic slots too.
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
RunObjects_Frozen:
        ; Players (fixed sweep, 2 slots)
        lea     (Player_1).w, a0
        move.w  #NUM_PLAYERS-1, d7
        bsr.s   .frozen_fixed

        ; Dynamic pool — spawn-order live list (empty slots cost zero). a2 is the
        ; cursor; Draw_Sprite preserves a0/d7/a2, so no save is needed.
    ifdef __DEBUG__
        ; A2 rail (item 1): Draw_Sprite doesn't alloc today, but flag the walk so
        ; the CompactDynamicLive assert stays TOTAL if it ever gains a spawn.
        st      (Dynamic_Live_Walking).w
    endif
        lea     (Dynamic_Live).w, a2
        move.w  (Dynamic_Live_Count).w, d7
        beq.s   .frozen_dyn_done
        subq.w  #1, d7
.frozen_dyn_loop:
        move.w  (a2)+, d0               ; A1: null-guard a zeroed entry — no deref
        beq.s   .frozen_dyn_next
        movea.w d0, a0
        tst.w   (a0)                    ; truth guard: dead-but-uncompacted slot
        beq.s   .frozen_dyn_next
        bsr.s   Draw_Sprite
.frozen_dyn_next:
        dbf     d7, .frozen_dyn_loop
.frozen_dyn_done:
    ifdef __DEBUG__
        sf      (Dynamic_Live_Walking).w
    endif

        ; System + Effect (fixed sweep, contiguous 24 slots)
        lea     (System_Slots).w, a0
        move.w  #NUM_SYSTEM+NUM_EFFECTS-1, d7
        bsr.s   .frozen_fixed
        rts

; Fixed-pool sweep — Draw each occupied slot across an [a0 .. a0+d7] run
.frozen_fixed:
.frozen_fixed_loop:
        tst.w   (a0)
        beq.s   .frozen_fixed_next
        bsr.s   Draw_Sprite
.frozen_fixed_next:
        lea     SST_len(a0), a0
        dbf     d7, .frozen_fixed_loop
        rts

; -----------------------------------------------
; ObjectMove — apply velocity to position (X and Y)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMove:
        move.w  SST_x_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_x_pos(a0)
        move.w  SST_y_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_y_pos(a0)
        rts

; -----------------------------------------------
; ObjectMoveX — apply X velocity only
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMoveX:
        move.w  SST_x_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_x_pos(a0)
        rts

; -----------------------------------------------
; ObjectMoveY — apply Y velocity only (gravity, falling)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMoveY:
        move.w  SST_y_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_y_pos(a0)
        rts
