# Loops and sprite rotation — what we have, what S3K does, what it costs

**Date:** 2026-08-28 · **Branch:** `research/loops` · **Tree read at:** aeon `42e70bea`
(worktree `agent-a55c7332cee812166`). Every claim about *our* tree below is pinned to
that revision — those age fastest and nothing here re-checks them for you.

**Status: RESEARCH AND DESIGN ONLY.** No engine code was written, no bytes moved, no
build run, no emulator touched. Items needing runtime confirmation are marked
**[TAG-RUNTIME]**.

> ## PARCEL 1 (THE TILT) HAS SHIPPED — 2026-08-28, branch `parcel/sprite-tilt`
>
> §6 recommended Option A first. It is built. **The rest of this document is
> unchanged research and its §3.3/§5.1 cost estimates are now superseded by
> measurement**; §§4-5.2 (loop layering, Route P) and Parcel 2 (the priority swap)
> are untouched and still open.
>
> **What shipped.** `Player_ApplyTilt` in `games/sonic4/player/player_common.emp`,
> called from `Player_Display` between `AnimateSprite` and `Player_LoadArt`. **Zero
> engine changes** — the engine already carries `angle`, `status`, `anim` and
> `mapping_frame` on the SST, and `RefreshSpritePieceCount` is already `pub`, so the
> whole policy is expressible game-side. The frame-selection rule (which anim ids
> tilt, the $01/$21 block bases, the 8/4 strides) is Sonic 4 data and stays in the
> game; `AnimateSprite` learns nothing about ground angle. Making the engine
> understand terrain would have been the wrong seam, and it was not needed.
>
> **Corrections to this document's own numbers, all measured:**
>
> | §  | this document said | measured |
> |----|---|---|
> | 3.3, 5.1 | "~40-60 bytes", "~50 bytes" | **110 bytes** of routine + 2 at the call site; **+132 B** total ROM in both sonic4 shapes |
> | 3.3 | VRAM zero | **holds.** RAM also unchanged (89.9% both sides) |
> | 3.3 | one frame (`$0E`) reaches 12 Important entries | **holds, and it is exactly one frame wide** — the next-worst newly-reachable frame is 10, so nothing sits between 10 and the cap |
> | 3.4 | apply after `AnimateSprite`, before `Player_LoadArt` | **holds** |
>
> **The byte overrun has one cause and it is stated here because §3.4 missed it.**
> §3.4 says to apply the offset after `AnimateSprite`. It does not say that
> `AnimateSprite` **early-outs** (`subq.b #1,anim_timer / bpl .done`) and therefore
> does *not* rewrite `mapping_frame` on the frames a script does not advance. S3K's
> `Animate_Sonic` does, which is why it can `add.b d3,mapping_frame(a0)`. A
> transcribed `add` here would compound the block every frame and walk off the end
> of the sheet — and even a correct add would leave the tilt lagging the angle by up
> to the animation hold (8 frames at a slow walk). The routine re-reads the running
> script's own frame byte instead, which is idempotent by construction. **That is
> ~26 of the 110 bytes and it is the whole gap against the estimate.**
>
> This tree had already solved exactly this problem, in exactly this way, and this
> document does not cite it: `games/sonic4/objects/tails_appendage.emp:340-356`, the
> ball-spin direction bank, carries the reasoning in full. It is the house precedent
> and the tilt follows it. (Its own facing fold is NOT the model to copy — it adds
> `$80` when facing left because it works on an arctan of travel, where
> `Animate_Sonic` simply skips the `not`. Copying the wrong one of the two is the
> "mirrors on one side only" bug, and it is now a permanent test.)
>
> **Three further deviations from S3K, all forced and all documented at the routine:**
> no tumble gate (we have no tumble mechanism; the 519 tiles of full-360 art §3.2
> found are still referenced by nothing and are a separate follow-up, selected by a
> counter and a `divu #$16`, not by an octant of the ground angle — it does NOT fall
> out of this selection); push suppression is structural rather than a `btst`
> (`Player_Animate` classifies `ANIM_PUSH` ahead of walk/run, so the tilt gate never
> sees a pushing frame); and no walk/run re-derive from `|ground_vel|`, because
> `Player_Animate` has already made that decision via `ANIM_RUN_THRESHOLD`.
>
> **§3.1's claim that `PlayerV.flip_angle` has no reader and no writer SURVIVES, and
> the tilt did not give it one.** §2.1 was right that the running tilt needs no
> state; it is a pure function of `angle`, `status`, `anim` and `anim_frame`.
>
> **How it is checked.** `tools/sprite_tilt_gate.py`, wired into `build.sh`'s
> post-sigil block (build-fatal, sonic4-only): it takes the routine's extent from
> the listing this build emitted and its bytes from the ROM this build emitted,
> decodes them with capstone, **executes them**, and compares 4,994 results against
> the S3K model re-derived from `sonic3k.asm:24808-24862` — a full 256-angle × 2-facing
> sweep plus every octant boundary and its neighbours, over all 14 animation cursors
> of all three characters' shipped scripts. The executor models one instruction form
> per line the routine contains and **raises on anything else**, so a future edit
> reaching for a new addressing mode stops the build rather than being skipped.
> `tools/test_sprite_tilt.py` (31 tests, in `build.sh`'s pytest lane) runs the same
> sweep over a committed cut of both build shapes, asserts structural invariants of
> the model rather than a copy of its output, and byte-poisons the cut four ways to
> prove the sweep is not vacuous. Red-first evidence: inverting the facing fold in
> source and rebuilding turned the build red with the two facings visibly swapped.
>
> **[TAG-RUNTIME] §3.2's tag stands and this parcel did NOT close it.** Nobody has
> looked at the pixels. The four blocks are established structurally and by matching
> S3K's code and scripts; *which* orientation each block holds is still unverified.
> A wrong block-to-angle assignment would be invisible to every gate above, because
> every gate compares against S3K's arithmetic and not against the art.
>
> **[TAG-RUNTIME] What a play-test can actually show today — measured, and it is
> less than it sounds.** Reading `games/sonic4/data/collision/angles.bin` and
> `solidity.bin` (the committed, interned surface-angle set for OJZ act 1: 20 live
> attribute slots), the steepest authored surface is `$E0` = -45°, and **exactly four
> attributes exceed the first band boundary at ±22.5°** — `$E0`, `$E8`, `$EC`, `$EC`.
> All four land in **block 1**. So shipped content reaches **two of the eight
> orientations**: upright, and one 45° step. **Blocks 2 and 3 and every 180°-flipped
> orientation are unreachable in OJZ act 1** — nothing drawn can put the character
> upside down, because §4.2's finding still holds and no loop exists. The tilt is
> visible today only as a single step on the handful of steep downhill-right slopes.
> That is a content ceiling, not a code one, and it is the same authoring bottleneck
> §7 decision 3 asks the owner about.
>
> **The replay net will diverge, and that is a finding, not a fixture to update.**
> `engine/system/replay.emp` hashes `render_flags` ($0E) and `mapping_frame` ($23) —
> both of the two bytes this routine writes. Every tick where the player is in
> `ANIM_WALK`/`ANIM_RUN` standing on one of those four attributes now hashes
> differently. Flat ground is byte-identical (angle 0 selects block 0 with no flip,
> in both facings, and the routine's write is then a no-op), so the divergence is
> bounded to those cells. The net has **no automated runner** — it needs the emulator
> and a human (`tools/test_replay_fixture.py`'s own docstring) — so this lane could
> not run it and did not re-stamp it. Both fixtures traverse OJZ act 1.
>
> ---

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
at all (§4.5.2). Two corrections he should have with that: the runtime decision itself is
**irreducible** — a loop is traversable in both directions, so the same cell at the top of
the loop needs opposite answers depending on which way you came, and nothing about the cell
can say which (§4.5.1). And the **two-plane representation itself is not the legacy part**:
Sonic Mania's engine still uses two planes, in the same four bits the Mega Drive used
(§10.1). So the honest goal is "stop needing the object for the common case", not "replace
the scheme".

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
`loc_126A4` (`:24808`). The load-bearing part, verbatim:

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

And the two animation scripts it indexes. The tree carries two variants — the S&K one
that actually ships (`General/Sprites/Sonic/Anim - Sonic.asm:38-39`) and a Sonic-3-only
twin (`Anim - Sonic S3.asm`) whose walk cycle starts at frame 1 instead of 7:

```asm
AniSonic00:     dc.b  $FF,   7,   8,   1,   2,   3,   4,   5,   6, $FF
AniSonic01:     dc.b  $FF, $21, $22, $23, $24, $FF, $FF, $FF, $FF, $FF
AniSonic02:     dc.b  $FE, $96, $97, $96, $98, $96, $99, $96, $9A, $FF   ; roll — $FE, not $FF
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
the same sentinel in the same position.

That is not a coincidence worth building on directly, though, and the reason is a concrete
byte. S3K's roll script heads with **`$FE`**, which routes to `loc_12A2A` — a speed-picked
roll path with no angle involvement. **Ours heads with `DUR_DYNAMIC` = `$FF`**, because we
reused the sentinel for "speed-scaled hold" rather than for "angle-dependent". So the two
meanings that S3K keeps separate are merged in our data, and keying the tilt on the header
byte would tilt the rolling ball. **The tilt must key on the animation id (`ANIM_WALK` /
`ANIM_RUN`), not on the duration sentinel.**

**A naming trap worth recording.** S3K's `flip_angle` is *not* the running tilt. It is
the somersault/tumble counter used when Sonic is launched off a spring or a ramp;
`Anim_Tumble` (`sonic3k.asm:24932`) reads it, does `divu.w #$16` (22° steps) and lands on
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

The switcher is **`Obj_PathSwap`, `sonic3k.asm:39702`**, worker `sub_1CDDA` at `:39799`.
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
block word is only half of S3K's layer system. `sub_F264` (`sonic3k.asm:19218`) then does
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

— and these are not merely *similar* to S3K's. Our Walk script's frame sequence
`7, 8, 1, 2, 3, 4, 5, 6` is **byte-identical to S&K's shipped `AniSonic00`**
(`General/Sprites/Sonic/Anim - Sonic.asm:38`), and our Run to `AniSonic01`. Same frames,
same order, same block strides (8 and 4), with the tilted blocks sitting at exactly the
offsets S3K's `add.b d3, mapping_frame(a0)` lands on. The donor data arrived intact; only
the code that uses the second half of it was never written.

**Dead-but-paid-for art in the ROM today: 640 tiles = 20,480 bytes for Sonic** (21% of his
art budget). The same four-block structure is present in Tails' and Knuckles' shipped
sheets at the same frame indices — 655 tiles (20,960 B) for Tails, 664 tiles (21,248 B)
for Knuckles. **Total ≈ 62,688 bytes of rotated character art currently referenced by
nothing.**

**And there is more rotation art than that.** S3K also carries **three full-360° tumble
sets** for the somersault Sonic does off springs and ramps — 12 frames each at base frames
`$31`, `$3D`, `$49`, selected by `flip_angle` through a `divu.w #$16` (30° steps),
`Anim_Tumble` at `sonic3k.asm:24932`. Measuring the same frame ranges in *our* shipped
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
`refresh_piece_count` (`engine/objects/frames.emp:53`) or the sprite draws the wrong
frame's pieces.

**And the idiom already exists in this file.** Knuckles' glide pose selection
(`player_common.emp:814-822`) is the same octant computation pointed at a different angle:

```
        move.b  PlayerV.glide_angle(a0), d1
        addi.b  #$10, d1
        lsr.b   #5, d1                          // low-byte >> 5 -> 0..7
        andi.w  #7, d1
        lea     Glide_Pose_Table8(pc), a1
        move.b  (a1,d1.w), d1
```

Same `+$10` round-to-nearest bias, same shift-and-mask to an octant, same
symmetric-table-plus-facing-flip trick that halves the pose count. The ground tilt is this
with `angle` instead of `glide_angle`, four sets instead of five poses, and *both* flip
bits instead of one. Whoever writes it should read that block first — the house style for
this exact computation is already settled.

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

**And that partial authoring is a predictable failure, not carelessness.** The two planes
are painted *independently*, so ordinary ground — which is solid on both — has to be drawn
twice. A plane B that is a partial copy of plane A is exactly what you get when an author
paints the common geometry into the second plane and stops partway. Sonic Worlds Next
solves this with a **third state — "solid on both"** — so shared geometry is authored once
(§10.4). That is directly relevant to Route P (§5.2) and it should be designed in from the
start rather than discovered later.

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
`y_pos` instead of `x_pos` (`loc_1CEF2`, `:39895`). Ours only ever compares X
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
it is documented at the site, which is the right place. Worth knowing though: **Sonic 2 had
no such gate either** (S3K added it), and **Mania kept one** (`abs(dx) < TO_FIXED(24)`), so
the design space has been visited in both directions by people who shipped.

**One risk our design carries that another engine found the hard way.** Our swapper
despawns when the camera leaves and re-arms `prev_side` on respawn — deliberate, and
documented in the file header as "re-armable by construction". Core Framework's
documentation warns that plane switchers must have "inactive if too far from window"
**disabled**, or players get stuck in loops (§10.4). Our re-arming is exactly the mitigation
that warning implies is needed, so the design looks right — but it is the configuration
another engine found to be a bug source, so it deserves a deliberate test on a real loop
rather than an assumption. **[TAG-RUNTIME]**

**Two upgrades from Mania worth considering when this is touched** (§10.2): the side test
uses `position + velocity` rather than bare position, a one-frame lookahead that removes a
class of fast-player edge cases; and the switcher carries an angle so it need not be
axis-aligned. Neither is required for a first loop.

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

Which surface the player is on **is a function of history, not of position**, and the proof
is one sentence long: **a loop is traversable in both directions.**

Take a loop split the classic way — one layer carries "ground → right arc → top", the other
"top → left arc → ground". Run it rightward and, at the top of the loop, you are finishing
the right arc and must be on the first layer. Run the *same loop leftward* and, at that
*same cell at the top*, you are finishing the left arc and must be on the second. Same
position, same geometry, opposite requirement. The only thing that differs is which way you
came.

So no purely positional bake can be correct for a two-way loop, and any design that claims
to eliminate the runtime decision is either wrong or has quietly made loops one-way.

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
frame, of the cell the player actually resolved onto. Edge-trigger on "the standing cell
changed" and the whole mechanism is roughly ten instructions and one 256-byte table.

**Where it must *not* go, and this is a trap.** The obvious home is the
`Ground_PostMove` fall-through, right after the floor snap writes `angle` and just before
`Player_SlopeRepel`. That spot is **explicitly guarded against exactly this**
(`player_ground.emp:453-460`): *"SEAM GUARD: … `Player_SlopeRepel` must stay IMMEDIATELY
below, and nothing state-specific may be inserted here."* The guard exists because GROUND
and ROLL share the fall-through and SPINDASH deliberately bypasses it.

The correct home is the **shared per-frame player tail** in `Player_Main`, alongside the
quadrant derive (`player_common.emp:606-612`) — a first-class derived value computed once
per frame from last frame's angle, which is precisely the shape a layer update has. That
placement also gets it for free on every state, not only the grounded ones, which matters
because you can enter a loop's far side airborne.

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
hand-drawn slopes. It also gives a natural home for "keep the last tilt for a few frames
after leaving the ground", which reads better on launch off a ramp.

**This is not speculative — Sonic Mania does exactly this and the source is public.**
`Player_HandleGroundRotation` keeps a `rotation` field separate from `angle` and
exponentially lerps it toward `angle << 1`, **at a rate that depends on ground speed**
(`>>2` when slow, `>>1` when fast), with a ±4.5° upright deadzone and a ±22.5°
don't-tilt-at-all gate. §10.3 has the code. If this option is taken, that is the shape to
copy, and the speed-dependent rate is the part I would not have invented.

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

**Buys, second and nearly as important.** The same spare bits can carry a **"solid on both
planes" state** (Sonic Worlds Next's third state, §10.4), so shared geometry is painted
once instead of twice. That removes the exact failure §4.2 measured — a plane B that is a
half-finished copy of plane A — and it roughly halves the authoring burden for every level,
loop or no loop. **This should be part of Route P from the start, not a follow-up.**

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

**Parcel 3 — Route P: paint the transition into the collision cell, *and* add a
"solid on both planes" state.** This is the owner's steer and I agree with it. The
clinching argument is not elegance, it is that **the spare bits already exist and already
travel end to end** (§4.5.2), so this is a feature parcel, not a format migration. The
payoff is that a loop becomes checkable at build time instead of at playtest time, which is
what the engine's principles are actually for.

The "solid on both" state rides along in the same bits and I would not ship Route P without
it. §4.2 measured a plane B that is a half-finished copy of plane A, and that is the
predictable result of making authors paint shared geometry twice. Sonic Worlds Next's
three-state model (§10.4) fixes it at the representation level and pays off on every
level, loop or not.

**A note on confidence.** I went looking for a modern engine that had found a better answer
than the 1992 one, because that is what the owner's instinct was reaching for. **Sonic
Mania's engine still defines `CPATH_COUNT = 2` and still puts plane A's solidity in bits
12/13 and plane B's in 14/15 — the same four bits as the Mega Drive** (§10.1). The
polygon-with-normals alternative fails on its own terms: a track crossover is a
self-intersection, which chain-shape collision explicitly does not support (§10.5). So the
two-plane representation is not a legacy compromise we are inheriting — it is the answer,
and what we are changing is only who writes it and when.

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
   want you to know before you pick it:** it will not remove the need for the game to
   decide something while you play. That part genuinely cannot be worked out in advance,
   and here is the reason in one line — you can run a loop in either direction, so at the
   very top of the loop the game needs opposite answers depending on which way you came in.
   Nothing about the spot itself can tell it that. Second, painted data cannot do the
   clever cases — a switch that only fires when you are on the ground, or one a boss moves
   around. So I would keep the old marker around as a rarely-used backup rather than delete
   it. **Are you happy with "painted by default, marker kept for the special cases"?**

   *One thing I would bundle in and want you to know about:* right now the level has two
   copies of its solid ground — a main one and an alternate one for the far side of loops —
   and ordinary ground has to be drawn into **both**. That is why the alternate copy in the
   level you are working on is a half-finished duplicate of the main one. I would add a
   third option, "solid in both", so ordinary ground is drawn once and only the genuinely
   loop-specific parts get drawn twice. It costs nothing extra to build alongside the rest
   and it makes every level cheaper to author, not just the ones with loops.

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

**`DEFERRED_WORK.md` IS amended by this parcel, on the two points above only** — the
"closed is not the same as exercised" note and the re-counted attr-set figure, both in the
"Path-B collision content" entry. Those are corrections to facts already asserted there, so
they belong with the entry now rather than with future work.

**Everything else is deliberately left out of it.** The DPLC ratchet comment belongs with
whoever lands Parcel 1, so entry and code move together. Route P and Route G should not be
booked until the owner has answered §7's decisions 4 and 5 — a proposal in the deferred
ledger reads as a commitment, and neither is one yet.

---

## 10. Online sources and the modern answer

The most valuable finding in the whole survey is here, and it is a negative one for anybody
hoping the modern engine found a better idea.

### 10.1 Sonic Mania kept the two-plane scheme — and kept the same bits

RSDKv5 (Mania's engine) and RSDKv4 (Sonic 1/2 2013) both still define
**`#define CPATH_COUNT (2)`**, and `Entity` still carries a single `uint8 collisionPlane`
([RSDKv5 `Scene.hpp`](https://github.com/RSDKModding/RSDKv5-Decompilation/blob/master/RSDKv5/RSDK/Scene/Scene.hpp),
[RSDKv4 `Scene.hpp`](https://github.com/Rubberduckycooly/Sonic-1-2-2013-Decompilation/blob/master/RSDKv4/Scene.hpp)).
And the tile-layout word's bit layout, from
[RSDKv5 `Collision.cpp`](https://github.com/RSDKModding/RSDKv5-Decompilation/blob/master/RSDKv5/RSDK/Scene/Collision.cpp):

```c
solid = collisionEntity->collisionPlane ? (1 << 14) : (1 << 12);   // floor
solid = collisionEntity->collisionPlane ? (1 << 15) : (1 << 13);   // wall / roof
```

**Bits 12/13 = plane A top / left-right-bottom, bits 14/15 = plane B — literally the same
four bits the Mega Drive used.** A 2017 engine running on modern hardware, with no reason
to economise, chose to keep the 1992 representation. That is about as strong an
endorsement of the design as exists, and it is the answer to "is there a better way that
modern engines found": for the loop problem specifically, no.

Two things RSDKv5 *did* change, both small and both worth copying:

* **Top-solid and LRB-solid are separate bits, not a 2-bit enum.** That lets
  `TILECOLLISION_UP` (inverted gravity) swap which one means "floor". Our attribute set
  stores a 2-bit enum (`SOL_NONE/TOP/LRB/ALL`); the bits are equivalent in expressive
  power but the split form makes gravity inversion a mask change rather than a table.
* **An orthogonal second axis.** `Entity.collisionLayers` is a bitmask over up to 8 tile
  layers, and a standard zone runs both foreground layers as collision every frame
  ([`Zone.c`](https://github.com/RSDKModding/Sonic-Mania-Decompilation/blob/master/SonicMania/Objects/Global/Zone.c)).
  So Mania is **layers ⊗ planes**: the plane bit is still the loop mechanism, the layer
  mask is for independently-scrolling or destructible foreground. Not something we need.

### 10.2 Mania's switcher, and three things worth stealing

[`PlaneSwitch.c`](https://github.com/RSDKModding/Sonic-Mania-Decompilation/blob/master/SonicMania/Objects/Global/PlaneSwitch.c)
is recognisably the same object as `Obj_PathSwap`, with flags
`HIGHLAYER_LEFT=1, PLANEB_LEFT=2, HIGHLAYER_RIGHT=4, PLANEB_RIGHT=8` — **one plane bit and
one priority bit per crossing side**, exactly S3K's subtype bits 3/4 and 5/6. Three
upgrades:

1. **The switcher can be rotated** (`Zone_RotateOnPivot` with a stored `angle`), so it is
   not axis-aligned. Ours is X-only; S3K's is X-or-Y; Mania's is any angle.
2. **Velocity anticipation.** The side test is `pivotPos.x + pivotVel.x >= self->position.x`
   — one frame of lookahead, not bare position. Cheap, and it removes a class of
   fast-player edge cases.
3. **It is applied to non-player entities too** (`CheckerBall`, `RollerMKII`, `HeavyRider`),
   and the plane is propagated to the sidekick, to spawned dust and to lost rings. **Our
   `Sst.layer` is already per-object, so we are structurally ready for this and S3K was
   not** — a point in our design's favour.

Note also that RSDKv4's *loop* switcher (`PSwitch_Loop`) writes **only the plane**, while
`PSwitch_H`/`PSwitch_V` write plane *and* draw order — i.e. even in the classics' own
reimplementation, priority-switching is a separate concern from plane-switching.

### 10.3 Mania *does* have a separate visual angle — this validates Option C

The classics have one `angle` field. Mania has two, and
[`Player.c`'s `Player_HandleGroundRotation`](https://github.com/RSDKModding/Sonic-Mania-Decompilation/blob/master/SonicMania/Objects/Global/Player.c)
is the reference implementation for what §5.1's Option C describes:

```c
if (self->angle <= 0x04 || self->angle >= 0xFC) { self->rotation = 0; }       // upright deadzone
else {
    int32 targetRotation = 0;
    if (self->angle > 0x10 && self->angle < 0xE8) targetRotation = self->angle << 1;   // don't tilt below 22.5 deg
    int32 rotate = targetRotation - self->rotation;
    int32 shift  = (abs(self->groundVel) <= 0x60000) + 1;    // slow: >>2, fast: >>1
    ... wrap-aware shortest-way-around ...
    self->rotation &= 0x1FF;
}
```

An exponential lerp toward a target derived from the collision angle, **at a rate that
depends on ground speed**, with a ±4.5° upright deadzone and a ±22.5° don't-tilt-at-all
gate. If Option C is ever taken, this is the shape to copy — and the speed-dependent rate
is the detail I would not have thought of.

And the draw-time snap in
[`Drawing.cpp`](https://github.com/RSDKModding/RSDKv5-Decompilation/blob/master/RSDKv5/RSDK/Graphics/Drawing.cpp)
includes **`ROTSTYLE_45DEG: rotation = (entity->rotation + 0x20) & 0x1C0`** — the same
octant snap, round-to-nearest, as `Animate_Sonic`'s `(angle + $10) >> 4 & 6`. And
`ROTSTYLE_STATICFRAMES` is *literally* the Genesis scheme: N logical frames, 2N sprites,
the second half pre-drawn diagonals selected by octant. The modern engine kept the classic
technique as a first-class render mode.

*Caveat carried from the reader:* which `rotationStyle` Mania's walk/run animations actually
use lives in binary sprite data, not source. **Unverified.**

### 10.4 The one idea that would genuinely improve our design

**Sonic Worlds Next** (the official Sonic Worlds successor, on Godot) uses **three states,
not two**: always-solid, high-layer-only, low-layer-only —
["a player on the Low layer will only interact with normal layer and lower layer"](https://github.com/Techokami/SonicWorldsNext/wiki/Collision-Layers-and-Masks).

**That directly diagnoses what I measured in §4.2.** Our two planes are painted
*independently*, so ordinary ground has to be drawn twice — and OJZ section 0's plane B
being a strict subset of plane A, with 644 cells solid on A and none on B, is exactly the
failure mode you would predict from "the author has to paint everything twice and stopped
partway". A third "solid on both" state, authored once, removes that whole class of
mistake — and it is expressible in the spare cell-word bits Route P would use anyway
(§4.5.2). **If Route P is built, this should be built into it from the start**, not bolted
on later.

Corroborating the same complaint from a different direction: **Core Framework**
(a Clickteam Sonic engine) is the only source that names the two-layer scheme's limits
outright, adding layers 2 and 3 for *"more complex level layouts, like S3 Angel Island Loop
closer to the tree, or Sandopolis loop gimmick"*
([DOCUMENTATION.md](https://github.com/niilisto/Core-Framework/blob/dev/DOCUMENTATION.md)).
So two planes is a floor, not a ceiling — worth knowing before the format is set.

Core Framework also carries a practical warning that **applies to us directly**: plane
switchers must have "inactive if too far from window" **disabled**, or players get stuck in
loops. Our `path_swap.emp` explicitly *does* despawn when the camera leaves and re-arms
`prev_side` on respawn (its header documents this as deliberate). That is a defensible
design — but it is precisely the configuration another engine found to be a bug source, so
it deserves a deliberate test rather than an assumption. **[TAG-RUNTIME]**

### 10.5 The "surfaces with normals" alternative does not survive contact

The natural modern instinct is to abandon tile layers for polygon edges with normals. It
does not work, and Box2D's own documentation supplies the reason: chain shapes
**"only support one-sided collision"** and **"self-intersection of chain shapes is not
supported"** ([collision.md](https://github.com/erincatto/box2d/blob/main/docs/collision.md),
[simulation.md](https://github.com/erincatto/box2d/blob/main/docs/simulation.md)).
**A track crossover *is* a self-intersection.** So the polygon representation does not
dissolve the problem — you still split the world into two non-self-intersecting chains and
pick one at runtime. That is the two-layer scheme wearing `categoryBits`.

Related negatives, all firm:

* **SRB2** cannot do loops at all — *"loops require running on walls, something that the
  Doom engine can't do"* ([thread](https://mb.srb2.org/threads/why-there-is-no-loop-physics-in-srb2.33855/)).
  Its substitute is the **zoom tube**: waypoint Things, player forced onto a fixed path.
  Community verdict is that it looks wrong. That is the honest ceiling of the "make the
  loop a scripted rail" idea, and it is the same thing S3K's `Obj_AutomaticTunnel` is.
* **No SGDK or 68000 homebrew implements Sonic-style loops.** No prior art at our hardware
  level outside the Sonic games themselves.
* **No public GalaxyTrail postmortem on Freedom Planet's collision exists.**

### 10.6 Hardware confirmation on rotation, and a correction to the brief

* [plutiedev.com/rotating-sprites](https://plutiedev.com/rotating-sprites), verbatim:
  *"the Mega Drive isn't able to rotate sprites in hardware **and the CPU certainly isn't
  up to it**."* Its entire prescription is pre-drawn frames plus H/V flip.
* [segaretro.org — Sega Mega Drive/Sprites](https://segaretro.org/Sega_Mega_Drive/Sprites):
  the sprite attribute entry is `PR | PL(2) | VF | HF | GFX(11)`. **There is no rotation
  field.** H-flip and V-flip are the only transforms.

Together with the eight-tree source sweep in §8.2, that closes the question.

**A correction to a figure in the dispatch brief:** it estimated "6×6 = 36 tiles worst case"
for a Sonic frame. The measured S2 maximum is **28 tiles** for a gameplay frame (31
including Super Sonic) against a 32-tile VRAM window — and our own shipped sheet peaks at
**29** (§3.2). DPLC gives a **1.71×** dedup on S2's sheet (4,415 referenced tile-slots
resolving to 2,576 unique). The independently-measured S2 rotation surcharge is **610
tiles ≈ 19.5 KB**, against the 640 tiles / 20,480 bytes I measured in our own optimised
sheet — two different methods, two files, agreeing to within 5%.

### 10.7 Sonic 1 solved it a third way, and the disassembly's comments are wrong about it

Worth recording because it is the only genuinely different classic approach, and because a
misleading comment has propagated. Sonic 1 and CD have **no layers**. Bit 7 of the chunk
byte marks a "loop chunk", and `FindNearestTile` substitutes **the next chunk in the list**
when a per-object render flag is set
([s1disasm](https://github.com/sonicretro/s1disasm/blob/master/_incObj/sub%20FindNearestTile%20%26%20FindFloor%20%26%20FindWall.asm)):

```asm
.specialtile:
        andi.w  #$7F,d1
        btst    #sprite_looping_bit,obRender(a0)
        beq.s   .treatasnormal
        addq.w  #1,d1                   ; use the NEXT chunk
```

`Sonic_Loops` sets and clears that bit, hardcoded to GHZ and SLZ only, keyed on chunk id,
Sonic's X within the chunk, and whether `angle` has crossed `$80`. **The reader grepped the
whole tree and found `sprite_looping_bit` read by exactly one routine, and Sonic 1 never
touches `art_tile`'s priority bit** — so the disassembly's own comment that the flag "sends
Sonic to the low plane" is misleading, and Sonic 1's behind-the-loop look is *static art
priority*, not a runtime switch. S2 replacing this with the two-layer scheme was a real
generalisation, not a rewrite for its own sake.

### 10.8 Community documentation vs. what I read in source

The community record **agrees** with everything I established first-hand, and adds three
details:

* [SCHG: Sonic 2 Level Editing](https://info.sonicretro.org/SCHG:Sonic_the_Hedgehog_2_(16-bit)/Level_Editing)
  gives the block word as **`SSTT YXII IIII IIII`** — `TT` = normal layer solidity,
  `SS` = alternate layer, each `00` none / `01` top / `10` LRB / `11` all. Exactly the bits
  I read out of `sub_F264`, and exactly the encoding `tools/collision_pipeline.py` uses.
* **Sonic 1's walk used 6 frames per orientation set, not 8** (offsets 0/6/12/18 via
  `d0 + (d0>>1)` then `×2`); S2 changed it to 8. The s1disasm calls the result *"the octant
  modifier"* verbatim, and marks the `subq.b #1` bias `if FixBugs` with the note *"Fix
  off-by-one-radian error (this was implemented in S2/S3K)"*. So the bias I quoted in §2.1
  is a *bug fix*, not an arbitrary constant.
* Angle `$FF` is a **flag**, not an angle: *"A 360° (255) Angle is used as a flag to notify
  an object to use its own angle to the nearest 90°"*
  ([SPG: Solid Tiles](https://info.sonicretro.org/SPG:Solid_Tiles)). Our pipeline already
  preserves this — `collision_pipeline.py`'s flip helpers are asserted to keep odd angles
  odd (`"odd-flag must stay odd through xflip"`), which is the same convention.

**And one negative worth stating:** the Sonic Physics Guide **does not document sprite
orientation at all.** Its Animations page covers timing only. So anyone looking for the
tilt mechanism in the community's canonical reference will not find it — which is probably
why the folklore exists.

### 10.9 Not covered

One reader in the online lane did not return. **68000 rotation cycle-cost figures, VBlank
DMA byte budgets, SpritesMind rotation threads, md.railgun.works, and Hidden Palace
prototype material are NOT COVERED** by this document. The rotation question (§10.6) was
answered from other sources instead; the rest is simply absent, and none of the
recommendations in §6 depend on it.

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

Measurements were taken with throwaway parsers over the shipped binaries (DPLC frame table,
mapping frame table, attribute-set tables, and the two editor collision planes). Every
number in §3.2, §3.3, §4.2 and §4.5.2 is reproducible from the files named above; none
came from an emulator.

**S3K (read first-hand):** `/home/volence/sonic_hacks/skdisasm/sonic3k.asm` —
`Animate_Sonic` :24737, its walk/run branch `loc_126A4` :24808, the offset write
`loc_12742` :24870, `Anim_Tumble` :24932, `Player_AnglePos` :18732 and its
`stick_to_convex` guard :19019, the per-layer shape resolve `sub_F264` :19218,
`LoadSolids` :9539, `Obj_PathSwap` :39702 with worker `sub_1CDDA` :39799 and the
horizontal variant `loc_1CEF2` :39895, `Player_SlopeRepel` :23911, `Obj_AutoSpin` :42298,
`Obj_AutomaticTunnel` :57183; `sonic3k.constants.asm:77-78`;
`General/Sprites/Sonic/Anim - Sonic.asm:38-40` (the S&K scripts that ship) and
`Anim - Sonic S3.asm` (the S3-only twin).

**Other reference disassemblies:** surveyed in §8 with per-project citations — s2disasm,
sonic_hack, S.C.E., and the five raw capstone trees under
`The Adventures of Batman and Robin/` (Batman & Robin, Vectorman, Gunstar Heroes, Alien
Soldier, Thunder Force IV, Ristar).

**Online sources:** cited inline in §10 with URLs — the RSDKv5, RSDKv4, Sonic Mania and
RSDKv4-Script decompilations; s1disasm; Sonic Retro's SPG and SCHG pages; SonLVL's manual;
Hatch Game Engine; Sonic Worlds Next; Core Framework; Box2D's collision and simulation
docs; Godot and Unity layer/mask docs; the SRB2 forums and wiki; plutiedev; segaretro.

**Caveats on sourcing, carried forward rather than buried.** The five `*_disasm/` trees are
raw capstone dumps with entirely auto-generated labels, so absences there are absence of
evidence, not proof (§8). Sonic Retro sits behind a proof-of-work wall; the SPG/SCHG quotes
in §10.8 were fetched first-hand through it, but a report on the same topic that could not
get through would be quoting a search-index paraphrase. And one reader in the online lane
never returned, so §10.9's topics are simply not covered.
