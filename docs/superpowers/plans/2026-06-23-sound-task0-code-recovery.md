# Sound Task 0 — Z80 Code-Space Recovery (F5 Table Banking) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover ~900 bytes of Z80 code space (currently **2 bytes** free to the `$16F0`
ceiling) by moving the engine-default lookup tables out of the `phase 0` Z80 blob into a
bank-aligned ROM block read through the `$8000` window, so the later music-expression phases
have room to grow.

**Architecture:** Move `FmPitchTableZ`, `PsgDivisorTableZ`, `LogVolumeLutZ`,
`CarrierMaskTableZ`, the engine-default `MovingTrucks_PitchTable`, and the `PsgVolEnv_*`
tables into a dedicated bank-aligned ROM block (the `align $8000` pattern already used by
`data/sound/dac_samples.asm`). The Z80 reads them via window-relative constants
(`(addr & $7FFF) | $8000`), with **one** `SndDrv_SetBank` swap per `Sequencer_Frame`
(save current bank → set table bank → run frame → restore). This is correct for the
production **COPY** song path (FM6=DAC, e.g. Moving Trucks — stream+patch live in Z80 RAM,
so the window is free during the frame). The **STREAM** path (FM6=FM) is guarded and
deferred (no STREAM songs exist yet).

**Tech Stack:** Z80 + 68000 assembly, AS Macro Assembler (`asw`), the custom Z80 sound
driver. Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`. Verify: rendered audio via
Exodus VGM → `vgm2wav` (NOT register streams), the DEBUG golden self-test, and `Lag_Frame_Count`.

---

## Context the engineer needs (read before starting)

- **The Z80 driver is assembled inline** into the ROM as a `phase 0` blob inside
  `engine/z80_sound_driver.asm` (`save` / `cpu z80` / `phase 0` at :36; `dephase` at :1172;
  `Z80_Sound_End` / `Z80_SOUND_SIZE` at :1174-1176; the ceiling assert vs `SND_STATE_BASE`
  = `$16F0` at :1179). The blob `include`s, in order: `sound_sequencer.asm` (:1081),
  `sound_sfx.asm` (:1088), `sound_fm.asm` (:1097), `sound_psg.asm` (:1106),
  `sound_tables_z80.asm` (:1112), `data/sound/movingtrucks_pitchtable.asm` (:1122).
- **Bank/window addressing** (from `sound_constants.asm:224-226`, the `DacSample` struct):
  `bank = (addr & $7F8000) >> 15`, `window_ptr = (addr & $7FFF) | $8000`.
- **`SndDrv_SetBank`** (`z80_sound_driver.asm:659-677`): in `a` = bank id; cache-gated on
  `SND_CUR_BANK` (`cp (hl) / ret z`); writes the `$6000` 9-bit latch LSB-first. Touches only
  `$6000` (DMA-safe; never the YM, never the `$2A` DAC park).
- **`Sequencer_Frame`** runs from `SndDrv_TimerATick` (`z80_sound_driver.asm:694-696`),
  inside the DAC loop's `di` window. On entry the current bank is the DAC sample bank (COPY
  songs) — the window is otherwise unused that frame, so it is free to repoint at the table
  bank and restore before the FILL dispatch resumes (`.afterPoll`).
- **The bank-aligned ROM precedent** is `main.asm:236-294`: `align $8000` snaps to a 32 KB
  bank start; `data/sound/dac_samples.asm` and the song streaming block both use it, with a
  build assert that the block does not cross a bank boundary.
- **The 7 read sites** that must switch to window-relative addressing:
  `sound_fm.asm:351` (`LogVolumeLutZ`), `:396` (`CarrierMaskTableZ`), `:640`
  (`MovingTrucks_PitchTable`), `:669` (`FmPitchTableZ`); `sound_psg.asm:125`
  (`PsgVolEnv_Ids`), `:126` (`PsgVolEnv_Ptrs`), `:159` (`PsgDivisorTableZ`). The per-song
  table pointer (`Snd_PitchTabPtr`, `sound_fm.asm:636`) is ALREADY a window pointer — no change.
- **No table read happens outside `Sequencer_Frame` scope** (verified by read-site audit) —
  confirm with a grep in Task 1 before relying on it.

---

## File structure

- `sound_constants.asm` — add build-time `snd_bank()`/`snd_win()` `function` helpers; add the
  `Snd_SavedSeqBank` RAM byte + the `SND_TABLE_BANK` selector; the trace-ring rebase.
- `main.asm` — add the `align $8000` table bank block + its includes; a no-cross-boundary assert.
- `engine/z80_sound_driver.asm` — remove the two table `include`s from the blob; add the
  per-`Sequencer_Frame` bank save/set/restore in `SndDrv_TimerATick`.
- `engine/sound_fm.asm`, `engine/sound_psg.asm` — switch the 7 read sites to `snd_win(Table)`.
- `engine/sound_tables_z80.asm`, `data/sound/movingtrucks_pitchtable.asm` — the table bodies
  move from "included in the blob" to "included in the ROM bank block" (the files themselves
  may be unchanged; only WHERE they are `include`d changes).
- `docs/DEFERRED_WORK.md` — record the STREAM-song banking constraint.

---

## Task 1: Build-time addressing helpers + verify the read-site invariant

**Files:**
- Modify: `sound_constants.asm` (near the other `function` defs, ~:145)

- [ ] **Step 1: Confirm no table read runs outside `Sequencer_Frame`**

Run:
```bash
cd /home/volence/sonic_hacks/s4_engine
grep -rnE "call[[:space:]]+(Fm_NoteOn|Fm_NoteFromTable|Fm_SetVolume|Psg_NoteOn|PsgVolEnv_Resolve)" engine/*.asm
```
Expected: every caller is reachable only from `Sequencer_Frame`/`ModUpdate`/`Sequencer_Channel`
(the per-frame engine). If ANY caller is in the ISR (`SndDrv_PollMailbox`, `Snd_LoadSong`) or
the DAC loop, STOP — that read would not be covered by the per-frame bank swap; note it and
revise (that site needs its own save/set/restore). This gates the whole approach.

- [ ] **Step 2: Add the addressing `function` helpers**

In `sound_constants.asm`, after the existing `function` block (~:147), add:
```
; --- ROM-address -> Z80 bank/window helpers (build-time; emit no bytes) ---
snd_bank        function addr, ((addr) & $7F8000) >> 15      ; 9-bit bank id
snd_win         function addr, ((addr) & $7FFF) | $8000      ; Z80 $8000-window ptr
```

- [ ] **Step 3: Build to verify the helpers assemble (no behavior change)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: `Build complete: s4.bin` (exit 0). `function` defs emit no bytes, so
`Z80_SOUND_SIZE` is unchanged.

- [ ] **Step 4: Commit**

```bash
git add sound_constants.asm
git commit -m "feat(sound): add snd_bank/snd_win build-time ROM-window helpers (F5 prep)"
```

---

## Task 2: Capture the Moving Trucks audio baseline (regression oracle)

**Files:** none (verification artifact only)

- [ ] **Step 1: Build the current ROM (pre-banking)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0.

- [ ] **Step 2: Capture a Moving Trucks VGM and render to WAV (the baseline)**

Load `s4.bin` in the Exodus emulator (user/MCP), trigger Moving Trucks, capture a fixed-length
VGM via the Exodus MCP VGM tools, and render it:
```bash
# after capturing e.g. /tmp/mt_baseline.vgm via Exodus MCP:
vgm2wav /tmp/mt_baseline.vgm /tmp/mt_baseline.wav
```
Expected: a `.wav` of the MT loop. Keep `/tmp/mt_baseline.wav` — every banking task below
must reproduce it (energy + spectrum match). This is the regression oracle (we verify rendered
AUDIO, not the key-on stream).

- [ ] **Step 3: No commit** (verification artifact only). Record the baseline path in the task notes.

---

## Task 3: Add the per-Sequencer_Frame table-bank swap (no tables moved yet)

**Files:**
- Modify: `sound_constants.asm` (add `Snd_SavedSeqBank` RAM byte; `SND_TABLE_BANK` selector)
- Modify: `engine/z80_sound_driver.asm:694-696` (`SndDrv_TimerATick`)

- [ ] **Step 1: Reserve a RAM byte for the saved bank + name the table bank**

In `sound_constants.asm`, beside `Snd_SavedDacBank` (~:975), add:
```
Snd_SavedSeqBank   = Snd_SongBase + 2     ; 1 byte: bank saved across the per-frame table swap
```
(Place it after `Snd_SongBase` (2 bytes); adjust the following symbol's base by 1. Verify it
stays below `SND_SEQ_TRACE`.) `SND_TABLE_BANK` is defined in Task 4 once the bank block exists;
for now reference it as a forward symbol.

- [ ] **Step 2: Wrap `Sequencer_Frame` with save → set table bank → restore**

In `engine/z80_sound_driver.asm` `SndDrv_TimerATick` (:694), change:
```z80
SndDrv_TimerATick:
        call    Snd_TimerA_Rearm
        call    Sequencer_Frame
```
to:
```z80
SndDrv_TimerATick:
        call    Snd_TimerA_Rearm
        ld      a, (SND_CUR_BANK)        ; save the live bank (DAC sample bank on COPY songs)
        ld      (Snd_SavedSeqBank), a
        ld      a, SND_TABLE_BANK        ; point the $8000 window at the engine table bank
        call    SndDrv_SetBank           ; cache-gated; 9 writes only on a real change
        call    Sequencer_Frame
        ld      a, (Snd_SavedSeqBank)    ; restore before the FILL dispatch resumes
        call    SndDrv_SetBank
```
(Leaves the rest of `SndDrv_TimerATick` — the `de=$4001` restore and lead recompute — intact.)

- [ ] **Step 3: Build (tables still inline — swap is harmless on COPY songs)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0. `Z80_SOUND_SIZE` grows slightly (the ~10-byte swap), still ≤ `$16F0` — if it
overruns, temporarily comment one table `include` to fit, since Task 4+ frees it; note it.

- [ ] **Step 4: Render-verify Moving Trucks unchanged**

Rebuild, capture MT VGM → `/tmp/mt_t3.wav`, compare to baseline:
```bash
vgm2wav /tmp/mt_t3.vgm /tmp/mt_t3.wav
# compare energy + spectrum (existing tooling, e.g. tools/vgm_*.py or a wav-compare helper)
```
Expected: energy + spectrum match `/tmp/mt_baseline.wav` (the swap repoints an unused window on
COPY songs). Also: DEBUG **golden self-test** passes at boot (no assertion halt).

- [ ] **Step 5: Commit**

```bash
git add sound_constants.asm engine/z80_sound_driver.asm
git commit -m "feat(sound): per-Sequencer_Frame table-bank swap (COPY path; F5 enabler)"
```

---

## Task 4: Create the bank-aligned table block; move FmPitchTableZ first

**Files:**
- Modify: `main.asm` (after the DAC sample block, ~:240) — add the table bank block
- Modify: `engine/z80_sound_driver.asm:1112` — stop including the tables in the blob
- Modify: `engine/sound_fm.asm:669` — `FmPitchTableZ` read → window-relative

- [ ] **Step 1: Add the bank-aligned table block in `main.asm`**

After the DAC sample include (`main.asm:240`), add:
```
; --- Engine-default sound tables (F5): bank-aligned, read via the Z80 $8000 window ---
        align   $8000                          ; snap to a 32KB bank start (no boundary cross)
SoundTableBank_Start:
        include "engine/sound_tables_z80.asm"   ; FmPitchTableZ, PsgDivisorTableZ, LogVolumeLutZ,
                                                ; CarrierMaskTableZ, PsgVolEnv_Ids/Ptrs/bodies
        include "data/sound/movingtrucks_pitchtable.asm" ; engine-default pitch table
SoundTableBank_End:
        if (SoundTableBank_End & $7F8000) <> (SoundTableBank_Start & $7F8000)
          error "Sound table bank crosses a 32KB bank boundary"
        endif
SND_TABLE_BANK = snd_bank(SoundTableBank_Start)
```

- [ ] **Step 2: Remove the table includes from the Z80 blob**

In `engine/z80_sound_driver.asm`, delete the two `include` lines inside `phase 0`:
`include "engine/sound_tables_z80.asm"` (:1112) and
`include "data/sound/movingtrucks_pitchtable.asm"` (:1122). The labels now resolve to the
68k ROM addresses in the bank block (one AS pass — the `phase 0` code can reference them).

- [ ] **Step 3: Switch the FmPitchTableZ read to window-relative**

In `engine/sound_fm.asm:669`, change:
```z80
        ld      de, FmPitchTableZ
```
to:
```z80
        ld      de, snd_win(FmPitchTableZ)   ; banked: $8000 window (table bank set per-frame)
```

- [ ] **Step 4: Build and confirm the size drop**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0. (Optional: re-add the temporary `message "ZMEASURE ..."` after
`Z80_SOUND_SIZE` (`z80_sound_driver.asm:1176`) to confirm the blob shrank by ~924 bytes — ALL
tables left the blob in Step 2 — then remove it.) Headroom should jump from 2 to ~900 bytes.

- [ ] **Step 5: Render-verify Moving Trucks unchanged**

Rebuild, capture MT VGM → `/tmp/mt_t4.wav`, compare to baseline. Expected: energy + spectrum
match (FmPitchTableZ reads now come through the window, with the table bank set per-frame).
Golden self-test passes.

- [ ] **Step 6: Commit**

```bash
git add main.asm engine/z80_sound_driver.asm engine/sound_fm.asm
git commit -m "feat(sound): bank engine sound tables out of the Z80 blob; FmPitchTableZ via window"
```

---

## Task 5: Window-relative reads for the remaining FM/PSG tables

**Files:**
- Modify: `engine/sound_fm.asm:351,396,640`
- Modify: `engine/sound_psg.asm:125,126,159`

- [ ] **Step 1: Switch the FM volume/carrier/default-pitch reads**

In `engine/sound_fm.asm`:
- `:351` `ld de, LogVolumeLutZ` → `ld de, snd_win(LogVolumeLutZ)`
- `:396` `ld de, CarrierMaskTableZ` → `ld de, snd_win(CarrierMaskTableZ)`
- `:640` `ld hl, MovingTrucks_PitchTable` → `ld hl, snd_win(MovingTrucks_PitchTable)`

(Do NOT touch `:636` `ld hl, (Snd_PitchTabPtr)` — that pointer is already a window ptr set by
the loader.)

- [ ] **Step 2: Switch the PSG table reads**

In `engine/sound_psg.asm`:
- `:125` `ld hl, PsgVolEnv_Ids` → `ld hl, snd_win(PsgVolEnv_Ids)`
- `:126` `ld de, PsgVolEnv_Ptrs` → `ld de, snd_win(PsgVolEnv_Ptrs)`
- `:159` `ld de, PsgDivisorTableZ` → `ld de, snd_win(PsgDivisorTableZ)`

> Note: `PsgVolEnv_Ptrs` holds POINTERS to the env bodies. Those bodies are now in the table
> bank too, so the stored pointers must also be window-relative. Verify how `PsgVolEnv_Ptrs`
> entries are emitted in `sound_tables_z80.asm` — if they use raw `dw Body`, wrap each as
> `dw snd_win(Body)` so the dereference (`PsgVolEnv_Resolve` → body ptr) lands in the window.

- [ ] **Step 3: Build**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0.

- [ ] **Step 4: Render-verify Moving Trucks AND exercise PSG**

Rebuild; capture MT → compare to baseline (MT uses FM + PSG). If MT does not exercise a PSG
volume envelope, additionally trigger any SFX/PSG content that does, and confirm it sounds
correct (PSG envelope bodies now read via the window). Golden self-test passes.

- [ ] **Step 5: Commit**

```bash
git add engine/sound_fm.asm engine/sound_psg.asm
git commit -m "feat(sound): remaining FM/PSG table reads via the $8000 window (F5)"
```

---

## Task 6: Data-region rework — trace ring tracks SND_SEQ_END

**Files:**
- Modify: `sound_constants.asm:954` (`SND_SEQ_TRACE`) + the FM-scratch/trace asserts (~:964-971)

- [ ] **Step 1: Rebase the trace ring above the (future-growable) channel array**

In `sound_constants.asm`, change the hardcoded trace base:
```
SND_SEQ_TRACE      = $1A00
```
to track the end of the per-channel block (so a later `SeqChannel_len` growth slides it up
automatically, into the currently-unused `$1A20-$1AFF` gap):
```
SND_SEQ_TRACE      = SND_FM_SCRATCH + SND_FM_SCRATCH_LEN   ; tracks SND_SEQ_END (auto-grows)
```
Add an assert that it still clears the song buffer:
```
        if (SND_SEQ_TRACE + SND_SEQ_TRACE_LEN) > SND_SONG_BUF
          fatal "trace ring runs into the song buffer at \{SND_SONG_BUF}"
        endif
```
(Update the existing FM-scratch "runs into the trace ring" assert at ~:970 if it referenced the
literal `$1A00`.)

- [ ] **Step 2: Build (no struct growth yet — this is a behavior-preserving rebase)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0. With `SeqChannel_len` unchanged, the trace ring lands at ~`$19BA` (right
after the scratch, as before) — identical layout, but now parameterized. The DEBUG trace ring
still functions (golden self-test + any trace-dependent debug intact).

- [ ] **Step 3: Render-verify + commit**

Rebuild, MT render-compare to baseline (unchanged). Then:
```bash
git add sound_constants.asm
git commit -m "feat(sound): trace ring tracks SND_SEQ_END (frees the channel-array growth path)"
```

---

## Task 7: Final verification, STREAM-song guard, and documentation

**Files:**
- Modify: `docs/DEFERRED_WORK.md`
- Modify: `docs/superpowers/specs/2026-06-23-music-expression-engine-design.md` (status note)

- [ ] **Step 1: Confirm the recovered headroom**

Temporarily add after `Z80_SOUND_SIZE` (`z80_sound_driver.asm:1176`):
```
        message "ZMEASURE Z80_SOUND_SIZE=\{Z80_SOUND_SIZE} headroom=\{SND_STATE_BASE - Z80_SOUND_SIZE}"
```
Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | grep ZMEASURE`
Expected: `headroom` ≈ 900 (was 2). Then REMOVE the `message` line and rebuild.

- [ ] **Step 2: STREAM-song guard (concrete)**

The per-frame table-bank swap (Task 3) is only correct when the window is otherwise free during
the frame (COPY songs). Make the swap conditional and DEBUG-assert the unsupported case:
1. In `engine/z80_sound_driver.asm` `SndDrv_TimerATick` (Task 3 Step 2), gate the swap on the
   COPY-mode flag the loader already sets (the FM6=DAC / `SH_F_STREAM`-clear state — read the
   bit `Snd_LoadSong` tested at its PATH A/B branch). Only `SetBank SND_TABLE_BANK` when COPY:
   ```z80
        ld      a, (SND_SEQ_ACTIVE)      ; (or the cached stream-mode flag set at load)
        ; ... test the COPY/STREAM bit; skip the swap block entirely if STREAM ...
   ```
2. In `Snd_LoadSong`'s STREAM (FM6=FM) branch, in DEBUG only, store a sentinel to
   `SND_SEQ_BADOP` (the existing debug "bad" marker) so a STREAM song surfaces loudly that the
   banked engine tables are not available to it yet. Production simply does not swap (the
   STREAM song reads its own bank; the engine-default tables it relies on are the deferred item).
   Comment both sites referencing the DEFERRED_WORK entry from Step 3.

- [ ] **Step 3: Record the deferral in DEFERRED_WORK.md**

Add under the sound section:
> **STREAM-song table banking (deferred).** Task 0's per-`Sequencer_Frame` table-bank swap is
> correct for COPY songs (FM6=DAC; the production path). STREAM songs (FM6=FM) read their
> stream/patch through the same `$8000` window during the frame, conflicting with the table
> bank. No STREAM songs exist yet. When authored: either carry the needed tables in the song's
> bank, or use per-access save/restore swaps (cache-gated `SndDrv_SetBank`). Guarded in
> `Snd_LoadSong` (Task 0).

- [ ] **Step 4: Full regression gate**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (exit 0).
- MT renders energy+spectrum-identical to `/tmp/mt_baseline.wav`.
- DEBUG golden self-test passes at boot.
- `Lag_Frame_Count` (0xFF89F8) shows no new steady-state lag with music playing (the one
  bank swap/frame is ~tens of cycles, absorbed by the 250-sample ring lead).

- [ ] **Step 5: Update the spec status + commit**

In the spec (§9.3), mark the F5 recovery DONE with the measured headroom. Then:
```bash
git add docs/DEFERRED_WORK.md docs/superpowers/specs/2026-06-23-music-expression-engine-design.md
git commit -m "docs(sound): record F5 code recovery done (~900B), STREAM-song banking deferral"
```

- [ ] **Step 6: Merge the Task 0 branch to master**

After full verification, fast-forward/merge the Task-0 feature branch to `master` (the
expression phases build on it). Confirm master builds clean with sound flags.

---

## Self-Review notes (author)
- **Spec coverage:** implements spec §9.3 (F5 code recovery) + §9.2 (data-region rework /
  trace-ring rebase). The per-channel struct GROWTH (§9.1) is intentionally deferred to the
  spine/T1 plan (it consumes the space this task frees) — Task 6 only parameterizes the trace
  ring so that growth "just works" later.
- **Risk:** banking is the riskiest recovery; mitigated by (a) moving one table first (Task 4)
  with a render-gate, (b) the COPY-path scoping + STREAM guard, (c) MT render regression after
  every task, (d) the read-site invariant check in Task 1 Step 1.
- **Naming consistency:** `snd_win()`/`snd_bank()` helpers, `SND_TABLE_BANK`,
  `Snd_SavedSeqBank`, `SoundTableBank_Start/End` used identically across tasks.
- **Open confirm-at-execution:** Task 1 Step 1 (no out-of-frame reads) and Task 5 Step 2 note
  (`PsgVolEnv_Ptrs` body pointers must be `snd_win()`-wrapped) are the two places to verify
  against live source before relying on them.
