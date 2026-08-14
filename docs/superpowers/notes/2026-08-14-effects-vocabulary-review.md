# Effects authoring vocabulary — five-lens review

**Date:** 2026-08-14
**Subject:** `docs/EFFECTS_AUTHORING.md`, `engine/effects/raster_dsl.emp`, `engine/effects/raster.emp`,
`engine/effects/palette_dsl.emp`, and the review artifact built from them.
**Occasion:** Effects P3 Parcel A merged (`f406d50b` / sigil `ae6ec13d`). The owner's question was
whether the vocabulary lets us **push the engine**, or only change a couple of lines.

Five independent lenses: language/clarity, the Genesis technique corpus, runtime-vs-DSL surface,
adversarial hands-on authoring, and a fresh-eyes ambition read. Findings below are marked
**VERIFIED** where the controller reproduced them directly, **ARGUED** where the lens's reasoning is
sound but unreproduced.

---

## 0. The headline answer

**Better than expected on capability, worse than expected on guard integrity.**

The vocabulary reaches more of `docs/research/visual-techniques-backlog.md` than anyone had said out
loud — two backlog entries are authorable *today* with zero new code, and a third is one constructor
away. But four guards do not do what they claim, one of them in a way Parcel D will hit immediately,
and two runtime routines are dead or self-contradicting.

The arm schedule — the thing most likely to be subtly wrong — was independently hand-traced for
k = 2, 3, 6 and 7 events by two lenses and is **correct**. That is the single most reassuring result.

---

## 1. Confirmed defects

### 1.1 `check_mixed_fire` checks the FIRST `SetReg`, not the last — VERIFIED

`raster_dsl.emp`, predicate `n_set == 0 || n_cram == 0 || first_set == 0`.

```
fire(120, [ sh_on(), pal_region(...), set_reg($8721, $8700) ])
```

`n_set = 2`, `first_set = 0` → **passes**. The trailing `set_reg` executes *after* the CRAM op has
burned `EFX_BLANK_DELAY`, which is precisely the ordering ruling 14 exists to forbid — and strictly
worse than the ~45%-across-the-line artifact it was written to bound. The diagnostic would also print
"it is at index 0", which is actively misleading.

Both shipped fixtures have at most one `SetReg`, so this is invisible today. "S/H on, swap the region,
change the backdrop" is an ordinary band and is exactly what Parcel D writes.

**Correct predicate:** all `SetReg`s occupy a prefix — `last_set == n_set - 1`, or equivalently
`first_cram > last_set`.

### 1.2 The per-fire budget models only half of what spends the budget — VERIFIED

`fire` sums `op_cram_words`, and `op_cram_words(SetReg) = 0`. There is **no ceiling on op count at
all**. So `fire(120, [sh_on(), sh_on(), sh_on(), cram($4A,[a,b,c])])` passes every `ensure`, as does a
fire carrying twenty `set_reg`s (42 body words, still under the 128-byte program cap).

The comment above the guard — which the controller wrote — says "RASTER_CRAM_MAX is a PER-FIRE **cycle**
budget… the ceiling is on the whole fire." The implementation is a CRAM-word budget. This is the exact
defect class the parcel spent twelve tasks hunting: a guard described more strongly than what it does.
`EFFECTS_AUTHORING.md`'s guarantee ("a fire that blows the ~60-cycle budget" made impossible)
overclaims accordingly.

### 1.3 `Raster_Clear` is a no-op; `HBlank_Uninstall` is unreachable — VERIFIED

`raster.emp`, `Raster_VBlank`:

```
move.l  Raster_Pending, d0
beq.s   .no_install          // 0 is filtered HERE
clr.l   Raster_Pending
move.l  d0, Raster_Program
bne.s   .copy_program        // d0 provably non-zero -> always taken
jbsr    HBlank_Uninstall     // dead
```

`Raster_Clear` stores 0 into `Raster_Pending`, which the `beq` treats as "nothing pending". The
documented "0 = clear/uninstall" convention on `Raster_Install` is therefore unreachable, HInt is never
disarmed, and `HBlank_Uninstall`'s only reference in the tree is that dead branch. Both procs have zero
callers (sections go through `Raster_InstallSection`), so it is fully latent — **but
`EFFECTS_AUTHORING.md` documents `Raster_Clear` as install route 2's teardown**, i.e. the doc points
authors at a no-op.

Fix: sentinel the clear (`Raster_Pending = -1`) or branch on `Raster_Program`.

### 1.4 `raster.emp`'s ENTER comment contradicts the measured T-1 calibration — VERIFIED

`raster.emp:406-407` instructs: *"Author the OP_RUN_GRADIENT fire at `gradient_top - 2` so line
gradient_top gets stream[0]."* The shipped constructor authors it at `top - 1`
(`rgp_arm1: raster_arm(top - 1, top)`), and `raster.emp:216-232` records that **T-2 is the rejected
naive derivation** that put the whole run one line high on hardware (boundaries at 107/119/… instead
of 108/120/…). This is pre-calibration text that survived the fix, sitting in the module the authoring
doc names as source of truth for the runtime side. Anyone hand-authoring a dense program from the
handler-top comment reproduces the exact bug the gate already caught once.

### 1.5 The doc claims a `BUGS.md` entry is missing; it is present — VERIFIED

`EFFECTS_AUTHORING.md` says the buffer over-read is *"awaiting a `docs/BUGS.md` entry: checked at this
commit, `BUGS.md` does not yet carry it."* `BUGS.md:79` carries it as **EFX-4**. Controller-introduced:
Task 9 was told to write "not yet booked", Task 10 then booked it, and only the `.emp` comment was
re-swept. A sentence that advertises having been verified and was not is the worst single defect on a
page whose credibility rests on citation discipline.

### 1.6 `set_reg` accepts scheduler-owned registers — VERIFIED

The only bounds are `$8000..$97FF` plus same-register agreement. That admits:

- **reg `$0A`** — the line-counter the scheduler owns. The handler writes the arm word *first*, then the
  ops, so a mid-frame `set_reg($8Axx, …)` overrides the schedule and desynchronises the rest of the frame.
- **reg `$0F`** — autoincrement. Changing it mid-frame breaks the addressing stride of every subsequent
  CRAM-class op.
- **reg `$00`** — a program that disables its own HInt.

A short denylist is a five-line `ensure` and in the spirit of the existing guards.

---

## 2. Capability findings — the answer to "can we push the engine?"

### 2.1 `OP_CRAM` is target-agnostic. VSRAM writes are already shipped runtime capability — VERIFIED

`Raster_HInt`'s `.op_cram` does `move.l (a1)+, (a2)` with **whatever command longword the program
carries**, then streams `count` words to `VDP_DATA`. Nothing in the handler is CRAM-specific; only the
*constructors* hardcode `VdpTarget.Cram`.

So backlog **§8 "VScroll per-cell"** — mid-frame vertical scroll splits — and VRAM writes to the HScroll
table are **executable by the shipped decoder today**, blocked purely by a missing constructor. P3 §9
lists `RUN_VSRAM` as out-of-scope on the premise that the op set is CRAM-only; **that premise is wrong
at the wire level.**

Estimated cost: ~25 lines (a `vdp_write(target, addr, words)` constructor plus match arms). Two traps:
`op_mask` must return **0** for a non-CRAM target — today it would derive `1 << (addr >> 5)` from a
VSRAM address, and at offset 0 that yields mask bit 0, the *character's* CRAM line, forcing a spurious
re-assert every frame — and `cram`'s address bounds must become target-conditional.

**This is the highest value-to-cost item in the review.**

### 2.2 Backlog §11 "mid-frame plane base swap" is authorable today — VERIFIED

Status in the backlog is `IDEA`, and its engine touchpoints list *"HInt handler that swaps base regs"*
as though one were needed. `OP_SET_REG` **is** that handler, and regs `$02`/`$04` are `$82xx`/`$84xx`,
inside `set_reg`'s accepted range:

```
fire(112, [ set_reg($8402, $8407) ]),   // plane B nametable -> $C000
fire(216, [ set_reg($8407, $8407) ]),   // restore
```

17 words, traced correct. What §11 still needs is the **content** side (a second nametable, and a
streamer that fills it), not raster support. The entry is stale in its raster half.

Same reasoning reaches backlog **§5 "backdrop register animation"** (reg `$07`, authorable today —
only the per-frame animation half is missing) and the HInt half of **§20 "sprite multiplexing"**
(reg `$05` SAT-base swap per band).

### 2.3 Backlog §19 "per-section HInt dispatch" is already answered — ARGUED

Ristar registers per-stage *code*; Aeon registers per-section *data* (`Sec.sec_raster_table` +
`Raster_InstallSection`) walked by one fixed handler, with the expensive per-line work moved out of the
interrupt into the parallax system's frame-level buffer. §19's stated motivation ("removes a branch tree
that gets uglier as more raster effects are added") is already satisfied with no branch tree at all.
The entry should be re-statused; what it would still buy is per-section arbitrary *code*, a much larger
and different claim than the entry makes.

### 2.4 The undeclared architecture worth naming — ARGUED

**Programs are frozen schedules; everything that moves, moves by mutating staged data** (variants, cycle
scripts, gradient streams) **or one blessed patched word.** That is a command-buffer-plus-dynamic-uniforms
split and it is the right shape for a 60-cycle handler. Because it is undeclared, its single exception
grew crooked (§3.1), and the temptation after this review will be to add runtime knobs *into* programs.
The right move is named patch fields and richer staging, not a mutable program format.

---

## 3. Structural gaps

### 3.1 The encoder knows every arm word's offset and throws it away — ARGUED

`raster_words` computes the full layout, yet `Raster_PatchWaterLine` re-derives one offset as a hand-pinned
magic number (`WATER_TEMPLATE_ARM0_OFF = 6`), valid only at `init_count == 1`, only for the first fire,
guarded only by an assertion the doc tells each future author to hand-copy.

Every runtime-varying effect on the backlog — lava surface, rising flood, lightning flash (§5),
beat-driven pulses (§18), a gradient that survives vertical camera movement — needs exactly this
mechanism, and today each would be another bespoke buffer/offset/proc trio with another prose invariant.
**The generalisation is small: let a fire be declared patchable at authoring time and have the DSL emit
its offset as a named constant.** That deletes the init-count trap, the co-located-assertion ritual, and
the doc's own "not checked" warning box in one move.

Corollaries found in the field:
- `region_boundary`'s `sh: 1` is **secretly load-bearing for a reason unrelated to Shadow/Highlight** —
  it is the only way to manufacture the init word the patch offset needs. A lava line that does not want
  S/H must write `set_reg($8C81, $8C81)`, a no-op register write, purely to keep `init_count` at 1. The
  doc never says this; it documents how to *detect* the failure, not how to *fix* it.
- The water assertion the doc prescribes proves "word 3 is *an* arm word for *some* line". It does **not**
  prove the program has one event, so it passes cleanly on a two-event program where the patch then drags
  an unrelated band rigidly along with the boundary.
- Everything is named Water (`Raster_InstallWater`, `Raster_Water_World_Y`, …), so authoring a lava line
  means calling `InstallWater` — which reads as a bug at every future review.
- There is exactly one `Buf_B` and one world anchor: **a section can have at most one moving boundary of
  any kind.** Lava and water together is impossible.

### 3.2 The world anchor has no owner — ARGUED

Raster owns `Raster_Water_World_Y`; the parallax/deformation system (§4.6) owns per-line HScroll wave and
ripple. A complete underwater section — palette boundary *plus* shimmer below the same line, S3K
Hydrocity's actual look — needs both subsystems to agree where the surface is, and they share no seam.
**Neither subsystem is missing a capability; the anchor is missing an owner.** Worth settling before
Parcel C freezes `sec_effects` as the composition point.

### 3.3 No mid-screen restore — ARGUED

There is a derived mechanism for restoring state at the frame top (`set_reg`'s paired reset, init words
derived from ops) and **nothing** for restoring at a lower line. A tint over lines 100-140 needs a second
fire at 140 that hand-supplies base colours — which `pal_region` cannot reach (staging holds variants, not
the base) and `cram` can only do with duplicated literals that rot when the base palette changes. The
"apply/restore" pairing the designers clearly understood stops working mid-screen.

This is the concrete form of the framing question below.

---

## 4. The framing question for the owner

**Is a raster program a schedule of events, or a description of screen bands — and is it a finished
artifact or a template?**

Mid-screen restore, world anchoring, the water patch, and composition are the same question surfacing in
four places. Bands compile down to fires-plus-resets without touching the wire format or the cycle budget;
the question is whether authors should ever see the fires at all. Nearly everything left on the backlog's
raster shelf varies at runtime.

If the answer is "bands and templates, eventually", the current vocabulary is the correct *target* of a
band compiler and nothing need change now except knowing it. If the answer is "events and constants,
forever", the restore and anchoring gaps are permanent and should be named as such.

**It is much cheaper to answer before Parcel C's presets freeze the shape around single static event
lists.**

---

## 5. Further defects, ARGUED (not yet reproduced)

- **`pal_region` is never cross-checked against the bound variant's `v_lines`.** If the variant does not
  cover `pal_line`, `Palette_DeriveVariant` never writes that staging line and `OP_PAL_REGION` streams
  **uninitialised RAM to CRAM mid-frame**. Safe today only because `variant()`'s `lines` defaults to
  `%1110`.
- **Conflicting frame-top resets for one register are undetected.** `prog_init` dedupes by *value*, so two
  `set_reg`s on the same register with different resets emit two init words; the later silently wins, and
  `init_count` becomes 2, which also breaks the water patch offset.
- **The dense constructor is the weakest in the suite.** `mask` is unvalidated (a wrong `pal_dirty_mask` is
  the observed P1 bug, and the dense tier is the only place it is still authorable); `rgp_init_word` is
  hardcoded `$8C81`; `stream` length is never checked against `lines * 3`.
- **Cycle `period` may be off by one.** The runtime reloads and decrements such that `period: 8` yields a
  9-frame cadence, while the field comment and `OJZ_ShimmerCycle` both claim 8. GATE-EVIDENCE contains **no
  cycling measurement at all**, so the claim is unverified in either direction.
- **`Pal_Cycle_None` does not exist**, although `palette.emp` documents that stopping a neighbour's cycling
  requires an empty script rather than NULL. Gated on EFX-3 (a count-0 script sets `PAL_ACT_CYCLE` before
  reading the count, re-arming the 15.1%-of-frame derive).
- **`set_reg` writes bypass `VDP_Shadow_Table`**, so a later `Flush_VDP_Shadow` with that register dirty
  restores the shadow's value. Undocumented at the constructor.
- **An undocumented ~7-8 event ceiling per program** (128-byte buffer; ~7 words per CRAM event). Discovered
  only by overflowing it; the error speaks bytes, not "drop two fires".
- **`arm_at`'s `gap <= 255` ensure is unreachable** on a 224-line screen — a guard that cannot fire, in a
  codebase with a documented history of exactly that.

---

## 6. Day-one authoring friction, ranked

1. **CRAM byte addresses are hand-computed from (line, entry)** — hit on every attempt involving colour.
   `pal_region` takes `addr` **and** `pal_line` **and** `entry`, then `ensure`s they agree: the author
   supplies the same fact twice and the vocabulary checks their arithmetic instead of doing it.
   **Proposed:** `cram_at(pal_line, entry, colours)`, and derive `addr` inside `pal_region`. That makes the
   mismatch class *unrepresentable* rather than *detected* — the standard the doc sets for itself.
2. The event ceiling is undiscoverable until overflow.
3. **No `sh_off()`**, and no named boot-base register words anywhere — forcing raw `$8C81`/`$8700` typing,
   the exact thing the doc's opening paragraph promises to eliminate. Those literals are unpinned against
   `boot_data.emp`.
4. The `init_count`/water-patch coupling is emergent and unowned.
5. **No colour helper** — every colour is a hand-packed BGR word with 3-bit channels at `<<1`/`<<5`/`<<9`.
6. No sanctioned way to generate fires programmatically; every doc example is a literal list.

---

## 7. Document defects

The specification *content* is sound — the arithmetic checked out everywhere both lenses tested it against
the encoder and both fixtures. What disqualifies the doc as-is is **provenance decay**:

- the status block is written in future tense ("are written to satisfy", "After Parcel A lands") and tells
  a first-time author the subsystem does not exist yet
- ~20 `raster.emp` citations are 11-22 lines stale, and the doc's own References section silently
  contradicts its body (`:572` vs `:561-575` for the same constant)
- the false "checked at this commit" claim (§1.5)
- a self-contradiction: four helpers are called "private to `raster_dsl`", then helper membership is
  explained as force-publicising private items. Both cannot hold — and the unstated consequence is that this
  parcel injected ~20 short generic names (`fire`, `cram`, `set_reg`, `variant`, `op_size`, `op_mask`) into
  **every** module in the tree. `emp_helper_closure.py` catches helper-vs-helper collisions; it does not
  catch a collision against a module-local name.
- `first_mismatch`'s documented prefix hole appears in the module but not in the doc
- **the palette variant system is never explained** despite being in the title and despite `pal_region`'s
  `slot`/`pal_line`/`entry` reaching straight into it. An author can copy the water fixture; they cannot
  author a *different* variant effect from this document.
- the T-1 trap section is placed before the wire format, so it warns readers who do not yet have the model

Structural fix: move "The authoring shape" and "Descriptor set" above the encoding sections. A first-time
author currently meets a dense-tier off-by-one, then arm-schedule algebra, then a two-fixture arithmetic
audit, before reaching the eight-line recipe — which sits after a table captioned "an author never calls
these".

---

## 8. What the review says to protect

- **Screen-line-first authoring.** Authors name the line the effect *lands on*; the encoder owns every `-1`.
  Both hands-on lenses reported zero friction here, which for this subsystem is a real achievement.
- **Derived-not-typed headers** and the two-independent-computations length check.
- **No dangerous defaults** (`sh` required).
- **The honesty tables** — "what each guard actually proves" and "what the vocabulary does NOT check". A
  refactor that folds these into cheerful guarantee lists would destroy the document's best property.
- **Teaching error messages.** `fire`'s budget failure explains the cycle model *and* names S3K's
  consecutive-fires technique as the fix. Error text containing the correct next move is rare.
- **The inlined-literal pin discipline**, which looks like duplication begging to be "cleaned up" into
  imports and is in fact the mitigation for a silent-degradation trap.
- **The method itself** — re-express byte-identically first, prove it, then extend. Anything built on top
  should be held to the same bar.

---

## 9. Density is the unmeasured risk

Two lenses converged on this independently. The only measured sparse figure in the tree is **8358 cyc/frame
at ~4 fires/frame** (OJZ section 1). Nothing has ever run **adjacent** fires on hardware. Yet:

- the doc actively prescribes six consecutive single-line fires as the way to swap a full palette line
- `full_line_fire_cost = 6` in `effects_budget_model.toml` is tagged `code-derived`, which by that file's own
  status key means `ceil(16/3)` — **not a measurement**
- the dense tier's measured marginal is ~342 cyc/line, and a sparse fire does *strictly more* work than a
  dense body (record walk, three-way opcode compare, `EFX_BLANK_DELAY`, plus the region op's `lea`/`adda`)
- the engine's own designers built `.dense_body` as a bypass of the record walk **precisely because the
  sparse walk was judged too heavy for every-line work** — and the doc then points authors at every-line
  sparse fires as the remedy for >3 colours

Whether six back-to-back sparse fires sustain one per line has never been run. This wants an oracle
measurement before any pack member relies on the idiom.
