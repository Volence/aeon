# Music Expression Engine — Phase 2: Global Controls & Game-Feel

> **For agentic workers:** REQUIRED SUB-SKILL — use `superpowers:subagent-driven-development` (or `superpowers:executing-plans`). Each numbered step is a checkbox: build + verify before moving on. Commit after each task; commit messages end with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

**Date:** 2026-06-27
**Branch:** `feat/music-expr-p1` (worktree `/home/volence/sonic_hacks/s4_engine-music-expr`; Phase 1 already merged on this branch)
**Spec:** `docs/superpowers/specs/2026-06-23-music-expression-engine-design.md` (§3.1 two fold-points, §6 T3 hardware LFO, §7 T4 master fade + global tempo)
**Command-API contract:** `docs/superpowers/specs/2026-06-16-sound-command-api.md` (NOTE: the shipped code uses **discrete per-type `SND_REQ_*` byte slots**, not the `MBX_CMD` jump-table from that doc — Phase 2 follows the shipped model.)

---

## Goal

Add the three **global, game-feel** controls that close the biggest expressive gaps, each independently verifiable and each leaving the build green:

1. **Master fade** — one global attenuation scalar `SND_MASTER_FADE` folded into the engine's two existing music volume writes (FM carrier-TL in `Fm_SetVolume`, PSG attenuation in `Psg_SetVolume`), driven by a tiny per-frame fade state machine, with a global "fade-dirty" flag so `ModUpdate` re-asserts held-note volumes during a fade. Triggered by a 68k API + `SND_REQ_FADE` mailbox slot (Fade-Out / Fade-In).
2. **Global tempo + ramp** — a global per-frame decrement scalar `SND_TEMPO_CUR` replacing the literal `16` in the per-channel tempo accumulator (the SMPS overflow-accumulator idiom), with a per-frame ramp, a `MEV_TEMPO` ($F3) sequencer opcode, and a `SND_REQ_TEMPO` mailbox slot + 68k API.
3. **Hardware LFO control** — a `MEV_LFO` ($F4) opcode that writes YM2612 `$22` (enable | 3-bit rate), wrapped in the DAC `$2A` address-park save/restore, plus the doc fix (`$08` rate = **3.82 Hz**, not 3.98).

**Out of scope (other phases — do NOT build):** portamento, fine-detune renderer, FM TL volume-envelope, SSG-EG, `MEV_REGWRITE`, the macro/automation spine (slot[1] `MacroTick`), any DAC mixer/pan/fade work, per-channel `$B4` AMS/FMS automation opcode (MEV_PAN already writes `$B4`), vibrato (Phase 1).

### ⚠ Load-bearing findings from reading the real code (verify in Task 0, do NOT trust the spec paraphrase)

- **F1 — The hardware LFO is ALREADY enabled at init.** `engine/z80_sound_driver.asm:166-168` writes `$22 = $08` (LFO ON, rate 0) once at boot. The spec §6 claims `$22 never enables the LFO` — **that is wrong against this codebase.** Consequence: the per-channel `$B4` AMS/FMS depth bits written by `MEV_PAN`/`Fm_SetPan` should **already** modulate today for any song that sets nonzero AMS/FMS. The real value of `MEV_LFO` is therefore: (a) **rate** control (init hard-codes rate 0 = 3.82 Hz), (b) explicit **enable/disable** under song control. Task 0 must empirically confirm the live `$22` value and whether existing MEV_PAN AMS/FMS already audibly modulates. **OPEN:** if it already modulates, frame `MEV_LFO`'s verification around the *rate change* + `$2A`-park safety, not "un-deading inert bits."
- **F2 — The duck folds exactly where the spec says.** `Fm_SetVolume` folds the SFX duck into the carrier-TL delta `Fm_ScratchLog` (sound_fm.asm:366-381, music-only gated by `Snd_ChanClass`); `Psg_SetVolume` folds it into the attenuation `c` (sound_psg.asm:328-355). Master fade folds into the **same** music-only gate. Confirmed.
- **F3 — `Sfx_DuckRamp` (sound_sfx.asm:296-357) is the proven template** for "ramp a global scalar each frame + re-assert held music notes." The fade SM mirrors its ramp/clamp; the re-assert is done the spec's way (a global dirty flag read by `ModUpdate`).
- **F4 — Tempo accumulator** is `sc_tempo_accum -= 16; if borrow: accum += sc_tempo_base; run an event-tick` (sound_sequencer.asm:71-79). The song's *musical* tempo lives in `sc_tempo_base` (per channel, from the header) and is **not** touched; the global scalar replaces the literal `16` decrement (larger = faster). No multiply.

---

## Architecture

**Master fade = ONE global scalar, folded at the two existing music volume writes.** `SND_MASTER_FADE` (1 byte, attenuation units: `$00` full … `$7F` silent) is summed with the SFX duck inside the existing `Snd_ChanClass` music-only gate and folded into `Fm_ScratchLog` (FM, clamp `$7F`) and into the PSG attenuation (`(duck+fade) >> 3`, clamp `$0F`). A per-frame state machine `Fade_Ramp` ramps `SND_MASTER_FADE` toward `SND_FADE_TARGET` by `SND_FADE_STEP` (gated by a delay counter); on a frame where it steps it sets `SND_FADE_DIRTY`. `ModUpdate` reads `SND_FADE_DIRTY` and re-asserts `sc_volume` on every keyed FM/PSG channel (held notes follow the fade); the flag is cleared once per frame after the channel loop. Note-on volume writes pick up the fade for free (they call `Fm_SetVolume`/`Psg_SetVolume`). DAC is intentionally not faded (out of scope). Fade is **music-only** (same gate as the duck); SFX stay full during a fade.

**Global tempo = a global decrement scalar on the per-channel accumulator.** `SND_TEMPO_CUR` (default `16`) replaces the literal `16` in `Sequencer_Frame`'s per-channel `sub`. `Tempo_Ramp` (per frame) ramps `SND_TEMPO_CUR` toward `SND_TEMPO_TARGET` by 1. `MEV_TEMPO` snaps base/cur/target (instant authored tempo); the mailbox sets a ramped target (`$FF` = restore the authored base). A `0` decrement would freeze the song, so every setter clamps `0 → 16`.

**Hardware LFO = `MEV_LFO` writes `$22` with the `$2A` park discipline.** The handler selects `$22` on `$4000`, writes `enable|rate` on `$4001` (via the shared `Fm_YmWrite`, part I), then calls `Fm_ReparkDac` to re-select `$2A` on the addr port (the DAC streamer parks `$2A`; a stray `$22` select otherwise misroutes the next DAC byte). The `$B4` depth bits are already written by `MEV_PAN`; `MEV_LFO` only controls the global oscillator.

**RAM:** the new globals (7 bytes) live in the free gap between the (relocated, Phase-1) trace ring and the song buffer. With `SeqChannel_len=58`: `SND_SEQ_TRACE=$1A97..$1AB7`, so `SND_GLOBAL_EXPR=$1AB7..$1ABE`, leaving 66 bytes of headroom below `SND_SONG_BUF=$1B00`. Derived from `SND_SEQ_TRACE + SND_SEQ_TRACE_LEN` so it auto-tracks any future ring/struct growth; a build assert keeps it below the song buffer. All bytes are `ds.b` (no even-align need).

**Independence:** Group C (LFO) is fully independent. Group B (tempo) and Groups A2–A6 (fade) build on the shared RAM/constants foundation laid in Task A1. Each task leaves the build green and the golden boot song (Moving Trucks) byte/spectrum-faithful.

## Tech Stack

- **Z80 assembler:** AS (Macroassembler), assembled inline in the 68k ROM under `phase 0`. Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → `s4.bin` (+ symbols via `convsym`; `tools/s4budget.py --summary` runs at the end). **A plain `./build.sh` EXCLUDES all sound.**
- **Z80 code ceiling:** `Z80_SOUND_SIZE <= SND_STATE_BASE ($16F0)`, asserted at `engine/z80_sound_driver.asm:1469-1474`. Phase 2 adds ~250–350 bytes of Z80 code. The F5 co-location work left ~1 KB headroom, so this should fit — **but check the assert + `s4budget` after every Z80-code task and flag any overflow rather than working around it.**
- **Conventions** (`CODING_CONVENTIONS.md`): sized branches (`jr`/`jp` chosen by range), `struct/endstruct`, `function` for compile-time math, **no `mulu`/`divu`**, `phase/dephase`. AS does NOT auto-align `ds.w` — all Phase-2 globals are `ds.b`. Any RAM-layout change requires a runtime boot verification, not just build asserts.
- **Verification = rendered AUDIO / observable behavior, never register proxies alone.** `exodus` MCP drives our ROM; `oracle` MCP for the S3K reference. **VGM captures ≤450 frames** (longer freezes the emulator). Tools: `tools/vgm_onsets.py` (tempo cadence), VGM→WAV energy envelope (fade), `tools/vgm_intranote.py` / audio spectrum (LFO tremolo). Runtime-boot after the RAM change (Task A1).
- **Daemon-watched, do NOT touch:** `data/editor/**`, `tools/ojz_strip_gen.py`. (`data/sound/*` and the sound transcoder are fair game if a tiny test phrase is needed for the MEV opcodes.)

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `sound_constants.asm` | Phase-2 RAM globals (`SND_GLOBAL_EXPR` block); fade/tempo command + tuning constants; `SND_REQ_FADE`/`SND_REQ_TEMPO` slots; `MEV_TEMPO`/`MEV_LFO` opcode constants + collision asserts; LFO rate-table doc | A1, B2, C1 |
| `engine/sound_fm.asm` | `Fm_SetVolume` master-fade + duck fold | A2 |
| `engine/sound_psg.asm` | `Psg_SetVolume` master-fade + duck fold | A2 |
| `engine/sound_sequencer.asm` | `Fade_Ramp` + `Tempo_Ramp`; `Sequencer_Frame` wiring (ramp calls, dirty-clear, decrement scalar); `ModUpdate` fade-dirty re-assert; `Seq_Op_Tempo`/`Seq_Op_Lfo` handlers + dispatch table | A3, B1, B2, C1 |
| `engine/z80_sound_driver.asm` | one-time init + song-load reset of globals; `SndDrv_PollMailbox` fade/tempo handlers (`Snd_FadeCommand`/`Snd_TempoCommand`); init slot clears; LFO init doc fix | A1, A4, B3, C1 |
| `engine/sound_api.asm` | 68k `Sound_FadeOut`/`Sound_FadeIn`/`Sound_SetTempo` | A5, B3 |

No new files.

---

## Task 0 — Read-only locate + record exact anchors (no edits, no commit)

Build the anchor inventory so every later task lands cleanly, and empirically resolve finding **F1** (LFO already enabled).

### Steps

1. **Confirm the two fold-points.**
   ```
   grep -n "no_duck\|SND_SFX_DUCK_LEVEL\|Fm_ScratchLog\|Snd_ChanClass" engine/sound_fm.asm
   grep -n "no_duck\|SND_SFX_DUCK_LEVEL\|env_done\|Psg_VolToAtten" engine/sound_psg.asm
   ```
   Record: `Fm_SetVolume` duck fold = **sound_fm.asm:366-381** (`call Snd_ChanClass` / `.no_duck:`). `Psg_SetVolume` duck fold = **sound_psg.asm:335-355** (`push hl`/`call Snd_ChanClass`/`pop hl` … `.no_duck:`). The `.no_duck` label has no external refs (grep to confirm) — safe to rename to `.no_global_atten`.
2. **Confirm the tempo accumulator.** `grep -n "sub.*16\|sc_tempo_accum\|Sequencer_Frame" engine/sound_sequencer.asm` → the literal `sub 16` is **sound_sequencer.asm:73**, inside the `.chan_loop` body (lines 62-85), between `push bc` (65) and `pop bc` (81). `c` is free there (restored by `pop bc`).
3. **Confirm `ModUpdate` top.** sound_sequencer.asm:134-139 — insert the fade re-assert **after** the `bit SCF_SFX_OVERRIDE_B,(ix+sc_flags) / ret nz` at lines 138-139, **before** line 147 (`bit SCF_IS_FM_B`).
4. **Confirm the mailbox dispatch.** sound_sequencer/`z80_sound_driver.asm`: `SndDrv_PollMailbox` = **z80_sound_driver.asm:528-588**; insert the fade/tempo checks after the `.no_sfx:` label (line 574), before the SAMPLE block (575). Init slot clears = lines 184-187; one-time `a=0` global init region = lines 182-202; song-load arm = `.arm:` lines 1255-1279 (`SND_SEQ_ACTIVE` set at 1271-1272).
5. **Confirm the LFO init + park helpers.** z80_sound_driver.asm:158-168 (`$22 = $08`, comment says `~3.98 Hz` at lines 158 & 167). `Fm_YmWrite` = sound_fm.asm:57-70 (`a=reg, c=data, b=part`; clobbers af, preserves bc/de/hl/ix). `Fm_ReparkDac` = sound_fm.asm:79-82 (re-selects `$2A`; preserves bc/de/hl/ix). `SND_REG_LFO=$22` already exists (sound_constants.asm:66).
6. **Confirm free opcode slots + dispatch.** `SeqOpcodeTable` = sound_sequencer.asm:1190-1221. `$F3`/`$F4` are `Seq_BadOpcode` (lines 1210-1211) → free. `Seq_ContinueFetch:` = sound_sequencer.asm:1183. `Seq_Op_NoteFill` (663-670) / `Seq_Op_PsgNoise` (691-698) are the zero-tick handler templates.
7. **Confirm free RAM.** Re-derive with `SeqChannel_len=58`: `SND_SEQ_END=$1A86`, scratch+param chain → `SND_MUSIC_PARAM=$1A91`, `SND_SEQ_TRACE=$1A97`, ring end `$1AB7`, `SND_SONG_BUF=$1B00` → **66 free bytes** at `$1AB7..$1AFF`. Free mailbox slots: `SND_CTRL_DMA_ACTIVE=$1F04`, `SND_STAT_BASE=$1F10` → `$1F05..$1F0F` free.
8. **Resolve F1 empirically (LFO).** Build the current ROM (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`), boot in **exodus**, play a song, and `emulator_read_memory` / the YM register stream for reg `$22`. **Record whether `$22 == $08` at runtime** (expected: yes — LFO already on). If a song with MEV_PAN AMS/FMS bits exists, note whether tremolo/vibrato is already audible. This determines the framing of Task C2.

**Record all of the above in the PR description. No commit.**

---

# Group A — Master Fade

## Task A1 — Phase-2 RAM globals + command/tuning constants + init/load reset (no behavior change)

Lays the shared foundation: the global RAM block (fade **and** tempo bytes), the command/tuning constants, the one-time init, and the per-song reset. All values are inert (fade=0, tempo=16-but-unused) until later tasks read them.

### Files
- `sound_constants.asm` — request slots (~line 23), command/tuning constants (new block near the SFX duck constants ~line 613), RAM globals + assert (~lines 1071 & 1100).
- `engine/z80_sound_driver.asm` — init slot clears (184-187), one-time init (after 202), song-load reset (after 1272).

### Steps

1. **`sound_constants.asm` — request slots.** After `SND_REQ_SFX = SND_REQ_BASE+$03` (line 23) add:
   ```
   SND_REQ_FADE            = SND_REQ_BASE+$05       ; master-fade cmd (0 idle / 1 out / 2 in)
   SND_REQ_TEMPO           = SND_REQ_BASE+$06       ; tempo cmd (0 idle / 1..$FE target / $FF restore)
       if (SND_REQ_TEMPO >= SND_STAT_BASE)
         error "SND_REQ_FADE/TEMPO (\{SND_REQ_TEMPO}) collide with the status block at \{SND_STAT_BASE}"
       endif
   ```
   (`SND_CTRL_DMA_ACTIVE=$1F04` and `SND_STAT_BASE=$1F10` are defined later but the assert resolves at end-of-pass; keep `$1F05/$1F06` clear of both — confirmed.)

2. **`sound_constants.asm` — command/tuning constants.** Add a new block (e.g. after the `SFX_DUCK_*` constants, ~line 614):
   ```
   ; --- Phase 2: master fade + global tempo (music expression engine) ---
   SND_FADE_CMD_OUT       = 1       ; SND_REQ_FADE: ramp the scalar UP to silence
   SND_FADE_CMD_IN        = 2       ; SND_REQ_FADE: snap silent, ramp DOWN to full
   SND_FADE_SILENCE       = SND_FM_TL_MAX   ; $7F = full master-fade attenuation
   SND_FADE_STEP          = 2       ; fade change per applied step (TL units; full fade ~1.06s)
   SND_FADE_DELAY         = 1       ; frames between fade steps (1 = every frame)
   SND_TEMPO_DECR_DEFAULT = 16      ; normal-speed per-frame accumulator decrement (100%)
   SND_TEMPO_RESTORE      = $FF     ; SND_REQ_TEMPO sentinel: ramp back to the authored base
   ```

3. **`sound_constants.asm` — RAM globals.** Immediately after `SND_SEQ_TRACE = SND_MUSIC_PARAM + SND_MUSIC_PARAM_LEN` (line 1071) add:
   ```
   ; --- Phase 2 global expression state (master fade + global tempo). Free RAM
   ; between the trace ring and the song buffer ($1B00). Derived from the ring end so
   ; it auto-tracks ring/struct growth; the assert below keeps it under the song
   ; buffer. All ds.b -> no even-align need. GLOBAL (not per-channel): one scalar each.
   SND_GLOBAL_EXPR     = SND_SEQ_TRACE + SND_SEQ_TRACE_LEN
   SND_MASTER_FADE     = SND_GLOBAL_EXPR+$00   ; current fade atten (0 full .. $7F silent)
   SND_FADE_TARGET     = SND_GLOBAL_EXPR+$01   ; fade ramp target
   SND_FADE_DELAY_CTR  = SND_GLOBAL_EXPR+$02   ; frames-until-next-step countdown
   SND_FADE_DIRTY      = SND_GLOBAL_EXPR+$03   ; 1 = fade stepped this frame (ModUpdate re-asserts)
   SND_TEMPO_CUR       = SND_GLOBAL_EXPR+$04   ; current per-frame accumulator decrement (16=100%)
   SND_TEMPO_TARGET    = SND_GLOBAL_EXPR+$05   ; tempo ramp target
   SND_TEMPO_BASE      = SND_GLOBAL_EXPR+$06   ; authored base (MEV_TEMPO; restore reference)
   SND_GLOBAL_EXPR_LEN = 7
   ```
   In the assert block after `SND_SONG_BUF` is defined (after line 1098, alongside the existing `> SND_SONG_BUF` asserts), **change** the trace-ring assert and **add** the globals assert:
   ```
       if (SND_SEQ_TRACE + SND_SEQ_TRACE_LEN) > SND_GLOBAL_EXPR
         fatal "trace ring (\{SND_SEQ_TRACE}+\{SND_SEQ_TRACE_LEN}) runs into the Phase-2 globals (\{SND_GLOBAL_EXPR})"
       endif
       if (SND_GLOBAL_EXPR + SND_GLOBAL_EXPR_LEN) > SND_SONG_BUF
         fatal "Phase-2 globals (\{SND_GLOBAL_EXPR}+\{SND_GLOBAL_EXPR_LEN}) run into the song buffer at \{SND_SONG_BUF}"
       endif
   ```
   (Leave the existing `song buffer overruns the mailbox` assert.)

4. **`engine/z80_sound_driver.asm` — init slot clears.** After `ld (SND_REQ_SFX), a` (line 187) add (a is still 0):
   ```
           ld      (SND_REQ_FADE), a
           ld      (SND_REQ_TEMPO), a
   ```

5. **`engine/z80_sound_driver.asm` — one-time global init.** After `ld (Snd_SpindashRev), a` (line 202, a still 0) add:
   ```
           ; Phase 2: fade = full volume (0), idle; tempo = normal-speed default (16).
           ld      (SND_MASTER_FADE), a
           ld      (SND_FADE_TARGET), a
           ld      (SND_FADE_DIRTY), a
           ld      (SND_FADE_DELAY_CTR), a
           ld      a, SND_TEMPO_DECR_DEFAULT
           ld      (SND_TEMPO_CUR), a
           ld      (SND_TEMPO_TARGET), a
           ld      (SND_TEMPO_BASE), a
   ```
   (a is reloaded by the ring-fill at line 208, so no need to restore 0.)

6. **`engine/z80_sound_driver.asm` — per-song reset.** In `.arm`, immediately after `ld (SND_SEQ_ACTIVE), a` (line 1272; a=1 here) add:
   ```
           ; Phase 2: reset global expression state for the new song. Fade -> full
           ; volume (else a song after a fade-out would play SILENT). Tempo -> normal
           ; (the song's MEV_TEMPO, if any, overrides on its first tick).
           xor     a
           ld      (SND_MASTER_FADE), a
           ld      (SND_FADE_TARGET), a
           ld      (SND_FADE_DIRTY), a
           ld      (SND_FADE_DELAY_CTR), a
           ld      a, SND_TEMPO_DECR_DEFAULT
           ld      (SND_TEMPO_CUR), a
           ld      (SND_TEMPO_TARGET), a
           ld      (SND_TEMPO_BASE), a
   ```
   (The following `xor a` at the original line 1274 still sets up the `SND_REQ_MUSIC` clear.)

7. **Build:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → green; `s4budget` Z80 size `<= $16F0`. Confirm `SND_GLOBAL_EXPR=$1AB7`, `SND_GLOBAL_EXPR_LEN=7`, all RAM asserts pass.

8. **Boot verify (mandatory — RAM change)** via **exodus**: reload symbols + `s4.bin`, reset, run ~600 frames, play `SONG_MOVINGTRUCKS`. Confirm it plays unchanged (golden). `emulator_lookup_symbol SND_MASTER_FADE` → `$1AB7`; `emulator_read_memory`/`emulator_z80_read` the 7 bytes: fade bytes `00`, `SND_TEMPO_CUR/TARGET/BASE` = `$10`. Confirm `$1B00+` (song buffer) intact.

9. **Commit:** `sound: Phase 2 RAM globals (master fade + global tempo) + init/load reset`.

---

## Task A2 — Fold the master-fade scalar into the two music volume writes (no behavior change; fade is 0)

### Files
- `engine/sound_fm.asm` — `Fm_SetVolume` (366-381).
- `engine/sound_psg.asm` — `Psg_SetVolume` (335-355).

### Steps

1. **`engine/sound_fm.asm`** — replace the duck-fold block (lines 366-381, `call Snd_ChanClass` … `.no_duck:`) with the combined fade+duck fold:
   ```
           ; --- master fade + SFX duck fold (music-only) ----------------------------
           ; Sum the global master-fade scalar and the SFX duck level into the carrier-
           ; TL delta so EVERY music volume write (note events AND the held-note re-
           ; assert) picks both up. MUSIC ONLY (ix < SND_SFX_BASE): an SfxChannel must
           ; not fade/duck. Sum (each 0..$7F; max ~$97, no 8-bit carry) clamp $7F, then
           ; fold into Fm_ScratchLog (clamp $7F). Fade 0 + duck 0 -> byte-identical no-op.
           call    Snd_ChanClass            ; CARRY set => MUSIC channel (hl = ix)
           jr      nc, .no_global_atten     ; SFX channel -> never fade/duck
           ld      a, (SND_SFX_DUCK_LEVEL)
           ld      hl, SND_MASTER_FADE
           add     a, (hl)                  ; a = duck + master fade
           cp      SND_FM_TL_MAX+1
           jr      c, .ga_have
           ld      a, SND_FM_TL_MAX         ; clamp combined to $7F
   .ga_have:
           or      a
           jr      z, .no_global_atten      ; nothing to add (no fade, no duck)
           ld      hl, Fm_ScratchLog
           add     a, (hl)                  ; log delta + combined global atten
           jr      nc, .ga_ok
           ld      a, SND_FM_TL_MAX         ; carry -> clamp to $7F (silent)
   .ga_ok:
           cp      SND_FM_TL_MAX+1
           jr      c, .ga_store
           ld      a, SND_FM_TL_MAX         ; clamp summed delta to $7F
   .ga_store:
           ld      (hl), a                  ; faded+ducked carrier-TL delta
   .no_global_atten:
   ```

2. **`engine/sound_psg.asm`** — replace the duck-fold block (lines 335-355, `push hl` … `.no_duck:`) with:
   ```
           ; --- master fade + SFX duck fold (music-only) ----------------------------
           ; (duck + fade) in TL units, mapped to 4-bit PSG atten by >>3, added to the
           ; attenuation, clamped to $0F (silent). MUSIC ONLY. hl preserved (contract).
           push    hl                       ; (Snd_ChanClass clobbers hl)
           call    Snd_ChanClass            ; CARRY set => MUSIC channel
           pop     hl                       ; restore caller's hl (contract)
           jr      nc, .no_global_atten     ; SFX channel -> never fade/duck
           ld      a, (SND_SFX_DUCK_LEVEL)
           ld      b, a
           ld      a, (SND_MASTER_FADE)
           add     a, b                     ; a = (duck + fade) in TL units (max ~$97)
           or      a
           jr      z, .no_global_atten      ; nothing to add
           srl     a
           srl     a
           srl     a                        ; TL units -> 4-bit atten units (>>3)
           add     a, c                     ; atten + global atten
           cp      SND_PSG_ATTEN_SILENT+1
           jr      c, .ga_ok
           ld      a, SND_PSG_ATTEN_SILENT  ; clamp to $0F (silent)
   .ga_ok:
           ld      c, a
   .no_global_atten:
   ```
   (`b` is clobber-legal — `Psg_SetVolume` clobbers af,bc.)

3. **Build:** green; Z80 size `<= $16F0`.

4. **Boot verify** (exodus): play `SONG_MOVINGTRUCKS` → byte/spectrum-unchanged (fade=0, duck=0 fast-path). Confirm an SFX still ducks the music (the duck path is preserved). Optionally `emulator_write_memory SND_MASTER_FADE = $40` for one channel test and confirm the music quiets, then set back to 0.

5. **Commit:** `sound: fold master-fade scalar into Fm_SetVolume/Psg_SetVolume (with the duck)`.

---

## Task A3 — Fade state machine + Sequencer_Frame wiring + ModUpdate fade-dirty re-assert (no behavior change; no trigger yet)

### Files
- `engine/sound_sequencer.asm` — new `Fade_Ramp` (place after `Sequencer_Frame`, before `ModUpdate`, ~line 88); `Sequencer_Frame` channel-loop preamble + dirty-clear (53-87); `ModUpdate` re-assert (after 139).

### Steps

1. **Add `Fade_Ramp`** after `Sequencer_Frame` (insert before the `ModUpdate` comment block at line 89):
   ```
   ; ----------------------------------------------------------------------
   ; Fade_Ramp — ramp SND_MASTER_FADE toward SND_FADE_TARGET by SND_FADE_STEP,
   ; gated by SND_FADE_DELAY_CTR. On a frame where the level CHANGES, set
   ; SND_FADE_DIRTY so ModUpdate re-asserts held-note volumes (the scalar is folded
   ; in Fm_SetVolume/Psg_SetVolume). Steady state (cur==target) = no step, no dirty.
   ; Called once/frame from Sequencer_Frame before the channel loop. Clobbers af,b.
   ; ----------------------------------------------------------------------
   Fade_Ramp:
           ld      a, (SND_FADE_TARGET)
           ld      b, a                     ; b = target (preserved below)
           ld      a, (SND_MASTER_FADE)
           cp      b
           ret     z                        ; at target -> steady, no work
           ; fade active: gate the step on the delay counter
           ld      a, (SND_FADE_DELAY_CTR)
           dec     a
           ld      (SND_FADE_DELAY_CTR), a
           ret     nz                       ; not this frame
           ld      a, SND_FADE_DELAY
           ld      (SND_FADE_DELAY_CTR), a  ; reload the step delay
           ld      a, (SND_MASTER_FADE)
           cp      b                        ; cur vs target (b)
           jr      nc, .down                ; cur >= target -> ramp down
           add     a, SND_FADE_STEP         ; ramp up toward target
           cp      b
           jr      c, .store
           ld      a, b                     ; clamp to target (no overshoot)
           jr      .store
   .down:
           sub     SND_FADE_STEP
           jr      c, .clamp_t              ; underflow past 0 -> clamp to target
           cp      b
           jr      nc, .store
   .clamp_t:
           ld      a, b
   .store:
           ld      (SND_MASTER_FADE), a
           ld      a, 1
           ld      (SND_FADE_DIRTY), a      ; level changed -> ModUpdate re-asserts
           ret
   ```

2. **`Sequencer_Frame` — call the ramp + clear the dirty flag.** Replace lines 57-87 (from `ld a,(SND_SEQ_CHCOUNT)` through `.run_sfx:`) so the ramp runs before the loop and the flag is cleared only on the active fall-through path:
   ```
           ld      a, (SND_SEQ_CHCOUNT)
           or      a
           jr      z, .run_sfx              ; no channels -> still run SFX
           call    Fade_Ramp               ; ramp master fade; set SND_FADE_DIRTY on a step
           ld      a, (SND_SEQ_CHCOUNT)     ; (Fade_Ramp clobbered a)
           ld      b, a                     ; b = channel count (djnz bound)
           ld      ix, SND_SEQ_CHANNELS     ; ix = first SeqChannel
   .chan_loop:
           bit     SCF_ACTIVE_B, (ix+sc_flags)
           jr      z, .next_chan
           push    bc
           call    ModUpdate
           ld      a, (ix+sc_tempo_accum)
           sub     16                       ; (Group B replaces 16 with SND_TEMPO_CUR)
           ld      (ix+sc_tempo_accum), a
           jr      nc, .chan_done
           add     a, (ix+sc_tempo_base)
           ld      (ix+sc_tempo_accum), a
           call    Sequencer_Channel
   .chan_done:
           pop     bc
   .next_chan:
           ld      de, SeqChannel_len
           add     ix, de
           djnz    .chan_loop
           xor     a
           ld      (SND_FADE_DIRTY), a      ; consume the re-assert flag (loop pass done)
   .run_sfx:
           jp      Sfx_Frame
   ```
   (Net change vs current: insert the `call Fade_Ramp` + `ld a,(SND_SEQ_CHCOUNT)` reload before `ld b,a`, and the `xor a / ld (SND_FADE_DIRTY),a` before `.run_sfx:`. The `sub 16` stays for now — Group B changes it.)

3. **`ModUpdate` — fade-dirty re-assert.** Insert after the SFX-override `ret nz` (line 139), before line 140:
   ```
           ; --- master-fade re-assert: while a fade stepped this frame, re-emit this
           ; channel's volume so HELD notes track the fade (the scalar is folded in
           ; Fm_SetVolume/Psg_SetVolume). Gated on the global dirty flag (set by
           ; Fade_Ramp, cleared after the channel loop). Only KEYED FM/PSG; DAC excluded.
           ld      a, (SND_FADE_DIRTY)
           or      a
           jr      z, .no_fade_reassert
           bit     SCF_KEYED_B, (ix+sc_flags)
           jr      z, .no_fade_reassert     ; silent -> next note keys at the faded level
           bit     SCF_IS_FM_B, (ix+sc_flags)
           jr      z, .fr_psg
           ld      a, (ix+sc_volume)
           call    Fm_SetVolume             ; re-assert carrier TLs (preserves ix)
           jr      .no_fade_reassert
   .fr_psg:
           bit     SCF_IS_PSG_B, (ix+sc_flags)
           jr      z, .no_fade_reassert     ; DAC/other -> not faded (out of scope)
           ld      a, (ix+sc_volume)
           call    Psg_SetVolume            ; re-assert attenuation (preserves ix)
   .no_fade_reassert:
   ```
   (Registers: ix preserved; the loop counter is on the stack via the caller's `push bc`. Falls through to the existing `bit SCF_IS_FM_B` at line 147.)

4. **Build:** green; Z80 size `<= $16F0` (flag if over).

5. **Boot verify** (exodus): play `SONG_MOVINGTRUCKS` → unchanged (target stays 0 → `Fade_Ramp` returns immediately, `SND_FADE_DIRTY` never set, re-assert path is one test/channel). **Manual SM test:** `emulator_write_memory SND_FADE_TARGET=$7F` while a song plays → confirm `SND_MASTER_FADE` ramps `0→$7F` over ~64 frames and the music fades to silence; set `SND_FADE_TARGET=0` → ramps back and music returns. (This validates A2+A3 before the mailbox exists.)

6. **Commit:** `sound: fade state machine + ModUpdate fade-dirty re-assert (no trigger yet)`.

---

## Task A4 — Z80 mailbox handler for `SND_REQ_FADE`

### Files
- `engine/z80_sound_driver.asm` — `SndDrv_PollMailbox` (after `.no_sfx:` line 574); new `Snd_FadeCommand`.

### Steps

1. **In `SndDrv_PollMailbox`,** after `.no_sfx:` (line 574), before the SAMPLE block:
   ```
           ; --- fade request? (1 = out, 2 = in) ---
           ld      a, (SND_REQ_FADE)
           or      a
           jr      z, .no_fade
           call    Snd_FadeCommand          ; set target (+ seed delay ctr)
           xor     a
           ld      (SND_REQ_FADE), a        ; clear slot (consumed)
           ld      a, (SND_STAT_ACK_COUNT)
           inc     a
           ld      (SND_STAT_ACK_COUNT), a
   .no_fade:
   ```

2. **Add `Snd_FadeCommand`** (place after `SndDrv_PollMailbox`, before `Snd_DacLookup` ~line 590):
   ```
   ; ======================================================================
   ; Snd_FadeCommand — a = SND_FADE_CMD_OUT (1) or SND_FADE_CMD_IN (2).
   ; OUT: ramp the scalar UP to silence. IN: snap to silence, ramp DOWN to full.
   ; Seeds the step-delay counter so Fade_Ramp steps immediately. Clobbers af.
   ; ======================================================================
   Snd_FadeCommand:
           cp      SND_FADE_CMD_IN
           jr      z, .fade_in
           ld      a, SND_FADE_SILENCE      ; fade out: target = silent
           ld      (SND_FADE_TARGET), a
           jr      .seed
   .fade_in:
           ld      a, SND_FADE_SILENCE
           ld      (SND_MASTER_FADE), a     ; start silent
           xor     a
           ld      (SND_FADE_TARGET), a     ; target = full volume
   .seed:
           ld      a, SND_FADE_DELAY
           ld      (SND_FADE_DELAY_CTR), a
           ret
   ```

3. **Build:** green; size check.

4. **Boot verify** (exodus): play a song, `emulator_write_memory SND_REQ_FADE=1` (or post via the next task's API), run ~70 frames → confirm `SND_REQ_FADE` cleared to 0, `SND_STAT_ACK_COUNT` bumped, `SND_MASTER_FADE` ramped to `$7F`, audio silent. Write `SND_REQ_FADE=2` → audio ramps back up.

5. **Commit:** `sound: SND_REQ_FADE mailbox handler (Snd_FadeCommand)`.

---

## Task A5 — 68k API: `Sound_FadeOut` / `Sound_FadeIn`

### Files
- `engine/sound_api.asm` — after `Sound_StopMusic` (line 219).

### Steps

1. Append:
   ```
   ; ----------------------------------------------------------------------
   ; Sound_FadeOut — ramp the music master volume down to silence (~1s). The song
   ; keeps playing; the game typically follows with Sound_StopMusic when silent.
   ; Clobbers: d0; SR restored.
   ; ----------------------------------------------------------------------
   Sound_FadeOut:
           move.b  #SND_FADE_CMD_OUT, d0
           lea     (SND_Z80_BASE+SND_REQ_FADE).l, a0
           bra.w   Sound_PostByte

   ; ----------------------------------------------------------------------
   ; Sound_FadeIn — snap the master volume to silence and ramp it up to full (~1s).
   ; Use right after Sound_PlayMusic to fade a song in. Clobbers: d0; SR restored.
   ; ----------------------------------------------------------------------
   Sound_FadeIn:
           move.b  #SND_FADE_CMD_IN, d0
           lea     (SND_Z80_BASE+SND_REQ_FADE).l, a0
           bra.w   Sound_PostByte
   ```
   **Crossfade / fade-to-prev:** this is a game-level composition that "rides on the scalar": `Sound_FadeOut` → (poll until silent / fixed delay) → `Sound_PlayMusic(new)` → `Sound_FadeIn`. **OPEN:** a dedicated engine "restore the *previous* song" (spec §7 "restore saved song state") needs the driver to save/restore the prior song id + sequencer state — that is heavier than the global-scalar scope of this slice and is **deferred** (note it in the PR). The FadeOut/FadeIn primitives are sufficient for crossfades the game orchestrates.

2. **Build:** green (68k side; sound enabled).

3. **Verify** in Task A6 (end-to-end audio).

4. **Commit:** `sound(68k): Sound_FadeOut / Sound_FadeIn API`.

---

## Task A6 — Verify master fade by rendered audio

### Steps

1. Build DEBUG ROM; reload symbols in **exodus**.
2. Boot, play `SONG_MOVINGTRUCKS`, let it reach a sustained passage. `emulator_vgm_start`; trigger a fade-out (post `SND_REQ_FADE=1` via `emulator_write_memory`, or call `Sound_FadeOut`); `emulator_run_frames` in **≤450-frame** chunks across the whole fade; `emulator_vgm_stop`.
3. **Audio check (the rule):** render the VGM → WAV; compute the RMS energy envelope in ~10-frame windows. Confirm a **smooth monotonic decay to ~0** over the fade (no abrupt steps, no clicks). Cross-check `SND_MASTER_FADE` sampled per frame ramps `0→$7F`; the FM `$40`-group TLs rise toward `$7F` and PSG attenuation rises toward `$0F` in the YM register stream.
4. **Fade-in:** post `SND_REQ_FADE=2`; capture; confirm the energy envelope rises **smoothly from ~0 back to full**.
5. **Regression:** with no fade active, `SONG_MOVINGTRUCKS` renders byte/spectrum-faithful vs the MT baseline; DEBUG boot self-test green. Confirm an SFX still ducks (duck path intact).
6. **Commit** (notes only): `sound: verify master fade (audio energy envelope ramps to silence + back)`. Record envelope numbers in the PR.

---

# Group B — Global Tempo (+ ramp)

> Depends on Task A1 (the `SND_TEMPO_*` globals + constants). The fade tasks (A2–A6) are not required for Group B.

## Task B1 — Apply the global decrement scalar + per-frame tempo ramp

### Files
- `engine/sound_sequencer.asm` — `Sequencer_Frame` decrement (line 73, already in the A3-edited block); new `Tempo_Ramp` (near `Fade_Ramp`).

### Steps

1. **Replace the literal decrement.** In `Sequencer_Frame`'s `.chan_loop` body, change:
   ```
           ld      a, (ix+sc_tempo_accum)
           sub     16
   ```
   to (read the global scalar; `c` is free between the loop's `push bc`/`pop bc`):
   ```
           ld      a, (SND_TEMPO_CUR)       ; global tempo decrement (16 = 100% speed)
           ld      c, a
           ld      a, (ix+sc_tempo_accum)
           sub     c                        ; accum -= global decrement (no multiply)
   ```
   (Rest of the borrow/reload/`Sequencer_Channel` logic unchanged; `pop bc` restores `c`.)

2. **Add `Tempo_Ramp`** next to `Fade_Ramp`:
   ```
   ; ----------------------------------------------------------------------
   ; Tempo_Ramp — step SND_TEMPO_CUR one unit toward SND_TEMPO_TARGET each frame
   ; (small range -> ~0.1-0.3s glide). No multiply. Clobbers af,b.
   ; ----------------------------------------------------------------------
   Tempo_Ramp:
           ld      a, (SND_TEMPO_TARGET)
           ld      b, a
           ld      a, (SND_TEMPO_CUR)
           cp      b
           ret     z                        ; at target -> nothing
           jr      c, .up                   ; cur < target -> speed up
           dec     a                        ; cur > target -> slow down
           ld      (SND_TEMPO_CUR), a
           ret
   .up:
           inc     a
           ld      (SND_TEMPO_CUR), a
           ret
   ```

3. **Call `Tempo_Ramp`** in `Sequencer_Frame`, immediately before `call Fade_Ramp` (in the A3-edited preamble):
   ```
           call    Tempo_Ramp               ; ramp the global tempo decrement
           call    Fade_Ramp
           ld      a, (SND_SEQ_CHCOUNT)
           ld      b, a
   ```

4. **Build:** green; size check.

5. **Boot verify** (exodus): play `SONG_MOVINGTRUCKS` → cadence unchanged (`SND_TEMPO_CUR=16` from A1 init = identical to the old `sub 16`). Confirm with `tools/vgm_onsets.py` that inter-onset spacing matches the baseline. **Manual SM test:** `emulator_write_memory SND_TEMPO_TARGET=24` → confirm `SND_TEMPO_CUR` ramps to 24 and the song speeds up ~1.5×; set `=8` → slows; `=16` → normal.

6. **Commit:** `sound: global tempo decrement scalar + per-frame Tempo_Ramp`.

---

## Task B2 — `MEV_TEMPO` ($F3) sequencer opcode

### Files
- `sound_constants.asm` — opcode constant + asserts (near line 363).
- `engine/sound_sequencer.asm` — `Seq_Op_Tempo` (near `Seq_Op_PsgNoise`) + dispatch table (line 1210).

### Steps

1. **`sound_constants.asm` — constant + asserts.** Near `MEV_PSGNOISE` (line 366):
   ```
   MEV_TEMPO         = $F3   ; + dd : set the GLOBAL tempo speed scalar (accumulator decrement)
           if (MEV_TEMPO <= MEV_NOTE_MAX) || (MEV_TEMPO < MEV_VOL) || (MEV_TEMPO > MEV_END)
             error "MEV_TEMPO (\{MEV_TEMPO}) must be a command opcode inside $E0-$FF"
           endif
           if MEV_TEMPO <> $F3
             error "MEV_TEMPO (\{MEV_TEMPO}) must be $F3 (free slot)"
           endif
   ```

2. **`engine/sound_sequencer.asm` — handler.** After `Seq_Op_PsgNoise` (line 698):
   ```
   ; $F3 MEV_TEMPO + dd : set the GLOBAL tempo speed scalar (per-frame accumulator
   ; decrement; 16 = authored/normal, larger = faster, smaller = slower). Snaps
   ; base+cur+target (instant authored change). 0 clamped to default (0 would freeze
   ; every accumulator). GLOBAL (affects all channels) though it rides one stream.
   ; Zero-tick; no writer hook -> hl stays the live stream ptr.
   Seq_Op_Tempo:
           ld      a, (hl)
           inc     hl                       ; consume operand (decrement value)
           or      a
           jr      nz, .ok
           ld      a, SND_TEMPO_DECR_DEFAULT ; 0 -> normal (never freeze)
   .ok:
           ld      (SND_TEMPO_BASE), a      ; authored base (restore reference)
           ld      (SND_TEMPO_CUR), a       ; instant snap (no ramp for an authored set)
           ld      (SND_TEMPO_TARGET), a
           jp      Seq_ContinueFetch
   ```

3. **Dispatch table.** sound_sequencer.asm:1210 — change `dw Seq_BadOpcode ; $F3 reserved` to:
   ```
           dw      Seq_Op_Tempo             ; $F3 MEV_TEMPO
   ```

4. **Build:** green; size check; opcode asserts pass.

5. **Boot verify** (exodus): play `SONG_MOVINGTRUCKS` → unchanged (no `MEV_TEMPO` in it). To exercise the handler without new content, `emulator_z80_write` the bytes `$F3 $18` into a live channel's stream just past its read ptr (or add a 2-byte `MEV_TEMPO` to a throwaway test phrase in `data/sound/`), and confirm `SND_TEMPO_BASE/CUR/TARGET` become `$18` and the song speeds up.

6. **Commit:** `sound: MEV_TEMPO ($F3) sequencer opcode (global tempo scalar)`.

---

## Task B3 — `SND_REQ_TEMPO` mailbox handler + 68k `Sound_SetTempo`

### Files
- `engine/z80_sound_driver.asm` — `SndDrv_PollMailbox` (after `.no_fade:`) + `Snd_TempoCommand`.
- `engine/sound_api.asm` — `Sound_SetTempo`.

### Steps

1. **In `SndDrv_PollMailbox`,** after `.no_fade:` (Task A4):
   ```
           ; --- tempo request? (1..$FE target decrement; $FF restore authored base) ---
           ld      a, (SND_REQ_TEMPO)
           or      a
           jr      z, .no_tempo
           call    Snd_TempoCommand
           xor     a
           ld      (SND_REQ_TEMPO), a
           ld      a, (SND_STAT_ACK_COUNT)
           inc     a
           ld      (SND_STAT_ACK_COUNT), a
   .no_tempo:
   ```

2. **Add `Snd_TempoCommand`** (near `Snd_FadeCommand`):
   ```
   ; ======================================================================
   ; Snd_TempoCommand — a = $FF (restore authored base) or a target decrement
   ; (1..$FE). Sets SND_TEMPO_TARGET; Tempo_Ramp glides cur toward it. 0 -> default
   ; (never freeze). Clobbers af.
   ; ======================================================================
   Snd_TempoCommand:
           cp      SND_TEMPO_RESTORE        ; $FF -> restore authored base
           jr      nz, .have
           ld      a, (SND_TEMPO_BASE)
   .have:
           or      a
           jr      nz, .ok
           ld      a, SND_TEMPO_DECR_DEFAULT ; 0 -> normal (defensive)
   .ok:
           ld      (SND_TEMPO_TARGET), a
           ret
   ```

3. **`engine/sound_api.asm`** — append:
   ```
   ; ----------------------------------------------------------------------
   ; Sound_SetTempo — ramp the global music speed to a target. d0.b = target
   ; per-frame accumulator decrement (16 = normal; >16 faster, <16 slower), or
   ; SND_TEMPO_RESTORE ($FF) to return to the song's authored tempo. Clobbers d0.
   ; ----------------------------------------------------------------------
   Sound_SetTempo:
           lea     (SND_Z80_BASE+SND_REQ_TEMPO).l, a0
           bra.w   Sound_PostByte
   ```

4. **Build:** green; size check.

5. **Boot verify** (exodus): play a song; post `SND_REQ_TEMPO=24` → `SND_TEMPO_TARGET=24`, cur ramps up, song speeds up; `=8` → slows; `=$FF` → target returns to `SND_TEMPO_BASE`. Confirm slot cleared + ack bumped.

6. **Commit:** `sound: SND_REQ_TEMPO mailbox + 68k Sound_SetTempo`.

---

## Task B4 — Verify global tempo by observable cadence

### Steps

1. Build; reload symbols in **exodus**.
2. Play `SONG_MOVINGTRUCKS`; capture a baseline VGM (≤450 frames) and extract onset timestamps with `tools/vgm_onsets.py`.
3. `Sound_SetTempo(24)` (or `emulator_write_memory SND_REQ_TEMPO=24`); capture; confirm inter-onset intervals shrink to ~16/24 of baseline (≈1.5× faster) **and** the sequencer tick cadence speeds up (`SND_STAT_TICK` still ~59 Hz — the *frame* clock is unchanged; only event spacing changes). No desync/crash.
4. `Sound_SetTempo(8)` → intervals grow ~2×. `Sound_SetTempo($FF)` → returns to baseline cadence.
5. Confirm `SND_TEMPO_CUR` glides (not a step) between values across frames.
6. **Regression:** at default (16) the song is cadence-identical to baseline; MT golden green.
7. **Commit** (notes): `sound: verify global tempo (onset cadence speed-up/slow-down/restore)`.

---

# Group C — Hardware LFO Control

> Fully independent of Groups A/B.

## Task C1 — `MEV_LFO` ($F4) opcode (writes `$22` with `$2A`-park) + doc fix

### Files
- `sound_constants.asm` — opcode constant + asserts; LFO rate-table doc (near `SND_REG_LFO` line 66).
- `engine/sound_sequencer.asm` — `Seq_Op_Lfo` + dispatch table (line 1211).
- `engine/z80_sound_driver.asm` — LFO-init comment doc fix (lines 158, 167).

### Steps

1. **`sound_constants.asm` — opcode + asserts.** After `MEV_TEMPO`:
   ```
   MEV_LFO           = $F4   ; + value : write YM2612 $22 (bit3 enable | bits0-2 rate); $2A re-parked
           if (MEV_LFO <= MEV_NOTE_MAX) || (MEV_LFO < MEV_VOL) || (MEV_LFO > MEV_END)
             error "MEV_LFO (\{MEV_LFO}) must be a command opcode inside $E0-$FF"
           endif
           if (MEV_LFO <> $F4) || (MEV_LFO = MEV_TEMPO)
             error "MEV_LFO (\{MEV_LFO}) must be $F4 (free slot, distinct from MEV_TEMPO)"
           endif
   ```

2. **`sound_constants.asm` — rate-table doc fix.** Replace the `SND_REG_LFO` comment (line 66) with the corrected Hz table:
   ```
   SND_REG_LFO             = $22   ; YM reg: GLOBAL low-freq osc — bit3 = enable, bits0-2 = rate.
   ; LFO rate (bits0-2) Hz: 0=3.82, 1=5.33, 2=5.77, 3=6.11, 4=6.60, 5=9.23, 6=46.11, 7=69.22.
   ; (Init sets $22=$08 = enable|rate0 = 3.82 Hz. Prior docs said 3.98 Hz — WRONG.)
   ```

3. **`engine/sound_sequencer.asm` — handler.** After `Seq_Op_Tempo`:
   ```
   ; $F4 MEV_LFO + value : write YM2612 $22 (bit3 enable | bits0-2 rate). The global
   ; LFO drives every channel's $B4 AMS (tremolo) / FMS (vibrato) depth bits (set by
   ; MEV_PAN/Fm_SetPan). MUST re-park the DAC $2A address after the $22 write: the
   ; addr port is parked on $2A during playback, so a stray $22 select would misroute
   ; the next DAC byte (spec §6). Fm_YmWrite + Fm_ReparkDac both preserve hl. Zero-tick.
   Seq_Op_Lfo:
           ld      c, (hl)                  ; c = operand ($22 byte: enable|rate)
           inc     hl                       ; consume operand
           ld      a, SND_REG_LFO           ; $22
           ld      b, 0                     ; part I
           call    Fm_YmWrite               ; $4000=$22, $4001=value (preserves bc/de/hl/ix)
           call    Fm_ReparkDac             ; restore the DAC $2A park (DAC-safe)
           jp      Seq_ContinueFetch
   ```

4. **Dispatch table.** sound_sequencer.asm:1211 — change `dw Seq_BadOpcode ; $F4 reserved` to:
   ```
           dw      Seq_Op_Lfo               ; $F4 MEV_LFO
   ```

5. **`engine/z80_sound_driver.asm` — init doc fix.** Lines 158 & 167: change `~3.98Hz`/`~3.98 Hz` to `~3.82 Hz` (comment only; the `$08` value is correct and stays).

6. **Build:** green; size check; opcode asserts pass.

7. **Boot verify** (exodus): play `SONG_MOVINGTRUCKS` → unchanged. Exercise the handler: `emulator_z80_write` the bytes `$F4 $03` into a live channel stream (or a throwaway test phrase) → confirm `$22` becomes `$0B` (enable|rate3 = 6.11 Hz) via the YM register stream, **and** that DAC drums still play cleanly immediately after (the `$2A` park survived — listen/measure for no DAC glitch). Then write `$F4 $00` → `$22=$00` (LFO off).

8. **Commit:** `sound: MEV_LFO ($F4) — write $22 with $2A park save/restore + 3.82 Hz doc fix`.

---

## Task C2 — Verify the hardware LFO (and the F1 finding)

### Steps

1. Build; reload symbols in **exodus**.
2. **Confirm F1:** at runtime read reg `$22` while a song plays — expect `$08` (LFO already on from init). Document the result.
3. **Register + DAC-safety:** trigger `MEV_LFO $03` (via stream poke or a test phrase). Confirm (a) `$22` changed to `$0B`, (b) the addr port re-parked on `$2A` (DAC bytes still route correctly) — capture a DAC-drum hit right after the opcode and confirm clean playback (no corruption/click). This is the load-bearing `$2A`-park check.
4. **Audible modulation:** on an FM channel with nonzero `$B4` AMS/FMS bits (set via `MEV_PAN` — author a short test phrase if no existing song uses AMS/FMS), capture a sustained note; measure the **amplitude-modulation (tremolo) depth + rate** in the audio spectrum (sidebands at the LFO rate) via `emulator_audio_spectrum` / `tools/vgm_intranote.py`. Confirm the modulation rate **changes** between two `MEV_LFO` rate values (e.g. rate 0 → 3.82 Hz vs rate 3 → 6.11 Hz). Confirm disabling (`$22=$00`) removes it.
5. **Regression:** MT golden green; DAC drums unaffected across LFO writes.
6. **Commit** (notes): `sound: verify hardware LFO ($22 rate change, $2A-park DAC safety, audible AMS/FMS)`. Record the F1 confirmation + measured rates in the PR.

---

## Self-review

**Spec coverage (Phase 2 scope):**
- ✅ Master fade — one global scalar `SND_MASTER_FADE` folded into the two existing music volume writes (the same music-only gate the duck uses, confirmed F2), driven by `Fade_Ramp` (state = target + delay counter), with the `SND_FADE_DIRTY` flag re-asserting held notes in `ModUpdate`; 68k `Sound_FadeOut`/`Sound_FadeIn` + `SND_REQ_FADE` mailbox (spec §7).
- ✅ Global tempo — `SND_TEMPO_CUR` replaces the literal `16` decrement; `Tempo_Ramp` glides; `MEV_TEMPO` ($F3) + `SND_REQ_TEMPO`/`Sound_SetTempo`; SMPS accumulator idiom, no multiply (spec §7).
- ✅ Hardware LFO — `MEV_LFO` ($F4) writes `$22` wrapped in `Fm_YmWrite`+`Fm_ReparkDac` ($2A park), doc fix to 3.82 Hz (spec §6).
- ✅ Out-of-scope items (portamento, fine-detune, FM TL vol-env, SSG-EG, MEV_REGWRITE, macro spine, DAC, vibrato, per-channel $B4 automation) untouched.

**No placeholders:** every step has exact asm/68k/constant text + exact build/verify commands.

**RAM / opcode-number consistency:** `SND_GLOBAL_EXPR=$1AB7` (= ring end), 7 bytes, ends `$1ABE < SND_SONG_BUF=$1B00` (66 B headroom); asserted. Mailbox slots `$1F05/$1F06` clear of `SND_CTRL_DMA_ACTIVE=$1F04` and `SND_STAT_BASE=$1F10`; asserted. `MEV_TEMPO=$F3`/`MEV_LFO=$F4` were `Seq_BadOpcode` (free); distinct; asserts mirror existing MEV asserts; dispatch entries updated. `SND_TEMPO_DECR_DEFAULT=16` everywhere; `0`-clamp at all three setters (opcode, mailbox, restore) prevents a frozen song.

**The `$2A`-park hazard:** `Seq_Op_Lfo` selects `$22`/writes via `Fm_YmWrite` (part I, absolute addressing — `de`=$4001 untouched) then `Fm_ReparkDac` re-selects `$2A` — both preserve `hl` (the live stream ptr), so no push/pop needed. Task C2 explicitly captures a DAC hit after the opcode to prove the park survived.

**The fade-dirty re-assert hazard:** `SND_FADE_DIRTY` is set by `Fade_Ramp` (before the channel loop) and cleared only on the active fall-through after the loop (`jr z,.run_sfx` early-exits skip the clear — correct, since `Fade_Ramp` never ran there). `ModUpdate`'s re-assert runs after the SFX-override `ret nz` (so a stolen voice is skipped), only for KEYED FM/PSG (DAC excluded), and `Fm_SetVolume`/`Psg_SetVolume` preserve `ix`; the loop counter is on the stack. Steady-state cost = one `ld/or/jr` per channel.

**The fade-silence-after-stop hazard:** song-load `.arm` resets `SND_MASTER_FADE=0` (and tempo=16), so a song played after a fade-out is **not** silent. Init zeroes them once.

**Z80 size:** Phase 2 adds ~250–350 bytes; the F5 co-location left ~1 KB. Every Z80-code task re-checks the `Z80_SOUND_SIZE <= $16F0` assert + `s4budget`; **flag overflow rather than working around it.**

**OPEN questions (flagged, not guessed):**
1. **F1 — LFO already enabled at init.** Resolved empirically in Task 0/C2. `MEV_LFO`'s value is rate/enable control, not "un-deading inert bits" (the spec premise is wrong against this code). If MEV_PAN AMS/FMS already modulates today, C2 verifies the *rate change* + `$2A` safety.
2. **Fade-to-prev / crossfade** with full "restore saved song state" (spec §7) needs driver-side previous-song save/restore — heavier than the global-scalar scope. **Deferred:** crossfade is delivered as a game-level composition riding on `Sound_FadeOut`/`Sound_FadeIn`/`Sound_PlayMusic`.
3. **Fade/tempo ramp speed** is fixed by constants (`SND_FADE_STEP`/`SND_FADE_DELAY`, 1-unit tempo step). If per-command speed is wanted, add a second mailbox arg slot later (the single-byte mailbox model is preserved here for consistency).
4. **DAC not faded** (master fade folds only into `Fm_SetVolume`/`Psg_SetVolume`, per scope). Acceptable game-feel; a DAC fade is future DAC-mixer work.
```

---

### Critical Files for Implementation
- /home/volence/sonic_hacks/s4_engine-music-expr/engine/sound_sequencer.asm
- /home/volence/sonic_hacks/s4_engine-music-expr/sound_constants.asm
- /home/volence/sonic_hacks/s4_engine-music-expr/engine/z80_sound_driver.asm
- /home/volence/sonic_hacks/s4_engine-music-expr/engine/sound_fm.asm
- /home/volence/sonic_hacks/s4_engine-music-expr/engine/sound_psg.asm
