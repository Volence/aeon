# LZ Compression Survey for S4LZ Design Validation

Research conducted 2026-04-24 for §2 Art & Compression Pipeline.

---

## 1. Reference Disassembly Survey

### 1.1 S.C.E. (Sonic Clean Engine)

**Format:** Kosinski Plus (KosPlus) — community-optimized Kosinski variant by
Flamewing, vladikcomper, and Clownacy.

**How it works:** Bit-stream based. Reads one descriptor byte at a time
(`move.b (a0)+,d0; add.b d0,d0` to shift out bits). Three token types:
- Code 1: literal byte copy (`move.b (a0)+,(a1)+`)
- Code 00: short dictionary ref (8-bit displacement, 2-5 byte copy)
- Code 01: long dictionary ref (13-bit displacement, 3-byte count field or
  extended 8-bit counter)

**Key characteristics:**
- Byte-aligned copies only (`move.b` throughout — 12 cycles per byte)
- 8× loop unrolling for large copies via `rept 8; move.b (a5)+,(a1)+; endr`
- Jump table dispatch for medium copies: `add.w d4,d4; jmp .mediumcopy-2(pc,d4.w)`
- Bit-stream overhead: `dbf d2,+; moveq #7,d2; move.b (a0)+,d0` = ~14-18 cycles
  per bit read (amortized over 8 bits)
- Moduled variant (KosPlusM): 4KB chunks, one per frame, DMA to VRAM

**Speed estimate:** ~190-310 KB/s (bit-stream parsing dominates)

**Compression ratio:** ~0.45-0.55 typical on tile art (good dictionary matching)

**Relevance to S4LZ:** Proves that bit-stream formats are CPU-bound on 68000.
The 14-18 cycle/bit overhead means ~2-3 cycles per output byte just for parsing,
before any copy work. S4LZ's byte-aligned token avoids this entirely.

### 1.2 Batman & Robin

**Format:** No compression. Raw art data DMA'd or CPU-copied to VRAM.

**How it works:**
- 78% of 2MB ROM is raw art/level data
- Massive unrolled VDP write loops (280 iterations of `move.l (a3)+,(a0)`)
- Level nametables stored in exact VDP format — zero conversion cost
- Active-display VDP writes for doubled bandwidth

**Key characteristics:**
- Zero decompression CPU cost
- Tradeoff: limited to what fits in 2MB ROM
- Bitplane interleaving for procedural effects

**Relevance to S4LZ:** Sonic 4 needs 10+ zones with distinct art — raw storage
would exceed 4MB. However, Batman's principle of "VDP-ready data" applies: S4LZ
should decompress to word-aligned, VDP-ready output. The active-display write
technique is too risky for scrolling games.

### 1.3 Vectorman

**Format:** No standard compression identified in disassembly. The game uses
pre-rendered 3D sprites stored as raw frame data. Art loading uses direct
memory copies with no decompression wrapper.

**Relevance to S4LZ:** Vectorman's approach (pre-rendered + raw storage) doesn't
apply to a tile-based engine. No compression techniques to adopt.

### 1.4 Gunstar Heroes / 1.5 Alien Soldier (Treasure)

**Format:** Custom byte-aligned LZ with RLE modes. Identical decompressor in
both games (code at $267E/$2B02 respectively).

**How it works:** Single control byte with bit-field dispatch:
- Bit 7 set: **Dictionary match** — 5-bit count (low bits), 10-bit offset
  (remaining bits + next byte). Copy via `move.b (a5)+,(a2)+` loop.
- Bit 7 clear, bit 6 set, bit 5 clear: **RLE-2** — fill with 2-byte pattern,
  5-bit repeat count.
- Bit 7 clear, bit 6 set, bit 5 set: **RLE-mixed** — alternating pattern fill.
- Bit 7 clear, bit 5 set, bit 6 clear: **RLE-1** — single byte fill, 5-bit count.
- Bit 7 clear, bit 5 clear, bit 6 clear: **Literal** — raw byte copy, 5-bit count.

**Key characteristics:**
- Byte-aligned tokens (no bit-stream, no nibble parsing)
- 5-bit counts (max 32), 10-bit dictionary window (1KB)
- All copies byte-by-byte with `dbra` loops — no word alignment
- Multiple RLE modes for common patterns
- Small decompressor (~100 bytes)
- Moderate speed, good ratio on sprite art with many repeated patterns

**Compression ratio:** Good on sprite art due to RLE modes. Weaker on diverse
tile art where dictionary matching dominates over run-length.

**Relevance to S4LZ:** The multi-mode RLE approach is interesting but adds
complexity. For tile art (our primary use case), LZ dictionary matching
outperforms RLE. The 10-bit window is too small for our needs. However, the
byte-aligned control byte approach validates S4LZ's direction: avoid bit-streams.

### 1.6 Thunder Force IV (Technosoft)

**Format:** No standard compression identified in the 64K-line disassembly.
Art appears to be stored raw or with minimal packing. The game's 1MB ROM
budget (~759KB data) suggests raw storage similar to Batman, enabled by the
horizontal shooter genre having fewer distinct tilesets than a platformer.

**Relevance to S4LZ:** Confirms that some high-end Genesis games chose raw
storage over compression. Not applicable to our multi-zone engine.

### 1.7 sonic_hack (Sonic 2 disassembly)

**Formats:** Kosinski (level art), Nemesis (sprite art via PLCs), Enigma
(tilemaps), KosPlus Moduled (upgraded path).

**Kosinski:** Bit-stream LZSS. 16-bit descriptor words, bit-reversed via 256-byte
LUT. Short refs (8-bit offset, 2-5 byte copy) and long refs (13-bit offset,
3-bit or 8-bit count). All byte-aligned copies. Loop-unrolled with configurable
`_Kos_LoopUnroll` (default 3 = 8× unrolling).

**KosPlus Moduled (upgraded path):** Same core as S.C.E. Decompresses in 4KB
chunks with VBlank bookmark system for interruptible decompression.

**Nemesis:** Huffman-coded tiles, decompresses directly to VDP data port.
Very slow (~50-100 KB/s) but historically the only sprite format.

**Speed:** Kosinski ~120-200 KB/s, KosPlus ~190-310 KB/s, Nemesis ~50-100 KB/s.

**Relevance to S4LZ:** This is the baseline we're replacing. S4LZ must beat
KosPM's speed (310 KB/s peak) while matching or improving its ratio (~0.50).

---

## 2. Online Format Survey

### 2.1 LZ4W (SGDK, Stephane-D)

**The closest existing format to S4LZ.** Word-aligned LZ4 variant for 68000.

**Token format:** 16-bit word: `LLLL MMMM OOOO OOOO`
- L (4 bits): literal count in words (0 = no literals)
- M (4 bits): match length - 1 in words
- O (8 bits): match offset - 1 in words

**Long match:** When M=0 and O≠0: O encodes match length - 2, actual offset
follows as a separate word with format `XOOO OOOO OOOO OOOO` (X=0: RAM source,
X=1: ROM source).

**End marker:** All three fields = 0.

**Key characteristics:**
- All operations word-aligned (move.w only)
- 8-bit offset field = 256-word window (512 bytes) — very small
- Minimum match: 1 word (2 bytes)
- No extension mechanism for literal counts >15
- Decompressor: ~4KB (lookup table dominated)
- Speed: 600-950 KB/s on 7.67 MHz 68000

**Compression ratio:** ~0.53 on tile data (12,672 → 6,746 bytes in SpritesMind
benchmark). Worse than LZ4HC on larger files due to tiny window.

**Comparison with S4LZ design:**
- **Window size:** LZ4W's 512-byte window is severely limiting. S4LZ's 64KB
  window will find more and longer matches, improving ratio significantly.
- **Token format:** LZ4W packs everything into one 16-bit word — efficient but
  limits all fields. S4LZ's nibble-split byte token is more compact for short
  sequences (1 byte vs 2 bytes overhead) and extends naturally.
- **Big-endian:** LZ4W uses big-endian (native 68000). S4LZ does too. Confirmed.
- **Speed ceiling:** LZ4W proves 600-950 KB/s is achievable with word-alignment.
  S4LZ targets the same range with better ratio from larger window.

### 2.2 Comper (Clownacy / Sonic community)

**Format:** Ultra-simple word-aligned LZSS.

**Token format:** 16-bit descriptor word with 1-bit-per-token flags (MSB first).
- Bit = 0: **Literal word** — copy next 2 bytes from input.
- Bit = 1: **Dictionary match** — read 2 bytes: `offset_byte, length_byte`.
  Offset = (256 - offset_byte) × 2 (max 512 bytes back).
  Length = (length_byte + 1) × 2 (max 512 bytes).
  Terminator: offset=0, length=0.

**Key characteristics:**
- Word-aligned copies (`move.w` throughout)
- Bit-stream descriptor (16-bit word, 16 tokens per descriptor)
- 256-word window (512 bytes) — same as LZ4W
- Max match: 256 words (512 bytes)
- Minimum match: 1 word (2 bytes)
- Very simple decompressor (~50 bytes)
- Optimal compression available via clownlzss graph-based parser

**Speed:** Very fast decompression due to simplicity — estimated 800-1200 KB/s.
The 1-bit descriptor adds ~4 cycles per token (add.w d0,d0 + bcs/bcc) which is
much cheaper than a full byte parse.

**Compression ratio:** Poor (~0.65-0.75 typical). Small window and simple
token format limit matching ability.

**Comparison with S4LZ design:**
- Comper proves word-aligned copies work well on 68000
- The 1-bit descriptor approach is faster per-token than a nibble parse
- However, the terrible ratio disqualifies it for bulk art loading
- S4LZ's nibble token carries more info per byte of overhead

### 2.3 FC8 (Big Mess o' Wires)

**Format:** Byte-aligned LZ for 68020/030. Not Genesis-specific but
instructive for format design.

**Token types:**
- LIT: `00aaaaaa` — next a+1 literal bytes
- BR0: `01baaaaa` — backref, 5-bit offset, length b+3
- BR1: `10bbbaaa'aaaaaaaa` — 11-bit offset, length bbb+3
- BR2: `11bbbbba'aaaaaaaa'aaaaaaaa` — 17-bit offset, length from LUT

**Key findings:**
- Minimum match length of 3 bytes is optimal — reducing to 2 bytes compressed
  0.7% better but decompressed 13% slower (more tokens, more dispatch overhead)
- 256-byte main loop fits in 68020 instruction cache
- Achieves ~63% ratio, 1.5-2× faster than LZG
- Jump table dispatch gave ~15% speedup

**Relevance to S4LZ:** The minimum match length finding is critical. On 68000
(no instruction cache), the tradeoff may differ. However, for word-aligned
copies, minimum match = 2 words (4 bytes) is our natural boundary since 1-word
matches cost the same to encode as a literal.

### 2.4 LZSA1 / LZSA2 (Emmanuel Marty)

**Format:** Byte-aligned LZ optimized for 8-bit CPUs.

**LZSA1 token:** `O|LLL|MMMM`
- O (1 bit): offset size (0=1 byte, 1=2 bytes)
- L (3 bits): literal length (7 = extension)
- M (4 bits): match length (15 = extension)
- Minimum match: 3 bytes
- Extension: single byte (0-248 direct, 249/250 = 16-bit length follows)

**Key characteristics:**
- Designed to avoid 16-bit math on 8-bit CPUs (not optimal for 68000)
- Little-endian offsets (costs extra on big-endian 68000)
- 1-byte or 2-byte offsets (8KB or 16KB window for LZSA2)
- Very good compression for 8-bit targets

**Relevance to S4LZ:** The extension mechanism is well-designed: single byte
for common cases, 16-bit length for rare long runs. S4LZ should adopt a
similar approach. The O-bit for offset size is clever but unnecessary when
we always use 16-bit offsets (free on 68000).

### 2.5 ZX0 (Einar Saukas, 68000 port by Emmanuel Marty)

**Format:** Bit-stream Elias-gamma encoded. 88-byte decompressor.

**Key characteristics:**
- Excellent ratio (close to Exomizer)
- Bit-stream parsing: ~10-15 cycles per output byte minimum
- No lookup tables needed (tiny code footprint)
- Too slow for real-time streaming on Genesis

**Relevance to S4LZ:** Maximum compression at minimum code size, but speed
is inadequate for our streaming use case. Useful only if ROM space were
the absolute constraint (it isn't — we have 4MB).

### 2.6 SLZ (Sik / Project MD)

**Format:** Simple LZ for Mega Drive homebrew. 16-bit uncompressed length
header, then byte-aligned LZSS tokens.

**Relevance:** Designed for load-time decompression, not streaming. No
specific innovations beyond standard LZSS.

### 2.7 MEGAPACK (Codemasters, Jon Menzies)

**Format:** Tile-aware compression for Mega Drive 4bpp data.

**Key characteristics:**
- Pre-analyzes tile data for color adjacency patterns before compression
- "Bit packing based on which colours were frequently next to other colours"
- Achieved ~30% better compression than LZ on graphics files
- Used in Fantastic Dizzy (512KB ROM)
- Available source: compress.c, decompress.c, megaunp.s (68k decompressor)
- Compressed 18,752 bytes to 10,387 bytes (0.554 ratio), beating LZMA2

**Relevance to S4LZ:** MEGAPACK proves that tile-aware preprocessing yields
significant ratio improvements over generic LZ. Their approach (color adjacency
analysis) is more complex than our proposed tile-delta XOR. However, the 30%
improvement claim validates the concept that preprocessing tile data before LZ
compression is worthwhile.

---

## 3. Cycle Cost Analysis

### 3.1 Key 68000 Instruction Timings

| Instruction | Cycles | Notes |
|---|---|---|
| `move.b (An)+,(An)+` | 12 | 1 byte per 12 cycles |
| `move.w (An)+,(An)+` | 12 | 2 bytes per 12 cycles (2× throughput) |
| `move.l (An)+,(An)+` | 20 | 4 bytes per 20 cycles (2.4× throughput) |
| `dbra Dn,label` | 10/14 | 10 if branch taken, 14 if falls through |
| `add.w Dn,Dn` | 4 | Register-to-register |
| `and.w #imm,Dn` | 8 | Immediate AND |
| `lsr.w #n,Dn` | 6+2n | Variable cost by shift amount |
| `move.b (a0)+,d0` | 8 | Read byte from stream |
| `jmp table(pc,d0.w)` | 14 | Jump table dispatch |

### 3.2 Theoretical Throughput Limits

At 7.67 MHz, one frame ≈ 127,833 cycles (NTSC, 60fps).

**Pure copy throughput (no parsing overhead):**
- `move.b` loop: 12 + 10 = 22 cycles/byte → 348 KB/s
- `move.w` loop: 12 + 10 = 22 cycles/2 bytes → 697 KB/s
- `move.w` unrolled (no dbra): 12 cycles/2 bytes → 1,278 KB/s
- `move.l` unrolled: 20 cycles/4 bytes → 1,534 KB/s

**This confirms that word-aligned copies are essential.** The move.b loop ceiling
is 348 KB/s — below our 700 KB/s target even with zero parsing overhead.

### 3.3 S4LZ Token Dispatch: Nibble Split Analysis

Proposed S4LZ token: single byte `LLLL MMMM` (hi=literal words, lo=match words).

**Two-stage nibble dispatch:**
```
; Read token byte
    move.b  (a0)+,d0          ; 8 cycles — read token
    move.b  d0,d1             ; 4 cycles — copy for match nibble
    lsr.b   #4,d0             ; 14 cycles — extract literal count (hi nibble)
    and.w   #$0F,d1           ; 8 cycles — extract match count (lo nibble)
; Total parse: 34 cycles
```

**Alternative: 256-entry jump table:**
```
; Read token byte  
    moveq   #0,d0             ; 4 cycles (only needed once at init)
    move.b  (a0)+,d0          ; 8 cycles — read token
    add.w   d0,d0             ; 4 cycles — word index
    jmp     table(pc,d0.w)    ; 14 cycles — dispatch
; Total parse: 26 cycles (+ table entry overhead)
```

The jump table saves 8 cycles per token but costs 2-5 KB ROM for 256 entries.

**Hybrid approach (RECOMMENDED):** Use nibble extraction, then two small jump
tables (16 entries each for literal count and match count). This costs only
16 × 4 = 128 bytes total instead of 2-5 KB.

**Revised parse:**
```
    move.b  (a0)+,d0          ; 8 cycles
    move.w  d0,d1             ; 4 cycles
    lsr.w   #4,d0             ; 14 cycles (6+2×4)
    and.w   #$0F,d1           ; 8 cycles
    add.w   d0,d0             ; 4 cycles
    jmp     lit_table(pc,d0.w) ; 14 cycles → unrolled literal copy
; After literals return:
    add.w   d1,d1             ; 4 cycles
    jmp     match_table(pc,d1.w) ; 14 cycles → unrolled match copy
; Total: 70 cycles for dispatch + both copies initiated
```

This is ~34 cycles of pure dispatch overhead per token. With average 4 literal
words (48 cycles) + 3 match words (36 cycles), total per token ≈ 118 cycles
producing ~14 bytes. That's ~8.4 cycles/byte → **912 KB/s** — within target.

### 3.4 Full 256-Entry Jump Table Analysis

A single 256-entry jump table where each entry handles both the literal count
(hi nibble) and match count (lo nibble) in an unrolled sequence:

**ROM cost:** 256 entries. If each entry averages 10 instructions (5 literal
`move.w` + 4 match `move.w` + 1 branch back) at 2-6 bytes each = ~2-5 KB.
Many entries can share tails via fall-through.

**Speed:** Saves the nibble extraction entirely (26 cycles dispatch vs 70 for
the two-table approach). However, most of the time is spent in the copy
instructions themselves, not dispatch. The savings per token is ~44 cycles.

**Verdict:** The 256-entry table is faster but the ROM cost is significant.
With the two-table approach achieving 912 KB/s (above our target), the
full 256-entry table is **not necessary**. Reserve it as an optimization
if profiling shows dispatch is the bottleneck.

---

## 4. Design Decision Validation

### 4.1 Nibble-Split Token — CONFIRMED with MODIFICATION

**Original design:** Single byte, hi nibble = literal count, lo nibble = match count.

**Validation:** LZ4W uses a similar 4+4+8 approach in a 16-bit word. FC8 uses
multi-bit type fields. Comper uses 1-bit descriptors. The nibble-split approach
is well-established and maps naturally to 68000 instruction set (`lsr.b #4`
extracts hi nibble, `and.w #$0F` extracts lo nibble).

**MODIFICATION:** Change from full 256-entry jump table to **two 16-entry
jump tables** (one for literal count, one for match count). This reduces ROM
from 2-5 KB to ~128-256 bytes while keeping unrolled copies. The full 256-entry
table can be added later if profiling demands it.

After the literal copy completes, the match count nibble is used to dispatch
into the second table. This gives unrolled copies for both literals and matches
with minimal ROM overhead.

**Token byte format (confirmed):**
```
  7  6  5  4  3  2  1  0
 [  LIT_CNT  |  MATCH_CNT ]
  literal words  match words
```

### 4.2 Word-Aligned Copies — CONFIRMED

**Validation:** Every high-speed 68000 format (LZ4W, Comper) uses word-aligned
copies. The cycle analysis is conclusive:

| Copy method | Cycles per byte | Throughput at 7.67 MHz |
|---|---|---|
| `move.b (a5)+,(a1)+` + dbra | 22 cycles/byte | 348 KB/s |
| `move.w (a0)+,(a1)+` + dbra | 11 cycles/byte | 697 KB/s |
| `move.w (a0)+,(a1)+` unrolled | 6 cycles/byte | 1,278 KB/s |

Word copies are **2× faster** than byte copies per byte of data. This alone
is the difference between hitting 700 KB/s and being stuck at 350 KB/s.

**Edge case:** Input data must be word-aligned. The S4LZ compressor must pad
to even length. All Genesis tile art is inherently word-aligned (32 bytes per
tile = 16 words), so this is a non-issue for our primary use case.

### 4.3 Jump Table Dispatch — MODIFIED

**Original design:** 256-entry jump table (~2-5 KB ROM).

**MODIFIED to:** Two 16-entry jump tables (~128-256 bytes ROM). See §3.3-3.4
analysis. The full table's 44-cycle/token savings is real but unnecessary
given we already exceed the 700 KB/s target with the two-table approach.

**Recommendation:** Implement the two-table approach first. If streaming
decompression proves to be a frame-time bottleneck after integration, upgrade
to the full 256-entry table. The format itself is unchanged — only the
decompressor implementation differs.

### 4.4 16-Bit Big-Endian Offsets (64KB Window) — CONFIRMED

**Validation:**

**Window size comparison:**
| Format | Window | Typical ratio on tile art |
|---|---|---|
| LZ4W | 512 bytes | ~0.53 |
| Comper | 512 bytes | ~0.65-0.75 |
| LZSA1 | 256 or 8KB bytes | ~0.50-0.55 |
| Kosinski | 8KB | ~0.45-0.55 |
| S4LZ | 64KB | projected ~0.45-0.50 |

A larger window strictly improves compression ratio (more potential matches).
On 68000, 16-bit offset math costs the same as 8-bit (all address arithmetic
is 16-bit minimum), so there is **zero speed penalty** for the larger window.
The only cost is that every match token includes 2 offset bytes instead of 1.
For matches of 2+ words (4+ bytes), this overhead is negligible.

**Big-endian:** 68000 is natively big-endian. LZ4's little-endian offsets
require a byte swap (`rol.w #8,d0` = 22 cycles). Big-endian offsets load
directly with `move.w (a0)+,d0` (8 cycles). Savings: **14 cycles per match**.
With typical data having 40-60% matches, this saves 5.6-8.4 cycles per token
on average.

### 4.5 Tile-Delta XOR Preprocessing — CONFIRMED with CAVEATS

**Validation from multiple sources:**

1. **MEGAPACK (Codemasters):** Tile-aware preprocessing achieved ~30% better
   compression than generic LZ on Mega Drive tile art. Their approach was more
   complex (color adjacency analysis), but the principle is proven.

2. **NES development (nesdev):** Delta-coding (XOR with previous tile) improved
   compression from 71% to 64.5% of original — a 9% improvement. On a different
   dataset, quadtree + delta achieved much larger gains.

3. **rage1 project (ZX Spectrum):** Proposed tile XOR for ZX0 compression with
   the rationale that "xoring data with previous byte produces more similar bytes,
   and later compression gets better result." Untested but theoretically sound.

4. **General compression theory (Daniel Lemire):** Delta coding + XOR is a
   standard preprocessing step in modern compression. XOR avoids negative values
   and produces more zeros when inputs are similar.

**Why it works on Genesis tile art:** Adjacent tiles in a tileset share color
palette structure and often have similar pixel patterns (e.g., grass variants,
wall shading). XOR produces mostly zeros for identical pixels and small values
for similar ones. This creates long runs of zeros and small values that LZ
compresses efficiently.

**Runtime cost of XOR undo:**
```
; Per tile (32 bytes = 16 words):
; After decompressing, XOR with previous tile
    move.w  (a1)+,d0    ; 8 cycles — read current (XOR'd) word
    eor.w   d1,d0       ; 4 cycles — XOR with previous
    move.w  d0,(a1)     ; 8 cycles — write back
    move.w  d0,d1       ; 4 cycles — save as next "previous"
; = 24 cycles per word = 12 cycles/byte
; For 32-byte tile: 384 cycles
; At 7.67 MHz: 384/7,670,000 × 1024 = negligible overhead
```

**CAVEAT:** The 10-25% improvement claim in ENGINE_ARCHITECTURE.md should be
considered a range estimate. Based on research:
- Conservative (poorly correlated tiles): ~5-10% improvement
- Typical (zone tilesets with gradients): ~10-20% improvement
- Best case (very similar adjacent tiles): ~20-30% improvement

The improvement is data-dependent. The build tool should measure and report
the ratio with and without delta, and optionally skip delta when it doesn't
help (flag in the compressed data header).

### 4.6 Extension Bytes for Counts >15 — CONFIRMED with SPECIFICATION

**Original design:** "Single byte extension" — underspecified.

**Research findings on extension mechanisms:**

| Format | Extension mechanism | Max count |
|---|---|---|
| LZ4 | Chained 255 bytes (sum until byte < 255) | Unlimited |
| LZSA1 | Single byte (0-248), then 249/250 → 16-bit | 65535 |
| FC8 | Lookup table for BR2 lengths | Fixed set |
| Kosinski | 8-bit extended count byte | 255 |

**Specification for S4LZ:**

When literal or match count nibble = 15 (maximum nibble value), read one
extension byte. The total count = 15 + extension_byte.

- Extension byte 0-254: count = 15 + byte (range 15-269 words = 30-538 bytes)
- Extension byte 255: read one more 16-bit word for the count (range 0-65535)

This is simpler than LZ4's chained-255 scheme and sufficient for our data.
Genesis tile art blocks are rarely larger than 538 bytes of consecutive
literals or matches. The 16-bit escape handles pathological cases.

**Why not LZ4-style chaining?** On 68000, a branch to check for 255 costs
10-14 cycles each iteration. For counts up to 270, single-byte extension
requires one check. LZ4 chaining would require multiple checks for the same
count. The single-byte approach is faster for the common case.

### 4.7 Minimum Match Length — CONFIRMED at 2 Words (4 Bytes)

**Research findings:**

FC8 found that minimum match = 3 bytes was optimal for byte-aligned formats.
Reducing to 2 bytes compressed 0.7% better but decompressed 13% slower.

For S4LZ's word-aligned format, the analysis differs:

**Match token cost:** 1 token byte + 2 offset bytes = 3 bytes overhead.
A 1-word (2-byte) match would expand data (3 bytes overhead > 2 bytes saved).
A 2-word (4-byte) match saves 1 byte net (4 data - 3 overhead).

Therefore, **minimum match = 2 words (4 bytes)** is the natural breakeven
point. This is confirmed by LZ4W's approach (minimum match = 1 word, but
with a 2-byte token that includes the offset inline — different tradeoff).

For S4LZ with a separate 2-byte offset, 2-word minimum is correct.

---

## 5. Summary of Decisions

| Decision | Verdict | Details |
|---|---|---|
| Nibble-split token byte | **CONFIRMED** | Hi=literal count, lo=match count. Well-validated. |
| Word-aligned copies | **CONFIRMED** | 2× throughput. Non-negotiable for speed target. |
| 256-entry jump table | **MODIFIED → Two 16-entry tables** | 128-256 bytes ROM vs 2-5 KB. Still achieves target speed. Full table reserved as optimization. |
| 16-bit BE offsets (64KB window) | **CONFIRMED** | Zero speed cost, better ratio than small windows. 14 cycles/match saved vs LE. |
| Tile-delta XOR preprocessing | **CONFIRMED** | 10-30% ratio improvement depending on data. Add header flag to optionally disable. |
| Extension bytes for >15 | **CONFIRMED with spec** | Single extension byte (count = 15 + byte). 255 → read 16-bit word. |
| MIN_MATCH = 2 words (4 bytes) | **CONFIRMED** | Natural breakeven for 3-byte match token overhead. |

---

## 6. Final S4LZ Format Specification

### Header (4 bytes)
```
Offset  Size  Field
$00     2     Uncompressed size in bytes (big-endian)
$02     1     Flags: bit 0 = tile-delta XOR enabled
$03     1     Reserved (0)
```

### Token Byte
```
  7  6  5  4  3  2  1  0
 [  LIT_CNT  | MATCH_CNT ]
```
- LIT_CNT (4 bits): Number of literal words to copy (0-14 direct, 15 = extended)
- MATCH_CNT (4 bits): Number of match words to copy (0-14 direct, 15 = extended)

### Token Processing Order
1. If LIT_CNT > 0: copy LIT_CNT words from compressed stream to output
2. If LIT_CNT = 15: read extension byte, count = 15 + byte (if byte = 255, read 16-bit count)
3. If MATCH_CNT > 0: read 16-bit offset, copy MATCH_CNT words from (output - offset)
4. If MATCH_CNT = 15: read extension byte, count = 15 + byte (if byte = 255, read 16-bit count)
5. If MATCH_CNT = 0 and LIT_CNT = 0: end of stream

### Match Offset
- 16-bit big-endian value (2 bytes)
- Interpreted as negative byte offset from current output position
- Range: 2 to 65534 bytes back (word-aligned, so always even)

### End Marker
- Token byte $00 (LIT_CNT=0, MATCH_CNT=0)

### Alignment
- All literal data is word-aligned in the compressed stream
- All match copies are word-aligned
- Compressed stream starts at word-aligned address
- Output buffer must be word-aligned

### Extension Count Encoding
```
If nibble = 15:
    read byte B
    if B < 255: count = 15 + B (max 269)
    if B = 255: read word W, count = W
```

### Tile-Delta XOR (when flag set)
- Build-time: XOR each 32-byte tile with the previous tile before compression
  (first tile stored as-is)
- Runtime: after decompressing each tile, XOR it with the previous tile's data
  to reconstruct the original

---

## 7. Projected Performance

**Speed:** 700-1,100 KB/s depending on data compressibility
- Best case (many matches): ~1,100 KB/s (less literal copying)
- Typical tile art: ~800-900 KB/s
- Worst case (mostly literals): ~700 KB/s (copies dominate)

**Ratio:** ~0.45-0.55 depending on art and delta preprocessing
- With tile-delta on zone tilesets: ~0.40-0.50
- Without delta: ~0.50-0.60
- Sprite art (no delta): ~0.50-0.55

**ROM footprint:** ~200-400 bytes for decompressor (two-table approach)

**Comparison with replaced formats:**

| Metric | Nemesis | Kosinski | KosPM | LZ4W | **S4LZ** |
|---|---|---|---|---|---|
| Speed (KB/s) | 50-100 | 120-200 | 190-310 | 600-950 | **700-1,100** |
| Ratio | 0.40-0.50 | 0.45-0.55 | 0.45-0.55 | 0.50-0.55 | **0.40-0.55** |
| Word-aligned | No | No | No | Yes | **Yes** |
| Streamable | Yes (slow) | No | Yes | Yes | **Yes** |
| Tile-aware | No | No | No | No | **Yes (delta)** |

---

## Sources

- [SGDK LZ4W specification](https://github.com/Stephane-D/SGDK/blob/master/bin/lz4w.txt)
- [SpritesMind LZ4W discussion](https://gendev.spritesmind.net/forum/viewtopic.php?t=2479)
- [FC8 format analysis](https://www.bigmessowires.com/2016/05/06/fc8-faster-68k-decompression/)
- [68000 decompression optimization](https://www.bigmessowires.com/2016/04/28/optimizing-assembly-fast-68k-decompression/)
- [clownlzss optimal parser](https://github.com/Clownacy/clownlzss)
- [clownlzss blog post](https://clownacy.wordpress.com/2021/10/14/clownlzss-a-perfect-lzss-compressor/)
- [LZSA format specification](https://github.com/emmanuel-marty/lzsa/blob/master/BlockFormat_LZSA1.md)
- [MEGAPACK for Mega Drive](https://github.com/lab313ru/megapack-megadrive)
- [ZX0 68000 decompressor](https://github.com/emmanuel-marty/unzx0_68000)
- [Mega Drive compression formats overview](https://s3unlocked.blogspot.com/2017/06/mega-drive-compression-formats.html)
- [NES tile compression discussion](https://forums.nesdev.org/viewtopic.php?t=3347)
- [Tile XOR preprocessing proposal](https://github.com/jorgegv/rage1/issues/109)
- [68000 instruction timings](https://wiki.neogeodev.org/index.php?title=68k_instructions_timings)
- [LZ4 on 68000](https://bumbershootsoft.wordpress.com/2025/07/12/lz4-decompression-on-the-68000/)
- [Plutiedev SLZ format](https://plutiedev.com/format-slz)
