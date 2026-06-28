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
        jr      z, .run_sfx              ; no song -> still run SFX (own the chip)

        ld      a, (SND_SEQ_CHCOUNT)
        or      a
        jr      z, .run_sfx              ; no channels -> still run SFX
        ld      b, a                     ; b = channel count (djnz bound)
        ld      ix, SND_SEQ_CHANNELS     ; ix = first SeqChannel
.chan_loop:
        bit     SCF_ACTIVE_B, (ix+sc_flags) ; SCF_ACTIVE?
        jr      z, .next_chan            ; inactive -> skip this channel
        push    bc                       ; preserve channel-loop counter (b) across
                                         ;   the calls (which clobber b)

        ; (1) modulation layer — render state -> YM (write-on-change). ix preserved.
        call    ModUpdate

        ; (1b) slot[1] macro/reg-automation (Component D). ARBITRATION: after the
        ; named-slot contours (ModUpdate) and BEFORE the slot[0] reader below. Gated
        ; on sc_mod_ptr != 0 so a single-stream song (every channel NULL — the
        ; Moving Trucks baseline) pays one word-test per channel and is byte-identical.
        ; bc is already saved by the push above; ix is preserved by MacroTick.
        ld      a, (ix+sc_mod_ptr)
        or      (ix+sc_mod_ptr+1)
        call    nz, MacroTick

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
.run_sfx:
        jp      Sfx_Frame                ; tail-call: SFX writes land AFTER music

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
        ; Phase 5a: if an SFX has stolen this physical voice, render NOTHING (no
        ; $B4/note-fill/re-key writes) — the SfxChannel owns the channel. The music
        ; cursor still advances in Sequencer_Channel, so the song never desyncs.
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        ; PSG route: the FM modulation path below is skipped. Music + SFX PSG channels
        ; both advance a PSG vol-env (spec §4) via the shared sc_psgenv* fields (now at
        ; +39..+41 on BOTH structs). Music + SFX PSG channels also both run the pitch-MOD
        ; path now (the SFX-only gate was removed in Phase 1; sc_mod_* exist on both
        ; structs at the same offsets). An un-modulated channel (sc_mod_ctrl==0) — which
        ; includes every music PSG channel without an active MEV_MODSET, and all noise
        ; tracks — pays only one test before falling through to the vol-env.
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .is_fm
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z                        ; DAC or other non-PSG -> nothing
        ; --- PSG PITCH MODULATION (spec §5): if armed, sweep/vibrato the tone
        ; divisor. Shares the FM triangle core (Mod_Advance) via Psg_ApplyMod; a
        ; non-modulated PSG SFX (sc_mod_ctrl==0) pays only this one test. Runs BEFORE
        ; the vol-env so both compose (mod re-latches the divisor; env re-emits volume).
        ld      a, (ix+sc_mod_ctrl)
        or      a
        call    nz, Psg_ApplyMod         ; advance accum + re-latch tone divisor (no re-key)
        ; NOTE: the noise-route gate (audit D1) was reverted — the Z80 code blob is at
        ; its HARD size limit ($16F0) and the gate cost ~9 bytes. The invariant
        ; "noise tracks never set sc_mod_ctrl" still holds (the transcoder never emits
        ; MEV_MODSET on a noise track). Re-add as a BUILD-TIME transcoder reject (0 Z80
        ; bytes) or restore this gate once Z80 space is recovered. See DEFERRED_WORK D1/F5.
.psg_env:
        ; --- PSG VOLUME ENVELOPE (spec §4): advance the contour + re-emit the volume
        ; (music + SFX; PsgEnvUpdate handles the noise route too — the HCZ2 hi-hat).
        ld      a, (ix+sc_psgenv)
        or      a
        ret     z                        ; no PSG vol-env -> done
        jp      PsgEnvUpdate             ; advance the contour + emit (tail-call, preserves ix)
.is_fm:

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

        ; --- PITCH MODULATION (spec §5): continuous additive freq-word vibrato/sweep
        ; on the HELD note (no key-on). Runs every frame regardless of the re-key state
        ; below — modulates held FM notes on music + SFX channels alike (the SFX-only
        ; gate was removed in Phase 1; sc_mod_ctrl exists on both structs at the same
        ; offset). A non-modulated channel (sc_mod_ctrl==0) pays only this one test.
        ld      a, (ix+sc_mod_ctrl)
        or      a
        call    nz, Mod_ApplyVibrato     ; advance + write-on-change $A4/$A0 (no key-on)
.vibrato_done:
        ; --- FM TL VOLUME ENVELOPE (spec §4 flagship): advance the carrier-TL contour
        ; + re-emit volume (folds sc_env_out in Fm_SetVolume). Runs EVERY frame (held
        ; notes too) so the swell/tremolo evolves across a held note. sc_env==0 -> one
        ; test then skip (byte-identical to no envelope; MT regression-safe).
        ld      a, (ix+sc_env)
        or      a
        call    nz, FmEnvUpdate          ; advance + re-emit carrier TLs (preserves ix)

        ; --- NOTE-FILL (#4 gate articulation): per-frame countdown; key OFF early when it
        ; reaches 0, leaving a staccato gap until the next attack. sc_fill_count==0 means
        ; disabled (sc_fill_master 0) OR already expired -> one test, no cost. Runs BEFORE the
        ; held-note `ret z` below so a held note can be released MID-duration (the gap). It is
        ; reloaded from sc_fill_master at every key-on (.rekey_on). Only channels with
        ; sc_fill_master != 0 (the gated percussion) are affected; every other channel keeps
        ; sc_fill_master == 0 -> full legato, byte-identical to before this feature.
        ld      a, (ix+sc_fill_count)
        or      a
        jr      z, .notefill_done        ; disabled / expired -> nothing
        dec     a
        ld      (ix+sc_fill_count), a
        jr      nz, .notefill_done       ; not yet 0 -> still keyed
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .notefill_done        ; already off -> idempotent
        call    Fm_NoteOff               ; reached 0 -> key OFF (clears SCF_KEYED); preserves ix
.notefill_done:

        ld      a, (ix+sc_pt_count)
        cp      2
        jr      nc, .multipoint          ; pt_count >= 2 -> trill/arp (Task 4)

        ; --- count==1 single-note pitch path (WRITE-ON-CHANGE) ---
        ; Render only when a MEV_PITCHENV armed a (re)key; else the note holds and
        ; we write NOTHING (the cycle-budget mandate). A held single note is thus a
        ; cheap flag test per frame.
        bit     SCF_REKEY_B, (ix+sc_flags)
        ret     z                        ; not armed -> held note -> NO YM writes
        res     SCF_REKEY_B, (ix+sc_flags) ; consume the (re)key arm
        ; THE RE-KEY RULE (corrected vs the oracle): MEV_PITCHENV is the only thing that
        ; reaches here (sole producer of sc_points + sole SCF_REKEY arm) — so the render
        ; below fires ONLY on a pitch op, never on a voice/timbre op (MEV_PATCH/MEV_OPBIAS/
        ; MEV_REGDELTA never arm SCF_REKEY). Every armed re-key RE-ARTICULATES, even when
        ; the rendered index is UNCHANGED: the real Zyrinx driver re-keys on EVERY pitch
        ; command (keyon_pending set unconditionally at driver $0519, gated only on that
        ; flag at $0BB0 — there is NO pitch-equality test), and the packer emits one
        ; MEV_PITCHENV per genuine sequence re-issue = one per oracle re-attack (incl.
        ; same-pitch repeats). Held notes still cost
        ; nothing: with no new PITCHENV, SCF_REKEY is never armed and the `ret z` above
        ; writes nothing — so this is per-event-tick traffic, not per-frame.
        ld      a, (ix+sc_points)        ; sc_points[0] = the single pitch point (idx)
        ld      (ix+sc_note), a          ; sc_note = last-rendered note index (update)
        ; RE-KEY STYLE (lever SND_REKEY_OFF_THEN_ON, sound_constants): DEFAULT = clean
        ; re-key. If the channel is ALREADY keyed we key-OFF first so the YM2612 sees a
        ; real 0->1 edge and retriggers the EG (oracle-faithful; matches the NOTE_RAW
        ; path). If NOT keyed (fresh note from silence/after a Rest), the key-on alone is
        ; the 0->1 edge — no key-off. SND_REKEY_OFF_THEN_ON=0 skips the key-off (key-on
        ; only, no retrigger when already keyed) for A/B-ing attack density vs the oracle.
    if SND_REKEY_OFF_THEN_ON
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .rekey_on             ; not keyed -> key-on alone gives the edge
        call    Fm_NoteOff               ; keyed -> key OFF first (forces a fresh 0->1 edge)
    endif
.rekey_on:
        ld      a, (ix+sc_points)        ; (re)load sc_points[0] (Fm_NoteOff clobbered a)
        bit     SCF_PITCH_CHROMATIC_B, (ix+sc_flags)
        jr      z, .rekey_persong        ; clear -> music: per-song fnum table
        call    Fm_NoteOn                ; SFX: chromatic FmPitchTableZ (same table the note-on used)
        jr      .rekey_fill
.rekey_persong:
        call    Fm_NoteFromTable         ; look up per-song table + key on (preserves ix)
.rekey_fill:
        ; reload the note-fill countdown for this fresh attack (master 0 -> stays legato)
        ld      a, (ix+sc_fill_master)
        ld      (ix+sc_fill_count), a
        ret

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
        bit     SCF_PITCH_CHROMATIC_B, (ix+sc_flags)
        jp      z, Fm_NoteFromTable      ; clear -> music: per-song table (tail-call, preserves ix)
        jp      Fm_NoteOn                ; set -> SFX: chromatic table (tail-call, preserves ix)

; ----------------------------------------------------------------------
; PsgEnvUpdate — advance one PSG (or noise) channel's volume-envelope contour by
; one frame and re-emit the channel volume so the new attenuation delta takes
; effect. Gated by ModUpdate: entered for a PSG route (music OR SFX) with
; sc_psgenv != 0 (sc_psgenv* live at +39/+40/+41 on both SeqChannel + SfxChannel).
; Body byte semantics (S3K zDoVolEnv-exact): plain value -> store as sc_psgenv_out +
; advance cursor; $80 -> cursor=0 and re-read; $81 -> sustain-hold (keep sc_psgenv_out,
; no advance, do NOT silence); $83 -> full rest: key the PSG channel off + disable env.
; In: ix = SeqChannel/SfxChannel (PSG/noise route). Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
PsgEnvUpdate:
        ld      a, (ix+sc_psgenv)        ; 1-based env id
        call    PsgVolEnv_Resolve        ; hl = body base; carry set = unknown id -> bail
        ret     c
.reread:
        ld      a, (ix+sc_psgenv_cur)    ; a = cursor
        ld      e, a
        ld      d, 0
        add     hl, de                   ; hl = &body[cursor]
        ld      a, (hl)                  ; a = body byte
        cp      PsgVolEnvCtl_Loop        ; $80 -> loop cursor to 0
        jr      z, .loop
        cp      PsgVolEnvCtl_Sustain     ; $81 -> sustain-hold (no advance, keep last out)
        jr      z, .sustain
        cp      PsgVolEnvCtl_Rest        ; $83 -> full rest (silence + disable)
        jr      z, .rest
        ; --- plain value: store as the atten delta, advance the cursor ---
        ld      (ix+sc_psgenv_out), a
        inc     (ix+sc_psgenv_cur)
.emit:
        ; re-emit the channel volume so the new sc_psgenv_out delta lands this frame.
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; folds sc_psgenv_out in; preserves ix
.loop:
        ld      (ix+sc_psgenv_cur), 0    ; cursor -> 0
        ld      a, (ix+sc_psgenv)        ; recompute body base (hl was advanced above)
        call    PsgVolEnv_Resolve
        ret     c
        jr      .reread
.sustain:
        ; hold last sc_psgenv_out (no advance, no silence) — re-emit so the held
        ; attenuation stays applied against the live sc_volume.
        jr      .emit
.rest:
        ; $83 full-rest: silence THIS note's tail (S3K zDoVolEnvFullRest -> zRestTrack).
        ; Do NOT clear sc_psgenv — the envelope ID must PERSIST so the NEXT note-on
        ; (which resets sc_psgenv_cur to 0 via Psg_EnvCursorReset) REPLAYS the contour.
        ; S3K keeps FMVolEnv/PSGVolEnv set and only resets the VolEnv cursor per note
        ; (zFinishTrackUpdate). Zeroing the id here disabled the envelope for every
        ; subsequent note in a run -> a flat loud-noise blast (the HCZ2 hi-hat bug).
        ; The cursor stays parked on the rest byte, so until the next note-on this
        ; re-silences each frame (matching S3K's per-frame re-rest).
        jp      Psg_NoteOff              ; silence this PSG channel (tail-call, preserves ix)

; ----------------------------------------------------------------------
; FmEnvUpdate — advance one FM channel's carrier-TL volume-envelope contour by one
; frame and re-emit the channel volume so the new attenuation delta takes effect
; (folded into Fm_SetVolume's Fm_ScratchLog). The FM mirror of PsgEnvUpdate; the
; UNIFIED sc_env/sc_env_cur/sc_env_out slot (+39/+40/+41) serves FM (here) xor PSG
; (PsgEnvUpdate) — a channel is FM xor PSG.
; Body bytes (mirror PSG, sound_tables_z80.asm): plain value -> sc_env_out + advance;
; $80 -> loop cursor to 0 + re-read; $81 -> sustain-hold (keep last out, no advance);
; $83 -> TL-silence the tail (sc_env_out = $7F, park the cursor). NOTE the deliberate
; deviation from PSG's $83 key-off: FM has its own EG, so a key-off would cut the
; release tail; a TL-silence preserves it (documented in the plan's Self-review).
; In: ix = FM channel, sc_env != 0. Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
FmEnvUpdate:
        ld      a, (ix+sc_env)           ; 1-based FM env id
        call    FmVolEnv_Resolve         ; hl = body base; carry set = unknown id -> bail
        ret     c
.reread:
        ld      a, (ix+sc_env_cur)       ; a = cursor
        ld      e, a
        ld      d, 0
        add     hl, de                   ; hl = &body[cursor]
        ld      a, (hl)                  ; a = body byte
        cp      FmVolEnvCtl_Loop         ; $80 -> loop cursor to 0
        jr      z, .loop
        cp      FmVolEnvCtl_Sustain      ; $81 -> sustain-hold (no advance, keep last out)
        jr      z, .sustain
        cp      FmVolEnvCtl_Rest         ; $83 -> TL-silence the tail
        jr      z, .rest
        ; --- plain value: store as the carrier-TL atten delta, advance the cursor ---
        ; NOTE: $82 is RESERVED (future RELEASE point) and is NOT yet a control code.
        ; Until assigned, $82 falls through here: stored as an attenuation byte and
        ; clamped like any plain value. Do NOT emit $82 in a body expecting it to be inert.
        ld      (ix+sc_env_out), a
        inc     (ix+sc_env_cur)
.emit:
        ; re-emit the channel volume so the new sc_env_out delta lands this frame.
        ld      a, (ix+sc_volume)
        jp      Fm_SetVolume             ; folds sc_env_out into the carrier TLs; preserves ix
.loop:
        ld      (ix+sc_env_cur), 0       ; cursor -> 0
        ld      a, (ix+sc_env)           ; recompute body base (hl was advanced above)
        call    FmVolEnv_Resolve
        ret     c
        jr      .reread
.sustain:
        ; hold last sc_env_out (no advance) — re-emit so the held atten stays applied.
        jr      .emit
.rest:
        ; FM $83 = TL-silence (NOT key-off): sc_env_out = $7F so the carrier TLs go
        ; silent while the YM EG release continues. The cursor stays parked on the rest
        ; byte so it re-silences each frame until the next attack resets sc_env_cur.
        ld      (ix+sc_env_out), SND_FM_TL_MAX
        jr      .emit

; ----------------------------------------------------------------------
; Mod_ReArm — per-note pitch-modulation re-arm (port of zPrepareModulation).
; Called from the FM key-on tail (Fm_NoteOnFreq), AFTER sc_base_freq is latched and
; ONLY for an SFX channel (the caller gates ix >= SND_SFX_BASE — sc_mod_* are
; SfxChannel-only fields). If sc_mod_ctrl is off, returns immediately (one bit-test
; for a non-modulated SFX note). Else (mirror zPrepareModulation):
;   * clear the accumulated offset (accum = 0)
;   * seed sc_mod_steps = raw_step >> 1 (S3K's `srl a` — the FIRST half-period is
;     half-length; subsequent reversals reload the FULL sc_mod_step_raw, see
;     Mod_ApplyVibrato — faithful to S3K's iy+3 reload)
;   * reload sc_mod_speed = sc_mod_speed_raw (fresh countdown)
;   * prime sc_last_freq = sc_base_freq so the first vibrato render writes only once
;     the offset actually changes (write-on-change).
; In: ix = SFX channel (sc_base_freq already latched by the caller). Clobbers af.
; Preserves bc,de,hl,ix.
; ----------------------------------------------------------------------
Mod_ReArm:
        ld      a, (ix+sc_mod_ctrl)
        or      a
        ret     z                        ; mod off -> nothing
        xor     a
        ld      (ix+sc_mod_accum), a
        ld      (ix+sc_mod_accum+1), a   ; accum = 0
        ; sc_mod_steps = raw_step >> 1 (initial half-period; reversals reload FULL raw).
        ld      a, (ix+sc_mod_step_raw)
        srl     a
        ld      (ix+sc_mod_steps), a
        ; sc_mod_speed = raw speed (fresh countdown for this note).
        ld      a, (ix+sc_mod_speed_raw)
        ld      (ix+sc_mod_speed), a
        ; prime the write-on-change shadow to the base note (d=$A4, e=$A0).
        ld      a, (ix+sc_base_freq)
        ld      (ix+sc_last_freq), a
        ld      a, (ix+sc_base_freq+1)
        ld      (ix+sc_last_freq+1), a
        ret

; ----------------------------------------------------------------------
; Mod_Advance — one frame of the pitch-modulation TRIANGLE/ACCUMULATOR (the chip-
; AGNOSTIC core of zDoModulation, shared by the FM and PSG renderers so the triangle
; machinery exists exactly once — the $16F0 code ceiling has no room to duplicate it).
; Runs the faithful sequence and produces the modulated 16-bit word, leaving the chip
; WRITE to the caller (FM emits $A4/$A0; PSG re-latches the tone divisor). Sequence:
;   * count down sc_mod_wait (one-shot delay; when it hits 0, hold it at 1 so the
;     modulation fires every frame thereafter)
;   * every sc_mod_speed frames: reload sc_mod_speed = sc_mod_speed_raw, then add the
;     sign-extended sc_mod_delta to the 16-bit sc_mod_accum
;   * final word = sc_base_freq + sc_mod_accum  (FM: hi=$A4,lo=$A0; PSG: hi,lo divisor)
;   * every sc_mod_steps applications: reload sc_mod_steps = sc_mod_step_raw (the FULL
;     raw count — S3K's iy+3) and NEGATE sc_mod_delta (triangle direction flip)
;   * write-on-change vs sc_last_freq: when the word is UNCHANGED (or still in the wait
;     delay) the caller must emit nothing.
; In: ix = SFX channel, sc_mod_ctrl != 0. Out: CARRY SET => skip (no chip write this
; frame). CARRY CLEAR => write needed: hl = modulated word, sc_last_freq updated, and
; d=hi/e=lo of the word loaded ready for the caller's emit. Clobbers af,bc,de,hl.
; Preserves ix.
; ----------------------------------------------------------------------
Mod_Advance:
        ; --- wait countdown (one-shot delay, then held at 1) ---
        dec     (ix+sc_mod_wait)
        jr      z, .past_wait            ; reached 0 this frame -> proceed (hold at 1)
        scf                              ; still delaying -> CARRY set => caller skips
        ret
.past_wait:
        inc     (ix+sc_mod_wait)         ; hold wait at 1 so it fires every frame hereafter

        ; --- speed gate: only accumulate every sc_mod_speed frames ---
        dec     (ix+sc_mod_speed)
        jr      nz, .sustain
        ld      a, (ix+sc_mod_speed_raw) ; reload the speed countdown (iy+1 in S3K)
        ld      (ix+sc_mod_speed), a
        ; bc = sign-extended signed delta (CF = sign bit of delta -> $FF/$00 in b).
        ld      a, (ix+sc_mod_delta)
        ld      c, a
        add     a, a                     ; CF = sign bit
        sbc     a, a                     ; a = $FF if delta<0 else $00
        ld      b, a                     ; bc = sign-extended delta
        ld      l, (ix+sc_mod_accum)
        ld      h, (ix+sc_mod_accum+1)
        add     hl, bc                   ; accum += delta
        ld      (ix+sc_mod_accum), l
        ld      (ix+sc_mod_accum+1), h
.sustain:
        ; --- final word = base + accum. FM applies the BLOCK-BOUNDARY CORRECTION (spec
        ; §4): split block|fnum, add accum to the 11-bit fnum, renormalize block so the
        ; modulated pitch crosses octaves seamlessly. PSG has no block: plain 16-bit add
        ; onto the 10-bit divisor. Mod_Advance is shared, so split on route class. Runs
        ; only when sc_mod_ctrl!=0 (caller-gated), so normal playback never reaches here.
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      z, .psg_word
        ; --- FM: hl = 11-bit fnum, b = block (0..7) ---
        ld      a, (ix+sc_base_freq)     ; $A4 value = (block<<3)|fnumHi3
        and     007h
        ld      h, a                     ; fnum bits 10..8
        ld      l, (ix+sc_base_freq+1)   ; fnum bits 7..0  -> hl = 11-bit fnum
        ld      a, (ix+sc_base_freq)
        rrca
        rrca
        rrca
        and     007h
        ld      b, a                     ; b = block
        ld      e, (ix+sc_mod_accum)
        ld      d, (ix+sc_mod_accum+1)
        add     hl, de                   ; hl = fnum + signed accum
        ; hi correction: fnum >= FNUM_HI -> fnum>>=1, block++ (block capped at 7)
        ld      a, b
        cp      007h
        jr      z, .fm_lo                ; block already 7 -> cannot raise further
        ld      a, h
        cp      FNUM_HI>>8
        jr      c, .fm_lo                ; fnum hi-byte < HI hi-byte -> below HI
        jr      nz, .fm_hi_do            ; hi-byte > HI hi-byte -> above HI
        ld      a, l
        cp      FNUM_HI&0FFh
        jr      c, .fm_lo                ; equal hi-byte, lo < HI lo -> below HI
.fm_hi_do:
        srl     h
        rr      l                        ; fnum >>= 1
        inc     b                        ; block += 1
        jr      .fm_pack                 ; one step suffices for a per-frame vibrato delta
.fm_lo:
        ; lo correction: fnum < FNUM_LO and block > 0 -> fnum<<=1, block--
        ld      a, b
        or      a
        jr      z, .fm_pack              ; block 0 -> keep low fnum (valid lowest pitch)
        ld      a, h
        cp      FNUM_LO>>8
        jr      c, .fm_lo_do             ; fnum hi-byte < LO hi-byte -> below LO
        jr      nz, .fm_pack             ; hi-byte > LO hi-byte -> at/above LO
        ld      a, l
        cp      FNUM_LO&0FFh
        jr      nc, .fm_pack             ; equal hi-byte, lo >= LO lo -> at/above LO
.fm_lo_do:
        add     hl, hl                   ; fnum <<= 1
        dec     b                        ; block -= 1
.fm_pack:
        ld      a, b
        add     a, a
        add     a, a
        add     a, a                     ; block << 3
        or      h                        ; (block<<3)|fnumHi3 = $A4 value (h is 0..7)
        ld      h, a                     ; hl = packed word (h=$A4 value, l=$A0 value)
        jr      .have_word
.psg_word:
        ld      h, (ix+sc_base_freq)     ; PSG: divisor hi
        ld      l, (ix+sc_base_freq+1)   ; PSG: divisor lo
        ld      c, (ix+sc_mod_accum)
        ld      b, (ix+sc_mod_accum+1)   ; bc = signed accum
        add     hl, bc                   ; hl = modulated divisor
.have_word:
        ; --- triangle reverse: every sc_mod_steps applications flip the delta sign --
        dec     (ix+sc_mod_steps)
        jr      nz, .write
        ld      a, (ix+sc_mod_step_raw)  ; reload the FULL raw step count (iy+3 in S3K)
        ld      (ix+sc_mod_steps), a
        ld      a, (ix+sc_mod_delta)
        neg
        ld      (ix+sc_mod_delta), a
.write:
        ; --- write-on-change: signal "skip" (CF set) when the word is unchanged ------
        ld      a, h
        cp      (ix+sc_last_freq)
        jr      nz, .changed
        ld      a, l
        cp      (ix+sc_last_freq+1)
        jr      nz, .changed
        scf                              ; unchanged -> CARRY set => caller writes nothing
        ret
.changed:
        ld      (ix+sc_last_freq), h
        ld      (ix+sc_last_freq+1), l
        ld      d, h                     ; d = word hi (FM $A4 value / PSG divisor hi)
        ld      e, l                     ; e = word lo (FM $A0 value / PSG divisor lo)
        or      a                        ; CARRY clear => caller emits (a=l here, nonzero ok)
        ret

; ----------------------------------------------------------------------
; Mod_ApplyVibrato — one frame of FM continuous pitch modulation. Thin wrapper over
; the shared Mod_Advance triangle core (above): if it says "write", emit $A4/$A0 on
; the HELD note (NO key-on — vibrato changes pitch without retriggering the EG).
; Called from ModUpdate's FM path for an SFX channel with sc_mod_ctrl != 0 (the
; caller gates BOTH the SFX-channel test and sc_mod_ctrl). The PSG analogue is
; Psg_ApplyMod (sound_psg.asm), which shares the same Mod_Advance core.
; In: ix = FM SFX channel, sc_mod_ctrl != 0. Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
Mod_ApplyVibrato:
        call    Mod_Advance              ; advance triangle; CF set => no write this frame
        ret     c
        ; d=$A4 value, e=$A0 value (set by Mod_Advance).
        jp      Fm_WriteFreq             ; write $A4 then $A0, NO key-on (preserves ix)

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

; $ED MEV_NOTEFILL + master : set per-channel note-fill (frames keyed from attack), zero tick.
; 0 = legato/off. The countdown + early key-off run in ModUpdate (per-frame). State-only, no
; writer hook -> hl stays the live stream ptr.
Seq_Op_NoteFill:
        ld      a, (hl)
        inc     hl                       ; consume operand (master)
        ld      (ix+sc_fill_master), a
        jp      Seq_ContinueFetch

; $EB MEV_PSGENV + env_id : set the channel's PSG volume-envelope id (1-based; 0=none),
; reset the cursor to 0. Zero-tick state setter (mirror of Seq_Op_NoteFill). The per-frame
; contour is rendered by PsgEnvUpdate (ModUpdate) + folded in Psg_SetVolume. sc_psgenv*
; live at +39/+40 on BOTH music and SFX SeqChannels, so this opcode applies to either with
; no channel-class gate (a non-PSG channel never sees $EB — the transcoder only emits it on
; PSG streams — and the write would be in-bounds + inert anyway).
Seq_Op_PsgEnv:
        ld      a, (hl)
        inc     hl                       ; consume operand
        ld      (ix+sc_psgenv), a        ; set env id (music + SFX)
        ld      (ix+sc_psgenv_cur), 0    ; restart the contour from frame 0
        jp      Seq_ContinueFetch

; $F9 MEV_MACRO + dw blob_offset (BE) : (re)arm the channel's slot[1] macro stream.
; sc_mod_ptr = Snd_SongBase + offset; mark active; reset to the body start. Zero-tick
; state setter (mirror of Seq_Op_PsgEnv) — no writer hook, so hl stays the live
; slot[0] stream ptr through the handler. The offset is BIG-ENDIAN, rebased to an
; absolute Z80 address exactly like the loader's mod_ptr parse (z80_sound_driver.asm
; :1188-1196) and TAG_MAC_LOOP. The packer (Component E) back-patches the offset to a
; macro-body blob it emits in the same song.
Seq_Op_Macro:
        ld      d, (hl)
        inc     hl                       ; d = offset hi (big-endian)
        ld      e, (hl)
        inc     hl                       ; e = offset lo  (hl now past the operand)
        push    hl                       ; save the live slot[0] stream ptr
        ld      hl, (Snd_SongBase)
        add     hl, de                   ; hl = base + offset = absolute body ptr
        ld      (ix+sc_mod_ptr), l
        ld      (ix+sc_mod_ptr+1), h     ; arm slot[1] cursor at the body start
        ld      a, 1
        ld      (ix+sc_macro_active), a  ; mark active (sc_pad alias)
        pop     hl                       ; restore the slot[0] stream ptr
        jp      Seq_ContinueFetch        ; jp (not jr): out of jr range, like the others

; $F2 MEV_PSGNOISE + ctrl : set the SN76489 noise control byte (mode+rate), latch it for
; the per-note rate-3 gate + SFX-steal re-arm, and silence tone-ch2's VOLUME so ch2 makes
; no audible tone while its FREQUENCY clocks the noise. Zero-tick. Writing the control
; register RESETS the LFSR, so this is ON-CHANGE (the opcode), NOT per-note — each hit is
; re-articulated by the per-note PSG volume envelope instead. Music streams only (the SFX
; transcoder drops smpsPSGform); a non-noise channel never sees $F2.
Seq_Op_PsgNoise:
        ld      a, (hl)
        inc     hl                       ; consume operand (the $E0-$EF control byte)
        ld      (ix+sc_noise_mode), a    ; latch for the per-note rate-3 gate + steal re-arm
        ld      (SND_Z80_PSG), a         ; write the noise control (resets LFSR once)
        ld      a, SND_PSG_SILENCE_T3    ; $DF = tone-ch2 volume | max attenuation
        ld      (SND_Z80_PSG), a         ; silence ch2 tone (its frequency still clocks noise)
        jp      Seq_ContinueFetch

; $F4 MEV_LFO + value : write YM2612 $22 (bit3 enable | bits0-2 rate). The global LFO
; drives every channel's $B4 AMS (tremolo) / FMS (vibrato) depth bits (set by MEV_PAN).
; MUST re-park the DAC $2A addr after the $22 write: the addr port is parked on $2A
; during playback, so a stray $22 select would misroute the next DAC byte. Fm_YmWrite
; (part I) + Fm_ReparkDac both preserve hl (the live stream ptr). Zero-tick.
Seq_Op_Lfo:
        ld      c, (hl)                  ; c = operand ($22 value: enable|rate)
        inc     hl                       ; consume operand
        ld      a, SND_REG_LFO           ; $22
        ld      b, 0                     ; part I
        call    Fm_YmWrite               ; $4000=$22, $4001=value (preserves bc/de/hl/ix)
        call    Fm_ReparkDac             ; restore the DAC $2A park (DAC-safe)
        jp      Seq_ContinueFetch

; $EC MEV_MODSET + wait speed change step : latch the pitch-modulation params (the
; engine's smpsModSet). Zero-tick setter. sc_mod_ctrl is set nonzero iff ANY of the
; 4 params is nonzero (all-zero = mod off — the smpsModSet 0,0,0,0 idiom AB/3C use to
; cancel modulation). The actual per-note re-arm (accum=0, steps seeded raw/2) happens
; at the next FM key-on (Mod_ReArm); Mod_ApplyVibrato (ModUpdate) renders it per frame.
;
; SFX-CHANNEL GATE: sc_mod_* are SfxChannel-only fields (offset +42.., PAST a 39-byte
; music SeqChannel). The transcoder only emits $EC into SFX streams, but a music stream
; must NEVER write these fields (it would corrupt the next channel's RAM). So consume
; all 4 operands FIRST (keep the stream in sync), then SKIP the writes for a music
; channel (ix < SND_SFX_BASE => carry set). Mirror of Seq_Op_PsgEnv's gate.
Seq_Op_ModSet:
        ; --- read all 4 operands into b,c,d,e (wait/speed/delta/step) ---
        ld      a, (hl)
        inc     hl                       ; wait
        ld      b, a                     ; b = wait
        ld      a, (hl)
        inc     hl                       ; speed
        ld      c, a                     ; c = speed
        ld      a, (hl)
        inc     hl                       ; change/delta (signed)
        ld      d, a                     ; d = delta
        ld      a, (hl)
        inc     hl                       ; step (raw count)
        ld      e, a                     ; e = step
        ; --- music + SFX both write sc_mod_* now (the SFX-only gate was removed in
        ; Phase 1; sc_mod_* exist on both structs at the same offsets). The field
        ; writes below do not clobber hl, so the live stream ptr stays valid. ---
        ; ctrl = OR of all 4 params (nonzero => active, all-zero => off).
        ld      a, b
        or      c
        or      d
        or      e                        ; a = wait|speed|delta|step  (the off test)
        ld      (ix+sc_mod_wait), b
        ld      (ix+sc_mod_speed), c
        ld      (ix+sc_mod_speed_raw), c ; reload source for the speed countdown
        ld      (ix+sc_mod_delta), d      ; signed change/step delta
        ld      (ix+sc_mod_steps), e      ; raw step count (seeded raw/2 at re-arm)
        ld      (ix+sc_mod_step_raw), e   ; reload source for the steps countdown (FULL)
        ld      (ix+sc_mod_ctrl), a       ; nonzero => active; zero => off
        ; SFX FM: re-write the UNMODULATED base note to the chip with NO key-on, so a
        ; held tail (smpsNoAttack) snaps back to base pitch when a sweep modSet turns
        ; off — Fm_WriteFreq changes a HELD note's pitch with no EG retrigger, so the
        ; tail needs no re-key (kills the faint "second attack" at the main->tail seam).
        ; Before the first note the channel is keyed-off/silent so this stale-freq write
        ; is inaudible and the main note's key-on overwrites it that same frame.
        ld      a, (ix+sc_route)
        cp      CHROUTE_PSG1             ; FM routes (<6) only; PSG/noise skip
        jr      nc, .modset_done
        push    hl                       ; Fm_WriteFreq clobbers hl (the live stream ptr)
        ld      d, (ix+sc_base_freq)
        ld      e, (ix+sc_base_freq+1)
        call    Fm_WriteFreq             ; $A4/$A0 = base note, no $28 key-on
        pop     hl
.modset_done:
        jp      Seq_ContinueFetch

; $F0 MEV_SPINREV (no operand) : port of cfSpindashRev (S3K). Add the GLOBAL rev into
; this channel's sc_transpose (a shared-prefix field that Fm_NoteOn applies to the note
; index, so the spindash nC5 rises), cap the transpose at exactly $10, else increment the
; global. Zero-tick. No operand consumed. We BORROW hl to point at Snd_SpindashRev (so
; the cap-skip path can `inc (hl)` directly), so we PUSH/POP hl around the handler to
; keep the live stream ptr intact for Seq_ContinueFetch (the T3/T4 hl-preservation rule).
; The spindash rev RESET is folded into the SFX-dispatch path (Sfx_BeginSound zeroes
; Snd_SpindashRev for any NON-spindash SFX) rather than a second stream opcode — the
; S3K smpsResetSpindashRev at the END of the spindash loop is redundant with that fold
; (the next non-spindash SFX resets it), and folding saves the $16F0 code budget. So
; there is no Seq_Op_SpinRevReset handler; $F1 stays Seq_BadOpcode and the transcoder
; emits nothing for smpsResetSpindashRev.
Seq_Op_SpinRev:
        push    hl                       ; save the live stream ptr (we borrow hl for the global)
        ld      hl, Snd_SpindashRev
        ld      a, (hl)
        add     a, (ix+sc_transpose)     ; add the escalating rev into the track transpose
        ld      (ix+sc_transpose), a
        cp      010h                     ; transpose hit exactly $10 -> stop rising (S3K cap)
        jr      z, .spin_done            ; capped -> do NOT climb the global
        inc     (hl)                     ; otherwise climb the global by one
.spin_done:
        pop     hl                       ; restore the stream ptr for Seq_ContinueFetch
        jp      Seq_ContinueFetch

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
        inc     hl                       ; a = pitch operand (bit 7 = no-attack flag)
        ld      d, a                     ; save raw operand for the no-attack test below
        ld      (ix+sc_note), a
        ld      a, (hl)
        inc     hl                       ; a = duration operand
        ld      (ix+sc_dur_count), a     ; explicit duration
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h  ; commit ptr before hooks clobber hl
        set     SCF_KEYED_B, (ix+sc_flags) ; SCF_KEYED
        ; bit 7 = smpsNoAttack: a held continuation (looped fade tail). Skip the
        ; note-on hook entirely — no $28 re-attack AND no freq re-write — so the note
        ; rings on while only its Vol (TL) walks down. The transcoder leaves bit 7
        ; CLEAR on the first note after a modSet so that note still re-keys to reset
        ; the swept pitch; subsequent tail passes are held. (sc_note keeps the flag:
        ; only the hook reads it as a pitch index, and the hook is skipped here.)
        bit     7, d
        ret     nz                       ; no-attack -> held; duration counts, no re-key
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
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz                       ; SFX owns this voice -> advance time, no key
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
; set state here but ModUpdate's FM gate means nothing is rendered (harmless).
;
; THE RE-KEY RULE (finalized, Task 5): MEV_PITCHENV is the ONLY opcode that
; re-articulates a note. It arms SCF_REKEY -> ModUpdate (re)keys (default: clean
; key-off-then-on so the EG retriggers; see SND_REKEY_OFF_THEN_ON). A note thus
; re-articulates ONLY on a PITCH change. Voice/timbre opcodes — MEV_PATCH,
; MEV_OPBIAS, MEV_REGDELTA — change the held note's timbre WITHOUT keying (none of
; them touch $28 or set SCF_REKEY). The transcoder (Task 8) emits MEV_PITCHENV only
; on an ACTUAL pitch change, so the re-key DENSITY matches the oracle (the residual
; the reference player overproduced — spec §8). Clobbers af, bc, de. Commits hl ->
; sc_stream_ptr (then ret, ending the tick). Uses ix.
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
        ; (no DEBUG trace here: OpBias is a per-op TL micro-event that would flood the
        ;  32-entry trace ring; the audible note-on / patch change is traced elsewhere.)
        pop     hl                       ; restore the live stream ptr
        jp      Seq_ContinueFetch        ; zero tick

; $EA MEV_REGDELTA + count + count*(reg_sel, value) : VOICE-STEPPING — write `count`
; per-operator YM2612 registers IMMEDIATELY (mid-note) for THIS channel, part-aware.
; This is the minimal-register-delta primitive: a held note's TIMBRE is swept by
; writing only the registers that CHANGE between voice steps. The Zyrinx rapid lead
; step ($9C->$A0) differs by EXACTLY ONE byte (operator S1's TL = $40 group op0), so
; a rapid step is ONE MEV_REGDELTA with count=1 — NOT a full ~26-register patch
; reload (that is ~6,500 cyc, untenable per frame; tools/cycle_budget_phase3.md). A
; genuine instrument change at a note onset still uses MEV_PATCH (full load).
;
; --- THE RE-KEY RULE (the calibration target) ---
; A note RE-ARTICULATES (a fresh key — see the re-key STYLE below) ONLY on a PITCH
; change, i.e. exclusively via MEV_PITCHENV (which arms SCF_REKEY -> ModUpdate keys
; the note). Voice/timbre changes — MEV_PATCH, MEV_OPBIAS, and THIS MEV_REGDELTA —
; alter the HELD note's timbre and NEVER re-key: this handler does NOT write $28
; (key) and does NOT set SCF_REKEY. So a voice-step sweep over a held note produces
; EXACTLY ONE key-on (the MEV_PITCHENV that started the note); the sweep is heard as
; a continuous timbre change with no re-attacks. The transcoder (Task 8) emits
; MEV_PITCHENV ONLY on an actual pitch change, so the re-key DENSITY matches the
; oracle (the residual the reference player overproduced — see spec §8).
;
; --- DIRECT-WRITE rationale (the design-for-C seam is preserved) ---
; This handler writes the YM DIRECTLY (Fm_RegDelta) when the opcode executes,
; rather than setting state for ModUpdate to render. A zero-tick mid-note delta is a
; one-shot register write with no per-frame component, so a direct write is simpler
; AND correct (write-on-change is satisfied — the byte is written exactly once, when
; the step occurs, with no redundant per-frame re-assert). Crucially this keeps
; ModUpdate strictly state->YM (it never gains a stream-derived register-delta path),
; so the design-for-C seam (a second modulation stream reader writing the SAME state)
; is untouched. ModUpdate stays STREAM-AGNOSTIC.
;
; Coordination SETTER (ZERO TICK): consumes count + count*(reg_sel,value), writes
; each, and continues the fetch loop. FM-only — a non-FM route still consumes the
; operands (so the stream stays aligned) but writes NOTHING (the FM gate). `count`
; and the operand pairs are trusted from the stream (the packer guarantees count>=1
; and well-formed reg_sel/value), per the engine's trust-the-packer operand model.
; Clobbers: af, bc, de, hl. Keeps the stream ptr live in hl across the writes (it is
; pushed around each Fm_RegDelta, which clobbers hl). Uses ix.
Seq_Op_RegDelta:
        ld      a, (hl)
        inc     hl                       ; a = count; hl past the count byte
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        jr      nz, .skip_pre            ; SFX owns this voice -> consume operands, no write
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
.skip_pre:
        ; --- non-FM route: skip 2*count operand bytes, write nothing ---
        add     a, a                     ; bytes to skip = count*2 (reg_sel+value pairs)
        jr      z, .skipped              ; count==0 -> nothing to skip (defensive)
        ld      c, a
        ld      b, 0
        add     hl, bc                   ; advance hl past the operand pairs
.skipped:
        jp      Seq_ContinueFetch        ; zero tick
.fm:
        ld      b, a                     ; b = count (loop bound)
        ; (no DEBUG trace here: RegDelta is a mid-note voice-stepping micro-event that
        ;  would flood the 32-entry trace ring; the audible note-on is traced elsewhere.)
.delta_loop:
        ld      a, (hl)
        inc     hl                       ; a = reg_sel
        ld      c, (hl)
        inc     hl                       ; c = value
        push    bc                       ; save loop count (b) + value (unused after)
        push    hl                       ; Fm_RegDelta clobbers hl -> keep the stream ptr
        call    Fm_RegDelta              ; write one resolved YM register (a=reg_sel, c=value)
        pop     hl
        pop     bc
        djnz    .delta_loop
        jp      Seq_ContinueFetch        ; zero tick

; $F8 MEV_REGWRITE + part + reg + val : write ONE arbitrary YM2612 register for an
; EXPLICIT part (0/1), IMMEDIATELY. Zero command-tick. The part is carried by the
; operand (NOT Fm_RoutePart-derived) — this is the raw register escape hatch for
; whole-part / global regs. GUARD: reg==$2A (DAC data) and reg==$2B (DAC enable)
; are SKIPPED (the operands are still consumed) so a song can never clobber the DAC
; stream or click the enable edge. After the write, Fm_ReparkDac re-selects $2A on
; the addr port so a racing DAC byte lands on $2A. de=$4001 is preserved BY
; CONSTRUCTION (Fm_YmWrite/Fm_ReparkDac use absolute YM addressing). hl-rule: load
; all 3 operands first (hl ends past them = the resume ptr), then push/pop hl around
; the YM-write pair (defensive, the YmWrite/Repark calls already preserve hl).
; Clobbers: af, bc. Manipulates: hl (kept live). Uses ix.
Seq_Op_RegWrite:
        ld      a, (hl)
        inc     hl                       ; a = part (0/1); hl past part byte
        and     1                        ; mask to part bit (Fm_YmWrite tests bit 0)
        ld      b, a                     ; b = part
        ld      a, (hl)
        inc     hl                       ; a = reg; hl past reg byte
        ld      e, a                     ; e = reg (preserve across the val read)
        ld      a, (hl)
        inc     hl                       ; a = val; hl now PAST all 3 operands
        ld      c, a                     ; c = val
        ; --- DAC-reg guard: refuse $2A / $2B (skip the write, operands consumed) ---
        ld      a, e                     ; a = reg
        cp      SND_REG_DAC_DATA         ; $2A ?
        jr      z, .skip
        cp      SND_REG_DAC_ENABLE       ; $2B ?
        jr      z, .skip
        ld      a, e                     ; a = reg (Fm_YmWrite wants reg in a)
        push    hl                       ; defensive: keep the live stream ptr across the write
        call    Fm_YmWrite               ; a=reg, c=val, b=part (absolute addr; de untouched)
        call    Fm_ReparkDac             ; re-select $2A on the addr port
        pop     hl
.skip:
        jp      Seq_ContinueFetch        ; zero tick (jp: out of jr range to the tail)

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
; MacroTick — the slot[1] register-automation reader (Component D). Walks
; sc_mod_ptr executing tag-prefixed events until ONE frame is yielded
; (TAG_MAC_NEXT), then commits the cursor. Runs once/frame per active music
; channel, AFTER ModUpdate, BEFORE Sequencer_Channel (the arbitration order:
; named-slot contours render in ModUpdate -> slot[1] reg-writes here -> slot[0]
; opcodes in Sequencer_Channel). Gated by the caller on sc_mod_ptr != 0.
;
; In:  ix = SeqChannel (a MUSIC channel; the caller only walks SeqChannels).
; hl = the live cursor (local to this call): loaded from sc_mod_ptr, advanced
; over each event, committed back to sc_mod_ptr before every return/yield.
; Fm_YmWrite/Fm_ReparkDac preserve bc,de,hl,ix, so the cursor in hl survives a
; reg-write. TAG_MAC_END disables the stream (sc_mod_ptr = 0) so the caller's
; gate skips it next frame.
; Clobbers: af,bc,de,hl. Preserves ix.
; ======================================================================
MacroTick:
        ld      l, (ix+sc_mod_ptr)
        ld      h, (ix+sc_mod_ptr+1)     ; hl = macro-stream cursor
.fetch:
        ld      a, (hl)
        inc     hl                       ; consume the tag byte
        cp      TAG_MAC_NEXT             ; $E0 -> yield one frame
        jr      z, .next
        cp      TAG_MAC_REG              ; $E1 -> immediate reg write
        jr      z, .reg
        cp      TAG_MAC_LOOP             ; $E2 -> cursor = base + BE offset
        jr      z, .loop
        cp      TAG_MAC_END              ; $E3 -> disable the stream
        jr      z, .end
        ; unknown tag (defense-in-depth; the packer forbids these) -> disable the
        ; stream so a stray byte can't be re-walked forever.
        jr      .end

.next:
        ; yield: commit the cursor (pointing at the byte AFTER this tag) and return.
        ; Next frame resumes here. (Mirror the slot[0] commit-before-return at
        ; Sequencer_NextOpcode :590-591.)
        ld      (ix+sc_mod_ptr), l
        ld      (ix+sc_mod_ptr+1), h
        ret

.reg:
        ; TAG_MAC_REG + part + reg + val : immediate YM write + repark $2A. Reads
        ; three operand bytes (advancing hl), then writes via the Component-B
        ; primitive Fm_YmWrite (a=reg, c=val, b=part) and Fm_ReparkDac. GUARD:
        ; refuse reg == $2A and reg == $2B (the DAC data/enable regs) — a raw poke
        ; there would corrupt/silence the DAC stream; skip the write, keep walking.
        ld      c, (hl)
        inc     hl                       ; c = part (0/1)
        ld      b, c                     ; stash part in b (Fm_YmWrite wants part in b)
        ld      a, (hl)
        inc     hl                       ; a = reg
        ld      e, a                     ; e = reg (saved across the guard test)
        ld      c, (hl)
        inc     hl                       ; c = val
        cp      SND_REG_DAC_DATA         ; $2A?
        jr      z, .reg_skip
        cp      SND_REG_DAC_ENABLE       ; $2B?
        jr      z, .reg_skip
        ld      a, e                     ; a = reg (b=part, c=val already set)
        call    Fm_YmWrite               ; a=reg, c=val, b=part (preserves bc,de,hl,ix)
        call    Fm_ReparkDac             ; re-park $2A (preserves bc,de,hl,ix)
.reg_skip:
        jr      .fetch                   ; multiple regs per frame: keep walking

.loop:
        ; TAG_MAC_LOOP + dw blob_offset (BE) : cursor = Snd_SongBase + offset.
        ; Same "BE offset, handler adds base" convention as MEV_MACRO/the loader's
        ; mod_ptr rebase. Re-read in the same frame (no implicit yield) so a body
        ; that is pure REG..LOOP would spin forever — the packer (Component E2) MUST
        ; guarantee every loop body contains a TAG_MAC_NEXT; enforced packer-side, not here.
        ld      d, (hl)
        inc     hl                       ; d = offset hi (big-endian)
        ld      e, (hl)
        inc     hl                       ; e = offset lo
        ld      hl, (Snd_SongBase)       ; hl = song base
        add     hl, de                   ; hl = base + offset = absolute cursor
        jr      .fetch

.end:
        ; disable the stream: NULL sc_mod_ptr + clear the active flag so the caller's
        ; gate skips this channel next frame. (No cursor commit needed — it's inert.)
        xor     a
        ld      (ix+sc_mod_ptr), a
        ld      (ix+sc_mod_ptr+1), a
        ld      (ix+sc_macro_active), a
        ret

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
        dw      Seq_Op_RegDelta          ; $EA MEV_REGDELTA (voice-stepping)
        dw      Seq_Op_PsgEnv            ; $EB MEV_PSGENV
        dw      Seq_Op_ModSet            ; $EC MEV_MODSET
        dw      Seq_Op_NoteFill          ; $ED MEV_NOTEFILL (gate articulation)
        dw      Seq_Op_LoopPoint         ; $EE MEV_LOOP_POINT
        dw      Seq_Op_Jump              ; $EF MEV_JUMP
        dw      Seq_Op_SpinRev           ; $F0 MEV_SPINREV
        dw      Seq_BadOpcode            ; $F1 reserved (SPINREV reset is dispatch-folded)
        dw      Seq_Op_PsgNoise          ; $F2 MEV_PSGNOISE
        dw      Seq_BadOpcode            ; $F3 reserved
        dw      Seq_Op_Lfo               ; $F4 MEV_LFO (write $22 LFO, DAC $2A re-parked)
        dw      Seq_BadOpcode            ; $F5 reserved
        dw      Seq_BadOpcode            ; $F6 reserved
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
        ld      b, a                     ; save index for the post-increment (b is free; push bc above)
        ld      hl, SND_SEQ_TRACE        ; ring base (no longer page-aligned)
        add     a, l
        ld      l, a
        ld      a, h
        adc     a, 0
        ld      h, a                     ; hl = SND_SEQ_TRACE + index (carry-correct)
        ld      (hl), c                  ; trace[index] = trace byte
        ld      a, b
        inc     a
        and     SND_SEQ_TRACE_LEN-1      ; index = (index+1) & (LEN-1)
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
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz                       ; SFX owns this voice -> emit no chip write
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
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jp      nz, Fm_NoteOff
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z
        jp      Psg_NoteOff

Seq_HookSetVol:
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
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
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
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
