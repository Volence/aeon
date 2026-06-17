# Sound Driver — Plan 1B Design: DMA-Survival Single-Channel DAC

**Date:** 2026-06-16
**Status:** Design approved, ready for plan
**Branch:** `feat/sound-1b`
**Extends:** master spec `2026-06-16-sound-driver-design.md` §5 (DAC subsystem), §8 (banking),
and §12 "Plan 1B". Builds on Phase 1 Foundations (merged) + the 1A refinement (per-type
mailbox slots, build-time tempo, interrupt-free Foundations driver).

## 1. Goal

Make the single-channel DAC **production-grade**: it plays real samples streamed from ROM
banks and **never gaps, scratches, or corrupts** under Sonic's heavy, bursty section-
streaming / PLC DMA. This is the prerequisite for Phase 2's multi-channel mixer (you can't
safely mix multiple streams until one stream survives DMA).

## 2. Research basis

Two deep research passes (local cracked blobs + modern homebrew docs, 2026-06-16) plus the
1A retrospective audit. Key confirmed facts driving the design:

- **68k↔Z80 RAM access requires holding the bus** (reads garbage, writes ignored otherwise)
  — real hardware, gen-hw.txt / plutiedev.
- **Reading ROM during a 68k→VDP DMA can corrupt the DMA** (address-bus glitch) → corrupted
  VRAM/art, and potentially RAM. This is *why* the engine stops the Z80 around DMA today.
- **No local reference driver buffers the DAC** — Batman/Flamedriver/Gunstar/TF4 all read ROM
  directly and either dodge heavy DMA (Batman) or scratch. The read-ahead buffer exists in no
  local disassembly; we build it from the Mega PCM / DualPCM model and verify on hardware.
- **Mega PCM blind-pre-buffer mechanics** (from its source): 256-byte page-aligned ring,
  single `inc l` advance, "high-byte = ring-full" check, 2:1 fill-ahead, drain-during-VBlank
  loop that reads no ROM. Survives ~24 KB DMA/frame.
- **The Genesis asserts the Z80 /INT during VBlank** automatically — the Z80 can take a
  VBlank interrupt with no 68k cooperation.
- **Bank switch** = 9 serial writes to `$6000`, 162 cycles (27 when cached no-op); never switch
  mid-sample.

## 3. Foundation decision (approved): continuous-buffer DAC

**The Z80 keeps running during DMA; the DAC always plays from a Z80-RAM ring buffer.** The
alternative — keep stopping the Z80 around DMA (today's behaviour) — freezes the DAC during
every art load → audible gaps/stutter. That fails the entire point of 1B.

**Art quality is unaffected, sound quality strictly improves.** Today's `stopZ80` is a *blunt
lock* (freeze the Z80 so it can't touch the shared bus and glitch the DMA). We replace it with
a *precise discipline*: the Z80 keeps running but, during the DMA window, touches only Z80 RAM
(the buffer) and the YM2612 — both on the Z80's own bus, never the shared cartridge bus the DMA
uses. So it can't glitch the DMA (art loads correctly), doesn't steal VDP/68k bandwidth (same
tiles/frame), and the DAC keeps playing. The cost is a **hard correctness requirement** (the Z80
must *never* read ROM during the DMA window) — a bug there fails loud (corrupt tiles / silence),
not as silent quality erosion, so it is catchable and hardware-verifiable.

## 4. Architecture

### 4.1 Ring buffer + two playback modes

- **Ring buffer:** 256 bytes, page-aligned at Z80 `$1700` (already reserved in the RAM map).
  Playback pointer is a low byte → `inc l` advance wraps the page for free. Read-ahead (fill)
  pointer chases it; the gap (high-byte delta) is the "ring full" check (Mega PCM trick).
- **The DAC always drains from the ring**, never from ROM directly. Two modes:
  - **FILL+PLAY** (active display): each output cycle, write one ring byte to YM reg `$2A` *and*
    read-ahead from ROM into the ring (2:1 until full, then 1:1).
  - **DRAIN** (VBlank/DMA window): write ring bytes to `$2A`, **read no ROM**. Rides the buffer's
    lead through the DMA.

### 4.2 DMA-window signalling — flag + IRQ hybrid (decided)

- A `DMA_ACTIVE` byte in Z80 RAM (status region). The 68k sets it before its DMA and clears it
  after (see §4.3).
- The **Z80 VBlank interrupt** (hardware-asserted at VBlank start) is the *entry*: its ISR flips
  the driver into DRAIN mode immediately — before the 68k's DMA begins — so entry is race-free.
- The **`DMA_ACTIVE` flag is the *exit*:** the Z80 resumes FILL+PLAY the moment it reads the flag
  clear (68k finished DMA) — precise, no over-draining.
- This re-introduces Z80 interrupts (reversing the 1A `im1` drop — now with purpose): `im 1`,
  `ei`, a small VBlank ISR. (Chosen over flag-only because corruption is the failure mode and
  the IRQ removes a timing assumption for little cost.)

### 4.3 `VInt_Level` change (the one cross-cutting engine edit)

- The DMA wrap in `engine/vblank.asm` changes from `stopZ80 … <DMA> … startZ80` to
  `set DMA_ACTIVE=1 … <DMA> … clear DMA_ACTIVE=0`. Same structure; instead of *freezing* the Z80
  we *signal* it. The rest of VInt is untouched. `DMA_ACTIVE=1` must be set before the *first*
  DMA of the frame and cleared only after the *last*.
- **s4lint:** the E006/E011 rule (which enforces "stopZ80 before VDP DMA") is refined to recognise
  the new model — the Z80 self-disciplines via `DMA_ACTIVE`; the 68k no longer stops it for the
  sound-streaming case. Document the new invariant so the rule (and future code) understands it.
- **VInt_Lag** path must set/clear `DMA_ACTIVE` around its Critical DMA too.

### 4.4 Banking

- `SetBank` routine, Batman-cached: compares the requested bank to a cached `Z80_CurBank`, returns
  in ~27 cycles if unchanged, else writes the 9-bit latch to `$6000` (~162 cycles) and updates the
  cache.
- **Banking happens only on the fill path, never the DAC drain path.** The DAC consumer reads only
  the ring, so banking never touches the audio-critical loop.
- **Samples are bank-aligned at build time:** the build tool packs samples so none crosses a 32 KB
  bank boundary (a `fatal` if one would), so there is never a mid-sample bank switch to stall audio.

### 4.5 Sample format + 68k API + real samples

- **8-byte ROM-resident descriptor** per sample, indexed by id:
  `bank(1), rate(1), ptr(2, Z80-window ptr), length(2), loop_ofs(2)` (loop_ofs 0 = one-shot).
- **68k API:** unchanged from 1A — the 68k posts a **sample id** into the `SND_REQ_SAMPLE` slot.
  The Z80 looks up the descriptor, calls `SetBank`, primes the ring, and plays. (The table is ROM-
  resident, so the 68k sends only the id — lighter than injecting the whole record.)
- **Real samples:** replace Foundations' generate-in-RAM sawtooth with a real DAC sample migrated
  from `sonic_hack/sound/DAC/` as the first streamed sample (a drum hit).

### 4.6 Cycle-balanced playback (the main sound-quality lever)

- Foundations feeds one byte per cooperative-loop iteration → the per-sample spacing jitters with
  whatever else the loop did → warbly pitch. 1B restructures output so the **per-sample cycle
  budget is constant** regardless of fill / mailbox-poll / scheduler-tick work — Batman's
  resumable-coroutine done rigorously, Mega PCM's cycle-balanced loops (all branch paths padded to
  equal cost). Fill and housekeeping happen *within* the fixed per-sample window, not between
  samples at variable cost.
- This is the trickiest part and the difference between a clean tone and a warbly one.

## 5. Scope (decided)

- **YM write-queue: deferred to the FM phase.** 1B is DAC-only; the DAC writes `$2A` at the
  playback cadence, well within the chip's rate limit. The write-queue decouples *FM* writes — it
  belongs with FM (Phase 1C/2), not here. Pulling it out of 1B trims it with zero loss.
- **Raw 8-bit PCM first; BRR compression deferred.** Get the streaming spine (buffer + banking +
  fill/drain + cycle-balanced output) rock-solid with the simplest sample format, then add BRR as a
  follow-on — BRR decode interacts with the fill path and adds cycle cost worth measuring on its own.

## 6. Success criteria

- A real ROM-streamed drum/SFX plays cleanly, **with no audible gap, scratch, or warble during
  worst-case Sonic DMA** (verified on Exodus under a heavy section-load frame).
- **No art corruption** under that same heavy-DMA frame (the discipline holds — verified by VRAM
  inspection + visual check).
- The DAC output rate is steady (cycle-balanced) — clean pitch.
- The driver remains fully Z80-autonomous; the 68k's only added cost is the `DMA_ACTIVE` flag
  set/clear (cheaper than the `stopZ80`/`startZ80` it replaces).
- Looping samples loop seamlessly; one-shots stop cleanly.

## 7. Spikes / open items (measure, don't assume)

1. **Buffer size vs peak DMA.** 256 bytes covers ~24 KB DMA at Mega PCM's rate; confirm against our
   actual worst single-frame DMA byte count (Exodus profiler / `Lag_Frame_Count`) at our chosen DAC
   rate. Resize the reserved buffer region if needed (growth reserve at `$1800` exists).
2. **Cycle budget** of the FILL+PLAY loop (output + 2 ROM reads + housekeeping) at the target DAC
   rate — confirm it fits and stays balanced.
3. **Z80 VBlank IRQ timing** — verify on hardware the ISR enters DRAIN before the 68k's first DMA in
   the worst case.

## 7b. Implementation evolution (as-built, 2026-06-17)

The implementation diverged from §4.2/§4.6 in two research- and hardware-driven ways; this
section is the as-built source of truth:

- **DMA-window signalling → research-refined to the Mega PCM zero-stop model + a 68k DMA-done
  ack.** The 68k no longer `stopZ80`s around its DMA (gated out in `VInt_Level`/`VInt_Lag` under
  `SOUND_DRIVER_ENABLED`); the Z80 keeps running. The Z80's hardware VBlank interrupt (RST $38,
  reserved at Z80 `$0038` via a `rept db 0` gap) flips it into DRAIN mode race-free. The Z80
  drains until the 68k sets a one-byte **DMA-done ack** (`SND_CTRL_DMA_ACTIVE` at `$1F04`, written
  bus-held at the end of the VInt DMA pipeline) — so the drain adapts to the *actual* DMA length
  each frame. The planned standalone `DMA_ACTIVE`-as-entry flag was dropped.
- **Cycle-balanced playback → replaced by YM Timer-A-paced output.** Rather than hand-balance the
  FILL and DRAIN loops to equal per-sample cost (fragile), the main loop outputs exactly one ring
  byte per **Timer A overflow** and does the variable fill/drain work in the slack before the next
  tick. Output cadence == the timer (constant pitch ~13.3 kHz) regardless of fill cost, fill-vs-
  drain mode, or DMA load. The VBlank ISR is minimal (flip to DRAIN + reset ack + per-frame
  mailbox poll). Residual: ~±4–8 µs poll-granularity jitter; a fully poll-free cycle-counted loop
  is the further refinement if that floor proves audible.
- **Real sample → clearly-TEMP synthetic raw-PCM blip.** The `sonic_hack` DAC samples are DPCM-
  compressed (decoding them is deferred content work, user-driven); 1B streams a throwaway clean
  blip to exercise the engine. Single sample uses build-time constants, not the descriptor table.

## 8. Decomposition

A single coherent plan, but the natural task order is: ring buffer + cycle-balanced drain (RAM
source) → ROM fill path + banking → `VInt_Level` DMA_ACTIVE signalling + Z80 VBlank ISR → sample
table + real sample → heavy-DMA hardware verification. Each step is build- and hardware-verifiable.
