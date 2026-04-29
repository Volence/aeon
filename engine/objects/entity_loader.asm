; Entity loader — type tables, section object spawn/despawn
; §4.9 section-local entity management

; -----------------------------------------------
; LoadTypeTable — copy per-section ObjDef pointer array to RAM
;
; ROM format: dc.b count, pad; dc.l ObjDef_Ptr × count
;
; In:  a0 = ROM type table pointer (count-prefixed block)
;           NULL = no types, clears table
; Out: none
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
LoadTypeTable:
        lea     (Object_Type_Table).w, a1

        move.l  a0, d1
        beq.s   .clear_all

        moveq   #0, d0
        move.b  (a0)+, d0               ; d0 = entry count
        addq.w  #1, a0                  ; skip pad byte
        tst.b   d0
        beq.s   .clear_all

        ; Copy count longwords from ROM to RAM
        move.w  d0, d1                  ; d1 = entry count (saved for zero-fill)
        subq.w  #1, d0                  ; dbf adjust

.copy_loop:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_loop

        ; Zero remaining entries to prevent stale pointers
        moveq   #MAX_OBJECT_TYPES, d0
        sub.w   d1, d0                  ; d0 = 32 - count
        beq.s   .done
        subq.w  #1, d0

.zero_loop:
        clr.l   (a1)+
        dbf     d0, .zero_loop

.done:
        rts

.clear_all:
        moveq   #MAX_OBJECT_TYPES-1, d0
.clear_loop:
        clr.l   (a1)+
        dbf     d0, .clear_loop
        rts

; -----------------------------------------------
; SpawnSectionObjects — parse object layout and spawn via Load_Object
;
; Reads 4-byte entries from ROM, extracts type/subtype/position,
; looks up ObjDef from Object_Type_Table, spawns with slot tag.
;
; In:  a0 = object layout pointer (ROM, dc.l 0 terminated)
;           NULL = no objects
;      d0.w = slot origin X (engine-space pixels)
;      d1.w = slot origin Y (engine-space pixels)
;      d2.b = slot tag (SLOT_TAG_LEFT or SLOT_TAG_RIGHT)
; Out: none
; Clobbers: d0-d5, a0-a3
; -----------------------------------------------
SpawnSectionObjects:
        move.l  a0, d3
        beq.s   .no_objects

        ; Save slot origins and tag
        move.w  d0, d4                  ; d4 = origin X
        move.w  d1, d5                  ; d5 = origin Y
        move.b  d2, d3                  ; d3.b = slot tag (low byte)

.entry_loop:
        move.l  (a0)+, d2               ; read 32-bit entry
        beq.s   .no_objects             ; terminator

        ; Save ROM pointer and entry
        movea.l a0, a3                  ; a3 = saved ROM pointer

        ; --- Extract type: bits 9-5 ---
        move.w  d2, d0
        lsr.w   #5, d0
        andi.w  #$1F, d0               ; d0.w = type index (0-31)

        ; --- Extract subtype: bits 4-0 ---
        move.w  d2, d1
        andi.w  #$1F, d1               ; d1.b = subtype
        move.b  d1, -(sp)              ; save subtype on stack

        ; --- Look up ObjDef pointer ---
        lsl.w   #2, d0                 ; type * 4 (longword index)
        lea     (Object_Type_Table).w, a1
        movea.l (a1, d0.w), a1         ; a1 = ObjDef pointer
        move.l  a1, d0
        beq.s   .skip_empty_type       ; NULL ObjDef = skip

        ; --- Extract X: bits 29-20 ---
        move.l  d2, d0
        swap    d0
        lsr.w   #4, d0
        andi.w  #$3FF, d0
        add.w   d4, d0                 ; d0 = engine-space X

        ; --- Extract Y: bits 19-10 ---
        move.l  d2, d1
        lsr.l   #8, d1
        lsr.w   #2, d1
        andi.w  #$3FF, d1
        add.w   d5, d1                 ; d1 = engine-space Y

        ; d0=X, d1=Y, a1=ObjDef, subtype on stack
        move.b  (sp)+, d2              ; d2.b = subtype

        jsr     Load_Object
        bne.s   .spawn_next            ; alloc failed — skip tag

        ; Tag the spawned object with slot ID
        move.b  d3, SLOT_TAG_OFFSET(a1)  ; a1 = new SST from Load_Object

.spawn_next:
        movea.l a3, a0                 ; restore ROM pointer
        bra.s   .entry_loop

.skip_empty_type:
        addq.w  #2, sp                 ; pop saved subtype (byte push uses word on 68000)
        movea.l a3, a0
        bra.s   .entry_loop

.no_objects:
        rts

; -----------------------------------------------
; DespawnSlotObjects — delete all dynamic objects with matching slot tag
;
; In:  d0.b = slot tag to match (SLOT_TAG_LEFT or SLOT_TAG_RIGHT)
; Out: none
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
DespawnSlotObjects:
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d1      ; dbf counter

.scan_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .next_slot              ; empty slot

        cmp.b   SLOT_TAG_OFFSET(a0), d0
        bne.s   .next_slot              ; different tag or untagged

        ; Save loop state across DeleteObject (clobbers d0, a1)
        movem.l d0-d1/a0, -(sp)
        jsr     DeleteObject
        movem.l (sp)+, d0-d1/a0

.next_slot:
        lea     SST_len(a0), a0
        dbf     d1, .scan_loop
        rts

; -----------------------------------------------
; Section_LoadSlotEntities — load type table, spawn objects, expand rings
;
; Orchestrates the three entity-loading primitives for one slot:
; 1. LoadTypeTable from sec_type_table
; 2. SpawnSectionObjects from sec_objects with slot tag
; 3. ExpandRings from sec_rings into ring buffer
;
; In:  a0 = Sec ptr (ROM section definition)
;      d0.b = slot tag (SLOT_TAG_LEFT or SLOT_TAG_RIGHT)
;      d4.w = slot origin X (engine-space pixels)
;      d5.w = slot origin Y (engine-space pixels)
;      a4 = ring buffer ptr (Ring_Buffer_0 or Ring_Buffer_1)
;      a5 = ring count byte ptr (Ring_Count_0 or Ring_Count_1)
; Out: none
; Clobbers: d0-d6, a0-a5
; -----------------------------------------------
Section_LoadSlotEntities:
        movem.l d0/d4-d5/a0/a4-a5, -(sp)

        ; 1. Load type table
        movea.l Sec_sec_type_table(a0), a0
        bsr.w   LoadTypeTable

        ; 2. Spawn objects
        movem.l (sp), d0/d4-d5/a0/a4-a5    ; peek (don't pop)
        move.b  d0, d2                      ; d2.b = slot tag
        move.w  d4, d0                      ; d0.w = origin X
        move.w  d5, d1                      ; d1.w = origin Y
        movea.l Sec_sec_objects(a0), a0
        bsr.w   SpawnSectionObjects

        ; 3. Expand rings
        movem.l (sp)+, d0/d4-d5/a0/a4-a5   ; pop
        movea.l Sec_sec_rings(a0), a0
        movea.l a4, a1
        move.w  d4, d0                      ; origin X
        move.w  d5, d1                      ; origin Y
        bsr.w   ExpandRings
        move.b  d0, (a5)                    ; store expanded ring count
        rts
