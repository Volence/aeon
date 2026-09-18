# d-41 re-capture — was the owner shown a crossfade, and does it matter?

**Answer: the pictures he ruled on are pictures of the scenes they claim to be, and the
crossfade changed nothing that the d-41 ruling turned on. The scene-13 pair is invalid
anyway, for a completely different and larger reason. Detail below.**

Shot 2026-09-18 from `s4.debug.bin` crc32 `62238a15` (848,075 B) with the post-sweep
`tools/fg_left_edge_capture.py`. **Nothing in `../2026-08-29-d41/` was touched** — that
directory is the record of what the owner was actually shown, and it is the thing under
audit.

Each scene here has TWO shots taken **from one ROM inside one run**:
* `midwindow-*` — the frame the OLD tool took, right after the cursor step, `Frames = 7`;
* `settled-*` — the frame the FIXED tool takes, after `Parallax_Transition_Frames` hits 0.

One ROM, one run, seven frames apart is what makes the settle effect **separable from the
intervening three weeks**: there is only one ROM, so no ROM difference can leak in.

## 1. Is the mid-window frame showing the PREVIOUS scene? NO — and that was tested

The worry was that a mid-crossfade frame shows the outgoing scene lerping toward the
requested one, which would make these pictures of the wrong scenes entirely.

Decided by experiment with a discriminator whose other outcome was possible. VDP reg `$0B`
bit 2 (per-column V-scroll) is re-asserted every frame **from the active config**, so
walking from a scene with bit 2 CLEAR to one with it SET separates the hypotheses:

```
settled at scene 6:  reg$0B=$03  bit2=CLEAR
step to scene 12, sampled INSIDE the window:
  +0f  Frames=7  Current=$013A1C (scene 6's)  Target=$013E90 (scene 12's)  reg$0B=$07 bit2=SET
```

**The register follows TARGET.** `Parallax_Update`'s Step 1 selects Target while the counter
is non-zero, so mode, bands and deform all come from the **requested** scene. Only the
scroll ACCUMULATORS (`Parallax_Current_Scroll_A/B`) are still lerping. The frame is the
right scene with its background still sliding into place — not the wrong scene.

⚠ Note the distinction the sweep's own write-up blurred: `Parallax_Current_Config` naming
the outgoing scene is what broke the GATE, which read that cell to pick its arm. The
RENDERER never reads it during a transition. Those are two different things.

## 2. Instrument nulls, stated BEFORE any difference number

| instrument | null — two SETTLED frames 7 apart, same scene, same ROM |
|---|---|
| raw pixel diff | scene 12: **40.8%** full / 42.7% left / 23.4% right · scene 13: **13.8% / 14.3% / 15.4%** |
| plane-B band scroll (px) | **0** on every band, both scenes |
| plane-B per-column V-scroll | non-zero — the deform PHASE advances every frame |

A pixel diff **cannot** answer this question: frames that are the same by construction
differ over a third of the frame, because the scene scrolls and deforms continuously. It is
rejected here as it was in the sweep. The band scroll has a null of 0 px. The per-column
words needed their animation removed — see §4.

## 3. What the crossfade actually changed

```
scene 12   VSRAM $4C=$0090 $4E=$0090  AND=$090  expected=$090   midwindow
           VSRAM $4C=$0090 $4E=$0090  AND=$090  expected=$090   settled      IDENTICAL
           plane-B band scroll  [-3,-53,-81,-109] -> [0,-53,-81,-109]   ONE BAND, 3 px

scene 13   VSRAM $4C=$0090 $4E=$0005  AND=$000  expected=$090   midwindow
           VSRAM $4C=$0090 $4E=$0005  AND=$000  expected=$090   settled      IDENTICAL
           plane-B band scroll  [0,-24,-36,-46]  -> [0,0,0,0]        up to 46 px
```

**Every VSRAM number the old README quotes is identical mid-window and settled.** The
d-41 ruling turned on those words and on the AND; the crossfade moved neither.

## 4. The per-column V-scroll — the quantity the borrow IS about — with animation held fixed

A band-scroll reading is horizontal and cannot see a vertical per-column difference, which
is why a first pass said "3 px" while the top-right of the frame plainly changed. The right
instrument is the 20 per-column plane-B V-scroll words, and its animation is removed by
**matching the deform phase**: shoot mid-window at phase P, settle, run on until
`Parallax_V_Deform_Phase_BG` reads P again, compare there.

```
scene 12: midwindow phase $0027; phase-matched settled frame 253 frames later
scene 13: midwindow phase $0076; phase-matched settled frame   1 frame  later
columns whose plane-B V-scroll differs, animation held fixed:  NONE, both scenes
   (scene 12 col 19 reads 144 at both = Camera_Y = the borrow doing its job)
```

**With the animation held fixed the crossfade moves no column at all.** The large visible
difference at the top right of `midwindow-scene12-right.png` — an orange slab absent from
`settled-scene12-right.png` — is the deform phase advancing from `$0027` to `$003C`, and it
appears and disappears with no transition anywhere near it. A first control that compared
two settled frames 7 apart happened to span `$003C`→`$0051`, saw no slab, and pointed the
wrong way; the phase-matched measurement is the one to believe.

## 5. ⚠ The scene-13 pair is INVALID — and not because of the crossfade

`658ebb8e`, **2026-09-02, "d-50: the column-19 borrow becomes per-scene, default ON"** —
four days after these captures — made the borrow declinable per scene, and scene 13
(`Perspective_Subtle`) **declines it**.

* old `after-scene13`: `$4E` becomes `$0090`, AND `$090` — the borrow ON, shown as the fix.
* today, settled: `$4E=$0005`, AND `$000`, `vds=$82 borrow=DECLINED` — and
  `fg_left_edge_gate` calls that **correct**, on its declining arm, GREEN.

The engine's answer for that scene was deliberately reversed after the ruling. No re-shoot
can reproduce `after-scene13`, and the difference has nothing to do with settling. **Scene
12 does not decline (`vds=$00`), so the scene-12 pair remains comparable, and it is the one
§3 and §4 rest on.**

## 6. What this CANNOT recover

The old captures were shot against `bcf682b5` (before) and `3e59b91b` (after); today's ROM
is `62238a15`. Those ROMs are not on disk and rebuilding them means an old `aeon` revision
against `sigil b73bf420e90c`. **So the old PNGs and the new ones are NOT compared here, and
no number in this directory is a before/after across those ROMs.** Three weeks of art,
scene, camera and VRAM-layout change sit between them and would be inseparable from the
settle. The settle question is answered instead by the one-ROM one-run pair above, where
that confound cannot exist. Anything a reader wants to conclude by eyeballing an old PNG
against a new one is confounded, and this directory does not support it.
