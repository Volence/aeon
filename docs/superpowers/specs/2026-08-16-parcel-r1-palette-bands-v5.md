# PARCEL R1 — palette bands (mid-screen restore). Design draft v5.

**Date:** 2026-08-16
**Status:** DRAFT — for adversarial sweep. Nothing here is ruled except where an owner ruling
is cited by name.
**Supersedes:** `2026-08-16-parcel-r1-palette-bands-v4.md` (v4, stopped by sweep 4 —
`2026-08-16-parcel-r1-sweep-4-adjudication.md`), which superseded v3/v2/v1 (killed by sweeps
3/2/1).
**Scope authority:** the 2026-08-16 Fable ruling (palette-only, one band per program, static
bands), unopened by sweeps 3 and 4.
**Owner rulings in force (2026-08-16):**
- The composition guard is the **equal-span-partner rule** (§4.2), carried from v4 and
  structurally survived by sweep 4.
- The mixed-fire +16 fallback ruling ("de-mix the water fire") is **VACATED** — sweep 4 proved
  it unbuildable for the live patchable fire. Replacement ruling: **measure first; the
  fallback slot is VACANT and is re-ruled only if the measurement fails** (§3.3). De-mix
  remains valid for static fires and is used as the S/H-band OFF idiom (§6.1).

> **READ THIS FIRST.** Four drafts have been swept; sweep 4 was the first with **no
> direction-level kill** — the mechanism, the opcode, and the guard shape are now stable
> across two consecutive sweeps. This draft is a REPAIR pass: sweep 4's four kills each had a
> namable fix, and per the standing process rule those fixes enter here as **CLAIMS D-A..D-F**
> (§12), not as rulings. By induction they are the most likely things in this document to be
> wrong. One process datum worth carrying: sweep 4's minima correction (D-D) arrived
> independently from two seats — the first minted fix to arrive pre-replicated.

---

## 1. What this builds

An effect that turns ON at a scanline and OFF again at a lower one — a fog slab, a top-half
glow, a tinted band, **over up to 3 CRAM entries**. Today every raster effect runs from its
start line to the bottom of the screen, which makes bands the single largest hole in the
effects vocabulary.

The 3-entry ceiling is structural, not chosen: the restore is a stream op under the per-fire
`stream_words <= 3` ceiling, and the program carries exactly one restore (§4.1), so the
six-fire whole-line idiom is unavailable to bands. Content that needs a wider band needs the
N-band booking (§9). Stated here so §1 does not oversell what §6 refuses.

The OFF edge is the whole problem. To turn an effect off mid-screen the handler must stream
the **pre-effect base colours** back into CRAM, and those colours must match this frame's
base-DMA payload — otherwise the bottom of the band is a different palette from the rest of
the screen.

### Scope, per the ruling

- **Palette only.** No register restore, no scroll restore.
- **ONE band per program** — at most one restore op in the whole composed program.
- **Static bands only.** The restore's partner must itself be a static fire (§4.2 rule 6);
  the split-spelling moving-top band sweep 4 found admissible-by-accident is refused.
- Scroll bands are re-homed to queue item 2 (the VSRAM op-class split).

### What changed from v4, in one paragraph

The mechanism (§2) is carried with two census corrections. C-C (the poison gate) is rebuilt in
breakpoint form with honest claim scope (§10.3, now D-A). C-B keeps its mechanism (own delay
site, never share `EFX_BLANK_DELAY`) but its candidate analysis is deleted — the landing
anchors are UNGROUNDED (§3.2), the restore measurement is the *first datum* at its shape, and
the +16 prognosis is withdrawn (§3.3). The de-mix fallback is vacated for the live patchable
fire and re-homed as the static S/H-band idiom (§6.1). Two new shape guards close sweep 4's
Kill 4 (§4.2a: single-op restore fire; §4.2b: the `$8F` autoincrement refusal). The band
minima are class-keyed (D-D, §6.2). The restore's payload collapses to `(addr, count)`
(D-F, §3). Sweep 4's eleven must-fixes are folded throughout, marked `[S4-n]`.

---

## 2. The mechanism — carried, verified by sweeps 2, 3, and 4

A new engine-owned 128-byte buffer, `Palette_Ship_Snap`, holding a per-line copy of
`Palette_Buffer` taken at the moment each palette line's frame-top DMA is enqueued. The
restore op streams from it.

### 2.1 The splice point

`engine/system/buffers.emp:236-263`, quoted verbatim (line 0; lines 1-3 identical; quote
re-verified against source by sweep 4):

```
237         move.b  Palette_Dirty, d0
238         beq     .no_pal
239         btst    #0, d0
240         beq     .skip_pal0
241         queue_static_dma(Static_Pal_Line0)
242         bcs     .skip_pal0                      // dropped -> leave bit 0 set
243         bclr    #0, Palette_Dirty               // enqueued -> clear bit 0
244     .skip_pal0:
```

The snapshot for line 0 goes **adjacent to the `bclr` at :243**. Both guard branches —
not-dirty (`beq`, :240) and dropped (`bcs`, :242) — are upstream of it, so the copy happens
iff the line was dirty and its DMA entry was accepted. On a clean or dropped line the snapshot
retains the previous frame's value, which is what CRAM retains. Correct by construction.

`[S4-10]` **Register note, corrected:** v4 justified the eight-unrolled-`move.l` copy shape
with "`d0` is contractually live across all four splices". False for the line-3 splice —
`buffers.emp:278` itself says d0's dirty-snapshot is dead after the bit-3 `btst` at `:257`.
The shape survives on cost alone: 8×20 = 160 cyc unrolled beats a `dbf` loop at 244, at every
splice, register availability aside.

### 2.2 The invariant

> **`Palette_Ship_Snap[line]` equals THIS FRAME'S base-DMA payload for that line.**

Not "what CRAM received at frame top" — `VInt_DrawLevel` sits between enqueue and drain
(`vblank.emp:168-198`), so on a heavy frame the drain lands after line 0. The payload phrasing
is what the `bclr` splice pins. The invariant is exact for spans inside one palette line, which
C-D guarantees at the constructor (§6.2) — `op_mask` is start-line-only, and C-D is what keeps
that from being a hole.

### 2.3 Why the snapshot is in phase — CLAIM 1, census re-corrected

**Nothing in VBlank writes `Palette_Buffer`.** Grounded three independent ways:

1. Exhaustive writer census across `engine/` and `games/`. Every writer is main-loop:
   `Palette_Compose` base copy (`palette.emp:344-348`), `Palette_RotateSpan` (`:447-473`),
   `Palette_DoFade` (`:490-498`), `Palette_DoOperator` (`:574-578`, `:593-622`, `:631-635`),
   the `Player_RefreshPhysics` line-0 copy (`player_common.emp:517-524`, twice per session),
   level/test init copies, **and the T15 sky-marker block at
   `games/sonic4/test/ojz_scroll_test.emp:476-486`** — `[S4-Kill1a]` filed correctly at last,
   third attempt: it is **UNCONDITIONAL, once per frame**, in `GameState_OJZScroll_Update`
   (outside the `if DEBUG` block, before `Parallax_Update`), writing `Palette_Buffer` word 0
   and `ori.b #1, Palette_Dirty`; only the *value* is section-keyed. v4 filed it as
   per-section-crossing (wrong); sweep 3 filed it as an init copy (wrong). Every consumer of
   the census — most of all the D-A gate's mask (§10.3) — must use this filing.
   Zero hits in `engine/system/vblank.emp`, `engine/debug/`, `engine/sound/`.
2. `Raster_VBlank` — the only palette-touching VBlank routine — writes only `Palette_Dirty`
   (`raster.emp:573-574`).
3. The HBlank handler streams from `Pal_Variant_Stage`, not `Palette_Buffer`
   (`raster.emp:733`).

**The torn-frame argument** (carried; sweep 4 confirmed the re-grounding): within one IRQ6 the
enqueue, the splice, and the drain read the same frozen buffer — a compose torn by IRQ6 ships
and snapshots the same half-composed image. It rests on `BuildStaticDMA`
(`buffers.emp:102-131`) being the only builder of `Static_Pal_Line0..3` (census fact,
grep-verified) — NOT on any general immutability of static DMA entries, which is false
(`Render_Sprites` re-patches `Static_Sprite_DMA` lengths every frame).

*Falsifier:* any new VBlank-context writer of `Palette_Buffer`. See §8.

### 2.4 The drop path — CLAIM 2

**The palette drop arms are unreachable AT TODAY'S CALL SITES** — a census, not a structural
bound. Palette lines enqueue first (`buffers.emp:241,247,253,259`); with ≤2 pre-existing
Critical entries the four palette `bcs` arms cannot fire. Nothing pins "≤2"; a Critical
enqueuer added ahead of the palette block reopens the path. The splice stays at the `bclr`
because it is free and correct if the path ever opens — grounded on "the enqueue and the
bit-clear are the same event". A drop gate cannot be built without a synthetic 8th Critical
enqueuer; consequence for D-A's claim scope in §10.3.

---

## 3. The opcode

`OP_PAL_RESTORE`, a **distinct `RasterOp` variant**, appended to the dispatch chain — for the
carried reasons (exhaustive match names every omission; the shared `.op_region` body and its
calibrated delay stay byte-identical).

### Payload — CLAIM D-F (sweep-4-minted, unswept)

`PalRestore(int, int)` — **(CRAM byte address, count)**. Not v4's four-field form. Grounds:
`BuildStaticDMA` maps `Palette_Buffer + $00/$20/$40/$60 → CRAM $0000/$20/$40/$60`
(`buffers.emp:106-131`), so **the snapshot offset IS the CRAM byte address** — the four-field
form carried two derivable fields whose only role was to disagree with `addr` (sweep 4's
witness: a hand-authored restore streaming the wrong line's base while address-keyed C-A
passes). One fact, one field; the agreement hazard is deleted by construction rather than
guarded. Wire words: `[OPCODE, cmd>>16, cmd&$FFFF, count-1, addr]` — `op_size` 5. The fifth
word stays (deriving addr from the VDP-scrambled command longword at runtime costs cycles the
handler does not have).

### 3.1 The dispatch pin — CLAIM 3, now four literals `[S4-6]`

The chain gains a fifth rung: `RASTER_DISPATCH_RUNGS == (OP_PAL_RESTORE - OP_CRAM)/2 + 1 = 5`,
re-spelled against the new last opcode (the current pin names `OP_RUN_RAMP` and would pass
silently after an append). **And the module ensure at `raster_dsl.emp:843-844` gains a FOURTH
term**: `RASTER_DEPTH_RESTORE == (OP_PAL_RESTORE - OP_CRAM) / 2` (= 4, dispatch cost
16×4+18 = 82) — v4 left the new depth literal unpinned in exactly the place its own §3.1
argument called dangerous. The ensure's "update these three literals" message becomes four.

The +16 SetReg fall-through tax breaks two measured ensures: **F1** 396→412 and **F5**
612→628 — triple-confirmed arithmetic (two sweep-4 seats + adjudicator). Both re-measured on
the new ROM; F5 wiring is §10.2's job.

`[S4-5]` **Emission placement is load-bearing.** F1 = 396 decomposes as 302+8+4×16+12+10,
which proves every current rung assembles with byte displacements. The restore body is
therefore emitted **LAST, after `.op_run_ramp`** — inserting it beside `.op_region` pushes the
dense-op branch targets toward the ±127 byte edge, and one silent relaxation to word makes a
failed rung 20 cyc, failing both pinned equalities with a message blaming the cost model.
Before pinning 412/628, read the emitted displacements off the listing.

*Falsifiers:* re-derive `(10-2)/2+1 = 5`; F1 measures 412; the listing shows byte-sized `Bcc`
throughout the chain.

### 3.2 The restore's delay — CLAIM C-B, mechanism carried, analysis rebuilt

**Carried and confirmed:** the restore's body is the region shape with its **own delay site**
in place of `EFX_BLANK_DELAY` — an appended opcode dispatches at 82 cyc vs the region's 34,
so sharing the constant is dead (sweep 3), and the constant is the restore's own knob
(sweep 4 confirmed the relative deltas: omit ≈ −10, `moveq #0` ≈ +8, versus the region path's
post-command overhead).

**Deleted, per sweep 4's kill:** every absolute landing figure. The "~14 cyc past the edge"
calibration point and the "~97 cyc window" are **UNGROUNDED** — no measurement or grounded
derivation exists in the tree ("~123 true HBlank" is itself an unmeasured estimate), and the
only calibrated-clean landing evidence (`effects-p2/GATE-EVIDENCE.md` rows 118-120) was
captured on a **mixed `OP_CRAM` fire** — a shape ~94-110 cyc away from a bare restore fire in
op position alone, plus +36 of dispatch/setup difference. No clean landing measurement for any
single-op sparse CRAM fire exists (P1's was voided by its own CORRECTION).

**Therefore:** the §7.3 restore measurement is the **FIRST DATUM** at this fire shape, not a
confirmation. The knob starts at **no spin** — chosen to *bracket*, not to pass: from there
the escalation is monotone (`moveq #0` = +18, then +10/`dbf`), each step is one constant, and
the measurement's reading is simple (leading-edge dots ⇒ step up; clean ⇒ done). No
prediction of which step lands clean is made, and none of v4's tripwire language ("trailing
dots ⇒ re-derive") survives — trailing dots at some step just mean the previous step was the
answer. The restore fire is **single-op by construction** (§4.2a), so the measured shape is
the only shape that ships.

### 3.3 The +16 mixed-fire tax — CLAIM 4, prognosis withdrawn, fallback slot VACANT

The mechanics carry: `check_mixed_fire` forces SetRegs before CRAM ops; the one shipped mixed
fire is `OJZ_TC_PROG` channel 0 — **which is PATCHABLE**
(`patchable(fx_tint_band(... sh: 1), ch: 0, lo: 3, hi: 220, offscreen_ship: 1)`,
`ojz_effects.emp:637-639`), a fact v4 never stated and sweep 4's Kill 3 turned on. The +16 on
its SetReg displaces its CRAM burst; whether that lands outside blanking is **one mandatory
measurement** (§7.3), on which:

- **v4's "expected to be tight and may fail" is WITHDRAWN.** It rode the same +14 over-count
  and ungrounded anchor as C-B's analysis. On corrected span arithmetic the draft-anchor slack
  is ~23 cyc; on the honest reading it is not derivable at all. No tilt drives planning.
- **The de-mix fallback is UNBUILDABLE here** (owner ruling vacated 2026-08-16): splitting a
  patchable fire needs two patchable records on one channel — refused by GUARD 11
  (`raster_dsl.emp:1146-1153`) and `check_intervals`, and decisively, `ship_trailer` collects
  the frame-top replay registers from the shipped fire's own op list (`:1300-1308`), so the
  split region fire ships with zero reg words — re-opening the documented "tinted but
  UNSHADOWED" found-in-play regression (`:1294-1299`). Making the S/H half static deletes the
  effect (the seam stops tracking the water line).
- **Replacement ruling (owner, 2026-08-16): the fallback slot is VACANT.** Measure; rule a
  fallback only on failure. Candidates NAMED, not ruled, for that day: a per-fire comptime
  delay word in the wire format (structural — the encoder knows each fire's op mix; the format
  moves again); narrowing the shipped fire's stream count; accepting the artifact if the
  measurement shows it sub-pixel. TRAP carried: never retune `EFX_BLANK_DELAY` globally.

Rider `[S4-MF-F]`: the arm-word gate derives expectations from the scene sidecar
(`effects_gates.py:72-98`) — no gate hardcodes the current shape — but any future re-authoring
regenerates the sidecar and stales the P2 baseline rows as evidence.

---

## 4. Guards

### 4.1 One band per program

Ensure in `raster_program` (`raster_dsl.emp:1124`), covering `patched_program` via its call at
`:1426` (sweep-4-confirmed). Count via a new total helper `op_is_restore`, shaped like
`prog_mask`. What it buys, stated honestly: restore-vs-restore ambiguity removed, blast radius
bounded. Composition is §4.2's job.

`[S4-7]` **`ensure` is non-aborting in sigil** (Poison + continue; only `ensure_fatal`
aborts — verified at the evaluator source, `eval/guards.rs:142-144`). So on a two-restore
program §4.2 still runs: it specs the **deterministic choice of the FIRST restore** (authored
order) so the diagnostic stream is clean, and §4.1's message names the count so the root cause
leads.

### 4.2 The composition guard — CLAIM C-A, carried, with its grounding stated

The helper, the rule, and the semantics carry from v4 verbatim: `op_cram_span(o)` total over
the enum (`(-1,0)` for SetReg/Vsram — address-keyed, honouring the Vsram trap); for the single
restore, every CRAM-span op at an earlier-or-same fire line whose span intersects the
restore's is refused, unless it is the **unique strictly-earlier op with an exactly equal
span** — the partner, equal by construction from `band()`. Zero partners → refuse (a restore
with no partner is base-over-base). Two or more intersecting earlier ops → refuse. Same-line
intersection → refuse unconditionally. Later lines → unconstrained.

Sweep 4 verified: expressible in `.emp` as specified (tuple return + destructuring; §11 lists
the language constraints), merge-safe against `compose`'s two-pass emission, and the
`preset(patched:)` untyped hazard named for §4.3 applies to C-A identically — inherited,
stated, not widened.

`[S4-2]` **The grounding v4 left unstated, now load-bearing text:** the earlier/later
comparison uses authored fire lines, and patchable records MOVE at runtime. C-A is safe for
them **only because `check_intervals` forces strictly ascending disjoint band intervals**
(`:982-992`), so every reachable fire line of a patchable record stays on one side of the
restore. *Falsifier: any relaxation of `check_intervals` silently voids C-A.* This goes in the
guard's own comment, not only here.

**Rule 6, new — the static-partner requirement:** the restore's **partner** must belong to a
**static** fire. A patchable ON op paired with a static restore is the split spelling of a
*moving-top band* — sweep 4 found it admitted by accident while §9 books moving bands as
unrepresentable, and under local removal the suppressed ON record leaves the restore firing
base-over-base. Scope says static bands; the guard now says it too. One ensure, keyed on
`fire_is_patch` of the partner's carrying fire. Deliberately NOT extended to later-line
intersecting ops: a patchable effect below the band is legitimate layering, and its whole
reachable range stays below the restore for the same `check_intervals` reason the
earlier/later comparison is sound at all.

### 4.2a Single-op restore fire — CLAIM D-B (sweep-4-minted, unswept)

**The fire carrying the restore carries the restore ONLY.** One ensure; it subsumes two
sweep-4 findings at once:

- *Kill 4:* a `SetReg` on the restore's fire runs first (`check_mixed_fire` ordering) and
  costs 110 cyc before the restore's command write — outside any reading of the blanking
  window, dots guaranteed, and no delay value can compensate (the correction is negative).
- *Must-fix 3:* a second stream op on the restore's line would contend for the one measured
  HBlank slot, with the winner decided by `compose`'s `progs` argument order.

Consequence for content: an S/H band ends with the **static de-mix idiom** —
`fire(bot-1, [reg_set($8C81)])` + `fire(bot, [restore])` — which builds (two static fires),
keeps the restore fire at the measured single-op shape, and inherits the codebase's own
"schedule the mode change a line earlier" remedy. §6.1 states it as the pattern; a preset
helper is content-parcel work. Side effect: nothing else can fire ON the band's bottom line;
with the restore fire's own downstream gap (§6.2) the next effect starts ≥2 lines below.

### 4.2b The autoincrement refusal — CLAIM D-C (sweep-4-minted, unswept)

`reg_set` currently blesses `$8Fxx` (mid-frame autoincrement, "ordinary technique",
`raster_dsl.emp:124-127`). Sweep 4's witness: `reg_set($8F04)` before a band changes the
stream stride to 4 — the ON op and the restore both write every OTHER entry, the restore
leaves a tinted entry behind and paints base over an entry it does not own, and every guard
passes, because **every span/mask computation in the module assumes stride 2** (`op_cram_span`,
`op_mask`, the ship destination — all of them, not just C-A).

**Design call, flagged for the sweep: refuse `$8Fxx` in `reg_set` TREE-WIDE**, not merely in
restore-carrying programs. The blessing was already unsound — the stride-2 assumption predates
bands — no shipped content uses it (the engine's own `$8F` excursions are IPL-guarded and
unreachable by HInt, sweep-4-verified), and program-scoped refusal leaves the same hole open
for every non-band program's `op_mask`. The constructor comment records the revocation
condition: a stride-aware span model. One ensure in `reg_set`.

### 4.3 Program-keyed ship refusal — CLAIM 6, carried

Unchanged and sweep-4-confirmed writable with no in-`patched_program` bypass: refuse a program
containing a restore op AND a fire with `fire_offscreen_ship(f) == 1`. On a shipping frame
CRAM holds VARIANT colours while the snapshot holds BASE. `[S4-11]` **Stated cost, no longer
"zero":** the one section with a live raster program — Sec0, `OJZ_TwoChannel`,
`offscreen_ship: 1` — is thereby **permanently excluded from carrying a band** while it ships.
The first band-content parcel discovers this here, not in a build error.

### 4.4 Guards that need nothing

Carried: `check_density` (inherits the restore's cost via CLAIM 9), `check_mixed_fire`
(restore is stream-class), the layout checks. `check_intervals` is not an overlap guard
(fire-line space) — but it is now C-A's load-bearing grounding (§4.2), which is a stronger
reason to leave it untouched than v3's wrong one.

---

## 5. The 14 match sites

Sweep 4 grep-verified the base count: exactly 12 `RasterOp` match sites
(`raster_dsl.emp:590, 621, 635, 663, 676, 684, 693, 701, 710, 728, 847, 858`); the 7
`RasterFire` sites are untouched by a new op variant. Plus the two new total helpers
(`op_cram_span`, `op_is_restore`) = 14 sites carrying a `PalRestore` arm. Every omission is a
build error.

| site | the restore's arm (payload `(addr, count)`) |
|---|---|
| `op_words` | `[OPCODE, cmd>>16, cmd&$FFFF, count-1, addr]` |
| `op_size` | 5 — cross-checked by `raster_program:1181` |
| `op_stream_words` | `count` — feeds the `RASTER_CRAM_MAX` ceiling |
| `count_stream_pal_region_ops` | 0 — a restore is not shippable (routes to `patchable:356`) |
| `op_ship_cram_addr` | −1 |
| `op_ship_stage_off` | −1 |
| `op_reg_word` | 0 |
| `op_ship_count` | 0 |
| `op_mask` | `1 << (addr >> 5)` — exact under §6.2's single-line refusal |
| `op_is_reg` | 0 — stream class |
| `op_dispatch_cyc` | `RASTER_DEPTH_RESTORE` (§3.1) |
| `op_work_cyc` | derived 68 (region 122 − 54 spin) — **UNVERIFIED until measured** (CLAIM 9) |
| `op_cram_span` | `(addr, 2*count)` — and the existing arms per §4.2 |
| `op_is_restore` | 1 |

Plus: the opcode const in `raster.emp`, one new `cmpi/beq` rung, and the restore body emitted
**last** (§3.1).

---

## 6. Authoring surface

### 6.1 `band(...)` and the S/H idiom

`band(top, bot, on: RasterOp)` returns `[fire(top, [on]), fire(bot, [restore])]` — the
restore's `(addr, count)` derived FROM the ON op's `op_cram_span`, so partner equality holds
by construction for `pal_region` and `cram` ops alike. Ensures by name: the ON op has a CRAM
span; `top < bot` in range; minimum height per §6.2; single palette line (C-D). Disciplines
carried: inline staging arithmetic; derive addresses from `pal_line`/`entry`. Not handable to
`patchable` (multi-fire refusal, `:331-332`).

**The S/H band** is `band()` plus the static de-mix pair (§4.2a): the ON fire may carry
`[reg_set(sh_on), tint]` (a mixed fire — subject to the same landing question every mixed fire
has, §3.3), and the OFF edge is `fire(bot-1, [reg_set(sh_off)])` + the band's own restore at
`bot`. Stated as the idiom; a `fx_` preset wrapping it is Parcel D content work.

### 6.2 Constructor refusals

**Single palette line (C-D, carried):** `ensure(entry + count <= 16)` at the constructor —
arithmetically verified at both ends by sweep 4, verbatim `stream_pal_region`'s own check.
With the 3-entry ceiling (§1) it can never bind in practice; it stays as the belt that makes
`op_mask`'s start-line semantics exact by construction rather than by luck.

**Minimum band height — CLAIM D-D (sweep-4-minted, PRE-REPLICATED: two seats independently
derived the same correction).** The minima key on the ON fire's **modelled cost**
(`fire_cost_cycles`), not on word count — v4's flat "2 and 1" was wrong for the third time:

| ON fire | modelled cyc | min gap (vs 488/line) |
|---|---|---|
| `stream_cram` 1w | 458 | 1 |
| `stream_cram` 2w | **488 — exactly the line, zero modelled slack** | 1 |
| `stream_cram` 3w | 518 | 2 |
| `stream_pal_region` 1w | 506 | **2** |
| `stream_pal_region` 3w | 566 | 2 |

`fx_tint_band` — the primary band content — is `pal_region`, so **even a 1-colour tint band
needs height ≥ 2**. "Band height" = `bot − top` in screen lines = the fire-line gap (uniform
−1 conversion, ordering-identical). The constructor refusal mirrors the density model by
computing `fire_cost_cycles` of the actual ON fire — never a count-keyed table.

**The restore fire's own downstream gap `[S4-1]`:** at derived `op_work_cyc` = 68 the restore
fire models 496 (1w) to 556 (3w) — over one line at every count, so **any fire below the band
sits ≥ 2 fire-lines below the restore**. Stated here so `check_density`'s refusal is predicted
by the authoring docs. Both this row and the table above ride CLAIM 9 (unmeasured
`op_work_cyc`); they are re-spelled once `raster_cost_probe` runs on the new op, and the spec
orders that measurement BEFORE the minima are frozen into constructor ensures.

### 6.3 Budget

Carried: 64-word ceiling, 7 fixed; a band costs 14 words (7+7 — the restore fire is single-op
by D-B, so never 16), leaving 43 for the rest of the program. A 3-word band cannot share
either fire line with any other stream op (per-fire ceiling + D-B) — content-visible, stated.

---

## 7. RAM, cost, and what must be measured

### 7.1 Placement

Carried, cost stated honestly: `Palette_Ship_Snap: [u8; 128]` at the engine-RAM tail before
`mark Engine_RAM_End` and before the `@shape_divergent` DEBUG block (line refs
sweep-4-verified); `game_ram` chains after `upper_ram`, so this is a **full game-side repin**.
Routine.

### 7.2 Snapshot cost — CLAIM 8, ESTIMATE

Carried with the §2.1 register correction: eight unrolled `move.l` per line on cost grounds,
~176 cyc/line, ~704 worst case ≈ 3.8% of the NTSC blanking window (sweep-4-derived against
`constants.emp:508-509`). Bytes 32/frame steady, 128 worst.

`[S4-9]` **The instrument, named exactly:** oracle profiler **per-routine rows** —
`VInt_Level` and `Enqueue_Dirty_Buffers` — before/after on the same scene, plus one synthetic
worst-case frame (all four lines dirtied) checking end-of-window position. **Never
`interrupts.hint`**, which in this ROM is HBlank+VBlank summed (the standing trap the module's
own comment at `raster_dsl.emp:918-922` records). The DMA byte budget cannot see these cycles;
`DMA_Budget_Remaining` under-reports the window once this lands — known limitation, stated.

### 7.3 The two landing measurements — evidence, not gates

Both controller-run, pinned camera (`Debug_Scene_Freeze`), reset before capture, column-bucket
brightness at **8 px buckets**, recorded in `docs/benchmarks/`. Pixels never gate.

1. **The restore's landing — the FIRST datum at its shape** (§3.2). Single-op restore fire on
   the band's bottom row; the measured row must use entries the art actually shows (per P1's
   CORRECTION — the S/H-seam protocol does not apply to a colour write). Read: leading-edge
   dots ⇒ step the delay knob up one rung and re-measure; clean ⇒ record the constant and the
   capture as the calibration datum this fire shape has never had. Per-scanline CRAM probing
   cannot substitute (frame-latched).
2. **The mixed-fire +16** on `OJZ_TC_PROG` ch 0's row, S/H-seam method (mode register shadows
   the whole row). Expected seam drift ~15 px is harmless; colour words spilling into the
   visible row is the failure — which **vacates into the owner re-ruling of §3.3**, with the
   named candidates. No prognosis is recorded.

---

## 8. The structural finding this parcel does NOT close — CLAIM 7, carried

The engine has no single frame-top commit seam; any future frame-top writer silently
invalidates the snapshot. Mitigation: a comptime registry of frame-top committers. The
**enforcing form remains UNVERIFIED**; the advisory form (census + length-pinning ensure) is
the floor. The design pass must attempt the enforcing form; failing that, ship advisory with
the residual risk in the invariant's own comment. Not gating R1.

---

## 9. Ruled out, and booked with preconditions

- **`OP_RESTORE_REG` — dead** (three kills; a register band is two fires today).
- **Scroll bands — queue item 2** (cross-mode `vsram(2,…)` meaning).
- **N bands** — booked behind an entry-ownership representation.
- **Moving bands** — booked behind the representation question, and the **split spelling
  (patchable ON + static restore) is now explicitly REFUSED** by §4.2 rule 6 — v4 admitted it
  by accident. When moving bands are designed, rule 6 is the seam to reopen.
- **De-mix for patchable fires — recorded DEAD** (sweep 4 Kill 3: GUARD 11, `check_intervals`,
  and the fire-scoped ship replay). Valid for static fires only (§6.1).
- **EFX-4b** adjacent and untouched.

---

## 10. Gates

1. **`raster_source_gate` restore arm** — with the existing gate's discipline carried
   verbatim `[S4-5]`: its own mangled local label for the restore loop, exact stop-PC
   assertion, `deterministic=False` (the det-mode PC hazard its header documents), and its own
   offset arithmetic (`addr`, no `slot*128`). The only gate observing the handler.
2. **F1 and F5 re-measured; F5 wired** `[S4-8]` — noting the wiring is real work:
   `effects_gates.py`'s expected-cost derivation handles one op per fire; F5 is a two-op fire
   and needs the summed form (both ops' fetch+dispatch+work+tail over one
   `RASTER_FIRE_BASE_CYC`). v4's "F1 is the only fixture that exercises the fall-through" is
   corrected to "the only one among the wired F0/F1/F3" — F5 contains the same SetReg, which
   is exactly why it moves.
3. **The poison gate, breakpoint form — CLAIM D-A (sweep-4-minted, unswept), replacing C-C.**
   v4's form died three ways: the fixture mask premise was false (the T15 marker makes it
   `%0101`), the pre-enqueue mask is `bclr`-destroyed before any post-frame read, and the
   drop-arm half is untestable. The rebuilt gate:
   - breakpoint at the pre-enqueue read (`buffers.emp:237`), capturing the **actual**
     pre-enqueue mask from `d0` — no authored-mask assumption survives into the gate;
   - poison chosen **outside the CRAM value space** (a word with bits set outside the `$0EEE`
     format mask, e.g. the `$Fxxx` family), stated in the gate and asserted absent from the
     fixture palette at gate start;
   - run to end-of-frame; per-line assert: lines IN the captured mask equal the payload span
     (`Palette_Buffer + line*32`), lines OUTSIDE it retain poison;
   - **claim scope, honest:** this tests dirty-gating and copy extent. The `bcs` drop arm is
     untestable without the synthetic enqueuer §2.4 rules out; that half rests on code review
     plus the "enqueue and bit-clear are the same event" grounding, and the gate's own comment
     says so.
   Breakpoints are already the `effects_gates.py` idiom (the F-series), so this rides the
   existing runner.
4. **Negative programs need an expect-fail lane `[S4-7]`.** `ensure` is non-aborting and no
   expect-fail harness exists — a poison program in a normal target fails the whole build.
   The lane: a separate sigil invocation over a tiny poison module, asserted to exit nonzero
   AND to emit the expected guard message, wired into the tool suite beside the existing
   tool tests. Poisons: a two-restore program (§4.1), a band+overlapping-tint (§4.2), a
   patchable-partner band (§4.2 rule 6), a `SetReg`-on-restore fire (D-B), a `reg_set($8F04)`
   (D-C). Cheap, and the first negative-build coverage in the tree.
5. **Comptime hand-twin** of a band program: `first_mismatch` PLUS the separate `.len` ensure.

---

## 11. `.emp` / sigil facts this design rests on

Carried: no multi-line ensure conditions; comptime free names resolve at the call site;
`{...}` interpolates in messages; unreferenced `const` is inert; `data` enforces length;
accumulate with `m = m | bit`. **New, sweep-4-verified at the evaluator source:** tuple
returns work via destructuring ONLY (`let (a,b) = f()` — no indexing, no `.0`); no
`break`/`continue` (use `return` or a done-flag); no comparison chaining (`a <= x < b`
mis-parses); **`ensure` is non-aborting** (Poison + continue; `ensure_fatal` aborts) — guards
must tolerate poisoned neighbours and pick deterministic representatives (§4.1).

---

## 12. The claims, collected, for the sweep

| # | claim | confidence | falsifier |
|---|---|---|---|
| 1 | No VBlank writer of `Palette_Buffer`; census now includes the per-frame T15 marker | high, 3 ways, census corrected twice | a new VBlank-context writer |
| 2 | Palette drop arms unreachable at today's call sites (enqueue order) | high; census not structure | a Critical enqueuer ahead of the palette block |
| 3 | Pin re-spelled + FOURTH depth literal; F1/F5 → 412/628; body emitted last, byte-branches confirmed on listing | high, triple-derived | F1 ≠ 412; a word-relaxed rung |
| 4 | +16 is one measurement; prognosis withdrawn; fallback slot VACANT (owner 2026-08-16) | — | the §7.3 measurement |
| 6 | Ship refusal writable, complete over `patched_program` output; excludes Sec0 while it ships | high (sweep-4-confirmed) | a second publish site; a foreign `preset(patched:)` template |
| 7 | Committer registry's enforcing form | **UNVERIFIED** | attempt in design pass |
| 8 | Snapshot ~176/~704 cyc ≈ 3.8% of blanking; instrument = per-routine rows | ESTIMATE | §7.2 measurement |
| 9 | `op_work_cyc` restore = 68 derived | **UNVERIFIED — measure BEFORE freezing §6.2 minima** | `raster_cost_probe` on the new op |
| C-A | Equal-span-partner guard + `check_intervals` grounding + static-partner rule 6 | survived sweep 4 structurally; rule 6 is new | a passing program that buries a live effect; a `check_intervals` relaxation |
| C-B | Own delay knob; no-spin start as a BRACKET; measurement is the first datum | mechanism confirmed; no landing prediction made | the §7.3 measurement |
| C-D | Single-line refusal exact at both ends | sweep-4-confirmed (unreachable belt) | — |
| D-A | Breakpoint-form poison gate, honest claim scope | **UNSWEPT, minted by sweep 4** | a broken build it passes within its claimed scope |
| D-B | Single-op restore fire subsumes Kill 4 + the slot contention | **UNSWEPT** | content needing a multi-op restore fire |
| D-C | Tree-wide `$8Fxx` refusal (stride-2 assumption is module-wide) | **UNSWEPT, design call flagged** | content needing mid-frame autoinc before a stride-aware model |
| D-D | Class-keyed minima (pal_region 1w ⇒ 2) | **UNSWEPT but pre-replicated by two seats**; rides CLAIM 9 | a third derivation disagreeing; the CLAIM 9 measurement |
| D-E | (subsumed into D-B) | — | — |
| D-F | `PalRestore(addr, count)` — offset IS the address | **UNSWEPT**; grounded on `BuildStaticDMA` | a mapping change breaking the identity |
| — | v3's CLAIM 5; v4's C-C form; v4's C-B candidate analysis; de-mix-for-patchable | **KILLED — recorded so none is re-adopted** | — |

Also ordered by this draft, small: fix the cost-table comment's 4-cyc attribution error
(`adda.w` is 12, not 8 — `raster_dsl.emp:822-823`) and the stale "526 against a 489-cycle
line" comment at `ojz_effects.emp:617-618`, both while the files are open.
