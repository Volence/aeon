# Sound Plan 1C — Minimal FM + PSG Music Sequencer

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. A fresh subagent per task; the controller drives the Exodus MCP verification between tasks. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hear a short multi-channel song play and loop cleanly — a few FM melodic voices (FM1–FM5) + PSG tone/noise + DAC drums (reusing the 1B DAC) — driven by a hand-authored test song in a compact event-list format. This validates the *entire* music pipeline (format → sequencer → FM/PSG hardware → coexistence with the continuous DAC) on the smallest footprint.

**Architecture:** Five units with clean interfaces. (1) An on-ROM **event-list song format (v0)** — per-channel SMPS-family byte streams + a `SongHeader`. (2) A **Z80 sequencer core** — per-channel stream interpreters advanced once per tempo tick by a jump-table opcode dispatch. (3) An **FM voice writer** — note→F-number/key-on, patch load via the YM busy-poll write discipline, log-volume × per-algorithm carrier mask. (4) A **PSG voice writer** — note→10-bit divisor, attenuation, noise, pause-silence. (5) **Scheduler integration** — YM Timer-A is programmed so one overflow = one tick; the free-running 1B DAC loop polls the Timer-A overflow flag each pass and calls `Sequencer_Tick` on overflow (bounded, split across ticks if needed) so the DAC never starves. Build-time Python tools generate the F-number/PSG-divisor table, the 256-byte log-volume LUT, the 8-byte carrier-mask table, and pack the test song; AS asserts validate every table size.

**Tech Stack:** Motorola 68000 + Zilog Z80 (AS Macro Assembler `asw`); Python 3 build-time tools with `pytest` (real TDD, files `tools/test_*.py` alongside the tool, run with `python3 -m pytest tools/`); `./build.sh` (flags `SOUND_DRIVER_ENABLED=1`, `DEBUG=1`, `SOUND_DBG_MIRROR=1`); Exodus emulator MCP for hardware verification + **VGM capture** (`emulator_vgm_start`/`_stop`) parsed for the YM register-write stream.

**Source spec:** `docs/superpowers/specs/2026-06-17-sound-1c-design.md`. **Extends:** 1B (`docs/superpowers/plans/2026-06-16-sound-1b-dma-survival-dac.md`, merged to master).

---

## Verification model (bare-metal — NOT pytest for the assembly)

The Z80/68k assembly cannot be unit-tested. Each kind of work is verified differently:

- **Python build-time tools** (table generators, song packer) — **real TDD with `pytest`**: write the failing test first (`tools/test_<tool>.py`), implement, pass, commit. These are the only true unit tests in 1C.
- **Assembly** — verified by three mechanisms, used together per task:
  1. **Build-time AS asserts** — `if … error/fatal` on every table size, struct length, RAM-budget, and opcode-table count. The ROM must not build if a contract is violated.
  2. **DEBUG boot self-tests** — a `bsr` from the DEBUG boot path that exercises a routine and writes a pass/fail marker the MCP can read (mirror or 68k RAM).
  3. **Exodus MCP + VGM capture** — reload ROM (`emulator_reload_rom`), reset, resume, read YM/Z80 state, and capture a VGM (`emulator_vgm_start` → run frames → `emulator_vgm_stop`) of the YM register-write stream. Parse it (DAC `$2A`/`$28`; FM `$A0–$B6` F-number, `$28` key-on/off; PSG latch/data) to confirm structure and timing. The VGM-interval histogram approach (already used in 1B verification) confirms the DAC `$2A` cadence stays steady while the sequencer runs.

**Honor these facts from 1A/1B (the law):**
- **Z80 = Intel hex** (`80h`, `1FFEh`, `$4000` is `4000h` style — match existing file) under `cpu z80`; 68k uses `$`.
- **Keep the even-pad block last** before `dephase` in `engine/z80_sound_driver.asm` (odd blob → boot address-error).
- **No fall-through into `ret`-terminated routines** — helpers live after the main loop.
- **MCP cannot read Z80 RAM directly** (`emulator_read_memory` errors on `$A00000`). Observe Z80 state via `Sound_Dbg_Mirror` (68k RAM `$FFB202`, 64 bytes) — built only when `SOUND_DBG_MIRROR=1`. It currently copies Z80 `$1F00..$1F2F` → mirror[0..47] and `$1600..$160F` → mirror[48..63]. **New sequencer observability must fit that window or widen the copy** (Task 2 addresses this). MCP read addresses need the `0x` prefix.
- **68k↔Z80 RAM needs the Z80 bus held** (`stopZ80`/`startZ80`); a single-byte slot write is atomic under the hold (latest-wins, no pending flag).
- **The 1B DAC loop is free-running and cycle-balanced.** Any code added to the per-sample path (Task 5's Timer-A poll) must preserve a known, documented per-pass cycle cost, or the DAC pitch warbles. This is the central risk.
- Build all three configs before each commit where they can differ:
  `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`, `SOUND_DRIVER_ENABLED=1 ./build.sh -pe`, `./build.sh -pe` → all exit 0. For MCP/VGM inspection add `SOUND_DBG_MIRROR=1`.

---

## File Structure

| File | Action | Single responsibility |
|---|---|---|
| `tools/gen_sound_tables.py` | Create | Emit the AS-includable `.asm` tables: F-number+block table (semitone→YM2612), PSG 10-bit divisor table, 256-byte log-volume LUT, 8-byte per-algorithm carrier-op mask. Pure functions, no I/O in the math. |
| `tools/test_gen_sound_tables.py` | Create | pytest: equal-temperament F-num/block math, PSG divisor math, log-curve monotonicity/endpoints, carrier-mask per-algorithm correctness, output-format round-trip. |
| `tools/song_packer.py` | Create | Authoring helper: assemble a Python song description (channels + event lists) into the `SongHeader` + per-channel byte streams, emit as an AS `.asm` data file; validate opcodes/operands at pack time. |
| `tools/test_song_packer.py` | Create | pytest: opcode encoding for every v0 opcode, header layout/offsets, stream-pointer back-patching, build-time validation rejects bad opcodes/out-of-range operands. |
| `data/sound/sound_tables.asm` | Create (generated) | The four generated tables + their AS size asserts. Checked in; regenerated by `gen_sound_tables.py`. |
| `data/sound/song_test.asm` | Create (generated) | The hand-authored test song (FM voices + PSG + DAC triggers), emitted by `song_packer.py` from `data/sound/song_test.py`. |
| `data/sound/song_test.py` | Create | The hand-authored song *source* (Python description fed to the packer). The human-editable authoring artifact. |
| `data/sound/fm_patches.asm` | Create | ROM FM patch table: the per-channel YM register records (`FmPatch` struct) + patch index enum + count assert. |
| `data/sound/song_table.asm` | Create | Song-id → `SongHeader` pointer table (bank-aware), + song-id enum + count assert. |
| `sound_constants.asm` | Modify | Music opcode constants, `FmPatch`/`SeqChannel` struct layouts, sequencer Z80 RAM offsets (phase/dephase or equ block within budget), tempo/Timer-A control reg equates re-enabled, trace-buffer offsets (Task 2), channel-route enum. |
| `engine/sound_sequencer.asm` | Create | Z80: `Sequencer_Tick` loop + jump-table opcode dispatch + per-channel state advance. Hardware-agnostic (writers are called out to). Included into the Z80 blob. |
| `engine/sound_fm.asm` | Create | Z80: `Fm_PatchLoad`, `Fm_NoteOn`/`Fm_NoteOff`, `Fm_SetVolume` (log-LUT × carrier mask), YM busy-poll write helper. Included into the Z80 blob. |
| `engine/sound_psg.asm` | Create | Z80: `Psg_NoteOn`/`Psg_NoteOff`, `Psg_SetVolume`, `Psg_Noise`, `Psg_SilenceAll`. Included into the Z80 blob. |
| `engine/z80_sound_driver.asm` | Modify | Wire the new units: include the sequencer/fm/psg sources; add the Timer-A program + per-pass overflow poll in the DAC loop (Task 5); extend `SndDrv_PollMailbox` for `SND_REQ_MUSIC` (Task 6); route `$E2` to the 1B DAC path. |
| `engine/sound_api.asm` | Modify | 68k `Sound_PlayMusic(d0=song_id)` / `Sound_StopMusic` (bus-held post to `SND_REQ_MUSIC`). |
| `debug/sound_debug.asm` | Modify | Widen / add a second mirror copy for the sequencer trace buffer + per-channel state so the dry-run (Task 2) and integration (Task 5) are MCP-observable. |
| `main.asm` | Modify | `include` the generated tables, patches, song(s), and song table in the ROM data area (under `SOUND_DRIVER_ENABLED`). |
| `build.sh` | Modify (if needed) | Optionally run the table/song generators as a pre-build step (or document manual regen). Generated `.asm` is checked in either way. |

**Z80 RAM budget note (spec §11):** new sequencer state (per-channel `SeqChannel` structs × channel count, loaded song header/pointers, scratch, and the Task-2 trace buffer) must fit in the 8 KB Z80 RAM ($A00000–$A02000) alongside the 1B 256-byte ring (`$1700`), state region (`$1600`), code, and stack (`$1FFE`). Task 1 lays out the addresses with build-time overflow asserts; the spec §12.2 RAM-map sub-design is updated as part of Task 1/2.

---

## Task 1: Build-time format + tables + test song + packer

Everything that can be computed on the build PC. No Z80 code yet. Real TDD for the Python; AS asserts for the generated tables. This task defines the *contracts* the rest of 1C consumes.

**Files:** Create `tools/gen_sound_tables.py`, `tools/test_gen_sound_tables.py`, `tools/song_packer.py`, `tools/test_song_packer.py`, `data/sound/song_test.py`, generated `data/sound/sound_tables.asm` + `data/sound/song_test.asm`; Modify `sound_constants.asm`, `main.asm`.

- [ ] **Step 1 — Research (SMPS format + YM/PSG pitch math).**
  Dispatch a research subagent. Confirm against: s2disasm `s2.sounddriver.asm` (SMPS coordination-flag table + the `cfXxx` opcode dispatch, note→frequency `SMPS_FreqTbl`, the duration model), skdisasm `Sound/Z80 Sound Driver.asm` (the S3K event/flag set, PSG handling, the per-channel `TrackSz` state layout), S.C.E. `Sound/Flamedriver.asm` (its coordination-flag jump table + note table), Batman & Robin sound. Online: plutiedev YM2612 (F-number = `freq * 2^(20-block) / master_clock`, the 11-bit F-num + 3-bit block split; equal-tempered semitone ratio `2^(1/12)`), plutiedev SN76489 (10-bit divisor = `clock / (32 * freq)`, latch/data byte format, attenuation 4-bit, noise control). Produce: the exact F-num/block formula + a reference value (e.g. A4=440 Hz → expected F-num+block, so the table can be checked against a known note), the PSG divisor formula, and the SMPS opcode-dispatch pattern we'll mirror. 4–6 line note.

- [ ] **Step 2 — Lock the opcode + struct + header contracts in `sound_constants.asm`.**
  Append a "Music format v0" block. **Opcode constants (spec §4 table — these values are the contract):**
  ```asm
  ; --- Music event-list opcodes (v0) ---
  ; $00–$7F : set default duration = value (ticks)   [range-dispatched]
  MEV_REST        = $80    ; rest for default duration (key-off + advance)
  ; $81–$DF : note, pitch index = byte-$81           [range-dispatched]
  MEV_NOTE_BASE   = $81    ; pitch 0 = MEV_NOTE_BASE
  MEV_NOTE_MAX    = $DF    ; highest note opcode (pitch index 0..$5E)
  MEV_VOL         = $E0    ; + vv  : set channel volume (linear 0..127)
  MEV_PATCH       = $E1    ; + pp  : set FM patch index
  MEV_DAC         = $E2    ; + ss  : DAC trigger sample id (DAC channel only)
  MEV_NOTE_DUR    = $E3    ; + nn dd : note nn with explicit duration dd
  MEV_LOOP_POINT  = $EE    ; loop-target marker (no operand)
  MEV_JUMP        = $EF    ; jump to loop point
  MEV_END         = $FF    ; end of stream (channel idle)
  ; reserved for Phase 3: $E4–$ED, $F0–$FE (unknown opcode = build/validation error)
  ```
  **Channel-route enum** (`SongHeader` per-channel routing byte):
  ```asm
  CHROUTE_FM1 = 0
  CHROUTE_FM2 = 1
  CHROUTE_FM3 = 2
  CHROUTE_FM4 = 3
  CHROUTE_FM5 = 4
  ; (FM6 is permanently the DAC in 1C — not a sequencer FM channel)
  CHROUTE_PSG1 = 5
  CHROUTE_PSG2 = 6
  CHROUTE_PSG3 = 7
  CHROUTE_PSGN = 8    ; PSG noise
  CHROUTE_DAC  = 9    ; emits $E2 DAC triggers only
  CHROUTE_COUNT = 10
  ```
  **`FmPatch` struct** (the ~25–29 byte YM record — exact layout is the contract; 4 operators × 7 per-op regs + 2 channel regs):
  ```asm
  FmPatch struct
  fp_alg_fb     ds.b 1          ; $B0 value: algorithm (bits0-2) + feedback (bits3-5)
  fp_lr_ams_fms ds.b 1          ; $B4 value: L/R (bits6-7) + AMS (bits4-5) + FMS (bits0-2)
  fp_dt_mul     ds.b 4          ; $30+ : DT/MUL per operator (op order S1,S3,S2,S4 — YM HW order)
  fp_tl         ds.b 4          ; $40+ : TL per operator (carrier TL is volume-modulated)
  fp_rs_ar      ds.b 4          ; $50+ : RS/AR per operator
  fp_am_d1r     ds.b 4          ; $60+ : AM/D1R per operator
  fp_d2r        ds.b 4          ; $70+ : D2R per operator
  fp_d1l_rr     ds.b 4          ; $80+ : D1L/RR per operator
  FmPatch endstruct             ; = 2 + 6*4 = 26 bytes
      if FmPatch_len <> 26
        error "FmPatch struct is \{FmPatch_len} bytes, expected 26"
      endif
  ```
  *(Confirm the YM operator ordering — the YM2612 register stride is `+4` between operators within a channel and the on-hardware op order is S1,S3,S2,S4; the patch layout and the writer in Task 3 must agree. Document the chosen order here.)*
  **`SongHeader` layout** (spec §4 — this is what the packer emits and the loader reads):
  ```
  SongHeader:
    db  tempo            ; Timer-A period selector (bigger = slower)
    db  channel_count
    ; per channel: route byte + 2-byte stream pointer (Z80-window-relative)
    rept channel_count: db route ; dw stream_ptr ; endm
    dw  patch_table_ptr  ; FM patch table for this song
  ```
  Add asserts: table sizes (Step 3), `CHROUTE_COUNT` matches the enum, opcode ranges don't overlap (`MEV_NOTE_MAX < MEV_VOL`).

- [ ] **Step 3 — TDD: `gen_sound_tables.py` (write `test_gen_sound_tables.py` FIRST).**
  Tool signatures (pure functions):
  ```python
  def fnum_block(semitone: int) -> tuple[int, int]:   # -> (fnum 11-bit, block 3-bit)
  def fm_pitch_table() -> list[tuple[int,int]]:        # one entry per pitch index 0..0x5E
  def psg_divisor(semitone: int) -> int:               # 10-bit
  def psg_divisor_table() -> list[int]:
  def log_volume_lut() -> list[int]:                   # 256 entries, linear idx -> YM TL delta (log)
  def carrier_mask_table() -> list[int]:               # 8 entries, algo 0..7 -> 4-bit carrier-op mask
  def emit_asm() -> str:                                # the full sound_tables.asm text
  ```
  pytest cases (failing first):
  - `fnum_block`: equal temperament — adjacent semitones' frequency ratio ≈ `2^(1/12)` within tolerance; a known reference (from Step 1, e.g. A4) maps to the expected (fnum, block); block increments at the documented octave boundaries; fnum stays in `0..0x7FF`.
  - `fm_pitch_table` length == `MEV_NOTE_MAX - MEV_NOTE_BASE + 1` (`0x5F` = 95 entries); each entry packs to the writer's expected word format.
  - `psg_divisor`: `divisor == round(clock / (32 * freq))`, clamped to `1..0x3FF`; monotonic decreasing with rising pitch.
  - `log_volume_lut`: 256 entries; `lut[127]` = max-loudness TL delta (0 attenuation), `lut[0]` = silence/max attenuation; monotonic; endpoints exact.
  - `carrier_mask_table`: 8 entries; algo 7 → all four ops are carriers (`0b1111`), algo 0 → only op4 (`0b1000`), and the rest match the YM2612 algorithm carrier map.
  - `emit_asm`: round-trips — re-parsing the emitted `dc.b`/`dc.w` reproduces the table values; includes the AS size asserts.
  Implement until green. Generate `data/sound/sound_tables.asm`. Add AS asserts at the bottom of the generated file:
  ```asm
      if (FmPitchTable_End-FmPitchTable)/2 <> 95
        error "FM pitch table wrong length"
      endif
      if (LogVolumeLut_End-LogVolumeLut) <> 256
        error "log volume LUT must be 256 bytes"
      endif
      if (CarrierMaskTable_End-CarrierMaskTable) <> 8
        error "carrier mask table must be 8 bytes"
      endif
  ```

- [ ] **Step 4 — TDD: `song_packer.py` (write `test_song_packer.py` FIRST).**
  Tool signature:
  ```python
  def pack_song(song: SongDesc) -> bytes        # raw header+streams bytes
  def emit_asm(song: SongDesc, label: str) -> str   # AS data file
  # SongDesc: tempo:int, channels:list[ChannelDesc]; ChannelDesc: route:int, events:list[Event]
  # Event helpers: SetDur(n), Rest(), Note(pitch), Vol(v), Patch(p), Dac(s), NoteDur(n,d), LoopPoint(), Jump(), End()
  ```
  pytest cases (failing first):
  - Each event helper encodes to the exact opcode byte(s) from Step 2 (`SetDur(0x20)`→`[0x20]`, `Rest()`→`[0x80]`, `Note(0)`→`[0x81]`, `Vol(64)`→`[0xE0,0x40]`, `NoteDur(3,8)`→`[0xE3,0x03,0x08]`, `Jump()`→`[0xEF]`, `End()`→`[0xFF]`, etc.).
  - Header: byte0=tempo, byte1=channel_count, then `(route, dw stream_ptr)` per channel, then `dw patch_table_ptr`; stream pointers back-patched to the correct offsets of each channel's stream.
  - Validation rejects: a note pitch > `0x5E`; a duration value > `0x7F` in `SetDur`; `$E2` on a non-DAC route; `$E1` on a non-FM route; a `Jump` with no preceding `LoopPoint`; a stream not terminated by `End`/`Jump`.
  - `emit_asm` produces a buildable `.asm` (labeled, `even`-terminated) that the test parses back to the same bytes.

- [ ] **Step 5 — Author the test song source `data/sound/song_test.py` + generate `song_test.asm`.**
  Hand-author a minimal but representative song: at least 2 FM channels (each `Patch`→`SetDur`→a few `Note`/`Rest`→`LoopPoint`→…→`Jump`), 1 PSG tone channel, 1 PSG noise channel, and 1 DAC channel emitting a couple of `Dac(sample_id)` triggers, all looping. Keep it short (a couple of bars). Run the packer to emit `data/sound/song_test.asm` (label `Song_Test`, header + streams + a small per-song FM patch table pointer). The song is the integration target for Tasks 5–6; here it just has to pack and build.

- [ ] **Step 6 — Wire into the ROM data area + build asserts.**
  In `main.asm`, under `SOUND_DRIVER_ENABLED`, `include` `data/sound/sound_tables.asm`, `data/sound/fm_patches.asm` (created Task 3 — add the include now, stub the file with an empty table + `even` so it builds), `data/sound/song_test.asm`, and `data/sound/song_table.asm` (created Task 6 — likewise stub now or defer the include to Task 6; pick one and note it). Place them in the ROM data block (not inside the Z80 `phase 0` blob). Build all three configs `-pe` → exit 0; the table-size asserts pass.

- [ ] **Step 7 — Run the Python suite + commit.**
  ```bash
  python3 -m pytest tools/test_gen_sound_tables.py tools/test_song_packer.py -q
  SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe   # + the other two configs
  git add tools/gen_sound_tables.py tools/test_gen_sound_tables.py \
          tools/song_packer.py tools/test_song_packer.py \
          data/sound/song_test.py data/sound/sound_tables.asm \
          data/sound/song_test.asm sound_constants.asm main.asm
  git commit -m "feat(sound 1c): music format v0 + build-time tables + song packer"
  ```

---

## Task 2: Sequencer core (RAM-only dry run)

The opcode interpreter, driven first by a **stub writer** that logs to a Z80 RAM trace buffer (mirrored to 68k for MCP) — verifying stream-walking, duration counting, loops, and dispatch *without touching any sound hardware*. No FM/PSG yet.

**Files:** Modify `sound_constants.asm` (RAM layout + trace buffer), Create `engine/sound_sequencer.asm`, Modify `engine/z80_sound_driver.asm` (include it; DEBUG dry-run hook), Modify `debug/sound_debug.asm` (mirror the trace + channel state).

- [ ] **Step 1 — Research (SMPS tick loop + per-track state).**
  Research subagent: from s2disasm/skdisasm, extract the SMPS per-track state block (`TrackSz`: stream ptr, duration timeout, saved duration, current note, volume, the active/rest flags) and the main tick (`TempoWait`/`Track_Run`): decrement the duration timeout, on expiry fetch+dispatch the next opcode(s), reload the timeout. Confirm the jump-table dispatch for the coordination-flag range (how SMPS turns a `$Ex` byte into a handler address) and how it handles the note-vs-flag range split. From S.C.E. Flamedriver: its equivalent. Produce the minimal tick-loop skeleton + the per-channel struct field order best for Z80 indexed (`ix`/`iy`) access. 4–5 lines.

- [ ] **Step 2 — `SeqChannel` struct + sequencer RAM layout (`sound_constants.asm`).**
  ```asm
  SeqChannel struct
  sc_stream_ptr   ds.w 1   ; +0  current read ptr into the channel byte stream
  sc_dur_count    ds.b 1   ; +2  ticks remaining on the current note/rest
  sc_dur_default  ds.b 1   ; +3  default duration for bare notes
  sc_patch        ds.b 1   ; +4  current FM patch index
  sc_volume       ds.b 1   ; +5  current channel volume (linear 0..127)
  sc_note         ds.b 1   ; +6  current pitch index (for key-off / debug)
  sc_flags        ds.b 1   ; +7  bit0=active, bit1=keyed, bit2=is_fm, bit3=is_psg, bit4=is_dac
  sc_route        ds.b 1   ; +8  channel route enum (CHROUTE_*) — selects the writer
  sc_loop_ptr     ds.w 1   ; +9  saved loop-point ptr (set by $EE, used by $EF)
  SeqChannel endstruct      ; = 11 bytes (round to 16 for shift-indexing if cheap)
  ```
  *(Spec says ~8 bytes; the loop-ptr + route push it to 11. Either keep 11 and index by add, or pad to 16 for `add a,a`×4 shift-indexing — decide by the research and document. If padded, assert the pad.)*
  Add the Z80 RAM block (within the 8 KB budget, clear of `$1600` state, `$1700` ring, code, `$1FFE` stack):
  ```asm
  SND_SEQ_BASE       = $1800          ; sequencer state region (growth reserve below the ring? confirm vs map)
  SND_SEQ_TEMPO      = SND_SEQ_BASE+$00   ; loaded song tempo (Timer-A selector)
  SND_SEQ_CHCOUNT    = SND_SEQ_BASE+$01
  SND_SEQ_PATCHTAB   = SND_SEQ_BASE+$02   ; loaded patch table ptr (2)
  SND_SEQ_ACTIVE     = SND_SEQ_BASE+$04   ; 1 = song playing
  SND_SEQ_CHANNELS   = SND_SEQ_BASE+$08   ; CHROUTE_COUNT * SeqChannel_len
  SND_SEQ_END        = SND_SEQ_CHANNELS + (CHROUTE_COUNT * SeqChannel_len)
      if SND_SEQ_END > SND_RING_BASE
        fatal "sequencer RAM overruns the DAC ring at \{SND_RING_BASE}"
      endif
  ; --- DEBUG dry-run trace ring (Task 2 only-ish; observable via mirror) ---
  SND_SEQ_TRACE      = $1A00          ; 32-byte trace ring of dispatched opcodes
  SND_SEQ_TRACE_LEN  = 32
  SND_SEQ_TRACE_WR   = SND_SEQ_BASE+$06
  ```
  *(Confirm the exact base addresses against the live z80-ram-map sub-design; the values above are illustrative — the implementer must place them in real free space and let the `fatal` guard prove no overlap. Update spec §12.2 RAM-map.)*

- [ ] **Step 3 — `engine/sound_sequencer.asm`: the tick loop + dispatch.**
  Structure (Z80; hardware-agnostic — calls out to writer hooks that are *stubs* this task):
  - `Sequencer_Tick`: `ld a,(SND_SEQ_ACTIVE) / or a / ret z`. Then loop over channels: `ld ix,SND_SEQ_CHANNELS`, `ld b,(SND_SEQ_CHCOUNT)`; per channel — if `sc_flags` bit0 (active) clear, skip; else `Sequencer_Channel`; `lea`-equivalent advance `ix += SeqChannel_len` (Z80: `ld de,SeqChannel_len / add ix,de`); `djnz`.
  - `Sequencer_Channel`: decrement `(ix+sc_dur_count)`; `jr nz, .still_holding` (held note → no work). On expiry, fall into `Sequencer_NextOpcode`.
  - `Sequencer_NextOpcode`: `ld l,(ix+sc_stream_ptr) / ld h,(ix+sc_stream_ptr+1)`; `ld a,(hl)`; **range-dispatch**: `cp MEV_REST` (`$80`) → below it is set-duration (`< $80`): store `a` into `sc_dur_default`, `inc hl`, loop to fetch the next opcode (a duration-set has no time cost — it precedes a note). `cp MEV_VOL` (`$E0`) → between `$81..$DF` is a note: pitch = `a - MEV_NOTE_BASE` → call the **writer hook** with pitch + reload `sc_dur_count` from `sc_dur_default`, `inc hl`, set keyed flag, store ptr, return. `$80` (rest): key-off hook, reload duration, advance. `>= $E0`: jump-table dispatch on `a - MEV_VOL` into the handler table for `$E0..` (vol/patch/dac/notedur/…/loop/jump/end). **Unknown opcode in a reserved slot → DEBUG `RaiseError`-equivalent (write a fail marker)**; the packer already forbids them, this is defense-in-depth.
  - Handlers: `$E0` vol → read operand, store `sc_volume`, call set-vol hook. `$E1` patch → store `sc_patch`, call patch hook. `$E2` dac → call DAC trigger hook with operand. `$E3` notedur → read pitch+dur operands, note-on hook, set `sc_dur_count`=dur. `$EE` loop-point → save `hl` (after the opcode) into `sc_loop_ptr`, continue fetching (zero time cost). `$EF` jump → `ld hl,(sc_loop_ptr)`, continue fetching. `$FF` end → clear active flag, return.
  - **The writer hooks this task are STUBS** that append `(route<<4)|event_code` to the `SND_SEQ_TRACE` ring and bump `SND_SEQ_TRACE_WR`. No YM/PSG writes. This isolates the interpreter.
  Add `include "engine/sound_sequencer.asm"` inside the Z80 blob in `engine/z80_sound_driver.asm` (after the main loop / helpers, before the even-pad). Keep it inside `phase 0` so labels resolve into the blob.

- [ ] **Step 4 — DEBUG dry-run driver + widen the mirror.**
  In `engine/z80_sound_driver.asm` (DEBUG only), add a one-shot dry-run: in `SndDrv_Init` under a `SOUND_SEQ_DRYRUN`-style guard, load `Song_Test` into the sequencer state (set per-channel `sc_stream_ptr` from the header, `sc_flags` active+route, `SND_SEQ_ACTIVE=1`) and call `Sequencer_Tick` a fixed number of times from a counter in the ISR (or step it from the idle loop), so the trace fills. (No Timer-A yet — Task 5. Here the dry-run is a bounded manual pump.)
  In `debug/sound_debug.asm`, add a third mirror copy: `SND_SEQ_BASE..` (the per-channel `sc_*` state + `SND_SEQ_TRACE` ring) into a free part of the 64-byte `Sound_Dbg_Mirror`, or **widen `Sound_Dbg_Mirror` in `ram.asm`** to e.g. 128 bytes and copy the sequencer window into mirror[64..]. Document the new offsets.

- [ ] **Step 5 — Build + Exodus dry-run verification (NOT pytest).**
  Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 SOUND_DBG_MIRROR=1 ./build.sh -pe` (+ the non-mirror DEBUG and release configs) → exit 0; RAM-overflow `fatal` does not trip.
  Exodus (controller): `emulator_reload_rom`, reset, resume a few frames, `emulator_read_memory` the mirror. **Expected observation:** the `SND_SEQ_TRACE` ring contains the exact opcode sequence the test song's streams should dispatch (e.g. for an FM channel: patch-set, then a run of note events at the authored cadence, then the loop wrap back to the loop-point), and each channel's `sc_dur_count`/`sc_stream_ptr` advance consistently and **wrap at the loop point** rather than running off the end. A channel that hit `$FF` shows its active flag cleared. **Concrete pass:** the trace's note count per loop iteration matches the song's authored note count, and the stream pointer returns to the post-`$EE` address on `$EF`.

- [ ] **Step 6 — Commit.**
  ```bash
  git add sound_constants.asm engine/sound_sequencer.asm engine/z80_sound_driver.asm \
          debug/sound_debug.asm ram.asm
  git commit -m "feat(sound 1c): sequencer core + opcode dispatch (RAM-only dry run, traced)"
  ```

---

## Task 3: FM voice writer + patch load

Replace the FM stub hooks with real YM2612 writes: patch load (busy-poll discipline), note-on (F-number + key-on with op mask), note-off, and volume = `log_lut[vol]` applied only to carrier operators. One FM channel becomes audible.

**Files:** Create `engine/sound_fm.asm`, Create `data/sound/fm_patches.asm` (fill the Task-1 stub), Modify `engine/sound_sequencer.asm` (call the FM writer for FM routes), Modify `engine/z80_sound_driver.asm` (include).

- [ ] **Step 1 — Research (YM write discipline + key-on + F-num).**
  Research subagent: from s2disasm/skdisasm/Flamedriver — the YM register-pair write helper (select reg on the part-I/part-II address port, **busy-poll bit7 of `$4000` before each write**, then write data; part I = `$4000/$4001` for ch1-3, part II = `$4002/$4003` for ch4-6); the key-on/off write to reg `$28` (`<op-mask:4><0:1><channel:3>`, where channel encodes part+index, e.g. ch4 = `$04|...`); the F-number write order (`$A4+n` high byte/block first, then `$A0+n` low byte); how TL (`$40+`) maps to volume and which operators are carriers per algorithm. plutiedev YM2612 page for the part-I/part-II addressing and the busy-flag timing. Confirm whether the 1B DAC path's `de=$4001` invariant survives FM writes to `$4002/$4003` (FM4–6 use part II) — the FM writer must restore/re-park `de` and reg `$2A` so the DAC loop's invariant holds. **This is the coexistence subtlety** — document it explicitly.

- [ ] **Step 2 — `data/sound/fm_patches.asm`: real patch records.**
  Define the patch table (`FmPatch` records) + a patch-index enum (`PATCH_BASS=0`, `PATCH_LEAD=1`, …) the test song references. Migrate a few simple patches' register values from `sonic_hack` SMPS voice data (data-only reuse per project policy — translate the SMPS voice byte layout into our `FmPatch` field order; do NOT copy code). Add a count assert:
  ```asm
      if (FmPatchTable_End-FmPatchTable)/FmPatch_len <> PATCH_COUNT
        error "FM patch table count mismatch"
      endif
  ```

- [ ] **Step 3 — `engine/sound_fm.asm`: the writers.**
  Z80 routines (each documents clobbers; leaf where possible):
  - `Fm_YmWrite` — `In: a=reg, c=data, b=part(0=I/1=II)`. Busy-poll `$4000` bit7; select reg on `$4000` (part I) or `$4002` (part II); write data to `$4001`/`$4003`. **Then re-park the DAC invariant** (re-select `$2A` on `$4000`, leave `de=$4001`) per Step-1's coexistence note — or document that the caller batches and re-parks once at the end.
  - `Fm_PatchLoad` — `In: ix=SeqChannel (gives route→FM channel index), hl=FmPatch ptr`. Map route→(part, channel-in-part, reg base offset). Write `fp_alg_fb`→`$B0+ch`, `fp_lr_ams_fms`→`$B4+ch`, then the 4 operators × 6 per-op regs (`$30/$40/$50/$60/$70/$80` + `ch` + op-stride `*4`) via `Fm_YmWrite`. Store the patch's algorithm (for the carrier mask) into the channel state. **One-time per patch change** (busy-poll cost is amortized, not per-tick-per-note).
  - `Fm_SetVolume` — `In: ix=channel, a=linear vol`. `log = LogVolumeLut[a]`. `mask = CarrierMaskTable[algorithm]`. For each of the 4 operators whose mask bit is set, write `$40+ch+op*4` = `min(0x7F, base_TL + log)` (base_TL from the patch). **Carriers only** — modulator TL untouched (preserves timbre). Cache the per-op base TL from the patch so volume changes don't re-read ROM each time.
  - `Fm_NoteOn` — `In: ix=channel, a=pitch index`. `FmPitchTable[pitch]` → fnum+block word; write `$A4+ch` (block + fnum high), `$A0+ch` (fnum low); key-on `$28` = `(op_mask<<4)|chsel` with op_mask = all-on. Set keyed flag.
  - `Fm_NoteOff` — key-off `$28` = `chsel` (op_mask=0). Clear keyed flag.
  Add `include "engine/sound_fm.asm"` to the Z80 blob.

- [ ] **Step 4 — Route FM events from the sequencer to the FM writer.**
  In `engine/sound_sequencer.asm`, replace the FM-route stub hooks: note → `Fm_NoteOn`, rest/key-off → `Fm_NoteOff`, vol → `Fm_SetVolume`, patch → `Fm_PatchLoad`. Gate by `sc_flags` is_fm / route in `CHROUTE_FM1..FM5`. PSG/DAC routes still stub (Tasks 4/6). **Keep the trace stub firing too** (so MCP can still see dispatch) under DEBUG.

- [ ] **Step 5 — Build + Exodus/VGM verification.**
  Build all configs `-pe` → exit 0. Drive the dry-run (or a minimal "play one FM channel" DEBUG path) so one FM channel runs.
  Exodus (controller): capture a VGM (`emulator_vgm_start` → run ~60 frames → `emulator_vgm_stop`). **Expected in the VGM stream:** YM writes to `$B0` (algorithm/fb) and the operator regs at patch-load time; then a cadence of `$A4`/`$A0` (F-number) writes each followed by a `$28` key-on, with `$28` key-off at note ends — at the song's tick cadence. Spot-check one note's F-num bytes against `FmPitchTable[pitch]` (the Task-1 reference value). Confirm the DAC `$2A` writes still appear interleaved (coexistence intact). **User confirms one audible, in-tune FM voice.** Also verify via `emulator_get_channel_states` that an FM channel is keyed.

- [ ] **Step 6 — Commit.**
  ```bash
  git add engine/sound_fm.asm data/sound/fm_patches.asm engine/sound_sequencer.asm \
          engine/z80_sound_driver.asm sound_constants.asm
  git commit -m "feat(sound 1c): FM voice writer + patch load + log-vol carrier mask"
  ```

---

## Task 4: PSG voice writer

PSG tone (3 channels) + noise audible from the same sequencer; pause silencing.

**Files:** Create `engine/sound_psg.asm`, Modify `engine/sound_sequencer.asm` (PSG routes), Modify `engine/z80_sound_driver.asm` (include).

- [ ] **Step 1 — Research (SN76489 from the Z80).**
  Research subagent: from skdisasm (S3K has full PSG) + S.C.E. + plutiedev SN76489 — the Z80 PSG port (`$7F11` from the Z80; confirm vs our `SND_Z80_*` equates — the PSG is written through the Z80's `$7F11` mirror, not the YM ports), the latch+data format (tone: `1 cc 0 dddd` latch low-4-bits, then `0 dddddddd` data high-6-bits; volume: `1 cc 1 vvvv` attenuation; noise: `1 11 0 0sff` control, `1 11 1 vvvv` attenuation), the 10-bit divisor split across latch/data bytes, and the noise-mode bits (periodic vs white, shift-rate / tone-3-tracking). Produce the exact byte sequences for tone note-on, volume, and noise.

- [ ] **Step 2 — `engine/sound_psg.asm`: the writers.**
  Z80 routines (write to the PSG port — `$7F11` per research):
  - `Psg_NoteOn` — `In: ix=channel (PSG1..3), a=pitch index`. `PsgDivisorTable[pitch]` → 10-bit divisor; emit latch byte `$80 | (ch<<5) | (div & $0F)` then data byte `(div >> 4) & $3F`.
  - `Psg_NoteOff` — set the channel's attenuation to silence (`$9F`-style with the channel's volume-latch bits): `$90 | (ch<<5) | $0F`.
  - `Psg_SetVolume` — `In: ix=channel, a=linear vol`. Map linear 0..127 → 4-bit attenuation (PSG attenuation is already log-ish; use a small linear→attenuation map, or reuse the top bits of the log LUT — decide and document). Emit `$90 | (ch<<5) | atten`.
  - `Psg_Noise` — noise channel: control byte `$E0 | mode` + attenuation `$F0 | atten`. note-on/off via attenuation.
  - `Psg_SilenceAll` — emit `$9F, $BF, $DF, $FF` (the four PSG silence latches; same bytes the boot table already uses) for `StopMusic`.
  Add `include "engine/sound_psg.asm"` to the Z80 blob.

- [ ] **Step 3 — Route PSG events.**
  In `engine/sound_sequencer.asm`, wire PSG routes (`CHROUTE_PSG1..PSGN`): note → `Psg_NoteOn`/`Psg_Noise`, rest → `Psg_NoteOff`, vol → `Psg_SetVolume`. **Pause silencing:** add a `Sequencer_SilencePsg`/`Sequencer_StopAll` entry that calls `Psg_SilenceAll` + FM key-offs (used by `StopMusic` in Task 6).

- [ ] **Step 4 — Build + Exodus/VGM verification.**
  Build all configs `-pe` → exit 0. Run the test song's PSG channels (dry-run/DEBUG pump).
  Exodus: VGM capture. **Expected:** PSG latch/data byte pairs at the song's cadence on the PSG tone channels, noise control bytes on the noise channel, and on a `StopMusic`/silence path the four `$9F/$BF/$DF/$FF` silence bytes. `emulator_get_channel_states` shows PSG channels active. **User confirms audible PSG tone + noise**, and that silencing stops them cleanly (no sustained tone).

- [ ] **Step 5 — Commit.**
  ```bash
  git add engine/sound_psg.asm engine/sound_sequencer.asm engine/z80_sound_driver.asm sound_constants.asm
  git commit -m "feat(sound 1c): PSG voice writer (tone+noise) + pause silencing"
  ```

---

## Task 5: Scheduler integration (the tricky part — the §8 risk)

Program YM Timer-A so one overflow = one tick (tempo from the song header). The free-running 1B DAC loop polls the Timer-A overflow flag once per pass; on overflow it re-arms the timer and calls `Sequencer_Tick`, bounded (split across ticks if needed) so the DAC never starves. **VGM-verify the DAC `$2A` cadence stays acceptable while the sequencer runs** — the headline risk; validate it here before building the full song on top.

**Files:** Modify `engine/z80_sound_driver.asm` (Timer-A program + per-pass poll + bounded `Sequencer_Tick` call), Modify `sound_constants.asm` (Timer-A control values, tempo finalization), Modify `debug/sound_debug.asm` (tick counter observability).

- [ ] **Step 1 — Research (Timer-A as tick source + cycle budget).**
  Research subagent: from plutiedev YM2612 (Timer-A: regs `$24`/`$25` = 10-bit N, `$27` = Timer control — load/enable Timer-A bit + the overflow-flag bit; reading `$4000` returns the status with Timer-A overflow in a status bit; you **re-arm by writing `$27` to reset the overflow flag**). From SMPS/Flamedriver: how the driver uses Timer-A (or the VBlank) as its tempo base and how it bounds per-tick work. Confirm the exact `$27` bits to (a) load+enable Timer-A and (b) clear the overflow flag, and the status-port bit to test. **Critically:** budget the added per-DAC-pass cost — reading `$4000` status + `bit` test + `jp` must be a *constant* small cost on every pass (it cannot be on the FILL path only, or the cycle balance breaks). Determine where in the balanced loop the poll fits and how many cycles it adds to all three paths equally. Produce the poll snippet + the re-arm sequence + the cycle delta to add to `SND_LOOP_CYC`.

- [ ] **Step 2 — Program Timer-A from the song tempo.**
  In `sound_constants.asm`, finalize the tempo/Timer-A equates (the `ym_timerA_n(tpf)` function already exists; re-enable `SND_REG_TIMER_A_HI/LO/CTRL` use). On song start (the loader, Task 6 — here add the routine), write `$24`=`tempo>>2`, `$25`=`tempo&3` (the song-header tempo byte is the Timer-A selector), `$27`= load+enable Timer-A. Add `Snd_TimerA_Program` (Z80) and `Snd_TimerA_Rearm` (write `$27` to reset the overflow flag + keep enabled).

- [ ] **Step 3 — Per-pass Timer-A poll in the DAC loop.**
  In `SndDrv_Sample` (and the idle loop), add — at the spot the research identified, with **equal cost on FILL/SKIP/DRAIN** — a read of `$4000` status, test the Timer-A overflow bit; if set: `Snd_TimerA_Rearm` + `call Sequencer_Tick`. **Update the cycle-balance proof comment** at the top of the file: the poll adds a constant `K` cycles to every path; bump `SND_LOOP_CYC` accordingly so `SND_DAC_RATE_HZ` reflects the new rate. The `Sequencer_Tick` call only fires on overflow (a few hundred Hz), not every pass — but it **must be bounded**: if a full tick (all channels, worst case a patch-load) exceeds the safe budget between DAC samples, **split the work across ticks** (service half the FM channels per tick — spec §8 / master spec §4.2): add a per-tick channel cursor in sequencer state so each overflow services a bounded slice. Document the chosen bound and how the DAC sample that absorbs a tick is momentarily longer (the bounded micro-perturbation).

- [ ] **Step 4 — Tick observability.**
  Increment `SND_STAT_TICK` (already reserved) in `Sequencer_Tick`. Mirror it (already in the `$1F00..$1F2F` window → mirror[3]). Optionally mirror the per-tick channel cursor.

- [ ] **Step 5 — Build + the critical VGM cadence verification.**
  Build all configs `-pe` → exit 0; the updated `SND_LOOP_CYC`/rate asserts hold.
  Exodus (controller — **this is the gating verification for the whole plan**):
  - `emulator_reload_rom`, reset, resume, start a song (or the dry-run pumped by the real Timer-A now).
  - `emulator_read_memory` mirror[3] (`SND_STAT_TICK`): it increments at the **expected tick rate** (Timer-A N from the song tempo → ticks/sec; over N frames the counter delta matches `ticks_per_frame * frames`). This proves the tempo math.
  - **VGM capture while music + DAC run together.** Parse the `$2A` DAC write intervals into a histogram (the 1B method). **Expected/pass:** the `$2A` cadence stays within an acceptable band — the periodic tick-rate perturbation (one slightly-longer DAC sample per tick) is bounded and small; there is **no** sustained gap or runaway drift. Compare the histogram to the 1B baseline (music off): the mean interval is ~unchanged, with a small periodic tail at the tick rate. If the cadence degrades (audible warble / dropout), the `Sequencer_Tick` slice is too big → tighten the split in Step 3 and re-verify. **User confirms the DAC stays clean while a tick runs.**

- [ ] **Step 6 — Commit.**
  ```bash
  git add engine/z80_sound_driver.asm sound_constants.asm debug/sound_debug.asm
  git commit -m "feat(sound 1c): Timer-A tick scheduler in the DAC loop (cadence-verified)"
  ```

---

## Task 6: Command API + DAC drums + full song

Wire the 68k command API, route `$E2` DAC triggers to the 1B sample path, add the bank-aware song table, and play the full test song (FM + PSG + drums) end-to-end, looping.

**Files:** Modify `engine/sound_api.asm` (68k helpers), Modify `engine/z80_sound_driver.asm` (`SND_REQ_MUSIC` handler + song loader + `$E2`→DAC route), Create `data/sound/song_table.asm`, Modify `main.asm` (include the song table).

- [ ] **Step 1 — Research (command handling + DAC re-trigger mid-music).**
  Research subagent: from Flamedriver/SMPS — how a "play music id" command loads a song (header parse, per-channel init, patch preload, start tempo) and how "stop" silences cleanly; how the driver mixes a DAC drum trigger *while FM/PSG music plays* (in 1C: FM6 stays the DAC, the music's DAC channel just posts to the existing 1B sample path). Confirm the 1B sample-start path (`SndDrv_PollMailbox`'s `SND_REQ_SAMPLE` branch) can be **re-entered for a new sample id mid-music** without clicking (it re-arms `$2B`, re-points the ROM ptr, re-primes the ring). Produce the loader sequence + the `$E2`→1B-DAC-path call.

- [ ] **Step 2 — Song table (bank-aware) `data/sound/song_table.asm`.**
  ```asm
  SONG_TEST = 1
  SONG_COUNT = 1
  SongTable:
      dc.l    Song_Test       ; id 1  (full 68k ROM address; loader derives bank+window via SetBank if banked)
  SongTable_End:
      if (SongTable_End-SongTable)/4 <> SONG_COUNT
        error "song table count mismatch"
      endif
  ```
  *(Songs live in ROM; if a song's bytes sit above the Z80 `$8000` window they must be reachable via `SndDrv_SetBank` like DAC samples. For the test song, keep it bank-aligned/within reach and document the addressing — header+streams are read by the Z80, so they need a Z80-window pointer + bank, same pattern as `DacSample`. Confirm whether the test song can live in the always-mapped low region or needs banking.)*
  Include from `main.asm` under `SOUND_DRIVER_ENABLED`.

- [ ] **Step 3 — Z80 `SND_REQ_MUSIC` handler + song loader.**
  In `SndDrv_PollMailbox`, add: `ld a,(SND_REQ_MUSIC) / or a / jr z,.no_music`. If nonzero: if `0`-was-the-special-stop is handled by id 0 → call `Sequencer_StopAll` (FM key-offs + `Psg_SilenceAll` + `SND_SEQ_ACTIVE=0` + disable Timer-A). Else id≥1 → `Snd_LoadSong`: look up `SongTable[id-1]`, `SetBank` if needed, parse the `SongHeader` (tempo, channel_count, per-channel route+stream_ptr → init each `SeqChannel`: ptr, route, flags active, default vol), store `SND_SEQ_PATCHTAB`, preload each FM channel's initial patch (optional — patches also set via `$E1` in-stream), `Snd_TimerA_Program tempo`, `SND_SEQ_ACTIVE=1`. Clear the slot. Bump `SND_STAT_ACK_COUNT`.
  **Route `$E2` to the 1B DAC path:** in the sequencer's DAC-route handler for `$E2`, instead of the stub, post into the 1B sample-start path (call the shared sample-start routine with the operand sample id — refactor 1B's `SND_REQ_SAMPLE` body into a callable `Snd_StartSample` if not already, so both the mailbox and the sequencer can invoke it). FM6/DAC stays the 1B channel.

- [ ] **Step 4 — 68k API helpers `engine/sound_api.asm`.**
  ```asm
  ; Sound_PlayMusic — start (or switch to) a song. In: d0.b = song id (nonzero).
  Sound_PlayMusic:
          lea     (SND_Z80_BASE+SND_REQ_MUSIC).l, a0
          bra.w   Sound_PostByte
  ; Sound_StopMusic — stop all music (FM key-off + PSG silence). 
  Sound_StopMusic:
          moveq   #0, d0
          lea     (SND_Z80_BASE+SND_REQ_MUSIC).l, a0
          bra.w   Sound_PostByte
  ```
  *(0 = stop is the spec's convention; the Z80 handler treats `SND_REQ_MUSIC`=0-after-nonzero as "no request" normally — so encode stop as a distinct sentinel if 0 can't mean "stop" in the latest-wins slot model. Resolve: use id 0 reserved = stop only if the handler special-cases a separate stop flag, else use a `SND_REQ_MUSIC_STOP` value like `$FF`. Decide in Step 1's research and keep `sound_constants.asm` authoritative.)*

- [ ] **Step 5 — DEBUG boot hook to play the full song.**
  In `engine/boot.asm` DEBUG path (next to the existing `Sound_PlaySample`), add `moveq #SONG_TEST,d0 / bsr.w Sound_PlayMusic` so the full song plays at boot. Remove/guard the Task-2 dry-run pump (the real Timer-A drives the sequencer now).

- [ ] **Step 6 — Build + full-song Exodus/VGM verification.**
  Build all configs `-pe` → exit 0.
  Exodus (controller): `emulator_reload_rom`, reset, resume. **Expected:**
  - VGM capture shows **all three layers together**: FM `$A0–$B6`+`$28` (FM1–FM5 melodic), PSG latch/data (tone+noise), and DAC `$2A` (the drum samples re-triggered by `$E2` at the authored beats).
  - `SND_STAT_TICK` increments steadily; each channel's `sc_stream_ptr` (mirror) **wraps at its loop point** — the song loops seamlessly (the `$EF` jump returns each stream to its `$EE` marker).
  - The DAC drum triggers (`$E2`) line up with the DAC `$2A` re-prime events (a new sample id mid-music re-points the ROM ptr without a click — verify no `$2B` toggle spam).
  - **User confirms: the full multi-channel test song plays and loops cleanly** — FM melody + PSG + drums, no dropout, in tune, the loop seam is clean.
  - `Sound_StopMusic` (drive a stop) silences FM + PSG cleanly (VGM shows key-offs + the four PSG silence bytes; Timer-A disabled).

- [ ] **Step 7 — Commit + merge.**
  ```bash
  git add engine/sound_api.asm engine/z80_sound_driver.asm data/sound/song_table.asm \
          engine/boot.asm main.asm sound_constants.asm
  git commit -m "feat(sound 1c): PlayMusic/StopMusic API + DAC drums + full test song"
  ```
  Per CLAUDE.md git workflow: when the plan is complete and verified, merge `feat/sound-1c` → `master`.

---

## Self-Review

**Spec coverage (vs `2026-06-17-sound-1c-design.md`):**
- §4 event-list format v0 (opcodes, SongHeader, pitch table) → Task 1 ✅
- §5 sequencer core (per-channel state, tick loop, jump-table dispatch) → Task 2 ✅
- §6 FM voice writer + patch format + log-vol × carrier mask → Tasks 1 (tables) + 3 ✅
- §7 PSG voice writer + pause silencing → Task 4 ✅
- §8 scheduler integration (Timer-A tick, DAC-loop poll, bounded split, cadence risk) → Task 5 ✅
- §9 68k↔Z80 command API (PlayMusic/StopMusic, song table, bank-aware) → Task 6 ✅
- §10 verification (Exodus + VGM + DEBUG self-test + tempo correctness) → per-task verify steps + Task 5/6 VGM ✅
- §11 Z80 RAM budget update → Task 1/2 (RAM layout + overflow `fatal`); spec §12.2 RAM-map updated ✅
- §12 decomposition (6 tasks) → Tasks 1–6, same order ✅
- §13 risks: sub-tick vs DAC cadence → Task 5 step 5 (gating VGM); YM busy-poll cost → Task 3 step 1 + Task 5 step 1 budget; F-num accuracy → Task 1 step 3 (reference-value test) + Task 3 step 5 (spot-check vs VGM); v0 minimalism accepted ✅

**Placeholder scan:** The genuinely hardware/research-dependent items are structured as *research-step-then-implement with a concrete acceptance*, not "TODO": the YM part-I/part-II `de`-invariant coexistence (Task 3 §1), the Timer-A poll's equal-cost placement + the bounded tick split (Task 5 §1/§3), the stop-sentinel encoding (Task 6 §4), and the test-song addressing/banking (Task 6 §2). Each names the exact thing the research must resolve before coding. No vague "implement the rest" — every assembly task gives the routine structure, the register/instruction sequence, and the exact AS-assert + Exodus/VGM observation.

**Decision points the implementer must resolve (flagged inline, not left silent):**
1. `SeqChannel` size 11 vs padded-16 (indexing cost) — Task 2 §2.
2. Exact YM operator ordering in `FmPatch` (S1,S3,S2,S4) — Task 1 §2 / Task 3 §1 must agree.
3. PSG linear→attenuation map (small table vs reuse log LUT top bits) — Task 4 §2.
4. Stop encoding (id 0 vs a `$FF` sentinel in the latest-wins slot) — Task 6 §4.
5. Test-song ROM addressing (low region vs banked like DAC) — Task 6 §2.
6. The exact free Z80 RAM bases for `SND_SEQ_*` (the values shown are illustrative; the `fatal` overflow guard proves the real placement) — Task 2 §2, reconciled with the live z80-ram-map sub-design.

**Type/label consistency:** `MEV_*` opcodes, `CHROUTE_*` routes, `FmPatch`/`FmPatchTable`, `SeqChannel`, `SND_SEQ_*`, `Sequencer_Tick`/`Sequencer_Channel`/`Sequencer_NextOpcode`/`Sequencer_StopAll`, `Fm_{YmWrite,PatchLoad,SetVolume,NoteOn,NoteOff}`, `Psg_{NoteOn,NoteOff,SetVolume,Noise,SilenceAll}`, `Snd_{TimerA_Program,TimerA_Rearm,LoadSong,StartSample}`, `Sound_{PlayMusic,StopMusic}`, `Song_Test`/`SongTable`/`SONG_TEST`, `FmPitchTable`/`PsgDivisorTable`/`LogVolumeLut`/`CarrierMaskTable` used consistently across tasks.

---

## Execution Handoff

After approval, execute with `superpowers:subagent-driven-development`: a fresh subagent per task (headless code + build + AS asserts + Python pytest + commit), with the controller driving the Exodus MCP + VGM verification between tasks. Task 5's cadence VGM is the gate before Task 6 — do not build the full song until the DAC cadence is confirmed acceptable with the sequencer running.
