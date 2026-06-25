# DAC Drum / DAC-Format-Revision — Design

**Date:** 2026-06-24
**Status:** design (approved direction; pending spec review)
**Supersedes:** the exploratory `feat/sound-stream-drums` branch (reference-only)
**Predecessor context:** `docs/superpowers/2026-06-24-dac-drum-phase-handoff.md`,
`docs/superpowers/specs/2026-06-23-music-expression-engine-design.md` (Task 0 banking)

---

## AMENDMENT (2026-06-25): drum payload codec → raw 8-bit PCM (DPCM reversed)

**Decision (Layer 6 rework, approved by the user):** drum playback switches from the
4-bit noise-shaped **DPCM** payload (§2.2/§3.4) to **raw 8-bit PCM**, and the DAC rate
target is **~18-22 kHz**. The DPCM decode FILL + inline `DecTable` are removed (clean —
no dormant decode path); `ds_table` (+2) becomes a reserved **`ds_codec`** byte
(`0 = raw 8-bit`; future DPCM codecs select a per-sample loop in `Snd_StartSample`).

**Why (the rationale that overturned §2.2):**
- **The shared DAC bank made compression moot.** DPCM's only real win was halving ROM.
  That mattered when drums would have been duplicated *per song* (total = drums × songs).
  The settled shared-bank design (§2.1) stores each drum **once**, so 4-bit only halves a
  few KB stored a single time. With the per-sample `ds_bank` (§3.3) a kit can also span
  multiple `$8000` banks (each drum ≤ 32 KB; a 32 KB bank holds ~1.8 s of raw audio — far
  longer than any drum), so raw-PCM size is a non-issue.
- **The decode was the rate cap.** Inline DPCM decode is ~120 cyc/sample; since the loop is
  jitter-free (every pass costs identically), that sets the ceiling (~6 kHz as built; ~18-20
  only via a fragile *interleaved* loop). Raw PCM has ~zero decode → a plain register-resident
  loop reaches ~25-29 kHz, so **18-22 kHz is comfortable with cycle margin** (less fragile,
  more HW-robust). This is exactly why high-rate Genesis drivers (MegaPCM-2's headline mode)
  stream raw PCM and reserve DPCM for size.
- **Raw 8-bit is also cleaner** (~48 dB vs ~30-40 dB for noise-shaped 4-bit) and full-bandwidth
  at the higher rate. The noise-shaping was a mitigation for 4 bits we no longer take.

**Kept:** the ring, DMA-survival, the B1-B4 bank brackets, the one-shot state machine, the
Task 5.3 STREAM drum-test song (codec-agnostic — it fires `$E2` ids), the shared-bank layout.
**Re-derived:** the cycle balance (raw FILL is cheaper; `SND_LOOP_CYC`/pads/rate follow).
**Re-encoded:** kick/snare/hat as raw 8-bit at the final rate. **DPCM stays a future option**
for genuinely large/long compressed samples (the `ds_codec` hook).

**Verification posture unchanged** (§6): rendered-audio + de-wrapped-ring (now ring == the raw
sample bytes, byte-exact), correct-`$2A` in Exodus, MT regression, DMA-survival stress. **No real
hardware** — the higher rate's silicon behavior can't be confirmed; this is an accepted, recorded
caveat. **Revert safety:** branch `feat/dac-l6-rate` off tag `dac-drum-pre-l6` (= Task 5.3 HEAD);
`feat/dac-drum` is the pristine fallback.

Sections §2.2 (codec), §3.4 (decode), §3.5 (decode FILL), §3.8 (rate) and §5 (content/encoder)
are superseded for drums by this amendment; read them as the rejected-DPCM history.

---

## 1. Goal (one paragraph)

Build a clean, from-scratch **DAC drum playback path** for the custom Z80-autonomous sound
driver: a song triggers a PCM drum sample via the `$E2` (`MEV_DAC`) opcode; each one-shot sample
**plays once and cleanly stops** to DC-center silence; FM6 is shared with the DAC; the sample
payload is a **constant-cost 4-bit DPCM** decoded inline in the streaming loop; samples live in a
**shared DAC bank** the `$8000` window swaps to per frame; and — because the current ~8948 Hz is
the loop trip-time, not a hardware limit — the loop is then raised toward a **best-in-class
~18-20 kHz**. Every layer is verified by **rendered-audio cross-correlation** of the captured YM
`$2A` stream against the same-codec-decoded sample reference (`numpy.corrcoef`, r ≥ 0.9), never by
"is the DAC non-silent" (an enabled DAC on a bad pointer streams structured ROM garbage that looks
audible — the documented false-positive trap).

This is the engine side of "DAC-format revision" (DEFERRED_WORK items E2/E3). Build with
`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`; a plain build excludes all sound.

---

## 2. Decisions

### 2.1 Settled (confirmed by the full research sweep — 8 disasms + online + demoscene)

- **Banking = shared DAC bank** (Flamedriver model). Songs **stream** from their own bank; DAC
  sample payloads live in a **separate shared bank**; the `$8000` window swaps per frame: song
  bank during the sequencer frame, sample bank during the DAC FILL. `SetBank` is cached (no-op
  when the requested bank is already latched). Confirmed industry-proven (S3K per-V-Int
  `DAC_Banks` re-latch; Zyrinx cached `$6000` serial latch). Our cached separate-shared-bank is
  strictly better cache-hit than Zyrinx's per-descriptor bank naming.
- **FM6 = adaptive time-share is the goal**; **dedicate-FM6-while-active is the proven-safe
  fallback shipped first** (Zyrinx: `$2B=$80` + `$B6=$C0` force-DAC-stereo + skip ch6 key-on
  while the sample plays, keep its sequencer bookkeeping advancing, re-key on exhaust). The
  adaptive Echo-style toggle (key-off FM6 + DC-center + `$2B`, re-key on exhaust) is a strict
  superset, behind a per-song flag.
- **One-shot only** (no content loops in v1). The **cycle-balanced streaming loop is the pacing
  authority** (not Flamedriver's SMC `djnz`). Our RAM-ring + equal-cost FILL/SKIP/DRAIN is
  strictly superior to Zyrinx's direct-ROM streaming, which has no DMA-survival.

### 2.2 Re-opened by the user and resolved by the research

- **Payload codec → 4-bit DPCM with a noise-shaped, per-sample-selectable delta table**
  ("DPCM-HQ", from MegaPCM-2), **not** stock JMan2050 `deltas.bin`. The decoder is byte-identical
  to plain DPCM (one `add a,(iy+nibble)` per nibble, **no clamp**, wraps mod-256 → intrinsically
  constant-cost). The entire quality win is bought **offline in our encoder**: error-feedback
  noise-shaping moves quantization hiss out of the drum band, and per-kit-fit delta steps sharpen
  transients — at **identical Z80 cost, identical ROM, zero added jitter**. Rejected for our
  constraints: IMA/OKI/Yamaha ADPCM (adaptive step + saturating predictor = inherently branchy =
  data-dependent FILL length = breaks `FILL==SKIP==DRAIN`); µ-law/a-law (8→8, no ROM win); 2/3-bit
  DPCM and BTC (quality losers, ROM-starvation fallbacks only); runtime multi-voice mixing
  (doubles ROM bandwidth, breaks constant-cost — simultaneous drums are done as **offline
  pre-mixed composites** instead). Raw 8-bit PCM is the fidelity *reference*, not the payload.
- **DAC rate → raise toward ~18-20 kHz, this phase, verified in the Exodus/`oracle` emulator.**
  8948 Hz is the loop trip-time, ~3× below the proven ceiling (Echo 10.6k, XGM2 13.3k, MegaPCM
  20-32k, Kabuto/Overdrive 2 stable ~26k). At 8948 Hz, Nyquist ≈4.5 kHz discards the 4-10 kHz band
  where drum punch lives. **Coupling caveat (load-bearing):** the decoder makes the loop *heavier*
  (~+30 cyc → ~8.3 kHz), while raising the rate means *trimming the prefix*. The biggest trim — the
  per-sample `$2A` re-select — historically fixed a real wrong-register bug, but that bug was the
  address latch being clobbered by the ISR / `Sequencer_Frame` (which write `$4000`), **not a
  hardware quirk**: by documented YM2612 behavior the latch holds across pure data writes (`$4001`).
  The precise fix is to **re-park `$2A` in every path that touches `$4000`** (ISR, Timer-A frame,
  `SetBank`) and drop the per-sample re-select. The original bug was observed in Exodus, so Exodus is
  a valid venue to verify the trim (correct-reg + steady `$2A` cadence + cross-correlation). **No
  real hardware is available**; real-HW confirmation is a future nicety, not a blocker. **Conservative
  fallback:** if Exodus shows any wrong-reg behavior, keep the per-sample re-select and accept a more
  modest rate. Decode and rate are still built and verified as two separate steps.

### 2.3 Deliberately left open (designed-for, not built in v1)

- Both FM6 modes are **built this phase**; the per-song flag selects dedicate vs adaptive (default =
  dedicate until adaptive is exercised by real content).
- The exact target rate within ~16-22 kHz (HW-measured in the rate-raise layer).
- Block-adaptive DDPCM (a 3-bit table selector + 1-bit predictor flag per block, still a single
  constant-cost lookup) — the aspirational ceiling above per-sample table selection; the format
  is kept open (the `ds_table` byte) so this is a clean additive extension.
- Looped DAC samples — a clean descriptor-version bump later; out of scope and bug-prone in v1.

---

## 3. Architecture

### 3.1 Playback state machine

Runs off the existing free-running `SndDrv_Sample` streaming loop; no separate player task. State
is `(SND_STAT_DAC_ACTIVE, SND_DAC_PHASE, SND_ROM_LEN, ring lead)`.

```
IDLE          DAC_ACTIVE=0, PHASE=0. Idle/main loop runs; FM6 owned by the sequencer;
              $2B left armed; the loop writes $2A=$80 (DC center) each pass. No ROM read.
   │  $E2 → Snd_StartSample
   ▼
PLAYING       DAC_ACTIVE=1, PHASE=1, ROM_LEN>0. Consumer emits 1 ring byte/pass to $2A;
              decode-FILL reads 1 ROM byte → 2 decoded ring bytes (2:1 catch-up); SKIP when
              the ring is full; DRAIN when a 68k DMA is in progress (SND_CTRL_DMA_ACTIVE).
   │  producer exhausts (ROM_LEN reaches 0)
   ▼
DRAINING_TAIL PHASE=2. Producer is done but the ring still holds up to LEAD_CAP undelivered
              decoded bytes. The consumer keeps emitting them; the FILL dispatch takes a
              STOP-PENDING branch that no longer reads ROM and is cycle-identical to SKIP, so
              the loop stays balanced. Continues until ring lead == 0.
   │  ring lead == 0
   ▼
STOPPING      Write $2A=$80 (DC center), clear DAC_ACTIVE, set PHASE=0, hand FM6 back
              (re-key if it was dedicated/toggled). Falls to IDLE next pass.
```

**Two-stage exhaust (the clean stop).** The producer hitting `ROM_LEN==0` does **not** stop the
DAC — it transitions to `DRAINING_TAIL` so the ring's already-decoded tail still plays out; only
when the ring fully drains do we DC-center and clear `DAC_ACTIVE`. Because the ring lead is primed
with `$80`, the tail naturally arrives at DC-center, so the clean stop and the FM6-return centering
are **the same mechanism — implemented once**.

**Underflow-safe exhaust test.** Decode-FILL consumes 1 ROM byte/pass and does `len -= 1`. The
exhaust test fires at exact zero: `dec hl` (or after `ld (SND_ROM_LEN),hl`) then `ld a,h / or l /
jp z,.producerDone`. The `bit15-set` form is kept only as a defensive underflow backstop, never the
primary test. (Samples are < 32 KB so a valid in-progress `len` is in `[1,$7FFF]`.)

**Re-trigger.** A later `$E2` re-enters `Seq_Op_Dac → Seq_HookDac → Snd_DacLookup →
Snd_StartSample` from any phase. `Snd_StartSample` fully re-initializes (RD=0, WR=LEAD_PRIME, ring
re-primed to `$80`, `SND_DEC_ACC=$80`, reloads ptr/len/bank/table from the descriptor, `PHASE=1`,
`DAC_ACTIVE=1`), so a re-trigger **is** the abort — no cross-fade, classic-faithful, no infinite
loop, no stranded `DAC_ACTIVE` (the only path that clears it is `STOPPING`, which always runs once
the lead drains).

### 3.2 Clean DAC state block (delete dead/aliased fields)

Verified on master: `SND_PLAY_ACTIVE/PTR/LEN` ($16F0-$16F5), `SND_TEST_SAMPLE`, `SND_DRAIN_*`, and
`SND_DAC_RATE` are **defined but never read** (dead 1B bring-up), and `SND_LOOP_OFS`/`SND_PLAY_MODE`
**physically overlap** at `$16FF` (the documented landmine). Per clean-not-bolted-on, **delete**
all of these and lay out a clean, non-aliased DAC state block. Net effect: room for the new fields
without lowering `SND_STATE_BASE` into code space, and the landmine is gone.

New / retained fields (final offsets assigned during implementation; all reads/writes are Z80-RAM,
bank-free):

| Field | Purpose |
|---|---|
| `SND_RING_RD`, `SND_RING_WR` | ring read/write low-byte pointers (retained) |
| `SND_ROM_PTR` (2) | current sample window read ptr (retained) |
| `SND_ROM_LEN` (2) | packed bytes remaining (retained; one-shot exhaust) |
| `SND_ROM_BANK` (1) | **sample** bank id — stashed by `Snd_StartSample`, latched by bracket B1; **seeded = `SND_SONG_BANK` at load** so B1 is a no-op for DAC-off songs |
| `SND_CUR_BANK` (1) | `SetBank` cache (retained) |
| `SND_SONG_BANK` (1) | **song** bank id — set in `Snd_LoadSong`, latched by bracket B1 |
| `SND_DEC_ACC` (1) | **DPCM running predictor** (must be RAM, see §3.4) — seeded `$80` |
| `SND_DAC_PHASE` (1) | 0=idle, 1=playing, 2=draining-tail |

Re-run the state-block overflow asserts after the re-layout.

### 3.3 Sample descriptor format

Extend `DacSample` to **9 bytes** (data format; designed-for-end-state per the no-pigeonhole rule).
Descriptors stay **inline in the Z80 blob** (Z80-addressable, no banking to read them); only the
sample *payload* bytes live in the shared bank.

```
ds_bank     ds.b 1   ; +0  sample bank id = (addr & $7F8000) >> 15
ds_rate     ds.b 1   ; +1  RESERVED forward-compat (per-sample rate); v1 = fixed rate, ignored
ds_table    ds.b 1   ; +2  DPCM delta-table index (0..NUM_DELTA_TABLES-1)
ds_ptr      ds.w 1   ; +3  Z80-window ptr (addr & $7FFF)|$8000, little-endian
ds_length   ds.w 1   ; +5  PACKED byte count (nibble pairs); < $8000
ds_loop_ofs ds.w 1   ; +7  RESERVED forward-compat (loop restart); v1 = 0, ignored
```

`Snd_DacLookup` indexes `id-1` by `*9` (`*8 + index`). Update the `DacSample_len == 8 → 9` assert.

### 3.4 The payload codec (noise-shaped 4-bit DPCM)

**Decode (per nibble), constant-cost by construction:** `acc = (acc + DecTable[table*16 + nibble])
& $FF; emit acc`. No clamp, no conditional — the mod-256 wrap **is** the proven S3K drum sound and
is intrinsically branchless. `acc` is seeded `$80` at sample start. High nibble first, then low.

**`DecTable` lives inline in the Z80 blob (bank-free).** It is read on *every* FILL pass (`iy =
DecTable + ds_table*16`, set once at `Snd_StartSample`); it **cannot** live in the `$8000` window
because the window holds the sample payload during FILL. Size = `NUM_DELTA_TABLES * 16` bytes (e.g.
3 tables = 48 B of the ~1 KB Z80 headroom). Starting table families (sharp-transient / body /
quiet); final values are produced and validated by our encoder (§5), not blindly lifted.

**`SND_DEC_ACC` must be in RAM, not a register.** The loop documents "live registers across
iterations: NONE"; the single `ei` lets the VBlank ISR land between samples and `SndDrv_PollMailbox`
clobbers `ix/iy` (and the ISR doesn't save them). A predictor kept in a register (as S3K's
self-contained loop does) would be destroyed. So: `ld a,(SND_DEC_ACC)` at FILL top, `ld
(SND_DEC_ACC),a` at FILL end, entirely inside the `di` window; SKIP/DRAIN never touch it (preserved
across non-FILL passes).

**Constant-cost guard (adversary Claim B):** (1) no-clamp wrap → no saturate branch; (2) `acc` in
RAM; (3) the only ROM read is one byte (vs two today), so the ~3.3-cyc/byte bus penalty is *more*
deterministic; (4) SKIP/DrainPad are regrown to track the new FILL exactly.

### 3.5 Decode FILL + cycle rebalance

Decode-FILL: load `acc` ← `SND_DEC_ACC`; read 1 ROM byte from the window; split into 2 nibbles
(high then low) via SMC'd table index (`ld (.i+2),a`); `add a,(iy+0)` per nibble; write both decoded
bytes to `ring[WR], ring[WR+1]`; `WR += 2`; store `acc` → `SND_DEC_ACC`; `len -= 1`; exhaust test
(§3.1). Net ring lead change is **+1/pass**, identical to today's raw 2-byte FILL, so the 2:1
catch-up and `LEAD_CAP`/`LEAD_PRIME` are unchanged.

The decode is ~+30 cyc heavier than the raw FILL (~183 → ~213 producer; ~400 → ~432 total → ~8.3
kHz). **Measure the real total in-assembler**, set `SND_LOOP_CYC` to it, regrow `SkipPad` to the new
producer cost and `DrainPad` to (new producer + the 21-cyc dispatch tail); `SND_DAC_RATE_HZ`
auto-follows `dac_rate_hz()`.

### 3.6 Shared-bank per-frame swap choreography (the real latent bug)

**Bank needs (verified):** the song bank must be in the window for *every* `Sequencer_Frame` ROM
read — per-channel command stream (STREAM songs), `FmPatch` reads, per-song pitch table, and the
co-located engine tables at window `$8000`. The sample bank must be in the window for *exactly one*
read — the FILL producer's `ld c,(hl)`.

**The bug (master, verified at `z80_sound_driver.asm:605-606,641-648`):** `Snd_StartSample` calls
`SndDrv_SetBank(ds_bank)` and restores only `$2A`+`de`, **not the bank**. Because it runs *inside*
`Sequencer_Frame` (`SndDrv_TimerATick → Sequencer_Frame → Seq_HookDac → Snd_StartSample`), the
sample bank persists and every channel sequenced after the `$E2` reads sample bytes as
fnum/patch/table/opcode data — garbage notes. Master is safe today only because no song fires `$E2`.

**The full window-read inventory** (every operation that reads the `$8000` window, and the bank it
needs): (a) the Timer-A frame — song channels read stream/patches/pitch/tables **and** the SFX
channels (`Sfx_Frame`, run inside `Sequencer_Frame`) read their blobs, all **co-located in the song
bank** (SFX blobs share the song's bank — verified) → **SONG bank**; (b) the DAC FILL producer →
**SAMPLE bank**; (c) the ISR `SndDrv_PollMailbox` — `SfxDispatch` reads an SFX blob and `Snd_LoadSong`
reads a new song, both via the window (and `SfxDispatch` SetBanks and *leaves it set*) → **SONG
bank**. So the window must hold the song bank for every frame and every ISR blob read, and the sample
bank for every FILL.

**Fix — four brackets, all cheap (SetBank is cached → no-op when banks coincide):**

- **B1 (`Run_SeqFrame_OnSongBank`, brackets *both* tick paths):** `SetBank(SND_SONG_BANK)` →
  `call Sequencer_Frame` → `SetBank(SND_ROM_BANK)`. Used by **both** `SndDrv_TimerATick` (streaming)
  **and** `SndDrv_IdleTick` (idle): after a sample exhausts the window is left on the sample bank, so
  the next idle-tick frame would otherwise read the song streams on the wrong bank. Runs entirely
  inside the loop's `di` window (no ISR race).
- **B2 (`Snd_StartSample`):** do **not** latch the sample bank — `Snd_StartSample` reads no sample
  ROM (it primes the ring with `$80`; the FILL producer reads ROM later). Just `ld (SND_ROM_BANK),a`
  (stash) and return. Removes the redundant latch that caused the bug.
- **B3 (`SndDrv_ISR`):** make the ISR **bank-transparent** — save `SND_CUR_BANK` on entry, restore it
  via `SetBank` on exit (around `SndDrv_PollMailbox`). `SfxDispatch`/`Snd_LoadSong` still SetBank to
  the song bank internally to read their blobs; B3 guarantees the pre-ISR bank (the **sample** bank
  during DAC streaming) is restored on exit, so an SFX firing mid-drum can't strand the window on the
  song bank and corrupt the next FILL. (A music-load resets the song anyway; the next frame's B1 sets
  the new song bank.)
- **B4 (`SndDrv_Idle` → streaming entry):** `SetBank(SND_ROM_BANK)` just before `jp SndDrv_Sample`,
  so a sample armed via the mailbox `SND_REQ_SAMPLE` path (whose `Snd_StartSample` runs in the ISR,
  bank-transparent under B3) still enters streaming on the sample bank. Cheap cached SetBank; a no-op
  for the `$E2`-in-frame path (B1-post already latched it).

**Guarantees:** every sequencer frame and every ISR blob read run on the song bank; FILL always runs
on the sample bank.
`SND_ROM_BANK` is seeded `= SND_SONG_BANK` at load, so for a **DAC-off song (e.g. MT)** both B1
`SetBank`s are the song bank — cached no-ops, MT byte-identical. When `song bank == sample bank`,
both `SetBank`s are cached no-ops. When they differ, the cost is up
to `2 × 9` serial `$6000` writes per Timer-A frame — a bounded one-pass micro-perturbation well
inside the ring-lead budget (verify the worst-frame spike in the rate-raise layer).

**Build/runtime assert:** for any DAC-on song, `song bank != sample bank` is allowed, but both
brackets must be present. The **verification gate** for this layer is cross-correlating the *music
channels* after a `$E2` — a bank-swap failure streams ROM garbage that looks audible, so a music
corrcoef ≥ 0.9 (not just the drum) is the guard.

### 3.7 FM6

**Dedicate-while-active (shipped first, Zyrinx-proven).** At sample start in `Snd_StartSample`, once
per trigger, after centering: `$2B=$80` (DAC mode on — already done) → **`$B6=$C0`** (part-II addr
`$4002`, data `$4003` = ch6 L+R on, AMS=FMS=0, force DAC stereo — **add this**, master omits it). While
`DAC_ACTIVE`: gate the ch6 voice writer in `Sequencer_Frame` so FM6 is not re-keyed (it coasts on its
own release rate) — **but keep advancing ch6's sequencer bookkeeping** (tempo/pattern position) so
its musical position isn't lost. On exhaust: clear the gate; FM6 re-articulates on its next note. No
`$2B` toggle needed in the fallback.

**Adaptive Echo-style toggle (the goal, behind a per-song flag).** FM6 plays music *between* hits. At
the DAC trigger edge (FM→DAC): key-off FM6 ops (`$28 = ch6sel`), write `$2A=$80` (DC center pass-
through to avoid a level jump), then `$2B=$80` + `$B6=$C0`, begin streaming. At exhaust (DAC→FM): the
two-stage drain already lands `$2A` at DC-center, then re-key FM6 (re-assert its current sequencer
note `$A4/$A0` fnum + `$28=$F0|ch6sel`). Pass through `$2A=$80` at **every** transition edge (both
directions); apply `$B6=$C0` only *after* centering to avoid a panning-level jump. The MD2 `$7F→$80`
DAC discontinuity is handled by deliberately centering at `$80` and letting the encoder dither across
that step.

### 3.8 The rate raise (separate, HW-gated layer)

After the decoder ships at ~8.3 kHz, raise the loop toward ~18-20 kHz as an independent change:

- **Prefix trim:** drop the per-sample `$2A` re-select. The latch holds across pure data writes
  (`$4001`) by documented YM2612 behavior; it was being clobbered by the ISR and `Sequencer_Frame`
  (which write `$4000`). The precise fix: **re-park `$2A` on exit of every path that touches
  `$4000`** — the VBlank ISR (`SndDrv_PollMailbox`), the Timer-A frame, and `SndDrv_SetBank` — then
  the steady-state consumer needs no per-sample re-select. Verify correct-reg in Exodus (the venue
  that caught the original bug). Optionally also amortize the K=30 Timer-A poll, but **only if it
  stays cycle-balanced** (a periodic poll would jitter the rate — pad or skip uniformly).
  **Fallback:** if any wrong-reg shows in Exodus, retain the per-sample re-select and a modest rate.
- **Re-balance** `SkipPad`/`DrainPad` to the shorter FILL; `SND_LOOP_CYC` and `SND_DAC_RATE_HZ`
  follow.
- **DMA-survival re-derivation:** the ~250-byte ring lead is a *wall-clock* budget — ~28 ms at
  8948 Hz, but ~12.5 ms at 20 kHz. Re-derive against the worst-case 68k DMA + VBlank stall at the
  target rate; **deepen the ring** if 256 B is too short. Note: growing past 256 B requires widening
  the single-byte `SND_RING_RD/WR` pointer scheme — a real architectural change, budgeted in this
  layer.
- **Per-sample rate** (if ever) comes from a fixed loop-trip-count / integer decimation in the
  decode, **never** a `djnz` pad (which would unbalance the three paths). v1 ships one fixed rate;
  `ds_rate` stays reserved.

---

## 4. Build-time shared-bank layout

- One **shared DAC bank**, `$8000`-aligned, holds all DPCM sample payloads concatenated. The bank
  is constant for a DAC-on session, so `SetBank` to it is a no-op after the first FILL — the
  per-frame swap cost is only the song↔sample transitions.
- Each sample must not straddle a `$8000` window boundary mid-sample (FILL never re-banks
  mid-sample). The build tool asserts each `ds_ptr + ds_length ≤ $10000`.
- The **drum test song co-locates the engine tables at the start of its own bank** (window `$8000`),
  exactly as MT does (`main.asm:256-289`) — so `SND_SONG_BANK` covers every sequencer-frame window
  read. This is the documented "co-locate tables in the song bank" hook.
- Descriptors (`DacSampleTable`) and `DecTable` stay **inline in the Z80 blob**.

**Asserts:** (1) `DacSample_len == 9`; (2) each `ds_ptr + ds_length ≤ $10000`; (3) `ds_table <
NUM_DELTA_TABLES`; (4) state-block overflow guard after the re-layout; (5) `Z80_SOUND_SIZE ≤
SND_STATE_BASE`; (6) `DecTable` block = `NUM_DELTA_TABLES*16` bytes; (7) both swap brackets present
for any DAC-on song.

---

## 5. Content plan (S3K steal → our encoder)

**Samples** (TEMP bring-up content; real kit is a later user content decision; custom drum art per
the no-ported-code rule): kick `skdisasm/Sound/DAC/86.wav`, snare `81.wav`, hat `8C.wav` (verified
present). skdisasm's shipped `generated/*.dpcm` are **empty**, so we encode from the `.wav`.

**Encoder (`tools/dac_encode.py`, offline, our own):**
- Greedy nearest-delta DPCM with mod-256 wrap (prev seeded `$80`, high-nibble-first), matching the
  decode exactly.
- **Error-feedback noise-shaping** quantizer (the DPCM-HQ quality win): carry the quantization error
  forward so hiss is pushed out of the drum band.
- Emit `.dpcm` payload + chosen `ds_table`; emit/optimize the `DecTable` families.
- Resample each source to the driver's target DAC rate before encoding (the cross-correlation proof
  is against the same-codec-decoded reference, so absolute pitch is not the gate, but matching the
  rate keeps the drums in tune).

---

## 6. Verification methodology

**Always rendered-audio cross-correlation**, never "is it non-silent." Capture the YM `$2A` byte
stream via the Exodus/`oracle` VGM logger; decode **both sides with the identical delta table**;
`numpy.corrcoef` over a contiguous sample-length window; compare against the **same-codec-decoded**
reference (the codec is lossy by design — do not compare to the pristine WAV). Tooling:
`tools/dac_verify.py` (extends the handoff's `$2A`-extraction + corrcoef script with same-codec
decode). Live Z80 state probes via `emulator_z80_read`: `SND_ROM_PTR/LEN`, `SND_ROM_BANK`,
`SND_SONG_BANK`, `SND_CUR_BANK`, `SND_DEC_ACC`, `SND_DAC_PHASE`, `SND_STAT_DAC_ACTIVE`,
`SND_SEQ_BADOP`.

**Per-layer gates:**
- **L0 blip** — decode-FILL output vs a known synthetic blip waveform, **r = 1.0** (FILL decode +
  ring + consumer bit-exact).
- **L1 single drum** — kick `$86` one-shot; `$2A` vs same-codec reference, **r ≥ 0.9**.
- **L2 one-shot stop** — `$2A` ends at `$80` and `DAC_ACTIVE` clears; immediate re-trigger restarts
  cleanly with no tail-garbage byte past the sample (validates the exact-zero exhaust).
- **L3 shared-bank** — a song that streams from its own bank and fires `$E2`; **the music-channel
  corrcoef after the `$E2` is the gate** (proves brackets B1+B2; garbage-that-looks-audible guard).
  **Fire an SFX mid-drum** and confirm both the SFX and the resumed music/drum are correct (proves
  B3). **MT regression** must stay byte-identical (B1 touches the idle tick path MT uses).
- **L4 codec A/B** — noise-shaped vs stock JMan2050 on snare `$81`; each vs its same-codec
  reference; noise-shaped ≥ stock on transient sharpness (4-10 kHz spectral centroid).
- **L5 FM6** — fire `$E2` while FM6 holds a note; FM6 coasts (dedicate) or cleanly keys-off+returns
  (adaptive) with `$2A` passing through `$80` at both edges.
- **L6 rate** — `$2A` cadence steady at the new rate; **correct-reg verified in Exodus** (the venue
  that caught the original wrong-reg bug); MT regression unchanged; ring-lead survives worst-case DMA
  at the new rate. No real hardware available — real-HW confirmation is a future nicety.

---

## 7. Build order (incrementally verifiable layers)

0. **RAM + descriptor groundwork.** Delete dead 1B state fields + the `SND_LOOP_OFS/$16FF`
   landmine; lay out the clean DAC state block (§3.2); add `SND_DEC_ACC/SND_DAC_PHASE/SND_SONG_BANK`;
   extend `DacSample` to 9 bytes (`ds_table`); update asserts. No behavior change; build green.
1. **One-shot stop state machine.** Replace the unconditional blip re-loop
   (`z80_sound_driver.asm:414-420`) with the two-stage exhaust (`DRAINING_TAIL` → `STOPPING`). Keep
   the current **raw** FILL (no decode yet). Prove **L0** + **L2** (+ re-trigger).
2. **Encoder + DecTable.** Build `tools/dac_encode.py` (noise-shaped DPCM-HQ) + the `DecTable`
   families; encode kick/snare/hat from the S3K `.wav`.
3. **Decode FILL.** Swap raw FILL for the 1-byte/2-nibble decode (`iy=DecTable+ds_table*16`,
   `SND_DEC_ACC` in RAM, no-clamp wrap). Cycle-count in-assembler; set `SND_LOOP_CYC`; regrow pads.
   Prove **L1** + **L4**.
4. **FM6 dedicate.** Add `$B6=$C0` at start; gate the ch6 key-on while `DAC_ACTIVE` (advance
   bookkeeping); re-key on exhaust. Prove **L5** (dedicate path).
5. **Shared-bank swap.** Brackets B1 (`Run_SeqFrame_OnSongBank`, both tick paths) + B2
   (`Snd_StartSample` stash-only) + B3 (`SndDrv_ISR` bank-transparent) + B4 (`SndDrv_Idle` entry
   latch); add the brackets-present assert; author a DAC-on test song streaming from its own bank
   firing `$E2` (engine tables + SFX blobs co-located in its bank). Prove **L3** (incl. an SFX fired
   mid-drum, per B3).
6. **Raise DAC rate.** Prefix trim (`$2A` re-park on every `$4000`-touch path: ISR, Timer-A frame,
   `SetBank`) + ring re-derivation/widening; target ~18-20 kHz; verify correct-reg + steady cadence
   in Exodus; safe ~8.3 kHz fallback (retain the per-sample re-select). Prove **L6**.
7. **Adaptive FM6 (per-song flag).** The Echo-style toggle (key-off + DC-center + `$2B`, re-key on
   exhaust) behind a per-song flag; **in scope this phase**. (Optional north-star: offline pre-mixed
   composite one-shots for simultaneous kick+snare.) Prove **L5** (adaptive path).

---

## 8. Risks & mitigations

- **Bank-swap correctness is the highest-risk area** ("multi-bank contention is where the bugs
  live"). Mitigated by the explicit B1/B2 brackets, the both-brackets assert, and the
  music-channel-corrcoef gate (not drum-only).
- **Rate-raise residual risk** (no real hardware to confirm on): the `$2A`-latch trim relies on
  documented YM2612 latch-holds behavior and is verified in Exodus (which caught the original
  wrong-reg bug), but Exodus is not a perfect YM2612 model. Isolated to Layer 6, with a clean
  fallback to retaining the per-sample re-select at a modest rate.
- **DMA-survival shrinks with rate:** re-derived in Layer 6; deepen the ring (and widen the pointer
  scheme) if needed.
- **False-positive verification:** every gate is rendered-audio cross-correlation vs a same-codec
  reference — never "non-silent."

---

## 9. Files touched (anticipated)

- `engine/z80_sound_driver.asm` — state machine, decode FILL, two-stage exhaust, B1-B4 brackets,
  `Snd_StartSample`, `SndDrv_TimerATick`/`SndDrv_IdleTick`, `SndDrv_ISR`, `SndDrv_Idle`,
  `DacSampleTable`, `DecTable`, FM6.
- `engine/sound_sequencer.asm` — ch6 voice-writer gate while `DAC_ACTIVE`.
- `sound_constants.asm` — clean DAC state block, 9-byte `DacSample`, `NUM_DELTA_TABLES`, asserts.
- `data/sound/dac_samples.asm` + new shared-bank layout in `main.asm` — co-located tables in the
  test song's bank; the shared DAC payload bank.
- `tools/dac_encode.py` (new), `tools/dac_verify.py` (new), a DEBUG drum-test song + trigger.
- `docs/ENGINE_ARCHITECTURE.md` §6 — document the two DAC banking modes + the rate decision.
```
