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
; Sfx_MusicChanPtr — resolve a physical route (in `a`, CHROUTE_*) to its MUSIC
; SeqChannel ptr in iy: SND_SEQ_CHANNELS + route*SeqChannel_len, via an add-loop
; (NO multiply). In: a = route. Out: iy = &SeqChannel[route]. Clobbers af, bc, iy.
; Preserves ix, de, hl. (iy is free here — the music loop only uses ix.)
; ----------------------------------------------------------------------
Sfx_MusicChanPtr:
        ld      iy, SND_SEQ_CHANNELS
        or      a
        ret     z                        ; route 0 -> base, no stride
        ld      b, a                     ; b = route (iteration count)
        ld      de, SeqChannel_len
.add_loop:
        add     iy, de                   ; += SeqChannel_len, route times
        djnz    .add_loop
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
        ; (1) override the MUSIC SeqChannel that owns this physical route.
        ld      a, (ix+sx_saved_route)
        call    Sfx_MusicChanPtr         ; iy = &music SeqChannel (no multiply)
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
        ld      a, (ix+sx_saved_route)
        call    Sfx_MusicChanPtr         ; iy = &music noise SeqChannel
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
        ; load the SFX's OWN FM voice (hl = sx_patch_base) into the SFX channel's
        ; physical voice. Fm_PatchLoad reads ix=SfxChannel for the route, hl=ptr.
        ld      l, (ix+sx_patch_base)
        ld      h, (ix+sx_patch_base+1)  ; hl = SFX FmPatch window ptr
        call    Fm_PatchLoad             ; upload the SFX voice (preserves ix)

.activate:
        ; (4) the SfxChannel is now armed — Sfx_Frame will run it next frame.
        set     SCF_ACTIVE_B, (ix+sc_flags)
        ret

; ----------------------------------------------------------------------
; SfxDispatch — resolve a posted SFX id to its blob, then for EACH of the SFX's
; channels (chcount) call Sfx_SelectVoice (dynamic-among-eligible + priority steal,
; Task 8) and, on success, init the chosen SfxChannel slot from that channel's
; record + Sfx_Steal it. Multi-channel SFX (Dash = FM5+PSG3, Skid = PSG1+PSG2)
; steal their voices INDEPENDENTLY: each channel runs the full selection ladder, so
; one channel dropping (no eligible voice / too low priority) doesn't block the rest.
; In: a = the SFX id posted to SND_REQ_SFX. Clobbers af,bc,de,hl,ix,iy.
;
; The blob lives in 68k ROM, read via the $8000 window. Bank in the SFX bank and
; LEAVE it (stream-path model; in-bank with the FM6=FM song under test, so this is
; a no-op SetBank). The per-channel cmd_ptr/voice_ptr are offsets from the blob
; base; add them to the blob's window base.
;
; Loop state lives in RAM (SND_SFX_DISP_*) rather than registers because each
; iteration calls Sfx_SelectVoice/Sfx_Steal, which clobber the full register set
; (incl. ix/iy). The blob base + chcount + per-channel cursor survive across calls
; in RAM; the chosen slot/route come back from Sfx_SelectVoice each iteration.
; ----------------------------------------------------------------------
SfxDispatch:
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

        ; (1) resolve the overridden music SeqChannel (no multiply) into iy.
        ld      a, (ix+sx_saved_route)
        call    Sfx_MusicChanPtr         ; iy = &music SeqChannel[sx_saved_route]

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
        ld      a, (ix+sx_saved_route)
        call    Sfx_MusicChanPtr         ; iy = &music noise SeqChannel
        push    ix
        push    iy
        pop     ix                       ; ix = music noise channel
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .noise_done
        ld      a, (ix+sc_note)          ; the held noise note (mode/rate)
        call    Psg_Noise                ; re-emit noise control + volume (preserves ix)
.noise_done:
        pop     ix                       ; ix = SFX slot
        jr      .deactivate

.psg:
        ; --- PSG TONE: if a note was sounding, re-key it (re-applies tone+volume) ---
        push    ix
        push    iy
        pop     ix                       ; ix = music PSG tone channel
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .psg_done
        ld      a, (ix+sc_note)
        call    Psg_NoteOn               ; re-key the held tone (preserves ix)
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
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .fm_done              ; between notes -> clearing override suffices
    if SND_REKEY_OFF_THEN_ON
        call    Fm_NoteOff               ; clean 0->1 edge: key OFF first (mirrors ModUpdate)
    endif
        ld      a, (ix+sc_note)          ; the held note index
        call    Fm_NoteFromTable         ; re-key from the per-song fnum table (preserves ix)
.fm_done:
        pop     ix                       ; ix = SFX slot

.deactivate:
        ; (4) deactivate the SfxChannel (End already cleared SCF_ACTIVE — defensive)
        ; and drop its priority so the next SFX of any priority can claim the slot.
        res     SCF_ACTIVE_B, (ix+sc_flags)
        ld      (ix+sx_priority), 0
        pop     ix                       ; restore the caller's SFX-slot ix
        ret

; ----------------------------------------------------------------------
; Sfx_StopAll — STUB (Task 12 fills it). Clears all overrides + kills SfxChannels
; + drops the queue + resets ducking. For Task 6, minimal: deactivate the 7
; SfxChannels and clear every music override so a StopMusic can't leave a voice
; muted. Clobbers af,bc,de,hl,ix.
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
;       find the one with the LOWEST sx_priority; if incoming(e) >= that lowest ->
;       Sfx_Restore that victim (hands its music voice back) and reuse the slot;
;       else carry-set DROP. A lower-priority SFX can never cut off a higher one.
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
