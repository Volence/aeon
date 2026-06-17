; ======================================================================
; engine/sound_sequencer.asm — Z80 music-event-list interpreter (Sound 1C)
;
; Assembled INLINE inside the z80_sound_driver.asm `phase 0` blob (included
; after SndDrv_SetBank, before the even-pad). Hardware-AGNOSTIC: it walks the
; per-channel byte streams, counts durations, handles loops, and DISPATCHES
; musical events to writer-hook stubs. In THIS task (2) the hooks are `ret`
; stubs and the only observable effect is the DEBUG trace ring — Tasks 3/4/6
; fill the hooks with real FM/PSG/DAC register writes (branching on sc_route)
; while the DEBUG trace keeps firing independently.
;
; OBSERVABILITY SEAM (design choice, documented per the task):
;   Each musical event does TWO independent things:
;     (a) under DEBUG, appends a trace record to SND_SEQ_TRACE (MCP-observable)
;     (b) calls a per-event writer hook (Seq_Hook*) — `ret` stubs this task.
;   The trace is SEPARATE from the writer hooks so later tasks can wire real
;   audio into the hooks without touching observability.
;
; CHANNEL ITERATION (research: Flamedriver zTrackUpdLoop, s2 zUpdateMusic):
;   ix holds the SeqChannel base; fields are (ix+sc_*). Advance to the next
;   channel with `ld de,SeqChannel_len / add ix,de` (size ADDED, never *index).
;
; FETCH/DISPATCH (research: s2 zFMDoNext .noteloop, Flamedriver zHandleCoordFlag):
;   Coordination flags ($E0..$FF) and set-default-duration (<$80) consume ZERO
;   ticks — the fetch is a LOOP that keeps reading bytes within the SAME tick
;   until a note or rest actually advances time.
; ======================================================================

; ----------------------------------------------------------------------
; Sequencer_Tick — advance every active channel by one tempo tick.
; Call once per tempo tick (Task 2 dry-run: once per VBlank from the ISR;
; Task 5 replaces this with the Timer-A sub-tick). Clobbers af,bc,de,hl,ix.
; ----------------------------------------------------------------------
Sequencer_Tick:
        ld      a, (SND_SEQ_ACTIVE)
        or      a
        ret     z                        ; no song playing -> nothing to do

        ld      a, (SND_SEQ_CHCOUNT)
        or      a
        ret     z                        ; no channels -> nothing to do
        ld      b, a                     ; b = channel count (djnz bound)
        ld      ix, SND_SEQ_CHANNELS     ; ix = first SeqChannel
.chan_loop:
        bit     0, (ix+sc_flags)         ; SCF_ACTIVE?
        jr      z, .next_chan            ; inactive -> skip this channel
        call    Sequencer_Channel
.next_chan:
        ld      de, SeqChannel_len       ; size added directly (no multiply)
        add     ix, de
        djnz    .chan_loop
        ret

; ----------------------------------------------------------------------
; Sequencer_Channel — advance ONE active channel (ix = its SeqChannel).
; Held notes burn a tick and return; on duration expiry, fetch+dispatch the
; next opcode(s). Clobbers af,c,de,hl (b is the channel-loop counter — saved
; by the `call` boundary; ix is preserved by every path here).
; ----------------------------------------------------------------------
Sequencer_Channel:
        dec     (ix+sc_dur_count)
        ret     nz                       ; note still holding -> no work this tick
        ; duration expired -> fetch the next time-advancing event
        ; (falls into Sequencer_NextOpcode)

; ----------------------------------------------------------------------
; Sequencer_NextOpcode — fetch+dispatch from the channel stream until an event
; ADVANCES time (note or rest). Zero-tick events (set-dur, vol, patch, dac,
; loop-point, jump, end) execute and loop back to fetch within the same tick.
; hl = stream read ptr (live only here); written back to sc_stream_ptr on the
; time-advancing paths and by the end handler.
; ----------------------------------------------------------------------
Sequencer_NextOpcode:
        ld      l, (ix+sc_stream_ptr)
        ld      h, (ix+sc_stream_ptr+1)  ; hl = current stream ptr
.fetch:
        ld      a, (hl)
        inc     hl                       ; consume the opcode byte
        ; --- range-dispatch ladder (research order: coord first, then rest/note) ---
        cp      MEV_VOL                  ; $E0
        jr      nc, .coord               ; $E0..$FF -> coordination-flag jump table
        cp      MEV_REST                 ; $80
        jr      c, .set_dur              ; $00..$7F -> set default duration (zero tick)
        jr      z, .rest                 ; $80       -> rest (advances time)
        ; else $81..$DF -> note (advances time)

; --- NOTE: pitch = opcode - MEV_NOTE_BASE; key-on; reload duration; advance ---
.note:
        sub     MEV_NOTE_BASE            ; a = pitch index
        ld      (ix+sc_note), a
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h  ; commit ptr before hooks clobber hl
        set     1, (ix+sc_flags)         ; SCF_KEYED
        ld      a, (ix+sc_dur_default)
        ld      (ix+sc_dur_count), a     ; reload duration (bare-note default)
    ifdef __DEBUG__
        ld      a, SEQEV_NOTEON
        call    Seq_Trace
    endif
        call    Seq_HookNoteOn           ; STUB this task (Task 3 wires FM/PSG)
        ret                              ; time advanced -> done this tick

; --- REST: key-off; reload duration; advance ---
.rest:
        res     1, (ix+sc_flags)         ; clear SCF_KEYED
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h
        ld      a, (ix+sc_dur_default)
        ld      (ix+sc_dur_count), a
    ifdef __DEBUG__
        ld      a, SEQEV_NOTEOFF
        call    Seq_Trace
    endif
        call    Seq_HookNoteOff          ; STUB this task
        ret                              ; time advanced -> done this tick

; --- SET DEFAULT DURATION ($00..$7F): zero tick, loop back to fetch ---
.set_dur:
        ld      (ix+sc_dur_default), a
        jr      .fetch                   ; no time cost -> keep fetching

; --- COORDINATION FLAG ($E0..$FF): jump-table dispatch (32 entries) ---
; (research: Flamedriver zHandleCoordFlag + PointerTableOffset)
.coord:
        sub     MEV_VOL                  ; a = 0..31 (index into SeqOpcodeTable)
        ld      c, a
        ld      b, 0
        push    hl                       ; save stream ptr across the table math
        ld      hl, SeqOpcodeTable
        add     hl, bc
        add     hl, bc                   ; +index*2 (dw entries)
        ld      a, (hl)
        inc     hl
        ld      h, (hl)
        ld      l, a                     ; hl = handler address
        ex      (sp), hl                 ; (sp) = handler, hl = stream ptr restored
        ret                              ; "jp (handler)" leaving hl = stream ptr
        ; NOTE: handlers receive hl = post-opcode stream ptr; they read any
        ; operand bytes (advancing hl), then either `jr/jp .fetch` (zero-tick)
        ; or store hl + `ret` (time-advancing / end).

; ======================================================================
; Coordination-flag handlers ($E0..$FF). Entered with hl = stream ptr just
; past the opcode byte. Zero-tick handlers fall back to .fetch; the note-dur
; handler and end handler store the ptr and return.
; ======================================================================

; $E0 MEV_VOL  + vv : set channel volume (linear 0..127), zero tick
Seq_Op_Vol:
        ld      a, (hl)
        inc     hl                       ; consume operand
        ld      (ix+sc_volume), a
    ifdef __DEBUG__
        push    hl
        ld      a, SEQEV_VOL
        call    Seq_Trace
        pop     hl
    endif
        call    Seq_HookSetVol           ; STUB this task
        jr      Seq_ContinueFetch

; $E1 MEV_PATCH + pp : set FM patch index, zero tick
Seq_Op_Patch:
        ld      a, (hl)
        inc     hl
        ld      (ix+sc_patch), a
    ifdef __DEBUG__
        push    hl
        ld      a, SEQEV_PATCH
        call    Seq_Trace
        pop     hl
    endif
        call    Seq_HookSetPatch         ; STUB this task
        jr      Seq_ContinueFetch

; $E2 MEV_DAC  + ss : DAC trigger (sample id in operand), zero tick.
; TIMING CHOICE: $E2 is treated as ZERO-tick — it fires the DAC trigger hook
; and continues the fetch loop. A following SetDur/Rest in the DAC channel's
; stream paces it (the DAC channel's "note" IS the trigger). Documented per task.
Seq_Op_Dac:
        ld      a, (hl)
        inc     hl
        ld      (ix+sc_note), a          ; stash trigger id (debug/visibility)
    ifdef __DEBUG__
        push    hl
        ld      a, SEQEV_DAC
        call    Seq_Trace
        pop     hl
    endif
        call    Seq_HookDac              ; STUB this task
        jr      Seq_ContinueFetch

; $E3 MEV_NOTE_DUR + nn dd : note nn with explicit duration dd (advances time)
Seq_Op_NoteDur:
        ld      a, (hl)
        inc     hl                       ; a = pitch operand
        ld      (ix+sc_note), a
        ld      a, (hl)
        inc     hl                       ; a = duration operand
        ld      (ix+sc_dur_count), a     ; explicit duration
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h  ; commit ptr before hooks clobber hl
        set     1, (ix+sc_flags)         ; SCF_KEYED
    ifdef __DEBUG__
        ld      a, SEQEV_NOTEON
        call    Seq_Trace
    endif
        call    Seq_HookNoteOn           ; STUB this task
        ret                              ; time advanced -> done this tick

; $EE MEV_LOOP_POINT : save the current (post-opcode) ptr as the loop target
Seq_Op_LoopPoint:
        ld      (ix+sc_loop_ptr), l
        ld      (ix+sc_loop_ptr+1), h
    ifdef __DEBUG__
        push    hl
        ld      a, SEQEV_LOOP
        call    Seq_Trace
        pop     hl
    endif
        jr      Seq_ContinueFetch        ; zero tick

; $EF MEV_JUMP : jump to the saved loop point
Seq_Op_Jump:
    ifdef __DEBUG__
        ld      a, SEQEV_JUMP
        call    Seq_Trace                ; (loads route from ix; hl not needed)
    endif
        ld      l, (ix+sc_loop_ptr)
        ld      h, (ix+sc_loop_ptr+1)    ; hl = loop target
        jr      Seq_ContinueFetch        ; zero tick -> resume fetching there

; $FF MEV_END : clear SCF_ACTIVE, store ptr, stop this channel (no time advance)
Seq_Op_End:
        res     0, (ix+sc_flags)         ; clear SCF_ACTIVE
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h
    ifdef __DEBUG__
        ld      a, SEQEV_END
        call    Seq_Trace
    endif
        ret                              ; channel done

; Reserved/unknown opcodes ($E4-$ED, $F0-$FE). The packer already forbids these;
; this is defense-in-depth. DEBUG: record the offending opcode, then stop the
; channel (clear SCF_ACTIVE) so a bad stream can't spin forever.
Seq_BadOpcode:
    ifdef __DEBUG__
        ld      a, (hl)                  ; (hl points just past the bad opcode; record
        ld      (SND_SEQ_BADOP), a       ;  the following byte as a coarse marker)
    endif
        res     0, (ix+sc_flags)         ; clear SCF_ACTIVE
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h
        ret

; Common tail for zero-tick handlers: resume the fetch loop with hl = stream ptr.
Seq_ContinueFetch:
        jp      Sequencer_NextOpcode.fetch

; ======================================================================
; SeqOpcodeTable — dw jump table for opcodes $E0..$FF (32 entries).
; Index = opcode - MEV_VOL. Reserved opcodes point at Seq_BadOpcode.
; ======================================================================
SeqOpcodeTable:
        dw      Seq_Op_Vol               ; $E0 MEV_VOL
        dw      Seq_Op_Patch             ; $E1 MEV_PATCH
        dw      Seq_Op_Dac               ; $E2 MEV_DAC
        dw      Seq_Op_NoteDur           ; $E3 MEV_NOTE_DUR
        dw      Seq_BadOpcode            ; $E4 reserved
        dw      Seq_BadOpcode            ; $E5 reserved
        dw      Seq_BadOpcode            ; $E6 reserved
        dw      Seq_BadOpcode            ; $E7 reserved
        dw      Seq_BadOpcode            ; $E8 reserved
        dw      Seq_BadOpcode            ; $E9 reserved
        dw      Seq_BadOpcode            ; $EA reserved
        dw      Seq_BadOpcode            ; $EB reserved
        dw      Seq_BadOpcode            ; $EC reserved
        dw      Seq_BadOpcode            ; $ED reserved
        dw      Seq_Op_LoopPoint         ; $EE MEV_LOOP_POINT
        dw      Seq_Op_Jump              ; $EF MEV_JUMP
        dw      Seq_BadOpcode            ; $F0 reserved
        dw      Seq_BadOpcode            ; $F1 reserved
        dw      Seq_BadOpcode            ; $F2 reserved
        dw      Seq_BadOpcode            ; $F3 reserved
        dw      Seq_BadOpcode            ; $F4 reserved
        dw      Seq_BadOpcode            ; $F5 reserved
        dw      Seq_BadOpcode            ; $F6 reserved
        dw      Seq_BadOpcode            ; $F7 reserved
        dw      Seq_BadOpcode            ; $F8 reserved
        dw      Seq_BadOpcode            ; $F9 reserved
        dw      Seq_BadOpcode            ; $FA reserved
        dw      Seq_BadOpcode            ; $FB reserved
        dw      Seq_BadOpcode            ; $FC reserved
        dw      Seq_BadOpcode            ; $FD reserved
        dw      Seq_BadOpcode            ; $FE reserved
        dw      Seq_Op_End               ; $FF MEV_END

; ======================================================================
; Seq_Trace (DEBUG) — append (sc_route<<4)|event_code to the trace ring.
; Enter with the event_code in `a`. Preserves bc,de,hl (so callers in the
; fetch path keep their stream ptr); clobbers af. ix = current SeqChannel.
; ======================================================================
    ifdef __DEBUG__
Seq_Trace:
        push    hl
        push    bc
        ld      c, a                     ; c = event_code (low nibble)
        ld      a, (ix+sc_route)
        add     a, a
        add     a, a
        add     a, a
        add     a, a                     ; a = route << 4 (route <= 15, no carry-out)
        or      c                        ; a = (route<<4) | event_code
        ld      c, a                     ; c = trace byte
        ld      a, (SND_SEQ_TRACE_WR)
        and     SND_SEQ_TRACE_LEN-1      ; defensive wrap (len is a power of two)
        ld      l, a
        ld      h, SND_SEQ_TRACE>>8       ; trace ring is page-aligned ($1A00)
        ld      (hl), c                  ; trace[wr] = byte
        inc     a
        and     SND_SEQ_TRACE_LEN-1      ; wr = (wr+1) & (LEN-1)
        ld      (SND_SEQ_TRACE_WR), a
        pop     bc
        pop     hl
        ret
    endif

; ======================================================================
; Writer-HOOK stubs (Task 2). Each is `ret`. Tasks 3/4/6 fill these in,
; branching on (ix+sc_route): Seq_HookNoteOn/Off -> FM key + PSG; SetVol ->
; log-vol x carrier-mask; SetPatch -> FM patch load; Dac -> 1B DAC trigger.
; They run with ix = current SeqChannel; the fetch path treats hl/bc/de as
; clobberable across these calls (it commits the stream ptr first).
; ======================================================================
Seq_HookNoteOn:
        ret
Seq_HookNoteOff:
        ret
Seq_HookSetVol:
        ret
Seq_HookSetPatch:
        ret
Seq_HookDac:
        ret
