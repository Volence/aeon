; Boot sequence — TMSS, VDP init, Z80 init, memory clearing

; -----------------------------------------------
; EntryPoint — first instruction after reset
; -----------------------------------------------
EntryPoint:
        tst.l   (HW_PORT_A_CTRL_FULL).l
        bne.s   Warm_Boot
        tst.w   (HW_EXPANSION_CTRL_FULL).l
        beq.s   Cold_Boot

; -----------------------------------------------
; Warm_Boot — soft reset path
; -----------------------------------------------
Warm_Boot:
        ; Wait for any in-progress DMA
.wait_dma:
        move.w  (VDP_CTRL).l, d0
        btst    #1, d0                      ; VDP status bit 1 = DMA busy
        bne.s   .wait_dma

        ; Fall through to cold boot.

; -----------------------------------------------
; Cold_Boot — full hardware initialization
; -----------------------------------------------
Cold_Boot:
        ; TMSS handshake (§0.2)
        move.b  (HW_VERSION).l, d0
        andi.b  #$F, d0                     ; low nibble = hardware version (0 = pre-TMSS)
        beq.s   .no_tmss
        move.l  #$53454741, (TMSS_REGISTER).l   ; "SEGA"
.no_tmss:

        ; Reset VDP command word state machine
        move.w  (VDP_CTRL).l, d0

        ; Preload hardware addresses via movem — the table head assigns:
        ; d5=$8000 (VDP reg cmd base) d6=RAM-clear dbf count d7=$0100 (reg
        ; stride / Z80 bus value); a0=Z80_RAM a1=Z80_BUS_REQUEST a2=Z80_RESET
        ; a3=VDP_DATA a4=VDP_CTRL (boot_data.asm owns the values).
        lea.l   BootData(pc), a5
        movem.w (a5)+, d5-d7
        movem.l (a5)+, a0-a4

        ; VDP register init — 24 registers from table (§0.3)
        moveq   #23, d1
.vdp_loop:
        move.b  (a5)+, d5
        move.w  d5, (a4)
        add.w   d7, d5                  ; d7 = $0100 → next register
        dbf     d1, .vdp_loop

        ; Start VRAM DMA fill (§0.7) — runs in background on VDP clock
        move.w  #vdpReg($0F, $01), (a4)    ; auto-increment = 1 for byte-by-byte DMA fill
        move.l  (a5)+, (a4)                ; vdpComm(0, VRAM, DMA)
        moveq   #0, d0
        move.w  d0, (a3)                    ; trigger fill (fill byte = 0)

        ; --- PARALLEL WORK WHILE DMA FILLS VRAM ---

        ; Z80 init (§0.5)
        move.w  d0, (a2)                    ; assert Z80 reset
        move.w  d7, (a1)                    ; request Z80 bus
        move.w  d7, (a2)                    ; release Z80 reset

.wait_z80:
        btst    d0, (a1)                    ; wait for bus grant (d0 = 0 → test bit 0)
        bne.s   .wait_z80

        ; Copy Z80 program to Z80 RAM (a5 already points at the included blob)
    ifdef SOUND_DRIVER_ENABLED
        move.w  #Z80_SOUND_SIZE-1, d1       ; byte count — the blob size exceeds moveq's signed-8 immediate
    else
        moveq   #Z80_IDLE_SIZE-1, d1
    endif
.load_z80:
        move.b  (a5)+, (a0)+
        dbf     d1, .load_z80

        ; Z80 reset with YM2612-safe delay
        move.w  d0, (a2)                    ; assert reset
        moveq   #25, d2
.ym_delay:
        dbf     d2, .ym_delay               ; ~264 cycles (YM2612 needs >= 192)
        move.w  d7, (a2)                    ; release reset — Z80 starts idle loop
        move.w  d0, (a1)                    ; release bus — Z80 has control

        ; Clear Work RAM — 64KB (§0.7)
        movea.l d0, a6                      ; a6 = 0
        move.w  d6, d2                      ; d2 = $3FFF dbf count → $4000 longs = 64KB
.clear_ram:
        move.l  d0, -(a6)                   ; wraps: $00000000 → $FFFFFFFC → ... → $FFFF0000
        dbf     d2, .clear_ram

        ; PSG silence (§0.6) — 4 bytes from data table
        moveq   #3, d2
.silence_psg:
        move.b  (a5)+, PSG_PORT-VDP_DATA(a3)
        dbf     d2, .silence_psg
        align 2

        ; --- WAIT FOR DMA FILL TO COMPLETE ---
.wait_fill:
        move.w  (a4), d2
        btst    #1, d2
        bne.s   .wait_fill

        ; Restore auto-increment to 2
        move.w  (a5)+, (a4)                 ; vdpReg($0F, $02)

        ; Clear CRAM — 128 bytes (§0.7)
        move.l  (a5)+, (a4)                 ; vdpComm(0, CRAM, WRITE)
        moveq   #bytesToLcnt($80), d2
.clear_cram:
        move.l  d0, (a3)
        dbf     d2, .clear_cram

        ; Clear VSRAM — 80 bytes (§0.7)
        move.l  (a5)+, (a4)                 ; vdpComm(0, VSRAM, WRITE)
        moveq   #bytesToLcnt($50), d2
.clear_vsram:
        move.l  d0, (a3)
        dbf     d2, .clear_vsram

        ; YM2612 key-off — silence all 6 FM channels (§0.6)
        stopZ80
        lea.l   (YM2612_A0).l, a6
        move.b  #$28, (a6)                  ; select Key On/Off register
        moveq   #2, d2
.keyoff_part1:
        move.b  d2, 1(a6)                   ; key off channels 0-2
        dbf     d2, .keyoff_part1
        moveq   #6, d2
        moveq   #2, d1
.keyoff_part2:
        move.b  d2, 1(a6)                   ; key off channels 4-6 ($04,$05,$06)
        subq.w  #1, d2
        dbf     d1, .keyoff_part2
        startZ80

        ; Clear all 68K registers
        movem.l (RAM_Start).w, d0-a6

        ; Disable all interrupts
        disableInts

        ; Init VDP shadow table (§0.4)
        bsr.w   VDP_Shadow_Init

        ; Init DMA queue (§1.1)
        bsr.w   Init_DMA_Queue

        ; Init sprite table link chain (§1.3)
        bsr.w   Init_SpriteTable

        ; Build static DMA entries (§1.5)
        bsr.w   BuildStaticDMA

        ; Set initial VBlank handler (§1.2)
        move.l  #VInt_Level, (VInt_Ptr).w

        ; Region detection (§0.8)
        move.b  (HW_VERSION).l, d0
        move.b  d0, (Hardware_Region).w
        andi.b  #$C0, d0                    ; keep bits 7:6 (domestic/export, NTSC/PAL)
        move.b  d0, (Region_Flags).w
        btst    #6, d0                      ; bit 6 = PAL
        bne.s   .pal
        move.w  #NTSC_TIMING_STEP, (Timing_Step).w
        move.w  #DMA_BUDGET_NTSC, (DMA_Budget_Default).w
        bra.s   .region_done
.pal:
        move.w  #PAL_TIMING_STEP, (Timing_Step).w
        move.w  #DMA_BUDGET_PAL, (DMA_Budget_Default).w
.region_done:
        clr.w   (Frame_Accumulator).w       ; RAM operand — the 68000 clr read-before-write hazard is I/O-only

        ; Controller port init (§0.9)
        move.b  #$40, (HW_PORT_1_CTRL).l    ; TH as output
        move.b  #$40, (HW_PORT_2_CTRL).l
        move.b  #$40, (HW_EXPANSION_CTRL).l
        move.b  #$40, (HW_PORT_1_DATA).l    ; TH high (initial state)
        move.b  #$40, (HW_PORT_2_DATA).l
        move.b  #$40, (HW_PORT_EXP_DATA).l

        ; Init HBlank vector slot to idle (§0.10). Written BEFORE interrupts
        ; unmask — RAM-clear leaves $0000, not a legal instruction; the slot
        ; must decode to a real rte before IRQ4 can fire. The long write fills
        ; the first two slot words with rte ($4E73) — offset 0 is the one that
        ; executes; the second rte is defensive. move.l (vs move.w) keeps this
        ; init 8 bytes, so boot stays byte-neutral and the trampoline re-pin is
        ; confined to the hblank region and below.
        move.l  #$4E734E73, (HBlank_Vector_Slot).w

        ; Enable VBlank interrupt (set VDP reg $01 bit 5)
        setVDPReg VDP_Shadow_vdp_mode2, #$34   ; $14 | $20 (VInt enable) = $34

        ; Flush shadow to hardware — VInt must be enabled in VDP before unmasking
        bsr.w   Flush_VDP_Shadow

        ; Enable interrupts
        enableInts

    ifdef __DEBUG__
        ; Golden compression self-test — decompressors vs build encoders.
        ; Runs before any game state touches Art_Staging_Buffer.
        bsr.w   CompressionSelfTest
    endif

    ifdef SOUND_DRIVER_ENABLED
        ; Sound mailbox idle handshake. Z80 already has the bus and the
        ; driver is running; registers are free here (post-boot setup).
        bsr.w   Sound_Init
    endif
        gameBootHook                     ; game-supplied (may be empty)

        ; Set initial game state — the game supplies the entry contract:
        ;   Game_Entry    = the first game-state routine
        ;   GAME_ENTRY_ID = its game-state id
        move.l  #Game_Entry, (Game_State).w
        move.b  #GAME_ENTRY_ID, (Game_State_ID).w
        clr.b   (Game_State_Init).w

        ; Enter main loop — never returns
        bra.w   GameLoop
