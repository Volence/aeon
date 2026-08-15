# Gate evidence — HBlank schedule local removal

Parcel: `docs/superpowers/plans/2026-08-16-hint-schedule-local-removal.md`
Design: `docs/superpowers/specs/2026-08-16-hint-schedule-local-removal-design.md` (rev 2)

Every gate here is STRUCTURAL — memory reads, derived arithmetic, breakpoints. None of it is a
screenshot. Oracle pixel capture is not usable in this lane (three capture protocols were each
killed by their own determinism control, and `BgAnim_Update` rides the lag-immune `Logic_Tick`, so
cross-build pixel comparison is unsound). Where a number is DERIVED, the derivation is shown; a
gate whose expectation was copied rather than derived is how the last two parcels shipped an
off-by-one.

---

## Task 1 — the 5-word patch table (comptime)

**Guard 10 (`check_rec_layout`) is not vacuous.** Two poison runs, each reverted immediately after:

Poison A — `record_words` returns one word too many (`n = 3` instead of `2`):

```
[Error] raster program: record 2 spans words 5..15 but the next record's arm word is at 14 —
        rec_len and the emitted layout disagree, so the builder would copy a misaligned slice
[Error] raster program: record 3 spans words 14..22 but the next record's arm word is at 21 — ...
```

Poison B — `patch_table` emits `rec_off + 2` (a uniform base error, which is precisely the
counterexample a design reviewer raised against an offset-only cross-check):

```
[Error] raster program: the patch table says record 2 starts at byte 12 but the emitted body puts
        its arm word at byte 10. The builder copies from the TABLE's offset, so this is the
        difference between copying the record and copying a misaligned slice of its neighbour.
```

Poison B is what motivated hardening the guard mid-task: as first written, `check_rec_layout`
recomputed `arm_word_index`/`record_words` and compared them to the emitted image, but never read
what `patch_table` actually emitted — so a wrong table sailed through and only a hand twin could
catch it, for pinned fixtures only. The guard now closes table -> derivation -> image.

ROM CRC is unchanged across the hardening (`bb5ca5aa` before and after), confirming comptime guards
move zero bytes.

---

## Task 2 — `Raster_BuildSchedule` replaces the patcher

**Premise:** with nothing suppressed, the builder must reproduce exactly what the patcher produced.

**Pinned inputs** (not "whatever the camera was doing" — the live buffer carries RUNTIME lines, and
the authored template line 100 is NOT what a free-running camera yields):

| input | value | how |
|---|---|---|
| `Debug_Scene_Freeze` | 1 | skips `Camera_Update`, so a written camera stays put |
| `Camera_Y` | 144 | the boot value, left alone |
| `Effects_World_Y[0]` | 244 | written |
| `Effects_World_Y[1]` | 360 | written |

**Latch readback** (`Effects_Screen_L`, `$FF8AC2`): `0064 00D8` = 100 and 216. Both anchors minus a
camera of 144, confirming the freeze held and the latch ran.

**Derived expectation.** Fire line = screen line - 1, so channel 0 fires at 99 and channel 1 at 215
(216 is inside its 216..223 band, so no clamp). The arm word written at record `i` schedules the gap
that lands record `i+2`, so the SLOT is two records back while the LINE delta is one record back:

- priming record 0's arm = `$8A00 | (99 - 1 - 1)` = `$8A61`
- priming record 1's arm = `$8A00 | (215 - 99 - 1)` = `$8A73`
- records 2 and 3 park (`$8AFF`) — nothing follows them

**Read** (`Raster_Active_Buf` -> `$FF89A2` = `Raster_Buf_A`, 48 bytes):

```
0004 8A61 0000 8A73 0000 8AFF 0002 0000 8C89 0004 C048 0000 0002 0048
8AFF 0001 0002 4002 0010 0000 0043 8AFF FFFF 0000
```

mask `%0100`; priming arms `$8A61` / `$8A73` as derived; record 2 parked with `OP_SET_REG $8C89` +
`OP_PAL_REGION` (command `$C0480000`, count-1 = 2, stage offset 72); record 3 parked with `OP_CRAM`
carrying the VSRAM command `$40020010` and value `$0043`; terminator `$8AFF $FFFF`. Every op word
matches `OJZ_TC_HAND`'s bodies.

Had the design draft's original arithmetic shipped — the two-back SLOT paired with the two-back
LINE — `arm1` would read `$8AD5` here.

**Cross-ROM control.** Master (`77801f78`) built to a scratch worktree, `s4.debug.bin` CRC
`34078a94` (matching the session handoff, so it is genuinely master), same frozen camera, same two
written anchors, same latch readback (`0064 00D8`). Master's patcher writes into `Raster_Buf_B`
(`$FF8A22`) and never swaps; the builder had swapped to `Buf_A`. Contents:

```
master  Buf_B: 00048A6100008A7300008AFF000200008C890004C0480000000200488AFF0001000240020010000000438AFFFFFF0000
branch  Buf_A: 00048A6100008A7300008AFF000200008C890004C0480000000200488AFF0001000240020010000000438AFFFFFF0000
```

**Byte-identical.** This comparison is sound in a way a pixel comparison would not be: the buffer is
a pure function of (template, anchors, camera), and all three are pinned.

### Two behaviours that are NOT identical to master, by design

1. **Suppression is already reachable in play.** `Camera_Y` is clamped to `[0, Camera_Y_Max]`, so
   with OJZ's anchors channel 1 (anchor 314, `band_hi` fire 222) suppresses whenever
   `Camera_Y < 91`, and channel 0 (anchor 224, `band_hi` 213) whenever `Camera_Y < 10`. Master
   clamps DOWN to `band_hi` there. Spawn is 144, so the pinned gate above is unaffected; a
   free-roaming climb will show channel 1's vscroll split vanishing rather than pinning at 223.
   That is Task 4's semantics arriving early for part of the camera range.
2. **`Raster_Active_Buf` alternates A/B every frame** now that the builder swaps, where master held
   Buf_B for the whole lifetime of a patched program. Anything reading the buffer must go through
   `Raster_Active_Buf` rather than assuming Buf_B.

### A sigil finding worth booking separately

`lea -RASTER_BUF_SIZE(a2), a2` — a NEGATED NAMED CONSTANT in a displacement — is DROPPED by sigil's
contract-closure walk (reported as `Raster_BuildSchedule: 2` dropped instructions, gate-fatal).
Bisected: `-128` resolves, `-RASTER_BUF_SIZE` does not. The instruction lowers correctly; it is the
ANALYSIS that goes blind, which makes this a gate-blindness bug rather than a codegen one. Worked
around with `suba.w #RASTER_BUF_SIZE, a2`, this tree's existing idiom (`plane_buffer.emp:194`,
`section.emp:324`, `tile_cache.emp:453`).
