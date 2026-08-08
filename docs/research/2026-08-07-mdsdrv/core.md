# MDSDRV core (68k-resident driver) vs. Aeon's Z80-autonomous driver

Source read: `docs/research/external/mdsdrv/` @ commit in tree (version string
`MDSDRV0.6 230612`, `mdsdrv.68k:37`). Files read in full: `src/mdsdrv.68k` (3192 L),
`src/mdsdrv.inc`, `src/mddef.inc`, `src/mdssub.inc`, `src/mdsseq.inc`, `src/blob.68k`,
`doc/api.md`, `doc/dma.md`, `doc/mdsseq.md` (relevant sections).

Marking convention used throughout:
- **[V]** = verified by reading the actual instructions at the cited line.
- **[C]** = computed by me from source (arithmetic on `rs` offsets / cycle comments).
- **[I]** = inferred; not directly stated in code.

Aeon citations are `engine/sound/*.emp` line numbers as of this read.

---

## 0. Answers to the six scoped questions (compact, before the ranked list)

### 0.1 The track model

**[V]** `TCOUNT equ 16` (`mdsdrv.inc:31`). A track is one `TSIZE`-byte struct
(`mdsdrv.inc:129-185`). **[C]** `TSIZE = 58` bytes (asm68k `rs.w/.l` even-align;
I reproduced the whole `rsreset` chain — see §3). Layout is three zones:

| zone | offsets | contents |
|---|---|---|
| sequence control | 0-11 | note flags, channel flags, 32-bit base addr, 16-bit position, stack ptr, tick counter, last-rest/last-note length |
| channel vars | 12-24 | channel id, **request id**, instrument, instrument transpose, note, **detune (1/256 semitone)**, 16-bit portamento pitch (8.8), 16-bit last written pitch, transpose, porta speed, volume |
| mtab + pitch env + stack | 25-51 | macro table (5 B), pitch envelope (6 B), 8-word call/loop stack |
| **type union** | 52-57 | 6 bytes overlaid by FM / PSG / PCM variants |

The type union is the notable bit **[V]** `mdsdrv.inc:184-215`: `t_type rs.b 6`, then
three `rsset t_type` blocks (`T_FMSIZE`, `T_PSGSIZE`, `T_PCMSIZE`) each asserted
`<= TSIZE` at build time (`mdsdrv.inc:266-274`, using `inform 3,...`). Tracks are
*typeless*; the last 6 bytes mean different things per channel class.

**Binding to physical channels.** There is **no free binding**. **[V]**
`mds_handle_request` (`mdsdrv.68k:768-839`) walks the 16 tracks looking for the first
whose `nf_enabled|cf_suspend` bits are clear, then copies the **channel id straight out
of the song header** into `t_channel_id` (`:783-784`). Channel id is a fixed enum
(`doc/mdsseq.md:285-292`): `00-05` FM1-FM6/PCM1, `06-08` PSG1-3, `09` PSG noise,
`0a-0f` dummy/PCM2/PCM3. So the *track slot* is dynamic (any of 16), but the
*physical voice* is authored into the song data, exactly like ours. The dispatch is
`@ch_update_table` (`:606-622`), a table of 6-byte `moveq #k,chnid / bra.w handler`
entries indexed by `chnid*6` computed with three `add.b`s (`:556-560`).

### 0.2 Arbitration when BGM and SFX compete

**[V]** Four "request slots" (`RCOUNT equ 4`, `mdsdrv.inc:30`) = four priority levels.
Slot 3 is BGM, slots 0-2 are SFX (`doc/api.md:103-106`; `mds_update_fade` hardcodes
`w_volume+6` / `w_tmask+6` = slot 3, `:945/:971`). **An SFX is just a song requested on
a lower slot number** — one code path serves both.

Per slot the driver keeps: `w_request`, `w_tempo`, `w_counter`, `w_seq_step`,
`w_volume`, `w_tmask` (which of the 16 tracks belong to me) and **`w_chmask`** (which
physical channels I have claimed) — all `rs.w RCOUNT` arrays (`mdsdrv.inc:222-228`).

Arbitration runs once per frame in `mds_update_priority` (`:878-932`) and is
**channel-granular, not track-granular**:

```
	lea	w_chmask(work),tmpa0		; channel mask
	move.b	t_channel_id(twork),chnid	; check priority
	move.b	t_request_id(twork),d0
	rept	RCOUNT-1
		beq.s	@has_priority		; my slot reached first -> I win
		move.w	(tmpa0)+,d1
		btst	chnid,d1		; a higher-priority slot claims my channel?
		bne.s	@no_priority
		subq.b	#2,d0			; next request
	endr
```
(`mdsdrv.68k:890-899`, unrolled with `rept`.)

Loser handling (**not** stealing, **not** killing) — `@no_priority` (`:926-929`):

```
@no_priority
	st	t_last_pitch(twork)
	ori.w	#(nm_restore<<@nf)|(1<<(@cf+cf_background)),flag
```
`cf_background` = "track is deprioritized and plays in the background"
(`mdsdrv.inc:98-99`). The loser's **sequence keeps running** — `mds_update`'s voice
loop tests `btst #cf+cf_background,flag` *after* `mds_update_seq` and skips only the
chip-writing half (`:546-549`). No desync.

Winner-on-regain: `bclr #cf_background` and, if it actually changed, mask the pending
key-on (`:908-925`):
```
	btst	#cf_drum_mode,t_channel_flag(twork)
	bne.s	@always_mask
	cmpi.b	#5,t_counter(twork)	; <5 ticks until the next event?
	bcc.s	@voice_not_enabled	; plenty of time -> allow the re-attack
@always_mask
	bclr	#nf_key_on,t_note_flag(twork)
```
i.e. **"no off-beat drums, and no re-attack of a note that is about to end anyway."**
`nm_restore` (`mdsdrv.inc:107`) = `key_off|ins|vol|pan_lfo|fm3` — one `ori.w` re-arms a
full voice reload on the next frame.

So: **priority, yes; ducking, no; restore-on-end, yes (via background+restore-mask);
stealing, no — the loser is muted, not evicted.** Volume ducking does not exist in
MDSDRV at all.

### 0.3 FM3 special mode

**[V]** Mechanism, end to end:

1. **Arm.** `flg` command with bit 7 set (`@cmd_flg_fm3`, `:1388-1393`):
   ```
	ori.l	#(1<<(nf+nf_fm3))|(1<<(nf+nf_vol)),flag
	lsl.b	#3,@cmd			; arg bits 0-3 (op mask) -> bits 3-6
	eori.b	#$80,@cmd		; toggle bit 7 = "ch3 special enabled"
	move.b	@cmd,t_op_mask(twork)	; we're reusing MSB of t_base_addr
   ```
   `t_op_mask equ t_base_addr` (`mdsdrv.inc:136`) — the operator mask lives in the
   **unused top byte of the 32-bit sequence pointer** (68k addresses are 24-bit).
   Bit polarity: a **set** bit in 3-6 means "this track does **not** own that operator"
   (every consumer does `btst #3+n,d4 / bne skip`, e.g. `:2133-2151`).

2. **Chip enable.** `mds_fm3_update_flag` (`:2393-2403`) writes YM reg `$27`:
   `andi.b #$40,d1 / ori.b #$15,d1` -> `$15` (normal) or `$55` (CH3 special + the
   timer-A load/enable/reset bits it always keeps set).

3. **Per-operator pitch.** `mds_fm3_update_pitch` (`:2130-2171`) writes the four
   special-mode frequency register pairs, high (block/fnum-hi) byte first:
   op1 `$AD/$A9`, op2 `$AE/$AA`, op3 `$AC/$A8`, op4 `$A6/$A2` — each gated on its
   op-mask bit. The `@write_one` tail is hand-cycle-counted (`:2156-2171`).

4. **Per-operator volume.** `mds_fm3_update_vol` (`:2330-2386`) walks TL for ops
   4,2,3,1 out of **`w_fm3_tl[4]` / `w_fm3_alg` in the *driver global* work area**
   (`mdsdrv.inc:249-251`), not per track. Loaded once by whichever track last did
   `ins` on FM3 (`@cmd_ins`, `:1217-1221`).

5. **Key on/off.** `w_fm3_mask` accumulates every participating track's operator bits;
   key-on = `not.b` the track mask, OR into `w_fm3_mask`, write `$28` with
   `add.b d4,d4 / andi.b #$f2,d4` (`:2682-2689`, with the comment "assumes that bit1
   of the op_mask is unused" — ch2 = FM3).

**Cost [C]:** 6 bytes of global RAM (`w_fm3_mask`, `w_fm3_alg`, `w_fm3_tl[4]`), **zero**
extra per-track RAM (the mask is scavenged into a pointer's spare byte), and 8 register
writes per pitch update instead of 2.

**Constraints [V]:** the four tracks share ONE instrument and ONE algorithm/feedback —
only TL and frequency are independent. Panning ($B4) is per-channel, so all four share
it. Participating tracks are assigned to the dummy channels `0a-0f` (`mds_dummy_update`,
`:2965-2973`) or to PSG3 — and taking PSG3 **mutes PSG3** (`mds_psg3_update`,
`:2892-2899`, writes `$DF` then jumps to `mds_fm3_update`). `t_op_mask` bit 1 must stay 0.

### 0.4 The ~1 KB RAM claim

**[C]** I reproduced the `rsreset` chains arithmetically:

```
TSIZE  = 58 bytes/track
WSIZE  = 76 (driver header) + 16*58 (928, tracks) = 1004 bytes
```
92.4% of the budget is the 16 track structs. The claim is honest and essentially
*is* "16 tracks x 58 bytes". The build even prints it (`mdsdrv.inc:262`,
`inform 0,"Track work area size is %d bytes",TSIZE`) and hard-errors on
misalignment / union overflow (`:263-274`).

**What they gave up to hit it [V]:**
- **A 6-byte type union** instead of per-class fields (`mdsdrv.inc:184-215`).
- **An 8-word shared stack** (`TSTACK_COUNT equ 8`) doing double duty: a `pat`
  subroutine call pushes 2 bytes (`:1540-1548`), a `lp` loop pushes 4 (count byte +
  return word, `:1482-1486`). So nesting depth is a *shared budget*, not 8 of each.
- **Pointer-byte scavenging** — op mask in the top byte of `t_base_addr`; the driver
  re-entrancy guard is `bset #7,(work)` / `bclr #7,(work)`, i.e. bit 7 of the top byte
  of `w_sdtop` (`:478-479, :593`).
- **Nibble packing** — the PSG envelope's *current volume level* (low nibble) and
  *frames-1 remaining* (high nibble) share one byte, with "high nibble == 0 means wait
  for key-off" as a third meaning (`:2699-2707`); position+delay are written together
  with one `move.w` (`:2827`).
- **Word-pair writes for byte fields** — the init code writes `t_ins/t_ins_trs`,
  `t_note/t_trs`, `t_trs/t_pta`, `t_vol/t_mtab_repeat`, `t_rest_time/t_note_time`
  as single `move.w`s (`:801-813`), which is *why* the field order looks arbitrary.

**Our comparable number [C]:** `11 * SeqChannel_len(60) = 660` +
`7 * SfxChannel_len(68) = 476` = **1136 bytes** of channel state for 18 slots
(`sound_constants.emp:665, 596`), plus header/scratch/trace. Same order of magnitude,
more slots, no union. We are not overweight relative to MDSDRV.

### 0.5 Per-track expression / the "256 steps per semitone" accumulator

This is the single biggest architectural difference and I found the real code.

**Everything modulates in the log (semitone) domain as 8.8 fixed point, and the f-num
is derived exactly once, by interpolation.**

`mds_pitch_update` (`:1988-1996`) builds the 8.8 pitch:
```
	move.w	t_note(twork),d1	; reads note:dtn as a WORD
	clr.b	d1			; -> note << 8
	add.w	t_trs(twork),d1		; + transpose<<8 (and pta in the low byte)
	clr.b	d1			; kill the pta byte
	move.b	t_dtn(twork),d0		; signed value
	ext.w	d0
	add.w	d1,d0			; d0 = ((note+trs)<<8) + detune
```
So **detune is literally 1/256 of a semitone**, and transpose is the integer part of
the same number.

Portamento (`:2000-2028`) then walks that same 8.8 value toward the target:
```
	move.w	d2,-(sp)		; get step >> 8
	move.b	(sp)+,d1
	ext.w	d1
	bpl.s	@add_step
	subq.w	#2,d1
@add_step
	addq.w	#1,d1
	muls	d3,d1			; d3 = t_pta (speed)
	asr.w	#1,d1
	add.w	t_pitch(twork),d1	; d1 = new_pitch
```
i.e. glide rate is proportional to the remaining *interval*, so it is exponential-in-
frequency / linear-in-pitch — musically uniform.

Pitch envelope (`:2033-2120`) adds a 16-bit modulator in the same units
(`doc/mdsseq.md`: "Each `0x100` step is a semitone"). Nodes are 4 bytes
(init modulation word, signed delta byte, length byte) with `7fxx` = jump; an
**extended 6-byte node format is selected by bit 15 of the envelope pointer**
(`:2038 bmi.s @extended`, `:2088 bclr #15,d1`).

The conversion, `mds_get_fm_pitch` (`:1887-1907`) — this is the code the wiki alludes to:
```
mds_get_fm_pitch
	lsl.l	#8,d0
	move.w	d0,d1			; upper bits of keycode  (= fraction<<8)
	beq.s	mds_get_fm_note_pitch	; fraction 0 -> skip the multiply entirely
	swap	d0
	lea	mds_note_table(pc,d0),tmpa1
	move.b	(tmpa1),d0
	add.b	t_ins_trs(twork),d0	; freq tab displacement
	move.l	mds_fm_freq_tab(pc,d0),d3	; reads THIS entry and the NEXT as one long
	move.w	d3,d0			; d0 = next semitone's fnum
	swap	d3			; d3 = this semitone's fnum
	sub.w	d3,d0			; delta
	mulu	d1,d0			; interpolate
	swap	d0			; take the high word
	add.w	d3,d0
	rol.w	#8,d0
	add.b	mds_octave_table-mds_note_table(tmpa1),d0	; octave added
	rts
```
`mds_fm_freq_tab` (`:1872-1876`) is 45 words = 45 semitones of f-num within one
"band"; the octave comes from a byte table of `block<<3` values (`:1961-1977`). The
PSG twin `mds_get_psg_pitch` (`:1924-1940`) interpolates in the divisor domain from a
**13-entry, one-octave** table and then `lsr.w d2` for the octave.

Two side-observations on this:
- `t_ins_trs` ("instrument transpose", `:1865, :1897`) shifts *which slice of the 45-entry
  f-num table* the scale uses — a **per-instrument choice of f-num band**, documented at
  `doc/mdsseq.md:520-525`: lower band = "increased detune and reduced key scaling"
  at the cost of pitch accuracy. Deliberate exploitation of the YM2612's KS/DT behaviour.
- `mds_note_table` is *deliberately allowed to overflow into* `mds_octave_table`
  (`:1943-1949, :1970-1977`) because the octave table's bytes are all even and therefore
  valid note-table indices. Documented as intentional.

Volume/pan/PSG specifics:
- Song volume is cached in **two representations** per slot (`w_volume` is a word: raw
  byte + `mds_convert_vol`-converted byte, `:749-751`), so per-frame paths do one
  `add.b` (`:2277`, `:2844`).
- FM volume applies the song volume **only to carriers**, selected by an 8-byte
  algorithm table (`mds_fm_op_table dc.b 3,3,3,3,2,1,1,0`, `:2316-2317`) compared
  against the operator index.
- Panning ($B4) and LFO sensitivity share one byte (`t_fm_pan_lfo`), split `$C0`/`$3F`
  by the `pan`/`lfo` commands (`:1303-1331`).
- **PSG envelope has a real release phase** (`:2708-2852`): `01` = "sustain current
  volume until key-off"; on key-off the sustain flag is cleared and reading continues
  into the release segment (`@key_off`, `:2761-2766` then `@command`). `02 nn` = jump
  (treated as end after key-off). `xy` = set volume `y`, wait `x` frames — **one byte
  per envelope *segment*, not per frame**.
- There is **no dedicated vibrato**: vibrato is just a looping pitch envelope. The
  hardware LFO is exposed separately via `lfo`/`pan`.

### 0.6 Position-independent code

**[V]** Achieved by four disciplines, all visible in source:
1. **Entry via a branch island**: `mds_top` is four `bra.w`s (`:27-31`); callers
   `jsr mdsdrv+0/4/8/12` (`doc/api.md`).
2. **Every jump table is a table of `bra.w`, never a table of addresses**:
   `mds_command`'s `@cmd_table` (`:169-189`), the sequence opcode `@cmd_table`
   (`:1127-1159`), the mtab `@commands` (`:1682-1694`), the channel `@ch_update_table`
   (`:606-622`). Dispatch is `jmp @cmd_table(pc,d0)` after scaling the index by 4 (or 6).
3. **Every static table read PC-relative**: `mds_note_table(pc,d0)`,
   `mds_fm_freq_tab(pc,d0)`, `mds_psg_vol_table(pc,d1)`, `mds_fade_rate(pc,d1)`,
   `@fmcreg_slot(pc,@cmd)`.
4. **All mutable state through registers passed in**: RAM via `work`(a0) supplied by the
   caller; song data via `a_sdtop`(a2) + 16-bit offsets stored in the data
   (`movea.w 0(@tbase,@cmd),tmpa0 / adda.l a_sdtop,tmpa0`, `:1207-1215` — with the
   documented "instrument data must fit within 32k of sdtop" caveat at `:1198-1199`).
   `pea @label(pc)` + `bra.w` is used where a PC-relative "call returning elsewhere" is
   needed (`:2489`, `:2565`).

**What it buys:** the driver ships as `out/mdsdrv.bin`, a blob any project `incbin`s at
any address with any toolchain (`README.md:32-33, 84-87`) — the whole distribution model.

---

## 1. Ranked candidate takeaways

### #1 — Modulate pitch in the log domain (8.8 semitones), derive f-num by interpolation
**[WORTH TAKING] — highest value, medium-high effort, medium risk.**

**MDSDRV:** detune, transpose, portamento and pitch envelope all operate on one 8.8
semitone number (`mds_pitch_update`, `mdsdrv.68k:1988-2120`); `mds_get_fm_pitch`
(`:1887-1907`) converts once by linear interpolation between adjacent f-num table
entries with an 8-bit fraction, with a zero-fraction fast path (`:1891`). PSG likewise
(`:1924-1940`).

**We:** modulate in the **linear f-num domain**. `sc_detune` is a signed byte added
*directly to the 11-bit f-num* (`sound_fm.emp:971-987`); portamento steps the f-num by
a byte magnitude (`sound_sequencer.emp:276-436`); vibrato accumulates f-num offsets
(`sc_mod_accum`). Because f-num is linear in frequency, we need
`Fm_FnumApplyDelta` (`sound_fm.emp:883-938`, ~55 bytes resident) to renormalize across
block boundaries after **every** delta, and we carry a documented accepted edge case
(block-7 bit bleed, `sound_fm.emp:861-882`).

**Why it matters (musical, not cosmetic):** our detune/vibrato/porta units are f-num
units. Our pitch table is normalized into `[$284, $508)` (`sound_fm.emp:869`), so the
same numeric depth is worth **~2x more cents at the bottom of a block than at the top**,
and it changes discontinuously when a glide crosses a block boundary (f-num halves).
MDSDRV's authored "depth 8" means the same interval everywhere. This is exactly the
class of bug that shows up as "the vibrato sounds wrong in the high octave".

**Fits our Z80 architecture?** Yes, with one caveat: the Z80 has no multiply.
Options: (a) 8x8 shift-add multiply (~8 iterations, ~200 T-states), (b) reduce the
fraction to 4 bits (16 steps/semitone) and use 4 shift-adds, (c) a 256-byte
delta-scaling table. **[C]** Budget check: 3.579545 MHz / 59.92 Hz ≈ **59,750 T-states
per frame**; 6 FM channels x ~250 T ≈ 1500 T ≈ **2.5% of the frame**. Affordable.
Note the zero-fraction fast path makes un-modulated notes free — which is the common
case, so the real average cost is far lower.

**Risk:** every authored vibrato depth / porta rate / detune in the shipped songs
(Moving Trucks, HCZ2) is in f-num units and would need rescaling. Mitigate by keeping
the existing f-num-domain path for `MEV_NOTE_RAW` streams and adding the log-domain
path as the default for table-derived notes.

**Bonus if taken:** `Fm_FnumApplyDelta` and its block-bleed edge case can be **deleted**
— the octave falls out of the table lookup (`add.b mds_octave_table...,d0`, `:1906`).
That is a net resident-byte *saving* against a ~316 B headroom.

---

### #2 — "Drum mode": one sequence byte = a whole percussion program
**[WORTH TAKING] — high value, low-medium effort, low risk.**

**MDSDRV:** `cf_drum_mode` (`mdsdrv.inc:92`). When set, a note byte is **not** a pitch —
it indexes the song's data table and is **called as a subroutine on the track's own
stack** (`@cmd_drum_mode`, `mdsdrv.68k:1112-1119`):
```
@cmd_drum_mode
	andi.w	#$00ff,@cmd
	move.w	@trackpos,t_stack(twork,@sp)	; push current pos
	addq.b	#2,@sp
	add.w	@cmd,@cmd			; get subroutine pos
	move.w	0(@tbase,@cmd),@trackpos
```
The drum subroutine can do anything (instrument change, TL writes, pitch envelope,
detune, register writes), and terminates with `dmfinish nn` (`:1553-1557`) which pops
the return address, **sets the actual note number from its operand**, and falls into the
normal note-length read (`bra.w @cmd_tie`). Also: on regaining priority, drum-mode
tracks *always* mask a pending key-on (`:915-916`) — "no off beat drums please".

**We:** we have `MEV_DAC` for sampled drums and `MEV_PATCH`/`MEV_OPBIAS`/`MEV_REGDELTA`
for FM voice changes, but **no equivalent** — an FM percussion line must spell out the
patch/TL/pitch changes inline on every hit. Our only stream-call mechanism is a
single-level `sc_repeat_ptr/sc_repeat_count` (`sound_sequencer.emp:1499-1547`) with no
call stack at all.

**Fits our Z80 architecture?** Yes — it is a stream-format + interpreter feature, host-
agnostic. Needs: one channel flag, a 2-byte return slot (we already have `sc_repeat_ptr`,
though a real 2-entry stack would be cleaner), and a `MEV_DRUMFINISH` opcode. Roughly
30-50 resident bytes.

**Payoff:** big data-size win on FM percussion tracks (1 byte per hit instead of a
5-10 byte preamble), and it makes an "FM drum kit" a first-class authored object.

---

### #3 — Pause / resume with a single restore bitmask
**[WORTH TAKING] — high value (we have *nothing*), low effort, low risk.**

**MDSDRV:** command `0x0b set_pause` (`mdsdrv.68k:315-339`). Pause ORs
`cm_pause = cf_suspend|cf_stop` into every track of the slot; resume clears
`cf_suspend` and does one `ori.b #nm_init|nm_restore,t_note_flag(a1)` — which re-arms
key-off + instrument reload + volume + pan/lfo + fm3 in a single instruction
(`mdsdrv.inc:106-108`). Suspended tracks still count as "in use" in the free-slot search
(`:769-771`), so a suspended song can't be clobbered.

**We [V]:** `grep -rn "PAUSE|Pause|SUSPEND" engine/sound/*.emp` returns exactly one hit,
and it is an unrelated comment (`z80_sound_driver.emp:1079`). **There is no pause/resume
in our driver at all.** A pause menu today can only StopMusic (losing position).

**Fits our Z80 architecture?** Yes, and we already own every piece: `Sfx_Restore`
(`sound_sfx.emp:1123-1288`) is a complete "re-upload patch, re-apply volume/pan, re-key
the held note from `sc_base_freq`" routine. Pause = key-off all + clear a global
`SND_SEQ_ACTIVE`-adjacent flag; Resume = the `Sfx_Restore` FM/PSG bodies, run per music
channel. Estimate ~60-80 resident bytes, plus a mailbox request byte.

**Watch out:** our `Sfx_Restore` has a hard-won stopped-sequencer gate
(`sound_sfx.emp:1126-1138`) for exactly this class of bug — a paused song must not let
an ending SFX re-key a note that nothing will ever silence.

---

### #4 — Let the macro table write **channel state**, not just YM registers
**[WORTH TAKING] — high value, low effort, low risk.**

**MDSDRV:** mtab commands `$00-$3f` = *set* the track-struct byte at that offset,
`$40-$7f` = *add to* it (`mds_update_mtab`, `mdsdrv.68k:1618-1647`):
```
@var_write
	moveq	#$40,d3
	cmp.b	d3,d2
	bcs.s	@var_set
	sub.b	d3,d2
	move.b	0(twork,d2),d3
	cmpi.b	#t_fm_tl,d2
	bcs.s	@no_tl_add
	add.b	d3,d1
	bpl.s	@var_set
	svs.b	d1			; saturating clamp on overflow
	andi.b	#$7f,d1
	...
@var_set
	move.b	d1,0(twork,d2)
	cmpi.b	#t_vol,d2
	bcs.s	@next_command
	bset	#nf+nf_vol,flag		; auto-dirty anything at/after t_vol
```
Two bytes of macro data can therefore drive volume, detune, transpose, portamento speed,
or any operator TL — with automatic saturation on TL fields and an automatic
"volume is dirty, re-render" flag for anything at or past `t_vol`. `doc/mdsseq.md:596-626`
lists the useful offsets as a friendly table (`11` detune, `16` transpose, `17` porta,
`18` volume, `36-39` op TLs, `51/56/57/58/76-79` the add-forms).

**We:** `MacroTick` (`sound_sequencer.emp:1627+`) supports only four tags:
`TAG_MAC_NEXT` (yield a frame), `TAG_MAC_REG` (raw YM write, with a $2A/$2B/$24-$27
refusal guard), `TAG_MAC_LOOP`, `TAG_MAC_END`. It cannot touch `sc_volume`,
`sc_detune`, `sc_transpose`, `sc_porta_incr` or `sc_opbias`.

**Fits our Z80 architecture?** Very well — `(ix+d)` *is* an offset-indexed struct write.
A `TAG_MAC_SET`/`TAG_MAC_ADD` pair is maybe 25-35 resident bytes and instantly makes
our macro spine as expressive as MDSDRV's. **Important safety note:** unlike MDSDRV we
run the same interpreter over `SfxChannel` and `SeqChannel`, whose layouts deliberately
diverge past +56 with two load-bearing aliases (`sound_constants.emp:703-722`). An
arbitrary-offset write from a macro stream would let a music macro poke an SFX slot's
`sx_priority`. Gate the offset range at build time in the transcoder (and ideally clamp
at runtime to `<= sc_last_freq`).

---

### #5 — Sub-frame time resolution: allow more than one sequence tick per frame
**[WORTH TAKING] — medium value, low effort, low-medium risk.**

**MDSDRV** (`mdsdrv.68k:497-513` + `:546`):
```
	move.w	w_counter(work,rnum),@counter	; apply tempo
	add.w	w_tempo(work,rnum),@counter
	addq.w	#1,@counter
	move.w	w_gtempo(work),@gtempo
	clr.w	@seq_step
@sequence_tick
	cmp.w	@gtempo,@counter
	bcs.s	@tick_done
	sub.w	@gtempo,@counter
	addq.w	#1,@seq_step
	bra.s	@sequence_tick
...
	dbra	d5,mds_update_seq	; run seq_step ticks this frame
```
so a fast tempo genuinely runs 2, 3, ... sequence ticks in one 60 Hz frame. Global tempo
defaults 128 NTSC / **107 PAL** (`:87-92`), i.e. PAL correction is a single constant.

**We [V]:** `sound_sequencer.emp:147-155`, and the comment is explicit:
> "Rate = (256-mod)/256 ticks/frame, **at most 1/frame**; mod 0 never carries = tick
> every frame (the full-speed degenerate case)."

So our maximum musical resolution is one event per frame per channel — a 32nd note at
150 BPM is 0.05 s = 3 frames, fine, but fast arpeggios/rolls and any tempo above
"one tick per frame" are simply unrepresentable, and we can never author a piece whose
tick rate exceeds the frame rate.

**Fits our Z80 architecture?** Yes — replace the `jr c, .chan_done` with a loop that
adds `sc_tempo_mod` repeatedly and calls `Sequencer_Channel` once per non-carry. Cost is
a few bytes. **Risk:** a runaway tempo value could execute unbounded ticks in a frame and
blow the frame budget; bound the loop (MDSDRV does not, which is a latent hazard in
*their* code). Also note our tempo model is S3K-exact by design — this changes that
contract, so it is a deliberate divergence, not a bug fix.

---

### #6 — Fade rate as a rotating bit pattern
**[WORTH TAKING] — small value, trivial effort, no risk. Nicest micro-trick in the file.**

**MDSDRV** (`mdsdrv.68k:309-310` and `:939-942`):
```
mds_fade_rate	equ	*
	dc.b	$01,$11,$49,$55,$57,$77,$7f,$ff
...
mds_update_fade
	move.b	w_fade_rate(work),d0
	ror.b	d0
	move.b	d0,w_fade_rate(work)
	bpl.w	mds_update_priority_return	; bit7 clear after the rotate -> no step
```
Eight rates from one byte of state and three instructions. The table's population counts
are 1,2,3,4,5,6,7,8 out of 8, and the set bits are *spread* (`$49 = %01001001`,
`$55 = %01010101`) so the stepping is evenly distributed, not bursty. Result: fractional
step rates (3/8 of a frame, 5/8, ...) with no counter and no division.

Then the direction/step is computed branchlessly (`:944-957`):
```
	moveq	#1,d1
	cmp.b	d2,d3
	scs.b	d0			; 0xff if vol < target
	or.b	d1,d0			; make it +1 or -1
	add.b	d0,d2
```

**We:** `Fade_Ramp` (`sound_sequencer.emp:228-260`) uses a countdown
`SND_FADE_DELAY_CTR` reloaded from the **compile-time constant** `SND_FADE_DELAY = 1`,
stepping by the compile-time constant `SND_FADE_STEP = 2`
(`sound_constants.emp:464-465`). So we have exactly **one** fade rate, baked in.

**Fits our Z80 architecture?** Perfectly — `rrc a` / `jp p` is the direct Z80 spelling,
and `sbc a,a` gives us the branchless `scs`. Replaces the delay counter with an equal-
sized byte and buys 8 selectable rates. ~10-15 bytes net-zero.

---

### #7 — PSG envelope: explicit release phase + run-length byte format
**[WORTH TAKING (the release phase) / evaluate separately (the format)] — medium value,
low effort for the release, medium for the format.**

**MDSDRV** (`mdsdrv.68k:2696-2852`, and the state doc in the header comment
`:2699-2707`): `01` = sustain until key-off; on key-off the sustain flag clears and the
envelope **continues reading** into a release segment; `02 nn` = jump, degraded to "end"
after key-off (`:2782-2801`); `xy` = "volume y, wait x frames".

**We [V]:** `PsgEnvUpdate` (`sound_sequencer.emp:632-680`) is S3K-exact:
`$80` loop, `$81` sustain-hold (returns immediately, holds the last value forever),
`$83` full rest. **There is no release segment** — `$81` holds until the next note-on.
`FmEnvUpdate` (`:692+`) mirrors it. Bodies are one attenuation byte **per frame**
(`sound_tables_z80.emp:82-101`; e.g. `PsgVolEnv_03` is 24 bytes for 24 frames).

Two distinct takeaways here:
- **(a) Release phase [WORTH TAKING]** — a "continue past sustain on key-off" branch is
  ~15-20 Z80 bytes and gives every PSG/FM envelope a real ADSR release instead of a
  hard cut. This is a genuine expressive gap, not a size question.
- **(b) Run-length byte format [defer]** — MDSDRV's `xy` packing is 1 byte per *segment*
  vs our 1 byte per *frame*. `PsgVolEnv_03` (24 bytes) would be ~9. But our bodies are
  S3K-imported verbatim and the fidelity work (`project_hcz2_psg_envelopes`) rests on
  that. Only worth it if envelope data ever becomes a ROM problem; it currently isn't.

---

### #8 — FM3 special mode (3 extra melodic voices)
**[WORTH TAKING — but expensive] — high value, high effort, medium-high risk.**

Mechanism, cost and constraints are fully documented in §0.3 above with line cites. In
short: reg `$27` = `$40|timers`; per-op freq at `$A8-$AA`/`$AC-$AE` (+ ch3's own
`$A2/$A6` for op4); per-op TL out of a **shared** `w_fm3_tl[4]`/`w_fm3_alg`; a shared
`w_fm3_mask` accumulating key bits; 6 bytes of global RAM and 1 scavenged byte per track.

**We:** nothing — `grep -rn "FM3 special\|special mode\|fm3" engine/sound/*.emp` returns
**zero hits**. `CHROUTE_FM3 = 2` is an ordinary FM voice (`sound_constants.emp:418`).

**Fits our Z80 architecture?** The mechanism is pure YM register work, so yes in
principle. The real costs for us:
- We would need a new route class (or "virtual routes") and a shared FM3 state block
  outside `SeqChannel`, plus per-op key-mask arbitration between up to 4 channels.
- Our SFX layer steals FM3 (`SFX_VOICE_COUNT = 7` includes FM3,
  `sound_constants.emp:447`) — a steal would have to evict *all* FM3-operator tracks
  at once and restore them together. That interacts badly with `Sfx_Restore`'s
  one-channel-at-a-time model.
- Resident Z80 headroom is ~316 B (memory: wave-4 reclaim); this feature is plausibly
  100-200 B of that.

**Recommendation:** bank it as a designed feature, not a near-term parcel. The
constraint that *matters* for design: the four operator-tracks share one patch and one
algorithm — it buys you **3 extra timbre-locked voices** (great for chords, arps,
percussion clusters), not 3 independent instruments.

---

### #9 — Restore heuristic: suppress a stale re-attack
**[WORTH TAKING] — small value, trivial effort, low risk. Also a possible latent bug of ours.**

**MDSDRV** (`mdsdrv.68k:908-925`, quoted in §0.2): on regaining a channel, clear the
pending `nf_key_on` if the track is in drum mode, or if fewer than 5 ticks remain until
the next event.

**We:** `Seq_RekeySingle` explicitly leaves the arm pending during a steal
(`sound_sequencer.emp:612-613`):
```
	bit	SCF_SFX_OVERRIDE_B, (ix+sc_flags)
	ret	nz	; stolen -> no chip writes; arm stays pending
```
and `Sfx_Restore` separately re-keys the held note from `sc_base_freq`
(`sound_sfx.emp:1241-1250`).

**[I] — not verified, worth a trace:** those two mechanisms can both fire around the
same restore. If a `MEV_PITCHENV` executed while the voice was stolen, `Sfx_Restore`
re-keys `sc_base_freq` **and** the still-pending `SCF_REKEY` fires on the next
`ModUpdate`, producing two attacks a frame apart (audible as a flam), and possibly at
two different pitches. I did not trace the exact `Sfx_Frame` / `Sequencer_Frame`
ordering to confirm, so treat this as a lead, not a finding. MDSDRV's "mask the pending
key-on unless there's real time left" rule is the cheap fix either way (~8 bytes:
`ld a,(ix+sc_dur_count) / cp 5 / jr c, res SCF_REKEY`).

---

### #10 — Generic pitch envelope in place of a dedicated vibrato state machine
**[WORTH TAKING if #1 is taken; otherwise REJECT] — medium value, medium effort.**

**MDSDRV** has no vibrato opcode. A pitch envelope (`:2033-2120`) is a node list
(init-modulation word, signed delta, length) with a jump command; a looping two-node
envelope *is* vibrato, a one-shot ramp is a sweep, and the same 6 bytes of state
(`t_peg_addr/mod/delay/pos`) serves both. Envelope selection carries a format bit
(bit 15 of the pointer -> 6-byte extended nodes with a 16-bit delta and explicit
next-node index).

**We:** a dedicated S3K-style vibrato costing **11 bytes/channel**
(`sc_mod_ctrl` +42 through `sc_mod_accum` +51/+52, `sound_constants.emp:648-657`) that
can only produce one shape.

**[C]** Across 18 slots that is 198 bytes of Z80 RAM for one waveform. A generic
6-byte pitch-envelope replacement would free ~90 bytes and cover strictly more shapes.
**But**: this only makes sense *after* #1, because in the f-num domain a generic delta
envelope inherits all the block-boundary problems. Sequence them together or not at all.

---

### #11 — `t_ins_trs`: per-instrument choice of f-num band
**[REJECT for now — but record the idea]**

**MDSDRV:** `t_ins_trs` (byte +29 of the FM voice, `doc/mdsseq.md:520-525`) displaces
the note index into the 45-entry f-num table, so an instrument can be authored to sound
in a *lower* f-num range at the same pitch — "increased detune and reduced key scaling,
but the pitch accuracy will be worse". Applied at `mdsdrv.68k:1865` / `:1897`.

**We:** all pitch entries are normalized into one band `[$284, $508)`
(`sound_fm.emp:869`), which is what makes `Fm_FnumApplyDelta`'s single-step correction
sufficient.

**Reject reason:** it is a real timbral knob, but it trades away exactly the invariant
our detune/porta correctness currently rests on, and the audible payoff (KS/DT
behaviour) is subtle. Revisit only if #1 lands (log-domain modulation makes the band
choice harmless).

---

### #12 — Four request slots unifying BGM and SFX under one code path
**[REJECT — architecture already committed; note the partial overlap]**

**MDSDRV:** `RCOUNT = 4`; an SFX is a song on a lower slot; one interpreter, one track
pool, one priority rule (`mds_update_priority`, `:878-932`).

**We:** a fully separate SFX subsystem — `sound_sfx.emp` is 1760 lines with its own
`SfxChannel`, dispatch, priority queue, steal/restore, duck ramp, instance caps.

**Reject reason:** this is not a technique, it is a different driver. Adopting it would
be a rewrite of a shipped, by-ear-verified subsystem.

**Worth recording, though:** we are already *half* the way there by design —
`SfxChannel` deliberately mirrors `SeqChannel`'s field layout for the first 57 bytes so
`ModUpdate`/`Sequencer_Channel` walk both (`sound_constants.emp:538-541`, with
per-field `ensure` asserts at `:677-738`). The remaining divergence is ownership and
arbitration, not interpretation. If a future rewrite is ever on the table, MDSDRV shows
the destination is coherent.

Also note MDSDRV has **no ducking at all**, whereas we ship a ramped global music duck
(`Sfx_DuckRamp`, `sound_sfx.emp:313`; `Sfx_DeepestDuck`, `:1297`). We are ahead here.

---

### #13 — Position-independent code
**[REJECT — architecturally N/A on Z80]**

Mechanism documented in §0.6. The Z80 has **no PC-relative addressing** beyond `jr`
(±127 bytes) — no `lea (pc,d)`, no `jmp (pc,d)`, no PC-relative data reads. Our blob is
uploaded to Z80 RAM at a fixed base and every label is absolute by necessity; the
`.emp` build already derives module bases by a link-time cursor (`sound_sequencer.emp`
header). There is nothing to port.

**Sub-idea also rejected:** "table of `bra.w` instead of table of addresses". On Z80 the
equivalent (a table of `jp nnnn`) is 3 bytes/entry vs our 2-byte address table, and our
`SeqOpcodeTable` is **banked** (`seq_opcode_tab.emp:42`, `vma: $8000`) so its ROM cost
is already free. Strictly worse for us.

---

### #14 — Field packing into pointer spare bytes
**[REJECT — 68k-specific]**

`t_op_mask equ t_base_addr` reusing the top byte of a 32-bit pointer
(`mdsdrv.inc:136`); the re-entrancy guard as `bset #7,(work)` on the top byte of
`w_sdtop` (`mdsdrv.68k:478-479, 593`). Both exploit 68k's 24-bit address bus. Z80
pointers are a full 16 bits with no spare bits. Nothing to harvest.

---

### #15 — The type union at the tail of the track struct
**[REJECT — quantified as ~1 byte/slot]**

MDSDRV overlays FM/PSG/PCM variants on a 6-byte tail with build-time size asserts
(`mdsdrv.inc:184-215, 266-274`). Tempting, because our structs carry both FM-only and
PSG-only fields simultaneously.

**[C] I sized it:** FM-only fields in `SeqChannel` are `sc_patch`, `sc_last_patch`,
`sc_pan`, `sc_opbias[4]`, `sc_last_pan`, `sc_fill_master`, `sc_fill_count` ≈ **10 bytes**.
PSG-only is `sc_noise_mode` ≈ **1 byte**. A union saves `(10+1) - max(10,1) = 1 byte`
per slot = **18 bytes total**. Not worth the aliasing hazard, especially given the
`SfxChannel`/`SeqChannel` overlap already burned us once (`sound_constants.emp:703-722`).

Also note we **already union the biggest one**: `sc_env`/`sc_env_cur`/`sc_env_out`
alias `sc_psgenv*` because a channel is FM xor PSG (`sound_constants.emp:770-774`).
The idea is not new to us; it is already applied where it pays.

---

### #16 — Command-length table so handlers never advance the pointer
**[REJECT — Z80 economics are the other way]**

MDSDRV reads the operand count from `@cmd_length_table(pc,@cmd)` before dispatching, and
the fetch loop advances by it (`mdsdrv.68k:1101-1107`, `:1022-1024`); handlers read
operands with `0(@tbase,@trackpos)` and never touch the cursor. Uniform, compact
handlers.

On Z80 our `ld a,(hl) / inc hl` is 1 byte + 6 T-states for the advance, and `hl` is the
natural cursor; going table-driven would cost a 32-byte table plus per-dispatch
arithmetic to save nothing. Our handlers already commit `hl -> sc_stream_ptr` at
exactly one place each.

---

### #17 — Cycle-burn YM pacing, carrier-only volume, write-on-change
**[ALREADY HAVE — all three]**

- **Cycle-burn instead of busy-flag polling:** `@burn56` (`:2247-2251`) and inline
  cycle-annotated padding in every write loop (`:2199-2205`, `:2287-2311`), including
  two deliberately cycle-balanced branches (`@modulator: nop/nop/bra.s`, `:2308-2311`).
  We do the same via `YM_ADDR_TO_DATA_MIN_T` measured per build (`sound_fm.emp:168-186`).
- **Carrier-only volume via an algorithm table:** `mds_fm_op_table dc.b 3,3,3,3,2,1,1,0`
  (`:2316-2317`). We have `CarrierMaskTableZ` (`sound_fm.emp:9`).
- **Write-on-change:** MDSDRV's `t_last_pitch` compare (`:2550`, `:2905`). Ours is
  `sc_last_freq` / `sc_last_pan` / `sc_psgenv_out`, and it is a documented module
  contract (`sound_sequencer.emp:441-444`).

---

### #18 — Deprioritized-but-still-running tracks (`cf_background`)
**[ALREADY HAVE]**

MDSDRV `cf_background` (`mdsdrv.inc:98`, gated at `mdsdrv.68k:548-549`) == our
`SCF_SFX_OVERRIDE` (`sound_constants.emp:804`), gated in `ModUpdate`
(`sound_sequencer.emp:451-452`) and at every note/opcode chip-write site
(`:612, :1113, :1315, :1432, :1666, :1758, :1777, :1787, :1801`). Same design, same
rationale (cursor advances, chip writes suppressed, no desync). Our version is
*more* thorough — MDSDRV gates in one place, we gate per opcode.

Likewise MDSDRV's `nm_restore` == our `Sfx_Restore`, and ours does strictly more
(patch re-upload, pan shadow resync, exact-frequency re-key from `sc_base_freq`,
stopped-sequencer guard, no-music-underneath silencing).

---

## 2. Other things that surprised me (no action, recorded for the file)

1. **`s<cc>` as arithmetic.** `scs.b d0 / or.b d1,d0` turns a compare into ±1
   (`:948-951`); `svs.b d1 / andi.b #$7f,d1` is a saturating clamp on signed overflow
   (`:1448-1450`, `:1635-1637`). Z80's `sbc a,a` is the same trick and we already use it
   (`sound_fm.emp:981-983`).
2. **`dbcs` as a dual-exit loop.** `dbcs tnum,@next_track` (`:839`) ends the track
   allocation loop on *either* "ran out of slots" or "allocated all `tcount`".
3. **Macro-table "end" implemented as an infinite hold, not a stop** (`:1700-1711`):
   sets delay to `$FF` and position to `pos-1` so the same command re-executes forever,
   keeping the table address live for restart on the next note. Avoids an "armed but
   idle" state entirely.
4. **The fade-in rate is smuggled into the sound ID.** `mds_request` takes a plain
   number; adding `$2000 + (rate<<10)` selects fade-in (`:670-688`, `doc/api.md:44-47`).
   Zero API surface for a feature.
5. **Two overlapping tables that are safe by construction** — `mds_note_table` overruns
   into `mds_octave_table`, which is fine because every octave-table byte is an even
   number and therefore a valid note index (`:1943-1949`, `:1970-1977`).
6. **The Z80 side is *only* a PCM mixer** with a DMA-protection handshake: the 68k
   rewrites the Z80's interrupt vector byte at `$0038` between `$08` (EX AF,AF' =
   protected) and `$C9` (RET = unprotected) to toggle DMA protection at runtime
   (`:412-420`). Self-modifying the *other* CPU's code as a mode switch.
7. **Their own doc admits a foot-gun we should not copy**: `@cmd_ins`'s
   "instrument data must fit within 32k of w_sdtop due to the `movea.w`"
   (`:1198-1199`) — a sign-extending 16-bit offset used as a base-relative pointer.
8. **`mds_z80_wait_fm`** (`mdssub.inc:114-127`) — if the Z80 is mid-FM-write, the 68k
   *releases* the bus, burns ~96 cycles with a `movem.l d0-d4` push/pop pair as a
   calibrated delay, and retries. Not applicable to us (single writer), but a nice
   pattern for any two-master YM setup.

---

## 3. Verification notes

- `TSIZE = 58` and `WSIZE = 1004` are **[C]**, computed by replaying the `rsreset`/`rs`
  chains from `mdsdrv.inc:129-257` under asm68k's even-alignment rule for `rs.w`/`rs.l`.
  Cross-check that gives me confidence: the driver's init code writes `t_ins`(14),
  `t_note`(16), `t_trs`(22), `t_vol`(24), `t_rest_time`(10) and `t_stack_pos`(8) as
  **word** pairs (`mdsdrv.68k:801-813`) — every one of those offsets is even under my
  computation, and `mdsdrv.inc:263` build-errors if `TSIZE` is odd (58 is even).
- Our sizes are read directly from the source's own asserts:
  `SeqChannel_len == 60` (`sound_constants.emp:667`),
  `SfxChannel_len == 68` (`:598`), `CHROUTE_COUNT == 11` (`:429`),
  `SFX_VOICE_COUNT = 7` (`:447`).
- The T-state frame budget (59,750) is **[C]** from 3.579545 MHz / 59.92 Hz.
- Item #9's double-attack concern is **[I]** — I did not trace `Sfx_Frame` vs
  `ModUpdate` ordering. Everything else marked [V] was read as instructions.
- I did **not** read `src/mdssub.z80` (the Z80 PCM mixer, 1692 lines) or
  `src/mdlib.68k`/`mdinit.68k`/`mdbug.68k` (test-ROM support, not driver core) beyond
  what the scope required.
