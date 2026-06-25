# Handoff: DAC Drum phase — resume at Layer 5 Task 5.3

**Date:** 2026-06-25 (continuation of the DAC-drum / DAC-format-revision phase)
**For:** the fresh agent picking up the remaining DAC work.
**Start by reading:** memory `project_dac_drum_phase.md` (full state + every decision + the
verification method), then this note, then the spec + plan below.

## State of the world

- **Branch `feat/dac-drum`** in the SIBLING worktree `/home/volence/sonic_hacks/s4_engine-dacdrum`.
  Master untouched. Spec + plan are on master. **Tree is clean; everything below is committed.**
- **DONE + VERIFIED + COMMITTED so far:**
  - **Layers 0-3** (clean DAC state, two-stage one-shot stop, noise-shaped DPCM-HQ encoder + S3K
    kick/snare/hat, constant-cost decode FILL). Verified earlier.
  - **Step 0** (`ea81f3b`): gated the idle `$2A=$80` write to the Timer-A tick (de-flood the VGM
    logger). NOTE the IN-SAMPLE `$2A` stream still partly drops in the VGM logger, so the VGM `$2A`
    xcorr is unreliable — use the **de-wrapped RING READ** (below) for decode fidelity.
  - **Layer 4 / FM6 dedicate** (`a29594c`): `$B6=$C0` force-DAC-stereo at sample start + gate the ch6
    `$28` key-on while `SND_STAT_DAC_ACTIVE` (in `Fm_NoteOnFreq.keyon` — the single FM key-on
    chokepoint, NOT the plan's `sound_sequencer.asm` spot). `$2B` stays armed (dedicate); the `$2B`
    toggle is Layer 7. Verified: `$B6=$C0` lands, kick byte-exact, MT not regressed.
  - **Layer 5 / bank brackets B1-B4** (`c9b392a` + `eda6418`): B1 `Run_SeqFrame_OnSongBank` from both
    tick paths; B2 `Snd_StartSample` stash-only; B3 DAC-aware ISR restore; B4 idle->stream latch;
    `Snd_LoadSong` seeds `SND_SONG_BANK` + (DAC_ACTIVE-guarded) `SND_ROM_BANK`. 3-agent review + focused
    re-review (all approve). Verified: MT + a kick COEXIST (bank-swap per frame), kick byte-exact.
  - **Mailbox-poll fix** (`f4afca6`): the VBlank ISR does NOT fire during DAC streaming (proven by
    instrumentation: 0 ISR entries / 15 streaming frames vs ~0.83/frame idle) — the loop's long `di`
    window misses the once-per-frame `/INT`. So the mailbox was frozen for a whole sample. FIXED by
    extracting `Snd_PollMailbox_Banked` and calling it from BOTH the ISR (idle) and `SndDrv_TimerATick`
    (the polled tick that runs during streaming). Verified: a ping is echoed mid-streaming-kick; a
    cross-bank retrigger (blip bank `$0D` -> kick bank `$0E` mid-stream) decodes byte-exact r=1.0; MT
    clean. This ALSO made the bank-bracket review's Findings A/B live + verified.

## Verification method (faithful — use this, not the VGM `$2A` xcorr)

Catch a sample mid-play and read the RING: stop nothing — with B1-B4 you can trigger a drum DURING MT.
Trigger via the mailbox: `emulator_z80_write $1F01 <id>` (1=blip bank `$0D`, 2=kick `$0E`, 3=snare,
4=hat), `emulator_run_frames N`, read 256 B at `$1700`, **DE-WRAP** as `ring[WR:]+ring[:WR]` (WR=`$16F6`),
and `corrcoef` vs `tools/dac_encode.decode_dpcm(<.dpcm>, table0)`. De-wrapped is r=1.0 byte-exact; a raw
linear corr understates (~0.98) due to the circular wrap. Key Z80 addrs: state block `$16F0`
(DEC_ACC,+0 / DAC_PHASE,+1 / SONG_BANK,+2 / ROM_BANK,+3 / CUR_BANK,+4 / RING_RD,+5 / RING_WR,+6),
`SND_STAT_DAC_ACTIVE=$1F14`, `SND_SEQ_ACTIVE=$1804`, ring `$1700`; mailbox `$1F00` ping / `$1F01` sample
/ `$1F02` music (1..$FE play, $FF stop); `SND_STAT_PING_ECHO=$1F11` (NOT $1F10 — that's ALIVE=$5A).
`emulator_audio_spectrum source=fm` = the real FM/DAC bus (tonal = healthy). MT song id = 1.

## Critical gotchas (don't relearn the hard way)

1. **Build:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (a plain build excludes ALL sound; green s4.bin
   ~548 KB, a silent ~362 KB means the flags dropped). **ALWAYS wrap in `timeout 180`** — asl CAN
   infinite-loop (the dead-table loop was fixed in 3eb1a84; diagnose any future hang with `asl -r`).
2. **Worktree:** `tools/bin` must be an ABSOLUTE symlink to the main checkout's `tools/bin` (already set
   up). NATIVE toolchain (no Wine). `tools/bin` shows as `?? tools/bin` in git status — never commit it.
3. **Git:** stage EXACT paths only, never `git add -A`/`-u` (untracked user WIP + the auto-commit daemon
   on `data/editor/` & `tools/ojz_strip_gen.py`). Commit each step.
4. **Oracle emulator can hang mid-session** (`emulator_run_frames` pending for minutes) — that's an
   emulator-side hang, NOT your code; ask the user to restart the Exodus GUI + MCP, don't retry into it.
   No real hardware — all verification is `oracle`.

## Next steps (in order)

0. **(Quick re-orient)** Build green + reload `s4.bin`; confirm MT plays (FM spectrum tonal, banks `$0F`)
   and a mailbox kick decodes byte-exact (de-wrapped ring r=1.0). Confirms the worktree + the L0-L5 state.
1. **Task 5.3 — STREAM DAC-on test song (plan Task 5.3).** Author a DEBUG test song (SMPS-ish format, see
   `sound_constants.asm` SongHeader `SH_*` + channel `SHC_*`/`MEV_*`; mirror MT's bank block at
   `main.asm`): FM melody + an FM6 line + a DAC channel firing `$E2` kick/snare on a beat, in its OWN
   `$8000`-aligned bank (DAC payloads stay in the separate shared DAC bank). Then the full proof:
   - **Bank-swap:** the FM/PSG music is correct AFTER each `$E2` (a swap failure corrupts every later note).
   - **FM6 gate (the Layer-4 proof deferred here):** FM6's `$28` key-on is suppressed during a sample,
     resumes after. NOTE this NOW works because the mailbox/tick services FM6 correctly during streaming.
   - **B3 SFX-mid-drum:** fire a gameplay SFX during a drum — it dispatches mid-drum (works now thanks to
     `f4afca6`; before, the mailbox was frozen so this was impossible), music continues, the next drum
     still decodes byte-exact.
   - MT regression unchanged.
2. **Layer 6 — raise the DAC rate** toward ~18-20 kHz (plan Tasks 6.1/6.2: `$2A` re-park prefix-trim,
   re-balance `SND_LOOP_CYC`, re-derive ring DMA-survival, re-encode samples at the final rate).
3. **Layer 7 — adaptive FM6 toggle** behind a per-song flag (`SH_F_FM6_ADAPTIVE`): key-off FM6 + `$2B`
   toggle at the trigger edge, re-key FM6 at exhaust (lets FM6 play music BETWEEN drum hits).
4. **FF-merge `feat/dac-drum` -> master** + `docs/ENGINE_ARCHITECTURE.md` §6 sync (plan Tasks F.1/F.2).

## Pre-existing bugs found this phase (out of bank-bracket scope — fix deliberately later)

- **`project_timera_disable_bug.md`** — StopMusic disables Timer A and `Snd_LoadSong` never re-arms it, so
  StopMusic->PlayMusic plays a loaded-but-SILENT song (masquerades as a banking bug). Cheap fix: re-arm
  Timer A on the play path.
- **`project_isr_not_during_dac_stream.md`** — the ISR-doesn't-fire-during-streaming finding (now FIXED by
  `f4afca6`; kept for the root-cause record + the design-comment drift it revealed).

## Pointers
- Spec: `docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md`
- Plan: `docs/superpowers/plans/2026-06-24-dac-drum-format-revision.md` (Tasks 5.3 / 6.x / 7.1 / F.x;
  Tasks 4.1/5.1/5.2 are marked DONE inline).
- Memories: `project_dac_drum_phase.md`, `project_isr_not_during_dac_stream.md`,
  `project_timera_disable_bug.md`, `reference_oracle_emulator_mcp.md`, `reference_no_real_hardware.md`,
  `feedback_verify_real_output_not_proxy.md`, `feedback_visible_progress_cadence.md`.
- Verify tooling: `tools/dac_encode.py` (`decode_dpcm`), `tools/dac_verify.py` (VGM caveat above).
