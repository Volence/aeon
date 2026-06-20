# Phase 3 cycle-budget spike — per-frame FM ModUpdate + 1B DAC at 59.4 Hz

**Status:** DE-RISKING SPIKE. Throwaway measurement + written verdict, NOT shipped
engine code. Decides whether Phase 3 can run a *full ModUpdate every frame* on all
6 FM channels alongside the free-running 1B DAC, or whether we must fall back to
Zyrinx's even/odd-frame channel split.

All cycle counts below are **deterministic Z80 T-states** (master clock / 15 =
3,579,545 Hz on NTSC). The 1B DAC's per-pass cost is *already proven balanced* at
400 T-states in `engine/z80_sound_driver.asm` lines 41–170 (the FILL/SKIP/DRAIN
cycle-balance proof); the FM figures are counted here from the real routines in
`engine/sound_fm.asm`.

Canonical T-states used (per the AS/Zilog table, all confirmed against the routine
bodies): `ld (nn),a`/`ld a,(nn)` = 13; `ld (hl),n` = 10; `ld r,(hl)`/`ld (hl),r` = 7;
`ld a,c`/`ld r,r'` = 4; `ld dd,nn` = 10; `ld dd,(nn)`/`ld (nn),dd` = 20; `nop` = 4;
`bit b,r` = 8; `jr` taken = 12 / not = 7; `jp` = 10; `jp cc` = 10 (taken or not);
`djnz` taken = 13 / not = 8; `call` = 17; `call cc` taken = 17 / not = 10; `ret` = 10;
`add hl,dd` = 11; `push` = 11; `pop` = 10; `inc/dec r` = 4; `inc/dec rr` = 6;
`add a,r`/`add a,(hl)` = 4/7; `sla r` = 8; `cp n` = 7; `and r/n` = 4/7; `or r` = 4.

---

## Step 1 — Compute the budget

### 1a. Z80 cycles per video frame

```
Z80 clock (NTSC)      = 3,579,545 cyc/s          (gen_sound_tables.py:43, Z80_CLOCK)
Frame rate (NTSC)     = 59.4 Hz                   (effective game-loop / VBlank rate)
Cycles per frame      = 3,579,545 / 59.4
                      = 60,261 cyc/frame          (≈ 60,260; use 60,260 as the budget)
```

### 1b. Subtract the 1B DAC consumer/free-running loop

The 1B DAC is the autonomous streaming loop (`engine/z80_sound_driver.asm`, the
cycle-balance proof at lines 41–170). It is a free-running, *every-path-equal-cost*
loop: FILL == SKIP == DRAIN == **400 T-states exactly** (line 158, "ALL THREE = 400
cyc EXACTLY (0-cyc spread)"). Note: the task brief's "~346 cyc/sample" is the
*historical* figure; the loop has since grown to a proven **400 cyc/pass** — see the
HISTORY note at lines 50–62 (+24 for re-selecting $2A every sample, +30 for the
Timer-A overflow poll). I use the **current, larger 400** so I do not understate the
DAC's share. Likewise the *effective* DAC rate is now `3,579,545 / 400 = 8,948 Hz`
(line 159), not the ~10 kHz quoted in the brief.

The loop runs continuously, so its per-frame footprint is simply "how many 400-cyc
passes fit in one frame":

```
DAC passes/frame      = 60,260 / 400 = 150.65  ->  ~151 passes/frame
DAC cost/frame        = 60,260 cyc                (the loop IS the Z80's main thread)
```

This is the key structural point and the honest framing: **the DAC loop is not a
budget line item that "leaves a remainder" — it is the dispatcher that consumes the
*entire* frame.** FM work does not run *alongside* the loop on free cycles; it runs
*inside* the loop, as the Timer-A overflow handler (`SndDrv_TimerATick` ->
`Sequencer_Tick`, lines 161–169). Every cycle spent in `Sequencer_Tick` is a cycle
the streaming loop is **not** servicing the ring.

So the real question is **NOT** "does 5.4k of FM fit in 60k of spare cycles" (it
trivially does in raw arithmetic). The real question, and the one that can actually
break the DAC, is:

> **Can the worst-case `Sequencer_Tick` (all 6 FM channels voice-stepping in one
> tick) complete without draining the ring lead past underrun?**

That is the constraint Step 2 and Step 3 measure. The 60,260 number is a sanity
ceiling (a single tick must obviously be << one frame); the *binding* limit is the
ring-lead headroom, computed in Step 3.

---

## Step 2 — ModUpdate worst case, counted from the real routines

A Phase 3 ModUpdate, per FM channel per frame, does: (a) a pitch/frequency reload
(2 YM freq writes + 1 key write — i.e. a re-key, same as `Fm_NoteOn`), and on a
**voice-step frame** (b) a full patch reload (`Fm_PatchLoad`) plus (c) the carrier-TL
re-assert (`Fm_SetVolume`, exactly as `Seq_HookSetPatch` does today at
sound_sequencer.asm:512–524).

### 2a. One YM register write — `Fm_YmWrite` (sound_fm.asm:56–69)

Part-I path (the common case), counted with its `call`:

```
call Fm_YmWrite          17
bit 0,b                   8
jr nz,.partII (not taken) 7
ld (SND_Z80_YM_A0),a     13
nop                       4
ld a,c                    4
ld (SND_Z80_YM_A1),a     13
ret                      10
                        ----
                         76 T-states per YM write (call + body + ret)
```

This **confirms** the brief's "~30 cyc/write" was an *under*estimate — the real
cost is **76 T** (the driver does NOT busy-poll; the spacing is the `nop` + caller
loop overhead, lines 52–53, but the absolute-addressing `ld (nn),a` writes are 13T
each and the call/ret framing dominates). I use 76 throughout.

### 2b. Re-key (pitch lookup + 2 freq writes + key write) — `Fm_NoteOn` / `Fm_NoteOnFreq` (sound_fm.asm:316–374)

```
Fm_NoteOn pitch lookup (ld l,a / ld h,0 / add hl,hl / ld de,nn / add hl,de
           / ld e,(hl) / inc hl / ld d,(hl))         = 4+4+11+10+11+7+6+7 = 60
Fm_NoteOnFreq:
  push de                                              11
  call Fm_RoutePart  (see 2c)                          83
  ld a,c / ld (nn),a / ld a,b / ld (nn),a (stash)      4+13+4+13 = 34
  pop de                                               10
  $A4 write setup: ld a,(nn)/ld b,a/ld a,(nn)/add a,n/ld c,d/push de
                                                       13+4+13+7+4+11 = 52
  call Fm_YmWrite                                      76
  pop de                                               10
  $A0 write setup: ld a,(nn)/ld b,a/ld a,(nn)/add a,n/ld c,e
                                                       13+4+13+7+4 = 41
  call Fm_YmWrite                                      76
  key-on: call Fm_ChSel (= Fm_RoutePart + a<<2|c)      83 + (4+4+4) = 95
  or n / ld c,a / ld a,n / ld b,0                      7+4+7+4 = 22
  call Fm_YmWrite                                      76
  set SCF_KEYED_B,(ix+f)                               23   (set b,(ix+d) = 23)
  jp Fm_ReparkDac (ld a,n/ld (nn),a/ret)               10 + (7+13+10) = 40
                                                      -----
                                              re-key ≈ 869 T-states
```

So the per-channel **re-key** alone is ≈ **870 T** — already heavier than the brief's
"~40 + 3×30 = ~130 cyc," because every write is 76T and `Fm_RoutePart`/`Fm_ChSel`
recompute the route via `call`s.

### 2c. `Fm_RoutePart` (sound_fm.asm:90–99), counted once for reuse

```
call Fm_RoutePart        17
ld a,(ix+sc_route)       19
ld b,0                    7
cp 3                      7
jr c,.done (worst: not)   7
ld b,1                    7
sub 3                     7
ld c,a                    4
ret                      10
                        ----
                         85 (use ~83; .done-taken branch saves a hair)
```

### 2d. Full patch reload — `Fm_PatchLoad` + `Fm_PatchOpGroup` (sound_fm.asm:142–220)

`Fm_PatchLoad` issues **26 YM writes total**: $B0, $B4, then 6 register groups ×
4 operators = 24. Counting the structural overhead:

```
push hl                                              11
call Fm_RoutePart                                    83
ld a,c/ld (nn),a/ld a,b/ld (nn),a (stash)            34
pop hl                                               10
$B0 setup: ld a,(nn)/ld b,a/ld a,(nn)/add a,n/ld c,(hl)/inc hl
                                                     13+4+13+7+7+6 = 50
call Fm_YmWrite                                      76
$B4 setup (same)                                     50
call Fm_YmWrite                                      76
6 × Fm_PatchOpGroup (each: setup + 4-op loop):
  per group fixed: call 17 + ld d,a 4 + ld e,0 7 + ld b,4 7 + ret 10        = 45
  per op (×4): push bc 11 + push de 11 + ld a,d 4 + add a,e 4 + push hl 11
             + ld hl,nn 10 + add a,(hl) 7 + pop hl 10 + ld c,(hl) 7
             + inc hl 6 + push hl 11 + ld hl,nn 10 + ld b,(hl) 7 + pop hl 10
             + call Fm_YmWrite 76 + pop de 10 + ld a,e 4 + add a,4 7
             + ld e,a 4 + pop bc 10 + djnz 13(8 last)               ≈ 243/op
  per group  = 45 + 4×243 - 5(last djnz)             ≈ 1,012
6 groups                                             6 × 1,012 = 6,072
jp Fm_ReparkDac (ld a,n/ld (nn),a/ret)               40
                                                    ------
                                   Fm_PatchLoad ≈ 11+83+34+10+50+76+50+76+6072+40
                                               ≈ 6,502 T-states
```

This is the headline correction: the brief's "~24×30 = ~720 cyc" is **off by ~9×**.
The real `Fm_PatchLoad` is ≈ **6,500 T**, because each of the 24 op-group writes
carries ~243T of push/pop/`ld hl,nn`/`add a,(hl)`/`call`/`djnz` framing, not a bare
13T store. (Confirmed against the loop body, sound_fm.asm:197–219.)

### 2e. Carrier-TL re-assert — `Fm_SetVolume` (sound_fm.asm:231–305)

```
log lookup: ld l,a/ld h,0/ld de,nn/add hl,de/ld a,(hl)/ld (nn),a
                                                     4+4+10+11+7+13 = 49
call Fm_RoutePart + stash (a,c)/(a,b)                83 + 34 = 117
call Fm_PatchPtr  (8× add hl + ld de,(nn) + add hl + ret; ~150)   ≈ 167
alg/mask: ld a,(hl)/and 7/push hl/ld l,a/ld h,0/ld de,nn/add hl,de
        /ld a,(hl)/ld (nn),a/pop hl                  7+7+11+4+4+10+11+7+13+10 = 84
ld de,nn/add hl,de                                   10+11 = 21
ld b,4/ld e,0/ld c,1                                 7+7+7 = 21
4-op loop, worst case = all 4 carriers (alg 7):
  per carrier op: push bc 11 + ld a,(nn) 13 + and c 4 + jr z (not) 7
    + ld a,(hl) 7 + push hl 11 + ld hl,nn 10 + add a,(hl) 7 + pop hl 10
    + jr c (not) 7 + cp n 7 + jr c (taken .tl_ok) 12 + ld c,a 4
    + ld a,n 7 + add a,e 4 + push hl 11 + ld hl,nn 10 + add a,(hl) 7
    + ld hl,nn 10 + ld b,(hl) 7 + pop hl 10 + call Fm_YmWrite 76
    + inc hl 6 + ld a,e 4 + add a,4 7 + ld e,a 4 + pop bc 10
    + sla c 8 + djnz 13(8 last)                      ≈ 312/op
4 ops                                                4 × 312 ≈ 1,248
jp Fm_ReparkDac                                      40
                                                    ------
                                   Fm_SetVolume ≈ 49+117+167+84+21+21+1248+40
                                               ≈ 1,747 T-states (4-carrier worst case)
```

### 2f. Per-channel worst-case ModUpdate (voice-step frame)

```
re-key (2b)                ≈   870
Fm_PatchLoad (2d)          ≈ 6,500
Fm_SetVolume re-assert (2e)≈ 1,750
                            ------
per channel (voice-step)   ≈ 9,120 T-states
```

### 2g. Six channels, all voice-stepping in the same frame

```
6 × 9,120                  ≈ 54,720 T-states
+ Sequencer_Tick dispatch overhead (channel walk, ~6 × ~60)  ≈ 400
                            ------
worst-case FM tick         ≈ 55,100 T-states
```

This is the **brutal worst case**: all 6 FM channels reload a full patch *and*
re-key *and* re-assert volume in the *same* Timer-A tick. The brief's "~5,400 cyc"
estimate is **~10× too low**, almost entirely because `Fm_PatchLoad` is ~6.5k not
~720.

---

## Step 3 — Verdict + fallback

### 3a. Sanity ceiling (the 60,260 frame)

```
worst-case FM tick   ≈ 55,100 T
budget               = 60,260 T/frame
                       -> ~5,160 T (8.6%) nominal headroom
```

On the naive "does it fit in a frame" question the answer is *barely* yes — but
**8.6% is not comfortable margin**, and this ceiling is the *wrong* limit anyway.

### 3b. The binding limit: ring-lead underrun (this is what actually breaks)

The FM tick does not run on spare cycles — it runs **inside** the DAC loop's `di`
window as the Timer-A overflow handler (`engine/z80_sound_driver.asm` lines 161–169).
While `Sequencer_Tick` runs, the streaming loop is **stalled**: the ring is being
drained by the YM at the DAC rate but **not refilled**. The ring lead is the only
buffer absorbing this stall.

```
Ring lead budget = SND_RING_LEAD_CAP (250) samples × SND_LOOP_CYC (400 cyc)
                 = 100,000 cyc   (z80_sound_driver.asm:165–166)
```

The driver's own BOUNDING note (lines 161–169) assumes "**~5000 cyc worst case**"
for a tick (one patch-load + other channels) — i.e. ~5% of the ring budget — and on
that basis declares the ring **cannot** underrun, and explicitly says the even/odd
split is "**held in reserve and is NOT needed for 5 FM + 4 PSG.**"

**That assumption does not survive Phase 3.** Phase 3's premise is *continuous
voice-stepping* — every active FM channel can reload its patch *every frame*. A
worst-case Phase 3 tick is ≈ **55,100 cyc**, which is **55% of the 100,000-cyc ring
budget**, not 5%. That is 11× the figure the DAC driver was designed and proven
against. At 55% drain in a single tick the ring lead would crater from 250 toward
~110 samples in one frame; a second heavy tick before the producer recovers
(entirely possible, since voice-stepping is *continuous*) would underrun and **click
the DAC audibly.**

### 3c. Verdict

**The simple "full ModUpdate every frame on all 6 channels" model does NOT have
comfortable margin and is REJECTED.**

- It is marginal even against the wrong (per-frame) ceiling (8.6%).
- It is **dangerous** against the right (ring-lead) limit: a 55k-cyc tick is 55% of
  the ring budget vs. the 5% the DAC loop was proven safe for, and Phase 3 makes
  these heavy ticks *recurring*, not one-off.

### 3d. Chosen approach (fallback adopted)

Adopt **Zyrinx's even/odd-frame split, PLUS patch-reload throttling.** Two
mechanisms, both required:

1. **Even/odd channel split (Zyrinx).** Process FM channels 0–3 on even frames,
   FM 4–5 + sequencer bookkeeping on odd frames. This roughly halves the per-tick FM
   cost. Worst-case tick with 3–4 channels voice-stepping ≈ 3.5 × 9,120 ≈ **32k cyc**
   — still 32% of the ring budget, so the split *alone is not enough.*

2. **Throttle the full patch re-assert (the real cost driver).** `Fm_PatchLoad`
   (~6.5k each) is ~71% of a channel's ModUpdate. A voice-sweep does **not** need a
   full 26-register reload every frame — most frames only a handful of registers
   actually change between adjacent voice-step entries. Recommended Phase 3 design:

   - **Cap full `Fm_PatchLoad` reloads to ≤ 1 channel per tick** (round-robin across
     the active FM channels). One full reload (~6.5k) + the re-key/vol for the rest
     (~6 × ~2.6k ≈ 15.6k) keeps a worst tick ≈ **22k cyc = 22% of the ring budget** —
     safe, with the same comfort margin the DAC driver was designed for.
   - Or, better, **emit a per-step register *delta*** (only the YM registers that
     differ from the previous step) instead of a full patch upload, computed at
     build time by the tool pipeline. This makes the common voice-step frame cost
     only the few changed writes (~76T each) + the re-key, eliminating the 6.5k
     spike almost entirely.

   The re-key (~870) and `Fm_SetVolume` re-assert (~1.75k) can stay per-channel
   per-frame; they are not the problem. The full `Fm_PatchLoad` is.

**Bottom line for the Phase 3 plan:** do **not** build the "full ModUpdate every
frame" model. Build the even/odd split as the frame-dispatch structure, and throttle
full patch reloads to ≤ 1/tick (round-robin) or replace them with build-time register
deltas. The ring-lead limit (100k cyc), not the 60,260-cyc frame, is the number every
ModUpdate design must be checked against — a tick must stay well under ~20–25k cyc to
keep the comfortable margin the 1B DAC loop was proven for.

---

## Summary numbers

| Quantity                                   | Value            | Source |
|--------------------------------------------|------------------|--------|
| Z80 cyc / frame (NTSC 59.4 Hz)             | 60,260           | 3,579,545 / 59.4 |
| 1B DAC loop pass cost                      | 400 cyc (exact)  | z80_sound_driver.asm:41–170 |
| One YM write (`Fm_YmWrite`, w/ call/ret)   | 76 cyc           | sound_fm.asm:56–69 |
| Re-key (`Fm_NoteOn`/`Fm_NoteOnFreq`)       | ~870 cyc         | sound_fm.asm:316–374 |
| Full patch reload (`Fm_PatchLoad`, 26 wr)  | ~6,500 cyc       | sound_fm.asm:142–220 |
| Carrier-TL re-assert (`Fm_SetVolume`)      | ~1,750 cyc       | sound_fm.asm:231–305 |
| Per-channel voice-step ModUpdate           | ~9,120 cyc       | sum above |
| **Worst-case FM tick (6 ch voice-step)**   | **~55,100 cyc**  | 6 × 9,120 + dispatch |
| Ring-lead underrun budget                  | 100,000 cyc      | z80_sound_driver.asm:165 (250 × 400) |
| Worst tick as % of ring budget             | **~55%**         | vs. 5% the DAC loop was proven for |
| Headroom vs. 60,260 frame ceiling          | ~5,160 cyc (8.6%)| marginal — and the wrong limit |

**VERDICT: REJECT the simple full-per-frame model.** Adopt the Zyrinx even/odd split
*and* throttle full `Fm_PatchLoad` reloads (≤ 1/tick round-robin, or build-time
register deltas). The full patch upload is ~6.5k cyc — 9× the brief's estimate and
the dominant cost — and 6 of them per tick (~55k) blows ~55% of the ring-lead budget
the 1B DAC depends on, versus the ~5% it was designed and verified against.
