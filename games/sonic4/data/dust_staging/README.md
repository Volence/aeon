# Dust asset importer — provenance

`gen_dust.py` extracts Sonic 3 & Knuckles' `Obj_DashDust` sprite assets
(spindash charge dust + skid/slide puff) into Aeon's mapping/DPLC/art formats.
Deterministic, no timestamps or RNG — running it twice produces byte-identical
output.

## Donor

`skdisasm/General/Sprites/Dash Dust/`:

- `Dash Dust.bin` — 5952 bytes = 186 tiles of 32 B, uncompressed 4bpp art.
- `DPLC - Dash Dust.asm` — 30 frames ($00-$1D), symbolic pointer table.
- `Map - Dash Dust.asm` — 30 frames ($00-$1D), symbolic pointer table.

Both `.asm` files use `dc.w LABEL-BASE` pointer arithmetic rather than hex
literals, and frame bodies mix `dc.b` with `dc.w`. Parsed via
`gen_characters.py`'s `frames_from_asm` (imported read-only via `importlib` —
see the docstring on `load_donor_parser()` in `gen_dust.py` for why this is not
refactored into a shared module).

## What we ship

One 88-tile art blob = donor tiles `$062`-`$0B9` (inclusive), in order:

| Blob tiles | Donor tiles | Use |
|---|---|---|
| 0-71  | `$062`-`$0A9` | charge frames `$0A`-`$10` (the spindash charge cycle), streamed by DPLC |
| 72-87 | `$0AA`-`$0B9` | the 16-tile skid/slide puff block, DMA'd resident once |

Donor mapping/DPLC frames `$0A`-`$10` are the charge cycle (tile counts
8, 8, 8, 12, 12, 12, 12 — verified against the real `.asm`). Frames `$11`-`$14`
are the puff cycle: one 2x2-tile piece each, at tile offsets `0`/`4`/`8`/`$C`
relative to their own resident window, and their DPLC lists are empty (verified:
all four point at the same zero-entry DPLC body). Frame `$15` is a pure
DPLC-load frame (empty mapping, pointing back at frame `$00`'s body) whose
single DPLC entry loads the 16-tile puff block (`$AA`, count 16 — verified).

Frames `$16`-`$1D` are the splash/drown set, on a **different art base**
(outside the `$062`-`$0B9` span we ship). Out of scope — no water system.

## Palette re-index (measured, not negotiable)

The dust draws on CRAM line 0, the character palette. Measured over the 88
shipped tiles:

| Source (S3K) index | Pixel count |
|---|---|
| 0  | 4286 |
| 1  | 1244 |
| 12 | 81   |
| 13 | 21   |

No other index appears. Under Aeon's `art/palettes/SonicAndTails.bin` line 0,
all three non-transparent source indices are wrong colours (index 1 is `$0EEE`
white in S3K but near-black here; 12 is `$0ECC` red vs a different colour here;
13 is `$0CAA` dark red vs a different colour here). The colour-lossless
permutation applied by `remap_art()`:

```
1  -> 6
12 -> 4
13 -> 7
```

identity for every other index. This is a **strict subset** of the
`PALETTE_REMAP_EXPECTED` table already pinned for Tails in
`../characters_staging/gen_characters.py` (same two source/target indices for
1->6 and 12->4 and 13->7).

## Knuckles needs a second, raw variant

`knuckles_main.bin`'s palette is byte-identical to S3K's own character
palette, so no single re-indexed variant can serve both the Sonic/Tails line
and Knuckles. The three colours the dust uses (S3K indices 1, 12, 13) sit at
disjoint indices between the two target palettes; the Sonic/Tails line and the
Knuckles line agree only at indices 0, 10 and 11, none of which is a colour the
dust art uses. A Knuckles build of this importer would need to emit a **raw**
(non-remapped) copy of the same donor tiles instead of applying `REMAP`. Not
implemented here — this task ships only the Sonic/Tails variant.

## Determinism

No timestamps, no RNG, no filesystem-order dependence (the donor `.asm`
pointer tables fix frame order). `tools/test_gen_dust.py::test_deterministic`
runs the importer twice into separate directories and asserts byte-identical
output for all four generated files.
