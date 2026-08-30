# The left-edge strip, sampled in VSRAM and the H-scroll table across frames — EXPLAINED

**2026-08-30, branch `measure/left-edge-vsram`, off master `82fb65a8`.** Subject: the owner's
sighting booked in `docs/DEFERRED_WORK.md` as *"THE LEFT EDGE STRIP ANIMATES FASTER THAN THE
BODY"* — *"the area that's like stuck in the bg is animating differently and super fast"*, red
arrow at the LEFT edge, effects lab, scene 14 at the time of the first measurement.

**Nothing here changes a ROM byte.** The deliverables are the instrument
(`tools/left_edge_vsram_probe.py`), this note, and the captures under
`docs/research/reference_captures/2026-08-30-left-edge-vsram/` (with their own README and
the run's complete raw output, `probe.log`, and every raw sample, `probe.json`).

| item | value |
|---|---|
| ROM | `s4.debug.bin`, **736,391 B, crc32 `0f6b1359`** (`DEBUG=1 ./build.sh`, canonical, exit 0) |
| assembler line | `Assembler: sigil 8951389a18c3 (clean at capture — no uncommitted changes)` — build.sh's own banner warns the binary predates sigil HEAD `036800fd`; a stale assembler emits an identical ROM when its source has not changed, and the ROM matches the owner's window's `romBytes 736391` |
| parallax / effects code since the sighting | `git log --oneline 6e2495a5..HEAD -- engine/level engine/effects games/sonic4/data/effects games/sonic4/test` is **empty** — verified, not assumed |
| instrument | `tools/left_edge_vsram_probe.py`, headless `oracle-aether` via `tools/aether_instance.py`; the owner's socket was never touched |
| run | `python3 tools/left_edge_vsram_probe.py --rom s4.debug.bin --lst s4.debug.lst --scenes 12,13,14 --frames 32 --out-dir docs/research/reference_captures/2026-08-30-left-edge-vsram` — exit 0, 10.0 s wall |
| clock | start `13:58:06 up 5 days, 5:47, load 4.41`; end `13:58:16 up 5 days, 5:47, load 5.30` |

---

## 1. Verdict: EXPLAINED

**The strip is plane B's own leading sliver on the Perspective scenes' shimmer rows, rendering
at the foreground's V-scroll instead of the background's, on a set of rows that changes every
frame.** It is the LEFT-edge half of the d-41 borrow's price, and the numbers name every part of
the mechanism:

1. **What the sliver reads.** `VSRAM[$4C] & VSRAM[$4E] & $7FF` equalled `Camera_Y & $7FF` on
   **every one of the 288 sampled frames** (nine runs of 32) — at rest it is the live camera Y,
   in motion it is the previous frame's camera Y, exactly as a producer that runs in the frame
   and an emitter that runs in VBlank must behave. That is the d-41 borrow doing its job:
   `engine/level/parallax.emp:2244`, `move.w d1, Parallax_Vscroll_Column_Buf + VSCROLL_COL19_BG_OFF`,
   copies camY into column-pair 19's plane-B word, so the AND is `camY & camY`.
2. **Plane A is not the strip.** The AND equalled pair 0's plane-A word (`VSRAM[$00]`) on
   **32/32 frames of all nine runs**. The plane-A sliver and the plane-A body read the same value
   in the same frame at the same rate — there is no rate, phase, or source difference on the
   foreground to see. (And at `Camera_X & 15 == 0`, the default position, plane A has no sliver
   at all: zero off-grain lines.)
3. **Plane B is.** On scenes 13 and 14, plane B's per-line H-scroll is off the 16-px grain on
   **70–87 of the 224 lines every frame** — all of them at or below line 112, which is exactly
   where `perspective_scene` (`games/sonic4/data/effects/ojz_scenes.emp:394-417`) turns the
   shimmer on for plane B (`dsb: 4` from world_y 112, `dsb: 2` from 160; `dsb: 15` = off above).
   Its distinct values are five: `0000 0001 0002 FFFE FFFF`. On every off-grain line the VDP
   renders plane B's leading `hscroll & 15` pixels at the AND value — that is Eke-Eke's
   hardware rule, Genesis Plus GX's `yscroll = vs[19] & (vs[19] >> 16)`, and Oracle's
   `plane_vscroll` (`oracle-core/src/render.rs:1172-1185`), which `plane_sample` (`:1195`)
   feeds with **each plane's own per-line hscroll**. Under the hardware rule the sliver is 14 or
   15 px wide on the `FFFE`/`FFFF` lines (22 + 29..36 lines per frame) and 1–2 px on the
   `0001`/`0002` lines (20 + 2); Oracle draws all of them 16 px (its ledgered divergence P4).
4. **The displacement.** Plane B is vertically LOCKED on these scenes (`v_factor: 15`;
   `Parallax_Current_Vscroll_BG` read 0 on every frame), so its body renders at pair 0's
   plane-B word — a constant `$0003`/`$0005` (scene 13) or `$0016` (scene 14) for the whole
   run — while the sliver renders at camY: **176 px** at the default position, **400 px** at
   the warp position, i.e. `camY − Vscroll_BG mod 512`. A strip of background from a different
   height, exactly where he pointed.
5. **Why it "animates super fast".** The shimmer phase advances every frame (`h_speed` 1 on
   scene 13, 2 on scene 14), so the SET of off-grain lines changes: **5–6 lines enter and 5–6
   leave per frame on scene 13, 10–12 in / 10–12 out on scene 14** — while every VSRAM word
   sits still. The strip's content is re-cut along different rows sixty times a second: rows
   snap between "background at its own height" and "background 176–400 px away" at frame
   rate. Nothing in the body does that. This is the "differently and super fast", and it is
   why the six-frame pixel diff could measure only a modest 1.27x — most of the strip's
   pixels are the same dark forest either way; the change is in which rows are torn, not in
   how many pixels move.
6. **Why he saw it only after d-41 ("this looks so much better, but…").** Before the borrow,
   `$4E` carried plane B's own word (`0 + wobble`), so the AND was `camY & small` ≈ small —
   plane B's sliver rendered near its own height and was invisible, while plane A's sliver
   was the broken one (d-40). The borrow moved the artifact from plane A to plane B's shimmer
   rows. `2026-08-29-vsram-column19-borrow.md` §4 predicted the split ("on those rows the
   sixteen split between the two edges") but priced it as sixteen static pixels; it did not
   say the rows would flicker.
7. **Scene 12 is clean, and that is the control.** `rocking_scene` gives plane B
   `DeformTable_Zero`, so its H-scroll is `0000` on all 224 lines at every position and every
   frame: **zero off-grain plane-B lines, zero in/out**. No plane-B sliver exists there, and
   plane A's sliver reads camY. If he saw the strip on scene 12, it was not this mechanism —
   the d-41 captures' scenes were 12 and 13, and this rules 12 out.

**Shown at more than one position:** default (`Camera_X` 96, `& 15 == 0`), warp
(`Camera_X` 360/376, `& 15 == 8`), and warp with the camera descending 16 px/frame — same
mechanism, same numbers, all three scenes.

---

## 2. The tables

Columns: `AND` = `VSRAM[$4C] & VSRAM[$4E] & $7FF` (what any sliver reads); `A0`/`B0` = pair 0's
plane-A/plane-B words (what the first full column of each plane reads; `B0` shown signed,
11-bit); `#offB` = lines where plane B's H-scroll `& 15 != 0`; `in/out` = lines entering /
leaving that set between consecutive frames; widths = lines per `hscroll & 15` on the last
frame (the hardware sliver width). All from `probe.json`; the full per-frame tables are in
`probe.log`.

### Scene 12 — Rocking_Fast

| position | camX | camY | `camX&15` | AND every frame | `AND==A0` | B0 (signed) | #offA | #offB | in/out per frame |
|---|---|---|---|---|---|---|---|---|---|
| default | 96 | 176 | 0 | `$0B0` = 176 = camY | 32/32 | rocks −20..+19 (deform, phase +3/frame) | 0 | **0** | 0/0 |
| warp | 360 | 400 | 8 | `$190` = 400 = camY | 32/32 | rocks −20..+19 | 224 | **0** | 0/0 |
| warp + DOWN | 360 | 400→848 | 8 | steps +16/frame with camY (ΔAND = ΔA0 = +16 on 31/31 transitions) | 32/32 | rocks −20..+20 | 224 | **0** | 0/0 |

Plane B H-scroll: one distinct value, `0000`, all 224 lines, all frames. Widths: `0px:224`.

### Scene 13 — Perspective_Subtle (`h_speed 1, v_speed 0`)

| position | camX | camY | `camX&15` | AND every frame | `AND==A0` | B0 | #offA | #offB | in/out per frame | widths (last frame) |
|---|---|---|---|---|---|---|---|---|---|---|
| default | 96 | 176 | 0 | `$0B0` = 176 | 32/32 | **3, constant** | 0 | 71–87 | 5–6 / 5–6 | 0px:144 1px:20 2px:2 14px:22 15px:36 |
| warp | 376 | 400 | 8 | `$190` = 400 | 32/32 | **5, constant** | 224 | 70–86 | 5–6 / 5–6 | 0px:151 1px:20 2px:2 14px:22 15px:29 |
| warp + DOWN | 376 | 400→848 | 8 | +16/frame with camY | 32/32 | **5, constant** | 224 | 70–85 | 0–6 / 0–6 | 0px:150 1px:20 2px:2 14px:22 15px:30 |

Off-grain plane-B lines (default, last frame): `119-134, 151-166, 169-179, 182-198, 201-211,
215-223` — nothing above 112. Displacement of the sliver vs the body: 176 − 3 = **173 px**
(default), 400 − 5 = **395 px** (warp).

### Scene 14 — Perspective (`h_speed 2, v_speed 1`)

| position | camX | camY | `camX&15` | AND every frame | `AND==A0` | B0 | #offA | #offB | in/out per frame | widths (last frame) |
|---|---|---|---|---|---|---|---|---|---|---|
| default | 96 | 176 | 0 | `$0B0` = 176 | 32/32 | **22, constant** | 0 | 71–85 | 0–12 / 0–12 (10–12 on all but the flat frames) | 0px:146 1px:20 2px:2 14px:22 15px:34 |
| warp | 360 | 400 | 8 | `$190` = 400 | 32/32 | **22, constant** | 224 | 71–86 | 10–12 / 10–12 | 0px:149 1px:20 2px:2 14px:22 15px:31 |
| warp + DOWN | 360 | 400→880 | 8 | +16/frame with camY | 32/32 | **22, constant** | 224 | 70–85 | 10–12 / 10–12 | 0px:150 1px:20 2px:2 14px:22 15px:30 |

Off-grain plane-B lines (default, last frame): `112-120, 137-151, 160-165, 169-184, 187-197,
201-216, …` (7 runs). Displacement: 176 − 22 = **154 px** (default), 400 − 22 = **378 px**
(warp).

### The rate question, answered directly

| what moves | at rest | camera descending 16 px/frame |
|---|---|---|
| Camera_Y | 0 | +16 (read at the frame boundary it shows as 0/+32 pairs — the camera hops; VSRAM smooths it to +16 because the emitter ships the previous frame's value) |
| the sliver's value (AND) | 0 | **+16/frame**, = ΔA0 on 31/31 transitions, all three scenes |
| plane A body (A0) | 0 | +16/frame |
| plane B body (B0), scenes 13/14 | 0 (locked) | **0 (locked)** |
| plane B body (B0), scene 12 | ±6/frame rocking | ±6/frame rocking |
| plane B off-grain line set, 13/14 | **5–12 lines in and out per frame** | same |
| plane B off-grain line set, 12 | empty | empty |

So on scenes 13/14 the plane-B sliver moves at **plane A's rate** (1:1 with the camera) while
plane B's body is locked, AND its row membership re-cuts at frame rate at rest. Both halves of
"animating differently and super fast", and both from the same two facts: `$4E = camY` and a
per-line plane-B H-scroll that leaves the grain.

### Producer vs VDP copy

`Hscroll_Buffer` (RAM) vs the VRAM H-scroll table at `(reg $0D & $3F) << 10`, and
`Parallax_Vscroll_Column_Buf` vs VSRAM (11-bit): identical at the sample point on 32/32 frames
in eight runs, 31/32 in one (scene 13 moving — one frame where the RAM copy was a frame ahead;
the VDP copy is what the tables above read). VSRAM is written once per frame in VBlank
(`Vscroll_Write requires(vblank)`), so per-frame sampling is the right grain; no
`run_to_scanline` sampling was needed.

---

## 3. d-32 re-measure — the left-edge ground glitch is ABSENT on this build (with the numbers)

The still-owed re-measure needed a frame with `Camera_X & 15 != 0` **and** plane A reaching the
left edge — the retracted attempt had neither. The probe warps to `Camera_X & 15 == 8` and then
walks the camera down in 96-px steps until columns 16/24 carry plane A over rows 96..216; at
the default Y (sky) and Y+96 they carry none (0/32 cells), at Y+192 they do.

Plane-A `opaque` from `pixel_attribution`, x = 0..15 then 16 and 24, rows 96..216 step 8
(`#` opaque, `.` transparent), at the warp position:

**Scene 12 and scene 14, `Camera_X = 360 (&15 = 8), Camera_Y = 400`** — identical grids:

```
y=96..184   ................  ..
y=192       #####...#.####.#  .#
y=200       ################  ##
y=208       ################  ##
y=216       ################  ##
opaque rows per column: 4 4 4 4 4 3 3 3 4 3 4 4 4 4 3 4 | x16=3 x24=4
```

**Scene 13, `Camera_X = 376 (&15 = 8), Camera_Y = 400`:**

```
y=96..152   ................  ..
y=160..184  ................  .#
y=192       ...#############  ##
y=200       ################  ##
y=208       ################  ##
y=216       ################  ##
opaque rows per column: 3 3 3 4 4 4 4 4 4 4 4 4 4 4 4 4 | x16=4 x24=8
```

**Reading.** The defect's signature (2026-08-27 reproduction) was the two leftmost columns
carrying NO ground band while x ≥ 16 carried one. Here rows 200–216 are opaque across all
sixteen leftmost pixels and at x=16/24 alike, on all three scenes. Row 192 is a terrain edge,
not a strip: at x=360 it is the same broken `#####...#.####.#` pattern at x=0..15 as the `.#`
at 16/24 (a slope crossing the sample row), and at x=376 the three transparent pixels at
x=0..2 sit inside a sliver that is 8 px wide on hardware and 16 in Oracle — a V-scroll
displacement would move all of x=0..7 together, not three pixels of it. Consistent with
§1 item 2: the plane-A sliver reads `$190` = 400 = camY on every frame here.
**Absent, measured at `&15 = 8` with ground present, three scenes.** The remaining caveat is
the one every left-edge picture on this tree carries: the sliver's WIDTH is Oracle's flat 16
where hardware says `hscroll & 15`; the VALUE the sliver reads is the hardware-tested half and
it is what these numbers assert.

---

## 4. What was eliminated, and what is not claimed

- **Rate difference on plane A** — eliminated: `AND == A0`, 288/288 frames, at rest and in motion.
- **Phase difference on plane A** — eliminated: same frame, same word.
- **A different SOURCE for the plane-A sliver** — eliminated: it is `camY & camY`.
- **Scene 12 as the sighting's scene** — eliminated for this mechanism: no off-grain plane-B line at any position.
- **NOT claimed:** what the strip looks like on real silicon beyond the hardware-tested
  value rule. Oracle draws every off-grain plane-B line's sliver 16 px wide; hardware would
  draw 14–15 px on the 51–58 negative-hscroll lines and 1–2 px on the 22 positive ones. The
  displacement and the per-frame re-cut are the same either way.
- **NOT claimed:** that the pictures prove it. The composed `*-left.png` crops are raster
  frames (`source == "raster"` asserted); the `*-planeB-stateRender-left.png` crops are what
  they say — a per-line render of the paused machine's VDP state with plane A and sprites
  masked (the server returns the retained raster only with all layers on), included so the
  reader can see plane B's edge alone. They corroborate; the VSRAM/H-scroll numbers are the
  evidence.

---

## 5. What follows (booked, not done here)

The mechanism is the borrow's price on the left edge. The options are the ones the borrow note
already laid out and none of them is free: keep it (Gynoug's answer, now with a flicker on the
Perspective family's shimmer rows), lock plane B's H-scroll to the grain on those rows (the
shimmer is ±2 px, so `dsb` on the hills/ground layers is the whole cost), or make the borrow
per-scene (a byte-moving config-record change). That is an owner decision with a picture in
front of him; this note is the measurement it needs.
