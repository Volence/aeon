# Character subsystem — lens-panel adjudication packet

**Review SHA:** `53efbf69` (pinned; master moved to `3649d237` mid-sweep, docs-only — no finding invalidated)
**Corpus:** the character subsystem as it stands — `games/sonic4/player/*.emp` (12 files, 5,770 lines),
`data/characters/*`, `data/animations/*`, `objects/{dust_puff,dust_spindash,tails_appendage}.emp`,
plus the engine seams the character work reaches into.
**Panel:** the ratified roster — A · A2 · B1 · B2×2 · C1×2 · C2×2 · C3×2 · C4×2 · C5 · V.
15 read-only seats, corpus-scale (×2 walk pairs fully doubled, opposed walk orders).
**Adjudication:** every load-bearing citation below was independently re-verified by the overseer.
Two seat claims were **corrected** (see §5); they are recorded rather than dropped.

---

## 1. What this sweep changes about the picture

The character work is structurally sound. Seat A found registration ceremony genuinely
clean (all 13 `PSTATE_*` rows present in all three dispatch tables with `.count` guards;
"Knuckles made every registration Tails made"). Seat A2 spot-checked ~20 S3K citations and
~25 arithmetic claims and found them **all true**. Seat C4b confirmed five divergences from
S3K as deliberate and *better* than the reference. The abstraction held: Knuckles' five
states cost one `cd_ability` pointer and zero branches in the shared frame.

Three things are not sound, and they compound:

1. **Two confirmed player-visible bugs** shipped, plus one latent and two minor.
2. **A critical determinism bug** (`Ctrl_1_Held`) that is a strong candidate root cause for
   the open replay desync on master.
3. **There is no automated safety net under any of it**, and the nets that appear to exist
   are vacuous. This is why 1 and 2 shipped.

Item 3 is the finding that reframes the rest. It is ranked first below.

---

## 2. Confirmed defects, ranked

### D1 — `Ctrl_1_Held` is clobbered mid-tick by lag VBlanks · CRITICAL
**Seats:** C3b · **Verified:** overseer, full chain

```
controllers.emp:34    move.b d0, Ctrl_1_Held           ← raw live-pad write
controllers.emp:37    or.b   d3, Ctrl_1_Press_Accum    ← Press accumulates; Held does NOT
vblank.emp:329        VInt_Lag: jbsr Read_Controllers  ← runs on EVERY lag VBlank
replay.emp:194        move.b d0, Ctrl_1_Held           ← playback writes it at tick top
player_climb.emp:208  "Ctrl_1_Held is frame-stable (VInt latches it once per tick)"  ← FALSE
```

`Ctrl_1_Press` is genuinely tick-stable: accumulated across lag frames, latched consume-once
in `VInt_Level`. `Ctrl_1_Held` is **not latched at all** — every VBlank, lag included,
overwrites it from the live pad.

Under playback the pad is untouched, so the live read is `$00`: **any lag frame silently drops
all held input for the remainder of that tick.** Character code re-reads `Ctrl_1_Held` at 11
points spread through the tick, so half a tick can run on stream input and half on a dead pad.
Guaranteed divergence, not a "if the pad differs" risk.

`replay.emp:122` claims this exact class (S1 REV00 / S2 input-bleed) was "killed structurally."
It was killed for Press. The Held half was never done and the comment reads as though both were.

**Fix:** give Held the same accumulate-then-latch treatment Press has — publish
`Ctrl_x_Held` in the `VInt_Level`-only latch block (`vblank.emp:237-245`), keeping a raw
`Ctrl_x_Held_Raw` for the IRQ's own edge detection. Then correct `player_climb.emp:208`.

**Why it matters beyond replay:** in live play this is a rare one-frame inconsistency where two
halves of one tick disagree about a held direction. Under replay it is deterministic breakage.

---

### D2 — No automated coverage of the character subsystem, and the harness cannot acquire any · HIGH (process)
**Seats:** V · **Verified:** overseer

`Debug_CharacterHotkey` (`ojz_scroll_test.emp:514`) is the **only writer of `Character_ID`**
in the tree. Its first gate:

```
tst.b   Input_Source
bne     .done          // replaying or recording: stand down
```

`Character_ID` is boot-zero = `CHAR_SONIC`. Under playback a replayed `A` cannot cycle the
character; under record a session cannot capture a cycle. **Every replay fixture, present and
future, runs as Sonic — by construction.**

Therefore `PSTATE_FLY`, `GLIDE`, `GLIDEFALL`, `SLIDE`, `CLIMB`, `LEDGE`, both ability hooks,
the per-character palette/physics/box/DPLC paths and `TailsAppendage_Refresh` have **zero**
automated coverage and cannot acquire it through the existing harness. The planned fixture
re-record will go green and change none of this.

Compounding, verified separately:
- `test.sh` asserts **nothing** about player behaviour; `games/sonic4/test/` holds scenes, not assertions.
- The replay net is **currently red on master** regardless.
- `verify_sprites.py:138` reads `data/dplc` — **does not exist** (real path `games/sonic4/data/dplc/`).
  `if dplc_dir.exists():` is False → the whole DPLC half (entry counts, **tile-indices-within-art-bounds**)
  is skipped, `all_ok` stays True, `test.sh` prints **"PASS: Sprite & DPLC verification."**
- `test.sh:80-110` has the same dead path; its `else` branch is `echo "  SKIP"` — calls neither
  `pass_test` nor `fail_test`, so it contributes nothing to totals and emits no failure signal.
  Knuckles was never in the loop (`for char in sonic tails`).
- `art/uncompressed/characters/` has **no `knuckles.bin`**. Even with paths fixed,
  `verify_sprites.py:177` sets `art_count = 65536` when no art matches — disabling the bounds
  check that is the tool's entire purpose.
- `player_common.emp:1174` asserts "the replay fixtures hold" — a prediction promoted to fact,
  never run, now known false.

**This is why D3–D6 shipped.** Every one of them lives in the blind spot.

---

### D3 — DPLC entry budget is at 12/12 with no guard; 13-entry frames are in the shipped blob · HIGH
**Seats:** C3a, C3b (opposed walks) · **Verified:** overseer parsed the blobs independently

`DMA_IMPORTANT_SLOTS = 12`. `perform_dplc` costs **one Important queue slot per DPLC entry**.
No `ensure` anywhere binds entry count to slot count — `dplc_peak_tiles` measures *tiles*, and
`knuckles_data.emp:114` says so explicitly.

Overseer parse of the shipped blobs (same walk as `dplc_peak_tiles`):

| blob | frames | peak tiles | **peak entries** |
|---|---|---|---|
| `optimized/sonic.bin` | 224 | 29 | **13** (frames 193, 200) |
| `knuckles.bin` | 251 | 29 | 5 |
| `optimized/tails.bin` | 251 | 24 | 2 |
| `optimized/tails_tail.bin` | 45 | 9 | 1 |

Sonic entry histogram tail: `10:6, 11:2, 12:2, 13:2`.
Script-reachable worst: **frame 196 (`$C4`) = 12 entries**, and `LookUp: [5, $C3, $C4, AF_BACK, 1]`
**holds** that frame while UP is held. 12 entries into 12 slots = **zero margin**.
(Frame 14 also carries 12 entries but is not reachable — `Walk` uses 7,8,1-6; `Run` uses `$21-$24`.)

Two in-tree comments assert safety and are both false and mutually inconsistent:
- `dplc.emp:10` — "DPLC_Sonic frames legitimately carry up to 6 entries"
- `knuckles_data.emp:22` — "well inside DMA_IMPORTANT_SLOTS ... (DPLC_Sonic carries up to 13)"

**Live today:** on the frame the look-up pose is entered the Important queue is 100% player, so
`PageIn_EnqueueLanding` is deterministically dropped — a streaming stall landing exactly when the
camera pans up and demands pages.
**Latent and permanent:** if a 13-entry frame is ever scripted or a re-export shifts entries,
`perform_dplc` enqueues 12, drops the 13th, and bails **before committing `prev_frame`** — so it
re-enqueues all 12 every frame forever. The 13th entry's tiles never load. Art streaming stops dead.
**Reachable today:** the byte budget can compact one entry into the next frame, turning the 12/12
case into the permanent case (C3b's arithmetic).

**Fix:** add `dplc_peak_entries()` beside `dplc_peak_tiles` in `engine/objects/dplc.emp` (same
parser, return `max(entry_count)`), and `ensure(dplc_peak_entries(_dplc_x) + RESERVE <= DMA_IMPORTANT_SLOTS)`
per character module with `RESERVE >= 2` (page landing + its possible 128 KB split). `sonic.bin`
fails that today at 13 — which is the point. Then re-page it in `tools/dplc_layout.py`.
Correct the two false comments.

**Related (C3a #3):** a DPLC entry whose ROM source crosses a `$20000` boundary splits into two
queue entries and `.split_reject` needs **two** free slots or rejects both halves. Character art
totals ≈353,632 B ≈ 2.7 × 128 KB, so ≥2 entries across the cast are guaranteed to cost 2 slots.
Fold into `RESERVE`, or `$20000`-align the `Art_*` blobs.

---

### D4 — Skid dust spawns through the entire jump arc · HIGH (release, Sonic, ordinary play)
**Seats:** C2a, C2b (opposed walks) · **Verified:** overseer

`PlayerV.skid_latch` has exactly one clear (`player_common.emp:896`, `.skid_drop`), and it sits
*below* both `btst #ST_ROLLING` (`:836` → ball branch `rts` at `:851`) and `btst #ST_IN_AIR`
(`:855` → `.walk_or_run`). Nine state-keyed branches return before ever reaching it.
`Dust_Tick` reads the latch guarded by **nothing but a `PSTATE_SLIDE` check**
(`dust_spindash.emp:85-90`).

**Repro (3 inputs):** run right to `|gsp| >= PHYS_SKID_MIN` → hold Left (latch arms, dust correct)
→ still holding Left, press jump.

**Observable:** ground dust puffs trail the whole jump arc, one every 4 frames, until landing
*and* releasing the opposing direction. Same leak for skid→roll, skid→spindash (puffs pile under
the charging player), and for Knuckles skid→jump→glide. Tails skid→jump→flight emits ~120 puffs
over 8 seconds; at 16 frames' life each that permanently occupies ~4 of 16 `NUM_EFFECTS` slots
and starts silently dropping other effects.

**Why gates miss it:** the stuck latch is *deterministic*, so a fixture hashes green; the
consequence is Effect-pool objects, and the pool is outside the hash entirely.

**Fix:** make the latch honest — clear it at the top of `Player_Animate` before the state
dispatch and let `.skid_show` re-`st` it (one writer, contract restored). Belt-and-braces
alternative: gate `Dust_Tick`'s skid leg on `!ST_IN_AIR && !ST_ROLLING`.

---

### D5 — Left-wall glide catch always fails · HIGH (Knuckles)
**Seats:** C2a, C2b (opposed walks) · **Verified:** overseer, incl. the S3K reference

Both `Air_WallProbeRight` (`player_air.emp:707`) and `Air_WallProbeLeft` (`:725`) do
`clr.w x_vel(a0)` on a hit. `GLF_PUSH_BIT` is set *only* on that hit edge. The path is tight
with no intervening `x_vel` write:

```
player_glide.emp:120    jbsr Glide_Collide     // comment: "snaps + zeroes on contact"
              :124-125  btst #GLF_PUSH_BIT,d0 / bne .hit_wall
              :153      jbra Knuckles_Gliding_WallCatch
player_climb.emp:492    tst.w x_vel(a0) / bmi .left_wall    ← x_vel is ALWAYS 0 here
```

So `bmi` is never taken and Knuckles **always faces right** at a wall catch. `Climb_WallDist:135-143`
reads that facing to pick its probe side, so a left-wall catch probes rightward into open air, gets
the `+32` sentinel on both corners, fails the both-flush test, and drops to `GLIDEFALL`.

**Left-hand walls are un-grabbable. Right-hand walls work by accident** — which is why nine rounds
of manual playtest passed: a right-wall test shows the feature working perfectly. And per D2, no
fixture can ever reach Knuckles.

S3K does not use velocity here (`sonic3k.asm:30776`, verified):
```
        move.b  double_jump_property(a0),d0    ; = our PlayerV.glide_angle
        addi.b  #$40,d0
        bpl.s   .right
;.left:  bset   #Status_Facing,status(a0)
```

**Fix (S3K-faithful, 4 instructions):** discriminate on `PlayerV.glide_angle` (`0` = right,
`-$80` = left; `+$40` splits them exactly), which is still live and correct at that point.
`PlayerV` is already imported in the module.

**Second site, same root (C2b F2b):** `player_glide.emp:158-163` `.hit_floor` derives landing
facing from the same zeroed `x_vel` — a corner landing slides facing right regardless of travel.

---

### D6 — `Slide_Terrain` consumes a quadrant-rotated probe as a fixed +Y distance · IMPORTANT (latent)
**Seats:** B2a, C2a, C4b (three walks) · **Verified:** overseer, incl. the S3K reference

```
player_glide.emp:478   jbsr Player_SensorFloor    // rotated by PBLK_QUADRANT
              :483-484 dist_to_fix(d0) / add.l d0, y_pos(a0)   ← always +Y
              :485     move.b d3, angle(a0)       ← feeds next frame's quadrant
```

`Player_SensorFloor` → `Player_SensorSurface` probes along the **quadrant's** down
(`player_sensors.emp:309`, `d7=0`). Entry to `PSTATE_SLIDE` *is* gated flat, but nothing keeps it
flat: `Slide_Terrain` rewrites `angle` from the floor every frame and `Player_Main:583-587`
re-derives the quadrant from it next frame. `PBLK_QUADRANT` has only two writers — `Player_Main`
and `player_air.emp:297` (`clr.b`, air path only) — and **`PSTATE_SLIDE` does not route through
`Air_Collide`**, so nothing zeroes it here.

Every other `Player_SensorFloor` consumer either routes through `Player_SnapToSurface` (which
mirrors the quadrant case table) or forces the quadrant to 0 first. `Slide_Terrain` does neither.

S3K's slide floor-follow is `sub_11FD6` → `Sonic_CheckFloor`, a plain **fixed downward** probe, so
its `add.w d1,y_pos` is axis-consistent by construction.

**Observable once a slide reaches terrain past ±45°:** wrong-axis snap (player pops through the
surface) or a spurious ledge-drop out of the slide while visibly on the ground.

**Fix:** `clr.b PBLK_QUADRANT(a4)` at the top of `PState_Slide` — the `Air_Collide` idiom, one
instruction, and truthful (the slide's terrain model *is* fixed-down like S3K's).

---

### D7 — The glide family has no ceiling handling at all · IMPORTANT (Knuckles)
**Seats:** C4b · **Verified:** structure confirmed; behavioural claim rests on the S3K read

`Glide_Collide` runs left wall, right wall, floor — **no upward probe**. `Slide_Terrain` likewise.
S3K's `Knux_DoLevelCollision_CheckRet` (`sonic3k.asm:32629`) dispatches on the motion class and
**three of its four classes probe the ceiling and eject downward**. A glide is `x_vel` up to `$1800`
against a parachuted `y_vel` of `$80` — it is in a horizontal class essentially always, so the
ceiling probe is on S3K's hot path, not an edge case.

Gliding into a rising overhang, the centre-height wall probes miss and nothing notices the head
entering solid terrain. The parachute guarantees `y_vel >= 0`, so it cannot self-correct.
Compounds with D9, which can push the head *into* a ceiling with no probe to see it.

**Fix:** add a ceiling probe to `Glide_Collide` (quadrant forced to 0), ejecting downward on
`dist < 0` and clamping `y_vel >= 0`.

---

### D8 — `Glide_Collide`'s single-centre floor probe rests on a false S3K claim · IMPORTANT
**Seats:** C4b · **Verified:** overseer (the reference read)

`player_glide.emp:315-325` justifies abandoning the A/B floor pair with: *"S3K's glide floor check
(sub_11FD6) is likewise a single CENTRE sensor."* `sub_11FD6` is a one-line trampoline into
`Sonic_CheckFloor`, which runs `FindFloor` **twice** — at `x±x_radius` — and keeps the nearer.
The claim does not survive reading the reference.

Behavioural cost: `Glide_Collide` is shared with `PState_GlideFall`, where the pair spread is the
point. Falling beside a platform lip, `PState_Air` lands ~10 px earlier than `PSTATE_GLIDEFALL`
does — an inconsistency inside our own engine that S3K does not have.

The bug it was introduced to fix is real but misdiagnosed: `PUSH_RADIUS` (10) equals Knuckles'
ability-box `x_radius` (10), so after a wall snap the outer floor sensor lands exactly on the snap
point and the probe cores treat that pixel as inside the wall column.

**Fix:** restore the A/B pair and close the actual cause (bias post-snap floor sensors inward 1 px,
or make the wall snap leave the probe point one pixel clear). If the centre probe is kept, the
comment must state what it really is — a deliberate divergence working around a flush-boundary
overlap, with the landing-window cost named.

---

### D9 — `PHook_AirEnter` applies a 9 px lift on mid-air ability-box exits; S3K applies none · MINOR
**Seats:** C4b

All three mid-air 21→39 box restores (glide release, slide ledge-drop, wall-catch fail) route
through `PHook_EnsureStanding`, which computes `(39-21)>>1 = 9` and does `sub.l d2, y_pos(a0)` —
an instantaneous 9 px teleport with **no head-clearance check**. All three S3K sites restore the
radii and touch `y_pos` not at all; S3K applies the shift only on the two *grounded* landings,
where "feet planted" is a real constraint.

Knuckles-only (for Sonic/Tails this hook is a `.keep` no-op on air entry). Our matching behaviour
on the two grounded exits is correct and should stay (C4b confirms it as *better* than S3K there).

**Fix:** a no-shift variant for the ability→standing air case, or add the A7-style clearance guard.

---

### D10 — Minor state-leak riders
**Seats:** C2a

- **`Air_LandOnObject` doesn't clear the cached quadrant** before `Air_LandState`'s ceiling probe
  (`player_air.emp:92-94`, `:420-423`). Landing on a solid object while carrying a steep angle
  makes the stand-vs-stay-rolling decision from a *horizontal* clearance reading.
  Fix: `clr.b PBLK_QUADRANT(a4)` as the first instruction of `Air_LandOnObject`.
- **`ST_PUSHING` survives the whole glide/climb chain** — cleared only by the ground wall probe and
  the airborne landing helpers, none of which the four Knuckles landing paths pass through. One
  frame of `ANIM_PUSH` on touchdown. Fix: `bclr` once in `PHook_GroundEnter`, which all four reach.

---

## 3. Vacuous / wrong-subject gates (fix these regardless of D-list scope)

| # | Gate | Defect | Seats |
|---|---|---|---|
| G1 | `player_climb.emp:121` `ensure(CLIMB_RADIUS == PLAYER_X_RADIUS + 1)` | Binds the climb probes to **Sonic's standing radius**, not `KNUX_ABILITY_RADIUS`. Holds only by the 9+1==10 coincidence. Set `KNUX_ABILITY_RADIUS = 11` → box grows, all six probe offsets stay at 10, **build stays green**. | **A, A2, B1, B2a, V (5 seats)** |
| G2 | `PBLK_*` offsets | 21 hand-rolled offset consts across 8 files, **5 `ensure`s** — 16 unguarded. `PlayerBlock`'s own doc says declaring it a type is "what makes the layout invariants **structural** instead of merely checked"; the consts convert it back, then don't check most of them. | A, B1, B2a |
| G3 | `verify_sprites.py:138` + `test.sh:80-110` | Both read a path that does not exist → skip silently → report PASS / contribute nothing. Knuckles in neither. | V |
| G4 | `knuckles_data.emp:96-101` | Tests palette **agreement**, not **grayness**; re-export both in lockstep and the dust turns that colour for every character while all three ensures pass. Not roster-scoped — a 4th character adds a blob nothing checks. | V |
| G5 | `sonic/tails/knuckles.emp:85/115/134` | `ensure(8*2 == offsetof(PlayerBlock, quadrant))` names `PhysTable_X` but its condition never references it. Append a 9th row → silently dropped, all three pass. Fix: `sizeof(PhysTable_X)`. | V |
| G6 | `constants.emp:325-326` | Message names a neighbour the condition restates as a literal. Low risk (generated), but the idiom is available one file over. | V |

**Cheap unenforced invariants worth adding** (seat V, §C): `CLIMB_CLAMBER_END == sizeof(Climb_ClamberFrames)`
(a 5th clamber step silently re-runs the bug-2 soft-lock); `cd_palette != 0` for every roster record
(currently guaranteed only by a manual emulator round-trip); **positional** gates on the three state
tables (the `.count` guards are cardinality-only — swap two rows and every gate passes while dispatch
calls the wrong handler; `tails_anims.emp:233` already does this correctly 25 rows deep); a DEBUG
assert that the Sonic-unreachable ability scratch really is zero (it is the fixtures' load-bearing
premise and nothing checks it); `jump_headroom == 0` at tick end (stated as MUST, unchecked).

---

## 4. Structural / quality findings (no bug today)

- **`Player_Animate` dispatches `player_state` with a 7-deep `cmpi.b` chain** next to three
  `offsets` tables keyed on the same byte. ~92-112 cycles/frame on the common path; grows by
  ~16 cycles/frame for *every* ability state added, charged to characters that can never reach it.
  Seats B1, C1a, C1b, C4a (4 seats). Fix: a 4th `offsets` table.
- **Dead prologue**: `Player_Animate` computes the `$800` walk hold every frame; the ball path
  unconditionally recomputes it from `$400` and spindash returns without reading it. ~70 cycles
  wasted on *every curled frame*, i.e. every airborne jump frame. Seats C1a, C1b.
- **Jump-button + debug-fly gate open-coded ×7** across five files. The masks are centralised;
  the eight-instruction sequence consuming them is not, and every ability parcel adds a copy.
  Seats B1, B2a, B2b, C5, C4a (**5 seats**). C4a's framing is the right one: it is *input policy*
  and belongs resolved once at the boundary, not re-decided per consumer.
- **Probe preamble reimplemented 5-6×**, and the missing "single probe, explicit point, known
  direction" rung has a **defect record**: `player_climb.emp:272` documents `move.w d0,d1` fixing a
  case where the angle's dirty high byte was added to `y_pos` and *"hurled the player through the
  floor to the level bottom"* — and notes the sibling copy already had the fix while this one did
  not. The cores alias in/out registers (`d0/d1` both ways), so every open-coded caller must
  remember to defend. Seats B2a, B2b, C4a.
- **~293 bytes of duplicated fallback animation rows** across four tables — the same 10-byte body
  written 24 times, because `offsets` has no alias form. Grows as (new ability anims) × (characters).
  Seats B2a, C5, C4a.
- **`Player_Chardef` is a single global read from 16 sites** while `PlayerBlock` is properly
  per-slot. Not a bug (nothing initialises `Player_2`), but it is an *undeclared* blocker of the
  CPU-follower/2P work sitting beside two ledgered ones, and it grew by four sites during C4.
  At minimum it should be ledgered in `DEFERRED_WORK.md`. Seats C4a, C2b.
- **The "ability scratch union" is documented but not implemented** — and `ARCH:1861` declares the
  overlay-headroom question **CLOSED** on "26 of 30 bytes used." Verified: **5 of those 26 are dead**
  (`flip_angle`, `air_left`, `invuln_time` unreferenced; `status_secondary`, `look_offset`
  write-only). True live usage is 21. Reclaiming them takes headroom 4 → 9 bytes; a real union
  takes it to ~11. **The closed ruling stands on dead data.** Seats C5 + C4a (overseer synthesis).
  Caveat: `$30..$4D` is the hashed replay window — any reshuffle is a fixture event.
- **Comment truth**: seat A2 filed 28 findings. The dangerous ones: `player_glide.emp:291` says
  `Glide_Collide` uses `Player_SensorFloor` while `:316` in the *same block* says it deliberately
  does not; `player_climb.emp:511` calls a `y-11` probe the "bottom-far corner" (it is the top) and
  anyone "fixing" the sign breaks the wall catch; `player_air.emp:305` claims d3/d4 hold velocities
  that the wall probes have overwritten; four headers claim work is unshipped that shipped
  (`knuckles.emp:11` "HIS ABILITY IS NOT WIRED YET" vs `:90` `Ability_KnuxGlide`).
- **`muls.w` ×5 on per-frame paths behind `// lint: disable=E002`** — a pragma **no tool reads**
  (`s4lint` follows `.asm` includes only; `game_root.asm` includes one file). The maths is likely
  correct (S3K spends the same `muls.w`); the defect is governance. Seats A, C1a, C1b.

**Perf items worth their own parcel:** interleave `SolidityTable`/`AngleTable` into one 512-byte
word table (~20 cyc/non-air cell, 2-4 cells/frame; costs a `d6` convention change across ~9 sites);
`Ctrl_1_Held`/`Press` as one aligned word read (~34-38 cyc/frame); quadrant derivation is dead work
on every airborne frame (~50 cyc).

---

## 5. Seat claims the overseer CORRECTED

Recorded so they are not re-litigated from the raw seat output.

1. **C5's RAM reclaim is wrong.** It claimed 10 bytes RAM from deleting dead `PlayerV` fields and
   4 more from pad removal. `PlayerV` is `vars PlayerV: Sst.sst_custom` — an **overlay into a fixed
   32-byte window** (`structs.emp:82`, inside `struct Sst (size: $50)`). Deleting fields reclaims
   **0 bytes of RAM**. The real reclaim is ~8 bytes of ROM (two dead `clr.b` writes) and the true
   value is the *headroom* reframing in §4. Reclassified minor.
2. **B2a's `Slide_Terrain` finding was filed critical; carried as important-latent.** The mechanism
   is fully confirmed, but reachability requires a slide to follow terrain past ±45° before friction
   ends it, which no seat demonstrated on OJZ geometry. Real, one-instruction fix, not proven live.

**Baseline correction found by the sweep:** `DEFERRED_WORK.md:508` states Tails' flight SFX
`$BA`/`$BB` are unwired. **They are wired** — `Fly_TickSfx` (`player_fly.emp:368-381`) tail-jumps
`Sound_PlaySFX`, called from `PState_Fly` step 1b. `player_fly.emp:16` repeats the false claim.
This is a stale entry in the doc checked at the start of every planning phase.

---

## 6. Confirmed-good — do NOT "fix" these

Seat C4b measured these against S3K/S.C.E. and confirmed our divergence is better:

- **Dust art is VRAM-resident**, so S3K's `air_left < 12` drowning interlock (a pure VRAM-budget
  workaround) is correctly *absent*. Copying it would import a hardware constraint as a gameplay rule.
- **The Tails appendage takes its own priority band** rather than inheriting the parent's: our
  `Render_Sprites` reverses intra-band order on odd frames, so S3K's co-banding would flicker here.
- **The climb's idle floor probe preserves the animation delta.** Stock S3K clobbers it — the
  documented cause of *"Knuckles resets to his first climbing frame when not holding up or down."*
  skdisasm only fixes it behind `if FixBugs`. We never had the defect.
- **`mask_opposing_lr`** resolves L+R-held to neither; S3K applies both accelerations in one frame.
- **A glide landing on a slope keeps the feet planted** (the grounded half of D9) — S3K sinks
  Knuckles 9 px and relies on the next floor pair to recover him. Ours is correct on the landing frame.

Seat A also confirmed registration ceremony is complete and correct across all three characters,
zero `.s`/`.w` violations, zero AS-era spellings, and all 23 indexed-addressing sites sanitized.

---

## 7. Suggested execution order

1. **D1** (`Ctrl_1_Held` latch) — engine-side, and it likely unblocks the replay re-record that
   everything else's verification depends on. Do this first for that reason.
2. **G3** (the vacuous test-tooling gates) — cheap, and it is how D3 gets caught next time.
3. **D4, D5, D10** — self-contained player-visible fixes, small diffs.
4. **D6, D3** — one-instruction fix and a comptime guard respectively; D3's guard will fail the
   build until `sonic.bin` is re-paged, so land the guard and the re-page together.
5. **G1, G2, G5** + the cheap `ensure`s from §3 — one guards parcel.
6. **D7, D8, D9** — the glide-family terrain work; these interact and want one parcel with a
   deliberate S3K re-read.
7. **§4 structural items** — separate parcels, each byte-changing (repin/refreeze ritual).
8. **D2** — the coverage hole. Needs a design decision (how does a fixture select a character?),
   not just a fix.

**Ritual note:** most of the above are byte-changing and carry the frozen-table / repin / refreeze
`--ab` obligations, and aeon+sigil must move as a pair.

---

## 8. Status — what shipped on `review/character-lens-sweep`

Owner-selected scope for this session: **D1 + G3 first**, with D3's guard landed as a
non-fatal ratchet rather than a hard assert.

| Item | State | Notes |
|---|---|---|
| **D1** `Ctrl_x_Held` latch | **FIXED** (`11dbf25f`) | Raw IRQ shadows at the RAM tail; `VInt_Level` publishes. Verified symbol-by-symbol that **no existing engine-RAM address moves** (only `Engine_RAM_End`, +4). **Runtime verification OWED.** |
| **G3** sprite/DPLC gates | **FIXED** (`f36b13ff`) | Manifest of the pairs the ROM actually embeds; 13 pairs checked incl. Knuckles; missing input is now a FAIL. Proven it can fail. |
| **D3** entry budget | **GUARDED** (`de2d8618`) | `dplc_peak_entries()`; real guard on knuckles/tails/dust, ratchet at 13 on Sonic. Comptime-only, CRC unchanged. Re-page still owed. |
| Stale docs | **FIXED** (`0873f8a2`) | Flight-SFX correction; CHAR-1..8 booked in `BUGS.md`. |
| D2, D4–D10, G1/G2/G4–G6, §4 | **OPEN** | Booked in `BUGS.md` as CHAR-1..CHAR-8. |

### Two things the next session must not inherit as "done"

1. **D1 is not runtime-verified.** The single oracle instance was in use by the
   effects-P3 lane for the whole session, so it was never taken. D1 is verified by
   build (3 shapes), by emitted-symbol inspection, and by a writer/reader audit —
   **not on the emulator**. The specific claim still owed: that a lag VBlank landing
   mid-tick no longer changes `Ctrl_1_Held`. Whether it also closes the master replay
   desync is a *hypothesis*, not a result.
2. **The optimized-art reproduction gate is parked, not fixed.** Repairing the dead
   paths made it run for the first time and it does not reproduce the committed
   artifacts — different algorithm, not drift (regenerated sonic art is 122,272 B /
   3821 tiles against the committed 97,472 B / 3046, and the committed blob is
   *smaller* than its own 3425-tile source, i.e. deduplicated, while the tool
   *expands*). `dplc_layout.py` is not the producer. Which tool is, and whether the
   committed artifacts should be regenerated by it, is an owner question; until it is
   answered the compare sits behind `DPLC_REPRO=1` and prints a KNOWN GAP line every
   run. Do not read the green `test.sh` as covering it.

### Pre-existing failures noticed in passing (not caused by this branch)

`./test.sh` on an unmodified `53efbf69` tree fails `OJZ strip generator self-tests` and
`ROM build` — identically, with or without this branch. Same disease as G3: red gates
nobody is watching. Worth a look, out of scope here.
