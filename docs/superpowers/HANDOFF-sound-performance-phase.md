# Handoff — Sound Performance & Budget Phase (GREEN-LIT 2026-07-01)

> **STATUS: EXECUTED 2026-07-02** (branch `feat/sound-perf-budget`). See the plan
> (`docs/superpowers/plans/2026-07-01-sound-performance-budget.md`), the spec
> (`docs/superpowers/specs/2026-07-01-sound-performance-budget-design.md`, outcome block in its
> status header), and the per-task measured record
> (`docs/research/phase_harness/t5..t11_verification.md` + `t12_matrix.md`, the final §H matrix).
> The evidence figures below are the phase KICKOFF state — historical.

**For:** the session executing this phase (brainstorm → spec → plan → subagent execution, per repo law).
**User green-lit** the full phase after the HCZ2 "duller/muffled/muddy" investigation. All evidence
below is from same-emulator A/B against the REAL S3K (skdisasm `sonic3k.bin` playing music id $04 in
oracle — captures + analysis scripts in the session scratchpad; regenerate per §5 if gone).

## 0. What this phase is

Three coupled work items, in priority order, that together close the last audible gap between our
HCZ2 rendering and real S3K — plus the budget recovery that everything else queues behind:

1. **Key-off-before-key-on for bare notes (NEW #1 — "no attacks").** The YM2612 key-on is
   edge-triggered: keying an already-keyed channel is a chip NO-OP. S3K's driver keys OFF before
   every note (`zKeyOffIfActive`); our bare-note path never does — measured: **61 of 64 melody notes
   per channel get no EG retrigger** (3 key-offs vs ref's 67). The S3K staccato echo melody renders
   as one continuous pitch-stepping pad, and the mix bed NEVER goes silent (ref has true digital
   silence in ~25% of frames; ours +2.1 dB bed RMS, +4.5 dB at the median frame). This is the single
   biggest "duller" cause. FIX: mirror the off-then-on (exists behind `SND_REKEY_OFF_THEN_ON` in
   `Seq_RekeySingle`, sound_sequencer.asm ~430-448) into the bare-note key-on chokepoint
   (`Fm_NoteOnFreq` keyon section, sound_fm.asm ~783-870). ~10 bytes — needs the budget recovery
   first (6 free) or 4+ reclaimed. MUST NOT touch the no-attack/tie path (bit-7 held notes skip the
   hook entirely — that stays).
2. **DAC starvation ("muffled/quiet drums", user-confirmed by ear).** The per-frame sequencer tick
   freezes the DAC: ref loses 18.9% of drum airtime to holds, ours 45.3% (intro) / **63.5%**
   (melody section) including full-frame 16.7ms freezes ref never has (ref max gap 5.6ms). A tom
   plays in 93ms on ref, 213ms on ours (2.3× smear). Per-hit rendered level is nearly equal
   (−0.6 dB) — the perceived 3-5 dB drum deficit is smear + the never-silent bed. Tick cost under
   HCZ2 load: ~16k cycles median, ~57k worst (≈96% of a frame). FIX directions to design:
   (a) slice `Sequencer_Frame` into resumable ≤2ms chunks returning to the DAC loop between slices;
   (b) interleave paced ring-fed $2A writes inside the tick; (c) reduce tick cost (env
   write-on-change ~1k cyc/channel, cached env-body ptr, cheaper per-channel dispatch) — likely all
   three. NOTE: ref also toggles $2B (DAC enable) per hit and keys FM6 off between hits (42-72%
   duty vs our always-armed 97%) — evaluate hit-scoped disable for silence purity.
   SIDE EFFECT: heavy ticks also explain the measured **~1.5% tempo slowness on clean data**
   (tick overruns push the next Timer-A poll late) — beyond the known ~0.5% idle poll residual.
   Fixing tick cost fixes tempo; re-measure after.
3. **Vibrato/detune fidelity trio ("washy, less defined").** All confirmed vs real S3K:
   (a) `Mod_ReArm` never reloads `sc_mod_wait` — delay honored only on a channel's FIRST note ever;
   every later note shimmers from frame 1 (S3K: 13-14 flat frames per note; short notes never
   vibrate). Fix: latch `sc_mod_wait_raw` per channel (+1 B both structs, shared-offset assert) and
   reload in Mod_ReArm — the old T1.9 finding, now with hard reference evidence. Also T1.9's other
   half: the delta SIGN isn't reloaded either (phase can start inverted).
   (b) **Our vibrato contour is bipolar (±depth around base); S3K's is unipolar-UP (base → +depth →
   base)** — doubles apparent depth where encodings match (96.7 vs 47.6 cents on FM3) and biases
   pitch flat by ~24c during vibrato. Fix in `Mod_Advance`/`Seq_Op_ModSet` semantics — check the
   S3K `zDoModulation` accumulator seed (it starts at +delta, not centered).
   (c) **The stretched pitch-table encoding halves modulation/detune depth on doubled-fnum notes**
   (`FmPitchTableZ` block 0 spans fnum 644-2044; S3K uses canonical 644-1214 per block): bass
   vibrato 36.3c vs ref 72.5c; FM3's echo detune (+4 fnum at block 7 = 10.8 cents in S3K) lands in
   our block-6 doubled encoding = 5.4c — the melody chorus is HALF as wide. Fix: renormalize the
   pitch table to canonical S3K block/fnum (regen + verify; also kills Mod_Advance's block-boundary
   churn) — a deliberate engine-encoding change, design it, don't patch it.
4. **Z80 budget recovery (the enabler).** 6 bytes free at $16EA/$16F0. Recover via DATA banking
   (CAUTION: pointer-table reads under bus contention were only proven safe for the
   SfxBlobWinTab-style access — re-verify per table) then the RAM-map/ceiling rework (~500-650 B:
   the dead 512 B $1B00 copy-path song buffer is the big item — **USER DECISION REQUIRED: reclaim
   it for code headroom vs reserve as the jingle-resume snapshot** (specs-review flagged collision;
   ask before spending). Unblocks: fix #1 (~10 B), vibrato fixes (+2 B/channel + ~20 B), portamento
   (~323 B resident, turnkey plan in docs/superpowers/plans/2026-06-28-portamento-resume.md), the
   deferred small gates (cold-boot $B6 seed, SFX self-steal guard, block-edge clamps, PSG note-fill,
   env write-on-change).

## 1. Exonerated (do NOT chase — verified byte-identical/equal vs real S3K)

FM voices incl. melody $03/$0E (all 30 regs at every matched key-on), TL volume folds, pans (FM +
the DAC L/C/R tom pattern), DAC sample data/amplitudes/import gain (per-hit attack RMS −0.6 dB),
tempo authoring, gate lengths (±1 frame), PSG tones/noise mode, song structure (note-for-note,
64/64 melody notes, ±2.7 cents). Minor residue only: −2.1 dB at 6-10 kHz (attack transients + PSG
detail), tone2 noise-clock period 1 vs 0, engine pitch table +1..+2 fnum (~2 cents).

## 2. Verification protocol for this phase (hard-won lessons)

- Reference = the skdisasm-built S3K in OUR emulator. The game posts its own music from the title
  demo — use the **NOP-patched copy** (patch `13 C0 00 A0 1C 0A/0B/0C` → NOPs ×3 sites =
  `sonic3k_muted.bin`, rebuildable in one python loop) and trigger via Z80 write `0x1C0A = $04`.
  ALWAYS purity-check a capture (per-second key-on histogram + content) before comparing — TWO
  investigations have been poisoned by contaminated references now.
- Oracle z80 addrs need `0x`/`$` prefixes (bare hex parses as decimal, silently wrong).
- Our debug hotkeys: UP=HCZ2, A=MT restart, C=drumtest, START=stop/toggle, B=SFX cycle.
- Verify by RENDERED audio numbers (band RMS, per-hit RMS, duty/stall histograms, spectral
  centroid), note-matched per channel — never register counts alone. vgm2wav renders; the analysis
  scripts from 2026-07-01 (clean_purity/dac_stall/dac_perburst/drum_loud/melody_cmp/melody_regs/
  gate_vib/vib_series/spectral/prominence .py) were in the session scratchpad — recreate from this
  spec if gone.
- Build: sound is now ON by default in build.sh; `SOUND_DBG_MIRROR=1` opt-in only (the mirror
  itself costs Z80 time per frame and puts a 60 Hz tick in the audio — leave OFF for captures).

## 3. Success criteria

- Melody notes retrigger (key-off count ≈ note count per channel); ~25% inter-note digital silence
  returns to the mix bed.
- Drum airtime lost to holds ≤ ~20% (parity with S3K's own driver); no full-frame freezes; tom hit
  duration within ~10% of ref; user reports drums sit right in the mix.
- Vibrato: flat delay frames per note match ref (13-14 on the melody), unipolar-up contour, depth
  in cents matches ref on BOTH encodings; FM3 chorus width ~10.8 cents.
- Tempo drift vs ref < 0.3% over 15 s.
- All existing regression gates green (build, 803+ pytest, MT A/B unchanged, SFX steal/restore).

## 4. Where everything is

- This phase's evidence chain: docs/superpowers/2026-07-01-sound-engine-review-findings.md (+ status
  header), 2026-07-01-sound-specs-review.md, and the memory file
  project_mt_hcz2_fidelity_2026_07_01 (the whole day's arc incl. gotchas).
- References: docs/research/reference_captures/ (tracked; README has trust levels). The clean HCZ2
  captures + S3K muted ROM live in the 2026-07-01 session scratchpad — RECAPTURE per §2 rather than
  hunting for them.
- Budget/porta plans: docs/superpowers/plans/2026-06-28-portamento-resume.md (turnkey after
  recovery); DEFERRED_WORK.md carries the small-items list with today's additions.
