# INSTA-SHIELD — Sonic's airborne ability

**Date:** 2026-08-26 · **Branch:** `parcel/instashield` · **Base:** `master` `94b384a2`

Owner's ask, verbatim and complete: *"Sonic instashield"*.

---

## 0. The measured starting point (cited, not re-derived)

- **The airborne-ability seam is BUILT.** `games/sonic4/player/player_air.emp:229-243`
  runs the active character's `cd_ability` hook on a FRESH jump press while already
  airborne (`Player_Ability`, `games/sonic4/player/characters.emp:129`), gated on the
  jump buffer being unspent so the launch press cannot fire it. The long comment block
  above it settles the frame semantics and states the rule this parcel obeys: **an
  ability whose S3K reference acts on the press frame applies its own press-frame
  effect INSIDE its hook, never by moving the seam** (the seam is under the replay
  gate). Nothing in `player_air.emp` changes here.
- `CharDef_Sonic.cd_ability` is `extern("Ability_None")` (`sonic.emp:41`) and
  `cd_ability_wh: 0` (`:52`).
- **There is no shield system.** `grep -ri shield games/sonic4 engine --include=*.emp`
  returns one unrelated hit (a comment in `sound_sequencer.emp`). `PlayerV.status_secondary`
  (`player_common.emp:92`, *"reserved condition bits (speedshoes etc.) — 0 for now"*)
  exists, is cleared by `Player_Init` (`:440`), and has **no other writer tree-wide**.
- **There is no damage system.** `Touch_Enemy`, `Touch_Boss`, `Touch_Hurt`,
  `Touch_Projectile`, `Touch_SolidBreak`, `Touch_SolidHurt` are all `rts` stubs
  (`engine/objects/collision.emp:200-227`).
- The ring sparkle (`games/sonic4/objects/ring_sparkle.emp`, landed 2026-08-26) is the
  model for "donor art + VRAM region + short-lived effect object"; the Tails appendage
  (`games/sonic4/objects/tails_appendage.emp`) is the model for "effect object that
  re-reads its parent every frame and streams its own DPLC".

---

## 1. What S3K actually does (`skdisasm/sonic3k.asm`, read, not summarised)

### 1.1 The trigger — `Sonic_ShieldMoves` (`:23401-23486`)

```
Sonic_ShieldMoves:
        tst.b   double_jump_flag(a0)     ; already used this airborne stretch?
        bne.w   locret_11A14             ;   -> nothing
        move.b  (Ctrl_1_pressed_logical).w,d0
        andi.b  #A|B|C,d0
        beq.w   locret_11A14
        bclr    #Status_RollJump,status(a0)      ; (1) ALWAYS, before any shield test
        tst.b   (Super_Sonic_Knux_flag).w ...    ; (2) super -> hyper dash / flag=1
Sonic_FireShield:
        btst    #Status_Invincible,status_secondary(a0) -> ret
        btst    #Status_FireShield  ... -> fire dash
Sonic_LightningShield: ... Sonic_BubbleShield: ... Sonic_CheckTransform: ...
Sonic_InstaShield:
        btst    #Status_Shield,status_secondary(a0)     ; (3) plain S2 shield -> ret
        bne.s   locret_11A14
        move.b  #1,(Shield+anim).w                      ; (4) play the shield anim
        move.b  #1,double_jump_flag(a0)                 ; (5) ATTACKING
        move.w  #sfx_InstaAttack,d0                     ; (6) SFX ($42)
        jmp     (Play_SFX).l
```

Five facts, in order:

1. **The roll-jump lockout is cancelled unconditionally** on any qualifying airborne
   press — before the super test, before every shield test. It is the press-frame
   effect the seam comment predicted.
2. Super/Hyper and each elemental shield take the press instead; each sets
   `double_jump_flag = 1` itself, so the one-shot is shared across the whole family.
3. **Any barrier suppresses the insta-shield.** Invincibility and the three elementals
   are filtered out above; the plain S2 shield is filtered here.
4/5/6. The visual is a separate persistent object told to play its animation; the flag
   goes to 1; a sound plays.

### 1.2 The flag — `double_jump_flag`, three values

| value | meaning | writer |
|---|---|---|
| 0 | available this airborne stretch | `Player_TouchFloor` (`:24379-24390`) on **landing** |
| 1 | ATTACKING | `Sonic_ShieldMoves` (`:23481`) on the press |
| 2 | spent — attack over, no second insta-shield until landing | `Obj_InstaShield_Main` (`:34615`) |

`Player_TouchFloor`'s clear is `tst.b double_jump_flag / beq ret / ... / move.b #0`.
So the one-shot is **per airborne stretch, reset on landing** — not per jump. Walking
off a ledge and pressing jump gets you an insta-shield, because `Sonic_ShieldMoves`
hangs off the airborne mode handler and the flag is still 0.

### 1.3 The visual — `Obj_InstaShield` (`:34570-34630`)

Init: `width_pixels`/`height_pixels` = `$18` (S3K's are HALF-extents), `priority $80`
(against the player's `$100`; in S3K the lower value draws in FRONT), palette 0,
`anim = 1` (write 1, `prev_anim` forced), art streamed by `PLCLoad_Shields`.

Main, every frame: inherit the parent's `x_pos`/`y_pos`, inherit `status` masked to the
orientation bit, inherit the high-priority art bit, `Animate_Sprite`, then

```
        cmpi.b  #7,mapping_frame(a0)     ; the LAST script entry
        bne.s   .notover
        tst.b   double_jump_flag(a2)     ; still in an attacking state?
        beq.s   .notover
        move.b  #2,double_jump_flag(a2)  ; mark the attack over
```

and it returns early with no draw at all while the player is invincible.

### 1.4 The animation — `Anim - Insta-Shield.asm`, derived

```
anim 0:  dc.b $1F,  6, $FF                                  ; idle: the EMPTY frame
anim 1:  dc.b   0,  0,0,1,2,3,4,5,6,6,6,6,6,6,6,7, $FD, 0   ; the attack
```

The first byte is the DURATION; the frame list is the **14** bytes
`0,1,2,3,4,5,6,6,6,6,6,6,6,7` (frame 0 appears once — the leading `0,0` is
duration-then-frame-0, which is easy to misread as a doubled first frame). Both S3K's
`Animate_Sprite` (`:36160-36178`, `subq.b/bcc`) and Aeon's `AnimateSprite`
(`engine/objects/animate.emp:91`, `subq.b/bpl`) show a frame for **duration + 1**
display frames, so `0` means one frame each and the attack script is **14 display
frames long**.

`Map - Insta-Shield.asm` has 8 offset words for **7 distinct frame bodies**: frames 0-5
are the visible flash (3, 3, 2, 3, 3, 3 pieces — confirmed by the converted blob), and
offsets **6 and 7 both point at `word_1A152: dc.w 0` — a ZERO-PIECE frame.** So the
script is **6 entries of visible art followed by 8 entries of nothing**, and the flag
flips to 2 on the 14th, the first and only entry whose frame index is 7.

**The attack window is therefore 14 frames, and more than half of it is invisible.**
That is deliberate in S3K: the hitbox outlives the flash.

Frame-for-frame, with `TouchResponse` running on Sonic before the Shield object in the
same pass: the press frame is frame 1 of 14 and reads flag = 1; the 14th frame still
reads 1 when the touch test runs and the object writes 2 immediately after; frame 15
reads 2. **14 attacking frames inclusive of the press frame.**

(The converted mapping blob independently corroborates §1.5: every visible frame's
bounding box comes out `(-24, +24)` on both axes — the same `$18` the object declares
and the same `$18` the expanded touch box uses.)

### 1.5 The hitbox — `TouchResponse` (`:20614-20646`)

```
        tst.b   character_id(a0)        ; Sonic only
        bne.s   Touch_NoInstaShield
        move.b  status_secondary(a0),d0
        andi.b  #$73,d0                 ; any shield, or invincible?
        bne.s   Touch_NoInstaShield
        cmpi.b  #1,double_jump_flag(a0) ; ATTACKING (not 0, not 2)
        bne.s   Touch_NoInstaShield
        move.w  status_secondary(a0),-(sp)
        bset    #Status_Invincible,status_secondary(a0)   ; contact = the player WINS
        move.w  x_pos(a0),d2
        move.w  y_pos(a0),d3
        subi.w  #$18,d2                 ; box left   = x - $18
        subi.w  #$18,d3                 ; box top    = y - $18
        move.w  #$30,d4                 ; box width  = $30
        move.w  #$30,d5                 ; box height = $30
        bsr.s   Touch_Process
        ... restore status_secondary, rts        ; NOTHING ELSE is tested this frame
```

against the normal path (`Touch_NoInstaShield`), which is
`x - 8`, width `$10`; `y - (y_radius - 3)`, height `2*(y_radius - 3)`.

**The arithmetic, derived:**

| | half-width | half-height | box |
|---|---|---|---|
| Sonic standing (`y_radius $13`) | 8 | `$13 - 3` = 16 | 16 x 32 |
| Sonic in a ball (`y_radius $E`, i.e. every jump) | 8 | `$E - 3` = 11 | 16 x 22 |
| **insta-shield attacking** | `$18` = **24** | `$18` = **24** | **48 x 48** |

`$18` is not a magic constant: it is exactly `Obj_InstaShield`'s declared
`width_pixels`/`height_pixels` (`:34576-34577`), which in S3K are half-extents. **The
ability's touch half-extent IS the effect object's own half-extent** — that is the
derivation, and it is why one number serves both axes. The expansion over a jumping
Sonic is `24 - 8 = 16 px` horizontally and `24 - 11 = 13 px` vertically, per side.

Two more properties that matter and are easy to miss:

- It is a **replacement**, not a union: the expanded sweep is the *only* sweep that
  frame (`bsr Touch_Process` then `rts`).
- The player is made **invincible for the duration of that sweep only**, and restored
  after — so an enemy contact resolves as a kill rather than as damage, without
  granting real invincibility.

### 1.6 The SFX

`sfx_InstaAttack` = S3K SFX **`$42`** (`sonic3k.constants.asm:1193`).

---

## 2. Design

### 2.1 The binding

`CharDef_Sonic.cd_ability` = `extern("Ability_InstaShield")`
(`games/sonic4/player/player_instashield.emp`, a new module in the object bank beside
`player_fly.emp`/`player_glide.emp`). `cd_ability_wh` stays **0** — see §2.4.

`Ability_InstaShield` is S3K's `Sonic_ShieldMoves` past the press test, in S3K's order:

```
        tst.b   PlayerV.instashield(a0)          ; (1) one-shot, per airborne stretch
        bne     .done
        cmpi.b  #PSTATE_ROLLJUMP, PlayerV.player_state(a0)   ; (2) S3K's bclr Status_RollJump
        bne     .not_rolljump
        moveq   #PSTATE_JUMP, d0
        jbsr    Player_SetState
    .not_rolljump:
        move.b  PlayerV.status_secondary(a0), d0 ; (3) THE SUPPRESSION PREDICATE
        andi.b  #INSTASHIELD_SUPPRESS_MASK, d0
        bne     .done
        move.b  #INSTASHIELD_ATTACKING, PlayerV.instashield(a0)   ; (4)
        jbra    InstaShield_Spawn                                 ; (5) the visual
    .done:  rts
```

**Why the roll-jump cancel is a state change and not a bit clear.** Aeon has no
`Status_RollJump` bit: the air-control lockout is `AIRF_INPUT_LOCK`, set by
`PState_RollJump`'s preamble into `d6` (`player_air.emp:70-71, 92`) — it is a property
of the STATE. `PSTATE_ROLLJUMP` and `PSTATE_JUMP` are otherwise identical (same
`AIRF_RELEASE_CAP`, same `PHook_AirBallEnter`), so the transition is exactly "lift the
lock" and nothing else. It is **gated on actually being in ROLLJUMP** — S3K's `bclr` is
a no-op on a clear bit, but an unconditional `Player_SetState(PSTATE_JUMP)` would curl
an uncurled faller (`PHook_AirBallEnter` runs `PHook_EnsureBall`), which S3K's `bclr`
plainly does not do.

**One frame of deviation, stated.** S3K's `bclr` takes effect the same frame, because
`Sonic_ChgJumpDir` re-tests `Status_RollJump` after `Sonic_JumpHeight` returns. Here the
lockout for the current frame is already latched in the caller's `d6` and the ability
hook's contract forbids touching it (`clobbers(d0-d2/a1-a2)`; `d6` must survive —
`player_air.emp:237-241`). So air control returns on the **next** frame. Widening the
hook contract to let an ability write `d6` is a seam change under the replay gate and is
not worth one frame of a lockout; booked, not built.

### 2.2 The one-shot state — a NEW `PlayerV` byte, and why not an existing one

`PlayerV` (`player_common.emp:89-170`) spends **26 of its 30 usable bytes**. The
ability-scratch block at its tail carries a documented UNION principle: *"exactly one
character is resident per slot, so Knuckles' glide/climb and any later ability re-use
the same bytes under their own names"* — but the language cannot express byte-sharing,
so `fly_fuel`, `fly_thrust`, `glide_angle`, `knux_step`, `knux_timer` are each
**declared in place**. This parcel follows that established precedent rather than
renaming `fly_thrust` (Tails' flap ramp, and S3K's own `double_jump_flag` for him):

```
        instashield:      u8,     // 0 ready / 1 attacking / 2 spent
```

appended at offset 26 (`$4A`), taking the overlay to 27 of 30. **Appending moves no
existing offset**, so nothing else is re-addressed and no layout re-stamp is implied.

**The block's replay-hash comment must change, and does.** The scratch block is
documented as *"address-free AND SONIC-UNREACHABLE"*, which is why `Player_Init`
deliberately does not clear those bytes. `instashield` is the **first Sonic-reachable
byte in that block**, so its own comment states that plainly and it is cleared where the
reset belongs rather than at init.

**Where it clears.** S3K clears in `Player_TouchFloor` (landing). Aeon has no single
landing routine — Knuckles' four landing paths deliberately bypass the airborne helpers
(see `PHook_GroundEnter`'s comment) — but every path lands *in a state*, and for Sonic
that state is `PSTATE_GROUND` or `PSTATE_ROLL` (a down-held landing goes straight to
ROLL via `Air_LandState`). So the clear goes in **`PHook_GroundEnter` and
`PHook_RollEnter`**, the two enter hooks a Sonic landing can reach. `PHook_SlideEnter`
and `PHook_ClimbEnter` are Knuckles-only grounded states and are named in the comment,
so a future Sonic ability that reaches them is a conscious change and not a silent gap.

Writing 0 over 0 is **hash-neutral**: the replay hash folds VALUES, so for every
recorded frame in which Sonic never insta-shielded these two `clr.b`s change nothing.

### 2.3 The visual — an effect object that re-reads its parent, NOT a fire-and-forget drop

S3K makes it a child object that inherits the player's position every frame. That is
required, not stylistic: Sonic moves up to ~16 px per frame and the flash is drawn
centred on him for 7 frames. The ring sparkle's fire-and-forget shape (position written
once) would visibly lag.

So: **`AllocEffect` slot + `parent_ptr` set, but deliberately NOT linked into the
parent's sibling chain.** The Tails appendage owns the only chain on a player slot and
uses `sibling_ptr != 0` as its presence test, with its header stating that a second kind
of child would need a discriminator. Leaving this child unchained **preserves** that
invariant instead of breaking it, and costs nothing the insta-shield needs:

- *Dying with the player* — the cascade's only service — is irrelevant for an object
  whose script deletes it after 15 frames. (No path releases a player slot in this
  engine today; there is no death.)
- *Findability on a character switch* — the appendage needs it; a 15-frame flash does
  not. A debug character-cycle mid-flash leaves a Sonic sprite finishing its animation
  on the new character for at most 15 frames, which is strictly better than the
  alternative (a live insta-shield making `TailsAppendage_Refresh` believe Tails already
  has his tails, so Tails renders without them for the rest of the act).

`InstaShield_Main` is `TailsAppendage_Main` minus the Tails-specific parts:

```
        movea.w Sst.parent_ptr(a0), a1
        move.l  x_pos(a1), x_pos(a0)         ; S3K inherits position outright
        move.l  y_pos(a1), y_pos(a0)
        move.b  status(a1), status(a0)       ; facing -> AnimateSprite's flip bits
        cmpi.b  #INSTASHIELD_LAST_FRAME, mapping_frame(a0)   ; S3K's `cmpi.b #7`
        bne     .not_over
        cmpi.b  #INSTASHIELD_ATTACKING, PlayerV.instashield(a1)
        bne     .not_over
        move.b  #INSTASHIELD_SPENT, PlayerV.instashield(a1)
    .not_over:
        jbsr    AnimateSprite                ; may DELETE this slot (AF_DELETE)
        <Perform_DPLC_Deferrable>
        jbra    Draw_Sprite
```

The `cmp`-before-write is S3K's and is kept for S3K's reason: the player may have landed
(flag back to 0) while the flash was still running, and the flash must not resurrect a
`2` over that.

**The terminal test runs BEFORE the animator, and that ordering is DERIVED, not
stylistic.** S3K tests after, because its `TouchResponse` runs on the player BEFORE the
Shield object in the same pass, so the frame on which the object writes `2` is still an
attacking frame for the touch test — 14 of them. Aeon's level tick is the other way
round: `RunObjects` (players AND effects) then `TouchResponse`
(`games/sonic4/test/ojz_scroll_test.emp:597, 693`), so a write during the object's own
call is visible to the same frame's touch test and S3K's placement would give **13**.
Moving the test one call earlier — it then sees the frame the PREVIOUS call set — puts
the write on the object's 15th and final call, the one where `AF_DELETE` retires it, and
restores the count to **exactly 14**. Same reference behaviour, opposite instruction
order, because the surrounding order is opposite.

Running after `AnimateSprite` is what makes the delete safe to sit under: the slot is
zeroed by then, and `Perform_DPLC` reads `mapping_frame == prev_frame == 0` and returns,
while `Draw_Sprite` guards null `mappings` (`sprites.emp:72-74`) — the same
animate-then-draw-a-dead-slot path `dust_puff` and `ring_sparkle` already run. The
parent pointer is read ONCE, at the top, so nothing dereferences a stale `a1` afterwards.

**Priority band** `PLAYER_PRIORITY_BAND + 1` = the dust's and the sparkle's. S3K's
`priority $80` against the player's `$100` means IN FRONT; Aeon's bands are inverted
(`Render_Sprites` walks 7 -> 0, higher = front), so the RELATIONSHIP transfers and the
number does not. Different band from the player, so the intra-band per-frame order
reversal cannot flicker it.

**The zero-piece frames are safe.** `Render_Sprites` reads the frame's piece-count word
and `beq .next_object` (`sprites.emp:299`), so a 0-piece frame simply emits nothing.
`Perform_DPLC` likewise handles a 0-entry frame (`subq.w #1,d4 / bmi .done`,
`dplc.emp:159`). The invisible tail of the attack window costs no SAT entries and,
because the composer zeroes those DPLC frames (§2.5), no DMA either.

**`AF_CALLBACK` was considered and rejected for now.** `engine/objects/animate.emp`
carries a `$FA` callback opcode whose *"installable-target set is EMPTY today"*, and the
attack-over write is exactly the shape it was built for. It is not used here because
this parcel would then be the first exercise of an untested engine dispatch, and S3K's
own structure (test the terminal frame in the object body) is both simpler and the
reference. Booked as a follow-up that would retire the forward machinery.

### 2.4 THE HITBOX EXPANSION IS **BLOCKED** — and `cd_ability_wh` is the wrong mechanism

The parcel brief asks for the expansion via `cd_ability_wh` + `PHook_EnsureAbility`.
**That would be a bug, and it is being reported rather than built.** Measured:

`cd_ability_wh` feeds `set_ability_size`, which writes `size_wh_off()` =
`Sst.width_pixels`/`height_pixels` (`player_common.emp:305-309`, `sst.emp:100-115`).
Those two bytes are **the TERRAIN collision box as well as the touch box**:
`player_sensors.emp:343-346` and `:547` read them and halve them into the sensor radii
(*"radii = SST_width/height_pixels >> 1"*). Knuckles' 10x10 ability box is a **physics**
box. Writing S3K's 48x48 attack box there would give Sonic a 48x48 terrain footprint for
15 frames of every insta-shield — he would stand 24 px above the floor and jam in every
corridor. S3K's expansion lives **only inside `TouchResponse`** and never touches
`y_radius`/`x_radius`. `cd_ability_wh` therefore stays 0 for Sonic.

The correct home is `engine/objects/collision.emp`, and it is **blocked on the damage
system**:

1. **Every handler the expansion exists to reach is an `rts` stub.** `Touch_Enemy`,
   `Touch_Boss`, `Touch_Hurt`, `Touch_Projectile`, `Touch_SolidBreak`, `Touch_SolidHurt`
   do nothing. An expanded box would be a mechanism with no observable effect — which is
   also why the emulator check *"see the expanded hitbox connect"* is not runnable today.
2. **A blanket expansion would be actively wrong.** Aeon's `TouchResponse` dispatches
   solids, springs and monitors through the SAME AABB that S3K reserves for the damage
   family (S3K resolves solids in `SolidObject`, outside `TouchResponse` entirely). A
   48x48 player box would let solid objects push Sonic from 24 px away and let springs
   fire from off-contact — a real regression, in exchange for nothing.
3. **Doing it correctly means a per-type box**, i.e. hoisting the type dispatch above
   the AABB in the engine's hottest per-object loop, paid on every object every frame,
   for a family that currently returns immediately.

So the expansion is **not built**. What ships instead is the state it needs, complete
and correct: `PlayerV.instashield` with S3K's three values and S3K's exact 15-frame
window, plus the attacking predicate itself, which is one comparison against
`INSTASHIELD_ATTACKING` (see §2.6b) and whose sole reader today is the visual's
attack-over write. The derivation of `$18` is recorded in §1.5 and booked; no dead constant is
emitted for it, because a constant nothing reads is comptime-inert and proves nothing.

### 2.5 Art, DPLC, mappings — provenance and pipeline

**The art is already in-tree, and it is sonic_hack's.**
`art/uncompressed/shields/insta_shield.bin` (1664 B = **52 tiles**) is **byte-identical**
(`md5 a8872f8e…`) to `sonic_hack/art/uncompressed/instashield.bin`, imported at
`2a0895aa` *"extract sprite art + DPLC tables from sonic_hack"*. It is **not** skdisasm's
(`0aea1dc5…`, 855 bytes differ): the donor is the recoloured S4 version, and the recolour
is exactly what makes it correct here.

**Palette — measured, not assumed.** A nibble census of the donor blob uses indices
`{0, 6, 7, 8}` only (0: 1935, 6: 791, 7: 253, 8: 349). In `art/palettes/SonicAndTails.bin`
— the file `Pal_SonicTails` embeds, itself byte-identical to sonic_hack's — those are
`6 = $0EEE` (white), `7 = $0CAA`, `8 = $0866`: a white -> blue-grey ramp. So the flash
draws on **CRAM line 0, Sonic's own line, with no remap**, which is also what S3K does
(`make_art_tile(ArtTile_Shield,0,0)`). skdisasm's blob uses `{0,1,$C,$D}` and would draw
in Sonic's *red* on our palette — a comptime index census pins the right donor.

**The committed DPLC is WRONG and is regenerated.** `games/sonic4/data/dplc/insta_shield.bin`
(24 B) carries **3 frames, all pointing at block A**; the donor has **8 frames** across
two blocks. It is a `PENDING_PAIRS` entry in `tools/verify_sprites.py` — "on disk and
verifiable, but not embedded in the ROM today" — so nothing ever noticed. This parcel
replaces it.

**Mappings do not exist in-tree** and are converted from the donor.
`sonic_hack/mappings/sprite/Instashield.asm` is the S2 8-byte piece format with S3K's
geometry verbatim; `sonic_hack/mappings/spriteDPLC/Instashield.asm` is S3K's DPLC format,
which is **byte-for-byte Aeon's DPLC format** (offset-word table, then `count` + entry
words of `(tiles-1)<<12 | start`).

`tools/compose_instashield.py` (new) is the composer, in `compose_ring.py`'s shape:

| output | derivation |
|---|---|
| `games/sonic4/data/mappings/insta_shield.bin` | donor `.asm` assembled, then `tools/convert_s2_mappings.py::convert_mappings` (imported, not re-implemented) |
| `games/sonic4/data/dplc/insta_shield.bin` | donor `.asm` assembled verbatim, **except** that any frame whose mapping frame has 0 pieces is emitted with a 0-entry DPLC frame |
| `games/sonic4/data/animations/insta_shield_donor_anim.bin` | the donor's raw S3K attack script (17 bytes), embedded as a `const` only — **0 ROM bytes** — so the animation gate's expectation is computed from the donor rather than typed in |

The art itself is **not re-emitted**: it is already in-tree, and the composer verifies it
against the donor instead.

The one deviation from the donor DPLC, stated and gated: **frames 6 and 7 draw zero
pieces, so they need zero tiles.** S3K reaches the same place differently — its object
loads a DPLC only on `mapping_frame` 0 and 3 — while Aeon's generic `Perform_DPLC` loads
on every frame change, so leaving the donor's entries there would DMA 928 bytes twice for
frames that draw nothing. A comptime `ensure` pins the correspondence in both directions
(zero pieces <=> zero entries), so the two blobs cannot drift apart.

`tools/test_instashield_art.py` (new) re-runs the composer against the donor into a tmp
dir and asserts both outputs are byte-identical to the committed blobs, plus the art
identity and the index census in Python. It **skips loudly by name** when
`AEON_SONIC_HACK_DIR` is absent, exactly as `tools/test_gen_dust.py` does.

### 2.6 VRAM

Peak DPLC frame = **29 tiles** (block B: `$F017` = 16 from tile 23, `$C027` = 13 from
tile 39). The art is 52 tiles total, so residency is not an option: the only free run big
enough would have to come out of `fg_art_pool`, whose ceiling is `POOL_TILE_CEILING` and
moving it moves RAM. **Streamed, exactly as S3K streams it.**

The map as read (`games/sonic4/vram.toml` -> `docs/generated/vram-map-sonic4.md`), with
this parcel's row in bold:

| tiles | name | kind | owner |
|---|---|---|---|
| 0-895 | fg_art_pool | arena | engine.level.page_cache |
| 896-911 | dust_puff | window | games.sonic4.dust_puff |
| 912-923 | dust_spindash | window | games.sonic4.dust_spindash |
| 924-927 | ring_sparkle | window | games.sonic4.ring_sparkle |
| **928-956** | **insta_shield (29)** | **window** | **games.sonic4.insta_shield** |
| 957-959 | FREE (3) | | the carve remainder |
| 960-991 | character_window | window | games.sonic4.player |
| 992-999 | test_obj | window | games.sonic4.test_objects |
| 1000-1015 | ring_placeholder | window | engine.objects.rings |
| 1016-1019 | test_marker | window | games.sonic4.player_common |
| 1020-1023 | FREE (4) | | |
| 1024-1471 | bg_region | arena | engine.bg |
| 1472-1491 | sprite_table | table | |
| 1492-1500 | tails_appendage | window | |
| 1501-1503 | FREE (3) | | |
| 1504-1531 | hscroll_table | table | |
| 1532-1535 | FREE (4) | | |
| 1536-2047 | plane_a / plane_b / window | plane | |

Declared with `const = "VRAM_INSTA_SHIELD"`; `tools/gen_vram_map.py` regenerates the
constants block, the Python mirror and the map doc, and `tools/test_gen_vram_map.py`
fails the build if any of the three drift. The 29 is not hand-typed into the wall check:
`ensure(VRAM_INSTA_SHIELD + dplc_peak_tiles(_dplc_insta) <= VRAM_TEST_SONIC)` reads the
peak out of the blob and the wall out of its owner.

**`Perform_DPLC_Deferrable`, not `Perform_DPLC`.** Sonic's own DPLC already peaks at 12
reachable entries against `DMA_IMPORTANT_SLOTS = 12` — `collision_data.emp:35-62` calls
that debt out as a ratchet — so a second Important-queue producer on the player's frames
is not available. Deferrable is documented for exactly this ("non-player objects,
budget-gated, can slip one frame"), and a dropped enqueue leaves `prev_frame` stale so
the next frame retries: the worst case is one frame of stale art on a 15-frame cosmetic.

### 2.6a Module structure — ONE section, and the reachability rule that forced it

The parcel started as two modules (`player/player_instashield.emp` for the ability,
`objects/insta_shield.emp` for the flash). It ships as ONE, at
`games/sonic4/player/player_instashield.emp`, section `player_instashield`, head label
`Ability_InstaShield`, one `order` row after `Climb_WallDist`.

**Why.** `player_fly` and `player_glide` are listed explicitly in sigil's module
registry (`crates/sigil-harness/src/native.rs`), which this parcel may not edit. An
unregistered module reaches the build ONLY through a `use` edge from an already
reachable one (the ring-sparkle route: `ojz_scroll_test` imports its art). Measured
here: with an `order` row but no `use` edge, both modules were absent from the manifest
entirely — `SIGIL_WARNINGS=full` did not even list them as unreachable — and the link
failed with `unresolved symbol Ability_InstaShield`.

The edge has to be REAL, not a token import, and it has to avoid a cycle:
`player_common` cannot import from the ability module because the ability module
imports `PlayerV` from it. The honest edge is **`sonic.emp`** — the record that binds
the hook — importing `INSTASHIELD_ABILITY_WH`, the ability's own statement that it
needs no ability collision box, exactly as `CharDef_Knuckles` reads
`KNUX_ABILITY_RADIUS`. That also puts the §2.4 ruling next to the field someone would
otherwise be tempted to fill in.

One edge admits one module, and the ability and the flash are one feature sharing one
state machine anyway (the hook opens the window, the flash closes it), so splitting
them would have bought a `use` line between twelve instructions and their visual. The
ring sparkle's header already records the principle: the self-contained file is the
honest unit.

### 2.6b The attacking predicate is a comparison, not a routine

The brief asked for the suppression check to be a single named predicate; it is
(`instashield_suppressed`, a module-private splice — module-private because a comptime
fn's free names resolve at the call site, EMP_PITFALLS §2, and both `PlayerV` and the
mask are `use`-imported).

"Is the player attacking?" deliberately did NOT become a second routine. It is one
comparison — `cmpi.b #INSTASHIELD_ATTACKING, PlayerV.instashield(<player>)` — and
wrapping a compare in a `jsr` to give it a name would cost more than it explains. What
it got instead is the name in prose, stated at `INSTASHIELD_READY` in
`config/constants.emp` as the single question the damage system will ask. Its one
reader today is the flash's own end-of-attack write, which is S3K's reader.

### 2.7 SFX — **BLOCKED**

`sfx_InstaAttack` is S3K SFX `$42`. Aeon's SFX bank
(`games/sonic4/data/sound/sfx/sfx_bank.emp`) holds **11** transcoded effects
(`$33 $34 $35 $36 $3C $62 $AB $B6 $B9`, plus `$BA $BB` in DEBUG) and `$42` is not among
them. Adding it means running `tools/sfx_transcode.py` against the S3K sound sources,
adding a `SfxTable` row, a `SFXID_*` id and a priority-ladder tier, and re-pinning the
sound blob's frozen goldens — a sound-lane parcel with its own ritual. Out of scope here;
booked with the exact recipe.

### 2.8 What this parcel does NOT do

- **No barrier shields** (S2 shield, fire, lightning, bubble) and no Super/Hyper. The
  press-frame branch tree S3K walks before reaching `Sonic_InstaShield` is represented
  by exactly one thing: the suppression predicate, which is *false* today because
  nothing writes `status_secondary`.
- **No damage system**, no enemy kills, no ring loss — and therefore no hitbox
  expansion (§2.4).
- **No SFX** (§2.7).
- No dropdash. No change to `player_air.emp`'s ability seam. No change to the
  `TailsAppendage` chain.

---

## 3. Gates

1. **Animation duration, derived, red-first.** A comptime fn walks a script's bytes and
   returns `frames * (duration + 1)`. It is run over BOTH our Aeon script and the
   embedded donor S3K script, and the `ensure` compares the two — no literal 14 anywhere.
   A second `ensure` pins our terminal frame index to the donor script's last frame byte
   (S3K's `cmpi.b #7`). Proven red by a poison module in the `emp_expect_fail` lane.
2. **Zero-piece <=> zero-entry correspondence, comptime.** Every mapping frame with 0
   pieces must have a 0-entry DPLC frame, and vice versa — this is what makes the one
   deviation from the donor blob a checked fact instead of a claim.
3. **Palette census, comptime.** Every nibble of the art in `{0, 6, 7, 8}`; a blob
   regenerated from skdisasm's donor (`{0,1,$C,$D}`) fails here by name.
4. **VRAM wall, comptime.** `VRAM_INSTA_SHIELD + dplc_peak_tiles(blob) <= VRAM_TEST_SONIC`,
   both sides read from their owners.
5. **Art provenance, pytest** (`tools/test_instashield_art.py`): re-derive from the
   donor, byte-compare the committed blobs; skip loudly by name without the donor.
6. **VRAM registry, pytest** (`tools/test_gen_vram_map.py`, already build-fatal).
7. **`tools/verify_sprites.py`** must still pass on the regenerated `PENDING_PAIRS` row.
8. **Replay fixtures — EMULATOR, tagged for the controller.** See §4.

## 4. Replay-fixture impact (measured statically, NOT re-recorded)

Decoding the two shipped streams and counting jump-button press edges:

| fixture | ticks | A/C press edges | B edges | verdict |
|---|---|---|---|---|
| `ojz_slide_fixture` | 2350 | **0** | 3 (debug-fly toggles) | **unaffected** — the ability seam can never fire |
| `ojz_fixture` | 1721 | **4** | 1 | **expect a re-stamp** |

`ojz_fixture`'s presses land at ticks 1137, 1237, 1248 and 1459. **1237 and 1248 are 11
ticks apart** — far shorter than a jump — so the second is almost certainly an airborne
press, which now fires the insta-shield: `PlayerV.instashield` becomes non-zero (the
custom window is hashed), an Effect slot is occupied for 15 ticks (the free-stack
occupancy is hashed), and if that jump was a roll-jump the state byte changes too.

**This is the intended state change, not a desync.** The fixture needs re-stamping in the
emulator, and this parcel deliberately does not re-record it.

## 5. Booking

- `docs/DEFERRED_WORK.md` "Dropdash, instashield — Sonic move-kit extensions": instashield
  struck, dropdash left, with the three riders below.
- The **hitbox expansion** booked against the damage system with §1.5's arithmetic, and
  cross-referenced from the get-up/damage entry (which already says *"fold it into the
  shields/damage work"*).
- The **SFX** (`$42`) booked with §2.7's recipe.
- The **one-frame roll-jump-cancel deviation** and the **`AF_CALLBACK` follow-up** booked.
- `docs/ENGINE_ARCHITECTURE.md` §5: the ability seam's description gains Sonic's row.
