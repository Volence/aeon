# `deform: own(..)` — the per-layer deform ref, and what its capability costs

**Parcel:** Scanline P3, Phase 1, Task 9 (`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`)
**Branch:** `p3/t9-deform-own`
**Design:** §2 — three deform spellings, of which exactly one trips `CAP_MULTI_DEFORM_TABLE`:
"`deform: own(table, amplitude_shift_a/b, phase, speed)` — per-layer table+speed (trips
MULTI_DEFORM_TABLE, extended record)", while "`shared(phase)` … is what WindyHaze / SkyHaze /
haze_fg actually are; does NOT trip MULTI_DEFORM_TABLE".

**What landed:** the mechanism, end to end — the authored variant, its guards, the comptime
lowering into Task 8's extended record, the runtime's per-band table load, and the measured
cost of that load. **What did not land, deliberately: adoption.** No shipped scene authors
`own()`. That is PARK-1 and owner-gated, and it is why all four canonical images are
byte-identical.

---

## 1. The model — one enum, two authoring positions, guarded rather than documented

`SceneDeform` had two variants and one position. It now has three variants and two positions,
and which variant is legal where is a build error, not a convention:

| position | `None` | `Shared(table, speed)` | `Own(table, sa, sb, ph, sp)` |
|---|---|---|---|
| **scene** — `scene(deform_fg:/deform_bg:)`, per PLANE | no table on that plane | the shipped twenty | **REFUSED** |
| **layer** — `layer(deform:)`, per LAYER (new) | inherit the scene's tables | **REFUSED** | this layer's own table |

Two things about that table are worth stating because a reader will otherwise mis-derive them.

**Layer-level `None` IS design §2's `shared(phase)`.** The design's middle spelling takes a
phase and no table — "samples the scene's plane-shared table at a per-layer phase". A layer
already carries `ly_phase`, `ly_dsa` and `ly_dsb`, so that variant needs no payload at the
layer and no new field anywhere: it is the DEFAULT, and it is what all twenty shipped scenes
already are. Adding a payload-carrying `Shared` at layer level would have been a second
spelling of the default, carrying a Label the lowering would then have to pick a plane for.

**`Own` carries ONE table Label, not two,** for the same reason `Shared` does: one table
serves both planes. A layer wanting a different curve per plane is a §9 future, not a silent
third meaning of the payload.

**Never a `Label = 0` default.** "Is a per-layer table attached?" is `scene_deform_is_own()`,
a VARIANT test, and every accessor matches all three arms exhaustively. An `ensure` comparing
a Label to an int is silently unevaluable and always passes (EMP_PITFALLS §3), so the payload
is never the discriminator anywhere in this parcel.

### 1.1 `own()`'s five payloads land in two different places

Three of the five already have a home. `shift_a`/`shift_b` are `band_deform_shift_a/b` and
`phase` is `band_phase_offset` — all three per-band in the LEGACY prefix since Parcel W. So
`layer()` folds them into `ly_dsa`/`ly_dsb`/`ly_phase`, and **after that fold an `own()` layer
is indistinguishable from a hand-authored one to every amplitude scan in `scene_dsl.emp`** —
`scene_caps()`'s `live_amp`, `scene_live_amp_a/b`, `scene_band()`'s lowering. That is why the
capability's arrival changed no existing fold. Only the TABLE and the SPEED are new, and they
are exactly what `band_ext` was shaped to hold.

The fold creates one hazard and it is guarded: authoring `own(...)` AND `layer(dsa:, dsb:,
phase:)` would be two sources for one record byte, so the plain arguments must be left at
their defaults when `own()` supplies them.

### 1.2 The three guards, and why each one exists

| guard | in | why it is not hygiene |
|---|---|---|
| `Shared` refused at layer level | `layer()` | a second spelling of `None`, carrying an unusable Label |
| `own()` + explicit `dsa/dsb/phase` refused | `layer()` | two sources for one byte, the drift this tree keeps paying for |
| `own()` with both shifts 15 refused | `layer()` | **makes `CAP_MULTI_DEFORM_TABLE ⇒ CAP_DEFORM` structural** — see §4 |
| `Own` refused at scene level | `scene()` | the header has one table word per plane and nowhere to put a per-layer speed; without the guard it lowers SILENTLY, dropping the shifts, phase and speed |
| an `own()` scene must also attach a plane-shared table | `scene()` | **the runtime mode key** — see §2 |

### 1.3 The one design decision that is not in the spec: the mode key

`parallax_mode_key()` decides per-line vs per-cell **at runtime**, by ORing the installed
config's two HEADER table words. It cannot see the bands. So a scene whose ONLY tables were
per-layer would answer per-cell at runtime while `scene_forces_per_line()` answered per-line at
comptime — the twin-key desync design §2 says is impossible by construction, reintroduced by a
new attachment the key cannot reach.

Three ways out were available. Widening the runtime key to scan the band array spends the
frame's hot path re-deriving what the lowering knows. Widening the 28-byte header to carry a
mode flag moves every emitted config record, which is the byte churn the P1 image-identity gate
is pinned on. **The third is the guard**, and it is also the honest model: `own()` OVERRIDES the
plane-shared table for one layer, and the layers that did not override it still need something
to sample. `scene()` requires a scene-level table on at least one plane — which is exactly the
key's own predicate.

**Consequence for the forcer set:** because a scene-level table is mandatory alongside any
`own()`, `scene_forces_per_line()` ARM 1 already fires for every `own()` scene. No sixth arm
was added, and adding one would have been a arm that can never be the sole reason — a dead arm
reading as coverage, which is the shape this plan's trap ledger names twice.

---

## 2. Inheritance is resolved at COMPTIME — and Task 8's declaration was wrong twice

Task 8 documented `band_ext.bx_deform_table_a` as "0 = inherit `pcfg_deform_table_fg`" and left
the runtime read to Task 9. Task 9 ruled the other way, and corrected two things in the
declaration while it was there.

**The sentinel is gone.** Every emitted extension carries the EFFECTIVE table and speed for its
band: `band_table_a/b()` and `band_speed_a/b()` in `scene_dsl.emp` pick the layer's own when it
has one and the scene's otherwise. Both inputs are comptime constants, so a runtime "is it
null? then use the config's" test — per band, per plane, every frame — would spend the hot path
re-deciding what the build knows. It also keeps the gated block at two instructions with no
branch, which is what makes §3's cost a clean per-band constant rather than a data-dependent
one. The consequence is worth stating plainly: **in a game that declares the capability, EVERY
band carries an extension**, including bands whose layer authored no `own()`. The extension is a
record-shape property of the GAME (design §3.1), never a per-band option.

**The two table fields were the wrong TYPE.** They were declared `u32`, which refuses a Label:

```
[Error] [emit.type] expected an integer for u32, got label
```

— once per emitted band, the first time a lowering put a real table in one. Task 8's
placeholder was the literal `0`, which is why the declaration survived a parcel while being
wrong. They are `*u8` now, the same as `parallax_config`'s three table words.

### 2.1 The proof, in emitted ROM bytes

From the capability-raised build (§3), `ParallaxConfig_OJZ_Default` — four layers, none of them
`own()`, scene-level `deform_bg: Shared(DeformTable_Zero, 1)`, no FG table:

```
DeformTable_Zero = $121C8
band0: prefix=0000000f010f000f0f00  ext.tblA=00000000  ext.tblB=000121c8  spdA=1 spdB=1
band1: prefix=0040000f010f000f0f00  ext.tblA=00000000  ext.tblB=000121c8  spdA=1 spdB=1
band2: prefix=0140000f010f000f0f00  ext.tblA=00000000  ext.tblB=000121c8  spdA=1 spdB=1
band3: prefix=0180000f010f000f0f00  ext.tblA=00000000  ext.tblB=000121c8  spdA=1 spdB=1
```

Four facts, each of which was a question: the FG slot is null because the scene attaches no FG
table; the BG slot carries the SCENE's table in every band, which is what "inherit" resolved
to; the speeds are the accessors' own defaults (FG `None` → 1, BG the scene's `1`); and the
stride is 20 with the legacy prefix unchanged at offset 0.

---

## 3. The runtime, and the instrument builds that can see it

**The block** (`engine/level/parallax.emp`, inside `Parallax_Fill_PerLine`'s `.next_band`):

```
if (Game.SCANLINE_CAPS & CAP_MULTI_DEFORM_TABLE) != 0 {
.cap_multi_deform_table_band_begin:
        movea.l band_ext_table_a(a1), a5    // this band's FG curve
        movea.l band_ext_table_b(a1), a6    // this band's BG curve
.cap_multi_deform_table_band_end:
}
```

This is the FIRST code site for the bit — Task 8's landing was data-side and explicitly
deferred the §3.3 bracket to here. It is NESTED inside `cap_deform_sample` because `a5`/`a6`
are the sampling machinery's registers and nothing else reads them; `scene_caps()` pins the
implication that makes the nesting sound, and `tools/scene_spans.py` derives a mask's expected
spans from exactly this nesting.

**The config-level hoist above it is NOT elided under the capability**, though it is dead
there. An `if CAP == 0 { .. }` gate would be the only inverted one in the tree and would make
the span model non-monotone — the tooling would have to learn that a WIDER mask emits FEWER
spans. Two `movea.l`s once per frame is not worth that.

### 3.1 The instrument-build recipe — reproducible, and NOT canonical

Neither ROM below is a golden and neither may be committed. Four edits from
`p3/t9-deform-own`'s tip:

| file | from | to |
|---|---|---|
| `games/sonic4/config/game.emp` | `SCANLINE_CAPS = $001F` | `$003F` |
| `engine/level/parallax.emp` | `BAND_EXT_N = 0` | `1` |
| `engine/ram.emp` | `BAND_EXT_BYTES = 0` | `10` |
| (I0 control only) `engine/level/parallax.emp` | the two `movea.l` | commented out, **labels kept** |

Then `FAST=1 DEBUG=1 ./build.sh`.

| build | crc | len | block |
|---|---|---|---|
| **I1** — the capability, complete | `abe1b79e` | 715046 | present, **8 bytes at $7B10** |
| **I0** — control, block removed | `e8fc604a` | 715010 | **0 bytes at $7B10** (labels survive) |

The I0 span reading zero at the SAME address is the control's signature: the pair differs in
those two instructions and in nothing else — same extended record, same Step-4a copy width,
same strides.

**Three build-order controls fired on the way there, each one a guard doing its job:**

1. `BAND_EXT_N = 1` alone, capability still `$001F`: Task 8's two-directional pin fires
   (*"BAND_EXT_N is 1 but this game does NOT declare CAP_MULTI_DEFORM_TABLE"*). The dispatch
   named this as the first control and it is exactly what happened.
2. Capability raised, record widened, RAM not: the reservation guard fires (*"Parallax_Shadow_Bands
   reserves fewer bytes than the shadow view needs: … = 160"*).
3. Following that guard's advice literally — *"widen BAND_ENTRY_LEN by sizeof(band_ext)"* —
   **fails the build in a second place**, because `BAND_ENTRY_LEN` mirrors the LEGACY
   `band_entry`, which sigil harvests ambiently, and `extern("band_entry_len")` pins it there.
   Correct-sounding advice, dead end. **Fixed in this parcel:** `engine/ram.emp` now carries a
   separate `BAND_EXT_BYTES` (the capability-selected tail) beside `BAND_ENTRY_LEN` (the
   legacy mirror, which never moves), the reservation is their sum, and both drift guards name
   the right constant.

### 3.2 The bracket's own witness

`effects_gates.py`'s `scanline_spans` lane reports `CAP_MULTI_DEFORM_TABLE — NOT GATED
ANYWHERE` on master, and that is **correct and expected after this task**: the lane reads the
two shipped `.lst`s, neither game raises the bit, and a comptime-elided span cannot appear in
either listing. For this bit the row is a statement about ADOPTION, not about the lowering.
The listing evidence is I1's:

```
(0) 1111/7B10 : $engine.parallax$Parallax_Fill_PerLine$cap_multi_deform_table_band_begin:
(0) 1112/7B18 : $engine.parallax$Parallax_Fill_PerLine$cap_multi_deform_table_band_end:
```

The note in `scene_dsl.emp`'s capability block is corrected accordingly, because the original
wording ("if either bit is still showing that row after Task 10, the lowering did not happen")
would have sent the next reader hunting for a lowering that is there.

*(P3 Task 16 update: the lane now spells this state out itself — the row reads `GATED IN
SOURCE, RAISED BY NEITHER FIXTURE (… elided from both)`, derived from the source brackets.
`NOT GATED ANYWHERE` is since reserved for a declared bit with no source brackets at all,
and FAILS. The paragraph above records what the lane printed at this parcel's landing.)*

---

## 4. The measurement

`tools/deform_own_cost_probe.py`, which imports `parallax_cost_probe`'s installer (`_one`:
`Debug_Scene_Freeze`, the `Replay_Record_Buf` scratch, the preemption-free window retry, the
four derived checks) and adds only the record builder — a band is 20 bytes here and carries two
table pointers the legacy builder has no field for. **The stride is DERIVED from the build under
measurement** (`Parallax_Shadow_Scroll_A - Parallax_Shadow_Bands` over `MAX_PARALLAX_BANDS`, the
same span `parallax.emp` pins the record against), never typed, and the probe **refuses a ROM
whose record is the legacy 10 bytes** rather than measuring the wrong path and reporting a
number.

One header field is load-bearing in a way that is easy to get wrong and is guarded in the
tool's own comments: the fixture's `pcfg_deform_table_fg` must be non-null even though the fill
takes its curves from the band, because `parallax_mode_key` still reads the HEADER. A fixture
with null header tables runs the per-cell filler and measures nothing. (Which is §1.3's guard,
arriving from the other side.)

### 4.1 The parameter — 32.00 cycles per band, residual 0.00

Fixtures S1/S2/S3: 1/2/3 bands, per-line, FG sampling live in every band, so the 224 sampled
lines are constant and the band-count slope isolates per-band work. `--repeat 3`, spread **0**
on every row, every window preemption-free.

| fixture | bands | I1 `Parallax_Update` | I0 `Parallax_Update` | delta |
|---|---|---|---|---|
| S1 | 1 | 12072 | 12040 | **+32** |
| S2 | 2 | 13186 | 13122 | **+64** |
| S3 | 3 | 14280 | 14184 | **+96** |

Per-band slope **1104.00** (I1) against **1072.00** (I0) — **32.00 cycles per band**, and the
per-fixture deltas are exactly `32 × bands`, so the residual is **0.00**. `Parallax_Fill_PerLine`'s
own row moves by the same amounts (10680/11102/11524 against 10648/11038/11428), which places
the cost inside the filler rather than somewhere else in the walker.

**The measured value IS the derived nominal.** Two `movea.l d16(An),An` are 16 cycles each on
the 68000. This is one of the rare places in this parcel family where booking would have been
right — recorded because the trap ledger's rule is "measure, don't book", and the measurement
is what turns a plausible 32 into a known one. It is also a RAM-side load with no VDP port in
reach, which is the condition under which nominal cycles are expected to hold.

Wall clock: I1 sweep 11:14:38 → 11:15:24 (**46 s**, load average 6.02 → 4.59); I0 sweep
11:13:39 → 11:14:25 (**46 s**). Both `uptime`-bracketed, both run alone, headless CLI lane, no
emulator MCP.

### 4.2 The plan's named fixture pair — predicted zero, measured zero

Step 4 asks for "a fixture with N layers sharing one table versus N layers each with their
own". Fixtures O1/O2/O3 are S1/S2/S3 with each band pointing at a DIFFERENT shipped curve
(`DeformTable_Zero` / `_Shimmer` / `_Haze`), one thing apart.

**The prediction was stated before the run and is in the tool's output text**: exactly zero,
because the lowering resolves inheritance at comptime, so both shapes execute the same two
`movea.l` per band and differ only in the pointer VALUES.

| bands | shared | own | delta |
|---|---|---|---|
| 1 | 12072 | 12072 | **+0** |
| 2 | 13186 | 13186 | **+0** |
| 3 | 14280 | 14280 | **+0** |

**`own()` costs nothing over `shared()` within a capability-raised build.** What the capability
costs is §4.1, per band, unconditionally, whether or not any layer overrides anything. That is
the number a future adoption is budgeted against, and it is why the arithmetic is "did this
GAME declare the bit", never "how many layers used it".

A fit that could not fail is what this plan's §5(b) is a postmortem for, so the zero is
reported as a CONTROL: it is evidence the load is data-independent and the two fixtures are one
thing apart, not evidence that the mechanism is free.

### 4.3 The standing rule on the canonical model

Task 9 changes `Parallax_Fill_PerLine`'s SOURCE and **all four canonical images are
byte-identical** (§5). A byte-identical image executes byte-identical instructions, so every
fitted coefficient in `[parallax.cost_model]` is unchanged by construction — a stronger
statement than a re-run, and the one the standing rule's arm (a) asks for. The new parameter is
booked OUTSIDE the fit, marked as measured on a non-canonical build, and explicitly excluded
from the 26-fixture sweep, because no canonical fixture can excite it.

---

## 5. Byte accounting — all four canonical shapes, before and after

Four full canonical builds each side (not `FAST=1`), so the pytest / `emp_expect_fail` /
budget lanes are inside the green.

| shape | before | after | length |
|---|---|---|---|
| `s4.bin` | `445092a7` | `445092a7` | 699108 |
| `s4.debug.bin` | `d7b36f90` | `d7b36f90` | 715010 |
| `demo.bin` | `9320c210` | `9320c210` | 96336 |
| `demo.debug.bin` | `2ef6bf83` | `2ef6bf83` | 101044 |

**All four unchanged** — no repin, no refreeze. All four are taken rather than sonic4 alone
because of the deb2 trap (a zero-byte DEBUG-only label moves `demo.bin` while `s4.bin` sits
still), and this parcel adds three new zero-byte poison modules, which is exactly the shape
that trap has.

**The §8.1 capability-off witness is REACHED.** `SIGIL_WARNINGS=full DEBUG=1 ./build.sh` lists
its `[module.unreachable]` set; `games.sonic4.scene_equiv_proof` is not among them, nor are
`scene_registry`, `ojz_scroll_test` or `engine.parallax`. The witness also went RED on demand:
adopting `own()` on `Scene_OJZ_Default` (§6) makes it report *"BAND 0 differs from
ParallaxConfig_OJZ_Default's at band field 7"* — the amplitude shift the own() supplied.

---

## 6. Red-first evidence

**The registry pins.** `SceneRegistry_CapsFolded` was one-sided against the declared word:
`folded & ~declared == 0` is 0 both when the registry demands exactly what the game declares
AND when it demands LESS, so it structurally cannot see a scene that STOPS raising a bit. Two
new pins close that, and the expected word is DERIVED from the per-scene roster already stated
in that file's banner, never copied from `fold_caps(SCENES)` (which would make the test `x == x`).

Proven red by temporarily giving `Scene_OJZ_Default`'s first layer
`deform: SceneDeform.Own(DeformTable_Zero, 15, 2, 0, 1)` — one authored line, reverted:

```
[Error] scene registry: the twenty scenes fold to capability mask 63, not the hand-derived 31 …
[Error] scene registry: a shipped scene now folds CAP_MULTI_DEFORM_TABLE — some layer authored
        `deform: SceneDeform.Own(..)`. Adopting a per-layer deform table is PARK-1 …
[Error] scene registry: the folded capability mask 63 is NOT a subset of Game.SCANLINE_CAPS 31 …
[Error] scene equivalence: Scene_OJZ_Default BAND 0 differs from ParallaxConfig_OJZ_Default's
        at band field 7
```

63 is `$003F` = the shipped `$001F` plus `$0020`, which is the whole differential.

**Three `emp_expect_fail` cases** (lane **23/23**, baseline was 20):

| case | proves | count |
|---|---|---|
| `poison_scene_own_caps` | two-fixture differential: scene-level `Shared` + per-layer phase/amplitude folds `$0005` and must NOT raise the bit; the SAME scene with the layer's ref made `Own` folds `$0025`. Fragment quotes all three numbers (5 / 37 / 32) | 1 |
| `poison_scene_own_placement` | a scene-level slot refuses `Own`; the legal `Shared` spelling of the same payload still builds | 1 |
| `poison_scene_own_flat` | `own()` with both shifts 15 is refused | **2** |

The third case's count is a finding, not a detail. It was **predicted 1 and measured 2**, and
the prediction was wrong for an instructive reason: `ensure` is non-aborting, so `layer()`
refuses the flat `own()` and builds the layer anyway; `scene_caps()` then folds it to `$0021`
and the `CAP_MULTI_DEFORM_TABLE ⇒ CAP_DEFORM` pin fires in its own words, because the amplitude
that would have supplied `$0004` is precisely the one the constructor just refused. **`$0020` is
raised by the VARIANT and `$0004` by the AMPLITUDE; separating them is what that guard is for**,
and the second diagnostic is that separation being observed rather than asserted. It is the
same shape as the R1 Task 9 `band()` minima cases, arrived at independently.

---

## 7. What Task 10 and PARK-1 inherit

- **`SceneLayer` now carries an attachment (`ly_deform`).** Task 10's curve is the second one,
  and design §2's "a layer may have a curve OR a deform ref, not both" is now expressible:
  `scene_deform_is_own(l.ly_deform)` is the term that half of the ensure needs. The `None` arm
  is not "no deform" at layer level — it is "inherits the scene's" — so the curve∧deform ensure
  must be written against the SCENE's attachment too, not only the layer's.
- **`derived_own(layers, count)`** is the shared walk `scene()` guards on and `scene_caps()`
  folds on, for `derived_mask()`'s reason: two copies could drift into a scene the guard
  approves and the fold classifies differently, which is a wrong record shape with no
  diagnostic.
- **Adoption (PARK-1) is a four-file edit and the build says so, in order.** `SCANLINE_CAPS`,
  `BAND_EXT_N`, `BAND_EXT_BYTES`, and the scene itself; the registry's two pins and Task 8's
  two-directional pin refuse every partial combination. Budget it at **32 cycles per band per
  frame** (§4.1) plus **10 bytes per band** of ROM and of shadow RAM — for every band in the
  game, not only the ones that override.
- **The DEFERRED_WORK item still stands.** `BAND_EXT_N` is a literal because no contract member
  is visible in a record-layout context; exposing each game's `SCANLINE_CAPS` as an
  `emp_defines` row would collapse three of those four edits into one. Task 9 did not need it
  and did not touch it — but it did add a fourth constant to the list it would collapse.
