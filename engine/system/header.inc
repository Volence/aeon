; gameHeader — emits the $100-$1FF Mega Drive ROM header from game-declared
; string symbols. Invoke immediately after the vectors include (org-0 image:
; $000-$0FF vectors, $100-$1FF header). Every field width-asserts at build
; time — a wrong-length string is a build error, not a corrupt header.
; The checksum word at $18E is emitted 0; tools/fixheader patches it.
; ROM start/end and RAM range are engine-owned (EndOfRom = engine epilogue label).
;
; Required game symbols (string, exact width):
;   GAME_CONSOLE(16) GAME_COPYRIGHT(16) GAME_TITLE_DOM(48) GAME_TITLE_OVS(48)
;   GAME_SERIAL(14) GAME_IO(16) GAME_SRAM(12) GAME_MEMO(52) GAME_REGION(16)
; {GLOBALSYMBOLS}: labels emitted by this macro (Checksum) must be real global symbols — AS macro labels are macro-local by default and would vanish from the symbol table.
gameHeader macro {GLOBALSYMBOLS}
        if strlen(GAME_CONSOLE) <> 16
          fatal "GAME_CONSOLE must be exactly 16 chars"
        endif
        if strlen(GAME_COPYRIGHT) <> 16
          fatal "GAME_COPYRIGHT must be exactly 16 chars"
        endif
        if strlen(GAME_TITLE_DOM) <> 48
          fatal "GAME_TITLE_DOM must be exactly 48 chars"
        endif
        if strlen(GAME_TITLE_OVS) <> 48
          fatal "GAME_TITLE_OVS must be exactly 48 chars"
        endif
        if strlen(GAME_SERIAL) <> 14
          fatal "GAME_SERIAL must be exactly 14 chars"
        endif
        if strlen(GAME_IO) <> 16
          fatal "GAME_IO must be exactly 16 chars"
        endif
        if strlen(GAME_SRAM) <> 12
          fatal "GAME_SRAM must be exactly 12 chars"
        endif
        if strlen(GAME_MEMO) <> 52
          fatal "GAME_MEMO must be exactly 52 chars"
        endif
        if strlen(GAME_REGION) <> 16
          fatal "GAME_REGION must be exactly 16 chars"
        endif
        dc.b    GAME_CONSOLE                ; $100
        dc.b    GAME_COPYRIGHT              ; $110
        dc.b    GAME_TITLE_DOM              ; $120
        dc.b    GAME_TITLE_OVS              ; $150
        dc.b    GAME_SERIAL                 ; $180
Checksum:
        dc.w    0                           ; $18E — fixheader patches
        dc.b    GAME_IO                     ; $190
        dc.l    $00000000                   ; $1A0 ROM start
        dc.l    EndOfRom-1                  ; $1A4 ROM end
        dc.l    $00FF0000                   ; $1A8 RAM start
        dc.l    $00FFFFFF                   ; $1AC RAM end
        dc.b    GAME_SRAM                   ; $1B0
        dc.b    GAME_MEMO                   ; $1BC
        dc.b    GAME_REGION                 ; $1F0
    endm
