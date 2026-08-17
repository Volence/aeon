# PARCEL R1 — palette bands (mid-screen restore). Design draft v6 — CONSOLIDATION.

**Date:** 2026-08-16
**Status:** CONSOLIDATION DRAFT — sweep 5 ruled the design CONVERGED
(`2026-08-16-parcel-r1-sweep-5-adjudication.md`); this draft folds in its fixes. Per that
adjudication, verification is a **single seat on the v5→v6 diff**, not a sixth full sweep.
**Supersedes:** v5 (`576e30e7`), v4, v3, v2, v1.
**Scope authority:** the 2026-08-16 Fable ruling (palette-only, one band per program, static
bands), unopened across five sweeps.
**Owner rulings in force:** equal-span-partner guard; the +16 fallback slot is **VACANT**
(measure first, rule only on failure); de-mix is the static-fire S/H idiom only.

> **Provenance discipline.** Sweep-5-minted fixes enter as **CLAIMS E-A..E-D** (§12). The
> five-sweep record on minted fixes: sweep 4's blessed-in-general breakpoint approach carried
> a wrong breakpoint address that sweep 5 caught — the rule ("minted fixes are the most
> likely thing to be wrong") has now paid out five times and the diff-verification seat's
> first job is the E-claims.

---

## 1. What this builds

An effect that turns ON at a scanline and OFF again at a lower one — a fog slab, a top-half
glow, a tinted band, **over up to 3 CRAM entries** (structural: the restore is one stream op
under the `stream_words <= 3` ceiling; wider bands wait on the N-band booking, §9).

The OFF edge is the whole problem: the handler must stream the **pre-effect base colours**
back into CRAM, matching this frame's base-DMA payload exactly.

### Scope, per the ruling

- **Palette only.**
- **ONE band per program** — at most one restore op in the composed program.
- **Static bands only — BOTH of the band's fires** (§4.2 rule 6, E-A). Moving bands in either
  direction are booked (§9).
- Scroll bands are queue item 2.

### What changed from v5

Rule 6 closes the moving-BOTTOM door sweep 5 found open (E-A). D-A's breakpoint moves one
instruction later and its comparison read is pinned to the same stop (E-B). `band()` grows an
`sh:` parameter and computes minima from real merged fire costs (E-C). D-C's enforcement
moves to a program-level scan (E-D). `op_work_cyc` for the restore corrects to **64**. C-D is
re-spelled for the `(addr, count)` payload and re-framed as the CRAM wrap guard. The delay
ladder gains its neither-rung-clean arm. Twelve smaller edits from the sweep-5 must-fix list,
marked `[S5-n]`.

---

## 2. The mechanism — carried, verified by sweeps 2-5

`Palette_Ship_Snap`, 128 bytes, engine-owned: a per-line copy of `Palette_Buffer` taken at the
moment each palette line's frame-top DMA is enqueued. The restore op streams from it.

### 2.1 The splice point

`engine/system/buffers.emp:236-263` (line 0 shown; lines 1-3 identical):

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

The snapshot for line 0 goes adjacent to the `bclr` at `:243` — downstream of both guard
branches, so the copy happens iff the line was dirty and its DMA was accepted. Copy shape:
eight unrolled `move.l (a1)+,(a2)+` per line, on cost grounds alone (160 vs 244 cyc — the
register-contract justification was a census error; `buffers.emp:278` frees d0 at the line-3
splice).

### 2.2 The invariant — stated at full strength `[S5-banked]`

> **`Palette_Ship_Snap[line]` equals THIS FRAME'S base-DMA payload for that line — and for a
> band's own line, "this frame's payload" is DELIVERED this frame, every frame.**

The second half is structural, verified by sweep 5: `Raster_VBlank` ORs the program's
`pal_dirty_mask` into `Palette_Dirty` **before** `Enqueue_Dirty_Buffers` on both VBlank paths
(`raster.emp:573-574`), so the band's line is dirty, enqueued, and snapshotted every frame;
and `Process_DMA_Critical` drains unconditionally — no budget test, no carry-over
(`dma_queue.emp:314-366`). Not "byte-identical to CRAM at frame top" (`VInt_DrawLevel` sits
between enqueue and drain). Exact for single-line spans, which C-D guarantees (§6.2).

### 2.3 Why the snapshot is in phase — CLAIM 1

**Nothing in VBlank writes `Palette_Buffer`.** Three ways: (1) exhaustive writer census — all
main-loop: `Palette_Compose` (`palette.emp:344-348`), `Palette_RotateSpan`, `Palette_DoFade`,
`Palette_DoOperator`, the `Player_RefreshPhysics` line-0 copy, init copies, and the **T15
sky-marker** (`ojz_scroll_test.emp:476-486`) — **unconditional, once per frame**, value
section-keyed (filing settled after three corrections; every census consumer uses this one);
zero hits in `vblank.emp`/`debug/`/`sound/`. (2) `Raster_VBlank` writes only `Palette_Dirty`.
(3) The HBlank handler streams `Pal_Variant_Stage`, not `Palette_Buffer`.

Torn-frame: within one IRQ6 the enqueue, splice, and drain read the same frozen buffer; rests
on `BuildStaticDMA` (`buffers.emp:102-131`) being the only builder of `Static_Pal_Line0..3`
(census fact), not on any general static-entry immutability (false — sprites re-patch).

*Falsifier:* a new VBlank-context writer. §8.

### 2.4 The drop path — CLAIM 2

Unreachable **at today's call sites** (enqueue order: palette lines first; ≤2 pre-existing
Critical entries). A census, not a structure; a drop gate cannot be built without a synthetic
enqueuer — consequence for E-B's claim scope (§10.3).

---

## 3. The opcode

`OP_PAL_RESTORE`, distinct `RasterOp` variant, appended.

### Payload — CLAIM D-F

`PalRestore(int, int)` — **(CRAM byte address, count)**. The snapshot offset IS the CRAM byte
address (`BuildStaticDMA` maps `Palette_Buffer+$00/$20/$40/$60 → CRAM $0000/$20/$40/$60` —
sweep-5-verified for all four lines). Wire: `[OPCODE, cmd>>16, cmd&$FFFF, count-1, addr]`,
`op_size` 5; the `Cram` arm's `vdp_comm` derivation (`raster_dsl.emp:592-595`) is the
precedent for cmd+addr from one field.

### 3.1 The dispatch pin — CLAIM 3, four literals

`RASTER_DISPATCH_RUNGS == (OP_PAL_RESTORE - OP_CRAM)/2 + 1` = 5, spelled against the new last
opcode, **plus the fourth depth literal** `RASTER_DEPTH_RESTORE == (OP_PAL_RESTORE - OP_CRAM)/2`
(= 4; dispatch 82) in the module ensure at `raster_dsl.emp:843-844`. F1 396→**412**, F5
612→**628** (triple-confirmed), both re-measured; F5 wired per §10.2.

**Emission: the restore body goes LAST, after `.op_run_ramp`** — F1=396 proves the chain
currently assembles byte-displacement `Bcc`; a mid-chain insertion risks a silent
word-relaxation (+4/rung) that fails the pins blaming the cost model. Read the displacements
off the listing before pinning. Also read the restore body's `lea Palette_Ship_Snap` form off
the listing (short-form depends on where the §7.1 repin lands).

### 3.2 The restore's delay — CLAIM C-B

Own delay site in the restore body; initially **no spin instructions**, `EFX_RESTORE_DELAY`
introduced at the first nonzero calibration; never shares `EFX_BLANK_DELAY` (dispatch 82 vs
34). All absolute landing figures remain deleted: the ~14/~97 anchors are UNGROUNDED, the
only calibrated capture is a mixed `OP_CRAM` fire (~94-110 cyc away in op position), so the
§7.3 restore measurement is the **FIRST DATUM** at this shape.

The knob starts at no-spin to bracket. Escalation: +18 (`moveq #0`), then +10/`dbf` —
monotone. Readings, complete `[S5-K3]`:
- leading-edge dots ⇒ step up one rung;
- clean ⇒ done; record the constant and the capture as this shape's first calibration datum;
- **leading at rung N and trailing at rung N+1 — the straddle case** (a rung step can exceed
  the clean window's width): no delay value exists; **narrow the restore's stream count** —
  fewer words, narrower burst — and re-measure. This is the §3.3-adjacent remedy, named here
  so the measurement protocol has no unlabelled outcome.

### 3.3 The +16 mixed-fire tax — CLAIM 4, fallback slot VACANT

The one shipped mixed fire is `OJZ_TC_PROG` ch 0 — **patchable** (`ojz_effects.emp:637-639`).
+16 on its SetReg displaces its CRAM burst; one mandatory measurement (§7.3), no prognosis.
De-mix is **unbuildable** for patchable fires (GUARD 11; `check_intervals`; fire-scoped ship
replay — the "tinted but UNSHADOWED" regression). **Owner ruling: measure first; the fallback
slot is vacant; candidates named for that day only** — per-fire comptime delay word (format
moves again); narrowing the fire's stream count; accepting a measured sub-pixel artifact.
TRAP: never retune `EFX_BLANK_DELAY` globally.

---

## 4. Guards

### 4.1 One band per program

Ensure in `raster_program` (covers `patched_program` via `:1426`), via new total
`op_is_restore`. `ensure` is non-aborting (Poison; only `ensure_fatal` aborts —
evaluator-verified), so C-A specs the deterministic **first restore** (authored order); sweep
5 traced the double-violation case to two clean diagnostics with data intact.

### 4.2 The composition guard — CLAIM C-A + rule 6 (E-A)

Carried: `op_cram_span(o)` total (`(-1,0)` for SetReg/Vsram — address-keyed); for the single
restore, every CRAM-span op at an earlier-or-same fire line intersecting the restore's span
is refused unless it is the **unique strictly-earlier op with an exactly equal span** (the
partner — `band()` guarantees equality by construction). Zero partners → refuse. Two+
intersecting earlier → refuse. Same-line intersection → refuse — `[S5-7]` this arm is
**unreachable once D-B ships** (D-B empties the restore's fire; `fire_lines` forbids two
records per line); it stays with a comment naming D-B as what deadens it, per the module's
"a guard that cannot fire is not free" doctrine. Later lines → unconstrained.

**Grounding, load-bearing:** patchable fire lines move; C-A is sound because
`check_intervals` forces strictly ascending disjoint band intervals, so every reachable line
of a patchable record stays on one side of the restore — **sweep-5-verified in both
orderings, transitively, with no straddling spelling found.** *Falsifier: any relaxation of
`check_intervals` silently voids C-A.* In the guard's own comment.

**Rule 6 — CLAIM E-A (sweep-5-minted): BOTH the restore's own carrying fire AND its
partner's carrying fire must be static** (`fire_is_patch == 0`). v5 constrained only the
partner; sweep 5's witness spliced `band()`'s restore fire into `patchable(...)` — every
guard passed, and above `band_hi` the restore record hit `.suppress` (`raster.emp:1083`) and
was not emitted: **the tint ran to the bottom of the screen, silently.** One-fire-list
indexing is an established spelling (`ojz_effects.emp:438`), so the door was open. Both
halves now closed: suppressed-ON (benign, base-over-base) and suppressed-RESTORE (visible).
Deliberately NOT extended to later-line intersecting patchables — legitimate layering, held
below by the same `check_intervals` grounding.

### 4.2a Single-op restore fire — CLAIM D-B

**The fire carrying the restore carries the restore ONLY.** Subsumes the SetReg kill (110 cyc
ahead of the command write — uncompensatable) and the stream-slot race. Consequences, stated
fully `[S5-8]`: nothing else may compose onto the band's bottom line (D-B refuses the merge),
and effectively nothing onto **bot-1 either** in the S/H shape — the reg fire there spends
412 of the 488 available at gap 1, so a second merged `reg_set` (522) is density-refused.
The next effect below a band starts ≥2 fire-lines under the restore — **carrying CLAIM 9's
rider `[S5-5]`: the margin is 8 cyc on the unmeasured constant; a −2% measurement flips it
to 1 (admitting direction), which is why the measurement precedes the freeze.**
D-B refusal messages name the line and op kinds only — compose keeps no input provenance
`[S5-9]`.

### 4.2b The autoincrement refusal — CLAIMS D-C + E-D

`$8Fxx` refused in `reg_set` (the early, message-bearing layer) **and — E-D
(sweep-5-minted) — enforced by a program-level scan in `raster_program`**:
`op_reg_word(o) >> 8 == $8F` → refuse. The constructor ensure alone is bypassable by direct
enum construction (`RasterOp.SetReg($8F04)` — the module's own `:64-70` comment documents the
bypass); the scan is where it cannot be dodged. Grounds carried: the stride-2 assumption is
module-wide; census clean (zero content `$8F` `reg_set`s; the engine's three excursions are
IPL-guarded, HInt-unreachable; **$0F is the only stride-affecting register in the admissible
range** — sweep-5-verified). Revocation condition in the comment: a stride-aware span model.

### 4.3 Program-keyed ship refusal — CLAIM 6

Carried; sweep-5-verified complete against **runtime install state** as well as encoder
output (every install/teardown path clears `Effects_Offscreen_Entry`; a band cannot inherit
a prior program's ship). Cost statement, corrected `[S5-12]`: Sec0 is excluded from bands
**doubly** — by its ship AND by its `[3,220]` channel band leaving no legal interval
(`sum(hi-lo+1)+(N-1) <= 221`); dropping the ship would not buy bands back.

### 4.4 Guards that need nothing

`check_density` (inherits the restore's cost via CLAIM 9), `check_mixed_fire` (restore is
stream-class), layout checks. `check_intervals` untouched — now C-A's stated grounding.

---

## 5. The 14 match sites

12 existing `RasterOp` sites (grep-pinned) + `op_cram_span` + `op_is_restore`. Arms for
`PalRestore(addr, count)`:

| site | arm |
|---|---|
| `op_words` | `[OPCODE, cmd>>16, cmd&$FFFF, count-1, addr]` |
| `op_size` | 5 |
| `op_stream_words` | `count` |
| `count_stream_pal_region_ops` | 0 — not shippable |
| `op_ship_cram_addr` / `op_ship_stage_off` | −1 |
| `op_reg_word` / `op_ship_count` | 0 |
| `op_mask` | `1 << (addr >> 5)` — exact under C-D |
| `op_is_reg` | 0 |
| `op_dispatch_cyc` | `RASTER_DEPTH_RESTORE` |
| `op_work_cyc` | **64** = 122 − 58 (spin 54 + its `moveq` 4) — **UNVERIFIED, CLAIM 9**; v5's 68 kept the moveq and contradicted its own §6.2; fifth arithmetic slip, pre-replicated correction |
| `op_cram_span` | `(addr, 2*count)` |
| `op_is_restore` | 1 |

Plus the opcode const, one `cmpi/beq` rung, the body emitted last (§3.1).

---

## 6. Authoring surface

### 6.1 `band(...)` — CLAIM E-C (sweep-5-minted): the constructor owns the whole shape

`band(top, bot, on: RasterOp, sh: 0|1)`:
- `sh: 0` → `[fire(top, [on]), fire(bot, [restore])]`
- `sh: 1` → `[fire(top, [reg_sh_on(), on]), fire(bot-1, [reg_sh_off()]), fire(bot, [restore])]`

The restore's `(addr, count)` derived from the ON op's span (partner equality by
construction). Why the constructor grows rather than the docs: v5's one-op `band()` could not
see the S/H shape's true minimum — the merged ON fire (`[reg, tint]`, 616 cyc) is measured
against the gap to **bot-1**, so an S/H band needs height ≥ **3**, and a constructor that
admits height 2 hands the author a `check_density` message about a fire pair it never
mentioned (pre-replicated by both arithmetic seats). `band()` computes its minima from the
**real merged fire costs** of the shape it emits. `reg_sh_off()` is a new paired constructor
`[S5-11]` so the off-word derives from the same boot base as `reg_sh_on()` (census-class
safety; no live `$0C` writer today).

Disciplines carried: inline staging arithmetic; not handable to `patchable`.

### 6.2 Constructor refusals

**C-D, re-spelled for the `(addr, count)` payload — and re-framed `[S5-2]`:** the payload has
no `entry`, so the writable form is `stream_cram`'s pair, verbatim:
- `((addr >> 1) & 15) + count <= 16` — **the CRAM wrap guard**, not a belt: addr `$7C` +
  count 3 wraps into CRAM `$00`, the character's line;
- `(addr >> 5) != 0` — the line-0 refusal, else `op_mask` bit 0 forces a per-frame
  character-palette re-assert (the documented Vsram-arm hazard, and sec_pal lines are 1-3
  NEVER 0 by standing rule).

**Minimum band height — CLAIM D-D**, cost-keyed via `fire_cost_cycles` of the fires `band()`
actually emits (E-C):

| ON fire (as emitted) | modelled cyc | min height |
|---|---|---|
| `stream_cram` 1w | 458 | 1 |
| `stream_cram` 2w | 488 — exactly the line; `<=` admits, floored constant, safe direction | 1 |
| `stream_cram` 3w | 518 | 2 |
| `stream_pal_region` 1w | 506 | 2 |
| `stream_pal_region` 3w | 566 | 2 |
| S/H shape (`[reg, tint]` merged, e.g. 616 @ 1w region; gap measured to bot-1 = height−1) | 616 | **3** |

`[S5-4]` The five cram/region rows are
**fixture-pinned** (F2/F3/F4) and invariant under the append — they can freeze now; only the
restore-side row below rides CLAIM 9.

**The restore fire's downstream gap:** 496 (1w) - 556 (3w) at work=64 ⇒ any fire below the
band sits ≥2 fire-lines under the restore. Rides CLAIM 9 (8-cyc margin, §4.2a); re-spelled
after the measurement, which the plan orders FIRST.

### 6.3 Budget

64-word ceiling, 7 fixed. `[S5-3]` Band cost by shape: `pal_region` or 1-word `cram` ON —
**14** words (remainder 43); 2-3-word `cram` ON — **15-16** (remainder 42-41, `Cram` op_size
is `4+len`); the S/H shape — **20** (the ON fire gains the reg op's 2, plus the bot-1 reg
fire's 2+2). A 3-word band cannot share either fire line with any other stream op.

---

## 7. RAM, cost, measurements

### 7.1 Placement

`Palette_Ship_Snap: [u8; 128]` at the engine-RAM tail before `mark Engine_RAM_End`, before
the `@shape_divergent` DEBUG block. Full game-side repin (`game_ram @ after(upper_ram)`).
Routine.

### 7.2 Snapshot cost — CLAIM 8, ESTIMATE

~176 cyc/line, ~704 worst ≈ 3.8% of NTSC blanking (18,565 cyc). Instrument: oracle profiler
**per-routine rows** — `VInt_Level` (row confirmed in-tree) and `Enqueue_Dirty_Buffers`
(plausible, **confirm with `raster_cost_probe --dump` before relying on it** `[S5-impl]`) —
never `interrupts.hint`. Resolution is adequate: the per-routine read is cycle-identical
across five boots. Byte budget cannot see these cycles; `DMA_Budget_Remaining` under-reports
the window once this lands — known, stated.

### 7.3 The two landing measurements — evidence, not gates

Controller-run, pinned camera, reset first, 8 px buckets, recorded in `docs/benchmarks/`.

1. **The restore's landing — the first datum at its shape.** Single-op restore fire; the
   measured row must use entries the art shows. Readings per §3.2's complete ladder,
   including the straddle arm.
2. **The mixed-fire +16** on `OJZ_TC_PROG` ch 0, S/H-seam method. Seam drift ~14-15 px
   expected; colour spill into the visible row is the failure — which vacates into the §3.3
   owner re-ruling. No prognosis.

Ordering pinned by the plan: **CLAIM 9's `raster_cost_probe` measurement runs FIRST** (after
§5's corrected model lands, so the fixture is compared against the right expectation), then
the minima freeze, then the captures.

---

## 8. The structural finding this parcel does NOT close — CLAIM 7

No single frame-top commit seam exists; a future frame-top writer silently invalidates the
snapshot. Mitigation: comptime committer registry — enforcing form UNVERIFIED, advisory form
(census + length-pinning ensure) is the floor; attempt enforcing, ship advisory with stated
residual risk otherwise. Not gating R1.

---

## 9. Ruled out, and booked

- `OP_RESTORE_REG` — dead (register bands are two fires today).
- Scroll bands — queue item 2.
- N bands — booked behind entry-ownership.
- **Moving bands, BOTH directions, explicitly refused**: moving-top (patchable partner) and
  moving-bottom (patchable restore fire) are both closed by rule 6/E-A. When moving bands
  are designed, E-A is the seam to reopen — and sweep 5's suppress-path trace
  (`raster.emp:1083`) is the hazard analysis that design inherits.
- De-mix for patchable fires — dead (recorded).
- EFX-4b — adjacent, untouched.

---

## 10. Gates

1. **`raster_source_gate` restore arm** — existing discipline verbatim: mangled local label,
   exact stop-PC, `deterministic=False`, own offset arithmetic (`addr`). **Breakpoint
   placement lesson applied: probe at the instruction AFTER the one whose effect is read.**
2. **F1/F5 re-measured, F5 wired** — the two-op formula (both ops' fetch+dispatch+work+tail
   over one `RASTER_FIRE_BASE_CYC`; direction sweep-5-confirmed against the existing
   one-op derivation). "Only F1 sees the fall-through" corrected: only among wired F0/F1/F3.
3. **The poison gate — CLAIM E-B (sweep-5-minted, corrected D-A).** Breakpoint at
   **`buffers.emp:238`** — one instruction AFTER the `d0` load (oracle checks breakpoints
   BEFORE execution; v5's `:237` captured pre-entry garbage — the fourth
   instruction-boundary error in this gate's lineage, caught by the discipline the tree's
   own source gate documents). At that stop, `d0` IS the pre-enqueue mask. **The payload
   comparison reads `Palette_Buffer` at the SAME stop** — the buffer is frozen for the IRQ
   (CLAIM 1) — never at end-of-frame, where v5's read passed only by T15-idempotency
   coincidence. Poison outside the CRAM value space (`$Fxxx` family), asserted absent from
   the fixture palette. Per-line: lines in the captured mask equal the payload span; lines
   outside retain poison — **noting the band's own line can never exercise the retain half**
   (dirty every frame by §2.2's banked invariant); the fixture must include a non-program
   line for that half. Claim scope: dirty-gating and copy extent; the `bcs` drop arm is
   untestable (§2.4) and the gate's comment says so.
4. **The expect-fail lane** — separate sigil invocations over poison modules, asserted to
   exit nonzero AND emit the expected message. Properties stated `[S5-10]`: the lane parses
   the whole `--root` tree per run (`Manifest::scan` is unconditional — CI cost, not
   soundness); the message match is fragile against wording edits (a wrong/missing message
   still fails, so drift is caught, but attribute failures to wording first). Poisons:
   two-restore (§4.1); band+overlapping-tint (C-A multiplicity); **rule-6 violation via a
   DISJOINT-span patchable co-tenant** `[S5-6]` — the same-span spelling trips the
   multiplicity arm first and never reaches rule 6 (working spelling in the sweep-5 seat
   report); SetReg-on-restore-fire (D-B); `RasterOp.SetReg($8F04)` direct-construction (E-D
   — poisons the scan, not the constructor).
5. **Comptime hand-twin** + separate `.len` ensure.

---

## 11. `.emp` / sigil facts this design rests on

No multi-line ensure conditions; comptime free names resolve at the call site; `{...}`
interpolates in messages; unreferenced `const` inert; `data` enforces length; accumulate with
`m = m | bit`; tuple returns via destructuring ONLY; no `break`/`continue`; no comparison
chaining; **`ensure` is non-aborting** (Poison; `ensure_fatal` aborts) — guards tolerate
poisoned neighbours and pick deterministic representatives.

---

## 12. The claims, collected

| # | claim | confidence | falsifier |
|---|---|---|---|
| 1 | No VBlank writer; T15 filing settled | high, 3 ways, census thrice-corrected | a new VBlank-context writer |
| 2 | Drop arms unreachable at today's call sites | high; census | a Critical enqueuer ahead of the palette block |
| 3 | Pin + 4th literal; F1/F5 412/628; body last; listing read | high, triple-derived | F1 ≠ 412; a word-relaxed rung |
| 4 | +16 is one measurement; fallback VACANT (owner) | — | the §7.3 measurement |
| 6 | Ship refusal complete (encoder + runtime); Sec0 doubly excluded | high, sweep-5-extended | a second publish site |
| 7 | Committer registry enforcing form | UNVERIFIED | attempt in design pass |
| 8 | Snapshot ~176/~704 ≈ 3.8%; per-routine rows | ESTIMATE | §7.2 measurement |
| 9 | Restore `op_work_cyc` = **64** (corrected) | UNVERIFIED — **measure FIRST, before minima freeze** | `raster_cost_probe` |
| C-A | Equal-span-partner + `check_intervals` grounding | survived sweeps 4-5 | a passing program that buries a live effect; an intervals relaxation |
| C-B | Own delay knob; bracket start; complete ladder incl. straddle arm | mechanism thrice-confirmed | the §7.3 capture |
| C-D | Wrap guard + line-0 refusal, re-spelled for `(addr,count)` | re-derivation | — |
| D-B | Single-op restore fire | survived sweep 5 | content needing a multi-op restore fire |
| D-D | Cost-keyed minima; cram/region rows fixture-pinned, freezable now | third derivation matched | the CLAIM 9 measurement (restore row only) |
| D-F | `(addr, count)` — offset IS the address | sweep-5-verified, all four lines | a mapping change |
| E-A | Rule 6: BOTH band fires static | **UNSWEPT (sweep-5-minted)** — diff-seat priority | a spelling that reaches `.suppress` on either band fire |
| E-B | Corrected poison gate (`:238`, same-stop read, non-program line) | **UNSWEPT** — diff-seat priority | a broken build it passes in-scope |
| E-C | `band(sh:)` owns the shape; minima from merged costs | **UNSWEPT** | an emitted shape whose real minimum differs from the constructor's |
| E-D | Program-level `$8F` scan closes the construction door | **UNSWEPT** | a CRAM-stride mutation the scan misses |
| — | v3 CLAIM 5; v4 C-C; v4 C-B analysis; de-mix-for-patchable; v5 rule-6-partner-only; v5 `:237` breakpoint; v5 work=68 | **KILLED — recorded** | — |

Ordered small fixes riding the implementation: the cost-table comment's `adda.w` attribution
(12, not 8); the stale `ojz_effects.emp:617-618` comment; §10.1's probe-PC discipline note.
