# BRIEF — a truthful per-fire cost model for the raster tier

**Date:** 2026-08-18
**Status:** scoped, not started. Prerequisite for Parcel R (which adds a fourth stream op into a
model that already under-charges the third).
**Vocabulary:** `docs/EFFECTS_OP_CLASSES.md` — reg / stream / run.

---

## The gap

`check_density` asks "does this fire finish before the next one is due?" and answers it with

```
fire_cost = RASTER_FIRE_BASE_CYC (418) + RASTER_CRAM_WORD_CYC (36) x stream_words
```

summed over **stream ops only**. Three things are wrong with it, all confirmed by review:

1. **`reg` ops are charged ZERO.** A reg-heavy fire is unmodelled and can never be refused. The
   model's own comment admits it.
2. **Every stream op is charged the same**, though `stream_pal_region` costs more than `stream_cram`
   (an extra dispatch rung, a `lea`/`adda` base setup, and a `lea` restore).
3. **Dispatch DEPTH is invisible.** An op's position in the compare chain is part of its cost, which
   is why adding an opcode can move an existing effect's write landing with no guard able to see it.

The constants are fitted exactly to two points — `418 + 36x1 = 454` and `418 + 36x3 = 526` — so the
model reproduces its own anchors perfectly and has never been tested against a third shape.

---

## What was attempted 2026-08-18, and why it is not enough

I tried to extract per-op costs by **differencing live scenes**: take the profiler's `interrupts.hint`
counter with a patch channel present, then suppressed, and attribute the delta to that fire.

| config | authored fires | `hint` cycles |
|---|---|---|
| mid-band | 2 | 10,298 |
| channel 0 suppressed | 1 | 9,296 |
| channel 1 suppressed | 1 | 9,633 |
| **above-screen (control)** | **2** | **10,690** |

The first three suggest a 3-word mixed fire costs ~1,002 and a 1-word stream fire ~665 — both far
above what the model charges (526 and 454).

**But the control kills the inference.** The above-screen config has the SAME fire count and the SAME
ops as mid-band; only the fire's line differs. It reads 392 cycles higher. So the delta is not
cleanly attributable to per-fire cost — it is contaminated by at least one of: the off-screen ship's
extra VBlank work in that state (if the counter is not purely HInt), fire-position effects, or
run-to-run variance. A repeat of the identical config would have separated these; the MCP wedged
before it completed (the documented StopSystem race — recovery is `kill -9` plus relaunch).

**Conclusion at the time: unusable.** That conclusion was WRONG, and the correction is below.

---

## The instrument, characterised (2026-08-18, later the same session)

The control that looked like noise was a real effect. Repeating one config established the floor
first, as the plan below demands:

| measurement | `hint` cycles |
|---|---|
| mid-band, sample 1 | 10,284 |
| mid-band, sample 2 | 10,317 |
| mid-band, sample 3 | 10,319 |

**Noise floor: +/- 35 cycles** on a fixed config. The instrument is far more precise than the failed
inference suggested — which means differences above ~35 cycles ARE real and attributable.

Then the discriminating test. The suspect control differed from mid-band in two ways at once (the
fire's line, and the off-screen ship being active). Separating them — put the fire on line 2 with the
ship INACTIVE, by latching to screen line 3 instead of -44:

| config | fire line | ship | `hint` |
|---|---|---|---|
| mid-band | 99 | inactive | ~10,307 |
| **line 2, ship inactive** | **2** | **inactive** | **10,309** |
| line 2, ship active | 2 | ACTIVE | 10,690 |

**Two facts, both useful:**

1. **Fire POSITION has no effect** — 10,309 against 10,307 is inside the noise floor. The handler is
   position-independent, as its design claims.
2. **The off-screen ship adds ~380 cycles to the `hint` counter**, despite the ship's work happening
   in VBlank (`Enqueue_Dirty_Buffers`). **So the counter includes some VBlank work.** That is the
   instrument's real caveat, and it is a usability constraint rather than a precision problem:
   *never compare two configs that differ in VBlank work.*

### What that rescues

The original per-fire deltas were taken between configs where the ship was inactive on BOTH sides
(latched lines 100 and 230, both above the `L <= 0` gate), so they are clean of ship contamination:

| fire | modelled | measured | under-charge |
|---|---|---|---|
| `reg_sh_on` + 3-word `stream_pal_region` | 526 | ~1,002 | **+90%** |
| 1-word `stream_vsram` | 454 | ~665 | **+46%** |

Both are lower bounds: suppressing a record also removes the builder's work to emit it, which (if
that VBlank saving is in the counter too) makes the true fire cost slightly higher still.

**The model charges roughly half of what a fire actually costs.** That is the parcel's justification,
now with numbers behind it.

### The instrument's other limitation, which shapes the fixture work

The oracle MCP **wedged three times** during this session's measurements (the documented StopSystem
race; recovery is `kill -9` plus relaunch, `pkill -x` is not enough). It survives roughly 10-15 calls
before wedging. So the fixture protocol must be economical: enable the profiler ONCE, then alternate
short presses with samples, rather than toggling the profiler per measurement. A run needing 40 MCP
calls will not complete.

---

## The measurement plan this actually needs

**Purpose-built fixtures, one variable at a time**, not live content. Each is a minimal raster program
installed in a pinned scene, differing from its neighbour in exactly one respect:

| fixture | isolates |
|---|---|
| F0 — no fires (priming + terminator only) | the floor: what the schedule costs with no work |
| F1 — one fire, one `reg_set` | the reg op's true cost, currently charged 0 |
| F2 — one fire, `stream_cram` 1 word | stream base + 1 word |
| F3 — one fire, `stream_cram` 3 words | the per-word slope (F3 - F2) / 2 |
| F4 — one fire, `stream_pal_region` 3 words | the region premium (F4 - F3) |
| F5 — one fire, `reg_set` + `stream_cram` 3 words | mixed-fire cost, and whether reg+stream is additive |
| F6 — two fires, each `stream_cram` 1 word | per-fire overhead vs per-op cost |

**Before any fixture is trusted, characterise the instrument**: run F0 ten times without changing
anything and record the spread. That number is the noise floor, and no difference smaller than it may
be reported as a cost. This session's whole difficulty was measurements taken once and believed.

**The quantity to measure is OCCUPANCY** — how long the fire owns the CPU — because that is what
`check_density` is actually asking about. Note the existing 454/526 anchors were derived by a
different method (observing how far into active display a write landed), which answers a different
question. **The model may have been fitted to the wrong quantity all along**, and that possibility
should be resolved explicitly rather than assumed either way.

---

## What the model should become

```
fire_cost = per-fire overhead
          + sum over ops of ( class base + dispatch depth + per-word slope x words )
```

with every term measured, and the dispatch-depth term derived from the op's position in the compare
chain so that **adding an opcode automatically re-prices every op behind it**. That is the property
that would have caught the regression the reviewers found by hand.

**Expect the honest model to refuse content that builds today.** Once `reg` costs something and
region fires are charged properly, an existing fixture may fail `check_density`. That is either a
real latent overrun the guard should always have caught, or the model over-charging — and
distinguishing the two is oracle work that belongs in this parcel, not a surprise during it.

---

## Definition of done

1. A noise floor for the instrument, stated as a number, with the repeat count that produced it.
2. Seven fixtures measured, each difference larger than the noise floor.
3. `fire_cost_cycles` replaced by the measured model, with every constant carrying its provenance.
4. Every existing program still builds — or, where one does not, an oracle observation showing
   whether the refusal is correct.
5. A poison test: a fire that should be refused, refused; a fire that should pass, passing.

---

## Why this is upstream of Parcel R

R adds a fourth stream op. Under today's model it would be charged like a `stream_cram` while costing
more than a `stream_pal_region` — the same under-charge that already exists, made worse, on the op
whose whole purpose is to fire close to another one. Fixing the model first means R's cost is checked
by something honest instead of retrofitted afterwards.
