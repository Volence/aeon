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
| `06-night-landed.png` | ⚠ **MISLABELLED — this frame is NOT in the night region.** Landing drops the camera out of it; see the correction below |
| `07-walking-back-across.png` | walking back west, lower geometry — the same region as `06`, not the night one |

`02` against `04` is the experiment: identical scenery, one frame apart, colours
swapped whole. Nothing repaints — part 2's row wipe is step 6 and does not exist yet,
and both regions share one tile set, so there is no "new palette over half-redrawn
art" transient to see. What E2 actually asks is whether the INSTANT whole-screen
colour change reads as a transition or as a fault.

## The thing to decide deliberately rather than be surprised by

**Sonic keeps his DAY colours in the night region** (`05`) — bright blue, red
shoes, unshaded skin, against a dark blue-green world. That is real and it is not a
capture artifact. **`06` is NOT evidence for this and originally was cited as though it
were** — see the correction below.

It is also NOT about the snap. Palette line 0 is the character line, shared by one file
every zone loads, so character colours cannot vary per region today; per-zone copies
need engine support first. That is the owner's own earlier ruling on aurora's
PALETTE-LINE0 card. **So if the verdict here is "the character looks wrong", the finding
is about line 0 and belongs to that card, not to E2's snap-versus-fade question.**

Said before the look rather than after it, deliberately: withholding it would look like
letting the judgement happen unprimed, and would in fact just produce a verdict about
the wrong mechanism.

## ⚠ CORRECTION, 2026-09-16: `06` and `07` are not in the night region, and the caption said they were

Raised by the hub's reader, which flagged `06`'s canopy as unlike every other frame and asked
whether it was a different scene or a mid-load capture. **It is a different scene, it is correct
behaviour, and the defect was in this file.** Measured on the running ROM rather than inferred
from the picture: booted `s4.debug.bin`, warped to x 5700 / y 1000, read the resolved region
rectangle out of RAM, pressed B to leave free flight, let Sonic fall, and read it again.

| | resolved region |
|---|---|
| in free flight, after the warp | x 5600..6143, y **0..2047** — the E2 snap row |
| after landing | x 4096..6143, y **2048..4095** — section 5's row |

Camera at the second reading: x 5540, **y 3034**. The night region is y 0..2047 by construction,
so landing takes the camera out of it entirely and into a region binding a different preset. A
different palette *and* different scenery is exactly what that is supposed to produce, and a
reproduction screenshot matches `06`/`07`'s vocabulary frame for frame.

**What was wrong here:** the caption read "landed, night region", and the line-0 paragraph then
reasoned from `05` *and* `06` together about Sonic's colours in the night region. That is still
true of `05` and was never evidence from `06`.

**THE THING WORTH KEEPING, which is not the caption.** This set was built to show ONE crossing
and it contains three: the fade at x 3400, the snap at x 5600, and an unannounced **VERTICAL**
crossing that happens whenever the player stops flying and falls. Nobody designed it into the run
and nobody noticed it afterwards. It is free today because no region streams yet. **It stops
being free at step 6:** a fall is exactly the half-redrawn condition the row wipe creates, and it
arrives with no horizontal travel at all, so §4.3's entry-side sweep needs an answer for entering
from ABOVE. Booked in `docs/DEFERRED_WORK.md` as **REGIONS-VERTICAL-CROSSING-ON-LANDING**; the
second, shorter look reserved in §3 should cover a fall as well as a walk.
