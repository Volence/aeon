# Effects gate scenes

`ab_runner` scenes (`oracle/linux-port/harness/ab_runner.py`). Three of them drive a patch channel
into each of the anchor states the SPARSE raster schedule can be in and capture the live raster
program so a gate can assert its shape; the fourth (`effects_raster_dense`) drives the DENSE tier
and is documented at the bottom of this file.

**Pass the ROM path ABSOLUTE.** `ab_runner` does not resolve it, and `headless_emulator` launches
`oracle_gui` with `env -C <oracle repo>`, so a relative `--old s4.debug.bin` resolves against the
EMULATOR's cwd. Nothing errors: the ROM silently fails to load, every poke and read answers ok
against blank RAM, and the run reports `ALL EQUAL` on a pair of pattern-filled captures. Two
different scenes returning the same `state_hash` is the tell. (`tools/effects_gates.py` resolves
the path itself, so this bites hand runs only — it cost this parcel twenty minutes.)

**The committed scenes carry NO listing path.** Their top-level `symbols` key is the placeholder
`$LST`; `tools/effects_gates.py` (`resolve_scene()`) writes a copy with `symbols` set to the
`--lst` under test beside each run's output and hands THAT to `ab_runner`. Until 2026-08-26 every
scene hardcoded the MAIN tree's `s4.debug.lst`, so a worktree's gates resolved master's RAM
addresses: the showcase parcel moved `Raster_Buf_A/_B/Raster_Active_Buf` by +84 B and all four
`scene:*` shape gates failed with "`Raster_Active_Buf points at 0x438aff`, which is neither captured
buffer" while their determinism halves passed (two runs of a stale capture agree perfectly).
Passing a raw committed scene to `ab_runner` by hand will fail loudly at `load_symbols("$LST")` —
resolve it first:

```bash
SCENE=$(python3 tools/effects_gates.py --resolve-scene suppressed --lst /ABS/PATH/s4.debug.lst)
python3 "$(python3 -c 'import sys; sys.path.insert(0, "tools"); from suite_paths import harness_path; print(harness_path())')/ab_runner.py" \
  --old OLD.bin --new NEW.bin --scene "$SCENE" --out /tmp/abgate --selfcheck
```

(or simply `python3 tools/effects_gates.py --only scene:suppressed --rom /ABS/s4.debug.bin --lst
/ABS/s4.debug.lst`, which does all of it and asserts the shape too).

`--selfcheck` runs OLD twice and aborts on disagreement (exit 2). **Treat that as a full stop**: a
nondeterministic scene invalidates everything downstream, and the cause is the scene, not the ROM.

## What the scenes pin, and why each poke is there

| poke | why |
|---|---|
| `Debug_Scene_Freeze = 1` | skips `Camera_Update`, so the written camera stays put. DEBUG shape only — hence `s4.debug.lst` |
| `Camera_Y = 144` | the latched line is `anchor - Camera_Y`, so pinning the camera is what makes the expected words derivable at all |
| `Effects_Motion_Any = 0` | **disarms the anchor mover** for the fixture. Added by EFFECTS-W1 item 4 (2026-09-03), which made `Effects_LatchWorldLines` add a per-channel sine sweep to the latched line: `OJZ_Preset_Sec0` authors `anchor_sweep(4, 1)` on channel 0, so without this poke the derived line would be `anchor - camera + (a 32 px peak-to-peak term)` and every expectation below would be a function of the frame the capture happened to land on. The mover deliberately runs **outside** `Debug_Scene_Freeze` (a frozen camera still has to be latched), so freezing the scene does **not** hold it still — this poke is what does, and it is one poke rather than four because the once-per-frame gate word is what the mover tests first. These gates measure `Raster_BuildSchedule`, not the mover; holding the mover fixed is varying one thing. |
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

## `effects_raster_dense` — the dense tier (added 2026-08-19, Tier-3 item 3)

Everything above is the SPARSE tier. The dense tier — `OP_RUN_GRADIENT`, the every-line body — had
no scene, no gate and no cost row until this parcel, while costing about 27% of a frame on the
shipped content. Three prior sessions established that gap; this scene closes half of it (the other
half is `raster_cost_probe`'s FD1/FD2 pair and `RASTER_DENSE_LINE_GRAD_CYC`).

**How it reaches the dense program.** `OJZ_TestGradient` lives on OJZ act 1 SECTION 2, so the scene
has to get the camera there. It does not navigate: it pokes `Camera_X` past the section boundary and
lets `Parallax_CheckBoundary` — which is edge-triggered on the section under the camera centre and
runs OUTSIDE the `Debug_Scene_Freeze` gate — install `OJZ_Preset_Sec2` itself.

| poke | why |
|---|---|
| `Debug_Scene_Freeze = 1` | as above: `Camera_Update` is skipped so the written camera stays put |
| `Camera_Y = 144` | `(144 + 112) >> SECTION_SIZE_SHIFT` = section row 0 |
| `Camera_X = 4960` | `(4960 + 160) >> 11` = section column 2, and `GRID_W` is 3, so flat section 2 |

`run_frames: 12` after the poke. **The settle is measured, not guessed:** at 3 frames
`Raster_Program` already points at `OJZ_TestGradient` but `Raster_Dense_Cmd` is still zero — the
program is installed a frame or two before the handler has walked its setup record — and the scene
would have captured a live program that had never run. 12 leaves margin. A settle that is too short
cannot pass vacuously here, because the gate asserts the run's END STATE and an unrun program fails
it loudly.

**What it asserts, and why the cursor is the one that counts.** The program half checks the words
`raster_gradient_program` emitted (the two priming arms, the setup record's arm, the opcode, the
line count, the command longword). The runtime half checks `Raster_Dense_Cursor`:

    Raster_Dense_Cursor == OJZ_GradientStream + OJZ_GRAD_LINES * RASTER_DENSE_WORDS_PER_LINE * 2

The dense body advances the cursor three words per line, so that equality holds if and only if the
body ran **exactly** `OJZ_GRAD_LINES` times from the right base. Nothing else in the scene can see
that: CRAM is re-asserted at frame top (so a post-frame `read_cram` reads the base palette — see
`ojz_effects.emp`'s note on why the framebuffer was the correct instrument for the original P2
gate), and the program words are ROM and identical whatever the handler did with them.

Both halves are red-first proven (2026-08-19). Dropping ONE of the three `move.w (a1)+, VDP_DATA`
from `.dense_body` lands the cursor at `stream + 96 * 2 * 2` and the gate names the exact word; a
behaviour-neutral extra instruction in the same body leaves this gate GREEN and turns the cost row
RED, which is the pair of poisons that shows the two gates are measuring different things.
