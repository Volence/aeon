# Act Art Streaming — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-parity-group union art emission with ONE globally-deduplicated, spatially-ordered, **paged act art pool**; remap section nametables to global pool indices; load all pages once at init. This unblocks the build (currently fails: `sec0_tiles.bin` 19296 B > buffer) and makes the level scrollable with **zero tile duplication**, on the foundation Phase 2 streams from.

**Architecture:** The act's unique tiles are deduped globally and stored once, ordered by spatial locality, split into independently-decodable ≤256-tile **pages** (a single ZX0 stream can't be random-accessed; pages can). Because the pool (≤1472 tiles) fits the 11-bit nametable tile-index field, a **pool index == its VRAM slot** for a fits-VRAM level — so strips reference global indices directly and pages load to fixed slots with no runtime indirection. Phase 2 later adds the dynamic page table + eviction over this same pool+pages+manifest (additive, not a rewrite). The old DSATUR-coloring/union path, `Decomp_Buffer` aliases, orphaned constants, and the two temp scaffolds are deleted — nothing layered on top.

**Tech Stack:** Python 3 build tools (`pytest`), AS Macro Assembler (68000), `salvador` (ZX0), `build.sh`, oracle emulator (MCP) for runtime verification.

**Out of Phase 1 scope (Phase 2/3, do NOT build here):** refcount/LRU eviction, on-demand page streaming, prefetch, per-section BG into the unified pool, the >2048-tile reference-widening question (Phase 1 pool ≤1472 fits 11 bits).

---

## File structure

**Build tools (Python — TDD with pytest):**
- `tools/tile_dedupe.py` — keep `dedupe_tiles`/`canonical_form`/`remap_nametable_word`; **delete** `color_sections` (170-202), `assign_section_slots` (205-251), `compute_adjacency` (150-167); **add** `order_pool_spatially()` + `split_pool_into_pages()`.
- `tools/ojz_strip_gen.py` — replace generate() Pass 4 (1268-1277), Pass 5 (1279-1317), Pass 6 (1319-1328), Pass 7 (1366-1373) with global-pool emission; update `REGION1_TILE_CAPACITY` (116) and the test assert (909).
- `tools/test_tile_dedupe.py` — remove the broken `TestAssignSectionSlots`/`TestColorSections`/`TestComputeAdjacency` (188-301); add `TestOrderPoolSpatially` + `TestSplitPoolIntoPages`.

**Build pipeline:**
- `build.sh` — replace per-section ZX0 loop (79-117) + `sec_tile_blobs.asm` dedup (119-143) with per-page pool compression + manifest include; remove scaffold guard (88-93).

**Engine (ASM — build + emulator verified):**
- `constants.asm` — remove `DECOMP_BUFFER_SIZE` (127); add `ART_STAGING_BUFFER_SIZE`, `ART_POOL_PAGE_TILES`; keep `REGION1_TILE_CAPACITY=1472` (365).
- `ram.asm` — remove `Decomp_Buffer`/`Decomp_Buffer_End` aliases (28-29); add purpose-named `Art_Staging_Buffer` (init-only, occupies the not-yet-populated tile-cache region, documented).
- `engine/level/load_art.asm` — replace `LoadArt_Compressed`/`Section_LoadArt`/`Level_LoadArt` union path with `Pool_LoadAll` (iterate manifest: decompress page → DMA to slot).
- `engine/level/section.asm` — delete empty preload/deferred stubs (368-390).
- `data/levels/ojz/act1/act_descriptor.asm` + `structs.asm` — Act struct gains `act_art_pool` (ptr) + `act_art_pool_pages` (count); Sec struct's `sec_tile_art`/`sec_tile_art_vram` (structs.asm 142-143) removed (sections no longer carry per-section art).
- Generated: `sec_tile_blobs.asm` + `sec_vram_bases.asm` deleted; new `ojz_act_pool.asm` (page BINCLUDEs + manifest) emitted.

---

## Task 0: Branch setup + scaffold revert

**Files:** `build.sh`, `test/ojz_scroll_test.asm` (revert scaffolds); git.

> ⚠️ `tools/ojz_strip_gen.py` and `data/editor/ojz` are watched by an auto-commit daemon that commits to the CURRENT branch (~60 s). We edit `ojz_strip_gen.py` in this plan, so the working branch must be the intended feature branch BEFORE editing it. The working tree also has pre-existing unrelated uncommitted changes (collision-editor work) — do NOT sweep them into our commits; commit only the files each task names.

- [ ] **Step 1: Create the feature branch from master, carrying current work tree**

Run: `git rev-parse --abbrev-ref HEAD` (note current branch). Then:
`git checkout -b feat/act-art-streaming`
Expected: switched to new branch; working-tree changes preserved.
(If the user prefers branching from clean `master`, stop and confirm — the pre-existing uncommitted collision work complicates a clean base.)

- [ ] **Step 2: Revert the two measurement scaffolds**

Run: `git checkout -- build.sh test/ojz_scroll_test.asm`
Expected: `build.sh` `DECOMP_BUFFER_CAPACITY` back to 9600; scroll rate back to +6.
Verify: `grep -n 'DECOMP_BUFFER_CAPACITY=' build.sh` shows `9600`.

- [ ] **Step 3: Commit the design spec**

```bash
git add docs/superpowers/specs/2026-06-22-act-art-streaming-design.md docs/superpowers/plans/2026-06-22-act-art-streaming-phase1.md
git commit -m "docs(art): act art streaming design spec + Phase 1 plan"
```

---

## Task 1: Spatial pool ordering + page splitting (tile_dedupe.py)

**Files:**
- Modify: `tools/tile_dedupe.py` (add functions; delete 150-167, 170-202, 205-251)
- Test: `tools/test_tile_dedupe.py` (remove 188-301 color/slot tests; add new)

- [ ] **Step 1: Write the failing test for spatial ordering**

Add to `tools/test_tile_dedupe.py`:
```python
class TestOrderPoolSpatially:
    def test_preserves_first_seen_order(self):
        # per_section_canon_tiles: each section's canonical IDs in traversal order
        per_section = [[0, 1, 2], [2, 3], [1, 4]]
        order = order_pool_spatially(per_section)
        # global pool = first-occurrence order across sections, deduped
        assert order == [0, 1, 2, 3, 4]

    def test_is_a_permutation_of_all_unique(self):
        per_section = [[5, 5, 1], [1, 9, 0]]
        order = order_pool_spatially(per_section)
        assert sorted(order) == [0, 1, 5, 9]
```

- [ ] **Step 2: Run it; verify it fails**

Run: `python3 -m pytest tools/test_tile_dedupe.py::TestOrderPoolSpatially -v`
Expected: FAIL — `NameError: name 'order_pool_spatially' is not defined`.

- [ ] **Step 3: Implement `order_pool_spatially`**

Add to `tools/tile_dedupe.py`:
```python
def order_pool_spatially(per_section_canon_tiles):
    """Global pool order = first-occurrence across sections (traversal order),
    deduped. Sections are visited in flat grid order, tiles in nametable order,
    so spatially-near tiles get near pool indices."""
    order = []
    seen = set()
    for section_tiles in per_section_canon_tiles:
        for cid in section_tiles:
            if cid not in seen:
                seen.add(cid)
                order.append(cid)
    return order
```

- [ ] **Step 4: Run it; verify it passes**

Run: `python3 -m pytest tools/test_tile_dedupe.py::TestOrderPoolSpatially -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Write the failing test for page splitting**

```python
class TestSplitPoolIntoPages:
    def test_splits_on_page_size(self):
        pool = list(range(600))             # 600 tiles
        pages = split_pool_into_pages(pool, page_tiles=256)
        assert [len(p) for p in pages] == [256, 256, 88]

    def test_single_page_when_small(self):
        pages = split_pool_into_pages([1, 2, 3], page_tiles=256)
        assert pages == [[1, 2, 3]]
```

- [ ] **Step 6: Run it; verify it fails**

Run: `python3 -m pytest tools/test_tile_dedupe.py::TestSplitPoolIntoPages -v`
Expected: FAIL — `name 'split_pool_into_pages' is not defined`.

- [ ] **Step 7: Implement `split_pool_into_pages`**

```python
def split_pool_into_pages(pool_order, page_tiles):
    """Split the ordered pool into contiguous pages of <= page_tiles each.
    Each page is independently decompressible and loads to slots
    [page_index*page_tiles .. +len)."""
    return [pool_order[i:i + page_tiles] for i in range(0, len(pool_order), page_tiles)]
```

- [ ] **Step 8: Run it; verify it passes**

Run: `python3 -m pytest tools/test_tile_dedupe.py::TestSplitPoolIntoPages -v`
Expected: PASS (2 tests).

- [ ] **Step 9: Delete the dead coloring/slot functions + their tests**

Delete from `tools/tile_dedupe.py`: `compute_adjacency` (150-167), `color_sections` (170-202), `assign_section_slots` (205-251) and their docstrings/comments.
Delete from `tools/test_tile_dedupe.py`: `TestPackRegions`, `TestComputeAdjacency`, `TestColorSections`, `TestAssignSectionSlots` (188-301).

- [ ] **Step 10: Run the full dedup test module; verify green**

Run: `python3 -m pytest tools/test_tile_dedupe.py -v`
Expected: PASS — only `dedupe`/`canonical`/`remap` + the two new classes; no import errors from deleted functions.

- [ ] **Step 11: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(art): global pool spatial ordering + page splitting; drop DSATUR coloring"
```

---

## Task 2: Global-pool emission in the generator (ojz_strip_gen.py)

**Files:**
- Modify: `tools/ojz_strip_gen.py` (Pass 4-7 → global pool; line 116; assert 909)
- Test: `tools/test_tile_dedupe.py` is unit-level; the generator has the smoke test at 891-917 — extend it.

- [ ] **Step 1: Update the capacity constant**

`tools/ojz_strip_gen.py:116`: change `REGION1_TILE_CAPACITY = 1536` → `REGION1_TILE_CAPACITY = 1472` (matches `constants.asm:365`; SAT at $B800). Add `ART_POOL_PAGE_TILES = 256` next to it.

- [ ] **Step 2: Replace Pass 4 (delete coloring) + build the global pool**

Replace `tools/ojz_strip_gen.py:1268-1277` (the `compute_adjacency`/`color_sections`/`assign_section_slots` block) with:
```python
    # Pass 4: global act art pool — spatially ordered, no per-section partition.
    from tile_dedupe import order_pool_spatially, split_pool_into_pages
    pool_order = order_pool_spatially(per_section_canon_tiles)   # canon IDs in pool order
    assert len(pool_order) <= REGION1_TILE_CAPACITY, (
        f"act art pool {len(pool_order)} tiles > VRAM capacity {REGION1_TILE_CAPACITY}")
    canon_to_pool = {cid: idx for idx, cid in enumerate(pool_order)}  # canon ID -> pool index (== VRAM slot)
    pages = split_pool_into_pages(pool_order, ART_POOL_PAGE_TILES)
```

- [ ] **Step 3: Repoint Pass 5 to global pool indices**

In `tools/ojz_strip_gen.py:1279-1317`, replace the per-section `section_slots[s_idx]` lookup with the global map. Where the old code did `vram_slot = slot_map.get(canon_idx, 0)`, use `vram_slot = canon_to_pool[canon_idx]`. (The nametable word remap via `remap_nametable_word(word, vram_slot, flip_bits)` is unchanged — `vram_slot` is now the global pool index, which equals the VRAM slot.)

- [ ] **Step 4: Replace Pass 6 — emit ONE pool, paged**

Replace `tools/ojz_strip_gen.py:1319-1328` (per-color union blob write) with one global pool, split into page files:
```python
    # Pass 6: emit the single act art pool as independently-decodable pages.
    for page_idx, page in enumerate(pages):
        with open(out_dir / f"act_pool_page{page_idx}.bin", "wb") as f:
            for canon_idx in page:
                f.write(unique[canon_idx])          # 32 raw bytes per tile
    pool_pages = len(pages)
```

- [ ] **Step 5: Replace Pass 7 — emit the manifest, not per-color bases**

Replace `tools/ojz_strip_gen.py:1366-1373` (sec_vram_bases.asm) with a pool manifest:
```python
    # Pass 7: act art pool manifest (page count + per-page tile count -> VRAM slot base).
    with open(out_dir / "ojz_act_pool_manifest.asm", "w") as f:
        f.write("; Auto-generated by tools/ojz_strip_gen.py — act art pool manifest\n")
        f.write(f"OJZ_ACT_POOL_PAGES = {len(pages)}\n")
        f.write(f"OJZ_ACT_POOL_TILES = {len(pool_order)}\n")
        for page_idx, page in enumerate(pages):
            base = page_idx * ART_POOL_PAGE_TILES
            f.write(f"OJZ_ACT_POOL_PAGE{page_idx}_SLOT = {base}\n")
            f.write(f"OJZ_ACT_POOL_PAGE{page_idx}_TILES = {len(page)}\n")
```

- [ ] **Step 6: Update the smoke-test assert (line 909)**

In `tools/ojz_strip_gen.py:909`, replace the per-section-blob assert with a per-page assert:
```python
        for page_file in sorted(out_dir.glob("act_pool_page*.bin")):
            assert page_file.stat().st_size <= ART_POOL_PAGE_TILES * 32, \
                f"{page_file} exceeds one page ({ART_POOL_PAGE_TILES} tiles)"
```

- [ ] **Step 7: Run the generator smoke test**

Run: `python3 -m pytest "tools/ojz_strip_gen.py::test_full_pipeline_runs" -v` (or the repo's generator-test invocation; if it's run via `python3 tools/ojz_strip_gen.py --selftest`, use that).
Expected: PASS — pages emitted, each ≤ 8192 B; pool ≤ 1472; no `color`/`union` references.

- [ ] **Step 8: Run the generator for real + verify output**

Run: `python3 tools/ojz_strip_gen.py` (or the args build.sh passes — inspect build.sh for the exact invocation).
Then: `ls -la data/generated/ojz/act1/act_pool_page*.bin data/generated/ojz/act1/ojz_act_pool_manifest.asm`
Expected: 3 pages for OJZ (256+256+~100 tiles → ~8192/8192/~3200 B); manifest lists `OJZ_ACT_POOL_PAGES = 3`, `OJZ_ACT_POOL_TILES ≈ 612`.
Verify dedup: `OJZ_ACT_POOL_TILES` ≈ 612 (the true distinct count), NOT 884 — zero duplication.

- [ ] **Step 9: Commit** (daemon may also auto-commit — that's fine on this branch)

```bash
git add tools/ojz_strip_gen.py
git commit -m "feat(art): generator emits one paged global act art pool; remove union/coloring"
```

---

## Task 3: build.sh — page compression + manifest include

**Files:** Modify `build.sh` (79-143).

- [ ] **Step 1: Replace the per-section ZX0 loop with per-page**

Replace `build.sh:79-117` (the `sec*_tiles.bin` ZX0 loop + the `DECOMP_BUFFER_CAPACITY` guards) with a loop over `act_pool_page*.bin`, each wrapped `[u16 BE uncompressed size][00][02]` + salvador ZX0 stream, guarded `size ≤ ART_POOL_PAGE_TILES*32` (8192):
```sh
ART_POOL_PAGE_BYTES=8192      # ART_POOL_PAGE_TILES (256) * 32
for page_bin in data/generated/ojz/act1/act_pool_page*.bin; do
    page_zx0="${page_bin%.bin}.zx0"
    size=$(stat -c%s "$page_bin")
    if (( size > ART_POOL_PAGE_BYTES )); then
        echo "ERROR: ${page_bin} is ${size} B — exceeds one page (${ART_POOL_PAGE_BYTES})."; exit 1
    fi
    "${TOOLS}/bin/salvador" "$page_bin" "${page_zx0}.tmp" > /dev/null
    printf '%b' "$(printf '\\x%02x\\x%02x\\x00\\x02' $((size >> 8)) $((size & 255)))" > "$page_zx0"
    cat "${page_zx0}.tmp" >> "$page_zx0"; rm -f "${page_zx0}.tmp"
done
```

- [ ] **Step 2: Replace the sec_tile_blobs dedup with a pool-page include**

Replace `build.sh:119-143` (the `sec_tile_blobs.asm` content-hash dedup) with emission of `ojz_act_pool.asm` listing page BINCLUDEs:
```sh
POOL_ASM="data/generated/ojz/act1/ojz_act_pool.asm"
{
  echo "; Auto-generated by build.sh — act art pool page BINCLUDEs + address table"
  i=0
  for page_zx0 in data/generated/ojz/act1/act_pool_page*.zx0; do
    echo "OJZ_Act_Pool_Page${i}:"
    echo "        BINCLUDE \"${page_zx0}\""
    i=$((i+1))
  done
  echo "OJZ_Act_Pool_PageTable:"            # dc.l of each page label, for Pool_LoadAll
  j=0
  while (( j < i )); do echo "        dc.l    OJZ_Act_Pool_Page${j}"; j=$((j+1)); done
} > "$POOL_ASM"
```
This `OJZ_Act_Pool_PageTable` (a `dc.l` of each page's address) is what `Pool_LoadAll` (Task 6) indexes — it does not guess label arithmetic.

- [ ] **Step 3: Verify the build data stage runs (no assembler yet)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | head -40` (it will fail later at the engine asm until Tasks 4-7, but the data stage + page compression must succeed).
Expected: pages compressed, `ojz_act_pool.asm` + `ojz_act_pool_manifest.asm` present; no `sec_tile_blobs.asm`/`sec_vram_bases.asm`; first assembler error is an *undefined symbol* from the engine side (expected — fixed in Tasks 4-7).

- [ ] **Step 4: Commit**

```bash
git add build.sh
git commit -m "build(art): compress act pool pages + emit pool include; drop per-section blobs"
```

---

## Task 4: Constants + RAM — purpose-named staging buffer

**Files:** Modify `constants.asm` (127), `ram.asm` (13-29).

- [ ] **Step 1: Replace the orphaned constant**

`constants.asm:127`: delete `DECOMP_BUFFER_SIZE = 32768`. Add near the VRAM/cache constants:
```
ART_POOL_PAGE_TILES     = 256                       ; tiles per pool page (matches build tool)
ART_STAGING_BUFFER_SIZE = ART_POOL_PAGE_TILES*32    ; 8192 — one page of decompressed art
```

- [ ] **Step 2: Replace the Decomp_Buffer aliases with a named staging buffer**

`ram.asm:27-29`: remove `Decomp_Buffer`/`Decomp_Buffer_End` aliases. Replace with a clearly-documented init-only staging view (it reuses the tile-cache nametable RAM, which is genuinely unpopulated during display-off level init — documented, not aliased-by-accident):
```
; Art staging — decompress one art-pool page here at level init (display off),
; then DMA it to VRAM. Occupies the tile-cache nametable RAM, which is not yet
; populated during init. INIT-ONLY; do not use after the cache is live.
Art_Staging_Buffer = Tile_Cache_Nametable
```
Confirm `ART_STAGING_BUFFER_SIZE` (8192) ≤ `TILE_CACHE_NT_SIZE` (9600) so the staging view fits.

- [ ] **Step 3: Build to confirm constants assemble**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | grep -i 'decomp_buffer\|art_staging' ; echo done`
Expected: no `Decomp_Buffer` undefined errors except from `load_art.asm` (fixed in Task 6); `Art_Staging_Buffer` resolves.

- [ ] **Step 4: Commit**

```bash
git add constants.asm ram.asm
git commit -m "refactor(art): Art_Staging_Buffer replaces Decomp_Buffer alias; drop DECOMP_BUFFER_SIZE"
```

---

## Task 5: Act/Sec descriptors — pool pointer, drop per-section art fields

**Files:** Modify `structs.asm` (Act + Sec), `data/levels/ojz/act1/act_descriptor.asm`.

- [ ] **Step 1: Add pool fields to the Act struct; remove per-section art from Sec**

In `structs.asm`: add to the Act struct `act_art_pool` (longword, ptr to `OJZ_Act_Pool_Page0`) and `act_art_pool_manifest` (longword or use the generated equates directly). Remove `sec_tile_art` ($40) and `sec_tile_art_vram` ($44) from the Sec struct (sections no longer carry per-section art). Keep the struct `struct`/`endstruct` discipline so AS recomputes offsets.

- [ ] **Step 2: Wire the act descriptor**

In `data/levels/ojz/act1/act_descriptor.asm`: include `data/generated/ojz/act1/ojz_act_pool_manifest.asm` and `ojz_act_pool.asm`; set `act_art_pool` to `OJZ_Act_Pool_Page0`. Remove the now-deleted includes of `sec_tile_blobs.asm` and `sec_vram_bases.asm`, and remove the per-section `dc.l ojz_Sec{N}_Tiles` / `dc.w OJZ_SEC{N}_VRAM` fields.

- [ ] **Step 3: Build to confirm descriptors assemble**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | grep -i 'sec_tile_art\|art_pool\|OJZ_SEC' ; echo done`
Expected: remaining errors only from `load_art.asm` referencing the old fields (fixed in Task 6).

- [ ] **Step 4: Commit**

```bash
git add structs.asm data/levels/ojz/act1/act_descriptor.asm
git commit -m "feat(art): act descriptor carries the art pool; sections drop per-section art fields"
```

---

## Task 6: Engine page loader (Pool_LoadAll)

**Files:** Modify `engine/level/load_art.asm` (replace 31-154).

- [ ] **Step 1: Replace the union load path with the page loader**

Replace `LoadArt_Compressed` (44-65), `Section_LoadArt` (81-89), and `Level_LoadArt` (103-154) with a single `Pool_LoadAll`. Keep `Art_Decompress` (22-28) unchanged. Interface + behavior:

```
; Pool_LoadAll — decompress every act-art-pool page into Art_Staging_Buffer and
; DMA each to its VRAM slot. Called at level init (display OFF) so the multi-page
; DMA drains across extended VBlanks. Replaces the per-section union load.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0-d4, a0-a4
;
; For page i in 0..OJZ_ACT_POOL_PAGES-1:
;   a0 = address of OJZ_Act_Pool_Page{i} (page list is contiguous labels; walk it)
;   peek u16 BE uncompressed size from wrapper; skip if zero
;   Art_Decompress -> Art_Staging_Buffer
;   QueueDMA_Critical: src = Art_Staging_Buffer, dest = OJZ_ACT_POOL_PAGE{i}_SLOT*32, len = size
;   VSync_Wait
```
Implementation note: emit the page label addresses as a small `dc.l` table in `ojz_act_pool.asm` (extend Task 3 Step 2 to also emit `OJZ_Act_Pool_PageTable: dc.l OJZ_Act_Pool_Page0, ...`) so the loader indexes pages by a table rather than guessing label arithmetic. Drive the loop from `OJZ_ACT_POOL_PAGES` and the per-page `*_SLOT` equates.

- [ ] **Step 2: Build the ROM**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -5`
Expected: `Build complete: s4.bin` (exit 0) — the build is UNBLOCKED.

- [ ] **Step 3: Commit**

```bash
git add engine/level/load_art.asm data/generated/ojz/act1/ojz_act_pool.asm
git commit -m "feat(art): Pool_LoadAll decompresses + DMAs all act-pool pages at init"
```

---

## Task 7: Wire init + delete dead stubs

**Files:** Modify `test/ojz_scroll_test.asm` (init call), `engine/level/section.asm` (delete 368-390).

- [ ] **Step 1: Call Pool_LoadAll at level init**

In `test/ojz_scroll_test.asm` around line 37 (where `Level_LoadArt` was called), call `Pool_LoadAll` with `a0 = OJZ_Act1_Descriptor` instead. Keep it before `Tile_Cache_Init` (the staging buffer reuses the not-yet-populated cache RAM) and before display-on (line 134).

- [ ] **Step 2: Delete the empty preload/deferred stubs**

In `engine/level/section.asm:368-390`, delete the `rts`-only stubs (`.preload_fwd`, `.preload_bwd`, `.preload_down`, `.preload_up`, `.deferred_fwd_load`, `.deferred_bwd_load`, etc.) and any now-dead branches to them. (Real prefetch arrives in Phase 2.)

- [ ] **Step 3: Build the ROM**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -3`
Expected: exit 0, `s4.bin` produced.

- [ ] **Step 4: Commit**

```bash
git add test/ojz_scroll_test.asm engine/level/section.asm
git commit -m "feat(art): init calls Pool_LoadAll; remove dead preload stubs"
```

---

## Task 8: Runtime verification (oracle emulator)

**Files:** none (verification).

- [ ] **Step 1: Reload the ROM and screenshot**

Use oracle MCP: `emulator_reload_rom` (`/home/volence/sonic_hacks/s4_engine/s4.bin`), then `emulator_screenshot`.
Expected: OJZ jungle art renders correctly (canopy, trunks, dirt, grass) — identical to the pre-change scaffold screenshot, i.e. the global pool loaded correctly to the right slots.

- [ ] **Step 2: Confirm scroll + profile (no regression)**

Drive scroll (reset; the scroll test auto-advances). Verify Camera_X advances/rebases across sections (read `Camera_X` deltas across frames). Enable profiler, `emulator_get_profiler_frames` during scroll.
Expected: ~60% idle, parallax-dominant, streaming small — matching `streaming_feasibility_2026_06_22`. No new lag.

- [ ] **Step 3: Confirm zero duplication + clean tree**

Run: `grep OJZ_ACT_POOL_TILES data/generated/ojz/act1/ojz_act_pool_manifest.asm` → ≈612 (the distinct count, not 884).
Run: `ls data/generated/ojz/act1/sec_tile_blobs.asm data/generated/ojz/act1/sec_vram_bases.asm 2>&1` → both absent.
Run: `grep -rn 'Decomp_Buffer\|DECOMP_BUFFER_SIZE\|color_sections\|assign_section_slots' engine tools constants.asm ram.asm | grep -v test_` → no matches (legacy fully removed).

- [ ] **Step 4: Final commit / merge prep**

```bash
git add -A docs/
git commit -m "docs(art): Phase 1 verified — global act art pool, build unblocked, zero duplication"
```
Then update `ENGINE_ARCHITECTURE.md` §2.3 (separate task / follow-up) to describe the act-art-pool model as the design, removing the graph-color/union prose.

---

## Self-review

- **Spec coverage:** §2.1 storage→Tasks 1-3; §2.2 reference (global indices)→Task 2 Step 3; §3 build→Tasks 1-3; §4 engine→Tasks 4-6; §6 cleanliness→Tasks 1,3,4,5,7 + Task 8 Step 3; §5 Phase 1→all. §2.3 residency *eviction* and §5 Phase 2/3 are explicitly out of scope (noted). ✓
- **Placeholders:** Python steps have complete code; ASM steps give interface + behavior + exact build/emulator verification (the engine's verification model — full instruction listings are written against live code during implementation, by design). The one genuinely deferred item (>2048-tile reference widening) is correctly Phase 2. ✓
- **Consistency:** `ART_POOL_PAGE_TILES=256` used in tile_dedupe, ojz_strip_gen (116), build.sh (8192=256*32), constants.asm. `canon_to_pool` / `pool_order` / `pages` names consistent across Task 1-2. `OJZ_ACT_POOL_*` manifest symbols consistent across Tasks 2,5,6. `Art_Staging_Buffer`/`ART_STAGING_BUFFER_SIZE` consistent Tasks 4,6. ✓
- **Risk:** Task 6's page-label-table emission was added to Task 3 Step 2 retroactively — confirm the `dc.l OJZ_Act_Pool_PageTable` is emitted there during implementation.
