# §5 Player System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A classic-faithful playable Sonic (S2 values + verified S3K behavior) on OJZ with real collision data, full sensor system, ground/air/roll/spindash states, and camera landing lock.

**Architecture:** Generator-only collision pipeline bakes sonic_hack placement data into the existing one-byte cache format (attr-set + SolidityTable). New `engine/player/` layer: macro-stamped directional sensor cores over `collision_lookup.asm`, a flat state machine in `player_common.asm` with Enter/Exit hooks, Sonic-specific tables in `sonic.asm`. Player stays a standard SST object in `Player_1`; physics read through an effective-table-in-RAM (a4 convention) refreshed on section change.

**Tech Stack:** Motorola 68000 (AS assembler), Python 3 generators, Exodus MCP for live verification.

**Authority documents** (read before implementing a task; cite-level details live there, NOT re-derived here):
- Spec: `docs/superpowers/specs/2026-06-12-player-system-design.md`
- Values & behaviors: `docs/research/player-physics-classics.md` (quick-reference card at bottom), `player-feel-modern.md` (§1 constants, §2 sensor spec, §4 bug table)
- Sensor architecture: `docs/research/player-sensors-sce.md` (§1.4 probe core, §3.3 pipeline steps, §3.4 gap list, §4.2 API surface)
- Structure: `docs/research/player-structure-refs.md` (§2.2 SST field budget)
- Conventions: `CODING_CONVENTIONS.md` (function/struct/phase, explicit branch sizing, register conventions)

**Engine contracts that MUST be honored (verified against current code):**
- Object routines preserve `a0`/`d7` (RunObjects loop — see the d4-not-d7 comment in `objects/test_player.asm:69-73`)
- Collision entries: `d3.b` = layer on EVERY call, X/Y saved in d4/d5, d3 not preserved (header of `engine/level/collision_lookup.asm`)
- `SST_x_pos`/`SST_y_pos` are 16.16 longs; `SST_x_vel`/`y_vel` 8.8 words; status bits `ST_*` at `constants.asm:171-180`
- Tile cache collision cells are **8px wide × 16px tall**, one byte each; sub-block pixel comes from raw engine coordinate `& $F`
- RAM: upper RAM is `.w`-addressed via `phase $FFFF8000` in `ram.asm`; add player RAM there with explicit even-padding
- `Player_1` slot setup happens in `test/ojz_scroll_test.asm` (`GameState_OJZScroll_Init`)

---

## Task 0: Branch hygiene & plan tracking

**Files:** none (process)

- [x] **Step 0.1:** Confirm on branch `player-system` in `/home/volence/sonic_hacks/s4_engine` (`git branch --show-current`). All commits for this plan go here. NEVER `git add` the modified `data/editor/**` files (user's level edits, uncommitted by design) — always add files explicitly, never `git add -A`.
- [x] **Step 0.2:** Baseline: run `./test.sh` — record pass count. Run `./build.sh -pe` — must succeed before any change.

---

## Task 1: Collision attr-set module (Python, pure functions + self-tests)

Builds the bake logic as an importable module with zero file I/O in the core functions, so it's unit-testable.

**Files:**
- Create: `tools/collision_pipeline.py`
- Modify: `test.sh` (add self-test section after "6. OJZ Strip Generator Self-Tests")

- [x] **Step 1.1: Write the module with self-tests inline.** Core API (signatures are the contract):

```python
#!/usr/bin/env python3
"""Collision attr-set pipeline (§5 Task 1).

Bakes sonic_hack per-placement collision (profile, xflip, yflip, solidity)
into one-byte attr-set indices + ROM tables. See
docs/superpowers/specs/2026-06-12-player-system-design.md §4 and
docs/research/player-sensors-sce.md §3.3.
"""
import struct

SOL_NONE, SOL_TOP, SOL_LRB, SOL_ALL = 0, 1, 2, 3

def flip_profile_x(heights: bytes) -> bytes:
    """xflip: reverse the 16 per-column heights."""
    return bytes(reversed(heights))

def flip_profile_y(heights: bytes) -> bytes:
    """yflip: solid now hangs from the top edge. 0→0, 16→16 (full stays
    full), else h → 256-h (two's-complement negative byte = hanging depth)."""
    return bytes(h if h in (0, 16) else (256 - h) & 0xFF for h in heights)

def flip_angle_x(angle: int) -> int:
    """Negate angle; odd-flag values stay odd (e.g. $FF → $01)."""
    return (-angle) & 0xFF

def flip_angle_y(angle: int) -> int:
    """Reflect: -(angle+$40)-$40 == -angle-$80."""
    return (-angle - 0x80) & 0xFF

def rotate_profile(heights: bytes) -> bytes:
    """Regenerate the rotated (wall) profile from a vertical profile.
    rotated[row] = solid width at 16px-block row `row` (0 = TOP row),
    measured from the LEFT edge, by counting columns whose vertical solid
    span covers that row. Positive h covers rows [16-h, 15] (bottom-up);
    negative h (hanging, depth d=|h|) covers rows [0, d-1]; h==16 covers all.
    Result per row: number of solid columns counted from the left until the
    first non-solid column (contiguous-from-left width). If the solid run is
    anchored at the RIGHT edge instead, emit negative width (256-w) per the
    Collision array 2 convention. If a row's solid is neither edge-anchored
    (floating middle span), anchor to the nearer edge — OJZ profiles are
    monotonic ramps/walls, this case doesn't occur in measured data
    (assert + count in self-test)."""
    out = bytearray(16)
    for row in range(16):
        solid = [covers(h, row) for h in heights]   # see covers() below
        if not any(solid):
            out[row] = 0
        elif all(solid):
            out[row] = 16
        elif solid[0]:                    # anchored left
            w = 0
            while w < 16 and solid[w]: w += 1
            out[row] = w
        elif solid[15]:                   # anchored right → negative
            w = 0
            while w < 16 and solid[15 - w]: w += 1
            out[row] = (256 - w) & 0xFF
        else:
            raise ValueError("floating solid span — unsupported profile")
    return bytes(out)

def covers(h: int, row: int) -> bool:
    """Does signed height byte h cover block row `row` (0 = top)?"""
    if h == 0:   return False
    if h == 16:  return True
    if h < 0x80: return row >= 16 - h          # bottom-anchored
    return row < (256 - h)                      # hanging, depth 256-h

class AttrSet:
    """Deduplicated (heights, angle, solidity) → byte index. Index 0
    reserved for air."""
    def __init__(self):
        self.entries = [(bytes(16), 0x00, SOL_NONE)]   # 0 = air
        self.lookup = {}
    def intern(self, heights: bytes, angle: int, solidity: int) -> int:
        key = (heights, angle, solidity)
        if key in self.lookup: return self.lookup[key]
        idx = len(self.entries)
        if idx > 255: raise ValueError("attr-set overflow (>255 entries)")
        self.entries.append(key)
        self.lookup[key] = idx
        return idx

def bake_cell(block_word: int, index_a: bytes, index_b: bytes,
              profiles: bytes, angles: bytes, attrset: AttrSet) -> tuple[int, int]:
    """One 16×16 placement → (path_a_byte, path_b_byte).
    block_word: chunk-entry word (bits 9:0 id, 10 xflip, 11 yflip,
    13:12 path-A solidity [bit12=top, bit13=lrb], 15:14 path-B solidity)."""
    block_id = block_word & 0x3FF
    xf = bool(block_word & 0x0400)
    yf = bool(block_word & 0x0800)
    out = []
    for index, sol_shift in ((index_a, 12), (index_b, 14)):
        sol = (block_word >> sol_shift) & 3
        prof_id = index[block_id] if block_id < len(index) else 0
        if sol == SOL_NONE or prof_id == 0:
            out.append(0); continue
        heights = profiles[prof_id*16:(prof_id+1)*16]
        angle = angles[prof_id]
        if xf: heights, angle = flip_profile_x(heights), flip_angle_x(angle)
        if yf: heights, angle = flip_profile_y(heights), flip_angle_y(angle)
        out.append(attrset.intern(heights, angle, sol))
    return out[0], out[1]

def emit_tables(attrset: AttrSet) -> dict[str, bytes]:
    """ROM tables: heightmaps (256×16), heightmaps_rot (256×16),
    angles (256), solidity (256). Unused slots zero."""
    hm, hmr, ang, sol = bytearray(4096), bytearray(4096), bytearray(256), bytearray(256)
    for i, (heights, angle, solidity) in enumerate(attrset.entries):
        hm[i*16:(i+1)*16] = heights
        hmr[i*16:(i+1)*16] = rotate_profile(heights)
        ang[i] = angle
        sol[i] = solidity
    return {"heightmaps.bin": bytes(hm), "heightmaps_rot.bin": bytes(hmr),
            "angles.bin": bytes(ang), "solidity.bin": bytes(sol)}
```

Plus loader helpers (file I/O kept separate): `load_collision_sources(sonic_hack_dir)` returning `(index_a, index_b, profiles, angles)` — index files Kosinski-decompressed via `ojz_strip_gen.kos_decompress` (import it; do NOT duplicate the decompressor), from:
  - `collision/OJZ primary 16x16 collision index.bin` → 374 bytes
  - `collision/OJZ secondary 16x16 collision index.bin` → 374 bytes
  - `collision/Collision array 1.bin` (4096 B profiles)
  - `collision/Curve and resistance mapping.bin` (256 B angles)

- [x] **Step 1.2: Self-tests** (`python3 tools/collision_pipeline.py test`), covering at minimum:

```python
def test_flip_x_reverses():        # synthetic ramp 1..16 reversed
def test_flip_y_negates():         # h=4 → 0xFC; 0 and 16 unchanged
def test_angle_flips():            # flip_angle_x(0x20)==0xE0; odd stays odd;
                                   # flip_angle_y(0x20)==0x60... (compute: -0x20-0x80 = -0xA0 & 0xFF = 0x60)
def test_covers_semantics():       # h=4 covers rows 12-15 only; h=0xFC (depth 4) covers rows 0-3
def test_rotate_flat_full():       # all-16 profile → rotated all-16
def test_rotate_ramp():            # heights [1]*16... pick a hand-computed 45° ramp case
def test_attrset_dedup_and_air():  # same combo interned once; index 0 is air
def test_bake_cell_solidity_gate():# sol=0 → 0 even with profile; per-path independence
def test_real_data_measurement():  # load real sonic_hack files; assert
                                   # len(index)==374 both paths; assert
                                   # attr count after baking ALL OJZ sections <= 255
                                   # and print the count (expect ≈91 per research)
```

The real-data test needs the chunk walk — import `load_chunk_map`/`load_layout` from `ojz_strip_gen` and iterate every `OJZ_1_sec*.bin` layout (paths/constants already defined at the top of `ojz_strip_gen.py` — reuse `SONIC_HACK`, `CHUNK_MAP_PATH`, `LAYOUT_DIR`).

- [x] **Step 1.3:** Run `python3 tools/collision_pipeline.py test` — all pass, note printed attr count.
- [x] **Step 1.4:** Add to `test.sh` after section 6:

```bash
section "6b. Collision Pipeline Self-Tests"
if python3 "${TOOLS}/collision_pipeline.py" test; then
    pass_test "Collision pipeline self-tests"
else
    fail_test "Collision pipeline self-tests"
fi
```

- [x] **Step 1.5:** Run `./test.sh` — all sections pass. Commit: `feat(§5): collision attr-set pipeline — bake placement into one-byte indices`

---

## Task 2: Wire real collision into strips + ROM tables

**Files:**
- Modify: `tools/ojz_strip_gen.py` (`generate_collision_bytes`, `write_strips_to_file`, `generate()`)
- Modify: `tools/gen_collision_data.py` (emit from attr-set instead of stubs)
- Modify: `main.asm:188-190` region (add SolidityTable BINCLUDE)
- Modify: `build.sh` if `gen_collision_data.py` isn't already invoked there (check; wire so collision tables regenerate before assembly)

- [x] **Step 2.1:** In `ojz_strip_gen.py`, build per-section collision grids from **sonic_hack data in BOTH modes** (editor mode included — same pattern as Pass 6b BG, which loads sonic_hack chunks/blocks when `use_editor`). New function:

```python
def build_section_collision(layout, chunks, index_a, index_b, profiles, angles, attrset):
    """Per tile column (8px) × collision row (16px): bake to (a_byte, b_byte).
    Section = 16×16 chunks = 256 tile cols × 128 collision rows.
    cell(tile_col, coll_row): chunk_col=tile_col//16, chunk_row=coll_row//8,
    block_col=(tile_col%16)//2, block_row=coll_row%8,
    word = chunks[layout[chunk_row][chunk_col]][block_row*8+block_col].
    BOTH 8px tile columns of one block share the block's baked bytes."""
```

`write_strips_to_file(strips, path, coll_a=None, coll_b=None)` — when grids provided, write real bytes instead of `generate_collision_bytes` output; keep the priority-bit fallback ONLY when sonic_hack collision files are missing (warn loudly). `generate()` threads one shared `AttrSet` across all 12 sections, then calls `collision_pipeline.emit_tables(attrset)` writing `data/collision/*.bin` — this REPLACES the stub generator output, and `gen_collision_data.py` becomes a thin CLI wrapper around the same emit (stub path deleted).

- [x] **Step 2.2:** Self-test additions to `ojz_strip_gen.py` `run_tests()`: `test_section_collision_sec0()` — bake sec0, assert: plane A ≠ plane B somewhere iff sec0 contains any of the 46 differing blocks (compute from indices, don't hardcode); assert all bytes < attr count; assert both 8px columns of block 0 match.
- [x] **Step 2.3:** Run `python3 tools/ojz_strip_gen.py test` then `python3 tools/ojz_strip_gen.py generate` — regenerates strips + `data/collision/*.bin`. Then `./build.sh -pe` — ROM builds.
- [x] **Step 2.4:** Add `SolidityTable:` BINCLUDE next to `AngleTable` in `main.asm`:

```asm
SolidityTable:
    BINCLUDE "data/collision/solidity.bin"
```

- [x] **Step 2.5: Live verify (Exodus MCP).** Load `s4.bin`, enter the OJZ state, toggle OUT of debug-fly (B button) and confirm the test player still lands on ground (it uses `Collision_FloorSensors` → now real heights). Walk onto a slope area — player will sink/float oddly into slopes (no angle handling yet — EXPECTED, note it, don't fix here). Verify no crash + flat ground level identical to before.
- [x] **Step 2.6:** Sync `ENGINE_ARCHITECTURE.md` §4.7: 8-px columns (not 16), real data note. Commit: `feat(§5): real OJZ collision data through strips + ROM tables — placeholder retired`

---

## Task 3: Input accumulation + player RAM + constants

**Files:**
- Modify: `engine/controllers.asm`, `engine/game_loop.asm`, `ram.asm`, `constants.asm`

- [x] **Step 3.1:** VBlank-latched press edges (research feel-modern §5). `Read_Controllers` ORs computed edges into accumulator bytes (`Ctrl_1_Press_Accum`/`Ctrl_2_Press_Accum`, declared next to the Ctrl block in `ram.asm`):

```asm
        or.b    d1, (Ctrl_1_Press_Accum).w  ; accumulate across lag frames
```

The non-lag handler (`VInt_Level`) — and ONLY it, never `VInt_Lag` — latches the accumulator into `Ctrl_*_Press` immediately after its `Read_Controllers` call, then clears the accumulator. `GameLoop` does NOT clear anything: consumers read a tick-stable `Ctrl_*_Press` that the next non-lag VBlank replaces wholesale.

Why a latch instead of an end-of-tick `GameLoop` clear: lag VBlanks fire mid-tick AFTER the player object has already consumed input (RunObjects runs early in the tick; the lag-prone streaming/render work runs after), so an end-of-tick clear wipes the edges those lag frames accumulated — the common lag case loses the press. With the latch, lag frames only OR into the accumulator, so a press landing in ANY lag frame survives into the next tick's latch. Consume-once with zero race: the latch runs in interrupt context while the main loop is parked in `VSync_Wait`.

Also mask opposing D-pad (bug #10) right after each pad read in `Read_Controllers`:

```asm
        ; L+R / U+D guard (worn pads) — if both bits set, clear both
        move.b  d0, d1
        andi.b  #BUTTON_LEFT|BUTTON_RIGHT, d1
        cmpi.b  #BUTTON_LEFT|BUTTON_RIGHT, d1
        bne.s   .lr_ok
        andi.b  #~(BUTTON_LEFT|BUTTON_RIGHT)&$FF, d0
.lr_ok: ; same pattern for UP|DOWN
```

- [x] **Step 3.2:** `constants.asm` — player constants block (all values from the spec §6 table; named per sonic_hack convention):

```asm
; -----------------------------------------------
; Player physics (§5) — 8.8 fixed point. Reference:
; docs/superpowers/specs/2026-06-12-player-system-design.md §6
; order of these eight must match Player_Phys field order (ram.asm) —
; block-copied by Player_RefreshPhysics
; -----------------------------------------------
PHYS_ACCEL              = $C
PHYS_DECEL              = $80
PHYS_FRICTION           = $C
PHYS_TOP_SPEED          = $600
PHYS_GRAVITY            = $38
PHYS_JUMP_FORCE         = $680
PHYS_AIR_ACCEL          = $18
PHYS_JUMP_RELEASE_CAP   = -$400
PHYS_GSP_CAP            = $1000     ; tunneling guard — see FEEL DEVIATION note (spec §2.1)
PHYS_FALL_CAP           = $1000
PHYS_SLOPE_WALK         = $20
PHYS_SLOPE_ROLL_DOWN    = $50
PHYS_SLOPE_ROLL_UP      = $14
PHYS_SLOPE_STAND_MIN    = $D        ; S3K standing slope-factor gate
PHYS_ROLL_FRICTION      = $6
PHYS_ROLL_DECEL         = $20
PHYS_ROLL_START_MIN     = $100      ; S3K
PHYS_UNROLL_MAX         = $80       ; S3K
PHYS_ROLL_FORCE_MIN     = $200
PHYS_KEEP_ROLL_MIN      = $400
PHYS_SLIP_SPEED         = $280
PHYS_SLIP_ANGLE         = $18       ; S3K slip threshold
PHYS_FALL_ANGLE         = $30       ; S3K detach threshold
PHYS_SLIP_NUDGE         = $80
PHYS_MOVE_LOCK_TIME     = 30
PHYS_SKID_MIN           = $400
PHYS_JUMP_BUFFER        = 2         ; frames — the one modern concession
SPINDASH_BASE           = $800
SPINDASH_CHARGE_STEP    = $200
SPINDASH_CHARGE_MAX     = $800
; Radii (SPG): sizes are 2r+1
PLAYER_X_RADIUS         = 9
PLAYER_Y_RADIUS         = 19
BALL_X_RADIUS           = 7
BALL_Y_RADIUS           = 14
PUSH_RADIUS             = 10        ; constant, never x_radius
CURL_Y_SHIFT            = 5         ; y_pos += on curl, -= on uncurl
; Player states (PSTATE_* — jump table indices ×2)
PSTATE_GROUND           = 0
PSTATE_ROLL             = 2
PSTATE_SPINDASH         = 4
PSTATE_AIR              = 6         ; airborne uncurled — no release cap
PSTATE_JUMP             = 8         ; airborne curled from jump — release cap
PSTATE_ROLLJUMP         = 10        ; as JUMP + air control lock
PSTATE_AIRBALL          = 12        ; airborne curled, not from jump
; Solidity classes (SolidityTable values; generator contract)
SOLID_NONE              = 0
SOLID_TOP               = 1
SOLID_LRB               = 2
SOLID_ALL               = 3
```

- [x] **Step 3.3:** `ram.asm` — player globals in upper RAM (after the Camera block is fine), history rings 256-aligned:

```asm
; -----------------------------------------------
; Player (§5)
; -----------------------------------------------
; Effective physics table — recomputed by Player_RefreshPhysics on
; section change / status events, NEVER per-frame. a4 points here
; during player movement code (classic convention).
Player_Phys:
Phys_accel:             ds.w 1
Phys_decel:             ds.w 1
Phys_friction:          ds.w 1
Phys_top_speed:         ds.w 1
Phys_gravity:           ds.w 1
Phys_jump_force:        ds.w 1
Phys_air_accel:         ds.w 1
Phys_release_cap:       ds.w 1
Player_Phys_End:

Player_Quadrant:        ds.b 1      ; (angle+$20)>>6, derived once per frame
Player_JumpBuffer:      ds.b 1      ; frames remaining on buffered jump press

; Position/stat history rings (Tails follow + trails later; recorded NOW)
; MUST be 256-aligned: index wraps via low-byte increment.
; NOT `align 256` — inside a phase block, align pads the UNPHASED location
; counter, so the phased address is only aligned by coincidence. Pad
; explicitly from the phased address (AS needs `(*)`) and assert:
        ds.b (256-((*)&255))&255    ; pad phased address to 256 boundary
Player_Pos_Ring:        ds.b 256    ; 64 × (x.w, y.w)
Player_Stat_Ring:       ds.b 256    ; 64 × (input.w, status.b, pad.b)
Player_Ring_Index:      ds.w 1      ; byte offset, low-byte wrap

    if Player_Pos_Ring&$FF
      error "Player_Pos_Ring not 256-aligned — low-byte index wrap breaks"
    endif
```

(The rings live at the RAM tail, just before `RAM_End`, so the padding wastes nothing in the middle of the layout. If padding pushes RAM_End past SYSTEM_STACK the build error catches it — current usage has headroom.)

- [x] **Step 3.4:** `./build.sh -pe` passes. Commit: `feat(§5): input edge accumulation, player RAM, physics constants`

---

## Task 4: Sensor cores (`engine/player/player_sensors.asm`)

**Files:**
- Create: `engine/player/player_sensors.asm`
- Modify: `main.asm` (include after `engine/level/collision_lookup.asm`)

The four directional cores replace direct `Collision_GetFloorHeight*` use for the player. Contract per core (S.C.E. protocol, research sensors §1.1/§4.2):

```
In:  d0.w = engine X px, d1.w = engine Y px, d3.b = layer,
     d6.b = sensor solidity class mask (SOLID_TOP for floor-class,
            SOLID_LRB for wall/ceiling-class — accepted when
            SolidityTable value & d6 != 0 or value == SOLID_ALL)
Out: d0.w = signed distance (−16..+31; ≥16 ⇒ nothing found),
     d1.b = surface angle (odd-flag already replaced by caller quadrant? NO —
            odd flag returned raw; PAIR wrappers do cardinal substitution),
     d2.b = attr byte (0 = air)
Clobbers: d0-d5, a1 (a0 preserved — player SST stays in a0 at call sites)
```

- [x] **Step 4.1:** Write the probe macro, stamped four ways. Skeleton (Down shown complete; the macro parameterizes axis/table/sign — implement per research sensors §1.4 semantics):

```asm
; probe_core dir, table, subreg_mask_coord, step_sign
; Down: probes at (X,Y); empty→re-probe (X,Y+16) dist+16; full→re-probe (X,Y−16) dist−16
Collision_ProbeDown:
        movem.w d0-d1, -(sp)               ; raw coords for sub-pixel recovery
        bsr.w   Collision_GetType          ; d0.b = attr (d3 layer threaded)
        ; solidity gate
        moveq   #0, d1
        move.b  d0, d1
        beq.s   .empty_extend              ; air → forward probe
        lea     (SolidityTable).l, a1
        move.b  (a1, d1.w), d2
        cmpi.b  #SOLID_ALL, d2
        beq.s   .solid_ok
        and.b   d6, d2
        beq.s   .empty_extend              ; wrong class → treat as air
.solid_ok:
        ; height lookup: HeightMaps[attr*16 + (rawX & $F)]
        ...                                ; (full math as in Collision_GetFloorHeight,
                                           ;  but with the THREE-CASE rule:)
        ; h == 0      → .empty_extend
        ; h == 16     → .full_backprobe    (re-probe one block back, dist −16)
        ; h negative  → accept iff (subY + h) < 0 else .empty_extend
        ; else        → dist = 16 − h − subY ; angle = AngleTable[attr]
        ...
.empty_extend:
        ; second probe one block forward (+16 on probe axis), SAME body minus
        ; further extension; on found: dist += 16. On air again: d0 = 32
        ; ("nothing"), d1 = 0, d2 = 0.
        ...
.full_backprobe:
        ; second probe one block back (−16); on found: dist −= 16.
        ; If STILL full: dist = −(subY) − 16 (deeply embedded).
        ...
```

Implement as ONE macro `sensor_core` with arguments for: probe axis (X/Y), height table (HeightMaps/HeightMapsRot), sub-coordinate sources, sign handling for Up/Left (height semantics negated — S.C.E. d6-eor equivalent done at assembly time, research sensors §1.2 table), then:

```asm
Collision_ProbeDown:   sensor_core DOWN
Collision_ProbeUp:     sensor_core UP
Collision_ProbeRight:  sensor_core RIGHT
Collision_ProbeLeft:   sensor_core LEFT
```

Each stamped core ends `rts`; total ≈4×120 bytes — ROM is cheap, cycles aren't.

- [x] **Step 4.2:** Pair + single wrappers (player-facing API; all take a0 = player SST):

```asm
; Player_SensorFloor    — A/B pair at (x ± x_rad, y + y_rad), rotated by
;                         Player_Quadrant (4 cases: down/right/up/left probes
;                         with radii roles swapped per research sensors §1.2).
;                         Closer (smaller dist) wins, tie → A.
;                         Out: d0 dist, d1 angle (odd-flag/divergence≥$20 →
;                         snapped to quadrant cardinal HERE), d2 attr.
; Player_SensorCeiling  — C/D mirror of floor pair.
; Player_SensorWall     — single probe at (x ± PUSH_RADIUS, y + d5.w offset),
;                         direction from d4 sign. Used grounded (next-frame
;                         projected position, +8px y when angle==0, −5 rolling)
;                         and airborne (y+0, post-move).
```

Radii read from `SST_width_pixels/height_pixels` — the state hooks keep those equal to 2r+1 values (Task 5), so half = r.

- [x] **Step 4.3:** DEBUG-build sensor self-check, run once at level init (`ifdef __DEBUG__`): probe 4-6 known sec0 positions (flat ground top, inside ground, air, one slope) and `trap #0`-style assert via the error handler on mismatch. Expected values: generate by adding a `--probe X Y` debug mode to `collision_pipeline.py` that prints the baked attr/height for a coordinate, run it for the chosen points, hardcode the expectations table in the asm with a comment citing the command. (Keeps asm and generator honest against each other.)
- [x] **Step 4.4:** `./build.sh -pe` + boot in Exodus, confirm self-check passes (no assert) and test player still lands. Commit: `feat(§5): directional sensor cores with extension, solidity gates, negative heights`

---

## Task 5: Player skeleton — state machine, GROUND state, flat movement

**Files:**
- Create: `engine/player/player_common.asm`, `engine/player/sonic.asm`
- Modify: `main.asm` (includes after `engine/player/player_sensors.asm`), `test/ojz_scroll_test.asm` (spawn `Player_Init` instead of TestPlayer for the player slot; keep debug-flag start), `objects/test_player.asm` (no longer the player's brain — leave file; the debug-fly moves INTO player_common as a state-suspend)

- [x] **Step 5.1:** SST overlay (in `player_common.asm`), per research structure-refs §2.2:

```asm
PlayerV struct
ground_speed    ds.w 1      ; inertia — single source of truth on ground
player_state    ds.b 1      ; PSTATE_* (jump-table offset)
status_secondary ds.b 1     ; speedshoes/etc. (reserved bits, 0 for now)
move_lock       ds.w 1      ; input-freeze frames (slip/spring channel)
spindash_charge ds.w 1
flip_angle      ds.b 1      ; visual rotation (springs/ramps — reserved)
air_left        ds.b 1      ; (reserved — no water yet)
invuln_time     ds.b 1      ; (reserved)
stick_convex    ds.b 1      ; flag: S-tunnel full adherence (objects set it)
PlayerV endstruct
        objvarsCheck PlayerV_len
_pl_gsp         = SST_sst_custom+PlayerV_ground_speed
_pl_state       = SST_sst_custom+PlayerV_player_state
...
```

(DPLC pair stays out — `sonic.asm` supplies `lea DPLC_Sonic,a2 / lea Art_Sonic,a3` as immediates, per spec §3.2.)

- [x] **Step 5.2:** Frame skeleton + dispatch in `player_common.asm`:

```asm
; Player_Init — set up Player_1 as Sonic (called from level state init)
;   mappings/art/anims = the existing Sonic test assets (Map_Sonic etc.)
;   width/height = 2*PLAYER_X_RADIUS+1 / 2*PLAYER_Y_RADIUS+1
;   state = PSTATE_AIR (drop to ground on frame 1), layer = 0
;   bsr Player_RefreshPhysics (identity: copies PHYS_* constants → Player_Phys)
;   code_addr = objroutine(Player_Main)

Player_Main:
        ; debug-fly toggle (B) — moved from test_player; when active, runs
        ; TestPlayer_Debug movement and SKIPS everything below (obj_control
        ; escape hatch). Re-entry: force PSTATE_AIR, clear velocities.
        ...
        lea     (Player_Phys).w, a4        ; physics table convention
        ; quadrant — first-class derived value
        move.b  SST_angle(a0), d0
        addi.b  #$20, d0
        lsr.b   #6, d0
        move.b  d0, (Player_Quadrant).w
        ; jump buffer latch
        btst    #BUTTON_C_BIT, (Ctrl_1_Press).w    ; any of A/B/C — define mask
        beq.s   .no_latch
        move.b  #PHYS_JUMP_BUFFER, (Player_JumpBuffer).w
.no_latch:
        ; state dispatch
        moveq   #0, d0
        move.b  _pl_state(a0), d0
        move.w  Player_States(pc, d0.w), d1
        jsr     Player_States(pc, d1.w)
        ; position history rings (unconditional)
        ...                                 ; addq.b #4 low-byte wrap per research
        ; animation select + AnimateSprite + DPLC + Draw (shared tail)
        jmp     Player_Display

Player_States:
        dc.w    PState_Ground-Player_States
        dc.w    PState_Roll-Player_States
        dc.w    PState_Spindash-Player_States
        dc.w    PState_Air-Player_States
        dc.w    PState_Jump-Player_States
        dc.w    PState_RollJump-Player_States
        dc.w    PState_AirBall-Player_States

; Player_SetState — THE one transition writer
; In: a0 = SST, d0.w = new PSTATE_*
;   old exit hook → new enter hook → store state byte
; Enter hooks own: width/height (= radii), curl y-shift, anim select,
; one-shot latches. Exit hooks own: cleanup (e.g. spindash dust later).
Player_SetState:
        moveq   #0, d1
        move.b  _pl_state(a0), d1
        move.w  PState_ExitHooks(pc, d1.w), d1
        jsr     PState_ExitHooks(pc, d1.w)
        move.b  d0, _pl_state(a0)
        move.w  PState_EnterHooks(pc, d0.w), d1
        jmp     PState_EnterHooks(pc, d1.w)
```

- [x] **Step 5.3:** GROUND state, flat-ground subset first (no slope factor, angle assumed 0): classic order — (spindash check: stub `rts` for now) → jump check (stub) → input accel/decel/friction on `ground_speed` with the back-out top-speed rule and turnaround kick → projection `x_vel = gsp·cos(angle)>>8, y_vel = −gsp·sin(angle)>>8` via `GetSineCosine` (verify its register contract in `engine/math.asm` before use) → ground wall probe (velocity-projected `Player_SensorWall`, cancel velocity along axis + zero gsp + ST_PUSHING, with the S3K skip for non-cardinal upper-half angles and facing-aware bit) → integration (`ObjectMove`) → floor pair (`Player_SensorFloor`): snap `y_pos += dist` within clamps (−14 fixed up, `min(|gsp·cos|>>8 + 4, 14)` down... grounded snap uses speed along probe axis per SPG), angle update, both-sensors-nothing → `Player_SetState #PSTATE_AIR`.
- [x] **Step 5.4:** GROUND enter/exit hooks: standing radii, walk/idle anim select by gsp (reuse existing anim ids 0/1/2 from test assets). AIR state minimal: air accel, gravity + fall cap, integration, floor pair when falling → landing (flat subset: `gsp = x_vel`) → `Player_SetState #PSTATE_GROUND`. No jump yet.
- [x] **Step 5.5:** Swap `ojz_scroll_test.asm` player setup to `Player_Init` (keep starting in debug-fly so streaming testing workflow is unchanged: `_debug_flag` equivalent → start suspended, B drops you into physics).
- [x] **Step 5.6:** (live-verified by orchestrator 2026-06-12: fall/landing, accel $C/f, friction, facing, ledge→AIR, gravity $38/f) Build + Exodus: walk/run on flat sec0 ground, accel curve to $600, friction stop, turnaround kick observable (brief −$80 snap), camera follows, debug-fly round-trips. Check `Player_Quadrant` stays 0 and gsp behaves via RAM watch. Commit: `feat(§5): player skeleton — state machine, flat ground movement, air fall`

**Task 5 implementation notes (2026-06-12):**
- Player files are included in the **object code bank** (after `ObjCodeBase`), not after `player_sensors.asm` — `objroutine(Player_Main)` requires the routine inside ObjCodeBase+64KB. Sensors stay in the engine block.
- Projection is `y_vel = sin(angle)·gsp>>8` with **NO negation** (step 5.3's `−gsp·sin` was wrong for our data): the classic angle convention (down-right slope = +$10) and `data/misc/sine.bin` (sin($10)=+$61) already agree with screen-down-positive Y. Task 7 must keep this.
- Legacy `Collision_GetFloorHeight`/`Collision_FloorSensors` deleted; `objects/test_player.asm` (still the object_test_state player) migrated to `Player_SensorFloor`.
- AIR applies gravity **before** the position add (plan/task order); classic applies it after (research §1). Re-evaluate in Task 6 when tuning jump arcs.
- **Pre-Task-6 file split (2026-06-12):** `player_common.asm` was split — `PState_Ground` + `Ground_Move` moved to `engine/player/player_ground.asm`, `PState_Air` to `engine/player/player_air.asm` (both in the object code bank, included from `main.asm` right after `player_common.asm`; reached only via the offset tables). `player_common.asm` keeps the overlay, `Player_Init`, `Player_RefreshPhysics`, `Player_Main`, `Player_SetState` + hooks, `Player_Display`, debug-fly, plus the `setStandingSize`/`maskOpposingLR` factoring macros and the `PSTATE_COUNT` lockstep asserts on the three state/hook tables.


---

## Task 6: Jumping + full air physics + landing banding

**Files:** `engine/player/player_air.asm` (air body, landing banding), `engine/player/player_common.asm` (jump entry from the grounded states + hooks), `engine/player/sonic.asm`

- [ ] **Step 6.1:** `Player_Jump` (called from GROUND/ROLL states): consume `Player_JumpBuffer` OR fresh press; ceiling headroom probe ≥6px (`Player_SensorCeiling` at angle+$80); perpendicular ADD: `x_vel += cos(angle−$40)·jump>>8`, `y_vel += sin(angle−$40)·jump>>8`; `Player_SetState #PSTATE_JUMP` (from ground) / `#PSTATE_ROLLJUMP` (from roll); clear stick_convex. **Jump-delay fix:** after the state switch, FALL THROUGH into the air state's movement for this same frame (do not `addq.l #4,sp`-abort like S2).
- [ ] **Step 6.2:** JUMP/AIR/ROLLJUMP/AIRBALL shared air body (one routine, flags per state):
  - air accel ($18) with S3K above-top preservation (back-out, not clamp) — SKIPPED ENTIRELY in ROLLJUMP (classic lockout, drag still runs)
  - release cap: JUMP/ROLLJUMP only — `if y_vel < −$400 && !held → y_vel = −$400`
  - air drag exact rule: `if −$400 ≤ y_vel < 0: x_vel −= x_vel asr 5` before gravity
  - gravity +$38, fall cap $1000; **NO up-cap** — at the spot where the classic −$FC0 clamp would live, write:

```asm
        ; FEEL DEVIATION (spec §2.1): classic non-jump up-velocity cap
        ; (y_vel clamped to -$FC0) deliberately REMOVED — our GSp cap
        ; ($1000) already bounds launches; the knob for "launches feel
        ; truncated" is PHYS_GSP_CAP, coupled to CAM_MAX_Y_STEP +
        ; VFILL_ROWS_PER_FRAME + 32px sensor reach. Do not re-add silently.
```

  - airborne angle decay toward 0 by 2/frame
  - airborne sensor activation by motion quadrant (`CalcAngle(x_vel,y_vel)` — if `engine/math.asm` lacks an arctan, add `GetArcTan` as a small octant table routine, S2-equivalent precision; check first) → wall probes (snap + `x_vel=0`), ceiling (flat band: bump `y_vel=0`; steep + moving up: reattach `gsp = ±y_vel`), floor when eligible.
- [ ] **Step 6.3:** Landing conversion (research physics-classics §2 "Landing"): motion-quadrant dispatch, then angle bands — flat: `gsp = x_vel`; mid (±$10–$1F): `y_vel >>= 1 (asr)`, `gsp = ±y_vel` by angle sign bit; steep (±$20–$3F): `x_vel = 0`, cap y_vel $FC0, `gsp = ±y_vel`; horizontal-motion floor hits: always `gsp = x_vel`; wall-quadrant hits while moving horizontally: `gsp = y_vel` (wall-run engage). Landing eligibility `dist ≥ −(y_vel>>8 + 8)`. On land: `Player_SetState` per curl state (JUMP/ROLLJUMP/AIRBALL land → GROUND with uncurl in hook, unless down held + speed → ROLL), clear PUSHING.
- [ ] **Step 6.4:** Build + verify in Exodus: tap vs hold jump heights; jump while running preserves x_vel; ramp areas launch along normal; roll-jump (temporarily reachable via forced test: hold down while landing — roll lands in Task 7, so for now verify JUMP only); jump buffer: press C 1-2 frames before landing → jumps on landing frame (frame-step in Exodus). Commit: `feat(§5): jumping, air physics, landing banding — jump-delay fixed, up-cap removed`

---

## Task 7: Slopes — slope factor, quadrant walking, slip

**Files:** `engine/player/player_ground.asm` (primarily), `engine/player/player_common.asm` (hooks/quadrant helpers as needed)

- [ ] **Step 7.1:** Slope factor in GROUND before input (skip in ceiling band `angle+$60 < $C0` rule): `gsp += $20·sin(angle)>>8`, with the S3K standing gate (`gsp==0` → apply only if `|factor| ≥ $D`).
- [ ] **Step 7.2:** Quadrant-rotated floor sensing (the §1.2 mode table): floor pair probes down/right/up/left per `Player_Quadrant` with snap axis per mode; angle continuity (reject Δ>$20 → cardinal snap, already in pair wrapper); GSp cap ±$1000 applied to gsp after slope factor.
- [ ] **Step 7.3:** `Player_SlopeRepel` (S3K version): grounded, not stick_convex, `angle ≥ $18` band check via `(angle+$18) < $30` unsigned-style comparison from research; `|gsp| < $280` → `gsp ±= $80` downhill; detach (`PSTATE_AIR`) only when `(angle+$30) ≥ $60`; `move_lock = 30`. While `move_lock > 0`: decrement here; Move/RollSpeed skip INPUT only (friction + slope factor still run).
- [ ] **Step 7.4:** Build + Exodus on OJZ slopes: walk up/down each band, watch `SST_angle` track profile angles, slip triggers below $280 on ≥$18 slopes with visible slide, no detach until $30. Walk into walls: push bit + gsp zero, facing-aware. Commit: `feat(§5): slope physics — factor, quadrant modes, S3K slip`

---

## Task 8: Rolling + spindash

**Files:** `engine/player/player_ground.asm`, `engine/player/sonic.asm`

- [ ] **Step 8.1:** ROLL state: start check in GROUND (down held, L/R not held, `|gsp| ≥ $100`); enter hook: ball radii + `y_pos += CURL_Y_SHIFT<<16`, roll anim; roll physics: friction $6 always, decel $20 opposing (stacks), NO input accel, slope factor $50/$14 asymmetric (never gsp==0-gated), unroll `|gsp| < $80` → GROUND (uncurl hook: −5px, with the wall-clearance check from spec §5.3 list), forced-roll honors `PHYS_KEEP_ROLL_MIN`. Jump from roll → ROLLJUMP (ball radii KEPT — bug #5 fix is structural: radii only change in hooks, and ROLLJUMP/JUMP/AIRBALL all use ball radii).
- [ ] **Step 8.2:** SPINDASH state (sonic.asm contributes the state): trigger down+jump-press in GROUND at |gsp|<... (S2 rule: down held, gsp—use classic: from duck/stand with down); charge `+$200` per jump press capped $800; decay `charge −= charge>>5` per frame; release (down released): `gsp = ±($800 + (charge>>8)·$80)` facing sign → ROLL state; camera: classic spindash lag = freeze camera 16 frames (simple counter the camera reads — match research camera notes).
- [ ] **Step 8.3:** Build + Exodus: roll down/up slopes (asymmetric factor visible), unroll at crawl, spindash charge through release values ($800–$C00 by taps), spindash up the loop ramp area. Commit: `feat(§5): rolling and spindash`

---

## Task 9: Path-swap object + loop verification

**Files:**
- Create: `objects/path_swap.asm`
- Modify: `main.asm` (include), `data/editor/objects.json`-equivalent object library (check `tools/ojz_entity_gen.py` header for the library path; add typeId `path_swap` → `ObjDef_PathSwap`), and the OJZ section JSON that contains the loop (find which section has the loop chunks by checking which sections bake path-B differences — Task 2's test prints them)

- [ ] **Step 9.1:** `path_swap.asm` — invisible vertical line, v2 archetype:

```asm
; subtype bits: 0-3 = half-height in 32px units; 4 = direction sense
;   (0: crossing rightward → layer 1, leftward → layer 0; 1: inverted);
;   5 = also swap render priority (unused for OJZ loop, reserved)
ObjDef_PathSwap: objdef code=PathSwap_Init, map=Map_TestObj, art=0, wdth=4, hght=64, col=COLLISION_NONE
PathSwap_Init:
        ; record spawn X as the line; per-player prev-side bit in sst_custom
PathSwap_Main:
        ; for Player_1: side = (player_x > line_x); if side != prev_side
        ;   && |player_y − line_y| < half_height → write SST_layer per
        ;   direction sense; update prev_side. No draw (render_flags off-screen).
```

- [ ] **Step 9.2:** Place two swappers at the OJZ loop (entry/exit feet) in the editor objects JSON for the loop's section; regenerate entities (`python3 tools/ojz_strip_gen.py generate` runs `ojz_entity_gen.generate()`).
- [ ] **Step 9.3:** Build + Exodus: roll through the loop both directions — full 360° angle sweep on the watch, layer flips at the swappers, no fallthrough at the top (angle continuity), exit speed sane. This is the §5 marquee verification — record exact reproduction steps in the commit message. Commit: `feat(§5): path-swap object — OJZ loop traversable both directions`

---

## Task 10: Camera landing lock + polish pass

**Files:** `engine/level/camera.asm`, `engine/player/player_common.asm`

- [ ] **Step 10.1:** Landing lock: camera Y follow skips downward correction while player state ∈ {JUMP, ROLLJUMP} AND player above last grounded camera target, until landing or bottom-deadzone exit (read `_pl_state` from `Player_1` — camera already `lea`s it). Verify no regression to debug-fly camera behavior (debug suspend reports "grounded" semantics — gate on the debug flag).
- [ ] **Step 10.2:** Spindash camera freeze counter from Task 8 honored here if not already.
- [ ] **Step 10.3:** Full-feel pass in Exodus against verification matrix items 1-9 (spec §9). Fix what fails; each fix its own commit with the matrix item in the message.
- [ ] **Step 10.4:** Frame budget: with player active on busiest OJZ section + streaming, check `Prof_FrameTotal`/`Prof_Peak_Frame` (DEBUG RAM, already exists at `ram.asm:184-193`) stays under 224 lines. Record numbers in DEFERRED_WORK note. Commit: `feat(§5): camera landing lock + verification fixes`

---

## Task 11: Docs closeout

**Files:** `docs/ENGINE_ARCHITECTURE.md` §5/§4.7, `docs/DEFERRED_WORK.md`, this plan (checkboxes), memory

- [ ] **Step 11.1:** ENGINE_ARCHITECTURE §5: flat state machine resolution (hierarchical "evaluate" → rejected), landing banding (fix the cascade "vector projection" line), −$FC0 removal note, per-section physics = plumbing-shipped status.
- [ ] **Step 11.2:** DEFERRED_WORK: close §3 SST-fit audit (fits, DPLC immediates); add launch-cap coupling note; list §5 deferred items (Sonic art/anim plan, dropdash/instashield, Tails, Knuckles, water rows, balance anims, look up/down, 6-button).
- [ ] **Step 11.3:** Save memory progress note. Commit: `docs(§5): architecture + deferred-work closeout for player system`

---

## Self-review notes (already applied)

- Spec coverage: §4 pipeline → Tasks 1-2; §5 sensors → Task 4; §3.3-3.5 → Task 5; §6 physics → Tasks 5-8; §7 camera → Task 10; §8 path swap → Task 9; §9 matrix → Tasks 9-10; §10 docs → Task 11; §2.1 deviation note → Task 6.2 comment + Task 11.
- The math dependency (`GetSineCosine` exists; arctan presence unverified) is called out in Task 6.2 with a fallback instruction.
- Type consistency: `PSTATE_*` byte offsets ×2 used consistently in dispatch and SetState; `_pl_*` accessor naming matches test_player's `_debug_flag` convention.
