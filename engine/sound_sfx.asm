; ======================================================================
; engine/sound_sfx.asm — Phase 5a SFX engine: steal + per-frame interpreter
; ----------------------------------------------------------------------
; Assembled INLINE inside the z80_sound_driver.asm `phase 0` blob (after
; sound_sequencer.asm — whose ModUpdate / Sequencer_Channel this REUSES —
; and before sound_fm.asm / sound_psg.asm — whose writers it CALLS).
;
; MODEL (spec §5): a parallel SFX interpreter layered over the music sequencer.
; A fixed 7-slot SfxChannel array ($1D00) — FM3/4/5 + PSG1/2/3 + noise (the
; stealable set). Each SfxChannel's 39-byte prefix MIRRORS SeqChannel, so the
; SHARED interpreter (ModUpdate + Sequencer_Channel) walks it with ix = the
; SfxChannel exactly as it walks a music channel. Sfx_Frame runs AFTER
; Sequencer_Frame so SFX hardware writes land last and OWN the stolen voice.
;
; STEAL (Sfx_Steal): set SCF_SFX_OVERRIDE on the target MUSIC SeqChannel (its
; cursor keeps advancing — see the music-side gate in sound_sequencer.asm — but
; every chip-write site early-returns, so the song never desyncs yet goes
; silent on that physical voice), key-off the physical voice cleanly, load the
; SFX's OWN FM voice, then set SCF_ACTIVE on the SfxChannel so Sfx_Frame runs it.
;
; SFX DATA SOURCING (load-bearing): the SFX blobs are 68k ROM data (id->blob via
; SfxBlobWinTab below, built from the build-time blob labels). They are read
; through the Z80 $8000 banked window, like the FM6=FM stream song. The whole
; SFX set lives in ONE bank (asserted == the Moving Trucks bank), so when an
; FM6=FM song is playing the bank is ALREADY parked there and SfxDispatch reads
; the blob with no re-bank. SfxDispatch banks the SFX bank in and LEAVES it (the
; stream-path model) — the per-frame SFX cursor reads the blob from the window
; every frame. Cross-bank songs (e.g. the COPY path, where the bank is the DAC
; bank) are a Task 8+ concern (a 68k-resolved SFX param block, mirroring
; SND_MUSIC_PARAM) — design-for-C: the format + slot layout already accommodate
; it; this 5a core is wired for the in-bank case the hardware test exercises.
;
; PATCH RESOLUTION (no SND_SEQ_PATCHTAB clobber): an SfxChannel carries its OWN
; voice ptr in sx_patch_base. Sfx_Steal calls Fm_PatchLoad with hl = that ptr —
; Fm_PatchLoad takes hl directly (it does NOT call Fm_PatchPtr), so the SFX voice
; loads WITHOUT touching SND_SEQ_PATCHTAB. Music restore (Task 7) re-derives the
; music patch via Fm_PatchPtr (SND_SEQ_PATCHTAB unchanged).
;
; REGISTER DISCIPLINE (project-critical contracts):
;   * ix preservation: every Fm_*/Psg_* writer preserves ix. Sfx_Frame/Sfx_Steal
;     push/pop ix around any work that re-points ix at a MUSIC channel, so the
;     SFX-slot ix is intact for the loop's `add ix,de`.
;   * de=$4001 invariant: all YM writes go through the Fm_* writers (absolute
;     addressing + $2A re-park). Sfx_Frame NEVER does raw `ld (de),a`. It clobbers
;     de; both Sequencer_Frame call sites re-park de=$4001 after the tail-call into
;     Sfx_Frame (the tail-call returns to the same caller), so the invariant holds.
; ======================================================================

; --- build-time ROM-window helpers (a 68k ROM addr -> Z80 $8000-window view) ---
; The window ptr keeps the low 15 bits and sets bit15 ($8000). The bank id is the
; addr >> 15 (the low 15 bits drop out; our ROM is < $800000 so no high mask is
; needed — and a `$`-prefixed hex literal inside an AS `function` body, evaluated
; under cpu z80, trips the expression parser, so the mask/base are DECIMAL
; equates here: 32767 = $7FFF, 32768 = $8000).
SFX_WIN_MASK = 32767                                     ; $7FFF (low 15 bits)
SFX_WIN_BASE = 32768                                     ; $8000 (window bit15)
sfx_winptr  function addr, (((addr) & SFX_WIN_MASK) | SFX_WIN_BASE)
sfx_bankid  function addr, ((addr) >> 15)               ; banked-window bank id

; The bank all SFX blobs live in (taken from the first blob; the contiguous
; build layout — all sfx_NN.asm blobs included together in main.asm — guarantees
; the rest share it). SfxDispatch banks this in and LEAVES it set (stream model).
SFX_BLOB_BANK = sfx_bankid(Sfx_33)

; --- SfxDispatch multi-channel loop scratch (Task 8) -------------------------
; The per-channel placement loop calls Sfx_SelectVoice/Sfx_Steal, which clobber
; EVERY register (incl. ix/iy), so the blob base + chcount + per-channel cursor +
; the selected slot/route must survive in RAM across iterations, not registers.
; Anchored just above SND_SFX_DUCK_TARGET (the top of the Phase-5a RAM map in
; sound_constants.asm) — kept here so this task touches only one file; a local
; mailbox-overrun guard stands in for the SND_SFX_RAM_END assert in constants.
SND_SFX_DISP_BASE  = SND_SFX_DUCK_TARGET + 1            ; blob window base (word)
SND_SFX_DISP_PRIO  = SND_SFX_DISP_BASE + 2             ; incoming SFX priority
SND_SFX_DISP_COUNT = SND_SFX_DISP_PRIO + 1             ; remaining channels (count-down)
SND_SFX_DISP_IDX   = SND_SFX_DISP_COUNT + 1            ; current channel record index
SND_SFX_DISP_SLOT  = SND_SFX_DISP_IDX + 1              ; chosen SfxChannel slot (this chan)
SND_SFX_DISP_ROUTE = SND_SFX_DISP_SLOT + 1             ; physical route the slot owns
SND_SFX_DISP_END   = SND_SFX_DISP_ROUTE + 1
        if SND_SFX_DISP_END > SND_REQ_BASE
          fatal "SFX dispatch scratch (\{SND_SFX_DISP_END}) overruns the mailbox at \{SND_REQ_BASE}"
        endif

; --- Task 10 ducking invariant: rings must NEVER duck the music (spec §7) -------
; The duck arms only for SFX whose authored priority >= SFX_DUCK_THRESHOLD. Ring
; pickup (SFXPRI_RING) must fall strictly below the threshold so collecting rings
; can't pump the music. Build-assert it here where the duck logic lives.
        if SFXPRI_RING >= SFX_DUCK_THRESHOLD
          error "SFXPRI_RING (\{SFXPRI_RING}) must be < SFX_DUCK_THRESHOLD (\{SFX_DUCK_THRESHOLD}) — rings must not duck"
        endif

; ======================================================================
; Task 9: 3-deep priority-gated SFX queue
; ======================================================================
;
; OVERVIEW: the mailbox is latest-wins single-byte; consecutive frames could clobber
; a pending id before Z80 processes it. The queue fixes this: SfxDispatch (the fast
; mailbox handler, called from SndDrv_PollMailbox) ENQUEUES {id, priority} and
; returns immediately. Sfx_DrainQueue (called at the TOP of Sfx_Frame each frame)
; pops the HIGHEST-priority pending entry and runs the real voice-selection + steal
; via Sfx_BeginSound.
;
; QUEUE LAYOUT (3 entries × 2 bytes = 6 bytes, then head/tail/cnt):
;   SND_SFX_QUEUE + 0 = entry 0: [id_byte, priority_byte]
;   SND_SFX_QUEUE + 2 = entry 1: [id_byte, priority_byte]
;   SND_SFX_QUEUE + 4 = entry 2: [id_byte, priority_byte]
;   SND_SFX_QUEUE_CNT = count of valid entries (0..3)
;   SND_SFX_QUEUE_HEAD/TAIL: allocated (reserved for 5b if needed); unused by 5a.
; Entry n is VALID iff n < CNT.  Valid entries are packed into slots 0..CNT-1.
; Enqueue appends at slot CNT; drain pops the max-priority slot and compacts.
;
; OVERFLOW (queue full, CNT == 3): compare incoming priority against the lowest-
; priority queued entry; if incoming > lowest → overwrite that lowest slot's {id,
; priority}; else → drop the incoming. This keeps only the most-relevant pending SFX.
;
; ENTRY ADDRESSING (no multiply): entry[n].id   = (SND_SFX_QUEUE + n + n)
;                                  entry[n].prio = (SND_SFX_QUEUE + n + n + 1)
; n ranges 0..2, so n+n is 0..4 — all within a single `add hl,de` per stride.
;
; CONTINUOUS-EXTEND HOOK (5b seam, dormant in 5a): if the blob's SfxHeader has
; SHF_CONTINUOUS AND a slot is already running that same id, EXTEND it (reset its
; stream cursor / refresh its hold) rather than queuing another instance — prevents
; machine-gun re-triggers. All 5a SFX are one-shots (SHF_CONTINUOUS never set), so
; this path is unreachable and fully dormant.  5b adds an sx_id field to SfxChannel
; and a "same-id active" scan; this hook label marks the seam.
; ======================================================================

; ----------------------------------------------------------------------
; Sfx_QueueEntryPtr — compute hl = address of entry[n].id byte in the queue.
; entry[n] is at SND_SFX_QUEUE + n*2 = SND_SFX_QUEUE + n + n (no multiply).
; In: a = n (0..2). Out: hl = &queue_entry[n].id. Clobbers af, hl, de.
; Callers must not rely on de surviving this call.
; ----------------------------------------------------------------------
Sfx_QueueEntryPtr:
        ld      l, a
        ld      h, 0
        add     hl, hl                   ; hl = n*2 (no multiply: add hl,hl)
        ld      de, SND_SFX_QUEUE
        add     hl, de                   ; hl = SND_SFX_QUEUE + n*2
        ret

; ----------------------------------------------------------------------
; Sfx_DrainQueue — pop the highest-priority entry from the SFX queue and
; launch it via Sfx_BeginSound.  Called once per frame at the TOP of Sfx_Frame.
; At most one SFX is begun per frame (bounded latency; highest-priority waiter
; plays first).
; In: nothing.  Out: SND_SFX_QUEUE_CNT decremented by 1 if an entry was drained;
;   Sfx_BeginSound called with the popped id. Clobbers af,bc,de,hl,ix,iy.
;
; REGISTER NOTES:
;   Throughout the scan phase: b=djnz-counter, c=best-slot, d=best-priority.
;   The slot cursor is kept in e (= SND_SFX_QUEUE_CNT scratch) between iterations.
;   Sfx_QueueEntryPtr clobbers de — the slot cursor (e) must be pushed/popped around
;   each call (b=djnz/c=best-slot are also pushed together as bc).
; ----------------------------------------------------------------------
Sfx_DrainQueue:
        ld      a, (SND_SFX_QUEUE_CNT)
        or      a
        ret     z                        ; queue empty -> nothing to drain

        ; scan entries 0..CNT-1 for the highest-priority one.
        ; Register allocation: b=djnz-counter (CNT-1), c=best-slot, d=best-priority.
        ; e = scan cursor (clobbered by Sfx_QueueEntryPtr, so push de saves it across call)
        ld      a, (SND_SFX_QUEUE_CNT)
        ld      b, a                     ; b = CNT (djnz counter)
        ld      c, 0                     ; c = best slot index (entry 0 primed)
        ; prime best priority = entry[0].priority (direct load, no Sfx_QueueEntryPtr call)
        ld      hl, SND_SFX_QUEUE + 1    ; &entry[0].priority
        ld      d, (hl)                  ; d = best priority
        ; only one entry -> slot 0 wins (no scan needed).
        dec     b
        jr      z, .drain_pop
        ; scan entries 1..CNT-1.
        ; b = djnz counter (CNT-1, already decremented), c = best slot, d = best priority.
        ; e = scan cursor (1..CNT-1). Sfx_QueueEntryPtr clobbers de, so push/pop de
        ; around each call to save (best-priority d, cursor e); bc pushed/popped too.
        ld      e, 1                     ; e = scan cursor starting at slot 1
.drain_scan_loop:
        push    bc                       ; save (djnz-counter b, best-slot c)
        push    de                       ; save (best-priority d, cursor e) — de clobbered below
        ld      a, e                     ; a = slot cursor (from saved e)
        call    Sfx_QueueEntryPtr        ; hl = &entry[a].id; de clobbered
        inc     hl                       ; hl = &entry[a].priority
        ld      a, (hl)                  ; a = candidate priority
        pop     de                       ; restore (d=best-priority, e=cursor)
        pop     bc                       ; restore (b=djnz-counter, c=best-slot)
        ; compare candidate(a) vs best(d): if a > d -> new winner
        cp      d                        ; CARRY set if a < d; Z if equal
        jr      c, .drain_no_update      ; a < d -> no update
        jr      z, .drain_no_update      ; tie -> FIFO (earlier slot = lower index wins)
        ld      d, a                     ; new best priority
        ld      c, e                     ; new best slot
.drain_no_update:
        inc     e                        ; advance cursor
        djnz    .drain_scan_loop         ; b-- and loop until all CNT-1 extras scanned

.drain_pop:
        ; c = best slot, d = best priority (d used only for scan; no longer needed).
        ; Read the popped id from entry[c].id.
        ld      a, c
        call    Sfx_QueueEntryPtr        ; hl = &entry[c].id; de clobbered
        ld      a, (hl)                  ; a = the popped id
        push    af                       ; preserve the id across the compact

        ; --- COMPACT: shift entries c+1..CNT-1 down one slot. ---------------------
        ; Number of entries to shift = (CNT-1) - c.
        ; Use hl as source ptr (entry[c+1]), de as dest ptr (entry[c]).
        ; Since hl = &entry[c] right now (from QueueEntryPtr above), advance 2 bytes:
        ld      d, h
        ld      e, l                     ; de = &entry[c] (dest)
        inc     hl
        inc     hl                       ; hl = &entry[c+1] (source)
        ; shift-count = CNT - 1 - c, in entries (each 2 bytes).
        ld      a, (SND_SFX_QUEUE_CNT)
        dec     a                        ; a = CNT-1
        sub     c                        ; a = (CNT-1) - c = entries to shift
        ; if a == 0 (c was the last slot), no shifting needed.
        jr      z, .compact_done
        ; each entry is 2 bytes; copy a*2 bytes from hl to de.
        ld      b, a
        add     a, b                     ; a = b*2 (byte count) without SLA (use add a,a)
        ld      b, a                     ; b = byte count
.shift_loop:
        ld      a, (hl)
        ld      (de), a
        inc     hl
        inc     de
        djnz    .shift_loop
.compact_done:
        ; decrement CNT.
        ld      hl, SND_SFX_QUEUE_CNT
        dec     (hl)

        ; call Sfx_BeginSound with the popped id.
        pop     af                       ; a = the popped id (raw SFX id)
        jp      Sfx_BeginSound           ; tail-call (clobbers all)

; ----------------------------------------------------------------------
; Sfx_Frame — run all active SfxChannels once per frame, AFTER Sequencer_Frame.
; Mirrors Sequencer_Frame's .chan_loop: per ACTIVE slot, ModUpdate (render) then
; the tempo-gated Sequencer_Channel (advance the SFX cursor — the SHARED interp).
; On a slot's stream End, Sequencer_Channel's MEV_END handler clears SCF_ACTIVE
; (verified in sound_sequencer.asm Seq_Op_End) — detect that and hand the voice
; back via Sfx_Restore (a `ret` stub in 5a Task 6; Task 7 fills it).
; In: nothing. Clobbers af,bc,de,hl,ix (same as Sequencer_Frame). Preserves
; nothing the caller needs except the de re-park it does after this tail-call.
; ----------------------------------------------------------------------
Sfx_Frame:
        call    Sfx_DrainQueue           ; Task 9: pop highest-priority pending SFX
        call    Sfx_DuckRamp             ; Task 10: ramp the music duck level toward target
        ld      b, SFX_VOICE_COUNT       ; b = slot count (djnz bound)
        ld      ix, SND_SFX_CHANNELS     ; ix = first SfxChannel
.slot_loop:
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      z, .next_slot            ; inactive slot -> skip
        push    bc                       ; preserve the slot-loop counter (b)

        ; (1) modulation layer — render the SFX channel's state -> chip. ix kept.
        call    ModUpdate

        ; (2) tempo accumulator: -16/frame; borrow => an event-tick is due.
        ld      a, (ix+sc_tempo_accum)
        sub     16
        ld      (ix+sc_tempo_accum), a
        jr      nc, .slot_done           ; no borrow -> no event-tick this frame
        add     a, (ix+sc_tempo_base)
        ld      (ix+sc_tempo_accum), a
        call    Sequencer_Channel        ; advance the SFX cursor (shared interp)
        ; if the SFX stream ended, Seq_Op_End (MEV_END) cleared SCF_ACTIVE.
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      nz, .slot_done
        call    Sfx_Restore              ; SFX ended -> hand the voice back to music
.slot_done:
        pop     bc
.next_slot:
        ld      de, SfxChannel_len       ; size added directly (no multiply)
        add     ix, de
        djnz    .slot_loop
        ret

; ----------------------------------------------------------------------
; Sfx_DuckRamp — ramp the global music duck LEVEL toward the duck TARGET by
; SFX_DUCK_RAMP_STEP each frame (linear, clamped, no overshoot). Called once per
; frame at the TOP of Sfx_Frame. The duck is FOLDED INTO Fm_SetVolume/Psg_SetVolume
; (music-only, gated by ix < SND_SFX_BASE), so the music's own note volume events
; already pick up the current level. This routine only handles HELD notes: on a
; frame where the level CHANGED, it re-asserts the volume on every active, non-
; overridden, KEYED music channel so a held note ducks/un-ducks IMMEDIATELY instead
; of coasting at the old level until its next volume event.
;
; WRITE-ON-CHANGE: if level == target (steady state, incl. both 0), do nothing — no
; ramp step, no chip writes. No multiply.
; In: nothing. Clobbers af,bc,de,hl,ix,iy. (Re-points ix at music channels; the
; caller — Sfx_Frame — reloads ix=SND_SFX_CHANNELS right after this returns.)
; ----------------------------------------------------------------------
Sfx_DuckRamp:
        ld      a, (SND_SFX_DUCK_LEVEL)
        ld      b, a                     ; b = current level
        ld      a, (SND_SFX_DUCK_TARGET)
        cp      b
        ret     z                        ; already at target -> no change, no writes
        jr      c, .ramp_down            ; target < level -> ramp down (decay)

        ; --- ramp UP: level = min(level + STEP, target). a = target, b = level. ---
        ld      c, a                     ; c = target (clamp ceiling)
        ld      a, b
        add     a, SFX_DUCK_RAMP_STEP    ; level + step (step is small; no 8-bit wrap)
        cp      c                        ; overshoot target?
        jr      c, .store                ; level+step < target -> use it
        ld      a, c                     ; clamp to target (no overshoot)
        jr      .store

.ramp_down:
        ; --- ramp DOWN: level = max(level - STEP, target). a = target, b = level. --
        ld      c, a                     ; c = target (clamp floor)
        ld      a, b
        sub     SFX_DUCK_RAMP_STEP       ; level - step
        jr      c, .clamp_floor          ; underflow past 0 -> floor at target
        cp      c                        ; undershoot target?
        jr      nc, .store               ; level-step >= target -> use it
.clamp_floor:
        ld      a, c                     ; clamp to target (no undershoot)

.store:
        ld      (SND_SFX_DUCK_LEVEL), a  ; the level CHANGED this frame (== guarded above)

        ; --- re-assert held music notes at the new duck level ----------------------
        ; Walk the 11 music SeqChannels. For each ACTIVE, NON-overridden, KEYED FM/PSG
        ; channel, re-apply sc_volume through the duck-aware writer (which re-folds
        ; the current SND_SFX_DUCK_LEVEL for ix < SND_SFX_BASE — do NOT add the duck
        ; again here). Overridden channels are silent (SFX owns them) -> skip.
        ld      ix, SND_SEQ_CHANNELS
        ld      b, CHROUTE_COUNT         ; 11 music channels
.dr_loop:
        push    bc                       ; preserve the channel counter
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      z, .dr_next
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        jr      nz, .dr_next             ; SFX owns this voice -> no music write
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .dr_next              ; not sounding -> next note keys at the new level
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      z, .dr_psg
        ld      a, (ix+sc_volume)
        call    Fm_SetVolume             ; carrier-TL re-asserted WITH the duck (ix kept)
        jr      .dr_next
.dr_psg:
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        jr      z, .dr_next              ; DAC (or other) -> no PSG volume
        ld      a, (ix+sc_volume)
        call    Psg_SetVolume            ; attenuation re-asserted WITH the duck (ix kept)
.dr_next:
        pop     bc
        ld      de, SeqChannel_len
        add     ix, de
        djnz    .dr_loop
        ret

; ----------------------------------------------------------------------
; Sfx_MusicChanPtr — resolve a physical route (in `a`, CHROUTE_*) to the MUSIC
; SeqChannel that OWNS it. Music channels are stored in SONG ORDER (index 0..
; SND_SEQ_CHCOUNT-1) with ARBITRARY sc_route values — there is NO index==route
; relationship (e.g. Moving Trucks = FM1..FM6 = routes 0..5, zero PSG, so PSG1's
; route 6 has no music channel at all). Resolving by stride math therefore lands
; on a stale/zeroed non-channel; we MUST search by sc_route instead.
;
; Iterate the SND_SEQ_CHCOUNT active channels from SND_SEQ_CHANNELS (stride
; SeqChannel_len, NO multiply), comparing each channel's sc_route to the target.
; In:  a  = target route (CHROUTE_*).
; Out: CARRY CLEAR + iy = &SeqChannel owning that route, if found;
;      CARRY SET (iy indeterminate) if no music channel owns it (or CHCOUNT==0).
; Preserves ix, hl. Clobbers af, bc, de, iy.
; ----------------------------------------------------------------------
Sfx_MusicChanPtr:
        ld      c, a                     ; c = target route (preserved across the scan)
        ld      a, (SND_SEQ_CHCOUNT)
        or      a
        jr      z, .not_found            ; no channels -> not found (carry set below)
        ld      b, a                     ; b = channel count (djnz bound)
        ld      iy, SND_SEQ_CHANNELS     ; iy = first SeqChannel
        ld      de, SeqChannel_len
.scan:
        ld      a, (iy+sc_route)
        cp      c                        ; this channel's route == target?
        jr      z, .found                ; match -> carry clear (cp equal => carry clear)
        add     iy, de                   ; advance to next channel (no multiply)
        djnz    .scan
.not_found:
        scf                              ; CARRY SET -> no music owns this route
        ret
.found:
        or      a                        ; CARRY CLEAR -> iy = owning SeqChannel
        ret

; ----------------------------------------------------------------------
; Sfx_Steal — claim a physical voice for an SfxChannel (spec §5).
; In:  ix = the target SfxChannel (init'd by SfxDispatch except SCF_ACTIVE):
;        sc_route       = the physical voice to steal (CHROUTE_*)
;        sx_saved_route = the music route whose SeqChannel to override
;        sx_kind        = SFXEL_FM / SFXEL_PSG / SFXEL_NOISE
;        sx_patch_base  = the SFX's own FM voice ptr (FM only; window addr)
; Steps: (1) set SCF_SFX_OVERRIDE on the music SeqChannel for sx_saved_route;
;        (2) key-off that physical voice on the MUSIC channel (clean note stop);
;        (3) for FM, load the SFX's OWN voice via Fm_PatchLoad(hl=sx_patch_base)
;            — does NOT touch SND_SEQ_PATCHTAB; (4) set SCF_ACTIVE on the SfxChannel.
; Preserves ix (the caller's SfxChannel) across all the music-channel work.
; Clobbers af,bc,de,hl,iy.
; ----------------------------------------------------------------------
Sfx_Steal:
        ; (1) find the MUSIC SeqChannel (if any) that owns this physical route.
        ; sx_saved_route == this SfxChannel's own physical voice (sc_route). If NO
        ; music channel owns it (carry set — e.g. PSG1 over a PSG-silent song), there
        ; is nothing to override or key-off: skip straight to loading the SFX voice +
        ; arming the slot. The SFX's own note-on then drives the physical voice.
        ld      a, (ix+sx_saved_route)
        call    Sfx_MusicChanPtr         ; carry clear + iy = owning channel; carry set = none
        jr      c, .no_music_fm_check    ; no music on this voice -> skip override+key-off
        set     SCF_SFX_OVERRIDE_B, (iy+sc_flags)

        ; (2)+(3) key-off the physical voice + load the SFX voice. The Fm_*/Psg_*
        ; writers take ix = the channel; push the SFX-slot ix, point ix at the
        ; MUSIC channel for the key-off, then restore the SFX-slot ix.
        ld      a, (ix+sx_kind)
        cp      SFXEL_FM
        jr      z, .fm
        cp      SFXEL_PSG
        jr      z, .psg
        ; --- NOISE: key off the music noise voice ---
        ; sx_saved_note is NOT captured here: our SFX transcoder drops periodic-noise
        ; mode (smpsPSGform), so a noise SFX never writes PSG3's $C0 tone register
        ; and PSG3's tone latch needs no restore. Field reserved for 5b periodic-noise
        ; restore if periodic-noise SFX are added later.
        push    ix                       ; save SFX-slot ix
        push    iy
        pop     ix                       ; ix = music noise SeqChannel
        call    Psg_NoteOff              ; silence the music noise voice (preserves ix)
        pop     ix                       ; restore SFX-slot ix
        jr      .activate

.psg:
        push    ix
        push    iy
        pop     ix                       ; ix = music SeqChannel
        call    Psg_NoteOff              ; key off the music PSG tone (preserves ix)
        pop     ix
        jr      .activate

.fm:
        push    ix
        push    iy
        pop     ix                       ; ix = music SeqChannel
        call    Fm_NoteOff               ; key off the music FM voice (preserves ix)
        pop     ix
.no_music_fm_check:
        ; FM SFX always loads its OWN voice (whether or not music underlay it). For a
        ; voice with no music underneath (carry-set path) only the FM kind needs the
        ; patch upload; PSG/noise just arm (their note-on writes tone+volume directly).
        ld      a, (ix+sx_kind)
        cp      SFXEL_FM
        jr      nz, .activate
        ; load the SFX's OWN FM voice (hl = sx_patch_base) into the SFX channel's
        ; physical voice. Fm_PatchLoad reads ix=SfxChannel for the route, hl=ptr.
        ld      l, (ix+sx_patch_base)
        ld      h, (ix+sx_patch_base+1)  ; hl = SFX FmPatch window ptr
        call    Fm_PatchLoad             ; upload the SFX voice (preserves ix)

.activate:
        ; (4) the SfxChannel is now armed — Sfx_Frame will run it next frame.
        set     SCF_ACTIVE_B, (ix+sc_flags)
        ret

; ======================================================================
; SfxDispatch (Task 9) — the FAST mailbox handler: resolve the id, read the
; SfxHeader for priority + flags, check the continuous-extend seam (5b dormant),
; then ENQUEUE {id, priority} via Sfx_QueueEnqueue and return immediately.
; The actual voice-selection + steal runs later in Sfx_DrainQueue (per frame).
;
; SfxDispatch is called from SndDrv_PollMailbox after consuming SND_REQ_SFX;
; it must be fast (the mailbox handler is on the timing-critical Z80 interrupt path).
; In: a = the raw SFX id posted to SND_REQ_SFX.  Clobbers af,bc,de,hl,ix,iy.
; ----------------------------------------------------------------------
SfxDispatch:
        ; --- id range check (dense table indexed by id - SFX_ID_BASE) ---
        push    af                       ; save raw id (needed for enqueue after range/ptr work)
        sub     SFX_ID_BASE
        jr      c, .disp_ignore          ; id < base -> ignore
        cp      SFX_TABLE_LEN
        jr      nc, .disp_ignore         ; id > max -> ignore
        ; hl = &SfxBlobWinTab[index] (2-byte entries; index*2 via add)
        ld      l, a
        ld      h, 0
        add     hl, hl                   ; index*2
        ld      de, SfxBlobWinTab
        add     hl, de
        ld      e, (hl)
        inc     hl
        ld      d, (hl)                  ; de = blob window ptr (0 = unused id)
        ld      a, d
        or      e
        jr      z, .disp_ignore          ; unused id slot -> ignore

        ; --- bank the SFX blob bank in (build-time constant; in-bank no-op) --------
        push    de
        ld      a, SFX_BLOB_BANK
        call    SndDrv_SetBank
        pop     de                       ; de = blob window base

        ; --- read SfxHeader: priority + flags (two bytes, no clobber of id) --------
        push    de
        pop     iy                       ; iy = blob base for header reads
        ld      b, (iy+SFXH_PRIORITY)    ; b = incoming SFX priority
        ld      a, (iy+SFXH_FLAGS)

        ; --- CONTINUOUS-EXTEND HOOK (5b seam, fully dormant in 5a) -----------------
        ; If SHF_CONTINUOUS is set AND a slot is already running this same id, EXTEND
        ; it (reset cursor) instead of queuing another instance. All 5a SFX are one-
        ; shots (SHF_CONTINUOUS never set in any transcoded 5a blob), so this branch
        ; is unreachable. 5b: add an sx_id field to SfxChannel, scan here, and call
        ; Sfx_Extend(slot) — the seam is present to avoid a format change later.
        bit     SHF_CONTINUOUS_B, a
        jr      z, .disp_enqueue         ; one-shot (or no matching active slot) -> enqueue
        ; SHF_CONTINUOUS: check if this id is already running (requires sx_id — 5b).
        ; For 5a: no sx_id field exists, so we cannot find the running slot safely.
        ; Fall through to enqueue (may retrigger, but no 5a SFX hits this path).
        ; 5b: insert "scan SfxChannels for sx_id == raw_id; if found call Sfx_Extend; ret"

.disp_enqueue:
        ; --- enqueue {raw_id, priority} -------------------------------------------
        ; priority is in b; recover raw id from the stack.
        pop     af                       ; a = raw id (pushed at entry before range check)
        call    Sfx_QueueEnqueue         ; enqueue {a=id, b=priority}; registers clobbered
        ret

.disp_ignore:
        pop     af                       ; discard the pushed raw id
        ret

; ----------------------------------------------------------------------
; Sfx_QueueEnqueue — insert {id, priority} into the 3-slot packed queue.
; If count < SFX_QUEUE_DEPTH: append at slot[CNT], increment CNT.
; If count == SFX_QUEUE_DEPTH (full): find the lowest-priority queued entry;
;   if incoming priority > that lowest -> overwrite {id,prio} in that slot;
;   else -> drop the incoming.
; In:  a = raw SFX id (caller guarantees a != 0).
;      b = incoming priority.
; Out: nothing. Clobbers af, bc, de, hl. Preserves ix, iy.
;
; OVERFLOW IMPLEMENTATION NOTE: SFX_QUEUE_DEPTH == 3 and the 3 entries live at
; FIXED, KNOWN addresses (SND_SFX_QUEUE+0/1, +2/3, +4/5). We compare priorities
; directly at those addresses rather than via Sfx_QueueEntryPtr (which clobbers de
; and would destroy our tracking state). The lowest-priority slot index (0,1,2) and
; its priority are kept in e and d respectively throughout the overflow path.
; ----------------------------------------------------------------------
Sfx_QueueEnqueue:
        ld      c, a                     ; c = id (save across ptr operations)
        ld      a, (SND_SFX_QUEUE_CNT)
        cp      SFX_QUEUE_DEPTH
        jr      nc, .enq_overflow        ; full -> overflow handling

        ; --- append: write {id,priority} at slot[CNT], increment CNT --------------
        ; a = CNT (unchanged by cp). Sfx_QueueEntryPtr clobbers de, but we don't
        ; need de after this call — proceed directly.
        call    Sfx_QueueEntryPtr        ; hl = &entry[CNT].id
        ld      (hl), c                  ; entry[CNT].id = incoming id
        inc     hl
        ld      (hl), b                  ; entry[CNT].priority = incoming priority
        ld      hl, SND_SFX_QUEUE_CNT
        inc     (hl)
        ret

.enq_overflow:
        ; queue full. Find the slot with the LOWEST priority among the 3 fixed entries.
        ; Use direct addressing (no Sfx_QueueEntryPtr) to avoid clobbering de.
        ; Track: d = lowest priority found, e = index of that slot (0,1,2).
        ld      hl, SND_SFX_QUEUE + 1    ; &entry[0].priority (offset 1 = SND_SFX_QUEUE+1)
        ld      d, (hl)                  ; d = entry[0].priority
        ld      e, 0                     ; e = slot of current lowest (slot 0)
        ; compare entry[1].priority (at SND_SFX_QUEUE + 3):
        ld      hl, SND_SFX_QUEUE + 3    ; &entry[1].priority
        ld      a, (hl)
        cp      d                        ; a vs d: CARRY set if a < d
        jr      nc, .enq_try2            ; a >= d -> entry[1] not lower, keep slot 0
        ld      d, a                     ; entry[1] is lower
        ld      e, 1                     ; e = slot 1
.enq_try2:
        ; compare entry[2].priority (at SND_SFX_QUEUE + 5):
        ld      hl, SND_SFX_QUEUE + 5    ; &entry[2].priority
        ld      a, (hl)
        cp      d                        ; a vs d: CARRY set if a < d
        jr      nc, .enq_cmp             ; a >= d -> entry[2] not lower
        ld      d, a                     ; entry[2] is lower
        ld      e, 2                     ; e = slot 2
.enq_cmp:
        ; d = lowest queued priority, e = its slot index.
        ; Gate: incoming priority (b) must STRICTLY exceed lowest (d) to overwrite.
        ld      a, b                     ; a = incoming priority
        cp      d
        ret     c                        ; a < d -> DROP incoming (no improvement)
        ret     z                        ; a == d -> DROP (tie; keep the running one)
        ; incoming > lowest: overwrite entry[e] with {incoming-id, incoming-priority}.
        ; Compute address = SND_SFX_QUEUE + e*2 (direct: e is 0,1,2; e*2 via add a,a).
        ld      a, e
        call    Sfx_QueueEntryPtr        ; hl = &entry[e].id; de clobbered (ok — done)
        ld      (hl), c                  ; overwrite id
        inc     hl
        ld      (hl), b                  ; overwrite priority
        ret

; ----------------------------------------------------------------------
; Sfx_BeginSound — resolve a posted SFX id to its blob, then for EACH of the
; SFX's channels (chcount) call Sfx_SelectVoice (dynamic-among-eligible +
; priority steal, Task 8) and, on success, init the chosen SfxChannel slot
; from that channel's record + Sfx_Steal it. Multi-channel SFX (Dash = FM5+PSG3,
; Skid = PSG1+PSG2) steal their voices INDEPENDENTLY: each channel runs the full
; selection ladder, so one channel dropping doesn't block the rest.
; In: a = the raw SFX id (range-unchecked — we re-check here for safety, since
;   the queue may have been populated before a ROM change or by Sfx_QueueEnqueue).
; Called from Sfx_DrainQueue via tail-call (jp Sfx_BeginSound). Clobbers all.
;
; The blob lives in 68k ROM, read via the $8000 window. Bank in the SFX bank and
; LEAVE it (stream-path model). The per-channel cmd_ptr/voice_ptr are offsets from
; the blob base; add them to the blob's window base.
;
; Loop state lives in RAM (SND_SFX_DISP_*) rather than registers because each
; iteration calls Sfx_SelectVoice/Sfx_Steal, which clobber the full register set
; (incl. ix/iy). The blob base + chcount + per-channel cursor survive across calls
; in RAM; the chosen slot/route come back from Sfx_SelectVoice each iteration.
; ----------------------------------------------------------------------
Sfx_BeginSound:
        ; --- id range check (dense table indexed by id - SFX_ID_BASE) ---
        sub     SFX_ID_BASE
        ret     c                        ; id < base -> ignore
        cp      SFX_TABLE_LEN
        ret     nc                       ; id > max -> ignore
        ; hl = &SfxBlobWinTab[index] (2-byte window-ptr entries; index*2 via add)
        ld      l, a
        ld      h, 0
        add     hl, hl                   ; index*2
        ld      de, SfxBlobWinTab
        add     hl, de                   ; hl = &SfxBlobWinTab[index]
        ld      e, (hl)
        inc     hl
        ld      d, (hl)                  ; de = blob window ptr (0 = unused id)
        ld      a, d
        or      e
        ret     z                        ; unused id slot -> ignore

        ; --- bank the SFX blob's bank in (build-time constant; in-bank no-op) ---
        push    de                       ; save blob window base
        ld      a, SFX_BLOB_BANK
        call    SndDrv_SetBank           ; $6000 latch only (DMA-safe); leaves it set
        pop     de                       ; de = blob window base

        ; --- stash the blob base + header fields into the dispatch scratch RAM ----
        ld      (SND_SFX_DISP_BASE), de  ; blob window base (little-endian word)
        push    de
        pop     iy                       ; iy = blob base for the header reads
        ld      a, (iy+SFXH_PRIORITY)
        ld      (SND_SFX_DISP_PRIO), a   ; incoming SFX priority
        ld      a, (iy+SFXH_CHCOUNT)
        or      a
        ret     z                        ; chcount 0 -> nothing to do (defensive)
        ld      (SND_SFX_DISP_COUNT), a  ; remaining channels to place
        xor     a
        ld      (SND_SFX_DISP_IDX), a    ; current channel record index (0-based)

.chan_loop:
        ; --- point iy at the current channel record: base + SFXH_CHANNELS + idx*6 -
        ld      iy, (SND_SFX_DISP_BASE)
        ld      bc, SFXH_CHANNELS        ; bc = fixed-header size (record array start)
        add     iy, bc
        ld      a, (SND_SFX_DISP_IDX)
        or      a
        jr      z, .rec_ready            ; record 0 -> no stride
        ld      b, a                     ; b = record index (iteration count)
        ld      de, SFXHC_LEN            ; 6-byte records; advance via add-loop (no mul)
.rec_stride:
        add     iy, de
        djnz    .rec_stride
.rec_ready:

        ; --- run the selection ladder for this channel's PREFERRED route ----------
        ; In: c = preferred route; incoming priority is read from SND_SFX_DISP_PRIO
        ; inside Sfx_SelectVoice (no reg survives the ladder). Out: a=slot, d=route
        ; (CARRY clear) or CARRY set = dropped.
        ld      a, (iy+SFXHC_ROUTE)
        ld      c, a                     ; c = preferred physical route
        call    Sfx_SelectVoice          ; clobbers everything incl. iy; selects/steals victim
        jp      c, .chan_drop            ; jp (not jr): the init body exceeds jr range

        ; a = chosen slot, d = physical route to own. Stash both, then re-derive iy
        ; (Sfx_SelectVoice clobbered it) and init the slot from the channel record.
        ld      (SND_SFX_DISP_SLOT), a   ; chosen SfxChannel slot index
        ld      a, d
        ld      (SND_SFX_DISP_ROUTE), a  ; physical route the slot will own

        ; ix = &SfxChannel[chosen slot]
        ld      a, (SND_SFX_DISP_SLOT)
        call    Sfx_SlotPtr              ; ix = chosen SfxChannel

        ; re-point iy at the channel record (Sfx_SlotPtr left iy intact, but
        ; Sfx_SelectVoice clobbered it — recompute base + SFXH_CHANNELS + idx*6).
        ld      iy, (SND_SFX_DISP_BASE)
        ld      bc, SFXH_CHANNELS
        add     iy, bc
        ld      a, (SND_SFX_DISP_IDX)
        or      a
        jr      z, .rec2_ready
        ld      b, a
        ld      de, SFXHC_LEN
.rec2_stride:
        add     iy, de
        djnz    .rec2_stride
.rec2_ready:

        ; --- wipe the chosen slot, then populate it from the record ---------------
        ; (the slot may be a just-restored steal victim — wipe clears stale state.)
        push    ix                       ; save the slot ptr across the wipe
        pop     hl                       ; hl = &SfxChannel[slot] (wipe cursor)
        ld      bc, SfxChannel_len
.wipe:
        ld      (hl), 0
        inc     hl
        dec     bc
        ld      a, b
        or      c
        jr      nz, .wipe

        ; sc_route = the PHYSICAL route the slot owns (NOT necessarily the preferred
        ; one — substitution/steal may have steered it to a different eligible voice).
        ld      a, (SND_SFX_DISP_ROUTE)
        ld      (ix+sc_route), a
        ; sc_flags = class bits, minus SCF_ACTIVE (Sfx_Steal arms it last).
        call    Snd_RouteClassFlags      ; a = SCF_ACTIVE | class bit (FM/PSG/DAC)
        res     SCF_ACTIVE_B, a
        ld      (ix+sc_flags), a

        ; sc_stream_ptr = blob base + cmd offset (BE in the record)
        ld      a, (iy+SFXHC_CMD_HI)
        ld      h, a
        ld      a, (iy+SFXHC_CMD_LO)
        ld      l, a                     ; hl = cmd offset (from blob base)
        ld      de, (SND_SFX_DISP_BASE)  ; de = blob window base
        add     hl, de
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h

        ; sx_patch_base = blob base + voice offset (FM only; PSG/noise -> base+0)
        ld      a, (iy+SFXHC_VOICE_HI)
        ld      h, a
        ld      a, (iy+SFXHC_VOICE_LO)
        ld      l, a
        add     hl, de
        ld      (ix+sx_patch_base), l
        ld      (ix+sx_patch_base+1), h

        ; sx_kind = SFXEL_* derived from the OWNED route (FM3..5 -> FM, PSG1..3 ->
        ; PSG, PSGN -> NOISE). Substitution keeps the kind (same-kind only), so the
        ; record's authored kind and the owned route's kind always agree.
        ld      a, (ix+sc_route)
        call    Sfx_RouteKind
        ld      (ix+sx_kind), a

        ; bookkeeping: priority, saved music route (== the OWNED physical route),
        ; tick gating (one event per frame until the stream sets durations).
        ld      a, (SND_SFX_DISP_PRIO)
        ld      (ix+sx_priority), a
        ld      a, (ix+sc_route)
        ld      (ix+sx_saved_route), a
        ld      (ix+sc_dur_count), 1     ; fire the first event-tick promptly
        ld      (ix+sc_dur_default), 1
        ld      (ix+sc_pt_count), 1      ; plain-note path (no trill/arp)
        ld      (ix+sc_tempo_base), 16   ; one event-tick per frame (accum -16 +16)
        ld      (ix+sc_tempo_accum), 16

        call    Sfx_Steal                ; override the music voice + load the SFX voice

.chan_drop:
        ; advance to the next channel record; loop until chcount exhausted.
        ld      a, (SND_SFX_DISP_IDX)
        inc     a
        ld      (SND_SFX_DISP_IDX), a
        ld      hl, SND_SFX_DISP_COUNT
        dec     (hl)
        jp      nz, .chan_loop           ; jp (not jr): the loop body exceeds jr range

        ; --- Task 10: arm the music duck if this SFX is high-priority (spec §7) ----
        ; Done AFTER the channel loop so that any Sfx_Restore calls triggered by a
        ; steal inside the loop (which zero SND_SFX_DUCK_TARGET if no other duck-
        ; eligible SFX was active at that moment) cannot un-arm the arm we set here.
        ; SND_SFX_DISP_PRIO is written once before the loop and only read (never
        ; written) inside it, so it is still valid here.
        ;
        ; A duck-eligible SFX (priority >= SFX_DUCK_THRESHOLD: spindash/dash/death/
        ; ring-loss) raises the duck TARGET to SFX_DUCK_DEPTH; Sfx_DuckRamp ramps the
        ; applied LEVEL toward it. Rings ($20 < threshold) leave the target untouched
        ; (build-asserted below) so collecting rings never pumps the music. The
        ; target is cleared on restore once no duck-eligible SFX remains active.
        ld      a, (SND_SFX_DISP_PRIO)
        cp      SFX_DUCK_THRESHOLD
        jr      c, .no_duck_arm          ; below threshold -> do not duck
        ld      a, SFX_DUCK_DEPTH
        ld      (SND_SFX_DUCK_TARGET), a
.no_duck_arm:
        ret

; ----------------------------------------------------------------------
; Sfx_RouteKind — map a physical route (in `a`, CHROUTE_*) to its SFXEL_* kind.
; FM3..FM5 -> SFXEL_FM; PSG1..PSG3 -> SFXEL_PSG; PSGN -> SFXEL_NOISE; else NONE.
; Clobbers af. (No multiply; pure comparisons against the CHROUTE_* enum.)
; ----------------------------------------------------------------------
Sfx_RouteKind:
        cp      CHROUTE_PSGN
        jr      z, .noise
        cp      CHROUTE_PSG1             ; < PSG1 -> FM (FM3..FM5 in the stealable set)
        jr      c, .fm
        ld      a, SFXEL_PSG             ; PSG1..PSG3 (PSGN handled above)
        ret
.fm:
        ld      a, SFXEL_FM
        ret
.noise:
        ld      a, SFXEL_NOISE
        ret

; ----------------------------------------------------------------------
; Sfx_Restore — hand the physical voice back to the music CLEANLY (spec §5).
; On an SfxChannel's End (Sfx_Frame detects the cleared SCF_ACTIVE), un-mute the
; overridden music channel, re-derive + re-upload its FM voice (NO register
; snapshots — everything is recomputed from the music channel's surviving
; sc_patch/sc_volume/sc_note, which the steal never overwrote), restore the
; PSG3<->noise coupled latch if a noise voice was borrowed, and FORCE a re-key of
; the held music note ONLY if it was sounding when stolen (SCF_KEYED set) — so the
; music resumes instantly with no silence gap rather than coasting mute until the
; next note event. If the channel was between notes, just clearing the override is
; enough (the next note keys normally).
;
; In:  ix = the ended SfxChannel:
;        sx_saved_route = the music route to un-mute (CHROUTE_*)
;        sx_kind        = SFXEL_FM / SFXEL_PSG / SFXEL_NOISE
;        sx_saved_note  = unused in v1 (reserved for 5b periodic-noise restore)
; Out: SCF_SFX_OVERRIDE cleared on the music channel; its voice re-asserted;
;      held note re-keyed iff it was keyed; the SfxChannel deactivated + priority 0.
; Preserves ix (push/pop) so Sfx_Frame's `add ix,de` still advances. The Fm_*/Psg_*
; writers preserve ix internally; we re-point ix at MUSIC channels only inside the
; push/pop. SND_SEQ_PATCHTAB is read-only (Fm_PatchPtr) — never written.
; Clobbers af,bc,de,hl,iy.
; ----------------------------------------------------------------------
Sfx_Restore:
        push    ix                       ; save the SFX-slot ix (caller's invariant)

        ; (1) find the music SeqChannel (if any) that owns this physical route.
        ; sx_saved_route == this SfxChannel's own physical voice (sc_route). If NO
        ; music channel owns it (carry set — e.g. PSG1 over a PSG-silent song), there
        ; is nothing to un-mute or restore: silence the SFX's OWN physical voice so its
        ; last note doesn't drone forever, then deactivate. (ix is still the SFX slot,
        ; whose sc_route IS the physical voice and whose SCF_IS_* are set, so the
        ; Fm_*/Psg_* writers target the right voice with no ix re-point.)
        ld      a, (ix+sx_saved_route)
        call    Sfx_MusicChanPtr         ; carry clear + iy = owning channel; carry set = none
        jr      c, .no_music             ; no music on this voice -> silence the SFX's own voice

        ; (2) un-mute: clear the override so its chip-write sites fire again.
        res     SCF_SFX_OVERRIDE_B, (iy+sc_flags)

        ; (3) dispatch by the owned voice kind (read from the SFX slot via ix).
        ld      a, (ix+sx_kind)
        cp      SFXEL_FM
        jr      z, .fm
        cp      SFXEL_PSG
        jr      z, .psg
        ; --- NOISE: re-key the music noise channel iff it was keyed when stolen ---
        ; PSG3 tone re-latch is intentionally omitted: our SFX transcoder drops
        ; periodic-noise mode (smpsPSGform), so a noise SFX never writes PSG3's $C0
        ; tone register — PSG3's tone latch is never disturbed and needs no restore.
        ; If 5b adds periodic-noise SFX, re-add a restore that re-latches only PSG3's
        ; tone DIVISOR (not volume, which belongs to music) and only when PSG3
        ; SCF_KEYED is set.
        ; iy already = the owning (noise) music channel from the single search above.
        push    ix
        push    iy
        pop     ix                       ; ix = music noise channel
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .noise_silence        ; music not keyed -> silence the stolen noise
        ld      a, (ix+sc_note)          ; the held noise note (mode/rate)
        call    Psg_Noise                ; re-emit noise control + volume (preserves ix)
        jr      .noise_done
.noise_silence:
        ; No music noise to restore: the SFX left the noise volume latched audible.
        ; Silence the noise channel (Psg_NoteOff's noise path writes $FF) so a noise
        ; SFX over a noise-silent song doesn't hiss forever.
        call    Psg_NoteOff              ; noise route -> $FF (max attenuation)
.noise_done:
        pop     ix                       ; ix = SFX slot
        jr      .deactivate

.psg:
        ; --- PSG TONE: if the music note was sounding, re-key it (re-applies tone+
        ; volume); if NOT, SILENCE the stolen physical voice. The SFX left its own
        ; last tone + volume LATCHED on the chip; if no music underlies this PSG
        ; channel (e.g. Moving Trucks uses 0 PSG channels, so PSG1 is never keyed) the
        ; re-key branch would do NOTHING and the SFX's last PSG tone would DRONE
        ; FOREVER. Key the channel off so it goes silent when there's no music to
        ; restore. (Jump = id $62 = PSG1 over a PSG-silent song is exactly this case.)
        push    ix
        push    iy
        pop     ix                       ; ix = music PSG tone channel
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .psg_silence          ; music not keyed -> silence the stolen voice
        ld      a, (ix+sc_note)
        call    Psg_NoteOn               ; re-key the held tone (preserves ix)
        jr      .psg_done
.psg_silence:
        call    Psg_NoteOff              ; no music here -> silence the PSG channel
.psg_done:
        pop     ix                       ; ix = SFX slot
        jr      .deactivate

.fm:
        ; --- FM: re-upload the music voice (the exact Seq_HookSetPatch pair), then
        ; re-key the held note iff it was sounding when stolen. ix = MUSIC channel
        ; for all of this so Fm_PatchPtr/Fm_SetVolume read the MUSIC sc_patch/sc_volume.
        push    ix
        push    iy
        pop     ix                       ; ix = music FM channel
        call    Fm_PatchPtr              ; hl = music FmPatch ptr (SND_SEQ_PATCHTAB, read-only)
        call    Fm_PatchLoad             ; re-upload the music voice (re-asserts op-bias)
        ld      a, (ix+sc_volume)        ; re-apply the music channel's loudness
        call    Fm_SetVolume             ; carrier TLs (+ op-bias) restored
        ; force re-key ONLY if a note was sounding when the voice was stolen.
        ; If the music was NOT keyed, the SFX may have left the FM voice keyed-ON with
        ; its own note; re-uploading the patch above does NOT key it off, so the stolen
        ; FM voice would sustain forever. Key it OFF (the music's next note keys it
        ; normally) — symmetric with the PSG/noise silence-when-no-music fix.
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .fm_silence           ; between notes -> silence the stolen FM voice
    if SND_REKEY_OFF_THEN_ON
        call    Fm_NoteOff               ; clean 0->1 edge: key OFF first (mirrors ModUpdate)
    endif
        ld      a, (ix+sc_note)          ; the held note index
        call    Fm_NoteFromTable         ; re-key from the per-song fnum table (preserves ix)
        jr      .fm_done
.fm_silence:
        call    Fm_NoteOff               ; no music note -> key the stolen FM voice off
.fm_done:
        pop     ix                       ; ix = SFX slot
        jr      .deactivate

.no_music:
        ; No music channel owns this physical voice (carry set from the search). The
        ; SFX left its own last note LATCHED on the physical voice; silence it so it
        ; doesn't drone forever. ix is STILL the SFX slot (never re-pointed on this
        ; path) — its sc_route IS the physical voice and SCF_IS_* are set, so the
        ; Fm_*/Psg_* writers target the correct voice directly. Do NOT touch any
        ; music channel. No extra push/pop: the entry `push ix` is balanced by
        ; .deactivate's `pop ix`.
        ld      a, (ix+sx_kind)
        cp      SFXEL_FM
        jr      nz, .no_music_psg
        call    Fm_NoteOff               ; FM SFX voice -> key off (preserves ix)
        jr      .deactivate
.no_music_psg:
        ; PSG tone OR noise: Psg_NoteOff reads ix's sc_route and silences the right
        ; voice (tone -> $9x|$0F attenuation, noise -> $FF).
        call    Psg_NoteOff              ; PSG/noise SFX voice -> silence (preserves ix)

.deactivate:
        ; (4) deactivate the SfxChannel (End already cleared SCF_ACTIVE — defensive)
        ; and drop its priority so the next SFX of any priority can claim the slot.
        res     SCF_ACTIVE_B, (ix+sc_flags)
        ld      (ix+sx_priority), 0

        ; --- Task 10: release the music duck iff no duck-eligible SFX remains -------
        ; This slot's sx_priority is now 0 (cleared above), so it won't self-count.
        ; Scan the 7 slots for any ACTIVE one with sx_priority >= SFX_DUCK_THRESHOLD;
        ; if NONE, drop the duck TARGET to 0 so Sfx_DuckRamp ramps the music back up.
        ; (Walk via iy so the caller's SFX-slot ix on the stack is untouched.)
        call    Sfx_AnyDuckActive        ; CARRY set => a duck-SFX still runs
        jr      c, .duck_keep
        xor     a
        ld      (SND_SFX_DUCK_TARGET), a ; no duck-eligible SFX left -> ramp back
.duck_keep:
        pop     ix                       ; restore the caller's SFX-slot ix
        ret

; ----------------------------------------------------------------------
; Sfx_AnyDuckActive — scan the 7 SfxChannel slots for any ACTIVE slot whose
; sx_priority >= SFX_DUCK_THRESHOLD (a duck-eligible SFX still running).
; Out: CARRY SET if at least one such slot exists, CARRY CLEAR otherwise.
; Clobbers af, bc, de, iy. Preserves ix, hl. (Walks via iy so an SFX-slot ix on
; the caller's stack/registers is undisturbed.)
; ----------------------------------------------------------------------
Sfx_AnyDuckActive:
        ld      iy, SND_SFX_CHANNELS
        ld      b, SFX_VOICE_COUNT
        ld      de, SfxChannel_len
.scan:
        bit     SCF_ACTIVE_B, (iy+sc_flags)
        jr      z, .scan_next            ; inactive slot -> skip
        ld      a, (iy+sx_priority)
        cp      SFX_DUCK_THRESHOLD
        jr      nc, .found               ; sx_priority >= threshold -> duck still on
.scan_next:
        add     iy, de
        djnz    .scan
        or      a                        ; CARRY CLEAR -> no duck-eligible SFX active
        ret
.found:
        scf                              ; CARRY SET -> a duck-eligible SFX is active
        ret

; ======================================================================
; Phase 5a SFX engine — confirmed edge-case guarantees (Task 12 sweep).
; Each of these is verified in the code above; this block is the audit trail.
;
; (a) PRIORITY CLEARED ON SFX END. Sfx_Restore (.deactivate) writes sx_priority=0
;     on every ended slot, so the next SFX of ANY priority can claim it — a
;     finished high-priority SFX never permanently blocks the slot (spec §11).
;     Sfx_StopAll also zeroes sx_priority on all 7 slots.
; (b) NOISE/PSG3 COUPLING NOT RESTORED — BY DESIGN. The transcoder DROPS periodic-
;     noise mode (smpsPSGform, Task 7 fix), so a noise SFX never writes PSG3's $C0
;     tone register; PSG3's tone latch is never disturbed and needs no restore.
;     Sfx_Restore's NOISE path therefore re-keys only the music noise channel (when
;     it was keyed) and deliberately omits any PSG3 tone re-latch (see the comment
;     at .fm/.psg/noise dispatch). sx_saved_note is reserved-but-unread for the 5b
;     periodic-noise upgrade.
; (c) FM6<->DAC MUTUAL EXCLUSION IS MOOT. FM6 is SFXEL_NONE in SfxEligTable, so no
;     SFX ever steals FM6 — there is no path where an SFX and the DAC contend for
;     it. (Opening FM6 to SFX for DAC-off songs is a one-byte table edit, 5b.)
; (d) Sfx_Frame RUNS EVEN WITH NO MUSIC. Sequencer_Frame's two "no song / no
;     channels" early guards branch to .run_sfx (jp Sfx_Frame), so SFX still own
;     the chip and drain the queue when the sequencer is idle (Task 6 Step 4).
; ======================================================================

; ----------------------------------------------------------------------
; Sfx_StopAll — clear all overrides + kill SfxChannels + DRAIN the queue + reset
; ducking (duck = 0, target = 0). Task 9 adds the queue drain here so a StopMusic
; mid-SFX leaves no stale queue entries that would fire on the next song's first
; frame.  Used by StopMusic (.music_stop) AND Snd_LoadSong (PlayMusic-mid-SFX
; reconciliation, Task 12) so the next song starts with no stale overrides or
; in-flight SFX. Clobbers af,bc,de,hl,ix.
; ----------------------------------------------------------------------
Sfx_StopAll:
        ; clear SCF_SFX_OVERRIDE on every music SeqChannel.
        ld      ix, SND_SEQ_CHANNELS
        ld      b, CHROUTE_COUNT
        ld      de, SeqChannel_len
.clr_music:
        res     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        add     ix, de
        djnz    .clr_music
        ; deactivate + clear priority on every SfxChannel.
        ld      ix, SND_SFX_CHANNELS
        ld      b, SFX_VOICE_COUNT
        ld      de, SfxChannel_len
.clr_sfx:
        res     SCF_ACTIVE_B, (ix+sc_flags)
        ld      (ix+sx_priority), 0
        add     ix, de
        djnz    .clr_sfx
        ; Task 9: drain the SFX queue (CNT=0; HEAD/TAIL left as-is — they're unused).
        xor     a
        ld      (SND_SFX_QUEUE_CNT), a
        ; Task 10: reset duck level + target (no duck after StopAll).
        ld      (SND_SFX_DUCK_LEVEL), a
        ld      (SND_SFX_DUCK_TARGET), a
        ret

; ======================================================================
; SfxEligTable — per-physical-route eligibility (CHROUTE_* -> SFXEL_*), the
; build-time data that drives runtime voice substitution (spec §4). FM1/FM2/FM6/
; DAC are SFXEL_NONE (lead/bass/DAC never stolen); FM3/4/5 = SFXEL_FM; PSG1/2/3 =
; SFXEL_PSG; PSGN = SFXEL_NOISE. The transcoder already rejects reserved-route
; SFX at build time; this table is what Sfx_SelectVoice consults at RUNTIME to
; find a same-kind free voice (FM<->FM, PSG<->PSG dynamic substitution). Opening
; FM6 to SFX later for DAC-off songs is a one-byte edit here (design-for-C).
; ======================================================================
SfxEligTable:
        db      SFXEL_NONE   ; CHROUTE_FM1  (0) — lead, never stolen
        db      SFXEL_NONE   ; CHROUTE_FM2  (1) — bass, never stolen
        db      SFXEL_FM     ; CHROUTE_FM3  (2)
        db      SFXEL_FM     ; CHROUTE_FM4  (3)
        db      SFXEL_FM     ; CHROUTE_FM5  (4)
        db      SFXEL_NONE   ; CHROUTE_FM6  (5) — reserved v1 (DAC / DAC-off FM)
        db      SFXEL_PSG    ; CHROUTE_PSG1 (6)
        db      SFXEL_PSG    ; CHROUTE_PSG2 (7)
        db      SFXEL_PSG    ; CHROUTE_PSG3 (8)
        db      SFXEL_NOISE  ; CHROUTE_PSGN (9)
        db      SFXEL_NONE   ; CHROUTE_DAC  (10) — DAC trigger channel, never stolen
SfxEligTable_End:
        if (SfxEligTable_End - SfxEligTable) <> CHROUTE_COUNT
          error "SfxEligTable length (\{SfxEligTable_End - SfxEligTable}) must equal CHROUTE_COUNT (\{CHROUTE_COUNT})"
        endif

; ======================================================================
; SfxRouteSlot — per-physical-route SfxChannel SLOT index (CHROUTE_* -> 0..6, or
; SFX_SLOT_NONE for non-stealable routes). The 7 SfxChannel slots map 1:1 onto
; the 7 stealable physical voices (FM3,FM4,FM5,PSG1,PSG2,PSG3,PSGN), so a slot
; PERMANENTLY owns its physical voice — "is this physical voice free" reduces to
; "is SfxChannel[SfxRouteSlot[route]] SCF_ACTIVE clear", and a slot's sc_route is
; always its own physical route. This makes Sfx_SelectVoice tiers (a) "preferred
; route busy?" and (b) "any free same-kind voice?" direct slot lookups (no
; multiply). Non-stealable routes ($FF) are never passed here (the transcoder
; rejects them; the eligibility table also gates them out).
;
;   slot 0 = FM3 (route 2)   slot 3 = PSG1 (route 6)
;   slot 1 = FM4 (route 3)   slot 4 = PSG2 (route 7)
;   slot 2 = FM5 (route 4)   slot 5 = PSG3 (route 8)
;                            slot 6 = PSGN (route 9)
; ======================================================================
SFX_SLOT_NONE = 255          ; $FF — route not mapped to any SfxChannel slot
                             ; (decimal: a $-hex literal under `cpu z80` trips the
                             ;  AS expression parser — same quirk as SFX_WIN_* above)
SfxRouteSlot:
        db      SFX_SLOT_NONE ; CHROUTE_FM1  (0)
        db      SFX_SLOT_NONE ; CHROUTE_FM2  (1)
        db      0             ; CHROUTE_FM3  (2) -> slot 0
        db      1             ; CHROUTE_FM4  (3) -> slot 1
        db      2             ; CHROUTE_FM5  (4) -> slot 2
        db      SFX_SLOT_NONE ; CHROUTE_FM6  (5)
        db      3             ; CHROUTE_PSG1 (6) -> slot 3
        db      4             ; CHROUTE_PSG2 (7) -> slot 4
        db      5             ; CHROUTE_PSG3 (8) -> slot 5
        db      6             ; CHROUTE_PSGN (9) -> slot 6
        db      SFX_SLOT_NONE ; CHROUTE_DAC  (10)
SfxRouteSlot_End:
        if (SfxRouteSlot_End - SfxRouteSlot) <> CHROUTE_COUNT
          error "SfxRouteSlot length (\{SfxRouteSlot_End - SfxRouteSlot}) must equal CHROUTE_COUNT (\{CHROUTE_COUNT})"
        endif

; ======================================================================
; SfxSlotRoute — inverse of SfxRouteSlot: SfxChannel slot index (0..6) -> its
; permanently-owned physical route (CHROUTE_*). Used by Sfx_SelectVoice's
; same-kind scan + priority-steal to recover the physical route a chosen slot
; owns (so the incoming SFX is steered onto a free voice it didn't author).
; ======================================================================
SfxSlotRoute:
        db      CHROUTE_FM3   ; slot 0
        db      CHROUTE_FM4   ; slot 1
        db      CHROUTE_FM5   ; slot 2
        db      CHROUTE_PSG1  ; slot 3
        db      CHROUTE_PSG2  ; slot 4
        db      CHROUTE_PSG3  ; slot 5
        db      CHROUTE_PSGN  ; slot 6
SfxSlotRoute_End:
        if (SfxSlotRoute_End - SfxSlotRoute) <> SFX_VOICE_COUNT
          error "SfxSlotRoute length (\{SfxSlotRoute_End - SfxSlotRoute}) must equal SFX_VOICE_COUNT (\{SFX_VOICE_COUNT})"
        endif

; ======================================================================
; Sfx_SlotPtr — resolve an SfxChannel slot index (in `a`, 0..6) to its RAM ptr
; in ix: SND_SFX_CHANNELS + slot*SfxChannel_len, via an add-loop (NO multiply).
; In: a = slot index. Out: ix = &SfxChannel[slot]. Clobbers af, de, ix.
; PRESERVES bc, hl, iy — Sfx_SelectVoice holds the incoming kind in b and the
; preferred route in c across these calls, so bc must survive (the djnz counter
; is push/pop'd around the loop).
; ======================================================================
Sfx_SlotPtr:
        ld      ix, SND_SFX_CHANNELS
        or      a
        ret     z                        ; slot 0 -> base, no stride
        push    bc                       ; preserve bc (caller's kind/route live here)
        ld      b, a                     ; b = slot index (iteration count)
        ld      de, SfxChannel_len
.add_loop:
        add     ix, de
        djnz    .add_loop
        pop     bc
        ret

; ======================================================================
; Sfx_SelectVoice — pick the SfxChannel slot + physical route for an incoming SFX
; channel (spec §4 dynamic-among-eligible + §6 priority-gated steal).
;
; In:  c = preferred physical route (CHROUTE_*, the SFX's authored target)
;      SND_SFX_DISP_PRIO = incoming SFX priority (SFXPRI_*; higher wins). NOTE the
;        priority is read from this dispatch scratch at the steal gate, NOT from a
;        register: Sfx_SlotPtr clobbers de on every tier, so no reg survives the
;        full ladder. The single caller (SfxDispatch) sets it before calling.
; Out: CARRY CLEAR  -> a = chosen SfxChannel slot index (0..6)
;                      d = physical route the chosen slot owns (CHROUTE_*)
;                      (the slot is NOT yet inited/stolen — SfxDispatch does that;
;                       if the slot was a steal victim it has ALREADY been
;                       Sfx_Restore'd here, so SfxDispatch may re-init freely)
;      CARRY SET    -> dropped (no eligible voice, incoming priority too low)
; Clobbers af,bc,de,hl,ix,iy. (The caller saves/restores anything it still needs.)
;
; The three-tier ladder (no multiply; slot ptrs via Sfx_SlotPtr add-loop):
;   (a) PREFERRED: SfxRouteSlot[c] is the slot that owns route c. If it is free
;       (SCF_ACTIVE clear) -> use it on route c.
;   (b) SUBSTITUTE: else scan all 7 slots for a FREE one whose route has the SAME
;       kind as c (SfxEligTable[route]==SfxEligTable[c]) -> use the first such slot
;       on ITS owned route (dynamic substitution; more SFX sound at once).
;   (c) STEAL/DROP: else all same-kind slots are busy. Among the same-kind slots,
;       find the one with the LOWEST sx_priority; if incoming priority (read from
;       SND_SFX_DISP_PRIO) >= that lowest -> Sfx_Restore that victim (hands its
;       music voice back) and reuse the slot; else carry-set DROP. A lower-priority
;       SFX can never cut off a higher one.
; ======================================================================
Sfx_SelectVoice:
        ; --- the incoming channel's KIND (SfxEligTable[c]) into b (held all tiers).
        ld      hl, SfxEligTable
        ld      a, c
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a                     ; hl = &SfxEligTable[c]
        ld      a, (hl)
        ld      b, a                     ; b = incoming kind (SFXEL_*)

        ; --- TIER (a): preferred route's own slot, if free. ----------------------
        ld      hl, SfxRouteSlot
        ld      a, c
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a                     ; hl = &SfxRouteSlot[c]
        ld      a, (hl)                  ; a = preferred slot (0..6; $FF if unmapped)
        cp      SFX_SLOT_NONE
        jr      z, .substitute           ; defensive: unmapped route -> skip to scan
        push    af                       ; save preferred slot index
        call    Sfx_SlotPtr              ; ix = &SfxChannel[preferred slot]
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      nz, .pref_busy           ; preferred voice busy -> try substitution
        pop     af                       ; a = preferred slot (free) — use it
        ld      d, c                     ; d = preferred physical route
        or      a                        ; CARRY CLEAR -> success
        ret
.pref_busy:
        pop     af                       ; discard preferred slot index

.substitute:
        ; --- TIER (b): first FREE slot of the SAME kind (b) on its OWNED route. ---
        ; Scan slots 0..6: kind = SfxEligTable[SfxSlotRoute[slot]] == b AND free.
        ld      c, 0                     ; c = slot index cursor (0..6)
.sub_loop:
        ld      a, c
        ld      hl, SfxSlotRoute
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a
        ld      a, (hl)                  ; a = route owned by slot c
        ld      hl, SfxEligTable
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a
        ld      a, (hl)                  ; a = SfxEligTable[route] = slot's kind
        cp      b
        jr      nz, .sub_next            ; different kind -> skip
        ; same kind: is this slot free?
        ld      a, c
        call    Sfx_SlotPtr              ; ix = &SfxChannel[c]
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      nz, .sub_next            ; busy -> skip
        ; free same-kind slot found -> use it on its owned route.
        ld      a, c
        ld      hl, SfxSlotRoute
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a
        ld      d, (hl)                  ; d = the slot's owned physical route
        ld      a, c                     ; a = chosen slot
        or      a                        ; CARRY CLEAR -> success
        ret
.sub_next:
        inc     c
        ld      a, c
        cp      SFX_VOICE_COUNT
        jr      c, .sub_loop

        ; --- TIER (c): all same-kind slots busy -> find lowest-priority occupant.
        ; b still = incoming kind. Scan same-kind slots; track the slot with the
        ; minimum sx_priority. l = best slot (or $FF none), h = best priority.
        ld      l, SFX_SLOT_NONE         ; l = lowest-priority same-kind slot (none yet)
        ld      h, 255                   ; $FF — priority sentinel above any real prio
        ld      c, 0                     ; c = slot cursor
.steal_loop:
        ld      a, c
        push    hl                       ; preserve (best slot,best prio) across the lookup
        ld      hl, SfxSlotRoute
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a
        ld      a, (hl)                  ; a = route owned by slot c
        ld      hl, SfxEligTable
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a
        ld      a, (hl)                  ; a = slot's kind
        pop     hl                       ; restore (best slot,best prio)
        cp      b
        jr      nz, .steal_next          ; different kind -> ignore
        ; same kind — read its current priority and keep the minimum.
        push    hl
        ld      a, c
        call    Sfx_SlotPtr              ; ix = &SfxChannel[c]
        ld      a, (ix+sx_priority)      ; a = occupant priority
        pop     hl
        cp      h
        jr      nc, .steal_next          ; >= current best -> not lower, keep best
        ld      h, a                     ; new lowest priority
        ld      l, c                     ; new lowest-priority slot
.steal_next:
        inc     c
        ld      a, c
        cp      SFX_VOICE_COUNT
        jr      c, .steal_loop

        ; l = lowest-priority same-kind slot, h = its priority. (l == $FF only if
        ; NO same-kind slot exists at all — impossible once tier (a)/(b) found the
        ; route mapped, but guard defensively.)
        ld      a, l
        cp      SFX_SLOT_NONE
        jr      z, .drop
        ; priority gate: incoming >= lowest occupant(h) -> steal; else drop. Read
        ; the incoming priority from the dispatch scratch (the `e` arg is long gone:
        ; Sfx_SlotPtr clobbers de on every tier's slot-ptr resolve).
        ld      a, (SND_SFX_DISP_PRIO)   ; a = incoming priority
        cp      h                        ; CARRY set if incoming < h (lower) -> drop
        jr      c, .drop
        ; --- STEAL: hand the victim's music voice back BEFORE re-init (order!) ----
        ld      a, l                     ; a = victim slot
        push    af                       ; save victim slot index
        call    Sfx_SlotPtr              ; ix = &SfxChannel[victim]
        call    Sfx_Restore              ; restore the victim's music voice (preserves ix)
        ; Sfx_Restore cleared SCF_ACTIVE + sx_priority; the slot is now reusable.
        pop     af                       ; a = victim slot
        ; recover the slot's owned physical route for the caller.
        push    af
        ld      hl, SfxSlotRoute
        add     a, l
        ld      l, a
        ld      a, 0
        adc     a, h
        ld      h, a
        ld      d, (hl)                  ; d = the victim slot's owned physical route
        pop     af                       ; a = victim slot (chosen)
        or      a                        ; CARRY CLEAR -> success
        ret
.drop:
        scf                              ; CARRY SET -> dropped (no voice available)
        ret

; ======================================================================
; SfxBlobWinTab — id -> blob $8000-window ptr (dense, indexed by id-SFX_ID_BASE).
; Entries are build-time constants from the 68k blob labels (sfx_winptr()). An
; unused id is 0 (SfxDispatch ignores it). All blobs share ONE bank, asserted ==
; the Moving Trucks bank below (SfxDispatch banks it in and leaves it set).
; (This Z80-side table avoids dereferencing the 68k SfxTable, which the Z80 can't
;  read without per-entry banking. Task 11's 68k Sound_PlaySFX will pre-resolve a
;  param block; this 5a core resolves in-bank at build time — design-for-C.)
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
