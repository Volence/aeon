; soundBankHead — the engine-tables-at-bank-head contract.
;
; Every bank the Z80 sequencer RUNS A FRAME ON (any bank SND_SONG_BANK or
; SFX_BLOB_BANK can name) MUST invoke this macro FIRST inside its
;     align $8000  /  save  /  cpu z80  /  phase 08000h
; region. The reader labels emitted here are fixed $8000-window addresses —
; a frame on a bank without this head reads garbage pitch/volume/dispatch.
; Today exactly ONE such bank exists (songs + SFX blobs + tables co-located;
; asserted in the game's song_table.asm and SFX guards). A future second bank
; needs a label-free data-only twin of this head at its start (see
; DEFERRED_WORK "Bank-D DAC co-location hook" for the generator approach).
;
; NO CODE may be authored in the banked window — only DATA tables. Z80 opcode
; fetches from $8000-$FFFF traverse the 68k bus; 68k contention (VRAM DMA-from-
; ROM / BUSREQ) corrupts fetched opcodes -> wild PC -> Z80 self-reinit. Banked
; DATA reads tolerate contention (worst case a one-frame glitch); banked CODE
; fetches do not. All in-frame code lives in the resident blob.
;
; args:
;   pitchfile  — game include that must define SndDefaultPitchTable (the
;                fallback pitch table sound_fm.asm uses when a song's
;                pitchtable_ptr is 0), inside the window.
;   sfxtabfile — game include defining SfxBlobWinTab (the id->blob window-
;                pointer table sound_sfx.asm's readers use under
;                SetBank(SFX_BLOB_BANK)).
; The game must also define, at its bank start (BEFORE the phase bracket):
; a bank-start label and SND_ENGINE_TABLE_BANK = <label> >> 15.
;
; {GLOBALSYMBOLS}: every label in the included files must be a real global
; symbol — AS macro-expansion labels are macro-local by default and would
; both break the driver's references and vanish from the symbol table.
soundBankHead macro pitchfile, sfxtabfile, {GLOBALSYMBOLS}
        include "engine/sound/sound_tables_z80.asm"
        include pitchfile
        include sfxtabfile
        include "engine/sound/seq_opcode_tab.asm"
    ifndef SIGIL_EMP_DAC
        include "engine/sound/dac_sample_tab.asm"
    else
        ; seam-2 (Option Y): the DacSampleTable descriptor head is the byte-identical
        ; artifact sigil CO-LINKS from dac_sample_tab.emp + dac_samples.emp's SND_*
        ; equs — dac_sample_tab.bin — BINCLUDE'd here at the same VMA ($85AD) the
        ; `.asm` head landed. The label MUST precede the BINCLUDE (the resident
        ; driver's `-D DacSampleTable=$85AD` and Snd_DacLookup pointer math depend on
        ; it). With the head native, NO AS consumer of SND_* remains — the cross-seam
        ; coupling dissolves (the whole point of Option Y).
DacSampleTable:
        BINCLUDE "engine/sound/generated/dac_sample_tab.bin"
DacSampleTable_End:
        if (DacSampleTable_End-DacSampleTable) <> DAC_SAMPLE_COUNT*DacSample_len
          fatal "DacSampleTable wrong size for DAC_SAMPLE_COUNT"
        endif
    endif
    endm
