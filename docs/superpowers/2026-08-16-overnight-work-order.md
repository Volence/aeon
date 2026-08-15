# OVERNIGHT WORK ORDER — from 2026-08-15 night

Written for a long unattended session. The owner is asleep. **Do not block waiting for them.**

**Entry state:** aeon `9c9d7c75` / sigil `f00408e1`, both pushed and matching `origin/master`,
chain 119, suite 3716/0, four shapes boot. CRCs `416be247` / `9ef00c29` / `6af0112d` / `fdc82cc0`.

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

---

## How to make decisions while the owner is asleep

**When you need a judgment call, dispatch a Fable agent as the decider.** Do not stall, and do not
silently pick the path of least resistance.

```
Agent(model: "fable", subagent_type: "general-purpose",
      prompt: "<the decision, the options, the evidence for each, the constraint that makes it
               hard, and what you currently lean toward and why>")
```

Rules for using it well:

- **Give it the evidence, not the question alone.** A decision brief with file:line facts, the two
  or three real options, and their costs gets a usable ruling; "which is better?" does not.
- **Say what you lean toward and why.** You want it to disagree with a reason, not to guess blind.
- **Take the ruling and move.** Record it in the parcel's evidence or plan doc as
  *"decided by Fable adviser, <date>: <ruling>, because <reason>"* so the owner can audit or
  overturn it in the morning. An unattributed decision is the thing to avoid, not a delegated one.
- For a **big design draft** (parcel W below), do not use one adviser — fan out **three mixed-model
  adversarial lenses** on the draft first, exactly as was done for Parcel P. That method found nine
  design-changing defects, three of which were flatly wrong claims that would otherwise have shipped
  as a green-looking gate.

### What to decide yourself, what to hand to Fable, what to STOP for

| class | action |
|---|---|
| mechanical, reversible, covered by a gate (naming, ordering, which of two spellings assembles) | decide yourself, note it in the commit |
| design tradeoffs inside an approved parcel's scope (table shape, guard placement, task ordering, what a gate measures) | **Fable adviser**, record the ruling |
| anything that changes engine DIRECTION, freezes a format, or is hard to reverse | **STOP.** Write the brief, leave it in the work order, move to the next queue item |
| destructive or outward-facing (force-push, history rewrite, deleting data, anything leaving the machine beyond the already-authorised `git push` of these two repos) | **STOP.** Never autonomously |

**Push is pre-authorised** for `aeon` and `sigil` `master` only, and only for work that has passed
its own gate. Nothing else leaves the machine.

## Standing rules

- **Never leave `master` broken.** Merge only after that parcel's gate passes. If a parcel cannot
  be finished, leave it on its branch, unmerged, and say so.
- **Commit every step.** Lost work is unacceptable; a long unattended run is exactly when it happens.
- **Verify the branch at commit time** — parallel sessions share this tree.
- `git add` exact paths only. Never `-A`, never a glob. The editor JSON churn belongs to the
  auto-commit daemon; never stage, revert or touch it.
- **Subagents must NEVER touch oracle MCP** — it deadlocks. All emulator work is foreground, one
  instance (`pgrep -a oracle_gui`).
- **Never tail a test run.** Read aggregate totals and every failing-target line. Suite totals are a
  **lower bound** (`deep_nesting_aborts` aborts without printing a `test result` line).
- **Ritual order for a byte-moving parcel:** freeze FIRST, then the strict suite, then
  `refreeze --check` + `repin --check`. Re-verify CRCs *after* the freeze — pins feed placement.
- **Guard proof standard:** inversion, plus showing the guard accepts the adjacent legal case.
- **Morning summary leads with what MERGED**, then what is on a branch, then what is blocked and the
  brief for each blocked decision.

---

## The queue

### 1. ~~Parcel P-b — the runtime~~ — **DONE 2026-08-15, all ten tasks, merged.**

Plan: `docs/superpowers/plans/2026-08-15-effects-p3-parcel-p-b.md`. Evidence:
`docs/benchmarks/effects-p3-p-b/GATE-EVIDENCE.md`. Chain 120.

Two rulings were taken to a Fable adviser and are recorded where they bind:

- **The demo-CRC gate criterion is superseded** (recorded in the plan's Task 10). It is
  unachievable for any parcel that adds engine RAM and therefore carried zero bits. Replaced by
  `tools/demo_drift_classifier.py`, which requires the demo diff to classify with **zero
  unclassified bytes**. Both demo shapes pass; proved non-vacuous by tampering one code byte.
- **`Effects_SetWorldY` got a call site** (GATE-EVIDENCE §6). The adviser corrected the failure
  class: `fx_tint_band` was a *comptime* helper that was never elaborated, whereas a `pub proc` is
  assembled either way — what an uncalled one cannot pin is its **contract**.

**Three things the next session should know:**

1. **EFX-9 is new and it invalidates EFX-5's reasoning.** `tools/effects_budget_check.py` is
   correct and is **run by nothing** — not `build.sh`, not CI. `raster_state_bytes` had drifted 10
   bytes and the gate credited with preventing that never executes. P-b corrected the value and
   repaired a crash in it; **the wiring is Parcel B's**, item 3 below.
2. **`raster_port` is confirmed dead**, as item 4 suspected: it appears only in `repin.toml` and in
   `pins.rs`'s generated doc comments, and `refreeze`'s own rerun hint still names it. P-b
   deliberately did **not** add pins to it.
3. **A better raster instrument exists than the one the gate used.** `ojz_scroll_test.emp` has
   `Debug_Scene_Freeze`, which skips `Camera_Update` so a written `Camera_X/Y` stays put. It was
   found only after the gate had been measured the hard way (lowering `Camera_Y_Max`). Use it.

### 2. `replay_runner` framebuffer dump — the highest-leverage item in this list

Repo: `oracle-next`. Teach the replay net to dump framebuffer rows at named checkpoints.

Right now `replay_runner` is **pixel-blind** — its whole surface is
`--rom/--lst/--fixture/--negative-control/--max-frames/--stall-frames` — so every raster/palette
gate has to be a manual pinned-camera oracle capture. That is why P-b's gate is the slow part, and
it will be the slow part of W, R and D too. A row-dump at checkpoints makes all of them
deterministic and headless.

**DESIGN SETTLED 2026-08-15 by Fable adviser** (briefed with the finished P-b gate as the
requirements list). Not yet implemented — this is a ready-to-start parcel, not an open question.

**Ruling: whole frames as the dump primitive, with the measuring instrument built ONCE into the
harness. Named row ranges are REFUSED** — the load-bearing half of every P-b clamp result was
"zero differing pixels at rows 120..223", an assertion about rows a fixture author would never
have declared, so a declare-what-matters format structurally cannot express the gate.

Build it in three stages, and keep them separate — the runner stays dumb, the instrument stays
canonical, the gates stay thin:

1. **`--dump-frames DIR`** on `replay_runner` (plus `--dump-at T1,T2,…` for ticks that are not
   checkpoints, since effects gates will want moments the fixture does not name). The core
   already renders every active scanline in its hot path, and `oracle-core/src/scanline_capture.rs`
   already ships `ScanlineCapture` with `Retain::LastFrame` — documented as the thing that makes
   **mid-frame CRAM effects visible**, which is precisely the subject. Sinks are opt-in via
   `wants_scanlines`, so a run without the flag stays byte-identical to today.
2. **`replay_framediff A_DIR B_DIR`** — a second binary, the canonical instrument. Per checkpoint:
   differing rows grouped into bands with explicit edges; per differing row a pixel count and
   `min_x`/`max_x`; and the identical ranges enumerated explicitly. Text plus a JSON sidecar.
   Those fields are exactly what the P-b gate had to establish by hand.
3. **`--expect-identical`**, a same-config re-run control that must report zero diffs. The
   background-animation drift that contaminated a P-b measurement **dissolves** headlessly — two
   runs of one config latch bit-identical frames because the animation phase is pinned by the
   tick — and this control is what keeps that honest while also catching nondeterminism creeping
   into the core.

**No committed golden images.** Pixels never enter the repo; dumps go to scratch (~7-8 MB/run,
disposable). The committed artifact is the small framediff **report**. A report-golden churns only
when the effect's geometry actually moves — which is exactly when review should look — whereas a
PNG golden churns on any pixel anywhere and would feed the freeze ritual for nothing.

**The rule that stops every parcel re-inventing its instrument, and it is a hard line:** a gate
script may select and assert on report fields; **it may never read pixels**. If a gate needs a
question the report cannot answer, the *report format* gets extended in `oracle-replay` — once,
reviewed, versioned with the harness — and every later gate inherits it. Do not add assertion
flags to the runner.

One constraint to write down: an A/B pair is two ROM builds under one fixture, so the config delta
must not perturb the RAM the checkpoint hashes cover. Effect-config-only deltas (anchors, bands,
palettes) do not touch player state, so this holds for W/R/D; if a future A/B desyncs, that is the
gate telling you the delta was not effect-only.

**Definition of done:** re-derive the P-b gate's row measurements through the tool. If it cannot
reproduce the seven-for-seven arm-word table's row consequences and the row-59/99 fragment
characterisation (`min_x` 127 and `max_x` 255), it is not finished.

~~Note `ojz_fixture` is **red on master** (open re-stamp, desync at tick 735, `docs/BUGS.md`) —
decide whether this parcel also re-stamps it or explicitly leaves it.~~ **STALE, CORRECTED
2026-08-15 — do not act on it.** `ojz_fixture` is **GREEN**, and `docs/BUGS.md` has said so since
2026-08-14: the tick-735 desync *never existed*, it was an artifact of hand-arming (three arming
attempts on one ROM produced three different hashes), and the re-stamp it pointed at had already
been merged as `32a79e1d`. Both fixtures pass, and the runner's negative control trips correctly,
so the passes are not vacuous.

**This is the second time that dead claim has been copied forward into a work order**, which is
the reason for spelling it out rather than deleting the line: the parcel has no fixture-repair
prerequisite, and the recorded lesson is that *a manual measurement giving a different answer
every time is not weak evidence, it is ABSENT evidence*.

### 3. Parcel B — budget honesty (small, safe, mostly correction)

`tools/effects_budget_model.toml`. P-a already shipped the density guard the roadmap asked for
(guard 8, worst-case band edges), so B shrinks to: correct `full_line_fire_cost` (it is a LINE
count, not a cost), retire or re-label `sparse_tier_cycles_per_frame = 8358` (it was VBlank+HInt
under the instrument bug — read the existing note about why the figure is a legitimate DIFFERENTIAL
before touching it), add the measured rows (vsram 454, cram-of-3 526, line 488), and update
`raster_state_bytes` if P-b has not already.

Also verify `tools/effects_budget_check.py` is not one of the **verified vacuous gates** — a prior
audit found it reporting `RAM=0`. Prove it fires by inverting a value.

### 4. The `raster_port` coverage hole (sigil-side, additive)

The pins tagged `tests = ["raster_port"]` — `RASTER` region, `RASTER_PROGRAM`, `RASTER_CURSOR`,
`RASTER_PENDING`, `RASTER_BUF_A`, `RASTER_ACTIVE_BUF`, `HBLANK_UNINSTALL_OFF` — are consumed by **no
test**. There is no `raster_port` binary in `crates/`. So the raster module has no standalone port
oracle, which is precisely the coverage P-b's runtime rewrite wants.

Either write the port test or delete the pins and record why. **Do not leave pins that look like
coverage and are not** — that is the exact failure class this project keeps re-finding.

### 5. Parcel W — the world anchor gets an owner (DESIGN FIRST, byte-changing)

Raster owns `Effects_World_Y[]` after P-b; the parallax deformation system owns per-line HScroll
wave and ripple; they share no seam, so a complete underwater section — palette boundary **plus**
shimmer at the same line — is inexpressible.

The roadmap says settle this **before `sec_effects` freezes** as the composition point. S3K anchors
ripple *phase* to world quantities in three separate places precisely because a wave keyed to a
frame counter slides when the camera moves.

**This one gets the full treatment:** brainstorm → design draft → **three mixed-model adversarial
lenses** → plan → execute. P-b deliberately named the RAM `Effects_World_Y` (not `Raster_*`) so that
W adds a *reader* rather than relocating storage — check that assumption still holds before
designing around it.

### 6. Parcel R — mid-screen restore

There is a derived mechanism for restoring at frame top and **nothing** for restoring at a lower
line, so a tint over lines 100-140 is not expressible. This is the concrete form of the bands
question. Note it will want to write the raster buffer mid-frame, which P-b's VBlank ruling
deliberately forbids for the patcher — R must settle that on its own terms, and that is a
design-direction question, so **STOP and brief it** rather than deciding it at 4am.

### 7. Parcel D — starter pack + content

Written after P and W, because its most interesting content — moving boundaries, a world-anchored
gradient — is exactly what those unlock.

---

## Also open, if the queue above stalls

- **Sound packages 5 and 6** (`project_open_work_inventory` memory). Self-contained.
- **The `STRESS_EVICT` famine root-cause.** Instrument first; averaged profiling cannot find a spike.
- **EFX-2** (cross-fade unreachable) and **EFX-7** (`Raster_Clear` is a no-op, `HBlank_Uninstall`
  unreachable) — both byte-changing, both deliberately open. Read why before touching either.
- **Splitting the VSRAM op class** off `RASTER_CRAM_MAX`. The corpus sweep found only CRAM writes
  glitch, so `vsram` inheriting `EFX_BLANK_DELAY` and the 3-word ceiling is pure loss — Ristar
  writes 42 VSRAM words in one fire. It only ever makes fires cheaper, so nothing currently legal
  becomes illegal.
- **Spacing sweep 2/4/8 lines**, to find where the adjacent-`cram` dot disappears.

---

## Things that have bitten this lane before

- **An unexercised authoring surface is unverified.** `fx_tint_band` shipped broken for two parcels
  because nothing had ever called it. If you add a preset, add a call site.
- **ROM length is not the measure of added data.** P-a added 146 bytes and the ROM grew 14; pins
  moved a uniform +0x90. Measure pin deltas.
- **`ensure` does not short-circuit** — one bad input fires every guard it violates.
- **`first_mismatch` is blind to length in BOTH directions.** Every twin needs its own `.len` ensure.
- **A gate can measure the placer, or go vacuous, and still look green.** Before trusting a gate,
  ask what a broken implementation would score on it.
- **Docs in this tree drift.** Re-derive every concrete file:line reference against the tree; treat
  specs as INTENT.
