# Faithful PSG Noise Pitch/Color (HCZ2 hi-hat rate-3 coupling) — Design

**Date:** 2026-06-26
**Branch:** `feat/hcz2-import`
**Status:** approved (design), pending implementation plan
**Research:** `psg-noise-rate3-research` workflow (11 agents: all 8 reference disasms + SN76489 hardware docs + modern drivers/trackers). Verdict: the S3K/SMPS skeleton is correct and hardware-faithful; ship the refined best-in-class form below.

## Problem

HCZ2's PSG noise hi-hat now has correct rhythm + per-hit decay (envelope fix), but the wrong **timbre/color**. S3K plays the hat as SN76489 white noise in **rate-3 mode** (`$E7` = clock the noise from tone-channel-2's frequency, set to `nMaxPSG1`). Our engine emits the control byte but **never writes tone-2's frequency** (`Psg_Noise`, `engine/sound_psg.asm`), so the noise clocks at a stale/default value (oracle-measured: PSG ch2 frequency-latch writes = 0). Two layers:
1. **Engine:** `Psg_Noise` writes only the noise control byte (`$E0|(pitch&7)`) + volume; never the tone-2 (`$C0`) frequency.
2. **Converter:** conflates noise *mode* and *pitch* — it forces the note's pitch to the `smpsPSGform` mode bits and drops the real `nMaxPSG1`, so the engine has no pitch to clock tone-2 with.

## Research findings (cross-source consensus)

- **Frequency cadence — PER-NOTE, unanimous.** Every reference driver that uses SN76489 noise (S.C.E./Flamedriver, sonic_hack/S2, Ristar, Gunstar, Alien Soldier, TF4) writes the note's PSG divisor to **tone-2's frequency latch (`$C0`)** per note-on — that *is* the rate-3 noise clock. The universal idiom is a 2–3 instruction **latch remap inside the shared PSG frequency writer**: detect the noise track (type byte `$E0`) and substitute register `$C0` for `$E0`, then write the standard note divisor.
- **LFSR fact — DEFINITIVE.** Writing the noise **control** register (`$E0–$EF`) **resets the LFSR** (Maxim/SMS-Power + Wikipedia). Writing the **frequency** (`$C0`) or **volume** (`$F0`) does **not**. So per-note frequency writes retune the noise cleanly with no re-trigger artifact.
- **Control cadence — on-change (SMPS) vs per-note (Gunstar/Echo).** SMPS family writes the control byte once via the `cfSetPSGNoise`/`smpsPSGform` zero-tick flag and lets the LFSR free-run, shaping each hit purely with the per-note PSG volume envelope (no per-hit click). Gunstar/Echo re-write control per note-on for a deliberately re-seeded punchy transient. TF4 re-asserts every frame (anti-pattern — 60 Hz LFSR resets).
- **Contention — physical, resolved by time-sharing.** One tone-gen-3 frequency latch is shared between PSG3 melody and the rate-3 noise clock; they cannot run simultaneously. Standard resolution: write the clock to `$C0`, silence tone-2's **volume** (`$DF`, leaving its frequency live), route the hit envelope to noise volume `$F0`. HCZ2 never uses PSG3 melodically, so no conflict.

## Design (refined, best-in-class)

### Engine

**1. New zero-tick opcode `MEV_PSGNOISE` — the SOLE owner of noise mode/rate.**
Operand = the SN76489 control byte (`$E0|mode|rate`, e.g. `$E7`). Handler:
- Store it to a per-channel noise-mode field (for the rate gate + steal re-arm).
- Write it to the PSG port **on-change** (first use; re-armed after an SFX/channel-steal clobber — reuse the existing `sx_saved_note` noise-steal coupling). Not per-note (avoids the LFSR-reset click), not "once" (survives a steal).
- Silence tone-2's **volume** (`$DF`) so ch2 makes no audible tone while clocking the noise.

**2. Noise note = PITCH, folded into the shared PSG note path.**
Remove the old "note low-3 bits = mode" mapping (kill the two-sources-of-truth). A noise note carries a normal pitch (PSG divisor-table index, with transpose). The noise channel reuses the standard PSG note-on path with a **latch remap**: the computed divisor goes to **`$C0`** (tone-2 = the clock) instead of the channel's own latch, and the volume goes to **`$F0`** (noise vol). This reuses the divisor table, transpose, and the per-note volume envelope unchanged.
- Write `$C0` **only when the active mode's rate == 3** (preset rates ignore tone-2; don't perturb PSG3).
- **Clamp the divisor ≥ 1** (hardware misbehaves with tone-3 frequency 0).
- The per-note PSG volume envelope (already shipped) shapes each hit; the LFSR free-runs (seeded once) → natural hi-hat variation, no per-hit click.

### Converter (`tools/smps_import.py`)
- `smpsPSGform $E7` → emit `MEV_PSGNOISE($E7)` (the control byte) instead of folding it into `noise_pitch`.
- Noise notes → carry the **real pitch** (`nMaxPSG1`), with transpose applied (0 for HCZ2), instead of the forced mode bits. Remove the `noise_pitch`/`st.noise` pitch-replacement.
- Regenerate `song_hcz2.asm`.

### Scope / decisions
- **Use rate-3 (`$E7`)** — faithful to S3K's choice for HCZ2. (A preset rate would fix "wrong color" with zero contention but is a *different* color; faithfulness wins. Accept that PSG3 can't be melodic while tuned noise is active — HCZ2 never is.)
- **Defer the per-voice LFSR-cadence flag** (free-running vs per-note re-seed). HCZ2's hat is free-running (the SMPS default); leave a clean hook, don't build the flag (YAGNI).
- **No SFX-noise regression.** SFX noise channels must keep working: the rate-3 `$C0` write is gated to MUSIC channels (the tuned-clock is a music feature); SFX noise (fixed-rate burst) is unaffected.

## Verification
- Oracle VGM (short, chunked captures — the long-run path froze the oracle): PSG ch2 frequency-latch writes go **0 → per-note**; noise color matches S3K (`audio_spectrum` on the isolated noise channel / listen). The blast-detector + decay histogram from the envelope fix stay clean; FM melody + PSG1/2 unaffected.
- Converter unit tests: `smpsPSGform $E7` → `MEV_PSGNOISE($E7)`; a noise note carries the real pitch (not the mode bits).

## Open items for the plan
- **Noise-mode field placement.** SeqChannel is 42 bytes (`sc_psgenv_out` at +41); SfxChannel's +42 is `sc_mod_ctrl`. Decide where `sc_noise_mode` lives without colliding with an SFX field the noise path needs (grow SeqChannel to +42 with the bare alias scoped to SeqChannel, or reuse a field the noise channel never uses). Confirm the music/SFX gate keeps them from cross-reading.
- **Exact routing.** How the PSGN hook reuses the shared divisor path (extract a shared divisor-compute helper from `Psg_NoteOn`, or special-case the latch in `Psg_Noise`). Confirm `PsgDivisorTableZ` covers `nMaxPSG1` ($D3 → index 82).
- **SFX-noise path audit.** Verify the current SFX noise handling (does it use `Psg_Noise`? a fixed rate?) and that moving the music control byte to `MEV_PSGNOISE` + the rate-3 music gate leaves SFX noise byte-identical.
- **Steal re-arm.** Wire the on-change re-write into the existing SFX-restore (`sx_saved_note`) path.
- Z80 headroom is ample (644 bytes free, `Z80_SOUND_SIZE=$146C` vs `$16F0`); the new opcode + remap (~25–40 bytes) fits.
