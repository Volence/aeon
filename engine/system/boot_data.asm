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
        include "engine/sound/z80_sound_driver.asm"
    else
      ifndef SIGIL_EMP_Z80_INIT
        include "engine/system/z80_init.asm"
      else
        ; sigil mixed build (no-sound shape): the idle program comes from
        ; z80_init.emp, placed by the sigil map. Whole-ROM off-canonical
        ; placement (the org-advance past the .emp span) is the deferred
        ; DEMAND-3 machinery, shared with sound_debug/game_debug; the port is
        ; proven by the z80_init_port off-canonical oracle. Both shipped shapes
        ; have sound ENABLED, so this whole `else` is skipped canonically.
      endif
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

; -----------------------------------------------
; Layout-assert wall — the boot code walks this table with ONE sequential
; (a5)+ cursor (movem head, register-count loop, fill command, blob copy,
; PSG bytes, post-DMA commands). Every offset below is consumed blind by
; that cursor, so the table's geometry is locked here; a layout edit that
; moves any waypoint must update the cursor protocol in lockstep.
; -----------------------------------------------

    ; Movem-preload head: 3 words (d5-d7) + 5 longs (a0-a4) — must match the
    ; movem.w/movem.l widths and order at the cursor's first two reads.
    if (BootData_VDPRegs-BootData) <> (3*2+5*4)
        fatal "BootData movem head is \{BootData_VDPRegs-BootData} bytes — the cursor's movem.w d5-d7 / movem.l a0-a4 reads expect 26"
    endif

    ; Blob start: head (26) + 24 VDP register bytes (the moveq #23 loop) +
    ; 4-byte DMA fill command are consumed before the Z80 copy begins.
    ifdef SOUND_DRIVER_ENABLED
    if (Z80_Sound_Start-BootData) <> 54
        fatal "Z80 blob starts at BootData+\{Z80_Sound_Start-BootData} — the cursor reaches the copy loop at +54"
    endif
    ; Post-blob evenness: the align after the blob must emit NOTHING — the
    ; cursor advances exactly Z80_SOUND_SIZE bytes and then reads the PSG
    ; values; an odd blob would shear the cursor off them by one.
    if (Z80_SOUND_SIZE & 1) <> 0
        fatal "Z80_SOUND_SIZE is odd (\{Z80_SOUND_SIZE}) — the post-blob align would emit a pad byte the (a5)+ cursor never skips"
    endif
    ; Total-layout lock: 54 + blob + PSG(4) + auto-increment word(2) +
    ; CRAM/VSRAM commands(8) — no hidden padding anywhere in the walk.
    if (BootData_End-BootData) <> (54+Z80_SOUND_SIZE+4+10)
        fatal "BootData table is \{BootData_End-BootData} bytes — the cursor protocol accounts for \{54+Z80_SOUND_SIZE+4+10}"
    endif
    else
    if (Z80_IdleProgram-BootData) <> 54
        fatal "Z80 idle blob starts at BootData+\{Z80_IdleProgram-BootData} — the cursor reaches the copy loop at +54"
    endif
    if (Z80_IDLE_SIZE & 1) <> 0
        fatal "Z80_IDLE_SIZE is odd (\{Z80_IDLE_SIZE}) — the post-blob align would emit a pad byte the (a5)+ cursor never skips"
    endif
    if (BootData_End-BootData) <> (54+Z80_IDLE_SIZE+4+10)
        fatal "BootData table is \{BootData_End-BootData} bytes — the cursor protocol accounts for \{54+Z80_IDLE_SIZE+4+10}"
    endif
    endif
