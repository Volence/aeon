# Portamento — resume plan (deferred from music-expr Phase 2)

**Date:** 2026-06-28. **Branch base:** `feat/music-expr-phase2` (after `d601093`).
**Status:** B1 engine machinery IMPLEMENTED + the GLIDE VERIFIED WORKING, but reverted
because it crashes the Z80 (root cause below). B2/B3 not started.

## Why deferred
Portamento's `Porta_Apply` runs **per frame, per armed channel**, from `ModUpdate`. It was
placed BANKED (`engine/sound_banked_z80.asm`, the `$8000` window). Banked in-frame **CODE**
is unsafe: Z80 fetches from `$8000-$FFFF` go through the 68k bus, and under 68k bus
contention (VRAM DMA-from-ROM and/or the DEBUG VBlank state-mirror's `stopZ80`/BUSREQ) the
fetched opcode is corrupted → wild PC → the Z80 self-reinits (no 68k watchdog; `di` doesn't
help — it masks the Z80 INT line, not 68k BUSREQ). 2+ armed channels = 2 banked-code
executions/frame → intermittent crash (~300-1200 frames); single channel rarely aligns →
stable. Twice live-captured (PC traced running into bank-`$0C` data from inside
`Porta_Apply`). The glide MATH is correct (verified smooth fnum sweeps, FM1 range 257 /
FM2 range 649). Banked **data** reads tolerate the contention; **code** fetches do not.
See memory `project_banked_preamble_constraint`.

## The verified B1 work (preserved)
`docs/superpowers/plans/porta-b1-WIP.patch` — apply with `git apply` onto the branch. It is
`Porta_Apply` + the FM/PSG note-on porta blocks + the ModUpdate FM/PSG porta wiring +
`.chan_init` arm-clear. The glide was oracle-verified (intra-note fnum sweeps); only the
PLACEMENT is wrong.

## The fix (turnkey)
1. **Relocate RESIDENT.** Move `Porta_Apply` (~257 B) AND `Fm_FnumApplyDelta` (~66 B) out of
   `engine/sound_banked_z80.asm` (the `phase 08000h` block) into the resident phase-0 Z80
   blob — paste them next to the resident `Tempo_Ramp`/`Fade_Ramp` in `sound_sequencer.asm`.
   Call sites need NO change (assembler re-resolves the labels). This also fixes the shipped
   detune's latent hazard (it shares `Fm_FnumApplyDelta`). Then delete the now-empty
   `sound_banked_z80.asm` + its `main.asm:282` include (and the SfxBlobWinTab DATA banking
   stays — data is safe).
2. **Recover ~300 B resident budget** (resident is ~22 B free with Porta_Apply banked; +323 B
   resident needs ~300 B back). Bank only **DATA** tables (safe — data reads tolerate the
   contention), the SfxBlobWinTab way (`engine/sfx_blob_win_tab.asm`). Candidates from the
   recovery doc + a fresh survey: `FmPatchInlineTable` (~64 B), `SeqOpcodeTable` (~64 B, hot
   but data), the DAC sample table, the small SFX maps (~35 B), `Seq_FmKeyoffChsels`, etc.
   The `phase`/budget assert tells you exactly how much more to free.
3. **Finish B2 + B3** (from the pernote plan):
   - B2: `MEV_PORTA = $F5` constant + asserts (sound_constants.asm) + `Seq_Op_Porta` handler
     (resident, beside Seq_Op_Tempo) + dispatch `$F5` slot (it's the free `Seq_BadOpcode`).
   - B3: packer `Porta(Event)` (tools/song_packer.py, mirror `Tempo`) + `MEV_PORTA = 0xF5`
     const + music-legal-set entry + a test. Run `pytest tools/` (constants-sync).
4. **Verify** on oracle (real `Sound_PlayMusic` via press-A — `z80_write 0x1F02 1` loads a
   0-channel song, useless): arm porta on FM1 (`$182A`) + FM2 (`$1864`), **3000+ frame soak**
   with PC staying resident (never `$8xxx`/`$Cxxx`), `SND_SEQ_ACTIVE`/`CHCOUNT` stay nonzero;
   render the glide audio (vgm2wav / vgm_intranote) to confirm smooth sweeps. Belt-and-
   suspenders: install the `$0000` reset-vector trap (`F3 18 FE` = `di; jr $`) during the
   soak — it must never fire.

## Note on the recovery doc
The recovery doc's "code-banking technique" for in-frame routines is UNSOUND (only DATA
banking is safe). Update `docs/superpowers/plans/2026-06-28-music-expr-phase2-recovery-and-banking.md`
and `ENGINE_ARCHITECTURE.md` to reflect this when doing the resume work.
