# Deferred Work

Tracks work that was identified during design/implementation but deferred because dependencies don't exist yet. Check this document at the start of each new system's planning phase — items here may now be unblocked.

> **Open defects** (not deferred features) live in **`docs/BUGS.md`**. See BUG-001: intermittent
> section-streaming rendering corruption (garbage tiles + red field) — captured live-emulator evidence.

---

## ✅ RESOLVED — OJZ section-0 tile-budget overflow — 2026-06-22

**RESOLVED 2026-06-22** via the globally-deduped paged act art pool (OJZ_ACT_POOL_TILES,
page loader), merged to master. The build succeeds and boots — every continuous-scroll
phase since (including Phase 2's on-device oracle verification) has run a bootable ROM.
Historical record retained below.

**Original report — The build failed** (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`) at the art-budget
check: `sec0_tiles.bin is 19296 bytes — exceeds Decomp_Buffer capacity (9600)`.
This blocked **all** runtime work — no bootable ROM. Surfaced as "OJZ layout edits
weren't showing in game."

**Root cause is engine-side, not bad level data.** Whole level = 612 distinct tiles
in a 1,536-tile FG VRAM pool (60% empty); user's "shouldn't need so many tiles"
intuition was correct. The per-section streaming + DSATUR color-grouping pipeline
duplicates tiles across two VRAM regions and forces section 0's 603-tile blob
through a 300-tile (`9,600 B`) RAM staging buffer (`Decomp_Buffer`).

**Recommended fix (engine + build tool):** whole-level shared tileset loaded once
(the Sonic 2 model) when total distinct tiles ≤ VRAM capacity — skip color-grouping,
emit one shared tileset, decompress in N≤300-tile passes at level init. Full analysis
+ numbers + the alternative (multi-pass per-section decompress) in
**`docs/research/2026-06-22-tile-budget-deep-dive.md`**.

**⚠ Touches `tools/ojz_strip_gen.py`** — which the auto-commit daemon watches (commits
edits as the user ~60s after change). Coordinate with the user before editing it;
don't edit it autonomously. Needs the user's go-ahead on approach (shared-tileset vs
multi-pass) before implementation.

---

## ✅ RESOLVED — Engine Phase 3 cleanup — 2026-06-23

Behavior-preserving cleanup (branch `cleanup/engine-phase3`). A 114-agent
verified-clean audit confirmed the leapfrog teardown left no dead code paths;
the engine's "orphan" constants are intentional design surface (hardware-register
sets, flag/enum layouts, DEFERRED_WORK-tracked scaffolding), not cruft. Shipped:
- Removed the `SOUND_LOADTEST` debug scaffold (asm block + `build.sh` flag).
- `BG_TILE_CAPACITY` 512→448 reconciled (see the entry below).
- Removed two true vestiges: the `ANIM_BALL` alias and the dead `Sprite_Link_Next`
  write + RAM field.
- Whole-engine comment hygiene (non-sound): stripped historical/lying/task-tag
  comments, kept load-bearing rationale; binary-neutral (ROM byte-identical).
- `ENGINE_ARCHITECTURE.md` reconciled to the shipped paged-dedup pipeline
  (no graph-coloring/DSATUR/`LoadSectionTiles`/per-section art swap; ZX0 act pool;
  §4.2 `Sec` struct corrected to the real 66-byte / `$42` layout); §7 marked PLANNED.
- `CLAUDE.md` pipeline description corrected (graph-color → dedup + spatial paging).

### DEFERRED — Phase 3 follow-ups (not done this pass)
- **Sound-subsystem comment lineage (~151 tags).** `sound_*.asm`,
  `z80_sound_driver.asm`, `sound_constants.asm`, `main.asm`, `game_loop.asm` carry
  dense `(Task N)`/`(Phase N)`/`(Sound 1X)` build-lineage in comments. Deferred to a
  dedicated pass — large, judgment-heavy, on a subsystem not otherwise being
  modified, and many tags sit on otherwise-good descriptions.
- **`CLAUDE.md` "What This Engine Is" residual staleness.** L105 still says
  single-tier "S4LZ compression (level/bulk art)" — it is two-tier now (ZX0 act-pool
  pages + S4LZ runtime block stream). L106 says "Flamedriver sound driver" — the
  shipped driver is the custom sequencer (`engine/sound_*.asm` + the Z80 driver),
  not Flamedriver. **RESOLVED 2026-06-23** — both fixed (L105 → two-tier ZX0 + S4LZ;
  L106 → from-scratch custom Z80-autonomous driver).
- **`ENGINE_ARCHITECTURE.md` §8.1b "Level Editor Tile Budget UI."** Its per-corner /
  4-way-corner-adjacency budget model is the old graph-coloring premise; under the
  global-dedup resident pool the relevant metric is a single global tile cap, not
  per-corner adjacency. Rewrite when the editor budget UI is revisited.

---

## From §5 — Player System

### Cycle Profiler (§8.5) Not Wired — Frame-Budget Measured via Lag Counter — 2026-06-14
**Surfaced during:** §5 Task 10.4 frame-budget pass.
**Status:** The §8.5 raster-bar / lagometer cycle profiler is NOT built. The
`Prof_*` RAM block (`ram.asm`: `Prof_RunObjects`/`Prof_TouchResponse`/
`Prof_RenderSprites`/`Prof_FrameTotal` + their `Prof_Peak_*`, DEBUG only) is
declared but written NOWHERE — confirmed live: all sixteen bytes at
`Prof_RunObjects` (0xFF89FC) read zero during active gameplay. This matches
spec §9 item 10's own note ("the §8.5 profiler is not built yet").
**Measured instead** via the wired `Lag_Frame_Count` (0xFF89F8, incremented in
`VInt_Lag` whenever the main loop misses VBlank): with the player active on OJZ,
**steady-state gameplay = 0 lag frames over 120 frames** (full game loop —
player physics + camera + render — completes within the ~224-line NTSC
active-display window before VBlank). Spindash launches at $7FA gsp added zero
lag. The only lag observed (+13 frames over a 250-frame run that crossed
terrain) was section-streaming art DMA during teleport/preload — amortized
deferrable DMA by design, not the per-frame player cost. The Task 10 camera
additions (landing lock + spindash freeze) are a few byte-tests + branches,
~10-20 cycles/frame, negligible.
**When to revisit:** Build the real cycle profiler if a future workload (dense
badnik + multi-part boss + heavy parallax) starts producing steady-state lag
frames; until then the lag counter is a sufficient pass/fail budget gate.
**See:** `docs/superpowers/specs/2026-06-12-player-system-design.md` §9 item 10.

### Removed Up-Velocity Cap — Launch-Cap Coupling (§2.1 FEEL DEVIATION) — 2026-06-12
**Surfaced during:** §5 Task 6/7 (commit 04b492b region).
**Status (intentional, shipped):** the classic non-jump airborne up-cap (`y_vel`
clamped to `-$FC0`) is **removed**. Launches are instead bounded by
`PHYS_GSP_CAP = $1000` (the SPG-placement ground-speed tunneling guard). The
`; FEEL DEVIATION` comment lives at the clamp site in
`engine/player/player_air.asm` (`PState_AirShared`, after the fall-cap).
**Coupling — do NOT change in isolation:** if launches ever feel truncated, the
knob is `PHYS_GSP_CAP`, and raising it is a **coupled** change. These must rise
together or the player will outrun streaming / tunnel through geometry:
- `CAM_MAX_Y_STEP` (16 px/frame, the camera-follow clamp the fill relies on),
- `VFILL_ROWS_PER_FRAME` (2 rows/frame — the VBlank-bound streaming contract;
  >2 overflows VBlank into active display, see §4.7),
- the 32px sensor reach (swept collision must cover one frame's travel).
Do not re-add the `-$FC0` cap silently. The separate `$FC0` cap in the
steep-landing conversion is a different, retained mechanism.

### §5 Deferred Items — Player/Character Follow-Up Work — 2026-06-14 (updated 2026-06-15)
**Status:** §5 (player-system branch) shipped Sonic-only, physics-first, on OJZ
with real collision, the full sensor layer, ground/air/roll/spindash, the loop,
and camera landing lock + spindash freeze. feat/sonic-animations added the full
animation set, speed-scaled timing, and shared spindash. Per spec §1, the
following are deliberately **deferred to follow-up plans** (not bugs):
- ~~**Sonic art / animation / DPLC** — a real sprite set + animation driver beyond
  the placeholder test art.~~ **DONE (feat/sonic-animations):** full ANIM_* contract
  (11 ids, build-time assert), `Player_Animate` read-only classifier, `DUR_DYNAMIC`
  speed-scaled timing in `AnimateSprite`, shared spindash in `player_spindash.asm`,
  `Player_AtLedgeEdge` balance probe, DEBUG anim viewer. Sonic's sprite art DATA is
  the real CUSTOM Sonic set migrated from sonic_hack (`art/optimized/characters/sonic.bin`,
  mappings + DPLC; frame-index layout follows the S2 convention, but the pixels are
  our custom design — NOT stock S2). Still provisional is the VRAM SLOT —
  `VRAM_TEST_SONIC` is a hand-placed test slot, not yet allocated via the build-time
  graph-color allocator (separate art-pipeline task).
- ~~**Spindash shared across all 3 characters** — `PState_Spindash` was in
  `sonic.asm`, blocking Tails/Knuckles.~~ **DONE (feat/sonic-animations):** relocated
  to `engine/player/player_spindash.asm`; resolves `ANIM_SPINDASH` per-character via
  the `ANIM_*` contract. `sonic.asm` now holds only `Sonic_InitAssets`, `Sonic_LoadArt`,
  `PhysTable_Sonic`.
- **In-game get-up trigger** — `ANIM_GETUP` (id 10) is defined and viewer-visible
  but nothing arms it in gameplay. A future pass needs the "just landed after a hurt"
  state to write `ANIM_GETUP` into the classifier path (or a dedicated PSTATE).
- **Duck / look-up camera pan** — duck and look-up are display conditions computed
  each frame (no new PSTATE); the camera-pan half is NOT implemented. The field
  `_pl_look_offset` is reserved as a zero-valued seam in the `PlayerV` SST overlay
  for the future pass that wires this up.
- **Balance threshold tuning** — `LEDGE_NO_GROUND` in `player_sensors.asm` is
  flagged as tunable; the current value is a first estimate.
- **Dropdash, instashield** — Sonic move-kit extensions.
- **Super Sonic** — transformation, palette cycle, physics row.
- **Tails** — CPU AI (4-state machine) + flight physics + position-history-buffer
  following (the `Player_Pos_Ring`/`Player_Stat_Ring` are already recorded for this).
- **Knuckles** — gliding, climbing, wall detection.
- **Per-character dispatch-table indirection** — the prerequisite refactor for
  Tails/Knuckles (today `Player_States` and `PhysTable_Sonic` are referenced
  directly; siblings need a character base-pointer). See the `Player_States`
  comment in `player_common.asm`.
- **Shields + damage + loss-rings** — shield objects, hit/invuln response, ring
  scatter (loss-rings is also tracked under §4.9).
- **Water** — and with it the **per-section physics modifier / Lerp system** (the
  RefreshPhysics plumbing shipped with an identity modifier; the modifier tables,
  section references, and boundary Lerp are the deferred half — see
  `ENGINE_ARCHITECTURE.md` §5.2).
- **6-button mappings** — X/Y/Z/Mode gameplay actions (detection exists, §5.1).
- **Forced-roll objects (S-tunnels)** — bypass the roll-start gate, use
  `PHYS_ROLL_FORCE_MIN` at rest; the `stick_convex` full-adherence flag and the
  roll-start gate already have the hook comments.
- **The §8.5 cycle profiler** — unwired (see the Cycle Profiler entry above).

---

## From §1 — Core VDP Pipeline

These subsystems are fully designed in ENGINE_ARCHITECTURE.md §1 but require other systems to exist first.

### Plane_Buffer "complete" guard — TRIED + REJECTED (not viable) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 6 gate (the diagonal-corruption fix, commit `b96c861`).
**Status: REJECTED.** Built + oracle-tested on branch `feat/plane-buffer-complete-guard` (commit `fb81809`, left UNMERGED for inspection). The idea was: add a `Plane_Buffer_Complete` flag set after the fill phase, gate `VInt_DrawLevel` on it, and re-add the drain to `VInt_Lag` so lag frames drain a *completed* buffer (killing the sustained-lag stutter) without the mid-fill tear. It IS corruption-safe (diagonal stayed clean across the corner), **but it is a net regression, not an improvement, for two reasons:**
1. **Plane/sprite desync.** The plane buffer completes at `Section_UpdateColumns` (ojz_scroll_test.asm:179) but the sprite table completes later at `Render_Sprites` (:188). A lag-frame drain firing in the window [179,188] commits NEW planes while the sprite table in VRAM is still LAST frame's → the world scrolls one frame ahead of the player sprite. The only desync-free drain point is "whole visual frame complete" = `VBlank_Ready` = exactly `VInt_Level` — i.e. there is NO safe lag-frame drain that also keeps sprites in sync, so the guard cannot deliver its benefit.
2. **+~10% lag.** Re-adding the drain to `VInt_Lag` extends the VBlank handler, stealing main-loop time and pushing borderline frames over: sustained-max-diagonal went 76% → 86% lag (measured).
**Conclusion:** `b96c861`'s whole-frame-defer is the CORRECT design — on a lag frame the screen shows the last *coherent* complete frame (planes+sprites together), which is the classic behavior; the "stutter" is just the framerate drop, not a fixable drain-timing artifact. The real lever for the sustained-diagonal lag is the **diagonal streaming budget** (below), not drain timing. Delete the branch if not inspecting.

### Diagonal streaming budget — ~76% lag at sustained MAX diagonal (§4.7 / §1.1) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 6 diagonal stress (PRE-EXISTING — master shows the same lag).
**Status:** Sustained MAX diagonal scroll (both axes at CAM_MAX=16px/frame) runs ~76% lag frames (genuine fill cost, not corruption — that's fixed). Profiler: Tile_Cache_Fill ~25% (FillRow+FillColumn+Decompress) + HInt ~24% + Process_DMA_Deferrable ~18% + parallax ~14%. The zero-slack contract `CAM_MAX_Y_STEP == VFILL_ROWS_PER_FRAME*8` was sized for SINGLE-axis motion; diagonal runs BOTH column-fill and row-fill against the shared `BLOCK_DECOMP_BUDGET=6`, roughly halving the effective per-axis budget.
**What:** Investigated 2026-06-23 (read-only profiler + code analysis). The cost is dominated by ESSENTIAL work with no significant redundancy — there is NO clean safe fix:
- `Tile_Cache_Fill` ~25% — column-fill (X) + row-fill (Y) both run, sharing `BLOCK_DECOMP_BUDGET=6`. Corner cells are NOT double-decompressed (`TileCache_FindStagedBlock` hits the staging slot). Clean.
- VBlank/"HInt" ~24% (vs ~4.6% stationary) — the **per-line HScroll DMA**: 896 B/frame (vs 112 B per-cell) queued by `Enqueue_Dirty_Buffers`, drained by `Process_DMA_Critical`. NOT for a shimmer (OJZ's `deformBg=DeformTable_Zero` is all-zeros — no deform); it carries the 4-band BG parallax AND deliberately works around a **live VDP `$0B` shadow→register propagation bug** (see the per-cell entry below). This ~20%/frame is a FLAT tax (same stationary or scrolling), so it's the single biggest lever — but NOT capturable by a config flip (proven below).
- `Process_DMA_Deferrable` ~17.5% — `BgAnim` animated-tile-band DMAs (+ any DPLC); already step-gated, all essential.
- `Parallax_Update` ~7.4% — per-line deform fill; essential.
Safe wins are small AND mostly DON'T help diagonal: an HScroll-DMA dirty-gate is near-useless here (the deform phase animates EVERY frame → buffer always dirty); skipping parallax Step-4a when vscroll is unchanged (~2%) only helps horizontal-only. So a real reduction needs a FEEL/VISUAL tradeoff — the user's call: **(A) accept the dip** (it's gameplay-rare — sustained MAX diagonal across corners; brief diagonals recover instantly; classic Sonic also slows under extreme load); **(B) lower `CAM_MAX` on diagonal** (detect dual-axis motion, cap the combined step — camera follows slightly slower); or **(C) cut non-essential BgAnim bands / parallax deform during fast scroll** (lose some visual flourish). Do NOT raise `CAM_MAX_Y_STEP` 16→24 (diagonal already saturates). Recommendation: (A) accept for now; revisit with (B)/(C) only if aggressive diagonal traversal becomes a design requirement.

### Per-cell HScroll (~20%/frame) — NOT ACHIEVABLE (per-cell can't do pixel-precise band boundaries) — 2026-06-23
**Surfaced during:** diagonal-budget investigation (the per-line HScroll DMA is the biggest single flat cost).
**Status: CLOSED — not achievable for OJZ's parallax.** Root-caused on hardware (VDP-register read, 2026-06-23). The chain:
- **`$0B` is NOT the problem.** With `deformBg` dropped, the VDP register `$0B` reads `$02` (`hscroll_mode: cell`) correctly — per-cell IS active and the shadow→register propagation works fine. The original `DeformTable_Zero` comment's "intermittent `$0B` stuck at `$03`" explanation was a **MISDIAGNOSIS**; a flush-side latch-reset "fix" (`Flush_VDP_Shadow`) was tried and changed nothing (branch `fix/vdp-mode3-propagation`, deleted).
- **The real cause is band-boundary precision.** A BG parallax band's on-screen boundary = `band_top_plane_row*8 − BG_vertical_scroll`. With smooth per-pixel vertical parallax (`vFactorBg`), those boundaries land at ARBITRARY screen lines (measured the per-line table putting one at **line 22**). Per-cell mode can only change scroll at 8-px cell-rows (lines 0,8,16,24…), so it rounds line 22 → 16/24, misaligning each band by up to 7 px → the FG/BG **tears at every band boundary during scroll** (user-confirmed at Cam `$02D0,$019D`; reproduced in free-fly).
**What:** Nothing — per-line (`DeformTable_Zero`) is mandatory for smooth banded vertical parallax and stays. The only way to use per-cell would be to give up smooth vertical scroll (chunky 8-px-stepped vscroll), which is not worth ~20%. Do NOT re-attempt the per-cell switch. Lesson: a settled/at-rest frame HIDES scroll-time tearing — verify under continuous motion ([[feedback_verify_during_motion]]), and read the actual VDP register before theorizing about propagation.

### ✅ RESOLVED — BG_TILE_CAPACITY reconciliation (512 → 448) + BG_Init guard (§2 A.5) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 5 doc-sync (PRE-EXISTING cross-tool inconsistency the SAT relocation left behind).
**Status:** The SAT was relocated to $B800, making it the BG region's hard ceiling — usable BG space is $8000-$B7FF = **448 tiles**, not the nominal 512 ($8000-$BFFF, which now overlaps the SAT). The value is inconsistent across the pipeline: `tools/inject_editor_bg.py` already uses 448 (correct), but `constants.asm BG_TILE_CAPACITY` and `tools/ojz_strip_gen.py BG_TILE_CAPACITY_PY` still say 512. **PARTIALLY ADDRESSED 2026-06-23 (commit 0aab611):** `engine/level/bg.asm` `BG_Init` now CLAMPS the blob copy to `BG_TILE_REGION_BYTES` ($8000-$B7FF), so it can no longer spray into the SAT (the runtime last-line guard). OJZ is safe today (340 tiles ≤ 448). **RESOLVED 2026-06-23 (Engine Phase 3 Task 2):** both `constants.asm BG_TILE_CAPACITY` and `tools/ojz_strip_gen.py BG_TILE_CAPACITY_PY` now gate at 448; the full build passes at the tightened gate. A too-large BG blob now fails at generation (the `ojz_strip_gen.py` assert) instead of being silently runtime-clamped.
**What:** Reconcile the gate to 448 in `constants.asm` AND `tools/ojz_strip_gen.py` (the latter is auto-commit-daemon-watched — coordinate with the user, do NOT hand-edit autonomously). Add a runtime/build guard in `BG_Init` (or an AS assert) that the BG blob ≤ `VRAM_SPRITE_TABLE - BG_TILE_BASE_VRAM`, so a future >448-tile blob fails loudly instead of silently spraying into the SAT.

### Editor-export Act descriptor format drift (§8 tooling) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 final review.
**Status:** `data/editor/ojz/act1/export/act_descriptor.asm` is git-tracked but NOT in the build include graph (`main.asm:198` includes only `data/levels/ojz/act1/act_descriptor.asm`, which IS correct), and it would not even assemble as-is (e.g. a path where a symbol is expected). So it is no build/runtime risk. But it still emits the OLD Act layout: the removed `cam_min_x/max_x/min_y/max_y` 4-word camera block, no `edge_mode` byte/pad, and pre-paging art fields — mismatched to the current `Act_len=$22`. This dir is auto-commit-daemon-watched (do NOT hand-edit autonomously).
**What:** Update the editor EXPORTER tool to emit the current Act format (no cam bounds, `edge_mode` + pad, `act_art_pool_table`/`pages`) so a future regeneration can never reintroduce the obsolete layout into the build. Coordinate with the user (daemon-watched path). Optional belt-and-suspenders: add an AS assert at the `OJZ_Act1_Descriptor` site that the emitted descriptor size equals `Act_len`, so ANY drifting descriptor (hand-written or exported) fails the build instead of silently mis-parsing.

### Static Sub-Sprite Array — Render-Path Optimization (§1.2 / §3.5)
**Surfaced during:** §1.2 multi-sprite implementation Task 8 research (2026-04-27).
**Status:** Implementation shipped with sibling-chain walk per spec; the static-array
optimization is logged here as a real follow-up, not just research backlog.
**What:** Sonic 3K (`s3.asm:29940-30024`) and S.C.E. (`Render Sprites.asm:259-292`)
both use a **static sub-sprite array** (count + per-child X/Y/frame triplets) embedded
in parent's object data, not a sibling-pointer chain. ~10 cycles/child saved (no
null-check, tighter loop) plus simpler render-time logic. Our `sibling_ptr` chain is
already wired to `CreateChild_*` / `DeleteChildren` lifecycle, so the trade-off is:
(a) keep chain for lifecycle + duplicate to a render array (data-sync risk), or
(b) replace chain with array and refactor all `CreateChild_*` / `DeleteChildren`.
**When to revisit:** When we have a real workload showing the per-child cycle cost
matters — multi-part bosses with 6+ children, Tails-tail-style trails, formation
enemies, etc. Premature without that signal.
**See:** `docs/research/sprite-system-§1.2.md` Task 8 for the cross-engine evidence.

### ~~Sprite Rendering Pipeline (§1.2)~~ — DONE 2026-04-27
**Completed in:** §1.2 sprite-system multisprite + piece-overflow plan
**What:** Most §1.2 features (two-phase render, priority bands, overflow cascade, scanline budget, sprite mask, link-order cycling, dirty-flag DMA) shipped during §3 Object System work. Remaining bullets closed in this plan: (a) multi-sprite batching via Approach 1 + semantic C — Draw_Sprite child-skip guard for parents with `RF_MULTISPRITE`; Render_Sprites walks `sibling_ptr` chain after parent emission, indexing parent's `mapping_frame` against each child's own `mappings`; mid-chain overflow skips just the offending child. (b) `sprite_piece_count` byte at SST_$2D for predictive total-piece overflow skip; populated by Load_Object (initial frame) + AnimateSprite (per frame change via new `RefreshSpritePieceCount` helper). (c) `Render_Sprites` factored emission into reusable `Emit_ObjectPieces` subroutine. (d) ENGINE_ARCHITECTURE.md §1.2/§3.5 link-chain doc corrected — "never rebuilt" was a wash on 68000.
**Test:** TestParent + 3 children renders identically with `RF_MULTISPRITE` on (Task 8) vs off (Task 7 baseline). Sprites_Rendered observed at 49 in stress scene; pre-check + per-piece dbeq layered defenses in place.
**See:** `docs/superpowers/specs/2026-04-27-sprite-system-design.md`, `docs/superpowers/plans/2026-04-27-sprite-system-multisprite-and-piece-overflow.md`, `docs/research/sprite-system-§1.2.md`.

### ~~Scroll / Plane Drawing — Core (§1.3)~~ — DONE 2026-04-25
**Completed in:** §4 Phase 1 Level/World System
**What:** Deferred Plane_Buffer (1536 bytes), Draw_TileColumn/Row, VInt_DrawLevel with autoincrement $80 column mode, overflow protection, pre-computed nametable strips.

### Scroll / Plane Drawing — Dual Plane / Row Updates (§1.3)
**Blocked by:** Vertical section support (§4.2)
**What:** Plane B scroll support, Draw_TileRow for vertical section transitions, double-update mechanism for fast travel.
**When ready:** After §4.2 adds vertical section teleport.

### DPLC Lookahead (§1.6)
**Blocked by:** Object System (§3) — specifically AnimateSprite and DPLC tables
**What:** Predictive art loading by peeking at next animation frame's DPLC requirements one frame early. Queue as Important-priority DMA.
**When ready:** After §3 defines animation system with frame scripts and DPLC mappings.

### Adaptive DMA Byte Budget (§1.1)
**Blocked by:** Real workloads from gameplay systems
**What:** Per-frame DMA byte tracking, lag-frame budget reduction, lag recovery 1.5x burst. Self-tuning throughput based on scene complexity.
**When ready:** After enough consumers exist to generate meaningful DMA load (character art streaming, level tile loading, animated tiles).

### ~~Variable HScroll DMA — Infrastructure (§1.1)~~ — DONE 2026-04-25
**Completed in:** §4 Phase 1 Level/World System
**What:** Hscroll_Dirty_Start/End tracking, Hscroll_Update fills 28 per-8-row bands from Camera_X.

### Variable HScroll DMA — Variable-Length Transfer (§1.1)
**Blocked by:** Confirmed performance need (currently always DMAs full 224-line table)
**What:** Use Hscroll_Dirty_Start/End to DMA only the dirty scanline range instead of all 896 bytes.
**When ready:** When HScroll partial updates become a measurable DMA budget issue.

### Background Work / Cooperative Multitasking (§1.5 → §9.7)
**Blocked by:** Full design of §9.7
**What:** Supervisor/user mode context switching for background S4LZ decompression in leftover CPU time.
**When ready:** When §9.7 is designed and the S4LZ decompressor exists.

### HUD Dirty Flags (§1.4)
**Blocked by:** HUD system (part of §9.13 screen/menu system)
**What:** Per-element dirty flags (score, rings, timer, lives) to skip HUD VDP writes on frames where nothing changed.
**When ready:** After HUD rendering exists.

---

## From §2 — Art & Compression Pipeline

### ~~§2 A.5 T2/T3 — Per-Section BG~~ — VERIFIED 2026-04-27
**Engine paths proven end-to-end** via temporary fixtures in OJZ Act 1, then reverted. Production ships pure T1.
**T2 verified:** `sec_bg_layout` ≠ NULL → `BG_RedrawForSection` blits the section's authored layout to Plane B on teleport. Tested with sec1 = byte-identical zone copy (proved redraw doesn't corrupt content) and sec3 = palette-tinted variant (proved swap visually).
**T3 verified:** sec5's BG layout referenced an in-section VRAM slot (color base 0, tile 5) tiled across all 64×32 cells. After A.4 streaming loaded sec5's tile pool, the BG correctly rendered tile 5 from sec5's region — not the shared 1024+ region. Proves `BG_RedrawForSection` works for any tile_index, regardless of source.
**T1 fallback fix:** `BG_RedrawForSection` originally skipped when `sec_bg_layout` was NULL, which meant T2→T1 transitions kept the prior section's BG. Now falls back to `Act.act_bg_layout` so every transition writes the correct content.
**For real T2/T3 use:** author per-section BG layout files, BINCLUDE them, set `sec_bg_layout` in the section descriptor. The build tool's `emit_bg_tile_blob` already accepts a list of nametables and unions their referenced tiles — no CLI flags or stubs needed.
**Plan:** `docs/superpowers/plans/2026-04-26-art-pipeline-phase2-A5-per-section-background.md` (Tasks 7-10 superseded by inline verification).

### §2 A.5 — Section_Check d0-Clobber Bug — FIXED 2026-04-27
**Status:** `preload_fwd` / `preload_bwd` in `engine/level/section.asm` clobber d0 to build a section offset, but `.threshold_check` assumed d0 = Camera_X high word. After preload fired, the threshold check read garbage d0, frequently spurious-triggering BWD teleport (`d0 ≤ $200` accidentally true). Fixed by reloading Camera_X at the top of `.threshold_check`. Was masking BG verification work.

### §2 A.5 T1 — FG Plane A Tile-Flip Mismatch vs sonic_hack
**Status:** Architectural milestone shipped, but Exodus's Plane A nametable viewer shows tile-orientation differences between our build and sonic_hack's running OJZ. Build-tool math verifies correct (chunk-level X/Y flip per sonic_hack ProcessAndWriteBlock + dedupe canonicalization + strip remap), so the residual gap is likely in Exodus viewer rendering details (CRAM shadow mode, palette auto-selection) rather than build-tool output — but that's not confirmed.
**Needs:** Live A/B diagnostic with sonic_hack paused at OJZ Act 1 + our build paused at the same screen, comparing specific VRAM tile bytes.
**Doesn't block:** anything; T1 architecture is solid and BG renders correctly.

### ~~§2 A.x — FG Strips Have Wrong Content in Upper Rows~~ — RESOLVED 2026-06-11 (re-test)
**Resolution:** Does not reproduce on current master. Live Exodus verification: at camY=0 over sec0/sec1's
empty top chunks, Plane A row 0 is fully transparent across all 64 cells (blank tile $C6, no priority);
where dirt IS rendered (camX=$EB0/camY=$290 → sec1 chunk rows 1-2, cols 9-11), the on-screen content
matches the source layout cell-for-cell (empty sky chunk over 28/$1D ground chunks). Two findings:
(1) hypothesis (b) was half-right — sec1's layout genuinely has dirt chunk $1D across chunk-row 0
cols 7-15 (editor data AND sonic_hack OJZ_1_sec1.bin agree), so "brown in the sky" at world Y<128
in sec1's right half is faithful level data, not a bug; (2) the "all 64 cells filled" misplacement
was a strip-era streaming artifact — the strip pipeline was deleted and replaced by the 2D block
tile cache (2026-06-10 rewrite), which renders correctly.
Original entry (for reference): As Camera_X scrolled into sec1+, Plane A's upper rows rendered
dirt/rock chunk content with priority set (0xC846, 0xC04C — pal 2), filling the sky region; row 0
had all 64 cells filled, not just slot 0's half.

### ~~§2 A.x — BG Tiles Render Black via Palette Index 0~~ — CLOSED 2026-06-11
**Resolution:** Was contingent on the FG-rows bug above ("resolves automatically once the FG-rows bug
is fixed"). With FG rendering verified faithful to source data, remaining black pixel-0 outlines on BG
tiles only appear where the FG is *supposed* to be transparent — that's the authored art, same as
sonic_hack. No engine work to do.



### ~~Generic Perform_DPLC Routine (§2.1 / §3.9)~~ — DONE 2026-04-25
**Completed in:** §3 Object System audit cleanup
**What:** Perform_DPLC with internalized change detection (SST_prev_frame), Important and Deferrable variants. Objects pass a2=DPLC table, a3=art base, d1=VRAM dest.

### Dynamic VRAM Allocator (§2.2)
**Blocked by:** §3 Object System (`Load_Object` spawn/destroy lifecycle drives `AllocVRAM`/`FreeVRAM` calls)
**What:** Bump allocator for unified VRAM pool, loaded table tracking, refcount per type_id, lazy reclaim, section compaction.
**When ready:** After §3 defines object RAM layout and the object loop exists.

### Refcount-based Art Caching / Lazy Reclaim (§2.2)
**Blocked by:** §3 Object System (refcount increments/decrements tied to object spawn/destroy)
**What:** Freed art stays in VRAM until pool needs space. Re-spawn of same type is free (refcount bump, no decompression).
**When ready:** After §3 and the dynamic VRAM allocator exist.

### Build-time Graph Coloring (§2.3)
**Blocked by:** §4 Level/World (section adjacency graph) + §8 Build Tools (tile deduplication pipeline)
**What:** Non-adjacent sections share VRAM tile indices. Build tool computes coloring from section adjacency graph.
**When ready:** After §4 defines section grid and §8 has flatten/deduplicate pipeline.

### Section-aware Streaming / Predictive Preloading (§2.1/§4.8)
**Blocked by:** §4 Level/World (section transition triggers, camera position, leapfrog loading)
**What:** Deferrable-priority DMA streaming of next section's art based on camera velocity and direction.
**When ready:** After §4 implements section transitions and camera system.

### S4LZ Streaming Mode (§2.1)
**Blocked by:** §9.7 Cooperative Multitasking (interruptible decompression with VBlank context switch)
**What:** Bookmark-based interruptible decompression. VBlank preempts mid-decompress, resumes next frame.
**When ready:** After §9.7 supervisor/user mode exists. Blocking mode handles all current use cases.

---

## From §3 — Object System (Research Phase)

These items were identified during §3 Phase 0 research but require a full SST field audit before committing.

### SST Field Audit & Size Re-evaluation (§3)
**Note (2026-06-10):** objects-formats-v2 resolved the dead-field/metadata half of this audit — `respawn_index`, `wait_timer`, and the separate priority word are gone; entity-window metadata (`slot_tag`/`entity_section_id`/`entity_list_index`/`layer`) packed at $2A-$2D; `sst_custom` grew to 34 bytes at $2E.
**CLOSED (2026-06-14, §5 player work):** the player overlay fits 34 bytes with room to spare — **`PlayerV_len` = $D (13 bytes)** of the 34 available (`engine/player/player_common.asm`: ground_speed, player_state, status_secondary, move_lock, spindash_charge, flip_angle, air_left, invuln_time, stick_convex, debug_flag; the last five are reserved/debug). The DPLC table and art base are **per-character code immediates** (`lea` in `sonic.asm`), NOT SST fields, so the 9-byte test_player DPLC-in-SST pattern is not carried over. No per-pool stride, no variable SST sizing, no SST growth needed for the player. The general SST-shrink question (below) stays open but is decoupled from the player.
**Blocked by:** Implementation of player subsystem (need real player field pressure)
**What:** Audit every SST field across all object types (player, badnik, platform, effect, boss, system) once subsystems are implemented. Determine actual field usage per type. Evaluate whether the SST can shrink from $50 to $4C or $48.
**When ready:** After §3 Phase 3 (animation) and Phase 4 (collision) are implemented — enough subsystems exist to see real field pressure.

### ~~Word code_addr at $00 (§3)~~ — DONE (superseded by objects-v2, 2026-06-10)
Shipped: SST $00 is a word offset from `ObjCodeBase`, `objroutine()` computes it at build time, and the object bank has a build-time 64KB overflow guard.
**What:** Use a word offset at $00 instead of longword function pointer (sonic_hack pattern). `objroutine function x,(x)-ObjCodeBase` computes offset from a $10000-aligned code bank. Dispatch: `moveq #BANK, d0; swap d0; move.w (a0), d0; movea.l d0, a1; jsr (a1)`. Saves 2 bytes per SST, 20 cycles per dispatch (~1,320 cycles/frame across 66 slots). Constraint: all object code must fit in one 64KB bank.

### Word Mappings Offset (§3)
**Blocked by:** SST field audit
**What:** Use a word offset for `mappings` instead of a longword ROM pointer. All sprite mappings would live within 64KB of a base address. Saves 2 bytes per SST. Combined with word code_addr, that's 4 bytes freed — may enable SST shrink.
**When ready:** During SST field audit. Requires organizing mapping data contiguously.

### Variable SST Sizing — Effect Pool (§3)
**Blocked by:** SST field audit (need to know actual effect field usage)
**What:** Thunder Force IV uses $20/$40/$60 per-type pools. A $20 effect SST (explosions, dust, score popups, debris) shares the $00-$19 prefix with the full SST, enabling shared routines (ObjectMove, Draw_Sprite). Saves ~768 bytes at 16 effect slots. Trade-off: separate RunEffects loop, effects can't use routines that access fields past $19 (e.g., AnimateSprite needs anim_table at $28).
**When ready:** After SST field audit determines which fields effects actually need. May be unnecessary if SST shrinks enough overall.

### ~~Pack collision_resp + width + height for Single-Longword Init (§3)~~ — SUPERSEDED by objects-v2 (2026-06-10)
The burst-copy spawn (`movem.l` of the whole $0A-$21 template block) makes per-field init moot — collision_resp/width/height arrive with everything else in one copy.
**Blocked by:** SST field audit + Load_Object init path performance pressure
**Source:** TheBlad768's S.C.E. and S1-in-S3 collision refactors (`d1e24ee` / `05512e4`) put `collision_type`, `collision_height`, `collision_width` adjacent so spawn init can do `move.b d0,collision_type(a0); swap d0; move.w d0,collision_height(a0)` — three bytes initialized from one ROM longword. Currently `collision_resp` is at $0F and `width_pixels`/`height_pixels` at $18-$19, so they need separate fetches.
**What:** Reorder SST so the type byte is adjacent to the width/height pair (or move both into the $0E neighborhood). Lets objdef tables emit `dc.b coltype, colh, colw, pad` and Load_Object init reads them in one `move.l`. Rough estimate: ~10-20 cycles saved per spawn × spawn frequency. Not free — reorder breaks the current $00-$19 "shared-prefix" boundary that we may want for a future $20 effect SST, so these two items must be evaluated together.
**When ready:** During SST field audit, alongside the effect-pool decision.

### ~~Object Data Macros (`subObjData` family) (§3)~~ — DONE (superseded by objects-v2, 2026-06-10)
Shipped as the `objdef` named-parameter macro (26-byte archetype image) plus `objentry`/`objend` for placement lists — semantic args, build-time validation.
**Blocked by:** Objdef format finalization (currently still raw `dc.b`/`dc.l` in `data/objdefs/test_objects.asm`)
**Source:** S.C.E.'s `subObjData frame,coltype,(colh/2),(colw/2)` macro hides the field layout behind a named-parameter call so reordering SST fields doesn't ripple through every object table. Same idea for child priority data, animation script entries, etc.
**What:** Once the objdef format is stable, wrap the byte/word emission in `function`-and-macro pairs that take semantic args (`coltype`, `colh`, `colw`, `frame`, `priority`, ...) rather than positional bytes. Uses our `function` for any /2 or shift conversion, `struct`/`endstruct` patterns where appropriate. Pure ergonomics — zero runtime cost, but it's the difference between objdef tables that read like data and ones that read like a binary blob.
**When ready:** When more than 2-3 objects exist and the objdef format stops churning.

### Multisprite children vs parent bbox culling (§3.5)
**Surfaced during:** objects-formats-v2 final review (2026-06-10).
**What:** Exact parent-bbox culling governs whole multisprite batches (children
skip independent registration), so a child extending beyond its parent's own
frame bbox can pop at the screen edge earlier than under the old ±32 margin.
No multisprite content exists yet.
**When to revisit:** first boss/multi-part object — either author parent frames
whose bbox covers the chain's extent, or have the generator union child extents.

### SST frame-pointer cache (§3.5)
**Surfaced during:** objects-formats-v2 T8 review (2026-06-10).
**What:** Draw_Sprite and Render_Sprites each resolve mapping_frame → frame data
per object per frame (~46 cycles each). RefreshSpritePieceCount/
PopulateSpawnedPieceCount already run at every mapping_frame write, so caching
the resolved frame POINTER in the SST (one long from sst_custom) has a ready
invalidation contract and saves ~90 cycles per rendered object per frame.
Caveat: the multisprite sibling walk indexes child mappings with the parent's
frame and must keep its inline resolve.
**When to revisit:** when profiling shows object-loop pressure (~20+ on-screen
objects), alongside the §3 SST field audit.

---

## From s4lint — Static Analysis (Phase 1)

### Fall-Through State Carry-Forward
**Blocked by:** Real codebase patterns that use fall-through across global labels during VDP access
**What:** When a routine doesn't end with `rts`/`rte`/`bra`/`jmp`, carry Z80/interrupt state forward to the next global label instead of resetting. Currently all state resets at every global label boundary.
**When ready:** When fall-through patterns appear in engine code that cause false positives on E006/E007/E008.

### Sprite Multiplexing for Particle/Weather Systems (§3.5)
**Blocked by:** HBlank handler infrastructure, weather/particle system design
**What:** Rewrite SAT entries mid-frame via HBlank to display 80+ visual sprites from 3-5 physical SAT entries. Each HBlank updates Y/X/tile for a small set of sprites, scanning them down the screen. 18 bytes/scanline VRAM bandwidth, ~92 68k cycles per HBlank handler. Best for simple, repetitive effects (rain, snow, starfields) where sprites are small and never share scanlines. Too constrained for general Sonic gameplay (diverse objects at varying positions).
**When ready:** When a weather or particle system needs more than 80 simultaneous sprites. Stone Protectors (falling snow, 3 sprites × 8 scanlines) is the reference pattern.

### Object-vs-Object Collision (§3)
**Blocked by:** Real gameplay objects that need it (boulders, boss parts, projectiles)
**What:** Current TouchResponse is player-vs-object only. For object-vs-object cases (two boulders bouncing, boss parts checking each other, shields vs projectiles), add a `CheckObjectPair` helper that takes two SSTs, does the same AABB test, and returns overlap data. Objects call it from their own per-frame routine against specific targets. A full O(n²) object-vs-object pass is overkill — object-side polling is the Sonic-era pattern.
**When ready:** When a gameplay object needs to react to another non-player object.

### W010 Loop Detection Refinement
**Blocked by:** When suggestion-tier noise becomes annoying even with `--no-suggestions`
**What:** W010 (indexed addressing in loops) currently triggers after ANY local label, not just actual `dbf`/`dbra` loop bodies. Should only flag indexed addressing between a local label and the `dbf` that references it. Phase 3 reclassified W010 as a suggestion (not warning), so the noise is lower-priority now.
**When ready:** When the false positive rate is still disruptive even as a suggestion.

---

## From §4 Phase 1 — Level/World System

### Path-B collision content — wire the secondary index through the strip generator (§4.7)
**Surfaced during:** objects-formats-v2 T7 (2026-06-10).
**What:** Dual-layer collision SHIPPED format-wise (768-byte blocks, two cache planes,
SST_layer select) but layer B is a byte-copy of layer A. The real data exists:
`sonic_hack/collision/OJZ secondary 16x16 collision index.bin` (138 bytes, 122 differ
from primary) — but `tools/ojz_strip_gen.py` derives collision from a VDP-priority-bit
placeholder, not the index files, so wiring block-ID → secondary index → real path-B
bytes is level-pipeline work. Also needed then: path-swapper objects that write SST_layer.
**RAM note:** lower RAM slack is now 910 bytes ($FFFF7C72 → $FFFF8000). One more
BLOCK_STAGE_SLOTS (+768) fits; nothing ≥1KB does without evicting something.
**When to revisit:** when the level pipeline replaces the priority-bit collision
placeholder with real collision data, or when the first loop is authored.



### ~~Tile cache vertical slide is a memmove — circular row origin (§4.7)~~ — DONE 2026-06-10
**Completed:** `Cache_Origin_Row` circular index shipped same day the lag was
observed live (debug-fly turbo descent = up to 3 memmoves/frame ≈ 260k cycles).
VSlide/VSlideUp are now O(1); row-walking consumers use an end-of-buffer
sentinel (~16 cycles/row); single-row consumers remap the index. Origin kept
even so collision stays cell-aligned. Verified in Exodus: 252-row descent →
origin 12 (252 mod 60), 216-row ascent → origin 36 ((12−216) mod 60), terrain
renders clean through 4+ ring wraps in both directions.
Original entry:
**Surfaced during:** tile cache fill rewrite 2026-06-10.
**What:** Columns evict via circular origin (`Cache_Origin_Col`, free), but rows evict by
shifting the whole buffer: `TileCache_VSlide`/`VSlideUp` move ~9.4 KB nametable + ~2.3 KB
collision per 2-row evict ≈ **~47k cycles (a third of a frame) every 16 px of sustained
vertical scroll**. Fine in the light test state; will cause lag frames under real object
load. Fix: add a `Cache_Origin_Row` circular index. Touches every row-indexed consumer —
`Tile_Cache_GetTile`/`GetCollision`, `TileCache_CopyBlockColumn`, `Draw_TileColumn`
(column walks would split into two runs at the wrap, mirroring the existing NT 63/0
split), `Draw_TileRow_FromCache`, `Section_RedrawPlanes`.
**When to revisit:** once gameplay objects + parallax + DMA load share the frame and
vertical traversal shows lag, or §4 vertical work touches these routines anyway.

### FG H-deform vs streaming seam (left-edge draw lookahead)
**Surfaced during:** plane-A scroll lock fix 2026-06-10.
**What:** Plane A is now hard-locked to the camera, but configs that apply an
**H-deform wave to plane A** (e.g. SkyHaze's bottom-band FG haze on Sec2) still
displace FG lines by up to the wave amplitude. A leftward wobble pulls plane
columns left of the camera window into view — those sit at the plane-wrap seam
and may hold ahead-content, exposing up to wave-amplitude pixels of seam at the
screen edge. Mitigation: stream a few extra columns of edge lookahead in
`Section_UpdateColumns` (≥ max FG deform amplitude in tiles) so the seam sits
beyond any FG wobble.
**When to revisit:** before shipping any production config with FG H-deform, or
if Sec2's haze shows edge artifacts during testing.

### ~~§4.9 entity window is X-only — no vertical dimension~~ — DONE 2026-06-11 (vertical entity window)
**Surfaced during:** vertical-axis audit 2026-06-10 (EntityWindow_TeleportShiftY added
for teleport consistency, but the underlying system is 1D).
**What it was:** `EntityScanState` had `ess_origin_x` but no Y origin; ring/object
populate used ROM Y verbatim; only the slot-mapped (upper) sections of each vertical
pair were scanned; `EntityWindow_Scan` advanced on camera X only.
**Fix shipped:** exactly the proposed shape — 2×2 quadrant scan state (4 entries: slot
L/R × row r/r+1, derived from `Slot_Section_Map` by `EntityWindow_BuildEntries`),
per-entry `ess_origin_y` + `ess_entry_idx`, `Entity_Window_Active` validity mask with
SEC_VOID stamping for out-of-grid entries, S3K-style camera-Y spawn band
(ENTITY_LOAD_BUFFER_Y $100) with despawn hysteresis (ENTITY_DESPAWN_BUFFER_Y $180),
128px-coarse vertical re-scan (ENTITY_RESCAN_COARSE_MASK), per-entry loaded bitmasks
making all spawn paths idempotent, ring-buffer high-water + DEBUG-fatal drop diagnostics,
and build-time guards on the band invariants. Teleport mask migration proven a no-op
(disjoint 2-section block moves, table in entity_window.asm). **OEF_ANY_Y is now
honored:** ANY_Y objects spawn on X coverage regardless of camera Y and are exempt
from Y despawn, with the flag mirrored to `SST_slot_tag` bit 7 at spawn. Full 7-check
verification matrix passed in Exodus 2026-06-11. See ENGINE_ARCHITECTURE.md §4.9.3/§4.9.6.

### Plane A wrap-cycle visible during scroll (§4.2 streaming polish)
**Surfaced during:** §4.6 polish session 2026-04-28 (after bhi→bhs core fix + Section_Teleport_Guard increase shipped).

**Symptom:** When scrolling right through a single section, foreground (Plane A) terrain appears to "draw from left to right" — chunks of FG content materialize at screen LEFT and seem to fill toward screen RIGHT as the user scrolls. When scrolling left (back), the LEFT chunk disappears first while the RIGHT chunk persists. User confirmed via experiment: stub'ing `Section_UpdateColumns` to `rts` immediately makes all FG content disappear, proving the streaming engine *is* producing the visible artifacts.

**Root cause analysis:**
- Plane A is 64 cells = 512 px wide; screen is 320 px wide
- Section is 4096 px (`SECTION_SHIFT = $1000`); user scrolls through a section across 8 plane-widths
- `Section_UpdateColumns` writes each new section col to plane col `(global_col mod 64)`
- The streaming target is mathematically *correct* — it writes off-screen-right (1 col past visible right edge)
- BUT plane col 0 has a visibility cycle as Camera_X grows: visible at screen LEFT briefly when `Cam_mod_512 ∈ [0,7]`, off-screen for ~190 px, then reappears at screen RIGHT and drifts left
- During this cycle, each plane col gets *overwritten* every 512 px of camera travel with new section data — but the overwrite happens off-screen-right, so the new content enters from screen-right correctly
- **The "drawing from left" perception** is the plane-wrap natural behavior: every 512 px of scroll, the pattern repeats. Content at screen LEFT after each wrap is the LATEST streamed content — user sees it as "appearing on the left."

**Verified facts:**
- HScroll values are correct (uniform `-Camera_X` across all 28 cell rows for Sec0)
- Section_FillInitial fills cols 0..63 correctly at boot
- Section_UpdateColumns advances Right_Col_Written / Left_Col_Written correctly
- Streaming writes target plane col is always off-screen-right at the moment of write
- Plane wrap is mathematically inevitable when plane width (512px) < section width (4096px)

**Possible fixes (all §4.2 architecture work, not §4.6):**
1. **Camera teleport per plane-width**: instead of `SECTION_SHIFT = $1000`, teleport every 512 px so plane wraps land at teleport boundaries (= invisible). Requires reworking section coordinate system, object spawning, collision lookups.
2. **Wider effective plane via VRAM trickery**: not feasible — VDP is hard-limited to 64×64.
3. **Section_UpdateColumns rewrite**: stream content N plane-widths AHEAD so each plane col is written 64+ cols before reaching visibility. Requires more aggressive write-ahead and careful Plane_Buffer budgeting.
4. **Live with it**: accept that plane-wrap pattern is visible. Real Sonic games (S1/S2/S3K) use camera teleport to mask it; we currently don't.

**When to revisit:** Dedicated §4.2 polish session. Don't try to band-aid this in §4.6 territory — it's a section-streaming engine architecture issue. Recommend Option 1 (camera teleport per plane-width) as the proper fix; it matches the technique used in real Sega Genesis Sonic games.

**Additional finding:** `SECTION_SHIFT = $1000` ≠ `SECTION_SIZE = $0800`. Comment claims "uniform shift applied on teleport (pixels)" but the value is 2× SECTION_SIZE. With current values, post-FWD Camera_X = $200 (= cam_min_x = BWD_THRESHOLD), which is what causes the section oscillation that the 30-frame Section_Teleport_Guard patches. The "natural" fix would be `SECTION_SHIFT = SECTION_SIZE = $0800` (so FWD/BWD both land Cam mid-window at $0A00, no oscillation), but this requires recalibrating Right_Col_Written / Left_Col_Written math in Section_UpdateColumns and the Section_FillInitial init values. Worth investigating as part of §4.2 polish — may also resolve the plane-wrap perception issue if the ring rotation is "shorter" per teleport.

### Section Preload with S4LZ Deferrable DMA (§4.2)
**Blocked by:** S4LZ art streaming pipeline (§2.1) and section adjacency graph
**What:** When camera crosses Section_FWD/BWD_PRELOAD threshold, queue Deferrable-priority DMA to load next section's tile art into the VRAM pool. Currently Section_QueueNewSlot1/0Cols just writes nametable strips; the art must already be in VRAM.
**When ready:** After §2 art streaming and §4.2 section preload are designed.

### Section Preload — Velocity-Based Timing (§4.2)
**Blocked by:** Player physics providing ground_speed
**What:** Preload threshold adapts to player ground_speed — trigger earlier at high speed to ensure art arrives before new columns are visible. Currently fires at fixed SECTION_FWD/BWD_PRELOAD constants.
**When ready:** After §3 player physics provides ground_speed to the section system.

### Vertical Section Teleport (§4.2)
**Blocked by:** Vertical level design and camera Y handling
**What:** Section_TeleportUp / Section_TeleportDown paths (stub exists in Section_Check). Camera Y threshold mirrors the X system. Required for multi-row section grids.
**When ready:** After a level with vertical transitions is designed.

### Section Null-Neighbor Camera Clamp (§4.2)
**Blocked by:** Act descriptor null-section encoding
**What:** When camera approaches a section slot with no neighbour (edge of the level), Camera_X should clamp to the act boundary instead of teleporting. Currently Section_TeleportBwd has a note for zero-clamp but no null check.
**When ready:** After act descriptors encode level boundaries.

### Dynamic Tile Override Table (§4.3)
**Blocked by:** Gameplay objects that need runtime tile patching
**What:** Tile_Override_Table (16 entries × 6 bytes) is allocated in RAM. Needs a writer (object sets col/row/new_tile) and a drain routine (VInt_DrawLevel emits row updates). Used for breakable tiles, activated switches, destroyed terrain.
**When ready:** When a gameplay object needs to modify level geometry at runtime.

### ~~§4.6 lerp accumulator never converges to per-band targets~~ — RESOLVED 2026-06-11 (re-test)
**Resolution:** Root cause was the TestPlayer d7 clobber (fixed 2026-06-10) — garbage object dispatch
was stomping the accumulators between frames, which is why every single-stepped iteration computed
correctly while stored values were wrong. Re-test on current master: Camera_X=608 stable, active config
resolves to ParallaxConfig_OJZ_Caves (factors 1/16,1/16,1/8,1/4,1 — NOT the April-era Default config the
original expectations were computed from), and `Parallax_Current_Scroll_B` reads exactly
[-38,-38,-76,-152,-608] = 608×factors, pixel-perfect. Entries 5-7 stay 0. Mid-pan spot-check at
Camera_X=624 under the same config was also exact ([-39,-78,-156,-624]). Note for future debugging:
the April "expected" values were computed against the wrong config — always derive targets from
`Parallax_Current_Config`'s actual band table, not from the act's default.

Original investigation notes kept for reference:

**Surfaced during:** §4.6 polish session 2026-04-28 (after MCP debug session).

After ~thousands of frames with Camera_X stable at 608, Plane A
entries 0-4 of `Parallax_Current_Scroll_A` converge to -608 (the
FACTOR_1 target — correct). But Plane B entries don't converge to
their per-band targets:

  Expected (steady state with camX=608):
    B[0] cloud (FACTOR_1_8) → -76
    B[1] far_mtns (FACTOR_1_4) → -152
    B[2] mid_mtns (FACTOR_3_8) → -228
    B[3] hills (FACTOR_1_2) → -304
    B[4] ground (FACTOR_1) → -608

  Observed: -542, -551, -608, -608, -608

Entries 5-7 (which the 5-band loop shouldn't touch) read as -608 even
though `Parallax_Init`'s zero loop correctly sets them to 0.

Verified via single-step:
- `Decode_Factor_A` returns -608 for FACTOR_1 ✓
- `Decode_Factor_B` reads correct s1=3 for cloud band's first call ✓
- Band loop iterates 5 times, exits with d5=5 ✓
- `a2`/`a3` advance by 2 per iter, end at entry 5 ✓
- `Parallax_Current_Config = $000104C2` (OJZ_Default) stable ✓
- Camera_X stable at 608 ✓
- `Parallax_Init` runs once at boot, never again ✓

So the lerp's *individual iterations* compute correctly per-band, yet
the steady-state values are wrong. This suggests entries are getting
overwritten BETWEEN frames by something that doesn't appear in the
band loop or Parallax_Update flow. Watchpoints don't fire.

Live MCP debugging hit a wall — the inconsistency between "every
instruction does the right thing" and "the stored values are wrong"
needs **instrumented offline debugging**: dump
`Parallax_Current_Scroll_A/B` to a debug VRAM region every frame, then
inspect the trace to find when/which write produces the wrong value.

**When to revisit:** Dedicated session with code instrumentation. Don't
try live-stepping — too much state, too much MCP-level uncertainty.

---

### ~~§4.6 visual artifacts blocked on root-cause of state clobber~~ — RE-TESTED 2026-06-11, ALL THREE RESOLVED

**Re-test 2026-06-11 (current master, live Exodus):**
1. **3-line race on load / wrong lerp targets** — RESOLVED. Accumulators converge pixel-exact to the
   active config's per-band targets (see the lerp entry below for full numbers). The April "wrong
   targets" were measured against the wrong config (Default instead of the per-section Caves).
2. **FG H-deformed during section transitions** — RESOLVED. FG HScroll words verified uniform at
   -Camera_X across all 224 lines through: a FWD teleport into Sec2, a BWD teleport back, and two
   live config switches (Windy↔Caves). The only per-line FG variation found was SkyHaze's *intentional*
   bottom-band haze on Sec2 (`parallax_combine_split` demo) — by design, not the artifact.
3. **BG warps while stationary** — RESOLVED. Two screenshots ~20s apart with camera idle at
   Camera_X=608 are byte-identical PNGs.

All three derived from the TestPlayer d7 stomp (fixed 2026-06-10). No further §4.6 debugging needed.

**Surfaced during:** §4.6 T12 testing, expanded in T12 polish session 2026-04-27.

Three known visual artifacts in the OJZ scroll test that all derive from
the same upstream state-corruption issue tracked below:

1. **3-line race on load.** Top scanlines lerp from VSRAM=0 to their
   converged target over the first half-second. Snap-on-init
   (32-iter convergence loop in `Parallax_Init`) was added but didn't
   eliminate the visible race. MCP runtime read of
   `Parallax_Current_Scroll_B` after Init shows entries [0]=-542, [1]=-551,
   [2..7]=-608 instead of the expected per-band targets (-76, -152, -228,
   -304, -608). The lerp accumulators are converging toward a *different*
   target than the math would predict — points to either a register
   clobber inside `Parallax_Update` or stale state from a stalled iter.

2. **FG appears H-deformed during section transitions.** When entering
   Sec2 (or otherwise crossing a section boundary), Plane A tiles show
   sine-wave horizontal offsets, even though `pcfg_deform_table_fg=NULL`
   for every shipped config. Possibly a section-streaming race where
   Plane A nametable updates land mid-deform-frame, or a residual
   per-line FG entry left in `Hscroll_Buffer` from a previous config.

3. **BG warps on its own when stationary.** With camera stopped, the
   BG plane keeps animating despite `Parallax_Deform_Phase_FG/BG`
   *never being incremented* by any code path (verified via grep of
   `s4.lst`). The animation source is unidentified — possibly the
   per-line H-deform sample reading garbage past the buffer when
   per-cell DMA mode is active but per-line fill ran.

**Current state:** Workarounds in place make the system not crash and
mostly render correctly. Multi-band horizontal parallax works, sine
deform on clouds is visible, per-section configs resolve. The artifacts
above are polish issues that compound on top of the upstream clobber
documented below; trying to patch them individually keeps producing
new failure modes.

**When to revisit:** When the upstream `Parallax_Current_Config` /
`Camera_Y` clobber (below) is root-caused and fixed, re-test all three
artifacts. If they persist, debug separately with the upstream noise gone.

---

### Parallax effects library — expansion backlog (§4.6)
**Surfaced during:** §4.6 polish session 2026-04-28.
**Where:** `data/parallax/effects/` — each effect is a self-contained file (deform table + parameterised macro + named variants). Two entries shipped so far: `heat_shimmer.asm`, `wave_rocking.asm`.

**Pattern to follow when adding effects:**
1. One file per effect under `data/parallax/effects/`.
2. Header comment: visual description, mechanism, tuning knobs, dependencies.
3. Shared deform table (one in ROM) + a `<effect>_config` macro that takes camelCase params (AS limitation — no underscores in macro args).
4. A few pre-named variants (`_Slow`, default, `_Fast`) for casual use.
5. Add an `include` line to `main.asm` after `ojz_default.asm` (some effects depend on `DeformTable_Zero`).

**Effects to add (ranked by ease/impact):**
- **screen_shake.asm** — short-duration triangle table at high speed. Per-column V or per-line H. Triggered by gameplay events; needs a "fade out over N frames" wrapper. Earthquake / explosion impact.
- **water_surface.asm** — combined per-line H sine + per-column V sine (90° offset). Hydrocity-style ambient water surface. Complex — verify VBlank budget.
- **mirage.asm** — extreme low-amplitude (1 px) high-frequency H-deform on a single mid band. Distant heat haze without affecting near terrain.
- **vortex.asm** — sawtooth H-deform + sawtooth V-column with reversing phase. Boss room / portal swirl.
- **earthquake.asm** — random/noise table V-column at high speed for ~30 frames, then quiesces. Procedural noise table generator helps here (a `deform_table_noise` macro, peer of sine/triangle).
- **banking.asm** — linear V-column ramp whose slope tracks Camera_X velocity. "Tilts into turns." Needs runtime parameter feed (Camera_X velocity → vDeformShiftBg adjustment).
- **falling.asm** — accelerating linear V-column ramp during fall sequences. Pairs with vertical scroll mechanics (§4.2 deferred).

**Deeper effects (need new mechanisms):**
- **raster_perspective.asm** — true 3D pseudo-perspective floor via per-LINE H-scroll programmed by HBlank IRQ. Sonic 2 special stage / S3K bonus stage feel. Different feature, not just a new table — needs HInt handler + per-line H-scroll arithmetic. Tracks as §4.7 task.
- **palette_cycle_band.asm** — recolour a band as the deform phase advances. Combines with existing effects. Needs palette-cycling pipeline.

**When to revisit:** When level design surfaces a specific need ("this zone wants underwater wobble", "the boss room needs a vortex"). Build effects on demand rather than speculatively.

### OJZ scroll-test sky-tint section marker (T15 diagnostic — remove later)
**Surfaced during:** §4.6 T15 testing 2026-04-28.

The `OJZScroll_Update` per-frame logic writes a section-id-keyed color into `Palette_Buffer[0]` (CRAM[0] = backdrop) so the sky tints differently per section: Sec0 black, Sec1 red, Sec2 green, Sec3 blue, Sec4 yellow, Sec5 magenta, Sec6 cyan, Sec7 gray, Sec8 white. The color table is `OJZ_SectionMarkerColors` at the bottom of `test/ojz_scroll_test.asm`. Useful for diagnosing slot rotation and section streaming visually.

**Why deferred:** this is a debug/development aid, not a shipping feature. Remove or gate behind a debug flag once OJZ has real visual content per section (e.g., distinct palettes, tile art, props) that makes the section identity obvious without a marker.

**When to revisit:** once §3 player physics is in and we're playtesting actual gameplay, the diagnostic tint will be confusing. Strip the marker code (~25 lines + the table) and let the per-section palette do the storytelling.

### ~~Section rotation should be block-style, not rolling~~ — DONE 2026-04-28
**Completed in:** §4.6 T15 commit. `Section_TeleportFwd`/`Bwd` now advance both slots by 2 sections per teleport (block-style), matching `SECTION_SHIFT = $1000` and the user's "infinite forward walking" intent. Architecture doc §4.1 still describes the older rolling-leapfrog model and needs updating in T17.

### Section rotation cascading work (§4.2 architectural fix)
**Surfaced during:** §4.6 T15 testing 2026-04-28.

**State:** The rotation logic itself is now block-style (shipped 2026-04-28). The cascade work below remains.

1. **`Section_UpdateColumns` ring-buffer math.** Currently assumes the rolling model — RC/LC trackers reset to fresh-streaming state and assume slot 1 = next section, slot 0 = continuation. With block-style, both slots are new at teleport, both need cold-fill streaming. Requires `FG_RedrawForSection` sibling to `BG_RedrawForSection` (already a separate deferred entry) so the visible content doesn't streak in over multiple frames after teleport.

2. **Preload bandwidth double-up.** Currently preload only loads slot 1's next section. Block-style needs both slot 0's *and* slot 1's next sections pre-fetched (= up to 2 sections of art queued during the slot 1 traversal). Doubles preload DMA bandwidth requirement; may need bigger preload window or velocity-based timing tightening to avoid mid-teleport stalls.

3. **Landing flag (separately deferred).** With block, post-teleport camera lands at `$200` (start of new slot 0), and walking left immediately fires BWD threshold. The `$0FFF` SHIFT nudge fixes that; the proper fix is sonic_hack's landing flag.

**When to revisit:** §4.2 polish session. Pair with FG_RedrawForSection and landing flag — they're all the same teleport pipeline.

**When to revisit:** §4.2 polish session. Pair with the FG-redraw work and the landing-flag mechanism; they're all the same teleport pipeline. Recommend reading `sonic_hack/code/engines/section_streaming.asm:Section_ForwardTeleport` end-to-end as the reference implementation.

### Plane A "fill-in" after teleport (§4.2 streaming polish)
**Surfaced during:** §4.6 T14 testing 2026-04-28.

**Symptom:** Crossing a section teleport boundary (`$1200` FWD or `$200` BWD), Plane A foreground content visibly "runs in" over ~2-3 frames as `Section_UpdateColumns` re-streams the visible 40 columns into the plane. User wants the teleport to be imperceptible — same content visible before and after.

**Why it happens:**
- After `Section_TeleportFwd`/`Bwd`, slot rotation relabels plane cols (slot 0 ↔ slot 1) but does not move data — plane content still has the OLD slot mapping's tiles.
- `Section_Right_Col_Written` / `Left_Col_Written` reset to fresh-streaming state. `Section_UpdateColumns` then gradually re-fills columns from the new slot map.
- `PLANE_BUFFER_SIZE = 1536` bytes only holds ~15 columns of strip data per frame; the visible 40-column window takes 2-3 frames to fully refresh.

**`BG_RedrawForSection` already handles plane B at teleport** (full-section rewrite via dedicated batch path, drains in 1-2 VBlanks). Plane A doesn't have an equivalent — it relies on the per-frame streaming machinery.

**Fix paths (ranked by complexity):**
1. **`FG_RedrawForSection` sibling.** Mirror BG's batch redraw, queueing 64 plane cols of new slot 0 + slot 1 content into `Plane_Buffer` at teleport. Requires `PLANE_BUFFER_SIZE` increase to ~6400 bytes (= ~5KB extra RAM) so the burst fits in one frame. Drains in 1-2 VBlanks via existing `VInt_DrawLevel`. Cleanest but eats RAM budget.
2. **VRAM DMA from staged source.** Pre-build a 4096-byte plane-half template during preload phase, then DMA-fill into VRAM at teleport. Faster than direct writes, doesn't need bigger Plane_Buffer. New infrastructure required.
3. **Brief display-off during teleport.** Disable display, blast plane via direct VDP writes (huge VRAM bandwidth available with display off), re-enable. 1-2 frames of black. Simplest but ugly.
4. **Live with the streaming fill-in.** Current state. ~33-50ms of "running in" content. Tolerable for early demos; not shippable.

**When to revisit:** §4.2 polish session. Path 1 is the most aligned with the current architecture; path 2 is where to head once we're tightening the engine. Reference `BG_RedrawForSection` as the model — Plane A version follows the same structure but writes 32 nametable cols × ~30 rows per slot.

### Section teleport landing-flag mechanism (player-physics polish)
**Surfaced during:** §4.6 T14 testing 2026-04-28.

**Current state:** `SECTION_SHIFT = $0FFF` (= FWD - BWD - 1) so post-teleport camera lands 1 px inside the safe zone, preventing idle oscillation between `$200` and `$1200`. Works for the OJZ camera-driven scroll test where camera is bounded directly by `cam_min_x` and user input is at fixed pixel-step.

**Why it's a stopgap:** when player physics arrive, the camera will follow a player position that can be flung past thresholds by springs, knockback, terminal-velocity falls, or other physics impulses. A 1-pixel margin is too narrow for momentum-based crossings — the player may overshoot and re-trigger the opposite teleport before they can move into a safe zone.

**The proper fix (sonic_hack pattern):** state-based suppression rather than geometric margin.
- Add a `Section_Teleport_Landing_Flag` byte to RAM (or reuse a bit in `Section_Preload_Flags`).
- On FWD teleport: set the landing flag.
- On BWD teleport: set the landing flag.
- In `Section_Check`: if the landing flag is set, suppress whichever teleport check is opposite to the most-recent direction. (Or: always suppress until the flag clears, which is symmetric.)
- Clear the flag when camera enters the central safe zone (e.g., `$0400 < camX < $09FF`). User must move into the safe zone before any further teleport can fire.

**Reference implementation:** `sonic_hack/code/engines/section_streaming.asm:Section_Check` lines 1100-1150. They use `ss_flags` bit 4 + `ss_landing_timer` for the same purpose; their thresholds are also asymmetric (FWD inclusive at `$1200`, BWD strict-less-than at `$200`) which complements the flag.

**When to revisit:** when integrating player physics (§3 spec). Restore `SECTION_SHIFT = $1000` at the same time so post-teleport camera lands exactly at the boundary, and the landing flag handles the rest. Until then, the `$0FFF` nudge is a clean equivalent for the camera-driven test setup.

### VDP register $0B (mode_set_3) propagation bug — workaround in place (§4.6)
**Surfaced during:** §4.6 polish session 2026-04-28.

**Symptom:** When `pcfg_deform_table_fg` and `pcfg_deform_table_bg` are both NULL (e.g. ParallaxConfig_OJZ_Default), the parallax pipeline auto-selects per-cell HScroll mode: `Parallax_Fill_PerCell` writes 28 longwords, the per-cell static DMA enqueues 112 bytes, `setVDPReg vdp_mode3 = $02` marks shadow dirty, and Flush_VDP_Shadow writes $8B02 to VDP_CTRL on every VBlank. Visually we expected per-cell HScroll: all 28 cell rows scroll uniformly with the same `-Camera_X`. We observed instead per-line behavior: only scanlines 0-27 (the top 28 px = 3.5 cell rows) scrolled correctly, lines 28-223 stayed pinned to plane col 0.

**Empirical proof of per-line state:** Patching VRAM HSCROLL_TABLE entries 28-223 directly with proper PA values via `mcp__exodus__emulator_write_vram` made the entire screen scroll correctly. This is only possible if VDP register $0B has bits 1:0 = %11 (per-line). VDP shadow byte at offset 11 reads $02 and dirty bit 11 stays set, but the visual proves register $0B is $03.

**What we tried (all failed):**
- `setVDPReg vdp_mode3, #$02` every frame in OJZScroll_Update (shadow + dirty path).
- Direct `move.w #$8B02, (VDP_CTRL).l` with stopZ80 wrap.
- Adding a state-machine reset (`move.w (VDP_CTRL).l, d1`) before the direct write to clear any half-finished 32-bit address command.
- None changed the register's per-line behavior.

**Workaround in place (2026-04-28):**
- `data/parallax/ojz_default.asm` defines `DeformTable_Zero` (256 zero bytes) and adds `deformBg=DeformTable_Zero` to both `ParallaxConfig_OJZ_Default` and `ParallaxConfig_OJZ_Floor`. This forces the entire pipeline (Parallax_Update auto-select, Enqueue_Dirty_Buffers DMA selector, OJZScroll_Update mode_set_3 force) into per-line mode for these no-/V-only-deform configs.
- Cost: ~1500-2000 extra cycles per frame (224-line fill vs 28), 8× HScroll DMA bandwidth (896 vs 112 bytes), 256 bytes ROM for the zero table. With sample = 0 the deform sampling adds 0 to each line — no visual change.
- ParallaxConfig_OJZ_Windy was unaffected (it has a real BG H-deform table and was already per-line).

**When to revisit:** When the per-cell mode is needed for performance budget. Investigation should focus on:
1. Possible interrupt-time VDP_CTRL write that lands between Flush_VDP_Shadow and the next render.
2. Possible Z80 bus interaction during the shadow flush — the Z80 isn't stopped during Flush_VDP_Shadow's individual `move.w` writes.
3. Re-examine whether Boot's initial VDP register write loop properly writes $0B = $00 then OJZScroll_Init's setVDPReg path correctly upgrades it to $02 on first VBlank.
4. Try writing $8B02 to VDP_CTRL in a known-clean place (e.g. immediately after `Flush_VDP_Shadow` returns, with explicit Z80 stop) and observe if behavior changes.

**Bare-minimum reproduction:** Remove `deformBg=DeformTable_Zero` from `ParallaxConfig_OJZ_Default`, build, load OJZ scroll test, scroll right. FG bricks scroll correctly only on top 28 scanlines; rest of the screen shows plane A column 0 stuck.

### ~~Parallax_Current_Config / Camera_Y intermittent clobber (§4.6)~~ — ROOT-CAUSED + FIXED 2026-06-10
**Root cause:** `TestPlayer_Main` read `Ctrl_1_Press` into **d7 — the RunObjects
loop counter** (object routines must preserve a0/d7). Every press edge extended
the player slot loop by the press bitmask value: the dispatcher marched up to
255 slots past `Player_1`, re-running live objects, then executing free-stack
words and arbitrary RAM as `code_addr` offsets into `ObjCodeBase`. Real object
routines invoked on garbage "slots" wrote SST fields through a0 at arbitrary
RAM (the zeroing symptom); level data executing as code produced stray writes
like `$FF71FF71` (the garbage symptom) or ILLEGAL INSTRUCTION (live crash
captured in Exodus 2026-06-10: a0=$FFFF9E14 = Dynamic_Free_Stack, d7=1,
caller RunObjects.always_next, jump target OJZ_SEC2_BLOCKS+$1640).
**Fix:** press bits moved to d4 (`objects/test_player.asm`); debug builds now
assert the a0/d7 loop contract after every dispatch (`Debug_AssertObjLoop`,
`engine/objects/core.asm`). Pointer-validation band-aids removed from
`Enqueue_Dirty_Buffers`, `Parallax_Update`, `Vscroll_Write`, and the OJZ test
mode-set-3 force. Re-test of the three §4.6 visual artifacts done 2026-06-11 —
all three resolved (see the artifacts entry above).

Original investigation notes kept for reference:
**Surfaced during:** §4.6 T12 testing (2026-04-27).
**Symptom:** During §4.6 T12 v2 debugging, multiple MCP reads showed
`Parallax_Current_Config = $00000000` and `Camera_Y = 0` even though
`Parallax_Init` and `Camera_Init` had set them correctly at boot. The
zeroing wasn't caught by Exodus MCP watchpoints, didn't fire the
breakpoint at the only `move.l #0, (Camera_Y).w` instruction
(`object_test_state.asm:34`, never on the OJZ scroll test path), and
no code path in the OJZ scroll test Update flow writes either field.
The corruption is intermittent — repeated single-step sessions sometimes
showed the values intact and Vscroll_Factor lerping correctly.
**Practical workaround in place:** OJZ parallax configs use
`vCenter=0, vOffset=0` so even when `Parallax_Current_Vscroll_BG` ends
up at a wrong negative steady-state value (we observed -59 instead of
the expected 62), the BG plane stays anchored at the top where the
nametable is fully populated. With OJZ being X-only-scroll in §4
Phase 1, this is functionally invisible.
**When to revisit:** When adding vertical camera scroll (§4 Phase 2+),
the parallax math depends on Camera_Y being accurate frame-to-frame.
Suspect candidates to investigate: (a) interrupt-time write through a
stale or corrupt pointer, (b) movem-out-of-bounds on the supervisor
stack at $FFFFFEF8 (lots of save/restore traffic in band loop +
VBlank handler), (c) Exodus MCP watchpoint not actually catching
writes in this build.
**Bare-minimum reproduction:** Build current `master`, load in Exodus,
let it run a few seconds at the OJZ scroll test, MCP-read
`Parallax_Current_Config` and `Camera_Y` repeatedly. Both should be
non-zero; intermittently they read zero.

### ~~OJZ Tile Art Loading — Full Terrain Visibility~~ — DONE 2026-04-26
**Completed in:** §2 Phase 2 Layer A.1 (tile dedupe + nametable remap)
**What:** ojz_strip_gen.py now globally dedupes tile data with hflip/vflip canonicalization across all 16 sections and rewrites strip files to reference the new compact index space. The deduped pool (10 tiles for OJZ act 1's current visible 48-row strip band) loads via Level_LoadArt → S4LZ_Decompress → DMA. Strip tile-index ceiling collapsed from 1856 → 9; nametable at VRAM $C000 is no longer at risk of being clobbered.
**Caveat:** Visible band still capped at strip rows 0-47 (sprite attribute table at VRAM $D800 = nametable row 48). Showing the *full* layout (chunk rows 2-12 of the 16-row OJZ layouts, the actual ground terrain) requires vertical-axis section transitions (still §4 deferred) or relocating the sprite table out of the Plane A nametable region (not currently planned). The pipeline is correct end-to-end; only the camera/strip envelope limits how much of OJZ becomes visible at once.
**Measurements:** see `docs/research/tile-pipeline-measurements.md`.

---

### ~~Chunk/block parsing produces mostly-empty tiles~~ — DONE 2026-04-26
**Completed in:** kos_decompress rewrite
**What:** Root cause was the homegrown Kosinski decoder in `tools/ojz_strip_gen.py` — subtle bit-order / displacement bugs that produced ~5× too much output and ~50% of blocks parsing as all-zero. Hypothesis 1 (multi-stream Kosinski) was wrong; hypothesis 2 (block-ID mask) was wrong. Real bug was the decoder itself. Fixed by porting `sonic_hack/code/engines/kosinski.asm` KosDec literally to Python: LUT bit-reversal of each descriptor byte + `add.b`-style MSB-first reads, exact stream-copy semantics matching the asm.
**Post-fix verification:** chunk 0x3f now references blocks 272-302 (all 4/4 non-zero, real ground data). Block count: 374 (was 2002 garbage). Tile art: 919 tiles (was 322 truncated). 141 unique source tile indices in OJZ act 1 sec0 strips (was 14). With this fix + a related palette-line-1 offset fix in the test state (sonic_hack's `palptr Pal_OJZ, 1` means OJZ palette occupies CRAM lines 1-3, not 0-2), the OJZ scroll test now renders actual OJZ art with correct green palette. Verified via Exodus Plane A viewer.
**Bonus learning:** Investigation revealed I had been over-confidently calling sparse-pixel screenshots "clean rendering" through A.1-A.3 verification. Honest visual ground truth (level editor screenshots from the user) was what surfaced the bug. Process lesson saved as a memory.

## From §4.6 — Parallax (post-T17 backlog)

### Per-block linear interpolation deformation format
**Blocked by:** N/A — deliberately not in v1.
**What:** S.C.E.'s block-based deformation table format with high-bit linear-interp flag. Variable-height blocks save ROM (~32 bytes vs ~256 bytes per table). v1 uses full 256-byte time-varying tables — block format is a ROM-saving optimization we don't currently need.
**When ready:** if a section's deformation table waste becomes a real ROM problem (currently affordable — 256 B per shape, shared across sections that use the same shape).

### Per-band deformation table pointers
**Blocked by:** visual demand for different wave shapes per band.
**What:** Each band points at its own 256-byte deform table. Currently single shared table per section (`pcfg_deform_table_fg` / `_bg`) + per-band amplitude/phase via `BAND_DSA/B` and `BAND_PHASE`. Adds 4 bytes per band (table pointer field) + multiple tables per section.
**When ready:** when a section visually requires different shapes per band — e.g., square wave for one band, sine for another.

### Per-band frequency variation
**Blocked by:** visual demand.
**What:** Per-band `phase_increment` byte. Currently only phase OFFSET varies per band (frequency is section-wide via `pcfg_deform_speed_fg/bg`).
**When ready:** when "different speeds per band" surfaces as a clear visual need.

### Plane A per-column V-scroll
**Blocked by:** use case (ground-plane warping is rare in Sonic-style platformers).
**What:** `pcfg_v_deform_table_fg` field is reserved but not wired in v1. Currently the FG plane always uses whole-plane V-scroll; `Vscroll_Write`'s per-column branch only writes the BG word per column-pair from `Parallax_Vscroll_Column_Buf`. Implementation is symmetric to the BG path — ~30 cycles + 80 bytes RAM for an FG column buffer + the fill code in `Parallax_Update`.
**When ready:** when a section needs ground-plane vertical warping (special-stage 3D floors, post-explosion ground sink, banking-platform foreground variants).

### Sprite mask for per-column V-scroll leftmost-partial-column garbage
**Blocked by:** sprite system + zone level data hooks.
**What:** Genesis VDP per-column V-scroll grain is 16 px. With non-zero plane B HScroll, the leftmost screen sliver renders at V-scroll = 0 regardless of VSRAM[0] — silicon-level, no register fix. v1 mitigates either by: locking plane B HScroll to 0 (`FACTOR_0`) which eliminates the partial column, or accepting the artifact. Real games drop a 16-px-wide sprite mask over the left edge to hide it (Sonic 3 Hydrocity boss arena, Streets of Rage banking, etc.).
**When ready:** when a section uses per-column V-scroll *and* wants non-zero plane B HScroll. ~1 sprite/frame overhead from the 80-sprite budget.

## From §4.9 — Section-Local Entity Management

### ~~§4.9.4 Rolling 4-Slot State Tracking (Respawn Memory)~~ — SHIPPED 2026-06-12
**Resolution:** `Ring_Collected_Park` (4 × 33 B rolling park, 134 B total) parks a section's
collected/killed bitmasks when `Collected_UpdateCenter` evicts it from the 3×3 window
(pristine sections skipped) and restores them in `Collected_ClaimSlot` on re-entry.
3×3 window + 4 park = 13 remembered sections — covers OJZ's whole act (zero resurrection);
larger acts degrade classically at long range. Spec: `docs/superpowers/specs/2026-06-12-respawn-memory-design.md`,
commit 235e200. Follow-ups from review (minor): (1) restore-leg verification read only the
collected mask — re-verify the killed mask round-trip plus a live no-respawn census when a
killable object path exists; (2) freed park entries aren't preferentially reused — rolling
overwrite can evict a live entry while a freed slot idles (effective capacity dips under
mixed traffic; spec-compliant, revisit if park pressure appears); (3) natural-eviction
retest needs an act larger than 3×3 — re-run when one exists.

### ~~§4.9.5 Warp-Based Teleport Preview (Entities in Preview Zone)~~ — SHIPPED 2026-06-12
**Resolution:** Visibility-derived window makes preview intrinsic. The despawn envelope overlaps sections ahead of the camera before any teleport fires — those sections are tracked, their entities are in the buffer. No warp coordinates, no coordinate shift, no integration work. Closed by the visibility-window plan (branch `vertical-entity-window`); see ENGINE_ARCHITECTURE.md §4.9.3.

### Bouncing "Loss Rings" (Ring Scatter on Damage)
**Blocked by:** §4.9 ring system + player damage system
**Surfaced during:** §4.9 design session 2026-04-29.
**What:** When the player takes damage, scatter N rings as temporary SST objects (not buffer entries). Each has physics (gravity, bounce), a lifetime timer, and can be re-collected. Uses AllocEffect slots (lightweight). These are separate from level-placed buffer rings — buffer rings are static positions with bitmask state, loss rings are short-lived physics objects.
**When ready:** After player damage/hurt system exists (§3 player physics) and ring collection works.

### Ring Attraction (Magnet Shield)
**Blocked by:** §4.9 ring system + shield system
**Surfaced during:** §4.9 design session 2026-04-29.
**What:** When player has magnet shield, uncollected rings within attraction radius accelerate toward the player. Modifies the per-frame ring collision check to also compute distance and apply pull velocity. Only affects buffer rings within range — loss rings (SST objects) would have their own attraction in their object code.
**When ready:** After shield system exists (§3 player abilities).

## From Teleport-Rebase (2026-06-10)

### ~~CRITICAL: FWD teleport advances slot pair out of a narrow grid~~ — DONE 2026-06-11
**Surfaced during:** teleport-rebase verification 2026-06-10 (pre-existing). **Fixed in:** grid-edge branch.
**What it was:** `Section_TeleportFwd` advanced the pair `(0,1) → (2,3)` but OJZ act1 is a 3×3 grid — sec_x=3 doesn't exist; the entity window built scan state from a garbage Sec pointer → DEBUG assert in `Collected_CheckRing` (release: undefined ring spawns) on walking right past `x=$1200`.
**Fix shipped:** `SEC_VOID` ($FF) sentinel in slot-1 sec_x past the grid; guards in `Section_Check .fwd_check` (sentinel check before the wrapping addq), TeleportFwd's SS_RESIDENT mark, EntityWindow Init/Rebuild slot-1 blocks (skipped; `Entity_Window_Active`=1; the stale entry's section_id stamped SEC_VOID for the despawn exemption), camera max-x void clamp ($8C0 = slot-0 right edge), `TileCache_DecompressBlock` world-edge guard (out-of-grid blocks decompress blank — also fixed the latent bottom-edge Sec-table overread that vertical fills have had since shipping), prefetch sec_x guard. BWD heals the pair (new slot 1 = old slot 0 − 1). Exodus-verified end to end (warp right → pair (2,$FF), objects spawn, camera pins $8C0, BWD returns (0,1)).
**Still open (minor, from review):** `Section_Check` clobber header understates; classic-style player X clamp at camera bounds (player can currently walk past the camera into the void region — level data should wall it, but a bounds clamp matching the classics is worth considering with §3 player physics).

### ~~Per-section BG layout swap at the seam (T2/T3 zones)~~ — SUPERSEDED 2026-06-12
Superseded by the full BG seam-streaming spec ("From Deep Forest BG Work
(2026-06-12)" below). The original observation stands: teleports no longer
run `Section_RedrawPlanes`, all production data is T1, and any per-section
BG needs a non-blocking streaming mechanism, not a synchronous blit.

## From Deep Forest BG Work (2026-06-12)

### SPEC: Per-section background grid with seam streaming
**Goal:** each section (or section row/column) gets its own background from
the editor's per-section BG assignment, and the engine stitches them into
one continuous world as the player travels — no visible swap, both axes.
User intent: "section below the forest has the darker firefly one, and the
tree one above connects to it."

**Why it works (the headroom argument):** Plane B is 64×64 cells (512×512px)
but the screen shows only 320×224. At the BG's parallax factors the hidden
margin is enormous in camera terms: vertically, 288 hidden px at camY/8 =
2304 camera px (more than one 2048px section row) before an off-screen row
wraps back into view; horizontally, 192 hidden px at camX/8 = 1536 camera px.
Rows/columns that scroll off one edge are rewritten with the NEXT section's
BG via QueueDMA_Deferrable long before they re-enter from the other edge —
the same trick as FG column streaming, applied to Plane B on both axes.
Bandwidth is trivial: one plane row or column = 128 bytes; a few per frame.

**Components:**
1. **BG grid data.** Zone data gains a BG-grid table: section (or section
   row/col band) → {nametable region ptr, tile blob ptr, anim band table
   ptr, palette line variant}. Editor already has per-section BG assignment
   (UI exists, engine unwired); injector emits the grid instead of the
   single zone-wide override.
2. **Seam tracker + row/col streamer.** Engine-side state: which BG region
   each plane row/column currently holds, and a per-frame budgeted streamer
   that rewrites rows/cols in the hidden margin toward the target (derived
   from camera section position + scroll direction). Mirrors the FG
   preview-column scheduler. Teleport rebases are coordinate-invariant on
   the plane (mod 512), same as FG — the streamer keys on world-derived BG
   scroll, not raw camY.
3. **Tile budget across the seam.** Both themes' tiles coexist in VRAM while
   a seam is in transit. Strategy: split the 448-tile BG pool into two
   half-pools (~224 each, minus shared animated slots); the streamer loads
   the incoming theme's blob into the inactive half (deferrable DMA, chunked)
   before its nametable rows reference it. Editor enforces per-theme budget
   (set_bg validator) and a shared-atlas option for themes that intentionally
   share tiles (forest ↔ darker forest).
4. **Animated bands per theme.** BgAnim_Table is per-act today; becomes
   per-theme, swapped when the seam fully clears the screen (bands reference
   fixed VRAM slot ranges, so the safe-swap moment = no on-screen rows from
   the outgoing theme). The table-driven design (driver/rate/dest per band)
   already supports this — needs a "active table ptr" indirection + handoff.
5. **Seam contract in the editor.** Two modes per adjacent BG pair:
   - **connects-to:** the arts' meeting edges are authored to blend (e.g.
     forest bottom rows = firefly zone top rows). Editor feature: edge
     preview of A-bottom against B-top (and A-right against B-left), plus
     a palette-compatibility check.
   - **disconnected:** transition must be masked. Two sanctioned tricks:
     (a) FG occlusion — level geometry covers the full screen height while
     the seam crosses (cave mouth, tunnel, waterfall; classic S3K), with an
     instant region swap while occluded; (b) palette blackout — fade the BG
     CRAM line to black over ~16 frames, swap/stream while black, fade up
     (thematically free for caves; needs the per-section palette mechanism).
6. **Per-section palette variants** (cheap multiplier, can ship first):
   same art, darker/tinted CRAM line per section row, lerped at the seam.
   The harness's per-section sky-tint table is the prototype.

**Constraints / open questions:**
- Vertical wrap vs themes: the current 512px art wraps seamlessly (camY/8 ×
  $1000 rebase = exactly one plane height). With per-row themes, the wrap
  must land on the THEME boundary — keep vFactorBg=3 and make each theme's
  vertical slice 512px (one full plane per section row) or 256px (two rows
  per plane); pick during design.
- Diagonal travel: two seams (X and Y) can be in transit at once; streamer
  must handle a 2D dirty region, or sequence one axis at a time with the
  hidden margin as slack.
- Parallax config per theme: band factors may differ per BG (the Sec3
  LockedClouds incident shows per-section configs + plane-space bands must
  agree); fold parallax config into the theme record so it swaps with the
  art under the same safe-swap rule.
- Budget the streamer against the existing deferrable consumers (BgAnim
  banks, DPLC, section streaming) — the queue is shared.

**Suggested build order:** (a) per-section palette variants (standalone
win), (b) vertical-axis streaming with connects-to seams only (forest →
firefly section: the motivating case), (c) horizontal axis + disconnected
transitions (palette blackout first, FG occlusion as level-design tooling),
(d) per-theme anim-table + parallax-config handoff, (e) editor seam
contracts + budget validation.
**When ready:** next major BG work block; (a) any time.

## From Vertical Entity Window — Task 6 (2026-06-11)

### ~~Teleport keep-range tests pre-shift coords against the post-rebase camera~~ — DISSOLVED 2026-06-12
**Resolution:** The keep-window no longer exists. The visibility-derived window retains all entities across a teleport (shift, no despawn); there is no keep-range test to get wrong. This defect was only relevant under the old TeleportShift keep-window/despawn design, which was deleted in the visibility-window plan.

### ~~No survivor continuity across teleports (per-entry loaded masks can't cover off-window sections)~~ — DISSOLVED 2026-06-12
**Resolution:** The keep-window no longer exists. The visibility-derived anchor is invariant across rebases — the same sections are tracked before and after — so there are no "just-left-the-window survivors" to worry about. The duplicate-spawn risk that blocked the keep-range fix is also gone: teleports never populate, so no re-add can occur. Closed by the same design deletion.

## From Vertical Entity Window — Task 8 closeout (2026-06-11)

### X-BWD clamp-to-zero degenerate slot pair
**Surfaced during:** Task 8 teleport-table review 2026-06-11.
**What:** From an odd start `sec_x`, `Section_TeleportBwd`'s clamp-to-zero (section.asm
~:481) can produce BOTH slots tracking section 0 — a two-entries-same-section window
state that nothing else can create. The teleport disjointness/no-op argument is
unaffected (the moved block is still disjoint from the old one), but the duplicate-entry
state itself is untested: two scan states + two loaded-mask slots for one section.
**When to revisit:** if any act ever starts at an odd `sec_x`. All current acts start
at `sec_x = 0`.

### SEC_VOID vs flat-id 255 alias
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** `SEC_VOID = $FF` lives in the same byte namespace as flat section ids, and on
a 16×16 grid the real bottom-right section has flat id 255 = $FF — a void-sentinel
alias. Separately, `EntityWindow_BuildEntries`' void path stamps the sentinel but does
NOT clear the entry's loaded-mask slot (safe today only because `InitSection`'s
compare-clear wipes it whenever a real section later claims the entry).
**When to revisit:** if act grids ever approach 16×16 (current max is 3×3), or if any
new consumer reads `Entity_Loaded_Masks` for void entries.

### RescanY burst is unbudgeted
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** A 128px coarse-row crossing re-walks all 4 entries' ROM lists from index 0 up
to each X ratchet in a single frame. Trivial on test fixtures (≤16 entities), but on
dense production levels (40-50 rings/section × 4 entries, ratchet fully advanced) the
burst could reach tens of K cycles in one frame — same shape as the tile-cache fill
bursts that needed N-way staging + a frame budget (2026-06-10).
**When to revisit:** when real level data lands — watch `Lag_Frame_Count` during fast
vertical traversal (the profiler misses single-frame bursts). Tile-cache N-way staging
is the precedent if budgeting is needed.

### Entity despawner micro-opts
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** `DespawnRings`/`DespawnObjects` recompute the loop-invariant Y band bounds
per entity (~3.5k cycles/frame at a full 128-ring buffer — hoist to registers before
the loop). `RescanY`'s defensive d7 save around the scan calls can likely be trimmed
once the RunObjects d7 contract is re-audited. Also: `ess_ring_left_idx`/
`ess_obj_left_idx` are dead struct fields (cleared at init, never read — the X scan
is a right-edge ratchet; no left scan exists). Removing them shrinks EntityScanState
$1A → $16 and stops tempting docs into describing phantom left scanners.
**When to revisit:** alongside any other §4.9 perf work (e.g. the RescanY budget entry
above) — not worth a dedicated session.

## From Visibility-Window Plan (2026-06-12)

### Slide populate is X-unfiltered
**Surfaced during:** visibility-window plan implementation 2026-06-12.
**What:** `EntityWindow_PopulateSectionRings` (and the object equivalent) offers every entry in the section's ROM list to `TrySpawnRing`/`TrySpawnObject` without an X edge filter. On a rightward slide the newly tracked section can be up to ~$500px beyond the right load edge, so all its in-band rings are added immediately rather than waiting for the ratchet to reach them. Fine at current entity counts; could front-load spawns noticeably on dense production sections.
**When to revisit:** when production entity density lands — watch `Ring_HighWater` after a slide vs a normal X ratchet advance. Perf backlog family (tile-cache N-way staging is the precedent for budgeted populate).

### Section_TeleportBwd .at_start clamp path lacks a SyncSlide-style guard
**Surfaced during:** visibility-window plan review 2026-06-12.
**What:** `Section_TeleportBwd` calls `EntityWindow_SyncSlide` unconditionally before the camera rebase, then may fall through `.at_start` with the slot map left as-is and still call `EntityWindow_TeleportShift`. Today `.at_start` is only reachable when `sec_x == 0` (already at the left edge of the grid — slot map parity guarantee holds). If that invariant ever breaks, the invariance assert would fire: a second SyncSlide call after an unchanged slot map with an already-shifted camera would re-derive the correct anchor, but the assert would see a mismatch. Add an Up-style guard (`cmpi.b #0, (Slot_Section_Map).w / blo.s .at_start_nop` pattern) when this path is next touched.
**When to revisit:** add the defense when `Section_TeleportBwd` is modified for any reason.

### Section_Check clobber header understates
**Surfaced during:** grid-edge branch review 2026-06-11 (pre-existing).
**What:** The `Section_Check` routine header documents a narrow clobber set, but its tail-branches (`bra.w Section_TeleportFwd` etc.) enter handler routines that clobber d0–d7/a0–a4 (`SyncSlide` + `TeleportShift` rebuild paths). Any caller that saves only the documented set around `Section_Check` will see unexpected register corruption. Fix the header when opportunistically passing through.
**When to revisit:** opportunistically when touching `Section_Check` or any teleport handler.

### Row-2 seam fixtures — DOWN-direction preview only structurally tested
**Surfaced during:** visibility-window verification 2026-06-12.
**What:** Vertical slide and DOWN teleport paths are structurally exercised (window derives rows correctly, vertical streaming works), but sections 6–8 (row 2 of the OJZ 3×3 grid) have no ring or object content, so the row-2 seam has no visible entities to confirm preview behavior end to end. The structural path is proven; the content test is deferred.
**When to revisit:** when row-2 section content is authored for production OJZ or any zone with ≥3 row sections.

## From Compression Two-Tier (2026-06-11)

### S4LZ DP literal-extension undercharge
**Surfaced during:** compression-two-tier review 2026-06-11.
**What:** The DP cost model doesn't charge the 2-byte lit-count extension word for literal runs ≥ 15 words. Fixing this requires run-length-aware DP state (~16× build time) for a measured ceiling well under 0.5% of the block corpus. Not worth it; recorded so it isn't re-litigated.
**Status:** Won't fix — cost model undercharge is negligible in practice.

### S4LZ decompressor micro-optimizations (audit F4 speed wins)
**Surfaced during:** compression audit 2026-06-11 (cycle analysis in docs/research/compression-audit-2026-06-11.md).
**What:** The decoder runs ~510-640 KB/s realistic mix. Three ranked wins were measured but NOT implemented because current budgets fit (6 blocks/frame ≈ half a frame; vertical scroll protocol +4/512px unchanged with dictionaries on): (1) `move.l` in the unrolled copy tables (guard match path for offset ≥ 4) — pure literals 10.2 → 9.2 c/byte; (2) unroll the extended-count `dbf` loops (currently the SLOWEST path per byte despite being the bulk-copy case) — 22 → ~12.5 c/word; (3) 256-entry token jump table (~1.5 KB ROM) — mixed ~13.7 → ~10 c/byte ≈ 770 KB/s.
**When ready:** when block budgets grow (BLOCK_DECOMP_BUDGET > 6, bigger blocks, or new per-frame consumers) or profiling shows decode pressure.

### ZX0 needs budgeted decode before any mid-gameplay use
**Surfaced during:** compression-two-tier T6 measurement 2026-06-11.
**What:** ZX0 measured ~76 KB/s (5 frames synchronous for a 6.3 KB section blob). Today it runs only at level init (invisible). The §4.2 deferred cold-load design (mid-traversal FWD/BWD section art loads — currently stubbed) would freeze ~5-7 frames if it called `Art_Decompress` on a ZX0 blob synchronously. Before implementing deferred loads: either route them through §9.7 cooperative-multitasking budgeted decode, or keep gameplay-streamed art on the S4LZ tier (wrapper version byte already dispatches per blob — the pipeline can mix tiers freely).
**When ready:** with §4.2 deferred cold-load implementation.

### Level editor exporter template is stale (dict fields, .zx0, blob aliases)
**Surfaced during:** compression-two-tier T2/T3 2026-06-11. Editor repo (sonic-level-editor, user-triaged commits only).
**What:** The editor's act-descriptor exporter (`src/core/export/act-descriptor.ts`) still emits the pre-compression-branch shape: `sec_reserved_2C`/pad instead of `sec_block_dict` ($2C) + `sec_block_dict_len` ($46); `OJZ_SecN_Tiles_S4LZ` labels + `.s4lz` BINCLUDEs instead of `OJZ_SecN_Tiles` + `.zx0`; 18 per-section BINCLUDE lines instead of the two generated blob-alias includes (`sec_tile_blobs.asm`/`sec_block_blobs.asm`). Nothing breaks today (the export dir isn't in the ROM build), but the NEXT editor export would hand the engine a NULL dict pointer for dict-compressed blocks. Also: `tools/ojz_strip_gen.py editor_data_available()` hardcodes `ojz/act1/section_0.tiles.bin` instead of deriving from project.json `dataPath` (same config-derivation treatment as the 2026-06-11 chunk-library move).
**When ready:** before the next editor level export; engine-side spec is all on master (structs.asm Sec fields, act_descriptor.asm as reference).
**Update 2026-06-11 (entity exporter):** entities now follow the build-step model —
`tools/ojz_entity_gen.py` generates entity_data.asm from the editor JSONs (X-sort,
validation, per-section minimized type tables, ring-buffer pressure analysis).
Direction decision: editor authors JSON, BUILD generates engine format — the
act-descriptor exporter above should eventually shrink into the same model rather
than be fixed in place. Editor-repo follow-up: placement UI checkboxes for the new
`anyY`/`xflip`/`yflip` object fields (generator already accepts them). Generator
polish backlog (review minors): friendly errors for malformed JSON/float coords,
warn on whole-act-empty dataPath misconfig, duplicate library-id check.

### Streaming polish backlog (consolidated pointers)
**Surfaced during:** vertical-streaming 2026-06-10 (full analysis in that plan's RESULTS + follow-ups).
**What:** (1) Prefetch column cursor — residual +4 vertical / +6 horizontal lag per 512px is block-row/col crossing decompresses; prefetch re-probes only the view-center column, walking the ~6 visible block columns between crossings should reach ~+1. (2) Per-VBlank plane-buffer drain budget — the deeper fix if row payloads ever grow past 2 rows/frame again. (3) DEBUG_FLY_SPEED_FAST is pinned to base speed by the 16px/f camera clamp (turbo is a no-op).
**When ready:** any perf-focused session; all measured groundwork is in docs/superpowers/plans/2026-06-10-vertical-streaming-budget.md.

### Real ring/object art at safe VRAM slots
**Surfaced during:** objects-v2 play-testing 2026-06-10.
**What:** Test objects render placeholder squares; VRAM_TEST_SONIC-era test art sat inside the FG pool (caused the debug-exit tile corruption, since fixed by relocation). Production ring/monitor/object art needs proper slots in the unified pool via the build-time allocator, replacing the placeholders so play-testing reads like a game.
**When ready:** prerequisite satisfied — §4.9 phase 2 (vertical entity window) shipped 2026-06-11; entities now spawn everywhere on both axes. Ready to pick up in any art-focused session.

---

## From Sound Driver Work (Future)

### Music-expression Task 0 (Z80 code recovery) — follow-ups — 2026-06-24
Task 0 recovered Z80 code headroom (2 → ~1016 B) by **co-locating** the engine lookup tables
at the start of Moving Trucks' streamed ROM bank (window `$8000`), read with the song bank
already in the window — no swap. SFX is covered (its blobs share MT's bank). Verified: MT
renders == pre-banking baseline. Merged on `feat/sound-task0-recovery`. Two follow-ups:
- **Bank-D (DAC) co-location hook — for the first real COPY / FM6=DAC-drum song.** COPY songs
  run with the **DAC sample bank** in the window during their frame, which lacks the tables.
  When a real drum song is authored, emit a **label-free data-only copy** of the engine tables
  at the DAC sample bank start (`main.asm`, after `dac_samples.asm`'s `align $8000`) — needs a
  small generator tweak (`gen_sound_tables.py` + `zyrinx_player.py` to emit a data-only twin,
  since the labels are defined once in MT's bank). The Phase-3 scratch COPY test songs (id 1–5)
  were dropped, so nothing needs this today. The banking model (tables at bank-start in whatever
  bank the window holds) is the general rule; this is just the COPY instance.
- **Dead 68k table copies.** With the scratch COPY songs gone, `data/sound/fm_patches.asm`
  (`FmPatchTable`) and `data/sound/sound_tables.asm` (the 68k duplicate of the Z80 tables) are
  now **wholly unreferenced** (the runtime uses the Z80 copies). Candidate for removal — left in
  this pass to keep Task 0 scoped to recovery.

> **Driver note:** the engine ships a **from-scratch custom Z80-autonomous sound driver**
> (2026-06-16 master sound spec), NOT an imported Flamedriver. Plans **1A** (foundations),
> **1B** (DMA-survival DAC), **1C** (FM+PSG sequencer), **1D** (Moving Trucks FM infra), and
> **Phase 3a** (FM depth — per-frame modulation engine + native Moving Trucks port) are SHIPPED
> (merged to master `c89bea3`, 2026-06-19). The remaining Phase 2 / 3b / 4 / 5 / 6 backlog
> (N-channel DAC mixer, FM extras, adaptive FM6, section-aware banking/fades + SFX, MegaDAW export)
> is tracked at the bottom of this section. References to "Flamedriver upload" below are historical.

### Sound Engine Deep Audit (2026-06-21) — Full Bug Backlog + Best-in-Class Roadmap
**Surfaced during:** a 73-agent adversarially-verified correctness audit + a fact-checked frontier
gap analysis (Zyrinx, XGM/XGM2, Echo, MDSDRV, GEMS, Flamedriver, demoscene/MegaPCM). Branch
`feat/sound-phase5a-sfx`. Memory: [[project_sound_audit_2026_06_21]], [[project_sfx_pitch_open]].
**Verdict:** structurally sound — **0 crashes, 0 register/bus-corruption, 0 IRQ bugs**. 40 confirmed
issues, clustered in SFX + DAC + the build pipeline. We are already best-in-class on DMA-survival
DAC cadence, the SFX steal/priority/ducking engine, and the static key-on FM-expression layer.
**Status of Item 1 (IN PROGRESS, branch off this one):** bug B1 (transcoder operator swap) + bug
A1 (SFX steal silence-gap). Everything else below is the durable backlog so nothing is lost.

#### A. Bugs reachable in normal gameplay (fix soon)
- **A1 — SFX steal silences the music voice it stole** (`engine/sound_sfx.asm` ~447/895/920/947).
  Steal's key-off clears `SCF_KEYED` on the music channel; `Sfx_Restore` tests that *same* now-cleared
  bit to decide whether to re-key the held note, so it never re-keys → music voice dropout on every
  steal of a sounding FM/PSG note. **Fix:** stash the music channel's KEYED state at steal, branch
  Restore on the saved bit. (Violates the spec's "no silence gap" criterion.) **→ Item 1.**
- **A2 — two SFX in one 68k frame → only the last survives** (`engine/sound_api.asm` 130; single-byte
  `SND_REQ_SFX`, latest-wins; consumed once/VBlank at `z80_sound_driver.asm` 522). Jump+ring, skid+ring,
  death+ring-loss all drop one SFX, *priority-blind*. The Z80 3-deep queue sits downstream and can't help.
  **Fix:** Flamedriver two-slot post (`zSFXNumber0/1`) or a small 68k-side pending ring. Audio-only (high/med).
  **IMPLEMENTED (af09e83, 8-deep 68k-side ring):** `Sound_PlaySFX` enqueues; `Sound_DrainSfxRing`
  (GameLoop, post-VSync) posts ONE id/frame into the mailbox once the Z80 has cleared it. Lint clean,
  full ROM assembles. **Runtime hardware-verification PENDING** — blocked by the OJZ section-0 tile-budget
  build failure below (no bootable ROM). Verify once that's resolved: jump+ring / skid+ring / death+ring-loss
  in one frame both reach the chip. Logic hand-traced (enqueue/drain/dedup edge cases) in the interim.

#### B. Build-pipeline / fidelity bugs (the "SFX sounds wrong" root cause)
- **B1 — transcoder swaps physical operators S2↔S3** (`tools/sfx_transcode.py` ~388). Emits S3K op
  order straight through, but our engine maps byte-index k→reg base+k*4 = physical `[S1,S3,S2,S4]`;
  S3K uploads `[S1,S2,S3,S4]`. Every transcoded FM SFX plays with OP2/OP3 transposed → wrong timbre
  (spindash alg-4 swaps the *modulators* = large). **Likely root of [[project_sfx_pitch_open]].**
  **Fix:** emit `[src[3],src[1],src[2],src[0]]` (OP_REORDER=[0,2,1,3]) for the S3K-SFX path only. **→ Item 1.**
- **B2 — by-ear FM octave / spindash-sweep "taste knobs" baked into committed SFX data** (`sfx_transcode.py`
  151-176; `_FM_SFX_OCTAVE`, `_SPINDASH_MOD_SCALE`). Unconverged WIP; likely *compensating* for B1.
  **After B1 lands + regen, re-evaluate — they may collapse toward 0/S3K-faithful.** (Paused 2026-06-21.)
- **B3 — AM-enable bit dropped vs S3K byte** (`sfx_transcode.py` 330-336/390; `_am<<5 & 0x80` always 0).
  Harmless on YM2612 (bit 5 of $60 is a don't-care) but a byte-fidelity divergence + a trap if a real
  AM voice is ever transcoded. Doc or preserve the junk bits.
- **B4 — looped-SFX fade tail (`smpsFMAlterVol`) + bare-duration replay — FIXED 2026-06-21** (see
  `docs/BUGS.md` BUG-002 items 1 & 3). The transcoder collapsed S&K's per-pass `smpsFMAlterVol` fade to one
  constant `MEV_VOL` (roll tail held flat then hard-cut) and dropped the SMPS bare-duration "replay previous
  note" idiom (spindash rev-tail collapsed to zero ticks). Fixed transcoder-side (no Z80 growth — driver has
  4 bytes free): AlterVol-bearing `smpsLoop`s are now UNROLLED with a dB-faithful per-pass fade (invert
  `LogVolumeLutZ`), and a standalone duration byte re-articulates the previous note. Packer backstop added.
  **`smpsNoAttack` (the per-pass FM re-key) — DONE 2026-06-21** (was the deferred half). VGM capture proved
  the unrolled tails re-keyed the FM envelope 43×(roll)/26×(spindash) at 30 Hz — the "jingle/higher-pitch"
  the user heard. Fixed in EXACTLY the 4 free Z80 bytes: bit 7 of a NoteDur's pitch operand is a no-attack
  flag; `Seq_Op_NoteDur` does `ld d,a / bit 7,d / ret nz` to skip the note-on hook (no `$28` re-attack AND no
  freq re-write) for a held continuation. The transcoder sets bit 7 on tail passes via `mod_dirty`: the FIRST
  note after a modSet still re-keys (resets the swept pitch to base), the rest hold. Verified on hardware:
  KEY-ON 43→2 / 26→2, tail holds at base fnum, TL fade intact. **Transition re-key (the last residual) —
  FIXED 2026-06-22** (see `docs/BUGS.md` Items 1+3 follow-up #3): `Seq_Op_ModSet` now re-writes `sc_base_freq`
  via `Fm_WriteFreq` (held-note pitch change, no `$28`) for SFX FM channels, so the modSet-off snaps the tail
  to base with no re-key; the transcoder holds ALL tail passes. +18 Z80 bytes reclaimed by folding 6 more
  channel-class tests into `Snd_ChanClass` (`Z80_SOUND_SIZE` `$16EE`, 2 free). Verified: roll/spindash
  KEY-ON 2→1, fades intact, skid/ring/jump/dash no regression. The looped FM SFX tails are now S&K-faithful
  (one key-on, smooth fade to silence). `Snd_ChanClass` has converted 11 of 12 inline channel-class sites;
  the 1 remaining + future reclaim is there if needed.
- **B5 — `smpsPSGform $E7` tone-FREQUENCY-TRACKED noise sweep** (refinement; the fixed-rate fix is done — see
  `docs/BUGS.md` BUG-003). The dash `$B6` (and any `smpsPSGform $E7` SFX) is now correctly rerouted to the
  NOISE channel, but plays a FIXED white-noise rate (`$E6`, clk/2048). S&K's `$E7` is white noise whose shift
  rate TRACKS PSG3's tone frequency — so as the channel's tone sweeps (its `smpsModSet`), the noise pitch
  descends (a "pshhew"). Reproducing it needs the engine to drive PSG3's frequency register as the noise clock
  + apply the modulation to it, with the audio on the noise channel — either (a) a `Psg_Noise` `$E7` path that
  writes PSG3's freq from the note+mod, or (b) the transcoder splitting the source channel into a silenced
  tone-clock (PSG3) + a noise channel (the engine + hardware then sync via the `$E7` track bit). Option (b) is
  engine-change-free but adds a 3rd SFX channel + needs the clock pinned to PSG3 (no voice substitution). The
  fixed-rate noise is the right character; the descending sweep is the nuance. Re-evaluate by ear.

#### C. DAC sample path — correct today by coincidence, breaks the moment real drums land
*(Do all four as ONE format revision — and fold in the best-in-class DAC work, item E2/E3 below. Partly
already tracked in "Multi-sample DAC loop-restart hardcodes the blip descriptor" further down.)*
- **C1 — one-shot samples never stop** (`z80_sound_driver.asm` 414-423). `DAC_ACTIVE` only ever set,
  never cleared on exhaustion; FILL-exhaust unconditionally re-loops the blip → any real drum machine-guns.
- **C2 — `Snd_StartSample` ignores `ds_loop_ofs` + `ds_rate`** (601-619). Descriptor loop-point + per-sample
  rate inert; multi-sample DAC blocked.
- **C3 — odd `ds_length` runs away ~64KB** (407-413). FILL `-=2` + `==0` test misses an odd final byte →
  reads off the end / bank-wrap. **Fix:** build-time assert sample lengths are even.
- **C4 — no consumer underrun guard** (353-363). Over-long DRAIN replays stale ring bytes as a buzz, no
  detection. **Fix:** output `$80` (DC center) when `lead==0`.

#### D. Latent correctness (trust-the-packer / new-content surfaces)
- **D1** PSG pitch-mod has no noise-route gate (`sound_sequencer.asm` 162; `sound_psg.asm` 239) — a noise
  channel carrying `sc_mod_ctrl!=0` corrupts the noise control register. Gate on tone route + reject in transcoder.
- **D2** note before any set-duration reloads from a zeroed `sc_dur_default` → 255-tick stuck note
  (`sound_sequencer.asm` 536; init `sc_dur_default` to 1).
- **D3** `sc_mod_wait` never restored on note re-arm — 2nd+ modulated note gets zero delay vs S3K
  `zPrepareModulation` (`sound_sequencer.asm` 381; add `sc_mod_wait_raw`).
- **D4** `Psg_NoteOn` ignores `sc_transpose` (S3K applies it to PSG too) (`sound_psg.asm` 154).
- **D5** PSG envelope attack uses a stale `sc_psgenv_out` / lands one frame late vs S3K (`sound_psg.asm`
  106/184; zero `sc_psgenv_out` at cursor-reset).
- **D6 (uncertain)** single-level repeat state may carry a stale `sc_repeat_count` across a song loop /
  mid-flight jump (`sound_sequencer.asm` 1042). Watch; add a packer guard if it bites.
- **D7** `MEV_REPEAT_END` operand 0 → 255-pass repeat, no runtime clamp (`sound_sequencer.asm` 1022; trust-packer).

#### E. Best-in-class — the honest gaps (cross-driver consensus)
**DO NOW (high payoff, seam already exists, ~no pigeonhole):**
- **E-now-1 — continuous/fine pitch + portamento ON MUSIC channels.** Every frontier driver converged
  on this (Zyrinx fine ladder + restoring-division glide `batman_driver_analysis.md`:186-219; MDSDRV 256
  steps/semitone; XGM2 freq-delta; Flamedriver pitch-slide w/ octave-rollover). Our `FmPitchTableZ` is
  strictly chromatic and our continuous-vibrato core (`Mod_Advance`/`sc_base_freq`/`sc_porta_*`) renders
  **SFX channels only** — music gets none. Promote that machinery into the music `SeqChannel` path + add a
  fine-pitch representation. Fields `sc_porta_accum/incr` reserved (`sound_constants.asm` 793). *(This is
  the same as the long-deferred Phase 3a Task 7 portamento + Zyrinx "take-next".)*
- **E-now-2 — per-frame FM TL volume envelope on music channels** (Flamedriver `zDoFMVolEnv`). We have
  static `OPBIAS` only. Reuses the existing `Fm_PatchTlGroup` TL-write plumbing. No format change.
- **E-now-3 — master fade-in/out + global tempo-speedup.** Grep-confirmed we have **neither** (Flamedriver
  `zDoMusicFadeOut/In`, `zFadeToPrev`, `zTempoSpeedup`). Table-stakes for level start/clear/death/drowning/
  invincibility/1-up. Cheap (ramp carrier TL toward $7F + a tempo-accumulator scalar w/ save/restore).
- **E-now-4 — sequencer-driven hardware LFO ($22 rate opcode).** We set `$22=$08` once at init and never
  sweep it; one free MEV opcode. **Also fix latent doc bug:** comment at `z80_sound_driver.asm` 219/228 says
  3.98 Hz but `$08` = **3.82 Hz**.

**DESIGN-FOR-IT-NOW, build later (the ONE true pigeonhole + its companions):**
- **E2 — multi-voice PCM mixing on FM6 DAC** — the single architectural decision that forecloses the
  frontier. XGM(4ch)/XGM2(3ch)/MDSDRV(2-3ch)/DualPCM(2ch) sum samples in Z80 RAM; our consumer copies one
  byte, no summing stage, no per-voice volume field (`z80_sound_driver.asm` 353-363; `sound_constants.asm`
  228-234). **Don't build the mixer now — shape the ring consumer + `DacSample` descriptor for N voices now**
  (per-voice volume byte + 16.16 mix cursor so per-sample pitch is free later), ship 1 voice, keep the
  RAM-only equal-cost invariant. This is the "[[feedback_best_of_class_north_star]] design-for-C, build-for-A"
  call — do it **before authoring real DAC content.**
- **E3 — round out the DAC format in that SAME revision:** loop point (= C2), priority, pan (via $B6),
  auto-bankswitch, `ds_rate` pitch, **+ 4-bit DPCM** (re-adopt our own S3K JMan2050 DPCM, `Flamedriver.asm`
  4321-4442 — halves ROM, producer-side so the 8948 Hz cadence is untouched), and route **sampled SFX** as
  mixer-voice-2 with ducking. (Skip PCM-on-PSG.) Fold the C1-C4 bug fixes in here.
- **E4 — independent per-channel modulation/control stream (dual-stream channels)** — Zyrinx's "feels alive"
  secret + MDSDRV macro-tracks. The seam is **already committed** (`sc_mod_ptr` slot[1], stream-agnostic
  `ModUpdate`) — best-prepared seam in the driver. *(= Phase 3b "dual per-channel data streams".)*
- **E5 — SSG-EG per-operator looping ($90-$9E)** — cheap buzzy/metallic/AY timbre family, one reg write at
  note-on. **Correction:** `MEV_REGDELTA` does **not** currently reach $90 — `RegDeltaGroupBase` is only
  $30-$80 (6 of 16 groups, `sound_fm.asm` 547). Add a 7th group + a per-op patch byte.

**SKIP / DEFER (and why):**
- **68k-resident sequencer (MDSDRV model)** — explicitly **skip**; our full-Z80 autonomy is the right call
  for a 60fps section-streaming platformer with a busy 68k. Borrow MDSDRV's *techniques* onto the Z80, not
  its CPU placement.
- **CSM mode** — skip; contends with Timer-A (our ~59 Hz sequencer clock).
- **CH3 special mode** (someday; niche, complicates FM3 SFX voice arbitration in `sound_sfx.asm`) and
  **Echo-style adaptive live-inject** (someday; mailbox could grow a direct-event slot — protocol is already
  reentrant/extensible). Build only when a concrete song/boss needs them.

#### F. Hygiene — doc drift, dead code, RAM budget (recovers ~750 B ROM)
- **F1** Z80 RAM-map spec (`docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md`) is STALE — the SFX
  array $1D00-$1EBC overruns the doc's "spare" page; `SND_STATE_BASE` moved $1600→$16F0; sequencer/trace/
  song/SFX regions undocumented. Reconcile to the live `sound_constants.asm` map + state true headroom.
- **F2** `ENGINE_ARCHITECTURE.md §6` still lists SFX deferred + AF_SOUND a stub (update on merge to master).
- **F3** Dead ROM: `dc.l SfxTable` 540 B unused (engine uses its own Z80 `dw` window table); duplicate
  `sfx_NN_patches` banks ~208 B; dead `Snd_TimerA_Program` (`z80_sound_driver.asm` 715). Purge.
- **F4** Stale/load-bearing-wrong comments: ISR "ix NOT touched" (it IS, via SfxDispatch — safe by
  construction, but the *reasoning* would license a future bug); `Sfx_Restore` "ret stub" (it's implemented);
  PSG header "never clobbers de" (it does; caller restores it); a0-clobber contracts on Sound_StopMusic/
  PlaySample/Ping/PlayRing (same class just fixed in Sound_PlaySFX — unify to all-preserve-a0).
- **F5** Z80 blob space TIGHT: ~118 B code headroom, ~67 B to the mailbox. Plan a space recovery (bank
  FmPitchTableZ/LogVolumeLut/MovingTrucks_PitchTable into a $8000-window read) **before 5b/FM6**.

### Per-frame pitch / volume envelopes (Phase 3a #2/#3) — DEFERRED, build-on-demand
**Surfaced during:** Moving Trucks missing-effects investigation (2026-06-19).
**Decision: do NOT build for MT; build only when a song's data actually uses them.**
**What:** A `ModUpdate` per-frame pitch-envelope processor (continuous intra-note pitch shape on
plain count==1 notes) and a per-frame volume-envelope/TL processor. A VGM census first *looked*
like MT needed these (oracle wrote freq ~16×/note, TL ~33×/note). **Re-measurement proved that was
an artifact:** the Zyrinx driver re-asserts every register every frame (60Hz full-state refresh) —
**97% of its freq writes and 99% of its TL writes are redundant re-writes of UNCHANGED values.**
Normalized to actual value *changes* per note, ours ≈ oracle (freq 0.92 vs 0.93/note; TL 0.43 vs
0.50/note). Our write-on-change engine already produces the same chip state. Building these now and
applying them to MT would ADD modulation MT doesn't have = over-modulation = WORSE. They remain
legitimate **general** capabilities (many FM tunes use real sweeps/swells) and the modulation layer
(`ModUpdate`, the design-for-C seam) is already architected to host them — so adding them later is a
clean drop-in. **When to build:** when a ported/authored song's command data actually requests
intra-note pitch/volume movement. Tool: `tools/vgm_intranote.py` (intra-note change census) +
`tools/vgm_modulation_diff.py`. LESSON: register write-COUNT is a misleading proxy; measure value
CHANGES. See memory [[project_mt_correct_source]].

### GATE articulation ($1A) — transcoder drops it (Phase 3a #4)
**Surfaced during:** same investigation. **Status:** deferred; only worth doing if percussion
phrasing audibly differs from B&R. **What:** MT uses 340 GATE commands (note-shortening, mostly
ch5/ch3/ch4 percussion). `tools/zyrinx_player.py` currently drops them (the gate-as-note-off model
b4137be/63bfd62 was REVERTED by 78fdfaf), and the engine has no sub-duration note-length field to
receive one. **When to build:** if the user reports percussion still lacks staccato/punch vs the
oracle. Needs BOTH a transcoder re-emit and an engine note-fill/gate-time field — and coordinate
with the reverted commits to avoid repeating whatever broke them.

### opbias-on-carriers fix (commit 05eca4a) — KEPT, carrier path not yet song-verified
**Status:** shipped + kept (correct latent-bug fix). `Fm_SetVolume` now writes carrier
TL = clamp(base + sc_opbias[op] + log), consistent with `Fm_PatchTlGroup`. **Caveat:** MT does not
exercise carrier opbias (FM2 carrier opbias=0), so it's verified by code audit + "doesn't break MT",
not by a song that uses it. **TODO when convenient:** add a synthetic alg5–7 test voice with a
carrier bias and capture-verify the $4x output, to bulletproof the untested path.

### Multi-sample DAC loop-restart hardcodes the blip descriptor (latent bug, Plan 1C)
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17).
**Status:** Benign in 1C (single DAC sample); **must fix before adding a 2nd DAC sample.**
**What:** The FILL-exhaust restart in `engine/z80_sound_driver.asm` (the rare "sample
exhausted → loop the blip" branch, ~line 399) hardcodes `SND_BLIP_PTR` / `SND_BLIP_LEN`:
```z80
        ld      hl, SND_BLIP_PTR
        ld      (SND_ROM_PTR), hl
        ld      hl, SND_BLIP_LEN
        ld      (SND_ROM_LEN), hl
```
instead of re-reading the **active `DacSample` descriptor's** loop fields (loop ptr / loop
len). In 1C there is exactly one DAC sample (the blip), so the constants and the active
sample agree and the restart is correct. The moment a second DAC sample (e.g. a real drum)
is added, an exhausted non-blip sample would incorrectly restart into the blip's bytes.
**When to fix:** when the DAC gains a 2nd sample (Phase 2 N-channel mixer, or any new drum):
have the exhaust branch reload `SND_ROM_PTR`/`SND_ROM_LEN` from the currently-playing
descriptor's loop fields (the `SND_LOOP_OFS` / per-sample loop machinery already exists in
`SND_STATE_BASE`), not from the fixed `SND_BLIP_*` constants.

### Dead-but-drift-guarded 68k ROM table/patch copies (Plan 1C)
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17).
**Status:** Harmless in 1C; candidate for trimming in a later phase.
**What:** The FM writer / sequencer read **inline Z80 copies** of the sound tables and FM
patches (`engine/sound_tables_z80.asm` and `data/sound/fm_patches.inc`, both included into
the `phase 0` Z80 blob). The **68k ROM copies** — `data/sound/sound_tables.asm` and
`data/sound/fm_patches.asm` (the latter `include`s the same `fm_patches.inc`) — are emitted
into ROM (via `main.asm`) but **not read by any 1C code path** (decision: inline for 1C, not
banked). They exist for a future banked-ROM loader. They are **drift-guarded**: the patch
bytes are single-sourced through `data/sound/fm_patches.inc` (a `pbyte` macro picks `dc.b`/`db`
per CPU), and `gen_sound_tables.py`'s generator + its pytest keep the table copies in sync, so
the dead copies cannot silently diverge.
**When to fix:** a later phase that either (a) adopts a banked-ROM song/patch loader (then the
68k copies become live), or (b) decides inline-only is permanent (then drop the unread 68k
`.asm` copies + their `main.asm` includes to reclaim ROM). No urgency — drift-guarded, small.

### Phase 2–6 sound backlog (master sound spec §12)
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17), per the 1C design §2 "explicitly deferred."
**What (each its own plan, per master spec §12):**
- **Phase 2 — DAC powerhouse:** N-channel DAC mixer (quality-adaptive single↔mix), stereo/pseudo-
  stereo PCM, pitch-shifted SFX, half-rate samples, BRR codec (after spike), bank-switch optimization.
- **Phase 3a — FM depth (SHIPPED, merged `c89bea3` 2026-06-19):** per-frame modulation engine,
  per-song pitch table + pitch envelopes (trills/arps), pan, signed per-op TL bias, voice-stepping
  via build-time register deltas, hardware LFO ($22=$08), note-fill gate articulation, native Moving
  Trucks port. **Deferred build-on-demand within 3a:** **Task 7 portamento** (MEV_PORTA — `sc_porta_*`
  struct fields reserved, not rendered) and the **formal Task 9 verification-harness file**
  (`tools/phase3_verify.py` was never written; MT fidelity was instead verified ad-hoc by rendered-audio
  comparison vs the GD3 rip — see memory [[project_mt_resolved]]).
- **Phase 3b — FM extras (DEFERRED):** dual per-channel data streams, true (division-based) portamento,
  SSG-EG, broader LFO use, Ch3 special/CSM, detune-unison, full PSG envelopes, raw-register escape hatch.
- **Phase 4 — Adaptive FM6/DAC slot:** the three content-adaptive modes (full 6th FM voice /
  Batman time-share / permanent N-channel DAC mixer). 1C keeps FM6 permanently the DAC (simple model).
- **Phase 5 — Engine integration & game-feel:** section-aware sound banking, music fade state machine,
  distance attenuation + priority SFX mixing, procedural ambient soundscape, continuous SFX. (These are
  ENGINE_ARCHITECTURE §6.4–6.7, all DEFERRED.)
- **Phase 6 — MegaDAW compiler:** event-list format finalization, MegaDAW export retarget,
  sample/DC-offset encoders. (1C hand-authors the test song; MegaDAW integration + real song-sourcing
  are downstream/user-driven — the engine defines the format contract first.)
**Blocked by:** 1C and Phase 3a have merged to master; remaining phases are sequenced next — **Phase 5
(SFX + game integration) is the current priority** (biggest gap: no SFX path exists, music is debug/boot
only). Each phase is audible + Exodus-verifiable.
**See:** `docs/superpowers/specs/2026-06-16-sound-driver-design.md` §12; `docs/superpowers/specs/2026-06-17-sound-1c-design.md` §2.

### Defensive Z80 RAM Upload — Verify-and-Retry
**Surfaced during:** Ristar disassembly deep-dive (2026-04-27). Source:
`ristar_disasm/code/disasm.asm` lines 8330–8350 (`$641A` upload routine);
analysis in `ristar_disasm/ANALYSIS.md` § "Sound architecture (CONFIRMED)".
**Blocked by:** N/A for 1C — the from-scratch driver is **assembled inline into the ROM**
(`engine/z80_sound_driver.asm`, `phase 0` blob), so there is no runtime 68k→Z80 byte-by-byte
*driver upload* to wrap. This pattern applies only if a future phase streams driver/data bytes
into Z80 RAM at runtime (it does not today).
**What:** Ristar's Z80 RAM upload routine writes each byte, **reads it
back to verify**, retries up to 16 times on mismatch before giving up.
Most Genesis games trust the write; Ristar's team apparently saw
intermittent bus-contention failures and added the retry loop. The
relevant pattern (paraphrased):

```asm
; In: a0 = src, a1 = z80_dst, d0 = byte count - 1
upload_loop:
    move.b  (a0)+, d1               ; load src byte
    moveq   #15, d3                 ; retry counter
.retry:
    move.b  d1, (a1)                ; write to z80 ram
    cmp.b   (a1), d1                ; verify
    beq.s   .ok                     ; matches → next byte
    dbra    d3, .retry              ; mismatch → retry
    bra.s   .abort                  ; give up after 16 tries
.ok:
    addq.w  #1, a1
    dbra    d0, upload_loop
```

**When ready:** Only if a future phase adds a **runtime** 68k→Z80 RAM byte-copy
(e.g. streaming song/sample data into Z80 RAM, rather than the current inline-in-ROM
driver). Wrap each Z80 byte write with the read-back-verify retry loop. ~30 extra lines
of asm. Not applicable to the inline-assembled 1A/1B/1C driver.
**Why bother:** Cheap insurance against a real-but-rare bug class. Most
runs will hit `.ok` on the first try; the retry only fires when the bus
is contended (probably never on most hardware revisions, but the cost is
~zero when it doesn't fire). Catches write-loss before it manifests as
silent driver failure or audio glitches that are nearly impossible to
debug after the fact.
**See:** `ristar_disasm/ANALYSIS.md`, `ristar_disasm/code/disasm.asm`
lines ~8330–8350.

## From Build Pipeline — Future Optimizations

### Pre-Baked Path Tables for Loops / Special Geometry
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Define loops, S-tubes, and corkscrews as parametric curves in the editor. Build tool samples the curve and emits a path table: sequence of (x, y, angle) waypoints. At runtime, player snaps to path and interpolates between waypoints — no per-frame collision queries during traversal. Eliminates the most complex and error-prone collision scenarios. Classic Sonic's loops use path-swapping between collision layers with hand-tuned height maps; this approach makes loops reliable by construction.
**Blocked by:** Level editor integration, §3 player physics (need movement system to consume path data).

### Build-Time Collision Validation
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Use modern CPU power to simulate player traversal at build time. Verify slopes are traversable (not too steep for physics constants), detect collision gaps, flag unreachable areas, check height profile transitions between adjacent cells for smoothness. Catches level design errors before they hit hardware.
**Blocked by:** §3 player physics (need physics constants and movement model to simulate), §4.7 collision system (need collision data format finalized).

### Animated Tile DMA Scripts
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Pre-compute animated tile sequences (waterfalls, conveyors, flickering lights) as table-driven DMA scripts at build time. Each frame entry is a pre-built DMA command (source ROM addr, VRAM dest, length). Runtime just steps through the table — zero computation, zero logic. Build tool handles figuring out VRAM addresses after graph coloring and structuring DMA entries.
**Blocked by:** Animated tile system design (Phase 4), VRAM graph coloring integration.

---

## How to Use This Document

When starting a new planning phase:
1. Read through deferred items
2. Check if any blockers are now resolved
3. If so, include the deferred work in the new plan
4. Move completed items to a "Done" section at the bottom (with the date and the system that unblocked them)

---

## Done

### Strip data emission + streaming decompressor removed (dead format) — 2026-06-11
**Completed in:** compression-two-tier Task 5 (dead-code sweep).
**What:** The 2D block cache replaced column strips entirely; the remaining strip
artifacts are gone. Deleted: `engine/s4lz_stream.asm` (zero callers) + `StreamState`
struct + `S4LZ_Stream_States` RAM; `tools/ojz_strip_gen.py` Pass 5b (wide-strip
`.s4lz` + checkpoint emission); the legacy `OJZ_Sec*_Strips_S4LZ` /
`OJZ_Sec*_Strip_Checkpoints` BINCLUDEs in the act descriptor (~50 KB ROM); orphan
generated files (`sec*_collision.s4lz` — no generator, no references;
`sec*_tiles.s4lz` — replaced by `.zx0`; stale sec9-D leftovers from the 16-section
era). Raw `sec*_strips_a.bin` emission STAYS — it feeds `ojz_block_gen.py` and the
editor (`sec*_strips_source.bin`). Also deleted `Section_StreamArtGroup` +
`STREAMING_BUFFER_A/B` + `Streaming_Active_Buffer` + `SS_STREAMING` (see the A.4
entry note below). The Sec struct never carried strip pointers by this point — no
layout change.

### §2 Phase 2 Layer A.5 T1 — Per-Section Background (Zone-Shared Tier) — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.5 (T1 only — T2/T3 fixtures deferred, see new entry below)
**What:** Plane B per-zone background art end-to-end. New shared-region VRAM block at slots 1280-1535 ($A000-$BFFF, 8 KB) reserved for BG tiles permanently — never overwritten by section transitions. Build tool extended: `load_bg_layout` parses OJZ_1.bin's BG section (16 chunk-rows × 128 cols), `build_bg_nametable_words` samples a 64×32 region, `emit_bg_tile_blob` dedupes + emits `bg_tiles.bin` with a 2-byte length header, `emit_zone_bg_layout` rewrites tile-index fields into the shared region (BG_TILE_BASE_SLOT + canon_idx). `chunk_get_tile_word` now honours chunk-entry X/Y flip flags (bits 10/11 per sonic_hack ProcessAndWriteBlock) — a latent bug uncovered during BG visual diff. Engine: new `engine/level/bg.asm` with `BG_Init` (loads BG tile blob to $A000 + blits zone nametable to Plane B at $E000, both blocking VDP DATA-port writes wrapped in stopZ80/startZ80) and `BG_RedrawForSection` (T2/T3-ready, called from teleport handlers; T1 sections with NULL `sec_bg_layout` skip). New struct fields: Sec.sec_bg_layout (replaces dead sec_strips_b placeholder, $1C, longword), Act.act_bg_layout ($16, longword), Act.act_bg_tiles ($1A, longword), Act struct $1A → $1E. Test scaffold loads dual palette: Pal_BGND (SonicAndTails, CRAM line 0) + Pal_OJZ (CRAM lines 1-3) matching sonic_hack's runtime layout.
**OJZ measurement:** 218 unique BG tiles (well within 256-slot capacity), bg_tiles.bin = 6978 bytes, zone_bg.bin = 4096 bytes, ROM cost ~11 KB. Engine cost: ~1.5 ms blocking at level init (display off), zero per-frame. Drop of 212 KB ROM elsewhere from removing the placeholder strips_b BINCLUDEs.
**Verified visually in Exodus:** Plane B renders OJZ's authentic cloud band (top) + sky transition + grass band (bottom) with magenta/pink/green palette colors, matching sonic_hack's Level_OJZ1_BG reference structure (image-9-style).
**Architectural fix vs spec:** §2.4's "T1 shares FG tiles, zero VRAM cost" claim was unworkable with A.3's per-section graph-colored FG pool — slots 0-1279 swap on every section transition, so BG nametable references can't reliably use them. The shared 256-slot region is the correct architectural fit. See `docs/research/per-section-background.md` Q5.
**See:** `docs/research/per-section-background.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.4 — Per-Section Deferrable Streaming — 2026-04-26
**DELETED 2026-06-11 (compression-two-tier Task 5):** `Section_StreamArtGroup` ended up
with zero callers — the union-blob model (color-class sections share one tile blob, so a
neighbor's art is already in VRAM; teleports mark sections `SS_RESIDENT` directly) made
runtime art streaming unnecessary, and the 2D tile cache (§4.7) superseded the preload
design it served. Removed with it: `STREAMING_BUFFER_A/B` (8 KB RAM),
`Streaming_Active_Buffer`, `STREAMING_BUFFER_SIZE`, and the `SS_STREAMING` state (value 1
retired; `SS_IDLE`/`SS_RESIDENT` keep their values). Entry below kept as history.
**Completed in:** §2 Phase 2 Layer A.4 (structural — visual verification blocked on upstream bug below)
**What:** `Section_StreamArtGroup` (engine/level/load_art.asm) decompresses + queues Deferrable DMA for an upcoming section. `Section_Check` extended to fire the preload trigger ~1024 px before the FWD teleport threshold (and ~512 px before BWD). Per-section state machine in `Section_Stream_State` (16 bytes RAM): `SS_IDLE` → `SS_STREAMING` → `SS_RESIDENT`. Two streaming buffers (`STREAMING_BUFFER_A`/`B`, 4 KB each, carved from existing `Decomp_Buffer`) handle fast direction reversals via round-robin. `Section_TeleportFwd`/`Bwd` retain blocking `Section_LoadArt` as a fallback for IDLE-state sections. `Level_LoadArt` reads section IDs from the act descriptor (not `Slot_Section_Map`) so it can be called before `Section_Init`.
**Verified structurally in Exodus:** `Section_Stream_State[0]=[1]=SS_RESIDENT` after Level_LoadArt; forward teleport advanced slot map 0/1 → 1/2 and Section_LoadArt fallback path fired correctly; backward teleport reversed cleanly.
**Visual verification blocked:** the test viewport renders mostly black due to a pre-existing upstream chunk/block parsing bug — see "Chunk/block parsing produces mostly-empty tiles" below.
**Closes the §4 Phase 1 deferred item:** "Section Preload with S4LZ Deferrable DMA" (the engine plumbing).
**See:** `docs/research/section-streaming.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.3 — Build-time Graph Coloring — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.3
**What:** Section adjacency graph + DSATUR greedy coloring + per-section VRAM-slot assignment, all at build time. `tile_dedupe.py` gained `compute_adjacency`, `color_sections`, `assign_section_slots`. `tools/ojz_strip_gen.py` emits per-section tile blobs (one per OJZ section) and an auto-generated `sec_vram_bases.asm` constants file. `Sec` struct gained `tile_art_s4lz` longword + `tile_art_vram` word (struct $40 → $48; `Section_GetSlotDef` updated to multiply by $48 = 72 instead of 64). New `Section_LoadArt` decompresses + DMAs one section's blob; `Level_LoadArt` walks the slot map and calls it for both initial slots; `Section_TeleportFwd`/`Bwd` call it for the new section after each teleport. The leapfrog system's adjacency invariant guarantees that the two visible slots always hold sections in DIFFERENT colors → DIFFERENT VRAM ranges → both render correctly simultaneously. A.2's region-1/region-2 fields removed from `Act_Desc` (multi-region packing remains in `tile_dedupe` for future use; A.3's per-section model is the active path; Act struct shrunk back to $16).
**OJZ measurement:** 16 sections in a horizontal chain → 15 adjacency edges → chromatic number 2 (path graph is bipartite; DSATUR optimal). Color bases: [0, 10]. Max simultaneously-resident: 20 tiles (10 per color × 2 colors; per-section blobs include shared tile 0 separately, so total > A.1's 10. Structural regression for OJZ-scale data; structural enabler for any zone that exceeds A.1's 1536-tile ceiling).
**Verified in Exodus:** Default rendering matches A.2 byte-for-byte. Forward teleport updates slot map 0/1 → 1/2 and runs Section_LoadArt for section 2 (Decomp_Buffer confirms section 2's tile data was decompressed and DMA'd). Backward teleport reverses. No nametable corruption, no flicker, rendering correct in both directions.
**See:** `docs/research/section-graph-coloring.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.2 — Multi-region VRAM Packing — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.2
**What:** `tile_dedupe.pack_regions` partitions canonical tiles across multiple VRAM regions; `tools/ojz_strip_gen.py` emits per-region pools (`ojz_tiles_r1.bin` / `ojz_tiles_r2.bin`) and supports `--force-region1-cap` for stress testing the spill path. Engine: `Level_LoadArt` calls `LoadArt_S4LZ` once per non-empty region. `Act_Desc` grew with `tile_art_r2_s4lz` longword (struct size $1C → $22). New constants `REGION1_TILE_CAPACITY=1536`, `REGION2_VRAM_BASE=$F800`, `REGION2_TILE_CAPACITY=64` define the layout. Region 2 lives in Plane B's off-screen rows ($F800-$FFFF, 16 rows × 128 bytes, 64 tiles), safe because OJZ's `cam_max_y=128px` keeps the visible bottom at nametable row 44 with a 3-row safety margin.
**Default-OJZ measurement:** 10 tiles fit in region 1; region 2 empty (placeholder S4LZ blob). Verified visually no regression vs A.1.
**Forced-spill (--force-region1-cap=5):** 5 tiles in region 1 (slots 0-4) + 5 in region 2 (slots 1984-1988); rendering matches default Exodus screenshot byte-for-byte. Confirms multi-region remap + dual LoadArt_S4LZ path works end-to-end.
**See:** `docs/research/multi-region-packing.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.1 — Tile Dedupe + Nametable Remap — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.1
**What:** Global flip-aware tile dedupe across all 16 OJZ sections, with build-tool nametable strip remap. New `tools/tile_dedupe.py` module (canonical_form + dedupe_tiles + remap_nametable_word, 12 unit tests, lex-smallest of 4 orientations as canonicalization rule per `docs/research/tile-dedupe-canonicalization.md`). `tools/ojz_strip_gen.py` extended with `decompress_full_ojz_art` + `collect_referenced_tiles` and a 3-pass generate flow (build strips → dedupe globally → remap + emit). Engine: new `engine/level/load_art.asm` exposes `LoadArt_S4LZ` (decompress to `Decomp_Buffer`, queue Critical DMA) and `Level_LoadArt` (act-descriptor-driven orchestrator). `Act_Desc` struct gained `tile_art_s4lz` longword + `tile_art_vram` word. `STRIP_TILE_HEIGHT` bumped 32 → 48 to sample first ground band. Build.sh now invokes ojz_strip_gen + s4lz compress. Test state replaces two manual `QueueDMA_Critical` calls with one `Level_LoadArt`. Closes the deferred "OJZ Tile Art Loading — Full Terrain Visibility" item. **Headline:** strip tile-index ceiling 1856 → 9, nametable collisions 2 → 0, VRAM bytes 10,304 → 320 (32× less). Full per-layer metrics in `docs/research/tile-pipeline-measurements.md`.

### VInt_DrawLevel CD-bit Corruption + Section_UpdateColumns Ring-Buffer Tracking (§4.1) — 2026-04-26
**Completed in:** §4 Phase 1 polish
**What:** Two integration bugs uncovered by the synthetic scroll test (`tools/synth_scroll_test_gen.py`).
1. VInt_DrawLevel's `lsl.l #2, d0` encoding leaked d0[31:16] garbage into VDP CD bits, randomly redirecting ~70% of column writes to VSRAM instead of Plane A. Fix: `moveq #0, d0` before reading the VRAM addr each iteration of `.next`.
2. Section_UpdateColumns tracked left/right boundaries independently, ignoring that the 64-col nametable wraps. Fix: clamp the opposite side after each loop so `Right - Left ≤ 63` always represents what's actually correct in VRAM.

### 128KB DMA Boundary Splitting (§1.1 / §2.1) — 2026-04-24
**Completed in:** §2 Art & Compression Pipeline
**What:** `QueueDMATransfer` checks if `source + length` crosses a 128KB boundary and splits into two queue entries. Sub+sub carry-flag approach (~16 cycles common case).

### Build-Time DPLC Tools (§2.1 / §2.6) — 2026-04-24
**Completed in:** §2 Art & Compression Pipeline
**What:** `tools/dplc_layout.py` — contiguous art rearrangement (1 DMA entry per frame change) + DPLC entry merging (3.1 → 1.2 entries average). Sprite art extracted to `art/uncompressed/`, optimized art in `art/optimized/`, DPLC tables in `data/dplc/`.
