# Per-Section Streaming Research (§2 A.4)

**Date:** 2026-04-26
**Driver:** §2 Phase 2 Layer A.4 needs to replace A.3's blocking `Section_LoadArt` calls in `Section_TeleportFwd`/`Bwd` with budget-gated Deferrable DMA streaming triggered ahead of the section transition. The player should never see a stutter when crossing section boundaries.

## Sources reviewed

**Reference disassemblies (all 7 per CLAUDE.md):**

1. **S.C.E.** — `Engine/Core/Load Level.asm` and `Engine/Variables.asm`. Has the **closest existing pattern**: a per-module decompression queue.
   - `Queue_KosPlus_Module` enqueues a (source_ptr, vram_dest) tuple.
   - `Process_KosPlus_Queue` advances the in-flight decompress (called every frame).
   - `Process_KosPlus_Module_Queue` processes the entire queue.
   - `KosPlus_modules_left` (RAM word) tracks pending modules; sign bit = "currently decompressing."
   - **Used at level init** for loading screens (Load Level.asm) and **palette fade** (Fading Palette.asm — `bsr.w Process_KosPlus_Module_Queue` runs during fade frames). Not used for in-gameplay section transitions.
   - Mechanism similar to A.4 (queue-based deferred decompress). Use case different (one-shot init, not continuous gameplay).

2. **sonic_hack** — `code/engines/dma_plc.asm` has **Sonic 2/3K's PLC system** (Pattern Load Cue). `ProcessDPLC` and `ProcessDPLC2` are the queue processors, called from `VInt_Load` (the loading-screen VBlank handler) and `Vint_TransferBuffers` (per-frame).
   - PLCs are pre-defined tables of `(art_ptr, vram_dest)` tuples per zone/level.
   - At level init, all PLCs queue; `ProcessDPLC` advances them across loading-screen VBlanks.
   - `ProcessDPLC2` runs in the active game frame too (limited budget).
   - Queue is per-zone, not per-section. A.4's per-section granularity is finer.

3. **Batman & Robin** (`disasm/code/engine/core.asm`) — no streaming-related symbols. Per ART_AND_COMPRESSION.md from earlier research, B&R uses raw uncompressed art with bulk DMA at scene load. No in-gameplay art streaming.

4. **Vectorman** (`vectorman_disasm/code/disasm.asm`) — no `stream`/`preload`/`deferred` symbol matches. Static art loading per scene.

5. **Thunder Force IV** (`thunderforce4_disasm/code/disasm.asm`) — no streaming symbols.

6. **Gunstar Heroes** (`gunstar_disasm/code/disasm.asm`) — no streaming symbols.

7. **Alien Soldier** (`aliensoldier_disasm/code/disasm.asm`) — no streaming symbols.

The five sibling disasms all appear to use static "load all art at scene init" patterns. No commercial Genesis game surveyed implements per-section in-gameplay art streaming (with the partial exception of S2/S3K's PLC system, which is per-zone not per-section).

**Online & community sources:**

8. **SGDK `MAP` system** — `inc/map.h`. Provides `MAP_scrollTo(map, x, y)` and `MAP_scrollToEx(map, x, y, forceRedraw)`. The first call does a full plane update; subsequent calls do incremental row/column updates via `prepareMapDataRowCB` / `prepareMapDataColumnCB` callbacks queued through SGDK's DMA queue. **Critically: this is nametable streaming, NOT art streaming.** SGDK assumes all tile art is already in VRAM; MAP only moves nametable cells around as the camera scrolls. Their docs explicitly say the system "avoids double-buffering overhead by leveraging DMA queue sequencing." Different mechanism from A.4 (we do art streaming, they do nametable streaming — both can coexist in our engine).

9. **plutiedev.com** — `dma-transfer` page covers basic DMA queue batching ("keep all your transfers there if possible") but **does not address deferred scheduling across multiple VBlanks, priority lanes, or preloading during scrolling**.

10. **md.railgun.works** — searched for `Pattern_Load_Cue`; page doesn't exist. General DMA pages cover hardware mechanics but not scheduling strategies.

11. **gendev.spritesmind.net** forum — front-page browse found no threads on deferred DMA scheduling, art streaming, or preloading. Closest topics: "VDP FIFO and DMA questions" (general DMA behavior), "Linear Frame Buffer" (memory management), "Script to convert RGB Images to Mega Drive format" (asset conversion). None directly relevant to per-section art streaming.

12. **GitHub homebrew** — Xeno Crisis, Tanglewood, Demons of Asteborg are SGDK-based and inherit MAP's nametable streaming. None implement custom per-section art streaming on top.

**Modern engine streaming literature:**

13. **Texture streaming in 3D engines** — async asset bundles, async texture loads, prefetch-by-camera-direction. Modern engines maintain a per-asset state machine (typically `LOADED` / `LOADING` / `LOAD_REQUESTED` / `UNLOADED`). Maps directly to A.4's `SS_RESIDENT` / `SS_STREAMING` / `SS_IDLE`.

14. **Open-world streaming heuristics** — preload distance based on travel speed (we have a fixed FWD/BWD threshold; velocity-adaptive is §3-deferred). Round-robin or pool-based buffer allocation (we use a 2-buffer round-robin).

## Genesis prior art

Sonic 2/3K's PLC system and S.C.E.'s KosPlus module queue are the closest analogs. Both use a **queue-based deferred decompression** pattern:
1. Caller pushes a (compressed_source, vram_dest) tuple onto a per-game-state queue.
2. A processing routine called every frame (or every few frames) advances in-flight decompresses.
3. Eventually the queue drains; tiles are in VRAM.

A.4 uses the same conceptual mechanism but with two key differences:
- **Per-section granularity** (PLCs/KosPlus are per-zone or per-loading-screen).
- **Adjacency-aware preload trigger** (PLCs/KosPlus fire at level init or fade events; A.4 fires when the camera crosses a per-frame threshold during normal gameplay).

The state-machine wrapper (`SS_IDLE` → `SS_STREAMING` → `SS_RESIDENT`) is novel for the platform — none of the surveyed Genesis games maintain a per-region "is this art currently being loaded" tracker, because none of them stream per-region during gameplay.

## SGDK MAP reference

SGDK's `MAP_scrollTo` is a useful reference for "stream incremental updates as the camera moves" but operates on the **nametable**, not the **tile art**. Its design assumptions:
- All tile art for the level is already in VRAM (loaded at scene init).
- As the camera moves, only nametable cells need updating (which references shift onto/off of the visible window).

A.4 plus our existing Section_UpdateColumns gives us *both* halves: nametable streaming (already done in §4 Phase 1) AND tile-art streaming (A.4 adds this). SGDK doesn't have the latter; we now do.

## Preload threshold decision

**Chosen: keep the existing constants — `SECTION_FWD_PRELOAD = $0E00`, `SECTION_BWD_PRELOAD = $0400`.**

Math:
- Forward: teleport at $1200, preload at $0E00 → 1024 px earlier. At normal Sonic camera speed (~6 px/frame), that's ~170 frames of streaming time before the teleport runs.
- Backward: teleport at $0200, preload at $0400 → 512 px earlier. ~85 frames of streaming time.

For OJZ-scale per-section blobs (~270 bytes compressed, ~320 bytes uncompressed), `S4LZ_Decompress` runs in well under one frame and the Deferrable DMA drains within 1-3 VBlanks. **Both thresholds give massive headroom.** No tuning needed for current data; if future bigger sections demand more lookahead, bump the constants.

The asymmetry (BWD has half the lookahead of FWD) is acceptable because backward camera motion is rarer in gameplay than forward, and `Section_BWD_PRELOAD` is constrained by `SECTION_BWD_THRESHOLD` being closer to the section origin. If profiling later shows backward transitions stuttering, increase `SECTION_BWD_PRELOAD` (e.g., to `$0600`) — but for OJZ, $0400 has plenty of margin.

## Decompressor invocation pattern decision

**Chosen: run-to-completion S4LZ decompress + queued Deferrable DMA.**

When the preload trigger fires:
1. `S4LZ_Decompress` runs end-to-end in one frame.
2. The decompressed bytes sit in a streaming buffer.
3. A single `QueueDMA_Deferrable` enqueues the buffer → VRAM transfer.
4. Deferrable DMA drains across upcoming VBlanks within the per-frame DMA budget.

For OJZ-scale sections (~270 bytes compressed), decompress takes well under 1 ms (~700-1100 KB/s S4LZ throughput, so 270 bytes = ~0.25 ms). Single-frame is trivially fine.

**Why not per-frame budgeted decompress** (S.C.E.-style, where decompression is paused/resumed across frames):
- Adds state-machine complexity inside `S4LZ_Decompress` (save/restore decompressor state).
- Unnecessary for current data scale.
- Future need (sections with multi-KB compressed blobs) is speculative; build it when those sections exist.

This decision should be revisited when:
- A real section blob exceeds ~1 KB compressed (decompress > 1 ms approaches frame budget pressure).
- A real level has section transitions where the preload-to-teleport window shrinks below ~30 frames.

For now, run-to-completion is correct and simpler. Documented to prevent a future maintainer from adding budgeted decompression speculatively.

## Anything that changes ENGINE_ARCHITECTURE.md

**None.** The architecture doc already describes A.4's design in §1.1 (DMA Queue priority lanes — "Section preload" listed under Deferrable) and §2.5 (Art Loading Flow — section preload via S4LZ stream + Deferrable DMA). §9.7 (Cooperative Multitasking) covers the future enhancement where the decompressor itself becomes preemptable; A.4 explicitly defers that. The arch doc is forward-looking enough to cover what we built; no update needed.
