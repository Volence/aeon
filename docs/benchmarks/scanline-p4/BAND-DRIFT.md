# Band drift — backgrounds that move on their own, and what they cost

**Parcel:** band drift, 2026-08-29. **Branch:** `band-drift`.
**Design:** `docs/superpowers/specs/2026-08-29-band-drift-design.md`.

**What landed:** the mechanism end to end at `BAND_DRIFT_N = 0` — the capability bit, the
authored variant and its two guards, the capability-selected record tail, the RAM accumulator
array, the three bracketed runtime spans, the `Factor0Lock` arm, the registry pins and the poison
fixtures. **What did not land, deliberately: adoption.** No shipped scene authors a drift, so
three of the four canonical images are byte-identical (§5).

---

## 1. The authored model

```
layer(world_y: 0, fa: FACTOR_0, fb: FACTOR_0, drift: SceneDrift.Rate(32))
```

is a strip that scrolls **only by drift** — S2 DEZ's 28 camera-locked star rows and S3K SSZ1's
camera-locked sky. It is the primary case, not an edge one: `Decode_Factor_B` returns 0 for a
locked band and the accumulator supplies the whole scroll. Nothing refuses the combination and
nothing should.

`SceneDrift` is `None | Rate(int)`, an exhaustive comptime enum, and "is this layer drifting?" is
`scene_drift_is_none()` — a VARIANT test. **`Rate(0)` is a build error naming `None`**, which is
what makes the accessor's `0` default unambiguous: the two would otherwise lower to the same four
zero bytes and no runtime discriminator could exist. (`scene_curve_to()` had to pick `$0FF` as its
inert default for want of exactly this refusal.)

### 1.1 The unit, and the hazard no assertion can catch

The authored unit is **1/256 px per frame, signed**. `Rate(256)` is one pixel per frame.

**The top hazard is not an out-of-range rate.** It is an author writing `Rate(1)` meaning *one
pixel per frame* and getting 1/256 of one — a 256x error that presents as "the drift doesn't
work". No assertion can catch it: `1` is a legal rate, and S3K's slowest real rate (`$500` = 5) is
only five times larger. **The mitigation is the two `ensure` messages**, both of which spell the
unit, give worked conversions and name the corpus maximum. They are the field's documentation, and
they were written as such rather than as diagnostics.

The `|r| <= 4096` bound is a **taste** bound and its message says so outright, so a future author
with a real reason raises it instead of routing around it. Nothing breaks above it: the wrap is
seamless at any rate (§3.2) and the arithmetic is one add.

### 1.2 8.8 is derived, not adopted

Every autoscroll rate in the surveyed S1/S2/S3K corpus is an **exact** multiple of 1/256 px/frame
— S3K's are multiples of `$100` in its own 16.16 accumulators (AIZ1 `$2000` = 32, MGZ1 `$500` = 5,
FBZ2 `$8000` = 128); S1/S2's are power-of-two fractions (GHZ clouds 1 / 0.75 / 0.5 = 256 / 192 /
128). 8.8 represents **100% of the corpus exactly**, with 21x headroom on the fastest observed
(S2 DEZ's stars, 6 px/frame = 1536). A coarser format (8.4) cannot spell `$500` or `$E00`.

---

## 2. Where the state lives — and the correction that made the parcel buildable

The rate is an authored constant and rides in a third capability-selected `band_record` tail
(`band_drift`, 4 bytes, LAST). **The accumulator cannot live beside it**, for two independent
reasons, both properties of the shadow view:

1. **The shadow view is destroyed and rebuilt from ROM every frame.** Step 4a walks every band and
   calls `copy_band_entry_fwd()`, which copies the whole record, tails included. An accumulator in
   a shadow tail is overwritten with its ROM image (zero) before it is ever read. `band_curve`'s
   three derived words survive only because they are **re-derived** after the copy by
   `.cap_factor_curve_hoist`; a value that must *accumulate* has no such escape.
2. **The shadow view is rotated**, so slot index != layer index. Step 4a's `.find_k` starts the
   copy at the band containing the current plane-space V-scroll and wraps. A per-slot accumulator
   would be attributed to a different layer the moment `Vscroll_BG` crossed a band top, and the
   drift phase would visibly jump between layers as the camera moved vertically.

So the accumulator lives one stage upstream: `Parallax_Drift_Acc`, indexed by **config band
index** exactly as `Parallax_Current_Scroll_A/_B` are, folded into the plane-B **target** inside
`Parallax_Update`'s band loop before Step 4a ever runs.

**That placement is also why the anchored overlay needs nothing.** Step 4b's split does
`move.w (a5), 2(a5)` on the shadow scroll words, so the manufactured entry inherits the parent's
*already-drifted* word by the mechanism that already exists — none of the `CURVE_FLAG_CONT_BIT`,
`Parallax_Curve_Carry` and staleness reasoning the curve tail required.

**The dual cost, stated rather than hidden** (`band_curve`'s own convention for its four dead ROM
bytes): the rate's shadow copy is never read. Step 4a copies 4 bytes per band per frame that
nothing consumes. That is the 16 cyc/band measured in §4.

---

## 3. The arithmetic

### 3.1 The whole runtime, as emitted

Read out of `s4.i2.bin` at the three span pairs, not transcribed from source:

| span | address | bytes | instruction | nominal MC68000 |
|---|---|---|---|---|
| `cap_band_drift_setup` | `$7752` | `49F8 8944` | `LEA ($8944).W, A4` | 8, once/frame |
| `cap_band_drift_accum` | `$7774` | `2229 0014` | `MOVE.L ($0014,A1), D1` | 20, per enabled band |
| | `$7778` | `D394` | `ADD.L D1, (A4)` | 20, per enabled band |
| | `$777A` | `D454` | `ADD.W (A4), D2` | 8, per enabled band |
| `cap_band_drift_step` | `$77B0` | `588C` | `ADDQ.L #4, A4` | 8, per band, both arms |

Fifteen bytes. `$0014` = 20 = `offsetof(band_record, br_drift)` at the shipped tail set, and the
`LEA` took the **short** absolute form.

- **`a4` is free**, and that is checked rather than assumed: `Parallax_Update` uses a0-a3 only, and
  `Decode_Factor_A/_B` declare `clobbers(d1-d2) preserves(d3)`, so no address register crosses
  them. `Parallax_Update` already declares `clobbers(d0-d7/a0-a6)` — no proc contract moved.
- **No per-band `tst` on the rate.** A zero rate costs 48 cycles; testing for it costs ~30 to save
  ~40 and adds a data-dependent branch. `band_ext` takes the same position for the same reason:
  unconditional-under-the-capability keeps the cost a clean per-band constant for the fitted model
  instead of a content-dependent one.
- **The accumulate is in the ENABLED arm; the step is on both.** A disabled band inherits the band
  above and emits nothing of its own, so accumulating for it would spend cycles on a value nothing
  reads — but its slot must still be stepped or every later band's accumulator shifts by one.

### 3.2 The wrap is seamless by arithmetic, not by luck

`A` is `[pixels:i16][fraction:u16]`, pixels HIGH. Per frame `A += (r << 8)` in 32-bit two's
complement; the pixel part is `A`'s high word, read directly by `ADD.W (A4), D2` on a big-endian
68000 — a word read, not a shift.

1. `A` wraps mod 2^32, so the pixel part wraps mod 65536 px.
2. It is added into a 16-bit plane-B scroll word, which wraps mod 65536 too.
3. Plane B is **512 px** wide (reg `$10` = `$11`) and the VDP consumes the low 10 bits.
4. **65536 = 128 x 512 exactly**, so the wrap is a whole number of plane widths and is invisible.

This is load-bearing rather than theoretical: at 6 px/frame the pixel part wraps every 10,923
frames ~= **3 minutes**, well inside a play session. A 16-bit 8.8 accumulator would wrap its pixel
part at 256, and 256 mod 512 != 0 — a visible 256-px snap every ~43 s. The high-word layout is
chosen from the wrap requirement, and it is the same layout S3K uses for `Camera_BG_X_pos`.

### 3.3 No multiply, no divide

The per-frame arithmetic is one 32-bit add. The 8.8 -> 16.16 alignment is a comptime `<< 8` in
`scene_band()` (at runtime it would be `lsl.l #8` = 24 cyc/band/frame on the 68000, 8 + 2n).
`CODING_CONVENTIONS.md` §2.1's four-point argument is not needed at any instruction here — there
is no instruction to carry it at.

---

## 4. COST — MEASURED, and the model held

### 4.1 The three builds, and why the third one exists

`tools/parallax_cost_probe.py`, `--repeat 1`, **spread 0 on every fixture of all three runs**,
every window preemption-free. `Parallax_Update`'s per-routine row, inclusive of callees, camera
frozen.

| build | `SCANLINE_CAPS` | `BAND_DRIFT_N` | record | drift spans in `.lst` | crc / len |
|---|---|---|---|---|---|
| canonical | `$005E` | 0 | 20 | 0 | `a9676c6b` / 735818 |
| **i3** | `$005E` | 1 | **24** | **0** | `6ad54642` / 735816 |
| **i2** | `$00DE` | 1 | **24** | **3 pairs** | `c9767161` / 736010 |

**i3 is the fixture that makes the measurement a split rather than a lump**, and the design did
not ask for it. The design's §4 bundles two independent costs — the drift block itself and Step
4a's copy widening — and predicts them separately (~56 and ~20) while noting the probe would fold
the second into "whichever term it attributes it to". i3 has the **widened record with the block
elided**, so `i3 - canonical` is the copy widening ALONE and `i2 - i3` is the block ALONE. One
thing changes per pair, which is the discipline the whole fixture matrix is built on.

Recipe for i3 (all three edits are one-line and reversible):
`BAND_DRIFT_N = 1` (`engine/level/parallax.emp`), `BAND_DRIFT_BYTES = 4` (`engine/ram.emp`), and
the `CAP_BAND_DRIFT -> BAND_DRIFT_N` reverse pin in `scene_registry.emp` temporarily relaxed —
that pin exists precisely to refuse this shape, which is why an instrument needs it out of the way
and a shipped tree does not. i2 is the same minus the pin relaxation, plus `SCANLINE_CAPS = $00DE`.
Both need `SIGIL_CONTRACTS=0`; see §6.

### 4.2 The measurement

Two independent band-count ladders (W0-W3 flat, W4/W5/W6/W24 with a NULL table attached). **Both
give identical marginals.**

| fixture | bands | canonical | i3 (24, off) | i2 (24, ON) | copy `i3-c` | drift `i2-i3` | total `i2-c` |
|---|---|---|---|---|---|---|---|
| W0 | 1 | 4700 | 4716 | 4780 | **+16** | **+64** | +80 |
| W1 | 2 | 5682 | 5714 | 5830 | **+32** | **+116** | +148 |
| W2 | 3 | 6644 | 6692 | 6860 | **+48** | **+168** | +216 |
| W3 | 4 | 7606 | 7670 | 7890 | **+64** | **+220** | +284 |
| W4 | 1 | 4732 | 4748 | 4812 | +16 | +64 | +80 |
| W5 | 2 | 5746 | 5778 | 5894 | +32 | +116 | +148 |
| W6 | 3 | 6740 | 6788 | 6956 | +48 | +168 | +216 |
| W24 | 4 | 7734 | 7798 | 8018 | +64 | +220 | +284 |

**Fitted columns:**

| term | canonical | i3 | i2 | `i2 - canonical` |
|---|---|---|---|---|
| `base` | 4719.1 | 4734.9 | 4798.9 | **+79.8** |
| `band_perline` | 970.6 | 986.2 | 1038.2 | **+67.6** |
| everything else | — | — | — | 0.0 to +7.1 (anchor terms) |

### 4.3 The answer, and it is against the design's own prediction

| quantity | design predicted | **measured** | gap |
|---|---|---|---|
| `band_drift_per_band_cycles` (the block) | **56** | **52** marginal / **56** on band 1 | -4 marginal, exact on band 1 |
| Step 4a copy widening, per band | **~20** | **16** | -4 |
| frame constant (the `lea`) | 8 | 12 | +4 |
| **combined, per band** | **76** | **68** | **-8 (-10.5%)** |
| 4-band scene, per frame | 312 | **284** | -9.0% |
| 16-band scene, per frame | 1224 | **1100** | -10.1% |

**The model held.** Every predicted term is within 11% and the shape is exactly right — linear in
band count, zero for every other term in the walker, identical on two independent ladders.

**The residual is 4 cycles per band and it is NOT explained here.** The encoded instructions in
§3.1 price at exactly 56 nominal per enabled band, and band 1 measures exactly `56 + 8` = 64. The
*marginal* band measures 52. Something in the widened loop body is 4 cycles cheaper from the
second band on, and the honest statement is that this measurement does not identify it. The same
4-cycle gap appears in the copy widening (16 measured against a nominal 20 for one added
`move.l (a1)+,(a4)+`), which is suggestive and is exactly the kind of suggestion that has been
wrong here before — recorded as an observation, not as a mechanism. The instrument is an emulator
IDEAL-CYCLE clock, not the datasheet.

### 4.4 Against the real budget

`axis1_budget_cycles = 103743`, `axis1_worst_scene_cycles = 42740.77`:

| scene shape | cyc/frame | % axis-1 budget | % worst shipped scene |
|---|---|---|---|
| 4 bands, drift authored | **284** | 0.274% | 0.664% |
| 4 bands, **no drift authored**, bit declared | **284** | 0.274% | 0.664% |
| 8 bands | 556 | 0.536% | 1.301% |
| 16 bands (the ceiling) | 1100 | 1.060% | 2.574% |
| capability OFF | **0** | 0% | 0% |

**The second row is the honest one and is the whole reason the capability exists.** A game that
declares the bit pays on every scene: the accumulate is capability-gated (not rate-gated) and the
copy widening is a property of the GAME's record shape, not of the band. A game that does not
declare it pays exactly zero cycles, zero ROM and zero RAM.

### 4.5 ⚠ THE SHIPPED `[parallax.cost_model]` ROWS WERE ALREADY STALE, FOR A REASON THAT IS NOT THIS PARCEL

Found while making the instrument reach the subject, and it matters more than the drift columns:

- **`tools/parallax_cost_probe.py` carried `BE_SIZE = 10` as the band-record stride** while the
  shipped record has been **20 bytes since 2026-08-26** (the d-15 showcase adopted a curve). Every
  synthetic config it installed was laid out at *half* the stride the walker advances by, so bands
  1..n-1 were decoded out of the middle of their predecessors. Band 0 is the one index a wrong
  stride cannot corrupt — which is exactly what let it look plausible. **This is the same tell, in
  the same shape, as the 2026-08-27 finding in `tools/left_col_mask_probe.py`**, whose lesson its
  sibling `parallax_hscroll_probe.py` wrote into a banner and this file never learned. The stride
  is now DERIVED from the `.lst` under measure (`set_stride()`), and printed on every run.
- **The committed model rows are up to 13.7% low against master.** They were fitted 2026-08-22 at
  a 10-byte record; the record widened three days later and the standing rule — *"the next parcel
  that touches a `Parallax_*` routine re-measures"* — never fired, because no parcel touched one.

| term | committed (2026-08-22, record 10) | re-measured (record 20) | drift |
|---|---|---|---|
| `base` | 4664.00 | **4719.1** | +55.1 |
| `band_perline` | 854.00 | **970.6** | **+116.6 (+13.7%)** |
| `multiband` | 20.00 | **39.1** | +19.1 |
| `band_sampling` | 154.00 | **167.2** | +13.2 |
| `vdeform` | 1472.00 | **1452.9** | -19.1 |
| `anchor` | 981.4 | **1024.5** | +43.1 |
| `anchor_ops` | 60.77 | **84.9** | +24.1 |
| `line_fg_only` / `line_bg_only` / `line_both` / `shift_lines` | 26.00 / 26.90 / 124.53 / 2.00 | 26.0 / 27.2 / 125.3 / 2.0 | ~0 |
| residual, un-anchored subset (18) | **0.00** | **67.56** | |
| residual, all 26 | 43.6 | 64.2 | |

**The un-anchored residual going 0.00 -> 67.56 is the row to look at**, and it is not noise (spread
0 on every fixture). The additive model was *exactly* identified at the 10-byte record and is not
at the 20-byte one, which says a term the model does not carry became non-negligible when the
record widened. Naming it is a separate parcel; it is booked in `docs/DEFERRED_WORK.md`.

Note that the drift columns in §4.2 are **immune to this**: they are differences between three
builds measured by the *same* corrected instrument on the same day, so whatever the model is
missing cancels.

---

## 5. What moved, and what did not

Built from **deleted** ROMs (a byte-neutral parcel cannot witness its own freshness, and a
leftover ROM ships four perfect CRCs as proof of a build that never ran).

| shape | baseline at this branch's base commit | after | moved? |
|---|---|---|---|
| `s4.bin` | `06d2ccf6` / 719205 | `06d2ccf6` / 719205 | **no** |
| `s4.debug.bin` | `a9676c6b` / 735818 | `a9676c6b` / 735818 | **no** |
| `demo.bin` | `3415e3ef` / 96372 | `3415e3ef` / 96372 | **no** |
| `demo.debug.bin` | `7599953e` / 101113 | `fdedb6e4` / 101113 | **yes — appendix only** |

**`demo.debug.bin` is the one that moves and it is worth being precise about.** 771 bytes differ,
and byte-for-byte:

- **2 bytes at `$18E`-`$18F`** — the Genesis header checksum, which sigil folds over the whole
  image including the appendix.
- **769 bytes at or above `EndOfRom` (`$1121C`)** — the deb2 symbol appendix.
- **Below `EndOfRom` the image is byte-identical**, and a symbol-by-symbol diff of the two listings
  shows exactly one added name (`Parallax_Drift_Acc`, a zero-length RAM array) with **no address
  moved and no symbol removed**.

`s4.debug.bin` carries the same new symbol in its listing and does **not** move at all. That
asymmetry is a property of sigil's deb2 emitter, not of this parcel, and is recorded as an
observation rather than explained.

---

## 6. ⚠ ADOPTION HAS A SIGIL RIDER THE DESIGN DOES NOT MENTION

Measured while building i2 — with the drift block live, sigil's **contract-closure gate fails**:

```
error: [call.live-clobbered] (D1c) moved against the frozen baseline.
  NEW firings: []
  GONE firings: ["Parallax_Update @ Decode_Factor_B :: d2 (got 0, want 1)"]
```

`add.w (a4), d2` reads d2 immediately on return from `Decode_Factor_B`, so d2 is now a genuine
live output of that call where the analysis previously saw it dead. **GONE is the destructive
direction** the gate is loudest about (the same closure feeds `find_dead_saves`, so a dropped row
can mean a load-bearing save is now reported dead), so it is a hard failure and not a warning.

The baseline lives in the **sigil** repo (`crates/sigil-harness/src/contract_baseline.rs`) and must
be adjudicated and updated in the same paired commit as any adoption. Both instrument builds above
were made with `SIGIL_CONTRACTS=0` and say so.

**It does not affect the canonical shapes.** They elide the block and build green with the gate on
— verified in §5. It is an adoption cost, not a landing one.

---

## 7. What is proven, and what is NOT

**Proven red, in the lane** (`emp_expect_fail`, 48/48 — a case passes only when the build FAILS
carrying the named fragment at the named diagnostic count):

| guard | fixture | fragment |
|---|---|---|
| `Rate(0)` refused, naming `None` | `poison_layer_drift.emp` Z | "is not a slow drift, it is no drift" |
| `|r| <= 4096` taste bound | `poison_layer_drift.emp` R | "THIS IS A TASTE BOUND" |
| `Factor0Lock` ^ drift refused | `poison_scene_lcm_factor0.emp` DR | "but a layer DRIFTS" |

**Proven red, by staged instrument builds** (each message reproduced in the parcel's evidence):

| guard | how |
|---|---|
| registry reverse pin (`BAND_DRIFT_N` without the capability) | `BAND_DRIFT_N = 1` alone -> fires naming both constants |
| shadow reservation, MESSAGE half | `BAND_DRIFT_N = 1` + capability, `BAND_DRIFT_BYTES` still 0 -> fires and **names `BAND_DRIFT_BYTES`**, which is row 5's whole requirement |

**Proven by artifact** (read from `s4.i2.lst`, derived from the symbols, not copied):

- all three span pairs present in the listing;
- `sizeof(band_record)` = **24**, from `Parallax_Shadow_Scroll_A - Parallax_Shadow_Bands` = 384 / 16;
- `Parallax_Drift_Acc` -> `Parallax_Curve_Carry` = **64 B** = 4 x `MAX_PARALLAX_BANDS`;
- `Parallax_State` span 552 -> **680 B**, i.e. **+128 B** exactly as the design derived from source.

### NOT PROVEN — and this is the important half

- **The runtime numeric witness was NOT run.** With the camera frozen, `Parallax_Drift_Acc[i]` at
  frame N and N+K must equal exactly `K * (rate << 8)`, and the band's HScroll longword's BG half
  must have moved by the accumulator's high word. **Nothing in this parcel executed the drift
  block against an expectation.** The cost measurement runs the walker, and a walker that
  accumulates into a slot nothing displays would cost precisely the same. This is the check that
  separates "works" from "green and dead", and it is TAGGED for the controller. Its expectation
  must be derived from the authored rate, never copied from a pin.
- **`scene_equiv_proof.emp`'s capability-off identity ensure could not be proven red**, because it
  is **vacuous for sonic4**: the guard is
  `(SCANLINE_CAPS & (MDT | FACTOR_CURVE | BAND_DRIFT)) != 0 || sizeof(band_record) == sizeof(band_entry)`
  and `$005E & CAP_FACTOR_CURVE != 0`, so the left disjunct is unconditionally true and has been
  since 2026-08-26. The design cites that file's "PROVEN RED (2026-08-20)" comment as a live
  precedent and expects a "24 against 20" flip; **that flip is not obtainable in this tree.** The
  disjunct gained `CAP_BAND_DRIFT` for correctness, and the vacuity is booked rather than papered
  over.
- **No emulator looked at a picture.** Everything above is a cycle row, a listing symbol or a ROM
  byte. Whether a drifting cloud layer *looks* right is unverified.
