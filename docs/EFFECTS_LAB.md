# The Effects Lab — how to drive it

**One page, for the person holding the pad.** Build `DEBUG=1 ./build.sh`, load `s4.debug.bin`,
and stand still. Everything here is a chord on the pad. None of it exists in the release ROM.

There is **one list** and **one chord** to walk it. Everything the act can demonstrate is in
it, in one order, and the screen names each entry as you pass it.

---

## The two chords

| Hold | Press | What it does |
|---|---|---|
| `START` | `LEFT` / `RIGHT` | step the **one list** — the next / previous thing to look at |
| `START` | `C` | step the **background tile animation** (no direction held) |

That is it. It used to be three separate chords — `START + LEFT/RIGHT` for background scenes,
`START + UP/DOWN` for raster programs, `START + A` for whole section presets — because those are
three different engine slots. **That is a reason that matters to the code and not to you**, so
they are now one list: the twenty-one background scenes, then the raster programs (with *bands
off* among them), then the act's nine per-section presets, and last the waterline strips. Thirty-eight
entries; hold `START` and walk it with `LEFT` and `RIGHT`.

`START + UP/DOWN` and `START + A` do **nothing** now. They are free pad.

The presets are the ones to reach for. A scene changes parallax only and a raster program changes
one channel; a preset installs an entire section's look — palette, palette cycling, palette
variants, the raster or water program, the water anchors and their motion, and the parallax
config — onto the section you are standing in. It is the same operation the engine runs when you
walk across a section boundary, so what you see is what that section really looks like.

**You do not need to know where you are.** That was the whole point. Stand anywhere and walk.

**It undoes itself.** Walk across any section boundary and the section's own effects come back.
Nothing you press here can leave the act mis-configured, and nothing you press here changes what
the game ships.

---

## Reading the screen

Top-left corner, four rows of small yellow glyphs. They appear once you hold `START` or `C`, not
at boot.

```
    HAZE       <- row 1: the ENTRY you are standing on, by NAME
    3 <>       <- row 2: on a PRESET entry only — the section digit and its VERDICT
    BAND       <- row 3: the raster program that is actually INSTALLED
    CMX        <- row 4: the BG tile-animation table that is actually installed
```

**Row 1 is where you are. Rows 3 and 4 are what the machine is doing.** That difference is
deliberate and it is useful: row 1 follows your cursor, rows 3 and 4 are read off the engine's
own cells every frame. Walk across a section boundary and row 1 still says `SWAP` while row 3
has moved to whatever that section binds — **that disagreement is the answer**, not a bug. It is
the readout telling you the crossing took your override away.

Row 2 is blank unless you are standing on a preset entry. It is not left showing the last preset
you visited, because a readout that is confidently about something you walked away from is worse
than no readout.

**Every entry's name is four letters** — four cells is the widest a single VDP sprite piece can
be, so that is a hardware limit rather than a taste call, and no two entries spell the same word.
The whole list is below.

---

## The whole list, in order

Row 0 is where a cold boot leaves the cursor. `RIGHT` goes down this table, `LEFT` goes up it,
and both wrap — so **one press of `LEFT` from boot lands on `WLIN`**, the last entry.

| # | Name | What it is |
|---|---|---|
| 0 | `DFLT` | the act's own default background |
| 1 | `UWTR` | underwater |
| 2 | `WNDY` | windy |
| 3 | `SHMS` | shimmer, slow |
| 4 | `SHMR` | shimmer |
| 5 | `SHMF` | shimmer, fast |
| 6 | `HAZS` | haze, slow |
| 7 | `HAZE` | haze |
| 8 | `HAZF` | haze, fast |
| 9 | `HAZU` | haze, uniform |
| 10 | `RCKS` | rocking, slow |
| 11 | `ROCK` | rocking |
| 12 | `RCKF` | rocking, fast |
| 13 | `PRSS` | perspective, subtle |
| 14 | `PRSP` | perspective |
| 15 | `PRSD` | perspective, dramatic |
| 16 | `WNHZ` | windy + haze |
| 17 | `SKHZ` | sky + haze |
| 18 | `CAVE` | caves |
| 19 | `LCLD` | locked clouds |
| 20 | `PFLR` | the perspective floor scene |
| 21 | `BAND` | raster: the hand-authored band demo (the control) |
| 22 | `SWAP` | raster: the mid-frame plane-base swap |
| 23 | `RMPW` | raster: the authored ramp witness (editor-authored) |
| 24 | `PROB` | raster: the authored probe (editor-authored) |
| 25 | `SHIM` | raster: the section-3 shimmer document (editor-authored) |
| 26 | `RAMP` | raster: the ramp probe (editor-authored) |
| 27 | `NONE` | raster: **off** |
| 28 | `WATR` | preset: section 0 — water |
| 29 | `SPLT` | preset: section 1 — the sparse raster split |
| 30 | `DENS` | preset: section 2 — the dense gradient ramp |
| 31 | `CYCL` | preset: section 3 — the palette-cycling band |
| 32 | `DPTH` | preset: section 4 — the depth showcase |
| 33 | `SREF` | preset: section 5 — the sidecar-bound program |
| 34 | `BSWP` | preset: section 6 — the plane-base swap |
| 35 | `BARE` | preset: section 7 — plain, the control |
| 36 | `GRND` | preset: section 8 — plain + the perspective floor |
| 37 | `WLIN` | the Hydrocity waterline strips, on screen |

Entries 0-20 are **background scenes** (parallax only). 21-27 are **raster programs** (per-line
effects only). 28-36 are **whole section presets**. 37 is the **waterline stamp**, which is a
background scene *plus* a picture. You do not have to care which is which — that is the point —
but it is why some entries change the background as you move and others change what is drawn on
a line.

**Row 2 is the one that matters on a preset entry.** The digit is the section whose preset is now
installed. The glyph beside it says whether that preset can show you anything *from where you are
standing*:

| Glyph | Means | What to do |
|---|---|---|
| **`-`** a bar | **Nothing is bound, in any channel this glyph can see.** No raster program, no water program, no palette cycle — and the background scene is the act's own default, the same one you would be looking at anyway. | Nothing is wrong and there is nothing to look for. Press again. Section 7 is the deliberate example. |
| **`→`** an arrow | **Parallax, and you have to move.** Nothing in the three channels above, but this section brings a **background scene of its own**. Parallax is a motion channel: standing still it is just a picture. | **Hold LEFT or RIGHT and watch the background.** Section 8, the perspective floor, is this. |
| **`X`** | **Bound, but blind here.** The preset installs a *water-style* program whose boundaries are anchored to **world** positions, and right now every one of them is above or below the screen. | Move up or down until it flips to a diamond, or accept that this one has to be reviewed where it lives. |
| **`◇`** a diamond | **Live.** Something is installed and it is on screen. | Look at it. |

The verdict is worked out **at the moment you press**, against the camera as it stood then. If
you then walk away, a diamond can go stale. Press again to re-ask.

**One cell, one glyph — and the ranking is diamond, then X, then arrow, then bar.** They are in
descending order of "what do I do next": *look now* beats *move up or down until it flips* beats
*travel sideways* beats *there is nothing here*. So a preset that binds **both** a raster program
and its own background scene shows you only the raster verdict — the diamond wins and the arrow
is not reported. Section 0 is the live case: it always answers for its **water** (a diamond near
the top of the act, an `X` anywhere else) and never mentions that it also installs its own
underwater background. There is no second cell to put the other half in; the free tiles beside
this readout are spent.

**What each glyph does not promise.** It is a *precondition* test, not a proof that something is
worth looking at.

- A **diamond** means the effect is installed and its boundary is on screen. It does not promise
  the effect is interesting, or that its colours differ from the art behind it.
- An **arrow** means this section resolves a background scene that is *not the act default*, and
  that the other three channels are empty. It does **not** promise the scene looks different from
  the default (the test is "is it a different scene", not "does it look different"); it does
  **not** promise you can see it — the background plane draws *behind* the level's own terrain,
  so you may need debug free-flight to get above the ground; and it explicitly does **not**
  promise anything moves while you stand still. That is the whole content of the arrow: move.

---

## The PRESET entries, and what each one needs to be visible

These are the **last nine entries of the list** — one per section of OJZ act 1, in order. The
quickest way to reach them from a cold boot is **one press of `START + LEFT`**, which wraps you
straight onto the last of them (`GRND`, section 8); keep pressing `LEFT` to walk down through
them to `WATR` (section 0).

| # | Name | What it is | What it needs |
|---|---|---|---|
| 0 | `WATR` | **Water.** Two world-anchored boundaries with a sweep, plus the underwater parallax. | The camera near the **top of the act** — the boundaries are anchored at world Y 224 and 314. Anywhere else this reads `X`. |
| 1 | `SPLT` | **The sparse raster split** — shadow/highlight plus a backdrop change below screen line 120. | Nothing. On screen wherever you are. |
| 2 | `DENS` | **The dense tier** — a 96-line gradient ramp down the lower half (screen lines 96-191). | Nothing, but **look closely**: the ramp moves three palette entries by one intensity step each, so it is a subtle shading change, not a rainbow. The blue test palette that used to hide it is gone. |
| 3 | `CYCL` | **A palette-cycling band** — no raster at all, the colours themselves animate (line 2, entries 8-11). | Nothing, but **watch, don't glance** — it is an 8-frame cycle. |
| 4 | `DPTH` | **The depth showcase** — the vertical-split program from this section's authored scene. | Nothing. |
| 5 | `SREF` | The program section 5's editor sidecar binds (`$013C4C`, measured on the live ROM). | Nothing. |
| 6 | `BSWP` | **The mid-frame plane swap** — from screen line 3 down, the foreground draws the background's map. | Nothing. It covers nearly the whole screen. |
| 7 | `BARE` | **Plain.** Palette and the act's own default background, nothing else. | — reads `-`. Deliberately empty; it is the control. |
| 8 | `GRND` | **The perspective floor.** A wooden floor whose boards fan out from a vanishing point, with the rows nearer you scrolling faster than the rows at the horizon. | Nothing to reach, but **you have to MOVE to see the point of it** — which is exactly what it **reads the arrow** for. |

### 8 — the perspective floor, and how to actually see it

**Press `START + LEFT` once from a cold boot** — it wraps straight onto `GRND`, section 8.

**What you are looking at.** The bottom of the screen becomes a wooden floor.
Its boards splay out from a single vanishing point pinned to the **centre of the
screen**, at about two thirds of the way down (screen line 152): boards right of centre
lean right at the bottom, boards left of centre lean left, and the board sitting
on the centre line runs straight down. Above the floor is a dark shadow band,
and above that the jungle undergrowth and flowers.

The vanishing point never moves — it is nailed to screen centre at every camera
position, because the horizon row's scroll factor is exactly zero. What slides is
which board sits on the centre line, so as you travel the centre alternates
between a board and a seam. That is a plank floor behaving correctly, not drift.

**Now hold LEFT or RIGHT and watch the floor, not the jungle.** The boards
nearest the bottom of the screen sweep past quickly; the boards up at the
horizon do not move at all; every row in between moves at its own speed, one
pixel more per line down the screen. Cross one screen width — 320 pixels — and
the bottom row of the floor has slid **316 pixels** relative to the horizon row,
which has not moved a pixel. That gradient is the whole effect: **at a standstill
this is just a picture of a floor.** The motion is what makes it a floor
receding away from you rather than wallpaper.

For scale, the depth showcase on preset 4 ramps its fastest layer from half
camera speed to full — a 2x difference across its band. This one ramps from
*zero* to full across 72 lines. It is the largest rate difference the scene
vocabulary can express in one layer, chosen precisely because every effect
reviewed this week was too subtle to see.

**Fly up if the level's own ground is in the way.** The floor is on the
BACKGROUND plane, so foreground terrain draws over it. The debug build boots
into free flight; get above the terrain and the floor fills the lower screen.

**It reads the arrow, and the arrow is telling you to move.** Until 2026-09-04 this
row read the **bar** — "nothing is bound" — while filling the bottom third of the
screen with a floor, because the glyph inspected only the raster, water and
palette-cycle channels and a background scene is a *parallax* config. That was the
readout's own failure inverted: it under-reported a live effect, and a reviewer
trusting it would have skipped this preset entirely. The glyph now asks the parallax
channel too. Sections 7 and 8 share one preset record and differ **only** in the
background scene the section itself binds, which is why the glyph has to ask the
question of the section rather than of the preset — and why the bar and the arrow
land on the right rows.

**Two honest limits.** The splay is drawn into the art and cannot be otherwise —
see below — so the boards do not re-project as you move; they slide, which is
what a real plank floor does when you walk sideways across it, and it is correct
for exactly this reason (the art's board pitch and the scroll rate are
proportional to the same depth term, so the fan lands on itself with the board
index relabelled). And the background plane repeats every 512 pixels, so the
pattern carries a mirrored crease 256 pixels either side of the vanishing point;
travel far enough in one direction and it sweeps in across the bottom of the
screen. Both are properties of a placeholder, not of the mechanism.

**Why the fan is art and not code.** The HScroll table is 896 bytes —
224 lines x 2 planes x 2 bytes — one scroll word per plane per **scanline**,
applied to the line as a whole. Per-line scroll can therefore only *shear* the
background (every board leaning the same way); a fan needs the shift to vary
*across* one line, and no VDP register does that. So the splay is drawn
(`tools/perspective_floor_gen.py`) and the engine supplies the recession
(`games/sonic4/data/editor/effects/ojz_act1_floor.json`, the `curve` on its last
layer). This is the answer to "what would I use the curve for".

Every row above was **measured** off the running ROM by `tools/preset_lab_witness.py`, not
read off a comment: 1-6 read the diamond, 7 and 8 read the bar, and 0 reads the diamond with
its first water boundary landing on screen line 90 from a boot camera. Section 5 was written
up as empty on the strength of a source comment and is not — its sidecar binds a real
program.

**Re-measured on 2026-09-04**, after the arrow landed, by the same instrument against the
same act: 1-6 read the diamond, 7 reads the bar, **8 reads the arrow**, and 0 reads the
diamond with its first water boundary on screen line 90 from a boot camera. The witness
derives every expectation from the ROM's own records — including its own reimplementation
of the section > preset > act resolve the arrow is decided by — so the run is two
independent implementations agreeing, not the readout marking its own homework.

Row 8's "what it needs" column above is derived from the scene document and the art, not
measured off a ROM — the numbers in it (screen line 152 for the horizon, a 72-line span,
316 pixels of relative slide per 320 of camera) come from `Vscroll_BG = v_offset = 288`,
the layer top at plane line 440, and the curve arithmetic in `engine/level/parallax.emp`,
re-derived arm by arm.

---

## Scene `01` — the Hydrocity waterline, and how to actually see it

This one is on the **scene** chord, not the preset chord, and it is worth its own section
because it is the only effect in the lab whose subject is fifteen scanlines tall.

**Press `START` + `RIGHT` once.** You boot with the section's own scene installed and the
cursor at 0, so the first press lands on **`01`** — the row-1 readout says `01` and
`ParallaxConfig_OJZ_Underwater` is live. That is the whole setup. You do not need to be
anywhere in particular and you do not need to press anything else.

**Then look at the background just below the waterline**, which sits between screen lines
**64 and 95** and drifts. Two things are happening and they are different things:

- **Everywhere below the waterline**, the background scrolls left and right by **16 pixels
  peak to peak** in a slow wave. That is the shimmer, and it is the thing you can see from
  across the room.
- **In the strip immediately under the surface** — between 6 and 15 scanlines of it — the
  ripples are visibly **bunched together**, tighter than the ones further down, and they relax
  back to normal spacing below the strip. That is the row remap. It squeezes about 27 lines of
  wave into 15, so the effect is *compression near the surface*, not a wobble.

**Stand still and it animates on its own.** The section sweeps the water anchor on a cycle of
roughly **15 seconds**, and the strip breathes with it: it grows from 6 scanlines to 15 and
tightens, then thins and relaxes. Nothing to press, nothing to hold.

**To see it invert, fly up.** In free flight (the debug build boots into it) every pixel you
climb takes one pixel off the compression. Somewhere between **6 and 37 pixels up** — the exact
figure depends on where the 15-second sweep happens to be when you start — the strip thins to
nothing and the effect switches off completely, with no seam. Keep climbing and it grows back
with the compression running the *other* way. That is the "depending on your perspective" the
effect is named for, and the equilibrium is real: the arithmetic turns itself off at zero
rather than being clamped there.

**If you cannot see it, that is a bug and not your eyes.** Two gates exist specifically so this
cannot ship invisible again — `tools/row_remap_gate.py` computes the wave's peak-to-peak travel
in pixels out of the linked ROM and fails the build under 8 px, and a comptime `ensure` beside
the scene does the same from the generator's own array. It shipped at 4 px on 2026-09-03 and
was invisible; it is 16 px now.

> **A number that was here and is gone.** An earlier version of this page said "fly up ~37 px".
> That was one end of a range read as a constant. The distance to equilibrium is not fixed — the
> anchor sweep moves it continuously between 6 and 37 px — so the page now says the range and
> says why it moves.

---

## Entry `37` — `WLIN`, the waterline strips themselves

Everything in the section above is the waterline's **scroll** half: the background's rows,
permuted. The effect has a second half that permutes **pixel rows of an image** into eight tiles
of VRAM every frame the perspective quantity moves, and until this entry existed **nothing on
screen pointed at those tiles**. They were resident, correct and invisible: the OJZ background
has no water surface to promote, and the effect writes no nametable cell by design. The only
evidence was a Python witness.

**Press `START + LEFT` once from a cold boot.** The list wraps straight onto `WLIN`, the last
entry — one press, from anywhere, standing still.

**What it does.** Two things, in this order: it installs `ParallaxConfig_OJZ_Underwater` (so it
is entry `01` plus something, and the background changes exactly as `01` does), and it puts a
**32 x 16 pixel picture in the top-right corner of the screen**. That picture *is* the eight
tiles the gather writes. Nothing copies them; the sprite names them.

```
      +--------+--------+
      | ABOVE  | BELOW  |    <- top-right corner, 32 x 16 px
      +--------+--------+
```

The left half is the strip that draws **above** the surface, the right half the strip **below**
it. Both are 16 x 16.

**The colours are wrong on purpose.** The stamp draws through palette line 1 — the lab's own
line, the one the four readout rows use — so what you see is a fourteen-step ramp of whatever
that line holds, not water. **The subject is the shape and how it moves**, not the hue.

**What to watch for.** The picture is only rebuilt on frames where the ladder row changes, which
is the engine's own guard and not a limitation of the stamp. So:

- **Fly up and down** (the debug build boots into free flight). The bands inside each half
  visibly **bunch and relax** as you climb — that is the same row permutation the background is
  doing, shown directly instead of at fifteen scanlines tall.
- **Stand still** and it breathes anyway, on the section's ~15-second anchor sweep.
- **A picture that never moves at all** means the ladder row is pinned, not that the stamp is
  broken; that is a real answer about the effect.

**It disappears when it stops being true, and that is the feature.** Walk across a section
boundary and the section re-installs its own scene, the remap stops being marked, and the eight
tiles freeze at their last content — so the stamp **removes itself** on that frame rather than
leaving a still picture of a state the machine has left. Stepping to any other entry removes it
too. If it vanishes while you are standing on `WLIN`, you crossed a boundary; press `START +
LEFT`/`RIGHT` round to it again.

**It costs no VRAM.** The eight tiles were already reserved and already written every frame; this
entry is one sprite that names them, in the DEBUG shape only.

## Scene `20` — the perspective floor WITH the per-column cone, one press from boot

**Press `START` + `LEFT` once.** The scene cursor boots at 0 and steps backwards with a
wrap, so a single LEFT lands on the last scene in the registry. Row 1 reads `20` and
`ParallaxConfig_Perspective_Floor` is live. Twenty presses of `START` + `RIGHT` reach the
same place the long way round.

**How this differs from preset `8`**, which is also "the perspective floor" and is
documented above. Preset 8 installs section 8's *editor-authored* scene: correct window,
correct ramp, and **no per-column deform at all**. Scene 20 is that same geometry with the
F3 **vanishing-point cone** on top — the thing scenes `13`/`14`/`15` have and preset 8 does
not. If you want to compare, walk to `GRND` (preset 8) and to `PFLR` (scene 20) — they show
the floor with and without the cone.

**What to look for, and all of it needs MOTION — a still frame shows none of it:**

- **Hold LEFT or RIGHT and watch the floor, not the jungle.** Rows nearer the bottom sweep
  past quickly and the row at the horizon does not move at all. The vanishing point stays
  put while the boards slide past it.
- **The horizon should read as a straight line, not a chevron.** The cone bows the plane by
  6 px at the screen edges, chosen so the hard shadow line under the horizon never steps by
  more than 1 px between neighbouring columns.
- **The apex leans as you travel**, bounded to the middle third of the display.

**The floor band deliberately has no shimmer and no haze.** A band that ramps its scroll
factor cannot also sample a deform table — the fill's curve loop has no registers left — so
the floor trades its wobble for its recession. The four bands above it keep theirs.

**This is BACKGROUND**, so OJZ's foreground terrain draws over it. Review it from debug
free-flight with the camera somewhere the foreground is open.

> **Why scenes `13`, `14` and `15` show you a "V in the trees" and this one does not.**
> They author `v_offset: 0`, which on a locked plane pins the visible window to plane rows
> 0-27 — the canopy. The floor art is at rows 48-63. Their cone was always working; it was
> pointed at the forest. They are the still-open F3 ballot on where the vanishing point
> should sit, so they are left exactly as they are.

---

## Things worth knowing

- **`START + LEFT/RIGHT` still steers you** — the directions keep their normal meaning while the
  chord is held. For a background review you are standing still, and that is the whole cost.
  `START` is the only free bit on a 3-button pad; X/Y/Z/MODE exist only on a 6-button pad, so a
  chord on them would be silently dead on a 3-button one, which is the worst thing a review tool
  can be.
- **The list goes both ways.** Thirty-eight entries, so the far side is at most nineteen presses,
  and `LEFT` from the first entry wraps onto the last (`WLIN`, just past the presets).
- **Entries are mutually exclusive.** Each one evicts the last, because each is an install into an
  engine slot. Selecting a scene and then a preset gives you the preset; the preset writes every
  channel including the one the scene wrote.
- **The BG animation chord is the one exception to "it undoes itself".** The band table is not an
  EffectsPreset channel, so walking across a section boundary does **not** put it back — press
  `START + C` round its cycle to turn it off again. It is also the only tier whose default is off
  in the shipped ROM as well as the debug one. That orthogonality is exactly why it is **not** in
  the one list: everything in the list replaces what came before it, and a latch that survives a
  crossing would turn the list into a set of switches you have to walk back through.
- **Nothing here runs during a replay.** Both chords stand down unless input is live, so a
  recorded fixture cannot trip them.
- **The section digit is one digit.** An act with more than ten sections cannot be labelled by
  this readout; giving it a second digit means a second VRAM region, because the free tiles
  beside it are spent. The build fails rather than mislabelling — a lint checks the preset
  entries against the act's own grid.
- **The verdict is one cell, and that is a VRAM fact rather than a design one.** The map has
  **one free tile left** (959) in the whole 2048. The arrow was made to fit by adding a glyph to
  the existing sheet, not a cell — which is why the verdicts rank against each other instead of
  being reported together. Reporting two channels at once needs a region taken from something
  else.

---

## Where this lives

`games/sonic4/test/ojz_scroll_test.emp` — `Debug_LabCycleHotkey` (the one list and its
dispatch), `Debug_BgAnimViewHotkey`, `Debug_PresetReadout_Show` / `_Blank`, and
`Debug_TierTags_Update` (all three name tags). Each proc's header carries the argument for its
chord and the enumeration of what was already taken. The glyph cells are
`games/sonic4/vram.toml`, regions `debug_lab_name` (the entry name), `debug_preset_readout`
(the digit and verdict), `debug_raster_tag` and `debug_bganim_tag`.

Four gates keep this page honest, all build-fatal in the build's pytest lane.
`tools/test_lab_index_lint.py` holds the one list to the three tables it dispatches into —
every scene reachable, every raster program reachable, every preset entry inside the act's own
grid, every name four defined letters, and no two entries spelling the same word.
`tools/test_scene_cycle_table_lint.py` and `tools/test_raster_cycle_table_lint.py` hold those
two sub-tables to the scene registry and to the preset documents on disk.
`tools/test_preset_verdict_font_lint.py` holds the verdict glyph sheet to the verdict
constants, so a state cannot ship without a glyph. Beyond the lane,
`tools/preset_lab_witness.py` boots a headless machine, walks the preset entries and compares
every painted tile against an expectation it derives from the ROM's own records:

```
python3 tools/preset_lab_witness.py --rom s4.debug.bin --lst s4.debug.lst
```

None of it exists in the release ROM: `s4.bin` is byte-identical with and without the whole
lab, `EndOfRom` and the symbol set included.

---

## The background tile animation — `START + C`

Its own chord, deliberately, and **not** part of the one list — see "Things worth knowing"
above for why. Hold `START` and press `C` with **no direction held**; each press steps it
round: **off → horizontal (camera X) → vertical (camera Y) → timer → an off-screen vertical
probe → that probe's control → off**. Row 4 of the readout names the live one
(`ACT` / `CMX` / `CMY` / `TMR` / `VRT` / `VCT`), so you never have to count presses.

The two probe states put nothing on the screen by construction — they aim at an unused VRAM
band reserve — so if the picture stops changing after `TMR`, that is them, and one or two more
presses brings you back to `ACT`.

**Off is where the game now boots**, in the shipped ROM as well as this one. The band that
used to animate the canopy on a free-running timer is still in the ROM, still authored, and
still costs the same bytes — it is simply not counted in the act's band table, so nothing
walks it. Nothing needs to be pressed to get the quiet screen; the chord exists to put a
view **back**.

The two views differ in **what drives the motion**, not in what moves:

| State | Driven by | What you should see |
|---|---|---|
| off | — | still canopy |
| horizontal | the camera's **X** | the canopy slides only while you run left or right, ~1 px per 16 px travelled — a full cycle is about three screen widths |
| vertical | the camera's **Y** | the canopy slides only while you move up or down, about one full cycle per screen height |

**Stand still and nothing moves.** That is the whole change from the old behaviour and it is
the point: a timer animates whether or not you are there, which reads as an animation; a
camera-driven band reads as depth.

Two things worth knowing before you call one of them broken:

- **Both views move the band the same way — sideways.** "Horizontal" and "vertical" name the
  camera axis, not the art's. A band whose art genuinely scrolls *upward* needs vertically
  pre-shifted phase art and a row-major slot order in the layout, and nothing in the tree can
  author either yet (the bake refuses the mismatch by name rather than shipping a shimmer).
  That is a content job, not a chord.
- **Off freezes the band, it does not rewind it.** Once a view has run, turning it off leaves
  the tiles wherever the last step put them — up to 63 px into their own 64 px pattern. A cold
  boot is the only guaranteed rest state. Nothing looks broken, because the band's tiles are
  reused all over the background and shift together.
