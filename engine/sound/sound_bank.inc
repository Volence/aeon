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
; Every table in this head is now a byte-identical BINCLUDE'd sigil artifact —
; no game include arg. SndDefaultPitchTable (the fallback pitch table sound_fm.asm
; uses when a song's pitchtable_ptr is 0) is BINCLUDE'd below from
; movingtrucks_pitchtable.bin (sigil lowers games/sonic4/data/sound/
; movingtrucks_pitchtable.emp; the .asm twin is deleted, flip Stage-0).
; SfxBlobWinTab (the id->blob window-pointer table sound_sfx.emp's readers use
; under SetBank(SFX_BLOB_BANK)) is BINCLUDE'd below as the byte-identical
; artifact sigil co-links from sfx_blob_win_tab.emp + sfx_bank.emp's SFX_WIN_*
; equs — sfx_blob_win_tab{,_debug}.bin (the .asm twin is deleted, seam-2 2d).
; The game must also define, at its bank start (BEFORE the phase bracket):
; a bank-start label and SND_ENGINE_TABLE_BANK = <label> >> 15.
;
; {GLOBALSYMBOLS}: every label in the included files must be a real global
; symbol — AS macro-expansion labels are macro-local by default and would
; both break the driver's references and vanish from the symbol table.
soundBankHead macro {GLOBALSYMBOLS}
        ; seam-2 (stage-3): the generated FM/PSG data tables (4 pure-math LUTs +
        ; the PSG/FM vol-env id-lists/pointer tables/bodies) are the byte-identical
        ; artifact sigil emits from sound_tables_z80.emp — sound_tables_z80.bin —
        ; BINCLUDE'd here at VMA $8000 (the .asm twin is deleted). SHAPE-INVARIANT.
        ; The resident FM/PSG writers read the 8 head labels (FmPitchTableZ ..
        ; FmVolEnv_Ptrs) via the seam-1 banked carriers at their fixed VMAs — the
        ; byte-exact $8000-based layout keeps those addresses correct.
SoundTablesZ80_Head:
        BINCLUDE "engine/sound/generated/sound_tables_z80.bin"
SoundTablesZ80_Head_End:
        ; Guard the head span (it has no generated _End of its own) so a size drift
        ; fails LOUD and LOCAL here rather than silently shifting the downstream
        ; heads (SfxBlobWinTab/SeqOpcodeTable/DacSampleTable) off their fixed
        ; banked-carrier VMAs ($845F/$856D/$85AD).
        if (SoundTablesZ80_Head_End-SoundTablesZ80_Head) <> 855
          fatal "sound_tables_z80 head wrong size ($357=855 B) — downstream head VMAs would shift"
        endif
        ; flip Stage-0: the SndDefaultPitchTable / MovingTrucks_PitchTable head is the
        ; byte-identical artifact sigil lowers from games/sonic4/data/sound/
        ; movingtrucks_pitchtable.emp — movingtrucks_pitchtable.bin — BINCLUDE'd here
        ; at VMA $8357 (the .asm twin is deleted). Pure data (the 132-entry two-page
        ; fnum table); the labels MUST precede the BINCLUDE (sound_fm's fallback reads
        ; SndDefaultPitchTable when a song's pitchtable_ptr is 0). SHAPE-INVARIANT.
SndDefaultPitchTable:
MovingTrucks_PitchTable:
        BINCLUDE "engine/sound/generated/movingtrucks_pitchtable.bin"
MovingTrucks_PitchTable_End:
        if (MovingTrucks_PitchTable_End-MovingTrucks_PitchTable) <> 2*PITCHTAB_COUNT
          fatal "MovingTrucks_PitchTable wrong size: \{MovingTrucks_PitchTable_End-MovingTrucks_PitchTable} != \{2*PITCHTAB_COUNT}"
        endif
        ; seam-2 (stage-2d): the SfxBlobWinTab id->blob window-pointer head is the
        ; byte-identical artifact sigil CO-LINKS from sfx_blob_win_tab.emp +
        ; sfx_bank.emp's SFX_WIN_* equs — sfx_blob_win_tab{,_debug}.bin —
        ; BINCLUDE'd here at VMA $845F (the .asm twin is deleted). The label MUST
        ; precede the BINCLUDE (the resident driver's SfxBlobWinTab=$845F banked
        ; carrier and sound_sfx.emp's `ld de, SfxBlobWinTab` depend on it).
        ; SHAPE-DEPENDENT: the SFX blobs sit after the shape-dependent songs, so
        ; every winptr(Sfx_NN) cell shifts with __DEBUG__.
SfxBlobWinTab:
      ifdef __DEBUG__
        BINCLUDE "engine/sound/generated/sfx_blob_win_tab_debug.bin"
      else
        BINCLUDE "engine/sound/generated/sfx_blob_win_tab.bin"
      endif
SfxBlobWinTab_End:
        if (SfxBlobWinTab_End-SfxBlobWinTab) <> SFX_TABLE_LEN*2
          fatal "SfxBlobWinTab wrong size for SFX_TABLE_LEN"
        endif
        ; seam-2 (stage-3): the SeqOpcodeTable coordination-opcode jump table is the
        ; byte-identical artifact sigil emits from seq_opcode_tab.emp, its 32
        ; `dc.w Seq_Op_*` cells resolved against the resident handler VMAs in the
        ; SAME blob link the driver ships from — seq_opcode_tab{,_debug}.bin —
        ; BINCLUDE'd here at VMA $856D (the .asm twin is deleted). SHAPE-DEPENDENT:
        ; the handlers re-base after sound_sequencer.emp's `if DEBUG==1` growth.
        ; The label MUST precede the BINCLUDE (the resident SeqOpcodeTable=$856D
        ; banked carrier and Sequencer_Channel's indexed read depend on it).
SeqOpcodeTable:
      ifdef __DEBUG__
        BINCLUDE "engine/sound/generated/seq_opcode_tab_debug.bin"
      else
        BINCLUDE "engine/sound/generated/seq_opcode_tab.bin"
      endif
SeqOpcodeTable_End:
        if (SeqOpcodeTable_End-SeqOpcodeTable) <> 32*2
          fatal "SeqOpcodeTable wrong size (must be 32 dw entries $E0..$FF)"
        endif
        ; seam-2 (Option Y): the DacSampleTable descriptor head is the byte-identical
        ; artifact sigil CO-LINKS from dac_sample_tab.emp + dac_samples.emp's SND_*
        ; equs — dac_sample_tab.bin — BINCLUDE'd here at VMA $85AD (the .asm twin is
        ; deleted). The label MUST precede the BINCLUDE (the resident driver's
        ; `-D DacSampleTable=$85AD` and Snd_DacLookup pointer math depend on it). With
        ; the head native, NO AS consumer of SND_* remains — the coupling dissolved.
DacSampleTable:
        BINCLUDE "engine/sound/generated/dac_sample_tab.bin"
DacSampleTable_End:
        if (DacSampleTable_End-DacSampleTable) <> DAC_SAMPLE_COUNT*DacSample_len
          fatal "DacSampleTable wrong size for DAC_SAMPLE_COUNT"
        endif
    endm
