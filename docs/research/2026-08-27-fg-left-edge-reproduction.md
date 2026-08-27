# FG left edge: a reproduction attempt, and what it rules out

**Run by the aeon overseer, 2026-08-27, on `s4.debug.bin` crc `9f9c0126` (735,386 B) — the
same ROM the owner's save state was taken on**, rebuilt at master `aa186cc1` after `rm -f`ing
the previous artifacts, so the ROM's existence witnesses its own freshness. The four-shape
CRCs match the sigil chain-170 pins exactly (`s4 66d2c263` / `s4.debug 9f9c0126`).

Instrument: `tools/fg_left_edge_probe.py` (new, committed with this note). It spawns
`oracle-aether` through `tools/aether_instance.py` — so the Rust-server identity assertion
runs — and reads the plane-A candidate's `opaque` flag out of `emulator/pixel_attribution`,
the same field the by-hand table in the booking tabulated. It refuses to measure if the
server's `romBytes` disagrees with the file on disk.

## Why not the owner's save state

The aether server has **no path from the bus to the filesystem** for machine state. That is a
deliberate rule, not a gap: `emulator/checkpoint` is in-memory only, and the method table is
asserted to contain no persist-to-disk variant (`crates/oracle-aether/tests/checkpoints.rs`,
"D13 rule 1"). So `2026-08-26-fg-left-edge-glitch.state0` cannot be loaded over the wire at
all, by design. The instrument was retired; the question was not.

## What was measured

Four independent routes to a left edge with ground on it. **None of them reproduces the
owner's symptom.**

| Route | Camera | Result at x=0 / x=8 |
|---|---|---|
| Boot, settled 240 f | (96, 144) | plane A empty in the whole sampled window — no ground anywhere to judge |
| Hold RIGHT, 5 stops | (2944 … 5824, 144) | band present in every column; counts equal across x=0…56 |
| One-tile steps, 5 stops | (2944 → 3008, 144) | one transient one-row shortfall at 2944, gone at the next step |
| Hold LEFT, 5 stops | (2640 → 2400, 144) | band present in every column; the only gaps are at x=24, not the left edge |
| Warp to the owner's player position | (195, **461**) | ground band continuous across all eight columns from y=136 down |

The one-row shortfalls that do appear are **not left-edge-specific** — the same probe shows
identical transient gaps at x=24 and x=32 — so they are terrain, not the defect.

## Three findings that change the hypothesis

**1. The symptom is CONDITIONAL, and the booked mechanism predicts it is not.** The booking's
reading is that "the fill window starts ~16 px right of the viewport, so the first two columns
are never written". That mechanism is camera-independent: it would show at *every* position
where ground reaches the left edge. It demonstrably does not — twelve sampled camera positions
across two travel directions show the two leftmost columns behaving exactly like their
neighbours. **A fix derived from that mechanism alone would be fixing something that is not
happening in the simple cases, and its sample passing would not mean much.**

**2. Every sample above held `Camera_Y` fixed** — at 144 for all the travel routes, at 461 for
the warp. That is precisely the shape this workspace's own review bar warns about: a clean
constant across varied inputs is evidence of a **confound**, and the confound here is the
variable the owner's capture differs in.

**3. The owner's camera sits 32 px off the position a warp can produce — CORRECTED, see
below.** He reported `Camera_Y = 429` with the player at y=573; warping the player to exactly
(355, 573) lands the camera at **(195, 461)**, where it stays through 240 further frames.

> **CORRECTION, same session, before this doc was an hour old.** The first version of this
> row read 461 as the *resting* value and concluded his capture was taken **mid-vertical
> motion**. A further measurement refutes that. The camera is `player - (160, 112)` at
> **every** warp — three points, (355,300) -> (195,188), (355,420) -> (195,308), (355,573) ->
> (195,461), all exact. 112 is half the 224-line screen, so a warp always lands
> screen-centred. The owner's state is `player_y - 144`, a **different offset**, not a
> transient of this one.
>
> What produces the extra 32 px is **not established** — a vertical camera deadzone whose
> phase depends on how the position was arrived at is the obvious candidate, and it is
> consistent with 144 being half the 288-px plane rather than half the screen, but nothing
> here measures it. Stated as an open question rather than a mechanism, because the mechanism
> story in the first version was wrong and this doc's whole value is the measurements.
>
> **What survives, and it is the operationally important half:** his camera/player phase is
> **not reachable by warping**, so his state carries streaming history a warp cannot
> reconstruct. That strengthens rather than weakens the conclusion below.

**A route that was tried and does not work:** dropping the player from above the ground to
force vertical camera travel. Warped to (355, 300) and (355, 420), the camera goes straight to
`y - 112` and **stays there for 130 frames with no fall** — in this scene the player does not
descend under gravity from a warp, so there is no play-reachable vertical motion to sample.

## The methodological catch, stated because it limits row 5 above

**The warp cannot reproduce this defect even if it is real.** The DEBUG warp mailbox exists
precisely because a bare camera poke tears — it is consumed at a coherent point and *rebuilds*
the column ring, the plane buffers and residency. That is the exact state under suspicion, so
warping to the owner's viewport is an instrument that **manufactures the absence** it reports.
Row 5 is therefore evidence about a freshly-rebuilt left edge, and no evidence at all about an
accumulated one. Recorded so nobody later reads that row as "measured clean at the owner's
camera position".

## What would settle it

Reaching the state by PLAY, with vertical camera motion in it — or the owner loading his own
`.state0` in `oracle-frontend`, which already exposes an aether socket, so the same probe can
attach and sample the true state directly.

---

# REPRODUCED — it is the per-column V-scroll hardware limitation, on the FOREGROUND

**Measured 2026-08-27 on `s4.debug.bin` after the fg-left-edge merge (`6e26471a`), all four
CRCs unchanged from `9f9c0126`.** The subagent's replacement lead was right in *class*: this is
per-column vertical scroll. It is not reachable by any route that holds the effect scene at its
default, which is why four earlier routes and twelve camera positions all came back clean.

## The condition

`VDP` register `$0B` bit 2 (per-column V-scroll) is **0** at boot and **1** on scenes 10-15 —
`Rocking_Slow/Rocking/Rocking_Fast` and `Perspective_Subtle/Perspective/Perspective_Dramatic`,
exactly the six the scene registry documents as attaching `SceneVDeform.Columns`. The effects-lab
hotkey (START + RIGHT) is what reaches them.

## The A/B, at Camera_Y=461 with ground continuous across the screen

```
CONTROL scene 0  bit2=0        TEST scene 10  bit2=1
  x=0  x=8  x=16                 x=0  x=8  x=16
y=144  #    #    #             y=144  #    #    #
y=152  #    #    #             y=152  .    #    #
y=160  #    #    #             y=160  .    .    #
y=168  #    #    #             y=168  .    .    #
 ...   #    #    #              ...   .    .    #
y=208  #    .    .             y=208  .    .    #
count 11   10    9             count  3    4   11
```

**That is the owner's signature exactly**: the two leftmost columns carry content in the upper
rows and go transparent across every ground row, while x>=16 carries the band. His own table
breaks at y=152; this one breaks at y=152 (x=0) and y=160 (x=8).

## The correlation, across all twenty scenes at one camera position

Sampling the ground rows only and calling the signature a **total wipe** (0 of 7 ground rows
opaque in the two leftmost columns, against 6-7 everywhere else):

| scenes | reg `$0B` | bit 2 | total wipe |
|---|---|---|---|
| 0-9, 16-19 (fourteen) | `0x03` | 0 | **none** |
| 10, 12, 13, 14, 15 | `0x07` | 1 | **all five** |
| 11 | `0x07` | 1 | not at this sample |

Scene 11 is `Rocking` at a wobble phase where the column offset passes through zero — the
artifact's visibility oscillates with the deform, so a single sample can miss it. **Five of six
per-column scenes, none of the fourteen others.**

*(An earlier looser threshold — "x=0 shorter than x=16 by more than one row" — also flagged scene
17. That is terrain: 5 rows against 7, not a wipe. The threshold is stated here so the count is
reproducible rather than eyeballed.)*

## Why "exactly two columns", the detail nobody could explain

Per-column V-scroll on this hardware works in **16-pixel** columns. Sixteen pixels is **two
8-pixel tile columns**. The "two columns" everybody kept trying to derive from a block size or an
off-by-one is simply one VSRAM column — it was never a fill-window quantity at all.

## Two instruments that manufacture the absence — both bit me

1. **The warp rebuilds the column ring** (already noted above), and additionally **clears
   `$0B` bit 2**: warping after selecting scene 10 puts the mode back to `0x03`. So a
   warp-then-sample run reports clean *twice over*, for two independent reasons.
2. **Travelling re-applies the section's own scene.** Selecting scene 10 and *then* driving right
   leaves `Debug_Scene_Index` reading 10 while bit 2 has gone back to 0 — the cursor and the live
   mode disagree. Both of my first two A/B attempts compared two scenes with the mode off and
   reported a null result with nothing visibly wrong. **Read `$0B` bit 2 at the sample point;
   never trust the scene cursor.**

## The connection to a ruling already taken

**This is `d-27`.** That card asks about "a hardware limitation ... when a background layer
scrolls vertically per column, the leftmost eight pixels of the screen render at the wrong
vertical offset", and the owner answered: keep shipping it. But the card describes **eight
pixels on the background**, and what is actually on screen is **sixteen pixels on the
foreground, wiping the ground**. The engine already models the policy —
`SceneLeftColMask.{SpriteMask|Factor0Lock|Accept}` is mandatory on any scene attaching
`SceneVDeform.Columns` — and `Factor0Lock` reasons about plane B, so it cannot save plane A.

**The ruling was taken on a materially understated description, so it goes back to him** rather
than being treated as settled. Filed as its own decision card.
