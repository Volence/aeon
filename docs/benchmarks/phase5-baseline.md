# Phase 5 Baseline Benchmark — Object System

Date: 2026-04-25
Build: `DEBUG=1 ./build.sh` (209,579 bytes)
Emulator: Exodus 2.1, NTSC mode (262 scanlines/frame, 224 active)

## Test Scene

Combined integration + stress test (`GameState_ObjectTest`):
- 1 player (Sonic, animated DPLC art streaming)
- 5 enemies (3 ground patrol, 2 elevated, COLLISION_HURT)
- 8 solid platforms (COLLISION_SOLID, staircase layout)
- 3 particle emitters (spawn to effect pool every 30 frames)
- 2 parent objects (3 children each, self-destruct at 180 frames)

Peak load: 24 dynamic slots + ~5 effect slots (init frame with parents + children + particles)
Steady state: 16 dynamic slots + 2-4 effect slots (after parents self-destruct)

## Per-Subsystem Scanline Costs

| Subsystem | Steady State | Peak | % of Active Frame (peak) |
|---|---|---|---|
| RunObjects | 21 | 38 | 17.0% |
| TouchResponse | 8 | 8 | 3.6% |
| Render_Sprites | 20 | 27 | 12.1% |
| **Frame Total** | **50** | **68** | **30.4%** |

Measured via VDP V counter (high byte = scanline number).
Peak values captured across all frames since boot, including the init frame.

## Slot Usage

| Pool | Capacity | Peak Used | Steady State |
|---|---|---|---|
| Dynamic | 40 | 24 (60%) | 16 (40%) |
| Effect | 16 | ~5 (31%) | 2-4 (13-25%) |

## Analysis

- Frame total is well within budget at ~50 scanlines steady state (22% of active frame)
- ~70% of CPU time is still available for future systems (level rendering, scrolling, sound)
- RunObjects is the largest cost (42% of game loop) — expected with animated Sonic DPLC streaming
- TouchResponse is cheap (16% of game loop) — O(players * objects) with early AABB rejection
- Render_Sprites is moderate (40% of game loop) — 4 flip variants, priority band sorting
- No lag frames observed during normal operation
- Parent self-destruct + DeleteChildren cascade completes without crash
- Effect pool recycles correctly (SP returns to base after particle despawn)
