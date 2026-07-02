; ======================================================================
; SeqOpcodeTable — dw jump table for coordination-flag opcodes $E0..$FF
; (32 entries). Index = opcode - MEV_VOL. Reserved opcodes point at
; Seq_BadOpcode.
;
; BANKED (budget A.2, 2026-07-02): co-located at the engine-table head of
; the song/SFX bank, emitted inside main.asm's `cpu z80 / phase 08000h`
; block (with FmPitchTableZ etc.), so it costs ZERO against the resident
; Z80-code ceiling. The label equals its $8000-window pointer; the sole
; reader — Sequencer_Channel's `.coord` dispatch (sound_sequencer.asm) —
; needs no code change (a plain indexed table read; no self-modification).
;
; BANK GUARANTEES at the read site (both == THIS bank today):
;   * music frame: Sequencer_Channel runs under B1's SetBank(SND_SONG_BANK)
;     (Run_SeqFrame_OnSongBank), and every song lives in this bank
;     (song_table.asm no-straddle asserts anchor at MovingTrucks_Bank_Start).
;   * SFX frame: Sfx_Frame's entry SetBank(SFX_BLOB_BANK) — the SFX blobs
;     are asserted co-located with this bank in main.asm.
; If a future song/SFX bank diverges, the REPLICATE-PER-BANK RULE at the
; main.asm phase block applies: that bank must carry an identical-layout
; engine-table head (this table included).
;
; The dw entries are RESIDENT phase-0 blob addresses (handlers are CODE and
; stay resident — banked opcode FETCHES corrupt under 68k bus contention);
; reading a resident address THROUGH the window is a plain data read.
; ======================================================================
SeqOpcodeTable:
        dw      Seq_Op_Vol               ; $E0 MEV_VOL
        dw      Seq_Op_Patch             ; $E1 MEV_PATCH
        dw      Seq_Op_Dac               ; $E2 MEV_DAC
        dw      Seq_Op_NoteDur           ; $E3 MEV_NOTE_DUR
        dw      Seq_Op_Pan               ; $E4 MEV_PAN
        dw      Seq_Op_RepeatStart       ; $E5 MEV_REPEAT_START
        dw      Seq_Op_RepeatEnd         ; $E6 MEV_REPEAT_END
        dw      Seq_Op_NoteRaw           ; $E7 MEV_NOTE_RAW
        dw      Seq_Op_PitchEnv          ; $E8 MEV_PITCHENV
        dw      Seq_Op_OpBias            ; $E9 MEV_OPBIAS
        dw      Seq_Op_RegDelta          ; $EA MEV_REGDELTA (voice-stepping)
        dw      Seq_Op_PsgEnv            ; $EB MEV_PSGENV
        dw      Seq_Op_ModSet            ; $EC MEV_MODSET
        dw      Seq_Op_NoteFill          ; $ED MEV_NOTEFILL (gate articulation)
        dw      Seq_Op_LoopPoint         ; $EE MEV_LOOP_POINT
        dw      Seq_Op_Jump              ; $EF MEV_JUMP
        dw      Seq_Op_SpinRev           ; $F0 MEV_SPINREV
        dw      Seq_BadOpcode            ; $F1 reserved (SPINREV reset is dispatch-folded)
        dw      Seq_Op_PsgNoise          ; $F2 MEV_PSGNOISE
        dw      Seq_Op_Tempo             ; $F3 MEV_TEMPO (global tempo scalar)
        dw      Seq_Op_Lfo               ; $F4 MEV_LFO (write $22 LFO, DAC $2A re-parked)
        dw      Seq_BadOpcode            ; $F5 reserved
        dw      Seq_Op_Detune            ; $F6 MEV_DETUNE (set sc_detune; applied at next note-on)
        dw      Seq_Op_PsgEnv            ; $F7 MEV_FMENV (shared handler: sets the unified
                                         ;   sc_env slot + resets sc_env_cur; ModUpdate
                                         ;   picks FmVolEnv vs PsgVolEnv by SCF_IS_FM_B)
        dw      Seq_Op_RegWrite          ; $F8 MEV_REGWRITE (raw YM2612 register write)
        dw      Seq_Op_Macro             ; $F9 MEV_MACRO (arm slot[1])
        dw      Seq_BadOpcode            ; $FA reserved
        dw      Seq_BadOpcode            ; $FB reserved
        dw      Seq_BadOpcode            ; $FC reserved
        dw      Seq_BadOpcode            ; $FD reserved
        dw      Seq_BadOpcode            ; $FE reserved
        dw      Seq_Op_End               ; $FF MEV_END
SeqOpcodeTable_End:

        ; 32 dw entries, one per $E0..$FF opcode — a short table would send
        ; high opcodes into the neighbouring table's bytes as a "handler".
        if (SeqOpcodeTable_End-SeqOpcodeTable) <> 32*2
          error "SeqOpcodeTable must be exactly 32 dw entries ($E0..$FF), got \{(SeqOpcodeTable_End-SeqOpcodeTable)/2}"
        endif
