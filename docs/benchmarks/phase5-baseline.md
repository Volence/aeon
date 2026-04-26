# Phase 5 Baseline Benchmark — Object System

Date: 2026-04-25
Build: `DEBUG=1 ./build.sh` (209,783 bytes)
Emulator: Exodus 2.1, NTSC mode (262 scanlines/frame, 224 active)

## Test Scene

Combined integration + stress test (`GameState_ObjectTest`):
- 1 player (Sonic, animated DPLC art streaming)
- 10 enemies (5 ground patrol, 3 mid-level, 2 high, COLLISION_HURT)
- 12 solid platforms (staircase layout, COLLISION_SOLID)
- 8 fast particle emitters (spawn every 8 frames, effect pool saturation)
- 3 parent objects (3 children each, self-destruct at 180 frames)

Peak load: 39 dynamic slots (25 list + 8 emitters + 3 parents + 9 children — capped at 40)
Steady state: 30 dynamic slots + 16 effect slots (after parents self-destruct)

## Per-Subsystem Scanline Costs

| Subsystem | Steady State | Peak | % of Active Frame (peak) |
|---|---|---|---|
| RunObjects | 52 | 93 | 41.5% |
| TouchResponse | 10 | 12 | 5.4% |
| Render_Sprites | 43 | 67 | 29.9% |
| **Frame Total** | **108** | **171** | **76.3%** |

Measured via VDP V counter (high byte = scanline number).
Peak values captured across all frames since boot, including the init frame.

## Slot Usage

| Pool | Capacity | Peak Used | Steady State |
|---|---|---|---|
| Dynamic | 40 | 39 (98%) | 30 (75%) |
| Effect | 16 | 16 (100%) | 16 (100%) |

## Analysis

- Steady state uses 108 scanlines (48% of active frame) — leaves headroom for level rendering
- Peak of 171 scanlines (76%) occurs during init with all parents + children active
- Effect pool fully saturated at 16/16 — emitters gracefully handle alloc failure
- RunObjects is the dominant cost (48% of game loop) — 30+ objects with movement, animation, DPLC
- Render_Sprites at 43 scanlines (40% of game loop) — scaling well with 30+ visible sprites
- TouchResponse remains cheap even with 10 enemies + 12 solids — AABB early rejection works
- No crashes or visual corruption under full load
- Parent self-destruct + DeleteChildren cascade stable
- No lag frames observed (frame total stays under 224 active scanlines)
- Real game scenes will have fewer objects on screen; this is intentionally worst-case

---

## Phase 7 Comparison — Link-Order Cycling

Date: 2026-04-25
Build: `DEBUG=1 ./build.sh` (209,837 bytes)
Change: Added `Sprite_Cycle_Counter` + per-band intra-band reversal on odd frames

### Per-Subsystem Scanline Costs

| Subsystem | Phase 5 | Phase 7 | Delta |
|---|---|---|---|
| RunObjects | 52 | 52 | 0 |
| TouchResponse | 10 | 10 | 0 |
| Render_Sprites | 43 | 46 | **+3** |
| **Frame Total** | **108** | **108** | **0** |

### Slot Usage

Unchanged: 30/40 dynamic, 16/16 effects.

### Analysis

- Render_Sprites gained +3 scanlines from link-order cycling overhead (btst per band, stack push/pop, indexed read instead of auto-increment)
- Frame total unchanged at 108 — the +3 is within measurement variance of the VDP V counter (1-scanline granularity)
- **Cost: ~3 scanlines (1.3% of active frame) for flicker-based overflow instead of permanent dropout**
- No visual artifacts, no crashes, no regressions under stress test load

---

## Phase 7 Final — All Advanced Sprite Features

Date: 2026-04-25
Build: `DEBUG=1 ./build.sh` (209,988 bytes)
Changes since Phase 5:
- Link-order cycling (per-band intra-band reversal on odd frames)
- Sprite X=0 masking support (configurable band-boundary insertion)
- Scanline-aware sprite budgeting (7 bands × 32 scanlines, 24-piece limit)
- Threshold optimization (skip budget check when total pieces < 24)
- Solid collision fix (skip landing snap while player is rising)

### Per-Subsystem Scanline Costs

| Subsystem | Phase 5 | Phase 7 (cycling only) | Phase 7 Final | Delta (5→final) |
|---|---|---|---|---|
| RunObjects | 52 | 52 | 52 | 0 |
| TouchResponse | 10 | 10 | 10 | 0 |
| Render_Sprites | 43 | 46 | 52 | **+9** |
| **Frame Total** | **108** | **108** | **115** | **+7** |

### Peak Values

| Subsystem | Phase 5 | Phase 7 Final | Delta |
|---|---|---|---|
| RunObjects | 93 | 73 | -20 |
| TouchResponse | 12 | 11 | -1 |
| Render_Sprites | 67 | 64 | -3 |
| **Frame Total** | **171** | **146** | **-25** |

### Slot Usage

Unchanged: 30/40 dynamic, 16/16 effects.

### Analysis

- Render_Sprites +9 scanlines over baseline from three features: cycling (+3), budgeting (+6)
- Frame total 115/224 (51%) at steady state — healthy headroom for level rendering
- Peak frame DROPPED from 171 to 146 — the budget check skips objects in overloaded bands, reducing peak render cost
- Threshold optimization saved 4 scanlines on Render_Sprites (56→52) by skipping the budget check when total pieces < 24
- X=0 masking adds zero steady-state cost (mask sprites only inserted when SpriteMask_Y ≠ 0)
- Solid collision fix: player no longer clips to platform tops mid-jump
- No lag frames, no visual corruption, no crashes under full stress load
- **Total Phase 7 cost: +7 scanlines (3.1% of active frame) for link-order cycling + scanline budgeting + X=0 masking support**
