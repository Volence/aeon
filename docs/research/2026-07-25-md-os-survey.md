<!--
Research artifact. Produced 2026-07-25 by a 5-agent survey of MarkeyJester's MD-OS
(/home/volence/sonic_hacks/MD-OS), a homebrew Mega Drive desktop OS in pure 68000.
Verified against this codebase before saving:
  - dma_queue.emp streams 14-byte DMAEntry records from RAM to VDP_CTRL, so the
    trigger-word-from-ROM hazard cannot apply here - CONFIRMED, no action
  - engine/system/math.asm holds GetSineCosine and nothing else - CONFIRMED
  - engine/system/vectors.asm:40-47 routes all 16 TRAPs to ErrorTrap - CONFIRMED
  - engine/debug/error_handler.asm:74-200 is a precompiled dc.l blob - CONFIRMED
This is a CANDIDATE survey, not a directive. LICENSING: MD-OS ships with no license
file, no copyright notice, and no permission grant anywhere in its tree. Techniques
may be read and reimplemented. Code must not be copied.
-->

# MD-OS technique survey

*Date: 2026-07-25. Prompted by "anything worth checking out for our docs or engine".*

## Verdict: take nothing

MD-OS is a preemptive microkernel and a compositing window manager that happens to run
on the same silicon as Aeon. It is worth reading for craft. It is not worth mining for
parts. Every subsystem is either strictly worse than what we already have or answers a
question a scrolling platformer does not ask.

Recorded so the survey does not get repeated:

- **Link System (its object allocator).** A fixed-size-slot pool with intrusive doubly
  linked lists plus a parent/child tree, 10 bytes of link overhead per slot. It pays
  that because it needs ORDERED iteration (z-order) and TREE structure. We need neither
  for gameplay objects, and `Free_Slot_Stack` (ENGINE_ARCHITECTURE §3.2) is cheaper on
  both axes. Do not adopt.
- **malloc/free.** A 256-byte-block bitmap allocator over a 32KB arena. We have no need
  for dynamic allocation, and it does not defragment: `R_HeapBlkCopy` is declared "a copy
  for reallocation" and referenced nowhere in the tree. The defragmenter was planned and
  never written.
- **Per-object message queues.** A 4-slot ring per widget plus a DefWindowProc table is
  the right shape for asynchronous user input. Our objects poke SST fields directly,
  which is far cheaper. A queue would be pure overhead.
- **Math.** No math library exists. Its `DivMul/` is a scratchpad ROM for arbitrary-
  precision (512-bit) mul/div, tens of thousands of cycles, uncommented. MD-OS itself
  uses `mulu`/`divu` freely at ~35 sites because a desktop OS has no frame budget. The
  one gap it could have filled, a fast 16/16 divide to retire the sanctioned `divs.w` at
  `engine/level/parallax.asm:355`, it does not: its divide is 128-bit and slower than
  `divu` for word operands.
- **The paint layer.** Its most impressive work and its least applicable. It turns Plane A
  into a linear 320x224 framebuffer costing $8C00 (35,840 bytes, 55% of VRAM) and then
  does damage-rectangle compositing with per-column occlusion culling. Damage rects
  assume a mostly static screen; ours scrolls every frame, so the damage region is always
  "everything". Architecturally incompatible, not merely expensive.

## Confirmations, not changes

- **The DMA trigger-word hazard does not apply to us.** MD-OS routes its final DMA
  control write through a RAM variable, annotated "last destination word RAM (due to bug
  on older hardware)": the classic workaround for the 68000 prefetching the trigger word
  out of ROM. We are immune by construction, because `dma_queue.emp` streams whole
  14-byte `DMAEntry` records from RAM to `VDP_CTRL`, trigger included. No action. Worth
  knowing the hazard exists so nobody "optimizes" a direct immediate write in later.
- **Immediate object deletion stays correct.** MD-OS defers `free` to VBlank
  specifically because a PREEMPTED thread could otherwise be interrupted mid-bitmap-
  update. We have no preemption, so the §3.2 justification for immediate deletion holds
  unchanged. This is confirmation of an existing decision, not a reason to revisit it.
- **Resource ownership tagging.** Its heap records carry an owning-thread tag so teardown
  is one sweep filtered by owner. We already do the equivalent with `entity_section_id`
  (§4.9.3). Independent arrival at the same pattern; no new information.

## The one idea worth banking

**Scanline-budgeted background work.** Not threading, which is overkill for us, but the
budgeting discipline underneath it.

MD-OS divides a fixed scanline allowance among all runnable threads
(`R_ThreadTime / R_ThreadCount`) and arms the H-interrupt at the resulting line, so the
CPU stolen from the compositor is BOUNDED no matter how many programs are open. The
default total is 22 scanlines. The transferable shape is: give a long-running task
exactly N scanlines per frame by arming the H-int at line N and taking control back,
rather than budgeting in units of work and hoping the units are uniform.

Where it could matter here: any incremental job whose per-unit cost is data-dependent and
therefore hard to budget by count. Tile-cache decompression is the obvious candidate,
since `BLOCK_DECOMP_BUDGET` currently budgets in blocks and a block's cost varies with
its compressed content.

Caveats, so this is not read as a recommendation:
- We already have the seams (§1.5 background work during idle, §1.8 H-blank dispatch),
  so this would be a change of budgeting UNIT, not new machinery.
- A resumable state machine gets most of the benefit at a fraction of the cost. The full
  `movem`/`usp`/user-mode switch is only needed if the work cannot be written as
  resumable, which ours can.
- MD-OS's version costs an H-interrupt per thread per frame, and grants only 22 scanlines
  total by default. The accounting is not free.
- Our tile-cache work runs in VBlank where there is no beam to budget against, so the
  mechanism would need rethinking for that consumer specifically.

Not proposed for the roadmap. Banked so the option is findable when a data-dependent
budget next causes trouble.

## Note for the wiki, not the engine

The genuinely valuable finds went to the wiki tracks, not here: exception stack-frame
decoding (M68K.md, the "When it crashes" page), TRAP as a road not taken (Flow & System),
Plane A as a framebuffer (GENESIS.md, the VDP page), and control-port peripheral
detection (Controllers, blocked on sources). See `empyrean/wiki/REFERENCES.md` for the
sourcing caveats, which are strict: MD-OS is emulator-developed and says so, so it is an
existence proof only and never a leg of the two-source rule.
