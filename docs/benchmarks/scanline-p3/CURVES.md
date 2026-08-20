# Curves — the ramping BG scroll factor, and what it costs

**Parcel:** Scanline P3, Phase 1, Task 10 (`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`)
**Branch:** `p3/t10-curves`
**Design:** §2 — "A BG factor may be a **curve(from, to)**: the effective scroll ramps per line
across the layer. Semantics (ruled): an additive per-line delta over the layer's
camera-tracked base scroll — the base term `camX >> factor` is preserved; the spread
`(camX>>to − camX>>from)` is computed once per frame per curve layer in the band hoist with a
bounded `divs.w` by layer height, never in the line loop, never a multiply."

**What landed:** the mechanism end to end — the authored variant and its five guards, the
capability-selected record tail, the once-per-frame hoist, the fifth line loop, the anchored
split's continuation, the instrument that can see all of it, and the two model columns.
**What did not land, deliberately: adoption.** No shipped scene authors a curve. That is why
every canonical image is unchanged below `EndOfRom` (§6).

---

## 1. The authored model

```
layer(world_y: 0, fa: FACTOR_1, fb: FACTOR_1_2, curve: SceneCurve.To(FACTOR_1_8))
```

reads as design §2's `curve(from, to)` with `from` spelled where it already lived. **The
variant carries only the far end.** `from` IS the layer's `fb` — the packed factor already in
the band record, still decoded by `Decode_Factor_B`, still the band's camera-tracked base.
Authoring it a second time inside the payload would be two sources for one record byte, which
is the drift Task 9's `own()` guards were written to refuse.

`SceneCurve` is `None | To(int)`, an exhaustive comptime enum, and "is this layer a curve?" is
`scene_curve_is_none()` — a VARIANT test. 0 is a legal packed-factor field value, so a payload
could never be the discriminator (EMP_PITFALLS §3).

### 1.1 The five guards, and why each one exists

| guard | in | why it is not hygiene |
|---|---|---|
| curve ∧ live amplitude refused | `layer()` | design §2's prohibition — the register argument, §2 below |
| curve ∧ `deform: Own(..)` refused | `layer()` | the same prohibition, named at the attachment the author wrote rather than the amplitude it folds into |
| far-end factor must be a packed `FACTOR_*` | `layer()` | the runtime reads it with the same `cmpi.b #15` sentinels; an out-of-range value decodes as a *different factor*, silently |
| `To(fb)` — a ramp whose ends are equal — refused | `layer()` | it costs a record tail in every band, a per-frame divide and a per-line loop to emit exactly what `.lp_flat` would have broadcast |
| a dormant layer may not carry a curve | `layer()` | a disabled band inherits the PREVIOUS band's scroll words, so there is no base for the ramp to be a delta over — while the fill would still run the curve loop, because the tail's active bit is authored, not derived from the mask |
| curve ∧ an anchor with live shifts refused | `scene()` | see §4 — the overlay writes deform shifts into bands whose layer authored none |

---

## 2. The curve ∧ deform prohibition, with the CORRECTED justification

Design §2 forbids curve and deform on one layer because "the fill loop's register file is
exhausted (verified: `.lp_both` uses all 16)".

**`.lp_both` uses fourteen.** Measured in this tree at the Task-10 tip, post-unroll and
post-Task-9: `d0`–`d7` and `a1`–`a6` are live across that loop; `a0` is spilled at the proc's
entry `movem.l a0/d7,-(sp)` and is dormant *in that loop* (the two single-channel loops DO use
it — it has been their curve walk pointer since the unroll parcel); `a7` only brackets the
proc. So the design's stated reason is checkably false, and a guard resting on it gets deleted
by the next reader.

**The real position is `.lp_curve`'s own allocation**, which is what the guard now cites:

| register | holds |
|---|---|
| `d1` | the accumulator — this line's BG scroll word |
| `d2` | the whole step, `floor(spread/span)` |
| `d3` | the Bresenham remainder |
| `d6` | the Bresenham error |
| `d5` | the span (the modulus) — free only because `d4` has already jumped to the band end |
| `d0.w` | the constant FG word |
| `d4` | the line index (the cross-loop contract: `d4` = the band's end line on exit) |
| `a4` / `a0` | the output cursor and its end |
| `d7` | the band countdown (proc-wide) |

That is every data register. A sampled channel additionally needs a phase base, an amplitude
shift and a sample scratch: **three more against zero free.** The combination is a §9 future
needing a measured re-allocation — which is what the design concluded, for a reason a reader
can now check.

---

## 3. The runtime, in three gated blocks

`CAP_FACTOR_CURVE = $0040`, promoted by Task 5, lowered here. All three blocks carry §3.3
brackets.

### 3.1 `cap_factor_curve_hoist` — once per frame per curve layer

Placed in `Parallax_Step4_Fill` **after Step 4a's copy loop and before Step 4b's anchored
overlay**, and that position is the whole design rather than a convenience:

> **The divisor must be the LAYER's span.** Step 4b splits a band in two at the anchored line.
> By the time the fill walks the shadow view, a split layer is two entries whose spans SUM to
> the layer's — so dividing by either half would make the ramp twice as steep on both sides of
> the boundary. That is the split re-parametrising the curve, which is exactly what design §2
> forbids. Computed here, the step is the layer's; Step 4b's whole-entry copy hands it to the
> split unchanged.

Per curve band it decodes the far-end factor against this frame's `camX` (spelled inline, not
as a `Decode_Factor_Curve` proc — a proc would emit a body, and gated, a stub, in every game),
subtracts the band's base scroll word to get the SPREAD, and divides.

### 3.2 The bounded `divs.w`, argued rather than assumed

The tree's only other `divs` is the plane-B transition ramp in `Parallax_Update`'s band loop,
whose bound is argued in two clauses. The curve's is argued the same way, and the argument is
quoted here because it is what Step 1 of the task asks for:

```
//   * NEVER ZERO, NEVER NEGATIVE, STRUCTURALLY. The divide is reached only past the
//     `ble .curve_next` above, so d4 is >= 1 here. It is also <= 224: Step 4a clamps
//     every shadow top into [0, SCREEN_HEIGHT] and this span is a difference of two
//     such tops (or of 224 and one of them), so the divisor is 1..224 on every path.
//     Divide-by-zero is unreachable by construction, not by likelihood — a zero-span
//     band is a state Step 4a REACHES (two tops both clamped to 224), which is why
//     the test is a real branch and not an assertion.
//   * THE QUOTIENT CANNOT OVERFLOW. The dividend is a WORD spread sign-extended to
//     32 bits, so |quotient| = |spread| / span <= |spread| <= $7FFF and fits the
//     word divs.w must return. Widening the dividend — the 8.8 step this design
//     rejected — is exactly what would break that argument.
```

**The second clause is why the per-line delta is Bresenham and not a fixed-point step.** A
ramp of 300 px over 100 lines is 3 px a line; a ramp of 30 px over 100 lines is a third of a
pixel a line, and a whole-integer step rounds it to zero — no ramp at all. The obvious fix, an
8.8 step `(spread << 8) / span`, **cannot be bounded**: at span 1 it needs `|spread| <= 127` to
keep the quotient inside a word, and the spread is a camera-scaled quantity with no such
bound. Carrying the exact remainder costs one compare and one conditional add per line, is
exact at every span, and keeps the divisor argument identical in shape to the precedent's.

The 68000's `divs` truncates toward zero and gives the remainder the dividend's sign; the hoist
normalises the pair to a FLOOR (`rem += span; whole -= 1` when the remainder is negative) so
the line loop's correction can be one-directional. Without that, a downward ramp would
accumulate its fraction in the wrong direction.

### 3.3 `cap_factor_curve_band` — the fifth line loop

```
.lp_curve:
        move.w  d0, (a4)+      ; FG word — constant across the layer
        move.w  d1, (a4)+      ; BG word — the ramp's value at this line
        add.w   d2, d1         ; acc += whole
        add.w   d3, d6         ; err += remainder
        cmp.w   d5, d6
        blo     .lc_next
        sub.w   d5, d6
        addq.w  #1, d1         ; the fraction carried one whole pixel
    .lc_next:
        cmpa.l  a0, a4
        blo     .lp_curve
```

**Tested BEFORE the deform hoists, and that order is the prohibition made structural.** A
curve band never samples — `layer()` refuses a curve beside a live amplitude and `scene()`
refuses one beside a live anchor shift — so every path through the sampling block would land
on `.lp_flat` anyway. Branching out here is what keeps this ONE new loop variant instead of a
product with the FG/BG/both matrix. The proc's header comment moved from "four specialized
line loops" to five in the same edit; a stale roster comment is how the `.lp_both`-uses-all-16
claim reached the design doc in the first place.

**The hoist falls straight into the loop and the non-curve path branches over both**, not the
other way round: with `CAP_DEFORM` off (a game with curves and no deform tables) the sampling
block between the hoist and `.lp_flat` elides completely, so a loop body outside this gate
would be fallen into by every flat band on the way past.

### 3.4 `cap_factor_curve_split` — six bytes, and the interaction they own

`bset #CURVE_FLAG_CONT_BIT, band_curve_flags(a5)` on the entry Step 4b manufactures. §4.

### 3.5 The record tail

`band_curve` is 10 bytes: four AUTHORED (the far-end factor's two shift nibbles and the flag
byte, plus a pad that keeps the words even) and three DERIVED words the hoist writes into the
SHADOW copy each frame (`bc_step`, `bc_rem`, `bc_span`; their ROM image is zero and is never
read). It is a SECOND capability-selected tail beside Task 8's `band_ext`, not a widening of
it: the two answer to different bits and a game may declare either, both or neither.

**The derived words live in the record rather than in three parallel RAM arrays** because the
anchored overlay copies whole entries — so `copy_band_entry_fwd`/`_back`, already generated
from `sizeof(band_record)`, carry a curve's parameters to its split for free. Three parallel
arrays would need three more shift-down walks in Step 4b, each a place for the two views to
drift. The cost is four dead ROM bytes per band in a curve game, stated rather than hidden.

### 3.6 The one datum that could not live in the record: the carry

`Parallax_Curve_Carry` — two words, capability-sized (`CURVE_CARRY_WORDS`, derived from
`BAND_CURVE_BYTES` so a capability flip stays a three-constant edit). It holds the last curve
entry's final accumulator and error so a split can resume from them.

**It was first built as two words of stack frame**, which is the better shape — live for one
call, free when the capability is off, no RAM layout question at all. It does not survive the
contract closure gate: **any `(sp)` or `d(sp)` access inside a proc with a `preserves()` movem
is read as a write to the saved-register slots**, and the build reported

```
-- [proc.clobber-undeclared] closure firings (§1, 2): --
  Parallax_Fill_PerLine        direct     a0
  Parallax_Fill_PerLine        direct     d7
```

— the exact pair the movem restores. Bisected to those four instructions on 2026-08-20:
replacing them with register moves cleared both firings while every other line of the block
stayed. `addq.l #4, sp` versus a `move.l (sp)+` pop made no difference, which is what ruled
out the frame-depth explanation and left the slot-aliasing one.

### 3.7 The instrument-build recipe — reproducible, and NOT canonical

Neither the build below nor any ROM derived from it is a golden and none may be committed.
Three edits from `p3/t10-curves`'s tip:

| file | from | to |
|---|---|---|
| `games/sonic4/config/game.emp` | `SCANLINE_CAPS = $001F` | `$005F` |
| `engine/level/parallax.emp` | `BAND_CURVE_N = 0` | `1` |
| `engine/ram.emp` | `BAND_CURVE_BYTES = 0` | `10` |

Then `FAST=1 DEBUG=1 ./build.sh`, and copy the artifacts aside as `s4.i1.bin` / `s4.i1.lst`.

| build | crc | len | record stride |
|---|---|---|---|
| **I1** — the capability, complete | `7a05bac5` | 715452 | 20 B |

**Two build-order controls fired on the way there, each a guard doing its job.** `BAND_CURVE_N
= 1` alone, capability still `$001F`, trips BOTH the registry's new two-directional pin
(*"BAND_CURVE_N is 1 but this game does NOT declare CAP_FACTOR_CURVE"*) and — usefully — the
§8.1 equivalence witness, whose message named only `CAP_MULTI_DEFORM_TABLE` because it was
written when there was one tail. It is a conjunction over both tail bits now; that correction
came from running the control, not from reading the file.

The three span pairs in I1's listing:

```
(0) 1061/7864 : $engine.parallax$Parallax_Step4_Fill$cap_factor_curve_hoist_begin:
(0) 1070/78EE : $engine.parallax$Parallax_Step4_Fill$cap_factor_curve_hoist_end:
(0) 1082/7A40 : $engine.parallax$Parallax_Step4_Fill$cap_factor_curve_split_begin:
(0) 1085/7A46 : $engine.parallax$Parallax_Step4_Fill$cap_factor_curve_split_end:
(0) 1122/7BA0 : $engine.parallax$Parallax_Fill_PerLine$cap_factor_curve_band_begin:
(0) 1128/7C06 : $engine.parallax$Parallax_Fill_PerLine$cap_factor_curve_band_end:
```

138 + 6 + 102 = 246 bytes of gated code, all of it absent from both shipped games.

---

## 4. The interaction: an anchor split inside a curve CONTINUES it

Design §2: *"an anchor split inside a curve layer **continues** the curve (the per-line delta
is indexed by absolute screen line, so the split changes deform shifts below the boundary
without re-parametrizing the curve)."*

Two halves make that true, and neither is free:

1. **The step is the LAYER's**, because the hoist runs before the split (§3.1).
2. **The accumulator resumes**, because Step 4b sets `CURVE_FLAG_CONT_BIT` on the entry it
   manufactures and the fill seeds from `Parallax_Curve_Carry` instead of the base scroll.
   The bit is set unconditionally under the capability — the fill reads it only after the
   ACTIVE bit says the band is a curve at all, so it is inert on a flat split — and it cannot
   go stale, because Step 4a re-copies the whole shadow view from ROM before the overlay runs.

The seed is also parked BEFORE the empty-entry early-out, which is not defensive: Step 4a can
clamp a layer to zero on-screen lines (two shadow tops both at 224), and a split below a
zero-line parent must still resume where that parent *would* have started rather than reading
whatever the last non-empty curve band left.

**Asserted, not argued** — §5's split arm derives BOTH hypotheses and reports that they
differ before checking which one the machine matches.

### 4.1 The one case that is refused, and why

`scene()` refuses a curve layer in a scene whose anchor carries live deform shifts. The
overlay writes `pcfg_anchor_dsa/dsb` into EVERY band from the split down, including bands
whose layer authored no deform — so a curve layer down there would become curve ∧ deform at
RUNTIME, past every layer-level guard, and the fill (which tests the curve first) would
silently drop the anchor's deform on exactly those rows. A **pure-boundary** anchor (both
shifts 15) composes with curves and is design §2's own case; it is the one §5 exercises.

---

## 5. The value evidence: `curve_probe.py --arm ramp`

`tools/curve_probe.py` extends Task 2's instrument discipline rather than replacing it: the
buffer is sampled with the machine stopped at `Parallax_Update`'s entry (a completed tick), and
the expectation is DERIVED from the fixture's own authored factors — the base decode, the
far-end decode, the floor division and the Bresenham walk — never read back off the
`bc_step`/`bc_rem` words the walker computed. Reading those and re-multiplying would be
checking the walker against itself.

**The sweep is the point.** A curve is camera-proportional — its whole spread is
`camX>>to − camX>>from` — so at `camX 0` the ramp is flat and a green there is compatible with
a walker that has no curve mechanism at all. The arm therefore refuses to pass unless at least
one swept position produces a spread of 16 px or more, and reports the range.

Verbatim, `s4.i1.bin`, one layer ramping `FACTOR_1_2 -> FACTOR_1_8` across all 224 lines:

```
  camX  spread   BG[0]  BG[223]   verdict
     0       0       0        0      PASS
    96      36     -48      -13      PASS
   320     120    -160      -41      PASS
  1024     384    -512     -130      PASS
  3072    1152   -1536     -390      PASS
  6144    2304   -3072     -779      PASS

spread range over the sweep: 0 .. 2304 px [anti-vacuity floor is 16]

RED-FIRST CONTROL at camX 6144 — the same words against the FLAT expectation:
  RED as required. 223 words differ from flat; first:
    line   1 BG: expected $F400 (-3072)  got $F40A (-3062)
    line   2 BG: expected $F400 (-3072)  got $F414 (-3052)
    line   3 BG: expected $F400 (-3072)  got $F41E (-3042)

ANCHORED SPLIT — Effects_Screen_L[0] = 80; shadow tops [0, 80, 160, 110]
  the two hypotheses differ on 80 words [0 would make this check vacuous]
  CONTINUES the ramp through the split: PASS
  RESTARTS  the ramp at the split:      FAIL   [must FAIL — it is the alternative hypothesis]

  FG: interior steps 223  nonzero   0  max|d1| 0  max|d2| 0
  BG: interior steps 223  nonzero 223  max|d1| 11  max|d2| 1  d1 histogram {10: 160, 11: 63}
```

Five things there are load-bearing:

1. **Every one of the 224 lines matches**, at six camera positions, against an expectation
   computed by different arithmetic in a different language.
2. **The red-first control runs the SAME checker over the SAME bytes** with only the
   expectation changed — the flat band the layer would be without its curve. It goes red, so
   the checker is reading the buffer and not its own prior belief.
3. **The split check derives both hypotheses and reports that they differ on 80 words**
   before reporting which one holds. If they agreed, a pass would prove nothing.
4. **`max|d2| = 1`** on BG is the Bresenham fraction, visible: the step alternates between 10
   and 11 px because the exact rate is 10.28. A whole-integer step would have shown
   `max|d2| = 0` and a ramp 63 px short at the bottom.
5. **FG is flat everywhere** — a curve that leaked into the FG half of the longword would be
   caught by the same compare.

### 5.1 One instrument defect found and fixed, worth carrying

The first run reported camX 3072 FAILING with a buffer flat at −147 while every derived check
was green. **Moving the camera crosses a section boundary**, `Parallax_CheckBoundary` fires,
and `Parallax_StartTransition` stages the section's own config as the TARGET — which leaves
`Parallax_Current_Config` still aimed at the fixture (so the pointer check passes) while
`Parallax_Update`'s Step 1 builds from the target. Two fixes, both kept: the camera moves
BEFORE the fixture is installed, and the transition state is now a derived check of its own.

A second defect was caught by the sweep and not by any single position: the tool's
`FACTOR_*` constants were first hand-written as hex with the shift nibbles TRANSPOSED, so
`FACTOR_1` read as "camX + camX". The tool and the walker then agreed on the wrong factor and
five of six positions passed. It is `packed()`, transcribed from `parallax_dsl.emp`, now.

---

## 6. The cost: `curve_probe.py --arm cost`

Five fixtures, three curve-vs-flat pairs **on the same ROM**, so the capability's 20-byte
record, Step 4a's wider copy and the hoist loop's per-band `btst` are held FIXED and cancel.
`--repeat 3`, spread **0** on every row, every window preemption-free.

| fixture | bands | curve lines | curve bands | `Parallax_Update` | `Fill_PerLine` |
|---|---|---|---|---|---|
| F1 | 1 | 0 | 0 | 4852 | 3352 |
| K1 | 1 | 224 | 1 | 14600 | 12730 |
| F2 | 2 | 0 | 0 | 5862 | 3614 |
| K2 | 2 | 224 | 2 | 16240 | 13242 |
| H2 | 2 | 112 | 1 | 11046 | 8428 |

```
  K1-F1 =  +9748   224 curve lines, 1 curve band
  K2-F2 = +10378   224 curve lines, 2 curve bands
  H2-F2 =  +5184   112 curve lines, 1 curve band

FIT: line_curve = 40.75 cyc/line   band_curve = 630.00 cyc/band
  K1-F1: measured  +9748  predicted +9758.00  residual -10.00
  K2-F2: measured +10378  predicted +10388.00  residual -10.00
  H2-F2: measured  +5184  predicted +5194.00  residual -10.00
  max |residual| = 10.00
```

**A curve line is CHEAPER than a sampled one** — 40.75 against `line_fg_only`'s 76.21 — and
that is the right shape: it reads no table, sign-extends nothing and shifts nothing. §5(b)'s
warning that per-channel costs do not sum applies here in the other direction, which is why
the column has its own fixtures rather than being inferred from the deform ones.

### 6.1 The residual is EXPLAINED, and the explanation is its own measurement

All three residuals are −10.00, which is the signature of a missing term rather than noise.
It is not an intercept — it is data dependence, and the arm measures it directly. K1 with ONE
thing changed, the far-end factor:

| fixture | ramps to | delta vs F1 |
|---|---|---|
| D4 | `FACTOR_1_4` | +9674 |
| K1 | `FACTOR_1_8` | +9748 |
| D32 | `FACTOR_1_32` | +9806 |

Same band, same 224 lines, same everything else: **a 132-cycle range**, larger than the
residual it explains. Two mechanisms, both real:

- the Bresenham correction fires `rem/span` of the lines and costs a `sub.w` + `addq.w` and a
  taken branch when it does;
- `divs.w` is operand-timed on the 68000, so a different dividend is a different number of
  cycles, once per curve band per frame.

K1's band spans 224 lines while K2's and H2's span 112 — different divisors, different
fractions. So **`line_curve` is a CENTRE, not a constant: ±0.30 cyc/line across the measured
range.** Recorded that way in `[parallax.cost_model]` rather than quoted to two decimals as if
it were fixed.

### 6.2 Standing against the canonical model

Task 10 changes `Parallax_Fill_PerLine`'s and `Parallax_Step4_Fill`'s SOURCE, and every
canonical image is unchanged below `EndOfRom` (§7). A byte-identical instruction stream
executes byte-identical instructions, so every fitted coefficient in `[parallax.cost_model]` is
unchanged **by construction** — the stronger form of the standing rule's arm (a). The two new
columns are booked OUTSIDE the fit, marked as measured on a non-canonical build, and excluded
from the 26-fixture sweep, because no canonical fixture can excite them.

### 6.3 The budget term

`scene_axis1_cycles_x100()` charges a curve scene `224 × line_curve + curve_bands ×
band_curve`, at the same whole-screen worst case the sampling term uses and for the same
reason: a layer's on-screen span is a RUNTIME quantity (Step 4a rebases and clamps the tops
every frame), so the comptime-knowable worst case is one curve layer covering the screen.
Added to the sampling term rather than maxed with it — a LAYER may not have both, but a SCENE
may, and charging each for the whole screen is the conservative direction.

`scene_curve_bands()` clamps its walk to the array, and that clamp is required rather than
defensive: `Scene{ .. }` bypasses every constructor guard, and `poison_budget_axis1.emp` uses
that door to declare a 116-layer scene. Every other fold in `scene_dsl.emp` survives that
fixture only by accident (they sit behind `if scene_has_table(s) == 1`, which it fails); this
one is called unconditionally and met it head on — 216 `[index.out-of-bounds]` diagnostics,
measured.

---

## 7. Byte accounting — all four canonical shapes

Four full canonical builds each side (not `FAST=1`), so the pytest / `emp_expect_fail` /
budget lanes are inside the green.

| shape | master | branch | length |
|---|---|---|---|
| `s4.bin` | `445092a7` | `060401e4` | 699108 → 699106 |
| `s4.debug.bin` | `d7b36f90` | `0dbaa80f` | 715010 (unchanged) |
| `demo.bin` | `9320c210` | `c708b114` | 96336 (unchanged) |
| `demo.debug.bin` | `2ef6bf83` | `dec88cc1` | 101044 (unchanged) |

**All four moved, and the plan's expectation ("byte-moving; the sonic4 side moves") is met for
a reason the plan did not name.** `CAP_FACTOR_CURVE = $0040` is not in sonic4's `$001F` mask
and no scene raises it, so every gated block elides and the lowering folds identically. What
moved is the **deb2 symbol appendix**, and only that:

| shape | diffs BEFORE `EndOfRom` | which bytes |
|---|---|---|
| `s4.bin` | **3** | `$18E`/`$18F` header checksum, `$1A7` the header's ROM-END address (the appendix is 2 B shorter) |
| `s4.debug.bin` | **2** | `$18E`/`$18F` only |
| `demo.bin` | **2** | `$18E`/`$18F` only |
| `demo.debug.bin` | **2** | `$18E`/`$18F` only |

Not one byte of executable or data image changed. The cause is a single new zero-length RAM
symbol, `Parallax_Curve_Carry`, entering the packed symbol table — **proven causally, not
assumed**: renaming it to a 15-character-longer name grew the image by exactly 15 bytes
(`6caefeac`/715025 against `0dbaa80f`/715010). This is the carried trap the plan's ledger names
from the other direction — "a ZERO-BYTE label still moves the image ... it was the deb2
appendix" — and it is why all four shapes are checked rather than sonic4 alone.

**No pin moved.** Nothing before `EndOfRom` changed, so no placement changed and no region pin
can have. `tools/demo_specialization_witness.py` passes unedited, with
`Parallax_Fill_PerLine` still **sonic4 686 / demo 2** — re-derived from the build. (The plan's
prose figure of 372 predates the unroll parcel; the tree's own pin already said 686 and still
does.)

The **§8.1 capability-off witness is REACHED**: `SIGIL_WARNINGS=full` lists 27 unreachable
modules, and `games.sonic4.scene_equiv_proof`, `scene_registry`, `ojz_scroll_test` and
`engine.parallax` are not among them. The two new names in that list are this parcel's two
poison fixtures, which is where a poison belongs.

---

## 8. Red-first evidence

Two `emp_expect_fail` cases (lane **25/25**, baseline was 23):

| case | proves | count |
|---|---|---|
| `poison_scene_curve_percell` | **the FORCER.** `scene_forces_per_line()` ARM 3 — authored DEAD by Task 6, woken here. The only fixture in the tree whose control half folds to capability mask ZERO (every other arm removed: no table, no anchor, cell precision, grid-aligned tops), so the single authored difference is the `curve:`. The fragment quotes **65 = $0041** — the capability bit AND the per-line bit arm 3 raises; a 64 would mean the arm went dead again | 1 |
| `poison_scene_curve_deform` | **the PROHIBITION, both halves in one build** — `layer()` refuses a curve beside a live amplitude, `scene()` refuses one beside an anchor with live shifts. The count of 2 is half the assertion: a 1 means one of the two stopped firing, and they live in different constructors for different reasons | **2** |

Both fixtures keep a PASSING half, so a count drift is a real signal in either direction: in
`percell`, a 2 would mean fixture A stopped folding to zero (some other arm started firing on
a bare scene); in `deform`, a 3 would mean fixture A stopped being legal — the prohibition
mis-widened from per-LAYER to per-SCENE.

---

## 9. Verification

| lane | result |
|---|---|
| four canonical builds | green; CRCs in §7 |
| `pytest tools` (build.sh's runner) | **1180 passed, 3 skipped** — unchanged |
| `emp_expect_fail` | **25/25** (baseline 23/23 plus this parcel's two) |
| `effects_budget_check` | **OK — 31 code-derived rows agree** |
| `test_scene_span_labels.py` | **11 passed** |
| `demo_specialization_witness` | OK — span absence + image differential, 8 procs / 878 B |
| `effects_gates.py --rom s4.debug.bin` | **OK — 26 gates** (not required by the ritual — this parcel touches none of `engine/effects/*`, `bg_anim.emp`, `buffers.emp` — but run, and green) |
| `curve_probe --arm ramp` | PASS, 6 camera positions, red-first control RED, split discriminator 80 words |
| `curve_probe --arm cost` | 5 + 2 fixtures, spread 0, residual 10.00 inside a measured 132-cycle band |
| `SIGIL_WARNINGS=full` | 27 unreachable modules, all explained; the witness modules are not among them |

Wall clock, `uptime`-bracketed, every lane run alone, headless CLI only, **no emulator MCP**:
ramp arm 12:05:50 → 12:06:07 (**17 s**, load 1.66); cost arm 12:08:35 → 12:09:48 (**73 s**,
load 1.46 → 5.68); canonical sonic4 release build + lanes 12:14:10 → 12:14:53 (**43 s**).

---

## 10. What a future adoption inherits

- **Adoption is a four-file edit and the build says so, in order**: `SCANLINE_CAPS`,
  `BAND_CURVE_N`, `BAND_CURVE_BYTES`, and the scene itself. The registry's adoption guard and
  the two-directional record pin refuse every partial combination.
- **Budget it at 40.75 cyc per curve line (±0.30) and 630 cyc per curve band per frame**, plus
  10 bytes per band of ROM and of shadow RAM — for every band in the game, not only the curve
  ones, because the tail is a record-shape property of the GAME (design §3.1).
- **The `divs` bound is span-based, not authoring-based.** Nothing an author writes can make
  the divisor zero; the guard is Step 4a's clamp plus the fill's own `ble`. An author CAN make
  a ramp so steep that the whole step dominates and the fraction never fires — that is a
  legal, cheap curve, not a defect.
- **Curve ∧ deform on one layer stays refused**, and §2 is the measured register position a
  future re-allocation would have to beat. `.lp_both` is untouched, so `line_both` remains the
  unchanged regression control it was made into by the unroll parcel.
