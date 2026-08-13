# Effects P2 — gate evidence (oracle, 2026-08-13)

Structured after `docs/benchmarks/effects-p1/GATE-EVIDENCE.md`: method, result
table, residuals, and an explicit NOT-verified section.

---

## Dense tier — `OP_RUN_GRADIENT` (plan Task 5, Step 4)

ROM: `s4.debug.bin` crc=`77d75ad9` len=711122, from `feat/effects-p2-palette`
paired with sigil `feat/effects-p2`. Fixture: `OJZ_TestGradient` on OJZ act-1
**section 2**, a 96-line run authored to start at screen line 96.

### Method — per-row colour, chosen so art cannot confound it

The claim under test is "the handler writes the authored stream value on each of
96 consecutive lines". Two candidate measurements were considered and one was
rejected on evidence:

- **Rejected: per-scanline CRAM reads** (`run_to_scanline` + `read_cram`). Read at
  scanline 100 the CRAM returned the *base* palette, not the stream value, at every
  sampled line. Oracle's CRAM read is frame-latched, so it cannot see a mid-frame
  write. Recorded here so it is not re-attempted.
- **Used: per-row framebuffer colour.** The gradient writes CRAM line 2 entries
  4/5/6 with three DIFFERENT words at the same ramp level — entry 4 pure blue,
  entry 5 blue+green, entry 6 **blue+red**. `OJZ_TestPal` (section 2's base
  palette) has red = 0 in *every* entry, so a pixel with `g == 0 && r == b && r > 0`
  can only come from the gradient's entry-6 write. That makes the signal
  unfalsifiable by art coverage, which is precisely what defeated the first P1
  attempt (see P1's CORRECTION).

The emulator decodes a 3-bit component as `v * 34`, so ramp level L reads as
`34*L` (L7 = 238 — the same 238 P1's red target decoded to).

### Result — the run lands exactly where authored

| ramp level | measured first row | authored first row (`96 + L*12`) |
|---|---|---|
| L1 (34)  | 108 | 108 |
| L2 (68)  | 120 | 120 |
| L3 (102) | 132 | 132 |
| L4 (136) | 144 | 144 |
| L5 (170) | 156 | 156 |
| L6 (204) | 168 | 168 |
| L7 (238) | 180 | 180 |

Seven of seven exact. L0 is `$0000` (black, r = 0) and so is correctly invisible to
the red-channel discriminator. Bands are 12 rows each, monotonically increasing —
8 distinct levels over 96 lines is the *whole* of CRAM's 3-bit-per-channel range,
so 8 steps (not 96) is the correct pass criterion.

### The ENTER schedule is CALIBRATED, not derived — the off-by-one this caught

The first build authored the `OP_RUN_GRADIENT` setup fire at `T-2`, which is what
the sparse tier's fire-line rule (`fire = M-1`, then the handler write shows on
`M`) predicts. On hardware that put the entire run **one line high** — every one
of the seven boundaries measured at `96 + L*12 - 1` (107/119/131/143/155/167/179),
a uniform −1, i.e. `stream[0]` displayed on line 95 rather than 96.

Moving the setup fire to `T-1` produced the exact table above. The dense path does
not inherit the sparse tier's extra −1 because **entering the run costs its own
pipelined arm** (survey Ruling 1b, at the ENTER edge), which absorbs one line. The
constructor `raster_gradient_program` now encodes `T-1`, with this measurement
cited in-module so it is not "corrected" back on the next reading.

### Residual: a dense run leaves its last value latched below the run

L7 measures as rows 180..**223** rather than 180..191. This is correct behaviour
for the program as authored, not a defect: the run ends at line 191 and nothing
restores the base palette for the remainder of the frame, so the final stream value
stays in CRAM until the next frame top, where `pal_dirty_mask %0100` re-asserts
line 2. Real content wanting the base palette back below a run must author a
restoring op after it. Consequence for authors, and the reason the run's END line
is not directly observable by this method.

### Residual: the row-119 partial tint recurs at dense boundaries — and alternates

Boundary rows 132, 156 and 180 carry **both** the outgoing and incoming level;
boundary rows 108, 120, 144 and 168 carry only the incoming one. Every other
boundary, in a stable pattern. This is the P1 row-119 artifact (the CRAM write
landing inside the following line's active display, survey Ruling 2b) generalised:
a dense run produces one such transition per level change, and whether the write
clears the line edge alternates with sub-line timing drift.

This is useful to Task 4 as *corroboration* but is the weaker instrument for the
A/B: entry 6 is a sparse colour in OJZ's art (1-4 px per row), whereas P1's entry-5
target is the dominant ground colour at ~70 px per row. **Task 4's A/B should be
measured on the P1 fixture's entry 5, not here.**

### NOT verified in this run

- The run's exact END line (masked by the latch residual above).
- Per-line cycle cost / the `NEEDS-MEASUREMENT` rows of
  `tools/effects_budget_model.toml` — profiling is separate from this gate.
- Behaviour under motion. This capture is a static camera parked in section 2.
  P1's mid-scroll rule exists because *art coverage* confounds a pixel count; the
  discriminator used here is art-independent, so a static frame is sound for this
  claim — but a moving-camera capture is still owed before the tier is called done.
- Whether a second dense run in the same frame re-arms correctly (single run only).

### Re-verified on the final ROM

Re-run after the Task-4 decision below changed the handler: crc `fa5c04e5`, all seven
boundaries still exact. The dense body does not use `OP_CRAM`, so the blanking delay
does not touch it — confirmed rather than assumed.

### Reproduction

The fixture sits on section 2, which is reached from spawn only past the authored
test wall at x=464. Recipe that works:

1. Debug ROM boots INTO debug-fly. Confirm `debug_flag` (player SST `+$3C`) reads
   `$FF` **before** teleporting — a physics-mode teleport drops the player into the
   pit at x≈4068 and he lands in section **8** (grid row 2), where `sec_raster_table`
   is 0 and "0 = keep current" silently leaves section 1's program installed. That
   reads exactly like a failed install and cost a full debug cycle here.
2. Player SST base is **`$FF8D86`** on this branch — NOT the `$FF8BA4` in the
   2026-08-12 handoff. Effects P2's `Palette_State` shifted the RAM layout. Take the
   address from `emulator_player_state`, never from a doc.
3. Write `x_pos` (`+$02`) = 4600, `y_pos` (`+$06`) = 500, then let the emulator run
   ~8 s: the camera is soft-clamped (art-streaming P2c) and converges to the
   teleport over several hundred frames rather than snapping.
4. Confirm `Raster_Program` holds `OJZ_TestGradient` before capturing.

---

## Row-119 partial tint — the A/B (plan Task 4) and S/H (plan Task 7 Step 3 / §4.5)

Fixture: `OJZ_TestRaster` on OJZ act-1 **section 1** (the P1 gate program). Both
builds captured at an **identical, fully-converged camera (2840, 356)** — the first
attempt compared (2856, 420) against (2840, 356) because the camera had not finished
converging, which would have made the pixel counts incomparable. Wait for
`Camera_X`/`Camera_Y` to stop changing, not for a fixed number of seconds.

### The measurement colour is NOT P1's (238,0,0)

Counting exact `(238,0,0)` returned **zero pixels on every row** — and that is not a
failure, it is S/H. Below the split every colour is exactly halved:
`(0,68,34)→(0,34,17)`, `(68,34,34)→(34,17,17)`, and the raster's red target
`(238,0,0)→(119,0,0)`. The correct discriminator below an S/H boundary is the
**shadowed** value. P1's number predates S/H actually working.

### Result

| | (a) fire early | (b) blanking delay |
|---|---|---|
| row 118 red px | 0 | 0 |
| **row 119 red px** | **1** | **0** |
| row 120 red px | 8 | 8 |
| first affected row | **119** | **120** (the authored line) |
| affected rows total | 97 | 96 |
| mean brightness 108-117 → 121-130 | 15.83 → 8.10 | 15.83 → 8.10 |

**(b) ADOPTED.** It removes the partial tint and puts the boundary on the authored
line. Option (a) is DELETED — it never removed the artifact by construction, and its
helper `raster_fire_screen` turned out to be **imported but never called**, so it was
dead code that had never affected a shipped program. Deleting it changed **zero
bytes** (debug crc `fa5c04e5` identical before and after), which is the proof it was
dead.

### S/H is PROVEN — closes the P1 residual and handoff §4.5

Mean row brightness steps **15.83 → 8.10 across the boundary, a 1.95x step DOWN**,
in the correct direction, at a boundary where the art is uniform. The prior note that
OJZ's art is all high-priority and S/H therefore undemonstrable is **wrong for
section 1**: the spawn-area art is low-priority and visibly shadows. This satisfies
plan Task 7 Step 3's requirement without any content change.

### Residual: the mode-register half of a fire still switches mid-line

The blanking delay guards the CRAM paths only. Column-bucket brightness across row
119 (32 px buckets) shows the S/H register taking effect ~45% of the way across the
line, **identically in both options**:

```
row 118:   5.3  10.3  25.1   7.8   5.3  10.3  25.1   7.8   5.3  10.3   (all unshadowed)
row 119:  10.3  10.3  22.3   2.8   5.1   5.1  10.8   1.4   5.1   5.1   (switch ~bucket 3)
row 120:   6.6   5.5  13.1   2.5   6.6   5.5  13.1   2.5   6.6   5.5   (all shadowed)
```

Extending the delay to `OP_SET_REG` would cost ~40 more cycles of a ~60-cycle budget
and was NOT taken without a cycle measurement to justify it. Authors wanting a
pixel-clean mode change should schedule it one line earlier. Left open deliberately.
