# SONIC-SLOPE-COLLISION: why Sonic stands on slopes and will not roll (2026-09-26)

Branch `research/sonic-slope-collision`, cut from `origin/master` at **`91d4119c`**.
Owner, playing the Sonic 2 clip act (`S2CLIP=s2_ehz_cpz`, Emerald Hill then Chemical
Plant): *"I think there's something wrong with how sonic interacts with slopes or the port
of the collision, I can stand on random things or don't just start rolling when I try to
it's weird."* Then, of a Chemical Plant screenshot: *"I was coming down here in ball and just
got stuck and can stand instead of rolling down more. this just like was wrong."*

Every number below is MEASURED on a headless emulator (the repo's `aether_instance` Rust
core, never the MCP server) unless it says READ (from source). Probes live beside this file.

## Answer in one table

| | Reproduced? | Cause | Fixed? |
|---|---|---|---|
| (a) stands on things he should not | **Yes**, three spots (two in CPZ on the clip, one on canonical OJZ) | **Engine physics port.** Air landings read the floor through the GROUNDED sensor wrapper, whose angle policy snaps any surface more than $20 from the player's current angle to the cardinal. In the air that angle is 0, so every landing on a $20-or-steeper surface became a FLAT landing (angle $00, gsp = x_vel), and the grounded follow then kept the angle at 0 forever. | **Yes**, `49b371f9` |
| (b) pressing down does not start a roll | **Yes** on a slope (the (a) state: standing at gsp 0, down is a duck); on flat ground the engine matches S3K exactly | The slope case is (a). On flat ground the rules are S3K's, which are stricter than the Sonic 2 the owner was playing: roll needs \|gsp\| ≥ $100 (S2: $80) AFTER a frame of friction, and any held left/right vetoes it (both games) | The slope case, yes (same fix). The flat-ground rules are a feel choice: options below |
| clip collision data wrong? | **No** | n/a | n/a |

**It is not the clip.** The collision the clip act carries is Sonic 2's, pixel for pixel
(20,407 solid blocks compared, 0 differences), and the defect reproduces on canonical OJZ.
The clip shows it far more because Sonic 2's terrain is steep: **58** exposed steep
(≥$20) top blocks in the clip act's plane A (Emerald Hill 19, Chemical Plant 39) against
**1** in the whole OJZ act (x 1072..1087, row y 528, the loop's ramp foot).

## Hypotheses, and what each forbade

* **H1, the clip's collision import is wrong** (heights, angles, index mapping, the wrong one
  of S2's two paths, solidity bits, flips). Forbids reproducing on OJZ, and predicts
  disagreement between Sonic 2's own FindFloor and our cell words at the stuck spot.
  **Refuted, measured both ways.** `s2_collision_equivalence.py` re-implements S2's
  `Find_Tile` (s2.asm:42894) and `FindFloor` (:42942) over the raw donor files and compares
  every 16-px block of both clip rectangles, path 0 to plane A and path 1 to plane B, on
  presence, top/LRB solidity, the angle byte (after S2's own flip arithmetic) and all 256
  floor-class pixels: **161,024 block-paths, 20,407 solid, 0 differences in every column.**
  Controls show the comparison can fail: ignoring X flip gives 3,157 angle / 1,267 pixel
  differences, ignoring Y flip 723 / 345, swapping the paths 3,122 presence differences.
  (Scope: this checks the donor-to-cell-word step, the one this hypothesis names. The
  word-to-ROM-attr step is the build's own bake-fidelity lane, `verify_level_bin.py`, green on
  every clip build here; and the runtime landing angles below, $28/$2C/$30, are the data's.)
* **H2, the physics port deviates from S3K/S2.** Predicts the same failure on OJZ wherever
  the same geometry exists. **Confirmed** at OJZ's one steep block.
* **H3, it is debug free-flight's leftovers.** Every drive here leaves free flight with a
  real B press, then pins the player, so none of these runs carries flight state. READ:
  `Player_DebugExit` (player_common.emp) enters `PSTATE_AIR` with all three velocities
  cleared, but keeps `angle` and `layer` from before the flight. After the fix a landing no
  longer reads `angle` at all, so the stale angle only decays harmlessly in the air
  (2/frame). The stale layer cannot matter on this clip today (the player never leaves
  layer A: no plane switchers, per the loops/planes research), but it WILL once switchers
  exist: fly from a plane-B stretch to a plane-A one and you land on plane B's collision.
  Booked, not measured.

## Symptom (a), measured

### The spot

The owner's picture (as relayed: grey machinery on the left, a quarter pipe on its right
face sweeping down to the floor, a row of white blocks at the floor, a striped pillar and a
lattice tower to the right) best matches, by my reading of a render of the donor tree, **Chemical Plant x 2432..2496, y 960..1024** (act
x 13792..13856, y 1216..1280): a 64x64 quarter pipe, shapes 37..31 X-flipped (angles
$3C..$04) plus the full-block-at-45° shape 251 (angle $20), at the bottom of a 128-px
machinery block whose top is act y 1152. The loops/planes research matched the same
description to a second quarter pipe, **CPZ x 3216..3330, y 960..1150** (act x 14576..14690),
shapes 82..73 with three shape-252 blocks. A description cannot pick between them, so both
were driven; the defect is the same at both.

### The drive and the result

`slope_probe.py` boots the clip DEBUG ROM, presses B, pins the player, then releases him.

**Roll off the block top** (act x 13700, feet 1152, gsp $300, DOWN for 3 frames): he rolls
to the edge, leaves it at x 13799, hits the upper block's hanging pillar at x 13814 (x_vel
522 -> 0, a real wall: act x 13824..13855 is solid down to y 1151 on both planes), and
falls straight down onto the quarter pipe:

| frame | ROM | y | x_vel | y_vel | gsp | angle | state |
|---|---|---|---|---|---|---|---|
| 76 | baseline `91d4119c` | 1243 | 0 | 0 | 0 | $00 | GRND, and every frame after (13+ logged) |
| 76 | fix `49b371f9` | 1243 | 0 | 1792 | 1792 | $28 | lands; then runs the pipe: $28 -> $20 -> $18 -> $10 -> $04 -> $00, reaching x 14016 at gsp 1541 thirty-three frames later |

**Straight drop onto the second pipe** (act x 14610, feet start 1300, nothing held):
baseline lands at y 1333 with angle $00, gsp 0, and stays (logged to frame 33); the fix
lands at angle $30, gsp 1288 and runs down ($30 -> $18 in 11 frames). With DOWN held from
frame 12: baseline lands standing at gsp 0 and never curls; the fix lands straight into
`ROLL` at gsp 1553 and rolls out at 1879.

**Canonical OJZ** (`DEBUG=1 ./build.sh`, drop at x 1080 from feet 470): baseline lands at
y 518 with angle $00, gsp 0 and stands on the loop's ramp foot for the rest of the log;
the fix lands at $2C, gsp 1472, and runs down it (crossing to layer 1 at x 1154 through the
loop's own crossover, as that loop is authored to).

### The cause (READ, then confirmed by the fix)

`Air_FloorLandBanded` and `Air_FloorLandFlat` (player_air.emp) called
`Player_SensorFloor`, which resolves the angle with the grounded policy: odd flag **or
\|surface − SST_angle\| ≥ $20** → substitute the quadrant cardinal. That second rule is
Sonic 2's `Sonic_Angle` (s2.asm:42649) and S3K's `Player_Angle` (sonic3k.asm:18854): the
per-frame GROUNDED follow, where it is the loop fall-through guard. Neither classic lands
through it. Both land through `Sonic_CheckFloor` (s2.asm:43564, called at :37570, :37644,
:37722; sonic3k.asm:19843 via `sub_11FD6`, called by `SonicKnux_DoLevelCollision`
:24039), which takes the nearer sensor's angle raw and substitutes 0 for the odd flag only
(sonic3k.asm:19890-19893).

In the air `angle` decays toward 0 by 2 a frame, so by touchdown it is 0 (or near it), and a
surface of $20 or steeper fails the ±$20 window: angle $00. Then:

1. the landing bands read $00 as FLAT: gsp = x_vel, y_vel = 0 (a vertical fall, x_vel 0,
   lands at gsp 0);
2. every grounded frame after that runs the same wrapper with `angle` = 0 against the real
   $20..$3C surface, fails the same window, and substitutes $00 again. The state is
   self-sustaining: the player stands on a 45° slope with no slope factor, forever;
3. down does nothing, because \|gsp\| is 0 (a duck, not a roll): symptom (b)'s slope case.

The Knuckles glide landing already had this right: `Glide_Collide` substitutes the cardinal
on the odd flag only, and its comment (player_glide.emp) and a DEFERRED_WORK ruling (owner,
2026-08-28: *"match S3K"*) say in as many words that S3K has no divergence rule on any
airborne landing path. The ordinary air landing was the one that did not follow it.

### The fix (`49b371f9`)

`Player_SensorLand` is the floor pair with the landing policy: `d7.b = $80` rides the same
body (the `& 3` quadrant arithmetic ignores bit 7), and the resolver's
`cmpi.b #2,d7 / beq .keep` became `tst.b d7 / bne .keep`, so the ceiling pair (d7 = 2) and
the landing pair (d7 = $80) both get odd-flag-only resolution while the grounded pair (d7 =
0) keeps the divergence snap. `Player_SensorFloor` and the new entry share one body
(`Player_SensorFloorAs`, which keeps the solid-object short-circuit for both). The two air
landings call `Player_SensorLand`. Nothing else changes: the grounded follow, spindash
charge and Knuckles' slide still call `Player_SensorFloor`.

**Deliberately not changed: Knuckles' `Slide_Terrain`.** It is the same class in S3K (the
slide reads the floor through `sub_11FD6`, sonic3k.asm:30998) and still uses the grounded
policy here. It is not a Sonic symptom, the slide's quadrant is forced to 0 every frame, and
changing it moves Knuckles' slide on slopes in a way nobody measured. Booked.

### The check (`337beedc`)

`tools/slope_landing_witness.py`, wired into the keepalive lane
(`tools/keepalive_manifest.toml`, `[wired."slope_landing_witness.py"]`, expect 0). It
derives its subjects from the COMMITTED act (exposed top blocks in the landing code's own
steep band, `(angle + $20) & $40`, with a clear drop above both foot sensors: one on OJZ)
and a flat control beside them, drops the standing player onto each, and requires a steep
landing to keep the surface's sign, have downhill gsp and move downhill, and a flat landing
to read $00 and stay put. Red-first on disk: the committed baseline's two player files
(`git checkout 91d4119c -- games/sonic4/player/player_sensors.emp
games/sonic4/player/player_air.emp`), built, run: **exit 1**, `L1 STEEP ... landed f17
angle $00 gsp 0, x 1080 -> 1080`, C1 passed; restored with `git checkout HEAD --`, rebuilt:
**exit 0**, `L1 ... angle $2C gsp 1064, x 1080 -> 1122`, `C1 ... angle $00 gsp 0, x 1176 ->
1176`. Through the runner: `keepalive_lane.py --only slope_landing_witness.py` reports
FAILED on the baseline ROM and PASSED on the fix. 5 s wall at load average ~20. Exit 2 on
an empty subject set, a player who never lands, a fault, a bus refusal, or a landing on
the wrong layer.

## Symptom (b), measured

Flat Emerald Hill ground (act x 400), gsp injected, then DOWN held (or DOWN+RIGHT) for 6
frames, fix ROM:

| injected gsp | DOWN alone | DOWN + RIGHT |
|---|---|---|
| $80 | GRND (gsp decays to $50) | GRND |
| $C0 | GRND | GRND |
| $100 | GRND (friction takes it to $F4 before the check) | GRND |
| $180 | **ROLL** | GRND |
| $400 | **ROLL** | GRND |

That is S3K to the letter (READ: `SonicKnux_Roll`, sonic3k.asm:23227: no roll while left
or right is held; `cmpi.w #$100`; the check runs after `Sonic_Move`'s friction). Sonic 2
differs in the threshold only: `Sonic_Roll` (s2.asm:36954) rolls from **$80**. So on flat
ground the engine does exactly what the project's S3K baseline says; a player who learned
Sonic 2 meets a stricter game in two ways:

* between $80 and about $10C (walking pace) S2 rolls and this engine ducks;
* **left or right held vetoes the roll, in both classics.** On a keyboard, holding RIGHT
  to run and tapping DOWN is two keys held: no roll, in Sonic 2 too. This is the most
  likely everyday "I pressed down and nothing happened", and it is reference behaviour.

Also S3K rather than S2, and relevant to "can stand instead of rolling down more": a roll
uncurls at \|gsp\| < $80 (S3K `Sonic_RollSpeed`, sonic3k.asm:22981 `cmpi.w #$80,d0`),
where Sonic 2 uncurls only at exactly 0 (`Sonic_RollSpeed`, s2.asm:36710 `tst.w inertia(a0)`). Not a
defect; a difference the owner will feel on the S2 clip.

### Options for the flat-ground feel (owner's call; nothing here is built)

| | What | Cost |
|---|---|---|
| A | Keep S3K (today). | None. The S2 clip feels slightly stricter than Sonic 2. |
| B | Sonic 2's $80 start threshold engine-wide (`PHYS_ROLL_START_MIN`). | One constant, but it is shared by three gates (the ground roll start, the landing's roll pick in `Air_LandState`, and the spindash-vs-jump gate in `PState_Ground`), so the spindash window moves too. A registered S3K divergence. |
| C | DOWN wins over a held left/right once \|gsp\| is past the threshold. | A divergence from BOTH classics; kills the "run with down+forward held" behaviour both have. Mostly a keyboard-comfort change. |
| D | A per-act physics profile (S2 rules for S2 clips). | A design: the constants become per-act data. Only worth it if more S2 content is coming. |

## Overlap with the loops/planes research

The player never leaves layer A on this clip (no plane switchers), and the loops/planes
research (master `3f573f88`, `docs/research/2026-09-26-s2clip-loops-planes.md`) reports S2
is also on its path 0 at the second quarter pipe. So "standing on the wrong layer's
collision" is not what happened at either spot: both reproductions are on plane A, where
S2's own path 0 agrees with our plane A block for block (above). Once plane switchers
exist, the debug-exit layer leftover (H3) becomes a live way to stand on the wrong plane.

## Also noticed, not a cause

* READ, pre-existing and already noted in `docs/research/player-sensors-sce.md` §3.1: the
  probe distance is `16 − h − sub` where both classics use `$F − (h + sub)`, so a player at
  rest has his feet one pixel lower than Sonic 2's. Uniform everywhere, so it cannot make
  him stand on one spot and not another. Not booked again.
* The build's tool suite failed once here on `EDQUOT` writing under `/tmp` (a disk quota,
  not the code); rerun with `TMPDIR` on the home disk, green.

## Landing evidence

* `tools/landing_build.sh` at `10c2c327` (TMPDIR on the home disk): **`finished=0`**; pre-build
  pytest 3,522 passed, 3 skipped; `needs_build` lane: all 34 reachable marked tests passed,
  1 EXEMPTED (`test_deb2_appendix[demo.bin]`, a shape the script does not build).
* CRCs, baseline `91d4119c` player files vs the fix (FAST builds of the baseline, canonical
  builds of the fix): `s4.bin` 828,920 `0cd3ce63` -> 828,952 `036807a4`; `s4.debug.bin`
  855,585 `1ff17f52` -> 855,619 `c7859dbb`; `demo.debug.bin` 105,426 `5e110699` unchanged
  (the demo carries no player code). Both Sonic 4 shapes move by +32/+34 bytes.
* Full (non-FAST) clip builds on the fix, `S2CLIP=s2_ehz_cpz` plain and `DEBUG=1`: exit 0
  each, every clip lane included. The plain clip ROM (no free flight) repeats the fixed
  landing at act x 14610: angle $30, gsp 1288.

## Open (booked in docs/DEFERRED_WORK.md, SONIC-SLOPE-COLLISION)

1. Knuckles' `Slide_Terrain` still uses the grounded angle policy (S3K: landing policy).
2. The roll-start feel options A-D (owner ruling).
3. Debug-fly exit keeps `angle` and `layer`; harmless today, a wrong-plane landing once
   plane switchers exist.

## Files

* `slope_probe.py` - scripted per-frame drive (research probe, no runner).
* `s2_collision_equivalence.py` - S2 FindFloor vs the clip's cell words (research probe;
  `noxflip` / `noyflip` / `swappath` arguments are its controls).
* `tools/slope_landing_witness.py` - the check, keepalive lane.
