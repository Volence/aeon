# Music Expression Engine — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. The numbered steps are bite-sized; treat each as a checkbox and verify before moving on.

**Date:** 2026-06-26
**Branch:** `feat/music-expr-p1` (worktree `/home/volence/sonic_hacks/s4_engine-music-expr`, == master)
**Spec:** `docs/superpowers/specs/2026-06-23-music-expression-engine-design.md` (§3 spine, §4 T1 pitch, §5 vol-env slot, §9 Task 0)

---

## Goal

Phase 1 is the **structural enabler** for the Music Expression Engine: grow the music `SeqChannel` struct to its end-state size so it carries the modulation block, fine-detune, and unified vol-env slot at the **same offsets the `SfxChannel` already uses**, relocate the DEBUG trace ring off its page boundary to make room, then **un-gate** the already-built-and-verified software vibrato / pitch-modulation core (`Mod_Advance` + friends) for MUSIC channels (FM + PSG) by deleting the SFX-only `Snd_ChanClass` gates at every read/write site, and add the spec's block-boundary octave correction so modulated pitch crosses octaves seamlessly.

After this phase, HCZ2's already-imported `smpsModSet` FM vibrato (9 `MEV_MODSET` `$EC` bytes already present in `data/sound/song_hcz2.asm`) becomes audible and matches S3K; Moving Trucks (the golden boot song, no modulation) renders byte/spectrum-identical; SFX vibrato does not regress.

**Out of scope (later phases — do NOT build):** master fade, tempo, hardware-LFO `$22`/`$B4` control, portamento *renderer* (the `sc_porta_*`/`sc_detune` bytes are only *reserved* here), FM TL vol-env, SSG-EG, `MEV_REGWRITE`, the slot[1] macro/automation spine, any DAC work.

## Architecture

Two facts from the real code drive the design:

1. **The mod core is already shared and stream-agnostic.** `Mod_Advance` / `Mod_ReArm` / `Mod_ApplyVibrato` (FM) / `Psg_ApplyMod` (PSG) / `PsgEnvUpdate` read only `sc_*` state, never a stream. They were written to serve *both* structs and are gated SFX-only purely because the music `SeqChannel` was too short to hold `sc_mod_*` (offsets +42..+54). The SFX path through them is shipped and verified faithful. So music vibrato = (a) give the music struct those fields at the identical offsets, then (b) delete the `ix >= SND_SFX_BASE` gates.

2. **The seq RAM block is boxed in.** Array base `SND_SEQ_CHANNELS = $1808`; today `SeqChannel_len = 43` → `SND_SEQ_END = $19E1`; the DEBUG trace ring is **page-aligned** at `$1A00` (the writer builds its address as `h = SND_SEQ_TRACE>>8 / l = index`), and `SND_MUSIC_PARAM = $1A20` (hardcoded), `SND_SONG_BUF = $1B00`. Growing the struct to ~58 B pushes `SND_SEQ_END` to `$1A86`, which overruns **both** the trace ring and the music-param block. The page-aligned trace formula `(Snd_SpindashRev+1+$FF)&$FF00` would round up to `$1B00` and collide with the song buffer.

   **RAM reorg:** make `SND_MUSIC_PARAM` track the end of the `Snd_*` scratch (no longer `$1A20`); place the trace ring **above** it (no longer page-aligned); change the trace writer from `ld h,page / ld l,index` to a `base + index` 16-bit add. With `SeqChannel_len = 58` the new tail is `SND_SEQ_END=$1A86`, scratch → `$1A91`, `SND_MUSIC_PARAM=$1A91`, `SND_SEQ_TRACE=$1A97..$1AB7`, all below `SND_SONG_BUF=$1B00` (73 B headroom). Both 68k (`engine/sound_api.asm`) and the debug mirror (`debug/sound_debug.asm`) already reference `SND_MUSIC_PARAM` / `SND_SEQ_TRACE` **by symbol**, so the move is transparent.

**End-state struct layout (the shared prefix extends through the mod block):**

| off | SeqChannel (music, NEW len 58) | SfxChannel (len 62, UNCHANGED) |
|----:|---|---|
| +0..+38 | shared interpreter prefix | identical |
| +39/40/41 | `sc_psgenv`/`_cur`/`_out` (alias `sc_env`/`_cur`/`_out`) | identical |
| +42..+48 | `sc_mod_ctrl,wait,speed,delta,steps,speed_raw,step_raw` | identical |
| +49 (w) | `sc_mod_accum` | identical |
| +51 (w) | `sc_base_freq` | identical |
| +53 (w) | `sc_last_freq` | identical |
| **+55** | `sc_noise_mode` (RELOCATED from +42) | `sx_priority` (diverges) |
| **+56** | `sc_detune` (reserved, signed; unused in P1) | `sx_pad` |
| **+57** | `sc_pad` (even-length pad) | `sx_patch_base` … |

The shared block is `+0..+54`; music-only fields and SFX bookkeeping legitimately diverge at `+55`. `sc_noise_mode` (music) and `sx_priority` (SFX) share offset +55 but are only ever read with their own struct's `ix` (verified: all four `sc_noise_mode` sites use a music `ix`). The "unified vol-env slot" is the existing `sc_psgenv` 3 bytes — Phase 1 adds the `sc_env*` *names* (zero new bytes; the FM vol-env phase plugs into them later). `sc_detune`/`sc_porta_accum`/`sc_porta_incr` are reserved bytes only (no renderer in Phase 1).

**Block-boundary correction (`Mod_Advance`, FM-only).** `Mod_Advance` is shared, so the correction branches on `SCF_IS_FM_B`. PSG keeps the plain 16-bit `base + accum` divisor add. FM splits the packed `$A4:$A0` word into `block` (3-bit) + `fnum` (11-bit), adds the signed accum to `fnum`, then single-steps the block: `fnum >= FNUM_HI → fnum>>=1, block++` (cap 7); `fnum < FNUM_LO and block>0 → fnum<<=1, block--`; repacks. Halving fnum + incrementing block is the *same chip pitch* (freq ∝ `fnum·2^block`), so this is pitch-preserving and **inert for in-window notes** (identical to the old combined add). `FNUM_LO=$0284` (the table's minimum fnum), `FNUM_HI=$0508` (= 2×, < `$0800` so it fires before the 11-bit field overflows into block). This runs only for channels with `sc_mod_ctrl != 0`, so non-modulated playback (all of Moving Trucks) never reaches it.

## Tech Stack

- **Z80 assembler:** AS (Macroassembler) via `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → `s4.bin` (+ symbols via `convsym`). A *plain* `./build.sh` EXCLUDES all sound.
- **Conventions** (`CODING_CONVENTIONS.md`): `struct/endstruct`, sized branches, `phase/dephase`, no `mulu`/`divu`, compile-time math via `function`. AS does **not** auto-align `ds.w`/`ds.l` — pad structs to even by hand. Any RAM-layout change requires a runtime boot verification, not just build asserts.
- **Verification:** rendered AUDIO, never register proxies. Exodus MCP (`exodus`) drives our ROM; oracle MCP (`oracle`) runs the S3K reference. VGM captured in ≤450-frame chunks (longer freezes the oracle). Diff tools: `tools/vgm_modulation_diff.py` (vibrato/pitch-motion OURS-vs-ORACLE; create if absent), `tools/vgm_intranote.py`, `tools/vgm_onsets.py`. Reference: `docs/research/reference_captures/`.
- **Daemon-watched, do NOT touch:** `data/editor/**`, `tools/ojz_strip_gen.py`. (`data/sound/*`, sound tooling are fair game but Phase 1 needs no content/tool change — HCZ2 already carries the `MEV_MODSET` bytes.)
- Commit after each task; commit messages end with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `sound_constants.asm` | RAM map (trace ring + music-param relocation, FNUM constants); `SeqChannel`/`SfxChannel` struct defs + offset asserts + `sc_*` aliases | T1, T2, T6 |
| `engine/sound_sequencer.asm` | trace writer (`Seq_Trace`); `ModUpdate` FM+PSG mod gates; `Seq_Op_ModSet` gate; `Mod_Advance` block correction | T1, T3, T5, T6 |
| `engine/sound_fm.asm` | `Fm_NoteOnFreq` base-freq latch + `Mod_ReArm` gate | T4 |
| `engine/sound_psg.asm` | `Psg_NoteOn` base-freq latch gate + `Mod_ReArm` gate | T4 |
| `engine/z80_sound_driver.asm` | `.chan_init` — zero the new gate field `sc_mod_ctrl` + reserved `sc_detune` | T2 |

No new files. `debug/sound_debug.asm` and `engine/sound_api.asm` need **no edits** (symbol-based); only stale "$1A00" comments in `sound_constants.asm` / `debug/sound_debug.asm` are cosmetically out of date (optional).

---

## Task 0 — Confirm every gate site (the PSG-env lesson)

No edits. Build the exact inventory so no gate is missed (one `Seq_Op_PsgEnv` gate was missed in the PSG-env work and found only via the oracle).

**Steps**

1. List every channel-class gate:
   ```
   grep -rn "Snd_ChanClass" engine/sound_sequencer.asm engine/sound_fm.asm engine/sound_psg.asm
   ```
2. Classify each. The Phase-1 **REMOVE** set (un-gate music vibrato/pitch-mod) is exactly six:
   - `engine/sound_fm.asm` `Fm_NoteOnFreq` — `call Snd_ChanClass` + `jr c,.keyon` (base-freq latch + `Mod_ReArm`). **[T4]**
   - `engine/sound_psg.asm` `Psg_NoteOn` — `push hl`/`call Snd_ChanClass`/`pop hl`/`jr c,.skip_base_latch` (PSG base-freq latch). **[T4]**
   - `engine/sound_psg.asm` `Psg_NoteOn` — `call Snd_ChanClass`/`jr c,.skip_rearm` (`Mod_ReArm`). **[T4]**
   - `engine/sound_sequencer.asm` `Seq_Op_ModSet` — `push hl`/`call Snd_ChanClass`/`pop hl`/`jr c,.modset_done`. **[T3]**
   - `engine/sound_sequencer.asm` `ModUpdate` FM path — `call Snd_ChanClass`/`jr c,.vibrato_done`. **[T5]**
   - `engine/sound_sequencer.asm` `ModUpdate` PSG path — `call Snd_ChanClass`/`jr c,.psg_env`. **[T5]**
3. Confirm the **KEEP** set (legitimate music-vs-SFX behavior, NOT vibrato/vol-env gates — do **not** touch):
   - `engine/sound_psg.asm` `Psg_SetVolume` duck fold (`jr nc,.no_duck`) — music ducks, SFX must not.
   - `engine/sound_psg.asm` `Psg_Noise` (`jr nc,.sfx`) — music vs SFX noise encoding.
   - `engine/sound_fm.asm` `Fm_PatchPtr` and `Fm_SetVolume` duck fold.
   - `engine/sound_sfx.asm` duck logic.
4. Confirm the **PSG volume envelope is already fully un-gated** (the "proven template"): `Seq_Op_PsgEnv` (no class gate, comment confirms "applies to either"), `PsgEnvUpdate` (called for music + SFX from `ModUpdate` `.psg_env`), `Psg_EnvCursorReset` (called unconditionally in `Psg_NoteOn`/`Psg_Noise`). So "the PSG vol-env's remaining gates" = **none remain**; the only music-vs-SFX PSG gates left are the duck and noise-encoding branches above, which MUST stay.
5. Confirm every `sc_mod_*`/`sc_base_freq`/`sc_last_freq`/`sc_noise_mode` read/write site:
   ```
   grep -rn "sc_mod_ctrl\|sc_mod_wait\|sc_mod_speed\|sc_mod_delta\|sc_mod_steps\|sc_mod_speed_raw\|sc_mod_step_raw\|sc_mod_accum\|sc_base_freq\|sc_last_freq\|sc_noise_mode\|sc_detune" engine/*.asm
   ```
   Verify all four `sc_noise_mode` sites use a *music* `ix` (init `z80_sound_driver.asm`, `Seq_Op_PsgNoise`, `Psg_Noise` music path, `sound_sfx.asm` where `ix` = music noise channel) — so relocating it from +42 to +55 is transparent (the `sc_noise_mode` alias auto-updates and `ix` is always the 58-byte struct there).

**No commit** (read-only investigation; record the inventory in the PR description).

---

## Task 1 — RAM layout: relocate music-param block + trace ring, fix the trace writer (no behavior change)

Decouples the trace ring and music-param block from the page boundary / `$1A00`-`$1A20` so the grown struct (T2) fits. Struct is NOT grown yet, so addresses merely shift; behavior is preserved.

### Files

- `sound_constants.asm` — RAM-map tail (current ~lines 1002–1093).
- `engine/sound_sequencer.asm` — `Seq_Trace` writer (current ~lines 1190–1197).

### Steps

1. **`engine/sound_sequencer.asm` — `Seq_Trace`:** anchor on the existing block (inside `ifdef __DEBUG__`):
   ```
        ld      a, (SND_SEQ_TRACE_WR)
        and     SND_SEQ_TRACE_LEN-1      ; defensive wrap (len is a power of two)
        ld      l, a
        ld      h, SND_SEQ_TRACE>>8       ; trace ring is page-aligned ($1A00)
        ld      (hl), c                  ; trace[wr] = byte
        inc     a
        and     SND_SEQ_TRACE_LEN-1      ; wr = (wr+1) & (LEN-1)
        ld      (SND_SEQ_TRACE_WR), a
   ```
   Replace with (build the ring address as `base + index`; ring no longer page-aligned; `b` is free between the entry `push bc` and exit `pop bc`, and `c` still holds the trace byte):
   ```
        ld      a, (SND_SEQ_TRACE_WR)
        and     SND_SEQ_TRACE_LEN-1      ; index 0..31 (LEN is a power of two)
        ld      b, a                     ; save index for the post-increment below
        ld      hl, SND_SEQ_TRACE        ; ring base (NO LONGER page-aligned — see RAM map)
        add     a, l
        ld      l, a
        ld      a, h
        adc     a, 0
        ld      h, a                     ; hl = SND_SEQ_TRACE + index (carry-correct)
        ld      (hl), c                  ; trace[index] = (route<<4)|event
        ld      a, b
        inc     a
        and     SND_SEQ_TRACE_LEN-1      ; index = (index+1) & (LEN-1)
        ld      (SND_SEQ_TRACE_WR), a
   ```

2. **`sound_constants.asm` — RAM-map tail:** replace the whole span from the trace-ring definition through the song-buffer asserts (current ~lines 1002–1093 — the `SND_SEQ_TRACE = (Snd_SpindashRev + 1 + $FF) & $FF00` block, its asserts, the `SND_MUSIC_PARAM = $1A20` block, and the `SND_SONG_BUF` asserts) with the reordered block below. Leave `SND_SEQ_TRACE_LEN = 32` where it is defined (near `SND_SEQ_END`), and leave the `Snd_*` scratch defs (`SND_FM_SCRATCH … Snd_SpindashRev`) and the `if (SND_FM_SCRATCH < SND_SEQ_END)` guard above it unchanged.
   ```
   ; --- Music-load param block — RELOCATED above the Snd_* scratch.
   ; WAS the hardcoded $1A20; the end-state per-channel array (grown SeqChannel, Phase 1)
   ; overruns $1A20, so the param block now TRACKS the scratch end (Snd_SpindashRev + 1)
   ; and slides up automatically with any future growth. The 68k (engine/sound_api.asm)
   ; posts {bank,ptr,flags,patchptr} here under the SND_REQ_MUSIC bus hold; BOTH sides
   ; reference the SND_MUSIC_PARAM symbol, so the move is transparent. No alignment need.
   SND_MUSIC_PARAM          = Snd_SpindashRev + 1
   SND_MUSIC_PARAM_BANK     = SND_MUSIC_PARAM+$00    ; song bank id (1 byte)
   SND_MUSIC_PARAM_PTR      = SND_MUSIC_PARAM+$01    ; song $8000-window ptr (2 bytes, LE)
   SND_MUSIC_PARAM_FLAGS    = SND_MUSIC_PARAM+$03    ; song SH_FLAGS byte (1 byte)
   SND_MUSIC_PARAM_PATCHPTR = SND_MUSIC_PARAM+$04    ; song patch-bank window ptr (2 bytes, LE)
   SND_MUSIC_PARAM_LEN      = 6

   ; --- Sequencer opcode trace ring (DEBUG) — RELOCATED above the music-param block and
   ; NO LONGER PAGE-ALIGNED. The grown channel array consumed the old $1A00 page. The
   ; writer (Seq_Trace, engine/sound_sequencer.asm) now builds the ring address as
   ; base+index via a 16-bit add (was h=SND_SEQ_TRACE>>8 / l=index, which required a page
   ; boundary); the write index still wraps mask-based. SND_SEQ_TRACE_LEN is defined above.
   SND_SEQ_TRACE      = SND_MUSIC_PARAM + SND_MUSIC_PARAM_LEN

   SND_SEQ_HEADER_LEN = SND_SEQ_CHANNELS - SND_SEQ_BASE
       if (SND_FM_SCRATCH + SND_FM_SCRATCH_LEN) > SND_MUSIC_PARAM
         fatal "FM scratch (\{SND_FM_SCRATCH}) runs into the music param block (\{SND_MUSIC_PARAM})"
       endif
       if (SND_MUSIC_PARAM + SND_MUSIC_PARAM_LEN) > SND_SEQ_TRACE
         fatal "music param block (\{SND_MUSIC_PARAM}) runs into the trace ring (\{SND_SEQ_TRACE})"
       endif
       if SND_SEQ_END > SND_REQ_BASE
         fatal "sequencer RAM (\{SND_SEQ_END}) overruns the mailbox at \{SND_REQ_BASE}"
       endif

   ; --- Song RAM buffer. Page-aligned at $1B00, unchanged.
   SND_SONG_BUF            = $1B00
   SND_SONG_BUF_SIZE       = $200                   ; 512 bytes ($1B00..$1CFF)

       if (SND_SEQ_TRACE + SND_SEQ_TRACE_LEN) > SND_SONG_BUF
         fatal "trace ring (\{SND_SEQ_TRACE}+\{SND_SEQ_TRACE_LEN}) runs into the song buffer at \{SND_SONG_BUF}"
       endif
       if (SND_SONG_BUF + SND_SONG_BUF_SIZE) > SND_REQ_BASE
         fatal "song buffer (\{SND_SONG_BUF}+\{SND_SONG_BUF_SIZE}) overruns the mailbox at \{SND_REQ_BASE}"
       endif
   ```
   This removes the page-alignment `fatal` and the now-inverted "music param overlaps trace" assert, and replaces the old "channels overrun the trace ring" guard with the FM-scratch/music-param guards.

3. **Build:**
   ```
   SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
   ```
   Expected: green; `Build complete: s4.bin`. With `SeqChannel_len` still 43, `SND_SEQ_END=$19E1`, scratch→`$19EC`, `SND_MUSIC_PARAM=$19EC`, `SND_SEQ_TRACE=$19F2..$1A11` — all below `$1B00`, all asserts pass.

4. **Boot verify (mandatory for a RAM-layout change)** via the **exodus** MCP: `emulator_load_symbols` (reload the new symbol file), reload `s4.bin`, `emulator_reset`, `emulator_run_frames` ~600. Request `SONG_MOVINGTRUCKS` (the golden boot song) and confirm it plays and the DEBUG self-test/mirror stays green. `emulator_lookup_symbol SND_SEQ_TRACE` → expect `$19F2`; `emulator_z80_read` 32 bytes there and confirm trace bytes appear after a few frames of playback (writer works off the page boundary). Confirm no crash / no garbage in `$1B00+` (song buffer intact).

5. **Commit:** `git add -A && git commit` with:
   ```
   sound: relocate trace ring + music-param block off the $1A00 page; base+index trace writer

   Frees the $1A00 page for the upcoming SeqChannel growth. Music-param block now
   tracks the Snd_* scratch end; trace ring sits above it (no longer page-aligned);
   Seq_Trace builds the ring address as base+index. No behavior change (MT golden green).

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   ```

---

## Task 2 — Grow `SeqChannel` to the end-state size (mod block at shared offsets + detune + unified vol-env names)

Adds `sc_mod_ctrl..sc_last_freq` (+42..+54) at the identical `SfxChannel` offsets, relocates `sc_noise_mode` to +55, reserves `sc_detune` at +56, pads to even (len 58), adds `sc_env*` aliases, repoints the mod aliases to `SeqChannel`, extends offset asserts, and zeros the new gate field in `.chan_init`. Gates stay intact, so still no behavior change.

### Files

- `sound_constants.asm` — `SeqChannel struct` (current ~766–824), `SeqChannel_len` assert (826–828), `(ix+d)` range assert (829–832), shared-prefix assert (833–839), `sc_*` aliases (843–886).
- `engine/z80_sound_driver.asm` — `.chan_init` (current ~1215–1218).

### Steps

1. **`sound_constants.asm` — `SeqChannel struct`:** anchor on the current tail of the struct:
   ```
   sc_psgenv       ds.b 1   ; +39 PSG vol-env id (1-based; 0 = none)
   sc_psgenv_cur   ds.b 1   ; +40 PSG vol-env cursor (frame index into the body)
   sc_psgenv_out   ds.b 1   ; +41 last computed atten delta (folded by Psg_SetVolume)
   sc_noise_mode   ds.b 1   ; +42 SN76489 noise control byte ($E0|mode|rate) latched by
                            ; MEV_PSGNOISE — music-noise channel only ...
   SeqChannel endstruct      ; = 43 bytes
   ```
   Replace from `sc_noise_mode ds.b 1 ; +42 …` through `SeqChannel endstruct` with:
   ```
   ; --- pitch-modulation block (spec §4): SHARED with SfxChannel at the SAME offsets
   ;     (+42..+54) so Mod_Advance / Mod_ReArm / Mod_ApplyVibrato / Psg_ApplyMod render
   ;     MUSIC and SFX through one code path. Inert until MEV_MODSET arms sc_mod_ctrl.
   ;     (The aliases below come from SeqChannel now; an assert verifies the offsets
   ;     match SfxChannel byte-for-byte.) ---
   sc_mod_ctrl     ds.b 1   ; +42 pitch-mod control (0 = off; nonzero = active)
   sc_mod_wait     ds.b 1   ; +43 onset delay (one-shot, then held at 1)
   sc_mod_speed    ds.b 1   ; +44 frames between delta applications (countdown)
   sc_mod_delta    ds.b 1   ; +45 signed per-step delta (flips sign each half-period)
   sc_mod_steps    ds.b 1   ; +46 steps until direction reverse (countdown; seeded raw/2 at re-arm)
   sc_mod_speed_raw ds.b 1  ; +47 latched speed (reload source for sc_mod_speed)
   sc_mod_step_raw ds.b 1   ; +48 latched FULL step count (reload source for sc_mod_steps)
   sc_mod_accum    ds.w 1   ; +49 signed 16-bit accumulated freq offset
   sc_base_freq    ds.w 1   ; +51 unmodulated note word latched at key-on (FM $A4/$A0; PSG div hi/lo)
   sc_last_freq    ds.w 1   ; +53 last modulated word written (write-on-change shadow)
   ; --- music-only fields (diverge AFTER the shared block; SfxChannel uses +55.. for its
   ;     sx_* bookkeeping). sc_noise_mode shares offset +55 with SfxChannel's sx_priority,
   ;     but is only ever read with a MUSIC ix (all four sites verified). ---
   sc_noise_mode   ds.b 1   ; +55 SN76489 noise control byte (RELOCATED from +42)
   sc_detune       ds.b 1   ; +56 signed fine-pitch offset (RESERVED; renderer is a later phase)
   sc_pad          ds.b 1   ; +57 pad to an even struct length (AS does not auto-align ds.w)
   SeqChannel endstruct      ; = 58 bytes
   ```

2. **`sound_constants.asm` — `SeqChannel` asserts:** change the length assert
   ```
           if SeqChannel_len <> 43
             error "SeqChannel struct is \{SeqChannel_len} bytes, expected 43"
           endif
   ```
   to `<> 58` / `expected 58`. Change the range assert from `SeqChannel_sc_last_pan > 127` to `SeqChannel_sc_detune > 127` / `sc_detune offset`. Extend the shared-prefix assert (the `if (SfxChannel_sc_flags <> …)` line) to also cover the mod block:
   ```
           if (SfxChannel_sc_flags <> SeqChannel_sc_flags) || (SfxChannel_sc_route <> SeqChannel_sc_route) || (SfxChannel_sc_note <> SeqChannel_sc_note) || (SfxChannel_sc_points <> SeqChannel_sc_points) || (SfxChannel_sc_last_pan <> SeqChannel_sc_last_pan) || (SfxChannel_sc_psgenv <> SeqChannel_sc_psgenv) || (SfxChannel_sc_mod_ctrl <> SeqChannel_sc_mod_ctrl) || (SfxChannel_sc_mod_accum <> SeqChannel_sc_mod_accum) || (SfxChannel_sc_base_freq <> SeqChannel_sc_base_freq) || (SfxChannel_sc_last_freq <> SeqChannel_sc_last_freq)
             error "SfxChannel shared prefix diverges from SeqChannel field offsets"
           endif
   ```

3. **`sound_constants.asm` — `sc_*` aliases:** the mod aliases currently come from `SfxChannel` (`sc_mod_ctrl = SfxChannel_sc_mod_ctrl`, etc., ~lines 877–886). Repoint them to `SeqChannel` (offsets are asserted equal):
   ```
   sc_mod_ctrl     = SeqChannel_sc_mod_ctrl
   sc_mod_wait     = SeqChannel_sc_mod_wait
   sc_mod_speed    = SeqChannel_sc_mod_speed
   sc_mod_delta    = SeqChannel_sc_mod_delta
   sc_mod_steps    = SeqChannel_sc_mod_steps
   sc_mod_speed_raw = SeqChannel_sc_mod_speed_raw
   sc_mod_step_raw = SeqChannel_sc_mod_step_raw
   sc_mod_accum    = SeqChannel_sc_mod_accum
   sc_base_freq    = SeqChannel_sc_base_freq
   sc_last_freq    = SeqChannel_sc_last_freq
   sc_detune       = SeqChannel_sc_detune
   ```
   Add the unified vol-env names right after the `sc_psgenv*` aliases (zero new bytes — same +39/40/41 slot):
   ```
   ; Unified vol-env slot (spec §5): the FM TL vol-env (later phase) and the PSG vol-env
   ; share ONE 3-byte slot (a channel is FM xor PSG). These names alias the existing
   ; sc_psgenv slot so the FM vol-env phase plugs in with no layout change. No new bytes.
   sc_env          = SeqChannel_sc_psgenv
   sc_env_cur      = SeqChannel_sc_psgenv_cur
   sc_env_out      = SeqChannel_sc_psgenv_out
   ```

4. **`engine/z80_sound_driver.asm` — `.chan_init`:** anchor on
   ```
           ld      (ix+sc_noise_mode), 0    ; noise mode unset until MEV_PSGNOISE
   ```
   and add immediately after it:
   ```
           ; pitch-mod block: zero ONLY the gate field — sc_mod_ctrl==0 keeps every Mod_*
           ; path inert (the accum/base/last fields are set by MEV_MODSET/Mod_ReArm/note-on
           ; when armed, so they need no init). Without this a stale sc_mod_ctrl from a prior
           ; song's channel would spuriously enable vibrato once the gates are removed (T5).
           ld      (ix+sc_mod_ctrl), 0
           ld      (ix+sc_detune), 0        ; fine-detune neutral (reserved; renderer is a later phase)
   ```

5. **Build:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`. Expected green; `SeqChannel_len=58`, all offset/shared-prefix asserts pass, RAM-map asserts pass (`SND_SEQ_END=$1A86`, `SND_MUSIC_PARAM=$1A91`, `SND_SEQ_TRACE=$1A97..$1AB7`, all `< $1B00`). Confirm `s4budget.py` reports Z80 size still `<= $16F0` (the F5 co-location headroom absorbs the larger init).

6. **Boot verify** (exodus MCP): reload symbols + ROM, reset, run ~600 frames, play `SONG_MOVINGTRUCKS`. Confirm MT plays correctly (channel stride `add ix,de` with `de=58` is consistent) and the DEBUG channel mirror / trace still populate. Confirm the debug mirror still assembles (its `SEQ_MIRROR_CHBYTES=20 <= 58` assert and 176-byte window assert are unaffected). Spot-check `emulator_z80_read` a music channel slot: `(slot+42)=0` (`sc_mod_ctrl`), and the relocated `sc_noise_mode` at `(slot+55)`.

7. **Commit:**
   ```
   sound: grow music SeqChannel to end-state (mod block at shared SfxChannel offsets)

   Adds sc_mod_ctrl..sc_last_freq at +42..+54 (identical to SfxChannel), relocates
   sc_noise_mode to +55, reserves sc_detune at +56, pads to len 58. Adds sc_env* /
   sc_detune aliases; repoints the mod aliases to SeqChannel; extends offset asserts.
   .chan_init zeros sc_mod_ctrl (the gate) + sc_detune. Gates still intact: no behavior
   change (MT golden green).

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   ```

---

## Task 3 — Un-gate `Seq_Op_ModSet` for music FM/PSG

`MEV_MODSET` (`$EC`) now writes the music channel's `sc_mod_*`. HCZ2's 9 `$EC` opcodes begin arming modulation state (rendering is still gated until T5, so audio is essentially unchanged — only a benign transient base-freq re-write on FM until T4 latches a real base; HCZ2 is not the golden boot song).

### Files

- `engine/sound_sequencer.asm` — `Seq_Op_ModSet` (current ~669–676).

### Steps

1. Anchor on the gate block:
   ```
           ; --- SFX-channel gate: a music stream must not write sc_mod_* ---
           push    hl                       ; save stream ptr (Snd_ChanClass clobbers hl)
           call    Snd_ChanClass            ; CARRY set => ix < $1D00 => music channel
           pop     hl                       ; restore stream ptr (pop does not affect flags)
           jr      c, .modset_done          ; music: ignore the writes (hl = stream ptr intact)
   ```
   Replace with (the field writes below do not touch `hl`, so the live stream ptr stays valid without the push/pop; the FM base-freq re-write further down still push/pops `hl` around `Fm_WriteFreq`):
   ```
           ; --- music + SFX both write sc_mod_* now (the SFX-only gate was removed in
           ; Phase 1; sc_mod_* exist on both structs at the same offsets). The field
           ; writes below do not clobber hl, so the live stream ptr stays valid. ---
   ```
   Leave the rest of `Seq_Op_ModSet` (the `or` of params, the `ld (ix+sc_mod_*)` writes, the FM `cp CHROUTE_PSG1` / `push hl … Fm_WriteFreq … pop hl` base-freq re-write, and the `.modset_done:` label) unchanged.

2. **Build + boot verify** (exodus MCP): `./build.sh` green. Boot, play `SONG_MOVINGTRUCKS` → unchanged (MT has no `MEV_MODSET`). Optionally play `SONG_HCZ2` and confirm it still boots/plays (vibrato not yet rendered; no crash).

3. **Commit:** `sound: un-gate Seq_Op_ModSet (MEV_MODSET) for music channels` + trailer.

---

## Task 4 — Un-gate the note-on base-freq latch + `Mod_ReArm` for music FM and PSG

Music FM (`Fm_NoteOnFreq`) and music PSG (`Psg_NoteOn`) now latch `sc_base_freq` and call `Mod_ReArm` (a no-op while `sc_mod_ctrl==0`), giving the renderer the unmodulated base. Closes the T3 transient. Still no audible change for non-modulated songs.

### Files

- `engine/sound_fm.asm` — `Fm_NoteOnFreq` (current ~700–704).
- `engine/sound_psg.asm` — `Psg_NoteOn` base-freq latch (~167–173) and `Mod_ReArm` (~185–188).

### Steps

1. **`engine/sound_fm.asm` — `Fm_NoteOnFreq`:** anchor on
   ```
           call    Snd_ChanClass            ; CARRY set => MUSIC channel (hl = ix)
           jr      c, .keyon                ; music -> no mod fields; straight to key-on
           ld      (ix+sc_base_freq), d     ; high byte slot = $A4 value
           ld      (ix+sc_base_freq+1), e   ; low byte slot  = $A0 value
           call    Mod_ReArm                ; per-note re-arm (no-op if sc_mod_ctrl==0)
   .keyon:
   ```
   Remove the two gate lines (`call Snd_ChanClass` + `jr c,.keyon`), keeping the latch, `Mod_ReArm`, and the `.keyon:` label:
   ```
           ; latch the unmodulated note word for the vibrato renderer (music + SFX now;
           ; sc_base_freq exists on both structs at +51) + per-note re-arm. Mod_ReArm
           ; reads sc_mod_*/sc_base_freq only (no chip), no-op when sc_mod_ctrl==0.
           ld      (ix+sc_base_freq), d     ; high byte slot = $A4 value
           ld      (ix+sc_base_freq+1), e   ; low byte slot  = $A0 value
           call    Mod_ReArm                ; per-note re-arm (no-op if sc_mod_ctrl==0)
   .keyon:
   ```

2. **`engine/sound_psg.asm` — `Psg_NoteOn` base-freq latch:** anchor on
   ```
           push    hl                       ; preserve the divisor table ptr (Snd_ChanClass clobbers hl)
           call    Snd_ChanClass            ; CARRY set => ix < $1D00 => music channel
           pop     hl                       ; restore the table ptr
           jr      c, .skip_base_latch      ; music PSG -> no mod fields, don't latch
           ld      (ix+sc_base_freq), d
           ld      (ix+sc_base_freq+1), e
   .skip_base_latch:
   ```
   Replace with (no `Snd_ChanClass` → `hl` is not clobbered, so the divisor table ptr survives without the push/pop):
   ```
           ; latch the base divisor for pitch modulation (music + SFX now). The two
           ; stores do not touch hl, so the divisor table ptr survives.
           ld      (ix+sc_base_freq), d
           ld      (ix+sc_base_freq+1), e
   .skip_base_latch:
   ```

3. **`engine/sound_psg.asm` — `Psg_NoteOn` `Mod_ReArm`:** anchor on
   ```
           call    Snd_ChanClass            ; CARRY set => ix < $1D00 => MUSIC channel
           jr      c, .skip_rearm           ; music PSG -> no mod re-arm (byte-identical)
           call    Mod_ReArm                ; PSG pitch-mod re-arm (preserves bc/de/hl/ix)
   .skip_rearm:
   ```
   Replace with:
   ```
           call    Mod_ReArm                ; PSG pitch-mod re-arm (music + SFX; no-op if sc_mod_ctrl==0)
   .skip_rearm:
   ```

4. **Build + boot verify** (exodus MCP): `./build.sh` green (confirm Z80 size assert still passes — this task *removes* code). Play `SONG_MOVINGTRUCKS` → byte/spectrum-unchanged (`Mod_ReArm` no-ops with `sc_mod_ctrl==0`; the base-freq latch writes RAM only). Play `SONG_HCZ2` → boots; vibrato still not rendered (ModUpdate gate intact).

5. **Commit:** `sound: un-gate note-on sc_base_freq latch + Mod_ReArm for music FM/PSG` + trailer.

---

## Task 5 — Un-gate `ModUpdate` vibrato/pitch-mod rendering for music FM + PSG

Removes the two `ModUpdate` channel-class gates so music FM runs `Mod_ApplyVibrato` and music PSG runs `Psg_ApplyMod` when `sc_mod_ctrl != 0`. **Must come after T2** (the music noise channel's `sc_mod_ctrl` is now the zeroed +42 field, not the old `sc_noise_mode` at +42 — so reading it on a music PSG/noise channel is safe). With the un-gates from T3/T4, HCZ2's FM vibrato now renders.

### Files

- `engine/sound_sequencer.asm` — `ModUpdate` PSG path (~149–150) and FM path (~192–193).

### Steps

1. **PSG gate:** anchor on
   ```
           call    Snd_ChanClass            ; CARRY set => MUSIC channel
           jr      c, .psg_env              ; music PSG -> env only (no mod fields at +42+)
           ; --- SFX PSG PITCH MODULATION (spec §5): ...
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Psg_ApplyMod         ; advance accum + re-latch tone divisor (no re-key)
   ```
   Remove the two gate lines; music + SFX PSG now both run the mod check (a music noise/tone channel with `sc_mod_ctrl==0` skips `Psg_ApplyMod` — its +42 was zeroed in `.chan_init`, T2):
   ```
           ; --- PSG PITCH MODULATION (spec §5; music + SFX). A non-modulated PSG channel
           ; (sc_mod_ctrl==0 — incl. every noise track, which never sets it) pays one test.
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Psg_ApplyMod         ; advance accum + re-latch tone divisor (no re-key)
   ```
   Keep the `.psg_env:` label and the env code that follows unchanged.

2. **FM gate:** anchor on
   ```
           call    Snd_ChanClass            ; CARRY set => MUSIC channel
           jr      c, .vibrato_done         ; music FM -> no mod fields, skip (byte-identical)
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Mod_ApplyVibrato     ; advance + write-on-change $A4/$A0 (no key-on)
   .vibrato_done:
   ```
   Remove the two gate lines:
   ```
           ; --- PITCH MODULATION (spec §5; music + SFX). Non-modulated FM (sc_mod_ctrl==0)
           ; pays one test. Modulates the HELD note (no key-on).
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Mod_ApplyVibrato     ; advance + write-on-change $A4/$A0 (no key-on)
   .vibrato_done:
   ```

3. **Build + boot verify** (exodus MCP): `./build.sh` green. Play `SONG_MOVINGTRUCKS` → unchanged (all `sc_mod_ctrl==0`). Play `SONG_HCZ2` → FM vibrato now audibly present. Quick check via `tools/vgm_modulation_diff.py` on a short capture: freq-reg rewrites between key-ons appear on the modulated FM channels (full A/B vs S3K is T7).

4. **Commit:** `sound: un-gate ModUpdate vibrato/pitch-mod (Mod_ApplyVibrato/Psg_ApplyMod) for music` + trailer.

---

## Task 6 — Block-boundary octave correction in `Mod_Advance` (FM-only)

Adds the spec §4 correction so a modulated FM fnum crosses octaves seamlessly. Pitch-preserving and inert for in-window notes (so SFX/HCZ2 in-range vibrato is unchanged); only channels with active modulation reach this code.

### Files

- `sound_constants.asm` — new `FNUM_LO`/`FNUM_HI` constants (near `FMPITCH_MAX_IDX`, ~line 497).
- `engine/sound_sequencer.asm` — `Mod_Advance` `.sustain` (current ~448–454).

### Steps

1. **`sound_constants.asm` — FNUM window:** add near `FMPITCH_MAX_IDX`:
   ```
   ; --- Block-boundary fnum window for the pitch-modulation octave correction (spec §4).
   ; halve-fnum + block++ (or double-fnum + block--) is the SAME chip pitch
   ; (freq ∝ fnum·2^block), so normalizing a modulated fnum into [FNUM_LO, FNUM_HI) keeps
   ; vibrato/glide continuous across an octave. HI = 2*LO and HI < $0800 so the correction
   ; fires BEFORE the 11-bit fnum field overflows into the block bits. Values: FmPitchTableZ
   ; minimum fnum ($0284) and ~the S.C.E. zDoPitchSlide $283/$508 thresholds.
   FNUM_LO = $0284
   FNUM_HI = $0508
           if FNUM_HI <> FNUM_LO*2
             error "FNUM_HI must be exactly 2x FNUM_LO (pitch-preserving octave correction)"
           endif
           if FNUM_HI >= $0800
             error "FNUM_HI must be < $0800 so the correction fires before 11-bit fnum overflow"
           endif
   ```

2. **`engine/sound_sequencer.asm` — `Mod_Advance` `.sustain`:** anchor on
   ```
   .sustain:
           ; --- final word = base_freq + accum (16-bit) ---
           ld      h, (ix+sc_base_freq)     ; FM: $A4 value / PSG: divisor hi  = high byte
           ld      l, (ix+sc_base_freq+1)   ; FM: $A0 value / PSG: divisor lo  = low byte
           ld      c, (ix+sc_mod_accum)
           ld      b, (ix+sc_mod_accum+1)   ; bc = signed accum
           add     hl, bc                   ; hl = modulated word
   ```
   Replace with (split FM into block|fnum + single-step block correction; PSG keeps the plain combined add; the triangle-reverse block and `.write` that follow are unchanged and consume `hl`):
   ```
   .sustain:
           ; --- final word = base + accum. FM applies the BLOCK-BOUNDARY CORRECTION (spec
           ; §4): split block|fnum, add accum to the 11-bit fnum, renormalize block so the
           ; modulated pitch crosses octaves seamlessly. PSG has no block: plain 16-bit add
           ; onto the 10-bit divisor. Mod_Advance is shared, so split on route class. Runs
           ; only when sc_mod_ctrl!=0 (caller-gated), so normal playback never reaches here.
           bit     SCF_IS_FM_B, (ix+sc_flags)
           jr      z, .psg_word
           ; --- FM: hl = 11-bit fnum, b = block (0..7) ---
           ld      a, (ix+sc_base_freq)     ; $A4 value = (block<<3)|fnumHi3
           and     007h
           ld      h, a                     ; fnum bits 10..8
           ld      l, (ix+sc_base_freq+1)   ; fnum bits 7..0  -> hl = 11-bit fnum
           ld      a, (ix+sc_base_freq)
           rrca
           rrca
           rrca
           and     007h
           ld      b, a                     ; b = block
           ld      e, (ix+sc_mod_accum)
           ld      d, (ix+sc_mod_accum+1)
           add     hl, de                   ; hl = fnum + signed accum
           ; hi correction: fnum >= FNUM_HI -> fnum>>=1, block++ (block capped at 7)
           ld      a, b
           cp      007h
           jr      z, .fm_lo                ; block already 7 -> cannot raise further
           ld      a, h
           cp      FNUM_HI>>8
           jr      c, .fm_lo                ; fnum hi-byte < HI hi-byte -> below HI
           jr      nz, .fm_hi_do            ; hi-byte > HI hi-byte -> above HI
           ld      a, l
           cp      FNUM_HI&0FFh
           jr      c, .fm_lo                ; equal hi-byte, lo < HI lo -> below HI
   .fm_hi_do:
           srl     h
           rr      l                        ; fnum >>= 1
           inc     b                        ; block += 1
           jr      .fm_pack                 ; one step suffices for a per-frame vibrato delta
   .fm_lo:
           ; lo correction: fnum < FNUM_LO and block > 0 -> fnum<<=1, block--
           ld      a, b
           or      a
           jr      z, .fm_pack              ; block 0 -> keep low fnum (valid lowest pitch)
           ld      a, h
           cp      FNUM_LO>>8
           jr      c, .fm_lo_do             ; fnum hi-byte < LO hi-byte -> below LO
           jr      nz, .fm_pack             ; hi-byte > LO hi-byte -> at/above LO
           ld      a, l
           cp      FNUM_LO&0FFh
           jr      nc, .fm_pack             ; equal hi-byte, lo >= LO lo -> at/above LO
   .fm_lo_do:
           add     hl, hl                   ; fnum <<= 1
           dec     b                        ; block -= 1
   .fm_pack:
           ld      a, b
           add     a, a
           add     a, a
           add     a, a                     ; block << 3
           or      h                        ; (block<<3)|fnumHi3 = $A4 value (h is 0..7)
           ld      h, a                     ; hl = packed word (h=$A4 value, l=$A0 value)
           jr      .have_word
   .psg_word:
           ld      h, (ix+sc_base_freq)     ; PSG: divisor hi
           ld      l, (ix+sc_base_freq+1)   ; PSG: divisor lo
           ld      c, (ix+sc_mod_accum)
           ld      b, (ix+sc_mod_accum+1)   ; bc = signed accum
           add     hl, bc                   ; hl = modulated divisor
   .have_word:
   ```
   Leave the existing triangle-reverse (`dec (ix+sc_mod_steps)` … `neg` … `ld (ix+sc_mod_delta),a`) and `.write:` write-on-change block immediately below unchanged — they read/write only `ix`-relative state and `hl`, both intact here.

3. **Build:** `./build.sh` green; FNUM asserts pass; confirm `s4budget.py` Z80 size still `<= $16F0` (this task adds ~55 bytes; the F5 co-location headroom covers it — if it ever fails, that is the budget signal, not a logic error).

4. **Boot verify** (exodus MCP): play `SONG_MOVINGTRUCKS` → unchanged (no channel reaches `Mod_Advance`). Play `SONG_HCZ2` → FM vibrato continuous (no octave pops). Audio A/B is T7.

5. **Commit:** `sound: add FM block-boundary octave correction to Mod_Advance (spec §4)` + trailer.

---

## Task 7 — Rendered-audio verification vs S3K + SFX no-regression

Verify by AUDIO (project hard rule), not register proxies.

### Steps

1. **Build** the DEBUG ROM: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`; reload symbols in the **exodus** MCP.
2. **Capture OURS (HCZ2 FM vibrato):** boot `s4.bin` in exodus, trigger `SONG_HCZ2` (id 3), let it reach a phrase with active FM vibrato. `emulator_vgm_start` → `emulator_run_frames` in **≤450-frame** chunks → `emulator_vgm_stop`; save the VGM.
3. **Capture ORACLE (S3K HCZ2):** in the **oracle** MCP, run S3K, play Hydrocity Zone Act 2, capture the matching phrase in **≤450-frame** chunks (longer captures freeze the oracle). Save the VGM. (If a cached HCZ2 oracle exists under `docs/research/reference_captures/`, reuse it.)
4. **Compare:**
   - `python3 tools/vgm_modulation_diff.py OURS.vgm ORACLE.vgm` (create the tool if absent — extract per-FM-channel `$A4/$A0` rewrites between key-ons, report rate/depth) — confirm FM vibrato/pitch-motion is PRESENT on the modulated channels and the rate/depth match S3K.
   - Render both to WAV (the project's VGM→WAV path) and compare energy + spectrum; confirm vibrato sidebands are present and align with S3K. Confirm by ear.
   - **Block-boundary continuity:** if any HCZ2 vibrato note sits at high fnum (`> FNUM_HI`), confirm OURS is continuous (the correction is pitch-preserving) — expect a match to S3K's pitch with no octave pop. For the common in-window notes the correction is inert, so OURS == ORACLE.
5. **SFX no-regression (shared mod core):** trigger a modulated SFX (e.g. spindash, or any SFX whose transcode emits `MEV_MODSET`) over silence and over a song; capture OURS, A/B vs the S3K SFX reference. Confirm SFX vibrato is unchanged for in-window notes and continuous (not glitchy) for any boundary-crossing note — `Mod_Advance`'s FM split is identical to the old combined add for in-range fnum.
6. **Golden regression:** `SONG_MOVINGTRUCKS` must still render byte/spectrum-faithful (capture + compare to the MT baseline / `br_moving_trucks_oracle.vgm`); DEBUG boot self-test stays green.
7. **Commit** (verification artifacts / notes only, no code): `sound: verify Phase 1 music vibrato vs S3K HCZ2 + SFX no-regression` + trailer. Record the diff/correlation numbers in the PR body.

---

## Self-review

**Spec coverage (Phase 1 scope):**
- ✅ RAM layout grown to end-state + trace ring relocated (T1, T2) — spec §9 Task 0. `SND_SEQ_END=$1A86`, `SND_MUSIC_PARAM=$1A91`, `SND_SEQ_TRACE=$1A97..$1AB7` < `SND_SONG_BUF=$1B00`; SfxChannel unchanged at 62 B.
- ✅ Mod block + fine-detune + unified vol-env slot at the SfxChannel offsets (T2) — spec §4.4, §5. `sc_mod_ctrl..sc_last_freq` at +42..+54 (asserted equal to SfxChannel); `sc_detune` reserved at +56; `sc_env*` names alias the +39/40/41 slot.
- ✅ Un-gate software vibrato/pitch-mod (FM + PSG) for music at **every** site (T3 ModSet, T4 note-on FM+PSG latch+ReArm, T5 ModUpdate FM+PSG) — spec §4.4/§4.5. All six gate sites from the Task-0 inventory removed.
- ✅ PSG vol-env confirmed already fully un-gated (Task 0); no remaining gates — the only music-vs-SFX PSG gates left (duck, noise-encoding) are intentional and preserved.
- ✅ Block-boundary octave correction in `Mod_Advance` (T6) — spec §4, FM-only, pitch-preserving, `FNUM_LO=$0284`/`FNUM_HI=$0508`.
- ✅ Verification by rendered audio vs S3K HCZ2 + SFX no-regression (T7).
- ✅ Out-of-scope items (fade, tempo, LFO, portamento renderer, FM vol-env, SSG-EG, REGWRITE, macro spine, DAC) untouched; `sc_porta_*`/`sc_detune` are reserved bytes only.

**No placeholders:** every step has exact asm/Python text and exact commands.

**Type/offset consistency:** SeqChannel len 58 (even); max offset `sc_detune`=+56 < 127; shared block +0..+54 asserted byte-identical to SfxChannel (`sc_psgenv`/`sc_mod_ctrl`/`sc_mod_accum`/`sc_base_freq`/`sc_last_freq`); `sc_noise_mode`(+55, music) vs `sx_priority`(+55, SFX) collision is safe (all `sc_noise_mode` sites use a music `ix`, verified). Trace writer `b` is free, `c` holds the trace byte through `ld (hl),c`. `Mod_Advance` FM path uses `a/b/d/e/h/l`; the unchanged triangle-reverse + `.write` consume only `ix`-state and `hl`.

**Ordering / hazards called out:** T2 (relocate `sc_noise_mode` off +42, zero `sc_mod_ctrl`) MUST precede T5 (un-gate PSG mod), else a music noise channel's +42 byte would be a nonzero `sc_noise_mode` and spuriously trigger `Psg_ApplyMod`. The T3→T4 window has a benign transient FM base-freq re-write (HCZ2 only, not the golden song, not audio-verified intermediate). Every task keeps the build green and the MT golden boot green; the new behavior manifests only with modulated content (HCZ2/SFX), audio-verified at T7.

**Known extreme limitations (documented, not in Phase 1's verified path):** single-step block correction is correct for per-frame vibrato deltas; very large excursions (portamento, Phase 2) may need an iterated normalize. Block-7 + heavy upward vibrato and block-0 + heavy downward vibrato are clamped (no block wrap) rather than fully corrected — the table extremes, matching S3K's own limits.
