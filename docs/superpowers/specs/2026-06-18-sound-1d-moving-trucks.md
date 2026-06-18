# Sound Plan 1D — Faithful "Moving Trucks" Port (B&R Zyrinx) + the engine features it needs

**Date:** 2026-06-18
**Status:** Design approved (2026-06-18, user delegated section approvals + autonomous execution)
**Branch:** `feat/sound-1d`
**Builds on:** 1C (FM+PSG music sequencer, event-list format v0, Timer-A tick, FmPatch) — merged to master.

## 1. Goal

Play **"Moving Trucks"** (The Adventures of Batman & Robin, Genesis; Zyrinx "Advanced Z80
Player", music Jesper Kyd) **faithfully** on our engine — all 6 FM voices, the real Zyrinx
instruments, panning, and volume dynamics — by **transcoding the already-decoded song** into our
v0 format and adding the small-but-proper engine features it needs. This is a demo *and* a real
stress test of our FM playback against a renowned, FM-heavy soundtrack. Fidelity is verified
objectively by **diffing our YM2612 register-write stream against the original B&R VGM capture**
(`song_05.vgm`) — not by ear alone.

This is a port of the user's own locally-decoded game data into the user's own engine, as a
demo/test to validate the sound engine. No driver code is copied — only data is transcoded
through new format-translation tooling.

## 2. Why Moving Trucks ports cleanly (profile)

From the decoded data (`decoded_full/05_Moving_Trucks.txt`, `megadaw_export/05_Moving_Trucks.json`):
- **269 `PITCH_1` (plain single notes), ZERO `PITCH_2–5`** → no vibrato/trills/arpeggio pitch
  envelopes to reproduce. This is the key reason it's portable to our minimal v0.
- **FM-only** — no PSG, no PCM/DAC drums in the decode. No sample extraction, no PSG work.
- Only `VOL_1` (level+duration, 19×), light panning (`PAN_*`, 16×), sparse FM op-modulation
  (`OP1/3/4`, ~57×), 35 distinct instruments, ~6 active FM channels (ch0–5; ch6 is a 1-pattern stub).

So Moving Trucks skips exactly the features our v0 cannot do (pitch envelopes, PCM). The only real
engine gap is the **6th FM voice** (we permanently dedicate FM6 to the DAC). The rest is a
transcoder plus two small, properly-designed opcodes.

## 3. Fidelity strategy (decided): port known → verify → deepen

1. Port everything well-understood faithfully: notes, the 35 real instruments, panning, all 6 FM
   voices, volume levels, tempo.
2. **Verify by VGM diff** against `song_05.vgm`: our YM register stream (voice loads `$30–$8E`,
   F-number `$A0–$A6`, key-on `$28`, TL `$40`, pan `$B4`) vs the original's, aligned in time.
3. **Deepen only where the diff shows it matters:** the untraced `OP1–4` op-modulation and the exact
   `VOL_1` envelope behavior are traced from the disassembled driver (`z80_driver.bin`,
   `z80_disasm.py`) **only if** they cause audible/measurable divergence. Don't guess; don't
   over-invest in inaudible internals.

## 4. The Zyrinx → v0 mapping (the transcoder contract)

The transcoder consumes the **already-decoded** Moving Trucks (resolving the pattern→sequence
structure into flat per-channel event streams) + `voices.json`, and emits a v0 song (via the
existing `song_packer` `SongDesc`) + a translated FM-patch bank.

**Notes.** Zyrinx note 0–127 (octave = note/12, semitone = note%12). Our pitch index = MIDI−12
(semitone 0 = C0). The exact octave base offset is **calibrated against the reference VGM**: for a
known note event, our generated F-number (via `FmPitchTable`) must match the original's `$A0/$A4`
writes. Pattern/song pitch-transpose (signed semitones) is applied before lookup; out-of-range
notes are clamped + logged.

**Voices (Zyrinx 30-byte → our 26-byte `FmPatch`).** Same YM register structure:
- Zyrinx[0] FB/ALG → `fp_alg_fb` (`$B0`; identical bit layout: fb bits5-3, alg bits2-0).
- Zyrinx[25] AMS/FMS/pan → `fp_lr_ams_fms` (`$B4`); L/R bits come from the song's pan (or forced on).
- Zyrinx[1–4] DT/MUL, [5–8] TL, [9–12] KS/AR, [13–16] AM/D1R, [17–20] D2R, [21–24] SL/RR → our six
  4-byte op arrays for `$30/$40/$50/$60/$70/$80`, **reordered** from Zyrinx operator order into our
  physical-register order [S1,S3,S2,S4]. **The reorder is verified byte-exact against the reference
  VGM's voice-load register writes** (the original driver's `$30–$8E` writes are ground truth — our
  `Fm_PatchLoad` must reproduce them). Zyrinx[26–29] "ext" bytes are dropped (purpose untraced; the
  VGM diff confirms they don't drive register writes — if they do, T6 traces them).

**Tempo.** Zyrinx Timer-B base (format code `$34/$38/$40/$48`, events/sec = 60×16/base; Moving Trucks
= `$38` standard) → our Timer-A tempo byte. Computed so our tick rate matches the original's
events/sec; pattern `tempo_delta` overrides applied. Verified by tick-rate + note-onset timing in the
diff.

**Structure.** Flatten patterns (expand `repeat`, apply per-pattern `pitch_transpose`/`tempo_delta`,
concatenate per channel) into our flat per-channel streams with `LoopPoint`/`Jump` at the song's
loop-back point (header `loop_point`).

**Channels.** Zyrinx ch0–5 → our FM1–FM6 (FM6 via the adaptive slot, §5.1). The trivial ch6 stub is
dropped (or merged) and logged. Pan/volume/voice events route per channel.

## 5. Engine features (best-possible, each a clean unit)

### 5.1 Adaptive FM6 slot
Today FM6 is permanently the DAC. Generalize it so a **song declares FM6's role**: a 6th FM
sequencer voice **or** the DAC channel (mutually exclusive — the YM2612 shares ch6 between FM and the
DAC via `$2B` bit7). Additions:
- A `SongHeader` flag (or a `CHROUTE_FM6` route) declaring FM6 = FM for this song.
- The song loader: if FM6=FM, write `$2B` bit7 = 0 (DAC mode OFF) and route FM6 to the sequencer's FM
  writer (FM6 = part II, channel index 2, chsel `$06`); if FM6=DAC (default, e.g. the 1C/Ode demo),
  keep the existing 1B behavior.
- **Risk to research (T3):** keeping the Timer-A tick alive when the DAC isn't streaming. The idle
  loop already polls Timer-A (added in 1C Task 6 for the load-deadlock), so a DAC-off song ticks the
  sequencer from the idle loop — confirm this holds, that the idle loop's `$80`/`$2A` writes are
  harmless with DAC mode off, and that the mode switch is clean (no click, no stuck state). Document
  the cycle accounting for the DAC-off path.
- The 1C/Ode demo (FM6=DAC) must still work unchanged (regression).

### 5.2 `MEV_PAN` opcode
A proper per-channel stereo opcode in the reserved `$E4–$ED` space (e.g. `MEV_PAN = $E4 + pp`),
mapping to YM `$B4` L/R bits (off / left / right / center). Applied per channel; the FM writer keeps
the rest of `$B4` (AMS/FMS) from the channel's patch. Packer-validated (FM/DAC routes only; values in
range). The transcoder emits it from Zyrinx `PAN_*`.

### 5.3 Volume dynamics (`VOL_1`)
Handle Zyrinx `VOL_1` (a level + duration) faithfully. Minimum: a volume change that takes the new
level (our existing `MEV_VOL` covers the level). Best-possible: a **volume-envelope/fade opcode**
designed to extend to the multi-level `VOL_2–5` envelopes later (not in Moving Trucks) — e.g. a
target level + ramp duration the sequencer steps each tick. Exact `VOL_1` semantics (does the
duration ramp, or hold-then-change?) are confirmed against the disasm/VGM in the verify pass; ship
the simplest faithful interpretation first.

## 6. Transcoder (`tools/zyrinx_port.py`, Python TDD)
- **Input:** the decoded Moving Trucks (consume `megadaw_export/05_Moving_Trucks.json` for the
  channel/pattern structure + resolve sequences to flat events via the existing decode tooling, or
  re-decode from `songs/` — implementer picks the most complete source) + `voices.json`.
- **Output:** an AS data file for our v0 song (label `Song_MovingTrucks`, via `song_packer.emit_asm`)
  + a translated `FmPatch` bank (the song's instruments) emitted in our patch format.
- **Pure functions, TDD:** note mapping, voice translation (with the operator reorder), tempo
  mapping, pattern flattening. pytest covers each mapping with reference values (e.g. a known voice's
  expected `FmPatch` bytes; a known note's expected pitch index/F-number).
- Lives alongside the other build tools; generated `.asm` checked in; regen documented.

## 7. Data
- Generated `data/sound/song_movingtrucks.asm` + its FM-patch bank, added to the song table with a
  new song id. Selectable: the DEBUG boot plays Moving Trucks (so it's audible on load), and the
  Start-toggle / a build path can switch between the Ode-to-Joy demo (FM6=DAC) and Moving Trucks
  (FM6=FM) to exercise both FM6 modes.

## 8. Verification (the gate)
- Build `SOUND_DRIVER_ENABLED=1 DEBUG=1 SOUND_DBG_MIRROR=1`, load in Exodus, capture our render's VGM
  (`emulator_vgm_start/_stop`).
- **Diff our YM register stream against `song_05.vgm`** (the original): parse both into time-ordered
  (reg, value) events; align at the first key-on; compare (a) voice-load register sets (`$30–$8E`,
  `$B0`, `$B4`) per instrument — should match byte-exact after the operator reorder; (b) F-number
  (`$A0/$A4`) + key-on (`$28`) sequence/timing — notes match in pitch and onset; (c) TL/`$40` volume
  and `$B4` pan changes. Build an interval/event histogram to quantify divergence.
- **Pass:** voice register sets match exactly; the note pitch/onset sequence matches (allowing our
  Timer-A tick quantization); divergences localize to the untraced `OP1–4`/`VOL` features.
- **T6 deepen:** where the diff shows audible/measurable divergence, trace the relevant Zyrinx
  handler in the disasm and extend the transcoder/engine. Re-diff.
- The mirror (`Sound_Dbg_Mirror`) confirms all 6 channels active, `BADOP=0`, the loop wraps, FM6 in FM
  mode.

## 9. Decomposition (tasks; each: research → build → Exodus/VGM-verify → commit)
1. **T1 — Transcoder core:** pattern→sequence flattening + note/tempo mapping → a packable v0 song
   (voices stubbed/placeholder). Verify it packs + builds + the note/tempo math matches reference
   values (pytest) and a spot-check vs the VGM note sequence.
2. **T2 — Voice translation:** Zyrinx 30-byte → our `FmPatch` (operator reorder, `$B4`, drop ext); the
   B&R instrument bank. Verify the translated register sets match the reference VGM's voice loads.
3. **T3 — Engine: adaptive FM6 slot.** FM6=FM mode; loader DAC-off + route; regression: the Ode demo
   (FM6=DAC) still plays. Exodus: 6 channels active.
4. **T4 — Engine: `MEV_PAN` + volume dynamics (`VOL_1`).** Opcodes + packer validation + transcoder
   emission. Exodus/VGM: pan + volume events appear.
5. **T5 — Integrate + GATE VGM diff:** wire Moving Trucks into the ROM, boot-play it, capture VGM,
   diff vs `song_05.vgm`. Confirm voices/notes/timing match; quantify residual divergence.
6. **T6 — (verify-driven) Deepen** `OP1–4`/`VOL` only where the diff shows it matters. Re-diff.

## 10. Risks
- **Adaptive FM6 vs the cycle-balanced DAC loop** (T3) — the central engine risk; the DAC-off tick
  path must keep the sequencer driven without the free-running DAC loop. Mitigated by the existing
  idle-loop Timer-A poll; confirm + document.
- **Operator-order ambiguity** in the voice translation — resolved objectively by the reference-VGM
  voice-load byte match (T2/T5).
- **Note octave base / tempo calibration** — resolved by the reference-VGM pitch/onset match (T1/T5).
- **Untraced `OP1–4`/`VOL` fidelity** — accepted as verify-driven (T6); may be inaudible.
- **6→6 channel fit + the ch6 stub** — dropped/merged + logged; the diff confirms no lost content.
