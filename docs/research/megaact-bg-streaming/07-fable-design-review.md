# Fable review of region background switching design v2

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** This is the research agent's final report,
> extracted programmatically from its transcript and committed VERBATIM, never retyped: a report
> whose value is its `file:line` citations cannot be summarised without becoming the
> summary-of-a-summary this project was bitten by twice today. It is a LEAD for the design, not a
> finding the design may assume: every MEASURED claim is re-checkable at its citation.

---

## Verdict

**On the right track for the background, with one thing wrong enough to reorder the plan.** Full overwrite (R2) is the correct decision for a 2D patchwork of arbitrary regions: build-time slot colouring genuinely dies on the four-colour argument, and the blank-first ordering is not only right but better-justified than the design says (the real Icecap failure is an in-place overwrite of visible tiles, which only a blank or a mask can fix, see finding 9). The single most important thing: **§3.6's account of what "ignore the warning" does is false.** In the release shape an over-budget foreground spot does not stutter, it holds the camera forever (finding 1), and the budget is the 80×60 cache window's page set, not the visible screen's. That number decides whether the Sonic 2/3 stress test can exist at all, it is a tool-only measurement, and it should run before the switch is built, not fifth. Second: the blank step has no transport and no cost anywhere in the design, and the cover it demands at speed is roughly two screens of opaque foreground per crossing (findings 2 and 3). D4's build-time check should come back as the warning R5 asks for.

## What's sound (keep it)

- **Full overwrite over any slot scheme.** §8's first row is correct: a planar region graph needs up to four colours, 94 tiles each, and the measured S3K backgrounds (104-174) do not fit. Simplicity plus the whole arena beats a per-word rebasing add on every wipe row plus a junction-prediction problem.
- **Blank, overwrite, repaint, each waiting on the last.** MEASURED support at the handler level in Batman & Robin: the camera trigger (`disasm/code/objects/objects_2.asm:5857-5861`, `cmpi.w #$680,$ffed9c` then `lea $330fc(pc),a6`) and the blank-fill handler's tile constant (`disasm/code/engine/interrupts.asm:231`, `move.w #$5fc,$ffe048.w`). The script byte order itself I did not re-decode.
- **Level-triggered arm on the crossing's own output** (`engine/level/bg.emp:614-622`, compares `BG_Plane_Layout` to the effective layout pointer). Pointer identity means two rows sharing a layout never re-wipe. This is the right primitive to hang the state machine on.
- **The wipe's plane-row (not map-row) cursor** (`bg.emp:700-713`) survives a window moving mid-sweep. The repaint half of the sequence is already built and already correct for falls.
- **Palette handled by the existing per-region machinery** (R6) and the position-driven blend booked, not designed. Correct restraint.
- **Naming BgAnim and budget contention as open risks** rather than hand-waving them.

## Findings, most serious first

**1. "Ignore the warning and it stutters" is wrong; in release it soft-locks, and the budget is the cache window, not the screen.** MEASURED.
- The refcount source is every nametable word in the 80×60 `Tile_Cache_Nametable` (`engine/level/page_cache.emp:1-17`), i.e. two screens wide and two-plus tall, and the engine's own calibration history states the consequence: "the refcount source is the whole 80x60 window ... refcount-based eviction therefore cannot sustain churn at ANY clamp < PAGE_FRAMES" (`engine/system/constants.emp:491-502`).
- When no evictable frame exists, `PageCache_AllocFrame` raises only under DEBUG and returns `PAGE_NOT_RESIDENT` in release (`page_cache.emp`, `.thrash` arm, ~:331-337); `PageIn_Process` re-enqueues the same page (`engine/level/page_in.emp`, `.alloc_fail`); the demand-stall watchdog is entirely inside `if DEBUG == 1` (`engine/level/tile_cache.emp:1072-1088`); `Camera_Art_Hold` holds the axis with player logic untouched (`engine/level/camera.emp:254-262`). Nothing in the release path ever gives up.
- So: a junction whose 80×60 window references more than 12 frames minus pins (`PAGE_FRAMES = 768/64`, `constants.emp:405,871`) is a permanent camera hold with the player free to walk off-screen. That is the informed choice R5 needs stated.
- What I'd do: rewrite §3.6's consequence; make M-B measure the window's page set (not the visible screen) at every camera position along a stitched two-zone seam, tool-only, before anything is built; have the build warning use the same window. Consider a release-shape escape (e.g. stall watchdog that releases the hold and accepts one garbage block) as an owner call.

**2. The blank step has no transport and no cost, and M-A omits it.** MEASURED constants, INFERRED cost.
- The only fill primitive is the boot-time byte DMA fill (`engine/system/vdp_init.emp:59`), not a runtime queue class. A full-plane blank is 8192 B; at the ~205 B/line blanking rate (slice 05) that is ~40 lines, more than the 38-line NTSC window and more than `DMA_BUDGET_NTSC` 6144 (`constants.emp:708`) allows beside the plane drain. So a fill is 2+ frames and starves the drain, or the blank goes through `Draw_BG_TileRow` at `BG_WIPE_ROWS_PER_FRAME = 4` (`bg.emp:492`) = 16 frames for the plane.
- The blank must cover all 64 rows, not just the visible ones: the plane is a ring (`bg.emp:295-301`), the window moves at up to 2 rows/frame on a fall (`CAM_MAX_Y_STEP = 16`, `constants.emp:1098`), and any row the streamer paints from the new layout during the overwrite references tiles not yet uploaded.
- Realistic sequence: 2-16 (blank) + 3 (upload) + 8 (visible repaint) = 13-27 frames, not "about a sixth of a second". M-A must be measured after the transport is chosen, because the choice moves the answer by ~3x.
- Also unnamed: the overwrite transport itself. `page_in.emp:246-253` lands pages only at `frame << 11` inside the FG pool; there is no "raw ROM to BG arena, chunked, budgeted" enqueue. That is engine work §7 does not list.

**3. The cover the design requires is roughly two screens of opaque foreground per crossing at speed, and nothing computes it.** INFERRED from MEASURED constants.
- The switch fires when the camera centre enters the region (`engine/level/parallax.emp:1213-1216`), so at the crossing the screen already spans 160 px of each side. From that instant the background is blank for T frames while the camera moves up to `CAM_MAX_X_STEP = 16` px/frame (`camera.emp:26`). For T = 25 that is 400 px of travel plus the 320 px screen: ~720 px of fully opaque Plane A on the new side of every boundary. That is a tunnel by another name; the corridor did not go away, only its check did (see "wrongly superseded").
- The blank word matters too: word 0 is FG tile 0, the blank tile (`tile_cache.emp:482,560`), which is transparent, so the "blank background" is the backdrop colour = CRAM entry 0 of line 0, which the engine reserves to the character (`engine/effects/palette.emp:48-55`, LINE-0 INVARIANT). The designer does not own that colour. Make the blank an authored fill word per crossing (a solid tile in a fixed slot, e.g. sky colour) so uncovered moments read as a flat sky, not as the character's colour 0.
- Risk for the owner (R3): for cave-to-treetop a cave mouth is natural cover; for treetop-to-deep-jungle it is not, and the "feel like completely different areas" goal wants visible transitions that full overwrite cannot give without a tunnel.

**4. Hysteresis is proposed at the wrong layer, and the sequence is neither reversible nor re-entrant.** MEASURED for the layer, INFERRED for the rest.
- `Parallax_CheckBoundary` is pure rectangle containment with no margin (`parallax.emp:1211-1240`); `REGION_MIN_SPAN` (`act_descriptor.emp:521`) is a step-over guard, not hysteresis. The palette and parallax swap at that crossing. Adding hysteresis to the background alone recreates exactly the "three private answers to which background" problem `bg.emp:15-21` refused: a hovering player gets a stable background and a flickering palette. Hysteresis belongs in the one crossing, once.
- Reversal: once the overwrite starts the old tiles are gone; walking back mid-sequence costs a second full sequence (another 13-27 blank frames). A spring or bounce across a horizontal boundary at 16 px/frame passes any small margin, so the Y margin must exceed jump height, or the authoring tool must refuse a boundary within jump reach of a spring.
- Re-entrancy: "bg change within a zone" implies small regions; a player at speed can enter region C before A-to-B finishes. The level-triggered arm handles the repaint retarget, but what the overwrite phase does when its target changes is undesigned.

**5. Two existing Plane B writers will paint garbage mid-sequence unless gated.** MEASURED.
- The steady-state streamer paints entering rows from the effective layout every frame the window moves (`bg.emp:748-777`), and `Section_RedrawPlanes` blits the region layout synchronously (`engine/level/section.emp` ~:620-680, reached via `Section_Plane_Dirty`, whose only setters are level init and the DEBUG warp, `section.emp:792`). Both read the arena. Both must draw blank (or nothing) during blank+overwrite and from the new blob after.

**6. Boot, respawn and warp into a non-default region become wrong by construction.** MEASURED.
- `BG_Init` loads only `Act.act_bg_tiles` (`bg.emp:144`); `Region` has `rg_bg_layout` and `rg_bg_span` and no tiles field (`engine/structs.emp:132-149`); `Section_RedrawPlanes` then blits the region's layout over the act's tiles. Harmless today (one blob), garbage under full overwrite. BG-BOOT-REGION-BLIT (`docs/DEFERRED_WORK.md:35302`) goes from cosmetic to blocking; the tree has no respawn path yet (grep found only ring/starpost names), and the stress test needs one. `Region` needs `rg_bg_tiles` (and a band table), and init must resolve the boot region after `Camera_Init`.

**7. Risk 2 (BgAnim) is understated: the release shape has no table selector at all.** MEASURED. `BgAnim_Update` does `lea BgAnim_Table, a3` in release; `BgAnim_Table_Ptr` exists only under DEBUG (`engine/level/bg_anim.emp:256-261`). Per-region bands are a release RAM word plus an ordering contract (pause bands at arm; band DMAs and overwrite DMAs share the deferrable queue). Also "every region gets the whole 376" is 320 static + 56 `band_reserve` under the current importer contract (`games/sonic4/vram.toml:226-236`) unless the reserve becomes per-region.

**8. Palette at a horizontal junction (risk for the owner under R6, not a correction).** During the blank the background palette question is moot, but the OLD zone's foreground occupies half the screen under the NEW zone's lines 1-3 for at least 160 px of travel, and both zones' foregrounds share 45 colours whenever they are on the same scanlines. The position-driven blend (§3.5) is the mitigation; until it exists, junctions between differently-coloured foregrounds will look wrong for a second at walking speed.

**9. §3.2/§4 overclaim Icecap, and miss the mechanism that actually argues for §3.1.** MEASURED counters, INFERRED cause.
- MEASURED: the trigger and the two counters (`skdisasm/sonic3k.asm:110257-110283`, `2802-2808`); and the next module is queued on the *next* `Process_Kos_Module_Queue` call, not in the same one (`:2735-2790`), so `Kos_decomp_queue_count` can read 0 while `Kos_modules_left` is nonzero. The gap is real.
- But the reconciliation labels the causal link INFERRED (`00-controller-reconciliation.md:34-38`) and the design upgraded it to "verified firsthand". And there is a second mechanism nobody weighed: ICZ2's secondary set lands at `$122` (`:110268`), the same base ICZ1's secondary occupies, since both acts share `ICZ_8x8_Primary_KosM` (`:199313-199314`). Visible ICZ1 art is overwritten in place module by module regardless of any gate; a correct gate would not remove that. Only a blank or a mask does, which is a stronger argument for §3.1 than the one given.

**10. M-A's budget figure is the act art budget, not the window.** 4096 B/frame is `act_art_budget`; the VBlank window is 6144 shared with the plane drain (worst case 1328 B BG + 536 B FG, `bg.emp:503-512`) and the uncharged riders. Whether the overwrite really gets 4096 B/frame during a fall with FG streaming is exactly what M-A must measure; the derived "~3 frames" is a floor.

**11. Sonic 4 vs the stress test.** The background design serves both. What the stress test needs and the design never mentions: per-zone object art (the VRAM map has one free tile, slice 06 Q3), and the foreground budget from finding 1. For Sonic 4 specifically, the tension is finding 3: the goal is regions that feel different, the mechanism gives abrupt swaps behind tunnels. R7's blend suggests the owner pictures gradual crossings; he should know full overwrite cannot give that for the background itself.

## Anything wrongly superseded

- **D4's check, yes; D4's mechanism, no.** The corridor as a mechanism is correctly gone. The build-time computation of "minimum cover = screen + T × v_max at this crossing" against the authored opaque-foreground extent was the valuable half, and it is exactly the warn-don't-refuse shape R5 asks for. Bring it back as a warning.
- **OC-3's ruling vanished.** v1 recorded the owner's answer ("Maybe hold, I guess we should see how long it is") and v2 §2 neither carries nor supersedes it. Under full overwrite the analogue is "cover shorter than the sequence": holding the camera at the cover's end using the existing `Camera_Art_Hold` is the engine-side safety net. Book it as an owner option, not a silent drop.
- **The runtime two-slot A/B scheme was correctly superseded**, but note for the record it is the only design with no blank at all; the measured S3K backgrounds (104-174) fit 188. If finding 3's cover cost proves too heavy in play, that is the fallback to reconsider, not the colouring.

## Measurements and ordering (§5, §7)

- **M-B first**, and redefined: the 80×60 window's page set along a stitched real-zone seam and at a three-zone junction, run through the existing strip/page tools. Tool-only, no engine change, and it decides whether the stress test exists. Add **M-E**: confirm the release-shape soft-lock under the existing stress-uniquify fixture (one emulator run).
- **Choose the blank transport before M-A**, then measure M-A as the full three-step sequence under the worst case: a fall at 16 px/frame with FG streaming active, on NTSC.
- **Add M-D**: cover length per crossing, derived from M-A × v_max plus screen width, feeding the build warning.
- **M-C** (hysteresis) must be measured at the crossing, not at the background, and on both axes.
- §7: put M-B and M-E before step 2; add "overwrite transport + streamer/redraw gating + boot-region tiles" to step 2's scope (findings 2, 5, 6); the BgAnim handover (step 4) needs the release selector (finding 7); the position blend stays last.

## What I could not determine

- Whether Icecap's visible lag is the gate or the in-place overwrite: needs an emulator, and the ban on MCP from a background agent stands.
- The real DMA fill rate on Oracle's model (hence the blank's cost); slice 05's sources disagree by two lines and one byte per line.
- Batman's `$330FC` script byte order (blank before upload of the same range): I verified the trigger and the fill handler's constant, not the script bytes.
- Sonic 2 background-only tile counts (unchanged from the design's own caveat).
- Whether 4096 B of upload plus the plane drain plus fixed riders fits the 6144 window on a bad frame: needs the profiler.

## Anything found false in the design or its notes

- §3.6: "an over-budget spot STUTTERS" and "if the visible screen alone references more art than the pool holds" — wrong on both counts (finding 1).
- §3.2 and §4: Icecap's cause labelled "verified firsthand"; the reconciliation itself labels it INFERRED (finding 9).
- §5 M-A: the "about a sixth of a second" estimate covers two of three steps (finding 2).
- §3.1: "Every region gets the whole 376-tile background block" — 320 static plus a 56-tile band reserve under today's contract (finding 7).
- §3.6: "the pinning rule stops meaning anything" — mild overstatement; page 0 is always pinned (`tools/ojz_strip_gen.py:142` comment), so it degrades to "pin page 0", which is harmless rather than meaningless.
- §2: the OC-3 ruling dropped without record.
- Cited line numbers I checked hold: `palette.emp:86` (`PAL_FADE_FRAMES`), `preset.emp:67` (`ep_transition`), `structs.emp:355` (`pcfg_transition`), `constants.emp:557` (`CLAMP_MARGIN_TILES`), `:648` (`BG_TILE_CAPACITY = 376`), `ojz_strip_gen.py:142` (0.75). Slice 06's "Region has no tiles field" is MEASURED and correct.
