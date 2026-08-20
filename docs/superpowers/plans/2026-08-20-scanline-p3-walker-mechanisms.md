# Scanline Services P3 — Walker Mechanisms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the scene model the runtime it has been describing. P1 authored the geometry, P2 made it pay for itself; P3 builds the six walker mechanisms design §10 names — world-Y re-glue, curves, per-layer deform refs, the single-source per-line forcer derivation, vscroll-split lowering, and the left-column mask — each landing with the §8.3 instrument that can see it.

**Architecture:** Three phases, each an atomic landing cluster (design §10's rule: gates + poisons in the same cluster, master never half-migrated). **Phase 0 is instruments and lands FIRST**, for the same reason P2's Phase 0 was measurement: four of the six mechanisms have no instrument today, and the F2/dense precedent in this tree is unambiguous — no instrument, no parcel. Phase 1 builds the mechanisms in dependency order. Phase 2 re-fits the cost model over the walker P3 leaves behind, gates the new axis, and lands.

**Tech Stack:** sigil `.emp` (comptime lowering, `ensure`, `emp_expect_fail` poisons), Python instruments under `tools/`, **oracle** for every cycle figure (oracle-next still has no profiler — see "Instrument" below), **oracle-next** `emulator/scanlines` for any landing/scanline question.

**Source of truth on disagreement:** the design spec `docs/superpowers/specs/2026-08-17-scanline-services-design.md` predates P2's landings. Where it disagrees with the tree, **this plan transcribes from the tree and the measured rows**, and the disagreements are enumerated in "Spec-vs-tree corrections" below. Do not resolve a conflict by re-reading the spec.

---

## Spec-vs-tree corrections — read before any task

Eight places where the design doc is stale against the tree as of `0cf5a053`. Each is a
number or a claim a task would otherwise copy.

| # | Spec says | Tree says | Consequence |
|---|---|---|---|
| C1 | §2/§3.3/§5: a per-line forcer prices **896 B** of VBlank DMA | `effects_budget_model.toml` `[scene_budget]`: **1792 B**, from a live-queue scan showing **two** 448-word entries (`dma_hscroll_perline_entries = 2`), 23.8% of the 7524 B pool, plus 4270 cyc of drain | Task 6 prices the forcer at the measured figure. **And Task 6 must first reconcile a real discrepancy:** `engine/system/buffers.emp:156-162` declares exactly ONE `Static_Hscroll_Line` (`dma_length(896)`), yet the queue scan sees two 896-byte entries. Two entries from one declared static is unexplained. Resolve it before pricing; do not assume either number is the error. |
| C2 | §2: curve∧deform per layer is forbidden because "the fill loop's register file is exhausted (verified: `.lp_both` uses all 16)" | `.lp_both` (`engine/level/parallax.emp:1350-1377`) has **14** registers live: `d0-d7` + `a1-a6`. `a0` is spilled at proc entry (`movem.l a0/d7,-(sp)` at `:1253`) and never touched in the loop; `a7` only brackets the proc | The ensure stays (Task 10 authors it), but its **justification text must be corrected** — "14 live, `a0` spilled by choice" — or the next reader will find the claim false and delete the guard. Relaxing the prohibition is a §9 non-goal needing a measured register-allocation design; PARK-3 below. |
| C3 | §4.1: "the transition ramp at `parallax.emp:593`" is the bounded-`divs` precedent | The only `divs` in the tree is `engine/level/parallax.emp:651`, inside the plane-B transition lerp; its bound is argued at `:640-645` (divisor `1..PARALLAX_TRANS_DEFAULT`, dividend `ext.l` of a word gap) | Task 10 cites `:651` and reuses that bounding argument shape for the curve hoist. |
| C4 | §4.1: the Parcel-W hand-unrolled entry copies are at `parallax.emp:862-864` and `:891-893` | They are at **`:927-929`** (`.anchor_shift_band`, word+long+long, pre-decrementing) and **`:956-958`** (the split-entry write, long+long+word) | Task 8 hardens those two sites. |
| C5 | §4.1: the copies are "pinned by `ensure(sizeof(band_entry)==10)` today" | No such ensure exists. `parallax.emp:132-133` asserts only **evenness** (`sizeof(band_entry) % 2 == 0`). The literal-10 pin is `BAND_ENTRY_LEN = 10` at `engine/ram.emp:38` plus `ensure(extern("band_entry_len") == BAND_ENTRY_LEN)` at `:40` | Task 8's record change moves `BAND_ENTRY_LEN`, which sizes `Parallax_Shadow_Bands` (`ram.emp:300`, 80 B today). That is a RAM move on axis 6, and the pin is an `extern()` site (EMP_PITFALLS §5 territory). Both belong in Task 8's step list, not discovered mid-task. |
| C6 | §8.3: runtime verification runs on oracle-next | oracle-next still has **no profiler instrument** (P2's ruling, unchanged). Its `emulator/scanlines` surface exists and is what the 1b/1c sweeps used | Every cycle row in P3 is oracle. Every landing/scanline question is oracle-next. Neither is a preference. |
| C7 | §2: the forcer set includes "any layer boundary not on the 8-px cell grid", and §4.1 describes act-space world-Y tops | `layer()` **ensures the opposite today**: `ensure(world_y % 8 == 0, "... off-grid tops arrive with world-Y re-glue (P3)")` and `ensure(world_y >= 0 && world_y < 512, "... act-tall world-Y arrives in P3")` (`engine/level/scene_dsl.emp:194-197`). `scene()` also fences `precision: line` behind a non-null BG table (`:469-470`) | Tasks 6 and 7 are the tasks those three ensure messages name. Each relaxation replaces a guard with a wider one — never deletes it. |
| C8 | §5 axis 5 budgets sprite strips "against a declared object-system reservation" | **Nothing measured.** `[scene_budget]` `axis5_sprite_slots = "NO SUBJECT UNTIL P3 ..."`; P2 Phase 0 took no sprite row | Task 4 measures the reservation. Without it Task 12's mask cannot be gated, only shipped. |

**Two further scope facts the spec does not state and a reader will assume wrongly:**

- **Axis 5's P3 subject is the LEFT-COLUMN MASK, not sprite strips.** §2 prices the mask's
  policy slot in axis 5 ("one engine-reserved SAT slot, 8-px masking column strip, emitted at
  scene install"). `CAP_FG_SPRITE_STRIPS` stays RESERVED past P3 — §10's P3 list does not
  include sprite strips.
- **Axis 7 gets NO subject in P3.** §10's P3 list contains no computed handlers, and §9
  records the computed-range infra as deliberately not rebuilt. The
  `axis7_computed_handler_pins` row stays "no subject" after this parcel, and Task 13 must
  say so in the toml rather than leave the P2 wording ("NO SUBJECT UNTIL P3") standing as a
  promise P3 did not keep.

---

## Instrument: cycles on oracle, scanlines on oracle-next, nothing in a subagent

- **Cycle rows: oracle, per-routine, keyed by entry address.** `interrupts.hint` is never a
  valid source — oracle buckets an interrupt by comparing handler entry PC against `0x78`, and
  Aeon's `VBlank_Handler` is a ROM address that never matches, so that counter is HBlank plus
  VBlank and reads as neither. Documented at the top of `tools/raster_cost_probe.py`.
- **Every oracle cycle figure is an IDEAL-CYCLE figure.** The 68000 core adds only
  `cyclesExecuted` to `_currentCycle` (`M68000.cpp:1029-1031`) while bus/VDP/DMA stall lands in
  `_currentTime`. `WALKER-MODEL.md` §7 states what that costs this model specifically: the
  walker's HScroll-buffer writes and the reg `$0B` assertion cost their nominal cycles here by
  construction. P3 does not fix that and must not claim to.
- **Landing/scanline questions: oracle-next `emulator/scanlines`**, with its own known limit —
  it renders a row atomically at line start, so a landing resolves to ±1 scanline and the early
  edge is not observable.
- **No emulator from a subagent, ever.** Oracle MCP from a background agent deadlocks. Every
  probe run in this plan is a foreground controller action; a subagent may write the probe and
  must not run it.
- **Every timing figure ships with a wall-clock uptime beside it.** A perf seat once reported
  12.7 s that was really 2.85 s because it measured the panel, not the build.

---

## The walker cost model is this parcel's regression net

`docs/benchmarks/scanline-p2/WALKER-MODEL.md` fits the walker to **max |residual| 0.27 cycles**
over 14 un-anchored fixtures, with `base = 3021.94` and eight slopes. That model is not
background reading — it is the acceptance criterion for every task that touches
`Parallax_*`:

> **Standing rule for Tasks 6-12.** Any task that changes a `Parallax_*` routine re-runs
> `tools/parallax_cost_probe.py --repeat 3` and lands in exactly one of two states:
> (a) **every fitted parameter unchanged** and the residual still ≤ 0.3 — recorded as such; or
> (b) **the model EXTENDED with the task's new parameter MEASURED**, one fixture per parameter,
> each varying one thing from a named neighbour, residual reported. A task may not land with a
> residual that grew and no parameter named. "The residual is the deliverable" is
> `WALKER-MODEL.md` §5's whole content, and it forced three model changes there.

Two model terms are already known to be moving:

- **`multiband = 23.21` is Step 4a's `.find_k` probe loop** (`parallax.emp:707-717`) — the
  cost paid once at `band_count >= 2` because at 1 band the loop body never runs. **Task 7
  rewrites `.find_k`.** That term is re-measured or retired; it is not carried.
- **`anchor` is two labelled regimes, not a parameter** (456.2 re-glue-only / 1204.7 shipped
  shape), with a named-but-unfitted missing parameter. **Task 1 is where that gets resolved**,
  and it is this parcel's flagship measurement deliverable.

---

## Trap ledger for this parcel

Design §8.5 requires each plan to enumerate the carried traps it touches. Transcribed for P3,
each with where it bites here.

| Trap | Where it bites in P3 |
|---|---|
| **VDP-port operand-vs-fetch bus behaviour** | The walker's inner loops write the HScroll buffer in RAM but the mode assert writes `$C00004` directly (`parallax.emp:574-579`). Near a VDP port, nominal cycle deltas neither hold nor fail predictably: the dense-body `-4(a2)` rider predicted 4 cyc/line from the previous parcel's absorption ratio and **measured 12, the full nominal**, while the parcel before it predicted nominal and measured a quarter of it. Do not book a cycle delta for any edit near a port write — measure the fixture pair. |
| **Measure-don't-book: three bookings were wrong this week** | `c2f9cfcd` "the booking was wrong by **6x**" (dense KIND hoist booked 24, measured 4); `0e5d49b7` "the booking **halved**, correctly"; the HBlank window's §2/§3 estimate was out by **2.5 spin iterations** because one term counted a trailing iteration that need not complete. Every P3 cost claim is a fixture-pair measurement or it is not a claim. |
| **deb2 appendix: a ZERO-BYTE label still moves the image** | Adding a zero-byte DEBUG-only proc moved `demo.bin` `aae04929 → 6710c1ac` with everything before `EndOfRom` identical — it was the deb2 appendix — while `s4.bin` did not move at all. **A release-CRC check on sonic4 alone would have missed it.** Every byte-accounting step in this plan checks all four shapes. |
| **Cross-seam carrier ripple** | New `Game.*` or cross-module RAM references inside a port-compiled engine module force a sigil isolation-port carrier injection and a repin row. This is systemic, not one-off (`bg_anim.emp`'s module-local `BGANIM_MAX_BANDS` mirror; `compression_selftest_port.rs`'s `OJZ_Act1_Descriptor` injection; the `DMA_Enq_Bytes_Frame` class). Tasks 5, 6 and 12 all add cross-seam names. Expect an **aeon+sigil pair** on those, and run sigil's suite with `--no-fail-fast` (cargo stops at the first failing binary otherwise; full green is the whole-workspace count, not a tail). |
| **`ab_runner`'s fixed-frame wall AND its scene-freeze blindness** | Two separate limits. (a) The four committed AB scenes **cannot return ALL EQUAL against a tick-rate change**: running the BASELINE ROM against itself at settle 180 vs 181 reproduces the same difference set. **Run the ±1-frame control before reading any DIFF as a finding.** (b) Those scenes poke `Debug_Scene_Freeze = 1`, so anything that only manifests under camera motion — which is most of Task 7 — is invisible to them by construction. Task 7's evidence is its own moving-camera instrument, not `ab_runner`. Also: `--new`/`--rom` need ABSOLUTE paths (a relative one resolves against the emulator's cwd and reads uninitialised RAM as a DIFF), and the committed scenes hard-code the SHARED checkout's `.lst` — copy them into the worktree, do not edit the committed ones. |
| **Clean-constant confound** | A constant measured "clean" is clean only against the code that existed when it was taken. `RASTER_STREAM_WORD_CYC` was "confirmed against hardware for the first time" at 30 and was 26 a day later once item 1 changed the handler, taking the whole window sweep with it. Every walker constant in `[parallax.cost_model]` was measured against **today's** walker; Tasks 7-10 change that walker, so those rows are stale the moment the task lands and Task 13 re-takes them. |
| **The hand-typed baseline term** | The P2 plan's own §5 figure (896 B) was half the measured value, and the effects-p3 baseline rows went camera-stale because their state was not reproducible. **No task in this plan may type a denominator into a step.** Read it from `tools/effects_budget_model.toml` at run time and name the row. |
| `extern()` poisons comptime-ness | `ram.emp:40`'s `extern("band_entry_len")` pin is directly in Task 8's blast radius. A ledger or size const that folds a link-time address stops the whole image being comptime and breaks the `first_mismatch` whole-image pins. Carry parameters; add bases at runtime. |
| Imported names don't travel into `comptime fn` bodies | Free names in a `comptime fn` resolve at the CALL SITE. A capability constant named inside a `pub comptime fn` body must be a literal held by a module-level pin (the `raster_dsl` pattern) — Tasks 5, 6 and 10 all add such bodies. |
| An `if` in block-tail position yields UNIT, silently | It mis-folded a capability mask to 0 during P1 and was caught only because the expected value had been derived independently. Tasks 5/6/10 extend `scene_caps()` and the forcer fold — flat accumulator over statement `if`s, never a nested if-expression. |
| `Label = 0` vacuous attachment | Every new attachment in P3 is a comptime ENUM VARIANT with exhaustive match. An `ensure` comparing a Label to an int is silently unevaluable and always passes (`scene_dsl.emp:243`, `preset.emp:52`, EMP_PITFALLS §3). |
| `refreeze --check` is not the goldens | It once passed with 16 golden ROM tests red. Any byte-moving task needs `--freeze NAME --ab REF` with prose emulator evidence, and the load-bearing line is the golden suite count (P1's was 3733/0, zero skips — a skip reads like a pass). |
| Span gates can measure the placer | Region pins include placer fill. `tools/demo_specialization_witness.py`'s docstring records that a whole-ROM-length pin was **rejected** for exactly this reason: every elision was absorbed by fill. Assert on the per-proc pins, never on an absolute region byte count. |
| A gate that asserts only "something failed" | Every poison perturbs the SUBJECT and names the specific mismatch, verified against a CONTROL build with the planted defect removed. Two-fixture differential form is required for span/budget gates. |
| Warning tallies are untracked | `SIGIL_WARNINGS=full` is a diagnostic. Never gate on a count. It IS useful as a dead-guard detector: a new `.emp` module outside the use closure has parse+scan coverage and **zero body elaboration**, so its ensures assert nothing. |
| `emp_expect_fail` sentinel drift | The lane's sentinel catches `--extra-entry` evaluating nothing. A diagnostic-count drift means a guard stopped firing or a new one started — investigate, never re-baseline. It earned its keep three times in P1. |

---

# PHASE 0 — INSTRUMENTS

> No engine code in this phase. Four of P3's six mechanisms have no instrument today; a
> mechanism that lands before the thing that can see it is the F2/dense defect, and this tree
> has the postmortem for it. **No Phase-1 task may reference a row Phase 0 did not measure.**

## Task 1: Resolve the anchor's two regimes — the flagship measurement

**Why this task exists:** `[parallax.cost_model]` carries `anchor` as **two labelled regimes**
(`anchor_cycles_reglue_only = 456.2`, `anchor_cycles_shipped_shape = 1204.7`) with
`anchor_status = "NOT CONSTANT"`, and `WALKER-MODEL.md` §8 says outright: "do not build a gate
on `anchor` without more fixtures." P3's re-glue work is the parcel that rewrites the anchored
overlay's neighbourhood, so it is where that parameter either gets a name or is proven absent.
Axis 1 — the one falsifiable budget axis in the tree — divides by this term.

**And the hypothesis on record is refutable from the published numbers.** `WALKER-MODEL.md`
§5(c) names the suspected missing parameter as "a per-band cost that DIFFERS between a flat
band and a sampling band", asserting it is collinear with `band_perline` "in every un-anchored
fixture (they all have uniform band types)". **That premise is false for W14 and W15**, which
are explicitly mixed — W14 is 2 bands with only the lower sampling, W15 is 3 with only the
lowest. Derive the consequence rather than taking it from here:

```
W7  − W4 = 21611 − 4540 = 17071   over 224 sampled lines
W14 − W5 = 13945 − 5409 =  8536   over 112 sampled lines
W15 − W6 = 12352 − 6255 =  6097   over  80 sampled lines
```

Each marginal is `(c_sampling_band − c_flat_band) + LINES × line_fg_only`. Subtracting the
first two pairs gives `line_fg_only = (17071 − 8536)/112`, and back-substituting leaves the
band-type delta at **zero to within a cycle on all three**. So in the UN-ANCHORED walker a
sampling band and a flat band cost the same, and §5(c)'s named parameter is not what the extra
**748 cycles** in W16 are. Step 1 re-derives this arithmetic independently and records the
verdict; Steps 2-4 design fixtures for what is actually left.

**Files:**
- Modify: `tools/parallax_cost_probe.py` (the `fixtures()` matrix at `:164`; `build()` at
  `:115` already accepts a per-band `shifts` list, so mixed-type fixtures need no new machinery)
- Modify: `tools/effects_budget_model.toml` (`[parallax.cost_model]`)
- Modify: `docs/benchmarks/scanline-p2/WALKER-MODEL.md` (§5(c) and §8 — correct the premise
  in the file that states it, do not leave the correction only here)

- [ ] **Step 1: Re-derive the band-type delta from the shipped fixtures and record the verdict**

Do the arithmetic above from the numbers in `WALKER-MODEL.md` §3 yourself. If it comes out
non-zero, this plan's derivation is wrong and that is the finding — report it. If it comes out
zero, §5(c)'s hypothesis is refuted for the un-anchored regime and §5(c) is edited to say so.

- [ ] **Step 2: Design fixtures that separate the remaining candidates for W16's extra 748**

W16 differs from W10/W12 in four ways at once — band count (4 vs 2/3), channel (BG vs FG),
sampled-line count (144 vs 224), and whether the overlay TURNS SAMPLING ON versus merely
rewriting shifts on bands that already sample. One fixture per candidate, each varying one
thing from a named neighbour, in the discipline that made the un-anchored fit 0-residual:

| new fixture | shape | isolates |
|---|---|---|
| `W17` | 2 bands, per-line, ROM shifts all flat, anchored, `dsb` turns BG sampling on below the split | the "turns sampling on" regime at W10's band count — **the decisive control**: if it reads ≈1204, band count is not the driver |
| `W18` | 4 bands, per-line, ROM shifts all flat, anchored, overlay writes FLAT shifts (sampling stays off) | the pure re-glue at W16's band count — the other half of the same 2×2 |
| `W19` | W16 with `dsa` (FG) instead of `dsb` | channel |
| `W20` | W16 with the split latched at a different line (change `Effects_World_Y[ch]`, not the camera) | split position, and it re-checks that `sampled_lines(split)` is accounting the partial screen correctly |

`W18` × `W17` is a 2×2 against `W10`/`W16`: if the 748 belongs to the regime it appears in both
"turns-on" cells and neither "rewrite" cell, independent of band count. **State the prediction
before running**, then measure — a fit that could not fail is what §5(b) is a postmortem for.

- [ ] **Step 3: Keep the three derived checks live on every new fixture**

The probe's existing checks are what stop an anchored fixture from measuring an early-out
instead of a split: `Parallax_Current_Config` still aimed at the fixture; `Replay_Record_Idx`
still 0 (the recorder never woke and wrote through the scratch); and `Parallax_Shadow_Bands`
tops read back showing a DIFFERENT top sequence from the un-anchored neighbour. **Poison
check 3** before trusting the new fixtures: set an anchored fixture's `pcfg_anchor_ch` to
`$FF` and confirm the run reports the tops as matching its neighbour and refuses, rather than
quietly measuring the un-anchored path.

- [ ] **Step 4: Fit, report the residual, and write the rows**

Either the anchored overlay becomes a **fitted parameter with a name** (and
`anchor_status` changes accordingly), or the regimes are re-recorded with the refuted
hypothesis replaced by whatever the 2×2 shows. A column excited by a single fixture is still
forbidden. Update the out-of-sample check against `ParallaxConfig_OJZ_Underwater` — the
existing +222.3 (1.1%) gap is the yardstick for whether the new parameterization is better.

- [ ] **Step 5: Commit**

```bash
git add tools/parallax_cost_probe.py tools/effects_budget_model.toml docs/benchmarks/scanline-p2/WALKER-MODEL.md
git commit -m "measure(p3): the anchored overlay's second regime — the 2x2 that names it"
```

---

## Task 2: The HScroll-buffer ramp instrument — built before curves exist — ✅ DONE 2026-08-20

**Why:** design §8.3's named instrument for curves is "after `Parallax_Update` on a pinned
camera state, read the HScroll buffer RAM and compare every line word in the curve span
against the comptime-expected ramp (derived, not copied); repeat across a camera sweep". There
is no such reader today. Building it after Task 10 would mean the mechanism's only witness is
a tool written to agree with it.

**Files:**
- Create: `tools/parallax_hscroll_probe.py`
- Create: `docs/benchmarks/scanline-p3/CURVE-INSTRUMENT.md`

- [x] **Step 1: Read and check the buffer against a ramp the tool DERIVES**

`Hscroll_Buffer` is `[u8; 896]` at `engine/ram.emp:270` — 224 lines × 4 bytes, FG word then BG
word. The expectation is computed from the fixture's own factors and layer height by the same
arithmetic the lowering will use, **never read off a neighbouring line or off the ROM**. Two
gate expectations copied from a nearby pin would have passed incorrect code twice in this tree.

- [x] **Step 2: Prove it red BEFORE any curve exists, against a hand-installed RAM ramp**

This is the whole point of the ordering. Write a synthetic ramp into `Hscroll_Buffer` through
the emulator's memory surface with the camera frozen, run the checker against a DIFFERENT
expected ramp, and confirm it fails naming the first mismatching line. Then run it against the
matching ramp and confirm it passes. **A checker that has never gone red is not an instrument.**

- [x] **Step 3: Add the moving-camera arm**

§8.3 says "repeat across a camera sweep (moving-camera requirement)" for a reason recorded in
memory: at-rest captures hide scroll artifacts. But the walker's cost arithmetic requires a
frozen camera (under sustained motion one logic tick spans two video frames and a per-frame
average stops being one call). **Those are two different runs and the tool must keep them
separate**: a frozen-camera arm for value checking at N pinned camera positions, stepped by
writing `Camera_X`/`Camera_Y` between frames rather than by holding a direction; and a
free-running arm that only asserts monotonicity/continuity, never a cycle count.

- [x] **Step 4: Commit**

```bash
git add tools/parallax_hscroll_probe.py docs/benchmarks/scanline-p3/CURVE-INSTRUMENT.md
git commit -m "instrument(p3): the HScroll ramp reader, red-first before a curve exists"
```

---

## Task 3: The re-glue instrument — shadow tops under a vertical sweep, and the transition-frame state

**Why (two reasons, both load-bearing):**

1. World-Y re-glue's claim is "layer tops stay glued to the background during vertical scroll".
   Nothing in the tree reads `Parallax_Shadow_Bands` across a vertical camera sweep today; the
   cost probe reads it at ONE frozen position as a fixture sanity check.
2. **P2 Task 12 is BLOCKED on two things, and this instrument closes one of them.** Blocker
   (b) is "there is no measured transition-frame reservation — neither Phase-0 camera state
   crosses a section boundary". The cost probe's own trick answers that without a real
   crossing: freeze the camera, then install `Parallax_Current_Config = A`,
   `Parallax_Target_Config = B`, `Parallax_Transition_Frames = N` in RAM. That is a live
   transition frame with both configs routed, measurable per-routine.

**Book the connection, and book its limit honestly.** A synthesized transition state exercises
`Parallax_Active_Config` routing, the reg `$0B` mode change and the per-band scroll lerp — the
three things `WALKER-MODEL.md` §8 lists as unmeasured. It does **not** exercise
`Parallax_StartTransition` or `Parallax_CheckBoundary`, which a frozen camera suppresses by
construction. So this task delivers **axis 1's transition-frame row** and, by scanning the DMA
queue at scanline 220 the way `engine_baseline_probe.py` does, axes 2 and 3's. It does **not**
close P2 Task 12: **blocker (a) — the section→scene join is a `Label` end to end
(`Sec.sec_parallax_config` → `EffectsPreset.ep_parallax` → `preset(parallax: Label = 0)`) —
is untouched by P3 and stays booked.** Do not report Task 12 as unblocked.

**Files:**
- Modify: `tools/parallax_cost_probe.py` (a `--transition N` mode; reuse the fixture installer)
- Create: `docs/benchmarks/scanline-p3/REGLUE-INSTRUMENT.md`
- Modify: `tools/effects_budget_model.toml` (transition-frame rows under `[parallax.cost_model]`)
- Modify: `docs/DEFERRED_WORK.md` (the "Scanline P2 Phase 2 — BLOCKED" entry: blocker (b)
  measured, blocker (a) restated as still open)

- [ ] **Step 1: The vertical-sweep shadow-top reader**

At each of N camera Y positions with `Debug_Scene_Freeze` on, run one frame and read all
`MAX_PARALLAX_BANDS` shadow tops plus the live band count. The **expectation is derived from
the authored world-Y tops and the frame's `Vscroll_BG`**, not from the previous position's
readback — a chained expectation drifts with the thing it is checking.

- [ ] **Step 2: Poison it against today's walker**

Today's Step 4a rebases plane-cell rows to screen lines from `Vscroll_BG`. Perturb
`Parallax_Current_Vscroll_BG` between the read and the expectation and confirm the checker
names the first disagreeing band index. If it passes, it is not reading what it claims to.

- [ ] **Step 3: The transition-frame arm and its rows**

Measure `Parallax_Update` (inclusive) and `Enqueue_Dirty_Buffers` in a synthesized transition
between the two shipped configs that differ most in mode — one per-cell, one per-line — so the
reg `$0B` change and the larger-of-the-pair HScroll length are both live. Scan the queue at
scanline 220 for the byte figure. Five boots, report spread, uptime beside every figure.

**Note the ordering contract while you are in here:** `Parallax_Update` tail-jumps
`Parallax_Step5_Vscroll` which tail-jumps `Parallax_Step4_Fill` — **Step 5 runs BEFORE Step 4**,
because Step 4a's rotation needs the current frame's `Vscroll_BG` (`parallax.emp:677-678`).
Task 7 must preserve or re-derive that; record it here so Task 7 does not rediscover it.

- [ ] **Step 4: Write the rows, marked for what they are**

```toml
# Transition-frame rows — SYNTHESIZED (camera frozen, configs installed in RAM), not a real
# section crossing: Parallax_StartTransition and Parallax_CheckBoundary do not run. This
# measures design §5's evaluation frame for axes 1/2/3 and closes P2 Task 12's blocker (b).
# Task 12's blocker (a) — the Label-typed section->scene join — is UNCHANGED and still blocks.
```

- [ ] **Step 5: Commit**

```bash
git add tools/parallax_cost_probe.py tools/effects_budget_model.toml docs/benchmarks/scanline-p3/REGLUE-INSTRUMENT.md docs/DEFERRED_WORK.md
git commit -m "measure(p3): shadow tops under a vertical sweep, and the transition frame's first row"
```

---

## Task 4: Axis 5 gets a denominator — the object-system SAT reservation

**Why:** Task 12 emits an engine-reserved SAT slot for the left-column mask, which design §5
prices in axis 5 "against a declared object-system reservation". That reservation was never
measured — `[scene_budget]` says `axis5_sprite_slots = "NO SUBJECT UNTIL P3 ... Phase 0
measured no row"`. A budget gate written against an unmeasured denominator passes while
enforcing a number nobody took; that is this plan family's founding lesson
(`EFX_BLANK_DELAY = 4`).

**Files:**
- Modify: `tools/engine_baseline_probe.py` (a SAT-occupancy arm)
- Modify: `tools/effects_budget_model.toml` (`[engine_reservation]`)
- Modify: `docs/benchmarks/scanline-p2/ENGINE-BASELINE.md`

- [ ] **Step 1: Measure SAT occupancy at the two DEFINED camera states**

Use the **same two states `ENGINE-BASELINE.md` §1 defines** (idle: OJZ act 1 section 0,
`Camera_X` 96 / `Camera_Y` 144; and max-diagonal) — a new state would make the reservation
incomparable with every other row. Read the sprite table and record: slots used, worst
per-scanline sprite count, and the pixels-per-line total against the H40 limits.

- [ ] **Step 2: Record the ceiling that actually binds**

Two different ceilings exist (total SAT entries, and the per-scanline sprite/pixel limits) and
the mask consumes one slot against the first while occupying one 8-px column against the
second. State which one the axis gates on and why. `ENGINE-BASELINE.md` §"what this does not
cover" already warns that the idle headroom is an upper bound because the level is nearly
empty of objects — carry that caveat onto this row explicitly.

- [ ] **Step 3: Write the row and supersede the "no subject" text**

- [ ] **Step 4: Commit**

```bash
git add tools/engine_baseline_probe.py tools/effects_budget_model.toml docs/benchmarks/scanline-p2/ENGINE-BASELINE.md
git commit -m "measure(p3): axis 5's reservation — SAT occupancy at the two defined states"
```

---

## Phase 0 checkpoint

**STOP.** Every row Tasks 1-4 create holds a measured number, or the Phase-1 task that would
divide by it does not start. Tasks 5-7 depend on no Phase-0 row and may proceed regardless;
Tasks 10 and 12 may not.

---

# PHASE 1 — THE MECHANISMS

## Task 5: Promote the two P3 capability bits and widen the specialization surface

**Why FIRST among the mechanisms:** `CAP_MULTI_DEFORM_TABLE = $0020` and
`CAP_FACTOR_CURVE = $0040` exist today only inside a **comment** at
`engine/level/scene_dsl.emp:105-107`, so `tools/scene_spans.py`'s `capability_bits()` cannot
see them and no span gate can measure their elision. `tools/test_scene_span_labels.py:50-51`
actively asserts that reserved bits are absent from the parse. Every later task in this phase
adds a gated block; without this task those blocks are ungated by construction.

**Files:**
- Modify: `engine/level/scene_dsl.emp` (`pub const` promotions; `scene_caps()`)
- Modify: `tools/test_scene_span_labels.py` (the reserved-bit assertion, and the
  longest-prefix uniqueness check now over 7 bits)
- Modify: `tools/scene_spans.py` if the prefix resolver needs it

- [ ] **Step 1: Promote the two bits and leave the other five in the comment**

Only the bits P3 lowers become `pub const`. `CAP_FG_SPRITE_STRIPS`, `CAP_BGANIM_BOUND`,
`CAP_DENSE_TIER`, `CAP_COMPUTED`, `CAP_DEGRADE` stay reserved — promoting a bit nothing raises
creates a span gate with no subject, which is the vacuous-gate shape.

- [ ] **Step 2: Re-run the longest-prefix uniqueness check over the widened set**

Span names resolve to a capability by longest matching prefix
(`effects_gates.py:859`: `s.startswith(cap[len("CAP_"):].lower())`). With `CAP_DEFORM` and
`CAP_MULTI_DEFORM_TABLE` both live, verify that no existing span name — the fill loop already
brackets `.cap_deform_sample_begin/_end` at `parallax.emp:1297/1421` — becomes ambiguous.
`test_scene_span_labels.py` already has this check; make it fail first by adding a deliberately
ambiguous name, then remove it.

- [ ] **Step 3: Byte accounting — this task must be ZERO-BYTE on all four shapes**

Nothing raises either bit yet, so sonic4's `SCANLINE_CAPS` stays `$001F`, demo's stays `0`, and
no gated block exists yet. **All four CRCs unchanged.** If any moves, a promotion leaked into
an emission path.

Run: `./build.sh`, `DEBUG=1 ./build.sh`, `./build.sh demo`, `DEBUG=1 ./build.sh demo`

- [ ] **Step 4: Commit**

```bash
git add engine/level/scene_dsl.emp tools/scene_spans.py tools/test_scene_span_labels.py
git commit -m "feat(scene): CAP_MULTI_DEFORM_TABLE and CAP_FACTOR_CURVE become gateable bits"
```

---

## Task 6: The per-line forcer derivation — ONE source, both twins

**Why:** design §2 makes this the reason "twin-key desync is impossible by construction": the
lowering owns the forcer set and feeds **both** the fill-side mode key and the
`engine.buffers` DMA-length key from one derivation. Today it is **two hand-written copies of
one decision** — `engine/level/parallax.emp:1011-1029` and `engine/system/buffers.emp:481-501`
are byte-for-byte the same `beq`/`bne` sequence in two files, each with a comment warning the
other exists. They read the same fields off the same `Parallax_Active_Config` result, so the
DATA is single-sourced and the CODE is not.

**Files:**
- Modify: `engine/level/scene_dsl.emp` (the forcer fold; retire the `precision` fence at
  `:469-470`; widen `scene_caps()`'s two ad-hoc booleans at `:536-538`)
- Modify: `engine/level/parallax.emp`, `engine/system/buffers.emp`
- Modify: `tools/effects_budget_model.toml`

- [ ] **Step 1: FIRST — reconcile 896 vs 1792 (correction C1). This blocks the rest of the task.**

`buffers.emp:156-162` declares ONE `Static_Hscroll_Line` at `dma_length(896)`. The live-queue
scan at scanline 220 recorded **two** 448-word entries. Both are in the tree; they cannot both
be a complete description. Read the queue yourself at the idle state, find every enqueue site
that can produce an HScroll entry, and write down which is true. **Do not price the forcer
until this is answered**, and do not answer it by picking the number that matches the spec.

- [ ] **Step 2: Author the forcer set as one comptime fold**

The exhaustive set, from design §2: `{ any H-deform table incl. shared, anchor_ch != NONE, any
curve layer, precision: line, any layer boundary not on the 8-px cell grid }`. Today's
`scene_caps()` implements only the first two, and `scene_dsl.emp:500` says so in a comment
that explicitly forbids widening it to guess at the rest — this task is the widening that
comment defers to. **Flat accumulator over statement `if`s**, never a nested if-expression
(it mis-folded a mask to 0 in P1).

Curve and off-grid arms are authored here but have no subject until Tasks 7 and 10. That is
correct ordering — the derivation is the single source, so it must exist before the mechanisms
that feed it — but it means the arms are dead code until then. **Say so in the code**, and put
the reachability question on Task 15's poison list rather than letting a dead arm read as
coverage.

- [ ] **Step 3: Retire the `precision` fence, and retire the derivation duplication**

`scene()`'s `ensure(precision != 1 || scene_deform_is_none(deform_bg) == 0, "P1: precision line
rides a zero-deform table ... standalone precision lowering lands with the forcer-set
derivation (P2/P3)")` is the guard this step replaces. Then make both runtime sites consume
one lowered key instead of re-deriving. Whether that key is a lowered config byte or a
comptime constant threaded through both is an implementation call — the requirement is that
**exactly one place decides**, and that the parallax and buffers spans still elide together
under `CAP_PER_LINE`.

- [ ] **Step 4: Byte accounting — sonic4 SHOULD be byte-identical here**

The 20 shipped scenes' forcer answers must not change: two carry `precision: PRECISION_LINE`
explicitly and five more use the same flat-pathed-zero-table idiom without the marking, and
all seven already lower to per-line via the deform-table arm. **If sonic4's image moves, the
new derivation disagrees with the old on a shipped scene — find which scene before proceeding,
do not repin.** demo must not gain: it has `SCANLINE_CAPS = 0` and both spans elide.

- [ ] **Step 5: Re-run the cost model (standing rule) — expect every parameter unchanged**

- [ ] **Step 6: Commit**

```bash
git add engine/level/scene_dsl.emp engine/level/parallax.emp engine/system/buffers.emp tools/effects_budget_model.toml
git commit -m "feat(scene): one forcer derivation feeds both mode twins"
```

---

## Task 7: World-Y re-glue — copy-all, capacity stays 8

**Why:** design §4.1. Layer tops are recomputed from world space each frame (the S3K
seed-and-search adapted to the shadow-layer layout). **The capacity ruling is explicit and
must not be quietly widened:** `MAX_PARALLAX_BANDS` stays 8 (≤7 authored when anchored),
Step 4a stays copy-all. World-Y buys ANCHORING and vertical gluing, not layer count; windowed
re-glue over >8 declared layers is a §9 future with its own re-derivation.

**Depends on:** Task 3 (instrument). **Byte-moving, and the model term `multiband` is inside
the code this task rewrites.**

**Files:**
- Modify: `engine/level/parallax.emp` (Step 4a, `:686-775`)
- Modify: `engine/level/scene_dsl.emp` (`layer()`'s two ensures at `:194-197`)
- Modify: `games/sonic4/data/effects/ojz_scenes.emp` if any authored top changes

- [ ] **Step 1: Relax `layer()`'s two ensures — into WIDER guards, not into nothing**

Both messages name this task. `world_y % 8 == 0` becomes the off-grid-legal form (and off-grid
now raises a per-line forcer through Task 6's fold — verify that edge, it is the coupling the
two tasks share). `world_y < 512` becomes an act-span bound: the number stops being the BG
plane height and becomes the act's, so it must be **derived from the act descriptor, not
typed**. A guard replaced by no guard is the failure mode; a guard replaced by a bound nobody
derived is the other one.

- [ ] **Step 2: Rewrite Step 4a's seed-and-search, preserving the Step-5-before-Step-4 contract**

`Parallax_Update` tail-jumps `Parallax_Step5_Vscroll` which tail-jumps `Parallax_Step4_Fill`,
because Step 4a's rotation needs the current frame's `Vscroll_BG` (`parallax.emp:677-678`).
Re-glue changes what Step 4a computes but not what it needs. If the new form does not need
`Vscroll_BG` first, the ordering may be simplified — **but that is a separate, stated change
with its own evidence**, not a side effect.

- [ ] **Step 3: Research step — what the references actually did, pointed**

Three questions, three sources, no ritual sweep:
- **S3K / S.C.E. `ApplyDeformation`** (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`):
  how the walker seeds from `Camera_Y_pos_BG_copy` and subtracts band heights to find the top
  scanline's band **plus its partial offset**. The partial offset is the part a naive port
  drops, and it is what makes the top band correct rather than one line off.
- **S2 MCZ** (`/home/volence/sonic_hacks/s2disasm/`): the `dc.b` row-height table plus world-Y
  gluing — S2's one authorable analog, and a smaller worked example of the same search.
- **TF4** (`.../thunderforce4_disasm/`): 8 layers from a FORMULA rather than a table. Not to
  copy — to check whether re-glue's per-frame search can be replaced by arithmetic for the
  even-spacing case, which is what OJZ mostly is. Re-verify against raw bytes; the bundled
  ANALYSIS.md mis-addresses in places (its layer base is `$8198`, not `$8000`).

- [ ] **Step 4: Run Task 3's instrument across the vertical sweep**

This is the acceptance evidence and `ab_runner` cannot substitute for it — the committed AB
scenes poke `Debug_Scene_Freeze = 1`, so a re-glue that is wrong under motion is invisible to
them by construction.

- [ ] **Step 5: Re-fit the model — `multiband` is re-measured or retired**

`multiband = 23.21` IS the `.find_k` probe loop this task rewrites. Re-measure W0..W6; if the
new form has no once-at-two-bands cost, the indicator column is removed and the removal is the
evidence, not an assumption.

- [ ] **Step 6: Byte accounting + landing lane**

Byte-moving on sonic4. demo: `Parallax_Step4_Fill` is one of the eight pinned procs in
`tools/demo_specialization_witness.py:93-102` (demo 176, sonic4 536) — **that pin moves and
must be RE-DERIVED from the build, never edited to match**. All four shapes; the deb2 trap
means demo can move on a label alone.

Expect a **repin + `refreeze --freeze NAME --ab REF` with prose emulator evidence**, and an
**aeon+sigil pair** if any pin row changes. `--check` is not the goldens.

- [ ] **Step 7: Commit**

```bash
git add engine/level/parallax.emp engine/level/scene_dsl.emp tools/demo_specialization_witness.py docs/benchmarks/scanline-p3/
git commit -m "feat(walker): world-Y re-glue — layer tops recomputed from world space, capacity unchanged"
```

---

## Task 8: The extended record — typed-data spike FIRST, then the addressing rewrite

**Why:** design §3.1 — record shapes are capability-dependent. No-new-capability scenes lower
to the existing 28-byte header + 10-byte entries **byte-identically**; extended records exist
only in games whose mask includes `CAP_MULTI_DEFORM_TABLE`. That makes the walker's field
displacements and strides **capability-selected comptime constants — a pervasive addressing
rewrite**, which §10 assigns to P3 by name, "typed conditional-data spike included".

**Depends on:** Task 5 (the bit), Task 7 (Step 4a's final shape). **This is the riskiest task
in the parcel.**

**Files:**
- Modify: `engine/level/parallax.emp` (the `band_entry` struct at `:69-80`; every field
  reference; the two Parcel-W copies)
- Modify: `engine/ram.emp` (`BAND_ENTRY_LEN` at `:38`, its `extern()` pin at `:40`,
  `Parallax_Shadow_Bands` at `:300`)
- Modify: `engine/level/scene_dsl.emp` (`scene_band()` lowering at `:1106-1128`)
- Modify: `tools/effects_budget_model.toml` (`[ram]`, axis 6)

- [ ] **Step 1: SPIKE the typed conditional data first, before authoring anything on it**

§3.1 states the alternative and its cost: "the proven untyped `if CAP {..} else {Data.empty}`
form forfeits size-annotation pins". Prove ONE record round-trips in the typed form — emitted,
size-annotated, and readable back — before the addressing rewrite depends on it. **This is
P2 Task 10's shape and P2 Task 10's step 2 governs it: if the spike fails, STOP and report;
take a ruling; do not invent a second emission path.** Registry-emission exclusivity is a
carried trap. The untyped fallback is available and is a worse-but-sound landing, not a
silent substitution — if it is taken, say so and record which pins were forfeited.

- [ ] **Step 2: Correct C5's record before relying on it**

The design's claimed pin (`ensure(sizeof(band_entry)==10)`) does not exist. What exists is
`parallax.emp:132-133` asserting **evenness only**, and `ram.emp:38-40`'s `BAND_ENTRY_LEN = 10`
mirror pinned through `extern("band_entry_len")`. The extended record changes that constant,
which sizes `Parallax_Shadow_Bands` (80 B today) and therefore moves RAM. Three consequences to
carry into the steps rather than discover: the evenness ensure must still hold for the extended
size; the `extern()` mirror is an EMP_PITFALLS §5 site; and axis 6's RAM row moves — and its
pool row was already found stale by ~2× in the unsafe direction, so **gate the DEBUG shape**
(6.5 KB free, not release's 16.7).

- [ ] **Step 3: Rebuild the two hand-unrolled copies as sizeof-derived generated copies**

`parallax.emp:927-929` (word+long+long, pre-decrementing from the entry tail) and `:956-958`
(long+long+word, forward). `comptime fn copy_band_entry()` at `:136-140` already generates this
shape and is NOT called by either site — that is the duplication to remove. Note the two sites
copy in **opposite orders** for cursor reasons; the generator must produce both directions or
the hardening is only half done.

- [ ] **Step 4: Bracket every capability-gated block (§3.3's emission convention)**

`.cap_multi_deform_table_<site>_begin` / `_end`, per the convention at `scene_dsl.emp:73-107`.
Path-level span gates cannot see an unbracketed block at all — the flat `.lst` drops
`$`-mangled locals.

- [ ] **Step 5: Byte accounting — sonic4 must be BYTE-IDENTICAL until a scene raises the bit**

sonic4's `SCANLINE_CAPS` is `$001F` and no shipped scene uses a per-layer deform ref yet, so
the extended record must not exist in any of the four images at the end of this task. §8.1's
**standing capability-off witness** is exactly this claim: a minimal capability-off fixture
scene stays word-equality-pinned in the sonic4 test lane as the permanent proof that the
zero-capability lowering path still emits legacy bytes after P2/P3 interleave conditionals.
Verify it is still reached (`SIGIL_WARNINGS=full` `[module.unreachable]` must not list it) —
an unreached witness asserts nothing.

- [ ] **Step 6: Cross-seam check**

The addressing rewrite touches `parallax.emp`'s struct, which `buffers.emp` reads. If any new
cross-module name appears, expect a sigil isolation-port carrier row and an **aeon+sigil pair**;
run sigil's suite with `--no-fail-fast`.

- [ ] **Step 7: Commit**

```bash
git add engine/level/parallax.emp engine/ram.emp engine/level/scene_dsl.emp tools/effects_budget_model.toml
git commit -m "feat(walker): capability-selected record shapes + the Parcel-W copies get generated"
```

---

## Task 9: Per-layer deform refs — `deform: own(table, shift_a/b, phase, speed)`

**Why:** design §2's three-variant ruling. `deform: none` and `deform: shared(phase)` describe
what the shipped scenes already are — `SceneDeform` today is per-PLANE, not per-layer
(`scene_dsl.emp:116-119`; a `Scene` carries `sc_deform_fg` and `sc_deform_bg`, and per-layer
control is the amplitude shift `ly_dsa`/`ly_dsb` only). `deform: own(...)` is the new variant,
and it is the one that trips `CAP_MULTI_DEFORM_TABLE` and rides Task 8's extended record.

**Depends on:** Task 8.

**Files:** `engine/level/scene_dsl.emp`, `engine/level/parallax.emp`

- [ ] **Step 1: Extend `SceneDeform` as an exhaustive comptime enum**

`None | Shared(Label, int) | Own(Label, int, int, int, int)`. Exhaustive match, never a
`Label = 0` default — "is a per-layer table attached?" must be answerable, and a Label-vs-int
`ensure` is silently unevaluable and always passes.

- [ ] **Step 2: `shared` must NOT trip the capability**

§2 is explicit: `shared(phase)` "is what WindyHaze/SkyHaze/haze_fg actually are; does NOT trip
MULTI_DEFORM_TABLE". Verify against the shipped scenes in `ojz_scenes.emp` that none of the 20
starts raising the bit. **The subset ensure at `scene_registry.emp:239` is one-sided
(`folded & ~declared == 0`)** — it catches a scene raising a bit the game did not declare, and
does NOT catch a scene that stops raising one. Derive the expected fold independently.

- [ ] **Step 3: The sampling loop reads a per-layer table pointer**

`.cap_deform_sample_begin/_end` (`parallax.emp:1297/1421`) currently hoists two table pointers
into `a5`/`a6` for the whole fill. Per-layer refs move that load per band. **That is a new cost
in the inner loop's setup path and it is measurable** — it is the task's model parameter.

- [ ] **Step 4: Measure the new parameter, one fixture varying one thing**

A fixture with N layers sharing one table versus N layers each with their own. Report the
residual.

- [ ] **Step 5: Byte accounting — sonic4 byte-identical unless a scene adopts `own`**

Adopting one is a separate authoring decision (PARK-1), not this task.

- [ ] **Step 6: Commit**

```bash
git add engine/level/scene_dsl.emp engine/level/parallax.emp tools/effects_budget_model.toml
git commit -m "feat(scene): deform own() — per-layer tables behind MULTI_DEFORM_TABLE"
```

---

## Task 10: Curves — the per-frame hoist and one specialized loop variant

**Why:** design §2/§4.1. A BG scroll factor may be `curve(from, to)`: the effective scroll ramps
per line across the layer as **an additive per-line delta over the layer's camera-tracked base
scroll**. The base term `camX >> factor` is preserved; the spread `(camX>>to − camX>>from)` is
computed **once per frame per curve layer in the band hoist with a bounded `divs.w` by layer
height**, never in the line loop and never as a multiply.

**Depends on:** Task 2 (instrument), Task 5 (the bit), Task 6 (a curve layer is a per-line
forcer). **Read the spec's own wording:** curves are a property of a **BG** factor (§2: "A BG
factor may be a curve(from, to)"), so the fill needs **one** new loop variant, not a product
with the existing FG/BG/both matrix. Author an `ensure` that says so rather than leaving it
implied.

**Files:** `engine/level/scene_dsl.emp`, `engine/level/parallax.emp`, `engine/level/parallax_dsl.emp`

- [ ] **Step 1: The bounded-`divs` hoist, with the bound ARGUED not assumed**

The precedent is `parallax.emp:651` (correction C3), whose bound is argued at `:640-645`:
divisor proven non-zero and range-bounded, dividend `ext.l`'d from a word so the quotient
cannot overflow. **Write the equivalent argument for layer height as the divisor** — a zero or
negative layer height must be impossible before the `divs`, not merely unlikely. This is the
tree's only other `divs` site; it is worth the paragraph.

- [ ] **Step 2: The loop variant, and the naming**

`Parallax_Fill_PerLine`'s existing loops are `.lp_both` (1350), `.band_fg_only`/`.lf_line`
(1380/1383), `.lp_bg` (1401) and `.lp_flat` (1442) — note the FG-only variant already breaks
the `.lp_*` convention and the header comment at `:1230` says "four specialized line loops".
Adding a fifth means **updating that comment too**; a stale roster comment is how the
`.lp_both`-uses-all-16 claim (C2) got into the design doc.

- [ ] **Step 3: The curve∧deform ensure — with the CORRECTED justification**

`ensure` a layer has a curve OR a deform ref, not both. **Do not copy the design's reason.**
The measured position is: `.lp_both` has 14 registers live (`d0-d7`, `a1-a6`); `a0` is spilled
at proc entry and dormant; `a7` brackets the proc. Write that. A guard whose stated reason is
checkably false gets deleted by the next reader.

- [ ] **Step 4: Anchor-inside-a-curve continues the curve**

§2's ruling: the per-line delta is indexed by **absolute screen line**, so a split changes
deform shifts below the boundary without re-parametrizing the curve. Order is unchanged —
static layer tops (Step 4a) first, then the anchor split (Step 4b). Assert the indexing;
this is exactly the kind of interaction that reads correct and renders wrong.

- [ ] **Step 5: Run Task 2's instrument — the derived-ramp check across the camera sweep**

Curves are camera-proportional, so a single frozen position tests almost nothing. Sweep.

- [ ] **Step 6: Measure the per-curve-line parameter and extend the model**

A new column alongside `line_fg_only` / `line_bg_only` / `line_both`. **Note what §5(b) proved
about this family:** the second channel on a shared line costs 50, not 76, because the loop
shares index and phase work — so a curve line's cost is not predictable from the deform line's
and must be its own fixture. Also: `line_both = 126.17`, **not** 152.5, is the standing proof
that summing per-channel costs is wrong here.

- [ ] **Step 7: Byte accounting + landing lane**

Byte-moving. `Parallax_Fill_PerLine` is a pinned demo proc (demo 2 — a bare `rts`; sonic4 372);
the sonic4 side moves and the pin is re-derived. Repin + `--freeze --ab` expected.

- [ ] **Step 8: Commit**

```bash
git add engine/level/scene_dsl.emp engine/level/parallax.emp engine/level/parallax_dsl.emp tools/effects_budget_model.toml
git commit -m "feat(walker): curve layers — per-frame spread hoist, one specialized loop"
```

---

## Task 11: Vscroll-split lowering — per-layer vertical depth

**Why:** design §2's ruled vertical mechanism set. Per-layer vertical depth = mid-frame
whole-plane VSRAM changes at layer boundaries, lowered to the **existing** `fx_vscroll_split`
raster op. Each boundary with a distinct v-factor is one raster fire, priced in axis 4.

**The tree's position, precisely:** `fx_vscroll_split` exists
(`engine/effects/raster_dsl.emp:590-592` — `fire(line, [stream_vsram(2, [offset])])`) and is
called from level data by hand (`ojz_effects.emp:529, 739`). **Nothing lowers into it**, and
there is no call site inside `engine/level/parallax.emp`. Today `Parallax_Step5_Vscroll` (the
VBlank path) and `fx_vscroll_split` (the HBlank path) both write plane-B whole-plane vscroll
through two independent routes with nothing routing one through the other. This task adds the
lowering; it must not add a second runtime mechanism.

**Depends on:** Task 7 (layer boundaries are world-Y after re-glue, and the fire line follows
the camera).

**Files:** `engine/level/scene_dsl.emp`, `games/sonic4/data/effects/ojz_scenes.emp`

- [ ] **Step 1: A per-layer v-factor attachment that lowers to `fx_vscroll_split`, not beside it**

- [ ] **Step 2: The two-writer interaction is the risk — state and check it**

Step 5 writes `Vscroll_Factor` in VBlank; the lowered split writes VSRAM mid-frame. A scene
using both is asking two writers to agree about the same plane-B word. Either forbid the
overlap with an `ensure` or define the precedence — **and whichever, the check goes in this
task**, because "both paths write it and nothing coordinates them" is the current state and
lowering into it makes the collision authorable for the first time.

- [ ] **Step 3: Instrument — the existing raster gate machinery, with its carried caveats**

§8.3: arm words + `memory_hash`, the **VSRAM N+1 landing model**, and the
emulator-disagreement caveat. Never CRAM reads (frame-latched). The `raster_source` gate is
the only one that observes the handler INTERPRETING the program rather than asserting its
words — it is the shape to follow.

- [ ] **Step 4: Axis 4a already owns per-fire spacing — do not build a parallel estimate**

The ledger's fire costs ARE `fire_cost_cycles` summed over the lowered program. A parallel
estimate is the drift the DSL pins exist to kill. Axis 4b's budget is enforced inside
`raster_program()`'s `check_hint_total` (`scene_dsl.emp:815-820`), not per-scene, for the same
Label-join reason that blocks P2 Task 12 — a new split fire raises that total and must be
checked there.

- [ ] **Step 5: Commit**

```bash
git add engine/level/scene_dsl.emp games/sonic4/data/effects/ojz_scenes.emp
git commit -m "feat(scene): per-layer vertical depth lowers to the vscroll-split fire"
```

---

## Task 12: Left-column mask emission — and axis 5 gets its first subject

**Why:** design §2 makes the declaration MANDATORY: any scene using per-column VSRAM must
declare `left_column_mask: sprite_mask | factor0_lock | accept`. The artifact is silicon —
with non-zero plane-B HScroll the leftmost partial column renders at V-scroll 0 regardless of
VSRAM[0], and every commercial game either masked it with a sprite strip or shipped it.

**The tree's position:** the defect is documented in comments only
(`engine/level/parallax.emp:416-424`, listing the same three mitigations) and booked at
`docs/DEFERRED_WORK.md:2248-2251`. `FACTOR_0` exists and works (`parallax_dsl.emp:26`) — that
is the `factor0_lock` policy, already available as an authoring choice. `sprite_mask` does not
exist: `grep` for `left_column_mask|sprite_mask|factor0_lock` across `engine/` returns **zero**
hits, and no sprite-mask auto-placement code exists anywhere.

**Depends on:** Task 4 (axis 5's reservation). **This task is what gives axis 5 a subject.**

**Files:**
- Modify: `engine/level/scene_dsl.emp` (the mandatory declaration + the enum)
- Modify: `engine/level/parallax.emp` or the object system (the reserved SAT slot)
- Modify: `games/sonic4/data/effects/ojz_scenes.emp` (declare the policy on the v-deform scenes)
- Modify: `tools/effects_budget_model.toml`, `docs/DEFERRED_WORK.md:2248-2251`

- [ ] **Step 1: The declaration is mandatory and the ensure says which scene**

An exhaustive comptime enum; a v-deform scene without one fails the build naming the scene.
`accept` is a real choice and must be spellable — "shipped it" is what Gynoug did and it is a
legitimate authoring answer, not a loophole.

- [ ] **Step 2: `sprite_mask` = one engine-reserved SAT slot, emitted at scene install**

Engine-owned slot, 8-px column strip. **The MD1-vs-MD2 fill-value question is UNPINNED** in the
research synthesis ("verify before depending on it") — if the mask's correctness depends on
what the partial column fetches, that is a BLOCKED item to report, not to assume.

- [ ] **Step 3: Price it in axis 5 against Task 4's measured reservation**

Read the reservation from the toml at run time. Do not type it.

- [ ] **Step 4: Close the DEFERRED_WORK booking or restate what is left**

`DEFERRED_WORK.md:2248-2251` says "blocked by: sprite system + zone level data hooks". If this
task unblocks it, close it in the same change. If only `factor0_lock`/`accept` land and
`sprite_mask` is deferred, **say which** — a partially-closed booking that reads as closed is
worse than an open one.

- [ ] **Step 5: Commit**

```bash
git add engine/level/scene_dsl.emp engine/level/parallax.emp games/sonic4/data/effects/ojz_scenes.emp tools/effects_budget_model.toml docs/DEFERRED_WORK.md
git commit -m "feat(scene): left_column_mask is mandatory, and axis 5 gets a subject"
```

---

# PHASE 2 — LEDGER, GATES, LANDING

## Task 13: Re-fit the model over the walker P3 leaves behind

**Why:** the clean-constant confound. Every row in `[parallax.cost_model]` was measured against
the walker as it stood on 2026-08-19. Tasks 7-10 changed it. Those rows are stale by
construction, and axis 1's comptime budget divides by them.

**Files:** `tools/effects_budget_model.toml`, `docs/benchmarks/scanline-p2/WALKER-MODEL.md`,
`engine/level/scene_dsl.emp` (the `SB_*` constants and `scene_axis1_*`)

- [ ] **Step 1: Re-run the full fixture set, including Task 1's additions**
- [ ] **Step 2: Report the residual, and the out-of-sample check against the live config**

The existing out-of-sample yardstick is `ParallaxConfig_OJZ_Underwater`: predicted 19288.7,
measured 19511, gap +222.3 (1.1%). A new parameterization that widens that gap is worse even
if its in-sample residual is smaller — §6 exists because the per-channel model fit the fixtures
perfectly and predicted 7100 against a measured 19511.

- [ ] **Step 3: Update axis 1's derivation, not just its numbers**

`axis1_reservation_cycles = 23894` is `idle_main_loop_cycles 35125` **less the walker's own
`idle_parallax_update` 19511** (charging a scene for the walker while leaving the baseline
walker in the reservation double-counts the thing being budgeted) **plus** `idle_vblank_cycles
8280`. If the walker's idle cost moved, that subtraction moves with it.

- [ ] **Step 4: State axis 7's status honestly**

`axis7_computed_handler_pins` still says "NO SUBJECT UNTIL P3". P3 gave it none. Rewrite the
row to say so and name what would (§10's list has no computed handlers in P3 or P4).

- [ ] **Step 5: `effects_budget_check` provenance rows**

`[symbols]` pins provenance, never enforcement. Every changed constant needs its row updated or
the drift detector reports the wrong authority.

- [ ] **Step 6: Commit**

```bash
git commit -am "measure(p3): the walker re-fitted over its own rewrite, residual reported"
```

---

## Task 14: The axis-5 budget row, gate and ledger equate

**Why:** design §5 axis 5. It has a subject (Task 12) and a reservation (Task 4) for the first
time.

**Files:** `engine/level/scene_dsl.emp`, `games/sonic4/data/effects/scene_registry.emp`,
`tools/scene_budget_report.py`, `tools/effects_budget_model.toml`

- [ ] **Step 1: Enforce comptime in `scene_budget_enforce()`, aggregate `max`**

Not `sum` — the P2 ratification stands: one scene is live at a time, and a sum over the shipped
20 refuses a registry that demonstrably runs. The pairwise sum belongs to the transition frame
(P2 Task 12, still blocked on the Label join).

- [ ] **Step 2: Publish the ledger rows as `pub equ`**

`pub equ`, never `pub const` — a `const` is name-resolution-only and mints no symbol, so the
formatter cannot see it. Follow the existing naming (`SceneBudget_Axis5_<Metric>`) and add the
rows to `REQUIRED_ROWS` in `tools/scene_budget_report.py` so `--check` fails loud when a row
stops being published (the readback regressing is silent by nature).

- [ ] **Step 3: Is it FALSIFIABLE? Measure, and if not, book it with its unlock condition**

`[scene_budget]`'s falsifiability section is the model to follow: of P2's four enforced axes,
exactly one has an input that can cross its budget, and the other three were **booked with
their unlock conditions rather than given faked poisons**. Determine which axis 5 is by
measurement, and write the answer into the toml either way.

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(p3): axis 5 enforced comptime, with its falsifiability measured"
```

---

## Task 15: Poisons — red-first, two-fixture differential, one unit over

**Why:** §8.2. Every new ensure gets a poison under `games/sonic4/test/poison/` as an
`emp_expect_fail` CASES row. EFX-9 is the "built carefully, run by nothing" postmortem, and
the lane's sentinel is the guard against the whole lane going vacuous.

**Files:** `games/sonic4/test/poison/*.emp`, `tools/emp_expect_fail.py`

- [ ] **Step 1: One poison per new guard**

At minimum: curve∧deform on one layer (Task 10); capacity under re-glue **plus** an anchor
(count+1 > 8, Task 7 — the existing `poison_scene_capacity.emp` is the neighbour); an off-grid
top that exceeds the derived act span (Task 7 — off-grid is now legal, so the poison must
target the new bound, not the retired one); a v-deform scene with no `left_column_mask`
(Task 12); the twin-key agreement (Task 6); the extended-record size pin (Task 8).

**Each exceeds by exactly ONE unit.** A poison that blows a bound by an order of magnitude can
pass for the wrong reason.

- [ ] **Step 2: Red-first, against a CONTROL build with the defect removed**

That control is what separates "the intended guard fired" from "something failed". P1's mask
poison is the two-fixture reference: fixture A PASSES and fixture B fails, differing in exactly
one authored field and one capability bit, **with A's passing measured rather than assumed**.
Note P1's own footnote — `fold_caps([A])` would make the subset test `(x & ~x) == 0`, true for
every input and evidence of nothing, so A's declared word is hand-derived.

- [ ] **Step 3: Kill the dead-arm question from Task 6**

Task 6 authored curve and off-grid forcer arms before their mechanisms existed. Now they exist.
A poison that raises **only** the curve forcer, and one that raises **only** the off-grid
forcer, prove each arm is reached and correct. Without them Task 6's fold has two arms nothing
ever evaluated.

- [ ] **Step 4: Sentinel and count**

Run: `DEBUG=1 ./build.sh` — expect `emp_expect_fail: OK — N/N cases` with N raised by exactly
the number added, sentinel PASS. A diagnostic-count drift means a guard stopped firing or a new
one started. **Investigate; do not re-baseline.**

- [ ] **Step 5: Commit**

```bash
git add games/sonic4/test/poison/ tools/emp_expect_fail.py
git commit -m "test(p3): one red-first poison per new walker guard"
```

---

## Task 16: The demo witness and the span gates, re-derived

**Why:** P3 changed six of the eight procs the demo witness pins, and every span gate's
expectation must come from the capability mask rather than a table.

**Files:** `tools/demo_specialization_witness.py`, `tools/scene_spans.py`,
`tools/effects_gates.py`

- [ ] **Step 1: RE-DERIVE `DEMO_SPECIALISED_PROCS`, never edit it to match**

The current pins are `Enqueue_Dirty_Buffers` 514/570, `Parallax_Active_Config` 6/18,
`Parallax_Fill_PerLine` 2/372, `Parallax_StartTransition` 90/118, `Parallax_Step4_Fill`
176/536, `Parallax_Step5_Vscroll` 62/144, `Raster_GetChannelBand` 8/50, `Vscroll_Write` 26/118
(`tools/demo_specialization_witness.py:93-102`). Read the new sizes from the build's `.lst`.
**There is no `PINNED_DEMO_LEN` and there must not be one** — the docstring at `:32-38` records
that a whole-ROM-length pin was rejected because every elision was absorbed by placer fill and
it "would have caught this poison for the wrong reason".

- [ ] **Step 2: The two new capabilities must ELIDE MEASURABLY from demo**

demo has `SCANLINE_CAPS = 0`. A capability that elides zero bytes from demo is either
unreachable or not actually gated. Record the delta per capability.

- [ ] **Step 3: Two-fixture differential, and do not measure the placer**

Each span gate compares sonic4 (`$001F` plus whatever P3 raises) against demo (`$0000`) and
asserts the DIFFERENCE matches the mask. Never an absolute region byte count — fill moves it.

- [ ] **Step 4: Run the mandatory lane**

Run: `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`
Paste totals + exit code into the merge evidence. **Mandatory ritual** — this parcel touches
`engine/level/*` and `engine/system/buffers.emp`; the CLAUDE.md rule names
`engine/effects/*`, `engine/level/bg_anim.emp` and `engine/system/buffers.emp`, and Task 6
touches the third.

**Naming caveat while you are in this file:** `effects_gates.py`'s `scene:mid_band`,
`scene:suppressed`, `scene:above_screen`, `scene:dense` gates are **raster_dsl fixture scenes,
not `scene_dsl` `Scene` values**. Two different things named "scene" in one gate list. Do not
wire a P3 scene gate into that namespace without renaming.

- [ ] **Step 5: Commit**

```bash
git add tools/demo_specialization_witness.py tools/scene_spans.py tools/effects_gates.py
git commit -m "gate(p3): witness pins and span gates re-derived over the new walker"
```

---

# Landing

- [ ] **All four shapes build:** `./build.sh`, `DEBUG=1 ./build.sh`, `./build.sh demo`,
      `DEBUG=1 ./build.sh demo`. Record all four CRCs and lengths.
      **Never land on `FAST=1`** — it skips every verification lane and prints a banner saying so.
- [ ] **Full tool suite:** `python3 -m pytest tools/ -q` — **aggregate totals, never a tail**
      (a tail-45 once hid 16 failures behind a merged "green").
- [ ] **Expect-fail lane:** N/N with the sentinel PASS.
- [ ] **Effects gate lane:** `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`
      — totals + exit code in the merge evidence.
- [ ] **`s4lint`, `effects_budget_check`, `verify_level_bin`** green; row counts recorded.
- [ ] **Byte accounting per task**, all four shapes each time — the deb2 appendix means a
      zero-byte label moves demo while sonic4 release does not.
- [ ] **`ab_runner` on the four committed scenes, with the ±1-frame control run FIRST.**
      This is a byte-changing parcel, so "ALL EQUAL" would be a warning, not a pass — but the
      scenes freeze the camera, so they cannot see Task 7 at all. Say which differences were
      predicted and enumerate them; an unenumerated DIFF is unexplained, not accepted.
- [ ] **Repin + `refreeze --freeze NAME --ab REF`** with prose emulator evidence.
      `--check` is NOT the goldens; the load-bearing line is the golden suite count with
      **zero skips** (a skipped golden reads like a pass).
- [ ] **Merge as an aeon+sigil PAIR** if any sigil-side change was needed — neither half builds
      without the other, and the sigil registry is global across worktrees.
- [ ] **P1 §8's deferred differential is now DUE.** The P1 gate evidence ruled its runtime
      spot-check tautological because all four images were byte-identical, and stated the
      unlock: "if the images ever diverge (a future parcel that moves bytes deliberately, e.g.
      P2 specialization), this test becomes a real differential and should be run then, against
      the last byte-identical reference." P3 moves bytes deliberately. **Run it.**
- [ ] **Doc sync in the same change:** `docs/ENGINE_ARCHITECTURE.md`'s parallax sections,
      `docs/DEFERRED_WORK.md` (the left-column booking, the P2 Task 12 blocker restatement,
      anything Phase 0 closed), and `WALKER-MODEL.md`. The architecture doc is the source of
      truth; if code diverges from it, one of them is wrong.

---

# What P3 must leave true for P5 to start

P4 is conditional on ledgers (BgAnim binding, and the degradation valve **only if** the OJZ
showcase scenes' ledgers demand it — the owner's standing lag disposition is "accept"). P5 is
the Aurora handoff. **This plan does none of P5's work**; what follows is the state P3 owes it,
so P5's first session is a spike and not an archaeology run.

1. **Every P3 mechanism is reachable through a scene constructor, not only through a runtime
   field.** `effects_gen.py` emits `.emp` that calls the SAME constructors the hand path uses.
   A mechanism reachable only by hand-writing a lowered record has no generator path at all.
2. **Every new constructor parameter is JSON-expressible.** Enum variants map to tagged
   objects; `points[256]`/bulk deform data goes out as `.bin` + `embed()` (the
   `inject_editor_bg.py` precedent), never as a literal array in JSON. A parameter whose only
   spelling is a comptime expression cannot cross the seam.
3. **Computed-handler refs, if any ever appear, are registry INDICES.** Never a symbol string
   folded into a comptime image — `extern()` poisons comptime-ness. P3 adds none, which is the
   easiest way to leave this true; do not break it incidentally.
4. **The constructor set's free names are known and collision-checked.** P5's generator emits
   a FIXED generator-owned `use` preamble checked against the helper-closure collision gate.
   P3 adds names to a DSL that already injects names as generic as `layer`, `scene`,
   `no_layer` — and `band` had to be renamed `cfg_band` across 44 sites in P1 because it
   collided with `raster_dsl.band`. **Every name Tasks 5-12 add is checked against
   `tools/emp_helper_closure.py`'s disjointness before landing**, and the P1-tail item
   "move `engine.level.scene_dsl` into sigil's `COMPTIME_HELPERS`" is the parcel that makes
   that check automatic (still open, still a paired aeon+sigil change).
5. **Error text is the Aurora user's error surface.** P5 ships RAW sigil `ensure` text; message
   wrapping is the Aurora lab phase's problem. So every `ensure` message P3 writes should name
   the scene, the field and the number — the ones in `scene_dsl.emp` today are the standard.
6. **The ledger renders every axis a scene can spend.** P5's authors need `--check` to tell
   them what a scene costs. After Task 14 that is axes 1/2/3/5 plus the summary rows; axis 4b
   remains enforced in `raster_program()` and axis 7 has no subject. **Say that in the report
   output**, so an author does not read a short list as a complete one.
7. **`schema: 1` is not P3's to write, but the JSON shape is P3's to not preclude.** The
   generator will REFUSE `schema != 1` and there is no migration machinery until the Aurora lab
   phase — so a P3 constructor signature that will obviously need a breaking change should be
   flagged now rather than shipped into a format with no migration story.

---

# PARK — owner decisions, not tasks

Marked rather than decided. Each is design-changing or taste-adjacent, and none blocks a task
above; each would change what the parcel ships.

| # | Question | Why it is the owner's |
|---|---|---|
| **PARK-1** | **Should any shipped OJZ scene actually ADOPT the new mechanisms?** Tasks 9-12 make `deform: own`, curves, per-layer vertical depth and the sprite mask authorable. Nothing above turns one on. Doing so is a visual change to the shipped game and it moves every image. | Visual behaviour + the byte-identity posture. The engine work and the content decision are separable and this plan separates them deliberately (the standing split: engine decisions are the assistant's, content sourcing is the owner's). |
| **PARK-2** | **Which `left_column_mask` policy does OJZ ship?** `sprite_mask` costs a SAT slot and an 8-px strip; `factor0_lock` costs the plane-B parallax on that layer; `accept` ships the artifact — and shipping it is what several commercial games did. | Pure visual taste, with a budget consequence on axis 5. |
| **PARK-3** | **Is curve∧deform on one layer worth reopening?** It is a §9 non-goal on register-file grounds, and correction C2 shows the stated reason overcounts by two (14 live, `a0` spilled). Reopening needs a measured register-allocation design, not an argument. | The §9 ruling is the owner's to revisit; the correction alone is not a reason to. |
| **PARK-4** | **Does the OJZ showcase want more than 7 anchored layers?** Capacity stays 8 by ruling; windowed re-glue over >8 is a §9 future with its own Step-4a re-derivation. If the showcase's answer is yes, that is a separate parcel and P3 should know before it lands. | Scope of the mega-act/showcase goal. |
| **PARK-5** | **Slack policy when a hero scene exceeds axis 1.** `budget_class` is designed (per-scene override resolved against the game's class table in `game.emp`) but unbuilt. The alternatives are: raise the budget with measured evidence, refuse the scene, or ship `budget_class`. | A margin question, and the design explicitly makes hero-scene overrides an authoring policy. |
| **PARK-6** | **Normalizing the two P1 byte-identity BRIDGES** (`layer_mask_raw: $1F` on OJZ_Default/Underwater, `v_deform_shift_raw: 0` on SkyHaze). They are hygiene, not features; normalizing is byte-moving and needs its own repin and `--ab`. P3 already moves bytes, so folding them in is cheap — **and folding a hygiene change into a mechanism parcel is exactly what "two byte-moving changes in one branch" warns against.** | Cheap but not free, and the owner has ruled once that these get their own parcel. |
| **PARK-7** | **Does the shipped `precision` field's current value mean anything?** Two of 20 scenes are marked `PRECISION_LINE`; five more use the identical flat-pathed-zero-table idiom without the marking. The field's values today are a migration default, not a considered claim. Task 6 makes the field load-bearing — which makes those five a decision. | Authoring intent on shipped content. |

---

## Dependency summary

```
Phase 0 (instruments, no engine code)
  T1 anchor regimes ──────────────┐
  T2 HScroll ramp reader ─────┐   │
  T3 re-glue + transition ──┐ │   │   (T3 also closes P2 Task 12's blocker (b) only)
  T4 axis-5 reservation ──┐ │ │   │
                          │ │ │   │
Phase 1 (mechanisms)      │ │ │   │
  T5 CAP bits ────────────┼─┼─┼───┼──┬──┬──┐
  T6 forcer derivation ◄──┼─┼─┼───┘  │  │  │
  T7 world-Y re-glue ◄────┼─┼─┴──────┘  │  │
  T8 extended record ◄────┼─┼───────────┴──┤  (needs T5, T7; SPIKE first)
  T9 per-layer deform ◄───┼─┼──────────────┘  (needs T8)
  T10 curves ◄────────────┼─┴─────────────────  (needs T2, T5, T6)
  T11 vscroll-split ◄─────┼───────────────────  (needs T7)
  T12 left-column mask ◄──┴───────────────────  (needs T4)

Phase 2
  T13 re-fit model      (needs T7-T10)
  T14 axis 5 gate       (needs T4, T12)
  T15 poisons           (needs every new ensure)
  T16 witness + spans   (needs all of Phase 1)
```
