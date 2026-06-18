# Sound Phase 3 — FM Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Z80 sound driver Zyrinx-class FM depth (multi-point pitch envelopes, voice-stepping, pan, per-op TL bias, portamento) and play "Moving Trucks" faithfully as a real native-sequencer port.

**Architecture:** Replace 1C's "one Timer-A tick = one event" sequencer with a per-frame engine at a fixed ~59.4 Hz: each frame, every channel runs a stream-agnostic `ModUpdate` (renders per-channel *modulation state* → YM) then advances its command stream gated by a per-channel tempo accumulator. The format + modulation layer are laid out for the full dual-stream (C) end state but only the single command stream (A) is driven now ("design for C, build for A").

**Tech Stack:** Z80 + 68000 assembly (AS Macro Assembler). No unit-test framework — every task verifies by `SOUND_DRIVER_ENABLED=1 DEBUG=1 SOUND_DBG_MIRROR=1 ./build.sh -pe`, Exodus MCP (incl. `emulator_z80_registers`/`emulator_z80_read`, and the `$FFB202` `Sound_Dbg_Mirror`), and `vgm2wav` rendered-audio diff vs the oracle `/tmp/moving_trucks_ref.vgm`. Honor `CODING_CONVENTIONS.md` (`struct`/`endstruct`, `phase`/`dephase`, `function` for compile-time math, `.s`/`.w`/`.l` sized branches, no `mulu`/`divu`).

**Spec:** `docs/superpowers/specs/2026-06-18-sound-phase3-fm-depth-design.md`
**RE references:** `…/disasm/sound/zyrinx_driver.asm`, `…/disasm/sound/ZYRINX_FORMAT.md`, `docs/research/z80_blobs/batman_driver_analysis.md`, `tools/zyrinx_player.py` (validated reference simulator), oracle `/tmp/moving_trucks_ref.vgm`.

---

## File Structure (what each file owns)

- `sound_constants.asm` — `MEV_*` opcodes, `SeqChannel` struct (+ the Phase-3 modulation-state block), `SCF_*` flags, frame-rate constant + `timerAReload()` function, the C-ready `SongHeader` per-channel layout constants.
- `engine/sound_sequencer.asm` — the per-frame engine: `Sequencer_Frame` (per-channel `ModUpdate` + tempo-accumulator-gated stream advance), the opcode handlers (existing + the new `MEV_PITCHENV`/`MEV_PAN`/`MEV_OPBIAS`/`MEV_PORTA`), `ModUpdate`.
- `engine/sound_fm.asm` — the FM writers `ModUpdate` calls: `Fm_NoteOnFreq` (have), `Fm_PatchLoad` (have, extend for op-bias), `Fm_SetPan` (new), pitch-table lookup using the per-song table ptr.
- `engine/z80_sound_driver.asm` — Timer-A reload to the fixed frame rate; the song loader sets per-channel `tempo_base` + the C-ready stream-table ptrs + the per-song pitch-table ptr.
- `tools/song_packer.py` — event classes + the C-ready header (per-channel `{route, cmd_ptr, mod_ptr}`); validation.
- `tools/zyrinx_player.py` — extend to EMIT our native format (the real port): MT song streams + the 132-entry pitch table + the FmPatch bank.
- `data/sound/` — generated `song_movingtrucks.asm`, `movingtrucks_patches.asm`, `movingtrucks_pitchtable.asm`; `song_table.asm` + `main.asm` re-wire `SONG_MOVINGTRUCKS` (streaming, FM6=FM).
- `debug/sound_debug.asm` — extend the `Sound_Dbg_Mirror` to surface per-channel modulation state (cursor, voice, tempo_accum) for MCP inspection.

---

## Task 1: Cycle-budget spike (de-risk before building)

**Goal:** confirm a worst-case frame (6 FM channels voice-stepping + the DAC) fits the Z80 budget at ~59.4 Hz before committing the architecture. Throwaway measurement, not shipped code.

**Files:** Create `tools/cycle_budget_phase3.md` (the measurement + verdict).

- [ ] **Step 1: Compute the budget.** One frame at 59.4 Hz = Z80 cycles/frame = 3,579,545 / 59.4 ≈ **60,260 cycles** (NTSC Z80 clock). The 1B DAC consumer loop already spends a fixed budget per pass; subtract the measured DAC cost (from `project_sound_driver_phase1` memory: the free-running loop is ~346 cyc/sample at ~10 kHz ≈ 168 passes/frame). Document the remaining FM budget per frame.
- [ ] **Step 2: Estimate `ModUpdate` worst case.** Per channel per frame: pitch lookup (~40 cyc) + 2 YM freq writes + key write (~30 cyc each with busy handling) + a full patch reload on a voice-step frame (~24 register writes ≈ 24×~30 = 720 cyc) + TL re-assert. Worst case ≈ 6 channels × ~900 cyc = ~5,400 cyc/frame for FM. Write the arithmetic in the doc.
- [ ] **Step 3: Verdict + fallback.** If FM (≈5.4k) + DAC fits in 60k with margin → proceed with the simple model (full `ModUpdate` every frame). If not, the documented fallback is Zyrinx's even/odd split (FM channels 0–3 on even frames, 4–5 + sequencer on odd) and/or throttling the patch re-assert. Record the chosen approach.
- [ ] **Step 4: Commit.**
```bash
git add tools/cycle_budget_phase3.md
git commit -m "spike(sound phase3): per-frame FM + DAC cycle budget at 59.4Hz"
```

---

## Task 2: Per-frame engine core + C-ready layout

**Goal:** restructure the sequencer to "frame @ ~59.4 Hz + per-channel tempo accumulator + per-frame `ModUpdate` skeleton", with the C-ready stream-table + extended `SeqChannel`. **Regression: the 1C test song and the 1B DAC still play.**

**Files:**
- Modify `sound_constants.asm` (the `SeqChannel` struct, frame-rate constant + `timerAReload()`, `SongHeader` per-channel layout).
- Modify `engine/sound_sequencer.asm` (`Sequencer_Tick`→`Sequencer_Frame`, the accumulator gate, the `ModUpdate` stub).
- Modify `engine/z80_sound_driver.asm` (Timer-A reload; the loader sets `tempo_base` + stream-table ptrs).
- Modify `tools/song_packer.py` + `data/sound/song_test.py` (emit the C-ready header + a `tempo_base`).

- [ ] **Step 1: Lock the extended `SeqChannel` struct.** In `sound_constants.asm`, extend the struct (keep existing fields; append the modulation-state block). Exact layout:
```
SeqChannel struct
sc_stream_ptr   ds.w 1   ; +0  command-stream read ptr  (slot[0])
sc_mod_ptr      ds.w 1   ; +2  modulation-stream read ptr (slot[1]; 0 for A/single-stream)
sc_dur_count    ds.b 1   ; +4  event-ticks remaining on the current note/rest
sc_dur_default  ds.b 1   ; +5
sc_patch        ds.b 1   ; +6  current/desired FM patch index (voice)
sc_last_patch   ds.b 1   ; +7  last patch actually loaded (voice-step change detect; $FF=force)
sc_volume       ds.b 1   ; +8
sc_note         ds.b 1   ; +9  current pitch index (key-off/debug)
sc_flags        ds.b 1   ; +10 SCF_* (active/keyed/is_fm/is_psg/is_dac)
sc_route        ds.b 1   ; +11
sc_loop_ptr     ds.w 1   ; +12
sc_repeat_ptr   ds.w 1   ; +14
sc_repeat_count ds.b 1   ; +16
sc_tempo_base   ds.b 1   ; +17 per-channel tempo (format code; larger = slower)
sc_tempo_accum  ds.b 1   ; +18 accumulator: -=16/frame, +=tempo_base on borrow
sc_pt_count     ds.b 1   ; +19 pitch-envelope point count (1..5)
sc_pt_cursor    ds.b 1   ; +20 current envelope point index (cycles 0..count-1)
sc_points       ds.b 5   ; +21 pitch-envelope points (note indices)
sc_transpose    ds.b 1   ; +26 signed per-pattern transpose
sc_pan          ds.b 1   ; +27 $B4 value (L/R/AMS/FMS)
sc_opbias       ds.b 4   ; +28 per-operator TL bias (S1,S3,S2,S4)
sc_porta_accum  ds.w 1   ; +32 Q-fixed glide accumulator
sc_porta_incr   ds.w 1   ; +34 glide per-frame increment (0 = no glide)
SeqChannel endstruct      ; = 36 bytes
```
Keep the `sc_* = SeqChannel_sc_*` aliases. The per-song pitch-table ptr lives in the seq header (Step 4), not per channel.
- [ ] **Step 2: Verify the RAM budget.** Add an assert in `sound_constants.asm`: the seq block (`SND_SEQ_BASE=$1800` .. mailbox `$1F00`) holds the header + `CHROUTE_COUNT` (11) slots × 36 bytes. `if SND_SEQ_BASE + SND_SEQ_HEADER_LEN + 11*SeqChannel_len > $1F00 / error "seq RAM overflow"`. Build to confirm the assert math (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`). Expected: builds.
- [ ] **Step 3: Frame-rate constant + `function`.** In `sound_constants.asm`:
```
SND_FRAME_HZ    = 59                     ; music frame rate (~59.4Hz, region-independent)
timerAReload    function hz, 1024 - (1000000000 / ((hz) * 18773))   ; YM Timer-A N
SND_TIMERA_N    = timerAReload(SND_FRAME_HZ)
```
- [ ] **Step 4: C-ready `SongHeader` layout.** Document + constant-ize the new per-channel header record: `db route ; dw cmd_ptr ; dw mod_ptr` (5 bytes/channel; `mod_ptr=0` for A). Header also gains `db tempo_base` (per song; per-channel override via stream) and `dw pitchtable_ptr` (per-song pitch table; 0 = use the engine default table). Update `tools/song_packer.py` to emit this and `data/sound/song_test.py` to set a `tempo_base` that reproduces its current event rate at 59.4 Hz (compute: 1C's old tempo → events/sec; pick `tempo_base` so `59.4*16/tempo_base` ≈ that rate).
- [ ] **Step 5: Timer-A → fixed frame rate.** In `engine/z80_sound_driver.asm`, set the Timer-A reload to `SND_TIMERA_N` at driver init (replacing the per-song tempo programming). The free-running DAC loop's Timer-A overflow poll now fires `Sequencer_Frame` once per frame.
- [ ] **Step 6: `Sequencer_Frame` (the new core).** In `engine/sound_sequencer.asm`, restructure the per-tick entry into a per-frame loop:
```
Sequencer_Frame:                ; called once per Timer-A overflow (~59.4Hz)
   ; for each active channel (ix walks slots, de=SeqChannel_len):
   ;   call ModUpdate            ; per-frame: render modulation state -> YM
   ;   ld a,(ix+sc_tempo_accum) / sub 16 / ld (ix+sc_tempo_accum),a
   ;   ret nc  (no event-tick this frame for this channel)
   ;   add a,(ix+sc_tempo_base) / ld (ix+sc_tempo_accum),a
   ;   call Sequencer_Channel     ; the existing 1C per-event-tick logic (dur_count, fetch opcode)
```
`Sequencer_Channel` keeps 1C's `dur_count`-decrement + `Sequencer_NextOpcode` fetch/dispatch (WAIT now means event-ticks; `$FF-byte` already). Commands set modulation STATE (not direct YM) — wired in later tasks; for now they behave as 1C.
- [ ] **Step 7: `ModUpdate` stub.** Add `ModUpdate` that, for an FM channel with `sc_pt_count<=1` and no glide and `sc_patch==sc_last_patch`, does nothing (plain held note — the regression-safe path). Real rendering arrives in Tasks 3–7. Preserve `ix`.
- [ ] **Step 8: Build + regression-verify.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 SOUND_DBG_MIRROR=1 ./build.sh -pe`. Reload in Exodus (`emulator_reload_rom`→`reset`→`resume`), read `Sound_Dbg_Mirror`/`emulator_z80_read`: the **1C test song still plays** (channels active, BADOP=0) and the **DAC still runs**. Capture ~10 s VGM; confirm FM key-ons + DAC unaffected. Expected: test song audibly unchanged.
- [ ] **Step 9: Commit.**
```bash
git add sound_constants.asm engine/sound_sequencer.asm engine/z80_sound_driver.asm tools/song_packer.py data/sound/song_test.py data/sound/song_test.asm
git commit -m "feat(sound phase3): per-frame engine + tempo accumulator + C-ready stream layout"
```

---

## Task 3: Pitch — per-song 132-entry fnum table + transpose/clamp

**Goal:** `ModUpdate` resolves a single note (count=1) via the per-song pitch table; `MEV_PITCHENV` count=1 keys it. Foundation for the envelope (Task 4).

**Files:** Modify `engine/sound_fm.asm` (pitch lookup via the per-song table ptr), `engine/sound_sequencer.asm` (`MEV_PITCHENV` handler, `ModUpdate` pitch path), `sound_constants.asm` (`MEV_PITCHENV` opcode), `tools/song_packer.py` (`PitchEnv` event), generate `data/sound/movingtrucks_pitchtable.asm` (the 132-entry table from the RE, via `tools/zyrinx_player.py`).

- [ ] **Step 1: Opcode.** `sound_constants.asm`: `MEV_PITCHENV = $E8 ; + count(1..5) + count note-index bytes : set pitch-envelope points + key-on`. Add the range/collision asserts alongside the existing `MEV_*` checks.
- [ ] **Step 2: Pitch-table lookup.** `engine/sound_fm.asm`: a routine `Fm_NoteFromTable` — in: `a`=note index, the per-song table ptr (from seq header, cached in a Z80 global `Snd_PitchTabPtr`); out: `de`=($A4,$A0) bytes. `idx = clamp_0_83(a + sc_transpose)`; `d = tableA4[idx]`, `e = tableA0[idx]`; then fall into `Fm_NoteOnFreq` (have) to write + key. Clamp via the two-tier behavior from the RE (saturate to $83). The table is two 132-byte pages (A4, A0).
- [ ] **Step 3: `MEV_PITCHENV` handler.** `engine/sound_sequencer.asm`: read `count` + `count` point bytes → `sc_points[]`, `sc_pt_count`, `sc_pt_cursor=0`; set `SCF_KEYED`. (Does NOT write YM directly — `ModUpdate` renders.)
- [ ] **Step 4: `ModUpdate` pitch path.** For count=1: each frame, look up `sc_points[0]` → write freq; key-on only on the frame the note was (re)armed (track via a per-channel "needs key" flag; see the re-key rule in Task 5). For count=1 this re-articulates once then holds.
- [ ] **Step 5: Generate the pitch table.** Extend `tools/zyrinx_player.py` with `emit_pitchtable_asm()` dumping the RE's 132-entry table to `data/sound/movingtrucks_pitchtable.asm` (`MovingTrucks_PitchTable_A4: dc.b …` / `_A0:`), and include it in the streaming block. Set the song header's `pitchtable_ptr` to it.
- [ ] **Step 6: Build + verify a single tone.** Author a 2-channel scratch test (or temporarily route one MT channel) emitting a few `MEV_PITCHENV count=1` notes. Build, Exodus: capture VGM, confirm the `$A4/$A0` written match the table for the given indices (parse the VGM; compare to `movingtrucks_pitchtable.asm`). Expected: exact match.
- [ ] **Step 7: Commit.**
```bash
git add sound_constants.asm engine/sound_fm.asm engine/sound_sequencer.asm tools/song_packer.py tools/zyrinx_player.py data/sound/movingtrucks_pitchtable.asm
git commit -m "feat(sound phase3): per-song pitch table + MEV_PITCHENV single-note path"
```

---

## Task 4: Multi-point pitch envelopes (trills/arps)

**Goal:** `count≥2` cycles the points per frame → trills/arpeggios.

**Files:** Modify `engine/sound_sequencer.asm` (`ModUpdate` cursor advance).

- [ ] **Step 1: Cursor advance in `ModUpdate`.** Each frame, for an FM channel with `sc_pt_count>1`: `sc_pt_cursor = (sc_pt_cursor+1) mod sc_pt_count`; look up `sc_points[cursor]` → freq; re-articulate per the re-key rule (Task 5). For `count==1`, cursor stays 0.
- [ ] **Step 2: Build + verify a trill.** Scratch test: `MEV_PITCHENV count=2` with two indices a semitone apart, held. Build, Exodus VGM: confirm the two `$A4/$A0` values alternate at the frame rate. Expected: alternation visible in the VGM at ~59 Hz cadence.
- [ ] **Step 3: Commit.**
```bash
git add engine/sound_sequencer.asm
git commit -m "feat(sound phase3): multi-point pitch envelopes (trills/arps)"
```

---

## Task 5: Voice-stepping + the re-key rule (calibrate vs oracle)

**Goal:** voice changes mid-note (no re-key) → timbre sweep; nail the exact re-key condition against the oracle.

**Files:** Modify `engine/sound_sequencer.asm` (`MEV_PATCH` = voice-set-no-rekey; `ModUpdate` patch reload + the re-key decision), `engine/sound_fm.asm` (`Fm_PatchLoad` re-assert path).

- [ ] **Step 1: `MEV_PATCH` = voice change without re-key.** Confirm/adjust `Seq_Op_Patch` to set `sc_patch` only (no key-on). `ModUpdate`: if `sc_patch != sc_last_patch`, `Fm_PatchLoad` (reload the voice) + set `sc_last_patch`; do NOT key. Carrier-TL re-assert each frame (apply `sc_opbias` + `sc_volume`).
- [ ] **Step 2: Define the re-key rule (the calibration).** Implement the hypothesis first: re-key (`Fm_NoteOnFreq` key bit) only when the *pitch index changes* (cursor lands on a different note than last frame) OR a new `MEV_PITCHENV` arrives — NOT on a voice change, NOT on same-pitch frames. Track `sc_note` (last keyed index).
- [ ] **Step 3: Build + calibrate against the oracle.** Build with one MT voice-stepping channel (e.g. ch1's seq65/70) wired in. Exodus: capture VGM, render via `vgm2wav`, and compare that channel's key-on count + density to the oracle `/tmp/moving_trucks_ref.vgm`. Use `emulator_z80_read` to watch `sc_patch`/`sc_last_patch`/`sc_note` live. If our key-on density ≠ oracle, adjust the re-key rule (e.g. same-pitch throttle, or only on `MEV_PITCHENV`) and re-measure. Iterate until the channel's key-on density + audio spectrum match. **Record the resolved rule in a comment + the spec.**
- [ ] **Step 4: Commit.**
```bash
git add engine/sound_sequencer.asm engine/sound_fm.asm docs/superpowers/specs/2026-06-18-sound-phase3-fm-depth-design.md
git commit -m "feat(sound phase3): voice-stepping + calibrated re-key rule"
```

---

## Task 6: Pan + per-operator TL bias

**Goal:** `MEV_PAN` sets `$B4`; per-op TL bias offsets operator TLs at patch load.

**Files:** Modify `engine/sound_sequencer.asm` (`MEV_PAN`, `MEV_OPBIAS` handlers), `engine/sound_fm.asm` (`Fm_SetPan`, op-bias in `Fm_PatchLoad`), `sound_constants.asm` (`MEV_OPBIAS` opcode), `tools/song_packer.py` (events).

- [ ] **Step 1: Pan.** `MEV_PAN` ($E4) + 1 byte → `sc_pan` (off=$00/L=$40/R=$80/C=$C0 in bits 6-7, matching Zyrinx $30-$36). `ModUpdate` writes `$B4+chan` = `sc_pan | AMS/FMS` when changed. Add `Fm_SetPan` in `sound_fm.asm`.
- [ ] **Step 2: Op-bias.** `MEV_OPBIAS = $E9 ; + op(0..3) + val` → `sc_opbias[op]`. In `Fm_PatchLoad`, add `sc_opbias[i]` to each operator's TL (clamped to 7 bits) on load.
- [ ] **Step 3: Build + verify.** Scratch test with a hard-L then hard-R note and an op-bias change. Exodus VGM: confirm `$B4` L/R bits flip and the `$40`-group TL reflects the bias. Expected: matches.
- [ ] **Step 4: Commit.**
```bash
git add sound_constants.asm engine/sound_sequencer.asm engine/sound_fm.asm tools/song_packer.py
git commit -m "feat(sound phase3): pan + per-operator TL bias"
```

---

## Task 7: Portamento (optional/last)

**Goal:** smooth glide between two note indices via a Q-fixed accumulator. Lowest priority; defer if schedule-pressed (MT fidelity unaffected per the RE).

**Files:** Modify `engine/sound_sequencer.asm` (`MEV_PORTA`, `ModUpdate` glide), `engine/sound_fm.asm` (16-bit fnum interpolation), `sound_constants.asm` (`MEV_PORTA`).

- [ ] **Step 1: Opcode + state.** `MEV_PORTA = $EA ; + target-index + duration` → set `sc_porta_incr` = (target_fnum − cur_fnum)/duration (shift-based or the RE's 16/16 division kernel — no `divu`), `sc_porta_accum` = cur. Glide-active when `sc_porta_incr != 0`.
- [ ] **Step 2: `ModUpdate` glide.** Each frame while gliding: `sc_porta_accum += sc_porta_incr`; write fnum from the accumulator; on reaching the target, snap + clear `sc_porta_incr`.
- [ ] **Step 3: Build + verify.** Scratch test: glide an octave over ~15 frames. Exodus VGM: confirm fnum ramps smoothly between the two table values. Expected: monotonic fnum ramp.
- [ ] **Step 4: Commit.**
```bash
git add sound_constants.asm engine/sound_sequencer.asm engine/sound_fm.asm
git commit -m "feat(sound phase3): portamento (Q-fixed glide)"
```

---

## Task 8: The port — emit native Moving Trucks from the song data

**Goal:** extend the validated reference player to emit our native format; wire `SONG_MOVINGTRUCKS` (streaming, FM6=FM). Source = `bank1_song03.bin`, not the oracle.

**Files:** Modify `tools/zyrinx_player.py` (native emitter), generate `data/sound/song_movingtrucks.asm` + `movingtrucks_patches.asm` (+ the pitch table from Task 3), modify `data/sound/song_table.asm`, `main.asm`, `engine/boot.asm`/`engine/game_loop.asm` (re-wire `SONG_MOVINGTRUCKS`).

- [ ] **Step 1: Native emitter.** Add `emit_native_song()` to `tools/zyrinx_player.py`: walk the simulated per-channel structure and emit our opcodes — `MEV_PITCHENV` (1–5 points), `MEV_PATCH` (voice-stepping), `MEV_PAN`, `MEV_OPBIAS`, `MEV_PORTA`, `MEV_REPEAT`/`MEV_LOOP` for the pattern/repeat/loopback structure, per-channel `tempo_base`. Reuse `zyrinx_port.py`'s Zyrinx-voice→FmPatch translation for the patch bank. 6 channels → FM1–6 (1:1).
- [ ] **Step 2: Generate + place.** Regenerate `song_movingtrucks.asm` + `movingtrucks_patches.asm` + `movingtrucks_pitchtable.asm`; restore the `align $8000` streaming block in `main.asm`; re-add the `SongTable`/`SongPatchTable` entries + the bank-boundary asserts in `song_table.asm`; set `SONG_MOVINGTRUCKS` in `boot.asm`/`game_loop.asm` (FM6=FM stream flags).
- [ ] **Step 2b: Packer validation.** `tools/song_packer.py` validates the emitted streams (opcode ranges, FM-only routes for FM opcodes, the C-ready header). Run the packer self-test. Expected: packs clean.
- [ ] **Step 3: Build.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 SOUND_DBG_MIRROR=1 ./build.sh -pe`. Expected: builds; bank-boundary asserts pass.
- [ ] **Step 4: Commit.**
```bash
git add tools/zyrinx_player.py data/sound/song_movingtrucks.asm data/sound/movingtrucks_patches.asm data/sound/movingtrucks_pitchtable.asm data/sound/song_table.asm main.asm engine/boot.asm engine/game_loop.asm
git commit -m "feat(sound phase3): emit native Moving Trucks port; wire SONG_MOVINGTRUCKS"
```

---

## Task 9: Final verification vs the oracle + regression

**Goal:** prove the port is faithful by RENDERED AUDIO (not register proxies), confirm regressions.

**Files:** Create `tools/phase3_verify.py` (the diff harness).

- [ ] **Step 1: Capture from boot.** Exodus: `emulator_reload_rom`→`reset`→`emulator_vgm_start /tmp/mt_phase3.vgm`→ wait ~16 s →`vgm_stop`.
- [ ] **Step 2: Audio diff.** `tools/phase3_verify.py`: render both `/tmp/mt_phase3.vgm` and the oracle `/tmp/moving_trucks_ref.vgm` via `vgm2wav`; report fraction-of-time-sounding, mean/peak, average log-spectrum correlation, and per-channel key-on note-sequence cross-correlation (offset-aligned). **Targets:** time-sounding ≈ oracle (≥95 %), spectrum r ≥ 0.9, dense-channel note match high. Honest numbers; no proxy claims.
- [ ] **Step 3: Per-channel residual check.** For any channel below target, use `emulator_z80_read` on its `SeqChannel` state to diagnose (cursor/voice/tempo_accum), fix, re-measure.
- [ ] **Step 4: Regression.** Switch the DEBUG song to `SONG_TEST`, build, verify the 1C song + DAC still play unchanged. Switch back.
- [ ] **Step 5: Commit + (on user OK) merge.**
```bash
git add tools/phase3_verify.py
git commit -m "test(sound phase3): rendered-audio verification harness + results"
```
Merge `feat/sound-phase3-fm-depth` → master once the port plays faithfully and regressions hold (per CLAUDE.md git workflow).

---

## Notes for the implementer

- **Calibrate, don't guess** the re-key rule (Task 5) and any timing detail — the oracle is ground truth; verify rendered audio, never a key-on/register proxy.
- **Design-for-C is load-bearing:** keep `ModUpdate` strictly state→YM (never parse a stream inside it), and keep `sc_mod_ptr`/the header's `mod_ptr` slot present-but-null. Adding the C modulation stream later must require zero changes to `ModUpdate` or the byte layout.
- **No-multiply/divide:** portamento slope + any scaling use shifts/adds or the RE's division kernel, never `mulu`/`divu`.
- Each task: build (`-pe`), verify in Exodus, commit. Keep `ENGINE_ARCHITECTURE.md` §6 in sync as features land.
