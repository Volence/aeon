# Handoff: DAC Drum phase — resume at Layer 4

**Date:** 2026-06-24 (continuation of the DAC-drum / DAC-format-revision phase)
**For:** the fresh agent picking up the remaining layers.
**Start by reading:** memory `project_dac_drum_phase.md` (full state + every decision + the verification
method + the build-bug fix), then the spec + plan below. This note is the crisp entry point.

## State of the world

- **Branch `feat/dac-drum`** in the SIBLING worktree `/home/volence/sonic_hacks/aeon-dacdrum`.
  Master is untouched. Spec + plan are on master.
- **Layers 0-3 are DONE and VERIFIED.** The DAC drum path builds and the DPCM decode is proven correct.
  - L0 clean DAC RAM state block + 9-byte descriptor.
  - L1 two-stage one-shot stop state machine + DEBUG trigger. Also fixed a latent `Snd_StartSample`
    bug (read descriptor before `SndDrv_SetBank`, which clobbers `hl`).
  - L2 noise-shaped DPCM-HQ encoder (`tools/dac_encode.py`) + inline DecTable + S3K kick/snare/hat.
  - L3 constant-cost DPCM decode FILL + cycle rebalance (`SND_LOOP_CYC` 587 → ~6098 Hz).
    Committed WIP `04fe3be`; verified correct (ring r=0.983, full+correct mid-play, DAC-bus audio).
- **THE BUILD INFINITE-LOOP IS FIXED** (`3eb1a84`): `asl` was infinite-looping (warning #80, FmPitchTable
  oscillating) on the DEAD 68k duplicate tables `sound_tables.asm`/`fm_patches.asm`. Removed their
  includes from `main.asm`. Build now ~1s. **Diagnose any future build hang with `asl -r`.**

## CRITICAL gotchas (don't relearn these the hard way)

1. **Build flag:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (a plain build excludes ALL sound).
2. **ALWAYS wrap builds in a hard `timeout`** (`timeout 180 bash -c '...build.sh'`) — asl CAN
   infinite-loop on certain layouts; an unwrapped build can hang for hours. Check `ps -o etime,pcpu`
   for `asl` at ~97% CPU = infinite loop; `asl -r` names the oscillating symbol.
3. **Worktree tools:** `tools/bin` must be an **ABSOLUTE** symlink to the main checkout's `tools/bin`
   (a relative symlink resolves wrong and breaks the salvador build). `tools/asl` + `tools/salvador`
   are already set up in this worktree. NATIVE toolchain (no Wine).
4. **VERIFY by the RING READ + frame-step, NOT the VGM `$2A` xcorr.** The idle loop floods `$2A=$80`
   and overwhelms the emulator's VGM logger, so the VGM `$2A` capture under-counts the sample (looks
   like a 60% drop — it is NOT; the engine output is correct). Faithful methods:
   - Read the live ring buffer ($1700, 256B) — it IS the decoded PCM fed to the DAC.
   - Catch fast samples mid-play with `emulator_press <neutral button e.g. z> frames=N` (deterministic
     frame-step), then read the ring (samples finish during tool latency at 3× emu speed otherwise).
   - `emulator_audio_spectrum source=fm` = the real DAC-bus audio.
   - Trigger samples directly via the mailbox: `emulator_z80_write $1F01 <id>` (1=blip raw, 2=kick,
     3=snare, 4=hat). Stop MT first with `$1F02=$FF` to avoid bank-conflict (B1-B4 brackets are L5).
5. **No real hardware** — all verification is the `oracle` emulator (never gate on real-HW). Never
   `git add -A` (untracked user WIP + auto-commit daemon on `data/editor/`, `tools/ojz_strip_gen.py`).

## Next steps (in order)

0. **(Recommended first, quick win)** Rate-limit the idle `$2A=$80` writes in `SndDrv_Idle`
   (`engine/z80_sound_driver.asm`) — they're harmless on HW but flood the VGM logger, breaking the
   `$2A`-capture verification, and waste Z80 cycles. Fixing it restores clean rendered-audio
   verification for the rest of the phase. Verify MT + a drum still play (ring read).
1. **Layer 4 — FM6 dedicate-while-active:** `$B6=$C0` stereo at sample start + gate the ch6 voice
   key-on while `DAC_ACTIVE` (advance bookkeeping, skip key-on), re-key on exhaust. Plan Task 4.1.
2. **Layer 5 — shared-bank swap brackets B1-B4** (the crux; spec §3.6) + a STREAM DAC-on test song.
3. **Layer 6 — raise DAC rate** toward ~18-20 kHz (prefix `$2A`-reselect trim, ring re-derivation).
4. **Layer 7 — adaptive FM6 toggle** behind a per-song flag.
5. FF-merge `feat/dac-drum` → master when the phase is done.

## Pointers
- Spec: `docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md`
- Plan: `docs/superpowers/plans/2026-06-24-dac-drum-format-revision.md` (Layers 4-7 = Tasks 4.1-7.1;
  NOTE its Task-0.0 worktree symlink commands are wrong — use an absolute `tools/bin` symlink).
- Memory: `project_dac_drum_phase.md`, `reference_no_real_hardware.md`,
  `feedback_visible_progress_cadence.md`, `feedback_verify_real_output_not_proxy.md`.
- Verify tooling: `tools/dac_verify.py` (note the VGM caveat above), `tools/dac_encode.py`.
