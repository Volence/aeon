# Raster op classes — reg / stream / run

**What this is:** the vocabulary for what a raster op COSTS, so an author can tell at the call site
what will fit in one fire. It replaces "CRAM-class", a name that includes VSRAM ops and has already
caused one guard to be specified against the wrong set.

**Status:** the taxonomy is descriptive of the engine as it stands today. The renames and the cost
model it enables are a parcel in progress — see §6 for what is enforced now versus what is not.

---

## 1. Why classify by cost rather than by target

The instinct is to group ops by what they change — palette here, scroll there. **That grouping is
actively misleading**, because the two spend the identical budget:

| fire contents | stream ops | stream words |
|---|---|---|
| `pal_region` + `pal_region` | 2 | up to 3 |
| `pal_region` + `vsram` | 2 | up to 3 |

At the WIRE level they are not merely similar, they are the same instruction. A vscroll split emits
`OP_CRAM` with a VSRAM write command — the shipped twin reads `2, $4002, $0010, 0, $0043`, where `2`
is `OP_CRAM` and the only VSRAM-ness is the target bits inside the command longword.

So the question "can these two ops share a fire?" is never answered by what they affect. It is
answered by what they spend.

---

## 2. The three classes

### `reg` — a single register word

**Mechanism:** one `$8xxx` word written to the VDP control port. No command longword, no blanking
delay, no data-port traffic.

**Members today:** `set_reg`, `sh_on` (a `set_reg` in a hat).

**Cost:** dispatch only — but note dispatch is not free and `reg` is the *most expensive op to
dispatch*, because it is the compare chain's fall-through: it pays every failed comparison ahead of
it. That is the opposite of the intuition its tiny wire body suggests.

**Ordering rule (enforced):** every `reg` op in a fire must precede every `stream` op. A `reg` write
executes immediately while a `stream` op burns a blanking delay first, so a `reg` placed after one
lands strictly later in the line — a worse artifact than the measured one, and invisible to an
author.

**Known artifact:** a mid-frame mode-register change switches roughly 45% of the way across its
line. Measured, documented, deliberately unfixed — extending the blanking delay to cover `reg` would
cost ~40 cycles of a ~60-cycle budget. So a `reg` op's edge is not pixel-clean; schedule it a line
early if that matters.

### `stream` — a command plus N words through the data port

**Mechanism:** a full VDP command longword in ONE `move.l` (which sets the address), then a
cycle-counted blanking delay that parks the writes offscreen, then N words to the data port.

**Members today:** `cram`, `pal_region`, `vsram` — and the proposed band restore joins this class.

**Cost:** the dominant per-fire cost. Each `stream` op pays its own command longword AND its own
blanking delay; the delay is the entire mechanism that keeps the write out of active display.

**Budget, per fire:** at most **2 stream ops**, at most **3 stream words total**. Both are cycle
budgets, not FIFO or CRAM limits. Three words is the wall most authors meet first — two ops is
legal and is the ceiling.

**Why 3 words:** about 60 cycles are usable between HINT-pending and the next line's active display,
after ~44 cycles of exception entry. A write outside that window paints a visible dot, because CRAM
is single-ported and the pixel pipeline reads it every dot.

**Consequence for wide swaps:** a full 16-colour line cannot swap in one fire. It is authored as
consecutive `stream` fires on successive lines, taking `ceil(N/3)` of them. That six-fire idiom is
ours, not a reference's — S3K swaps a whole water palette in ONE interrupt by parking the counter,
stopping the Z80 and spinning ~370 cycles between triples.

### `run` — a dense mode that owns a line range

**Mechanism:** not an op that returns. It reprograms the line counter to fire EVERY line and runs a
minimal per-line body for a declared range, then restores sparse dispatch.

**Members today:** `run_gradient` (streams pre-computed words from ROM), `run_ramp` (computes each
line's value from a 16.16 accumulator, so it is parameterisable at runtime).

**Cost:** owns the handler for its range. It is not composable into an ordinary fire — a `run` is
authored through its own program constructor, not by adding an op to a fire's list.

**Budget:** one run at a time. Entering and leaving each cost their own scheduling line.

---

## 3. The rule of thumb

> **`reg` ops are cheap to run and expensive to dispatch. `stream` ops are the budget. `run` ops take
> the whole handler.**

If two ops are both `stream`, they compete — whatever they target. If one is `reg` and one is
`stream`, they coexist easily, but the `reg` must come first.

---

## 4. Naming

Constructors should carry their class, then their target:

```
reg_set          reg_sh_on
stream_cram      stream_pal_region      stream_vsram      stream_pal_restore
run_gradient     run_ramp
```

The class is what determines whether two ops fit together, so it belongs at the front where a reader
scanning a fire's op list sees it first. The target answers "what does this do", which is the second
question, not the first.

**"CRAM-class" is retired.** It named a set containing VSRAM ops, and a proposed guard was specified
against it that would have wrongly refused legitimate scroll content for exactly that reason.

---

## 5. What belongs where — quick table

| constructor | class | words | notes |
|---|---|---|---|
| `set_reg` / `sh_on` | `reg` | — | must precede streams; ~45% mid-line edge |
| `cram` | `stream` | 1-3 | inline colour words |
| `pal_region` | `stream` | 1-3 | colours from a variant staging buffer |
| `vsram` | `stream` | 1-3 | same opcode as `cram`, VSRAM target |
| *(band restore)* | `stream` | 1-3 | proposed; streams from a frame-top snapshot |
| `run_gradient` | `run` | — | own program shape, ROM stream |
| `run_ramp` | `run` | — | own program shape, computed per line |

---

## 6. What is enforced today, and what is NOT

**Enforced, build-fatal, on the COMPOSED program** (so layering two presets onto one line re-checks
the composition, not just the parts):

- at most 4 ops per fire
- at most 2 `stream` ops per fire
- at most 3 `stream` words per fire
- every `reg` op precedes every `stream` op
- fires strictly ascending, disjoint reachable intervals (a collision would store a `-1` gap, whose
  byte is the PARK word, killing every later fire in the frame)

**NOT enforced — read no cycle guarantee into the above.** The ceilings are STRUCTURAL COUNTS. The
cost of a fire is not modelled:

- a 4-op fire of `reg`s and a 1-op fire of one `stream` both pass, and the first is certainly slower
- the density model charges `reg` ops **zero**, so a reg-heavy fire is unmodelled and never refused
- it charges every `stream` op the same, though `pal_region` costs more than `cram` (deeper
  dispatch, extra base setup) — so region-shaped fires are under-charged
- dispatch DEPTH is invisible to it entirely, which is why adding an opcode can tax an existing op's
  landing position with no guard able to see it

These ceilings bound the DAMAGE of a mistake. They do not certify the shapes they admit.

**This gap is CLOSED as of 2026-08-16.** `fire_cost_cycles` now charges every op class its measured
cost including dispatch position: `FIRE_BASE + sum(fetch + dispatch(depth) + class work + word
slope x words + tail)`, with dispatch depth derived from the opcode order so inserting an opcode
re-prices everything behind it. Eight measured fixtures, four free parameters, zero residual —
`docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md`.

A `reg` op costs **94 cycles** and a whole reg-only fire **396**, where the retired model charged
zero and could never refuse one. A `stream_pal_region` costs **48 more** than a `stream_cram` at
equal word count. A dispatch rung is **16 cycles**. And a `stream_vsram` word was measured to cost
exactly what a colour word costs — same instruction path, since a VSRAM op emits `OP_CRAM` with a
different command longword — so the reg/stream/run vocabulary's claim that the ceiling is a CYCLE
budget rather than a CRAM one is now measured rather than argued.
