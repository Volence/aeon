# Music Expression Engine — Phase 2 (Per-Note): Portamento + Fine Detune + FM TL Volume-Envelope

> **For agentic workers:** REQUIRED SUB-SKILL — use `superpowers:subagent-driven-development` (or `superpowers:executing-plans`). Each numbered step is a checkbox: build + verify before moving on. Commit after each task; commit messages end with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

**Date:** 2026-06-27
**Branch:** `feat/music-expr-p1` (worktree `/home/volence/sonic_hacks/aeon-music-expr`; Phase 1 already merged on this branch)
**Spec:** `docs/superpowers/specs/2026-06-23-music-expression-engine-design.md` (§3.1 two fold-points, §4 T1 pitch = fine detune + portamento, §5 T2 FM TL vol-env + unified `sc_env` slot)
**Sibling slice (opcode coordination):** `docs/superpowers/plans/2026-06-27-music-expression-phase2-global.md` assigns `MEV_TEMPO=$F3`, `MEV_LFO=$F4`. **This slice assigns `MEV_PORTA=$F5`, `MEV_DETUNE=$F6`** — disjoint by construction (see Task 0 §6 and the per-opcode fixed-slot asserts).

> **⚠ RE-SCOPED 2026-06-27 — Group C (FM TL volume-envelope, Tasks C1–C4) + `MEV_FMENV=$F7` are SUPERSEDED.** They were absorbed into the Phase 3 macro/automation-spine spec (`docs/superpowers/specs/2026-06-27-music-expr-macro-spine-design.md`), where the FM-TL vol-env is the *volume* macro target's renderer. **Do NOT build Group C from this plan** — `$F7` is now owned by Phase 3; building it on both sides hits the fixed-slot assert (a hard duplicate-symbol break). This plan now delivers **porta ($F5) + detune ($F6) only.** Group C is left below for reference, struck. It was field- and dependency-disjoint from porta/detune (touches only the unified `sc_env` slot, never `sc_porta_*`/`sc_detune`/`Fm_FnumApplyDelta`), so the residual porta+detune work stands unchanged; the ~190 Z80 bytes Group C estimated move to the Phase 3 budget.

---

## Goal

Add the three **per-note expression** controls that Phase 1 reserved state for, each independently verifiable and each leaving the build green and the Moving Trucks golden boot song byte/spectrum-faithful:

1. **Fine detune** — a per-channel signed `sc_detune` (already reserved at SeqChannel +56) sign-extended and added to the looked-up fnum (FM, block-corrected) / divisor (PSG) **at note-on**, so it composes for free with vibrato + portamento (both build on the latched `sc_base_freq`). Drives unison/chorus (HCZ2's two PSG leads beat apart). The converter (`tools/smps_import.py`) emits it from `smpsDetune`/`smpsAlterNote` (currently dropped). Armed by `MEV_DETUNE` ($F6).
2. **Portamento** — a per-channel linear-in-fnum, add-only glide between notes (FM + PSG), reusing the already-reserved `sc_porta_accum` (+32, current sliding pitch) / `sc_porta_incr` (+34, used here as the persistent glide-rate magnitude). Reuses Phase 1's block-boundary octave correction via a shared `Fm_FnumApplyDelta` helper so a glide crosses octaves seamlessly. Armed by `MEV_PORTA` ($F5). **Zero new struct bytes.**
3. **FM TL volume-envelope** — intra-note carrier-TL swells/tremolo (the Flamedriver `zDoFMVolEnv` analogue), mirroring the shipped PSG vol-env engine (`PsgEnvUpdate` + its `$80`/`$81`/`$83`/plain-delta body format) but writing FM **carrier** TLs. Uses the unified `sc_env`/`sc_env_cur`/`sc_env_out` slot (Phase 1 aliased onto `sc_psgenv`). Folds `sc_env_out` into the existing `Fm_SetVolume` carrier-TL delta (`Fm_ScratchLog`, the same seam the duck + master-fade use). Resolves id→body via a new `FmVolEnv_Ids/Ptrs` map mirroring `PsgVolEnv_*`. Armed by `MEV_FMENV` ($F7).

**Out of scope (other phases — do NOT build):** master fade / global tempo / hardware LFO (the Phase-2 GLOBAL slice), SSG-EG, `MEV_REGWRITE`, the macro/automation spine (slot[1] `MacroTick`), any DAC work, vibrato (Phase 1, already shipped/un-gated).

---

## Architecture

Two facts from the **real code** (verified, Task 0) drive the design:

- **One pitch fold-point already exists and is octave-safe.** `Mod_Advance` (`engine/sound_sequencer.asm:418-535`) decomposes the packed FM `$A4:$A0` word into `(block, fnum)`, adds a signed accum to the 11-bit fnum, and single-steps the block via `FNUM_LO=$0284`/`FNUM_HI=$0508` (`sound_constants.asm:504-505`). Detune and portamento are **the same fnum arithmetic** applied at a different time (note-on for detune; per-frame for porta). We extract that block-correction into a small shared helper `Fm_FnumApplyDelta` (Group A) that both reuse — **we do NOT refactor the verified `Mod_Advance` inline copy** (avoids regressing Phase-1 vibrato; mild duplication is the safer trade at the `$16F0` ceiling).
- **The packed FM word is monotonic in pitch.** `packed = ($A4<<8)|$A0 = (block<<11)|fnum` with `fnum` ≤ 11 bits, so a plain 16-bit unsigned compare of two table-valid words gives the correct pitch ordering (used by portamento to pick glide direction + detect "reached"). The *step*, however, must be done in decomposed `(block,fnum)` space (a semitone is ~`$30-$50` of fnum inside a block but the packed word jumps `$07FC → $0C3B` across the block-0→1 boundary — see `FmPitchTableZ` indices 20→21), which is exactly why `Fm_FnumApplyDelta` is needed.

- **One carrier-TL fold-point already sums extra attenuation.** `Fm_SetVolume` stashes the log-volume delta in `Fm_ScratchLog` (`sound_fm.asm:354`), the per-op carrier loop (`:412-481`) reads it as a positive 8-bit delta (`ld b,0` sign-assumption at `:446`), and the duck folds into it (`:366-381`, music-only). The FM vol-env folds `sc_env_out` into `Fm_ScratchLog` **as a positive attenuation delta** (exactly like the shipped PSG env folds `sc_psgenv_out` into the PSG attenuation, `sound_psg.asm:317-326`) — this keeps the carrier-only selection (`CarrierMaskTableZ`) and the `b=0` sign-assumption intact, and composes additively with the duck (and, if the global slice lands, the master fade). FM vol-env therefore = **attenuation contour** (positive = quieter): swell-in = a high→0 contour, tremolo = an oscillating contour, identical semantics to the PSG bodies.

- **The unified env slot is FM-xor-PSG.** A channel is FM xor PSG, so `sc_env`/`sc_env_cur`/`sc_env_out` (= the `sc_psgenv*` slot at +39/+40/+41, `sound_constants.asm:908-910`) serves one renderer at a time: `ModUpdate`'s PSG path runs `PsgEnvUpdate` (resolve via `PsgVolEnv_*`), the FM path runs the new `FmEnvUpdate` (resolve via `FmVolEnv_*`). The opcode handler that sets the slot is shared (`MEV_FMENV` dispatches to the existing `Seq_Op_PsgEnv`, which sets `sc_env`+`sc_env_cur`); the *renderer* picks the table by route. Init already zeroes the slot (`z80_sound_driver.asm:1215-1217`), so it is init-clean for FM.

**Portamento ↔ vibrato composition (documented scoping decision).** While a glide is *in progress* (`sc_porta_incr != 0` AND `sc_porta_accum != sc_base_freq`), portamento **owns the pitch** (writes `$A4:$A0` / divisor, write-on-change via `sc_last_freq`) and vibrato is suppressed *for that channel that frame*. When the glide completes (`sc_porta_accum == sc_base_freq == target`), `Porta_Apply` returns carry-clear and the existing `Mod_ApplyVibrato`/`Psg_ApplyMod` path runs on the target note — so a held post-glide note still vibratos. Simultaneous glide+vibrato is therefore *sequential, not summed*; glides are short, so this is inaudible in practice and avoids two writers fighting over `sc_last_freq`. (Full simultaneous summation would require a second accumulator = new struct bytes, which Phase 1 did not reserve — flagged in Self-review.)

**`sc_porta_incr` semantics (documented refinement of the spec).** The spec says "zero `sc_porta_incr` on completion." With only the two reserved fields and no separate "porta-armed" flag, we instead treat **`sc_porta_incr` as the *persistent* glide-rate magnitude** (a byte; high byte 0) set by `MEV_PORTA`, and detect completion by `sc_porta_accum == sc_base_freq` (no field zeroed). This needs no extra state, keeps portamento armed across notes (the correct tracker behavior — a porta setting persists until changed), and direction is derived per-frame from `accum` vs `target`. `MEV_PORTA 0` disarms (subsequent notes snap). The converter/composer must precede the first `MEV_PORTA` on a channel with at least one normal (snapping) note so `sc_porta_accum` is seeded to a real pitch (`.chan_init` also zeros `sc_porta_incr` so a stale rate from a prior song never auto-glides).

**Detune integration.** Detune adds into `sc_base_freq` *at note-on* (FM: before the `Fm_WriteFreq` + latch in `Fm_NoteOnFreq`; PSG: before the latch + emit in `Psg_NoteOn`). Because vibrato (`Mod_Advance` reads `sc_base_freq`) and portamento (target = `sc_base_freq`) both build on the latched base, detune composes for held notes automatically — no per-frame detune cost. FM detune uses `Fm_FnumApplyDelta` (block-safe; a `+detune` at the top of block 0 would otherwise overflow fnum into the block bits). PSG detune is a plain 16-bit add to the divisor (note the sign inversion: +detune raises FM pitch but lowers PSG pitch since the divisor is the period — irrelevant for chorus, where two channels just need opposite offsets to beat).

**FM vol-env source.** S3K/skdisasm SMPS tracks carry **PSG** volume envelopes (via `sTone`/`smpsPSGvoice`) but **no FM volume-envelope coordination flag** (FM vol-env is a Flamedriver/custom-driver feature). `tools/smps_import.py` therefore has **no source to emit `MEV_FMENV` from**; Group C delivers the *engine renderer + `FmVolEnv` engine table + packer (`song_packer.py`) support + a hand-authored test phrase*, and the `smps_import.py` FM-env mapping is **deferred** (a one-line hook for the first source song that uses one). This is an honest gap, documented in Self-review — it does not block the slice (the feature is verifiable via the packer/test phrase and is forward-looking authoring capability).

## Tech Stack

- **Z80 assembler:** AS (Macroassembler), assembled inline in the 68k ROM under `phase 0`. Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → `s4.bin` (+ symbols via `convsym`; `tools/s4budget.py --summary` runs at the end via `build.sh:169`). **A plain `./build.sh` EXCLUDES all sound.**
- **Z80 code ceiling:** `Z80_SOUND_SIZE <= SND_STATE_BASE ($16F0)`, asserted at `engine/z80_sound_driver.asm:1469-1473`. This slice adds ~380–450 bytes of Z80 code (helper ~50, `Porta_Apply` ~140, `FmEnvUpdate`+`FmVolEnv_Resolve` ~80, the FM-env + detune folds/hooks ~110, three opcode handlers ~40). The F5 co-location left ~1 KB headroom, but the GLOBAL slice also spends ~300 — **check the assert + `s4budget` after EVERY Z80-code task and FLAG any overflow rather than working around it** (the shared `Fm_FnumApplyDelta` for detune+porta is load-bearing for staying under).
- **Engine lookup tables are banked at `$8000`-window bank start** (`main.asm:266-275`, `phase 08000h`), NOT in the Z80 RAM blob — the per-table "phase 0" comments in `sound_tables_z80.asm` are stale post-F5. `FmVolEnv_*` is generated alongside `PsgVolEnv_*` by `gen_sound_tables.py` → `engine/sound_tables_z80.asm`, so it lands in the same bank and `FmVolEnv_Resolve` reads it window-relative exactly like `PsgVolEnv_Resolve`. Adding it spends co-located **bank** bytes, not the `$16F0` Z80-code budget.
- **Conventions** (`CODING_CONVENTIONS.md`): sized branches (`jr`/`jp` by range — note the existing `Seq_Op_*` handlers `jp Seq_ContinueFetch`, not `jr`, because the 1D repeat handlers pushed it out of range), `struct/endstruct`, `function` for compile-time math, **no `mulu`/`divu`** (all stepping here is add/sub/shift; verified in Self-review), `phase/dephase`, the **hl-preservation rule** (push/pop `hl` around any call that clobbers the live stream ptr in an opcode handler). AS does NOT auto-align `ds.w`. Any RAM-layout change requires a runtime boot verification; this slice adds **no new RAM** (all state is reserved Phase-1 fields), so only the table/code changes need the boot check.
- **Verification = rendered AUDIO / observable behavior, never register proxies alone.** `exodus` MCP drives our ROM; `oracle` MCP for the S3K reference. **VGM captures ≤450 frames** (longer freezes the emulator). Primary tool: `tools/vgm_intranote.py` (measures intra-note fnum + carrier-TL movement — exactly the three signals here). Detune chorus is HCZ2-relevant; the HCZ2 A/B is deferred (note it). Verification uses **live `emulator_z80_write` stream/field pokes** (the GLOBAL slice's pattern for `MEV_TEMPO`) to avoid new committed content, plus optional hand-authored test phrases for thorough A/B.
- **Daemon-watched, do NOT touch:** `data/editor/**`, `tools/ojz_strip_gen.py`. `tools/smps_import.py` + `tools/song_packer.py` + `tools/gen_sound_tables.py` are **fair game**.

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `sound_constants.asm` | `MEV_PORTA`/`MEV_DETUNE`/`MEV_FMENV` opcode constants + range/fixed-slot/collision asserts | A2, B2, C3 |
| `engine/sound_sequencer.asm` | `Fm_FnumApplyDelta` helper; `Porta_Apply`; `FmEnvUpdate`; `ModUpdate` FM+PSG porta + FM-env wiring; `Seq_Op_Detune`/`Seq_Op_Porta` handlers + dispatch-table entries | A2, B1, B2, C1, C3 |
| `engine/sound_fm.asm` | `Fm_NoteOnFreq` detune add (A) + porta note-on (B) + FM-env cursor reset (C); `Fm_SetVolume` `sc_env_out` fold (C); `FmVolEnv_Resolve` | A1, B1, C1, C2 |
| `engine/sound_psg.asm` | `Psg_NoteOn` detune add (A) + porta note-on (B); `ModUpdate`-side already shared | A1, B1 |
| `engine/z80_sound_driver.asm` | `.chan_init` zero `sc_porta_incr` (+accum) | B1 |
| `engine/sound_tables_z80.asm` | GENERATED — gains `FmVolEnv_*` map + bodies | C2 |
| `tools/gen_sound_tables.py` | `_emit_fm_vol_env_z80` + `_FM_VOL_ENVS`; wire into `emit_asm_z80` | C2 |
| `tools/smps_import.py` | emit `Detune` from `smpsDetune`/`smpsAlterNote` (was dropped) | A3 |
| `tools/song_packer.py` | `Detune`/`Porta`/`FmEnv` event classes + `MEV_*` consts | A3, B3, C3 |
| `tools/test_song_packer.py`, `tools/test_smps_import.py`, `tools/test_gen_sound_tables.py` | tests for the new events/emission/table | A3, B3, C2, C3 |

No new engine files. New test-only song generators (optional) live in `data/sound/` and are run by hand.

---

## Task 0 — Read-only: confirm anchors + reserved fields + opcode coordination (no edits, no commit)

Record all of the following (with the exact file:line) in the PR description before any edit.

**Steps**
1. **Reserved porta fields exist, unused.** `sound_constants.asm:809-810` (`SeqChannel`): `sc_porta_accum ds.w 1 ; +32`, `sc_porta_incr ds.w 1 ; +34`; aliases `:896-897`. `SfxChannel` mirror `:704-705`. Confirm no reader/writer: `grep -rn "sc_porta" engine/*.asm` → only comments (`sound_sequencer.asm:129,970`).
2. **`sc_detune` at +56.** `sound_constants.asm:854` (struct), alias `:926`, range assert `:862-863`, zeroed in `.chan_init` `z80_sound_driver.asm:1223`.
3. **Unified env slot.** `sc_env`/`sc_env_cur`/`sc_env_out` alias `sc_psgenv`/`_cur`/`_out` at +39/+40/+41 (`sound_constants.asm:908-910`; struct `:832-834`); zeroed at init `z80_sound_driver.asm:1215-1217`.
4. **PSG vol-env renderer (the mirror target).** `PsgEnvUpdate` `sound_sequencer.asm:317-359` (body opcodes: `$80` loop `:327`, `$81` sustain `:329`, `$83` rest `:331`, plain delta `:333-335`; cursor `sc_psgenv_cur`, out `sc_psgenv_out`); resolver `PsgVolEnv_Resolve` `sound_psg.asm:120-140`; fold into `Psg_SetVolume` `:317-326`; cursor reset `Psg_EnvCursorReset` `:110-112`; tables `sound_tables_z80.asm:70-94`; generator `gen_sound_tables.py:_PSG_VOL_ENVS:308-327`, `_emit_psg_vol_env_z80:336-376`, wired in `emit_asm_z80:292`.
5. **Carrier-TL fold point.** `Fm_SetVolume` `sound_fm.asm:347-482`: `ld (Fm_ScratchLog),a` `:354`; duck fold `:366-381` (`.no_duck:` `:381`, music-only via `Snd_ChanClass` `:366`); per-op carrier loop `:412-481` reads `Fm_ScratchLog` as positive (`ld b,0` `:446`); `CarrierMaskTableZ` algorithm-aware `:396`; `Fm_ScratchLog = SND_FM_SCRATCH+2` `:802`.
6. **Free opcode slots + cross-plan coordination.** `SeqOpcodeTable` `sound_sequencer.asm:1190-1222`; `$F5/$F6/$F7` are `Seq_BadOpcode` (`:1212-1214`) → free. `$F3/$F4` are also free here but **the GLOBAL slice claims `$F3=MEV_TEMPO`, `$F4=MEV_LFO`** (`docs/.../2026-06-27-music-expression-phase2-global.md` Tasks B2/C1). This slice takes **`MEV_PORTA=$F5`, `MEV_DETUNE=$F6`, `MEV_FMENV=$F7`**. Coordination is by **fixed-slot asserts on BOTH sides** (each opcode `error`s unless it equals its assigned value), so the union is collision-free without a fragile cross-`ifdef`. Existing MEV assert style to mirror: `sound_constants.asm:449-466`. `Seq_ContinueFetch` `:1183-1184`. Zero-tick handler templates: `Seq_Op_NoteFill:666-670`, `Seq_Op_PsgEnv:678-683`.
7. **Note-on chokepoints.** FM: `Fm_NoteOnFreq` `sound_fm.asm:684-727` (`push de` `:688`, `Fm_WriteFreq` `:689`, `pop de` `:690`, latch `sc_base_freq` `:696-697`, `Mod_ReArm` `:698`, `.keyon:` `:699`); `Fm_WriteFreq` `:753-779`; `Fm_NoteOn` table lookup `:661-674`; `Fm_NoteFromTable` `:628-650`. PSG: `Psg_NoteOn` `sound_psg.asm:151-184` (table lookup `:152-160`, latch `:166-167`, `Psg_EmitDivisor` `:170`, `Psg_EnvCursorReset` `:174`, `Mod_ReArm` `:181`, `.skip_rearm:`+`SetVolume` `:182-184`); `Psg_EmitDivisor` `:237-273`.
8. **ModUpdate render points.** FM path `sound_sequencer.asm:170-305`: vibrato `:189-191`, `.vibrato_done:` `:192`, held-note `ret z` `:221`. PSG path `:140-169`: pitch-mod `:155-157`, `.psg_env:` `:163`, env tail-call `:166-169`.
9. **`.chan_init` does NOT zero `sc_porta_*`.** `z80_sound_driver.asm:1167-1253`; zeroes `sc_env`/`sc_detune`/`sc_mod_ctrl` `:1215-1223`. Porta zero must be added (Group B).
10. **Confirm the constants Group A/B reuse exist:** `FNUM_LO=$0284`/`FNUM_HI=$0508` `sound_constants.asm:504-505`; `SND_FM_TL_MAX=$7F` `:85`; `SND_PSG_ATTEN_SILENT=$0F` `:243`; `SCF_IS_FM_B=2` `:934`. `Snd_ChanClass` `sound_fm.asm:121-126` (CARRY set ⇒ music; clobbers af, `hl=ix`; preserves bc,de,ix).
11. **Z80 size assert + budget.** `z80_sound_driver.asm:1469-1473`; `tools/s4budget.py` (run by `build.sh:169`). Record the current headroom: build once (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`) and read the `s4budget --summary` Z80 line.
12. **Converter detune drop + packer/test surface.** `smps_import.py:627-631` (`smpsDetune`/`smpsAlterNote` → `_warn_detune_once`), `_signed8`/`resolve_const` usage `:582-584`, dropped-flag list `:269-270`. `song_packer.py` opcode consts `:40-71`, `PsgEnv` class `:211-227`, `ModSet` `:247-270`. Tests run via `python3 -m pytest tools/test_song_packer.py tools/test_smps_import.py tools/test_gen_sound_tables.py -q`.

**No commit.**

---

# Group A — Fine Detune (smallest; converter + note-on add + opcode)

## Task A1 — `Fm_FnumApplyDelta` helper + FM/PSG detune at note-on (no behavior change; detune is 0)

### Files
- `engine/sound_sequencer.asm` — new `Fm_FnumApplyDelta` (place right after `Mod_Advance`, before `Mod_ApplyVibrato`, ~line 536).
- `engine/sound_fm.asm` — `Fm_NoteOnFreq` (`:684`, before the `push de` at `:688`).
- `engine/sound_psg.asm` — `Psg_NoteOn` (after the table lookup `:160`, before the latch `:166`).

### Steps

1. **Add the shared block-safe fnum helper** in `engine/sound_sequencer.asm` after `Mod_Advance`'s `ret` (`:535`):
   ```
   ; ----------------------------------------------------------------------
   ; Fm_FnumApplyDelta — add a SIGNED 16-bit delta to the 11-bit fnum of a packed
   ; FM word, applying the SAME single-step block-boundary correction as Mod_Advance
   ; (spec §4) so the result crosses an octave seamlessly (halve fnum + block++ is the
   ; same chip pitch). Shared by fine-detune (note-on, Group A) and portamento (per-
   ; frame, Group B) so the block math exists once outside the verified Mod_Advance.
   ; In:  d = $A4 value ((block<<3)|fnumHi3), e = $A0 value (fnum low), hl = signed delta.
   ; Out: d = $A4 value, e = $A0 value (normalized). Clobbers af,bc,hl. Preserves ix.
   ; ----------------------------------------------------------------------
   Fm_FnumApplyDelta:
           ld      a, d
           rrca
           rrca
           rrca
           and     007h
           ld      c, a                     ; c = block (0..7)
           ld      a, d
           and     007h                     ; a = fnumHi3
           ld      b, a
           ld      a, e
           ex      de, hl                   ; de = signed delta; (hl free)
           ld      h, b
           ld      l, a                     ; hl = 11-bit fnum
           add     hl, de                   ; hl = fnum + delta
           ; --- hi correction: fnum >= FNUM_HI and block<7 -> fnum>>=1, block++ ----
           ld      a, c
           cp      007h
           jr      z, .lo
           ld      a, h
           cp      FNUM_HI>>8
           jr      c, .lo
           jr      nz, .hi_do
           ld      a, l
           cp      FNUM_HI&0FFh
           jr      c, .lo
   .hi_do:
           srl     h
           rr      l                        ; fnum >>= 1
           inc     c                        ; block += 1
           jr      .pack
   .lo:
           ; --- lo correction: fnum < FNUM_LO and block>0 -> fnum<<=1, block-- ------
           ld      a, c
           or      a
           jr      z, .pack
           ld      a, h
           cp      FNUM_LO>>8
           jr      c, .lo_do
           jr      nz, .pack
           ld      a, l
           cp      FNUM_LO&0FFh
           jr      nc, .pack
   .lo_do:
           add     hl, hl                   ; fnum <<= 1
           dec     c                        ; block -= 1
   .pack:
           ld      a, c
           add     a, a
           add     a, a
           add     a, a                     ; block << 3
           or      h                        ; (block<<3)|fnumHi3 (h is 0..7)
           ld      d, a                     ; d = $A4 value
           ld      e, l                     ; e = $A0 value
           ret
   ```

2. **`engine/sound_fm.asm` — FM detune at note-on.** Insert at the TOP of `Fm_NoteOnFreq`, immediately before `push de` (`:688`):
   ```
           ; --- FINE DETUNE (spec §4): add the sign-extended sc_detune to the looked-up
           ; fnum (block-corrected) BEFORE the chip write + sc_base_freq latch, so the
           ; detune carries into vibrato/portamento (both build on sc_base_freq) for free.
           ; sc_detune==0 (default / SFX / NOTE_RAW) -> skip (byte-identical no-op).
           ld      a, (ix+sc_detune)
           or      a
           jr      z, .no_detune
           ld      l, a
           add     a, a
           sbc     a, a
           ld      h, a                     ; hl = sign-extended sc_detune
           call    Fm_FnumApplyDelta        ; d/e = detuned, normalized packed word
   .no_detune:
   ```
   (Helper preserves ix; `Fm_NoteOnFreq` enters with `d=$A4,e=$A0` from `Fm_NoteOn`/`Fm_NoteFromTable`/`MEV_NOTE_RAW`; `a/bc/hl` are free here.)

3. **`engine/sound_psg.asm` — PSG detune at note-on.** Insert after the divisor lookup (`:160`, where `d`=hi, `e`=lo), before the `sc_base_freq` latch (`:166`):
   ```
           ; --- FINE DETUNE (spec §4): add the sign-extended sc_detune to the looked-up
           ; tone divisor BEFORE the latch + emit, so vibrato/portamento inherit it.
           ; PSG has no block — plain 16-bit add. NOTE the sign inversion vs FM: the
           ; divisor is the PERIOD, so +detune LOWERS PSG pitch (chorus is symmetric, so
           ; opposite-sign detune on two leads beats either way). sc_detune==0 -> skip.
           ld      a, (ix+sc_detune)
           or      a
           jr      z, .no_detune
           ld      c, a
           add     a, a
           sbc     a, a
           ld      b, a                     ; bc = sign-extended sc_detune
           ld      h, d
           ld      l, e
           add     hl, bc                   ; divisor + detune
           ld      d, h
           ld      e, l
   .no_detune:
   ```
   (`hl`/`bc` are free here — `Psg_NoteOn` clobbers af,bc,de,hl per its contract; the table ptr in `hl` from the lookup is no longer needed after `:160`.)

4. **Build:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → green; `s4budget` Z80 size `<= $16F0` (flag if over). FNUM asserts unchanged.

5. **Boot verify** (exodus): reload symbols + `s4.bin`, reset, run ~600 frames, play `SONG_MOVINGTRUCKS` → byte/spectrum-unchanged (`sc_detune==0` everywhere → the `or a / jr z` fast path is taken). Play `SONG_HCZ2` → unchanged (no `MEV_DETUNE` yet). **Manual SM check:** `emulator_z80_write` a small value (e.g. `$10`) into a music FM channel's `sc_detune` (slot base + `sc_detune` offset), trigger/await a note, capture a short VGM, and confirm via `tools/vgm_intranote.py` that the channel's keyed fnum is shifted up by the expected amount vs the same note with `sc_detune=0`; set back to `$00`.

6. **Commit:** `sound: Fm_FnumApplyDelta helper + FM/PSG fine-detune at note-on (inert; sc_detune=0)`.

---

## Task A2 — `MEV_DETUNE` ($F6) opcode

### Files
- `sound_constants.asm` — constant + asserts (near `MEV_PSGNOISE` `:366`).
- `engine/sound_sequencer.asm` — `Seq_Op_Detune` handler (after `Seq_Op_PsgNoise` `:709`) + dispatch table (`:1213`).

### Steps

1. **`sound_constants.asm` — constant + asserts** (after the `MEV_PSGNOISE` line `:366`):
   ```
   MEV_DETUNE        = $F6   ; + dd (signed) : set this channel's sc_detune (fine pitch)
           if (MEV_DETUNE <= MEV_NOTE_MAX) || (MEV_DETUNE < MEV_VOL) || (MEV_DETUNE > MEV_END)
             error "MEV_DETUNE (\{MEV_DETUNE}) must be a command opcode inside $E0-$FF"
           endif
           if MEV_DETUNE <> $F6
             error "MEV_DETUNE (\{MEV_DETUNE}) must be $F6 (per-note slice slot; GLOBAL slice owns $F3/$F4)"
           endif
   ```

2. **`engine/sound_sequencer.asm` — handler** (after `Seq_Op_PsgNoise`, before `Seq_Op_ModSet` `:711`; mirrors the `Seq_Op_NoteFill` zero-tick, state-only template — no writer hook, so `hl` stays the live stream ptr):
   ```
   ; $F6 MEV_DETUNE + dd : set the channel's signed fine-pitch detune (applied at the
   ; NEXT note-on, folded into sc_base_freq so vibrato/porta inherit it). Zero-tick;
   ; state-only -> hl stays the live stream ptr.
   Seq_Op_Detune:
           ld      a, (hl)
           inc     hl                       ; consume operand (signed detune)
           ld      (ix+sc_detune), a
           jp      Seq_ContinueFetch
   ```

3. **Dispatch table** (`sound_sequencer.asm:1213`): change `dw Seq_BadOpcode ; $F6 reserved` to:
   ```
           dw      Seq_Op_Detune            ; $F6 MEV_DETUNE
   ```

4. **Build:** green; size check; opcode asserts pass.

5. **Boot verify** (exodus): `SONG_MOVINGTRUCKS` unchanged. Exercise without new content: `emulator_z80_write` the bytes `$F6 $10` into a live music FM channel's stream just past its read ptr (or use the Task A3 packer for a throwaway phrase), and confirm `sc_detune` becomes `$10` and the next note's fnum shifts.

6. **Commit:** `sound: MEV_DETUNE ($F6) sequencer opcode (per-channel fine detune)`.

---

## Task A3 — Converter emits `Detune` from `smpsDetune`/`smpsAlterNote` + packer `Detune` event

### Files
- `tools/song_packer.py` — `MEV_DETUNE` const (near `:70`); `Detune(Event)` class (near `PsgEnv` `:211`).
- `tools/smps_import.py` — replace the drop at `:627-631`.
- `tools/test_song_packer.py`, `tools/test_smps_import.py` — tests.

### Steps

1. **`tools/song_packer.py` — opcode const** (after `MEV_PSGNOISE = 0xF2` `:70`):
   ```
   MEV_PORTA = 0xF5             # + dd: arm/set portamento glide rate (0 = off)
   MEV_DETUNE = 0xF6            # + dd (signed): set channel fine detune
   MEV_FMENV = 0xF7            # + env_id: set the channel's FM TL vol-env id (FM route)
   ```

2. **`tools/song_packer.py` — `Detune` event** (after the `PsgEnv` class `:227`):
   ```
   class Detune(Event):
       """Fine pitch detune: the engine adds the signed sc_detune to the looked-up
       fnum/divisor at the next note-on (folded into sc_base_freq so vibrato/porta
       inherit it). Sub-semitone offset for unison/chorus. FM and PSG. Zero-tick."""
       def __init__(self, detune: int):
           self.detune = detune

       def encode(self) -> bytes:
           return bytes([MEV_DETUNE, self.detune & 0xFF])

       def validate(self, route):
           if not (-128 <= self.detune <= 127):
               raise PackError(f"Detune {self.detune} out of signed byte range -128..127")
   ```
   Export it in `__all__`/the module-level names if one exists (match how `PsgEnv` is exported; grep `song_packer.py` for `PsgEnv` to find the export site and add `Detune`).

3. **`tools/smps_import.py` — emit `Detune`.** Import it: add `Detune` to the `from song_packer import (...)` block (grep the import for `PsgEnv`/`ModSet` and add `Detune`). Replace the drop body at `:627-631`:
   ```
       elif mnem in ("smpsDetune", "smpsAlterNote"):
           # cfDetune ($E1): a fine FREQUENCY detune (signed), NOT a transpose. Emit it
           # as a per-channel sc_detune (the engine folds it into the note-on fnum/
           # divisor). The engine sc_detune is a signed byte applied directly to the
           # 11-bit fnum (FM) / 10-bit divisor (PSG); the S3K cfDetune operand is the
           # same small signed quantity, so pass it through clamped to the safe range
           # (kept well inside one block so the block-correction never has to fire).
           d = _signed8(resolve_const(args[0]))
           d = max(-_DETUNE_CLAMP, min(_DETUNE_CLAMP, d))
           out.append(Detune(d))
   ```
   Add the clamp constant near `_detune_warned` (`:551`): `_DETUNE_CLAMP = 0x3F  # keep |detune| < ~half a low-octave semitone so a top-of-block fnum can't need >1 block-correction step`. (`Fm_FnumApplyDelta` is single-step, so a detune large enough to need >1 step at the table extremes would under-correct; `$3F` is safely inside one block at the lowest octave where fnum steps are smallest.) Delete `_warn_detune_once`/`_detune_warned` if now unreferenced (grep first), and remove `"smpsDetune", "smpsAlterNote"` from the dropped-flag comment list `:269-270`.

4. **Tests.**
   - `tools/test_song_packer.py`: add a test that `Detune(0x10).encode() == bytes([0xF6, 0x10])`, `Detune(-1).encode() == bytes([0xF6, 0xFF])`, and `Detune(200)` / `Detune(-200)` raise `PackError`. Import `Detune`, `MEV_DETUNE` from `song_packer`.
   - `tools/test_smps_import.py`: add a test that a `("flag","smpsDetune",["08h"])` token (and `smpsAlterNote`) produces a `Detune(8)` event in `out`, and that a large operand is clamped to `±0x3F`. (Mirror the existing `_dispatch_flag` test pattern in that file.)

5. **Run tests:** `python3 -m pytest tools/test_song_packer.py tools/test_smps_import.py -q` → green.

6. **Build + boot verify** (exodus): `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` green (HCZ2 is regenerated only if you re-run `song_hcz2.py`; if you do, confirm the new `$F6` bytes appear in `data/sound/song_hcz2.asm` for the ~10 `smpsDetune`/`smpsAlterNote` sites and the build still fits). Play `SONG_HCZ2`: the two PSG leads now carry detune → an audible chorus/beat. Capture ≤450-frame VGM; `tools/vgm_intranote.py` should show a small **constant** fnum offset between the two lead channels at the same nominal note (the beat); confirm by ear. (Full HCZ2 A/B vs S3K oracle is deferred.)

7. **Commit:** `sound(tools): emit Detune (MEV_DETUNE) from smpsDetune/smpsAlterNote + packer Detune event`.

---

# Group B — Portamento (glide; reuses the block correction)

> Depends on `Fm_FnumApplyDelta` from Group A (Task A1).

## Task B1 — `Porta_Apply` + FM/PSG porta note-on + `.chan_init` arm-clear

### Files
- `engine/z80_sound_driver.asm` — `.chan_init` (after `sc_detune` zero `:1223`).
- `engine/sound_sequencer.asm` — new `Porta_Apply` (after `Mod_ApplyVibrato` `:550`); `ModUpdate` FM path (before vibrato `:189`) + PSG path (before pitch-mod `:155`).
- `engine/sound_fm.asm` — `Fm_NoteOnFreq` porta note-on (after `Mod_ReArm` `:698`, before `.keyon:` `:699`).
- `engine/sound_psg.asm` — `Psg_NoteOn` porta note-on (after `Mod_ReArm` `:181`, before `:183`).

### Steps

1. **`engine/z80_sound_driver.asm` — `.chan_init`** (after `ld (ix+sc_detune), 0` `:1223`):
   ```
           ; portamento OFF for a fresh song (sc_porta_incr = the persistent glide rate;
           ; nonzero = armed). A stale rate from a prior song would auto-glide the first
           ; note. sc_porta_accum is seeded by the first (snapping) note-on, so it needs
           ; no init, but zero it for cleanliness/determinism.
           ld      (ix+sc_porta_incr), 0
           ld      (ix+sc_porta_incr+1), 0
           ld      (ix+sc_porta_accum), 0
           ld      (ix+sc_porta_accum+1), 0
   ```

2. **`engine/sound_sequencer.asm` — `Porta_Apply`** (after `Mod_ApplyVibrato`'s `jp Fm_WriteFreq` `:550`):
   ```
   ; ----------------------------------------------------------------------
   ; Porta_Apply — one frame of portamento glide (spec §4): step sc_porta_accum (the
   ; current sounding pitch) toward the target (sc_base_freq, latched at note-on) by
   ; sc_porta_incr (the persistent glide-rate MAGNITUDE, a byte), linear-in-fnum with
   ; the block-boundary correction (FM) or linear-in-divisor (PSG). Write-on-change.
   ; Caller-gated on sc_porta_incr != 0. While a glide is in progress this OWNS the
   ; pitch (vibrato suppressed); when accum == target it returns "done" so vibrato
   ; resumes on the held target note.
   ; In: ix = channel, sc_porta_incr != 0.
   ; Out: CARRY SET  => glide active this frame (caller skips vibrato).
   ;      CARRY CLEAR => at target (caller runs vibrato as normal).
   ; Clobbers af,bc,de,hl. Preserves ix.
   ; ----------------------------------------------------------------------
   Porta_Apply:
           bit     SCF_IS_FM_B, (ix+sc_flags)
           jr      z, .psg
           ; ===== FM glide (packed words are monotonic in pitch) =====
           ld      d, (ix+sc_porta_accum)
           ld      e, (ix+sc_porta_accum+1)  ; de = current packed word
           ld      a, (ix+sc_base_freq)
           cp      d
           jr      nz, .fm_dir
           ld      a, (ix+sc_base_freq+1)
           cp      e
           jr      nz, .fm_dir
           or      a                        ; current == target -> CF clear (done)
           ret
   .fm_dir:
           ; CF (from cp a,(target_lo) below) chooses direction: build delta in hl.
           ld      a, (ix+sc_base_freq)
           cp      d
           jr      c, .fm_down              ; target_hi < current_hi -> glide DOWN
           jr      nz, .fm_up               ; target_hi > current_hi -> glide UP
           ld      a, (ix+sc_base_freq+1)
           cp      e
           jr      c, .fm_down              ; equal hi, target_lo < current_lo -> DOWN
   .fm_up:
           ld      l, (ix+sc_porta_incr)
           ld      h, 0                     ; hl = +rate
           call    Fm_FnumApplyDelta        ; d/e = current + rate (block-normalized)
           ; overshoot up? new >= target -> snap
           ld      a, (ix+sc_base_freq)
           cp      d
           jr      c, .fm_snap              ; target_hi < new_hi -> overshot
           jr      nz, .fm_store            ; target_hi > new_hi -> not there yet
           ld      a, (ix+sc_base_freq+1)
           cp      e
           jr      c, .fm_snap
           jr      .fm_store
   .fm_down:
           ld      a, (ix+sc_porta_incr)
           neg
           ld      l, a
           sbc     a, a
           ld      h, a                     ; hl = -rate (sign-extended; rate is a byte)
           call    Fm_FnumApplyDelta        ; d/e = current - rate (block-normalized)
           ; overshoot down? new <= target -> snap
           ld      a, (ix+sc_base_freq)
           cp      d
           jr      c, .fm_store             ; target_hi < new_hi -> still above target
           jr      nz, .fm_snap             ; target_hi > new_hi -> overshot
           ld      a, (ix+sc_base_freq+1)
           cp      e
           jr      nc, .fm_snap             ; target_lo >= new_lo -> overshot/at target
   .fm_store:
           ld      (ix+sc_porta_accum), d
           ld      (ix+sc_porta_accum+1), e
           jr      .fm_emit
   .fm_snap:
           ld      d, (ix+sc_base_freq)
           ld      e, (ix+sc_base_freq+1)
           ld      (ix+sc_porta_accum), d
           ld      (ix+sc_porta_accum+1), e
   .fm_emit:
           ; write-on-change vs sc_last_freq (shared with the vibrato shadow)
           ld      a, d
           cp      (ix+sc_last_freq)
           jr      nz, .fm_write
           ld      a, e
           cp      (ix+sc_last_freq+1)
           jr      nz, .fm_write
           scf                              ; unchanged but gliding -> skip write, CF set
           ret
   .fm_write:
           ld      (ix+sc_last_freq), d
           ld      (ix+sc_last_freq+1), e
           call    Fm_WriteFreq             ; $A4/$A0, no key-on (preserves ix)
           scf                              ; glide active -> CF set
           ret
   .psg:
           ; ===== PSG glide (10-bit divisor; linear-in-divisor) =====
           ld      d, (ix+sc_porta_accum)
           ld      e, (ix+sc_porta_accum+1)  ; de = current divisor
           ld      a, (ix+sc_base_freq)
           cp      d
           jr      nz, .psg_dir
           ld      a, (ix+sc_base_freq+1)
           cp      e
           jr      nz, .psg_dir
           or      a                        ; current == target -> done
           ret
   .psg_dir:
           ld      a, (ix+sc_base_freq)
           cp      d
           jr      c, .psg_down             ; target < current -> step DOWN (toward target)
           jr      nz, .psg_up
           ld      a, (ix+sc_base_freq+1)
           cp      e
           jr      c, .psg_down
   .psg_up:
           ld      l, (ix+sc_porta_incr)
           ld      h, 0
           add     hl, de                   ; current + rate
           ; overshoot? new >= target -> snap
           ld      a, (ix+sc_base_freq)
           cp      h
           jr      c, .psg_snap
           jr      nz, .psg_have
           ld      a, (ix+sc_base_freq+1)
           cp      l
           jr      c, .psg_snap
   .psg_have:
           ld      d, h
           ld      e, l
           jr      .psg_store
   .psg_down:
           ld      a, e
           sub     (ix+sc_porta_incr)
           ld      l, a
           ld      a, d
           sbc     a, 0
           ld      h, a                     ; hl = current - rate
           ; overshoot? new <= target -> snap
           ld      a, (ix+sc_base_freq)
           cp      h
           jr      c, .psg_have2            ; target_hi < new_hi -> still above target
           jr      nz, .psg_snap
           ld      a, (ix+sc_base_freq+1)
           cp      l
           jr      nc, .psg_snap
   .psg_have2:
           ld      d, h
           ld      e, l
           jr      .psg_store
   .psg_snap:
           ld      d, (ix+sc_base_freq)
           ld      e, (ix+sc_base_freq+1)
   .psg_store:
           ld      (ix+sc_porta_accum), d
           ld      (ix+sc_porta_accum+1), e
           ld      a, d
           cp      (ix+sc_last_freq)
           jr      nz, .psg_write
           ld      a, e
           cp      (ix+sc_last_freq+1)
           jr      nz, .psg_write
           scf
           ret
   .psg_write:
           ld      (ix+sc_last_freq), d
           ld      (ix+sc_last_freq+1), e
           call    Psg_EmitDivisor          ; re-latch divisor (d=hi,e=lo); preserves hl,ix
           scf
           ret
   ```

3. **`engine/sound_sequencer.asm` — ModUpdate FM path.** Replace the vibrato block (`:189-192`):
   ```
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Mod_ApplyVibrato     ; advance + write-on-change $A4/$A0 (no key-on)
   .vibrato_done:
   ```
   with (porta first; suppress vibrato while a glide is active):
   ```
           ; --- PORTAMENTO (spec §4): a glide owns the pitch (suppresses vibrato);
           ; once at target it falls through so a held note still vibratos. Armed
           ; channels only (sc_porta_incr != 0) pay more than one test.
           ld      a, (ix+sc_porta_incr)
           or      (ix+sc_porta_incr+1)
           jr      z, .no_porta
           call    Porta_Apply              ; CF set => glide active -> skip vibrato
           jr      c, .vibrato_done
   .no_porta:
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Mod_ApplyVibrato     ; advance + write-on-change $A4/$A0 (no key-on)
   .vibrato_done:
   ```

4. **`engine/sound_sequencer.asm` — ModUpdate PSG path.** Replace the pitch-mod block (`:155-157`):
   ```
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Psg_ApplyMod         ; advance accum + re-latch tone divisor (no re-key)
   ```
   with:
   ```
           ; --- PORTAMENTO (PSG, spec §4): same gate/own-pitch model as FM. ---
           ld      a, (ix+sc_porta_incr)
           or      (ix+sc_porta_incr+1)
           jr      z, .no_psg_porta
           call    Porta_Apply              ; CF set => glide active -> skip pitch-mod
           jr      c, .psg_env
   .no_psg_porta:
           ld      a, (ix+sc_mod_ctrl)
           or      a
           call    nz, Psg_ApplyMod         ; advance accum + re-latch tone divisor (no re-key)
   ```
   (`.psg_env:` is the existing label `:163`; the porta-active branch skips both pitch-mod and lets the env still run via the normal fall-through — correct, since `jr c,.psg_env` lands exactly where the no-porta path falls to.)

5. **`engine/sound_fm.asm` — FM porta note-on.** Insert after `Mod_ReArm` (`:698`), before `.keyon:` (`:699`):
   ```
           ; --- PORTAMENTO note-on (spec §4): if a glide rate is armed, ATTACK at the
           ; current slid pitch (sc_porta_accum) and glide to the target (sc_base_freq,
           ; just latched); else SNAP sc_porta_accum = target (normal attack; seeds the
           ; next glide's start). de currently = the (detuned) target word.
           ld      a, (ix+sc_porta_incr)
           or      (ix+sc_porta_incr+1)
           jr      z, .porta_snap
           ld      d, (ix+sc_porta_accum)
           ld      e, (ix+sc_porta_accum+1)  ; de = start pitch (old)
           ld      (ix+sc_last_freq), d
           ld      (ix+sc_last_freq+1), e    ; prime write-on-change shadow to the start
           call    Fm_WriteFreq             ; re-write $A4/$A0 = start (no key-on); preserves ix
           jr      .keyon
   .porta_snap:
           ld      d, (ix+sc_base_freq)
           ld      e, (ix+sc_base_freq+1)
           ld      (ix+sc_porta_accum), d
           ld      (ix+sc_porta_accum+1), e  ; accum = target (no glide)
   .keyon:
   ```
   (After this re-write, the key-on at `.do_keyon`/`.keyon` keys the EG at the START pitch; `Porta_Apply` then glides on subsequent frames. `Fm_WriteFreq` clobbers af,bc,de,hl, preserves ix — fine here, `de` is reloaded as needed and `hl` is not live.)

6. **`engine/sound_psg.asm` — PSG porta note-on.** Insert after `Mod_ReArm` (`:181`), before `ld a,(ix+sc_volume)` (`:183`):
   ```
           ; --- PORTAMENTO note-on (PSG, spec §4): attack at sc_porta_accum + glide,
           ; or snap accum = target. de = the (detuned) target divisor at this point?
           ; No — reload from sc_base_freq (Psg_EmitDivisor/Mod_ReArm clobbered de).
           ld      a, (ix+sc_porta_incr)
           or      (ix+sc_porta_incr+1)
           jr      z, .porta_snap
           ld      d, (ix+sc_porta_accum)
           ld      e, (ix+sc_porta_accum+1)
           ld      (ix+sc_last_freq), d
           ld      (ix+sc_last_freq+1), e
           call    Psg_EmitDivisor          ; re-latch start divisor (no re-key); preserves hl,ix
           jr      .porta_done
   .porta_snap:
           ld      d, (ix+sc_base_freq)
           ld      e, (ix+sc_base_freq+1)
           ld      (ix+sc_porta_accum), d
           ld      (ix+sc_porta_accum+1), e
   .porta_done:
   ```
   (Then the existing `:183` `ld a,(ix+sc_volume)` / `jp Psg_SetVolume` runs. `Psg_EmitDivisor` clobbers af,bc,de; `a` is reloaded at `:183`.)

7. **Build:** green; **`s4budget` Z80 size `<= $16F0` (flag if over — this is the largest task; if it overflows, that is the budget signal).**

8. **Boot verify** (exodus): `SONG_MOVINGTRUCKS` byte/spectrum-unchanged (`sc_porta_incr==0` → the `or` fast path skips `Porta_Apply`, and note-on snaps). **Manual SM glide test:** on a music FM channel, `emulator_z80_write` `sc_porta_incr` = e.g. `$08` (lo) `$00` (hi), then trigger two different notes (poke `$F5 $08` + a note opcode into the stream, or set the rate field + let two stream notes play); capture a ≤450-frame VGM spanning both notes; `tools/vgm_intranote.py` must show the fnum **sweeping smoothly across intermediate values** between the two key-ons (not a single jump), and a glide spanning ≥1 octave must be **continuous** (no octave pop — the block correction). Repeat on a PSG channel (divisor sweeps).

9. **Commit:** `sound: portamento glide (Porta_Apply, FM+PSG) + porta note-on + .chan_init arm-clear`.

---

## Task B2 — `MEV_PORTA` ($F5) opcode

### Files
- `sound_constants.asm` — constant + asserts.
- `engine/sound_sequencer.asm` — `Seq_Op_Porta` + dispatch table (`:1212`).

### Steps

1. **`sound_constants.asm`** (after the `MEV_DETUNE` block from A2):
   ```
   MEV_PORTA         = $F5   ; + dd : set the portamento glide rate (fnum/divisor units
                             ;        per frame); 0 = OFF (notes snap)
           if (MEV_PORTA <= MEV_NOTE_MAX) || (MEV_PORTA < MEV_VOL) || (MEV_PORTA > MEV_END)
             error "MEV_PORTA (\{MEV_PORTA}) must be a command opcode inside $E0-$FF"
           endif
           if (MEV_PORTA <> $F5) || (MEV_PORTA = MEV_DETUNE)
             error "MEV_PORTA (\{MEV_PORTA}) must be $F5 (distinct from MEV_DETUNE; GLOBAL slice owns $F3/$F4)"
           endif
   ```

2. **`engine/sound_sequencer.asm` — handler** (near `Seq_Op_Detune`):
   ```
   ; $F5 MEV_PORTA + dd : set the persistent portamento glide-rate magnitude (the per-
   ; frame fnum/divisor step; 0 = off -> notes snap). The next porta-armed note keeps
   ; the current pitch as the glide start. Zero-tick; state-only -> hl stays the stream
   ; ptr. The rate is a byte (high byte forced 0) — Porta_Apply assumes hi==0.
   Seq_Op_Porta:
           ld      a, (hl)
           inc     hl                       ; consume operand (rate)
           ld      (ix+sc_porta_incr), a
           ld      (ix+sc_porta_incr+1), 0
           jp      Seq_ContinueFetch
   ```

3. **Dispatch table** (`sound_sequencer.asm:1212`): `dw Seq_BadOpcode ; $F5 reserved` →
   ```
           dw      Seq_Op_Porta             ; $F5 MEV_PORTA
   ```

4. **Build:** green; size check; opcode asserts pass.

5. **Boot verify** (exodus): `SONG_MOVINGTRUCKS` unchanged. Poke `$F5 $08` into a live stream and confirm `sc_porta_incr` becomes `$0008` and the next note glides.

6. **Commit:** `sound: MEV_PORTA ($F5) sequencer opcode (portamento glide rate)`.

---

## Task B3 — Packer `Porta` event

### Files
- `tools/song_packer.py` — `Porta(Event)` (near `Detune`).
- `tools/test_song_packer.py` — test.

### Steps

1. **`tools/song_packer.py`** (`MEV_PORTA` const already added in A3 step 1):
   ```
   class Porta(Event):
       """Portamento: set the glide rate (fnum/divisor units per frame; 0 = off). The
       engine glides each new note from the previous pitch to the new one. FM and PSG.
       Must follow at least one normal note on the channel (seeds the glide start).
       Zero-tick."""
       def __init__(self, rate: int):
           self.rate = rate

       def encode(self) -> bytes:
           return bytes([MEV_PORTA, self.rate & 0xFF])

       def validate(self, route):
           if not (0 <= self.rate <= 0xFF):
               raise PackError(f"Porta rate {self.rate} out of byte range 0..255")
   ```
   Export `Porta` alongside `Detune`.

2. **Test** (`tools/test_song_packer.py`): `Porta(8).encode() == bytes([0xF5, 8])`; `Porta(300)` raises `PackError`.

3. **Run tests:** `python3 -m pytest tools/test_song_packer.py -q` → green.

4. **Commit:** `sound(tools): packer Porta event (MEV_PORTA)`.

> **Converter note (documented):** S3K `cfPortamento`/slide is `smpsModSet`-driven (already imported as `ModSet`/vibrato) rather than a discrete glide flag, so `smps_import.py` is **not** changed for portamento in this slice — `MEV_PORTA` is authored via the packer/test phrases (and is available for any future source mapping). Flagged in Self-review.

---

# Group C — FM TL Volume-Envelope (mirror the PSG vol-env onto carriers)

> **⚠ SUPERSEDED 2026-06-27 — DO NOT BUILD.** Absorbed into the Phase 3 macro/automation-spine spec (`docs/superpowers/specs/2026-06-27-music-expr-macro-spine-design.md` §4) as the *volume* macro target's renderer. `MEV_FMENV=$F7` is now owned by Phase 3. Tasks C1–C4 below are retained for reference only — building them here AND in Phase 3 collides on the `$F7` fixed-slot assert.

## Task C1 — `Fm_SetVolume` env fold + `FmEnvUpdate` + ModUpdate wiring + FM env cursor reset (inert; sc_env=0)

### Files
- `engine/sound_fm.asm` — `Fm_SetVolume` fold (after `ld (Fm_ScratchLog),a` `:354`); `Fm_NoteOnFreq` cursor reset (in the FM porta block / before `.keyon` `:699`).
- `engine/sound_sequencer.asm` — `FmEnvUpdate` (place near `PsgEnvUpdate`, after `:359`); `ModUpdate` FM path wiring (after `.vibrato_done` `:192`).

### Steps

1. **`engine/sound_fm.asm` — fold `sc_env_out` into `Fm_ScratchLog`.** Insert immediately after `ld (Fm_ScratchLog), a` (`:354`), BEFORE the duck block (`:356`):
   ```
           ; --- FM TL VOLUME ENVELOPE (spec §5): add the per-frame env attenuation delta
           ; to the carrier-TL delta (mirror of Psg_SetVolume's env fold, sound_psg.asm).
           ; Folded HERE (before the duck/master-fade fold) so all three compose; the
           ; per-op carrier loop reads Fm_ScratchLog as a positive 0..$7F delta, so we
           ; clamp to $7F. sc_env_out is the unified slot (=sc_psgenv_out); 0 on a no-env
           ; channel -> the or a/jr z fast path is byte-identical to no envelope. Applies
           ; to carriers ONLY for free (Fm_ScratchLog only reaches carrier ops).
           ld      a, (ix+sc_env_out)
           or      a
           jr      z, .env_done
           ld      hl, Fm_ScratchLog
           add     a, (hl)                  ; env delta + log delta
           jr      nc, .env_ok
           ld      a, SND_FM_TL_MAX         ; carry -> clamp to $7F (silent)
   .env_ok:
           cp      SND_FM_TL_MAX+1
           jr      c, .env_store
           ld      a, SND_FM_TL_MAX
   .env_store:
           ld      (hl), a
   .env_done:
   ```

2. **`engine/sound_sequencer.asm` — `FmEnvUpdate`** (mirror of `PsgEnvUpdate`; place right after `PsgEnvUpdate`'s `.rest` `jp Psg_NoteOff` `:359`):
   ```
   ; ----------------------------------------------------------------------
   ; FmEnvUpdate — advance one FM channel's carrier-TL volume-envelope contour by one
   ; frame and re-emit the channel volume so the new attenuation delta takes effect
   ; (folded into Fm_SetVolume's Fm_ScratchLog). The FM mirror of PsgEnvUpdate; the
   ; UNIFIED sc_env/sc_env_cur/sc_env_out slot serves FM (here) xor PSG (PsgEnvUpdate).
   ; Body bytes (mirror PSG): plain value -> sc_env_out + advance; $80 -> loop cursor
   ; to 0; $81 -> sustain-hold (keep last out, no advance); $83 -> TL-silence the tail
   ; (sc_env_out = $7F, park the cursor) — NOTE the deviation from PSG's key-off: FM
   ; has its own EG, so a key-off would cut the release; TL-silence preserves it.
   ; In: ix = FM channel, sc_env != 0. Clobbers af,bc,de,hl. Preserves ix.
   ; ----------------------------------------------------------------------
   FmEnvUpdate:
           ld      a, (ix+sc_env)
           call    FmVolEnv_Resolve         ; hl = body base; CF set = unknown id -> bail
           ret     c
   .reread:
           ld      a, (ix+sc_env_cur)
           ld      e, a
           ld      d, 0
           add     hl, de                   ; hl = &body[cursor]
           ld      a, (hl)
           cp      FmVolEnvCtl_Loop         ; $80
           jr      z, .loop
           cp      FmVolEnvCtl_Sustain      ; $81
           jr      z, .sustain
           cp      FmVolEnvCtl_Rest         ; $83
           jr      z, .rest
           ld      (ix+sc_env_out), a       ; plain value = carrier-TL atten delta
           inc     (ix+sc_env_cur)
   .emit:
           ld      a, (ix+sc_volume)
           jp      Fm_SetVolume             ; folds sc_env_out into the carrier TLs (preserves ix)
   .loop:
           ld      (ix+sc_env_cur), 0
           ld      a, (ix+sc_env)
           call    FmVolEnv_Resolve
           ret     c
           jr      .reread
   .sustain:
           jr      .emit
   .rest:
           ld      (ix+sc_env_out), SND_FM_TL_MAX   ; TL-silence (no key-off; parks cursor)
           jr      .emit
   ```
   (`FmVolEnvCtl_*` and `FmVolEnv_Resolve` come from Tasks C2/C3; assemble C2 first or define the ctl constants in C2. Sequence: do C2 — table + `FmVolEnv_Resolve` — then C1's `FmEnvUpdate` resolves. **Re-order Task execution C2 → C1 → C3, OR define `FmVolEnvCtl_*`/`FmVolEnv_Resolve` as part of C2 and reference here.** This plan documents the dependency: `FmEnvUpdate` references `FmVolEnv_Resolve`+`FmVolEnvCtl_*`, so land C2 first.)

3. **`engine/sound_sequencer.asm` — ModUpdate FM path wiring.** Insert immediately after `.vibrato_done:` (`:192`):
   ```
           ; --- FM TL VOLUME ENVELOPE (spec §5): advance the carrier-TL contour + re-
           ; emit volume (folds sc_env_out in Fm_SetVolume). Runs every frame (held notes
           ; too) so the swell/tremolo evolves. sc_env==0 -> one test, skip.
           ld      a, (ix+sc_env)
           or      a
           call    nz, FmEnvUpdate          ; advance + re-emit carrier TLs (preserves ix)
   ```

4. **`engine/sound_fm.asm` — reset the FM env cursor on attack.** In `Fm_NoteOnFreq`, add to BOTH the `.porta_snap` and the porta-glide branches (or simplest: once, right after the porta block, before `.keyon:`):
   ```
           ld      (ix+sc_env_cur), 0       ; restart the FM vol-env contour on this attack
   ```
   (Mirrors `Psg_EnvCursorReset`; harmless when `sc_env==0`. Place it just before the `.keyon:` label so every FM attack — snap or glide — resets the contour.)

5. **Build:** (after C2 lands) green; size check.

6. **Boot verify** (exodus): `SONG_MOVINGTRUCKS` byte/spectrum-unchanged (`sc_env==0` → fast path; the `Fm_ScratchLog` fold's `or a/jr z` is byte-identical to no envelope). Deferred to Task C4 for the audible env test.

7. **Commit:** `sound: FM TL vol-env renderer (FmEnvUpdate) + Fm_SetVolume fold + ModUpdate wiring`.

---

## Task C2 — `FmVolEnv_*` engine table (generator) + `FmVolEnv_Resolve`

### Files
- `tools/gen_sound_tables.py` — `_FM_VOL_ENVS` + `_emit_fm_vol_env_z80` + wire into `emit_asm_z80` (`:292`).
- `engine/sound_tables_z80.asm` — GENERATED output (do not hand-edit; regenerate).
- `engine/sound_psg.asm` — `FmVolEnv_Resolve` (place next to `PsgVolEnv_Resolve` `:120-140`).
- `tools/test_gen_sound_tables.py` — table test.

### Steps

1. **`tools/gen_sound_tables.py` — FM env bodies + emitter.** After `_PSG_VOL_ENVS` (`:327`), add a minimal but representative engine-default FM vol-env set (attenuation deltas, same control-byte format as PSG — `$80` loop / `$81` sustain / `$83` rest):
   ```
   # --- FM TL volume-envelope table (spec §5; the Flamedriver zDoFMVolEnv analogue) --
   # Same byte format as the PSG vol-env: per-frame CARRIER-TL attenuation deltas
   # (higher = quieter) + $80 loop / $81 sustain-hold / $83 rest (TL-silence). Engine
   # id is 1-based. These are ENGINE DEFAULTS for authoring (S3K has no FM vol-env to
   # import); add more as songs need them.
   _FM_VOL_ENVS = [
       # id    label         body
       (0x01, "fmEnv_swell",   [0x20, 0x18, 0x12, 0x0C, 0x08, 0x05, 0x02, 0x00,
                                _CTL_SUSTAIN]),                 # swell-IN: loud->bright, hold
       (0x02, "fmEnv_decay",   [0x00, 0x02, 0x04, 0x06, 0x08, 0x0C, 0x10, 0x18,
                                _CTL_SUSTAIN]),                 # decay: bright->quiet, hold
       (0x03, "fmEnv_trem",    [0x00, 0x02, 0x04, 0x06, 0x04, 0x02,
                                _CTL_LOOP]),                    # tremolo: oscillate, loop
   ]
   ```
   Add `_emit_fm_vol_env_z80()` mirroring `_emit_psg_vol_env_z80()` (`:336-376`) but with `FmVolEnv`/`FmVolEnvCtl_` labels and `_FM_VOL_ENVS`:
   ```
   def _emit_fm_vol_env_z80() -> list:
       out = []
       out.append("; --- FM TL volume-envelope table (spec section 5) ---------------------------")
       out.append("; Same format as the PSG vol-env (atten deltas + 80h/81h/83h ctl) but the")
       out.append("; renderer (FmEnvUpdate) folds the delta into the CARRIER TLs (Fm_SetVolume).")
       out.append("FmVolEnvCtl_Loop    = 80h")
       out.append("FmVolEnvCtl_Sustain = 81h")
       out.append("FmVolEnvCtl_Rest    = 83h")
       out.append("")
       ids  = ", ".join(_z80_byte(e[0]) for e in _FM_VOL_ENVS)
       ptrs = ", ".join("FmVolEnv_%02X" % e[0] for e in _FM_VOL_ENVS)
       out.append("FmVolEnv_Ids:    db %s" % ids)
       out.append("FmVolEnv_Ids_End:")
       out.append("FmVolEnv_Ptrs:   dw %s" % ptrs)
       out.append("FmVolEnv_Ptrs_End:")
       out.append("")
       out.append("FMVOLENV_COUNT = FmVolEnv_Ids_End - FmVolEnv_Ids")
       out.append("        if (FmVolEnv_Ptrs_End - FmVolEnv_Ptrs) <> FMVOLENV_COUNT*2")
       out.append('          error "FmVolEnv_Ptrs entry count mismatch vs FmVolEnv_Ids"')
       out.append("        endif")
       out.append("")
       for env_id, label, body in _FM_VOL_ENVS:
           toks = ", ".join(
               {_CTL_LOOP: "FmVolEnvCtl_Loop",
                _CTL_SUSTAIN: "FmVolEnvCtl_Sustain",
                _CTL_REST: "FmVolEnvCtl_Rest"}.get(b, _z80_byte(b))
               for b in body)
           out.append("FmVolEnv_%02X:   db %s   ; %s" % (env_id, toks, label))
       out.append("")
       return out
   ```
   Wire it into `emit_asm_z80()` after the PSG env append (`:292`): `out.extend(_emit_fm_vol_env_z80())`.

2. **Regenerate:** `python3 tools/gen_sound_tables.py` → rewrites `engine/sound_tables_z80.asm` (and `data/sound/sound_tables.asm`). Confirm `FmVolEnv_Ids`/`FmVolEnv_Ptrs`/`FmVolEnv_01..03` + `FMVOLENV_COUNT` appear after the PSG env block (same `phase 08000h` bank).

3. **`engine/sound_psg.asm` — `FmVolEnv_Resolve`** (mirror `PsgVolEnv_Resolve` `:120-140`; place right after it):
   ```
   ; ----------------------------------------------------------------------
   ; FmVolEnv_Resolve — map a 1-based FM vol-env id (a) to its body ptr (hl) via the
   ; FmVolEnv_Ids/FmVolEnv_Ptrs parallel arrays (engine/sound_tables_z80.asm, banked
   ; $8000 window). The FM mirror of PsgVolEnv_Resolve.
   ; Out: carry clear + hl = body base on match; carry set on unknown id.
   ; In: a = 1-based env id. Clobbers af,bc,de,hl. Preserves ix.
   ; ----------------------------------------------------------------------
   FmVolEnv_Resolve:
           ld      b, FMVOLENV_COUNT
           ld      hl, FmVolEnv_Ids
           ld      de, FmVolEnv_Ptrs
   .scan:
           cp      (hl)
           jr      z, .found
           inc     hl
           inc     de
           inc     de
           djnz    .scan
           scf
           ret
   .found:
           ex      de, hl
           ld      e, (hl)
           inc     hl
           ld      d, (hl)
           ex      de, hl
           or      a
           ret
   ```
   (Placed in `sound_psg.asm` next to `PsgVolEnv_Resolve` for locality, but `FmEnvUpdate` lives in `sound_sequencer.asm` — cross-file `call FmVolEnv_Resolve` is fine, same as `PsgEnvUpdate` calling `PsgVolEnv_Resolve` cross-file.)

4. **Test** (`tools/test_gen_sound_tables.py`): assert the generated `engine/sound_tables_z80.asm` contains `FmVolEnv_Ids:`, `FmVolEnv_Ptrs:`, `FMVOLENV_COUNT`, and `FmVolEnv_01`/`_02`/`_03` bodies with the expected ctl tokens; assert `len(_FM_VOL_ENVS)` ids == ptrs.

5. **Build:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` green; the `FmVolEnv_Ptrs` count assert + size assert pass; `s4budget` Z80 size `<= $16F0` (the table is in the co-located bank, not the Z80 code, but `FmVolEnv_Resolve`+`FmEnvUpdate` are Z80 code — check).

6. **Boot verify** (exodus): `SONG_MOVINGTRUCKS` unchanged.

7. **Commit:** `sound: FmVolEnv engine table (gen_sound_tables) + FmVolEnv_Resolve`.

---

## Task C3 — `MEV_FMENV` ($F7) opcode + packer `FmEnv` event

### Files
- `sound_constants.asm` — constant + asserts.
- `engine/sound_sequencer.asm` — dispatch table (`:1214`) → shared `Seq_Op_PsgEnv`.
- `tools/song_packer.py` — `FmEnv(Event)` (near `PsgEnv`).
- `tools/test_song_packer.py` — test.

### Steps

1. **`sound_constants.asm`** (after the `MEV_PORTA` block):
   ```
   MEV_FMENV         = $F7   ; + env_id : set the channel's FM TL vol-env id (FM route;
                             ;            shares the unified sc_env slot with MEV_PSGENV)
           if (MEV_FMENV <= MEV_NOTE_MAX) || (MEV_FMENV < MEV_VOL) || (MEV_FMENV > MEV_END)
             error "MEV_FMENV (\{MEV_FMENV}) must be a command opcode inside $E0-$FF"
           endif
           if (MEV_FMENV <> $F7) || (MEV_FMENV = MEV_PORTA) || (MEV_FMENV = MEV_DETUNE)
             error "MEV_FMENV (\{MEV_FMENV}) must be $F7 (distinct from MEV_PORTA/MEV_DETUNE)"
           endif
   ```

2. **Dispatch table** (`sound_sequencer.asm:1214`): `dw Seq_BadOpcode ; $F7 reserved` →
   ```
           dw      Seq_Op_PsgEnv            ; $F7 MEV_FMENV (shared handler: sets the
                                            ;   unified sc_env slot + resets sc_env_cur;
                                            ;   ModUpdate picks FmVolEnv vs PsgVolEnv by route)
   ```
   (No new handler: `Seq_Op_PsgEnv` `:678-683` writes `sc_psgenv`(=`sc_env`) + `sc_psgenv_cur`(=`sc_env_cur`) — exactly what an FM-env arm needs. The env-id namespace differs (FmVolEnv ids) but the renderer resolves by route. Documented in the dispatch comment + Self-review.)

3. **`tools/song_packer.py` — `FmEnv` event** (after `PsgEnv` `:227`; `MEV_FMENV` const added in A3):
   ```
   class FmEnv(Event):
       """FM TL volume envelope: set the channel's 1-based FM vol-env id (0 = none). The
       engine restarts the contour on each FM attack and folds the per-frame carrier-TL
       attenuation delta into Fm_SetVolume. FM routes only. Body bytes live in the
       engine's FmVolEnv table (gen_sound_tables.py). Mirrors PsgEnv."""
       def __init__(self, env_id: int):
           self.env_id = env_id

       def encode(self) -> bytes:
           return bytes([MEV_FMENV, self.env_id & 0xFF])

       def validate(self, route):
           if route not in _FM_ROUTES:
               raise PackError(f"FmEnv on non-FM route {route}")
           if not (0 <= self.env_id <= 0xFF):
               raise PackError(f"FmEnv env_id {self.env_id} out of byte range")
   ```
   Export `FmEnv`. (`_FM_ROUTES` already exists — used by `PsgEnv.validate` `:224`.)

4. **Test** (`tools/test_song_packer.py`): `FmEnv(1).encode() == bytes([0xF7, 1])`; `FmEnv` on a PSG route raises `PackError`; `FmEnv` on an FM route validates.

5. **Run tests:** `python3 -m pytest tools/test_song_packer.py -q` → green.

6. **Build:** green; opcode asserts pass; size check.

7. **Boot verify** (exodus): `SONG_MOVINGTRUCKS` unchanged. Poke `$F7 $01` + an FM note into a live stream and confirm `sc_env` becomes `1`; full audible check in C4.

8. **Commit:** `sound: MEV_FMENV ($F7) opcode (shared sc_env handler) + packer FmEnv event`.

---

## Task C4 — Verify FM TL vol-env by rendered audio

### Steps
1. Build DEBUG ROM; reload symbols in **exodus**.
2. Author a tiny test phrase (a `data/sound/song_fmenvtest.py` mirroring `song_pitchtest.py`: one FM channel, `Patch`, `FmEnv(1)` (swell) then a long held note, looping), regenerate its `.asm`, wire it into `song_table.asm` as a DEBUG-only id, and point the DEBUG boot at it — OR, to stay content-free, `emulator_z80_write` `sc_env=1` on a held music FM channel mid-playback.
3. **Audio check (the rule):** capture a ≤450-frame VGM of a held FM note with `sc_env=1`. `tools/vgm_intranote.py` must report **carrier-TL movement between key-ons** (the swell: TL falling, i.e. brightening, over the held note) — confirm the intra-note TL delta tracks the `fmEnv_swell` body. Switch to `sc_env=3` (`fmEnv_trem`) and confirm **oscillating** carrier TL at the loop period. Confirm modulator TLs do NOT move (carrier-only via `CarrierMaskTableZ`). Confirm by ear (swell / tremolo).
4. **Compose-with-detune/porta spot check:** with `sc_env` + `sc_detune` set, confirm the note is both detuned (constant fnum offset) and swelling (TL contour) — independent axes.
5. **Regression:** `SONG_MOVINGTRUCKS` byte/spectrum-faithful (all `sc_env==0`); DEBUG boot self-test green. `SONG_HCZ2` PSG vol-envs unaffected (the shared slot is FM-xor-PSG; HCZ2 PSG channels still run `PsgEnvUpdate`).
6. **Commit** (notes only): `sound: verify FM TL vol-env (intra-note carrier-TL swell + tremolo)`. Record the `vgm_intranote` TL-movement numbers in the PR.

---

## Self-review

**Spec coverage (this slice):**
- ✅ **Fine detune** — `sc_detune` (+56, reserved Phase 1) sign-extended into the looked-up fnum (FM, block-corrected via `Fm_FnumApplyDelta`) / divisor (PSG) at note-on, folded into `sc_base_freq` so vibrato/porta inherit it (spec §4). Converter emits it from `smpsDetune`/`smpsAlterNote` (was dropped, `smps_import.py:627-631`); `MEV_DETUNE=$F6`.
- ✅ **Portamento** — linear-in-fnum, add-only glide (FM+PSG) reusing `sc_porta_accum` (+32) / `sc_porta_incr` (+34, as the persistent rate) + Phase-1's block correction (shared `Fm_FnumApplyDelta`); `MEV_PORTA=$F5`; **zero new struct bytes** (spec §4).
- ✅ **FM TL vol-env** — `FmEnvUpdate` mirrors `PsgEnvUpdate` ($80/$81/$83/plain), unified `sc_env` slot, `sc_env_out` folded into the carrier-TL `Fm_ScratchLog` (the duck/master-fade seam, carrier-mask aware), resolved via `FmVolEnv_*` mirroring `PsgVolEnv_*`; `MEV_FMENV=$F7` (spec §5).
- ✅ Out-of-scope items (fade/tempo/LFO, SSG-EG, MEV_REGWRITE, macro spine, DAC, vibrato) untouched.

**No placeholders:** every step has exact asm/Python/constant text + exact build/verify commands.

**Struct-offset + opcode-number consistency (incl. cross-plan MEV collision):** `sc_porta_accum`=+32/`sc_porta_incr`=+34/`sc_detune`=+56/`sc_env*`=+39..41 confirmed (`sound_constants.asm:809-810,854,908-910`) — **no struct growth, no RAM change**. New opcodes `MEV_PORTA=$F5`/`MEV_DETUNE=$F6`/`MEV_FMENV=$F7` are all `Seq_BadOpcode` slots today (`:1212-1214`); each has a **fixed-slot `error` assert**, and the GLOBAL slice fixes `$F3/$F4` the same way, so the union is collision-free **by construction** (no fragile cross-`ifdef`) — documented as the coordination mechanism. Packer `MEV_*` consts mirror the asm (`song_packer.py`).

**FM-xor-PSG `sc_env`-slot sharing hazard:** addressed — a channel sets `SCF_IS_FM_B` xor `SCF_IS_PSG_B`, and `ModUpdate` routes to `FmEnvUpdate` (FM path) xor `PsgEnvUpdate` (PSG path); `MEV_FMENV` and `MEV_PSGENV` write the *same* slot via the shared `Seq_Op_PsgEnv`, and the renderer picks `FmVolEnv` vs `PsgVolEnv` by route, so the id namespaces never cross. Init already zeroes the slot (`z80_sound_driver.asm:1215-1217`). The packer validates `FmEnv`→FM-route, `PsgEnv`→PSG-route, so a stream can't put an FM id on a PSG channel.

**No-multiply check:** all detune/porta/env arithmetic is add/sub/shift (`add a,a`/`sbc a,a` sign-extend; `srl`/`rr`/`add hl,hl` block correction; `add hl,de`/`sub`/`sbc` stepping). No `mulu`/`divu`. Linear-in-fnum (FM) / linear-in-divisor (PSG) is the deliberate add-only choice (spec §2 rejects division-based glide).

**Budget:** ~380–450 Z80 bytes added; the FM `FmVolEnv` table is in the co-located `$8000` bank, not the Z80 code. The `$16F0` ceiling and `s4budget` are checked after **every** Z80-code task (A1, B1, B2, C1, C2) and overflow is **flagged, not worked around**. If both Phase-2 slices land (~300 from GLOBAL), re-check headroom; the shared `Fm_FnumApplyDelta` (detune+porta) is the key economy.

**OPEN questions / documented deviations (flagged, not guessed):**
1. **Porta+vibrato are sequential, not summed** — porta owns the pitch during a glide and vibrato resumes at glide-end. Full simultaneous summation needs a second accumulator = new struct bytes (not reserved in Phase 1). Acceptable for short glides; revisit if a song needs glide-with-vibrato.
2. **`sc_porta_incr` repurposed as the persistent rate** (not zeroed on completion; completion = `accum==target`). Deliberate refinement of the spec's "zero on completion," needed because only two porta fields were reserved and no arm-flag bit exists. The converter/composer must seed `sc_porta_accum` with a normal note before the first `MEV_PORTA`.
3. **FM `$83` rest = TL-silence, not key-off** (PSG's rest keys off). FM has its own EG; a key-off would cut the release. Deviation documented in `FmEnvUpdate`.
4. **No `smps_import.py` source for FM vol-env or portamento** — S3K SMPS has no FM-vol-env flag, and its slides are `smpsModSet`-driven (already imported as vibrato). Group C delivers engine+packer+test-phrase support; the converter hooks are **deferred** to the first source song that needs them. (Only detune has a real S3K source, handled in A3.) `Detune` clamp `±$3F` keeps the single-step block correction sufficient at table extremes.
5. **HCZ2 detune A/B vs the S3K oracle is deferred** (the chorus is verified by the constant inter-channel fnum offset + by ear in A3; the full oracle A/B rides with the deferred HCZ2 validation).

### Critical Files for Implementation
- /home/volence/sonic_hacks/aeon-music-expr/engine/sound_sequencer.asm
- /home/volence/sonic_hacks/aeon-music-expr/engine/sound_fm.asm
- /home/volence/sonic_hacks/aeon-music-expr/engine/sound_psg.asm
- /home/volence/sonic_hacks/aeon-music-expr/sound_constants.asm
- /home/volence/sonic_hacks/aeon-music-expr/tools/gen_sound_tables.py
