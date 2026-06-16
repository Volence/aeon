# Sound Driver Design — Best-on-Platform Z80-Autonomous Audio Engine

**Date:** 2026-06-16
**Status:** Design approved, ready for plan decomposition
**Branch:** `design/sound-driver`
**Supersedes:** `ENGINE_ARCHITECTURE.md §6 Audio` — that section planned to *bolt features onto
Flamedriver*. This design replaces Flamedriver with our own driver while preserving **every**
feature §6 planned. To beat Flamedriver we must include all of §6 *plus* the frontier additions.

## 1. Purpose & Ambition

The s4_engine writes every subsystem from scratch. Audio is currently the only
place the architecture planned to import outside code (Flamedriver). This design
replaces that plan: we build our **own** Z80-autonomous sound driver, fully ours,
targeting **best-on-the-platform** quality with no compromise — a full DAC
powerhouse *and* deep FM synthesis *and* a game-feel integration layer no
commercial Genesis game shipped.

The central finding from research (§2) is that **the best-in-the-world Genesis
driver does not exist yet.** Every existing driver — hobbyist (Mega PCM,
Flamedriver, XGM2, Echo, MDSDRV) and commercial legend (Technosoft's Thunder
Force IV, Treasure's Gunstar Heroes, Jesper Kyd's Batman & Robin) — nails one
slice and leaves the rest. No driver has ever shipped the *union*. This engine is
that union.

MegaDAW becomes the authoring tool / compiler for the driver's data format. We do
not constrain the design to any existing format (SMPS/VGM); MegaDAW re-targets.

## 2. Research Basis

All eight reference disassemblies were examined, including the four commercial Z80
sound blobs that were previously opaque binary data. A custom Z80 disassembler was
written (`docs/research/z80_blobs/z80dasm.py`) and the blobs extracted and
analyzed:

- **Batman & Robin** (Jesper Kyd) — full reverse-engineering in
  `docs/research/z80_blobs/batman_driver_analysis.md`. Source of several pillars.
- **Gunstar Heroes / Alien Soldier** (Treasure), **Thunder Force IV** (Technosoft)
  — listings in `docs/research/z80_blobs/*.lst`.
- Modern/online frontier survey (Mega PCM 2.1, XGM2, Echo, MDSDRV, DualPCM,
  Kabuto hardware notes, Furnace YM2612 docs, pcmenc, SNES BRR) with citations
  retained in the research agents' reports.

**Key findings that shaped this design:**

1. The legends were **all single-channel DAC** — none mixed. Multi-channel mixing
   combined with DMA-survival buffering is genuinely **unexplored territory**.
2. **Batman's architecture** is distinct from every other driver: a
   resumable-coroutine DAC scheduler clocked by YM Timer B, dual per-channel data
   streams, true division-based portamento, dynamic FM6 reclamation, DC-offset
   removal, log volume. This is *why* that soundtrack sounds alive.
3. **Mega PCM 2.1** (released 2026-05-10) is the single-channel quality king
   (read-ahead ring buffer survives 24 KB DMA, cycle-exact loops, ~32 kHz,
   DPCM-HQ) — but does **no mixing** and is DAC-only.

## 3. Hardware Constraints (the immovable budget)

- **FM6 and the DAC are mutually exclusive.** YM2612 reg `$2B` bit 7 swaps FM
  channel 6's output for the byte written to reg `$2A`. No 7th voice. Every "DAC
  channel," single or mixed, shares this one output.
- **The Z80 (3.58 MHz) is a single shared budget** for DAC feeding/mixing *and*
  FM/PSG sequencing. Cost scales with DAC channel count × sample rate. Reference
  (XGM): ~4 PCM voices @ ~14 kHz ≈ 70% of the Z80 (effectively ~6-bit output). You
  cannot have a maximal mixer *and* maximal FM simultaneously.
- **YM2612 register write speed is capped** (~1 write / ~33.6 Z80 cycles; faster /
  word writes unreliable). A write-queue is mandatory.
- **68k→VDP DMA freezes the bus**, starving any Z80 loop that reads sample bytes
  from ROM mid-transfer (the classic "scratchy DAC"). Mitigate via read-ahead
  buffering (§5).
- **Z80 bank switch costs 100+ cycles** (9 serial writes to `$6000`) — the #1 Z80
  perf threat after DAC mixing. Drives the bank-packing optimization (§8).
- **Z80 RAM is 8 KB**, bounding buffers and any echo/delay line.

## 4. Architecture

### 4.1 Z80 Autonomy & 68k Handoff

Entire engine on the Z80; the 68k only posts commands. Handoff uses Batman's
**direct-injection mailbox**: the 68k writes whole command records straight into
Z80 RAM plus an atomic "dirty" flag the driver latches and clears each tick. Zero
opcode parsing, lowest latency. (Batman `$16EA`/`$17EA` staging model.)
**Verified writes:** command/data writes use read-back-and-retry
(`move.b d0,(a1); cmp.b (a1),d0; bne retry`, ~8 cycles each) to prevent silent
loss under bus contention (Batman/Zyrinx + DEFERRED_WORK).

### 4.2 Cooperative Scheduler

Backbone is **Batman's resumable-coroutine model**, generalized:
- A YM **Timer** (sub-frame, NTSC/PAL-independent — §8) is the master tick.
- Between ticks the DAC engine runs as a near-100%-duty background task feeding
  reg `$2A`. On timer overflow it **breaks out, services FM/PSG, reloads the
  timer, and resumes** the DAC mid-stream.
- FM update is **split across ticks** (Batman runs two halves alternately) to
  balance load.

A third architectural model, distinct from Mega PCM's ISR and XGM2's sample-rate
ISR — the right one for a streaming Sonic engine.

### 4.3 The Adaptive FM6/DAC Slot (first-class pillar)

FM6 is a **content-adaptive slot**; the engine selects mode from the composer's
data. Novel — no existing driver offers all three:

| Composer content | FM6 behavior |
|---|---|
| FM6 melody, little/no DAC | Full **6th FM synth voice** |
| FM6 melody **and** DAC samples | **Time-share** (Batman): synth in gaps, DAC per hit |
| **No FM6 melody** | **Permanent N-channel DAC mixer** — zero melodic-voice cost |

- Mode driven by data, evaluated per song/section.
- Reclamation: drop DAC mode (`$2B=$00`) the instant no sample is active, returning
  FM6 + its cycles to the sequencer.
- Honest trade-off: in time-share mode each sample briefly interrupts a concurrent
  FM6 note (imperceptible for short hits). Always-on-mixer mode has no FM6 melody
  to interrupt, so no conflict. This design *minimizes* the §3 cycle cost — DAC
  cycles are spent only when samples actually sound (vs XGM's permanent mixer).

Contrast classic Sonic/SMPS, which dedicates FM6 to the DAC permanently (music
effectively gets 5 FM voices + DAC). [Exact stock behavior to be confirmed against
Flamedriver source during planning; not load-bearing.]

## 5. DAC Subsystem

**Quality-adaptive output:**
- **1 active sample** → highest-class single-stream: up to ~32 kHz with
  Kabuto/Mega-PCM-grade jitter control (timing model accounts for ROM contention).
- **2–N active samples** → software mixer: sum signed bytes, clamp via a
  precomputed saturation **LUT**, write the single result to reg `$2A`. Per-channel
  volume and pitch (per-sample `djnz` delay / phase accumulator); rate scales down
  as count rises (§3 budget). Per-channel selectable **half-rate** (~6.65 kHz) for
  bass/ambient samples saves ~50% ROM with no audible loss.

**DMA-survival read-ahead buffer (mandatory):** Z80-RAM ring buffer pre-filled from
ROM during safe windows, drained during DMA so the DAC never reads ROM
mid-transfer. Target: survive Sonic's worst-case per-frame DMA (Mega PCM 2 /
DualPCM model). Highest-payoff quality feature; what separates us from classic SMPS.

**YM write-queue:** decouples the mixer from the ~33.6-cycle write limit.

**Busy-poll policy:** the YM busy flag is polled once at driver init, but NOT before
each write on the DAC-feed / timer-setup paths — loop timing already guarantees
spacing there (DualPCM/Mega PCM omit it too). FM register-pair writes (Plan 1C) DO
need a busy-poll (or write-queue gating) before each write; this is where the hazard
bites. Decided during Phase-1 Foundations hardware bring-up (2026-06-16).

**Compression:**
- **BRR-style codec** (SNES-derived, 9 bytes / 16 samples, cheap add/shift
  predictor) as primary — better fidelity-per-byte than 4-bit DPCM. *Spike: measure
  Z80 decode cost at rate alongside N voices.*
- **Gunstar packed-accumulator DPCM** as a lighter alternative (~50% ROM).

**Stereo PCM & panning:** per-sample L/R enable flips (reg `$B6`) for panned/moving
samples, time-interleaved stereo, and **pseudo-stereo** (alternate L/R per tick for
width from mono).

**Pitch-shifted SFX reuse:** one ROM sample played at different rates (jump → up for
mini-hop, down for heavy landing) — ROM savings + variety. One step-multiply/tick
when pitch ≠ 1.

**Independent DAC volume** separate from FM/PSG levels.

**Internal precision:** mix at >8-bit precision and **dither** down to the 8-bit DAC
(portable kernel of the Amiga 14-bit idea).

## 6. FM / PSG Synthesis

**From Batman (the "alive" texture):**
- **Dual per-channel data streams** — a note stream (arpeggio, portamento targets,
  patch/LFO changes) *and* an independent modulation/volume stream. Held notes
  evolve without retriggering.
- **True portamento** via a 16÷16 restoring division over a sub-semitone linear
  pitch table (128-entry).
- **Algorithm-aware software TL volume via self-modifying code** — carrier selection
  costs zero per-frame branching (pairs with the §7 carrier mask + log curve).

**Depth (Flamedriver-class and beyond):**
- **SSG-EG** (regs `$90–9F`) — evolving/buzzy envelopes (alarms, energy fields, pads).
- **LFO** (reg `$22`) + per-patch AMS/FMS (`$B4`). Hardware LFO is 8 global rates;
  per-channel vibrato uses software F-number modulation (modulation envelopes).
- **Ch3 special mode / CSM** — operator phase reset (click-free attacks, formants)
  and CH3-as-4-oscillators bonus voice (detuned unison, bells, inharmonic timbres).
- **Micro-detune unison/chorus** — driver-managed voice pairing spawns a detuned
  twin for fat leads/pads.
- **Vibrato / pitch-modulation tables, fast arpeggio chords.**

**PSG (Batman ignored it — we use it fully):**
- Noise-channel percussion, per-channel volume envelopes.
- **PSG pause silencing** — write `$9F,$BF,$DF,$FF` to `$7F11` on pause so tones
  don't sustain.
- *Optional* offline-encoded **PSG-as-PCM aux channel** (pcmenc Viterbi) — a 4th
  "PCM-ish" voice off the DAC. *Spike: Genesis Z80 playback cost unverified.*

**Raw-register escape hatch** (Echo-style) so sound designers can drive any YM/PSG
register directly.

## 7. Audio Quality & Correctness Details

Cross-cutting low-cost wins, several from Batman/Zyrinx:

- **Logarithmic volume curve** — 256-byte LUT mapping linear → perceptual
  attenuation. Zero runtime cost; the single easiest quality win.
- **Per-algorithm carrier mask** — 8-byte table giving the carrier-operator bitmask
  per FM algorithm (algo 0–3 = op4; 4 = ops 2,4; 5–6 = ops 2,3,4; 7 = all). Volume
  changes touch only carriers, never modulators (preserves timbre). Essential for
  the log curve to not distort patches.
- **DC offset removal** — subtract a per-sample precomputed DC bias before reg `$2A`
  output; eliminates boundary pops/clicks. One subtract/tick. Paired with a
  **build-time DC-offset tool** that computes the bias per sample.
- **Frequency-based FM panning** (NOVEL, zero-cost composition convention) — pan FM
  channels by register: high melody → R, mid → C, bass → L; widens the FM image with
  no CPU/Z80 cost.

## 8. Tempo, Timing & Z80 Performance

- **YM Timer sub-frame tempo** (Timer A, regs `$24-$25`, polled) as the timebase
  instead of VBlank counting → sub-frame precision, NTSC/PAL-independent by
  construction; **lag frames become irrelevant to music tempo**. (Batman uses Timer
  B; TF4 Timer A — either works.)
- **Bank-switch optimization** — pack samples contiguously per-section in ROM;
  bank-aware sample table skips the switch when the current bank matches; build
  pipeline verifies no sample crosses a 32 KB boundary. Saves 100+ cycles/switch.

## 9. Engine Integration & Game-Feel Layer (the part that beats Flamedriver)

These tie audio into section streaming and game state — marked NOVEL in §6, shipped
by no commercial Genesis game.

- **Section-aware sound banking** — `sec_music` / `sec_sound_bank` in section defs
  trigger music/sample-set swaps per section (outdoor→nature, cave→drips,
  boss→percussion). `Section_Preload` pre-loads the next section's bank before
  teleport (zero gap). **Conditional bank swaps** from game state (boss→heavy perc,
  water→echo, speed shoes→high-energy).
- **Music fade state machine** — `IDLE → FADING_OUT → SWITCHING → FADING_IN`
  (+ `STINGER_PLAY`). Per-section `sec_music_fade_type`: `FADE_CUT` /
  `FADE_CROSSFADE` (30–60 frame Z80 volume-envelope crossfade) / `FADE_STINGER`.
  Runs in the main loop alongside palette cross-fade so audio + visual transitions
  align at teleport.
- **Distance-based attenuation + priority SFX mixing** —
  `volume = max − distance×falloff`, made perceptual by the §7 log table. Distant
  enemies audible before visible (audio foreshadowing); explosions fade with
  distance. Simultaneous SFX ranked by priority (explosion > enemy > pickup > UI) so
  a close explosion dominates a distant ring. ~1 subtract + lookup per
  `PlaySoundLocal`; ~20 cycles 68k for ranking.
- **Procedural ambient soundscape** (NOVEL) — per-section `sec_ambient_pool`; a Z80
  LFSR random trigger plays a random low-volume sample every 0.5–3 s, decoupled from
  music. ~50 bytes Z80. Each section becomes a distinct auditory environment.
- **Continuous SFX** — looped-while-held sounds (spindash charge, shield buzz, speed
  shoes) in a dedicated slot (`PlaySoundContinuous`/`StopSoundContinuous`), separate
  from the one-shot SFX queue.

## 10. Data Format & MegaDAW Compiler

**Direction (settled here):**
- A **compact event-list format** (Echo/XGM family) extended for our features: dual
  data streams, portamento/modulation commands, DAC triggers, per-channel pan
  automation, adaptive-FM6 hints, section-bank/fade/ambient metadata.
- VGM used only as an *import/authoring* source, never the runtime format.
- **MegaDAW becomes the compiler**: authors and emits our event-list format and
  encodes samples (BRR / DPCM / PSG-PCM) and DC-offset biases at build time —
  consistent with the engine's build-time-computation philosophy.

**Design principles (constrain the later spec):**
- **Runtime format optimized for Z80 playback speed, not authoring convenience** —
  the two are decoupled. MegaDAW's internal model can be rich; the emitted bytes are
  whatever the Z80 reads fastest (minimal branching, byte-aligned dispatch).
- Variable-length events; common events get short opcodes (entropy-coded by
  frequency, like Echo's `$D0–DF` short delays).
- Loop/jump/SFX-channel-lock semantics first-class (the reason event lists beat
  VGM).
- Self-describing enough that the **build pipeline can validate** it (no sample
  crosses a bank boundary, every referenced instrument exists, etc.).

**The concrete format is a deferred sub-design** (see §12.7) — opcode table, byte
layout, dual-stream encoding. It should follow the engine's needs, not lead them;
locking it before Phases 3–4 risks designing it twice.

## 11. Explicitly Rejected (debunked in research — do not pursue)

- "5 extra PCM channels via FM TL registers" — write bandwidth too low.
- Real-time Z80 sample interpolation — no cycle budget; raise source rate instead.
- Granular/wavetable software synthesis on Z80 — use real FM (Ch3) instead.
- 68k-assisted DAC mixing — breaks Z80 autonomy (our goal); fallback only.
- Pier Solar "cart streaming" — myth; it is plain Sega CD Red Book audio.

## 12. Phased Decomposition

Too large for one plan. Each phase → its own plan → implement → verify (Exodus MCP)
→ merge. Every phase produces something audible and verifiable.

- **Phase 1 — Foundation.** Z80-autonomous shell, direct-injection mailbox +
  verified writes, Timer-driven cooperative scheduler, single-channel high-quality
  DAC + read-ahead DMA-survival buffer + YM write-queue, minimal FM sequencer +
  basic patch load + **log volume curve + carrier mask + DC-offset removal**, basic
  PSG + pause silencing. Goal: a clean tone + a drum sample that does not scratch
  under DMA. **First plan targets this.**
- **Phase 2 — DAC powerhouse.** N-channel mixer, quality-adaptive single↔mix,
  stereo/pseudo-stereo PCM, pitch-shifted SFX, half-rate samples, BRR codec (after
  spike), >8-bit internal mix + dither, bank-switch optimization.
- **Phase 3 — FM depth.** Dual data streams, true portamento, SSG-EG, LFO, Ch3
  special/CSM, detune-unison, full PSG (+ optional PSG-PCM after spike), frequency
  FM panning convention, raw-register escape hatch.
- **Phase 4 — Adaptive FM6 slot.** Wire the three-mode content-adaptive slot across
  scheduler + mixer + sequencer.
- **Phase 5 — Engine integration & game-feel.** Section-aware banking, music fade
  state machine, distance attenuation + priority mixing, procedural ambient
  soundscape, continuous SFX.
- **Phase 6 — MegaDAW compiler.** Event-list format finalization, MegaDAW export
  re-target, sample/DC-offset encoders.
- **Stretch — Software echo/reverb** (Z80-RAM delay line), if budget remains.

### 12.x Deferred Sub-Designs (each gets its own focused design pass)

**Principle: design the contracts and the layouts up front; let the algorithms
emerge during implementation.** A thing deserves its own design pass when it is (a)
an *interface* between components, or (b) an on-disk / in-memory *layout* — because
those are expensive to change once code depends on them. Algorithms (the mixer
kernel, the portamento division, the LFSR ambient trigger) can be grown via TDD and
don't need a spec.

By that test, these are the sub-designs this spec implies — none should be frozen
now; each has a natural trigger point:

1. **68k↔Z80 command API** (interface) — the full command set the game posts:
   `PlayMusic`, `PlaySFX`, `PlaySoundLocal(distance,priority)`,
   `PlaySoundContinuous`/`Stop`, bank-swap, fade triggers; record layouts; the
   verified-write protocol. *Trigger: start of Phase 1* (everything depends on it).
2. **Z80 RAM memory map** (layout) — budget the tight 8 KB across read-ahead
   buffer(s), per-channel structs, mixer state, fade/ambient/SFX state, stack.
   *Trigger: start of Phase 1.*
3. **Instrument / patch format** (layout, MegaDAW-coupled) — how FM operator params +
   SSG-EG + LFO + algorithm + the dual-stream modulation/volume envelopes are stored
   and loaded; ties to MegaDAW's existing FM editor. *Trigger: Phase 3.*
4. **Sample pipeline & sample-table format** (layout + build tooling) — BRR/DPCM
   encoder, build-time DC-offset tool, per-section bank packing + boundary
   verification, the runtime sample table. *Trigger: Phase 2.*
5. **Runtime music event-list format** (layout) — the §10 concrete format. *Trigger:
   before Phase 6 (or a draft just before Phase 3 once FM features are locked).*
6. **Section-audio integration contract** (interface, existing-engine-coupled) — how
   `sec_music`/`sec_sound_bank`/preload hook into the section streamer, preload-vs-
   teleport timing, fade state machine ↔ palette cross-fade coordination. *Trigger:
   Phase 5, co-designed with the section system.*
7. **Scheduler cycle-budget policy** (partly spike §13.4) — how the Timer tick
   divides between mixer and FM halves, and the over-budget fallback. *Trigger: Phase
   1 plan, informed by the spike.*

## 13. Spikes Required Before Committing (measure, don't assume)

1. BRR decoder Z80 cost at target rate alongside N voices.
2. pcmenc PSG-PCM playback cost on the Genesis Z80 specifically.
3. Software echo tap cost alongside the mixer.
4. Achievable per-channel rate at 2/3/4 mixed voices given scheduler overhead.

## 14. Success Criteria

- Fully Z80-autonomous; 68k cost is mailbox writes only.
- A drum/sample stream that **does not audibly scratch** during worst-case Sonic DMA.
- Polyphonic samples (≥2 simultaneous) with per-channel volume/pitch.
- FM music with audibly evolving timbre (dual streams) and smooth portamento.
- Region-independent tempo (NTSC/PAL).
- The adaptive FM6 slot demonstrably switching among its three modes from data.
- Section-aware banking, fades, distance attenuation, ambient soundscape, and
  continuous SFX all working against the live section-streaming engine.
- Every line our own; no imported driver code.
- **Beats Flamedriver:** includes everything §6 planned to add to Flamedriver, plus
  the frontier mixer / DMA buffer / BRR / adaptive-FM6 it never had.
