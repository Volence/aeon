# Aeon-side overseer handoff (2026-08-19)

Written for a Fable overseer taking this session over after a `/clear`. The role is
**orchestrate + decide + check quality**, not implement: dispatch Opus subagents for the
work, and spend your own attention on rulings and on whether returned work is actually
sound. There is a `dispatching-empyrean-agents` skill — use it when writing dispatch prompts.

## Where things stand

The raster substrate byte-moving parcel **merged 2026-08-19** as an aeon+sigil PAIR:
aeon `ed015f0f` + `5f30d05d` ↔ sigil `31aa4464`. Neither half stands alone (sigil's goldens
pin aeon's four shape CRCs; all four moved). Master is green:
aeon pytest **1025 passed / 2 skipped**, effects gates **10/10 exit 0**, four shapes build;
sigil **3731 passed / 2 failed** — those 2 are pre-existing and booked, see below.

Closed: substrate items 2, 4, 1a + three Tier 4 riders. Detail lives in
`docs/DEFERRED_WORK.md`; do not re-derive it in conversation.

## The three items left

1. **Item 1b — run the HBlank window sweep.** Spec AND runbook:
   `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-SPEC.md` (§9 is the runbook). Unblocked
   2026-08-19 when oracle-next shipped `emulator/scanlines`. This is a real measurement
   session; delegate the driver, but see "what to check" below — this one has a specific way
   of producing a confident wrong answer.
2. **Item 1c — point the spin solver at the measured window centre.** Depends on 1b's number.
   Deletes the last hand-fitted delay values and adds an `ensure` that every op's computed
   landing sits inside the window with margin. Also must correct `raster_dsl.emp`'s `fire()`
   guard text, which currently documents the defect as open.
3. **Item 1 ripple / close-out** — re-pin the F-series if 1c moves timing, re-run the effects
   gate lane, repin + `refreeze --freeze NAME --ab REF` in sigil, merge as a pair.

## Decisions that are yours

- **If the sweep disagrees with the prediction (N ∈ [15,19], centre 17).** §7 of the spec
  forbids tuning the fixture toward the prediction; §6b's two anchors assign fault instead
  (both clean → our arithmetic; either dirty → the instrument). Your call is whether the
  evidence actually supports the verdict a subagent reports.
- **Whether 1c ships one target or keeps per-class anchors.** The owner ruled "best-in-class,
  single derivation" on 2026-08-18. Hold that unless measurement contradicts it.
- **The `ojz_run_b` fix** (see below) — relocate `BG_LAYOUT_SIZE`, teach the harness a
  companion module, or use `LowerOptions.defines`. Deliberately NOT ruled.
- **Anything novel or irreversible.** Standing instruction: flag big bets for owner sign-off
  rather than absorbing them.

## What to check in returned work — these have all actually bitten here

- **Vacuous gates.** A poison must perturb the SUBJECT and name the specific mismatch. A test
  asserting only "something raised" is not a test. Ask: *what did they perturb, and did the
  right assertion fail?*
- **Copied expectations.** Gate expectations must be DERIVED from shipped constants, never
  typed in or copied from a neighbouring pin. This has twice nearly enshrined a wrong number.
- **ROM length is not code delta.** Placer fill absorbs bytes — item 2 grew +40 bytes of code
  while the ROM grew +20. Reconcile per-proc against the `.lst`.
- **`build.sh` green does NOT mean sigil green.** A new cross-seam `use` in an `.emp` breaks
  sigil's `*_port` tests silently. Only `cargo test --release --workspace --no-fail-fast`
  sees it (plain cargo stops at the first failing binary). This parcel broke 5 that way.
  **Never let a data module be imported by something a port harness compiles.**
- **Never accept a tailed test run.** Require aggregate totals and failing-target names. A
  tail-45 once hid 16 failures.
- **For the sweep specifically:** every capture must assert `source == "raster"`. The other
  value, `"stateRender"`, is a post-hoc render that shows N=0 and N=17 as IDENTICAL — it is
  structurally blind to the defect being measured, and unchecked it produces a clean-looking
  wrong answer. This is the single most likely way 1b goes bad.

## Peer session

`oracle-next-34` owns oracle-next and has been a good counterpart — contract-first, verifies
pointers before recording them. Message it via SendMessage for anything needing a build or a
capability on their side. Live agreements: field 1 (rendered RGB) was the agreed first slice;
per-pixel CRAM index + S/H state are a named deferred follow-up; our acceptance criteria A1/A2
are in their permanent suite. They owe an owner ruling on a Tier 2 keep-dead collision — we
told them instruction stepping is off aeon's critical path, so it should not block us.

**Do not ask a peer to do something this session was denied permission for.**

## Known-red, not ours

`ojz_run_b_{,debug_}regions_match_reference` fail on sigil with `unknown name BG_LAYOUT_SIZE`
— pre-existing from aeon `5519ea54`, verified against pre-merge master, booked in
`DEFERRED_WORK.md`. They fail to COMPILE, not because a number moved, so do not re-baseline
around them.

## Overnight posture

The owner is asleep and expects continued progress. **The three items above are the FRONT of
the queue, not the end of it — do not idle when they land.** Keep master unbroken, commit each
step, merge aeon+sigil as pairs, and lead any summary with what merged. Where a decision is
genuinely the owner's, do the work that does not depend on it and leave the question stated
plainly rather than guessing.

## The continuation queue — work it in this order

Everything here is already scoped in `docs/DEFERRED_WORK.md` or in a written plan. Nothing
below needs the owner **except** where marked PARK.

**A. Scanline P2 Phase 1 — specialization** (plan:
`docs/superpowers/plans/2026-08-18-scanline-p2-specialization-budget.md`, Tasks 6-9b).
The best overnight block: five tasks, fully specified, and **it does not depend on Phase 0's
measurements**. Order is load-bearing — bracketing labels (Task 6) before the span gates that
require them. sonic4 must stay BYTE-IDENTICAL through this (it raises every capability bit,
`SCANLINE_CAPS = $001F`); demo must SHRINK, and a capability that elides zero bytes from demo
is either unreachable or not actually gated. Do NOT start Phase 2 (budget) — it is blocked on
Phase 0, which needs oracle and is a separate session's work.

**B. Tier 3 perf** — the substrate sweep's ranked list, deliberately scheduled AFTER the freeze
as byte-moving parcels. Each is its own parcel with its own repin/refreeze; do not batch two
byte-movers into one branch (that is the confounding that voided the prebatch A/B measurement).
Ranked by leverage:
1. `raster.emp:736` — 30 cyc per streamed word vs 16 via `-4(a2)`. **Highest leverage: this
   constant is what sets `RASTER_CRAM_MAX = 3`**, so it may buy back burst capacity, which
   interacts with 1c's window arithmetic. Sequence it AFTER 1c or expect to re-derive.
2. `raster.emp:714` — `OP_SET_REG` pays all five compare rungs (80 of its 110 cyc); a leading
   `tst.w d1 / beq` decimates it.
3. `raster.emp:834` — dense kind re-tested per scanline, ~2,300 cyc/frame, run-invariant.
4. `palette.emp` ×6 `lsl.w #1` → `add.w dN,dN`, ~768 cyc/derive.
5. Four missed mandatory tail calls (`raster.emp:560,622`, `palette.emp:386,666`).
6. **PARK — `raster.emp:656`** (redundant SR push/pop, ~30 cyc/fire; `rte` already restores
   SR). Needs a sigil-side context flavour, so it is a paired change AND a novel mechanism:
   **owner sign-off required, do not assume.**

**C. Substrate item 3's structural fix** — the one-byte frame-epoch flag so a pre-rewind fire
retires as a park. Currently only MITIGATED by the `<= 223` constructor bound, which does not
cover any future non-constructor path into a dense run. Interrupt-priority reasoning is
source-confirmed, never emulator-confirmed — that gap is part of the work.

**D. Remaining Tier 4** — `palette_dsl`'s self-test-only variant mirror, C5 footprint, the
EFX-4b angle, and the zero-`assert.*` observation. Small, zero-byte, good filler between
larger parcels.

**E. The `ojz_run_b` ruling** — PARK unless it blocks something. It is pre-existing and needs a
design call (relocate `BG_LAYOUT_SIZE`, teach the harness a companion module, or use
`LowerOptions.defines`), and `BG_LAYOUT_SIZE` is a genuine `engine.level.bg` concept rather
than a stray constant.

**Broader backlog:** `project_open_work_inventory` in memory is the authoritative what's-left
across sound and engine. Its claim that "the backlog is EMPTY after 5+6" is FALSE — there are
unplanned riders recorded inside it.

If everything above somehow lands, do not invent scope: run a lens sweep on an unswept area
(`project_lens_coverage_gap_2026_08_13` names sound, tools and engine-system as unswept since
07-16) and bring the findings back as a packet for the owner to rule on.
