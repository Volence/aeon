# Music-Expression Phase 2 — Z80 Space Recovery + Banking Strategy

**Date:** 2026-06-28
**Branch:** `feat/music-expr-phase2` (off master `20bcfe0`, after Task-0 doc-sync `d8ea65a`)
**Why this exists:** The two Phase-2 plans (`2026-06-27-music-expression-phase2-{pernote,global}.md`)
were written assuming **~1 KB** of free Z80 code. That headroom existed *before* Phase 1+3 merged;
those features consumed ~800 B of it. A build probe confirms only **216 B free**
(`Z80_SOUND_SIZE=$1618`, ceiling `SND_STATE_BASE=$16F0`). The user chose **"recover space, ship all."**

## Budget (research-confirmed, instruction-counted — `z80-recovery-research` workflow)

Phase 2 new **resident** Z80 code = **798 B**: detune 102, **portamento 384** (Porta_Apply 256),
master-fade 190, global-tempo 107, LFO 15. Free = 216 → must offload **582 B**.

Dead code = **0 B** (all DEFERRED_WORK F3/F4 leads stale: `Snd_TimerA_Program` already purged by the
Phase-3 fixed-rate rewrite; `Sfx_Restore` is a live 2-caller routine, not a stub; the "last inline
channel-class site" no longer exists — only the `Snd_ChanClass` def itself remains). Recovery is
**refactor, not deletion.**

## The banking rule (the key insight)

The F5 mechanism: code/data read **only inside a sequencer frame** can live in the `$8000` song-bank
window (`cpu z80 / phase 08000h`, co-located with `sound_tables_z80.asm` in the MT bank) at **zero cost**
to the `$16F0` resident ceiling. `Run_SeqFrame_OnSongBank` guarantees the song/table bank is in the
window for the whole frame, under `di`. **Every song already must co-locate with that bank** (the voice
writers read `FmPitchTableZ`/`LogVolumeLutZ` there every frame), so banking more in-frame code/tables
adds **no new lock-in** — it is the same constraint that already governs all songs.

**Does NOT qualify** (must stay resident): anything read on the DAC FILL/refill path (sample bank in
window) or the streaming-context mailbox poll (sample bank), or the ISR. So: `DacSampleTable` (sample
bank), `Snd_FadeCommand`/`Snd_TempoCommand` + their mailbox checks (mailbox context), and any in-place
insertion into an existing resident routine.

## Recovery targets (bank existing resident tables → frees resident budget)

| Table | File | B | Note |
|---|---|---|---|
| `SfxBlobWinTab` | `engine/sound_sfx.asm` ~1419-1444 | 270 | id→blob window ptr; **belongs** in the SFX/song bank. Needs a 3-line `SfxDispatch` reorder: move `ld a,SFX_BLOB_BANK / call SndDrv_SetBank` **above** the table lookup so it reads through the window. |
| `FmPatchInlineTable` | `engine/z80_sound_driver.asm` 1359-1361 | 64 | Self-described TEMP in-frame COPY-path table (`Fm_PatchPtr`). Qualifies (in-frame only). Move under `phase 08000h`; point `SND_SEQ_PATCHTAB`/`Fm_PatchPtr` at the window label for the copy path. |
| **freed** | | **334** | headroom 216 → **550** |

(Deliberately NOT banking `SeqOpcodeTable` (64 B) — it's the hottest dispatch path and banking it adds
per-opcode bus jitter; not needed given the code-banking below. Small SFX maps (35 B) skipped — low yield.)

## Phase-2 code placement (the resident/banked split)

**Author in the `$8000` window (in-frame only → 0 resident cost), ~450 B:**
`Fm_FnumApplyDelta`, `Porta_Apply`, `Fade_Ramp`, `Tempo_Ramp`, `Seq_Op_Detune`, `Seq_Op_Porta`,
`Seq_Op_Tempo`, `Seq_Op_Lfo`. (All run inside ModUpdate / Sequencer_Frame / the opcode dispatch, song
bank in window. They never `SetBank`. `SeqOpcodeTable` stays resident; its `dw` entries hold the `$8xxx`
window addresses of the banked handlers — mixed resident/banked targets resolve correctly.)

**Resident (in-place edits / mailbox / init), ~348 B:**
detune+porta note-on adds (inside `Fm_NoteOnFreq`/`Psg_NoteOn`), `.chan_init` porta zero,
`Fm_SetVolume`/`Psg_SetVolume` fade folds, ModUpdate fade-reassert + porta wiring (call sites),
`Sequencer_Frame` ramp-call/dirty-clear/decrement-swap preamble, the global RAM-block init/per-song
reset, `Snd_FadeCommand`/`Snd_TempoCommand` + their `SndDrv_PollMailbox` checks.

**Result:** 348 resident ≤ 550 headroom → **~202 B margin.** Preserves the plans' reviewed asm verbatim
(no risky Porta_Apply rewrite).

## Execution order (build + budget gate + audio verify after every step)

**Phase R — recovery (verify MT/HCZ2/DrumTest/SFX render IDENTICALLY + Z80 size drops ~334 B):**
- R1: bank `FmPatchInlineTable` (simplest). R2: bank `SfxBlobWinTab` (+ the `SfxDispatch` reorder).
- Gate: build green, `Z80_SOUND_SIZE` ≈ `$1618-$14E`≈`$14CA`, golden MT byte/spectrum-identical, SFX fire,
  DAC drums clean (the bank reorder is the risk).

**Phase 2 — features (per the two plans, re-anchored to master; banked split above):**
LFO ($F4, smallest) → tempo ($F3) → detune ($F6) → master-fade → portamento ($F5, largest).
Each: build + `Z80_SOUND_SIZE ≤ $16F0` gate + rendered-audio verify (`vgm_intranote.py` / `vgm_onsets.py`
/ energy envelope). MT golden-faithful at every step. Commit per task with the
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

**Note:** all line anchors in the two source plans predate the Phase-3 merge and are SHIFTED — re-grep
every anchor against current master before each edit. The LFO 3.82-Hz driver-comment doc fix is already
done (Task 0). Group C of the pernote plan (`MEV_FMENV` $F7 / FM-TL vol-env) is SUPERSEDED — already
shipped via Phase 3; do NOT build it.
