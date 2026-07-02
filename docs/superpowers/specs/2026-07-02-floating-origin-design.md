# Floating Origin (Continuous-Scroll Phase 4) — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02); pending spec review
**Extends:** `2026-06-22-continuous-scroll-traversal-design.md` §9 (the approved sketch —
this spec promotes it, corrects it, and completes it)
**Design-week queue:** #2 of 5 (`docs/superpowers/2026-07-02-design-week-queue.md`)

---

## 1. Goal

Remove the ~16-sections-per-axis coordinate ceiling: level size bounded by ROM only.
Mechanism (user-ratified): **atomic floating-origin rebase** — when the fine camera
nears the signed-word ceiling, one owner routine shifts every live world coordinate
by a fixed delta in one frame and counts the shift in a base counter. The engine
runs on 16-bit fine coordinates between rebases, unchanged.

The modulo/toroidal alternative (S3K's shipped `Screen_Y_wrap_value` masking) was
researched and REJECTED: it is a permanent every-comparison convention (one stray
`cmp.w` = a seam bug with the worst reproduction profile), requires power-of-2 world
sizes (conflicts with arbitrary `grid_w × grid_h`), and still needs a base counter
for respawn keys. Two of its ideas are adopted tactically (§6).

**Companion decision (user-ratified): `section_id` widens byte→word** in this design
(byte caps a level at 256 sections total).

## 2. Coordinate model

Per axis: `absolute = World_Section_Base × SECTION_SIZE + fine`.
- `World_Section_Base_X` / `World_Section_Base_Y`: two RAM words, the only new
  steady-state state. Zero at level init.
- *fine* = every existing 16-bit coordinate (camera, SST positions, ring buffer,
  cache cursors). Nothing about their format changes.
- ROM data is finite ⇒ the grid is finite ⇒ absolute section ids are unique for the
  level's lifetime. No epoch machinery.
- Floating-origin compatibility with art-streaming Phase 2 was designed in there:
  residency keys off cache content, not coordinates.

## 3. REBASE_DELTA — per-act, per-axis, build-derived (the §9 correction)

**§9's claim "a multiple of SECTION_SIZE is automatically plane-aligned" is FALSE**
(and §9's `SECTION_SIZE=$1000` was stale — it is `$0800`, `constants.asm:309`).
Parallax band scroll = `camera >> band_shift`; a rebase shifts each band by
`DELTA >> band_shift`, visible unless that is ≡ 0 (mod 512). OJZ's 1/16 band
(`FACTOR_1_16`, `ojz_default.asm`) would jump 128 px under a one-section delta.

**Rule:** `REBASE_DELTA_axis = max(SECTION_SIZE, 512 << slowest_band_shift_axis)`
— powers of two, so the max satisfies both constraints (whole sections for the base
counter; plane alignment for every band, FG trivially included). OJZ act 1:
`REBASE_DELTA_X = $2000` (4 sections), `REBASE_DELTA_Y = $1000` (2 sections;
`vFactorBg = 3`). **Build-time assert co-located with each act's parallax config**:
every band's `DELTA >> shift` ≡ 0 (mod 512) — a future slower band fails the build,
never ships a visible rebase. Plane B is a load-once wrapping 64×64 nametable
(`bg.asm:74-87`) — an aligned shift needs **no redraw** (mod-512 invariant, already
documented at `bg.asm:95-98`).

Derived-value invariants (all follow from delta = whole sections): multiple of 16 px
⇒ `Cache_Top_Row` even-parity holds; multiple of 512 ⇒ Plane A mapping invariant;
whole sections ⇒ fine section-derive shifts by exactly `DELTA/SECTION_SIZE`.

## 4. Trigger

- Down-shift: `fine_camera ≥ REBASE_THRESHOLD` (`$6000`) → subtract `REBASE_DELTA`,
  base += `DELTA/SECTION_SIZE`.
- Up-shift (backward travel): `fine_camera < REBASE_DELTA` AND base > 0 → add
  `REBASE_DELTA`, base −= `DELTA/SECTION_SIZE`.
- Hysteresis is inherent: post-shift the camera sits ≥ `$4000` from either trigger.
- **Assert:** `REBASE_THRESHOLD + max_frame_displacement < $8000` and
  `REBASE_THRESHOLD − REBASE_DELTA > REBASE_DELTA` (the two triggers cannot chatter).
  Max frame displacement includes any future teleport-like mechanic; today it is
  `CAM_MAX_X_STEP`/`CAM_MAX_Y_STEP`.
- Checked once per frame per axis at the atomic point (§5). Both axes may rebase the
  same frame independently.

## 5. The shift event — one owner, atomic, audited

**Placement (audit-verified):** immediately **after `Camera_Update`, before
`Tile_Cache_Fill`** (frame order per `ojz_scroll_test.asm:149-261` and the real level
loop): positions and camera are final, no world-derived consumer has run — every
downstream system sees rebased coordinates within the same frame; rendering never
observes mixed state.

**`Rebase_Execute` (per axis; delta and field offsets parameterized) — the complete
shift-list (2026-07-02 audit, supersedes §9's list):**
1. Quiesce partial fills: force `Cache_Fill_Resume_Col/_Row` and
   `Cache_Fill_RowResume_Row/_Col` to `$FFFF` (nothing mid-flight to shift).
2. Invalidate block staging: `TileCache_InvalidateStaging` (`Block_Stage_Keys` are
   fine-sec-keyed and go stale).
3. Shift by DELTA (pixels; 16.16 highword where applicable):
   - `Camera_X`/`Camera_Y` (16.16 long),
   - every SST `x_pos`/`y_pos` across `Object_RAM → Object_RAM_End` — **all three
     slot arrays** (Dynamic/System/Effect) + `Player_1`; stride `SST_len`, skip
     `code_addr == 0`,
   - `Ring_Buffer`: **X and Y** words per entry (count `Ring_Count`),
   - world tile cursors by `DELTA/8`: `Cache_Left_Col`, `Cache_Head_Col`,
     `Cache_Top_Row`, `Cache_Bottom_Row`, `Cache_Prev_Cam_Row`,
     `Section_Right/Left_Col_Written`, `Section_Top/Bottom_Row_Written`,
   - `Camera_Y_Coarse_Prev` (masked reseed from the rebased `Camera_Y`).
   - **NOT shifted:** `Cache_Origin_Col/Row` (physical ring indices), sub-pixel
     fractions (delta is whole pixels), velocities (never rebased — KSP lesson),
     respawn/collected memory (section-id-keyed, invariant), static ROM data.
4. Reseed `Parallax_Prev_Sec_X/Y` to `$FF` → forces one clean config re-select
   through the base-aware lookup (the audit's wrong-parallax-config bug).
5. `World_Section_Base_axis ± DELTA/SECTION_SIZE`.
6. `EntityWindow_BuildEntries` — rebuilds anchor/origins/`ess_*` from the rebased
   camera (derived state is re-derived, never hand-shifted).

**DEBUG audit (runs after every rebase):** every live world coordinate ∈
`[0, REBASE_THRESHOLD)`; staging keys empty; entity-window entries consistent with
the camera; `RaiseError` on any violation. New world-coordinate RAM fields added in
the future MUST be registered in the shift-list — the routine header carries this
contract, and the audit walk is the enforcement net.

## 6. Absolute-section lookups & tactical adoptions

`+World_Section_Base` enters at the **seven audited world→section site clusters**
(grid helpers `Section_FlatIDXY`/`Section_GetSecPtrXY` stay base-agnostic; callers
add the base): parallax boundary check, Plane-B redraw lookup, entity-window
derive/init/slide (3), tile-cache block-dict lookups (fill + prefetch), and the
active-section diagnostic.

Adopted from the research (tactical, not architectural):
- **Signed-difference compares** (RFC 1982 idiom, `sub.w` + sign branch) at hot
  live-vs-live position sites (touch response, entity distance checks) — valid
  unconditionally given ≤2-screen live separation, and makes each site
  rebase-agnostic outright.
- **Single-owner shift routine + audit walk** (the Unity `onShift` broadcast lesson,
  §5).

## 7. section_id byte→word widening

All section-id carriers widen to word; `SEC_VOID = $FF → $FFFF`:
- `Ring_Buffer` entry 6→8 bytes: `{x.w, y.w, section_id.w, list_index.b, pad.b}`
  (`RING_BUFFER_ENTRY_SIZE`, `rings.asm` producers/consumers),
- SST `entity_section_id` byte→word (SST $2A-$2D metadata block relayout — the
  packed fields and `sst_custom` base move; every consumer re-anchored via the
  struct, plus the `SST_slot_tag` bit-7 OEF_ANY_Y mirror stays),
- respawn/collected/killed keys (`Collected_*`/`Killed_*` take `d0.w`),
- entity window: `Entity_Window_Center_ID`, `Entity_Window_Anchor`,
  `ess_section_id`,
- `Section_FlatIDXY` returns a word.
Lands as one coherent format change (own phase, §9), verified by the existing
respawn/collection behavior tests.

## 8. What this does NOT touch

Layout/collision/entity ROM formats (section-local, build-enforced); the streaming
engine's fill logic (only its cursors shift); parallax math (only its prev-section
bytes reseed); sound; player physics; art-streaming Phase 2 (position-independent
by design). The deferred `EDGE_WRAP_V` edge mode is the second consumer of
`Rebase_Execute` (same shift applied modulo at the level edge) — noted, not built.

## 9. Phasing

- **F1 — Rebase machinery.** Base counters, delta derivation + asserts, trigger,
  `Rebase_Execute` + DEBUG audit, the seven lookup sites, force-rebase soak
  (DEBUG flag drops `REBASE_THRESHOLD` to 2 sections) on stock OJZ.
- **F2 — section_id widening.** The §7 format change, isolated and verified.
- **F3 — Wide-grid fixture + acceptance.** A fixture act descriptor repeating OJZ's
  section pointers 24× horizontally (pure data — sections are pointers; no new art):
  real >16-section traversal. Acceptance: sustained max-scroll circuits across many
  rebases, both directions, both axes; **pixel-identity across rebase frames**
  (oracle screenshots straddling a rebase differ only by normal scroll advance);
  respawn/collected memory correct across the full run; `Lag_Frame_Count` unchanged
  (the event is a few hundred cycles, once per ~4 sections of travel).

All engine-tagged (design-#5 input) except the F3 fixture data.

## 10. Risks & open parameters

- **Shift-list completeness** — the one real hazard (a missed field fails silently,
  later). Mitigations: single owner, DEBUG audit walk, force-rebase soak, the
  routine-header contract for future fields. The dead-but-reserved camera fields
  (`Pos_table`, `H_scroll_frame_offset`, `Camera_Lookahead`, `Camera_Pan_Offset`)
  are inert today; if ever wired they join the list (header note covers them).
  Design #3 (Tails position-history ring) must register its buffer when built.
- **`REBASE_THRESHOLD = $6000`** — tunable; only constraint is the §4 asserts.
- **Both-axes-same-frame** — two sequential per-axis executes; the audit runs after
  both.
- **Debug ergonomics** — oracle/debugger show fine coords; the section diagnostic
  becomes base-aware (site #7). Absolute position when needed = base × `$800` +
  fine (documented in the debugger notes).

## 11. Research provenance

Three-agent pass, 2026-07-02: (a) aeon coordinate-consumer audit — complete
shift-list with file:line, signedness map (`asr` derives + signed clamps set the
ceiling), parallax alignment table, the five §9 gaps; (b) web — KSP/Unreal/Unity
origin-shifting (integer base + local coords validated; position/velocity split;
single-owner broadcast pattern; trigger-vs-max-speed guard), RFC 1982 signed-
difference arithmetic, Thorne taxonomy; negative result: no 16-bit-era game
exceeded $8000 px (S3K's wrap-at-32767 is a shipped glitch, not a feature);
(c) reference disassemblies — S2/S3K/S.C.E. toroidal Y-wrap documented in full
(modulo masking, power-of-2 periods, `-$100` sentinel), no rebase mechanism
anywhere in the corpus.
