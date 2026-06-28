# Handoff — Music-Expression Phase 2 (midway: recovery + LFO + detune done)

**Written:** 2026-06-28. Branch `feat/music-expr-phase2` (off `master` `20bcfe0`).
**For:** a fresh agent (or the same one) finishing Phase 2. The hard/novel parts are DONE.

## What's committed (in order, all build-green + verified)
- `d8ea65a` — **Task 0 doc-sync** (on `master`, separate from this branch's feature work).
- `e9472f8` — recovery+banking **strategy doc** (`docs/superpowers/plans/2026-06-28-music-expr-phase2-recovery-and-banking.md`).
- `adf86a9` — **LFO** (`MEV_LFO` $F4, resident) + a per-build Z80-budget `message`.
- `9ab15df` — **Z80 recovery**: banked `SfxBlobWinTab` (270 B) → engine/sfx_blob_win_tab.asm.
- `0009d77` — **detune A1**: note-on adds + the FIRST banked in-frame code (`Fm_FnumApplyDelta`).
- `22fdeb8` — **detune A2**: `MEV_DETUNE` ($F6) opcode.
- `fd1f1b6` — **detune A3**: converter emits `Detune` + packer `Detune` event + MEV_LFO sync fix; 771 tests.

## Budget (the gating constraint — was the whole reason for recovery)
- Live: `Z80_SOUND_SIZE` = **$153C / $16F0 → 436 B free** (the build prints this every time).
- Phase 2 needed 798 B resident; recovery freed 270 B + code-banking keeps the big routines out of resident.
- Remaining resident est: tempo ~67, porta ~92 (Porta_Apply 256 BANKED), fade+global-A1 ~190 → ~349 B ≤ 436. ~87 B margin.

## THE banking pattern (reuse this for every remaining big in-frame routine)
**Resident is scarce; the `$8000` song-bank window is free.** Anything that runs ONLY inside a sequencer
frame (ModUpdate / Sequencer_Frame / opcode dispatch / note-on) can live in the window at 0 resident cost.
- File: **`engine/sound_banked_z80.asm`** (included in main.asm's `cpu z80 / phase 08000h` block, after
  the tables). Put `Porta_Apply`, `Fade_Ramp`, `Tempo_Ramp` here. `Fm_FnumApplyDelta` is already here.
- A resident in-frame `call Foo` where `Foo` is banked resolves to its `$8xxx` window addr and executes
  correctly (the song bank is guaranteed in the window in-frame, under `di`). PROVEN: `Fm_FnumApplyDelta`
  at `$856D`, `Fm_NoteOnFreq` assembles `call $856D`, runtime-verified (poke detune → valid block-corrected
  fnums, no crash).
- INVARIANTS (in the file header): a banked routine must NEVER be reached from mailbox/ISR/idle (sample
  bank in window there) and must NEVER SetBank while executing. So: **mailbox handlers** (`Snd_FadeCommand`,
  `Snd_TempoCommand`, the PollMailbox checks) + **init/reset** + **in-place edits to resident routines**
  stay RESIDENT. The big standalone in-frame routines go banked. Small opcode handlers (`Seq_Op_*`) are
  resident (cheap, 8-19 B; margin allows it).

## Remaining tasks (the two written plans — re-anchor every line number, they predate Phase 3)
Plans: `docs/superpowers/plans/2026-06-27-music-expression-phase2-{global,pernote}.md`.
1. **Tempo** (global B1-B4 + the global-plan **A1 RAM foundation** first — `SND_GLOBAL_EXPR` block, shared
   with fade): `SND_TEMPO_CUR` replaces the literal `16` decrement in `Sequencer_Frame`; `Tempo_Ramp`
   (BANKED); `MEV_TEMPO` $F3 (resident handler); `SND_REQ_TEMPO` mailbox (resident) + 68k `Sound_SetTempo`;
   packer `Tempo` event + `MEV_TEMPO` const.
2. **Portamento** (pernote B1-B3): `Porta_Apply` (256 B — BANK IT) + FM/PSG porta note-on (resident, in
   Fm_NoteOnFreq/Psg_NoteOn) + `.chan_init` arm-clear (resident) + ModUpdate wiring (resident) + `MEV_PORTA`
   $F5 (resident) + packer `Porta` event. Reuses the banked `Fm_FnumApplyDelta`.
3. **Master fade** (global A2-A6): the global-plan A1 RAM block (do once, shared with tempo) + fold the
   master-fade scalar into `Fm_SetVolume`/`Psg_SetVolume` (resident, integrate with the EXISTING Phase-3
   env+duck folds — re-read those, the plan's "replace the duck block" anchors are stale) + `Fade_Ramp`
   (BANKED) + ModUpdate fade-dirty re-assert (resident) + `SND_REQ_FADE` mailbox + `Snd_FadeCommand`
   (resident) + 68k `Sound_FadeOut`/`Sound_FadeIn`.

NOTE pernote **Group C** ($F7 FM-vol-env) is SUPERSEDED (shipped via Phase 3) — do NOT build it.

## Per-task checklist (every task)
1. Re-grep the plan's anchors against current master (Phase 3 shifted all line numbers).
2. Big in-frame routine → `engine/sound_banked_z80.asm`; resident edits in place.
3. Build `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`; read the budget `message` (`<= $16F0`, flag if over).
4. **If you touched a MEV_* in sound_constants.asm, run `python3 -m pytest tools/ -q`** (the
   constants-sync test fails otherwise — that's how the LFO/packer gap was caught).
5. Verify on oracle: MT regression (id 1 @ `z80_write 0x1F02 1`) + the feature (poke state, observe).
6. Commit per task, exact paths, `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Gotchas learned this session
- **Oracle symbols are STALE** after `reload_rom` (it reloads the binary, not the symbol table). For TRUE
  addresses, grep `s4.lst` (the listing — shows the assembled bytes + address). `lookup_symbol` lied
  (`SfxBlobWinTab`=$101E stale vs the real $845F in the listing).
- `get_channel_states` is just the enable mask (all `true` always) — useless for "is it playing." Use the
  audio spectrum, a VGM capture, or read RAM state.
- `z80_write`/`z80_read` need `0x`-prefixed addresses (`0x1F02`, not `1F02`).
- Daemon-watched (don't touch / never `--amend` near): `data/editor/**`, `tools/ojz_strip_gen.py`. Commit
  exact paths only (there's user WIP in `tools/forest_bg_gen.py` + `data/sprites/` — leave it).
- Useful addresses: mailbox `SND_REQ_MUSIC`=$1F02, `SND_REQ_SFX`=$1F03; `SND_SEQ_CHANNELS`=$1808,
  `SeqChannel_len`=$3A, sc_flags+$0A, sc_base_freq+$33, sc_detune+$38.

## What's left to fully close Phase 2
After the 3 features above: each plan also has a "verify by rendered audio" task (fade energy envelope,
tempo onset cadence, porta fnum sweep) — do those via VGM/spectrum. Then merge `feat/music-expr-phase2`
to `master` (FF). The HCZ2 detune-chorus demo (regenerate `song_hcz2.py`) rides with the separate
HCZ2-revisit thread, not Phase 2.
