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
; Sequencer_Frame — the PER-FRAME engine (Phase 3). Runs ONCE per Timer-A
; overflow at the FIXED ~59.06 Hz frame rate (the DAC/idle-loop poll rearms +
; calls here). Replaces 1C's "one Timer-A tick = one event" model. For each
; active channel, in order:
;   (1) call ModUpdate — render the channel's MODULATION STATE to the YM
;       (write-on-change; a held single note writes nothing). Stream-agnostic.
;   (2) advance the per-channel TEMPO ACCUMULATOR (sc_tempo_accum -= 16). On a
;       borrow (an event-tick is due), reload (accum += tempo_base) and run the
;       EXISTING per-event-tick logic (Sequencer_Channel: dur_count + opcode
;       fetch/dispatch). Otherwise no event-tick this frame (a held note still
;       burns NO command-stream time — only the accumulator advanced).
; Clobbers af,bc,de,hl,ix.
; ----------------------------------------------------------------------
Sequencer_Frame:
        ; --- FRAME OBSERVABILITY: increment SND_STAT_TICK on EVERY call (now once
        ; per FRAME, the fixed ~59 Hz clock). Placed at the very top (BEFORE the
        ; active check) so the counter reflects each Timer-A overflow regardless of
        ; song-active state — the controller uses its rate to verify the frame
        ; frequency. Wraps mod 256. Clobbers af (Sequencer_Frame already does). ---
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
        push    bc                       ; preserve channel-loop counter (b) across
                                         ;   the calls (which clobber b)

        ; (1) modulation layer — render state -> YM (write-on-change). ix preserved.
        call    ModUpdate

        ; (2) tempo accumulator: subtract 16 each frame; borrow => event-tick due.
        ld      a, (ix+sc_tempo_accum)
        sub     16
        ld      (ix+sc_tempo_accum), a
        jr      nc, .chan_done           ; no borrow -> no event-tick this frame
        ; borrow: reload accumulator (+= tempo_base) and run one event-tick.
        add     a, (ix+sc_tempo_base)
        ld      (ix+sc_tempo_accum), a
        call    Sequencer_Channel        ; existing per-event-tick logic (ix preserved)
.chan_done:
        pop     bc
.next_chan:
        ld      de, SeqChannel_len       ; size added directly (no multiply)
        add     ix, de
        djnz    .chan_loop
        ret

; ----------------------------------------------------------------------
; ModUpdate — the MODULATION LAYER (Phase 3). Renders ONE channel's modulation
; STATE to the YM2612, once per frame. ix = the channel's SeqChannel.
;
; CONTRACT (load-bearing — must hold through Tasks 3–7):
;   * STREAM-AGNOSTIC: ModUpdate ONLY reads channel state (sc_*), it NEVER parses
;     a command/modulation stream. Adding the second (modulation) stream later
;     populates the same state via a separate reader — ModUpdate is untouched.
;     This is the design-for-C seam.
;   * WRITE-ON-CHANGE: it writes the YM only when the RENDERED value changes. A
;     held single note writes its freq/key/patch once at onset (via the existing
;     key-on path) and then NOTHING per frame — NO redundant per-frame re-asserts
;     (the cycle-budget mandate; tools/cycle_budget_phase3.md). The cheap held-
;     note path below is that no-op.
;   * Preserves ix (the channel loop relies on it).
;
; PITCH PATHS (Phase 3 Tasks 3+4): an FM channel whose note was set by
; MEV_PITCHENV keys its pitch from the PER-SONG fnum table via Fm_NoteFromTable.
;   * count==1 (Task 3) — SINGLE held note, WRITE-ON-CHANGE: render iff SCF_REKEY
;     is armed (a MEV_PITCHENV just (re)keyed this channel) — look up sc_points[0]
;     (idx 0..$83) + sc_transpose, write $A4/$A0 + key on, set sc_note, and CLEAR
;     SCF_REKEY. Otherwise the note is held -> NO YM writes (a pure cursor check).
;     The ONLY producer of sc_points here is MEV_PITCHENV, which ALWAYS arms
;     SCF_REKEY, so the rekey arm covers every count==1 change.
;   * count>=2 (Task 4, .multipoint) — TRILL/ARP, re-articulated EVERY frame: the
;     cursor cycles the points (wrap at sc_pt_count) once per ~59 Hz frame and
;     keys sc_points[cursor] each frame. The first point sounds on the arm frame
;     (SCF_REKEY -> render cursor 0 without advancing); subsequent frames advance.
;     Writing every frame is correct — the pitch changes per frame (that's the
;     trill); the write-on-change rule governs HELD single notes only.
; Gating count==1 on SCF_REKEY keeps the existing SONG_TEST path EXACT: the loader
; inits sc_pt_count=1, so a bare-note FM channel takes the count==1 path, but its
; notes are keyed by Sequencer_Channel's hook (NOT MEV_PITCHENV), so they never arm
; SCF_REKEY -> ModUpdate is a no-op for them (a single flag test), as in Task 2.
;
; PAN (Task 6): rendered here, write-on-change — $B4+chan is written only when
; sc_pan differs from sc_last_pan (a held pan, incl. the no-MEV_PAN default, writes
; nothing). Per-op TL bias (Task 6) is NOT rendered here — it is latched in
; Fm_PatchLoad at patch load / note (the Zyrinx key-on latch), so ModUpdate has no
; per-frame op-bias cost. Voice-step deltas (Task 5) and portamento (Task 7) are
; NOT rendered yet; their seams (sc_patch vs sc_last_patch, sc_porta_incr) are left
; for those tasks. ModUpdate stays STREAM-AGNOSTIC (reads sc_* state only).
;
; Clobbers: af (held-note no-op) or af,bc,de,hl (render path). Preserves ix.
; ----------------------------------------------------------------------
ModUpdate:
        ; Non-FM channels (PSG / DAC) have no per-frame FM modulation to render in
        ; Phase 3a -> no-op. (PSG modulation is out of scope; see spec §1.)
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z

        ; --- PAN (Task 6): write $B4 ONLY when sc_pan changed since last written.
        ; Independent of the note/pitch logic below (pan persists across notes), so
        ; it is rendered first, every frame, write-on-change. A held pan (sc_pan ==
        ; sc_last_pan) writes nothing — including the no-MEV_PAN default (both 0),
        ; leaving the patch's own $B4 (set by Fm_PatchLoad) untouched.
        ld      a, (ix+sc_pan)
        cp      (ix+sc_last_pan)
        jr      z, .pan_done             ; unchanged -> no $B4 write
        ld      (ix+sc_last_pan), a      ; commit the shadow (a = sc_pan)
        call    Fm_SetPan                ; write $B4+chan = sc_pan (preserves ix)
.pan_done:

        ld      a, (ix+sc_pt_count)
        cp      2
        jr      nc, .multipoint          ; pt_count >= 2 -> trill/arp (Task 4)

        ; --- count==1 single-note pitch path (WRITE-ON-CHANGE) ---
        ; Render only when a MEV_PITCHENV armed a (re)key; else the note holds and
        ; we write NOTHING (the cycle-budget mandate). A held single note is thus a
        ; cheap flag test per frame.
        bit     SCF_REKEY_B, (ix+sc_flags)
        ret     z                        ; not armed -> held note -> NO YM writes
        ld      a, (ix+sc_points)        ; sc_points[0] = the single pitch point
        ld      (ix+sc_note), a          ; sc_note = last-rendered note index
        res     SCF_REKEY_B, (ix+sc_flags) ; consume the (re)key arm
        jp      Fm_NoteFromTable         ; look up per-song table + key on (preserves ix)

.multipoint:
        ; --- count>=2 trill/arp pitch path (PER-FRAME re-articulation) ---------
        ; Cursor-cycle the pitch points ONCE PER FRAME (the ~59 Hz frame clock),
        ; wrapping at sc_pt_count, and re-key sc_points[cursor] every frame. For a
        ; multi-point note the pitch changes EACH frame — that IS the trill/arp —
        ; so writing the YM every frame is correct here (the write-on-change rule
        ; governs HELD single notes only; see the count==1 path above).
        ;
        ; FIRST-POINT-ON-ARM: Seq_Op_PitchEnv sets sc_pt_cursor=0 and arms SCF_REKEY.
        ; On the frame the note arms we render sc_points[0] and consume the arm
        ; WITHOUT advancing — so the first point sounds on the arm frame. Every
        ; subsequent frame (REKEY clear) advances the cursor first, then renders.
        ; This makes the audible sequence points[0], points[1], ... points[n-1],
        ; points[0], ... at the frame rate.
        ;
        ; mod-arithmetic with NO divu: increment the cursor and compare against
        ; count; on reaching count, wrap to 0 (a counter/compare, per conventions).
        ld      a, (ix+sc_pt_cursor)
        bit     SCF_REKEY_B, (ix+sc_flags)
        jr      nz, .mp_armed            ; armed -> render cursor (==0) as-is, no advance
        inc     a                        ; advance the cursor
        cp      (ix+sc_pt_count)
        jr      c, .mp_store             ; cursor < count -> in range
        xor     a                        ; cursor == count -> wrap to 0
.mp_store:
        ld      (ix+sc_pt_cursor), a
.mp_armed:
        res     SCF_REKEY_B, (ix+sc_flags) ; consume any arm (no-op when already clear)
        ; a = cursor; index sc_points[cursor] (cursor is 0..count-1, count<=5).
        ld      c, a
        push    ix
        pop     hl                       ; hl = SeqChannel base
        ld      b, 0
        add     hl, bc                   ; hl = base + cursor
        ld      a, sc_points
        add     a, l
        ld      l, a
        jr      nc, .mp_nocarry
        inc     h                        ; carry into high byte (sc_points offset add)
.mp_nocarry:
        ld      a, (hl)                  ; a = sc_points[cursor] (absolute fnum idx)
        ld      (ix+sc_note), a          ; sc_note = last-rendered note index
        jp      Fm_NoteFromTable         ; look up per-song table + key on (preserves ix)

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

; $E7 MEV_NOTE_RAW + a4 a0 dd : key an FM note at a RAW frequency word (the exact
; $A4/$A0 bytes) for duration dd, bypassing FmPitchTableZ. Lets a VGM-derived song
; reproduce the original chip pitch EXACTLY (sub-C0 bass + microtuning the note
; table can't reach). FM-only: a non-FM route still consumes the 3 operands and
; advances time, but does not key (the packer routes NOTE_RAW only to FM channels).
; Advances time (like NOTE_DUR).
Seq_Op_NoteRaw:
        ld      a, (hl)
        inc     hl                       ; a = $A4 value (block|fnumHi)
        ld      d, a                     ; d = $A4 (Fm_NoteOnFreq input)
        ld      (ix+sc_note), a          ; stash $A4 for debug/mirror visibility
        ld      a, (hl)
        inc     hl                       ; a = $A0 value (fnum low)
        ld      e, a                     ; e = $A0 (Fm_NoteOnFreq input)
        ld      a, (hl)
        inc     hl                       ; a = duration
        ld      (ix+sc_dur_count), a     ; explicit duration
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h  ; commit ptr before the hook clobbers hl
        set     SCF_KEYED_B, (ix+sc_flags) ; SCF_KEYED
    ifdef __DEBUG__
        ld      a, SEQEV_NOTEON
        call    Seq_Trace                ; preserves de (the fnum word)
    endif
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z                        ; non-FM route -> time advanced, no key
        ; RETRIGGER the hardware envelope: key OFF then key ON, so every note
        ; re-attacks. The original B&R driver keys off->on per note (1599 offs /
        ; 801 ons in the reference VGM); without the key-off a re-keyed channel
        ; never re-attacks and decays to silence after the first note (the "blips"
        ; bug). NOTE_RAW-only: the note-index path (1C demo) is unchanged. The
        ; key-off..key-on are tens of Z80 cycles apart (Fm_NoteOff repark + the
        ; $A4/$A0 writes inside Fm_NoteOnFreq), ample for the EG to see the edge.
        push    de                       ; save fnum word across the key-off
        call    Fm_NoteOff               ; key OFF (clobbers de; preserves hl,ix)
        pop     de                       ; de = $A4/$A0 again
        call    Fm_NoteOnFreq            ; key ON at raw freq (preserves ix)
        ret                              ; time advanced -> done this tick

; $E8 MEV_PITCHENV + count + count idx bytes : set the channel's pitch-envelope
; points and ARM a (re)key. This is a COORDINATION opcode that ALSO advances time
; (like a note): it sets up the channel's modulation STATE — it does NOT write the
; YM here. ModUpdate (the per-frame renderer) keys/holds the note write-on-change.
;   * read count (1..5), store sc_pt_count
;   * read `count` absolute note-index bytes into sc_points[0..count-1]
;   * sc_pt_cursor = 0
;   * set SCF_KEYED (a note is now live) + SCF_REKEY (ModUpdate must (re)articulate
;     next frame even if the rendered index is unchanged — a same-pitch retrigger)
;   * reload sc_dur_default (paces the note like a bare Note; a following WAIT/
;     SetDur sets the hold length) and ADVANCE TIME (commit ptr, ret)
; The packer routes MEV_PITCHENV only to FM channels; a non-FM route would still
; set state here but ModUpdate's FM gate means nothing is rendered (harmless). The
; re-key RULE is finalized in Task 5; for now an armed count==1 note keys once and
; holds. Clobbers af, bc, de. Commits hl -> sc_stream_ptr (then ret, ending the tick). Uses ix.
; `count` is trusted from the stream (the packer guarantees 1..5; a 0 would make djnz
; copy 256 bytes, >5 would overrun sc_points[5]) — packer is the sole guarantor, per the
; engine's trust-the-packer operand model.
Seq_Op_PitchEnv:
        ld      a, (hl)
        inc     hl                       ; a = count (1..5); hl past the count byte
        ld      (ix+sc_pt_count), a
        ld      b, a                     ; b = count (loop bound)
        push    ix
        pop     de                       ; de = SeqChannel base (so we can index sc_points)
        ld      a, e
        add     a, sc_points
        ld      e, a
        jr      nc, .no_carry
        inc     d                        ; carry into high byte (sc_points offset add)
.no_carry:
        ; de -> &sc_points[0]; copy `count` operand bytes hl -> de.
.copy_pts:
        ld      a, (hl)
        inc     hl                       ; consume one point byte (absolute index 0..$83)
        ld      (de), a
        inc     de
        djnz    .copy_pts
        ; cursor 0, arm key + rekey.
        ld      (ix+sc_pt_cursor), 0
        set     SCF_KEYED_B, (ix+sc_flags)
        set     SCF_REKEY_B, (ix+sc_flags)
        ; pace like a bare note: reload the default duration, commit ptr, advance.
        ld      a, (ix+sc_dur_default)
        ld      (ix+sc_dur_count), a
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h  ; commit ptr (hl is dead after this opcode)
    ifdef __DEBUG__
        ld      a, SEQEV_NOTEON
        call    Seq_Trace                ; trace as a note-on (the audible effect)
    endif
        ret                              ; time advanced -> done this tick (ModUpdate renders)

; $E4 MEV_PAN + b4 : set the channel's pan/AMS/FMS state (the raw YM $B4 byte:
; bits7-6 L/R, bits5-4 AMS, bits2-0 FMS). Coordination SETTER (like Vol/Patch):
; stores the operand into sc_pan and continues the fetch loop (ZERO TICK). Does
; NOT write the YM here — ModUpdate renders sc_pan to $B4+chan write-on-change.
; The transcoder computes the $B4 byte from the Zyrinx pan command; the opcode
; just carries it. Calls NO writer hook (just stores state, like LoopPoint), so hl
; stays the live stream ptr across the handler.
; Clobbers: af (DEBUG trace only). Manipulates: hl (kept live). Uses ix.
Seq_Op_Pan:
        ld      a, (hl)
        inc     hl                       ; consume the $B4 operand byte
        ld      (ix+sc_pan), a           ; store pan state (rendered by ModUpdate)
    ifdef __DEBUG__
        ld      a, SEQEV_VOL             ; reuse the VOL trace code (no dedicated pan code)
        call    Seq_Trace                ; preserves hl (the live stream ptr)
    endif
        jp      Seq_ContinueFetch        ; zero tick

; $E9 MEV_OPBIAS + op(0..3) + val : set one operator's additive TL bias. Coordination
; SETTER (zero tick): stores val into sc_opbias[op]. The bias takes effect at the
; NEXT patch load / note (Fm_PatchLoad adds it to the $40-group TLs) — matching the
; Zyrinx latch-at-key-on model — so there is NO per-frame re-assert and ModUpdate
; is untouched. Calls NO writer hook, so hl stays the live stream ptr.
; `op` is trusted from the stream (the packer guarantees 0..3); a value > 3 would
; index past sc_opbias[3] into sc_porta_accum — packer is the sole guarantor.
; Clobbers: af, bc (the op index math). Manipulates: hl (kept live). Uses ix.
Seq_Op_OpBias:
        ld      a, (hl)
        inc     hl                       ; a = op index (0..3)
        and     3                        ; defensive clamp to 0..3 (no overrun)
        ld      c, a                     ; c = op index
        ld      a, (hl)
        inc     hl                       ; a = bias value
        ; sc_opbias[op] = val : index the per-op array off the channel base.
        push    hl                       ; save stream ptr across the pointer math
        push    ix
        pop     hl                       ; hl = SeqChannel base
        ld      b, 0
        add     hl, bc                   ; hl = base + op
        push    af                       ; save bias value across the offset add
        ld      a, sc_opbias
        add     a, l
        ld      l, a
        jr      nc, .nocarry
        inc     h                        ; carry into high byte
.nocarry:
        pop     af                       ; a = bias value
        ld      (hl), a                  ; sc_opbias[op] = val
    ifdef __DEBUG__
        ld      a, SEQEV_PATCH           ; reuse the PATCH trace code (timbre change)
        call    Seq_Trace
    endif
        pop     hl                       ; restore the live stream ptr
        jp      Seq_ContinueFetch        ; zero tick

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
        dw      Seq_Op_Pan               ; $E4 MEV_PAN
        dw      Seq_Op_RepeatStart       ; $E5 MEV_REPEAT_START
        dw      Seq_Op_RepeatEnd         ; $E6 MEV_REPEAT_END
        dw      Seq_Op_NoteRaw           ; $E7 MEV_NOTE_RAW
        dw      Seq_Op_PitchEnv          ; $E8 MEV_PITCHENV
        dw      Seq_Op_OpBias            ; $E9 MEV_OPBIAS
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
; active flag so Sequencer_Frame stops walking the streams.
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
