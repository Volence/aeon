; Z80 idle program — clears Z80 RAM, enters infinite loop
Z80_IdleProgram:
        save
        cpu z80
        phase 0

        xor     a
        ld      bc, (Z80_RAM_END-Z80_RAM)-Z80_IdleProgram_CodeEnd-1
        ld      de, Z80_IdleProgram_CodeEnd+1
        ld      hl, Z80_IdleProgram_CodeEnd
        ld      sp, hl
        ld      (hl), a
        ldir
        pop     ix
        pop     iy
        ld      i, a
        ld      r, a
        pop     de
        pop     hl
        pop     af
        ex      af, af'
        exx
        pop     bc
        pop     de
        pop     hl
        pop     af
        ld      sp, hl
        di
        im      1
        ld      (hl), 0E9h          ; patch: jp (hl) opcode at address 0
        jp      (hl)                ; idle loop

Z80_IdleProgram_CodeEnd:
        dephase
        restore
Z80_IdleProgram_End:

Z80_IDLE_SIZE = Z80_IdleProgram_End - Z80_IdleProgram
