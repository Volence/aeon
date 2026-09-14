# REGIONS-P2 on screen (T5), 2026-09-13

Taken by the aeon overseer in its own private Oracle instance (`bus.mode: own-instance`, not the
owner's window) on `parcel/regions-p2` tip `a3757a59`, `s4.debug.bin` md5 `02bbdfc6`, 846,742 bytes,
symbols from the same build's listing. Route: cold boot, hold RIGHT (DEBUG fly mode). "Centre" is
`Camera_X` + 160, the point `Region_Resolve` tests. The night region is row 9, x 3400..4799.
CRAM line 1 index 2 is the tracer: forest `$0E62`, night `$0E20`.

| file | frame | centre x | `Pal_Fade_Frames` | CRAM 1:2 | what it shows |
|---|---:|---:|---:|---|---|
| `t5-f185-before.png` | 185 | 2128 | 0 | `$0E62` | forest, past the 2048 section line (a shared palette, nothing happened there) |
| `t5-f267-cross.png` | 267 | 3408 | 0 | `$0E62` | first frame the centre is past 3400; the crossing check reads the previous frame's centre (3392), so nothing yet |
| `t5-f268.png` | 268 | 3424 | 15 | `$0E40` | armed on the next frame; every differing channel one step toward night |
| `t5-f272-settled.png` | 272 | ~3488 | 11 | `$0E20` | settled at k = 5, the derived 2d-1 for d = 3; the night look (parked for the owner) |
| `t5-f312-sec4096.png` | 312 | 4128 | 0 | `$0E20` | past the 4096 section line INSIDE the region: nothing re-arms, colours unchanged |
| `t5-f358-snapback.png` | 358 | 4832 | 0 | `$0E62` | past 4800: snapped straight back to forest, no fade (the forest preset has transition 0) |
| `t5-f385-reversal-defect.png` | 385 | 5104 | 0 | `$0E20` | THE DEFECT: re-entered from the right (armed at frame 363, count 15), reversed out at once; the fade kept stepping and settled on NIGHT inside the forest region, where it stays |

Side observation for the fade fix: in the 4 emulated frames after the re-entry arm (363 -> 367) the
count fell 15 -> 13, so about 2 of those frames were lag frames, in the window the parcel flagged.
