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
