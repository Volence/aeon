# PUBLISH-BAND-RECORD-LEN: the band stride is one equate (2026-09-25)

Closes `PUBLISH-BAND-RECORD-LEN` (docs/DEFERRED_WORK.md). Branch `parcel/band-record-len`.

## The equate

```
EQU band_record_len = $00000020     s4.lst, s4.debug.lst   (sonic4)
EQU band_record_len = $0000000A     demo.debug.lst         (demo)
```

Defined in `engine/level/parallax.emp`, directly under `pub struct band_record`:

```
pub equ band_record_len = sizeof(band_record)
```

It is derived from the struct and never typed. The name follows the listing's existing
spelling for a struct size (`band_entry_len`, `parallax_config_len`, `SST_len`): bytes per
record, never a band count. Oracle's request used the same name.

## Did sigil's equate publication already cover it? Partly, and this is the one line beside it

Checked before building, as the booking asked. The `band_entry_*` rows come from sigil's
`STRUCT_OFFSET_TWINS` harvest (`sigil-harness/src/native.rs`, `harvest_engine_struct_offsets`).
That harvest lays out a fixed list of structs ambiently, with only `types.emp`, no defines and
no contract. `band_record`'s size folds the `GAME_SCANLINE_CAPS` define, so that harvest could
not size it per game. parallax.emp's own banner explains why `band_record` is deliberately
kept out of that list.

A `pub equ` in an ordinary module does not have that limit. It mints a link-level `EquSym`, and
sigil-link's listing writer puts every `EquSym` in the Equate Table. That is the same route as
`DPLC_PEAK_TILES_*` and `SceneBudget_*`. parallax.emp lowers once per game, with that game's
defines and contract, so the value is per game by construction. No mechanism was needed, and
nothing changed in sigil.

**Shape-blind harvest hazard (STRESS-CLAMP-EQU-WRONG): not affected.** This row does not come
from `harvest_engine_constants`. Measured: each listing carries its own game's value (32, 32
and 10 above). The source derivation `tools/band_geometry.record_stride(game)` agrees for both
games.

## Byte identity (same assembler: `sigil` release binary, built 17 Sep 04:11, untouched)

| artifact        | before (tip 885a0220)  | after (equate added)   |
|-----------------|------------------------|------------------------|
| s4.bin          | 6d1af7a3, 821479 B     | 6d1af7a3, 821479 B     |
| s4.debug.bin    | 62238a15, 848075 B     | 62238a15, 848075 B     |
| demo.debug.bin  | ce922bf7, 104707 B     | ce922bf7, 104707 B     |

The listing diff, before against after, is exactly: one new `EQU band_record_len` row, the
equate count +1 (797 to 798 in s4.debug; 575 to 576 in demo.debug), and parallax.emp's
source-digest line plus the aggregate digest.

## Consumers

The stride had been worked out five different ways in ten tools. All ten now read the
published row through one reader, `tools/band_geometry.published_stride(lst)`. It raises
`Unreadable` when the row is absent or duplicated, or when it is smaller than the same
listing's `band_entry_len`.

| tool | what it did before | now |
|---|---|---|
| `parallax_hscroll_probe.py` | source sum (`record_stride("sonic4")`) at import | `install_stride(lst)` in main() before any boot. The import-time source value stays for the offline fixture tests, and a disagreement between the two is refused. |
| `parallax_cost_probe.py` `set_stride` | `Parallax_Shadow_Bands` span / MAX_PARALLAX_BANDS | reads the published row. Takes the listing, not `sym`. |
| `parallax_hscroll_identity.py` | `pcp.set_stride(sym)` (span) | `pcp.set_stride(args.lst)` |
| `curve_probe.py` | its own span division, plus a **transcribed `20 * 8`** shadow read and slice | `pcp.set_stride(args.lst)`. The shadow read uses the installed stride. |
| `deform_own_cost_probe.py` | `derive_stride(sym)` (span) | `pcp.set_stride(args.lst)`. `derive_stride` is deleted. |
| `left_col_mask_probe.py` | source sum | published row |
| `parallax_scratch_probe.py` | **typed `BAND_REC = 32`** (wrong for demo) | published row, installed in main(). The module value is `None`. |
| `band_drift_golden.py` | hand sum of the ram.emp mirrors | published row. The source sum remains only as a check on its source-derived drift offset. |
| `row_remap_gate.py` (build.sh post-sigil gate, every shape) | source sum | published row. The source sum remains only as a check on its source-derived `br_remap` offset. |
| `row_remap_witness.py` | source sum | as row_remap_gate |

Out of scope and left alone: the readers of tail **offsets** and **counts**
(`band_geometry.tail_counts`/`tail_offset`, and the field offsets in the three tools that keep
a source cross-check). Those are separate facts from the stride. `parallax_scratch_probe.py`'s
`CFG_HDR = 30` is a typed `sizeof(parallax_config)`. The listing already publishes it as
`parallax_config_len`, but this parcel only touched the stride.

## Red-first, shown on disk and restored from the commit

1. Mutation, on disk (`git diff`): `-pub equ band_record_len = sizeof(band_record)`.
2. Rebuilt s4 plain, s4 debug and demo debug (FAST). `grep -c band_record_len` gives 0 in
   all three listings.
3. All eleven consumer invocations refused, each naming the missing row. In every one the
   stride read comes before its emulator boot in main(), and every one exited within seconds:
   hscroll 1, cost 1, identity 1, curve 1, deform 1, left_col 1, scratch 1 (UNMEASURABLE),
   band_drift_golden 2 (UNMEASURABLE), row_remap_gate sonic4 2, row_remap_gate demo 2,
   row_remap_witness 2 (REFUSED).
4. `test_the_build_publishes_this_games_record_stride`: 3 failed (s4.lst, s4.debug.lst,
   demo.debug.lst).
5. Restored with `git restore --source=HEAD engine/level/parallax.emp` from commit `949d29d8` (the tools commit; the equate itself landed in `b6cafac9`),
   then rebuilt.
6. Green: row_remap_gate sonic4 0 (`sizeof(band_record)=32`), row_remap_gate demo 0 (`=10`),
   band_drift_golden 0 (stride 32), left_col_mask_probe --claims 0 (stride 32). In-process,
   the installer that main() calls before booting gives: hscroll 32, cost_probe 32 on s4.debug
   and 10 on demo.debug. hscroll_probe given demo.debug.lst **refuses** (10 against sonic4's
   32), which is the transcription class this closes.

## Tests (runner: build.sh's pytest lanes; the needs_build row runs post-sigil)

`tools/test_band_geometry.py` adds nine tests:

- five reader cases over listing text written in the test: a control, no row, a duplicated
  row, a record shorter than its prefix, and a missing file;
- one `needs_build` row per listing (`s4.lst`, `s4.debug.lst`, `demo.debug.lst`). Each checks
  the published row against `record_stride(game)`, a separate source derivation that never
  reads a listing;
- one power check: the two games' source strides differ, so a listing that published the
  other game's stride cannot pass.
