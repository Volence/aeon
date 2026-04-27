# §2 Phase 2 — A.5: Per-Section Background Art Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all three Plane B background tiers from ENGINE_ARCHITECTURE.md §2.4 — zone-shared (T1), per-section layout (T2), per-section layout + own tile art (T3) — and prove each on OJZ Act 1 (T1 ships; T2/T3 via synth fixtures).

**Architecture:** Build-tool extension emits a zone-wide BG layout (T1) plus optional per-section BG layouts (T2/T3) and BG-tile additions to A.3's section tile art groups (T3). Engine adds Plane B drawing routines (`BG_Init` for one-shot zone fill, `BG_RedrawForSection` for transition redraw). Tier detection via sentinel pointers on Act / Sec descriptors — no parallel system, BG fits inside the existing Sec / art-group / streaming machinery.

**Tech Stack:** AS Macro Assembler (asw), Python 3 (`tools/ojz_strip_gen.py`, `tools/tile_dedupe.py`, `tools/s4lz.py`), Exodus emulator with MCP for visual verification.

---

## Files in scope

**Create:**
- `docs/research/per-section-background.md` — Task 1 research output
- `data/levels/ojz/act1/bg_fixture_t2.asm` — synth tier-2 fixture variant (OJZ act with one tier-2 section)
- `data/levels/ojz/act1/bg_fixture_t3.asm` — synth tier-3 fixture variant (OJZ act with one tier-3 section)
- `engine/level/bg.asm` — Plane B drawing routines (`BG_Init`, `BG_RedrawForSection`)
- `tools/test_bg_emit.py` — unit tests for BG layout emission

**Modify:**
- `tools/ojz_strip_gen.py` — extend `generate()` for BG layout emission + tier-3 BG-tile inclusion in section art groups
- `structs.asm` — Act gets `act_bg_layout`; Sec gets `sec_bg_layout`; obsolete `sec_strips_b` placeholder removed
- `data/levels/ojz/act1/act_descriptor.asm` — emit `act_bg_layout` + per-section `sec_bg_layout` (NULL on shipped OJZ = T1)
- `engine/level/section.asm` — call `BG_RedrawForSection` from `Section_TeleportFwd` / `Section_TeleportBwd` for T2/T3 sections
- `engine/level/load_art.asm` — `Level_LoadArt` calls `BG_Init` for the act's zone-wide BG; `Section_StreamArtGroup` covers BG tiles for T3 sections
- `test/ojz_scroll_test.asm` — wire act-descriptor selection (default OJZ vs T2 fixture vs T3 fixture) via build flag
- `build.sh` — pass tier-fixture flag through to `ojz_strip_gen.py` when building fixture variants
- `docs/ENGINE_ARCHITECTURE.md` — §2.4 updated with concrete tier-detection rules and storage decisions
- `docs/research/tile-pipeline-measurements.md` — append A.5 row(s)
- `docs/DEFERRED_WORK.md` — mark §2 phase 2 complete; record any uncovered follow-ups

---

## Task 1: Research — full CLAUDE.md sweep

Settle three open questions from the spec via research across ALL 7 reference disasms + online sources. **Per project memory `feedback_research_breadth`: listed targets are starting points, not limits.** Per `feedback_research_before_build`: cross-reference findings against ENGINE_ARCHITECTURE.md §2.4 baseline, don't treat documented designs as from-scratch.

**Files:**
- Create: `docs/research/per-section-background.md`

**Open questions (research must produce a recommendation for each):**
1. Pre-clear Plane B before T2/T3 redraw, or trust full-coverage strips? (Speed vs robustness; affects redraw cost)
2. Does T3 BG tile art share A.3's "art group" concept (spec hunch: cleaner) or sit in a parallel system?
3. Does BG-tile dedupe share the global FG-tile pool (more aliasing opportunities) or run as a separate pass (simpler, less aliasing)?

**Bonus question (because it must be settled before Task 4):**
4. BG layout storage shape — full Plane B nametable (64×32 = 4096 B/section), partial (e.g. 64×16 = 2048 B), column-strip array (parallel to strips_a)? Sonic 2 / S3K / S.C.E. evidence determines this.

- [ ] **Step 1: Sweep all 7 reference disasms for Plane B handling**

Read each disasm's level loader and section/zone transition for how Plane B is initialized, scrolled, and redrawn. Capture (a) the data shape (full nametable? strip array? row-by-row?) and (b) when redraw happens (level-load only? per-zone? per-section?).

Targets and likely paths:
- `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/` — search for `Plane_B`, `bg_layout`, `Level_BGScroll`
- `/home/volence/sonic_hacks/sonic_hack/` — same patterns
- `/home/volence/sonic_hacks/The Adventures of Batman and Robin/` — `LoadTilesFromROM` and Plane B nametable writes
- `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/` — 64×64 plane usage, BG variants
- `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/` — Treasure's BG handling
- `/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/` — heavily-varying per-section BG
- `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/` — per-stage BG art swapping (spec-flagged target)

For each disasm, write a paragraph in the research doc: where the Plane B writes happen, what data shape is used, when redraw fires. If a disasm doesn't redraw Plane B per-section, note that — it's a data point.

- [ ] **Step 2: Sweep online sources**

Search the following for Plane B / BG techniques. **Don't stop at named sources** — follow links to anything relevant.

- plutiedev.com — Plane B nametable swaps, parallax, per-stage BG (spec-flagged)
- md.railgun.works — BG init sequences, hardware quirks
- segaretro.org — Sonic CD per-act backgrounds (spec-flagged), Castlevania Bloodlines techniques
- SpritesMind forum — search "plane B redraw", "BG streaming", "per-section background"
- GitHub homebrew — Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD, SGDK example projects
- SGDK (sgdk-mdrobot, marsdev) — modern BG/MAP loading patterns
- Amiga demoscene + 68000-era engine literature — applicable techniques

Capture: any pattern that contradicts or enriches the disasm findings. Especially look for "redraw whole nametable on transition" vs "stream column-by-column" vs "double-buffer Plane B" — and the cost of each.

- [ ] **Step 3: Settle the 4 open questions in the research doc**

For each question, write: (a) what each source said, (b) trade-offs, (c) the choice we'll make, (d) one sentence on why.

Anti-pattern from project memory `feedback_research_breadth`: don't trust thin subagent summaries. If a finding is load-bearing for the design, verify it by reading the actual cited code yourself.

- [ ] **Step 4: Update spec + arch doc with concrete decisions**

Edit `docs/superpowers/specs/2026-04-26-art-pipeline-phase2-design.md` Phase A.5 section: replace open-question bullets with the chosen answers, citing the research doc.

Edit `docs/ENGINE_ARCHITECTURE.md` §2.4: replace any vague/forward-looking language with the concrete tier-detection rule and storage shape settled by research.

- [ ] **Step 5: Commit research output**

```bash
git add docs/research/per-section-background.md docs/superpowers/specs/2026-04-26-art-pipeline-phase2-design.md docs/ENGINE_ARCHITECTURE.md
git commit -m "research(§2 A.5): settle BG layout shape, tier-3 art-group sharing, dedupe scope, redraw policy"
```

---

## Task 2: Add struct fields + remove dead `sec_strips_b` placeholder

`sec_strips_b` was added in §4 Phase 1 as a placeholder; nothing draws it, the build tool emits all-zero blobs for it (`tools/ojz_strip_gen.py:12`). Replace it with the real BG-layout fields settled in Task 1. The Act struct gets the zone-wide pointer so T1 sections can rely on a single shared layout.

**Files:**
- Modify: `structs.asm:106-156` (Sec + Act struct definitions)

- [ ] **Step 1: Audit usage of `sec_strips_b` to confirm it's dead**

```bash
cd /home/volence/sonic_hacks/s4_engine
grep -rn "sec_strips_b\|Sec_sec_strips_b\|Strips_B" engine/ test/ tools/ data/ docs/
```

Expected: only references are the struct definition, the placeholder emission in `ojz_strip_gen.py`, the BINCLUDE lines in `act_descriptor.asm`, and any docs. No engine code reads it.

- [ ] **Step 2: Remove `sec_strips_b` from Sec struct**

Edit `structs.asm` Sec struct (lines 106–134). Delete the `sec_strips_b ds.l 1` line at offset $1C. Replace it with a `ds.l 1` reserved slot (keeping struct size $48 unchanged this step — actual semantics added in Step 3).

- [ ] **Step 3: Add `sec_bg_layout` to Sec struct (replacing the reserved slot from Step 2)**

```asm
sec_strips_a        ds.l 1          ; $00 — plane A nametable strip array ptr (ROM)
sec_objects         ds.l 1          ; $04 — compact 4-byte object entries
sec_rings           ds.l 1          ; $08 — pattern-encoded ring entries
sec_plc             ds.l 1          ; $0C — S4LZ art PLC list
sec_pal             ds.l 1          ; $10 — 128-byte palette (4 lines × 32 bytes)
sec_scroll          ds.l 1          ; $14 — parallax layer table (Phase 4)
sec_raster_table    ds.l 1          ; $18 — raster command table (§7.2)
sec_bg_layout       ds.l 1          ; $1C — Plane B layout pointer (0 = use Act_bg_layout, T1)
```

Keep the rest of Sec unchanged through `sec_tile_art_vram`. Verify the assertion at end of struct still says `if Sec_len <> $48`.

- [ ] **Step 4: Add `act_bg_layout` to Act struct**

Edit `structs.asm` Act struct (lines 140–156). Add field after `cam_max_y`:

```asm
cam_max_y           ds.w 1          ; $14 — camera Y upper bound (pixels)
act_bg_layout       ds.l 1          ; $16 — zone-wide Plane B layout pointer (T1 default)
Act endstruct

    if Act_len <> $1A
      error "Act struct is \{Act_len} bytes, expected $1A"
    endif
```

- [ ] **Step 5: Build to verify struct size assertions pass**

```bash
cd /home/volence/sonic_hacks/s4_engine
./build.sh -pe
```

Expected: PASS (no struct-size errors). Build will fail later because `act_descriptor.asm` still references `OJZ_SecN_Strips_B` and the new `act_bg_layout` field is missing — that's fine, those are fixed in Task 4.

- [ ] **Step 6: Commit struct changes**

```bash
git add structs.asm
git commit -m "feat(§2 A.5): add sec_bg_layout + act_bg_layout, retire sec_strips_b placeholder"
```

---

## Task 3: Build-tool — emit zone-wide BG layout (T1)

Build tool reads chunk-row-0 (sky band) of OJZ once and emits a zone-wide Plane B layout blob. Storage shape is whatever Task 1's research settled — for the planning code below assume **full 64×32 Plane B nametable, raw uncompressed, 4096 bytes** (replace with research's choice if different).

**Files:**
- Modify: `tools/ojz_strip_gen.py` (add `emit_zone_bg_layout()` helper, call from `generate()`)
- Test: `tools/test_bg_emit.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tools/test_bg_emit.py`:

```python
"""Tests for BG layout emission (§2 A.5 T1)."""

import os
import struct
import tempfile
import unittest

from ojz_strip_gen import (
    decompress_full_ojz_art,
    emit_zone_bg_layout,
)


class TestZoneBgEmit(unittest.TestCase):
    def test_zone_bg_layout_is_64_by_32(self):
        """T1 zone-wide BG layout: full Plane B nametable size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks, blocks, tiles = decompress_full_ojz_art()
            out_path = os.path.join(tmpdir, "zone_bg.bin")
            emit_zone_bg_layout(chunks, blocks, out_path)
            self.assertTrue(os.path.isfile(out_path))
            size = os.path.getsize(out_path)
            self.assertEqual(size, 64 * 32 * 2,
                             f"Expected 4096 B (64×32 nametable words), got {size}")

    def test_zone_bg_layout_words_are_valid_nametable_words(self):
        """Each word's tile-index field must stay below 1536 (no nametable collision)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks, blocks, tiles = decompress_full_ojz_art()
            out_path = os.path.join(tmpdir, "zone_bg.bin")
            emit_zone_bg_layout(chunks, blocks, out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            for i in range(0, len(data), 2):
                word = struct.unpack(">H", data[i:i+2])[0]
                tile_index = word & 0x07FF
                self.assertLess(tile_index, 1536,
                                f"BG word {i//2} has tile_index {tile_index} ≥ 1536")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/volence/sonic_hacks/s4_engine
python3 -m unittest tools.test_bg_emit -v
```

Expected: FAIL with `ImportError: cannot import name 'emit_zone_bg_layout' from 'ojz_strip_gen'`.

- [ ] **Step 3: Implement `emit_zone_bg_layout` in `tools/ojz_strip_gen.py`**

Place near other emission helpers (alongside the strip-emission code). The function builds the BG nametable by reading chunk-row 0 of every chunk in OJZ's layout (the sky/cloud band) and writing 64 columns × 32 rows of nametable words.

```python
def emit_zone_bg_layout(chunks, blocks, out_path):
    """Emit a 64×32 Plane B nametable for OJZ's zone-wide BG (sky+clouds).

    BG content = chunk-row 0 of every chunk in OJZ's act-1 layout, repeated
    horizontally to cover all 64 plane columns. Vertical: 32 rows = 4 chunk-rows
    of 8 tiles each. Output is raw uncompressed VDP nametable words (big-endian).
    """
    PLANE_W = 64
    PLANE_H = 32
    out = bytearray(PLANE_W * PLANE_H * 2)

    # OJZ's zone-wide BG repeats horizontally — pick chunk 0's row 0 as the unit.
    # (Task 1 research may select a different sampling strategy; update here.)
    sample_chunk = 0
    chunk_data = chunks[sample_chunk]  # 8×8 block of block-IDs

    for plane_row in range(PLANE_H):
        chunk_row_in_block = plane_row // 2  # 2 plane-rows per chunk-row of 16px / 8px tile
        for plane_col in range(PLANE_W):
            chunk_col_in_block = plane_col // 2
            block_id_word = chunk_data[chunk_row_in_block * 8 + (chunk_col_in_block & 7)]
            block_id = block_id_word & 0x03FF
            block = blocks[block_id]  # 4 tile-words per block (2×2 tile arrangement)
            tile_in_block_row = plane_row & 1
            tile_in_block_col = plane_col & 1
            tile_word = block[tile_in_block_row * 2 + tile_in_block_col]
            tile_word &= 0xF7FF  # strip priority bit (BG stays low-priority)
            offset = (plane_row * PLANE_W + plane_col) * 2
            out[offset:offset+2] = tile_word.to_bytes(2, 'big')

    with open(out_path, "wb") as f:
        f.write(out)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m unittest tools.test_bg_emit -v
```

Expected: PASS — both `test_zone_bg_layout_is_64_by_32` and `test_zone_bg_layout_words_are_valid_nametable_words`.

- [ ] **Step 5: Wire `emit_zone_bg_layout` into `generate()`**

Find the section in `ojz_strip_gen.py` `generate()` where strip blobs are emitted (after dedupe + remap). Add a call to emit `zone_bg.bin`:

```python
zone_bg_path = os.path.join(out_dir, "zone_bg.bin")
emit_zone_bg_layout(chunks, blocks, zone_bg_path)
print(f"Emitted zone BG layout: {zone_bg_path} ({os.path.getsize(zone_bg_path)} bytes)")
```

- [ ] **Step 6: Run build tool to verify zone_bg.bin appears in generated output**

```bash
cd /home/volence/sonic_hacks/s4_engine
python3 tools/ojz_strip_gen.py generate
ls -l data/generated/ojz/act1/zone_bg.bin
```

Expected: file exists, size 4096 bytes.

- [ ] **Step 7: Commit build-tool BG emission**

```bash
git add tools/ojz_strip_gen.py tools/test_bg_emit.py
git commit -m "feat(§2 A.5 T1): emit zone-wide Plane B nametable from build tool"
```

---

## Task 4: Wire `act_bg_layout` into OJZ act descriptor + remove placeholder strips_b BINCLUDEs

**Files:**
- Modify: `data/levels/ojz/act1/act_descriptor.asm`

- [ ] **Step 1: Add zone BG label + BINCLUDE at end of file**

Append to `data/levels/ojz/act1/act_descriptor.asm` (after the existing per-section tile blobs):

```asm
; Zone-wide BG layout (§2 A.5 T1)
OJZ_Act1_BG_Layout: BINCLUDE "data/generated/ojz/act1/zone_bg.bin"
    align 2
```

- [ ] **Step 2: Add `act_bg_layout` to `OJZ_Act1_Descriptor`**

Edit lines 11–23 to append the new field after `cam_max_y`:

```asm
OJZ_Act1_Descriptor:
    dc.l    OJZ_Act1_Sections       ; sec_grid_ptr
    dc.w    9                       ; grid_w
    dc.w    1                       ; grid_h
    dc.w    $0100                   ; start_local_x
    dc.w    $0060                   ; start_local_y
    dc.b    0                       ; start_sec_x
    dc.b    0                       ; start_sec_y
    dc.w    SLOT_ORIGIN_L           ; cam_min_x
    dc.w    SLOT_ORIGIN_L + $4680   ; cam_max_x
    dc.w    0                       ; cam_min_y
    dc.w    128                     ; cam_max_y
    dc.l    OJZ_Act1_BG_Layout      ; act_bg_layout (§2 A.5 T1)
    align 2
```

- [ ] **Step 3: Replace all 9 `OJZ_SecN_Strips_B` references with NULL pointer (`0`)**

For each `OJZ_SecN:` block (9 of them), change line `dc.l OJZ_SecN_Strips_B` (which was `sec_strips_b` at offset $1C) to `dc.l 0` (now `sec_bg_layout` at offset $1C with NULL = "use act default").

```bash
sed -i 's/dc\.l    OJZ_Sec\([0-9]\)_Strips_B/dc.l    0                       ; sec_bg_layout (NULL = T1 default)/g' \
  data/levels/ojz/act1/act_descriptor.asm
```

- [ ] **Step 4: Delete the 9 `OJZ_SecN_Strips_B: BINCLUDE` lines**

These reference now-deleted placeholder files (the build tool will be updated in Task 7 to stop emitting them). For now, just delete the BINCLUDEs:

```bash
sed -i '/OJZ_Sec[0-9]_Strips_B: BINCLUDE/,/^    align 2$/{/OJZ_Sec[0-9]_Strips_B: BINCLUDE/d; /^    align 2$/d}' \
  data/levels/ojz/act1/act_descriptor.asm
```

(If the sed range deletion is fragile in your environment, edit the file by hand: remove the 9 pairs of `OJZ_SecN_Strips_B: BINCLUDE ...` + following `align 2` lines.)

- [ ] **Step 5: Stop emitting placeholder strips_b in build tool**

Edit `tools/ojz_strip_gen.py` — find the line that emits `sec{N}_strips_b.bin` (around line 799) and the docstring at line 12. Remove both. Search for any other `_strips_b` references and remove.

- [ ] **Step 6: Build to verify it links cleanly**

```bash
cd /home/volence/sonic_hacks/s4_engine
./build.sh -pe
```

Expected: PASS. ROM `s4.bin` produced.

- [ ] **Step 7: Commit descriptor wiring**

```bash
git add data/levels/ojz/act1/act_descriptor.asm tools/ojz_strip_gen.py
git commit -m "feat(§2 A.5 T1): wire act_bg_layout into OJZ descriptor; drop strips_b placeholder"
```

---

## Task 5: Engine — `BG_Init` draws Plane B once at level load

**Files:**
- Create: `engine/level/bg.asm`
- Modify: `engine/level/load_art.asm` (call `BG_Init` from `Level_LoadArt`)
- Modify: top-level include list (probably `S4.asm` or wherever section.asm is included)

- [ ] **Step 1: Find where engine files are included**

```bash
cd /home/volence/sonic_hacks/s4_engine
grep -rn "engine/level/section.asm\|engine/level/load_art.asm" --include="*.asm"
```

Note the file that includes those — `bg.asm` will go in the same place.

- [ ] **Step 2: Create `engine/level/bg.asm`**

```asm
; Plane B (background) drawing routines (§2 A.5)
; T1: BG_Init — blit zone-wide layout to VRAM Plane B nametable once at level load.
; T2/T3: BG_RedrawForSection — replace Plane B nametable from new section's BG.

VRAM_PLANE_B_BYTES = $E000              ; Plane B nametable VRAM byte address
BG_LAYOUT_SIZE     = 64 * 32 * 2        ; 4096 bytes (full nametable)

; -----------------------------------------------
; BG_Init — copy act_bg_layout to Plane B nametable.
; In:  a0 = Act descriptor pointer
; Out: none
; Clobbers: d0–d2, a0–a2
; Note: blocking write via VDP DATA port. Display assumed off (called from
;       level-init path before display is enabled).
; -----------------------------------------------
BG_Init:
        movea.l Act_act_bg_layout(a0), a1
        cmpa.l  #0, a1
        beq.s   .skip                           ; act has no zone BG (defensive — every shipped act sets it)

        ; -- set VDP write address to Plane B nametable, autoincrement = 2 --
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (VDP_CTRL).l

        ; -- blit BG_LAYOUT_SIZE bytes via word writes --
        lea     (VDP_DATA).l, a2
        move.w  #BG_LAYOUT_SIZE/2 - 1, d0       ; word count - 1
.copy:
        move.w  (a1)+, (a2)
        dbf     d0, .copy
.skip:
        rts

; -----------------------------------------------
; BG_RedrawForSection — replace Plane B nametable from a section's BG layout.
; In:  a0 = Sec ptr
;      a1 = Act ptr (for fallback)
; Out: none
; Clobbers: d0, a0–a2
; Used by Section_TeleportFwd / Section_TeleportBwd for T2/T3 sections.
; If sec_bg_layout is NULL, the section is T1 (uses Act default — no redraw).
; -----------------------------------------------
BG_RedrawForSection:
        move.l  Sec_sec_bg_layout(a0), d0
        beq.s   .t1_skip                         ; T1: no redraw needed
        ; T2/T3: blit per-section layout to Plane B
        movea.l d0, a1
        ; -- (research-settled: pre-clear or trust full coverage; default trust) --
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (VDP_CTRL).l
        lea     (VDP_DATA).l, a2
        move.w  #BG_LAYOUT_SIZE/2 - 1, d0
.copy:
        move.w  (a1)+, (a2)
        dbf     d0, .copy
.t1_skip:
        rts
```

- [ ] **Step 3: Include `engine/level/bg.asm` from the top-level include list**

Add `include "engine/level/bg.asm"` next to the existing `include "engine/level/section.asm"` line in whichever file aggregates engine includes (found in Step 1).

- [ ] **Step 4: Wire `BG_Init` into `Level_LoadArt`**

Read `engine/level/load_art.asm` to find `Level_LoadArt`. Add a call to `BG_Init` after the FG art load completes, before `Level_LoadArt` returns. The act-descriptor pointer should already be in `a0` at level-init entry per the test's `lea OJZ_Act1_Descriptor, a0` setup.

```bash
grep -n "Level_LoadArt:" engine/level/load_art.asm
```

Read around that line, then add `bsr.w BG_Init` (with `a0` set to the act ptr — preserve or restore around the call as needed).

If `Level_LoadArt` consumes `a0` partway through, save+restore:

```asm
        movem.l a0, -(sp)
        ; ... existing FG art load body ...
        movem.l (sp)+, a0
        bsr.w   BG_Init
        rts
```

- [ ] **Step 5: Build**

```bash
./build.sh -pe
```

Expected: PASS.

- [ ] **Step 6: Visual verification via Exodus MCP**

Open the ROM in Exodus (user does the open). Then via MCP:

1. Run `mcp__exodus__emulator_reset`
2. Wait until `Game_State` reaches `GameState_OJZScroll_Update` (`mcp__exodus__emulator_run_to` Game_State write).
3. Take `mcp__exodus__emulator_screenshot` — confirm Plane B contains a sky+cloud band, not black.
4. Open the Plane B viewer (`mcp__exodus__emulator_get_layer_states`) and dump VRAM at $E000–$EFFF — confirm tile-index field is non-zero across the sampled words.

Document findings — sky should look like a band, not garbage. If garbage: the chunk sampling in `emit_zone_bg_layout` picked the wrong row; revise.

- [ ] **Step 7: Commit T1 engine path**

```bash
git add engine/level/bg.asm engine/level/load_art.asm S4.asm   # or whichever aggregates includes
git commit -m "feat(§2 A.5 T1): BG_Init blits zone-wide Plane B at level load"
```

---

## Task 5b: Shared BG tile region (architectural extension surfaced during Task 5 verification)

**Why this exists:** Visual verification of Task 5 revealed that A.3's per-section graph-colored FG pool means VRAM slots 0–1279 are swapped on every section transition. The BG nametable can't reliably reference those slots — slot content shifts as the player moves. T1's "shares FG tiles" claim from §2.4 is a pre-A.3 assumption that didn't survive.

**Fix:** reserve VRAM slots 1280–1535 ($A000-$BFFF) as a permanent shared BG tile region. Load it once at level init alongside the initial FG sections, never swap. BG nametable references resolve into this region. See `docs/research/per-section-background.md` Q5 for justification.

**Files:**
- Create: nothing new
- Modify: `tools/ojz_strip_gen.py` — extract BG layout from sonic_hack's `OJZ_1.bin`, dedupe BG-referenced tiles, emit `bg_tiles.bin` and remapped `zone_bg.bin`
- Modify: `tools/test_bg_emit.py` — tests for BG-tile dedupe + remap into shared region
- Modify: `constants.asm` — add `BG_TILE_BASE_VRAM = $A000`, `BG_TILE_BASE_SLOT = 1280`, `BG_TILE_CAPACITY = 256`
- Modify: `structs.asm` — Act struct gains `act_bg_tiles ds.l 1` at `$1A` (Act_len → $1E)
- Modify: `engine/level/bg.asm` — `BG_Init` loads `act_bg_tiles` to VRAM $A000 first, then blits Plane B nametable
- Modify: `data/levels/ojz/act1/act_descriptor.asm` — wire `act_bg_tiles` to new `OJZ_BG_Tiles` BINCLUDE

- [ ] **Step 1: Add BG-tile constants**

`constants.asm`:
```asm
BG_TILE_BASE_VRAM   = $A000           ; (slot 1280) start of shared BG tile region
BG_TILE_BASE_SLOT   = BG_TILE_BASE_VRAM/32   ; 1280 — for nametable index remap
BG_TILE_CAPACITY    = 256             ; tiles ($A000..$BFFF = 8 KB)
```

- [ ] **Step 2: Add `act_bg_tiles` to Act struct**

```asm
act_bg_layout       ds.l 1          ; $16 — zone-wide Plane B nametable
act_bg_tiles        ds.l 1          ; $1A — zone-wide Plane B tile blob (raw)
Act endstruct
    if Act_len <> $1E
      error "Act struct is \{Act_len} bytes, expected $1E"
    endif
```

- [ ] **Step 3: Extend build tool — extract BG layout from OJZ_1.bin**

Add helpers in `tools/ojz_strip_gen.py`:
- `load_bg_layout(path) → list[list[int]]` parses OJZ_1.bin's BG section (rows after FG)
- `extract_bg_tile_refs(bg_layout, chunks, blocks) → set[int]` collects unique tile indices referenced by the BG region we'll display
- `emit_bg_tiles(unique_indices, full_blob, out_path) → mapping` writes raw deduped tile bytes, returns src→canon map (with hflip/vflip canonicalization via tile_dedupe)
- Modify `emit_zone_bg_layout` to accept a `tile_remap` dict and rewrite each tile_index → `BG_TILE_BASE_SLOT + canon_index`

- [ ] **Step 4: Tests in test_bg_emit.py**

```python
def test_bg_tile_count_fits_capacity(self):
    """BG tile pool must fit in BG_TILE_CAPACITY (256 slots) for OJZ."""
    # ... extracts BG tiles, asserts len(unique) <= 256
def test_zone_bg_indices_in_shared_region(self):
    """Every BG nametable word's tile_index must land in [1280, 1535]."""
    # ... emits zone_bg, asserts all words have tile_index ∈ [1280, 1535]
```

- [ ] **Step 5: Engine — `BG_Init` loads BG tiles + blits nametable**

```asm
BG_Init:
        movem.l d0-d4/a0-a3, -(sp)
        movea.l a0, a3                          ; a3 = act ptr (preserve)

        ; --- load BG tile blob to VRAM at BG_TILE_BASE_VRAM ---
        movea.l Act_act_bg_tiles(a3), a1
        cmpa.w  #0, a1
        beq.s   .skip_tiles
        ; size baked into the blob's first word (uncompressed length, big-endian)
        move.w  (a1)+, d4                       ; d4 = byte length
        beq.s   .skip_tiles
        stopZ80
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(BG_TILE_BASE_VRAM,VRAM,WRITE), (VDP_CTRL).l
        lea     (VDP_DATA).l, a2
        lsr.w   #1, d4                          ; words = bytes / 2
        subq.w  #1, d4
.tile_copy:
        move.w  (a1)+, (a2)
        dbf     d4, .tile_copy
        startZ80
.skip_tiles:

        ; --- blit BG nametable to Plane B ---
        movea.l Act_act_bg_layout(a3), a1
        cmpa.w  #0, a1
        beq.s   .skip_nt
        stopZ80
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (VDP_CTRL).l
        lea     (VDP_DATA).l, a2
        move.w  #BG_LAYOUT_SIZE/2 - 1, d0
.nt_copy:
        move.w  (a1)+, (a2)
        dbf     d0, .nt_copy
        startZ80
.skip_nt:
        movem.l (sp)+, d0-d4/a0-a3
        rts
```

(Header word convention: BG-tiles blob starts with a big-endian uncompressed-length word, mirroring S4LZ's blob shape so the engine doesn't need a separate "byte count" field.)

- [ ] **Step 6: Wire `act_bg_tiles` into OJZ descriptor**

`act_descriptor.asm`:
```asm
    dc.l    OJZ_Act1_BG_Layout      ; act_bg_layout
    dc.l    OJZ_Act1_BG_Tiles       ; act_bg_tiles (§2 A.5 T1 shared region)
    align 2
...
OJZ_Act1_BG_Tiles: BINCLUDE "data/generated/ojz/act1/bg_tiles.bin"
    align 2
```

- [ ] **Step 7: Build, reload, visually verify**

Build, reload ROM in Exodus, screenshot, confirm Plane B shows authentic OJZ clouds + grass band (matches sonic_hack image-9 reference).

- [ ] **Step 8: Commit**

```bash
git add tools/ojz_strip_gen.py tools/test_bg_emit.py constants.asm structs.asm engine/level/bg.asm data/levels/ojz/act1/act_descriptor.asm
git commit -m "feat(§2 A.5 T1): shared BG tile region — load OJZ_1.bin BG tiles once at level init"
```

---

## Task 6: T1 measurement entry + visual confirmation in measurements doc

**Files:**
- Modify: `docs/research/tile-pipeline-measurements.md`

- [ ] **Step 1: Append A.5 T1 row to the measurement table**

Edit `docs/research/tile-pipeline-measurements.md`. Append a new section heading after the post-A.4 row:

```markdown
## A.5 T1 — Zone-wide background layer added

Plane B now displays the zone-wide BG (sky+clouds). Engine cost is one level-init blit of 4 KB (4096 word-writes via VDP DATA port, ~0.6 ms — once, before display is enabled). Per-frame cost: zero.

| Metric | Pre-A.5 | A.5 T1 |
|---|---:|---:|
| Plane B contents | All zeros (black) | 64×32 zone BG |
| Level-init Plane B blit | 0 bytes | 4096 bytes (one-shot) |
| Per-section transition cost | 0 (Plane B unchanged) | 0 (T1: no redraw) |
| ROM cost — zone BG layout | 0 | 4096 B uncompressed |
| Per-section sec_strips_b placeholder | 9 × N B (placeholder) | Removed |

Visual: OJZ scroll test now shows a continuous sky+cloud BG band on Plane B while FG (trees) renders on Plane A. No transition stutter on FWD/BWD teleports (T1 = static BG, nothing to redraw).
```

- [ ] **Step 2: Commit measurement update**

```bash
git add docs/research/tile-pipeline-measurements.md
git commit -m "docs(§2 A.5 T1): record measurement + visual confirmation"
```

---

## Task 7: Build-tool — emit per-section BG layout (T2 / T3 path)

Tier detection:
- `sec_bg_layout = NULL`, `sec_tile_art_s4lz` shared with FG → T1
- `sec_bg_layout ≠ NULL`, `sec_tile_art_s4lz` shared → T2
- `sec_bg_layout ≠ NULL`, `sec_tile_art_s4lz` separate (BG tiles in same group as FG via A.3 art-group sharing — research-settled in Task 1) → T3

**Files:**
- Modify: `tools/ojz_strip_gen.py` (add `emit_section_bg_layout()`, `--bg-tier` flag)
- Modify: `tools/test_bg_emit.py` (add T2/T3 emission tests)

- [ ] **Step 1: Write the failing test for per-section BG emission**

Append to `tools/test_bg_emit.py`:

```python
class TestSectionBgEmit(unittest.TestCase):
    def test_section_bg_layout_is_64_by_32(self):
        """T2/T3 per-section BG layout: same shape as zone BG."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks, blocks, tiles = decompress_full_ojz_art()
            out_path = os.path.join(tmpdir, "sec0_bg.bin")
            # Sample chunk index 1 to differentiate from zone-BG (chunk 0).
            emit_section_bg_layout(chunks, blocks, sample_chunk_id=1, out_path=out_path)
            self.assertEqual(os.path.getsize(out_path), 64 * 32 * 2)

    def test_section_bg_layout_differs_from_zone_bg(self):
        """T2 fixture must produce a layout visually different from zone BG."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks, blocks, tiles = decompress_full_ojz_art()
            zone_path = os.path.join(tmpdir, "zone.bin")
            sec_path = os.path.join(tmpdir, "sec.bin")
            emit_zone_bg_layout(chunks, blocks, zone_path)
            emit_section_bg_layout(chunks, blocks, sample_chunk_id=1, out_path=sec_path)
            with open(zone_path, "rb") as f:
                zone = f.read()
            with open(sec_path, "rb") as f:
                sec = f.read()
            self.assertNotEqual(zone, sec, "Section BG must differ from zone BG for T2/T3 visibility test")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest tools.test_bg_emit.TestSectionBgEmit -v
```

Expected: FAIL with `ImportError: cannot import name 'emit_section_bg_layout'`.

- [ ] **Step 3: Implement `emit_section_bg_layout`**

Add to `tools/ojz_strip_gen.py` near `emit_zone_bg_layout`:

```python
def emit_section_bg_layout(chunks, blocks, sample_chunk_id, out_path):
    """Emit a 64×32 Plane B nametable for one section's BG (T2/T3).

    Differs from emit_zone_bg_layout only in which chunk is sampled — letting
    T2/T3 fixtures show visually distinct backgrounds per section without
    needing real per-section BG source data in OJZ.
    """
    PLANE_W = 64
    PLANE_H = 32
    out = bytearray(PLANE_W * PLANE_H * 2)
    chunk_data = chunks[sample_chunk_id]

    for plane_row in range(PLANE_H):
        chunk_row_in_block = plane_row // 2
        for plane_col in range(PLANE_W):
            chunk_col_in_block = plane_col // 2
            block_id_word = chunk_data[chunk_row_in_block * 8 + (chunk_col_in_block & 7)]
            block_id = block_id_word & 0x03FF
            block = blocks[block_id]
            tile_in_block_row = plane_row & 1
            tile_in_block_col = plane_col & 1
            tile_word = block[tile_in_block_row * 2 + tile_in_block_col]
            tile_word &= 0xF7FF
            offset = (plane_row * PLANE_W + plane_col) * 2
            out[offset:offset+2] = tile_word.to_bytes(2, 'big')

    with open(out_path, "wb") as f:
        f.write(out)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m unittest tools.test_bg_emit -v
```

Expected: PASS — all 4 tests.

- [ ] **Step 5: Add `--bg-fixture` CLI flag to `ojz_strip_gen.py generate`**

Find the argparse setup in `generate()`'s entry point. Add:

```python
parser.add_argument("--bg-fixture", choices=["none", "t2", "t3"], default="none",
                    help="Emit T2/T3 BG fixtures for synth visual verification (default: none = T1 only)")
```

- [ ] **Step 6: Wire the flag — when `--bg-fixture=t2` or `t3`, also emit `secN_bg.bin` for chosen sections**

Add to `generate()` after the zone BG emission:

```python
if args.bg_fixture in ("t2", "t3"):
    # Synth fixture: section 4 gets a different BG sampled from chunk index 1.
    sec_bg_path = os.path.join(out_dir, "sec4_bg.bin")
    emit_section_bg_layout(chunks, blocks, sample_chunk_id=1, out_path=sec_bg_path)
    print(f"Emitted T2/T3 fixture BG: {sec_bg_path}")

if args.bg_fixture == "t3":
    # T3 also gets per-section BG-tile additions to section 4's tile art group.
    # Build-tool research (Task 1) settles whether this shares FG dedupe pool or
    # a separate BG-only pool — stub here pending Task 1 outcome.
    raise NotImplementedError("T3 BG-tile emission — implemented in Task 9")
```

- [ ] **Step 7: Run build tool with T2 flag, verify sec4_bg.bin appears**

```bash
python3 tools/ojz_strip_gen.py generate --bg-fixture=t2
ls -l data/generated/ojz/act1/sec4_bg.bin
```

Expected: file exists, 4096 bytes, content differs from `zone_bg.bin`.

- [ ] **Step 8: Commit T2 build-tool emission**

```bash
git add tools/ojz_strip_gen.py tools/test_bg_emit.py
git commit -m "feat(§2 A.5 T2): emit per-section BG layout under --bg-fixture flag"
```

---

## Task 8: T2 fixture descriptor + engine redraw on transition

**Files:**
- Create: `data/levels/ojz/act1/bg_fixture_t2.asm`
- Modify: `engine/level/section.asm` (call `BG_RedrawForSection` from teleports)
- Modify: `test/ojz_scroll_test.asm` (build flag picks fixture descriptor)

- [ ] **Step 1: Create T2 fixture descriptor**

Copy the entire content of `data/levels/ojz/act1/act_descriptor.asm` to `data/levels/ojz/act1/bg_fixture_t2.asm`. Then edit the new file:

1. Rename top label from `OJZ_Act1_Descriptor:` to `OJZ_Act1_T2_Descriptor:`.
2. Find `OJZ_Sec4:` and change its `dc.l 0  ; sec_bg_layout` (added in Task 4) to `dc.l OJZ_Sec4_BG_Layout`.
3. At end of file, append:

```asm
; T2 fixture: section 4 has its own BG layout (sampled from a different chunk)
OJZ_Sec4_BG_Layout: BINCLUDE "data/generated/ojz/act1/sec4_bg.bin"
    align 2
```

- [ ] **Step 2: Add `BG_RedrawForSection` calls to teleport handlers**

Edit `engine/level/section.asm`. In `Section_TeleportFwd` (line ~249), after the existing post-teleport state machine block (around line 287, after `move.b #SS_RESIDENT, (a1, d6.w)`), add a `BG_RedrawForSection` call. Same for `Section_TeleportBwd` after line 329.

After teleport, `a0` already holds the new section's Sec ptr (set by `Section_GetSlotDef`). Use it directly.

In `Section_TeleportFwd` after the `SS_RESIDENT` write block, before the final `rts`:

```asm
        ; -- A.5: redraw Plane B if new section is T2/T3 (sec_bg_layout != 0) --
        movea.l (Current_Act_Ptr).w, a1
        bsr.w   BG_RedrawForSection
        rts
```

Same insertion in `Section_TeleportBwd` before its final `rts`. Both paths (the SS_IDLE → blocking fallback and the post-state-update path) need the redraw — careful: the `beq.w Section_LoadArt` is a tail call, so the BG redraw won't run on cold-camera writes. For Phase 1 / OJZ that's acceptable since cold writes only happen at level init (where `BG_Init` already ran). Add a comment.

Equivalent care for the SS_RESIDENT path:

```asm
Section_TeleportFwd:
        ; ... existing body ...
        cmpi.b  #SS_IDLE, d0
        beq.w   Section_TeleportFwd_ColdLoad      ; renamed: blocks then redraws BG
        move.b  #SS_RESIDENT, (a1, d6.w)
        movea.l a0, a3                              ; preserve Sec ptr across BG_RedrawForSection
        movea.l (Current_Act_Ptr).w, a1
        movea.l a3, a0
        bsr.w   BG_RedrawForSection
        rts

Section_TeleportFwd_ColdLoad:
        movea.l a0, a3                              ; preserve Sec ptr across Section_LoadArt
        bsr.w   Section_LoadArt
        movea.l a3, a0
        movea.l (Current_Act_Ptr).w, a1
        bsr.w   BG_RedrawForSection
        rts
```

(Same shape for `Section_TeleportBwd` — `BWD_ColdLoad`.)

- [ ] **Step 3: Add build-flag selection of fixture descriptor in test**

Edit `test/ojz_scroll_test.asm`. Wrap the `lea OJZ_Act1_Descriptor` lines (at least 3 places — `Level_LoadArt`, `Camera_Init`, `Section_Init`) with a build flag:

```asm
        ifndef BG_FIXTURE
BG_FIXTURE = 0
        endif

        ifndef OJZ_TEST_DESCRIPTOR
        if BG_FIXTURE = 2
OJZ_TEST_DESCRIPTOR equ OJZ_Act1_T2_Descriptor
        elseif BG_FIXTURE = 3
OJZ_TEST_DESCRIPTOR equ OJZ_Act1_T3_Descriptor
        else
OJZ_TEST_DESCRIPTOR equ OJZ_Act1_Descriptor
        endif
        endif
```

Then change the three `lea OJZ_Act1_Descriptor, a0` lines (lines 27, 31, 35 of `test/ojz_scroll_test.asm`) to `lea OJZ_TEST_DESCRIPTOR, a0`.

- [ ] **Step 4: Add `bg_fixture_t2.asm` to the build's included files**

Find the master include list (likely in `S4.asm`). After the `include "data/levels/ojz/act1/act_descriptor.asm"` line, add:

```asm
        ifdef BG_FIXTURE_T2
        include "data/levels/ojz/act1/bg_fixture_t2.asm"
        endif
```

(The build flag is set via `./build.sh --bg-fixture=t2` — wired in Step 5.)

- [ ] **Step 5: Add `--bg-fixture` flag to `build.sh`**

Edit `build.sh` to forward the flag. Locate the `python3 tools/ojz_strip_gen.py generate` call and the asw assembler invocation. Add:

```bash
BG_FIXTURE="${BG_FIXTURE:-none}"
for arg in "$@"; do
    case "$arg" in
        --bg-fixture=t2) BG_FIXTURE=t2 ;;
        --bg-fixture=t3) BG_FIXTURE=t3 ;;
    esac
done

# Pass to strip generator
python3 tools/ojz_strip_gen.py generate --bg-fixture="$BG_FIXTURE"

# Pass as asw -D define
ASW_DEFINES=""
case "$BG_FIXTURE" in
    t2) ASW_DEFINES="-D BG_FIXTURE=2 -D BG_FIXTURE_T2" ;;
    t3) ASW_DEFINES="-D BG_FIXTURE=3 -D BG_FIXTURE_T3" ;;
esac
# ... existing asw invocation, with $ASW_DEFINES injected before the input file
```

- [ ] **Step 6: Build T2 fixture variant**

```bash
./build.sh --bg-fixture=t2
```

Expected: PASS. ROM produced.

- [ ] **Step 7: Visual verification on T2 fixture**

User opens `s4.bin` in Exodus. Via MCP:
1. `mcp__exodus__emulator_reset`
2. Move camera right past section-3→section-4 transition (~5× sec FWD teleports starting from $200 camera_x).
3. `mcp__exodus__emulator_screenshot` — confirm Plane B now shows the section-4 fixture BG (different chunk sampling), distinct from sections 0–3.
4. Move camera back (BWD teleports) — confirm Plane B redraws back to T1 zone BG when leaving section 4.

If T2 redraw doesn't happen: BWD/FWD teleport call site missed. Re-check Step 2.

- [ ] **Step 8: Commit T2 fixture + engine redraw**

```bash
git add data/levels/ojz/act1/bg_fixture_t2.asm engine/level/section.asm test/ojz_scroll_test.asm build.sh S4.asm
git commit -m "feat(§2 A.5 T2): per-section BG layout fixture + engine redraw on teleport"
```

---

## Task 9: Build-tool — T3 BG tiles join section's tile art group

**Files:**
- Modify: `tools/ojz_strip_gen.py`
- Modify: `tools/test_bg_emit.py`

T3 means the section's BG also references unique tile art that must live in VRAM. Per Task 1 research outcome (assume "BG tiles share section's A.3 art group" path — revise if research chose otherwise): when `--bg-fixture=t3`, collect BG-referenced tile indices alongside FG-referenced ones into the section's tile blob and update its remap.

- [ ] **Step 1: Write failing test for T3 tile-group inclusion**

Append to `tools/test_bg_emit.py`:

```python
class TestT3TileGroupInclusion(unittest.TestCase):
    def test_t3_section_tile_group_includes_bg_tiles(self):
        """T3: section's tile blob includes tiles referenced by both FG strips AND BG layout."""
        # Run generate with --bg-fixture=t3
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["OJZ_OUT_DIR"] = tmpdir
            from ojz_strip_gen import generate_for_test  # extracted helper, see Step 3
            result = generate_for_test(out_dir=tmpdir, bg_fixture="t3")
            # Section 4 is the T3 fixture section. Its tile-set must include any
            # tile referenced only by BG (not by FG).
            self.assertIn("sec4_tile_count", result)
            self.assertGreater(result["sec4_bg_only_tile_count"], 0,
                               "T3 must add at least one BG-only tile to section's group")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest tools.test_bg_emit.TestT3TileGroupInclusion -v
```

Expected: FAIL.

- [ ] **Step 3: Refactor `generate()` into testable `generate_for_test`**

Extract `generate()`'s body into a new helper that returns a dict of metrics. Wrapper preserves the CLI behavior:

```python
def generate_for_test(out_dir, bg_fixture="none"):
    """Internal entry point — same as generate() but returns a metrics dict."""
    # ... existing body (move from CLI generate())
    return metrics  # dict with sec*_tile_count, sec*_bg_only_tile_count, etc.

def generate():
    args = parse_args()
    metrics = generate_for_test(out_dir=DEFAULT_OUT_DIR, bg_fixture=args.bg_fixture)
    # print metrics as before
```

- [ ] **Step 4: Implement T3 logic — when `bg_fixture=t3`, collect BG-tile references alongside FG**

Inside `generate_for_test`, where each section's tile-reference set is built (existing A.3 logic), extend it for T3 fixture sections:

```python
if bg_fixture == "t3" and sec_id == 4:
    # Walk the section's BG layout and add referenced tiles to the section's tile-set.
    bg_layout = build_section_bg_layout(chunks, blocks, sample_chunk_id=1)
    bg_tile_refs = collect_bg_tile_refs(bg_layout)
    fg_tile_refs = sec_tile_refs[sec_id]
    bg_only = bg_tile_refs - fg_tile_refs
    sec_tile_refs[sec_id] |= bg_tile_refs  # union
    metrics[f"sec{sec_id}_bg_only_tile_count"] = len(bg_only)
```

Where `build_section_bg_layout` is the in-memory variant of `emit_section_bg_layout` (returns a list/array instead of writing to disk), and `collect_bg_tile_refs(layout) -> set[int]` extracts the set of tile-index fields from the nametable words.

- [ ] **Step 5: Run T3 test**

```bash
python3 -m unittest tools.test_bg_emit.TestT3TileGroupInclusion -v
```

Expected: PASS.

- [ ] **Step 6: Run build tool with T3 flag, verify sec4 blob expanded**

```bash
python3 tools/ojz_strip_gen.py generate --bg-fixture=t3
ls -l data/generated/ojz/act1/sec4_tiles.bin
```

Compare with the size from `--bg-fixture=t2` (or `none`) — sec4 should be larger when T3 includes BG tiles.

- [ ] **Step 7: Commit T3 build-tool extension**

```bash
git add tools/ojz_strip_gen.py tools/test_bg_emit.py
git commit -m "feat(§2 A.5 T3): BG tiles join section's A.3 tile art group under --bg-fixture=t3"
```

---

## Task 10: T3 fixture descriptor + visual verification

A.4's existing `Section_StreamArtGroup` already streams the section's tile blob — no engine change needed for T3 streaming since BG tiles are now part of that blob. The only new code is the T3 fixture descriptor + a re-mapped BG layout that references the section's expanded tile group.

**Files:**
- Create: `data/levels/ojz/act1/bg_fixture_t3.asm`
- Modify: `tools/ojz_strip_gen.py` (T3 BG layout uses section-local tile indices, like FG strips do)

- [ ] **Step 1: T3 fixture's BG layout must use REMAPPED tile indices**

Currently `emit_section_bg_layout` writes raw chunk-extracted tile indices. For T3 (section's own tile-art group with its own VRAM base), the BG nametable words need to reference the same remapped indices as the FG strips — otherwise BG references VRAM tiles outside the section's group.

Add a `remap` parameter:

```python
def emit_section_bg_layout(chunks, blocks, sample_chunk_id, out_path, remap=None):
    """If remap is provided, rewrite each tile_index field via remap[idx]
    (matches the per-section A.3 remap used for FG strips)."""
    # ... existing body, but after computing tile_word:
    if remap is not None:
        tile_index = tile_word & 0x07FF
        flip_priority = tile_word & 0xF800
        new_index = remap.get(tile_index, tile_index)  # fallback unchanged for unknown
        tile_word = flip_priority | new_index
```

- [ ] **Step 2: Wire remap into T3 emission**

In `generate_for_test`, when emitting T3 fixture:

```python
if bg_fixture == "t3" and sec_id == 4:
    sec_bg_path = os.path.join(out_dir, "sec4_bg.bin")
    emit_section_bg_layout(chunks, blocks, sample_chunk_id=1,
                            out_path=sec_bg_path,
                            remap=sec_remap[sec_id])
```

- [ ] **Step 3: Create T3 fixture descriptor**

Copy `bg_fixture_t2.asm` to `bg_fixture_t3.asm`. Rename top label to `OJZ_Act1_T3_Descriptor:`. Section 4's `sec_bg_layout` already points to `OJZ_Sec4_BG_Layout` (T3 reuses the same per-section BG mechanism — A.3 streaming covers the new BG tiles transparently). No additional fields needed.

- [ ] **Step 4: Add T3 fixture include to top-level**

In `S4.asm` (or wherever fixtures are included):

```asm
        ifdef BG_FIXTURE_T3
        include "data/levels/ojz/act1/bg_fixture_t3.asm"
        endif
```

- [ ] **Step 5: Build T3 fixture**

```bash
./build.sh --bg-fixture=t3
```

Expected: PASS.

- [ ] **Step 6: Visual verification on T3 fixture via Exodus MCP**

User opens ROM. Via MCP:
1. Reset.
2. Camera right to enter section 4.
3. Screenshot — confirm BG shows section 4's variant (visually distinct from zone BG).
4. Open VRAM viewer, examine Plane B nametable AND section 4's tile-art VRAM base — confirm BG tile references resolve to the streamed-in section tiles, not garbage.
5. Move BWD out of section 4 — BG returns to zone default, no glitches.

Document findings.

- [ ] **Step 7: Commit T3 fixture + verification notes**

```bash
git add data/levels/ojz/act1/bg_fixture_t3.asm tools/ojz_strip_gen.py S4.asm
git commit -m "feat(§2 A.5 T3): per-section BG art fixture rides A.4 streaming"
```

---

## Task 11: Documentation + arch-doc sync

**Files:**
- Modify: `docs/research/tile-pipeline-measurements.md` (T2 + T3 measurements)
- Modify: `docs/ENGINE_ARCHITECTURE.md` §2.4 (final concrete design)
- Modify: `docs/DEFERRED_WORK.md` (mark §2 phase 2 complete; record any uncovered items)

- [ ] **Step 1: Append T2/T3 rows to measurements doc**

In `docs/research/tile-pipeline-measurements.md`, append:

```markdown
## A.5 T2 — Per-section BG layout (synth fixture)

T2 fixture uses section 4 of OJZ Act 1 with a BG layout sampled from chunk index 1 (visually distinct from zone-BG chunk 0). On FWD teleport into section 4, `BG_RedrawForSection` blits 4 KB to Plane B nametable. Cost: ~0.6 ms blocking (display continues; one-frame stutter possible — research-settled trade-off).

| Metric | A.5 T1 | A.5 T2 fixture |
|---|---:|---:|
| Per-section BG layout ROM | 0 | 4096 B/section |
| Transition redraw cost (frame-time) | 0 | ~0.6 ms (4096 word writes) |
| Plane B contents post-transition | unchanged (zone) | replaced (per-section) |
| Engine code added | BG_Init only | + BG_RedrawForSection |

## A.5 T3 — Per-section BG layout + own tile art (synth fixture)

T3 fixture: section 4's BG layout references the section's own A.3 tile-art group. BG tile additions ride A.4's `Section_StreamArtGroup` — no new streaming logic. Build-tool report on this fixture: sec4 had X BG-only tiles added to its tile group, Y total tiles in group.

| Metric | A.5 T2 | A.5 T3 fixture |
|---|---:|---:|
| sec4 tile-art group size | (T2 = FG only) | + BG-only tiles |
| BG tile remap applied to BG layout | n/a (shares FG VRAM) | yes (section-local indices) |
| Streaming entry uses A.4 path | n/a | yes (no new code) |

(Fill X and Y from actual generate() output.)
```

- [ ] **Step 2: Update ENGINE_ARCHITECTURE.md §2.4**

Edit `docs/ENGINE_ARCHITECTURE.md` lines 1250–1270. Replace forward-looking language with the actual implementation:

- Replace "Uses Section_BG_Layout_Ptr for a zone-wide BG fallback" with "Uses Act_act_bg_layout for zone-wide BG (T1 — drawn once at level load by BG_Init). Sections with non-zero sec_bg_layout override the zone default on FWD/BWD teleport via BG_RedrawForSection."
- Replace "Two new optional fields in the section definition: sec_bg_layout_off, sec_bg_plc_off" with the actual fields: `sec_bg_layout` (Sec, $1C, longword) and `act_bg_layout` (Act, $16, longword). Note: `sec_bg_plc_off` is NOT a separate field — T3 BG tiles join the section's existing A.3 tile-art group (`sec_tile_art_s4lz`), per Task 1 research.
- Note the storage shape: full 64×32 nametable per BG (4096 B), uncompressed (research-settled — replace with research outcome).

- [ ] **Step 3: Update DEFERRED_WORK.md**

Open `docs/DEFERRED_WORK.md`. Find the §2 Art & Compression Pipeline section. Mark Phase 2 layers A.1–A.5 complete with the date 2026-04-26 and a one-line summary. If the file has a dedicated "deferred" list, move A.5-related items to "done."

If T1's "blocking 4 KB blit on transition" is something we want to defer optimizing (deferrable DMA via the queue), add a deferred entry: "§2 A.5 T2/T3 BG redraw via Deferrable DMA queue rather than blocking — currently ~0.6 ms blocking on transition, could move to ~0 ms by routing through Plane_Buffer or a dedicated streaming buffer."

- [ ] **Step 4: Commit documentation**

```bash
git add docs/research/tile-pipeline-measurements.md docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "docs(§2 A.5): finalize tier design, record T1/T2/T3 measurements, update deferred"
```

---

## Task 12: Merge to master + close §2 phase 2 milestone

**Files:** none (git only)

- [ ] **Step 1: Verify all tests pass**

```bash
cd /home/volence/sonic_hacks/s4_engine
python3 -m unittest tools.test_tile_dedupe tools.test_bg_emit tools.test_s4lint tools.test_s4budget -v
```

Expected: all PASS.

- [ ] **Step 2: Verify all three build variants**

```bash
./build.sh                          # default (T1 only)
./build.sh --bg-fixture=t2          # T2 fixture
./build.sh --bg-fixture=t3          # T3 fixture
```

Expected: all three produce a valid `s4.bin` without errors.

- [ ] **Step 3: Visual smoke test of default build**

User opens default `s4.bin` in Exodus. Confirm via screenshot:
- FG (trees) renders on Plane A as before A.5 (no regression).
- BG (sky+clouds) now renders on Plane B (was black before A.5).
- FWD/BWD teleports work, no transition stutter on default build (T1 = no per-section redraw).

- [ ] **Step 4: Merge feature branch to master**

```bash
git status                          # confirm clean working tree
git log master..HEAD --oneline      # review A.5 commit list
git checkout master
git merge --no-ff -                 # merges previous branch
```

Adjust to the actual branch name if different. Use `--no-ff` for a clear merge commit per project convention.

- [ ] **Step 5: Update memory if any new behaviors learned**

If anything surprised you (e.g., a tier-detection rule that changed mid-implementation, a research finding that contradicted spec assumptions), save a memory entry. Otherwise nothing to add — `project_phase1_complete.md` and `project_milestone_boot.md` patterns can be augmented with a `project_phase2_complete.md` similar in shape.

---

## Self-Review Notes (visible in plan body for transparency)

**Spec coverage check:**
- [x] T1 zone-shared (Tasks 3–6)
- [x] T2 per-section layout (Tasks 7–8)
- [x] T3 per-section layout + own tiles (Tasks 9–10)
- [x] All 3 open spec questions surfaced in Task 1 research
- [x] Build tool extension (Tasks 3, 7, 9)
- [x] Engine Plane B redraw (Task 5, Task 8)
- [x] OJZ ships T1; T2/T3 via fixtures (Task 8, Task 10)
- [x] Visual verification per tier (Tasks 5/6/8/10)
- [x] Build tool round-trip (Tasks 3/7/9 unit tests)
- [x] Out of scope (BG palette swaps, animated tiles, parallax variation) — explicitly excluded; not in any task

**Risk note — Task 1 research outputs may force restructuring of Tasks 3–10.** That's expected and was the user's pattern across A.1–A.4. If research settles a different storage shape (e.g., S4LZ-compressed BG vs raw, or column strips vs full nametable), update Task 3's emission code, Task 5's blit code, and Task 8's redraw code accordingly. The task scaffolding (file boundaries, test points, commit cadence) stays the same; only the byte counts and code shape inside each task changes.

**Type/name consistency check:**
- `act_bg_layout` — Act struct field, longword (used in: Task 2 Step 4, Task 4 Step 2, Task 5 Step 2 "BG_Init")
- `sec_bg_layout` — Sec struct field, longword (used in: Task 2 Step 3, Task 4 Step 3, Task 5 Step 2 "BG_RedrawForSection", Task 8 Step 1)
- `BG_Init` / `BG_RedrawForSection` — engine routines (Task 5 Step 2)
- `emit_zone_bg_layout` / `emit_section_bg_layout` — build tool helpers (Task 3 Step 3, Task 7 Step 3)
- `OJZ_Act1_BG_Layout` (zone) / `OJZ_SecN_BG_Layout` (per-section) — ROM labels
- `OJZ_Act1_T2_Descriptor` / `OJZ_Act1_T3_Descriptor` — fixture descriptor labels
- `--bg-fixture=t2` / `--bg-fixture=t3` — build flags (forwarded as `BG_FIXTURE=2` / `BG_FIXTURE=3` asw defines + `BG_FIXTURE_T2` / `BG_FIXTURE_T3` for ifdef switches)

All consistent.
