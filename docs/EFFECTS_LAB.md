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
| 5 | Whatever section 5's editor sidecar binds. Nothing today. | — reads `-` until its sidecar binds something. |
| 6 | **The mid-frame plane swap** — 64 lines above the screen bottom, the foreground starts drawing the background's map. | Nothing. Look at the **bottom** of the screen. |
| 7 | **Plain.** Palette and parallax only. | — reads `-`. Deliberately empty; it is the control. |
| 8 | Plain, the same record as 7. | — reads `-`. |

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
