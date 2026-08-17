# PARCEL R1 — palette bands (mid-screen restore). Design draft v4.

**Date:** 2026-08-16
**Status:** DRAFT — for adversarial sweep. Nothing here is ruled except where an owner ruling is
cited by name.
**Supersedes:** `2026-08-16-parcel-r1-palette-bands-design.md` (v3, killed by sweep 3), which
superseded v2 (killed by sweep 2) and v1 (killed by sweep 1).
**Scope authority:** the 2026-08-16 Fable ruling (palette-only, one band per program, static
bands), which the owner pre-committed to and sweep 3 did not reopen.
**Owner rulings taken this draft (2026-08-16):** the composition guard is the
**equal-span-partner rule** (§4.2), and the mixed-fire +16 fallback is **de-mix the water fire**
(§7.4). Both are scope/direction rulings; their *correctness* is still swept.

> **READ THIS FIRST.** Three drafts died here. The standing process finding: **an adjudication
> MINTS fixes, and minted fixes entering the next draft unswept is what killed v2 and v3.**
> Sweep 3 minted four fixes — the composition guard, the restore's own delay, the Gate 3
> replacement, the dirty-mask masking. They enter this draft as **CLAIMS C-A..C-D** (§12), not as
> rulings, and by induction they are the most likely things in this document to be wrong.
> Positive claims need more redundancy than kills: where a claim is grounded N independent ways,
> N is stated.

---

## 1. What this builds

An effect that turns ON at a scanline and OFF again at a lower one — a fog slab, a top-half glow,
a tinted band. Today every raster effect runs from its start line to the bottom of the screen,
which makes bands the single largest hole in the effects vocabulary.

The OFF edge is the whole problem. To turn an effect off mid-screen the handler must stream the
**pre-effect base colours** back into CRAM, and those colours must match this frame's base-DMA
payload — otherwise the bottom of the band is a different palette from the rest of the screen.

### Scope, per the ruling

- **Palette only.** No register restore, no scroll restore.
- **ONE band per program** — at most one restore op in the whole composed program.
- **Static bands only.** A *moving* band stays booked (§9).
- Scroll bands are **re-homed to queue item 2** (the VSRAM op-class split), not deferred vaguely.

### What changed from v3, in one paragraph

The mechanism (§2) is carried unchanged — it is verified by three independent seats across three
sweeps. What changed: the one-band ensure is **no longer claimed to collapse composition** (sweep
3 killed CLAIM 5 — it bounds blast radius N×N → 1×N and removes restore-vs-restore ambiguity,
nothing more); a real composition guard is added (§4.2, C-A); the restore gets its **own** delay
constant and landing measurement instead of sharing `EFX_BLANK_DELAY` (§3.2, C-B); Gate 3 is
replaced by a poison gate (§10.3, C-C); the restore's span is constructor-refused across a
palette-line boundary (§6.2, C-D); and sweep 3's ten must-fixes are incorporated throughout,
marked `[MF-n]`.

---

## 2. The mechanism — carried from v3, verified by sweeps 2 and 3

A new engine-owned 128-byte buffer, `Palette_Ship_Snap`, holding a per-line copy of
`Palette_Buffer` taken at the moment each palette line's frame-top DMA is enqueued. The restore
op streams from it.

### 2.1 The splice point

`engine/system/buffers.emp:236-262`, quoted verbatim (line 0; lines 1-3 identical):

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

The snapshot for line 0 goes **adjacent to the `bclr` at :243**. Both guard branches — not-dirty
(`beq`, :240) and dropped (`bcs`, :242) — are upstream of it, so the copy happens **iff the line
was dirty and its DMA entry was accepted**. On a clean or dropped line the snapshot is not
written and retains the previous frame's value, which is exactly what CRAM retains, since no DMA
was queued for that line. Correct **by construction**, not by argument.

### 2.2 The invariant

> **`Palette_Ship_Snap[line]` equals THIS FRAME'S base-DMA payload for that line.**

Deliberately *not* "byte-identical to what CRAM received at frame top". `VInt_DrawLevel` sits
between the enqueue and the drain (`vblank.emp:168-198`), so on a heavy frame the drain lands
after line 0 and the frame-top phrasing is false. The payload phrasing is what the `bclr` splice
actually pins.

`[MF-9 → C-D]` The invariant is **exact only for spans inside one palette line**: `op_mask` is
`1 << (a >> 5)` — the START line only — so a span crossing a 32-byte boundary would leave its
second line's dirty bit unraised. §6.2 refuses that span at the constructor, which makes the
start-line semantics exact rather than vacuous.

### 2.3 Why the snapshot is in phase — CLAIM 1

**Nothing in VBlank writes `Palette_Buffer`.** Grounded three independent ways:

1. Exhaustive writer census across `engine/` and `games/`. Every writer is main-loop:
   `Palette_Compose` base copy (`palette.emp:344-348`), `Palette_RotateSpan` (`:447-473`),
   `Palette_DoFade` (`:490-498`), `Palette_DoOperator` (`:574-578`, `:593-622`, `:631-635`), the
   `Player_RefreshPhysics` line-0 copy (`player_common.emp:517-524`), level/test init copies,
   **and `[MF-7]` the per-section-crossing update body at `games/sonic4/test/ojz_scroll_test.emp:485`
   (+ dirty at `:486`) — a LIVE RUNTIME WRITER, main-loop, mis-filed by v3 as an init copy.**
   Zero hits in `engine/system/vblank.emp`, `engine/debug/`, `engine/sound/`.
2. `Raster_VBlank` — the only palette-touching VBlank routine — writes only `Palette_Dirty`
   (`raster.emp:573-574`).
3. The HBlank handler streams from `Pal_Variant_Stage`, not `Palette_Buffer` (`raster.emp:733`).

**The torn-frame argument, re-grounded `[MF-10]`.** A `Palette_Compose` torn mid-write by IRQ6
ships a half-composed buffer **and snapshots that same half-composed buffer**, because within one
IRQ6 the enqueue, the splice, and the drain all read the same frozen buffer — there is no writer
between them (grounded on the census above plus `VInt_Lag` running the same enqueue→drain
sequence, `vblank.emp:291-337`). v3 additionally leaned on "the static DMA entries are immutable",
and that generalisation is **false** — `Render_Sprites` re-patches `Static_Sprite_DMA`'s length
words from the main loop every frame (`buffers.emp:136-137`, `sprites.emp:481`). The argument
here does not need it: it needs only that nothing re-patches `Static_Pal_Line0..3`, which is a
census fact (`Build_DMA_Entry` has exactly two callers, sweep 3 confirmed), stated as such, not
as a structural property.

*Falsifier:* any new VBlank-context writer of `Palette_Buffer`. See §8.

### 2.4 The drop path — CLAIM 2, restated `[MF-8]`

**The palette drop arms are unreachable AT TODAY'S CALL SITES** — a census, not a structural
bound. Level init can leave 2 entries queued when a VBlank lands (`ojz_scroll_test.emp:135`,
`:145`, no drain between), and 2+7 can exceed `DMA_CRITICAL_SLOTS = 8` — but the palette lines
enqueue **first** (`buffers.emp:241, 247, 253, 259`), so with ≤2 pre-existing entries the four
palette `bcs` arms cannot fire; only the sprite and HScroll drops can, and only at init. Nothing
pins "≤2 pre-existing entries"; a Critical enqueuer added ahead of the palette block reopens the
path. The splice stays at the `bclr` because it is free and correct if the path ever opens —
grounded on "the enqueue and the bit-clear are the same event", not on reachability.

Consequence carried from v3: the comment at `buffers.emp:232-235` ("reachable during a fade") is
stale, and a drop gate cannot be built without a synthetic 8th Critical enqueuer.

---

## 3. The opcode

`OP_PAL_RESTORE`, a **distinct `RasterOp` variant**, appended to the dispatch chain
(`raster.emp:694-701`). Distinct rather than a source-select flag for the v3 reasons (sigil names
a missing match arm on all 12 sites; flag arity at arm patterns is UNVERIFIED), and for the sweep
1 criterion that ratified it: the shared `.op_region` body stays byte-identical, keeping the
oracle-calibrated `EFX_BLANK_DELAY` path untouched for every existing `pal_region` user.

New enum arm: `PalRestore(int, int, int, int)` — (CRAM byte address, pal line, entry, count),
one term simpler than `PalRegion` (no variant slot). Wire words:
`[OPCODE, cmd>>16, cmd&$FFFF, count-1, snapshot offset]` where the offset is
`line*32 + entry*2` — **no `slot*128` term** `[MF-6]`; the naive reuse of the source gate's
`offset_of()` (`raster_source_gate.py:83`) would predict wrong.

### 3.1 The dispatch pin re-spelled — CLAIM 3, load-bearing, carried from v3

The pin at `raster_dsl.emp:843-844` names **`OP_RUN_RAMP` by name** as the chain's last rung, so
appending `OP_PAL_RESTORE = 10` leaves the pin passing while the real chain is five rungs long —
silently under-charging every `set_reg` by 16 cycles with a green build. **R1 re-spells the
ensure against `OP_PAL_RESTORE`** as the new last opcode:
`RASTER_DISPATCH_RUNGS == (OP_PAL_RESTORE - OP_CRAM) / 2 + 1` = **5**.

The +16 breaks two measured equality ensures: **F1** 396→412 (`raster_dsl.emp:925-926`) and
**F5** 612→628 (`:933-934`). Both are re-measured on the new ROM. `[MF-5]` **F5 must be wired**:
`effects_gates.py:196` currently runs `--only F0,F1,F3`, so F5's constant would otherwise be
hand-updated with nothing checking it. F1 is the only fixture that exercises the fall-through op
and therefore the only one that can see the tax.

*Falsifier:* re-derive `(10-2)/2 + 1 = 5`; F1 measures 412 on the new ROM.

### 3.2 The restore's own body and delay — CLAIM C-B (sweep-3-minted, unswept)

The restore does NOT share `EFX_BLANK_DELAY`. The delay is calibrated for the region path's
dispatch depth (34 cyc before its command write); the appended restore dispatches at 82 cyc
(+48), so sharing the constant lands its last colour word ~136 cyc past the display edge against
a ~97 cyc window — CRAM dots on every band's restore line (sweep 3's second kill).

The restore body is `OP_PAL_REGION`'s shape — command `move.l`, delay site, count,
`lea Palette_Ship_Snap, a2`, `adda.w` offset, word loop, `lea VDP_CTRL, a2` restore — with its
own delay knob in place of the shared constant: initially **no spin instructions at all**, with
`EFX_RESTORE_DELAY` introduced at the first nonzero calibration. Derived candidates, priced
off the pinned cost table (`raster_dsl.emp:820`: moveq 4, N=4 spin 54):

- **Omit the spin entirely**: first colour word ~10 cyc *earlier* than the region path's
  calibrated landing (dispatch +48, spin −58). Risk is the leading edge — the calibrated landing
  is ~14 cyc past the display edge, so ~10 early leaves ~4 cyc of margin before a dot appears on
  the restore line's right edge.
- **`moveq #0` + fall-through dbf** (18 cyc): ~8 cyc late — a 3-word burst's last word lands at
  ~96 of the ~97 window, at the edge.

**Start with omit; the landing measurement decides (§7.3), and `moveq #0` is the named next rung
if leading-edge dots appear.** Neither is decidable from constants — the ~14/~97 figures carry
the "~40 cyc" and "~10/dbf" approximations' error bars. The constant is the restore's own knob;
retuning it cannot affect any other op.

*Falsifier:* the §7.3 measurement itself.

### 3.3 The +16 mixed-fire tax — CLAIM 4, now with a ruled fallback

Unchanged mechanics from v3: `check_mixed_fire` forces SetRegs before CRAM ops
(`raster_dsl.emp:1099`), the one shipped mixed fire is OJZ's water (`sh_on() + pal_region`), and
the +16 on the fall-through SetReg pushes the region's CRAM command write 16 cycles later.
Sweep 3's re-derivation puts the baseline slack at ≤ ~9 cyc, so this measurement is now
**expected to be tight and may fail**. It remains one mandatory measurement (§7.3), and:

**TRAP, ruled: if it fails, do NOT retune `EFX_BLANK_DELAY`** — the tax is per-op-mix, the delay
is global; retuning fixes mixed fires by breaking unmixed ones.

**The ruled fallback (owner, 2026-08-16): de-mix the water fire.** Split
`fire(N, [sh_on(), pal_region(...)])` into `fire(N-1, [sh_on()])` + `fire(N, [pal_region(...)])`.
Content-side authoring change: zero handler bytes, zero format change, no recalibration, and it
removes the tax's only shipped victim. The S/H seam turns on one line earlier — acceptable
against a residual that is already a deliberately-unfixed ~45% mid-line seam
(`raster.emp:207-217`), and the codebase's own remedy for it ("authors wanting a pixel-clean mode
change must schedule it a line earlier"). Future mixed fires inherit a **documented constraint**
(the fire's CRAM landing carries the dispatch tax; measure or de-mix), not a broken one.
Check: the de-mixed `sh_on()` fire needs a fire-line gap of 1 below it, which `check_density`
admits (a reg-only fire is far under the 488-cyc line).

---

## 4. Guards

### 4.1 One band per program — reframed after sweep 3

The ensure goes in **`raster_program` (`raster_dsl.emp:1124`)**, covering `patched_program` via
its call at `:1426`. Count via a new total helper `op_is_restore`, shaped like `prog_mask`.

**What this ensure buys — stated honestly, per sweep 3's kill of CLAIM 5:** it removes
restore-vs-restore ambiguity and bounds the blast radius of a bad restore to one per program. It
does **not** collapse the pairing predicate (that is §4.2's job), the restore-vs-writer overlap
(also §4.2), or the merged-fire ordering problem (§4.2 refuses same-line overlap). v3 claimed
otherwise and died for it.

`[MF-1]` v3's "`check_intervals` is already what forbids two overlapping bands" is **deleted** —
verified false at `raster_dsl.emp:982-992`: it works in fire-line space and forbids only two
records on the *same* fire line. Overlap in entry space is §4.2's job and nothing else's.

### 4.2 The composition guard — CLAIM C-A (sweep-3-minted, owner-ruled shape, unswept)

**The problem it closes (sweep 3's central kill):**
`compose([band(100,140,E), fx_tint_band(120, same E)])` passes every existing guard and the
restore at 140 kills the tint from 140 to the bottom of the screen. No existing guard reads which
CRAM entries an op owns.

**The semantic rule.** A restore writes *base* — a destructive reset (sweep 1's categorical
objection). It therefore destroys the work of **every** earlier overlapping CRAM writer below the
band, except exactly one: its own partner, the band's ON op, whose effect is *supposed* to end
there. So: **the only writer a restore may bury is its own partner, and it must bury all of it.**

**The helper.** `op_cram_span(o) -> (addr, bytes)`, a total comptime fn in the ship-helper family
(`op_ship_cram_addr:675-682` is the template):

```
SetReg(w)                       => (-1, 0)
Cram(a, cols)                   => (a, 2 * cols.len)
PalRegion(a, slot, pl, e, cnt)  => (a, 2 * cnt)
Vsram(a, vals)                  => (-1, 0)     // VSRAM address, not a CRAM span — see trap
PalRestore(a, pl, e, cnt)       => (a, 2 * cnt)
```

**TRAP, carried and honoured:** the guard keys on the **CRAM address span**, never on op class.
"CRAM-class" in the dispatcher includes `Vsram` (`op_dispatch_cyc:852-853`), but a VSRAM address
is not a palette address — `op_cram_span` returns no span for it, exactly as `op_mask` returns 0
(`:714-719`). A class-keyed guard would false-positive on `OJZ_TC_PROG`
(`fx_tint_band` + `fx_vscroll_split`, `ojz_effects.emp:637-642`).

**The guard**, in `raster_program`, over the composed fire list (ops are fully matchable there;
fires carry screen lines):

1. Find the restore (§4.1 guarantees at most one). No restore → guard passes vacuously.
2. Let `RS` = its span, `RL` = its fire line.
3. **Partner:** among ops with a CRAM span at fire lines **strictly earlier** than `RL`, exactly
   ONE may intersect `RS`, and its span must **equal** `RS` exactly. Zero partners → refuse (a
   restore with no partner restores base over base — authoring nonsense, refused by name). Two or
   more intersecting earlier ops → refuse (the second is a writer the restore would bury).
4. **Same line:** any op with a CRAM span intersecting `RS` on the restore's own fire line →
   refuse unconditionally. `compose` merges same-line fires into one record and emits stream ops
   in `progs` argument order (`raster_dsl.emp:434-452`), so the winner would be decided by
   argument order — sweep 1's "worse half".
5. Ops at fire lines later than `RL` are unconstrained — an effect turning on below the band is
   legitimate layering.

**Known edges, stated for the sweep:**

- Over-refusal: an ON op that legitimately wants a *different* span than its restore is refused;
  the remedy is to match the spans (restoring untouched entries is base-over-base). The refusal
  message says so.
- The partner is **recognised** (unique equal span, strictly earlier), not declared. A
  representation-level pairing (a `Band` fire variant) was considered and rejected this draft:
  `compose` rebuilds fires from per-line op buckets (`:406-466`), so fire identity does not
  survive composition — a fire-level marker dies at the merge, a two-line fire breaks compose's
  model and pre-answers the open moving-band representation question, and an op-payload
  `partner_line` field degenerates into this same span check plus a redundant field.
- A band cannot overlap a **dense** run by construction — dense ops are not `RasterOp` variants
  and `raster_gradient_program` takes no op list (sweep 3 confirmed; stated here so it is in the
  draft, not only in the adjudication).
- Restore-vs-**ship** overlap is not this guard's job — §4.3 refuses the combination outright.

**Nobody has yet proven this guard sufficient — sweep 3's exact words: it "must be swept". It is
the largest single claim in this draft.**

*Falsifiers:* a composed program that passes the guard and still buries a live effect; a
legitimate program the guard refuses that content actually needs (beyond the stated over-refusal).

### 4.3 Program-keyed ship refusal — CLAIM 6, carried from v3, sweep-3-confirmed closed

Unchanged from v3, which sweep 3 confirmed: refuse a program that contains a restore op AND a
fire with `fire_offscreen_ship(f) == 1`, in `raster_program`. On a shipping frame CRAM holds
VARIANT colours while the snapshot holds BASE — a band restoring at its bottom edge would paint
the dry palette over a submerged screen. Program-keyed because a static band carries no channel
(`fire_channel` = −1 for `RasterFire.Fire`); channel-keyed is unwritable. The cross-program hole
is genuinely closed (sweep 3): `Effects_Offscreen_Entry` is cleared on both `Raster_VBlank`
install branches, and BUG A's clear-first/publish-last fix means a ship pointer cannot outlive
its program into a band frame. "Complete" stays qualified to *programs actually built by
`patched_program`* — `preset(patched:)` is untyped, a pre-existing hazard R1 does not inherit
silently. Content cost today: zero (one shipped fire declares `offscreen_ship: 1`, no shipped
program has a restore).

### 4.4 Guards that need nothing

- `check_density` (`:1014-1036`) — op-agnostic, inherits the restore's cost through
  `op_cost_cycles`; silently right only if `op_work_cyc` is right, which §7.2 measures (CLAIM 9).
- `check_mixed_fire` (`:1082-1102`) — keys on `op_is_reg`; the restore returns 0, handled.
- `check_arm_layout` (`:1347`), `check_rec_layout` (`:1375`) — layout only, via `op_size`.
- `check_intervals` — op-agnostic and **not** an overlap guard (§4.1).

---

## 5. The 13 match sites

All in `engine/effects/raster_dsl.emp`; zero `RasterOp`/`RasterFire` references outside it
(sweep-3-confirmed by grep). Every omission is a build error.

| site | line | the restore's arm |
|---|---|---|
| `op_words` | 589 | `[OPCODE, cmd>>16, cmd&$FFFF, n-1, line*32 + entry*2]` |
| `op_size` | 620 | 5 — cross-checked by `raster_program:1181` |
| `op_stream_words` | 634 | `n` — feeds the `RASTER_CRAM_MAX` ceiling |
| `count_stream_pal_region_ops` | 660 | 0 — a restore is not shippable |
| `op_ship_cram_addr` | 675 | −1 |
| `op_ship_stage_off` | 683 | −1 |
| `op_reg_word` | 692 | 0 |
| `op_ship_count` | 700 | 0 |
| `op_mask` | 709 | `1 << (a >> 5)` — exact under §6.2's single-line refusal |
| `op_is_reg` | 727 | 0 — stream class |
| `op_dispatch_cyc` | 846 | depth 4 = 82 cyc (§3.1) |
| `op_work_cyc` | 857 | body cost with `EFX_RESTORE_DELAY` — **UNVERIFIED until measured** (CLAIM 9) |
| `op_cram_span` | new | `(a, 2*cnt)` — §4.2, and the existing arms per the table there |

Plus: the opcode const in `raster.emp` beside `:94-173`, one new `cmpi/beq` rung at `:694-701`,
the restore body beside `.op_region`, and the new `op_is_restore` helper (§4.1).

---

## 6. Authoring surface

### 6.1 `band(...)` — the first two-fire helper

`band(top, bot, on: RasterOp)` returns `[fire(top, [on]), fire(bot, [restore])]` — the first
helper emitting two fires from one call. **The restore's span is derived FROM the ON op's
`op_cram_span`**, so partner equality (§4.2 step 3) holds by construction for any CRAM-span op —
`pal_region` (variant tint) or `cram` (literal colours) alike. Ensures, by name:

- the ON op has a CRAM span (a reg-only or VSRAM "band" is refused — registers are already
  expressible as two fires, §9);
- `top < bot`, both in the authored-line range;
- minimum height (§6.2 note), spelled against the **fire-line gap**;
- the span stays inside one palette line (§6.2).

It follows `fx_tint_band`'s two disciplines: inline staging arithmetic (comptime free names
resolve at the call site — `raster_dsl.emp:503-515` records that bug shipping broken for two
parcels) and derive the CRAM address from `pal_line`/`entry` so address/line agreement cannot
fail. It **cannot** be handed to `patchable` (hard-refuses multi-fire, `:331-332`).

### 6.2 Constructor refusals — including CLAIM C-D (sweep-3-minted, unswept)

**Single palette line `[C-D]`:** `ensure(entry + count <= 16)` — the restore's span must not
cross a 32-byte palette-line boundary. This is what makes `op_mask`'s start-line-only semantics
exact (§2.2) rather than "not fatal but vacuous". Cost to content: zero — every shipped effect
targets entries within one line.

**Minimum band height `[MF-2]`, re-derived (sweep 2's copied numbers were wrong):**
`check_density`'s gap is the **fire-line difference**. A 3-word stream is 518 cyc (stream_cram)
/ 566 (region), both ≤ 2×488 ⇒ gap ≥ **2**; a 1-word stream is 458 ≤ 488 ⇒ gap ≥ **1**. So the
minima are **2 and 1**, not 3 and 2. "Band height" is DEFINED as `bot - top` in screen lines,
which equals the fire-line gap (the encoder converts both lines identically). The constructor
refusal is spelled against that gap, by count, mirroring the density model — otherwise it refuses
programs the model admits. The restore's own per-count cost enters via `op_work_cyc` (CLAIM 9),
so these minima are re-checked once that arm is measured.

### 6.3 Budget

`RASTER_BUF_SIZE = 128` ⇒ 64-word ceiling; fixed overhead 7 words. A band costs **14 words**
(ON fire 7 + restore fire 7), 16 with a `SetReg` on the ON fire. With one band per program the
old "4 bands" figure is moot; what matters is the remainder: **43 words** (64−7−14) for the rest
of the composed program — comfortably more than any shipped program uses.

---

## 7. RAM, cost, and what must be measured

### 7.1 Placement — with the cost stated honestly `[MF-3]`

`Palette_Ship_Snap: [u8; 128]` at the engine-RAM tail, before `mark Engine_RAM_End`
(`engine/ram.emp:972-974`) and before the `@shape_divergent` DEBUG block (`:965-970`) so both
shapes keep equal offsets. The file's "ripples ZERO existing addresses" idiom is true of
**engine** RAM only: `pub region game_ram @ after(upper_ram)` (`games/sonic4/config/ram.emp:72`),
so 128 B at the engine tail moves **every game-side RAM address — a full game-side repin**.
Routine (the POOL_TILE_CEILING change moved 126 pins), but it is the real cost and v3 understated
it. The alternatives still cost more (mid-file placement ripples engine addresses too;
`Palette_State` trips its span guard).

### 7.2 Snapshot cost — CLAIM 8, ESTIMATE, unmeasured

Unchanged from v3: eight unrolled `move.l (a1)+,(a2)+` per line (no free data register for `dbf`
— `d0` is contractually live across all four splices, `buffers.emp:37-38`; `movem.l` would widen
both VBlank clobber unions for ~7%). ~176 cyc/line ⇒ ~176 steady state (OJZ ships
`pal_dirty_mask %0100`, one line), ~704 worst case (4 lines). Bytes: 32/frame steady, 128 worst.

**The instrument `[MF-4]`:** the snapshot adds zero DMA bytes, and the DMA budget is
byte-denominated (`vblank.emp:136`, `:168-190`) — so v3's "does Deferrable start dropping"
check goes green **vacuously**. The real failure mode is silent overrun of the blanking window.
Measure: oracle profiler VBlank row before/after on the same scene (steady state), plus one
synthetic worst-case frame (all four lines dirtied) checking end-of-VBlank position against the
window — not queue behaviour. Also read sigil's actually-emitted sequence from the listing.
Stated as before: `DMA_Budget_Remaining` will under-report the window once this lands — a known
limitation, not a defect to rediscover.

### 7.3 The two landing measurements — evidence, not gates

Both are controller-run, pinned-camera (`Debug_Scene_Freeze`), reset before capture,
column-bucket brightness at **8 px buckets** (a 16-cycle shift is ~15 px — unresolvable at the
recorded 32 px granularity), recorded in `docs/benchmarks/`. Landing position is a pixel
property and pixels never gate (oracle pixel capture is nondeterministic by construction).

1. **The restore's own landing** (C-B): capture the band's bottom edge row. Failure = CRAM dots
   on the restore line (leading-edge dots ⇒ step the knob to `moveq #0`; trailing-edge dots at
   the no-spin setting cannot be fixed by any delay value — they would mean the dispatch
   derivation itself is wrong: stop and re-derive §3.2, do not tune). The S/H-seam protocol
   (`docs/benchmarks/effects-p2/GATE-EVIDENCE.md:171-178`) does not apply here — the restore is a
   colour write, so the measured row must use entries the art actually shows at that row; pick
   the capture column against the pinned camera accordingly, per P1's CORRECTION
   (`docs/benchmarks/effects-p1/GATE-EVIDENCE.md:124-159`). Per-scanline CRAM probing cannot
   substitute (oracle CRAM reads are frame-latched).
2. **The mixed-fire +16** (CLAIM 4): the water fire's row, S/H-seam method (mode register
   shadows the whole row, art-independent). Two quantities: the seam moving right ~15 px is
   expected and harmless; the `pal_region` colour words spilling into the visible row is the
   failure — and triggers the ruled fallback (§3.3): **de-mix the water fire**, never a global
   retune.

---

## 8. The structural finding this parcel does NOT close — CLAIM 7, carried

Unchanged from v3. The engine has no single frame-top commit seam; any future frame-top writer
silently invalidates the snapshot. Mitigation: a comptime registry of frame-top committers.
**The enforcing form remains UNVERIFIED** (no grounded build-time mechanism detects an
unregistered CRAM-reaching writer); the advisory form (census + an `ensure` pinning its length)
is the floor. R1's design pass must attempt the enforcing form; failing that, ship advisory and
state the residual risk in the invariant's own comment. Deliberately not gating R1.

---

## 9. Ruled out, and booked with preconditions

Unchanged from v3, summarised:

- **`OP_RESTORE_REG` — dead** (three kills; a register band is two fires today).
- **Scroll bands — re-homed to queue item 2** (whole-plane vs per-column changes `vsram(2,…)`'s
  meaning; the band is wrong before any restore exists).
- **N bands** — booked behind an entry-ownership representation. §4.2's guard is single-restore
  by construction; relaxing §4.1 without that representation re-opens sweep 1's objection.
- **Moving bands** — booked behind the band-representation question (`patchable` refuses both
  current spellings). Explicitly NOT pre-answered by this draft's guard design (§4.2, edge 2).
- **EFX-4b** adjacent and untouched (static programs unpadded; copy reads 128 B; harmless).

---

## 10. Gates

1. **`raster_source_gate` extended to the restore op** — breaks at the restore's loop, reads the
   computed source pointer against `Palette_Ship_Snap + line*32 + entry*2` (its own offset
   arithmetic, `[MF-6]`). The only gate observing the handler rather than the program's words.
2. **F1 and F5 re-measured; F5 wired into the runner** (§3.1, `[MF-5]`).
3. **The poison gate — CLAIM C-C (sweep-3-minted, unswept), replacing v3's tautological Gate 3.**
   v3 compared the snapshot to the four static DMA source spans, which ARE `Palette_Buffer` — a
   copy compared to its source: any copy loop anywhere passes, and on a dropped line it
   red-flags correct code. Replacement, causally grounded by poisoning the subject:
   - pause; write a poison pattern over all 128 B of `Palette_Ship_Snap` from oracle; run
     exactly one frame; read back.
   - **Program-mask lines** (dirty every frame by construction — `Raster_VBlank` re-asserts
     `prog_mask` into `Palette_Dirty`, `raster.emp:573-574`) must now equal the payload span
     (`Palette_Buffer + line*32`, read at the same paused instant): a missing/mis-spliced copy
     leaves poison. Equality is meaningful because the poison broke it first.
   - **Non-dirty lines must RETAIN the poison**: an unconditional 128-byte copy — the exact
     broken build the old gate passed — fails here.
   - The mask is the **pre-enqueue** `Palette_Dirty` value; for the fixture scene it is the
     program's `pal_dirty_mask` (OJZ: line 2, `%0100`), known at authoring time.
   - Validity condition, stated: the fixture scene must not recompose the palette between the
     VBlank and the paused read (steady-state OJZ qualifies — no fade/cycle active). RAM reads
     only ⇒ rides `effects_gates.py`.
4. **A two-restore poison program** must fail the §4.1 ensure, and a
   **band+overlapping-tint poison** must fail the §4.2 guard — each poison needs an `ensure`
   that reads it (an unreferenced `const` is inert).
5. **Comptime hand-twin** of a band program: `first_mismatch` PLUS a separate `.len` ensure
   (`:1453-1460` — blind in both directions without the pair).

**Not gates:** the two §7.3 landing measurements (pixels = evidence), and the §7.2 profiler
rows (recorded in benchmarks).

---

## 11. `.emp` gotchas this design must respect

Carried verbatim from v3: no multi-line `ensure` conditions; comptime free names resolve at the
call site (inline constants in helper bodies); `{...}` in ensure messages interpolates; an
unreferenced `const` is inert; `data` enforces length, `const` does not; no indexed assignment —
accumulate with `m = m | bit`.

---

## 12. The claims, collected, for the sweep

| # | claim | confidence | falsifier |
|---|---|---|---|
| 1 | Nothing in VBlank writes `Palette_Buffer`; snapshot == payload even on a torn frame | high, 3 ways + census fixed `[MF-7]` | a new VBlank-context writer (§8) |
| 2 | Palette drop arms unreachable **at today's call sites**, saved by enqueue order | high, 2 ways; census not structure | a Critical enqueuer ahead of the palette block |
| 3 | Dispatch pin re-spelled to `OP_PAL_RESTORE`; rungs = 5; F1/F5 move +16 | high, re-derived | F1 measures 412 |
| 4 | +16 mixed-fire is one measurement, expected tight; fallback = de-mix, ruled | medium | the §7.3 measurement |
| 6 | Program-keyed ship refusal writable and complete over `patched_program` output | high (sweep-3-confirmed closed) | a second publish site; a foreign template on `preset(patched:)` |
| 7 | Committer registry's enforcing form | **UNVERIFIED** | attempt in design pass |
| 8 | Snapshot cost ~176 steady / ~704 worst; window not overrun | **ESTIMATE** | §7.2 profiler + worst-case frame |
| 9 | `op_work_cyc` restore arm ≈ region body with own delay | **UNVERIFIED** | `raster_cost_probe` on the new op |
| C-A | Equal-span-partner guard is sufficient for one-band composition | **UNSWEPT, minted by sweep 3, largest claim here** | a passing program that buries a live effect; a needed program refused |
| C-B | `EFX_RESTORE_DELAY` starting at omit lands the burst in-window | **UNSWEPT**, derived only | the §7.3 restore landing measurement |
| C-C | The poison gate is causally grounded in both directions | **UNSWEPT** | a broken build it passes (e.g. copy-at-wrong-splice-point that still lands before the read) |
| C-D | Single-palette-line refusal makes the dirty-mask invariant exact at zero content cost | **UNSWEPT** | shipped content needing a cross-line span |
| — | v3's CLAIM 5 (one band collapses composition) | **KILLED by sweep 3** — recorded so it is not re-adopted | — |

**Minimum band heights (2 / 1, fire-line gap)** are also a re-derivation this draft must not
inherit blind a second time `[MF-2]` — the sweep should re-derive them a third way.
