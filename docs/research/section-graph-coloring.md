# Section Graph Coloring Research (§2 A.3)

**Date:** 2026-04-26
**Driver:** §2 Phase 2 Layer A.3 needs to assign per-section VRAM tile-slot ranges such that adjacent sections never share VRAM (so both can render simultaneously) but non-adjacent sections can share (cutting total working-set size).

## Sources reviewed

**Reference disassemblies (all 7 per CLAUDE.md):**
1. **S.C.E.** — `Engine/Core/Load Level.asm` (`LoadLevelLoadBlock`) loads "primary" + "secondary" level art at fixed VRAM destinations via Kosinski-Plus modules. No runtime VRAM aliasing; each art set goes to a hardcoded slot. Per-zone setup, hand-authored.
2. **sonic_hack** — uses Sonic 2/3K's **Pattern Load Cue (PLC)** system. `code/engines/dma_plc.asm` and per-character PLC tables (e.g. `plcs/KnuxPLC.asm`) — pre-defined lists of `(compressed_art_ptr, vram_dest)` tuples. Loaded at level-init or on-demand. **Hand-authored, fixed VRAM destinations.** Closest existing Genesis prior art for "load art at controlled VRAM offsets," but no graph-coloring or auto-derived offsets.
3. **Batman & Robin** (`disasm/code/engine/core.asm`) — uses raw nametable BINCLUDEs (per `ART_AND_COMPRESSION.md` from A.2 research). Art-loading code present but no symbols matching VRAM-aliasing or section-aware patterns.
4. **Vectorman** (`vectorman_disasm/code/disasm.asm`) — same as A.2 research showed: dynamic 64×32 / 64×64 plane size switching at runtime. Art DMA via standard VDP routines. No runtime VRAM aliasing or per-region coloring detected via symbol grep.
5. **Thunder Force IV** (`thunderforce4_disasm/code/disasm.asm`) — no symbol matches for VRAM aliasing/coloring.
6. **Gunstar Heroes** (`gunstar_disasm/code/disasm.asm`) — no symbol matches.
7. **Alien Soldier** (`aliensoldier_disasm/code/disasm.asm`) — no symbol matches.

The five sibling disasms (3-7) likely use simple "DMA from ROM to fixed VRAM" art loading without any aliasing strategy. Symbol-grep-based search is shallow (these disasms have few semantic symbol names; most are auto-generated `loc_XXXXXX` labels) so the absence of evidence here isn't conclusive — but combined with B&R's documented "uncompressed everywhere" approach and S.C.E./sonic_hack's hand-authored PLCs, the pattern is clear: **no commercial Genesis game appears to do automatic graph-coloring-based VRAM allocation across level sections.**

**Compiler register-allocation literature:**
8. **Chaitin (1981)** — original graph-coloring register allocation, the seminal paper.
9. **Briggs/Cooper/Torczon (1989)** — optimistic spilling improves Chaitin on hard cases.
10. **George/Appel (1996)** — iterated register coalescing handles move instructions.
11. **Poletto/Sarkar (1999)** — linear scan; faster, slightly worse quality, simpler.

For our problem (≤100 sections, small adjacency graphs), all of this is overkill. Even Chaitin's worst case (NP-hard for general graphs, exponential in worst case) is fine for our `N ≤ 16` OJZ case. **DSATUR greedy is sufficient and optimal for our graph classes** (see source 13).

**2D bin packing (within a color class):**
12. **Coffman, Garey, Johnson (1996)** — survey of bin-packing approximations. First-Fit-Decreasing (FFD) is within 22% of optimal; Best-Fit-Decreasing similar. **Our bin-packing is degenerate** — within a color class C, the VRAM range is `max(|S.tiles|)` for sections S in C; every section in C starts at C's base. No actual packing decisions to make. Documented to prevent a future maintainer adding unnecessary complexity.

**Online & community sources:**
13. **Wikipedia: DSatur** — Brélaz 1979. **Optimal on bipartite, cycle, and wheel graphs.** Path graphs are bipartite (every path is 2-colorable), so DSATUR optimally 2-colors any chain-style act layout. For more complex 2D grid acts, the graph might not be bipartite (depends on dimensions), but DSATUR still produces good results on small instances.
14. **plutiedev** — pages on plane configuration covered in A.2 research; nothing on runtime VRAM aliasing. The site doesn't address this topic.
15. **md.railgun.works** — searched for "Pattern Load Cue" page; doesn't exist (404).
16. **gendev.spritesmind.net forum** — browsed front page; no threads on runtime VRAM allocation strategies, art-region aliasing, or per-section tile loading. Closest topics are "Linear Frame Buffer", "Thousand tiles based maps", and "VDP FIFO and DMA questions" — none address our problem.
17. **GitHub homebrew** — Xeno Crisis, Tanglewood, Demons of Asteborg etc. all use SGDK as-is; SGDK's `MAP` system streams tiles based on visible window but doesn't graph-color. No homebrew project surveyed implements section-graph-coloring.

**Modern engine literature:**
18. **Texture atlasing in 3D engines** — pack many small textures into one large texture to minimize binding switches. Conceptually similar ("many tiles in one VRAM region"), but static and at build time, with no runtime aliasing. Doesn't generalize to our problem.
19. **NES CHR-RAM bank switching** — different cartridges and games swap CHR-RAM banks per scene. The mechanism is bank-switch register writes (no DMA), but the **logical concept** is closest to A.3: "swap which art is visible based on context." NES bank-switching is per-scene/per-screen; A.3 generalizes to per-section with adjacency-aware sharing.
20. **Unity/Unreal asset bundles** — runtime asset swapping driven by scene. Modern equivalent of PLC. Dynamic allocation; not directly comparable to our static graph-coloring.

**Conclusion from breadth:** Section-graph-coloring is genuinely novel for Genesis. The closest analogs are S2/S3K's hand-authored PLCs (no auto-coloring) and NES CHR-RAM bank switching (no adjacency awareness). DSATUR's optimality results on bipartite/cycle graphs cover all reasonable Sonic act layouts.

## Adjacency definition decision

**Chosen: 4-neighbor (N/S/E/W only) on the section grid.**

Sections are addressed as `(sec_x, sec_y)` in a `grid_w × grid_h` layout. Section A is adjacent to section B iff they differ by exactly 1 along exactly one axis: `|sec_x_A - sec_x_B| + |sec_y_A - sec_y_B| == 1`.

**Why not 8-neighbor (with diagonals):** The leapfrog slot system holds at most 2 sections simultaneously, and they are always horizontal/vertical neighbors (never diagonal). Two diagonally-adjacent sections never co-exist in the slots. Treating diagonals as adjacent would needlessly inflate the chromatic number for layouts with more than 1 row, wasting VRAM.

**Why not visibility-bbox-overlap:** More permissive (could find more sharing opportunities) but requires per-section bounding-box arithmetic and per-camera-position visibility checks. Vast complexity overhead for OJZ act 1 where adjacency is trivially the linear chain. If a future act uses asymmetric section sizes or weird layouts, revisit.

**Implementation:** `compute_adjacency(grid_w, grid_h)` returns `[(a, b), ...]` edges where each section ID is `sec_y * grid_w + sec_x`. For OJZ act 1 (16×1 grid): 15 edges (path graph 0-1, 1-2, …, 14-15). For a 4×4 grid: 24 edges.

## Coloring algorithm decision

**Chosen: DSATUR greedy (Brélaz 1979).**

Justification grounded in the research:
- **Optimal on bipartite graphs** — paths and trees are bipartite, so OJZ's path graph gets 2-coloring. Most Sonic acts are paths or near-paths.
- **Optimal on cycles** — handles wraparound layouts (e.g. arena-style levels) optimally.
- **Optimal on wheels** — handles hub-and-spoke layouts.
- **Optimal on graphs with ≤6 vertices** — covers any pathological tiny act.
- **Generally near-optimal on small graphs** — for the rare future act that's neither bipartite nor cyclic nor tiny, DSATUR's quality is near optimal in practice.

For `N ≤ 16` (OJZ scale), DSATUR runs in O(N²) = 256 operations at worst — trivial at build time. For larger zones, DSATUR scales to O(N²) which is fine up to ~10,000 sections (impractical for any reasonable Sonic level anyway).

**Why not brute-force optimal:** Exponential in worst case. For path graphs the optimum is trivially 2 colors; brute-force just confirms what DSATUR already gives. No quality gap to recover.

**Why not Chaitin/Briggs:** These algorithms are designed for register allocation where "spilling" (storing a variable to memory when register pressure is too high) is meaningful. In our problem there's no analog — if a coloring needs more colors, we just add a color (= more VRAM range) until the act fits. Our equivalent of "pressure" is total VRAM budget, which we track separately via A.2's region capacity constants.

## Per-color packing decision

**Chosen: Degenerate. Each section in color C starts at C's VRAM base.**

Within a color class C, all sections share the same VRAM range. Section S's tiles occupy slots `[C_base, C_base + |S.tiles|)`. Different sections in C have different `|S.tiles|` but they all start at `C_base`. Their tiles overwrite each other in VRAM as the camera traverses across same-color sections.

The leapfrog adjacency invariant guarantees no overlap problem: at any time, the two visible slots hold *adjacent* sections, which by graph-coloring construction are in *different* colors → *different* VRAM ranges → both render correctly simultaneously.

**Why no real bin-packing:** Within a color, there's no "fitting" decision — every section starts at the same base. The size of color C's VRAM range is determined by `max(|S.tiles|)` over sections in C; smaller sections leave unused slots within the range, which is fine.

**Implementation:** `assign_section_slots(per_section_tiles, colors, region_start=0)` returns:
- `color_bases[c]`: VRAM tile-slot start for color c (computed cumulatively from `region_start`)
- `section_slots[s]`: dict mapping each canonical_tile_id used by section s to its VRAM tile slot (within s's color's range)

Total VRAM used = `sum over colors c of max(|S.tiles| for S in c)`, achieved by per-color stacking starting from `region_start`.

## Genesis prior art (PLC system)

Sonic 2/3K's PLC (Pattern Load Cue) system is the closest existing platform analog. A PLC is a hand-authored list of `(compressed_art_ptr, vram_dest_byte)` tuples loaded at level-init or boss-fight-init. Each level/scene has its own PLC; the PLC's VRAM destinations are picked manually by the level designer to avoid clobbering character art or HUD tiles.

**Differences from A.3:**
1. **Manual vs auto:** PLCs require a human to think about VRAM layout. A.3 auto-derives layouts from a section adjacency graph.
2. **Per-level vs per-section:** PLCs operate at level granularity (load all of level X's art at start). A.3 operates at section granularity within a level (load each section's art on transition).
3. **Static vs aliasing:** PLCs use disjoint VRAM regions per art set. A.3 explicitly aliases non-adjacent sections to the same VRAM range.

A.3 is essentially "PLC, but with adjacency-aware automatic VRAM offset assignment, fine-grained per-section." None of the surveyed platforms documents this approach; A.3 is novel.

## Anything that changes ENGINE_ARCHITECTURE.md

**None.** §2.3 already describes "Build-time tile graph coloring (NOVEL): The build tool analyzes all sections in the zone and constructs an adjacency graph (which sections can be simultaneously visible — up to 4 at any corner of the 2D grid). Non-adjacent sections can reuse the same VRAM tile indices, like register allocation in a compiler." This research confirms the design choice and adds implementation specifics (DSATUR, 4-neighbor adjacency, degenerate packing). The arch doc is forward-looking enough to cover what we built; no update needed.

The "up to 4 at any corner of the 2D grid" phrase in the arch doc anticipates the future 2D-grid case where 4 sections can co-exist if the camera straddles a 2×2 corner. A.3 implements 4-neighbor adjacency, which handles up to 2 simultaneously-visible sections (only horizontal or vertical pairs). When a future act uses a 2D grid AND camera positioning ever exposes a 2×2 corner, expand adjacency to 8-neighbor at that time. The current implementation is correct for the slot-2 leapfrog system in use today.
