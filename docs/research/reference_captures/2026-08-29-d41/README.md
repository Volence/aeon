# d-41 — the column-19 borrow, both halves, captured

Captured 2026-08-29 for the owner's d-41 ruling. **These are evidence for a decision, not a
gate.** Nothing here asserts anything; `tools/fg_left_edge_gate.py` is what can go red.

Produced by `tools/fg_left_edge_capture.py`, which refuses rather than guessing: it checks the
served ROM against the file on disk, that the scene cursor landed where it was driven, that VDP
reg `$0B` bit 2 is actually set at the sample point, and that `source == "raster"` — a post-hoc
state render is not the frame the raster drew and every mid-frame effect is missing from one.

| ROM | build | `s4.debug.bin` crc32 |
|---|---|---|
| `before-*` | aeon `cb469857` (the branch's own base, pre-fix) | `bcf682b5` |
| `after-*`  | aeon `b47b2448` (`parcel/fg-left-edge-vsram`)      | `3e59b91b` |

Assembler `sigil b73bf420e90c`, md5 `495986ee66a4e1e87c2e831a2a3a7de0`, unchanged across both
builds. Crops are x 0..31 and x 288..319, upscaled 6x; the full frames are 320x224 untouched.

## What each pair shows, at `Camera_Y = 144`

**Scene 13** is the honest one and the pair to read first.
`before`: `VSRAM $4C=0090 $4E=0005`, AND = `$000` against an expected `$090` — the leftmost
column renders 144 px out of position. `after`: `$4E` becomes `$0090`, AND = `$090`, correct.
- `*-scene13-left.png` — the defect and its repair. A brown diagonal branch runs continuously
  into the left edge in `after` and is absent in `before`.
- `*-scene13-right.png` — **the price.** The rightmost 16 px in `after` carry foreground-height
  background: a brown/orange strip above and purple flowers below, against a hard vertical seam
  at x=304. None of it is in `before`.

**Scene 12** is included because it is the scene that was asked for, and because it carries a
warning: on the PRE-FIX ROM its AND came out `$090` **by accident** — `$4E` happened to read
`$07F4`, a wobble phase whose bits happen to cover `$0090`. So `before-scene12-left.png` shows
no defect, and a reader comparing only that pair would conclude the fix does nothing. Its right
edge still shows the price. See `2026-08-29-vsram-column19-borrow.md`.

## The limit these pictures carry

The affected strip's WIDTH here is Oracle's model, which flattens it to 16 px where hardware and
GPGX say `hscroll & 15` — Oracle's own divergence P4. The displaced CONTENT is the hardware-tested
part; the exact width on real silicon is not, and we have no console to settle it.

---

## ⚠ AUDITED 2026-09-18 — read this before using these pictures

Nothing above has been edited; this is an append. It is what the tool that produced these
captures was later found to be doing, and what that does and does not cost.

`tools/fg_left_edge_capture.py` **never waited for the parallax crossfade to finish**
(`git log -S Parallax_Transition_Frames` over its whole history is empty). Every frame in
this directory was shot with `Parallax_Transition_Frames == 7`, mid-transition. Fixed
2026-09-18; the tool now settles and refuses to shoot inside the window.

**What that does NOT cost.** These are still pictures of the scenes they name: the renderer
is driven by `Parallax_Target_Config` during a transition, which is the REQUESTED scene, and
that was tested rather than read. Every VSRAM value quoted above is identical mid-window and
settled, and with the deform animation held fixed the crossfade moves no per-column V-scroll
at all. **The d-41 ruling rests on quantities the crossfade did not touch.**

**What it does cost.** The background's horizontal band scroll was still sliding: on scene 12
by 3 px on one band, on scene 13 by up to 46 px.

**⚠ And the scene-13 pair is invalid for a bigger, unrelated reason.** `658ebb8e`
(2026-09-02, d-50) made the borrow per-scene and scene 13 now DECLINES it, so
`after-scene13-*.png` shows behaviour the engine deliberately no longer has.

Full measurements, the instrument nulls, and re-shot frames:
`../2026-09-18-d41-resettled/README.md`.
