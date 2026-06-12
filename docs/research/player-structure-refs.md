# Player Structure References — §5 Research

Survey of player/character CODE STRUCTURE and state-machine patterns across the
reference disassemblies, plus an SST fit analysis for the deferred §3 audit
question ("do player overlays fit 34 bytes of `sst_custom`?"). Physics *values*
are out of scope — this is about how the code is organized.

Sources read for this document:
- `sonic_hack/code/objects/{Sonic,Tails,Knuckles,Player_Common}.asm` + `S4.constants.asm`
- `skdisasm/sonic3k.asm` + `sonic3k.constants.asm` (S3K player fields, Pos_table)
- `ristar_disasm/ANALYSIS.md`
- `gunstar_disasm/ANALYSIS.md` (covers Alien Soldier — shared engine)
- `vectorman_disasm/ANALYSIS.md`, `thunderforce4_disasm/ANALYSIS.md`
- `disasm/OBJECT_SYSTEM.md` (Batman & Robin)
- `s4_engine/structs.asm`, `constants.asm`, `objects/test_player.asm`,
  `docs/ENGINE_ARCHITECTURE.md` §3/§5, `docs/DEFERRED_WORK.md`

---

## 1. State-Machine Survey

### 1.1 Sonic 2 / sonic_hack — the cautionary tale

The S2-derived player is a **three-layer state system where only the top layer
is explicit**:

1. **Lifecycle states** via `objroutine` word at SST $00 — `Sonic_Init →
   Sonic_Control / Sonic_Hurt / Sonic_Dead / Sonic_Gone / Sonic_Respawning`
   (comment block at top of `Sonic.asm`). Clean: explicit, one writer per
   transition.
2. **Movement modes** via a 4-entry jump table indexed by status bits 1-2:
   ```asm
   move.b  status(a0),d0
   andi.w  #6,d0                  ; bits 1 (air) + 2 (ball)
   move.w  Sonic_Modes(pc,d0.w),d1
   jsr     Sonic_Modes(pc,d1.w)   ; MdNormal / MdAir / MdRoll / MdJump
   ```
   (`Sonic.asm:84-89`, table at `:116-119`). Semi-clean: the dispatch is a
   table, but the *index is derived from flag bits*, so "what state am I in" and
   "what flags are set" can never disagree only because they're the same bits —
   transitions are `bset`/`bclr` scattered anywhere.
3. **Everything else as flag soup** — three packed status bytes
   (`status` $28: facing/air/ball/on-object/rolljump/pushing/water;
   `status2` $29: doublejump/speedshoes/nofriction; `status3` $2A:
   lock_motion/lock_jumping/flip_turned/stick_convex/spindash/jumping —
   `S4.constants.asm:185-210`). Measured spread: **304 `status*(a0)` accesses
   across just the 4 player files**, and 11 files codebase-wide test `s1b_*`/
   `s2b_*`/`s3b_*` bits. There is no single authority for any transition:
   entering "rolling" mutates height/width, anim, y_pos bias, and a status bit
   at multiple call sites.

**Worst-in-class: Knuckles.** Glide/climb state doesn't even live in the SST —
it's in **global RAM** (`Knuckles_Glide_Flags`, `Knuckles_Climb_State`,
`Knuckles.asm:215-455`), tested with raw `btst #5`-style magic bit numbers, in
a 3,180-line file with 220+ unnamed `loc_` labels. State spread across SST bits
+ globals + the routine word is the end state of the flag-soup pattern.

**Best-in-class, same codebase: the Tails CPU AI.** One explicit word
(`Tails_CPU_routine`) indexing a jump table of **5 states** (Init, Spawning,
Flying, Normal, Panic — `Tails.asm:158-163`; note ENGINE_ARCHITECTURE §5.4 says
"4-state", the Panic state makes it 5). Transitions are single
`move.w #N,(Tails_CPU_routine).w` writes, each commented with the target state.
Trivially auditable. The same team wrote both patterns; the explicit one stayed
readable.

**Shared-code split:** `Player_Common.asm` is only 603 lines (JumpAngle,
JumpFlip, SlopeResist, RollRepel, SlopeRepel, RollLeft/Right,
CheckWallsOnGround, RollSpeed) against 2,216 (Sonic) + 2,617 (Tails) + 3,180
(Knuckles) per-character lines. `Sonic_Move`/`Tails_Move`, boundary checks,
animate, and DPLC loaders are near-identical copy-paste per character. The S2
lineage shares the *helpers* but duplicates the *control flow*.

### 1.2 Ristar (Sonic-1-derived)

From `ristar_disasm/ANALYSIS.md` (CONFIRMED items unless noted):

- **Two-level hierarchical dispatch**: top game mode (`$FFEA00` ×4 → table at
  `$3B24`) → level handler `$7872` → sub-mode (`$FFEA02`) → dense `bra.w` jump
  table at `$7934` with 17+ sub-modes. The analysis explicitly rates this
  "cleaner than Sonic's single-level mode handler."
- Player lives at a **fixed SST slot** (`$FFB000`), pointer mirrored at
  `$FFE528`. $40-byte Sonic-1-style SST; object IDs stored pre-shifted ×4.
- Grab-arm mechanic (INFERRED): directional **raycast over object slots** on
  grab press, plus the chained-sprite rope renderer for the arm itself — the
  grab is its own state with dedicated child-sprite machinery, not extra bits
  on the walk state.
- Takeaway: a Sonic-1-engine team shipping two years later moved to explicit
  hierarchical state indices and per-state sub-tables. That's the evolution
  path our §5 plan already proposes.

### 1.3 Batman & Robin

From `disasm/OBJECT_SYSTEM.md`:

- Players at fixed slots (`$FFF650`/`$FFF690`), ~90-byte linked-list nodes.
- **Two-level threaded bytecode**: a *state script* (variable ops, conditional
  branches on `$22/$24/$26/$28` locals) drives an *action script* (animation,
  movement, spawning, yield). Dispatch is `movea.w (a4)+,a0; jmp (a0)`.
- The defining idea: **the saved script PC at `$08(a6)` IS the state**. Yield
  (`$0820`) checkpoints the pointer; resume continues mid-behavior next frame.
  No state counter exists at all.
- Verdict for a player avatar: superb for scripted multi-phase behavior
  (bosses, cutscenes), wrong fit for a physics-driven character whose "state"
  must be cheaply queryable by collision, camera, and object code every frame.
  A script PC can't be `cmp`'d against "is he rolling?".

### 1.4 Vectorman

From `vectorman_disasm/ANALYSIS.md`:

- Player is **outside the object pool**: a dedicated ~1,500-byte RAM block at
  `$FFFFAF68` (`$B5A0` for the second slot). The 12-byte dispatch stub only
  holds **two function pointers — update and render**.
- **Function-pointer-as-state**: a transition is
  `move.l #NewStateRoutine,$4(a4)`. Zero dispatch table, zero index math; the
  null render pointer doubles as "invisible".
- Trade-offs: transitions are the cheapest possible, but state is opaque (you
  can't switch on it without comparing pointers), and the giant out-of-pool
  player block means player-vs-object code paths diverge from object-vs-object
  paths. Their player needed ~1500 bytes because *everything* (history,
  animation machinery, weapon state) lives in the block.

### 1.5 Gunstar Heroes / Alien Soldier (Treasure)

From `gunstar_disasm/ANALYSIS.md` (shared engine, two iterations):

- 96-byte SST; **routine index at offset $04 feeding a PC-relative jump
  table**: `move.w $4(a5),d0; lea JumpTable(pc,d0.w),a0; jmp (a0)`. Same
  concept as our `objroutine()`, word-offset encoded.
- Alien Soldier adds **split dispatch** — coarse type flags at $02 gate before
  the fine routine index, so simple objects skip the full dispatch. A two-level
  hierarchy again, encoded as data.
- State data: timers at $50/$56/$5E, link fields $58/$5C for multi-part
  coordination. Player state transitions are index writes, like every other
  object — the player is *not* special-cased.
- **On the famous responsiveness**: nothing exotic in the dispatch. It comes
  from (a) input → velocity with no hidden intermediaries — actions apply
  velocity/state changes the same frame the edge is detected; (b) per-frame
  edge-detected input (Ristar stores held+edge at `$EA3A/B`, same family
  pattern); (c) the player updating early in a fixed slot order so its state is
  current for everything else that frame; (d) zero-cost dispatch keeping the
  whole player update well inside a frame even on busy screens. Responsiveness
  is an *architecture-wide latency budget*, not a player-code trick.

### 1.6 Thunder Force IV

From `thunderforce4_disasm/ANALYSIS.md`: type-segregated pools (32-byte stride;
bullets/enemies/main entities separate), player in the main entity pool at
`$FFFF8198`. A ship avatar has near-trivial movement state, so the player
state-machine lesson is thin; the durable lesson is **pool segregation by
processing profile**, which our slot ranges (§3.1) already adopt.

### 1.7 Pattern verdict

| Pattern | Used by | Verdict |
|---|---|---|
| Explicit state index + jump table | Tails CPU, Ristar sub-modes, Treasure $04 index | **Clean.** Single writer per transition, auditable, `cmp`-able. |
| Two-level hierarchy (coarse → fine table) | Ristar modes, Alien Soldier split dispatch | **Clean**, scales; exactly our state/substate plan. |
| Function pointer / script PC as state | Vectorman, B&R | Cheapest transitions, but opaque state; wrong for a queried avatar. |
| Flag bits as state | S2 status/status2/status3 | **Spaghetti.** 304 accesses/4 files; transitions scattered; Knuckles leaks into globals. |
| Flag bits as *concurrent conditions* | everyone | Fine — facing, underwater, on-object, pushing are orthogonal conditions, not states. |

The line S2 never drew: **mutually-exclusive movement modes belong in a state
index; concurrent conditions belong in flag bits.** S2 used bits for both, so
"jumping" lives in status3 bit 5 AND status bit 1 AND the Modes index AND
(for Knuckles) globals.

---

## 2. SST Fit Analysis (feeds the deferred §3 audit)

### 2.1 What the universal SST already covers

Our $50 SST (`structs.asm:66-99`) already provides, as universal fields, things
S2 kept in the player overlay or duplicated:

| Player need | Covered by | Note |
|---|---|---|
| Lifecycle state | `code_addr` $00 | Init/Control/Hurt/Dead/Respawn as objroutine words — keep the S2 top layer |
| Position w/ subpixel | `x_pos`/`y_pos` 16.16 longs | subsumes S2's x_pixel/y_pixel words |
| Velocity | `x_vel`/`y_vel` $0A/$0C | |
| Facing / flips | `render_flags` $0E | ST_XFLIP mirrors RF bit |
| Status bits | `status` $1E | ST_IN_AIR/ROLLING/ON_OBJECT/PUSHING/UNDERWATER already defined (`constants.asm:174-180`) — S2's s1b_* byte is already universal |
| Ground angle | `angle` $1F | |
| Animation state | `anim`/`prev_anim`/`anim_frame`/`anim_timer`/`anim_table` | |
| DPLC change detection | `prev_frame` $24 | replaces per-character LoadSonicDynPLC compare field |
| Collision dims | `width_pixels`/`height_pixels` | state enter hooks rewrite these |
| Collision layer | `layer` $2D | S2's `layer` byte |
| Leader link | `parent_ptr` $26 | Tails → leader reference (S2 hardcodes MainCharacter address) |

### 2.2 What must live in `sst_custom` (34 bytes, $2E-$4F)

Derived from the union of S2 (`S4.constants.asm:77-99`) and S3K
(`sonic3k.constants.asm:52-74`) player overlays, restructured for the §5
hierarchical state machine, with S3K's byte-timer compaction
(invincibility/speed-shoes decremented every 8 frames — confirmed at
`sonic3k.constants.asm:63-64`):

| Field | Size | Replaces (S2/S3K) |
|---|---|---|
| ground_speed | 2 | `inertia` $24 |
| player_state | 1 | Sonic_Modes index + s3b_jumping/spindash/lock bits |
| player_substate | 1 | (new — §5.4 hierarchy) |
| status_secondary | 1 | status2: speedshoes/doublejump-used/nofriction bits |
| shield | 1 | `shields` $3C |
| flip_angle | 1 | $27 |
| flip_speed | 1 | $2D |
| flips_remaining | 1 | $2C |
| air_left | 1 | $2B |
| double_jump_property | 1 | S3K $25 (Tails flight frames/2, Knux glide phase) |
| move_lock | 2 | $2E word |
| invulnerable_time | 1 | S3K byte timer (S2 wastes a word) |
| invincibility_time | 1 | S3K byte, /8 frames |
| speedshoes_time | 1 | S3K byte, /8 frames |
| next_tilt | 1 | $36 |
| tilt | 1 | $37 |
| interact_obj | 2 | $38 word (object stood on) |
| spindash_charge | 2 | $3A word |
| object_control | 1 | S3K $2E (carried/controlled-by-object semantics) |
| layer_plus | 1 | $3F (secondary solid bit) |
| **Total** | **24** | |

**24 of 34 bytes → 10 spare** for per-character extras (Knuckles glide speed
word + climb sub-timer ≈ 3-4 bytes; Tails needs ~0 — flight time is
double_jump_property, CPU AI state is global by design in every reference).

**The one pressure point: the DPLC pair.** `test_player.asm` burns 9 custom
bytes on `dplc_ptr` (long) + `art_base` (long) + debug_flag because generic
shared code needs them per-slot. If the real player keeps that pattern:
24 + 8 = **32 of 34 — fits, 2 spare**. Recommended instead: per-character
wrapper code supplies DPLC table/art base as immediates (`lea Sonic_DPLC,a2`)
to `Perform_DPLC` — characters have per-character code anyway, so the SST
copies are redundant. That keeps 10 bytes of headroom.

**What stays global (validated by every reference):** position/stat history
buffers, CPU-AI state machine word + timers, saved respawn state, super
palette/timer machinery, active physics table (RAM block per player slot,
pointed at by a4 — S2's `Sonic_top_speed/acceleration/deceleration` trio
already proves the calling convention). None of these are per-slot data.

### 2.3 Conclusion

**Fits.** A full S3K-feature-set player needs 24-32 of the 34 custom bytes
depending on where the DPLC pair lives. No per-pool stride, no SST growth, no
$60 player slot. The deferred-work question ("whether player overlays fit 34
bytes — re-evaluate during §5", `DEFERRED_WORK.md:149`) can be closed as
*fits, with the DPLC-as-immediates recommendation*. Corollary: the
word-mappings shrink idea (`DEFERRED_WORK.md:159`) is not needed for player
pressure reasons.

---

## 3. Assessment of the §5 Plan Items

**State entry/exit hooks (§5.4) — KEEP.** This is the direct antidote to the
measured S2 failure: entering/leaving a state touches height/width, hitbox,
animation, and collision mode at 3+ scattered sites per state, and Knuckles'
glide adds global flags on top. No commercial reference implements explicit
hooks — but B&R achieves the same effect implicitly (script entry runs setup
opcodes; yield point defines exit), which validates the concept. Implementation
should be a single `Player_SetState` routine: look up old state's exit handler,
new state's enter handler, call both, write the state byte. Transitions are
rare (a handful per second), so two indirect calls per transition are free; the
payoff is one auditable writer for `player_state`, which the Tails-CPU pattern
proves keeps code readable for a decade of modification.

**Hierarchical state machine, state + substate bytes (§5.4) — KEEP, with one
modification.** The survey is unanimous that explicit indices beat flag-derived
dispatch (Ristar's two-level tables, Treasure's $02-gate + $04-index, Tails
CPU vs. the rest of the S2 player). The modification: do **not** try to absorb
the concurrent-condition bits into the hierarchy. Facing, underwater,
on-object, pushing (already universal `ST_*` bits at $1E) and the powerup bits
in status_secondary are orthogonal to GROUNDED/AIRBORNE/ROLLING/SPECIAL and
combinatorially explode the state count if forced in. The principled split —
*state index for mutually exclusive modes, bits for concurrent conditions* —
is the actual fix for S2's tangle, and it makes the plan's "2-bit status +
status3 parallel bits replaced" wording precise: status3's pseudo-states
(jumping, spindash, lock_motion) move into state/substate; status's genuine
conditions stay bits.

**Configurable physics tables (§5.2/§5.3) — KEEP.** S2 already half-implements
this: `Sonic_Control` loads `lea (Sonic_top_speed).w,a4` and every movement
routine reads physics through a4 (`Sonic.asm:81`), with the water/super code
swapping the RAM values. The plan's per-character ROM base table + per-section
modifier composing into a per-player RAM block is a straight generalization of
a proven calling convention — zero new per-frame cost (a4 is already the
convention), and it keeps physics out of the SST entirely. One caution from
the survey: apply modifiers at section-transition time (recompute the RAM
block), never per-frame; and the smooth-Lerp can ship later — every reference
snaps (S2 water snaps values at the surface line) and nobody noticed for 30
years.

**Player_Common shared code (§5.4) — KEEP, and invert the split.** sonic_hack's
`Player_Common.asm` shares 603 lines of *helpers* while 8,000 lines of
near-identical *control flow* (Move, Boundary, Animate, DPLC, the Md* mode
bodies) are duplicated three ways — that's the measured failure mode to avoid.
The new engine should make Player_Common own the entire frame skeleton (input →
state dispatch → physics → collision → animate → DPLC) and reduce per-character
files to: a physics table, art/DPLC config, and ability state handlers plugged
into the state machine (Sonic: dropdash/instashield states; Tails: fly states +
the CPU AI as its own 5-state machine — Init/Spawning/Flying/Normal/**Panic**,
the plan's "4-state" undercounts; Knuckles: glide/climb states, finally in the
SST instead of globals). The hierarchical state machine is what makes this
inversion possible: characters add *states*, not *forks inside shared
routines*.

---

## 4. Position History Buffer (Tails following)

**S2/sonic_hack implementation** (`Sonic.asm:211-226` `Sonic_RecordPos`):
- `Sonic_Pos_Record_Buf`: **$100 bytes = 64 entries × 4** (x word, y word).
- Written **every frame** while the leader runs (called from `Sonic_Control`
  main path and hurt/dead paths).
- Ring index trick: `addq.b #4,(Sonic_Pos_Record_Index+1).w` — incrementing
  only the index's low byte wraps at 256 for free; requires the buffer
  256-byte-aligned-addressable via the index, no masking instruction.
- Parallel `Sonic_Stat_Record_Buf` ($100 bytes): `Ctrl_1_Logical` word +
  `status` word per entry — because the Tails AI doesn't just chase positions,
  it **replays the leader's inputs and status** from the past
  (`Tails.asm:401-417` reads earlier input word and tests the recorded pushing
  bit to filter actions).
- Read side: Tails targets the entry `$10*4+4 = $44` bytes back ≈ **17 frames
  of delay** (`Tails.asm:237-244`), clamped above water level when submerged.
- Init quirk: on spawn the buffer is filled/zeroed over 64 iterations so the
  follower doesn't chase stale garbage.

**S3K implementation** (`sonic3k.asm:22123-22164`, `sonic3k.constants.asm:324-362`):
identical shape — `Pos_table` $100 bytes, +4/frame, same low-byte wrap;
`Stat_table` packs ctrl word + status byte + **art_tile byte** (3 used bytes
per entry). Competition mode gets per-player tables. Also consumed by the
invincibility-stars trail, which is why it predates Tails (it's in Sonic 1).

**Cost:** ~10 instructions/frame on the leader (≈60-70 cycles), $200 bytes RAM
+ two index words. Negligible on both axes.

**Recommendation for §5:** adopt the S2/S3K shape unchanged — 64 × 4-byte ring,
low-byte-increment wrap (place via `phase` in ram.asm at a 256-byte boundary so
the wrap stays free), parallel stat ring recording input + status because input
replay is what makes the follower feel intentional rather than rubber-banded.
Record unconditionally every frame (a "follower active?" branch costs more than
the writes). The buffer also feeds invincibility trails and any future
afterimage effect for free.
