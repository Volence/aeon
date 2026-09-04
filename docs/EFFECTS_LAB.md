# The Effects Lab — how to drive it

**One page, for the person holding the pad.** Build `DEBUG=1 ./build.sh`, load `s4.debug.bin`,
and stand still. Everything here is a chord on the pad. None of it exists in the release ROM.

The lab has three tiers. They are independent: each one writes state the other two do not
touch, so you can stack them.

---

## The three chords

| Hold | Press | What it does |
|---|---|---|
| `START` | `LEFT` / `RIGHT` | step the **background scene** — parallax only |
| `START` | `UP` | step the **raster program** — bands only |
| `START` | `DOWN` | raster program **off** |
| `START` | `A` | step the **whole preset** — everything a section looks like |

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
| **`-`** a bar | **Nothing is bound.** This preset has no raster program, no water program and no palette cycle. Palette and parallax only. | Nothing is wrong. There is genuinely nothing to look for. Press again. |
| **`X`** | **Bound, but blind here.** The preset installs a *water-style* program whose boundaries are anchored to **world** positions, and right now every one of them is above or below the screen. | Move up or down until it flips to a diamond, or accept that this one has to be reviewed where it lives. |
| **`◇`** a diamond | **Live.** Something is installed and it is on screen. | Look at it. |

The verdict is worked out **at the moment you press**, against the camera as it stood then. If
you then walk away, a diamond can go stale. Press again to re-ask.

And it is a *precondition* test, not a promise: a diamond means the effect is installed and its
boundary is on screen. It does not promise the effect is interesting, or that its colours differ
from the art behind it.

---

## What is in the `START + A` cycle, and what each one needs to be visible

The list is the act's own section table, in order. For OJZ act 1 that is nine entries. The
cursor starts at 0 and your first press installs **1**, because you boot standing in 0.

| # | What it is | What it needs |
|---|---|---|
| 0 | **Water.** Two world-anchored boundaries with a sweep, plus the underwater parallax. | The camera near the **top of the act** — the boundaries are anchored at world Y 224 and 314. Anywhere else this reads `X`. |
| 1 | **The sparse raster split** — shadow/highlight plus a backdrop change below screen line 120. | Nothing. On screen wherever you are. |
| 2 | **The dense tier** — a 96-line gradient ramp down the lower half, plus this section's own palette. | Nothing. |
| 3 | **A palette-cycling band** — no raster at all, the colours themselves animate (line 2, entries 8-11). | Nothing, but **watch, don't glance** — it is an 8-frame cycle. |
| 4 | **The depth showcase** — the vertical-split program from this section's authored scene. | Nothing. |
| 5 | The program section 5's editor sidecar binds (`$013C4C`, measured on the live ROM). | Nothing. |
| 6 | **The mid-frame plane swap** — 64 lines above the screen bottom, the foreground starts drawing the background's map. | Nothing. Look at the **bottom** of the screen. |
| 7 | **Plain.** Palette and parallax only. | — reads `-`. Deliberately empty; it is the control. |
| 8 | Plain, the same record as 7. | — reads `-`. |

Every row above was **measured** off the running ROM by `tools/preset_lab_witness.py`, not
read off a comment: 1-6 read the diamond, 7 and 8 read the bar, and 0 reads the diamond with
its first water boundary landing on screen line 90 from a boot camera. Section 5 was written
up as empty on the strength of a source comment and is not — its sidecar binds a real
program.

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

## Things worth knowing

- **`START + A` makes you jump** unless you are in debug free-flight (which the debug build boots
  into). Every free button on a 3-button pad is a jump button or already taken; this was the
  cheapest collision left. In free flight it costs nothing.
- **The cycle only goes forward.** Nine entries, so the far side is at most five presses.
- **The three tiers stack.** `START + A` then `START + UP` puts a hand-authored band program on
  top of a section's preset. `START + A` again wipes it, because a preset install writes every
  channel.
- **Nothing here runs during a replay.** All three chords stand down unless input is live, so a
  recorded fixture cannot trip them.
- **The readout is one digit.** An act with more than ten sections would have its eleventh
  hidden rather than mislabelled — the cycle clamps. Nothing in the tree is that size yet;
  giving the readout a second digit means a second VRAM region, because the free tiles beside
  it are now spent.

---

## Where this lives

`games/sonic4/test/ojz_scroll_test.emp` — `Debug_SceneCycleHotkey`, `Debug_BandDemoHotkey`,
`Debug_PresetCycleHotkey`, and the two readouts. Each proc's header carries the argument for its
chord and the enumeration of what was already taken. The glyph cells are
`games/sonic4/vram.toml`, region `debug_readout`.
