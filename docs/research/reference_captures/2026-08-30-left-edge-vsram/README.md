# The left-edge strip — VSRAM + H-scroll sample, captured

Captured 2026-08-30 by `tools/left_edge_vsram_probe.py` for the owner's sighting *"the area
that's like stuck in the bg is animating differently and super fast"* (left edge, effects lab).
**These are corroboration for a measurement, not a gate.** The measurement is
`docs/research/2026-08-30-left-edge-vsram-sample.md`; the raw output of the run that produced
every file here is `probe-output.txt`, and every raw sample (VSRAM, both H-scroll tables, the column
buffer, camera, per-line off-grain sets, the attribution grids) is `probe.json`.

The probe refuses rather than guessing: the served ROM is checked against the file on disk, the
scene cursor must land where it was driven, VDP reg `$0B` bit 2 is re-read at every sample
point (the DEBUG warp clears it, so the scene is re-installed after every warp), the warp must
ack, and the composed captures assert `source == "raster"`.

| ROM | build | `s4.debug.bin` crc32 |
|---|---|---|
| all | aeon `82fb65a8` (master at capture; the measurement branch changes no ROM byte) | `0f6b1359` (736,391 B) |

Assembler `sigil 8951389a18c3` (build.sh's banner: the binary predates sigil HEAD `036800fd`;
the ROM matches the owner's window's 736,391 B). Headless `oracle-aether` via
`tools/aether_instance.py`; the owner's socket was never touched.

Run: `13:58:06 up 5 days, 5:47` to `13:58:16`, 10.0 s wall, exit 0.

## Files

Per scene (12 = Rocking_Fast, 13 = Perspective_Subtle, 14 = Perspective) and per position
(`default` = `Camera_X 96, Camera_Y 176`, `& 15 == 0`; `warp` = `Camera_X 360` (376 on scene
13), `Camera_Y 400`, `& 15 == 8`):

- `sceneNN-<pos>-full.png` — the composed raster frame, 320x224, untouched.
- `sceneNN-<pos>-left.png` — x 0..31 of that frame, 6x. The strip he pointed at.
- `sceneNN-<pos>-planeB-stateRender-full.png` / `-left.png` — the same machine with plane A,
  sprites and window MASKED, so plane B's edge is visible alone. **A state render, not a raster
  frame**: the server returns the retained raster only when every layer is on, and renders a
  masked picture per line from the paused VDP state. Mid-frame effects are absent from it;
  there are none in play at these positions, but it is labelled for what it is.

## What to look at

**Scene 14 / 13, `planeB-stateRender-left`** (the pair to read first). What the numbers say
the crop contains: above line 112 no plane-B line is off-grain, so the left 16 px are the
same background as the body; from line 112 down, 70–87 lines per frame are off-grain and on
each of those the leftmost 16 px (Oracle's width) render plane B at the foreground's V-scroll
(400 px away at the warp position, 176 at the default) instead of the background's — a strip
cut along horizontal seams that the body to its right does not have. In the 6x crop the lower
half does read as more broken than the upper half, but the reader should trust `probe-output.txt`'s
per-line `hsB` column over an eyeballed seam. Which rows are cut changes every frame; a still
cannot show that, `probe-output.txt`'s `in/out` column does (5–6 lines per frame on 13, 10–12 on 14).

**Scene 12, `planeB-stateRender-left`** — the control. No seams: plane B's H-scroll is `0000`
on all 224 lines, so no plane-B sliver exists.

**`*-warp-left.png`** (composed) — the ground rows 192–223 are continuous into x=0; that is the
d-32 grid in the note (`#` on all sixteen leftmost pixels at rows 200–216).

## The limit these pictures carry

The sliver's WIDTH is Oracle's flat 16 px; hardware and GPGX draw `hscroll & 15` — 14–15 px on
the negative-hscroll lines (most of them), 1–2 px on the positive ones. The VALUE the sliver
reads is the hardware-tested half and is what the note's numbers assert.
