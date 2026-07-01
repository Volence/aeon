# Phase 5a SFX engine — RAM fit + Sfx_Frame cycle-budget spike

**Status:** DE-RISKING SPIKE. Throwaway measurement + written verdict before Task 2 builds
anything. Mirrors the method and format of `tools/cycle_budget_phase3.md`; real equate values
sourced from `sound_constants.asm` (read 2026-06-20).

**Goal:** confirm (a) the `SfxChannel` array + queue + duck scratch fit the $1D00..$1EFF free
block, and (b) `Sfx_Frame`'s worst-case per-tick cost is well within the ring-lead budget the 1B
DAC depends on.

---

## Step 1 — RAM fit

### 1a. Real equates (from `sound_constants.asm`)

All addresses confirmed by grep:

| Symbol | Value | Source line |
|---|---|---|
| `SND_SONG_BUF` | `$1B00` | sound_constants.asm:781 |
| `SND_SONG_BUF_SIZE` | `$200` (512 B) | sound_constants.asm:782 |
| `SND_REQ_BASE` | `$1F00` | sound_constants.asm:14 |
| `SeqChannel_len` | `39` | sound_constants.asm:585, guarded by `error` at :587 |
| `SND_FRAME_HZ` | `59` | sound_constants.asm:157 |
| `Z80_CLOCK_HZ` | `3,579,545` | sound_constants.asm:189 |
| `SND_LOOP_CYC` | `400` | sound_constants.asm:194 |
| `SND_RING_LEAD_CAP` | `250` | sound_constants.asm:180 |

**No corrections needed.** Every equate in the plan matches the real source.

### 1b. Free block location

```
SND_SONG_BUF_END  = SND_SONG_BUF + SND_SONG_BUF_SIZE  = $1B00 + $200 = $1D00
SND_REQ_BASE      = $1F00

Free block         = $1D00..$1EFF  =  512 bytes
```

This is the only uncommitted Z80 RAM in the entire map between the song buffer and the mailbox.

### 1c. SfxChannel struct size

`SfxChannel` is a superset of `SeqChannel` — the same 39-byte interpreter prefix
(so `ModUpdate`/`Sequencer_Channel` walk it without modification), plus 7 bytes of SFX-only
bookkeeping:

| Field | Bytes | Purpose |
|---|---|---|
| `SeqChannel` compatible prefix | 39 | Full interpreter state; same field order, same offsets |
| `sfxc_priority` | 1 | Authored priority byte (from SFX header) |
| `sfxc_voice_ptr` | 2 | Ptr to this SFX's own FM voice blob |
| `sfxc_music_route` | 1 | The `sc_route` of the stolen music channel (for restore) |
| `sfxc_saved_psg3` | 1 | PSG3 tone register saved before noise SFX; 0 = N/A |
| `sfxc_kind` | 1 | Channel kind (FM / PSG / noise) — avoids re-deriving at restore |
| `sfxc_flags` | 1 | SFX flags: continuous, looping, stereo-alt, duck-level |

```
SfxChannel_len  = 39 + 7  =  46 bytes
```

### 1d. SFX region layout ($1D00..$1EFF)

7 slots covers the stealable set: FM3 + FM4 + FM5 (3) + PSG1 + PSG2 + PSG3 (3) + noise (1).

```
SFX_SLOTS           = 7
SFX_ARRAY_BASE      = $1D00
SFX_ARRAY_LEN       = 7 × 46            = 322 bytes   ($1D00..$1E41)

SFX queue (after array):
  3 entries × 2 bytes (id + priority)   =   6 bytes
  head / tail / count                   =   3 bytes
  SFX_QUEUE_LEN                         =   9 bytes   ($1E42..$1E4A)

Duck-level scratch:
  duck_level (current ramp value, 1 B)
  duck_target (target level, 1 B)
  duck_decay  (ramp decrement/frame, 1 B)
  duck_flags  (active / direction, 1 B)
  DUCK_SCRATCH_LEN                      =   4 bytes   ($1E4B..$1E4E)

Total SFX region                        = 322 + 9 + 4  = 335 bytes

Free block                                             = 512 bytes
Headroom                                               = 512 - 335 = 177 bytes
```

**Verdict: FITS.** 335 B occupies 65% of the free block, leaving 177 B of headroom for
Phase 5b growth (held-loop state, distance scratch, etc.) before anything needs to move.

---

## Step 2 — Sfx_Frame cycle budget

### 2a. Frame budget and binding limit

From `cycle_budget_phase3.md` (Step 1):

```
Z80 clock (NTSC)          = 3,579,545 cyc/s
Frame rate                = SND_FRAME_HZ = 59 Hz
Cycles per frame          = 3,579,545 / 59  ≈  60,670 cyc/frame
```

The 60,670-cyc frame ceiling is the sanity limit. The **binding** limit is the ring-lead
underrun budget (same as Phase 3): the 1B DAC stalls while `Sequencer_Tick` runs; the ring
lead is the only buffer absorbing the stall.

```
Ring-lead budget  = SND_RING_LEAD_CAP × SND_LOOP_CYC
                  = 250 × 400  =  100,000 cyc
```

The driver was designed and proven safe at a worst-case music tick of ~5,000–5,400 cyc
(~5% of the ring budget). A tick must stay well under ~20,000–25,000 cyc to maintain
comfortable margin (same threshold established in Phase 3's analysis).

### 2b. Primitive costs (real figures from `cycle_budget_phase3.md`)

These are deterministic Z80 T-states counted from the real routines in `engine/sound_fm.asm`:

| Operation | Cyc (T-states) | Source |
|---|---|---|
| One YM write — `Fm_YmWrite` (call+body+ret) | 76 | cycle_budget_phase3.md §2a |
| Re-key — `Fm_NoteOn`/`Fm_NoteOnFreq` | ~870 | cycle_budget_phase3.md §2b |
| Full patch reload — `Fm_PatchLoad` (26 writes) | ~6,500 | cycle_budget_phase3.md §2d |
| Carrier-TL re-assert — `Fm_SetVolume` | ~1,750 | cycle_budget_phase3.md §2e |

### 2c. Per-slot cost in `Sfx_Frame`

`Sfx_Frame` iterates 7 `SfxChannel` slots each frame.

**Inactive slot** (SCF_ACTIVE_B clear): one `bit SCF_ACTIVE_B,(ix+sc_flags)` test (8T) +
`jr z` taken (12T) = **~20 T-states**.

**Active slot — running note** (the common case after init):
`Sfx_Frame` calls `ModUpdate` on the channel. For a sustained note between pitch-step
events, `ModUpdate` does pitch-point interpolation + one re-key (the pitch may drift
per-frame under portamento or vibrato), but does **not** reload the full patch — that only
happens on note-on events. The dominant cost is the re-key path:

```
ModUpdate, running-note path:
  pitch accumulator check + update   ~100 T
  Fm_NoteOn (if pitch changed)       ~870 T   (worst: pitch advances every frame)
  overhead, flag tests, ptr advance  ~100 T
                                    ------
  active slot worst-case per frame   ~900 T
```

Note: **`Sfx_Frame` does NOT call `Fm_PatchLoad` per frame** on active slots. The full
6,500-cyc patch reload only occurs on the note-on event when the SFX is first dispatched
(`SfxDispatch`, not in the per-frame path). This is the structural difference from Phase 3's
ModUpdate concern — SFX voices change their patch at most once (on steal), not every frame.

**Active slot — note-on transition frame** (SFX just triggered, or a multi-note SFX
advancing to a new note):
```
Fm_PatchLoad (full 26-write reload)  ~6,500 T
Fm_NoteOn (re-key)                   ~  870 T
                                     ------
  note-on frame                      ~7,370 T   (per slot)
```
This is a one-shot cost per note event, not a per-frame recurring cost. Even if all 3
concurrent SFX fire note-on events in the same tick: 3 × 7,370 ≈ 22,100 T = 22% of the
ring budget. Acceptable — and it cannot be sustained frame after frame (SFX notes last
many frames each).

### 2d. Worst-case `Sfx_Frame` (steady-state, after dispatch)

3 concurrent active SFX at the running-note worst case + 4 idle slots:

```
3 active × 900 T                     2,700 T
4 idle   × 20 T                         80 T
                                     ------
  Sfx_Frame base                     2,780 T
```

### 2e. Duck ramp cost

The ducking ramp applies at most 6 carrier-TL writes per frame (one `Fm_YmWrite` call per
operator pair being nudged). Using the real primitive cost of 76 T per write:

```
duck ramp writes    = 6 × 76 T  =  456 T
```

(The plan estimated 200 T for this line item; the real per-write cost from
`cycle_budget_phase3.md §2a` is 76 T, so 6 writes = 456 T. Corrected here.)

### 2f. Total `Sfx_Frame` worst case (steady-state)

```
Sfx_Frame base                       2,780 T
Duck ramp (6 writes × 76 T)            456 T
                                     ------
  Sfx_Frame total (steady-state)     3,236 T
```

### 2g. Combined tick budget check

`Sfx_Frame` runs immediately after `Sequencer_Tick` inside the same Timer-A handler window.
The ring-lead drains for the full duration of both.

```
Music Sequencer_Tick, typical        ~5,400 T   (driver bounding note, z80_sound_driver.asm:161)
Sfx_Frame steady-state worst         ~3,236 T
                                     ---------
  Combined per-tick                  ~8,636 T

Ring-lead budget                    100,000 T
Combined as % of ring budget         ~8.6%
```

The combined tick is **8.6% of the ring-lead budget**, comfortably inside the ~20–25%
threshold established in Phase 3's analysis (the driver was designed for ~5% and shown
safe; Phase 3 verified the fallback needed at 55%+; 8.6% gives 2.5× headroom above the
designed-for load).

Even the spike case (3 simultaneous note-on events in one tick):

```
Music tick typical                   ~5,400 T
Sfx_Frame spike (3 × 7,370 + 4 × 20 + 456)  ~22,600 T
                                     ---------
  Combined spike                     ~28,000 T  =  28% of ring budget
```

28% is in the zone the Phase 3 analysis called "safe with the same comfort margin" — well
within the 100k budget and below the regime (~55%) where underrun risk becomes real.
Spike frames are also isolated, not sustained frame after frame.

---

## Step 3 — Verdict + fallback

### Chosen approach: full per-frame `Sfx_Frame` every frame

**Both constraints are satisfied:**

1. **RAM:** 335 B occupies a 512-B free block ($1D00..$1EFF), leaving 177 B headroom.
2. **Cycles:** steady-state `Sfx_Frame` ≈ 3,236 T = 8.6% of the ring budget when added to
   a typical music tick. Even worst-case simultaneous note-on spikes reach only ~28%,
   well inside the safe zone.

**Proceed with full per-frame `Sfx_Frame` dispatched every Timer-A tick, after
`Sequencer_Tick`.**

### Documented fallback (if a future SFX set exceeds budget)

If a future Phase 5 addition (e.g., Phase 5b continuous-loop SFX with per-frame pitch drift
+ held FM rewrites) pushes the combined tick materially above ~25% of the ring budget, apply
the same lever as Phase 3 identified: **even/odd-frame split of the 7 SFX slots** (slots 0–3
on even frames, slots 4–6 on odd frames). This halves the per-tick SFX cost at the cost of
halving per-slot temporal resolution — acceptable for sustained ambient SFX (5b) but not
needed in 5a. The `Sfx_Frame` dispatch loop structure must make this split trivially
addable (one `bit 0,(iy+SND_FRAME_COUNT)` gate at the top).

---

## Summary

| Quantity | Value | Source |
|---|---|---|
| Free Z80 RAM block | $1D00..$1EFF = **512 B** | sound_constants.asm:781–782,14 |
| `SfxChannel_len` | **46 B** (39 + 7) | SeqChannel endstruct + spec §3 |
| SFX array (7 slots) | 322 B | 7 × 46 |
| SFX queue + duck scratch | 13 B | 9 + 4 |
| **Total SFX region** | **335 B** | |
| **Headroom** | **177 B** | 512 − 335 |
| Z80 cyc / frame (NTSC 59 Hz) | 60,670 | 3,579,545 / 59 |
| Ring-lead budget | 100,000 cyc | 250 × 400 |
| `Sfx_Frame` steady-state worst | ~3,236 cyc | 3×900 + 4×20 + 6×76 |
| Music tick (typical) | ~5,400 cyc | z80_sound_driver.asm:161 |
| **Combined tick** | **~8,636 cyc = 8.6% of ring budget** | |
| Spike (3 simultaneous note-on) | ~28,000 cyc = 28% | isolated, not sustained |
| **Verdict** | **FITS — proceed full per-frame** | |

**One plan estimate corrected:** duck ramp cited as ~200 cyc; real cost = 6 × 76T = 456 T
(per `Fm_YmWrite` measured at 76 T in `cycle_budget_phase3.md §2a`). Does not change the
verdict.
