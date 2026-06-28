; ======================================================================
; SfxBlobWinTab — id -> blob $8000-window ptr (dense, indexed by id-SFX_ID_BASE).
;
; BANKED (Phase-2 Z80 budget recovery, 2026-06-28): this table is co-located in
; the Moving Trucks / SFX bank, emitted inside main.asm's `cpu z80 / phase 08000h`
; block, so it costs ZERO against the resident Z80-code ceiling ($16F0) — it was
; moved out of the resident phase-0 blob to free room for Music-Expression Phase 2.
; Its home bank IS SFX_BLOB_BANK (the SFX blobs share the MT bank), so the two
; readers (SfxDispatch + Sfx_BeginSound in sound_sfx.asm) now SetBank(SFX_BLOB_BANK)
; BEFORE the lookup, reading the table through the $8000 window. Entries are
; build-time window ptrs from the 68k blob labels (sfx_winptr()); an unused id is 0
; (the readers ignore it). Included under the phase block so `dw` is little-endian
; (as the Z80 reads it) and the labels equal their $8000-window ptrs.
;
; Depends on (all defined earlier — sound engine assembles at boot.asm:279, the
; phase block is later in main.asm): sfx_winptr() + SFX_WIN_* (sound_sfx.asm),
; SFXID_* + SFX_ID_BASE (sound_constants.asm), and the forward 68k Sfx_NN blob
; labels (data/sound/sfx/, included later in the same bank).
; ======================================================================
SfxBlobWinTab:
        dw      sfx_winptr(Sfx_33)       ; $33 RING_RIGHT
        dw      sfx_winptr(Sfx_34)       ; $34 RING_LEFT
        dw      sfx_winptr(Sfx_35)       ; $35 DEATH
        dw      sfx_winptr(Sfx_36)       ; $36 SKID
        rept    (SFXID_ROLL - SFXID_SKID - 1)
        dw      0                        ; $37..$3B unused
        endm
        dw      sfx_winptr(Sfx_3C)       ; $3C ROLL
        rept    (SFXID_JUMP - SFXID_ROLL - 1)
        dw      0                        ; $3D..$61 unused
        endm
        dw      sfx_winptr(Sfx_62)       ; $62 JUMP
        rept    (SFXID_SPINDASH - SFXID_JUMP - 1)
        dw      0                        ; $63..$AA unused
        endm
        dw      sfx_winptr(Sfx_AB)       ; $AB SPINDASH
        rept    (SFXID_DASH - SFXID_SPINDASH - 1)
        dw      0                        ; $AC..$B5 unused
        endm
        dw      sfx_winptr(Sfx_B6)       ; $B6 DASH
        rept    (SFXID_RINGLOSS - SFXID_DASH - 1)
        dw      0                        ; $B7..$B8 unused
        endm
        dw      sfx_winptr(Sfx_B9)       ; $B9 RINGLOSS
SfxBlobWinTab_End:

        ; the table must hold exactly one window-ptr entry per id in the dense
        ; [RING_RIGHT..RINGLOSS] range (this span IS SFX_TABLE_LEN, but that equate
        ; is forward-defined in sfx_table.asm — included AFTER this blob — so it
        ; can't be first-pass-evaluated here; assert against the SFXID_* equates,
        ; which ARE known). The local in-blob labels evaluate in the first pass.
SFX_TABLE_SPAN = SFXID_RINGLOSS - SFXID_RING_RIGHT + 1
        if (SfxBlobWinTab_End - SfxBlobWinTab) <> (SFX_TABLE_SPAN * 2)
          error "SfxBlobWinTab length (\{SfxBlobWinTab_End - SfxBlobWinTab}) != span*2 (\{SFX_TABLE_SPAN*2})"
        endif
        ; NOTE: every SFX blob (and its inline patch bank) MUST share ONE bank,
        ; else SfxDispatch's single SetBank can't view them all. That invariant
        ; is enforced by the build LAYOUT (all sfx_NN.asm blobs are included
        ; contiguously in main.asm) — it can't be asserted here because the blob
        ; labels are forward 68k references, not first-pass-evaluable in this
        ; phased Z80 context. SFX_BLOB_BANK is taken from Sfx_33; the contiguous
        ; layout guarantees the rest match.
