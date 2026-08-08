# Harmony Framework study (2026-08-07)

Read of **Harmony Framework** (UltraRing) — `github.com/UltraRing/Harmony-Framework`,
cloned to `docs/research/external/harmony/` (gitignored; upstream, not vendored).

A modern accuracy-focused classic-Sonic framework in **GameMaker Studio 2 / GML**,
~19.5k lines. **No code transfers.** It was read as a source of design decisions, a
feature checklist, and a bugfix catalog — its authors did the classic-Sonic archaeology,
then chose what to keep, fix, or add. The decisions are the transferable part.

Evidence files: [`player.md`](2026-08-07-harmony/player.md) ·
[`framework-tooling.md`](2026-08-07-harmony/framework-tooling.md) ·
[`render-effects.md`](2026-08-07-harmony/render-effects.md)

---

## Two framing assumptions I got wrong going in

1. **"Their float physics won't port."** Wrong. Harmony's physics is **8.8 fixed-point
   written in decimal** — every constant is n/256 (0.046875=`$C`, 0.21875=`$38`,
   0.3125=`$50`). Only three spots need true division (peelout `/2.9`, audio pitch,
   sub-step count) and all are shiftable. No porting obstacle at all.

2. **"It's modern, so expect GPU-era ideas."** Wrong in the opposite direction. Harmony is
   unusually *un*-modern: nearly every effect it ships is a GPU re-creation of a specific
   VDP technique. `shd_line_scroll` **is** the per-line HScroll table. `shd_line_dist`
   **is** our deform table (same 256-entry signed table, same
   `(line + time + offset) mod N` sampling). `shd_color_replacer` is CRAM palette swapping
   done the hard way because GameMaker has no indexed color. It reads as a careful
   transcription of the hardware, which is *why* it is useful to us.

---

## Where we are ahead (useful negative results)

Recorded so these do not get re-litigated:

- **State machine.** Their `state` is a bare function pointer with **no enter/exit hooks**;
  every transition site hand-patches its own consequences, and the hitbox is keyed off the
  *animation*, not the state (`player_util.gml:436-483`). We have hooks and a single
  transition writer.
- **S3K fidelity — we beat them in 8 catalogued places.** Their slip band is 45° not `$18`;
  they omit the S3K downhill nudge entirely; **no roll-jump air-control lockout**; no
  uncurl-into-ceiling guard; no L/R veto on roll start; push sensors at +4 instead of +8;
  unroll at exactly `gsp==0` instead of 0.5; air drag lacks the classic truncation.
- **Object management.** Their culling is an O(all objects) unsorted per-frame walk vs our
  X-sorted ratchet + 2×2 window + hysteresis + idempotent bitmasks. Their persistence is an
  unbounded instance-id list vs our 3×3 bitmask window.
- **Engine/game separation.** Essentially nonexistent — `instance_util.gml:88` hard-codes
  `obj_player`. Ours is a typed `implement Game` contract.
- **Animation.** Plain frame/duration table vs our behavior sequencer.

## The cautionary find

**`no_skid_state` — the config flag documented as making skidding "closer to the genesis
games" — is never read anywhere in the repo.** Their skid is still a 24-frame Mania-style
timer sub-state. Two other "hacky fix" timers are dead the same way.

A config flag claiming a behavior is not evidence the behavior exists. This is the same
failure mode as our own arch doc claiming palette cross-fade had shipped
(see `project_alignment_audit_2026_07_15`), and a direct argument for `ensure()` discipline.

---

## Defects this exposed in our code

| # | Finding | Confidence |
|---|---|---|
| 1 | **Roll animation runs at half speed.** Classic (and Harmony) use `8-\|gsp\|` for walk/run but **`4-\|gsp\|` for roll/ball**. ~4 instructions in `Player_Animate`'s `.ball` path | **Confirmed by inspection (2026-08-07)** — see below |
| 2 | **Deform phase is screen-anchored, not layer-anchored.** Harmony anchors the deform sample index in the *layer's* space (`obj_aaz2_water_effect/Create_0.gml:36,62` — `cy` for FG, `cy*(1-2/3)` for BG). Ours slides against the art on vertical scroll. ~3 instructions, shipped system | Verified by agent, not re-checked here |
| 3 | **Camera does not compensate for `CURL_Y_SHIFT`.** Harmony carries an explicit `camera_rolling_offset = [5,1,5]`, exactly our 5px curl shift | **Half-confirmed (2026-08-07)** — see below |

### #1 confirmed, with a mechanism correction

The agent's cite pointed at where the hold is *computed*; the actual data path is an
out-parameter. Chain verified end to end:

- `Player_Animate` computes `d3 = max(0,($800-|gsp|))>>8` once
  (`player_common.emp:403-411`) — `$800` is 8.0 in 8.8, i.e. the classic `8-|gsp|`.
- It is an **out-parameter**, not consumed locally: `player_common.emp:392` documents
  `Out: ... d3.b = dynamic per-anim hold`. The `.ball` path (`:425-427`) just sets
  `ANIM_ROLL` and returns — it never touches `d3`.
- `AnimateSprite` substitutes the caller's `d3` wherever a script's duration byte is the
  `DUR_DYNAMIC` sentinel (`engine/objects/animate.emp:54-61`,
  `engine/system/constants.emp:73`).
- **`Walk`, `Run` *and* `Roll` are all `DUR_DYNAMIC`** (`sonic_anims.emp:37-39`).

So one `8-|gsp|` hold drives all three, and the ball spins at half the classic rate. The
in-code comment at `player_common.emp:399` already says "walk/run/roll" share it — the
divergence was written down at the time and never questioned. Fix belongs in the `.ball`
path (halve `d3` before `rts`).

### #3 half-confirmed — the "should we" half is still open

**Confirmed:** there is no compensation. `CURL_Y_SHIFT` appears in `player_common.emp`,
`player_ground.emp`, `player_air.emp` and `constants.emp` — and **nowhere in
`engine/level/camera.emp`**, which tracks `Sst.y_pos(a0)` directly (`camera.emp:294`).
Since the curl/uncurl hooks shift `y_pos` by ±5px (`player_common.emp:669,679`), the
camera target moves 5px on every curl and uncurl.

**Still open:** whether it *should* compensate. Harmony is a Mania-lineage framework, and
our baseline ruling is S3K (memory: `feedback_s3k_baseline_not_s2`). S3K may well shift
the camera target too and simply accept it — in which case matching Harmony here would be
a deliberate deviation from classic feel, not a bug fix. **Resolve against skdisasm before
touching this.**

## Gaps confirmed in code (not in the doc)

- **No fade of any kind. No title card. No act transition.**
- **`HBlank_Install` has zero consumers** — the entire §7.2 raster command table is unbuilt
  and `sec_raster_table` has no reader.
- `sec_pal` / `sec_pal_cycle` have no consumer. `Camera_Pan_Offset` is write-only
  scaffolding. `sec_camera_lookahead` has no reader.
- No screen shake, no look-up/down pan, no moving camera limits.

Harmony is ahead of us on transitions and camera polish **only because it built them** —
none of it required a GPU.

---

## Ranked candidates

### Player (§5 territory — our player is early, so structural ideas land cheap)

1. **Immediate-mode capability flags** (`player_states.gml:5-15`) — reset 7 permission bits
   each frame; states re-assert what they need. Kills the "state forgot to clean up" bug
   class outright. **One byte + a `move.b`.** [WORTH TAKING]
2. **Post-dispatch cross-cutting condition block** (`player_state_conditions()`) — one home
   for transitions belonging to no single state. A free `jbsr` after our dispatch.
   [WORTH TAKING]
3. **Shield descriptor record.** Theirs is a dispatch array + one `shield_state` byte, but
   shield *identity* is enum-tested in five files (damage, aquaphobia, dropdash gating, and
   insta-shield is not a shield at all). Recommended replacement: a 4-field descriptor
   record, same shape as our existing hook tables. [WORTH TAKING — as the fix for their
   mistake, not a copy of their design]
4. **Per-character dispatch-table indirection before any Tails code exists.** They get the
   data tables right (physics struct-of-arrays, hitbox arrays, per-character anim registry)
   but fork control flow inline — four `if (character == ...)` branches inside one shared
   jump state. Strongest validation of our spec §3.1. [WORTH TAKING — sequencing advice]

Rejected: sub-stepped movement (our `$1000` cap already bounds motion to cell size);
heightmap-derived angles and wall-probe-driven mode switching (6+ extra probes/frame to
solve what our odd-flag + divergence-snap covers); their input-after-collision frame order.

### Rendering (VDP-feasible)

1. **Per-band linear scroll-factor ramp** — the one *capability* they have that we lack.
   `shd_line_scroll.fsh:24-27` computes `OffsetX * (1 + floor(y/LineGaps)*YSteps)`: a linear
   ramp of scroll factor down a strip, authored as two endpoint factors plus a height
   (`obj_aaz_bg_inside/Create_0.gml:29`, whose comment explains it makes the water's top
   match the horizon and its bottom match the foreground — the S3K HCZ look). Our bands are
   flat (`configs.emp:38-51`) so we stack 5 to fake a gradient. **Zero extra DMA** (still
   896 B), one `add.w` per line, and it sidesteps our shift-add factor set having only 14
   representable fractions. [WORTH TAKING]
2. **Marker-relative rebase** — best idea in the repo, no shader involved.
   `obj_act_transition` stores player, camera, camera bounds, signpost, monitors **and every
   parallax layer's scroll residue** relative to a marker object, then re-solves them against
   the next act's marker (`background_util.gml:129-143`). Zero parallax discontinuity across
   an act boundary. Structurally the same trick as our teleport/floating-origin rebase,
   applied to *presentation* state — exactly what the mega-act corridor seams need. Our
   `Parallax_StartTransition` only lerps or snaps; neither preserves on-screen position.
   [WORTH TAKING — authoring + engine]

Rejected as impossible, with the hardware reason: full-frame capture and re-warp (no
readable framebuffer — but the *effect* survives via per-line HScroll, which is what S3K
does; consequence: their warp also warps sprites and ours cannot, though a per-sprite X
offset sampled at the sprite's Y is a cheap partial); bounded water pools via palette split
(a raster CRAM swap is full-width by construction; S/H on low-priority tiles is the only
bounded substitute and gives half-brightness, not a blue shift); per-object arbitrary
palettes (CRAM is 4 lines × 16); 3D LUT color grading (meaningless at 64 colors — though it
does corroborate our §7.1 computed-water-palette instinct).

### Dev tooling (points at Oracle/Aurora more than Aeon)

1. **Mouse-picked command arguments** (`obj_shell/Create_0.gml:62-70`, `Step_0.gml:284-305`)
   — a command declares "arg 2 is a world X" or "arg 1 is the instance under the cursor" and
   the console live-fills from the mouse. Oracle has the framebuffer, the camera, and
   `emulator_object_list`, but nothing resolving a screen click to a game-space value.
   **Zero ROM cost, highest-leverage single idea in the repo.** [→ Oracle]
2. **Slow-motion / fast-forward** (`obj_dev/Step_1.gml:59-60`, two lines). Oracle has
   instruction-granular stepping but no *continuous playback at a controlled rate with input
   live* — precisely the tool for the recurring "verify render/scroll DURING motion" problem
   (see memory: `feedback_verify_during_motion`). [→ Oracle]
3. **`obj_script_trigger`** — one 15-line placeable object, two editor properties
   (`script_to_execute` function-typed, `trigger_once` bool). Every set piece (water rise,
   camera lock, boss entry, music change) collapses into one primitive instead of a new
   object type each time. We have all the ingredients (per-section type tables, subtype byte,
   trigger flag array) and none of the shape. [→ Aeon + Aurora]
4. **In-ROM dev menu with declarative registration** (`dev_util.gml:13-59`) — level select is
   one line per entry; the auto-enumerated "every room" category is a nice trick. Removes a
   rebuild from every "look at act 2" loop. The live-tunables half is more expensive for us
   (most of our constants are comptime immediates, not RAM). [→ Aeon, DEBUG shape]

Rejected: `file_bin_util` (95 lines of dead code with a sign-extension bug, aimed at caching
runtime-baked collision maps — a problem our build-time embedding already solves); global
suspend-with-allowlist (a GameMaker workaround with no analogue); their 30 Penner easing
curves (should become 4-6 build-time LUTs — runtime evaluation is impossible under
no-`mulu`/no-`divu`).

---

## Two cross-checks worth running

1. **Sine table.** `math_util.gml:118-129` (`__trig256_build`) independently re-derives the
   Mega Drive sine table *including* the `*512`→truncate→`>>1` rounding **and four
   hand-corrected cardinal entries**. Diff against our generator — if we disagree, one of us
   is wrong about the hardware table.
2. **`dont_reset_frame`** (animation change preserving frame phase) may not be expressible in
   our system given the `prev_anim = $FF` change-detection convention. Worth confirming
   before it is assumed available.

## Hardware archaeology (unexpected bonus)

Their Blue Sphere engine is a verbatim port of Mania's tables, which are transitively S3K's
(`stage_bss_engine.gml:162` says so). `palette_page` / `palette_line` are **vestigial Genesis
names** that now index a sprite flipbook: 2 pages × 16 cycle steps = **exactly** the 32-frame
length, and `Draw_0.gml:78` offsets the sphere depth row by `palette_line`.

That is direct evidence **S3K's special-stage floor moved entirely by CRAM cycling on a
static plane**, and that projected sprites had to share the phase counter. The geometry is
four integer LUTs indexed by a depth row 0..111 and ports to 68000 almost line-for-line
(~9% of a frame in DIVUs; the divisor is already table-indexed, so a reciprocal makes them
MULUs). Only the 5.9 MB of pre-rendered art does not port.
