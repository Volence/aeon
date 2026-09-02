# Item 5 comptime probe — `[Label; 2]` choosers and struct comparison (2026-09-02)

A throwaway BUILD probe answering the two questions spec
`docs/superpowers/specs/2026-08-30-item5-variants-cycles-key-shapes.md` §5 (lines 589-590)
left open because no build was run there. Nothing written to `.emp` for this probe lands;
this document is the deliverable. Branch `probe/item5-comptime-questions`, based on aeon
master `15efabca`.

Toolchain: sigil binary `/home/volence/sonic_hacks/sigil/target/release/sigil`,
`--version` = `sigil 0.1.0 (8951389a)`, file mtime 2026-08-30 10:46. The sigil repo HEAD at
probe time was `036800fde1f6a70f15e2485eac0240417314c311` (branch master); the 12 commits
between `8951389a` and HEAD are attest/freeze/overseer/harness-pin commits by their
messages (not verified beyond the messages; the binary was NOT rebuilt, per the brief).

Every reported result below comes from a canonical (non-FAST) `build.sh` run except where a
line is marked `[sigil stage via FAST]`. That marking is needed because on a RED tree the
canonical path stops in the `emp_expect_fail` lane (`build.sh:506-515`, which runs real
sigil builds with a poison `--extra-entry` BEFORE the main sigil build) and that lane prints
only the first three diagnostics of the list it counted; the full list was then read off the
sigil stage itself with `FAST=1 DEBUG=1 ./build.sh`, same tree, same binary. The canonical
lane's COUNT and the FAST list agree in every case.

## Verdicts

| # | Question | Verdict |
|---|---|---|
| Q1 | May a single `comptime fn` return `[Label; 2]` into `preset(variants:)`? | **YES.** Both `-> [Label; 2]` (typed) and `-> array` are accepted; the returned pair reaches `ep_variants` at `$14/$18` in slot order; ROMs byte-identical to control when the fn returns the hand pair. |
| Q1-L | Is the `[Label; N]` annotation length-checked? | **NO, not on the fn.** A `[Label; 2]` parameter accepted a 3-element array and reported `.len == 3`. A wrong-length array IS refused, but only when the record is emitted (`array length mismatch: expected 2 element(s), got 3`, blamed on the `pub data` line). |
| Q2-a | Can two `pal_variant` STRUCT values be compared by `first_mismatch([x],[y])`? | **YES** — element `!=` over structs works; red-first proven (index 0 on a `shift_g` mutation). |
| Q2-b | Direct `x == y` / `x != y` on struct values in an `ensure`? | **YES, both** — red-first proven for `pal_variant` and `pal_cycle_channel`. |
| Q2-c | Field-wise `x.v_shift_g == y.v_shift_g`? | **YES** — red-first proven. |
| Q2-d | `[pal_cycle_channel; 2]` element compare, and the prefix case? | **YES element-compares** (`[a,b]` vs `[a,c]` reports index 1) and **YES still blind to a prefix** (`[a]` vs `[a,b]` returns -1) — the `.len` pairing remains required. |
| Q2-e | Can the HAND `pub data` twin (`Variant_Water_Deep`, `OJZ_ShimmerCycle`) be named in such an ensure? | **NO.** Bare in an ensure: `unknown name`. Inside an array literal it resolves as a LABEL and label-vs-struct `!=` is always true, so `first_mismatch([Variant_Water_Deep], [variant(...)])` reports index 0 for the EQUAL twin too (always-red, useless). Field access on the data symbol: `unknown name`. |
| Q2-f | Workable single-source shape | A module-level `const X = variant(...)` feeding BOTH `pub data Variant_Water_Deep: pal_variant = X` and the ensure builds byte-identically and its ensures are red-first proven. |

## Control (clean master `15efabca`, before any edit)

Four-shape canonical build, all exit 0 (`uptime` at start: `23:26:20 up 7 days, 15:15, load
3.52`; at end: `23:33:45 up 7 days, 15:22, load 4.55`).

```
Build complete: s4.bin — 719387 bytes (702.5 KB, 17.2% of 4MB)
Build complete: s4.debug.bin — 736391 bytes (719.1 KB, 17.6% of 4MB)
Build complete: demo.bin — 96476 bytes (94.2 KB, 2.3% of 4MB)
Build complete: demo.debug.bin — 101359 bytes (99.0 KB, 2.4% of 4MB)

55cf05d6fcacf5c785b47a57275c409a844bc59a3291444b0563db7686891cf4  s4.bin
605705488b296fa82ba4a0d5d45c2012795038af1a95eb6127dd64c4cbc02077  s4.debug.bin
88d185f9ff38a09f0e520f3dbc1811730ff9c37a8ebce430d85e4cbb2c7bbd4e  demo.bin
ab01d226b45c9e5a8c7e64ad5d394439102b3a12f9b184e63fc8dd89778553ec  demo.debug.bin
```

## The GREEN probe tree (the one state that was built four-shape)

The complete throwaway diff against master, reproduced so the probe can be re-run. It
edits only `games/sonic4/data/effects/ojz_effects.emp` (a reached module —
`SIGIL_WARNINGS` unreachable count unchanged at 54 in every build here):

```diff
@@ -901,7 +901,10 @@
-pub data Variant_Water_Deep:  pal_variant = variant(shift_r: 1, shift_g: 1)                 // halve R+G, keep B
+const PROBE_WATER_DEEP = variant(shift_r: 1, shift_g: 1)   // PROBE Q2-E: const feeds both the data and the ensure
+pub data Variant_Water_Deep:  pal_variant = PROBE_WATER_DEEP                                  // halve R+G, keep B
+ensure(PROBE_WATER_DEEP == variant(shift_r: 1, shift_g: 1), "Q2-E1 const twin == equal says unequal")
+ensure(first_mismatch([PROBE_WATER_DEEP], [variant(shift_r: 1, shift_g: 1)]) == -1, "Q2-E2 const twin first_mismatch index {first_mismatch([PROBE_WATER_DEEP], [variant(shift_r: 1, shift_g: 1)])}")
@@ -1032,7 +1035,47 @@
-pub data OJZ_Preset_Sec3:  EffectsPreset = preset(pal: OJZ_Palette, raster: Raster_Program_None, cycle: OJZ_ShimmerCycle,  variants: [Variant_Water_Deep, 0])
+// PROBE (throwaway, item5 comptime probe) — spelling A: typed [Label; 2] in and out
+pub comptime fn probe_variants_pair(sec: int, hand: [Label; 2]) -> [Label; 2] {
+    ensure(sec >= 0 && sec < 9, "probe_variants_pair(sec: {sec}): out of range")
+    comptime var out = hand
+    if sec == 99 { out = [0, Variant_Water_Deep] }
+    return out
+}
+// PROBE Q1-L (throwaway) — a [Label; 2] PARAMETER accepts a 3-element array (annotation not length-checked)
+pub comptime fn probe_takes_pair(v: [Label; 2]) -> int { return v.len }
+ensure(probe_takes_pair(v: [Variant_Water_Deep, 0, 0]) == 3, "Q1-L probe_takes_pair: len {probe_takes_pair(v: [Variant_Water_Deep, 0, 0])}")
+// PROBE Q2 (throwaway) — struct comparison forms, GREEN inputs
+ensure(first_mismatch([variant(shift_r: 1, shift_g: 1)], [variant(shift_r: 1, shift_g: 1)]) == -1,
+       "Q2-F1 pal_variant first_mismatch: index {first_mismatch([variant(shift_r: 1, shift_g: 1)], [variant(shift_r: 1, shift_g: 1)])}")
+ensure(variant(shift_r: 1, shift_g: 1) == variant(shift_r: 1, shift_g: 1),
+       "Q2-F2 pal_variant direct == says unequal")
+ensure(!(variant(shift_r: 1, shift_g: 1) != variant(shift_r: 1, shift_g: 1)),
+       "Q2-F3 pal_variant direct != says unequal")
+ensure(variant(shift_r: 1, shift_g: 1).v_shift_g == variant(shift_r: 1, shift_g: 1).v_shift_g,
+       "Q2-F4 pal_variant field-wise v_shift_g differs")
+ensure(first_mismatch([cycle_channel(line: 2, first: 8, count: 4, period: 8)], [cycle_channel(line: 2, first: 8, count: 4, period: 8)]) == -1,
+       "Q2-C1 pal_cycle_channel first_mismatch: index {first_mismatch([cycle_channel(line: 2, first: 8, count: 4, period: 8)], [cycle_channel(line: 2, first: 8, count: 4, period: 8)])}")
+ensure(cycle_channel(line: 2, first: 8, count: 4, period: 8) == cycle_channel(line: 2, first: 8, count: 4, period: 8),
+       "Q2-C2 pal_cycle_channel direct == says unequal")
+ensure(!(cycle_channel(line: 2, first: 8, count: 4, period: 8) != cycle_channel(line: 2, first: 8, count: 4, period: 8)),
+       "Q2-C3 pal_cycle_channel direct != says unequal")
+ensure(cycle_channel(line: 2, first: 8, count: 4, period: 8).pc_period == cycle_channel(line: 2, first: 8, count: 4, period: 8).pc_period,
+       "Q2-C4 pal_cycle_channel field-wise pc_period differs")
+// P1: prefix blindness — [a] vs [a, b] must report -1 (the documented precondition)
+ensure(first_mismatch([cycle_channel(line: 2, first: 8, count: 4, period: 8)],
+                      [cycle_channel(line: 2, first: 8, count: 4, period: 8), cycle_channel(line: 3, first: 0, count: 2, period: 1)]) == -1,
+       "Q2-P1 prefix case did NOT return -1")
+// P2: array-of-struct element compare — [a, b] vs [a, c] must report index 1
+ensure(first_mismatch([cycle_channel(line: 2, first: 8, count: 4, period: 8), cycle_channel(line: 3, first: 0, count: 2, period: 1)],
+                      [cycle_channel(line: 2, first: 8, count: 4, period: 8), cycle_channel(line: 3, first: 0, count: 2, period: 7)]) == 1,
+       "Q2-P2 array-of-struct mismatch index is {first_mismatch([...same two arrays...])}, expected 1")
+pub data OJZ_Preset_Sec3:  EffectsPreset = preset(pal: OJZ_Palette, raster: Raster_Program_None, cycle: OJZ_ShimmerCycle,  variants: probe_variants_pair(sec: 3, hand: [Variant_Water_Deep, 0]))
```

Four-shape canonical build of that tree, all exit 0 (`23:39:09 up 7 days, 15:28, load 3.50`
to `23:47:07 up 7 days, 15:36, load 8.47`):

```
Build complete: s4.bin — 719387 bytes (702.5 KB, 17.2% of 4MB)
Build complete: s4.debug.bin — 736391 bytes (719.1 KB, 17.6% of 4MB)
Build complete: demo.bin — 96476 bytes (94.2 KB, 2.3% of 4MB)
Build complete: demo.debug.bin — 101359 bytes (99.0 KB, 2.4% of 4MB)
```

| ROM | control sha256 | green-probe sha256 | |
|---|---|---|---|
| s4.bin | `55cf05d6…891cf4` | `55cf05d6…891cf4` | identical |
| s4.debug.bin | `60570548…bc02077` | `60570548…bc02077` | identical |
| demo.bin | `88d185f9…7bbd4e` | `88d185f9…7bbd4e` | identical |
| demo.debug.bin | `ab01d226…8553ec` | `ab01d226…8553ec` | identical |

(`cmp` against the saved control ROMs: no differing bytes, both sonic4 shapes.)

## Q1 evidence — `[Label; 2]` chooser into `preset(variants:)`

### Read-back (green probe, canonical build)

Addresses from the listing, bytes from the ROM:

```
s4.debug.lst:  (0) 2072/13EB4 :        Variant_Water_Deep:
               (0) 2081/13F7C :        OJZ_Preset_Sec3:
s4.debug.bin @ 0x13F7C+0x14:  00013f90: 0001 3eb4 0000 0000     ep_variants[0]=Variant_Water_Deep, [1]=0

s4.lst:        (0) 1756/13612 :        Variant_Water_Deep:
               (0) 1765/136DA :        OJZ_Preset_Sec3:
s4.bin @ 0x136DA+0x14:        000136ee: 0001 3612 0000 0000     ep_variants[0]=Variant_Water_Deep, [1]=0
```

Whole record, s4.debug.bin @ 0x13F7C (38 bytes), identical to control:
`0002 36d0 | 0000 0000 | 0000 8204 | 0000 0000 | 0001 3bec | 0001 3eb4 0000 0000 | 7fff 7fff 7fff 7fff | 0000`
(`ep_pal OJZ_Palette`, `ep_parallax 0`, `ep_raster Raster_Program_None`, `ep_patched 0`,
`ep_cycle OJZ_ShimmerCycle`, `ep_variants`, four `PATCH_ANCHOR_NONE`, `ep_transition 0`).

### RED-1 — the chooser really is on the path (canonical `DEBUG=1 ./build.sh`, exit 0)

Mutation: `if sec == 3 { out = [0, Variant_Water_Deep] }` (swap the pair for the bound section).

```
s4.debug.bin sha256  ff5a5e65524b74fa995aa5e313abeef3fdda2d5088eb86f2166cf8c8138f373e
s4.debug.bin @ 0x13F7C+0x14:  00013f90: 0000 0000 0001 3eb4
cmp -l s4.debug.bin control/s4.debug.bin   (1-based decimal offsets)
 81810   0   1     <- 0x13F91  ep_variants[0] bytes 1..3: 01 3E B4 -> 00
 81811   0  76
 81812   0 264
 81814   1   0     <- 0x13F95  ep_variants[1] bytes 1..3: 00 -> 01 3E B4
 81815  76   0
 81816 264   0
```

Exactly six bytes differ, all inside Sec3's `ep_variants`; slot order is preserved through
the fn. (No header-checksum diff: the checksum is a word sum, invariant under a longword
swap.)

### RED-2 — the fn's own `ensure` fires (canonical count; text via sigil stage)

Mutation: `variants: probe_variants_pair(sec: 9, hand: [Variant_Water_Deep, 0])`. In the
RED-2 canonical run (see Q2 below, 14 diagnostics + sentinel = 15 counted by
`emp_expect_fail`), the lane's own three-line sample included it:

```
[Error] probe_variants_pair(sec: 9): out of range @ Span { source: SourceId(94), start: 75275, end: 75351 }
```

Span → the `ensure(sec >= 0 && sec < 9, ...)` line inside the fn.

### Q1-L — annotation is not length-checked on the fn; emission catches it (canonical RED-3)

- `[Label; 2]` PARAMETER, 3-element argument: builds green; the ensure
  `probe_takes_pair(v: [Variant_Water_Deep, 0, 0]) == 3` PASSES (in the green four-shape
  build above). Red-first: flipped to `== 2` it fires
  `[Error] Q1-L probe_takes_pair: len 3` (RED-2 list below).
- `-> [Label; 2]` fn returning `[0, Variant_Water_Deep, 0]` into `variants:` — canonical
  `DEBUG=1 ./build.sh` exit 1, `emp_expect_fail` counted 2 (ours + sentinel):

```
[Error] array length mismatch: expected 2 element(s), got 3 @ Span { source: SourceId(94), start: 78571, end: 78759 }
```

  The span is the whole `pub data OJZ_Preset_Sec3: ... = preset(...)` line, NOT the fn's
  return. The same diagnostic and the same blamed line appear with the fn spelled
  `hand: array) -> array` `[sigil stage via FAST]`, so the check belongs to the emitted
  record (`ep_variants: [*u8; 2]`) or `preset()`'s parameter, not to the fn signature —
  and given Q1-L's parameter result, to the record.

### Spellings

| Spelling | Result |
|---|---|
| `pub comptime fn f(sec: int, hand: [Label; 2]) -> [Label; 2]` | accepted; green four-shape byte-identical; RED-1/RED-2 above |
| `pub comptime fn f(sec: int, hand: array) -> array` | accepted `[sigil stage via FAST]`, s4.debug.bin sha `60570548…` = control; RED-3 twin gives the identical `array length mismatch` diagnostic |
| `comptime var out = hand; if ... { out = [..] }; return out` | accepted (flat accumulator, per `docs/EMP_PITFALLS.md` §1) |

No spelling was refused. The typed form is the tidier one and matches `preset()`'s own
parameter spelling (`preset.emp:123`).

## Q2 evidence — struct comparison

### RED-2 — every accepted form fires on a one-field mutation

Mutations applied to the green tree all at once: right-hand `variant(shift_r: 1, shift_g: 0)`
on F1-F4, right-hand `cycle_channel(..., period: 7)` on C1-C4, P1's expectation flipped to
`== 0` (its message made to interpolate the value), P2's expectation flipped to `== 0`, E1/E2
right-hand `shift_g: 0`, Q1-L `== 2`, Q1 `sec: 9`. Canonical `DEBUG=1 ./build.sh` exit 1:

```
FAIL  sentinel (1.66s): fragment 'EMP_EXPECT_FAIL_SENTINEL' present but got 15 [Error] diagnostic(s), expected 1
```

(15 = our 14 + the lane's sentinel.) The full 14, same tree `[sigil stage via FAST]`:

```
error: native build (sonic4 debug): build_program: 14 error(s);
  [Error] Q2-E1 const twin == equal says unequal
  [Error] Q2-E2 const twin first_mismatch index 0
  [Error] Q1-L probe_takes_pair: len 3
  [Error] Q2-F1 pal_variant first_mismatch: index 0
  [Error] Q2-F2 pal_variant direct == says unequal
  [Error] Q2-F3 pal_variant direct != says unequal
  [Error] Q2-F4 pal_variant field-wise v_shift_g differs
  [Error] Q2-C1 pal_cycle_channel first_mismatch: index 0
  [Error] Q2-C2 pal_cycle_channel direct == says unequal
  [Error] Q2-C3 pal_cycle_channel direct != says unequal
  [Error] Q2-C4 pal_cycle_channel field-wise pc_period differs
  [Error] Q2-P1 prefix case returned -1 (blind to the longer twin, as documented)
  [Error] Q2-P2 array-of-struct mismatch index is 1, expected 1
  [Error] probe_variants_pair(sec: 9): out of range
```

(Spans elided; each pointed at its own `ensure`.) Then the green tree above builds four-shape
byte-identical — green after red, for every form. Per form:

| Form | Green (equal inputs) | Red (one field differs) | Verdict |
|---|---|---|---|
| F1/C1 `first_mismatch([x],[y]) == -1` | passes | fires, reports index 0 | works |
| F2/C2 `x == y` | passes | fires | works |
| F3/C3 `!(x != y)` | passes | fires | works |
| F4/C4 `x.field == y.field` | passes | fires | works |
| P2 `[a,b]` vs `[a,c]` | reports 1 (`== 1` passes) | `== 0` fires with "index is 1" | element-compares |
| P1 `[a]` vs `[a,b]` | `== -1` passes | `== 0` fires with "returned -1" | prefix-blind, `.len` pairing required |
| E1/E2 const-fed twin | passes | fires | works |

Note P1's "red" is a flipped EXPECTATION, not a mutation of the data — there is no data
mutation that makes the prefix case fire, which is precisely the documented blindness
(`raster_dsl.emp:3384-3401`). The value of the probe is the interpolated `-1` on struct
elements, confirming the precondition carries over to struct arrays unchanged.

Cross-type: `variant(...) == cycle_channel(...)` is NOT refused — it evaluates false and the
ensure fires (`[Error] Q2-D4 cross-type == said equal`, canonical RED-4 sample). A typo'd
constructor on one side of an equality ensure therefore reads as a mismatch, not as a type
error.

### RED-4 — the hand `pub data` twin cannot be named (canonical count 6 = 5 + sentinel)

```
[sigil stage via FAST], same tree:
  [Error] unknown name `Variant_Water_Deep`            <- ensure(Variant_Water_Deep == variant(shift_r: 1, shift_g: 1), ...)
  [Error] unknown name `Variant_Water_Deep`            <- ensure(Variant_Water_Deep == variant(shift_r: 1, shift_g: 0), ...)
  [Error] Q2-D3b EQUAL twin via array literal: index 0 <- ensure(first_mismatch([Variant_Water_Deep], [variant(shift_r: 1, shift_g: 1)]) == -1, ...)
  [Error] Q2-D4 cross-type == said equal (expect refusal or fire)
  [Error] unknown name `OJZ_ShimmerCycle.pcs_ch`       <- ensure(OJZ_ShimmerCycle.pcs_ch[0] == cycle_channel(...), ...)
```

The canonical lane's three-line sample showed D4 and the `OJZ_ShimmerCycle.pcs_ch` line
plus the sentinel. D3 discriminated separately `[sigil stage via FAST]`: with the UNEQUAL
twin (`shift_g: 0`) and `== -1` it fires "index 0"; with the EQUAL twin and `== -1` it fires
"index 0"; with the EQUAL twin and `== 0` it passes. So inside an array literal the data
symbol is a label, label-vs-struct `!=` is always true, and that form is an always-red
guard — the mirror image of the always-green trap in `docs/EMP_PITFALLS.md` §3, and just as
useless.

### The workable single-source shape (E1/E2)

`const PROBE_WATER_DEEP = variant(shift_r: 1, shift_g: 1)` feeding
`pub data Variant_Water_Deep: pal_variant = PROBE_WATER_DEEP` emits the same 8 bytes
(`0100 0100 0000 0e00` at 0x13EB4, ROM byte-identical to control in the four-shape green
build), and `ensure(PROBE_WATER_DEEP == variant(...))` / `first_mismatch([PROBE_WATER_DEEP], [...])`
both fire on a `shift_g` mutation (RED-2). Whether such a struct-valued `const` can be
`pub` and imported ACROSS modules (generated `effects_scenes.emp` ↔ hand `ojz_effects.emp`)
was not probed — see Open.

## Four-shape status, final tree

The `.emp` edits were reverted (`git checkout -- games/sonic4/data/effects/ojz_effects.emp`;
`git status` clean against base `15efabca`), then the four shapes were rebuilt canonically.
All four exit 0 (`23:52:09 up 7 days, 15:41, load 4.76` to `23:59:32 up 7 days, 15:48,
load 8.23`), sizes as in the control block, sha256 identical to control for all four ROMs:

```
55cf05d6fcacf5c785b47a57275c409a844bc59a3291444b0563db7686891cf4  s4.bin
605705488b296fa82ba4a0d5d45c2012795038af1a95eb6127dd64c4cbc02077  s4.debug.bin
88d185f9ff38a09f0e520f3dbc1811730ff9c37a8ebce430d85e4cbb2c7bbd4e  demo.bin
ab01d226b45c9e5a8c7e64ad5d394439102b3a12f9b184e63fc8dd89778553ec  demo.debug.bin
```

(Master moved four docs/data-only commits past `15efabca` while this ran — `b467ab57` at
the time of writing; the branch was not rebased.)

## Left open, and why

1. **Cross-module visibility of a struct-valued `pub const`** — the implementing parcel's
   ensure must see the generated value and the hand value in ONE module. This probe proved
   the same-module `const` shape only. Not probed because it needs an edit to a generated
   file or a second hand module, outside the two questions asked. The alternative that
   needs no cross-module value is the spec's own layer 1 (text golden in
   `tools/test_effects_gen.py`) plus layer 2 (byte golden read off `s4.lst`/`s4.debug.bin`,
   exactly the read-back method used here), neither of which needs comptime equality at all.
2. **Whether `preset()`'s `variants: [Label; 2]` parameter would refuse a 3-array by itself**
   — indistinguishable here from the record-emission check, since Q1-L shows a fn parameter
   annotation is not length-checked; the emission check catches it either way, blamed on the
   `pub data` line.
3. **Runtime confirmation** — none; no emulator was used (workspace rule). The bytes were
   read from the ROM at the listing's addresses; nothing here ran the ROM.
4. **The sigil binary is 12 commits behind sigil HEAD** (`8951389a` vs `036800fd`). Not
   rebuilt per the brief. Every result above is against `8951389a`.

Nothing from this probe deserves to land as code. The one candidate — E1/E2's const-fed
twin — is a design choice for the implementing parcel (it moves `Variant_Water_Deep`'s
definition one line up into a `const`), not a probe artefact.
