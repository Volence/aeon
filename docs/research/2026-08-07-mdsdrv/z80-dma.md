# MDSDRV Z80 / PCM / DMA-survival — source-level study and comparison to Aeon

Sources read in full (all VERIFIED by reading, not summary):

- `docs/research/external/mdsdrv/src/mdssub.z80` (1692 lines, the whole Z80 PCM driver)
- `docs/research/external/mdsdrv/src/mdssub.inc`
- `docs/research/external/mdsdrv/doc/dma.md`, `doc/api.md`
- `docs/research/external/mdsdrv/src/mdsdrv.68k` (relevant spans: 60-180, 240-530, 2990-3192)
- `docs/research/external/mdsdrv/src/mddef.inc` (185-224), `sample/dma/main.68k`, `sample/dma/README.md`
- Ours: `engine/sound/z80_sound_driver.emp` (all 1380), `engine/sound/sound_api.emp`,
  `engine/sound/dac_sample_tab.emp`, `engine/sound/sound_constants.emp` (136-205),
  `engine/system/vblank.emp` (55-215), `games/sonic4/data/sound/dac_samples.emp`

I also **assembled** `mdssub.z80` with the repo's own `tools/sjasmplus.exe` (under wine, into
scratchpad only) to get exact sizes. Blob = **2714 bytes**; code runs `$0000`-`~$09DA`,
`pitch_update_fill` at `$0A00`, `pitch_update_mix` at `$0A40`, version string `$0A80`-`$0A99`.

---

## PART 1 — What MDSDRV actually is (VERIFIED)

### 1.1 Architecture: the Z80 is a PCM *slave*, not the sequencer

This is the single most important framing difference. **MDSDRV's Z80 does nothing but PCM.**
The FM/PSG sequencer runs on the **68k**, which writes YM2612 registers *directly through the
Z80 bus window* while holding the bus (`mdsdrv.68k:1399-1402`, `:2157-2169`, `:2381-2410` —
`mds_z80_wait_fm` / `move.b d0,$4000(zram)` / `mds_z80_start`). That is the SMPS-68k model.

Consequence: MDSDRV's Z80 blob is **2714 B** total for a 3-channel mixing PCM engine, and it
gets **~870 B of free Z80 RAM plus a 4 KB volume-table region** to play with. Our Z80 blob is
the *entire* music engine (sequencer + FM + PSG + SFX + DAC) and is up against a `$16F0`
code ceiling with ~316 B free. **Every "why don't we do what they do" answer bottoms out here.**

Also consequence: MDSDRV's 68k holds the Z80 bus dozens of times per frame (every FM register
write). Ours holds it **twice** per frame. On the bus-contention axis, our architecture is
already strictly better and that is not a small thing.

### 1.2 The PCM engine

| | MDSDRV mode 2 | MDSDRV mode 3 | Aeon |
|---|---|---|---|
| simultaneous PCM streams | 2 | 3 | **1** |
| output rate | 3579545/201 = **17809 Hz** | 3579545/268 = **13357 Hz** | 3579545/195 = **18356 Hz** |
| batch size | 32 samples | 30 samples | n/a (1:1) |
| mixing | Z80, signed, saturating | same | none |
| per-channel volume | 16 levels, 256-B LUT each | same | none |
| per-channel pitch | 8 rates, self-modified | 8 rates | none (fixed loop rate) |

Rate arithmetic (this trips people up): the `= 134` / `= 201` annotations throughout
`mdssub.z80` are **budget excluding the DAC output macro**. The file header states it
explicitly (`mdssub.z80:26-27`):

```
;    2xPCM max at 18khz   (201 cycles, 134 excl output)
;    3xPCM max at 13.5khz (268 cycles, 201 excl output)
```

`out_dac` is 67 T (`mdssub.z80:80-91`), so 134+67 = 201 and 201+67 = 268. **Our single stream
at 18356 Hz is marginally faster than their two streams at 17809 Hz.** The gap is entirely the
mixing work, not driver quality.

Sample format: **raw unsigned 8-bit**, converted to signed on the way in via the volume LUT and
back to unsigned with a free `xor c` (c = `$80`) inside `out_dac`. The LUTs are built by the
**68k at init** (`mdsdrv.68k:3163-3176`), not shipped in the blob:

```
	moveq	#-128,d1			;<-- for unsigned samples
	add.b	d0,d1
	ext.w	d1
	muls	(a0),d1
	move.w	d1,-(sp)			; use most significant byte
	move.b	(sp)+,(a1)+
```
16 tables x 256 B = **4096 B at `$0F00`-`$1EFF`** (`mdssub.inc:71`). Volume byte is literally the
**high byte of the LUT address**, so scaling is one `ld a,(bc)` (7 T) with `b` = volume:

```
	macro	read_one						; = 27
		ld		c,(hl)						;7
		inc		hl							;6
		ld		a,(bc)						;7      <- volume scale, 7 cycles
		ld		(de),a						;7
	endm
```
Effective volume range is `$0F`..`$1E` (`mdsdrv.inc:85-98`'s `mds_z80_get_vol` produces
`(~vol & 15) + 15`), not the `10-1f` the comment in `mdssub.inc:48` claims — a source/comment nit.

Mixing + saturation (`mdssub.z80:175-186`) is the prettiest 4 bytes in the file:

```
	macro	read_mix_one					; = 48 (59 worst case)
		ld		a,(de) / inc de / ld c,a
		ld		a,(bc)						;7   volume-scaled, signed
		add		a,(hl)						;7   mix into the buffer
		jp		po,.no_ovf					;10  P/V = signed overflow
		sbc		a,a							;4   -> $00 (C=0) or $FF (C=1)
		xor		$7f							;7   -> $7F (max+) or $80 (max-)
.no_ovf
		ld		(hl),a						;7
	endm
```
Saturating signed clamp in three instructions. Worth stealing verbatim if we ever mix.

Pitch (this is the clever one): the fill loop is **unrolled 8 slots x 4 iterations**, and the
per-slot byte that decides "advance the source pointer" is **patched at key-on** from a 64-byte
nop/`inc hl` table (`mdssub.z80:1668-1688`):

```
pitch_update_fill
	db		$00,$00,$00,$00,$00,$00,$00,$23		; rate 1: 1 inc per 8 outputs
	...
	db		$23,$23,$23,$23,$23,$23,$23,$23		; rate 8: 1:1
```
`$00` = nop, `$23` = `inc hl`; `pitch_update_mix` is the same with `$13` = `inc de`. Key-on patches
the 8 slots with 8 `ldib` macros (`:868-875`). **Nearest-neighbour resampling at literally zero
runtime cost and zero cycle variance.** The price is the documented bank-alignment table
(`mdssub.z80:33-39`): a sample crossing a bank boundary must cross on a batch boundary, so
alignment is 4*rate (2ch) or 5*rate (3ch) bytes.

### 1.3 DMA survival — the actual contract

`doc/dma.md` is honest about the mechanism and the limits. Verified against the code:

**Default = protection OFF.** `mds_init` leaves `$0038` = `$C9` (RET) so the Z80 ignores its
own VBlank /INT, and the 68k is expected to stop the Z80 bus around DMA "as with other sound
drivers" (`dma.md:38-41`). Low latency, classic behaviour, degraded PCM during DMA.

**Protection ON** is enabled by `set_pcmmode` (`$11`) with a buffer size in `d2` (40..220). The
68k enables it by **writing an opcode into Z80 code space** (`mdsdrv.68k:412-420`):

```
	moveq	#8,d0							; $08 - EX AF,AF' opcode
	tst.b	d2
	bne.s	@use_dma_protection
	moveq	#-55,d0							; $C9 - RET opcode
	moveq	#40,d2							; Min buffer size
	st.b	z_vbl_ack(zram)					; Acknowledge pending...
@use_dma_protection
	move.b	d0,$0038(zram)					; Rewrite interrupt routine
	move.b	d2,z_min_buffer(zram)
```

The runtime contract, exactly:

1. On its **own** VBlank /INT the Z80 enters `vbl` (`mdssub.z80:264+`), sets `z_vbl_ack = 0`,
   and enters a wait loop. **The Z80 opens the protection window itself — the 68k does nothing
   to open it.**
2. Inside the wait loop the Z80 **keeps feeding the DAC from its RAM ring**, cycle-matched to
   the main loop's cadence (`vbl_loop` = 57 T + a per-mode hook; `m2_vbl` at `:759-772` pads to
   134 T and does `dec a / ld (z_load),a / out_dac_slow`). **No 68k-bus access of any kind
   happens inside the window.**
3. The **68k must write a non-zero byte to `z_vbl_ack` (`$A00E06`) every VBlank, after all its
   DMAs are done** (`dma.md:73-88`). That write requires a bus hold. `sample/dma/main.68k:274-278`
   shows the canonical form (one hold: ack + read `z_load` back for telemetry).
4. If the buffer falls below `PCM_MIN_BUFFER` (**35** in source, `mdssub.z80:64`; `dma.md:67`
   says 40 — a doc/source discrepancy) the Z80 **stops emitting entirely** and spins in
   `vbl_wait_ack` (`:307-310`). The DAC latch holds its last value → silence, not garbage.
5. Failure to ack = **PCM stops** (`dma.md:76-77`). Never corruption.
6. There is an explicit "I need to mask interrupts for a long time" escape: `set_pcmmode` with
   `d1=d2=0` disables protection again (`dma.md:89-103`).

**Documented limits:** buffer 40..220 samples. 100 is the recommended value for 2ch. At 17809 Hz,
**100 samples = 5.6 ms ≈ 88 scanlines**, i.e. a 100-byte buffer covers the *entire* NTSC vblank.
220 = 12.4 ms. There is **no documented max-DMA-bytes-per-frame** — the budget is expressed
purely as buffer depth vs. how long the 68k takes to ack. `z_load` (`$A00E01`) is the 68k-readable
telemetry: "if this is often 40 in the vertical interrupt, increase the buffer" (`dma.md:130-134`).

### 1.4 68k <-> Z80 protocol

- **No mailbox/command ring at all** for the PCM side. The 68k writes the Z80's variable block
  (`$0E00`-`$0E1F`, `mdssub.inc:28-66`) **directly, under a bus hold**. Per-channel struct is 8 B:
  `key_on / vol / pitch / bank / addr(w) / count(w)`.
- Multi-byte atomicity is provided **by the bus hold**, not by a protocol. E.g. the addr write
  (`mdsdrv.68k:3084-3092`) pushes a word to the 68k stack first, then does
  `mds_z80_wait_req` -> three `move.b`s -> `mds_z80_start`, so the whole triple lands in one hold.
- "New command" signalling is a plain `st.b` of a `key_on` byte plus a global `z_key_on`
  (`mdsdrv.inc:144-158`); the Z80 clears it when consumed. Latest-wins, no queue.
- **No ack mechanism** except `z_vbl_ack` (which is the DMA handshake, not a command ack) and the
  `z_load` read-back for tuning.
- **`z_busy` (`$0E00`) is a *reverse* handshake:** the Z80 raises it around its own YM writes
  (`ld (hl),h` / `ld (hl),l` with `hl = $0E00` — 7 T each, no register loads). The 68k, *after*
  taking the bus, checks it and if set **releases the bus, burns ~96 T with a dummy
  `movem.l d0-d4` push/pop pair, and retries** (`mdssub.inc:114-127`). Purpose: never freeze the
  Z80 between a YM address write and its data write.
- The VBlank ISR also solves "interrupted while in the shadow register set": it sniffs `hl` for
  `$0E00`, and patches `vbl_exx` to either `exx` ($D9) or `nop` so the return restores the right
  bank (`mdssub.z80:271-288`). This exists **because MDSDRV runs the PCM loop with `ei`**.

### 1.5 Code-size / RAM tricks

- Blob 2714 B; code ~2522 B; two 64-B pitch tables; 26-B version string.
- Z80 RAM map: code `$0000`-`$09DA`, free `$0A9A`-`$0DFF` (~870 B), vars `$0E00`-`$0EFC`,
  stack down from `$0F00`, **volume LUTs `$0F00`-`$1EFF` (4 KB)**, ring `$1F00`-`$1FFF` (256 B).
- Self-modifying code is used **everywhere**, not as a hack but as the primary mechanism:
  - channel enable/disable = patching `jp` ($C3, always -> disabled path) vs `jp m` ($FA, taken
    only when the volume byte is negative) at a fixed address (`:439-442`, `:475-476`). The
    "is this channel playing" test is folded into the volume load it needs anyway, and key-off
    is encoded as the **sign bit of the volume byte** — one byte, zero extra branch.
  - per-mode VBlank hook = patching the operand of one `jp nc` (`vbl_hook equ $+1`, `:301-302`).
  - the mode jump table is reached by patching the **displacement byte of a `jr`**
    (`ld (mode_table-1),a` at `:358`) — a jump table with no indexing math at all.
  - bank selection: `set_bank_fast` is 9 x `ld (hl),h` with `hl = $6001`; the bank bits are baked
    into the **opcodes** ($74 = `ld (hl),h` -> writes bit 0, $75 = `ld (hl),l` -> writes bit 1),
    rewritten by `write_bank_ins_*` (`:125-147`) only on bank change. 63 T, zero registers.
  - loop-body pitch slots (section 1.2).
  - `ld (entry3+1),a ; for flashcart savestates` (`:354`) — stashes the current mode into the
    init code's own immediate so a savestate/reset resumes correctly. Unexpected.
- Padding idiom: shared `burn_27` / `burn_31` are literally `nop / ret` reached by `call`
  (`:427-430`) — **31 T in 3 bytes** (10.3 T/byte) vs a `jr` at 12 T in 2 bytes (6 T/byte).
- Every producer path is **hand-interleaved with `out_dac`** at <=134 T spacing, with hand-written
  cycle annotations at every boundary. Roughly 40% of the file's complexity is this interleaving.

---

## PART 2 — Ranked candidate takeaways

Byte costs are Z80 code bytes against our ~316 B headroom. "Cycles" are hot-loop T-states
against `SND_LOOP_CYC = 195` (`sound_constants.emp:200`).

---

### #1 [WORTH TAKING] Our Timer-A bulk-refill reads ROM *during* an active 68k DMA — the exact thing our own bracket exists to prevent

**MDSDRV:** never touches the 68k bus inside the protection window. `vbl_loop`/`m2_vbl`
(`mdssub.z80:293-302`, `:759-772`) do RAM reads and YM writes only. `doc/dma.md:18-26` states the
hazard precisely: the danger is the Z80 requesting the 68k bus **just as a DMA starts**, which
glitches the address lines — "in the best case the data transferred by the DMA to VRAM will be
corrupted. In the worst case ... you may get corruption on 68K RAM or flashcart ROM."

**Us:** `z80_sound_driver.emp:976-999`, and the comment says it outright:

```
    // 4. BULK-REFILL: top the lead up to SND_RING_LEAD_TARGET every frame, then
    // stop at sample end. Does NOT defer on an active 68k DMA — filling THROUGH
    // the DMA recovers the lead every frame and prevents the underrun (the read
    // still returns correct data; the DAC is already holding here).
.refill:
        ...
        ld      a, (ix+0)               // fill 1 byte: ROM(ix) -> ring[wr]
```
`ld a,(ix+0)` with `ix` in the `$8000` window **is** a 68k-bus access. Up to
`SND_RING_LEAD_TARGET` = 200 of them, back to back.

**Is it reachable?** Yes, routinely. Timer A period = 18.773 us x (1024-137) = **16.65 ms =
60.05 Hz** (`sound_constants.emp:163-173`) vs NTSC VBlank at 59.92 Hz. The two are free-running
and independent, so the tick's phase relative to the VBlank DMA window walks all the way around
roughly every 7.7 s. The tick lands inside the DMA window a fixed fraction of the time,
continuously. The comment's justification ("the read still returns correct data") is true for the
*arbiter-waits* case but is not the hazard `dma.md` describes.

Note this is a **hardware-only** defect — per the project memory we verify on emulator only, and
Exodus/Oracle do not model cartridge-bus contention. So it will never show up in our testing.
That is an argument for fixing it cheaply now, not for ignoring it.

**Fix:** poll the flag inside `.refill` and stop when it is set.
```
.refill:
        ld      a, (SND_CTRL_DMA_ACTIVE)
        or      a
        jr      nz, .refillDone
```
**Cost:** 6 bytes, 0 hot-loop cycles (off the timed path). **Risk: low.** The only behavioural
change is that on the frames where the tick lands inside the DMA window, that frame's lead
top-up is skipped — which is exactly the situation candidate #2 exists to make safe. Better
still, put it *inside* the loop (same 6 B) so it fills right up to the moment the flag rises.

---

### #2 [WORTH TAKING] DRAIN has no underrun guard — it laps the ring and buzzes; MDSDRV holds the last sample

**MDSDRV:** if `z_load < PCM_MIN_BUFFER` (35) the wait loop **stops emitting** and spins:
```
	ld		a,(z_load)						; 13
	cp		PCM_MIN_BUFFER					; 7
vbl_hook		equ		$+1
	jp		nc,vbl_wait_ack					; 10      <- only emits if load >= 35
```
(`mdssub.z80:299-310`). The DAC latch holds its last value. Degradation = silence.

**Us:** `z80_sound_driver.emp:477-485` — `.drain` is a pure `pad_to_cycles` + `jp .loop`. The
consumer at `.loop` (`:365-370`) emits `ring[c]` and does `inc c` **unconditionally**, with no
comparison against `b`. When the lead reaches 0, RD walks past WR and we replay the previous
256 bytes forever: a **~72 Hz buzz** (18356/256) at full amplitude, not silence.

Worse, it is **not self-correcting**. The tick's refill test is
```
        ld      a, b
        sub     c                       // lead = WR - RD
        cp      SND_RING_LEAD_TARGET
        jr      nc, .refillDone         // lead >= target -> topped up
```
(`:982-985`). After a lap, `(b - c) & $FF` is a large number (e.g. 248), so the refill concludes
the ring is **full** and does nothing. One underrun latches the buzz for the rest of the sample.

**Fix (branchless, so it does not perturb the cycle proof):** spend part of the existing 76 T
DRAIN pad on "do not advance RD when lead == 0":
```
        ld      a, b        ;4
        sub     c           ;4      lead
        add     a, $FF      ;7      C = (lead != 0)
        ld      a, c        ;4
        ccf                 ;4      C = (lead == 0)
        sbc     a, 0        ;7      c -= 1 iff lead == 0  (undo this pass's inc)
        ld      c, a        ;4
```
34 T, ~9 bytes, **constant cost on both paths**, and it comes straight out of the pad — so
`ensure(cycles(.loop,.fill_body) + cycles(.drain,.drain_end) == 195)` re-derives and still holds
with a shorter pad. Effect: RD pins to WR, the same (last valid) byte is re-emitted = DC hold,
exactly MDSDRV's behaviour, and the ring never laps so the tick's refill sees a real lead of 0
and refills properly.

**Cost:** ~9 B, **0 net cycles**. **Risk: low** (the pad shrinks; the existing ensure re-checks it).

---

### #3 [WORTH TAKING, with a legibility caveat] Patch hot-loop *opcodes* instead of testing RAM flags — MDSDRV's `$0038` trick generalized. -37 T/sample, -9 bytes, +23% DAC rate

**MDSDRV:** the 68k enables DMA protection by writing **one opcode byte into Z80 code**
(`mdsdrv.68k:419`, `move.b d0,$0038(zram)`), and the Z80 itself flips channels on/off by writing
`$C3` vs `$FA` over a `jp` opcode (`mdssub.z80:439-442`, `:475-476`, `:693-694`). Both variants
cost identical cycles, so the *test* disappears entirely and only the *branch* remains.

**Us:** the hot loop pays for two RAM flag tests every single sample
(`z80_sound_driver.emp:378-387`, costs from the header at `:69-71`):
```
        ld      a, (SND_DAC_PHASE)      ; 13
        cp      2                       ;  7    "phase 30"
        jp      z, .draining            ; 10
    .dma_check:
        ld      a, (SND_CTRL_DMA_ACTIVE); 13
        or      a                       ;  4    "DMA 27"
        jp      nz, .drain              ; 10
```
Both flags are **write-rarely, read-18356-times-per-second**. Replace each with a bare
conditional-jump opcode that the writer patches:

- Flags entering `.dma_check` are deterministically **Z** (set by the `and SND_TIMERA_OVF_MASK`
  at `:375`; the intervening `jp z` does not touch flags, and it was not taken). So `$C2`
  (`JP NZ`) is a guaranteed **never-taken** 10 T, and `$CA` (`JP Z`) is a guaranteed
  **always-taken** 10 T. Same for the phase check (flags there are also Z from the same `and`).
- Delete `ld a,(nn)` (3 B / 13 T) + `cp 2` (2 B / 7 T) and `ld a,(nn)` (3 B / 13 T) + `or a`
  (1 B / 4 T). The `jp cc` stays, unchanged in size and cost.
- 68k side: `vblank.emp:83-89` / `:158-164` write `$CA`/`$C2` to a code address instead of `$01`/`$00`
  to a RAM address. Identical instruction, identical bus hold. The symbol has to be exported.
- Z80 side: `.exhaust` (`:403-408`) and `.refillDone` (`:1007-1009`) write `$CA` instead of `2`;
  `SndDrv_Init`/`Snd_StartSample`/`.stop` write `$C2` instead of `0`/`1` — all same-size stores.

**Payoff:** 195 -> **158 T**, DAC rate 18356 -> **22655 Hz (+23.4%)** for **-9 bytes**. Or bank
the 37 T as headroom toward mixing (see #6/#7). All three `ensure(cycles(...))` re-derive
automatically; both pads shrink.

**Caveat, stated plainly:** this converts two self-describing RAM flags into self-modifying code,
in a codebase whose whole character is machine-checked contracts. `cycles()` will still measure
correctly (both opcode variants are 10 T) but it only *sees* one of them, so the "these two bytes
are a two-valued flag" fact becomes a prose invariant plus an `ensure` on the two opcode
constants. Also: two `$1F0x` RAM cells stop being readable by the debugger/state mirror as flags.
Given how much of this driver's value is its verifiability, I'd rank this **third**, behind the
two correctness fixes, and I would gate it on the user actually wanting the rate.

---

### #4 [WORTH TAKING] Ring-lead telemetry byte (their `z_load`)

**MDSDRV:** `z_load` at `$A00E01` is the whole tuning story — the 68k reads it every frame and
`sample/dma/main.68k:276` displays it; `dma.md:130-134` tells you exactly how to read it
("often 40 -> increase the buffer"). Their DMA sample ROM is a *tuning instrument*: left/right
adjusts a simulated DMA length so you can find the buffer size your game needs.

**Us:** we have `SND_STAT_ALIVE / PING_ECHO / ACK_COUNT / TICK / DAC_ACTIVE`
(`z80_sound_driver.emp:234-236`, `:265`) but **nothing that reports ring lead or underrun**. We
have literally no way to measure how much DMA-survival margin a frame actually used.

**Fix:** in `SndDrv_TimerATick`, right at the spill (`:951-955`, where `b`/`c` are already live):
```
        ld      a, b
        sub     c
        ld      (SND_STAT_MIN_LEAD), a
```
**Cost: 5 bytes** + 1 RAM byte (there are 45 B of map slack per the z80-ram-map spec). Sample the
lead *before* the refill so it reports the frame's worst case. Optionally DEBUG-gate it to 0 B in
the release shape. **Risk: none.** This is the prerequisite for ever claiming our DMA margin is
adequate rather than assuming it.

---

### #5 [REJECT for our architecture — but understand why] "Z80 self-opens the DMA window on its own /INT"

**MDSDRV:** the protection window opens with **zero 68k action** — the Z80's own VBlank interrupt
does it (`mdssub.z80:264-267`). The 68k only ever *closes* it. Two direct consequences:
one bus hold per frame instead of two, and **fail-safe default**: a missed ack means PCM stops
(silence), never a ROM read inside a DMA.

**Us:** `vblank.emp:83-89` and `:158-164` — two bus-held byte writes per frame, and the failure
mode is inverted: if the raise is missed, the Z80 **FILLs straight through the DMA** (the
dangerous direction). Ours is fail-open; theirs is fail-closed.

**Why we cannot simply adopt it:** our streaming loop runs `di` **end to end** by design
(`z80_sound_driver.emp:37-44`, `:352`), precisely so the register-resident state (`de/h/b/c/ix/hl'`)
survives without per-sample spills. The VBlank ISR therefore **does not fire during streaming** —
which is exactly when the window matters. MDSDRV can do this only because its PCM loop runs `ei`,
and the price it pays is the shadow-register-detection hack at `mdssub.z80:271-288`. Adopting
their trigger means adopting `ei` in the hot loop and re-solving that problem. **Not worth it.**

**What *is* worth taking from this item** is the fail-safe *posture*, cheaply: candidates #1 and
#2 together give us MDSDRV's actual safety properties (never read ROM in the window; hold instead
of buzz on underrun) without changing the trigger. **Verdict on the headline question: MDSDRV's
DMA approach is not better than our flag-bracket in mechanism — the shapes are near-identical
(both keep the Z80 running and feed the DAC from a RAM ring, both cycle-match the in-window
output to the steady-state cadence). It is better in two specific properties: fail-closed
default, and an absolute no-68k-bus-access rule inside the window. We already beat it on window
tightness (our window is the DMA pipeline, theirs is all of vblank), on latency, on bus-hold
count for music (their 68k sequencer holds the bus dozens of times per frame), and on rigour
(our balance is `ensure(cycles(...))`-checked at build time; theirs is hand-counted comments).**
The prior claim in `docs/research/2026-06-23-genesis-technique-survey.md:42` — "keep our
flag-bracket DMA survival, ours is better" — **holds**, with the two amendments above.

---

### #6 [REJECT for now — hard RAM blocker; record for the mixing phase] Volume-LUT + saturating-add mixing

**MDSDRV:** `mdssub.z80:160-191` (macros) + `mdsdrv.68k:3163-3176` (68k builds the LUTs). Cost:
**4096 B of Z80 RAM** for 16 x 256-B tables, plus the unrolled mix loops.

**Us:** our Z80 RAM is full. Map (`sound_constants.emp`, z80-ram-map spec): code to `$16F0`,
state/tables to `$18FF`, ring `$1900`-`$19FF`, sequencer `$1A00`+, SFX, stack top `$1FFE`.
Free: ~316 B code headroom, ~45 B map slack, ~231 B stack headroom. **There is no 4 KB hole, and
no 1 KB hole.** The LUT cannot be banked into `$8000` either — that window is occupied by the
sample payload, and reading it during a DMA is forbidden.

**Verdict: REJECT at 16 levels.** Two viable reduced forms to record for a future mixing phase:
- **No per-channel volume at all** — plain signed add + the `sbc a,a / xor $7f` clamp (4 B, 11 T,
  `mdssub.z80:181-184`). Zero table. This is the form to prototype first.
- **One shared 256-B "halve" table** so `A/2 + B/2` never overflows: 256 B of RAM, which we could
  probably find. Costs 1 bit of depth.

Cycle reality check for us: our fetch is `ld a,(ix+0)` (19 T) + `inc ix` (10 T) = **29 T**;
MDSDRV's is `ld c,(hl)` (7) + `inc hl` (6) = **13 T**. A second stream in our loop costs ~29 T
fetch + ~18 T mix/clamp + ~10 T pointer = ~57-70 T, taking 195 -> ~255-265 (13.5-14 kHz). With
candidate #3's 37 T banked first, 158 + ~65 = ~223 T = **16.0 kHz for two streams** — better than
MDSDRV's 2ch mode. That is the honest number to plan against.

---

### #7 [WORTH TAKING — deferred, large] Self-modified pitch slots (per-sample playback rate, free at runtime)

**MDSDRV:** `mdssub.z80:1668-1688` (tables) + `:856-875` (the 8 `ldib` patches at key-on).
8 rates, zero runtime cost, zero cycle variance.

**Us:** no pitch control at all — `ds_rate` in the descriptor is a reserved zero byte
(`dac_sample_tab.emp:69` "ds_rate (reserved)"), and the FILL loop is 1:1 (`:389-401`).
Every drum plays at exactly 18356 Hz.

**Why deferred:** the trick requires an **unrolled** producer block so there is a distinct
patchable byte per slot. Our producer is a single balanced pass. Adopting it means restructuring
FILL into an 8-step (or 4-step) unrolled block, which invalidates the current three-span
`cycles()` proof shape (it would become one per-block proof — still provable, but a rewrite).
Cost estimate: 64-B table + ~30 B patch code + ~60-100 B of unrolled body = **~160-200 B**, over
half our headroom. **Risk: medium-high** (breaks the balance proof structure).

**Value if taken:** pitched drums from one sample set, and the same mechanism is the natural
vehicle for #6 (their mix loops are the *same* unrolled block with `$13`/`inc de` slots).

---

### #8 [WORTH TAKING only as the vehicle for #6/#7] Batch producer with auto-increment pointers

**MDSDRV:** pointer setup is amortized over a 32-sample batch, so the inner fetch is
`ld c,(hl) / inc hl` (13 T) rather than an indexed load. That is the structural reason its
producer is ~16 T/sample cheaper than ours.

**Us:** 1:1, with `ix` as the ROM pointer (29 T/fetch) because `hl` is committed to the ring page
and `de` is pinned to `$4001`. I looked for a register re-plan that recovers the 16 T without
restructuring (moving ROM to `bc`, the ring indices to `ixl/iyl`, the DAC write to absolute, the
ring into the shadow set) — **every variant I costed nets out at zero or worse**, because our
consumer is already extremely cheap (22 T vs their 67 T) and any pointer move pushes cost onto it.
The 16 T is genuinely bought by the batch structure, not by register choice.

**Verdict:** not worth it for one stream — our 18356 Hz already beats their 17809 Hz, and their
batch model's price is the enormous hand-interleaving of `out_dac` calls through every producer
path (the bulk of `mdssub.z80`'s complexity, all hand-counted). Revisit only bundled with #6/#7.

---

### #9 [ALREADY HAVE — and better] `$2A` parked instead of re-selected per sample

**MDSDRV** re-selects reg `$2A` on **every single sample** (`out_dac`, `mdssub.z80:83-85`:
`ld a,b / ld ($4000),a` where `b = $2A`), costing **17 T/sample**. It has to: the 68k writes YM
registers asynchronously from its own sequencer.

**Us:** `z80_sound_driver.emp:31-35` — the addr port stays parked on `$2A` for the driver's
lifetime and the steady-state write is a bare `ld (de),a` (7 T). Only possible because nothing
but our Z80 ever writes `$4000`. **This is a direct dividend of the Z80-autonomous architecture**
and it is worth ~9% of the loop.

---

### #10 [ALREADY HAVE — and better] Cycle-matched in-window output

**MDSDRV** hand-pads `vbl_loop`/`m2_vbl`/`m3_vbl` to the steady-state cadence, with cycle counts
in comments (`mdssub.z80:294-302`, `:759-772`, `:1335-1359`).
**Us:** `ensure(cycles(...) == 195)` x3 (`z80_sound_driver.emp:493-497`) — the same property,
**machine-checked at build time**, with derived `pad_to_cycles` so the pads cannot drift.
Strictly better; keep as is.

---

### #11 [ALREADY HAVE] Ring geometry and depth

Theirs: 256 B ring, usable 40-220 (`dma.md:59-60`), recommended 100 (= 5.6 ms).
Ours: 256 B page-aligned ring, `LEAD_PRIME` 128, `LEAD_TARGET` 200 (`sound_constants.emp:191-192`)
= 10.9 ms at 18356 Hz. Comparable and slightly deeper. No change.

---

### #12 [ALREADY HAVE — different solution, ours simpler] Mid-sample bank crossing

**MDSDRV** crosses banks at runtime (`bit 7,h` per batch -> `write_bank_start_de` ->
9 patched opcodes, `mdssub.z80:531-556`), which is why it needs the documented sample-alignment
table.
**Us:** solved at **build time** — `dac_samples.emp:13-15` places each sample blob so it cannot
straddle a 32 KB boundary, with an always-on post-placement check. Zero runtime cost, zero
alignment burden on the content.
**Residual capability gap:** we cannot play a sample **longer than 32 KB**. Irrelevant for drums;
would matter for streamed voice/music. Note it, do not act.

---

### #13 [REJECT — not applicable] `z_busy` FM-write handshake and the movem-as-delay backoff

`mdssub.inc:114-127`. Exists because MDSDRV's 68k writes the YM directly and must not freeze the
Z80 mid address/data pair. **Our 68k never writes the YM at all** — it writes Z80 RAM bytes only
(`sound_api.emp` in full). Our bus holds can freeze the Z80 between its own `$4000`/`$4001` pair,
but the YM's constraint is a *minimum* spacing, and freezing only widens it. Nothing to take.

(The 68k-side idiom is still cute: `movem.l d0-d4,-(sp)` / `movem.l (sp)+,d0-d4` used purely as a
calibrated 96-cycle delay.)

---

### #14 [REJECT — nice, but blocked on tooling] `call burn_31` shared delay routine for pads

`mdssub.z80:427-430`. 31 T in 3 bytes vs our dense `jr` pad at 12 T in 2 bytes — ~1.7x denser.
Our two pads total 27 B (`z80_sound_driver.emp:426`, `:484`); this could reclaim ~10-14 B.
**Blocked:** `cycles()` would count the `call` as 17 T and not follow into the callee, so
`pad_to_cycles` would compute the wrong pad. Needs a sigil feature (or a hand-pinned `ensure`).
Low value against the risk of silently mis-timing the hot loop. Park it.

---

### #15 Curiosities worth knowing about (no action)

- **`jr`-displacement jump table** (`mdssub.z80:352-377`): `ld (mode_table-1),a` patches the
  displacement byte of the `jr main_loop` immediately preceding the table. A jump table with no
  indexing math and no `jp (hl)`. Range-limited to +-127, so only good for small tables.
- **Savestate-resilient mode stash** (`:354`): `ld (entry3+1),a ; for flashcart savestates` —
  writes live state into an *init routine's immediate operand* so a reset resumes correctly.
- **Busy flag via `ld (hl),h` / `ld (hl),l`** with `hl = $0E00` (`:281`, `:396`, `:405`): sets a
  RAM byte to `$0E` / `$00` in 7 T with no register loads. Free idiom, applicable anywhere we
  need a cheap two-valued RAM flag written from a hot path.
- **`xor c` (c = `$80`) inside `out_dac`**: signed<->unsigned conversion folded into the output
  path for free, so all mixing math is signed. Relevant if we ever mix.
- **The DMA sample ROM is a tuning instrument** (`sample/dma/main.68k`): D-pad left/right adjusts
  a simulated DMA burn loop (`r_dma_delay`, `:271-273`) while displaying `z_load`. We should build
  the equivalent when we act on #4 — it is how you get a *number* for DMA margin instead of
  "sounds fine".

---

## PART 3 — VERIFIED vs INFERRED

### VERIFIED (read directly in source; sizes measured by assembling)

- MDSDRV blob = 2714 B; layout `$0000`-`$09DA` code, `$0A00`/`$0A40` pitch tables, `$0A80` version.
- Rate arithmetic: 2ch = 201 T = 17809 Hz; 3ch = 268 T = 13357 Hz; `out_dac` = 67 T.
- 16 x 256-B volume LUTs at `$0F00`-`$1EFF`, built by the 68k, indexed by volume-as-high-byte.
- Volume byte effective range `$0F`-`$1E` (from `mds_z80_get_vol`), not the `10-1f` in the comment.
- Ring = 256 B at `$1F00`; usable buffer 40-220; `PCM_MIN_BUFFER` = 35 in source vs 40 in `dma.md`.
- DMA protection is OFF by default; enabled by writing `$08`/`$C9` at Z80 `$0038` via `set_pcmmode`.
- The Z80 opens the window on its own /INT; the 68k closes it with one bus-held write to
  `z_vbl_ack`; no 68k-bus access occurs inside the window; underrun = stop emitting (hold).
- No max-DMA-bytes limit is documented anywhere; the budget is buffer depth vs. ack latency.
- Pitch = 8-slot self-modified nop/`inc` table; alignment requirement is a direct consequence.
- Channel enable/key-off = `$C3`/`$FA` opcode patch + volume sign bit.
- Our `SndDrv_TimerATick` refill reads `(ix+0)` (the banked `$8000` window) without checking
  `SND_CTRL_DMA_ACTIVE`, and says so in its own comment.
- Our `.drain` path contains no lead check; `.loop` incs RD unconditionally; the tick's
  `cp SND_RING_LEAD_TARGET / jr nc` misreads a lapped ring as full.
- Our Timer A = 60.05 Hz vs VBlank 59.92 Hz -> free-running phase drift.
- Our samples are guaranteed not to straddle a 32 KB boundary at build time.
- Our hot-loop flag tests cost 30 T (phase) + 27 T (DMA) of the 195 T budget.

### INFERRED (reasoned, not directly stated by either source)

- **That the tick's refill-through-DMA is a real hardware hazard** rests on `dma.md`'s
  description of the DMA-start address-line glitch plus the phase-drift argument. Neither source
  quantifies the probability. It is unobservable on our emulator by construction.
- **The -37 T / +23% figure for candidate #3** is arithmetic on the header's own cycle
  decomposition (`z80_sound_driver.emp:69-71`), not a measured build. It assumes sigil accepts a
  bare `jp cc` whose opcode is patched at runtime inside a `cycles()` span (both variants are
  10 T, so the count is correct, but I have not confirmed sigil has no additional check).
- **The flag state entering `.dma_check` is Z** — I traced it (`and SND_TIMERA_OVF_MASK` sets it;
  the intervening `jp z` does not touch flags). Confirm against a listing before implementing.
- **The ~16.0 kHz two-stream projection** in #6 is my cycle estimate for a mix body we have not
  written. Treat as an order-of-magnitude planning number only.
- **The register re-plan dead end** in #8 is my analysis of several alternatives, not an
  exhaustive proof that no assignment recovers the 16 T.
- **The 4 KB LUT being unbankable** follows from "the `$8000` window holds the sample payload and
  must not be read during DMA" — sound, but it is my deduction, not a documented constraint.
