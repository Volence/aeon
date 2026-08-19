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

The owner is asleep and expects continued progress. Keep master unbroken, commit each step,
merge aeon+sigil as pairs, and lead any summary with what merged. Where a decision is genuinely
the owner's, do the work that does not depend on it and leave the question stated plainly.
