# Recon — "getting the first thing we see to be the floating shadow water thing"

> **Correction, 2026-11-17 (review before landing).** Three points in this recon are wrong or have been overtaken. (1) WATERLINE-OFF-READING was not open when this was written. It had been answered "gone" by the hub at 2026-09-09T23:43:39Z (34c18f0c). (2) ParallaxConfig_OJZ_Underwater was not bound only to section 0. Section 5 also bound it, as the d-53 loan (`ojz_effects.emp:1665-1675` at 60846831), so the wavy band was not unique to section 0. The section-0 identification (F1) still holds, because the act starts in section 0. (3) The owner's sentence turned out to be Reading B, a complaint. The controller acted on Reading A, put the two tokens back unlanded in the owner's tree, and the rebuild-first launcher then reproduced the waterline in every build until it was reverted (49b613fa). The waterline stays off on master. The stale-ROM diagnosis below is correct, and master confirms it (`docs/lane-log.jsonl` entry at 2026-09-10T03:05:53Z: the ROM was built at 20:52Z, before a422e7bc at 21:36Z). Read option (a) as the action that misfired, not as a recommendation.

Research only. Nothing here was built, no emulator was run, and nothing outside this file
was touched. Dispatched 2026-09-09; the filename carries the date the controller asked for.

Every claim below is marked **[verified]** (I read the bytes or the lines myself, in this
tree, this session) or **[relayed]** (I am repeating what a file or a commit says).

---

## F4 — THE TRAP. It is the same effect he switched off, and he has never seen it off.

**Plainly: the thing in the screenshot is the thing that was turned off at 17:36 today.
Not a cousin of it. The identical two records, at the identical screen line, in a ROM
that predates the switch-off.**

The argument, in four steps, each independently checkable.

### 1. No ROM anywhere in this tree has the waterline off. [verified]

`EffectsPreset` is `(size: 46)` with `ep_patch_world_ys` at `$1C` and `ep_patch_motion` at
`$26` (`engine/effects/preset.emp:57,66,86`). Reading those fields straight out of every
built ROM in the tree:

| ROM | mtime | `OJZ_Preset_Sec0` addr | `patch_world_ys` | `patch_motion` |
|---|---|---|---|---|
| `s4.bin` | 2026-09-09 05:07 | `$1454C` (`s4.lst:4413`) | `(224, 314, 32767, 32767)` | `($4100, 0, 0, 0)` |
| `s4.debug.bin` | 2026-09-09 16:52 | `$1503A` (`s4.debug.lst:5394`) | `(224, 314, 32767, 32767)` | `($4100, 0, 0, 0)` |
| `.claude/worktrees/agent-aae99358d58004445/s4.debug.bin` | 2026-09-09 18:56 | `$1503A` | `(224, 314, 32767, 32767)` | `($4100, 0, 0, 0)` |

`$4100` decodes through `anchor_sweep`'s own packing —
`(amp_shift << 12) | (period_shift << 8) | phase`, `engine/effects/raster_dsl.emp:2282` —
as **amp_shift 4, period_shift 1, phase 0**. That is character-for-character the retired
value the comment block at `ojz_effects.emp:1440` says to put back.

The switch-off is `a422e7bc`, **2026-09-09 17:36:12**, merged `ea29abaa` at 18:01. The two
canonical ROMs both predate it. The one worktree ROM that postdates it
(`parcel/palette-authored-seed`, built 18:56) does **not** contain `a422e7bc`
(`git merge-base --is-ancestor` says LACKS) [verified]. I searched the whole tree for any
`s4*.bin` newer than 17:30 and found exactly that one.

So: **there is no build in existence, here, in which section 0's waterline is off.** The
owner's screenshot cannot be a picture of the new state. He is looking at the old one.

The switch-off's own decision card says the same thing from the other side, and says it
unprompted — `docs/decisions.jsonl`, card `WATERLINE-OFF-READING`, filed 22:16:11Z
[verified, quoted]:

> "NOBODY HAS SEEN IT ON SCREEN: derived from the suppress branch and PATCH_ANCHOR_NONE's
> contract, not observed."

### 2. Section 7's waterline cannot produce this picture. [verified]

The only other live waterline in the act is section 7's. It differs from section 0's in
every attribute the screenshot description names:

| | **section 0**, channel 0 | **section 7**, channel 2 |
|---|---|---|
| Shadow/Highlight | **ON** — `sh: 1`, and the trailer replays `$8C89` = VDP reg $0C S/H on (`ojz_effects.emp:1938,2044`) | **OFF** — `sh: 0` (`ojz_effects.emp:2166`) |
| CRAM entries swapped | line 2, entries **4,5,6** | line 2, entries **3,4,5** |
| variant bound to slot 0 | `Variant_Water_Deep` = `variant(shift_r:1, shift_g:1)` — halve R+G. The file's own measurement: on this palette it comes out "DARKER BROWN" and "the palette half was nearly invisible" (`:2131-2135`) | `Variant_OJZ_Water` = `variant(shift_r:1, bias_g:-1, bias_b:4)` — blue-dominant (`:1312`) |
| sweep | amp 4 = **±16 px**, period 1 = 8.53 s | amp 5 = ±8 px, period 0 = 4.27 s |
| parallax overlay | `ParallaxConfig_OJZ_Underwater` **bound** on the preset | `parallax:` **deliberately unbound** (`:1750-1755`), falls to `ParallaxConfig_OJZ_Default` |
| wavy per-line deformation | **yes** — see step 3 | **no** |

Section 7 has **no shadow** and **no wave**. The screenshot has both. It is not section 7.

### 3. Where the "scalloped/wavy" and the "much darker" each come from — and they ride the same anchor. [verified]

This is the part that makes the trap tight, because it means the switch-off removed
*three* visible things off one value, not one.

`OJZ_Preset_Sec0` binds `parallax: ParallaxConfig_OJZ_Underwater`. That scene
(`games/sonic4/data/effects/ojz_scenes.emp:238-330`) is bound **only here** — its own
comment says section 0 is "the only section that binds this config and the only one with a
live patch channel". Its layer 1 carries:

```
layer(world_y: 1024, fa: FACTOR_1, fb: FACTOR_1_2, dsa: 15, dsb: 15,
      rowRemap: SceneRemap.Ladder(RowRemapLadder_Waterline16, 101, 4)),
```

and the scene's `anchor: SceneAnchor.At(0, 15, 0)` "writes dsb 0 into every band from the
split down, against `DeformTable_Shimmer`" — `deform_sine(amplitude: 8, period: 32)`, i.e.
**a ±8 px per-line horizontal wave, 16 px peak to peak** (`ojz_scenes.emp:291-303`). The
split is on **patch channel 0** — the same latched line as the tint band.

So one anchor drives all three:

1. **the dark region below** — `sh: 1` puts the VDP in Shadow/Highlight from that scanline
   down, so the same art renders at half brightness;
2. **the wavy/scalloped band** — plane B below the split gets the shimmer deformation plus
   the waterline row-remap ladder, which is a per-line horizontal displacement, i.e. the
   only thing in this act that can make a horizontal boundary read as anything other than a
   perfectly straight line;
3. **the palette swap** on line 2 entries 4,5,6.

`ojz_effects.emp:1450-1456` states the coupling explicitly [relayed, and consistent with
what I read in `ojz_scenes.emp`]: "the `parallax:` band split, which reads the SAME latched
line, goes off-screen with it."

The merge commit `ea29abaa` flags the same coupling as the reason it ran the gate ritual:
"ParallaxConfig_OJZ_Underwater anchors its band split on the very channel removed …
which the returning agent had not flagged and which would have been visible on camera."

**Caveat I will not paper over:** I can account for *wavy* and for *dark below* from source.
I cannot prove from source alone that the boundary row reads specifically as *bright
yellow-green*. The brightest entry on CRAM line 2 is `$06EA` = (R5,G7,B3) — a bright
yellow-green — and it sits in the foliage ramp (entries 9..15), which the tint does **not**
swap and which S/H therefore shadows below the line and leaves bright above it
[verified from `games/sonic4/data/generated/ojz/act1/ojz_palette.bin`; note the blob's rows
are CRAM lines 1,2,3, so "line 2" is the file's second 32-byte row]. A row of that foliage
smeared by the remap's compression at the top of the band is the mechanism I would bet on,
but **that is a hypothesis, not a measurement** — see TAG-1.

### 4. So what does his sentence mean?

His words are genuinely two-way, and the difference decides the parcel:

* **Reading A — he wants it.** "Getting the first thing we see to be the floating shadow
  water thing" = a goal. He is pointing at something he likes and asking that it be the
  opening image. Under this reading, `WATERLINE-OFF-READING` should be answered `other`
  and the two tokens go back.
* **Reading B — he is naming the complaint.** The same gerund phrase can describe the
  present, unwanted outcome: *what's happening is that the first thing we see is the
  floating shadow water thing* — which is exactly the "dark and distracting right now" he
  said before. Under this reading the landed change already grants it and the screenshot is
  the evidence for the complaint, not a request.

**Both readings agree on the identity claim.** Whatever he wants done, the object he is
pointing at is section 0's channel-0 waterline, live in his ROM, removed on master. There
is no third effect to go find.

I flag two things about Reading B. First, it is the reading the controller already took
once, and the card exists precisely because he took it *without asking* — "I inferred his
answer rather than asking" (`7764ea10`). Taking it a second time, on a second ambiguous
sentence, on the strength of the first inference, is how a wrong reading gets laundered
into a settled fact. Second, "floating shadow water thing" is affectionate naming, not
complaint vocabulary; "dark and distracting" was the complaint vocabulary. That is a weak
signal, and I offer it as one.

**Recommendation on process, not on the look:** this is one question to him and it costs
nothing — the card `WATERLINE-OFF-READING` is already open and already offers `gone` /
`still` / `other`. His screenshot is arguably an answer to it. Ask which.

---

## F1 — Which section produces the picture: section 0.

The geometry closes it independently of everything above.

* Act start is **section 0** — `OJZ_Act1_Descriptor` has `start_sec_x: 0, start_sec_y: 0,
  start_local_x: $0100, start_local_y: $0100`
  (`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:163-169`) [verified].
* `Sec[0].sec_effects` = `OJZ_Preset_Sec0` (`act_descriptor.emp:239,252`) [verified].
* Camera Y at spawn = `start_local_y - CAM_SCREEN_HALF_H` = `256 - 112` = **144**
  (`engine/level/camera.emp:166-171`, `CAM_SCREEN_HALF_H = 112` at
  `engine/system/constants.emp:541`) [verified — and this is the same $0090 the effects file
  records as measured on oracle].
* Channel 0's screen line = `anchor - Camera_Y` = `224 - 144` = **80**, on a 224-line
  screen. **80/224 = 35.7% — "roughly a third of the way down the screen."**
* The sweep at amp 4 carries it ±16 px, so 64..96; `ojz_scenes.emp:255` records it measured
  on the shipped build as `Effects_Screen_L[0]` "sweeping 93 -> 75 unattended".

The controller's description of the screenshot — band a third down, same art darker below —
is reproduced by section 0's numbers with no fitting. No other section is a candidate: only
sections 0 and 7 install a patched program at all (`RASTER_MAX_PATCH` is 4, "section 0 uses
two of them and section 7 uses the other two, and no section installs both programs",
`ojz_effects.emp:2091`), and section 7 is ruled out in F4 step 2.

**What would have to be true for it NOT to be section 0:** the owner would have to have
navigated to section 7 (reachable — 3×3 grid, section 7 is row 2 col 1) *and* section 7's
palette-only, shadowless, waveless blue boundary would have to be what "shadow" and
"scalloped" describe. I do not think that survives contact with the byte evidence.

---

## F2 — Where the act starts, and whether `boot_override_gate` matters here.

**Start position, named:** `games/sonic4/data/levels/ojz/act1/act_descriptor.emp:163-169` —
`start_local_x: $0100`, `start_local_y: $0100`, `start_sec_x: 0`, `start_sec_y: 0`.
Section size is `1 << SECTION_SIZE_SHIFT` = 2048 px (`engine/system/constants.emp:358`), so
the spawn is world (256, 256), inside **section 0**, flat id 0. [verified]

**Consumers:** `engine/level/camera.emp:155-171` derives the boot camera from
`start_sec_* << SECTION_SIZE_SHIFT` plus `start_local_*` minus the screen half-extents.

**On the `boot_override_gate` note the controller carried:** the claim is **correct and
still true**, but it is about the *override* path, not the authored one, and it does **not**
matter for this parcel. `tools/boot_override_gate.py:442-443` [verified, quoted]:

> "select must read the section containing the DESTINATION rather than the authored
> `Act.start_sec_x/y`."

That gate exists to prove a `Boot_At_X/Y` override streams the destination section rather
than the authored one. Nothing in this parcel touches the override; the owner is looking at
an ordinary authored boot. **Where the note *does* bite is option (b) — see F3.**

---

## F3 — The two ways to grant it, priced.

### (a) Bring the effect to the section the act starts in — **it is already there.**

Because the act starts in section 0 and the effect *is* section 0's, option (a) is not a
migration at all. It collapses to **reverting two tokens** — the exact inverse of `a422e7bc`,
which touched **one file, 33 insertions / 3 deletions, and of those only two lines are code**
[verified from `git show a422e7bc --stat` and the diff].

In `games/sonic4/data/effects/ojz_effects.emp`, `OJZ_Preset_Sec0` (~line 1516):

```
patch_world_ys: [PATCH_ANCHOR_NONE, ...]   ->  [224, ...]
patch_motion:   [ANCHOR_MOTION_NONE, ...]  ->  [anchor_sweep(amp_shift: 4, period_shift: 1), ...]
```

**ROM bytes:** 4 bytes change **in place** — `+$1C` (`$7FFF` -> `$00E0`) and `+$26`
(`$0000` -> `$4100`) inside a fixed-size 46-byte record. **Nothing moves.** No symbol
shifts, no size changes, no `EndOfRom` movement, so no re-layout. [verified — derived from
the struct layout and the ROM reads above.]

**Gates and fixtures — what does NOT go red:**

* `tools/effects_gates.py`'s three sparse scenes (`mid_band`, `suppressed`,
  `above_screen`) **poke `Effects_World_Y` themselves** before capturing —
  `tools/scenes/effects_raster_mid_band.json` pokes `Camera_Y 144` and
  `Effects_World_Y 244`, and `derive_arms` reads `pokes["Effects_World_Y"]`
  (`tools/effects_gates.py:681`) [verified]. The preset *seed* is not their subject.
* Their bands come from the `patchable(ch:, lo:, hi:)` calls in the game source
  (`tools/effects_gates.py:769-785`) [verified]; those did not move and will not.
* `tools/row_remap_gate.py` reads `pcfg_anchor_ch` / `pcfg_anchor_dsb` out of the config
  record statically [verified]; independent of the seed.
* `tools/fixtures/anchor_sweep/*` resolve bands through `sec == 0 -> OJZ_Preset_Sec0 ->
  OJZ_TwoChannel` [verified — every one of the four guards on `sec == 0`]. The `patched:`
  binding was **deliberately kept** through the switch-off for exactly this reason, so the
  revert leaves them where they are. Restoring the sweep *gives back* the real-array arm its
  live subject, which is the state those tests were written against.
* `bca32302` and `a56c97e4` fixed `test_anchor_sweep_band` so a zero-band / bandless channel
  is a **report**, not a refusal [relayed from the commit subjects]. Those fixes are
  content-direction-neutral; they do not need reverting.

**Band fit, re-derived rather than copied:** seeded screen line 80, amplitude ±16, so the
excursion is 64..96. Channel 0's band is `lo: 3, hi: 220` (`ojz_effects.emp:1940`). 64..96
is comfortably inside — 61 lines of camera travel before the sweep's own peak reaches a
clamp, which is the derivation the file already carries and which I re-checked rather than
trusted.

**What still has to happen:** the effects gate ritual (owner ruling 2026-08-18) —
`python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst` — because the parcel
touches an effects path. The switch-off ran it at 18 PASS / 0 FAIL. **TAG-2.**
Byte-changing parcels in this tree also ride a sigil re-pin / refreeze ritual; I did not
verify whether an in-place 4-byte change with no symbol movement triggers it. **TAG-3.**

**What would BREAK: nothing I can find.** This is a revert of a same-day change, to a state
that had shipped for days.

### (b) Move the act start to where the effect already is — **expensive, and it breaks things.**

This only makes sense under a premise I believe is false (that he means section 7's
waterline). Priced anyway.

**Files:** `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` —
`start_sec_x: 0 -> 1`, `start_sec_y: 0 -> 2` (section 7 = grid row 2, col 1), local X/Y
retained. **ROM bytes:** `Act` is a fixed struct; `ACT_START_SX/SY` are two bytes at `$0C`
and `$0D` (`tools/boot_override_gate.py:153`) — again in-place, nothing moves.

The *arithmetic* actually works out, which is the seductive part: `OJZ_SEC7_CAMERA_Y` is
defined as `(2 << SECTION_SIZE_SHIFT) + 144` (`ojz_effects.emp:1780-1781`), and a spawn at
`start_local_y $0100` in row 2 gives camera `row_top + 256 - 112` = `row_top + 144` —
exactly the value the section-7 anchors were seeded against, which its own banner labels
"⚠ AN ASSUMPTION". The move would make the assumption true. That is the only thing cheap
about it.

**What goes RED — derived, not run:**

1. **`tools/boot_override_gate.py` refuses to run at all.** Its destination is fixed:
   `DEST_X, DEST_Y = 2560, 2400` (`:133`) [verified], which at 2048-px sections is grid
   (1,1) = **section 4**, whose preset `OJZ_Preset_Depth` binds no `parallax:` and so
   resolves to the act default `ParallaxConfig_OJZ_Default`. The gate reads the authored
   section from `Act.start_sec_x/y` in the ROM and, by its own docstring (`:47-52`),
   *"refuses to run (setup error) if those two resolve the same, because then the witness
   could not fail."* Today the authored section is 0 -> `ParallaxConfig_OJZ_Underwater`,
   which differs. Move the start to section 7 — whose `parallax:` is deliberately unbound
   (`ojz_effects.emp:1750`) and therefore also resolves to `ParallaxConfig_OJZ_Default` —
   and control == destination. **SetupError.** Fixing it means moving `DEST_X/DEST_Y`, i.e.
   editing the gate to accommodate the content, which is the shape of thing this repo just
   ruled against (`ea29abaa`: "a check may require that authored content is CORRECT; it may
   not require that particular content EXISTS" — the converse abuse is equally available).
2. **The three sparse effects scenes.** Each is `"reset": true` then `run_frames: 180`
   before any poke [verified, `tools/scenes/effects_raster_mid_band.json`] — so they boot
   into the **authored** start and inherit whatever preset that section installs. Today that
   is `OJZ_TwoChannel`, channels **0 and 1**, which is exactly what `derive_arms` models
   (`bands["ch0"]`, `bands["ch1"]`, `tools/effects_gates.py:679-680`). Boot into section 7
   and the installed program is `OJZ_WorldWater`, channels **2 and 3** — a different
   schedule shape. Three emulator-backed gates lose their subject. This is a **break**, not
   a move: the gates would need re-aiming, and each boots its own headless emulator.
3. **The two committed replay fixtures re-stamp.** `games/sonic4/data/replays/ojz_fixture.bin`
   (1721 ticks, 27 checkpoints) and `ojz_slide_fixture.bin` (2350 ticks, 37 checkpoints)
   (`tools/test_replay_fixture.py:24-29`) [verified] are recorded from the authored spawn.
   Moving it invalidates every checkpoint hash. The re-stamp *"needs the emulator and a
   human"* and *"the net has no automated runner at all, which is how master stayed red
   from the Knuckles C4 merge until 2026-08-13 with nothing reporting it"* — that file's own
   docstring [verified, quoted]. And `test_fixture_structure` asserts exact blob lengths
   because *"the fixture sits before the fault-handler island, so its size moves EndOfRom and
   requires a sigil repin"* — so a re-stamp that changes length drags in the repin as well.
4. **Content, not instruments:** section 7 has *no* `parallax:` binding, so the act would
   open on the plain default parallax with no row-remap and no shimmer, and the opening
   waterline would be section 7's static-colour blue line with no shadow. If the owner is
   pointing at the shadow and the wave, option (b) delivers a screen without either. **That
   is the substantive reason (b) is the wrong lever even if the premise were right.**

---

## What I could not settle

* **TAG-1 — the exact hue of the band. Needs a frame, not a file.** I can derive *wavy*
  (row-remap + `dsb: 0` shimmer) and *dark below* (`sh: 1`) from source. The specific
  "bright yellow-green" I can only attribute to CRAM line 2 entry `$06EA` (R5,G7,B3) in the
  unswapped foliage ramp, rendered unshadowed above the line. **This wants one look at the
  running ROM with `emulator/scanlines` or a screenshot at spawn — foreground work, not
  mine.** It does not change F1 or F4; it would only firm up the mechanism story.
* **TAG-2 — the effects gate ritual.** Any parcel that lands either option must run
  `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst` and paste totals.
  It boots a headless emulator per gate, so I could not and did not run it.
* **TAG-3 — the sigil re-pin question.** I did not establish whether a 4-byte in-place
  change with zero symbol movement still requires the repin/refreeze ritual. Cheap to
  settle; I flagged it rather than guess.
* **The two competing readings of his sentence** (F4 step 4). This is not answerable from
  the tree. It is a question for him, and there is already an open card to hang it on.

## Two things I found that were not asked for

1. **A premise in the brief is wrong, and in the direction that matters.**
   `parcel/sec7-waterline-palette-not-sh` is **merged**, not unmerged — `git merge-base
   --is-ancestor parcel/sec7-waterline-palette-not-sh HEAD` returns true [verified]. Its
   two content commits (`c9b6db23` "the waterline is a PALETTE swap now, and S/H was hiding
   a dead effect", `cdf4a7e6`) are in master and in every ROM listed above. So section 7's
   waterline being palette-only-and-shadowless is *shipped state*, not a pending proposal —
   which is what lets me rule section 7 out of F1 with byte evidence rather than with a
   branch diff. The worktree `agent-a44d4c72c37de27ba` I was told not to check out is not
   where that work lives.

2. **There is an open owner card this screenshot probably answers.**
   `docs/decisions.jsonl`, id `WATERLINE-OFF-READING`, filed 2026-09-09T22:16:11Z, asks
   him exactly this: `gone` (what shipped) / `still` (stops moving, band stays) / `other`.
   Its recommendation is `gone`, and its own detail block admits *"this is an INFERENCE I
   made for you, not an answer you gave"*. If his message is the answer to that card, the
   parcel is not a new decision at all — it is closing an open one, and the record should
   say so rather than opening a second thread beside it. Whatever is decided, that card
   wants updating in the same landing.
