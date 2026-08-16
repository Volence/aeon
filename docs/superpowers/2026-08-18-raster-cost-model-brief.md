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

**Conclusion: differencing live scenes cannot resolve a 36-cycle-per-word slope against a
several-hundred-cycle uncertainty band.** Do not build the model on these numbers. They are recorded
here so nobody re-derives them and mistakes them for measurements.

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
