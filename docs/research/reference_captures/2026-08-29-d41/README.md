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
