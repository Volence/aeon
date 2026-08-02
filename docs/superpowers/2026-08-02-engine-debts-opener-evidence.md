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

## Parcel 1 — leak B-side: PASS on `fix-despawn-cascade` (aeon dbcb3795)

Same procedure, porter ROM `s4.debug.bin` CRC `764d4e87`/422066 (worktree build,
CRC countersigned). Identical staging (parents 17/18/19, chain head slot 3). Same
poke on parent 18 → first churn frame's despawn walk:
- Parent 18 AND children 3/4/5 all freed the SAME frame (`active:false` ×4);
  `Dynamic_Free_SP` $9EB2→$9EBA (+8 = 4 slots) — the plan's exact prediction.
- Next reconcile: `Dynamic_Live_Count` 40→36 (−4, was −1 pre-fix).
- Parents 17/19 unaffected mid-run; free-run past their natural timer cascade:
  END STATE ZERO parents/children/orphans, count 30 (pre-fix ended 33 with 3
  corpse-orbiting orphans), free SP $9EC6 = base +10 slots = every allocated
  parent/child slot returned. No walk-rail assert at any point.

A/B verdict: 33-with-orphans vs 30-clean — the row-1599 leak class is closed by
the cascade.

## Parcel 3 — PAL NTSC-only deletion: PASS (aeon merge 218608b, chain-24)

Porter reader-sweep clean (only the 3 expected sites). Code −0x10/shape, RAM −4
(every upper-RAM symbol ≥ $802C). Oracle B-side on the porter DEBUG ROM
(8cdcaae5/422038): `DMA_Budget_Default` seeded $1800 (NTSC, DMA_BUDGET_NTSC=6144)
at the shifted address $FF81FE; `Hardware_Region`=$A0/`Region_Flags`=$80 correct;
600-frame held-right max-scroll run: Camera_X 0→5824 px, `Lag_Frame_Count`=0,
clean OJZ render, no assert. Chain 23→24 (`pal-ntsc-only`), strict 2990/0/4
own-run restored.

Countersign catch (the parcel's lesson): the porter's fixture sweep got the suite
to "all residuals are refreeze territory" — but FOUR more files carried stale
literals of the same −0x10 class that only surfaced AFTER the refreeze
(boot_data_port BootData windows, native_full LOAD_BEARING, native_offcanonical
GameLoop/AnimateSprite, and `seam1::blob_lma` — a harness SRC literal, byte-gate-
only consumer). All pin-sourced where pins exist (sigil 237c1afb). Standing rule
confirmed: "refreeze territory" claims must be re-verified by an own-run AFTER the
refreeze, not classified from failure names.

## Input/replay parcel I1 — 6-button layer: MERGED (chain-25 `input-6button`)

aeon merge `0887b51` / sigil `16aa2175`. Oracle gate on the MDControl6 device:
PAD_6BTN detected (port 2 degrades 3BTN), X/Y/Z/Mode → `BUTTON_EXT_*` exact, edge
latch consume-once, 600-frame max-scroll behavioral A/B IDENTICAL to pre-parcel
(Camera_X 5824 px, lag 0). Strict 2990/0/4 own-run post-refreeze.

Findings worth their ledger space:
1. **The live gate caught a protocol bug code review missed**: the first-pass
   HIGH-first TH cadence sampled every 6-button phase a half-cycle early against
   the rising-edge pad counter (oracle's MDControl6 model, and real pads) —
   detection could never fire. Rewritten to the SGDK LOW-FIRST cadence, verified
   phase-by-phase against the device source.
2. **`jbsr` relaxation is convergence-history-dependent at the ±32K reach
   boundary**: the parcel's shift pulled `Sound_PlaySFX` into bsr.w range of the
   player bank; the whole-ROM build's monotonic grow keeps `jsr` while a
   standalone lower picks `bsr.w`. Fixed by pinning the borderline cross-bank
   call to explicit `jsr` (byte-identical) — the kept-width class.
3. **Two stale-literal fixture classes killed structurally at the second bite**:
   off-canonical LOAD_BEARING spots now read from the frozen size tables (which
   regenerate at every refreeze); the keystone deform-pointer offset is
   listing-derived. Plus the parallax RAM-label table pin-sourced at its third.

## Oracle tool observations (for the oracle backlog, NOT engine bugs)

1. **`run_to` at the current PC is a no-op**: arming a transient breakpoint at the
   address the CPU is parked on fires immediately without executing a frame — two
   consecutive `run_to <same state proc>` calls can bracket ZERO executed frames.
   Verify frame_token, not hit count, when frame-stepping this way.
2. **Breakpoints at non-jump-target/fall-through addresses did not fire** (bps at
   `.check_active` $47C2 and `.despawn` $47FC never registered hits even while
   single-stepping proved execution passed through both). Proc-entry bps fired
   reliably. Worth a look in oracle's bp engine.
