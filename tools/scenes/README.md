# Effects gate scenes

`ab_runner` scenes (`oracle/linux-port/harness/ab_runner.py`) that drive a patch channel into each
of the three anchor states the raster schedule can be in, and capture the live raster program so a
gate can assert its shape.

```bash
python3 /home/volence/sonic_hacks/oracle/linux-port/harness/ab_runner.py \
  --old OLD.bin --new NEW.bin \
  --scene /home/volence/sonic_hacks/aeon/tools/scenes/effects_raster_suppressed.json \
  --out /tmp/abgate --selfcheck
```

`--selfcheck` runs OLD twice and aborts on disagreement (exit 2). **Treat that as a full stop**: a
nondeterministic scene invalidates everything downstream, and the cause is the scene, not the ROM.

## What the scenes pin, and why each poke is there

| poke | why |
|---|---|
| `Debug_Scene_Freeze = 1` | skips `Camera_Update`, so the written camera stays put. DEBUG shape only — hence `s4.debug.lst` |
| `Camera_Y = 144` | the latched line is `anchor - Camera_Y`, so pinning the camera is what makes the expected words derivable at all |
| `Effects_World_Y = N` | channel 0's world anchor — the only value that differs between the three scenes |

Channel 1 is deliberately **not** poked. Its preset anchor (314) puts it at latched line 170, below
its band floor, so it clamps UP to fire line 221 in all three scenes. That keeps the scenes free of
a hard-coded second address (`Effects_World_Y + 2`), which would rot the moment the RAM block moves.

Both raster buffers are captured plus `Raster_Active_Buf`, because `Raster_BuildSchedule` swaps
buffers every frame — a scene reading a fixed buffer would sample the stale one on half of all
frames and look stable while measuring nothing. The gate resolves the live one from the pointer.

## The expected words, DERIVED

Bands, in fire lines (`patchable` screen bands minus 1): channel 0 `2..219`, channel 1 `221..222`.
The arm word written at record *i* schedules the gap that lands record *i+2*, so its value is
`$8A00 | (this_fire - previous_fire - 1)` — the SLOT is two records back, the LINE delta is one.
Priming records occupy fire lines 0 and 1, so the first authored gap is measured from 1.

| scene | anchor | `L` | channel 0 | word 1 (priming 0) | word 3 (priming 1) |
|---|---|---|---|---|---|
| `mid_band` | 244 | 100 | fires at 99 | `$8A00\|(99-1-1)` = **`$8A61`** | `$8A00\|(221-99-1)` = **`$8A79`** |
| `suppressed` | 374 | 230 | **not emitted** (230 > 220) | `$8A00\|(221-1-1)` = **`$8ADB`** | **`$8AFF`** (parked) |
| `above_screen` | 100 | -44 | clamps UP to fire 2 | `$8A00\|(2-1-1)` = **`$8A00`** | `$8A00\|(221-2-1)` = **`$8ADA`** |

Word indices are into the live buffer: 0 = `pal_dirty_mask`, 1 = priming 0's arm, 2 = its op_count,
3 = priming 1's arm, 4 = its op_count, 5 = the first authored record's arm.

`$8C89` is the water fire's `OP_SET_REG` word (Shadow/Highlight on). It must be PRESENT in
`mid_band` and `above_screen` and ABSENT in `suppressed` — that absence is the parcel's whole
subject, and asserting it is what stops the gate from passing on a program that merely moved.

**Re-derive these rather than trusting the table.** If a derivation disagrees with a number here,
doubt the number first and the code second — two gates in the parcel that produced these scenes were
written against copied values and would have failed correct code.
