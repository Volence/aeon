# Loops and sprite rotation — what we have, what S3K does, what it costs

**Date:** 2026-08-28 · **Branch:** `research/loops` · **Tree read at:** aeon `42e70bea`
(worktree `agent-a55c7332cee812166`). Every claim about *our* tree below is pinned to
that revision — those age fastest and nothing here re-checks them for you.

**Status: RESEARCH AND DESIGN ONLY.** No engine code was written, no bytes moved, no
build run, no emulator touched. Items needing runtime confirmation are marked
**[TAG-RUNTIME]**.

---

## 0. The two questions, and the one-line answers

The owner asked two things:

> "When I start going on a loop I don't start turning upside down like in the games.
> Also how do we do like a loop now? Do we have an implementation way?"

**(1) Why doesn't he tilt?** Because nothing in the engine turns the player's ground
angle into a sprite orientation. The animation driver never reads `angle`. **But the
tilted artwork is already in the ROM** — 20,480 bytes of it for Sonic alone, in exactly
the frame layout S3K's code expects, referenced by nothing. The missing piece is roughly
fifteen instructions, not an art project.

**(2) Is there a path to loops?** Yes, and far more of it is built than anyone in this
session believed at dispatch. The two-surface collision system — two collision planes per
section, a per-object layer select read by every sensor, and a working path-swapper
object — is complete end to end and has been since 2026-08-08. Two path swappers are
placed in OJZ act 1 section 1 today. What is missing is (a) the drawn loop itself — **no
section in OJZ has a place where plane B is solid and plane A is not**, so the closed
mechanism has never been exercised by real content — and (b) three finishing touches on
the swapper, of which the sprite priority swap is the one that makes a loop look like a
loop.

**(2b) And the owner wants the object gone.** He is right that the authoring should move
into the tooling, and the format already has the spare room to do it with no format change
at all (§4.5.2). But the runtime decision itself is irreducible — which surface you are on
depends on where you have *been* — so the honest goal is "stop needing the object for the
common case", not "delete the object" (§4.5.1).

---

## 1. Correction to the dispatch brief

The brief that produced this document carried a measured claim:

> "I found no path-swapper / layer-switching / plane-solidity machinery."

**That claim is wrong.** It was retracted mid-task by its author; this section records
the correction and my independent re-derivation, because a wrong fact in a brief is the
most expensive kind.

I re-derived both of the brief's claims by a *different enumeration parameter* than the
one that produced them — instead of grepping for names, I enumerated (a) the fields of
the live object record and asked what each is for, and (b) the inputs the sprite renderer
actually consumes. Results:

| Brief's claim | Verdict | How I re-derived it |
|---|---|---|
| `animate.emp` has zero references to `angle`; nothing turns ground angle into sprite orientation | **SURVIVES** | Enumerated every `Sst` field the renderer reads (`mapping_frame`, `frame_off`, `render_flags`, `art_tile`) — none is a function of `angle`. See §3.1. |
| No path-swapper / layer-switching / plane-solidity machinery | **FAILS — comprehensively** | Enumerating the `Sst` struct hit `layer: u8 @ $2D` on the third read. Enumerating what a collision lookup reads per tile hit the two-plane select and the 2-bit solidity field. See §4. |

The mechanism of the miss is worth keeping: the brief's grep pattern *did* include
`path_swap`, and would have matched the filename instantly. The search was scoped to
`engine/level/`, `engine/objects/` and `games/sonic4/player/`. The file is
`games/sonic4/objects/path_swap.emp` — a directory the search never visited. The pattern
was fine; the scope excluded the answer.

**Second correction, to our own tree's history.** `docs/DEFERRED_WORK.md` already carries
a fully-corrected entry closing this exact ground (§ "Path-B collision content", corrected
2026-08-08). And `docs/research/animation-system.md` — written during the animation design
phase — already documented S3K's angle-derived frame offset and cited it as the *reason*
the frame-index animation model was chosen over Treasure's sequential-cursor model
("Random frame access (essential for walk angle offsets)", `animation-system.md:349`).
The design anticipated rotation. The feature was simply never built. **Reading our own
notes first would have answered a third of this task.**

---

## 2. What S3K actually does — established from source

Both mechanisms below are read first-hand out of `/home/volence/sonic_hacks/skdisasm/`.
Line numbers are as-committed in that tree today.

### 2.1 Sprite orientation: four art sets plus both flip bits

The routine is **`Animate_Sonic`, `sonic3k.asm:24737`**. Its walk/run branch begins at
`loc_126A4` (`:24805`). The load-bearing part, verbatim:

```asm
loc_126A4:
        addq.b  #1,d0
        bne.w   loc_12A2A
        moveq   #0,d0
        tst.b   flip_type(a0)
        bmi.w   Anim_Tumble
        move.b  flip_angle(a0),d0
        bne.w   Anim_Tumble             ; tumbling? different mechanism entirely
        moveq   #0,d1
        move.b  angle(a0),d0
        bmi.s   loc_126C8
        beq.s   loc_126C8
        subq.b  #1,d0                   ; bias so the snap rounds symmetrically
loc_126C8:
        move.b  status(a0),d2
        andi.b  #1,d2                   ; d2 = facing bit
        bne.s   loc_126D4
        not.b   d0                      ; facing left -> mirror the angle
loc_126D4:
        addi.b  #$10,d0                 ; +22.5 deg: snap to NEAREST, not floor
        bpl.s   loc_126DC
        moveq   #3,d1                   ; upper half -> set BOTH flip bits (180 deg)
loc_126DC:
        andi.b  #$FC,render_flags(a0)
        eor.b   d1,d2
        or.b    d2,render_flags(a0)     ; render_flags bits 0-1 = X-flip, Y-flip
        btst    #5,status(a0)
        bne.w   loc_12A72               ; pushing: skip the angle path
        lsr.b   #4,d0
        andi.b  #6,d0                   ; d0 in {0,2,4,6} -- FOUR art sets
```

and then the walk/run table choice and the offset multiply:

```asm
        lea     (AniSonic01).l,a1       ; RUN table
        cmpi.w  #$600,d2                ; |ground_vel| >= $600 -> run
        bhs.s   loc_12724
        lea     (AniSonic00).l,a1       ; WALK table
        add.b   d0,d0                   ; walk sets are 8 frames apart
loc_12724:
        add.b   d0,d0                   ; run sets are 4 frames apart
        move.b  d0,d3
        ...
loc_12742:
        move.b  d0,mapping_frame(a0)
        add.b   d3,mapping_frame(a0)    ; <-- THE ANGLE OFFSET. That is the whole trick.
```

And the two animation scripts it indexes
(`General/Sprites/Sonic/Anim - Sonic S3.asm:38-39`):

```asm
AniSonic00:     dc.b  $FF,   1,   2,   3,   4,   5,   6,   7,   8, $FF
AniSonic01:     dc.b  $FF, $21, $22, $23, $24, $FF, $FF, $FF, $FF, $FF
```

**So the answer, precisely:**

* It is **(a) angle-derived selection among stored tilted art variants**, combined with
  **(b) the render flags' X-flip *and* Y-flip bits** — `d1 = 3` sets both, which is a
  180° rotation. It is *not* flips alone, and it is *not* runtime art rotation.
* There are **four** stored orientation sets. Flipping reaches the other four. Eight
  visual orientations, 45° apart.
* Walk sets live at mapping frames `$01-$08`, `$09-$10`, `$11-$18`, `$19-$20`
  (stride 8). Run sets at `$21-$24`, `$25-$28`, `$29-$2C`, `$2D-$30` (stride 4).
* The snap is `((angle_maybe_mirrored + $10) >> 4) & 6`. The `+$10` is round-to-nearest;
  the `& 6` keeps only the low quadrant because the sign bit already became the
  double-flip.
* The walk/run threshold is `|ground_vel| >= $600`. Speed shoes double the *animation*
  speed by doubling `d2` first (`status_secondary` bit 7).
* Rotation is **suppressed while pushing** (`status` bit 5) — the push pose has no
  tilted variants.

**The script header is the marker.** The `$FF` byte at the head of `AniSonic00`/`AniSonic01`
is what routes into this path at all — `move.b (a1),d0; bmi.s loc_126A4` at `:24755`, then
`addq.b #1,d0; bne.w loc_12A2A` at `:24808`. Only walk and run (and their Super twins)
carry it; every other script is angle-blind. **Our `DUR_DYNAMIC` is `$FF`**
(`engine/system/constants.emp:73`) and sits at byte 0 of exactly our Walk and Run scripts —
the same sentinel in the same position. That is not a coincidence worth building on
directly, though: our Roll script *also* carries `DUR_DYNAMIC`, and S3K explicitly routes
roll away from the angle path. **The tilt must key on the animation id (`ANIM_WALK` /
`ANIM_RUN`), not on the duration sentinel.**

**A naming trap worth recording.** S3K's `flip_angle` is *not* the running tilt. It is
the somersault/tumble counter used when Sonic is launched off a spring or a ramp;
`Anim_Tumble` (`sonic3k.asm:24928`) reads it, does `divu.w #$16` (22° steps) and lands on
mapping frames `$31`+. Our own `PlayerV.flip_angle`, commented "reserved (visual
rotation)", is named after that field and is a poor home for the running tilt — the tilt
needs no state at all, it is a pure function of `angle` and `status`.

**Child sprites do not rotate.** The shield objects and the dust have no tilted variants
and none of the shield DPLC code consults angle. In S3K a shielded Sonic running a loop
has a shield that stays upright. That is the shipped look, not a bug to fix.

### 2.2 Track crossover: two solidity bits per tile, one bit-number per player

S3K stores **two independent solidity fields per collision cell**, and the player carries
**the bit number to test** rather than a layer index.

`sonic3k.constants.asm:77-78`:

```asm
top_solid_bit =         $46 ; byte ; the bit to check for top solidity (either $C or $E)
lrb_solid_bit =         $47 ; byte ; the bit to check for left/right/bottom solidity ($D or $F)
```

So bits 12/13 of the chunk-block word are path A's top / left-right-bottom solidity, and
bits 14/15 are path B's. The player holds `$C`/`$D` (path A) or `$E`/`$F` (path B).

The lookup switches a **global** collision pointer from the player's bit —
`Player_AnglePos`, `sonic3k.asm:18732`:

```asm
Player_AnglePos:
        move.l  (Primary_collision_addr).w,(Collision_addr).w
        cmpi.b  #$C,top_solid_bit(a0)
        beq.s   loc_EC42
        move.l  (Secondary_collision_addr).w,(Collision_addr).w
```

The switcher is **`Obj_PathSwap`, `sonic3k.asm:39702`**, worker `sub_1CDDA` at `:39796`.
Its full subtype map, read out of the code:

| subtype bit | meaning |
|---|---|
| 0-1 | band half-extent, indexed into `word_1CD34: dc.w $20,$40,$80,$100` (32/64/128/256 px) |
| 2 | orientation: clear = vertical line (compares `x_pos`), set = **horizontal line** (compares `y_pos`, `loc_1CEF2`) |
| 3 | crossing rightward/downward → path B |
| 4 | crossing leftward/upward → path B |
| 5 | crossing rightward/downward → **sprite drawn in front (high priority)** |
| 6 | crossing leftward/upward → sprite drawn in front |
| 7 | grounded-only (skip while `Status_InAir`) |

and three further behaviours:

* **Per-player armed state.** Bytes `$34(a0)`/`$35(a0)` hold "player N is past the line",
  armed at Init from each player's current position, so a respawn never counts as a
  crossing. `Breathing_bubbles` gets a third byte.
* **A proximity gate.** `cmpi.w #$40,d2; bhs -> return` — the swap only fires when the
  player is within 64 px of the line horizontally.
* **The priority swap is not optional dressing.** Every firing path does
  `andi.w #drawing_mask,art_tile(a1)` — it *clears* the VDP high-priority bit
  unconditionally, then re-sets it only if the direction's priority bit is set. This is
  what puts Sonic behind the loop art on the far side. Without it the loop reads as flat.
* `render_flags` bit 0 on the swapper object suppresses the solid-bit write entirely,
  leaving a priority-only swapper.

**And the loop is pure physics.** Nothing forces the player around. The only thing that
keeps him on is the slip/detach check — S3K slips when the surface is ≥ `$18` from flat
*and* `|ground_vel| < $280`, and detaches when additionally ≥ `$30` from flat. Run into a
loop at or above `$280` and you carry through it; run in slower and you slide back out.
That is the whole mechanism.

There *are* scripted-path objects in S3K, and it is worth naming them so nobody mistakes
one for a loop: **`Obj_AutoSpin`** (object `$26`, `sonic3k.asm:42298`) uses the same
segment geometry as the path swapper but on crossing writes `ground_vel = $580` and forces
a roll — that is the corkscrew/tube entrance, not a loop. **`Obj_AutomaticTunnel`**
(object `$24`, `:57183`) is the genuine on-rails object: it takes `object_control`, zeroes
both velocities, sets `ground_vel = $800` and walks the player down a hardcoded waypoint
list. Neither is involved in an ordinary loop.

**A second layer of indirection I nearly missed.** The 2-bit-per-plane solidity in the
block word is only half of S3K's layer system. `sub_F264` (`sonic3k.asm:19236`) then does
`movea.l (Collision_addr).w,a2; move.b (a2,d0.w),d0` — the **block ID resolves through a
per-layer index array to a heightmap id**, so the *same block* can present a completely
different shape and angle on each plane. `LoadSolids` (`:9539`) sets that up two ways: the
Sonic 3 format keeps two contiguous 1,536-byte arrays (`Secondary = Primary + $600`); the
S&K format **interleaves them byte-by-byte** (`Secondary = Primary + 1`, hence the
`add.w d0,d0` word stride before a byte read), so plane select is a one-byte pointer bump.
That is the tighter of the two and worth knowing, though — see §4.1 — our design does not
need either.

---

## 3. What our engine has today — question 1 (sprite orientation)

### 3.1 The claim survives: nothing reads `angle` for rendering

Enumerating the fields `engine/objects/sprites.emp` consumes to place a sprite:
`mapping_frame` (:326), `frame_off` (:329/:332), `render_flags` (:340/:388/:393),
`art_tile` (:361). None is written from `angle` anywhere.

`AnimateSprite` (`engine/objects/animate.emp:78`) opens by copying the two flip bits
straight from `status` into `render_flags` and never looks at angle again:

```asm
        andi.b  #$F9, Sst.render_flags(a0)
        move.b  Sst.status(a0), d0
        andi.b  #$06, d0                // RF_XFLIP|RF_YFLIP
        or.b    d0, Sst.render_flags(a0)
```

The single place a script frame becomes a mapping frame is `.set_frame`
(`animate.emp:108`), `move.b d0, Sst.mapping_frame(a0)`, tail-calling
`RefreshSpritePieceCount`.

`PlayerV.flip_angle` (`games/sonic4/player/player_common.emp:95`) is declared
`// reserved (visual rotation)` and **has no reader and no writer** anywhere in
`engine/` or `games/`. (The `flip_angle_x` / `flip_angle_y` functions in
`tools/collision_pipeline.py` are unrelated build-time helpers that mirror a collision
tile's *surface* angle when the tile is flipped.)

So: **the player's sprite has exactly four possible orientations today (X-flip × Y-flip)
and nothing drives either from the terrain.** That is why he does not tilt.

### 3.2 The surprise: the tilted art is already in the ROM

The shipped art is `art/optimized/characters/sonic.bin` with
`games/sonic4/data/dplc/optimized/sonic.bin`
(`games/sonic4/data/collision/collision_data.emp:15-17`). Parsing the DPLC's own
frame table:

* 224 mapping frames; art blob 97,472 bytes = 3,046 tiles, and the DPLC references
  exactly 3,046 distinct tiles — the blob is precisely its referenced set.
* Frames `$01`-`$32` occupy a **strictly contiguous, sequentially-laid-out** tile run.
* The four walk blocks and four run blocks have **zero tile overlap with each other**:

| block | frames | distinct art tiles | bytes |
|---|---|---|---|
| walk, upright | `$01-$08` | 143 | 4,576 |
| walk, tilt 1 | `$09-$10` | 164 | 5,248 |
| walk, tilt 2 | `$11-$18` | 128 | 4,096 |
| walk, tilt 3 | `$19-$20` | 161 | 5,152 |
| run, upright | `$21-$24` | 61 | 1,952 |
| run, tilt 1 | `$25-$28` | 63 | 2,016 |
| run, tilt 2 | `$29-$2C` | 61 | 1,952 |
| run, tilt 3 | `$2D-$30` | 63 | 2,016 |

Our animation scripts reference **only the upright blocks**
(`games/sonic4/data/animations/sonic_anims.emp:37-38`):

```
Walk:     [DUR_DYNAMIC, 7, 8, 1, 2, 3, 4, 5, 6, AF_END],
Run:      [DUR_DYNAMIC, $21, $22, $23, $24, AF_END],
```

— the same frame numbers as S3K's `AniSonic00`/`AniSonic01`, at the same block strides
(8 and 4), with the tilted blocks sitting at exactly the offsets S3K's `add.b d3` lands on.

**Dead-but-paid-for art in the ROM today: 640 tiles = 20,480 bytes for Sonic** (21% of his
art budget). The same four-block structure is present in Tails' and Knuckles' shipped
sheets at the same frame indices — 655 tiles (20,960 B) for Tails, 664 tiles (21,248 B)
for Knuckles. **Total ≈ 62,688 bytes of rotated character art currently referenced by
nothing.**

**And there is more rotation art than that.** S3K also carries **three full-360° tumble
sets** for the somersault Sonic does off springs and ramps — 12 frames each at base frames
`$31`, `$3D`, `$49`, selected by `flip_angle` through a `divu.w #$16` (30° steps),
`Anim_Tumble` at `sonic3k.asm:24928`. Measuring the same frame ranges in *our* shipped
sheet gives 171 / 165 / 183 tiles against S3K's 171 / 165 / 184 — the one-tile difference
is our optimiser's dedupe. **So our art blob is S3K's Sonic sheet wholesale, and a further
519 tiles (16,608 bytes) of full-circle tumble art is also present and referenced by
nothing.** A spring somersault is therefore also already paid for, if it is ever wanted.

**[TAG-RUNTIME]** I established the four walk/run blocks structurally (four disjoint,
equal-length, contiguous runs at exactly the S3K strides) and by matching S3K's code and
scripts, not by looking at the pixels. Confidence is high but a five-second eyeball of
mapping frames `$09`, `$11`, `$19` in a sprite viewer would make it certain, and would
also tell us *which* orientation each block is.

### 3.3 What enabling it costs — measured

**VRAM: zero.** The character window is 32 tiles (`VRAM_TEST_SONIC = $03C0`, tiles
960-991, `games/sonic4/config/constants.emp:393`) and it is a *DPLC streaming window* —
one frame resident at a time. The build's existing guard
(`collision_data.emp:31`) already measures the peak across **all 224 frames** and passes:
peak is 29 tiles, at frame `$0E`, which is *inside walk tilt block 1*. The wall already
accounts for the tilted art.

**ROM: zero new bytes of art.** It is already there.

**DMA queue: one specific, bounded new risk.** `collision_data.emp:34-61` records a
standing debt: the Important DMA queue has 12 slots (`DMA_IMPORTANT_SLOTS`), a DPLC frame
should leave 2 free, so the safe bound is 10 entries per frame, and Sonic's sheet already
violates it. Measuring the walk/run blocks specifically:

* Upright walk + run frames: **max 8 entries**. Comfortably inside budget.
* Tilted walk + run frames: **max 12 entries — but only ONE frame reaches it**, frame
  `$0E`, and it is the same frame that carries the 29-tile peak. The other 35 tilted
  frames are all ≤ 10.

So turning tilt on makes exactly one 12-entry frame reachable during ordinary running. On
that single frame the Important queue is 100% player art and the art-page landing is
deferred. Today the same condition is already reachable by holding UP (frame `$C4`, 12
entries — the file says so). The new part is that it would now happen *while running*,
which is when the level is actually streaming. This is a real cost and it is precisely one
frame wide.

**CPU: negligible.** ~15 instructions once per player per frame, in the display tail.
Order 100 cycles against a ~127,000-cycle NTSC frame.

### 3.4 Where the code would go

`Player_Display` (`player_common.emp:704`) runs
`Player_Animate → Dust_Tick → AnimateSprite → Player_LoadArt`. The tilt must be applied
**after `AnimateSprite`** (which owns `mapping_frame` and rewrites it every frame — the
file already notes this when explaining why Knuckles' glide poses are expressed as anim
ids rather than direct frame writes, `player_common.emp:719-722`) and **before
`Player_LoadArt`** (which streams art from `mapping_frame`).

One caution the code must respect: `Sst.frame_off` is a render cache and the struct
comment is explicit — "MUST be refreshed on every `mapping_frame`/`mappings` write"
(`engine/objects/sst.emp`). Anything that adds an offset to `mapping_frame` must re-run
`refresh_piece_count` (`engine/objects/frames.emp:54`) or the sprite draws the wrong
frame's pieces.

---

## 4. What our engine has today — question 2 (track crossover)

### 4.1 The machinery is complete, and it is not a stub

Traced end to end at `42e70bea`:

1. **Authoring.** Aurora writes two collision planes per section:
   `games/sonic4/data/editor/ojz/act1/section_N.collattr.bin` (plane A) and
   `section_N.collattrb.bin` (plane B) — 256×256 cells, one 16-bit big-endian word each.
2. **Baking.** `tools/ojz_strip_gen.py:1576-1625` (`apply_editor_collision_overlay`) reads
   both files and bakes each through `collision_pipeline.bake_plane_cell` into a shared
   interned attribute set. A missing or malformed plane-B file mirrors plane A; both files
   are present for all nine OJZ sections.
3. **The attribute byte.** Each baked byte indexes an interned
   `(16-byte height profile, angle byte, 2-bit solidity)` triple
   (`tools/collision_pipeline.py:144-160`). Solidity is
   `SOL_NONE / SOL_TOP / SOL_LRB / SOL_ALL` (`:48`) — **top-only surfaces are
   expressible**, which is what a loop's outer shell needs. `DEFERRED_WORK.md` records 13
   of 255 attr-set slots used, ~242 free.
4. **The donor bit positions match S3K exactly.** `PATH_A_SOL_SHIFT = 12`,
   `PATH_B_SOL_SHIFT = 14` (`collision_pipeline.py:53-54`) — the same bits 12/13 and 14/15
   that S3K's `$C/$D` and `$E/$F` name.
5. **Storage.** Two collision planes in the tile cache, plane B at
   `+TILE_CACHE_COLL_SIZE`.
6. **Lookup.** `Collision_GetType` (`engine/level/collision_lookup.emp`) takes
   `d3.b = layer` and adds `TILE_CACHE_COLL_SIZE` to the byte index for layer 1.
7. **Per-object layer.** `Sst.layer: u8 @ $2D` — "collision layer select (0 = path A,
   1 = path B)" (`engine/objects/sst.emp`). Every object carries one; it is not a global.
8. **Every sensor honours it.** `move.b layer(a0), d3` at
   `player_sensors.emp:343, :454, :547`, `player_glide.emp:371`, and four sites in
   `player_climb.emp`. Floor, ceiling, wall and surface probes all pass it through.
   Cleared at `player_common.emp:457` on player init.
9. **The switcher exists.** `games/sonic4/objects/path_swap.emp` — `PathSwap_Init` /
   `PathSwap_Main` — an invisible vertical line that writes `Sst.layer` on the leader
   crossing it. Shipped 2026-06-12, ported to `.emp` 2026-07-29.
10. **It is placed in a level.** `ObjDef_PathSwap` is type 1 in
    `OJZ_Sec1_TypeTable` (`games/sonic4/data/generated/ojz/act1/entity_data.emp:41`), and
    `section_1.objects.json` places two instances at (768, 836) subtype 82 and
    (880, 1000) subtype 19.

**Our per-object layer is architecturally better than S3K's.** S3K switches a global
`Collision_addr` in `Player_AnglePos` before every probe, then swaps it back for the other
player. Ours carries the layer on the querying object, so two players, or a player and a
carried object, can genuinely be on different paths at once with no re-entrancy hazard.
Our `docs/research/dual-layer-collision.md` §3 already argued this.

### 4.2 The gap is content, not code

I compared the two authored planes for all nine OJZ act 1 sections
(cells = 16-bit words, "solid" = nonzero):

| section | plane A solid cells | plane B solid cells | cells differing |
|---|---|---|---|
| 0 | 1,060 | 416 | 644 |
| 1 | 0 | 0 | 0 |
| 2-8 | 0 | 0 | 0 |

Two things follow.

**First, section 1 — the one holding both path swappers — has no collision authored at
all, on either plane.** The swappers are flipping a layer over empty space.

**Second, section 0's plane B is a strict subset of plane A.** Of the 644 differing cells,
**644 are solid on A and air on B, and zero are solid on B and air on A.** For a loop you
need at least one place where plane B provides a surface plane A does not. There is no
such place. So plane B in section 0 is partial authoring, not a designed crossover.

**No loop geometry exists anywhere in OJZ act 1 today.** The mechanism is complete and
untested by real content. Note that these are files the owner is actively editing —
measured 2026-08-28, files timestamped 14:41 the same day. **[TAG-RUNTIME]** this table is
perishable; re-measure before quoting it.

### 4.3 The three real gaps in our path swapper, against S3K

Comparing `path_swap.emp` line by line with `Obj_PathSwap`:

**Gap 1 — no sprite priority swap.** Our subtype bit 5 is
`PATHSWAP_BIT_PRIO`, declared "reserved: render-priority swap (future)", and
`PathSwap_Init` raises a debug error if level data ever sets it. S3K's equivalent (bits 5
and 6) is what makes Sonic pass *behind* the loop art on the far side, and it fires on
every crossing (it clears the priority bit unconditionally, then re-sets it). **Without
this a loop reads as a flat painted circle — the player runs over the top of his own
scenery.** This is the single most visible missing piece.

The mechanics on our side are trivial: the VDP priority bit is bit 15 of `art_tile`,
`vram_art(tile, pal, pri)` already packs it (`engine/objects/objdef.emp:32`), and the
player's `art_tile` comes from `CharacterDef.cd_vrambase` with the bit clear
(`player/characters.emp:87`). It is a `bclr`/`bset` pair on `art_tile(a1)`.

**Gap 2 — no horizontal swapper.** S3K's subtype bit 2 selects a swapper that compares
`y_pos` instead of `x_pos` (`loc_1CEF2`). Ours only ever compares X
(`PathSwap_Main`). Vertical loops, corkscrews entered from above, and any layer change
across a horizontal boundary are unbuildable.

**Gap 3 — one player only.** S3K keeps a per-player armed byte (`$34`, `$35`) and runs
the worker once per player. Ours keeps a single `PathSwapV.prev_side` and reads
`Camera_Target` — so it serves the leader and nobody else. Fine today (one player), a
blocker for co-op.

Two more, smaller:

* **Direction expressiveness.** S3K has two independent bits (rightward→B, leftward→B),
  four combinations. Ours has one invert bit, two. Ours cannot express "swap to B going
  right, leave alone going left".
* **Subtype budget.** Ours spends bits 0-3 on half-height in 32 px units; S3K spends bits
  0-1 on a four-entry table (32/64/128/256 px). Adding orientation and two priority bits
  to our byte means re-cutting the field. Cheap now, annoying after level data exists.

**Deliberately different, and defensibly so:** we dropped S3K's `|dx| < $40` proximity
gate. The header explains why — spawn-time re-arming plus the teleport rebase shifting
object and player by the same delta covers what the gate was for. I agree with that call;
it is documented at the site, which is the right place.

### 4.4 The physics half is already S3K-exact

Loops in S3K are pure physics, and ours are already built to the same numbers:

* `Player_SlopeRepel` (`player_ground.emp:481`) implements the S3K slip/detach: slip band
  ≥ `$18` from flat, detach band ≥ `$30`, slip threshold `PHYS_SLIP_SPEED = $280`,
  nudge `$80`, control lock 30 frames (`engine/system/constants.emp:186-190`). These are
  the S3K constants, not approximations.
* `quadrant = (angle + $20) >> 6` (`player_common.emp:606`) matches S3K's
  `Player_AnglePos` derivation (`sonic3k.asm:18754`), and the sensor pair rotates with it
  (`Player_SensorFloor`, and the per-quadrant probe/step table at
  `player_common.emp:1322-1339`).
* A full 16-byte height profile plus an angle byte plus a solidity class per collision
  cell, with rotated height maps for the wall quadrants
  (`HeightMaps` / `HeightMapsRot`, `player_sensors.emp:186-235`).

**One dangling thread:** `PlayerV.stick_convex` — "full terrain adherence (objects will
set)" — is *read* at `player_ground.emp:435` (bypasses the snap-down window) and `:488`
(suppresses the slip check, commented "loop adherence: no slip"), and is *cleared* at
`:1038` and `player_common.emp:462`. **Nothing ever sets it.**

This is a faithful port of S3K's `stick_to_convex` ($3C), and S3K reads it at exactly the
two matching sites: `Player_AnglePos`'s distance-based detach (`sonic3k.asm:19019`,
`tst.b stick_to_convex(a0); bne` → snap unconditionally) and `Player_SlopeRepel`
(`:23913`, same guard). In S3K it is set by objects that need guaranteed adherence —
Carnival Night's rotating discs are the canonical user. So the field is correct, correctly
placed, and simply has no object that wants it yet. A plain loop does not need it; `$280`
carries you.

---

### 4.5 The owner's steer: get away from the object

Mid-task the owner said:

> "For loops I thought we wanted to get away from the object because there was a better way
> to handle them with our tooling."

He is right about the direction, and I owe him one correction about what it can achieve.
Both are worth stating precisely, because the difference determines what actually gets
built.

#### 4.5.1 The runtime decision is irreducible. The authoring is not.

Which surface the player is on **is a function of history, not of position.** At a loop's
base, the same cell must mean "riding the near arc" when you arrive along the ground and
"back on the ground" when you come down the far arc. The geometry at that cell is identical
in both cases. No purely positional bake can distinguish them, because the distinguishing
fact is not in the level — it is in where the player has been.

So the engine will keep making a per-frame layer decision on the player, whatever we do.
That part does not move to build time and a design that claims it does is wrong.

**What genuinely can move to build time is where the transitions are and what they do.**
Today that lives in a hand-placed object with a hand-tuned subtype byte, in a *different
file from the geometry it belongs to*. Nothing checks that a loop has swappers at all, that
their X is right, or that their vertical band covers the loop. A missing or mistuned
swapper is a silent bug found only by playing. That is the real cost of the object route,
and it is exactly the kind of cost this engine's stated principles — build-time computation
over runtime, compile-time validation over playtesting — exist to remove.

Verified, since the citations were handed to me second-hand: `ENGINE_ARCHITECTURE.md:19`
does say **"collision embedded in block data (S.C.E.-style per-placement, zero separate
maps)"**, and `:20` does list **"angle continuity for loop stability"** as shipped in §5
(implemented at `player_ground.emp:411`; the design note is `ARCH:3080`, "reject angle
jumps > `$20` between frames (prevents loop fallthrough)"). Both citations hold.

And "per-placement" is accurate about what shipped: the solidity a cell gets is chosen by
**that cell's own word** (`bake_plane_cell`, `tools/collision_pipeline.py:213`,
`solidity = (cell_word >> 12) & 3`), not by the shape it references. `solidity.bin` is a
256-byte table indexed by the *interned attribute*, which is per-placement by construction.

#### 4.5.2 The enabling fact: the format already has the room

This is the single most useful thing I found for this question, and it comes from
enumerating what a collision cell actually stores rather than from grepping for a feature.

Aurora's per-plane cell word is 16 bits, and its full decoded layout
(`tools/collision_pipeline.py:209-231`, `:50-57`) is:

| bits | meaning | in use? |
|---|---|---|
| 9:0 | shape index into the base bank | **partly** — the imported S&K bank is 256 shapes, so bits 8-9 never take a value |
| 10 | X-flip (mirrors the height profile, negates the angle) | yes |
| 11 | Y-flip (reflects the angle about `$40`) | yes |
| 13:12 | this plane's solidity — bit 12 = top, bit 13 = left/right/bottom | yes |
| **15:14** | **nothing** | **free** |

**Two bits per cell per plane are entirely unused, and two more are unused in practice, and
they already travel end to end** — Aurora writes them, `apply_editor_collision_overlay`
reads them, `bake_plane_cell` ignores them.

On the runtime side, the attribute byte is an interned index into a shared set. I counted
the live set at `42e70bea`: **21 entries used, 235 free.** (`DEFERRED_WORK.md` says 13 —
that number is stale.)

**So a per-cell layer-transition field needs no format change, no new RAM, no new file, and
no extra lookup on the sensor hot path.** That is a rare position to be in and it is what
makes the tooling route cheap rather than aspirational.

#### 4.5.3 Where the runtime decision would live

The sensors probe many cells per frame and most probes are speculative — both sensors of a
pair, the ±16 extension probes, the ceiling checks. **A transition must never fire from a
speculative probe.** So the read is not on the probe path at all: it is one lookup per
frame, of the cell the player actually resolved onto, at the point where the ground state
is already settled (the `Ground_PostMove` seam, `player_ground.emp:449-460`, immediately
before `Player_SlopeRepel`). Edge-trigger on "the standing cell changed" and the whole
mechanism is roughly ten instructions and one 256-byte table.

A variant worth naming: because S3K's swapper is a *line* (one column, with a vertical
band), the transition is arguably more natural as a thin **per-section transition list** —
a handful of (axis, coordinate, band, effect) records the player's position is compared
against once per frame — rather than as a per-cell attribute. That costs a comparison loop
instead of a lookup, but keeps the attribute set uncluttered and makes a horizontal
transition as cheap as a vertical one. It is the same idea with a different index; I would
pick between them when the first loop is drawn and it is clear how transitions actually
cluster.

## 5. Options

The two questions have independent option sets, so they are listed separately. §5.1 is
sprite orientation; §5.2 is how loop layering gets authored.

## 5.1 Sprite orientation — three routes

They are not variants of one plan; they foreclose different things.

### Option A — Finish the classic: angle-snapped tilted frames + the priority swap

Turn on exactly what S3K does, using art we already ship.

**What it buys.** The look the owner is asking for, at essentially its historical
fidelity: eight orientations, 45° apart, snapped. Loops, quarter-pipes, corkscrews and
steep slopes all read correctly. Because the art is already in ROM and the frame layout
already matches S3K's strides, this is the shortest path from here to "he turns upside
down".

**What it costs.**
* ROM: ~40-60 bytes of new code. Zero new art.
* VRAM: zero. The 32-tile window's existing guard already covers the tilted peak (29).
* DMA: one frame (`$0E`, walk tilt 1) reaches 12 Important slots, becoming reachable
  during running rather than only while holding UP. One art-page landing deferred on that
  frame.
* CPU: ~100 cycles/frame/player.
* Authoring: none for the tilt. The priority-swap and horizontal-swapper work is a
  separate ~100 bytes in `path_swap.emp` plus a subtype re-cut.
* Risk: low and bounded. Every number above is already guarded by a comptime `ensure` that
  scans the whole sheet.

**What it forecloses.** The 45° granularity. Sonic will visibly *snap* between
orientations rather than turn smoothly — which is exactly what the classic games do, and
which some people read as charm and others as jank. It also locks the tilt to
walk/run: any *other* animation (skidding, ducking, the idle poses) stays upright on a
slope, because no tilted art exists for those. S3K has the same limitation.

### Option B — Option A, plus authored tilt for more poses

Same mechanism, wider coverage: commission tilted variants for skid, push, balance, and
whatever else reads badly on a curve, and extend the angle offset to those animation ids.

**What it buys.** A more consistent world. Currently, and under Option A, a player who
skids on the inside of a loop stands bolt upright.

**What it costs.** Art, and it is not cheap. A single tilted block for one 4-frame
animation is roughly 60-75 tiles ≈ 2 KB per character per block; three blocks per
animation per character. Adding tilt to four more animations across three characters is
order 70-100 KB of new art and a matching DPLC re-page. It also pushes squarely into the
DPLC entry-count debt: the safe bound is 10 entries/frame and the sheet already breaks it,
so any new art must be paged by a tool that respects that budget, which does not exist
today. And it needs an artist.

**What it forecloses.** Nothing technical. It is Option A plus money.

### Option C — Interpolated visual angle (a smooth, non-classic tilt)

Keep a separate *visual* angle on the player that eases toward the collision angle over a
few frames, and drive the frame selection from that instead of the raw angle. Optionally
subdivide further than 45° if art ever allows.

**What it buys.** Removes the snap *timing* artefact — the visual angle stops jittering
when the collision angle flickers between two adjacent tiles, which is a real thing on
hand-drawn slopes. Sonic Mania does something in this family. It also gives a natural home
for "keep the last tilt for a few frames after leaving the ground", which reads better on
launch off a ramp.

**What it costs.** One byte of player state (`flip_angle` is already reserved, though it
would be better renamed), ~10 more instructions, and a decision about the easing rate that
someone has to tune by feel. It cannot make the *orientation* smoother — with four art
sets you still land on one of eight poses. So it buys smoother transitions, not smoother
rotation, unless paired with Option B.

**What it forecloses.** Nothing, but it adds a tunable that will need play-testing, and
it puts a piece of state between the physics and the render that the replay hash will need
to cover (`engine/system/replay.emp` hashes the custom window).

### A note on what is *not* an option

**Runtime tile rotation is not on the table, and the survey found no counterexample.**
I had five reference trees swept for it specifically — every `rol`/`ror` in Gunstar Heroes
(6 total across 59,453 lines, none in a tile loop), zero `rol.b`/`ror.b` anywhere in
Vectorman, and nothing in Alien Soldier, Thunder Force IV, Batman & Robin or Ristar.
**Every rotating sprite in every one of these games is pre-rendered discrete art indexed by
an angle bucket, plus the VDP flip bits.** Rotating an 8×8 4bpp tile on a 7.6 MHz 68000
costs a few hundred cycles even with lookup tables; a 29-tile Sonic frame would be five
figures every frame, several times the whole DPLC budget, before any DMA. Stored variants
are the answer, and always were.

## 5.2 Loop layering — how the crossover gets authored

The engine-side mechanism (two planes, per-object layer, layer-aware sensors) is settled
and none of these change it. What differs is **where the transition data lives and who
writes it.**

### Route L — Keep the hand-placed swapper object (what we have)

Author draws the loop in Aurora, then separately places trigger objects in the object list
with a subtype byte encoding band half-height, direction sense and grounded-only.

**Buys.** It exists and works today. It is dynamic — a swapper can be spawned, moved,
despawned, or made conditional on being grounded, and a boss could carry one. It is also
what every classic Sonic game does, so its failure modes are known.

**Costs.** Each swapper occupies an entity-window slot from the same 40-slot budget as
badniks and takes a per-frame object-loop call while on screen. The transition lives in a
different file from the geometry it belongs to, so nothing can check that a loop has
swappers, that they are at the right X, or that their band covers the loop's height. It is
also the *only* mechanism today, which means every static loop pays the dynamic cost.
Three real gaps remain against S3K (§4.3): no priority swap, no horizontal orientation,
one player only.

**Forecloses.** Nothing, but it keeps loop correctness in playtesting rather than in the
build.

### Route P — Paint the transition into the collision cell, bake it with the geometry

Use the spare cell-word bits (§4.5.2) to mark cells that change the player's layer. The
bake folds it into the existing interned attribute; the runtime reads it once per frame
from the cell the player actually stands on (§4.5.3).

**Buys.** The transition and the geometry become *the same data, painted with the same
brush, in the same file, at the same time* — so it cannot be forgotten, cannot be misplaced
relative to the loop, and cannot drift when the loop is moved or copy-pasted (Aurora's
chunk clipboard already carries both collision planes with a stamp). And it becomes
**checkable at build time**: "every cell where plane A and plane B differ is reachable from
a transition" is a bake assertion, which turns a class of silent playtest bugs into build
failures. Deletes the object, its entity slots and its per-frame cost for static loops.

**Costs.** ~256 bytes ROM for a transition table, ~10 instructions per frame, a modest
attr-set expansion (21 of 256 used, so there is room), an Aurora paint mode, and a bake
step. No format change — the bits are already there and already travel. Call it a
medium-sized parcel spanning both repos.

**Forecloses.** The dynamic cases. Painted data cannot be conditional on `ST_IN_AIR`, cannot
be moved by a boss, cannot be spawned or removed. If those are wanted, Route L has to
survive alongside it as the escape hatch — which is fine and cheap, but it means "get away
from the object" is really "stop needing the object for the common case", not "delete it".

### Route G — Generate the layering from the geometry at bake time

The pipeline already flattens, dedupes, spatially orders, pages and generates. Add a step
that reads both authored planes, treats each plane's solid surface as a graph, detects
closed cycles (a loop *is* a closed cycle), and emits the transitions itself. The author
draws a loop and never thinks about layers.

**Buys.** The best possible authoring story, and the one most in keeping with this engine's
stated principles. It also makes the loop *verified by construction* — the tool cannot emit
a loop it could not traverse.

**Costs.** A real algorithm plus its own test suite, and it is the only option here whose
cost I cannot bound honestly from where I sit. Worse, **it does not generalise.** For a
closed loop the traversal intent is derivable from the shape. For two paths that merely
overlap — a bridge over a road, a branch you can take either way — the author's intent
about which surface you end up on is *not* in the geometry, and a tool that guesses will
guess wrong. So Route G is a specialisation of Route P, not a replacement: it needs P's
representation to emit into, and P's explicit painting as the fallback.

**Forecloses.** Nothing, but building it before P exists means building the derivation
before the thing it derives *into*, which is backwards.

---

## 6. Recommendation

**Option A, then Route P, in three parcels, in this order.** The reason for the ordering
is stated at the end and it matters more than the choices themselves.

**Parcel 1 — the tilt (Option A).** It is the owner's actual question, it is ~50 bytes of
code, the art is already paid for, and every comptime guard that could stop it already
passes because they all scan the whole sheet. The measurable downside is one animation
frame reaching the DMA slot cap. I would take that trade immediately, and separately
ledger "re-page Sonic's DPLC to ≤ 10 entries/frame" — which is *already* an open debt in
`collision_data.emp`, not one this creates.

**Parcel 2 — the priority swap, in whichever mechanism exists.** Whether a loop switches
layers by object or by painted cell, it must also switch the player's VDP priority bit or
the loop reads as flat. This is two instructions and it is the difference between "a loop"
and "a circle painted on a wall". Do it in `path_swap.emp` now (it is the only mechanism
today, and the subtype bit is already reserved for it), and carry it into Route P when
that lands.

**Parcel 3 — Route P: paint the transition into the collision cell.** This is the owner's
steer and I agree with it. The clinching argument is not elegance, it is that **the spare
bits already exist and already travel end to end** (§4.5.2), so this is a feature parcel,
not a format migration. The payoff is that a loop becomes checkable at build time instead
of at playtest time, which is the thing the engine's principles are actually for.

**Where I push back on the owner.** "Get away from the object" cannot mean "delete the
object". Two reasons, and he should hear both before choosing:

1. **The runtime decision does not go away** (§4.5.1). Layer membership depends on where
   the player has been, not only where he is. Route P moves the *authoring* into the
   geometry; the engine still decides once per frame. Any pitch that claims otherwise is
   overselling.
2. **The object can do things data cannot** — fire only while grounded, follow only the
   leader, be spawned or moved by something else. Those cases are rare, but when one turns
   up, having deleted the mechanism is expensive. Keep `path_swap.emp` as the escape hatch
   and let Route P take the common case. That is a smaller, safer change than a
   replacement, and it costs nothing to keep.

**Not Route G yet.** Auto-deriving the layering from the geometry is the right ambition and
the wrong first move: it must emit *into* Route P's representation, which does not exist
yet, and it only works where traversal intent is derivable from shape (a closed loop), so
it needs P's explicit painting as its fallback regardless. Build P, draw one loop with it,
then decide whether G is worth the algorithm.

**Not Option B or C yet.** B (tilted art for more poses) is an art commission for a
complaint nobody has made; C (smoothed visual angle) fixes a jitter on content that does
not exist. Both stay available at zero cost for having waited.

The ordering reason: **Parcel 1 is the only item whose result is visible without any level
authoring at all.** Tilt shows up on the slopes already drawn in section 0. Everything
else — the priority swap, Route P, any loop at all — is invisible until somebody draws a
loop. So Parcel 1 first is not just cheapest; it is the only one that can be *seen to
work* before the authoring bottleneck is hit.

---

## 7. Decisions for the owner vs. engineering we can just do

### Decisions — these need you

Written plainly, because these are trades, not implementation details.

1. **Snapped or smooth?** The classic games rotate the character in eight fixed steps —
   he visibly clicks from one pose to the next as he goes round. That is faithful, it is
   free, and the artwork for it is already sitting in the cartridge. A smoother-looking
   version costs a lot of new drawing. **Which look do you want?** My advice: take the
   free faithful one, look at it on a real loop, and decide then.

2. **How much of the character should tilt?** Right now only running and walking have
   sideways-drawn versions. If you skid, brake, or push a block while on the side of a
   loop, you will be drawn standing straight up. The classic games have the same quirk and
   almost nobody notices. Fixing it means commissioning a lot of new drawings. **Is that
   worth it to you, and if so, which moves matter most?**

3. **How many loops, and where?** None of this is visible until somebody draws a loop into
   a level — the shape, plus a second invisible copy of the ground that only applies while
   you are on the far side of it. The tools for that exist and work. **This is the real
   bottleneck, and it is authoring time, not programming time.** Do you want to draw the
   first one, or would you rather I build a small throwaway test loop so the code can be
   proven before you spend effort on a real one?

4. **How should a loop tell the game to switch sides — a marker you place, or something
   you paint?** Today it is a marker: you draw the loop, then separately drop an invisible
   trigger into the level and set a few options on it. It works, but the trigger lives in a
   different place from the loop, so nothing can check that you remembered it, put it in
   the right spot, or made it tall enough. The alternative is to paint the switch straight
   onto the loop with the same brush you draw the loop with, so the two can never come
   apart and the build can *check* them. I recommend the painted version and it needs no
   change to any file format — the room for it is already there, unused. **Two things I
   want you to know before you pick it:** it will not remove the need for the game to make
   a decision while you play (that part cannot be precomputed, because which side you are
   on depends on where you have been, not just where you are), and it cannot do the clever
   cases — a switch that only fires when you are on the ground, or one a boss moves. So I
   would keep the old marker around as a rarely-used backup rather than delete it. **Are
   you happy with "painted by default, marker kept for special cases"?**

5. **Should the tools work loops out for us?** A further step is possible: the build tool
   looks at a loop you have drawn and figures out the side-switching by itself, so you
   never think about it at all. It is the nicest version and I think it is the right
   long-term goal. But it only works for actual closed loops — for anything where two paths
   merely overlap and you could go either way, the tool cannot know which you meant, so you
   would still paint those by hand. **Worth building later, not first** — it needs the
   painted version to exist for it to write into. **Do you want this booked as a follow-up,
   or is the painted version enough?**

6. **One player or two?** The side-switching currently only follows whoever the camera is
   following. Making it work for a second character on screen is a small job, but it is
   only worth doing if two-player is actually planned. **Is it?**

7. **A quality debt you should know about.** There is an existing problem where one
   particular drawing of Sonic needs so much graphics traffic in a single frame that the
   level's own scenery loading gets pushed back by one frame. It already happens when you
   hold UP to look upward. Turning on the tilt makes it happen on one frame of the
   sideways running cycle too. It is invisible in practice, but it is a debt, and the fix
   is a re-processing pass over Sonic's graphics. **Fix now, or ledger it?** My advice:
   ledger it — it is one frame, it predates this work, and the fix wants a tool we do not
   have.

### Engineering — no decision needed, we can just do it

* Reading the angle, mirroring it by facing, adding `$10`, taking `>> 4 & 6`, doubling
  once for run and twice for walk, and adding the result to the mapping frame.
* Setting both sprite flip bits together for the upside-down half.
* Re-running the frame-offset cache refresh after modifying the mapping frame.
* Suppressing the tilt while pushing (S3K does; the push pose has no tilted art).
* Clearing and setting the VDP priority bit on the player in the path swapper.
* Adding the horizontal-line orientation to the path swapper and re-cutting its subtype
  byte to fit.
* Renaming `PlayerV.flip_angle` or leaving it alone — the running tilt needs no state, and
  the name is borrowed from a different S3K feature (the somersault counter).
* Deciding whether `stick_convex` gets a writer. It is dead today; a loop probably does
  not need it, and S3K only sets it from objects (rotating discs).
* Choosing between the per-cell attribute and the per-section transition list for Route P's
  index (§4.5.3) — both are cheap; pick when the first loop shows how transitions cluster.
* Adding a bake assertion that every cell where the two planes disagree is reachable from a
  transition, once Route P exists.

---

## 8. Reference survey — the breadth pass

`CLAUDE.md` requires every reference tree and the online sources for a design phase. What
each one actually contributed:

### 8.1 The convergent result

**Every rotating sprite in every tree uses the same recipe: N stored orientations covering
half a circle, indexed by an angle bucket with a round-to-nearest bias, plus the VDP flip
bits for the other half.** Sonic invented nothing here and Treasure arrived at it
independently — down to the same bias instruction.

| project | stored orientations | effective | index expression | table cost |
|---|---|---|---|---|
| **S3K** `Animate_Sonic` `sonic3k.asm:24737` | 4 | 8 (45°) | `((angle+$10)>>4)&6` | frame-offset only |
| **Sonic 2** `SAnim_WalkRun` `s2.asm:38076` | 4 | 8 (45°) | identical, with the comment *"angle must be 0, 2, 4 or 6"* | frame-offset only |
| **sonic_hack** `code/objects/Sonic.asm:1786` | 4 | 8 | identical, unmodified from S2 | — |
| **S.C.E.** `Objects/Players/Sonic/Sonic.asm:2497` | 4 | 8 | identical, named-constant cleanup only | — |
| **Alien Soldier** `code/disasm.asm:25470` | 8 | 16 (22.5°) | `((angle-$110)>>3)&$1C` → longword table at ROM `$35306` | 32 B ptrs + 96 B records, ≈104 tiles ≈3.3 KB |
| **Gunstar Heroes** `code/disasm.asm:15838` | 8 | 8 | `((angle+$10)>>3)&$1C` → longword table at ROM `$016A50` | 8 longs, 736 B mapping data |
| **Batman & Robin** `disasm/code/effects/effects.asm:2523` | **60** (6°) | 60 | `((angle × $F00) >> 16) × 4` into two 240-byte tables | 480 B |

Alien Soldier is the sharpest reading of the technique — it clears *both* flip bits
(`andi.w #$e7ff`) and sets both (`ori.w #$1800`) exactly as S3K's `moveq #3,d1` does, from
a completely unrelated codebase. Batman & Robin is the outlier worth remembering: **60
orientations is affordable when each entry is a small art-tile-plus-attribute record rather
than a whole character**, which is the right lesson for effects, not for Sonic.

### 8.2 The negative result, stated explicitly

**No runtime 8×8 tile rotation was found in any tree.** Gunstar Heroes has 6 `rol`/`ror`
instructions in 59,453 lines and every one was inspected — none is in a loop over tile
rows. Vectorman contains zero `rol.b`/`ror.b` in the entire file. Nothing in Alien Soldier,
Thunder Force IV, Batman & Robin or Ristar. This is a *searched-and-found-none*, not an
assumption.

### 8.3 Crossover approaches found outside Sonic

* **Vectorman** — the genuine outlier, and the most interesting alternative to a tile
  layer scheme. `code/disasm.asm:4055-4104`: map cell → block-type id → block shape →
  **one 16-bit word per pixel**, whose top 5 bits (`rol.w #5; andi.w #$1f`) are a 32-value
  surface code, with an `$F800` sentinel escaping to a coarser second tier whose shift
  amounts live in RAM. The whole probe is installed as a per-object function pointer. That
  is a per-pixel terrain field with configurable granularity — far finer than a per-tile
  height map, and a genuinely different point in the design space. *Caveat carried from
  the reader: the 5-bit field's semantics (angle vs material class) could not be confirmed
  from any caller — treat "32-step angle" as likely but unproven.*
  Vectorman also has a **budget-capped global DMA art queue** (`sub_007826`, `:6288`) —
  54 entries and 2,880 bytes per frame across the whole scene — which is a DPLC analogue
  with a *global* rather than per-object budget. Given our own per-frame Important-slot
  pressure (§3.3), that is worth a look independently of loops.
* **Sonic 2** — `Obj03`, `s2.asm:45180`, the disassembly's own header being
  *"Object 03 - Collision plane/layer switcher"*. Same subtype layout as S3K's. **S3K added
  the `|dx| < $40` proximity gate; S2 has no such check** — which makes our own decision to
  drop it well-precedented rather than novel.
* **S&K's collision index format** — `LoadSolids`, `sonic3k.asm:9539`: the two planes'
  block→shape arrays are **interleaved byte-by-byte**, so layer select is `base + 0` vs
  `base + 1`. Strictly tidier than S2's two separate arrays. We need neither, because our
  attribute byte is already per-cell per-plane.
* **Object-based solid platforms** (both Sonic games, `SolidObject`/`PlatformObject`) —
  while `Status_OnObject` is set, tile collision is skipped entirely and the angle forced
  to 0. A full override rather than a layer. We have the equivalent (`ST_ON_OBJECT`).
* **Alien Soldier, Thunder Force IV, Batman & Robin, Ristar** — **no multi-surface terrain
  system found in any of them.** For TF4 (a horizontal shooter) and Alien Soldier (a boss
  rush) that is expected. For Batman & Robin the reader could not recover a terrain
  collision model at all — `grep -iE "collis|solid|layer|height|slope|floor|ceiling"` over
  its three level/engine files returns zero hits — so this is *unknown*, not *absent*.
  Ristar likewise contributed nothing: its local `ANALYSIS.md` marks its own
  chained-sprite and slope claims **"INFERRED — not yet confirmed in the disasm"**, and
  `aeon/docs/research/ristar-techniques.md` inherits that uncertainty. Worth knowing before
  anyone cites it.

### 8.4 Per-tile surface-angle tables: a Sonic idiom, not an industry one

Present in S2, S3K, S.C.E. and sonic_hack (256-byte `ColCurveMap` / `AngleArray`, one byte
per collision shape). **Absent from Gunstar, Alien Soldier, Thunder Force IV, Batman &
Robin and Ristar.** Vectorman has a finer per-pixel analogue (above). And in every Sonic
tree the angle byte is **hand-authored in the editor alongside its height map** — there is
no angle-generation tooling in either `s2disasm/build_tools/` or `sonic_hack/tools/`. The
only build-time derivation anywhere is the rotated height map (`ConvertCollisionArray`,
`s2.asm:43366`), a bit-transpose, and even that ships pre-baked with the routine stubbed
to `rts`. We do the same thing: `tools/collision_pipeline.py` derives `heightmaps_rot.bin`
from `heightmaps.bin`.

*A caveat about the five `*_disasm/` trees:* they are raw capstone linear dumps with
100% auto-generated `loc_`/`sub_` labels. Positive findings there were read
instruction-by-instruction and, for the three load-bearing ones (Gunstar, Alien Soldier,
Batman), confirmed against the ROM bytes. **Absences in those trees are absence of evidence
in an unlabelled dump, not proof of absence.**

---

## 9. Interaction with `docs/DEFERRED_WORK.md`

* **"Path-B collision content — wire the secondary index through the strip generator
  (§4.7)"** — already marked fully closed (2026-08-08) and its corrections are accurate.
  **This document confirms it and adds one fact the entry does not carry:** the mechanism
  is closed but *no divergent path-B geometry has been authored anywhere in OJZ act 1*
  (§4.2), so the closed path has never actually been exercised by content. That is worth
  appending, because "closed end to end" reads as "proven", and it is not.
* **The DPLC entry-count ratchet** (`games/sonic4/data/collision/collision_data.emp:34-61`)
  is not currently in `DEFERRED_WORK.md` as an entry; it is ledgered at the site. Option A
  changes its exposure — the 12-entry frame moves from "reachable only while holding UP"
  to "reachable while running" — so if the tilt lands, that ratchet's comment needs
  updating in the same parcel.
* **A stale number in that same entry.** It states "13/255 combos used today, ~242 slots
  headroom". Counting the shipped `solidity.bin`/`angles.bin`/`heightmaps.bin` at
  `42e70bea` gives **21 used, 235 free**. Not a problem — the headroom conclusion survives —
  but the figure has drifted and Route P's costing depends on it, so it should be
  re-quoted rather than copied.
* **Nothing here closes an open entry**, and nothing here is blocked by one. Parcels 1 and
  2 in §6 are ready work, not blocked work. **Route P (Parcel 3) is a new item** and
  belongs in `DEFERRED_WORK.md` once the owner has answered decision 4 in §7 — it spans
  both aeon (bake + runtime + attribute) and Aurora (a paint mode), so it wants a booked
  entry rather than a loose intention. Route G belongs there too, explicitly blocked on
  Route P.

`DEFERRED_WORK.md` is **not modified by this parcel.** The amendments above belong with
whoever lands the corresponding work, so that the entry and the code move together — and
Route P's entry should not be written until it is a decision, not a proposal.

---

## 11. Sources actually opened

**Ours (at `42e70bea`):** `engine/objects/sst.emp`, `engine/objects/animate.emp`,
`engine/objects/sprites.emp`, `engine/objects/frames.emp`, `engine/objects/dplc.emp`,
`engine/objects/objdef.emp`, `engine/level/collision_lookup.emp`, `engine/structs.emp`,
`engine/system/constants.emp`, `games/sonic4/player/player_common.emp`,
`games/sonic4/player/player_ground.emp`, `games/sonic4/player/player_sensors.emp`,
`games/sonic4/objects/path_swap.emp`, `games/sonic4/config/constants.emp`,
`games/sonic4/data/animations/sonic_anims.emp`,
`games/sonic4/data/collision/collision_data.emp`,
`games/sonic4/data/characters/{tails,knuckles}_data.emp`,
`games/sonic4/data/generated/ojz/act1/entity_data.emp`, `games/sonic4/map.toml`,
`tools/collision_pipeline.py`, `tools/ojz_strip_gen.py`, `tools/ojz_block_gen.py`,
`docs/DEFERRED_WORK.md`, `docs/ENGINE_ARCHITECTURE.md`,
`docs/research/{dual-layer-collision,animation-system,collision-system}.md`.
Binary data parsed directly: `games/sonic4/data/dplc/{,optimized/}{sonic,tails,knuckles}.bin`,
`games/sonic4/data/mappings/sonic.bin`, `art/optimized/characters/sonic.bin`,
`games/sonic4/data/editor/ojz/act1/section_*.collattr{,b}.bin` (read-only).

**S3K:** `/home/volence/sonic_hacks/skdisasm/sonic3k.asm` (`Animate_Sonic` :24737,
`Anim_Tumble` :24928, `Player_AnglePos` :18732, `Obj_PathSwap` :39702, `sub_1CDDA` :39796),
`sonic3k.constants.asm:77-78`, `General/Sprites/Sonic/Anim - Sonic S3.asm:38-39`.

**Other references and online sources:** see §8 and §10.
