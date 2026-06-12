; AS functions, macros, and compile-time utilities

; -----------------------------------------------
; AS functions — build-time computation
; -----------------------------------------------

; VDP command word generation
vdpComm     function addr,type,rwd, \
              (((type & rwd) & 3) << 30) | ((addr & $3FFF) << 16) | (((type & rwd) & $FC) << 2) | ((addr & $C000) >> 14)

; VDP register command
vdpReg      function reg,val, ($8000 | ((reg) << 8) | (val))

; Art tile encoding
vram_art    function tile,pal,pri, (pri<<15)|(pal<<13)|tile

; Tile index to VDP byte address
vram_bytes  function tile, tile<<5

; Sprite size encoding (width/height in cells, 1-4)
sprSize     function w,h, ((((h)-1)<<2)|((w)-1))<<8

; Byte count to longword loop count (for dbf)
bytesToLcnt function n, (n)/4-1

; VDP command delta — scrambled offset for row advancement in PlaneMapToVRAM
vdpCommDelta    function addr, (((addr)&$3FFF)<<16)|(((addr)&$C000)>>14)

; Plane cell byte offset — offset for cell (col, row) in plane of given width
planeLoc        function width,col,row, (((width)*(row)+(col))*2)

; DMA source word address (bit 23 cleared for RAM safety)
dmaSource       function addr, (((addr)>>1)&$7FFFFF)

; DMA length in words
dmaLength       function bytes, (((bytes)>>1)&$FFFF)

; Object code offset from ObjCodeBase (word — stored at SST $00)
; Usage: move.w #objroutine(MyObject), code_addr(a0)
; ObjCodeBase is defined in main.asm at align $10000
objroutine  function x, (x)-ObjCodeBase

; -----------------------------------------------
; Struct macros
; -----------------------------------------------
; AS has built-in struct/endstruct:
;   Label struct / Label endstruct
; Auto-generates Label_len. No custom macros needed.

; objvarsCheck — assert a per-object custom struct fits sst_custom.
; MANDATORY after every sst_custom overlay struct — aborts the build
; on overflow with the excess byte count.
; Usage:  MyV struct
;           field ds.w 1
;         MyV endstruct
;         objvarsCheck MyV_len
; Short accessor equates are then derived from the struct:
;         _field = SST_sst_custom+MyV_field
objvarsCheck macro structlen
    if (structlen) > SST_CUSTOM_SIZE
        fatal "object custom vars overflow sst_custom by \{(structlen)-SST_CUSTOM_SIZE} bytes"
    endif
        endm

; -----------------------------------------------
; objdef — emit a v2 archetype template (26 bytes):
; a verbatim ROM image of SST $00 (code_addr) + $0A-$21 (template block;
; $20-$21 are pad, overwritten by Load_Object's runtime init).
; All params optional except code/map. Example:
;   objdef code=TestEnemy_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
;          zpri=4, xvel=ENEMY_PATROL_SPEED, wdth=16, hght=16, col=COLLISION_HURT
;
; Parameter name notes (AS Macro Assembler quirk):
;   AS substitutes params token-wise for identifiers, but ALSO into
;   SIZE-ATTRIBUTE SUFFIXES — a param named `w` turns `dc.w`/`move.w`
;   into `dc.<value>` (verified empirically against asl 1.42 Bld 212;
;   whole identifiers like RF_PRIORITY_SHIFT are NOT at risk, nor are
;   comments). Hence w → wdth and h → hght are REQUIRED; pri → zpri
;   and rf → rfbits are belt-and-braces. Local temporaries use the
;   ODZ_ prefix.
; -----------------------------------------------
objdef macro code,map,art,zpri,xvel,yvel,wdth,hght,col,anims,anim,sub,rfbits,statbits
    if "code" = ""
        fatal "objdef: code required"
    endif
    if "map" = ""
        fatal "objdef: map required"
    endif
ODZ_TL set 0
    if "art" <> ""
ODZ_TL set art
    endif
ODZ_PB set 0
    if "zpri" <> ""
ODZ_PB set zpri
    endif
    if ODZ_PB > 7
        fatal "objdef: priority exceeds 7"
    endif
ODZ_XV set 0
    if "xvel" <> ""
ODZ_XV set xvel
    endif
ODZ_YV set 0
    if "yvel" <> ""
ODZ_YV set yvel
    endif
ODZ_WD set 0
    if "wdth" <> ""
ODZ_WD set wdth
    endif
ODZ_HT set 0
    if "hght" <> ""
ODZ_HT set hght
    endif
ODZ_RESP set 0
    if "col" <> ""
ODZ_RESP set col
    endif
ODZ_ATBL set 0
    if "anims" <> ""
ODZ_ATBL set anims
    endif
ODZ_ANI set 0
    if "anim" <> ""
ODZ_ANI set anim
    endif
ODZ_SDEF set 0
    if "sub" <> ""
ODZ_SDEF set sub
    endif
ODZ_RFVAL set 0
    if "rfbits" <> ""
ODZ_RFVAL set rfbits
    endif
ODZ_BITS set 0
    if "statbits" <> ""
ODZ_BITS set statbits
    endif
ODZ_START set *
        dc.w objroutine(code)                           ; $00 code_addr
        dc.w ODZ_XV, ODZ_YV                             ; $0A x_vel, $0C y_vel
        dc.b ODZ_RFVAL|(ODZ_PB<<RF_PRIORITY_SHIFT)      ; $0E render_flags (priority in bits 5-7)
        dc.b ODZ_RESP                                   ; $0F collision_resp
        dc.l map                                        ; $10 mappings
        dc.w ODZ_TL                                     ; $14 art_tile
        dc.b ODZ_WD, ODZ_HT                             ; $16 width, $17 height
        dc.b ODZ_ANI, ODZ_SDEF                          ; $18 anim, $19 subtype default
        dc.l ODZ_ATBL                                   ; $1A anim_table
        dc.b ODZ_BITS, 0                                ; $1E status, $1F angle
        dc.w 0                                          ; $20-$21 pad (copied, then re-inited)
    if (*-ODZ_START) <> 26
        fatal "objdef emitted \{*-ODZ_START} bytes, expected 26"
    endif
        endm

; -----------------------------------------------
; objentry / objend — guarded object placement list entries.
; Build-fails on: non-monotonic X (breaks the scan's sorted early-out),
; coords outside the section, type/subtype overflow, list longer than
; the killed-bitmask capacity (MAX_LIST_ENTRIES).
; Usage:
;   Sec_Objects:
;       objentry $100, $0B0, 1          ; x, y, type [, subtype] [, oflags]
;       objentry $600, $0B0, 0
;       objend
; oflags = OEF_* bit numbers pre-shifted by the caller, e.g. (1<<OEF_XFLIP)
; -----------------------------------------------
OE_PREV_X set 0
OE_COUNT set 0

objentry macro px,py,ptype,psub,pflags
    if "px" = ""
        fatal "objentry: x required"
    endif
OE_SUB set 0
    if "psub" <> ""
OE_SUB set psub
    endif
OE_FLG set 0
    if "pflags" <> ""
OE_FLG set pflags
    endif
    if (OE_FLG & $1FFF) <> 0
        fatal "objentry: flags overlap type/subtype bits — pass pre-shifted masks like (1<<OEF_XFLIP)"
    endif
    if (px) < 0
        fatal "objentry: x \{px} outside section"
    endif
    if (px) > SECTION_SIZE-1
        fatal "objentry: x \{px} outside section"
    endif
    if (py) < 0
        fatal "objentry: y \{py} outside section"
    endif
    if (py) > SECTION_SIZE-1
        fatal "objentry: y \{py} outside section"
    endif
    if (ptype) > OEF_TYPE_MASK
        fatal "objentry: type \{ptype} exceeds 31"
    endif
    if OE_SUB > OEF_SUBTYPE_MASK
        fatal "objentry: subtype exceeds 255"
    endif
    if (px) < OE_PREV_X
        fatal "objentry: X \{px} not >= previous \{OE_PREV_X} — lists must be X-sorted"
    endif
OE_PREV_X set px
OE_COUNT set OE_COUNT+1
    if OE_COUNT > MAX_LIST_ENTRIES
        fatal "objentry: list exceeds MAX_LIST_ENTRIES (killed-bitmask capacity)"
    endif
        dc.w px, py, OE_FLG|((ptype)<<OEF_TYPE_SHIFT)|OE_SUB
        endm

objend macro
        dc.w -1
OE_PREV_X set 0
OE_COUNT set 0
        endm

; -----------------------------------------------
; Hardware control macros
; -----------------------------------------------

stopZ80 macro
        move.w  #$0100, (Z80_BUS_REQUEST).l
.wait_z80:
        btst    #0, (Z80_BUS_REQUEST).l
        bne.s   .wait_z80
        endm

startZ80 macro
        move.w  #$0000, (Z80_BUS_REQUEST).l
        endm

disableInts macro
        move.w  #$2700, sr
        endm

enableInts macro
        move.w  #$2300, sr
        endm

; -----------------------------------------------
; VDP shadow table write-through
; -----------------------------------------------

; SetVDPReg — write to shadow table + mark dirty
; reg = struct field offset (e.g. vdp_mode2), val = value (register or immediate)
setVDPReg macro reg,val
        move.b  val, (VDP_Shadow_Table+reg).w
        ori.l   #(1<<reg), (VDP_Dirty_Mask).w
        endm

; -----------------------------------------------
; vdpCommReg — runtime VDP command from register
; Converts a VRAM/CRAM/VSRAM byte address in a data register
; to a VDP command longword (in-place).
; type/rwd must be assembly-time constants.
; clr: 1 = clear upper word of reg first, 0 = assume clean
; Used by DMA queue entry writes (movep interleave).
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
; In: slotvar = queue slot pointer variable (e.g. DMA_Critical_Slot)
;     queueend = queue end address constant
;     entryvar = pre-computed entry variable (e.g. Static_Pal_Line0)
; Clobbers: a1, a2
; -----------------------------------------------
queueStaticDMA macro slotvar, queueend, entryvar
        movea.w (slotvar).w, a1
        cmpa.w  #queueend, a1
        beq.s   .done
        lea     (entryvar).w, a2
        move.l  (a2)+, (a1)+
        move.l  (a2)+, (a1)+
        move.l  (a2)+, (a1)+
        move.w  (a2)+, (a1)+
        move.w  a1, (slotvar).w
.done:
        endm

; -----------------------------------------------
; Entity-window loaded-bit clears (§4.9 phase 2)
; Both no-op when the entity's section is no longer tracked.
; Fixed internal labels: expand each macro at most once per global-label
; scope (the two macros use distinct labels, so one of EACH per scope is
; fine). Current expansions: EntityWindow_DespawnRings (ring),
; EntityWindow_DespawnObjects (obj) — one each.
; -----------------------------------------------

; clearLoadedRing — clear a ring's loaded bit from its buffer entry
; In: bufReg = Ring_Buffer base (address register)
;     idxReg = entry byte offset, index×6 (data register; overwritten)
; Clobbers: d0-d3, a0
clearLoadedRing macro bufReg,idxReg
        moveq   #0, d3
        move.b  5(bufReg, idxReg.w), d3 ; list_index
        move.b  4(bufReg, idxReg.w), d0 ; section_id
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .clr_ring_skip          ; section untracked — no loaded bits
        move.w  d3, d1
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Clear
.clr_ring_skip:
        endm

; clearLoadedObj — clear an object's loaded bit from its SST fields
; In: sstReg = SST pointer (address register; fields read before any call)
; Clobbers: d0-d3, a0
clearLoadedObj macro sstReg
        moveq   #0, d3
        move.b  SST_entity_list_index(sstReg), d3
        move.b  SST_entity_section_id(sstReg), d0
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .clr_obj_skip           ; section untracked — no loaded bits
        move.w  d3, d1
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Clear
.clr_obj_skip:
        endm

; -----------------------------------------------
; Debug subsystem flags (only meaningful when __DEBUG__ is defined)
; Use the MD Debugger's ifdebug macro (from debug/debugger.asm) for conditionals.
; -----------------------------------------------
DEBUG_ALL               = 0
DEBUG_DMA               = 0 | DEBUG_ALL
DEBUG_VRAM              = 0 | DEBUG_ALL
DEBUG_OBJECTS            = 0 | DEBUG_ALL
DEBUG_COLLISION         = 0 | DEBUG_ALL
