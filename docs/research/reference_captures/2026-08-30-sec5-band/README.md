# The section-5 authored band, seen on screen — and its control

Captured 2026-08-30 on branch `measure/sec5-band-witness` for EFFECTS-W1 item 1 step 6
(aeon `c9a462be`, whose own message says *"NOT VERIFIED: nothing has been seen on screen"*).
**This is the measurement that message asked for, in the shape aurora and aeon agreed
(empyrean OVERSEER.md 14:42Z): the picture, the control, and five CRAM samples — bound run A,
bound run B, unbound — with the two bound runs required to agree byte for byte.** Nothing here
is a gate; `tools/sec5_band_witness.py` is the instrument and it refuses rather than guesses.

**VERDICT: BAND SEEN.** On the bound ROM, warped into section 5, CRAM line 2 entry 8 reads
`$0EA4` at screen lines 40, 56 and 72 and `$0000` at 8, 20, 96 and 150 — all seven within one
frame (259) — on two independent private emulator instances whose tables and frames are
byte-identical. On the control ROM (same tree, `rasterRef: null`) the same entry reads
`$0000` on every line and `Raster_Program` is 0. The vacuity check (in-band == out-of-band)
did not fire.

## The ROMs

| ROM | tree | size | crc32 | md5 | how built |
|---|---|---|---|---|---|
| bound   | aeon `6e2495a5` (master tip; the step-6 content) | 736391 | `476e220f` | `cd5960055466380728b056bc4bdf29f2` | `DEBUG=1 ./build.sh`, canonical, exit 0 |
| control | aeon `7c7c5981` (`section_5.meta.json` `rasterRef: null`, regenerated) | 736391 | `3ceb094d` | `9d0a33c376ed790c34ad8cc64524a07f` | `FAST=1 DEBUG=1 ./build.sh`, exit 0 — see below |

Assembler, from the build's own first line: `sigil 8951389a18c3 (clean at capture — no
uncommitted changes)`; `sigil --version` = `0.1.0 (8951389a)`; binary md5
`aee4fac951a177041f53e77e2573d2f4`. Same binary for both builds.

**The two ROMs differ in exactly 5 bytes**: the header checksum (`$18E-$18F`) and the
`ep_raster` longword inside `OJZ_Preset_Sec5` (`$13FF6..$13FF9`): `$013ACE`
(`EditorRaster_OJZ_Act1_ojz_sec5_showcase`) in the bound ROM, `$008204` (`Raster_Program_None`)
in the control. The preset document's own `pub data` still emits in the control (a document is
not a binding), so the sizes match.

**The canonical build REFUSES the control tree, by design.** `DEBUG=1 ./build.sh` on `7c7c5981`
exited 1 in the pytest lane with three failures and produced no ROM (the on-disk `s4.debug.bin`
was still the bound one, crc32 `476e220f`, which is why the crc32 is recorded beside every
measurement):

- `tools/test_effects_seam_gate.py::TestRasterSeamAgainstTheRealTree::test_section_5_is_the_bound_one_and_its_id_is_the_shipped_document` — `no sidecar carries a rasterRef — step 6's band is gone`
- `tools/test_effects_seam_gate.py::TestRasterSeamAgainstTheRealTree::test_the_bound_sections_are_exactly_the_threaded_ones` — `the bound sections are [], not [5]`
- `tools/test_raster_cycle_table_lint.py::test_every_preset_document_is_REACHABLE` — `these preset documents ... are reachable by NOTHING: ['ojz_sec5_showcase']`

Those are step 5/6's own content assertions doing their job. The control artifact was therefore
built with `FAST=1 DEBUG=1`, which runs only what produces the ROM; the 5-byte diff above is the
evidence that it is the control and not a stale copy. The control tree is reverted at
`2ebcd76a`; the branch tip carries the bound content.

## Where the camera is, and how section 5 was found

Sections are `BLOCKS_PER_SECTION_AXIS` (16) blocks of `BLOCK_TILE_SIZE` (16) tiles of 8 px =
2048 px square (`engine/system/constants.emp:788,811`; `SECTION_SIZE_SHIFT = 11` at `:232`). The
act is a 3x3 grid (`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:99-100`; row 1 =
Sec3,Sec4,Sec5 at `:174-176`), so section 5 is column 2, row 1: world X `4096..6143`, Y
`2048..4095`. `Parallax_CheckBoundary` takes the section under the camera CENTRE,
`(Camera_X+160)>>11, (Camera_Y+112)>>11` (`engine/level/parallax.emp:854-861`).

The instrument warps the PLAYER to the section's centre `(5120, 3072)` through the DEBUG mailbox
(`Warp_Req_X/Y/Flag`; ack in 15 frames, not clamped). The engine centred the camera at
`(4960, 2960)`, whose centre `(5120, 3072)` decomposes to section `(2, 1)` = flat 5, and the
engine's own `Parallax_Prev_Sec_X/Y` read `(2, 1)`. The warp consumer (`ojz_scroll_test.emp`,
step 7) re-sentinels those trackers and calls `Parallax_CheckBoundary` itself, so the install
went through the same path a walked crossing takes: `Effects_InstallPreset` -> `Raster_Install`
(stages `Raster_Pending`) -> `Raster_VBlank` (copies it into `Raster_Program`). After the ack
+4 frames, `Raster_Pending` = 0 and `Raster_Program` = `$013ACE` (bound) / `$000000` (control —
an empty program uninstalls the handler, `engine/effects/raster.emp:685-705`).

## The five CRAM tables

CRAM line 2 entry 8 = byte `$50`, parsed from
`games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json` (`on.cram.addr: 80`, colour
`3748` = `$0EA4`, `top: 32`, `bot: 80`). `band()` fires ON at screen line `top` and the restore
at `bot` (`engine/effects/raster_dsl.emp:674-689`), so lines 32..79 are in-band. The base
colour is measured off the out-of-band lines, not assumed.

| line | region | bound A | bound B | control |
|---|---|---|---|---|
| 8   | outside | `$0000` | `$0000` | `$0000` |
| 20  | outside | `$0000` | `$0000` | `$0000` |
| 40  | in-band | `$0EA4` | `$0EA4` | `$0000` |
| 56  | in-band | `$0EA4` | `$0EA4` | `$0000` |
| 72  | in-band | `$0EA4` | `$0EA4` | `$0000` |
| 96  | outside | `$0000` | `$0000` | `$0000` |
| 150 | outside | `$0000` | `$0000` | `$0000` |

`bound-A-sec5.cram.txt` and `bound-B-sec5.cram.txt` are byte-identical (md5
`4e2506e220da218ee75b6467fbafbfbf` both); the two JSON records are identical apart from the
label and file names. Every sample in every run landed in frame 259; the frames were captured at
frame 260. Three runs were taken (A, B, control); no third bound run.

**Vacuity check**: in-band `{$0EA4}` vs base `$0000` on both bound runs — the instrument sees a
mid-frame CRAM write, so a frame-latched palette cannot be what produced the match. The
control, which reads base everywhere, is the run a frame-latched instrument would ALSO produce;
it is the bound runs that discriminate, and they did.

## The pictures

All frames are `emulator/scanlines` with `source == "raster"` asserted (a post-hoc state render
is refused). Full frames are 320x224 untouched; crops are rows 16..95, x 80..143, upscaled 6x —
a gap between OJZ trunks at this camera where the background shows and both band edges are
unoccluded. The yellow 16x16 square at screen centre is the player marker.

| file | md5 |
|---|---|
| `bound-A-sec5-full.png` | `49c4d5047e7137b1fc7daae28b6ac70c` |
| `bound-B-sec5-full.png` | `49c4d5047e7137b1fc7daae28b6ac70c` (identical to A) |
| `bound-A-sec5-rows16-95-x80-143-6x.png` | `04f021e760674d3832bf20b1eb1f2b4a` |
| `bound-B-sec5-rows16-95-x80-143-6x.png` | `04f021e760674d3832bf20b1eb1f2b4a` (identical to A) |
| `control-sec5-full.png` | `b5768d0b73abdce420073eb0a9e6ff11` |
| `control-sec5-rows16-95-x80-143-6x.png` | `4f9200f2d924654b7dabc1d46cf24fbe` |

- **`bound-*-full.png`** — an azure band across the whole width from screen line 32 to 79 over
  the dark jungle background; the trunks and vines in front of it keep their own colours except
  where they, too, drew entry 8 (black), which turns azure inside the band. Above 32 and below 80
  the same content is black between the vines.
- **`bound-*-rows16-95-*.png`** — the same, with both edges crisp: azure begins at crop row 96
  (= line 32) and ends at crop row 384 (= line 80) against black on either side.
- **`control-*`** — the same scene, same camera, same frame number, with no band: the region
  that is azure in the bound crop is black.

## What this does NOT establish

- **The exact transition lines.** `run_to_scanline` is polling-based and can stop a line or two
  past its target; the samples sit well inside (40/56/72) and well outside (8/20/96/150) the
  band. Lines 32 and 80 themselves are pinned by the build-time arm decode (effects_gates PIN 5),
  not here. The crop's edges at rows 96/384 are the picture's own evidence and were read by eye.
- **Only entry `$50` was sampled.** A band that also touched a neighbouring entry would pass.
- **One camera position.** Step 6's claim that screen lines 0..95 are unoccluded *at every
  camera position in the section* was not tested; one position was.
- **A walked crossing.** The warp consumer calls the same `Parallax_CheckBoundary` path, but
  scrolling from section 4 into 5 (and back out, where the band must leave) was not measured.
- **Motion.** These are static frames; nothing here says what the band looks like while the
  camera moves.
- **Hardware.** Oracle's Rust core (`oracle-aether`, private headless instance per run), not a
  console; there is no console to settle it on.
- **The control was not built canonically** — see above; the 5-byte diff is what stands in for
  the verification lanes on that artifact.
- **The aurora `SectionMeta` SHA** that `docs/DEFERRED_WORK.md` says step-6 evidence must cite
  (`sceneRef`'s was aurora `a88db05`; `rasterRef` needs its successor) is not cited here: the
  step-6 commit does not name it and this lane did not have aurora's tree.

## Reproduce

```
python3 tools/sec5_band_witness.py --rom s4.debug.bin --lst s4.debug.lst \
    --label bound-A --out-dir docs/research/reference_captures/2026-08-30-sec5-band
# control: on a tree with section_5.meta.json rasterRef: null (regenerated + FAST=1 DEBUG=1 built)
python3 tools/sec5_band_witness.py --rom <control.bin> --lst <control.lst> --label control \
    --expect-unbound --control-preset ojz_sec5_showcase --out-dir ...
```

Run with `PYTHONDONTWRITEBYTECODE=1` and a cleared `tools/__pycache__`. Timings: each run
(spawn, 240-frame settle, warp, 7 samples, capture) completed in under 20 s wall-clock on this
machine at load ~3-6 (`uptime` 12:29-12:33, up 5 days 4:18-4:22).
