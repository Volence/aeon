# §2 Art & Compression Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver S4LZ compression (compressor tool + 68000 decompressor), a random-access tile format (compressor tool + 68000 decompressor), and a basic art loading API — verified end-to-end through the §1 DMA pipeline.

**Architecture:** Four sequential phases. Phase 0 audits the existing DMA queue. Phases 1-2 each follow research → build tool → build 68000 decompressor → test. Phase 3 wraps them with an API and robust tests. Raw art lives in repo; build script compresses before assembly.

**Tech Stack:** Python 3 (build tools), 68000 assembly (decompressors), AS Macro Assembler, existing build pipeline (`build.sh`).

---

## File Structure

**New files to create:**

| File | Purpose |
|------|---------|
| `tools/s4lz.py` | S4LZ compressor / decompressor / verify CLI tool |
| `tools/tilefmt.py` | Random-access tile format compressor / decompressor / verify CLI tool (name may change after Phase 2 research) |
| `engine/s4lz_decompress.asm` | 68000 S4LZ blocking decompressor + tile-delta XOR undo |
| `engine/tile_decompress.asm` | 68000 random-access tile decompressor (single + batch) |
| `engine/art_load.asm` | `LoadArt_S4LZ` and `LoadArt_Tiles` API routines |
| `docs/research/dma-queue-audit.md` | Phase 0 research findings |
| `docs/research/lz-compression-survey.md` | Phase 1 research findings |
| `docs/research/tile-format-survey.md` | Phase 2 research findings |
| `test/sonic_sprites.bin` | Raw Sonic sprite tiles extracted from sonic_hack (for Phase 2 test) |

**Files to modify:**

| File | Changes |
|------|---------|
| `ram.asm` | Add `Decomp_Buffer` (art decompression work buffer) |
| `constants.asm` | Add S4LZ format constants, buffer sizes, new game state ID |
| `macros.asm` | Add any compression-related macros |
| `main.asm` | Include new engine files |
| `build.sh` | Add compression step before assembly |
| `engine/game_loop.asm` | Add compressed art test game states |
| `docs/DEFERRED_WORK.md` | Add §2 deferred items |
| `docs/ENGINE_ARCHITECTURE.md` | Update §2 with implementation notes |

---

## Phase 0: DMA Queue Audit

### Task 1: Research DMA implementations across all references

**Files:**
- Create: `docs/research/dma-queue-audit.md`

This is a research task. The goal is to understand how every reference project handles DMA transfers and whether our implementation is best-in-class.

- [ ] **Step 1: Search S.C.E. for DMA queue implementation**

Search `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/` for DMA-related routines. Look for:
- Queue structure (how entries are stored, how many slots)
- Enqueue mechanism (how transfers are added)
- Drain mechanism (how transfers are executed during VBlank)
- Priority handling (if any)
- 128KB boundary protection

```bash
grep -rn "DMA\|dma\|Process_DMA\|QueueDMA\|DmaQueue" /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/ --include="*.asm" | head -40
```

Document: format, slot count, drain approach, cycle counts.

- [ ] **Step 2: Search Batman & Robin for VDP shadow/DMA approach**

Search `/home/volence/sonic_hacks/The Adventures of Batman and Robin/` for DMA and VDP shadow table routines. Batman uses a VDP shadow table instead of a queue — understand the tradeoffs.

```bash
grep -rn "DMA\|dma\|Shadow\|shadow\|VDP_Write\|VRAM_Copy" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/" --include="*.asm" | head -40
```

Document: how they schedule DMA, when it runs, shadow table flush approach.

- [ ] **Step 3: Search Vectorman for DMA handling**

```bash
grep -rn "DMA\|dma\|VDP\|vdp" /home/volence/sonic_hacks/The\ Adventures\ of\ Batman\ and\ Robin/vectorman_disasm/ --include="*.asm" | head -40
```

Focus on: how they handle DMA with their 64×64 plane setup (same as ours).

- [ ] **Step 4: Search Gunstar Heroes for DMA scheduling**

```bash
grep -rn "DMA\|dma\|VDP\|sprite" /home/volence/sonic_hacks/The\ Adventures\ of\ Batman\ and\ Robin/gunstar_disasm/ --include="*.asm" | head -40
```

Focus on: handling heavy sprite counts, DMA bandwidth management.

- [ ] **Step 5: Search Alien Soldier for DMA optimization**

```bash
grep -rn "DMA\|dma\|VDP\|vdp" /home/volence/sonic_hacks/The\ Adventures\ of\ Batman\ and\ Robin/aliensoldier_disasm/ --include="*.asm" | head -40
```

- [ ] **Step 6: Search Thunder Force IV for multi-layer DMA**

```bash
grep -rn "DMA\|dma\|scroll\|layer" /home/volence/sonic_hacks/The\ Adventures\ of\ Batman\ and\ Robin/thunderforce4_disasm/ --include="*.asm" | head -40
```

Focus on: managing DMA bandwidth across multiple scroll layers.

- [ ] **Step 7: Check sonic_hack's S2-based DMA for comparison**

```bash
grep -rn "Process_DMA\|QueueDMA\|DMA_Queue" /home/volence/sonic_hacks/sonic_hack/ --include="*.asm" | head -20
```

- [ ] **Step 8: Search online sources**

Check for updates and alternatives:
- Flamewing's GitHub repo for Ultra DMA Queue updates
- SGDK's DMA queue implementation (github.com/Stephane-D/SGDK)
- SpritesMind forum threads on DMA optimization
- plutiedev.com DMA timing documentation
- GitHub homebrew projects (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD)

```bash
# Web searches for each source
```

- [ ] **Step 9: Write research findings document**

Create `docs/research/dma-queue-audit.md` with:
- Summary of each reference's approach
- Comparison table (format, slots, drain method, cycle cost, priority support)
- Assessment of our implementation vs findings
- Specific improvements identified (if any)
- Decision on 128KB boundary safety (implement now for §2, or still defer?)

- [ ] **Step 10: Commit research findings**

```bash
git add docs/research/dma-queue-audit.md
git commit -m "docs: Phase 0 DMA queue audit — research findings"
```

### Task 2: Implement DMA queue improvements (if any)

**Files:**
- Modify: `engine/dma_queue.asm` (if changes needed)
- Modify: `constants.asm` (if slot counts change)
- Modify: `ram.asm` (if queue layout changes)

- [ ] **Step 1: Review findings and decide on changes**

Based on `docs/research/dma-queue-audit.md`, decide:
- Are any code changes needed?
- Should 128KB boundary protection be added now?
- Are slot counts correct?

If no changes needed, document "confirmed best-in-class" reasoning in the audit doc and skip to the commit step.

- [ ] **Step 2: Implement changes (if any)**

Apply surgical changes to `engine/dma_queue.asm` and related files. Each change should be small and targeted.

For 128KB boundary protection specifically (likely needed for §2's larger art transfers), add to `QueueDMATransfer`:

```asm
; After calculating source in d1:
; Check if transfer crosses 128KB boundary
; boundary_remaining = $20000 - (source & $1FFFF)
; if length > boundary_remaining: split into two transfers
```

- [ ] **Step 3: Re-verify with existing §1 DMA test**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Load `s4.bin` in emulator. Title screen should display identically to before changes.

- [ ] **Step 4: Commit**

```bash
git add engine/dma_queue.asm constants.asm ram.asm
git commit -m "feat(§2): Phase 0 DMA queue audit — [describe changes or 'confirmed best-in-class']"
```

**CHECKPOINT: Phase 0 complete. Review findings before proceeding to Phase 1.**

---

## Phase 1: S4LZ Compression Pipeline

### Task 3: Research LZ compression formats

**Files:**
- Create: `docs/research/lz-compression-survey.md`

Starting from ENGINE_ARCHITECTURE.md §2.1 baseline. Research validates each design decision.

- [ ] **Step 1: Extract current S4LZ design decisions to validate**

Read `docs/ENGINE_ARCHITECTURE.md` lines 1066-1098. Document the 6 key decisions:
1. Nibble-split token (hi=literal count words, lo=match count words)
2. Word-aligned copies
3. 256-entry jump table dispatch (~2-5KB ROM)
4. 16-bit big-endian offsets (64KB window)
5. Tile-delta XOR preprocessing (10-25% ratio improvement claim)
6. Extension bytes for counts >15

- [ ] **Step 2: Search all 7 references for art loading formats**

For each reference, find how bulk art is loaded:
```bash
# S.C.E. — compression routines
grep -rn "Decomp\|Nemesis\|Kosinski\|Comper\|LZ\|compress\|UFTC" /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/ --include="*.asm" | head -30

# Batman & Robin
grep -rn "Decomp\|compress\|art\|tile\|DMA.*art" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/" --include="*.asm" | head -30

# Repeat for Vectorman, Gunstar, Alien Soldier, Thunder Force IV, sonic_hack
```

Document: what format each uses, any tile-aware preprocessing, decompression speed.

- [ ] **Step 3: Research online LZ formats for 68000**

Search for and analyze:
- **LZ4W (SGDK):** Source at github.com/Stephane-D/SGDK — find the decompressor, understand format
- **Comper:** Community format used in Sonic hacking — find source and benchmarks
- **LZSA / LZSA2:** github.com/emmanuel-marty — designed for 8/16-bit CPUs
- **clownlzss:** github.com/Clownacy/clownlzss — optimal parser library
- **MEGAPACK (Codemasters):** Research tile-delta preprocessing technique
- **SpritesMind / retrodev forums:** Any 68000 LZ benchmarks or comparisons

- [ ] **Step 4: Write research findings with decision validation**

Create `docs/research/lz-compression-survey.md` with:
- Summary of each format analyzed
- Speed and ratio comparisons (where data available)
- Validation of each S4LZ design decision (confirmed, modified, or replaced)
- Final S4LZ format specification (refined from architecture doc if needed)
- Tile-delta preprocessing: confirmed beneficial or not?

- [ ] **Step 5: Update ENGINE_ARCHITECTURE.md if any decisions changed**

If research revealed improvements to the S4LZ format, update §2.1 in `docs/ENGINE_ARCHITECTURE.md`.

- [ ] **Step 6: Commit**

```bash
git add docs/research/lz-compression-survey.md docs/ENGINE_ARCHITECTURE.md
git commit -m "docs: Phase 1 LZ compression research — validate S4LZ design"
```

**CHECKPOINT: Review S4LZ format decisions before building the tool.**

### Task 4: Build S4LZ Python tool — compressor and decompressor

**Files:**
- Create: `tools/s4lz.py`

The tool has three modes: compress, decompress, verify. Core format (from architecture doc, subject to Task 3 adjustments):

```
S4LZ Format:
  Header: [2 bytes BE] decompressed size in bytes (even)
  Sequences (repeated):
    [1 byte] Token — hi nibble: literal_count (words), lo nibble: match_raw
    [1 byte] Literal extension (if literal_count nibble == 15)
    [literal_count * 2 bytes] Literal words
    --- STOP if decompressed_size reached ---
    [2 bytes BE] Match offset in bytes (backwards from current dest)
    [1 byte] Match extension (if match_raw nibble == 15)
    Match length = match_raw + MIN_MATCH (words), MIN_MATCH = 2
```

- [ ] **Step 1: Write basic test — compress and decompress a known byte sequence**

Create `tools/s4lz.py` starting with the test:

```python
#!/usr/bin/env python3
"""S4LZ compressor / decompressor for Sonic 4 Engine.

Usage:
    s4lz.py compress [--tile-delta] <input> <output>
    s4lz.py decompress [--tile-delta] <input> <output>
    s4lz.py verify [--tile-delta] <input>
"""

import struct
import sys
import argparse

MIN_MATCH_WORDS = 2
MAX_LIT_NIBBLE = 14
MAX_MATCH_NIBBLE = 14
TILE_SIZE = 32

def test_roundtrip():
    """Verify compress→decompress round-trip on known data."""
    # 4 tiles of test data (128 bytes) with repeated patterns
    tile_a = bytes(range(32))
    tile_b = bytes(range(32))  # identical to tile_a — should compress well
    tile_c = bytes([0xFF - x for x in range(32)])
    tile_d = bytes(range(32))  # identical to tile_a
    test_data = tile_a + tile_b + tile_c + tile_d

    compressed = compress(test_data)
    decompressed = decompress(compressed)
    assert decompressed == test_data, f"Round-trip failed: got {len(decompressed)} bytes"
    assert len(compressed) < len(test_data), f"Compression made data larger: {len(compressed)} >= {len(test_data)}"
    print(f"PASS: {len(test_data)} -> {len(compressed)} bytes ({len(compressed)/len(test_data):.2%})")

    # Test with tile-delta
    encoded = tile_delta_encode(test_data)
    compressed_td = compress(encoded)
    decoded = tile_delta_decode(decompress(compressed_td))
    assert decoded == test_data, "Tile-delta round-trip failed"
    print(f"PASS tile-delta: {len(test_data)} -> {len(compressed_td)} bytes ({len(compressed_td)/len(test_data):.2%})")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_roundtrip()
        sys.exit(0)
    main()
```

Run to verify it fails (functions not yet defined):
```bash
cd /home/volence/sonic_hacks/aeon && python3 tools/s4lz.py test
```

Expected: `NameError: name 'compress' is not defined`

- [ ] **Step 2: Implement tile-delta encode/decode**

Add to `tools/s4lz.py`:

```python
def tile_delta_encode(data):
    """XOR each 32-byte tile against the previous. First tile unchanged."""
    if len(data) % TILE_SIZE != 0:
        raise ValueError(f"Data size {len(data)} not a multiple of tile size {TILE_SIZE}")
    out = bytearray(data[:TILE_SIZE])
    for i in range(TILE_SIZE, len(data), TILE_SIZE):
        for j in range(TILE_SIZE):
            out.append(data[i + j] ^ data[i - TILE_SIZE + j])
    return bytes(out)

def tile_delta_decode(data):
    """Undo tile-delta: XOR each tile against the previous to reconstruct."""
    if len(data) % TILE_SIZE != 0:
        raise ValueError(f"Data size {len(data)} not a multiple of tile size {TILE_SIZE}")
    out = bytearray(data[:TILE_SIZE])
    for i in range(TILE_SIZE, len(data), TILE_SIZE):
        for j in range(TILE_SIZE):
            out.append(out[i - TILE_SIZE + j] ^ data[i + j])
    return bytes(out)
```

- [ ] **Step 3: Implement match finder**

Add to `tools/s4lz.py`:

```python
def find_best_match(data_words, pos, window_size=32768):
    """Find the longest match at pos within the sliding window.
    Returns (offset_bytes, length_words) or None."""
    n = len(data_words)
    best_len = 0
    best_offset = 0
    max_match = min(n - pos, MAX_MATCH_NIBBLE + MIN_MATCH_WORDS + 255)

    start = max(0, pos - window_size)
    for j in range(pos - 1, start - 1, -1):
        mlen = 0
        while pos + mlen < n and mlen < max_match and data_words[pos + mlen] == data_words[j + mlen]:
            mlen += 1
        if mlen >= MIN_MATCH_WORDS and mlen > best_len:
            best_len = mlen
            best_offset = (pos - j) * 2
            if best_len >= max_match:
                break

    if best_len >= MIN_MATCH_WORDS:
        return (best_offset, best_len)
    return None
```

- [ ] **Step 4: Implement greedy compressor**

```python
def compress(data):
    """Compress raw data to S4LZ format."""
    if len(data) % 2 != 0:
        raise ValueError("Input must be word-aligned (even byte count)")

    data_words = []
    for i in range(0, len(data), 2):
        data_words.append(struct.unpack(">H", data[i:i+2])[0])

    n = len(data_words)
    out = bytearray()
    out += struct.pack(">H", len(data))

    pos = 0
    while pos < n:
        lit_start = pos
        while pos < n and find_best_match(data_words, pos) is None:
            pos += 1
        lit_len = pos - lit_start

        if pos >= n:
            _emit_sequence(out, data_words, lit_start, lit_len, 0, 0, final=True)
            break

        offset, mlen = find_best_match(data_words, pos)
        _emit_sequence(out, data_words, lit_start, lit_len, offset, mlen, final=False)
        pos += mlen

    return bytes(out)

def _emit_sequence(out, data_words, lit_start, lit_len, offset, mlen, final):
    """Emit one token sequence to the output buffer."""
    lit_nibble = min(lit_len, 15)
    if final:
        match_nibble = 0
    else:
        match_raw = mlen - MIN_MATCH_WORDS
        match_nibble = min(match_raw, 15)

    token = (lit_nibble << 4) | match_nibble
    out.append(token)

    if lit_nibble == 15:
        out.append(lit_len - 15)

    for i in range(lit_len):
        out += struct.pack(">H", data_words[lit_start + i])

    if not final:
        out += struct.pack(">H", offset)
        if match_nibble == 15:
            out.append(mlen - MIN_MATCH_WORDS - 15)
```

- [ ] **Step 5: Implement decompressor**

```python
def decompress(data):
    """Decompress S4LZ data to raw bytes."""
    if len(data) < 2:
        raise ValueError("Data too short for S4LZ header")

    decompressed_size = struct.unpack(">H", data[0:2])[0]
    out = bytearray()
    pos = 2

    while len(out) < decompressed_size:
        token = data[pos]; pos += 1
        lit_count = token >> 4
        match_raw = token & 0xF

        if lit_count == 15:
            lit_count += data[pos]; pos += 1

        for _ in range(lit_count):
            out += data[pos:pos+2]; pos += 2

        if len(out) >= decompressed_size:
            break

        offset = struct.unpack(">H", data[pos:pos+2])[0]; pos += 2
        match_len = match_raw + MIN_MATCH_WORDS
        if match_raw == 15:
            match_len += data[pos]; pos += 1

        src = len(out) - offset
        for _ in range(match_len):
            out += out[src:src+2]; src += 2

    return bytes(out[:decompressed_size])
```

- [ ] **Step 6: Implement CLI (main function)**

```python
def main():
    parser = argparse.ArgumentParser(description="S4LZ compressor for Sonic 4 Engine")
    parser.add_argument("mode", choices=["compress", "decompress", "verify"])
    parser.add_argument("input", help="Input file")
    parser.add_argument("output", nargs="?", help="Output file (not needed for verify)")
    parser.add_argument("--tile-delta", action="store_true", help="Apply tile-delta preprocessing")
    args = parser.parse_args()

    with open(args.input, "rb") as f:
        data = f.read()

    if args.mode == "compress":
        if args.tile_delta:
            data = tile_delta_encode(data)
        result = compress(data)
        with open(args.output, "wb") as f:
            f.write(result)
        ratio = len(result) / len(data) if data else 0
        print(f"Compressed: {len(data)} -> {len(result)} bytes ({ratio:.2%})")

    elif args.mode == "decompress":
        result = decompress(data)
        if args.tile_delta:
            result = tile_delta_decode(result)
        with open(args.output, "wb") as f:
            f.write(result)
        print(f"Decompressed: {len(data)} -> {len(result)} bytes")

    elif args.mode == "verify":
        if args.tile_delta:
            encoded = tile_delta_encode(data)
        else:
            encoded = data
        compressed = compress(encoded)
        decompressed = decompress(compressed)
        if args.tile_delta:
            decompressed = tile_delta_decode(decompressed)
        if decompressed == data:
            ratio = len(compressed) / len(data) if data else 0
            print(f"VERIFY OK: {len(data)} -> {len(compressed)} bytes ({ratio:.2%})")
        else:
            print("VERIFY FAILED: data mismatch after round-trip", file=sys.stderr)
            sys.exit(1)
```

- [ ] **Step 7: Run tests**

```bash
cd /home/volence/sonic_hacks/aeon
python3 tools/s4lz.py test
```

Expected: Both tests pass.

- [ ] **Step 8: Commit**

```bash
git add tools/s4lz.py
git commit -m "feat(§2): add S4LZ Python tool — compress, decompress, verify with tile-delta"
```

### Task 5: Compress title screen art and verify PC-side round-trip

**Files:**
- Input: `test/title_art.bin` (existing, 10752 bytes raw)

- [ ] **Step 1: Verify round-trip on real title screen art**

```bash
cd /home/volence/sonic_hacks/aeon
python3 tools/s4lz.py verify --tile-delta test/title_art.bin
```

Expected: `VERIFY OK: 10752 -> XXXX bytes (XX.XX%)`

The ratio should be ≤0.50 (≤5376 bytes) with tile-delta. If not, investigate — the art has 336 tiles (10752/32) of title screen graphics which should compress well due to adjacent tile similarity.

- [ ] **Step 2: Compress for ROM inclusion**

```bash
python3 tools/s4lz.py compress --tile-delta test/title_art.bin test/title_art.s4lz
```

- [ ] **Step 3: Verify the compressed file decompresses correctly**

```bash
python3 tools/s4lz.py decompress --tile-delta test/title_art.s4lz /tmp/title_art_verify.bin
diff test/title_art.bin /tmp/title_art_verify.bin && echo "MATCH" || echo "MISMATCH"
```

Expected: `MATCH`

- [ ] **Step 4: Add compressed art to .gitignore (generated by build)**

Add to `.gitignore`:
```
*.s4lz
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "feat(§2): verify S4LZ round-trip on title screen art"
```

### Task 6: Build 68000 S4LZ decompressor and tile-delta undo

**Files:**
- Create: `engine/s4lz_decompress.asm`

- [ ] **Step 1: Write S4LZ_Decompress routine**

Create `engine/s4lz_decompress.asm`:

```asm
; S4LZ blocking decompressor (§2.1)
; Two-stage nibble dispatch with unrolled copy tables.

; -----------------------------------------------
; S4LZ_Decompress — blocking decompression
; In:  a0 = source (compressed S4LZ data in ROM)
;      a1 = destination (RAM buffer)
; Out: a0 = past end of compressed data
;      a1 = past end of decompressed data
; Clobbers: d0-d3, a2-a3
; -----------------------------------------------
S4LZ_Decompress:
        move.w  (a0)+, d3                      ; d3 = decompressed size (bytes)
        lea     (a1,d3.w), a2                  ; a2 = end of output

.token_loop:
        moveq   #0, d0
        move.b  (a0)+, d0                      ; read token byte
        move.w  d0, d1
        lsr.w   #4, d1                          ; d1 = literal count (high nibble)
        andi.w  #$0F, d0                        ; d0 = match raw (low nibble)

        cmpi.w  #15, d1
        beq.s   .ext_literals
        add.w   d1, d1                          ; *2 for word-sized jumps
        neg.w   d1
        jmp     .lit_end(pc,d1.w)

.ext_literals:
        moveq   #0, d1
        move.b  (a0)+, d1                      ; extension byte
        addi.w  #15, d1                         ; total literal count
        subq.w  #1, d1
.lit_loop:
        move.w  (a0)+, (a1)+
        dbf     d1, .lit_loop
        bra.s   .lit_done

        ; Unrolled literal copies (14 down to 1 word)
        move.w  (a0)+, (a1)+                   ; literal 14
        move.w  (a0)+, (a1)+                   ; literal 13
        move.w  (a0)+, (a1)+                   ; literal 12
        move.w  (a0)+, (a1)+                   ; literal 11
        move.w  (a0)+, (a1)+                   ; literal 10
        move.w  (a0)+, (a1)+                   ; literal 9
        move.w  (a0)+, (a1)+                   ; literal 8
        move.w  (a0)+, (a1)+                   ; literal 7
        move.w  (a0)+, (a1)+                   ; literal 6
        move.w  (a0)+, (a1)+                   ; literal 5
        move.w  (a0)+, (a1)+                   ; literal 4
        move.w  (a0)+, (a1)+                   ; literal 3
        move.w  (a0)+, (a1)+                   ; literal 2
        move.w  (a0)+, (a1)+                   ; literal 1
.lit_end:
        ; literal 0 = no copies, falls through

.lit_done:
        cmpa.l  a2, a1
        bhs.s   .done                          ; reached decompressed size after literals

        ; --- Match ---
        move.w  (a0)+, d2                      ; d2 = match offset (bytes)
        movea.l a1, a3
        suba.w  d2, a3                          ; a3 = match source (dest - offset)

        cmpi.w  #15, d0
        beq.s   .ext_match
        addq.w  #S4LZ_MIN_MATCH, d0            ; d0 = match length (words)
        add.w   d0, d0                          ; *2 for word-sized jumps
        neg.w   d0
        jmp     .match_end(pc,d0.w)

.ext_match:
        moveq   #0, d1
        move.b  (a0)+, d1
        addi.w  #15+S4LZ_MIN_MATCH, d1
        subq.w  #1, d1
.match_loop:
        move.w  (a3)+, (a1)+
        dbf     d1, .match_loop
        bra.s   .token_loop

        ; Unrolled match copies (16 down to 1 word, for MIN_MATCH=2 max normal=16)
        move.w  (a3)+, (a1)+                   ; match 16
        move.w  (a3)+, (a1)+                   ; match 15
        move.w  (a3)+, (a1)+                   ; match 14
        move.w  (a3)+, (a1)+                   ; match 13
        move.w  (a3)+, (a1)+                   ; match 12
        move.w  (a3)+, (a1)+                   ; match 11
        move.w  (a3)+, (a1)+                   ; match 10
        move.w  (a3)+, (a1)+                   ; match 9
        move.w  (a3)+, (a1)+                   ; match 8
        move.w  (a3)+, (a1)+                   ; match 7
        move.w  (a3)+, (a1)+                   ; match 6
        move.w  (a3)+, (a1)+                   ; match 5
        move.w  (a3)+, (a1)+                   ; match 4
        move.w  (a3)+, (a1)+                   ; match 3
        move.w  (a3)+, (a1)+                   ; match 2
        move.w  (a3)+, (a1)+                   ; match 1
.match_end:

        bra.s   .token_loop

.done:
        rts
```

- [ ] **Step 2: Write TileDelta_Undo routine**

Append to `engine/s4lz_decompress.asm`:

```asm
; -----------------------------------------------
; TileDelta_Undo — reverse tile-delta XOR preprocessing
; First 32-byte tile unchanged; each subsequent tile XOR'd
; with the previous reconstructed tile.
; In:  a0 = buffer (decompressed tile data, modified in-place)
;      d0.w = total size in bytes (must be multiple of 32)
; Out: none (buffer modified in-place)
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
TileDelta_Undo:
        sub.w   #TILE_SIZE, d0
        ble.s   .done
        lea     (a0), a1                       ; a1 = previous tile (tile 0)
        lea     TILE_SIZE(a0), a0              ; a0 = current tile (tile 1)
.tile_loop:
        rept 8
        move.l  (a1)+, d1
        eor.l   d1, (a0)+
        endr
        sub.w   #TILE_SIZE, d0
        bgt.s   .tile_loop
.done:
        rts
```

- [ ] **Step 3: Add constants to constants.asm**

Add to `constants.asm`:

```asm
; -----------------------------------------------
; S4LZ compression (§2.1)
; -----------------------------------------------
S4LZ_MIN_MATCH         = 2             ; minimum match length in words
TILE_SIZE               = 32            ; bytes per 8x8 4bpp tile
DECOMP_BUFFER_SIZE      = 32768         ; 32KB decompression work buffer
```

- [ ] **Step 4: Add decompression buffer to ram.asm**

Add to `ram.asm` before `RAM_End:`:

```asm
; -----------------------------------------------
; Decompression buffer (§2)
; -----------------------------------------------
Decomp_Buffer:          ds.b DECOMP_BUFFER_SIZE
Decomp_Buffer_End:
```

- [ ] **Step 5: Include new file in main.asm**

Add to `main.asm` after the `include "engine/game_loop.asm"` line:

```asm
    include "engine/s4lz_decompress.asm"
```

- [ ] **Step 6: Build to verify assembly**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: builds successfully with no errors.

- [ ] **Step 7: Commit**

```bash
git add engine/s4lz_decompress.asm constants.asm ram.asm main.asm
git commit -m "feat(§2): add 68000 S4LZ decompressor + tile-delta undo"
```

### Task 7: Wire up compressed title screen test

**Files:**
- Modify: `build.sh` — add compression step
- Modify: `engine/game_loop.asm` — new test state using compressed art
- Modify: `constants.asm` — new game state ID

- [ ] **Step 1: Update build.sh to compress art before assembly**

Add compression step to `build.sh` after the environment setup and before the assembly step:

```bash
# Compress art assets
echo "Compressing art..."
python3 tools/s4lz.py compress --tile-delta test/title_art.bin test/title_art.s4lz
```

- [ ] **Step 2: Add compressed art test game state**

Add to `constants.asm`:

```asm
GS_S4LZ_TEST            = 2
```

Add to `engine/game_loop.asm` — a new game state that loads compressed art:

```asm
; -----------------------------------------------
; GameState_S4LZTest — §2 compressed art verification
; Decompresses S4LZ title screen art, undoes tile-delta,
; DMAs to VRAM, writes nametable, enables display.
; -----------------------------------------------
GameState_S4LZTest:
        tst.b   (Game_State_Init).w
        bne.s   .update

        move.b  #1, (Game_State_Init).w

        ; Copy palette to buffer line 0
        lea     Test_Palette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #(32/4)-1, d0
.pal_copy:
        move.l  (a0)+, (a1)+
        dbf     d0, .pal_copy
        move.b  #1, (Palette_Dirty).w

        ; Decompress S4LZ art to buffer
        lea     Test_TileArt_S4LZ(pc), a0
        lea     (Decomp_Buffer).w, a1
        bsr.w   S4LZ_Decompress

        ; Undo tile-delta
        lea     (Decomp_Buffer).w, a0
        move.w  #TEST_ART_SIZE, d0
        bsr.w   TileDelta_Undo

        ; Queue DMA from buffer to VRAM
        move.l  #Decomp_Buffer, d1
        move.w  #0, d2
        move.w  #TEST_ART_SIZE, d3
        bsr.w   QueueDMA_Critical

        ; Write nametable (same as uncompressed test)
        stopZ80
        lea     Test_Nametable(pc), a1
        move.l  #vdpComm(VRAM_PLANE_A, VRAM, WRITE), d0
        move.w  #TEST_MAP_WIDTH-1, d1
        move.w  #TEST_MAP_HEIGHT-1, d2
        bsr.w   PlaneMapToVRAM
        startZ80

        ; Enable display
        SetVDPReg VDP_Shadow_vdp_mode2, #$74

.update:
        rts

; -----------------------------------------------
; Compressed test data
; -----------------------------------------------
Test_TileArt_S4LZ:
        binclude "test/title_art.s4lz"
Test_TileArt_S4LZ_End:
        align 2
```

- [ ] **Step 3: Update boot to use compressed test state**

In `engine/boot.asm`, find where `Game_State` is set to the initial state. Change it to use `GameState_S4LZTest`:

Find the line that sets the initial game state (likely `move.l #GameState_DMATest, (Game_State).w`) and change to:

```asm
        move.l  #GameState_S4LZTest, (Game_State).w
```

- [ ] **Step 4: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: compression step runs, then assembly succeeds.

- [ ] **Step 5: Commit**

```bash
git add build.sh engine/game_loop.asm constants.asm engine/boot.asm
git commit -m "feat(§2): add S4LZ compressed title screen test"
```

### Task 8: Verify title screen round-trip in emulator

- [ ] **Step 1: Load ROM in emulator and verify visually**

Load `s4.bin` in the emulator. The title screen should display identically to the §1 uncompressed test — same art, same palette, same nametable layout. Any difference indicates a decompressor bug.

- [ ] **Step 2: Use Exodus MCP to verify VRAM contents**

Use Exodus MCP tools to compare VRAM tile data against the raw uncompressed art. The first N tiles in VRAM should be byte-identical to `test/title_art.bin`.

- [ ] **Step 3: Document results**

If the test passes, note the compressed size and ratio. If it fails, debug using Exodus MCP memory inspection to find where decompression diverges.

- [ ] **Step 4: Commit verification notes**

```bash
git commit --allow-empty -m "verify(§2): S4LZ title screen round-trip confirmed in emulator"
```

**CHECKPOINT: Phase 1 complete. S4LZ compression pipeline working end-to-end. Review before Phase 2.**

---

## Phase 2: Random-Access Tile Format

### Task 9: Research random-access tile formats

**Files:**
- Create: `docs/research/tile-format-survey.md`

Starting from UFTC as baseline candidate. Research validates or replaces it.

- [ ] **Step 1: Study UFTC source and documentation**

```bash
# Search S.C.E. for UFTC integration
grep -rn "UFTC\|uftc\|UncTile\|tilefmt" /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/ --include="*.asm" | head -20
```

Also search online: Sik's mdtools UFTC repo, Flamewing's UFTC implementation.

Document: format spec, compression ratio on sprite art, decompression speed, code size.

- [ ] **Step 2: Search all 7 references for per-frame sprite art loading**

For each reference, find how sprite animation frames are loaded:

```bash
# How does each game handle per-frame sprite art?
grep -rn "DPLC\|DynPLC\|SpriteArt\|LoadArt\|AnimFrame\|ArtLoad" /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/ --include="*.asm" | head -20
# Repeat for other references
```

Document: DPLC approach, pre-decompressed frames, any random-access schemes.

- [ ] **Step 3: Research alternative random-access formats**

Search online for:
- Alternative random-access tile formats in homebrew/SGDK
- Simpler schemes (per-tile RLE, per-tile mini-LZ, full-tile dictionary)
- Different block sizes for dictionary approach (2×2, 2×4, 4×8)
- Amiga demoscene random-access sprite techniques

- [ ] **Step 4: Write research findings**

Create `docs/research/tile-format-survey.md` with:
- UFTC analysis (strengths, weaknesses, ratio, speed)
- Alternatives found and their tradeoffs
- Final format decision (UFTC as-is, modified UFTC, or alternative)
- If UFTC modified: specify changes
- Performance targets confirmed/adjusted

- [ ] **Step 5: Commit**

```bash
git add docs/research/tile-format-survey.md
git commit -m "docs: Phase 2 random-access tile format research"
```

**CHECKPOINT: Review tile format decision before building the tool.**

### Task 10: Build tile format Python tool

**Files:**
- Create: `tools/tilefmt.py`

The exact format depends on Task 9 research findings. This task implements whatever format was chosen. The structure follows the same pattern as `tools/s4lz.py`:

- [ ] **Step 1: Write test and tool skeleton**

Create `tools/tilefmt.py` with:
- Compress: raw sprite sheet → random-access format
- Decompress tile: extract single tile by index
- Decompress batch: extract multiple tiles by index list
- Decompress all: extract entire sheet
- Verify: round-trip check

```python
#!/usr/bin/env python3
"""Random-access tile format compressor/decompressor for Sonic 4 Engine.

Usage:
    tilefmt.py compress <input> <output>
    tilefmt.py decompress <input> <output> [--tiles=0,1,2,...]
    tilefmt.py verify <input>
"""
# Implementation depends on Phase 2 research findings.
# Tool structure follows s4lz.py pattern:
# compress(data) -> compressed
# decompress_tile(data, index) -> 32 bytes
# decompress_batch(data, indices) -> bytes
# decompress_all(data) -> bytes
# verify(data) -> bool
```

- [ ] **Step 2: Implement compressor based on research findings**

Implement the format chosen in Task 9 research. If UFTC: split tiles into 4×4 blocks, build dictionary, store tiles as 4 dictionary indices each. If alternative: implement as specified.

- [ ] **Step 3: Implement decompressor (single tile + batch + all)**

Key requirement: single tile decompression must not touch any other tile's data.

- [ ] **Step 4: Run tests on synthetic data**

```bash
cd /home/volence/sonic_hacks/aeon && python3 tools/tilefmt.py test
```

- [ ] **Step 5: Commit**

```bash
git add tools/tilefmt.py
git commit -m "feat(§2): add random-access tile format Python tool"
```

### Task 11: Extract Sonic sprite art and verify PC-side

**Files:**
- Create: `test/sonic_sprites.bin` (raw tiles extracted from sonic_hack)

- [ ] **Step 1: Find and decompress Sonic sprite art from sonic_hack**

```bash
# Find Sonic's art in sonic_hack
grep -rn "ArtNem_Sonic\|Art_Sonic\|SonicArt" /home/volence/sonic_hacks/sonic_hack/ --include="*.asm" | head -10

# Decompress using nemdec tool
# Exact path depends on grep results
/home/volence/sonic_hacks/sonic_hack/tools/nemdec <input_path> test/sonic_sprites.bin
```

- [ ] **Step 2: Verify round-trip with tile format tool**

```bash
python3 tools/tilefmt.py verify test/sonic_sprites.bin
```

Expected: `VERIFY OK` with compression ratio ≤0.55.

- [ ] **Step 3: Compress for ROM inclusion**

```bash
python3 tools/tilefmt.py compress test/sonic_sprites.bin test/sonic_sprites.tf
```

- [ ] **Step 4: Test single-tile and batch decompression**

```bash
# Decompress tiles 0-7 (a single sprite frame)
python3 tools/tilefmt.py decompress test/sonic_sprites.tf /tmp/frame_tiles.bin --tiles=0,1,2,3,4,5,6,7

# Compare against the same tiles from the raw file
python3 -c "
raw = open('test/sonic_sprites.bin','rb').read()
dec = open('/tmp/frame_tiles.bin','rb').read()
expected = raw[:8*32]
assert dec == expected, 'Tile mismatch'
print('Single-tile extraction: PASS')
"
```

- [ ] **Step 5: Update .gitignore and commit**

Add `*.tf` to `.gitignore`:

```bash
git add test/sonic_sprites.bin .gitignore
git commit -m "feat(§2): extract Sonic sprites, verify tile format round-trip"
```

### Task 12: Build 68000 tile format decompressor

**Files:**
- Create: `engine/tile_decompress.asm`

Implementation depends on Task 9 research. Provides two entry points:

- [ ] **Step 1: Write decompressor routines**

Create `engine/tile_decompress.asm`. The exact implementation depends on the chosen format. If UFTC, the structure is:

```asm
; Random-access tile decompressor (§2.1)

; -----------------------------------------------
; DecompTile_Single — decompress one tile by index
; In:  a0 = compressed tile data (ROM)
;      a1 = destination buffer (32 bytes written)
;      d0.w = tile index
; Out: a1 = past end of written data (+32)
; Clobbers: d0-d2, a2-a3
; -----------------------------------------------
DecompTile_Single:
        ; Implementation depends on format from Task 9 research
        ; For UFTC: read tile's 4 dictionary indices, copy 4 blocks (8 bytes each)
        rts

; -----------------------------------------------
; DecompTile_Batch — decompress multiple tiles by index
; In:  a0 = compressed tile data (ROM)
;      a1 = destination buffer
;      a2 = tile index list (word-sized indices, -1 terminated)
; Out: a1 = past end of written data
; Clobbers: d0-d2, a2-a3
; -----------------------------------------------
DecompTile_Batch:
.loop:
        move.w  (a2)+, d0
        bmi.s   .done
        bsr.s   DecompTile_Single
        bra.s   .loop
.done:
        rts
```

- [ ] **Step 2: Include in main.asm**

Add after the S4LZ include:

```asm
    include "engine/tile_decompress.asm"
```

- [ ] **Step 3: Build to verify assembly**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

- [ ] **Step 4: Commit**

```bash
git add engine/tile_decompress.asm main.asm
git commit -m "feat(§2): add 68000 random-access tile decompressor"
```

### Task 13: Sprite display test in emulator

**Files:**
- Modify: `build.sh` — add tile format compression step
- Modify: `engine/game_loop.asm` — add sprite display test state
- Modify: `constants.asm` ��� new game state ID

- [ ] **Step 1: Update build.sh to compress sprite art**

Add after the S4LZ compression line:

```bash
python3 tools/tilefmt.py compress test/sonic_sprites.bin test/sonic_sprites.tf
```

- [ ] **Step 2: Add sprite test game state**

Add to `constants.asm`:
```asm
GS_SPRITE_TEST          = 3
```

Add to `engine/game_loop.asm`:

```asm
; -----------------------------------------------
; GameState_SpriteTest — §2 random-access tile verification
; Decompresses specific sprite tiles, DMAs to VRAM,
; sets up sprite table entries, enables display.
; -----------------------------------------------
GameState_SpriteTest:
        tst.b   (Game_State_Init).w
        bne.s   .update

        move.b  #1, (Game_State_Init).w

        ; Decompress tiles 0-7 (one sprite frame) to buffer
        lea     Test_SpriteTiles(pc), a0
        lea     (Decomp_Buffer).w, a1
        lea     .tile_list(pc), a2
        bsr.w   DecompTile_Batch

        ; Queue DMA: buffer -> VRAM tile 0
        move.l  #Decomp_Buffer, d1
        move.w  #0, d2
        move.w  #8*TILE_SIZE, d3                ; 8 tiles = 256 bytes
        bsr.w   QueueDMA_Critical

        ; Set up a sprite entry to display the tiles
        lea     (Sprite_Table_Buffer).w, a0
        move.w  #112, (a0)+                    ; Y position (center-ish)
        move.b  #sprSize(4,2)>>8, (a0)+        ; 4 wide x 2 tall
        move.b  #0, (a0)+                      ; link = 0 (end)
        move.w  #vram_art(0,0,0), (a0)+        ; tile 0, palette 0
        move.w  #160, (a0)+                    ; X position (center-ish)
        move.b  #1, (Sprite_Table_Dirty).w

        ; Load palette
        lea     Test_Palette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #(32/4)-1, d0
.pal_copy:
        move.l  (a0)+, (a1)+
        dbf     d0, .pal_copy
        move.b  #1, (Palette_Dirty).w

        SetVDPReg VDP_Shadow_vdp_mode2, #$74

.update:
        rts

.tile_list:
        dc.w    0, 1, 2, 3, 4, 5, 6, 7, -1

Test_SpriteTiles:
        binclude "test/sonic_sprites.tf"
Test_SpriteTiles_End:
        align 2
```

- [ ] **Step 3: Point boot to sprite test state**

Change boot to use `GameState_SpriteTest`:

```asm
        move.l  #GameState_SpriteTest, (Game_State).w
```

- [ ] **Step 4: Build and test in emulator**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Load in emulator. A sprite composed of tiles 0-7 from Sonic's sprite sheet should appear on screen. Verify visually against the original art.

- [ ] **Step 5: Commit**

```bash
git add build.sh engine/game_loop.asm constants.asm engine/boot.asm
git commit -m "feat(§2): add sprite tile format display test"
```

**CHECKPOINT: Phase 2 complete. Both compression formats working. Review before Phase 3.**

---

## Phase 3: Basic Art Loading API + Robust Test

### Task 14: Implement LoadArt_S4LZ and LoadArt_Tiles

**Files:**
- Create: `engine/art_load.asm`

- [ ] **Step 1: Write LoadArt_S4LZ**

Create `engine/art_load.asm`:

```asm
; Art loading API (§2)
; Thin wrappers connecting decompressors to DMA pipeline.

; -----------------------------------------------
; LoadArt_S4LZ — decompress S4LZ art and queue DMA to VRAM
; In:  a0 = source (compressed S4LZ data in ROM, tile-delta encoded)
;      d0.w = VRAM destination (byte address)
;      d1.w = decompressed size (bytes, for tile-delta undo)
; Out: none
; Clobbers: d0-d4, a0-a3
; -----------------------------------------------
LoadArt_S4LZ:
        move.w  d0, d4                         ; save VRAM dest
        move.w  d1, -(sp)                      ; save decompressed size

        ; Decompress to buffer
        lea     (Decomp_Buffer).w, a1
        bsr.w   S4LZ_Decompress

        ; Tile-delta undo
        lea     (Decomp_Buffer).w, a0
        move.w  (sp)+, d0                      ; restore size
        bsr.w   TileDelta_Undo

        ; Queue DMA to VRAM
        move.l  #Decomp_Buffer, d1             ; source
        move.w  d4, d2                         ; VRAM dest
        move.w  (Decomp_Buffer-2).w, d3        ; size from S4LZ header (2 bytes before buffer? no...)
        ; Actually, use the size we saved
        ; Let's restructure to keep size available

        rts
```

Wait — we need the decompressed size for the DMA. The S4LZ header contains it but we've already consumed it. Better approach: read the size from the S4LZ header first, then decompress, then DMA.

Revised:

```asm
; -----------------------------------------------
; LoadArt_S4LZ — decompress S4LZ art and queue DMA to VRAM
; In:  a0 = source (compressed S4LZ data in ROM, tile-delta encoded)
;      d0.w = VRAM destination (byte address)
; Out: none
; Clobbers: d0-d4, a0-a3
; -----------------------------------------------
LoadArt_S4LZ:
        move.w  d0, -(sp)                     ; save VRAM dest
        move.w  (a0), d4                       ; d4 = decompressed size from S4LZ header (preserved)

        ; Decompress to buffer
        lea     (Decomp_Buffer).w, a1
        bsr.w   S4LZ_Decompress

        ; Tile-delta undo
        lea     (Decomp_Buffer).w, a0
        move.w  d4, d0
        bsr.w   TileDelta_Undo

        ; Queue DMA: Decomp_Buffer -> VRAM
        move.l  #Decomp_Buffer, d1
        move.w  (sp)+, d2                      ; restore VRAM dest
        move.w  d4, d3                         ; decompressed size
        bsr.w   QueueDMA_Critical
        rts

; -----------------------------------------------
; LoadArt_Tiles — decompress tile-format tiles and queue DMA to VRAM
; In:  a0 = source (compressed tile data in ROM)
;      a2 = tile index list (word-sized, -1 terminated)
;      d0.w = VRAM destination (byte address)
; Out: none
; Clobbers: d0-d3, a0-a3
; -----------------------------------------------
LoadArt_Tiles:
        move.w  d0, d4                         ; save VRAM dest

        ; Count tiles in list (for DMA size)
        movea.l a2, a3
        moveq   #0, d3
.count:
        move.w  (a3)+, d0
        bmi.s   .count_done
        addq.w  #1, d3
        bra.s   .count
.count_done:
        lsl.w   #5, d3                         ; d3 = tile_count * 32 = byte size

        ; Decompress tiles to buffer
        lea     (Decomp_Buffer).w, a1
        bsr.w   DecompTile_Batch

        ; Queue DMA: Decomp_Buffer -> VRAM
        move.l  #Decomp_Buffer, d1
        move.w  d4, d2
        ; d3 = total bytes
        bsr.w   QueueDMA_Critical
        rts
```

- [ ] **Step 2: Include in main.asm**

Add after tile_decompress include:

```asm
    include "engine/art_load.asm"
```

- [ ] **Step 3: Build to verify assembly**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

- [ ] **Step 4: Commit**

```bash
git add engine/art_load.asm main.asm
git commit -m "feat(§2): add LoadArt_S4LZ and LoadArt_Tiles API"
```

### Task 15: Robust test suite

**Files:**
- Modify: `engine/game_loop.asm` — comprehensive test state
- Create: test art files (extracted from sonic_hack/S.C.E.)

- [ ] **Step 1: Extract additional test art from sonic_hack**

Extract zone tile art and small object art:

```bash
# Find zone art (Kosinski-compressed level tiles)
grep -rn "ArtKos_\|KosArt_\|LevelArt" /home/volence/sonic_hacks/sonic_hack/ --include="*.asm" | head -10

# Decompress a zone's tiles using kosdec
/home/volence/sonic_hacks/sonic_hack/tools/kosdec <zone_art_path> test/zone_tiles.bin

# Find small object art (ring, monitor)
grep -rn "ArtNem_Ring\|Art_Ring" /home/volence/sonic_hacks/sonic_hack/ --include="*.asm" | head -5
/home/volence/sonic_hacks/sonic_hack/tools/nemdec <ring_art_path> test/ring_art.bin
```

- [ ] **Step 2: Compress all test art in build.sh**

Update `build.sh`:

```bash
echo "Compressing art..."
python3 tools/s4lz.py compress --tile-delta test/title_art.bin test/title_art.s4lz
python3 tools/s4lz.py compress --tile-delta test/zone_tiles.bin test/zone_tiles.s4lz
python3 tools/s4lz.py compress --tile-delta test/ring_art.bin test/ring_art.s4lz
python3 tools/tilefmt.py compress test/sonic_sprites.bin test/sonic_sprites.tf
```

- [ ] **Step 3: Add comprehensive test game state**

Add to `constants.asm`:
```asm
GS_ROBUST_TEST          = 4
```

Add to `engine/game_loop.asm` — a test state that loads all art types through the API:

```asm
; -----------------------------------------------
; GameState_RobustTest — §2 full pipeline verification
; Loads: title screen (S4LZ), zone tiles (S4LZ large),
;        ring art (S4LZ small), sprite tiles (tile format).
; All through LoadArt API -> DMA pipeline -> VRAM.
; -----------------------------------------------
GameState_RobustTest:
        tst.b   (Game_State_Init).w
        bne.s   .update

        move.b  #1, (Game_State_Init).w

        ; Load palette
        lea     Test_Palette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #(32/4)-1, d0
.pal_copy:
        move.l  (a0)+, (a1)+
        dbf     d0, .pal_copy
        move.b  #1, (Palette_Dirty).w

        ; Test 1: Title screen via LoadArt_S4LZ
        lea     Test_TileArt_S4LZ(pc), a0
        move.w  #0, d0                         ; VRAM $0000
        bsr.w   LoadArt_S4LZ

        ; Test 2: Small object art via LoadArt_S4LZ
        lea     RobustTest_RingArt(pc), a0
        move.w  #vram_bytes(400), d0            ; VRAM tile 400
        bsr.w   LoadArt_S4LZ

        ; Test 3: Sprite tiles via LoadArt_Tiles
        lea     Test_SpriteTiles(pc), a0
        lea     .sprite_tiles(pc), a2
        move.w  #vram_bytes(500), d0            ; VRAM tile 500
        bsr.w   LoadArt_Tiles

        ; Write nametable for title screen
        stopZ80
        lea     Test_Nametable(pc), a1
        move.l  #vdpComm(VRAM_PLANE_A, VRAM, WRITE), d0
        move.w  #TEST_MAP_WIDTH-1, d1
        move.w  #TEST_MAP_HEIGHT-1, d2
        bsr.w   PlaneMapToVRAM
        startZ80

        ; Set up sprite for tile-format art
        lea     (Sprite_Table_Buffer).w, a0
        move.w  #112, (a0)+
        move.b  #sprSize(4,2)>>8, (a0)+
        move.b  #0, (a0)+
        move.w  #vram_art(500,0,0), (a0)+
        move.w  #20, (a0)+
        move.b  #1, (Sprite_Table_Dirty).w

        SetVDPReg VDP_Shadow_vdp_mode2, #$74

.update:
        rts

.sprite_tiles:
        dc.w    0, 1, 2, 3, 4, 5, 6, 7, -1

RobustTest_RingArt:
        binclude "test/ring_art.s4lz"
        align 2

RobustTest_ZoneTiles:
        binclude "test/zone_tiles.s4lz"
        align 2
```

- [ ] **Step 4: Build and test**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Load in emulator. Verify:
- Title screen art visible in background plane (S4LZ large load)
- Sprite visible on screen (tile format load)
- No visual corruption
- Use Exodus MCP to verify VRAM at tile 400 contains ring art

- [ ] **Step 5: Commit**

```bash
git add build.sh engine/game_loop.asm constants.asm test/zone_tiles.bin test/ring_art.bin engine/boot.asm
git commit -m "feat(§2): robust test — multiple art formats through full pipeline"
```

### Task 16: Update deferred work and architecture docs

**Files:**
- Modify: `docs/DEFERRED_WORK.md`
- Modify: `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: Add §2 deferred items to DEFERRED_WORK.md**

Add after the existing §1 section:

```markdown
## From §2 — Art & Compression Pipeline

### Dynamic VRAM Allocator (§2.2)
**Blocked by:** §3 Object System (`Load_Object` spawn/destroy lifecycle drives `AllocVRAM`/`FreeVRAM` calls)
**What:** Bump allocator for unified VRAM pool, loaded table tracking, refcount per type_id, lazy reclaim, section compaction.
**When ready:** After §3 defines object RAM layout and the object loop exists.

### Refcount-based Art Caching / Lazy Reclaim (§2.2)
**Blocked by:** §3 Object System (refcount increments/decrements tied to object spawn/destroy)
**What:** Freed art stays in VRAM until pool needs space. Re-spawn of same type is free (refcount bump, no decompression).
**When ready:** After §3 and the dynamic VRAM allocator exist.

### Build-time Graph Coloring (§2.3)
**Blocked by:** §4 Level/World (section adjacency graph) + §8 Build Tools (tile deduplication pipeline)
**What:** Non-adjacent sections share VRAM tile indices. Build tool computes coloring from section adjacency graph.
**When ready:** After §4 defines section grid and §8 has flatten/deduplicate pipeline.

### Section-aware Streaming / Predictive Preloading (§2.1/§4.8)
**Blocked by:** §4 Level/World (section transition triggers, camera position, leapfrog loading)
**What:** Deferrable-priority DMA streaming of next section's art based on camera velocity and direction.
**When ready:** After §4 implements section transitions and camera system.

### S4LZ Streaming Mode (§2.1)
**Blocked by:** §9.7 Cooperative Multitasking (interruptible decompression with VBlank context switch)
**What:** Bookmark-based interruptible decompression. VBlank preempts mid-decompress, resumes next frame.
**When ready:** After §9.7 supervisor/user mode exists. Blocking mode handles all current use cases.
```

- [ ] **Step 2: Update ENGINE_ARCHITECTURE.md §2 with implementation notes**

Add implementation notes to §2.1 documenting:
- Final S4LZ format specification (confirmed or adjusted by research)
- Final tile format choice (UFTC, modified UFTC, or alternative)
- Actual compression ratios achieved on test data
- Decompression speed measurements (if benchmarked)
- Any deviations from original design

- [ ] **Step 3: Commit**

```bash
git add docs/DEFERRED_WORK.md docs/ENGINE_ARCHITECTURE.md
git commit -m "docs: update §2 deferred work and architecture notes"
```

- [ ] **Step 4: Restore boot to point to final test state**

Ensure `engine/boot.asm` points to `GameState_RobustTest` (or whichever state we want as the default verification).

- [ ] **Step 5: Final build and verification**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Load in emulator one final time. Everything should work.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: §2 Art & Compression Pipeline — S4LZ, tile format, art loading API, verification tests"
```

**CHECKPOINT: Phase 3 complete. §2 implementation done. Ready for merge to master.**
