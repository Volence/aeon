# Sound Driver Design — Best-on-Platform Z80-Autonomous Audio Engine

**Date:** 2026-06-16
**Status:** Design approved, ready for plan decomposition
**Branch:** `design/sound-driver`

## 1. Purpose & Ambition

The s4_engine writes every subsystem from scratch. Audio is currently the only
place the architecture planned to import outside code (Flamedriver). This design
replaces that plan: we build our **own** Z80-autonomous sound driver, fully ours,
targeting **best-on-the-platform** quality with no compromise — a full DAC
powerhouse *and* deep FM synthesis.

The central finding from research (see §2) is that **the best-in-the-world
Genesis driver does not exist yet.** Every existing driver — hobbyist (Mega PCM,
Flamedriver, XGM2, Echo, MDSDRV) and commercial legend (Technosoft's Thunder
Force IV, Treasure's Gunstar Heroes, Jesper Kyd's Batman & Robin) — nails one
slice and leaves the rest. No driver has ever shipped the *union*. This engine is
that union.

MegaDAW becomes the authoring tool / compiler for the driver's data format. We do
not constrain the design to any existing format (SMPS/VGM); MegaDAW re-targets to
ours.

## 2. Research Basis

All eight reference disassemblies were examined, including the four commercial Z80
sound blobs that were previously opaque binary data. A custom Z80 disassembler was
written (`docs/research/z80_blobs/z80dasm.py`) and the blobs extracted and
analyzed:

- **Batman & Robin** (Jesper Kyd) — full reverse-engineering in
  `docs/research/z80_blobs/batman_driver_analysis.md`. The source of several
  pillars below.
- **Gunstar Heroes / Alien Soldier** (Treasure), **Thunder Force IV** (Technosoft)
  — listings in `docs/research/z80_blobs/*.lst`.
- Modern/online frontier survey (Mega PCM 2.1, XGM2, Echo, MDSDRV, DualPCM,
  Kabuto hardware notes, Furnace YM2612 docs, pcmenc, SNES BRR) with citations
  retained in the research agents' reports.

**Key findings that shaped this design:**

1. The legends were **all single-channel DAC** — none mixed. Their edge was
   encoding (Gunstar's packed-accumulator DPCM), per-sample rate, and
   architecture, not raw channel count. Multi-channel mixing combined with
   DMA-survival buffering is genuinely **unexplored territory**.
2. **Batman's architecture** is distinct from every other driver: a
   resumable-coroutine DAC scheduler clocked by YM Timer B, dual per-channel data
   streams (note + independent modulation/volume), true division-based portamento,
   and dynamic FM6 reclamation. This is *why* that soundtrack sounds alive.
3. **Mega PCM 2.1** (released 2026-05-10) is the single-channel quality king
   (read-ahead ring buffer survives 24 KB DMA, cycle-exact loops, ~32 kHz,
   DPCM-HQ) — but it does **no mixing** and is DAC-only.

## 3. Hardware Constraints (the immovable budget)

These bound every decision below and must be respected, not wished away:

- **FM6 and the DAC are mutually exclusive.** YM2612 reg `$2B` bit 7 swaps FM
  channel 6's output for the 8-bit value written to reg `$2A`. There is no 7th
  voice. Every "DAC channel," single or mixed, shares this one output.
- **The Z80 (3.58 MHz) is a single shared budget** for DAC feeding/mixing *and*
  FM/PSG sequencing. Cost scales with DAC channel count × sample rate. Reference
  point (XGM): ~4 PCM voices @ ~14 kHz ≈ 70% of the Z80. You cannot have a
  maximal mixer *and* maximal FM simultaneously — something gives.
- **YM2612 register write speed is capped** (~1 write per ~33.6 Z80 cycles; the
  internal shift register makes faster/word writes unreliable). A write-queue is
  mandatory so the mixer never stalls on the chip.
- **68k→VDP DMA freezes the bus**, starving any Z80 loop that reads sample bytes
  from ROM mid-transfer — the classic "scratchy DAC." Must be mitigated by
  read-ahead buffering (see §5).
- **Z80 RAM is 8 KB**, bounding buffer sizes and any echo/delay line length.

## 4. Architecture

### 4.1 Z80 Autonomy & 68k Handoff

The entire engine runs on the Z80; the 68k only posts commands. Handoff uses
Batman's **direct-injection mailbox**: the 68k writes whole command records
straight into Z80 RAM (channel-start records, DAC trigger blocks) plus an atomic
"dirty" flag the driver latches and clears each tick. Zero opcode parsing, lowest
possible latency. (Batman `$16EA`/`$17EA` staging model.)

### 4.2 Cooperative Scheduler

Backbone is **Batman's resumable-coroutine model**, generalized:

- A YM **Timer** (sub-frame, NTSC/PAL-independent — see §7) is the master tick.
- Between ticks, the DAC engine runs as a near-100%-duty background task feeding
  reg `$2A`. When the timer overflows, the engine **breaks out, services the
  FM/PSG sequencer, reloads the timer, and resumes** the DAC mid-stream.
- The FM update is **split across ticks** (Batman runs two halves on alternating
  ticks) to balance load.

This keeps the sample stream continuous (smooth, dense percussion/ambience) while
giving FM a steady sub-frame cadence — distinct from Mega PCM's ISR model and
XGM2's sample-rate ISR. It is a third architectural model, and the right one for a
streaming Sonic engine.

### 4.3 The Adaptive FM6/DAC Slot (first-class pillar)

FM6 is a **content-adaptive slot**; the engine selects mode automatically from
what the composer's data contains. This is novel — no existing driver offers all
three:

| Composer content | FM6 behavior |
|---|---|
| FM6 melody, little/no DAC | Full **6th FM synth voice** |
| FM6 melody **and** DAC samples | **Time-share** (Batman): synth in gaps, DAC per hit |
| **No FM6 melody** | **Permanent N-channel DAC mixer** — costs zero melodic voices |

- Mode is driven by data, evaluated per song/section.
- Reclamation is the Batman trick: drop DAC mode (`$2B=$00`) the instant no sample
  is active, returning FM6 (and its Z80 cycles) to the sequencer.
- Trade-off, stated honestly: in the time-share mode, each sample briefly
  interrupts any concurrent FM6 note (imperceptible for short hits; Batman accepts
  it). In always-on-mixer mode there is no FM6 melody to interrupt, so no conflict.
- This design *minimizes* the §3 cycle cost: DAC cycles are spent only when
  samples are actually sounding, unlike a static always-on mixer (XGM) that pays
  forever.

Contrast with classic Sonic/SMPS, which dedicates FM6 to the DAC permanently
(music effectively gets 5 FM voices + DAC). [Exact stock behavior to be confirmed
against our Flamedriver source during planning; not load-bearing for this design.]

## 5. DAC Subsystem

**Quality-adaptive output:**
- **1 active sample** → highest-class single-stream path: up to ~32 kHz with
  Kabuto/Mega-PCM-grade jitter control (timing model accounts for ROM-access
  contention).
- **2–N active samples** → software mixer: sum signed bytes, clamp via a
  precomputed saturation **LUT**, write the single result to reg `$2A`.
  Per-channel volume and pitch (per-sample `djnz` delay / phase accumulator).
  Per-channel rate scales down as count rises (the §3 budget).

**DMA-survival read-ahead buffer (mandatory):** a Z80-RAM ring buffer pre-filled
from ROM during safe windows, drained during DMA so the DAC never reads ROM
mid-transfer. Target: survive Sonic's worst-case per-frame DMA. (Mega PCM 2 /
DualPCM model.) This is the single highest-payoff quality feature and what
separates us from every classic SMPS game.

**YM write-queue:** decouples the mixer from the chip's ~33.6-cycle write limit.

**Compression:**
- **BRR-style codec** (SNES-derived, 9 bytes / 16 samples, cheap add/shift
  predictor decode) as the primary format — better fidelity-per-byte than 4-bit
  DPCM. *Spike required:* measure Z80 decode cost at target rate alongside N
  voices (flagged unproven on Z80 in research).
- **Gunstar-style packed-accumulator DPCM** as a lighter-weight alternative.

**Stereo PCM:** per-sample L/R enable flips (reg `$B6`) for panned/moving samples
and time-interleaved stereo — almost no Sonic-era driver does real PCM panning.

**Internal precision:** mix at >8-bit precision and **dither** down to the 8-bit
DAC to reduce quantization hiss on quiet passages (portable kernel of the Amiga
14-bit idea).

## 6. FM / PSG Synthesis

**From Batman (the "alive" texture):**
- **Dual per-channel data streams** — a note stream (arpeggio, portamento targets,
  patch/LFO changes) *and* an independent modulation/volume stream. Held notes
  evolve without retriggering. This is the structural source of evolving timbre.
- **True portamento** via a 16÷16 restoring division over a sub-semitone linear
  pitch table (128-entry) — smooth analog glissando.
- **Algorithm-aware software TL volume via self-modifying code** — carrier
  selection costs zero per-frame branching.

**Depth Batman skipped, layered on top (Flamedriver-class and beyond):**
- **SSG-EG** (regs `$90–9F`) — evolving/buzzy envelopes.
- **LFO** (reg `$22`) + per-patch AMS/FMS (`$B4`).
- **Ch3 special mode / CSM** — operator phase reset for click-free attacks and
  formant/percussion textures; CH3-as-4-oscillators bonus voice.
- **Micro-detune unison/chorus** — driver-managed voice pairing/stealing spawns a
  detuned twin for fat leads/pads.
- **Vibrato / pitch-modulation tables, fast arpeggio chords.**

**PSG (Batman ignored it entirely — we use it fully):**
- Noise-channel percussion, per-channel volume envelopes.
- *Optional* offline-encoded **PSG-as-PCM aux channel** (pcmenc Viterbi approach)
  — a 4th "PCM-ish" voice that doesn't touch the DAC. *Spike required:* playback
  cost on the Genesis Z80 is unverified.

**Raw-register escape hatch** (Echo-style `$F8/$F9`-equivalent) so sound designers
can drive any YM/PSG register directly for one-off effects.

## 7. Tempo & Timing

YM **Timer-driven sub-frame tempo** (Batman uses Timer B; TF4 uses Timer A). This
gives finer-than-frame resolution and **NTSC/PAL independence by construction** —
superior to VBlank-locked tempo. Region differences become a timer reload value,
not a double-update hack.

## 8. Data Format & MegaDAW Compiler

- A **compact event-list format** (Echo/XGM family) extended for our features:
  dual data streams, portamento/modulation commands, DAC triggers, per-channel
  pan automation, and the adaptive-FM6 hints.
- VGM is used only as an *import/authoring* source, never as the runtime format
  (raw register logs are large and carry no loop/SFX/instrument semantics).
- **MegaDAW becomes the compiler**: it authors and emits our event-list format and
  encodes samples (BRR / DPCM / PSG-PCM) at build time — consistent with the
  engine's build-time-computation philosophy.

## 9. Explicitly Rejected (debunked in research — do not pursue)

- "5 extra PCM channels via FM TL registers" — write bandwidth too low
  (community-rejected).
- Real-time Z80 sample interpolation — no cycle budget; raise source rate instead.
- Granular/wavetable software synthesis on Z80 — use real FM (Ch3) instead.
- 68k-assisted mixing — breaks Z80 autonomy (our explicit goal); fallback only.
- Pier Solar "cart streaming" — myth; it is plain Sega CD Red Book audio.

## 10. Phased Decomposition

This is too large for one implementation plan. It decomposes into phases, each
getting its own plan → implementation → verify → merge cycle. Phasing is chosen so
every phase produces something audible and verifiable on hardware (Exodus MCP).

- **Phase 1 — Foundation.** Z80-autonomous shell, direct-injection mailbox,
  Timer-driven cooperative scheduler, single-channel DAC (high-quality path) with
  read-ahead DMA-survival buffer + YM write-queue, minimal FM sequencer (note
  on/off, basic patch load), basic PSG. Goal: a clean tone + a clean drum sample
  that does not scratch under DMA. **First plan targets this.**
- **Phase 2 — DAC powerhouse.** N-channel software mixer, quality-adaptive
  single↔mix switching, stereo PCM panning, BRR codec (after spike), >8-bit
  internal mix + dither.
- **Phase 3 — FM depth.** Dual data streams, true portamento, SSG-EG, LFO, Ch3
  special, detune-unison, algorithm-aware SW volume, full PSG (+ optional PSG-PCM
  after spike).
- **Phase 4 — Adaptive FM6 slot.** Wire the three-mode content-adaptive slot
  across scheduler + mixer + sequencer.
- **Phase 5 — MegaDAW compiler.** Event-list format finalization, MegaDAW export
  re-target, sample encoders.
- **Stretch — Software echo/reverb** (Z80-RAM delay line), if budget remains.

## 11. Spikes Required Before Committing (measure, don't assume)

These were flagged unverified in research and need a cycle-cost measurement
(Exodus MCP is ideal) before their feature is locked:

1. BRR decoder Z80 cost at target rate alongside N voices.
2. pcmenc PSG-PCM playback cost on the Genesis Z80 specifically.
3. Software echo tap cost alongside the mixer.
4. Achievable per-channel rate at 2/3/4 mixed voices given our scheduler overhead.

## 12. Success Criteria

- Fully Z80-autonomous; 68k cost is mailbox writes only.
- A drum/sample stream that **does not audibly scratch** during worst-case Sonic
  DMA (the headline quality bar).
- Polyphonic samples (≥2 simultaneous) with per-channel volume/pitch.
- FM music with audibly evolving timbre (dual streams) and smooth portamento.
- Region-independent tempo (NTSC/PAL).
- The adaptive FM6 slot demonstrably switching among its three modes from data.
- Every line our own; no imported driver code.
