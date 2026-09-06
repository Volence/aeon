# LIVE-EFFECTS — the RAM surface an Oracle panel writes

For the oracle lane, so a panel is built against a stated contract rather than a struct
inferred from bytes. Everything below is **measured from this tree and from a running
window**, not derived from source alone; where something is not measured it says so.

Written 2026-09-06T15:52:24Z against aeon master `852f1a85`; addresses read from `s4.debug.lst`.

## 1. The three selectors — write these, never `Debug_Lab_Index`

| what | symbol | address | width | shape |
|---|---|---|---|---|
| parallax scene | `Parallax_Current_Config` | `$FFFF88EC` | u32 | **both** (release + debug) |
| raster program | `Raster_Program` | `$FFFF8BD6` | u32 | **both** |
| band table | `BgAnim_Table_Ptr` | `$FFFFE91A` | u32 | **DEBUG ONLY** |

Each holds a **pointer**, and the engine **re-reads it every frame** — `Parallax_Update`
lists `Parallax_Current_Config` under its own *Reads*, and the raster build does
`move.l Raster_Program, d0` per frame. **So a write takes effect on the next frame with no
engine change.** Observed live across two lab rows: `Raster_Program` held `Raster_Buf_B`
(RAM) on the floor row and `EditorRaster_OJZ_Act1_aurora_ramp_witness` (ROM) on another.

**`Debug_Lab_Index` (`$FFFFEE0D`, u8) is the CHORD'S CURSOR ONLY.** Writing it moves the
on-screen label and changes nothing that runs. This cost this lane an hour today — the
label said one row while the machine ran another.

**`Raster_Program` = 0 means no program**, and the engine short-circuits on it
(`beq` after the read). `BgAnim_Table_Ptr` = 0 is **never valid**; `BgAnim_Init` seeds it.

**Shape warning: the band selector does not exist in a release build.** A panel that offers
band switching must gate on the shape, or it will write a RAM address that is something
else entirely. The other two are present in both.

## 2. The band table layout

```
BgAnim_Table:  u16  count            // number of records that FOLLOW
               band[count]           // 44 bytes each, contiguous
```

`count` is how many of the following records the walk reads, so a **table whose count is 0
turns the whole system off** — that is exactly how the shipped act boots silent.
`BGANIM_MAX_BANDS` = 4.

One record, `struct bganim_band`, **44 bytes**, pinned by an `ensure` in
`engine/level/bg_anim.emp`:

| off | field | type | meaning / range |
|---|---|---|---|
| 0 | `driver` | u16 | **0 = Camera_X, 1 = Camera_Y, 2 = Logic_Tick.** Only these three |
| 2 | `rate_shift` | u16 | `step = driver_value >> rate_shift`. Larger = slower |
| 4 | `step_mask` | u16 | pattern period along the axis **in px, minus 1** (so 63 = 64 px). Must be `2^n - 1` |
| 6 | `col_shift` | u16 | **log2 of the rotation UNIT in bytes.** Historical name: `rows*32` horizontal, `cols*32` vertical |
| 8 | `tile_count` | u16 | tiles in the band |
| 10 | `vram_dest` | u16 | **VRAM byte address** of the band's first slot |
| 12..44 | `banks` | u32 x 8 | pointers to the 8 pre-shifted art banks, 1 px apart |

**Worked example, the shipped act's band 0**, straight out of the generated module:
`[0, 4, 63, 7, 32, $8000]` = Camera_X driven, 1 px per 16 units, 64 px period, rotation
unit 128 B, 32 tiles, first slot at VRAM $8000.

**The fields a panel can usefully nudge are `driver` and `rate_shift`.** `step_mask` and
`col_shift` are geometry derived from the art's shape — changing either without changing
the art gives a cadence the art does not have, which is a picture rather than an effect.
`vram_dest` and `banks` are placement and would need the art moved.

## 3. Bands-off has NO canonical target — a real gap, named rather than papered over

There is **no `BgAnim_Table_Empty` symbol in this tree.** Bands-off means pointing
`BgAnim_Table_Ptr` at a `u16` containing 0. The shipped act's own `BgAnim_Table` happens to
be exactly that (it is `default_off`), so it works today **by coincidence of content, not by
contract** — an act with live bands has a non-zero count there.

**Two ways to close it, and the second is mine to do if oracle wants it:** the panel supplies
its own zero word in RAM and points at that; or aeon adds a 2-byte `BgAnim_Table_Empty`
constant so bands-off has a stable, act-independent target. **Say which and I will land the
second — it is two bytes.**

## 4. Nudging parameters: NOT YET, and this is the S hook

`Parallax_Current_Config` points at **ROM**, so a scene's factors cannot be edited in place.
The hook is the live-palette shape: a **RAM scratch config**, plus an entry point that copies
the active ROM config into it and re-points the selector; the panel then edits the RAM copy
and the next frame picks it up.

**The pattern already exists on the raster channel** — `Raster_Buf_A` (`$FFFF8BE4`) and
`Raster_Buf_B` (`$FFFF8C64`), 128 B each (`RASTER_BUF_SIZE`), are RAM working copies and
`Raster_Program` legitimately points at them. So this is copying a shape, not inventing one.
**Until it lands, a nudge control has nothing to write and should not ship** — a slider that
silently does nothing is worse than an absent one.

## 5. The torn-frame caveat DISSOLVES under pause-write-resume — oracle's correction, accepted

I flagged that a mid-frame write races the once-per-frame read. **Oracle is right that a
paused write cannot land mid-frame**, so the pause-write-resume flow the owner already
accepted (*"a small pause to pause and unpause for the change is fine"*) removes it entirely.
**The caveat stands only for a write to a running machine**, which is the scripted-sweep case
and not the panel's.
