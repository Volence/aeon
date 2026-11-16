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

### The pre-build lint lane is red on master (MEASURED)

A plain `./build.sh` at 6db86e0d fails in the pre-build pytest lane.
`tools/test_citation_form.py::test_live_citations_resolve_to_something` reports 28 bare
`.emp:N` citations under `docs/audits/` (from commit 90a45adb). This predates C1 and C1
does not touch it.

Every build below used `NO_LINT=1` (about 16 s for canonical, about 50 s for S2CLIP).
Tasks 8 to 10 cannot get a green build either until this is fixed (owner question Q3).

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
(Camera_X, Camera_Y, P1 x, P1 y), recorded by Task 6's `leg_run` on the current canonical
ROM. The survey JSON is only the interim input for developing the generator.

Commit the generated overlay together with the path it was generated from, so it is
reproducible offline.

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

**COVERS** when all three hold:

- `dispatched ≥ 30` on ≥ 60 ticks of the drive window;
- `Dynamic_Live_Count ≤ NUM_DYNAMIC` on every tick;
- P1's (x, y) equals the canonical run leg's on ≥ 95 % of ticks. This is the path witness:
  the overlay must not have changed the route.

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
- Result: P2(t) == P1(t − 16) on every tick from 180 to 599, with maximum separation
  487 px (a vertical fall).

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

The regeneration adds `VRAM_STRESS_SIDEKICK = $0300` and two `ensure`s. A Tails follower
would need 9 more tiles for its appendage, at 797-805, which also fits (ESTIMATED; not built).

P2 shares the `insta_shield` window at 928 with P1. That is visual only (R4).

### 2.5 Canonical bytes stay identical by construction (MEASURED)

There are no top-level `if` items in `.emp`. Gating is therefore done inside proc bodies:
`if STRESS_SIDEKICK == 1 { … }` emits nothing when the constant is false. The precedent is
`if OJZ_CLIP_ACT == 1` in `ojz_scroll_test.emp`.

The constant lives in a new const-only module, `games/sonic4/test/stress_shape.emp`, with
the content `module games.sonic4.stress_shape` / `pub const STRESS_SIDEKICK = 0`. Sigil
walks the whole tree, so the module needs no registry entry. The shape writes `1` under
the EXIT-trap restore.

With the vram.toml region, the new module and the gated code all present at value 0:

- canonical `s4.bin` = 193507d9 and `s4.debug.bin` = ce326232, byte-identical to the
  untouched baseline;
- sigil warning counts unchanged (19 path-mismatch; 170 release, 158 DEBUG in total).

At value 1, both stress ROMs build (MEASURED):

- `s4.sidekick3.bin`: 68b88a27, 850 616 B
- `s4.sidekick3.debug.bin`: 1178573b, 870 880 B

Rejected alternative: reusing `OJZ_CLIP_ACT`. That constant gets rewritten by `clip_act.emp`.

### 2.6 Reference code for Task 9

The full diff is `proto/sidekick_proto_v3.diff`, 164 lines. Task 9 takes it as written.
Imports added to `ojz_scroll_test.emp`:

```
use games.sonic4.stress_shape.{STRESS_SIDEKICK}
use engine.structs.{CharacterDef}
use games.sonic4.constants.{VRAM_STRESS_SIDEKICK}
```

(The prototype also imported `NUM_EFFECTS`, which it no longer uses. Drop it.)

**Init**, in `GameState_OJZScroll_Init`, after the DEBUG boot-override block:

```
if STRESS_SIDEKICK == 1 {
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
}
```

**Per tick**, in `GameState_OJZScroll_Update` right after `jbsr RunObjects`:

```
if STRESS_SIDEKICK == 1 {
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
}
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

Task 9 must also run sigil's cross-seam suite against the stress branch with
`--no-fail-fast`, because a new module was added (`warn_tier_corpus`, `contract_baseline`).

### 2.7 Build shape and coverage

**Build shape.** Set `STRESS_SIDEKICK=1` in `build.sh`. In-place re-bake, under the same
EXIT trap pattern as S2CLIP:

- the `vram.toml` region and map regeneration;
- `sed` of `stress_shape.emp` to `1`;
- `git checkout` of `vram.toml`, `config/constants.emp`, `tools/vram_map.py`,
  `docs/generated/vram-map-sonic4.md` and `stress_shape.emp` on exit;
- literal `ROM_NAME="s4.sidekick"`;
- mutually exclusive with STRESS_OBJECTS and S2CLIP.

Alternative: commit the region, the module at 0 and the gated code to master. Section 2.5
shows that is byte-neutral, and then the shape only flips the constant. **Recommended:**
commit them, which reduces the shape to a one-line sed.

**Coverage** (per tick, from listing symbols):

- `Player_2+SST_code_addr ≠ 0` on ≥ 90 % of drive ticks;
- |P2.x − P1.x| + |P2.y − P1.y| ≤ 512 on ≥ 90 % of drive ticks (MEASURED maximum: 160 in
  release, 487 in DEBUG flight);
- `Player_2+art_tile & $7FF == VRAM_STRESS_SIDEKICK`;
- desync witness: P2(t) == P1(t − 16) on ≥ 95 % of ticks after tick 16 of the drive. A
  failure is reported as DID NOT COVER, and never retried silently.

**The plan's "DPLC transfers present" check: use the profiler.** `Player_LoadArt` calls
must be ≥ 2 × the canonical leg's count, or report the actual ratio. ESTIMATED; settled by
the first `s4.sidekick` run leg.

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

### 3.1 Which clip actually streams on `run`

Both clips were converted and built in the stress worktree. The donors are gitignored, so
I converted them with `tools/s2_zone_convert.py convert s2disasm@{EHZ,CPZ,MTZ,OOZ,WFZ}`
and `s2-simonwai-disasm@HPZ`, about 1 s each.

I then ran each on BlastEm with `bx/streamprobe.py`: hold RIGHT from tick 150, press C
every 16 ticks while P1 makes less than 2 px of progress in 8 ticks. All figures below
are MEASURED.

**`s2_ehz_cpz` (17 pages, 12 frames):** the run reaches `Camera_X_Max` 16064 at tick 2964.

- `Page_Evict_Gen` stays at 1 for the whole leg, set once by `PageCache_Init` at tick 4.
- `PageCache_Direct_Map` stays at 1 (`PAGECACHE_DIRECT_BOUNDED`) for the whole leg.

So the leg makes **zero** evictions and never leaves the bounded-direct regime. This
agrees with the September survey's profiles: the clip release-run leg has no
`PageCache_AllocFrame` or `PageIn_EnqueueLanding` row (PUBLISHED data, MEASURED by me from
the survey tarball). **This clip does not cover streaming on `run`.**

**`s2_woven` (49 pages; worst window 12 of 12 frames):**

- `PageCache_Direct_Map` = 0 (the general regime) from load onwards.
- `Page_Evict_Gen` goes 3 → 4 → 5 → 6 at ticks 236, 324 and 364, with cam_x 412, 949
  and 1202. That is **3 evictions during the drive window**.
- Then **the run stalls**: P1 is stuck at x 2230 from about tick 500 to 1880, when the
  probe hit its time limit. The C-press unstick does not free it. `Camera_X_Max` is 9920.

### 3.2 Mechanism

Set `STREAM_CLIP = s2_woven`. The S2CLIP shape already exists, so the leg is
`S2CLIP=s2_woven` with `LEG_ROM s4.s2clip[.debug]`.

The donors must be converted in whichever worktree builds the leg (owner question Q4).

### 3.3 Coverage rule

The plan's rule was "decode calls ≥ 1". **Replace it.** `ZX0R_Decompress` is entered with
`jbra` from `PageIn_Process`, is stackless and calls nothing, so it never appears as a
profiler row (PUBLISHED: `oracle-core/src/profiler.rs` keys rows by JSR/BSR entry only).

New rule, over the drive window, in both shapes:

- **COVERS when** ΔPage_Evict_Gen ≥ 1 **and** `PageIn_EnqueueLanding` calls ≥ 1 **and**
  `PageCache_Direct_Map == 0` at the end of the drive.
- Cross-check: `PageCache_PickVictim` calls == ΔPage_Evict_Gen.
- The canonical OJZ `run` leg is the control and should give 0 evictions (ESTIMATED; read
  from Task 6's canonical leg).

Because `s2_woven` stalls, the drive window must be "until progress stops", i.e. the leg
driver's stall cut-off. The coverage numbers are then taken over that window. The probe
saw all 3 evictions before tick 364, so a stall cut-off at tick ≥ 400 covers (MEASURED for
BlastEm with my unstick policy; ESTIMATED for Task 6's `run` policy, settled by the first
`s4.s2clip` run leg).

## 4. Plan items overturned (with the evidence above)

1. **Overlay path.** It moves to `games/sonic4/test/fixtures/stress_objects.overlay.json`,
   not `…/data/editor/ojz/act1/…`. Reason: staleness, see 1.3 step 3.
2. **Object placement.** It is perpendicular placement with greedy thinning to a live cap
   of 38, not a flat `n_per_screen`. Reason: pool exhaustion, see 1.2. Coverage is
   "≥30 dispatched on ≥60 ticks", not "live ≥ ¾·NUM_DYNAMIC". Live count is a poor proxy,
   because culled stale objects inflate it.
3. **Sidekick follower.** It replays P1's input with a 16-tick delay and pins to P1 in
   flight, instead of "same input, 32 px behind". Reason: the measured desync in 2.3.
4. **Shape constant.** It lives in the new module `games/sonic4/test/stress_shape.emp`;
   `clip_act.emp` is not reused. The CharacterDef copy lives in System slot 0, not an
   effect slot.
5. **Plan default `games/sonic4/test/stress_sidekick.emp`.** Dropped. The code sits inside
   `ojz_scroll_test.emp`, because it has to sit right after `RunObjects` and inside Init.
6. **Stream rule.** It uses `Page_Evict_Gen`, `PageIn_EnqueueLanding` and
   `PageCache_Direct_Map`, not a decode-routine count (3.3). The clip is `s2_woven`, not
   `s2_ehz_cpz` (3.1).

## 5. Effort (ESTIMATED; replaces the plan's 4-6 days)

| Item | Plan | Revised | Why |
|---|---|---|---|
| C2 objects | 1-1.5 d | **1.5-2 d** | the generator now includes the window model and thinning, a new `--overlay` mode, and the shape self-check |
| C3 sidekick | 2-4 d | **1-1.5 d** | the prototype works and is byte-neutral; what remains is the shape wiring, coverage, and the sigil cross-seam run |
| C4 stream | 0.5 d | **1-1.5 d** | the clip changes, the rule is rewritten, and the leg driver must handle the woven stall |
| **Total** | 4-6 d | **3.5-5 d** | |

## 6. Owner questions

**Q1. Stalled stream leg.** `s2_woven` streams (3 evictions by tick 364) but its `run` leg
stalls at x 2230. Options:

- (a) accept coverage over the window up to the stall (**recommended**: the evictions are
  real and measured);
- (b) add a `stream` leg policy that routes around the wall;
- (c) author a clip that streams on a flat run.

**Q2. Per-slot `cd_vrambase` / `Player_Chardef` for a real CPU Tails.** The stress shape
does not need it, because it swaps the pointer. A shipped CPU Tails does. Options:

- (a) make `Player_Chardef` per slot in the Player_Blocks;
- (b) keep the pointer swap in the game layer.

**Recommended:** (a), when CPU Tails is scheduled. It is not a step-0 blocker.

**Q3. Master build is red** on `test_citation_form` (28 bare citations in `docs/audits`,
from 90a45adb). Tasks 8 to 10 need a green build to land. Recommended: fix the citations
on master first, as a small separate parcel.

**Q4. Donor availability.** The clip donors are gitignored. Every worktree that builds
STREAM_CLIP must run the six conversions first. Recommended: Task 10's leg setup runs
them, or refuses with a clear message.
