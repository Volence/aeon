# PARCEL R1 — sweep 3 adjudication. v3 stopped. The narrowing did not do what it was bought to do.

**Date:** 2026-08-16
**Draft reviewed:** `specs/2026-08-16-parcel-r1-palette-bands-design.md` @ `db5ea7af`
**Seats:** gate vacuity (Sonnet), hardware/timing (Fable), correctness/state (Opus).
**Prior:** sweep 1 killed v1, sweep 2 killed v2, and the audit holed three of sweep 2's own fixes.

---

## The one-line state

**The mechanism is now verified sound by a third independent seat. The SCOPE ARGUMENT is not.**
One band per program was adopted because it "collapses the pairing predicate, the cross-band
overlap guard and the merged-fire ordering problem, all at once". It collapses the first partially
and the other two not at all. That was the draft's entire justification for shipping with no
composition guard, so v3 does not proceed.

**This is sweep 1's unanswered objection wearing a smaller scope.** The prediction in the audit —
"under the current process a sweep 3 should be EXPECTED to kill something in the fix list" — came
true, and it killed the fix the whole draft was built on.

---

## KILL — CLAIM 5 is false. One band per program does not collapse composition.

Derived at `raster_dsl.emp:393-466` and re-derived against every guard `raster_program` runs.

```
compose([ band(top: 100, bot: 140, entries E),
          fx_tint_band(line: 120, ... same E ...) ])
```

| guard | line | verdict |
|---|---|---|
| `fire_lines` | 1046 | 99, 119, 139 — strictly ascending. PASS |
| `check_intervals` | 982 | intervals `[99,99] [119,119] [139,139]`, disjoint. PASS |
| `check_density` | 1014 | 20-line gaps. PASS |
| `check_mixed_fire` | 1082 | keys on `op_is_reg` only. PASS |
| the proposed one-restore ensure | — | exactly one restore. PASS |

At runtime the restore at 140 writes base over `E` and **kills `fx_tint_band`'s tint from 140 to
the bottom of the screen**, where that preset is specified to run. Nothing in the tree can see it:
no guard reads *which CRAM entries an op owns*. `op_mask` (`:709-720`) reduces the whole address to
one palette-line bit; `op_ship_cram_addr` (`:675-682`) is read only by the ship trailer.

The same-line variant is worse and is verbatim sweep 1's third bullet: `compose` splits ops
regs-then-streams (`:434-452`), so two stream ops on one line merge into one fire and **which wins
is decided by the order the author passed lists to `compose()`**.

**What the narrowing actually bought:** "nothing to overlap with" is true only of
*restore-vs-restore*. The overlap that matters is *restore-vs-any-CRAM-writer*, and a program may
carry arbitrarily many of those. The pairing predicate is not collapsed either — with one restore
and three region fires above it, "which fire is this restore's partner, and does it cover the same
entries" is still unanswered; it is merely no longer ambiguous *between restores*.

**Sweep 1's categorical objection stands unanswered.** A restore "writes the ABSENCE of a value,
which cannot lose a race — it is a destructive reset". One band bounds the *number* of resets to
one. It does not make that one reset compose. Blast radius N×N → 1×N; semantics unchanged.

---

## KILL — the restore's own CRAM burst misses the blanking window. "Same `EFX_BLANK_DELAY`" is false.

The draft said the restore is `OP_PAL_REGION`'s body with a different `lea`, "same
`EFX_BLANK_DELAY`". But the delay is calibrated for the region path's **dispatch depth**, and an
appended opcode does not run at that depth:

- `OP_PAL_REGION` — 1 failed rung + hit = 16 + 18 = **34 cyc** before its command `move.l`
  (`raster.emp:694-697`; costs pinned `raster_dsl.emp:813-814`).
- `OP_PAL_RESTORE = 10` appended — 4 failed rungs + hit = 64 + 18 = **82 cyc**. **Δ = +48.**

Re-derived two ways: the depth formula `(10-2)/2 = 4`, and counting the four `cmpi/beq` rungs at
`raster.emp:694-701`. Against the draft's own window arithmetic (burst ~14 cyc past the edge, three
words ~74, window ~97), the restore's last word lands ~136 cyc past the edge — outside the window
on every reading, including the most generous (H40 blanking incl. borders ≈ 123 cyc).

**So every band paints ~30-40 px of CRAM dots on its own restore line** — the exact artifact
`EFX_BLANK_DELAY` exists to kill — unmixed, and independent of the §3.2 mixed-fire tax. §7.3
measured only the water fire's +16; nothing in the draft observed the restore's own burst.

This is not fatal to the direction, and **sweep 1 already anticipated the remedy**: a fifth opcode
"gives the restore its own independently tunable body". The draft quoted that as a benefit and then
contradicted it by sharing the constant. The restore needs its **own** delay constant (≈0-1 `dbf`,
since dispatch has already burned the margin) and its own landing measurement.

**And the mixed-fire +16 now looks likely to FAIL, not pass.** By the same derivation the baseline
slack is ≤ ~9 cyc. The draft ruled out the only cheap remedy (global retune — correctly, the tax is
per-op-mix and the delay is global) and named no fallback, so R1 as drafted breaks shipped content
with no ruled path.

---

## KILL — Gate 3 is a tautology, and inverted on the case it exists for.

§10.3 compares `Palette_Ship_Snap` against "the four static DMA source spans". Those spans **are**
`Palette_Buffer + $00/$20/$40/$60` (`buffers.emp:13-16`, `extern("Palette_Buffer") + $NN`). The
gate compares the copy to the memory it was copied from.

Given CLAIM 1 (nothing in VBlank writes `Palette_Buffer`), the buffer is frozen for the whole
VBlank window, so **any** copy loop, spliced **anywhere**, ignoring the drop branch entirely,
produces equality — including the exact broken build §2.1 exists to prevent.

Worse, and found by two seats independently: on a dirty-but-dropped line, *correct* code leaves the
snapshot holding the OLD value while `Palette_Buffer` holds the NEW one, so **the gate red-flags
correct code**. It passes wrong builds and fails right ones. It only reads as a mere tautology
because CLAIM 2 says the drop path is unreachable.

Any replacement must compare against something causally independent of the snapshot's source — the
DMA queue's accepted-entry record, or CRAM itself — and must be masked by the **pre-enqueue**
`Palette_Dirty` value (`d0` at `buffers.emp:237`, dead by the ship block at `:278`). **NEW CLAIM,
unswept.**

---

## Must-fix, individually smaller

1. **§4.3's "`check_intervals` is already what forbids two overlapping bands" is FALSE.** VERIFIED
   at `raster_dsl.emp:982-992`: it works in **fire-line** space, one interval per record, and
   forbids two records reaching the *same fire line* because the arm gap would be -1 = `$8AFF` =
   PARK. Bands `[100,140]` and `[120,160]` produce four distinct fire lines and pass. A
   load-bearing mis-derivation that the §4.1 relaxation path would have inherited.
2. **§6.2's minimum band heights were copied from sweep 2, not re-derived — the exact sin this
   process warns about.** Re-derived: `check_density`'s gap is the fire-line difference; a 3-word
   `stream_cram` is 518 and a 3-word region 566, both ≤ 2×488 ⇒ gap ≥ **2**; a 1-word stream is
   458 ≤ 488 ⇒ gap ≥ **1**. So the minima are 2 and 1, not 3 and 2 — unless "band height" means
   the inclusive span, a definition the draft never states. The constructor refusal must be spelled
   against the fire-line gap or it will refuse programs the model admits.
3. **§7.1 understates the RAM cost.** VERIFIED: `pub region game_ram @ after(upper_ram)`
   (`games/sonic4/config/ram.emp:72`), so 128 B at the engine tail ripples **every game-side RAM
   address** — a full repin. `ram.emp`'s "ripples ZERO existing addresses" is true of *engine* RAM
   only, and the draft quoted it as the whole cost.
4. **§7.2's Deferrable-drop check cannot answer.** The DMA budget is **byte**-denominated
   (`vblank.emp:136`, `:168-190`) and the snapshot adds zero bytes, so Deferrable behaves
   identically with and without it however many cycles it burns. The real failure mode is silent
   overrun of the blanking window, and the right instrument is end-of-window position, not queue
   behaviour. As specified this measurement goes green vacuously.
5. **F5 is not wired.** `effects_gates.py:196` asks `--only F0,F1,F3`. §10 claimed "F1 and F5
   re-measured"; F5's constant (612→628) would be hand-updated with nothing checking it.
6. **`offset_of()` carries a `slot*128` term** (`raster_source_gate.py:83`) that does not apply to
   the restore's `line*32 + entry*2`. A naive Gate 1 extension reusing it predicts wrong.
7. **Census hole.** `games/sonic4/test/ojz_scroll_test.emp:485` writes `Palette_Buffer` (+ dirty at
   `:486`) inside the per-section-crossing update body — a **live runtime writer**, mis-filed by the
   draft as an init copy. CLAIM 1 survives (it is main-loop), but the falsifier discipline depends
   on the census being right.
8. **CLAIM 2 must be restated** as "unreachable at today's call sites". "≤2 pre-existing entries"
   is a census of today's content, not a structural bound, and nothing pins it.
9. **`op_mask` is `1 << (a >> 5)` — the START line only.** A restore spanning a 32-byte palette-line
   boundary leaves the second line out of `pal_dirty_mask`. Not fatal (snapshot and CRAM are gated
   on the same bit, so they still agree) but the §2.2 invariant is vacuous there.
10. **The "static DMA entries are immutable" generalisation is false.** `Render_Sprites` re-patches
    `Static_Sprite_DMA`'s length words from the main loop every frame (`buffers.emp:136-137`,
    `sprites.emp:481`). Nothing structurally prevents the same for a palette line, and the torn-frame
    argument leans on immutability.

---

## What the sweep CONFIRMED — record it so it is not re-derived

- **The snapshot mechanism is sound**, now checked by a third independent seat and not falsified.
  `VInt_Ptr` is only ever `VInt_Level` (`boot.emp:281`, `ojz_scroll_test.emp:267` — the only two
  writers), which **closes** what would otherwise be an open census through a function pointer.
  `Build_DMA_Entry` has exactly two callers and never re-patches `Static_Pal_Line0..3`.
- **No first-frame black**, closed two ways: `Raster_VBlank` re-asserts `prog_mask` into
  `Palette_Dirty` every frame and runs strictly before `Enqueue_Dirty_Buffers` on both paths, and
  IRQ4 cannot nest inside IRQ6; independently, boot clears both Work RAM and CRAM to zero.
- **§4.2's cross-program ship hole is genuinely closed** — `Effects_Offscreen_Entry` is cleared on
  both `Raster_VBlank` install branches before `Enqueue_Dirty_Buffers`, and BUG A's
  clear-first/publish-last fix means a ship pointer cannot outlive its program into a band frame.
- **CLAIM 3 holds**, verified two further ways. F1 396→412 and F5 612→628 are the only tripwires.
- **A band cannot overlap a dense run, by construction** — dense ops are not `RasterOp` variants,
  `raster_gradient_program` takes no op list, and mixing is ruled not-authorable. Coherent by
  refusal, but unstated in the draft.
- **BUG B is FIXED** (chain 128) — `clr.w Raster_Dense_Lines` at `raster.emp:588` in `Raster_VBlank`
  and `:927`. The hardware seat's "band stuck ON after a crossing" symptom read the audit doc, which
  predates the fix, and does not apply.
- `adda.w` sign-extension is safe here (snapshot offsets ≤ 126). §5's 12 match sites confirmed by
  count; zero `RasterOp` references outside `raster_dsl.emp` confirmed by grep.

---

## Where this leaves the parcel

The direction is intact and the mechanism is verified. What is missing is what has been missing
since sweep 1, restated precisely:

**R1 needs a real composition guard, and the narrowing was an attempt to avoid writing one.**

The shape is namable: for the single restore op, refuse any other CRAM-class op in the composed
program whose `[addr, addr + 2*count)` intersects the restore's and whose fire line is strictly
earlier, unless it is the restore's own partner. It needs `op_ship_cram_addr`/`op_ship_count`
generalised to a total `op_cram_span`, and it must key on the address, **not** op class — `Vsram`
is CRAM-class in the dispatcher (`op_dispatch_cyc:852-853`) but `op_mask` 0. **Nobody has proven
this is expressible without an entry-ownership representation. It is a NEW CLAIM and must be
swept.**

Plus, before a v4 is planable:
- the restore's own delay constant and its own landing measurement;
- a ruled fallback for the mixed-fire +16, which now looks more likely to fail than pass;
- a Gate 3 replacement that is not keyed on the snapshot's own source.

**The process note, since this is the third time.** Every sweep so far has minted fixes that the
next draft adopted unswept, and every sweep has then killed them. This adjudication mints four more
(the composition guard, the restore delay constant, the Gate 3 replacement, the dirty-mask
masking). By induction they are the most likely things to be wrong in v4, and they should enter it
labelled as claims, not as rulings.
