# Sound 1D — Moving Trucks Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. A fresh subagent per task; the controller drives the Exodus MCP + VGM verification between tasks. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Faithfully play B&R's "Moving Trucks" on our engine — 6 FM voices, the real Zyrinx instruments, panning, volume dynamics — by transcoding the already-decoded song into our v0 format and adding the engine features it needs (adaptive FM6 slot, pan opcode, volume dynamics).

**Architecture:** A build-time Python transcoder (`tools/zyrinx_port.py`, TDD) turns the decoded Moving Trucks + `voices.json` into our v0 song (`song_packer` `SongDesc`) + a translated `FmPatch` bank. Three small, properly-designed engine additions (adaptive FM6, `MEV_PAN`, volume dynamics) let our 1C sequencer play it. Fidelity is proven by diffing our YM2612 register stream against the original `song_05.vgm`.

**Tech Stack:** Python 3 + pytest (transcoder, TDD); Motorola 68000 + Zilog Z80 (AS Macro Assembler `asw`); `./build.sh` (`SOUND_DRIVER_ENABLED=1 DEBUG=1 [SOUND_DBG_MIRROR=1]`); Exodus MCP + VGM capture/diff.

**Source spec:** `docs/superpowers/specs/2026-06-18-sound-1d-moving-trucks.md`. **Builds on:** 1C (`docs/superpowers/specs/2026-06-17-sound-1c-design.md`), merged to master.

## REVISION (post-T1-research, 2026-06-18) — size + streaming + repeat opcode

Measured Moving Trucks: 19 unique sequences, 97 pattern entries, repeats 1–81×. Fully unrolling = ~50,900 events (~100 KB) — impossible. Inlined with repeats NOT unrolled = ~3,932 events (~7.9 KB) — fits a 32 KB ROM bank, NOT our ~1 KB free Z80 RAM. Two consequences vs the original plan:

1. **Bounded-repeat opcode (`MEV_REPEAT_START` / `MEV_REPEAT_END nn`)** — the transcoder emits each pattern's sequence body ONCE wrapped in a repeat marker with its repeat count, instead of unrolling. Sequencer gains per-channel repeat state (saved ptr + count) in `SeqChannel` — like `sc_loop_ptr` but counted. This keeps the song ~7.9 KB. (Added as **Task 1b** below; transcoder support in T1, packer support in T1b.)
2. **DAC-off ROM streaming (no RAM copy)** — because an FM6=FM song runs with the DAC OFF, the bank is free, so the sequencer reads stream pointers DIRECTLY through the banked `$8000` window (set the bank once at load; it's held since nothing else touches it). The 1C `Sequencer_NextOpcode` fetch (`ld a,(hl)`) works unchanged whether `hl` is RAM or the ROM window. So the DAC-off loader does NOT copy to RAM (unlike 1C's small-song path) — it bank-aligns the song, `SetBank(song bank)`, and points each `sc_stream_ptr` at `(song_window_base + per-channel offset)`. The whole song (all channel streams + patch bank) must fit in ONE 32 KB bank (`align $8000`). (Folded into **T3**.) The 1C copy-to-RAM path stays for FM6=DAC songs (DAC holds the bank).

**Decoded-data sources** (all under `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/sound/`):
- `ZYRINX_FORMAT.md` — the format spec (note/voice/command/tempo layout).
- `megadaw_export/05_Moving_Trucks.json` — per-channel pattern structure (seq_idx/repeat/pitch_transpose/tempo_delta) + header.
- `decoded_full/05_Moving_Trucks.txt` — expanded command stream (human-readable).
- `decoded_full/voices.json` — every FM voice (bank1 = Moving Trucks' bank), fully parsed.
- `songs/` (raw binaries), `decode_full.py`/`decode_song.py`/`parse_song.py` (decode tooling — importable), `z80_driver.bin`/`z80_disasm.py` (driver, for T6 tracing).
- `vgm/song_05.vgm` — the original render (the fidelity ground truth).

---

## Verification model
- **Python transcoder** — real TDD with pytest (`tools/test_zyrinx_port.py`): note/tempo/voice/flatten math, each with reference values; run `python3 -m unittest tools.test_zyrinx_port` (pytest not installed system-wide).
- **Assembly** — build-time AS asserts (opcode/struct/RAM) + Exodus MCP (mirror reads) + VGM capture/diff.
- **The gate (T5)** — our YM register stream vs `song_05.vgm`: voice-load register sets match byte-exact (after the operator reorder), the note pitch/onset sequence matches. This both proves fidelity and localizes any divergence to the untraced features.
- Build all three configs `-pe` exit 0 before each commit where they can differ:
  `SOUND_DRIVER_ENABLED=1 DEBUG=1 SOUND_DBG_MIRROR=1 ./build.sh -pe`, `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`, `./build.sh -pe`.

**Honor the 1C law:** Z80 = Intel-hex under `cpu z80`; 68k uses `$`. Keep the even-pad block last before `dephase`. Absolute YM addressing only (preserve `de=$4001`); re-park `$2A`. One `ei` per DAC pass. Zero-tick coordination handlers must preserve `hl` across writer-hook calls. Accurate `Clobbers:` comments. MCP can't read Z80 RAM — use `Sound_Dbg_Mirror` ($FFB202), `0x`-prefixed addresses. Don't stage the pre-existing unrelated WIP (`data/editor_bg_override.json`, `tools/forest_bg_gen.py`, `data/sprites/`).

---

## Task 1: Transcoder core — flatten + note/tempo mapping

Everything that turns the decoded song's structure into a packable v0 song, with voices stubbed (a single placeholder patch) so we can hear/verify the NOTES before instruments land.

**Files:** Create `tools/zyrinx_port.py`, `tools/test_zyrinx_port.py`, generated `data/sound/song_movingtrucks.asm`; uses `tools/song_packer.py` (1C).

- [ ] **Step 1 — Research (decoded-data shape + the resolution path).** Read `ZYRINX_FORMAT.md` (§ Note Values, § Sequence Data Format, § Tempo), `megadaw_export/05_Moving_Trucks.json` (channel/pattern structure), and `decoded_full/05_Moving_Trucks.txt`. Determine the cleanest way to get **flat per-channel event lists** (note, duration, voice-select, pan, volume): either (a) import/extend the existing `decode_full.py`/`decode_song.py` to resolve each pattern's `seq_idx` → its sequence's event stream and concatenate per channel with repeats/transposes applied, or (b) parse `decoded_full` text. Confirm: how a `WAIT` maps to note duration (duration = `$FF - byte`), how `PITCH_1`/`NOTE` carry the note value, where the loop point is (header `loop_point` + per-channel pattern list), and the note→octave/semitone convention. Produce: the chosen input path + the exact note-value→our-pitch-index formula candidate (to be calibrated in T5) + the tempo formula. 4–6 lines.

- [ ] **Step 2 — TDD: note + tempo mapping (write `test_zyrinx_port.py` FIRST).**
  Pure functions in `tools/zyrinx_port.py`:
  ```python
  def zyrinx_note_to_pitch(note: int, transpose: int = 0) -> int:   # Zyrinx 0..127 (+transpose) -> our pitch index (0..0x5E), clamped
  def zyrinx_tempo_to_byte(format_code: int, tempo_delta: int = 0) -> int:  # Timer-B base -> our Timer-A tempo byte
  def wait_to_ticks(wait_byte: int) -> int:                          # $80..$FF -> duration in our ticks
  ```
  pytest cases (failing first): a reference Zyrinx note maps to the expected pitch index (document the chosen octave base — calibrated in T5 against the VGM, but pin a value now); `zyrinx_note_to_pitch` clamps out-of-range to 0..0x5E and is monotonic; transpose shifts by semitones; `zyrinx_tempo_to_byte($38)` yields a tempo byte whose tick rate ≈ the original's events/sec (60×16/56 ≈ 17.1/sec); `wait_to_ticks($FF)=0`, `wait_to_ticks($80)=127`. Implement until green.

- [ ] **Step 3 — Flatten the song → a v0 `SongDesc`.**
  ```python
  def load_moving_trucks() -> dict          # read the decoded JSON + resolve sequences to per-channel events
  def flatten_channel(channel) -> list      # expand patterns (repeat/transpose/tempo) -> flat (note/rest/dur/voice/pan/vol) events
  def build_songdesc() -> SongDesc          # all channels -> song_packer SongDesc (T1: VOICE -> a single placeholder Patch(0); pan/vol dropped this task)
  ```
  Map each flat event → `song_packer` helpers: note→`Note`/`NoteDur`, wait/rest→`Rest`/`SetDur`, voice→`Patch(0)` (placeholder until T2), loop→`LoopPoint`/`Jump`. Route the 6 active channels → `CHROUTE_FM1..FM6` (FM6 placeholder until T3 — for T1, route the 6th channel to `CHROUTE_FM5` or drop it + log; the real FM6 lands in T3). Drop the ch6 stub + log. pytest: a channel with a repeat=2 pattern flattens to the doubled event list; `build_songdesc()` returns a `SongDesc` the packer accepts.

- [ ] **Step 4 — Emit + build.** `write_asm(build_songdesc(), "Song_MovingTrucks", "data/sound/song_movingtrucks.asm")`. The song uses a placeholder patch bank (reuse the 1C demo patches or a single neutral patch — voices come in T2). Add the include to `main.asm` (under `SOUND_DRIVER_ENABLED`, ROM data area) + a song-table entry (extend `data/sound/song_table.asm`: `SONG_MOVINGTRUCKS = 2`, bump `SONG_COUNT`). Build all configs `-pe` exit 0.

- [ ] **Step 5 — Commit.**
  ```bash
  python3 -m unittest tools.test_zyrinx_port
  git add tools/zyrinx_port.py tools/test_zyrinx_port.py data/sound/song_movingtrucks.asm data/sound/song_table.asm main.asm
  git commit -m "feat(sound 1d): Zyrinx transcoder core — flatten + note/tempo mapping (voices stubbed)"
  ```

---

## Task 2: Voice translation — Zyrinx 30-byte → our FmPatch bank

Replace the placeholder patches with the song's real instruments, verified byte-exact against the reference VGM's voice loads.

**Files:** Modify `tools/zyrinx_port.py` (+test), generated `data/sound/movingtrucks_patches.asm` (+ the patch bank the song references).

- [ ] **Step 1 — Research (voice format + the operator-order ground truth).** Read `ZYRINX_FORMAT.md` § Voice Table + `voices.json` (bank1). Confirm the 30-byte layout (FB/ALG; DT/MUL, TL, KS/AR, AM/D1R, D2R, SL/RR per op; AMS/FMS/pan; 4 ext). The operator-order question (natural op1-4 vs register order) is **resolved objectively in T5** by matching our `Fm_PatchLoad` register writes to the original's voice loads in `song_05.vgm` — for now implement the reorder our 1C patches use (Zyrinx natural op1,op2,op3,op4 → our physical-register array `[S1,S3,S2,S4]` = natural indices `[0,2,1,3]`), and note it's VGM-verified in T5. List the 35 voice indices Moving Trucks references (from `decoded_full`: 0,3,7,14,19,20,21,27,28,30,40,56,58,108,110,113,156,157,158,159,160,161,162,164,166,167,168,169,170,171,172,173,174,177).

- [ ] **Step 2 — TDD: voice translation (test first).**
  ```python
  def translate_voice(v: dict) -> bytes     # voices.json entry -> 26-byte FmPatch (our format)
  ```
  Map: `fp_alg_fb = (v['fb']<<3)|v['algo']`; `fp_lr_ams_fms = v['ams_fms_pan']` (or force L/R=11 if 0); each of the 6 op arrays reordered `[0,2,1,3]`; drop `ext`. pytest: a known `voices.json` entry → the expected 26 `FmPatch` bytes (compute by hand for one voice as the reference); assert length 26; assert the reorder (op array `[a,b,c,d]` → `[a,c,b,d]`).

- [ ] **Step 2b — Build the per-song patch bank + remap indices.** Collect the distinct voice indices the song uses, translate each, emit them as a contiguous `FmPatch` table (`data/sound/movingtrucks_patches.asm`, with the `pbyte`-style single-source pattern + a count assert), and **remap** the song's `VOICE n` references to dense local patch indices (0..34). Update `build_songdesc()` to emit `Patch(local_idx)` instead of the placeholder. The song's `SongHeader` patch-table ptr / `SND_SEQ_PATCHTAB` points at this bank (the loader sets it — wire in T5).

- [ ] **Step 3 — Build + commit.** Regenerate `song_movingtrucks.asm` + emit `movingtrucks_patches.asm`; include both in `main.asm`. Build all configs `-pe` exit 0. `python3 -m unittest tools.test_zyrinx_port`.
  ```bash
  git add tools/zyrinx_port.py tools/test_zyrinx_port.py data/sound/movingtrucks_patches.asm data/sound/song_movingtrucks.asm main.asm
  git commit -m "feat(sound 1d): Zyrinx voice -> FmPatch translation + per-song instrument bank"
  ```

---

## Task 3: Engine — adaptive FM6 slot

Let a song use FM6 as a 6th FM sequencer voice (DAC off) instead of the DAC. The central engine change.

**Files:** Modify `sound_constants.asm` (route/flag + FM6 mapping), `engine/sound_fm.asm` (FM6 = part II ch2), `engine/sound_sequencer.asm` (route FM6), `engine/z80_sound_driver.asm` (loader: DAC-mode switch + FM6 route), `engine/sound_api.asm`/song header as needed.

- [ ] **Step 1 — Research (DAC-off tick path + FM6 hardware mapping).** Confirm from `engine/z80_sound_driver.asm`: (a) with no DAC sample active, the **idle loop** runs and its Timer-A poll (added 1C Task 6) calls `Sequencer_Tick` — so a DAC-off song still ticks; verify the idle loop's `$80`/`$2A` writes are harmless when `$2B` bit7=0 (DAC mode off) and don't disturb FM6's registers; (b) FM6 = YM part II, channel-in-part index 2, key-on chsel `$06`, register-channel offset 2 (so its FM regs are `$X0+2` on part II). Confirm `Fm_PatchLoad`/`Fm_NoteOn`/`Fm_SetVolume` already handle "part II, ch 2" via the route→(part,ch) map — it should, since FM4/FM5 use part II; FM6 just adds ch index 2. Document the clean DAC-on→DAC-off switch (write `$2B`=$00) and back, no click, no stuck state, and the cycle accounting for the DAC-off path.

- [ ] **Step 2 — Add the FM6 route + song FM6-mode declaration.** In `sound_constants.asm`: add `CHROUTE_FM6 = ...` (renumber/extend the route enum cleanly, keeping DAC's route; update `CHROUTE_COUNT` + asserts) OR a `SongHeader` flag bit "FM6 = FM". Map `CHROUTE_FM6` → (part II, ch 2, chsel `$06`, `SCF_IS_FM`). Extend `Fm_RoutePart`/`Fm_ChSel` so FM6 resolves correctly.

- [ ] **Step 3 — Loader DAC-mode switch.** In `Snd_LoadSong` (`engine/z80_sound_driver.asm`): if the song declares FM6=FM (no DAC), write `$2B`=$00 (DAC mode OFF) during load (absolute addressing, re-park `$2A`), set `SND_STAT_DAC_ACTIVE=0`, and DON'T start a DAC sample; the sequencer's FM6 channel drives YM ch6 as FM. If FM6=DAC (the 1C/Ode demo default), keep the existing behavior (DAC mode on, `$2B`=$80). Ensure the Ode demo still plays (regression).

- [ ] **Step 4 — Route FM6 in the sequencer.** In `engine/sound_sequencer.asm`, ensure `CHROUTE_FM6` hits the FM writer hooks (it should via the `SCF_IS_FM` gate). Update the transcoder (T1/T2) to route the song's 6th channel to `CHROUTE_FM6`.

- [ ] **Step 5 — Build + Exodus verify.** Build all configs `-pe` exit 0. Reload a DAC-off test (a 2-channel inline test using FM6, or the Moving Trucks song once T1/T2 land), confirm via the mirror: 6 FM channels active, FM6 keyed, `$2B`=$00 (DAC off), `SND_SEQ_ACTIVE=1`, `BADOP=0`. Confirm the Ode demo (FM6=DAC) still plays (regression). Commit.
  ```bash
  git add sound_constants.asm engine/sound_fm.asm engine/sound_sequencer.asm engine/z80_sound_driver.asm
  git commit -m "feat(sound 1d): adaptive FM6 slot — song uses FM6 as 6th FM voice (DAC off)"
  ```

---

## Task 4: Engine — MEV_PAN opcode + volume dynamics

**Files:** Modify `sound_constants.asm` (opcodes), `engine/sound_fm.asm` (pan/vol writers), `engine/sound_sequencer.asm` (handlers), `tools/song_packer.py` (+test, encode/validate), `tools/zyrinx_port.py` (emit pan/vol).

- [ ] **Step 1 — Research (pan + VOL_1 semantics).** From `ZYRINX_FORMAT.md`: PAN_* → YM `$B4` L/R bits (PAN_OFF `$00`, PAN_R `$80`, PAN_L `$40`, PAN_C `$C0` in bits 6-7). VOL_1 = 1 level + duration byte; confirm whether the duration ramps or holds (trace `z80_disasm.py` if unclear, else ship level-set first). Confirm our `Fm_SetVolume` already sets carrier TL from a linear vol; pan is the `$B4` L/R bits (preserve AMS/FMS from patch).

- [ ] **Step 2 — `MEV_PAN` opcode.** In `sound_constants.asm`: define `MEV_PAN` in the reserved `$E4–$ED` space (`+ pp` operand: 0=off,1=L,2=R,3=center). Add `SEQEV_PAN` trace code. In `engine/sound_fm.asm`: `Fm_SetPan` (In: ix=channel, a=pan code) → write `$B4+ch` = (panbits) | (patch AMS/FMS bits); absolute addressing, preserve `ix`. In `engine/sound_sequencer.asm`: `Seq_Op_Pan` handler (zero-tick; read operand, store, call hook with `push hl`/`pop hl` per the 1C hl-preservation rule). In `tools/song_packer.py`: `Pan(code)` helper + encode + validation (FM routes only); +test.

- [ ] **Step 3 — Volume dynamics.** Ship `VOL_1` as a volume set via the existing `MEV_VOL` (the transcoder emits `Vol(level)`); if the disasm shows a ramp matters, add a `MEV_VOL_FADE` opcode (target + ramp-ticks, stepped per tick in the sequencer) — designed to extend to VOL_2-5 later. Keep scope to what Moving Trucks needs; document the extension path. +packer test.

- [ ] **Step 4 — Transcoder emits pan/vol.** Update `tools/zyrinx_port.py` to emit `Pan(...)` from `PAN_*` and `Vol(...)` from `VOL_1`. Regenerate the song.

- [ ] **Step 5 — Build + Exodus/VGM verify + commit.** Build all configs `-pe` exit 0; pytest green. Capture VGM, confirm `$B4` pan writes + volume changes appear at the song's cadence. Commit.
  ```bash
  git add sound_constants.asm engine/sound_fm.asm engine/sound_sequencer.asm tools/song_packer.py tools/test_song_packer.py tools/zyrinx_port.py data/sound/song_movingtrucks.asm
  git commit -m "feat(sound 1d): MEV_PAN opcode + volume dynamics + transcoder emission"
  ```

---

## Task 5: Integrate + GATE VGM diff vs the original

Wire Moving Trucks to play at boot, capture our render, and diff it against `song_05.vgm` to prove fidelity and localize any divergence.

**Files:** Modify `engine/boot.asm` (boot-play Moving Trucks), `data/sound/song_table.asm`, the Start-toggle (`engine/game_loop.asm`) to switch demo↔Moving Trucks; Create `tools/vgm_diff.py` (+ optional test).

- [ ] **Step 1 — Research (VGM diff method).** Confirm the VGM command set (from the 1C VGM work): `$52 reg val` = YM part-I write, `$53` = part-II, `$50` = PSG, `$61/$62/$70-7F` = waits, `$2B`/`$2A` = DAC. Plan the diff: parse both VGMs into time-ordered (port,reg,val) events; align at the first `$28` key-on; compare voice-load register sets (`$30-$8E`,`$B0`,`$B4` grouped per voice-load burst), F-number (`$A0-$A6`) + key-on (`$28`) sequence, TL/`$40`, pan/`$B4`.

- [ ] **Step 2 — Boot-play Moving Trucks.** In `engine/boot.asm` DEBUG: play `SONG_MOVINGTRUCKS` (or make the Start-toggle cycle Ode↔Moving Trucks; set Moving Trucks as the boot song so it's audible on load). The loader (T3) sets FM6=FM/DAC-off for it and `SND_SEQ_PATCHTAB` → the Moving Trucks patch bank.

- [ ] **Step 3 — `tools/vgm_diff.py`.** Parse our captured VGM + `song_05.vgm`; emit a report: per-voice-load register-set match (byte-exact?), note pitch/onset sequence match (with our Timer-A quantization tolerance), and a list of divergences (which regs/events differ, at what time). This is the controller's instrument for T5/T6.

- [ ] **Step 4 — Build + the GATE.** Build `SOUND_DRIVER_ENABLED=1 DEBUG=1 SOUND_DBG_MIRROR=1`. Controller: reload, reset, resume, capture VGM (~30-60s), stop. Run `vgm_diff.py` ours vs `song_05.vgm`. **Calibrate** the note octave base + tempo (T1) and the voice operator-order (T2) so the voice loads + note sequence MATCH — iterate the transcoder constants until the diff is clean. Confirm via the mirror: 6 channels active, FM6 keyed, `BADOP=0`, the song loops. **Pass:** voice register sets match (after reorder calibration); note pitch/onset sequence matches; residual divergence is localized to the untraced `OP1-4`/`VOL` features.

- [ ] **Step 5 — Commit.**
  ```bash
  git add engine/boot.asm engine/game_loop.asm data/sound/song_table.asm tools/vgm_diff.py data/sound/song_movingtrucks.asm tools/zyrinx_port.py
  git commit -m "feat(sound 1d): boot-play Moving Trucks + VGM-diff verification (calibrated to the original)"
  ```

---

## Task 6: Deepen (verify-driven) — only where the diff diverges

**Files:** as needed — `tools/zyrinx_port.py`, `engine/sound_*.asm`, `tools/song_packer.py`.

- [ ] **Step 1 — Triage the T5 diff.** Identify the largest audible/measurable divergences from the GATE diff. Likely candidates: the `OP1-4` op-modulation (does the original change FM op registers mid-note?), the `VOL_1` ramp behavior, or per-note pan motion.
- [ ] **Step 2 — Trace + implement** the specific Zyrinx handler in `z80_disasm.py`/`z80_driver.bin` for the divergent feature, extend the transcoder + (if needed) a new opcode, and re-diff. Repeat only while a divergence is audible/worth it. If the T5 diff is already clean enough (notes + voices match, residuals inaudible), this task is a no-op — document that.
- [ ] **Step 3 — Commit** any improvements.

---

## Self-Review

**Spec coverage:** §4 mapping (notes/voices/tempo/structure/channels) → T1+T2 ✅; §5.1 adaptive FM6 → T3 ✅; §5.2 MEV_PAN → T4 ✅; §5.3 volume dynamics → T4 ✅; §6 transcoder → T1/T2 ✅; §7 data/song-table → T1/T2/T5 ✅; §8 VGM-diff verification → T5 (+`vgm_diff.py`) ✅; §3 port→verify→deepen → T1-T5 then T6 ✅; §10 risks: adaptive-FM6/DAC-loop → T3 §1; operator-order → T2/T5 (VGM-verified); octave/tempo calibration → T1/T5; untraced features → T6.

**Placeholder scan:** the genuinely research-dependent items (the decoded-data resolution path T1§1, the operator-order ground truth T2§1/T5, the DAC-off tick path T3§1, VOL_1 ramp semantics T4§1) are structured as research-step-then-implement with a concrete VGM/Exodus acceptance — not vague TODOs. The transcoder Python is full-TDD with signatures + reference-value tests.

**Type/label consistency:** `zyrinx_note_to_pitch`/`zyrinx_tempo_to_byte`/`translate_voice`/`build_songdesc`, `Song_MovingTrucks`/`SONG_MOVINGTRUCKS`, `CHROUTE_FM6`, `MEV_PAN`/`SEQEV_PAN`/`Fm_SetPan`/`Seq_Op_Pan`, `movingtrucks_patches.asm`, `tools/vgm_diff.py` used consistently.

**Decision points (flagged, resolved by verification not guess):** note octave base (T1, VGM-calibrated); voice operator order (T2, VGM-verified); FM6 route-enum vs header-flag (T3 §2 — implementer picks the cleaner; keep DAC route intact); VOL_1 ramp vs set (T4 §1 — ship set, deepen if needed).

## Execution Handoff
Execute with `superpowers:subagent-driven-development`: fresh subagent per task, controller drives Exodus MCP + VGM diff. T5's VGM diff is the gate; T6 is verify-driven (may be a no-op if T5 is clean).
