# PARCEL R1 — sweep 4 adjudication. v4 stopped, but the kills are repairs, not re-directions.

**Date:** 2026-08-16
**Draft reviewed:** `specs/2026-08-16-parcel-r1-palette-bands-v4.md` @ `144ec6ac`
**Seats:** gate vacuity (Sonnet), hardware/timing (Fable), correctness/state (Opus).
**Prior:** sweeps 1-3 killed v1-v3; the audit holed three of sweep 2's minted fixes.
**Adjudicator verification:** the two decisive factual disputes below were resolved by the
adjudicator's own reads of `ojz_scroll_test.emp:466-496` and `ojz_effects.emp:560-645`, not by
majority vote between seats.

---

## The one-line state

**The mechanism, the opcode, and C-A's guard shape all survived a hostile pass — for the first
time in this parcel, no kill is direction-level.** What died: the poison gate as specified
(C-C, two seats independently), the delay candidate analysis (C-B, on an anchor that turns out
to be ungrounded AND the wrong fire shape), the owner-ruled de-mix fallback (unbuildable for
the actual live fire), and the unguarded restore-fire shapes (SetReg-on-restore, autoinc).
Every kill has a namable repair. v4 does not proceed; v5 is specification-level, with **two
items that go back to the owner** (§Kill-3's re-ruling, and C-C's harness scope).

---

## KILL 1 — CLAIM C-C, the poison gate, is dead as specified. Three independent holes, two seats.

**(a) It red-flags a correct build on its own named fixture.** §10.3 says the fixture mask is
"the program's `pal_dirty_mask` (OJZ: line 2, `%0100`), known at authoring time". False —
verified by adjudicator read: the T15 sky-marker block (`ojz_scroll_test.emp:476-486`) runs
**unconditionally every frame** in `GameState_OJZScroll_Update` — outside the `if DEBUG` block
(closes at `:473`), before `Parallax_Update` — writing `Palette_Buffer` word 0 and
`ori.b #1, Palette_Dirty`. Only the *value* is section-keyed. The real pre-enqueue mask is at
least `%0101`, line 0 is legitimately snapshotted, and the gate's "non-dirty lines retain
poison" half fails a correct build. **This also corrects v4's `[MF-7]` and sweep 3's own
census filing** — `:485` is not "the per-section-crossing update body"; it is per-frame.
(The gate-vacuity seat's contrary CONFIRMED item traced only the cycle/physics writers and
missed this block; adjudicated against it by direct read.)

**(b) The quantity it keys on is unobtainable by its own rules.** The pre-enqueue
`Palette_Dirty` is destroyed by the four `bclr`s as the lines enqueue
(`buffers.emp:243,249,255,261`) — it is not recoverable from a paused post-frame RAM read.
Capturing it needs a breakpoint at `buffers.emp:237` reading `d0`, which §10.3's "RAM reads
only" phrasing forbids. **The phrasing, not the harness, is the problem**: `effects_gates.py`
already runs breakpoint-based fixtures (the F-series and `raster_source_gate`), so a
breakpoint-captured pre-enqueue mask rides the existing runner. The self-imposed constraint
was wrong, not the goal.

**(c) It cannot see the half of the splice it exists to protect.** A broken build that splices
the copy gated only on "dirty" (after the `btst`/`beq`) and ignores the drop guard (`bcs`)
passes the gate identically, because the drop path is unreachable in fixture content (CLAIM 2,
by the draft's own restatement). The gate never forces a drop, so the `bcs`-side of the splice
is untestable without the synthetic 8th Critical enqueuer §2.4 already rules out building.
**The repair is honesty of claim scope**: the poison gate (breakpoint form, per (b)) tests
splice *location relative to the dirty test* and copy extent; the drop-arm half is asserted by
code review plus the §2.4 grounding ("the enqueue and the bit-clear are the same event"), and
the gate's comment must say so.

Also unspecified: the poison pattern itself, unchecked against collision with real payload
words (Genesis palette words are low-entropy; `$0000`/`$0EEE` recur). The repair must pick a
poison provably absent from the fixture palette (e.g. a word with bits set outside the
9-bit-per-channel CRAM format) and state it.

**C-C's v5 form (a sweep-4-minted claim, unswept):** breakpoint at the pre-enqueue read
capturing `d0`; poison chosen outside the CRAM value space; assert per-line
snapshot==payload for lines in the captured mask, poison retained for lines outside it; claim
scope limited to dirty-gating and copy extent.

---

## KILL 2 — CLAIM C-B's candidate analysis is dead. The arithmetic was wrong AND priced against the wrong anchor.

Two independent witnesses from the hardware seat, both re-derived by the adjudicator's read of
the pinned table:

**(a) The "+14 over-count".** v4's "moveq #0 lands the last word at ~96 of ~97" folded the
stream loop's final *expired* `dbf` (14 cyc) into the burst span — an instruction that runs
after the last write and cannot paint a dot. Stream cadence is 30 cyc/word
(`RASTER_STREAM_WORD_CYC`, `raster_dsl.emp:816`): on the draft's own anchor the moveq#0
candidate's last word lands ~82 of ~97, not ~96. So the real comparison was **omit ≈ 4 cyc
leading margin vs moveq#0 ≈ 15 trailing / 8 additional leading** — and the draft picked the
4-cycle candidate *because of* the inflated figure. The selection rationale is built on the
error. (This is v3's exact +14 error, inherited by the adjudicator into v4 despite the
process warning. Recorded as such.)

**(b) The anchor itself.** The only calibrated-clean landing evidence in the tree
(`effects-p2/GATE-EVIDENCE.md` rows 118-120) was captured on `OJZ_TestRaster` — a **mixed**
fire (SetReg precedes the CRAM op) whose stream op is `OP_CRAM` (dispatch 18), not
`OP_PAL_REGION` (34). A bare single-op restore fire differs from that anchor by the whole
preceding-SetReg op (~94 cyc today, 110 after the append) plus the dispatch delta — terms
6-10× larger than the ±10/±8 the candidates argue over, and v4 applied none of them. No clean
landing measurement for ANY single-op sparse CRAM fire exists (P1's was voided by its own
CORRECTION). Under the mixed-anchor reading both candidates plausibly land far *early*, and
§7.3's tripwire ("trailing dots at no-spin ⇒ re-derive") is itself mis-derived.

**What survives:** the mechanism — own delay site, own measurement, never share
`EFX_BLANK_DELAY` — and the relative deltas (omit −10 / moveq#0 +8 net vs region overhead,
independently confirmed). **What v5 must say instead:** the §7.3 restore measurement is not a
confirmation step, it is the **first datum** at this fire shape; the delay knob's starting
value is chosen to bracket, not to pass (start omit, expect to step); and the ~14/~97
constants are flagged UNGROUNDED (see BLOCKED) rather than quoted as anchors.

**Corollary retraction:** §3.3's "the +16 mixed-fire measurement is expected to be tight and
may fail" is withdrawn. On the corrected span arithmetic the draft-anchor slack is ~23 cyc and
+16 is expected to pass; on the anchor-ungrounded reading it is not derivable at all. Neither
tilt may drive planning. The measurement stands; the prognosis is deleted.

---

## KILL 3 — The owner-ruled de-mix fallback is UNBUILDABLE for the fire it exists to save. The ruling goes back to the owner.

Verified by adjudicator read of the preset table (`ojz_effects.emp:569-575`): the live mixed
fire is **not** a static program — no preset installs `OJZ_WATER_PROG`. It is `OJZ_TC_PROG`
channel 0: `patchable(fx_tint_band(... sh: 1), ch: 0, lo: 3, hi: 220, offscreen_ship: 1)`
(`:637-639`). De-mixing it means two patchable records tracking one moving boundary on one
channel — refused three independent ways (correctness seat, verified plausible against
source): GUARD 11 (`raster_dsl.emp:1146-1153`, one patchable record per channel),
`check_intervals` (overlapping bands `[2,219]`/`[3,220]`), and — decisively — `ship_trailer`
collects the frame-top replay registers **from the shipped fire's own op list**
(`:1300-1308`), so a de-mixed region fire ships with zero reg words, re-opening the documented
"tinted but UNSHADOWED" found-in-play regression (`:1294-1299`). Making the S/H half static
instead decouples the seam from the moving water line, i.e. deletes the effect.

**The de-mix pattern is still valid where it CAN build — static fires — and that is exactly
where Kill 4 needs it** (below). But as the ruled fallback for the +16 on the live patchable
water fire it is dead. Combined with Kill 2's corollary (the +16 is no longer "expected to
fail"), the honest v5 position is: **measure first; the fallback slot is VACANT and
re-ruled only if the measurement fails.** Candidate fallbacks to name (not rule) in v5: a
per-fire comptime delay word in the wire format (structural, format moves again); accepting a
measured sub-pixel artifact if that is what it is; narrowing the shipped fire's stream count.
This is an **owner decision point**, flagged per the leapfrog-provenance rule.

Rider (hardware seat, survives in modified form): the arm-word gate derives its expectations
from the scene sidecar (`effects_gates.py:72-98`), so no gate breaks under any future
de-mix — but the P2 baseline rows 118-120 become stale as evidence for whatever shape ships,
and any re-authoring regenerates the sidecar.

---

## KILL 4 — The restore fire's own SetReg shape is unguarded, and it is the headline content.

Correctness seat, arithmetic re-checked: ending an S/H band means the restore fire is
`[reg_set($8C81), restore]`. `check_mixed_fire` forces the SetReg first; under the appended
chain a SetReg op costs 8+80+12+10 = **110 cyc** before the restore's command write even
begins. No value of `EFX_RESTORE_DELAY` can compensate (it is already at/near zero and the
required correction is negative). Whatever Kill 2 did to the absolute anchor, a +110
op-position term is outside any reading of the blanking window: **dots on the restore line of
every S/H band, guaranteed, and §7.3's measurement-1 as specified certifies a shape content
will not ship.**

Cheap close, entering v5 as a claim: **refuse any `SetReg` on the fire carrying the restore**,
and state the S/H-band OFF pattern as the *static* de-mix — `fire(bot-1, [reg_set($8C81)])` +
`fire(bot, [restore])` — which builds (two static fires, no channel), keeps the restore fire
single-op (matching C-B's measured shape), and inherits the codebase's own "schedule the mode
change a line earlier" remedy. Measurement-1 then measures the shape that ships.

Same class, narrower (correctness seat): **the autoincrement hole.** `reg_set($8F04)` is
blessed by the constructor's own comment (mid-frame autoinc is "ordinary technique",
`raster_dsl.emp:124-127`), changes the stream stride to 4, and silently voids every span/mask
computation C-A depends on — the restore leaves a tinted entry behind and paints base over an
entry it does not own, with every guard passing. No shipped content does it; the engine's own
`$8F` excursions are IPL-guarded (`section.emp:243-250`, `plane_buffer.emp:465-469`) and
unreachable by HInt. Close with one ensure: refuse `$8Fxx` `reg_set` in any program carrying a
restore (or tree-wide; owner's pick — tree-wide is simpler and no content uses it).

---

## MUST-FIX, consolidated across seats

1. **Minimum band heights are wrong for the third time — and two seats independently derived
   the same correction, which is the redundancy this process was built for.** The minima key
   on the ON op's **class**, not word count: a 1-word `pal_region` fire models 506 > 488 ⇒
   gap **2** (the primary band content, `fx_tint_band`, is `pal_region`); 1-2-word
   `stream_cram` ⇒ 1 (2-word = 488 exactly, zero modelled slack — state it); 3-word either ⇒
   2. `band()`'s refusal must key on `fire_cost_cycles` of the ON fire, not on count.
   Additionally the **restore fire's own downstream gap** (≥ 2 at every count: 496-556 > 488,
   riding unmeasured CLAIM 9) is underived in v4 — an effect starting 1 line below a band is
   refused by `check_density` with a diagnostic §6 never predicts. Both tables enter v5
   re-derived and CLAIM-labelled against CLAIM 9's measurement.
2. **C-A's earlier/later reasoning must state its real grounding**: it is safe for patchable
   fires ONLY because `check_intervals` forces disjoint ascending bands, so a moving record
   stays on one side of the restore. Falsifier: any relaxation of `check_intervals` silently
   voids C-A. Corollary to rule on: the **split spelling of a top-moving band**
   (`patchable(tint)` + static restore below `hi`) is ADMITTED by the guard as specified,
   while §9 books moving bands as unrepresentable — state it as the one legal moving-top form
   (with the local-removal interaction: a suppressed ON record leaves the restore firing
   base-over-base, inert) or refuse it. Refusing is one ensure; admitting needs the §9
   booking rewritten.
3. **The restore must be the FIRST stream op on its fire.** `fire` admits two stream ops and
   only the first's writes are measured to land in HBlank; compose's `progs`-order emission
   decides which op gets the good slot — the "worse half" surviving for disjoint spans.
   One ensure.
4. **Drop the restore's redundant payload fields.** `BuildStaticDMA` maps
   `Palette_Buffer+$00/20/40/60 → CRAM $0000/20/40/60` (`buffers.emp:106-131`), so the
   snapshot offset IS the CRAM address. `PalRestore(addr, count)` removes the
   field-disagreement hazard v4 otherwise inherits (a hand-authored restore with
   `pal_line`/`entry` disagreeing with `addr` streams the wrong line's base while
   address-keyed C-A passes). If the long form is kept, the `stream_pal_region` agreement
   ensures (`:181-184`) must be replicated. The short form is better: one fact, one field.
5. **Branch-relaxation hazard on the F1 pin.** F1=396 proves all four rungs currently
   assemble byte-displacement; inserting the restore body beside `.op_region` pushes the
   dense-op targets toward the ±127 edge, and one relaxation to word makes a failed rung 20,
   failing both pinned equalities with a message blaming the cost model. **Emit the restore
   body LAST (after `.op_run_ramp`) and read the emitted displacements off the listing before
   pinning 412/628.** The `raster_source_gate` extension must also carry the existing gate's
   discipline verbatim: mangled local label, exact stop-PC assertion, `deterministic=False`.
6. **Pin the new dispatch depth.** §3.1 re-spells `RASTER_DISPATCH_RUNGS` only; the module
   ensure at `:843-844` holds three depth literals and its message says "update these three".
   It gains a fourth term: `RASTER_DEPTH_RESTORE == (OP_PAL_RESTORE - OP_CRAM) / 2`.
7. **Gate 4's negative programs need a mechanism that exists.** `ensure` is non-aborting in
   sigil (Poison + continue; only `ensure_fatal` aborts), and no expect-fail build harness
   exists in the tree — a poison program in a normal target fails the WHOLE build. v5 must
   either add a named expect-fail lane (a separate sigil invocation asserted to exit nonzero,
   wired into the tool suite) or replace gate 4 with comptime-twin coverage. Also: with
   non-aborting ensures, a two-restore program reaches C-A anyway — spec the deterministic
   choice (first restore) so the diagnostic is clean.
8. **F5 wiring is real work, and the F1 sentence was wrong.** F5 contains the same
   fall-through SetReg as F1 (it is why it moves 612→628); the draft's "F1 is the only
   fixture that exercises the fall-through op" should read "the only one among the wired
   F0/F1/F3". Wiring F5 into `effects_gates.py` needs a two-op expected-cost formula that
   does not exist there yet (sum both ops' fetch+dispatch+work+tail over one
   `RASTER_FIRE_BASE_CYC`).
9. **§7.2's instrument must name its rows**: per-routine profiler rows (`VInt_Level` /
   `Enqueue_Dirty_Buffers`), never `interrupts.hint` (HBlank+VBlank summed — the standing
   trap the module's own comment records).
10. **Small census/comment corrections**: the "d0 is contractually live across all four
    splices" justification is false for the line-3 splice (`buffers.emp:278` says d0 is free
    there) — the unrolled-copy conclusion survives on cost alone (160 vs 244); the cost-table
    comment's region attribution is off by 4 (`adda.w (a1)+,aN` is 12, not 8 —
    `raster_dsl.emp:822-823`); the stale "526 against a 489-cycle line" comment at
    `ojz_effects.emp:617-618`; and [MF-7]'s filing corrected per Kill 1(a).
11. **Content limits stated in §1/§6**: a band restores at most **3 CRAM entries** (stream-op
    ceiling × one restore op) — C-D's `entry+count<=16` can never bind and the "fog slab"
    framing must say "up to 3 entries"; a 3-word band cannot share either fire line with any
    other stream op; and §4.3's refusal permanently excludes Sec0 (`OJZ_TwoChannel`,
    `offscreen_ship: 1`) — the one section with a live raster program — from carrying a band.

---

## What the sweep CONFIRMED — record it so it is not re-derived

- **C-A is expressible in `.emp` as specified** — verified at the sigil evaluator source, not
  argued: tuple returns work (`Value::Tuple`, destructuring `let (a,b) =` only — no indexing,
  no `.0`), match arms are full expressions, `return` escapes nested loops, `ensure` is legal
  in fn bodies. Constraints v5 must respect: no `break`/`continue` (done-flag or `return`),
  no comparison chaining.
- **The §5 site table is complete**: exactly 12 `RasterOp` match sites exist (grep-counted at
  `:590,621,635,663,676,684,693,701,710,728,847,858`), +`op_cram_span` = 13; the 7
  `RasterFire` sites are untouched by a new op variant. The mechanical arm choices are safe
  (`count_stream_pal_region_ops→0` makes a restore unshippable at `patchable:356`;
  `op_is_reg→0` routes it into the stream ceiling and mixed-fire ordering).
- **Compose's merge cannot reorder ops across lines** and the guard's line reasoning is
  merge-safe (subject to must-fix 2's grounding); "fire line" vs "screen line" is a uniform
  −1, ordering-identical.
- **§4.1's placement covers both entry points** (`patched_program` calls `raster_program`
  at `:1426` before table work); §4.3 is writable with no in-`patched_program` bypass.
- **C-D is arithmetically correct at both ends** (entry 15/count 1 → bytes 30-31; entry
  0/count 16 → 0-31) and is verbatim `stream_pal_region`'s own check — though unreachable in
  practice per must-fix 11.
- **[MF-10]'s re-grounding holds**: `BuildStaticDMA` is the only builder of
  `Static_Pal_Line0..3`; `Render_Sprites` re-patches `Static_Sprite_DMA` only. The
  immutability generalisation is genuinely no longer load-bearing.
- **The dispatch arithmetic is now triple-confirmed** (two seats + adjudicator): rungs 4→5,
  SetReg 64→80 (+16), F1 396→412, F5 612→628, restore dispatch 82 (+48 vs region, +64 vs
  cram — the latter never stated in v4 and feeding Kill 2b). F5 confirmed unwired
  (`effects_gates.py:196`).
- **The +16 does not break the shipped program's density** (`OJZ_TC_PROG` ch0 models 676
  against a 976 gap-2 budget), and a reg-only fire (412 ≤ 488) admits the gap-1 de-mix — for
  static fires, where Kill 4 needs it.
- **Snapshot cost arithmetic checks**: ~176/line, ~704 worst ≈ 3.8% of the NTSC blanking
  window; band budget 14 words, 43-word remainder; 16 cyc ≈ 14-15 px, 8 px buckets justified.
- **The engine's `$8F` excursions cannot interleave with HInt** (IPL-guarded) — Kill 4's
  autoinc hole is authoring-side only.

---

## BLOCKED — constants that do not exist, refused as anchors

- **The ~97 cyc blanking window** and **the ~14 cyc past-edge calibration point**: no
  measurement or grounded derivation anywhere in the tree (the "~123 true HBlank" figure is
  itself an unmeasured design-doc estimate). Every landing margin in v4 was quoted against
  them. v5 states them as UNGROUNDED and treats the first pinned-camera capture as the first
  datum.
- **`op_work_cyc` for the restore** (CLAIM 9): hand-derived only; measure with
  `raster_cost_probe` before §6.2's restore-side minima are spelled.
- **Whether the appended rung's branches stay byte-sized**: needs the build listing
  (must-fix 5).

---

## Where this leaves the parcel

The core is now stable across two consecutive sweeps: snapshot mechanism (3 seats), opcode
choice + dispatch arithmetic (triple-confirmed), C-A's shape (expressible, merge-safe,
grounded modulo must-fix 2), C-D, the scope. v5 is a repair pass:

1. C-C rebuilt as the breakpoint-form poison gate with honest claim scope (Kill 1) —
   **sweep-4-minted, enters v5 as a claim**.
2. C-B re-derived against the mixed-anchor reality; measurement re-framed as first-datum;
   prognoses deleted (Kill 2).
3. **OWNER: the +16 fallback ruling is vacated** (Kill 3). Recommend: measure first, rule a
   fallback only on failure, candidates named in v5.
4. The two shape guards (no SetReg on the restore fire + static de-mix pattern for S/H bands;
   `$8Fxx` refusal) (Kill 4) — **sweep-4-minted, enter v5 as claims**.
5. The eleven must-fixes, of which the class-keyed minima (independently double-derived) and
   the C-A grounding statement are the substantive ones.

**The process note, fourth iteration.** Sweep 4 minted fixes again (the breakpoint gate, the
class-keyed minima, first-stream-op rule, the payload collapse, the shape guards). Per the
standing rule they enter v5 as claims. One instance of the disease recurred in v4 itself —
the +14 over-count was inherited from v3's §7.3 text even while re-deriving around it — and
one instance of the cure worked: two seats independently produced the same minima correction,
which is the first time a minted fix arrives pre-replicated.
