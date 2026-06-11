# Two-Tier Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Replace the single S4LZ tier with the measured-best two-tier scheme: ZX0 for
load-time tile art (0.968 → 0.62), S4LZ-v3 + per-section block dictionary for the
runtime block path (0.52 → 0.29 effective), plus the audit's correctness/speed/dead-code
items. Best-of-the-best mandate from the user; build time is not a constraint.

**Architecture:** Two formats by decode-speed tier. Hot path (TileCache_DecompressBlock,
6 blocks/frame) keeps word-aligned S4LZ upgraded to the v3 token (pad byte = short
offset/2, 0 = long offset word follows) and gains a per-section ROM dictionary: the
window is pre-seeded with K section blocks stored raw (K chosen per section by build
sweep 0..3, minimum effective size; measured optimum K=1 on OJZ). Cold path (section
tile art, 85-frame preload window + init loads) moves to ZX0 (salvador-compressed,
unzx0_68000 decompressor vendored under zlib license, adapted to AS syntax + house
conventions).

**Measured basis (OJZ corpus, unique sections, docs/research/compression-audit-2026-06-11.md):**
- Tiles: raw 24,800 → today 23,998 (0.968) → ZX0 15,394 (0.621). Example sec1_tiles.bin: 8,992 → 8,878 today → 5,464 ZX0.
- Blocks: raw 94,904 → today 49,426 (0.521) → v3+dict1 27,180 effective (0.286).
- v3 alone (no dict): tiles 0.847 / blocks 0.486. ZX0+dict on blocks (0.262) rejected: decode too slow for 6/frame.
- zstd-trained dicts measured WORSE than real-block dicts (0.445 vs 0.319 at K=2) — real blocks carry exact word runs.

**Decode-cost contracts:** v3 ≤ v1 cycles (short-offset matches skip the offset-word
fetch); dict adds one compare-branch per match (~16c, only on dict-hits). ZX0 is
bitstream (~Kosinski-class); budgeted ONLY for preload/init paths — measure actual
cycles in Exodus during T6 and record in the architecture doc.

---

### Task 1: S4LZ v3 format — compressor + blocking decompressor + tests
**Files:** tools/s4lz.py, engine/s4lz_decompress.asm, test additions to tools/ (pytest or self-test), docs later (T8).
- [ ] s4lz.py: bump header (reserved byte → version=1 marker; flags bit1 = v3 token… simpler: v3 IS the format now; version byte = 1; loader asserts). Token: byte [lit nibble|match nibble] + second byte = match offset/2 when 1-255 (offset 2..510, even), 0 = 16-bit offset word follows after literals. Extensions unchanged (nibble 15 → word). EOS = $00 token + pad. Keep word alignment throughout (token word, literal words, offset word).
- [ ] s4lz.py: DP cost model update (match cost = 0 short / 2 long + ext); emit per spec. Remove checkpoint_interval/max_match_words options and _compress_segmented (dead with streams, T5). Remove tile_delta? KEEP encode/decode functions + flag (harmless, may help future non-deduped data) but it is no longer used by build.
- [ ] s4lz.py self-tests: update all 12, add v3-specific: short-offset boundary (2, 510, 512), long offset, both-ext token, overlap match offset 2 short-form.
- [ ] s4lz_decompress.asm: v3 decode — token word fetch (move.w), match path: tst.b pad → short (ext.w + add.w d,d → offset) or long (offset word after literals — NOTE stream order: token, [lit ext], literals, [offset word if long], [match ext]). Keep a3-safe contract. Fix audit F5: consume EOS pad (a0 ends even, past stream); truncation note for odd sizes in header comment.
- [ ] Verify: build both flavors; py round-trips green.
- [ ] Commit.

### Task 2: Per-section block dictionary
**Files:** tools/ojz_block_gen.py, engine/level/tile_cache.asm, structs.asm (Act/Sec field), data regen via build.
- [ ] ojz_block_gen.py: per section, sweep K=0..3 dict blocks (4-gram coverage scoring, see audit harness); pick min(total = dict raw + Σ compressed). Emit: dict blob (raw, word-aligned) + per-block v3 streams compressed with window pre-seeded by dict. Block index table entry for dict blocks points into the RAW dict region (no decompression marker: high bit of index offset = raw direct). Sec struct gains sec_block_dict (ptr) + sec_block_dict_len (word).
- [ ] tile_cache.asm TileCache_DecompressBlock: load dict ptr/len from Sec; raw-direct blocks: movem/loop copy 768B from ROM (or better: FindStagedBlock-style return of ROM pointer? staging slots are RAM — copy needed; raw copy ≈ 770×6c ≈ cheaper than any decompress). Match copy: after a2 = a1 - offset, cmp a2 vs slot base; below → add (dict_end - slot_base) rebase constant (computed once per call into a register).
- [ ] DEBUG assert: dict_len even, offsets never reach below dict base.
- [ ] Regen data, build, verify in Exodus: level boots, blocks render identically (screenshot compare vs master), Lag_Frame_Count idle unchanged, vertical descent protocol not regressed (≤ +4/512px).
- [ ] Commit.

### Task 3: ZX0 tile-art tier
**Files:** tools/ (vendor salvador build or prebuilt + license), engine/zx0_decompress.asm (vendored unzx0_68000.S adapted: AS syntax, sized branches, house header, zlib license attribution), engine/level/load_art.asm, build.sh, act descriptor data refs (.zx0 files).
- [ ] Vendor salvador: tools/salvador/ source + build into build.sh prerequisites (or commit prebuilt linux binary — prefer building from source once into tools/bin, document). License files retained.
- [ ] build.sh: sec*_tiles.bin → salvador → sec*_tiles.zx0 (replaces s4lz+tile-delta step). Empty sections: keep 4-byte zero header convention? ZX0 has no size header — keep our 4-byte [size.w][ver.b][res.b] prefix wrapper for BOTH tiers (loader peeks size for DMA), then format-specific stream. Loader dispatch by version byte (0/1 = s4lz v1/v3, 2 = zx0).
- [ ] engine/zx0_decompress.asm: adapt unzx0_68000.S — verify against salvador output (T6 test). Account for our 4-byte wrapper (skip before calling).
- [ ] load_art.asm: LoadArt dispatches on version byte; Section_StreamArtGroup likewise. S4LZ path stays for any v1/v3 art blobs.
- [ ] Build, Exodus verify: title art + section art loads render identically.
- [ ] Commit.

### Task 4: ASM-vs-encoder golden test (audit F5 test gap)
**Files:** test/ (new test mode or debug assert), tools/.
- [ ] Build-time: compress a fixed test vector (≥1 of each: short offset, long offset, both-ext, overlap-2, empty) with s4lz.py AND salvador; BINCLUDE blobs + expected SHA/checksum words into DEBUG build; boot-time self-test decompresses both formats to RAM and compares checksums, assert on mismatch (ifdebug). Cheap, runs every DEBUG boot.
- [ ] Exodus MCP verification of the assert path (corrupt one byte → assert fires).
- [ ] Commit.

### Task 5: Dead code + pipeline cleanups
**Files:** engine/s4lz_stream.asm (delete), tools/ojz_strip_gen.py (strip emission removal), data/levels/ojz/act1/act_descriptor.asm (strip BINCLUDEs), build.sh, structs.asm (ss_* struct removal), ram.asm if stream state RAM exists.
- [ ] Delete s4lz_stream.asm + assembly include; remove strip .s4lz/.bin emission + checkpoint files + BINCLUDEs (~50 KB ROM); remove StreamState struct + RAM.
- [ ] build.sh empty-blob: emit header+EOS (6 bytes) per audit F5.
- [ ] Blob content-dedup: section pipeline content-hashes tile/dict/block blobs; identical → shared label (act descriptor points N sections at one blob). (~37 KB on OJZ today.)
- [ ] Build both flavors; ROM size delta recorded.
- [ ] Commit.

### Task 6: Measure + verify in Exodus (DEBUG)
- [ ] Block decode timing: breakpoint sampling or cycle delta around TileCache_DecompressBlock for v3+dict vs the master baseline (expect ≤ baseline); sustained vertical+horizontal scroll lag protocol (≤ +4/512px vertical, ≤ +6 horizontal).
- [ ] ZX0 decode timing: frame_token span across a full section art load; record KB/s; confirm preload window comfortably absorbs it.
- [ ] Visual: boot, scroll all sections, teleports, debug-fly sweep — screenshot spots vs master.
- [ ] Record all numbers in the plan results section.

### Task 7: ROM accounting + before/after report
- [ ] Script: total compressed bytes per class before (git show master data) vs after; verify the measured ratios surfaced in audit hold in shipped ROM (tiles ~0.62, blocks ~0.29 effective).

### Task 8: Docs
- [ ] ENGINE_ARCHITECTURE §2.1 rewrite: two-tier table with MEASURED ratios/speeds (not projections), v3 token spec, dict design, ZX0 tier + license note, corrected decompressor speed numbers; kill stale claims (0.45-0.50, 700-1,100 KB/s, jump tables, tile-delta benefit).
- [ ] DEFERRED_WORK: close audit items; add follow-ups found during implementation.
- [ ] Commit; merge branch `compression-two-tier` to master after final review.

**Branch:** `compression-two-tier` off master. Subagent-driven (implementer + spec review + code review per task). Each task ends with both build flavors green.
