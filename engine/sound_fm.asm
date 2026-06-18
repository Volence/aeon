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
;   eff_TL = clamp7(patch_TL[op] + sc_opbias[op])
; TL is 7-bit attenuation, so the sum SATURATES at $7F (silent). sc_opbias is a
; per-note brightness/level bias LATCHED here at patch load (the Zyrinx key-on
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
        ; --- data = clamp7(patch_TL[op] + sc_opbias[op]) ---
        ld      a, (hl)                  ; patch base TL for this op
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
        ld      a, c                     ; a = base TL
        add     a, (hl)                  ; + sc_opbias[op] (signed-ish bias)
        jr      c, .clamp                ; 8-bit overflow -> saturate silent
        cp      SND_FM_TL_MAX+1          ; result > $7F ?
        jr      c, .tl_ok
.clamp:
        ld      a, SND_FM_TL_MAX         ; clamp to $7F (silent)
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
        ; carrier: effective_TL = min($7F, base_TL + log)
        ld      a, (hl)                  ; base TL for this op
        push    hl
        ld      hl, Fm_ScratchLog
        add     a, (hl)                  ; + log delta (may carry past 8 bits)
        pop     hl
        jr      c, .clamp                ; 8-bit overflow -> silent
        cp      SND_FM_TL_MAX+1          ; result > $7F ?
        jr      c, .tl_ok
.clamp:
        ld      a, SND_FM_TL_MAX         ; clamp to $7F (silent)
.tl_ok:
        ld      c, a                     ; data = effective TL
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
; Fm_NoteFromTable — key a note from the PER-SONG fnum (pitch) table.
; In: ix = SeqChannel, a = note index (an ABSOLUTE index 0..PITCHTAB_MAX_IDX into
;     the 132-entry chromatic fnum table — NOT the engine's FmPitchTableZ note
;     numbering). This is the Phase-3 pitch-envelope renderer path used by
;     ModUpdate; the per-song table is the exact Zyrinx Moving-Trucks fnum table.
;
; TABLE: TWO PARALLEL PAGES (sound_constants.asm) — A4 page first (PITCHTAB_COUNT
; bytes), then the A0 page. So for index i: $A4 = base[i], $A0 = base[COUNT+i].
; base = Snd_PitchTabPtr (per-song) when nonzero, else MovingTrucks_PitchTable
; (the inline engine-default table in this blob).
;
; PITCH: idx = clamp_0_83(note + sc_transpose), with sc_transpose SIGNED and the
; result SATURATING to 0..PITCHTAB_MAX_IDX (the RE's $1100/$1200 clamp behavior:
; below 0 -> 0, above $83 -> $83). The add is done in signed 16-bit so a large
; negative transpose can't wrap. Then $A4/$A0 are looked up and Fm_NoteOnFreq
; writes them + keys on.
; Clobbers: af, bc, de, hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_NoteFromTable:
        ; --- idx = clamp_0_83(note + sc_transpose) (signed) ---
        ld      l, a
        ld      h, 0                     ; hl = note index (0..$83, positive)
        ld      a, (ix+sc_transpose)     ; signed per-pattern transpose
        ld      e, a
        add     a, a                     ; CF = sign bit of transpose
        sbc     a, a                     ; a = $FF if transpose<0, else $00
        ld      d, a                     ; de = sign-extended transpose
        add     hl, de                   ; hl = note + transpose (signed 16-bit)
        bit     7, h                     ; result negative? (h >= $80)
        jr      z, .nonneg
        ld      hl, 0                    ; < 0 -> clamp to 0
        jr      .clamped
.nonneg:
        ld      a, h                     ; hl is 0..$102 here
        or      a
        jr      nz, .clamp_hi            ; high byte set -> > $83 -> clamp
        ld      a, l
        cp      PITCHTAB_MAX_IDX+1
        jr      c, .clamped              ; l <= $83 -> in range
.clamp_hi:
        ld      l, PITCHTAB_MAX_IDX      ; > $83 -> clamp to $83
.clamped:
        ld      c, l                     ; c = clamped idx (0..$83); preserved below

        ; --- resolve table base: per-song ptr, else engine default ---
        ld      hl, (Snd_PitchTabPtr)
        ld      a, h
        or      l
        jr      nz, .have_base
        ld      hl, MovingTrucks_PitchTable
.have_base:
        ; --- $A4 = base[idx] ---
        ld      b, 0                     ; bc = idx
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
        ; hl = &FmPitchTableZ[pitch] = base + pitch*2
        ld      l, a
        ld      h, 0
        add     hl, hl                   ; pitch*2 (word entries)
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
        push    de                       ; save the split fnum bytes

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

        ; --- KEY ON: $28 = $F0 | chsel, ALWAYS via part I ---
        call    Fm_ChSel                 ; a = chsel = (part<<2)|ch
        or      SND_FM_KEYON_OPMASK      ; $F0 | chsel (all 4 ops on)
        ld      c, a                     ; data = key-on byte
        ld      a, SND_REG_KEY_ONOFF     ; reg = $28
        ld      b, 0                     ; key on/off is GLOBAL -> part I
        call    Fm_YmWrite

        set     SCF_KEYED_B, (ix+sc_flags)
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
