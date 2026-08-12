# Session state — effects suite design + Phase 1, overnight 2026-08-11/12

> **SUPERSEDED 2026-08-12 (later the same day): the blockers below are CLEARED and
> the parcel is MERGED to master, aeon + sigil paired.** The character-dispatch work
> landed, which re-coupled the pair; this parcel was rebased onto it, re-verified,
> repinned and refrozen as sigil chain entry 105. Kept for the gotchas, which still
> hold. Current status: `docs/benchmarks/effects-p1/GATE-EVIDENCE.md`.

## Where the work is

- **aeon:** `feat/effects-p1-raster-core`, worktree `.worktrees/effects-p1`, 11 commits ahead of master. Both canonical shapes build green (debug crc `66ce78de`, plain crc `cf6c2811`).
- **sigil:** `feat/effects-p1-registry`, worktree `.worktrees/effects-p1`, based on **`9f6b6209`**. Contains no source changes — it exists only to provide binaries paired with aeon master.
- **NOT merged, and not mergeable as-is.** See "Blocked on" below.

## What shipped

Effects Phase 1 per `docs/superpowers/2026-08-11-effects-suite-design.md`:
the sparse HInt raster dispatcher, the `sec_pal` per-section palette consumer, and the
`sec_raster_table` consumer. Two previously-dead `Sec` descriptor fields now have live
engine consumers. Verified on oracle mid-scroll — the raster split lands exactly at the
authored screen line. Evidence + residuals: `docs/benchmarks/effects-p1/GATE-EVIDENCE.md`.

## Blocked on (do these first — P2 plan Task 0 walks them)

1. **The aeon/sigil pair is split.** Sigil master's registry requires modules that exist
   only on the unmerged `feat/character-dispatch` (`games.sonic4.player_fly`, tails), so
   **aeon master cannot build with sigil master**. That is a pre-existing condition, not
   caused by this work. Recovery recipe: `memory/reference_aeon_sigil_pairing.md`.
   Merging P1 before the pair is coherent would risk an unbuildable master.
2. **Golden repin/refreeze owed.** P1 changes bytes and adds RAM; the sigil-side golden
   gates have not been re-frozen.
3. **Replay net NOT re-run.** `Raster_State` shifts `Engine_RAM_End` and the game RAM
   chained after it, so expect layout-induced hash drift needing a fixture re-stamp.
   Disposition (layout vs behavioural) is P2 Task 0 Step 4.

## Two things a reader should know about the emulator

- I took over the **single** oracle instance (it had been sitting paused at
  `Process_DMA_Critical` for 2.5 h with a ROM built 2.5 h earlier — stale, not live) and
  reloaded it with this branch's debug ROM. If the parallel character/VRAM session wants
  its own ROM back it needs a reload; nothing else was disturbed.
- **`emulator_reload_rom` does NOT reload symbols.** Stale symbols silently resolve to
  wrong addresses — `Camera_X` read 0 through 400 frames of scrolling, and a ROM label
  pointed at non-palette bytes. Always follow a reload with
  `emulator_load_symbols <worktree>/s4.debug.lst`.

## Gotchas worth carrying forward

- The shell cwd was reset out of my worktree twice by `cd`-into-sigil commands, and one
  build consequently ran against the main tree (on the other agent's branch), producing a
  confusing `Air_Collide` contract failure. **Use absolute paths / an explicit `cd` in
  every build command** when working across worktrees.
- Measuring a raster effect from a screenshot: count pixels **exactly equal** to the
  written colour. "Reddish" thresholds catch OJZ's brown trunks (a first pass reported a
  spurious boundary at row 45) and brightness means are dominated by the art's own
  canopy/ground transition at row 111-112.

## Next

`docs/superpowers/plans/2026-08-12-effects-p2-palette-engine.md` — palette engine,
variants/regions, dense raster tier, gated on the hand-authored OJZ water cluster.
Phases 3-6 (library + starter pack, Aurora Effects Lab, Map integration, frame effects
engine) stay unplanned by design; each is planned when its predecessor has shipped.
