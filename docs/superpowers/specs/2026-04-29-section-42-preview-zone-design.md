# §4.2 Preview-Zone Design

**Date:** 2026-04-29
**Branch target:** `feat/section-42-preview-zone` (from `master` at `0b8af3a`, tag `checkpoint/pre-teleport-refresh`)
**Status:** Spec — pending implementation plan

## Background

The visible "warp at teleport" has two cooperating causes:

1. **Plane B tear.** `BG_RedrawForSection` performs ~25-30k cycles of direct VDP pokes during *active display* on every section transition. The top-down sweep visible at teleport is the raster racing the rewrite.
2. **Plane A art-shuffle.** Block-style slot rotation flips the slot tile bases at teleport, but plane A still references the previous section's nametable indices for ~3 frames until streaming overwrites at 1-2 cols/frame. During that window, nametable refs resolve against the *new* section's VRAM = wrong art shuffling visibly.

A failed prototype (burst-fill writing 41 cols at teleport) confirmed empirically that "do all the writes faster" doesn't solve it — the drain is too long for one VBlank and spills into active display, producing a different warp shape.

The architectural fix has been documented since §4.1 of `ENGINE_ARCHITECTURE.md` ("preview columns/rows copied at boundary edges for seamless visual transition") but never implemented for nametable rendering. Entities already use the equivalent (§4.9 warp-based preview); this spec extends preview to plane A and plane B nametables.

## Goals

- Eliminate the visible warp at FWD teleport (plane A art-shuffle + plane B tear).
- Eliminate the visible warp at BWD teleport (symmetric coverage).
- Replace `BG_RedrawForSection` with per-frame plane B streaming — no VDP writes during active display, by construction.
- Reserve plane geometry now (4-col edges + 4-row edges + 4×4 corners) so the eventual 2D-streaming work doesn't require re-architecting preview.

## Non-goals (deferred to follow-up specs)

- **Landing-flag mechanism** (proper teleport-position handoff). Blocked on player physics.
- **BWD teleport landing-position decision.** Preview-zone may make this moot; revisit during implementation.
- **`SECTION_SHIFT $0FFF` vs `$0800` reconcile.** Independent stopgap; out of scope.
- **2D-streaming diagonal-corner trigger logic.** Geometry reserved here; logic in the 2D-streaming spec.
- **Vertical preview implementation.** Routine stubs and geometry reserved; vertical streaming follow-up will populate.

## Approach summary

Preview is **nametable-only** edge regions on both planes. Nametable cells in the preview regions reference tile art already resident in the slot pair's existing VRAM allocation — no extra art VRAM is allocated. Preview copies are dedicated one-shot routines (mirroring sonic_hack's `Section_CopyPreview` family), fired when the source section's art finishes loading and at teleport. The streaming engine itself is unchanged; preview is a separate, surgical mechanism.

## Architecture & geometry

**Plane A** (world tile-col coordinates):

```
world cols:    [60-63]  [64 ........ 319]  [320 ........ 575]  [576-579]
                BWD-pre   slot L (Sec N)     slot R (Sec N+1)    FWD-pre
                4 cols    256 cols           256 cols            4 cols

vertical:      [rows 60-63]  rows 64-X (slot L+R area)  [rows X+1..X+4]
                TOP preview                              BOT preview
                (reserved)                               (reserved)
```

Plane A is 64×64 tiles. World→plane is wraparound (`world_col mod 64`).

**Plane B**: identical geometry — 4-col / 4-row edges + 4×4 corners reserved.

**Preview width:** `PREVIEW_COLS = 4`, `PREVIEW_ROWS = 4` (= `PREVIEW_PIXELS = 32`, since 1 tile = 8 px). Matches sonic_hack's proven value; sized so populated preview is always ahead of typical Sonic camera-step rate.

**Preview cost (per plane):**
- Horizontal: 4 + 4 cols × ~28 visible rows × 2 bytes = ~448 bytes nametable
- Vertical: 4 + 4 rows × ~40 visible cols × 2 bytes = ~640 bytes nametable
- Corners: 4 × (4×4 cells) × 2 bytes = 128 bytes
- **Total per plane: ~1.2 KB nametable.** Both planes: ~2.4 KB.

**VRAM art impact: zero.** Preview cells reference whichever slot's art they need; no new "preview slot" allocation, no graph-coloring change, no impact on future 2D-corner art budget.

## Components

**New file:** `engine/level/preview.asm` — preview-copy routines.

| Routine | Source | Dest | Trigger |
|---|---|---|---|
| `Section_CopyFwdPreview` | leading 4 cols of Sec(N+2)'s strip in ROM | plane A cols 576-579 + plane B cols 576-579 | Sec(N+2) art preload completes |
| `Section_CopyBwdPreview` | trailing 4 cols of Sec(prev)'s strip in ROM | plane A cols 60-63 + plane B cols 60-63 | Teleport handler |
| `Section_CopyTopPreview` | bottom 4 rows of Sec_above's strip | plane A+B top preview rows | (stub — vertical follow-up) |
| `Section_CopyBotPreview` | top 4 rows of Sec_below's strip | plane A+B bottom preview rows | (stub — vertical follow-up) |
| `Section_CopyDiagonalPreview` × 4 | 4×4 corner cells | corner preview regions | (stub — 2D-streaming follow-up) |

Each copy enqueues two DMA descriptors (one per plane, into the Important tier) — source ROM, dest VDP nametable address. No CPU staging, no Layout-RAM intermediate.

**Modified files:**

- `engine/level/section.asm` — add dispatch from preload completion to `Section_CopyFwdPreview`; add teleport-handler call to `Section_CopyBwdPreview`. **Leave the streaming clamp at `section.asm:421` in place** — it is no longer the bug. Preview cols are populated by the copy routines, not by the streamer. The clamp remains the streamer's intended boundary.
- `engine/level/parallax.asm` (or wherever plane B redraw currently lives) — **delete `BG_RedrawForSection`**. Replace with per-frame plane B streamer that writes 1-2 BG cols/rows per frame through the DMA queue, riding the same camera-velocity trigger as plane A streaming.
- `engine/level/camera.asm` (or equivalent) — implement the `camera_min_x`/`camera_max_x` clamp toggle rule (see Camera clamps below).

## Data flow & timing

**Block-rotation cycle (FWD travel):**

```
T=0  LEVEL INIT
     Slot L = Sec0 art, Slot R = Sec1 art
     BWD preview cleared (Sec(-1) doesn't exist)
     FWD preview populated when Sec2 first preloads (mid-Sec1 traversal)

T=enter Sec1  (camera world col >= 320)
     Sec0 offscreen — slot L safe to overwrite
     ► Sec2 art preload begins into slot L

T=Sec2 preload completes
     ► FIRES: Section_CopyFwdPreview
       Writes Sec2's leading 4 cols into plane A+B cols 576-579
       Refs resolve to Sec2 art now resident in slot L

T=approach Sec1 right edge
     Camera shows last cols of Sec1 + first 4 cols of Sec2 seamlessly
     (No warp visible — bytes are correct on both sides of teleport)

T=teleport
     Camera world position rewinds by SECTION_SHIFT
     ► FIRES: Section_OnTeleport_Fwd
       (a) Section_CopyBwdPreview: writes Sec1's trailing 4 cols into plane A+B cols 60-63
           (refs resolve to Sec1 art still in slot R — not yet overwritten)
       (b) FWD preview cells NOT cleared. Plane wraparound makes the cells that
           held "Sec2 leading cols (FWD preview)" pre-teleport identical to the
           cells that hold "slot L start" post-teleport — same bytes, different
           world-coord labels. No action required.

T=midpoint of Sec2  (~85 frames after teleport)
     Sec1 still resident in slot R, fully offscreen behind camera.
     BWD preview region not visible (camera far past col 63).
     ► Sec3 art preload begins into slot R (overwrites Sec1)
     [BWD preview becomes stale here, but it's offscreen — no visible artifact.
      It will be rewritten at the next teleport before being visible again.]

T=Sec3 preload completes
     [No preview action — Sec3 is the new slot R "current," not a preview source.
      The next FWD preview (Sec4 leading) will fire when Sec4 lands in slot L
      mid-Sec3 traversal.]

[cycle repeats]
```

**Trigger summary:**

| Event | Action |
|---|---|
| Level init | Populate BWD preview from Sec(-1) if it exists, else zero-fill |
| Section preload completion (lands in slot L) | `Section_CopyFwdPreview` using new section's leading 4 cols |
| Teleport (FWD or BWD) | `Section_CopyBwdPreview` using just-left section's trailing 4 cols |
| Boundary clamp hit (no neighbor) | Zero-fill the relevant preview region (sonic_hack `cn-clearing fallback`) |

**Stale rule:**

- BWD preview becomes stale when slot R is overwritten (Sec3 preload mid-Sec2-traversal). It's offscreen at that moment and gets rewritten at the next teleport before camera can see it.
- FWD preview becomes stale when slot L is overwritten (Sec4 preload mid-Sec3-traversal). Camera is far from FWD preview at that moment; rewritten when the new source section finishes loading.

**BWD travel:** the same lifecycle inverted. `Section_OnTeleport_Bwd` mirrors `Section_OnTeleport_Fwd`.

## Camera clamps

`camera_min_x` and `camera_max_x` toggle based on whether the current pair has a neighboring section beyond the BWD/FWD preview region:

| Camera state | `camera_min_x` |
|---|---|
| Level start (`section_cur_X = 0`, no Sec(-1)) | `$200` (= world col 64; BWD preview unreachable) |
| Any post-teleport pair (`section_cur_X >= 2`) with valid Sec(prev) | `$200 - PREVIEW_PIXELS` (= world col 60; camera can scroll into BWD preview) |
| Returned to `section_cur_X = 0` via BWD teleport | back to `$200` |

Mirrored rule for `camera_max_x` at the level's far edge.

Per architecture doc §4.1, "boundary clamping is data-driven." Implementation: a flag on each section (or computed from grid neighbor presence in `Level_Section_Grid`) determines the clamp window per pair. The clamp updates at teleport.

## Plane B integration

**Today (deleted):**
- `BG_RedrawForSection` — direct VDP pokes during active display, ~25-30k cycles, top-down sweep visible.

**Replacement:**
- **Per-frame plane B streamer.** Writes 1-2 BG cols/rows per frame via the DMA queue (Important tier). Rides the camera-velocity trigger that drives plane A streaming.
- **Plane B preview copies.** Same routines as plane A (`Section_CopyFwdPreview` / `_CopyBwdPreview`) write into plane B preview regions in parallel. One DMA descriptor per plane, queued together.
- **No teleport-time burst.** At teleport, plane B's BWD preview is recopied (~224 bytes — fits trivially in VBlank). FWD preview unchanged at teleport (plane wraparound). The body of plane B is already correct from prior streaming.

**Plane B BG art region unchanged.** BG tile art lives at VRAM slots 1280-1535 (`$A000-$BFFF`) per architecture doc §A.3 / T1 — loaded once at level init, never overwritten. Plane B nametable refs always point into this fixed range.

**Per-section BG variation.** Sections that change BG (`sec_bg_layout` per-section field, §4.2) work via the streamer reading from whichever section's BG strip is active for the current camera column. Preview copies follow the same per-section logic.

**The tear is gone by construction:** there is no longer any code path that writes plane B during active display. All writes go through DMA at VBlank only.

## Architecture doc updates

After this spec lands, update:

- **§4.1 step 2 — preview specifics.** Add: "Preview width is 4 cols / 4 rows. Preview cells reference resident slot art; no extra VRAM allocated. Copies fire on source-section preload completion (FWD) and at teleport (BWD)."
- **§4.4 Deferred Plane Buffer.** Add: "Plane B never writes during active display. The legacy `BG_RedrawForSection` burst is removed; plane B uses per-frame streaming + preview copies, identical to plane A."
- **§4.5 Camera System (or §4.1 if clamps live there).** Add the camera-clamp toggle rule for preview accessibility — `camera_min_x = $200` when at level start, `$200 - PREVIEW_PIXELS` otherwise; mirrored on max.

The doc updates ship as part of this spec's branch, not as a follow-up — keeps doc and code in sync per project policy.

## Testing & verification

**Primary success criterion:** scrolling FWD across multiple teleport boundaries shows no perceptible warp, shuffle, or tear. Verified via Exodus screen-recording + frame-step at teleport moments — adjacent frames must show byte-identical content in the camera-visible region except for the single column of true new content streamed that frame.

**Verification steps:**

1. **Plane A preview content (Exodus VRAM read).** At T_pre (Sec(N+2) art finished loading): read plane A nametable at FWD preview region; verify cells contain expected nametable indices for Sec(N+2)'s leading 4 cols. Repeat for BWD preview after teleport.

2. **Plane B no-burst regression.** Confirm `BG_RedrawForSection` is removed (grep the binary). Set Exodus watchpoint on its former entry address — must never fire. Read `VDP_Status` periodically during active display; verify no VDP writes outside VBlank.

3. **Camera clamp behavior.**
   - First pair (`section_cur_X = 0`): camera at world col 64 → can't go further left.
   - Post-teleport pair (`section_cur_X = 2`): camera at world col 64 → scrolls to col 60.
   - BWD-teleport back to `section_cur_X = 0`: clamp re-engages at col 64.

4. **Boundary cases.** Test ROM with no FWD neighbor in last pair: preview region zero-filled. Test BWD at level start: preview region zero-filled.

5. **Direction reversal near boundary.** Player reverses at world col 65 (1 col into slot L, BWD preview already populated): camera scrolls into BWD preview cols 60-63 without artifacts. Reverses again: FWD scroll continues normally.

6. **DMA budget.** Exodus profiler — confirm preview-copy DMA descriptors fit in the Important queue tier without crowding existing DMA traffic. Per-teleport preview cost: ~448 bytes (BWD recopy on both planes). Should land well under per-frame budget.

7. **Long-run soak.** Camera scripted across 20 sections (10 teleports). No VRAM/RAM leaks, no DMA queue overflows, no growing frame-time.

8. **Visual sanity.** Load test ROM in Exodus, scrub frame-by-frame across teleport, confirm by eye no seam / shuffle / tear is visible.

## Open follow-up specs (post-merge)

These are deferred items (per memory `project_section_42_preview_zone_brainstorm.md`) that this spec does not address but is compatible with:

1. **Landing-flag mechanism** — proper teleport-position handoff (replaces SECTION_SHIFT-nudge stopgap). Blocked on player physics.
2. **BWD teleport landing-position decision** — revisit after preview-zone is in place.
3. **`SECTION_SHIFT` $0FFF → $0800 reconcile** — independent stopgap.
4. **Vertical preview implementation** — populate the `Section_CopyTopPreview` / `_CopyBotPreview` stubs reserved here.
5. **2D-streaming diagonal-corner trigger logic** — populate `Section_CopyDiagonalPreview` stubs; corner geometry already reserved.
6. **`Section_UpdateColumns` ring-buffer math overhaul** — overlaps partially with this spec; remaining work tracked separately if any.
