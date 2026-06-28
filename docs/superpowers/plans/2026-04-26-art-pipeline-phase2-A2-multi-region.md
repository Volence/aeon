# §2 Phase 2 — Layer A.2: Multi-region VRAM Packing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the deduped tile pool overflows the 1536-tile primary art region, spill into a secondary VRAM region carved out of Plane B's off-screen nametable rows. Adds a build-tool stress flag (`--force-region1-cap`) so the spill path can be exercised on data that doesn't naturally exceed 1536 (which OJZ act 1 currently doesn't).

**Architecture:** `tile_dedupe.py` gains a `pack_regions(unique_count, regions)` pass that assigns each canonical tile a final VRAM tile-slot, filling region 1 first and overflowing into region 2. Strips remap to the per-canonical VRAM slot rather than to a flat canonical-index. `ojz_strip_gen.py` emits two pool blobs (`ojz_tiles_r1.bin` and `ojz_tiles_r2.bin`) which `build.sh` S4LZ-compresses. `Act_Desc` gets a second `tile_art_r2_s4lz` pointer; `Level_LoadArt` calls `LoadArt_S4LZ` once per non-empty region. Region 2's VRAM destination is a fixed engine constant (`REGION2_VRAM_BASE`), determined by Task 1's research.

**Tech Stack:** Python 3 + `unittest` (build tool), 68000 assembly with the AS Macro Assembler (engine), existing S4LZ infrastructure.

**Spec:** `docs/superpowers/specs/2026-04-26-art-pipeline-phase2-design.md` (Phase A.2 section)

**Out of scope:** Graph coloring (A.3), Deferrable streaming (A.4), per-section BG (A.5).

---

## File map

**New files:**
- `docs/research/multi-region-packing.md` — Task 1 research output

**Modified files:**
- `tools/tile_dedupe.py` — add `pack_regions()`; rename `remap_nametable_word`'s `canonical_index` parameter to `vram_tile_slot`
- `tools/test_tile_dedupe.py` — tests for `pack_regions`; update existing remap tests for renamed parameter
- `tools/ojz_strip_gen.py` — add `--force-region1-cap` CLI flag, two-region partition + emission
- `build.sh` — compress both region blobs (skip empty)
- `constants.asm` — `REGION1_TILE_CAPACITY`, `REGION2_VRAM_BASE`, `REGION2_TILE_CAPACITY`
- `structs.asm` — `Act_Desc` gains `tile_art_r2_s4lz` longword (size: $1C → $20)
- `data/levels/ojz/act1/act_descriptor.asm` — populate region-2 pointer; add `OJZ_Tiles_R2_S4LZ` BINCLUDE (or zero if no spill)
- `engine/level/load_art.asm` — `Level_LoadArt` calls `LoadArt_S4LZ` for region 2 if pointer non-null
- `docs/research/tile-pipeline-measurements.md` — append A.2 row(s)
- `docs/DEFERRED_WORK.md` — close any A.2-relevant items

---

## Task 0: Create feature branch

**Files:** none (git only)

- [ ] **Step 1: Create and check out the A.2 feature branch from master**

Run:
```bash
git checkout master
git status
git checkout -b feat/s2-a2-multi-region
git status
```

Expected: clean working tree, branch `feat/s2-a2-multi-region` checked out.

---

## Task 1: Research — region-2 boundary, character-DMA conflict, full CLAUDE.md sweep

**Files:**
- Create: `docs/research/multi-region-packing.md`

**This research task is mandatory per `CLAUDE.md`'s research checklist. Do all of it, not just the listed targets per the user's stored "research breadth" feedback.**

### Required source coverage (CLAUDE.md mandate, not a subset)

- [ ] **Step 1: All 7 reference disassemblies**

For each, look at how it lays out VRAM regions, whether it ever stores art-like data inside off-screen nametable rows, and whether character DMA targets conflict with static art:

```bash
ls /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/
grep -rn 'plane.*[ab]\|nametable\|sprite.*table\|VRAM' /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Sonic_3___Knuckles__SCE_/ 2>/dev/null | head -10
ls "/home/volence/sonic_hacks/sonic_hack/"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm"
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm"
```

For each project, search for VRAM-layout related symbols (e.g. `VRAM`, `VDP_REG_05`, `sprite_attr`, `nametable_a`, `nametable_b`). Note any project that uses Plane B's off-screen rows for art or anything other than nametable data.

- [ ] **Step 2: Online sources**

Use WebFetch on each of these (catch failures and continue):
- `https://plutiedev.com/tiles-and-palettes` — VRAM layout / off-screen embedding
- `https://plutiedev.com/scrolling-the-screen` — plane configuration, scroll limits
- `https://md.railgun.works/index.php?title=VDP_Plane_Sizes` (or whatever URL the wiki uses for plane configuration) — fetch, then search the wiki for "Plane B off-screen" or similar
- `https://segaretro.org/Sega_Mega_Drive/Memory_map` — VDP memory map references
- Search SpritesMind forum for "off-screen nametable" / "Plane B unused area"

Report back which sources had relevant content and which were 404 / not useful.

- [ ] **Step 3: GitHub homebrew check**

Look at any homebrew Genesis project that uses 64×64 planes (Vectorman is the only commercial one but homebrew may have followed). Try Xeno Crisis, Tanglewood, Demons of Asteborg if accessible.

- [ ] **Step 4: Modern engine literature**

Search briefly for "off-screen nametable embedding" or analogous "embed data in unused VRAM region" patterns. NES has similar concepts (CHR-RAM swaps); SNES has VRAM bank tricks. Document anything relevant from outside the Genesis world.

- [ ] **Step 5: Compute the safe region-2 boundary for aeon**

Concrete numbers (Task 1 must establish these in the research doc):

The OJZ act descriptor has `cam_max_y = 128` (pixels). Bottom of visible viewport = camera_y + 224 px = max 352 px = nametable row 44 (352 / 8). Rows 45-63 of Plane B are guaranteed-off-screen for OJZ act 1 with current cam_max_y.

Plane B nametable lives at VRAM byte $E000-$FFFF. Each nametable row is 64 cols × 2 bytes = 128 bytes.
- Row 45 starts at $E000 + 45 × 128 = $E000 + $1680 = $F680
- Row 48 starts at $E000 + 48 × 128 = $E000 + $1800 = $F800

Decision options:
- **Option A:** Region 2 = $F680..$FFFF = 19 rows × 128 bytes = 2432 bytes = 76 tiles. Tight against the actual visible boundary.
- **Option B:** Region 2 = $F800..$FFFF = 16 rows × 128 bytes = 2048 bytes = 64 tiles. 3-row safety margin.
- **Option C:** Region 2 = $FC00..$FFFF = 8 rows × 128 bytes = 1024 bytes = 32 tiles. 7-row safety margin; never visible regardless of cam_max_y < 352 px.

Pick one based on research findings. Justify in the research doc. Recommendation if research turns up no new info: **Option B** — meaningful capacity (64 tiles) with a comfortable margin against future cam_max_y increases.

- [ ] **Step 6: Character-DMA conflict analysis**

Per ENGINE_ARCHITECTURE.md §2.3, character sprite tiles DMA into Plane A's off-screen nametable rows. Region 2 lives in Plane B. Confirm:
- Plane A and Plane B nametables occupy disjoint VRAM regions ($C000-$DFFF vs $E000-$FFFF)
- No character-DMA target falls inside Plane B
- No other VDP table (sprite attr at $D800, HScroll at $DC00) falls inside Plane B

Record the answer in the research doc. If anything contradicts the assumption, flag it loudly.

- [ ] **Step 7: Write the research notes**

Write `docs/research/multi-region-packing.md` with these sections (no other structure):
1. **Sources reviewed** — every source actually opened, including unlisted material from broader search
2. **Region-2 boundary decision** — chosen option (A/B/C) with one paragraph of justification grounded in the research findings; explicit numeric boundaries in VRAM bytes and tile slots
3. **Character-DMA conflict result** — one paragraph confirming or flagging
4. **Engine constants to add** — concrete `equ` values for `REGION2_VRAM_BASE` (byte addr), `REGION2_TILE_CAPACITY`, and `REGION1_TILE_CAPACITY`
5. **Anything that changes ENGINE_ARCHITECTURE.md** — explicit list (state "none" if so)

- [ ] **Step 8: Commit research notes**

```bash
git add docs/research/multi-region-packing.md
git commit -m "docs(research): multi-region VRAM packing for §2 A.2

Establishes region-2 boundary, character-DMA conflict analysis, and
engine constants for the A.2 plan. Sources cover all 7 disassemblies
plus plutiedev/md.railgun/SpritesMind/GitHub homebrew per CLAUDE.md
research checklist."
```

---

## Task 2: Apply research findings to ENGINE_ARCHITECTURE.md (conditional)

**Files:**
- Modify (conditional): `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: Check the research notes for arch-doc-changing items**

Open `docs/research/multi-region-packing.md` section 5 ("Anything that changes ENGINE_ARCHITECTURE.md").

- [ ] **Step 2a: If list is empty, skip Task 2**

- [ ] **Step 2b: If list is non-empty**

Apply the listed changes surgically to §2.3 (or the relevant subsection) of `docs/ENGINE_ARCHITECTURE.md`. Commit:
```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(arch): apply A.2 research findings to §2.3"
```

---

## Task 3: Add `pack_regions` to `tile_dedupe.py` (TDD)

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py`

The existing `dedupe_tiles` returns a list of unique canonical tiles indexed `[0..N)`. With multi-region packing, each canonical tile lands in a specific VRAM tile slot determined by region capacities. `pack_regions` does that assignment.

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_tile_dedupe.py` (after the existing classes; before `if __name__ == "__main__":`):

```python
class TestPackRegions(unittest.TestCase):
    def test_packs_into_first_region_when_fits(self):
        from tile_dedupe import pack_regions
        # 3 unique tiles, regions = [(start=0, capacity=1536), (start=1984, capacity=64)]
        slots = pack_regions(3, [(0, 1536), (1984, 64)])
        self.assertEqual(slots, [0, 1, 2], "all 3 fit in region 0 starting at slot 0")

    def test_spills_into_second_region_when_first_exhausted(self):
        from tile_dedupe import pack_regions
        # 5 unique tiles, region 0 capacity = 3 → 2 tiles spill into region 1
        slots = pack_regions(5, [(0, 3), (1984, 64)])
        self.assertEqual(
            slots,
            [0, 1, 2, 1984, 1985],
            "first 3 in region 0; remainder starts at region 1's base 1984",
        )

    def test_raises_on_total_overflow(self):
        from tile_dedupe import pack_regions
        # 10 unique tiles, total capacity = 5 → must raise
        with self.assertRaises(OverflowError):
            pack_regions(10, [(0, 3), (1984, 2)])

    def test_skips_zero_capacity_region(self):
        from tile_dedupe import pack_regions
        # First region has 0 capacity; everything goes to region 1
        slots = pack_regions(2, [(0, 0), (1984, 64)])
        self.assertEqual(slots, [1984, 1985])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -5
```
Expected: 4 errors (`ImportError: cannot import name 'pack_regions'`).

- [ ] **Step 3: Implement `pack_regions`**

Append to `tools/tile_dedupe.py`:

```python
def pack_regions(
    unique_count: int,
    regions: list[tuple[int, int]],
) -> list[int]:
    """Assign each canonical tile to a VRAM tile slot.

    `regions` is a list of (start_tile_slot, capacity) tuples in fill order.
    Returns a list of length `unique_count` where slots[i] is the VRAM
    tile slot assigned to canonical tile i.

    Raises OverflowError if total capacity is insufficient.
    """
    slots: list[int] = []
    region_idx = 0
    region_used = 0
    for canon_idx in range(unique_count):
        # Skip exhausted (or zero-capacity) regions
        while region_idx < len(regions) and region_used >= regions[region_idx][1]:
            region_idx += 1
            region_used = 0
        if region_idx >= len(regions):
            raise OverflowError(
                f"Tile pool exceeds region capacity at canonical tile {canon_idx}"
            )
        slots.append(regions[region_idx][0] + region_used)
        region_used += 1
    return slots
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: 16 tests pass (12 existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — pack_regions for multi-region VRAM"
```

---

## Task 4: Rename `canonical_index` parameter to `vram_tile_slot`

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py`

Now that the tile-index field of nametable words is set by `pack_regions`'s output rather than the canonical-list position, rename the parameter for clarity. Behavior is unchanged when the caller passes the canonical index directly (as A.1 did) — both interpretations are bit-equivalent up to the 11-bit tile-index field.

- [ ] **Step 1: Update `remap_nametable_word` signature**

In `tools/tile_dedupe.py`, change:
```python
def remap_nametable_word(word: int, canonical_index: int, canon_flip_bits: int) -> int:
    """Rewrite a 16-bit nametable word for the deduped tile space.

    Preserves priority + palette; replaces tile_index with canonical_index;
    XORs the original H/V bits with canon_flip_bits to recover the original
    visual orientation.
    """
    # Strip old tile_index
    high = word & ~NAMETABLE_TILE_MASK
    if canon_flip_bits & 1:
        high ^= NAMETABLE_H_BIT
    if canon_flip_bits & 2:
        high ^= NAMETABLE_V_BIT
    return high | (canonical_index & NAMETABLE_TILE_MASK)
```

to:
```python
def remap_nametable_word(word: int, vram_tile_slot: int, canon_flip_bits: int) -> int:
    """Rewrite a 16-bit nametable word with a final VRAM tile slot.

    Preserves priority + palette; replaces tile_index with vram_tile_slot;
    XORs the original H/V bits with canon_flip_bits to recover the original
    visual orientation.

    The tile-index field is 11 bits (0-2047), spanning the full VRAM tile
    range. Region 1 tiles get slots 0..REGION1_CAPACITY-1; region 2 tiles
    get slots starting at REGION2_VRAM_BASE/32.
    """
    high = word & ~NAMETABLE_TILE_MASK
    if canon_flip_bits & 1:
        high ^= NAMETABLE_H_BIT
    if canon_flip_bits & 2:
        high ^= NAMETABLE_V_BIT
    return high | (vram_tile_slot & NAMETABLE_TILE_MASK)
```

- [ ] **Step 2: Update existing tests to use the new parameter name**

In `tools/test_tile_dedupe.py`, the `TestRemapNametableWord` class uses keyword argument `canonical_index=...`. Change all calls to `vram_tile_slot=...`.

Search and replace within the file (only the `canonical_index=` occurrences in test calls — leave any unrelated identifiers alone):

```bash
grep -n 'canonical_index=' tools/test_tile_dedupe.py
```

Expected: three lines in `TestRemapNametableWord`. Edit each so `canonical_index=` becomes `vram_tile_slot=`.

Also update `TestRoundTrip.test_dedupe_remap_round_trip`'s call to `remap_nametable_word`. The call is:
```python
remap_nametable_word(
    w,
    mapping[w & NAMETABLE_TILE_MASK][0],
    mapping[w & NAMETABLE_TILE_MASK][1],
)
```
This is positional, no rename needed. But the round-trip's reconstruct logic now has a subtle issue: after pack_regions, tile slots aren't [0, 1, 2, ...] always. The round-trip test must continue to use canonical_index directly (not pack_regions'd slots), so the existing test stays valid as-is — it doesn't exercise multi-region packing.

- [ ] **Step 3: Run tests**

Run:
```bash
python3 tools/test_tile_dedupe.py 2>&1 | tail -3
```
Expected: all 16 tests still pass.

- [ ] **Step 4: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "refactor(tools): remap_nametable_word — vram_tile_slot param

Same behavior; clearer name for the multi-region world. The tile-index
field is now 'whatever VRAM slot this tile lives in', which equals the
canonical index only in the single-region case."
```

---

## Task 5: Add `--force-region1-cap` flag to `ojz_strip_gen.py`

**Files:**
- Modify: `tools/ojz_strip_gen.py`

This is the synthetic stress flag that lets us exercise spill behavior on data that doesn't naturally exceed 1536 tiles.

- [ ] **Step 1: Add a CLI argument**

In `tools/ojz_strip_gen.py`, find the `main()` function. Currently it parses `sys.argv[1] in ("test", "generate")`. Extend to also accept an optional `--force-region1-cap=N` flag for the `generate` command.

Replace the existing `main()`:

```python
def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("test", "generate"):
        print(f"Usage: {sys.argv[0]} test|generate [--force-region1-cap=N]")
        sys.exit(1)

    if sys.argv[1] == "test":
        run_tests()
        return

    # generate
    force_cap = None
    for arg in sys.argv[2:]:
        if arg.startswith("--force-region1-cap="):
            try:
                force_cap = int(arg.split("=", 1)[1])
            except ValueError:
                print(f"Invalid --force-region1-cap value: {arg}")
                sys.exit(1)
        else:
            print(f"Unknown arg: {arg}")
            sys.exit(1)
    generate(force_region1_cap=force_cap)
```

- [ ] **Step 2: Update `generate()` signature**

Change `def generate():` to `def generate(force_region1_cap=None):`. The body still reads as before; the cap will be threaded into Task 6's region-packing logic.

- [ ] **Step 3: Verify the flag parses**

Run:
```bash
python3 tools/ojz_strip_gen.py generate --force-region1-cap=5 2>&1 | grep -E 'force|Phase A.1' | head
```

Expected: no error; the existing A.1 measurement still prints (Task 6 wires the cap into actual behavior).

- [ ] **Step 4: Commit**

```bash
git add tools/ojz_strip_gen.py
git commit -m "feat(tools): ojz_strip_gen — --force-region1-cap stress flag (no-op)"
```

---

## Task 6: Wire multi-region packing into `generate()` flow

**Files:**
- Modify: `tools/ojz_strip_gen.py`

Hook `pack_regions` into the existing 3-pass flow and emit two output blobs (`ojz_tiles_r1.bin`, `ojz_tiles_r2.bin`).

- [ ] **Step 1: Add region-capacity constants near the top of `tools/ojz_strip_gen.py`**

After the existing `OJZ_TILES_COUNT = 322` line, insert:

```python
# Multi-region VRAM packing (§2 A.2) — must match constants.asm
# REGION2_VRAM_BASE / 32 == REGION2 starting tile slot
REGION1_TILE_CAPACITY = 1536          # primary art pool $0000-$BFFF
REGION2_VRAM_BASE     = 0xF800        # Plane B off-screen, row 48+ (per A.2 research)
REGION2_TILE_CAPACITY = 64            # ($10000 - $F800) / 32 = 64 tiles
```

(If A.2 research picked Option A or C instead of Option B, the implementer should adjust these to match what `docs/research/multi-region-packing.md` says.)

- [ ] **Step 2: Modify the `generate()` body to use `pack_regions`**

In the existing Pass 2 / Pass 3 of `generate()` (the section that does dedupe + remap + emit), find this block:

```python
    # ---- Pass 2: dedupe across all sections, emit deduped tile pool ----
    full_blob = decompress_full_ojz_art(OJZ_ART_PATH)
    sorted_indices, raw_tiles = collect_referenced_tiles(per_section_strips, full_blob)
    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)

    # Build src_idx → (canonical_idx, flip_bits) lookup
    src_to_canon: dict[int, tuple[int, int]] = {
        src_idx: mapping[i]
        for i, src_idx in enumerate(sorted_indices)
    }
```

Replace it with:

```python
    # ---- Pass 2: dedupe across all sections, pack into regions, emit pools ----
    full_blob = decompress_full_ojz_art(OJZ_ART_PATH)
    sorted_indices, raw_tiles = collect_referenced_tiles(per_section_strips, full_blob)
    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)

    # Apply --force-region1-cap stress flag (caps region 1 to force region 2 spill)
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

- [ ] **Step 3: Update Pass 3 to use `src_to_slot` instead of `src_to_canon`**

Find the Pass 3 block:

```python
    # ---- Pass 3: rewrite each section's strips and emit binaries ----
    total_strips = 0
    first_strips = None
    for sec_id, strips in per_section_strips.items():
        remapped_strips = []
        for col in strips:
            remapped_col = []
            for word in col:
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                canon_idx, flip_bits = src_to_canon.get(src_idx, (0, 0))
                remapped_col.append(
                    tile_dedupe.remap_nametable_word(word, canon_idx, flip_bits)
                )
            remapped_strips.append(remapped_col)
```

Replace `src_to_canon.get(src_idx, (0, 0))` with `src_to_slot.get(src_idx, (0, 0))` and the variable name `canon_idx` with `vram_slot`:

```python
    # ---- Pass 3: rewrite each section's strips and emit binaries ----
    total_strips = 0
    first_strips = None
    for sec_id, strips in per_section_strips.items():
        remapped_strips = []
        for col in strips:
            remapped_col = []
            for word in col:
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                vram_slot, flip_bits = src_to_slot.get(src_idx, (0, 0))
                remapped_col.append(
                    tile_dedupe.remap_nametable_word(word, vram_slot, flip_bits)
                )
            remapped_strips.append(remapped_col)
```

- [ ] **Step 4: Replace single-pool emission with per-region emission**

Find the emission block (after Pass 3, before the measurement print):

```python
    # ---- Emit deduped tile pool ----
    tile_out = os.path.join(out_dir, "ojz_tiles.bin")
    with open(tile_out, "wb") as f:
        for tile in unique:
            f.write(tile)
```

Replace with:

```python
    # ---- Emit deduped tile pools (one per region) ----
    r1_out = os.path.join(out_dir, "ojz_tiles_r1.bin")
    with open(r1_out, "wb") as f:
        for tile in r1_tiles:
            f.write(tile)

    r2_out = os.path.join(out_dir, "ojz_tiles_r2.bin")
    with open(r2_out, "wb") as f:
        for tile in r2_tiles:
            f.write(tile)
```

- [ ] **Step 5: Update the measurement print to show region split**

Find the existing measurement block:

```python
    raw_referenced = len(sorted_indices)
    deduped = len(unique)
    pct = (1.0 - deduped / raw_referenced) * 100 if raw_referenced else 0.0
    fits = deduped <= 1536
    src_max = max(sorted_indices) if sorted_indices else 0
    src_min = min(sorted_indices) if sorted_indices else 0
    src_collisions = sum(1 for i in sorted_indices if i >= 1536)
    post_max = deduped - 1
    print(
        f"\n=== OJZ Act 1 — Phase A.1 measurement ===\n"
        f"  Source tile indices referenced: {raw_referenced} "
        f"(min={src_min}, max={src_max})\n"
        f"  Source indices ≥1536 (nametable collision risk): {src_collisions}\n"
        f"  Deduped (with flip canonicalization): {deduped} "
        f"({pct:.1f}% reduction)\n"
        f"  Highest remapped tile index: {post_max}\n"
        f"  Pool fits in 1536: {'yes' if fits else 'NO — A.2 multi-region needed'}\n"
        f"  Deduped blob: {deduped * 32} bytes uncompressed → {tile_out}\n"
    )
    if not fits:
        print(
            "ERROR: post-dedupe pool exceeds 1536 tiles; "
            "A.2 multi-region packing required (out of scope for A.1)."
        )
        sys.exit(1)
```

Replace with:

```python
    raw_referenced = len(sorted_indices)
    deduped = len(unique)
    pct = (1.0 - deduped / raw_referenced) * 100 if raw_referenced else 0.0
    src_max = max(sorted_indices) if sorted_indices else 0
    src_min = min(sorted_indices) if sorted_indices else 0
    src_collisions = sum(1 for i in sorted_indices if i >= 1536)
    r1_count = len(r1_tiles)
    r2_count = len(r2_tiles)
    r1_max_slot = max((slots[i] for i in range(len(unique)) if slots[i] < region2_start_slot), default=-1)
    r2_max_slot = max((slots[i] for i in range(len(unique)) if slots[i] >= region2_start_slot), default=-1)
    cap_label = (
        f" (region1 force-capped at {region1_cap})"
        if force_region1_cap is not None else ""
    )
    print(
        f"\n=== OJZ Act 1 — Phase A.2 measurement{cap_label} ===\n"
        f"  Source tile indices referenced: {raw_referenced} "
        f"(min={src_min}, max={src_max})\n"
        f"  Source indices ≥1536 (nametable collision risk): {src_collisions}\n"
        f"  Deduped (with flip canonicalization): {deduped} "
        f"({pct:.1f}% reduction)\n"
        f"  Region 1: {r1_count} tiles (max slot {r1_max_slot}) → {r1_out}\n"
        f"  Region 2: {r2_count} tiles (max slot {r2_max_slot}) → {r2_out}\n"
        f"  R1 cap: {region1_cap}; R2 cap: {REGION2_TILE_CAPACITY}; "
        f"total cap: {region1_cap + REGION2_TILE_CAPACITY}\n"
    )
```

(Remove the `sys.exit(1)` overflow guard — `pack_regions` raises `OverflowError` on real overflow now, which propagates up cleanly.)

- [ ] **Step 6: Update `test_full_pipeline_runs` to look for the new outputs**

Find `test_full_pipeline_runs` in `ojz_strip_gen.py`. Change:

```python
            tile_path = os.path.join(td, "ojz_tiles.bin")
            assert os.path.exists(tile_path), "deduped pool not written"
            size = os.path.getsize(tile_path)
            assert size > 0, "deduped pool is empty"
            assert size % 32 == 0, f"pool size {size} not a multiple of 32"
            assert size // 32 <= 1536, f"pool {size//32} exceeds 1536 tiles"
```

to:

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

- [ ] **Step 7: Run self-tests**

Run:
```bash
python3 tools/ojz_strip_gen.py test 2>&1 | tail -5
```
Expected: all tests pass including `test_full_pipeline_runs`.

- [ ] **Step 8: Run the generator (no spill, default OJZ data)**

Run:
```bash
python3 tools/ojz_strip_gen.py generate 2>&1 | grep -E 'A.2 measurement|Region|R1 cap'
```
Expected output (region 2 should be empty for default OJZ):
```
=== OJZ Act 1 — Phase A.2 measurement ===
  ...
  Region 1: 10 tiles (max slot 9) → .../ojz_tiles_r1.bin
  Region 2: 0 tiles (max slot -1) → .../ojz_tiles_r2.bin
  R1 cap: 1536; R2 cap: 64; total cap: 1600
```

- [ ] **Step 9: Run the generator with stress flag (forces spill)**

Run:
```bash
python3 tools/ojz_strip_gen.py generate --force-region1-cap=5 2>&1 | grep -E 'A.2 measurement|Region|R1 cap'
```
Expected (region 1 capped at 5, so 5 tiles overflow into region 2):
```
=== OJZ Act 1 — Phase A.2 measurement (region1 force-capped at 5) ===
  ...
  Region 1: 5 tiles (max slot 4) → .../ojz_tiles_r1.bin
  Region 2: 5 tiles (max slot 1988) → .../ojz_tiles_r2.bin
  R1 cap: 5; R2 cap: 64; total cap: 69
```

- [ ] **Step 10: Reset to default (no spill) for the rest of the plan**

Run:
```bash
python3 tools/ojz_strip_gen.py generate > /dev/null
```

Verify:
```bash
ls -la data/generated/ojz/act1/ojz_tiles_r1.bin data/generated/ojz/act1/ojz_tiles_r2.bin
```
Expected: r1.bin = 320 bytes, r2.bin = 0 bytes.

- [ ] **Step 11: Commit**

```bash
git add tools/ojz_strip_gen.py
git commit -m "feat(tools): wire pack_regions into generate, emit per-region pools"
```

---

## Task 7: S4LZ-compress both region blobs in `build.sh`

**Files:**
- Modify: `build.sh`

- [ ] **Step 1: Replace the single-blob compression line with per-region**

Find in `build.sh`:

```bash
echo "Compressing OJZ tile pool with S4LZ..."
python3 "${TOOLS}/s4lz.py" compress --tile-delta \
    data/generated/ojz/act1/ojz_tiles.bin \
    data/generated/ojz/act1/ojz_tiles.s4lz
```

Replace with:

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
    # No spill — produce a 4-byte zero-length S4LZ stream so the BINCLUDE always exists.
    # Header: uncompressed size = 0 (BE word), flags = 0, reserved = 0
    printf '\x00\x00\x00\x00' > data/generated/ojz/act1/ojz_tiles_r2.s4lz
fi
```

- [ ] **Step 2: Confirm `S4LZ_Decompress` handles a zero-size header gracefully**

Read `engine/s4lz_decompress.asm` quickly:
- The routine reads `move.w (a0)+, d3` for uncompressed size, then enters `.token_loop` which reads a token byte and `beq` on $00 = end. With size = 0 + the next byte = 0 (terminator), the loop exits immediately without copying anything. Safe.

- [ ] **Step 3: Run the build to verify both compression steps**

Run:
```bash
./build.sh -nl 2>&1 | grep -E 'Compressing|Compressed' | head
```
Expected: two `Compressing ...` lines (or one + the placeholder branch). With default OJZ (no spill), region 2 takes the `printf` branch.

- [ ] **Step 4: Confirm both .s4lz files exist**

Run:
```bash
ls -la data/generated/ojz/act1/ojz_tiles_r1.s4lz data/generated/ojz/act1/ojz_tiles_r2.s4lz
```
Expected: r1.s4lz exists with non-zero size, r2.s4lz exists at 4 bytes (or more if spill).

- [ ] **Step 5: Commit**

```bash
git add build.sh
git commit -m "build: compress both A.2 region pools (placeholder when r2 empty)"
```

---

## Task 8: Add engine constants for the regions

**Files:**
- Modify: `constants.asm`

The build tool already has these constants (Task 6). The engine needs matching values.

- [ ] **Step 1: Add region constants near the existing nametable strips block**

Open `constants.asm`. Find:
```asm
; Nametable strips
STRIP_TILE_HEIGHT       = 48        ; rows per strip (0–47; row 48+ = sprite table)
STRIP_BYTE_SIZE         = STRIP_TILE_HEIGHT*2   ; 96 bytes per strip
```

Insert immediately after that block:

```asm
; Multi-region VRAM tile packing (§2 A.2)
; Region 1: primary art pool $0000-$BFFF (1536 tiles).
; Region 2: Plane B off-screen rows, $F800-$FFFF (64 tiles).
;   Safe because OJZ act_descriptor's cam_max_y=128 caps the visible
;   bottom row at nametable row 44; rows 45+ of Plane B never render.
;   Row 48 chosen for a 3-row safety margin against future cam_max_y bumps.
; Build-tool side: tools/ojz_strip_gen.py REGION* constants must match.
REGION1_TILE_CAPACITY   = 1536
REGION2_VRAM_BASE       = $F800
REGION2_TILE_CAPACITY   = 64        ; ($10000 - $F800) / 32
```

(If A.2 research picked a different boundary, adjust to match. Keep build-tool and asm-side constants synchronized.)

- [ ] **Step 2: Build to confirm**

Run:
```bash
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add constants.asm
git commit -m "feat(§2): engine constants for A.2 region 1 + region 2 layout"
```

---

## Task 9: Extend `Act_Desc` with region-2 pointer

**Files:**
- Modify: `structs.asm`
- Modify: `data/levels/ojz/act1/act_descriptor.asm`

- [ ] **Step 1: Update the struct**

In `structs.asm`, find the existing Act struct:

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
tile_art_s4lz       ds.l 1          ; $16 — pointer to S4LZ-compressed FG tile pool (§2 A.1)
tile_art_vram       ds.w 1          ; $1A — VRAM byte destination (tile-slot * 32)
Act endstruct

    if Act_len <> $1C
      error "Act struct is \{Act_len} bytes, expected $1C"
    endif
```

Add a `tile_art_r2_s4lz` longword after `tile_art_vram` (and align). Replace the struct + assertion:

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

- [ ] **Step 2: Update the OJZ Act 1 descriptor to include the new field**

In `data/levels/ojz/act1/act_descriptor.asm`, find:

```asm
    dc.l    OJZ_Tiles_S4LZ          ; tile_art_s4lz (deduped pool, S4LZ-compressed)
    dc.w    $0000                   ; tile_art_vram (VRAM byte $0000 = tile slot 0)
    align 2
```

Replace with:

```asm
    dc.l    OJZ_Tiles_R1_S4LZ       ; tile_art_s4lz (region 1)
    dc.w    $0000                   ; tile_art_vram (VRAM byte $0000)
    dc.l    OJZ_Tiles_R2_S4LZ       ; tile_art_r2_s4lz (region 2; 4-byte placeholder if no spill)
    dc.w    0                       ; pad
    align 2
```

- [ ] **Step 3: Update the BINCLUDE labels**

In the same file, find the existing BINCLUDE line:

```asm
OJZ_Tiles_S4LZ: BINCLUDE "data/generated/ojz/act1/ojz_tiles.s4lz"
```

Replace with:

```asm
OJZ_Tiles_R1_S4LZ: BINCLUDE "data/generated/ojz/act1/ojz_tiles_r1.s4lz"
OJZ_Tiles_R2_S4LZ: BINCLUDE "data/generated/ojz/act1/ojz_tiles_r2.s4lz"
```

- [ ] **Step 4: Build to verify struct + descriptor align**

Run:
```bash
./build.sh -nl 2>&1 | tail -5
```
Expected: clean build (Level_LoadArt still single-region; Task 10 wires the second call).

- [ ] **Step 5: Commit**

```bash
git add structs.asm data/levels/ojz/act1/act_descriptor.asm
git commit -m "feat(§2): Act_Desc gains tile_art_r2_s4lz; OJZ act1 wires both regions"
```

---

## Task 10: Extend `Level_LoadArt` to handle region 2

**Files:**
- Modify: `engine/level/load_art.asm`

The existing `Level_LoadArt` calls `LoadArt_S4LZ` once for region 1. Add a conditional second call for region 2.

- [ ] **Step 1: Replace `Level_LoadArt`**

Open `engine/level/load_art.asm`. Replace the existing `Level_LoadArt` block:

```asm
; -----------------------------------------------
; Level_LoadArt — load all FG tile art for the act referenced by a0.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d3, a0–a4
;
; A.1 single-region behaviour: act descriptor has ONE compressed tile-art
; pointer (Act_tile_art_s4lz) and ONE VRAM destination (Act_tile_art_vram).
; A.2 will extend this routine to walk a region table.
; -----------------------------------------------
Level_LoadArt:
        moveq   #0, d0
        move.w  Act_tile_art_vram(a0), d0           ; d0.w = VRAM byte dest
        movea.l Act_tile_art_s4lz(a0), a0           ; a0 = compressed S4LZ source
        bra.w   LoadArt_S4LZ                        ; tail call
```

with the multi-region version:

```asm
; -----------------------------------------------
; Level_LoadArt — load all FG tile art for the act referenced by a0.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d3, a0–a4
;
; A.2 behaviour: region 1 always loads (Act_tile_art_s4lz / Act_tile_art_vram).
; Region 2 loads only when Act_tile_art_r2_s4lz is non-null AND the S4LZ
; stream's uncompressed size is non-zero. Region 2's VRAM destination is the
; engine constant REGION2_VRAM_BASE.
; -----------------------------------------------
Level_LoadArt:
        movem.l a0/d4, -(sp)                        ; preserve descriptor + scratch
        movea.l a0, a4                              ; a4 = act ptr (saved across LoadArt)

        ; -- region 1 (always) --
        moveq   #0, d0
        move.w  Act_tile_art_vram(a4), d0           ; d0.w = VRAM byte dest
        movea.l Act_tile_art_s4lz(a4), a0           ; a0 = compressed S4LZ source
        bsr.w   LoadArt_S4LZ

        ; -- region 2 (skip if pointer null) --
        movea.l Act_tile_art_r2_s4lz(a4), a0
        cmpa.w  #0, a0
        beq.s   .done

        ; -- skip if uncompressed size header is zero (placeholder no-spill blob) --
        move.w  (a0), d4
        beq.s   .done

        move.w  #REGION2_VRAM_BASE, d0              ; d0.w = region 2 VRAM byte dest
        bsr.w   LoadArt_S4LZ

.done:
        movem.l (sp)+, a0/d4
        rts
```

- [ ] **Step 2: Build to verify the new routine**

Run:
```bash
./build.sh 2>&1 | tail -5
```
Expected: clean build with no new lint warnings beyond the pre-existing baseline. ROM size should be ~639 KB (close to A.1's; +6 bytes for the new Act_Desc field, plus a few bytes for the new code).

- [ ] **Step 3: Commit**

```bash
git add engine/level/load_art.asm
git commit -m "feat(§2): Level_LoadArt loads region 2 when present"
```

---

## Task 11: Verify default-OJZ build in Exodus (no spill expected)

**Files:** none (Exodus interaction)

- [ ] **Step 1: Tell the user to load the new s4.bin in Exodus**

Tell the user: "Please reload `s4.bin` in Exodus. The OJZ scroll test should boot the same way as A.1 (sky + cloud band visible, no garbage). Region 2 is empty for default OJZ, so the second LoadArt_S4LZ call is the placeholder/no-op path."

- [ ] **Step 2: Sanity-check Exodus state**

Use `mcp__exodus__emulator_status` to verify the emulator is running. PC should be at `VSync_Wait` (the per-frame idle). Frame token > 0.

- [ ] **Step 3: Verify Decomp_Buffer holds the deduped region 1 pool**

Use `mcp__exodus__emulator_read_memory` with `symbol=Decomp_Buffer` and `len=320`. Expect 10 tiles of pixel data (matches A.1's content: tile 0 all zeros, tiles 1+ with pixel data).

- [ ] **Step 4: Visually verify rendering**

Use `mcp__exodus__emulator_screenshot`. The scene should look identical to A.1's verified screenshot — clean black sky tiles + cloud-band patterns mid-screen. No garbage; no nametable corruption.

- [ ] **Step 5: Document the verification result**

No commit at this step — this is empirical confirmation that the default A.2 build is regression-free.

---

## Task 12: Verify forced-spill build in Exodus (region 2 exercised)

**Files:** none (build flag + Exodus interaction)

This task validates the spill code path on data that wouldn't naturally exceed 1536.

- [ ] **Step 1: Build with --force-region1-cap=5**

Run:
```bash
python3 tools/ojz_strip_gen.py generate --force-region1-cap=5
python3 tools/s4lz.py compress --tile-delta \
    data/generated/ojz/act1/ojz_tiles_r1.bin \
    data/generated/ojz/act1/ojz_tiles_r1.s4lz
python3 tools/s4lz.py compress --tile-delta \
    data/generated/ojz/act1/ojz_tiles_r2.bin \
    data/generated/ojz/act1/ojz_tiles_r2.s4lz
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build. ROM is now built against a "tile pool spilled into region 2" data set.

- [ ] **Step 2: Reload in Exodus**

Tell the user: "Please reload `s4.bin` (built with `--force-region1-cap=5` to force region 2 spill)."

- [ ] **Step 3: Verify VRAM contents**

`mcp__exodus__emulator_read_memory(symbol=Decomp_Buffer, len=160)` should show the FIRST 5 tiles of decompressed data (160 bytes). The remaining tiles got DMA'd to region 2's VRAM destination.

VRAM at $F800 is not directly readable via `read_memory` (which only routes 68k addresses). To verify region 2, use `mcp__exodus__emulator_screenshot` and confirm rendering is still correct (no garbage, same visible scene as default).

- [ ] **Step 4: Visually verify rendering — should look identical to default**

The point of A.2 is that spilling tiles into region 2 produces the same visible output as having all tiles in region 1, just using a different VRAM region. If rendering looks the same, the multi-region mapping is correct end-to-end.

`mcp__exodus__emulator_screenshot` — confirm visible scene matches the default-OJZ baseline (clean black sky + cloud-band marks).

- [ ] **Step 5: Reset to default build for the rest of the plan**

```bash
python3 tools/ojz_strip_gen.py generate
./build.sh
```

Verify by checking `data/generated/ojz/act1/ojz_tiles_r2.bin` is 0 bytes again.

- [ ] **Step 6: No commit — verification only**

---

## Task 13: Update measurements log with A.2 numbers

**Files:**
- Modify: `docs/research/tile-pipeline-measurements.md`

- [ ] **Step 1: Capture both default and stress numbers**

Run:
```bash
python3 tools/ojz_strip_gen.py generate 2>&1 | grep -A 8 'A.2 measurement'
echo '---'
python3 tools/ojz_strip_gen.py generate --force-region1-cap=5 2>&1 | grep -A 8 'A.2 measurement'
```
Note the values from each output.

- [ ] **Step 2: Reset to default**

```bash
python3 tools/ojz_strip_gen.py generate > /dev/null
```

- [ ] **Step 3: Edit the measurements doc**

Open `docs/research/tile-pipeline-measurements.md` and find the A.2 row in the table:

```
| A.2 | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd |
```

Replace with two rows — one for default, one for forced-spill stress:

```
| **A.2** (default OJZ) | 48 | 14 | 1856 | 2 | 10 (28.6%) | 9 | yes (region 1) | 320 | 262 (0.819) | $0000-$013F (region 1 only; region 2 empty) |
| A.2 (--force-region1-cap=5) | 48 | 14 | 1856 | 2 | 10 (28.6%) | 1988 | yes (split: r1=5, r2=5) | r1=160; r2=160 | tbd | $0000-$009F (r1) + $F800-$F89F (r2) |
```

(Adjust numbers if research picked a different region-2 boundary or actual run produced different values.)

Also update the "Headline" section to add a sentence about A.2 confirming the spill path works on synthetic stress.

- [ ] **Step 4: Commit**

```bash
git add docs/research/tile-pipeline-measurements.md
git commit -m "docs(research): A.2 measurements — default + forced-spill stress"
```

---

## Task 14: Update DEFERRED_WORK.md

**Files:**
- Modify: `docs/DEFERRED_WORK.md`

A.2 doesn't directly close any specific deferred item (the OJZ visibility one was closed by A.1), but it does unblock A.3's graph-coloring assumption (tiles can land in two regions). Add a brief A.2 entry to the Done section.

- [ ] **Step 1: Add A.2 to the Done section**

Open `docs/DEFERRED_WORK.md`. Find the existing A.1 entry in the Done section:

```
### §2 Phase 2 Layer A.1 — Tile Dedupe + Nametable Remap — 2026-04-26
```

Insert a new entry immediately above it (Done section is ordered most-recent-first):

```markdown
### §2 Phase 2 Layer A.2 — Multi-region VRAM Packing — <today's date>
**Completed in:** §2 Phase 2 Layer A.2
**What:** `tile_dedupe.pack_regions` partitions canonical tiles across multiple VRAM regions; `tools/ojz_strip_gen.py` emits per-region pools (`ojz_tiles_r1.bin` / `ojz_tiles_r2.bin`) and supports `--force-region1-cap` for stress testing the spill path. Engine: `Level_LoadArt` calls `LoadArt_S4LZ` once per non-empty region. `Act_Desc` grew with `tile_art_r2_s4lz` longword; new constants `REGION1_TILE_CAPACITY=1536`, `REGION2_VRAM_BASE=$F800`, `REGION2_TILE_CAPACITY=64` define the layout. Region 2 lives in Plane B's off-screen rows ($F800-$FFFF, 16 rows × 128 bytes), safe because OJZ's `cam_max_y=128px` keeps the visible bottom at nametable row 44.
**Default-OJZ measurement:** 10 tiles fit in region 1; region 2 empty. Verified visually no regression vs A.1.
**Forced-spill (--force-region1-cap=5):** 5 tiles in region 1 + 5 in region 2 (slots 1984-1988), rendering matches default. Confirms spill path works.
**See:** `docs/research/multi-region-packing.md`, `docs/research/tile-pipeline-measurements.md`.
```

(Replace `<today's date>` with the actual date when this task runs.)

- [ ] **Step 2: Commit**

```bash
git add docs/DEFERRED_WORK.md
git commit -m "docs: §2 A.2 — multi-region VRAM packing complete"
```

---

## Task 15: s4budget + final lint check

**Files:** Read-only

- [ ] **Step 1: Run the budget tool**

```bash
python3 tools/s4budget.py s4.lst s4.bin --summary
```
Expected: ROM ~639 KB / 4 MB; RAM ~41 KB / 64 KB. A.2 should add at most a few hundred bytes to ROM (slightly bigger Level_LoadArt + Act_Desc + the placeholder r2.s4lz BINCLUDE).

- [ ] **Step 2: Run full lint**

```bash
./build.sh
```
Expected: clean build; warning count should match A.1's baseline (no new warnings introduced).

- [ ] **Step 3: No commit — verification only**

---

## Task 16: Merge to master

**Files:** none (git only)

- [ ] **Step 1: Verify clean working tree**

```bash
git status
git log --oneline master..HEAD
```
Expected: no uncommitted changes; commit list shows the work from Tasks 0-14.

- [ ] **Step 2: Merge to master with --no-ff**

```bash
git checkout master
git merge --no-ff feat/s2-a2-multi-region -m "$(cat <<'EOF'
Merge §2 Phase 2 Layer A.2: multi-region VRAM packing

Splits the deduped tile pool across two VRAM regions when region 1
($0000-$BFFF, 1536 tiles) overflows. Region 2 lives in Plane B's
off-screen rows ($F800-$FFFF, 64 tiles) — safe because the OJZ act
descriptor caps cam_max_y at 128 px (visible bottom at nametable row
44; rows 45+ never render).

Build tool: tools/tile_dedupe.pack_regions partitions canonical tiles
across regions; tools/ojz_strip_gen.py emits ojz_tiles_r1.bin /
ojz_tiles_r2.bin and supports --force-region1-cap=N for stress
testing. Engine: Level_LoadArt calls LoadArt_S4LZ once per non-empty
region. Act_Desc grew with tile_art_r2_s4lz longword.

Default OJZ: 10 tiles fit in region 1; region 2 empty (no regression).
Forced spill (--force-region1-cap=5): 5 tiles in region 1, 5 in
region 2; rendering matches default — multi-region mapping verified
end-to-end.

A.3 (graph coloring) is the next layer.
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
git branch -d feat/s2-a2-multi-region
git status
git log --oneline -3
```

---

## Self-review checklist (run before claiming done)

- [ ] All 16 unit tests in `tools/test_tile_dedupe.py` pass (12 from A.1 + 4 new for `pack_regions`)
- [ ] `python3 tools/ojz_strip_gen.py test` passes including the updated `test_full_pipeline_runs`
- [ ] Default `python3 tools/ojz_strip_gen.py generate` produces empty `ojz_tiles_r2.bin` (no spill on OJZ act 1)
- [ ] Stress `python3 tools/ojz_strip_gen.py generate --force-region1-cap=5` produces 5-tile r1 + 5-tile r2
- [ ] `./build.sh` produces `s4.bin` with no errors and no new lint warnings beyond A.1's baseline
- [ ] In Exodus (default build): scroll test renders identical to A.1; no regression
- [ ] In Exodus (forced-spill build): scroll test renders identical to default; region 2 mapping is correct end-to-end
- [ ] `docs/DEFERRED_WORK.md` has the A.2 entry in the Done section with today's date
- [ ] `docs/research/tile-pipeline-measurements.md` has both A.2 rows populated (default + forced-spill)
- [ ] Build-tool and asm-side region constants stay in sync (`REGION1_TILE_CAPACITY`, `REGION2_VRAM_BASE`, `REGION2_TILE_CAPACITY` in both `tools/ojz_strip_gen.py` and `constants.asm`)
