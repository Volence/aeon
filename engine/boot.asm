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
        btst    #1, d0
        bne.s   .wait_dma

        ; Check CROSS_RESET_RAM magic (warm boot detection)
        ; When game state worth preserving exists, branch here on valid magic
        ; For now, fall through to cold boot regardless

; -----------------------------------------------
; Cold_Boot — full hardware initialization
; -----------------------------------------------
Cold_Boot:
        ; TMSS handshake (§0.2)
        move.b  (HW_VERSION).l, d0
        andi.b  #$F, d0
        beq.s   .no_tmss
        move.l  #$53454741, (TMSS_REGISTER).l   ; "SEGA"
.no_tmss:

        ; Reset VDP command word state machine
        move.w  (VDP_CTRL).l, d0

        ; Preload hardware addresses via movem
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
        move.w  #Z80_SOUND_SIZE-1, d1       ; word count — blob may exceed moveq range
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
        move.w  d6, d2                      ; d2 = $3FFF (longword count)
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
        andi.b  #$C0, d0
        move.b  d0, (Region_Flags).w
        btst    #6, d0
        bne.s   .pal
        move.w  #NTSC_TIMING_STEP, (Timing_Step).w
        move.w  #DMA_BUDGET_NTSC, (DMA_Budget_Default).w
        bra.s   .region_done
.pal:
        move.w  #PAL_TIMING_STEP, (Timing_Step).w
        move.w  #DMA_BUDGET_PAL, (DMA_Budget_Default).w
.region_done:
        move.w  #0, (Frame_Accumulator).w

        ; Controller port init (§0.9)
        move.b  #$40, (HW_PORT_1_CTRL).l    ; TH as output
        move.b  #$40, (HW_PORT_2_CTRL).l
        move.b  #$40, (HW_EXPANSION_CTRL).l
        move.b  #$40, (HW_PORT_1_DATA).l    ; TH high (initial state)
        move.b  #$40, (HW_PORT_2_DATA).l
        move.b  #$40, (HW_PORT_EXP_DATA).l

        ; Init HBlank handler pointer (§0.10)
        move.l  #HBlank_Null, (HBlank_Handler_Ptr).w

        ; Enable VBlank interrupt (set VDP reg $01 bit 5)
        setVDPReg VDP_Shadow_vdp_mode2, #$34   ; $14 | $20 (VInt enable) = $34

        ; Flush shadow to hardware — VInt must be enabled in VDP before unmasking
        bsr.w   Flush_VDP_Shadow

        ; Enable interrupts
        enableInts

        ; Mark cold boot complete (§0.11)
        move.l  #CROSS_RESET_MAGIC, (CROSS_RESET_MAGIC_ADDR).l

    ifdef __DEBUG__
        ; Golden compression self-test — decompressors vs build encoders.
        ; Runs before any game state touches Decomp_Buffer.
        bsr.w   CompressionSelfTest
    endif

    ifdef SOUND_DRIVER_ENABLED
        ; Sound mailbox idle + (DEBUG) ping handshake. Z80 already has the bus
        ; and the driver is running; registers are free here (post-boot setup).
        bsr.w   Sound_Init
      ifdef __DEBUG__
        moveq   #$3C, d0                 ; DEBUG: ping with a recognizable value
        bsr.w   Sound_Ping
        ; DEBUG: play the demo song. NORMALLY SONG_TEST (FM1 lead + FM2 bass + PSG1
        ; thirds harmony). Press START in-game to toggle stop/play (game_loop
        ; Debug_MusicToggle).
        ;
        ; *** CURRENT DEV-VERIFICATION SONG — Sound Phase 3 Task 6 (TEMPORARY):
        ; SONG_PANTEST exercises MEV_PAN (write-on-change $B4) + MEV_OPBIAS (per-
        ; operator TL bias latched in Fm_PatchLoad). One FM channel: a note hard-
        ; LEFT ($B4=$80, ~1s), the SAME note hard-RIGHT ($B4=$40, ~1s), then a
        ; recentered ($B4=$C0) note with a +$30 bias on modulator op0 (reg $40 = $68
        ; vs $38 — an audibly darker timbre), looping. Expected $B4/$40 bytes are
        ; documented in data/sound/song_pantest.py. (SONG_TEST = id 1, SONG_PITCHTEST
        ; = 2, SONG_TRILLTEST = 3 remain in the table for switch-back.) REVERT to
        ; SONG_TEST after verifying. ***
        moveq   #SONG_PANTEST, d0
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w     ; DEBUG: track play state for the Start-toggle
      endif
    endif

        ; Set initial game state
        move.l  #GameState_OJZScroll_Init, (Game_State).w
        move.b  #GS_OJZ_SCROLL_TEST, (Game_State_ID).w
        clr.b   (Game_State_Init).w

        ; Enter main loop — never returns
        bra.w   GameLoop

; -----------------------------------------------
; Boot Data Table — read sequentially via (a5)+
; -----------------------------------------------
BootData:
        ; Movem preload: d5-d7
        dc.w    $8000                       ; d5: VDP reg command base
        dc.w    bytesToLcnt($10000)         ; d6: RAM clear longword count ($3FFF)
        dc.w    $0100                       ; d7: Z80 bus/reset value

        ; Movem preload: a0-a4
        dc.l    Z80_RAM                     ; a0
        dc.l    Z80_BUS_REQUEST             ; a1
        dc.l    Z80_RESET                   ; a2
        dc.l    VDP_DATA                    ; a3
        dc.l    VDP_CTRL                    ; a4

        ; VDP register values $00-$17 (§0.3)
BootData_VDPRegs:
        dc.b    $04                         ; $00: HInt off, HV counter readable
        dc.b    $14                         ; $01: display OFF, VInt OFF, DMA ON
        dc.b    $30                         ; $02: Plane A nametable at $C000
        dc.b    $3C                         ; $03: Window nametable at $F000
        dc.b    $07                         ; $04: Plane B nametable at $E000
        dc.b    $5C                         ; $05: Sprite table at $B800
        dc.b    $00                         ; $06: unused
        dc.b    $00                         ; $07: BG color = pal 0, entry 0
        dc.b    $00                         ; $08: unused (SMS compat)
        dc.b    $00                         ; $09: unused (SMS compat)
        dc.b    $FF                         ; $0A: HInt counter = every 256 lines
        dc.b    $00                         ; $0B: full-screen V/H scroll
        dc.b    $81                         ; $0C: H40 (320px), no interlace
        dc.b    $2F                         ; $0D: HScroll table at $BC00
        dc.b    $00                         ; $0E: unused
        dc.b    $02                         ; $0F: auto-increment = 2 (normal word access)
        dc.b    $11                         ; $10: 64x64 scroll planes
        dc.b    $00                         ; $11: window H disabled
        dc.b    $00                         ; $12: window V disabled
        dc.b    $FF                         ; $13: DMA length low = $FF
        dc.b    $FF                         ; $14: DMA length high = $FF
        dc.b    $00                         ; $15: DMA source low
        dc.b    $00                         ; $16: DMA source mid
        dc.b    $80                         ; $17: DMA fill mode

        ; VRAM DMA fill command
        dc.l    vdpComm(0, VRAM, DMA)

        ; Z80 program (assembled Z80 code) — sound driver replaces idle when enabled
    ifdef SOUND_DRIVER_ENABLED
        include "engine/z80_sound_driver.asm"
    else
        include "engine/z80_init.asm"
    endif
        align 2

        ; PSG silence values
        dc.b    $9F, $BF, $DF, $FF
        align 2

        ; Post-DMA VDP commands
        dc.w    vdpReg($0F, $02)            ; restore auto-increment to 2
        dc.l    vdpComm(0, CRAM, WRITE)
        dc.l    vdpComm(0, VSRAM, WRITE)
BootData_End:
