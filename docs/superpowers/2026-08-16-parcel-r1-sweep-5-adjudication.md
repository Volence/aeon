# PARCEL R1 — sweep 5 adjudication. CONVERGED. Every kill is a token, a line, or a number.

**Date:** 2026-08-16
**Draft reviewed:** `specs/2026-08-16-parcel-r1-palette-bands-v5.md` @ `576e30e7`
**Seats:** gate vacuity (Sonnet), hardware/timing (Fable), correctness/state (Opus).
**Prior:** sweeps 1-4; sweep 4 was the first with no direction-level kill, this one has no
STRUCTURE-level kill. Two findings arrived pre-replicated from independent seats (the
`op_work_cyc` value, the S/H minimum height) — the second and third instances of the
redundancy the process was rebuilt for.

---

## The one-line state

**The design holds. Four kills, all with single-token/-line/-sentence fixes; twelve
must-fixes, mostly authoring-docs and gate-spelling; a long confirmed list including a
STRONGER invariant than the draft claims.** The parcel is converged: v6 is a consolidation,
not a redesign, and the recommendation at the end is a single-seat verification of the v5→v6
diff instead of a sixth full sweep.

---

## KILL 1 — Rule 6 is one token short: nothing requires the RESTORE'S OWN fire to be static. The moving-BOTTOM band builds clean and corrupts silently.

Correctness seat, witness traced through every guard. Using only public constructors and an
established in-tree spelling (list indexing, precedent `ojz_effects.emp:438`):

```
let B = band(50, 100, on: <pal_region 1w, span S>)
PROG  = [B[0]] ++ patchable([B[1]], ch: 0, lo: 100, hi: 150)
```

`patchable` accepts a one-fire list; the restore fire is not itself marked; `check_intervals`
sees `[49,49]` then `[99,149]` — ascending, disjoint; C-A finds the unique equal-span earlier
partner on a **static** fire, so rule 6 (which constrains only the PARTNER) passes; D-B, §4.1,
§4.3 all pass. At runtime the restore record is patchable `line_src`: above `band_hi` it hits
`.suppress` (`raster.emp:1083`) and is **not emitted** — the ON tint runs to the bottom of the
screen on those frames, silently. Rule 6's own rationale covered the benign half (suppressed
ON → base-over-base, inert) and missed the visible half (suppressed RESTORE → unbounded tint).

**Fix, one ensure:** rule 6 reads "**both** the restore's fire and its partner's fire are
static" (`fire_is_patch == 0` on the restore's carrying fire).

**Same shape, second door:** direct enum construction bypasses constructors — the module's own
comment (`raster_dsl.emp:64-70`) says so — which makes D-C's "one ensure in `reg_set`"
bypassable via `RasterOp.SetReg($8F04)`. Since D-C's call is tree-wide, enforce it where it
cannot be bypassed: a program-level scan `op_reg_word(o) >> 8 == $8F` in `raster_program`
(the helper already exists). The `reg_set` ensure stays as the early, message-bearing layer.

---

## KILL 2 — D-A's breakpoint is one instruction early, and its comparison read is unpinned. The fourth instance of the boundary error class.

Gate seat, grounded in the oracle source itself: breakpoint checks run **before** the stopped
instruction executes (`M68000.cpp:940-943` — `CheckExecution` precedes fetch/decode). Breaking
at `buffers.emp:237` (`move.b Palette_Dirty, d0`) therefore captures whatever `d0` held on
proc entry — an undeclared input, not the mask. The tree's own `raster_source_gate` documents
the correct discipline (probe at I+1 to observe I's effect, `raster_source_gate.py:152-157`);
D-A specified the opposite. **Fix, one line: break at `:238`** (any point before `d0` is next
written).

Second hole, same seat: "run to end-of-frame, paused read of `Palette_Buffer`" is unpinned
against the main loop's own writers — the T15 marker rewrites word 0 **after** the observed
VBlank, and the gate passes today only because that write is idempotent under a frozen camera.
Fixture coincidence, the exact class that killed C-C three times. **Fix: take the payload
comparison read AT the same VBlank stop** (the buffer is frozen for the whole IRQ — CLAIM 1),
not at an unspecified later instant. With both fixes D-A's claim scope ("dirty-gating and copy
extent") becomes true as stated.

Sweep-4's Kill 1 blessed the breakpoint *approach* without checking the breakpoint *address*;
recorded per the standing rule: a minted fix was wrong in the detail nobody swept.

---

## KILL 3 — The delay escalation ladder has an unstated absolute claim: "trailing dots mean the previous step was the answer."

Hardware seat. That sentence is only true if a clean rung exists, and the ladder cannot
guarantee one: the first step is +18 cyc, later steps +10, while the clean-delay window
implied by the tree's only (unmeasured) figure is ~13 cyc wide — **a rung can straddle the
window**, showing leading dots at one step and trailing dots at the next with no clean step
between. The repair that deleted v4's absolute predictions left this one universal behind.
**Fix, one sentence:** the ladder gains a neither-adjacent-rung-clean arm, falling to the
§3.3-named remedy (narrowing the restore's stream count — fewer words, narrower burst).

---

## KILL 4 — `op_work_cyc` for the restore is 64, not 68. Pre-replicated: two seats, two directions, one answer.

The printed derivation "region 122 − 54 spin" subtracts the `dbf` spin but keeps the `moveq`
that exists only to feed it; omitting the delay site removes 58, so no-spin work = **64**.
Hardware seat: 68 contradicts §3.2's settled "omit ≈ −10" and §6.2's own 496/556 figures.
Correctness seat, independently: computing §6.2's row WITH 68 yields 500/560, so the draft is
self-inconsistent and 496 requires 64. Resolution: **64**; §6.2's 496/556 stand; §5's table
row and CLAIM 9's text change. The fifth minima-class arithmetic slip in this parcel —
CLAIM 9's measurement must be compared against the corrected model, and the derivation error
must be fixed BEFORE the measurement or the fixture would "fail" correct hardware.

---

## MUST-FIX, consolidated

1. **`band()` cannot see the S/H band's true minimum height** (pre-replicated, both
   arithmetic seats): with the ON fire's merged `[reg_sh_on, tint]` cost (616) measured
   against the gap to the bot-1 reg fire, an S/H band needs height ≥ **3**; `band()` as
   specified sees a bare tint (506 → 2) and admits a program `check_density` refuses with an
   unpredicted message — sweep 4's must-fix 1 complaint, unrepaired for the flagship shape.
   **Fix: `band(top, bot, on, sh: 0/1)` constructs all the fires (two or three) and computes
   minima from the real merged costs.**
2. **C-D is unwritable as stated under D-F** — the payload has no `entry`. The writable form
   is `stream_cram`'s: `((addr >> 1) & 15) + count <= 16`. And it is NOT a dead belt: it is
   the **CRAM wrap guard** (addr `$7C` + count 3 wraps into line 0, the character's line).
   The constructor also needs `stream_cram`'s line-0 refusal (`(addr >> 5) != 0`), else
   `op_mask` bit 0 forces a per-frame character-palette re-assert — the documented Vsram-arm
   hazard.
3. **§6.3's "14 words, never 16" is false for cram-ON bands**: `Cram` op_size is `4 + len`,
   so a 3-word cram band is 16 words / 41 remainder. Holds for `pal_region` and 1-word cram.
4. **§6.2's CLAIM-9 rider is wrong for the D-D table**: cram/region rows are fixture-pinned
   (F2/F3/F4) and invariant under the append; only the restore-downstream row rides CLAIM 9.
   The minima can freeze earlier than the draft says — except the restore row.
5. **The downstream-gap margin is 8 cyc on the unmeasured constant** (496 vs 488): a −2%
   measurement error flips it to gap 1 (admitting direction). §4.2a's bare "≥2 lines below"
   carries the CLAIM 9 rider explicitly.
6. **The rule-6 poison must use a DISJOINT-span patchable co-tenant** — the obvious same-span
   spelling trips C-A's multiplicity arm first and the poison passes on the wrong message.
   Working spelling recorded in the seat report. Structural fact worth keeping: via `band()`
   the partner is always band()'s own ON op, so rule 6 is reachable through exactly two
   doors (compose-merge onto a patchable line; direct construction).
7. **C-A's same-line arm goes dead once D-B ships** — two fires cannot share a line and D-B
   empties the restore's own fire. Per the module's own "a guard that cannot fire is not
   free" doctrine: keep it, but annotate at the arm that D-B is what makes it unreachable.
8. **Nothing else may compose onto bot-1 either** (the reg fire spends 412 of 488 at gap 1) —
   §4.2a's side-effect statement extends one line up.
9. **D-B refusals are not input-attributable** (compose keeps no provenance); the expect-fail
   lane asserts message text, not attribution.
10. **The expect-fail lane parses the whole tree per run** (`Manifest::scan` is
    unconditional) — "tiny poison module" understates cost; and the expected-message match is
    fragile against wording edits. Both stated as known properties, not defects.
11. **Add `reg_sh_off()`** so the S/H idiom's off-word cannot drift from `reg_sh_on()`'s
    boot-derived base (census-class safety, same as CLAIM 2).
12. **Sec0's band exclusion is doubly determined**: even shipless, `check_intervals` leaves
    no legal interval beside a `[3,220]` channel band. "Excluded while it ships" overstates
    what dropping the ship would buy.

Small corrections ordered with them: the §7.2 profiler note is answerable (per-routine rows
resolve 176-cyc deltas — five-boot spread 0), and `Enqueue_Dirty_Buffers`-as-row is
plausible-not-confirmed (flagged for the implementer, one `--dump` answers it).

---

## CONFIRMED — the load-bearing set, methods stated in the seat reports

- **D-D's table, third independent derivation: all five rows match**, and the 488-exactly row
  is modelled-safe (`<=` admits; the scanline constant is floored from 488.5, slack in the
  safe direction). **`check_density` keys the gap on the UPPER fire** — the S/H idiom as
  spelled (reg at bot-1, restore at bot) BUILDS.
- **Rule 6's narrowing is sound for later-line ops** — `check_intervals` constrains a
  patchable band against a static single-line interval in both orderings, transitively
  disjoint, authored-order ascending; no channel or split-compose spelling straddles. (The
  hole was the restore's own fire — Kill 1 — not the narrowing.)
- **The guard can recover the partner's carrying fire post-compose** (`fire_is_patch` and
  `fire_screen_line` are in scope at the op walk; compose re-wraps patchable merges).
- **D-F's identity mapping holds for all four lines** (`SRC_PAL_LINEn` ↔ `vdp_comm` CRAM
  addresses), and `op_words` derives cmd+addr from one field with the existing `Cram` arm as
  precedent.
- **D-C's census is clean**: zero `reg_set($8F..)` in content; the engine's three `$8F80`
  excursions are IPL-guarded and unreachable by HInt; **$0F is the only stride-affecting
  register in `reg_set`'s admissible range** ($8A already banned, DMA regs inert without a
  CD5 write).
- **Poison semantics are safe for the guard chain**: a failing non-fatal `ensure` discards
  its Poison; data stays intact; the §4.1+rule-6 double violation yields two clean
  diagnostics and a well-defined first-restore choice.
- **One `Enqueue_Dirty_Buffers` hit per frame is architectural** (VInt_Level/VInt_Lag
  mutually exclusive per IRQ6; no other callers).
- **§4.3 is complete against runtime install state too**, not only encoder output — every
  install/teardown path clears `Effects_Offscreen_Entry`; a band program cannot inherit a
  previous program's ship.
- **The invariant is STRONGER than §2.2 states — bank it in v6**: the band's own palette line
  is dirty every frame (`Raster_VBlank` OR before enqueue), enqueued every frame, snapshotted
  every frame, and `Process_DMA_Critical` drains unconditionally — "this frame's payload" is
  always actually delivered this frame. Corollary: D-A's retain-poison assertion can never
  exercise the band's own line in a band-installed fixture; the gate needs a non-program line
  for that half.
- **The §3.2 repair is complete** apart from Kill 3's one sentence: no other absolute landing
  figure survives; the relative deltas all check; F1/F5/dispatch unchanged (inputs unmoved).
- **No sweep-4 finding was adopted unlabelled** (full tag scan; S4-3/S4-4 subsumed by name
  into D-B/D-F).

---

## BLOCKED — carried forward, unchanged in kind

The restore's true `op_work_cyc` (measure with `raster_cost_probe` AFTER Kill 4's correction,
BEFORE the minima freeze); whether the restore body's `lea` and the chain's branches assemble
short-form (the §3.1 listing read); the ~97/~14 landing constants (ungrounded by design now —
the §7.3 captures are the first data).

---

## Where this leaves the parcel — CONVERGED

Five sweeps. The mechanism has survived four, the opcode and arithmetic three, the guard
shape two, and this sweep's worst finding is a missing `fire_is_patch` check. The fix list is
one ensure, one breakpoint address, one sentence, one number, and twelve smaller edits.

**Recommendation:** fold into **v6 as the consolidation draft** (sweep-5-minted fixes
labelled E-A..E-D per the standing rule), then run a **single verification seat on the v5→v6
diff** — checking the fixes were applied as adjudicated and minted nothing new — instead of a
sixth full sweep. Full sweeps have paid for themselves five times; a sixth against a
converged draft would re-verify settled ground at three-seat cost. If the diff seat finds
anything structural, that decision reverses. Then: owner sign-off → writing-plans, with the
plan's first tasks being the two ordered measurements (CLAIM 9 via `raster_cost_probe`, then
the §7.3 captures) before any constructor minima freeze.
