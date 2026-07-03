# Sound Production Suite — Design (Banking Package 5)

**Date:** 2026-07-03
**Status:** BANKED design (sound design-banking session, second wave; user pre-approved the
package direction — this spec is the review artifact before its plan)
**Goal:** Make the engine's *mixes* sound produced — modern production techniques no shipped
Genesis driver has — using the three channels physically available on this hardware:
build-time DSP, control-rate register automation, and FM-operator tricks. Real-time DSP on
the mixed output is impossible (the chip mix never passes through a CPU) and everything here
respects that.
**Provenance:** user asked for "reverb-ish / targeted-compression-ish / anything unique"
(2026-07-03); full demoscene/tracker/composer research pass done same day (Titan Overdrive,
Furnace/Deflemask, Kabuto notes, MDSDRV, Follin/Koshiro practice, SpritesMind; Paprium
investigated and DISMISSED — fabricated chip branding, MCU-in-cart, nothing adoptable).
**Byte reality (measured, not doc claims):** current free resident Z80: **362 B DEBUG / 488 B
release**. Banked packages A+B+D consume ≤ 260 B of it (ceilings). The table-banking lever is
**exhausted** (SeqOpcodeTable + all big LUTs already live in the banked window — verified).
The suite is therefore TIERED: Tier 1 fits unconditionally; Tier 2 executes against MEASURED
post-A-D headroom with an explicit budget gate.

---

## 1. Tier 0 — build-time / authoring (ZERO resident bytes, biggest wins)

1. **Drum mastering chain** (extends package C's runbook): per-drum EQ / multiband
   compression / saturation / **baked reverb tails** in the Python sample pipeline.
   Demoscene validation: Titan Overdrive 2's acclaimed audio is exactly this — offline-
   mastered material through a clean DAC path. Amiga-scene rule adopted: bake **gated**
   (hard-cut) tails — they read as "produced" at low sample rates far better than long ones.
2. **Ladder-effect-aware level staging.** The YM2612 (MD1) DAC has a crossing discontinuity
   that adds bright grit to QUIET signals — free harmonics on fades and soft tails
   (Koshiro-era composers exploited it deliberately). Adopt as mastering RULES: stage PCM
   and quiet FM carrier-TL ranges around it; **decide the reference target (MD1 ladder vs
   MD2/YM3438 clean) and make oracle + vgm2wav renders model the choice** — otherwise our
   A/B verification lies. (Research: joelkp/AlyJames/jsgroth analyses.)
3. **TL-filter-sweep vocabulary + generator.** Sweeping a modulator's TL at control rate IS
   the FM substitute for a filter sweep (Koshiro's TB-303 trick). We already ship TL-capable
   macros — add a build-time `filter_env → TL-curve` generator (Python) + authored patch
   vocabulary (wah, acid bass, filter-env pads). Authoring + tooling only.
4. **PSG periodic-noise sub-bass.** Periodic noise = 1/16-duty pulse **4 octaves below** the
   clocking tone (reaches ~7 Hz). We already ship tone-clocked noise (`MEV_PSGNOISE`); this
   is an authoring pattern + doc: a sub layer under FM bass that no FM voice can reach.
5. **Generative variation at build time** (Koshiro SoR3 "Automated Composing" pattern,
   tamed): humanized velocities, ghost-note dice, alternate sample start-offsets per drum
   hit, and **baked kick+snare flam composites** (kills the main reason anyone wants a
   second DAC voice). Python-only; deterministic seeds (build reproducibility — no
   `random()` without a seed in the manifest).
6. **SSG-EG timbre vocabulary** (after package D lands runtime group 6): patch presets
   using looping SSG-EG on modulators for transient snap and shimmer tails.
7. **Echo authoring rules** (Follin practice, applies to Tier-2's echo bus AND manual
   authoring today): echo notes at −6 dB-ish, **opposite hard-pan**, duller patch
   (modulator TL dropped), same-channel ghost-note fallback during rests when no spare
   channel exists (C64 convention).

## 2. Tier 1 — small resident features (fit inside any realistic post-A-D floor)

8. **Kick-triggered sidechain pump (~30-50 B).** The user's "targeted compression," real:
   on a DAC drum trigger (per-sample flag in the 12-byte descriptor — `ds_vol` neighbors,
   or a song-header enable), set the existing duck engine's target to an authored depth
   with fast attack, and let the shipped slow-release ramp recover it. Music-side gate,
   write-on-change re-assert — all shipped plumbing (`SND_SFX_DUCK_LEVEL` path). Per-song
   opt-in. NOTE the interaction: package B moves ducking to per-SFX authored depths; the
   pump writes the same target variable — LAST-WRITER semantics must be spec'd in the plan
   (recommend: pump and SFX-duck targets combine as MAX, same rule as B's overlap policy).
9. **Autopan macro target (~20-40 B).** Binary L/R pan flipping at macro rate (rotary/
   tremolo width) as a new macro/`MEV` surface riding the existing `$B4` pan plumbing —
   plus cross-panned echoes from item 7. (Furnace-community standard.)

## 3. Tier 2 — budget-gated resident features (execute against MEASURED headroom)

10. **Opportunistic echo bus (~80-120 B + ~40 B RAM from the $1ED2 free block).** Engine-
    automatic ghost echo: flag a source channel; the sequencer replays its note events
    N ticks later, quieter/duller/cross-panned, on a designated echo channel — and the bus
    is **priority-aware**: SFX steals or busy arrangements silence the echo gracefully
    (reverb that ducks itself — no driver anywhere ships this). Follin's authored practice,
    generalized. RAM: small note FIFO (event, vol, tick) in the 46-byte `$1ED2` block.
11. **Auto detune-unison (~50-80 B).** One score channel → two chip voices, ±detune,
    hard-panned L/R (the community-standard width trick as an engine feature; absorbs the
    Phase-3b `detune-unison` backlog orphan). Only meaningful when the arrangement has a
    spare FM channel — pairs with the echo bus's idle-channel arbitration.
12. **ExtCh3 operator-as-track (moderate; sequencer plumbing).** CH3 special mode gives
    each of FM3's four operators an independent frequency: 4-note organ/pad chords on ONE
    channel (alg 7), or two 2-op voices (alg 4). MDSDRV ships op-split tracks — the one
    feature it has that we don't. Score-side: a channel-route variant; engine-side: op-freq
    addressing in the note-on path. Size in the plan; likely the largest Tier-2 item.

**Tier-2 budget gate (normative):** Tier 2 executes ONLY after packages A/B/D land and the
build's budget line is re-measured. Priority order 10 → 11 → 12; each item's plan task
starts with "measure free bytes; if < item's ceiling + 32 B safety floor, STOP and record."
If actuals block item 10, the fallback is a dedicated code-size optimization pass (the
driver has never had one; NOT promised here — sized as its own decision if needed).

## 4. Designed-NOT-built (recorded so nobody re-derives)

- **CSM formant/vocal mode (CH3 + Timer A key-on).** Talking-synth timbres, near-zero
  shipped precedent, spectacular showpiece — but CSM drives key-on from **Timer A, which is
  our frame clock** (architecture pin, T0.1 history). A CSM passage needs the tick derived
  from Timer B for its duration — an invasive dual-clock mode. Verdict: DESIGN DOOR ONLY —
  `MEV_REGWRITE` already reaches `$27` mode bits for experiments on a scratch song; a real
  feature waits until a song concretely wants a vocal moment. (Research: SpritesMind t=1231,
  AlyJames CSM notes, Furnace docs.)
- **PSG volume-register PCM stinger** (3-channel 4-bit PCM, offline Viterbi-encoded):
  perfect for our build pipeline, brutal on the Z80 (~all of it), eats all PSG — only
  plausible as a music-paused title-screen voice stinger. Door stays open; no feature.
- **26 kHz DAC chase** (Overdrive 2 territory): 18.4 kHz + mastering wins the A/B for drums;
  revisit only if rendered drum A/Bs ever dispute it.
- **SKIP list (researched, dead):** FM-register PCM "5 extra channels" (bandwidth-debunked),
  XGM-style 4×PCM mixing / Furnace DualPCM (sacrifices our rate + autonomy for polyphony we
  bake at build time), Paprium "Datenmeister" (fabricated), Kabuto PSG readback bits +
  `$2C` test-register games (non-stock curiosities), Traveller's-Tales 68k mixing
  (contradicts Z80 autonomy).

## 5. Verification (foreground oracle; rendered audio per the standing rule)

- Sidechain: rendered HCZ2 with pump on/off — RMS dip ~authored dB on kick onsets, release
  slope matches; registers show duck-target writes only on triggers (write-on-change).
- Echo bus: rendered A/B vs a hand-authored Follin-style echo of the same phrase —
  must be indistinguishable; steal test: fire SFX on the echo channel mid-phrase, echo
  drops + returns without artifacts, music channels byte-identical throughout.
- Unison/autopan: stereo field renders (L/R channel split) show width; mono-sum shows no
  comb-cancel worse than −3 dB (detune chosen accordingly).
- Mastering/ladder: render the drum kit through BOTH ladder models; publish the chosen
  reference in the runbook; kit A/B vs source WAVs (spectrum + transient).
- Every Tier-1/2 feature: OFF by default, byte-identical renders for existing songs
  (MT/HCZ2 golden captures) when unused.

## 6. Resolve during writing-plans

- Sidechain trigger encoding (per-sample descriptor flag vs song-header mask) + the
  MAX-combine rule with package B ducking.
- Echo FIFO depth/layout in the 46-byte block (bounds worst case: 16th-note echo at
  fastest tempo).
- Autopan surface: macro tag vs new MEV (prefer macro tag — zero opcode spend).
- ExtCh3 route encoding + whether alg-4 dual-voice is v1 or door-only.
- Which Tier-0 tools land in package C's runbook vs this package's tasks (avoid duplicate
  pipelines — likely: mastering chain extends C's tool tasks; this package owns the
  filter-env generator + variation engine).
