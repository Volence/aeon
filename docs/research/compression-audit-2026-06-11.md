# S4LZ Compression Audit — 2026-06-11

Full-system review: format design, compressor strength, decompressor speed/correctness,
measured against the real OJZ corpus (16 per-section tile blobs, 90,592 B; per-block
stream data, 105,428 B). Companion: `compression-audit-landscape.md` (external survey).

## Measured ratios (real data, not projections)

| Corpus | Config | Ratio | Notes |
|---|---|---|---|
| Tile blobs | **today** (`--tile-delta`, shipping) | **0.968** | delta XOR HURTS post-dedup data |
| Tile blobs | no delta, same format | 0.881 | config change only |
| Tile blobs | v3 format (short-offset pad) | **0.847** | optimal parse, modeled exactly |
| Tile blobs | LZ4HC (≈LZ4W class) | 0.815 | byte-granular matches |
| Tile blobs | zlib -9 | 0.610 | entropy coding — unreachable at our speed class |
| Blocks (768 B each) | today | 0.532 | per-block for random access |
| Blocks | v3 format | **0.486** | −7.2% relative; all intra-block offsets are near |
| Blocks | whole-stream (no random access) | 0.192 | what per-block independence costs |

Example files: `sec1_tiles.bin` 8,992 → today 8,878 (0.987) → no-delta 7,966 (0.886) →
v3 7,542 (0.839). `sec0_tiles.bin` 6,336 → 6,034 → 5,530 → 5,198 (0.820).

The architecture doc's "~0.45–0.50" ratio claim does not hold on the real corpus: the
build's tile dedup already removed the redundancy that figure assumed. Post-dedup unique
tiles are inherently LZ-hostile (literals are 83% of the compressed stream).

## Findings

### F1 — `--tile-delta` is a net loss on the shipping corpus (config bug)
0.968 with vs 0.881 without (−8.7 pt). After dedup, adjacent tiles are dissimilar; the
XOR converts structure to noise and destroys cross-tile matches. The "5–30% better"
design claim was tested pre-dedup. **Fix: drop the flag in build.sh** (or make the
compressor try both and keep the smaller — the header flag already supports per-blob choice).

### F2 — the token PAD byte is pure waste; repurpose it as a short offset (format v3)
Every sequence spends 1 byte on a $00 pad for word alignment (~3.7% of compressed size).
LZ4W spends that same byte on its offset. v3: pad byte = match offset/2 when offset ≤ 510
(0 = long offset word follows). 49% of tile matches and ~100% of block matches qualify.
Measured: tiles 0.881→0.847, blocks 0.524→0.486. Decode cost: neutral-to-faster
(the byte arrives with the token word; saves the offset-word fetch on short matches).
Byte-count token variant (v2) measured weaker (0.866) — v3 is the right variant.

### F3 — compressor parse is already optimal; the match finder's early-exit is free
The DP (per-position best match + all sublengths, flat offset cost) is provably optimal
for this cost model; an exhaustive finder reproduces the shipping totals exactly. No
compressor-strength work needed beyond retargeting the cost model to v3.

### F4 — decompressor is ~510–640 KB/s, not the documented 700–1,100
Cycle analysis (see agent report in this audit): realistic mix ≈ 13.7 c/byte. The
documented jump-table design was never implemented (shipped: nibble extraction).
Speed wins, cheapest first: (1) `move.l` in unrolled copy tables (guard match path for
offset ≥ 4); (2) unroll the extended-count `dbf` loops — currently the SLOWEST path per
byte despite being the bulk case; (3) 256-entry token jump table (~1.5 KB ROM) → ~10
c/byte ≈ 770 KB/s. Block decompression is ~half a frame at 6 blocks/frame today; these
wins cut it to ~⅓.

### F5 — correctness nits (no current-caller impact, all latent)
- EOS path doesn't consume the pad byte → returned a0 is odd / off-by-one (breaks
  back-to-back stream parsing if ever used).
- No truncation to header size on odd-size input (a1 contract wrong; benign today).
- build.sh emits bare 4-byte headers for empty sections with NO EOS token — safe only
  because all callers peek size first. Emit header+EOS (2 bytes) for defense.
- **No test verifies the 68000 decompressor against the Python encoder** — all round-trip
  tests are Python-vs-Python. Add an Exodus-MCP or debug-build checksum test.

### F6 — dead code: the streaming variant and strip data
`s4lz_stream.asm` (S4LZ_Stream_Init/Decompress) has zero callers; the per-section
`sec*_strips.s4lz` + checkpoint files are BINCLUDEd but never referenced (~50 KB ROM).
The 2D block cache replaced strips (DEFERRED_WORK acknowledges). Delete both together.
The compressor's `checkpoint_interval`/`max_match_words` options serve only this dead
path (and the literal-run overshoot was never capped anyway — contract hole, moot).

### F7 — section blob duplication (build-level, not compression)
sec0=sec2=sec4=sec6=sec8 and sec1=sec3=sec5=sec7 and secA–D are byte-identical blobs
compressed and stored separately (test-level artifact, but the generator should
content-hash blobs and share one copy + pointer; saves ~37 KB on this act today).

## Verdict on the format choice itself
S4LZ (with v3) lands within 4% of LZ4HC-class ratio on tiles while keeping word-aligned
68000-native decode — the design thesis survives contact with real data. zlib's 0.61
needs entropy coding (Kosinski-or-slower decode — wrong tier). No external format
(LZ4W included) justifies a migration: v3 + the speed wins close the gap from our side.

## Recommended work package (priority order)
1. build.sh: drop `--tile-delta` (or auto-pick smaller) — free 8.7 pt.
2. Format v3 (compressor cost model + encoder + both decode paths + regen data).
3. Decoder speed: move.l tables + extended-loop unroll (+ jump table if profiling wants it).
4. Correctness: EOS pad consume, empty-blob EOS, ASM-vs-Python verification test.
5. Delete s4lz_stream.asm + strip generation/data; remove checkpoint/max_match options.
6. Blob content-dedup in the section pipeline.
7. Docs: fix §2.1 speed/ratio claims to measured numbers.
