# Runtime witnesses: EFX-4b, C1b-3 with physics, C3b-2 (2026-09-12)

Worktree helper for the aeon controller, branch `witness/raster-collision-0912` (cut from master
`9fe9ee91`). Headless only: every emulator was an `oracle-aether` spawned through
`tools/aether_instance.py` (implementation `oracle-rs`, handshake asserted). No emulator MCP
tool was called, and no socket was dialled except the ones those spawns created. No `.emp` was
changed and nothing was built.

## ROM, instrument, command

- **ROM:** `/home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.bin`, **crc32 `9ce1c2ff`, 847533 B**,
  and the `s4.debug.lst` beside it. Its `DIGEST-ROM` row names the same crc. That tree is clean
  at master `9fe9ee91`. It was only read.
- **Symbols:** loaded into every spawn; the server refuses a listing that does not bind to the
  ROM.
- **Source inputs:** every derived value comes from this worktree, which is also `9fe9ee91`.
  The tool proves each input file is the build's before using it:

  | file | how it was proven |
  |---|---|
  | `engine/effects/raster.emp` | crc `58fa755c` = the listing's DIGEST-READ |
  | `engine/effects/raster_dsl.emp` | crc `672be671` = DIGEST-READ |
  | `games/sonic4/test/ojz_scroll_test.emp` | crc `ce7dc444` = DIGEST-READ |
  | `games/sonic4/player/player_common.emp` | crc `04329bef` = DIGEST-READ |
  | editor planes `section_0.collattr{,b}.bin` | byte-identical to the ROM tree's copies (sigil does not read them, so there is no digest row) |
  | base bank `collision/base/{heightmaps,angles}.bin` | byte-identical to the ROM tree's copies |

- **Tool:** `tools/lens_residue_raster_witness.py` at `9de327c7`. It is a witness tool, not a
  gate: build.sh and pytest do not run it.
- **Final command,** run from the worktree root:

  ```
  python3 tools/lens_residue_raster_witness.py all --lag-budget 3000 \
      --rom /home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.bin \
      --lst /home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.lst --expect-crc 9ce1c2ff
  ```

  Result: **exit 0**, `finished=0`. It ran from 2026-09-12T14:37:52Z to 14:39:41Z (`date -u`):
  efx4b took 1.0 s, c1b3 2.8 s and c3b2 104.5 s of wall time. `uptime` load average at the end
  was 7.85 / 6.94 / 5.88, with the parallel helper running.
- **Earlier identical run:** a full `all` run from 14:32:57Z to 14:34:41Z, on the tool before
  the latch-timing context was added, gave the same three verdicts and the same figures.

| witness | verdict | key measured value | control value |
|---|---|---|---|
| EFX-4b | **WITNESSED** | after `OJZ_BaseSwap` (46 B): `Raster_Buf_A[46..128)` = 0 non-zero bytes, and `[0..46)` = ROM image | after `OJZ_BandDemo` (110 B): 35 of 64 bytes of `Raster_Buf_A[46..110)` non-zero |
| C1b-3 | **WITNESSED** | `Cache_Origin_Row` 34: rests at y 573 = committed floor 592 − 19; 12/12 lookups match committed cells, 6 of them discriminating | origin 0 (warp re-seed), same drop point: rests at y 573; 12/12 match |
| C3b-2 | **NOT OBSERVED** | 0 tear hits in 3000 lag frames: 95% bound 0.001 per lag frame; 0 lag VBlanks anywhere in `Effects_LatchWorldLines` | latch entered 25.6..56.2 lines after its tick's VBlank; 0/240 ticks had a lag VBlank before the latch |

Controller-verified facts, cited as the controller's and consistent with every run here:
- At boot plus 400 frames, `Raster_Program` = `$FFFF8C64` = `Raster_Buf_B` and `Raster_Patch_Tab`
  = `$000156BE` = `OJZ_TwoChannel` + $80. Section 0 at boot is therefore a PATCHED install.
- One B press hands the player to real physics.

The tool's own boot+400 read agrees: `Raster_Program $FF8C64`, `Raster_Patch_Tab $0156BE`.

---

## EFX-4b: a longer then a shorter static install

**Derivation, from source and ROM:**
- `RASTER_BUF_SIZE` = 128 (`raster.emp`), cross-checked as `Raster_Buf_B − Raster_Buf_A` = $80.
- The terminator is `[RASTER_ARM_PARK $8AFF][RASTER_OPS_END $FFFF]` (`raster.emp`).
- Each program's length was walked out of its own 128-byte ROM image: the bytes through the last
  non-zero word, which must be that terminator.
  - `OJZ_BandDemo` ($014E48) is **110 B**. This agrees with its source ensure: "7 fixed + 3 bands
    × (2+6 ON, 2+6 restore) = 55" words.
  - `OJZ_BaseSwap` ($014EC8) is **46 B**. This agrees with `OJZ_BASE_SWAP_HAND`, 23 words.
  - Both ROM images are zero from their length to 128. That is the EFX-4b padding, present in
    the ROM.
- The lab rows were read out of the ROM's own table (`Debug_LabCycleHotkey.lab_index`, 6-byte
  rows, `LAB_KIND_RASTER` = 1, sub-index into `.raster_table`):
  - `OJZ_BandDemo` is row **21**.
  - `OJZ_BaseSwap` is row **22**.

**Route:** the real hotkey, not a `Raster_Pending` poke.
1. At boot+400 (`Debug_Lab_Index` measured **0**), write `Debug_Lab_Index` = 20.
2. Hold START, then press RIGHT. That steps to row 21, and the row installs through
   `Raster_Install`.
3. Stop at `$engine.effects.raster$Raster_VBlank$no_install` on each VBlank until the one where
   `Raster_Pending` = 0 and `Raster_Program` = the target. That is the stop immediately after
   the fixed 128-byte copy.
4. Repeat for row 22.

**Raw values:**
- Before: `Raster_Program $FF8C64`, `Raster_Patch_Tab $0156BE`, `Raster_Active_Buf $FF8BE4`.
- After `OJZ_BandDemo` (frame 404): `Debug_Lab_Index 21`, `Raster_Program $014E48`,
  `Raster_Patch_Tab $000000`, `Raster_Active_Buf $FF8BE4`. `Buf_A[0..128)` equals the ROM image.
- After `OJZ_BaseSwap` (frame 408): `Debug_Lab_Index 22`, `Raster_Program $014EC8`,
  `Raster_Patch_Tab $000000`, `Raster_Active_Buf $FF8BE4` (= `Raster_Buf_A`).
  - `Buf_A[0..46)` equals the ROM image.
  - **`Buf_A[46..128)`: 0 non-zero bytes.** `Buf_A[46..62)` = `00000000000000000000000000000000`.
  - Two frames later the buffer is unchanged.

**Control:** after the longer install, 35 of the 64 bytes in `Buf_A[46..110)` were non-zero
(`Buf_A[46..62)` = `0002c04a000000160000048c8a1b0001`). The zero tail after the shorter
install is therefore bytes that were overwritten. It is not RAM that was never written. Had the
copy been bounded, or the image unpadded, those 35 bytes would have survived.

**Verdict: WITNESSED.**

**The survey (3c):** the recipe is right as written, including the "not sections 0 or 7" rule.
Its "not checked" items are now measured: the boot `Debug_Lab_Index` is 0, and rows 21/22 are
confirmed from the ROM table.

---

## C1b-3: Collision_GetType at a non-zero origin, with physics on

**Setup, derived before running:**
- **No hysteresis in the cache window.** `Tile_Cache_Fill`'s vertical window
  (`engine/level/tile_cache.emp`, `.v_section`) sets the desired top to
  `((Camera_Y >> 3) − TILE_CACHE_MARGIN_V) & ~1`. The desired span is at least 60 rows, so it is
  clamped to exactly `TILE_CACHE_ROWS` = 60. The top therefore equals the desired top whichever
  way the camera arrived.
- **What that makes the origin.** `Cache_Origin_Row` = (Cache_Top_Row − the top at the last
  `Tile_Cache_Init`) mod 60, a function of camera Y. Measured as such: boot top 2 / origin 0;
  after the fly top 32 / origin 30; at rest top 36 / origin 34.
- **Consequence for the control.** Flight alone cannot produce origin 0 at the same camera.
  The control therefore re-seeds the origin through the warp mailbox, whose consumer
  (`Debug_Warp_Consume`) runs `Tile_Cache_Init`.
- **Choosing the drop height.** The warp centres the camera at y − `CAM_SCREEN_HALF_H` (112).
  The grounded rest camera for the floor at 573 is 429, which is Cache_Top_Row 36. Top 36 needs
  a camera in 416..431, so a drop y in 528..543. From the boot marker (y 256) at
  `PLAYER_DEBUG_FLY_SPEED` 16 px/frame, only 17 frames (y 528) lands in that range. The run
  re-measures all of it.

**Test** (one boot):
1. Boot+400: player (256,256) in fly, camera (96,144), top 2, origin 0.
2. Hold DOWN 17 frames. At frame 419: (256,528), camera (96,384), top 32, origin 30.
3. Press B. Frame 420 is the first physics frame, still at (256,528); the box goes 16×16 → 19×39.
4. First grounded frame 441: (256,573), `player_state` 0, `ST_IN_AIR` clear, camera (96,429),
   top 36, **origin 34**.
5. At rest (30 still frames, frame 471): the same values, **y 573, origin 34**, layer 0.

**Control** (a fresh boot):
1. Press B, land (rest y 573, origin 34; setup only).
2. Warp to (256,528). The mailbox reads back (256,528). On the ack frame (504): camera (96,416),
   top 36, **origin 0**.
3. First grounded frame 524: y 573, origin 0.
4. At rest (frame 554): **y 573, origin 0**.

**The expected height, from committed data only.** Section 0 plane A (`section_0.collattr.bin`)
cells were baked through `tools/collision_pipeline.bake_plane_cell` with the base bank, the
level build's own function.
- The sensors sit at x 256 ± 9 (x_rad = width 19 >> 1).
- The floor surface is y 592 at both sensors, and flat across 247..265.
- The rest y is 592 − y_rad 19 (height 39 >> 1) = **573**.
- Test and control both measured **573**.

**Lookups:** every `Collision_GetType` call over 2 frames at rest was stopped at entry for its
inputs (d0 = x, d1 = y, d3 = layer) and the cache window, then taken to the stacked return
(checked) for its d0.b result. Each result was graded against the committed cell. For a solid
cell the check compares `HeightMaps[attr]`, `AngleTable`, `SolidityTable` and `CrossoverTable`
from the ROM against the baked (heights, angle, solidity, xover); an air cell must return 0.
- Test, at origin 34: **12 calls, 12 in the window (6 solid, 6 air), 12 match, 0 mismatch.**
- Control, at origin 0: 12 calls, 12 match.
- Anti-vacuity: at origin 34, **6 of the 12** calls would have read a DIFFERENT committed cell
  had the origin been dropped (physical row = row − Cache_Top_Row). At origin 0 that count is
  0 by construction.

**Verdict: WITNESSED.** Origins used: test 34 (landing and rest), control 0 (landing and rest).

**Scope, stated so it is not over-read:**
- The pre-C1b-3 form `floor(L/2) + O/2` equals the shipped `floor((L+O)/2)` for every even
  origin. No run can tell the new form from the old one, and this witness does not try to. What
  it shows is that the shipped lookup reads the committed cell at a non-zero origin and that a
  player lands and stands where the data says.
- Only layer 0 (path A) and one standing column were exercised.

---

## C3b-2: lag-frame residue in section 0

**Instrument.**
- **Loop bounds.** They were decoded with capstone out of the ROM bytes of
  `Effects_LatchWorldLines` ($008ABC..$008B3A), starting from the listing's `$...$plain_ch` and
  `$...$mch` labels:
  - `.plain`: head $008B2E, store `move.w d2,(a1)+` at $008B32, `dbra` at $008B34.
  - `.mch`: head $008AD4, store `move.w d2,$6(a0)` at $008B20, `dbra` at $008B24.
- **Channel counter.** `RASTER_MAX_PATCH` = 4 (`raster_dsl.emp`), so d0 = 3 on channel 0 and 2
  on channel 1.
- **What counts as a tear.** The interrupted PC must be the loop's `dbra` with d0.w = 3
  (channel 0's store has retired), or head..store with d0.w = 2 (channel 1's store has not). A
  PC test alone cannot tell the channels apart, because all four share one loop body.
- **Where the PC and d0 are read.** At `VInt_Lag` entry, SP points at the `jbsr` return
  address. `VBlank_Handler`'s `movem.l d0-a6` block (60 B) sits above that, then the exception
  frame [SR][PC]. So the saved d0 is at SP+4 and the stacked PC at SP+66. The layout was
  validated at every stop: the return address equalled `VBlank_Handler`'s `.done` 3000 of 3000
  times.
- **Channel state.** Each channel's record state comes from `Raster_BuildSchedule`'s own rule.
  The fire line is `Effects_Screen_L[ch]` − 1. A fire line past `band_hi` is suppressed; below
  `band_lo` it is clamped up. The band table is read from the ROM at `Raster_Patch_Tab`.

**Run:** a diagonal zig-zag in fly that keeps the camera in section 0: 182 legs, 37748 frames.
- **3000 `VInt_Lag` stops, all of them.** `Lag_Frame_Count` matched the stop count at every
  stop (0 out of step), and rose by 2999 by the last stop, whose own increment lands after it.
  The first full run read it one frame later: 3000.
- `Raster_Patch_Tab` was `$0156BE` at every stop, so section 0's patched program was live
  throughout.
- **`Effects_Motion_Any` = 0 at every stop.** The latch runs its `.plain` loop, not `.mch`.
- Channel 0 / channel 1 record state: **suppressed / live (clamped up) at 2910 stops,
  suppressed / suppressed at 90** (camera near the act top).
- Where the lag VBlanks landed (nearest preceding non-phased symbol):
  | routine | stops |
  |---|---|
  | `PageCache_PatchRun_Seq` | 727 |
  | `S4LZ_Decompress` | 454 |
  | `PageCache_Audit` | 454 |
  | `Parallax_Fill_PerLine` | 364 |
  | `Draw_TileColumn` | 183 |
  | `TileCache_FillRow` | 182 |
  | `Parallax_Step4_Fill` | 135 |
  | `EntityWindow_TrySpawnObject` | 91 |
- **Inside `Effects_LatchWorldLines` at all: 0.**

**Tear hits: 0.** Channel 1's record was live at 97% of stops, but no stop was a hit, so no
hit's channel-1 state can be reported.

**Context,** measured on the same flight: the latch is entered **25.6..56.2 scanlines (median
43.4) after the VBlank that starts its tick** (a frame is 262 lines). In **0 of 240** ticks did
a lag VBlank land between the tick start and the latch. A lag VBlank reaches the latch only if a
tick's pre-latch work overruns a frame, which is about 200 more lines than it takes here. The
lag VBlanks land in the streaming work later in the tick instead.

**Verdict: NOT OBSERVED.** 0 hits in 3000 lag frames puts a 95% upper bound of **0.00100** on the
per-lag-frame tear probability (1 − 0.05^(1/3000); the rule of three gives the same 3/n). This is
a bound, **not a clean result**: nothing here shows the window closed.

**A second reason section 0 cannot show the residue: channel 0's record is never emitted there**
(below). A tear in section 0 would leave no visible disagreement even if one were caught.

---

## What the survey got wrong

The survey (`survey/physics-scene-0912`, `docs/superpowers/notes/2026-09-12-physics-scene-survey.md`)
got two things wrong in 3d, and left one thing in §5 item 1 incomplete. The corrections come
from source, and runtime confirms them where noted.

1. **3d: "Channel 0 carries `anchor_sweep` motion, so `Effects_LatchWorldLines` takes its `.mch`
   loop" is WRONG.**
   - Source: `OJZ_Preset_Sec0` binds `patch_motion: [ANCHOR_MOTION_NONE × 4]`
     (`games/sonic4/data/effects/ojz_effects.emp:1519-1522`).
   - Runtime: `Effects_Motion_Any` = 0 at all 3000 stops.
   - The latch runs the `.plain` loop. The `anchor_sweep` the survey read is in a comment
     (`:1444`) quoting a binding that has since been removed.
2. **3d: "Section 0 at boot already has two patchable channels with motion" is WRONG in its
   consequence.**
   - Source: channel 0's world anchor is `PATCH_ANCHOR_NONE` = $7FFF
     (`patch_world_ys: [PATCH_ANCHOR_NONE, 314, …]`, `:1518`).
   - Its latched line is therefore $7FFF − Camera_Y, far past `band_hi`.
   - Runtime: its record was **suppressed at all 3000 stops**. Only channel 1 (world Y 314,
     band 222..223) ever emits.
   - Section 0 cannot show a two-channel disagreement at any camera or timing.
   - The survey's "not checked: whether channel 1 is suppressed" is now measured: live (clamped
     up) at 2910 of 3000 stops.
3. **§5 item 1 and the brief: "the same drop at `Cache_Origin_Row` = 0" cannot be produced by
   flight.** The origin is a pure function of camera Y since the last `Tile_Cache_Init` (derived
   above, measured). The only in-scene way to put origin 0 at the same camera is the warp
   mailbox. Also, no slide is needed to get a non-zero origin: the plain boot B-drop from
   (256,256) already lands at origin 34 (measured in an exploratory run, frame 457).
4. **3d, method detail:** "read the stacked return PC" at `VInt_Lag` works only after skipping
   `VBlank_Handler`'s 60-byte `movem` and the 4-byte `jbsr` return, so the PC is at SP+66. The
   channel window needs the dbra counter (the saved d0) as well as the PC.
5. **3c and 3e: nothing wrong found.** 3c's lengths (110 / 46) and rows (21 / 22) are confirmed.

## Booking corrections for the controller

I did not edit `docs/DEFERRED_WORK.md` or the s7 note. Suggested text:

- **EFX-4b.** It was CLOSED by padding (`DEFERRED_WORK.md` ~line 12041;
  `docs/superpowers/notes/2026-09-12-raster-efx4b-c3b2.md` TAG `[RUNTIME-UNVERIFIED]`). It is now
  **RUNTIME-WITNESSED** on the longer→shorter case, ROM `9ce1c2ff`: lab rows 21→22, 35 non-zero
  control bytes, then `Buf_A[46..128)` all zero.
  - The s7 note's "EFX-4b PARTIAL" is superseded.
  - s7's frame-400 read observed the PATCHED builder's buffer (`Raster_Program` = `Raster_Buf_B`,
    as the controller measured), not the static copy.
- **C1b-3.** Status line in `DEFERRED_WORK.md` ~line 30644 ("C1b-3's premise witnessed"), and
  s7's "LIMIT: the scroll test has no physics". Now **RUNTIME-WITNESSED WITH PHYSICS**, ROM
  `9ce1c2ff`:
  - origin 34 versus warp-re-seeded origin 0, same drop from (256,528);
  - both rest at y 573 = committed floor 592 − 19;
  - 12/12 `Collision_GetType` returns match the committed cells in each run, 6 of them
    discriminating.
  - Scope: it cannot distinguish the shipped form from `floor(L/2)+O/2`, which are equal for even
    origins.
  - s7's "the scroll test has no player physics" is wrong about the scene (the survey already
    said so). The C1b-3 half is now closed.
- **C3b-2.** The residue was accepted on analysis
  (`docs/superpowers/notes/2026-09-12-raster-efx4b-c3b2.md`, `[RUNTIME-UNVERIFIED]`). Runtime:
  **NOT OBSERVED, 0 in 3000 lag frames, 95% bound 0.001 per lag frame**. Please book it with
  these facts, so the zero is not read as "clean":
  - (a) The lag VBlanks never land in the latch because it runs 26..56 lines into its tick; 0 of
    240 ticks had a lag VBlank before it.
  - (b) Section 0 cannot show a disagreement at all: its channel 0 is anchor-NONE and always
    suppressed, and its motion is NONE, so the `.plain` loop runs.
  - The residue stays a cosmetic hazard on analysis only. The recipe as specified (fly in section
    0) cannot observe it.
  - **RUNTIME-TAG:** the one place in OJZ act 1 with two live, moving patch records is section 7
    (from source: `OJZ_Preset_Sec7`, `patched: OJZ_WorldWater`, anchors on channels **2 and 3**,
    `anchor_sweep` on channel 2, so the `.mch` loop runs there). The window of interest there is
    channel 2's store versus channel 3's, not 0 versus 1. The latch timing above was measured in
    section 0 only.
- **Controller's frame-440 fact** ("y 256 → 426, Sonic drawn"): true, but mid-fall. From a
  frame-400 B, the player lands at y 573 around frame 457 (`Cache_Origin_Row` 34 at landing).
  Do not read 426 as a floor height.

## Hygiene and side findings

- **Emulator instances.** Every instance was spawned and reaped by `aether_instance`; there were
  about 9 in total, one per tool witness plus exploratory probes. Each exploratory probe checked
  that its own PID was gone after the reap.
- **Leftover check.** At 14:39:54Z, `pgrep -a -f oracle-aether` showed only MCP-shim instances
  (`/tmp/oracle-mcp-*` sockets, on `aeon/s4.debug.bin`). None were mine, and none were touched.
- **Home-path test.** `tools/test_no_baked_home_paths.py`, run with a fresh
  `-X pycache_prefix` directory: `6 passed in 0.06s`. The coordinator's exact
  `PYTHONPYCACHEPREFIX=$(mktemp -d) python3 -m pytest ...` spelling was refused by the worktree
  isolation checker. The tool spells no absolute path; the ROM and listing are arguments.
- **Phased symbols in a PC → symbol map.** `DacSampleTable` is a bank VMA at listing $85B1, and
  it sits inside `Parallax_Fill_PerLine`. An unfiltered nearest-symbol histogram put 11 of 100
  lag PCs on it. The tool filters phased names through `scene_spans.vma_phased_symbol_names`;
  any other PC-attribution tool should do the same.
- **Shared scratchpad.** The session scratchpad is shared with the parallel helper. A scratch file
  of mine (`scratchpad/methods.py`) was overwritten by theirs mid-run. Nothing committed depended
  on it; later scratch went into a per-agent subdirectory.
