# Moving background bands — the anchor mover (EFFECTS-W1 DoD item 4)

*Design pass, 2026-09-02. Branch `design/moving-bands`. **Nothing is built and no engine byte
moves.** This document is specific enough to implement from and priced enough to sequence.
Where it is uncertain it says so; every number it quotes is re-derived from an artifact in this
tree at `73b07a4f` and the derivation is shown.*

**The item, verbatim** (`empyrean/docs/superpowers/specs/2026-08-29-effects-definition-of-done.md`
line 23): *"**Moving raster bands**: the moving-top step (P2b), plus the **time-driven anchor
mover** so a band's edges move over time while the player stands still (the owner's addition; a
gap in every prior plan). P3 (both edges moving) only if the owner asks."* Aeon's own pricing line
(`:59`) reads *"4 L, needs a design pass (the anchor mover is new)"*, and `:63` — *"Aeon reads item
4 as motion, not colour."*

---

## 0. The one-paragraph answer

**The mechanism that moves a band edge already ships; what is missing is the thing that moves.**
`Effects_World_Y[4]` is a RAM bank of world-space boundary anchors, and all three consumers that
can place a horizontal edge — the raster schedule builder, the parallax band split, and the
off-screen palette ship — already read a single per-frame derivation of it. Nothing advances it
except a DEBUG chord. This design adds **two motion terms evaluated inside that one derivation**:
**SWEEP**, a stateless periodic offset read from the sine table against `Logic_Tick` (the shape
item 7's vertical bob shipped six days ago, applied per channel instead of per scene), and
**APPROACH**, a rate-gated one-pixel ramp of the anchor toward a target (S.C.E./stock-S2's waterline
with its unclamped overshoot made arithmetically unreachable, at Ristar's sub-pixel rates and by
Ristar's zero-RAM mechanism for getting them). Neither needs a fixed-point accumulator, neither
touches the band records, and neither is a second spelling of `SceneDrift` —
drift moves a band's *contents horizontally*, this moves a band's *edge vertically*, and the two
are different axes of different quantities that never meet. The cost is **+12 cycles/frame with
nothing authored** and **~+236 with one channel sweeping**, charged against the axis-1 *reservation*
rather than its budget. The blocker is not engineering: **it cannot be authored today.** No editor
document has a field for a channel's world Y, let alone its motion, and adding one is an empyrean
schema amendment — the same wall item 3 hit.

---

## 1. What already exists, measured

This section is first because the item's size (L) was priced before anyone looked, and most of it
is already built. Every claim here is read from source or from `s4.debug.lst` / `s4.debug.bin` at
`73b07a4f`, not from a plan document.

### 1.1 The anchor bank and its single derivation

| symbol | address | size | authority |
|---|---|---|---|
| `Effects_World_Y` | `$FFFF8BEE` | `[u16; 4]`, 8 B | `s4.debug.lst:2513` |
| `Effects_Screen_L` | `$FFFF8BF6` | `[u16; 4]`, 8 B | `s4.debug.lst:2514` |

`engine/ram.emp:466-472` states the design intent in its own words, and it is worth quoting because
it *pre-authorises this item*:

> They live in RAM, not in the preset's ROM array, because that is what makes them **MOVABLE**:
> rising lava, a flood line and a beat-driven pulse all rewrite an anchor at runtime through
> `Effects_SetWorldY`. The preset's inline array is the seed, not the storage.

`Effects_LatchWorldLines` (`engine/effects/raster.emp:1847`) is by ruling the **single** derivation
of `Effects_Screen_L`:

```
Effects_Screen_L[ch] = Effects_World_Y[ch] - Camera_Y        ; signed, unclamped
```

Read out of the ROM at `$8320`, not transcribed from source — 26 bytes, `4E75` terminated:

```
8320  32 38 a6 08   MOVE.W ($FFA608).W, D1     ; Camera_Y integer word
8324  41 f8 8b ee   LEA    ($FF8BEE).W, A0     ; Effects_World_Y
8328  43 f8 8b f6   LEA    ($FF8BF6).W, A1     ; Effects_Screen_L
832C  70 03         MOVEQ  #3, D0
832E  34 18         MOVE.W (A0)+, D2           ; .ch
8330  94 41         SUB.W  D1, D2
8332  32 c2         MOVE.W D2, (A1)+
8334  51 c8 ff f8   DBF    D0, .ch
8338  4e 75         RTS
```

Nominal MC68000: `12+8+8+4` header, `3 x 30 + 34` loop, `16` RTS = **172 cycles/frame, 26 bytes**.
(§7 states the calibration that number should be read with.)

**Its three readers, and they are exactly three** (grep for `Effects_Screen_L` across `engine/`):

| reader | site | when | what it places |
|---|---|---|---|
| `Raster_BuildSchedule` | `engine/effects/raster.emp:1669` | VBlank | a patchable fire's **scanline** |
| Step 4b anchored overlay | `engine/level/parallax.emp:1777` | main loop | the **line a parallax band is split at** |
| the off-screen frame-top ship | `engine/effects/preset.emp` / raster ship path | VBlank | the whole-screen state when the edge is above line 0 |

**The per-frame call site is GAME code, not engine code**: `GameState_OJZScroll_Update`
(`games/sonic4/test/ojz_scroll_test.emp:695`), between `Camera_Update` and `Parallax_Update`, and
that placement is already a ruling with its reasoning written at the call site. This matters to §4:
a mover folded into the latch needs **no new call site and no new ordering ruling**.

### 1.2 The three edges an anchor can already move

| tier | how the edge is placed | is it already movable at runtime? |
|---|---|---|
| **parallax band top** (`SceneLayer.ly_world_y`) | comptime → plane line → screen line by Step 4a's rebase against `Vscroll_BG` | **No.** It is a ROM constant. It moves on screen only when the camera moves. |
| **parallax band SPLIT** (`scene(anchor: ch)`) | Step 4b splits the containing band at `Effects_Screen_L[ch]` | **Yes.** One channel per scene (`pcfg_anchor_ch` is one byte). |
| **raster fire line** (`patchable(fires, ch, lo, hi)`) | `patch_table` → `Raster_BuildSchedule` re-derives from `Effects_Screen_L[ch]` each VBlank | **Yes**, within `[lo, hi]`. |

**So "the band's own top" is the one edge that structurally cannot move**, and this design does not
try to make it. That is a limit, stated in §9, not an omission — Step 4a's `.find_k`
(`engine/level/parallax.emp:1543`) requires band tops to *ascend*, and independently-moving tops
cross. Item 4's moving edges are the anchored split and the raster fires, which is what the DoD's
own title ("Moving **raster** bands") says.

### 1.3 The only thing that moves an anchor today

`Effects_SetWorldY` (`engine/effects/raster.emp:1866`), 16 bytes at `$833A`:

```
833A  02 40 00 03   ANDI.W #3, D0
833E  d0 40         ADD.W  D0, D0
8340  41 f8 8b ee   LEA    ($FF8BEE).W, A0
8344  31 81 00 00   MOVE.W D1, (0,A0,D0.W)
8348  4e 75         RTS
```

**Its only call site in the tree is a DEBUG hotkey** — `C`+`UP`/`DOWN` nudging channel 0 by one
pixel per held frame (`games/sonic4/test/ojz_scroll_test.emp:941`), and the source there says
outright that it exists to keep the proc's *contract* pinned rather than to be a feature. That
hotkey is the whole of "a band's edge moves over time" in the shipped engine, and it needs a human
holding a button.

---

## 2. References read, and what each gave

Per `CLAUDE.md`'s research checklist. **Three gave the design something load-bearing and one of
them corrected it twice; one gave a rejected-but-instructive alternative; one gave a warning; one
gave nothing and the nothing is recorded as a checked negative.** In order of how much they
changed the design: item 7's vertical bob (§2.3, in this repo), Ristar (§2.4), S.C.E. (§2.1),
Batman & Robin (§2.5), sonic_hack / stock S2 (§2.2), Thunder Force IV (§2.6, nothing).

### 2.1 S.C.E. — the target-and-speed ramp, and its bug (LOAD-BEARING)

`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Core/Water Effects.asm:49-70`:

```
        moveq   #0,d1
        move.b  (Water_speed).w,d1
        move.w  (Target_water_level).w,d0
        sub.w   (Mean_water_level).w,d0
        beq.s   .return
        bhs.s   .skip
        neg.w   d1
.skip   add.w   d1,(Mean_water_level).w
```

Three fields (`Engine/Variables.asm:247-253`): `Mean_water_level` (the state, world Y),
`Target_water_level` (world Y goal), `Water_speed` (px/frame). The displayed
level is `mean + ripple`, and the ripple is a *separate additive term* from oscillator slot 0
(`Engine/Core/Oscillatory Routines.asm:84,163`, amplitude `$10`, one-sided after `lsr.w #1`).

**Four things this contributed:**

1. **The two-term split is the reference's own shape.** A slow-moving *mean* plus a fast periodic
   *ripple*, composed by addition. §5's SWEEP + APPROACH is that split, generalised.
2. **A ramp needs a target, not a free rate.** The reference has no unbounded velocity anywhere,
   and §5.2 adopts that.
3. **A named defect to not inherit.** The code above does **not** clamp the step to the remaining
   distance. If `|target - mean|` is not a multiple of `Water_speed` it overshoots and oscillates
   by ±speed forever. It never bites because `Water_speed` is 1 and is written exactly once
   (`Water Effects.asm:99`), so the bug is invisible in the shipped game and would be immediate at
   speed 2. §5.2 clamps.
4. **A "snap or ramp" flag costs one bit.** `WaterResize_MaxYFromX`
   (`Engine/Objects/Check Range.asm:562-577`) uses the sign bit of the Y word to mean "write both
   mean and target" (teleport) versus "write target only" (ramp). We get the same expressiveness
   for free because `Effects_SetWorldY` already exists as the teleport.

**And what it could not give.** *Its advance is triggered by camera X, never by a clock.* The
per-level `WaterResize` hook walks a `(max_y, camera_x)` table; there is no time-keyed motion in
S.C.E. at all. It also ships **dormant** — every level passes `dc.l 0` for `WaterResize`
(`Levels/DEZ/Pointers/DEZ1 - Pointers.asm:7`) and `Water_flag` is never set. So it is a mechanism
to learn the shape from, not one anyone has watched run.

### 2.2 sonic_hack / stock S2 — the amputated version, and confirmation of the corpus (WARNING)

`sonic_hack`'s `DynamicWater` is `rts` (`code/engines/water.asm:119-121`) and the ramp is deleted.
Its live path is `water.asm:14-41`, which is *literally the thing item 4 exists to improve on*:

```
        move.w  #$130,d2                ; position at which the palette changes
        sub.w   (Camera_Y_pos).w,d2
```

A **hardcoded world-Y literal**, no RAM cell, no target, no speed — a horizontal band boundary with
every moving part removed. Worse, it is unreachable: `water.asm:12-13` branches away unless
`Current_Zone` is non-zero and OJZ is the only zone, so `MoveWater` (the ripple + conversion) is
dead code. `New_Water_Level` and `Water_change_speed` exist in `S4.constants.asm:1420-1421` and are
referenced by nothing.

Stock S2 (`s2disasm/s2.asm:5343-5365`) has the identical ramp, dispatched through a per-zone table
in which **every entry is `DynamicWaterNull` except `DynamicWaterCPZ2`** — one camera-X trip point
setting one target. ARZ has *no* rising water (`s2.asm:5395-5396`), contrary to the folklore.
`Water_Level_3` has two writers in the entire disassembly.

**What this contributed: a corpus bound.** The whole Sonic 1/2/3K corpus contains *one* moving
boundary and it is camera-triggered. **Nothing in any reference implements time-driven boundary
motion.** So §5.1 is genuinely new work rather than a port, and no reference will validate it —
which is itself worth knowing before someone goes looking for prior art that is not there.

### 2.3 Item 7's vertical bob — the closest prior art is six days old and in this repo (LOAD-BEARING)

`engine/level/parallax.emp:2146-2170`, EFFECTS-W1 item 7, merged `8c75722b`:

```
        moveq   #0, d3
        move.b  parallax_config.pcfg_bob(a0), d3   ; packed (amp << 4) | period; 0 = no bob
        beq     .v_bob_none
        move.w  d3, d0
        and.w   #$0F, d0                           ; period shift p
        move.w  Logic_Tick+2, d4                   ; the lag-immune tick
        lsr.w   d0, d4
        and.w   #BOB_SINE_ENTRIES-1, d4
        add.w   d4, d4
        lea     Sine_Table, a1
        move.w  (a1,d4.w), d4                      ; -256 .. +256
        lsr.w   #4, d3                             ; amplitude shift a
        asr.w   d3, d4                             ; ARITHMETIC: the wave is signed
        add.w   d4, d2
```

This is a **time-driven vertical displacement, priced in-source at 114-144 cycles**
(`parallax.emp:2128-2135`), packed into **one byte**, costing **zero RAM**, with its two nibble
ladders *derived* by `comptime fn` from the sine table's own constants rather than picked
(`bob_shift_min` / `bob_shift_max` / `bob_period_shift_max`, `parallax.emp:599-691`).

**Everything §5.1 needs is already solved here**: the tick source, the table access mode (`lea`
first — `Sine_Table(pc,d4.w)` is a measured build failure at this distance, `parallax.emp:2154-2160`),
the signed shift, the `moveq #0` before `move.b` (load-bearing: `move.b` leaves bits 8-31 dirty and
the `lsr.w #4` would shift them into the amplitude nibble), and the `0` sentinel. SWEEP is the bob
with `a0` pointing at an anchor instead of at a `parallax_config`. **This is the single most
important input to this design and it is not one of the disassemblies.**

### 2.4 Ristar — four flavours of exactly this, and it corrects this design twice (LOAD-BEARING)

*Read as a raw capstone dump (~460k lines, no symbols, per-line `; $XXXXXX` address comments);
the wave table below was verified by reading ROM bytes directly, because `data` regions decode as
garbage instructions.* Ristar has **no `(scanline, action)` script**: its HBlank vector is a live
`jmp imm.l` in RAM at `$00FFEA70` (installed at `$0004A2`), and every phase change is a
`move.l #addr, $ea72.w`. The "per-stage HInt script" is a **chain of code pointers**, each handler
installing its successor. That answers Q3 in the negative: there is no data-driven script to copy,
so §5.1's packed-nibble surface is not competing with a better one that already exists.

What it *does* have is four working moving boundaries, and two of them change this design:

**Flavour A — accelerating screen-space sweep** (`$00BB2E` init, `$00BD30` advance). A 16-bit
integer scanline in `$FFE688` with an **8.8 velocity** in `$FFE690`; velocity `+= $20` per frame
(acceleration), clamped, then `asr.w #8` and added to the boundary; on reaching line 200 it
**clamps the position AND zeroes the velocity**. Confirms §5.2's clamp-and-stop terminal state.
Multiple boundaries are scheduled by **reprogramming reg 10 from inside the HInt** — one HInt entry
per boundary, not per scanline.

**Flavour B — 16.16 accumulator with an INTEGER MIRROR** (`$011E68`). Three advance modes off one
jump table: a monotone rise at `$4000` = **0.25 px/frame** clamping at a target; a **ping-pong** at
`$2000` = 0.125 px/frame with a direction bit flipped by two bounds tests; and a **ramp toward a
target from a small word table** at one of two rates. The load-bearing observation, and it is the
research lane's own sentence: *"Ristar never stores the boundary as fixed-point in the slot the
raster path reads — always integer + a shadow accumulator."*

> **⚠ THIS CORRECTS §5.2's FIRST DRAFT.** That draft gave APPROACH an integer `u8` speed in
> px/frame, which makes **1 px/frame the slowest expressible ramp = 60 px/s** — a waterline
> crossing the screen in under four seconds. S.C.E. and stock S2 got away with it because 1 px/f is
> the only rate either ever uses; **Ristar's real rates are 0.25 and 0.125 px/frame**, and that is
> what makes a boundary read as *rising* rather than *stepping*. §5.2 is rewritten below.

**Flavour C — base + phase table** (`$0123D0`). `boundary = base + wave[phase]`, where `phase`
advances one step per **32 frames** via an `andi.w #$1f / bne` **rate gate** on the global frame
counter, and `wave` is a 32-entry signed byte table at ROM `$0123FE` (verified by direct read:
`0,-4,-8,-12,-8,-4,0,4,8,12,16,20,24,28,28,28,24,20,16,12,8,4,0,-4,-8,-12,-12,-12,-8,-8,-4,-4`,
range −12..+28 px, a 1024-frame ≈ 17 s swell). The `base` is itself a *second, independently
animated* boundary with its own state machine (`$012354`, rates −1/+1/+8 px/frame, its own rate
gate), and a third machine at `$01226A` does rise-dwell-fall-dwell-loop with four separate rates.

Two things come out of this and **both change the design**:

> **⚠ CORRECTION 1 — the rate gate replaces the accumulator, at zero RAM.** `frame & N` costs one
> `andi` + one `bne` and yields rates 1, 1/2, 1/4 … 1/2^k px/frame **with no accumulator at all**.
> For power-of-two rates it is not an approximation of the 16.16 accumulator, it is *the same
> motion*: `acc += $4000` mirrors an integer that increments on exactly every 4th frame, which is
> what a mask of 3 does. Since every rate we need is a power of two (§9.6 already accepts that
> ladder for SWEEP), the accumulator buys nothing and costs 16 bytes of RAM and a seed. **§5.2
> adopts the gate.**
>
> **⚠ CORRECTION 2 — SWEEP needs a per-channel PHASE OFFSET.** *"One table serves any number of
> bands if you give each band its own phase offset."* Without it, two channels sweeping at the same
> period move in lockstep, which reads as one boundary rather than two. Item 7's bob needs no
> offset because it is scene-global; a per-channel sweep does. **This repo already has the
> pattern** — `band_entry.band_phase_offset` exists for exactly this reason on the deform sampler
> (`engine/level/parallax.emp:107`). §5.1 gains a phase byte and `ep_patch_motion` widens from
> `[u8;4]` to `[u16;4]`.

**Flavour D — world Y → scanline** (`$00D3C8`): `line = worldY − cameraY`, clamp negative to 0, park
at `$FF` when past the screen, cache the scanline, `addi.w #$8a00` into reg 10. **Structurally
identical to `Effects_LatchWorldLines` plus `Raster_BuildSchedule`'s clamp/suppress** — independent
confirmation that the shipped shape is the right one. Ristar also ships the *static* counter-example
alongside (`$FFF040`, written only as `#$0` and `#$b0`), which is today's Aeon behaviour: **the two
coexist in one game, which is the disposition this item is asking for.**

**One gotcha worth carrying:** Ristar's one-shot arm flag `$FFEA92` means an already-fired HInt
still *enters* on every subsequent trigger and costs ~20 cycles to bail. Our schedule builder chains
with gap counters and parks at `$FF` rather than re-entering, so we do not pay this — recorded
because it is the obvious way to get it wrong.

### 2.5 Batman & Robin — the object-anchored boundary, and the shadow trick (LOAD-BEARING, as a rejection)

**Two real moving boundaries, both stored unusually.** HBlank vector is the same RAM inline-`jmp`
(`code/init/vectors.asm:31`, `$FFFFE560`).

**Object-anchored split** (`code/engine/level_engine.asm:3148-3196`, ROM `$01C3F2`): *there is no
boundary variable.* The boundary **is an object's world Y**, read straight out of the SST at offset
`$1A`, converted as `(objY − camY) − 1` into reg 10 with an off-screen early-out. Whatever moves the
object moves the boundary — velocity, script, anything — so it moves independently of the camera by
construction.

> **This is a fifth answer to "where does the mover live" that §4 did not consider: *nowhere — the
> boundary reads a position something else already animates.*** It is rejected for item 4 for one
> reason only, and it is not a technical one: **an object is not authorable in Aurora**, and item 4
> exists so that an author can express the motion. It is, however, exactly what §5.3 recommends for
> the gameplay-coupled case — so B&R is prior art *for the half this design deliberately leaves to
> game code*, which is worth knowing before someone reads that omission as a gap.

**The shadow-table discipline is load-bearing and is the elegant part.** The split routine **swaps
the plane-A scroll shadow**: it stashes the camera's HScroll/VScroll in a scratch pair for the HInt
to restore and writes the object-relative values into the shadow the VBlank already commits. So the
**top band rides the existing commit for free and only the bottom band costs an HInt** — a two-band
split is one HInt, not two commits. Aeon gets the same property by a different route (the schedule
builder emits one record per boundary and the frame-top state is the un-fired base), so this is
confirmation rather than a lever, but it is the argument for why our per-boundary cost is right.

**Pseudo-3D horizon** (`$0246D2`): a boundary scanline in `$FFF5BC` derived from a 32-bit
fixed-point pitch by `swap`, clamped to never rise above line 64, **latched** into a commit slot
whose low byte is OR'd straight into `$8A00`. Advanced by camera pitch, not by a timer — so it is
motion, but not the *time-driven* motion this item wants.

**Self-modifying RAM HInt** (`code/engine/misc.asm:71-170`): copies a 140-byte handler into RAM and
**patches immediate operands inside the copy** as the effect's state, so the band state machine has
zero RAM loads and zero state branches — the state *is* the instruction stream. The cheapest
per-scanline HInt in any of the three trees. **Recorded and not adopted**: it is incompatible with
this codebase's build-time-validation posture (a self-patched immediate is invisible to every
`ensure`, every span gate and every byte golden), and item 4's cost is nowhere near the pressure
that would justify it.

### 2.6 Thunder Force IV — CONTRIBUTED NOTHING, and the negative is worth the space

*Its disassembly has no address comments and no labels; the lane re-disassembled the ROM with
capstone to get addresses, so this is a checked negative rather than a failure to find things.*

- **Only two HBlank handlers exist in the entire 1 MB ROM** (a full scan for `move.l #imm, $f0f8.w`:
  `$C7D2` and `$EE2A`). Neither is a band boundary — one is a Bresenham VSRAM stepper for a
  title-logo vertical *scale*, the other a bitmask-driven line-skip squeeze.
- **VDP reg 10 is never written dynamically.** It comes only from the init table at `$0015D4`,
  where **reg 10 = `$00`** — HInt on *every* line. Reg 11 = `$00` too: full-screen HScroll,
  full-screen VScroll, never a per-line table or 2-cell VScroll in gameplay.
- Its famous parallax is **not band-based**: 8 slots of a 64-byte layer table at `$FF8198`, each
  getting one whole-layer X/Y scroll. Layer objects moved as wholes.

So the earlier claim in `engine/level/parallax.emp:1525-1528` — that TF4 was checked for an
arithmetic alternative to Step 4a's search and *"does not supply one: its bands are SCREEN-anchored"*
— is **confirmed and strengthened**: TF4 has no bands at all. Do not send anyone back to it for
this problem.

*(Also note: that tree's `ANALYSIS.md` presents several listings as "conceptual" pseudo-code. The
parallax loop checks out against the ROM; treat its object-pool listings as illustrative.)*

### 2.7 `docs/ENGINE_ARCHITECTURE.md`

§ around `:4536-4565` documents the anchor bank and the `Effects_Screen_L` latch as shipped, in the
same words `engine/ram.emp` uses. It is the baseline and this design does not contradict it; it
**discharges** its sentence *"rising lava, a flood line, a beat-driven pulse all rewrite an anchor
through `Effects_SetWorldY`"* by supplying the two of those three that are authorable, and by
naming the third as game code (§5.3). ARCH gains a paragraph when this lands; it needs no
correction.

---

## 3. What the design must NOT become — drift, curves, vsplit, bob

The brief asks this plainly: *"Item 4 must not become a second spelling of drift."* It cannot,
and the reason is dimensional rather than a matter of discipline.

| mechanism | what moves | axis | driven by | state | landed |
|---|---|---|---|---|---|
| `SceneDrift.Rate(r)` | a band's **plane-B scroll word** — its *contents* | **horizontal** | a 16.16 accumulator per band, `Parallax_Drift_Acc` | 4 B/band RAM | mechanism 2026-08-29, **adoption is item 3** |
| `curve` | a band's **factor across its own height** | horizontal, per line | camera X, hoisted once/frame | 3 words in the band's curve tail | shipped |
| `vsplit` | where a band's **factor changes** within the band | vertical, comptime | nothing — it is a constant | none | shipped |
| **vertical bob** (item 7) | the **whole BG V-scroll** — every band's contents together | **vertical** | `Logic_Tick` → sine | none | 2026-08-30, **unwitnessed in motion** |
| **this item** | a **boundary's position** — where one band stops and the next starts | **vertical** | `Logic_Tick` → sine, and/or a ramp | 0 or 3 B/channel | not built |

**Drift and item 4 are orthogonal and neither subsumes the other.** Drift adds a per-band term to
`Parallax_Current_Scroll_B[i]`, a *horizontal* scroll word; a band's edges are *horizontal lines*
whose positions are *vertical* quantities. Turning drift's rate up moves the clouds sideways
faster; it never moves the line the clouds stop at. Composed, they are exactly the intended
picture: a cloud band that drifts sideways while its lower edge sweeps up and down.

**The bob is the near miss, and it is worth being precise about why it is not this item.** The bob
adds its sine term to `Parallax_Current_Vscroll_BG` — the *single site the whole pipeline's BG
vertical origin flows through* (`parallax.emp:2185-2190`). Every band top rebases against that
origin in Step 4a, so a bob moves **every band's edge by the same amount, together**: the whole
background sways as one picture. Item 4 needs edges that move **relative to each other** — a
waterline rising *through* a static skyline. A bob cannot express that at any amplitude, and a
per-band bob is unreachable because Step 4a's `.find_k` needs ascending tops (§9.1).

**Sharing the sine table is reuse, not duplication.** The two read the same `Sine_Table` against the
same `Logic_Tick` and pack the same two nibbles, and that is the point: an author who has learned
one ladder has learned both.

---

## 4. Where the mover lives — the ruling

### 4.1 The decision

> **The mover is evaluated inside `Effects_LatchWorldLines`, in its existing per-channel loop,
> against `Logic_Tick`. It is gated on a new capability bit and, within that, on a single
> once-per-frame "any motion authored" word.**

### 4.2 Why there and nowhere else

1. **It is the SINGLE derivation of `Effects_Screen_L`, and that is a standing ruling with a
   named failure it prevents.** `engine/effects/raster.emp:1830-1840`: on a `VInt_Lag` frame VBlank
   runs twice against one main-loop update, so three independent `anchor - Camera_Y` computations
   put the fire line and the boundary state on **different cameras** and every transition pops. A
   mover anywhere else re-opens that: the raster fire would move on the frame the parallax split
   had not yet. One insertion here moves all three consumers, on one tick, with one camera.
2. **The call site is already correct and already exists.** `GameState_OJZScroll_Update:695`, between
   `Camera_Update` and `Parallax_Update`, outside the `Debug_Scene_Freeze` gate. No new proc, no new
   game-loop edit, no ordering ruling to make or to get wrong.
3. **The loop is already the right shape.** It already walks all four channels with `a0` on the
   world bank and `a1` on the screen bank. The mover is loop-body work, not a second walk.

### 4.3 What was rejected, and why

**(a) A per-band anchor that advances — i.e. a 16.16 accumulator per channel, band drift's exact
arithmetic, writing back into `Effects_World_Y[]`.** *Rejected for SWEEP, adopted in a bounded form
for APPROACH (§5.2).* Two reasons:

- **It creates a second authority over one word.** `Effects_World_Y[]` has exactly one writer today
  (`Effects_SetWorldY` and the preset seed). An accumulator that rewrites it every frame silently
  overwrites any gameplay or debug write — the existing `C`+`UP` nudge would appear to do nothing
  the moment a mover was authored on channel 0, and the failure would present as "the hotkey is
  broken". A periodic term has no business owning the anchor; it is a *displacement*, and it belongs
  where displacements belong, downstream of the position.
- **Band drift's seamless-wrap argument does not transfer, and this is the trap.**
  `docs/benchmarks/scanline-p4/BAND-DRIFT.md` §3.2 proves a free-running accumulator is safe because
  `65536 = 128 x 512` exactly, so the pixel part's wrap is a whole number of plane widths and is
  invisible. **An anchor has no such modulus.** It is an act coordinate; a free-running ramp walks
  out of the channel's `patchable(lo, hi)` band and `Raster_BuildSchedule` **removes the record**
  (`raster.emp:1673`, `bgt .suppress`) — the band does not stop, it vanishes. Anyone who reaches for
  the drift accumulator by analogy will import a wrap proof that is false here. §5.2 bounds the ramp
  by a target instead.

**(b) A scene-level clock the bands read — i.e. a global phase word the consumers each index.**
*Rejected.* It is what we would build if there were no single derivation; there is one, and putting
the clock beside it and letting three consumers each do their own lookup is precisely the
divergence `Effects_LatchWorldLines` exists to prevent. Note the design **does** read a scene-level
clock (`Logic_Tick`) — it reads it *once, in the one place*, which is the useful half of the idea
without the seam.

**(c) A mover on the band record (a fourth capability tail beside `band_ext`/`band_curve`/
`band_drift`).** *Rejected, and it is the option that looks most natural.* Two independent blocks:
the shadow view is **destroyed and rebuilt from ROM every frame** and is **rotated**, so slot index
!= layer index (`parallax.emp:283-297`) — the same two properties that forced `Parallax_Drift_Acc`
one stage upstream. And a band record's top is a *plane* line, so a mover there would move the edge
in plane space and inherit Step 4a's `.find_k` ordering requirement (§9.1).

**(d') The boundary IS an object's position — Batman & Robin's answer (§2.5).** *Rejected for this
item, and it is the option with the best pedigree.* B&R stores no boundary variable at all: the
split routine reads an object's world Y out of its SST and converts it (`$01C3F2`). Whatever moves
the object moves the boundary, for free, with no mover to design. **It is rejected for one reason
and it is not technical: an object is not authorable in Aurora**, and item 4 exists so an author can
express the motion. It is, however, exactly what (d) recommends for the gameplay-coupled half.

**(d) A per-frame object writing `Effects_SetWorldY`.** *Not rejected — it is already possible today
with zero engine change, and §5.3 makes it the recommended answer for the gameplay-coupled cases.*
It is rejected only as the answer to *this* item, because an object is not authorable in Aurora and
item 4's whole point is that an author can express it.

---

## 5. The mechanism

The latch's derivation becomes:

```
Effects_World_Y[ch]  <- approach(Effects_World_Y[ch], Target[ch], Speed[ch])     ; §5.2, writes back
Effects_Screen_L[ch] <- Effects_World_Y[ch] + sweep(Motion[ch], Logic_Tick) - Camera_Y    ; §5.1
```

Two terms, composed by addition, exactly as S.C.E. composes mean and ripple (§2.1). The order is
load-bearing: APPROACH publishes into the bank (so gameplay reading `Effects_World_Y` sees a real
world Y), SWEEP does not (it is a display displacement — see §9.4 for what that costs).

### 5.1 SWEEP — periodic, stateless, the item's core deliverable

```
sweep(m, t) = Sine_Table[((t >> p) + ph) & (SINE_CYCLE_ENTRIES-1)] >> a
              where m = (a << 12) | (p << 8) | ph        ; a,p one nibble each; ph a byte
sweep(0, t) = 0
```

Item 7's bob (§2.3) in every respect except two: `m` is per **channel** rather than per scene, the
result is added to an anchor rather than to the BG V-scroll, and **it carries a phase offset**.

**The phase byte is Ristar's correction (§2.4 flavour C), and it is not decoration.** Without it,
two channels sweeping at the same period move in lockstep and read as one boundary. Ristar gives
each band its own phase into one shared wave table for exactly this reason; **this repo already
has the pattern** in `band_entry.band_phase_offset` (`engine/level/parallax.emp:107`), which exists
to desync the deform sampler across bands. `ph` is added *after* the shift so it is a phase in table
entries (0..255 = a full cycle), matching how the deform sampler spells it.

- **Peak-to-peak travel** = `2 * (SINE_AMPLITUDE >> a)` px. With `SINE_AMPLITUDE = $100` that is
  `512 >> a`: shift 4 gives 32 px, shift 6 gives 8 px.
- **Period** = `SINE_CYCLE_ENTRIES << p` ticks = `256 << p`. At 60 Hz, `p=0` is 4.3 s, `p=3` is 34 s.
  (Ristar's own swell is 1024 frames ≈ 17 s, which is `p=2`. The ladder covers the reference.)
- **`m = 0` is the sentinel for "this channel does not sweep"**, which is why amplitude shift 0 must
  be illegal — item 7 pins exactly this at `parallax.emp:705` and the reasoning applies verbatim.
  Note the sentinel is now the whole **word**, so `a=0, p=0, ph=0` is the only colliding encoding
  and shift 0 being illegal is still what separates them.
- **The amplitude ladder must be re-derived, NOT copied from the bob.** `BOB_SHIFT_MIN` is derived
  against `VSCROLL_BG_MAX` (289 seam-free plane-window origins) because the bob's excursion has to
  fit the *plane*. An anchor's excursion has to fit **the channel's declared `patchable(lo, hi)`
  band** — a different quantity, in screen lines, and per channel rather than global. Copying the
  bob's number would be the copied-expectation defect this repo has booked three times. §11 Q1
  carries the open half: whether the bound can be comptime at all.

**What SWEEP buys, against the DoD's own three examples:** a light shaft crossing (yes, directly), a
shadow sweeping (yes), a waterline *swaying* (yes — this is the reference's ripple, and Ristar's
±12/+28 px swell). A waterline **rising and staying risen** — no. That is §5.2.

### 5.2 APPROACH — a rate-gated ramp to a target, with the reference's bug fixed

*Rewritten after §2.4. The first draft used an integer px/frame speed; Ristar shows why that is too
coarse and shows the cheaper fix.*

Per channel: a `u16` target (`$FFFF` = none) and a `u8` **rate shift**.

```
if Target[ch] == NONE:                      nothing
if (Logic_Tick & ((1 << RateShift[ch]) - 1)) != 0:   nothing this frame     ; THE RATE GATE
d = Target[ch] - World_Y[ch]
if d == 0:                                  nothing                        ; terminal, forever
World_Y[ch] += (d > 0 ? 1 : -1)                                            ; ONE pixel, so it
                                                                           ; cannot overshoot
```

**Three properties, each from a specific reference finding:**

1. **The rate gate replaces the accumulator, at zero RAM** (§2.4 correction 1). `RateShift` k gives
   `1 / 2^k` px per frame: 1, 0.5, 0.25, 0.125 … down to 1/128 px/f at k=7 (≈ 2 px/s, a genuinely
   slow flood). Ristar's two real rates — `$4000` = 0.25 and `$2000` = 0.125 px/f — are k=2 and k=3.
   For power-of-two rates this is not an approximation of a 16.16 accumulator, it is the identical
   motion: `acc += $4000` mirrors an integer that increments on every 4th frame, which is what a
   mask of 3 does. **The accumulator would cost 16 bytes of RAM, a seed, and a re-entry semantics
   ruling, and buy nothing.**
2. **Stepping one pixel makes overshoot arithmetically impossible**, which is the S.C.E./S2 bug
   (§2.1(3)) not merely fixed but *unreachable*. Their `add.w speed, mean` with no `min` oscillates
   by ±speed forever when the distance is not a multiple of the speed; it never bites there only
   because their speed is 1 and is written once. A one-pixel step is their speed-1 case made
   universal, with the rate moved into the gate.
3. **Arrival is terminal and free.** `d == 0` costs the compare, forever. Ristar's flavour A does
   the same thing explicitly (`clamp the position AND zero the velocity`, `$00BD62`). A risen
   waterline that has arrived costs nothing.

**Handles:**

- **`Effects_SetWorldY` remains the teleport** and needs no change — it moves the *position*; the
  ramp continues from wherever it lands. That is S.C.E.'s sign-bit "snap vs ramp" flag
  (`Check Range.asm:562-577`) obtained for free from a proc that already ships.
- **A new `Effects_SetTargetY(ch, y, rate_shift)`**, mirroring `Effects_SetWorldY` instruction for
  instruction, is the retarget handle — what lets a boss, a switch or a cutscene drive a flood.
- **Ownership rule, stated once:** a channel with a live target is owned by the mover; a channel
  with `Target = NONE` is owned by whoever writes `Effects_World_Y`. Both are legal; both at once is
  an authoring error the engine cannot detect and does not try to.

**Not built, and named so the absence is a decision:** *ping-pong* (Ristar flavour B's direction bit
flipped by two bounds tests, `$011EA2`) and *acceleration* (flavour A's `velocity += $20`). Both are
small — ping-pong is a direction bit plus a second bound; acceleration needs the velocity word the
gate removed. Neither is asked for by the DoD's three examples, and a ping-pong is expressible today
as a SWEEP with a large amplitude, which is the same picture by a cheaper route.

### 5.3 What is deliberately NOT built: the gameplay-coupled ramp

"The water rises when the boss is hit, and stops at the ledge" is **game logic**, and the engine
already exposes the handle for it — `Effects_SetWorldY`, `pub`, shipped, contract-pinned. Building
an engine-side scripting tier for it would be a dormant scaffold with no consumer, which this repo
rules against (`LO_SUPPRESS` was ruled out 2026-08-28 on exactly this ground). **§5.2's target is
the authorable half; §5.3's object is the scripted half; there is no third thing.** Say this
explicitly in the authoring docs, because "the engine has no rising water" is the wrong conclusion
to draw from its absence.

---

## 6. State, and where it lives

| what | where | size | why there |
|---|---|---|---|
| `Effects_Motion[4]` | RAM, beside `Effects_Screen_L`, inside `Raster_State` | 4 B (`[u8;4]`) | the packed `(a<<4)\|p` byte, **bit-identical to `pcfg_bob`** so the ladder code is literally item 7's |
| `Effects_Phase[4]` | same | 4 B (`[u8;4]`) | Ristar's per-band phase offset (§2.4 correction 2); separate from the motion byte so the bob's packing is reused rather than re-invented |
| `Effects_Target[4]` | same | 8 B (`[u16;4]`) | mutable at runtime — that is the point |
| `Effects_RateMask[4]` | same | 8 B (`[u16;4]`) | **the MASK, not the shift.** `(1<<k)-1` is comptime work; computing it per channel per frame would be ~14 cycles to store 4 fewer bits, and `CODING_CONVENTIONS.md` §2 rules that direction |
| `Effects_Motion_Any` | same | 2 B | the once-per-frame gate (§7.2) |
| `ep_patch_motion[4]`, `ep_patch_phase[4]` | `EffectsPreset`, `$26`/`$2A` | +8 B/record | the preset already owns `ep_patch_world_ys` at `$1C`; the seed belongs beside the seed |
| `ep_patch_target[4]`, `ep_patch_ratemask[4]` | `EffectsPreset`, `$2E`/`$36` | +16 B/record | *P3 only — see §10* |

**RAM: +26 B** (SWEEP-only: +10 B). **ROM: +8 B/preset x 7 shipped presets = +56 B** for SWEEP,
+16 B/preset = +112 B with APPROACH, plus the code. `EffectsPreset` goes 38 -> **46** (SWEEP) or
**62** (both).

- The 7 shipped presets are contiguous at `$13F10..$13FF4`, stride `$26` = 38, verified from
  `s4.debug.lst:2082-2088` — `$13F36 - $13F10 = $26`. `struct EffectsPreset (size: 38)`
  (`engine/effects/preset.emp:57`) must be re-declared **spelt in full, never as a delta**, per that
  file's own standing instruction; its size has already gone stale once, by 4, undetected for two
  tasks, because the module was outside every `use` closure and sigil validates a declared layout
  only when something reachable uses it.
- **The RAM addition lands inside `Raster_State` and that has a ritual.** `RASTER_STATE_SIZE`
  (`engine/effects/raster.emp:374`) is a spelt-out sum that measures the region's real emitted span,
  and `engine/ram.emp` mirrors `RASTER_MAX_PATCH` as a **bare literal `4`** in two places
  (`:480`, `:498`) because the ram-harvest pass runs outside the comptime-helper injection. Any new
  `[T; 4]` here spells the literal and the `RASTER_STATE_SIZE` term together, or the build goes red
  at `raster.emp` — which is the designed behaviour, not a hazard.
- **Free RAM is not tight.** `Game_RAM_End = $FFFFE610` (`s4.debug.lst:5503`); the next reserved
  address seen in the listing is `$FFFFFC00`, a span of `$15F0` = 5,616 bytes. 26 bytes is 0.5% of
  it. *Caveat: I did not audit what occupies that span, only that no symbol in the listing does.*

### 6.1 The capability bit — and the arithmetic that constrains it

`CAP_ANCHOR_MOTION` **must be `$0100`**, not a value picked to avoid disturbing the reserved list.
`tools/test_scene_span_labels.py::test_the_declared_and_retired_bits_are_a_gapless_run_from_bit_zero`
asserts that declared ∪ retired is exactly `[1 << i for i in range(N)]`
(`engine/level/scene_dsl.emp:216-231`), so a new declaration takes the **next** bit and **every
reserved name shifts up one**: `CAP_FG_SPRITE_STRIPS $0100→$0200`, `CAP_BGANIM_BOUND $0200→$0400`,
`CAP_DENSE_TIER $0400→$0800`, `CAP_COMPUTED $0800→$1000`, `CAP_DEGRADE $1000→$2000`. Band drift's
declaration block documents this and did exactly this; do not re-litigate it.

sonic4's `SCANLINE_CAPS` is `$005E` today (`games/sonic4/config/game.emp:71`). Item 3 raises it to
`$00DE`; this item raises it to `$01DE`. **Sequencing note: whichever of items 3 and 4 lands second
inherits a one-line conflict on that constant and on the reserved-name comment. Nothing else
couples them.**

---

## 7. The cost, priced

### 7.1 The referent, said before the numbers

`Effects_LatchWorldLines` is **main-loop, non-walker** code. It sits inside
`axis1_reservation_cycles = 24257` (`tools/effects_budget_model.toml:1208`, = 15980 non-walker main
loop + 8277 VInt bracket), **not** inside `axis1_budget_cycles = 103743`. So a cycle added here is
**not** a cycle spent out of the scene budget — it is a cycle **removed from** it, for every scene,
on every frame. That is a stricter charge than "0.3% of budget" and it is the honest one.

`axis1_worst_scene_cycles = 42740.77` (`:1209`), so headroom today is `103743 - 42741 = 61002`.

### 7.2 The gate, and why it inverts band drift's rule

BAND-DRIFT §3.1 rules against a per-band `tst` on the rate: *"A zero rate costs 48 cycles; testing
for it costs ~30 to save ~40."* That reasoning is correct there and **inverts here**, which is worth
showing rather than asserting: a single `tst.w Effects_Motion_Any` + `beq` costs **12 cycles once
per frame** and skips **224 to 896** depending on what is authored. Between 19:1 and 75:1, against
band drift's 0.75:1. The rule is "measure the ratio", not "never test" — and stating the ratio is
what makes the two decisions consistent rather than contradictory.

With the gate, a game that declares the bit but authors no motion runs the **existing 172-cycle
loop unchanged**, plus 12.

### 7.3 Derived per-frame cost

Nominal MC68000, derived from the instruction shapes in §5 and from the *encoded* forms of the
existing loop (§1.1) and item 7's bob (§2.3). `a` and `p` are the sweep nibbles.

| state | derivation | cycles/frame | Δ vs today | axis-1 budget after |
|---|---|---|---|---|
| capability OFF | the block elides | **172** | 0 | 103743 |
| ON, nothing authored | 172 + `tst.w`/`beq` on `Effects_Motion_Any` | **184** | **+12** | 103731 |
| ON, 1 ch sweeping | 184 + 3x`lea` (24) + 1x(110+2(a+p)) + 3x30 | **~408** | **+236** | 103507 |
| ON, 1 ch sweeping + 1 ch ramping | + 2x`lea` (16) + 1x104 + 3x30 | **~618** | **+446** | 103297 |
| ON, 4 ch sweeping | 184 + 24 + 4x(110+2(a+p)) | **~648** | **+476** | 103267 |
| ON, 4 ch, both terms, all moving | + 16 + 4x104 | **~1080** | **+908** | 102835 |

Per-channel arms, derived from the instruction shapes in §5 (each arm's cost is the sum of its
encoded forms; `a`, `p` are the sweep nibbles):

| arm | inactive | active |
|---|---|---|
| the existing loop body | — | 30 (measured shape, §1.1) |
| SWEEP | 30 (`moveq`/`move.b`/`beq` + step the phase cursor) | **110 + 2(a+p)** |
| APPROACH | 30 (no target) · 62 (target set, rate gate shut this frame) | **104** |

Worst realistic case (**+908**) is **1.5% of today's headroom** (`103743 - 42741 = 61002`) and
**0.7% of the 128,000-cycle frame pool**. The shipped-today case (+12) is **0.01%**. **The realistic
first-content case is one sweeping channel: +236, or 0.4% of headroom.**

**Two addressing-mode assumptions the cost rests on, checked rather than inherited** (item 7's
source flags the first as rot-prone in its own words — *"it costs 4 more cycles and 2 more bytes
the day ROM growth pushes it past"*):

- `Sine_Table` is at **`$2AF0`** (`s4.debug.lst:2956`), so `lea Sine_Table,aN` still lowers to
  **absolute short = 8 cycles**, not 12. Headroom to `$8000` is `$5510` = 21,776 bytes.
- `Logic_Tick` is at **`$FFFF8004`** (`s4.debug.lst:5181`), so `move.w Logic_Tick+2,dN` is
  absolute short = **12 cycles**.

**ROM:** ~120-150 bytes of code for SWEEP (~16 instructions in the loop + 3 `lea` + the gate),
~90-110 more for APPROACH (~15 instructions), plus **+56 B** (SWEEP) or **+112 B** (both) of preset
records (§6), plus **+16 B** for `Effects_SetTargetY`. Call it **+180 to +210 bytes for P2** and
**+400 to +440 cumulative after P3**, in the shapes that declare the bit; **0** in `demo`
(`SCANLINE_CAPS = 0`).

### 7.4 ⚠ HOW WRONG THESE NUMBERS ARE LIKELY TO BE — the calibration, stated

The brief is right that this repo's cycle tables have rotted. **The relevant calibration is
band drift's, because it is the most recent same-shaped derivation and it was checked**
(`BAND-DRIFT.md` §4.3, three-build differential, spread 0 on every fixture):

| quantity | predicted nominal | measured | error |
|---|---|---|---|
| the drift block, per band | 56 | 52 marginal / 56 on band 1 | −7% marginal, **exact** on the first |
| Step 4a copy widening, per band | 20 | 16 | −20% |
| the frame constant (`lea`) | 8 | 12 | **+50%** |
| **combined, per band** | 76 | 68 | **−10.5%** |

Its own conclusion: *"The model held. Every predicted term is within 11%."* Note the residual it
could not explain — **4 cycles per band cheaper from the second band on** — is unidentified, and the
instrument is an emulator **ideal-cycle** clock, not the datasheet.

**So: read §7.3 as ±15%, and expect the loop terms to come in LOW and the frame constants HIGH.**
The idle number (+12) is two instructions and is the one least likely to move.

⚠ **TAGGED FOR FOREGROUND MEASUREMENT — MEASUREMENT 1.** No emulator was run for this design (the
brief forbids it from a background agent). The measurement is: **the per-routine profiler row for
the game state's frame, camera frozen, in four builds** — capability off; on with nothing authored;
on with one channel sweeping; on with four channels sweeping and approaching. `tools/parallax_cost_probe.py`
is **not** the instrument (it measures `Parallax_Update`); the row wanted is the main-loop one, and
the fixture discipline to copy is BAND-DRIFT §4.1's — *one thing changes per pair*, with the
"widened state, block elided" build built on purpose so the RAM/seed cost and the block cost are a
split rather than a lump.

---

## 8. The authoring surface — and it is BLOCKED

**This is the section the brief asked to be checked, and the answer is that item 4 cannot be
authored today.** `tools/EFFECTS_CONSUMER_CONTRACT.md`'s drift rule is unambiguous: *"the consumer
may read exactly the fields listed here. Adding a read of a new field... is a CONTRACT change: it
amends this file + the empyrean schema pair in the same change series, and Aurora re-pins its
golden."*

### 8.1 What the two documents can express today

| document | key set | can it name a channel? | can it set the channel's world Y? | can it set motion? |
|---|---|---|---|---|
| **scene** (`editor/effects/<id>.json`) | contract §2.1 — incl. `anchor` | **yes** (`anchor` → `pcfg_anchor_ch`, generator at `tools/effects_gen.py:1165-1167`) | **no** | **no** |
| **preset** (`editor/effects/presets/<id>.json`) | `{schema, id, name, bands, cycles, variants}` (contract §2.4; `cycles`/`variants` landed 2026-09-02 as item 5) | no | **no** | **no** |

Grep of `tools/effects_gen.py` for `patch_world_ys` returns **nothing**. The anchor *seeds* —
`ep_patch_world_ys`, the field `Effects_InstallPreset` copies into the bank unconditionally on every
install (`preset.emp:254-290`) — **are reachable only from hand-written `.emp`.** So:

> **Item 4's authoring gap is not one field, it is two.** Even if a `motion` key landed tomorrow,
> an author could not say *where* the boundary starts, because `patch_world_ys` has never been
> exposed either. **The world-Y seed is the prerequisite, and it is a contract change on its own.**

This is a genuine finding and it changes the item's shape: the aeon-only half (engine + generator)
does not produce an authorable feature. **The same wall item 3 hit, and one field deeper.**

### 8.2 The CR this needs — the shape, not the text

Filed against `empyrean/docs/AURORA_EFFECTS_SCHEMA.md` §7 and
`contract/schema/aurora-effects-preset.schema.json`, following the template of
`docs/2026-08-30-effectsref-contract-change.md`.

**Where the keys go: the PRESET document, not the scene.** This is already settled by two committed
rulings and must not be re-argued — `docs/superpowers/specs/2026-08-28-raster-band-ownership-design.md`
§16.1 (*"A scene IS a `parallax_config`. It is not an effects bundle... 'put a band in a scene' is
not a thing you can do"*) and empyrean §7's own reservation of the presets directory for
*"patchable **world-anchor channels**"* — which is this item, named, in a reservation that predates
it. A parcel dispatched to put these on the scene file would be repeating a documented mistake.

**Proposed shape**, one key, an array of four channel objects, so the two prerequisites land
together:

```json
"channels": [
  { "world_y": 1328, "motion": { "sweep": { "amplitude_shift": 4, "period_shift": 2 } } },
  { "world_y": null },
  ...
]
```

with `world_y: null` = `PATCH_ANCHOR_NONE` and `motion` absent = static. Whether `target`/`speed`
(§5.2) join in the same CR or a later one is §10's sequencing question, not a schema question.

**Three consequences the CR must state, all inherited rather than new:**
- **An older `effects_gen.py` silently ignores the key** — the sidecar/document readers apply no
  unknown-key check on this path, so a tree carrying `channels` and an older generator builds green
  and shows nothing (contract §6.1's named, accepted behaviour).
- **An older Aurora erases it** on the next save round-trip, so the sequencing precondition applies:
  **no `channels` key lands in aeon's tree until the Aurora-side writer is on aurora master**, and
  the aeon parcel cites that SHA. `sceneRef` needed `a88db05`; `rasterRef` needed `7b1d15a0`.
- **The generator validates SHAPE, sigil validates VALUES** (contract §2.1's standing posture). The
  amplitude/period ladders stay `ensure`s in `.emp` so the author reads the sentence carrying the
  measurement.

### 8.3 ⚠ The trap this document is itself standing next to

`EFFECTS_CONSUMER_CONTRACT.md`'s own banner: *"THIS DOCUMENT ENUMERATES FIELD NAMES. THE EMPYREAN
SCHEMA OWNS THEIR VALUES"* — and it records that reading it as if it settled values **already
shipped two defects**. The JSON above is a **proposal**, not a specification. The implementer reads
`empyrean/docs/AURORA_EFFECTS_SCHEMA.md` and `contract/schema/aurora-effects-preset.schema.json`
**at a committed revision** (`git -C ../empyrean show origin/main:<path>`), never through the working
tree.

---

## 9. What it cannot do — limits, not omissions

**9.1 A parallax band's own top cannot move.** Step 4a's `.find_k` (`parallax.emp:1543-1556`) finds
the last band whose plane top ≤ the current V-scroll, assuming **tops ascend and band 0's top is 0**.
Independently-moving tops cross, and a crossing does not degrade — it selects the wrong `k` and
rotates the entire shadow view to the wrong band, mis-attributing every band's scroll for that
frame. Moving edges are the **anchored split** and the **raster fires** (§1.2). Making band tops
movable is a different, larger item that would need the search replaced by a sort.

**9.2 At most four moving edges, at most one of them splitting the parallax bands.**
`RASTER_MAX_PATCH = 4` is pinned in three places, one of them a bare literal in `ram.emp` for a
harvest-pass reason (§6). `pcfg_anchor_ch` is a single byte, so a scene binds **one** channel to its
band split; the other three can move raster fires only. Raising 4 is a separate parcel.

**9.3 An edge's travel is bounded by its channel's declared `patchable(lo, hi)` band, and leaving
it upward does not stop the edge — it DELETES the band.** `raster.emp:1673`, `bgt .suppress`, removes
the record for the frame; below `lo` the line is clamped up and the frame-top ship covers the rest.
Both behaviours are correct and deliberate; neither is what an author expects from "the water kept
rising". **A sweep whose amplitude exceeds its band flickers the band out at the top of every
cycle** — this is the most likely first bug, and §11 Q1 is whether it can be refused at build time.

**9.4 A swept edge's position exists only in screen space.** SWEEP is added into `Effects_Screen_L`
and never into `Effects_World_Y`, deliberately (§4.3a). So a future gameplay consumer asking "is the
player under the waterline" reads the **mean**, not the swept surface. S.C.E. publishes both
(`Water_level` displayed vs `Mean_water_level`) and gameplay reads the displayed one. **This costs
nothing today because no gameplay reads the bank**, and the fix when it does is 8 bytes
(`Effects_Display_Y[4]`) and one `move.w` per channel. Named so it is a decision later, not a
discovery.

**9.5 A moving TOP only, with a static bottom** — for raster bands, until P3. That is parcel P2b's
scope (`2026-08-28-raster-band-ownership-design.md` §8) and the constraint is ORD-1: the ON fire's
`band_hi` must sit strictly above the static restore's line. So the band gets taller and shorter; it
does not travel as a rigid pair. The *other* half of rule 6 (`raster_dsl.emp:2673`, a patchable
**restore** = a moving bottom) stays refused and must: sweep 5 measured its failure — the suppressed
restore leaves the tint running to the bottom of the screen instead of turning off where authored.
**Both edges moving is P3** — +2 bytes/patch record, a named relaxation of `check_intervals`, and
*"only if the owner asks"* per the DoD.

**9.6 Power-of-two ladders only, on all three axes.** Sweep amplitude is `256 >> a` and period is
`256 << p`, so the authorable sets are {256, 128, 64, 32, 16, 8, 4, 2} px peak and
{4.3 s, 8.5 s, 17 s, 34 s, ...}; **APPROACH's rate is `1 / 2^k` px/frame** by the same rule, since
the rate gate *is* a power-of-two mask (§5.2). An author wanting a 20-pixel sway gets 16 or 32; one
wanting 0.2 px/frame gets 0.25 or 0.125. **This is exactly the corpus's own resolution** — Ristar's
only two real waterline rates are 0.25 and 0.125, S.C.E.'s only rate is 1 — so the ladder is not a
compromise against the reference, it is the reference. Arbitrary values need a multiply
(`CODING_CONVENTIONS.md` §2.1's four-point argument) or a fixed-point accumulator, and neither is
worth it until someone asks. **Item 7 shipped with the identical ladder and nobody has complained — but
nobody has watched it move either** (its lane row: *"⚠ NOTHING SEEN IN MOTION"*).

**9.7 No easing, and no acceleration.** APPROACH moves at a constant rate, exactly as S.C.E. and
Ristar's flavour B do. A waterline that decelerates as it arrives is not expressible. Ristar's
flavour A *does* accelerate (`velocity += $20` per frame, `$00BD3C`) and that would need the
velocity word the rate gate removes — a real trade, named in §5.2, and the direction to go if
someone wants a boundary that lurches.

**9.8 Nothing here is verified in motion, and one thing beneath it is not either.** This design
rests on the anchored split and the patchable fire path being visually correct. `Effects_SetWorldY`
is exercised **only from the DEBUG hotkey**, and `docs/benchmarks/effects-p3-p-b/GATE-EVIDENCE.md`
§6 books the main-loop-write → VBlank-conversion seam as measured but not pixel-verified. If the
foundation has a one-frame or one-line error, this item will surface it and it will look like this
item's bug.

---

**9.9 `Debug_Scene_Freeze` does not stop the mover, and that is correct twice over.**
`Effects_LatchWorldLines` runs **outside** the freeze gate on purpose
(`games/sonic4/test/ojz_scroll_test.emp:704`, and `tools/parallax_cost_probe.py:864-868` depends on
it), so a frozen scene still latches. A mover inside the latch therefore keeps moving with the
camera pinned — which is *literally the item's own description* and makes the frozen scene the ideal
witness instrument. It also means a probe that freezes the camera and expects a static picture will
see one that is not; that is the mover working, not interference.

**9.10 Authoring a mover into a shipped scene INVALIDATES the recorded replay fixtures.** The
existing anchor hotkey is deliberately input-gated precisely so it cannot do this — its own source
says *"a free-running counter would perturb every frame of every build of this scene, moving the
visual baseline and risking a desync in the replay fixtures"* (`ojz_scroll_test.emp:865-871`). A
`Logic_Tick`-driven mover is **deterministic** (that counter *is* the replay timebase, lag-immune,
`engine/ram.emp:249-250`) so replays stay reproducible — but every checkpoint recorded before the
mover existed was recorded against a different picture. **Parcel P5 carries a fixture re-stamp**,
and `REPLAY-RESTAMP` is the precedent for what that costs. This is a cost of *authoring*, not of
landing the mechanism: P2/P3 with nothing authored perturb nothing.

## 10. Parcel ladder

Each rung is separately landable and separately witnessable. **P0 is not optional** — it is the
cheapest way to find out whether the foundation works before building on it, and it is the exact
mistake `feedback_test_before_stacking` names.

| # | parcel | bytes | gates on | delivers |
|---|---|---|---|---|
| **P0** | **Witness the shipped mechanism.** Drive the `C`+`UP`/`DOWN` hotkey and confirm the palette boundary AND the parallax split track the anchor together, on the same frame. Zero code. | 0 | nothing | the answer to §9.8; kills or confirms the item's premise for one session's work |
| **P1** | **P2b** — relax rule 6 **half 2** at `engine/effects/raster_dsl.emp:2710` (*"a patchable partner is the split spelling of a moving-top band"*), keeping ORD-1 and keeping **half 1** at `:2673` (a patchable *restore* is moving-BOTTOM and stays refused) | **0** (design §8: *"no runtime change at all"*) | P1 of the band-ownership design, **landed 2026-08-28** | **moving TOP, static bottom** for raster bands, byte-identically |
| **P2** | **SWEEP** — `CAP_ANCHOR_MOTION = $0100`, `Effects_Motion[4]` + `Effects_Phase[4]` + `Effects_Motion_Any`, `ep_patch_motion`/`ep_patch_phase`, the loop body, the derived ladders and their `ensure`s, poison fixtures | ~+120-150 code, +56 preset, +10 RAM | P1 | **the item's core: an authored edge that sweeps, each channel on its own phase** |
| **P3** | **APPROACH** — target + rate-mask banks, `Effects_SetTargetY`, the rate-gated one-pixel ramp | ~+90-110 code, +56 preset, +16 RAM | P2 | **a rising waterline that arrives and stops** |
| **P4** | **the CR + the generator** — `channels` in the preset schema; `effects_gen.py` reads `world_y` and `motion` | 0 unbound (always-emitted zero-byte chooser, ruling Q-c) | **empyrean adjudication + an Aurora writer on master** | **authorability — without this, P2/P3 are engine features nobody can use** |
| **P5** | **the authored scene + the look** | content | P4 | the owner sees it |

**P1 and P2 are independent** — P2b unlocks a raster band's top edge; SWEEP moves the anchor
whatever consumes it, and the anchored parallax split consumes it today with no P2b at all. Either
can go first. **P4 is the long pole and it is not aeon's to schedule**, which is why P2 and P3 are
worth landing behind it rather than waiting: a hand-authored `.emp` scene proves the engine half and
is exactly what `Scene_Perspective` does for `decline_borrow` today.

---

## 11. Open questions

**Q1 — Can a sweep's amplitude be bounded against its channel's band at build time?** §9.3's
flicker is the item's most likely first bug and it is a build-time-refusable class *if* the two
numbers can meet. They may not: `lo`/`hi` live in the raster program's `patchable(...)` call,
`amplitude_shift` would live in the preset, and the preset and the program are separate `.emp`
data whose association is a pointer. **If they cannot meet at comptime, say so in the `ensure`
message and put the bound in the authoring doc instead** — a runtime clamp is the wrong answer
(item 7 explicitly rejects one for the same class, `parallax.emp:596-598`). *Not settled here.*

**Q2 — Does the widened `clobbers()` on `Effects_LatchWorldLines` move sigil's contract baseline?**
Today it declares `clobbers(d0-d2/a0-a1)`; the loop in §5 needs roughly `d0-d6/a0-a5`. **Band drift
hit exactly this** — `[call.live-clobbered]` (D1c) fired in the destructive GONE direction and the
fix was a paired commit against `crates/sigil-harness/src/contract_baseline.rs`
(BAND-DRIFT.md §6). **Assume this parcel pairs with sigil and budget for it.** *Not verified —
nothing was built.*

**Q3 — Is sine the right primitive? ANSWERED: yes, and there is no script to lose to.** Ristar's
"per-stage HBlank script" turns out to be a *chain of code pointers* (`move.l #addr, $ea72.w`), not
a `(line, action)` data table — there is no data-driven scripting surface in any of the three trees
to compete with two packed nibbles (§2.4). Ristar's own periodic boundary is `base + wave[phase]`
off a **32-entry signed byte table**, which is a coarser sine; ours is a 256-entry word table we
already ship. **One residual, not closed:** Ristar's table is *not* a sine — it is an asymmetric
hand-drawn swell (−12..+28, with dwells). A hand-authored wave is more expressive than a sine and
costs one `tableRef`, which the effects schema already has a mechanism for. **Not proposed here**,
because nobody has asked for a non-sinusoidal boundary and §5.1's `tableRef` variant would be a
speculative second path. Recorded so the option is known to exist.

**Q4 — OWNER CALL: is `Rate` wanted at all?** §4.3(b) argues the unbounded 16.16 ramp is a footgun
here because there is no modulus, and §5.2 replaces it with target+speed. **A free-running edge that
wraps its band is nonetheless a real look** (a repeating light shaft, a conveyor of shadow) and it is
a taste question, not an engineering one. Designed up to this line: the mechanism would be
`Target = the far edge, and on arrival reseed the position to the near edge` — a two-instruction
addition to §5.2, not a new term. **Not chosen here.**

**Q5 — OWNER CALL: P3 (both edges moving).** The DoD defers it to *"only if the owner asks."*
Priced by the band-ownership design at +2 B/patch record and *"~+8 NOMINAL cycles per patchable
record per VBlank (unmeasured)"*. Nothing in this design forecloses it.

---

## 12. What this document did not settle

- **Every reference in the brief was read** (§2). Ristar corrected this design twice after the
  first draft was committed — §5.2's ramp was too coarse by 4-8x and §5.1 had no phase offset — and
  both corrections are marked in place rather than smoothed in, so a reader can see which parts of
  the design survived contact with the corpus and which did not.
- **No cycle was measured.** §7.3 is derived from encoded instruction shapes and calibrated against
  band drift's ±11%; MEASUREMENT 1 (§7.4) is tagged with its exact fixture matrix.
- **No pixel was looked at**, including of the mechanism this builds on (§9.8, parcel P0).
- **Q1's comptime reachability was reasoned about, not tried.** A 20-minute throwaway build probe
  would settle it and no such probe was run.
- **The per-arm cycle costs in §7.3 are derived from instruction shapes I wrote, not from an
  assembled listing.** Item 7's bob and the existing latch were read out of the ROM; the *new* arms
  cannot be, because nothing was built. That is the ordinary state of a design pass and it is why
  MEASUREMENT 1 exists — but it is a weaker footing than §1's numbers and the two should not be read
  as equally solid.
- **`RASTER_MAX_PATCH = 4` was not questioned.** Four moving edges is enough for every case the DoD
  names, but nobody checked whether the showcase act wants more, and raising it is a three-site
  change (§9.2) that is much cheaper to do before P2 than after.
- **The empyrean schema was not read at a committed revision for this pass.** §8.2's JSON is a
  proposal shaped from aeon's side of the contract only, and §8.3 says why that is a trap and not a
  specification.
