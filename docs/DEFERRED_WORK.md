# Deferred Work

Tracks work that was identified during design/implementation but deferred because dependencies don't exist yet. Check this document at the start of each new system's planning phase — items here may now be unblocked.

---

## From §1 — Core VDP Pipeline

These subsystems are fully designed in ENGINE_ARCHITECTURE.md §1 but require other systems to exist first.

### Sprite Rendering Pipeline (§1.2)
**Blocked by:** Object System (§3)
**What:** Two-phase render (Draw_Sprite during object loop → Render_Sprites converts to VDP format), priority-band sorting, overflow handling, multi-sprite batching, sprite count per object.
**When ready:** After §3 defines object RAM layout and the object loop exists.

### Scroll / Plane Drawing (§1.3)
**Blocked by:** Level / World System (§4)
**What:** Deferred plane buffer (768 words), Draw_TileColumn/Row, VInt_DrawLevel, overflow protection, dual plane support, double-update mechanism, pre-computed nametable strips.
**When ready:** After §4 defines section format and level layout RAM.

### DPLC Lookahead (§1.6)
**Blocked by:** Object System (§3) — specifically AnimateSprite and DPLC tables
**What:** Predictive art loading by peeking at next animation frame's DPLC requirements one frame early. Queue as Important-priority DMA.
**When ready:** After §3 defines animation system with frame scripts and DPLC mappings.

### Adaptive DMA Byte Budget (§1.1)
**Blocked by:** Real workloads from gameplay systems
**What:** Per-frame DMA byte tracking, lag-frame budget reduction, lag recovery 1.5x burst. Self-tuning throughput based on scene complexity.
**When ready:** After enough consumers exist to generate meaningful DMA load (character art streaming, level tile loading, animated tiles).

### Variable HScroll DMA (§1.1)
**Blocked by:** Scroll system (§4) — specifically camera and scroll routines
**What:** Dirty-range tracking (Hscroll_Dirty_Start/End), variable-length DMA for only changed hscroll entries instead of full 448-byte buffer.
**When ready:** After §4 implements camera movement and scroll update routines.

### Background Work / Cooperative Multitasking (§1.5 → §9.7)
**Blocked by:** Full design of §9.7
**What:** Supervisor/user mode context switching for background S4LZ decompression in leftover CPU time.
**When ready:** When §9.7 is designed and the S4LZ decompressor exists.

### HUD Dirty Flags (§1.4)
**Blocked by:** HUD system (part of §9.13 screen/menu system)
**What:** Per-element dirty flags (score, rings, timer, lives) to skip HUD VDP writes on frames where nothing changed.
**When ready:** After HUD rendering exists.

### 128KB DMA Boundary Splitting (§1.1 / §2.1)
**Blocked by:** Nothing — can be added any time before production
**What:** DMA transfers from ROM that cross a 128KB boundary ($20000, $40000, etc.) cause the VDP source address to wrap within the bank, loading garbage tiles. `QueueDMATransfer` must check if `source + length` crosses a boundary and split into two entries. S.C.E. has a proven implementation (~20 lines, ~16 cycles common case, ~154 for split transfers). See `docs/research/dplc-improvements.md` for details.
**When ready:** Should be added before any real sprite art or level art loads from ROM. Safe to add now.

---

## From §2 — Art & Compression Pipeline

### Generic Perform_DPLC Routine (§2.1 / §3.9)
**Blocked by:** Object System (§3) — specifically SST layout with `ros_prev_frame`, `art_source`, `dplc_script` fields
**What:** Single generic DPLC routine that works for all objects (S.C.E. approach). Per-object `ros_prev_frame` for frame change detection. Reads DPLC table, computes ROM source from `art_source` pointer, queues DMA to allocated VRAM address. Character DPLCs → Important priority, Object DPLCs → Deferrable priority.
**When ready:** After §3 defines SST layout and animation system.

### Build-Time DPLC Tools (§2.1 / §2.6)
**Blocked by:** Sprite art extraction from sonic_hack
**What:** Two build-time tools: (1) Contiguous art layout — rearrange tiles so each animation frame's tiles are contiguous in ROM, guaranteeing 1 DMA entry per frame change. (2) DPLC entry merging — merge adjacent entries in legacy DPLC tables (3.1 → 1.2 entries average). Both produce optimized DPLC tables and rearranged art.
**When ready:** After sprite art is extracted from sonic_hack to `art/uncompressed/`.

---

## How to Use This Document

When starting a new planning phase:
1. Read through deferred items
2. Check if any blockers are now resolved
3. If so, include the deferred work in the new plan
4. Move completed items to a "Done" section at the bottom (with the date and the system that unblocked them)
