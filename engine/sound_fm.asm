; ======================================================================
; engine/sound_fm.asm — YM2612 FM voice writer + patch load (Sound 1C, Task 3)
;
; Assembled INLINE inside the z80_sound_driver.asm `phase 0` blob (after the
; sequencer include, before the even-pad), so its labels resolve into Z80 RAM.
; Turns the sequencer's FM-route hooks into real YM2612 register writes: ONE FM
; channel becomes audible. PSG/DAC routes stay stubbed (Tasks 4/6).
;
; --- COEXISTENCE WITH THE 1B DAC LOOP (the central constraint) ------------
; The DAC streaming loop holds `de` = $4001 for its whole life and re-selects
; reg $2A on $4000 every pass before `ld (de),a`. THEREFORE every YM port write
; here uses ABSOLUTE addressing (`ld (4000h),a` style) and NEVER loads a port
; address into `de` — so de=$4001 is preserved BY CONSTRUCTION. (Sequencer_Frame
; runs from the Timer-A overflow poll in the DAC/idle loop, which also push/pops
; de, but we do not rely on that.) As belt-and-suspenders, every multi-write
; batch re-parks reg $2A on
; $4000 at the END (Fm_ReparkDac) so a DAC write that races in lands on $2A even
; before the consumer re-selects. We NEVER touch $2B (the DAC-enable edge is
; owned by init / sample-start — re-toggling it clicks).
;
; --- TABLES (decision 1: INLINE, not banked) ------------------------------
; The FM pitch table, log-volume LUT, and carrier-mask table are emitted as
; Z80-syntax data in engine/sound_tables_z80.asm and included into THIS blob
; (FmPitchTableZ / LogVolumeLutZ / CarrierMaskTableZ). They are static and tiny
; (~454 bytes), so an inline directly-addressable copy is simplest and needs no
; $8000-window banking. (Task 6 may switch to the banked 68k ROM tables.)
;
; --- VOLUME SOURCE (decision 2: RE-READ the patch, no per-channel cache) ---
; Fm_SetVolume re-derives the FmPatch pointer from sc_patch + the inline patch-
; table base and re-reads algorithm + base TLs on each volume change. Volume
; changes are infrequent and the inline patch table is directly addressable, so
; this costs nothing extra and keeps SeqChannel at 11 bytes (no cache fields).
;
; --- FM CHANNEL MAPPING (route -> part, channel-in-part, chsel) -----------
;   route  CHROUTE_  part  ch-in-part  chsel(key-on)
;     0      FM1      I(0)     0          $00
;     1      FM2      I(0)     1          $01
;     2      FM3      I(0)     2          $02
;     3      FM4     II(1)     0          $04
;     4      FM5     II(1)     1          $05
;     5      FM6     II(1)     2          $06   (Sound 1D: adaptive FM6 slot)
; part = (route>=3); ch-in-part = route - (part?3:0); chsel = (part<<2)|ch.
; (Note the deliberate $03 gap in chsel — FM6 = $06 is the DAC's slot, used by an
; FM6=FM song with DAC mode OFF. Fm_RoutePart's route-3 split yields ch 2 for
; route 5 automatically, so NO writer change was needed for FM6.)
; ======================================================================

; ----------------------------------------------------------------------
; Fm_YmWrite — write one YM2612 register, ABSOLUTE addressing (de untouched).
; In:  a = register number, c = data byte, b = part (0 = part I, 1 = part II)
; Part I  : select reg on $4000, nop delay, data to $4001.
; Part II : select reg on $4002, nop delay, data to $4003.
; NO busy-poll — the `nop` plus the caller's per-op loop overhead supplies the
; inter-write spacing the YM2612 needs for regs >= $30.
; Clobbers: af (a is consumed). Preserves bc, de, hl, ix.
; ----------------------------------------------------------------------
Fm_YmWrite:
        bit     0, b                     ; part II?
        jr      nz, .partII
        ld      (SND_Z80_YM_A0), a       ; $4000 = reg select (part I)
        nop                              ; inter-write delay (no busy-poll)
        ld      a, c
        ld      (SND_Z80_YM_A1), a       ; $4001 = data (part I)
        ret
.partII:
        ld      (SND_Z80_YM_A2), a       ; $4002 = reg select (part II)
        nop                              ; inter-write delay
        ld      a, c
        ld      (SND_Z80_YM_A3), a       ; $4003 = data (part II)
        ret

; ----------------------------------------------------------------------
; Fm_ReparkDac — re-select reg $2A on $4000 (part I addr port) so a racing DAC
; write lands on the DAC-data reg. Defensive end-of-batch belt-and-suspenders
; (strictly redundant — the DAC consumer/idle loop re-selects $2A every pass —
; but cheap and future-proof). NEVER touches $2B.
; Clobbers: af. Preserves bc, de, hl, ix.
; ----------------------------------------------------------------------
Fm_ReparkDac:
        ld      a, SND_REG_DAC_DATA      ; $2A
        ld      (SND_Z80_YM_A0), a       ; re-park part-I addr port on DAC data
        ret

; ----------------------------------------------------------------------
; Fm_RoutePart — derive (b = part, c = ch-in-part) from the channel route.
; In:  ix = SeqChannel.  Out: b = part (0/1), c = ch-in-part (0..2).
; Clobbers: af, bc. Preserves de, hl, ix.  (FM routes are 0..5 incl. FM6;
; non-FM routes never reach here — the hooks gate on SCF_IS_FM first. The
; `cp 3`/`sub 3` split maps route 5 -> part II, ch 2 = FM6 with no special case.)
; ----------------------------------------------------------------------
Fm_RoutePart:
        ld      a, (ix+sc_route)
        ld      b, 0                     ; assume part I
        cp      3                        ; route < 3 -> part I, ch = route
        jr      c, .done
        ld      b, 1                     ; route >= 3 -> part II
        sub     3                        ; ch-in-part = route - 3
.done:
        ld      c, a                     ; c = ch-in-part (0..2)
        ret

; ----------------------------------------------------------------------
; Fm_PatchPtr — compute the FmPatch pointer for sc_patch into hl.
; In:  ix = SeqChannel (uses sc_patch).  Out: hl = (SND_SEQ_PATCHTAB) + patch*26.
; The base is the LOADED patch-table ptr (SND_SEQ_PATCHTAB), set by Snd_LoadSong:
; the 1C copy-path sets it to FmPatchInlineTable (Z80 RAM); the Sound 1D stream-
; path sets it to the song's patch bank window address (read transparently through
; the $8000 window while the song's bank is held). So FM patch loads work the same
; whether the bank lives in RAM or the banked ROM window. (Before 1D this label
; hardcoded FmPatchInlineTable; the dynamic base is functionally identical for the
; 1C path since the loader sets SND_SEQ_PATCHTAB = FmPatchInlineTable there.)
; FmPatch_len = 26. Multiply by shift/add (NO mulu): keep P2 = patch*2 in de,
; then accumulate in hl by doubling and adding P2 — the running products are
;   *2 (=P2) -> *4 -> *8 -> +P2=*10 -> *20 -> +P2=*22 -> +P2=*24 -> +P2=*26.
; Clobbers: af, de, hl. Preserves bc, ix.
; ----------------------------------------------------------------------
Fm_PatchPtr:
        ld      a, (ix+sc_patch)
        ld      l, a
        ld      h, 0                     ; hl = patch
        add     hl, hl                   ; hl = patch*2  (call it P2)
        ld      e, l
        ld      d, h                     ; de = P2
        add     hl, hl                   ; hl = P2*2  = patch*4
        add     hl, hl                   ; hl = P2*4  = patch*8
        add     hl, de                   ; hl = patch*8 + patch*2 = patch*10
        add     hl, hl                   ; hl = patch*20
        add     hl, de                   ; hl = patch*20 + patch*2 = patch*22
        add     hl, de                   ; hl = patch*24
        add     hl, de                   ; hl = patch*26  (= patch*FmPatch_len)
        ld      de, (SND_SEQ_PATCHTAB)   ; base = loaded patch-table ptr (RAM or window)
        add     hl, de                   ; hl = table base + patch*26
        ret

; ----------------------------------------------------------------------
; Fm_PatchLoad — load a full FM voice into a channel (one-time per patch change,
; cost amortized — NOT per note). In: ix = SeqChannel, hl = FmPatch ptr.
; Writes fp_alg_fb -> $B0+ch, fp_lr_ams_fms -> $B4+ch, then the 4 operators ×
; 6 per-op regs ($30/$40/$50/$60/$70/$80 + ch + op*4) via Fm_YmWrite, in the
; patch's physical-register operator order (array index 0..3 = +0/+4/+8/+C).
; Clobbers: af, bc, de, hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_PatchLoad:
        push    hl                       ; save patch ptr (Fm_RoutePart clobbers bc only)
        call    Fm_RoutePart             ; b = part, c = ch-in-part
        ld      a, c
        ld      (Fm_ScratchCh), a        ; stash ch-in-part
        ld      a, b
        ld      (Fm_ScratchPart), a      ; stash part
        pop     hl                       ; hl -> patch (fp_alg_fb)

        ; --- $B0+ch : algorithm/feedback ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_ALG_FB        ; reg = $B0 + ch
        ld      c, (hl)                  ; data = fp_alg_fb
        inc     hl
        call    Fm_YmWrite

        ; --- $B4+ch : L/R / AMS / FMS ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_LR_AMS_FMS    ; reg = $B4 + ch
        ld      c, (hl)                  ; data = fp_lr_ams_fms
        inc     hl
        call    Fm_YmWrite

        ; --- 6 per-op register groups, each 4 operators (op*4 stride) ---
        ; hl currently points at fp_dt_mul[0]. The 6 groups are contiguous in the
        ; FmPatch record in the same order as the register bases below.
        ld      a, SND_REG_OP_DT_MUL     ; $30
        call    Fm_PatchOpGroup
        ld      a, SND_REG_OP_TL         ; $40 (TL group: adds per-op sc_opbias, clamps)
        call    Fm_PatchTlGroup
        ld      a, SND_REG_OP_RS_AR      ; $50
        call    Fm_PatchOpGroup
        ld      a, SND_REG_OP_AM_D1R     ; $60
        call    Fm_PatchOpGroup
        ld      a, SND_REG_OP_D2R        ; $70
        call    Fm_PatchOpGroup
        ld      a, SND_REG_OP_D1L_RR     ; $80
        call    Fm_PatchOpGroup

        jp      Fm_ReparkDac             ; defensive end-of-batch re-park ($2A)

; --- Fm_PatchOpGroup: write one 4-operator register group.
; In:  a = register base ($30/$40/...), hl = ptr to the 4 patch bytes (advanced).
;      Fm_ScratchCh = ch-in-part, Fm_ScratchPart = part.
; Writes (base + op*4 + ch) = patch[op] for op = 0..3. Advances hl by 4.
; Clobbers: af, bc, de, hl (hl advanced by 4). Preserves ix. (Internal helper
; of Fm_PatchLoad.)
Fm_PatchOpGroup:
        ld      d, a                     ; d = register base (preserved across ops)
        ld      e, 0                     ; e = op*4 accumulator (0,4,8,12)
        ld      b, 4                     ; 4 operators
.op_loop:
        push    bc                       ; save op counter (Fm_YmWrite uses bc)
        push    de                       ; save base+offset accumulator
        ; reg = base + (op*4) + ch
        ld      a, d                     ; base
        add     a, e                     ; + op*4
        push    hl
        ld      hl, Fm_ScratchCh
        add     a, (hl)                  ; + ch-in-part
        pop     hl
        ld      c, (hl)                  ; data = patch[op]
        inc     hl                       ; advance patch ptr
        push    hl
        ld      hl, Fm_ScratchPart
        ld      b, (hl)                  ; b = part
        pop     hl
        call    Fm_YmWrite               ; a=reg, c=data, b=part
        pop     de
        ld      a, e
        add     a, 4
        ld      e, a                     ; op offset += 4
        pop     bc
        djnz    .op_loop
        ret

; --- Fm_PatchTlGroup: write the $40 (TL) register group WITH the per-operator
; additive TL bias (sc_opbias[op]) applied. For each op 0..3:
;   eff_TL = clamp(patch_TL[op] + sc_opbias[op], 0, $7F)
; sc_opbias is a SIGNED two's-complement byte (-128..127): NEGATIVE brightens
; (reduces attenuation), POSITIVE darkens. TL is 7-bit attenuation, so the result
; is clamped on BOTH ends — < $00 -> $00 (max brightness), > $7F -> $7F (silent).
; sc_opbias is a per-note brightness/level bias LATCHED here at patch load (the Zyrinx key-on
; latch model) — it is NOT re-asserted per frame, so this is the ONLY place it is
; applied (cost amortized at patch load, not per note/frame). sc_opbias is zeroed
; by the seq clear, so a song that never emits MEV_OPBIAS gets eff_TL = patch_TL
; (this group is then byte-identical to Fm_PatchOpGroup for $40 — no regression).
; In:  a = $40 (register base), hl = ptr to the 4 patch TL bytes (advanced by 4).
;      ix = SeqChannel (reads sc_opbias[op]); Fm_ScratchCh/Part set by Fm_PatchLoad.
; The op index 0..3 is tracked in Fm_ScratchOp so the bias byte can be indexed.
; Clobbers: af, bc, de, hl (hl advanced by 4). Preserves ix. (Internal helper.)
Fm_PatchTlGroup:
        ld      d, a                     ; d = $40 base (preserved across ops)
        ld      e, 0                     ; e = op*4 accumulator (0,4,8,12)
        xor     a
        ld      (Fm_ScratchOp), a        ; op index = 0
        ld      b, 4                     ; 4 operators
.tl_loop:
        push    bc                       ; save op counter (Fm_YmWrite uses bc)
        push    de                       ; save base+offset accumulator
        ; --- data = clamp(patch_TL[op] + sc_opbias[op], 0, $7F) ---
        ; sc_opbias[op] is a SIGNED two's-complement byte (-128..127): negative
        ; BRIGHTENS (lowers attenuation), positive DARKENS. Done as a signed 16-bit
        ; add then clamped on BOTH ends — mirrors the proven Fm_NoteFromTable
        ; pattern: result < $00 -> $00 (max brightness), > $7F -> $7F (silent).
        ; patch_TL is 0..$7F (positive, high byte 0).
        ld      a, (hl)                  ; patch base TL for this op (0..$7F)
        inc     hl                       ; advance patch ptr
        push    hl                       ; save patch ptr across the bias index
        ld      c, a                     ; c = base TL (preserve across the index math)
        ; hl = &sc_opbias[op] = ix-base + sc_opbias + op
        push    ix
        pop     hl                       ; hl = SeqChannel base
        ld      a, (Fm_ScratchOp)        ; op index 0..3
        add     a, sc_opbias             ; + sc_opbias field offset
        add     a, l
        ld      l, a
        jr      nc, .nocarry
        inc     h
.nocarry:
        ; de = sign-extended signed bias: a=$FF..hi if bias<0, else $00..hi
        ld      a, (hl)                  ; a = sc_opbias[op] (signed)
        ld      e, a
        add     a, a                     ; CF = sign bit of bias
        sbc     a, a                     ; a = $FF if bias<0, else $00
        ld      d, a                     ; de = sign-extended bias (signed 16-bit)
        ld      l, c                     ; hl = patch base TL (0..$7F, positive)
        ld      h, 0
        add     hl, de                   ; hl = patch_TL + signed bias (signed 16-bit)
        bit     7, h                     ; result negative? (h >= $80)
        jr      nz, .clamp_lo            ; < 0 -> clamp to $00 (max brightness)
        ld      a, h
        or      a
        jr      nz, .clamp_hi            ; high byte set -> > $7F -> clamp silent
        ld      a, l
        cp      SND_FM_TL_MAX+1          ; result > $7F ?
        jr      c, .tl_ok                ; in range 0..$7F
.clamp_hi:
        ld      a, SND_FM_TL_MAX         ; clamp to $7F (silent)
        jr      .tl_ok
.clamp_lo:
        xor     a                        ; clamp to $00 (max brightness)
.tl_ok:
        ld      c, a                     ; c = effective TL (data)
        pop     hl                       ; restore patch ptr (already advanced)
        ; --- reg = $40 + (op*4) + ch ---
        pop     de                       ; recover d=base, e=op*4 (re-push below)
        push    de
        ld      a, d                     ; $40 base
        add     a, e                     ; + op*4
        push    hl
        ld      hl, Fm_ScratchCh
        add     a, (hl)                  ; + ch-in-part
        ld      hl, Fm_ScratchPart
        ld      b, (hl)                  ; b = part
        pop     hl
        call    Fm_YmWrite               ; a=reg, c=data, b=part
        pop     de
        ld      a, e
        add     a, 4
        ld      e, a                     ; op offset += 4
        ld      a, (Fm_ScratchOp)
        inc     a
        ld      (Fm_ScratchOp), a        ; op index += 1
        pop     bc
        djnz    .tl_loop
        ret

; ----------------------------------------------------------------------
; Fm_SetVolume — apply linear volume to the CARRIER operators only.
; In: ix = SeqChannel, a = linear volume (0..127).
; log  = LogVolumeLutZ[vol];  alg  = patch.fp_alg_fb & 7;  mask = CarrierMaskTableZ[alg].
; For each op (0..3) whose mask bit is set: $40+ch+op*4 = min($7F, base_TL+log).
; Modulator TL is left at the patch value (preserves timbre). Carriers only.
; Re-reads the patch (decision 2) — no per-channel cache.
; Clobbers: af, bc, de, hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_SetVolume:
        ; log attenuation delta from the inline LUT
        ld      l, a
        ld      h, 0
        ld      de, LogVolumeLutZ
        add     hl, de
        ld      a, (hl)
        ld      (Fm_ScratchLog), a       ; stash log delta

        ; --- Phase 5a music ducking (spec §7) -------------------------------------
        ; Fold the GLOBAL music duck level into the carrier-TL delta so EVERY music
        ; volume write (note events AND the per-frame re-assert) ducks automatically
        ; — no separate duck pass can be out-fought by the music's own note volumes.
        ; MUSIC ONLY: an SfxChannel lives at/above SND_SFX_BASE ($1D00) and must NOT
        ; duck (ducking the SFX would defeat the cut-through). Music SeqChannels live
        ; at SND_SEQ_CHANNELS ($1808..) — strictly below $1D00 — so the high byte of
        ; ix cleanly separates the two (music hi = $18/$19 < $1D; SFX hi = $1D/$1E).
        ; The per-op carrier loop clamps base+bias+log to [0,$7F], so a saturated
        ; Fm_ScratchLog can't wrap — but pre-clamp to $7F here for cleanliness.
        push    ix
        pop     hl                       ; hl = ix (the channel ptr)
        ld      a, h
        cp      SND_SFX_BASE>>8          ; CARRY set => ix < $1D00 => MUSIC channel
        jr      nc, .no_duck             ; SFX channel -> never duck (no add)
        ld      a, (SND_SFX_DUCK_LEVEL)
        or      a
        jr      z, .no_duck              ; duck level 0 -> nothing to add
        ld      hl, Fm_ScratchLog
        add     a, (hl)                  ; log delta + duck level
        jr      nc, .duck_ok
        ld      a, SND_FM_TL_MAX         ; carry out of 8 bits -> clamp to $7F (silent)
.duck_ok:
        cp      SND_FM_TL_MAX+1
        jr      c, .duck_store
        ld      a, SND_FM_TL_MAX         ; clamp the summed delta to $7F
.duck_store:
        ld      (hl), a                  ; ducked carrier-TL delta
.no_duck:

        call    Fm_RoutePart             ; b = part, c = ch-in-part
        ld      a, c
        ld      (Fm_ScratchCh), a
        ld      a, b
        ld      (Fm_ScratchPart), a

        call    Fm_PatchPtr              ; hl -> FmPatch for sc_patch
        ; algorithm = fp_alg_fb & 7 -> carrier mask
        ld      a, (hl)                  ; fp_alg_fb (fp_alg_fb is +0)
        and     7
        push    hl                       ; save patch base
        ld      l, a
        ld      h, 0
        ld      de, CarrierMaskTableZ
        add     hl, de
        ld      a, (hl)                  ; a = 4-bit carrier mask
        ld      (Fm_ScratchMask), a
        pop     hl                       ; hl -> patch base again

        ; hl -> fp_tl[0] = patch base + FmPatch_fp_tl
        ld      de, FmPatch_fp_tl
        add     hl, de                   ; hl -> base TL array [S1,S3,S2,S4]

        ; Loop over operators 0..3. `c` holds a walking carrier-mask bit that
        ; starts at bit0 (op 0 = reg offset +0) and shifts left each op, so
        ; `mask & c` tests "is operator i a carrier". `e` accumulates op*4.
        ld      b, 4                     ; 4 operators
        ld      e, 0                     ; e = op*4 accumulator (0,4,8,12)
        ld      c, 1                     ; c = walking mask bit (1<<op), starts bit0
.op_loop:
        push    bc                       ; save op counter (b) + walking bit (c)
        ld      a, (Fm_ScratchMask)
        and     c                        ; mask bit set for this op?
        jr      z, .skip_op              ; modulator -> leave TL untouched
        ; carrier: effective_TL = clamp(base_TL + sc_opbias[op] + log, 0, $7F).
        ; INCLUDE the per-operator bias (signed) so re-applying volume does NOT
        ; clobber the opbias Fm_PatchLoad wrote — mirrors the driver's key-on
        ; TL = (0x7F^patch_TL) + op_mod. (Bug: writing base+log alone dropped the
        ; bias on any carrier operator -> wrong timbre / lost kick punch on alg5+
        ; voices where a biased operator is a carrier.) op index = e>>2.
        ld      d, (hl)                  ; d = base TL (0..$7F)
        ld      a, e
        rrca
        rrca
        and     3                        ; a = op index (e>>2)
        push    hl                       ; save fp_tl ptr (restored before reg write)
        ld      l, a
        ld      h, 0
        push    ix
        pop     bc
        add     hl, bc                   ; hl = SeqChannel base + op
        ld      bc, sc_opbias
        add     hl, bc                   ; hl = &sc_opbias[op]
        ld      a, (hl)                  ; a = sc_opbias[op] (signed)
        ld      c, a
        add     a, a
        sbc     a, a
        ld      b, a                     ; bc = sign-extended bias (16-bit signed)
        ld      l, d
        ld      h, 0                     ; hl = base TL (positive)
        add     hl, bc                   ; hl = base + bias
        ld      a, (Fm_ScratchLog)
        ld      c, a
        ld      b, 0                     ; bc = log delta (positive)
        add     hl, bc                   ; hl = base + bias + log (signed 16-bit)
        bit     7, h                     ; result < 0 ?
        jr      nz, .clamp_lo            ; -> $00 (max brightness)
        ld      a, h
        or      a
        jr      nz, .clamp               ; high byte set -> > $7F -> silent
        ld      a, l
        cp      SND_FM_TL_MAX+1          ; result > $7F ?
        jr      c, .tl_ok
.clamp:
        ld      a, SND_FM_TL_MAX         ; clamp to $7F (silent)
        jr      .tl_ok
.clamp_lo:
        xor     a                        ; clamp to $00 (max brightness)
.tl_ok:
        ld      c, a                     ; data = effective TL
        pop     hl                       ; restore fp_tl ptr
        ; reg = $40 + (op*4) + ch
        ld      a, SND_REG_OP_TL
        add     a, e                     ; + op*4
        push    hl
        ld      hl, Fm_ScratchCh
        add     a, (hl)                  ; a = reg = $40 + op*4 + ch
        ld      hl, Fm_ScratchPart
        ld      b, (hl)                  ; b = part
        pop     hl
        call    Fm_YmWrite               ; a=reg, c=data, b=part
.skip_op:
        inc     hl                       ; advance to next base-TL byte
        ld      a, e
        add     a, 4
        ld      e, a                     ; op offset += 4
        pop     bc                       ; restore op counter (b) + walking bit (c)
        sla     c                        ; walking bit <<= 1 (next op)
        djnz    .op_loop
        jp      Fm_ReparkDac             ; defensive re-park ($2A)

; ----------------------------------------------------------------------
; Fm_SetPan — write the channel's $B4 (L/R / AMS / FMS) register from sc_pan.
; In: ix = SeqChannel (uses sc_pan). Reg = $B4 + ch-in-part, part-aware. Called by
; ModUpdate only when sc_pan changed (write-on-change), so the YM write here is
; never redundant. NOTE: $B4 is a STEREO-OUTPUT (+ hardware LFO depth) register;
; the controller confirms the exact $B4 bytes via the Exodus YM register stream /
; the Task-9 oracle diff.
; Clobbers: af, bc. Preserves de, hl, ix. (de = the DAC loop's $4001 is untouched —
; Fm_RoutePart/Fm_YmWrite/Fm_ReparkDac all use absolute YM addressing.)
; ----------------------------------------------------------------------
Fm_SetPan:
        call    Fm_RoutePart             ; b = part, c = ch-in-part (clobbers af,bc)
        ld      a, c                      ; a = ch-in-part
        add     a, SND_REG_LR_AMS_FMS     ; reg = $B4 + ch (b still = part)
        ld      c, (ix+sc_pan)            ; data = sc_pan (the raw $B4 byte)
        call    Fm_YmWrite                ; a=reg, c=data, b=part
        jp      Fm_ReparkDac              ; defensive re-park ($2A); preserves ix

; ----------------------------------------------------------------------
; Fm_RegDelta — write ONE per-operator YM2612 register for the current channel,
; PART-AWARE, resolved from a reg_sel byte (Phase 3 Task 5 voice-stepping).
; This is the mid-note minimal-register-delta primitive: the timbre of a HELD
; note is swept by writing only the register(s) that change between voice steps
; (the dominant Zyrinx lead step is ONE byte — operator S1's TL). It does NOT
; touch $28 (key) and does NOT re-key — per the re-key rule, only a pitch change
; (MEV_PITCHENV) re-articulates a note (see Seq_Op_RegDelta).
;
; In:  ix = SeqChannel, a = reg_sel = (group_code << REGDELTA_GROUP_SHIFT) | op,
;      c = value (the register data byte; preserved through the route math).
; reg_sel -> ym_reg = RegDeltaGroupBase[group_code] + op*4 + ch-in-part (part-aware
; via Fm_RoutePart). group_code 0..5 = $30/$40/$50/$60/$70/$80; op 0..3 = the
; physical operator (reg stride +4). group_code is masked to the table size so a
; bad encoding can never index past RegDeltaGroupBase.
; Clobbers: af, bc, de, hl. Preserves ix. (de = the DAC loop's $4001 is untouched —
; Fm_RoutePart/Fm_YmWrite use absolute YM addressing.)
; ----------------------------------------------------------------------
Fm_RegDelta:
        ld      (Fm_ScratchLog), a       ; stash reg_sel  (Fm_ScratchLog is free here)
        ld      a, c
        ld      (Fm_ScratchMask), a      ; stash value    (reuse the same free scratch)

        ; route -> part + ch-in-part (the same pattern as Fm_SetPan/Fm_NoteOnFreq).
        call    Fm_RoutePart             ; b = part, c = ch-in-part (clobbers af,bc)
        ld      a, c
        ld      (Fm_ScratchCh), a        ; ch-in-part
        ld      a, b
        ld      (Fm_ScratchPart), a      ; part

        ; --- resolve the register from reg_sel: base[group] + op*4 + ch ---
        ld      a, (Fm_ScratchLog)       ; a = reg_sel
        and     REGDELTA_OP_MASK         ; a = op (0..3)
        add     a, a
        add     a, a                     ; a = op*4 (operator reg stride)
        ld      e, a                     ; e = op*4 (preserve across the group lookup)
        ld      a, (Fm_ScratchLog)       ; a = reg_sel again
        rrca
        rrca                             ; a = reg_sel >> 2 (group_code in low bits)
        and     REGDELTA_GROUP_MASK      ; a = group_code field
        cp      REGDELTA_GROUP_COUNT
        jr      c, .group_ok
        xor     a                        ; out-of-range group_code -> group 0 (defensive)
.group_ok:
        ld      l, a
        ld      h, 0
        ld      bc, RegDeltaGroupBase
        add     hl, bc                   ; hl = &RegDeltaGroupBase[group_code]
        ld      a, (hl)                  ; a = group base ($30/$40/.../$80)
        add     a, e                     ; + op*4
        ld      hl, Fm_ScratchCh
        add     a, (hl)                  ; + ch-in-part -> a = the YM register number
        push    af                       ; save reg across the value/part loads
        ld      a, (Fm_ScratchMask)
        ld      c, a                     ; c = value
        ld      a, (Fm_ScratchPart)
        ld      b, a                     ; b = part
        pop     af                       ; a = reg
        call    Fm_YmWrite               ; a=reg, c=value, b=part (preserves ix)
        jp      Fm_ReparkDac             ; defensive re-park ($2A); preserves ix

; RegDeltaGroupBase — group_code 0..5 -> the per-operator YM register-group base.
; Order MATCHES the FmPatch group order + the SND_REG_OP_* equates: 0=$30 DT/MUL,
; 1=$40 TL, 2=$50 RS/AR, 3=$60 AM/D1R, 4=$70 D2R, 5=$80 D1L/RR. The $40 (TL) group,
; op0 is the canonical voice-step target (the lead's 1-byte sweep).
RegDeltaGroupBase:
        db      SND_REG_OP_DT_MUL        ; group 0 = $30
        db      SND_REG_OP_TL            ; group 1 = $40 (TL — the lead voice-step)
        db      SND_REG_OP_RS_AR         ; group 2 = $50
        db      SND_REG_OP_AM_D1R        ; group 3 = $60
        db      SND_REG_OP_D2R           ; group 4 = $70
        db      SND_REG_OP_D1L_RR        ; group 5 = $80
RegDeltaGroupBase_End:

        if (RegDeltaGroupBase_End - RegDeltaGroupBase) <> REGDELTA_GROUP_COUNT
          fatal "RegDeltaGroupBase length must be REGDELTA_GROUP_COUNT (\{REGDELTA_GROUP_COUNT})"
        endif

; ----------------------------------------------------------------------
; Fm_TransposeClamp — hl = clamp_0_max(note + signed sc_transpose), h=0.
; In: a = note index, c = max valid index (inclusive). ix = SeqChannel.
; Out: hl = clamped index (0..c, h=0). Clobbers af,de,hl. Preserves bc,ix.
; Shared by Fm_NoteFromTable (max $83) and Fm_NoteOn (max FMPITCH_MAX_IDX). The
; spindash rev feeds sc_transpose (spec §6); for the common note sc_transpose==0.
; The add is signed 16-bit so a large negative transpose can't wrap (the RE's
; saturating clamp: below 0 -> 0, above max -> max).
; ----------------------------------------------------------------------
Fm_TransposeClamp:
        ld      l, a
        ld      h, 0                     ; hl = note index (positive)
        ld      a, (ix+sc_transpose)     ; signed per-pattern transpose
        ld      e, a
        add     a, a                     ; CF = sign bit of transpose
        sbc     a, a                     ; a = $FF if transpose<0, else $00
        ld      d, a                     ; de = sign-extended transpose
        add     hl, de                   ; hl = note + transpose (signed 16-bit)
        bit     7, h                     ; result negative?
        jr      z, .nonneg
        ld      hl, 0                    ; < 0 -> clamp to 0
        ret
.nonneg:
        ld      a, h                     ; high byte set -> > max -> clamp
        or      a
        jr      nz, .clamp_hi
        ld      a, l
        cp      c                        ; l vs max
        ret     z                        ; l == max -> in range (h=0)
        ret     c                        ; l <  max -> in range (h=0)
.clamp_hi:
        ld      l, c                     ; clamp to max
        ret

; ----------------------------------------------------------------------
; Fm_NoteFromTable — key a note from the PER-SONG fnum (pitch) table.
; In: ix = SeqChannel, a = note index (an ABSOLUTE index 0..PITCHTAB_MAX_IDX into
;     the 132-entry chromatic fnum table — NOT the engine's FmPitchTableZ note
;     numbering). This is the Phase-3 pitch-envelope renderer path used by
;     ModUpdate; the per-song table is the exact Zyrinx Moving-Trucks fnum table.
;
; TABLE: TWO PARALLEL PAGES (sound_constants.asm) — A4 page first (PITCHTAB_COUNT
; bytes), then the A0 page. So for index i: $A4 = base[i], $A0 = base[COUNT+i].
; base = Snd_PitchTabPtr (per-song) when nonzero, else MovingTrucks_PitchTable
; (the inline engine-default table). idx = clamp_0_83(note+transpose) via
; Fm_TransposeClamp; then $A4/$A0 are looked up and Fm_NoteOnFreq keys on.
; Clobbers: af, bc, de, hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_NoteFromTable:
        ; --- idx = clamp_0_83(note + sc_transpose) (signed) ---
        ld      c, PITCHTAB_MAX_IDX
        call    Fm_TransposeClamp        ; hl = clamped idx (0..$83, h=0)
        ld      b, h
        ld      c, l                     ; bc = idx (b=0)

        ; --- resolve table base: per-song ptr, else engine default ---
        ld      hl, (Snd_PitchTabPtr)
        ld      a, h
        or      l
        jr      nz, .have_base
        ld      hl, MovingTrucks_PitchTable
.have_base:
        ; --- $A4 = base[idx] ---
        add     hl, bc                   ; hl = &A4page[idx]
        ld      d, (hl)                  ; d = $A4 value (block|fnumHi)
        ; --- $A0 = base[PITCHTAB_COUNT + idx] = &A4page[idx] + PITCHTAB_COUNT ---
        ld      bc, PITCHTAB_COUNT
        add     hl, bc                   ; hl = &A0page[idx]
        ld      e, (hl)                  ; e = $A0 value (fnum low)
        ; de = (d=$A4, e=$A0) -> write freq + key on (preserves ix)
        jp      Fm_NoteOnFreq

; ----------------------------------------------------------------------
; Fm_NoteOn — key a note on the channel.
; In: ix = SeqChannel, a = pitch index (0..94).
; FmPitchTableZ[pitch] = packed word: HIGH byte = $A4 value ((block<<3)|fnumHi),
; LOW byte = $A0 value (fnum low). Write $A4+ch FIRST (latches block/fnum-high),
; then $A0+ch (commits). Then key-on via PART I: $28 = $F0 | chsel.
; Sets SCF_KEYED.
; Clobbers: af, bc, de, hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_NoteOn:
        ; apply the signed sc_transpose (the spindash rev feeds this, spec §6) + clamp to
        ; FmPitchTableZ's valid range 0..FMPITCH_MAX_IDX. sc_transpose==0 for a
        ; non-transposed note, so this is a no-op for the common case.
        ld      c, FMPITCH_MAX_IDX
        call    Fm_TransposeClamp        ; hl = clamped idx (0..FMPITCH_MAX_IDX, h=0)
        ; hl = &FmPitchTableZ[idx] = base + idx*2
        add     hl, hl                   ; idx*2 (word entries)
        ld      de, FmPitchTableZ
        add     hl, de
        ld      e, (hl)                  ; e = low  byte = $A0 value (fnum low)
        inc     hl
        ld      d, (hl)                  ; d = high byte = $A4 value (block|fnumHi)
        ; fall into Fm_NoteOnFreq with de = packed (d=$A4 val, e=$A0 val)

; ----------------------------------------------------------------------
; Fm_NoteOnFreq — key a note at a RAW frequency word (no pitch-table lookup).
; In: ix = SeqChannel, d = $A4 value ((block<<3)|fnumHi), e = $A0 value (fnum low).
; Shared tail of Fm_NoteOn; the MEV_NOTE_RAW handler enters HERE with de preset so
; a VGM-derived song reproduces the original chip pitch exactly. Same write order
; as Fm_NoteOn ($A4 first, then $A0, then key-on). Sets SCF_KEYED.
; Clobbers: af, bc, de, hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_NoteOnFreq:
        ; Write $A4 then $A0 (no key-on yet) via the shared Fm_WriteFreq head. It
        ; re-parks $2A at the end, harmless before the key-on below. de (the fnum word)
        ; is reloaded after for the base-freq latch.
        push    de                       ; save the split fnum bytes across the writes
        call    Fm_WriteFreq             ; $A4 then $A0 (Fm_ScratchPart/Ch set inside)
        pop     de                       ; e = $A0 val, d = $A4 val (for the latch below)

        ; --- latch the unmodulated note word for the vibrato renderer (spec §5) -----
        ; The pitch-mod offset is summed onto THIS each frame (d=$A4 high, e=$A0 low).
        ; sc_base_freq is an SfxChannel-only field (offset +51, PAST a 39-byte music
        ; SeqChannel), and Fm_NoteOnFreq runs for MUSIC FM too (MT) — so GATE on the
        ; SFX-channel test: a music note must NOT write here (it would corrupt the next
        ; channel's RAM). SfxChannels live at/above SND_SFX_BASE ($1D00).
        push    ix
        pop     hl                       ; hl = ix
        ld      a, h
        cp      SND_SFX_BASE>>8          ; CARRY set => ix < $1D00 => MUSIC channel
        jr      c, .keyon                ; music -> no mod fields; straight to key-on
        ld      (ix+sc_base_freq), d     ; high byte slot = $A4 value
        ld      (ix+sc_base_freq+1), e   ; low byte slot  = $A0 value
.keyon:
        ; --- KEY ON: $28 = $F0 | chsel, ALWAYS via part I ---
        call    Fm_ChSel                 ; a = chsel = (part<<2)|ch
        or      SND_FM_KEYON_OPMASK      ; $F0 | chsel (all 4 ops on)
        ld      c, a                     ; data = key-on byte
        ld      a, SND_REG_KEY_ONOFF     ; reg = $28
        ld      b, 0                     ; key on/off is GLOBAL -> part I
        call    Fm_YmWrite

        set     SCF_KEYED_B, (ix+sc_flags)
        ; --- per-note pitch-mod re-arm (Task 4) — SFX channels only -----------------
        ; Mod_ReArm touches sc_mod_*/sc_last_freq (SfxChannel-only). Gate on the same
        ; SFX-channel test so a MUSIC note (MT) never reads/writes those fields.
        push    ix
        pop     hl                       ; hl = ix
        ld      a, h
        cp      SND_SFX_BASE>>8          ; CARRY set => ix < $1D00 => MUSIC channel
        jr      c, .skip_rearm           ; music -> no mod re-arm (MT byte-identical)
        call    Mod_ReArm                ; per-note re-arm (no-op if sc_mod_ctrl==0)
.skip_rearm:
        jp      Fm_ReparkDac             ; defensive re-park ($2A)

; ----------------------------------------------------------------------
; Fm_NoteOff — key the channel off (op_mask = 0). Always via part I.
; In: ix = SeqChannel. Clears SCF_KEYED.
; Clobbers: af, bc, de. Preserves hl, ix.
; ----------------------------------------------------------------------
Fm_NoteOff:
        call    Fm_ChSel                 ; a = chsel = (part<<2)|ch
        ld      c, a                     ; data = $28 byte = chsel (op_mask 0 -> key off)
        ld      a, SND_REG_KEY_ONOFF     ; reg = $28
        ld      b, 0                     ; GLOBAL -> part I
        call    Fm_YmWrite
        res     SCF_KEYED_B, (ix+sc_flags)
        jp      Fm_ReparkDac             ; defensive re-park ($2A)

; ----------------------------------------------------------------------
; Fm_WriteFreq — write a raw frequency word to $A4/$A0 WITHOUT keying on (the
; vibrato/pitch-mod path: change pitch on a HELD note, no EG retrigger). Mirrors
; Fm_NoteOnFreq's two freq writes ($A4 first, then $A0) minus the $28 key-on and the
; SCF_KEYED set. Used by Mod_ApplyVibrato (ModUpdate) each frame the modulated freq
; word changes.
; In: ix = SeqChannel/SfxChannel, d = $A4 value (block|fnumHi), e = $A0 value (fnum
; low). Clobbers: af,bc,de,hl. Preserves ix. (de = the DAC loop's $4001 is untouched
; — Fm_RoutePart/Fm_YmWrite/Fm_ReparkDac all use absolute YM addressing.)
; ----------------------------------------------------------------------
Fm_WriteFreq:
        push    de                       ; save the split fnum bytes across Fm_RoutePart
        call    Fm_RoutePart             ; b = part, c = ch-in-part
        ld      a, c
        ld      (Fm_ScratchCh), a
        ld      a, b
        ld      (Fm_ScratchPart), a
        pop     de                       ; e = $A0 val, d = $A4 val

        ; --- $A4+ch FIRST (block + fnum high) ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_FNUM_HI       ; reg = $A4 + ch
        ld      c, d                     ; data = $A4 value
        push    de
        call    Fm_YmWrite
        pop     de

        ; --- $A0+ch (fnum low) ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_FNUM_LO       ; reg = $A0 + ch
        ld      c, e                     ; data = $A0 value
        call    Fm_YmWrite
        jp      Fm_ReparkDac             ; defensive re-park ($2A); preserves ix

; ----------------------------------------------------------------------
; Fm_ChSel — compute the $28 channel-select nibble = (part<<2)|ch-in-part.
; In: ix = SeqChannel.  Out: a = chsel ($00,$01,$02,$04,$05,$06 for FM1..FM6).
; Clobbers: af, bc. Preserves de, hl, ix.
; ----------------------------------------------------------------------
Fm_ChSel:
        call    Fm_RoutePart             ; b = part, c = ch-in-part
        ld      a, b
        add     a, a
        add     a, a                     ; a = part<<2
        or      c                        ; | ch-in-part
        ret

; ----------------------------------------------------------------------
; FM writer scratch (Z80 RAM in the free sequencer block; single-threaded —
; only Sequencer_Frame (driven by the Timer-A poll in the DAC/idle loop) reaches
; the FM writer, so a static scratch is safe). Placed at SND_FM_SCRATCH (see
; sound_constants.asm).
; ----------------------------------------------------------------------
Fm_ScratchPart  = SND_FM_SCRATCH+0       ; current part (0/1)
Fm_ScratchCh    = SND_FM_SCRATCH+1       ; current ch-in-part (0..2)
Fm_ScratchLog   = SND_FM_SCRATCH+2       ; log-volume delta
Fm_ScratchMask  = SND_FM_SCRATCH+3       ; carrier mask
Fm_ScratchOp    = SND_FM_SCRATCH+4       ; Task 6: op index 0..3 (Fm_PatchTlGroup)

        ; the scratch defs must all fit inside SND_FM_SCRATCH_LEN.
        if (Fm_ScratchOp - SND_FM_SCRATCH) >= SND_FM_SCRATCH_LEN
          fatal "Fm_Scratch* exceed SND_FM_SCRATCH_LEN (\{SND_FM_SCRATCH_LEN})"
        endif
