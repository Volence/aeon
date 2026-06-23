# Continuous-Scroll Traversal — Phase 2 (Vertical + Edge Modes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make vertical scroll fully continuous (camera reaches the bottom section row of the 3×3 grid), with a configurable per-act vertical edge behavior (clamp / vertical-wrap / kill-stub).

**Architecture:** Phase 1 already did the hard parts — continuous `Camera_Y`, world-row tile-cache fill (unbounded, up/down eviction, cross-frame resume), ring-wrap plane writes (`world_row & 63`), world-derived entity window, `Player_LevelBound` already computing `grid_h*SECTION_SIZE − SCREEN_HEIGHT`. Research confirmed the "garbage beyond plane row 47" was a *stale comment*, not a layout constraint (plane is 64×64, SAT relocated to `$B800` freeing rows 48-63). So Phase 2 is **unlock + verify** plus the **edge-mode** feature: lift the Y clamp (grid-derived), add `edge_mode` (CLAMP default / WRAP_V / KILL-stub), verify full-height + diagonal streaming on device.

**Tech Stack:** AS Macro Assembler (68000), `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`, oracle emulator (MCP) for runtime verification.

**Branch:** create `feat/continuous-scroll-vertical` off master (Phase 1 is merged). Spec: `docs/superpowers/specs/2026-06-22-continuous-scroll-traversal-design.md` §10.

**Verification model:** the bulk of Phase 2's value is the on-device gate (Task 6). Code tasks 1–5 each build clean; correctness is confirmed at the gate. The riskiest item is the **zero-slack vertical streaming contract under diagonal motion** (`CAM_MAX_Y_STEP=16 == VFILL_ROWS_PER_FRAME×8`, H+V fills share `BLOCK_DECOMP_BUDGET=6`).

---

## File structure (Phase 2 touches)
- `engine/level/camera.asm` — Y clamp → grid-derived; edge-mode dispatch at the bottom/top edge.
- `data/levels/ojz/act1/act_descriptor.asm` + `structs.asm` — delete `cam_min_y/cam_max_y`; add `edge_mode` field.
- `constants.asm` — `EDGE_CLAMP`/`EDGE_WRAP_V`/`EDGE_KILL` enum.
- `engine/level/section.asm` (or a new small `edge.asm`) — `EDGE_WRAP_V` live-set shift routine; `EDGE_KILL` hook stub.
- `engine/player/player_common.asm` — `Player_LevelBound` bottom: dispatch on edge_mode (clamp vs wrap-handled-elsewhere vs kill-hook).
- `engine/level/parallax.asm`, `docs/ENGINE_ARCHITECTURE.md` — remove stale render-safety comment; sync VRAM diagram.

---

## Task 0: Branch + baseline (prove the under-fill hypothesis)

**Files:** none (setup + oracle).

- [ ] **Step 1: Branch.** `git checkout -b feat/continuous-scroll-vertical master`. (Carries the pre-existing WIP harmlessly.)
- [ ] **Step 2: Baseline VRAM dump.** Build current master, reload in oracle, scroll to the bottom of the *current* (2-section) clamp, and `emulator_read_vram` Plane A rows 48-63 (`$C000 + 48*128 = $D800` … `$DFFF`). Expected: stale/zero data (proves rows below the clamp were never streamed — the under-fill hypothesis). Record it.

---

## Task 1: Lift the Y clamp — grid-derived full-height

**Files:** Modify `engine/level/camera.asm` (the `.clamp_y` block), `data/levels/ojz/act1/act_descriptor.asm`, `structs.asm`.

Current `.clamp_y` (from Phase 1) bounds via `Act_cam_min_y`/`Act_cam_max_y` + a camera-derived `sec_y`. Make it grid-derived (symmetric with the X clamp), and delete the descriptor's Y-bound fields.

- [ ] **Step 1: Read the live `.clamp_y` block** in `engine/level/camera.asm` (the `sec_y = Camera_Y>>SECTION_SIZE_SHIFT`, top-row `Act_cam_min_y`, bottom-row `Act_cam_max_y` logic).
- [ ] **Step 2: Rewrite the Y clamp to grid-derived** `[0, grid_h*SECTION_SIZE − SCREEN_HEIGHT]`, mirroring the X clamp's `moveq #0,d1 / move.w Act_grid_h(a0),d1 / lsl.l #8 / lsl.l #3 / subi.w #SCREEN_HEIGHT,d1` (min = 0). Keep the deadzone Y follow + spindash freeze unchanged. Remove the `Act_cam_min_y`/`Act_cam_max_y` reads.
- [ ] **Step 3: Delete the descriptor Y-bound fields.** Remove `cam_min_y` + `cam_max_y` from the `Act` struct (`structs.asm`) and the two `dc.w` lines in `act_descriptor.asm` (now nothing supplies camera bounds — fully grid-derived, symmetric with X). Update the `Act_len` assert.
- [ ] **Step 4: Build.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -4` → exit 0.
- [ ] **Step 5: Quick oracle check.** Reload; press Down; confirm `Camera_Y` now advances past the old 2-section limit toward `grid_h*SECTION_SIZE − SCREEN_HEIGHT` (3×2048−224 = `$1720`), and rows 48-63 now stream valid data (re-dump VRAM `$D800`+). Commit: `git commit -m "feat(traversal): lift camera Y clamp to grid-derived full height"` (+ trailer).

---

## Task 2: `edge_mode` field + dispatch scaffold (CLAMP default)

**Files:** `constants.asm`, `structs.asm`, `data/levels/ojz/act1/act_descriptor.asm`, `engine/level/camera.asm` (or `engine/player/player_common.asm` bottom-bound).

- [ ] **Step 1: Add the enum** in `constants.asm`: `EDGE_CLAMP = 0`, `EDGE_WRAP_V = 1`, `EDGE_KILL = 2`.
- [ ] **Step 2: Add the `edge_mode` field** to the `Act` struct (`structs.asm`, a `ds.b 1` — reuse a reserved/pad byte or extend; update `Act_len` assert) and set it in `act_descriptor.asm` to `EDGE_CLAMP` for OJZ Act 1.
- [ ] **Step 3: Add the dispatch scaffold** where the bottom edge is handled (the Y clamp / `Player_LevelBound` bottom). Read `Act_edge_mode(a0)` and branch: `EDGE_CLAMP` → the existing clamp (Task 1); `EDGE_WRAP_V` → (Task 3 routine, stub `nop`/fall-through for now); `EDGE_KILL` → (Task 4 hook, stub for now). Keep CLAMP behavior identical to Task 1.
- [ ] **Step 4: Build + commit.** `./build.sh` exit 0; oracle: CLAMP behavior unchanged from Task 1. `git commit -m "feat(traversal): per-act vertical edge_mode field + dispatch (CLAMP default)"` (+ trailer).

---

## Task 3: `EDGE_WRAP_V` — vertical wrap (fall-forever)

**Files:** `engine/level/section.asm` (or new `engine/level/edge.asm`), wired from the Task 2 dispatch.

Mechanism: when the player crosses the bottom (`Player_1.y_pos >= level_height`) wrap by `−level_height`; crossing the top (`< 0`) by `+level_height`. `level_height = grid_h*SECTION_SIZE` is a multiple of the 512px plane → plane-aligned → seamless. Shift the **live set** atomically (the same shift-list as the floating-origin §9, on Y): `Camera_Y`, `Player_1.y_pos`, every active object `y_pos` (walk Object_RAM/Dynamic_Slots), every active ring `engine_Y` (walk Ring_Buffer), and the cache vertical cursors (`Cache_Top_Row`/`Cache_Bottom_Row`/`Cache_Prev_Cam_Row`) by `±level_height/8` (preserve the `Cache_Top_Row` even parity — `level_height/8` is a multiple of 256, even). Then re-derive the vertical window (re-run the vertical part of `EntityWindow`/`BuildEntries`) so origins recompute from the wrapped camera.

- [ ] **Step 1: Read** the floating-origin shift-list (§9) + the active-object walk pattern (Object_RAM stride, `Ring_Buffer` stride) — confirm the iteration the audit described.
- [ ] **Step 2: Write `Edge_WrapV`** — compute `level_height = grid_h << SECTION_SIZE_SHIFT`; on bottom-cross subtract it from the live-set Y fields (camera, player, active objects, active rings, cache cursors), on top-cross add it; then re-derive the entity window. Atomic within the frame.
- [ ] **Step 3: Wire** the Task 2 `EDGE_WRAP_V` dispatch to call `Edge_WrapV` (replacing the stub).
- [ ] **Step 4: Build.** `./build.sh` exit 0.
- [ ] **Step 5: Test on oracle.** Temporarily set OJZ Act 1 `edge_mode = EDGE_WRAP_V`; drive the player Down past the bottom; confirm it wraps to the top at the same X with **no visible jump** (`Camera_Y` jumps by `level_height` but the screen is identical — plane-aligned), and content/collision are correct after the wrap. Revert OJZ to `EDGE_CLAMP` for the production verification (keep WRAP_V as a tested capability). Commit: `git commit -m "feat(traversal): EDGE_WRAP_V vertical wrap (fall-forever) via live-set shift"` (+ trailer).

---

## Task 4: `EDGE_KILL` — deferred death-pit hook (stub)

**Files:** the edge dispatch + a hook stub.

- [ ] **Step 1: Add the `EDGE_KILL` hook.** In the dispatch, `EDGE_KILL` sets a `Player_Death_Pending` flag (new RAM byte) when the player crosses the bottom, and **falls through to clamp** meanwhile (so the player doesn't fall off into void with no death system). Add a clear comment: "wired to the death system when it exists (no death system yet — clamps + flags for now)."
- [ ] **Step 2: Build + commit.** `./build.sh` exit 0. `git commit -m "feat(traversal): EDGE_KILL hook stub (death-pending flag; clamps until death system)"` (+ trailer).

---

## Task 5: Remove stale render-safety comment + sync docs

**Files:** `engine/level/parallax.asm`, `docs/ENGINE_ARCHITECTURE.md`.

- [ ] **Step 1: Remove the stale comment** at `parallax.asm:488-492` ("FG_V_scroll exposes plane rows beyond row 47 / sprite table region as garbage") — it describes the pre-relocation layout. Replace with an accurate note (FG vscroll = `Camera_Y`; the cache fills all 64 rows; SAT is at `$B800`).
- [ ] **Step 2: Sync the VRAM diagram** in `docs/ENGINE_ARCHITECTURE.md` (the ~§2.3 region map): rows 48-63 are normal Plane A nametable rows; SAT at `$B800`; "Region 2" is gone. Note `edge_mode` (clamp/wrap/kill) in the traversal section.
- [ ] **Step 3: Build (sanity) + commit.** `git commit -m "docs(traversal): drop stale row-47 render-safety note; sync VRAM diagram + edge modes"` (+ trailer).

---

## Task 6: GATE — full-height vertical verification (oracle)

**Files:** none (verification). The core Phase-2 sign-off.

- [ ] **Step 1: Full-height reach.** Drive Down across all 3 rows; confirm `Camera_Y` reaches `$1720` (bottom clamp) and the **bottom-row unique art renders cleanly** (screenshot); VRAM rows 48-63 = valid nametable data.
- [ ] **Step 2: Diagonal stress (the zero-slack risk).** Drive diagonal (Down+Right) at sustained max speed across the sec0/1/3/4 corner; watch `Lag_Frame_Count` (profiler hides bursts) — H column-fill + V row-fill share `BLOCK_DECOMP_BUDGET=6`. Record the lag rate; confirm no pop-in/torn rows/columns.
- [ ] **Step 3: Bottom-boundary correctness.** At `sec_y = grid_h-1`, confirm the V prefetch honors `SEC_VOID` (no over-read past the grid), `Cache_Top_Row` stays even (collision parity), and the camera clamps correctly.
- [ ] **Step 4: WRAP_V spot-check.** (Optional, if not covered in Task 3) flip to `EDGE_WRAP_V`, confirm seamless fall-forever, revert.
- [ ] **Step 5:** If any check fails → systematic-debugging before proceeding. Record results.

---

## Task 7: Revisit `CAM_MAX_Y_STEP` (deferred speed bump — DO NOT SKIP)

**Files:** `constants.asm` (conditionally).

- [ ] **Step 1: Decision from the Task 6 stress data.** If the diagonal `Lag_Frame_Count` showed comfortable headroom, raise `CAM_MAX_Y_STEP` 16→24 **and** `VFILL_ROWS_PER_FRAME` 2→3 together (keep `CAM_MAX_Y_STEP ≤ VFILL_ROWS_PER_FRAME×8`), then re-run the Task 6 diagonal stress to confirm it still holds. If headroom was tight, keep 16 and record why. Either way, **make the call explicitly** (this is the tracked deferral from the design).
- [ ] **Step 2: Build + commit** (the change, or a note-only commit recording the keep-16 decision).

---

## Task 8: Merge

- [ ] **Step 1:** Confirm Task 6 gate green. Final whole-branch review (subagent). Then superpowers:finishing-a-development-branch → merge `feat/continuous-scroll-vertical` to master (local FF, as in Phase 1).

---

## Self-review

- **Spec coverage (§10):** render-safety-resolved → no rework (Task 1 lifts, no relayout) ✓; grid-derived Y clamp + delete descriptor bounds → Task 1 ✓; `edge_mode` CLAMP/WRAP_V/KILL → Tasks 2/3/4 ✓; stale comment + arch-doc → Task 5 ✓; verification (full-height, diagonal zero-slack, bottom-boundary, parity) → Task 6 ✓; `CAM_MAX_Y_STEP` revisit → Task 7 ✓ (explicitly "do not skip"). Floating-origin (Phase 4) correctly NOT in scope; WRAP_V shares its shift-list (noted).
- **Placeholders:** each code task gives the site + the precise change + the mechanism (WRAP_V shift-list is fully specified); implementers read live code per task (the Phase-1-proven pattern) for exact ASM. EDGE_KILL is explicitly a stub (death system absent) — a documented deferral, not a hidden TODO.
- **Consistency:** `grid_h << SECTION_SIZE_SHIFT` (split `lsl.l #8 + #3`) used for Y exactly as X; `level_height` term consistent across Task 1 (clamp) and Task 3 (wrap); `edge_mode` enum names consistent (Tasks 2/3/4); `EDGE_CLAMP` is the OJZ production value, WRAP_V tested then reverted.
- **Risk:** the diagonal zero-slack budget (Task 6 Step 2) is the real unknown; Task 7 is gated on its data. The WRAP_V live-set walk must be atomic-in-frame (Task 3) — same constraint as floating-origin.
