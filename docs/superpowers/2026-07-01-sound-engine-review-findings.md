# Sound Engine Quality Review — Consolidated Findings (2026-07-01)

> **STATUS UPDATE (same day):** the fix pass SHIPPED to master (`4f7c563` merge + toolchain commits
> `ef94cc9..f2448d4`). Oracle-verified: Timer-A/StopMusic revival (T0.1), NOTE_RAW steal/restore pitch
> (T1.5), tempo 2× speed-up (T1.4), PSG rest-gate wash removal (T1.2), HCZ2 drum re-triggers (T1.1),
> MT/HCZ2 regressions clean. Content-inert fixes build-verified. NOT fixed (still open): T1.9 vibrato
> per-note reload (+2 struct bytes, schedule with porta), the Seq_Op_ModSet override gate (budget),
> B1 block-edge clamps, PSG note-fill, F3 late slot-clear, retrigger policy, frame-clock decision,
> DAC ratification, the game-feel spec, doc-sync. **Z80 budget after the pass: `$16EA`/`$16F0` — 6
> bytes free** (the numbers below reflect the pre-fix state).

Five-agent deep review (driver core, sequencer/expression, SFX+integration, Python toolchain,
architecture) of the sound engine on master (`ed586b4`). Read-only audit; fixes tracked separately.
Severity: **crash** > **audible-now** > **latent** (correct inputs never hit it) > minor.

Build baseline: `SOUND_DRIVER_ENABLED=1 DEBUG=1` green; `Z80_SOUND_SIZE=$1666` / ceiling `$16F0`
= **138 bytes free** (docs saying 216 are stale). pytest: 771 passed, 2 skipped.

> Prerequisite fixed first: master's DEBUG build had been broken since the engine/game restructure
> (root-`data/` path fallout in build.sh + 3 generators) — fixed in `ed586b4`.

---

## Tier 0 — crash / everything-dies class

- **T0.1 Timer-A: StopMusic kills the whole driver (music, SFX, DAC refill).** `z80_sound_driver.asm:562`
  `.music_stop` calls `Snd_TimerA_Disable`; `Snd_LoadSong.arm` (1330-1366) deliberately never re-arms.
  With no Timer-A tick, `Sequencer_Frame` never runs — and `Sfx_Frame` only runs as its tail, so **all SFX
  die too**, and a mid-flight DAC drum loses its per-frame refill. Fix: delete the disable call (−3 B), add
  belt-and-suspenders `call Snd_TimerA_ProgramFixed` in `.arm` (+3 B); `Snd_TimerA_Disable` becomes dead
  (~13 B reclaim). Net ≈ 0 B. (Known bug, confirmed + found worse than recorded.)
- **T0.2 SFX-before-first-music reads its event stream through bank 0.** `Run_SeqFrame_OnSongBank`
  (z80:866-871) banks `SND_SONG_BANK` (zeroed at init) before `Sequencer_Frame`→`Sfx_Frame`; the SFX slot
  loop has no SetBank. Cold boot + SFX with no song ever loaded → the Z80 interprets 68k code at ROM
  $0000-$7FFF as an event stream (random notes/reg pokes). Masked today only because all songs+SFX share
  one bank. Fix: `ld a,SFX_BLOB_BANK / call SndDrv_SetBank` at `Sfx_Frame` entry (+5 B).
- **T0.3 Banked in-frame CODE hazard: `Fm_FnumApplyDelta`** (`sound_banked_z80.asm:41`, sole caller
  `sound_fm.asm:725`, FM note-on path). The only code in the $8000 window; unsafe under bus contention
  (proven failure mode). Dormant on master (no `$F6` in shipped data) but armed by any detuned content.
  Fix: relocate resident (~60 B), delete the banked-code file.
- **T0.4 `MEV_REGWRITE`/`TAG_MAC_REG` guard $2A/$2B but not $24/$25/$27.** An authored `$27` write
  (natural ch3-special value `$40`) stops Timer A → total freeze (combined with T0.1, unrecoverable).
  Fix: extend guard or force timer bits (~12 B).
- **T0.5 Packer foot-guns that hang/corrupt the Z80:** (a) nested `RepeatStart` packs cleanly but the
  engine is single-level (corrupted loop ptr) — reject at pack time; (b) a mid-body `MacLoop` (yield check
  only inspects the terminal event) → `MacroTick` infinite spin — require a `MacNext` before any `MacLoop`.
  (`song_packer.py:776-789`, `:395-407`.)

## Tier 1 — audible now

- **T1.1 HCZ2 is missing drum hits.** S3K DAC bare-duration bytes RE-TRIGGER the saved sample
  (`zUpdateDACTrack_cont`); our importer paces them as silence (`smps_import.py:943-973`). HCZ2's
  accelerating snare rolls and its 9-hit fill are gone. The 2026-06-23 fix repaired the TIME of these
  bytes, not their articulation. Fix: track `saved_dac`, emit `Dac(saved)` + paced rest.
- **T1.2 PSG vol-envelope un-silences rested channels (drone).** ModUpdate's PSG tail has no `SCF_KEYED`
  gate (`sound_sequencer.asm:270-276`); sustain/plain env bytes re-emit volume after a REST keyed the
  channel off. 5/11 shipped env bodies end in `$81` sustain. S3K gates exactly this. Fix: +4 B KEYED gate.
- **T1.3 `MEV_NOTEFILL` is dead on bare-note streams (the whole SMPS import path)** — `sc_fill_count` is
  only reloaded on the PITCHENV(count==1) rekey path, so imported staccato becomes legato. Fix: reload at
  `Fm_NoteOnFreq` (net ≈ 0 B). PSG note-fill doesn't exist at all (separate ~15-20 B feature).
- **T1.4 Tempo speed-up is arithmetically broken.** CUR > base makes the unsigned accumulator wrap
  (absorbs one borrow/frame): CUR=2×base yields 0.22 ticks/frame in bursts+stalls, not 2.0. Fix: loop the
  borrow (~10-12 B). `sound_sequencer.asm:86-95`.
- **T1.5 SFX steal/restore re-keys the WRONG PITCH on NOTE_RAW songs (Moving Trucks).** `Seq_Op_NoteRaw`
  stashes the raw $A4 byte in `sc_note`; `Sfx_Restore` re-keys it as a pitch-table INDEX → up to ~130 ms
  wrong-note blip per steal. Fix: latch `sc_base_freq` before the override gate + restore via
  `Fm_NoteOnFreq` on raw songs (~15-18 B).
- **T1.6 SFX restore loses the song's MEV_PAN/$B4 (pan + AMS/FMS)** — restore re-derives $B4 from the
  patch; write-on-change shadow never refires. Fix: zero `sc_last_pan` in restore (+4 B).
- **T1.7 One-frame stale-volume attacks on envelope'd notes** — env emits before the rekey and
  `sc_env_out` isn't cleared at note-on; every attack's first ~17 ms plays the previous note's env tail.
  Fix ~8 B (+ optionally reorder FmEnvUpdate after rekey).
- **T1.8 Sticky multipoint arp: REST can't stop it** (re-keys every frame, re-sets KEYED). Fix: +4 B
  KEYED gate at `.multipoint`.
- **T1.9 Vibrato onset/phase deviates from S3K per note** — `Mod_ReArm` doesn't reload `wait` or the
  delta SIGN (S3K reloads both every note): delay ignored after the first note; phase can start inverted.
  Full fix needs +2 struct bytes/channel — schedule with the portamento budget work.
- **T1.10 Fade-in starts with a 1-frame full-volume blip** — `.fade_in` doesn't set `SND_FADE_DIRTY`.
  Fix +5 B.
- **T1.11 Importer: PSG `smpsSetVol` operand decoded wrong** (S3K uses bits 3-6 inverted; we use the low
  nibble) — wrong PSG volumes AND poisons subsequent AlterVol deltas. `smps_import.py:505,608`.
- **T1.12 Importer: `smpsPan` drops the AMS/FMS arg; DAC pan dropped entirely** — HCZ2 pans its tom
  fills L/C/R via FM6 $B6; we play them center. (DAC pan may need a small engine path — decide.)

## Tier 2 — latent / robustness

- MacroTick `TAG_MAC_REG` not gated by `SCF_SFX_OVERRIDE` (macro reg-writes corrupt a running SFX) — +6 B.
- `Seq_Op_PsgNoise` + `Seq_Op_ModSet` tail ungated vs SFX override (~5-7 B each).
- Mod_Advance/FnumApplyDelta block math: no negative-underflow/block-7 clamps → screech on out-of-range
  sweeps (~14-16 B, or transcoder-side range validation).
- Importer: FM/PSG bare standalone duration should RE-ATTACK, not tie (S3K re-articulates; latent for
  HCZ2 which always uses smpsNoAttack; sfx_transcode already does it right).
- Importer: rest-duration overflow clamps (drops time → channel drift) instead of splitting.
- Packer: Macro-without-body packs offset 0; no 64 KB offset bound; channel_count >11 loads as silent
  zero-song; duplicate routes unchecked.
- REQ_MUSIC/REQ_SAMPLE cleared after the handler → a request landing mid-load is silently erased.
- Same-SFX retrigger spawns up to 3 concurrent instances (spindash rev spam) — POLICY DECISION, then the
  5b extend (~25-35 B). Multi-channel SFX tier-c self-steal (~15-20 B guard).
- Transcoder: unknown `smpsVc*` sub-macros silently pass (should raise); B5 noise-tracking-tone still the
  documented refinement; stale smpsModSet docstring.
- No YM2612 busy-flag wait on register bursts — real-hardware-only risk (Exodus blind to it); recorded as
  first suspect if hardware testing ever shows dropped writes.

## Design decisions surfaced (need explicit choice)

1. **Frame clock is 59.06 Hz, not NTSC 59.92** (`SND_TIMERA_N` targets 59) → ALL music ~1.4 % slow vs
   S3K. `N=125` gives 59.85 Hz. Changes the feel of already-verified MT — re-verify after.
2. **DAC format: the approved spec rejected runtime mixing (pre-mixed composites) but ARCH §6.2 +
   DEFERRED E2 still advertise an N-voice mixer**, and the 9-byte descriptor has no `ds_vol`/mix cursor.
   Foreclosure: sampled-SFX-over-drums. Needs user ratification before a real drum library is authored.
   (The "one-shots never stop" urgency in the post-merge handoff is STALE — the drum-phase state machine
   fixed it.)
3. **SFX retrigger policy** — concurrent instances (current) vs classic restart-same-channel.
4. **Arp re-attack** — multipoint trill slurs (same-mask $28 write ≠ EG retrigger); A/B vs oracle, then
   decide.

## Architecture verdict (unchanged decisions)

Foundation is right: Z80 autonomy, DMA-survival DAC, Timer-A tick, event format + macro spine all hold.
The binding constraint is the **resident-code budget** (138 B free; portamento needs ~323 B resident).
Runway: bank remaining DATA tables (~200-260 B, safe pattern) → then a deliberate Z80 RAM-map/ceiling
rework (~500-650 B more; drop the unused 512 B copy-path song buffer) before Phase 5. Clean audits:
$2A park discipline, mailbox protocol (bar the late-clear nit), RAM layout (+stack ~230 B headroom),
hl-preservation, SFX priority/queue/duck model, D8 packer gate, header contract.

Perf note: a fully-lit expression frame (vibrato+env+macro on all channels) costs 28-34 k cycles ≈ half
the frame, all of it DAC stall → drums degrade toward ~9-10 kHz effective. Cheap recovery: env
write-on-change (~10 B) + cached env body ptr.

## Doc drift to reconcile (single doc-sync pass)

ARCH §6.1 deferred list (detune/LFO/tempo/fade SHIPPED; only porta remains) · §6.2 DAC mixing/DPCM
contradict the approved spec · §6.8 bank-switch shipped · banked-code physics constraint unrecorded ·
DEFERRED_WORK C1-C4 + blip-descriptor stale (fixed by drum phase) · F1/F5 headroom 216→138 · Z80 RAM-map
spec stale · §6.10 "Flamedriver" label · sequencer header comments (ModSet/Mod_ReArm/Mod_Advance,
sc_note sentinel) · sfx_transcode smpsModSet docstring · handoff §4.B stale C1 claim.
