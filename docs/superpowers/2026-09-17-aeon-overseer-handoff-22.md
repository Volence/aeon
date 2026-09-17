# Aeon overseer handoff 22 (2026-09-17, morning)

**The resume anchor for the next aeon session.** Written 2026-09-17T09:37:13Z. Read `docs/lane-status.json` first and **fetch origin before reading master**. Nothing was in flight when this was written; no agent survives the `/clear`.

## Landed this session (all pushed; each has a lane-log entry with evidence)
- **SPAWNDESC-SIZE-CLOSE** (merge 2c7e6631): sigil d7e6aa15 (release binary md5 8027e7ba, swapped 08:11:55Z) refuses a mis-sized struct. Its check covers the `use` closure only; a module outside it (engine/debug/sound_debug.emp) still builds clean when mis-sized. preset.emp and structs.emp comments corrected. Effects gates run: 41 PASS, 0 FAIL. Aurora notified.
- **STRESS-SHAPES-NIGHTLY** (merge 294ef86c, pushed 3890712d): the nightly builds STRESS_EVICT then STRESS_ART after the needs_build lane, reports FAILED on non-zero, and checks the tree is clean afterwards. test_landing_lane_shapes.py skips STRESS_* prefixes.
- **PRESET-LAB-WITNESS-REGIONS** (merge ba20678d): the nightly preset lab lane had been COULD NOT RUN since 09-16 (cause 7de53e2e, the 11th DEBUG region row). The 10 is PRESET_CYCLE_MAX, a one-digit DEBUG readout, not an engine counter. The witness now reads it from source and prints regions 10..12 as NOT MEASURED. Exit 0 re-verified on the merged tree.
- **REGION-BG-COVER-WARNING phase 1** (merge 41ced185, docs only): required cover derived from source. BLOCKED on what "opaque cover" means; filed as card **REGION-BG-COVER-DEFINITION** (recommend waiting for a real showcase crossing). Note: `docs/superpowers/notes/2026-09-17-region-bg-cover-warning.md`.

## Owner cards open
REGION-BG-COVER-DEFINITION (new), FG-CACHE-10-HOW (recommend stay-at-12), SP6-MODULATION-DIVERGENCE (spring A/B needs his ear).

## Next, in order (nothing waits on anyone)
1. **LS-13b**: boot's hand-written Z80 pause; the sigil language feature has shipped. Read its booking in DEFERRED_WORK and sigil's LS-13b note before dispatch. It is a byte-mover, so it gets the full landing lane.
2. Small: the stale comment at `tools/nightly_effects_gates.sh` ~line 223 ("the act's own section grid") should say the lab cycle list (LAB_CYCLE_COUNT, capped by PRESET_CYCLE_MAX). Also open from the witness parcel: PRESET_CYCLE_MAX is read from source but not checked against the ROM.
3. Per-region animated background strips stay booked (REGION-BG-PER-REGION-BANDS): no band content ships, so building them now would be a dormant scaffold.

## Housekeeping observed, not acted on
29 older agent worktrees under `.claude/worktrees/` from earlier sessions. Not pruned: check each branch's ancestry against origin/master first, per the shared-machine cautions.

## Lessons
- A merge that conflicts inside a `&&` chain stops the chain, but anything after a `;` still runs: the landing runner looked "started" and was not. Confirm the runner with pgrep.
- An agent's own brief can overcount: the cover booking's formula undercounts vertical crossings (n+7 vs the measured n+8/n+15 bound). Its note derives the right one.
