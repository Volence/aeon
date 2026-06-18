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
; address into `de` — so de=$4001 is preserved BY CONSTRUCTION. (Sequencer_Tick
; runs inside the VBlank ISR, which also push/pops de, but we do not rely on
; that.) As belt-and-suspenders, every multi-write batch re-parks reg $2A on
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
; part = (route>=3); ch-in-part = route - (part?3:0); chsel = (part<<2)|ch.
; (Note the deliberate $03 gap in chsel — FM6/DAC would be $06, not used here.)
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
; Clobbers: af, bc. Preserves de, hl, ix.  (FM routes are 0..4; non-FM routes
; never reach here — the hooks gate on SCF_IS_FM first.)
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
; In:  ix = SeqChannel (uses sc_patch).  Out: hl = FmPatchInlineTable + patch*26.
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
        ld      de, FmPatchInlineTable
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
        ld      a, SND_REG_OP_TL         ; $40
        call    Fm_PatchOpGroup
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
; In: ix = SeqChannel.  Out: a = chsel ($00,$01,$02,$04,$05 for FM1..FM5).
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
; only Sequencer_Tick (in the VBlank ISR) reaches the FM writer, so a static
; scratch is safe). Placed at SND_FM_SCRATCH (see sound_constants.asm).
; ----------------------------------------------------------------------
Fm_ScratchPart  = SND_FM_SCRATCH+0       ; current part (0/1)
Fm_ScratchCh    = SND_FM_SCRATCH+1       ; current ch-in-part (0..2)
Fm_ScratchLog   = SND_FM_SCRATCH+2       ; log-volume delta
Fm_ScratchMask  = SND_FM_SCRATCH+3       ; carrier mask
