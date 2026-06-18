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
        ; --- TICK OBSERVABILITY (Task 5): increment SND_STAT_TICK on EVERY call.
        ; Placed at the very top (BEFORE the active check) so the counter reflects
        ; each Timer-A overflow regardless of song-active state — the controller
        ; uses its increment RATE to verify the Timer-A tick frequency. Wraps mod
        ; 256. Clobbers af (Sequencer_Tick already clobbers af). ---
        ld      a, (SND_STAT_TICK)
        inc     a
        ld      (SND_STAT_TICK), a

        ld      a, (SND_SEQ_ACTIVE)
        or      a
        ret     z                        ; no song playing -> nothing to do

        ld      a, (SND_SEQ_CHCOUNT)
        or      a
        ret     z                        ; no channels -> nothing to do
        ld      b, a                     ; b = channel count (djnz bound)
        ld      ix, SND_SEQ_CHANNELS     ; ix = first SeqChannel
.chan_loop:
        bit     SCF_ACTIVE_B, (ix+sc_flags) ; SCF_ACTIVE?
        jr      z, .next_chan            ; inactive -> skip this channel
        push    bc                       ; preserve channel-loop counter (b): the
        call    Sequencer_Channel        ;   .coord path clobbers b via `ld b,0`
        pop     bc                       ;   and a `call` does NOT preserve b
.next_chan:
        ld      de, SeqChannel_len       ; size added directly (no multiply)
        add     ix, de
        djnz    .chan_loop
        ret

; ----------------------------------------------------------------------
; Sequencer_Channel — advance ONE active channel (ix = its SeqChannel).
; Held notes burn a tick and return; on duration expiry, fetch+dispatch the
; next opcode(s). Clobbers af,bc,de,hl (b is NOT preserved — the .coord path
; does `ld b,0`; the caller's channel-loop counter is saved by an explicit
; push/pop bc around this call. ix is preserved by every path here).
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
        set     SCF_KEYED_B, (ix+sc_flags) ; SCF_KEYED
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
        res     SCF_KEYED_B, (ix+sc_flags) ; clear SCF_KEYED
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
        push    hl                       ; hook clobbers hl; stream ptr stays LIVE here
        call    Seq_HookSetVol           ; STUB this task
        pop     hl
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
        push    hl                       ; hook clobbers hl; stream ptr stays LIVE here
        call    Seq_HookSetPatch         ; STUB this task
        pop     hl
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
        push    hl                       ; hook clobbers hl; stream ptr stays LIVE here
        call    Seq_HookDac              ; STUB this task
        pop     hl
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
        set     SCF_KEYED_B, (ix+sc_flags) ; SCF_KEYED
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
        res     SCF_ACTIVE_B, (ix+sc_flags) ; clear SCF_ACTIVE
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h
    ifdef __DEBUG__
        ld      a, SEQEV_END
        call    Seq_Trace
    endif
        ret                              ; channel done

; Reserved/UNKNOWN opcodes ($E4-$ED, $F0-$FE). The packer already forbids these;
; this is defense-in-depth against an unknown opcode only — it stops the channel
; (clear SCF_ACTIVE) so an unrecognized byte can't be re-dispatched forever.
; It does NOT catch a non-terminating (all-zero-tick) loop body: that case is
; prevented at PACK time by song_packer's loop-body validation (a LoopPoint..Jump
; span must contain a Note/Rest/NoteDur), not by any runtime iteration cap.
Seq_BadOpcode:
    ifdef __DEBUG__
        ld      a, (hl)                  ; (hl points just past the bad opcode; record
        ld      (SND_SEQ_BADOP), a       ;  the following byte as a coarse marker)
    endif
        res     SCF_ACTIVE_B, (ix+sc_flags) ; clear SCF_ACTIVE
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
; Writer-HOOK dispatch (Task 3 wired FM; Task 4 wires PSG; DAC still a `ret`
; stub — Task 6). Each hook gates on the route class bits in sc_flags: FM routes
; call the Fm_* writers (engine/sound_fm.asm), PSG routes call the Psg_* writers
; (engine/sound_psg.asm), the DAC route falls through to `ret`.
; They run with ix = current SeqChannel. EVERY writer (Fm_* AND Psg_*) preserves
; ix — the channel loop relies on it. INVARIANT for hl across these calls:
;   - TIME-ADVANCING hooks (NoteOn/NoteOff, called from .note/.rest/.notedur):
;     the handler commits the stream ptr to sc_stream_ptr and then `ret`s, ending
;     the tick. hl is dead after the hook, so it is freely clobberable there.
;   - ZERO-TICK hooks (SetVol/SetPatch/Dac, called from Seq_Op_Vol/Patch/Dac):
;     the handler keeps the stream ptr LIVE in hl and continues the fetch loop
;     (Seq_ContinueFetch -> .fetch reads ld a,(hl)/inc hl WITHOUT reloading from
;     sc_stream_ptr). These hooks DO clobber hl (e.g. Fm_PatchPtr/Fm_PatchLoad),
;     so the zero-tick handlers MUST push/pop hl around the hook call. Any future
;     hook-calling zero-tick handler must do the same or the stream ptr corrupts.
;
; NOTE on inputs (the writers expect them):
;   Seq_HookNoteOn  -> Fm_NoteOn / Psg_NoteOn (a = pitch index = sc_note);
;                      PSGN route -> Psg_Noise (noise control + volume).
;   Seq_HookNoteOff -> Fm_NoteOff / Psg_NoteOff (ix only)
;   Seq_HookSetVol  -> Fm_SetVolume / Psg_SetVolume (a = linear vol = sc_volume)
;   Seq_HookSetPatch-> Fm_PatchLoad (FM only; PSG ignores patch -> ret)
; ======================================================================
Seq_HookNoteOn:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z                        ; non-FM/PSG (DAC) -> stub (Task 6)
        ld      a, (ix+sc_note)          ; a = pitch index
        ld      b, a                     ; (preserve pitch across the route test)
        ld      a, (ix+sc_route)
        cp      CHROUTE_PSGN
        ld      a, b                     ; a = pitch index again
        jp      z, Psg_Noise             ; noise route -> noise control + volume
        jp      Psg_NoteOn               ; tone route
.fm:
        ld      a, (ix+sc_note)          ; a = pitch index
        jp      Fm_NoteOn

Seq_HookNoteOff:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jp      nz, Fm_NoteOff
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z
        jp      Psg_NoteOff

Seq_HookSetVol:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z
        ld      a, (ix+sc_volume)        ; a = linear volume (0..127)
        jp      Psg_SetVolume
.fm:
        ld      a, (ix+sc_volume)        ; a = linear volume (0..127)
        jp      Fm_SetVolume

Seq_HookSetPatch:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z                        ; PSG/DAC have no patch -> ignore
        call    Fm_PatchPtr              ; hl = FmPatch ptr for sc_patch
        jp      Fm_PatchLoad

; Seq_HookDac (Task 6) — the DAC route's $E2 trigger. Seq_Op_Dac stashed the
; operand (the sample id) in sc_note; look it up in DacSampleTable and start the
; 1B DAC sample path. Snd_StartSample touches only RAM + the $6000 latch + $2B/$2A
; (no ROM read) and re-parks $2A + restores de=$4001 — safe inside the Timer-A
; tick (DAC not paused but between samples). Called only for the $E2 opcode, so no
; route gate is needed here. Preserves ix; the zero-tick Seq_Op_Dac handler
; push/pops hl around this call, so the clobbered hl is fine.
Seq_HookDac:
        ld      a, (ix+sc_note)          ; a = DAC sample id (the $E2 operand)
        call    Snd_DacLookup            ; a=id -> hl=descriptor (carry set if bad)
        ret     c                        ; bad id -> ignore the trigger
        jp      Snd_StartSample          ; start DAC playback from the descriptor

; ======================================================================
; Sequencer_StopAll — the StopMusic primitive (wired to the command API in
; Task 6). Key-off every FM channel + silence all PSG channels, then clear the
; active flag so Sequencer_Tick stops walking the streams.
;
; IMPLEMENTATION (decision 4): direct hardware silencing rather than a per-
; channel hook loop — it is unconditional (independent of whatever routes the
; current song happened to load) and cannot leave a note hanging:
;   * FM: key-off all six possible FM channels by writing $28 = chsel for chsel
;     $00,$01,$02,$04,$05,$06 (op-mask 0 = key off). Direct via part I ($4000).
;   * PSG: Psg_SilenceAll emits $9F/$BF/$DF/$FF (max attenuation, all 4 channels).
; Then SND_SEQ_ACTIVE = 0. Does NOT touch $2B (DAC enable) — DAC is owned by the
; 1B loop. Clobbers af, bc, hl. Preserves de (the DAC loop's $4001), ix.
; ======================================================================
Sequencer_StopAll:
        ; --- FM: key-off all six FM channels (op-mask 0) via $28 on part I. ---
        ld      hl, Seq_FmKeyoffChsels   ; the six chsel nibbles
        ld      b, 6
.fm_keyoff:
        ld      a, SND_REG_KEY_ONOFF     ; $28 (key on/off, always part I)
        ld      (SND_Z80_YM_A0), a       ; select $28 on $4000
        nop                              ; inter-write delay (no busy-poll)
        ld      a, (hl)                  ; chsel (op-mask bits 7..4 = 0 -> key off)
        ld      (SND_Z80_YM_A1), a       ; $4001 = $28 data
        inc     hl
        djnz    .fm_keyoff
        ; re-park reg $2A on the part-I addr port for the DAC consumer.
        ld      a, SND_REG_DAC_DATA      ; $2A
        ld      (SND_Z80_YM_A0), a

        ; --- PSG: max attenuation on all four channels. ---
        call    Psg_SilenceAll

        ; --- stop the sequencer. ---
        xor     a
        ld      (SND_SEQ_ACTIVE), a
        ret

; The six FM channel-select nibbles ($28 data bytes with op-mask 0 -> key off):
; FM1/2/3 = $00/$01/$02 (part I), FM4/5/6 = $04/$05/$06 (part II, the +4 part
; offset). FM6 is the DAC in 1C but harmless to key off (op-mask 0).
Seq_FmKeyoffChsels:
        db      00h, 01h, 02h, 04h, 05h, 06h
