# DMA Queue Audit — Phase 0 of S2 Art & Compression Pipeline

Date: 2026-04-24

## Purpose

Audit our DMA queue implementation against all 7 reference disassemblies and community best practices before building the S4LZ compression pipeline, which will push larger art transfers through DMA.

---

## Reference Implementations

### 1. S.C.E. (Sonic Clean Engine) — Flamewing Ultra DMA Queue

**Source:** `Engine/Core/DMA Queue.asm`

This is the canonical Flamewing Ultra DMA Queue. Our implementation derives from it.

- **Entry format:** 14 bytes (DMAEntry struct), movep-based layout with pre-initialized VDP register numbers ($93-$97, $94)
- **Slots:** 18 (252 bytes at `DMA_queue`, calculated as `$12*7` words)
- **Enqueue:** ~184 cycles (single transfer), ~338 cycles (128KB split). 48 cycles on full queue discard
- **Drain:** Jump-table unrolled — `jmp .jump_table-DMA_queue(a1)`. Computes offset from slot pointer, jumps directly to the correct unrolled drain point. Zero branches per entry during drain
- **Priority:** None. Single flat FIFO queue
- **128KB safety:** Optional (`Use128kbSafeDMA`). S.C.E. enables it. Splits crossing transfers into two entries
- **VInt safety:** Optional (`UseVIntSafeDMA`). S.C.E. disables it (costs 46 cycles)
- **Static DMA:** `QueueStaticDMA` macro for compile-time-known transfers. 122 cycles when queued
- **Debug:** Separate `DMA Queue(Debug).asm` module raises error on overflow

**Key insight:** S.C.E. is the definitive Sonic community implementation. 18 slots is generous for a Sonic game; most frames use 3-6 entries (palette, sprites, character art, maybe animated tiles).

### 2. Batman & Robin — VDP Shadow Table (No Queue)

**Source:** `disasm/code/engine/vdp.asm`

Batman & Robin does NOT use a DMA queue at all. The VDP file is primarily collision/interaction routines, not DMA infrastructure. The game uses a different paradigm:

- **Approach:** VDP register shadow table stored in RAM ($F7D0-$F7F4 region). Registers are updated in RAM, then bulk-written to VDP during VBlank via sequential `move.w` writes
- **DMA:** Issued directly/inline where needed, not queued. Individual move.w sequences write VDP DMA registers ($93-$97) directly to the control port
- **Priority:** N/A (no queue)
- **128KB safety:** Not observed — art assets presumably aligned at build time
- **Tradeoff:** Simpler code (no queue overhead), but less flexible. Works because B&R has relatively fixed art layouts and uses its VDP shadow table for display-list-driven rendering rather than dynamic art streaming

**Key insight:** Shadow table approach works for games with static or predictable VRAM layouts. Not suitable for a Sonic engine where art streaming is dynamic and frame-varying.

### 3. Vectorman — Command Buffer with Counter

**Source:** `vectorman_disasm/code/disasm.asm` (around $7826-$78A0)

Vectorman uses a distinctly different DMA queue design, despite using 64x64 planes (same as our engine):

- **Entry format:** 14 bytes per entry, but stored as raw VDP register words ($8F02, $93xx, $94xx, source regs, dest command) — NOT movep-encoded
- **Queue structure:** Write pointer at `$E7FE` (long), count at `$E806` (word), backup pointer at `$E802`, backup count at `$E808`. Queue grows forward (pointer advances)
- **Enqueue:** Builds VDP commands directly: writes `$8F02` (auto-increment=2), then $93/$94 length regs, then source regs from ROM data, then destination command. Each entry is 14 bytes of raw VDP words
- **Capacity check:** Hard cap at 54 entries (`cmpi.w #$36, d2` where $36 = 54 decimal), plus a VRAM bandwidth check (`$B40` = 2880 words = 5760 bytes)
- **Drain:** Called via `jsr $899a` — processes entries by writing each 14-byte block sequentially to VDP control port
- **Rollback:** On overflow, restores write pointer and count from backup ($E802/$E808). This allows speculative enqueue with transactional rollback
- **Priority:** None (single queue)
- **128KB safety:** Not observed

**Key insights:**
1. The bandwidth cap (5760 bytes) is a hard budget — Vectorman actively prevents DMA overrun
2. Transactional rollback is clever: try to enqueue all of an object's tiles, if it doesn't fit, rollback all of them. Our implementation discards individual entries silently
3. 54 slots is far more than S.C.E.'s 18 — Vectorman streams many small sprite tiles

### 4. Gunstar Heroes — Reverse-Fill DMA Buffer

**Source:** `gunstar_disasm/code/disasm.asm` (around $0D36-$0F28, $12F4-$139A)

Treasure's approach is unique and extremely efficient:

- **Entry format:** 14 bytes (7 words), stored as raw VDP register word pairs: `$94xx/$93xx` (size), `$95xx` (src low), `$96xx` (src mid), `$97xx` (src high), `$8F02` (auto-inc), destination command
- **Queue structure:** Buffer at $F400, write pointer at $F70C, end pointer at $F70E. Queue grows BACKWARD (pre-decrement): entries are written using `-(a0)` moves, so the write pointer decreases from $F70C toward $F400
- **Drain:** In VBlank, reads from $F70C backward to $F400 with a simple forward loop: `move.l (a3)+, (a0)` x3 + `move.w (a3)+, (a0)` + `move.w (a3)+, (a0)` per entry. After drain, resets both pointers to $F400
- **Capacity:** Buffer is $F400 to $F70C = ~780 bytes = ~55 entries max. But many entries are hardcoded (palette, sprite table, scroll data) and written directly in the VBlank handler, not through the queue
- **Priority:** None, but Gunstar has FIXED DMA slots for specific subsystems. Lines $E0E-$E88 show hardcoded DMA commands for specific art banks (3 fixed DMAs for animated sprite banks, 4 for player sprites), separate from the general queue. This is effectively a manual priority system
- **128KB safety:** Not observed — Treasure probably guaranteed alignment at build time
- **Additional DMA slots:** Fixed slots at $84A0, $8560, $8500, $8478 for specific subsystem DMAs checked individually

**Key insights:**
1. Reverse-fill is genuinely clever: enqueue with pre-decrement writes (cache-friendly backward build), drain with sequential forward reads (bus-friendly sequential access)
2. Fixed DMA slots for known-at-compile-time transfers (our Static DMA system is similar)
3. Total DMA bandwidth is carefully partitioned: the VBlank handler has a specific order of fixed DMAs before draining the general queue

### 5. Alien Soldier — Reverse-Fill DMA Buffer (Nearly Identical to Gunstar)

**Source:** `aliensoldier_disasm/code/disasm.asm` (around $0DFA-$0F72, similar to Gunstar)

Alien Soldier shares the Treasure engine with Gunstar Heroes. The DMA system is structurally identical:

- **Entry format:** Same 14-byte raw VDP word format
- **Queue:** Same $F400 buffer, $F70C/$F70E pointers, reverse-fill approach
- **Drain:** Same forward sequential drain in VBlank, identical `move.l`/`move.w` pattern
- **Fixed slots:** More fixed DMA slots than Gunstar ($84A0, $8560, $8500, $8478), with conditional execution per slot
- **Notable difference:** Alien Soldier has additional per-slot conditional checks (`tst.w (a3)` before processing each fixed slot) and supports variable-size sprite DMAs configured by flag bits at $F7E7

**Key insight:** Alien Soldier's extreme optimization reputation comes from CPU-side code, not DMA innovation. The DMA system is inherited from Gunstar and sufficient — DMA is not the bottleneck in either game.

### 6. Thunder Force IV — Inline DMA Construction (No Queue)

**Source:** `thunderforce4_disasm/code/disasm.asm` (around $1956-$19D2)

Thunder Force IV does NOT use a DMA queue either. It constructs DMA commands inline:

- **Approach:** DMA parameters stored in RAM ($F100=length, $F102=source, $F106=dest). A subroutine at $1956 reads these, manually constructs VDP register words ($9300-$9700) using stack manipulation and byte extraction, then writes them directly to `$C00004` (VDP control port)
- **VDP register shadow:** Uses RAM mirror at $F0AA-$F0B4 for display configuration registers
- **Z80 coordination:** Stops Z80 before each DMA (`bsr.w $82C`), restarts after (`bra.w $840`)
- **Multi-layer management:** Multiple DMA subroutines ($1962, $19D2, etc.) for different VRAM targets — each constructs destination differently (`$804000` for VRAM-A, `$80C000` for VRAM-B)
- **Priority:** N/A — each layer's DMA is issued at a fixed point in the VBlank sequence
- **128KB safety:** Not observed

**Key insight:** TF4 manages its 4+ scroll layers by having dedicated DMA routines per layer with fixed ordering in VBlank. This is deterministic but inflexible. The DMA construction on the stack is wasteful compared to movep-based pre-initialized queues.

### 7. sonic_hack (Sonic 2 Modified) — Flamewing Ultra DMA Queue

**Source:** `code/engines/dma_queue.asm`

This is our Sonic 2 mod's DMA queue, also derived from Flamewing:

- **Entry format:** Same 14-byte DMAEntry struct as S.C.E.
- **Slots:** Same calculation as S.C.E. (18 slots)
- **Options:** `AssumeSourceAddressInBytes=1`, `Use128kbSafeDMA=1`, `UseVIntSafeDMA=0`
- **Drain:** Simple loop (`cmpa.w a1, a6; bls.s .done; move.l; move.l; move.l; move.w; bra.s .loop`) — NOT the S.C.E. jump table! This is the older, slower Sonic 2 drain style with a branch per entry
- **Static DMA:** Has `QueueStaticDMA` macro (same as S.C.E.)
- **128KB safety:** Enabled with full splitting

**Key insight:** Our sonic_hack build uses 128KB-safe enqueue but a loop-based drain instead of the jump table drain. This means every entry costs one extra branch (~10 cycles) compared to S.C.E.'s zero-branch drain.

---

## Comparison Table

| Feature | S.C.E. | Vectorman | Gunstar/AS | TF4 | sonic_hack | **Our Engine** |
|---|---|---|---|---|---|---|
| Queue type | Flat FIFO | Forward buffer | Reverse-fill | No queue | Flat FIFO | 3-priority sub-queues |
| Entry size | 14 bytes | 14 bytes | 14 bytes | N/A | 14 bytes | 14 bytes |
| Slot count | 18 | 54 | ~55 | N/A | 18 | 32 (8+12+12) |
| Encoding | movep pre-init | Raw VDP words | Raw VDP words | Inline construct | movep pre-init | movep pre-init |
| Enqueue cost | ~184 cycles | ~200 cycles (est.) | ~160 cycles (est.) | N/A | ~200 cycles | ~190 cycles |
| Drain method | Jump table | Sequential loop | Sequential loop | Direct writes | Loop + branch | Jump table (Critical) + budgeted loop (Important/Deferrable) |
| Drain per-entry | ~64 cycles | ~68 cycles (est.) | ~68 cycles (est.) | N/A | ~74 cycles | ~64 cycles (Critical), ~80 cycles (budgeted) |
| Priority support | None | None | Fixed slots + queue | Per-layer ordering | None | 3 tiers (Critical/Important/Deferrable) |
| 128KB safety | Yes (optional) | No | No | No | Yes | **No (deferred)** |
| Bandwidth budget | No | Yes (5760 bytes) | No (implicit via fixed ordering) | No | No | Yes (DMA_Budget_Remaining) |
| Static DMA | QueueStaticDMA macro | No | Hardcoded fixed slots | N/A | QueueStaticDMA macro | BuildStaticDMA + Enqueue_Dirty_Buffers |
| VInt safety | Optional | Implicit (SR mask) | Implicit (SR mask) | Implicit (SR mask) | Optional | Yes (sr save/restore in enqueue) |
| Overflow handling | Silent discard | Transactional rollback | Silent discard | N/A | Silent discard | Silent discard + debug counter |
| Rollback support | No | Yes | No | N/A | No | No |

---

## Assessment of Our Implementation

### What We Do Well

1. **3-priority sub-queues** — No reference uses explicit priority levels. Gunstar/AS approximate it with fixed slots + general queue, but our design is cleaner and more flexible. Critical palette/sprite DMAs will never be starved by bulk art loads.

2. **Jump-table drain for Critical** — Matches S.C.E.'s best-in-class approach. ~64 cycles per entry with zero branches.

3. **Budget-aware drain for Important/Deferrable** — No reference implements bandwidth budgeting inline during drain. Vectorman has a pre-enqueue budget check, but our per-drain-entry budget check is more precise and adaptive.

4. **Static DMA pre-registration** — BuildStaticDMA + Enqueue_Dirty_Buffers is cleaner than Gunstar's hardcoded fixed slots. Compile-time construction, runtime dirty-flag gating.

5. **VInt safety in enqueue** — We save/restore SR around queue writes, preventing race conditions. S.C.E. leaves this optional (and off by default).

6. **movep encoding** — Same as S.C.E., proven optimal for the 14-byte entry format.

### Issues Found

#### CRITICAL: 128KB Boundary Safety Not Implemented

Our enqueue has NO 128KB boundary protection. This is explicitly noted as deferred, but with S2 introducing larger art transfers from ROM, this becomes dangerous:

- **Risk:** Any ROM art data crossing a 128KB boundary ($20000, $40000, $60000, etc.) will wrap to the start of the 128KB block, producing garbage tiles on real hardware
- **When it will bite:** S4LZ-compressed art in ROM is NOT alignment-guaranteed. The decompressed data source will be RAM (safe), but raw art loads from ROM for uncompressed data or initial loads could cross boundaries
- **Cost of fix:** ~16 extra cycles per enqueue for non-crossing transfers, ~154 extra cycles for crossing transfers (auto-split into two entries). This is S.C.E.'s proven approach
- **Recommendation:** **Implement now.** The cost is negligible and the bug is silent (works in emulators, fails on some real hardware). Copy the proven sub+sub boundary detection from S.C.E./sonic_hack

#### MODERATE: Budget Drain Discards Unprocessed Entries

When `Drain_Budgeted_Queue` exits due to budget exhaustion, `Process_DMA_Important` and `Process_DMA_Deferrable` unconditionally reset their slot pointers (lines 143, 159). Any entries that were not drained because the budget ran out are silently discarded.

- **Current behavior:** Queue is fully cleared every frame regardless of whether entries were processed
- **Impact:** During heavy art-load frames, Important/Deferrable entries may be queued but never executed
- **Assessment:** This is actually correct for our design. Entries represent "this frame's work" — if the budget can't fit them, they need to be re-queued next frame by the caller (e.g., the art streaming system). The alternative (carrying entries across frames) would require a ring buffer or partial-drain tracking, adding complexity for minimal gain. The callers know what they need and will re-request.
- **No change needed** — but the art streaming system (S2) must be designed knowing this: it should track "pending art loads" independently and re-enqueue each frame until processed.

#### MINOR: Slot Count Assessment

32 total slots (8 Critical + 12 Important + 12 Deferrable) vs. S.C.E.'s 18 flat slots:

- **Critical (8):** 4 palette lines + 1 sprite table = 5 fixed per frame. Leaves 3 for character art DMA or emergency transfers. Adequate.
- **Important (12):** For character art streaming, animated tiles, DPLC art. 12 slots at 14 bytes = 168 bytes of RAM. Adequate for early engine; may need to grow when full gameplay exists.
- **Deferrable (12):** For section art preloading, background updates. 12 slots is generous for deferred work.
- **Total (32):** 448 bytes. Compared to S.C.E.'s 252 bytes (18 slots). The extra 196 bytes is justified by the priority system.
- **Recommendation:** Keep as-is. The 3-tier partition provides better worst-case guarantees than a single 32-slot flat queue.

#### MINOR: No Transactional Rollback

Vectorman's ability to speculatively enqueue a batch and rollback on overflow is clever but adds complexity. Our debug overflow counter serves the same diagnostic purpose, and our priority system makes overflow less likely for critical transfers.

- **No change needed.**

---

## 128KB Boundary Decision

**Decision: Implement 128KB boundary splitting in QueueDMATransfer now.**

Rationale:
1. S4LZ decompression will decompress to RAM (safe), but the engine also needs to support direct ROM-to-VRAM transfers for initial level loads, uncompressed fallback art, and potentially UFTC random-access tiles
2. The fix is proven (copied verbatim from S.C.E./Flamewing), costs ~16 cycles in the common case, and prevents a class of hardware-only bugs that are extremely difficult to diagnose
3. Every serious reference that has it (S.C.E., sonic_hack) enables it. The references that lack it (Vectorman, Gunstar, TF4) are commercial games that solved alignment at the asset pipeline level — we cannot guarantee that during development
4. The `QueueStaticDMA` macro in `buffers.asm` already uses compile-time boundary validation. The runtime queue needs the same safety for dynamic transfers

The implementation should use S.C.E.'s proven `sub.w d3,d0; sub.w d1,d0; blo.s .doubletransfer` approach. This handles all edge cases (zero-length, exact boundary, boundary+1) correctly.

---

## Specific Improvements Identified

### Must Implement (before S2 work begins)

1. **128KB boundary splitting in QueueDMATransfer** — Add the proven S.C.E. sub+sub detection and auto-split. ~30 lines of code.

### Consider for Later

2. **Compile-time boundary validation for QueueStaticDMA** — Our `BuildStaticDMA` in `buffers.asm` doesn't validate boundaries at assembly time. Add the `MOMPASS>1` checks from S.C.E.'s macro.

3. **Debug overflow logging** — Our `DMA_Overflow_Count` only counts. Consider adding Flamewing's `RaiseError` approach (from `DMA Queue(Debug).asm`) that reports which queue overflowed and the failed transfer parameters.

### Not Recommended

4. **Transactional rollback (Vectorman style)** — Not worth the complexity. Our priority system provides better guarantees.

5. **Reverse-fill (Treasure style)** — Requires different drain logic, incompatible with jump-table drain. No measurable benefit over forward-fill with movep.

6. **Single flat queue replacing 3-tier** — Would lose priority guarantees. Our design is superior to every reference for a Sonic engine's mixed-priority workload.

---

## DMA Bandwidth Reference Numbers

For DMA budget planning in the art streaming system:

| Configuration | VBlank Bandwidth | Per-Scanline (active) |
|---|---|---|
| NTSC 320x224 (H40) | ~7,524 bytes | ~18 bytes |
| NTSC 256x224 (H32) | ~6,118 bytes | ~14 bytes |
| PAL 320x224 (H40) | ~17,622 bytes | ~18 bytes |
| PAL 256x224 (H32) | ~14,329 bytes | ~14 bytes |

Our engine targets NTSC H40 (320x224). The ~7,524 byte VBlank budget must cover:
- Palette (4 lines x 32 bytes = 128 bytes) — Critical
- Sprite table (640 bytes) — Critical
- HScroll buffer (up to 448 bytes) — Critical
- Character art (variable, typically 512-2048 bytes) — Important
- Level art streaming (variable) — Important/Deferrable
- Animated tiles (variable) — Important

Total fixed: ~1,216 bytes. Leaves ~6,300 bytes for variable art, which is comfortable for section streaming.

Note: VRAM DMA in 64K mode (our configuration) runs at roughly half the speed of CRAM/VSRAM DMA. The numbers above are for VRAM. CRAM/VSRAM transfers are effectively free (128 bytes of palette = negligible time).

---

## Conclusion

Our DMA queue is **best-in-class** among the surveyed implementations. The 3-priority sub-queue design with jump-table critical drain and budgeted lower-priority drain is more sophisticated than any reference. The one critical gap is 128KB boundary protection, which must be added before S2 work begins. All other aspects (slot counts, encoding, static DMA, priority system) are sound.
