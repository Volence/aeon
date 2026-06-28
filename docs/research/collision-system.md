# Collision System Research

Research across 7 reference disassemblies and online sources for collision detection,
response dispatch, solid object interactions, sprite overflow handling, and controller
input. All findings are raw research — no engine code produced.

---

## 1. sonic_hack (Sonic 2 mod)

**Source:** `sonic_hack/code/objects/Object_Specific_Routines/object_touch_response.asm`

### Collision Detection Algorithm

Center-center AABB using doubled-delta math. The overlap test works entirely in
"doubled space" to avoid a division or shift. For each axis:

```
combined_width = obj_full_w + char_full_w
distance = |obj_center - char_center|
overlap = combined_width - 2*distance
if overlap <= 0: no collision on this axis
```

All arithmetic is integer, using `ext.w` on byte-sized width/height. The 2x
multiply is a single `add.w d3,d3`. No actual multiply instruction (`mulu`/`muls`)
is used anywhere in the collision code.

Cost per pair: approximately 30-40 cycles for early-exit (X miss), 60-80 for full
overlap + axis detection. Extremely cheap.

### Collision Iteration Pattern

**Player-vs-all linear scan.** `TouchResponse` takes a0 = player character and
iterates the entire `Dynamic_Object_RAM` range (40 slots) using `dbf`. Each object
is checked in sequence:

1. `tst.b collision_response(a1)` — skip objects with no collision type (fast reject)
2. X overlap check (width)
3. Y overlap check (height)
4. If overlapping, dispatch to type handler via jump table

Before the object loop, `Touch_Rings` is called separately for ring collision (rings
use a separate data format, not the object table).

The loop also includes a **fall-off safety check** after the scan: if the player is
flagged as standing on an object (`bit 3 of status`), it verifies the interact_obj
is still alive and the player is still within X bounds. This catches the edge case
where the player walks off a moving platform outside the AABB detection range.

### Collision Response Dispatch

**Type byte + jump table.** `collision_response(a1)` is a pure type byte (0-12).
The handler dispatches via `jsr TouchResponse__ResponseTypeTable(pc, d1.w)` using
a table of `bra.w` instructions:

| Type | Constant | Handler |
|------|----------|---------|
| 0 | CT_NONE | Touch_Enemy (fallback) |
| 1 | CT_ENEMY | Touch_Enemy |
| 2 | CT_BOSS | Touch_Boss |
| 3 | CT_HURT | Touch_ChkHurt |
| 4 | CT_MONITOR | Touch_Monitor |
| 5 | CT_RING | Touch_Ring |
| 6 | CT_BUBBLE | Touch_Bubble |
| 7 | CT_PROJECTILE | Touch_Projectile |
| 8 | CT_SOLID | Touch_Solid |
| 9 | CT_BREAKABLE | Touch_SolidBreakable |
| 10 | CT_SPRING | Touch_Spring |
| 11 | CT_SOLIDHURT | Touch_SolidHurt |
| 12 | CT_TOUCH | Touch_Touch |

Bounds checking: types > CT_TOUCH are rejected. Loop state (d6/a1) is saved on the
stack before the handler call and restored after.

Dimensions come directly from `width_pixels` and `height_pixels` in the SST —
no lookup table. This is a departure from S.C.E./S3K which pack size into the
collision byte.

### Solid Object Interactions

**Shared `Solid_Detect_AABB` subroutine.** Called by Touch_Solid, Touch_Spring,
and Touch_SolidHurt via `bsr`. Returns overlap data and axis determination in
registers, or discards the caller's return address and returns directly to the
dispatcher if no overlap.

**Side detection:** After computing X and Y penetration (both in doubled space),
the routine compares `|rel_x|` vs `|rel_y|`. The condition codes directly encode
the axis:
- `bhs/bcc` = side axis (|rel_x| >= |rel_y|) = push horizontally
- `blo/bcs` = vertical axis (|rel_x| < |rel_y|) = land or head-bump

This is minimum-penetration-axis detection: push out on the axis with the SMALLER
penetration. Very robust for AABB-on-AABB.

**Side collision (Touch_Solid_Side):**
- Convert doubled-space penetration to real pixels (`lsr #1`)
- Push character left or right by penetration amount
- Zero x_vel and inertia
- If on ground: set pushing flag on both character and object

**Landing (Touch_Solid_Land):**
- Exit ball form (changes height)
- Snap Y: `char_y = obj_y - (obj_h + char_h) / 2`
- Zero y_vel, set on-object/not-in-air flags
- Store interact_obj = a1 (which object the player is standing on)
- Set object's standing-status bit (bit 3 for P1, bit 4 for P2)

**Head bump (Touch_Solid_HeadBump):**
- Only if y_vel < 0 (rising)
- Snap Y below: `char_y = obj_y + (obj_h + char_h) / 2 + 1`
- Zero y_vel

**On-object fast path (Touch_Solid_OnObject):**
- If character already standing on THIS object, skip detection entirely
- Check X bounds — if past edge, force fall-off
- Otherwise, reposition Y to stay on top

**Moving platform support:** Not explicit in the collision code. The object itself
moves its own x_pos/y_pos, and the on-object fast path repositions the character
every frame. Character velocity is NOT transferred from the platform — the Y snap
handles vertical tracking, but horizontal inertia transfer would need to be handled
by the platform object.

### Spring Collision

Complex but well-structured. Touch_Spring reads orientation from subtype bits 3-5:
- 0 = up, 2 = side, 4 = down, 6 = diagonal up, 8 = diagonal down

The spring first checks if the character is already standing on it (on-object fast
path). Otherwise, it calls `Solid_Detect_AABB` and routes based on axis:
- Vertical axis + char above = potential up bounce or landing
- Vertical axis + char below = potential down bounce or head bump
- Side axis = potential side bounce or push

The bounce force comes from a custom SST field `Spring__BounceForce(a1)`.

---

## 2. S.C.E. (Sonic Clean Engine — S3K-based)

**Source:** `Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Touch Response.asm`,
`Engine/Objects/Solid Object.asm`

### Collision Detection Algorithm

Edge-based AABB. S.C.E. uses a fundamentally different AABB formulation from
sonic_hack. Instead of center-center with doubled deltas, it uses:

```
left_edge = obj_x - half_width
right_edge = obj_x + half_width
player_left = player_x
player_right = player_x + player_width
overlap = (player_right > left_edge) AND (player_left < right_edge)
```

The implementation computes `obj_x - half_width - player_left_edge` and then checks
two conditions using unsigned branch (`bhs`/`blo`). Width and height come from a
lookup table (`Touch_Sizes`) indexed by the low 6 bits of `collision_flags`.

### Collision Iteration Pattern

**Registration list, not linear scan.** S.C.E. maintains a `Collision_response_list`
in RAM ($FFB830, 128 bytes). During each object's update, objects that want to be
collidable call `Add_SpriteToCollisionResponseList`, which appends the object's RAM
address (as a word) to the list and increments the count.

`TouchResponse` then iterates only the registered objects:
```asm
lea  (Collision_response_list).w, a4
move.w (a4)+, d6          ; count (word count, not object count)
beq.s  Touch_Return       ; if zero, skip
Touch_Loop:
movea.w (a4)+, a1          ; load registered object address
; ... overlap check ...
subq.w #2, d6
bne.s  Touch_Loop
```

This means only objects that explicitly opt in to collision are checked. Invisible
or off-screen objects that skip `Draw_Sprite` never register, so they never cost
collision cycles.

**Advantage:** Fewer iterations per frame when many objects are dormant or off-screen.
**Disadvantage:** Registration adds a small per-object cost during the render path,
and the list has a fixed max size (64 entries).

### Collision Response Dispatch

**Packed type + size in one byte.** `collision_flags` ($28 in S.C.E.'s SST) encodes:
- Bits 7-6: type (00=touch/enemy, 01=item, 10=hurt, 11=special)
- Bits 5-0: size index (lookup into Touch_Sizes table)

The dispatch first checks type bits, then for type 01 (item), checks the size index
to determine if it is a ring ($47) or monitor ($46).

`Touch_Sizes` is a table of 57 (width, height) byte pairs, indexed 0-$38. Each pair
stores half-dimensions. This is a shared global table — all objects of a given "size
class" share the same hitbox dimensions.

### Solid Object Interactions

S.C.E.'s `SolidObject` family is **completely separate** from `TouchResponse`. Objects
call `SolidObjectFull` / `SolidObjectTop` / `SolidObjectFullSloped` etc. from their
own update routines, passing width/height as register arguments.

The solid detection uses an edge-relative coordinate system where the origin is the
object's left edge. The standing check is distance-from-top based.

**Side detection:** S.C.E. computes separate penetration on X and Y axes, then
compares the absolute values (`cmp.w d1, d5`). If horizontal distance > vertical
distance, the player goes to the top/bottom branch. Otherwise, the left/right branch.
This inverted from sonic_hack's logic — S.C.E. treats the LARGER penetration axis
differently.

The side collision sets pushing flags, the top collision calls `RideObject_SetRide`
(which stores the interact pointer and clears airborne flags), and the bottom
collision pushes the player below and zeroes y_vel.

**Sloped variants:** S.C.E. has full sloped platform support via height tables passed
in a2. `SolidObjSloped2` uses the player's X offset within the platform to look up
a Y height byte from the table, creating per-pixel slope detection. This is an
entire system sonic_hack doesn't have (its slopes are all terrain-based, not
object-based).

**Key S.C.E. architectural issue:** The solid object system runs during the object's
own update loop (caller provides dimensions), while the touch response system runs
centrally. This creates a design split where solid and non-solid collision follow
completely different code paths and calling conventions.

### Shield Touch Response

S.C.E. adds a separate `ShieldTouchResponse` pass that runs before the main
TouchResponse. It uses an expanded hitbox (96x96 pixels for the shield area) and
only processes harmful objects (type bits = $80). If a match is found and the object
has the `shield_reaction.all_shields` flag, the projectile is deflected using
`GetArcTan` + `GetSineCosine` for directional bounce.

---

## 3. Batman & Robin

**Source:** `The Adventures of Batman and Robin/disasm/OBJECT_SYSTEM.md`

### Collision Detection

Batman & Robin's object system document identifies a `collision_word` field at
offset $2E in the 90-byte SST. The object system uses a doubly-linked active list
(not a flat array), which means collision checking would iterate the linked list
rather than scanning fixed stride slots.

The game's bytecode interpreter (Level 2 action scripts) handles collision detection
as an opcode within the script system. This means collision is data-driven —
collision behaviors are defined in script bytecode, not hardcoded 68K routines.

No explicit AABB code was found in the available analysis, but the architecture
implies software-managed bounding box checks since the game needs fine control over
multi-layered effects-heavy scenes.

### Solid Object Interactions

Not analyzed in available documentation. The bytecode interpreter likely handles
solid interactions through script opcodes that test positions and apply corrections.

### Sprite Overflow

No documented overflow handling. Batman & Robin's scenes are heavily effects-driven
(VDP shadow table, raster effects) but typically have fewer discrete sprite objects
than a Sonic game.

---

## 4. Vectorman

**Source:** `The Adventures of Batman and Robin/vectorman_disasm/ANALYSIS.md`

### Collision Detection

Vectorman's 12-byte dispatch entries don't include collision data — each object type
handles its own collision internally via dedicated routines. The player data block
at $FFFFAF68 is over 1500 bytes, likely including collision state.

The game uses separated update/render calls per object. Collision would occur during
the update phase. The terminator-based object list ($FFFF = end) means the collision
loop naturally skips unused slots.

### Specific Techniques

No detailed collision algorithm was extractable from the raw disassembly, as it uses
a single-file format without labels. The ANALYSIS.md focuses on the DMA pipeline
and object dispatch architecture rather than collision.

### Sprite Overflow

Not explicitly documented. Vectorman's 3D-rendered sprites tend to be large (few
sprites, many tiles each) rather than many small sprites, so per-scanline limits are
less of a concern.

---

## 5. Gunstar Heroes

**Source:** `The Adventures of Batman and Robin/gunstar_disasm/ANALYSIS.md`,
raw disasm analysis

### Collision Detection

Gunstar uses 96-byte ($60 stride) SST entries. The $58 offset serves as a **link
pointer** used for both code callbacks and object-to-object references. The raw
disassembly shows extensive use of `$58(a5)` for boss coordination:

```asm
; Boss reads parent position via link:
movea.w $58(a5), a0         ; follow link to connected object
move.w  $10(a0), d0         ; read parent's X position
```

With 52 writes and 19 reads to the $58 field in Gunstar, the link system is central
to how multi-part bosses communicate. Boss hits are detected through what appears to
be a `boss_hitcount` mechanism where collisions decrement a counter.

### Collision Iteration

Likely player-vs-all or registration-based, but the raw disassembly doesn't have
labeled collision routines. The 96-byte stride loops (`lea $60(a5), a5; dbf d7, loop`)
process objects sequentially.

### Response Dispatch

Index-based jump table at offset $04:
```asm
move.w  $4(a5), d0          ; routine index
lea     JumpTable(pc, d0.w), a0
jmp     (a0)
```

This is state dispatch, not collision dispatch. Collision response appears to be
embedded within each object's state handler rather than centralized.

---

## 6. Alien Soldier

**Source:** `The Adventures of Batman and Robin/aliensoldier_disasm/` (symlink to
Gunstar ANALYSIS.md), raw disasm

### Collision Detection

Same 96-byte SST as Gunstar but with an additional link field at $5C (104 references
vs Gunstar's 0). This enables chains like:
```
Body ($58 -> Head, $5C -> LeftArm)
  +-- Head ($58 -> Body)
  +-- LeftArm ($58 -> Body, $5C -> RightArm)
  +-- RightArm ($58 -> Body)
```

### Two-Stage Dispatch

Alien Soldier uses a **two-stage object dispatch**: first by type flags ($02), then
by routine index via a longword table. Simple objects skip the full dispatch. This
reduces overhead for objects that only need basic processing (projectiles, particles).

### Key Technique: Display List Pre-Building

Alien Soldier pre-builds VDP command sequences at fixed RAM addresses during the main
loop. VBlank just writes the pre-built command blocks to VDP ports — zero computation
at interrupt time. This is relevant because it means collision checking happens
during the main loop with plenty of CPU time, not under VBlank pressure.

---

## 7. Thunder Force IV

**Source:** `The Adventures of Batman and Robin/thunderforce4_disasm/ANALYSIS.md`

### Collision Detection

TF4 uses **type-segregated object pools** with 32-byte stride ($20):
- Bullet pool 1: $FFFF9000 (1 KB)
- Bullet pool 2: $FFFF9400 (1 KB)
- Enemy pool 1: $FFFFD000 (1 KB)
- Enemy pool 2: $FFFFD400 (1 KB)

Confirmed by 437 instances of `lsl.w #5` (multiply by 32) for index calculations.

This segregation means collision checking can be targeted: player bullets check
against the enemy pool, enemy bullets check against the player. No wasted iterations
checking bullet-vs-bullet or enemy-vs-enemy.

### Bullet Fast Path

The bullet processing loop is minimal:
```asm
; Conceptual bullet inner loop:
lea     $9000.w, a0         ; bullet pool
moveq   #31, d7             ; 32 bullets max
.bullet_loop:
    tst.w   (a0)            ; active?
    beq.b   .next
    move.w  $1E(a0), d0     ; load velocity
    add.w   d0, $10(a0)     ; integrate position
    ; bounds check, sprite write
.next:
    adda.w  #$20, a0        ; stride = 32
    dbra    d7, .bullet_loop
```

No AI, no animation state, no collision response — just velocity integration, bounds
check, and sprite entry write. The tight loop means 32 bullets cost roughly the same
as 5-6 full-featured objects.

### Sprite Overflow Handling

**Round-robin rotation.** With 80+ objects competing for 80 VDP sprite slots:
- Priority nibbles in sprite attributes control draw order
- `add.w $F29A.w` rotates which sprites get priority each frame
- Lower-priority sprites flicker in/out across 4-frame windows
- All objects remain visible — none permanently hidden

This is the most directly applicable overflow solution found across all references.

---

## 8. Online Sources

### plutiedev.com — Controller Protocol

**3-button reading** requires two TH toggles:
1. Write $40 to data port (TH=1), read: `--CBRLDU`
2. Write $00 to data port (TH=0), read: `--SA00DU`
3. Combine into `SACBRLDU` byte, invert (1=pressed)

**6-button reading** requires seven TH toggles:
1. Cycles 1-2: standard 3-button data (same as above)
2. Cycles 3-5: compatibility padding (ignore values)
3. Cycle 6 (TH=0): detection — bits 3-0 = `0000` means 6-button controller
4. Cycle 7 (TH=1): extra buttons — `--CBMdXYZ` (Mode, X, Y, Z)

**Critical rules:**
- Read controllers ONCE per frame only. 6-button controllers use timing-based
  backward compatibility. Reading more than once per frame breaks them.
- Do not require Mode button at startup (that is how 6-button controllers enter
  3-button compatibility mode).
- 4 NOPs minimum between TH toggle and read (bus synchronization).
- Port addresses: Data1=$A10003, Data2=$A10005, Ctrl1=$A10009, Ctrl2=$A1000B.
- Write $40 to both control AND data ports during initialization.

**Detection:** After cycle 6, check if bits 3-0 are all zero. If yes, a 6-button
controller is connected and cycle 7 data is valid. If not (3-button or no controller),
skip the extra button read.

**Press/hold detection (standard technique):**
```asm
move.b  (Held), d1      ; previous held state
move.b  d0, (Held)      ; store new held state
eor.b   d0, d1          ; toggle changed bits
and.b   d0, d1          ; mask to newly-pressed only
move.b  d1, (Press)     ; store pressed
```

### huguesjohnson.com — Genesis Collision Tutorial

The tutorial covers grid-based collision for tiles (not object-vs-object AABB).
Uses `btst` on collision map bits. Not directly applicable to the object collision
system but demonstrates the Genesis community's preference for bit-test approaches
over arithmetic overlap tests.

### SpritesMind Forum — Collision Discussion

Key insight from the forum: collision data should live in ROM, not RAM. Large
collision maps ($A0 x $500 = 160x1280 tiles) fit in ROM and are accessed directly.
This aligns with aeon's per-section collision map design.

### VDP Sprite Link System

The Genesis VDP processes sprites via a linked list in the Sprite Attribute Table:
- 8 bytes per sprite entry: Y, size/link, tile/flags, X
- Link field (byte in entry[3]) points to next sprite to process
- VDP follows links starting from sprite 0, up to 80 sprites max
- Per-scanline: max 20 sprites (H40 mode) or 16 sprites (H32)
- When limit hit: remaining sprites on that scanline are silently dropped
- Link value 0 terminates the chain (sprite 0 is always processed first)
- Sprite at X=0 causes remaining sprites on that scanline to be masked

**Overflow management:** The standard technique is to rotate the link chain start
point each frame. This distributes dropout as even flicker rather than permanently
hiding the same sprites. TF4 uses a 4-frame rotation window.

### SGDK / Homebrew

SGDK's sprite engine includes collision fields in its sprite structure but they are
marked "not yet used." The VDP's hardware collision flag (`VDP_SPRCOLLISION_FLAG`)
only indicates that SOME sprites overlapped somewhere — it does not identify which
sprites. All serious collision detection is software-based.

---

## 9. Synthesis and Recommendations

### 9.1 AABB Math Formula

**Recommendation: Center-center doubled-delta (from sonic_hack).**

sonic_hack's formulation is superior to S.C.E.'s edge-based approach for several
reasons:
- Full-width values from the SST are used directly — no division by 2 needed
- The "doubled space" trick (`add.w d3, d3`) replaces what would otherwise be
  a shift or division to get half-widths
- All arithmetic is adds, subtracts, and compares — zero multiplies
- The penetration depth is a natural byproduct of the overlap test, available for
  push-out calculation without additional work

Formula per axis:
```
combined = obj_full_width + char_full_width
rel = obj_center - char_center   (signed)
abs_rel = |rel|
doubled_dist = abs_rel * 2       (add.w d, d)
penetration = combined - doubled_dist
if penetration <= 0: no overlap
```

Axis determination for solid objects:
```
compare |rel_x| vs |rel_y|
if |rel_x| >= |rel_y|: side axis (push horizontally)
if |rel_x| < |rel_y|: vertical axis (land or head-bump)
```

This minimum-penetration-axis approach is standard in modern physics engines and
works perfectly for axis-aligned boxes.

### 9.2 Iteration Pattern

**Recommendation: Player-vs-all linear scan with fast rejection.**

Registration lists (S.C.E.) add complexity without sufficient benefit for a Sonic
game:
- The collision list must be populated each frame by every object
- The list has a fixed max size that can overflow
- The per-object registration call adds overhead to the render path
- In a Sonic level, most on-screen objects DO need collision

The linear scan approach (sonic_hack) is simpler and has excellent average-case
performance:
- `tst.b collision_response(a1)` rejects empty/non-collidable slots in 8 cycles
- With 40 dynamic slots and typically 15-25 active objects, the scan touches
  ~40 bytes total for the empty slots (just the tst.b) and does full AABB math
  on ~20 objects
- Worst case: 40 active collidable objects x ~80 cycles = ~3200 cycles per player
- With 2 players: ~6400 cycles total = ~0.5% of a frame

Type-segregated pools (TF4) are overkill for a Sonic game. Sonic's object variety
(badniks, springs, platforms, monitors, rings — all in the same space) doesn't
benefit from the rigid pool segregation that helps a shmup's bullet patterns.

### 9.3 Collision Response Dispatch

**Recommendation: Type byte + jump table (from sonic_hack, already designed).**

The existing aeon design with `collision_resp` as a pure type byte and a
jump table of handlers is the cleanest approach found across all references:
- S.C.E. packs type + size into one byte, requiring bit masking and a size lookup
  table. Our approach stores dimensions directly in the SST — no table needed.
- Gunstar/Alien Soldier embed collision response in per-object state handlers,
  making it hard to change collision behavior without rewriting the object.
- Batman uses script bytecode — powerful but too heavyweight for a platformer.

The 13-type table (NONE through TOUCH) covers all Sonic gameplay needs. New types
are trivially added: define a constant, add a `bra.w` entry, write the handler.

### 9.4 Solid Side Detection

**Recommendation: Minimum-penetration-axis with `Solid_Detect_AABB` subroutine
(from sonic_hack, already proven).**

The sonic_hack `Solid_Detect_AABB` pattern is elegant:
1. Compute overlap on both axes as a byproduct of the AABB test
2. Determine which axis has smaller overlap via `cmp |rel_y|, |rel_x|`
3. Return axis in condition codes (bhs = side, blo = vertical)
4. If no overlap, discard caller's return address and return to dispatcher

The return-address discard trick (`addq.l #4, sp; rts`) is a smart optimization
that eliminates a branch in the no-collision case for all solid-type handlers.

**Standing detection:** Character above object center (`rel_y < 0`) + falling
(`y_vel >= 0`) = landing. Snap Y to `obj_y - (obj_h + char_h) / 2`. Store
interact_obj and set on-object status bits.

**On-object tracking:** Once standing, skip full AABB detection. Check X bounds
only (for fall-off). Reposition Y every frame. This is the fast path that makes
moving platforms work.

### 9.5 Controller Protocol

**Recommendation: Extend existing 3-button code to support 6-button with detection.**

The existing `engine/controllers.asm` implements correct 3-button reading. Changes
needed for 6-button support:

1. **Detection:** At init (or first VBlank), perform the 7-cycle TH toggle sequence.
   After cycle 6, check if data bits 3-0 are all zero. Store result in a
   `Controller_Type` byte (0 = 3-button, 1 = 6-button).

2. **Reading:** If 6-button detected, extend the read sequence to 7 cycles. Store
   X/Y/Z/Mode in a separate `Ctrl_1_Held_6` / `Ctrl_1_Press_6` byte pair.

3. **Timing safety:** Read controllers exactly once per frame, in VBlank. Never
   re-read. The existing VBlank placement is correct.

4. **Compatibility:** The 7-cycle sequence is backward compatible with 3-button
   controllers — cycles 3-7 are simply ignored. But detection should still be done
   to avoid interpreting garbage as button presses.

5. **Mode button warning:** Some clone systems hardwire Mode=pressed. Do not use
   Mode for critical gameplay functions. X/Y/Z are safe for secondary controls.

### 9.6 Sprite Overflow Handling

**Recommendation: Link-order cycling (from TF4, already designed in
ENGINE_ARCHITECTURE.md section 3.5).**

The existing architecture document already specifies the approach:
- Rotate the sprite link chain start point each frame
- Use a 4-frame window so every sprite gets at least one visible frame
- Cost: one `addq` + `andi` per frame

Additional techniques to layer on top:
- **Scanline-aware budgeting** (already designed): During `Render_Sprites`, maintain
  per-scanline sprite counts. Skip or simplify sprites that would exceed 20.
- **Sprite X=0 masking** (already designed): Hardware clipping for free.
- **Sprite multiplexing** (already designed): For weather/particle effects only.

The TF4 round-robin approach is confirmed as the production-standard technique.
No other reference does anything more sophisticated — it simply works.

### 9.7 Key Differences from S.C.E. to Preserve

The aeon's collision design diverges from S.C.E. in three deliberate ways that
should NOT be reverted:

1. **No size table.** S.C.E.'s `Touch_Sizes` table (57 entries of byte pairs) forces
   all objects of a given "size class" to share identical hitbox dimensions. Our
   approach stores width/height directly in the SST, so every object can have unique
   collision dimensions. This is strictly more flexible.

2. **Unified collision path.** S.C.E. splits touch response (central dispatcher) from
   solid objects (per-object callee). Our approach runs BOTH through the central
   `TouchResponse` loop via collision_resp types. Solid objects are just type 8-12.
   This eliminates the architectural split and its associated bugs (e.g., S.C.E.'s
   known issue where SolidObject routines aren't properly integrated with touch
   response).

3. **No registration list.** S.C.E.'s `Collision_response_list` adds per-object
   overhead and a fixed-size limit. Our linear scan with fast rejection is simpler,
   has no overflow risk, and costs approximately the same cycles in practice.

### 9.8 Open Questions for Implementation

1. **Terrain collision (distinct from object collision):** Per-section collision maps
   are specified in ENGINE_ARCHITECTURE.md (flat byte array, 128-column shift-based
   lookup). This research focused on object-vs-object — terrain collision is a
   separate system with its own angle detection, sensor lines, and slope handling.

2. **Sloped solid objects:** S.C.E. supports per-pixel sloped platforms via height
   tables. Do we need this? Diagonal springs and sloped moving platforms may require
   it. If so, the height table approach (pass a2 = ROM slope data) is well-proven.

3. **Boss hit communication:** Gunstar/Alien Soldier use link fields for multi-part
   boss coordination. The SST already has `parent_ptr` and `sibling_ptr`. Boss hit
   handling should route through the parent — children forward hits via the link.

4. **Insta-shield expansion:** S.C.E. expands the player's hitbox temporarily during
   insta-shield (96x96 vs normal 32x38). This needs a mechanism to override
   width_pixels/height_pixels for the duration of the attack.

5. **Shield deflection:** S.C.E. uses `GetArcTan` + `GetSineCosine` to compute
   bounce direction when a shield deflects a projectile. This is expensive
   (~200 cycles for arctan + sine lookup) but only fires on contact. Worth keeping
   for the visual quality.

---

## References

### Disassembly Sources
- sonic_hack: `code/objects/Object_Specific_Routines/object_touch_response.asm`
- S.C.E.: `Engine/Objects/Touch Response.asm`, `Engine/Objects/Solid Object.asm`, `Engine/Core/Controllers.asm`
- Batman & Robin: `disasm/OBJECT_SYSTEM.md`
- Vectorman: `vectorman_disasm/ANALYSIS.md`
- Gunstar Heroes: `gunstar_disasm/ANALYSIS.md`
- Alien Soldier: `aliensoldier_disasm/` (shared analysis with Gunstar)
- Thunder Force IV: `thunderforce4_disasm/ANALYSIS.md`

### Online Sources
- [Plutiedev — Controllers](https://www.plutiedev.com/controllers)
- [Hugues Johnson — Genesis Collision Detection](https://huguesjohnson.com/programming/genesis/collision-detection/)
- [Hugues Johnson — 6-Button Controllers](https://huguesjohnson.com/programming/genesis/6button/)
- [Hugues Johnson — Sprite Link List](https://huguesjohnson.com/programming/genesis/spritelist/)
- [SpritesMind — Collision Discussion](https://gendev.spritesmind.net/forum/viewtopic.php?t=3274)
- [SpritesMind — Sprite Limit Discussion](https://gendev.spritesmind.net/forum/viewtopic.php?t=1192)
- [Raspberryfield — 6-Button Protocol](https://www.raspberryfield.life/2019/03/25/sega-mega-drive-genesis-6-button-xyz-controller/)
- [GitHub — LUMINARY Engine](https://github.com/BigEvilCorporation/LUMINARY)
- [MegaCat Studios — VDP Graphics Guide](https://megacatstudios.com/blogs/retro-development/sega-genesis-mega-drive-vdp-graphics-guide-v1-2a-03-14-17)
- [Copetti — Mega Drive Architecture](https://www.copetti.org/writings/consoles/mega-drive-genesis/)
