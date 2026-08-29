# Band drift — time-driven parallax scroll (design r1)

*2026-08-29. DESIGN ONLY — no engine code, no generator edits, no tests were written for this
document. It is the contract the implementation parcel executes from.*

**Written against aeon `aa2a9f297bcce77a0957aab0205b00e71607ad09`** (this worktree's base;
verified reachable at `origin/master` with `git branch -r --contains HEAD`). Every aeon claim
below was read out of the source at that revision. **No artifact was measured** — this worktree
has no `s4.bin` / `s4.debug.lst`, so every RAM and cycle figure here is a SOURCE derivation and
says so at the point it is made.

**The editor's survey was read at aurora `d15b9e07d53b2e2b0b66b605d2601e98b091b24b`**, resolved
by `git -C ../aurora fetch -q origin && git -C ../aurora rev-parse origin/master` on 2026-08-29
and read with `git show <rev>:docs/reviews/2026-08-26-bg-capability-survey-s1-s2-s3k.md` — never
through the sibling working tree. **That SHA is reachable at `origin/master`**, not local-only.

**No emulator was used.** Two claims in this document are runtime questions and are TAGGED as
such (§10); nothing here is presented as a runtime measurement.

---

## 0. Verdict in six lines

1. **Build it.** Every one of the ~20 autoscroll sites the survey enumerates across S1/S2/S3K is
   expressible, and the arithmetic is **one `add.l` per band per frame** — no multiply, no divide,
   no `CODING_CONVENTIONS.md` §2.1 argument needed anywhere.
2. **8.8 signed is the right fixed point, and this is now derived rather than adopted** (§3): all
   twelve S3K rates in survey row 6 are exact multiples of 1/256 px/frame, and so are all eleven
   S1/S2 rates. 8.8 represents **100% of the surveyed corpus exactly**, with 21× headroom on the
   fastest (DEZ stars, 6 px/frame).
3. **The editor's placement of the accumulator is structurally impossible and must be corrected.**
   "A per-band 16.16 accumulator in the shadow view" cannot work: Step 4a re-copies every shadow
   band from ROM every frame (`copy_band_entry_fwd`), and it *rotates* the array, so an
   accumulator living there would be both wiped and mis-attributed. §1 has the correction.
4. **The accumulator belongs one stage upstream**, in a capability-sized RAM array parallel to
   `Parallax_Current_Scroll_B`, folded into the plane-B target inside `Parallax_Update`'s band
   loop. Placing it there makes the anchored-overlay interaction **vanish** rather than needing a
   `CURVE_FLAG_CONT_BIT`-style mechanism (§6.4).
5. **Engine M is right for the runtime and light for the parcel.** The runtime is ~15
   instructions; the parcel is **five mirrored constants across five files** plus the vacuity
   fixtures. §8 re-derives it: engine **M for code, L for surface**; schema **S** (agree); Aurora
   **S** (agree, not this lane's call).
6. **Two things are the owner's, not mine** (§11): adopting the capability moves every ROM image
   in the tree, and the accumulator's behaviour across a section-boundary config switch is a
   visible choice.

---

## 1. Where the state lives

### 1.1 The correction to the editor's proposal

Survey row 6 prices the engine side as *"a capability-gated `band_drift` tail … holding a signed
8.8 px/frame rate, **a per-band 16.16 accumulator in the shadow view**, added to the decoded base
in Step 4 before the fill."* The rate half is right. The accumulator half cannot be built, for
two independent reasons, both read out of `engine/level/parallax.emp` at the pinned revision:

**(a) The shadow view is destroyed and rebuilt from ROM every frame.** `Parallax_Step4_Fill`'s
Step 4a walks every band and calls `copy_band_entry_fwd(a1, a4)`, whose body is
`copy_run_longs()` × `move.l (src)+,(dst)+` over `sizeof(band_record)` — the **whole** record,
tails included. An accumulator stored in a shadow band tail is overwritten with its ROM image
(zero) before it is ever read. `band_curve`'s own three derived words survive this only because
they are **re-derived** every frame by `.cap_factor_curve_hoist` *after* the copy; a value that
must *accumulate* has no such escape.

**(b) The shadow view is rotated, so slot index ≠ layer index.** Step 4a's `.find_k` locates the
band containing the current plane-space V-scroll and copies **starting at k, wrapping**. Shadow
slot 0 is config band k. Even if (a) were solved, a per-slot accumulator would be attributed to a
different layer the moment `Vscroll_BG` crossed a band top — the accumulated drift would jump
between layers as the camera moved vertically.

This is not a nitpick about wording. Anyone implementing row 6 literally gets a green build, a
zero-valued accumulator, and no diagnostic.

### 1.2 Where each half goes

| quantity | home | why |
|---|---|---|
| **rate** (authored, constant) | ROM: a new capability-selected `band_drift` tail on `band_record`, beside `band_ext` and `band_curve` | It is a per-layer authored constant, which is exactly what the two existing tails carry. Read once per band per frame through `a1`, which already walks the **ROM** band records at `sizeof(band_record)` stride in `Parallax_Update`. |
| **accumulator** (per-band, persists across frames) | RAM: `Parallax_Drift_Acc`, a capability-sized array inside the `Parallax_State` span, **indexed by config band index** — the same indexing `Parallax_Current_Scroll_A` / `_B` use | It must survive the frame boundary and it must be attached to the *layer*, not to a rotated shadow slot. `Parallax_Current_Scroll_B` is the existing per-config-band persistent word; the accumulator is its sibling. |

### 1.3 The structures

```emp
// engine/level/parallax.emp — the THIRD capability-selected tail.
pub const BAND_DRIFT_N = 0            // pinned literal, exactly as BAND_EXT_N / BAND_CURVE_N are
pub struct band_drift (size: 4) {
    bd_rate_1616: i32,   // px/frame in 16.16, PRE-SHIFTED at comptime from the authored 8.8
}
pub struct band_record (size: sizeof(band_entry)
                            + sizeof(band_ext)   * BAND_EXT_N
                            + sizeof(band_curve) * BAND_CURVE_N
                            + sizeof(band_drift) * BAND_DRIFT_N) {
    br_base:  band_entry,
    br_ext:   [band_ext;   BAND_EXT_N],
    br_curve: [band_curve; BAND_CURVE_N],
    br_drift: [band_drift; BAND_DRIFT_N],     // NEW, last — see §1.5
}
```

```emp
// engine/ram.emp — the mirror, and the accumulator.
const BAND_DRIFT_BYTES = 0   // sizeof(band_drift) * BAND_DRIFT_N; pinned in parallax.emp
const DRIFT_ACC_LONGS  = BAND_DRIFT_BYTES / 4   // derived, not a fourth hand-maintained number
// … inside the Parallax_State region, beside Parallax_Curve_Carry:
    Parallax_Drift_Acc: [u32; DRIFT_ACC_LONGS * MAX_PARALLAX_BANDS],
```

`DRIFT_ACC_LONGS` deriving from `BAND_DRIFT_BYTES` is deliberate and copies
`CURVE_CARRY_WORDS = BAND_CURVE_BYTES / 5` exactly: **a capability flip must edit one number on
this side, not two.** A game that declares no drift reserves zero bytes.

### 1.4 Why the accumulator is `u32` and not `u16`

Derived in §3.2: an accumulator whose integer part wraps at anything other than a multiple of the
512-px Plane-B span produces a visible jump. A 16-bit 8.8 accumulator wraps its pixel part at 256,
and 256 mod 512 ≠ 0 → a 256-px snap. A 32-bit accumulator laid out **`[pixels:i16][fraction:u16]`
(pixels in the HIGH word)** wraps at 65536 px = 128 × 512 exactly, so the wrap is invisible. That
layout is also what makes the pixel-part read a single `move.w (a4),Dn` on a big-endian 68000 —
the first word of the long *is* the pixel part. It is the same layout S3K uses for
`Camera_BG_X_pos`, arrived at from the wrap requirement rather than copied from it.

### 1.5 Why `br_drift` is LAST in the record, and why the tail is 4 bytes

- **Last** so that raising `BAND_DRIFT_N` alone does not move `br_ext` or `br_curve`, keeping
  `parallax.emp`'s two existing `offsetof` ensures true without editing them. The new ensure is
  additive.
- **4 bytes** keeps `sizeof(band_record)` at **24** (20 today: 10 legacy + 0 ext + 10 curve), and
  24 % 4 == 0, so `copy_band_entry_fwd`'s `sizeof(band_record) % 4 == 0` fast path survives and no
  trailing `move.w` appears. It also keeps the record EVEN, which
  `tools/parallax_crossing_gate.py` (`SetupError` on an odd `parallax_config`) and the
  address-error argument in `copy_band_entry`'s banner both depend on.
- **`i32` rather than `i16` + a runtime shift.** An 8.8 rate must be aligned to the 16.16
  accumulator. Doing it at runtime costs `lsl.l #8` = **24 cycles per band per frame** on the
  68000 (8 + 2n). Doing it in the lowering costs **2 ROM bytes per band** and zero cycles. The
  lowering is `bd_rate_1616: r << 8`, folded at comptime.

> **Alignment note, because the instinct is wrong here.** `br_drift` sits at record offset 20, and
> band *i*'s record base is `config + sizeof(parallax_config)(=30) + 20i`, so the `i32` lands on
> an EVEN but not 4-aligned address. On a 68000 that is legal and costs nothing: only ODD
> addresses fault, and a long access is two word accesses on the 16-bit bus regardless of
> 4-alignment. No padding is needed and none should be added.

### 1.6 RAM cost — derived from source, not estimated

Per-band bytes in `Parallax_State`, enumerated over the fields `engine/ram.emp` indexes by
`MAX_PARALLAX_BANDS` (this is the same enumeration `PARALLAX_STATE_LONGS`' own comment block
spells as `100 + 18 * M`, extended by the two capability tails):

| field | today | with drift |
|---|---|---|
| `Parallax_Current_Scroll_A` + `_B` | 4 | 4 |
| `Parallax_Shadow_Bands` (= `sizeof(band_record)`) | 20 | **24** |
| `Parallax_Shadow_Scroll_A` + `_B` | 4 | 4 |
| `Parallax_Drift_Acc` | 0 | **4** |
| **per band** | **28** | **36** |

Ceiling-independent remainder: **104 B** (100 from `PARALLAX_STATE_LONGS`' own breakdown — 3
phase words + `Current_Vscroll_BG` + 2 config longs + 4 transition/section bytes + the 80 B
column buffer — plus the 4 B `Parallax_Curve_Carry`, present because `BAND_CURVE_N` is 1).

- **Today:** `104 + 28 × 16` = **552 B**.
- **With drift:** `104 + 36 × 16` = **680 B**.
- **Δ = +128 B**, of which +64 is shadow-band widening and +64 is the accumulator array.
- **Capability OFF: Δ = 0 B**, both terms are capability-sized.

The 552 figure agrees with the independent measurement in the survey's §F addendum (which read it
from a built `s4.debug.lst` *and* re-derived it), so the model this delta rides on is corroborated
from an artifact even though this document measured none.

**Headroom is not re-measured here.** The §F addendum puts the free gap between `Game_RAM_End` and
the initial stack pointer at **6,642 B**; +128 B is **1.9%** of that. I could not re-verify the
6,642 (no build artifact in this worktree) and it is carried as the addendum's number, not as
mine. RAM is not the constraint either way.

`PARALLAX_STATE_LONGS` and the `% 4 == 0` tail ensure in `parallax.emp` both gain a
`sizeof(band_drift) * BAND_DRIFT_N` term plus the accumulator's `4 * BAND_DRIFT_N * M`; both are
derived expressions today and stay derived. `Parallax_Init` clears the whole span in longs, so the
accumulator **zeroes itself at level init with no new code** — provided it sits inside the span
and is a whole number of longs (4 × 16 = 64 ✓).

---

## 2. The runtime, in full

One capability-gated block, in `Parallax_Update` (`engine/level/parallax.emp`), plus one `lea`.

```emp
    // before .band_loop, beside `lea Parallax_Current_Scroll_A, a2`:
    if (Game.SCANLINE_CAPS & CAP_BAND_DRIFT) != 0 {
    .cap_band_drift_setup_begin:
        lea     Parallax_Drift_Acc, a4
    .cap_band_drift_setup_end:
    }

    // … inside the enabled arm, immediately after `jbsr Decode_Factor_B`
    //     (d2 = -decode(camX, factor_b)), BEFORE the snap/lerp:
    if (Game.SCANLINE_CAPS & CAP_BAND_DRIFT) != 0 {
    .cap_band_drift_accum_begin:
        move.l  band_drift.bd_rate_1616(a1), d1   // ROM rate, 16.16 px/frame
        add.l   d1, (a4)                          // acc += rate
        add.w   (a4), d2                          // target_b += acc's PIXEL part (high word)
    .cap_band_drift_accum_end:
    }

    // … at .band_done, on both arms, beside `addq.l #2, a2`:
    if (Game.SCANLINE_CAPS & CAP_BAND_DRIFT) != 0 {
    .cap_band_drift_step_begin:
        addq.l  #4, a4
    .cap_band_drift_step_end:
    }
```

That is the whole runtime. Notes the implementation parcel must not lose:

- **`a4` is free in `Parallax_Update`.** The band loop uses a0 (config), a1 (ROM band), a2/a3
  (current-scroll cursors); a4–a6 are untouched until the `jbra Parallax_Step5_Vscroll` tail.
  `Decode_Factor_A`/`_B` declare `clobbers(d1-d2) preserves(d3)`, so no address register crosses
  them. `Parallax_Update` already declares `clobbers(d0-d7/a0-a6)`, so **no proc contract moves**.
- **`d1` is the right scratch.** It is dead between `Decode_Factor_B`'s return and the lerp's
  `move.w (a3), d1`.
- **No per-band `tst` on the rate.** A zero rate costs 48 cycles; testing for it costs ~30 to save
  ~40 and adds a data-dependent branch. This copies `band_ext`'s stated position exactly
  ("unconditional under the capability — two `movea.l`s and no test"), which is what keeps the
  cost a clean per-band constant for the walker model.
- **The accumulate is in the ENABLED arm only.** A disabled band inherits the band above's scroll
  word and emits nothing of its own, so accumulating for it would be spending cycles on a value
  nothing reads. Its slot is still stepped at `.band_done`. Layer masks are comptime per config,
  so a band cannot toggle at runtime and there is no resume discontinuity to reason about.
- **Drift lands in the plane-B TARGET, before the snap/lerp.** §6.1 derives why.
- **There is no plane-A rate, and that is a refusal by representation.** `Parallax_Update`'s own
  banner records why plane A is hard-locked and never lerped: the FG streaming engine draws
  columns in a camera-anchored 64-column window, so *any* FG scroll offset from the camera drags
  the plane-wrap seam into view at the screen edge. A drift term is exactly such an offset, and an
  unbounded growing one. The entire S1/S2/S3K corpus in survey row 6 is background drift. No field
  exists, so the mistake is unspellable rather than guarded.

---

## 3. The arithmetic

### 3.1 8.8 signed is verified, not assumed

The authored unit is **1/256 px per frame, signed**. Checked against every rate the survey
enumerates:

| source | rates as given | in 1/256 px/frame | exact? |
|---|---|---|---|
| S3K AIZ1 | `$2000`/frame (16.16) | 32 | ✓ |
| S3K MGZ1 | `$500` + `$500`/row | 5, 10, 15, 20, 25 | ✓ |
| S3K MGZ2 | `$800` | 8 | ✓ |
| S3K FBZ out / LBZ2 | `$E00` | 14 | ✓ |
| S3K FBZ2 / SSZ2 | `$8000` | 128 | ✓ |
| S3K SSZ1 | `$500` | 5 | ✓ |
| S3K SSZ2 / Ending | `$1000` / `$800` | 16 / 8 | ✓ |
| S1 GHZ clouds | 1.0 / 0.75 / 0.5 px/f | 256 / 192 / 128 | ✓ |
| S2 WFZ clouds | 0.5 / 0.25 / 0.125 | 128 / 64 / 32 | ✓ |
| S2 HTZ clouds | +4/16 px/f | 64 | ✓ |
| S2 SCZ | 0.5 px/f | 128 | ✓ |
| S2 DEZ stars | 1 … 6 px/f | 256 … 1536 | ✓ |
| S1/S2 Special Stage, titles | ±1 px/f | ±256 | ✓ |

**Every rate in the corpus is exact in 8.8.** That is not luck: S3K's rates are all multiples of
`$100` in its 16.16 accumulators, i.e. multiples of 1/256, and S1/S2's are power-of-two fractions.
The finest rate needed is 5/256 ≈ 0.0195 px/frame (S3K `$500`); the coarsest is 1536/256 = 6
px/frame (DEZ). 8.8's range is ±127.996 px/frame — **21× headroom** on the fastest observed.

A finer format (12.4, 16.16 authored) buys nothing measurable; a coarser one (8.4) loses `$500`
and `$E00`. **8.8 is the right answer and the editor's instinct was correct.**

### 3.2 Wrap behaviour, derived

Let `A` be the accumulator, `[pixels:i16][fraction:u16]`, units 1/65536 px. Per frame
`A ← A + (r << 8)` in 32-bit two's complement, `r` the authored 8.8 rate. The pixel part `P` =
`A >> 16` = the high word, read directly.

1. `A` wraps mod 2³², so `P` wraps mod 2¹⁶ = **65536 px**.
2. `P` is added into the band's plane-B scroll word, a 16-bit quantity, which wraps mod 65536 too.
3. The fill packs that word into the per-line HScroll longword. With 64-cell planes (reg `$10` =
   `$11`, §2.3 of `ENGINE_ARCHITECTURE.md`) Plane B is **512 px** wide and the VDP consumes the
   low 10 bits of the HScroll value.
4. 65536 = 128 × 512, so **the wrap is a whole number of plane widths and is invisible.** ∎

The same argument covers the plane-B scroll word's own overflow, which can already happen today
(`camX` reaches `$8000`) and is already benign for the same reason. This design adds no new
overflow class.

Time-to-wrap is not a correctness concern given the above, but it is worth one line so the
seamlessness is understood as load-bearing rather than theoretical: at 6 px/frame the pixel part
wraps every 10,923 frames ≈ **3 minutes**, well inside a play session; at 5/256 px/frame it takes
~15.5 hours. The fast case is reachable, so a non-seamless wrap would have been a shipped bug.

### 3.3 No multiply, no divide

The per-frame arithmetic is **one 32-bit add**. The 8.8 → 16.16 alignment is a comptime `<< 8` in
`scene_band()`. The pixel-part extraction is a big-endian word read, not a shift.

`CODING_CONVENTIONS.md` §2.1's four-point argument (divisor non-zero structurally · quotient
cannot overflow · alternative named and rejected · cost and executions per frame) **is not needed
at any instruction in this design**, which is the signal the brief asked for. For contrast, the
two nearby mechanisms that *do* divide — the transition lerp's `divs.w d4, d2` and the curve
hoist's span divide — both carry that argument at the instruction, and this one has no instruction
to carry it at.

---

## 4. Per-frame cost, derived

Nominal MC68000 timings. **These are directly comparable to `tools/effects_budget_model.toml`'s
rows**, whose instrument is stated as "IDEAL-CYCLE (the clock excludes bus/VDP/DMA stall)".

**The brief's mispricing caveat does not apply to this block, and here is why rather than a
claim that it doesn't:** no instruction in §2 touches a VDP port, a Z80 bus window, or a DMA
register. `Parallax_Update` runs in the main loop, outside the DMA window, so 68000 accesses to
ROM and work RAM are not stalled by the VDP (which fetches VRAM on its own bus). The nominal table
is the right instrument here. It would *not* be for anything near `VDP_CTRL` — e.g. the reg `$0B`
write a few lines above in the same proc.

### 4.1 The block

| site | instruction | cycles | runs |
|---|---|---|---|
| setup | `lea Parallax_Drift_Acc, a4` | 8 | once/frame |
| accum | `move.l band_drift.bd_rate_1616(a1), d1` — `MOVE.L (d16,An),Dn` | 20 | per **enabled** band |
| accum | `add.l d1, (a4)` — `ADD.L Dn,(An)` = 12 + 8 EA | 20 | per **enabled** band |
| accum | `add.w (a4), d2` — `ADD.W (An),Dn` = 4 + 4 EA | 8 | per **enabled** band |
| step | `addq.l #4, a4` — `ADDQ.L #,An` | 8 | per band (both arms) |

- enabled band: **56 cycles**
- disabled band: **8 cycles**
- frame constant: **8 cycles**

### 4.2 The rider nobody priced: Step 4a's copy widens

`sizeof(band_record)` goes 20 → 24, so `copy_run_longs()` goes 5 → 6 and `copy_band_entry_fwd`
gains one `move.l (a1)+,(a4)+` = **20 cycles**. Step 4a's `.copy_band` loop runs over **every**
band, every frame, in **every scene of a game that declares the bit** — drift authored or not,
because the record shape is a property of the GAME, not of the band (design 3.1's rule, restated
in `band_ext`'s banner).

This is the term the survey's row-6 pricing omits, and the §F addendum already names Step 4a's
copy-all as *"the cycle half — the real gate"* for band-count scaling. It is small here, but it
should be stated rather than discovered.

`copy_band_entry_back` and the second `copy_band_entry_fwd` in Step 4b gain one long each, but
Step 4b runs only on anchored scenes (one config in the tree carries `anchor_ch`), and only over
the bands below the split. Not modelled; named.

### 4.3 Totals against the real budget

Using `tools/effects_budget_model.toml`: `axis1_budget_cycles = 103743`,
`axis1_worst_scene_cycles = 42740.77`.

| scene shape | drift block | Step 4a rider | total/frame | % of axis-1 budget | % of worst shipped scene |
|---|---|---|---|---|---|
| 4 bands, all enabled, drift authored | 4×56 + 8 = 232 | 4×20 = 80 | **312** | 0.30% | 0.73% |
| 4 bands, **no drift authored**, bit declared | 232 | 80 | **312** | 0.30% | 0.73% |
| 8 bands | 456 | 160 | **616** | 0.59% | 1.44% |
| 16 bands (the ceiling) | 904 | 320 | **1224** | 1.18% | 2.86% |
| capability OFF | 0 | 0 | **0** | 0% | 0% |

The second row is the honest one and is the reason the capability matters: **a game that declares
the bit pays for it on every scene**, because both the accumulate (capability-gated, not
rate-gated) and the copy widening (record shape) are unconditional under the bit. A game that does
not declare it pays exactly zero cycles, zero ROM and zero RAM.

**These are derivations, not measurements.** `[parallax.cost_model]`'s own standing rule — *"the
next parcel that touches a `Parallax_*` routine re-measures per the P3 standing rule rather than
carrying them"* — applies to this parcel. The implementation parcel must re-run
`tools/parallax_cost_probe.py` on a capability-raised instrument build and replace the table above
with fitted numbers. Predicted new column: a `band_drift_per_band_cycles` of **~56**, plus **~20**
folded into whichever term the probe attributes Step 4a's copy to. Recording the prediction here
is deliberate — if the measurement lands far from it, the model is wrong somewhere and that is
worth finding.

---

## 5. Cross-checks against the tree's own scaling constraints

- `MAX_PARALLAX_BANDS` is **16** (`engine/system/constants.emp`), pinned by
  `engine/level/scene_dsl.emp`'s `ensure(MAX_PARALLAX_BANDS == 16, …)`. Survey row 4's "8" is the
  known-stale row; the survey's own banner says so, and I re-grounded it here. **No other row of
  the survey is relied on in this document except row 6's reference citations, which are S1/S2/S3K
  facts and not aeon facts.**
- `parallax_config` is 30 bytes and is NOT touched by this design — no header field, no new
  pointer. This is what keeps `engine/buffers.emp` (which keys the HScroll DMA length off the
  header's deform-table fields) out of the parcel entirely.
- The `pcfg_layer_mask` `btst d5, d6` reaches bits 0..15 already; drift adds no mask width.
- Axis-2 (DMA bytes) is untouched: the HScroll entry stays one 896-byte static.

---

## 6. Interaction with what already exists

### 6.1 The transition lerp

Drift folds into `d2` — the plane-B **target** — before `.snap_b` / the lerp. Consequences:

- Outside a transition, `.snap_b` writes `target` straight to `Parallax_Current_Scroll_B[i]`, so
  the drift appears at full value every frame. Correct.
- Inside a transition, the lerp's step is `(target − current) / frames_remaining`, recomputed
  every frame against a target that now moves by `rate` per frame. The ramp still converges: at
  `frames_remaining == 1` the step is the whole residual against that frame's target. The
  `divs.w` divisor invariant (`frames_remaining` is 1..`PARALLAX_TRANS_DEFAULT`, structurally
  non-zero) is untouched, and the quotient bound argument (|gap| ≤ `$7FFF`) is unchanged because
  the drift contribution to `gap` is one frame's `rate`, bounded by ±128 px.
- **Alternative considered and rejected:** folding drift in *after* the lerp (i.e. lerping only
  the camera term). It is arguably cleaner semantically, but it is a behaviour change nobody
  asked for and it forces the accumulate into Step 4a's copy loop — the loop the §F addendum
  flags as the band-count scaling risk. Rejected on both counts. Named here so a future reader
  can reopen it deliberately.

### 6.2 Locked bands (`Factor0Lock` the *encoding*, i.e. `band_factor_b_s1 == 15`)

`Decode_Factor_B` returns `d2 = 0` for a locked band. A locked band with a non-zero drift rate is
a strip that scrolls **only** by drift — which is precisely S2 DEZ's 28 camera-locked star rows and
S3K SSZ1's camera-locked sky. **This is the primary use case, not an edge case, and there is no
guard.** `layer(fb: FACTOR_0, drift: SceneDrift.Rate(n))` is the canonical spelling of a pure
autoscroll strip and the authoring doc should say so.

### 6.3 `Factor0Lock` the *left-column policy* — THE ONE NEW GUARD THIS DESIGN REQUIRES

`SceneLeftColMask.Factor0Lock` is a verified impossibility claim: *"plane B provably never
H-scrolls."* `scene()` verifies it today by scanning every layer's `ly_fa` and `ly_fb` against
`FACTOR_0`, **plus a dedicated arm for curves**, whose message states the principle exactly:

> *"a layer RAMPS its plane-B factor … the ramp is a scroll source the fb scan cannot see: every
> fb can be locked while the curve walks plane-B HScroll away from zero across the layer, and the
> sliver comes back on those lines."*

A drift rate is the same class of invisible plane-B scroll source, in time instead of in space.
Without a fourth arm, a scene can declare `Factor0Lock`, pass the build, drift plane B, and bring
back the artefact the claim says cannot exist.

**Required, in `engine/level/scene_dsl.emp`, inside `scene()`, beside the existing `lcm_f0` curve
arm:** refuse `Factor0Lock` when any layer carries a non-`None` drift with a non-zero rate.
Recommended message shape — refuse a non-zero rate, not merely a non-`None` variant, because
`Rate(0)` is itself refused at `layer()` (§7) so the two guards compose without a hole.

### 6.4 Per-column V-scroll scenes — **falls out, no new guard**

`scene()` already refuses a per-column-V-deform scene that declares no `left_column_mask` policy.
Drift makes plane-B HScroll non-zero, so the artefact is live; §6.3 closes the `Factor0Lock`
escape; therefore a per-column scene that drifts **must** declare `Accept` or `SpriteMask`, and
the build says so with the guards that already exist. Nothing to add. This composition should be
stated in `docs/EFFECTS_AUTHORING.md` so an author meets it as a documented consequence rather
than as a surprise.

### 6.5 The anchored overlay (Step 4b) — **the interaction VANISHES**

This is the strongest argument for §1.2's placement.

The curve tail had to solve a real problem here: Step 4b splits a band by copying it down and
retopping it, and a split inside a curve layer must **continue** the ramp rather than
re-parametrise it. That cost `band_curve`'s three derived words riding inside the record, a
`CURVE_FLAG_CONT_BIT` set on the manufactured entry, a `Parallax_Curve_Carry` RAM pair, and a
paragraph of reasoning about staleness.

Drift needs **none of it**, because the drift is already folded into
`Parallax_Current_Scroll_B[i]` before Step 4a runs. Step 4a copies that word into the shadow;
Step 4b's split does `move.w (a5), 2(a5)` on the shadow scroll words, so the manufactured entry
inherits the parent's **already-drifted** scroll word by the mechanism that already exists. Zero
code, zero flags, zero carry state, and no staleness question.

The dual cost, stated plainly rather than hidden (this is `band_curve`'s own convention for its
four dead ROM bytes): **the rate's shadow copy is never read.** Step 4a copies 4 bytes per band
per frame that nothing consumes. That is the 20 cycles priced in §4.2. §9 records the alternative
that avoids it and why it was rejected.

### 6.6 Band-slot identity across a config switch

`Parallax_Drift_Acc` is indexed by **band slot within the active config**, exactly as
`Parallax_Current_Scroll_A`/`_B` are. When `Parallax_CheckBoundary` switches configs at a section
crossing, slot *i* of the new config may be a different layer, and it inherits the old layer's
accumulated drift.

**This exposure is inherited, not created** — `Parallax_Current_Scroll_B` has it today and the
transition lerp eases across it. But it is now *visible over time* rather than instantaneous, so it
deserves a decision. See §11, card 2. **The recommended default is CONTINUE (no reset), and it is
the zero-code option**: a reset would snap a drifting cloud layer back to phase 0 at a section
boundary, which is worse than a phase inherited between two layers the scene author placed in the
same slot on purpose.

### 6.7 What does NOT ride on this parcel

Survey row 15 (time-driven vertical bob, S3K FBZ / SSZ1) says it *"rides on row 6's engine parcel
(a vertical drift/bob term); S"*. **That is wrong, and the implementation parcel must not take
it.** Plane B's vertical scroll is a **whole-plane** quantity: `Parallax_Step5_Vscroll` computes
one `Parallax_Current_Vscroll_BG` from `camY` and the config's `v_factor_bg` / `v_center_y` /
`v_offset`, and `Vscroll_Write` ships it. There is no per-band vertical field for a per-band bob
to live in, and per-column VSRAM is per-*column*, not per-row.

What FBZ and SSZ1 actually do — a single sine on the whole BG Y — maps to a **scene-level** term
folded into Step 5, not to a per-band tail. It is a different field, a different code site and a
different capability. Worth building; not this parcel. Relaying this back to the editor lane is
listed in §12.

---

## 7. The field contract

Presented in the shape the band-field parcel is producing. **"Assertion" names a file and a
symbol. Where none exists, the row says NONE and that is the answer, not an omission.**

| # | name | type | range | absent / zero | lowers to | assertion LOCATION |
|---|---|---|---|---|---|---|
| 1 | `layer(drift:)` | `SceneDrift` = `None` \| `Rate(r)` | — | `None` = the layer does not drift; it is the default and it lowers to a zero tail | contributes `CAP_BAND_DRIFT` to `scene_caps()` iff `Rate` | the enum is a TYPE — a bad variant is a type error, not an assertion. **No runtime sentinel**: `None` and `Rate(0)` are indistinguishable in ROM, which is why row 2 refuses `Rate(0)`. |
| 2 | `r` — the authored rate | `int`, signed, **units 1/256 px per frame** | `−4096 … +4096` (= ∓16.0 px/frame); `0` REFUSED | n/a — `Rate(0)` is a build error naming `None` | `bd_rate_1616 = r << 8` | **NEW** `ensure` in `layer()`, `engine/level/scene_dsl.emp`. Message must spell the UNIT and the corpus max (6 px/frame = 1536) — see §7.1. |
| 3 | `bd_rate_1616` | `i32` | derived from row 2 | 0 = no motion | ROM, `band_record.br_drift[0]` | `ensure(BAND_DRIFT_N == 0 \|\| offsetof(band_record, br_drift) == sizeof(band_entry) + sizeof(band_ext)*BAND_EXT_N + sizeof(band_curve)*BAND_CURVE_N)` — **NEW**, `engine/level/parallax.emp` |
| 4 | `BAND_DRIFT_N` | pinned literal, 0 or 1 | — | 0 = tail absent; record byte-identical to today | record shape | (a) the capability-off identity `ensure` in `engine/level/parallax.emp` gains a third disjunct; (b) **NEW** two-directional pin in `games/sonic4/data/effects/scene_registry.emp`, modelled on its `CAP_FACTOR_CURVE` pair |
| 5 | `BAND_DRIFT_BYTES` | mirror const, `engine/ram.emp` | 0 or 4 | 0 | shadow reservation + `DRIFT_ACC_LONGS` | the `extern("Parallax_Shadow_Scroll_A") − extern("Parallax_Shadow_Bands") == sizeof(band_record) * MAX_PARALLAX_BANDS` `ensure` in `engine/level/parallax.emp` — its MESSAGE must gain the drift term or it will name the wrong constant |
| 6 | `Parallax_Drift_Acc` | `[u32; DRIFT_ACC_LONGS * MAX_PARALLAX_BANDS]`, 16.16 px | wraps mod 2³² — seamless, §3.2 | zeroed by `Parallax_Init`'s long clear | RAM, inside `Parallax_State` | `ensure((extern("Parallax_State_End") − extern("Parallax_State"))/4 == PARALLAX_STATE_LONGS)` in `engine/level/parallax.emp` — `PARALLAX_STATE_LONGS` gains the drift terms; and the `% 4 == 0` tail ensure beside it |
| 7 | `CAP_BAND_DRIFT` | `pub const`, `engine/level/scene_dsl.emp` | **`$0080`** — derived in §7.2, and the reserved comment block shifts up one bit in the same commit | bit clear = block elided, zero cost | the four gated spans of §2 | `tools/scene_spans.py` derives from the `pub const CAP_*` lines (no edit); `tools/test_scene_span_labels.py`'s gapless-run test is what **forces** `$0080`, and its declared-name-list test carries a literal that must gain the name. The span lane will report "NOT GATED ANYWHERE" until a game raises it (§10.1) |
| 8 | `Factor0Lock` ∧ drift | — | refused | — | — | **NEW** arm in `scene()`, `engine/level/scene_dsl.emp` — §6.3 |
| 9 | shipped-hand-scene adoption | — | refused | — | — | **NEW** `ensure((SceneRegistry_CapsFolded & CAP_BAND_DRIFT) == 0, …)` in `games/sonic4/data/effects/scene_registry.emp`, modelled on the `CAP_FACTOR_CURVE` owner gate at the same site — §11 card 1 |
| 10 | schema `layer.drift: {"rate": int}` | JSON | as row 2 | absent = `None` | `tools/effects_gen.py` → `layer(drift: SceneDrift.Rate(r))` | **NONE TODAY on the aeon side.** `effects_gen.py` refuses unknown keys, so an unknown `drift` key is refused before the field lands; after it lands, the range is enforced by row 2's `ensure` at build time, not by the generator. The empyrean schema is the other half and is not this lane's file. |

### 7.1 The unit hazard, and why the guard is shaped this way

The top authoring hazard is **not** an out-of-range rate; it is an author writing `drift: 1`
meaning *1 px per frame* and getting *1/256 px per frame* — a 256× error that looks like "the
drift doesn't work". No assertion can catch it, because 1 is a legal rate (S3K has no rate that
slow, but `$500` = 5 is only 5× larger).

Three mitigations, in order of strength:

1. **The `ensure` message is the documentation an author will actually read.** It must state the
   unit ("1/256 px per frame"), give one worked conversion ("1 px/frame = 256; S3K AIZ1's clouds
   = 32"), and name the corpus max.
2. **Aurora presents px/frame** and multiplies by 256 on export. One field, as the survey prices
   it, but the field's unit is px/frame in the UI and 1/256 px/frame on the wire. That is the
   editor lane's call, not mine; it is relayed in §12.
3. The bound `|r| ≤ 4096` (16 px/frame) is a **taste** bound, not a correctness bound — nothing
   breaks at 100 px/frame, it just looks absurd. Its message should say that, so a future author
   with a real reason to exceed it raises the bound instead of working around the guard.

### 7.2 `CAP_BAND_DRIFT = $0080`, and the reserved comment block shifts up one bit

**Verified against the check, not guessed.** My first instinct was `$1000` — the first bit past the
reserved block, so as not to disturb five comment lines. That is wrong, and
`tools/test_scene_span_labels.py` would have caught it:

- `test_the_declared_and_retired_bits_are_a_gapless_run_from_bit_zero` asserts
  `sorted(declared ∪ retired) == [1 << i for i in range(N)]`. Today that set is
  `{$0001 retired, $0002, $0004, $0008, $0010, $0020, $0040}` = bits 0..6, gapless. A new bit at
  `$1000` leaves a five-bit hole and the test fails. **The new bit must be `$0080`.**
- `test_reserved_comment_bits_are_not_parsed_as_declarations` asserts the five reserved *names*
  are absent from the declared set. `CAP_BAND_DRIFT` is a different name, so it passes — but the
  reserved comment would then claim `$0080` for `CAP_FG_SPRITE_STRIPS` while a declaration also
  holds it. That is precisely the failure the gapless test's own docstring names: *"a value a
  still-reserved bit already claims in the comment … leaves the names right and the arithmetic
  wrong."*

**Therefore, in one commit:** `pub const CAP_BAND_DRIFT = $0080`, and the reserved comment block
shifts up one bit — `CAP_FG_SPRITE_STRIPS=$0100`, `CAP_BGANIM_BOUND=$0200`, `CAP_DENSE_TIER=$0400`,
`CAP_COMPUTED=$0800`, `CAP_DEGRADE=$1000`. Renumbering a *reserved* bit is free: nothing lowers,
raises, brackets or masks against any of the five, and the reserved-names test checks names, not
values.

**One test must be edited by hand**:
`test_the_declared_bits_are_the_four_p1_survivors_plus_the_two_p3_promotions` carries the declared
name list as a literal ("This list is the whole promotion contract"). It gains `CAP_BAND_DRIFT` and
should be renamed. `tools/scene_spans.py` itself needs no edit — it parses the `pub const` lines.

### 7.3 The standing rule this parcel must obey

`scene_dsl.emp` states it directly: *"the bit arrives WITH its gated block in the emission parcel,
never ahead of it"* — promoting a bit nothing raises manufactures a span gate with no subject,
which is the vacuous-gate shape this suite keeps rediscovering. **`CAP_BAND_DRIFT`, the four
bracketed spans, the `band_drift` struct and the `scene_band()` lowering land in ONE commit.**

---

## 8. Re-deriving "Engine M / Schema S"

The editor's estimate, restated: **Engine M**, **Schema S**, **Aurora S**.

### 8.1 The runtime is smaller than M

Fifteen instructions across four bracketed spans in one proc, no new proc, no contract change, no
header change, no new register pressure, one free address register. By the size scale the survey
itself uses, the *code* is **S**.

### 8.2 The surface is larger than M

Adding a third capability tail is not a local edit, because the tail pattern's cost is its
**mirror set**. Enumerated from the two existing tails' own banners and pins:

| # | file | edit |
|---|---|---|
| 1 | `engine/level/parallax.emp` | `band_drift` struct, `BAND_DRIFT_N`, `band_record`'s third array field, new `offsetof` ensure, capability-off identity ensure gains a disjunct, reservation-ensure MESSAGE gains the term, `PARALLAX_STATE_LONGS` + its `% 4` ensure gain terms, the four gated spans in `Parallax_Update` |
| 2 | `engine/ram.emp` | `BAND_DRIFT_BYTES` + its value ensure, `DRIFT_ACC_LONGS`, `Parallax_Drift_Acc` in the `Parallax_State` region, the block-size comment |
| 3 | `engine/level/scene_dsl.emp` | `CAP_BAND_DRIFT = $0080` + the reserved comment renumber, `SceneDrift` enum + its 3 accessors, `ly_drift` on `SceneLayer`, `layer()` guards, `scene_band()`'s `br_drift`, `scene_caps()` fold, the `Factor0Lock` arm, a pin ensure for any inlined literal |
| 3b | `tools/test_scene_span_labels.py` | the declared-name-list literal gains `CAP_BAND_DRIFT` (§7.2); the gapless-run and reserved-name tests need no edit and are what enforce the bit value |
| 4 | `games/sonic4/data/effects/scene_registry.emp` | the import list (a partial import of `band_record` fails **at the declaration**, in `parallax.emp`, naming a type that file plainly declares — its own banner warns about this), the two-directional `BAND_DRIFT_N` pin, the shipped-hand-scene owner gate |
| 5 | `games/sonic4/test/scene_equiv_proof.emp` | the import list and the capability-off byte-identity ensure |
| 6 | `games/sonic4/config/game.emp` | `SCANLINE_CAPS` — **only on adoption**, §11 card 1 |
| 7 | `tools/effects_gen.py` | the JSON `layer.drift` lowering (**owned by another parcel tonight — this document does not touch it**) |
| 8 | `docs/EFFECTS_AUTHORING.md`, `docs/ENGINE_ARCHITECTURE.md` §4.6 | the field, and §6.4's composition |
| 9 | `tools/effects_budget_model.toml` | the re-measured cost column (§4.3) |
| 10 | fixtures | §10 |

Six of those carry an `ensure` that must be **shown red** before it is trusted (`EMP_PITFALLS.md`'s
universal countermeasure). Precedent for the size: the curve tail was **one task of a twelve-task
phase** and additionally invented `CURVE_CARRY_WORDS` — and this design deliberately avoids that
one by deriving `DRIFT_ACC_LONGS` instead.

### 8.3 Verdict

| layer | editor | this lane | delta |
|---|---|---|---|
| Engine — runtime code | M | **S** | smaller |
| Engine — parcel surface | (folded into M) | **L** | larger |
| Engine — overall | **M** | **M, with the mirror set and the vacuity fixtures being most of it** | agree on the label, disagree on where the weight sits |
| Schema | S | **S** | **agree** |
| Aurora | S | **S** — with the px/frame ↔ 1/256 unit decision attached (§7.1) | agree, plus a rider |

**Numbers, so this is not another T-shirt:** ~15 new instructions, ~10 new/edited `ensure`s across
5 files, +128 B RAM and +4 B/band ROM when adopted (0 when not), and a derived 312–1224 cycles per
frame (0.30%–1.18% of the axis-1 budget). The estimate that was wrong was not the label — it was
the accumulator's *location* (§1.1), which is a correctness error rather than a sizing one.

---

## 9. The alternative that was considered and rejected

**Option B — a parallel ROM rate array, reached through a new `pcfg_drift_table` word in
`parallax_config`.**

- **Avoids** the 4 dead shadow bytes per band, the +64 B shadow RAM, and the +20 cycles/band/frame
  of §4.2 — i.e. the entire "record shape is a game property" tax.
- **Costs** a 30 → 34 byte `parallax_config`, which moves every config record in the tree and pulls
  `engine/buffers.emp` (which keys the HScroll DMA length off header fields) into the parcel; a
  per-frame null test or a second capability gate on the pointer; and — the decisive term — a
  **new lowering shape** that `scene_band()` cannot express. Today every per-band ROM quantity is
  in `band_record`. A second per-band array means the registry, `effects_gen.py`,
  `scene_equiv_proof.emp` and the budget model all learn a shape that exists for one field.

**Rejected.** The saving is 0.077%–0.31% of the axis-1 budget and 64 B of RAM; the cost is a novel
per-band data shape. `band_curve`'s banner sets the precedent for how to handle exactly this
trade — *"The cost is four dead ROM bytes per band in a curve game, stated plainly rather than
hidden"* — and this design states four dead **shadow** bytes the same way.

Recorded here with its numbers so that if the band ceiling is ever raised again, or if Step 4a's
copy-all becomes the measured bottleneck the §F addendum warns it might, the reopening is a
decision rather than a rediscovery.

---

## 10. The zero-content vacuity problem

**No shipped scene will declare drift.** `sonic4`'s `SCANLINE_CAPS` is `$005E` and `demo`'s is
`0`, so with `CAP_BAND_DRIFT` unraised every gate over real content passes trivially, and every
bracketed span is comptime-elided out of both listings.

This tree has already learned this twice, and the lesson is written down in `scene_dsl.emp`:

> *"a bit with no lowering and a bit with a lowering nobody uses produce the SAME row, and the
> lane cannot tell them apart, because a comptime-elided span is absent from the listing either
> way."*

So the span-label lane will report `CAP_BAND_DRIFT: NOT GATED ANYWHERE` and that will be
**correct and uninformative**. The proof must come from elsewhere. Required, in order:

### 10.1 A capability-raised instrument build — the presence witness

Follow the shape of `docs/benchmarks/scanline-p3/CURVES.md` and `DEFORM-OWN.md` exactly. A
**deliberately-authored non-zero fixture**: a scene with at least one layer carrying
`drift: SceneDrift.Rate(n)` with n ≠ 0, built with `CAP_BAND_DRIFT` raised and `BAND_DRIFT_N = 1`,
recorded in `docs/benchmarks/scanline-p4/BAND-DRIFT.md` with:
- all four span-label pairs present in the `.lst`,
- the ROM crc and length,
- `sizeof(band_record)` observed as 24 via the shadow-span arithmetic.

### 10.2 The converse control — the VALUE control, not a presence control

The same fixture with **every** layer at `drift: SceneDrift.None`, capability still raised. The
spans still appear (the block is capability-gated, not rate-gated) and the accumulator never
leaves zero.

**This is the control that makes 10.1 non-vacuous, and its shape matters:** a control that merely
*drops the capability* proves only that the gate elides, which is the question four green gates
already answered. The control that earns its place holds the capability fixed and varies the
**authored value** — the confound-varying discipline this lane keeps having to relearn.

### 10.3 Red-first on every new `ensure`

`EMP_PITFALLS.md`'s universal countermeasure. Poison fixtures under `games/sonic4/test/poison/`,
each **shown** red rather than asserted red:

| poison | what it must fail on |
|---|---|
| `poison_factor0_lock_drift` | `Factor0Lock` + a non-zero drift (§6.3) |
| `poison_drift_rate_zero` | `Rate(0)` — must name `None` |
| `poison_drift_rate_range` | `\|r\| > 4096` |
| `poison_drift_cap_mismatch` (×2) | `BAND_DRIFT_N` raised without `CAP_BAND_DRIFT`, and the reverse |

### 10.4 The byte-identity proof must be extended AND proven red

`games/sonic4/test/scene_equiv_proof.emp`'s capability-off ensure must name `BAND_DRIFT_N`, and —
following the precedent already recorded in that file's own comment (*"PROVEN RED (2026-08-20):
with `BAND_EXT_N` flipped to 1 this fails reporting 20 against 10"*) — the parcel must record the
observed failure text from flipping `BAND_DRIFT_N` **alone**, expecting `24` against `20`.

### 10.5 Reachability

`SIGIL_WARNINGS=full DEBUG=1 ./build.sh 2>&1 | grep module.unreachable`, compared **by NAME**
against a run on the same tree without the change. `EMP_PITFALLS.md` §3 explicitly corrects the
older "compare the count against 25" advice; four new poison fixtures will move the count by four
and that is expected, not signal. A guard in an unreachable module is a dead guard.

### 10.6 The numeric witness — **TAGGED, RUNTIME**

The one check that catches a green-but-dead implementation: with the camera frozen, read
`Parallax_Drift_Acc[i]` at frame N and frame N+K and expect **exactly** `K × (r << 8)`, and read
the band's HScroll longword and expect its BG half to have moved by the accumulator's high word.

**This is an emulator measurement. It cannot be run from a background agent** (they deadlock on
the Oracle MCP), so it is TAGGED for the controller or the owner. Two constraints on it:
- the expectation must be **derived from the authored rate**, never copied from a pin or a nearby
  number;
- `romBytes` must be compared against the ROM on disk before the measurement — a stale MCP shim
  serves a previous freeze behind a correct-looking `romPath`.

### 10.7 Cost re-measurement

`tools/parallax_cost_probe.py` on the 10.1 instrument build, per `[parallax.cost_model]`'s own
standing rule, replacing §4.3's derivations with fitted numbers.

---

## 11. For the owner — two cards, neither of them mine to decide

**Card 1 — Adopting the capability moves every ROM image in the tree.**
`BAND_DRIFT_N` is a pinned engine-wide literal for the reason `BAND_EXT_N`'s banner records at
length (the context that lays out an emitted `data` record type binds no contract members, so it
cannot read `Game.SCANLINE_CAPS`). So flipping it to 1 widens `band_record` 20 → 24 for **both
games**, including `demo`, whose `SCANLINE_CAPS` is 0 and which will never drift. That is exactly
what the d-15 showcase parcel did for `CAP_FACTOR_CURVE`, and `scene_registry.emp` carries an
explicit owner gate refusing a shipped hand scene from folding it. **Landing the mechanism with
`BAND_DRIFT_N = 0` moves no byte and needs no card. Adopting it on a scene the owner sees does,
and this design proposes the same owner-gate `ensure` (§7 row 9) so adoption cannot happen by
accident.**

**Card 2 — What a drifting layer does at a section boundary.**
The accumulator is indexed by band slot, so crossing into a config whose slot *i* is a different
layer transfers the accumulated drift. Options: **CONTINUE** (recommended; zero code; a cloud
layer that occupies slot 2 in both scenes drifts seamlessly across the boundary) or **RESET**
(costs a `clr.l` per band in `Parallax_CheckBoundary` and produces a visible snap on every
crossing). This changes what the owner sees, so it is his call. My recommendation is CONTINUE and
it is also the do-nothing default — but it should be *chosen*, because the failure mode
(a drift phase inherited by an unrelated layer) is only invisible while scene authors keep drifting
layers in matching slots.

---

## 12. Reconciliation, and what to relay

### 12.1 There is NO existing moving-band booking to reconcile with — the name collides, the
mechanism does not

`docs/DEFERRED_WORK.md` carries **"R1 booking: moving bands (patchable ON and/or OFF edges)"** and
**"R1 booking: N bands"**. Both are in the **raster / HBlank** domain: they are about
`engine/effects/raster.emp`'s compiled programs, `Raster_BuildSchedule`'s per-entry `.suppress`
path, rule 6 / CLAIM E-A, `check_band_pairing`, `check_intervals`, anchor channels and the
`HI_CLAMP` bias word. Their "band" is a **palette/tint band on a scanline program**, not a
parallax scroll band. They were DESIGNED 2026-08-28 in
`docs/superpowers/specs/2026-08-28-raster-band-ownership-design.md`.

**This design neither reconciles with nor supersedes them.** They share no file, no struct, no RAM
and no capability bit. `grep -i "drift\|autoscroll\|time-driven"` over `DEFERRED_WORK.md` returns
no parallax-drift booking at all — every hit is a different sense of the word "drift" (constant
drift-guards, camera drift, doc drift).

**The collision is worth stating loudly**, because "moving bands" is now two mechanisms in this
repo. Recommended: this one is **band drift** and never "moving bands"; the raster one keeps
"moving bands". The implementation parcel should book this design in `DEFERRED_WORK.md` under a
heading that cannot be confused with the raster pair.

### 12.2 To the editor lane

1. **The accumulator cannot live in the shadow view** (§1.1). Row 6's engine sketch needs that one
   correction; everything else in it holds.
2. **8.8 is confirmed exact for the whole corpus** (§3.1) — including all twelve S3K rates, which
   is a nicer result than "close enough".
3. **Row 15 does not ride on this parcel** (§6.7). Vertical BG scroll is whole-plane in this
   engine; a bob is a scene-level Step-5 term, a different field and a different bit. Row 15's "S"
   is a sizing of the wrong mechanism.
4. **The Aurora field's unit is a decision, not a detail** (§7.1). One field, as priced — but
   px/frame in the UI with a ×256 on export is strongly preferred to raw 1/256 units, because the
   256× units error is the hazard no guard can catch.
5. **Their §5 does not resolve.** The brief that reached this lane cited "their §5" for what of
   theirs is blocked; the survey at `d15b9e07` has sections **A–F** and no §5, and its own
   "BLOCKED" line reads *"none. Every row was resolved from source."* What is blocked is inferable
   from row 6's verdict column (their one field arrives *after* engine and schema) — but it is not
   in a §5, and the citation should not be repeated.

---

## 13. Implementation order

Each step ends green and red-first, per §10.3.

1. `CAP_BAND_DRIFT` + `band_drift` + `BAND_DRIFT_N = 0` + `band_record`'s third field + the three
   `ensure`s in `parallax.emp`. **Byte-identical build required** — the capability-off identity
   ensure is the check, and it must be proven red by flipping `BAND_DRIFT_N` alone (§10.4).
2. `engine/ram.emp`: `BAND_DRIFT_BYTES`, `DRIFT_ACC_LONGS`, `Parallax_Drift_Acc`,
   `PARALLAX_STATE_LONGS`' terms. Still byte-identical at `BAND_DRIFT_N = 0`.
3. `scene_dsl.emp`: `SceneDrift`, `ly_drift`, `layer()` guards, `scene_band()`'s `br_drift`,
   `scene_caps()` fold, the `Factor0Lock` arm. Still byte-identical.
4. The four gated spans in `Parallax_Update`. Still byte-identical (elided at caps `$005E`).
5. `scene_registry.emp` + `scene_equiv_proof.emp` pins. Still byte-identical.
6. The instrument build + its converse control (§10.1, §10.2), the poison fixtures (§10.3),
   `BAND-DRIFT.md`.
7. `tools/effects_gen.py`'s `layer.drift` lowering — **coordinate with whoever owns that file**;
   it was under another parcel's edit on 2026-08-29.
8. Cost re-measurement (§10.7) and the budget-model row.
9. Docs: `EFFECTS_AUTHORING.md`, `ENGINE_ARCHITECTURE.md` §4.6, the `DEFERRED_WORK.md` booking
   (§12.1).
10. **STOP.** Adoption on a shipped scene is card 1 and is the owner's.

---

## 14. What this document does NOT claim

- **No cycle figure here was measured.** §4 is a nominal-table derivation whose instrument choice
  is argued (§4 preamble); it is comparable to the budget model's IDEAL-CYCLE rows and it must be
  replaced by a probe run.
- **No RAM figure was read from an artifact by this lane.** §1.6 is a source derivation; it agrees
  with the survey §F addendum's artifact measurement, which is corroboration, not a measurement of
  mine. The 6,642 B headroom figure is carried from that addendum unverified.
- **`tools/effects_gen.py` was not read or edited**, per the brief. §13 step 7 is a placeholder
  whose shape the owning parcel must confirm.
- §7.2's bit value **was** verified against `tools/test_scene_span_labels.py`'s two bit tests, and
  the verification overturned this document's first answer (`$1000` → `$0080` plus a reserved-block
  renumber). The three tests' bodies were read; the rest of that file was not.
- **Nothing was run in an emulator.** §10.6 is TAGGED.
- Every S1/S2/S3K citation in §3.1 is **relayed from the survey at `d15b9e07`**, not independently
  re-read in the disassemblies. The *arithmetic* on those rates (that they are exact multiples of
  1/256) is mine and is checkable from the table as written.
