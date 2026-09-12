# Blank-cell priority under Shadow/Highlight: measuring gap-lens F4

2026-09-12. Branch `measure/blank-priority-0912`, cut from `9fe9ee91`. The probe is
`tools/blank_priority_probe.py`. It is a probe, not a gate: nothing runs it.

## Verdict: CONSEQUENCE, in section 1 only, on the Rust core

On oracle-rs, a blank plane-A cell's priority bit does change what Shadow/Highlight shows.
When the engine's `$0000` is replaced by a word with bit 15 set, the cell's shadowed
low-priority plane-B pixels come up to normal intensity. Nothing else changes. In OJZ act 1
this can only be seen in section 1. That is the only section where S/H was measured on, and
its S/H comes from `OJZ_TestRaster`, the Effects P1 gate fixture, not from authored content.
19 of the 116 blank-priority words can be displayed inside that band.

**What this does not establish.** The instrument implements the premise by design, so this
is not a hardware result. oracle-core's `sh_state` (`crates/oracle-core/src/render.rs`) says
the default state is Shadow iff both the A-slot and B priority bits are 0, and that
"transparent planes still contribute their tile's priority, the Bloodlines light-ray trick".
The measurement shows that the engine's bytes produce a different picture under that model.
That the model matches a real Mega Drive is oracle's claim. It is not tested here, and no
real hardware is available to test it.

## ROM and instrument

- ROM `/home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.bin`, 847533 bytes, crc32
  `9ce1c2ff`, with the `.lst` beside it. That tree is at `9fe9ee91`. `cmp` finds all nine
  `sec{N}_strips_a.bin` byte-identical to this branch's.
- `oracle-aether`, spawned through `tools/aether_instance.py`. The handshake reported
  `implementation "oracle-rs"`. PIDs were 2923061 (run 1) and 2935135 (run 2); each was
  reaped and `/proc/<pid>` was confirmed gone. No MCP tool and no socket other than the
  probe's own were used.
- **VRAM writes** use `emulator/write_vram`. In oracle that is `Vdp::poke_vram`, a direct
  store into the VRAM array (it also updates the SAT cache inside the SAT). It **does not go
  through the VDP data port**: no FIFO, no auto-increment, no command latch. The renderer
  reads VRAM each line, so the next rendered frame sees the poke. Every poke is read back
  after the capture, and the probe refuses the run if the engine rewrote it.
- **Pixels** come from `emulator/scanlines`, with `source == "raster"` asserted on every call
  and `mode == "h40"`. Captures use checkpoint/restore: restore, poke, run 2 frames, capture
  all 224 rows. The second frame is rendered entirely after the poke.

## Command

```
PYTHONPYCACHEPREFIX=$(mktemp -d) python3 tools/blank_priority_probe.py \
    --rom /home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.bin \
    --lst /home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.lst --json out.json
```

- **Run 2** (the recorded one): 2026-09-12 14:28:15 to 14:28:24 UTC per `date -u`. The
  probe's own clock read 8.6 s, with `uptime` load 13.85 at the start. Exit 0.
- **Run 1**, taken before the `$7800` control, the boot sweep and `Effects_Screen_L` were
  added: 14:26:36 to 14:26:42 UTC, 4.9 s, load 4.08. Exit 0, and every row the two runs
  share was identical.
- **Run 3**, the committed file (only its docstring differs from run 2's): 14:30:47 to
  14:30:52 UTC, exit 0. Its output differs from run 2's only in the timestamp and PID lines
  (`diff` exit 0 with those filtered out), and PID 2956830 was reaped and gone.

## Population, re-derived

Each word of `sec{N}_strips_a.bin` is parsed with the strip layout. The column stride is
776 B = `STRIP_TILE_HEIGHT*2 + 2*(STRIP_TILE_HEIGHT//2) + STRIP_COLLISION_PAD`, read from
`tools/ojz_strip_gen.py`. A word is blank if `word & NT_TILE_MASK == 0`, where
`NT_TILE_MASK` is `$07FF`. It carries priority if `word & $8000` is set. `NT_ATTR_MASK` is
`$F800` and priority is its top bit. Both masks are read from `engine/system/constants.emp`
at lines 433-434.

**116 words**: 20 / 19 / 10 / 15 / 10 / 11 / 14 / 7 / 10 over sections 0-8. This matches
the seat's count, and I derived it independently.

| sec | words | values |
|---|---|---|
| 0 | 20 | 20 x `$C000` |
| 1 | 19 | 7 x `$8800`, 12 x `$C000` |
| 2 | 10 | 2 x `$8000`, 8 x `$8800` |
| 3 | 15 | 7 x `$8800`, 8 x `$C000` |
| 4 | 10 | 2 x `$8000`, 8 x `$8800` |
| 5 | 11 | 7 x `$8800`, 4 x `$C000` |
| 6 | 14 | 4 x `$C000`, 2 x `$8000`, 8 x `$8800` |
| 7 | 7 | 7 x `$8800` |
| 8 | 10 | 2 x `$8000`, 8 x `$8800` |

A wider census from a scratch script using the same parse (the probe does not print it):
543,613 blank words in total, 39,443 of them carrying any attribute bit, and 22,112 a
non-zero palette.

## S/H extent, measured, all nine sections

For each section the probe warps the player through the mailbox, confirms which section the
engine installed (`Parallax_Prev_Sec_X/Y`), then steps through one frame with
`run_to_scanline` 0..223 and reads VDP reg `$0C` at every line.

| where | camera | installed program | reg `$0C` seen | S/H lines | `Effects_Screen_L` ch0..3 |
|---|---|---|---|---|---|
| boot (sec 0) | (96,144) | `Raster_Buf_B` (patched) | `81` | none | `7F6F 00AA 7F6F 7F6F` |
| sec 0 | (864,912) | `Raster_Buf_B` (patched) | `81` | none | `7C6F FDAA 7C6F 7C6F` |
| sec 1 | (2912,912) | `OJZ_TestRaster` | `81 89` | **121..223** | `7C6F x4` |
| sec 2 | (4960,912) | `OJZ_TestGradient` | `81` | none | |
| sec 3 | (864,2960) | (`Vectors`, i.e. address 0) | `81` | none | |
| sec 4 | (2912,2960) | `OJZ_DepthVSplit` | `81` | none | |
| sec 5 | (4960,2960) | `..._ojz_sec5_showcase` | `81` | none | |
| sec 6 | (864,5008) | `..._ojz_sec6_baseswap` | `81` | none | |
| sec 7 | (2912,5008) | `Raster_Buf_B` (patched) | `81` | none | `6C6F 6C6F FD4B FDAA` |
| sec 8 | (4960,5008) | (`Vectors`) | `81` | none | |
| sec 1 scene | (2120,440) | `OJZ_TestRaster` | `81 89` | 121..223 | |
| sec 0 scene | (40,408) | `Raster_Buf_B` | `81` | none | `7E67 FFA2 7E67 7E67` |
| sec 7 scene | (2080,4202) | `Raster_Buf_B` | `81` | none | `6F95 6F95 007D 00D0` |

Camera bounds are 0..5824 x 0..5920, from `Camera_X_Max` / `Camera_Y_Max`.

**Section 1's band is 121..223 by register sampling**, measured at two cameras. The pinned
program (`OJZ_TEST_HAND`) puts the write's effect on line 120. The one-line difference is
where `run_to_scanline` samples the register, and I did not examine it. Every cell measured
below sits at line 128 or lower, clear of that line.

**Section 0.** The source reads as if section 0 had S/H: `OJZ_Preset_Sec0` binds
`OJZ_TwoChannel`, whose channel 0 is `fx_tint_band(line: 100, ..., sh: 1)`. Measured, S/H is
never on at any of three cameras. At all three, channel 0's latched screen line is exactly
`$7FFF - Camera_Y`: `$7F6F` = 32767-144, `$7C6F` = 32767-912, `$7E67` = 32767-408. Channel
0's anchor is `PATCH_ANCHOR_NONE` (`$7FFF`), and it is being latched as world Y 32767,
which puts the record tens of thousands of lines below the screen. The measured facts are
that the record never fires and that the latch equals `$7FFF - Camera_Y`. The step between
them (`Raster_BuildSchedule` dropping an out-of-band record) is my reading, not something I
measured.

## Premise test (section 1, camera (2120,440))

The probe picked the best of 106 candidate cells. A candidate must be a blank plane-A cell
(`$0000` in VRAM), all 64 of its dots inside S/H lines 125 and below, and plane B beneath it
low-priority on every dot. The chosen cell also had 64/64 opaque B dots, and no sprite won
any of its dots (checked by `pixel_attribution`).

- The cell is VRAM `$C394`, screen x 8..15, y 128..135.
- **`$0000` -> `$8000`: 25 px changed, 25 inside the cell and 0 outside.** All 25 are exact
  shadow -> normal on the core's intensity ramp:
  - `(36,18,18)->(72,36,36)` x17
  - `(0,18,0)->(0,36,0)` x6
  - `(0,36,18)->(0,72,36)` x2
- The other 39 dots are `(0,0,0)` in both frames. Shadowed black is still black, so
  "changed pixels" undercounts "affected pixels" by exactly the black dots.
- `pixel_attribution` after the poke reports plane A `priority=true, opaque=false` at the
  cell. The toggle landed on the dot being diffed.
- **Same cell, `$0000` -> `$7800`** (every attribute bit except priority: palette 3 and both
  flips): **0 px changed.** The effect comes from bit 15, not from writing some attribute.

## Controls

- **Outside S/H, same frame:** blank cell `$C118` at screen x 24..31, y 88..95, above the
  line, with 64/64 opaque low-priority B dots. `$0000` -> `$8000` changed **0 px**, as
  predicted, while `pixel_attribution` confirmed priority=true landed.
- **Outside S/H, other sections:** the in-place writes in sections 0 and 7 below (15 words)
  changed **0 px**. So did all of them written together.
- **Determinism:** two unmodified captures from the same checkpoint differed in **0 px** in
  every scene. Without that, no diff here would be a verdict.
- **S/H really is on at the test line:** reg `$0C` = `$89` at lines 121..223 and `$81` above,
  in the same scene the premise used.
- **The world -> VRAM mapping** was checked before any in-place poke. In a 7x7 neighbourhood
  of each word, blank/non-blank agreed with `strips_a` everywhere, and non-blank cells'
  attribute bits matched. That was 49/49 cells, or 42/42 at the screen edge, for every word.

## Consequence

**Count: 19 of 116.** A word counts if some camera exists that shows its whole cell on lines
inside a *measured* S/H band. That camera's centre must be in the band's section (the
`Parallax_CheckBoundary` rule: camX+160, camY+112) and inside the camera bounds. Only
section 1 has a band, and all 19 of its words qualify. No other section's word can be on
screen while section 1 is installed. The count says the words *can* be shown in the band.
It says nothing about whether normal play takes the camera there.

**In place** at camera (2120,440), with section 1 installed. Six of section 1's words are on
screen: cols 13/29/45, rows 72/74, world y 576/592, screen y 136/152. Each is `$0000` in
VRAM, and each was written back as its authored `$C000`:

| word | screen | changed px | shadow->normal | unchanged (all black) |
|---|---|---|---|---|
| col 13 row 72 | (32,136) | 14 | 14 | 50 |
| col 13 row 74 | (32,152) | 11 | 11 | 53 |
| col 29 row 72 | (160,136) | 14 | 14 | 50 |
| col 29 row 74 | (160,152) | 11 | 11 | 53 |
| col 45 row 72 | (288,136) | 14 | 14 | 50 |
| col 45 row 74 | (288,152) | 11 | 11 | 53 |
| **all six** | | **75** | **75** | |

Row 72 changed `(0,18,0)->(0,36,0)` x7, `(36,18,18)->(72,36,36)` x5 and
`(0,36,18)->(0,72,36)` x2. Row 74 changed `(0,18,0)->(0,36,0)` x11. Every changed dot was
inside its own cell.

The authored word restores palette 2 as well as priority. The `$7800` control above shows
the non-priority bits change 0 px, so the difference measured here is the priority bit's.

## What F4 got wrong

1. **Section 7's water band is not Shadow/Highlight.** `OJZ_WorldWater` channel 2 has been
   `sh: 0`, a palette swap, since 2026-09-05. Measured, reg `$0C` never gets bit 3 in
   section 7 at either camera, and restoring 3 of its blank-priority words in the water band
   changed 0 px. None of section 7's 7 words has a consequence.
2. **The consequence population is 19, not "section 1 plus section 7".** Only section 1's
   words can reach an S/H band.
3. **Section 1's S/H is a gate fixture.** It comes from `OJZ_TestRaster`, the P1 acceptance
   program, bound as `OJZ_Preset_Sec1`. So the visible consequence exists only where test
   scaffolding turns S/H on. No authored OJZ content uses S/H at the cameras measured. That
   bears on the "engine keeps attributes vs baker strips them" question F4 left as an
   authoring decision.
4. **The premise holds on oracle-rs**, and 25 of 64 dots changed rather than 64 because the
   remaining 39 were black. It is not established for hardware, and this note cannot
   establish it. See the verdict.
5. **Not an F4 error, but found here:** section 0's preset reads as S/H in the source
   (`OJZ_TwoChannel` ch0 `sh: 1`), and it never switches on. Channel 0's latched line is
   `$7FFF - Camera_Y` at all three cameras measured. If the S/H tint band there was meant to
   show, it does not.

Nothing here was BLOCKED, and everything was reached headlessly. The words at section 1
rows 88/90 and row 32, and section 0's other clusters, were not measured in place. They are
counted through the geometry above, not through pixels.
