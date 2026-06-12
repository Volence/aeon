# Player Collision Sensors — S.C.E. Architecture vs. Our Substrate (§5 prerequisite)

Research for the §5 player system. Sources: S.C.E. (`Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Find Floor.asm`,
`Objects/Players/Sonic/Sonic.asm`, `Engine/Core/Load Level.asm`, `Objects/Main/Path Swap/Path Swap.asm`),
sonic_hack (`code/engines/object_touch.asm`, `collision/*.bin`, `mappings/{16x16,128x128}/OJZ.bin`),
our engine (`engine/level/collision_lookup.asm`, `engine/level/tile_cache.asm`,
`tools/ojz_strip_gen.py`, `tools/ojz_block_gen.py`, `tools/gen_collision_data.py`,
`docs/ENGINE_ARCHITECTURE.md` §4.7). All byte counts below were measured on the actual files,
not taken from docs. **No code is to be ported — this documents architecture and data formats only.**

Related prior research: `docs/research/dual-layer-collision.md` (layer A/B format — note its claim that
the OJZ index files are "NOT Kosinski-compressed" is **wrong**, corrected in §3.2 below),
`docs/research/player-movement.md`, `docs/research/collision-system.md`.

---

## 1. S.C.E. sensor architecture

### 1.1 The six sensors

S.C.E. is a direct refactor of the S3K player. The classic 6-sensor layout, expressed as routine pairs
(every "pair" routine runs the probe twice — Primary then Secondary — and keeps the *closer* result):

| Sensors | Role | S.C.E. pair routine | Probe core | Positions (floor mode) |
|---|---|---|---|---|
| A / B | floor (grounded + falling) | `Player_AnglePos` (grounded), `Sonic_CheckFloor` (air) | `FindFloor` | `(x ± x_radius, y + y_radius)` |
| C / D | ceiling | `Sonic_CheckCeiling` | `FindFloor`, coords inverted | `(x ± x_radius, y − y_radius)` with `eori.w #$F` on Y |
| E / F | push / walls | `CheckLeftWallDist` / `CheckRightWallDist` (single), `CalcRoomInFront` (grounded, velocity-projected) | `FindWall` | `(x ± 10, y)` airborne; `(x ± 10, y + 8)` grounded on flat (−5 when rolling) |

Radii (`Sonic.asm:66`, stored packed as `bytes_to_word(38/2,18/2)`): standing `y_radius=19, x_radius=9`;
rolling/jumping `y_radius=14, x_radius=7` (`bytes_to_word(28/2,14/2)`). Wall sensors deliberately use the
constant `$A` (10 px), **not** `x_radius`.

Result protocol of every distance routine: `d1.w` = signed distance to the surface
(negative = embedded → snap; 0 = touching; positive = gap), `d3.b` = surface angle
(replaced by the quadrant's cardinal — `0/$40/$80/$C0` passed in `d2` — when the angle byte is odd, see §2.3).

### 1.2 Mode rotation (grounded)

`Player_AnglePos` rounds `angle(a0)` to a quadrant (the `±$20 / andi #$C0` dance at its top, with an
asymmetric bias so 45° corners prefer the previous mode) and dispatches:

| Quadrant | Mode | Routine | Sensor axis | Snap axis |
|---|---|---|---|---|
| `$00` | floor | fallthrough in `Player_AnglePos` | down from feet | `y_pos += d1` |
| `$40` | right wall (climbing left wall surface) | `Player_WalkVertL` | left, X inverted via `eori.w #$F,d3` | `x_pos -= d1` |
| `$80` | ceiling | `Player_WalkCeiling` | up, Y inverted via `eori.w #$F,d2` | `y_pos -= d1` |
| `$C0` | left wall | `Player_WalkVertR` | right | `x_pos += d1` |

In each mode the "radius" roles rotate: wall modes use `y_radius` along the probe axis and `x_radius` across it.
The coordinate inversion trick (`eori.w #$F`) plus a sign-flip mask in `d6` (`$800` for ceiling probes of
`FindFloor`, `$400` for left probes of `FindWall`, `0` for down/right) lets ONE probe core serve both directions:
`d6` is `eor`'d into the block word before the y-flip/x-flip test, inverting the meaning of the flip bit and
therefore the sign of the height. `a3` carries `+$10` or `−$10` — the world step to the *next* 16×16 block
when the first block is empty or full.

Angle resolution after the pair: `Player_Angle` takes the closer sensor's angle; if it differs from the
current angle by ≥ `$20`, the angle snaps to the nearest cardinal (`angle = (angle+$20) & $C0`) — this is
what keeps the player stable running over jagged terrain.

Snap limits (grounded): snap up at most 14 px (`cmpi.w #-$E,d1; blt → ignore`); snap down at most
`min(|speed_along_axis| + 4, 14)` px unless `stick_to_convex` is set — beyond that the player goes airborne
(`bset in_air`). This is the classic "speed-scaled glue" that keeps fast players attached over convex curves.

### 1.3 When each sensor fires in the frame

Grounded, not rolling (`Sonic_MdNormal`, `Sonic.asm:359`):
1. `SonicKnux_Spindash`, `Sonic_Jump`, `Player_SlopeResist` (slope physics, no sensors)
2. `Sonic_Move` — **E/F push sensors** fire from inside it via `CalcRoomInFront` (`Sonic.asm:831`):
   probes at the **next-frame position** (`x_pos.l + x_vel<<8`, same for Y), at angle `angle ± $40`
   (sign from `ground_vel` direction). On hit (`d1 < 0`): velocity along the push axis is cancelled
   (`d1<<8` added back), `ground_vel` cleared, `pushing` status bit set. The grounded sensor sits 8 px
   below center on flat ground (`addq.w #8,d2` when `angle & $38 == 0`), raised 5 px when rolling.
3. `Player_LevelBound`, then `MoveSprite2_TestGravity` — position integration
4. `Call_Player_AnglePos` → `Player_AnglePos` — **A/B floor sensors**, post-integration, snap + angle update
5. `Player_SlopeRepel` — no sensors (angle/speed test that detaches from walls/ceilings when too slow)

`Sonic_MdRoll` is the same shape (push handled inside `Sonic_RollSpeed` via the same `CalcRoomInFront`).

Airborne (`Sonic_MdAir` / `Sonic_MdJump`): control + gravity + integration, `Player_JumpAngle`
(rotates `angle` back toward 0), then everything funnels into **`Player_DoLevelCollision`**
(`Sonic.asm:1876`), which classifies motion by `GetArcTan(x_vel, y_vel)` rounded to a quadrant
(`subi.b #$20; andi.b #$C0`) and runs only the sensors that face the motion:

| Moving mostly | Sensors run, in order |
|---|---|
| down (`$00`) | E (`CheckLeftWallDist` at `x−$A`), F (`CheckRightWallDist` at `x+$A`), then A/B (`Sonic_CheckFloor`). Landing accepted only if `d1 ≥ −(y_vel/256 + 8)` — embed tolerance scales with fall speed. Landing converts velocity: flat → `ground_vel = x_vel`; steep slope (angle within `$20` of cardinal ±`$40`) → `ground_vel = y_vel` (negated by angle sign), shallow slope → `y_vel >>= 1` first. |
| left (`$40`) | `Player_HitLeftWall`: E only, then C/D (`Sonic_CheckCeiling`), then A/B if moving down |
| up (`$80`) | `Player_HitCeilingAndWalls`: E and F, then C/D. Ceiling hit on a slanted ceiling quadrant re-attaches (lands on ceiling → `ground_vel = ±y_vel`); flat ceiling just zeroes `y_vel`. |
| right (`$C0`) | mirror of left |

Wall hits in air: `x_pos −= d1` (snap out) + `clr.w x_vel`. All airborne wall probes are at sensor
height `y + 0` (center).

### 1.4 The probe core: `FindFloor` / `FindWall` (block → tile → height → angle chain)

`FindFloor` (`Find Floor.asm:435`) — inputs: `d2/d3` = probe Y/X (world px), `d5` = solidity bit number,
`a3` = ±$10 step, `a4` = angle output address, `d6` = direction eor mask. Steps:

1. **Block fetch** — `GetFloorPosition_FG` (`:409`): walks layout row index (`y>>5`, masked) →
   128×128 chunk ID word → `chunk_id<<7 + (y&$70) + ((x>>3)&$E)` into decompressed chunk RAM →
   `a1` points at the 16-bit **block word** for the 16×16 block containing the probe point.
2. **Solidity gate** — `move.w (a1),d0; andi.w #$3FF` (block ID 0–1023); `btst d5,d4` tests the
   placement's solidity bit (see §2.2). Fail → treat as empty.
3. **Collision index** — `movea.l (Collision_addr).w,a2; add.w d0,d0; move.b (a2,d0.w)` →
   collision tile ID (0–255; 0 = no collision → empty). The `add.w d0,d0` is S&K's *interleaved*
   index: primary byte at even offsets, secondary at odd (`Load_Solids` sets
   `Secondary_collision_addr = Primary + 1`). (S2/sonic_hack instead keep two separate
   un-interleaved 768-byte RAM buffers and skip the doubling.)
4. **Angle** — `AngleArray[collision_id]` → `(a4)`. X-flip (`btst #$A` of block word): `not.w` the
   in-block column and negate the angle. Y-flip (`btst #$B`): column for walls / row inversion implied,
   angle reflected via `angle = −(angle+$40)−$40`.
5. **Height** — `HeightMaps[collision_id*16 + (x & $F)]` (or `HeightMapsRot[... + (y & $F)]` in
   `FindWall`), sign-extended. The `eor d6,d4` + flip-bit test negates the height for
   ceiling/left-facing probes.
6. **Distance** — three cases:
   - height 0 (or solidity/index failed) → **extend probe one block forward** (`add a3` to the probe
     axis, run `FindFloor2`, `+$10` to the result). `FindFloor2` is the identical body minus further
     extension — total reach is exactly 2 blocks.
   - height 16 (`$10`, full) → **extend one block backward** (`sub a3`, `FindFloor2`, `−$10`) — finds
     the true surface when the foot block is completely buried.
   - else → `d1 = $F − (height + (y & $F))` (floor), same with `x & $F` for walls.
   - negative height value `h` (−1..−15): solid hangs from the far edge — accepted only when
     `(probe & $F) + h` stays negative, else falls through to the empty case.
   So every sensor's distance range is **−16..+31 px** for one call.

`FindWall` is the same machine with X/Y roles swapped and `HeightMapsRot`.
S.C.E. extra (skippable for us): when `Background_collision_flag` is set, every probe runs twice —
FG layout then BG layout offset by `Camera_X/Y_diff` — and keeps the minimum (used for BG-plane terrain).
`Ring_FindFloor` is a simplified clone for dropped rings.

---

## 2. S.C.E./S3K collision data formats

### 2.1 Global per-tile data (zone-independent, in ROM)

| File (S.C.E.) | Size | Format |
|---|---|---|
| `Data/Misc/Floor/Height Maps.bin` (`HeightMaps`) | 4096 B | 256 profiles × 16 bytes; byte = signed height of that 1-px column, 0..16 up from the bottom; negative = solid hanging down from the top edge |
| `Data/Misc/Floor/Height Maps Rotated.bin` (`HeightMapsRot`) | 4096 B | same, but 16 bytes = rows, value = width from the left; the same 256 profiles pre-rotated 90° at build time so wall sensors never transpose at runtime |
| `Data/Misc/Floor/Angle Map.bin` (`AngleArray`) | 256 B | one angle byte per profile, S3K angle units (256 = full circle, `$00` flat floor, counter-clockwise). **Odd values are a flag**: "no usable angle" — callers `btst #0` and substitute the probe quadrant's cardinal. `$FF` marks full blocks/odd tiles. |

### 2.2 Per-placement data: solidity lives in the chunk map word

Block word (one per 16×16 block inside a 128×128 chunk definition):

```
bit 15..14  secondary-path solidity   (bit $E = top-solid, bit $F = left/right/bottom-solid)
bit 13..12  primary-path solidity     (bit $C = top-solid, bit $D = left/right/bottom-solid)
bit 11      y-flip
bit 10      x-flip
bit 9..0    16×16 block ID
```

Two independent 2-bit solidity fields = the **two collision layers**. `top` only ⇒ jump-through
platform; `lrb` only ⇒ ceilings/walls you can jump up through; both ⇒ fully solid. Solidity is a
property of *placement*, the height profile a property of the *block art* (via the index files) —
the same sloped block can be a platform in one chunk and fully solid in another.

### 2.3 Per-zone data: collision index (block ID → profile ID)

Per zone, one byte per 16×16 block per path: `block_id → collision_tile_id`. Kosinski-compressed in
ROM, decompressed to RAM at level load (S.C.E. `Load_Level` → `SolidRAM`, interleaved P/S;
sonic_hack `water.asm:210-220` KosDec's `zd_col_primary`/`zd_col_secondary` into separate
`Primary_Collision`/`Secondary_Collision` RAM buffers).

### 2.4 Layer switching

Two per-player SST bytes — `top_solid_bit` (`$C` or `$E`) and `lrb_solid_bit` (`$D` or `$F`), always
written as a pair. They do double duty:
1. **solidity bit number** for the `btst d5` gate (selects which 2-bit field of the block word applies), and
2. **collision index selector**: every sensor entry point does
   `cmpi.b #$C,top_solid_bit(a0); beq → Primary_collision_addr; else Secondary_collision_addr`
   into the global `Collision_addr` scratch pointer.

Path swappers (`Objects/Main/Path Swap/Path Swap.asm:121/124` etc.) are invisible line objects: when the
player crosses the line in the armed direction they write `bytes_to_word($C,$D)` or `($E,$F)` to
`top_solid_bit(a1)` (one 16-bit write flips both), optionally also flipping the *render* priority. That
is the whole mechanism — loops are two overlapping geometries selected per-object by two bit numbers.
Our per-object `SST_layer` (0/1) + per-plane cache bytes already model this more cleanly (no global
pointer, multi-actor safe) — confirmed conclusion of `docs/research/dual-layer-collision.md` §3.

---

## 3. Our substrate — what exists, what's placeholder, gap analysis

### 3.1 What `Tile_Cache_GetCollision` returns today

`engine/level/tile_cache.asm:71`: input world tile col (8 px units) / world tile row, `d3.b` = layer.
Resolves through the origin ring (`Cache_Left_Col`/`Cache_Origin_Col`, rows halved then offset by
`Cache_Origin_Row/2` — valid because Top/Origin rows are kept even), indexes
`Tile_Cache_Collision[row*80 + col (+2400 for plane B)]`, returns **one byte**.

**Cell geometry: 8 px wide × 16 px tall** — one byte per *tile column* per 16-px row
(`TILE_CACHE_COLS=80`, `TILE_CACHE_COLL_ROWS=30`, `constants.asm:286-292`). Note
`ENGINE_ARCHITECTURE.md` §4.7's example (`lsr.w #4,d0` for X) describes 16-px columns — **the code
is 8 px** (`collision_lookup.asm:20` does `lsr.w #3`). Doc needs a sync edit. Consequence for real
data: the two 8-px cells covering one world 16×16 block must carry the same byte (the generator emits
per-tile-column, so this holds automatically when both columns derive from the same block), and
`x & $F` sub-block columns still resolve correctly because blocks are 16-px aligned in world space.

**The byte today is a placeholder**: `tools/ojz_strip_gen.py:962 generate_collision_bytes` sets
`1` if either 8×8 nametable word in the cell has the **VDP priority bit** (bit 15) set, else `0`
(OJZ ground art is pri=1, sky pri=0). Plane B is a byte-for-byte copy of plane A
(`:982`). The collision index files are never read. `tools/ojz_block_gen.py` then just repacks those
strip bytes into the 768-byte blocks (512 B nametable + 128 B plane A + 128 B plane B,
`BLOCK_RAW_SIZE`, `constants.asm:304`), and `TileCache_FillRow/CopyBlockColumn` copy them into the
cache verbatim. So the entire downstream plumbing (blocks → staging → cache → `Tile_Cache_GetCollision`)
is **format-complete**; only the *content* of the byte is fake.

Runtime consumers that already exist (`engine/level/collision_lookup.asm`):
- `Collision_GetType` — engine-px → cache lookup with bounds check (air outside cache)
- `Collision_GetFloorHeight` — type → `HeightMaps[type*16 + (x&$F)]` → `d0 = 16 − height − (y&$F)`,
  angle from `AngleTable[type]` — the §4.7 distance formula, matching S.C.E.'s within one off-by-one
  convention (S.C.E. computes `$F − …` because its heights are relative to the block bottom; ours uses
  `16 − …` — must be reconciled when real profiles land, see §4.3)
- `Collision_GetFloorHeight_Wall` — same against `HeightMapsRot` with axes swapped
- `Collision_FloorSensors` — A/B pair from SST (`SST_x_pos ± width/2, SST_y_pos + height/2`), closer wins

And the ROM tables exist but are **stubs**: `main.asm:182-190` BINCLUDEs `data/collision/*.bin`
generated by `tools/gen_collision_data.py` — profile 0 = air, profile 1 = flat-full, everything else
zero; all angles zero. The HeightMapsRot stub is *not even rotated* (it's a copy of the flat stub).

### 3.2 What the real OJZ source data provides (sonic_hack, measured)

`/home/volence/sonic_hacks/sonic_hack/collision/`:

| File | ROM size | Decompressed / format |
|---|---|---|
| `OJZ primary 16x16 collision index.bin` | 140 B | **Kosinski** (loaded via `KosDec`, `water.asm:216` — the "not compressed" claim in `dual-layer-collision.md` is wrong) → **374 bytes**, one byte per 16×16 block, value = collision tile ID 0–255. 186 nonzero. 31 distinct nonzero profiles used. |
| `OJZ secondary 16x16 collision index.bin` | 138 B | Kosinski → **374 bytes**. Differs from primary at **46 blocks** — genuine path-B data (loop interiors). 28 distinct profiles. |
| `Collision array 1.bin` | 4096 B | 256 × 16 height profiles (S2 `ColArray`). OJZ uses **no negative heights** (all values 0..16; e.g. profile `$42` = `9,9,9,10,10,11,…,15`, `$FF` = all 16, `$01` = all 8 — a half-height floor). |
| `Collision array 2.bin` | 4096 B | rotated profiles (`ColArray+$1000` in `object_touch.asm:805`). **Does contain negative bytes** (`$F1–$FF` = −15..−1) — wall probes against right-anchored geometry need signed handling. |
| `Curve and resistance mapping.bin` | 256 B | angle per profile (S2 `ColCurveMap`). `angle[0]=$FF`, `angle[1]=$FF` (odd-flag), real slope values elsewhere (`$E0`, `$D0`, `$C8`, …). |

The placement side: `mappings/128x128/OJZ.bin` (Kosinski, 2 streams → 71 chunks × 64 words) carries
the block words exactly as §2.2 — measured usage: all four flip combos occur, and the dual solidity
fields are richly used (e.g. 98 placements top-solid-on-A-only, 249 fully-solid on both paths, 53
placements solid on path B but *empty* on path A — loop interior walls). Block IDs max out at 373,
matching the 374-entry index and the 374 blocks in `mappings/16x16/OJZ.bin`. **`ojz_strip_gen.py`
already decodes both files** (`load_chunk_map`/`load_block_map` with a working `kos_decompress`) but
explicitly drops bits 15..10 of the chunk word (docstring at `:262` mislabels them "priority
overrides" — they are xflip/yflip + the two solidity fields).

### 3.3 The exact pipeline work (§5 prerequisite)

The generator already walks layout → chunk word → block ID per 16-px cell to emit nametable words.
Real collision is the same walk keeping three more things per cell: the chunk word's flip bits,
its per-path solidity field, and `index[block_id]` per path. Conversion steps:

1. **Decompress the two index files** with the existing `kos_decompress` (374 B each).
2. **Resolve per cell, per path** (A from primary index + bits 12-13; B from secondary index +
   bits 14-15): `(profile_id, xflip, yflip, solidity)`. Cell is air if `solidity == 0` or
   `profile_id == 0`.
3. **Bake placement into the byte.** S.C.E. resolves flips and solidity at runtime from the block
   word; our sensors see only one byte, so the build must bake. Measured: OJZ has only **91 unique
   solid `(profile, xflip, yflip, solidity)` combos across both paths** — comfortably inside one
   byte. Recommended encoding: the cache byte is an index into a build-generated, deduplicated
   **collision attribute set**: emit a *synthesized profile* per combo —
   - xflip ⇒ reverse the 16 height bytes, negate the angle;
   - yflip ⇒ flip height semantics (`h → −h` for hanging geometry, angle `→ −(angle+$40)−$40`);
   - regenerate `HeightMapsRot` rows from the flipped vertical profile (never trust the source
     rotated array for flipped placements);
   - reserve 2 high bits of the byte for solidity (`%01` top-only, `%10` lrb-only, `%11` all),
     leaving 6 bits = 64 profile slots ≥ the measured need — **or** keep all 8 bits as attr-set
     index and store solidity as a per-entry byte in a parallel 256-byte `SolidityTable`. The second
     costs one extra ROM table + one indexed load per probe but keeps 256 profile head-room and a
     simpler generator; either fits the data.
4. **Regenerate `data/collision/*.bin`** from `Collision array 1/2.bin` + `Curve…bin` through the
   attr-set remap (replacing `gen_collision_data.py`'s stubs), preserving the odd-angle-flag
   convention.
5. **Emit per 8-px cell**: both tile columns of a block get the same byte; plane A and plane B bytes
   now genuinely differ. Block/strips/cache formats are untouched — this is generator-content-only,
   exactly the deferred work flagged in `ojz_strip_gen.py:969` and `dual-layer-collision.md` §2.

### 3.4 Gap list (runtime, beyond data)

| Gap | S.C.E. behavior | Our current state |
|---|---|---|
| Two-block probe extension | empty → +16 px probe, full → −16 px probe; range −16..+31 | `Collision_GetFloorHeight` probes **one** cell; air returns sentinel `$7F`, full block returns `−(y&$F)` with no back-probe — sensors will jitter on block seams and tunnel at >16 px/frame |
| Solidity filtering | `btst d5` per placement, top vs lrb | none — byte is profile-only; encode per §3.3 step 3 and gate per sensor class (floor sensors accept top+all; wall/ceiling accept lrb+all) |
| Ceiling / left-wall directions | same cores via coordinate inversion + `d6` eor mask | only down (`GetFloorHeight`) and one wall direction exist; need 4 directional wrappers (build them as thin entry points over one core, S.C.E.-style, or four straight-line variants — decide in §5 design) |
| Negative heights | handled in probe core (`bmi` branch) | `ext.w` is done but the accept/reject rule (`(sub + h) < 0`) is absent; required for `Collision array 2` content |
| Angle odd-flag | `btst #0` → substitute quadrant cardinal | absent; `AngleTable` stub is all zeros so it's currently invisible |
| Speed-scaled snap-down, angle cardinal-snap | `Player_Angle` + the `min(|vel|+4,14)` clamp | player-side, not substrate — belongs to §5 proper |
| `ENGINE_ARCHITECTURE.md` §4.7 | — | says 16-px collision columns; code is 8-px. Sync when touching §4.7 |

### 3.5 Register-convention note

`collision_lookup.asm` header: `d3.b` = layer on **every** entry, X/Y saved in `d4/d5`, `d3` not
preserved by contract. New §5 sensor wrappers must keep this. `Collision_FloorSensors` shows the
pattern (movem-save around the first probe).

---

## 4. Sensor-to-tile-cache mapping and required API extensions

### 4.1 How the lookup composes with the world-space ring cache

S.C.E. probes ROM layout + chunk RAM — unlimited range. We probe a sliding 640×480 px ring buffer.
The composition chain for one sensor:

```
engine px (SST domain)
  → Collision_GetType: lsr #3 / Engine_To_World_Col/Row (origin ring + section rebase)
  → bounds vs Cache_Left_Col/Head_Col/Top_Row/Bottom_Row  (outside → air)
  → Tile_Cache_GetCollision: ring remap, row halve, plane select → type byte
  → HeightMaps[type*16 + (x & $F)]  (sub-block px resolution comes from the RAW engine
    coordinate, NOT the cache index — the cache only ever resolves to a 16-px cell;
    the &$F masks recover the intra-cell pixel)
  → distance + AngleTable[type]
```

This already works because world blocks are 16-px aligned and `Cache_Top_Row` is forced even, so
`(engine_y & $F)` ≡ position within the collision cell. **Invariant to protect in §5: every coordinate
the player physics feeds to sensors must be in the same engine-px domain as `SST_x_pos`** — teleport
rebases (pure-rebase model) keep `x & $F` stable since `SECTION_SHIFT` is a multiple of 16.

Cache coverage vs sensor reach: margins are 160 px horizontal / 128 px vertical beyond the viewport;
max sensor excursion is half-height + probe extension ≈ 36 px from the player, who sits near the
camera center — no realistic way to probe outside a healthy cache. The out-of-bounds → air fallback
still wants a debug assert in DEBUG builds (silent air is how players fall through the world during
streaming bugs, cf. the SEC_VOID lesson).

### 4.2 API surface §5 needs (extensions, not rewrites)

Existing per §3.1. To support the full 6-sensor model:

1. **`Collision_ProbeDown` / `Up` / `Left` / `Right`** — directional cores wrapping
   `Collision_GetType` + height resolution **with the two-block extension** (§3.4 row 1) and the
   negative-height rule. Each takes engine X/Y + layer (`d3`), returns S.C.E.-protocol
   `dist.w / angle.b / type.b`, range −16..+31. Up/Left negate height semantics — decide between
   S.C.E.'s shared-core-with-eor-mask (smaller) and four specialized routines (faster, no mask
   plumbing); with `function`-generated code AS can stamp four variants from one macro at zero
   runtime cost, which is the conventions-preferred answer.
2. **Solidity gate parameter** — sensor class bit(s) in a register or per-wrapper constant, tested
   against the encoded solidity before height lookup (replaces `btst d5`).
3. **Pair wrappers** — `Collision_FloorSensors` exists; need `CeilingSensors`, `WallSensor`
   (single, ±10 px convention), and mode-rotated variants used by the grounded state (the §1.2
   table). Closer-wins + angle-resolution (cardinal snap on odd/divergent angle) policy lives here.
4. **`Collision_GetHeightAtColumn`** (cheap variant): type byte → height, no distance math — wanted
   by objects (rolling monitors, badnik edge checks `ChkFloorEdge`-style) that only ask "is there
   floor at this exact column".
5. **Velocity-projected probe entry** — accept a pre-offset position (next-frame), used by the
   grounded push sensors; no new mechanism, just a documented entry that skips the SST fetch.

Total new substrate ≈ the directional cores + the data pipeline of §3.3. The cache, the layer
model, the lookup math, and the ROM table slots are already in place and verified by the priority-bit
placeholder; nothing in the §4.7 architecture needs to move.
