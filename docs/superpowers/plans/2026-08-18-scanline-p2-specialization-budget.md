# Scanline Services P2 — Specialization + Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the scene model pay for itself — comptime-elide every capability a game does not use, and put every scene under a budget whose denominators are measured rather than assumed.

**Architecture:** Three phases, each an atomic landing cluster (design spec §10's rule: gates + poisons in the same cluster, master never half-migrated). **Phase 0 is measurement and lands FIRST**, because P2's budget half is `pool − engine_reservation` and every one of those denominators is currently a NEEDS-MEASUREMENT row. Phase 1 adds `if Game.SCANLINE_CAPS & CAP_X` gating with the bracketing-label convention its span gates require. Phase 2 publishes per-scene ledger consts and checks them against the Phase-0 numbers.

**Tech Stack:** sigil `.emp` (comptime lowering, `ensure`, `emp_expect_fail` poisons), Python gate tools under `tools/`, **oracle** for all Phase-0 profiling (oracle-next has no profiler instrument yet — see "Instrument" below; design §8.3's oracle-next target applies to Phases 1-2's runtime checks and to Phase 0 only once a profiler surface lands there).

---

## Why Phase 0 is first

The design doc lists the measurement program at §8.4 and the budget model at §5, and it would be natural to build the gates and then fill the numbers in. **Do not.** Substrate sweep item 1 is the cautionary case, closed 2026-08-18: `EFX_BLANK_DELAY = 4` was a constant fitted to one op shape, enforced by an author-facing guard, and wrong for every other shape for as long as nothing measured it. A budget gate written against an unmeasured denominator is the same defect with a bigger blast radius — it will *pass*, and it will be enforcing a number nobody took.

Phase 0 produces data and nothing else. No gate in Phases 1-2 may reference a row Phase 0 did not measure.

## Instrument: PHASE 0 RUNS ON ORACLE

Design §8.3 points P2's runtime verification at oracle-next. **For Phase 0 that is not yet possible and this plan does not pretend otherwise.**

Confirmed with the oracle-next session 2026-08-18: **oracle-next has no profiler instrument at all.** None of its 31 bus methods is profiler-shaped. So the HInt/VInt question is neither reproduced nor fixed there — it is absent, and there is nothing to migrate onto.

**Phase 0 runs on oracle, full stop.** Every row it produces carries the standing oracle caveat: `interrupts.hint` is HBlank **plus** VBlank, because oracle buckets an interrupt by comparing handler entry PC against `0x78` and Aeon's `VBlank_Handler` is a ROM address that never matches — so both handlers land in one bucket and the counter reads as neither. **Per-routine rows keyed by entry address are mandatory; `interrupts.hint` is never a valid source.** Documented at the top of `tools/raster_cost_probe.py`.

This is a silent wrong number rather than a missing one, which is why the discipline is non-negotiable rather than a preference.

**When a profiler surface does land on oracle-next**, its design is already pinned on their side: HInt and VInt as separate buckets keyed by interrupt **cause**, never by handler-entry-PC matching, with Aeon's finding cited as the measured counterexample. At that point Task 1 becomes a genuine cross-instrument parity check. Until then it is a regression check of oracle against itself (see Task 1).

**Standing caveat carried from oracle-next:** absolute cycle claims keep oracle as the reference while oracle-next's instruction-granularity slop is open. Do not assert oracle-next cycle parity in any row this plan produces.

## Trap ledger for this parcel

Design §8.5 requires each plan to enumerate which carried traps it touches. This parcel touches:

| Trap | Where it bites here |
|---|---|
| `extern()` poisons comptime-ness | Ledger consts (Task 10) must not fold a link-time address, or the whole image stops being comptime |
| Imported names don't travel into `comptime fn` bodies | Any capability constant named inside a `pub comptime fn` body must be a literal held by a module-level pin — the `raster_dsl` pattern. A name the *owning* module declares DOES travel when that module is glob-imported |
| `Label = 0` vacuous attachment | Capability-gated blocks that elide to nothing must be proven absent, not proven zero |
| `refreeze --check` is not the goldens | Any byte-moving task here needs `--freeze NAME --ab REF` with prose emulator evidence |
| Warning tallies are untracked | Never gate on a warning count; `SIGIL_WARNINGS=full` is a diagnostic, not a gate |
| Registry-emission exclusivity | `scene_registry` stays the sole emission path; specialization must not add a second |
| Span gates can measure the placer | Region pins include placer fill — a span that "differs by shape" may be measuring fill, not code |
| A gate that asserts only "something failed" | Every poison must perturb the SUBJECT and name the specific mismatch |

---

# PHASE 0 — MEASUREMENT

## Task 1: Re-confirm oracle's own figures before building budgets on them

**Why this task exists:** an instrument is a claim until something checks it, and Phase 0's remaining four tasks all take numbers from this one. **This was originally written as an oracle-next parity check; it is not, because oracle-next has no profiler.** It is a regression check of oracle against a known-good reference — cheap, and it catches the case where something in the toolchain moved between the 2026-08-18 measurement and Phase 0's run.

The reference is unusually good: the eight raster cost fixtures were re-measured on oracle on 2026-08-18 against the current (post-substrate-item-1) wire format, and every one matched its cost model to the cycle, 3 boots, spread 0.

**Files:**
- Reference: `tools/raster_cost_probe.py` (the existing probe and its per-routine methodology)
- Reference: `engine/effects/raster_dsl.emp` — the eight pinned fixture `ensure`s
- Create: `docs/benchmarks/scanline-p2/INSTRUMENT-PARITY.md`

- [ ] **Step 1: Record the reference values**

These are the oracle figures from 2026-08-18, marginal cost per fire, `(fixture − F0) / n`, F0 = 572:

| Fixture | n | cyc/fire |
|---|---|---|
| F1 (reg_set) | 6 | 412 |
| F2 (stream_cram 1w) | 6 | 462 |
| F3 (stream_cram 3w) | 5 | 522 |
| F4 (stream_pal_region 3w) | 6 | 570 |
| F5 (reg_set + cram 3w) | 4 | 632 |
| F6 (two cram 1w, one fire) | 4 | 622 |
| F7 (stream_vsram 1w) | 6 | 462 |
| F8 (pal_restore 3w) | 6 | 708 |

- [ ] **Step 2: Re-run the existing probe unchanged**

No new tool. `tools/raster_cost_probe.py` already is this check — do not write a second one, and do not add a third wire-format transcription (the probe's encoder is pinned by `tools/test_raster_wire_pin.py`).

Run: `python3 tools/raster_cost_probe.py --rom s4.debug.bin --lst s4.debug.lst --repeat 3`

- [ ] **Step 3: Compare against the reference and record the verdict**

Reference — oracle, 2026-08-18, per-routine row for the HBlank trampoline, 3 boots spread 0, marginal `(fixture − F0) / n`:

| | F0 | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 |
|---|---|---|---|---|---|---|---|---|---|
| cyc | 572 | 412 | 462 | 522 | 570 | 632 | 622 | 462 | 708 |
| n | — | 6 | 6 | 5 | 6 | 4 | 4 | 6 | 6 |

Three outcomes, each with a different consequence — write the one you got into `INSTRUMENT-PARITY.md`:
- **All nine match.** The instrument is stable since 2026-08-18. Phase 0 proceeds.
- **A constant offset on every row.** Something in the toolchain shifted uniformly. Record the offset and find its cause; do NOT silently subtract it and carry on.
- **Divergent per fixture.** Either the ROM changed or the instrument did. STOP and report — do not take budget rows until it is explained.

- [ ] **Step 4: Record the standing caveats in the evidence file**

Two, both carried into every Phase-0 row:
1. `interrupts.hint` is HBlank **plus** VBlank on oracle. Per-routine rows only.
2. Absolute cycle claims keep oracle as the reference; no row may assert oracle-next parity while its instruction-granularity slop is open.

- [ ] **Step 5: Commit**

```bash
git add docs/benchmarks/scanline-p2/INSTRUMENT-PARITY.md
git commit -m "measure(p2): re-confirm oracle's cost figures before budgets build on them"
```

---

## Task 2: Engine baseline rows — idle and max-diagonal

**Why:** design §5 — every axis budget is `pool − engine_reservation`, and the reservation is standing engine cost at a **defined worst-case camera state**. Without these two numbers every budget in Phase 2 is a fraction of an unknown.

**Files:**
- Modify: `tools/effects_budget_model.toml` (the `[engine_reservation]` table, created here)
- Create: `docs/benchmarks/scanline-p2/ENGINE-BASELINE.md`

- [ ] **Step 1: Define the two camera states precisely, in the evidence file first**

"Idle" and "max-diagonal" are not self-defining. Record: section, camera position, whether the player is moving, whether streaming is active, what is on screen. A baseline whose state is not reproducible is not a baseline. The P2 baseline rows in `effects-p3` went camera-stale exactly this way (recorded in the R1 evidence, §7.3 measurement 2 — "NO VERDICT").

- [ ] **Step 2: Measure both states**

Per-routine rows for: `Parallax_Update`, `Raster_VBlank`, `Palette_Compose`, `Enqueue_Dirty_Buffers`, `BgAnim_Update`. Five boots per state; report spread. Every figure ships with a wall-clock uptime beside it (carried standing constraint — a perf seat once reported a 12.7s figure that was really 2.85s because it measured the panel, not the build).

- [ ] **Step 3: Write the rows**

```toml
[engine_reservation]
# The standing engine cost a scene budget is measured AGAINST, not part of. Two states,
# both defined in docs/benchmarks/scanline-p2/ENGINE-BASELINE.md -- a reservation whose
# camera state is not reproducible is not a reservation.
status = "measured"
idle_main_loop_cycles      = 0    # REPLACE with the measured figure
max_diagonal_main_loop_cycles = 0 # REPLACE
idle_vblank_cycles         = 0    # REPLACE
max_diagonal_vblank_cycles = 0    # REPLACE
instrument = "ORACLE per-routine rows (oracle-next has no profiler); interrupts.hint is NEVER a valid source here -- it sums HBlank and VBlank"
```

- [ ] **Step 4: Commit**

```bash
git add tools/effects_budget_model.toml docs/benchmarks/scanline-p2/ENGINE-BASELINE.md
git commit -m "measure(p2): engine reservation baselines, idle and max-diagonal"
```

---

## Task 3: The per-frame HInt total (budget axis 4b)

**Why:** design §5 axis 4 splits into (4a) per-fire spacing, which the existing `check_density` machinery already owns, and (4b) a per-frame HInt TOTAL, which is genuinely new. The toml's absolute HInt rows have **never been measured** — `interrupts.hint` conflates VBlank, which is why.

**Files:**
- Modify: `tools/effects_budget_model.toml` (`[raster.sparse]`, replacing the superseded rows)
- Modify: `docs/benchmarks/scanline-p2/ENGINE-BASELINE.md`

- [ ] **Step 1: Measure the HBlank trampoline's per-frame total on the shipped OJZ content**

Not a fixture — real content, at both camera states from Task 2. The trampoline's own per-routine row, summed over the frame.

- [ ] **Step 2: Cross-check against the model**

The lowered program's fire costs are already known per fire (`fire_cost_cycles`). Sum them over the frame's live records and compare to the measured total. A gap is either dropped fires or a cost the model does not price — **investigate before recording either number.**

- [ ] **Step 3: Write the row with its derivation, and supersede the never-measured ones**

```toml
hint_total_cycles_per_frame = 0   # REPLACE — measured, NOT interrupts.hint
hint_total_derivation = "sum of fire_cost_cycles over live records; measured/model gap recorded in ENGINE-BASELINE.md"
```

- [ ] **Step 4: Commit**

```bash
git commit -am "measure(p2): the per-frame HInt total — budget axis 4b's first datum"
```

---

## Task 4: Walker fitted-model parameters

**Why:** design §5 axis 1 requires the walker's cost to come from a **fitted additive model** with a small parameter set (per-layer, per-line-mode, per-curve, per-deform-ref, re-glue), pinned to oracle fixtures with a 0-residual target — explicitly NOT per-variant re-measurement. This is the raster F1-F8 precedent applied to the walker.

**Files:**
- Modify: `tools/effects_budget_model.toml` (`[parallax.cost_model]`, created here)
- Create: `tools/parallax_cost_probe.py`
- Create: `docs/benchmarks/scanline-p2/WALKER-MODEL.md`

- [ ] **Step 1: Enumerate the parameters and design one fixture per parameter**

Each fixture varies ONE thing from a neighbour — the discipline that made the raster model 0-residual. Minimum set: 1-layer vs 2-layer (per-layer slope), per-cell vs per-line (line-mode premium), curve absent vs present (per-curve), deform-ref absent vs present, re-glue absent vs present.

- [ ] **Step 2: Measure, fit, and report the residual**

The residual is the deliverable, not a footnote. A non-zero residual means a parameter is missing from the model — name it or record it as unexplained. Do not fit and move on.

- [ ] **Step 3: Write the rows, each naming its fixture**

- [ ] **Step 4: Commit**

```bash
git add tools/parallax_cost_probe.py tools/effects_budget_model.toml docs/benchmarks/scanline-p2/WALKER-MODEL.md
git commit -m "measure(p2): the walker's fitted additive cost model, residual reported"
```

---

## Task 5: max-contiguous-DMA-stall (awareness row, not gating)

**Why:** design §5 carries this NEEDS-MEASUREMENT **for awareness, not gating, this phase** — it couples to the sound driver's DMA-survival design. Measure it, record it, do not build a gate on it.

**Files:**
- Modify: `tools/effects_budget_model.toml`

- [ ] **Step 1: Measure the longest contiguous DMA stall in a frame at both camera states**

- [ ] **Step 2: Record it against the Z80/DAC headroom, explicitly marked non-gating**

```toml
max_contiguous_dma_stall_cycles = 0   # REPLACE — AWARENESS ONLY, deliberately not gated
max_contiguous_dma_stall_note = "couples to the sound driver's DMA-survival design; gating this is a later decision, not P2's"
```

- [ ] **Step 3: Commit**

```bash
git commit -am "measure(p2): max contiguous DMA stall — awareness row, deliberately ungated"
```

---

## Phase 0 checkpoint

**STOP. Do not begin Phase 1 until every row above holds a measured number.** If any row is still `0` or `NEEDS-MEASUREMENT`, the budget gates in Phase 2 have nothing real to check and Phase 1's span gates do not depend on them — so Phase 1 may proceed, but Phase 2 must not.

---

# PHASE 1 — SPECIALIZATION

## Task 6: The bracketing-label emission convention

**Why:** design §3.3 states this as an emission convention, "not an afterthought", because §8.2's path-level span gates *require* it — the flat `.lst` drops `$`-mangled locals, which is why `raster_source_gate` had to hand-roll a resolver. Labels first, gating second; the reverse order leaves the gates unable to see what they must measure.

**Files:**
- Modify: `engine/level/scene_dsl.emp`
- Modify: `engine/level/parallax.emp`
- Test: `tools/test_scene_span_labels.py` (create)

- [ ] **Step 1: Write the failing test — every comptime-gated block has both brackets**

```python
def test_every_gated_block_is_bracketed():
    """A capability-gated block without both labels cannot be span-gated at all."""
    lst = (AEON / "s4.debug.lst").read_text()
    opens = set(re.findall(r"\$cap_(\w+)_begin\b", lst))
    closes = set(re.findall(r"\$cap_(\w+)_end\b", lst))
    assert opens, "no bracketing labels emitted at all — the convention is not in force"
    assert opens == closes, f"unbalanced brackets: {opens ^ closes}"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python3 -m pytest tools/test_scene_span_labels.py -q`
Expected: FAIL — "no bracketing labels emitted at all".

- [ ] **Step 3: Emit the brackets around each capability-gated region**

Name them for the capability, not the call site, so a span gate can derive its expectation from the mask rather than copy it.

- [ ] **Step 4: Run the test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add engine/level/scene_dsl.emp engine/level/parallax.emp tools/test_scene_span_labels.py
git commit -m "feat(scene): bracketing-label convention for capability-gated blocks"
```

---

## Task 7: CAP-mask gating at all three depths

**Why:** design §3.3. Three depths, measured differently (§8.2): module-level (zero scenes ⇒ zero parallax/raster/palette-compose bytes), path-level (no-deform ⇒ no sampling loop; never-per-line ⇒ no 224-fill and no 896-B DMA entry; no-anchor ⇒ no Step-4b), data-level (§3.1 record shapes).

**Files:**
- Modify: `engine/level/parallax.emp`, `engine/level/scene_dsl.emp`, `engine/effects/raster.emp`

Capability bits, already live from P1 (`games/sonic4/config/game.emp`, `SCANLINE_CAPS = $001F`; `games/demo/config/game.emp`, `SCANLINE_CAPS = 0`):

| Bit | Name | Raised by |
|---|---|---|
| `$0001` | `CAP_PER_LINE` | a deform table attached throughout |
| `$0002` | `CAP_PER_COL_VSRAM` | `v_deform_bg` |
| `$0004` | `CAP_DEFORM` | a table AND a live (non-15) amplitude |
| `$0008` | `CAP_ANCHORS` | `anchor_ch:` on a scene |
| `$0010` | `CAP_TRANSITIONS` | folded by `fold_caps()`, no single scene raises it |

- [ ] **Step 1: Gate one capability at a time, rebuilding between each**

Take `CAP_ANCHORS` first — it is the narrowest (one scene raises it) and its elision target (Step-4b) is a single block.

- [ ] **Step 2: After each capability, verify sonic4 is BYTE-IDENTICAL**

sonic4 raises all five bits, so gating must not change its image at all. This is the same differential P1 used and it is the strongest available check:

Run: `DEBUG=1 ./build.sh && python3 -c "import zlib;print(f'{zlib.crc32(open(\"s4.debug.bin\",\"rb\").read()):08x}')"`
Expected: unchanged from the pre-task crc. **If it moves, the gate is eliding something sonic4 uses.**

- [ ] **Step 3: Verify demo SHRINKS**

demo has `SCANLINE_CAPS = 0`, so every gated block must vanish from it. Record the byte delta per capability — a capability that elides zero bytes from demo is either unreachable or not actually gated.

- [ ] **Step 4: Commit per capability**

```bash
git commit -am "feat(scene): elide CAP_ANCHORS when a game does not raise it"
```

---

## Task 8: The demo witness — span absence AND whole-image comparison

**Why:** design §8.2 requires both, and states why: "spans alone can be satisfied by an inlined leak with no boundary symbol — recorded lesson; the image delta is the backstop."

**Files:**
- Create: `tools/test_demo_specialization_witness.py`

- [ ] **Step 1: Write the two-part witness**

```python
def test_demo_has_no_capability_gated_spans():
    """demo declares SCANLINE_CAPS = 0, so every gated span must be absent from its .lst."""
    lst = (AEON / "demo.debug.lst").read_text()
    leaked = sorted(set(re.findall(r"\$cap_(\w+)_begin\b", lst)))
    assert not leaked, f"demo carries capability-gated spans it cannot use: {leaked}"


def test_demo_image_does_not_grow_with_sonic4_scenes():
    """The backstop: an inlined leak has no boundary symbol, so spans cannot see it.

    demo authors no scenes. Its image is therefore the permanent witness that the
    engine is genuinely agnostic -- P1 used exactly this and it is what caught the
    difference between 'the symbol is gone' and 'the bytes are gone'.
    """
    assert demo_image_len() == PINNED_DEMO_LEN, (
        "demo's image moved; a scene-model change leaked into a game with no scenes")
```

- [ ] **Step 2: Poison it — prove the image half catches what the span half cannot**

Force one gated block to emit unconditionally *without* its bracketing labels, rebuild demo, and confirm `test_demo_image_does_not_grow_with_sonic4_scenes` fails while the span test still passes. That asymmetry is the entire justification for having both; if both fail or both pass, the poison did not reproduce the leak class.

- [ ] **Step 3: Restore and confirm green**

- [ ] **Step 4: Commit**

```bash
git add tools/test_demo_specialization_witness.py
git commit -m "test(p2): demo witness — span absence plus the whole-image backstop"
```

---

## Task 9: Depth-scoped span gates

**Why:** §8.2 — the three depths are measured differently and a single gate shape cannot cover them. Expectations derived from the capability mask, **never copied** (point at `effects_gates.py`'s `derive_arms` pattern).

**Files:**
- Modify: `tools/effects_gates.py`

- [ ] **Step 1: Derive each expectation from `SCANLINE_CAPS`, not from a table**

Read the mask out of the game's `game.emp` with the existing `emp_int` helper and compute which spans must be present or absent. A hand-written list of expected spans is the copied-expectation defect this codebase has been bitten by repeatedly.

- [ ] **Step 2: Two-fixture differential form**

§8.2 requires it for span/budget gates: a single poison can pass on layout accident. Each span gate compares sonic4 (`$001F`) against demo (`$0000`) and asserts the *difference* matches the mask, rather than asserting an absolute span in either.

- [ ] **Step 3: Guard against measuring the placer**

Region spans include placer fill. Assert on span *presence/absence* and on deltas between the two fixtures, never on an absolute byte count that fill can move.

- [ ] **Step 4: Run the full lane**

Run: `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`
Expected: all gates PASS, exit 0. Paste totals + exit code into the merge evidence (mandatory ritual, CLAUDE.md Testing section — this parcel touches `engine/effects/*`).

- [ ] **Step 5: Commit**

```bash
git commit -am "gate(p2): depth-scoped span gates, expectations derived from the cap mask"
```

---

## Task 9b: The rebase structural check (§8.2's last bullet, §6)

**Why:** §8.2 lists "Rebase structural check per §6" among P2's build-time gates. §6 is explicit about its scope and it must not be overstated: until §4.11 exists (FUTURE/Phase-4), this is a **structural/declarative check only** — an act-relative tagging check — "stated plainly so it cannot be mistaken for runtime rebase verification, which is deferred to when the rebase mechanism ships."

**Files:**
- Modify: `engine/level/scene_dsl.emp`

- [ ] **Step 1: Assert every world-Y layer top and anchor bank is act-relative-tagged**

A comptime `ensure` over the registry: any scene declaring a world-Y layer top or an anchor bank must carry the act-relative tag. This is a tagging check, not a rebase test.

- [ ] **Step 2: Name the limitation IN the ensure message**

The message must say what it does not check, so a future reader cannot mistake a green build for rebase verification:

```
"scene {name}: world-Y layer top is not act-relative-tagged. NOTE this is a STRUCTURAL check only -- it proves the declaration is tagged, NOT that a rebase preserves it. Runtime rebase verification waits on the §4.11 mechanism (Phase 4); do not read a green build here as rebase-safe."
```

- [ ] **Step 3: Poison it — an untagged declaration must fail the build**

- [ ] **Step 4: Commit**

```bash
git commit -am "gate(p2): act-relative tagging check, scoped explicitly to structure"
```

---

# PHASE 2 — BUDGET

> **Blocked on Phase 0.** Every check below references a row Phase 0 measured.

## Task 10: Ledger consts + the formatter spike

**Why:** design §5 — the lowering publishes per-scene ledger rows as **named exported comptime consts** (zero ROM bytes); a formatter tool reads them from the build's symbol table and renders `<game>_scene_budgets.txt`. Derivation stays single-sourced in `.emp`. **P2 includes the symbol-readback spike.**

**Files:**
- Modify: `engine/level/scene_dsl.emp`
- Create: `tools/scene_budget_report.py`

- [x] **Step 1: Spike the readback FIRST, before building the ledger on it** — **FAILED, then PASSED after the sigil unblock (both 2026-08-19).**

**SECOND RUN, on sigil `0df77f83`: it round-trips.** `pub equ SPIKE_LEDGER_EQU = SceneRegistry_CapsFolded * 7 + 3`
appears in `s4.debug.lst` as `EQU SPIKE_LEDGER_EQU = $000000DC` — 220, the computed value, exactly.
A negative control renders two's complement (`$FFFFFFFB` = -5), so the formatter does not assume
signedness. CRC unchanged: ledger rows are zero-ROM. `pub equ` is the ledger spelling; `pub const`
still mints no symbol and must not be used for a ledger row.

*The original failing verdict is kept below, because the reason it failed is the reason the row
shape is what it is.*

**VERDICT: a computed comptime value cannot be read back, in any spelling available today.**
`pub const` and `pub equ` were both spiked in a reached, section-carrying module with a
genuinely computed value; both built GREEN and ZERO-BYTE (`crc=d22dda85`, unchanged), and
NEITHER appears in `s4.debug.lst` (symbol count unchanged at 2578, against a passing positive
control on labels from the same module). The `.lst` emitter walks `sec.labels` only; `equ`
mints a link symbol but no label; deb2 is `convsym` over that same `.lst`. Full evidence,
sigil source citations and the unblock sketch: `docs/DEFERRED_WORK.md`, "Scanline P2 Phase 2
(Tasks 10-13) — BLOCKED".

The spike is the risky half: a comptime const must be visible in the `.lst`/deb2 in a form a tool can read. Prove one const round-trips end to end before authoring twenty.

**Trap:** `extern()` poisons comptime-ness. A ledger const that folds a link-time address stops the whole image being comptime and breaks the `first_mismatch` whole-image pins. Carry parameters, add bases at runtime.

- [x] **Step 2: If the readback does not work, STOP and report** — **TAKEN. This step governed; no second emission path was built. Steps 3-5 are blocked pending the ruling.**

Design §5 named this a spike precisely because it might not. Do not invent a second emission path — registry-emission exclusivity is a carried trap. Report and take a ruling.

- [x] **Step 3: Publish one axis for one scene, verify the report renders it** — done; `tools/scene_budget_report.py --check` renders all 12 rows, exit 0

- [x] **Step 4: Fan out to all axes and all scenes** — all four gateable axes over all 20 scenes (axes 5/7 have no subject; booked in the toml)

- [ ] **Step 5: Commit**

```bash
git add engine/level/scene_dsl.emp tools/scene_budget_report.py
git commit -m "feat(p2): per-scene ledger consts + the symbol-readback formatter"
```

---

## Task 11: Budget rows, reservations, and comptime enforcement

**Why:** design §5's ownership rule — enforcement constants live in the comptime DSL as the single authority; the toml `[symbols]` gate pins PROVENANCE (drift detection), **never enforcement**. Per axis, the SUM is enforced comptime in the lowering (it alone sees all scenes via the registry); the Python checker stays constants-only.

**Files:**
- Modify: `engine/level/scene_dsl.emp`, `tools/effects_budget_model.toml`

- [x] **Step 1: Enforce one axis comptime, using Phase 0's measured reservation** — axis 2 first, as the plan directs

Start with axis 2 (VBlank DMA bytes) — it has a hard pool (7524 B NTSC H40) and the clearest reservation.

- [x] **Step 2: Show the COMBINED per-line cost** — 1792 B AND 4270 cyc of drain, in the ensure text and the report. NOTE the plan's 896 B / 12% is HALF the measured value

§5 is explicit: per-line forcers price 896 B, and the ledger must show DMA bytes **plus** axis-3 drain CPU together, so "12%" never reads as the whole tax.

- [x] **Step 3: Add the `[symbols]` provenance rows** — 9 rows added, `effects_budget_check` OK 31/31

Provenance only. If a row here is doing enforcement, it is in the wrong place.

- [ ] **Step 4: Repeat per axis**

Seven axes: main-loop cycles, VBlank DMA bytes, VBlank CPU, HInt (4a existing + 4b from Task 3), sprite slots, RAM, computed-handler pins.

> **AXIS AUDIT 2026-08-19 — "seven axes" is not seven gates. FOUR are gateable in P2.**
>
> | # | Axis | Verdict |
> |---|---|---|
> | 1 | main-loop cycles | **GATEABLE** — pool 128000/frame, reservation `idle_main_loop_cycles` 35125 (headroom `idle_vsync_wait_cycles` 79595); cost from `[parallax.cost_model]` carrying residual 0.27, out-of-sample gap +1.1%, anchor as the measured worst regime 1204.7 LABELLED not fitted |
> | 2 | VBlank DMA bytes | **GATEABLE** — pool 7524 B, reservation `dma_queue_words_idle` 1528 w = 3056 B |
> | 3 | VBlank CPU | **GATEABLE** — pool ~18200 cyc, reservation `idle_vblank_cycles` 8280 (`VInt_Level` bracket) ⇒ budget 9920 |
> | 4a | HInt per-fire spacing | already owned by `check_density`; no new work |
> | 4b | HInt per-frame total | **GATEABLE** — sparse 1878 (1.5%), dense 32758 (25.7%) is the shipped worst case; the open −242 cyc / 1 fire dense model gap goes in the derivation note, not absorbed |
> | 5 | sprite slots | **NOT GATEABLE** — nothing measured in Phase 0, and no subject: `CAP_FG_SPRITE_STRIPS` is RESERVED (P3+), no lowering |
> | 6 | RAM | **GATEABLE, pool row STALE** — see correction 2 below |
> | 7 | computed-handler pins | **NO SUBJECT IN P2** — `CAP_COMPUTED` is RESERVED (P3+), no lowering; design §472 records the computed-range infra as deliberately not rebuilt |
>
> **Correction 1 — axis 2's per-line forcer is 1792 B, not 896.** The live queue carries TWO
> 448-word entries (`dma_hscroll_perline_entries = 2`, `dma_hscroll_perline_bytes_each = 896`),
> so the per-line tax is 23.8% of the 7524 B pool, not 12% — before Step 2's drain CPU is added.
> The understatement Step 2 exists to prevent is in this plan's own figure.
>
> **Correction 2 — axis 6's pool row is stale ~2x, unsafe direction.** `effects_budget_model.toml:540`
> says `free_before_stack_kb = 31.8`; measured on `bc048e2a` it is **16.7 KB** (release) and
> **6.5 KB** (DEBUG, the shape a budget must clear). Re-take the row and gate DEBUG.
>
> Task 13's "one poison per axis" scopes to the four gateable axes accordingly.

- [ ] **Step 5: Commit per axis**

---

## Task 12: The transition-frame check

**Why:** design §5 — the ledger's evaluation frame is the **transition frame**, not steady state: outgoing + incoming configs partially live under `Active_Config` routing, the reg `$0B` mode-change overhead, and the larger of the two HScroll DMA lengths. Steady-state is reported too, but pass/fail runs against the transition frame of the worst adjacent-scene pair, registry-derived.

**Files:**
- Modify: `engine/level/scene_dsl.emp`

> **BLOCKED 2026-08-19 — this gate would be vacuous as written. Two independent failures.**
>
> **(a) The section→scene join column is a `Label`.** Adjacency itself IS derivable (grid order;
> `GRID_W`/`GRID_H` and `flat = sec_y*grid_w + sec_x` are comptime ints). What is missing is the
> join from a section to its SCENE VALUE: `Sec.sec_parallax_config: *u8` →
> `EffectsPreset.ep_parallax: *u8` → `preset(…, parallax: Label = 0)` is Labels end to end, and
> there is no comptime path from `ParallaxConfig_OJZ_Underwater` back to `SCENES[1]`. The tree
> already declined this exact check for this exact reason at `scene_registry.emp:280-282`.
>
> **(b) There is no measured transition-frame reservation.** Neither Phase-0 camera state crosses
> a section boundary, so reg `$0B` overhead, the larger HScroll DMA of the pair and `Active_Config`
> routing have no measured row — and the plan's own rule forbids inventing them.
>
> **Missing measurement to unblock:** a boundary-crossing camera state for the baseline probe,
> plus a comptime-visible value-typed section→scene map (invert authorship, do not add a parallel
> hand-written array). See `docs/DEFERRED_WORK.md`, "Scanline P2 Phase 2 (Tasks 10-13) — BLOCKED".

- [ ] **Step 1: Derive adjacency from section descriptors, not a hand list**

The registry knows all scenes; adjacency comes from the section descriptors. A hand-maintained adjacency list is a copied expectation.

- [ ] **Step 2: Compute the worst adjacent pair per axis and check that**

- [ ] **Step 3: Report steady-state alongside, clearly labelled non-gating**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(p2): budgets gate on the transition frame of the worst adjacent pair"
```

---

## Task 13: Poisons — every axis, two-fixture differential form

**Why:** §8.2 — every budget axis, the tiling/curve/attachment ensures, and the capability-mask ensure each get a poison fixture, wired under `games/sonic4/test/poison/` as `emp_expect_fail` CASES rows with red-first sentinel discipline. EFX-9 is the "built carefully, run by nothing" postmortem.

**Files:**
- Create: `games/sonic4/test/poison/poison_budget_<axis>.emp` (one per axis)
- Modify: the `emp_expect_fail` CASES table

- [x] **Step 1: For each axis, author a scene that exceeds it by exactly one unit** — axis 1 only: unit = ONE BAND (115 passes / 116 fails by 82.01 cyc). Axes 2/3/4b are NOT falsifiable (measured; unlock conditions booked in the toml) so their poisons were booked, not faked

One unit, not ten. A poison that blows the budget by an order of magnitude can pass for the wrong reason.

- [x] **Step 2: Verify each poison is RED FIRST** — verified before registration: 1 `[Error]`, the axis-1 message, cost 104188 vs budget 104106

Run the expect-fail lane and confirm the new case fails *before* it is registered as expected-fail. A poison added straight to the expected list is never proven to bite.

Run: `DEBUG=1 ./build.sh`
Expected: `emp_expect_fail: OK — N/N cases` with N increased by the number of poisons added.

- [x] **Step 3: Confirm the sentinel still fires** — sentinel PASS, lane `OK — 20/20 cases` (was 19/19)

The lane's sentinel guard catches `--extra-entry` evaluating nothing, which would make every case vacuous. A diagnostic-count drift here means a guard stopped firing or a new one started — investigate, do not re-baseline.

- [ ] **Step 4: Commit**

```bash
git add games/sonic4/test/poison/
git commit -m "test(p2): one red-first poison per budget axis, two-fixture form"
```

---

# Landing

- [ ] **All four shapes build:** `DEBUG=1 ./build.sh`, `./build.sh`, `DEBUG=1 ./build.sh demo`, `./build.sh demo`
- [ ] **Full tool suite green:** `python3 -m pytest tools/ -q` — report aggregate totals, never a tail (a tail-45 once hid 16 failures)
- [ ] **Effects gate lane:** `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst` — paste totals + exit code into the merge evidence (mandatory ritual for any parcel touching `engine/effects/*`)
- [ ] **Byte accounting:** sonic4 byte-identical through Phase 1 (it raises every capability); demo strictly smaller, delta recorded per capability
- [ ] **Repin + `refreeze --freeze NAME --ab REF`** with prose emulator evidence if any phase moved bytes. `--check` is NOT the goldens
- [ ] **Merge as an aeon+sigil pair** if any sigil-side change was needed — neither half builds without the other
