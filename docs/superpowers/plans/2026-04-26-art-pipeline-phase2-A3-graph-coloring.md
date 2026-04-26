# §2 Phase 2 — Layer A.3: Build-time Graph Coloring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the deduped tile pool around *sections* rather than the global pool. Build tool computes the section adjacency graph from the act descriptor, graph-colors sections so adjacent sections never share VRAM tile slots, and emits per-section S4LZ blobs. Engine adds a `Section_LoadArt` routine that decompresses + DMAs a section's blob to its assigned VRAM range; `Section_Init` loads both initial slots, and `Section_TeleportFwd`/`Bwd` load the incoming section after each transition.

**Architecture:** Each section gets two new fields in its `Sec` struct (`tile_art_s4lz` longword + `tile_art_vram` word). `tile_dedupe.py` gains a coloring pipeline (`compute_adjacency` → `color_sections` → `assign_section_slots`). For each color class C, the VRAM range is sized to `max(|S.tiles|)` over sections S in C; sections in C share that range (their tiles overwrite each other in VRAM as the camera traverses). The leapfrog system already maintains the invariant that the two visible slots hold *adjacent* sections, which by graph-coloring construction live in *different* color classes (so their VRAM ranges don't conflict). Per-section blobs are compressed to S4LZ at build time. Section transitions trigger a blocking `Section_LoadArt` (A.4 will replace blocking with Deferrable streaming).

**Tech Stack:** Python 3 + `unittest` (build tool), 68000 assembly with the AS Macro Assembler (engine), existing S4LZ + DMA infrastructure.

**Spec:** `docs/superpowers/specs/2026-04-26-art-pipeline-phase2-design.md` (Phase A.3 section)

**Out of scope:** Deferrable streaming on transition (A.4), per-section background art (A.5).

**Why default OJZ exercises A.3 naturally:** With 16 sections in a horizontal chain, the graph is a path. Chromatic number = 2 (path graphs are bipartite). 2-coloring assigns even-indexed sections to color 0 and odd-indexed to color 1. Crossing from section N to section N+2 requires section N+2's tiles to overwrite section N's tiles in VRAM (both in color N%2). That overwriting *is* the test — if the build's coloring is wrong or the engine doesn't reload tiles on transition, the rendering breaks visibly. **No stress flag needed for initial verification.**

---

## File map

**New files:**
- `docs/research/section-graph-coloring.md` — Task 1 research output

**Modified files:**
- `tools/tile_dedupe.py` — add `compute_adjacency`, `color_sections`, `assign_section_slots`
- `tools/test_tile_dedupe.py` — tests for the three new functions
- `tools/ojz_strip_gen.py` — replaces global pack_regions flow with per-section coloring + per-section blob emission. Per-section strip remap uses each section's slot assignment.
- `build.sh` — compress one S4LZ per section
- `structs.asm` — `Sec` struct gains `tile_art_s4lz` longword + `tile_art_vram` word (size $40 → $48)
- `data/levels/ojz/act1/act_descriptor.asm` — populate per-section `tile_art_s4lz`/`tile_art_vram` for all 16 sections; remove obsolete act-wide `tile_art_s4lz`/`tile_art_vram` from `Act_Desc`
- `engine/level/load_art.asm` — add `Section_LoadArt` routine; rewrite `Level_LoadArt` to call `Section_LoadArt` for both initial slots
- `engine/level/section.asm` — `Section_Init` calls `Level_LoadArt` (already done), `Section_TeleportFwd`/`Bwd` call `Section_LoadArt` after slot-map update
- `docs/research/tile-pipeline-measurements.md` — append A.3 row
- `docs/DEFERRED_WORK.md` — A.3 done entry
- `docs/ENGINE_ARCHITECTURE.md` — only if research surfaces something

---

## Task 0: Create feature branch

**Files:** none (git only)

- [ ] **Step 1: Create and check out the A.3 feature branch from master**

```bash
git checkout master
git status
git checkout -b feat/s2-a3-graph-coloring
git status
```

Expected: clean working tree, branch `feat/s2-a3-graph-coloring` checked out.

---

## Task 1: Research — graph coloring + bin packing + Genesis prior art (full CLAUDE.md sweep)

**Files:**
- Create: `docs/research/section-graph-coloring.md`

Per `CLAUDE.md`'s research checklist and the user's stored "research breadth" feedback, this task does the **full** sweep. Don't shortcut.

- [ ] **Step 1: All 7 reference disassemblies — runtime VRAM management strategies**

For each, look at how it manages VRAM as the camera moves between regions. None are expected to do graph coloring (it's novel for Genesis), but check whether any uses *runtime VRAM aliasing* (different objects/levels sharing VRAM regions at different times):

```bash
ls "/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/"
grep -rln 'VRAM\|art.*load\|tile.*load' /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/ 2>/dev/null | head -10
ls /home/volence/sonic_hacks/sonic_hack/code/engines/
ls /home/volence/sonic_hacks/sonic_hack/plcs/
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/code/"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/code/"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/code/"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/code/"
```

For sonic_hack specifically: read `/home/volence/sonic_hacks/sonic_hack/plcs/` to understand the **PLC (Pattern Load Cue) system** — that's S2/S3K's mechanism for runtime art swapping per zone/act. Document how it picks VRAM destinations. PLCs are *closest existing analog* to A.3 (per-zone art with VRAM addresses, except hand-authored not auto-colored).

- [ ] **Step 2: Compiler register allocation literature (graph coloring foundations)**

The classic algorithms:
- **Chaitin (1981)** — original graph-coloring register allocation
- **Briggs et al. (1989)** — improved spilling via optimistic coloring
- **George/Appel (1996)** — iterated register coalescing
- **Linear scan** (Poletto & Sarkar, 1999) — simpler, faster, slightly worse quality

For our problem (≤100 sections, small adjacency graphs, optimal coloring trivial via brute force), most of this is overkill. But document why — explicitly note that we can use brute force for `N ≤ 16`, greedy for larger graphs, with a fallback to Chaitin-style spilling never needed.

- [ ] **Step 3: 2D bin packing (within a color class)**

Classic algorithms for the bin-packing sub-problem:
- **First-Fit-Decreasing (FFD)** — simple, within 22% of optimal
- **Best-Fit-Decreasing (BFD)** — sometimes better, similar complexity
- **Optimal (ILP-based)** — feasible for tiny instances (≤20 items), exponential for big ones

Our bin packing is degenerate: within a color class C, the VRAM range for C is `max(|S.tiles|)` for sections S in C. There's no real packing — every section in C just starts at C's base. So we don't actually need a bin packer. **Document this explicitly** in the research notes so a future maintainer doesn't add unnecessary complexity.

- [ ] **Step 4: Online sources — full sweep**

Use WebFetch on each (catch failures and continue, summarize results):
- `https://plutiedev.com/` and any "scrolling" or "vdp" tutorial pages — same as A.2 research; no new ground expected but try anyway
- `https://md.railgun.works/index.php?title=PLC` (Pattern Load Cue topic, if exists) — sonic-specific runtime art loading
- `https://gendev.spritesmind.net/forum/` — search "tile sharing" or "VRAM allocation" or "section art"
- GitHub: search for any homebrew project that does runtime VRAM region aliasing or per-section art swapping (not just zone-wide)

- [ ] **Step 5: Modern engine literature**

Brief look at how modern engines handle "asset streaming with locality":
- **Texture atlasing in 3D engines** — packs many textures into one large texture, similar conceptually to "many sections share one VRAM region"
- **Asset bundles in Unity/Unreal** — runtime swap based on scene
- **NES CHR-RAM swapping** — bank switching for tile art per scene; closest 8-bit analog

Document what (if anything) maps to our problem. Most modern asset-streaming is dynamic-allocation-driven; our coloring is static.

- [ ] **Step 6: Resolve A.3 open questions**

Based on the research, settle the three open questions:

**a. Adjacency definition.** For OJZ act 1 (1-row × 16-col grid), choose:
- **Strict 4-neighbor** (N/S/E/W only): adjacency edge between section X and Y if `|sec_x_X - sec_x_Y| + |sec_y_X - sec_y_Y| == 1`. Simple, sound for grid layouts. Ignores diagonals (which can't be simultaneously visible if camera shows one section at a time).
- **8-neighbor** (with diagonals): adds diagonals; needed only if the camera viewport can ever straddle a 2×2 corner. For our slot system (2 slots, leapfrog), only horizontal/vertical adjacency matters. Diagonals never co-exist in the slots.

Recommendation: **4-neighbor**. Simple, exact for the slot-based system. If future visibility logic ever exposes 2×2 corners, expand.

**b. Per-color packing strategy.** Earlier paragraph already concluded: degenerate. Each section in color C starts at C's base; their tiles overwrite each other on transition. Document.

**c. Brute-force optimal vs heuristic.** For ≤16 sections (OJZ), brute force is `O(N^N)` worst case but practical for tiny graphs. Greedy DSATUR coloring works for any size and produces optimal results on bipartite graphs (which paths are). Use **DSATUR greedy** — handles any size, optimal on path/cycle/bipartite graphs, no heuristic-vs-optimal gap to worry about for our graph shapes.

- [ ] **Step 7: Write the research notes**

Write `docs/research/section-graph-coloring.md` with these exact sections:

1. **Sources reviewed** — every source actually opened, including unlisted material from broader search
2. **Adjacency definition decision** — 4-neighbor with one paragraph of justification
3. **Coloring algorithm decision** — DSATUR greedy with one paragraph of justification (cite results on bipartite/path graphs being optimal)
4. **Per-color packing decision** — degenerate (each section in color starts at color's base) with one-paragraph explanation of why no real packing is needed
5. **Genesis prior art** — what S2/S3K's PLC system does and why coloring is novel
6. **Anything that changes ENGINE_ARCHITECTURE.md** — explicit list (state "none" if so)

- [ ] **Step 8: Commit research notes**

```bash
git add docs/research/section-graph-coloring.md
git commit -m "$(cat <<'EOF'
docs(research): section graph coloring for §2 A.3

Full CLAUDE.md sweep. Settles three open questions:
- 4-neighbor adjacency (N/S/E/W); diagonals never co-exist in
  the leapfrog slot system
- DSATUR greedy coloring (optimal on path/cycle/bipartite graphs;
  scales to any future grid size without heuristic gaps)
- Degenerate per-color packing — each section in color C starts at
  C's base, no bin-packer needed

PLC (Pattern Load Cue) in S2/S3K is the closest Genesis prior art —
but PLCs are hand-authored per-zone, not auto-colored across sections.
A.3 is novel for the platform.
EOF
)"
```

---

## Task 2: Apply research findings to ENGINE_ARCHITECTURE.md (conditional)

**Files:**
- Modify (conditional): `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: Check the research notes**

Open `docs/research/section-graph-coloring.md` section 6 ("Anything that changes ENGINE_ARCHITECTURE.md").

- [ ] **Step 2a: If list is empty, skip Task 2**

- [ ] **Step 2b: If list is non-empty**

Apply the listed changes surgically to `docs/ENGINE_ARCHITECTURE.md` §2.3 or §4.x. Commit:
```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(arch): apply A.3 research findings"
```

---

## Task 3: Add `compute_adjacency` to `tile_dedupe.py` (TDD)

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py`

`compute_adjacency` takes a 2D grid (width × height in sections) and returns a list of (section_a, section_b) edges using 4-neighbor adjacency. Section IDs are flat indices: `id = sec_y * grid_w + sec_x`.

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_tile_dedupe.py` (after `TestPackRegions`, before `if __name__`):

```python
class TestComputeAdjacency(unittest.TestCase):
    def test_linear_chain(self):
        from tile_dedupe import compute_adjacency
        # 4 sections in 1 row → edges (0,1), (1,2), (2,3)
        edges = compute_adjacency(4, 1)
        self.assertEqual(set(edges), {(0, 1), (1, 2), (2, 3)})

    def test_2x2_grid(self):
        from tile_dedupe import compute_adjacency
        # 2x2 grid:
        #   id 0 (0,0)  id 1 (1,0)
        #   id 2 (0,1)  id 3 (1,1)
        # 4-neighbor edges: (0,1), (0,2), (1,3), (2,3)
        edges = compute_adjacency(2, 2)
        self.assertEqual(set(edges), {(0, 1), (0, 2), (1, 3), (2, 3)})

    def test_single_section(self):
        from tile_dedupe import compute_adjacency
        edges = compute_adjacency(1, 1)
        self.assertEqual(edges, [])

    def test_3x1_grid(self):
        from tile_dedupe import compute_adjacency
        edges = compute_adjacency(3, 1)
        self.assertEqual(set(edges), {(0, 1), (1, 2)})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: 4 errors (`ImportError: cannot import name 'compute_adjacency'`).

- [ ] **Step 3: Implement `compute_adjacency`**

Append to `tools/tile_dedupe.py`:

```python
# ---------------------------------------------------------------------------
# Section adjacency graph (§2 A.3)
# ---------------------------------------------------------------------------

def compute_adjacency(grid_w: int, grid_h: int) -> list[tuple[int, int]]:
    """4-neighbor adjacency on a grid_w × grid_h section grid.

    Section IDs are flat row-major: id = sec_y * grid_w + sec_x.
    Returns sorted list of (a, b) tuples with a < b.

    Diagonals are excluded — the leapfrog slot system never holds two
    diagonally-adjacent sections simultaneously.
    """
    edges: list[tuple[int, int]] = []
    for y in range(grid_h):
        for x in range(grid_w):
            sid = y * grid_w + x
            # East neighbor
            if x + 1 < grid_w:
                edges.append((sid, sid + 1))
            # South neighbor
            if y + 1 < grid_h:
                edges.append((sid, sid + grid_w))
    return sorted(edges)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: 20 tests pass (16 from A.1+A.2 plus 4 new).

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — compute_adjacency (4-neighbor section grid)"
```

---

## Task 4: Add `color_sections` (DSATUR greedy)

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py`

DSATUR (Saturation Degree) greedy coloring is provably optimal on bipartite, cycle, and path graphs (which covers all reasonable Sonic act layouts). It picks the next vertex by maximum saturation (number of distinct colors among neighbors), tie-breaking by raw degree.

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_tile_dedupe.py`:

```python
class TestColorSections(unittest.TestCase):
    def test_path_graph_two_colors(self):
        from tile_dedupe import color_sections
        # 4 sections in a chain → 2 colors alternating
        edges = [(0, 1), (1, 2), (2, 3)]
        colors = color_sections(4, edges)
        # Color 0 and color 1 alternate; verify adjacent sections differ
        for a, b in edges:
            self.assertNotEqual(colors[a], colors[b])
        # Should use only 2 colors (chromatic number of P4 is 2)
        self.assertEqual(set(colors), {0, 1})

    def test_single_section_color_zero(self):
        from tile_dedupe import color_sections
        colors = color_sections(1, [])
        self.assertEqual(colors, [0])

    def test_triangle_three_colors(self):
        from tile_dedupe import color_sections
        # K_3 (complete graph on 3 nodes) — chromatic number 3
        edges = [(0, 1), (1, 2), (0, 2)]
        colors = color_sections(3, edges)
        for a, b in edges:
            self.assertNotEqual(colors[a], colors[b])
        self.assertEqual(set(colors), {0, 1, 2})

    def test_disconnected_graph_minimal_colors(self):
        from tile_dedupe import color_sections
        # Two isolated nodes → both color 0
        colors = color_sections(2, [])
        self.assertEqual(colors, [0, 0])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: 4 errors (`ImportError: cannot import name 'color_sections'`).

- [ ] **Step 3: Implement DSATUR greedy**

Append to `tools/tile_dedupe.py`:

```python
def color_sections(num_sections: int, edges: list[tuple[int, int]]) -> list[int]:
    """DSATUR greedy graph coloring.

    Returns a list of length num_sections where colors[s] is the color
    (0-indexed) assigned to section s. Adjacent sections are guaranteed
    to have different colors. The chromatic number is len(set(colors)).

    DSATUR is provably optimal on bipartite, cycle, and path graphs,
    which covers all reasonable Sonic act adjacency shapes.
    """
    # Build adjacency dict
    neighbors: dict[int, set[int]] = {i: set() for i in range(num_sections)}
    for a, b in edges:
        neighbors[a].add(b)
        neighbors[b].add(a)

    colors: list[int] = [-1] * num_sections
    while True:
        # Pick vertex with max saturation (distinct colors in neighbors);
        # tie-break by max degree, then by lowest index.
        uncolored = [s for s in range(num_sections) if colors[s] == -1]
        if not uncolored:
            break

        def sat(s: int) -> int:
            return len({colors[n] for n in neighbors[s] if colors[n] != -1})

        chosen = max(
            uncolored,
            key=lambda s: (sat(s), len(neighbors[s]), -s),
        )

        # Assign smallest available color
        forbidden = {colors[n] for n in neighbors[chosen] if colors[n] != -1}
        c = 0
        while c in forbidden:
            c += 1
        colors[chosen] = c

    return colors
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: 24 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — color_sections via DSATUR greedy"
```

---

## Task 5: Add `assign_section_slots` (per-section VRAM-slot computation)

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py`

`assign_section_slots` takes per-section unique-tile lists and a coloring, returns:
- `color_bases`: list of length max_color+1, where `color_bases[c]` is the VRAM tile-slot start for color c
- `section_slots`: list of length num_sections, where `section_slots[s]` is a dict mapping `canonical_tile_id` → `vram_tile_slot` for section s

The total VRAM range used = sum over colors of (max |S.tiles| for S in color C). Sections within a color class share the same C_start.

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_tile_dedupe.py`:

```python
class TestAssignSectionSlots(unittest.TestCase):
    def test_two_color_chain(self):
        from tile_dedupe import assign_section_slots
        # 4 sections in a chain.
        # Section 0: uses canonical tiles [0, 1, 2]      (color 0)
        # Section 1: uses canonical tiles [3]            (color 1)
        # Section 2: uses canonical tiles [4]            (color 0)
        # Section 3: uses canonical tiles [5, 6]         (color 1)
        # Colors:    [0, 1, 0, 1]
        # Color 0: max sections-tiles = max(3, 1) = 3 → slots 0, 1, 2
        # Color 1: max sections-tiles = max(1, 2) = 2 → slots 3, 4 (start at 3)
        per_section_tiles = [[0, 1, 2], [3], [4], [5, 6]]
        colors = [0, 1, 0, 1]
        color_bases, section_slots = assign_section_slots(
            per_section_tiles, colors, region_start=0
        )
        # Color 0 starts at 0, color 1 starts at 3
        self.assertEqual(color_bases, [0, 3])
        # Section 0 (color 0): tile 0→slot 0, tile 1→slot 1, tile 2→slot 2
        self.assertEqual(section_slots[0], {0: 0, 1: 1, 2: 2})
        # Section 2 (color 0): tile 4→slot 0 (overlaps section 0 in VRAM, OK by adjacency)
        self.assertEqual(section_slots[2], {4: 0})
        # Section 1 (color 1): tile 3→slot 3
        self.assertEqual(section_slots[1], {3: 3})
        # Section 3 (color 1): tile 5→slot 3, tile 6→slot 4
        self.assertEqual(section_slots[3], {5: 3, 6: 4})

    def test_single_color_no_aliasing(self):
        from tile_dedupe import assign_section_slots
        # Two isolated sections, both color 0
        per_section_tiles = [[0, 1], [2]]
        colors = [0, 0]
        color_bases, section_slots = assign_section_slots(
            per_section_tiles, colors, region_start=0
        )
        # Only color 0; max tiles = 2; section 0 gets [0, 1], section 1 reuses [0]
        self.assertEqual(color_bases, [0])
        self.assertEqual(section_slots[0], {0: 0, 1: 1})
        self.assertEqual(section_slots[1], {2: 0})

    def test_region_start_offset(self):
        from tile_dedupe import assign_section_slots
        # If region_start = 100, all slots shift by 100
        per_section_tiles = [[0]]
        colors = [0]
        color_bases, section_slots = assign_section_slots(
            per_section_tiles, colors, region_start=100
        )
        self.assertEqual(color_bases, [100])
        self.assertEqual(section_slots[0], {0: 100})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: 3 errors (`ImportError`).

- [ ] **Step 3: Implement `assign_section_slots`**

Append to `tools/tile_dedupe.py`:

```python
def assign_section_slots(
    per_section_tiles: list[list[int]],
    colors: list[int],
    region_start: int = 0,
) -> tuple[list[int], list[dict[int, int]]]:
    """Compute per-section VRAM tile-slot assignment given a coloring.

    Each section's tiles get slots within its color's VRAM range.
    Sections in the same color share the range — their tiles overwrite
    each other in VRAM as the camera traverses (safe because adjacent
    sections are guaranteed different colors by `color_sections`).

    Args:
      per_section_tiles[s] = list of canonical tile IDs section s references
      colors[s]            = color index assigned to section s
      region_start         = base VRAM tile slot (default 0; A.2's region 1)

    Returns:
      color_bases[c]      = VRAM tile-slot start for color c
      section_slots[s]    = dict mapping canonical_tile_id → VRAM tile slot
                            (within section s's color's range)
    """
    if not per_section_tiles:
        return [], []

    num_colors = max(colors) + 1
    # Per-color: max number of distinct tiles any section in that color uses.
    per_color_max = [0] * num_colors
    for s, tiles in enumerate(per_section_tiles):
        c = colors[s]
        if len(tiles) > per_color_max[c]:
            per_color_max[c] = len(tiles)

    # Compute color bases: color 0 starts at region_start; color C starts at
    # color C-1's base + color C-1's max tile count.
    color_bases: list[int] = []
    cursor = region_start
    for c in range(num_colors):
        color_bases.append(cursor)
        cursor += per_color_max[c]

    # Per-section slot map: each tile gets the next slot starting from its
    # color's base. Order within section is the iteration order of
    # per_section_tiles[s].
    section_slots: list[dict[int, int]] = []
    for s, tiles in enumerate(per_section_tiles):
        base = color_bases[colors[s]]
        slot_map = {tile_id: base + offset for offset, tile_id in enumerate(tiles)}
        section_slots.append(slot_map)

    return color_bases, section_slots
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: 27 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — assign_section_slots (per-color VRAM ranges)"
```

---

## Task 6: Wire graph coloring into `ojz_strip_gen.py`

**Files:**
- Modify: `tools/ojz_strip_gen.py`

Replace A.2's global `pack_regions` flow with per-section coloring + per-section slot assignment + per-section blob emission.

- [ ] **Step 1: Replace the Pass 2 + Pass 3 + emission code**

In `tools/ojz_strip_gen.py`, find this block (currently in `generate()`):

```python
    # ---- Pass 2: dedupe across all sections, pack into regions, emit pools ----
    full_blob = decompress_full_ojz_art(OJZ_ART_PATH)
    sorted_indices, raw_tiles = collect_referenced_tiles(per_section_strips, full_blob)
    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)

    region1_cap = REGION1_TILE_CAPACITY
    if force_region1_cap is not None:
        region1_cap = force_region1_cap

    region2_start_slot = REGION2_VRAM_BASE // tile_dedupe.TILE_SIZE
    regions = [(0, region1_cap), (region2_start_slot, REGION2_TILE_CAPACITY)]
    slots = tile_dedupe.pack_regions(len(unique), regions)

    # Build src_idx → (vram_tile_slot, flip_bits) lookup
    src_to_slot: dict[int, tuple[int, int]] = {}
    for i, src_idx in enumerate(sorted_indices):
        canon_idx, flip_bits = mapping[i]
        src_to_slot[src_idx] = (slots[canon_idx], flip_bits)

    # Partition unique tiles by region
    r1_tiles = [unique[i] for i in range(len(unique)) if slots[i] < region2_start_slot]
    r2_tiles = [unique[i] for i in range(len(unique)) if slots[i] >= region2_start_slot]
```

…and the Pass 3 + emission code that follows.

Replace the entire block (Pass 2 + Pass 3 + emission + measurement) with:

```python
    # ---- Pass 2: dedupe across all sections ----
    full_blob = decompress_full_ojz_art(OJZ_ART_PATH)
    sorted_indices, raw_tiles = collect_referenced_tiles(per_section_strips, full_blob)
    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)

    # src_idx → canonical_idx + flip_bits
    src_to_canon: dict[int, tuple[int, int]] = {
        src_idx: mapping[i]
        for i, src_idx in enumerate(sorted_indices)
    }

    # ---- Pass 3: per-section unique canonical-tile lists ----
    sec_ids_in_order = list(per_section_strips.keys())
    per_section_canon_tiles: list[list[int]] = []
    for sec_id in sec_ids_in_order:
        seen: set[int] = set()
        ordered: list[int] = []
        for col in per_section_strips[sec_id]:
            for word in col:
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                canon_idx, _ = src_to_canon.get(src_idx, (0, 0))
                if canon_idx not in seen:
                    seen.add(canon_idx)
                    ordered.append(canon_idx)
        per_section_canon_tiles.append(ordered)

    # ---- Pass 4: section adjacency + coloring + slot assignment ----
    grid_w, grid_h = _ojz_grid_dimensions(sec_ids_in_order)
    edges = tile_dedupe.compute_adjacency(grid_w, grid_h)
    colors = tile_dedupe.color_sections(len(sec_ids_in_order), edges)
    color_bases, section_slots = tile_dedupe.assign_section_slots(
        per_section_canon_tiles, colors, region_start=0
    )

    # ---- Pass 5: rewrite each section's strips using its own slot map ----
    total_strips = 0
    first_strips = None
    for s_idx, sec_id in enumerate(sec_ids_in_order):
        slot_map = section_slots[s_idx]
        remapped_strips = []
        for col in per_section_strips[sec_id]:
            remapped_col = []
            for word in col:
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                canon_idx, flip_bits = src_to_canon.get(src_idx, (0, 0))
                vram_slot = slot_map.get(canon_idx, 0)
                remapped_col.append(
                    tile_dedupe.remap_nametable_word(word, vram_slot, flip_bits)
                )
            remapped_strips.append(remapped_col)

        out_a = os.path.join(out_dir, f"sec{sec_id}_strips_a.bin")
        write_strips_to_file(remapped_strips, out_a)
        out_b = os.path.join(out_dir, f"sec{sec_id}_strips_b.bin")
        with open(out_b, "wb") as f:
            f.write(bytes(len(remapped_strips) * STRIP_TILE_HEIGHT * 2))
        if first_strips is None:
            first_strips = remapped_strips
        total_strips += len(remapped_strips)

    # ---- Pass 6: emit per-section tile-art blobs ----
    for s_idx, sec_id in enumerate(sec_ids_in_order):
        sec_tiles = per_section_canon_tiles[s_idx]
        sec_out = os.path.join(out_dir, f"sec{sec_id}_tiles.bin")
        with open(sec_out, "wb") as f:
            for canon_idx in sec_tiles:
                f.write(unique[canon_idx])

    # ---- A.3 measurement ----
    raw_referenced = len(sorted_indices)
    deduped = len(unique)
    pct = (1.0 - deduped / raw_referenced) * 100 if raw_referenced else 0.0
    src_max = max(sorted_indices) if sorted_indices else 0
    src_min = min(sorted_indices) if sorted_indices else 0
    src_collisions = sum(1 for i in sorted_indices if i >= 1536)
    num_colors = max(colors) + 1 if colors else 0
    max_simultaneous = sum(
        max((len(per_section_canon_tiles[s]) for s in range(len(colors)) if colors[s] == c), default=0)
        for c in range(num_colors)
    )
    print(
        f"\n=== OJZ Act 1 — Phase A.3 measurement ===\n"
        f"  Source tile indices referenced: {raw_referenced} "
        f"(min={src_min}, max={src_max})\n"
        f"  Source indices ≥1536 (nametable collision risk): {src_collisions}\n"
        f"  Deduped (with flip canonicalization): {deduped} "
        f"({pct:.1f}% reduction)\n"
        f"  Section adjacency: {grid_w}×{grid_h} grid, {len(edges)} edges\n"
        f"  Chromatic number: {num_colors} (DSATUR greedy)\n"
        f"  Max simultaneously-resident: {max_simultaneous} tiles\n"
        f"  Color bases: {color_bases}\n"
    )
```

- [ ] **Step 2: Add the `_ojz_grid_dimensions` helper**

Insert before `def generate(...)`:

```python
def _ojz_grid_dimensions(sec_ids: list[str]) -> tuple[int, int]:
    """Read the OJZ act descriptor's grid_w / grid_h.

    OJZ act 1 uses a flat horizontal layout. For now, hard-coded to
    (len(sec_ids), 1). When future acts use 2D grids, parse the act
    descriptor or take grid dims as parameters.
    """
    return (len(sec_ids), 1)
```

- [ ] **Step 3: Update `test_full_pipeline_runs`**

Find `test_full_pipeline_runs` and replace its assertions block:

```python
            r1_path = os.path.join(td, "ojz_tiles_r1.bin")
            r2_path = os.path.join(td, "ojz_tiles_r2.bin")
            assert os.path.exists(r1_path), "region 1 pool not written"
            assert os.path.exists(r2_path), "region 2 pool not written (even if empty)"
            r1_size = os.path.getsize(r1_path)
            r2_size = os.path.getsize(r2_path)
            assert r1_size % 32 == 0, f"r1 size {r1_size} not a multiple of 32"
            assert r2_size % 32 == 0, f"r2 size {r2_size} not a multiple of 32"
            assert r1_size // 32 <= REGION1_TILE_CAPACITY
            assert r2_size // 32 <= REGION2_TILE_CAPACITY
```

with:

```python
            # A.3: per-section blobs (one per OJZ section)
            import glob
            sec_files = sorted(glob.glob(os.path.join(td, "sec*_tiles.bin")))
            assert len(sec_files) > 0, "no per-section tile blobs written"
            for f in sec_files:
                size = os.path.getsize(f)
                assert size % 32 == 0, f"{f} size {size} not a multiple of 32"
                # Each section's blob should be ≤ pool's deduped count × 32
                assert size <= REGION1_TILE_CAPACITY * 32
```

- [ ] **Step 4: Run self-tests**

```bash
python3 tools/ojz_strip_gen.py test 2>&1 | tail -5
```
Expected: all tests pass.

- [ ] **Step 5: Run the generator**

```bash
python3 tools/ojz_strip_gen.py generate 2>&1 | grep -A 10 'A.3 measurement'
```
Expected output:
```
=== OJZ Act 1 — Phase A.3 measurement ===
  Source tile indices referenced: 14 (min=0, max=1856)
  Source indices ≥1536 (nametable collision risk): 2
  Deduped (with flip canonicalization): 10 (28.6% reduction)
  Section adjacency: 16×1 grid, 15 edges
  Chromatic number: 2 (DSATUR greedy)
  Max simultaneously-resident: <some number ≤ 10> tiles
  Color bases: [0, <some>]
```

(The exact "max simultaneously-resident" depends on how OJZ's per-section tile distribution lands. Likely 4-8 since tiles are concentrated in cloud + first-ground bands.)

- [ ] **Step 6: Verify per-section blob files exist**

```bash
ls data/generated/ojz/act1/sec*_tiles.bin | head -5
```

Expected: 16 files (sec0_tiles.bin … sec11_tiles.bin, secA_tiles.bin … secD_tiles.bin).

- [ ] **Step 7: Commit**

```bash
git add tools/ojz_strip_gen.py
git commit -m "feat(tools): ojz_strip_gen — per-section coloring + per-section blobs"
```

---

## Task 7: build.sh — compress per-section tile blobs

**Files:**
- Modify: `build.sh`

A.2 compressed two region blobs. A.3 emits up to 16 per-section blobs (one per OJZ section). Replace the A.2 compression block with a loop that compresses every `sec*_tiles.bin` it finds.

- [ ] **Step 1: Replace the per-region compression with per-section**

In `build.sh`, find:

```bash
echo "Compressing OJZ region 1 tile pool with S4LZ..."
python3 "${TOOLS}/s4lz.py" compress --tile-delta \
    data/generated/ojz/act1/ojz_tiles_r1.bin \
    data/generated/ojz/act1/ojz_tiles_r1.s4lz

# Region 2 only emits a non-empty blob when there's spill; compress only if non-empty.
if [[ -s data/generated/ojz/act1/ojz_tiles_r2.bin ]]; then
    echo "Compressing OJZ region 2 tile pool with S4LZ..."
    python3 "${TOOLS}/s4lz.py" compress --tile-delta \
        data/generated/ojz/act1/ojz_tiles_r2.bin \
        data/generated/ojz/act1/ojz_tiles_r2.s4lz
else
    # No spill — write a 4-byte zero-length S4LZ stream so the BINCLUDE always exists.
    # Header: uncompressed size = 0 (BE word), flags = 0, reserved = 0
    printf '\x00\x00\x00\x00' > data/generated/ojz/act1/ojz_tiles_r2.s4lz
fi
```

Replace with:

```bash
echo "Compressing OJZ per-section tile blobs with S4LZ..."
for sec_bin in data/generated/ojz/act1/sec*_tiles.bin; do
    sec_s4lz="${sec_bin%.bin}.s4lz"
    if [[ -s "$sec_bin" ]]; then
        python3 "${TOOLS}/s4lz.py" compress --tile-delta "$sec_bin" "$sec_s4lz"
    else
        # Zero-length section — write a 4-byte zero-length S4LZ header so the BINCLUDE exists.
        printf '\x00\x00\x00\x00' > "$sec_s4lz"
    fi
done
```

- [ ] **Step 2: Run the build**

```bash
./build.sh -nl 2>&1 | grep -E 'Compressing|Compressed' | head -20
```

Expected: ~16 lines per section (one "Compressed: ..." per non-empty blob; zero-length sections show no output but their .s4lz file is created).

- [ ] **Step 3: Verify .s4lz files**

```bash
ls data/generated/ojz/act1/sec*_tiles.s4lz | wc -l
```
Expected: 16 (one per section).

- [ ] **Step 4: Commit**

```bash
git add build.sh
git commit -m "build: compress per-section tile blobs with S4LZ"
```

---

## Task 8: Extend `Sec` struct with per-section tile-art fields

**Files:**
- Modify: `structs.asm`

- [ ] **Step 1: Add fields to the Sec struct**

In `structs.asm`, find:

```asm
Sec struct
sec_strips_a        ds.l 1          ; $00 — plane A nametable strip array ptr (ROM)
sec_objects         ds.l 1          ; $04 — compact 4-byte object entries
sec_rings           ds.l 1          ; $08 — pattern-encoded ring entries
sec_plc             ds.l 1          ; $0C — S4LZ art PLC list
sec_pal             ds.l 1          ; $10 — 128-byte palette (4 lines × 32 bytes)
sec_scroll          ds.l 1          ; $14 — parallax layer table (Phase 4)
sec_raster_table    ds.l 1          ; $18 — raster command table (§7.2)
sec_strips_b        ds.l 1          ; $1C — plane B nametable strip array ptr (ROM)
sec_reserved        ds.l 1          ; $20 — reserved
sec_pal_cycle       ds.l 1          ; $24 — palette cycling script (Phase 4)
sec_sound_bank      ds.l 1          ; $28 — DAC sample bank pointer
sec_deform_table    ds.l 1          ; $2C — deformation table (Phase 4)
sec_anim_blocks     ds.l 1          ; $30 — animated tile script (Phase 4)
sec_collision       ds.l 1          ; $34 — flat 128×128 collision map
sec_flags           ds.w 1          ; $38 — SF_* bitmask
sec_music           ds.w 1          ; $3A — music track (0 = keep current)
sec_layer_mask      ds.b 1          ; $3C — parallax layer enable (Phase 4)
sec_camera_lookahead ds.b 1         ; $3D — lookahead pixels (0 = zone default)
sec_deform_speed    ds.b 1          ; $3E — deformation rate (Phase 4)
sec_transition_type ds.b 1          ; $3F — transition type (Phase 4)
Sec endstruct

    if Sec_len <> $40
      error "Sec struct is \{Sec_len} bytes, expected $40"
    endif
```

Replace `sec_reserved` (the longword at $20) with the new fields, and grow the struct by 4 bytes (8 bytes total: removing $20 reserved, adding two new $20+$24 fields, repurposing one):

Actually, the cleanest extension is to *append* new fields after the existing ones (avoiding any re-numbering of existing offsets that other code depends on). Append `tile_art_s4lz` (4) + `tile_art_vram` (2) + 2 pad bytes for alignment, taking the struct from $40 to $48:

```asm
Sec struct
sec_strips_a        ds.l 1          ; $00 — plane A nametable strip array ptr (ROM)
sec_objects         ds.l 1          ; $04 — compact 4-byte object entries
sec_rings           ds.l 1          ; $08 — pattern-encoded ring entries
sec_plc             ds.l 1          ; $0C — S4LZ art PLC list
sec_pal             ds.l 1          ; $10 — 128-byte palette (4 lines × 32 bytes)
sec_scroll          ds.l 1          ; $14 — parallax layer table (Phase 4)
sec_raster_table    ds.l 1          ; $18 — raster command table (§7.2)
sec_strips_b        ds.l 1          ; $1C — plane B nametable strip array ptr (ROM)
sec_reserved        ds.l 1          ; $20 — reserved
sec_pal_cycle       ds.l 1          ; $24 — palette cycling script (Phase 4)
sec_sound_bank      ds.l 1          ; $28 — DAC sample bank pointer
sec_deform_table    ds.l 1          ; $2C — deformation table (Phase 4)
sec_anim_blocks     ds.l 1          ; $30 — animated tile script (Phase 4)
sec_collision       ds.l 1          ; $34 — flat 128×128 collision map
sec_flags           ds.w 1          ; $38 — SF_* bitmask
sec_music           ds.w 1          ; $3A — music track (0 = keep current)
sec_layer_mask      ds.b 1          ; $3C — parallax layer enable (Phase 4)
sec_camera_lookahead ds.b 1         ; $3D — lookahead pixels (0 = zone default)
sec_deform_speed    ds.b 1          ; $3E — deformation rate (Phase 4)
sec_transition_type ds.b 1          ; $3F — transition type (Phase 4)
sec_tile_art_s4lz   ds.l 1          ; $40 — per-section S4LZ tile pool ptr (§2 A.3)
sec_tile_art_vram   ds.w 1          ; $44 — VRAM byte dest (color base × 32)
                    ds.w 1          ; $46 — pad
Sec endstruct

    if Sec_len <> $48
      error "Sec struct is \{Sec_len} bytes, expected $48"
    endif
```

- [ ] **Step 2: Build to confirm the struct change doesn't break callers**

```bash
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build (no callers reference `Sec_len` past $3F yet — those references are in `Section_GetSlotDef` via `lsl.w #6, d0` for `× 64`. We need to update that to `× 72`).

If the build fails or behavior breaks because of the size change, see Step 3.

- [ ] **Step 3: Update `Section_GetSlotDef` to use the new Sec_len**

In `engine/level/section.asm`, find:

```asm
Section_GetSlotDef:
        add.w   d0, d0                             ; slot_index × 2 bytes
        lea     (Slot_Section_Map).w, a0
        move.b  (a0, d0.w), d1                     ; d1.b = sec_x for this slot
        movea.l Act_sec_grid_ptr(a2), a1
        ; sec_x × Sec_len ($40) = sec_x × 64 = sec_x << 6
        moveq   #0, d0
        move.b  d1, d0
        lsl.w   #6, d0
        adda.w  d0, a1                             ; a1 → Sec struct for this section
        movea.l a1, a0
        rts
```

Replace the multiply-by-64 (`lsl.w #6, d0`) with a generic multiply by Sec_len. AS lets us compute it at assembly time. Since 72 ($48) isn't a power of 2, use `add+shifts` (sec_x × 72 = sec_x × 64 + sec_x × 8 = lsl#6 + lsl#3):

```asm
Section_GetSlotDef:
        add.w   d0, d0                             ; slot_index × 2 bytes
        lea     (Slot_Section_Map).w, a0
        move.b  (a0, d0.w), d1                     ; d1.b = sec_x for this slot
        movea.l Act_sec_grid_ptr(a2), a1
        ; sec_x × Sec_len ($48 = 72): compute as sec_x*64 + sec_x*8
        moveq   #0, d0
        move.b  d1, d0
        move.w  d0, d2
        lsl.w   #6, d0                             ; sec_x × 64
        lsl.w   #3, d2                             ; sec_x × 8
        add.w   d2, d0                             ; sec_x × 72 = Sec_len
        adda.w  d0, a1                             ; a1 → Sec struct for this section
        movea.l a1, a0
        rts
```

(Note: this introduces d2 as a clobber; update the docstring's clobber list.)

Update the comment block at the top of `Section_GetSlotDef`:
```asm
; Clobbers: d0–d2, a0–a1
```

- [ ] **Step 4: Build to confirm**

```bash
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add structs.asm engine/level/section.asm
git commit -m "feat(§2): Sec struct gains tile_art fields (size \$40 → \$48)"
```

---

## Task 9: Add `Section_LoadArt` routine + rewrite `Level_LoadArt`

**Files:**
- Modify: `engine/level/load_art.asm`

`Section_LoadArt` is the new per-section primitive: takes a Sec struct pointer, decompresses its S4LZ blob to Decomp_Buffer, queues a Critical DMA to the VRAM dest from `sec_tile_art_vram`. `Level_LoadArt` becomes a wrapper that calls `Section_LoadArt` for each initial slot.

- [ ] **Step 1: Replace the contents of `engine/level/load_art.asm`**

Open `engine/level/load_art.asm`. Replace the entire file with:

```asm
; Level art loader (§2 Phase 2 A.1/A.2/A.3)
; Blocking S4LZ → DMA pipeline. A.3 reorganized loading around per-section
; pools (graph-colored) instead of global region pools.

; -----------------------------------------------
; LoadArt_S4LZ — decompress an S4LZ stream and queue Critical DMA to VRAM.
;
; In:  a0 = source ROM pointer (S4LZ stream, word-aligned)
;      d0.w = VRAM byte destination (tile-slot * 32)
; Out: a0 = past end of compressed data (returned from S4LZ_Decompress)
; Clobbers: d0–d3, a0–a3
;
; Uses Decomp_Buffer (32 KB transient at $FFFF0000). For loads exceeding
; one VBlank's DMA budget, the caller is responsible for running with
; the display blanked off so multiple Critical DMAs can drain across one
; extended VBlank.
; -----------------------------------------------
LoadArt_S4LZ:
        movem.l d4-d6/a4, -(sp)
        move.w  d0, d6                              ; d6.w = VRAM dest
        movea.l a0, a4                              ; a4 = saved source ptr (size peek)
        move.w  (a4), d4                            ; d4.w = uncompressed size (BE)

        ; -- skip the entire decompress + DMA if size is zero (placeholder blob) --
        beq.s   .return

        lea     (Decomp_Buffer).l, a1               ; a1 = work buffer
        bsr.w   S4LZ_Decompress                     ; decompress; a0 advances past stream

        move.l  #Decomp_Buffer, d1                  ; d1 = source (RAM, $FFFF0000)
        moveq   #0, d2
        move.w  d6, d2                              ; d2.w = VRAM dest
        move.w  d4, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Critical
        bsr.w   VSync_Wait

.return:
        movem.l (sp)+, d4-d6/a4
        rts

; -----------------------------------------------
; Section_LoadArt — load one section's tile art group.
;
; In:  a0 = Sec struct pointer
; Out: none
; Clobbers: d0–d4, a0–a4
;
; A.3 behaviour: each section has its own S4LZ blob and VRAM dest.
; Sections in the same color class overlay each other in VRAM as the
; camera traverses; the leapfrog system guarantees that the two
; currently-resident slots hold ADJACENT sections, which by graph-
; coloring construction are in DIFFERENT colors → DIFFERENT VRAM ranges,
; so both render correctly simultaneously.
; -----------------------------------------------
Section_LoadArt:
        moveq   #0, d0
        move.w  sec_tile_art_vram(a0), d0           ; d0.w = VRAM byte dest
        movea.l sec_tile_art_s4lz(a0), a0           ; a0 = compressed S4LZ source
        cmpa.w  #0, a0
        beq.s   .skip                               ; null pointer → no art for this section
        bra.w   LoadArt_S4LZ                        ; tail call
.skip:
        rts

; -----------------------------------------------
; Level_LoadArt — load tile art for both initial slot sections.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d4, a0–a4
;
; A.3 behaviour: walks the slot section map and calls Section_LoadArt
; for each slot's currently-assigned section. At Section_Init time, both
; slots hold the starting section + its right neighbor (per leapfrog
; convention).
; -----------------------------------------------
Level_LoadArt:
        movem.l a0/a4, -(sp)
        movea.l a0, a4                              ; a4 = act ptr (saved across calls)

        ; -- slot 0 --
        moveq   #SLOT_LEFT, d0
        movea.l a4, a2                              ; a2 = act ptr for Section_GetSlotDef
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 0
        bsr.w   Section_LoadArt

        ; -- slot 1 --
        moveq   #SLOT_RIGHT, d0
        movea.l a4, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 1
        bsr.w   Section_LoadArt

        movem.l (sp)+, a0/a4
        rts
```

- [ ] **Step 2: Build to confirm linkage**

```bash
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add engine/level/load_art.asm
git commit -m "feat(§2): Section_LoadArt + Level_LoadArt walks slot map (A.3)"
```

---

## Task 10: Wire `Section_LoadArt` into teleport paths

**Files:**
- Modify: `engine/level/section.asm`

After each forward/backward teleport updates the slot map, the new section needs its tile art loaded.

- [ ] **Step 1: Add Section_LoadArt call after slot map update in `Section_TeleportFwd`**

In `engine/level/section.asm`, find `Section_TeleportFwd` (around line 183). After the slot-map updates and column-tracking reset but BEFORE the rts, add a Section_LoadArt call for the new slot 1 section:

Replace:

```asm
        ; -- reset column tracking so streaming refills the visible window --
        move.w  #SLOT_ORIGIN_L/8 - 1, (Section_Right_Col_Written).w
        move.w  #SLOT_ORIGIN_L/8,     (Section_Left_Col_Written).w

        move.b  #4, (Section_Teleport_Guard).w
        rts
```

(at the END of `Section_TeleportFwd`)

with:

```asm
        ; -- reset column tracking so streaming refills the visible window --
        move.w  #SLOT_ORIGIN_L/8 - 1, (Section_Right_Col_Written).w
        move.w  #SLOT_ORIGIN_L/8,     (Section_Left_Col_Written).w

        move.b  #4, (Section_Teleport_Guard).w

        ; -- A.3: load new slot 1 section's tile art (blocking) --
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 1
        bsr.w   Section_LoadArt
        rts
```

- [ ] **Step 2: Add Section_LoadArt call in `Section_TeleportBwd`**

Same idea for the backward teleport. Find `Section_TeleportBwd` (around line 210), add a Section_LoadArt call for the new slot 0 section after the slot-map update.

The end of Section_TeleportBwd currently is:

```asm
        ; -- reset column tracking so streaming refills the visible window --
        move.w  #SLOT_ORIGIN_L/8 - 1, (Section_Right_Col_Written).w
        move.w  #SLOT_ORIGIN_L/8,     (Section_Left_Col_Written).w
        move.b  #4, (Section_Teleport_Guard).w
        rts
```

Replace with:

```asm
        ; -- reset column tracking so streaming refills the visible window --
        move.w  #SLOT_ORIGIN_L/8 - 1, (Section_Right_Col_Written).w
        move.w  #SLOT_ORIGIN_L/8,     (Section_Left_Col_Written).w
        move.b  #4, (Section_Teleport_Guard).w

        ; -- A.3: load new slot 0 section's tile art (blocking) --
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 0
        bsr.w   Section_LoadArt
        rts
```

- [ ] **Step 3: Build to confirm**

```bash
./build.sh 2>&1 | grep -E 'error|Build complete' | head -5
```
Expected: `Build complete: s4.bin — ...`.

- [ ] **Step 4: Commit**

```bash
git add engine/level/section.asm
git commit -m "feat(§2): Section_TeleportFwd/Bwd load new section's tile art (A.3)"
```

---

## Task 11: Populate per-section tile_art fields in OJZ act descriptor

**Files:**
- Modify: `data/levels/ojz/act1/act_descriptor.asm`

Each of OJZ act 1's 16 sections needs `sec_tile_art_s4lz` set to its per-section S4LZ blob, and `sec_tile_art_vram` set to the VRAM byte dest computed from its color's base. We need to know the color bases — which the build tool prints. **For OJZ's path graph, color 0 starts at slot 0 and color 1 starts at slot N (where N = max tiles per section in color 0).** The exact value comes from running the generator.

The simplest approach: hard-code the 16 BINCLUDEs and per-section pointers, leaving `tile_art_vram` as $0000 + per-color base computed at compile time via assembler `function`. But the build tool doesn't yet emit those base values into asm.

Practical workaround: the build tool already computes `color_bases`. Have the build emit a small asm include file (e.g. `data/generated/ojz/act1/sec_vram_bases.asm`) that defines per-section `OJZ_SecN_Vram` constants. The act descriptor BINCLUDEs that file and uses the constants.

Per-task-7-clarification implementation:

- [ ] **Step 1: Make ojz_strip_gen.py emit `sec_vram_bases.asm`**

Reopen `tools/ojz_strip_gen.py`. After the per-section blob emission (Pass 6) and before the measurement print, add:

```python
    # ---- Pass 7: emit per-section VRAM-base constants for the act descriptor ----
    bases_path = os.path.join(out_dir, "sec_vram_bases.asm")
    with open(bases_path, "w") as f:
        f.write("; Auto-generated by tools/ojz_strip_gen.py — DO NOT EDIT\n")
        f.write("; Per-section VRAM byte destinations (color_base × 32 bytes/tile)\n")
        for s_idx, sec_id in enumerate(sec_ids_in_order):
            base_slot = color_bases[colors[s_idx]]
            f.write(f"OJZ_Sec{sec_id}_Vram = {base_slot} * 32\n")
```

- [ ] **Step 2: Re-run the generator**

```bash
python3 tools/ojz_strip_gen.py generate > /dev/null
cat data/generated/ojz/act1/sec_vram_bases.asm | head -20
```

Expected: 16 lines of `OJZ_SecN_Vram = K * 32` constants.

- [ ] **Step 3: Update `data/levels/ojz/act1/act_descriptor.asm` for per-section fields**

Currently OJZ_Act1_Descriptor has act-wide tile_art fields from A.2. Those are obsolete with A.3 — remove them. Then update each Sec struct entry to include the new tile_art fields.

First, include the auto-generated VRAM bases file. At the top of `data/levels/ojz/act1/act_descriptor.asm` (just below the existing comment), insert:

```asm
    include "data/generated/ojz/act1/sec_vram_bases.asm"
```

Then, remove the act-wide fields from `OJZ_Act1_Descriptor`. Find:

```asm
    dc.l    OJZ_Tiles_R1_S4LZ       ; tile_art_s4lz (region 1)
    dc.w    $0000                   ; tile_art_vram (VRAM byte $0000)
    dc.l    OJZ_Tiles_R2_S4LZ       ; tile_art_r2_s4lz (region 2; 4-byte placeholder if no spill)
    dc.w    0                       ; pad
    align 2
```

Replace with:

```asm
    align 2
```

(Now the act descriptor ends after `cam_max_y`. The Act struct in structs.asm needs a corresponding shrink — see Step 4 below.)

For each Sec entry (sec0 through sec11 + secA-secD), add the new tile_art fields. Each Sec entry currently looks like:

```asm
OJZ_Sec0:
    dc.l    OJZ_Sec0_Strips_A       ; sec_strips_a
    dc.l    0, 0, 0                 ; sec_objects, sec_rings, sec_plc
    dc.l    OJZ_Palette             ; sec_pal
    dc.l    0, 0                    ; sec_scroll, sec_raster_table
    dc.l    OJZ_Sec0_Strips_B       ; sec_strips_b
    dc.l    0, 0, 0, 0, 0, 0        ; sec_reserved, sec_pal_cycle, sec_sound_bank, sec_deform_table, sec_anim_blocks, sec_collision
    dc.w    0                       ; sec_flags
    dc.w    0                       ; sec_music
    dc.b    0, 0, 0, 0              ; sec_layer_mask, sec_camera_lookahead, sec_deform_speed, sec_transition_type
    align 2
```

Append two new fields (struct grew $40 → $48). Modify each Sec entry to add the tile_art fields. For sec0:

```asm
OJZ_Sec0:
    dc.l    OJZ_Sec0_Strips_A       ; sec_strips_a
    dc.l    0, 0, 0                 ; sec_objects, sec_rings, sec_plc
    dc.l    OJZ_Palette             ; sec_pal
    dc.l    0, 0                    ; sec_scroll, sec_raster_table
    dc.l    OJZ_Sec0_Strips_B       ; sec_strips_b
    dc.l    0, 0, 0, 0, 0, 0        ; sec_reserved, sec_pal_cycle, sec_sound_bank, sec_deform_table, sec_anim_blocks, sec_collision
    dc.w    0                       ; sec_flags
    dc.w    0                       ; sec_music
    dc.b    0, 0, 0, 0              ; sec_layer_mask, sec_camera_lookahead, sec_deform_speed, sec_transition_type
    dc.l    OJZ_Sec0_Tiles_S4LZ     ; sec_tile_art_s4lz (§2 A.3)
    dc.w    OJZ_Sec0_Vram           ; sec_tile_art_vram
    dc.w    0                       ; pad
    align 2
```

Apply the same pattern to all 16 sections, substituting `Sec0` → `Sec1`, `Sec2`, ..., `Sec11`, `SecA`, `SecB`, `SecC`, `SecD`. This is mechanical text repetition — use a search-replace if the editor supports it.

- [ ] **Step 4: Replace the existing BINCLUDE block with per-section BINCLUDEs**

In the same file, find:

```asm
OJZ_Tiles_R1_S4LZ: BINCLUDE "data/generated/ojz/act1/ojz_tiles_r1.s4lz"
OJZ_Tiles_R2_S4LZ: BINCLUDE "data/generated/ojz/act1/ojz_tiles_r2.s4lz"
```

Replace with:

```asm
OJZ_Sec0_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec0_tiles.s4lz"
OJZ_Sec1_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec1_tiles.s4lz"
OJZ_Sec2_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec2_tiles.s4lz"
OJZ_Sec3_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec3_tiles.s4lz"
OJZ_Sec4_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec4_tiles.s4lz"
OJZ_Sec5_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec5_tiles.s4lz"
OJZ_Sec6_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec6_tiles.s4lz"
OJZ_Sec7_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec7_tiles.s4lz"
OJZ_Sec8_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec8_tiles.s4lz"
OJZ_Sec9_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/sec9_tiles.s4lz"
OJZ_Sec10_Tiles_S4LZ: BINCLUDE "data/generated/ojz/act1/sec10_tiles.s4lz"
OJZ_Sec11_Tiles_S4LZ: BINCLUDE "data/generated/ojz/act1/sec11_tiles.s4lz"
OJZ_SecA_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/secA_tiles.s4lz"
OJZ_SecB_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/secB_tiles.s4lz"
OJZ_SecC_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/secC_tiles.s4lz"
OJZ_SecD_Tiles_S4LZ:  BINCLUDE "data/generated/ojz/act1/secD_tiles.s4lz"
```

- [ ] **Step 5: Shrink Act_Desc back to size before A.2 added the region-2 fields**

In `structs.asm`, find:

```asm
Act struct
sec_grid_ptr        ds.l 1          ; $00 — pointer to section definition array
grid_w              ds.w 1          ; $04 — sections wide
grid_h              ds.w 1          ; $06 — sections tall
start_local_x       ds.w 1          ; $08 — player start X within section (0–$7FF)
start_local_y       ds.w 1          ; $0A — player start Y within section
start_sec_x         ds.b 1          ; $0C — starting section X index
start_sec_y         ds.b 1          ; $0D — starting section Y index
cam_min_x           ds.w 1          ; $0E — camera X lower bound (pixels)
cam_max_x           ds.w 1          ; $10 — camera X upper bound (pixels)
cam_min_y           ds.w 1          ; $12 — camera Y lower bound (pixels)
cam_max_y           ds.w 1          ; $14 — camera Y upper bound (pixels)
tile_art_s4lz       ds.l 1          ; $16 — pointer to S4LZ-compressed FG tile pool, region 1 (§2 A.1)
tile_art_vram       ds.w 1          ; $1A — VRAM byte destination for region 1
tile_art_r2_s4lz    ds.l 1          ; $1C — pointer to region-2 S4LZ pool (0 = no spill) (§2 A.2)
                    ds.w 1          ; $20 — pad to align next long
Act endstruct

    if Act_len <> $22
      error "Act struct is \{Act_len} bytes, expected $22"
    endif
```

Replace with (removing all tile_art fields, A.3 makes them per-Sec instead of per-Act):

```asm
Act struct
sec_grid_ptr        ds.l 1          ; $00 — pointer to section definition array
grid_w              ds.w 1          ; $04 — sections wide
grid_h              ds.w 1          ; $06 — sections tall
start_local_x       ds.w 1          ; $08 — player start X within section (0–$7FF)
start_local_y       ds.w 1          ; $0A — player start Y within section
start_sec_x         ds.b 1          ; $0C — starting section X index
start_sec_y         ds.b 1          ; $0D — starting section Y index
cam_min_x           ds.w 1          ; $0E — camera X lower bound (pixels)
cam_max_x           ds.w 1          ; $10 — camera X upper bound (pixels)
cam_min_y           ds.w 1          ; $12 — camera Y lower bound (pixels)
cam_max_y           ds.w 1          ; $14 — camera Y upper bound (pixels)
Act endstruct

    if Act_len <> $16
      error "Act struct is \{Act_len} bytes, expected $16"
    endif
```

- [ ] **Step 6: Build to verify all the moving parts align**

```bash
./build.sh 2>&1 | grep -E 'error|Build complete' | head -5
```
Expected: `Build complete: s4.bin — ...`. If errors appear, the most likely cause is missing per-section additions to Sec entries (Step 3) — verify all 16 sections have the new `dc.l OJZ_SecN_Tiles_S4LZ` + `dc.w OJZ_SecN_Vram` + pad.

- [ ] **Step 7: Commit**

```bash
git add tools/ojz_strip_gen.py structs.asm data/levels/ojz/act1/act_descriptor.asm
git commit -m "feat(§2): per-section tile_art fields for OJZ act 1 (A.3)"
```

---

## Task 12: Verify default OJZ build in Exodus

**Files:** none (Exodus interaction)

- [ ] **Step 1: Tell the user to reload `s4.bin`**

Tell the user: "Please reload `s4.bin` in Exodus."

- [ ] **Step 2: Sanity-check Exodus state**

`mcp__exodus__emulator_status` — verify running, PC at `VSync_Wait`, frame_token > 0.

- [ ] **Step 3: Verify decompressed tile data in Decomp_Buffer**

`mcp__exodus__emulator_read_memory(symbol="Decomp_Buffer", len=320)` — should show a section's tile data (the LAST decompressed batch wins; with two initial slots loaded, it's slot 1's section).

- [ ] **Step 4: Visual verification**

`mcp__exodus__emulator_screenshot` — should show OJZ's clean black sky + cloud band + sparse marks. Visually identical to A.1/A.2 default.

- [ ] **Step 5: Section transition test**

Drive the camera horizontally to cross at least one section boundary:

```python
# Pseudo — actual MCP calls below
mcp__exodus__emulator_write_memory(symbol="Camera_X", value=<engine X past section 0/1 boundary>, width=4)
# Then take a screenshot.
```

Compute target Camera_X:
- SLOT_ORIGIN_L = $200; SECTION_FWD_THRESHOLD = $1200 (engine pixels)
- Setting Camera_X to e.g. $1300 (= 0x13000000 in 16.16) puts the camera past the FWD threshold; Section_Check fires Section_TeleportFwd; Section_LoadArt loads the new section's tiles; rendering should remain glitch-free.

After the write, screenshot. Verify visually that the new section's tiles render cleanly with no garbage, no flicker, no nametable corruption.

- [ ] **Step 6: Reset Camera_X**

`mcp__exodus__emulator_write_memory(symbol="Camera_X", value=39845888, width=4)` — back to start position ($02600000).

- [ ] **Step 7: No commit — verification only**

---

## Task 13: Update measurements log with A.3 numbers

**Files:**
- Modify: `docs/research/tile-pipeline-measurements.md`

- [ ] **Step 1: Capture A.3 measurement output**

```bash
python3 tools/ojz_strip_gen.py generate 2>&1 | grep -A 12 'A.3 measurement'
```

Note the numbers: chromatic number, max simultaneously-resident, color bases.

- [ ] **Step 2: Edit the measurements doc**

Open `docs/research/tile-pipeline-measurements.md` and find the A.3 row in the table (currently `| A.3 | tbd | ... |`). Replace with concrete numbers from Step 1's output. Add a "headline" paragraph below the existing A.2 paragraph explaining what A.3 changed:

> **A.3 reorganizes the same 10-tile deduped pool around per-section art groups colored over the section adjacency graph.** Default OJZ has 16 sections in a horizontal chain (path graph), chromatic number 2 — sections alternate between color 0 and color 1. Max simultaneously-resident tiles drops from `(sum of all unique tiles across sections)` to `(max color's max-section tiles)`. For OJZ's small dataset this difference is small, but the structural change is what unblocks A.4's per-section streaming and lets future bigger-data zones load only what they need.

- [ ] **Step 3: Commit**

```bash
git add docs/research/tile-pipeline-measurements.md
git commit -m "docs(research): A.3 measurements — graph coloring on OJZ"
```

---

## Task 14: Update DEFERRED_WORK.md

**Files:**
- Modify: `docs/DEFERRED_WORK.md`

- [ ] **Step 1: Add A.3 to the Done section above A.2's entry**

Open `docs/DEFERRED_WORK.md`. Find the A.2 done entry:

```
### §2 Phase 2 Layer A.2 — Multi-region VRAM Packing — 2026-04-26
```

Insert immediately ABOVE it:

```markdown
### §2 Phase 2 Layer A.3 — Build-time Graph Coloring — <today's date>
**Completed in:** §2 Phase 2 Layer A.3
**What:** Section adjacency graph + DSATUR greedy coloring + per-section VRAM-slot assignment, all at build time. `tile_dedupe.py` gained `compute_adjacency`, `color_sections`, `assign_section_slots`. `tools/ojz_strip_gen.py` emits per-section tile blobs (one per OJZ section) and a per-section VRAM-base constants file. `Sec` struct gained `tile_art_s4lz` longword + `tile_art_vram` word (struct $40 → $48; `Section_GetSlotDef` updated to multiply by $48 = 72 instead of 64). New `Section_LoadArt` decompresses + DMAs one section's blob; `Level_LoadArt` walks the slot map and calls it for both initial slots; `Section_TeleportFwd`/`Bwd` call it for the new section after each teleport. The leapfrog system's adjacency invariant guarantees that the two visible slots always hold sections in DIFFERENT colors → DIFFERENT VRAM ranges → both render correctly simultaneously. A.2's region-1/region-2 fields removed from `Act_Desc` (multi-region packing remains in `tile_dedupe` for future use; A.3's per-section model is the active path).
**OJZ measurement:** 16 sections in a horizontal chain → 15 adjacency edges → chromatic number 2 (path graph is bipartite). Max simultaneously-resident: <fill in from Task 13 output>.
**Verified in Exodus:** Default rendering matches A.2; section transitions trigger blocking `Section_LoadArt` correctly; no nametable corruption, no flicker.
**See:** `docs/research/section-graph-coloring.md`, `docs/research/tile-pipeline-measurements.md`.

```

(Replace `<today's date>` and `<fill in from Task 13 output>` with actual values when this task runs.)

- [ ] **Step 2: Commit**

```bash
git add docs/DEFERRED_WORK.md
git commit -m "docs: §2 A.3 — build-time graph coloring complete"
```

---

## Task 15: s4budget + final lint check

**Files:** Read-only

- [ ] **Step 1: Run the budget tool**

```bash
python3 tools/s4budget.py s4.lst s4.bin --summary
```
Expected: ROM ~639-650 KB; RAM ~41 KB. A.3 should add a small amount of ROM (per-section S4LZ blobs, around 16 × ~30 bytes = 0.5 KB) plus a few hundred bytes of new asm code.

- [ ] **Step 2: Run full lint**

```bash
./build.sh
```
Expected: clean build; warning count should match A.1's baseline (no new warnings introduced by A.3).

- [ ] **Step 3: No commit — verification only**

---

## Task 16: Merge to master

**Files:** none (git only)

- [ ] **Step 1: Verify clean working tree**

```bash
git status
git log --oneline master..HEAD
```
Expected: clean tree; commit list shows the work from Tasks 0-14.

- [ ] **Step 2: Merge with --no-ff**

```bash
git checkout master
git merge --no-ff feat/s2-a3-graph-coloring -m "$(cat <<'EOF'
Merge §2 Phase 2 Layer A.3: build-time graph coloring

Reorganizes the deduped tile pool around sections rather than the
global pool. Build tool computes the section adjacency graph from the
act descriptor (4-neighbor, OJZ act 1 = path graph), DSATUR-greedy
colors it (chromatic number 2 for paths), and emits per-section S4LZ
blobs at per-section VRAM destinations. Engine's new Section_LoadArt
decompresses + DMAs one section's blob; Section_Init loads both
initial slots; Section_TeleportFwd/Bwd load the new section after each
teleport.

The leapfrog system's invariant (slots always hold ADJACENT sections)
combines with the coloring (adjacent = different colors = different
VRAM ranges) to guarantee both visible slots render correctly
simultaneously, even as same-color sections share VRAM ranges across
camera transitions.

A.4 (Deferrable streaming) replaces the blocking Section_LoadArt calls
with streaming. A.5 (per-section background art) is the final layer.
EOF
)"
```

- [ ] **Step 3: Verify the merged state builds clean**

```bash
./build.sh
```
Expected: clean build on master.

- [ ] **Step 4: Delete the feature branch**

```bash
git branch -d feat/s2-a3-graph-coloring
git status
git log --oneline -3
```

---

## Self-review checklist (run before claiming done)

- [ ] All 27 unit tests in `tools/test_tile_dedupe.py` pass (16 from A.1+A.2 + 4 + 4 + 3 new)
- [ ] `python3 tools/ojz_strip_gen.py test` passes
- [ ] `python3 tools/ojz_strip_gen.py generate` prints the A.3 measurement block with chromatic number 2 for OJZ
- [ ] 16 `secN_tiles.bin` and 16 `secN_tiles.s4lz` files exist in `data/generated/ojz/act1/`
- [ ] `data/generated/ojz/act1/sec_vram_bases.asm` exists and defines all 16 `OJZ_SecN_Vram` constants
- [ ] `./build.sh` produces `s4.bin` with no errors and no new lint warnings beyond A.2's baseline
- [ ] In Exodus: scroll test renders identically to A.2 at the start position
- [ ] In Exodus: cross at least one section boundary; new section renders cleanly with no nametable corruption
- [ ] `docs/DEFERRED_WORK.md` has the A.3 entry in the Done section with today's date
- [ ] `docs/research/tile-pipeline-measurements.md` has the A.3 row populated
- [ ] Build-tool and asm-side per-section vram bases stay in sync (build emits the asm include; manual editing of those values is forbidden)
