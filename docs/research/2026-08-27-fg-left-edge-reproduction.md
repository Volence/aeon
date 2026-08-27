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
