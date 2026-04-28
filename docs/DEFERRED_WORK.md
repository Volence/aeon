# Deferred Work

Tracks work that was identified during design/implementation but deferred because dependencies don't exist yet. Check this document at the start of each new system's planning phase — items here may now be unblocked.

---

## From §1 — Core VDP Pipeline

These subsystems are fully designed in ENGINE_ARCHITECTURE.md §1 but require other systems to exist first.

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

### §2 A.x — FG Strips Have Wrong Content in Upper Rows
**Status:** Discovered while verifying §2.4 T1 fallback. As Camera_X scrolls into sec1+, Plane A's upper rows render dirt/rock chunk content with priority bit set (0xC846, 0xC04C — pal 2, priority high), filling the sky region with brown texture instead of being transparent. Plane A row 0 has all 64 cells filled with these tiles, not just slot 0's half. The BG layer underneath is correct; the FG covers it.
**Possible causes:** (a) `tools/ojz_strip_gen.py` strip emission samples wrong chunks for upper rows, (b) FG layout source file (OJZ_1.bin FG section) genuinely has those tiles and our build is faithful, (c) section streaming writes tiles to wrong nametable rows.
**Needs:** Compare sec1's `strips_a.bin` against expected chunks from sonic_hack's OJZ_1.bin FG layout; verify Plane A tile placement matches `Section_FillInitial` / `Section_UpdateColumns` math.
**Doesn't block:** §2.4 BG work is complete — this is a separate FG path issue. Likely lurking since A.3, surfaced now because users see the BG more clearly.

### §2 A.x — BG Tiles Render Black via Palette Index 0
**Status:** OJZ palette line 2 entry 0 = `$0000` (black) — matches sonic_hack source palette exactly. Many BG tiles in OJZ_1.bin's BG layout use palette index 0 for "outline shadow" pixels; in sonic_hack these are normally hidden by Plane A FG covering the grass band. In our engine, Plane A occasionally has transparent gaps (likely related to FG-rows bug above), exposing the BG's intentionally-black-pixel-0 outlines as visible black gaps.
**Doesn't block:** Cosmetic. Resolves automatically once the FG-rows bug is fixed (FG covers the BG black correctly).



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
**Blocked by:** Implementation of animation, collision, and player subsystems (need real field usage data)
**What:** Audit every SST field across all object types (player, badnik, platform, effect, boss, system) once subsystems are implemented. Determine actual field usage per type. Evaluate whether the SST can shrink from $50 to $4C or $48.
**When ready:** After §3 Phase 3 (animation) and Phase 4 (collision) are implemented — enough subsystems exist to see real field pressure.

### Word code_addr at $00 (§3)
**Blocked by:** SST field audit (want full picture before committing field sizes)
**What:** Use a word offset at $00 instead of longword function pointer (sonic_hack pattern). `objroutine function x,(x)-ObjCodeBase` computes offset from a $10000-aligned code bank. Dispatch: `moveq #BANK, d0; swap d0; move.w (a0), d0; movea.l d0, a1; jsr (a1)`. Saves 2 bytes per SST, 20 cycles per dispatch (~1,320 cycles/frame across 66 slots). Constraint: all object code must fit in one 64KB bank.
**When ready:** During SST field audit. Requires organizing object code contiguously.

### Word Mappings Offset (§3)
**Blocked by:** SST field audit
**What:** Use a word offset for `mappings` instead of a longword ROM pointer. All sprite mappings would live within 64KB of a base address. Saves 2 bytes per SST. Combined with word code_addr, that's 4 bytes freed — may enable SST shrink.
**When ready:** During SST field audit. Requires organizing mapping data contiguously.

### Variable SST Sizing — Effect Pool (§3)
**Blocked by:** SST field audit (need to know actual effect field usage)
**What:** Thunder Force IV uses $20/$40/$60 per-type pools. A $20 effect SST (explosions, dust, score popups, debris) shares the $00-$19 prefix with the full SST, enabling shared routines (ObjectMove, Draw_Sprite). Saves ~768 bytes at 16 effect slots. Trade-off: separate RunEffects loop, effects can't use routines that access fields past $19 (e.g., AnimateSprite needs anim_table at $28).
**When ready:** After SST field audit determines which fields effects actually need. May be unnecessary if SST shrinks enough overall.

### Pack collision_resp + width + height for Single-Longword Init (§3)
**Blocked by:** SST field audit + Load_Object init path performance pressure
**Source:** TheBlad768's S.C.E. and S1-in-S3 collision refactors (`d1e24ee` / `05512e4`) put `collision_type`, `collision_height`, `collision_width` adjacent so spawn init can do `move.b d0,collision_type(a0); swap d0; move.w d0,collision_height(a0)` — three bytes initialized from one ROM longword. Currently `collision_resp` is at $0F and `width_pixels`/`height_pixels` at $18-$19, so they need separate fetches.
**What:** Reorder SST so the type byte is adjacent to the width/height pair (or move both into the $0E neighborhood). Lets objdef tables emit `dc.b coltype, colh, colw, pad` and Load_Object init reads them in one `move.l`. Rough estimate: ~10-20 cycles saved per spawn × spawn frequency. Not free — reorder breaks the current $00-$19 "shared-prefix" boundary that we may want for a future $20 effect SST, so these two items must be evaluated together.
**When ready:** During SST field audit, alongside the effect-pool decision.

### Object Data Macros (`subObjData` family) (§3)
**Blocked by:** Objdef format finalization (currently still raw `dc.b`/`dc.l` in `data/objdefs/test_objects.asm`)
**Source:** S.C.E.'s `subObjData frame,coltype,(colh/2),(colw/2)` macro hides the field layout behind a named-parameter call so reordering SST fields doesn't ripple through every object table. Same idea for child priority data, animation script entries, etc.
**What:** Once the objdef format is stable, wrap the byte/word emission in `function`-and-macro pairs that take semantic args (`coltype`, `colh`, `colw`, `frame`, `priority`, ...) rather than positional bytes. Uses our `function` for any /2 or shift conversion, `struct`/`endstruct` patterns where appropriate. Pure ergonomics — zero runtime cost, but it's the difference between objdef tables that read like data and ones that read like a binary blob.
**When ready:** When more than 2-3 objects exist and the objdef format stops churning.

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

### §4.6 visual artifacts blocked on root-cause of state clobber

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

### Parallax_Current_Config / Camera_Y intermittent clobber (§4.6) — investigation
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

## From Sound Driver Work (Future)

### Defensive Z80 RAM Upload — Verify-and-Retry
**Surfaced during:** Ristar disassembly deep-dive (2026-04-27). Source:
`ristar_disasm/code/disasm.asm` lines 8330–8350 (`$641A` upload routine);
analysis in `ristar_disasm/ANALYSIS.md` § "Sound architecture (CONFIRMED)".
**Blocked by:** Flamedriver design / sound driver implementation.
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

**When ready:** When we implement Flamedriver upload (`engine/z80_init.asm`
or wherever the driver-bytes copy lives). Wrap each Z80 byte write with
the read-back-verify retry loop. ~30 extra lines of asm.
**Why bother:** Cheap insurance against a real-but-rare bug class. Most
runs will hit `.ok` on the first try; the retry only fires when the bus
is contended (probably never on most hardware revisions, but the cost is
~zero when it doesn't fire). Catches write-loss before it manifests as
silent driver failure or audio glitches that are nearly impossible to
debug after the fact.
**See:** `ristar_disasm/ANALYSIS.md`, `ristar_disasm/code/disasm.asm`
lines ~8330–8350.

---

## How to Use This Document

When starting a new planning phase:
1. Read through deferred items
2. Check if any blockers are now resolved
3. If so, include the deferred work in the new plan
4. Move completed items to a "Done" section at the bottom (with the date and the system that unblocked them)

---

## Done

### §2 Phase 2 Layer A.5 T1 — Per-Section Background (Zone-Shared Tier) — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.5 (T1 only — T2/T3 fixtures deferred, see new entry below)
**What:** Plane B per-zone background art end-to-end. New shared-region VRAM block at slots 1280-1535 ($A000-$BFFF, 8 KB) reserved for BG tiles permanently — never overwritten by section transitions. Build tool extended: `load_bg_layout` parses OJZ_1.bin's BG section (16 chunk-rows × 128 cols), `build_bg_nametable_words` samples a 64×32 region, `emit_bg_tile_blob` dedupes + emits `bg_tiles.bin` with a 2-byte length header, `emit_zone_bg_layout` rewrites tile-index fields into the shared region (BG_TILE_BASE_SLOT + canon_idx). `chunk_get_tile_word` now honours chunk-entry X/Y flip flags (bits 10/11 per sonic_hack ProcessAndWriteBlock) — a latent bug uncovered during BG visual diff. Engine: new `engine/level/bg.asm` with `BG_Init` (loads BG tile blob to $A000 + blits zone nametable to Plane B at $E000, both blocking VDP DATA-port writes wrapped in stopZ80/startZ80) and `BG_RedrawForSection` (T2/T3-ready, called from teleport handlers; T1 sections with NULL `sec_bg_layout` skip). New struct fields: Sec.sec_bg_layout (replaces dead sec_strips_b placeholder, $1C, longword), Act.act_bg_layout ($16, longword), Act.act_bg_tiles ($1A, longword), Act struct $1A → $1E. Test scaffold loads dual palette: Pal_BGND (SonicAndTails, CRAM line 0) + Pal_OJZ (CRAM lines 1-3) matching sonic_hack's runtime layout.
**OJZ measurement:** 218 unique BG tiles (well within 256-slot capacity), bg_tiles.bin = 6978 bytes, zone_bg.bin = 4096 bytes, ROM cost ~11 KB. Engine cost: ~1.5 ms blocking at level init (display off), zero per-frame. Drop of 212 KB ROM elsewhere from removing the placeholder strips_b BINCLUDEs.
**Verified visually in Exodus:** Plane B renders OJZ's authentic cloud band (top) + sky transition + grass band (bottom) with magenta/pink/green palette colors, matching sonic_hack's Level_OJZ1_BG reference structure (image-9-style).
**Architectural fix vs spec:** §2.4's "T1 shares FG tiles, zero VRAM cost" claim was unworkable with A.3's per-section graph-colored FG pool — slots 0-1279 swap on every section transition, so BG nametable references can't reliably use them. The shared 256-slot region is the correct architectural fit. See `docs/research/per-section-background.md` Q5.
**See:** `docs/research/per-section-background.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.4 — Per-Section Deferrable Streaming — 2026-04-26
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
