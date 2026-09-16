# Controller reconciliation across the research slices

> Written by the aeon overseer, not by a research agent. Where two slices disagree, this is where the
> disagreement is settled — **by reading the source firsthand, not by picking the more convincing
> report.** Every claim below is labelled the same way the slices label theirs.

## R1. Is there a shipped SCROLLING corridor? Yes — exactly one, and it has a gating bug.

**The contradiction.** Slice 01 (S3K/S2) concluded *"every one of these swaps happens with the camera
pinned in a boss arena"* and *"its corridor is a moment in time, not a strip of level."* Slice 05
(online) reported Icecap Zone as *"the only S3K act transition with no screen lock"*, a genuine
scrolling corridor whose art *"visibly lags at speed."*

**Why both could be sincere.** Slice 01 read AIZ, HCZ and MGZ in depth, and for ICZ says *"I only read
the load line."* Its own evidence even held the clue: `Events_fg_5` is set by the results object for
every act 1 **except AIZ and ICZ**. Slice 05's ICZ evidence was the S3 Unlocked blog quoting code —
secondhand, not `sonic3k.asm` read directly. **So slice 01's "every swap is camera-locked" was a claim
about the zones it read, and slice 05's corridor claim had never met the disassembly.**

**Settled firsthand in `skdisasm/sonic3k.asm`:**

- **MEASURED — the trigger is a camera position, during live scrolling.** `ICZ1BGE_Normal` (≈110257):
  `cmpi.w #$6900,(Camera_X_pos).w`. On passing it queues ICZ2's secondary art and advances the routine,
  then falls through to `ICZ1_Deform` and `DrawBGAsYouMove`. **No boss arena, no results tally, no lock
  in the trigger.** The level keeps scrolling while the art loads.
- **MEASURED — the two queues use two different counters.** `Queue_Kos` (line 2802) increments
  `Kos_decomp_queue_count` (line 2808). `Queue_Kos_Module` (line 2667) tracks progress on the separate
  `Kos_modules_left` (lines 2704-2751). In `ICZ1BGE_Normal`, the **128×128 chunks and 16×16 blocks** go
  through `Queue_Kos`; the **8×8 tiles** (`ICZ2_8x8_Secondary_KosM`) go through `Queue_Kos_Module`.
- **MEASURED — Icecap gates the act switch on the chunks-and-blocks counter only.** `ICZ1BGE_Transition`
  (≈110283) opens with `tst.w (Kos_decomp_queue_count).w; bne.w loc_53938`, then `Load_Level`,
  `LoadSolids`, palette. **HCZ, by contrast, waits on `Kos_modules_left`** (slice 01, ≈105771) — the
  tile counter.
- **INFERRED — the gate can pass while tile modules are still pending.** `Process_Kos_Module_Queue`
  feeds modules into the decompression queue one at a time (lines 2735-2751: it checks
  `Kos_decomp_queue_count` for room and emptiness). Between two modules that counter can read zero
  while `Kos_modules_left` does not. That is consistent with — **not proven to be the cause of** — the
  reported art lag at speed; confirming it needs a running emulator.

**The design lesson, which is sharper than either slice alone.** The one shipped scrolling corridor
lags because **the layout switch is gated on the layout data being ready, not on the tiles that layout
references being resident.** Aeon's step-6 crossing wipe has the same exposure in principle: it assumes
every tile the new layout names is already in VRAM (slice 06, Q5). **So the wipe must not arm until the
new layout's tile set is resident — gate on the tiles, not the layout.** And slice 05's corridor-length
rule follows: length ≥ top speed × (decompression frames + upload frames), where raw-form pages drive
the decompression term to zero.

## R2. "One zone is as big as the foreground pool" vs "every S3K background fits in 376"

**Not a contradiction — two different populations, and the design must use the right one.**

- **Slice 06** decoded real zones at **604-965 (S2) / 698-2536 (S3K) unique tiles after flip-dedup —
  foreground AND background combined.** That is the foreground pool's problem, since the FG pool is 768.
- **Slice 01** split them per act, layout-referenced, flip-deduped, blank excluded. **Background-only:
  AIZ1 137, AIZ2 104 (+70 with fire), HCZ1 159, HCZ2 168.** Every one fits aeon's 376-tile BG block
  alone, and the same-zone PAIRS measured fit together: AIZ1+AIZ2 background 256, HCZ1+HCZ2 background
  373 against 376.
- **Slice 01's own caveat, carried:** those include never-visible layout areas and exclude
  animated-tile frames; MGZ, ICZ, LBZ and the S&K half were not measured.

**Consequence.** The **background** half of a same-zone handoff fits aeon's existing BG block without a
re-carve, on S3K's measured numbers. The **foreground** half is the budget problem, which is what the
held video-memory levers (steps 7 and 8) exist to address. **Cross-ZONE background pairs were not
measured by any slice** — that is still open, and it is the case the S2-or-S3-in-one-act showcase needs.
