# Batman & Robin (Genesis) Z80 Sound Driver — Complete Reverse Engineering

**Subject:** `batman_z80.bin` — 6181-byte ($1825) hand-written Z80 sound driver
(Jesper Kyd, Clockwork Tortoise / The Adventures of Batman & Robin, 1995).
**Z80 base address:** `$0000`. **Stack:** `SP=$1FFE`.
**Method:** Static disassembly via `z80dasm.py`, re-run from clean entry points,
plus hand-decoding of embedded data tables. Addresses cited are Z80-space.

Legend: **[CONFIRMED]** = decoded from bytes/instructions. **[INFERRED]** = strong
deduction from surrounding logic. Where a value is stated without a tag it is directly
read from the listing.

---

## 0. Executive Summary

This is a **custom, hand-written, Timer-B-driven FM+DAC driver** with **no SMPS lineage
and no PSG usage whatsoever**. It is unusually sophisticated for 1995:

- **Sub-frame timing.** Driven by YM2612 **Timer B** (reg $26=$72, $27 load+enable),
  not VBlank. The main loop continuously re-arms Timer B and does work between overflows.
- **Cooperative DAC streaming interleaved with FM.** A single cooperative loop feeds DAC
  samples byte-by-byte with a per-sample software rate delay, breaking out *only* when
  Timer B overflows to service FM, then resuming the sample mid-stream. This is a
  software scheduler, not an interrupt handler.
- **14-bit linear pitch space** with a 128-entry frequency table → real **portamento
  (glissando) via 16-bit fixed-point division**, smooth pitch slides, and vibrato with
  sub-semitone resolution.
- **Two parallel data streams per channel**: a *note stream* and an independent
  *modulation/control stream* (pitch envelopes, vibrato shapes, per-op volume).
- **Software TL volume envelopes** layered on top of the hardware patch, applied
  per-operator every frame, with carrier/operator selection driven by the algorithm.
- **Hardware LFO** (reg $22) enabled per-song; **$B4 AMS/FMS** sensitivity in every patch.
- **Mailbox = direct RAM injection.** The 68k does not send opcode bytes; it writes
  whole channel-start records and DAC-request records directly into Z80 RAM, which the
  driver latches on its next pass. Zero command-parser overhead.

The "evolving / atmospheric" Jesper Kyd sound comes from: (1) the dual-stream
control track running independent pitch + volume + vibrato envelopes per voice, (2)
true portamento between notes via fixed-point division, and (3) hardware LFO with
per-patch FMS/AMS — all running at sub-frame Timer-B rate.

---

## 1. Memory Map

### Code/data regions (in ROM blob, $0000–$1824)
| Range | Contents |
|---|---|
| `$0000–$0094` | Init + main scheduler loop + DAC feed loop |
| `$0095–$00F5` | Scheduler flag + **DAC engine live variables** (see §3) |
| `$00F6–$012F` | FM update **even half** (entry `Update_FM_A`) |
| `$0130–$01D8` | FM update **odd half** (`Update_FM_B`) + channel dispatch + fade-out snapshot |
| `$01D9–$01FD` | `SetBank` — ROM bank select via `$6000` (see §2) |
| `$01FE–$0316` | `Channel_PerFrame` — arpeggio, software volume table, **pitch-slide accumulator**, **vibrato table** |
| `$0317–$0A73` | `Channel_Sequencer` — note-duration ticking + **command dispatch** + all command handlers |
| `$0A74–$0B36` | Math kernels: fraction-multiply (`$0A74`), **portamento delta** (`$0A99`), 2's-comp (`$0B11`), **16-bit ÷ 16-bit** (`$0B19`) |
| `$0B37–$0B3C` | Portamento scratch (cur/target freq words + register bytes) |
| `$0B3D–$0B51` | `Set_LFO` — writes reg $22 from `$0E5E` |
| `$0B52–$0E1B` | `Channel_Load` — **note-on, instrument load, key on/off, per-op TL volume write** |
| `$0E1C–$0E5C` | `Write4Regs` — write 4 operator registers stepping +4 |
| `$0E5D–$0EFF` | **Global / song-header variables** (LFO, freq-base ptr, instrument table ptr, etc.) |
| `$0F00–$0FFF` | F-number **high-byte** lookup (256 entries) |
| `$1000–$10FF` | F-number **low-byte** lookup (256 entries) |
| `$1100–$11FF` | Identity/clamp ramp (special pitch mode, positive offset) |
| `$1200–$12FF` | Identity/clamp ramp (special pitch mode, negative offset) |
| `$1300–$13FF` | **128-entry 16-bit frequency table** (linear pitch space, BE words) |
| `$1400–$14FF` | **Software volume→attenuation table** (runtime-computed; zero in blob) |
| `$1480–$16D3` | **6 channel-state structures** working copies (stride $67) |
| `$16E0–$16F4` | **DAC request staging block** (latched into $00ED–$00F5) |
| `$16F5–$17E9` | `Service_Top`: fade-out engine + DAC latch + **channel-start mailbox scanner** |
| `$17EA–$1822` | **68k→Z80 mailbox** (6× channel-start records) |
| `$1823–$1824` | `di / halt` (idle trap / safety) |

### The 6 channel structures
Init at `$0006–$0018` sets byte 0 of each to `$FF`. Stride **$67 (103) bytes**:
`$1480, $14E7, $154E, $15B5, $161C, $1683`.
(Note: the prompt's addresses `$14D1…` are *+$51 into* these; the true struct base is
`$1480`. The dispatch in `Update_FM_B` uses `$1480`-based pointers — confirmed.)

The driver maps these to **YM2612 channels 1–6**: channels 0–2 → part I
(`$4000/$4001`), channels 3–5 → part II (`$4002/$4003`); `Channel_Load` adds 2 to the
register and switches `ix` to `$4002` when `b≥3` (`$0C0E`, `$0C48`, `$0CEE`). Channel 5
(index 5, struct `$1683`) is the **DAC channel** when sample playback is active — its FM
update is skipped while `$00EB=$80` (`$0139`).

---

## 2. Init & Bank Switching

### Init ($0000–$0049) [CONFIRMED]
```
di
ld sp,$1FFE
ld a,$FF ; mark all 6 channel structs inactive (byte 0 = $FF)
ld ix,$4000
(ix+0)=$2B, (ix+1)=$00   ; YM $2B = $00  -> DAC disabled
(ix+0)=$26, (ix+1)=$72   ; YM $26 = Timer B period = $72
(ix+0)=$27, (ix+1)=$2A   ; YM $27 = $2A -> load Timer B + enable + reset-on-overflow flag
```
Each YM write busy-waits on `bit 7,(ix+0)` (the $4000 status busy bit) first — correct
YM2612 access discipline. The driver is **Timer-B-paced**: `$2A` = enable Timer B + set
its overflow flag; the scheduler polls `bit 1,(ix+0)` (Timer B overflow) to know when a
sub-frame tick has elapsed.

### SetBank `$01D9` [CONFIRMED — answers question #2]
The DAC path and several sequencer commands call `$01D9` with `a` = a **ROM bank id**
(from `$00EC` for DAC, or per-stream bank fields). It compares against the cached bank
`$0E5F`; if unchanged it returns. Otherwise it writes the bank serially to the **Z80 bank
register at `$6000`**, one bit per `ld (hl),a` after `srl a` — the classic Mega Drive
Z80 9-bit bank-latch protocol (writes bit 0 nine times). After loading it writes `$00` to
clear, then caches the new bank in `$0E5F`. So `$00EC` selects which 32 KB window of the
68k ROM is visible at Z80 `$8000–$FFFF`, where the **sample data and music data live**.
This is what makes the cooperative DAC loop able to stream multi-bank samples.

---

## 3. The DAC Engine (cooperative scheduler) — verified & extended

### Live variables ($00EB–$00F5) [CONFIRMED]
| Addr | Meaning |
|---|---|
| `$00EB` | sample-active flag (`$80`=playing) |
| `$00EC` | sample ROM **bank** (→ SetBank) |
| `$00ED` | **pitch / rate** (inner `djnz` count, `ld c`) |
| `$00EE/EF` | current sample **pointer** (hl) |
| `$00F0/F1` | current sample **length** (de) |
| `$00F2/F3` | **loop pointer** |
| `$00F4/F5` | **loop length** |

### Main scheduler loop ($004A–$0094) [CONFIRMED]
```
$004A: toggle $0095; even tick -> call Update_FM_A ($00F6); odd -> Update_FM_B ($0130)
$005C: YM $27 = $0A   ; re-arm Timer B WITHOUT load? ($0A = enable+overflow-reset, no load bit)
$006E: read $00EB; YM $2B = that  ; DAC-enable register tracks the sample-active flag
$007E: if $00EB==$80 -> jp $0096 (enter DAC feed); else clear $00EB, wait Timer B, loop
```
So **every sub-frame** the driver runs *one half* of the FM engine, re-arms Timer B, and
sets reg $2B (DAC enable) to mirror whether a sample is active.

### DAC feed loop ($0096–$00E7) [CONFIRMED + clarified]
```
$0096: YM $B6 = $C0      ; channel-6 stereo = L+R (DAC panning)
$00A4: SetBank($00EC)
$00AA: hl = $00EE (ptr), de = $00F0 (len)
$00B1: busy-wait status bit, then YM addr=$2A (DAC data port)
$00BC: c = $00ED (pitch)
$00C0: a=(hl); inc hl; YM $2A data = a ; b=c; djnz   <- per-sample RATE DELAY
$00C8: dec de; if de==0 -> check loop ($00F4 len); if loop len 0 -> stop (jp $0082)
       else reload hl=$00F2 (loop ptr), de=$00F4 (loop len)
$00D9: bit 1,(ix+0) Timer B overflow? no -> jp $00C0 (keep feeding)
       yes -> save de,hl back to $00F0/$00EE and jp $002A (go service FM, re-arm Timer B)
```
**This is the signature trick:** DAC playback is a *resumable coroutine*. FM is serviced
in the gaps between DAC sample writes whenever Timer B fires; the sample pointer/length
are checkpointed and restored, so a long sample plays continuously across hundreds of FM
sub-frames with **zero clicks**. Hardware-accurate sample-rate control comes from the
`b=c / djnz` busy-delay (`c` = `$00ED`). Loop support is full (loop ptr + loop len).

---

## 4. FM Update Split (load balancing) [CONFIRMED]

`$004A` alternates `Update_FM_A` ($00F6) on even ticks and `Update_FM_B` ($0130) on odd
ticks — splitting the 6-channel workload across two Timer-B periods to stay inside the
sub-frame budget.

**`Update_FM_A` ($00F6):**
1. `call $16F5` — `Service_Top` (fade engine + DAC latch + mailbox scan; §7).
2. `call $0B3D` — `Set_LFO` (reg $22 from `$0E5E`).
3. Copy `$0E67` → four addresses `$0D45/$0D71/$0D9D/$0DC5` (patches the **immediate
   operands** of four TL-write sites — a self-modifying-code optimization selecting which
   operators get software volume, based on the current algorithm). **[CONFIRMED self-mod]**
4. `Channel_Load` (`$0B52`) for channels 0–3 (`iy` = struct, `b` = channel id).

**`Update_FM_B` ($0130):**
1. `Channel_Load` for channel 4; channel 5 only if no DAC active (`$00EB≠$80`).
2. For all 6 channels: if `(ix+31)≠0` (channel enabled) → `call $0317`
   (`Channel_Sequencer`) then `call $01FE` (`Channel_PerFrame`).
3. `$01A9`: tempo/global counter at `$180F`; when it hits 6, snapshots the 6 channels'
   key bytes into `$1810+` (a state-readback block the 68k can poll). **[INFERRED:
   sync/heartbeat for 68k]**

---

## 5. Per-Channel Math & Pitch (the "evolving texture" core)

### Frequency table `$1300` (128× BE 16-bit) [CONFIRMED]
A **linear pitch ladder** (not raw YM F-num/block). Values rise then wrap at index 36 to
`$8000` and repeat every 12 entries (one octave = 12 entries = 24 bytes). The high/low
bytes are mirrored into `$0F00`/`$1000` for fast single-byte lookup. Conversion to
YM2612 block/F-num is done by `$0A99` (`srl h … sub $08` octave-shifting). Sub-semitone
resolution gives smooth slides & vibrato.

### `$0A74` fraction-multiply [CONFIRMED]
8-round shift-add: `hl = a × de` building a fractional interpolation — used to scale
vibrato/volume table entries by an amount, and to interpolate between frequency entries.
No `mulu`.

### `$0A99` portamento delta [CONFIRMED]
Computes the signed frequency **difference** between current note (`$0B37`/`$0B38`) and
target (`$0B3A`/`$0B3B`), normalizes the octave (`srl h / sub $08` loop), then divides by
the glide duration to produce a per-frame increment stored in `(ix+68/69)`. Handles both
directions (2's-complement via `$0B11`).

### `$0B19` 16÷16 fixed-point division [CONFIRMED]
Classic 16-iteration restoring division (`rl c / rla / adc hl,hl / sbc hl,de / ccf`).
Divisor = `(ix+72/73)` (glide length). This produces the **portamento slope** — i.e. real
glissando, not stepped pitch. No `divu`.

### Pitch-slide accumulator (`$029C–$02CC` inside `$01FE`) [CONFIRMED]
```
(ix+66/67) += (ix+68/69)        ; 16-bit fractional pitch accumulator
hl = (ix+66/67) >> 5            ; scale
(ix+5) = (ix+64) | h ; (ix+6)=l ; -> YM A0/A4 frequency output for this channel
```
The portamento target counter `(ix+70/71)` increments until it equals `(ix+72/73)`, at
which point the slide latches to the destination note. **This is true legato/portamento.**

### Vibrato / pitch-LFO table (`$02F5`, when modulation flag `(ix+44)=0`) [CONFIRMED]
```
h = $11 (or $12 if (ix+48) negative)   ; pick +/- ramp page
l = (iy+49) + (ix+48)                  ; index by modulation phase
a = table -> index into $0F00/$1000 freq split -> (ix+5/6)
```
A **table-driven pitch modulator**: an independent control stream advances `(iy+49)`
(phase) and `(ix+48)` (depth/offset), generating evolving pitch contours (vibrato,
swells, sweeps) without touching the note stream. This is the mechanism behind Kyd's
shifting/atmospheric pads.

### Arpeggio / note-table (`$01FE`, `$0226–$0299`) [CONFIRMED]
`(ix+55)` indexes a small per-note table `(iy+56)` (modulo `(ix+54)` length). Each step
selects a transpose value that is added to the base note before frequency lookup,
clamped to `$00..$7F`, then resolved through `$13xx`/`$14xx` tables into a final F-num and
a software-volume value. This gives **fast arpeggio chords** (the classic Genesis
"chord = rapid arpeggio on one channel" trick) and per-step volume.

---

## 6. Sequencer / Data Format (answers question #3)

### Two streams per channel [CONFIRMED]
- **Control/modulation stream**: pointer `(ix+36/37)`, loop `(ix+38/39)`, ticked by
  `Channel_Sequencer` `$0317`. Drives pitch envelopes, vibrato, per-op volume.
- **Note stream** (the main music): pointer `(ix+24/25)` region, advanced by the note
  duration counter.

### Note-duration ticking (`$0317`) [CONFIRMED]
`(ix+33) -= $10` each frame; on borrow, reload from `(ix+32)` and step a wait/delay
counter `(ix+34)`; when expired, fetch next stream byte at `$0339`:
- **byte ≥ $80 (negative)** → it is a **rest/wait count** (`$034B`: store, `inc (ix+34)`).
- **byte 0–$7F** → **command index** → `iy=$0660+byte`, `push de / ret` (jump to handler).

### Note-on path (`$03D0` → `$0A68`) [CONFIRMED]
The main note dispatch `$03D0` reads a byte: if **negative ($80–$FF)** it is a **note-on**
(handler `$0A68`: stores note in `(ix+34)`/`(ix+36/37)`); if **positive ($00–$7F)** it is a
**command** → `iy=$0860+byte`, dispatch.

There are **two command jump tables**, selected by which stream is parsing. Crucially,
the **same low command byte means different things in the note stream vs the control
stream** — verified by decoding both targets.

### NOTE-stream command table `$0860` (dispatch `iy=$0860+byte`) [CONFIRMED]
| Byte | Target | Function (decoded) |
|---|---|---|
| $80–$84 | $600A | (reserved → note handler) |
| $85 | $05AD | **Arpeggio/note-table, 1 entry** → fields 56–60 ($38–$3C), set modulation-active, glide target |
| $86 | $05F7 | Arpeggio table, 2 entries |
| $87 | $060E | Arpeggio table, 3 entries |
| $88 | $0575 | Arpeggio table, 4 entries |
| $89 | $0590 | Arpeggio table, 5 entries |
| $8A | $03C9 | Set field `(ix+7)` (key-scaling / detune param) |
| $8B | $1823 | **Halt** (end-of-track → di/halt safety) |
| $8C | $0627 | **Instrument / patch change** (loads patch from `$0E65` table, bank `$0E64`) |
| $8D | $03A1 | Set `(ix+20)=1` (enable a per-channel flag) |
| $8E | $0447 | **Reset envelope / note-init** |
| $8F | $03A7 | Set `(ix+63)=0` (clear modulation/portamento retrigger) |
| $90–$97 | $0369–$039A | **Set LFO group** — sets `$0E5E` = $08..$0F → reg $22 (LFO on + freq 0–7) |
| $98–$9B | $03E8–$0406 | **Pitch-envelope presets** (`(ix+17)`=rate $F8/$38, `(ix+19)`=shape $00/$80/$40/$C0) |
| $9C–$9F | $03AD–$03C2 | **Per-operator TL-offset set** (`(ix+9/11/13/15)`) |

Each arpeggio-table command ($85–$89) also resets the portamento accumulator
(`(ix+70/71)=0`), sets `(ix+44)=1` (modulation active), and reads a glide target byte
that is run through `$0A74` and `>>4` into `(ix+72/73)` — i.e. **a note can carry an
arpeggio pattern AND a portamento target simultaneously.**

### CONTROL-stream command table `$0660` (dispatch `iy=$0660+byte`) [CONFIRMED]
| Idx | Target | Function |
|---|---|---|
| 0 | $04FD | **Volume envelope, 1 value** → fields 49–53 ($31–$35), length `(ix+54)` |
| 1 | $0524 | Volume envelope, 2 values |
| 2 | $053D | Volume envelope, 3 values |
| 3 | $0558 | Volume envelope, 4 values |
| 4 | $04DE | Volume envelope, 5 values |
| 5–9 | $05AD–$0590 | (shared with note table) arpeggio/note-table 1–5 entries |
| 10 | $03C9 | set `(ix+7)` |
| 11 | $1823 | halt |
| 12 | $0627 | instrument change |
| 13 | $03A1 | flag set |
| 14 | $0410 | `call $0447` then resume note stream — **envelope retrigger** |
| 15 | $1823 | halt |

So the control stream primarily drives **per-operator software volume envelopes**
(fields 49–53, applied to TL each frame), while the note stream drives **arpeggio
tables + portamento + patch/LFO changes**.

---

## 7. 68k → Z80 Mailbox (answers question #3, part 2)

There is **no single command byte**. `Service_Top` (`$16F5`, falls through to `$17A0`)
runs every even tick and does:

### DAC request latch ($1754–$179F) [CONFIRMED]
If `$16F4 == $80` (DAC-request flag, set by 68k), copy the staging block `$16EA–$16F3`
into the live DAC variables `$00ED–$00F5` (pitch, bank, ptr, len, loop ptr, loop len),
clear `$16F4`, and set `$00EB=$80` (start playing). **The 68k triggers a sample by writing
the staging block + flag; the Z80 latches it atomically on its next pass.**

### Channel-start mailbox scan ($17A0–$17E9) [CONFIRMED]
Scans **6× 6-byte records at `$17EA`** (one per channel). For any record whose first byte
is nonzero:
- set channel `(ix+0)=$FF` (force re-init), copy patch id `(ix+1)`,
- decode a 3-byte **banked data pointer**: `(ix+2)` = bank high bit, `(ix+3)=$80|bankhi`
  (maps pointer into Z80 `$8000+` window), `(ix+4)` = pointer low,
- clear the record (write `$00`) so it fires once.

**So the 68k starts music/SFX by writing a channel-start record (patch + banked song
pointer) into `$17EA+`, and triggers DAC by writing the `$16EA` staging block.** This is a
zero-parse, direct-injection mailbox — faster than any opcode protocol.

### Fade-out engine ($16F5–$1753) [CONFIRMED]
If `$180E≠0`, walk all carrier TL registers ($40-block on both YM parts) toward `$7F`
(silence) via `$1724` — a **hardware fade-out** that ramps attenuation directly.

---

## 8. Instrument / Patch Format (answers question #5)

`Channel_Load` ($0B52) on a note-on with new patch (`$0BAF`) reads the patch via
`(iy+2)` bank + `(iy+3/4)` pointer (SetBank-relocated) and streams the full FM register
set in this order (verified by register-arithmetic simulation):

```
$30,$34,$38,$3C   DT/MUL   (4 operators)   <- via Write4Regs ($0E1C)
$40,$44,$48,$4C   TL       (op1 block)     <- written by SOFTWARE-VOLUME path ($0D29+)
$50,$54,$58,$5C   RS/AR
$60,$64,$68,$6C   AM/D1R(D1R+AM bit)
$70,$74,$78,$7C   D2R
$80,$84,$88,$8C   D1L/RR
$B0               FB/ALGO
$B4               L/R/AMS/FMS  (stereo + LFO sensitivity)
```
Then key-on (`$28` with operator mask `b|$F0`). **No $90–$9C (SSG-EG) writes — confirmed
absent.** No Ch3 special mode ($A8–$AC). The patch includes **$B4**, so every instrument
carries its own stereo panning and **LFO AMS/FMS sensitivity** — central to the lush,
modulated pads. The TL ($40 block) is **not** copied verbatim; it is computed each note
as `patch_TL XOR $7F + channel_op_volume, clamped` (`$0D3C`/`$0D68`/etc.) so the software
volume envelope and the patch attenuation combine. Which operators receive volume is
selected by the algorithm via the self-modifying `add a,$00/$04` operands patched at
`$0D44`/`$0D70`/`$0D9C`/`$0DC4` (set in `Update_FM_A` from `$0E67`).

---

## 9. PSG / SN76489 (answers question #4)

**Not used at all.** No write to `$7F11` (PSG port) exists anywhere in the blob; no PSG
attenuation/noise tables. The driver is **pure 6-channel FM + 1 DAC** (DAC stealing FM
channel 6 while active). No PSG-as-PCM, no noise percussion. Percussion is DAC samples.

---

## 10. LFO / Ch3 / Timer-A / SSG-EG (answers question #6)

- **Hardware LFO (reg $22):** Enabled per-song. `Set_LFO` ($0B3D) writes `$0E5E` to reg
  $22 every even tick; commands $90–$97 set `$0E5E` to $08–$0F (LFO-on + frequency 0–7).
  Combined with per-patch $B4 FMS/AMS, this is the main "movement" source. **[CONFIRMED]**
- **Ch3 special mode:** Not used (no $27 bit-6 set after init; init writes $2A/$0A only).
- **Timer A:** Not used ($24/$25 never written; only Timer B drives timing).
- **SSG-EG ($90–$9F):** Not used.
- **DMA awareness:** None needed — driver never touches the 68k bus or VDP; the cooperative
  Timer-B loop is immune to 68k DMA stalls because it never waits on the 68k.

---

## 11. Channel Structure Field Map (stride $67, base $1480)

Offsets are `(ix+n)` decimal as used by the code. **[CONFIRMED]** unless noted.

| Off | Hex | Field |
|---|---|---|
| 0 | $00 | active/state byte ($FF=needs init, else live) |
| 1 | $01 | patch id / countdown (note-on delay) |
| 2–4 | $02–$04 | banked **note-stream pointer** (bank, ptr hi/lo) |
| 5–6 | $05–$06 | **YM frequency output** (A4/A0 — written to hardware) |
| 7 | $07 | key-scaling / detune param (cmd $8A) |
| 9,11,13,15 | $09,$0B,$0D,$0F | per-operator **TL volume offsets** (cmd $9C–$9F) |
| 8,10,12,14 | $08,$0A,$0C,$0E | per-operator **live software volume** |
| 16,18 | $10,$12 | pitch-envelope state (rate/shape staging) |
| 17,19 | $11,$13 | pitch-envelope **rate / shape** (cmd $98–$9B: $F8 + $00/$80/$40/$C0) |
| 20 | $14 | per-channel enable flag (cmd $8D) |
| 21–24 | $15–$18 | operator TL base values (patch carriers) |
| 25 | $19 | AMS/stereo byte ($B4 source) |
| 26 | $1A | envelope sustain/decay counter |
| 27,28 | $1B,$1C | envelope target/mask |
| 29–30 | $1D,$1E | last frequency (for portamento compare) |
| 31 | $1F | **channel-enabled** (0 = skip in Update_FM_B) |
| 32–33 | $20,$21 | **note-duration reload / counter** |
| 34 | $22 | control-stream wait/delay counter |
| 35 | $23 | control-stream **bank** |
| 36–37 | $24,$25 | control-stream **pointer** |
| 38–39 | $26,$27 | control-stream **loop pointer** |
| 40,41 | $28,$29 | sequence repeat counters |
| 42,43 | $2A,$2B | pattern/position index + limit |
| 44 | $2C | **modulation-active flag** (0 → table pitch mode $02F5) |
| 45–47 | $2D–$2F | banked frequency-table base ptr (bank, lo/hi) |
| 48 | $30 | modulation **depth/offset** (signed) |
| 49–53 | $31–$35 | **per-op volume-envelope values** (set by CONTROL-stream cmds $0660 idx 0–4) |
| 54 | $36 | step-table **length/mode** (1–5) |
| 55 | $37 | **arpeggio/envelope step index** (mod `(ix+54)`) |
| 56–60 | $38–$3C | **arpeggio / note table** (transpose steps; set by NOTE-stream cmds $85–$89) |
| 61 | $3D | note-active flag (0 → run sequencer; else note-off $0416) |
| 62 | $3E | last instrument id (dedup) |
| 63 | $3F | modulation/portamento retrigger flag |
| 64 | $40 | frequency **block/high** base |
| 66–67 | $42,$43 | **pitch-slide accumulator** (16-bit fractional) |
| 68–69 | $44,$45 | **pitch-slide increment** (portamento slope) |
| 70–71 | $46,$47 | portamento **progress counter** |
| 72–73 | $48,$49 | portamento **target length** (÷ divisor) |

---

## 12. Techniques Worth Stealing (vs Flamedriver / Mega PCM / XGM2)

1. **Cooperative DAC coroutine interleaved with FM at Timer-B rate.** Instead of a fixed
   DAC ISR + separate FM update, this driver feeds DAC sample bytes in a tight loop and
   *checkpoints/resumes* whenever Timer B fires to do FM. Result: glitch-free DAC of
   arbitrary length with no dedicated mixing buffer and no DMA. Mega PCM gets clean DAC
   but doesn't interleave FM this tightly; XGM2 uses a sample-rate ISR. **This is a third
   model worth prototyping for Flamedriver: a single Timer-B coroutine.**

2. **14-bit linear pitch space + real portamento via 16÷16 division.** The frequency
   table is a linear ladder with sub-semitone steps, and glides are computed by an actual
   restoring-division slope per note. Most Genesis drivers (incl. SMPS) do stepped or
   coarse-additive slides. This gives true analog-style glissando — a Kyd signature.

3. **Dual data streams per channel (note + control).** Pitch envelopes, vibrato, and
   per-operator volume run on an *independent* control track, so a single held note can
   evolve (swell, detune, vibrato-in) without re-triggering. This is the structural reason
   the soundtrack feels "alive." Flamedriver could add an optional second per-channel
   modulation pointer cheaply.

4. **Per-operator software TL volume layered over the patch, algorithm-aware via SMC.**
   Carrier selection is patched into the TL-write code by self-modifying the `add a,n`
   operands from the algorithm — zero per-frame branching to decide which operators are
   carriers. Clean, fast, and gives smooth software volume envelopes on top of hardware
   ADSR.

5. **Hardware LFO + per-patch FMS/AMS ($B4) as a first-class, song-selectable parameter.**
   Cheap global "shimmer" that most drivers leave at zero. Worth exposing per-instrument
   in MegaDAW.

6. **Direct-injection mailbox (no opcode parser).** The 68k writes whole channel-start /
   DAC-request records into Z80 RAM; the Z80 latches and clears them. No command decode,
   no ring buffer, atomic single-flag handoff. Lower latency and less code than a byte
   protocol.

7. **Fade-out by ramping carrier TL toward $7F in hardware** — trivially cheap, no
   per-note volume math.

### What it does NOT do (so we don't over-credit it)
- No PSG (so no PSG envelopes/noise — all percussion is DAC).
- No SSG-EG, no Ch3 special mode, no Timer A.
- No multi-sample mixing / pseudo-stereo PCM; one DAC stream at a time.
- DAC steals FM channel 6 (only 5 FM voices while a sample plays).

---

## 13. Confidence & Open Items

- **CONFIRMED** by direct decode: init/timer, bank switch, DAC coroutine + loop, FM split,
  patch register order, LFO use, no-PSG, no-SSG-EG, both command tables, the mailbox,
  portamento division, pitch-slide accumulator, software TL volume, the channel struct
  field map (every offset above is traced to an instruction).
- **INFERRED** (logic-strong, not bus-traced): exact byte layout of the *song header*
  (`$0E5E–$0E67`: LFO, freq-table base ptr `$0E62`, instrument table `$0E65`, etc.) — the
  fields are read by the code but populated by the 68k loader, which isn't in this blob.
  The `$1810+` readback block is inferred to be a 68k-polled heartbeat.
- To fully resolve the song-header byte order and the on-ROM music/patch byte format,
  the next step is a live trace (Exodus): break on `$16F5`/`$0B52`, dump `$0E5E–$0E67`
  and the channel structs, and follow `$8000+` after a `SetBank` to read real song bytes.
