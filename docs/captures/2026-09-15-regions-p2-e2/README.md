# E2 on screen: an instant colour change over unchanged scenery

Captured 2026-09-15 by the controller in the foreground, on the merged tree's
`s4.debug.bin` (aeon `ec513055`, md5 `9250a9af…`), symbols `s4.debug.lst`.
A headless capture cannot settle this: "reads as a glitch" is a motion percept.
These stills say WHAT changes and WHERE; the verdict is the owner's, on a running ROM.

## What the run did

One continuous hold of RIGHT from the spawn in free flight, through BOTH treatments
of the same crossing:

| file | what it shows |
|---|---|
| `00-day-before-fade.png` | day colours, approaching the FADE edge at x = 3400 |
| `01-fade-midway.png` | the shipped 16-frame fade, night colours arriving gradually |
| `02-day-before-snap.png` | day again, approaching the SNAP edge at x = 5600 |
| `03-snap-frame.png` | still day, one tick before the crossing |
| `04-snap-after.png` | night, INSTANT — same art, only the colours moved |
| `05-night-with-sonic.png` | out of free flight: Sonic in the night region |
| `06-night-landed.png` | landed, night region |
| `07-walking-back-across.png` | walking back west, lower geometry |

`02` against `04` is the experiment: identical scenery, one frame apart, colours
swapped whole. Nothing repaints — part 2's row wipe is step 6 and does not exist yet,
and both regions share one tile set, so there is no "new palette over half-redrawn
art" transient to see. What E2 actually asks is whether the INSTANT whole-screen
colour change reads as a transition or as a fault.

## The thing to decide deliberately rather than be surprised by

**Sonic keeps his DAY colours in the night region** (`05`, `06`) — bright blue, red
shoes, unshaded skin, against a dark blue-green world. That is real and it is not a
capture artifact.

It is also NOT about the snap. Palette line 0 is the character line, shared by one file
every zone loads, so character colours cannot vary per region today; per-zone copies
need engine support first. That is the owner's own earlier ruling on aurora's
PALETTE-LINE0 card. **So if the verdict here is "the character looks wrong", the finding
is about line 0 and belongs to that card, not to E2's snap-versus-fade question.**

Said before the look rather than after it, deliberately: withholding it would look like
letting the judgement happen unprimed, and would in fact just produce a verdict about
the wrong mechanism.
