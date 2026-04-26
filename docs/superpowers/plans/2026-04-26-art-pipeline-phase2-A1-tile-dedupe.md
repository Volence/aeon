# §2 Phase 2 — Layer A.1: Tile Dedupe + Nametable Remap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OJZ act 1 render its full terrain by globally deduplicating unique tiles (with hflip/vflip canonicalization), rewriting per-section nametable strips to reference the new compact index space, and replacing the test state's raw `QueueDMA_Critical` hack with a real S4LZ → DMA `Level_LoadArt` call.

**Architecture:** A new `tools/tile_dedupe.py` module (with pytest tests) provides the three primitive passes — flip canonicalization, global dedupe, nametable remap. `tools/ojz_strip_gen.py` invokes them after assembling the per-section nametable. The deduped pool is S4LZ-compressed at build time. A new `engine/level/load_art.asm` exposes `LoadArt_S4LZ` (decompress + DMA primitive) and `Level_LoadArt` (act-descriptor-driven orchestrator). The OJZ scroll test calls `Level_LoadArt` instead of hand-rolling DMA.

**Tech Stack:** Python 3 + pytest (build tool), 68000 assembly with the AS Macro Assembler (engine), existing `S4LZ_Decompress` and DMA queue (`QueueDMA_Critical`).

**Spec:** `docs/superpowers/specs/2026-04-26-art-pipeline-phase2-design.md`

**Out of scope (deferred to A.2-A.5 follow-up plans):** Multi-region VRAM packing, graph coloring across sections, Deferrable streaming, per-section background tiers.

---

## File map

**New files:**
- `tools/tile_dedupe.py` — pure-Python tile canonicalization, global dedupe, nametable remap
- `tools/test_tile_dedupe.py` — pytest unit tests
- `engine/level/load_art.asm` — `LoadArt_S4LZ` primitive + `Level_LoadArt` orchestrator
- `docs/research/tile-dedupe-canonicalization.md` — research findings (output of Task 2)

**Modified files:**
- `tools/ojz_strip_gen.py` — calls `tile_dedupe` after building the nametable, replaces today's `OJZ_TILES_COUNT=322` linear export with deduped pool export
- `build.sh` — invokes `s4lz.py compress --tile-delta` on the deduped pool
- `data/levels/ojz/act1/act_descriptor.asm` — `OJZ_Tiles` label now references the S4LZ blob and exposes `OJZ_TILES_VRAM` constant
- `main.asm` — include `engine/level/load_art.asm`
- `engine/level/section.asm` — no logic change; documentation comment that art loading happens before `Section_Init`
- `test/ojz_scroll_test.asm` — replace the two `QueueDMA_Critical` hacks with a single `Level_LoadArt` call
- `ram.asm` — reserve `LoadArt_Work_Buffer` (32 KB transient buffer) at end of work RAM
- `docs/DEFERRED_WORK.md` — close "OJZ Tile Art Loading — Full Terrain Visibility" and tag related items
- `docs/ENGINE_ARCHITECTURE.md` — only if research surfaces something that updates §2.1 or §2.5

---

## Task 0: Create feature branch

**Files:** none (git only)

- [ ] **Step 1: Create and check out the feature branch from master**

Run:
```bash
git checkout master
git pull
git checkout -b feat/s2-a1-tile-dedupe
git status
```

Expected: clean working tree, branch `feat/s2-a1-tile-dedupe` checked out.

---

## Task 1: Research — flip-aware tile dedupe & H/V preservation audit

**Files:**
- Create: `docs/research/tile-dedupe-canonicalization.md`
- Audit: `tools/ojz_strip_gen.py` (read-only — confirms current H/V handling)

**Note for the implementer:** Per the user's stored feedback (`feedback_research_breadth.md`), the targets below are the *starting set*, not a closed checklist. After working through these, spend non-trivial time looking for unlisted relevant material — modern texture-atlas tooling, Genesis homebrew GitHub projects, demoscene techniques. Surface anything strong even if it wasn't pre-enumerated.

- [ ] **Step 1: Read S.C.E.'s art tooling**

```bash
ls /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/build_source/
ls /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Sonic_3___Knuckles__SCE_/Tools/
```

Look for any tile-dedup utility (likely written in Lua or C). Note algorithm and any flip handling.

- [ ] **Step 2: Read SGDK's `rescomp` image converter**

```bash
find / -path '*sgdk*' -name '*.java' 2>/dev/null | head
```

If not present locally, fetch the rescomp source via GitHub: `https://github.com/Stephane-D/SGDK` — read `tools/rescomp/src/sgdk/rescomp/resource/internal/Tile.java` (or equivalent). Note canonicalization rule (lex-smallest of 4 orientations, hash-based, etc.).

- [ ] **Step 3: Read sonic_hack's existing utilities**

```bash
ls /home/volence/sonic_hacks/sonic_hack/scripts/
ls /home/volence/sonic_hacks/sonic_hack/tools/
```

Document any flip-aware tile handling.

- [ ] **Step 4: Web search for additional sources**

Search terms (use WebSearch tool):
- "Sega Genesis tile deduplication flip canonicalization"
- "Mega Drive tilemap optimizer"
- "TexturePacker hflip vflip canonical form"
- "Aseprite tile dedupe algorithm"

Note any patterns that improve on what S.C.E. / SGDK do.

- [ ] **Step 5: Audit `tools/ojz_strip_gen.py` for H/V flag preservation**

Read `chunk_get_tile_word()` (lines ~248-268). The function returns the raw 16-bit nametable word from `blocks[block_id][word_idx]` — it preserves all bits including H/V/priority/palette. This is unchanged through `generate_section_strips()` and `write_strips_to_file()`. Confirm by inspection.

Also read the strip files: pick a tile word with H bit set in the source data and trace it through to the output `.bin` file. (Use `python3 -c` to read a few words from `data/generated/ojz/act1/sec0_strips_a.bin` and verify a non-zero high byte.)

Run:
```bash
python3 -c "
import struct
data = open('data/generated/ojz/act1/sec0_strips_a.bin', 'rb').read()
# print 16 nametable words and decode the flip bits
for i in range(16):
    w = struct.unpack_from('>H', data, i*2)[0]
    h = bool(w & 0x0800); v = bool(w & 0x1000)
    print(f'word {i}: 0x{w:04X} h={h} v={v}')
"
```
Expected: at least one word has h=True or v=True (OJZ uses tile flips heavily).

- [ ] **Step 6: Write research notes**

Write `docs/research/tile-dedupe-canonicalization.md` with:
1. **Sources reviewed** (every source you actually opened, including unlisted ones surfaced in Step 4)
2. **Canonicalization rule** — single sentence specifying our chosen rule (e.g., "lex-smallest of the 4 orientations: identity, H, V, HV"), with one paragraph of justification.
3. **Dedupe algorithm** — single paragraph describing the pass (hash table from canonical-form → tile_id, walk all section tiles, collapse).
4. **Strip remap rule** — single paragraph describing how original H/V bits XOR with the canonicalization rotation to produce the rewritten word's flip bits.
5. **`ojz_strip_gen.py` audit result** — confirms H/V bits are preserved end-to-end OR lists the line that needs to change.
6. **Anything that changes ENGINE_ARCHITECTURE.md** — explicit list, even if empty.

- [ ] **Step 7: Commit research notes**

```bash
git add docs/research/tile-dedupe-canonicalization.md
git commit -m "$(cat <<'EOF'
docs(research): tile dedupe canonicalization for §2 A.1

Findings from S.C.E., SGDK rescomp, sonic_hack utilities, and broader
texture-atlas tooling. Locks the canonical-form rule and confirms
ojz_strip_gen.py preserves H/V flag bits end-to-end.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Apply research findings to architecture doc (if applicable)

**Files:**
- Modify (conditional): `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: Check the research notes for arch-doc-changing items**

Open `docs/research/tile-dedupe-canonicalization.md` and look at item 6 ("Anything that changes ENGINE_ARCHITECTURE.md").

- [ ] **Step 2a: If list is empty**

Skip Step 2b. Move to Task 3.

- [ ] **Step 2b: If list is non-empty**

For each listed change, apply it to the appropriate `## 2.x` subsection in `docs/ENGINE_ARCHITECTURE.md`. Keep the change small and surgical — don't restructure the section.

Commit:
```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(arch): apply A.1 research findings to §2.1"
```

---

## Task 3: Add tile flip helpers to `tools/tile_dedupe.py`

**Files:**
- Create: `tools/tile_dedupe.py`
- Create: `tools/test_tile_dedupe.py`
- Test: `tools/test_tile_dedupe.py::test_hflip_tile`, `::test_vflip_tile`, `::test_hflip_idempotent_pair`

A Genesis tile is 32 bytes = 8 rows × 4 bytes/row, where each byte is two 4-bpp pixels packed (high nibble = left pixel, low nibble = right pixel). H-flip reverses the 4 bytes within a row AND swaps the nibble order in each byte. V-flip reverses the 8 rows.

- [ ] **Step 1: Write the failing test**

Create `tools/test_tile_dedupe.py`:

```python
"""Tests for tile_dedupe — flip canonicalization, dedupe, and strip remap."""
import pytest
from tile_dedupe import hflip_tile, vflip_tile

# Build a sentinel tile where each pixel = row*8 + col so flips are visible.
# Row r byte b (b in 0..3) encodes pixels (r*8 + b*2) and (r*8 + b*2 + 1).
# In the byte, high nibble = left pixel, low nibble = right pixel.
def _make_test_tile():
    out = bytearray(32)
    for r in range(8):
        for b in range(4):
            left  = (r * 8 + b * 2) & 0x0F
            right = (r * 8 + b * 2 + 1) & 0x0F
            out[r * 4 + b] = (left << 4) | right
    return bytes(out)

def test_hflip_tile():
    t = _make_test_tile()
    flipped = hflip_tile(t)
    # After H-flip, row r byte 0 was row r byte 3 with nibbles swapped
    for r in range(8):
        orig_byte_3 = t[r * 4 + 3]
        # H-flip of byte: high nibble <-> low nibble
        expected = ((orig_byte_3 & 0x0F) << 4) | ((orig_byte_3 & 0xF0) >> 4)
        assert flipped[r * 4 + 0] == expected, (
            f"row {r}: expected {expected:02X}, got {flipped[r*4]:02X}"
        )

def test_vflip_tile():
    t = _make_test_tile()
    flipped = vflip_tile(t)
    # After V-flip, row 0 == original row 7
    for r in range(8):
        for b in range(4):
            assert flipped[r * 4 + b] == t[(7 - r) * 4 + b]

def test_hflip_idempotent_pair():
    """H-flipping twice returns the original tile."""
    t = _make_test_tile()
    assert hflip_tile(hflip_tile(t)) == t

def test_vflip_idempotent_pair():
    """V-flipping twice returns the original tile."""
    t = _make_test_tile()
    assert vflip_tile(vflip_tile(t)) == t
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'tile_dedupe'`.

- [ ] **Step 3: Write minimal implementation**

Create `tools/tile_dedupe.py`:

```python
"""Tile canonicalization, global dedupe, and nametable remap for §2 A.1.

A Genesis tile is 32 bytes = 8 rows × 4 bytes/row; each byte holds two
4-bpp pixels (high nibble = left, low nibble = right).

H-flip = reverse the 4 bytes in each row AND swap nibbles within each byte.
V-flip = reverse the 8 rows.
"""

TILE_SIZE = 32
TILE_ROW_BYTES = 4
TILE_ROWS = 8


def hflip_tile(tile: bytes) -> bytes:
    out = bytearray(TILE_SIZE)
    for r in range(TILE_ROWS):
        for b in range(TILE_ROW_BYTES):
            src = tile[r * TILE_ROW_BYTES + (TILE_ROW_BYTES - 1 - b)]
            # Swap nibbles (left pixel <-> right pixel)
            out[r * TILE_ROW_BYTES + b] = ((src & 0x0F) << 4) | ((src & 0xF0) >> 4)
    return bytes(out)


def vflip_tile(tile: bytes) -> bytes:
    out = bytearray(TILE_SIZE)
    for r in range(TILE_ROWS):
        src_row = TILE_ROWS - 1 - r
        out[r * TILE_ROW_BYTES : (r + 1) * TILE_ROW_BYTES] = (
            tile[src_row * TILE_ROW_BYTES : (src_row + 1) * TILE_ROW_BYTES]
        )
    return bytes(out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — hflip/vflip primitives"
```

---

## Task 4: Add canonical-form helper

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py::test_canonical_form_picks_smallest`

The canonical form picks the lexicographically-smallest of the four orientations: identity, H, V, HV. Returns `(canonical_bytes, flip_bits)` where `flip_bits ∈ {0, 1, 2, 3}` encodes which flips produce the canonical from the original (bit 0 = H needed, bit 1 = V needed).

Note: research-driven canonicalization rule. If Task 1's research selected a different rule, use that instead — adjust the test and implementation accordingly.

- [ ] **Step 1: Write the failing test**

Append to `tools/test_tile_dedupe.py`:

```python
from tile_dedupe import canonical_form

def test_canonical_form_picks_smallest():
    """Canonical form returns the lex-smallest of the 4 orientations."""
    t = _make_test_tile()
    h = hflip_tile(t)
    v = vflip_tile(t)
    hv = hflip_tile(v)
    candidates = [t, h, v, hv]
    smallest = min(candidates)
    canon, flip_bits = canonical_form(t)
    assert canon == smallest, "canonical_form must return lex-smallest"
    # Verify flip_bits maps from original to canonical
    test_decoded = t
    if flip_bits & 1: test_decoded = hflip_tile(test_decoded)
    if flip_bits & 2: test_decoded = vflip_tile(test_decoded)
    assert test_decoded == canon


def test_canonical_form_horizontal_partner():
    """An H-flipped tile and its original share the same canonical form."""
    t = _make_test_tile()
    h = hflip_tile(t)
    canon_t, _  = canonical_form(t)
    canon_h, _  = canonical_form(h)
    assert canon_t == canon_h
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 4 pass + 2 fail with `ImportError: cannot import name 'canonical_form'`.

- [ ] **Step 3: Write minimal implementation**

Append to `tools/tile_dedupe.py`:

```python
def canonical_form(tile: bytes) -> tuple[bytes, int]:
    """Return (canonical_bytes, flip_bits).

    Canonical form is the lex-smallest of the 4 orientations:
      flip_bits 0 = identity
      flip_bits 1 = hflip (need to apply H to original to get canonical)
      flip_bits 2 = vflip
      flip_bits 3 = both
    Two tiles that differ only by an H/V/HV flip share the same canonical form.
    """
    h  = hflip_tile(tile)
    v  = vflip_tile(tile)
    hv = hflip_tile(v)
    candidates = [(tile, 0), (h, 1), (v, 2), (hv, 3)]
    candidates.sort(key=lambda c: c[0])
    return candidates[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — canonical_form (lex-smallest of 4 orientations)"
```

---

## Task 5: Add `dedupe_tiles` global pass

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py::test_dedupe_tiles_collapses_flips`

Input: a list of 32-byte tiles (the raw tile-art blob). Output: `(unique_tiles, mapping)` where `unique_tiles` is the list of canonical-form tiles in first-seen order, and `mapping[i] = (canonical_index, flip_bits)` tells how original tile `i` maps to a canonical tile.

- [ ] **Step 1: Write the failing test**

Append to `tools/test_tile_dedupe.py`:

```python
from tile_dedupe import dedupe_tiles

def test_dedupe_tiles_collapses_flips():
    t = _make_test_tile()
    h = hflip_tile(t)
    different = bytes([0xAA] * 32)  # not a flip of t
    inputs = [t, h, t, different]   # tile 0 and 1 are H-flips; tile 2 dup of 0
    unique, mapping = dedupe_tiles(inputs)
    # Two unique canonical forms: canonical(t) and 'different'
    assert len(unique) == 2, f"expected 2 unique tiles, got {len(unique)}"
    # tiles 0, 1, 2 all map to the same canonical index
    assert mapping[0][0] == mapping[1][0] == mapping[2][0]
    # tile 3 maps to the other canonical index
    assert mapping[3][0] != mapping[0][0]
    # tile 0 and tile 1 have flip_bits that differ by exactly 1 (the H bit)
    assert (mapping[0][1] ^ mapping[1][1]) == 1


def test_dedupe_tiles_first_seen_order():
    """Unique tiles must be emitted in first-seen-canonical order."""
    t1 = bytes([0x11] * 32)
    t2 = bytes([0x22] * 32)
    unique, _ = dedupe_tiles([t1, t2, t1])
    assert unique == [t1, t2]  # both are already canonical (palindromic)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 6 pass + 2 fail with `ImportError: cannot import name 'dedupe_tiles'`.

- [ ] **Step 3: Write minimal implementation**

Append to `tools/tile_dedupe.py`:

```python
def dedupe_tiles(tiles: list[bytes]) -> tuple[list[bytes], list[tuple[int, int]]]:
    """Globally dedupe a list of 32-byte tiles using canonical form.

    Returns (unique_tiles, mapping) where:
      unique_tiles[k] is the k-th distinct canonical-form tile, in first-seen order.
      mapping[i] = (canonical_index, flip_bits) for the i-th input tile.
    """
    canonical_to_index: dict[bytes, int] = {}
    unique: list[bytes] = []
    mapping: list[tuple[int, int]] = []
    for t in tiles:
        canon, flip_bits = canonical_form(t)
        idx = canonical_to_index.get(canon)
        if idx is None:
            idx = len(unique)
            canonical_to_index[canon] = idx
            unique.append(canon)
        mapping.append((idx, flip_bits))
    return unique, mapping
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — dedupe_tiles global pass"
```

---

## Task 6: Add nametable strip remap

**Files:**
- Modify: `tools/tile_dedupe.py`
- Modify: `tools/test_tile_dedupe.py::test_remap_nametable_word`

A Genesis nametable word: `priority[15] | palette[14:13] | V[12] | H[11] | tile_index[10:0]`. After dedupe, each original tile maps to `(canonical_index, canon_flip_bits)`. The new nametable word keeps priority+palette unchanged; the new tile_index is `canonical_index`; the new H/V bits are the original H/V XORed with `canon_flip_bits`.

- [ ] **Step 1: Write the failing test**

Append to `tools/test_tile_dedupe.py`:

```python
from tile_dedupe import remap_nametable_word

def test_remap_nametable_word_preserves_priority_palette():
    # priority=1, palette=2, no flips, tile_index=42
    word = (1 << 15) | (2 << 13) | 42
    # Mapping says tile 42 → canonical 7, no flip needed
    new = remap_nametable_word(word, canonical_index=7, canon_flip_bits=0)
    assert (new >> 15) & 1 == 1, "priority preserved"
    assert (new >> 13) & 3 == 2, "palette preserved"
    assert new & 0x7FF == 7, "tile_index = canonical_index"
    assert (new >> 11) & 1 == 0, "H bit unchanged"
    assert (new >> 12) & 1 == 0, "V bit unchanged"


def test_remap_nametable_word_xors_flip_bits():
    # Original word: H=1, V=0, tile_index=42
    word = (1 << 11) | 42
    # Canonicalization needed an additional H flip
    new = remap_nametable_word(word, canonical_index=7, canon_flip_bits=1)
    assert (new >> 11) & 1 == 0, "1 ^ 1 = 0 — H now off"
    assert (new >> 12) & 1 == 0, "V still 0"
    assert new & 0x7FF == 7, "tile_index updated"


def test_remap_nametable_word_double_flip():
    # Original: H=1, V=1, tile=42; canon needs H+V flip
    word = (1 << 12) | (1 << 11) | 42
    new = remap_nametable_word(word, canonical_index=7, canon_flip_bits=3)
    assert (new >> 11) & 1 == 0
    assert (new >> 12) & 1 == 0
    assert new & 0x7FF == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 8 pass + 3 fail with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Append to `tools/tile_dedupe.py`:

```python
NAMETABLE_TILE_MASK = 0x07FF
NAMETABLE_H_BIT     = 0x0800
NAMETABLE_V_BIT     = 0x1000


def remap_nametable_word(word: int, canonical_index: int, canon_flip_bits: int) -> int:
    """Rewrite a 16-bit nametable word for the deduped tile space.

    Preserves priority + palette; replaces tile_index with canonical_index;
    XORs the original H/V bits with canon_flip_bits to recover the original
    visual orientation.
    """
    # Strip old tile_index
    high = word & ~NAMETABLE_TILE_MASK
    # Pull out and toggle H/V via XOR
    if canon_flip_bits & 1:
        high ^= NAMETABLE_H_BIT
    if canon_flip_bits & 2:
        high ^= NAMETABLE_V_BIT
    return high | (canonical_index & NAMETABLE_TILE_MASK)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/tile_dedupe.py tools/test_tile_dedupe.py
git commit -m "feat(tools): tile_dedupe — remap_nametable_word (priority/palette preserved, flip XOR)"
```

---

## Task 7: Add round-trip test

**Files:**
- Modify: `tools/test_tile_dedupe.py::test_round_trip_dedupe_remap`

End-to-end test: a synthetic tile-art blob + nametable rendering should produce identical pixels after dedupe + remap, when expanded back through the canonical inverse.

- [ ] **Step 1: Write the failing test**

Append to `tools/test_tile_dedupe.py`:

```python
def test_round_trip_dedupe_remap():
    """Dedupe + remap a small tile + nametable set, expand back, byte-compare."""
    t1 = _make_test_tile()
    t2 = hflip_tile(t1)              # H-flipped duplicate of t1
    t3 = bytes([0x55] * 32)          # different palindromic tile
    tiles = [t1, t2, t3]
    # Nametable: tile_index 0 (no flip), tile_index 1 (no flip), tile_index 2 (no flip)
    # palette=1, priority=0
    words = [(1 << 13) | i for i in range(3)]

    unique, mapping = dedupe_tiles(tiles)
    new_words = [
        remap_nametable_word(w, mapping[w & NAMETABLE_TILE_MASK][0],
                                mapping[w & NAMETABLE_TILE_MASK][1])
        for w in words
    ]

    # For each remapped word, reconstruct what the VDP would display
    def reconstruct(word: int, pool: list[bytes]) -> bytes:
        idx = word & NAMETABLE_TILE_MASK
        h   = bool(word & NAMETABLE_H_BIT)
        v   = bool(word & NAMETABLE_V_BIT)
        out = pool[idx]
        if h: out = hflip_tile(out)
        if v: out = vflip_tile(out)
        return out

    for original_idx, new_word in enumerate(new_words):
        rebuilt = reconstruct(new_word, unique)
        assert rebuilt == tiles[original_idx], (
            f"round-trip mismatch at tile {original_idx}"
        )
```

- [ ] **Step 2: Run test to verify it passes (should pass — building blocks already work)**

Run:
```bash
cd tools && python3 -m pytest test_tile_dedupe.py -v
```
Expected: 12 passed.

- [ ] **Step 3: Commit**

```bash
git add tools/test_tile_dedupe.py
git commit -m "test(tools): tile_dedupe — end-to-end round-trip"
```

---

## Task 8: Wire dedupe + remap into `tools/ojz_strip_gen.py`

**Files:**
- Modify: `tools/ojz_strip_gen.py`

The existing `generate()` exports a per-section nametable as strips and emits a 322-tile blob (`OJZ_TILES_COUNT * 32 bytes` from stream 0 of OJZ.bin). We replace this with: collect all unique tiles referenced by all sections, dedupe them, write the deduped pool, and rewrite the strip files to reference the new indices.

- [ ] **Step 1: Add tile-collection helper**

Insert near the top of `tools/ojz_strip_gen.py` (after the imports):

```python
import tile_dedupe
```

Add a helper function before `generate()`:

```python
def collect_referenced_tiles(
    all_section_strips: dict,  # sec_id → list[list[int]]
    full_tile_blob: bytes,
) -> tuple[set[int], list[bytes]]:
    """Walk every nametable word across all sections, return (referenced_indices, raw_tile_list).

    raw_tile_list[i] = the 32 bytes of tile index i, for every i in referenced_indices,
                       in ascending index order.
    referenced_indices = set of source tile indices used by any nametable entry.
    """
    referenced: set[int] = set()
    for strips in all_section_strips.values():
        for col in strips:
            for word in col:
                referenced.add(word & tile_dedupe.NAMETABLE_TILE_MASK)
    raw_tiles: list[bytes] = []
    sorted_indices = sorted(referenced)
    for idx in sorted_indices:
        base = idx * tile_dedupe.TILE_SIZE
        if base + tile_dedupe.TILE_SIZE <= len(full_tile_blob):
            raw_tiles.append(full_tile_blob[base : base + tile_dedupe.TILE_SIZE])
        else:
            raw_tiles.append(bytes(tile_dedupe.TILE_SIZE))  # missing → zero tile
    return sorted_indices, raw_tiles
```

- [ ] **Step 2: Decompress the full OJZ tile blob (not just 322 tiles)**

In `generate()`, replace the existing call to `generate_tile_art(...)` with code that decompresses every Kosinski stream in OJZ.bin and concatenates the result.

Find and remove this block in `generate()`:
```python
    # Extract tile art (stream 0 of OJZ.bin, first OJZ_TILES_COUNT tiles)
    tile_out = os.path.join(out_dir, "ojz_tiles.bin")
    generate_tile_art(OJZ_ART_PATH, tile_out, OJZ_TILES_COUNT)
    print(f"Tile art: {OJZ_TILES_COUNT} tiles ({OJZ_TILES_COUNT*32} bytes raw, "
          f"Kosinski source {os.path.getsize(OJZ_ART_PATH)} bytes) -> {tile_out}")
```

Add a new helper above `generate()`:

```python
def decompress_full_ojz_art(path: str) -> bytes:
    """Decompress every Kosinski stream in OJZ.bin and concatenate."""
    src = open(path, "rb").read()
    out = bytearray()
    pos = 0
    while pos < len(src):
        try:
            decoded, pos = kos_decompress(src, pos)
        except (IndexError, KeyError):
            break
        if not decoded:
            break
        out.extend(decoded)
    return bytes(out)
```

- [ ] **Step 3: Replace strip emission with collect + dedupe + remap flow**

Find the loop in `generate()` that processes each section file (the `for sec_path in section_files:` block). Replace it with this two-pass version:

```python
    # ---- Pass 1: build per-section strips, collect into a dict ----
    per_section_strips: dict[str, list[list[int]]] = {}
    for sec_path in section_files:
        sec_name = os.path.basename(sec_path).replace(".bin", "")
        sec_id = sec_name.split("sec")[1]

        layout = load_layout(sec_path)
        if not layout:
            print(f"  WARNING: {sec_name} produced empty layout, skipping")
            continue

        strips = generate_section_strips(layout, chunks, blocks)
        per_section_strips[sec_id] = strips
        print(
            f"  {sec_name}: {len(layout)} rows × {len(layout[0])} chunks "
            f"→ {len(strips)} strips"
        )

    # ---- Pass 2: dedupe across all sections, remap strips ----
    full_blob = decompress_full_ojz_art(OJZ_ART_PATH)
    sorted_indices, raw_tiles = collect_referenced_tiles(per_section_strips, full_blob)
    unique, mapping = tile_dedupe.dedupe_tiles(raw_tiles)

    # Build src_idx -> (canonical_idx, flip_bits) lookup
    src_to_canon: dict[int, tuple[int, int]] = {
        src_idx: mapping[i]
        for i, src_idx in enumerate(sorted_indices)
    }

    # ---- Pass 3: rewrite each section's strips and emit binaries ----
    total_strips = 0
    first_strips = None
    for sec_id, strips in per_section_strips.items():
        remapped_strips = []
        for col in strips:
            remapped_col = []
            for word in col:
                src_idx = word & tile_dedupe.NAMETABLE_TILE_MASK
                if src_idx in src_to_canon:
                    canon_idx, flip_bits = src_to_canon[src_idx]
                    remapped_col.append(
                        tile_dedupe.remap_nametable_word(word, canon_idx, flip_bits)
                    )
                else:
                    remapped_col.append(0)
            remapped_strips.append(remapped_col)

        out_a = os.path.join(out_dir, f"sec{sec_id}_strips_a.bin")
        write_strips_to_file(remapped_strips, out_a)

        out_b = os.path.join(out_dir, f"sec{sec_id}_strips_b.bin")
        with open(out_b, "wb") as f:
            f.write(bytes(len(remapped_strips) * STRIP_TILE_HEIGHT * 2))
        print(f"  sec{sec_id}: emitted {len(remapped_strips)} strips → {out_a}")

        if first_strips is None:
            first_strips = remapped_strips
        total_strips += len(remapped_strips)

    # ---- Emit deduped tile pool ----
    tile_out = os.path.join(out_dir, "ojz_tiles.bin")
    with open(tile_out, "wb") as f:
        for tile in unique:
            f.write(tile)
    raw_referenced = len(sorted_indices)
    deduped = len(unique)
    pct = (1.0 - deduped / raw_referenced) * 100 if raw_referenced else 0.0
    fits = deduped <= 1536
    print(
        f"\nOJZ Act 1 — Phase A.1\n"
        f"  Tile references (post-section walk): {raw_referenced}\n"
        f"  Deduped (with flip canonicalization): {deduped} "
        f"({pct:.1f}% reduction)\n"
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

- [ ] **Step 4: Add an embedded test for the new pipeline**

Append to the existing `run_tests()` function in `ojz_strip_gen.py`:

```python
def test_full_pipeline_runs():
    """Smoke test: full generate() pipeline runs without error and produces deduped output."""
    import tempfile, shutil
    global OUTPUT_DIR
    saved = OUTPUT_DIR
    with tempfile.TemporaryDirectory() as td:
        OUTPUT_DIR = td
        try:
            generate()
            tile_path = os.path.join(td, "ojz_tiles.bin")
            assert os.path.exists(tile_path), "deduped pool not written"
            size = os.path.getsize(tile_path)
            assert size > 0, "deduped pool is empty"
            assert size % 32 == 0, f"pool size {size} not a multiple of 32"
            assert size // 32 <= 1536, f"pool {size//32} exceeds 1536 tiles"
        finally:
            OUTPUT_DIR = saved
    print(f"  [OK] test_full_pipeline_runs: deduped pool produced, fits in 1536 tiles")
```

Then add a call to `test_full_pipeline_runs()` inside the existing `run_tests()` function, after the last existing test call.

- [ ] **Step 5: Run all ojz_strip_gen self-tests**

Run:
```bash
python3 tools/ojz_strip_gen.py test
```
Expected: all tests pass, including the new one. The new test prints the dedupe summary in addition to "[OK]".

- [ ] **Step 6: Run the actual generator and observe output**

Run:
```bash
python3 tools/ojz_strip_gen.py generate
```
Expected: per-section emission lines + the new "OJZ Act 1 — Phase A.1" measurement block. Note the deduped tile count (record it for the final commit message).

- [ ] **Step 7: Commit**

```bash
git add tools/ojz_strip_gen.py
git commit -m "feat(tools): wire tile_dedupe into ojz_strip_gen, emit deduped pool"
```

---

## Task 9: S4LZ-compress the deduped pool at build time

**Files:**
- Modify: `build.sh`

After `ojz_strip_gen.py generate` runs, `data/generated/ojz/act1/ojz_tiles.bin` holds the raw deduped pool. We compress it to `ojz_tiles.s4lz` so the engine consumes the compressed form via S4LZ_Decompress.

- [ ] **Step 1: Locate the strip-generation step in build.sh**

Read `build.sh` and find where `ojz_strip_gen.py` is invoked (or where data generation happens). If it isn't currently invoked, the pipeline expects pre-generated files committed alongside the act descriptor.

Run:
```bash
grep -n 'ojz_strip_gen\|s4lz\|generated' build.sh
```

- [ ] **Step 2a: If `ojz_strip_gen.py` is not invoked from `build.sh`**

Add a generation step. Before the assembler invocation (the `"${TOOLS}/asl"` line), insert:

```bash
echo "Generating OJZ data..."
python3 "${TOOLS}/ojz_strip_gen.py" generate

echo "Compressing OJZ tile pool with S4LZ..."
python3 "${TOOLS}/s4lz.py" compress --tile-delta \
    data/generated/ojz/act1/ojz_tiles.bin \
    data/generated/ojz/act1/ojz_tiles.s4lz
```

- [ ] **Step 2b: If `ojz_strip_gen.py` IS already invoked from `build.sh`**

Add only the S4LZ compression step immediately after that invocation:

```bash
echo "Compressing OJZ tile pool with S4LZ..."
python3 "${TOOLS}/s4lz.py" compress --tile-delta \
    data/generated/ojz/act1/ojz_tiles.bin \
    data/generated/ojz/act1/ojz_tiles.s4lz
```

- [ ] **Step 3: Run the build to confirm both steps execute**

Run:
```bash
./build.sh -nl
```
Expected: build runs the generator, runs the S4LZ compress, then assembles. The compressed file should exist:
```bash
ls -la data/generated/ojz/act1/ojz_tiles.s4lz
```

- [ ] **Step 4: Commit**

```bash
git add build.sh
git commit -m "build: compress deduped OJZ tile pool with S4LZ at build time"
```

---

## Task 10: Reserve `LoadArt_Work_Buffer` in RAM

**Files:**
- Modify: `ram.asm`

A.1 needs a 32 KB transient buffer for S4LZ decompression at level init. Per the spec it's "transient" — only live during `Level_LoadArt`. We still reserve fixed RAM space; the buffer is reusable for any future blocking S4LZ load.

- [ ] **Step 1: Read current RAM layout**

Run:
```bash
cat ram.asm
```
Note where existing reservations end and how much room remains (work RAM is typically `$FF0000-$FFFFFF` = 64 KB total).

- [ ] **Step 2: Add reservation**

Append to `ram.asm` (or insert in the appropriate location matching existing convention — `phase`/`dephase` blocks, `dc.b`/`ds.b` style):

```asm
; -----------------------------------------------
; LoadArt work buffer (§2 A.1)
; Transient — only live during Level_LoadArt; reusable for any blocking
; S4LZ load. Sized for the worst-case zone deduped tile pool (≤32 KB).
; -----------------------------------------------
LoadArt_Work_Buffer:    ds.b    LOADART_WORK_BUFFER_SIZE
```

If `ram.asm` uses `phase`/`dephase`, place the reservation inside the existing block (or open a new one); follow the existing pattern verbatim.

- [ ] **Step 3: Define the buffer-size constant**

In `constants.asm`, add:

```asm
LOADART_WORK_BUFFER_SIZE = 32*1024      ; 32 KB; sized for worst-case deduped zone tile pool
```

- [ ] **Step 4: Build to confirm RAM allocation succeeds**

Run:
```bash
./build.sh -nl
```
Expected: assembly succeeds; no overflow on the work-RAM reservation. If you get an error about RAM overflow, note the symbol name reported and find what to relocate (probably trim an existing transient region).

- [ ] **Step 5: Commit**

```bash
git add ram.asm constants.asm
git commit -m "feat(ram): reserve LoadArt_Work_Buffer (32 KB transient)"
```

---

## Task 11: Implement `LoadArt_S4LZ` and `Level_LoadArt`

**Files:**
- Create: `engine/level/load_art.asm`

`LoadArt_S4LZ` is the primitive: decompress an S4LZ stream into the work buffer, then DMA from the work buffer to VRAM via `QueueDMA_Critical`. The DMA queue's existing 128KB-boundary splitter handles ROM-source crossings; our concern is RAM source (the work buffer) which won't cross 128 KB at 32 KB max.

`Level_LoadArt` is the act-descriptor-driven orchestrator. It reads a single tile-art pointer from the act descriptor and calls `LoadArt_S4LZ`.

- [ ] **Step 1: Write `LoadArt_S4LZ`**

Create `engine/level/load_art.asm`:

```asm
; Level art loader (§2 A.1)
; Blocking S4LZ → DMA pipeline used at level init.
;
; LoadArt_S4LZ — decompress one S4LZ stream into the work buffer and
;                queue a Critical DMA to VRAM.
;
; In:  a0 = source ROM pointer (S4LZ stream, word-aligned)
;      d0.l = VRAM byte destination (tile-slot * 32)
; Out: a0 = past end of compressed data (returned from S4LZ_Decompress)
; Clobbers: d0–d3, a0–a3
;
; Notes:
; - Decompression target is the global LoadArt_Work_Buffer (32 KB transient).
; - For decompressed sizes that exceed one VBlank's DMA budget, the caller
;   is responsible for running with the display blanked off so multiple
;   Critical DMAs can drain across one extended VBlank. A.1's only call
;   site (Level_LoadArt) does this.
; - Asserts in debug builds that uncompressed size ≤ LOADART_WORK_BUFFER_SIZE.
LoadArt_S4LZ:
        movem.l d4-d6/a4, -(sp)
        move.l  d0, d6                              ; d6 = VRAM dest
        movea.l a0, a4                              ; a4 = saved source ptr (for size peek)
        move.w  (a4), d4                            ; d4.w = uncompressed size (BE)

        ; (Optional debug assertion: confirm d4 ≤ LOADART_WORK_BUFFER_SIZE.
        ;  Use whatever assertion macro the project provides — verify against
        ;  debug/debugger.asm. Omitted from this plan to avoid pinning a macro
        ;  name that may not exist yet.)

        lea     (LoadArt_Work_Buffer).w, a1         ; a1 = work buffer
        bsr.w   S4LZ_Decompress                     ; decompress; a0 advances past stream

        ; -- queue DMA: work buffer → VRAM, length = uncompressed size --
        move.l  #LoadArt_Work_Buffer, d1            ; d1 = source (RAM)
        moveq   #0, d2
        move.w  d6, d2                              ; d2.w = VRAM dest (assumes ≤16-bit)
        move.w  d4, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Critical

        ; -- drain the queue this frame (display is off during level init) --
        bsr.w   VSync_Wait

        movem.l (sp)+, d4-d6/a4
        rts
```

- [ ] **Step 2: Write `Level_LoadArt`**

Append to `engine/level/load_art.asm`:

```asm
; Level_LoadArt — load all FG tile art for the act referenced by a0.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d3, a0–a4
;
; A.1 single-region behaviour: act descriptor has ONE compressed tile-art
; pointer (Act_tile_art_s4lz) and ONE VRAM destination (Act_tile_art_vram).
; A.2 will extend this routine to walk a region table.
Level_LoadArt:
        movem.l a0/d0, -(sp)
        move.l  Act_tile_art_s4lz(a0), a0           ; a0 = compressed S4LZ source
        moveq   #0, d0                              ; VRAM byte dest = $0000
        move.l  d0, d0                              ; (placeholder if Act_tile_art_vram added)
        bsr.w   LoadArt_S4LZ
        movem.l (sp)+, a0/d0
        rts
```

(`Act_tile_art_s4lz` and `Act_tile_art_vram` need to be added to the `Act_Desc` struct — see Task 13.)

- [ ] **Step 3: Skip lint until include wired**

`s4lint` is invoked at the project root via `main.asm`. The new file isn't included yet — do a full `./build.sh` once Task 12 wires the include and `Act_tile_art_*` fields exist (Task 13). For this task, just verify the file syntactically by inspection.

- [ ] **Step 4: Commit (file isolated; doesn't yet affect ROM)**

```bash
git add engine/level/load_art.asm
git commit -m "feat(§2): LoadArt_S4LZ + Level_LoadArt routines"
```

---

## Task 12: Include `load_art.asm` in main.asm

**Files:**
- Modify: `main.asm`

- [ ] **Step 1: Find the existing engine/level includes**

Run:
```bash
grep -n 'include.*engine/level' main.asm
```

- [ ] **Step 2: Add the new include**

Insert immediately after the last `engine/level/*.asm` include:

```asm
    include "engine/level/load_art.asm"
```

Order matters only inasmuch as `LoadArt_S4LZ` references `S4LZ_Decompress` (already in `engine/s4lz_decompress.asm`) and `QueueDMA_Critical` (in `engine/dma_queue.asm`). Both are included earlier in `main.asm`, so this works.

- [ ] **Step 3: Build to confirm linkage**

Run:
```bash
./build.sh -nl
```
Expected: assembly succeeds. If a symbol resolution error appears (e.g., `Act_tile_art_s4lz` undefined), it's because Task 13 hasn't run yet — proceed there next, then return.

If the build fails on the missing `Act_tile_art_s4lz` symbol, that's expected; we proceed to Task 13 which adds it.

- [ ] **Step 4: Commit (only if build is clean)**

```bash
git add main.asm
git commit -m "build: include engine/level/load_art.asm"
```

If the build failed because of `Act_tile_art_s4lz`, hold off on commit and continue to Task 13. Then come back and do the build + commit.

---

## Task 13: Extend `Act_Desc` struct with the tile-art pointer

**Files:**
- Modify: `structs.asm`
- Modify: `data/levels/ojz/act1/act_descriptor.asm`

The act descriptor needs a new longword field pointing at the S4LZ-compressed tile pool, plus a word for the VRAM destination tile-slot.

- [ ] **Step 1: Read current Act_Desc struct definition**

Run:
```bash
grep -n -A 20 'Act_Desc:\|Act_sec_grid_ptr\|Act_grid_w' structs.asm
```

Find the `struct`/`endstruct` block (or `equ` chain, depending on style) defining `Act_Desc`.

- [ ] **Step 2: Add fields to the struct**

Inside the `Act_Desc` struct definition, after the existing camera-bounds fields, add:

```asm
Act_tile_art_s4lz    rs.l    1   ; pointer to S4LZ-compressed FG tile pool
Act_tile_art_vram    rs.w    1   ; VRAM byte destination (tile-slot × 32)
                     rs.w    1   ; alignment pad
```

(Match the existing `rs.x` / `equ` style — read what's around it and follow the same pattern.)

- [ ] **Step 3: Add the matching values to `OJZ_Act1_Descriptor`**

In `data/levels/ojz/act1/act_descriptor.asm`, after the `cam_max_y` line in `OJZ_Act1_Descriptor`, add:

```asm
    dc.l    OJZ_Tiles_S4LZ          ; tile_art_s4lz
    dc.w    $0000                   ; tile_art_vram (VRAM byte $0000 = tile slot 0)
    dc.w    0                       ; pad
```

Then ADD a new tile blob declaration at the bottom of the file (do NOT rename or remove the existing `OJZ_Tiles` label yet — that label is still referenced by the test state and removing it now breaks the build before Task 14 fixes the consumer):

Insert immediately after the existing `OJZ_Tiles: BINCLUDE ...` line:

```asm
OJZ_Tiles_S4LZ: BINCLUDE "data/generated/ojz/act1/ojz_tiles.s4lz"
```

The old `OJZ_Tiles` label gets removed in Task 14 once nothing references it.

- [ ] **Step 4: Update Level_LoadArt to read the VRAM dest from the descriptor**

In `engine/level/load_art.asm`, replace the placeholder VRAM-dest logic in `Level_LoadArt`:

Replace:
```asm
        move.l  Act_tile_art_s4lz(a0), a0           ; a0 = compressed S4LZ source
        moveq   #0, d0                              ; VRAM byte dest = $0000
        move.l  d0, d0                              ; (placeholder if Act_tile_art_vram added)
        bsr.w   LoadArt_S4LZ
```

with:
```asm
        moveq   #0, d0
        move.w  Act_tile_art_vram(a0), d0           ; d0.w = VRAM byte dest
        move.l  Act_tile_art_s4lz(a0), a0           ; a0 = compressed S4LZ source
        bsr.w   LoadArt_S4LZ
```

- [ ] **Step 5: Build to confirm**

Run:
```bash
./build.sh -nl
```
Expected: assembly succeeds.

- [ ] **Step 6: Commit (bundle the struct + descriptor + Level_LoadArt fixup)**

```bash
git add structs.asm data/levels/ojz/act1/act_descriptor.asm engine/level/load_art.asm main.asm
git commit -m "feat(§2): Act_Desc gains tile_art_s4lz + tile_art_vram fields"
```

---

## Task 14: Replace the test state's manual DMA with `Level_LoadArt`

**Files:**
- Modify: `test/ojz_scroll_test.asm`

The test currently does its own two-batch `QueueDMA_Critical` of `OJZ_Tiles`. That entire block becomes a single `Level_LoadArt` call.

- [ ] **Step 1: Read the existing init code**

Open `test/ojz_scroll_test.asm`. The hack lives in `GameState_OJZScroll_Init` between the palette copy and the `Camera_Init` call (lines ~28-40 in the file as committed at `086d3bd`).

- [ ] **Step 2: Delete the old DMA block**

Remove these lines:

```asm
; Tile art DMA split: 322 tiles = 10304 bytes > NTSC budget (7200).
; Load in two Critical DMA batches so each fits within one VBlank.
OJZ_TILES_SIZE   = 322 * 32     ; 10304 bytes raw
OJZ_TILES_BATCH1 = 160 * 32     ; 5120 bytes — first batch
OJZ_TILES_BATCH2 = OJZ_TILES_SIZE - OJZ_TILES_BATCH1   ; 5184 bytes — second batch
```

And inside `GameState_OJZScroll_Init`, remove:

```asm
        ; -- DMA tile art: batch 1 (tiles 0-159 → VRAM $0000) --
        move.l  #OJZ_Tiles, d1
        moveq   #0, d2
        move.w  #OJZ_TILES_BATCH1, d3
        jsr     QueueDMA_Critical
        jsr     VSync_Wait

        ; -- DMA tile art: batch 2 (tiles 160-321 → VRAM OJZ_TILES_BATCH1) --
        move.l  #OJZ_Tiles+OJZ_TILES_BATCH1, d1
        move.w  #OJZ_TILES_BATCH1, d2
        move.w  #OJZ_TILES_BATCH2, d3
        jsr     QueueDMA_Critical
        jsr     VSync_Wait
```

- [ ] **Step 3: Insert the `Level_LoadArt` call**

After the palette-copy block (after `move.b #$0F, (Palette_Dirty).w`), insert:

```asm
        ; -- load deduped FG tile pool via S4LZ → VRAM (display still off) --
        lea     OJZ_Act1_Descriptor, a0
        bsr.w   Level_LoadArt
```

The display is still off at this point (the `setVDPReg VDP_Shadow_vdp_mode2, #$64` enabling display-on still runs later, after `Section_Init`).

- [ ] **Step 3b: Remove the now-unused `OJZ_Tiles` label**

In `data/levels/ojz/act1/act_descriptor.asm`, remove the line:

```asm
OJZ_Tiles: BINCLUDE "data/generated/ojz/act1/ojz_tiles.bin"
```

Confirm nothing else references it:

```bash
grep -rn 'OJZ_Tiles\b' --include='*.asm'
```

Expected: only `OJZ_Tiles_S4LZ` matches (the `\b` word boundary excludes the suffix).

- [ ] **Step 4: Build**

Run:
```bash
./build.sh
```
Expected: full build with lint succeeds. Note the `s4.bin` size in the output.

- [ ] **Step 5: Commit**

```bash
git add test/ojz_scroll_test.asm
git commit -m "feat(§2): OJZ scroll test uses Level_LoadArt instead of raw DMA"
```

---

## Task 15: Visual verification — Exodus MCP

**Files:**
- Read-only verification

The user will load the ROM in Exodus. We use the Exodus MCP tools to verify:
1. VRAM at $0000+ contains the deduped tile pool (not zero, not garbage).
2. Plane A nametable references stay below the deduped pool size (no longer reaches indices ≥1536).
3. The visual rendering in section 0 shows the full OJZ terrain (not just sparse sky tiles).

- [ ] **Step 1: Ask the user to load `s4.bin` in Exodus**

Tell the user: "Please load `s4.bin` in Exodus. The OJZ scroll test should auto-start. Take a screenshot when it boots."

- [ ] **Step 2: Verify VRAM via MCP**

Run via the `mcp__exodus__emulator_read_memory` tool:
- Address: `0x000000` (VRAM byte 0)
- Length: `64` bytes (first 2 tiles)
- Verify: bytes are not all-zero (the deduped pool's first tile may be the OJZ sky tile which IS zero — if so, read at offset `64` to see tile 1 instead).

- [ ] **Step 3: Sample a Plane A nametable entry**

Plane A nametable lives at VRAM `$C000`. Read 64 bytes starting there (`mcp__exodus__emulator_read_memory` address `0xC000` length 64) and confirm the tile-index field of each word is `< 1536`.

Decode each word's tile index:
```python
# (run this locally; just for the human-readable check)
for i in range(0, 64, 2):
    w = (data[i] << 8) | data[i+1]
    tile = w & 0x07FF
    h = bool(w & 0x0800)
    v = bool(w & 0x1000)
    print(f"entry {i//2}: 0x{w:04X} tile={tile} h={h} v={v}")
    assert tile < 1536, f"entry {i//2} references tile {tile} ≥ 1536"
```

- [ ] **Step 4: Visual confirmation**

Use `mcp__exodus__emulator_screenshot` to capture the rendered frame. Verify with the user: section 0 shows OJZ terrain rows 32-63 (ground tiles) correctly rendered, no glitched bytes, no broken nametable.

- [ ] **Step 5: Drive camera right via MCP / controller**

Use `mcp__exodus__emulator_write_memory` to set `Ctrl_1_Held` to `$08` (RIGHT) for several frames, or have the user press right. Verify a section transition occurs and the new section's tiles render correctly (still no glitched bytes).

- [ ] **Step 6: Document the verification**

Write a short note in the plan execution log (or a follow-up commit message) describing:
- Deduped tile count from build
- VRAM contents looked correct
- Plane A entries all < 1536
- Section 0 + at least one transition rendered correctly

No commit at this step — verification only.

---

## Task 16: Update `DEFERRED_WORK.md`

**Files:**
- Modify: `docs/DEFERRED_WORK.md`

Two items close with this commit; one item adjusts.

- [ ] **Step 1: Move "OJZ Tile Art Loading — Full Terrain Visibility" to Done**

In `docs/DEFERRED_WORK.md`, under "From §4 Phase 1", find the entry "OJZ Tile Art Loading — Full Terrain Visibility (§4.1 integration test)". Replace it with a strikethrough header pointing into the Done section, matching the pattern of other already-done items (e.g., "~~Scroll / Plane Drawing — Core (§1.3)~~ — DONE 2026-04-25").

Append to the Done section at the bottom:

```markdown
### OJZ Tile Art Loading — Full Terrain Visibility (§4.1 / §2.1) — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.1 (tile dedupe + nametable remap)
**What:** ojz_strip_gen.py now deduplicates tiles globally (with hflip/vflip canonicalization) and rewrites strip files to reference the new compact index space. The deduped pool fits in VRAM $000-$5FF; nametable references stay <1536. Replaced two manual `QueueDMA_Critical` calls in the test state with a single `Level_LoadArt` invocation that reads the act descriptor's tile-art pointer, decompresses S4LZ to a 32 KB transient work buffer, and DMAs to VRAM.
```

- [ ] **Step 2: Mark "Section Preload with S4LZ Deferrable DMA" as still deferred but unblocked downstream**

The S4LZ-blocking-load path is now exercised. The Deferrable streaming path (the actual deferred item) still requires §2 phase 2 layer A.4. No edit needed here — the item stays in the deferred list with its existing "When ready" note.

- [ ] **Step 3: Commit**

```bash
git add docs/DEFERRED_WORK.md
git commit -m "docs: close OJZ Tile Art Loading deferred item (§2 A.1)"
```

---

## Task 17: Update `MEMORY.md`'s "OJZ test visual limit" note

**Files:**
- Modify: `~/.claude/projects/-home-volence-sonic-hacks-s4-engine/memory/project_ojz_test_visual_limit.md` (and the index entry in `MEMORY.md`)

The memory entry says the scroll test only shows sparse tiles. After A.1 it shows full terrain — so this entry needs to either be removed or updated.

- [ ] **Step 1: Read the existing memory entry**

Run:
```bash
cat ~/.claude/projects/-home-volence-sonic-hacks-s4-engine/memory/project_ojz_test_visual_limit.md
```

- [ ] **Step 2: Replace its content with the resolved state**

Overwrite the file with:

```markdown
---
name: OJZ scroll test renders full terrain (resolved)
description: §2 Phase 2 Layer A.1 closed the visibility gap — tile dedupe + nametable remap make all OJZ terrain visible
type: project
---
The scroll test now renders the full OJZ terrain after §2 Phase 2 Layer A.1 (tile dedupe + nametable remap, 2026-04-26). Originally the layout referenced tile indices up to 1856 — collisions with the Plane A nametable at $C000 produced glitched bytes for ~42% of the terrain. The fix flattens + dedupes per-section tiles globally with hflip/vflip canonicalization and rewrites nametable strips to reference the new compact <1536 index space. ojz_strip_gen.py emits the deduped pool; build.sh S4LZ-compresses it; Level_LoadArt blocks on decompress + DMA at level init.

**Why:** Closes the deferred item. Future agents asking "why does OJZ render correctly now" should find this note.

**How to apply:** When working on §4/§2 art-pipeline items, this is the baseline behaviour — the test is no longer artificially limited.
```

(Or, if you prefer, remove the entry entirely and update `MEMORY.md`'s index. Keeping the entry as "resolved" makes the trail of how it was fixed easier to follow.)

Edit `MEMORY.md`'s index line for this entry to reflect the new state:

Find:
```
- [§4 Phase 1 OJZ test visual limit](project_ojz_test_visual_limit.md) — scroll test only shows sparse tiles; full OJZ visuals blocked on §2 tile-graph-coloring (Plane A at \$C000 conflicts with tile indices ≥1536)
```

Replace with:
```
- [OJZ test renders full terrain](project_ojz_test_visual_limit.md) — §2 A.1 (tile dedupe + remap) made the OJZ scroll test render full terrain; previous "sparse tiles" limit closed 2026-04-26
```

- [ ] **Step 3: No commit needed**

Memory files live outside the project repo.

---

## Task 18: Run `s4budget` and confirm no ROM/RAM regressions

**Files:**
- Read-only: `s4.lst`, `s4.bin`

- [ ] **Step 1: Run the budget tool**

Run:
```bash
python3 tools/s4budget.py
```

Expected: budget summary prints, no overflow on RAM or ROM. The 32 KB `LoadArt_Work_Buffer` should appear in the RAM section.

- [ ] **Step 2: Compare ROM size to pre-A.1 baseline**

The S4LZ-compressed tile pool replaces the raw 322-tile blob. Net size impact: deduped pool S4LZ-compressed should be smaller than the raw 322-tile blob (≈10 KB), even before dedupe gains. Note the new ROM size for the merge commit message.

```bash
ls -la s4.bin
```

- [ ] **Step 3: Lint full project**

Run:
```bash
./build.sh
```
Expected: lint pass, no errors.

---

## Task 19: Final merge to master

**Files:** none (git only)

- [ ] **Step 1: Verify clean working tree on the branch**

Run:
```bash
git status
git log --oneline master..HEAD
```

Expected: no uncommitted changes; commit list shows the work from Tasks 0-16.

- [ ] **Step 2: Merge to master**

Per `feedback_git_and_docs` (commit early, merge to master between plans), once everything verifies, merge with `--no-ff` so the merge commit is a clear breadcrumb.

```bash
git checkout master
git merge --no-ff feat/s2-a1-tile-dedupe -m "$(cat <<'EOF'
Merge §2 Phase 2 Layer A.1: tile dedupe + nametable remap

Closes "OJZ Tile Art Loading — Full Terrain Visibility" deferred item.
Foundational layer for the §2 phase 2 milestone. A.2 (multi-region
packing) is the next layer; ENGINE_ARCHITECTURE.md §2 stays the baseline
for its own plan.

EOF
)"
```

- [ ] **Step 3: Verify the merged state builds cleanly**

```bash
./build.sh
```
Expected: clean build on master.

- [ ] **Step 4: Optionally delete the feature branch**

Only after the user confirms they're satisfied with the merge:

```bash
git branch -d feat/s2-a1-tile-dedupe
```

---

## Self-review checklist (the implementer should run this before claiming done)

- [ ] All 12 unit tests in `tools/test_tile_dedupe.py` pass
- [ ] `python3 tools/ojz_strip_gen.py test` passes including the new `test_full_pipeline_runs`
- [ ] `python3 tools/ojz_strip_gen.py generate` prints the "OJZ Act 1 — Phase A.1" measurement block and the deduped pool fits in 1536 tiles
- [ ] `./build.sh` produces `s4.bin` with no errors and no s4lint warnings
- [ ] In Exodus: VRAM $0000+ contains real tile data; Plane A nametable entries all reference tile_index < 1536; section 0 renders OJZ ground terrain (no glitched bytes); a horizontal scroll across one section boundary still renders correctly
- [ ] `docs/DEFERRED_WORK.md` has the "OJZ Tile Art Loading" item moved to Done with today's date
- [ ] No new symbols introduced that shadow existing ones; no SST shape changes; `Load_Object`'s temporary `art_tile` field still works untouched
