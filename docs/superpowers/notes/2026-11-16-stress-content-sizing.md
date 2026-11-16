---
kind: note
title: Step-0 stress content sizing (v2 C1)
date: 2026-11-16
base: aeon master 6db86e0d
plan: .aeon-v2-harness/docs/superpowers/plans/2026-11-16-measurement-harness-and-stress.md (Task 7)
consumers: Tasks 8 (STRESS_OBJECTS), 9 (STRESS_SIDEKICK), 10 (STREAM_CLIP)
---

# Step-0 stress content: what each shape is, and how big it is (v2 C1)

This note fixes the build mechanism, the content and the coverage rule for each of the
three stress shapes. Tasks 8 to 10 build them as written here. Where this note departs
from the plan, it says so under "Plan items overturned", with the evidence.

Every figure carries one of these labels:

- **MEASURED**: I ran it or read it from a built artifact at 6db86e0d, and the artifact is named.
- **ESTIMATED**: a model or a judgement. Each one names the run that settles it.
- **PUBLISHED**: read from a committed doc or source file, which is cited.

No figure here is 0 or "OK" by default. Where something was not measured, the note says so.

All scratch evidence lives in `.aeon-v2-stress/.scratch-c1/` (uncommitted): the probes,
logs, ROMs, listings and the prototype diff. Paths below are relative to that directory.

## 0. Shared facts every shape relies on

### Listing symbols (MEASURED)

I read these from `base/s4.lst` and `base/s4.debug.lst`, the canonical release and DEBUG
builds at 6db86e0d. Every one exists in both listings.

RAM symbols:

- `Dynamic_Live_Count`, `Dynamic_Live`, `Dynamic_Live_Pending_Count`
- `Player_1`, `Player_2`, `Player_Chardef`
- `Camera_X`, `Camera_Y`, `Camera_X_Max`
- `Page_Evict_Gen`, `PageCache_Direct_Map`
- `Ctrl_1_Held`, `Ctrl_1_Press`

Code symbols:

- `PageIn_EnqueueLanding`, `PageCache_AllocFrame`, `PageCache_PickVictim`
- `Player_Main`, `Ability_None`, `ObjCodeBase`, `CharDef_Sonic`

Equates:

| Equate | Value | Equate | Value |
|---|---|---|---|
| `SST_code_addr` | $00 | `CULL_DISTANCE_X` | $300 |
| `SST_x_pos` | $02 | `CULL_DISTANCE_Y` | $200 |
| `SST_y_pos` | $06 | `ENTITY_LOAD_BUFFER` | $180 |
| `art_tile` | $14 | `ENTITY_DESPAWN_BUFFER` | $200 |
| `mapping_frame` | $23 | `ENTITY_LOAD_BUFFER_Y` | $100 |
| `NUM_DYNAMIC` | $28 (40) | `ENTITY_DESPAWN_BUFFER_Y` | $180 |
| `NUM_PLAYERS` | 2 | `SECTION_SIZE` | $800 |
| `PAGE_FRAMES` | $C (12) | `SCREEN_WIDTH` | $140 |
| `BUTTON_RIGHT` | $08 | `SCREEN_HEIGHT` | $E0 |
| `BUTTON_B` | $10 | `BUTTON_C` | $20 |

`PAGECACHE_DIRECT_{RESIDENT,PLAIN,BOUNDED}` are $FF, $80 and $01 (PUBLISHED,
`engine/system/constants.emp:452-454`).

### How the measurement builds were made (MEASURED)

Every build below used `NO_LINT=1` (about 16 s for canonical, about 50 s for S2CLIP),
because the pre-build citation lane was red at 6db86e0d. Master's fix (c0ced27e) is now
merged into this branch (5863be59).

After that merge, canonical `s4.bin` = 193507d9 and `s4.debug.bin` = ce326232 are
unchanged (MEASURED, rebuilt).

### Builds needed for the leg ROMs

Every leg ROM needs `SIGIL_BUILD=…/sigil/target/release/sigil` and
`SIGIL_EMIT=…/sigil/target/release/emit_sound_blob`.

## 1. STRESS_OBJECTS (Task 8, plan C2)

### 1.1 How the engine holds objects (PUBLISHED, from `engine/objects/entity_window.emp` and `core.emp`)

**Load.** An object loads when all of these hold:

- its section is one of the four tracked sections. The 2×2 set starts at
  `sec_x0 = (Camera_X − ENTITY_DESPAWN_BUFFER) >> 11`, with the same rule in Y.
- its X is within [Camera_X − $180, Camera_X + 320 + $180].
- its Y is within [Camera_Y − $100, Camera_Y + 224 + $100].

**Despawn.** An object despawns only in two cases:

- its section leaves the tracked set;
- its Y leaves [Camera_Y − $180, Camera_Y + 224 + $180].

There is no X despawn. So objects stay live until their whole section column is dropped,
which happens 512 px after the camera's left edge passes the section boundary.

**Dispatch.** RunObjects skips the dispatch of any object with
|x − Camera_X| > CULL_DISTANCE_X or |y − Camera_Y| > CULL_DISTANCE_Y. Those objects stay
live and still count in `Dynamic_Live_Count`.

**Pool.** The pool holds `NUM_DYNAMIC` = 40 slots plus a pending list of 8. When both are
full, `Load_Object` returns failure. The window then sets no "loaded" bit, so the next scan
retries the load (`entity_window.emp:1316`). An alloc failure is silent and costs a
re-scan. It is not a crash, but it is a stress artifact we do not want to measure.

**Generator limits.** Each section allows at most 128 entries and 32 types
(PUBLISHED, `tools/ojz_entity_gen.py`).

What this means for density: uniform density along the path cannot give "many objects on
screen" without filling the pool with stale, culled objects in sections the camera has
already passed.

### 1.2 Density model and numbers

Model: `sim/objsim.py` and `sim/objsim2.py`. They replay the entity window and the
RunObjects cull, using the equates above, over the camera and player path of the
canonical `run` leg.

The path comes from the 2026-09-25 perf survey's release run leg, `legjson/s1_rel_run.json`:
1898 ticks, cam_x 96 → 5824 (PUBLISHED data, extracted from the survey tarball). The
canonical OJZ objects come from the committed `entity_data.emp`. There are 11 of them:
sec0 holds 1 solid and 7 springs, sec1 holds 1 solid, and sec2 holds 1 solid and 1 static
(MEASURED).

| Placement | Overlay objects | Live max | Alloc-fail events | Ticks with ≥30 dispatched | Ticks with ≥20 dispatched |
|---|---|---|---|---|---|
| uniform, 24 px spacing, ±96 px in Y | 237 | 40 (at cap 1509 ticks) | 84 234 | 1226 | 1287 |
| uniform, 96 px spacing, ±96 px in Y | 61 | 40 (at cap 160 ticks) | 491 | 875 | 1169 |
| **perpendicular ±96 px, 24 px spacing, greedily thinned to live ≤ 38** | **248** | **38** | **0** | **531** | **679** |
| perpendicular ±96 px, 32 px spacing, thinned to ≤ 38 | 244 | 38 | 0 | 368 | 712 |

All of these figures are ESTIMATED: they come from a static model, not a ROM run. The
uniform rows show the failure mode described in 1.1. The thinned 24 px row is the design.

Per-section overlay counts for the design row (ESTIMATED): sec0 2, sec1 60, sec4 92,
sec7 45, sec8 49. All of these are under the 128-entry limit, and the overlay adds at
most 2 types per section.

### 1.3 Mechanism (what Task 8 builds)

**1. Overlay generator.** Write `tools/stress_objects_overlay.py`.

- `place(path, act_w, act_h, spacing=24, offset=96, clearance_px=64, live_cap=NUM_DYNAMIC-2)`.
- For each path point at arc-length step `spacing`, put candidates at ±`offset` px along
  the path normal.
- Drop any candidate within `clearance_px` (Chebyshev) of any path point, or outside the act.
- Then thin greedily. Replay the window model of 1.1 over the camera path. At the worst tick
  over the live cap, drop the overlay objects farthest from the camera, and repeat until
  max live ≤ 38.
- `scratch-c1/sim/objsim2.py` is the reference implementation. Port its `simulate` and
  `thin` functions as they are, and read the equates from the listing, not from literals.
- Types alternate `solid` and `static` at subtype 0, both already in `objects.json`, both
  using `VRAM_TEST_OBJ` art, and both present in release and DEBUG (MEASURED from the
  listings).
- Never use `spring`: it launches the player, and the path assumption breaks.
- Never use `enemy`: `ObjDef_Enemy` is DEBUG-only (MEASURED: release listing 0, DEBUG 1).

**2. The path input.** The input is the canonical `run` leg's per-tick
(Camera_X, Camera_Y, P1 x, P1 y).

Task 8 commits that path as `games/sonic4/test/fixtures/stress_objects.path.json`, next
to the overlay, so the overlay is reproducible offline. The path comes from:

- Task 6's canonical `run` leg JSON on the harness branch, which is expected to land first;
- or, if Task 6 has not landed, the September survey's `s1_rel_run.json`, extracted from
  `docs/research/2026-09-25-perf-survey/results/leg_json.tar.gz`. Columns 4 to 7 of each
  row are cx, cy, px, py.

The fixture header records which of the two it came from, plus that source's commit. A
fixture made from the survey is regenerated from Task 6's leg once Task 6 lands. The path
witness in 1.4 catches any drift.

**3. Overlay location: `games/sonic4/test/fixtures/stress_objects.overlay.json`.** This is
NOT the plan's `games/sonic4/data/editor/ojz/act1/…`.

MEASURED: an empty file at the plan's path turns `tools/level_staleness.py` STALE. The
content stamp hashes every file under `games/sonic4/data/editor/**`, so the canonical
build's staleness gate would fail.

**4. Re-bake.** Add `--overlay PATH` to `ojz_entity_gen.py generate`.

- It merges the overlay into the section lists before the 128/32 validation.
- It rewrites `games/sonic4/data/generated/ojz/act1/entity_data.emp` in place.
- `_mode_generate` currently rejects any argument (PUBLISHED), so this is new.

**5. Build shape `STRESS_OBJECTS=1`.** Copy the S2CLIP block in `build.sh` (lines ~186-256
and ~1074-1121):

- an EXIT trap that runs `git checkout` and `git clean` on
  `games/sonic4/data/generated/ojz/act1`;
- a standalone literal `ROM_NAME="s4.stressobj"` (`.debug` added by the existing DEBUG
  suffix logic);
- release and DEBUG builds; FAST refused.
- The shape is mutually exclusive with S2CLIP and STRESS_SIDEKICK. S2CLIP's pass 8 also
  rewrites `entity_data.emp`.

**6. Self-check in the shape.** After the re-bake, the shape re-runs the model on the baked
data. It refuses the build if max live > 38, or if fewer than 60 ticks have ≥30 objects
dispatched.

### 1.4 Coverage rule (Task 8 / Task 6 leg policy `run`)

Read these per tick, the same way in both shapes:

- `Dynamic_Live_Count.w`
- `Dynamic_Live_Pending_Count`
- the first `Dynamic_Live_Count` word pointers of `Dynamic_Live[]`. For each SST, read
  `x_pos` (`SST_x_pos` $02) and `y_pos` (`SST_y_pos` $06).
- `Camera_X` and `Camera_Y`

`dispatched(t)` is the count of SSTs with |x − Camera_X| ≤ `CULL_DISTANCE_X` and
|y − Camera_Y| ≤ `CULL_DISTANCE_Y`. It needs no `emulator/object_list`.

Thresholds, as named constants in the leg policy:

| Constant | Value | Rationale |
|---|---|---|
| `OBJ_DISPATCH_MIN` | 30 | ¾ · `NUM_DYNAMIC` (40), the plan's load level, counted as dispatched not live |
| `OBJ_COVER_TICKS` | 60 | one second at 60 Hz of sustained load: the plan's figure. The model gives 531 |
| `OBJ_PATH_PCT` | 95 | path witness: solid objects 64 px off the path must not change the route. 5 % slack for single-tick sub-pixel jitter |

**COVERS** when all three hold:

- `dispatched ≥ OBJ_DISPATCH_MIN` on ≥ `OBJ_COVER_TICKS` ticks of the drive window;
- `Dynamic_Live_Count ≤ NUM_DYNAMIC` on every tick;
- P1's (x, y) equals the canonical run leg's on ≥ `OBJ_PATH_PCT` % of ticks.

Otherwise the result is **DID NOT COVER**, reported with the measured counts.

`Dynamic_Live_Pending_Count > 0` on any tick is reported, not hidden.

Model expectation: 531 ticks with ≥30 dispatched (ESTIMATED; settled by the first
`s4.stressobj` run leg).

## 2. STRESS_SIDEKICK (Task 9, plan C3)

### 2.1 Answer to the C1 questions

**Can a second Player_Main instance run with no product-code changes? Yes (MEASURED).**

**Can a VRAM region be borrowed in both shapes? Yes (MEASURED).**

So there is no owner decision needed for the shape itself. The owner item that remains is
for the future real CPU Tails, not for this shape (Q2).

### 2.2 The audit: what is per-slot and what is global (PUBLISHED, from source)

Already per-slot, through `player_block(a0, a4)`, which asserts `NUM_PLAYERS == 2`:

- the SST, Player_Blocks[slot], and physics;
- RunObjects' always-loop dispatches Player_2 when its `code_addr` ≠ 0;
- TouchResponse and RingCollision loop over `NUM_PLAYERS` and skip slots whose
  `code_addr` is 0.

Global, and these needed handling:

**`Player_Chardef`** (the CharacterDef cache). Its `cd_vrambase` drives P2's `art_tile`
(`Player_InitAssets`) and the DPLC destination (`Player_LoadArt`). Fix, with no product
change: the shape keeps a copy of the CharacterDef with `cd_vrambase` replaced, and swaps
the `Player_Chardef` pointer around P2's calls.

**The input path.** `Player_Main` reads `Ctrl_1_Held` and `Ctrl_1_Press` directly. Only
the leader (`cmpa.w #Player_1`) writes the input word into
`Player_Stat_Ring[Player_Ring_Index]`, as `Held<<8 | Press`. The shape gives P2 the
leader's input word from 16 ticks ago, and restores `Ctrl_1_Held` afterwards.

**Globals that are left alone** (risks R1 to R3):

- `Player_Init` / `Player_RefreshPhysics` write `Camera_Curl_Offset` and palette line 0.
  P2 shares the character, so they write identical values.
- `Camera_Hold_Frames`, written by spindash.
- `Player_Death_Pending`. Under `EDGE_KILL` it only clamps.

### 2.3 The follower design, and why the plan's version was dropped

The plan said "same input, 32 px behind". MEASURED that this fails. In a BlastEm 0.6.2
release run over RSP, holding RIGHT from tick 150 (`bx/probe.py`, v1 prototype), P2 hit a
spring P1 had missed. P2 was then off-camera, where `Collision_GetType` returns AIR because
the collision lookup only covers the tile-cache window around the camera
(`engine/level/collision_lookup.emp`). P2 fell through the world.

The **delayed-input replay** works. P2 spawns on P1 and runs P1's input word from K = 16
ticks ago, so it retraces P1's path exactly.

In this section and in 3.1, a "tick" is one probe step: one hit of the breakpoint at
`Input_Tick`, where the probe writes the pad bytes and reads RAM. `Logic_Tick` read 0 on
every row in this game state (`lt` = 0 in every row of the JSON), so the step count is the
only clock. `Frame_Counter` advanced about 1.04 frames per step (2 → 730 over 700 steps).

MEASURED, release v2 (`s4.sidekick2.bin`, crc 878edbaa), 700 ticks:

- P2(t) == P1(t − 16) on all 500 ticks from 200 to 699;
- P1 identical to the canonical run on every tick;
- maximum separation 160 px;
- P2 `art_tile` = 768;
- `Player_Chardef` restored to `CharDef_Sonic` after every tick.

MEASURED, DEBUG (`s4.sidekick3.debug.bin`, crc 1178573b), 600 ticks, with debug-fly
toggled by B at tick 160:

- P1 leaves the ground in free flight, which writes no ring entries.
- Without a fix, P2 replays stale ring words.
- v3 adds the fix: while P1's `debug_flag` is set, P2 is pinned to P1's position.
- Result: P2(t) == P1(t − 16) on every tick from 180 to 599.
- The largest separation is 487 px as a Manhattan sum |dx| + |dy|, at tick 426:
  dx 247, dy 240. That is a diagonal flight path, not a fall.
- Across the run, the largest single-axis separations are dx 252 and dy 240.
- In release, the maximum of 160 px is all horizontal (dy 0 on every tick).

### 2.4 VRAM (MEASURED)

`spare_nametable` (tiles 768-895) has lifetime `boot` and no register. The DEBUG tags
borrow tiles 883-895, which leaves 768-882 (115 tiles) free in both shapes.

The shape declares this region in `games/sonic4/vram.toml`, before `debug_preset_readout`:

```toml
[[region]]
name = "stress_sidekick_body"
owner = "games.sonic4.ojz_scroll_test"
kind = "window"
base = 768
tiles = 29                 # = character_window's 29
lifetime = "mode"
const = "VRAM_STRESS_SIDEKICK"
borrows = "spare_nametable"
```

Regenerate the map with:

```
python3 tools/gen_vram_map.py --game sonic4 --toml games/sonic4/vram.toml \
  --emp games/sonic4/config/constants.emp --py tools/vram_map.py \
  --map-doc docs/generated/vram-map-sonic4.md
```

The regeneration adds `VRAM_STRESS_SIDEKICK = $0300` and two `ensure`s.

A Tails follower would need 9 more tiles for its appendage, at 797-805, which also fits
(ESTIMATED; not built). The brief says 8. The declared region is 9: `tails_appendage`
has `tiles = 9` at `games/sonic4/vram.toml:574` (PUBLISHED), so this note sizes against 9.

P2 shares the `insta_shield` window at 928 with P1. That is visual only (R4).

### 2.5 The build mechanism: one committed patch, applied under an EXIT trap (MEASURED)

**The chosen mechanism.** The shape keeps all stress code off canonical master, following
the plan's off-canonical decision. The sidekick lives in one patch file,
`tools/stress/sidekick.patch` (Task 9 commits it). The patch is data that nothing
compiles, and it touches exactly two files:

- `games/sonic4/vram.toml`: adds the `stress_sidekick_body` region of 2.4;
- `games/sonic4/test/ojz_scroll_test.emp`: adds the code of 2.6, **ungated**.

The patch needs no `if` gate and no shape constant. The reference copy, 104 lines, is
`.scratch-c1/offmaster/sidekick.patch`.

**The shape `STRESS_SIDEKICK=1`** in `build.sh` follows the S2CLIP pattern:

1. Refuse FAST, and refuse S2CLIP or STRESS_OBJECTS in the same build.
2. Install an EXIT trap that runs `git checkout --` on `games/sonic4/vram.toml`,
   `games/sonic4/test/ojz_scroll_test.emp`, `games/sonic4/config/constants.emp`,
   `tools/vram_map.py` and `docs/generated/vram-map-sonic4.md`.
3. Run `git apply --check tools/stress/sidekick.patch`. If it fails, refuse loudly and
   name the patch: the patch has rotted against `ojz_scroll_test.emp`.
4. Run `git apply tools/stress/sidekick.patch`.
5. Regenerate the VRAM map with the `gen_vram_map.py` command of 2.4.
6. Build with the standalone literal `ROM_NAME="s4.sidekick"`, in release or DEBUG
   (`.debug` comes from the existing suffix logic).

**What I measured on this mechanism** (`.scratch-c1/offmaster/`):

- The patch applies cleanly at 5863be59.
- Applying it, regenerating, and building release and DEBUG gives `s4.bin` 68b88a27
  (850 616 B) and `s4.debug.bin` 1178573b (870 880 B). These are byte-identical to the
  gated v3 prototype ROMs that were probed in 2.3, so the probe evidence carries over
  unchanged.
- After the `git checkout` restore, the tree shows only `?? .scratch-c1/`.
- A canonical rebuild then gives 193507d9 and ce326232, identical to the baseline.

**Canonical bytes are unchanged by construction.** Canonical master gains only a patch
file that nothing compiles. No listing, no VRAM-map doc and no generated constant changes
on master.

**Rejected alternative.** Commit the region and a const-gated copy of the code to master.
I measured that this is byte-neutral: with the region, a new `games/sonic4/test/stress_shape.emp`
module and the gated code all at 0, the build gave 193507d9 and ce326232, and the sigil
warning counts were unchanged. It was still rejected, because it puts stress code, a VRAM
region, generated constants and a vram-map entry on master, against the plan's
off-canonical decision. Reusing `OJZ_CLIP_ACT` as the gate was rejected too, because
`clip_act.emp` rewrites it.

**Cost of the chosen mechanism.** The patch can rot when `ojz_scroll_test.emp` changes.
Step 3 makes that loud. Fixing it is a re-diff of two hunks.

### 2.6 Reference code for Task 9 (the body of the patch)

These imports are added to `ojz_scroll_test.emp`:

```
use engine.structs.{CharacterDef}
use games.sonic4.constants.{VRAM_STRESS_SIDEKICK}
```

**Init**, in `GameState_OJZScroll_Init`, after the DEBUG boot-override block:

```
        lea     System_Slots, a1                // CharacterDef copy's home: System slot 0
        lea     2(a1), a1                       // (its code_addr stays 0: never dispatched)
        movea.l a1, a2
        movea.l Player_Chardef, a0
        moveq   #sizeof(CharacterDef)/2-1, d0
.sk_copy:
        move.w  (a0)+, (a1)+
        dbf     d0, .sk_copy
        move.w  #VRAM_STRESS_SIDEKICK, offsetof(CharacterDef, cd_vrambase)(a2)
        lea     Player_1, a0
        lea     Player_2, a1
        move.l  Sst.x_pos(a0), d0
        move.l  d0, Sst.x_pos(a1)
        move.l  Sst.y_pos(a0), Sst.y_pos(a1)
        movea.l a1, a0
        jbsr    Player_Init
        movea.l Player_Chardef, a5
        lea     System_Slots, a1
        lea     2(a1), a1
        move.l  a1, Player_Chardef
        lea     Player_2, a0
        tst.b   PlayerV.debug_flag(a0)
        bne     .sk_marker
        jbsr    Player_InitAssets
.sk_marker:
        move.l  a5, Player_Chardef
        lea     Player_2, a0
        move.w  #Ability_None - ObjCodeBase, Sst.code_addr(a0)   // park RunObjects' dispatch
```

**Per tick**, in `GameState_OJZScroll_Update` right after `jbsr RunObjects`:

```
        lea     Player_2, a0
        tst.w   Sst.code_addr(a0)
        beq     .sk_off
        lea     Player_1, a1                    // leader in free flight writes no trail:
        tst.b   PlayerV.debug_flag(a1)          // pin the follower to it
        beq     .sk_trail
        move.l  Sst.x_pos(a1), Sst.x_pos(a0)
        move.l  Sst.y_pos(a1), Sst.y_pos(a0)
.sk_trail:
        movea.l Player_Chardef, a5
        lea     System_Slots, a1
        lea     2(a1), a1
        move.l  a1, Player_Chardef
        movea.w Ctrl_1_Held, a6                 // Held<<8|Press, restored below
        move.w  Player_Ring_Index, d0
        subi.w  #4*(16+1), d0                   // the leader's input 16 ticks ago
        andi.w  #$FC, d0
        lea     Player_Stat_Ring, a1
        move.w  (a1,d0.w), Ctrl_1_Held
        jbsr    Player_Main
        move.w  a6, Ctrl_1_Held
        move.l  a5, Player_Chardef
.sk_off:
```

Sigil gate traps the prototype hit, and their fixes (all MEASURED):

1. **`lea Sym+expr+2, aN` triggers "contract closure DROPPED".** Fix: split it into
   `lea Sym, aN` followed by `lea 2(aN), aN`.
2. **`call.live-clobbered` on `GameState_OJZScroll_Init @ AllocEffect :: a1`.** Fix: no
   AllocEffect at all; the record lives in System slot 0. DEBUG tags use slots 2-7, and
   release never dispatches System slots.
3. **`call.live-clobbered` on `Player_Main :: d7`.** `Player_Main` preserves only `d7.w`.
   Fix: save the input in `a6`.
4. **Copying a `.emp` file anywhere in the worktree breaks the build** with "module
   declared twice". Keep scratch copies as `.emp.txt`.

The patched tree passes every sigil gate the build runs (MEASURED, rc 0 in both shapes).
Task 9 should still run sigil's cross-seam suite (`warn_tier_corpus`, `contract_baseline`)
with `--no-fail-fast` against the patched tree once, and record the result. Because the
patched code never reaches master, sigil's canonical goldens are not affected.

### 2.7 Coverage

Thresholds, as named constants in the leg policy:

| Constant | Value | Rationale |
|---|---|---|
| `SK_LIVE_PCT` | 90 | plan figure. Allows the spawn tick and DEBUG's 27-tick art lag (2.3: 6 % of 450 ticks) |
| `SK_SEP_MAX` | 512 px, Manhattan | about 2× the largest single-axis excursion measured (252, DEBUG flight); release peak 160 |
| `SK_REPLAY_PCT` | 95 | desync witness. Measured 100 % in both shapes; the 5 % is slack for policy inputs the probe never sent, such as jumps. It is a judgement, not a measurement |
| `SK_DPLC_RATIO` | 0.9 | P2 runs `Player_LoadArt` every tick it is live; 10 % for ticks without a pending frame change |

Per tick, read from listing symbols:

- `Player_2+SST_code_addr ≠ 0` on ≥ `SK_LIVE_PCT` % of drive ticks;
- |P2.x − P1.x| + |P2.y − P1.y| ≤ `SK_SEP_MAX` on ≥ `SK_LIVE_PCT` % of drive ticks;
- `Player_2+art_tile & $7FF == VRAM_STRESS_SIDEKICK` on ≥ `SK_LIVE_PCT` % of drive
  ticks. In MEASURED terms: release 100 %. DEBUG mismatched on ticks 150-176, before P2's
  art was set, which is 27 of 450 ticks;
- desync witness: P2(t) == P1(t − 16) on ≥ `SK_REPLAY_PCT` % of ticks after tick 16 of the
  drive.

**DPLC check (profiler).** `Player_LoadArt` is reached only by `jbra`
(`games/sonic4/player/player_common.emp:1286,1292`), so it never gets a profiler row. Use
`Perform_DPLC` instead, which is `jbsr`'d inside `Player_LoadArt`
(`games/sonic4/player/characters.emp:106`) and is present in both listings (MEASURED).

The rule: (`Perform_DPLC` calls in the sidekick leg) − (`Perform_DPLC` calls in the
canonical `run` leg over the same drive window) ≥ `SK_DPLC_RATIO` × (ticks with P2 live).

Other `Perform_DPLC` callers are test_animated, tails_appendage and test_player. They run
identically in both legs, so they cancel in the delta. If Task 3's DMA probe events are
available, its per-tick count of DMA transfers to `VRAM_STRESS_SIDEKICK` is a stricter
second witness.

**A missing `Perform_DPLC` row in either leg is UNMEASURABLE.** It is reported loudly and
is never a pass. Never treat a missing row as 0.

Any failed check is DID NOT COVER, reported with the measured numbers and never retried
silently.

The expected delta is about 1 call per live tick (ESTIMATED; settled by the first
`s4.sidekick` run leg).

### 2.8 Risks (all ESTIMATED; none blocks the shape)

- **R1.** `Camera_Hold_Frames` is global, and P2's spindash writes it. The `run` policy
  does not spindash.
- **R2.** `Player_Death_Pending` is global. Under EDGE_KILL it only clamps.
- **R3.** P2 collects rings, so the ring count differs from canonical. It is not a
  coverage input.
- **R4.** The `insta_shield` window at 928 is shared. Visual only.
- **R5.** P2 runs after RunObjects rather than straight after P1. Object interaction order
  differs from a real CPU Tails. Acceptable for load stress.
- **R6.** `test_system_pool_release_empty`'s literal scanner would flag the sidekick
  release ROM if it were ever run on it. Slot 0's `code_addr` stays 0. Exempt the shape
  ROM from that test.

## 3. STREAM_CLIP (Task 10, plan C4)

### 3.1 Which clip streams, and whether it finishes

Both clips were converted and built in this worktree. The donors are gitignored, so I
converted them with `tools/s2_zone_convert.py convert s2disasm@{EHZ,CPZ,MTZ,OOZ,WFZ}`
and `s2-simonwai-disasm@HPZ`, about 1 s each.

I ran each on BlastEm 0.6.2 with `bx/streamprobe.py`: hold RIGHT from tick 150, and press
C every 16 ticks while P1 makes less than 2 px of progress in 8 ticks. "Tick" means the
probe step of 2.3. **Only the release shape was run. DEBUG `s4.s2clip.debug.bin` DID NOT
RUN for either clip.**

**`s2_ehz_cpz`, release (17 pages, 12 frames), MEASURED:**

- **FINISHES:** it reaches `Camera_X_Max` 16064 at tick 2964.
- **No streaming:** `Page_Evict_Gen` stays at 1 for the whole leg (`PageCache_Init`'s
  bump, at tick 4), and `PageCache_Direct_Map` stays at 1 (`PAGECACHE_DIRECT_BOUNDED`).
  That is zero evictions.
- The September survey agrees: its clip release-run profile has no `PageCache_AllocFrame`
  or `PageIn_EnqueueLanding` row (PUBLISHED data, MEASURED by me from the tarball).

**`s2_woven`, release (49 pages; worst window 12 of 12 frames), MEASURED:**

- **Streams:** `PageCache_Direct_Map` is 0 (general regime) from load onwards.
  `Page_Evict_Gen` goes 3 → 4 → 5 → 6 at ticks 236, 324 and 364 (cam_x 412, 949, 1202),
  which is 3 evictions in the drive window.
- **STUCK:** P1 x = 2230 on every logged row from tick 504 to tick 2996
  (`bx/woven_run.jsonl`), and the probe ended at its 3000-step limit (`bx/woven.out`:
  "done at tick 2999"). The C-press unstick does not free it. `Camera_X_Max` is 9920 and
  cam_x stays at 2071.

**No candidate meets the brief's Step 3** (FINISH, plus decode ≥ 1). `s2_ehz_cpz`
finishes but never pages. `s2_woven` pages but does not finish.

### 3.2 Mechanism and status

The leg is the existing S2CLIP shape: `S2CLIP=s2_woven`, LEG_ROM `s4.s2clip[.debug]`. The
donors must be converted in whichever worktree builds it (Q3).

The controller's ruling decides how the leg is reported:

- **The stream leg's status is STUCK at the stall.** It is never COVERS.
- The rule's counts (3.3) are reported as **annotations** alongside STUCK. They never
  turn the leg into COVERS.
- They are the evidence for G0's "a streaming act exists": `s2_woven` evicts on a real
  drive (3 evictions, MEASURED).
- Whether to find or author a clip that both streams and finishes is owner question Q1.

### 3.3 Streaming counts (the annotation; also the rule for a future clip that finishes)

The plan's rule was "decode calls ≥ 1". **Replace it.** `ZX0R_Decompress` is entered by
`jbra` from `PageIn_Process`, is stackless and calls nothing, so it never appears as a
profiler row (PUBLISHED: `oracle-core/src/profiler.rs` keys rows by JSR/BSR entry only).

**Window.** The window starts at the first drive tick, which is after load, so
`PageCache_Init`'s bump is excluded (`engine/level/page_cache.emp:256` bumps
`Page_Evict_Gen` with no `PickVictim` call). The window ends at the drive's end, or at
the stall for a STUCK leg.

Over that window:

- `streamed` holds when ΔPage_Evict_Gen ≥ 1 **and** `PageIn_EnqueueLanding` calls ≥ 1
  **and** `PageCache_Direct_Map == 0` at the window's end.
- **Cross-check:** `PageCache_PickVictim` calls ≥ ΔPage_Evict_Gen. It cannot be `==`,
  because `PickVictim` can return $FFFF and the caller then takes `.no_frame` without
  bumping the counter (`page_cache.emp:425-427`).
- Report `no_victim = PickVictim calls − ΔPage_Evict_Gen` alongside the check.
  `PickVictim calls < ΔPage_Evict_Gen` means the window or the profiler is wrong: report
  it as UNMEASURABLE.
- A missing `PageIn_EnqueueLanding` or `PickVictim` row while ΔPage_Evict_Gen > 0 is also
  UNMEASURABLE. It is never read as 0.
- The canonical OJZ `run` leg is the control, and should give ΔPage_Evict_Gen = 0
  (ESTIMATED; read from Task 6's canonical leg).

For `s2_woven`, a window ending at a stall cut-off of tick 400 or later contains all 3
evictions. That is MEASURED under my probe's input; for Task 6's `run` policy it is
ESTIMATED, and settled by the first `s4.s2clip` run leg.

## 4. Plan items overturned (with the evidence above)

1. **Overlay path.** It moves to `games/sonic4/test/fixtures/stress_objects.overlay.json`,
   not `…/data/editor/ojz/act1/…`. Reason: staleness, see 1.3 step 3.
2. **Object placement.** It is perpendicular placement with greedy thinning to a live cap
   of 38, not a flat `n_per_screen`. Reason: pool exhaustion, see 1.2. Coverage is
   `OBJ_DISPATCH_MIN` dispatched on `OBJ_COVER_TICKS` ticks, not "live ≥ ¾·NUM_DYNAMIC".
3. **Sidekick follower.** It replays P1's input with a 16-tick delay and pins to P1 in
   flight, instead of "same input, 32 px behind". Reason: the measured desync in 2.3.
4. **CharacterDef copy home.** It lives in System slot 0, not an effect slot. Reason: the
   AllocEffect a1 gate trap, 2.6.
5. **Plan default `games/sonic4/test/stress_sidekick.emp`.** Dropped. The code is a patch
   to `ojz_scroll_test.emp` (2.5), because it has to sit right after `RunObjects` and
   inside Init.
6. **Stream rule and clip.** The rule uses `Page_Evict_Gen`, `PageIn_EnqueueLanding` and
   `PageCache_Direct_Map`, not a decode-routine count (3.3). The clip is `s2_woven`,
   reported STUCK with the counts as annotations (3.2). No clip meets Step 3.

There is no overturn 7: the sidekick does not need a commit to master (2.5).

## 5. Effort (ESTIMATED; replaces the plan's 4-6 days)

| Item | Plan | Revised | Why |
|---|---|---|---|
| C2 objects | 1-1.5 d | **1.5-2 d** | the generator now includes the window model and thinning, a new `--overlay` mode, the path fixture, and the shape self-check |
| C3 sidekick | 2-4 d | **1-1.5 d** | the prototype works; what remains is turning it into the patch shape, coverage, and one sigil cross-seam run |
| C4 stream | 0.5 d | **0.5-1 d** | the shape already exists; the work is the STUCK reporting, the annotation counts, and the donor setup |
| **Total** | 4-6 d | **3-4.5 d** | a clip that also finishes (Q1) is not included |

## 6. Owner questions

**Q1. A clip that both streams and finishes.** None exists: `s2_ehz_cpz` finishes but
never pages, and `s2_woven` pages but is STUCK at x 2230 (3.1). Under the ruling, step 0
reports the stream leg as STUCK with the counts as annotations. Do you want a clip that
both streams and finishes, so the leg can cover? Options:

- (a) author or route one, for example a flat woven variant or a corridor past the wall;
- (b) add a `stream` leg policy that drives around the wall;
- (c) accept STUCK-with-annotations as step 0's final answer.

**Q2. Per-slot `cd_vrambase` / `Player_Chardef` for a real CPU Tails.** The stress shape
does not need it, because it swaps the pointer. A shipped CPU Tails does. Options:

- (a) make `Player_Chardef` per slot in the Player_Blocks;
- (b) keep the pointer swap in the game layer.

**Recommended:** (a), when CPU Tails is scheduled. It is not a step-0 blocker.

**Q3. Donor availability.** The clip donors are gitignored. Every worktree that builds
STREAM_CLIP must run the six conversions first. Recommended: Task 10's leg setup runs
them, or refuses with a clear message.
