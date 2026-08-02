# Engine-debts opener — overseer gate evidence (2026-08-02)

Companion to `plans/2026-08-02-engine-debts-opener.md`. All oracle work foreground
(overseer), ROM `s4.debug.bin` CRC `76d06e43`/422066 built fresh from master `e03aad8`
(delete-first; the stale-`sigil`-binary trap below).

## Toolchain note — stale release binary trap (fixed)

`sigil/target/release/sigil` predated the A3 `span()` merge and panicked mid-build
("unknown function `span`", dac_sample_tab.emp) while LEAVING the old artifact in
place — its CRC still matched golden, i.e. exactly the stale-ROM class. Rebuilt
12:40 from sigil master `0ad2f49d`; always delete-first + assert fresh mtime.

## Parcel 2 — A2 (mid-walk compact) verify: PASS

The spec-§9 latch is shipped in `engine/objects/core.emp` (AllocDynamic latch at
full count → `Dynamic_Live_Pending` (8 deep) → `DrainDynamicPending` at the
RunObjects frame-end reconcile; `CompactDynamicLive` walk-flag-asserted, called
ONLY from the reconcile). Live soak: entered `GameState_ObjectTestChurn` at runtime
(`Game_State` ← `GameState_ObjectTestChurn_Init`), ~7,000 churn frames (frame_token
9603482 → 9610518+), a sampled PC even landed inside `AllocDynamic` mid-churn:
- NO assert fired (DEBUG rails live every frame; the .asm-era churn soak fired the
  old hazard within ~4 frames).
- Steady state: `Dynamic_Live_Count`=29, `Pending`=0 at reconcile — the 40→29
  population decay is the accepted alloc-fail cost when >8 churners die+respawn in
  one saturated frame (latch full → alloc-fail → churner loses its replacement),
  NOT a defect. The ruled semantics (alloc-fail family) are exactly what shipped.
Verdict: the A2 hazard row closes as ALREADY-FIXED + soak-verified.

## Parcel 1 — leak A-side: REPRODUCED on master (pre-fix)

Vehicle: `GameState_ObjectTest` (3 TestParents + children), then hot-swap
`Game_State` to the churn RUN proc (`GameState_ObjectTestChurn`, $5DEA6) whose
per-frame `EntityWindow_Scan` early-outs (Active=0) to the Despawn walkers.
Trigger poke on parent slot 18 ($FF8FB2): `slot_tag` $FF→$00 (tagged),
`entity_section_id` $00→$FE (untracked; live tracked set read as {0,1,3,4}).

Single-stepped the whole mechanism end-to-end in `EntityWindow_DespawnObjects`:
entry $8FB2 loaded → tag guard falls through (tagged) → `.check_active` all four
section compares miss → `.despawn` → `DeleteObject` (parent only). Then observed:
- Parent slot 18 freed (SST zeroed); its 3 children (slots 3/4/5) SURVIVE with
  `parent_ptr`=$8FB2 pointing at the freed slot.
- Free-run ~38 s: parents 17/19 self-destructed via their own timer cascade and
  their children were correctly freed (the test_parent lifecycle path) — but the
  window-despawned parent's children orbit the zeroed corpse at (0,0)±24 forever:
  `Dynamic_Live_Count` settled at 33 = 40 − 7 (the 3 leaked slots still "live"),
  `Dynamic_Free_SP` recovered exactly 7 slots ($9EB2→$9EC0), never the 3 orphans.
- Screenshot: `docs/research/leak_repro_orphans_2026-08-02.png`.

B-side (post-fix, cascade): same procedure must show parent 18's despawn freeing
4 slots (parent + 3 children) same frame, count → 36 after reconcile, free SP +8,
no walk-rail assert. To be run on the `fix-despawn-cascade` ROM.

## Oracle tool observations (for the oracle backlog, NOT engine bugs)

1. **`run_to` at the current PC is a no-op**: arming a transient breakpoint at the
   address the CPU is parked on fires immediately without executing a frame — two
   consecutive `run_to <same state proc>` calls can bracket ZERO executed frames.
   Verify frame_token, not hit count, when frame-stepping this way.
2. **Breakpoints at non-jump-target/fall-through addresses did not fire** (bps at
   `.check_active` $47C2 and `.despawn` $47FC never registered hits even while
   single-stepping proved execution passed through both). Proc-entry bps fired
   reliably. Worth a look in oracle's bp engine.
