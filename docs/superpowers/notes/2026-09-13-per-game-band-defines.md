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

## 2. Measured, against section 1

Everything below section 1 was written after building. Control = aeon `62fe88f7` built by
`tools/landing_build.sh` in this worktree (`finished=0`); its four md5s match the brief's
09:51Z readings exactly.

| image | control | after | size delta | predicted |
|---|---|---|---|---|
| `s4.bin` | `d83e2780169264af93b0b0276423ad1c` 820223 | **identical** | 0 | identical |
| `s4.debug.bin` | `6211829d4b067b0130e4c693f6528589` 846601 | **identical** | 0 | identical |
| `demo.bin` | `a8a84b6f22dc0cc408683a37af08fb2f` 97109 | `1774d78cf82982c3faaf27f5fb809161` 97058 | **-51** | -4 |
| `demo.debug.bin` | `b4443af7e918ea895d91e8c3f15a2456` 103501 | `339f50a332426b138082307d5186bea6` 103449 | **-52** | 0 |

**sonic4: the prediction held.** Both images byte-identical.

**demo: the CODE moved exactly as derived, and the ROM size moved for two reasons the derivation
missed.** A label-by-label diff of the listings (every label present in both, 1507 / 1851):

- ROM labels: delta 0 up to `Parallax_Step4_Fill`'s `.not_first` (the first label after the
  copy run), then **-4** (plain). In the debug shape, -4 from there and back to **0** from
  `Parallax_InstallScratch`'s `.copy`, which is the +4 of the x16 -> x5 `mul_const`. Both
  exactly section 1.3's table.
- **Miss 1: the object bank is anchored at `$10000`.** Everything from `ObjCodeBase` on has
  delta 0, and `EndOfRom` is `$1121A` in all four demo listings. The -4 of code before the
  anchor is absorbed by fill and never reaches the file size. Section 1.3 predicted the label
  shift correctly and then wrongly carried it through to the image size.
- **Miss 2: the deb2 appendix lost three names.** The whole file-size delta is after
  `EndOfRom`: the appendix is 26939 -> 26888 bytes (plain) and 33331 -> 33279 (debug). With
  the remap mark, drift array and curve carry all zero-sized, `Parallax_Remap_State`,
  `Parallax_Drift_Acc`, `Parallax_Curve_Carry` and `Parallax_Shadow_Bands` are four labels on
  ONE address, `$FFFF8948`. That is the only new label-collision group in either demo listing.
  **deb2 keeps one symbol per address.** Two measurements establish it:
  - convsym's own text output (`-output log`) keeps all four names, 548 symbols before and
    after. So the listing reader does not drop them; the deb2 writer does.
  - Standalone deb2 over the raw listings: control 9059 bytes, new 9009, and the CONTROL
    listing with those three names deleted (from the label lines AND the symbol-table rows,
    since the symbol table is what convsym reads) is **exactly 9009**. So the three names are
    the whole delta. The 21 other RAM labels that shifted down by 8..780 bytes cost nothing.
    (The raw-listing delta is -50 against the ROM's -51 because sigil demangles `.emp` locals
    before convsym, which changes the Huffman input. The ROM's figure is the real one.)
  The same mechanism, in the other direction, is recorded for the band-drift adoption in
  `docs/ENGINE_ARCHITECTURE.md` ("the file-size deltas ... are the deb2 symbol appendix taking
  the new names"). I had written "the deb2 appendix keeps its size: same names" without testing
  what deb2 does with names that share an address.
- Consequence, runtime-irrelevant: the MD Debugger in demo prints one of the four names for
  `$FFFF8948`. All four are zero-length there.

**RAM: every predicted figure held.**

| label | control | after | delta |
|---|---|---|---|
| `Parallax_Drift_Acc` (both shapes) | `$FFFF8950` | `$FFFF8948` | -8 |
| `Parallax_Curve_Carry` | `$FFFF8990` | `$FFFF8948` | -72 |
| `Parallax_Shadow_Bands` | `$FFFF8994` | `$FFFF8948` | -76 |
| `Parallax_Shadow_Scroll_A` .. `Engine_RAM_End` (plain) | | | **-428** (`Parallax_State` 820 -> 392) |
| `Parallax_Scratch_Arm` .. (debug) | | | **-780** (also `Parallax_Scratch_Config` 542 -> 190) |

## 3. Obligation 1: the three contexts

The mechanism is sigil's `native::shape_defines` (read at sigil `origin/master` `962cec05`,
`crates/sigil-harness/src/native.rs` and `game_defines.rs`): the profile's built-in
`emp_defines` merged with the game's own `map.toml [defines]` rows, refusing a row that
shadows a built-in. Its doc comment says every `.emp` build and harvest path reads this merge.
Measured:

| context | verdict | evidence |
|---|---|---|
| emitted-`data` binding record layout | **VISIBLE** | `band_record`'s size folds `GAME_SCANLINE_CAPS` through the four counts; the twenty sonic4 scene records in `scene_registry.emp` lay out at 32 B per band from the sonic4 row, and both sonic4 images are byte-identical. A record that could not see the row would fail with `unknown name`, and one that folded it to 0 would change every record's bytes |
| `harvest_engine_ram_addresses` | **VISIBLE** | `engine/ram.emp` sizes its reservations from the row: `Parallax_State` is 392 B in `demo.lst` and 820 B in `s4.lst`, and `parallax.emp`'s span guards (resolved RAM spans against `sizeof(band_record)` and the counts) are green in all four shapes. Source agrees: the harvest builds with `shape_defines(profile, aeon)` |
| `harvest_engine_struct_offsets` | **NOT VISIBLE, and neither is any built-in define** | three spikes on `band_entry`, each `FAST=1 DEBUG=1 ./build.sh` on the clean tree and restored from HEAD: `bx_spike: [u8; 0]` passes the harvest (the build then fails later, in `build_program`, on 139 `[struct.missing-field] ... bx_spike` from `scene_dsl.emp`'s struct literals, which is the spike's own fault and proves the harvest stage was passed); `[u8; DEBUG & 0]` fails `harvest_engine_struct_offsets: layout band_entry: Some(Diagnostic { level: Error, message: "unknown name `DEBUG`", ... })`; `[u8; GAME_SCANLINE_CAPS & 0]` with the sonic4 row present fails with `unknown name `GAME_SCANLINE_CAPS``. Source agrees: the harvest calls `layout_struct_ambient(&file, &types_file.items, sname)`, which takes no define env |

**So the booking's premise was one-third wrong.** The 2026-08-20 `DEBUG` measurement drove
`BAND_EXT_N`, which sizes `band_record`, and `band_record` is deliberately not a
`STRUCT_OFFSET_TWINS` member, so that measurement never reached the struct harvest. Nothing in
this parcel needs the third context. Only the booking's optional Secondary item does
(folding the tails back onto `band_entry`), and that item is now blocked on a different sigil
gap from the one originally named. The ask is in section 6.

## 4. Design, guards, and what the tool layer needed

**One caps-shaped define, `GAME_SCANLINE_CAPS`, not four per-count rows.** Reasons, strongest
first:
1. One equality guards it against the contract in both directions and for every bit, so no
   bit of the define is ever unchecked. Four per-count toggles would each need their own
   two-way pin, and a future sizing tail would need a new row in every game.
2. sigil's game-row polarity audit (`audit_game_declared_polarity`) requires a boolean-shaped
   game row to take both 0 and 1 across the shipped shapes. `BAND_EXT_N` is 0 in both games,
   so a per-count row would fail it and need a sigil-side exemption, which is out of scope. A
   caps-shaped row takes two distinct non-boolean values (`0x0FDE`, `0`) and passes.
3. The knowledge of which bit sizes which tail stays in the engine, next to the tails.
Cost: changing a game's capabilities is now two lines (`game.emp` and `map.toml`), and the
build names the one that was forgotten. `Game.SCANLINE_CAPS` stays a bare literal in
`games/sonic4/config/game.emp`, byte-for-byte as it was, so the regex readers are untouched.

**The masks in the folds are literals**, per `docs/EMP_PITFALLS.md` §2. A module importing
`BAND_REMAP_N` gets a clone whose initializer re-evaluates in that module, where a `CAP_*` name
that does not resolve degrades silently. The define resolves everywhere.

**Guard site: engine-side, not per game. This departs from the brief's framing, and on
purpose.** A module-scope `ensure` in `engine/level/parallax.emp` sees both the define and
`Game.SCANLINE_CAPS` (measured: the guards evaluate, and fire, in both games). Every game that
reaches parallax therefore gets the guards without writing them. A per-game guard site would
have to be re-authored in each new game, and a game that forgot would carry exactly the
unchecked copy requirement 1 forbids. Demo needed no new game-side file.

| guard (`engine/level/parallax.emp`) | runner | red-first mutation (applied to one file, shown, restored from HEAD) | the failing message |
|---|---|---|---|
| G1 `GAME_SCANLINE_CAPS == Game.SCANLINE_CAPS` | sigil build (every shape, via `build.sh`) | M1 sonic4 row `0x0FDE` -> `0x0FFE` | `... is 4094 but this game's Game.SCANLINE_CAPS is 4062. Bits in the define that the game does not declare: 32. Bits the game declares that the define lacks: 0. ...` |
| G1 | same | M2 sonic4 row -> `0x07DE` | `... is 2014 but ... is 4062. ... does not declare: 0. Bits the game declares that the define lacks: 2048. ...` |
| G1 | same | M3 demo row `0` -> `0x0800` | `... is 2048 but ... is 0. Bits in the define that the game does not declare: 2048. ...` |
| G1 | same | M4 demo `game.emp` `SCANLINE_CAPS = DemoScenes_CapsFolded | $0040` | `... is 0 but ... is 64. ... Bits the game declares that the define lacks: 64. ...` |
| G2 literal masks == `CAP_*` | same | M5 `scene_dsl.emp` `CAP_BAND_DRIFT = $0080` -> `$1000` (demo) | `a CAP_* bit in engine/level/scene_dsl.emp moved (CAP_MULTI_DEFORM_TABLE 32, CAP_FACTOR_CURVE 64, CAP_BAND_DRIFT 4096, CAP_ROW_REMAP 2048; expected 32, 64, 128 and 2048) ...` |
| G3 `BAND_EXT_N` == its bit | same | M6 fold -> literal `1` (demo) | `BAND_EXT_N is 1 but this game's Game.SCANLINE_CAPS & CAP_MULTI_DEFORM_TABLE is 0: ...` |
| G3 `BAND_CURVE_N` | same | M7 fold -> `1` (demo) | `BAND_CURVE_N is 1 but ... & CAP_FACTOR_CURVE is 0: ...` |
| G3 `BAND_CURVE_N` | same | M8 fold -> `0` (sonic4) | `BAND_CURVE_N is 0 but ... & CAP_FACTOR_CURVE is 64: ...` |
| G3 `BAND_DRIFT_N` | same | M9 fold -> `0` (sonic4) | `BAND_DRIFT_N is 0 but ... & CAP_BAND_DRIFT is 128: ...` |
| G3 `BAND_REMAP_N` | same | M10 fold -> `1` (demo) | `BAND_REMAP_N is 1 but ... & CAP_ROW_REMAP is 0: ...` |
| existing span guard, over the NEW `ram.emp` folds | same | M11 `ram.emp` `BAND_REMAP_BYTES` mask `$0800` -> `$0020` (sonic4) | `Parallax_Shadow_Bands does not reserve what the shadow view needs: sizeof(band_record) x MAX_PARALLAX_BANDS = 512. ...` |
| `tools/band_geometry.py` mask cross-check | `python3 tools/band_geometry.py`; in lanes, `tools/test_band_geometry.py` (build.sh's pytest lane) | M12 `ram.emp` `BAND_DRIFT_BYTES` mask `$0080` -> `$0040` | `Unreadable: the band_drift tail's masks disagree: engine/level/parallax.emp BAND_DRIFT_N reads $0080, engine/ram.emp BAND_DRIFT_BYTES reads $0040, engine/level/scene_dsl.emp CAP_BAND_DRIFT is $0080` |
| `tools/test_band_geometry.py` | build.sh's pytest lane | M13 disable the cross-check in `band_geometry.py` | `1 failed, 10 passed`: `FAILED tools/test_band_geometry.py::test_refuses_a_ram_mask_out_of_step_with_parallax` |

All thirteen went red on the named message and restored clean; the runner log is
`.runlogs/redfirst.log` (script in the session scratchpad, reproduced by the table). Together,
G1 and G3 are both directions of the eight scene_registry.emp pins they retire, and they now
cover demo too. G1 is an equality over every bit, and each G3 is an equality of two 0/1
values.

**A gap the emp build cannot close, and where it is closed instead.** `engine/ram.emp`'s four
folds spell their own copies of the masks (the RAM harvest cannot import parallax.emp's counts
or scene_dsl's `CAP_*`). A wrong ram.emp mask fails the build only where it changes a game's
value: M11 is red because `$0020` is clear in sonic4. M12's swap to `$0040` is set in sonic4
and clear in demo, exactly like `$0080`, so it builds GREEN in both games. That case is closed
by `tools/band_geometry.py`'s textual cross-check, which the pytest lane runs on every build
through `test_counts_follow_the_contract_not_the_define` (the real tree fails to read). A
future game whose bits separate the two masks would also catch it in the emp build.

**The tool layer: the brief's escape hatch, recorded rather than taken silently.** The brief
said not to break the regex readers of `const SCANLINE_CAPS`, and to stop if a tool reader had
to change. `SCANLINE_CAPS` is untouched. But five tools also regex-read the RETIRED LITERALS,
and against the new tree, unchanged, they refuse loudly (exit codes and text measured before
any tool edit):

- `row_remap_gate.py` (a strict build gate, both games): `UNMEASURABLE — could not read `BAND_EXT_N``, exit 2
- `band_drift_golden.py` (a strict build gate): `UNMEASURABLE — cannot find `const BAND_DRIFT_BYTES` in engine/ram.emp ...`, exit 2
- `parallax_hscroll_probe.py` (imported by the pytest lane): `cannot find `const BAND_EXT_BYTES` in engine/ram.emp ...` at import
- `left_col_mask_probe.py`: `FAIL: cannot find `const BAND_EXT_BYTES` in engine/ram.emp ...`
- `row_remap_witness.py` reads the same four `pub const BAND_*_N = (\d+)`

No design keeps those regexes working. The value they read no longer exists without naming a
game, and a derived initializer that happened to start with a digit would be worse: the old
regex would read its first literal and lie for demo. So the change is forced by the subject,
not a degradation. All five now read `tools/band_geometry.py`, one reader that takes the game,
follows exactly the new spelling, refuses the retired literal, and cross-checks the masks
three ways. Two of those probes were already wrong before this parcel: their hand sums stopped
early (left_col 20, hscroll 24, against a real stride of 32) and are right now.
`row_remap_gate`'s undeclared arm used to print "no non-NULL remap tail (both checked)", and
demo's record no longer has a remap field, so it now says so instead of claiming a read that
cannot happen.

## 5. Landing verification

**First landing run, tip `d566ab64`: `finished=1`, and what it caught was mine.** All four
shapes failed their pre-build pytest lane on one test,
`tools/test_citation_form.py::test_live_citations_resolve_to_something` ("6 of 354 live
`.emp:LINE` citations point at nothing"). My parallax.emp edits had shifted six cited lines
onto blank lines. Every other test passed (2605 passed, 1 failed, per shape). Because pytest
runs first, that run never reached the expect-fail lane, the sigil build or the post-sigil
gates, so it proves nothing about them. The FAST builds before it had skipped those lanes too.

That test only sees citations that land on BLANK lines. Enumerating every live citation into
the four `.emp` files I edited (with the test's own collector, control against HEAD) found 56,
and 51 of them had moved onto different text. Fixed in `357c0b5e`:
- 8 now cite by symbol: the six the test named, plus two whose cited text I rewrote. Four of
  the eight were already wrong at control: scene_dsl's "lock sentinel" pointed at
  `copy_band_entry_fwd`, the hscroll probe's "never lerped" at a `band_ext` offset const,
  scene_dsl's `pcfg_transition` test at a banner line, and structs.emp's evenness ensure at a
  banner line. The symbol form corrects them.
- 42 were re-pointed mechanically to the line now holding the text they cited at control, and
  verified: none shows different text than it did at control. Each pointer is preserved exactly,
  right or wrong, and its form is left alone.
- 5 had not moved.

The edits are comment-only (the one code line touched is an instruction's trailing comment),
and all four FAST images are identical to the previous commit.

**Second landing run, tip `357c0b5e`: `finished=1` again, and again it was a predicted number
caught by a pin I had not found.** All four shapes built, and every build-lane gate passed
(2606 passed per shape pytest lane; `row_remap_gate`, `band_drift_golden` and the rest green).
The four images: s4 `d83e2780…` 820223 and s4.debug `6211829d…` 846601 (both identical to the
control), demo `1774d78c…` 97058, demo.debug `339f50a3…` 103449. The needs_build lane then
failed one of its 14: `test_effects_gates_segments.py::test_segmented_parent_checks_the_row_set_it_aggregated`,
whose `demo_witness` row runs `tools/demo_specialization_witness.py`:
`FAIL  Parallax_Step4_Fill emits 188 bytes in demo, pinned at 192 (-4). ... RE-DERIVE why it moved before touching the pin.`

That -4 is exactly section 1.3's row for `Parallax_Step4_Fill` (+6 for the x10 `mul_const`, -10
for the shorter copy run), derived before any build. The pin's own comment tied 192 to "32 B
record stride since CAP_ROW_REMAP", which was demo's record only while the counts were
engine-wide. Re-pinned to 188 with that derivation written beside the number. I had enumerated
tool readers of the literals and missed this one: it pins PROC SIZES, not constants, so no
grep for `BAND_*` finds it. The image half of that witness exists for exactly this kind of
unannounced byte movement, and it worked.

**Final landing run, tip `af246d84`: `finished=0`.** `tools/landing_build.sh`, log
`.runlogs/landing-af246d84-1052.log` (worktree-local, gitignored), 10:52Z to 11:05Z.

| shape | EXIT | size | md5 | pytest lane (pre-sigil) | post-sigil marked half | expect-fail |
|---|---|---|---|---|---|---|
| s4 | 0 | 820223 | `d83e2780169264af93b0b0276423ad1c` (= control) | 2606 passed, 2 skipped | 5 passed, 9 skipped | 55/55 |
| s4.debug | 0 | 846601 | `6211829d4b067b0130e4c693f6528589` (= control) | 2606 passed, 2 skipped | 6 passed, 8 skipped | 55/55 |
| demo | 0 | 97058 | `1774d78cf82982c3faaf27f5fb809161` | 2606 passed, 2 skipped | 1 passed, 13 skipped | 55/55 |
| demo.debug | 0 | 103449 | `339f50a332426b138082307d5186bea6` | 2606 passed, 2 skipped | 1 passed, 13 skipped | 55/55 |
| needs_build lane | 0 | | | 14 passed; "OK — all 14 marked test(s) ran and passed" | | |

The pytest lane is 2606 per shape against the control's 2595: +11, the new
`tools/test_band_geometry.py`. `[call.flag-result-unused]` / `[call.result-invalid-path]`: 0 hits
in the log, the same as the control. `row_remap_gate` reads sonic4 at `sizeof(band_record)=32`
and demo at `10` with no remap field, both OK. The assembler is `sigil 0.1.0 (1532b72f)`.
sigil md5 `739016647ad1ab92f4d072e3013b8818` and emit_sound_blob md5
`1f936ebb805d39eae23844ee66fb458a`, read at the start (09:54Z), mid-parcel (10:27Z) and at the
end (11:02Z): unchanged.

**Not run, and owed by the overseer:** no emulator was used. The runtime consequence (demo's
`Parallax_Init` now clears 98 longs instead of 205, and its walker strides by 10 instead of 32)
is exercised by no lane, because demo never calls `Parallax_Update`. The effects-gate ritual is
not triggered: no file under `engine/effects/`, `engine/level/bg_anim.emp` or
`engine/system/buffers.emp` changed, and `tools/effects_gates.py` and the nightly call none of
the tools this parcel edited.

## 6. Asks, and what is left

**sigil (none blocks this branch; all are theirs to act on):**

1. **`the_shipped_maps_game_declared_rows_are_polarity_covered` goes red when their aeon
   reference tree includes this landing.** `crates/sigil-harness/tests/game_config_defines.rs`
   asserts `keys.is_empty()` ("no shipped map declares a row ... When the first row lands this
   line is the one that changes, in the same commit as the row"). After this landing the audit
   returns `{"GAME_SCANLINE_CAPS"}`. It should pass the audit itself: value-shaped, `4062`
   across the five sonic4 shapes and `0` across the two demo shapes, so two distinct values.
   The ask is the expectation change to `== {"GAME_SCANLINE_CAPS"}`. Their tree reads aeon
   through `AEON_DIR` / `provision-aeon-ref.sh`, so nothing breaks until they re-provision.
2. **The demo images moved** (-51 / -52 B, deb2 appendix only; sonic4 is identical). Anything
   on their side that pins demo's image identity needs the routine repin at their next
   reference advance.
3. **Optional, demand-gated: a define env for `harvest_engine_struct_offsets`.** Context: the
   `STRUCT_OFFSET_TWINS` harvest lays each twin out with
   `layout_struct_ambient(&file, &types_file.items, sname)`, which has no define env, so a
   harvested struct's layout cannot name any define, built-in or game. Error text:
   `harvest_engine_struct_offsets: layout band_entry: Some(Diagnostic { level: Error, message:
   "unknown name `DEBUG`", ... })`. Reproduction: add `bx_spike: [u8; DEBUG & 0],` as the last
   field of `band_entry` in `engine/level/parallax.emp` and run `FAST=1 DEBUG=1 ./build.sh`.
   The only consumer would be the booking's Secondary item, which aeon has not asked for, so
   this is a record, not a request.

**aeon, booked in `docs/DEFERRED_WORK.md`:** demo still reserves the 256-byte
`Waterline_Art_Buffer` although it does not declare `CAP_ROW_REMAP`. Gating it on the same
define is now possible, and it is its own byte-moving decision.

**Stale prose noticed and NOT fixed.** Each was already wrong before this parcel, so it is
listed, not fixed:
- `engine/level/scene_dsl.emp` ~2375 / 2387 / 2398: say an unraised capability "keeps
  BAND_CURVE_N at 0 / BAND_DRIFT_N at 0 and the four canonical images byte-identical". Curve
  (2026-08-26) and drift (2026-09-02) have been adopted by sonic4 since.
- `games/sonic4/data/effects/scene_registry.emp` header (~45-48): "This game does not [declare
  CAP_MULTI_DEFORM_TABLE], so every array below is the size it has always been". True of the
  extension, but sonic4's records carry three other tails and are 32 bytes.
- `tools/left_col_mask_probe.py:163` ("the shipped stride is 20") and
  `tools/parallax_hscroll_probe.py:186` ("the live stride is 20"). Both are 32; the paragraph
  added under each says so.
- `docs/ENGINE_ARCHITECTURE.md` RAM table under "Band ceiling" (~2745-2756): the 2026-08-27
  snapshot (`Parallax_Shadow_Bands` 160, total 328). sonic4 is now 512 / 820 and demo 160 / 392.
- `tools/effects_gen.py:1990` docstring: "(sonic4 $01DE, demo 0)". sonic4 is `$0FDE`.
- `docs/benchmarks/scanline-p3/EXTENDED-RECORD.md` §3: "A build DEFINE is visible in all
  three". Corrected where it is cited (DEFERRED_WORK, EMP_PITFALLS §9) but not in the dated
  benchmark itself.
