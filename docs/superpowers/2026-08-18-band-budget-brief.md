# BRIEF — the band-budget parcel: let raster channels roam the whole screen

**For:** an agent with no prior context.
**DESIGN-FIRST.** This changes a comptime safety guard and a runtime contract. Research → design
draft → **three mixed-model adversarial lenses on the draft** → owner sign-off → plan → execute. Do
not go from research straight to a plan; the lens sweep on the previous parcel's draft found two
load-bearing defects that would otherwise have shipped behind green-looking gates.

**Price it honestly before you start: this is worth about 3 screen rows.** Say so in the draft. An
earlier revision of the design claimed "takes the residual to zero", which was wrong and was
corrected. If the sweep or the owner decides 3 rows is not worth a wire-format change, that is a
legitimate outcome.

---

## What you need to understand first

Read, in order:
1. `aeon/docs/superpowers/specs/2026-08-16-hint-schedule-local-removal-design.md` — the previous
   parcel's design, especially **§5 (correctness arguments)** and **§8 (this parcel)**.
2. `aeon/engine/effects/raster_dsl.emp` — `check_intervals`, `check_density`, `fire_cost_cycles`,
   `patch_table`, `RASTER_MAX_PATCH`.
3. `aeon/engine/effects/raster.emp` — `Raster_BuildSchedule`, `Raster_GetChannelBand`.
4. `aeon/engine/level/parallax.emp` — the anchored-overlay boundary (search `.anchor_hi_ok`).
5. `aeon/tools/scenes/README.md` — how the arm arithmetic works, with derivations.

### The mechanism, in one paragraph

Aeon's HBlank raster engine runs a chain of "fire records" during active display. The gap between
fires is RELATIVE — each record carries an arm word `$8Axx` written to VDP register `$0A`, and the
value is `$8A00 | (this_fire_line - previous_fire_line - 1)`. A "patchable" record's line is derived
each frame from a world anchor minus the camera, and `Raster_BuildSchedule` (VBlank) re-records the
whole schedule from a ROM template into the inactive buffer, emitting only the records that are live
this frame, then swaps. A record whose latched line has passed its authored band is not emitted at
all.

### The constraint this parcel attacks

`check_intervals` (comptime) requires every record's possible fire-line interval to be **strictly
ascending and disjoint**. A patchable record's interval is its authored band; a static record's is
its own line. The guard exists for one reason: two records able to reach the same fire line make the
inter-record gap `-1`, which stores as `$FF` — and **`$8AFF` IS the park word**, so it would silently
kill every remaining fire in the frame.

The cost is a BAND BUDGET: disjoint bands over screen lines 3..223 must satisfy
`sum(hi_i - lo_i + 1) + (N-1) <= 221`. So two channels cannot both traverse the screen. In the
shipped OJZ content, channel 0 (the water boundary) is banded `3..220` and channel 1 (a vscroll-split
gate fixture) `222..223` — the budget is EXACTLY full. Whatever a band cannot reach, the boundary
cannot express: past `band_hi` the record is dropped, so up to 3 rows render dry that the world says
should be wet.

---

## What is already settled — do not re-litigate

**Ruled 2026-08-16 by a Fable adviser, with evidence:**

> **It does NOT need per-record cost in the table.** Split the invariant in two.
>
> - **Safety (the park word):** enforced by the builder with ONE runtime compare — every emitted
>   line strictly greater than the previous; suppress or push the violator. No cost model, no table
>   data. This alone makes an overlapping-band schedule SAFE (it cannot kill the chain).
> - **Quality (density):** the existing comptime `fire_cost_cycles` already computes per-record cost
>   at build time. Bake its RESULT — `ceil(cost / RASTER_SCANLINE_CYC)` in LINES, not raw cycles —
>   and it need not even be per-record: a single **program-wide max** (currently 2 lines) as one
>   header word closes density with at most one line of pessimism on the cheap record.

Also settled: a density violation is **cosmetic**, not fatal. `raster_dsl.emp`'s `check_density`
comment says it — an overrun does not drop the next fire (the counter is already armed), it pushes
the writes into active display, which renders as a visible mid-row colour change. Only the park word
is fatal. That asymmetry is what makes this parcel small.

---

## What is genuinely open — this is the design work

### 1. The collision PRIORITY ruling

When two records' latched lines collide, one must yield. Who? Candidate answers: authored order,
channel index, the record with the narrower band, the one whose anchor moved least. **There is no
obviously right answer and it is a content-visible decision** — the loser's boundary vanishes or
shifts. Propose one, argue it, and let the sweep attack it.

### 2. The parallax-agreement contract — the hard part

The palette boundary (`Raster_BuildSchedule`, VBlank) and the scroll boundary
(`parallax.emp`, main loop) must reach the SAME answer, or they disagree on screen — the exact defect
Parcel W exists to remove, and `docs/DEFERRED_WORK.md` explicitly forbids changing one side alone.

Today they agree because both apply the same rule to the same two band words from the same table
(`Raster_GetChannelBand`). **Under collision resolution the winner is a COMPUTED outcome**, so both
consumers must compute it identically from the shared latch plus static per-channel data — which is a
contract change to `Raster_GetChannelBand`, whose whole reason for existing is that the two sides
clamp identically.

Note the constraint that kills the obvious shortcut: a published "who won" bitmask written by the
builder in VBlank is **one tick stale** to the parallax reader in the main loop. That cross-camera
skew is precisely what `Effects_LatchWorldLines` exists to prevent. Whatever you design must be a
pure function of state both sides can read on the same tick.

### 3. Re-proving §5

The previous design's correctness arguments §5.1-5.3 (no negative gap; the 8-bit arm ceiling
survives; density is only relaxed) all rest on the emitted list being a SUBSEQUENCE of a
strictly-ascending disjoint authored list. **This parcel deletes that premise.** Every one of those
arguments needs re-proving under the new rules, and the draft must do it explicitly rather than
inheriting them.

---

## Definition of done

1. Both OJZ channels can be authored with overlapping bands and the schedule stays safe — no park
   word appears by accident, ever, under any anchor combination.
2. The two boundaries agree in all three anchor states, proved through the existing scene harness
   (`aeon/tools/scenes/`, `aeon/tools/effects_scene_assert.py`) rather than by hand.
3. `check_intervals`' replacement guard is **poison-proved**: show it firing on a schedule that
   would have parked the chain, and staying silent on shipped content. A guard nobody has seen fire
   is a guard nobody knows is wired.
4. The residual is re-measured and stated. If it did not actually reach ~0, say so.

---

## Traps, all of which have already cost this codebase time

- **`$8AFF` is the park word.** Any encoding change must answer what a negative gap MEANS, not merely
  re-spell it.
- **The arm SLOT is two records back; the LINE delta is one record back.** Ruling 1b. The previous
  design draft got this backwards and three lens seats caught it independently. `arm = $8A00 |
  (this_fire - prev_fire - 1)`, written into the slot belonging to the record two earlier.
- **Derive every expected number from the values you actually wrote; never copy one from a nearby
  pin.** Two gates in the previous parcel were written against copied numbers and would have failed
  correct code.
- **A cross-seam symbol is invisible to `build.sh`** and breaks sigil `*_port` targets silently. Any
  new symbol goes into `sigil/crates/sigil-harness/repin.toml` AND each port test's carrier table.
- **A link-time address cannot enter an emitted image that a comptime pin compares** — it makes the
  image non-comptime and breaks `first_mismatch`. Carry parameters; add bases at runtime.
- **`lea -NAMED_CONST(aN), aN` is silently DROPPED by sigil's contract-closure walk** (gate-fatal,
  and it is the ANALYSIS going blind, not the codegen). `-128` resolves; `-RASTER_BUF_SIZE` does not.
  Use `suba.w #CONST, aN`.
- **`.emp` comptime `var[i] = x` does not parse** — assignment targets are bare dotted paths with no
  indexing form. Accumulate into a scalar (a bitmask), as `prog_mask` does.
- This is a **byte-changing** parcel: the repin/refreeze ritual applies, and `aeon` + `sigil` merge
  and push as a PAIR. `refreeze --check` is NOT the goldens.

---

## Process expectations

- Commit every step; never leave `master` broken; use a feature branch and merge when the gate passes.
- `git add` exact paths only. Never touch `games/sonic4/data/editor/**` (auto-commit daemon).
- The lens sweep is three seats with DIFFERENT lenses and mixed models — hardware/timing,
  correctness/state, gate-vacuity is the composition that worked. Give each the ground truth and tell
  it to verify claims against the source rather than trusting the draft.
- Subagents must NEVER touch `mcp__oracle__*` tools (they deadlock). The scene harness is safe.
