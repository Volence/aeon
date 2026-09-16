# Regions part 2, step 2 — the background blob turns row-major, and the row streamer arrives with no caller

Parcel `parcel/regions-p2-step2`, based on aeon master `6a7e4464`.
Spec: empyrean `origin/main:docs/superpowers/specs/2026-09-14-regions-part-2-design.md` §4.2
(option R), §1a items 1 and 2, step table row 2.
**No emulator was used.** The step's own gate, BG-NT-IDENTICAL, needs one and is TAGGED below,
not claimed.

## What landed

| what | where |
|---|---|
| the transpose DELETED — the blob ships in the editor's own row-major order | `tools/inject_editor_bg.py` |
| `BG_Init`'s nametable blit → one linear autoinc-`$02` `move.l` run | `engine/level/bg.emp` |
| `Section_RedrawPlanes`' Plane B half → the same shape | `engine/level/section.emp` |
| `Draw_BG_TileColumn` DELETED; `Draw_BG_TileRow` added, no caller | `engine/level/plane_buffer.emp` |
| the streamed-region / V-deform exclusion, as a ROM-level refusal | `tools/test_bg_stream_vdeform_exclusion.py` |
| the two other readers of the byte order | `tools/test_perspective_floor.py`, `tools/perspective_floor_witness.py` |
| doc sync | `docs/ENGINE_ARCHITECTURE.md`, `docs/ART_PIPELINE_CONTRACT.md`, `docs/DEFERRED_WORK.md`, `docs/EMP_PITFALLS.md` |

**Row-major is the Plane B nametable's own VRAM order**, so the "row loop" §4.2 asks for
degenerates to a straight memcpy: 2048 longwords behind one command setup instead of 64
per-column setups and an autoincrement excursion. That is why the two blits got *smaller*
rather than larger.

The `$2700` interrupt mask in `BG_Init` STAYS and so does its DEBUG IPL assert, re-worded. The
excursion it partly existed for is gone, but the other hazard is not: the VInt handler repoints
the VDP address register, so a VBlank inside an 8192-byte blocking copy still sprays the
remainder. Half a justification going away is not the whole one going away.

## Three findings, in the order they matter

### 1. §4.2's build-time `ensure` is not expressible — and the spelling it invites is silently vacuous

§4.2 asks for an `ensure` refusing "a streamed region that also names a per-column vertical
deform table", inverted once. Measured against the release sigil that builds this tree
(`md5(SIGIL_BUILD) = 324d85d6ad5267a99bd57f118871ed1f`), **control first**, at act 1's ten real
`ojz_region()` call sites:

| condition | result |
|---|---|
| `ensure(1 == 0, …)` — the control | **RED**, 55 times |
| `ensure(parallax_config.pcfg_v_deform_table_bg(parallax) == 12345, …)` | GREEN |
| `ensure(parallax_config.pcfg_v_deform_table_bg(parallax) != 12345, …)` — its exact negation | GREEN |

A proposition and its negation both passing means the condition is never decided. `rg_parallax`
arrives as a `Label`; `.emp` has no comptime dereference of one, and the scene DSL — which does
know about `v_deform` — knows nothing about regions. So the fact is not merely unavailable at
the site: **an author writing §4.2's guard the obvious way would have shipped a permanently
vacuous `ensure` with no diagnostic.**

My first probe of this was itself vacuous and I nearly recorded it as a result: written as
`ensure(bg_layout == 0 || parallax == 0 || <deref> == 0, …)` it built green because every act-1
row takes `bg_layout == 0` and the disjunction short-circuits before the interesting operand.
Putting the deref first is what made the measurement possible at all.

Booked in `docs/DEFERRED_WORK.md` as **BG-STREAM-VDEFORM** with three costed routes back to an
`ensure`, and generalised into `docs/EMP_PITFALLS.md` §12, because the next author to meet a
`Label` in a guard will hit the same wall on an unrelated subject.

**Shipped instead:** `tools/test_bg_stream_vdeform_exclusion.py` — a `needs_build` pytest over
`s4.bin` + `s4.lst` that reads a region row and the parallax config it resolves to (through
`Effects_ResolveParallax`'s own rungs) as bytes, and refuses the pair.

**Proven red, with the mutation quoted from disk:**

```
act_descriptor.emp:660
    ojz_region(x0: OJZ_NIGHT_X0, x1: OJZ_NIGHT_X1, y0: 0, y1: 2047,
               effects: OJZ_Preset_Night, parallax: ParallaxConfig_Rocking,
               bg_layout: OJZ_Act1_BG_Layout, bg_span: 512),   // MUTATION
```

```
s4.bin md5 b9f9698cca305eca8c8a25b9da05657d -> 0ea5ebad761a13d6d1107ed98c7c0775
E  AssertionError: ... region 9 [x 3400..4799, y 0..2047] streams
   (bg_layout $2451C, bg_span 512) and its parallax config $135C4 (via rg_parallax)
   names pcfg_v_deform_table_bg = $13486
```

The md5 is quoted because a mutated source and a stale ROM are indistinguishable from the
test's output alone — and I hit exactly that: my FIRST mutation attempt left the test reporting
`1 passed` while the build had exited 1 and written nothing.

**The tree refused that first mutation, and the refusal is worth recording.** Rebinding region
row 0's `parallax:` away from `ojz_act1_sec_scene(sec: 0)` breaks the editor-scene binding seam,
and `effects_seam_gate` stops the build naming the missing sidecar index. The nine sidecar rows
are not free to repoint; the night row, which binds no sidecar, is.

**Non-vacuity of the shipped test, stated plainly.** Its subject set is the act's ten region
rows, and it reads a real config word for each — a row it cannot resolve is a failure, not a
quiet pass, so "I read nothing" and "I read ten and none offended" cannot come out the same
colour. What a green does NOT say: that the combination has ever existed. At this pin no region
streams and no region-bound config carries a table (the tables that ship are on lab scenes;
`tools/left_col_mask_probe.py` already asserts the act-installed ones carry none). It arms the
day step 6 authors the first streamed region.

### 2. `Draw_BG_TileRow`'s signature deviates from §4.2, deliberately

Shipped: `(d0: plane row, d1: map row, d2: BAND LAYOUT X in cells, a0: *Region) out(d0: admitted)`.
§4.2 spells `(d0, d1, a0)`, and §1a item 1 asks for the band's X to be resolved by "one band
lookup per streamed row" **inside** the routine.

There is nothing here to look up. No band record carries an X anchor at this pin — `band_entry`
is the fixed 10-byte legacy record that `engine/level/parallax.emp` says "must never gain a
field", because sigil harvests its length ambiently — and a band's live Plane-B scroll is not
the answer either, since HScroll already applies it and adding it to the source would double it.
A resolve loop written today could only end in a constant 0: an instrument that cannot produce
the non-zero answer it claims to look for, which is precisely the shape that reads as evidence
and is not.

Carrying the X as an **input** costs 4 bytes (`add.w d2,d2` + `adda.w d2,a1`), is genuinely
parametric rather than dormant, and keeps the source arithmetic — and therefore the routine —
final: big levels' TRACK bands supply a real anchor from the tracker, which is where the band
knowledge actually lives. **This is my call and the owner can overrule it in one line**; if the
preference is the spec's exact arity, the honest alternative is `moveq #0, d2` at the top with
the same comment, not a loop.

What the routine still does NOT do, named in its header and booked in `DEFERRED_WORK.md`: a map
wider than the plane needs the map's width as the row stride and a gather that wraps modulo it
(two runs, not one). Neither is written because neither has a data shape yet.

### 3. `Draw_BG_TileRow` returns whether it was admitted

The column producer it replaces "silently drops if buffer full". That is fine for a producer
nobody tracks and wrong for §4.3's wipe cursor: a cursor that advanced past a row whose entry
never landed would leave one row of the old picture in the new background permanently, with
nothing to notice. `out(d0)` is 1 or 0 and the cursor advances on 1 only. Recorded in
`ENGINE_ARCHITECTURE.md` beside the overflow-drop paragraph, because that paragraph said "each
producer" and now has an exception.

## Pins re-derived rather than left standing

Deleting code deletes the sites pins name, and a pin whose sites are gone cannot fail on the
change it names. Three files moved:

* `bg.emp` — **both per-axis plane pins DELETED.** Their three sites (`move.w #$8F80`,
  `cmpi.w #64`, `moveq #32-1`) were all artefacts of the column-major blit. What the linear
  blit spells instead is the autoincrement (a cell, not a plane), the plane's VRAM base (a
  layout constant) and `BG_LAYOUT_SIZE/4 - 1`, which follows the constant. `BG_LAYOUT_SIZE`
  keeps its own pin and is now the only one in the file.
* `plane_buffer.emp` — vertical pin 7 sites → 2, and it loses two conjuncts with the sites that
  justified them (`PLANE_V_CELLS * 2 == 1 << 7`, the deleted column stride; `PLANE_V_CELLS / 2 - 1
  == 32 - 1`, the deleted copy count). Horizontal pin 6 → 8: `Draw_BG_TileRow`'s two `lsl.w #7`
  are the row stride and are horizontal, not vertical.
* `section.emp` — 20 sites → 17, and its cross-references to the other two files' counts updated.

## The transpose had consumers the spec did not list

§4.2 names one: `tools/inject_editor_bg.py`. A tree-wide sweep found two more that decode
`zone_bg.bin` in column-major order and would have read a transposed picture in silence:

* `tools/test_perspective_floor.py::test_baked_plane_b_carries_the_generated_band` — indexes
  `(col*ROWS + row)*2` to check the BAKED plane against the generator's art.
* `tools/perspective_floor_witness.py` — builds its `want` row the same way to compare LIVE
  Plane B against the blob. **Edited, not run — it is an emulator lane.**

Both flipped. `tools/verify_level_bin.py`'s "column-major strip vs row-major grid" is about the
FOREGROUND strips and is untouched; every other tree-wide `column-major` hit is BG tile-band
animation slots, waterline gather order, or VDP tile order — three different subjects sharing a
word.

`tools/ojz_strip_gen.py`'s `emit_zone_bg_layout` **always emitted row-major** (its output was
unconditionally overwritten by the injector, which is why the disagreement never showed). The
two producers now agree instead of disagreeing, which is one fewer way for the
second-writer-wins accident to matter.

## The transpose composes — source-derived, and NOT an observation

The regenerated `zone_bg.bin` is **exactly** the transpose of the committed one:

```
4096 of 4096 cells agree under  new[(r*64 + c)*2] == old[(c*64 + r)*2]   (0 mismatches)
old == new byte-identical?  False        (so the check is not vacuous)
nonzero words: old 4096, new 4096
```

And the old blit's mapping was `VRAM[PLANE_B + r*128 + c*2] = old[(c*64 + r)*2]`, i.e. the VRAM
image *is* the transpose of the old blob. So **the expected Plane B nametable at `$E000` is now
byte-identical to `zone_bg.bin` itself** — the new blob is the predicted VRAM image, and the new
blit is the identity map onto it.

That is a deterministic transform of committed data. **It is not an observation** and it does
not discharge BG-NT-IDENTICAL: it says the data and the arithmetic compose, and says nothing
about what the hardware actually received.

## GATE BG-NT-IDENTICAL — TAGGED, needs the foreground emulator

**Claim to test:** the Plane B nametable in VRAM is byte-identical before and after this parcel,
after boot and again after one warp.

**What to run**

| | |
|---|---|
| shape | `s4.debug.bin` (DEBUG=1) |
| BEFORE | the coordinator's frozen `/home/volence/sonic_hacks/.aeon-bgnt-baseline/s4.debug.bin` (846894 B, md5 `01295a2407078afd9b8a45645e443010`). **I rebuilt that shape at my own base `6a7e4464` and got the identical size and md5**, so the frozen control and this parcel's baseline are the same bytes and the master gap (`8756007f` vs `6a7e4464`) does not matter for it |
| AFTER | this parcel's `s4.debug.bin`, 846856 B, md5 `317e18245cb1ed9eaf9ffd40dab7fe98` |
| addresses | `$E000` .. `$FFFF`, 8192 bytes (`VRAM_PLANE_B`, `engine/system/constants.emp`) |
| when | after boot, settled — the coordinator measured the nametable stable between frames 120 and 240 with no input over a 256-byte sample; and again after one DEBUG warp, which takes the `Section_RedrawPlanes` cache-recovery path and so exercises the OTHER rewritten blit |
| PASS | the 8192 bytes are equal between the two ROMs at both sample points |

**A third leg, free:** the AFTER read should also equal
`games/sonic4/data/generated/ojz/act1/zone_bg.bin` byte for byte (8192 B, the blob at this
commit). If the before/after comparison fails, that tells you which side is wrong — a mismatch
against the blob is the new blit; a match against the blob with a before/after difference means
the OLD picture was never the blob's transpose, which would be a much older bug.

**A green build is not this gate.** The whole risk of option R is a transpose that composes
wrong and still assembles.

## Build shapes — all four canonical, green

Base `6a7e4464`; assembler sigil `700177b1` (`md5(SIGIL_BUILD) = 324d85d6ad5267a99bd57f118871ed1f`).
Wall clock during these runs: `up 4:18`–`4:32`, load average 2.8–6.0 (parallel sessions on this
box), so the times are inflated and are recorded as context, not as a benchmark.

| shape | exit | size | md5 | vs `6a7e4464` | build time |
|---|---|---|---|---|---|
| `s4.bin` | 0 | 820477 | `46f2e4e5390c4627b84a298a2dc4a311` | **-38** | 3:50 |
| `s4.debug.bin` | 0 | 846856 | `317e18245cb1ed9eaf9ffd40dab7fe98` | **-38** | 3:49 |
| `demo.bin` | 0 | 97173 | `f8d51cb8a4308c6af53a5dc102e70fa8` | **-36** | 3:19 |
| `demo.debug.bin` | 0 | 103606 | `623c01672e168f7ac94e71474c5c8fa7` | **-36** | 3:19 |

Baseline figures are my own rebuild of `6a7e4464` in this worktree (820515 / 846894 / 97209 /
103642), not copied from step 1's note — they happen to agree with it exactly, which is the
expected result of two doc-only commits in between.

Warning profile unchanged in every shape: `153 warnings, proc.clobber-undeclared 72,
module.unreachable 59, module.path-mismatch 14, proc.undeclared-fallthrough 5, import.no-names 2,
proc.out-unwritten 1` — identical to the baseline's, including `proc.out-unwritten 1`, which is
pre-existing and not `Draw_BG_TileRow`'s `out(d0)`.

### Where the bytes went — MEASURED, by symbol span, not estimated

| site | release | debug | demo debug |
|---|---|---|---|
| `BG_Init` | 212 → 176 (**-36**) | 308 → 272 (-36) | 308 → 272 (-36) |
| `Section_RedrawPlanes` | 508 → 480 (**-28**) | 642 → 614 (-28) | 600 → 572 (-28) |
| `Draw_BG_TileColumn` → `Draw_BG_TileRow` | 90 → 92 (**+2**) | 90 → 92 | 90 → 92 |
| **code total** | **-62** | -62 | -62 |

The symbol sets are otherwise identical in every shape (941 release, 1108 debug; the only
difference is the one deleted name and the one added one).

**The ROM shrank 38, not 62, and I chased that rather than reasoning about it.** The running
address shift over the release listing is `-62` from `BgAnim_Init` onward and **resets to 0 at
`$010000`** (`ObjCodeBase`, a fixed bank base), so 24 bytes of the code saving are absorbed into
alignment padding there — the same mechanism step 1 measured in the opposite direction when its
+60 of table absorbed to +0. The -38 that survives appears as a shift of the ROM tail: the two
images are identical up to `$18E`, and from `$C4066` (past `EndOfRom`, i.e. inside the deb2
symbol appendix) the new image equals the old shifted by exactly 38. Part of that tail figure is
the appendix carrying the renamed symbol itself (`Draw_BG_TileColumn` → `Draw_BG_TileRow`, three
characters shorter). **I did not decompose the remaining tail bytes further, and the -38 is the
number to quote.**

## Lanes

* Pre-build `pytest tools -m "not needs_build"`: **2693 passed, 2 skipped, 15 deselected, 140
  subtests passed**, after fixing the one failure it found (`test_citation_form` —
  `ART_PIPELINE_CONTRACT.md:402` cited `bg.emp:51`, which my own header edit pushed onto a blank
  line; re-cited by symbol as that gate's own message prescribes).
* **A red lane that was not a code defect, worth knowing:** the first run of that lane reported
  `5 failed, 55 errors` purely because `SIGIL_BUILD` was unset in that shell.
  `provenance_fixtures.NoAssembler` refuses to *skip* in that case — "these provenance tests
  measured NOTHING. That is a failure, not a skip." That is the right behaviour and it is easy to
  misread as breakage.

## Open / not done here

* **BG-NT-IDENTICAL is UNMEASURED.** Tagged above. Nothing in this parcel claims the picture is
  unchanged on hardware; it claims the data and the arithmetic compose, which is a weaker thing.
* **`tools/perspective_floor_witness.py` was edited and not run** (emulator lane). Its arithmetic
  change is the same one-line flip as its pytest sibling, which IS run and green, but the witness
  itself has no evidence here.
* **PAIRED HALF NOT DONE.** This parcel changes ROM bytes in all four shapes, so sigil's goldens
  no longer match: a `repin` + `refreeze --freeze <parcel> --ab` on the sigil side, landing in
  lockstep. Nothing here touches sigil and sigil's suite was not run.
* **Not cross-seam by NAME.** `Draw_BG_TileRow` and the deleted `Draw_BG_TileColumn` appear in
  `.emp`, `tools/` and docs only — neither `map.toml`, nor either `game_root.asm`, nor
  `debugger.asm` names either. The byte change above is the pairing obligation, not a name.
* **`Draw_BG_TileRow` has no caller**, and that is the step boundary, not an omission. Steps 3-6
  supply it: the region-aware blits, the clamp, the tracker, the wipe.
