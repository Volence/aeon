# Raster palette bands — ENTRY OWNERSHIP. Design draft r1.

**Date:** 2026-08-28
**Status:** DESIGN ONLY — no engine code written, no bytes moved, nothing built.
**Closes (as a design):** `docs/DEFERRED_WORK.md` "R1 booking: N bands (more than one restore
per program)" and "R1 booking: moving bands (patchable ON and/or OFF edges)". Both bookings
name the same blocker and this document treats them as one.
**Parent spec:** `docs/superpowers/specs/2026-08-16-parcel-r1-palette-bands-v6.md` (R1 v6) —
§1, §4.1, §4.2 (C-A, rule 6/E-A), §4.2a (D-B), §4.2b, §6.1-6.3, §9, §12.
**Tree revision every source claim below was read at:** `5b09649c` (worktree
`agent-a08d92d1ffd17c760`, branch `design/raster-n-bands`, 2026-08-28). Claims about our own
tree age fastest — re-read before trusting one at a later revision.
**Not run, by standing instruction:** no emulator, no build, no sigil. Every cycle figure
below is either transcribed from a constant in the tree (cited) or NOMINAL from the 68000
timing tables (marked). Nothing here is a measurement made by this pass.

---

## 0. The one-paragraph answer

A band is **one authored object that emits two records**, and R1 threw that fact away at
`band()`'s return by flattening into a fire list. Every guard downstream then had to
*reconstruct* the pairing from span equality and fire order, which works when there is
exactly one restore and stops working the moment there are two. The fix is to stop
reconstructing: **carry the band's identity on its ops**, so ownership is *declared* by the
constructor and *checked* by the guard rather than inferred. Once identity is explicit, N
bands is a per-band repeat of the same walk, and a moving band is a pair of records driven
from one latched anchor by a constant offset — which turns out to be exactly lockstep, so the
two edges of a moving band cannot desynchronise even in principle. `.suppress` stops being a
silent drop because a band's records never take it alone: either neither takes it (clamp) or
both do, from a bit-identical predicate on a bit-identical input.

---

## 1. What the two bookings actually share

Both bookings blame "the guards reason in the singular". That diagnosis is correct but it is
one layer above the cause. The cause is visible in three places in the shipped source:

1. **`band()` knows the pairing and discards it.** `raster_dsl.emp:655-714` builds the ON fire
   and the restore fire in one call, deriving the restore's payload from the ON op's own span
   (`pal_restore(sa, sb / 2)`, `:671`). At that instant the pairing is a fact. The return is
   `[f_on, fire(bot, [pal_restore(...)])]` — a plain fire list, in which nothing records that
   these two belong together.
2. **The guard re-derives it.** `raster_dsl.emp:2584-2637` finds "the restore" by scanning for
   the first `op_is_restore`, then finds "its partner" as the unique strictly-earlier op with
   an *exactly equal span*. With one restore this is sound. With two, "the unique
   strictly-earlier equal-span op" names a set, and `isect_earlier == 1` (`:2636`) is a count
   over a union of two bands' candidates.
3. **The runtime has no notion of a pair either.** `Raster_BuildSchedule`
   (`raster.emp:1638-1727`) decides emit-or-suppress **per patch-table entry**, independently.
   `raster.emp:1673`'s `bgt .suppress` removes a record whose latched line is past its band's
   top edge; `.suppress` at `:1721` skips the entry's remaining eight bytes and continues. That
   is a clean, well-formed schedule operation — and it is applied to one half of a pair with no
   knowledge that the other half exists.

Sweep 5's witness is (3) meeting (1): splice `band()`'s restore fire into `patchable(...)`,
every comptime guard passes because none of them can see a pair, and at runtime one record of
the pair is removed while the other survives.

So: **one representation change, in the constructor and the op, fixes the comptime half; one
policy change in the schedule builder fixes the runtime half.** They are separable and I
sequence them separately in §8.

---

## 2. The representation — band identity on the op

### 2.1 Where the tag must live: on the OP, not the fire

`compose()` (`raster_dsl.emp:489-562`) **rebuilds every merged fire**. Its own note says so at
`:484-488`: "a mark carried only in the input variant is lost by construction — exhaustive
matching cannot catch it, because the loss is in reconstruction, not destructuring". That is
why `patchable`'s channel/band had to be explicitly re-carried at `:557`.

Ops, by contrast, survive compose **verbatim**: `ops = ops ++ [o]` at `:537` and `:546` copies
the op value with no reconstruction. A tag on the op therefore travels through composition for
free and cannot be dropped by a future merge rule. A tag on the fire would have to be
re-carried by hand in `compose`, exactly like `p_ch`/`p_lo`/`p_hi`/`p_sh` — four fields that
are already a maintenance hazard and that `compose`'s guard 9 exists to police.

**Decision: the band id is a payload field on the CRAM-span op variants.**

```
pub comptime enum RasterOp {
    SetReg(int),
    Cram(int, array, int),                     // + band id  (0 = not part of a band)
    PalRegion(int, int, int, int, int, int),   // + band id
    Vsram(int, array),                         // unchanged — VSRAM has no CRAM span
    PalRestore(int, int, int),                 // + band id  (never 0)
}
```

This is a large mechanical diff — three variants across the ~14 match sites the parent spec
enumerates in §5 — and it is worth it for one reason: **the tag and the span are then in one
payload**, so the two facts a band's correctness depends on cannot drift apart, and `op_words`
simply does not emit the tag. Zero wire bytes, zero ROM.

Two alternatives were considered and rejected:

- **A wrapper variant `Owned(int, RasterOp)`.** Rejected: every `op_*` total would have to
  recurse, and the module's own note at `:94-102` credits *exhaustive, non-recursive* match
  arms with catching the `op_mask` trap. A wrapper reintroduces the shared-`if` shape that note
  argues against.
- **A side table of band descriptors passed alongside `fires` into `raster_program`.**
  Rejected: it survives `compose` only if `compose` learns to merge two side tables, and it
  identifies a band by line — which stops being an identity the moment the lines move.

### 2.2 The id itself — derived, never authored

The id must be unique per band and stable under composition. It is **not** an author
parameter, because a hand-authored id is one more number two bands can accidentally share.

```
id = top * 128 + sa          // ON fire's authored screen line, CRAM byte start address
```

- `top` is 3..223 (`fire`'s bound, `raster_dsl.emp:326`) and `sa` is 0..126 (`pal_restore`'s
  bound, `:306`), so the pair packs without collision.
- Uniqueness is **structural, not hoped for**: two bands sharing an id would have to share both
  an ON line and a start address, and the ownership walk (§3) refuses that independently, with
  a sentence, before the id ever matters. The id-uniqueness `ensure` is therefore a
  *corroborating* check, not the load-bearing one.
- `band()` computes it. Authors never see it. It appears only in diagnostics, where it prints
  as "the band opening at line {top} on entry {sa >> 1}".

> **Do not read this as "the ON line is the identity".** It is not: `compose` can merge two
> bands' ON ops onto the same line (two tints starting at 60 over different entries), which is
> legal and must stay legal. `top` alone collides there; `top` with `sa` does not.

---

## 3. THE OWNERSHIP RULE

### 3.1 What ownership means

A `pal_restore` streams **this frame's base-DMA payload** back to CRAM (R1 v6 §2.2). It is a
blunt instrument: it writes *base*, not "this band's contribution removed". So a restore at
line R over span S is correct if and only if, for every CRAM entry `e` in S:

> the value live on `e` immediately above the band's ON line is **base**, and nothing other
> than the band's own ON op writes `e` between the ON line and R.

That is the whole semantic content of C-A, said without the word "partner". It generalises to
N bands with no change, and it is checkable per entry.

### 3.2 The rule, as a walk

**RULE OWN-1 — per-entry timeline.** For each CRAM entry `e` (0..63), walk the program's
records in **program order**, and within a record its ops in **list order**, visiting only ops
whose CRAM span covers `e`. Maintain two comptime scalars:

| state | meaning |
|---|---|
| `holds_base` | 1 iff `e` currently holds this frame's base-DMA value |
| `open` | the id of the band currently live on `e`, or 0 |

| op visited | rule |
|---|---|
| ON op of band B (`band_id != 0`, not a restore) | refuse if `open != 0` (two bands live on one entry); refuse if `holds_base == 0` (the restore below would restore base over a non-base value — the bury); then `open = B`, `holds_base = 0` |
| restore of band B | refuse if `open != B` (an unpaired restore, or one closing a band it does not own); then `open = 0`, `holds_base = 1` |
| any op with `band_id == 0` | refuse if `open != 0` (a third-party write inside a live band gets buried by the pending restore); then `holds_base = 0` |

At the end of the entry's walk: refuse if `open != 0` (a band whose restore never covers this
entry — see OWN-2).

**RULE OWN-2 — span integrity.** Each id appears on exactly two ops: one non-restore ON and one
restore. Their `op_cram_span`s are **equal**. `band()` guarantees this by construction
(`:660, :671`) and the guard re-checks it, so a hand-built `RasterOp.PalRestore(a, n, id)` with
a mismatched span is refused rather than trusted — the same "constructor-only refusals are not
refusals" doctrine the `$8F`/`$8A` scan is built on (`raster_dsl.emp:2531-2555`).

**RULE OWN-3 — order.** The ON record must precede the restore record in program order.

That is the entire ownership rule. There is **no inference anywhere in it.**

### 3.3 Why this is strictly better than C-A, case by case

| case | C-A today | OWN-1 |
|---|---|---|
| restore with no ON op | refused (`isect_earlier == 0`) | refused: `open != B` at the restore |
| one earlier equal-span partner | admitted | admitted |
| two earlier intersecting ops | refused (count 2) | refused: the second clears `holds_base`, the ON's base test fires |
| op on the restore's own line | refused (redundant with D-B) | D-B unchanged; OWN-1 also sees it as a third-party write inside the band |
| **two bands, disjoint spans** | **refused** (`restore_n <= 1`) | **admitted** — separate entries, separate walks |
| **two bands sequential over the SAME span** (40-60, then 80-100) | **refused** | **admitted** — the first restore restores base, so `holds_base` is 1 again when the second ON opens |
| two bands *nested* over the same span | refused | refused: `open != 0` at the inner ON |
| unbanded write above a band, same entry | refused | refused, with a better sentence (see below) |

The last row is where the new rule earns its keep as *documentation*: today's message says the
op "is not its equal-span partner", which describes the guard. OWN-1 can say the true thing —
*"entry 5 was last written at screen line 40 by an op that is not part of a band; the restore
at line 100 streams this frame's BASE palette, so from line 100 down entry 5 reverts to base
rather than to the line-40 value."*

### 3.4 What OWN-1 does NOT rule out — stated because a guard's silence is a claim

- Nothing about VSRAM or register ops. `op_cram_span` is `(-1, 0)` for both
  (`raster_dsl.emp:1515, 1518`) and they are invisible to this walk, correctly.
- Nothing about **runtime** palette content: `fx_tint_band`'s unbound-variant hazard
  (`:615-619`) is a runtime binding and stays booked.
- Nothing about landing, density, or budget — `check_landings`, `check_density`,
  `check_hint_total` are untouched and still own those.
- Nothing about whether the band is *visible*. A band over entries the art never uses passes.

### 3.5 `.emp` spelling constraints this walk must respect

Read from `docs/EMP_PITFALLS.md` and the module's own notes at revision `5b09649c`:

- **No index assignment.** `raster_dsl.emp:2511-2517` records that sigil's `Assign` target is a
  bare path with no indexing form, which is why `prog_mask` and guard 11 accumulate into
  scalars. The walk therefore uses `for e in 0..64 { comptime var open = 0 ... }` — per-entry
  scalars inside a literal range loop, exactly `compose`'s `for line in 3..224` shape
  (`:501`). No arrays are written.
- **No `break`/`continue`** (R1 v6 §11). The walk runs to completion on every entry.
- **`ensure` is non-aborting** (Poison). A violated walk continues with nonsense state and would
  emit a cascade. Countermeasure, following `band()`'s own precedent at `:663-664` ("inert on
  the refused path … measured 6 -> 1"): carry a per-entry `poisoned` flag, set it at the first
  refusal on that entry, and gate every later `ensure` in that entry's walk on
  `poisoned == 0`. **One sentence per entry, maximum.**
- **No nested if-expressions** (pitfall 1). The walk is statement-`if` only, accumulating into
  scalars — the shape pitfall 1 prescribes.
- **Free names resolve at the call site** (pitfall 2). The walk lives inside `raster_program`,
  which is `pub comptime fn` in a `COMPTIME_HELPERS` module, so it may name only
  module-defined names and literals — `64`, `0`, `1`. No imported constants. Same discipline
  as every other guard in the file.

---

## 4. `.suppress` — designed out, not guarded against

### 4.1 What it does today, and why the asymmetry exists

`Raster_BuildSchedule`, `raster.emp:1666-1678`:

```
move.w  (a2, d2.w), d2      // Effects_Screen_L[ch] — the LATCHED screen line; may be negative
subq.w  #1, d2              // -> fire line
cmp.w   2(a0), d2           // band_hi_fl
bgt     .suppress           // past the band it can reach: REMOVE the record
cmp.w   (a0), d2            // band_lo_fl
bge     .have_line
move.w  (a0), d2            // clamp UP — the frame-top ship covers what is above
```

The two edges are treated differently on purpose. Above the band, the record clamps and the
off-screen ship covers the rest (`raster.emp:1841-1845`). Below the band, the record is
**removed** — which is the right semantics for the effect this was built for: a region
*boundary* whose anchor has left the bottom of its range means "no boundary on screen", and
the correct rendering is that the swap does not happen at all.

For a band's OFF edge that semantics is exactly inverted: "the OFF edge is off the bottom of
its range" must never mean "there is no OFF edge".

### 4.2 The design rule

> **RULE SUP-1. A record carrying a band op is never suppressed alone. Suppression is a
> property of the BAND, and both spellings of it are total: either no member is suppressed
> (`CLAMP`), or every member is (`PAIR`), decided from one predicate on one input.**

Two policy bits per patchable record, one per edge, and **0 means today's behaviour** so
existing content encodes identically:

| bit | 0 (default) | 1 |
|---|---|---|
| `HI_CLAMP` | suppress when the latched line is past `band_hi` — today | clamp DOWN to `band_hi` |
| `LO_SUPPRESS` | clamp UP to `band_lo` — today | suppress when the latched line is above `band_lo` |

A band's records must all declare the **same** pair of bits (comptime-checked). The two useful
combinations:

- **`CLAMP` (`HI_CLAMP=1, LO_SUPPRESS=0`)** — recommended default for bands. The band never
  disappears; it pins its bottom at `band_hi` and its top at `band_lo`. The failure mode is
  *visible and authorable* (the band stops following), never silent.
- **`PAIR` (`HI_CLAMP=0, LO_SUPPRESS=1`)** — the band vanishes entirely when its anchor leaves
  the travel range at either end. Correct for a fog slab that scrolls off screen.

### 4.3 Why a PAIR suppression cannot be partial — the lockstep theorem

This is the load-bearing argument and it is worth writing as arithmetic, because it is what
replaces "the guards reason in the singular".

Let the ON record be patchable on channel `c` with band `[lo, hi]` and bias 0. Let the OFF
record be patchable on the **same channel `c`** with band `[lo+H, hi+H]` and bias `H`, where
`H = bot - top` is the authored band height. Let `x` be the latched fire line
`Effects_Screen_L[c] - 1`, computed **once per frame** by `Effects_LatchWorldLines`
(`raster.emp:1847-1858` — its whole reason for existing is that all consumers read one
derivation).

The builder computes each record's line as `clamp(x + bias, lo_fl, hi_fl)`:

- ON: `clamp(x, lo-1, hi-1)`
- OFF: `clamp(x + H, lo+H-1, hi+H-1)` = `clamp(x, lo-1, hi-1) + H`

**The two are algebraically identical up to the constant `H`.** Consequences, all exact:

1. **The gap between the two records is exactly `H` on every frame, at every anchor value,
   including both clamped regimes.** They cannot invert. They cannot converge. They cannot
   drift.
2. **The suppression predicates are the same predicate.** `x + H > hi+H-1` ⟺ `x > hi-1`, and
   `x + H < lo+H-1` ⟺ `x < lo-1`. Both records evaluate identical booleans from identical
   inputs, so under `PAIR` they suppress together or not at all — **not by coordination, but
   because there is nothing to coordinate.**
3. **Under `CLAMP` neither is ever suppressed**, so sweep 5's failure mode is not merely
   guarded — it is arithmetically unreachable.

For the `sh: 1` shape the de-mix `reg_sh_off` fire at `bot-1` is a **third** member of the same
rigid group, bias `H-1`, band `[lo+H-1, hi+H-1]`. The identical algebra applies; a rigid group
is 2 or 3 records, never more.

### 4.4 What the bias costs, and where it lives

The patch-table entry is five words today
(`[line_src][band_lo_fl][band_hi_fl][rec_off][rec_len]`, `raster_dsl.emp:2745-2776`). Two
spellings for the new fields:

| | pack into `line_src` | a sixth table word |
|---|---|---|
| ROM | **0 bytes** — `line_src` is `$8000\|ch` with `ch < 4` (`raster.emp:1671` masks with `RASTER_MAX_PATCH-1` = 3), so bits 2..14 are free | +2 bytes per record (~+8 bytes for OJZ section 0) |
| existing images | **byte-identical** (defaults are all-zero bits) | change; needs the routine repin |
| VBlank cycles / patchable record | ~+30 NOMINAL (extract, mask, add) | ~+8 NOMINAL (`add.w (a0)+, d2`) |
| `Raster_GetChannelBand` | must mask before its exact-equality `cmp.w` (`raster.emp:1787, 1795`) | must widen its `addq.l #8` skip (`:1797`) |

Both spellings touch `Raster_GetChannelBand`, so that is not a discriminator.
**Recommendation: the sixth word**, because the scarce resource here is VBlank cycles
(`Raster_BuildSchedule` runs every VBlank and walks every record) and 8 bytes of ROM is not
scarce. The byte-identity property is not lost by this choice, because **parcels P1/P2a/P2b
below need no table change at all** and P3 is a byte-changing parcel that takes the ordinary
repin ritual. Both figures are NOMINAL; §7 says what to measure.

### 4.5 The residual, stated rather than hidden

- **A `CLAMP` band whose top edge scrolls off the screen pins its top at `band_lo`.** With
  `lo = 3` (the minimum `patchable` admits, `:431`) that is the top of the visible area minus
  the three rows the priming records own (`fire`'s bound, `:326`). Visible, small, stated.
- **A band cannot use the off-screen ship.** CLAIM 6 (`raster_dsl.emp:2674-2677`) refuses a
  band in a program with any `offscreen_ship` fire, for a reason that does not change here: on
  a shipping frame CRAM holds variant colours while `Palette_Ship_Snap` holds base. Unchanged.
- **`.suppress` itself stays**, and stays reachable — every existing `patchable` record uses it
  with default bits, and a `PAIR` band uses it deliberately. What changes is that reaching it
  is no longer possible for one member of a group alone.

---

## 5. The invariant the whole thing rests on, named

C-A's grounding today is a reference to an implementation: "sound ONLY because
`check_intervals` forces strictly ascending disjoint band intervals … *Falsifier: any
relaxation of `check_intervals` silently voids this guard*" (`raster_dsl.emp:2579-2583`). This
design **does** relax `check_intervals`, so that falsifier has to be discharged head-on rather
than stepped around.

> **INVARIANT ORD-1.** For any two records r1, r2 with r1 before r2 in program order, every
> line r1 can reach at runtime is strictly above every line r2 can reach.

ORD-1 is the property OWN-1 needs (its walk is in program order and reasons about "above").
`check_intervals` is one *proof* of ORD-1, not ORD-1 itself. The relaxation:

> **RULE INT-1.** For a rigid group (§4.3), `check_intervals` skips the internal comparisons
> between the group's members and tests the group's **envelope** `[lo_fl(first),
> hi_fl(last)]` against its neighbours. ORD-1 holds *within* the group by §4.3's lockstep
> theorem (the members are exactly `H` and `H-1` apart on every frame) and *outside* it by the
> envelope test, which is the ordinary check.

This matters concretely and is not a technicality. Without INT-1, the naive interval test
requires `lo+H > hi`, i.e. **`H > hi - lo`: the band must be taller than its travel range.**
OJZ channel 0 is banded `3..120` (`raster.emp:1738`, the note at `Raster_GetChannelBand`), a
travel of 117 lines — so without INT-1 no useful moving band exists on that anchor at all.
With INT-1 the height is bounded only by the density minima, which for a 1-colour
`pal_region` tint is 2 (R1 v6 §6.2).

Consequently:

> **RULE DEN-1.** Between the members of a rigid group, `check_density`'s gap is **exactly
> `H`** (and `H-1` to the de-mix fire), not the worst-case band-edge difference. Same
> derivation, same theorem. This is the arithmetic `band()` already performs for static bands
> (`raster_dsl.emp:669-670, 704-705`); INT-1/DEN-1 make it apply unchanged to the moving case.

**Falsifier for ORD-1, replacing C-A's:** *any code path that computes a group member's line
from anything other than the group's single latched anchor plus its constant bias.* That is a
sharper falsifier than "a relaxation of `check_intervals`", because it names the mechanism
rather than the guard.

**Standing warning honoured:** `check_intervals`' own comment (`:2289-2296`) says "do NOT
weaken this guard ad hoc" and points at the banked runtime-resolution design. INT-1 is not
that weakening: it does not admit two *independent* patchable records into overlapping
intervals. Two rigid groups that overlap each other are still refused, and that case remains
`docs/superpowers/specs/2026-08-17-effects-tail-design-v3.md`'s (r3.1, revival-ready).

---

## 6. Guard 11 and the parallax overlay

GUARD 11 (`raster_dsl.emp:2505-2530`) refuses two patchable records on one channel, because
`Raster_GetChannelBand` answers with the **first** match and the overlay would follow one
record while the palette followed the other.

A rigid group is 2-3 patchable records on one channel, so GUARD 11 must be relaxed to *one
rigid group per channel* (a lone `patchable` record is a group of one). The hazard GUARD 11
names does not apply, and for a reason worth stating rather than asserting: the overlay wants
**the boundary**, and a band's boundary is its top edge. The first table match in program order
is the group's ON record. So first-match is not "arbitrary but tolerable" — it is correct by
construction.

**Open call, flagged rather than decided (§10, Q3):** if a future scroll effect wants to track
a band's *bottom* edge, `Raster_GetChannelBand` needs to say which edge it is reporting. Do not
solve that speculatively.

---

## 7. Cost, honestly

### 7.1 ROM, per program

- **Band identity: 0 bytes.** The id is a comptime payload field; `op_words`
  (`raster_dsl.emp:1356`) does not emit it and `op_size` (`:1409`) does not count it.
- **The ownership walk: 0 bytes.** Comptime only.
- **A band's wire cost is 16 words**, and this is a CORRECTION to the parent spec. R1 v6 §5
  gives `op_size` 5 for the restore and §6.3 prices a band at 14 words; both predate substrate
  item 1, which moved the solved spin into the program. At `5b09649c` the shipped
  `op_size` (`raster_dsl.emp:1409-1419`) reads `PalRegion => 6` and `PalRestore => 6`, with
  `op_words` (`:1356-1383`) emitting the matching `[op][cmd hi][cmd lo][SPIN][count-1][…]`.
  So the ON record is `2 + 6 = 8` words and the restore record is `2 + 6 = 8`.

  | shape | words |
  |---|---|
  | `band(sh: 0)`, `pal_region` or 1-word `cram` ON | **16** |
  | `band(sh: 0)`, 3-word `cram` ON | 18 |
  | `band(sh: 1)` (ON+reg merged, de-mix fire, restore) | **22** |

  Against `raster_words`' fixed 7 words (`:2428`) and the 64-word ceiling enforced at `:2706`:

  | bands | words | free |
  |---|---|---|
  | 1 | 23 | 41 |
  | 2 | 39 | 25 |
  | 3 | 55 | 9 |
  | 4 | **71 — REFUSED** | — |

  > **N is capped at THREE, not four.** Three bands leave 9 words: enough for a `reg_set` fire
  > (4 words) or a 1-word `vsram` fire (8), not for a fourth band. Two bands leave 25, which is
  > comfortable. **The program buffer, not the HInt budget, is what caps N.**
  >
  > Derived here from the shipped `op_size` and the `out.len * 2 <= 128` ensure, *not* copied
  > from §6.3 — which is exactly how the stale 14 was caught. Anyone re-deriving this after a
  > wire-format change must go back to `op_size`, never to this table.
- **The patch table (P3 only): +2 bytes per record** for the bias word, ~8 bytes for OJZ
  section 0.

### 7.2 RAM

**Zero, in both halves.** `Palette_Ship_Snap` is already 128 bytes covering all four palette
lines (R1 v6 §7.1), so N bands share it with no growth. The moving half adds no RAM either:
`Effects_World_Y` / `Effects_Screen_L` are `[u16; 4]` each (`engine/ram.emp:471`) and **a rigid
group consumes ONE channel, not two or three** — that is what the bias buys.

`RASTER_MAX_PATCH = 4` (`raster_dsl.emp:1989`) would allow four moving bands, but the 64-word
program buffer caps N at **three** (§7.1) — so the buffer is the binding limit and the channel
count has one slot to spare for an ordinary `patchable` record beside three bands.

### 7.3 Per-frame cycles

| site | delta | status |
|---|---|---|
| `Raster_HInt` (the raster budget) | **0** for the mechanism. A second band's *fires* cost what R1 already prices them at | model, see below |
| `Raster_BuildSchedule`, in-band path | **0** — `bgt .suppress` becomes `ble .lo_test`, same instruction class | NOMINAL |
| `Raster_BuildSchedule`, per patchable record | **~+8** (`add.w (a0)+, d2` for the bias) | NOMINAL, 68000 tables |
| `Raster_BuildSchedule`, out-of-band frames only | **~+18** (the policy `btst` + branch) | NOMINAL |
| `Raster_GetChannelBand`, per table entry | **~+8** (widened skip) | NOMINAL |

**These are nominal and I did not measure them, by instruction.** The repo's standing rule is
that cycle claims *near VDP ports* are measured; none of these sites touch a VDP port —
`Raster_BuildSchedule` writes only the inactive RAM buffer, which is exactly why it can be
built in VBlank at all. That makes the nominal figures defensible *for these sites*. It does
not make them measured. See §7.5.

**The raster budget (axis 4b).** `check_hint_total` (`:2489-2497`) charges summed
`fire_cost_cycles` against `RASTER_HINT_FRAME_CYC - RASTER_HINT_RESERVATION_CYC = 84,595`
model cycles (`:2477-2487`). Transcribing R1 v6 §6.2's own figures: a 1-word `pal_region` ON
fire is 506 model cycles and the restore fire is 496 at `op_work_cyc = 64`, so a band is
**~1,002 model cyc/frame**; the buffer's maximum of three bands ≈ **3,006 cyc ≈ 3.6 % of the
axis-4b budget**. For scale the whole shipped OJZ section-0 sparse program is 1,878 measured
cyc/frame (`:2483-2485`).

> **The restore side of that number rides CLAIM 9, which R1 v6 §12 still marks UNVERIFIED**
> (`op_work_cyc == 64`, "measure FIRST, before minima freeze"). Every band-height minimum in
> `band()` is cost-keyed to it (`:669, :704`). N bands multiplies an unmeasured constant by N.
> **This is the single most important number to measure before any band parcel freezes**, and
> it is the same measurement R1 already ordered first and — as of `5b09649c` — the tree still
> records as unverified.

**Conclusion on cost: bands are not budget-limited. They are buffer-limited (64 words) and
density-limited (minimum heights).** Say that to Aurora in those terms.

### 7.4 Build time

The ownership walk is `64 entries × ops-in-program`. A program is at most 64 words, so at most
~20 ops; the ceiling is ~1,280 inner steps per `raster_program` call, per call site in the tree.
**UNMEASURED.** It could be trimmed to only entries some band touches (≤ 3 per band), but that
needs a mask accumulation and the tree's own `m = m | bit` idiom, and the trim should only be
made if a measurement says it is needed.

### 7.5 What to measure, and how — TAG for the controller (I cannot run the emulator)

1. **CLAIM 9, the restore's `op_work_cyc`.** `tools/raster_cost_probe` against the shipped
   single-band fixture. Everything in §7.3's HInt column and every band minimum rides it.
   *This is a pre-existing R1 debt, not one this design creates.*
2. **A second restore's pixel landing.** The R1 §7.3 protocol verbatim — pinned camera, reset
   first, 8-px buckets, `docs/benchmarks/` — applied to the *second* band's OFF edge in a
   two-band fixture. The solver re-derives the spin from the op's own position
   (`raster_dsl.emp:1106-1198`), so **nothing is hand-tuned and nothing may be**; what is being
   measured is whether the solved spin lands, which is the same question §7.3 asked once.
   Reading ladder: R1 v6 §3.2's complete ladder including the straddle arm.
3. **`Raster_BuildSchedule`'s per-frame cost, before and after the bias word.** Oracle
   per-routine profiler row for `Raster_BuildSchedule`, five boots, spread 0, at a fixed camera.
   Confirm the row exists with `raster_cost_probe --dump` before relying on it — R1 v6 §7.2
   records that `Enqueue_Dirty_Buffers`' row was "plausible" and had to be confirmed.
4. **A moving band's OFF edge DURING MOTION.** An at-rest capture cannot see a desync; the
   lockstep theorem predicts zero drift and the capture must be able to falsify it. Camera in
   motion, the anchor swept across both clamp regimes and through both band edges.
5. **Build-time delta of the ownership walk** (§7.4): wall-clock `sigil build` on a 4-band
   fixture versus master, same machine, with a concurrent-load note beside the timing.

---

## 8. Sequencing — and a correction to the brief

The brief asks which of the two capabilities lands first and whether N bands gates moving
bands. **It does not. A moving band is the N=1 case.** Both bookings say the blocker is the
same representation, and they are right; neither is a prerequisite for the other. But there is
a natural ladder, and three of its four rungs are zero-runtime:

| parcel | content | runtime change | ROM delta | unlocks |
|---|---|---|---|---|
| **P1** | band identity (§2) + OWN-1/2/3 (§3) replacing C-A; `restore_n <= 1` still in force | none | **0 bytes; existing images byte-identical** | nothing user-visible — it is the representation |
| **P2a** | delete the `restore_n <= 1` refusal and the `if restore_n == 1` gate | none | 0 | **N BANDS** |
| **P2b** | relax rule 6 half 2 (patchable *partner*) | none | 0 | **moving TOP with a static bottom** |
| **P3** | bias word, policy bits, SUP-1, INT-1, DEN-1, GUARD-11 relaxation | `Raster_BuildSchedule`, `Raster_GetChannelBand`, `patch_table` | +2 B/record | **fully moving bands, both edges** |

**P1 must land first**, and not because of dependency ordering — because it is the only parcel
that can be gated with **zero bytes changed**. Its expect-fail lane proves the walk fires on
five poisons and its whole-image pin proves every shipped program is byte-identical. A
representation change that provably moves no byte is the cheapest thing in this ladder to
trust, and everything else is built on it.

**P2b is nearly free and worth calling out separately.** R1 v6 §4.2 itself classifies a
suppressed ON as *"benign, base-over-base"* — the measured failure sweep 5 found was the
suppressed **restore**, not the suppressed partner. Rule 6 half 2 is therefore a *precautionary*
refusal, and with OWN-1 in place plus `check_intervals` proving ORD-1 (the ON's `hi_fl` is
strictly below the static restore's line), a moving-top / static-bottom band is sound with **no
runtime change at all**. It is the cheapest real capability in this document.

> **Contradicting the brief on one point:** it frames these as "two capabilities". They are
> four, and the two cheap middle ones — N bands and moving-top — are each a guard deletion
> after P1. Only the fourth needs the runtime.

---

## 9. Gates, and what a green rules out

Per `GATE-VACUITY` (`docs/DEFERRED_WORK.md:12043-12063`) each gate states what a green rules
out and names the poison that proves it fires.

### G1 — the ownership walk (expect-fail lane, `sigil` exit code + message)

**A green rules out:** for every CRAM entry any band touches, in every program in the tree —
an unpaired restore; a restore closing a band it does not own; two bands live on one entry;
a non-band write buried by a pending restore; a restore restoring base over a non-base value;
a band whose restore does not cover every entry its ON op writes.
**A green does NOT rule out:** anything about landing, density, budget, VSRAM, registers, or
runtime palette binding (§3.4).

**Vacuity trap, named because it is the obvious one:** the walk visits nothing in a program
with no bands, so a tree with zero bands passes it perfectly. The poison set must therefore
contain bands:

| poison module | expected refusal |
|---|---|
| restore with no ON of that id | "restore of band … with no ON above it" |
| two bands nested on one entry | "two bands live on entry …" |
| an unbanded `stream_cram` between an ON and its restore | the bury sentence |
| an unbanded `stream_cram` above an ON, same entry | the base sentence |
| `RasterOp.PalRestore(a, n, id)` hand-built with a span ≠ its ON's | OWN-2 |

Plus a **positive fixture that must BUILD**: a two-band program with disjoint spans and a
two-band program sharing one span sequentially. Without the positive fixture, a walk that
refuses everything also passes the expect-fail lane. Per R1 v6 §10.4 the lane asserts *both*
nonzero exit and the expected message, and attributes a failure to message wording first.

### G2 — rigid-group linkage (comptime)

**A green rules out:** a group whose members disagree about channel, policy bits, or whose
biases and bands are not offset by exactly `H`.
**A green does NOT rule out that the runtime applies the bias** — that is G3's job. Saying so
in the guard's own comment is the point.
**Poison:** `band_moving` hand-split into two `patchable(...)` calls, which is sweep 5's
spelling generalised.

### G3 — the bias reaches the schedule (`raster_source` gate arm)

**A green rules out:** that `Raster_BuildSchedule` computes the OFF record's line as anything
other than the ON record's clamped line plus `H`.
**Method, applying E-B's lesson verbatim (R1 v6 §10.3):** breakpoint at the instruction
**AFTER** the bias add — oracle checks breakpoints *before* execution — and read `d2` at that
same stop. `deterministic=False`, exact stop PC, mangled local label, own offset arithmetic:
the `raster_source_gate` discipline the tree already documents.
**Vacuity trap, and it is the important one:** a reading taken with the anchor inside the band
never enters the clamp arms, so the gate would be green on the arm that matters least. **The
gate must sample at three anchor values — inside the band, above `lo`, below `hi` — and assert
the clamp arm was entered at two of them.** A hit count on the clamp path is the positive
control; a pass count is not a witness.
**Poison:** force the fixture's bias word to 0 and require red.

### G4 — no partial group suppression (the gate that would have caught sweep 5)

**A green rules out:** that any member of a rigid group reached `.suppress` while another
member of the same group did not.
**Method:** breakpoint hit counts at `.suppress` and at `.have_line`, per record, over a sweep
of the anchor across both edges, on two fixtures — one `CLAMP` band (expected `.suppress`
count for its records: exactly 0) and one `PAIR` band (expected: every member, on the same
frames).
**Vacuity trap:** if the anchor never leaves the travel range, `.suppress` is never reached and
the count is 0 for the wrong reason. **The gate must first assert that the out-of-band regime
was entered at all** — a nonzero hit count on the clamp path (CLAMP fixture) or on `.suppress`
(PAIR fixture). Without that assertion this gate is vacuous by construction, and it is the one
gate in this design whose vacuity would restore the exact bug it exists to prevent.

### G5 — byte-identity for P1/P2a/P2b

**A green rules out:** that a pure-comptime parcel moved a byte. The `first_mismatch(
patched_program(...), hand_twin)` whole-image pin already exists (`raster.emp:1560`);
P1's claim is that it and the ROM CRC are both unchanged.
**A green does NOT rule out** that the walk is doing anything at all — G1's poisons are what
prove that. The two gates are complementary and neither substitutes for the other.

---

## 10. What Aurora would author

Written for someone who is not going to read `raster_dsl.emp`.

**Today.** One band per raster program: an effect that turns on at a screen line and off again
at a lower one, over at most 3 palette colours. Both lines are fixed at build time. If the
band needs to move with the world, it cannot be a band.

**After P1/P2a.** *Up to three bands per program*, each with its own two lines and its own
colours, authored exactly as today:

```
compose([ band(top: 40,  bot: 96,  on: <a tint>, sh: 0),
          band(top: 120, bot: 180, on: <another tint>, sh: 0) ])
```

The four numbers Aurora has to respect, all build-time errors with sentences if broken:

1. **Height.** A 1-colour tint band needs `bot - top >= 2`; its Shadow/Highlight form needs 3.
   (R1 v6 §6.2 — unchanged by this design.)
2. **Count.** Three bands is the ceiling — a band is 16 program words against a 64-word buffer
   with 7 fixed (§7.1). Three bands leave room for one register-only fire and nothing more;
   two bands leave comfortable room for another effect.
3. **Colours.** At most 3 CRAM entries per band, never on palette line 0.
4. **Sharing colours.** Two bands may use the same colours **only if they do not overlap
   vertically**. Two bands at different heights over the same colours: fine. One inside the
   other over the same colours: refused, and the message says which entry and which two bands.
   Different colours: overlap freely.

**After P2b.** A band whose **top edge follows a world anchor** and whose bottom is fixed —
"tint everything between the water line and screen bottom, and stop tinting at line 180". No
new call: `patchable` applied to the ON half.

**After P3.** A band that **moves as a unit**:

```
band_moving(top: 40, bot: 96, on: <a tint>, sh: 0,
            ch: 1, lo: 3, hi: 190, policy: CLAMP)
```

- `ch` is a world-anchor channel (0..3), moved at runtime by `Effects_SetWorldY`. **One channel
  per moving band**, not one per edge — the two edges are driven from a single anchor and are
  rigidly 56 lines apart here, always.
- `lo`/`hi` are how far the band's **top** may travel. The bottom's range follows automatically.
- `policy` is required, with no default (following `region_boundary`'s `sh` precedent — whether
  an effect vanishes or pins is worth stating at the call site):
  - `CLAMP` — when the anchor runs past either end of the travel range, the band **pins** at
    that end and stays visible.
  - `PAIR` — when the anchor runs past either end, the band **disappears completely**.
- The height is rigid. A band that must change height while moving is **two anchors**, is not a
  rigid group, and is refused; that case belongs to the banked effects-tail design
  (`2026-08-17-effects-tail-design-v3.md`).
- A moving band cannot also be a shipped/off-screen-covered effect (§4.5).

**What Aurora will notice as a limit and should be told up front:** a moving band's top edge
pins at line `lo` rather than sliding off the top of the screen under `CLAMP`, because a band
cannot use the off-screen ship. Author `lo: 3` if the band should reach as near the top as the
raster tier can go.

---

## 11. Open questions

1. **Which edge does the parallax overlay follow?** (§6) `Raster_GetChannelBand` returns the
   first table match, which for a rigid group is the ON record — right for a band, since the
   boundary is the top edge. If a scroll effect ever wants the bottom edge, the proc needs to
   say which edge it reports. **Not solved here, deliberately.** Owner call when a consumer
   exists.
2. **Pack the bias, or grow the table?** (§4.4) I recommend the sixth word on a NOMINAL cycle
   argument. Measurement 3 in §7.5 settles it. If the measured `Raster_BuildSchedule` row has
   no headroom concern at all, packing is strictly better (zero ROM, byte-identical images).
3. **CLAIM 9 is still unverified at `5b09649c`** and every band minimum rides it. This design
   does not create that debt but N bands multiplies it by N. Should P2a be gated on measurement
   1, or is the existing single-band evidence enough to admit a second band at the same shape?
   My recommendation: gate P2a on measurement 1, because the minima freeze is what P2a makes
   load-bearing for three bands instead of one.
4. **Should the ownership walk be trimmed to touched entries?** (§7.4) Only if measurement 5
   says the 64-entry sweep costs real build time. Do not pre-optimise a comptime loop.
5. **Is `PAIR` at the `lo` edge ever wanted?** The `LO_SUPPRESS` bit is new runtime code (a
   branch the builder does not have today) and no content asks for it yet. It is specced for
   symmetry — a band scrolling off the *top* under `CLAMP` pins at `lo` and stays visible, which
   is wrong for a fog slab that should have gone. **If P3 ships without a consumer for it,
   ship the `HI_CLAMP` bit only and leave `LO_SUPPRESS` unbuilt** — a dormant scaffold is worse
   than a booking.
6. **Does `Cram`'s and `PalRegion`'s new field disturb any hand-built `RasterOp.` construction
   in content?** R1 v6 §4.2b establishes that direct enum construction is a spelling the
   language admits and content has used. A tree-wide grep for `RasterOp.` at implementation
   time is part of P1, not of this design.

## 12. What I did NOT do

- **No emulator, no build, no sigil, no bytes.** Every runtime claim above is derived from
  source read at `5b09649c` and marked NOMINAL where it is a cycle count.
- **No hand-tuned spin, anywhere.** The solver derives spins from the measured window anchor
  (`raster_dsl.emp:1106-1198`); a second restore's spin is *solved*, and if it does not land the
  remedy is R1 v6 §3.2's ladder (narrow the stream count), never a hand-adjusted constant.
- **No cost-gate expectation adjusted to match a number.** §7.1's four-band table is derived
  from `raster_words`' fixed 7 and the SHIPPED `op_size` (which corrected R1 v6 §6.3's stale 14
  to 16); §7.3's 3.6 % is derived from §6.2's 506/496 against `:2477-2487`'s 84,595.

---

## 13. Claims

| # | claim | confidence | falsifier |
|---|---|---|---|
| OWN-1 | Per-entry walk with `(holds_base, open)` is total, and reproduces every C-A refusal while admitting disjoint and sequential bands | high — case table §3.3 derived from the shipped guard at `:2584-2637` | a program C-A refuses that OWN-1 admits, or vice versa, other than the two rows marked as deliberate |
| OWN-2 | Each id on exactly two ops, equal spans | high — `band()` constructs both, `:660/671` | a hand-built restore the guard admits with a mismatched span |
| ID-1 | `top * 128 + sa` is unique per band by construction | high — `fire_lines` forbids duplicate lines and OWN-1 forbids two ONs on one entry | two bands with equal `top` and equal `sa` that OWN-1 admits |
| SUP-1 | A band member is never suppressed alone | **high, and structural** — §4.3's algebra, not a guard | a builder path that computes a member's line other than from the group anchor + bias |
| LOCK-1 | `clamp(x+H, lo+H, hi+H) == clamp(x, lo, hi) + H` for all x | certain — arithmetic | none; it is arithmetic |
| ORD-1 | Program order == runtime line order, preserved under INT-1 | high — lockstep within a group, envelope test outside | a group member whose line is not anchor + constant bias |
| INT-1 | Envelope test is a sound `check_intervals` relaxation for a rigid group only | high, conditional on ORD-1 | two *independent* patchable records admitted into overlapping intervals — that would be the ad-hoc weakening the guard's own comment forbids |
| DEN-1 | Gap within a group is exactly `H` | high — follows LOCK-1 | as ORD-1 |
| G11-1 | First table match is the group's ON record, which is the boundary the overlay wants | high for bands; **an open call for a bottom-edge consumer** | a consumer that needs the bottom edge |
| C-1 | 0 ROM, 0 RAM for P1/P2a/P2b; +2 B/record for P3 | high — the id is not emitted; the snapshot and anchors already exist | an emitted image that changes under P1 |
| C-2 | A band is **16** program words, not R1 v6 §6.3's 14 (the spin word); the buffer caps N at **THREE**; three bands ≈ 3.6 % of the axis-4b budget | word count high — re-derived from the shipped `op_size` at `:1409-1419`. Budget share medium — **rides CLAIM 9, still UNVERIFIED** | an `op_size` change; measurement 1 |
| C-3 | `Raster_BuildSchedule` deltas ~+8 / ~+18 cyc | **NOMINAL, UNMEASURED** | measurement 3 |
| SEQ-1 | N bands does NOT gate moving bands; the shared prerequisite is P1 | high — a moving band is N=1 | — |
| — | *KILLED by this design:* "the equal-span-partner guard is single-restore by construction" (it is single-restore because the pairing was inferred, not because span equality is inherently singular); "moving bands need N-bands first" | — | — |
