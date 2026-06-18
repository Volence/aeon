; ======================================================================
; engine/sound_sequencer.asm — Z80 music-event-list interpreter (Sound 1C)
;
; Assembled INLINE inside the z80_sound_driver.asm `phase 0` blob (included
; after SndDrv_SetBank, before the even-pad). Hardware-AGNOSTIC: it walks the
; per-channel byte streams, counts durations, handles loops, and DISPATCHES
; musical events to writer hooks. The hooks are now FULLY WIRED (branching on
; sc_route): FM routes call the Fm_* writers (engine/sound_fm.asm), PSG routes
; call the Psg_* writers (engine/sound_psg.asm), and the DAC route's $E2 trigger
; calls Snd_StartSample. Under DEBUG the trace ring fires independently.
;
; OBSERVABILITY SEAM (design choice, documented per the task):
;   Each musical event does TWO independent things:
;     (a) under DEBUG, appends a trace record to SND_SEQ_TRACE (MCP-observable)
;     (b) calls a per-event writer hook (Seq_Hook*) — now wired to real writers.
;   The trace is kept SEPARATE from the writer hooks so observability stays
;   independent of the audio path.
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
; Called once per tempo tick by the DAC loop's Timer-A overflow poll (Task 5):
; the loop polls Timer A's overflow flag, re-arms, and calls here. Clobbers
; af,bc,de,hl,ix.
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
        call    Seq_HookNoteOn           ; -> Fm_NoteOn / Psg_NoteOn / Psg_Noise per route
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
        call    Seq_HookNoteOff          ; -> Fm_NoteOff / Psg_NoteOff per route
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
        call    Seq_HookSetVol           ; -> Fm_SetVolume / Psg_SetVolume per route
        pop     hl
        jp      Seq_ContinueFetch        ; jp (not jr): the 1D repeat handlers pushed this out of jr range

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
        call    Seq_HookSetPatch         ; FM: Fm_PatchLoad + re-apply vol; PSG/DAC ignore
        pop     hl
        jp      Seq_ContinueFetch        ; jp (not jr): the 1D repeat handlers pushed this out of jr range

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
        call    Seq_HookDac              ; -> Snd_StartSample (DAC sample id in sc_note)
        pop     hl
        jp      Seq_ContinueFetch        ; jp (not jr): the 1D repeat handlers pushed this out of jr range

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
        call    Seq_HookNoteOn           ; -> Fm_NoteOn / Psg_NoteOn / Psg_Noise per route
        ret                              ; time advanced -> done this tick

; $E5 MEV_REPEAT_START (no operand) : save the current (post-opcode) ptr as the
; body-start the matching $E6 jumps back to. Zero tick. Does NOT touch
; sc_repeat_count — the count is established when $E6 is first reached (so a
; fresh body always re-enters with count==0). The transcoder emits FLAT,
; single-level repeats (NO nesting), so one sc_repeat_ptr/sc_repeat_count per
; channel suffices; nested REPEAT_START would overwrite the saved ptr (unsupported).
; Calls NO writer hook -> just manipulates hl + state (like LoopPoint/Jump), so hl
; stays the live stream ptr.
; Clobbers: af (DEBUG trace only). Manipulates: hl (kept live). Uses ix.
Seq_Op_RepeatStart:
        ld      (ix+sc_repeat_ptr), l
        ld      (ix+sc_repeat_ptr+1), h  ; save body-start ptr (post-opcode)
    ifdef __DEBUG__
        push    hl
        ld      a, SEQEV_RPT_START
        call    Seq_Trace
        pop     hl
    endif
        jr      Seq_ContinueFetch        ; zero tick

; $E6 MEV_REPEAT_END + nn : end of a repeatable body. sc_repeat_count is the
; "reps remaining" state machine (0 = fresh-OR-done):
;   fresh (count==0)  -> set count = nn (total reps)
;   dec count
;   count > 0 (more)  -> reload hl from sc_repeat_ptr (jump to body start), fetch
;   count == 0 (done) -> fall through PAST the operand (body played nn times),
;                        leaving count==0 so the NEXT repeat block re-arms fresh.
; Edge nn=1: fresh->set 1->dec->0->done, body played once, continue past. ✓
; Edge nn=0: would be malformed (the packer forbids 0); fresh->set 0->dec->255->
;   loops 255 more passes. Not emitted by the transcoder; not specially handled.
; Zero tick, calls NO writer hook (hl stays live across the jump-back / fall-through).
; Clobbers: af, b (b holds nn across the fresh test). b is already a scratch reg in
; the tick loop — the caller saves the channel counter with push/pop bc around
; Sequencer_Channel, and the .coord dispatch already does `ld b,0`.
; Manipulates: hl (jump-back reload OR live past the operand). Uses ix.
Seq_Op_RepeatEnd:
        ld      a, (hl)
        inc     hl                       ; a = nn (operand); hl now PAST the operand
        ld      b, a                     ; b = nn (preserve across the fresh test)
    ifdef __DEBUG__
        push    hl
        push    bc
        ld      a, SEQEV_RPT_END
        call    Seq_Trace                ; (preserves bc,de,hl)
        pop     bc
        pop     hl
    endif
        ld      a, (ix+sc_repeat_count)
        or      a
        jr      nz, .have_count          ; nonzero -> a repeat is in progress
        ld      a, b                     ; fresh -> seed remaining = nn (total)
.have_count:
        dec     a
        ld      (ix+sc_repeat_count), a  ; store decremented remaining
        jr      z, .done                 ; reached 0 -> body has played nn times
        ; more reps remain -> jump back to the saved body start.
        ld      l, (ix+sc_repeat_ptr)
        ld      h, (ix+sc_repeat_ptr+1)
        ; fall through to Seq_ContinueFetch with hl = body start
.done:
        ; if .done: hl already points past the operand (count left at 0 -> next
        ; repeat block re-arms fresh). Either way, resume fetching at hl.
        jr      Seq_ContinueFetch        ; zero tick

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
        dw      Seq_BadOpcode            ; $E4 reserved (MEV_PAN, T4)
        dw      Seq_Op_RepeatStart       ; $E5 MEV_REPEAT_START
        dw      Seq_Op_RepeatEnd         ; $E6 MEV_REPEAT_END
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
; Writer-HOOK dispatch (FM/PSG/DAC all wired). Each hook gates on the route
; class bits in sc_flags: FM routes call the Fm_* writers (engine/sound_fm.asm),
; PSG routes call the Psg_* writers (engine/sound_psg.asm); the DAC route's $E2
; trigger (Seq_HookDac) calls Snd_StartSample (no route gate — $E2 is DAC-only).
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
        call    Fm_PatchLoad             ; load the voice (preserves ix)
        ; Fm_PatchLoad wrote the patch's BASE TLs (full per-patch loudness) to the
        ; carriers, but NOT the channel's current volume — so re-apply sc_volume
        ; so a patch change preserves the intended loudness instead of jumping to
        ; patch-base until the next $E0. Fm_SetVolume re-reads the patch base TLs
        ; and writes base+log to the carriers, OVERWRITING (not stacking on) the TLs
        ; Fm_PatchLoad just wrote — no double-apply. Both routines preserve ix.
        ld      a, (ix+sc_volume)        ; a = current channel volume (linear 0..127)
        jp      Fm_SetVolume             ; re-apply volume to the carriers

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
