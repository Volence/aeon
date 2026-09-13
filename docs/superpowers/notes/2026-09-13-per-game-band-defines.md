# Per-game band-record sizing: `GAME_SCANLINE_CAPS` as a `map.toml [defines]` row

Branch `parcel/per-game-band-defines`, base aeon `origin/master` `62fe88f7`, sigil `1532b72f`
(sigil md5 `739016647ad1ab92f4d072e3013b8818`, emit_sound_blob md5
`1f936ebb805d39eae23844ee66fb458a`).

This file is written in two passes. Section 1 (the derivation) was written and committed
BEFORE any source edit and before any post-change build. Later sections record what was
measured. If a measured number disagrees with section 1, the disagreement is explained, not
adopted.

## 0. Was there a subject? (measured on the control, before any edit)

The brief's premise was that demo pays for widened band records it can never use. Read off
the control's `demo.lst` and `s4.lst` (both built by `tools/landing_build.sh` at `62fe88f7`):

| label | demo.lst | s4.lst |
|---|---|---|
| `Parallax_State` | `$FFFF88A0` | `$FFFF88A0` |
| `Parallax_Remap_State` | `$FFFF8948` | `$FFFF8948` |
| `Parallax_Drift_Acc` | `$FFFF8950` | `$FFFF8950` |
| `Parallax_Curve_Carry` | `$FFFF8990` | `$FFFF8990` |
| `Parallax_Shadow_Bands` | `$FFFF8994` | `$FFFF8994` |
| `Parallax_Shadow_Scroll_A` | `$FFFF8B94` | `$FFFF8B94` |
| `Parallax_State_End` | `$FFFF8BD4` | `$FFFF8BD4` |

Demo's `Parallax_State` is 820 bytes, identical to sonic4's, including a 512-byte shadow
band array (32 bytes x 16 bands), a 64-byte drift accumulator array, a 4-byte curve carry
and an 8-byte remap mark, although demo's `SCANLINE_CAPS` folds to 0 and it declares none of
the four tail capabilities. **So demo pays, and the parcel has a subject. The payment is RAM,
not ROM record bytes:** demo registers no scenes, so it emits no band record at all. What it
pays in ROM is code shape (section 1.3), not data.

## 1. The byte derivation (written before building)

### 1.1 The inputs

`band_entry` = 10 (`BAND_ENTRY_LEN`), `band_ext` = 10, `band_curve` = 10, `band_drift` = 4,
`band_remap` = 8 (the `(size: N)` claims in `engine/level/parallax.emp`).
`MAX_PARALLAX_BANDS` = 16. `PARALLAX_CFG_HDR_LEN` = 30 (sizeof(parallax_config)).

| game | `Game.SCANLINE_CAPS` | EXT ($0020) | CURVE ($0040) | DRIFT ($0080) | REMAP ($0800) | sizeof(band_record) |
|---|---|---|---|---|---|---|
| sonic4 | `$0FDE` | 0 | 1 | 1 | 1 | 10+0+10+4+8 = **32** |
| demo | 0 (the fold of an empty registry) | 0 | 0 | 0 | 0 | **10** |

Today both games compile with the sonic4 column, because the four counts are engine-wide
literals.

### 1.2 sonic4: expected BYTE-IDENTICAL (both shapes)

Every one of the four counts keeps its value for sonic4 (derived from `$0FDE`: 0, 1, 1, 1),
so every size, stride, displacement, reservation and `mul_const` election is unchanged.
The one new thing the build sees is a define row. A define reaches the listing as a `-`
equate row plus a `DIGEST-DEFINE` line (sigil `0aa1e2bc`), and `append_deb2_appendix`
filters every equate out at the deb2 boundary, so the ROM's symbol appendix cannot grow.
No `pub const` name is added or removed (the four `BAND_*_N` keep their names, only their
initializers change), so no listing label moves either.

Prediction: `s4.bin` and `s4.debug.bin` md5 unchanged. `s4.lst`/`s4.debug.lst` gain one
`EQU GAME_SCANLINE_CAPS` row and one `DIGEST-DEFINE` line and are otherwise unchanged in
their label set.

### 1.3 demo: the ROM

Demo emits no band record, so no ROM data changes size. It does emit `Parallax_Update`,
`Parallax_Step4_Fill`, `Parallax_Fill_PerLine` and `Parallax_Init` (all present in the
control `demo.lst`), and the code in them that is NOT behind a capability gate is shaped by
`sizeof(band_record)`. Every ungated use, and what 32 -> 10 does to it:

| site (`engine/level/parallax.emp`) | proc | sonic4 (32) | demo (10) | delta |
|---|---|---|---|---|
| `:1092` `move.w #PARALLAX_STATE_LONGS-1, d0` | Parallax_Init | `#204`, 4 B | `#97`, 4 B | 0 (explicit `.w`, not a moveq candidate) |
| `:1987` `adda.l #sizeof(band_record), a1` | Parallax_Update | 6 B | 6 B | 0 |
| `:2053` `lea sizeof(band_record)(a1), a4` | Parallax_Step4_Fill | 4 B | 4 B | 0 |
| `:2063` `adda.w #sizeof(band_record), a4` | Parallax_Step4_Fill | 4 B | 4 B | 0 (both > 8, no addq) |
| `:2078` `mul_const.w d3, #sizeof(band_record), d5` | Parallax_Step4_Fill | x32 is a power of two: `lsl.w #5,d3`, **2 B** | x10 has two set bits: the word LTR chain `move.w d3,d5 / lsl.w #2,d3 / add.w d5,d3 / (one doubling)`, **8 B** (beats `mulu.w #10`'s ~46 cycles at ~22-26) | **+6** |
| `:2081` `copy_band_entry_fwd(a1, a4)` | Parallax_Step4_Fill | 32/4 = 8 x `move.l (a1)+,(a4)+`, **16 B** | 10 = 2 x `move.l` + 1 x `move.w`, **6 B** | **-10** |
| `:2083`, `:2105` `-sizeof(band_record)(a4)` | Parallax_Step4_Fill | 4 B each | 4 B each | 0 |
| `:3765` `lea sizeof(band_record)(a1), a1` | Parallax_Fill_PerLine | 4 B | 4 B | 0 |
| `:4020` `mul_const.w d1, #sizeof(band_record)/2, d2` | Parallax_InstallScratch (**DEBUG only**) | x16: `lsl.w #4,d1`, **2 B** | x5: `move.w d1,d2 / lsl.w #2,d1 / add.w d2,d1`, **6 B** | **+4** (debug only) |

Every other use of `sizeof(band_record)`, `offsetof(band_record, ...)`, `Parallax_Drift_Acc`,
`Parallax_Remap_State` and `Parallax_Curve_Carry` in code sits inside an
`if (Game.SCANLINE_CAPS & CAP_*) != 0` block, which demo already elides (checked by walking
the enclosing blocks of every site). RAM operands are all short-absolute (`$FFFF8xxx`); the
labels after `Parallax_State` move DOWN by 428 bytes (section 1.4) and stay at or above
`$FFFF8A28`, so none crosses below `$FFFF8000` into the long-absolute form.

Prediction:
- `demo.bin`: **-4 bytes** (Step4_Fill: +6 - 10). Control 97109 -> **97105**. md5 changes
  (bytes and the header checksum).
- `demo.debug.bin`: **0 bytes** (Step4_Fill -4, InstallScratch +4). md5 changes.
- Both demo images: every ROM label after `Parallax_Step4_Fill`'s copy run moves by -4
  (plain), and in the debug shape moves by -4 between Step4_Fill and InstallScratch and by 0
  after it. The deb2 appendix keeps its size: same names, and the address order within each
  run is preserved.
- Caveat named in advance: a branch whose span crosses the copy run shrinks by 4 and could
  in principle relax differently, and a section with an alignment of 8 or more after the run
  could change its padding. Either would show as a size delta other than the above, and is
  to be explained from the listing, not adopted.

### 1.4 demo: the RAM

| reservation (`engine/ram.emp`) | control | after | delta |
|---|---|---|---|
| `Parallax_Remap_State` (`REMAP_STATE_LONGS` longs) | 8 | 0 | -8 |
| `Parallax_Drift_Acc` (`DRIFT_ACC_LONGS x 16` longs) | 64 | 0 | -64 |
| `Parallax_Curve_Carry` (`CURVE_CARRY_WORDS` words) | 4 | 0 | -4 |
| `Parallax_Shadow_Bands` (`(10 + tails) x 16`) | 512 | 160 | -352 |
| **`Parallax_State` total** (`4 x PARALLAX_STATE_LONGS`, 205 -> 98) | 820 | 392 | **-428** |
| `Parallax_Scratch_Config` (DEBUG only, `30 + record x 16`) | 542 | 190 | -352 |

Prediction: demo `Parallax_State_End - Parallax_State` = 392; `Engine_RAM_End` moves by
-428 in `demo.lst` (`$FFFFB842` -> `$FFFFB696`) and by -780 in `demo.debug.lst`.
sonic4 RAM: unchanged.
