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

---

# ⚠ CORRECTION, 2026-09-16 — `t5-f272-settled.png` IS MID-FADE. Its name is wrong.

**Do not take a colour measurement from `t5-f272-settled.png`, and do not take one from any
other frame in this set either.** The reasons differ per frame and are below.

## What is wrong with `t5-f272-settled.png`

A decode of that frame found **45.9% of its pixels in colours that are in neither the day
palette nor the night one** — control established first, on a freshly captured live
night-region frame that decoded 100.0% with 0.0% unaccounted
(`docs/superpowers/notes/2026-09-16-night-palette-mechanism.md`). It is a mid-fade frame.

**The refutation was already in the table above, one column over.** That row records
`Pal_Fade_Frames` = **11**, and `engine/ram.emp` spells that field *"cross-fade frames
remaining (0 = stable)"*. Non-zero means the cross-fade was still running. The word
"settled" was written into the filename because the **CRAM tracer entry** (line 1, entry 2)
had reached its night value `$0E20` — and a tracer entry is evidence about one colour.
`Palette_DoFade` steps all 48 words of lines 1-3 by ±1 per step, so a word already close to
its target **arrives early** and sits there while the rest of the palette is still moving.

## How all four recorded numbers fit together

Consistent with every number in the table, and with the ROM this set was taken on
(`parcel/regions-p2` tip `a3757a59`, which is an **ancestor of `f122cce3`**, the fade-fix
that added `Palette_DoFade`'s `.arrived` early close — so on this ROM the counter always ran
the full 16 composes regardless of when the palette arrived):

* the fade armed at frame 268 with the count at 15, so frame 272 is **k = 5** composes in,
  and `16 - 5 = 11` is exactly the count recorded. ✓
* `Palette_DoFade` steps only on **ODD** decremented counts, so 5 composes are **3 steps**
  (at k = 1, 3, 5). The night transform's largest per-channel move is red −3, so at k = 5 the
  buffer had **arrived** — which is why the tracer read the night value and why a careful
  person wrote "settled".
* **but the picture is not the buffer.** `Palette_Compose` runs in the main loop; the DMA to
  CRAM runs in the *next* VBlank; and a paused screenshot is the *previously completed* video
  frame. The PNG therefore lags the state recorded beside it by one or two composes — and at
  **both** k = 3 and k = 4 the fade had taken **2 of its 3 steps**. So whichever of the two
  the lag is, the image shows a two-thirds-of-the-way intermediate palette, in neither the
  day set nor the night set. That is the 45.9%, and it is concentrated in the dirt ramp
  because that is where the channel distances are largest.

This last part is a **reconstruction** consistent with all the recorded numbers, not a
measurement: this set's capture protocol was by hand and is not written down, so the exact
one-or-two-compose lag cannot be recovered. It does not need to be — the conclusion is the
same at either lag, and the load-bearing claim (the frame is mid-fade) rests on the counter
and on the decode, neither of which depends on it.

## What is safe to conclude from this set

| frame | safe to conclude |
|---|---|
| `t5-f185-before.png` | ✅ forest colours past a shared-palette section line; nothing armed. |
| `t5-f267-cross.png` | ✅ the crossing check reads the previous frame's centre. Timing only. |
| `t5-f268.png` | ✅ the fade **arms** on the tick after the centre passes 3400, count 15. Timing only — the colours are one step in. |
| `t5-f272-settled.png` | ❌ **NOTHING about colour.** Mid-fade. The name is wrong; the file is kept so this correction has somewhere to live. |
| `t5-f312-sec4096.png` | ⚠ the *structural* claim holds (nothing re-arms at a section line inside a region: count 0, region unchanged). The *colour* claim does not: one tracer entry is not 48 words, and no buffer-vs-target or CRAM-vs-buffer read was taken, so "colours unchanged" is undecidable from what was recorded. |
| `t5-f358-snapback.png` | ✅ the structural claim (no fade arms leaving the region; the forest preset has `transition` 0). |
| `t5-f385-reversal-defect.png` | ✅ the defect it records is real and was fixed (`f122cce3` and the mid-fade-snap ruling). Structural. |

**So: every *timing and structural* row of this set stands. Every *colour* reading taken
from it does not**, including the channel means the NIGHT-REGION-LOOK ruling was measured
from. Those means should be treated as acceptance checks on a result, never as inputs to the
recipe — the transform finding in the 2026-09-16 note is unaffected, because it is derived
from the source recipe and from CRAM read off a booted machine and never reads a capture.

## What replaces it

`tools/night_settle_capture.py` captures the same edge and **runs until the fade has actually
settled**, deriving every filename from the state read on that tick
(`tools/capture_settle.py`). Feed that predicate this set's own recorded numbers for frame
272 and the name it produces is `in-k+005-t00272-cx3488-r09-pf11-fading.png` — there is no
input to it that produces the other name. `tools/test_capture_settle.py` holds exactly that,
parsing the table above.

The replacement set is **not captured yet**: it needs a live Oracle and a foreground run.
Until it exists, there is no settled night-colour reference in this repository, and that is
better than the one there appeared to be.
