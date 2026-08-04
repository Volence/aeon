# Item 28 (bg blit) — A/B evidence, and the fork this parcel STOPPED at

Evidence packet for the `item28-bg-guard` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent) — one real corruption guard, one byte-neutral dispatch
inversion, and comment/contract corrections.

**This parcel deliberately does NOT do the thing item 28 is named for.** The
blit posture (`move.l`/DMA) and the BG column-major transpose are a coupled
three-way design fork and were left for review; see the last section.

## Builds compared

| shape | OLD (`master` @ `f042c02`) | NEW (`parcel/item28-bg-blit`) |
|---|---|---|
| `s4.bin` | `crc=056aa103` / 384,048 | `crc=3879b953` / 384,048 |
| `s4.debug.bin` | `crc=b5c1a039` / 423,383 | `crc=2623ee7f` / 423,383 |
| `demo.debug.bin` | `crc=cdb58b5a` / 93,943 | `crc=e3243cbb` / 93,943 |

All three file lengths unchanged — the +2 lands in existing region padding. The
`bg` region grew 174 -> 176 B; that is the whole diff, and it is the guard.

## Result 1 — the bug, walked

`BG_Init`'s tile blit takes `d1.w` = blob byte length from a 2-byte BE header.
The guards were `beq .skip_tiles` (rejects 0 only) and an upper clamp
(`cmpi.w #BG_TILE_REGION_BYTES` — rejects nothing at or below `$3800`). Then
`lsr.w #1` / `subq.w #1` / `dbf`:

| len | after `lsr.w #1` | after `subq.w #1` | dbf iterations | words written |
|---|---|---|---|---|
| **1** | `$0000` | **`$FFFF`** | **65,536** | **128 KB — wraps ALL of VRAM twice**, through the SAT, both planes and the HScroll table |
| 2 | `$0001` | `$0000` | 1 | 1 — correct |
| 3 | `$0001` | `$0000` | 1 | 1, trailing byte dropped — benign, as the old comment said |

So the hole is real and is **exactly and only length 1**. Odd lengths >= 3 are
fine. The pre-existing comment described the hazard accurately and explicitly
declined to fix it.

## Result 2 — the review's literal fix would have introduced a second bug

The review prescribed `beq.s .skip_tiles` **after** the `lsr`. At that point
`stop_z80` has already run, and `.skip_tiles` sits **past** the matching
`start_z80` — so a taken guard branch would have left the Z80 bus held for the
rest of the level. A one-line "obvious" fix that trades a data-dependent VRAM
spray for an unconditional sound death.

Taken instead: hoist BOTH counter ops above the `stop_z80` bracket, so the guard
branches before the bus is ever taken. Neither `stop_z80` nor the VDP setup
touches `d1`, so the hoist is free.

```
.bg_len_ok:
        lsr.w   #1, d1          // word count = bytes/2
        beq     .skip_tiles     // 1-byte (sub-word) blob -> nothing to copy
        subq.w  #1, d1          // dbf counter (safe: word count >= 1)
        stop_z80
        ...
```

Verified in the shipped ROM at `s4.bin:$63B2`:
`e249 673a 5341 33fc 0100 00a1 1100` = `lsr.w` / `beq.s` / `subq.w` / `stop_z80`.

**The nametable blit does NOT share the shape** — its count is a compile-time
`#BG_LAYOUT_SIZE/2 - 1` (4095), never data-derived. Checked rather than assumed,
and a comment now records it so the next reader need not re-derive it.

## Result 3 — rendering unchanged

Deterministic scene: reset, then `press(['right'], 300)`. The captured
framebuffer is **byte-identical (md5 `9cf6ec8b…`) to the reference capture taken
at parcel 1** — five parcels earlier, same sequence. Since the guard only fires
on a malformed length-1 blob and no shipped blob is length 1, the correct result
is exactly this: no visible change, and the hazard structurally closed.

68k in the normal main loop (`VInt_DrawLevel`), never the error handler.

## Result 4 — the byte-neutral items, proven byte-neutral

- **Dispatch inversion** (ZX0 was the out-of-line arm; it is the production
  case): verified from the data, not assumed — every act-pool page ships as
  `.zx0` and there is **no `.s4lz` file anywhere** under `games/sonic4/data`;
  the only caller reaching the S4LZ arm is `compression_selftest`, which
  exercises both deliberately. `Art_Decompress` stays at offset 19376 / 29482 in
  both size tables.
- **`zx0_decompress.emp`**: one comment line only (Elias values accumulate in
  `d0.l` while the copy loops count with `dbf`/word — safe by construction, the
  u16 wrapper caps uncompressed size at 65535). `ZX0_Decompress` unchanged at
  3728 / 10304, which is the proof: this file's whole value is that it diffs
  clean against Emmanuel Marty's upstream `unzx0_68000.S` V2.

## Result 5 — contract corrections

`load_art`'s clobber header was wrong, and **the review's description of how it
was wrong is itself stale** (d7 IS clobbered now — the drop handling added
`move.w d4, d7`). Re-derived from scratch: own writes ∪ callee licenses minus
the `movem` set = **`d0-d4, d7, a0-a3`**. The real defect was **d5** — declared
but written by no instruction and no callee, so every caller was saving a
register this proc never touches. Signature is now
`clobbers(d0-d4/d7/a0-a3) preserves(d6/a4-a6)`, with the derivation written into
the header. The d6 save is genuinely live (the `dbf` page counter across three
calls), so there was no dead save to drop.

Two `bg.emp` documentation defects, both verified against ground truth:
- The header claimed the region is `$A000-$BFFF`. Both halves were wrong: it is
  `$8000-$B7FF` (slots 1024-1471), bounded above by the relocated SAT at
  `$B800`.
- **The runtime 32-row limit is now recorded.** `BG_Init` fills all 64 plane
  rows and the header advertised 512px of vertical headroom, but the two runtime
  maintainers only ever touch 32 — `Section_RedrawPlanes`' Plane B blit is 4096
  bytes = 64 cols x 32 rows, and `Draw_BG_TileColumn` writes `moveq #32-1`. A
  redraw or a streamed column silently reverts to a 32-row world while rows
  32-63 keep stale init content. Invisible today ONLY because the injector
  zero-pads, so "stale" reads as "blank".

## STOPPED — the coupled fork, left for review

Not implemented, deliberately: `move.l`/unroll/DMA conversion of the two init
blits, and the BG column-major transpose. The review itself makes the coupling
explicit — "decide together with bg.asm's posture", "decide with load_art", and
"column-major forces 64 small DMAs if the init blits become DMA (decide
together)". Three decisions that have to be taken as one:

1. **bg init blits** — CPU word pokes today (~90k cycles nametable, ~158k tiles,
   about 2 frames with SR masked and the Z80 stopped). Tier 1 `move.l` ~80k;
   Tier 3 real DMA ~0.3-0.4 frame for all 22 KB, but needs 128KB-straddle
   handling.
2. **load_art** — queue+VSync vs direct blocking DMA (est. 3-8 frames per act
   load).
3. **the transpose** — column-major would take `Draw_BG_TileColumn` from ~34 to
   ~22 cyc/word (~380/strip, per-frame at scroll speed), and the review's census
   says it needs no dual format. But it flips `.emp` twins, `ojz_strip_gen.py`
   and the editor-library blobs in one commit, and the ACT blob must be
   transposed too (production sections have `sec_bg_layout = NULL`, so the act
   fallback IS the common per-frame path).

The owner's standing instruction is to stop on a coupled design fork rather than
pick, so it stops here.

One useful finding for whoever takes it: **the guard added by this parcel is not
made redundant by a `move.l` conversion.** A halved long count underflows
identically on a 2-byte blob, so the guard would be re-derived, not deleted. The
two are less coupled than they look.

## Gates

Strict suite **3000 passed / 0 failed** after the re-pin (30 failed before it,
all stale-pin/golden fallout from the `bg` region's +2). `refreeze --check` +
`repin --check` clean.
