# The Effects Lab — how to drive it

**One page, for the person holding the pad.** Build `DEBUG=1 ./build.sh`, load `s4.debug.bin`,
and stand still. Everything here is a chord on the pad. None of it exists in the release ROM.

The lab has four tiers. They are independent: each one writes state the others do not
touch, so you can stack them.

---

## The four chords

| Hold | Press | What it does |
|---|---|---|
| `START` | `LEFT` / `RIGHT` | step the **background scene** — parallax only |
| `START` | `UP` | step the **raster program** — bands only |
| `START` | `DOWN` | raster program **off** |
| `START` | `A` | step the **whole preset** — everything a section looks like |
| `C` | `A` | step the **background tile animation** — off / horizontal / vertical |

`START + A` is the one to reach for first. The other two change one channel each; this one
installs an entire section's look — palette, palette cycling, palette variants, the raster or
water program, the water anchors and their motion, and the parallax config — onto the section
you are standing in. It is the same operation the engine runs when you walk across a section
boundary, so what you see is what that section really looks like.

**You do not need to know where you are.** That was the whole point. Stand anywhere and cycle.

**It undoes itself.** Walk across any section boundary and the section's own effects come back.
Nothing you press here can leave the act mis-configured, and nothing you press here changes what
the game ships.

---

## Reading the screen

Top-left corner, two rows of small yellow glyphs. They appear on your first press, not at boot.

```
    1 4        <- row 1: the SCENE cursor (two digits, 00-19)
    3 <>       <- row 2: the PRESET cursor (one digit) and its VERDICT
```

**Row 2 is the one that matters for `START + A`.** The digit is the section whose preset is now
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

## What is in the `START + A` cycle, and what each one needs to be visible

The list is the act's own section table, in order. For OJZ act 1 that is nine entries. The
cursor starts at 0 and your first press installs **1**, because you boot standing in 0.

| # | What it is | What it needs |
|---|---|---|
| 0 | **Water.** Two world-anchored boundaries with a sweep, plus the underwater parallax. | The camera near the **top of the act** — the boundaries are anchored at world Y 224 and 314. Anywhere else this reads `X`. |
| 1 | **The sparse raster split** — shadow/highlight plus a backdrop change below screen line 120. | Nothing. On screen wherever you are. |
| 2 | **The dense tier** — a 96-line gradient ramp down the lower half (screen lines 96-191). | Nothing, but **look closely**: the ramp moves three palette entries by one intensity step each, so it is a subtle shading change, not a rainbow. The blue test palette that used to hide it is gone. |
| 3 | **A palette-cycling band** — no raster at all, the colours themselves animate (line 2, entries 8-11). | Nothing, but **watch, don't glance** — it is an 8-frame cycle. |
| 4 | **The depth showcase** — the vertical-split program from this section's authored scene. | Nothing. |
| 5 | The program section 5's editor sidecar binds (`$013C4C`, measured on the live ROM). | Nothing. |
| 6 | **The mid-frame plane swap** — from screen line 3 down, the foreground draws the background's map. | Nothing. It covers nearly the whole screen. |
| 7 | **Plain.** Palette and the act's own default background, nothing else. | — reads `-`. Deliberately empty; it is the control. |
| 8 | **The perspective floor.** A wooden floor whose boards fan out from a vanishing point, with the rows nearer you scrolling faster than the rows at the horizon. | Nothing to reach, but **you have to MOVE to see the point of it** — which is exactly what it **reads the arrow** for. |

### 8 — the perspective floor, and how to actually see it

**Press `START + A` until the preset digit reads `8`.**

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

## Things worth knowing

- **`START + A` makes you jump** unless you are in debug free-flight (which the debug build boots
  into). Every free button on a 3-button pad is a jump button or already taken; this was the
  cheapest collision left. In free flight it costs nothing.
- **The cycle only goes forward.** Nine entries, so the far side is at most five presses.
- **The tiers stack.** `START + A` then `START + UP` puts a hand-authored band program on
  top of a section's preset. `START + A` again wipes it, because a preset install writes every
  channel.
- **The BG animation tier is the one exception to "it undoes itself".** The band table is not
  an EffectsPreset channel, so walking across a section boundary does **not** put it back —
  press `C + A` round the cycle to turn it off again. It is also the only tier whose default
  is off in the shipped ROM as well as the debug one.
- **Nothing here runs during a replay.** All three chords stand down unless input is live, so a
  recorded fixture cannot trip them.
- **The readout is one digit.** An act with more than ten sections would have its eleventh
  hidden rather than mislabelled — the cycle clamps. Nothing in the tree is that size yet;
  giving the readout a second digit means a second VRAM region, because the free tiles beside
  it are now spent.
- **The verdict is one cell, and that is a VRAM fact rather than a design one.** The two cells
  at VRAM tiles 1022/1023 were the last free run beside `debug_readout`, and it is spent. The
  arrow was made to fit by adding a **fourth glyph to the existing sheet**, not a third cell —
  which is why the four verdicts rank against each other instead of being reported together.
  Reporting two channels at once needs a new VRAM region.

---

## Where this lives

`games/sonic4/test/ojz_scroll_test.emp` — `Debug_SceneCycleHotkey`, `Debug_BandDemoHotkey`,
`Debug_PresetCycleHotkey`, `Debug_BgAnimViewHotkey`, and the two readouts. Each proc's header carries the argument for its
chord and the enumeration of what was already taken. The glyph cells are
`games/sonic4/vram.toml`, region `debug_readout`.

Two gates keep this page honest. `tools/test_preset_verdict_font_lint.py` (build-fatal, in
the build's pytest lane) holds the glyph sheet to the verdict constants, so a fifth state
cannot ship without a fifth glyph. `tools/preset_lab_witness.py` boots a headless machine,
presses the chord round the whole cycle and compares every painted tile against an
expectation it derives from the ROM's own records:

```
python3 tools/preset_lab_witness.py --rom s4.debug.bin --lst s4.debug.lst
```

None of it exists in the release ROM: `s4.bin` is byte-identical with and without the whole
lab, `EndOfRom` and the symbol set included.

---

## The background tile animation — `C + A`

Three states, forward-only: **off → horizontal → vertical → off**.

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
