# Tile Dedupe + Flip Canonicalization Research (§2 A.1)

**Date:** 2026-04-26
**Driver:** §2 Phase 2 Layer A.1 needs to globally deduplicate 32-byte Genesis tiles, treating tiles that are H/V/HV-mirrors as the same canonical tile, then rewrite nametable strips so the original visual is preserved via the nametable's H/V flip bits.

## Sources reviewed

**Reference disassemblies (all 7):**
1. **S.C.E.** (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Tools/`) — directory contains only the AS Macro Assembler binary and HTML docs. No tile-dedupe utility exists.
2. **sonic_hack** (`/home/volence/sonic_hacks/sonic_hack/tools/`) — Kosinski and Nemesis compressors/decompressors plus `split_sections.py`. No flip-aware tile-dedupe utility.
3. **Batman & Robin disasm** (`The Adventures of Batman and Robin/disasm/`) — pure disassembly, no `tools/` or `scripts/` directory. No `hflip`/`vflip`/`canonical` symbols anywhere in the source. Disassemblies show final tile data, not the build pipeline that produced it.
4. **Vectorman disasm** (`vectorman_disasm/`) — same as Batman & Robin: pure disassembly, no build tools, no flip-related symbols.
5. **Thunder Force IV disasm** (`thunderforce4_disasm/`) — same.
6. **Gunstar Heroes disasm** (`gunstar_disasm/`) — same.
7. **Alien Soldier disasm** (`aliensoldier_disasm/`) — same.

The five sibling disassemblies are silent on tile-dedupe specifically because they're working backwards from the final ROM. Whatever dedupe their original developers did happened in build tools we'll never see.

**Online & community sources:**
8. **SGDK `rescomp` — `tools/rescomp/src/sgdk/rescomp/resource/Tileset.java`** (Stephane-D/SGDK on GitHub, master branch, fetched 2026-04-26). The `getTileIndex()` method invokes `getFlipEquality()` when `TileOptimization.ALL` is enabled and returns the index of the *first-encountered* equivalent tile, with the comment "better to keep first index if duplicated." Only confirmed flip-aware tile-dedupe implementation found in any source.
9. **plutiedev.com** — fetched the "Tiles and palettes" and "Tile ID flags" topics. Documents nametable flip bits as a runtime VDP feature (correctness-level reference) but does not discuss build-time flip-aware canonicalization. Tile-dedupe as a build optimization is not covered.
10. **md.railgun.works** — searched for "tile dedup"; zero results. Wiki has no page on the topic.
11. **GitHub homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD)** — these projects are SGDK consumers, so they inherit `rescomp`'s first-encountered approach. No surveyed project replaces or extends rescomp's tile-equivalence rule.
12. **`aeon/tools/ojz_strip_gen.py`** — read end-to-end, audited specifically for H/V bit preservation.

**Conclusion from breadth:** Lex-smallest canonicalization is genuinely novel for the Genesis homebrew/disasm world. SGDK's first-encountered is the only published prior art; everyone else either doesn't dedupe at all or uses SGDK as a black box.

## Canonicalization rule

**Lex-smallest of the four orientations: identity, H, V, HV.** Compare the 32 bytes of each orientation as a byte sequence; the lexicographically smallest variant becomes the canonical form. Deterministic, build-reproducible, independent of section iteration order — a non-issue if our section-walk order changes (e.g., reordering sections in the act descriptor doesn't shuffle which orientation wins). SGDK's `rescomp` uses first-encountered instead, which is load-order-dependent; lex-smallest improves on this for our use case where we expect to regenerate strip data frequently as level layouts evolve.

## Dedupe algorithm

Walk every 32-byte tile referenced anywhere across all sections of an act. For each tile, compute its canonical form (lex-smallest orientation) and the flip bits needed to rotate the *original* into that canonical (so the strip remap can recover the original orientation). Maintain a hash table from `canonical_bytes → canonical_index` in first-seen order; if the canonical form is new, append to a `unique_tiles` list. Emit `mapping[i] = (canonical_index, flip_bits_from_original_to_canonical)` for the i-th input tile. The `unique_tiles` list is what gets S4LZ-compressed and DMA'd to VRAM.

## Strip remap rule

A Genesis nametable word is `priority[15] | palette[14:13] | V[12] | H[11] | tile_index[10:0]`. Rewriting preserves priority + palette unchanged. The new tile_index is `canonical_index` from `mapping[i]`. The new H/V bits are the original H/V XORed with the `flip_bits` that the canonicalization needed: if the canonicalization rotated the tile by H to reach canonical, the strip's H bit toggles to recover the original visual. `new_H = orig_H ^ (flip_bits & 1); new_V = orig_V ^ ((flip_bits >> 1) & 1)`.

## `ojz_strip_gen.py` audit result

**No fix needed.** `chunk_get_tile_word()` returns `blocks[block_id][word_idx]` — the full 16-bit nametable word with all bits intact (priority, palette, V, H, tile index). The word flows unchanged through `generate_section_strips()` → `build_strips_from_nametable()` → `write_strips_to_file()`. Independent verification: a `struct.unpack` sample of the first 1000 words from the existing `data/generated/ojz/act1/sec0_strips_a.bin` shows H-flip bits set in the data (e.g., word at offset 0x278 = 0xE941 with H=1), confirming end-to-end preservation. The remap pass in A.1 can rely on this without changes.

## ENGINE_ARCHITECTURE.md changes

**None.** §8.1a already lists "Deduplicate tiles: Identify identical tiles across sections (including flip variants)" as a build-tool deliverable; §8.1b mentions "Flip-variant detection" in the editor budget UI section. The architecture doc treats flip-aware dedupe as a documented requirement; A.1 is implementing what the doc already specifies. The lex-smallest-orientation rule is an implementation detail not worth surfacing into the architecture doc.
